"""Validate and manifest the static Sabrina English lesson library."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


CONTENT_FILES = (
    "vocabulary-a1.json",
    "vocabulary-a2.json",
    "vocabulary-b1.json",
    "vocabulary-b2.json",
    "expressions.json",
    "patterns.json",
)
DEFAULT_MINIMUMS = {"vocabulary": 4000, "expressions": 600, "patterns": 250}
ALLOWED_LEVELS = {"A1", "A2", "B1", "B2"}


def normalize_identity(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def _kind_for(filename: str) -> str:
    if filename.startswith("vocabulary-"):
        return "vocabulary"
    if filename == "expressions.json":
        return "expressions"
    return "patterns"


def _load_json(path: Path, errors: List[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing file {path.name}")
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"cannot read {path.name}: {error}")
    return None


def _non_empty_string(row: Dict[str, Any], field: str, label: str, errors: List[str]) -> bool:
    if field not in row:
        errors.append(f"{label}: missing {field}")
        return False
    if not isinstance(row[field], str) or not row[field].strip():
        errors.append(f"{label}: {field} must be a non-empty string")
        return False
    return True


def _validate_row(
    row: Any,
    filename: str,
    index: int,
    kind: str,
    errors: List[str],
) -> Optional[Tuple[str, str]]:
    label = f"{filename}[{index}]"
    if not isinstance(row, dict):
        errors.append(f"{label}: entry must be an object")
        return None

    common = ("id", "level", "topic")
    if kind == "vocabulary":
        fields = common + ("word", "phonetic", "translation", "example")
        identity_field = "word"
    elif kind == "expressions":
        fields = common + ("expression", "usage", "example")
        identity_field = "expression"
    else:
        fields = common + ("pattern", "explanation")
        identity_field = "pattern"

    for field in fields:
        _non_empty_string(row, field, label, errors)

    level = row.get("level")
    if level not in ALLOWED_LEVELS:
        errors.append(f"{label}: invalid level {level}")
    if filename.startswith("vocabulary-"):
        expected_level = filename[len("vocabulary-") : -len(".json")].upper()
        if level in ALLOWED_LEVELS and level != expected_level:
            errors.append(f"{label}: level {level} does not match {expected_level} shard")

    if kind == "patterns":
        examples = row.get("examples")
        if not isinstance(examples, list) or not examples or any(
            not isinstance(example, str) or not example.strip() for example in examples
        ):
            errors.append(f"{label}: examples must contain non-empty strings")

    identity = row.get(identity_field)
    item_id = row.get("id")
    if isinstance(identity, str) and isinstance(item_id, str):
        return item_id, normalize_identity(identity)
    return None


def validate_library(
    content_dir: Path, minimums: Optional[Dict[str, int]] = None
) -> List[str]:
    content_dir = Path(content_dir)
    required = dict(DEFAULT_MINIMUMS if minimums is None else minimums)
    errors: List[str] = []
    rows_by_file: Dict[str, List[Any]] = {}
    counts = {"vocabulary": 0, "expressions": 0, "patterns": 0}
    seen_ids = set()
    seen_content = {"vocabulary": set(), "expressions": set(), "patterns": set()}

    for filename in CONTENT_FILES:
        payload = _load_json(content_dir / filename, errors)
        if payload is None:
            continue
        if not isinstance(payload, list):
            errors.append(f"{filename}: top level must be an array")
            continue
        rows_by_file[filename] = payload
        kind = _kind_for(filename)
        counts[kind] += len(payload)
        for index, row in enumerate(payload):
            identity = _validate_row(row, filename, index, kind, errors)
            if identity is None:
                continue
            item_id, normalized = identity
            if item_id in seen_ids:
                errors.append(f"{filename}[{index}]: duplicate id {item_id}")
            seen_ids.add(item_id)
            if normalized in seen_content[kind]:
                errors.append(f"{filename}[{index}]: duplicate {kind.rstrip('s')} {normalized}")
            seen_content[kind].add(normalized)

    for kind, minimum in required.items():
        actual = counts.get(kind, 0)
        if actual < minimum:
            errors.append(f"{kind} count {actual} is below {minimum}")

    manifest = _load_json(content_dir / "manifest.json", errors)
    if isinstance(manifest, dict):
        if manifest.get("counts") != counts:
            errors.append("manifest counts do not match content files")
        manifest_files = manifest.get("files")
        if not isinstance(manifest_files, dict):
            errors.append("manifest files must be an object")
        else:
            for filename in CONTENT_FILES:
                metadata = manifest_files.get(filename)
                if not isinstance(metadata, dict):
                    errors.append(f"manifest missing metadata for {filename}")
                    continue
                path = content_dir / filename
                if path.is_file():
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    if metadata.get("sha256") != digest:
                        errors.append(f"sha256 mismatch for {filename}")
                    if metadata.get("count") != len(rows_by_file.get(filename, [])):
                        errors.append(f"count mismatch for {filename}")
    elif manifest is not None:
        errors.append("manifest.json: top level must be an object")

    return errors


def write_manifest(content_dir: Path, version: str) -> Path:
    content_dir = Path(content_dir)
    files: Dict[str, Dict[str, Any]] = {}
    counts = {"vocabulary": 0, "expressions": 0, "patterns": 0}
    for filename in CONTENT_FILES:
        path = content_dir / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{filename} must contain an array")
        kind = _kind_for(filename)
        count = len(payload)
        counts[kind] += count
        files[filename] = {
            "kind": kind,
            "count": count,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    manifest = {"version": version, "files": files, "counts": counts}
    destination = content_dir / "manifest.json"
    destination.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return destination


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Sabrina English content")
    parser.add_argument("content_dir", type=Path)
    args = parser.parse_args(argv)
    errors = validate_library(args.content_dir)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("content library: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
