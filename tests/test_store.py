import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sabrina_backend.store import Store, VersionConflict


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "sabrina.db"
        self.store = Store(self.db_path)
        self.store.initialize()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_initializes_secure_schema(self):
        with sqlite3.connect(self.db_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "select name from sqlite_master where type = 'table'"
                )
            }
            journal_mode = connection.execute("pragma journal_mode").fetchone()[0]
            session_foreign_keys = connection.execute(
                "pragma foreign_key_list(sessions)"
            ).fetchall()
            schema_version = connection.execute(
                "select version from schema_version"
            ).fetchone()[0]

        self.assertTrue({"profiles", "sessions", "schema_version"} <= tables)
        self.assertEqual("wal", journal_mode)
        self.assertTrue(session_foreign_keys)
        self.assertEqual(3, schema_version)

    def test_profile_names_are_case_and_space_insensitive(self):
        profile_id = self.store.create_profile("  Sabrina   Lee  ", "123456")

        authenticated = self.store.authenticate("sABRINA lee", "123456")

        self.assertEqual(profile_id, authenticated["id"])
        self.assertEqual("Sabrina Lee", authenticated["display_name"])
        with self.assertRaises(ValueError):
            self.store.create_profile("SABRINA LEE", "abcdef")

    def test_pin_is_hashed_and_wrong_pin_fails(self):
        self.store.create_profile("Owner", "correct horse")

        with sqlite3.connect(self.db_path) as connection:
            salt, pin_hash = connection.execute(
                "select pin_salt, pin_hash from profiles where username_normalized = ?",
                ("owner",),
            ).fetchone()

        self.assertNotIn(b"correct horse", salt)
        self.assertNotIn(b"correct horse", pin_hash)
        self.assertIsNone(self.store.authenticate("Owner", "wrong pin"))
        self.assertIsNotNone(self.store.authenticate("Owner", "correct horse"))

    def test_profile_can_be_resolved_by_username_without_pin(self):
        profile_id = self.store.create_profile("Sabrina", "123456")

        profile = self.store.find_profile("  sABRINA ")

        self.assertEqual(profile_id, profile["id"])
        self.assertEqual("Sabrina", profile["display_name"])
        self.assertIsNone(self.store.find_profile("Unknown"))

    def test_session_is_hashed_scoped_and_expires(self):
        owner_id = self.store.create_profile("Owner", "123456")
        token = self.store.create_session(owner_id)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        with sqlite3.connect(self.db_path) as connection:
            stored_hash, expires_at = connection.execute(
                "select token_hash, expires_at from sessions"
            ).fetchone()

        self.assertEqual(token_hash, stored_hash)
        self.assertNotEqual(token, stored_hash)
        resolved = self.store.resolve_session(token)
        self.assertEqual(owner_id, resolved["id"])
        expires = datetime.fromisoformat(expires_at)
        lifetime_days = (expires - datetime.now(timezone.utc)).total_seconds() / 86400
        self.assertGreater(lifetime_days, 89.9)
        self.assertLessEqual(lifetime_days, 90.0)

        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "update sessions set expires_at = ? where token_hash = ?",
                ("2000-01-01T00:00:00+00:00", token_hash),
            )
        self.assertIsNone(self.store.resolve_session(token))

    def test_state_version_conflict_returns_current_state(self):
        profile_id = self.store.create_profile("Sabrina", "123456")
        initial = self.store.read_state(profile_id)
        first_state = {
            "version": 2,
            "history": [{"key": "A:hello"}],
            "favorites": [],
            "streak": {"count": 1, "lastLearnedDate": "2026-10-16"},
        }

        written = self.store.write_state(profile_id, initial["state_version"], first_state)

        self.assertEqual(1, written["state_version"])
        self.assertEqual(first_state, written["state"])
        with self.assertRaises(VersionConflict) as conflict:
            self.store.write_state(profile_id, 0, {"history": []})
        self.assertEqual(written, conflict.exception.current)

    def test_three_profiles_are_isolated(self):
        profile_ids = {
            name: self.store.create_profile(name, "123456")
            for name in ("Owner", "Sabrina", "Max")
        }

        for index, (name, profile_id) in enumerate(profile_ids.items(), start=1):
            self.store.write_state(
                profile_id,
                0,
                {"history": [{"key": name}], "favorites": [], "streak": {"count": index}},
            )

        states = {
            name: self.store.read_state(profile_id)["state"]
            for name, profile_id in profile_ids.items()
        }
        self.assertEqual(["Owner"], [item["key"] for item in states["Owner"]["history"]])
        self.assertEqual(["Sabrina"], [item["key"] for item in states["Sabrina"]["history"]])
        self.assertEqual(["Max"], [item["key"] for item in states["Max"]["history"]])


if __name__ == "__main__":
    unittest.main()


class SchemaMigrationTest(unittest.TestCase):
    """A v1 database (no email column) must upgrade in place when the service starts."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "sabrina.db"
        with sqlite3.connect(self.db_path) as connection:
            connection.executescript(
                """
                create table schema_version (version integer not null);
                insert into schema_version(version) values (1);
                create table profiles (
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
                create table sessions (
                    token_hash text primary key,
                    profile_id integer not null references profiles(id) on delete cascade,
                    created_at text not null,
                    expires_at text not null
                );
                """
            )
            connection.execute(
                "insert into profiles (username_normalized, display_name, pin_salt, pin_hash,"
                " state_json, state_version, created_at, updated_at)"
                " values ('owner', 'Owner', x'00', x'00', '{}', 0, 'now', 'now')"
            )
        self.store = Store(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_upgrades_v1_and_keeps_existing_profiles(self):
        self.store.initialize()
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            version = connection.execute("select version from schema_version").fetchone()[0]
            columns = {
                row["name"] for row in connection.execute("pragma table_info(profiles)").fetchall()
            }
            owner = connection.execute(
                "select display_name, email from profiles where username_normalized = 'owner'"
            ).fetchone()
        self.assertEqual(3, version)
        self.assertIn("email", columns)
        self.assertEqual("Owner", owner["display_name"])
        self.assertIsNone(owner["email"])

        # v3 adds the invite allowlist; an upgraded database gets an empty one.
        self.assertEqual([], self.store.allowlist_list())
        self.store.allowlist_add("New Kid")
        self.assertEqual(["new kid"], self.store.allowlist_list())
