import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from sabrina_backend.app import MAX_BODY_BYTES, create_server


class AppTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        base = Path(self.tempdir.name)
        self.root_dir = base / "site"
        self.data_dir = base / "data"
        self.root_dir.mkdir()
        (self.root_dir / "index.html").write_text(
            "<!doctype html><title>Sabrina English</title>", encoding="utf-8"
        )
        self.server = create_server("127.0.0.1", 0, self.root_dir, self.data_dir)
        self.server.store.create_profile("Owner", "123456")
        self.server.store.create_profile("Sabrina", "234567")
        self.server.store.create_profile("Max", "345678")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tempdir.cleanup()

    def request(self, method, path, payload=None, token=None, headers=None, raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        request_headers = dict(headers or {})
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        if raw is None and payload is not None:
            raw = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        connection.request(method, path, body=raw, headers=request_headers)
        response = connection.getresponse()
        body = response.read()
        result_headers = dict(response.getheaders())
        connection.close()
        if body and result_headers.get("Content-Type", "").startswith("application/json"):
            parsed = json.loads(body.decode("utf-8"))
        elif not body:
            parsed = None
        else:
            parsed = body.decode("utf-8")
        return response.status, result_headers, parsed

    def login(self, username="Owner", pin="123456"):
        status, _, body = self.request(
            "POST", "/api/auth/login", {"username": username, "pin": pin}
        )
        self.assertEqual(200, status)
        return body["token"]

    def test_serves_index_and_health(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(200, status)
        self.assertIn("Sabrina English", body)
        self.assertIn("Content-Security-Policy", headers)

        status, _, health = self.request("GET", "/api/health")
        self.assertEqual(200, status)
        self.assertEqual({"status": "ok", "database": "ok"}, health)

        (self.root_dir / ".git").mkdir()
        (self.root_dir / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        status, _, body = self.request("GET", "/.git/HEAD")
        self.assertEqual(404, status)
        self.assertEqual("not_found", body["error"])

    def test_health_reports_database_error(self):
        self.server.store.db_path.unlink()
        self.server.store.db_path.mkdir()

        status, _, health = self.request("GET", "/api/health")

        self.assertEqual(503, status)
        self.assertEqual({"status": "error", "database": "error"}, health)

    def test_login_profile_round_trip_and_logout(self):
        token = self.login()
        status, _, profile = self.request("GET", "/api/profile", token=token)
        self.assertEqual(200, status)
        self.assertEqual("Owner", profile["display_name"])
        self.assertEqual(0, profile["state_version"])

        state = {"version": 2, "history": [{"key": "A:hello"}], "favorites": [], "streak": {}}
        status, _, saved = self.request(
            "PUT",
            "/api/profile",
            {"state_version": 0, "state": state},
            token=token,
        )
        self.assertEqual(200, status)
        self.assertEqual(1, saved["state_version"])
        self.assertEqual(state, saved["state"])

        status, _, _ = self.request("POST", "/api/auth/logout", {}, token=token)
        self.assertEqual(204, status)
        status, _, body = self.request("GET", "/api/profile", token=token)
        self.assertEqual(401, status)
        self.assertEqual("unauthorized", body["error"])

    def test_logout_consumes_body_before_next_keepalive_request(self):
        token = self.login()
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request(
            "POST",
            "/api/auth/logout",
            body=b"{}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        response = connection.getresponse()
        response.read()
        self.assertEqual(204, response.status)

        connection.request(
            "POST",
            "/api/auth/login",
            body=json.dumps({"username": "Sabrina", "pin": "234567"}),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        body = json.loads(response.read().decode("utf-8"))
        connection.close()

        self.assertEqual(200, response.status)
        self.assertEqual("Sabrina", body["profile"]["display_name"])

    def test_rejected_put_closes_connection_without_poisoning_next_request(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request(
            "PUT",
            "/api/profile",
            body=b"{}",
            headers={"Content-Type": "application/json", "Authorization": "Bearer bad"},
        )
        response = connection.getresponse()
        response.read()
        self.assertEqual(401, response.status)
        self.assertEqual("close", response.getheader("Connection"))
        connection.close()

    def test_rejects_invalid_profile_state(self):
        token = self.login()
        status, _, body = self.request(
            "PUT",
            "/api/profile",
            {"state_version": 0, "state": {"history": {}, "favorites": 42}},
            token=token,
        )
        self.assertEqual(400, status)
        self.assertEqual("invalid_profile_state", body["error"])

    def test_cloudflare_client_ip_gets_its_own_rate_limit_bucket(self):
        for _ in range(5):
            self.request(
                "POST",
                "/api/auth/login",
                {"username": "Owner", "pin": "wrong"},
                headers={"CF-Connecting-IP": "203.0.113.10"},
            )
        status, _, _ = self.request(
            "POST",
            "/api/auth/login",
            {"username": "Owner", "pin": "123456"},
            headers={"CF-Connecting-IP": "203.0.113.11"},
        )
        self.assertEqual(200, status)

    def test_token_cannot_select_another_profile(self):
        owner_token = self.login()
        sabrina_token = self.login("Sabrina", "234567")
        self.request(
            "PUT",
            "/api/profile",
            {"state_version": 0, "state": {"history": [{"key": "Sabrina"}]}},
            token=sabrina_token,
        )

        status, _, profile = self.request(
            "GET", "/api/profile?profile_id=2", token=owner_token
        )
        self.assertEqual(200, status)
        self.assertEqual("Owner", profile["display_name"])
        self.assertEqual([], profile["state"]["history"])

    def test_stale_write_returns_409_with_current_state(self):
        token = self.login()
        first = {"history": [{"key": "first"}]}
        self.request(
            "PUT", "/api/profile", {"state_version": 0, "state": first}, token=token
        )

        status, _, conflict = self.request(
            "PUT",
            "/api/profile",
            {"state_version": 0, "state": {"history": [{"key": "stale"}]}},
            token=token,
        )
        self.assertEqual(409, status)
        self.assertEqual("version_conflict", conflict["error"])
        self.assertEqual(first, conflict["current"]["state"])
        self.assertEqual(1, conflict["current"]["state_version"])

    def test_rejects_bad_and_oversized_json(self):
        status, _, body = self.request(
            "POST",
            "/api/auth/login",
            headers={"Content-Type": "application/json"},
            raw=b"not-json",
        )
        self.assertEqual(400, status)
        self.assertEqual("invalid_json", body["error"])

        status, _, body = self.request(
            "POST",
            "/api/auth/login",
            headers={"Content-Type": "application/json"},
            raw=b"x" * (MAX_BODY_BYTES + 1),
        )
        self.assertEqual(413, status)
        self.assertEqual("body_too_large", body["error"])

    def test_rejects_hostile_origin(self):
        status, _, body = self.request(
            "POST",
            "/api/auth/login",
            {"username": "Owner", "pin": "123456"},
            headers={"Origin": "https://evil.example"},
        )
        self.assertEqual(403, status)
        self.assertEqual("forbidden_origin", body["error"])

    def test_failed_logins_are_rate_limited_per_ip_and_username(self):
        for _ in range(5):
            status, _, body = self.request(
                "POST", "/api/auth/login", {"username": "Owner", "pin": "wrong-pin"}
            )
            self.assertEqual(401, status)
            self.assertEqual("invalid_credentials", body["error"])

        status, _, body = self.request(
            "POST", "/api/auth/login", {"username": "Owner", "pin": "wrong-pin"}
        )
        self.assertEqual(429, status)
        self.assertEqual("rate_limited", body["error"])

        status, _, _ = self.request(
            "POST", "/api/auth/login", {"username": "Sabrina", "pin": "234567"}
        )
        self.assertEqual(200, status)

    def test_api_security_headers_disable_caching(self):
        status, headers, _ = self.request("GET", "/api/health")
        self.assertEqual(200, status)
        self.assertEqual("no-store", headers["Cache-Control"])
        self.assertEqual("nosniff", headers["X-Content-Type-Options"])
        self.assertEqual("no-referrer", headers["Referrer-Policy"])
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])

    def test_application_logs_rotate(self):
        for _ in range(80):
            self.server.logger.info("x" * 4096)
        for handler in self.server.logger.handlers:
            handler.flush()

        self.assertTrue((self.data_dir / "sabrina.log").exists())
        self.assertTrue((self.data_dir / "sabrina.log.1").exists())


if __name__ == "__main__":
    unittest.main()
