"""Private loopback transport for the HTML command deck.

The dashboard is a presentation client only.  Elite journal reduction,
profile ownership and every mutating command remain in the Python process.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import parse_qs, urlparse


MAX_COMMAND_BYTES = 64 * 1024


class _DashboardHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class HtmlDashboardServer:
    """Serve bundled dashboard assets and one revisioned application state."""

    def __init__(self, static_root, *, command_callback=None, host_state=None):
        self.static_root = Path(static_root).resolve()
        self.command_callback = command_callback
        self.token = secrets.token_urlsafe(32)
        self._condition = threading.Condition()
        self._snapshot_json = "{}"
        self._revision = 0
        self._last_client_seen = 0.0
        self._stopping = threading.Event()
        self._closing = False
        self._host_state = dict(host_state or {})
        self._host_revision = 0
        # The atlas receives a random loopback port after the journal backend
        # is constructed. The parent still supplies the exact private URL and
        # the atlas independently restricts its frame ancestor to this deck.
        self._frame_sources = {"http://127.0.0.1:*"}
        self._server = _DashboardHTTPServer(("127.0.0.1", 0), self._handler_type())
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="html-dashboard-http",
            daemon=True,
        )
        self._thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/?token={self.token}"

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.port}"

    def allow_frame_source(self, origin):
        """Allow one exact loopback child application inside the command deck."""
        parsed = urlparse(str(origin or ""))
        try:
            port = parsed.port
        except ValueError:
            return False
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not port:
            return False
        normalised = f"http://127.0.0.1:{port}"
        with self._condition:
            self._frame_sources.add(normalised)
        return True

    @property
    def last_client_seen(self):
        return self._last_client_seen

    def set_command_callback(self, callback):
        self.command_callback = callback

    def publish(self, snapshot):
        encoded = json.dumps(
            snapshot or {}, ensure_ascii=False, separators=(",", ":"),
        )
        with self._condition:
            if encoded == self._snapshot_json:
                return self._revision
            self._snapshot_json = encoded
            self._revision += 1
            self._condition.notify_all()
            return self._revision

    def request_shutdown(self):
        with self._condition:
            self._closing = True
            self._condition.notify_all()

    def update_host_state(self, values):
        values = values if isinstance(values, dict) else {}
        with self._condition:
            changed = False
            for key, value in values.items():
                if self._host_state.get(key) != value:
                    self._host_state[key] = value
                    changed = True
            if changed:
                self._host_revision += 1
                self._condition.notify_all()
            return self._host_revision

    def stop(self):
        if self._stopping.is_set():
            return
        self._stopping.set()
        self.request_shutdown()
        try:
            self._server.shutdown()
        except Exception:
            pass
        try:
            self._server.server_close()
        except Exception:
            pass

    def _handler_type(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "VoidCompassDashboard/1"

            def log_message(self, _format, *_args):
                return

            def do_GET(self):
                owner._handle_get(self)

            def do_POST(self):
                owner._handle_post(self)

        return Handler

    def _authorised(self, handler, parsed):
        supplied = (
            (parse_qs(parsed.query).get("token") or [""])[0]
            or handler.headers.get("X-VoidCompass-Token", "")
        )
        return secrets.compare_digest(str(supplied), self.token)

    def _security_headers(self, handler):
        with self._condition:
            frame_sources = sorted(self._frame_sources)
        frame_policy = " ".join(frame_sources) if frame_sources else "'none'"
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Referrer-Policy", "no-referrer")
        handler.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
            f"object-src 'none'; frame-src {frame_policy}; "
            "frame-ancestors 'none'; base-uri 'none'",
        )

    def _send_bytes(self, handler, payload, content_type, status=200,
                    cache="no-store"):
        handler.send_response(status)
        self._security_headers(handler)
        handler.send_header("Cache-Control", cache)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(payload)))
        handler.send_header("Connection", "close")
        handler.end_headers()
        try:
            handler.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _send_json(self, handler, payload, status=200):
        encoded = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")
        self._send_bytes(
            handler, encoded, "application/json; charset=utf-8", status,
        )

    def _static_path(self, request_path):
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        if not relative or relative.startswith("."):
            return None
        candidate = (self.static_root / relative).resolve()
        try:
            candidate.relative_to(self.static_root)
        except ValueError:
            return None
        return candidate

    def _handle_get(self, handler):
        parsed = urlparse(handler.path)
        path = parsed.path
        if path in {"/api/snapshot", "/api/events", "/api/health", "/api/host"}:
            if not self._authorised(handler, parsed):
                self._send_json(handler, {"error": "unauthorised"}, 403)
                return
            self._last_client_seen = time.monotonic()
            if path == "/api/snapshot":
                with self._condition:
                    payload = self._snapshot_json.encode("utf-8")
                self._send_bytes(
                    handler, payload, "application/json; charset=utf-8",
                )
            elif path == "/api/events":
                self._serve_events(handler, parsed)
            elif path == "/api/host":
                self._send_json(handler, {
                    **self._host_state,
                    "closing": self._closing,
                    "revision": self._revision,
                    "host_revision": self._host_revision,
                })
            else:
                self._send_json(handler, {
                    "ok": True,
                    "closing": self._closing,
                    "revision": self._revision,
                    "last_client_seen": self._last_client_seen,
                })
            return

        candidate = self._static_path(path)
        if candidate is None or not candidate.is_file():
            self._send_json(handler, {"error": "not found"}, 404)
            return
        try:
            payload = candidate.read_bytes()
        except OSError:
            self._send_json(handler, {"error": "asset unavailable"}, 404)
            return
        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        self._send_bytes(
            handler,
            payload,
            content_type,
            cache="no-store" if candidate.name == "index.html" else "no-cache",
        )

    def _serve_events(self, handler, parsed):
        query = parse_qs(parsed.query)
        try:
            last_revision = int((query.get("since") or ["-1"])[0])
        except (TypeError, ValueError):
            last_revision = -1
        try:
            wait = max(0.05, min(15.0, float((query.get("wait") or ["12"])[0])))
        except (TypeError, ValueError):
            wait = 12.0
        with self._condition:
            if self._revision == last_revision and not self._closing:
                self._condition.wait(timeout=wait)
            revision = self._revision
            closing = self._closing
        self._send_json(handler, {"revision": revision, "closing": closing})

    def _handle_post(self, handler):
        parsed = urlparse(handler.path)
        if parsed.path != "/api/command" or not self._authorised(handler, parsed):
            self._send_json(handler, {"error": "unauthorised"}, 403)
            return
        origin = str(handler.headers.get("Origin") or "")
        expected_origin = f"http://127.0.0.1:{self.port}"
        if origin and origin != expected_origin:
            self._send_json(handler, {"error": "invalid origin"}, 403)
            return
        try:
            length = int(handler.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_COMMAND_BYTES:
            self._send_json(handler, {"error": "invalid command size"}, 413)
            return
        try:
            payload = json.loads(handler.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(handler, {"error": "invalid json"}, 400)
            return
        if not isinstance(payload, dict) or not str(payload.get("action") or ""):
            self._send_json(handler, {"error": "invalid command"}, 400)
            return
        callback = self.command_callback
        try:
            accepted = bool(callable(callback) and callback(payload))
        except Exception:
            accepted = False
        self._send_json(handler, {"accepted": accepted}, 202 if accepted else 400)
