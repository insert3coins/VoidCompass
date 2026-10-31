"""Void Compass's local API (5.5.7): /api/v1 for your own tools.

Off until the commander switches it on (Settings › Integrations › Local API).
It listens on this PC only unless other devices are allowed. There's no key:
nothing it answers leaves the PC, and secrets are redacted. Browsers may call it
only from local pages (files, OBS browser sources, localhost), so a website
can't read it or drive it. Reading is always allowed; changing anything
(overlays, the deck, the voice) can be switched off.

The server never touches application state from its own threads: every call
that reads or changes the app is handed to the app's own thread and waited
for (``run_on_main``). The provider, the dashboard in the app, answers the
``api_*`` calls listed in PROVIDER_CALLS. The human-readable reference is
api.md, served at /api/v1/docs.
"""

from __future__ import annotations

from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import ipaddress
import json
import logging
import os
import re
import sys
import threading
import time
from urllib.parse import parse_qs, unquote, urlparse

from voidcompass.core import journal_files
from voidcompass.core.paths import resource_path

API_VERSION = "1"
PREFIX = "/api/v1"
DEFAULT_PORT = 7380
MAX_BODY_BYTES = 64 * 1024
MAX_STREAMS = 16
MAIN_THREAD_TIMEOUT_S = 8.0
DEBUG_WAIT_S = 1.5
EVENT_TYPES = ("journal", "status", "cargo", "navroute", "market", "shiplocker",
               "feed", "thought", "overlay", "voice", "music", "exploration")
# Anything named like these is blanked before it leaves the app: the deck's
# snapshot can carry the commander's EDSM, Inara and Raven keys and webhooks.
_SECRET_NAME = re.compile(r"api_?key|apikey|webhook|token|secret|password", re.IGNORECASE)
_EVENT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")

# What the provider answers. Every one runs on the app's own thread.
PROVIDER_CALLS = (
    "api_status", "api_debug", "api_commander", "api_location", "api_ship", "api_journal_folder", "api_companion",
    "api_dashboard", "api_pages", "api_page", "api_open_page", "api_feed", "api_add_feed",
    "api_themes", "api_set_theme", "api_overlays", "api_overlay", "api_set_overlay",
    "api_toggle_overlay", "api_hide_overlays", "api_notify", "api_watcher", "api_watcher_thought",
    "api_watcher_poke", "api_watcher_answer", "api_watcher_code", "api_watcher_meet", "api_watcher_book",
    "api_voice", "api_voice_say", "api_voice_stop", "api_voice_hush", "api_music",
    "api_music_library", "api_music_control", "api_galnet",
    "api_bgs", "api_bgs_factions", "api_bgs_faction", "api_bgs_systems", "api_bgs_system", "api_bgs_conflicts",
    "api_bgs_activity", "api_bgs_track",
    "api_exploration", "api_exploration_bodies", "api_exploration_systems", "api_exploration_route",
    "api_exploration_regions", "api_codex", "api_log", "api_add_log", "api_statistics", "api_contacts",
    "api_missions", "api_fleet", "api_achievements", "api_trading", "api_colonisation", "api_carriers",
    "api_mining", "api_mining_run", "api_combat", "api_engineering", "api_powerplay", "api_route",
    "api_copy_next", "api_capsules", "api_leave_capsule",
    "api_add_waypoint", "api_change_waypoint", "api_delete_waypoint", "api_clear_waypoints", "api_return_later",
    "api_return_later_action", "api_neutron_route", "api_import_neutron_route",
    "api_wrapped_years", "api_wrapped", "api_recorder_sessions", "api_recorder_tape",
    "api_rigs", "api_rig_mark", "api_rigs_clear", "api_mining_record",
)


def redact(value):
    """The value with anything secret-looking blanked, however deep."""
    if isinstance(value, dict):
        return {key: ("<hidden>" if _SECRET_NAME.search(str(key)) and item not in ("", None, False)
                      and not isinstance(item, (dict, list)) else redact(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = int(status)
        self.message = str(message)


class EventBus:
    """What happened, numbered, for polling and streaming clients."""

    def __init__(self, size=2000):
        self._events = deque(maxlen=size)
        self._seq = 0
        self._condition = threading.Condition()
        self._last_status = None

    @property
    def seq(self):
        return self._seq

    def publish(self, kind, data):
        kind = str(kind)
        if kind not in EVENT_TYPES:
            return None
        if kind == "status":
            # Status.json is rewritten several times a second with nothing new.
            if data == self._last_status:
                return None
            self._last_status = data
        with self._condition:
            self._seq += 1
            event = {"seq": self._seq, "type": kind, "at": round(time.time(), 3), "data": redact(data)}
            self._events.append(event)
            self._condition.notify_all()
            return event

    def since(self, seq, types=None, limit=100, events=None):
        with self._condition:
            rows = [event for event in self._events if event["seq"] > seq]
        if types:
            rows = [event for event in rows if event["type"] in types]
        if events:
            rows = [event for event in rows if event["type"] != "journal"
                    or str((event["data"] or {}).get("event")) in events]
        return rows[:limit] if limit else rows

    def wait(self, seq, timeout):
        with self._condition:
            if self._seq <= seq:
                self._condition.wait(timeout)
            return self._seq

    def wake(self):
        with self._condition:
            self._condition.notify_all()


def _int(value, default, low=None, high=None):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = default
    if low is not None:
        number = max(low, number)
    if high is not None:
        number = min(high, number)
    return number


def _names(value):
    """A comma-separated list of names from a query parameter."""
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


class _ApiHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 64

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


class LocalApi:
    """The /api/v1 server. ``provider`` answers PROVIDER_CALLS;
    ``run_on_main(task)`` schedules a task on the app's thread and returns
    False once the app is closing."""

    def __init__(self, provider, run_on_main=None, version=""):
        self.provider = provider
        self.run_on_main = run_on_main
        self.version = str(version or "")
        self.bus = EventBus()
        self.port = DEFAULT_PORT
        self.allow_lan = False
        self.allow_control = True
        self.error = ""
        self._server = None
        self._thread = None
        self._streams = 0
        self._streams_lock = threading.Lock()
        self._stopping = threading.Event()
        self._started_at = 0.0
        self._docs_cache = None
        self._routes = self._route_table()

    # -- lifecycle -----------------------------------------------------------
    @property
    def running(self):
        return self._server is not None

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.port}{PREFIX}"

    def configure(self, *, enabled, port=DEFAULT_PORT, allow_lan=False, allow_control=True):
        """Apply the settings: start, stop or restart as they need. True when
        the server is listening as asked (or off when asked)."""
        port = _int(port, DEFAULT_PORT, 1024, 65535)
        self.allow_control = bool(allow_control)
        if not enabled:
            self.stop()
            self.error = ""
            return True
        restart = self.running and (port != self.port or bool(allow_lan) != self.allow_lan)
        self.port, self.allow_lan = port, bool(allow_lan)
        if restart:
            self.stop()
        if self.running:
            return True
        return self.start()

    def start(self):
        host = "0.0.0.0" if self.allow_lan else "127.0.0.1"
        try:
            self._server = _ApiHTTPServer((host, self.port), self._handler_type())
        except OSError as exc:
            self._server = None
            self.error = f"Port {self.port} is in use or blocked ({exc.strerror or exc})"
            logging.warning("Local API could not start: %s", self.error)
            return False
        self.error = ""
        self._stopping.clear()
        self._started_at = time.time()
        # It looks for "stop" every 0.1 s (the default half second was most of
        # its share of a close).
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.1},
                                        name="local-api", daemon=True)
        self._thread.start()
        logging.info("Local API listening on %s:%s", host, self.port)
        return True

    def stop(self):
        server = self._server
        if server is None:
            return
        self._server = None
        self._stopping.set()
        self.bus.wake()
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass

    def publish(self, kind, data):
        """Something happened in the app (any thread)."""
        if self.running:
            self.bus.publish(kind, data)

    def state(self):
        """For the Settings page: listening where, or why not."""
        return {"running": self.running, "url": self.base_url if self.running else "",
                "error": self.error, "lan": self.allow_lan, "control": self.allow_control,
                "streams": self._streams}

    # -- the app's thread ----------------------------------------------------
    def _call(self, name, *args, _wait=MAIN_THREAD_TIMEOUT_S, **kwargs):
        method = getattr(self.provider, name, None)
        if not callable(method):
            raise ApiError(501, f"{name} isn't available in this build")
        if self.run_on_main is None:
            return method(*args, **kwargs)
        done = threading.Event()
        box = {}

        def task():
            try:
                box["value"] = method(*args, **kwargs)
            except ApiError as exc:
                box["error"] = exc
            except Exception as exc:
                logging.exception("Local API call %s failed", name)
                box["error"] = ApiError(500, f"{type(exc).__name__}: {exc}")
            finally:
                done.set()

        if self.run_on_main(task) is False:
            raise ApiError(503, "Void Compass is closing")
        if not done.wait(_wait):
            raise ApiError(504, "Void Compass is busy; try again in a moment")
        if "error" in box:
            raise box["error"]
        return box["value"]

    # -- routes ----------------------------------------------------------------
    def _route_table(self):
        """(method, pattern, handler, control)."""
        rows = [
            ("GET", r"", self._index, False),
            ("GET", r"/ping", self._ping, False),
            ("GET", r"/docs", self._docs, False),
            ("GET", r"/status", lambda req: self._call("api_status"), False),
            # The live debugger (tools/debug): this PC only, whatever the settings.
            ("GET", r"/debug", self._debug, False),
            ("GET", r"/debug/log", self._debug_log, False),
            ("POST", r"/debug/verbose", self._debug_verbose, True),
            ("GET", r"/commander", lambda req: self._call("api_commander"), False),
            ("GET", r"/commander/location", lambda req: self._call("api_location"), False),
            ("GET", r"/commander/ship", lambda req: self._call("api_ship"), False),
            ("GET", r"/journal/events", self._journal_events, False),
            ("GET", r"/journal/history", self._journal_history, False),
            ("GET", r"/journal/files", self._journal_files, False),
            ("GET", r"/journal/(status|cargo|navroute|market|shiplocker)", self._companion, False),
            ("GET", r"/events", self._events, False),
            ("GET", r"/events/stream", self._stream, False),
            ("GET", r"/dashboard", lambda req: self._call("api_dashboard"), False),
            ("GET", r"/dashboard/pages", lambda req: self._call("api_pages"), False),
            ("GET", r"/dashboard/pages/([a-z0-9-]{1,40})", lambda req, page: self._call("api_page", page), False),
            ("POST", r"/dashboard/page", self._open_page, True),
            ("GET", r"/dashboard/feed", self._feed, False),
            ("POST", r"/dashboard/feed", self._add_feed, True),
            ("GET", r"/themes", lambda req: self._call("api_themes"), False),
            ("POST", r"/dashboard/theme", self._set_theme, True),
            ("GET", r"/overlays", lambda req: self._call("api_overlays"), False),
            ("POST", r"/overlays/hide-all", lambda req: self._call("api_hide_overlays", True), True),
            ("POST", r"/overlays/show-all", lambda req: self._call("api_hide_overlays", False), True),
            ("POST", r"/overlays/notify", self._notify, True),
            ("GET", r"/overlays/([a-z0-9_-]{1,40})", lambda req, oid: self._call("api_overlay", oid), False),
            ("POST", r"/overlays/([a-z0-9_-]{1,40})", self._set_overlay, True),
            ("POST", r"/overlays/([a-z0-9_-]{1,40})/toggle",
             lambda req, oid: self._call("api_toggle_overlay", oid), True),
            ("GET", r"/watcher", lambda req: self._call("api_watcher"), False),
            ("POST", r"/watcher/thought", self._thought, True),
            ("POST", r"/watcher/poke", lambda req: self._call("api_watcher_poke"), True),
            ("POST", r"/watcher/answer", self._answer, True),
            ("GET", r"/watcher/code", lambda req: self._call("api_watcher_code"), False),
            ("POST", r"/watcher/meet", self._meet, True),
            ("POST", r"/watcher/book", lambda req: self._call("api_watcher_book"), True),
            ("GET", r"/voice", lambda req: self._call("api_voice"), False),
            ("POST", r"/voice/say", self._say, True),
            ("POST", r"/voice/stop", lambda req: self._call("api_voice_stop"), True),
            ("POST", r"/voice/hush", self._hush, True),
            ("GET", r"/music", lambda req: self._call("api_music"), False),
            ("GET", r"/music/library", lambda req: self._call("api_music_library"), False),
            ("POST", r"/music/(play-pause|next|previous)",
             lambda req, op: self._call("api_music_control", op), True),
            ("GET", r"/galnet", lambda req: self._call("api_galnet"), False),
            ("GET", r"/bgs", lambda req: self._call("api_bgs"), False),
            ("GET", r"/bgs/factions", lambda req: self._call("api_bgs_factions", str(req.query.get("query") or "")[:80]), False),
            ("GET", r"/bgs/factions/([^/]{1,240})", lambda req, name: self._call("api_bgs_faction", unquote(name)[:160]), False),
            ("GET", r"/bgs/systems", self._bgs_systems, False),
            ("GET", r"/bgs/systems/([0-9]{1,20})", self._bgs_system, False),
            ("GET", r"/bgs/conflicts", lambda req: self._call("api_bgs_conflicts"), False),
            ("GET", r"/bgs/activity", self._bgs_activity, False),
            ("POST", r"/bgs/track", self._bgs_track, True),
            ("GET", r"/exploration", lambda req: self._call("api_exploration"), False),
            ("GET", r"/exploration/bodies", self._exploration_bodies, False),
            ("GET", r"/exploration/survey", lambda req: self._call("api_exploration_survey"), False),
            ("GET", r"/exploration/systems", lambda req: self._call(
                "api_exploration_systems", str(req.query.get("query") or "")[:80], _int(req.query.get("limit"), 100, 1, 1000)), False),
            ("GET", r"/exploration/route", lambda req: self._call(
                "api_exploration_route", _int(req.query.get("limit"), 100, 1, 5000)), False),
            ("GET", r"/exploration/regions", lambda req: self._call("api_exploration_regions"), False),
            ("GET", r"/codex", lambda req: self._call("api_codex", str(req.query.get("region") or "")[:60]), False),
            ("GET", r"/log", lambda req: self._call("api_log", _int(req.query.get("limit"), 20, 1, 200)), False),
            ("POST", r"/log", self._add_log, True),
            ("GET", r"/statistics", lambda req: self._call("api_statistics"), False),
            ("GET", r"/contacts", lambda req: self._call("api_contacts"), False),
            ("GET", r"/missions", lambda req: self._call("api_missions"), False),
            ("GET", r"/commander/fleet", lambda req: self._call("api_fleet"), False),
            ("GET", r"/achievements", lambda req: self._call("api_achievements"), False),
            ("GET", r"/trading", lambda req: self._call("api_trading", _int(req.query.get("days"), 30, 1, 3650)), False),
            ("GET", r"/colonisation", lambda req: self._call("api_colonisation"), False),
            ("GET", r"/carrier", lambda req: self._call("api_carriers"), False),
            ("GET", r"/mining", lambda req: self._call("api_mining"), False),
            ("POST", r"/mining/run", self._mining_run, True),
            ("GET", r"/mining/record", lambda req: self._call("api_mining_record"), False),
            ("GET", r"/combat", lambda req: self._call("api_combat"), False),
            ("GET", r"/engineering", lambda req: self._call("api_engineering"), False),
            ("GET", r"/powerplay", lambda req: self._call("api_powerplay"), False),
            ("GET", r"/route", lambda req: self._call("api_route"), False),
            ("POST", r"/route/copy-next", lambda req: self._call("api_copy_next"), True),
            ("POST", r"/route/waypoints", self._add_waypoint, True),
            ("POST", r"/route/waypoints/clear", self._clear_waypoints, True),
            ("POST", r"/route/waypoints/([0-9]{1,4})", self._change_waypoint, True),
            ("POST", r"/route/waypoints/([0-9]{1,4})/delete",
             lambda req, index: self._call("api_delete_waypoint", int(index)), True),
            ("GET", r"/route/return-later", lambda req: self._call("api_return_later"), False),
            ("POST", r"/route/return-later/(waypoint|dismiss)", self._return_later, True),
            ("GET", r"/route/neutron", lambda req: self._call("api_neutron_route"), False),
            ("POST", r"/route/neutron/import", lambda req: self._call("api_import_neutron_route"), True),
            ("GET", r"/capsules", lambda req: self._call("api_capsules"), False),
            ("POST", r"/capsules", self._leave_capsule, True),
            # Your journey, told back (5.5.10).
            ("GET", r"/wrapped", lambda req: self._call("api_wrapped_years"), False),
            ("GET", r"/wrapped/([0-9]{4})", lambda req, year: self._call("api_wrapped", int(year)), False),
            ("GET", r"/recorder", lambda req: self._call("api_recorder_sessions"), False),
            ("GET", r"/recorder/tape", lambda req: self._call("api_recorder_tape", str(req.query.get("session") or "")[:40]), False),
            # Expeditions (5.6.1): the active one, and every one you've kept.
            ("GET", r"/expedition", lambda req: self._call("api_expedition"), False),
            ("GET", r"/expeditions", lambda req: self._call("api_expeditions"), False),
            # The Rig Tracker (5.5.10): the rig keys, from a Stream Deck or a script.
            ("GET", r"/rigs", lambda req: self._call("api_rigs"), False),
            ("POST", r"/rigs/clear", self._clear_rigs, True),
            ("POST", r"/rigs/([1-6])", lambda req, slot: self._call("api_rig_mark", int(slot)), True),
        ]
        return [(method, re.compile(f"^{re.escape(PREFIX)}{pattern}/?$"), handler, control)
                for method, pattern, handler, control in rows]

    def endpoints(self):
        """Every route, for the index."""
        out = []
        for method, pattern, _handler, control in self._routes:
            path = pattern.pattern[1:-3].replace("\\", "")
            path = path.replace("([a-z0-9-]{1,40})", "{page}").replace("([a-z0-9_-]{1,40})", "{overlay}")
            path = path.replace("([^/]{1,240})", "{name}").replace("([0-9]{1,20})", "{address}")
            path = path.replace("([0-9]{1,4})", "{n}").replace("([0-9]{4})", "{year}").replace("([1-6])", "{n}")
            path = re.sub(r"\(([a-z|-]+)\)", r"{\1}", path)
            out.append({"method": method, "path": path or PREFIX, "control": control})
        return out

    # -- handlers ----------------------------------------------------------------
    def _index(self, req):
        return {"name": "Void Compass", "api": API_VERSION, "version": self.version,
                "docs": f"{PREFIX}/docs", "control": self.allow_control, "endpoints": self.endpoints()}

    # -- the live debugger ---------------------------------------------------------
    @staticmethod
    def _debug_caller(req):
        if not _loopback(req.client):
            raise ApiError(403, "The debugger only answers this PC")

    def _debug(self, req):
        """What's going on inside: read off the main thread first, so a stuck
        UI still answers; then the app's own view, if its thread is free."""
        self._debug_caller(req)
        from voidcompass.core import crash_reporter, debug_tap
        answer = {"process": debug_tap.process(), "ui_heartbeat_s": crash_reporter.heartbeat_age(),
                  "threads": debug_tap.threads(stacks=req.query.get("stacks") in ("1", "true")),
                  "verbose_s": debug_tap.verbose(), "log_seq": debug_tap.records(10**12)["seq"],
                  "events_seq": self.bus.seq, "streams": self._streams}
        try:
            # A short wait: the debugger asks every second, and a stuck UI is the news.
            answer["app"] = self._call("api_debug", _wait=DEBUG_WAIT_S)
            answer["main_thread"] = "free"
        except ApiError as exc:
            answer["main_thread"] = "busy" if exc.status == 504 else exc.message
        return answer

    def _debug_log(self, req):
        self._debug_caller(req)
        from voidcompass.core import debug_tap
        return debug_tap.records(_int(req.query.get("since"), 0, 0), str(req.query.get("level") or "DEBUG"),
                                 _int(req.query.get("limit"), 500, 1, debug_tap.RING_SIZE),
                                 str(req.query.get("text") or "")[:80])

    def _debug_verbose(self, req):
        self._debug_caller(req)
        from voidcompass.core import debug_tap
        return {"verbose_s": debug_tap.set_verbose(req.body.get("on") is True,
                                                   _int(req.body.get("seconds"), debug_tap.VERBOSE_MAX_S, 10))}

    def _ping(self, req):
        return {"ok": True, "api": API_VERSION, "version": self.version}

    def _docs(self, req):
        if self._docs_cache is None:
            text = ""
            for candidate in (resource_path("api.md"), resource_path("API.md")):
                try:
                    text = candidate.read_text(encoding="utf-8")
                    break
                except OSError:
                    continue
            self._docs_cache = markdown_page(text or "# Void Compass API\n\nThe reference (api.md) is missing from this build.",
                                             "Void Compass API")
        return _Raw(self._docs_cache, "text/html; charset=utf-8")

    def _journal_events(self, req):
        since = _int(req.query.get("since"), 0, 0)
        limit = _int(req.query.get("limit"), 100, 1, 1000)
        events = set(_names(req.query.get("event")))
        rows = self.bus.since(since, {"journal"}, limit, events or None)
        return {"seq": self.bus.seq, "events": [{"seq": row["seq"], **(row["data"] or {})} for row in rows]}

    def _journal_files(self, req):
        folder = self._call("api_journal_folder")
        limit = _int(req.query.get("limit"), 50, 1, 1000)
        rows = []
        for path in reversed(journal_files.list_journals(folder)[-limit:]):
            try:
                size = os.path.getsize(path)
            except OSError:
                size = None
            started = journal_files.journal_date(path)
            rows.append({"name": os.path.basename(path), "started": started.isoformat() if started else None,
                         "bytes": size})
        return {"folder": folder, "files": rows}

    def _journal_history(self, req):
        """Past events from the journal files on disk, newest first."""
        folder = self._call("api_journal_folder")
        wanted = [name for name in _names(req.query.get("event")) if _EVENT_NAME.match(name)]
        limit = _int(req.query.get("limit"), 50, 1, 500)
        max_files = _int(req.query.get("files"), 20, 1, 200)
        after = str(req.query.get("after") or "")
        before = str(req.query.get("before") or "")
        # The game writes "event":"X"; other tools' copies may add a space.
        markers = [marker for name in wanted for marker in (f'"event":"{name}"', f'"event": "{name}"')]
        found = []
        scanned = 0
        past = False
        for path in reversed(journal_files.list_journals(folder)):
            if past or scanned >= max_files or len(found) >= limit:
                break
            scanned += 1
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as source:
                    lines = source.readlines()
            except OSError:
                continue
            for line in reversed(lines):
                if markers and not any(marker in line for marker in markers):
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                stamp = str(row.get("timestamp") or "")
                if after and stamp and stamp <= after:
                    # Newest first: everything from here on is older still.
                    past = True
                    break
                if before and stamp >= before:
                    continue
                found.append(row)
                if len(found) >= limit:
                    break
        return {"events": redact(found), "files_scanned": scanned}

    def _bgs_systems(self, req):
        only = str(req.query.get("only") or "").casefold()
        if only not in ("", "tracked", "conflicts"):
            raise ApiError(400, "only is tracked or conflicts")
        return self._call("api_bgs_systems", str(req.query.get("query") or "")[:80], only)

    def _bgs_system(self, req, address):
        return self._call("api_bgs_system", int(address), _int(req.query.get("days"), 90, 1, 3650))

    def _bgs_activity(self, req):
        tick = req.query.get("tick")
        if tick in (None, ""):
            return self._call("api_bgs_activity", None)
        try:
            return self._call("api_bgs_activity", float(tick))
        except ValueError:
            raise ApiError(400, "tick is a tick's start, in Unix seconds (from periods[].start)")

    def _bgs_track(self, req):
        name = " ".join(str(req.body.get("faction") or "").split())[:160]
        if not name:
            raise ApiError(400, 'Name the faction: {"faction": "...", "tracked": true}')
        return self._call("api_bgs_track", name, req.body.get("tracked", True) is not False)

    def _exploration_bodies(self, req):
        query = req.query
        return self._call("api_exploration_bodies", str(query.get("system") or "")[:160], _flag(query.get("first")),
                          _flag(query.get("landable")), _flag(query.get("bio")), _flag(query.get("footfall")),
                          _int(query.get("min_value"), 0, 0, 10 ** 12), _int(query.get("limit"), 100, 1, 1000))

    def _add_log(self, req):
        title = " ".join(str(req.body.get("title") or "").split())[:120]
        if not title:
            raise ApiError(400, 'Give the entry a title: {"title": "...", "detail": "..."}')
        return self._call("api_add_log", title, " ".join(str(req.body.get("detail") or "").split())[:1000])

    def _mining_run(self, req):
        action = str(req.body.get("action") or "").casefold()
        if action not in ("start", "end"):
            raise ApiError(400, 'action is "start" or "end"')
        return self._call("api_mining_run", action)

    def _add_waypoint(self, req):
        name = " ".join(str(req.body.get("name") or "").split())[:140]
        if not name:
            raise ApiError(400, 'Name the system: {"name": "Colonia", "note": "..."}')
        return self._call("api_add_waypoint", name, " ".join(str(req.body.get("note") or "").split())[:1000])

    def _change_waypoint(self, req, index):
        changes = {}
        if "name" in req.body:
            changes["name"] = " ".join(str(req.body.get("name") or "").split())[:140]
            if not changes["name"]:
                raise ApiError(400, "A waypoint needs a name")
        if "note" in req.body:
            changes["note"] = " ".join(str(req.body.get("note") or "").split())[:1000]
        if "visited" in req.body:
            changes["visited"] = req.body.get("visited") is True
        if "move" in req.body:
            if req.body.get("move") not in ("up", "down"):
                raise ApiError(400, 'move is "up" or "down"')
            changes["move"] = req.body["move"]
        if not changes:
            raise ApiError(400, 'Say what to change: name, note, visited or move')
        return self._call("api_change_waypoint", int(index), changes)

    def _clear_rigs(self, req):
        if req.body.get("confirmed") is not True:
            raise ApiError(400, 'Forgetting the rigs on this planet needs {"confirmed": true}')
        return self._call("api_rigs_clear")

    def _clear_waypoints(self, req):
        if req.body.get("confirmed") is not True:
            raise ApiError(400, 'Clearing every waypoint needs {"confirmed": true}')
        return self._call("api_clear_waypoints")

    def _return_later(self, req, action):
        entry_id = str(req.body.get("id") or "")[:300]
        if not entry_id:
            raise ApiError(400, 'Which place? {"id": "..."} from /api/v1/route/return-later')
        return self._call("api_return_later_action", action, entry_id)

    def _leave_capsule(self, req):
        note = " ".join(str(req.body.get("note") or "").split())
        if not note:
            raise ApiError(400, 'Write the note: {"note": "..."}')
        wait = str(req.body.get("wait") or "none")
        if wait not in CAPSULE_WAITS:
            raise ApiError(400, f"wait is one of {', '.join(CAPSULE_WAITS)}")
        return self._call("api_leave_capsule", note[:280], " ".join(str(req.body.get("system") or "").split())[:100], wait)

    def _companion(self, req, name):
        data = self._call("api_companion", name)
        if data is None:
            raise ApiError(404, f"No {name} file yet: the game writes it as you play")
        return data

    def _events(self, req):
        since = _int(req.query.get("since"), 0, 0)
        limit = _int(req.query.get("limit"), 200, 1, 1000)
        wait = min(30.0, max(0.0, float(_int(req.query.get("wait"), 0, 0, 30))))
        types = {name for name in _names(req.query.get("types")) if name in EVENT_TYPES} or None
        events = set(_names(req.query.get("event"))) or None
        rows = self.bus.since(since, types, limit, events)
        deadline = time.monotonic() + wait
        while not rows and wait and not self._stopping.is_set():
            left = deadline - time.monotonic()
            if left <= 0:
                break
            self.bus.wait(max(since, self.bus.seq), left)
            rows = self.bus.since(since, types, limit, events)
        return {"seq": self.bus.seq, "events": rows}

    def _stream(self, req):
        return _Stream({name for name in _names(req.query.get("types")) if name in EVENT_TYPES} or None,
                       set(_names(req.query.get("event"))) or None, _int(req.query.get("since"), self.bus.seq, 0))

    def _feed(self, req):
        return self._call("api_feed", _int(req.query.get("limit"), 50, 1, 200))

    def _open_page(self, req):
        page = str(req.body.get("page") or "").strip().casefold()
        if not page:
            raise ApiError(400, "Say which page: {\"page\": \"explore\"}")
        if not self._call("api_open_page", page):
            raise ApiError(404, f"No page called {page}")
        return {"ok": True, "page": page}

    def _add_feed(self, req):
        message = str(req.body.get("message") or "").strip()
        if not message:
            raise ApiError(400, "Say what to show: {\"message\": \"...\"}")
        return self._call("api_add_feed", str(req.body.get("tag") or "API")[:16], message[:500],
                          str(req.body.get("severity") or "INFO"))

    def _set_theme(self, req):
        name = str(req.body.get("name") or "").strip()
        if not name:
            raise ApiError(400, "Say which theme: {\"name\": \"...\"}")
        if not self._call("api_set_theme", name):
            raise ApiError(404, f"No theme called {name}")
        return {"ok": True, "theme": name}

    def _set_overlay(self, req, overlay_id):
        changes = {key: req.body[key] for key in ("enabled", "x", "y", "opacity") if key in req.body}
        if not changes:
            raise ApiError(400, "Nothing to change: send enabled, x, y and/or opacity")
        return self._call("api_set_overlay", overlay_id, changes)

    def _notify(self, req):
        title = str(req.body.get("title") or "").strip()
        if not title:
            raise ApiError(400, "A notification needs a title")
        severity = str(req.body.get("severity") or "info").casefold()
        return self._call("api_notify", title[:80], str(req.body.get("message") or "")[:300],
                          severity if severity in {"info", "warn", "fail", "success"} else "info",
                          max(2.0, min(60.0, float(_int(req.body.get("seconds"), 8, 2, 60)))))

    def _thought(self, req):
        text = " ".join(str(req.body.get("text") or "").split())
        if not text:
            raise ApiError(400, "Give it something to think: {\"text\": \"...\"}")
        return self._call("api_watcher_thought", text[:400], str(req.body.get("heading") or "")[:40],
                          # Said aloud whenever the voice is on, unless asked not to.
                          req.body.get("speak", True) is not False)

    def _answer(self, req):
        answer = req.body.get("answer")
        if isinstance(answer, bool) or answer in (None, ""):
            raise ApiError(400, "Give its answer: {\"answer\": 1} (1 to 3, as the hotkeys) or its key")
        return self._call("api_watcher_answer", answer if isinstance(answer, int) else str(answer)[:40])

    def _meet(self, req):
        code = str(req.body.get("code") or "").strip()
        if not code:
            raise ApiError(400, "Give a friend's Watcher code: {\"code\": \"VCWATCH1...\"}")
        return self._call("api_watcher_meet", code[:4000])

    def _hush(self, req):
        seconds = req.body.get("seconds")
        if seconds is None:
            return self._call("api_voice_hush", None)
        try:
            seconds = max(0, min(86400, int(float(seconds))))
        except (TypeError, ValueError):
            raise ApiError(400, "Seconds is a number: {\"seconds\": 30}, 0 to lift the hush, or leave it out to hush until lifted")
        return self._call("api_voice_hush", seconds)

    def _say(self, req):
        text = " ".join(str(req.body.get("text") or "").split())
        if not text:
            raise ApiError(400, "Give it something to say: {\"text\": \"...\"}")
        return self._call("api_voice_say", text[:400])

    # -- HTTP ----------------------------------------------------------------
    def _handler_type(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "VoidCompassAPI/1"
            timeout = 60

            def log_message(self, _format, *_args):
                return

            def do_OPTIONS(self):
                if owner._caller_refused(self):
                    owner._fail(self, ApiError(403, owner._caller_refused(self)))
                    return
                owner._send(self, 204, b"", "text/plain")

            def do_GET(self):
                owner._handle(self, "GET")

            def do_POST(self):
                owner._handle(self, "POST")

            def do_PUT(self):
                owner._fail(self, ApiError(405, "Use GET or POST"))

            do_DELETE = do_PATCH = do_PUT

        return Handler

    def _handle(self, handler, method):
        parsed = urlparse(handler.path)
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        try:
            refused = self._caller_refused(handler)
            if refused:
                raise ApiError(403, refused)
            route, args = self._match(method, parsed.path)
            _method, _pattern, function, control = route
            if control and not self.allow_control:
                raise ApiError(403, "The API is read-only (allow control in Settings)")
            body = self._body(handler) if method == "POST" else {}
            result = function(_Request(query, body, handler.client_address[0]), *args)
        except ApiError as exc:
            self._fail(handler, exc)
            return
        except Exception as exc:
            logging.exception("Local API request failed: %s", parsed.path)
            self._fail(handler, ApiError(500, f"{type(exc).__name__}: {exc}"))
            return
        if isinstance(result, _Raw):
            self._send(handler, 200, result.body.encode("utf-8"), result.content_type)
        elif isinstance(result, _Stream):
            self._serve_stream(handler, result)
        else:
            self._send_json(handler, 200, redact(result if result is not None else {"ok": True}))

    def _match(self, method, path):
        allowed = False
        for route in self._routes:
            match = route[1].match(path)
            if not match:
                continue
            if route[0] == method:
                return route, match.groups()
            allowed = True
        if allowed:
            raise ApiError(405, f"{method} isn't used on {path}")
        raise ApiError(404, f"No such endpoint: {path} (see {PREFIX} for the list)")

    def _caller_refused(self, handler):
        """Why this caller may not use the API, or "" when it may."""
        if not self.allow_lan and not _loopback(handler.client_address[0]):
            return "Only this PC may call the API (allow other devices in Settings)"
        # Note: a website that points its own name at 127.0.0.1 (DNS rebinding)
        # still sends that name as Host, so only addresses and local names pass.
        if not _local_host(_hostname(handler.headers.get("Host")), self.allow_lan):
            return "Call the API by address (127.0.0.1) or localhost"
        origin = handler.headers.get("Origin")
        if origin is not None and not _local_origin(origin, self.allow_lan):
            return "Web pages may only call the API from this PC (a local file, OBS or localhost)"
        return ""

    def _body(self, handler):
        try:
            length = int(handler.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY_BYTES:
            handler.close_connection = True
            raise ApiError(413, "That request is too big")
        if length <= 0:
            return {}
        raw = handler.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ApiError(400, "The body must be JSON")
        if not isinstance(body, dict):
            raise ApiError(400, "The body must be a JSON object")
        return body

    def _cors(self, handler):
        origin = handler.headers.get("Origin")
        if origin is None or not _local_origin(origin, self.allow_lan):
            return
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Vary", "Origin")
        handler.send_header("Access-Control-Allow-Headers", "Content-Type")
        handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        handler.send_header("Access-Control-Max-Age", "600")

    def _send(self, handler, status, payload, content_type):
        try:
            handler.send_response(status)
            self._cors(handler)
            handler.send_header("Content-Type", content_type)
            handler.send_header("Content-Length", str(len(payload)))
            handler.send_header("Cache-Control", "no-store")
            handler.send_header("X-Content-Type-Options", "nosniff")
            handler.end_headers()
            handler.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _send_json(self, handler, status, payload):
        self._send(handler, status, json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _fail(self, handler, error):
        # Note: a refused POST leaves its body unread, so the connection can't be reused.
        handler.close_connection = True
        self._send_json(handler, error.status, {"error": {"status": error.status, "message": error.message}})

    def _serve_stream(self, handler, stream):
        with self._streams_lock:
            if self._streams >= MAX_STREAMS:
                self._fail(handler, ApiError(429, f"At most {MAX_STREAMS} streams at once"))
                return
            self._streams += 1
        try:
            handler.close_connection = True
            handler.send_response(200)
            self._cors(handler)
            handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
            handler.send_header("Cache-Control", "no-store")
            handler.send_header("Connection", "close")
            handler.end_headers()
            handler.connection.settimeout(None)
            handler.wfile.write(b": void compass\nretry: 3000\n\n")
            handler.wfile.flush()
            seq = stream.since
            last_beat = time.monotonic()
            while not self._stopping.is_set():
                rows = self.bus.since(seq, stream.types, 500, stream.events)
                for row in rows:
                    data = json.dumps(row, ensure_ascii=False, default=str)
                    handler.wfile.write(f"id: {row['seq']}\nevent: {row['type']}\ndata: {data}\n\n".encode("utf-8"))
                    seq = row["seq"]
                if rows:
                    handler.wfile.flush()
                seq = max(seq, self.bus.seq) if not rows else seq
                if time.monotonic() - last_beat > 15:
                    handler.wfile.write(b": still here\n\n")
                    handler.wfile.flush()
                    last_beat = time.monotonic()
                self.bus.wait(seq, 5.0)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with self._streams_lock:
                self._streams -= 1


class _Request:
    def __init__(self, query, body, client=""):
        self.query = query
        self.body = body
        self.client = client


class _Raw:
    def __init__(self, body, content_type):
        self.body = body
        self.content_type = content_type


class _Stream:
    def __init__(self, types, events, since):
        self.types = types
        self.events = events
        self.since = since


def _loopback(address):
    try:
        return ipaddress.ip_address(str(address).split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _flag(value):
    """A yes/no query parameter: None when it isn't given."""
    if value in (None, ""):
        return None
    return str(value).casefold() in ("1", "true", "yes", "on")


# The waits a time capsule can be left with (exploration.time_capsules.WAITS,
# less "date", which needs a date picked on the deck).
CAPSULE_WAITS = ("none", "week", "month", "six_months", "year", "two_years")


def _hostname(value):
    try:
        return (urlparse(f"//{value or ''}").hostname or "").casefold()
    except ValueError:
        return ""


def _local_host(host, allow_lan=False):
    """An address, localhost, or (on a network) a machine name like mypc or mypc.local."""
    if host in ("localhost", ""):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return allow_lan and ("." not in host or host.endswith((".local", ".lan", ".home.arpa")))
    return address.is_loopback or allow_lan


def _local_origin(origin, allow_lan=False):
    """Pages allowed to call from a browser: local files ("null"), OBS's local
    browser sources (http://absolute/), and pages served on this PC."""
    origin = str(origin or "").strip()
    if origin in ("null", "file://"):
        return True
    try:
        host = (urlparse(origin).hostname or "").casefold()
    except ValueError:
        return False
    if host == "absolute":
        return True
    if host in ("localhost",) or host.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or (allow_lan and address.is_private)


# -- the docs page ------------------------------------------------------------------
_INLINE = [
    (re.compile(r"\*\*([^*]+)\*\*"), r"<b>\1</b>"),
    (re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+|#[^)\s]+)\)"), r'<a href="\2">\1</a>'),
]
_LANG_ALIASES = {"js": "javascript", "ps1": "powershell", "cmd": "bat", "sh": "shell", "py": "python"}
_BLOCK_START = re.compile(r"^(#{1,4}\s|```|\||>|[-*]\s|\d+\.\s|<!--)")


def _inline(text):
    # Code spans first, kept apart so their insides aren't formatted.
    parts = re.split(r"(`[^`]+`)", html.escape(text, quote=False))
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{part[1:-1]}</code>")
            continue
        for pattern, replacement in _INLINE:
            part = pattern.sub(replacement, part)
        out.append(part)
    return "".join(out)


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")


def _code_lang(fence, text):
    lang = fence.strip().casefold()
    if lang:
        return _LANG_ALIASES.get(lang, lang)
    head = text.lstrip()
    if head[:1] in "{[":
        return "json"
    if re.match(r"(GET|POST)\s|https?://", head):
        return "http"
    if head.startswith("<"):
        return "html"
    return "text"


def _blocks(text):
    """api.md as blocks: (kind, ...). Only what the reference uses."""
    lines = str(text or "").splitlines()
    blocks = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("```"):
            fence = stripped[3:]
            index += 1
            code = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            body = "\n".join(code)
            blocks.append(("code", _code_lang(fence, body), body))
            continue
        group = re.match(r"^<!--\s*group:\s*(.*?)\s*-->$", stripped)
        if stripped.startswith("<!--"):
            if group:
                blocks.append(("group", group.group(1)))
            index += 1
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            blocks.append(("heading", len(heading.group(1)), heading.group(2)))
            index += 1
            continue
        if stripped.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells):
                    rows.append(cells)
                index += 1
            if rows:
                blocks.append(("table", rows))
            continue
        if re.match(r"^([-*]|\d+\.)\s+", stripped):
            ordered = bool(re.match(r"^\d+\.", stripped))
            items = []
            while index < len(lines) and re.match(r"^([-*]|\d+\.)\s+", lines[index].strip()):
                items.append(re.sub(r"^([-*]|[0-9]+[.])[ ]+", "", lines[index].strip()))
                index += 1
            blocks.append(("list", ordered, items))
            continue
        if stripped.startswith(">"):
            quote = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip()[1:].strip())
                index += 1
            blocks.append(("quote", " ".join(quote)))
            continue
        if not stripped:
            index += 1
            continue
        paragraph = []
        while index < len(lines) and lines[index].strip() and not _BLOCK_START.match(lines[index].strip()):
            paragraph.append(lines[index].strip())
            index += 1
        blocks.append(("para", " ".join(paragraph)))
    return blocks


def _pre(lang, code):
    return f'<pre data-lang="{html.escape(lang)}"><code>{html.escape(code)}</code></pre>'


def _label(text):
    """"**Example: a thing** (Python)" as (kicker, title, note)."""
    match = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", text)
    title, note = (match.group(1), match.group(2)) if match else (text, "")
    kicker = ""
    if title.casefold().startswith("example:"):
        kicker, title = "Example", title.split(":", 1)[1].strip()
    note = note.strip()
    if note.startswith("(") and note.endswith(")"):
        note = note[1:-1]
    return kicker, title, note


def _examples(run):
    """Label-and-code pairs: one becomes an example card, several become tabs."""
    if len(run) == 1:
        (text, (_kind, lang, code)), = run
        kicker, title, note = _label(text)
        caption = (f'<span class="kicker">{html.escape(kicker)}</span>' if kicker else "") + f"<b>{_inline(title)}</b>"
        caption += f"<small>{_inline(note)}</small>" if note else ""
        return f'<figure class="example"><figcaption>{caption}</figcaption>{_pre(lang, code)}</figure>'
    tabs = []
    for text, (_kind, lang, code) in run:
        _kicker, title, note = _label(text)
        note_html = f'<p class="tab-note">{_inline(note)}</p>' if note else ""
        tabs.append(f'<div class="tab" data-label="{html.escape(title)}"><h5 class="tab-label">{_inline(title)}</h5>'
                    f"{note_html}{_pre(lang, code)}</div>")
    return f'<div class="tabs">{"".join(tabs)}</div>'


def _endpoint_table(rows):
    cards = []
    for row in rows[1:]:
        if len(row) < 3:
            continue
        method, path, words = row[0].strip().upper(), row[1].strip().strip("`"), " | ".join(row[2:])
        cards.append(
            f'<article class="endpoint" id="{_slug(method + " " + path)}" data-method="{html.escape(method)}" '
            f'data-path="{html.escape(path)}"><header><span class="verb verb-{method.casefold()}">{html.escape(method)}</span>'
            f'<code class="path">{html.escape(path)}</code></header><p>{_inline(words)}</p></article>')
    return f'<div class="endpoints">{"".join(cards)}</div>'


def _table(rows):
    if [cell.casefold() for cell in rows[0][:3]] == ["method", "path", "what it does"]:
        return _endpoint_table(rows)
    head = "".join(f"<th>{_inline(cell)}</th>" for cell in rows[0])
    rest = "".join("<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in row) + "</tr>" for row in rows[1:])
    return f'<div class="table"><table><thead><tr>{head}</tr></thead><tbody>{rest}</tbody></table></div>'


def _render(blocks, ids, section):
    out = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        kind = block[0]
        following = blocks[index + 1] if index + 1 < len(blocks) else None
        if kind == "para" and block[1].startswith("**") and following and following[0] == "code":
            run = []
            while (index + 1 < len(blocks) and blocks[index][0] == "para" and blocks[index][1].startswith("**")
                   and blocks[index + 1][0] == "code"):
                run.append((blocks[index][1], blocks[index + 1]))
                index += 2
                # An "Example:" is its own card: only variants of one thing share tabs.
                if run[-1][0].casefold().startswith("**example:"):
                    break
            if len(run) > 1 and run[-1][0].casefold().startswith("**example:"):
                run.pop()
                index -= 2
            out.append(_examples(run))
            continue
        if (kind == "code" and block[1] == "http" and re.match(r"(GET|POST)\s", block[2].lstrip())
                and following and following[0] == "code" and following[1] == "json"):
            out.append(f'<div class="exchange"><div class="leg leg-ask"><span>REQUEST</span>{_pre("http", block[2])}</div>'
                       f'<div class="leg leg-answer"><span>RESPONSE</span>{_pre("json", following[2])}</div></div>')
            index += 2
            continue
        if kind == "heading":
            level, words = block[1], block[2]
            slug = _slug(words)
            if level != 2:
                slug = f"{section}-{slug}" if slug in ids else slug
                ids.add(slug)
            out.append(f'<h{level} id="{slug}">{_inline(words)}</h{level}>')
        elif kind == "code":
            out.append(_pre(block[1], block[2]))
        elif kind == "table":
            out.append(_table(block[1]))
        elif kind == "list":
            tag = "ol" if block[1] else "ul"
            out.append(f"<{tag}>{''.join(f'<li>{_inline(item)}</li>' for item in block[2])}</{tag}>")
        elif kind == "quote":
            out.append(f"<blockquote>{_inline(block[1])}</blockquote>")
        elif kind == "para":
            out.append(f"<p>{_inline(block[1])}</p>")
        index += 1
    return "".join(out)


def _docs_asset(name):
    try:
        return resource_path("web", "api-docs", name).read_text(encoding="utf-8")
    except OSError:
        return ""


def markdown_page(text, title):
    """api.md as the docs page: one section at a time with a sidebar, endpoint
    cards you can try, tabbed examples. Readable with scripts off too."""
    blocks = _blocks(text)
    # Sections split at each h2; whatever comes first is the overview.
    sections = [{"slug": "overview", "title": "Overview", "group": "", "blocks": []}]
    group = ""
    for block in blocks:
        if block[0] == "group":
            group = block[1]
        elif block[0] == "heading" and block[1] == 2:
            sections.append({"slug": _slug(block[2]), "title": block[2], "group": group, "blocks": [block]})
        else:
            sections[-1]["blocks"].append(block)
    page_title = title
    overview = sections[0]
    for block in overview["blocks"]:
        if block[0] == "heading" and block[1] == 1:
            page_title = block[2]
            overview["blocks"] = [b for b in overview["blocks"] if b is not block]
            break
    if len(sections) > 1:
        overview["group"] = sections[1]["group"]
    # h2s own their plain slugs, so a same-named h3 elsewhere can't take one.
    ids = {section["slug"] for section in sections}

    nav, body, last_group = [], [], None
    for section in sections:
        if section["group"] != last_group:
            if last_group is not None:
                nav.append("</div>")
            label = f"<h6>{html.escape(section['group'])}</h6>" if section["group"] else ""
            nav.append(f'<div class="rail-group">{label}')
            last_group = section["group"]
        nav.append(f'<a href="#{section["slug"]}">{html.escape(section["title"])}</a>')
        inner = _render(section["blocks"], ids, section["slug"])
        if section is overview:
            inner = f'<h1 id="overview">{_inline(page_title)}</h1>{inner}'
        body.append(f'<section class="doc" data-section="{section["slug"]}" data-group="{html.escape(section["group"])}">'
                    f"{inner}</section>")
    if nav:
        nav.append("</div>")
    css = _docs_asset("docs.css") or _DOCS_FALLBACK_CSS
    script = _docs_asset("docs.js").replace("</script", "<\\/script")
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{html.escape(title)}</title><style>{css}</style></head><body>"
        '<header class="top"><button type="button" class="rail-toggle" aria-label="Sections" aria-expanded="false">'
        '<i></i><i></i><i></i></button><a class="brand" href="#overview"><strong>VOID COMPASS</strong>'
        f'<small>LOCAL API · V{html.escape(API_VERSION)}</small></a>'
        '<code class="base">http://127.0.0.1:7380/api/v1</code>'
        '<span class="live" id="live" title="Is Void Compass answering?"><i></i><span>CHECKING</span></span></header>'
        '<div class="frame"><aside class="rail" id="rail">'
        '<label class="find"><input id="find" type="search" placeholder="Find an endpoint or topic" '
        'autocomplete="off" spellcheck="false" aria-label="Find"><kbd>/</kbd></label>'
        '<div class="results" id="results" hidden></div>'
        f'<nav aria-label="Sections">{"".join(nav)}</nav></aside>'
        f'<main id="main">{"".join(body)}</main></div>'
        f"<script>{script}</script></body></html>"
    )


# Note: only used if web/api-docs is missing from a build.
_DOCS_FALLBACK_CSS = """
:root{color-scheme:dark;--bg:#070b10;--panel:#0d141c;--border:#243746;--text:#dcebf3;--muted:#91a8b7;--accent:#00d1ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 "Segoe UI",system-ui,sans-serif}
.top,.rail{padding:12px 20px;border-bottom:1px solid var(--border)}.rail a{display:inline-block;margin-right:14px;color:var(--muted)}
main{max-width:920px;padding:8px 20px 80px}a{color:var(--accent)}h1,h2,h3{color:#fff}
code{font:13px/1.5 Consolas,monospace;background:var(--panel);padding:1px 5px}pre{background:var(--panel);border:1px solid var(--border);padding:12px;overflow:auto}
pre code{padding:0}table{border-collapse:collapse;width:100%}th,td{border:1px solid var(--border);padding:6px 9px;text-align:left}
.endpoint{border:1px solid var(--border);padding:8px 12px;margin:6px 0}.verb{font-weight:700;margin-right:8px;color:var(--accent)}
.find,.results,.live,.rail-toggle{display:none}
"""
