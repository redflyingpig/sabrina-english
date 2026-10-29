import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sabrina_backend.admin import bind_email, init_profiles, list_profiles, rename_profile, reset_pin
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

    def test_init_creates_exactly_three_profiles_without_printing_compatibility_pins(self):
        output = io.StringIO()

        created = init_profiles(self.data_dir, output)

        self.assertEqual(["Owner", "Sabrina", "Max"], list(created))
        self.assertEqual(3, len(set(created.values())))
        for name, pin in created.items():
            self.assertRegex(pin, r"^[0-9]{8}$")
            self.assertNotIn(pin, output.getvalue())
        self.assertIn("username-only login", output.getvalue())
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

    @staticmethod
    def _state(marker):
        return {
            "version": 2,
            "updatedAt": "2026-10-16T09:30:00+00:00",
            "history": [
                {
                    "key": f"lesson:{marker}",
                    "favoriteKey": f"A:{marker}",
                    "date": "2026-10-16",
                    "mode": "Vocabulary",
                    "title": marker,
                    "detail": marker,
                    "examples": [],
                }
            ],
            "favorites": [],
            "streak": {"count": 1, "lastLearnedDate": "2026-10-16"},
        }

    def _owner_id(self):
        created = init_profiles(self.data_dir, io.StringIO())
        store = self.store()
        return store.authenticate("Owner", created["Owner"])["id"]

    def test_backup_leaves_no_temporary_or_sidecar_files(self):
        owner_id = self._owner_id()
        self.store().write_state(owner_id, 0, self._state("first"))

        backup_database(
            self.data_dir, keep=30, now=datetime(2026, 10, 16, 9, 30, tzinfo=timezone.utc)
        )

        backups = self.data_dir / "backups"
        self.assertEqual(
            ["sabrina-20261016T093000Z.db"],
            sorted(path.name for path in backups.iterdir()),
        )

    def test_backup_is_self_contained_for_read_only_readers(self):
        owner_id = self._owner_id()
        self.store().write_state(owner_id, 0, self._state("first"))

        backup_path = backup_database(
            self.data_dir, keep=30, now=datetime(2026, 10, 16, 9, 30, tzinfo=timezone.utc)
        )

        # A finished backup must be readable without a writable directory or WAL sidecars,
        # which is what the documented restore drill does first.
        with sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True) as connection:
            self.assertEqual("ok", connection.execute("pragma integrity_check").fetchone()[0])
        self.assertEqual(
            [backup_path.name],
            sorted(path.name for path in (self.data_dir / "backups").iterdir()),
        )

    def test_documented_restore_stages_before_replacing_live_database(self):
        if shutil.which("sqlite3") is None:
            self.skipTest("sqlite3 command line tool is not available")
        repo_root = Path(__file__).resolve().parents[1]
        runbook = (repo_root / "OPERATIONS.md").read_text(encoding="utf-8")
        section = runbook.split("## 恢复", 1)[1].split("## Cloudflare Tunnel", 1)[0]
        script = section.split("```sh", 1)[1].split("```", 1)[0]

        owner_id = self._owner_id()
        store = self.store()
        store.write_state(owner_id, 0, self._state("backup-snapshot"))
        backup_path = backup_database(
            self.data_dir, keep=30, now=datetime(2026, 10, 16, 9, 30, tzinfo=timezone.utc)
        )

        # The live database keeps changing after the backup and still has a WAL to replay:
        # a naive overwrite of sabrina.db would silently restore stale data.
        live = sqlite3.connect(self.data_dir / "sabrina.db")
        self.addCleanup(live.close)
        live.execute("pragma journal_mode = wal")
        live.execute(
            "update profiles set state_json = ?, state_version = state_version + 1 where id = ?",
            (json.dumps(self._state("live-after-backup")), owner_id),
        )
        live.commit()
        self.assertTrue((self.data_dir / "sabrina.db-wal").exists())

        stub_dir = Path(self.tempdir.name) / "stub-bin"
        stub_dir.mkdir()
        launchctl = stub_dir / "launchctl"
        launchctl.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        launchctl.chmod(0o755)
        # The runbook ends by reinstalling the LaunchAgents; run the documented script inside a
        # throwaway project directory so the test never touches the real launchd installation.
        fake_repo = Path(self.tempdir.name) / "repo"
        (fake_repo / "deploy").mkdir(parents=True)
        install_marker = fake_repo / "install-called"
        install = fake_repo / "deploy" / "install.sh"
        install.write_text(f'#!/bin/sh\ntouch "{install_marker}"\nexit 0\n', encoding="utf-8")
        install.chmod(0o755)
        commands = script.replace(
            "$HOME/Library/Application Support/SabrinaEnglish", str(self.data_dir)
        )
        commands = commands.replace("/path/to/backup.db", str(backup_path))
        commands = commands.replace("/usr/bin/python3", sys.executable)
        environment = dict(
            os.environ, PATH=f"{stub_dir}:{os.environ['PATH']}", PYTHONPATH=str(repo_root)
        )

        completed = subprocess.run(
            ["/bin/sh", "-e", "-c", commands],
            cwd=fake_repo,
            env=environment,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertTrue(install_marker.exists(), "runbook must reinstall the service")
        restored = sqlite3.connect(self.data_dir / "sabrina.db")
        self.addCleanup(restored.close)
        self.assertEqual(
            "ok", restored.execute("pragma integrity_check").fetchone()[0]
        )
        restored_state = json.loads(
            restored.execute(
                "select state_json from profiles where id = ?", (owner_id,)
            ).fetchone()[0]
        )
        self.assertEqual("backup-snapshot", restored_state["history"][0]["title"])
        self.assertFalse((self.data_dir / "restore-staging.db").exists())
        self.assertTrue((self.data_dir / "pre-restore" / "sabrina.db").exists())

        # The runbook snapshots the live database before swapping, so the newer state is recoverable.
        safety_candidates = sorted(
            path
            for path in (self.data_dir / "backups").glob("sabrina-*.db")
            if path != backup_path
        )
        self.assertEqual(1, len(safety_candidates), "runbook must take one safety backup")
        with sqlite3.connect(safety_candidates[0]) as connection:
            safety_state = json.loads(
                connection.execute(
                    "select state_json from profiles where id = ?", (owner_id,)
                ).fetchone()[0]
            )
        self.assertEqual("live-after-backup", safety_state["history"][0]["title"])


    def test_bind_email_and_rename_are_reusable_operations(self):
        store = self.store()
        store.create_profile("Owner", "123456")
        store.create_profile("Sabrina", "234567")

        output = io.StringIO()
        bind_email(self.data_dir, "Owner", "Alex.Yacao.Wang@Gmail.com", output)
        rename_profile(self.data_dir, "Owner", "Alex", output)

        profiles = self.store().list_profiles()
        self.assertEqual(
            [("Alex", "alex.yacao.wang@gmail.com"), ("Sabrina", None)],
            [(p["display_name"], p["email"]) for p in profiles],
        )
        self.assertIn("Alex", output.getvalue())

    def test_rename_rejects_a_taken_name(self):
        store = self.store()
        store.create_profile("Owner", "123456")
        store.create_profile("Sabrina", "234567")
        with self.assertRaises(ValueError):
            store.rename_profile("Owner", "sabrina")

if __name__ == "__main__":
    unittest.main()
