"""Invite allowlist stored as a Markdown file inside an Obsidian vault.

The list is intentionally a plain note: the site owner keeps it in Obsidian, edits it there, and
the service reads it on every sign-in so a change takes effect without a restart.

Format (tolerant):
    # comments are ignored
    - Sabrina          <- a Markdown list item
    Max                <- or a bare line
Blank lines are ignored. Matching is case- and spacing-insensitive.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Iterable, List

VAULT_NAME = "Sabrina Config"
ALLOWLIST_FILENAME = "allowlist.md"

# Primary: the iCloud Obsidian vault, so the note syncs to other devices and shows up in Obsidian's
# vault switcher. macOS protects iCloud Drive, so the LaunchAgent can only read it after Full Disk
# Access is granted; until then the service falls back to the local vault below.
ICLOUD_PATH = (
    Path.home()
    / "Library/Mobile Documents/iCloud~md~obsidian/Documents"
    / VAULT_NAME
    / ALLOWLIST_FILENAME
)
# Fallback: a plain folder at the home root, always readable by the service.
LOCAL_PATH = Path.home() / VAULT_NAME / ALLOWLIST_FILENAME
DEFAULT_PATH = ICLOUD_PATH

HEADER = (
    "# 允许登录的名字\n\n"
    "> 每行一个名字，可以直接在 Obsidian 里增删。\n"
    "> 以 `-` 开头的列表项和普通文字都有效；`#` 开头的标题、`>` 开头的引用会被忽略。\n"
    "> 已经注册过的同学即使从这里删掉也能继续登录，这里只决定**新名字**能否建立档案。\n\n"
)


def configured_path():
    value = os.environ.get("SABRINA_ALLOWLIST")
    return Path(value).expanduser() if value else None


def path() -> Path:
    return configured_path() or DEFAULT_PATH


def normalize_name(value: str) -> str:
    return " ".join(str(value or "").strip().split()).casefold()


def parse(text: str) -> List[str]:
    names: List[str] = []
    seen = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(">"):
            continue
        line = re.sub(r"^[-*+]\s+|^\d+\.\s+", "", line).strip()
        line = line.strip("*_` ")
        if not line:
            continue
        normalized = normalize_name(line)
        if normalized and normalized not in seen:
            seen.add(normalized)
            names.append(normalized)
    return names


def candidates() -> List[Path]:
    configured = configured_path()
    return [configured] if configured else [ICLOUD_PATH, LOCAL_PATH]


def read_names(target: Path = None) -> List[str]:
    """Read the first existing note; fall back to the local vault when iCloud is unreadable."""
    paths = [target] if target else candidates()
    for candidate in paths:
        if not candidate.exists():
            continue
        try:
            return parse(candidate.read_text(encoding="utf-8"))
        except OSError as error:
            # iCloud Drive is TCC-protected: a launchd process gets "Operation not permitted" unless
            # the interpreter has Full Disk Access. Log it and try the local fallback.
            logging.getLogger("sabrina.allowlist").warning(
                "cannot read invite list %s: %s", candidate, error
            )
    return []


def _write(target: Path, names: Iterable[str]) -> None:
    ordered = sorted({normalize_name(name) for name in names if normalize_name(name)})
    body = HEADER + "".join(f"- {name}\n" for name in ordered)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=str(target.parent), prefix=".allowlist-", suffix=".md")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(body)
        os.chmod(temp, 0o600)
        os.replace(temp, target)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def writable_path() -> Path:
    """Prefer the synced iCloud note; fall back to the local vault when it is not writable."""
    configured = configured_path()
    if configured:
        return configured
    try:
        ICLOUD_PATH.parent.mkdir(parents=True, exist_ok=True)
        return ICLOUD_PATH
    except OSError as error:
        logging.getLogger("sabrina.allowlist").warning(
            "cannot write to %s (%s); using %s", ICLOUD_PATH, error, LOCAL_PATH
        )
        return LOCAL_PATH


def add(name: str, target: Path = None) -> str:
    target = target or writable_path()
    normalized = normalize_name(name)
    names = read_names(target)
    if normalized not in names:
        names.append(normalized)
        _write(target, names)
    return normalized


def remove(name: str, target: Path = None) -> bool:
    target = target or writable_path()
    normalized = normalize_name(name)
    names = read_names(target)
    if normalized not in names:
        return False
    _write(target, [item for item in names if item != normalized])
    return True


def ensure_file(target: Path = None, seed: Iterable[str] = ()) -> Path:
    target = target or path()
    if not target.exists():
        _write(target, seed)
    return target
