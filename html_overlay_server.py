"""Private loopback transport shared by every HTML cockpit overlay."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import parse_qs, urlparse


class _OverlayHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _OverlayState:
    def __init__(self, overlay_id, template, title):
        self.overlay_id = str(overlay_id)
        self.template = str(template or "canvas")
        self.title = str(title or overlay_id)
        self.snapshot_json = "{}"
        # A newly registered surface stays hidden until its first authoritative
        # model supplies geometry; this prevents a 0,0 startup flash.
        self.window = {"visible": False}
        self.shutdown = False
        self.revision = 0
        self.clients = 0
        self.last_client_seen = 0.0
        self.rendered_revision = -1
        self.content_height = 0
        self.last_rendered_at = 0.0
        self.ready = threading.Event()
        self.host_status = {}


class HtmlOverlayServer:
    """Serve bundled assets and independent SSE streams from one port."""

    def __init__(self, static_root, presentation_held=False):
        self.static_root = Path(static_root).resolve()
        self.token = secrets.token_urlsafe(32)
        self._condition = threading.Condition()
        self._overlays = {}
        self._window_revision = 0
        self._presentation_held = bool(presentation_held)
        self._host_shutdown = False
        self._stopping = threading.Event()
        self._server = _OverlayHTTPServer(("127.0.0.1", 0), self._handler_type())
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="html-overlay-http",
            daemon=True,
        )
        self._thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/?token={self.token}"

    def register(self, overlay_id, template=None, title=None):
        overlay_id = str(overlay_id)
        with self._condition:
            state = self._overlays.get(overlay_id)
            if state is None:
                state = _OverlayState(overlay_id, template or "canvas", title or overlay_id)
                self._overlays[overlay_id] = state
                self._window_revision += 1
            else:
                if template:
                    state.template = str(template)
                if title:
                    state.title = str(title)
            self._condition.notify_all()
        return state

    def unregister(self, overlay_id):
        with self._condition:
            state = self._overlays.get(str(overlay_id))
            if state is None:
                return
            try:
                payload = json.loads(state.snapshot_json or "{}")
            except json.JSONDecodeError:
                payload = {}
            payload["shutdown"] = True
            payload.setdefault("window", {})["shutdown"] = True
            state.snapshot_json = json.dumps(payload, separators=(",", ":"))
            state.window = dict(payload.get("window") or {})
            state.shutdown = True
            self._window_revision += 1
            state.revision += 1
            self._condition.notify_all()

    def publish(self, overlay_id, snapshot):
        state = self.register(overlay_id)
        snapshot = snapshot or {}
        encoded = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
        with self._condition:
            window = dict(snapshot.get("window") or {})
            shutdown = bool(snapshot.get("shutdown"))
            window_changed = window != state.window or shutdown != state.shutdown
            if window_changed:
                state.window = window
                state.shutdown = shutdown
                self._window_revision += 1
            if encoded == state.snapshot_json:
                if window_changed:
                    self._condition.notify_all()
                return state.revision
            state.snapshot_json = encoded
            state.revision += 1
            self._condition.notify_all()
            return state.revision

    def update_window(self, overlay_id, window):
        """Publish geometry/visibility without rebuilding the visual model."""
        state = self.register(overlay_id)
        window = dict(window or {})
        with self._condition:
            if window == state.window:
                return self._window_revision
            state.window = window
            state.shutdown = bool(window.get("shutdown"))
            self._window_revision += 1
            self._condition.notify_all()
            return self._window_revision

    def is_ready(self, overlay_id):
        with self._condition:
            state = self._overlays.get(str(overlay_id))
            return bool(state and state.ready.is_set())

    def clients(self, overlay_id):
        with self._condition:
            state = self._overlays.get(str(overlay_id))
            return int(state.clients if state else 0)

    def last_client_seen(self, overlay_id):
        """Return the monotonic timestamp of the latest browser request."""
        with self._condition:
            state = self._overlays.get(str(overlay_id))
            return float(state.last_client_seen if state else 0.0)

    def rendered_revision(self, overlay_id):
        """Return the newest model the browser confirms it has painted."""
        with self._condition:
            state = self._overlays.get(str(overlay_id))
            return int(state.rendered_revision if state else -1)

    def rendered_content_height(self, overlay_id):
        """Return the browser's latest intrinsic content-height request."""
        with self._condition:
            state = self._overlays.get(str(overlay_id))
            return int(state.content_height if state else 0)

    def host_status(self, overlay_id):
        with self._condition:
            state = self._overlays.get(str(overlay_id))
            return dict(state.host_status if state else {})

    def window_manifest(self):
        with self._condition:
            result = {}
            for overlay_id, state in self._overlays.items():
                result[overlay_id] = {
                    "template": state.template,
                    "title": state.title,
                    "window": dict(state.window),
                    "shutdown": state.shutdown,
                }
            return result

    def set_presentation_held(self, held):
        """Atomically curtain every native browser window in the host."""
        held = bool(held)
        with self._condition:
            if held == self._presentation_held:
                return self._window_revision
            self._presentation_held = held
            self._window_revision += 1
            self._condition.notify_all()
            return self._window_revision

    def request_host_shutdown(self):
        """Wake the browser host and ask it to close every WebView window."""
        with self._condition:
            if self._host_shutdown:
                return
            self._host_shutdown = True
            self._window_revision += 1
            self._condition.notify_all()

    def stop(self):
        if self._stopping.is_set():
            return
        self._stopping.set()
        with self._condition:
            self._condition.notify_all()
        try:
            self._server.shutdown()
        except Exception:
            pass
        try:
            self._server.server_close()
        except Exception:
            pass

    def stop_async(self):
        threading.Thread(target=self.stop, name="html-overlay-stop", daemon=True).start()

    def _handler_type(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "VoidCompassOverlay/2"

            def log_message(self, _format, *_args):
                return

            def do_GET(self):
                owner._handle_get(self)

            def do_POST(self):
                owner._handle_post(self)

        return Handler

    def _authorised(self, handler, parsed):
        query = parse_qs(parsed.query)
        supplied = ((query.get("token") or [""])[0]
                    or handler.headers.get("X-VoidCompass-Token", ""))
        return secrets.compare_digest(str(supplied), self.token)

    @staticmethod
    def _security_headers(handler):
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Referrer-Policy", "no-referrer")
        handler.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
            "frame-ancestors 'none'; base-uri 'none'",
        )

    def _send_bytes(self, handler, payload, content_type, status=200, cache="no-store"):
        try:
            handler.send_response(status)
            self._security_headers(handler)
            handler.send_header("Cache-Control", cache)
            handler.send_header("Content-Type", content_type)
            handler.send_header("Content-Length", str(len(payload)))
            handler.send_header("Connection", "close")
            handler.end_headers()
            handler.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _send_json(self, handler, payload, status=200):
        self._send_bytes(handler, json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                         "application/json; charset=utf-8", status)

    @staticmethod
    def _overlay_id(parsed):
        return str((parse_qs(parsed.query).get("overlay") or [""])[0])

    def _state(self, parsed):
        overlay_id = self._overlay_id(parsed)
        with self._condition:
            return self._overlays.get(overlay_id)

    def _touch(self, state, delta=0):
        with self._condition:
            state.last_client_seen = time.monotonic()
            if delta:
                state.clients = max(0, state.clients + int(delta))

    def _static_path(self, request_path):
        relative = request_path.lstrip("/")
        candidate = (self.static_root / relative).resolve()
        try:
            candidate.relative_to(self.static_root)
        except ValueError:
            return None
        return candidate

    def _handle_get(self, handler):
        parsed = urlparse(handler.path)
        if parsed.path.startswith("/api/"):
            if not self._authorised(handler, parsed):
                self._send_json(handler, {"error": "unauthorised"}, 403)
                return
            if parsed.path == "/api/windows":
                query = parse_qs(parsed.query)
                try:
                    since = int((query.get("since") or ["-1"])[0])
                except (TypeError, ValueError):
                    since = -1
                try:
                    wait_s = max(0.0, min(1.0, float((query.get("wait") or ["0"])[0])))
                except (TypeError, ValueError):
                    wait_s = 0.0
                with self._condition:
                    if since == self._window_revision and wait_s:
                        self._condition.wait_for(
                            lambda: (
                                self._window_revision != since
                                or self._host_shutdown
                                or self._stopping.is_set()
                            ),
                            timeout=wait_s,
                        )
                    revision = self._window_revision
                    overlays = self.window_manifest()
                    presentation_held = self._presentation_held
                    closing = self._host_shutdown or self._stopping.is_set()
                self._send_json(handler, {
                    "revision": revision,
                    "overlays": overlays,
                    "presentation_held": presentation_held,
                    "closing": closing,
                })
                return
            state = self._state(parsed)
            if state is None:
                self._send_json(handler, {"error": "unknown overlay"}, 404)
                return
            if parsed.path == "/api/events":
                self._serve_events(handler, state)
                return
            self._touch(state)
            if parsed.path == "/api/snapshot":
                with self._condition:
                    payload = state.snapshot_json.encode("utf-8")
                self._send_bytes(handler, payload, "application/json; charset=utf-8")
            elif parsed.path == "/api/health":
                self._send_json(handler, {
                    "ok": True, "revision": state.revision, "clients": state.clients,
                    "rendered_revision": state.rendered_revision,
                    "ready": state.ready.is_set(),
                })
            else:
                self._send_json(handler, {"error": "not found"}, 404)
            return
        candidate = self._static_path(parsed.path)
        if candidate is None or not candidate.is_file():
            self._send_json(handler, {"error": "not found"}, 404)
            return
        try:
            payload = candidate.read_bytes()
        except OSError:
            self._send_json(handler, {"error": "asset unavailable"}, 404)
            return
        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        self._send_bytes(handler, payload, content_type)

    def _serve_events(self, handler, state):
        handler.send_response(200)
        self._security_headers(handler)
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Connection", "keep-alive")
        handler.send_header("X-Accel-Buffering", "no")
        handler.end_headers()
        self._touch(state, 1)
        try:
            last_revision = -1
            while not self._stopping.is_set():
                with self._condition:
                    if state.revision == last_revision:
                        self._condition.wait(timeout=10.0)
                    revision = state.revision
                if self._stopping.is_set():
                    break
                body = (f"event: revision\ndata: {revision}\n\n".encode("utf-8")
                        if revision != last_revision else b": keepalive\n\n")
                last_revision = revision
                try:
                    handler.wfile.write(body)
                    handler.wfile.flush()
                    self._touch(state)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            self._touch(state, -1)

    def _handle_post(self, handler):
        parsed = urlparse(handler.path)
        allowed = {"/api/ready", "/api/rendered", "/api/host-status"}
        if parsed.path not in allowed or not self._authorised(handler, parsed):
            self._send_json(handler, {"error": "unauthorised"}, 403)
            return
        state = self._state(parsed)
        if state is None:
            self._send_json(handler, {"error": "unknown overlay"}, 404)
            return
        if parsed.path == "/api/host-status":
            try:
                length = min(4096, max(0, int(handler.headers.get("Content-Length", "0"))))
                payload = json.loads(handler.rfile.read(length) or b"{}")
                state.host_status = payload if isinstance(payload, dict) else {}
            except (TypeError, ValueError, json.JSONDecodeError, OSError):
                state.host_status = {"ok": False, "reason": "invalid host status"}
            self._send_json(handler, {"accepted": True}, 202)
            return
        if parsed.path == "/api/rendered":
            try:
                length = min(1024, max(0, int(handler.headers.get("Content-Length", "0"))))
                payload = json.loads(handler.rfile.read(length) or b"{}")
                revision = int(payload.get("revision"))
                content_height = max(0, min(4096, int(payload.get("content_height") or 0)))
            except (TypeError, ValueError, json.JSONDecodeError, OSError):
                self._send_json(handler, {"error": "invalid revision"}, 400)
                return
            with self._condition:
                state.rendered_revision = max(state.rendered_revision, revision)
                state.content_height = content_height
                state.last_rendered_at = time.monotonic()
                state.last_client_seen = state.last_rendered_at
            self._send_json(handler, {"accepted": True, "revision": revision}, 202)
            return
        state.ready.set()
        self._send_json(handler, {"ready": True}, 202)
