"""Shared distance-proportional route "pip line" used by the HUD and dashboard.

Draws the upcoming nav-route hops as a single horizontal line whose segment
lengths are proportional to jump distance, with a pip (dot) at each system
and a graceful fallback to plain tick marks when there isn't enough width
for legible dots. Modeled on SrvSurvey's PlotJumpInfo pip plotter.
"""

import math

SCOOPABLE_CLASSES = "KGBFOAM"


def _distance(a, b):
    if not a or not b:
        return None
    try:
        return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))
    except Exception:
        return None


def build_route_hops(current_coords, route_list, nav_route_entries, current_sys=None,
                      waypoint_manager=None, max_hops=12):
    """Returns (hops, truncated_count) for the upcoming route ahead of current position.

    Each hop is {"name": str, "dist": float|None, "scoopable": bool}, where
    "dist" is the LY distance from the previous point (current position for
    the first hop). Prefers the game's NavRoute.json data; falls back to
    unvisited custom waypoints when no in-game route is active.
    """
    route = list(route_list or [])
    entries = list(nav_route_entries or [])
    route_idx = -1
    if current_sys and current_sys != "---" and route:
        try:
            route_idx = route.index(current_sys)
        except ValueError:
            route_idx = -1

    if route_idx >= 0:
        upcoming_names = route[route_idx + 1:]
        upcoming_entries = entries[route_idx + 1:]
    else:
        upcoming_names = route
        upcoming_entries = entries

    hops = []
    prev_coords = current_coords
    total_upcoming = len(upcoming_names)
    for name, entry in zip(upcoming_names, upcoming_entries):
        coords = (entry or {}).get("StarPos")
        star_class = str((entry or {}).get("StarClass") or "").upper()
        hops.append({
            "name": name,
            "dist": _distance(prev_coords, coords),
            "scoopable": star_class in SCOOPABLE_CLASSES,
        })
        if coords:
            prev_coords = coords
        if len(hops) >= max_hops:
            break

    if not hops and waypoint_manager and getattr(waypoint_manager, "waypoints", None):
        pending = [wp for wp in waypoint_manager.waypoints if not wp.get("visited")]
        total_upcoming = len(pending)
        prev_coords = current_coords
        for wp in pending:
            coords = wp.get("coords")
            dist = waypoint_manager.get_distance(prev_coords, coords) if prev_coords and coords else None
            hops.append({"name": wp.get("name"), "dist": dist, "scoopable": False})
            if coords:
                prev_coords = coords
            if len(hops) >= max_hops:
                break

    truncated = max(0, total_upcoming - len(hops))
    return hops, truncated


def total_distance_text(hops, truncated=0):
    dists = [h["dist"] for h in hops if h.get("dist")]
    if not dists and not truncated:
        return ""
    total = sum(dists)
    suffix = "+" if truncated else ""
    return f"{total:,.1f}{suffix} LY"


def draw_pip_line(canvas, x1, x2, y, hops, theme, *, dot_radius=5, bg="#010101", min_seg_px=9):
    """Draws the proportional pip line for `hops` across [x1, x2] at height y.

    theme: dict with "accent" and "orange" hex colors.
    Degrades to plain tick marks (no dots) once segments get too thin to
    read as individual pips.
    """
    n = len(hops)
    if n == 0 or x2 <= x1:
        return
    width = x2 - x1
    raw_dists = [h.get("dist") for h in hops]
    total = sum(d for d in raw_dists if d)
    if not total:
        fracs = [(i + 1) / n for i in range(n)]
    else:
        filled = [d if d else (total / n) for d in raw_dists]
        cum = 0.0
        fracs = []
        for d in filled:
            cum += d
            fracs.append(min(1.0, cum / total))

    dense = (width / n) < min_seg_px
    prev_x = x1
    for i, (hop, frac) in enumerate(zip(hops, fracs)):
        nx = x1 + frac * width
        is_next = (i == 0)
        color = theme["accent"] if is_next else theme["orange"]
        dash = None if is_next else (4, 3)
        canvas.create_line(prev_x, y, nx, y, fill=color, width=3 if is_next else 2, dash=dash)
        if dense:
            tick_h = 7 if hop.get("scoopable") else 4
            canvas.create_line(nx, y - tick_h, nx, y + tick_h, fill=color, width=2)
        else:
            r = dot_radius if is_next else max(2, dot_radius - 1)
            canvas.create_oval(nx - r, y - r, nx + r, y + r, outline=color, width=2, fill=bg)
            if hop.get("scoopable"):
                canvas.create_arc(nx - r - 2, y - r - 2, nx + r + 2, y + r + 2, start=140, extent=80, style="arc", outline=color)
        prev_x = nx
