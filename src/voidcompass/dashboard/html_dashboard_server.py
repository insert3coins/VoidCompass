"""Private loopback transport for the HTML command deck.

The dashboard is a presentation client only.  Elite journal reduction,
profile ownership and every mutating command remain in the Python process.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse

from voidcompass.core.static_assets import asset_type, read_asset


# Engineering build exports can carry a complete outfitting document.  Keep a
# firm loopback limit while allowing normal EDEC/EDSY/SLEF/Coriolis payloads.
MAX_COMMAND_BYTES = 2 * 1024 * 1024
# A postcard drawn in the editor (5.6.3), as a PNG in base64.
MAX_POSTCARD_BYTES = 48 * 1024 * 1024
# Music streams in the slices the player asks for; a file is never read whole.
MEDIA_CHUNK_BYTES = 64 * 1024
_MEDIA_ID = re.compile(r"[0-9a-f]{16}")
_RANGE = re.compile(r"bytes=(\d*)-(\d*)")
_SANDBOXED_MODULES = frozenset({
    "/assets/hatchling-3d.js",
    "/galactic_map/vendor/three.module.min.js",
    "/galactic_map/vendor/three.core.min.js",
})


def _body_read(handler):
    """The request body has been read in full: the connection may be reused."""
    handler.close_connection = not getattr(handler, "keep_after_body", False)


class _DashboardHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    # The dashboard page loads a dozen stylesheets and scripts at once. At
    # socketserver's default listen backlog of 5, Windows refuses part of
    # that burst, which is how launches lost files in their first second
    # (see page-start.js, which still repairs any loss that remains).
    request_queue_size = 128

    def handle_error(self, request, client_address):
        # Browsers drop kept-alive connections whenever they like (an idle
        # socket, a closed page); that is not worth a traceback in the log.
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


class HtmlDashboardServer:
    """Serve bundled dashboard assets and one revisioned application state."""

    def __init__(self, static_root, *, image_root=None, command_callback=None,
                 host_state=None, on_asset_error=None, games_root=None, gamecard_root=None):
        self.static_root = Path(static_root).resolve()
        self.image_root = Path(image_root).resolve() if image_root else None
        # The Games page (5.6.3): each game's own files under /games/<id>/,
        # played framed in the deck, and their card pictures under /gamecards/.
        self.games_root = Path(games_root).resolve() if games_root else self.static_root.parent / "games"
        self.gamecard_root = Path(gamecard_root).resolve() if gamecard_root else None
        self.command_callback = command_callback
        self.on_asset_error = on_asset_error
        self.token = secrets.token_urlsafe(32)
        self._condition = threading.Condition()
        self._snapshot_json = "{}"
        self._revision = 0
        self._last_client_seen = 0.0
        # Only the page's own client calls snapshot/events (the native host
        # polls /api/host), so this count tells the host its page is running.
        self._page_requests = 0
        self._stopping = threading.Event()
        self._closing = False
        self._host_state = dict(host_state or {})
        self._host_revision = 0
        # The music library (services.music_library.MusicLibrary). The page
        # lists it and streams tracks and covers by id, never by file path.
        self.music = None
        # The postcard album (services.postcard_album, 5.5.3.7): pictures by
        # id under /media/postcard/ and /media/postcard-thumb/.
        self.postcards = None
        # The screenshot album (services.screenshot_album): /media/shot/ and
        # /media/shot-thumb/, by id.
        self.screenshots = None
        # Constellations saved as pictures (5.5.4): /media/constellation/ and
        # /media/constellation-thumb/, by id.
        self.constellations = None
        # Answers the deck asks for by name (5.5.10): /api/data/<name>, given
        # to data_provider(name, query) -> (content type, bytes) or None.
        self.data_provider = None
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

    def set_host_value(self, key, value):
        """Store a value the host reads on its next poll, without bumping
        host_revision (which tells the host to re-apply window geometry)."""
        with self._condition:
            self._host_state[str(key)] = value

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
            # Connections are reused (HTTP/1.1 keep-alive). Every overlay
            # polls several times a second, and the music visualizer's levels
            # travel fifteen times a second each way; a fresh TCP connection
            # per request left thousands of sockets in TIME_WAIT, and Windows
            # began refusing new ones (net::ERR_NO_BUFFER_SPACE). An idle
            # connection is dropped after a minute.
            timeout = 60

            def log_message(self, _format, *_args):
                return

            def do_GET(self):
                # A GET never carries a body here; if one does, don't guess
                # where it ends.
                if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Length", "0").strip() not in {"", "0"}:
                    self.close_connection = True
                owner._handle_get(self)

            def do_POST(self):
                # Reuse the connection only once this request's body has been
                # read in full (see _body_read): an unread body would be taken
                # for the next request line.
                self.keep_after_body = not self.close_connection
                self.close_connection = True
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

    def _game_headers(self, handler):
        # A game is framed by the deck and nothing else, and reaches nothing
        # beyond its own folder: it talks to the deck only by postMessage.
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Referrer-Policy", "no-referrer")
        handler.send_header(
            "Content-Security-Policy",
            f"default-src 'self' {self.origin}; script-src 'self' {self.origin}; "
            f"style-src 'self' {self.origin} 'unsafe-inline'; img-src 'self' {self.origin} data: blob:; "
            f"media-src 'self' {self.origin} data: blob:; font-src 'self' {self.origin}; "
            "connect-src 'none'; object-src 'none'; frame-src 'none'; form-action 'none'; "
            f"frame-ancestors {self.origin}; base-uri 'none'",
        )

    def _send_bytes(self, handler, payload, content_type, status=200,
                    cache="no-store", game=False, cors=False):
        handler.send_response(status)
        if game:
            self._game_headers(handler)
        else:
            self._security_headers(handler)
        # The games iframe deliberately has a unique sandbox origin. Browser
        # ES modules require CORS even for same-host URLs, so grant it only for
        # the renderer and the two bundled Three.js modules it imports.
        if cors:
            handler.send_header("Access-Control-Allow-Origin", "*")
        handler.send_header("Cache-Control", cache)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(payload)))
        handler.send_header("Connection", "close" if handler.close_connection else "keep-alive")
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

    @staticmethod
    def _inside(root, relative):
        if root is None or not relative or any(part.startswith(".") for part in relative.split("/")):
            return None
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return None
        return candidate

    def _static_path(self, request_path):
        # Large shared artwork lives outside the web bundle under assets/images so
        # desktop views and packaged builds use one authoritative copy.
        if request_path.startswith("/images/") and self.image_root is not None:
            relative = request_path.removeprefix("/images/")
            if not relative or relative.startswith("."):
                return None
            candidate = (self.image_root / relative).resolve()
            try:
                candidate.relative_to(self.image_root)
            except ValueError:
                return None
            return candidate
        # Shared browser assets live beside the dashboard folder so every
        # overlay can use the same branded cursor without duplicating it, and
        # the boot screen wakes the same watcher orb the heartbeat overlay draws.
        # The music visualizers (5.6.2) are shared with the music overlay, and
        # the Hatchling's looks (5.6.3) with its game page.
        if request_path in {"/assets/cursor.css", "/assets/void-compass-cursor.png",
                            "/assets/heartbeat-orb.js", "/assets/heartbeat-life.js",
                            "/assets/music-visualizers.js", "/assets/hatchling-art.js", "/assets/hatchling-life.js",
                            "/assets/hatchling-3d.js", "/galactic_map/vendor/three.module.min.js",
                            "/galactic_map/vendor/three.core.min.js"}:
            candidate = (self.static_root.parent / request_path.lstrip("/")).resolve()
            try:
                candidate.relative_to(self.static_root.parent)
            except ValueError:
                return None
            return candidate
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
            if path in {"/api/snapshot", "/api/events"}:
                with self._condition:
                    self._page_requests += 1
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
                    "page_requests": self._page_requests,
                })
            else:
                self._send_json(handler, {
                    "ok": True,
                    "closing": self._closing,
                    "revision": self._revision,
                    "last_client_seen": self._last_client_seen,
                })
            return

        if path.startswith("/api/data/"):
            if not self._authorised(handler, parsed):
                self._send_json(handler, {"error": "unauthorised"}, 403)
                return
            self._serve_data(handler, parsed)
            return

        if path == "/api/music/library" or path.startswith("/media/"):
            if not self._authorised(handler, parsed):
                self._send_json(handler, {"error": "unauthorised"}, 403)
                return
            self._serve_music(handler, path)
            return

        if path.startswith("/games/") or path.startswith("/gamecards/"):
            self._serve_game_file(handler, path)
            return

        candidate = self._static_path(path)
        if candidate is None or not candidate.is_file():
            self._report_asset_error(path, "not found")
            self._send_json(handler, {"error": "not found"}, 404)
            return
        try:
            payload = read_asset(candidate)
        except OSError as exc:
            self._report_asset_error(path, type(exc).__name__)
            self._send_json(handler, {"error": "asset unavailable"}, 404)
            return
        content_type = asset_type(candidate)
        self._send_bytes(
            handler,
            payload,
            content_type,
            cache="no-store" if candidate.name == "index.html" else "no-cache",
            cors=path in _SANDBOXED_MODULES,
        )

    def _serve_game_file(self, handler, path):
        game = path.startswith("/games/")
        if game:
            candidate = self._inside(self.games_root, path.removeprefix("/games/"))
        else:
            candidate = self._inside(self.gamecard_root, path.removeprefix("/gamecards/"))
            if candidate is not None and candidate.suffix.casefold() not in {".png", ".jpg", ".jpeg", ".webp"}:
                candidate = None
        if candidate is None or not candidate.is_file():
            self._send_json(handler, {"error": "not found"}, 404)
            return
        try:
            payload = read_asset(candidate)
        except OSError:
            self._send_json(handler, {"error": "asset unavailable"}, 404)
            return
        self._send_bytes(handler, payload, asset_type(candidate), cache="no-cache", game=game)

    def _serve_data(self, handler, parsed):
        name = parsed.path.removeprefix("/api/data/").strip("/")
        query = {key: values[0] for key, values in parse_qs(parsed.query).items() if values}
        provider = self.data_provider
        try:
            answer = provider(name, query) if callable(provider) else None
        except Exception as exc:
            self._send_json(handler, {"error": str(exc)[:200]}, 500)
            return
        if not answer:
            self._send_json(handler, {"error": "not found"}, 404)
            return
        content_type, payload = answer
        self._send_bytes(handler, payload, content_type)

    def _serve_music(self, handler, path):
        if path.startswith("/media/postcard"):
            self._serve_postcard(handler, path)
            return
        if path.startswith("/media/constellation"):
            self._serve_constellation(handler, path)
            return
        if path.startswith("/media/shot"):
            self._serve_screenshot(handler, path)
            return
        library = self.music
        if library is None:
            self._send_json(handler, {"error": "music unavailable"}, 404)
            return
        if path == "/api/music/library":
            self._send_json(handler, library.payload())
            return
        kind, _, name = path.removeprefix("/media/").partition("/")
        identifier = name.removesuffix(".jpg")
        file = None
        if _MEDIA_ID.fullmatch(identifier):
            if kind == "music":
                file = library.track_file(identifier)
            elif kind == "art":
                file = library.art_file(identifier)
        if file is None:
            self._send_json(handler, {"error": "not found"}, 404)
            return
        if kind == "art":
            try:
                payload = file.read_bytes()
            except OSError:
                self._send_json(handler, {"error": "not found"}, 404)
                return
            self._send_bytes(handler, payload, "image/jpeg", cache="no-cache")
            return
        from voidcompass.services.music_library import audio_type
        self._send_file_range(handler, file, audio_type(file))

    def _serve_postcard(self, handler, path):
        album = self.postcards
        kind, _, name = path.removeprefix("/media/").partition("/")
        identifier = name.removesuffix(".png").removesuffix(".jpg")
        data = None
        if album is not None and kind == "postcard-preview":
            data, content_type = album.preview(), "image/png"
        elif album is not None and _MEDIA_ID.fullmatch(identifier):
            if kind == "postcard":
                data, content_type = album.full(identifier), "image/png"
            elif kind == "postcard-thumb":
                data, content_type = album.thumb(identifier), "image/jpeg"
            elif kind == "postcard-photo":
                data, content_type = album.photo(identifier), "image/jpeg"
        if not data:
            self._send_json(handler, {"error": "not found"}, 404)
            return
        self._send_bytes(handler, data, content_type, cache="no-cache")

    def _save_postcard(self, handler):
        """The editor's drawing (5.6.3): {id, mode, design, png (base64)}."""
        origin = str(handler.headers.get("Origin") or "")
        if origin and origin != f"http://127.0.0.1:{self.port}":
            _body_read(handler)
            self._send_json(handler, {"error": "invalid origin"}, 403)
            return
        try:
            length = int(handler.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_POSTCARD_BYTES:
            _body_read(handler)
            self._send_json(handler, {"ok": False, "error": "too big"}, 413)
            return
        try:
            payload = json.loads(handler.rfile.read(length).decode("utf-8"))
            _body_read(handler)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(handler, {"ok": False, "error": "invalid json"}, 400)
            return
        saver = getattr(self, "postcard_saver", None)
        try:
            answer = saver(payload) if callable(saver) and isinstance(payload, dict) else None
        except Exception as exc:
            answer = {"ok": False, "error": str(exc)[:120]}
        answer = answer or {"ok": False, "error": "not saved"}
        self._send_json(handler, answer, 200 if answer.get("ok") else 400)

    def _serve_constellation(self, handler, path):
        album = self.constellations
        kind, _, name = path.removeprefix("/media/").partition("/")
        identifier = name.split(".", 1)[0]
        data, content_type = None, ""
        if album is not None and _MEDIA_ID.fullmatch(identifier):
            if kind == "constellation":
                data, content_type = album.full(identifier), "image/png"
            elif kind == "constellation-thumb":
                data, content_type = album.thumb(identifier), "image/jpeg"
        if not data:
            self._send_json(handler, {"error": "not found"}, 404)
            return
        self._send_bytes(handler, data, content_type, cache="no-cache")

    def _serve_screenshot(self, handler, path):
        album = self.screenshots
        kind, _, name = path.removeprefix("/media/").partition("/")
        identifier = name.split(".", 1)[0]
        data, content_type = None, ""
        if album is not None and _MEDIA_ID.fullmatch(identifier):
            if kind == "shot":
                data, content_type = album.picture(identifier)
            elif kind == "shot-thumb":
                data, content_type = album.thumb(identifier), "image/jpeg"
        if not data:
            self._send_json(handler, {"error": "not found"}, 404)
            return
        self._send_bytes(handler, data, content_type, cache="no-cache")

    def _send_file_range(self, handler, file, content_type):
        """Send a file, or the byte range the player asks for when it seeks."""
        try:
            size = file.stat().st_size
        except OSError:
            self._send_json(handler, {"error": "not found"}, 404)
            return
        start, end, status = 0, max(0, size - 1), 200
        match = _RANGE.fullmatch(str(handler.headers.get("Range") or "").strip())
        if match and (match.group(1) or match.group(2)):
            if match.group(1):
                start = int(match.group(1))
                end = min(int(match.group(2)), size - 1) if match.group(2) else size - 1
            else:
                start = max(0, size - int(match.group(2)))
            if start >= size or start > end:
                handler.send_response(416)
                self._security_headers(handler)
                handler.send_header("Content-Range", f"bytes */{size}")
                handler.send_header("Content-Length", "0")
                handler.send_header("Connection", "close")
                handler.end_headers()
                return
            status = 206
        length = end - start + 1 if size else 0
        handler.send_response(status)
        self._security_headers(handler)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Accept-Ranges", "bytes")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Content-Length", str(length))
        if status == 206:
            handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        handler.send_header("Connection", "close")
        handler.end_headers()
        try:
            # Paused music stops reading; the idle timeout is for requests.
            handler.connection.settimeout(None)
            with open(file, "rb") as source:
                source.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = source.read(min(MEDIA_CHUNK_BYTES, remaining))
                    if not chunk:
                        break
                    handler.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, OSError):
            # The player moved on (a seek or a skip) part-way through.
            pass

    def _report_asset_error(self, path, reason):
        # A missing script leaves the page frozen, so say which one it was.
        callback = self.on_asset_error
        if callable(callback) and not str(path).startswith("/favicon"):
            try:
                callback(f"Dashboard asset unavailable: {path} ({reason})")
            except Exception:
                pass

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
        if parsed.path == "/api/postcard-save" and self._authorised(handler, parsed):
            self._save_postcard(handler)
            return
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
            body = handler.rfile.read(length)
            _body_read(handler)
            payload = json.loads(body.decode("utf-8"))
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
