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


SCHEMA_VERSION = 3
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
                    updated_at text not null,
                    email text
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

                create table if not exists allowlist (
                    username_normalized text primary key,
                    added_at text not null
                );
                """
            )
            row = connection.execute("select version from schema_version").fetchone()
            if row is None:
                connection.execute(
                    "insert into schema_version(version) values (?)", (SCHEMA_VERSION,)
                )
            elif row["version"] in (1, 2):
                # v2 added the (now dormant) email column; v3 adds the invite allowlist, which the
                # create-table block above already provisioned.
                columns = {
                    info["name"]
                    for info in connection.execute("pragma table_info(profiles)").fetchall()
                }
                if "email" not in columns:
                    connection.execute("alter table profiles add column email text")
                connection.execute("update schema_version set version = 3")
            elif row["version"] != SCHEMA_VERSION:
                raise RuntimeError(f"Unsupported schema version: {row['version']}")
            # Created after the migration above so a v1 database without the column still upgrades.
            connection.execute(
                "create index if not exists profiles_email_idx on profiles(email)"
            )
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

    # ---- invite allowlist ---------------------------------------------------------------------
    # The site is shared with classmates, so a brand-new name only becomes a study profile when it is
    # on the invite list. Names that already have a profile keep working without being listed.

    def is_allowlisted(self, display_name: str) -> bool:
        normalized = self.normalize_username(self.normalize_display_name(display_name))
        with self._connect() as connection:
            row = connection.execute(
                "select 1 from allowlist where username_normalized = ?", (normalized,)
            ).fetchone()
        return row is not None

    def allowlist_add(self, display_name: str) -> str:
        normalized = self.normalize_username(self.normalize_display_name(display_name))
        with self._connect() as connection:
            connection.execute(
                "insert or ignore into allowlist (username_normalized, added_at) values (?, ?)",
                (normalized, self._utc_now().isoformat()),
            )
        return normalized

    def allowlist_remove(self, display_name: str) -> bool:
        normalized = self.normalize_username(self.normalize_display_name(display_name))
        with self._connect() as connection:
            cursor = connection.execute(
                "delete from allowlist where username_normalized = ?", (normalized,)
            )
        return cursor.rowcount > 0

    def allowlist_list(self) -> List[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "select username_normalized from allowlist order by username_normalized"
            ).fetchall()
        return [row["username_normalized"] for row in rows]

    def login_or_create(self, display_name: str) -> Dict[str, Any]:
        """Sign in an existing profile, or create one when the name is on the invite list.

        Raises PermissionError when the name is new and not listed, so the route can answer 403
        instead of silently minting a profile.
        """
        normalized_name = self.normalize_display_name(display_name)
        existing = self.find_profile(normalized_name)
        if existing is not None:
            return {"id": existing["id"], "display_name": existing["display_name"], "created": False}
        if not self.is_allowlisted(normalized_name):
            raise PermissionError("This username is not on the invite list")
        try:
            profile_id = self.create_profile(normalized_name, secrets.token_urlsafe(32))
        except ValueError:
            # Lost a race with a concurrent request for the same name: use the winner's profile.
            existing = self.find_profile(normalized_name)
            if existing is None:
                raise
            return {"id": existing["id"], "display_name": existing["display_name"], "created": False}
        return {"id": profile_id, "display_name": normalized_name, "created": True}


    def delete_profile(self, display_name: str) -> Dict[str, Any]:
        """Delete a profile and its sessions. Study data is not recoverable without a backup."""
        normalized = self.normalize_username(self.normalize_display_name(display_name))
        with self._connect() as connection:
            row = connection.execute(
                "select id, display_name, email from profiles where username_normalized = ?",
                (normalized,),
            ).fetchone()
            if row is None:
                raise KeyError(f"No profile named {display_name}")
            sessions = connection.execute(
                "delete from sessions where profile_id = ?", (row["id"],)
            ).rowcount
            connection.execute("delete from profiles where id = ?", (row["id"],))
        return {
            "id": row["id"],
            "display_name": row["display_name"],
            "email": row["email"],
            "sessions": sessions,
        }

    def rename_profile(self, display_name: str, new_display_name: str) -> Dict[str, Any]:
        """Rename a profile (display name and its unique normalized key)."""
        normalized = self.normalize_username(self.normalize_display_name(display_name))
        new_name = self.normalize_display_name(new_display_name)
        new_username = self.normalize_username(new_name)
        now = self._utc_now().isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "select id from profiles where username_normalized = ?", (normalized,)
            ).fetchone()
            if row is None:
                raise KeyError(f"No profile named {display_name}")
            try:
                connection.execute(
                    "update profiles set username_normalized = ?, display_name = ?, updated_at = ?"
                    " where id = ?",
                    (new_username, new_name, now, row["id"]),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Profile already exists") from error
        return {"id": row["id"], "display_name": new_name}

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

    def find_profile(self, username: str) -> Optional[Dict[str, Any]]:
        try:
            normalized = self.normalize_username(username)
        except ValueError:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "select id, display_name from profiles where username_normalized = ?",
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "display_name": row["display_name"]}

    def reset_pin(self, username: str, pin: str) -> str:
        normalized = self.normalize_username(username)
        self.validate_pin(pin)
        salt = secrets.token_bytes(16)
        now = self._utc_now().isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "select id, display_name from profiles where username_normalized = ?",
                (normalized,),
            ).fetchone()
            if row is None:
                raise KeyError("Profile not found")
            connection.execute(
                "update profiles set pin_salt = ?, pin_hash = ?, updated_at = ? where id = ?",
                (salt, self._pin_hash(pin, salt), now, row["id"]),
            )
            connection.execute(
                "delete from sessions where profile_id = ?", (row["id"],)
            )
        return str(row["display_name"])

    def list_profiles(self):
        with self._connect() as connection:
            rows = connection.execute(
                "select display_name, email, created_at, updated_at from profiles order by id"
            ).fetchall()
        return [
            {
                "display_name": row["display_name"],
                "email": row["email"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

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
            current = connection.execute(
                "select display_name from profiles where id = ?", (profile_id,)
            ).fetchone()
            saved = {
                "display_name": current["display_name"],
                "state": json.loads(serialized),
                "state_version": expected_version + 1,
            }
        return saved
