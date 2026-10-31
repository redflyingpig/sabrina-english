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
# Deliberately NOT inside iCloud Drive or Documents: the LaunchAgent cannot read those without
# Full Disk Access (TCC returns "Operation not permitted"), so the note lives at the home root where
# the service can read it and Obsidian can still open it as a vault.
DEFAULT_PATH = Path.home() / VAULT_NAME / ALLOWLIST_FILENAME

HEADER = (
    "# 允许登录的名字\n\n"
    "> 每行一个名字，可以直接在 Obsidian 里增删。\n"
    "> 以 `-` 开头的列表项和普通文字都有效；`#` 开头的标题、`>` 开头的引用会被忽略。\n"
    "> 已经注册过的同学即使从这里删掉也能继续登录，这里只决定**新名字**能否建立档案。\n\n"
)


def path() -> Path:
    configured = os.environ.get("SABRINA_ALLOWLIST")
    return Path(configured).expanduser() if configured else DEFAULT_PATH


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


def read_names(target: Path = None) -> List[str]:
    target = target or path()
    try:
        return parse(target.read_text(encoding="utf-8"))
    except OSError as error:
        # An unreadable note (permissions, iCloud eviction) means "nobody new is invited"; log it so
        # the failure is visible instead of silently rejecting every new name.
        logging.getLogger("sabrina.allowlist").warning(
            "cannot read invite list %s: %s", target, error
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


def add(name: str, target: Path = None) -> str:
    target = target or path()
    normalized = normalize_name(name)
    names = read_names(target)
    if normalized not in names:
        names.append(normalized)
        _write(target, names)
    return normalized


def remove(name: str, target: Path = None) -> bool:
    target = target or path()
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
