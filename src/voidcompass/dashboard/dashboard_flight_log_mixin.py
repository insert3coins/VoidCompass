"""Session flight logs (5.5.3.8), for MainDashboard: one page for each
night you flew, on the Captain's Log page, and a notice when you log off
that tonight's is written."""
from __future__ import annotations

import logging
import time

from voidcompass.core.config import get_active_profile
from voidcompass.exploration.flight_log import flight_logs
from voidcompass.overlays import watcher_mind


class DashboardFlightLogMixin:
    def _flight_logs(self, sessions):
        """The Captain's Log sessions' flight logs, worked out again only when
        a session, the travel history or the Watcher's nature changes."""
        config = getattr(self, "config", None) or {}
        history = getattr(self, "travel_history", None)
        newest = sessions[0] if sessions else {}
        finds = []
        deep = getattr(self, "deep_survey", None)
        if deep is not None and hasattr(deep, "discovery_state"):
            try:
                finds = deep.discovery_state(1200)
            except Exception as exc:
                logging.debug("Flight log field discoveries skipped: %s", exc)
        key = (len(sessions), str(newest.get("started")), str(newest.get("ended")), int(newest.get("jumps") or 0),
               getattr(history, "revision", None), watcher_mind.personality(config), get_active_profile(config),
               len(finds), str((finds[-1] if finds else {}).get("timestamp")))
        cached = getattr(self, "_flight_log_cache", None)
        flying = bool(newest) and not newest.get("ended")
        # Tonight's, still in flight, is brought up to date now and then.
        if cached and cached[0] == key and (not flying or time.monotonic() - cached[2] < 20):
            return cached[1]
        rows = []
        if history is not None:
            with history.lock:
                rows = list(history.rows)
        postcards = []
        album = getattr(self, "postcard_album", None)
        if callable(album):
            try:
                postcards = album().rows()
            except Exception as exc:
                logging.debug("Flight log postcards skipped: %s", exc)
        logs = flight_logs(sessions, rows, postcards, watcher_mind.personality(config), finds=finds)
        self._flight_log_cache = (key, logs, time.monotonic())
        return self._flight_log_pet(logs, sessions)

    def _flight_log_pet(self, logs, sessions):
        """The Hatchling's diary for each night (5.6.4), beside the Watcher's words."""
        state_of = getattr(self, "_hatchling_state", None)
        if not callable(state_of):
            return logs
        from voidcompass.core import hatchling
        from voidcompass.exploration.flight_log import _epoch
        state = state_of()
        pet = state.get("pet")
        if not pet:
            return logs
        ends = {str(session.get("started") or ""): session for session in sessions if isinstance(session, dict)}
        shown = []
        for log in logs:
            session = ends.get(log.get("id")) or {}
            start = _epoch(session.get("started"))
            end = _epoch(session.get("ended")) or time.time()
            lines = hatchling.diary(state, start, end) if start is not None else []
            shown.append({**log, "pet": {"name": pet["name"], "lines": lines}} if lines else log)
        return shown

    def _flight_log_written(self):
        """At log-off: a notice that tonight's flight log is on the Captain's
        Log page (Flight log notice on that page)."""
        if not bool((getattr(self, "config", None) or {}).get("flight_log_notice", True)):
            return False
        log = getattr(self, "captains_log", None)
        toast = getattr(self, "toast_hud", None)
        if log is None or toast is None or not hasattr(toast, "push"):
            return False
        try:
            session = next(iter(log.sessions()), None)
        except Exception:
            return False
        if not isinstance(session, dict) or not int(session.get("jumps") or 0) and watcher_mind.session_hours(session) < .1:
            return False
        flown = watcher_mind.session_flown(session)
        summary = watcher_mind.session_summary(session)
        toast.push("FLIGHT LOG WRITTEN", f"{flown}{' · ' + summary if summary else ''}. On the Captain's Log page.",
                   severity="info", duration_s=12.0)
        return True

    def _handle_flight_log_command(self, operation, payload):
        if operation == "notice":
            self.config["flight_log_notice"] = (payload or {}).get("value") is True
            persist = getattr(self, "_persist_config", None)
            if callable(persist):
                persist()
            return True
        return False
