"""The watch rota (5.7.6): an optional crew that changes the watch with what
you're doing.

- Docked: Aster, who keeps the log and the paperwork.
- Scanning (FSS or DSS) or working a planet's surface: Axiom, the surveyor.
- Flying a plotted route: Meridian, the navigator.
- Deep, quiet space, far from home: the Watcher.

Anything else keeps whoever is on watch. Who takes each duty is yours to
choose (or "keep", to leave that duty to whoever has the watch). An activity has to hold for a while
before the watch changes, so a quick look at the FSS doesn't flip it, and the
watch never changes twice in quick succession. Choosing a companion yourself
holds your choice for a while before the rota takes over again.
"""

SETTLE_S = 45.0       # an activity holds this long before the watch changes
# 5.7.7: docking is plain at once; a quick look at the FSS isn't. Each duty settles in its own time.
SETTLE_BY_DUTY = {"docked": 10.0, "scanning": 45.0, "surface": 30.0, "route": 30.0, "deep": 60.0, "flight": 45.0}
MIN_GAP_S = 90.0      # the least time between two rota handovers (5.7.7: was three minutes, which felt dead)
HOLD_S = 300.0        # a companion you chose yourself keeps the watch this long (5 minutes)
DEEP_LY = 1000.0      # this far from home counts as deep space, unless you choose another
DEEP_CHOICES = (250, 500, 1000, 2000, 5000, 10000)

FSS_FOCUS = 9         # Status.json GuiFocus: the FSS
SAA_FOCUS = 10        # the DSS (surface probe) view

TICK_S = 5.0          # the deck looks again this often, even when Status.json is quiet
KEEP = "keep"         # a duty that leaves whoever is on watch

# Each duty, in the order it's checked, with who takes it unless you choose
# otherwise (Settings: the companion page, under Its thoughts).
DUTIES = (
    ("docked", "Docked", "aster"),
    ("scanning", "Scanning (FSS or DSS)", "axiom"),
    ("surface", "On a planet's surface", "axiom"),
    ("route", "On a plotted route", "meridian"),
    ("deep", "Deep space", "watcher"),
    # Flying with none of the above: the ship's own computer, Lyra (5.7.6).
    ("flight", "Ordinary flight", "lyra"),
)
DEFAULT_DUTIES = {duty: who for duty, _label, who in DUTIES}
CREW = ("watcher", "aster", "axiom", "meridian", "lyra")


def duty_key(duty):
    return f"crew_rota_{duty}"


def duties(config):
    """{duty: companion or KEEP}, from the commander's settings."""
    config = config or {}
    out = {}
    for duty, _label, default in DUTIES:
        value = str(config.get(duty_key(duty)) or default).casefold()
        out[duty] = value if value in CREW or value == KEEP else default
    return out


def deep_ly(config):
    """How far from home deep space starts, from the commander's setting."""
    try:
        value = int(float((config or {}).get("crew_rota_deep_ly") or DEEP_LY))
    except (TypeError, ValueError):
        value = int(DEEP_LY)
    return value if value in DEEP_CHOICES else int(DEEP_LY)


def duty_of(facts):
    """Which duty you're on (docked, scanning, surface, route, deep, flight) or None.

    facts: docked, gui_focus, on_planet, on_foot, in_srv, route_left, home_ly, deep_ly."""
    facts = facts or {}
    if facts.get("docked"):
        return "docked"
    if facts.get("gui_focus") in (FSS_FOCUS, SAA_FOCUS):
        return "scanning"
    if facts.get("on_planet") and (facts.get("on_foot") or facts.get("in_srv")):
        return "surface"
    flying = not (facts.get("on_foot") or facts.get("in_srv") or facts.get("on_planet"))
    try:
        route_left = int(facts.get("route_left") or 0)
    except (TypeError, ValueError):
        route_left = 0
    if flying and route_left > 0:
        return "route"
    try:
        far = float(facts.get("home_ly") or 0) >= float(facts.get("deep_ly") or DEEP_LY)
    except (TypeError, ValueError):
        far = False
    if flying and far:
        return "deep"
    # No fix on where we are yet: it could be deep space, so nobody's flight.
    if flying and facts.get("home_ly") is not None:
        return "flight"
    return None


def settle_for(facts):
    """How long the current activity has to hold before the watch changes."""
    return SETTLE_BY_DUTY.get(duty_of(facts), SETTLE_S)


def wanted(facts, rota_duties=None):
    """Who should have the watch for this activity, or None to keep whoever has it."""
    duty = duty_of(facts)
    if duty is None:
        return None
    who = (rota_duties or DEFAULT_DUTIES).get(duty, DEFAULT_DUTIES[duty])
    return None if who == KEEP else who


class Rota:
    """Decides when the watch changes. ``step`` returns who should take it, or None."""

    def __init__(self):
        self.candidate = None
        self.since = 0.0
        self.last_change = float("-inf")
        self.held_until = 0.0

    def hold(self, now):
        """You chose a companion yourself: the rota leaves it alone for a while."""
        self.held_until = now + HOLD_S
        self.candidate = None

    def release(self):
        """5.7.7: let the rota take over again now."""
        self.held_until = 0.0

    def step(self, facts, now, current, enabled=True, rota_duties=None):
        if not enabled or now < self.held_until:
            self.candidate = None
            return None
        target = wanted(facts, rota_duties)
        if target is None or target == current:
            self.candidate = None
            return None
        if target != self.candidate:
            self.candidate, self.since = target, now
            return None
        if now - self.since < settle_for(facts) or now - self.last_change < MIN_GAP_S:
            return None
        self.candidate = None
        self.last_change = now
        return target

    def status(self, facts, now, current, enabled=True, rota_duties=None):
        """5.7.7: what the rota is doing, for the companion page and the debug
        log: {state, duty, wanted, until, text}. States: off, holding, settled,
        waiting (the activity is settling), gap (too soon after the last change)."""
        duty = duty_of(facts)
        target = wanted(facts, rota_duties)
        names = {"watcher": "The Watcher", "aster": "Aster", "axiom": "Axiom", "meridian": "Meridian", "lyra": "Lyra"}
        label = dict((key, title) for key, title, _who in DUTIES).get(duty, "no duty")
        row = {"duty": duty, "wanted": target, "until": None}
        if not enabled:
            return dict(row, state="off", text="Rota off")
        if now < self.held_until:
            return dict(row, state="holding", until=self.held_until,
                        text=f"Holding your pick ({names.get(current, current)})")
        if target is None or target == current:
            return dict(row, state="settled", text=f"Rota: {label.lower()}, {names.get(current, current)} on watch"
                        if duty else f"Rota: {names.get(current, current)} on watch")
        if self.candidate == target:
            settle_at = self.since + settle_for(facts)
            gap_at = self.last_change + MIN_GAP_S
            if gap_at > settle_at and gap_at > now:
                return dict(row, state="gap", until=gap_at, text=f"Rota: {label.lower()}, {names.get(target, target)} next")
            return dict(row, state="waiting", until=max(settle_at, now),
                        text=f"Rota: {label.lower()}, {names.get(target, target)} takes over")
        # Not yet seen by a step: no countdown, so the page doesn't redraw on a ticking time.
        return dict(row, state="waiting", text=f"Rota: {label.lower()}, {names.get(target, target)} takes over")

    def changed(self, now):
        """The rota changed the watch: it waits before the next change."""
        self.last_change = now
