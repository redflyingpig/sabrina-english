import os
import plistlib
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"


class DeployContractTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.data_dir = self.base / "data"
        self.agents_dir = self.base / "LaunchAgents"
        self.environment = {
            **os.environ,
            "SABRINA_PROJECT_DIR": str(ROOT),
            "SABRINA_DATA_DIR": str(self.data_dir),
            "SABRINA_LAUNCH_AGENTS_DIR": str(self.agents_dir),
            "SABRINA_SKIP_LAUNCHCTL": "1",
        }

    def tearDown(self):
        self.tempdir.cleanup()

    def install(self):
        return subprocess.run(
            [str(DEPLOY / "install.sh")],
            cwd=ROOT,
            env=self.environment,
            text=True,
            capture_output=True,
            check=True,
        )

    def plist(self, name):
        with (self.agents_dir / name).open("rb") as handle:
            return plistlib.load(handle)

    def test_service_binds_loopback_on_18880(self):
        self.install()
        service = self.plist("ai.sabrina-english.site.plist")

        arguments = service["ProgramArguments"]
        self.assertEqual("/usr/bin/python3", arguments[0])
        self.assertIn("sabrina_backend.app", arguments)
        self.assertEqual("127.0.0.1", arguments[arguments.index("--host") + 1])
        self.assertEqual("18880", arguments[arguments.index("--port") + 1])

    def test_launchagents_use_absolute_paths_and_keepalive(self):
        self.install()
        service = self.plist("ai.sabrina-english.site.plist")
        backup = self.plist("ai.sabrina-english.backup.plist")

        self.assertTrue(service["KeepAlive"])
        self.assertTrue(service["RunAtLoad"])
        self.assertEqual(str(ROOT), service["WorkingDirectory"])
        for plist in (service, backup):
            for argument in plist["ProgramArguments"]:
                if "/" in argument:
                    self.assertTrue(Path(argument).is_absolute(), argument)

    def test_backup_runs_daily_and_keeps_thirty(self):
        self.install()
        backup = self.plist("ai.sabrina-english.backup.plist")

        self.assertEqual({"Hour": 3, "Minute": 15}, backup["StartCalendarInterval"])
        arguments = backup["ProgramArguments"]
        self.assertIn("sabrina_backend.backup", arguments)
        self.assertEqual("30", arguments[arguments.index("--keep") + 1])

    def test_install_is_idempotent_and_preserves_database(self):
        self.install()
        database = self.data_dir / "sabrina.db"
        with sqlite3.connect(database) as connection:
            connection.execute("create table install_sentinel(value text)")
            connection.execute("insert into install_sentinel values ('keep-me')")

        self.install()

        with sqlite3.connect(database) as connection:
            value = connection.execute("select value from install_sentinel").fetchone()[0]
        self.assertEqual("keep-me", value)
        self.assertEqual(0o700, self.data_dir.stat().st_mode & 0o777)

    def test_uninstall_does_not_delete_data(self):
        self.install()
        database = self.data_dir / "sabrina.db"

        subprocess.run(
            [str(DEPLOY / "uninstall.sh")],
            cwd=ROOT,
            env=self.environment,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertTrue(database.exists())
        self.assertFalse((self.agents_dir / "ai.sabrina-english.site.plist").exists())
        self.assertFalse((self.agents_dir / "ai.sabrina-english.backup.plist").exists())

    def test_operations_cover_health_backup_restore_and_tunnel(self):
        operations = (ROOT / "OPERATIONS.md").read_text(encoding="utf-8")
        for heading in (
            "安装与升级",
            "廣東話课程内容",
            "账号与档案（Cloudflare Access + 邮箱验证码）",
            "健康检查",
            "日志",
            "备份",
            "恢复",
            "Cloudflare Tunnel",
            "回滚",
            "卸载",
        ):
            self.assertIn(heading, operations)


if __name__ == "__main__":
    unittest.main()
