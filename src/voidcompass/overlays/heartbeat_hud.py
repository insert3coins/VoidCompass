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
from voidcompass.core import display_scale, themes
from voidcompass.overlays import overlay_chrome
from voidcompass.core.overlay_registry import OVERLAY_SPECS, TEXT_SIZES, overlay_text_scale, text_size_choice
from voidcompass.overlays.heartbeat_events import classify
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer
from voidcompass.overlays import watcher_mind

_STALL_AFTER_S = 15
# Enough history for the orb to catch up on a burst between two polls.
_EVENT_HISTORY = 24

ORB_SIZES = (54, 72, 96)
DEFAULT_ORB_SIZE = 54
EYE_COLORS = ("theme", "hal")
LIVELINESS = ("calm", "standard", "alive")

# Status.json flags the Watcher's mood reads (todo-watcher-life.md).
_FLAG_SCOOPING = 0x00000800
_FLAG_FSD_CHARGING = 0x00020000
_FLAG2_GLIDE = 0x00001000
_FLAG2_ON_FOOT = 0x00000001
_FLAG2_LOW_HEALTH = 0x00000080
_FLAG_LOW_FUEL = 0x00080000
_FLAG_OVERHEATING = 0x00100000
_FLAG_IN_DANGER = 0x00400000
_FLAG_INTERDICTED = 0x00800000


def orb_size(config):
    """The orb's window size in px, always one of ORB_SIZES."""
    try:
        size = int(float((config or {}).get("heartbeat_orb_size", DEFAULT_ORB_SIZE)))
    except (TypeError, ValueError):
        size = DEFAULT_ORB_SIZE
    return size if size in ORB_SIZES else DEFAULT_ORB_SIZE


def liveliness(config):
    """How alive the Watcher is between events: calm, standard or alive."""
    value = str((config or {}).get("heartbeat_liveliness") or "standard").casefold()
    return value if value in LIVELINESS else "standard"


def idle_motion(config):
    """Blinks, breathing and glances between events (on unless turned off)."""
    return bool((config or {}).get("heartbeat_idle_motion", True))


# The Watcher's own Frame rate in Overlay Studio (5.5.7); 0 is "same as all
# overlays". Lower is kinder to older PCs.
FRAME_RATES = (0, 60, 30, 24, 15)


def frame_rate_setting(config):
    """The Watcher's Frame rate as chosen: one of FRAME_RATES."""
    try:
        rate = int(float((config or {}).get("heartbeat_frame_rate", 0)))
    except (TypeError, ValueError):
        rate = 0
    return rate if rate in FRAME_RATES else 0


def frame_rate(config):
    """What the Watcher animates at: its own rate, or every overlay's."""
    return frame_rate_setting(config) or int(HtmlOverlayServer.frame_rate or 30)


THOUGHT_SIDES = ("auto", "left", "right")


def thought_side_setting(config):
    """Overlay Studio's Thought side: auto (toward the middle of the screen),
    left or right of the orb (5.5.3.5)."""
    value = str((config or {}).get("heartbeat_thought_side") or "auto").casefold()
    return value if value in THOUGHT_SIDES else "auto"


# The Watcher's text sizes, as a list rather than a number field (the field
# saved on every arrow step); since 5.5.4 every overlay's are the same list.
HEARTBEAT_TEXT_SIZES = TEXT_SIZES
heartbeat_text_size = text_size_choice


def heartbeat_text_scale(config):
    """The Watcher's own text size (5.5.3.5): its Studio percentage, or the
    text size of all overlays when that is 0."""
    return overlay_text_scale(config, "heartbeat_hud")


def place_thought(side, orb_x, orb_y, orb_px, width_px, height_px, bounds):
    """Where the window goes while a thought shows, in screen px: returns
    (side, x, y). The orb never moves. The words go on the side asked for
    when they fit on the orb's monitor, else the other side; the window grows
    up and down alike, unless that runs off the top or bottom of the screen,
    when it grows away from that edge instead (5.5.3.5: near an edge the
    words ran off the screen)."""
    y = orb_y - (height_px - orb_px) / 2.0
    if bounds:
        left, top, right, bottom = bounds
        fits = {"right": orb_x + orb_px + width_px <= right, "left": orb_x - width_px >= left}
        other = "left" if side == "right" else "right"
        if not fits.get(side) and fits[other]:
            side = other
        elif not fits.get(side):
            side = "right" if right - (orb_x + orb_px) >= orb_x - left else "left"
        y = max(top, min(y, bottom - height_px))
        # Always around the orb: the window holds it, however tall.
        y = max(orb_y + orb_px - height_px, min(y, orb_y))
    x = orb_x - width_px if side == "left" else orb_x
    return side, int(round(x)), int(round(y))


def vitals(flags, flags2=0, fuel_percent=None):
    """What the Watcher feels from one Status.json write."""
    try:
        flags = int(flags or 0)
    except (TypeError, ValueError):
        flags = 0
    try:
        flags2 = int(flags2 or 0)
    except (TypeError, ValueError):
        flags2 = 0
    try:
        fuel = None if fuel_percent is None else max(0.0, min(100.0, float(fuel_percent)))
    except (TypeError, ValueError):
        fuel = None
    return {
        # It anticipates: the drive charging, a glide down to a surface.
        "fsd_charging": bool(flags & _FLAG_FSD_CHARGING),
        "glide": bool(flags2 & _FLAG2_GLIDE),
        "fuel_percent": None if fuel is None else round(fuel, 1),
        "scooping": bool(flags & _FLAG_SCOOPING),
        "low_fuel": bool(flags & _FLAG_LOW_FUEL),
        "overheating": bool(flags & _FLAG_OVERHEATING),
        "danger": bool(flags & (_FLAG_IN_DANGER | _FLAG_INTERDICTED)),
    }


def overlay_directions(config, orb_x, orb_y, size):
    """Unit vectors from the orb to each enabled overlay's centre, so the
    eye can glance at the one an event concerns."""
    config = config or {}
    cx, cy = orb_x + size / 2.0, orb_y + size / 2.0
    directions = {}
    for spec in OVERLAY_SPECS:
        if spec.attr == "heartbeat_hud" or not spec.available:
            continue
        if not config.get(spec.enabled_key, spec.default_enabled):
            continue
        try:
            x = float(config.get(spec.x_key, spec.default_position[0]))
            y = float(config.get(spec.y_key, spec.default_position[1]))
        except (TypeError, ValueError):
            continue
        dx = x + spec.default_size[0] / 2.0 - cx
        dy = y + spec.default_size[1] / 2.0 - cy
        length = (dx * dx + dy * dy) ** .5
        if length > 1:
            directions[spec.attr] = [round(dx / length, 3), round(dy / length, 3)]
    return directions


def _memory_path(config):
    try:
        from voidcompass.core.config import get_active_profile, get_profile_file
        return get_profile_file(get_active_profile(config), "watcher_memory.json")
    except Exception:
        return None


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
        self._vitals = vitals(0)
        # Its inner voice and its memory of the commander (watcher_mind).
        self._mind_path = _memory_path(config)
        self.mind = watcher_mind.WatcherMind(self._mind_path, config)
        self._thought_seen = None
        # 5.5.4: its voice. The dashboard sets the listener (it speaks the
        # words) and says whether the voice is on.
        self.voice_listener = None
        self._spoken_id = None
        self._next_idle_thought = time.time() + 45
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
        try:
            self.mind.seen()
            self.mind.save()
        except Exception:
            pass
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
        changed = stalled != self._stalled
        now = time.time()
        if now >= self._next_idle_thought:
            self._next_idle_thought = now + 30
            if self.mind.tick(self._context()):
                changed = True
        # A thought's second beat, when it is due.
        if self.mind.follow_up():
            changed = True
        # Moved somewhere new (Overlay Studio or a drag): it notices.
        position = (self.config.get('heartbeat_hud_x'), self.config.get('heartbeat_hud_y'))
        if getattr(self, '_last_position', None) not in (None, position):
            if self.mind.note('moved'):
                changed = True
        self._last_position = position
        self.mind.save_if_due()
        # Its story moved on (5.5.3.5): tell the achievements.
        story = self.mind.story_progress()
        listener = getattr(self, 'story_listener', None)
        if story and callable(listener):
            try:
                listener(story)
            except Exception:
                pass
        # A thought arriving or dissolving redraws (and resizes) the window.
        current = self.mind.current()
        if (current or {}).get("id") != self._thought_seen:
            changed = True
        if changed:
            self._redraw()
        self._schedule_tick()

    def _context(self):
        """What the rest of the app knows, for its idle thoughts (the music
        playing, Galnet's latest); the dashboard sets the provider."""
        provider = getattr(self, 'context_provider', None)
        if not callable(provider):
            return {}
        try:
            return provider() or {}
        except Exception:
            return {}

    def _check_profile(self):
        """A commander switch gives the Watcher that commander's memory."""
        path = _memory_path(self.config)
        if path != self._mind_path:
            self.mind.seen()
            self.mind.save()
            self._mind_path = path
            active = self.mind.voice_active
            self.mind = watcher_mind.WatcherMind(path, self.config)
            self.mind.voice_active = active

    def poke(self):
        """The Watcher hotkey: it looks up and answers (5.5.3.2)."""
        if self.mind.poke(self._context()):
            self._redraw()
            return True
        return False

    def answer(self, answer):
        """An answer to its question (the answer hotkeys, or the Watcher
        page): by number (1 to 3) or by the answer's key (5.6.1)."""
        thought = self.mind.answer(answer)
        if thought:
            self._redraw()
        return thought

    def meet(self, card):
        """Another commander's Watcher, from a shared code (5.6.1)."""
        thought = self.mind.meet(card)
        if thought:
            self._redraw()
        return thought

    def reset(self):
        """The Watcher page's RESET: it forgets everything, and wakes again."""
        backup = self.mind.reset()
        self._redraw()
        return backup

    def set_voice_active(self, active):
        """Its voice switched on or off (5.5.4). Switched on, it may say its
        first word at once."""
        active = bool(active)
        if active == self.mind.voice_active:
            return
        self.mind.voice_active = active
        if active and self.mind.find_voice():
            self._redraw()

    def _speaks(self, thought):
        """Whether this thought is said aloud, by the Voice level setting."""
        if not self.mind.voice_active or not callable(self.voice_listener):
            return False
        level = str(self.config.get('watcher_voice_level') or 'every').casefold()
        if thought.get('topic') == 'voice_found':
            return True
        if thought.get('topic') == 'relay':
            return bool(thought.get('speak'))
        need = {'important': 2, 'sometimes': 1}.get(level, 0)
        return int(thought.get('importance') or 0) >= need

    def note(self, kind, fields=None):
        """Something Void Compass noticed that the Watcher may think about
        (an achievement, an unlogged Codex colour, a new region). The
        thought, when it had one."""
        thought = self.mind.note(kind, fields)
        if thought:
            self._redraw()
        return thought

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
            if activity in {'LoadGame', 'Commander'}:
                self._check_profile()
            self.mind.observe(str(activity or ''), detail if isinstance(detail, dict) else {})
        else:
            self._status_serial += 1
            if isinstance(detail, dict) and 'Flags' in detail:
                self._vitals = vitals(detail.get('Flags'), detail.get('Flags2'), detail.get('fuel_percent'))
                try:
                    flags2 = int(detail.get('Flags2') or 0)
                except (TypeError, ValueError):
                    flags2 = 0
                # 5.5.7: on foot, the health bar is how it knows you're in a fight.
                self.mind.vitals(self._vitals.get('fuel_percent'), self._vitals.get('scooping'),
                                 health=detail.get('Health'), low_health=bool(flags2 & _FLAG2_LOW_HEALTH),
                                 on_foot=bool(flags2 & _FLAG2_ON_FOOT), in_danger=self._vitals.get('danger'),
                                 vehicle=detail.get('fuel_vehicle') or '')
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
            'orb': {'size': orb_size(self.config), 'eye': eye_color(self.config),
                    'liveliness': liveliness(self.config), 'idle': idle_motion(self.config),
                    'frame_rate': frame_rate(self.config),
                    # What its story has done to the eye (5.6.1).
                    'story': self.mind.story_marks() if getattr(self, 'mind', None) is not None else {}},
            'vitals': dict(self._vitals),
            'personality': watcher_mind.personality(self.config),
            'overlays': overlay_directions(
                self.config, self._safe_int(self.config.get('heartbeat_hud_x'), 12),
                self._safe_int(self.config.get('heartbeat_hud_y'), 12), orb_size(self.config)),
            'memory': self._memory_summary(),
            'thought': self._thought_payload(),
        }

    def _memory_summary(self):
        mind = getattr(self, 'mind', None)
        if mind is None:
            return {}
        last = mind.memory.get('last_seen')
        death = mind.memory.get('last_death')
        now = time.time()
        return {
            'away_hours': round((now - float(last)) / 3600.0, 1) if last else None,
            'sessions': int(mind.memory.get('sessions') or 0),
            'recent_death': bool(death and now - float(death) < 1800),
            # The bond grown over sessions together (5.5.3.2): it warms the eye.
            'bond': mind.bond(),
        }

    def _thought_payload(self):
        mind = getattr(self, 'mind', None)
        thought = mind.current() if mind is not None else None
        self._thought_seen = (thought or {}).get('id')
        if not thought:
            return None
        if thought['id'] != self._spoken_id:
            self._spoken_id = thought['id']
            # A new thought: the local API's event stream hears it (5.5.7).
            listener = getattr(self, 'thought_listener', None)
            if callable(listener):
                try:
                    listener(thought)
                except Exception:
                    pass
            if self._speaks(thought):
                words = self.mind.spoken_words(thought)
                try:
                    try:
                        said = self.voice_listener(words, thought['id'], feel=thought.get('voice'))
                    except TypeError:
                        said = self.voice_listener(words, thought['id'])  # a listener without the feel (5.6.1)
                    spoken = bool(words) and bool(said)
                except Exception:
                    spoken = False
                self._voiced = (thought['id'], words == thought['text']) if spoken else None
        voiced = getattr(self, '_voiced', None) or (None, False)
        return {'id': thought['id'], 'text': thought['text'], 'script': thought.get('script') or thought['text'],
                # Said aloud (5.5.4): the page types it in time with the voice
                # once it says whole thoughts.
                'voice': voiced[0] == thought['id'],
                'voice_full': voiced[0] == thought['id'] and voiced[1],
                'mood': thought.get('mood') or '', 'side': self.thought_side(),
                'kind': thought.get('kind') or '', 'heading': thought.get('heading') or '',
                'style': watcher_mind.thought_style(self.config),
                # 5.6.1: a question to answer (the answer hotkeys, 1 to 3), and
                # a story moment the eye shows once.
                'question': thought.get('question'), 'effect': thought.get('effect') or ''}

    def thought_side(self):
        """The side asked for in Overlay Studio, or on Auto the side of the
        orb with room for them: toward the middle of the monitor the orb is on
        (any monitor, not just the main one), judged from the orb's centre.
        Moving the orb across the middle moves the next thought to the other
        side. The bridge still swaps sides if the words won't fit there."""
        chosen = thought_side_setting(self.config)
        if chosen != 'auto':
            return chosen
        x = self._safe_int(self.config.get('heartbeat_hud_x'), 12)
        y = self._safe_int(self.config.get('heartbeat_hud_y'), 12)
        centre_x = x + orb_size(self.config) * display_scale.monitor_scale(x, y) / 2
        bounds = display_scale.monitor_bounds(centre_x, y)
        if bounds:
            left, _top, right, _bottom = bounds
        else:
            try:
                left, right = 0, int(self.root.winfo_screenwidth())
            except Exception:
                left, right = 0, 1920
        return 'left' if centre_x > (left + right) / 2 else 'right'

    def apply_settings(self):
        """Studio changed the orb's size, eye colour, thoughts or nature."""
        self.mind.config = self.config
        self._redraw()

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        self._redraw()
