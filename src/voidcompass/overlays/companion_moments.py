"""What a companion's display shows of its own work (5.7.6).

Meridian's needle points to the next star while the drive charges on a route,
and home at rest, with home's distance on its sounding gauge and a wake for
each jump; Axiom's crystal lights a facet for each body scanned in this
system, and its map draws them; Aster's halo shows the pad when docking is
granted, and its watch bill the rota's duty. The mind already follows the
route and the system's scans: this adds the rest, for the overlay's model."""
import math
import time

# Sagittarius A*, the heart of the galaxy.
CORE = (25.21875, -20.90625, 25899.96875)
# Bodies drawn on Axiom's map of the system, nearest first.
MAP_BODIES = 48

# A granted pad stops showing once you've docked, given up, or after this long.
DOCK_HOLD_S = 600.0
_DOCK_OVER = {"Docked", "DockingCancelled", "DockingTimeout", "DockingDenied", "Undocked", "FSDJump",
              "CarrierJump", "SupercruiseEntry", "Died", "Shutdown"}


def heading_to(here, there):
    """Degrees clockwise from galactic north (towards the core) from here to there, or None."""
    try:
        x, _y, z = (float(value) for value in here)
        tx, _ty, tz = (float(value) for value in there)
    except (TypeError, ValueError):
        return None
    if abs(tx - x) < 1e-6 and abs(tz - z) < 1e-6:
        return None
    return round(math.degrees(math.atan2(tx - x, tz - z)) % 360.0, 1)


def headings(here, entries=(), system="", home=None):
    """5.7.6: Meridian's compass: the next star on the route, home and the
    core, as headings, and how far home is."""
    out = {"next": bearing(here, entries, system), "core": heading_to(here, CORE), "home": None, "home_ly": None}
    if home is not None:
        out["home"] = heading_to(here, home)
        try:
            out["home_ly"] = round(math.dist([float(v) for v in here], [float(v) for v in home]), 1)
        except (TypeError, ValueError):
            pass
    return out


def bearing(here, entries, system=""):
    """Heading from here to the next star on the plotted route, in degrees
    clockwise from galactic north (towards the core), or None.

    here: [x, y, z]; entries: NavRoute.json's Route rows ({StarSystem, StarPos})."""
    try:
        x, _y, z = (float(value) for value in here)
    except (TypeError, ValueError):
        return None
    rows = [row for row in entries or () if isinstance(row, dict) and isinstance(row.get("StarPos"), (list, tuple))]
    names = [str(row.get("StarSystem") or "").casefold() for row in rows]
    current = str(system or "").casefold()
    # The row after the one we're in; before the first jump, the route starts where we are.
    start = names.index(current) + 1 if current and current in names else 1 if len(rows) > 1 else 0
    for row in rows[start:]:
        try:
            nx, _ny, nz = (float(value) for value in row["StarPos"][:3])
        except (TypeError, ValueError):
            continue
        if abs(nx - x) < 1e-6 and abs(nz - z) < 1e-6:
            continue
        return round(math.degrees(math.atan2(nx - x, nz - z)) % 360.0, 1)
    return None


class Moments:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.body_count = None
        self.complete = False
        self.pad = None
        self.pad_at = None
        self.jumps = 0

    def observe(self, event, raw):
        raw = raw if isinstance(raw, dict) else {}
        if event in ("FSDJump", "CarrierJump"):
            self.body_count, self.complete = None, False
            # Meridian's wake: each jump, counted.
            self.jumps += 1
        elif event == "FSSDiscoveryScan":
            try:
                self.body_count = int(raw.get("BodyCount")) or None
            except (TypeError, ValueError):
                pass
        elif event == "FSSAllBodiesFound":
            self.complete = True
            try:
                self.body_count = int(raw.get("Count")) or self.body_count
            except (TypeError, ValueError):
                pass
        if event == "DockingGranted":
            try:
                self.pad, self.pad_at = int(raw.get("LandingPad")), self.clock()
            except (TypeError, ValueError):
                self.pad = None
        elif event in _DOCK_OVER:
            self.pad = None

    def payload(self, mind=None, context=None):
        """The model's ``moment``: route, scan and dock, each only while it
        applies; the headings and the watch from the deck's ``context``."""
        context = context if isinstance(context, dict) else {}
        out = {"jumps": self.jumps}
        left = getattr(mind, "_route_left", None)
        if left:
            out["route"] = {"left": int(left), "total": int(getattr(mind, "_route_total", None) or left),
                            "bearing": context.get("next")}
        compass = {key: context.get(key) for key in ("home", "home_ly", "core") if context.get(key) is not None}
        if compass:
            out["heading"] = compass
        if "rota" in context:
            out["watch"] = {"rota": bool(context.get("rota")), "duty": context.get("duty")}
        survey = getattr(mind, "_survey", None)
        if self.body_count:
            found = len(getattr(survey, "bodies", None) or {})
            out["scan"] = {"found": min(found, self.body_count), "total": self.body_count, "complete": self.complete}
        where = getattr(survey, "where", None) or {}
        if where:
            out.setdefault("scan", {"found": len(where), "total": 0, "complete": False})["bodies"] = [
                [round(distance, 1), kind] for distance, kind in sorted(where.values())[:MAP_BODIES]]
        if self.pad is not None and self.clock() - (self.pad_at or 0) < DOCK_HOLD_S:
            out["dock"] = {"pad": self.pad}
        return out
