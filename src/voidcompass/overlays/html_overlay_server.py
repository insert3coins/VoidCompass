"""Private loopback transport shared by every HTML cockpit overlay."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import deque
import json
import logging
from pathlib import Path
import secrets
import weakref
import sys
import threading
import time
from urllib.parse import parse_qs, unquote, urlparse

from voidcompass.core.static_assets import asset_type, read_asset


def _clean_shapes(value):
    """The page's shapes as at most 32 polygons of 3-64 integer points."""
    shapes = []
    for polygon in (value if isinstance(value, list) else [])[:32]:
        if not isinstance(polygon, list):
            continue
        points = []
        for point in polygon[:64]:
            try:
                x, y = int(point[0]), int(point[1])
            except (TypeError, ValueError, IndexError):
                continue
            points.append([max(-100, min(20000, x)), max(-100, min(20000, y))])
        if len(points) >= 3:
            shapes.append(points)
    return shapes


def _body_read(handler):
    """The request body has been read in full: the connection may be reused."""
    handler.close_connection = not getattr(handler, "keep_after_body", False)


class _OverlayHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    # Every overlay page asks for its files at once as the host starts. At
    # socketserver's default listen backlog of 5, Windows refuses part of that
    # burst (WSAECONNREFUSED): a page that loses a script never renders, and
    # one that loses its document fails navigation. That was the overlay that
    # "sometimes" never came up.
    request_queue_size = 128

    def handle_error(self, request, client_address):
        # Browsers drop kept-alive connections whenever they like (an idle
        # socket, a closed page); that is not worth a traceback in the log.
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


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
        # The page's visible shapes (device px polygons), for the Dark box fix.
        self.shapes = []
        self.last_rendered_at = 0.0
        self.ready = threading.Event()
        self.host_status = {}
        self.reload_revision = 0
        self.generation = 0
        self.layout_revision = 0
        self.measured_layout_revision = -1
        self.measured_revision = -1
        self.measurement_serial = -1
        self.ordered = deque()
        self.event_signature = None
        self.delivery_protocol = 0


class HtmlOverlayServer:
    """Serve bundled assets, atomic models and the shared overlay-host feed."""

    def __init__(self, static_root, presentation_held=False, on_asset_error=None):
        self.static_root = Path(static_root).resolve()
        self.on_asset_error = on_asset_error
        # Ship portraits live with the rest of Void Compass' bundled artwork,
        # outside the HTML document root.  Expose that one directory through a
        # narrow, traversal-safe route so the navigation HUD can select from a
        # complete journal-ID catalog without duplicating every image in web/.
        self.ship_art_root = (
            self.static_root.parent / "assets" / "images" / "ships"
        ).resolve()
        self.token = secrets.token_urlsafe(32)
        self._condition = threading.Condition()
        self._overlays = {}
        self._window_revision = 0
        HtmlOverlayServer._instances.add(self)
        self._presentation_held = bool(presentation_held)
        self._host_shutdown = False
        self._stopping = threading.Event()
        # Per-overlay sources of data that change too quickly to republish as
        # snapshots (the music visualizer's levels), served at /api/live.
        self._live_providers = {}
        # Per-overlay files made on request (5.5.3.7): the minimap's region
        # map, a postcard's photo. Served at /api/file?name=...
        self._file_providers = {}
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

    # Animation frames per second for every overlay page; 0 is uncapped.
    frame_rate = 30
    # Overlays with a frame rate of their own (5.5.7, the Watcher), by
    # overlay id; the rest follow ``frame_rate``.
    frame_rate_by_overlay = {}
    # Every overlay at once (5.5.1.5): hidden while the Galaxy or System Map
    # is open, or all shown with an outline while Overlay Studio's layout
    # mode is on, so empty ones can be placed too. Layout mode wins.
    # Overlay ids hidden while a map is open (each overlay can opt out).
    overlays_hidden = frozenset()
    layout_mode = False
    # Overlay Studio's OPACITY for every overlay (0.4-1). The host fades each
    # window with Windows' own layered-window alpha rather than the pages
    # fading themselves: the desktop compositor does it, so it holds on every
    # GPU and driver (a page-level fade did not reach the screen for one
    # Radeon RX 9070 XT user, though full transparency did).
    opacity = 1.0
    # Overlays with their own opacity (5.5.3.3), by overlay id; the rest
    # follow ``opacity``.
    opacity_by_overlay = {}
    # The Dark box fix (5.5.3.3.1): where WebView2 draws without the GPU, its
    # transparent pixels come out black; the host then cuts every overlay
    # window to the shapes its page reports.
    shape_windows = False
    # The overlay host's windows (5.5.3.4.1): visual hosting, or the classic
    # pywebview windows (Overlay Studio, for a PC where the new ones fail).
    # The host reads it when it starts.
    classic_windows = False
    _instances = weakref.WeakSet()

    @classmethod
    def set_opacity(cls, value):
        """Set every overlay window's opacity; True when it changed."""
        try:
            value = round(max(0.4, min(1.0, float(value))), 3)
        except (TypeError, ValueError):
            value = 1.0
        if value == cls.opacity:
            return False
        cls.opacity = value
        for server in list(cls._instances):
            with server._condition:
                server._window_revision += 1
                server._condition.notify_all()
        return True

    @classmethod
    def set_classic_windows(cls, enabled):
        """Classic overlay windows on or off; True when it changed."""
        enabled = bool(enabled)
        changed = enabled != cls.classic_windows
        cls.classic_windows = enabled
        return changed

    @classmethod
    def set_shape_windows(cls, enabled):
        """Turn the Dark box fix on or off; True when it changed."""
        enabled = bool(enabled)
        if enabled == cls.shape_windows:
            return False
        cls.shape_windows = enabled
        for server in list(cls._instances):
            with server._condition:
                server._window_revision += 1
                server._condition.notify_all()
        return True

    @classmethod
    def set_overlay_frame_rates(cls, mapping):
        """Set the overlays that animate at their own rate ({overlay id:
        frames per second}); 0 or a missing id follows ``frame_rate``. The
        pages pick it up on their next health poll."""
        clean = {}
        for overlay_id, value in (mapping or {}).items():
            try:
                rate = int(value)
            except (TypeError, ValueError):
                continue
            if rate > 0:
                clean[str(overlay_id)] = max(5, min(240, rate))
        cls.frame_rate_by_overlay = clean

    @classmethod
    def set_overlay_opacities(cls, mapping):
        """Set the overlays that have their own opacity ({overlay id: 0.4-1});
        True when it changed."""
        clean = {}
        for overlay_id, value in (mapping or {}).items():
            try:
                clean[str(overlay_id)] = round(max(0.4, min(1.0, float(value))), 3)
            except (TypeError, ValueError):
                continue
        if clean == cls.opacity_by_overlay:
            return False
        cls.opacity_by_overlay = clean
        for server in list(cls._instances):
            with server._condition:
                server._window_revision += 1
                server._condition.notify_all()
        return True

    @classmethod
    def set_overrides(cls, hidden=None, layout=None):
        """Change the all-overlay overrides; True when one changed.

        ``hidden`` is the overlay ids to hide (an empty set shows them all).
        """
        changed = False
        layout_changed = False
        if hidden is not None:
            hidden = frozenset(str(item) for item in hidden)
            if hidden != cls.overlays_hidden:
                cls.overlays_hidden = hidden
                changed = True
        if layout is not None and bool(layout) != cls.layout_mode:
            cls.layout_mode = bool(layout)
            changed = True
            layout_changed = True
        if changed:
            for server in list(cls._instances):
                with server._condition:
                    server._window_revision += 1
                    if layout_changed:
                        for state in server._overlays.values():
                            # Pages repaint their layout outline from health.
                            # A map visibility change belongs to native window
                            # state only; invalidating page models here made
                            # every hidden browser wait on its throttled poll
                            # before it could be shown again.
                            state.revision += 1
                    server._condition.notify_all()
        return changed

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
                if self._geometry(window) != self._geometry(state.window):
                    state.layout_revision += 1
                state.window = window
                state.shutdown = shutdown
                self._window_revision += 1
            if encoded == state.snapshot_json:
                if window_changed:
                    self._condition.notify_all()
                return state.revision
            state.snapshot_json = encoded
            state.revision += 1
            # One host waits for both model and window changes. Hidden pages
            # receive the same deliveries as visible ones.
            if not window_changed:
                self._window_revision += 1
            signature = self._event_signature(state.template, snapshot)
            if signature is not None and signature != state.event_signature:
                state.ordered.append((state.revision, encoded))
            state.event_signature = signature
            self._condition.notify_all()
            return state.revision

    @staticmethod
    def _geometry(window):
        return tuple(window.get(key) for key in ("x", "y", "width", "height"))

    @staticmethod
    def _event_signature(template, snapshot):
        """Retain event-bearing changes while ordinary state may coalesce.

        These queues are drained by the page's ordered acknowledgements, and
        reset with its browser generation. They are not animation timelines.
        """
        if template == "toast":
            value = snapshot.get("notifications")
        elif template == "heartbeat":
            model = snapshot.get("heartbeat") or {}
            value = [model.get("events"), model.get("thought")]
        elif template == "hatchling":
            model = snapshot.get("hatchling") or {}
            value = [model.get("cue"), model.get("chat"), model.get("line")]
        else:
            return None
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    def delivery(self, overlay_id, after=None):
        """An atomic model/revision envelope, including unacknowledged events."""
        with self._condition:
            state = self._overlays.get(str(overlay_id))
            if state is None:
                return None
            records = list(state.ordered)
            if not records or records[-1][0] != state.revision:
                records.append((state.revision, state.snapshot_json))
            ordered_revisions = {revision for revision, _ in state.ordered}
            if after == [state.generation, state.layout_revision, state.revision]:
                records = []
            return {
                "type": "voidcompass.overlay",
                "overlay": state.overlay_id,
                "generation": state.generation,
                "layout_revision": state.layout_revision,
                "revision": state.revision,
                "health": {
                    "frame_rate": self.frame_rate_by_overlay.get(state.overlay_id, self.frame_rate),
                    "layout": self.layout_mode, "title": state.title,
                },
                "deliveries": [{
                    "revision": revision, "snapshot": json.loads(encoded),
                    "ordered": revision in ordered_revisions,
                } for revision, encoded in records],
            }

    def snapshot(self, overlay_id):
        """What an overlay page is showing now, as data (the local API), or
        None for an overlay that hasn't published yet."""
        with self._condition:
            state = self._overlays.get(str(overlay_id))
            encoded = state.snapshot_json if state is not None else None
        if not encoded:
            return None
        try:
            return json.loads(encoded)
        except ValueError:
            return None

    def update_window(self, overlay_id, window):
        """Publish geometry/visibility without rebuilding the visual model."""
        state = self.register(overlay_id)
        window = dict(window or {})
        with self._condition:
            if window == state.window:
                return self._window_revision
            if self._geometry(window) != self._geometry(state.window):
                state.layout_revision += 1
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

    def window_visible(self, overlay_id):
        """Return whether the overlay's window is meant to be on screen."""
        with self._condition:
            state = self._overlays.get(str(overlay_id))
            return bool(state and state.window.get("visible"))

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

    def request_reload(self, overlay_id):
        """Ask the host to reload one failed browser page in place."""
        with self._condition:
            state = self._overlays.get(str(overlay_id))
            if state is None or state.shutdown:
                return 0
            state.last_client_seen = 0.0
            state.rendered_revision = -1
            state.content_height = 0
            state.shapes = []
            state.last_rendered_at = 0.0
            state.ready.clear()
            state.host_status = {}
            state.generation += 1
            state.measured_layout_revision = -1
            state.measured_revision = -1
            state.measurement_serial = -1
            state.ordered.clear()
            state.reload_revision += 1
            self._window_revision += 1
            self._condition.notify_all()
            return state.reload_revision

    def window_manifest(self):
        with self._condition:
            result = {}
            for overlay_id, state in self._overlays.items():
                window = dict(state.window)
                window["opacity"] = self.opacity_by_overlay.get(overlay_id, self.opacity)
                if self.shape_windows and state.shapes:
                    window["region"] = state.shapes
                if not state.shutdown:
                    if self.layout_mode:
                        window["visible"] = True
                    elif overlay_id in self.overlays_hidden:
                        window["visible"] = False
                result[overlay_id] = {
                    "template": state.template,
                    "title": state.title,
                    "window": window,
                    "shutdown": state.shutdown,
                    # Native WebView creation and page rendering are separate
                    # milestones.  The host must not reveal a surface until
                    # the browser client has painted an authoritative model.
                    # The page has drawn the latest model (not just any). A
                    # hidden overlay is only revealed once it has, so it never
                    # appears showing what it drew while hidden (5.5.2.7).
                    "render_current": self._render_current(state),
                    "strict_ready": state.delivery_protocol >= 2,
                    "generation": state.generation,
                    "layout_revision": state.layout_revision,
                    "content_ready": bool(
                        state.ready.is_set()
                        and state.rendered_revision >= 0
                    ),
                    "reload_revision": state.reload_revision,
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

    def reset_host_session(self):
        """Forget browser-only state before a replacement host connects.

        Models and requested window geometry remain authoritative in this
        process.  Only the per-process readiness/heartbeat evidence is reset,
        allowing a newly launched WebView host to recreate every surface.
        """
        with self._condition:
            self._host_shutdown = False
            for state in self._overlays.values():
                state.clients = 0
                state.last_client_seen = 0.0
                state.rendered_revision = -1
                state.content_height = 0
                state.shapes = []
                state.last_rendered_at = 0.0
                state.ready.clear()
                state.host_status = {}
                state.generation += 1
                state.measured_layout_revision = -1
                state.measured_revision = -1
                state.measurement_serial = -1
                state.ordered.clear()
            self._window_revision += 1
            self._condition.notify_all()
            return self._window_revision

    @staticmethod
    def _render_current(state):
        return bool(state.rendered_revision >= state.revision and (
            state.delivery_protocol < 2 or (state.measured_layout_revision == state.layout_revision
                                            and state.measured_revision >= state.revision)
        ))

    def acknowledge_rendered(self, overlay_id, payload):
        """Accept applied models in order, and only current layout measurements."""
        revision = int(payload["revision"])
        layout = int(payload.get("layout_revision", -1))
        serial = int(payload.get("measurement", -1))
        height = max(0, min(4096, int(payload.get("content_height") or 0)))
        shapes = _clean_shapes(payload.get("shapes"))
        with self._condition:
            state = self._overlays[str(overlay_id)]
            versioned = "generation" in payload
            if (versioned and int(payload["generation"]) != state.generation) or (
                    not versioned and state.delivery_protocol >= 2):
                return False
            if versioned and not 0 <= revision <= state.revision:
                raise ValueError("invalid revision")
            before = (self._render_current(state), state.content_height, state.shapes)
            state.rendered_revision = max(state.rendered_revision, revision)
            if versioned:
                state.delivery_protocol = 2
            current_measurement = (not versioned or (
                revision == state.revision and layout == state.layout_revision
                and serial > state.measurement_serial
            ))
            if current_measurement:
                if "content_height" in payload:
                    state.content_height = height
                if "shapes" in payload:
                    state.shapes = shapes
                if versioned and payload.get("measured") is True:
                    state.measured_layout_revision = layout
                    state.measured_revision = revision
                    state.measurement_serial = serial
            while state.ordered and state.ordered[0][0] <= revision:
                state.ordered.popleft()
            state.last_rendered_at = time.monotonic()
            state.last_client_seen = state.last_rendered_at
            after = (self._render_current(state), state.content_height, state.shapes)
            if before != after:
                self._window_revision += 1
                self._condition.notify_all()
            return True

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

    def set_live_provider(self, overlay_id, provider):
        """Serve `provider()` at /api/live for one overlay; None removes it."""
        if provider is None:
            self._live_providers.pop(str(overlay_id), None)
        else:
            self._live_providers[str(overlay_id)] = provider

    def set_file_provider(self, overlay_id, provider):
        """Serve `provider(name)` -> (bytes, content type) or None at
        /api/file for one overlay; None removes it."""
        if provider is None:
            self._file_providers.pop(str(overlay_id), None)
        else:
            self._file_providers[str(overlay_id)] = provider

    def stop_async(self):
        threading.Thread(target=self.stop, name="html-overlay-stop", daemon=True).start()

    def _handler_type(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "VoidCompassOverlay/2"
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
            handler.send_header("Connection", "close" if handler.close_connection else "keep-alive")
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

    def _ship_art_path(self, request_path):
        prefix = "/ship-art/"
        if not request_path.startswith(prefix):
            return None
        relative = unquote(request_path[len(prefix):]).lstrip("/")
        candidate = (self.ship_art_root / relative).resolve()
        try:
            candidate.relative_to(self.ship_art_root)
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
                    if (query.get("deliver") or [""])[0] == "1":
                        try:
                            seen = json.loads((query.get("seen") or ["{}"])[0])
                            if not isinstance(seen, dict):
                                seen = {}
                        except (TypeError, ValueError):
                            seen = {}
                        for overlay_id, spec in overlays.items():
                            if not spec["shutdown"]:
                                spec["delivery"] = self.delivery(overlay_id, seen.get(overlay_id))
                    presentation_held = self._presentation_held
                    closing = self._host_shutdown or self._stopping.is_set()
                self._send_json(handler, {
                    "revision": revision,
                    "overlays": overlays,
                    "presentation_held": presentation_held,
                    "closing": closing,
                    "hosting": "classic" if self.classic_windows else "composition",
                })
                return
            state = self._state(parsed)
            if state is None:
                self._send_json(handler, {"error": "unknown overlay"}, 404)
                return
            if parsed.path == "/api/events":
                self._serve_events(handler, state)
                return
            if parsed.path == "/api/file":
                provider = self._file_providers.get(state.overlay_id)
                name = str((parse_qs(parsed.query).get("name") or [""])[0])[:120]
                try:
                    found = provider(name) if callable(provider) and name else None
                except Exception:
                    found = None
                if not (isinstance(found, tuple) and len(found) == 2 and isinstance(found[0], (bytes, bytearray))):
                    self._send_json(handler, {"error": "not found"}, 404)
                    return
                self._send_bytes(handler, bytes(found[0]), str(found[1]), cache="private, max-age=600")
                return
            if parsed.path == "/api/live":
                provider = self._live_providers.get(state.overlay_id)
                try:
                    live = provider() if callable(provider) else {}
                except Exception:
                    live = {}
                self._send_json(handler, live if isinstance(live, dict) else {})
                return
            self._touch(state)
            if parsed.path == "/api/snapshot":
                with self._condition:
                    envelope = (parse_qs(parsed.query).get("envelope") or [""])[0] == "1"
                    payload = (json.dumps(self.delivery(state.overlay_id), separators=(",", ":"))
                               if envelope else state.snapshot_json).encode("utf-8")
                self._send_bytes(handler, payload, "application/json; charset=utf-8")
            elif parsed.path == "/api/health":
                self._send_json(handler, {
                    "ok": True, "revision": state.revision, "clients": state.clients,
                    "rendered_revision": state.rendered_revision,
                    "ready": state.ready.is_set(),
                    # Overlay Studio > All overlays > Frame rate: every page's
                    # animation loops follow it (web/assets/frame-cap.js),
                    # unless the overlay has a rate of its own.
                    "frame_rate": self.frame_rate_by_overlay.get(state.overlay_id, self.frame_rate),
                    # Overlay Studio's layout mode: pages draw a labelled
                    # outline of their window (web/assets/overlay-layout.js).
                    "layout": self.layout_mode,
                    "title": state.title,
                })
            else:
                self._send_json(handler, {"error": "not found"}, 404)
            return
        candidate = self._ship_art_path(parsed.path)
        if candidate is None:
            candidate = self._static_path(parsed.path)
        if candidate is None or not candidate.is_file():
            self._report_asset_error(parsed.path, "not found")
            self._send_json(handler, {"error": "not found"}, 404)
            return
        try:
            payload = read_asset(candidate)
        except OSError as exc:
            self._report_asset_error(parsed.path, type(exc).__name__)
            self._send_json(handler, {"error": "asset unavailable"}, 404)
            return
        cache = "private, max-age=3600" if parsed.path in {
            "/galactic_map/vendor/three.module.min.js", "/galactic_map/vendor/three.core.min.js",
        } else "no-store"
        self._send_bytes(handler, payload, asset_type(candidate), cache=cache)

    def _report_asset_error(self, path, reason):
        # A missing script leaves an overlay that never reports ready.
        callback = self.on_asset_error
        if callable(callback) and not str(path).startswith("/favicon"):
            try:
                callback(f"Overlay asset unavailable: {path} ({reason})")
            except Exception:
                pass

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
            handler.close_connection = True
            self._touch(state, -1)

    def _handle_post(self, handler):
        parsed = urlparse(handler.path)
        allowed = {"/api/ready", "/api/rendered", "/api/host-status", "/api/host-status-batch", "/api/watcher-renderer"}
        if parsed.path not in allowed or not self._authorised(handler, parsed):
            self._send_json(handler, {"error": "unauthorised"}, 403)
            return
        if parsed.path == "/api/host-status-batch":
            try:
                declared = int(handler.headers.get("Content-Length", "0"))
                if not 0 <= declared <= 65536:
                    raise ValueError("invalid length")
                payload = json.loads(handler.rfile.read(declared) or b"{}")
                _body_read(handler)
                statuses = payload["overlays"]
                if not isinstance(statuses, dict) or any(not isinstance(item, dict) for item in statuses.values()):
                    raise ValueError("invalid statuses")
                with self._condition:
                    for overlay_id, status in statuses.items():
                        state = self._overlays.get(overlay_id)
                        if state is not None:
                            state.host_status = status
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
                handler.close_connection = True
                self._send_json(handler, {"error": "invalid host statuses"}, 400)
                return
            self._send_json(handler, {"accepted": True}, 202)
            return
        state = self._state(parsed)
        if state is None:
            self._send_json(handler, {"error": "unknown overlay"}, 404)
            return
        if parsed.path == "/api/watcher-renderer":
            try:
                length = int(handler.headers.get("Content-Length", "0"))
                if not 0 <= length <= 1024:
                    raise ValueError("invalid length")
                payload = json.loads(handler.rfile.read(length) or b"{}")
                _body_read(handler)
                snapshot = json.loads(state.snapshot_json or "{}")
                enabled = (snapshot.get("heartbeat") or {}).get("orb", {}).get("renderer_logging") is True
                from voidcompass.core.watcher_renderer_diagnostics import record
                accepted = state.overlay_id == "heartbeat" and enabled and record("overlay", str(payload.get("renderer") or ""), str(payload.get("reason") or ""))
            except (TypeError, ValueError, AttributeError, json.JSONDecodeError, OSError):
                handler.close_connection = True
                self._send_json(handler, {"error": "invalid renderer report"}, 400)
                return
            self._send_json(handler, {"accepted": bool(accepted)}, 202 if accepted else 403)
            return
        if parsed.path == "/api/host-status":
            try:
                declared = max(0, int(handler.headers.get("Content-Length", "0")))
                payload = json.loads(handler.rfile.read(min(4096, declared)) or b"{}")
                if declared <= 4096:
                    _body_read(handler)
                state.host_status = payload if isinstance(payload, dict) else {}
            except (TypeError, ValueError, json.JSONDecodeError, OSError):
                state.host_status = {"ok": False, "reason": "invalid host status"}
            self._send_json(handler, {"accepted": True}, 202)
            return
        if parsed.path == "/api/rendered":
            try:
                declared = max(0, int(handler.headers.get("Content-Length", "0")))
                payload = json.loads(handler.rfile.read(min(32768, declared)) or b"{}")
                if declared <= 32768:
                    _body_read(handler)
                accepted = self.acknowledge_rendered(state.overlay_id, payload)
                revision = int(payload["revision"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
                self._send_json(handler, {"error": "invalid revision"}, 400)
                return
            self._send_json(handler, {"accepted": accepted, "revision": revision}, 202)
            return
        # /api/ready carries a small body too. Leaving it unread corrupts the
        # next request on this HTTP/1.1 connection (e.g. "{}GET /api/health").
        try:
            length = int(handler.headers.get("Content-Length", "0"))
            if not 0 <= length <= 1024:
                raise ValueError("invalid ready payload length")
            body = handler.rfile.read(length)
            _body_read(handler)
        except (TypeError, ValueError, OSError):
            handler.close_connection = True
            self._send_json(handler, {"error": "invalid ready payload"}, 400)
            return
        # Which renderer the page has, once per overlay, for the logs: a
        # software renderer (SwiftShader) means transparent areas may come
        # out black, the dark boxes the Dark box fix cures (5.5.3.3.1).
        try:
            renderer = str((json.loads(body or b"{}") or {}).get("renderer") or "")[:160]
        except (TypeError, ValueError, AttributeError):
            renderer = ""
        if renderer and renderer != getattr(state, "renderer", ""):
            state.renderer = renderer
            logging.info("Overlay renderer: %s: %s", state.overlay_id, renderer)
        with self._condition:
            try:
                ready_payload = json.loads(body or b"{}")
                if (("generation" in ready_payload and int(ready_payload["generation"]) != state.generation)
                        or (state.delivery_protocol >= 2 and "generation" not in ready_payload)):
                    self._send_json(handler, {"ready": False}, 202)
                    return
            except (TypeError, ValueError):
                self._send_json(handler, {"ready": False}, 400)
                return
            was_content_ready = bool(
                state.ready.is_set() and state.rendered_revision >= 0
            )
            state.ready.set()
            is_content_ready = bool(
                state.ready.is_set() and state.rendered_revision >= 0
            )
            if is_content_ready != was_content_ready:
                self._window_revision += 1
                self._condition.notify_all()
        self._send_json(handler, {"ready": True}, 202)
