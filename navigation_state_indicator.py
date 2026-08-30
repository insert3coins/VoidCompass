"""Code-native sustained-state instrument for the Navigation HUD.

The shallow indicator bay is divided into three deliberate roles: a state
sigil on the left, an always-readable native label in the centre, and a live
motion response on the right.  The visual vocabulary takes the useful idea
from the Navigation HUD concept mock-up—ring, icon and state-specific motion—
without importing its large panel or duplicating telemetry shown elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from navigation_instrument import STATE_SCENES, event_scene, state_scene


@dataclass(frozen=True)
class IndicatorDesign:
    dialect: str
    variant: str


DESIGNS = {
    "flight": IndicatorDesign("flight", "cruise"),
    "supercruise": IndicatorDesign("flight", "supercruise"),
    "fighter": IndicatorDesign("flight", "fighter"),
    "exploration": IndicatorDesign("survey", "exploration"),
    "docked": IndicatorDesign("station", "docked"),
    "landed": IndicatorDesign("surface", "landed"),
    "surface_vehicle": IndicatorDesign("surface", "vehicle"),
    "on_foot": IndicatorDesign("surface", "foot"),
    "scanner": IndicatorDesign("survey", "scanner"),
    "map": IndicatorDesign("survey", "map"),
    "combat": IndicatorDesign("hazard", "combat"),
    "vehicle_deploy": IndicatorDesign("handoff", "deploy"),
    "vehicle_board": IndicatorDesign("handoff", "board"),
    "vehicle_switch": IndicatorDesign("handoff", "switch"),
    "fsd_lock": IndicatorDesign("hazard", "lock"),
    "asteroid_field": IndicatorDesign("hazard", "asteroid"),
    "fsd_charge": IndicatorDesign("fsd", "charge"),
    "fsd_cooldown": IndicatorDesign("fsd", "cooldown"),
    "jump": IndicatorDesign("fsd", "jump"),
    "arrival": IndicatorDesign("fsd", "arrival"),
    "supercruise_overcharge": IndicatorDesign("fsd", "overcharge"),
    "carrier_transit": IndicatorDesign("carrier", "transit"),
    "carrier_arrival": IndicatorDesign("carrier", "arrival"),
    "carrier_deck": IndicatorDesign("carrier", "deck"),
    "orbital_approach": IndicatorDesign("planetary", "orbital_approach"),
    "glide": IndicatorDesign("planetary", "glide"),
    "surface_approach": IndicatorDesign("planetary", "surface_approach"),
    "surface_hold": IndicatorDesign("planetary", "hold"),
    "surface_departure": IndicatorDesign("planetary", "surface_departure"),
    "orbital_departure": IndicatorDesign("planetary", "orbital_departure"),
}


class NavigationStateIndicator:
    """Draw a quiet but expressive state sigil and motion response."""

    def __init__(self, canvas, mix_colour):
        self.canvas = canvas
        self.mix_colour = mix_colour

    @staticmethod
    def _cycle(phase, period):
        period = max(1.0, float(period or 1.0))
        return (float(phase) % period) / period

    @staticmethod
    def _ease(value):
        value = max(0.0, min(1.0, float(value)))
        return value * value * (3.0 - (2.0 * value))

    @staticmethod
    def _wave(progress):
        return 0.5 - (0.5 * math.cos(float(progress) * math.tau))

    def _line(self, *coords, colour, width=1, tags="nav_state_core", smooth=False):
        width = max(1, int(width))
        if width >= 2:
            self.canvas.create_line(
                *coords, fill="#010101", width=width + 2,
                smooth=smooth, tags=tags,
            )
        self.canvas.create_line(
            *coords, fill=colour, width=width,
            smooth=smooth, tags=tags,
        )

    def _dot(self, x, y, colour, radius=1.4, tags="nav_state_core"):
        radius = max(1.0, float(radius))
        self.canvas.create_oval(
            x - radius - 1, y - radius - 1,
            x + radius + 1, y + radius + 1,
            fill="#010101", outline="", tags=tags,
        )
        self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill=colour, outline="", tags=tags,
        )

    def _arc(self, x1, y1, x2, y2, start, extent, colour,
             width=1, tags="nav_state_core"):
        if abs(float(extent)) >= 359.5:
            self.canvas.create_oval(
                x1, y1, x2, y2, fill="", outline=colour,
                width=width, tags=tags,
            )
            return
        self.canvas.create_arc(
            x1, y1, x2, y2, start=start, extent=extent,
            style="arc", outline=colour, width=width, tags=tags,
        )

    @staticmethod
    def _geometry(model):
        y = float(model["scene_y"])
        top = float(model["scene_top"])
        bottom = float(model["scene_bottom"])
        left = float(model["scene_x1"]) + 9
        left_end = float(model["group_left"]) - 14
        right_start = float(model["group_right"]) + 14
        right = float(model["scene_x2"]) - 9
        left_center = left + ((left_end - left) * 0.38)
        right_center = right_start + ((right - right_start) * 0.58)
        return {
            "y": y, "top": top, "bottom": bottom,
            "left": left, "left_end": left_end,
            "right_start": right_start, "right": right,
            "left_center": left_center, "right_center": right_center,
        }

    def draw_static(self, model, tags="nav_state_static"):
        """Draw the shared open chassis without surrounding the state in a box."""
        g = self._geometry(model)
        colour = model["state_color"]
        dim = self.mix_colour(colour, 0.30)
        y = g["y"]

        # Two independent rails visually terminate at the centred label.  The
        # small outer corners echo the app chrome without becoming a capsule.
        self._line(g["left"], y, g["left_end"], y,
                   colour=dim, tags=tags)
        self._line(g["right_start"], y, g["right"], y,
                   colour=dim, tags=tags)
        for x, side in ((g["left"], 1), (g["right"], -1)):
            self._line(x, g["top"] + 5, x, g["bottom"] - 5,
                       colour=dim, tags=tags)
            self._line(x, g["top"] + 5, x + side * 7, g["top"] + 5,
                       colour=dim, tags=tags)
            self._line(x, g["bottom"] - 5, x + side * 4, g["bottom"] - 5,
                       colour=dim, tags=tags)

        # Inboard registration ticks connect both instruments to the label but
        # deliberately stop short of the protected text aperture.
        for x, side in ((g["left_end"], -1), (g["right_start"], 1)):
            self._line(x, y - 4, x, y + 4, colour=dim, tags=tags)
            self._line(x, y - 4, x + side * 5, y,
                       colour=dim, tags=tags)

    def draw_center_core(self, model, phase, *, tags="nav_state_core", motion=True):
        """Add one restrained state pulse beneath the fixed centre label."""
        profile = str(model.get("motion_profile") or "flight")
        design = DESIGNS.get(profile, DESIGNS["flight"])
        variant = self._resolve_variant(
            profile, model.get("state"), design.variant,
        )
        scene = state_scene(profile)
        level = str(model.get("animation_intensity") or "Standard").title()
        speed, depth = {
            "Calm": (0.78, 0.72),
            "Energetic": (1.18, 1.28),
        }.get(level, (1.0, 1.0))
        progress = self._cycle(phase * speed, scene.period) if motion else 0.18
        wave = self._wave(progress) if motion else 0.35
        colour = model["state_color"]
        activity = max(0.0, min(
            1.0, float(model.get("activity_energy", 0.0) or 0.0),
        ))
        dim = self.mix_colour(colour, min(0.38, 0.22 + depth * 0.06))
        glow = self.mix_colour(
            colour, min(0.88, 0.58 + activity * 0.22),
        )
        y = float(model.get("label_y", model.get("scene_y", 0.0)))
        cx = float(model.get("label_x", 0.0))
        label_half = max(13.0, float(model.get("label_width", 0.0)) / 2.0)
        rail_left = cx - label_half - 3.0
        rail_right = cx + label_half + 3.0
        rail_y = min(float(model.get("scene_bottom", y + 15.0)) - 3.0, y + 9.0)
        rail_span = max(1.0, rail_right - rail_left)
        self._line(rail_left, rail_y, rail_right, rail_y,
                   colour=self.mix_colour(colour, 0.18), tags=tags)

        if not motion:
            self._line(cx - 3, rail_y, cx + 3, rail_y,
                       colour=dim, width=2, tags=tags)
            return

        dialect = design.dialect
        travelling = (
            profile == "supercruise" or variant == "jump"
            or dialect in {"planetary", "handoff"}
        )
        if travelling:
            local = self._cycle(progress * 8.0, 1.0)
            if variant in {"surface_departure", "orbital_departure", "board"}:
                local = 1.0 - local
            x = rail_left + rail_span * local
            self._line(max(rail_left, x - 5), rail_y, x, rail_y,
                       colour=glow, width=2, tags=tags)
        elif dialect == "survey":
            x = rail_left + rail_span * wave
            self._line(max(rail_left, x - 4), rail_y, x, rail_y,
                       colour=glow, tags=tags)
        elif dialect in {"station", "surface"} and variant in {"docked", "landed"}:
            for offset in (-5, 0, 5):
                self._line(cx + offset, rail_y - 1, cx + offset, rail_y + 1,
                           colour=colour if offset == 0 else dim, tags=tags)
        elif dialect == "carrier":
            offset = (-6, 0, 6)[int(self._cycle(progress * 4.0, 1.0) * 3)]
            self._line(cx + offset - 2, rail_y, cx + offset + 2, rail_y,
                       colour=glow, width=2, tags=tags)
        else:
            half = 2.0 + wave * (6.0 if dialect in {"fsd", "hazard"} else 3.0)
            self._line(cx - half, rail_y, cx + half, rail_y,
                       colour=glow, width=2 if wave > 0.72 else 1, tags=tags)

        # A state change gets one quiet resolving glint; live events only lift
        # its brightness through activity_energy and do not add another packet.
        transition = model.get("transition_progress")
        if transition is not None:
            transition = max(0.0, min(1.0, float(transition)))
            x = rail_left + rail_span * self._ease(transition)
            self._line(max(rail_left, x - 5), rail_y, x, rail_y,
                       colour=colour, width=2, tags=tags)

    def draw_state(self, model, phase, *, tags="nav_state_core", motion=True):
        profile = str(model.get("motion_profile") or "flight")
        design = DESIGNS.get(profile, DESIGNS["flight"])
        scene = state_scene(profile)
        level = str(model.get("animation_intensity") or "Standard").title()
        speed, depth = {
            "Calm": (0.78, 0.72),
            "Energetic": (1.18, 1.28),
        }.get(level, (1.0, 1.0))
        progress = self._cycle(phase * speed, scene.period) if motion else 0.18
        activity = max(0.0, min(1.0, float(model.get("activity_energy", 0.0) or 0.0)))
        colour = model["state_color"]
        dim = self.mix_colour(colour, min(0.50, 0.30 + depth * 0.08 + activity * 0.08))
        glow = self.mix_colour(
            colour,
            min(0.92, scene.intensity * (0.88 + depth * 0.12) + activity * 0.10),
        )
        g = self._geometry(model)
        g["motion_depth"] = depth
        g["activity_energy"] = activity

        drawer = getattr(self, f"_draw_{design.dialect}")
        variant = self._resolve_variant(
            profile, model.get("state"), design.variant,
        )
        self._draw_theme_depth(
            g, design.dialect, variant, progress,
            colour, dim, tags,
        )
        self._draw_left_field(
            g, design.dialect, variant, progress,
            colour, dim, glow, tags,
        )
        drawer(g, variant, progress, colour, dim, glow, tags)
        self._draw_context(
            g, profile, variant, progress, model,
            colour, dim, glow, tags,
        )
        self._draw_activity_reaction(
            g, profile, design.dialect, variant, model,
            colour, dim, glow, tags,
        )

    def _draw_theme_depth(self, g, dialect, variant, progress,
                          colour, dim, tags):
        """Paint a restrained parallax bed using only the active theme colour.

        Depth belongs behind the readable state dialect, so these marks are
        deliberately smaller, dimmer, and confined to the two open wings.
        Integer-multiple cycles keep every layer seamless at the loop point.
        """
        depth = max(0.55, min(1.45, float(g.get("motion_depth", 1.0) or 1.0)))
        activity = max(0.0, min(1.0, float(g.get("activity_energy", 0.0) or 0.0)))
        y = g["y"]
        far = self.mix_colour(colour, min(0.29, 0.13 + depth * 0.07 + activity * 0.05))
        near = self.mix_colour(colour, min(0.42, 0.20 + depth * 0.10 + activity * 0.07))
        wings = (
            (g["left"] + 5, g["left_end"] - 5),
            (g["right_start"] + 5, g["right"] - 5),
        )

        if dialect == "flight" and variant == "supercruise":
            count = 3 if depth < 0.9 else (5 if depth < 1.15 else 7)
            for wing_index, (x1, x2) in enumerate(wings):
                span = max(1.0, x2 - x1)
                for index in range(count):
                    local = (progress * 2.0 + index / count + wing_index * 0.13) % 1.0
                    accelerated = local * local
                    x = x1 + span * accelerated
                    lane = (-9, -4, 4, 9)[index % 4]
                    py = y + lane * (1.0 - accelerated * 0.55)
                    length = 3 + accelerated * (9 + depth * 5)
                    self._line(max(x1, x - length), py, x, py,
                               colour=far, tags=tags)
            return

        if dialect == "fsd" and variant == "jump":
            count = 4 if depth < 1.1 else 6
            for wing_index, (x1, x2) in enumerate(wings):
                span = max(1.0, x2 - x1)
                for index in range(count):
                    local = (progress * 2.0 + index / count + wing_index * 0.17) % 1.0
                    x = x1 + span * local
                    lane = (-9, -5, 5, 9)[index % 4]
                    length = 4 + local * (10 + depth * 7)
                    self._line(max(x1, x - length), y + lane, x, y + lane,
                               colour=near if local > 0.72 else far, tags=tags)
            return

        if dialect == "hazard" and variant == "asteroid":
            count = 3 if depth < 1.1 else 5
            for wing_index, (x1, x2) in enumerate(wings):
                span = max(1.0, x2 - x1)
                for index in range(count):
                    local = (progress * 2.0 + index / count + wing_index * 0.21) % 1.0
                    x = x1 + span * local
                    py = y + math.sin(index * 2.3 + progress * math.tau * 2.0) * 9
                    radius = 0.8 + (index % 2) * 0.6
                    self.canvas.create_polygon(
                        x, py - radius, x + radius, py,
                        x, py + radius, x - radius, py,
                        fill="#010101", outline=far, tags=tags,
                    )
            return

        # Other modes get a quiet two-speed registration layer rather than a
        # generic particle field. It gives the instrument depth without
        # obscuring the state-specific geometry drawn above it.
        count = 2 if depth < 1.1 else 3
        for wing_index, (x1, x2) in enumerate(wings):
            span = max(1.0, x2 - x1)
            for index in range(count):
                local = (progress * 0.5 + index / count + wing_index * 0.19) % 1.0
                x = x1 + span * local
                tick = 2 + depth
                self._line(x, y - tick, x, y + tick,
                           colour=far, tags=tags)

    def _draw_activity_reaction(self, g, profile, dialect, variant, model,
                                colour, dim, glow, tags):
        """Let a live journal event energise the sustained instrument.

        The event renderer owns the recognisable event symbol. This layer is
        connective tissue: a field response and a left-to-right hand-off that
        makes the whole instrument react as one without crossing the label.
        """
        kind = str(model.get("activity_kind") or "")
        energy = max(0.0, min(1.0, float(model.get("activity_energy", 0.0) or 0.0)))
        if not kind or energy <= 0.01:
            return
        progress = max(0.0, min(1.0, float(model.get("activity_progress", 0.0) or 0.0)))
        family = event_scene(kind).family
        y = g["y"]
        tone = self.mix_colour(colour, min(0.98, 0.58 + energy * 0.40))
        shadow = self.mix_colour(colour, min(0.62, 0.24 + energy * 0.34))

        # Route, survey, resource and clearance events visibly pass through
        # the protected centre aperture instead of painting across its text.
        if family in {"route", "scope", "resource", "clearance", "signal"}:
            if progress < 0.44:
                local = self._ease(progress / 0.44)
                x1, x2 = g["left"] + 4, g["left_end"] - 2
                x = x1 + (x2 - x1) * local
                self._line(max(x1, x - 10 - energy * 8), y, x, y,
                           colour=tone, width=2, tags=tags)
                self._dot(x, y, tone, radius=1.1 + energy * 0.55, tags=tags)
            elif progress < 0.57:
                pulse = math.sin(((progress - 0.44) / 0.13) * math.pi)
                for x in (g["left_end"], g["right_start"]):
                    self._line(x, y - (3 + pulse * 5), x, y + (3 + pulse * 5),
                               colour=tone, width=2, tags=tags)
            else:
                local = self._ease((progress - 0.57) / 0.43)
                x1, x2 = g["right_start"] + 2, g["right"] - 4
                x = x1 + (x2 - x1) * local
                self._line(max(x1, x - 10 - energy * 8), y, x, y,
                           colour=tone, width=2, tags=tags)
                self._dot(x, y, tone, radius=1.1 + energy * 0.55, tags=tags)

        if family == "scope":
            # A scope event briefly widens both existing scan fields.
            width = 5 + energy * 11
            for cx in (g["left_center"], g["right_center"]):
                self._arc(cx - width, y - 5, cx + width, y + 5,
                          18, 144, shadow, tags=tags)
                self._arc(cx - width, y - 5, cx + width, y + 5,
                          198, 144, shadow, tags=tags)
        elif family == "resource":
            # Prospector/refinery activity converges as fragments, matching
            # mining rather than borrowing the route or FSD vocabulary.
            center = g["right_center"]
            for index, offset in enumerate((-8, -3, 4, 9)):
                x = g["right"] - 7 - ((g["right"] - center - 7) * energy)
                py = y + offset * (1.0 - energy * 0.55)
                self._dot(x - index * 3, py, tone if index < 2 else shadow,
                          radius=1.0 + energy * 0.4, tags=tags)
        elif family in {"hazard", "signal"}:
            # Warning energy shears the rails; it does not flash a second
            # generic warning icon over the state label.
            shear = energy * 6
            for x1, x2, direction in (
                (g["left"] + 6, g["left_end"] - 4, 1),
                (g["right_start"] + 4, g["right"] - 6, -1),
            ):
                self._line(x1, y - shear * direction, x2, y + shear * direction,
                           colour=shadow, width=2, tags=tags)
        elif family in {"charge", "arrival", "docking", "surface", "vehicle"}:
            # Strong state changes brighten only the inboard couplers. The
            # event-specific renderer supplies the recognisable motion.
            height = 3 + energy * 7
            self._line(g["left_end"], y - height, g["left_end"], y + height,
                       colour=tone, width=2, tags=tags)
            self._line(g["right_start"], y - height, g["right_start"], y + height,
                       colour=tone, width=2, tags=tags)

    @staticmethod
    def _resolve_variant(profile, state, default):
        """Refine shared motion profiles using the exact displayed game state."""
        state = str(state or "").upper()
        if profile == "flight" and state == "MULTICREW":
            return "multicrew"
        if profile == "supercruise" and state == "TAXI":
            return "taxi"
        if profile == "scanner":
            return "dss" if state == "DSS" else "fss"
        if profile == "map":
            return {
                "GALAXY MAP": "galaxy_map",
                "SYSTEM MAP": "system_map",
                "ORRERY": "orrery",
                "POWER MAP": "power_map",
                "CODEX": "codex",
            }.get(state, default)
        if profile == "surface_vehicle":
            return {
                "NOMAD": "nomad", "SCORPION": "scorpion",
                "RHINO": "rhino",
            }.get(state, "srv")
        if profile == "combat" and state.startswith("INTERDICT"):
            return "interdiction"
        if profile == "fsd_lock":
            return "mass_lock" if state == "MASS LOCK" else "signal"
        if profile == "arrival" and state == "INTERDICTION EVADED":
            return "recovery"
        return default

    def _draw_left_field(self, g, dialect, variant, progress,
                         colour, dim, glow, tags):
        """Fill the left wing with motion belonging to the sustained state.

        The state sigil remains the visual anchor, but it no longer floats on
        an empty rail. Each cockpit dialect owns a quiet secondary field so the
        wing feels alive without reintroducing route, survey, or fuel metrics.
        """
        y = g["y"]
        cx = g["left_center"]
        depth = max(0.55, min(1.45, float(g.get("motion_depth", 1.0) or 1.0)))
        activity = max(0.0, min(1.0, float(g.get("activity_energy", 0.0) or 0.0)))
        x1 = g["left"] + 8
        x2 = g["left_end"] - 7
        outer_end = cx - 20
        inner_start = cx + 20
        if outer_end <= x1 or x2 <= inner_start:
            return
        wave = self._wave(progress)

        def moving_packet(start, end, amount, py, tone=glow, length=10,
                          radius=1.0):
            amount = float(amount) % 1.0
            px = start + ((end - start) * amount)
            direction = 1 if end >= start else -1
            tail = px - (direction * length)
            if direction > 0:
                tail = max(start, tail)
            else:
                tail = min(start, tail)
            self._line(tail, py, px, py, colour=tone, tags=tags)
            self._dot(px, py, colour, radius=radius, tags=tags)

        if dialect == "flight":
            lanes = (-5, 5) if variant != "supercruise" else (-7, 0, 7)
            for lane in lanes:
                self._line(x1, y + lane, outer_end, y + lane,
                           colour=self.mix_colour(colour, 0.25), tags=tags)
                self._line(inner_start, y + lane, x2, y + lane,
                           colour=self.mix_colour(colour, 0.22), tags=tags)
            base_count = 4 if variant == "supercruise" else (3 if variant == "fighter" else 2)
            count = max(1, base_count + (1 if depth > 1.12 or activity > 0.72 else 0)
                        - (1 if depth < 0.86 else 0))
            for index in range(count):
                local = (progress + index / count) % 1.0
                lane = lanes[index % len(lanes)]
                moving_packet(x1, outer_end, local, y + lane,
                              length=(16 if variant == "supercruise" else 10)
                              * (0.84 + depth * 0.16),
                              radius=1.25 if variant == "supercruise" else 1.0)
            # The inboard bearing solution breathes toward the state label.
            solution = inner_start + ((x2 - inner_start) * wave)
            self._line(inner_start, y - 3, solution, y - 3,
                       colour=glow, tags=tags)
            self._line(inner_start, y + 3, solution, y + 3,
                       colour=dim, tags=tags)
            self._line(solution, y - 5, solution, y + 5,
                       colour=colour, tags=tags)
            return

        if dialect == "survey":
            sweep = x1 + ((x2 - x1) * wave)
            height = 5 + (wave * 5)
            self._line(sweep, y - height, sweep, y + height,
                       colour=colour, width=2, tags=tags)
            contacts = (0.10, 0.27, 0.48, 0.72, 0.91)
            for index, amount in enumerate(contacts):
                px = x1 + ((x2 - x1) * amount)
                py = y + (-6, 4, -2, 7, -5)[index]
                local = (progress + index * 0.19) % 1.0
                active = local < 0.22
                self._dot(px, py, colour if active else dim,
                          radius=1.55 if active else 0.9, tags=tags)
            # Broken range brackets distinguish a scope from a route line.
            self._arc(cx - 28, y - 12, cx + 28, y + 12,
                      22 + progress * 360, 48, glow, tags=tags)
            self._arc(cx - 28, y - 12, cx + 28, y + 12,
                      202 + progress * 360, 48, dim, tags=tags)
            return

        if dialect == "station":
            cells = 8
            active = min(cells - 1, int(wave * cells))
            for index in range(cells):
                px = x1 + ((x2 - x1) * (index + 0.5) / cells)
                lit = index in {active, cells - 1 - active}
                self._line(px - 5, y, px + 5, y,
                           colour=colour if lit else dim,
                           width=2 if lit else 1, tags=tags)
            return

        if dialect == "surface":
            points = []
            samples = 18
            for index in range(samples):
                amount = index / (samples - 1)
                px = x1 + ((x2 - x1) * amount)
                terrain = (
                    math.sin((amount + progress) * math.tau * 2.0)
                    + 0.45 * math.sin((amount - progress) * math.tau * 5.0)
                )
                points.extend((px, y + 7 + terrain * 1.8))
            self._line(*points, colour=dim, smooth=True, tags=tags)
            scan_x = x1 + ((x2 - x1) * wave)
            self._line(scan_x, y + 3, scan_x, y + 11,
                       colour=glow, tags=tags)
            if variant == "landed":
                for amount in (0.22, 0.50, 0.78):
                    px = x1 + ((x2 - x1) * amount)
                    self._dot(px, y + 7, colour if wave > amount else dim,
                              radius=1.1, tags=tags)
            return

        if dialect == "handoff":
            cells = 7
            active = min(cells - 1, int(wave * cells))
            if variant == "board":
                active = cells - 1 - active
            for index in range(cells):
                px = x1 + ((x2 - x1) * (index + 0.5) / cells)
                tone = colour if index == active else dim
                self.canvas.create_rectangle(
                    px - 3, y - 3, px + 3, y + 3,
                    fill="#010101", outline=tone, tags=tags,
                )
            return

        if dialect == "hazard":
            if variant == "asteroid":
                count = 5 if depth < 0.86 else (7 if depth > 1.12 or activity > 0.7 else 6)
                for index in range(count):
                    local = (progress + index / count) % 1.0
                    px = x1 + ((x2 - x1) * local)
                    py = y + math.sin(index * 2.1 + progress * math.tau) * 7
                    radius = 1.5 + index % 3
                    self.canvas.create_polygon(
                        px, py - radius, px + radius, py,
                        px, py + radius, px - radius, py,
                        fill="#010101", outline=glow if index < 2 else dim,
                        tags=tags,
                    )
                return
            spread = 18 + wave * max(18, (x2 - x1) * 0.28)
            for side in (-1, 1):
                px = cx + side * spread
                self._line(px, y - 9, px, y + 9,
                           colour=colour, width=2, tags=tags)
                self._line(px, y - 9, px - side * 7, y - 9,
                           colour=glow, tags=tags)
                self._line(px, y + 9, px - side * 7, y + 9,
                           colour=glow, tags=tags)
            return

        if dialect == "fsd":
            base_count = 5 if variant in {"charge", "overcharge", "jump"} else 3
            count = max(2, base_count + (1 if depth > 1.12 or activity > 0.68 else 0)
                        - (1 if depth < 0.86 else 0))
            for index in range(count):
                local = (progress + index / count) % 1.0
                moving_packet(x1, outer_end, local, y + (-6, 0, 6)[index % 3],
                              length=13 * (0.86 + depth * 0.14), radius=1.15)
                moving_packet(x2, inner_start, local, y + (6, 0, -6)[index % 3],
                              length=13 * (0.86 + depth * 0.14), radius=1.15)
            return

        if dialect == "carrier":
            for lane in (-6, 0, 6):
                self._line(x1, y + lane, x2, y + lane,
                           colour=self.mix_colour(colour, 0.28), tags=tags)
            count = 4 if depth < 0.86 else (6 if depth > 1.12 or activity > 0.7 else 5)
            for index in range(count):
                local = (progress + index / count) % 1.0
                moving_packet(x1, x2, local, y + (-6, 0, 6)[index % 3],
                              length=18 * (0.86 + depth * 0.14), radius=1.1)
            return

        if dialect == "planetary":
            departing = variant in {"surface_departure", "orbital_departure"}
            amount = 1.0 - wave if departing else wave
            active = min(7, int(amount * 8))
            for index in range(8):
                px = x1 + ((x2 - x1) * (index + 0.5) / 8)
                offset = abs(index - active)
                tone = colour if offset == 0 else (glow if offset == 1 else dim)
                height = 3 + (index % 3) * 2
                self._line(px, y - height, px, y + height,
                           colour=tone, width=2 if offset == 0 else 1,
                           tags=tags)
            self._line(x1, y + 11, x2, y + 4,
                       colour=dim, tags=tags)

    def _draw_flight(self, g, variant, progress, colour, dim, glow, tags):
        y = g["y"]
        cx = g["left_center"]
        fighter = variant == "fighter"
        wave = self._wave(progress)
        # The ship sigil is a live attitude reference.  Normal flight breathes
        # quietly, while fighter and Supercruise states carry more energy.
        amplitude = 0.10 if fighter else (0.065 if variant == "supercruise" else 0.035)
        scale = 1.0 + (amplitude * wave)
        if fighter:
            points = (
                cx + 8 * scale, y,
                cx - 7 * scale, y - 6 * scale,
                cx - 2 * scale, y,
                cx - 7 * scale, y + 6 * scale,
            )
        else:
            points = (
                cx + 8 * scale, y,
                cx - 6 * scale, y - 5 * scale,
                cx - 2 * scale, y,
                cx - 6 * scale, y + 5 * scale,
            )
        self.canvas.create_polygon(
            *points, fill="#010101", outline=colour, width=1, tags=tags,
        )
        bearing = progress * (360 if variant == "supercruise" else 54)
        if variant != "supercruise":
            bearing = 27 * math.sin(progress * math.tau)
        self._arc(cx - 13, y - 10, cx + 13, y + 10,
                  28 + bearing, 124, dim, tags=tags)
        self._arc(cx - 13, y - 10, cx + 13, y + 10,
                  208 + bearing, 124, dim, tags=tags)
        orbit = progress * math.tau
        self._dot(
            cx + math.cos(orbit) * 13,
            y + math.sin(orbit) * 9,
            colour if variant == "supercruise" else glow,
            radius=1.35 if variant == "supercruise" else 1.0,
            tags=tags,
        )
        if variant == "multicrew":
            for index, offset in enumerate((-7, 0, 7)):
                local = (progress + index / 3) % 1.0
                active = local < 0.34
                self._dot(cx + offset, y + 8,
                          colour if active else glow,
                          radius=1.7 if active else 1.1, tags=tags)
            self._line(cx - 7, y + 8, cx + 7, y + 8,
                       colour=dim, tags=tags)

        x1, x2 = g["right_start"] + 5, g["right"] - 4
        span = max(1.0, x2 - x1)
        if variant == "taxi":
            nodes = ((x1, y + 5), (x1 + span * 0.34, y - 5),
                     (x1 + span * 0.68, y + 2), (x2, y - 3))
            self._line(
                *(value for point in nodes for value in point),
                colour=dim, smooth=True, tags=tags,
            )
            active = min(len(nodes) - 1, int(progress * len(nodes)))
            for index, (x, py) in enumerate(nodes):
                self._dot(x, py, colour if index == active else dim,
                          radius=1.8 if index == active else 1, tags=tags)
            return
        if variant == "multicrew":
            crew_x = (x1 + x2) / 2
            self._arc(crew_x - 13, y - 10, crew_x + 13, y + 10,
                      28, 124, glow, tags=tags)
            self._arc(crew_x - 13, y - 10, crew_x + 13, y + 10,
                      208, 124, glow, tags=tags)
            for index, offset in enumerate((-7, 0, 7)):
                pulse = (progress + index / 3) % 1.0
                self._dot(crew_x + offset, y,
                          colour if pulse < 0.34 else dim,
                          radius=2 if pulse < 0.34 else 1.2, tags=tags)
            return
        lanes = (-6, 0, 6) if variant == "supercruise" else (-4, 4)
        packets = 4 if variant == "supercruise" else (3 if fighter else 2)
        if variant == "supercruise":
            # Supercruise is one continuous perspective flow—no separate gate
            # or target object. The rails converge while streaks lengthen and
            # accelerate toward the outboard edge.
            perspective_lanes = (-8, 0, 8)
            for lane in perspective_lanes:
                self._line(x1, y + lane, x2, y + lane * 0.28,
                           colour=self.mix_colour(colour, 0.26), tags=tags)
            depth = max(0.55, min(1.45, float(g.get("motion_depth", 1.0) or 1.0)))
            activity = max(0.0, min(1.0, float(g.get("activity_energy", 0.0) or 0.0)))
            streaks = 5 if depth < 0.86 else (9 if depth > 1.12 or activity > 0.68 else 7)
            for index in range(streaks):
                local = (progress + index / streaks) % 1.0
                accelerated = local * local
                x = x1 + span * accelerated
                lane = perspective_lanes[index % len(perspective_lanes)]
                py = y + lane * (1.0 - accelerated * 0.72)
                length = 7 + accelerated * (25 + depth * 5 + activity * 5)
                tone = colour if local > 0.72 else glow
                self._line(max(x1, x - length), py, x, py,
                           colour=tone, width=2 if local > 0.72 else 1,
                           tags=tags)
                if index < 3:
                    self._dot(x, py, colour, radius=1.1, tags=tags)

            # A compression front travels with the flow and fades naturally at
            # both edges, reading as speed distortion rather than another icon.
            compression_x = x1 + span * progress
            edge = math.sin(progress * math.pi)
            front_height = edge * 10
            if front_height > 0.5:
                front_colour = self.mix_colour(
                    colour, 0.22 + edge * 0.78,
                )
                self._line(compression_x, y - front_height,
                           compression_x, y + front_height,
                           colour=front_colour,
                           width=2 if edge > 0.55 else 1, tags=tags)
            return
        elif fighter:
            target_x = x1 + span * 0.68
            size = 7 + (self._wave(progress) * 3)
            for side in (-1, 1):
                x = target_x + side * size
                self._line(x, y - 7, x, y + 7,
                           colour=glow, tags=tags)
                self._line(x, y - 7, x - side * 5, y - 7,
                           colour=colour, tags=tags)
                self._line(x, y + 7, x - side * 5, y + 7,
                           colour=colour, tags=tags)
        else:
            # Normal-space flight reads as an attitude/vector ladder, not a
            # Supercruise star stream. The caret tracks a restrained bearing
            # oscillation while pitch ticks remain fixed to the ship plane.
            vector_x = x1 + span * (0.48 + 0.18 * math.sin(progress * math.tau))
            self._line(x1, y, x2, y, colour=dim, tags=tags)
            for index, offset in enumerate((-9, -5, 5, 9)):
                length = 8 if abs(offset) == 5 else 5
                self._line(vector_x - length, y + offset,
                           vector_x + length, y + offset,
                           colour=glow if abs(offset) == 5 else dim, tags=tags)
            self.canvas.create_polygon(
                vector_x, y - 3, vector_x + 5, y,
                vector_x, y + 3, vector_x - 5, y,
                fill="#010101", outline=colour, tags=tags,
            )
            return
        for index in range(packets):
            local = (progress + index / packets) % 1.0
            x = x1 + span * local
            lane = lanes[index % len(lanes)]
            length = 20 if variant == "supercruise" else 12
            self._line(max(x1, x - length), y + lane, x, y + lane,
                       colour=glow, width=2 if variant == "supercruise" else 1,
                       tags=tags)
            self._dot(x, y + lane, colour, radius=1.2, tags=tags)

    def _draw_survey(self, g, variant, progress, colour, dim, glow, tags):
        y = g["y"]
        cx = g["left_center"]
        map_variants = {
            "map", "galaxy_map", "system_map", "orrery", "power_map", "codex",
        }
        if variant in map_variants:
            points = (
                (cx - 12, y + 6), (cx - 3, y - 7),
                (cx + 10, y + 2), (cx + 15, y - 5),
            )
            flat = tuple(value for point in points for value in point)
            self._line(*flat, colour=dim, width=1, tags=tags, smooth=True)
            active = min(len(points) - 1, int(progress * len(points)))
            for index, (x, py) in enumerate(points):
                self._dot(x, py, colour if index == active else dim,
                          radius=2 if index == active else 1.2, tags=tags)
        elif variant == "dss":
            self._arc(cx - 13, y - 11, cx + 13, y + 11,
                      0, 360, dim, tags=tags)
            for index in range(3):
                angle = progress * math.tau + index * math.tau / 3
                px = cx + math.cos(angle) * 11
                py = y + math.sin(angle) * 8
                self._dot(px, py, colour if index == 0 else glow,
                          radius=1.5, tags=tags)
                self._line(px, py, cx, y, colour=dim, tags=tags)
        else:
            radius_x, radius_y = (15, 10) if variant == "fss" else (13, 9)
            self._arc(cx - radius_x, y - radius_y, cx + radius_x, y + radius_y,
                      18, 144, dim, tags=tags)
            self._arc(cx - radius_x, y - radius_y, cx + radius_x, y + radius_y,
                      198, 144, dim, tags=tags)
            # A complete rotation keeps the scope sweep continuous at the
            # animation seam while the broken range arcs retain the HUD shape.
            angle = (-0.5 * math.pi) + (progress * math.tau)
            self._line(cx, y,
                       cx + math.cos(angle) * radius_x,
                       y + math.sin(angle) * radius_y,
                       colour=glow, width=2 if variant == "fss" else 1,
                       tags=tags)
            self._dot(cx, y, colour, radius=1.4, tags=tags)

        x1, x2 = g["right_start"] + 5, g["right"] - 5
        span = max(1.0, x2 - x1)
        if variant == "dss":
            # DSS is planetary probe coverage: a planet disc, orbit arcs and
            # three moving impact solutions instead of an FSS frequency trace.
            pcx = x1 + span * 0.63
            radius_x, radius_y = 18, 11
            self._arc(pcx - radius_x, y - radius_y,
                      pcx + radius_x, y + radius_y,
                      0, 360, dim, tags=tags)
            coverage = 30 + (progress * 300)
            self._arc(pcx - radius_x, y - radius_y,
                      pcx + radius_x, y + radius_y,
                      90, coverage, glow, width=2, tags=tags)
            for index in range(3):
                angle = progress * math.tau + index * math.tau / 3
                px = pcx + math.cos(angle) * (radius_x + 8)
                py = y + math.sin(angle) * (radius_y + 3)
                self._line(px, py, pcx, y, colour=dim, tags=tags)
                self._dot(px, py, colour if index == 0 else glow,
                          radius=1.4, tags=tags)
            return
        if variant == "fss":
            # The FSS response is a compact frequency spectrum with an exact
            # tuning cursor and resolved signal spikes.
            baseline = y + 7
            self._line(x1, baseline, x2, baseline, colour=dim, tags=tags)
            trace = []
            samples = (0, -2, 1, -7, 2, -4, 0, -9, 2, -3, 0)
            for index, sample in enumerate(samples):
                x = x1 + span * index / (len(samples) - 1)
                trace.extend((x, baseline + sample))
            self._line(*trace, colour=glow, tags=tags, smooth=True)
            cursor_x = x1 + span * progress
            self._line(cursor_x, y - 10, cursor_x, y + 10,
                       colour=colour, width=2, tags=tags)
            self._dot(cursor_x, baseline, colour, radius=1.4, tags=tags)
            return
        if variant == "system_map":
            star_x = x1 + 17
            self._dot(star_x, y, colour, radius=3, tags=tags)
            for index, orbit in enumerate((28, 49, 72)):
                self._arc(star_x - 4, y - 4 - index,
                          star_x + orbit, y + 4 + index,
                          200, 320, dim, tags=tags)
                angle = progress * math.tau + index * 1.7
                px = star_x + (orbit - 4) * (0.5 + 0.5 * math.cos(angle))
                py = y + math.sin(angle) * (3 + index)
                self._dot(px, py, glow, radius=1.2, tags=tags)
            return
        if variant == "orrery":
            center = (x1 + x2) / 2
            for index, (rx, ry) in enumerate(((25, 7), (48, 10), (70, 13))):
                self._arc(center - rx, y - ry, center + rx, y + ry,
                          0, 360, dim, tags=tags)
                angle = progress * math.tau * (1.0 - index * 0.17) + index * 2.1
                self._dot(center + math.cos(angle) * rx,
                          y + math.sin(angle) * ry,
                          colour if index == 0 else glow,
                          radius=1.4, tags=tags)
            return
        if variant == "power_map":
            nodes = (
                (x1 + span * 0.12, y), (x1 + span * 0.36, y - 7),
                (x1 + span * 0.58, y + 6), (x1 + span * 0.82, y - 2),
            )
            self._line(*(value for point in nodes for value in point),
                       colour=dim, tags=tags, smooth=True)
            active = min(3, int(progress * 4))
            for index, (x, py) in enumerate(nodes):
                radius = 4 if index == active else 3
                self.canvas.create_polygon(
                    x, py - radius, x + radius, py,
                    x, py + radius, x - radius, py,
                    fill="#010101", outline=colour if index == active else dim,
                    tags=tags,
                )
            return
        if variant == "codex":
            cell_width = span / 5
            active = min(4, int(progress * 5))
            for index in range(5):
                x = x1 + cell_width * (index + 0.5)
                tone = colour if index == active else dim
                self.canvas.create_rectangle(
                    x - 7, y - 6, x + 7, y + 6,
                    fill="#010101", outline=tone, tags=tags,
                )
                if index < active:
                    self._line(x - 3, y, x, y + 3, x + 5, y - 4,
                               colour=glow, tags=tags)
            return
        if variant in {"map", "galaxy_map"}:
            offsets = (5, -5, 3, -7, 1)
            route = []
            for index, offset in enumerate(offsets):
                x = x1 + span * index / (len(offsets) - 1)
                route.extend((x, y + offset))
            self._line(*route, colour=dim, tags=tags, smooth=True)
            active = min(len(offsets) - 1, int(progress * len(offsets)))
            for index, offset in enumerate(offsets):
                x = x1 + span * index / (len(offsets) - 1)
                self._dot(x, y + offset,
                          colour if index == active else dim,
                          radius=1.7 if index == active else 1, tags=tags)
            return

        # General exploration uses the discovery sweep and resolved contacts.
        sweep_x = x1 + span * progress
        self._line(sweep_x, y - 9, sweep_x, y + 9,
                   colour=glow, tags=tags)
        contacts = (0.16, 0.38, 0.63, 0.84)
        for index, amount in enumerate(contacts):
            x = x1 + span * amount
            py = y + (-6, 4, -2, 7)[index]
            distance = abs(amount - progress)
            tone = colour if distance < 0.09 else dim
            self._dot(x, py, tone, radius=1.6 if tone == colour else 1,
                      tags=tags)

    def _draw_station(self, g, variant, progress, colour, dim, glow, tags):
        y = g["y"]
        cx = g["left_center"]
        travel = self._wave(progress)
        offset = 7 + ((1.0 - travel) * 7)
        self.canvas.create_rectangle(
            cx - 3, y - 3, cx + 3, y + 3,
            fill="#010101", outline=colour, width=1, tags=tags,
        )
        for side in (-1, 1):
            x = cx + side * offset
            inward = x - side * 6
            self._line(x, y - 9, x, y + 9, colour=glow, tags=tags)
            self._line(x, y - 9, inward, y - 9, colour=dim, tags=tags)
            self._line(x, y + 9, inward, y + 9, colour=dim, tags=tags)

        x1, x2 = g["right_start"] + 6, g["right"] - 5
        # Sustained DOCKED means the pad is secured—not that clearance is
        # still being requested. The right response therefore becomes a
        # locked landing-pad plan with four retained clamps.
        center = x1 + (x2 - x1) * 0.58
        pad_width = min(48, (x2 - x1) * 0.34)
        self.canvas.create_polygon(
            center - pad_width, y - 10,
            center + pad_width, y - 10,
            center + pad_width * 0.72, y + 10,
            center - pad_width * 0.72, y + 10,
            fill="#010101", outline=dim, tags=tags,
        )
        self.canvas.create_rectangle(
            center - 8, y - 5, center + 8, y + 5,
            fill="#010101", outline=glow, tags=tags,
        )
        clamp = 3 + (self._wave(progress) * 2)
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            px = center + sx * (11 + clamp)
            py = y + sy * 7
            self._line(px, py, px - sx * 5, py,
                       colour=colour, width=2, tags=tags)
        self._dot(center, y, colour, radius=1.4, tags=tags)

    def _draw_surface(self, g, variant, progress, colour, dim, glow, tags):
        y = g["y"]
        cx = g["left_center"]
        wave = self._wave(progress)
        if variant == "landed":
            body_y = y - (wave * 0.8)
            self._arc(cx - 17, y - 3, cx + 17, y + 15,
                      18, 144, glow, tags=tags)
            self._line(cx - 9, body_y + 6, cx + 9, body_y + 6,
                       colour=dim, tags=tags)
            self._line(cx - 5, body_y + 6, cx - 9, y + 11,
                       colour=colour, tags=tags)
            self._line(cx + 5, body_y + 6, cx + 9, y + 11,
                       colour=colour, tags=tags)
            for gear_x in (cx - 9, cx + 9):
                self._dot(gear_x, y + 11, colour if wave > 0.52 else dim,
                          radius=1.0 + wave * 0.55, tags=tags)
        elif variant in {"vehicle", "srv", "scorpion", "rhino", "nomad"}:
            bob = math.sin(progress * math.tau) * (0.9 if variant == "nomad" else 0.65)
            body_y = y + bob
            self.canvas.create_rectangle(
                cx - (12 if variant == "nomad" else 10), body_y - 5,
                cx + (11 if variant == "nomad" else 9), body_y + 4,
                fill="#010101", outline=colour, tags=tags,
            )
            mast_x = cx + 2 + math.sin(progress * math.tau) * 2
            self._line(cx - 4, body_y - 5, mast_x, body_y - 10,
                       colour=dim, tags=tags)
            wheel_tone = colour if wave > 0.45 else glow
            wheel_radius = 1.9 + wave * 0.45
            self._dot(cx - 7, y + 7, wheel_tone,
                      radius=wheel_radius, tags=tags)
            self._dot(cx + 6, y + 7, wheel_tone,
                      radius=wheel_radius, tags=tags)
            if variant == "nomad":
                self._dot(cx, y + 7, colour if wave < 0.5 else glow,
                          radius=1.45 + ((1.0 - wave) * 0.35), tags=tags)
        else:
            # A minimal human locator—not a character illustration—keeps the
            # on-foot state distinct at the HUD's very small scale. A soft
            # suit-beacon pulse adds life without falsely implying movement.
            body_y = y + math.sin(progress * math.tau) * 0.6
            beacon = 4 + wave * 4
            self._arc(cx - beacon, body_y - 7 - beacon * 0.55,
                      cx + beacon, body_y - 7 + beacon * 0.55,
                      15, 150, glow, tags=tags)
            self._arc(cx - beacon, body_y - 7 - beacon * 0.55,
                      cx + beacon, body_y - 7 + beacon * 0.55,
                      195, 150, glow, tags=tags)
            self._dot(cx, body_y - 7, colour, radius=2, tags=tags)
            self._line(cx, body_y - 4, cx, body_y + 4,
                       colour=glow, width=2, tags=tags)
            self._line(cx, body_y, cx - 5, body_y + 3,
                       colour=dim, tags=tags)
            self._line(cx, body_y, cx + 5, body_y + 3,
                       colour=dim, tags=tags)
            self._line(cx, body_y + 4, cx - 4, body_y + 10,
                       colour=dim, tags=tags)
            self._line(cx, body_y + 4, cx + 4, body_y + 10,
                       colour=dim, tags=tags)

        x1, x2 = g["right_start"] + 5, g["right"] - 5
        if variant == "landed":
            # A stable ground plane and three confirmed contact points make
            # LANDED read as weight-on-gear rather than continued travel.
            ground_y = y + 7
            self._line(x1, ground_y, x2, ground_y,
                       colour=dim, tags=tags)
            center = (x1 + x2) / 2
            self._line(center - 14, y - 3, center + 14, y - 3,
                       colour=glow, width=2, tags=tags)
            contacts = (center - 22, center, center + 22)
            for index, x in enumerate(contacts):
                self._line(x, y - 3, x, ground_y,
                           colour=glow, tags=tags)
                pulse = (progress + index / 3) % 1.0
                self._dot(x, ground_y,
                          colour if pulse < 0.34 else dim,
                          radius=1.7 if pulse < 0.34 else 1.1, tags=tags)
            return
        if variant == "foot":
            span = x2 - x1
            for index in range(6):
                local = (progress + index / 6) % 1.0
                x = x1 + span * local
                py = y + (-4 if index % 2 else 4)
                self.canvas.create_oval(
                    x - 3, py - 1.5, x + 3, py + 1.5,
                    fill=glow if index < 2 else dim, outline="", tags=tags,
                )
            return

        pattern = (-1, 4, -5, 2, -3, 5, 0)
        period = 18 * len(pattern)
        offset = progress * period
        points = []
        x = x1 - offset
        index = 0
        while x <= x2 + period:
            if x1 <= x <= x2:
                points.extend((x, y + pattern[index % len(pattern)]))
            x += 18
            index += 1
        if len(points) >= 4:
            self._line(*points, colour=dim, tags=tags, smooth=True)
        if variant in {"vehicle", "srv", "scorpion", "rhino", "nomad"}:
            contact_count = 3 if variant == "nomad" else 2
            for index in range(contact_count):
                marker_x = x1 + (x2 - x1) * (index + 1) / (contact_count + 1)
                self._dot(marker_x, y - 2,
                          colour if index == 0 else glow,
                          radius=1.5, tags=tags)

    def _draw_handoff(self, g, variant, progress, colour, dim, glow, tags):
        y = g["y"]
        cx = g["left_center"]
        left_box, right_box = cx - 11, cx + 11
        for x in (left_box, right_box):
            self.canvas.create_rectangle(
                x - 4, y - 5, x + 4, y + 5,
                fill="#010101", outline=dim, tags=tags,
            )
        self._line(left_box + 4, y, right_box - 4, y,
                   colour=dim, tags=tags)
        travel = self._wave(progress)
        if variant == "board":
            travel = 1.0 - travel
        elif variant == "switch":
            travel = 0.5 + (0.5 * math.sin(progress * math.tau))
        marker_x = left_box + (right_box - left_box) * travel
        self._dot(marker_x, y, colour, radius=2, tags=tags)
        if variant == "switch":
            mirror_x = left_box + (right_box - left_box) * (1.0 - travel)
            self._dot(mirror_x, y, glow, radius=1.4, tags=tags)

        x1, x2 = g["right_start"] + 6, g["right"] - 5
        span = x2 - x1
        bay_x = x2 - 13
        self._line(bay_x, y - 10, x2, y - 10,
                   colour=dim, tags=tags)
        self._line(bay_x, y + 10, x2, y + 10,
                   colour=dim, tags=tags)
        self._line(x2, y - 10, x2, y + 10,
                   colour=glow, width=2, tags=tags)
        if variant == "deploy":
            vehicle_x = bay_x - (span - 24) * travel
        elif variant == "board":
            vehicle_x = x1 + (span - 24) * travel
        else:
            vehicle_x = x1 + (span - 24) * travel
        self._line(x1, y + 7, bay_x, y + 7,
                   colour=dim, tags=tags)
        self.canvas.create_rectangle(
            vehicle_x - 6, y - 4, vehicle_x + 6, y + 3,
            fill="#010101", outline=colour, tags=tags,
        )
        self._dot(vehicle_x - 4, y + 5, glow, radius=1.3, tags=tags)
        self._dot(vehicle_x + 4, y + 5, glow, radius=1.3, tags=tags)
        if variant == "switch":
            mirror_x = x1 + (span - 24) * (1.0 - travel)
            self.canvas.create_rectangle(
                mirror_x - 5, y - 8, mirror_x + 5, y - 2,
                fill="#010101", outline=glow, tags=tags,
            )
        else:
            direction = -1 if variant == "deploy" else 1
            self._line(vehicle_x - direction * 12, y,
                       vehicle_x - direction * 5, y,
                       colour=glow, width=2, tags=tags)

    def _draw_hazard(self, g, variant, progress, colour, dim, glow, tags):
        y = g["y"]
        cx = g["left_center"]
        if variant == "asteroid":
            angle = progress * math.tau
            points = []
            radii = (13, 10, 14, 9, 12, 11, 13)
            for index, radius in enumerate(radii):
                theta = angle + index * math.tau / len(radii)
                points.extend((cx + math.cos(theta) * radius,
                               y + math.sin(theta) * radius * 0.72))
            self.canvas.create_polygon(
                *points, fill="#010101", outline=colour, width=1, tags=tags,
            )
            self._line(cx - 8, y - 5, cx + 6, y + 6,
                       colour=dim, tags=tags)
        elif variant == "mass_lock":
            radius = 7 + (self._wave(progress) * 5)
            self._dot(cx, y, colour, radius=3, tags=tags)
            self._arc(cx - radius, y - radius, cx + radius, y + radius,
                      20, 140, glow, width=2, tags=tags)
            self._arc(cx - radius, y - radius, cx + radius, y + radius,
                      200, 140, glow, width=2, tags=tags)
            self._line(cx - 13, y + 10, cx + 13, y - 10,
                       colour=colour, width=2, tags=tags)
        elif variant == "signal":
            radius = 8 + (self._wave(progress) * 6)
            self.canvas.create_polygon(
                cx, y - 7, cx + 7, y, cx, y + 7, cx - 7, y,
                fill="#010101", outline=colour, tags=tags,
            )
            self._arc(cx - radius, y - radius, cx + radius, y + radius,
                      145, 70, glow, tags=tags)
            self._arc(cx - radius, y - radius, cx + radius, y + radius,
                      325, 70, glow, tags=tags)
            self._dot(cx, y, colour, radius=1.7, tags=tags)
        elif variant == "interdiction":
            radius = 13
            rotation = progress * 180
            for inset in (0, 5):
                tone = glow if inset == 0 else dim
                self._arc(cx - radius + inset, y - radius + inset,
                          cx + radius - inset, y + radius - inset,
                          25 + rotation, 105, tone,
                          width=2 if inset == 0 else 1, tags=tags)
                self._arc(cx - radius + inset, y - radius + inset,
                          cx + radius - inset, y + radius - inset,
                          205 + rotation, 105, tone,
                          width=2 if inset == 0 else 1, tags=tags)
            self._dot(cx, y, colour, radius=2, tags=tags)
        else:
            radius = 11 + (self._wave(progress) * 3)
            self.canvas.create_polygon(
                cx, y - radius, cx + radius, y,
                cx, y + radius, cx - radius, y,
                fill="#010101", outline=colour, width=2, tags=tags,
            )
            self._line(cx, y - 6, cx, y + 3,
                       colour=glow, width=2, tags=tags)
            self._dot(cx, y + 7, colour, radius=1.3, tags=tags)

        x1, x2 = g["right_start"] + 4, g["right"] - 5
        span = x2 - x1
        if variant == "asteroid":
            for index in range(7):
                local = (progress + index / 7) % 1.0
                x = x1 + span * local
                py = y + math.sin(index * 2.2 + progress * math.tau) * 8
                radius = 2 + index % 3
                self.canvas.create_polygon(
                    x, py - radius, x + radius, py,
                    x, py + radius, x - radius, py,
                    fill="#010101", outline=dim if index > 1 else glow,
                    tags=tags,
                )
        elif variant == "mass_lock":
            center = g["right_center"]
            wave = self._wave(progress)
            self._dot(center, y, colour, radius=3.2, tags=tags)
            for index in range(3):
                radius = 7 + index * 7 + wave * 3
                tone = glow if index == 0 else dim
                self._arc(center - radius, y - radius * 0.55,
                          center + radius, y + radius * 0.55,
                          25, 130, tone, tags=tags)
                self._arc(center - radius, y - radius * 0.55,
                          center + radius, y + radius * 0.55,
                          205, 130, tone, tags=tags)
            barrier = center - 32
            self._line(barrier, y - 9, barrier, y + 9,
                       colour=colour, width=2, tags=tags)
            for index in range(3):
                x = x1 + index * 13
                self._line(x, y - 4, x + 7, y, x, y + 4,
                           colour=glow, tags=tags)
        elif variant == "signal":
            target_x = x1 + span * 0.76
            samples = []
            for index in range(13):
                x = x1 + span * index / 12
                envelope = 1.0 - abs((index / 12) - 0.72)
                py = y + math.sin(index * 1.7 + progress * math.tau) * 6 * envelope
                samples.extend((x, py))
            self._line(*samples, colour=glow, smooth=True, tags=tags)
            size = 6 + self._wave(progress) * 2
            self.canvas.create_polygon(
                target_x, y - size, target_x + size, y,
                target_x, y + size, target_x - size, y,
                fill="#010101", outline=colour, tags=tags,
            )
        elif variant == "interdiction":
            target_x = x1 + span * 0.72
            for side in (-1, 1):
                points = []
                for index in range(9):
                    amount = index / 8
                    x = x1 + (target_x - x1) * amount
                    amplitude = (1.0 - amount) * 9
                    py = y + side * amplitude * math.sin(
                        progress * math.tau + amount * math.pi,
                    )
                    points.extend((x, py))
                self._line(*points, colour=glow, width=2,
                           smooth=True, tags=tags)
            self._arc(target_x - 9, y - 9, target_x + 9, y + 9,
                      35, 110, colour, width=2, tags=tags)
            self._arc(target_x - 9, y - 9, target_x + 9, y + 9,
                      215, 110, colour, width=2, tags=tags)
            self._dot(target_x, y, colour, radius=1.5, tags=tags)
        else:
            target_x = x1 + span * 0.68
            radius = 7 + self._wave(progress) * 2
            for side in (-1, 1):
                x = target_x + side * radius
                self._line(x, y - 8, x, y + 8,
                           colour=colour, width=2, tags=tags)
                self._line(x, y - 8, x - side * 5, y - 8,
                           colour=glow, tags=tags)
                self._line(x, y + 8, x - side * 5, y + 8,
                           colour=glow, tags=tags)
            for index in range(3):
                local = (progress + index / 3) % 1.0
                x = x1 + (target_x - x1) * local
                py = y + (-6, 0, 6)[index]
                self._line(max(x1, x - 12), py, x, py,
                           colour=glow, tags=tags)
                self._dot(x, py, colour, radius=1.2, tags=tags)

    def _draw_fsd(self, g, variant, progress, colour, dim, glow, tags):
        y = g["y"]
        cx = g["left_center"]
        wave = self._wave(progress)
        if variant in {"charge", "overcharge"}:
            radius = 14 - (wave * 6)
        elif variant in {"arrival", "cooldown", "recovery"}:
            radius = 7 + (wave * 8)
        else:
            radius = 9 + (wave * 3)
        self._arc(cx - radius, y - radius, cx + radius, y + radius,
                  20, 140, glow, width=2, tags=tags)
        self._arc(cx - radius, y - radius, cx + radius, y + radius,
                  200, 140, glow, width=2, tags=tags)
        self._dot(cx, y, colour, radius=2 if variant == "jump" else 1.4,
                  tags=tags)

        x1, x2 = g["right_start"] + 4, g["right"] - 4
        span = x2 - x1
        if variant == "recovery":
            # Interdiction evaded is an escape/recovery vector, not a normal
            # hyperspace arrival. The lanes reopen and terminate in a clear
            # resolved check at the outboard edge.
            spread = 3 + self._wave(progress) * 7
            self._line(x1, y, x2 - 18, y - spread,
                       colour=glow, width=2, tags=tags)
            self._line(x1, y, x2 - 18, y + spread,
                       colour=glow, width=2, tags=tags)
            self._line(x2 - 14, y, x2 - 8, y + 6, x2, y - 7,
                       colour=colour, width=2, tags=tags)
        elif variant in {"charge", "overcharge"}:
            count = 6 if variant == "overcharge" else 5
            for index in range(count):
                local = (progress + index / count) % 1.0
                x = x2 - span * local
                size = 4 + local * (5 if variant == "overcharge" else 3)
                self._line(x + size, y - size, x, y, x + size, y + size,
                           colour=colour if index < 2 else glow,
                           width=2, tags=tags)
            if variant == "overcharge":
                points = []
                for index in range(9):
                    x = x1 + span * index / 8
                    py = y + (7 if (index + int(progress * 16)) % 2 else -7)
                    points.extend((x, py))
                self._line(*points, colour=glow, width=1, tags=tags)
        elif variant == "jump":
            for index in range(8):
                local = (progress + index / 8) % 1.0
                x = x1 + span * local
                py = y + ((index % 5) - 2) * 4
                length = 14 + local * 30
                self._line(max(x1, x - length), py, x, py,
                           colour=colour if index < 2 else glow,
                           width=2 if index < 2 else 1, tags=tags)
        elif variant in {"arrival", "cooldown"}:
            for index in range(3):
                local = (progress + index / 3) % 1.0
                ring_x = x1 + span * (0.78 if variant == "arrival" else 0.42)
                ring = 4 + local * 18
                tone = colour if local < 0.36 else dim
                self._arc(ring_x - ring, y - ring * 0.55,
                          ring_x + ring, y + ring * 0.55,
                          20, 140, tone, tags=tags)
                self._arc(ring_x - ring, y - ring * 0.55,
                          ring_x + ring, y + ring * 0.55,
                          200, 140, tone, tags=tags)

    def _draw_carrier(self, g, variant, progress, colour, dim, glow, tags):
        y = g["y"]
        cx = g["left_center"]
        self.canvas.create_polygon(
            cx - 17, y - 5, cx + 10, y - 5,
            cx + 17, y, cx + 10, y + 5,
            cx - 17, y + 5, cx - 12, y,
            fill="#010101", outline=colour, width=1, tags=tags,
        )
        self._line(cx - 10, y, cx + 10, y,
                   colour=glow, width=2, tags=tags)
        for offset in (-8, 8):
            self._line(cx + offset, y - 5, cx + offset, y + 5,
                       colour=dim, tags=tags)
        # A smooth, reversible power packet runs through the carrier spine;
        # engine apertures breathe harder in transit than on arrival.
        carrier_wave = self._wave(progress)
        power_x = cx - 9 + (carrier_wave * 18)
        self._dot(power_x, y, colour, radius=1.4, tags=tags)
        flare = (3.0 if variant == "transit" else 1.5) * carrier_wave
        for side in (-1, 1):
            self._line(cx - 17 - flare, y + side * 3,
                       cx - 12, y + side * 3,
                       colour=glow, width=2 if variant == "transit" else 1,
                       tags=tags)

        x1, x2 = g["right_start"] + 4, g["right"] - 4
        span = x2 - x1
        if variant == "deck":
            # The command deck remains centred and ready.  Paired console
            # pulses breathe toward the carrier instead of implying travel.
            console_wave = self._wave(progress)
            center = (x1 + x2) / 2
            self._line(x1, y - 7, center - 9, y - 3,
                       colour=dim, tags=tags)
            self._line(x1, y + 7, center - 9, y + 3,
                       colour=dim, tags=tags)
            self._line(center + 9, y - 3, x2, y - 7,
                       colour=dim, tags=tags)
            self._line(center + 9, y + 3, x2, y + 7,
                       colour=dim, tags=tags)
            travel = console_wave * max(1, ((span / 2) - 10))
            self._dot(x1 + travel, y - 5, colour,
                      radius=1.2, tags=tags)
            self._dot(x2 - travel, y + 5, colour,
                      radius=1.2, tags=tags)
            for index, offset in enumerate((-7, 0, 7)):
                tone = colour if index == int(progress * 3) % 3 else glow
                self._dot(center + offset, y, tone,
                          radius=1.25 if tone == colour else 0.8, tags=tags)
            return
        for lane in (-7, 0, 7):
            self._line(x1, y + lane, x2, y + lane,
                       colour=dim, tags=tags)
        if variant == "transit":
            aperture_x = x2 - 14
            radius = 6 + self._wave(progress) * 5
            self._arc(aperture_x - radius, y - radius,
                      aperture_x + radius, y + radius,
                      35, 110, colour, width=2, tags=tags)
            self._arc(aperture_x - radius, y - radius,
                      aperture_x + radius, y + radius,
                      215, 110, colour, width=2, tags=tags)
        else:
            brake_x = x1 + span * 0.72
            close = self._wave(progress)
            for side in (-1, 1):
                x = brake_x + side * (7 + (1.0 - close) * 8)
                self._line(x, y - 9, x, y + 9,
                           colour=colour, width=2, tags=tags)
                self._line(x, y - 9, x - side * 6, y - 9,
                           colour=glow, tags=tags)
                self._line(x, y + 9, x - side * 6, y + 9,
                           colour=glow, tags=tags)
        direction = -1 if variant == "arrival" else 1
        for index in range(4):
            local = (progress + index / 4) % 1.0
            if direction > 0:
                x = x1 + span * local
            else:
                x = x2 - span * local
            width = 18 + (8 * (1.0 - local) if variant == "arrival" else 0)
            self._line(max(x1, x - width), y + (-7, 0, 7)[index % 3], x,
                       y + (-7, 0, 7)[index % 3],
                       colour=colour if index == 0 else glow,
                       width=3 if index == 0 else 2, tags=tags)

    def _draw_planetary(self, g, variant, progress, colour, dim, glow, tags):
        y = g["y"]
        cx = g["left_center"]
        departing = variant in {"surface_departure", "orbital_departure"}
        hold = variant == "hold"
        glide = variant == "glide"
        shuttle = self._wave(progress)
        travel = shuttle if departing else 1.0 - shuttle
        if hold:
            travel = 0.5
        horizon_y = y + ((travel - 0.5) * 8)
        self._arc(cx - 18, horizon_y - 3, cx + 18, horizon_y + 16,
                  18, 144, glow, tags=tags)
        ship_y = y + ((travel - 0.5) * 14)
        self.canvas.create_polygon(
            cx + 5, ship_y, cx - 4, ship_y - 3,
            cx - 1, ship_y, cx - 4, ship_y + 3,
            fill="#010101", outline=colour, tags=tags,
        )
        if hold:
            # Station keeping should remain visually stable, but the paired
            # stabiliser arcs confirm that the hold solution is still active.
            stabiliser = 5 + self._wave(progress) * 3
            self._arc(cx - stabiliser, ship_y - stabiliser,
                      cx + stabiliser, ship_y + stabiliser,
                      35, 110, glow, tags=tags)
            self._arc(cx - stabiliser, ship_y - stabiliser,
                      cx + stabiliser, ship_y + stabiliser,
                      215, 110, glow, tags=tags)
        if variant in {"orbital_approach", "orbital_departure"}:
            self._arc(cx - 14, y - 11, cx + 14, y + 11,
                      22, 128, dim, tags=tags)

        x1, x2 = g["right_start"] + 5, g["right"] - 5
        span = x2 - x1
        if hold:
            center = (x1 + x2) / 2
            self._line(x1, y, x2, y, colour=dim, tags=tags)
            self._line(center - 18, y - 7, center + 18, y - 7,
                       colour=glow, tags=tags)
            self._line(center - 18, y + 7, center + 18, y + 7,
                       colour=glow, tags=tags)
            self.canvas.create_polygon(
                center + 5, y, center - 4, y - 3,
                center - 1, y, center - 4, y + 3,
                fill="#010101", outline=colour, tags=tags,
            )
            pulse = 3 + self._wave(progress) * 3
            self._arc(center - pulse, y - pulse, center + pulse, y + pulse,
                      0, 360, colour, tags=tags)
            return
        if glide:
            self._line(x1, y + 10, x2, y - 8,
                       colour=glow, width=2, tags=tags)
            self._line(x1, y + 4, x2, y - 12,
                       colour=dim, tags=tags)
            marker_x = x1 + span * self._wave(progress)
            amount = (marker_x - x1) / max(1.0, span)
            marker_y = (y + 10) + ((-18) * amount)
            self.canvas.create_polygon(
                marker_x + 5, marker_y,
                marker_x - 4, marker_y - 3,
                marker_x - 1, marker_y,
                marker_x - 4, marker_y + 3,
                fill="#010101", outline=colour, tags=tags,
            )
            return
        if variant in {"orbital_approach", "orbital_departure"}:
            planet_x = x2 - 16
            self._arc(planet_x - 16, y - 11, planet_x + 16, y + 11,
                      105, 150, glow, width=2, tags=tags)
            self._arc(x1, y - 12, planet_x + 7, y + 12,
                      205, 130, dim, tags=tags)
            amount = self._wave(progress)
            if variant == "orbital_departure":
                amount = 1.0 - amount
            marker_x = x1 + (planet_x - x1) * amount
            marker_y = y - math.sin(amount * math.pi) * 8
            self._dot(marker_x, marker_y, colour, radius=1.8, tags=tags)
            self._line(max(x1, marker_x - 12), marker_y,
                       marker_x, marker_y, colour=glow, tags=tags)
            return

        # Surface approach/departure becomes a landing corridor and pad
        # solution. Direction reversal communicates descent versus climb.
        pad_x = x2 - 14
        self._line(x1, y - 10, pad_x, y - 4,
                   colour=dim, tags=tags)
        self._line(x1, y + 10, pad_x, y + 4,
                   colour=dim, tags=tags)
        self.canvas.create_rectangle(
            pad_x - 7, y - 5, pad_x + 7, y + 5,
            fill="#010101", outline=glow, tags=tags,
        )
        amount = self._wave(progress)
        if departing:
            amount = 1.0 - amount
        marker_x = x1 + (pad_x - x1) * amount
        corridor = 9 * (1.0 - amount)
        marker_y = y + math.sin(progress * math.tau) * corridor * 0.28
        self.canvas.create_polygon(
            marker_x + 5, marker_y,
            marker_x - 4, marker_y - 3,
            marker_x - 1, marker_y,
            marker_x - 4, marker_y + 3,
            fill="#010101", outline=colour, tags=tags,
        )

    def _draw_context(self, g, profile, variant, progress, model,
                      colour, dim, glow, tags):
        """Add only context that belongs to the currently resolved state.

        This deliberately excludes fuel scooping: the live fuel cell owns that
        animation.  Keeping these accents state-scoped prevents landing gear,
        cargo scoop, fuel, or FSD decorations from leaking into unrelated
        sigils as generic overlays did in the previous renderer.
        """
        y = g["y"]
        cx = g["left_center"]

        if (model.get("boost_armed")
                and profile in {"flight", "supercruise", "fighter"}):
            # Neutron readiness remains useful in flight, but now reads as a
            # restrained charged wake behind the ship rather than a second
            # unrelated animation spanning the complete instrument.
            accent = self.mix_colour(
                model.get("accent_color") or colour, 0.76,
            )
            wake = self._wave(progress)
            for side in (-1, 1):
                length = 4 + wake * 5
                self._line(cx - 16 - length, y + side * 4,
                           cx - 16, y + side * 4,
                           colour=accent, width=1, tags=tags)

        gravity = float(model.get("gravity_load", 0.0) or 0.0)
        gravity_profiles = {
            "landed", "surface_vehicle", "on_foot",
            "orbital_approach", "glide", "surface_approach",
            "surface_hold", "surface_departure", "orbital_departure",
        }
        if gravity > 0 and profile in gravity_profiles:
            # Gravity is tied to planetary/surface states only. The lower load
            # bar expands with reported gravity and breathes with the sigil.
            load = min(1.0, gravity)
            pulse = 0.82 + (self._wave(progress) * 0.18)
            half_span = (7 + load * 11) * pulse
            gravity_colour = model.get("gravity_color") or colour
            self._line(cx - half_span, g["bottom"] - 2,
                       cx + half_span, g["bottom"] - 2,
                       colour=self.mix_colour(gravity_colour, 0.76),
                       width=2 if load > 0.55 else 1, tags=tags)

    def draw_transition(self, model, transition, progress, tags="nav_state_motion"):
        """Morph into the target state's own visual language."""
        progress = max(0.0, min(1.0, float(progress)))
        eased = self._ease(progress)
        wave = math.sin(progress * math.pi)
        colour = transition.get("to_color") or model["state_color"]
        glow = self.mix_colour(colour, min(0.92, 0.58 + wave * 0.34))
        dim = self.mix_colour(colour, 0.34)
        g = self._geometry(model)
        y = g["y"]
        profile = str(transition.get("to_profile") or model.get("motion_profile") or "flight")
        design = DESIGNS.get(profile, DESIGNS["flight"])
        variant = self._resolve_variant(profile, model.get("state"), design.variant)
        left = (g["left"] + 5, g["left_end"] - 3)
        right = (g["right_start"] + 3, g["right"] - 5)
        wings = (left, right)

        if design.dialect == "flight" and variant == "supercruise":
            # Perspective streaks accelerate open into the Supercruise flow.
            for wing_index, (x1, x2) in enumerate(wings):
                span = max(1.0, x2 - x1)
                for index, lane in enumerate((-7, 0, 7)):
                    local = max(0.0, min(1.0, eased * 1.35 - index * 0.12))
                    x = x1 + span * local * local
                    py = y + lane * (1.0 - local * 0.7)
                    self._line(max(x1, x - 6 - local * 18), py, x, py,
                               colour=colour if local > 0.65 else glow,
                               width=2 if local > 0.76 else 1, tags=tags)
            return

        if design.dialect == "fsd":
            if variant in {"charge", "overcharge"}:
                # Charge cells close toward each wing's state anchor.
                for cx, (x1, x2) in zip(
                    (g["left_center"], g["right_center"]), wings,
                ):
                    for index in range(4):
                        origin = x1 + (x2 - x1) * (index + 0.5) / 4
                        x = origin + (cx - origin) * eased
                        self._line(x - 3, y - 5, x + 3, y - 5,
                                   colour=glow, width=2, tags=tags)
                        self._line(x - 3, y + 5, x + 3, y + 5,
                                   colour=glow, width=2, tags=tags)
                return
            if variant == "jump":
                # Hyperspace enters as an outward streak burst.
                for x1, x2 in wings:
                    center = (x1 + x2) / 2
                    half = (x2 - x1) / 2
                    for index, lane in enumerate((-8, -3, 3, 8)):
                        side = -1 if index < 2 else 1
                        x = center + side * half * eased
                        length = 4 + 22 * eased
                        self._line(x - side * length, y + lane, x, y + lane,
                                   colour=colour, width=2, tags=tags)
                return
            # Arrival and cooldown release the compressed jump solution.
            for cx in (g["left_center"], g["right_center"]):
                rx = 4 + wave * 17
                ry = 2 + wave * 7
                self._arc(cx - rx, y - ry, cx + rx, y + ry,
                          0, 360, glow, width=2 if progress < 0.5 else 1,
                          tags=tags)
            return

        if design.dialect == "station":
            # Docking clamps settle onto a retained pad lock.
            for cx in (g["left_center"], g["right_center"]):
                spread = 17 - eased * 10
                for side in (-1, 1):
                    x = cx + side * spread
                    self._line(x, y - 8, x, y + 8,
                               colour=glow, width=2, tags=tags)
                    self._line(x, y, x - side * 6, y,
                               colour=colour, tags=tags)
            return

        if design.dialect == "survey":
            # A scope sweep crosses each wing independently, protecting text.
            for x1, x2 in wings:
                x = x1 + (x2 - x1) * eased
                height = 4 + wave * 7
                self._line(x, y - height, x, y + height,
                           colour=colour, width=2, tags=tags)
                self._line(x1, y, x, y, colour=dim, tags=tags)
            return

        if design.dialect in {"surface", "planetary"}:
            # A moving horizon establishes approach/departure direction.
            departing = variant in {"surface_departure", "orbital_departure"}
            amount = 1.0 - eased if departing else eased
            offset = 8 - amount * 16
            for x1, x2 in wings:
                self._line(x1, y + offset + 3, x2, y + offset - 3,
                           colour=glow, width=2, tags=tags)
                marker = x1 + (x2 - x1) * amount
                self._line(marker, y + offset - 3, marker, y + offset + 4,
                           colour=colour, tags=tags)
            return

        if design.dialect == "hazard":
            # Hazard brackets converge without borrowing the old arc morph.
            for x1, x2 in wings:
                center = (x1 + x2) / 2
                spread = (x2 - x1) * (0.48 - eased * 0.30)
                for side in (-1, 1):
                    x = center + side * spread
                    self._line(x, y - 8, x, y + 8,
                               colour=colour, width=2, tags=tags)
                    self._line(x, y - 8, x - side * 6, y - 8,
                               colour=glow, tags=tags)
                    self._line(x, y + 8, x - side * 6, y + 8,
                               colour=glow, tags=tags)
            return

        if design.dialect == "carrier":
            # Carrier deck lanes unfold from the centre of each wing.
            for x1, x2 in wings:
                center = (x1 + x2) / 2
                for lane in (-6, 0, 6):
                    extent = (x2 - x1) * 0.5 * eased
                    self._line(center - extent, y + lane,
                               center + extent, y + lane,
                               colour=colour if lane == 0 else glow,
                               width=2 if lane == 0 else 1, tags=tags)
            return

        if design.dialect == "handoff":
            # Deployment/boarding is a compact cell transfer.
            reverse = variant == "board"
            for x1, x2 in wings:
                amount = 1.0 - eased if reverse else eased
                x = x1 + (x2 - x1) * amount
                self.canvas.create_rectangle(
                    x - 4, y - 4, x + 4, y + 4,
                    fill="#010101", outline=colour, width=2, tags=tags,
                )
                self._line(x1, y, x, y, colour=dim, tags=tags)
            return

        # Ordinary flight receives a clean vector wipe rather than the former
        # generic paired arcs.
        for x1, x2 in wings:
            x = x1 + (x2 - x1) * eased
            self._line(x, y - (4 + wave * 5), x, y + (4 + wave * 5),
                       colour=colour, width=2, tags=tags)
            self._line(x1, y, x, y, colour=glow, tags=tags)


assert set(DESIGNS) == set(STATE_SCENES), "Navigation state designs must remain exhaustive"
