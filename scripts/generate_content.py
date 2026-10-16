"""Generate the versioned Sabrina English lesson library."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

if __package__:
    from .example_templates import (
        EXPRESSION_FRAMES,
        EXPRESSION_ITEMS,
        PATTERN_BASES,
        PATTERN_CONTEXTS,
        build_example,
    )
    from .validate_content import normalize_identity, validate_library, write_manifest
else:
    from example_templates import (  # type: ignore
        EXPRESSION_FRAMES,
        EXPRESSION_ITEMS,
        PATTERN_BASES,
        PATTERN_CONTEXTS,
        build_example,
    )
    from validate_content import normalize_identity, validate_library, write_manifest  # type: ignore


SOURCE_REVISION = "82c9872576b23118d7c42e920c11beb77f510ae2"
SOURCE_SHA256 = "1a6947e04785db63613a92e14903cdae7954f7e84860b10e68e5c7cbb3f9c3cf"
CONTENT_VERSION = "2026.10.16-1"
LEVEL_COUNTS = (("A1", 800), ("A2", 1200), ("B1", 1200), ("B2", 800))
WORD_PATTERN = re.compile(r"[a-z]+(?:-[a-z]+)?")
CHINESE_PATTERN = re.compile(r"[\u3400-\u9fff]")
PROPER_NAME_PATTERN = re.compile(r"男子名|女子名|人名|地名|国名|姓氏")

DENY_WORDS = {
    "ain",
    "aren",
    "couldn",
    "didn",
    "doesn",
    "don",
    "hadn",
    "hasn",
    "haven",
    "isn",
    "mightn",
    "mustn",
    "needn",
    "shan",
    "shouldn",
    "wasn",
    "weren",
    "won",
    "wouldn",
}

TOPIC_WORDS = {
    "family": {"family", "parent", "mother", "father", "child", "baby", "brother", "sister", "marry", "relative"},
    "school": {"school", "student", "teacher", "lesson", "class", "learn", "study", "exam", "homework", "book"},
    "work": {"work", "job", "office", "meeting", "manager", "staff", "career", "business", "report", "project"},
    "shopping": {"shop", "store", "buy", "sell", "price", "cost", "pay", "cash", "market", "customer"},
    "food": {"food", "eat", "drink", "meal", "cook", "bread", "fruit", "vegetable", "restaurant", "kitchen"},
    "health": {"health", "doctor", "nurse", "medicine", "pain", "sick", "exercise", "body", "hospital", "sleep"},
    "transport": {"bus", "train", "car", "road", "station", "drive", "ride", "traffic", "airport", "ticket"},
    "travel": {"travel", "trip", "tour", "hotel", "visit", "journey", "holiday", "passport", "luggage", "flight"},
    "weather": {"weather", "rain", "snow", "wind", "cloud", "sunny", "storm", "temperature", "warm", "cold"},
    "home": {"home", "house", "room", "door", "window", "chair", "table", "bed", "garden", "clean"},
    "relationships": {"friend", "love", "help", "kind", "talk", "meet", "invite", "share", "trust", "together"},
    "entertainment": {"music", "film", "movie", "game", "sport", "dance", "sing", "play", "party", "concert"},
    "digital-life": {"computer", "phone", "internet", "online", "email", "message", "screen", "website", "digital", "video"},
    "public-services": {"police", "library", "bank", "post", "service", "government", "law", "public", "clinic", "council"},
    "time": {"time", "day", "week", "month", "year", "today", "tomorrow", "early", "late", "schedule"},
    "nature": {"nature", "tree", "plant", "animal", "river", "sea", "mountain", "forest", "earth", "environment"},
}


def _source_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_ecdict(path: Path) -> Iterator[Dict[str, str]]:
    if _source_digest(path) != SOURCE_SHA256:
        raise ValueError("ECDICT source SHA-256 does not match the pinned build input")
    with path.open(encoding="utf-8-sig", newline="") as source:
        yield from csv.DictReader(source)


def _rank(row: Dict[str, str]) -> Optional[int]:
    ranks = []
    for field in ("bnc", "frq"):
        value = row.get(field, "").strip()
        if value.isdigit() and int(value) > 0:
            ranks.append(int(value))
    return min(ranks) if ranks else None


def _translation(value: str) -> str:
    value = value.replace(r"\n", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    preferred = [
        line
        for line in lines
        if CHINESE_PATTERN.search(line)
        and not re.match(r"^\[(计|医|化|经|网络|法|地质|农|建|航)]", line)
    ]
    candidates = preferred or [line for line in lines if CHINESE_PATTERN.search(line)]
    if not candidates:
        return ""
    cleaned = re.sub(r"^(?:[a-z]+\.)+\s*", "", candidates[0], flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*[\[【].*$", "", cleaned).strip(" ;；,，")
    return cleaned[:120].strip()


def rank_daily_words(rows: Iterable[Dict[str, str]], limit: int = 4000) -> List[Dict[str, str]]:
    eligible: List[Tuple[int, str, Dict[str, str]]] = []
    seen = set()
    for row in rows:
        source_word = row.get("word", "").strip()
        word = source_word.casefold()
        normalized = normalize_identity(word)
        rank = _rank(row)
        translation = _translation(row.get("translation", ""))
        phonetic = row.get("phonetic", "").strip()
        if (
            not WORD_PATTERN.fullmatch(word)
            or source_word != source_word.lower()
            or word in DENY_WORDS
            or normalized in seen
            or rank is None
            or not phonetic
            or not translation
            or PROPER_NAME_PATTERN.search(translation)
        ):
            continue
        seen.add(normalized)
        copy = dict(row)
        copy["word"] = word
        copy["translation_clean"] = translation
        eligible.append((rank, word, copy))
    eligible.sort(key=lambda item: (item[0], item[1]))
    if len(eligible) < limit:
        raise ValueError(f"only {len(eligible)} suitable daily words found; need {limit}")
    return [row for _, _, row in eligible[:limit]]


def assign_level(index: int) -> str:
    cursor = 0
    for level, count in LEVEL_COUNTS:
        cursor += count
        if index < cursor:
            return level
    raise ValueError(f"vocabulary index {index} exceeds configured level counts")


def assign_topic(word: str) -> str:
    for topic, keywords in TOPIC_WORDS.items():
        if word in keywords or any(word.startswith(keyword) for keyword in keywords if len(keyword) >= 5):
            return topic
    return "daily-life"


def _slug(value: str) -> str:
    return normalize_identity(value).replace(" ", "-")


def _write_json(path: Path, payload: Sequence[Dict[str, object]]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _vocabulary(rows: Sequence[Dict[str, str]]) -> Dict[str, List[Dict[str, object]]]:
    shards = {level: [] for level, _ in LEVEL_COUNTS}
    for index, row in enumerate(rows):
        level = assign_level(index)
        word = row["word"]
        topic = assign_topic(word)
        phonetic = row["phonetic"].strip().strip("/")
        shards[level].append(
            {
                "id": f"v1:{_slug(word)}",
                "level": level,
                "topic": topic,
                "word": word,
                "phonetic": f"/{phonetic}/",
                "translation": row["translation_clean"],
                "example": build_example(row, topic),
            }
        )
    return shards


def _expressions() -> List[Dict[str, object]]:
    result = []
    for frame_index, (frame, usage, example, level) in enumerate(EXPRESSION_FRAMES):
        for item_index, (item, topic) in enumerate(EXPRESSION_ITEMS):
            expression = frame.format(item=item)
            result.append(
                {
                    "id": f"e1:{frame_index + 1:02d}-{item_index + 1:02d}-{_slug(expression)[:48]}",
                    "level": level,
                    "topic": topic,
                    "expression": expression,
                    "usage": usage,
                    "example": example.format(item=item),
                }
            )
    return result


def _patterns() -> List[Dict[str, object]]:
    result = []
    for base_index, (base, explanation, example, level) in enumerate(PATTERN_BASES):
        for context_index, (context, example_context, topic) in enumerate(PATTERN_CONTEXTS):
            pattern = base.format(context=context)
            rendered = example.format(example_context=example_context)
            result.append(
                {
                    "id": f"p1:{base_index + 1:02d}-{context_index + 1:02d}-{_slug(pattern)[:48]}",
                    "level": level,
                    "topic": topic,
                    "pattern": pattern,
                    "explanation": explanation,
                    "examples": [
                        rendered,
                        f"Try changing one word in this {context} pattern.",
                        f"Use this pattern in a short conversation {example_context}.",
                    ],
                }
            )
    return result


def generate_library(source_csv: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    vocabulary = _vocabulary(rank_daily_words(load_ecdict(source_csv)))
    for level, rows in vocabulary.items():
        _write_json(output_dir / f"vocabulary-{level.lower()}.json", rows)
    _write_json(output_dir / "expressions.json", _expressions())
    _write_json(output_dir / "patterns.json", _patterns())
    write_manifest(output_dir, CONTENT_VERSION)
    errors = validate_library(output_dir)
    if errors:
        raise ValueError("generated content is invalid:\n" + "\n".join(errors))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Sabrina English content")
    parser.add_argument("--ecdict", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    generate_library(args.ecdict, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
