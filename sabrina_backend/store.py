"""SQLite persistence for Sabrina English profiles and sessions."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union


SCHEMA_VERSION = 1
SESSION_DAYS = 90
PBKDF2_ITERATIONS = 600_000
EMPTY_STATE = {
    "version": 2,
    "history": [],
    "favorites": [],
    "streak": {"count": 0, "lastLearnedDate": ""},
}


class VersionConflict(Exception):
    """Raised when a client attempts to overwrite a newer state."""

    def __init__(self, current: Dict[str, Any]):
        super().__init__("Profile state version conflict")
        self.current = current


class Store:
    def __init__(self, db_path: Union[Path, str]):
        self.db_path = Path(db_path).expanduser()

    @staticmethod
    def normalize_username(username: str) -> str:
        if not isinstance(username, str):
            raise ValueError("Username must be text")
        return " ".join(username.strip().split()).casefold()

    @staticmethod
    def normalize_display_name(display_name: str) -> str:
        if not isinstance(display_name, str):
            raise ValueError("Display name must be text")
        normalized = " ".join(display_name.strip().split())
        if not 1 <= len(normalized) <= 32:
            raise ValueError("Display name must be 1 to 32 characters")
        return normalized

    @staticmethod
    def validate_pin(pin: str) -> None:
        if not isinstance(pin, str) or not 6 <= len(pin) <= 64:
            raise ValueError("PIN must be 6 to 64 characters")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys = on")
        connection.execute("pragma busy_timeout = 5000")
        return connection

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.db_path.parent, 0o700)
        except OSError:
            pass
        with self._connect() as connection:
            connection.execute("pragma journal_mode = wal")
            connection.executescript(
                """
                create table if not exists schema_version (
                    version integer not null
                );

                create table if not exists profiles (
                    id integer primary key,
                    username_normalized text not null unique,
                    display_name text not null,
                    pin_salt blob not null,
                    pin_hash blob not null,
                    state_json text not null,
                    state_version integer not null default 0,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists sessions (
                    token_hash text primary key,
                    profile_id integer not null references profiles(id) on delete cascade,
                    created_at text not null,
                    expires_at text not null
                );

                create index if not exists sessions_profile_id_idx
                    on sessions(profile_id);
                create index if not exists sessions_expires_at_idx
                    on sessions(expires_at);
                """
            )
            row = connection.execute("select version from schema_version").fetchone()
            if row is None:
                connection.execute(
                    "insert into schema_version(version) values (?)", (SCHEMA_VERSION,)
                )
            elif row["version"] != SCHEMA_VERSION:
                raise RuntimeError(f"Unsupported schema version: {row['version']}")
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _pin_hash(pin: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256", pin.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32
        )

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    def create_profile(self, display_name: str, pin: str) -> int:
        display_name = self.normalize_display_name(display_name)
        username = self.normalize_username(display_name)
        self.validate_pin(pin)
        salt = secrets.token_bytes(16)
        now = self._utc_now().isoformat()
        state = json.dumps(EMPTY_STATE, separators=(",", ":"), ensure_ascii=False)
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    insert into profiles (
                        username_normalized, display_name, pin_salt, pin_hash,
                        state_json, state_version, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        username,
                        display_name,
                        salt,
                        self._pin_hash(pin, salt),
                        state,
                        now,
                        now,
                    ),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as error:
            raise ValueError("Profile already exists") from error

    def authenticate(self, username: str, pin: str) -> Optional[Dict[str, Any]]:
        try:
            normalized = self.normalize_username(username)
            self.validate_pin(pin)
        except ValueError:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "select id, display_name, pin_salt, pin_hash from profiles "
                "where username_normalized = ?",
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        candidate = self._pin_hash(pin, row["pin_salt"])
        if not hmac.compare_digest(candidate, row["pin_hash"]):
            return None
        return {"id": row["id"], "display_name": row["display_name"]}

    def create_session(self, profile_id: int) -> str:
        token = secrets.token_urlsafe(32)
        created = self._utc_now()
        expires = created + timedelta(days=SESSION_DAYS)
        with self._connect() as connection:
            connection.execute(
                "insert into sessions(token_hash, profile_id, created_at, expires_at) "
                "values (?, ?, ?, ?)",
                (
                    self._token_hash(token),
                    profile_id,
                    created.isoformat(),
                    expires.isoformat(),
                ),
            )
        return token

    def resolve_session(self, token: str) -> Optional[Dict[str, Any]]:
        if not isinstance(token, str) or not token:
            return None
        now = self._utc_now().isoformat()
        token_hash = self._token_hash(token)
        with self._connect() as connection:
            connection.execute("delete from sessions where expires_at <= ?", (now,))
            row = connection.execute(
                """
                select profiles.id, profiles.display_name
                from sessions
                join profiles on profiles.id = sessions.profile_id
                where sessions.token_hash = ? and sessions.expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "display_name": row["display_name"]}

    def delete_session(self, token: str) -> None:
        if not isinstance(token, str) or not token:
            return
        with self._connect() as connection:
            connection.execute(
                "delete from sessions where token_hash = ?", (self._token_hash(token),)
            )

    def read_state(self, profile_id: int) -> Dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "select display_name, state_json, state_version from profiles where id = ?",
                (profile_id,),
            ).fetchone()
        if row is None:
            raise KeyError("Profile not found")
        return {
            "display_name": row["display_name"],
            "state": json.loads(row["state_json"]),
            "state_version": row["state_version"],
        }

    def write_state(
        self, profile_id: int, expected_version: int, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not isinstance(expected_version, int) or expected_version < 0:
            raise ValueError("State version must be a non-negative integer")
        if not isinstance(state, dict):
            raise ValueError("State must be an object")
        serialized = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
        now = self._utc_now().isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                update profiles
                set state_json = ?, state_version = state_version + 1, updated_at = ?
                where id = ? and state_version = ?
                """,
                (serialized, now, profile_id, expected_version),
            )
            if cursor.rowcount != 1:
                current = connection.execute(
                    "select display_name, state_json, state_version from profiles where id = ?",
                    (profile_id,),
                ).fetchone()
                if current is None:
                    raise KeyError("Profile not found")
                raise VersionConflict(
                    {
                        "display_name": current["display_name"],
                        "state": json.loads(current["state_json"]),
                        "state_version": current["state_version"],
                    }
                )
        return self.read_state(profile_id)
