"""Consistent SQLite backup and retention for Sabrina English."""

from __future__ import annotations

import argparse
import contextlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from .admin import default_data_dir


def backup_database(
    data_dir: Path, keep: int = 30, now: Optional[datetime] = None
) -> Path:
    data_dir = Path(data_dir).expanduser()
    source_path = data_dir / "sabrina.db"
    if not source_path.is_file():
        raise FileNotFoundError(f"Database not found: {source_path}")
    if keep < 1:
        raise ValueError("keep must be at least 1")

    backup_dir = data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(backup_dir, 0o700)
    except OSError:
        pass
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    filename = f"sabrina-{timestamp.strftime('%Y%m%dT%H%M%SZ')}.db"
    destination = backup_dir / filename
    temporary = backup_dir / f".{filename}.tmp"

    try:
        with contextlib.closing(sqlite3.connect(source_path)) as source, contextlib.closing(
            sqlite3.connect(temporary)
        ) as target:
            source.backup(target)
        with contextlib.closing(sqlite3.connect(temporary)) as check:
            # Finish the copied WAL inside the temporary file and leave the finished backup in
            # rollback-journal mode: a backup must be readable on its own, without -wal/-shm
            # sidecars and without write access to the backup directory.
            check.execute("pragma journal_mode = delete")
            integrity = check.execute("pragma integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"Backup integrity check failed: {integrity}")
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        # Connections stay closed above, so anything left behind is stale sidecar residue.
        for leftover in (
            temporary,
            Path(f"{temporary}-wal"),
            Path(f"{temporary}-shm"),
            Path(f"{destination}-wal"),
            Path(f"{destination}-shm"),
        ):
            with contextlib.suppress(FileNotFoundError):
                leftover.unlink()

    backups = sorted(backup_dir.glob("sabrina-*.db"), reverse=True)
    for expired in backups[keep:]:
        expired.unlink()
    return destination


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Back up Sabrina English")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--keep", type=int, default=30)
    args = parser.parse_args(argv)
    print(backup_database(args.data_dir, args.keep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
