"""Local-only profile administration for Sabrina English."""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence, TextIO

from . import allowlist
from .store import Store


PROFILE_NAMES = ("Owner", "Sabrina", "Max")


def default_data_dir() -> Path:
    configured = os.environ.get("SABRINA_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "Library/Application Support/SabrinaEnglish"


def _store(data_dir: Path) -> Store:
    store = Store(Path(data_dir) / "sabrina.db")
    store.initialize()
    return store


def _random_pin(existing=None) -> str:
    existing = set(existing or ())
    while True:
        pin = f"{secrets.randbelow(100_000_000):08d}"
        if pin not in existing:
            return pin


def init_profiles(data_dir: Path, output: TextIO = sys.stdout) -> Dict[str, str]:
    store = _store(data_dir)
    existing = {profile["display_name"].casefold() for profile in store.list_profiles()}
    created: Dict[str, str] = {}
    for name in PROFILE_NAMES:
        if name.casefold() in existing:
            continue
        pin = _random_pin(created.values())
        store.create_profile(name, pin)
        created[name] = pin
    if created:
        output.write(
            "Profiles created. The website uses username-only login; "
            "compatibility PINs are not shown or used.\n"
        )
    else:
        output.write("Profiles already initialized.\n")
    return created


def reset_pin(data_dir: Path, username: str, pin: str) -> str:
    store = _store(data_dir)
    return store.reset_pin(username, pin)


def list_profiles(data_dir: Path, output: TextIO = sys.stdout) -> None:
    store = _store(data_dir)
    for profile in store.list_profiles():
        output.write(
            f"{profile['display_name']}\temail={profile.get('email') or '-'}"
            f"\tcreated={profile['created_at']}\tupdated={profile['updated_at']}\n"
        )


def allow_name(data_dir: Path, username: str, output: TextIO = sys.stdout) -> None:
    normalized = allowlist.add(username)
    output.write(f"已加入白名单：{normalized}\n写入 {allowlist.path()}\n")


def disallow_name(data_dir: Path, username: str, output: TextIO = sys.stdout) -> None:
    removed = allowlist.remove(username)
    verb = "已移出白名单" if removed else "白名单里没有"
    output.write(f"{verb}：{allowlist.normalize_name(username)}\n名单文件 {allowlist.path()}\n")


def list_allowlist(data_dir: Path, output: TextIO = sys.stdout) -> None:
    names = allowlist.read_names()
    output.write(f"名单文件：{allowlist.path()}\n")
    if not names:
        output.write("(空：只有已经注册过的名字能登录)\n")
        return
    for name in names:
        output.write(f"- {name}\n")


def sync_allowlist(data_dir: Path, output: TextIO = sys.stdout) -> None:
    """Copy the iCloud note into the local fallback (run from a shell that can read iCloud)."""
    if not allowlist.ICLOUD_PATH.exists():
        output.write(f"iCloud 名单不存在：{allowlist.ICLOUD_PATH}\n")
        return
    try:
        text = allowlist.ICLOUD_PATH.read_text(encoding="utf-8")
    except OSError as error:
        output.write(f"读取 iCloud 名单失败：{error}\n请给运行服务的 Python 授予「完全磁盘访问」。\n")
        return
    names = allowlist.parse(text)
    allowlist._write(allowlist.LOCAL_PATH, names)
    output.write(
        f"已同步 {len(names)} 个名字到本机兜底文件\n"
        f"  源：{allowlist.ICLOUD_PATH}\n  目标：{allowlist.LOCAL_PATH}\n"
    )


def rename_profile(data_dir: Path, username: str, new_name: str, output: TextIO = sys.stdout) -> None:
    store = _store(data_dir)
    renamed = store.rename_profile(username, new_name)
    output.write(f"已改名：{username} → {renamed['display_name']}\n")


def delete_profile(data_dir: Path, username: str, output: TextIO = sys.stdout) -> None:
    store = _store(data_dir)
    removed = store.delete_profile(username)
    output.write(
        f"已删除档案：{removed['display_name']}（id={removed['id']}, "
        f"email={removed['email'] or '-'}, 清除会话 {removed['sessions']} 个）\n"
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Manage Sabrina English profiles")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-profiles")
    reset_parser = subparsers.add_parser("reset-pin")
    reset_parser.add_argument("username")
    reset_parser.add_argument("--generate", action="store_true")
    subparsers.add_parser("list-profiles")
    allow_parser = subparsers.add_parser("allow")
    allow_parser.add_argument("username")
    subparsers.add_parser("sync-allowlist")
    unallow_parser = subparsers.add_parser("unallow")
    unallow_parser.add_argument("username")
    subparsers.add_parser("list-allowlist")
    delete_parser = subparsers.add_parser("delete-profile")
    delete_parser.add_argument("username")
    rename_parser = subparsers.add_parser("rename")
    rename_parser.add_argument("username")
    rename_parser.add_argument("new_name")
    args = parser.parse_args(argv)

    if args.command == "init-profiles":
        init_profiles(args.data_dir)
        return 0
    if args.command == "list-profiles":
        list_profiles(args.data_dir)
        return 0
    if args.command == "allow":
        allow_name(args.data_dir, args.username)
        return 0
    if args.command == "sync-allowlist":
        sync_allowlist(args.data_dir)
        return 0
    if args.command == "unallow":
        disallow_name(args.data_dir, args.username)
        return 0
    if args.command == "list-allowlist":
        list_allowlist(args.data_dir)
        return 0
    if args.command == "delete-profile":
        delete_profile(args.data_dir, args.username)
        return 0
    if args.command == "rename":
        rename_profile(args.data_dir, args.username, args.new_name)
        return 0
    if args.command == "reset-pin":
        pin = _random_pin() if args.generate else getpass.getpass("New PIN (6-64 chars): ")
        display_name = reset_pin(args.data_dir, args.username, pin)
        if args.generate:
            print(f"{display_name}: {pin}")
        else:
            print(f"PIN reset for {display_name}; existing sessions were signed out.")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
