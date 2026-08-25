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

    Each hop is {"name": str, "dist": float|None, "scoopable": bool|None,
    "star_class": str}, where
    "dist" is the LY distance from the previous point (current position for
    the first hop). A pending commander-authored profile route takes
    precedence; otherwise the game's NavRoute.json supplies the upcoming legs.
    """
    route = list(route_list or [])
    entries = list(nav_route_entries or [])
    waypoints = list(getattr(waypoint_manager, "waypoints", None) or [])
    pending = [wp for wp in waypoints if not wp.get("visited")]
    if pending:
        hops = []
        prev_coords = current_coords
        for wp in pending[:max_hops]:
            coords = wp.get("coords")
            dist = waypoint_manager.get_distance(prev_coords, coords) if prev_coords and coords else None
            hops.append({
                "name": wp.get("name"), "dist": dist,
                "scoopable": None, "star_class": "",
            })
            if coords:
                prev_coords = coords
        return hops, max(0, len(pending) - len(hops))

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
        star_class = str((entry or {}).get("StarClass") or "").strip()
        hops.append({
            "name": name,
            "dist": _distance(prev_coords, coords),
            "scoopable": star_class.upper() in SCOOPABLE_CLASSES,
            "star_class": star_class,
        })
        if coords:
            prev_coords = coords
        if len(hops) >= max_hops:
            break

    truncated = max(0, total_upcoming - len(hops))
    return hops, truncated


def build_route_track(current_coords, route_list, nav_route_entries, current_sys=None,
                      waypoint_manager=None):
    """Build the complete visual route, retaining completed and current pips.

    This is intentionally separate from :func:`build_route_hops`: callers use
    that upcoming-only slice for remaining-jump counts and distance, while the
    HUD uses this full track to prevent completed route geometry from
    disappearing and rescaling after every arrival.
    """
    route = list(route_list or [])
    entries = list(nav_route_entries or [])
    current_key = str(current_sys or "").strip().casefold()

    # A commander-authored profile route is deliberate and takes visual
    # precedence over a leftover Elite NavRoute snapshot. This keeps a newly
    # added manual waypoint on the HUD immediately while the game route remains
    # available again as soon as the profile plan is cleared.
    waypoints = list(getattr(waypoint_manager, "waypoints", None) or [])
    if waypoints:
        exact_current = next(
            (index for index, waypoint in enumerate(waypoints)
             if str(waypoint.get("name") or "").strip().casefold() == current_key),
            -1,
        ) if current_key else -1
        last_visited = max(
            (index for index, waypoint in enumerate(waypoints)
             if waypoint.get("visited")),
            default=-1,
        )
        current_index = exact_current if exact_current >= 0 else last_visited
        next_index = next(
            (index for index, waypoint in enumerate(waypoints)
             if not waypoint.get("visited")),
            -1,
        )
        hops = []
        previous_coords = current_coords if current_index < 0 else None
        for index, waypoint in enumerate(waypoints):
            coords = waypoint.get("coords")
            distance = None
            if previous_coords and coords:
                try:
                    distance = waypoint_manager.get_distance(previous_coords, coords)
                except Exception:
                    distance = None
            hops.append({
                "name": waypoint.get("name"),
                "dist": distance,
                "scoopable": None,
                "star_class": "",
                "completed": bool(waypoint.get("visited")),
                "current": index == current_index,
                "next": index == next_index,
            })
            if coords:
                previous_coords = coords
        return {
            "hops": hops,
            "origin_current": current_index < 0,
            "source": "waypoints",
        }

    if route:
        route_idx = -1
        if current_key:
            route_idx = next(
                (index for index, name in enumerate(route)
                 if str(name or "").strip().casefold() == current_key),
                -1,
            )
        # When the current system is present, route[0] is the fixed visual
        # origin and every later system is one jump pip. Some Frontier route
        # snapshots contain only upcoming systems; in that case CURRENT is the
        # origin and all supplied entries remain pending.
        first_index = 1 if route_idx >= 0 else 0
        previous_coords = (
            (entries[0] or {}).get("StarPos")
            if first_index == 1 and entries else current_coords
        )
        hops = []
        for route_index in range(first_index, len(route)):
            entry = entries[route_index] if route_index < len(entries) else {}
            entry = entry if isinstance(entry, dict) else {}
            coords = entry.get("StarPos")
            star_class = str(entry.get("StarClass") or "").strip()
            hops.append({
                "name": route[route_index],
                "dist": _distance(previous_coords, coords),
                "scoopable": star_class.upper() in SCOOPABLE_CLASSES,
                "star_class": star_class,
                "completed": route_idx >= 0 and route_index <= route_idx,
                "current": route_idx >= 0 and route_index == route_idx,
                "next": (
                    route_index == route_idx + 1
                    if route_idx >= 0 else route_index == first_index
                ),
            })
            if coords:
                previous_coords = coords
        return {
            "hops": hops,
            "origin_current": route_idx in (-1, 0),
            "source": "game",
        }

    return {"hops": [], "origin_current": True, "source": "none"}


def total_distance_text(hops, truncated=0):
    dists = [h["dist"] for h in hops if h.get("dist")]
    if not dists and not truncated:
        return ""
    total = sum(dists)
    suffix = "+" if truncated else ""
    return f"{total:,.1f}{suffix} LY"


def pip_layout(x1, x2, hops, *, min_seg_px=9):
    """Return the same distance-proportional geometry used by the renderer."""
    n = len(hops)
    if n == 0 or x2 <= x1:
        return [], False
    width = x2 - x1
    raw_dists = [hop.get("dist") for hop in hops]
    total = sum(distance for distance in raw_dists if distance)
    if not total:
        fractions = [(index + 1) / n for index in range(n)]
    else:
        filled = [distance if distance else (total / n) for distance in raw_dists]
        layout_total = sum(filled)
        cumulative = 0.0
        fractions = []
        for distance in filled:
            cumulative += distance
            fractions.append(min(1.0, cumulative / layout_total))
    positions = [x1 + (fraction * width) for fraction in fractions]
    return positions, (width / n) < min_seg_px


def draw_pip_line(canvas, x1, x2, y, hops, theme, *, dot_radius=5, bg="#010101", min_seg_px=9):
    """Draws the proportional pip line for `hops` across [x1, x2] at height y.

    theme: dict with "accent" and "orange" hex colors.
    Degrades to a clean micro-pip rail once segments get too thin to read as
    individual full-size pips.
    """
    n = len(hops)
    if n == 0 or x2 <= x1:
        return
    positions, dense = pip_layout(x1, x2, hops, min_seg_px=min_seg_px)
    stateful = any(
        any(key in hop for key in ("completed", "current", "next"))
        for hop in hops
    )

    def hop_style(index, hop):
        is_current = stateful and bool(hop.get("current"))
        is_completed = stateful and bool(hop.get("completed"))
        is_next = bool(hop.get("next")) if stateful else index == 0
        if is_current:
            color = theme["accent"]
        elif is_completed:
            color = theme.get("completed", theme["accent"])
        elif is_next:
            color = theme.get("next", theme["orange"]) if stateful else theme["accent"]
        else:
            color = theme.get("pending", theme["orange"])
        return is_current, is_completed, is_next, color

    if dense:
        # A long route is an overview instrument, not a compressed comb of
        # systems. Every hop still contributes to the fixed proportional
        # geometry and progress calculation, while a small bank of readable
        # cells shows completed distance, current position and what remains.
        if stateful:
            current_index = next(
                (index for index, hop in enumerate(hops) if hop.get("current")),
                -1,
            )
            last_completed = max(
                (index for index, hop in enumerate(hops) if hop.get("completed")),
                default=-1,
            )
            progress_index = current_index if current_index >= 0 else last_completed
            progress_x = positions[progress_index] if progress_index >= 0 else x1
        else:
            current_index = -1
            progress_x = x1

        width = x2 - x1
        cell_count = max(10, min(18, int(round(width / 28.0))))
        gap = 2.0
        cell_width = (width - (gap * (cell_count - 1))) / cell_count
        pending_color = theme.get("pending", theme["orange"])
        completed_color = theme.get("completed", theme["accent"])
        for cell in range(cell_count):
            cell_x1 = x1 + (cell * (cell_width + gap))
            cell_x2 = cell_x1 + cell_width
            canvas.create_rectangle(
                cell_x1, y - 2, cell_x2, y + 2,
                fill=pending_color, outline="",
            )
            if progress_x > cell_x1:
                fill_x2 = min(cell_x2, progress_x)
                if fill_x2 > cell_x1:
                    canvas.create_rectangle(
                        cell_x1, y - 2, fill_x2, y + 2,
                        fill=completed_color, outline="",
                    )

        if current_index >= 0:
            radius = 3
            canvas.create_oval(
                progress_x - radius, y - radius,
                progress_x + radius, y + radius,
                fill=bg, outline=theme["accent"], width=2,
            )
            canvas.create_oval(
                progress_x - 1, y - 1,
                progress_x + 1, y + 1,
                fill=theme["accent"], outline="",
            )

        if current_index != n - 1:
            radius = 3
            canvas.create_polygon(
                x2, y - radius, x2 + radius, y,
                x2, y + radius, x2 - radius, y,
                fill=bg, outline=theme["orange"], width=1,
            )
        return

    prev_x = x1
    for i, (hop, nx) in enumerate(zip(hops, positions)):
        is_current, is_completed, is_next, color = hop_style(i, hop)
        dash = (4, 3) if stateful and not (is_completed or is_current or is_next) else None
        if not stateful and not is_next:
            dash = (4, 3)
        line_width = 3 if is_current or (is_next and not stateful) else 2
        canvas.create_line(prev_x, y, nx, y, fill=color, width=line_width, dash=dash)
        if is_current:
            r = dot_radius + 1
        elif is_next:
            r = dot_radius
        else:
            r = max(2, dot_radius - 1)
        canvas.create_oval(
            nx - r, y - r, nx + r, y + r,
            outline=color, width=3 if is_current else 2, fill=bg,
        )
        if is_current:
            canvas.create_oval(
                nx - 1.5, y - 1.5, nx + 1.5, y + 1.5,
                fill=color, outline="",
            )
        if hop.get("scoopable"):
            canvas.create_arc(nx - r - 2, y - r - 2, nx + r + 2, y + r + 2, start=140, extent=80, style="arc", outline=color)
        prev_x = nx
