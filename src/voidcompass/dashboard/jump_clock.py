"""5.6.9: the jump clock, timed from the game itself.

The game writes no journal event when the jump key is pressed: Status.json's
charging flags show it, StartJump follows during the countdown, Status' FsdJump
bit rises as the ship enters the tunnel, and FSDJump (or SupercruiseEntry) says
it has arrived. The clock notes those moments for each jump and learns from the
commander's own jumps how long each part takes, so the Navigation HUD can count
down to the real jump instead of guessing. Status moments use the file's own
write time; journal moments the time they were read (the watcher polls quickly
while a jump is under way).
"""

import json
import os
import statistics

KINDS = ("hyperspace", "supercruise")
# press -> tunnel, StartJump -> tunnel, tunnel -> arrival.
SEGMENTS = ("lead", "countdown", "tunnel")
# Anything outside these (a charge held by mass lock, a stalled load) is not learned from.
LIMITS = {"lead": (0.5, 40.0), "countdown": (0.0, 25.0), "tunnel": (0.5, 60.0)}
# StartJump to arrival in a commander's journals: 18-19 s in 931 of 953
# hyperspace jumps, 5 s in 107 of 113 supercruise entries.
TRANSIT = {"hyperspace": 18.5, "supercruise": 5.0}
KEEP = 9
# A charge or jump with no outcome after this long is forgotten.
STALE_S = 90.0
# The charging flag fell and no StartJump came: the charge was cancelled.
CANCEL_S = 2.0
# StartJump this far from the press-based prediction re-anchors the countdown.
REANCHOR_S = 1.5
# The FSD cooldown (Status' FsdCooldown bit), learned by what came before it.
AFTER = ("hyperspace", "supercruise", "drop", "other")
COOL_LIMITS = (1.0, 120.0)
# A jump, supercruise entry or drop this close to the bit rising caused it.
CAUSE_S = 8.0


class JumpClock:
    def __init__(self, samples=None, cooldown=None):
        self.cooldown = {after: [float(v) for v in (cooldown or {}).get(after) or [] if isinstance(v, (int, float))][-KEEP:]
                         for after in AFTER} if isinstance(cooldown, dict) else {after: [] for after in AFTER}
        self.recent = []
        self.cool = None
        self.samples = {kind: {segment: [] for segment in SEGMENTS} for kind in KINDS}
        for kind, rows in (samples or {}).items():
            if kind not in self.samples or not isinstance(rows, dict):
                continue
            for segment, values in rows.items():
                if segment in SEGMENTS and isinstance(values, list):
                    self.samples[kind][segment] = [float(v) for v in values if isinstance(v, (int, float))][-KEEP:]
        self.jump = None

    @classmethod
    def load(cls, path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                saved = json.load(handle)
                return cls(saved.get("samples"), saved.get("cooldown"))
        except (OSError, ValueError, AttributeError):
            return cls()

    def save(self, path):
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            temp = f"{path}.tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump({"samples": self.samples, "cooldown": self.cooldown}, handle)
            os.replace(temp, path)
        except OSError:
            pass

    def expected(self, kind, segment):
        values = self.samples.get(kind, {}).get(segment) or []
        return statistics.median(values) if values else None

    # --------------------------------------------------------------- moments
    def charging(self, kind, at):
        """Status: the drive is charging (the jump key was pressed)."""
        kind = kind if kind in KINDS else "supercruise"
        jump = self.jump
        if jump and jump.get("tunnel") and at - jump["tunnel"] < LIMITS["tunnel"][1]:
            return
        if jump and not jump.get("tunnel") and at - jump["seen"] < STALE_S and not self._cancelled(jump, at):
            # The hyperdrive bit can arrive a write later than the charging bit.
            if kind == "hyperspace":
                jump["kind"] = kind
            jump["dropped"] = None
            jump["seen"] = at
            return
        self.jump = {"kind": kind, "press": at, "start": None, "tunnel": None, "dropped": None, "seen": at}

    def charge_dropped(self, at):
        """Status: the charging flag fell (the countdown began, or a cancel)."""
        if self.jump and not self.jump.get("tunnel") and not self.jump.get("dropped"):
            self.jump["dropped"] = at

    def started(self, kind, at):
        """Journal: StartJump."""
        kind = kind if kind in KINDS else "hyperspace"
        jump = self.jump
        fresh = (not jump or jump.get("tunnel") or (jump["kind"] != kind and jump.get("start"))
                 or at - jump["seen"] > STALE_S or self._cancelled(jump, at))
        if fresh:
            jump = self.jump ={"kind": kind, "press": None, "start": None, "tunnel": None, "dropped": None, "seen": at}
        jump["kind"] = kind
        jump["start"] = at
        jump["dropped"] = None
        jump["seen"] = at

    def tunnel(self, at):
        """Status: the FsdJump bit rose; the ship is entering the jump."""
        jump = self.jump
        if not jump or jump.get("tunnel") or at - jump["seen"] > STALE_S:
            return
        jump["tunnel"] = at
        jump["seen"] = at
        if jump.get("press") is not None:
            self._learn(jump["kind"], "lead", at - jump["press"])
        if jump.get("start") is not None:
            self._learn(jump["kind"], "countdown", at - jump["start"])

    def arrived(self, kind, at):
        """Journal: FSDJump or SupercruiseEntry. Returns True if it learned something."""
        self._happened(kind, at)
        jump, self.jump = self.jump, None
        if not jump or jump["kind"] != kind or at - jump["seen"] > STALE_S:
            return False
        if jump.get("tunnel") is not None:
            self._learn(kind, "tunnel", at - jump["tunnel"])
        return True

    def cancel(self):
        self.jump = self.cool = None

    def dropped(self, at):
        """Journal: SupercruiseExit, which starts a cooldown of its own."""
        self._happened("drop", at)

    def cooling(self, at):
        """Status: the FsdCooldown bit rose."""
        self.cool = {"start": at}

    def cooled(self, at):
        """Status: the FsdCooldown bit fell. Returns True if it learned the length."""
        cool, self.cool = self.cool, None
        if not cool:
            return False
        low, high = COOL_LIMITS
        length = at - cool["start"]
        if not low <= length <= high:
            return False
        rows = self.cooldown[self._cause(cool["start"])]
        rows.append(round(length, 3))
        del rows[:-KEEP]
        return True

    def cool_view(self, now):
        """The cooldown for the HUD, as epoch milliseconds, or None."""
        cool = self.cool
        if not cool or now - cool["start"] > COOL_LIMITS[1] + 30:
            return None
        after = self._cause(cool["start"])
        rows = self.cooldown[after]
        ready = cool["start"] + statistics.median(rows) if rows else None
        return {"after": after, "start": int(round(cool["start"] * 1000)),
                "ready": int(round(ready * 1000)) if ready is not None else None, "exact": ready is not None}

    # ----------------------------------------------------------------- view
    def view(self, now):
        """What the HUD needs, as epoch milliseconds, or None between jumps."""
        jump = self.jump
        if not jump or now - jump["seen"] > STALE_S or self._cancelled(jump, now):
            return None
        kind = jump["kind"]
        lead, countdown = self.expected(kind, "lead"), self.expected(kind, "countdown")
        tunnel = self.expected(kind, "tunnel")
        jumped = jump.get("tunnel") is not None
        at = None
        if jumped:
            at = jump["tunnel"]
        else:
            by_press = jump["press"] + lead if jump.get("press") is not None and lead is not None else None
            by_start = jump["start"] + countdown if jump.get("start") is not None and countdown is not None else None
            # The press is read from Status' own write time, the more precise
            # anchor; a StartJump far from it means the charge was held.
            at = by_press if by_press is not None and (by_start is None or abs(by_start - by_press) <= REANCHOR_S) \
                else by_start
        arrive = None
        if at is not None and tunnel is not None:
            arrive = at + tunnel
        elif jump.get("start") is not None:
            arrive = jump["start"] + TRANSIT[kind]

        def ms(value):
            return int(round(value * 1000)) if value is not None else None

        return {
            "kind": kind,
            "press": ms(jump.get("press")),
            "start": ms(jump.get("start")),
            "jump": ms(at),
            "jumped": jumped,
            "arrive": ms(arrive),
            # The countdown comes from this commander's measured jumps.
            "exact": at is not None,
        }

    # -------------------------------------------------------------- private
    def _happened(self, kind, at):
        self.recent = (self.recent + [(kind, at)])[-4:]

    def _cause(self, start):
        # Status and the journal are read apart, so the cause may be noted
        # just before or just after the bit rises.
        near = [kind for kind, at in self.recent if abs(at - start) <= CAUSE_S]
        return near[-1] if near else "other"

    def _cancelled(self, jump, now):
        return bool(jump.get("dropped") and not jump.get("start") and not jump.get("tunnel")
                    and now - jump["dropped"] > CANCEL_S)

    def _learn(self, kind, segment, value):
        low, high = LIMITS[segment]
        if not low <= value <= high:
            return False
        rows = self.samples[kind][segment]
        rows.append(round(float(value), 3))
        del rows[:-KEEP]
        return True
