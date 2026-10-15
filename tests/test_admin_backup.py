import io
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sabrina_backend.admin import init_profiles, list_profiles, reset_pin
from sabrina_backend.backup import backup_database
from sabrina_backend.store import Store


class AdminBackupTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tempdir.name) / "data"

    def tearDown(self):
        self.tempdir.cleanup()

    def store(self):
        store = Store(self.data_dir / "sabrina.db")
        store.initialize()
        return store

    def test_init_creates_exactly_three_profiles_and_prints_pins_once(self):
        output = io.StringIO()

        created = init_profiles(self.data_dir, output)

        self.assertEqual(["Owner", "Sabrina", "Max"], list(created))
        self.assertEqual(3, len(set(created.values())))
        for name, pin in created.items():
            self.assertRegex(pin, r"^[0-9]{8}$")
            self.assertIn(f"{name}: {pin}", output.getvalue())
        with sqlite3.connect(self.data_dir / "sabrina.db") as connection:
            names = [
                row[0]
                for row in connection.execute(
                    "select display_name from profiles order by id"
                )
            ]
        self.assertEqual(["Owner", "Sabrina", "Max"], names)

    def test_init_is_idempotent(self):
        first_output = io.StringIO()
        first = init_profiles(self.data_dir, first_output)
        second_output = io.StringIO()

        second = init_profiles(self.data_dir, second_output)

        self.assertEqual(3, len(first))
        self.assertEqual({}, second)
        self.assertNotRegex(second_output.getvalue(), r"[0-9]{8}")
        self.assertIn("already initialized", second_output.getvalue())

    def test_reset_pin_invalidates_existing_sessions(self):
        created = init_profiles(self.data_dir, io.StringIO())
        store = self.store()
        owner = store.authenticate("Owner", created["Owner"])
        token = store.create_session(owner["id"])
        self.assertIsNotNone(store.resolve_session(token))

        reset_pin(self.data_dir, "Owner", "new-pin-123")

        self.assertIsNone(store.resolve_session(token))
        self.assertIsNone(store.authenticate("Owner", created["Owner"]))
        self.assertIsNotNone(store.authenticate("Owner", "new-pin-123"))

    def test_list_never_prints_secrets_or_state(self):
        created = init_profiles(self.data_dir, io.StringIO())
        store = self.store()
        owner = store.authenticate("Owner", created["Owner"])
        store.write_state(owner["id"], 0, {"history": [{"secret": "study-data"}]})
        output = io.StringIO()

        list_profiles(self.data_dir, output)

        text = output.getvalue()
        self.assertIn("Owner", text)
        self.assertIn("Sabrina", text)
        self.assertIn("Max", text)
        self.assertNotIn("study-data", text)
        for pin in created.values():
            self.assertNotIn(pin, text)

    def test_backup_is_consistent_and_restorable(self):
        created = init_profiles(self.data_dir, io.StringIO())
        store = self.store()
        owner = store.authenticate("Owner", created["Owner"])
        state = {"history": [{"key": "A:hello"}], "favorites": [], "streak": {}}
        store.write_state(owner["id"], 0, state)

        backup_path = backup_database(
            self.data_dir, keep=30, now=datetime(2026, 10, 16, 9, 30, tzinfo=timezone.utc)
        )

        self.assertTrue(backup_path.exists())
        self.assertEqual("ok", self._integrity(backup_path))
        with sqlite3.connect(backup_path) as connection:
            saved_state = connection.execute(
                "select state_json from profiles where display_name = 'Owner'"
            ).fetchone()[0]
        self.assertIn("A:hello", saved_state)
        self.assertFalse(any(self.data_dir.glob("*.tmp")))

    def test_backup_retains_newest_thirty(self):
        init_profiles(self.data_dir, io.StringIO())
        start = datetime(2026, 9, 1, tzinfo=timezone.utc)

        for offset in range(31):
            backup_database(self.data_dir, keep=30, now=start + timedelta(days=offset))

        backups = sorted((self.data_dir / "backups").glob("sabrina-*.db"))
        self.assertEqual(30, len(backups))
        self.assertNotIn("20260901", backups[0].name)
        self.assertIn("20260902", backups[0].name)
        self.assertIn("20261001", backups[-1].name)

    @staticmethod
    def _integrity(path):
        with sqlite3.connect(path) as connection:
            return connection.execute("pragma integrity_check").fetchone()[0]


if __name__ == "__main__":
    unittest.main()
