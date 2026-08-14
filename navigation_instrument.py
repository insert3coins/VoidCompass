"""Animation scene vocabulary for the Navigation HUD instrument.

The HUD renderer stays in :mod:`hud`, while this module owns the small,
deterministic description of how each sustained state and journal pulse should
move.  Keeping that vocabulary free of Tk makes it inexpensive to test and
prevents the boot-inspired visuals from becoming another large conditional in
the overlay itself.
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
    """Short boot-style response layered over the sustained state."""

    family: str
    direction: str = "outward"
    pulses: int = 1
    intensity: float = 0.78


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

    # These states own stronger bespoke motion in the HUD renderer.  Listing
    # them here prevents the ordinary flight stream being painted underneath.
    "fsd_lock": StateScene("dedicated", 26.0, packets=0),
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
    "fuel": {"fuel", "boost"},
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
        "fuel": "inward",
        "recovery": "outward",
    }.get(family, "outward")
    pulses = {
        "boot": 3,
        "route": 3,
        "charge": 5,
        "arrival": 3,
        "scope": 3,
        "hazard": 4,
    }.get(family, 2)
    intensity = 0.9 if family in {"charge", "hazard"} else 0.78
    return EventScene(family, direction=direction, pulses=pulses, intensity=intensity)


class NavigationInstrumentRenderer:
    """Draw the Navigation HUD as a compact animated flight-computer scene.

    The renderer deliberately owns no game state.  It receives the verified
    state model from ``hud.TacticalHUD`` and turns it into code-native Canvas
    geometry inspired by the startup flight computer.  Sustained states,
    modifiers and one-shot journal events are separate layers.
    """

    def __init__(self, canvas, mix_colour):
        self.canvas = canvas
        self.mix_colour = mix_colour

    @staticmethod
    def _cycle(phase, period):
        return (float(phase) % max(1.0, float(period))) / max(1.0, float(period))

    @staticmethod
    def _smooth(value):
        value = max(0.0, min(1.0, float(value)))
        return value * value * (3.0 - (2.0 * value))

    def _line(self, *coords, colour, width=1, tags="nav_state_motion", smooth=False):
        if width > 1:
            self.canvas.create_line(
                *coords, fill="#010101", width=width + 2,
                tags=tags, smooth=smooth,
            )
        self.canvas.create_line(
            *coords, fill=colour, width=width,
            tags=tags, smooth=smooth,
        )

    def _dot(self, x, y, colour, radius=1.2, tags="nav_state_motion"):
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

    def draw_static(self, model, tags="nav_state_static"):
        """Draw a quiet open frame; state geometry remains free to transform."""
        x1, x2 = model["scene_x1"], model["scene_x2"]
        label_y = model["label_y"]
        top, bottom = model["scene_top"], model["scene_bottom"]
        group_left, group_right = model["group_left"], model["group_right"]
        colour = model["state_color"]
        dim = self.mix_colour(colour, 0.38)

        # Bootloader-style open header: no enclosing rail or tapered capsule.
        self.canvas.create_line(
            x1 + 7, label_y, group_left - 9, label_y,
            fill=dim, width=1, tags=tags,
        )
        self.canvas.create_line(
            group_right + 9, label_y, x2 - 7, label_y,
            fill=dim, width=1, tags=tags,
        )
        for x, side in ((x1, 1), (x2, -1)):
            self.canvas.create_line(
                x, top + 3, x, bottom,
                fill=dim, width=1, tags=tags,
            )
            self.canvas.create_line(
                x, top + 3, x + (side * 7), top + 3,
                fill=dim, width=1, tags=tags,
            )
            self.canvas.create_line(
                x, bottom, x + (side * 4), bottom,
                fill=dim, width=1, tags=tags,
            )

    def draw_state(self, model, phase, palette, tags="nav_state_motion", motion=True):
        profile = model["motion_profile"]
        state = model["state"]
        colour = model["state_color"]
        scene = state_scene(profile)

        if profile == "fsd_lock":
            self._draw_lock(model, phase, colour, tags)
        elif profile == "fsd_charge":
            self._draw_charge(model, phase, colour, tags)
        elif profile == "fsd_cooldown":
            self._draw_cooldown(model, phase, colour, tags)
        elif profile == "jump":
            self._draw_hyperspace(model, phase, colour, tags)
        elif profile == "arrival":
            self._draw_arrival(model, phase, colour, tags)
        elif profile == "supercruise_overcharge":
            self._draw_overcharge(model, phase, colour, tags)
        elif profile in {"carrier_transit", "carrier_arrival"}:
            self._draw_carrier(model, phase, colour, tags, arriving=profile == "carrier_arrival")
        elif profile in {"orbital_approach", "glide", "surface_approach"}:
            self._draw_approach(model, phase, colour, tags, profile)
        elif profile == "surface_hold":
            self._draw_surface_hold(model, phase, colour, tags)
        elif profile in {"surface_departure", "orbital_departure"}:
            self._draw_departure(model, phase, colour, tags, profile)
        elif scene.family == "scope":
            self._draw_scope(model, phase, colour, tags, state)
        elif scene.family == "plot":
            self._draw_plot(model, phase, colour, tags, state)
        elif scene.family == "route":
            self._draw_supercruise(model, phase, colour, tags)
        elif scene.family == "readiness":
            self._draw_docked(model, phase, colour, tags)
        elif scene.family == "horizon":
            self._draw_landed(model, phase, colour, tags)
        elif scene.family == "terrain":
            self._draw_terrain(model, phase, colour, tags, state)
        elif scene.family == "alert":
            self._draw_combat(model, phase, colour, tags)
        elif scene.family == "handoff":
            self._draw_handoff(model, phase, colour, tags, profile)
        else:
            self._draw_flight(
                model, phase, colour, tags,
                fighter=profile == "fighter",
            )

        self._draw_modifiers(model, phase, palette, tags)

    def _bounds(self, model):
        return (
            model["scene_x1"] + 8,
            model["scene_x2"] - 8,
            model["scene_y"],
            model["scene_top"],
            model["scene_bottom"],
        )

    def _draw_flight(self, model, phase, colour, tags, fighter=False):
        x1, x2, y, top, bottom = self._bounds(model)
        span = x2 - x1
        period = 36 if fighter else 56
        travel = self._cycle(phase, period)
        dim = self.mix_colour(colour, 0.48)
        center = (x1 + x2) / 2

        # Sparse star drift and a clear forward vector: this is a scene, not a
        # packet running through a status rail.
        for index, offset in enumerate((0.08, 0.39, 0.72, 0.91)):
            local = (offset - travel) % 1.0
            x = x1 + (span * local)
            py = y + ((index % 3) - 1) * 3
            self._dot(x, py, colour if index == 1 else dim, 1, tags)
        self._line(center + 9, y, x2 - 8, y, colour=dim, tags=tags)
        pointer = x2 - 4
        self._line(
            pointer - 5, y - 3, pointer, y, pointer - 5, y + 3,
            colour=colour, tags=tags,
        )
        self._ship(center, y, colour, tags, fighter=fighter)
        if fighter:
            wing = 12 + (abs((travel * 2) - 1) * 5)
            self._line(center - wing, top + 1, center + wing, top + 1,
                       colour=dim, tags=tags)

    def _draw_supercruise(self, model, phase, colour, tags):
        x1, x2, y, top, bottom = self._bounds(model)
        span = x2 - x1
        travel = self._cycle(phase, 25)
        dim = self.mix_colour(colour, 0.58)
        ship_x = x1 + (span * 0.44)
        for index in range(5):
            local = (travel + (index / 5.0)) % 1.0
            x = x1 + (span * local)
            py = y + ((index % 3) - 1) * 3
            length = 8 + (local * 12)
            self._line(max(x1, x - length), py, x, py,
                       colour=colour if index == 0 else dim,
                       width=2 if index == 0 else 1, tags=tags)
        gate_x = x2 - 14
        gate = 3 + (abs((travel * 2) - 1) * 3)
        self._line(gate_x - 4, y - gate, gate_x, y, gate_x - 4, y + gate,
                   colour=colour, tags=tags)
        self._ship(ship_x, y, colour, tags)

    def _draw_scope(self, model, phase, colour, tags, state):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        radius_x = min(34.0, (x2 - x1) * 0.12)
        radius_y = max(5.0, (bottom - top) / 2)
        dim = self.mix_colour(colour, 0.42)
        travel = self._cycle(phase, 40 if state in {"FSS", "DSS"} else 68)

        if state == "DSS":
            # DSS owns a moving planetary meridian rather than the FSS sweep.
            self.canvas.create_oval(
                center - radius_x, y - radius_y,
                center + radius_x, y + radius_y,
                fill="", outline=dim, width=1, tags=tags,
            )
            meridian = (travel * 2.0) - 1.0
            width = max(2.0, radius_x * (1.0 - abs(meridian)))
            self.canvas.create_oval(
                center - width, y - radius_y,
                center + width, y + radius_y,
                fill="", outline=colour, width=1, tags=tags,
            )
            self._dot(center + (radius_x * meridian), y, colour, 1.2, tags)
            return

        self.canvas.create_oval(
            center - radius_x, y - radius_y,
            center + radius_x, y + radius_y,
            fill="", outline=dim, width=1, tags=tags,
        )
        self.canvas.create_oval(
            center - (radius_x * 0.48), y - (radius_y * 0.48),
            center + (radius_x * 0.48), y + (radius_y * 0.48),
            fill="", outline=self.mix_colour(colour, 0.28), width=1, tags=tags,
        )
        angle = (-0.8 * math.pi) + (travel * 1.6 * math.pi)
        self._line(
            center, y,
            center + (math.cos(angle) * radius_x),
            y + (math.sin(angle) * radius_y),
            colour=colour, tags=tags,
        )
        contacts = 3 if state == "FSS" else 2
        for index in range(contacts):
            cx = center + ((-0.62 + (index * 0.56)) * radius_x)
            cy = y + ((-1 if index % 2 else 1) * (radius_y * 0.45))
            pulse = abs(((travel + (index * 0.23)) % 1.0) * 2 - 1)
            self._dot(cx, cy, colour if pulse < 0.45 else dim, 1.2, tags)
        # Calibration ticks make exploration's passive scope span the scene.
        for x in (x1 + 22, x2 - 22):
            self._line(x, y - 3, x, y + 3, colour=dim, tags=tags)

    def _draw_plot(self, model, phase, colour, tags, state):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        dim = self.mix_colour(colour, 0.46)
        travel = self._cycle(phase, 64)

        if state in {"SYSTEM MAP", "ORRERY"}:
            for index, scale in enumerate((0.32, 0.58, 0.88)):
                rx = 12 + (scale * 28)
                ry = 3 + (scale * 4)
                self.canvas.create_oval(
                    center - rx, y - ry, center + rx, y + ry,
                    fill="", outline=dim, width=1, tags=tags,
                )
                angle = (travel * math.tau * (index + 1)) + index
                self._dot(
                    center + (math.cos(angle) * rx),
                    y + (math.sin(angle) * ry),
                    colour if index == 1 else dim, 1, tags,
                )
            self._dot(center, y, colour, 1.5, tags)
            return

        offsets = (2, -3, 1, -2, 3, -1, 1)
        points = [
            (x1 + ((x2 - x1) * index / 6), y + offsets[index])
            for index in range(7)
        ]
        self._line(
            *[value for point in points for value in point],
            colour=dim, width=1, smooth=True, tags=tags,
        )
        scaled = travel * 6
        segment = min(5, int(scaled))
        fraction = scaled - segment
        cx = points[segment][0] + ((points[segment + 1][0] - points[segment][0]) * fraction)
        cy = points[segment][1] + ((points[segment + 1][1] - points[segment][1]) * fraction)
        for index, (px, py) in enumerate(points):
            self._dot(px, py, colour if index <= segment else dim, 1, tags)
        self._ship(cx, cy - 1, colour, tags, scale=0.72)

    def _draw_docked(self, model, phase, colour, tags):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        dim = self.mix_colour(colour, 0.42)
        pulse = abs((self._cycle(phase, 76) * 2) - 1)
        cells = 8
        for index in range(cells):
            amount = (index + 0.5) / cells
            x = x1 + ((x2 - x1) * amount)
            active = index in {int(pulse * (cells - 1)), cells - 1 - int(pulse * (cells - 1))}
            self._line(x - 5, y, x + 5, y,
                       colour=colour if active else dim,
                       width=2 if active else 1, tags=tags)
        clamp = 12
        for side in (-1, 1):
            x = center + (side * clamp)
            inward = x - (side * 5)
            self._line(x, top, x, bottom, inward, bottom,
                       colour=colour, tags=tags)

    def _draw_landed(self, model, phase, colour, tags):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        dim = self.mix_colour(colour, 0.48)
        wave = abs((self._cycle(phase, 82) * 2) - 1)
        span = (x2 - x1) * (0.34 + (wave * 0.04))
        self.canvas.create_arc(
            center - span, y - 2, center + span, bottom + 5,
            start=12, extent=156, style="arc", outline=dim,
            width=1, tags=tags,
        )
        self._ship(center, y - 1, colour, tags)
        for dx in (-5, 5):
            self._line(center + dx, y + 2, center + dx, bottom,
                       colour=colour, tags=tags)
            self._dot(center + dx, bottom, colour, 1, tags)

    def _draw_terrain(self, model, phase, colour, tags, state):
        x1, x2, y, top, bottom = self._bounds(model)
        span = x2 - x1
        travel = self._cycle(phase, 42 if state in {"SRV", "NOMAD"} else 62)
        dim = self.mix_colour(colour, 0.44)
        points = []
        for index in range(13):
            local = (index / 12 + travel) % 1.0
            x = x1 + (span * index / 12)
            height = (math.sin(local * math.tau * 2.0) + math.sin(local * math.tau * 5.0)) * 1.4
            points.extend((x, bottom - 1 - height))
        self._line(*points, colour=dim, tags=tags, smooth=True)
        center = (x1 + x2) / 2
        if state in {"SRV", "NOMAD"}:
            self.canvas.create_rectangle(
                center - 6, y - 3, center + 5, y + 2,
                fill="#010101", outline=colour, width=1, tags=tags,
            )
            for dx in (-4, 3):
                self.canvas.create_oval(
                    center + dx - 1.5, y + 1,
                    center + dx + 1.5, y + 4,
                    fill="#010101", outline=colour, width=1, tags=tags,
                )
        else:
            step = -1 if int(phase // 7) % 2 else 1
            self._dot(center, y - 3, colour, 1.3, tags)
            self._line(center, y - 1, center, y + 3,
                       colour=colour, tags=tags)
            self._line(center, y + 1, center + (step * 3), y + 4,
                       colour=colour, tags=tags)

    def _draw_combat(self, model, phase, colour, tags):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        dim = self.mix_colour(colour, 0.45)
        pulse = abs((self._cycle(phase, 22) * 2) - 1)
        radius = 7 + (pulse * 4)
        for side in (-1, 1):
            x = center + (side * radius)
            inward = x - (side * 4)
            self._line(x, top, x, bottom, inward, top,
                       colour=colour if side == (-1 if int(phase // 4) % 2 else 1) else dim,
                       width=2, tags=tags)
        self._dot(center, y, colour, 1.5, tags)
        for index, x in enumerate((x1 + 30, x2 - 44, x2 - 19)):
            py = y + (-3 if index % 2 else 3)
            self.canvas.create_oval(
                x - 3, py - 2, x + 3, py + 2,
                fill="", outline=dim, width=1, tags=tags,
            )

    def _draw_handoff(self, model, phase, colour, tags, profile):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        travel = self._cycle(phase, 38)
        wave = abs((travel * 2) - 1)
        if profile == "vehicle_board":
            wave = 1.0 - wave
        spread = 8 + (wave * min(54, (x2 - x1) * 0.18))
        dim = self.mix_colour(colour, 0.46)
        self._ship(center - spread, y, dim, tags, scale=0.7)
        self.canvas.create_rectangle(
            center + spread - 4, y - 2,
            center + spread + 4, y + 2,
            fill="#010101", outline=colour, width=1, tags=tags,
        )
        self._line(center - spread + 6, y, center + spread - 5, y,
                   colour=dim, tags=tags)

    def _draw_lock(self, model, phase, colour, tags):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        wave = abs((self._cycle(phase, 24) * 2) - 1)
        spread = 12 + (wave * min(70, (x2 - x1) * 0.22))
        dim = self.mix_colour(colour, 0.48)
        for side in (-1, 1):
            x = center + (side * spread)
            inward = x - (side * 7)
            self._line(x, top, x, bottom, inward, top,
                       colour=colour, width=2, tags=tags)
            self._line(inward, bottom, x, bottom,
                       colour=dim, tags=tags)
        self.canvas.create_polygon(
            center, y - 4, center + 4, y,
            center, y + 4, center - 4, y,
            fill="", outline=colour, width=1, tags=tags,
        )

    def _draw_charge(self, model, phase, colour, tags):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        travel = self._cycle(phase, 11)
        dim = self.mix_colour(colour, 0.38)
        cells = 10
        for index in range(cells):
            amount = (index + 0.5) / cells
            left_x = x1 + ((center - 9 - x1) * amount)
            right_x = x2 - ((x2 - center - 9) * amount)
            active = amount <= travel
            cell_colour = colour if active else dim
            self._line(left_x - 5, top + 1, left_x + 5, top + 1,
                       colour=cell_colour, width=2 if active else 1, tags=tags)
            self._line(right_x - 5, bottom - 1, right_x + 5, bottom - 1,
                       colour=cell_colour, width=2 if active else 1, tags=tags)
        ring = 4 + ((1.0 - travel) * 4)
        self.canvas.create_oval(
            center - ring, y - 5,
            center + ring, y + 5,
            fill="", outline=colour, width=2, tags=tags,
        )
        self._dot(center, y, colour, 1.5, tags)

    def _draw_cooldown(self, model, phase, colour, tags):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        travel = self._cycle(phase, 28)
        dim = self.mix_colour(colour, 0.4)
        for index in range(4):
            local = (travel + (index / 4)) % 1.0
            offset = 7 + ((x2 - x1) * 0.44 * local)
            fade = colour if local < 0.38 else dim
            for side in (-1, 1):
                x = center + (side * offset)
                self._line(x, y - 3, x, y + 3,
                           colour=fade, tags=tags)
        self.canvas.create_arc(
            center - 8, y - 5, center + 8, y + 5,
            start=30 + (travel * 300), extent=190,
            style="arc", outline=dim, width=1, tags=tags,
        )

    def _draw_hyperspace(self, model, phase, colour, tags):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        travel = self._cycle(phase, 8)
        dim = self.mix_colour(colour, 0.52)
        # Perspective gates expand from the drive core while long streaks
        # radiate outward—the opposite silhouette to the charging cells.
        for index in range(5):
            local = (travel + (index / 5)) % 1.0
            half = 5 + (local * min(90, (x2 - x1) * 0.24))
            height = 2 + (local * 4)
            gate_colour = colour if index == 0 else dim
            self._line(center - half, y - height, center - half, y + height,
                       colour=gate_colour, width=2 if index == 0 else 1, tags=tags)
            self._line(center + half, y - height, center + half, y + height,
                       colour=gate_colour, width=2 if index == 0 else 1, tags=tags)
        for side in (-1, 1):
            end = x1 if side < 0 else x2
            self._line(center + (side * 8), y, end, y,
                       colour=dim, width=2, tags=tags)
        self._dot(center, y, colour, 2, tags)

    def _draw_arrival(self, model, phase, colour, tags):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        travel = self._cycle(phase, 24)
        dim = self.mix_colour(colour, 0.44)
        for index in range(3):
            local = (travel + (index / 3)) % 1.0
            radius_x = 5 + (local * min(80, (x2 - x1) * 0.22))
            radius_y = 2 + (local * 4)
            self.canvas.create_oval(
                center - radius_x, y - radius_y,
                center + radius_x, y + radius_y,
                fill="", outline=colour if local < 0.34 else dim,
                width=1, tags=tags,
            )
        self._ship(center, y, colour, tags)

    def _draw_overcharge(self, model, phase, colour, tags):
        x1, x2, y, top, bottom = self._bounds(model)
        span = x2 - x1
        travel = self._cycle(phase, 6)
        dim = self.mix_colour(colour, 0.62)
        for index in range(7):
            local = (travel + (index / 7)) % 1.0
            x = x1 + (span * local)
            py = top + 1 if index % 2 == 0 else bottom - 1
            self._line(max(x1, x - 18), py, x, py,
                       colour=colour if index in {0, 3} else dim,
                       width=2, tags=tags)
        center = (x1 + x2) / 2
        shear = 3 if int(phase // 2) % 2 else -3
        self._line(center - 12, y + shear, center, y,
                   center + 12, y - shear,
                   colour=colour, width=2, tags=tags)

    def _draw_carrier(self, model, phase, colour, tags, arriving=False):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        travel = self._cycle(phase, 28 if arriving else 14)
        dim = self.mix_colour(colour, 0.52)
        self._ship(center, y, colour, tags, carrier=True, scale=0.9)
        if arriving:
            for index in range(3):
                local = (travel + index / 3) % 1.0
                span = 16 + (local * min(110, (x2 - x1) * 0.3))
                self._line(center - span, top + 1, center - span, bottom - 1,
                           colour=colour if local < 0.3 else dim, tags=tags)
                self._line(center + span, top + 1, center + span, bottom - 1,
                           colour=colour if local < 0.3 else dim, tags=tags)
            return
        for index in range(6):
            local = (travel + index / 6) % 1.0
            left = x1 + ((center - 18 - x1) * local)
            right = x2 - ((x2 - center - 18) * local)
            py = top + 1 if index % 2 == 0 else bottom - 1
            self._line(left - 10, py, left, py, colour=dim, width=2, tags=tags)
            self._line(right, py, right + 10, py, colour=dim, width=2, tags=tags)

    def _draw_approach(self, model, phase, colour, tags, profile):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        dim = self.mix_colour(colour, 0.5)
        periods = {"orbital_approach": 28, "glide": 8, "surface_approach": 18}
        travel = self._cycle(phase, periods[profile])
        horizon_span = (x2 - x1) * (0.34 if profile == "orbital_approach" else 0.22)
        self.canvas.create_arc(
            center - horizon_span, y - 1,
            center + horizon_span, bottom + 6,
            start=12, extent=156, style="arc",
            outline=dim, width=1, tags=tags,
        )
        if profile == "orbital_approach":
            for index in range(3):
                local = (travel + index / 3) % 1.0
                left = x1 + ((center - 12 - x1) * local)
                right = x2 - ((x2 - center - 12) * local)
                self._line(left - 7, y, left, y, colour=colour, tags=tags)
                self._line(right, y, right + 7, y, colour=colour, tags=tags)
        elif profile == "glide":
            for index in range(6):
                local = (travel + index / 6) % 1.0
                x = x1 + ((x2 - x1) * local)
                self._line(x - 10, top, x, bottom,
                           colour=colour if index % 2 == 0 else dim,
                           width=2 if index % 2 == 0 else 1, tags=tags)
        else:
            gate_y = top + (travel * (bottom - top))
            for side in (-1, 1):
                x = center + (side * 18)
                self._line(x - 5, gate_y, x + 5, gate_y,
                           colour=colour, width=2, tags=tags)
        self._ship(center, y - 1, colour, tags, scale=0.75)

    def _draw_departure(self, model, phase, colour, tags, profile):
        x1, x2, y, top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        travel = 1.0 - self._cycle(phase, 18 if profile == "surface_departure" else 24)
        dim = self.mix_colour(colour, 0.48)
        horizon_span = (x2 - x1) * (0.2 - (0.07 * (1.0 - travel)))
        self.canvas.create_arc(
            center - horizon_span, y,
            center + horizon_span, bottom + 5,
            start=12, extent=156, style="arc", outline=dim,
            width=1, tags=tags,
        )
        if profile == "surface_departure":
            gate_y = top + (travel * (bottom - top))
            for side in (-1, 1):
                x = center + (side * 18)
                self._line(x - 5, gate_y, x + 5, gate_y,
                           colour=colour, tags=tags)
        else:
            for index in range(3):
                local = (travel + index / 3) % 1.0
                spread = 12 + (local * min(100, (x2 - x1) * 0.28))
                self._line(center - spread, y, center - spread + 9, y,
                           colour=colour if index == 0 else dim, tags=tags)
                self._line(center + spread - 9, y, center + spread, y,
                           colour=colour if index == 0 else dim, tags=tags)
        self._ship(center, y - 1, colour, tags, scale=0.75)

    def _draw_surface_hold(self, model, phase, colour, tags):
        """Quiet hover scene with no false approach/departure direction."""
        x1, x2, y, _top, bottom = self._bounds(model)
        center = (x1 + x2) / 2
        dim = self.mix_colour(colour, 0.48)
        pulse = abs((self._cycle(phase, 76) * 2.0) - 1.0)
        horizon_span = min((x2 - x1) * 0.18, 48)
        self.canvas.create_arc(
            center - horizon_span, y,
            center + horizon_span, bottom + 5,
            start=12, extent=156, style="arc",
            outline=dim, width=1, tags=tags,
        )
        bracket = 17 + (pulse * 2)
        for side in (-1, 1):
            x = center + (side * bracket)
            self._line(x, y - 4, x, y + 4, colour=dim, tags=tags)
            self._line(
                x, y - 4, x - (side * 4), y - 4,
                colour=colour, tags=tags,
            )
            self._line(
                x, y + 4, x - (side * 4), y + 4,
                colour=colour, tags=tags,
            )
        self._ship(center, y - 1, colour, tags, scale=0.75)

    def _draw_modifiers(self, model, phase, palette, tags):
        x1, x2, y, top, bottom = self._bounds(model)
        colour = model["state_color"]
        if model.get("fuel_scooping"):
            green = palette["green"]
            travel = self._cycle(phase, 18)
            self.canvas.create_arc(
                x1 - 13, top - 4, x1 + 21, bottom + 5,
                start=280, extent=150, style="arc",
                outline=self.mix_colour(green, 0.68), width=2, tags=tags,
            )
            for index in range(3):
                local = (travel + index / 3) % 1.0
                x = x1 + 8 + ((x2 - x1) * 0.2 * local)
                self._line(max(x1, x - 7), y + (index - 1) * 2, x, y + (index - 1) * 2,
                           colour=green, tags=tags)

        if model.get("boost_armed"):
            accent = palette["accent"]
            travel = self._cycle(phase, 48)
            radius = 7 + (abs((travel * 2) - 1) * 3)
            self.canvas.create_oval(
                x2 - 28 - radius, y - 5,
                x2 - 28 + radius, y + 5,
                fill="", outline=self.mix_colour(accent, 0.62),
                width=1, tags=tags,
            )
            self._line(x2 - 43, y, x2 - 16, y,
                       colour=self.mix_colour(accent, 0.5), tags=tags)

        gravity = float(model.get("gravity_load", 0.0) or 0.0)
        if gravity > 0:
            gravity_colour = model.get("gravity_color", colour)
            span = (x2 - x1) * (0.08 + (gravity * 0.12))
            center = (x1 + x2) / 2
            self._line(center - span, bottom, center + span, bottom,
                       colour=gravity_colour, width=2 if gravity > 0.5 else 1,
                       tags=tags)

        ship_config = model.get("ship_config") or {}
        center = (x1 + x2) / 2
        if ship_config.get("landing_gear"):
            for dx in (-5, 5):
                self._line(center + dx, bottom - 3, center + dx, bottom,
                           colour=self.mix_colour(colour, 0.74), tags=tags)
                self._line(center + dx - 2, bottom,
                           center + dx + 2, bottom,
                           colour=colour, tags=tags)
        if ship_config.get("cargo_scoop"):
            orange = palette["orange"]
            scoop_x = x1 + 17
            self._line(scoop_x - 4, y - 2, scoop_x, y + 3,
                       scoop_x + 4, y - 2,
                       colour=orange, tags=tags)
        # Analysis Mode is intentionally not drawn as a generic overlay here.
        # Its former right-hand sweep only made visual sense when it terminated
        # on the (now separate) local-target reticle.  Scanner/map states and
        # journal scan events already provide their own integrated geometry.

    def draw_transition(self, model, transition, progress, tags="nav_state_motion"):
        """Boot-style scanner wipe between two genuinely different scenes."""
        x1, x2, y, top, bottom = self._bounds(model)
        progress = self._smooth(progress)
        split = 0.45
        if progress < split:
            local = progress / split
            colour = transition["from_color"]
            left = x1 + (((x2 - x1) / 2) * local)
            right = x2 - (((x2 - x1) / 2) * local)
        else:
            local = (progress - split) / (1.0 - split)
            colour = transition["to_color"]
            center = (x1 + x2) / 2
            left = center - (((x2 - x1) / 2) * local)
            right = center + (((x2 - x1) / 2) * local)
        dim = self.mix_colour(colour, 0.58)
        self._line(left, top, left, bottom, colour=colour, width=2, tags=tags)
        self._line(right, top, right, bottom, colour=colour, width=2, tags=tags)
        for x in (left - 8, right + 8):
            if x1 <= x <= x2:
                self._line(x, y - 2, x, y + 2, colour=dim, tags=tags)

    def draw_event(self, model, event, progress, palette, tags="nav_state_motion"):
        kind = str(event.get("kind") or "")
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

        if scene.family == "fuel":
            if kind == "boost":
                radius_x = 8 + (eased * min(90, (x2 - x1) * 0.26))
                for offset in (-3, 3):
                    self.canvas.create_arc(
                        center - radius_x, y - 5 + offset,
                        center + radius_x, y + 5 + offset,
                        start=20, extent=140, style="arc",
                        outline=colour, width=2, tags=tags,
                    )
                self._dot(center, y, colour, 2, tags)
                return
            self.canvas.create_arc(
                x1 - 10, top - 5, x1 + 35, bottom + 6,
                start=278, extent=150, style="arc",
                outline=colour, width=2, tags=tags,
            )
            for index in range(4):
                local = (eased + index / 4) % 1.0
                x = x1 + 18 + ((center - x1 - 18) * local)
                self._line(x - 8, y + ((index % 3) - 1) * 2, x, y + ((index % 3) - 1) * 2,
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
