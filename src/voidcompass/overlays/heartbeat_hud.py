"""HeartbeatHUD — the journal watcher orb.

A HAL 9000-style eye that watches every journal event and every Status.json
write. Each journal event falls into the orb as a mote in its own colour, and
the notable ones play their own effect (a jump streaks stars out of the
pupil, a discovery scan rings out through the bezel, combat turns the iris
red); heartbeat_events.py decides which. Status.json writes, the steadiest
signal the game gives, only run a small blip round the bezel.

If nothing arrives for a while the orb reports the feed as stalled: the
galaxy in its iris stops turning and a small red dot lights on the bezel.
The eye itself stays lit, because a quiet game is not a broken link.

This class only keeps the model; web/heartbeat draws it.
"""
from collections import deque
import time

from voidcompass.core.application_runtime import OverlayWindowState
from voidcompass.core import themes
from voidcompass.overlays import overlay_chrome
from voidcompass.overlays.heartbeat_events import classify

_STALL_AFTER_S = 15
# Enough history for the orb to catch up on a burst between two polls.
_EVENT_HISTORY = 24

ORB_SIZES = (54, 72, 96)
DEFAULT_ORB_SIZE = 54
EYE_COLORS = ("theme", "hal")


def orb_size(config):
    """The orb's window size in px, always one of ORB_SIZES."""
    try:
        size = int(float((config or {}).get("heartbeat_orb_size", DEFAULT_ORB_SIZE)))
    except (TypeError, ValueError):
        size = DEFAULT_ORB_SIZE
    return size if size in ORB_SIZES else DEFAULT_ORB_SIZE


def eye_color(config):
    value = str((config or {}).get("heartbeat_eye_color") or "theme").casefold()
    return value if value in EYE_COLORS else "theme"


class HeartbeatHUD:

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._pulse_serial = 0
        self._status_serial = 0
        self._event_serial = 0
        self._events = deque(maxlen=_EVENT_HISTORY)
        self._last_pulse_ts = time.time()
        self._activity_kind = 'startup'
        self._activity_label = 'LINK READY'
        self._activity_state = 'STARTUP'
        self._state_changed = False
        self._stalled = False
        self._tick_job = None
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._html_render_model = {}
        self._redraw()
        self.win = OverlayWindowState(root)
        screen_h = root.winfo_screenheight()
        size = orb_size(config)
        x = self._safe_int(config.get('heartbeat_hud_x'), 12)
        y = self._safe_int(config.get('heartbeat_hud_y'), max(12, screen_h - size - 12))
        self.win.geometry(overlay_chrome.position_geometry(x, y))
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

    def _schedule_tick(self):
        self._tick_job = self.win.call_later(750, self._tick)

    def _tick(self):
        stalled = time.time() - self._last_pulse_ts > _STALL_AFTER_S
        if stalled != self._stalled:
            self._redraw()
        self._schedule_tick()

    def pulse(self, kind='status', activity=None, state=None, detail=None):
        """Record one journal event or Status.json write for the orb."""
        self._pulse_serial += 1
        self._last_pulse_ts = time.time()
        previous_state = self._activity_state
        self._activity_kind = str(kind or 'status').casefold()
        self._activity_label = str(activity or kind or 'TELEMETRY').upper()[:28]
        self._activity_state = str(state or previous_state or 'FLIGHT').upper()[:28]
        self._state_changed = bool(previous_state and self._activity_state != previous_state)
        if self._activity_kind == 'journal':
            self._event_serial += 1
            self._events.append({'seq': self._event_serial, **classify(activity, detail)})
        else:
            self._status_serial += 1
        self._redraw()

    def _redraw(self):
        self._stalled = time.time() - self._last_pulse_ts > _STALL_AFTER_S
        self._html_render_model = {
            'pulse_id': self._pulse_serial,
            'stalled': self._stalled,
            'status': 'TELEMETRY STALLED' if self._stalled else 'TELEMETRY LIVE',
            'kind': self._activity_kind,
            'activity': self._activity_label,
            'state': self._activity_state,
            'state_changed': self._state_changed,
            'status_seq': self._status_serial,
            'events': list(self._events),
            'orb': {'size': orb_size(self.config), 'eye': eye_color(self.config)},
        }

    def apply_settings(self):
        """Studio changed the orb's size or eye colour."""
        self._redraw()

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        self._redraw()
