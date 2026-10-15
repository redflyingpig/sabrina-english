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
        self.assertEqual(1, schema_version)

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
