"""HTTP service for the self-hosted Sabrina English application."""

from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
from urllib.parse import unquote, urlsplit

from .store import Store, VersionConflict


MAX_BODY_BYTES = 1024 * 1024
LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 10 * 60
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)


class SabrinaHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: Tuple[str, int],
        handler_class,
        root_dir: Path,
        data_dir: Path,
    ):
        self.root_dir = root_dir.resolve()
        self.data_dir = data_dir.resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.data_dir, 0o700)
        except OSError:
            pass
        self.store = Store(self.data_dir / "sabrina.db")
        self.store.initialize()
        self.login_failures: Dict[Tuple[str, str], list] = {}
        self.public_origin = os.environ.get(
            "SABRINA_PUBLIC_ORIGIN", "https://sabrina.redflyingpig.com"
        ).rstrip("/")
        self.logger = self._configure_logger()
        super().__init__(server_address, handler_class)

    def _configure_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"sabrina.{id(self)}")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = RotatingFileHandler(
            self.data_dir / "sabrina.log",
            maxBytes=256 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
        return logger

    def server_close(self) -> None:
        try:
            super().server_close()
        finally:
            for handler in list(self.logger.handlers):
                handler.close()
                self.logger.removeHandler(handler)


class SabrinaHandler(BaseHTTPRequestHandler):
    server: SabrinaHTTPServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format_string: str, *args) -> None:
        self.server.logger.info(
            "%s %s", self.client_address[0], format_string % args
        )

    def _security_headers(self, dynamic: bool = False) -> Dict[str, str]:
        headers = {
            "Content-Security-Policy": CONTENT_SECURITY_POLICY,
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
        }
        if dynamic:
            headers["Cache-Control"] = "no-store"
        return headers

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        content_type: str,
        dynamic: bool = False,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in self._security_headers(dynamic).items():
            self.send_header(name, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _send_json(self, status: int, payload: Optional[Dict[str, Any]]) -> None:
        if payload is None:
            body = b""
        else:
            body = json.dumps(
                payload, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8", dynamic=True)

    def _error(self, status: int, code: str, message: str) -> None:
        self._send_json(status, {"error": code, "message": message})

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        if origin.rstrip("/") == self.server.public_origin:
            return True
        origin_parts = urlsplit(origin)
        return origin_parts.scheme in {"http", "https"} and origin_parts.netloc == self.headers.get(
            "Host"
        )

    def _read_json(self) -> Optional[Dict[str, Any]]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._error(400, "invalid_content_length", "Invalid Content-Length")
            return None
        if length > MAX_BODY_BYTES:
            remaining = min(length, MAX_BODY_BYTES + 1)
            while remaining:
                chunk = self.rfile.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
            self.close_connection = True
            self._error(413, "body_too_large", "Request body exceeds 1 MiB")
            return None
        if length <= 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._error(400, "invalid_json", "Request body must be valid JSON")
            return None
        if not isinstance(payload, dict):
            self._error(400, "invalid_json", "Request JSON must be an object")
            return None
        return payload

    def _bearer_token(self) -> Optional[str]:
        authorization = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not authorization.startswith(prefix):
            return None
        token = authorization[len(prefix) :].strip()
        return token or None

    def _authenticated(self) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        token = self._bearer_token()
        profile = self.server.store.resolve_session(token) if token else None
        if profile is None:
            self._error(401, "unauthorized", "A valid session is required")
            return None, None
        return token, profile

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/health":
            self._health()
        elif path == "/api/profile":
            self._get_profile()
        elif path.startswith("/api/"):
            self._error(404, "not_found", "API endpoint not found")
        else:
            self._serve_static(path)

    def do_POST(self) -> None:
        if not self._origin_allowed():
            self._error(403, "forbidden_origin", "Cross-origin request rejected")
            return
        path = urlsplit(self.path).path
        if path == "/api/auth/login":
            self._login()
        elif path == "/api/auth/logout":
            self._logout()
        else:
            self._error(404, "not_found", "API endpoint not found")

    def do_PUT(self) -> None:
        if not self._origin_allowed():
            self._error(403, "forbidden_origin", "Cross-origin request rejected")
            return
        if urlsplit(self.path).path == "/api/profile":
            self._put_profile()
        else:
            self._error(404, "not_found", "API endpoint not found")

    def _health(self) -> None:
        try:
            with self.server.store._connect() as connection:
                connection.execute("select 1").fetchone()
        except sqlite3.Error:
            self._send_json(503, {"status": "error", "database": "error"})
            return
        self._send_json(200, {"status": "ok", "database": "ok"})

    def _login(self) -> None:
        payload = self._read_json()
        if payload is None:
            return
        username = payload.get("username")
        pin = payload.get("pin")
        if not isinstance(username, str) or not isinstance(pin, str):
            self._error(400, "invalid_request", "Username and PIN are required")
            return
        try:
            normalized = self.server.store.normalize_username(username)
        except ValueError:
            normalized = ""
        key = (self.client_address[0], normalized)
        now = time.monotonic()
        failures = [
            timestamp
            for timestamp in self.server.login_failures.get(key, [])
            if now - timestamp < LOGIN_FAILURE_WINDOW_SECONDS
        ]
        if len(failures) >= LOGIN_FAILURE_LIMIT:
            self.server.login_failures[key] = failures
            self._error(429, "rate_limited", "Too many failed login attempts")
            return
        profile = self.server.store.authenticate(username, pin)
        if profile is None:
            failures.append(now)
            self.server.login_failures[key] = failures
            self._error(401, "invalid_credentials", "Username or PIN is incorrect")
            return
        self.server.login_failures.pop(key, None)
        token = self.server.store.create_session(profile["id"])
        self._send_json(
            200,
            {
                "token": token,
                "profile": {
                    "display_name": profile["display_name"],
                    "expires_in_days": 90,
                },
            },
        )

    def _logout(self) -> None:
        payload = self._read_json()
        if payload is None:
            return
        token, profile = self._authenticated()
        if profile is None:
            return
        self.server.store.delete_session(token)
        self._send_json(204, None)

    def _get_profile(self) -> None:
        _, profile = self._authenticated()
        if profile is None:
            return
        self._send_json(200, self.server.store.read_state(profile["id"]))

    def _put_profile(self) -> None:
        _, profile = self._authenticated()
        if profile is None:
            return
        payload = self._read_json()
        if payload is None:
            return
        state_version = payload.get("state_version")
        state = payload.get("state")
        if (
            not isinstance(state_version, int)
            or isinstance(state_version, bool)
            or state_version < 0
            or not isinstance(state, dict)
        ):
            self._error(
                400,
                "invalid_profile_state",
                "state_version and object state are required",
            )
            return
        try:
            saved = self.server.store.write_state(profile["id"], state_version, state)
        except VersionConflict as conflict:
            self._send_json(
                409,
                {
                    "error": "version_conflict",
                    "message": "Profile state has changed",
                    "current": conflict.current,
                },
            )
            return
        self._send_json(200, saved)

    def _serve_static(self, request_path: str) -> None:
        decoded = unquote(request_path)
        relative = decoded.lstrip("/") or "index.html"
        candidate = (self.server.root_dir / relative).resolve()
        try:
            candidate.relative_to(self.server.root_dir)
        except ValueError:
            self._error(404, "not_found", "File not found")
            return
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.is_file():
            self._error(404, "not_found", "File not found")
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {
            "application/javascript",
            "application/json",
        }:
            content_type += "; charset=utf-8"
        self._send_bytes(200, candidate.read_bytes(), content_type)


def create_server(
    host: str,
    port: int,
    root_dir: Union[Path, str],
    data_dir: Union[Path, str],
) -> SabrinaHTTPServer:
    return SabrinaHTTPServer(
        (host, port), SabrinaHandler, Path(root_dir), Path(data_dir)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Sabrina English")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18880)
    parser.add_argument("--root-dir", type=Path, default=Path.cwd())
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / "Library/Application Support/SabrinaEnglish",
    )
    args = parser.parse_args()
    server = create_server(args.host, args.port, args.root_dir, args.data_dir)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
