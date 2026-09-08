"""HeartbeatHUD — tiny always-on corner pulse confirming the status/journal
watcher is alive, modeled on SrvSurvey's PlotPulse (bottom-left corner icon
that flashes on every journal write).

Rather than pulsing strictly on journal-file writes (which can go quiet for
long stretches during uneventful supercruise), this ties into the highest
-frequency reliable signal already flowing through the app: every processed
Status.json update (dashboard_scan_mixin.py's _apply_status_update). If no
pulse arrives for a while, the dot itself turns red as a stall indicator —
a small visual complement to the app's existing freeze-diagnostics work.

Deliberately skips the shared tri-line/bracket chrome (overlay_chrome.py) —
at ~34px across there's no room for it to read as anything but noise, same
reasoning that kept toast_hud.py's compact notification cards plain.
"""
from application_runtime import OverlayWindowState
import time
from config import save_config
import overlay_chrome
import themes
_CHROMA = '#ff00ff'
_SIZE = 54
_STALL_COLOR = '#ff5a5a'
_STALL_AFTER_S = 15
_MAX_GROWTH = 6

class HeartbeatHUD:

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._pulse_level = 0
        self._pulse_serial = 0
        self._last_pulse_ts = time.time()
        self._activity_kind = 'startup'
        self._activity_label = 'LINK READY'
        self._activity_state = 'STARTUP'
        self._state_changed = False
        self._tick_job = None
        self._last_render_key = None
        self._html_render_model = {'pulse_id': self._pulse_serial, 'stalled': False, 'status': 'TELEMETRY LIVE', 'kind': self._activity_kind, 'activity': self._activity_label, 'state': self._activity_state, 'state_changed': False}
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self.win = OverlayWindowState(root)
        screen_h = root.winfo_screenheight()
        x = self._safe_int(config.get('heartbeat_hud_x'), 12)
        y = self._safe_int(config.get('heartbeat_hud_y'), max(12, screen_h - _SIZE - 12))
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self._redraw()
        self._schedule_tick()

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return int(default)

    def destroy(self):
        if self._tick_job:
            try:
                self.win.cancel(self._tick_job)
            except Exception:
                pass
            self._tick_job = None
        try:
            self.win.destroy()
        except Exception:
            pass

    def _schedule_tick(self, delay_ms=None):
        delay_ms = 150 if self._pulse_level > 0 else 750 if delay_ms is None else delay_ms
        self._tick_job = self.win.call_later(delay_ms, self._tick)

    def _tick(self):
        if self._pulse_level > 0:
            self._pulse_level -= 1
        render_key = (self._pulse_level, time.time() - self._last_pulse_ts > _STALL_AFTER_S)
        if render_key != self._last_render_key:
            self._redraw()
        self._schedule_tick()

    def pulse(self, kind='status', activity=None, state=None):
        """Flash for journal/Status activity and retain its cockpit context."""
        growth = 1 if self.config.get('reduced_motion_enabled', False) else None
        self._pulse_level = growth if growth is not None else _MAX_GROWTH
        self._pulse_serial += 1
        self._last_pulse_ts = time.time()
        previous_state = self._activity_state
        self._activity_kind = str(kind or 'status').casefold()
        self._activity_label = str(activity or kind or 'TELEMETRY').upper()[:28]
        self._activity_state = str(state or previous_state or 'FLIGHT').upper()[:28]
        self._state_changed = bool(previous_state and self._activity_state != previous_state)
        self._html_render_model = {'pulse_id': self._pulse_serial, 'stalled': False, 'status': 'TELEMETRY LIVE', 'kind': self._activity_kind, 'activity': self._activity_label, 'state': self._activity_state, 'state_changed': self._state_changed}
        if self._last_render_key != (self._pulse_level, False):
            self._redraw()

    def _redraw(self):
        cx = cy = _SIZE // 2
        stalled = time.time() - self._last_pulse_ts > _STALL_AFTER_S
        self._last_render_key = (self._pulse_level, stalled)
        self._html_render_model = {'pulse_id': self._pulse_serial, 'stalled': stalled, 'status': 'TELEMETRY STALLED' if stalled else 'TELEMETRY LIVE', 'kind': self._activity_kind, 'activity': self._activity_label, 'state': self._activity_state, 'state_changed': self._state_changed}

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        self._last_render_key = None
        self._redraw()
