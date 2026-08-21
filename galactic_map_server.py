"""Loopback-only HTTP transport for the HTML Galactic Atlas.

The server deliberately owns no Elite Dangerous state.  Tk publishes immutable
JSON snapshots and receives validated commands through callbacks queued by the
map view.  This keeps journal and profile state on the application's UI thread
while the browser performs all rendering.
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


MAX_COMMAND_BYTES = 96 * 1024


class _AtlasHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class GalacticMapServer:
    """Serve bundled atlas assets and live data on a private random port."""

    def __init__(self, static_root, atlas_asset, *, command_callback=None,
                 regions_provider=None, status_callback=None):
        self.static_root = Path(static_root).resolve()
        self.atlas_asset = Path(atlas_asset).resolve()
        self.command_callback = command_callback
        self.regions_provider = regions_provider
        self.status_callback = status_callback
        self.token = secrets.token_urlsafe(32)
        self._condition = threading.Condition()
        self._snapshot_json = "{}"
        self._revision = 0
        self._regions_json = None
        self._stopping = threading.Event()
        self._last_client_seen = 0.0
        self._clients = 0
        self._server = _AtlasHTTPServer(("127.0.0.1", 0), self._handler_type())
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="galactic-atlas-http",
            daemon=True,
        )
        self._thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/?token={self.token}"

    @property
    def last_client_seen(self):
        return self._last_client_seen

    @property
    def client_count(self):
        return self._clients

    def publish(self, snapshot):
        """Publish one JSON-safe immutable snapshot and wake live clients."""
        encoded = json.dumps(
            snapshot or {}, ensure_ascii=False, separators=(",", ":"),
        )
        with self._condition:
            self._snapshot_json = encoded
            self._revision += 1
            self._condition.notify_all()
            return self._revision

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
        threading.Thread(
            target=self.stop, name="galactic-atlas-stop", daemon=True,
        ).start()

    def _handler_type(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "VoidCompassAtlas/1"

            def log_message(self, _format, *_args):
                return

            def do_GET(self):
                owner._handle_get(self)

            def do_POST(self):
                owner._handle_post(self)

        return Handler

    def _touch_client(self, delta=0):
        self._last_client_seen = time.monotonic()
        if delta:
            self._clients = max(0, self._clients + int(delta))
        callback = self.status_callback
        if callable(callback):
            try:
                callback(self._clients, self._last_client_seen)
            except Exception:
                pass

    def _authorised(self, handler, parsed):
        query = parse_qs(parsed.query)
        supplied = (
            (query.get("token") or [""])[0]
            or handler.headers.get("X-VoidCompass-Token", "")
        )
        return secrets.compare_digest(str(supplied), self.token)

    def _security_headers(self, handler):
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Referrer-Policy", "no-referrer")
        handler.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'none'",
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
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_json(self, handler, payload, status=200):
        encoded = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")
        self._send_bytes(handler, encoded, "application/json; charset=utf-8", status)

    def _static_path(self, request_path):
        aliases = {
            "/": "index.html",
            "/index.html": "index.html",
            "/app.js": "app.js",
            "/boot.js": "boot.js",
            "/styles.css": "styles.css",
            "/vendor/three.module.min.js": "vendor/three.module.min.js",
            "/vendor/three.core.min.js": "vendor/three.core.min.js",
            "/vendor/OrbitControls.js": "vendor/OrbitControls.js",
        }
        relative = aliases.get(request_path)
        if relative is None:
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
        if path == "/api/events":
            if not self._authorised(handler, parsed):
                self._send_json(handler, {"error": "unauthorised"}, 403)
                return
            self._serve_events(handler)
            return
        if path in {"/api/snapshot", "/api/regions", "/api/health"}:
            if not self._authorised(handler, parsed):
                self._send_json(handler, {"error": "unauthorised"}, 403)
                return
            self._touch_client()
            if path == "/api/snapshot":
                with self._condition:
                    payload = self._snapshot_json.encode("utf-8")
                self._send_bytes(
                    handler, payload, "application/json; charset=utf-8",
                )
            elif path == "/api/regions":
                self._serve_regions(handler)
            else:
                with self._condition:
                    revision = self._revision
                self._send_json(handler, {
                    "ok": True, "revision": revision,
                    "clients": self._clients,
                })
            return
        if path == "/assets/atlas.png":
            candidate = self.atlas_asset
        elif path == "/assets/icon.png":
            candidate = self.static_root.parent.parent / "icon-source.png"
        else:
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
            handler, payload, content_type,
            cache="public, max-age=86400" if path != "/" else "no-store",
        )

    def _serve_regions(self, handler):
        if self._regions_json is None:
            try:
                payload = self.regions_provider() if callable(self.regions_provider) else {}
                self._regions_json = json.dumps(
                    payload, ensure_ascii=False, separators=(",", ":"),
                )
            except Exception as exc:
                self._send_json(handler, {"error": str(exc)}, 500)
                return
        self._send_bytes(
            handler, self._regions_json.encode("utf-8"),
            "application/json; charset=utf-8", cache="public, max-age=86400",
        )

    def _serve_events(self, handler):
        handler.send_response(200)
        self._security_headers(handler)
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Connection", "keep-alive")
        handler.send_header("X-Accel-Buffering", "no")
        handler.end_headers()
        self._touch_client(1)
        try:
            last_revision = -1
            while not self._stopping.is_set():
                with self._condition:
                    if self._revision == last_revision:
                        self._condition.wait(timeout=12.0)
                    revision = self._revision
                if self._stopping.is_set():
                    break
                if revision != last_revision:
                    body = f"event: revision\ndata: {revision}\n\n".encode("utf-8")
                    last_revision = revision
                else:
                    body = b": keepalive\n\n"
                try:
                    handler.wfile.write(body)
                    handler.wfile.flush()
                    self._touch_client()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            self._touch_client(-1)

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
        self._touch_client()
        callback = self.command_callback
        if callable(callback):
            try:
                accepted = callback(payload)
            except Exception:
                accepted = False
        else:
            accepted = False
        self._send_json(handler, {"accepted": bool(accepted)}, 202 if accepted else 400)
