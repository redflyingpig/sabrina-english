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
            f"{profile['display_name']}\tcreated={profile['created_at']}"
            f"\tupdated={profile['updated_at']}\n"
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
    args = parser.parse_args(argv)

    if args.command == "init-profiles":
        init_profiles(args.data_dir)
        return 0
    if args.command == "list-profiles":
        list_profiles(args.data_dir)
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
