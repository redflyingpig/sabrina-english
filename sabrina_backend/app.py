"""HTTP service for the self-hosted Sabrina English application."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import mimetypes
import os
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
from urllib.parse import unquote, urlsplit

from .allowlist import read_names as read_allowlist
from .store import Store, VersionConflict


MAX_BODY_BYTES = 4 * 1024 * 1024
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "media-src 'self' blob:; "
    "connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)
# The wordbook is a scanned book: it lives in the data directory (never in git)
# and is only served to signed-in profiles.
WORDBOOK_PAGE_PATTERN = re.compile(r"^p\d{3}\.jpg$")
WORDBOOK_MAX_ENTRIES = 10000
WORDBOOK_KEY_MAX_LENGTH = 120
# The 廣東話 course (ERB workbook) is also copyrighted: course.json lives in the
# data directory and is served only to signed-in profiles. The app code is public.
CANTONESE_MODULES = (
    "app", "core", "data", "exercises", "host", "render", "speech", "store", "ui",
    "views/course", "views/dialogues", "views/home", "views/lesson", "views/more",
    "views/quiz", "views/review",
)
CANTONESE_SECTIONS = ("lessons", "cards", "days", "dialogues", "answers", "settings")
CANTONESE_MAX_KEYS = 5000
CANTONESE_KEY_MAX_LENGTH = 120
CANTONESE_MAX_BYTES = 1024 * 1024
STATIC_FILES = frozenset(
    {
        "index.html",
        "assets/content-library.js",
        "assets/wordbook.js",
        "assets/wordbook.css",
        "assets/cantonese-core.js",
        "assets/cantonese.css",
        "content/manifest.json",
    }
    | {f"assets/cantonese/{name}.js" for name in CANTONESE_MODULES}
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
        self.approved_content_files = self._load_approved_content_files()
        self.data_dir = data_dir.resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.data_dir, 0o700)
        except OSError:
            pass
        self.wordbook_dir = self.data_dir / "wordbook"
        self.cantonese_dir = self.data_dir / "cantonese"
        self.store = Store(self.data_dir / "sabrina.db")
        self.store.initialize()
        self.public_origin = os.environ.get(
            "SABRINA_PUBLIC_ORIGIN", "https://sabrina.redflyingpig.com"
        ).rstrip("/")
        self.logger = self._configure_logger()
        super().__init__(server_address, handler_class)

    def _load_approved_content_files(self) -> frozenset:
        manifest_path = self.root_dir / "content" / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            files = manifest["files"]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
            return frozenset()
        if not isinstance(files, dict):
            return frozenset()
        approved = {
            name
            for name in files
            if isinstance(name, str)
            and name.endswith(".json")
            and Path(name).name == name
            and not name.startswith(".")
        }
        return frozenset(approved)

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
        if self.close_connection:
            self.send_header("Connection", "close")
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
            self._error(413, "body_too_large", "Request body exceeds 4 MiB")
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
            self.close_connection = True
            self._error(401, "unauthorized", "A valid session is required")
            return None, None
        return token, profile

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/health":
            self._health()
        elif path == "/api/profile":
            self._get_profile()
        elif path == "/api/wordbook/data":
            self._wordbook_data()
        elif path.startswith("/api/wordbook/pages/"):
            self._wordbook_page(path[len("/api/wordbook/pages/") :])
        elif path == "/api/cantonese/course":
            self._cantonese_course()
        elif path.startswith("/api/"):
            self._error(404, "not_found", "API endpoint not found")
        else:
            self._serve_static(path)

    def do_POST(self) -> None:
        if not self._origin_allowed():
            self.close_connection = True
            self._error(403, "forbidden_origin", "Cross-origin request rejected")
            return
        path = urlsplit(self.path).path
        if path == "/api/auth/login":
            self._login()
        elif path == "/api/auth/logout":
            self._logout()
        else:
            self.close_connection = True
            self._error(404, "not_found", "API endpoint not found")

    def do_PUT(self) -> None:
        if not self._origin_allowed():
            self.close_connection = True
            self._error(403, "forbidden_origin", "Cross-origin request rejected")
            return
        if urlsplit(self.path).path == "/api/profile":
            self._put_profile()
        else:
            self.close_connection = True
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
        if not isinstance(username, str):
            self._error(400, "invalid_request", "Username is required")
            return
        # Existing names always sign in; a new name only becomes a profile when it is on the
        # invite list, so a typo cannot quietly create an empty profile.
        try:
            profile = self.server.store.login_or_create(username, read_allowlist())
        except PermissionError:
            self._error(403, "not_allowed", "This username is not on the invite list")
            return
        except ValueError as error:
            self._error(400, "invalid_username", str(error))
            return
        token = self.server.store.create_session(profile["id"])
        self._send_json(
            200,
            {
                "token": token,
                "profile": {
                    "id": profile["id"],
                    "display_name": profile["display_name"],
                    "expires_in_days": 90,
                },
                "created": profile["created"],
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
            or not self._valid_state(state)
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

    def _wordbook_data(self) -> None:
        _, profile = self._authenticated()
        if profile is None:
            return
        self._send_wordbook_file(self.server.wordbook_dir / "data.json", "application/json; charset=utf-8")

    def _wordbook_page(self, name: str) -> None:
        _, profile = self._authenticated()
        if profile is None:
            return
        if not WORDBOOK_PAGE_PATTERN.match(name):
            self._error(404, "not_found", "File not found")
            return
        self._send_wordbook_file(self.server.wordbook_dir / "pages" / name, "image/jpeg")

    def _cantonese_course(self) -> None:
        _, profile = self._authenticated()
        if profile is None:
            return
        self._send_wordbook_file(
            self.server.cantonese_dir / "course.json",
            "application/json; charset=utf-8",
            missing=("cantonese_unavailable", "Cantonese course is not installed"),
        )

    def _send_wordbook_file(
        self,
        path: Path,
        content_type: str,
        missing: Tuple[str, str] = ("wordbook_unavailable", "Wordbook content is not installed"),
    ) -> None:
        try:
            body = path.read_bytes()
        except OSError:
            self._error(404, *missing)
            return
        # Signed-in content: shared caches must not keep it, and the browser must
        # revalidate every time so a signed-out tab cannot read it from cache.
        # Auth runs before this, so a 304 is only ever sent to a valid session.
        etag = '"' + hashlib.sha256(body).hexdigest() + '"'
        cache_control = "private, no-cache"
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", cache_control)
            for name, value in self._security_headers().items():
                self.send_header(name, value)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", cache_control)
        for name, value in self._security_headers().items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _valid_state(state: Any) -> bool:
        if not isinstance(state, dict):
            return False
        history = state.get("history", [])
        favorites = state.get("favorites", [])
        if not isinstance(history, list) or not all(
            SabrinaHandler._valid_entry(item, "key") for item in history
        ):
            return False
        if not isinstance(favorites, list) or not all(
            SabrinaHandler._valid_entry(item, "favoriteKey") for item in favorites
        ):
            return False
        streak = state.get("streak")
        if streak is not None:
            if not isinstance(streak, dict):
                return False
            count = streak.get("count", 0)
            last_date = streak.get("lastLearnedDate", "")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                return False
            if not isinstance(last_date, str):
                return False
        if "wordbook" in state and not SabrinaHandler._valid_wordbook(state["wordbook"]):
            return False
        if "cantonese" in state and not SabrinaHandler._valid_cantonese(state["cantonese"]):
            return False
        if "version" in state and (not isinstance(state["version"], int) or isinstance(state["version"], bool)):
            return False
        if "updatedAt" in state and not isinstance(state["updatedAt"], str):
            return False
        return True

    @staticmethod
    def _valid_wordbook(wordbook: Any) -> bool:
        # {"entries": {"<day>:<word>": {"level": 0-3, "at": "<iso time>"}}}
        if not isinstance(wordbook, dict):
            return False
        entries = wordbook.get("entries", {})
        if not isinstance(entries, dict) or len(entries) > WORDBOOK_MAX_ENTRIES:
            return False
        for key, entry in entries.items():
            if not key or len(key) > WORDBOOK_KEY_MAX_LENGTH:
                return False
            if not isinstance(entry, dict):
                return False
            level = entry.get("level")
            if not isinstance(level, int) or isinstance(level, bool) or not 0 <= level <= 3:
                return False
            if not isinstance(entry.get("at", ""), str):
                return False
        return True

    @staticmethod
    def _valid_cantonese(cantonese: Any) -> bool:
        # {"lessons": {id: day}, "cards": {id: {due, ivl, ease, reps, lapses, at}},
        #  "days": {"YYYY-MM-DD": {...}}, "dialogues": {id: n}, "answers": {key: text},
        #  "settings": {...}}; shape is owned by assets/cantonese-core.js.
        if not isinstance(cantonese, dict):
            return False
        if any(key not in CANTONESE_SECTIONS for key in cantonese):
            return False
        for section in CANTONESE_SECTIONS:
            values = cantonese.get(section, {})
            if not isinstance(values, dict) or len(values) > CANTONESE_MAX_KEYS:
                return False
            if any(not key or len(key) > CANTONESE_KEY_MAX_LENGTH for key in values):
                return False
        for card in cantonese.get("cards", {}).values():
            if not isinstance(card, dict):
                return False
            for field in ("due", "ivl", "ease", "reps", "lapses"):
                value = card.get(field, 0)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    return False
        for count in cantonese.get("dialogues", {}).values():
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                return False
        if any(not isinstance(text, str) for text in cantonese.get("answers", {}).values()):
            return False
        encoded = json.dumps(cantonese, separators=(",", ":"), ensure_ascii=False)
        return len(encoded.encode("utf-8")) <= CANTONESE_MAX_BYTES

    @staticmethod
    def _valid_entry(item: Any, identity_key: str) -> bool:
        if not isinstance(item, dict) or not isinstance(item.get(identity_key), str):
            return False
        if not item[identity_key]:
            return False
        for key in ("favoriteKey", "date", "mode", "title", "detail", "phonetic", "speech"):
            if key in item and not isinstance(item[key], str):
                return False
        examples = item.get("examples", [])
        return isinstance(examples, list) and all(isinstance(value, str) for value in examples)

    def _serve_static(self, request_path: str) -> None:
        decoded = unquote(request_path)
        parts = [part for part in decoded.split("/") if part]
        if any(part in {".", ".."} or part.startswith(".") for part in parts):
            self._error(404, "not_found", "File not found")
            return
        relative = decoded.lstrip("/") or "index.html"
        approved = set(STATIC_FILES)
        approved.update(
            f"content/{name}" for name in self.server.approved_content_files
        )
        if relative not in approved:
            self._error(404, "not_found", "File not found")
            return
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
        body = candidate.read_bytes()
        etag = '"' + hashlib.sha256(body).hexdigest() + '"'
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            for name, value in self._security_headers().items():
                self.send_header(name, value)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "public, max-age=0, must-revalidate")
        for name, value in self._security_headers().items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


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
