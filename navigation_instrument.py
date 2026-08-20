"""State vocabulary and short-lived event overlays for the Navigation HUD.

Sustained state geometry lives in :mod:`navigation_state_indicator`.  This
module contains only the shared timing vocabulary and the intentionally small
journal-event layer; it does not own a second fallback indicator.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class StateScene:
    """Visual language for one sustained cockpit state."""

    family: str
    period: float
    packets: int = 1
    segments: int = 4
    intensity: float = 0.68


@dataclass(frozen=True)
class EventScene:
    """Short response layered over the sustained state."""

    family: str
    direction: str = "outward"


_DEFAULT_STATE = StateScene("vector", 58.0, packets=2)


STATE_SCENES = {
    # Ordinary travel uses the bootloader's route-solution language.
    "flight": StateScene("vector", 58.0, packets=2),
    "supercruise": StateScene("route", 30.0, packets=3, segments=5, intensity=0.78),
    "fighter": StateScene("vector", 40.0, packets=3, intensity=0.78),
    "exploration": StateScene("scope", 72.0, packets=2, segments=5),

    # Passive modes retain visible life without pretending the ship is moving.
    "docked": StateScene("readiness", 92.0, packets=1, segments=5, intensity=0.55),
    "landed": StateScene("horizon", 84.0, packets=1, segments=4, intensity=0.58),
    "surface_vehicle": StateScene("terrain", 46.0, packets=2, segments=4),
    "on_foot": StateScene("terrain", 66.0, packets=1, segments=4, intensity=0.58),
    "scanner": StateScene("scope", 42.0, packets=2, segments=5, intensity=0.82),
    "map": StateScene("plot", 68.0, packets=2, segments=5, intensity=0.62),
    "combat": StateScene("alert", 26.0, packets=2, segments=4, intensity=0.86),

    # Vehicle hand-offs use the readiness cells from the startup sequence.
    "vehicle_deploy": StateScene("handoff", 38.0, packets=2, segments=4),
    "vehicle_board": StateScene("handoff", 44.0, packets=2, segments=4),
    "vehicle_switch": StateScene("handoff", 40.0, packets=2, segments=4),

    # These states own stronger bespoke motion in the state indicator. Listing
    # them here prevents the ordinary flight stream being painted underneath.
    "fsd_lock": StateScene("dedicated", 26.0, packets=0),
    "asteroid_field": StateScene("dedicated", 54.0, packets=0, intensity=0.72),
    "fsd_charge": StateScene("dedicated", 12.0, packets=0, segments=5, intensity=0.9),
    "fsd_cooldown": StateScene("dedicated", 24.0, packets=0),
    "jump": StateScene("dedicated", 9.0, packets=0, intensity=0.9),
    "arrival": StateScene("dedicated", 20.0, packets=0),
    "supercruise_overcharge": StateScene("dedicated", 7.0, packets=0, intensity=0.92),
    "carrier_transit": StateScene("dedicated", 16.0, packets=0, intensity=0.9),
    "carrier_arrival": StateScene("dedicated", 34.0, packets=0),
    "orbital_approach": StateScene("dedicated", 24.0, packets=0),
    "glide": StateScene("dedicated", 9.0, packets=0, intensity=0.88),
    "surface_approach": StateScene("dedicated", 24.0, packets=0),
    "surface_hold": StateScene("dedicated", 76.0, packets=0, intensity=0.55),
    "surface_departure": StateScene("dedicated", 24.0, packets=0),
    "orbital_departure": StateScene("dedicated", 20.0, packets=0),
}


def state_scene(profile):
    """Return the visual scene for a Navigation HUD motion profile."""

    return STATE_SCENES.get(str(profile or "flight"), _DEFAULT_STATE)


_EVENT_FAMILIES = {
    "boot": {"wake"},
    "route": {"route_set", "route_clear", "route_target", "route_divert"},
    "charge": {"jump_charge"},
    "supercruise": {"supercruise_enter", "supercruise_drop", "supercruise_exit"},
    "arrival": {
        "arrival", "arrival_neutron", "arrival_white_dwarf",
        "arrival_valuable", "carrier_arrival", "planet_clear",
    },
    "docking": {"dock", "dock_request", "dock_denied", "undock"},
    "surface": {"touchdown", "liftoff", "body_approach"},
    "vehicle": {"vehicle_deploy", "vehicle_board", "vehicle_switch"},
    "scope": {
        "honk", "fss_progress", "fss_signal", "body_scan", "signals",
        "valuable_discovery", "first_discovery", "footfall_candidate", "codex",
    },
    "clearance": {"data_sale"},
    "resource": {
        "prospector_scan", "prospector_rich", "prospector_core",
        "mining_refined",
    },
    "signal": {"signal_drop"},
    "hazard": {"warning", "interdiction"},
    "recovery": {"interdiction_clear"},
}


_EVENT_LOOKUP = {
    kind: family
    for family, kinds in _EVENT_FAMILIES.items()
    for kind in kinds
}


def event_scene(kind):
    """Return a bounded scene for a live Navigation HUD journal pulse."""

    kind = str(kind or "")
    family = _EVENT_LOOKUP.get(kind, "pulse")
    direction = {
        "route": "forward",
        "charge": "inward",
        "supercruise": "outward" if kind == "supercruise_exit" else "inward",
        "arrival": "outward",
        "docking": "inward" if kind != "undock" else "outward",
        "surface": "up" if kind == "liftoff" else "down",
        "vehicle": "inward" if kind == "vehicle_board" else "outward",
        "clearance": "outward",
        "recovery": "outward",
    }.get(family, "outward")
    return EventScene(family, direction=direction)


class NavigationEventRenderer:
    """Draw only brief, non-duplicated journal responses over the state."""

    def __init__(self, canvas, mix_colour):
        self.canvas = canvas
        self.mix_colour = mix_colour

    @staticmethod
    def _smooth(value):
        value = max(0.0, min(1.0, float(value)))
        return value * value * (3.0 - (2.0 * value))

    def _line(self, *coords, colour, width=1, tags="nav_event_motion", smooth=False):
        if width > 1:
            self.canvas.create_line(
                *coords, fill="#010101", width=width + 2,
                tags=tags, smooth=smooth,
            )
        self.canvas.create_line(
            *coords, fill=colour, width=width,
            tags=tags, smooth=smooth,
        )

    def _dot(self, x, y, colour, radius=1.2, tags="nav_event_motion"):
        halo = radius + 1.2
        self.canvas.create_oval(
            x - halo, y - halo, x + halo, y + halo,
            fill="#010101", outline="", tags=tags,
        )
        self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill=colour, outline="", tags=tags,
        )

    def _ship(self, x, y, colour, tags, scale=1.0, carrier=False, fighter=False):
        if carrier:
            self.canvas.create_polygon(
                x - (13 * scale), y - (3 * scale),
                x + (8 * scale), y - (3 * scale),
                x + (13 * scale), y,
                x + (8 * scale), y + (3 * scale),
                x - (13 * scale), y + (3 * scale),
                x - (9 * scale), y,
                fill="#010101", outline=colour, width=1, tags=tags,
            )
            self._line(
                x - (7 * scale), y, x + (7 * scale), y,
                colour=self.mix_colour(colour, 0.65), tags=tags,
            )
            return
        if fighter:
            points = (
                x + (6 * scale), y,
                x - (5 * scale), y - (4 * scale),
                x - (2 * scale), y,
                x - (5 * scale), y + (4 * scale),
            )
        else:
            points = (
                x + (6 * scale), y,
                x - (4 * scale), y - (4 * scale),
                x - (1 * scale), y,
                x - (4 * scale), y + (4 * scale),
            )
        self.canvas.create_polygon(
            *points, fill="#010101", outline=colour,
            width=1, tags=tags,
        )
    def _bounds(self, model):
        return (
            model["scene_x1"] + 8,
            model["scene_x2"] - 8,
            model["scene_y"],
            model["scene_top"],
            model["scene_bottom"],
        )

    def draw_event(self, model, event, progress, palette, tags="nav_event_motion"):
        kind = str(event.get("kind") or "")
        if kind in {"fuel", "boost"}:
            return
        scene = event_scene(kind)
        colour = palette.get(str(event.get("tone") or "accent"), palette["accent"])
        dim = self.mix_colour(colour, 0.52)
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        eased = self._smooth(progress)

        if scene.family == "route":
            offsets = (2, -2, 1, -3, 2)
            if kind == "route_divert":
                offsets = (2, -2, 1, 5, -3)
            points = [
                (x1 + ((x2 - x1) * index / 4), y + offsets[index])
                for index in range(5)
            ]
            self._line(*[v for point in points for v in point],
                       colour=dim, width=1, smooth=True, tags=tags)
            route_progress = 1.0 - eased if kind == "route_clear" else eased
            x = x1 + ((x2 - x1) * route_progress)
            if kind == "route_target":
                radius = 3 + (math.sin(progress * math.pi) * 3)
                self.canvas.create_oval(
                    x - radius, y - radius,
                    x + radius, y + radius,
                    fill="", outline=colour, width=1, tags=tags,
                )
            else:
                self._ship(x, y - 1, colour, tags, scale=0.72)
            for px, py in points:
                reached = px <= x if kind != "route_clear" else px >= x
                self._dot(px, py, colour if reached else dim, 1, tags)
            return

        if scene.family == "charge":
            count = 8
            for index in range(count):
                amount = (index + 0.5) / count
                left = x1 + ((center - x1) * amount)
                right = x2 - ((x2 - center) * amount)
                active = amount <= eased
                self._line(left - 4, top, left + 4, top,
                           colour=colour if active else dim,
                           width=2 if active else 1, tags=tags)
                self._line(right - 4, bottom, right + 4, bottom,
                           colour=colour if active else dim,
                           width=2 if active else 1, tags=tags)
            return

        if scene.family == "supercruise":
            # Entry opens a forward aperture; a destination drop compresses
            # it without claiming normal-space arrival; exit releases the
            # gate outward.  These three events no longer share a generic wipe.
            opening = kind == "supercruise_exit"
            travel = eased if opening else 1.0 - eased
            spread = 5 + (travel * min(90, (x2 - x1) * 0.24))
            for side in (-1, 1):
                gate_x = center + (side * spread)
                inward = gate_x - (side * 7)
                self._line(
                    gate_x, top, gate_x, bottom,
                    inward, y,
                    colour=colour, width=2, tags=tags,
                )
            if kind == "supercruise_enter":
                for index in range(3):
                    local = (eased + (index / 3)) % 1.0
                    x = x1 + ((x2 - x1) * local)
                    self._line(max(x1, x - 12), y + (index - 1) * 2, x, y + (index - 1) * 2,
                               colour=dim, tags=tags)
            elif kind == "supercruise_drop":
                self.canvas.create_polygon(
                    center, y - 5, center + 6, y,
                    center, y + 5, center - 6, y,
                    fill="", outline=colour, width=1, tags=tags,
                )
            return

        if scene.family == "arrival":
            if kind == "planet_clear":
                horizon = max(3.0, (1.0 - eased) * min(80, (x2 - x1) * 0.22))
                self.canvas.create_arc(
                    center - horizon, y - 1,
                    center + horizon, bottom + 5,
                    start=12, extent=156, style="arc",
                    outline=dim, width=1, tags=tags,
                )
                for side in (-1, 1):
                    x = center + (side * (8 + (eased * min(100, (x2 - x1) * 0.28))))
                    self._line(x - (side * 10), y, x, y,
                               colour=colour, width=2, tags=tags)
                return
            if kind == "carrier_arrival":
                self._ship(center, y, colour, tags, carrier=True, scale=0.82)
                for side in (-1, 1):
                    x = center + (side * (14 + (eased * min(120, (x2 - x1) * 0.33))))
                    self._line(x, top, x, bottom,
                               colour=colour, width=2, tags=tags)
                return
            radius_x = 6 + (eased * min(120, (x2 - x1) * 0.34))
            radius_y = 2 + (eased * 5)
            self.canvas.create_oval(
                center - radius_x, y - radius_y,
                center + radius_x, y + radius_y,
                fill="", outline=colour, width=2 if progress < 0.5 else 1,
                tags=tags,
            )
            if kind == "arrival_neutron":
                self._line(center - radius_x, top, center + radius_x, bottom,
                           colour=dim, width=2, tags=tags)
            elif kind == "arrival_white_dwarf":
                self._line(center, top - 1, center, bottom + 1,
                           colour=colour, width=2, tags=tags)
            elif kind in {"arrival_valuable", "valuable_discovery"}:
                self.canvas.create_polygon(
                    center, y - 5, center + 9, y,
                    center, y + 5, center - 9, y,
                    fill="", outline=colour, width=1, tags=tags,
                )
            return

        if scene.family == "docking":
            if kind == "dock_denied":
                spread = 10 + (eased * min(100, (x2 - x1) * 0.28))
                for side in (-1, 1):
                    x = center + (side * spread)
                    self._line(x - 4, top, x + 4, bottom,
                               colour=colour, width=2, tags=tags)
                    self._line(x - 4, bottom, x + 4, top,
                               colour=colour, width=2, tags=tags)
                return
            direction = 1.0 - eased if scene.direction == "outward" else eased
            spread = 8 + ((1.0 - direction) * min(80, (x2 - x1) * 0.2))
            for side in (-1, 1):
                x = center + (side * spread)
                inward = x - (side * 7)
                self._line(x, top, x, bottom, inward, top,
                           colour=colour, width=2, tags=tags)
            return

        if scene.family == "surface":
            travel = eased if scene.direction == "down" else 1.0 - eased
            gate_y = top + ((bottom - top) * travel)
            for side in (-1, 1):
                x = center + (side * 24)
                self._line(x - 6, gate_y, x + 6, gate_y,
                           colour=colour, width=2, tags=tags)
            return

        if scene.family == "vehicle":
            spread = 7 + (eased * min(70, (x2 - x1) * 0.2))
            if scene.direction == "inward":
                spread = 7 + ((1.0 - eased) * min(70, (x2 - x1) * 0.2))
            self._ship(center - spread, y, dim, tags, scale=0.65)
            self.canvas.create_rectangle(
                center + spread - 4, y - 2,
                center + spread + 4, y + 2,
                fill="#010101", outline=colour, width=1, tags=tags,
            )
            return

        if scene.family == "scope":
            if kind == "honk":
                for index in range(3):
                    local = max(0.0, min(1.0, (eased * 1.25) - (index * 0.15)))
                    radius_x = 5 + (local * min(120, (x2 - x1) * 0.34))
                    radius_y = 2 + (local * 5)
                    self.canvas.create_oval(
                        center - radius_x, y - radius_y,
                        center + radius_x, y + radius_y,
                        fill="", outline=colour if index == 0 else dim,
                        width=2 if index == 0 else 1, tags=tags,
                    )
                return
            if kind == "body_scan":
                radius_x, radius_y = 25, 6
                self.canvas.create_oval(
                    center - radius_x, y - radius_y,
                    center + radius_x, y + radius_y,
                    fill="", outline=dim, width=1, tags=tags,
                )
                scan_x = center - radius_x + (eased * radius_x * 2)
                self._line(scan_x, y - radius_y, scan_x, y + radius_y,
                           colour=colour, width=2, tags=tags)
                return
            if kind == "fss_signal":
                radius = 3 + (math.sin(progress * math.pi) * 8)
                target_x = center + 28
                self.canvas.create_oval(
                    target_x - radius, y - min(5, radius),
                    target_x + radius, y + min(5, radius),
                    fill="", outline=colour, width=1, tags=tags,
                )
                self._dot(target_x, y, colour, 1.5, tags)
                return
            if kind == "signals":
                for index, offset in enumerate((-42, -16, 19, 47)):
                    pulse = abs((((eased + index * 0.18) % 1.0) * 2) - 1)
                    radius = 2 + (pulse * 3)
                    self.canvas.create_oval(
                        center + offset - radius, y - radius,
                        center + offset + radius, y + radius,
                        fill="", outline=colour if index % 2 == 0 else dim,
                        width=1, tags=tags,
                    )
                return
            if kind == "codex":
                radius = 4 + (math.sin(progress * math.pi) * 5)
                self.canvas.create_polygon(
                    center, y - radius, center + radius, y,
                    center, y + radius, center - radius, y,
                    fill="", outline=colour, width=2, tags=tags,
                )
                return
            radius_x = 16 + (eased * 18)
            radius_y = 4 + (eased * 2)
            self.canvas.create_oval(
                center - radius_x, y - radius_y,
                center + radius_x, y + radius_y,
                fill="", outline=dim, width=1, tags=tags,
            )
            angle = (-0.75 * math.pi) + (eased * 1.5 * math.pi)
            self._line(center, y,
                       center + (math.cos(angle) * radius_x),
                       y + (math.sin(angle) * radius_y),
                       colour=colour, tags=tags)
            if kind in {"valuable_discovery", "first_discovery", "footfall_candidate"}:
                self.canvas.create_polygon(
                    center + radius_x, y - 3,
                    center + radius_x + 4, y,
                    center + radius_x, y + 3,
                    center + radius_x - 4, y,
                    fill="", outline=colour, width=1, tags=tags,
                )
            else:
                self._dot(center + (radius_x * 0.55), y - 2, colour, 1.3, tags)
            return

        if scene.family in {"clearance", "recovery"}:
            for index in range(4):
                local = min(1.0, max(0.0, (eased * 1.3) - (index * 0.12)))
                spread = 8 + (local * min(120, (x2 - x1) * 0.36))
                self._line(center - spread, y, center - spread + 9, y,
                           colour=colour, tags=tags)
                self._line(center + spread - 9, y, center + spread, y,
                           colour=colour, tags=tags)
            return


        if scene.family == "resource":
            # Mining lives on the right wing and deliberately uses a different
            # visual grammar from FSS/DSS scope activity.  Elite exposes the
            # completed ProspectedAsteroid analysis (not limpet launch), then
            # MiningRefined as each tonne reaches the hold.
            lane_left = max(center + 8, float(model.get("group_right", center + 8)))
            lane_right = x2
            cx = lane_left + ((lane_right - lane_left) * 0.52)
            half_y = max(4.0, min(6.0, (bottom - top) * 0.42))

            if kind == "mining_refined":
                # Three loose fragments converge into a refinery/cargo cell.
                target_x = min(lane_right - 7, cx + 13)
                cell_w, cell_h = 8.0, half_y + 1.0
                self.canvas.create_rectangle(
                    target_x - cell_w, y - cell_h,
                    target_x + cell_w, y + cell_h,
                    fill="#010101", outline=dim, width=1, tags=tags,
                )
                fill_width = max(0.0, (cell_w * 2.0 - 3.0) * eased)
                if fill_width:
                    self._line(
                        target_x - cell_w + 2, y + cell_h - 2,
                        target_x - cell_w + 2 + fill_width, y + cell_h - 2,
                        colour=colour, width=2, tags=tags,
                    )
                burst_count = max(2, min(4, int(event.get("count", 1) or 1) + 1))
                for index in range(burst_count):
                    local = max(0.0, min(1.0, (eased * 1.25) - (index * 0.09)))
                    start_x = max(lane_left + 3, cx - 24 - (index * 4))
                    px = start_x + ((target_x - start_x - cell_w - 2) * local)
                    py = y + ((index % 3) - 1) * half_y * (1.0 - local)
                    self._dot(px, py, colour if local > 0.72 else dim, 1.2, tags)
                return

            radius_x = max(9.0, min(14.0, (lane_right - lane_left) * 0.18))
            radius_y = half_y
            rock = (
                cx - radius_x, y - 1,
                cx - radius_x * 0.68, y - radius_y,
                cx - radius_x * 0.08, y - radius_y * 0.76,
                cx + radius_x * 0.54, y - radius_y,
                cx + radius_x, y - radius_y * 0.12,
                cx + radius_x * 0.72, y + radius_y * 0.78,
                cx + radius_x * 0.10, y + radius_y,
                cx - radius_x * 0.74, y + radius_y * 0.70,
            )
            self.canvas.create_polygon(
                *rock, fill="#010101", outline=dim, width=1, tags=tags,
            )

            if kind == "prospector_core":
                # Motherlodes fracture around a bright central seam.
                crack = (
                    cx - radius_x * 0.42, y - radius_y * 0.72,
                    cx - radius_x * 0.10, y - radius_y * 0.15,
                    cx - radius_x * 0.28, y + radius_y * 0.10,
                    cx + radius_x * 0.12, y + radius_y * 0.72,
                )
                self._line(*crack, colour=colour, width=2, smooth=True, tags=tags)
                core_radius = 1.6 + (math.sin(progress * math.pi) * 2.2)
                self.canvas.create_polygon(
                    cx, y - core_radius,
                    cx + core_radius, y,
                    cx, y + core_radius,
                    cx - core_radius, y,
                    fill=colour, outline="#010101", width=1, tags=tags,
                )
                for side in (-1, 1):
                    spread = radius_x + 4 + (eased * 8)
                    self._line(
                        cx + (side * spread), y - half_y,
                        cx + (side * spread), y + half_y,
                        colour=colour, width=2, tags=tags,
                    )
                return

            # Ordinary prospecting sweeps across the irregular rock. A rich
            # analysis resolves into brighter contacts instead of a core seam.
            sweep_x = cx - radius_x + ((radius_x * 2.0) * eased)
            self._line(
                sweep_x, y - radius_y, sweep_x, y + radius_y,
                colour=colour, width=2, tags=tags,
            )
            bracket_spread = radius_x + 10 - (eased * 7)
            for side in (-1, 1):
                bx = cx + (side * bracket_spread)
                self._line(bx, y - half_y, bx, y + half_y,
                           colour=dim, tags=tags)
                self._line(bx, y - half_y, bx - (side * 4), y - half_y,
                           colour=dim, tags=tags)
                self._line(bx, y + half_y, bx - (side * 4), y + half_y,
                           colour=dim, tags=tags)
            contact_count = max(1, min(3, int(event.get("material_count", 1) or 1)))
            contacts = ((-0.47, -0.28), (0.08, 0.38), (0.55, -0.42))
            for index, (ox, oy) in enumerate(contacts[:contact_count]):
                if eased < 0.34 + (index * 0.10):
                    continue
                contact_colour = colour if kind == "prospector_rich" else dim
                self._dot(
                    cx + (radius_x * ox), y + (radius_y * oy),
                    contact_colour, 1.5 if kind == "prospector_rich" else 1.0, tags,
                )
            return

        if scene.family in {"hazard", "signal"}:
            flash = int(progress * 12) % 2 == 0
            frame_colour = colour if flash else dim
            self._line(x1, top, x1 + 22, top,
                       colour=frame_colour, width=2, tags=tags)
            self._line(x2 - 22, bottom, x2, bottom,
                       colour=frame_colour, width=2, tags=tags)
            spread = 6 + (eased * min(80, (x2 - x1) * 0.22))
            for side in (-1, 1):
                x = center + (side * spread)
                self._line(x, top, x, bottom,
                           colour=frame_colour, width=2, tags=tags)
            return

        # Wake and uncommon events receive a brief boot-sequence sweep rather
        # than falling back to the old shared lane tracer.
        x = x1 + ((x2 - x1) * eased)
        self._line(x - 12, top, x, top, colour=dim, width=2, tags=tags)
        self._line(x, bottom, min(x2, x + 12), bottom,
                   colour=colour, width=2, tags=tags)
