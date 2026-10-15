"""Galaxy Minimap overlay (5.5.3.7): the Milky Way in a corner of the screen,
drawn from the same Codex region map as the Galactic Atlas, with you on it.

The here and now: where you are (and the region's name), the trail of this
game session's jumps, and the route you've plotted, waypoint by waypoint, to
where it ends. Sol and the core for bearings. (The whole journey is the
Galactic Atlas's.) The page (web/galaxy_minimap) draws it; this keeps the
model.
"""
from __future__ import annotations

import math

from voidcompass.core import home_anchor, themes
from voidcompass.core.application_runtime import OverlayWindowState
from voidcompass.exploration.galactic_regions import find_region, region_names
from voidcompass.overlays import overlay_chrome

SIZES = (180, 240, 320)
DEFAULT_SIZE = 240
# "route" frames you, the trail and the route ahead (the default, 5.5.3.7).
VIEWS = ("route", "local", "galaxy")
# A long session's trail is thinned evenly to this many points (its shape
# reads the same; its last points are always kept).
TRAIL_POINTS = 2000
# The strip under the map: its height in design px at 100% text.
STRIP_PX = 40


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def minimap_options(config):
    """Overlay Studio's choices for the minimap."""
    config = config or {}
    size = _integer(config.get("galaxy_minimap_size"), DEFAULT_SIZE)
    view = str(config.get("galaxy_minimap_view") or "route").casefold()
    return {
        "size": size if size in SIZES else DEFAULT_SIZE,
        "view": view if view in VIEWS else "route",
        "route": bool(config.get("galaxy_minimap_route", True)),
        # The names of the regions it shows (5.5.3.7).
        "labels": bool(config.get("galaxy_minimap_labels", True)),
        # The whole trip from Spansh: your waypoint route, or the latest
        # neutron plot (5.5.3.7).
        "spansh": bool(config.get("galaxy_minimap_spansh", True)),
        # Where your sealed time capsules wait (5.5.3.7).
        "capsules": bool(config.get("galaxy_minimap_capsules", True)),
        # The region names' size (5.5.4): 0 follows the minimap's text size.
        "region_text": region_text_size(config.get("galaxy_minimap_region_text_percent")),
    }


def region_text_size(value):
    """A region-name size from Overlay Studio: 0 (the minimap's text size)
    or one of the Watcher's text sizes."""
    from voidcompass.overlays.heartbeat_hud import heartbeat_text_size
    return heartbeat_text_size(value)


def next_view(view):
    """The view after this one, for the minimap's view hotkey."""
    order = list(VIEWS)
    return order[(order.index(view) + 1) % len(order)] if view in order else order[0]


def minimap_text_scale(config):
    """The minimap's own text size (Overlay Studio), or all overlays' when 0:
    the same choices as the Watcher's (5.5.3.7)."""
    from voidcompass.overlays.heartbeat_hud import heartbeat_text_size
    own = heartbeat_text_size((config or {}).get("galaxy_minimap_text_scale_percent"))
    if own <= 0:
        own = _integer((config or {}).get("overlay_text_scale_percent"), 100)
    return max(75, min(200, own)) / 100.0


def _point(x, z):
    return [round(float(x), 1), round(float(z), 1)]


def session_trail(rows, limit=TRAIL_POINTS):
    """This session's arrivals as (x, z), thinned evenly to ``limit`` points
    when it's been a long one (the first and last are always kept)."""
    points = []
    for row in rows:
        try:
            points.append(_point(row[2], row[4]))
        except (TypeError, ValueError, IndexError):
            continue
    if len(points) <= limit:
        return points
    step = (len(points) - 1) / float(limit - 1)
    return [points[round(index * step)] for index in range(limit)]


def _region_name(x, z):
    found = find_region(x, 0.0, z)
    return found[1] if found else ""


# What each star on the route is good for (5.5.3.7): fuel from the scoopable
# classes; a neutron star's or white dwarf's jet boosts the drive (and bites).
SCOOPABLE = frozenset("KGBFOAM")


def star_kind(star_class):
    """'scoop', 'neutron', 'dwarf' or '' for a NavRoute StarClass."""
    star = str(star_class or "")
    if star in SCOOPABLE:
        return "scoop"
    if star == "N":
        return "neutron"
    if star.startswith("D"):
        return "dwarf"
    return ""


def plotted_route(entries, position=None, system=""):
    """The plotted route ahead (NavRoute.json's entries): from the system
    you're in to its end, as points, with its name, how far and how many
    jumps. None when there's no route."""
    stops = []
    for entry in entries or ():
        try:
            pos = [float(value) for value in entry.get("StarPos")]
        except (AttributeError, TypeError, ValueError):
            continue
        if len(pos) == 3:
            stops.append((str(entry.get("StarSystem") or ""), pos, star_kind(entry.get("StarClass"))))
    if len(stops) < 2:
        return None
    here = str(system or "").casefold()
    start = next((index for index, stop in enumerate(stops) if stop[0].casefold() == here), 0)
    ahead = stops[start:]
    if len(ahead) < 2:
        return None  # arrived
    end_name, end_pos = ahead[-1][0], ahead[-1][1]
    origin = position if position is not None else ahead[0][1]
    kinds = [stop[2] for stop in ahead]
    return {
        "points": [_point(stop[1][0], stop[1][2]) for stop in ahead],
        "stars": kinds,
        "name": end_name,
        "distance": round(math.dist([float(v) for v in origin], end_pos), 1),
        "jumps": len(ahead) - 1,
    }


# A very long trip is thinned to this many points (neutron stops and its end
# are always kept).
TRIP_POINTS = 1500


def _coords(value):
    """[x, y, z] from a waypoint's coords (a list, or a dict of x/y/z)."""
    if isinstance(value, dict):
        value = [value.get("x"), value.get("y"), value.get("z")]
    try:
        coords = [float(item) for item in value]
    except (TypeError, ValueError):
        return None
    return coords if len(coords) == 3 and all(math.isfinite(item) for item in coords) else None


def spansh_trip(waypoints=None, plot=None, position=None, system=""):
    """The whole trip ahead, beyond the leg plotted in game (5.5.3.7).

    From your waypoint route (what the Nav HUD follows; a Spansh neutron plot
    imported into it keeps its coordinates and neutron stops), or, without
    one, the latest neutron plot itself. The stops after the system you're
    in, or after the last one visited, to the end: points, which are neutron
    stars, the destination, how far and how many jumps. Stops without known
    coordinates are left out of the line. None when there's no trip ahead.
    """
    plot_rows = [row for row in ((plot or {}).get("waypoints") or ()) if isinstance(row, dict)]
    from_plot = {str(row.get("system") or "").casefold(): row for row in plot_rows}
    stops, source = [], "waypoints"
    for row in waypoints or ():
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        known = from_plot.get(name.casefold()) or {}
        stops.append({"name": name, "pos": _coords(row.get("coords")) or _coords(known.get("coords")),
                      "neutron": bool(row.get("neutron", known.get("neutron"))),
                      "jumps": row.get("jumps", known.get("jumps")), "visited": bool(row.get("visited"))})
    if len(stops) < 2:
        source = "neutron"
        stops = [{"name": str(row.get("system") or ""), "pos": _coords(row.get("coords")), "neutron": bool(row.get("neutron")),
                  "jumps": row.get("jumps"), "visited": False} for row in plot_rows]
    if len(stops) < 2:
        return None
    here = str(system or "").casefold()
    at = next((index for index, stop in enumerate(stops) if stop["name"].casefold() == here), -1)
    if at >= 0:
        ahead = stops[at + 1:]
    else:
        last_visited = max((index for index, stop in enumerate(stops) if stop["visited"]), default=-1)
        ahead = stops[last_visited + 1:]
    drawn = [stop for stop in ahead if stop["pos"] is not None]
    if not drawn:
        return None
    # The distance along the trip, from you (or its next stop).
    origin = _coords(position) or drawn[0]["pos"]
    distance, previous = 0.0, origin
    for stop in drawn:
        distance += math.dist(previous, stop["pos"])
        previous = stop["pos"]
    jumps = [_integer(stop["jumps"], -1) for stop in ahead]
    if len(drawn) > TRIP_POINTS:
        step = (len(drawn) - 1) / float(TRIP_POINTS - 1)
        keep = {round(index * step) for index in range(TRIP_POINTS)}
        drawn = [stop for index, stop in enumerate(drawn) if index in keep or stop["neutron"]]
    return {
        "points": [_point(stop["pos"][0], stop["pos"][2]) for stop in drawn],
        "neutron": [index for index, stop in enumerate(drawn) if stop["neutron"]],
        "name": ahead[-1]["name"],
        "distance": round(distance, 1),
        # Spansh's own count when every stop has one; otherwise a jump a stop.
        "jumps": sum(jumps) if jumps and min(jumps) >= 1 else len(ahead),
        "stops": len(ahead),
        "source": source,
    }


def build_minimap_model(rows, position=None, system="", route_entries=None, options=None, regions_visited=0, trip=None,
                        capsules=None, home=None):
    """The page's model. ``rows`` are this session's travel-history rows
    (oldest first, starting where the session began), ``position`` the ship's
    [x, y, z] when known, ``route_entries`` NavRoute.json's route."""
    options = dict(options or minimap_options({}))
    if position is None and rows:
        last = rows[-1]
        position, system = [last[2], last[3], last[4]], system or last[1]
    here = None
    if position is not None:
        x, y, z = (float(value) for value in position)
        here = {"x": round(x, 1), "z": round(z, 1), "system": str(system or ""),
                "region": _region_name(x, z), "from_sol": round(math.sqrt(x * x + y * y + z * z), 1)}
    # Your home (5.5.4): Sol unless you set another; the strip measures from it.
    home = dict(home or home_anchor.home({}))
    marker = {"name": str(home["name"]), "x": round(home["pos"][0], 1), "z": round(home["pos"][2], 1),
              "custom": bool(home.get("custom"))}
    if here is not None:
        here["from_home"] = round(math.dist((x, y, z), home["pos"]), 1)
    return {
        "here": here,
        "home": marker,
        "trail": session_trail(rows),
        "session_jumps": max(0, len(rows) - 1),
        "route": plotted_route(route_entries, position, system) if options["route"] else None,
        "trip": trip if options.get("spansh", True) else None,
        "capsules": [list(point) for point in (capsules or ())][:200] if options.get("capsules", True) else [],
        "regions_visited": int(regions_visited or 0),
        "regions_total": len(region_names()),
        "options": options,
    }


class GalaxyMinimapHUD:
    """Native window proxy for the HTML minimap; up while it is enabled."""

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._signature = None
        self._region_cache = {}
        self._html_render_model = build_minimap_model([], options=minimap_options(config))
        self.win = OverlayWindowState(root)
        self.win.geometry(overlay_chrome.position_geometry(
            _integer(config.get("galaxy_minimap_hud_x"), 40), _integer(config.get("galaxy_minimap_hud_y"), 600)))
        # session rows, every row, revision, position, system, route entries, trip, capsules
        self._last = ([], [], None, None, "", None, None, None)

    def _regions_visited(self, rows, revision):
        """How many of the 42 regions the journey has reached, counted once
        per travel-history revision (a few thousand lookups at most)."""
        if self._region_cache.get("revision") == revision:
            return self._region_cache["count"]
        seen = set()
        by_system = self._region_cache.setdefault("systems", {})
        for row in rows:
            key = str(row[1]).casefold()
            if key not in by_system:
                found = find_region(row[2], row[3], row[4])
                by_system[key] = found[0] if found else 0
            if by_system[key]:
                seen.add(by_system[key])
        self._region_cache.update(revision=revision, count=len(seen))
        return len(seen)

    def update(self, session_rows, all_rows=None, revision=None, position=None, system="", route_entries=None, trip=None,
               capsules=None):
        """This session's arrivals, the whole journey (only to count regions),
        where the ship is, the plotted route and the Spansh trip
        (``spansh_trip``). Rebuilt only when something changed."""
        session_rows = list(session_rows or [])
        all_rows = list(all_rows or session_rows)
        options = minimap_options(self.config)
        home = home_anchor.home(self.config)
        route_key = tuple(str((entry or {}).get("StarSystem") or "") for entry in (route_entries or ()))
        signature = (revision if revision is not None else len(all_rows), len(session_rows),
                     tuple(round(float(v), 1) for v in position) if position else None, str(system or ""),
                     route_key, tuple(sorted(options.items())),
                     (trip["source"], trip["name"], trip["stops"], len(trip["points"])) if trip else None,
                     tuple(tuple(point) for point in (capsules or ())), home["name"], tuple(home["pos"]))
        self._last = (session_rows, all_rows, revision, position, system, route_entries, trip, capsules)
        if signature == self._signature:
            return False
        self._signature = signature
        visited = self._regions_visited(all_rows, signature[0])
        self._html_render_model = build_minimap_model(
            session_rows, position=position, system=system, route_entries=route_entries,
            options=options, regions_visited=visited, trip=trip, capsules=capsules, home=home)
        return True

    def apply_settings(self):
        """Overlay Studio changed its size, view or route."""
        session_rows, all_rows, revision, position, system, route_entries, trip, capsules = self._last
        self._signature = None
        self.update(session_rows, all_rows, revision, position, system, route_entries, trip, capsules)

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass
