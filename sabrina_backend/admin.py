"""Local-only profile administration for Sabrina English."""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence, TextIO

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


def bind_email(data_dir: Path, username: str, email: str, output: TextIO = sys.stdout) -> None:
    store = _store(data_dir)
    store.bind_profile_email(username, email)
    output.write(f"已把 {username} 绑定到 {store.normalize_email(email)}\n")


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
    bind_parser = subparsers.add_parser("bind-email")
    bind_parser.add_argument("username")
    bind_parser.add_argument("email")
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
    if args.command == "bind-email":
        bind_email(args.data_dir, args.username, args.email)
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
