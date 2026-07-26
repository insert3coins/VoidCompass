"""Elite-style interactive 3D expedition and galactic-region map."""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
import math
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from galactic_regions import find_region, region_geometry
from stellar_types import star_type_label
from ui_theme import THEME, button, configure_ttk


LAYER_COLOURS = {
    "Regions": THEME.dim,
    "Valuable": THEME.orange,
    "Biology": THEME.green,
    "Codex": THEME.accent,
    "Photos": THEME.text,
    "Recon": THEME.red,
    "Bookmarks": THEME.yellow,
}

VIEW_PRESETS = (
    "Perspective",
    "Galaxy Overview",
    "Top",
    "Side",
    "Route Focus",
)

GALACTIC_CENTRE = (0.0, 0.0, 25899.0)
GALAXY_RADIUS_LY = 51500.0
MAX_ROUTE_POINTS = 1500


@lru_cache(maxsize=24)
def _map_font(size, bold=False):
    filename = "consolab.ttf" if bold else "consola.ttf"
    pixel_size = max(9, round(float(size) * 1.5))
    try:
        return ImageFont.truetype(f"C:/Windows/Fonts/{filename}", pixel_size)
    except OSError:
        return ImageFont.load_default()


def _position(value):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        return tuple(float(value[index]) for index in range(3))
    except (TypeError, ValueError):
        return None


def _hex_rgb(value):
    value = str(value or "#000000").lstrip("#")
    if len(value) != 6:
        return 0, 0, 0
    try:
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return 0, 0, 0


def _mix(left, right, amount):
    amount = max(0.0, min(1.0, float(amount)))
    a = _hex_rgb(left)
    b = _hex_rgb(right)
    values = [round(a[index] + (b[index] - a[index]) * amount) for index in range(3)]
    return "#{:02x}{:02x}{:02x}".format(*values)


def _star_colour(star_class):
    code = str(star_class or "").upper()
    if code.startswith(("O", "B")):
        return "#91d8ff"
    if code.startswith("A"):
        return "#d5ecff"
    if code.startswith("F"):
        return "#fff0c2"
    if code.startswith("G"):
        return "#ffd46b"
    if code.startswith("K"):
        return "#ff9a4d"
    if code.startswith(("M", "L", "T", "Y")):
        return "#ff6b55"
    if code.startswith(("N", "D")):
        return "#b7a6ff"
    if code.startswith(("H", "BLACK", "SUPERMASSIVE")):
        return "#c7d3dc"
    return THEME.accent


class ExpeditionMapView:
    def __init__(
        self, parent, app, open_record_callback=None,
        popout_callback=None, focus_mode=False,
    ):
        self.parent = parent
        self.app = app
        self.open_record_callback = open_record_callback
        self.popout_callback = popout_callback
        self.focus_mode = bool(focus_mode)
        self._map_points = []
        self._system_rows = []
        self._value_rows = []
        self._route_rows = []
        self._snapshot = {}
        self._bookmarks = []
        self._camera_center = [0.0, 0.0, 0.0]
        self._fit_radius = 1000.0
        self._zoom = 1.0
        self._pan = [0.0, 0.0]
        self._yaw = -0.55
        self._pitch = -0.62
        self._projection_context = None
        self._background_draw = None
        self._background_photo = None
        self._background_item = None
        self._render_job = None
        self._render_pending = False
        self._camera_ready = False
        self._drag_mode = None
        self._drag_origin = None
        self._drag_last = None
        self._drag_distance = 0.0
        self._hover_point = None
        self._selected_point = None
        configure_ttk(parent, "ExpeditionMap")
        self._build()

    def _build(self):
        toolbar = tk.Frame(self.parent, bg=THEME.panel)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        tk.Label(
            toolbar, text="GALAXY MAP // EXPEDITION INTELLIGENCE", fg=THEME.orange,
            bg=THEME.panel, font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.LEFT, padx=10, pady=8)
        tk.Label(
            toolbar, text="LMB orbit · RMB move · wheel zoom · 2× reset", fg=THEME.muted,
            bg=THEME.panel, font=("Cascadia Mono", 7),
        ).pack(side=tk.LEFT)
        if callable(self.popout_callback):
            button(
                toolbar, "DOCK" if self.focus_mode else "POP OUT",
                self._toggle_popout, accent=self.focus_mode,
            ).pack(side=tk.RIGHT, padx=(0, 8), pady=5)
        button(toolbar, "RESET", self._reset_view).pack(side=tk.RIGHT, padx=(0, 8), pady=5)
        button(toolbar, "CURRENT", self._focus_current).pack(side=tk.RIGHT, padx=(0, 6), pady=5)
        self.view_mode = tk.StringVar(value="Perspective")
        combo = ttk.Combobox(
            toolbar, textvariable=self.view_mode, state="readonly", width=16,
            values=VIEW_PRESETS, style="ExpeditionMap.TCombobox",
        )
        combo.pack(side=tk.RIGHT, padx=(0, 6), pady=5)
        combo.bind("<<ComboboxSelected>>", lambda _event: self._reset_view())

        layers = tk.Frame(self.parent, bg=THEME.inset)
        layers.pack(fill=tk.X, pady=(0, 5))
        tk.Label(
            layers, text="DISPLAY", fg=THEME.muted, bg=THEME.inset,
            font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.LEFT, padx=(8, 5), pady=4)
        self.layer_vars = {}
        for name in ("Regions", "Valuable", "Biology", "Codex", "Photos", "Recon", "Bookmarks"):
            var = tk.BooleanVar(value=True)
            self.layer_vars[name] = var
            tk.Checkbutton(
                layers, text=name.upper(), variable=var, command=self._schedule_render,
                fg=LAYER_COLOURS[name], bg=THEME.inset, selectcolor=THEME.input,
                activebackground=THEME.inset, activeforeground=LAYER_COLOURS[name],
                font=("Cascadia Mono", 7, "bold"), bd=0, highlightthickness=0,
            ).pack(side=tk.LEFT, padx=(0, 8), pady=3)

        self.summary = tk.Label(
            self.parent, text="", fg=THEME.accent, bg=THEME.bg,
            font=("Cascadia Mono", 8, "bold"), anchor="w",
        )
        self.summary.pack(fill=tk.X, padx=4, pady=(0, 5))
        self.canvas = tk.Canvas(
            self.parent, bg=THEME.inset, highlightthickness=1,
            highlightbackground=THEME.border, bd=0, cursor="crosshair",
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._schedule_render())
        self.canvas.bind("<Map>", self._on_canvas_mapped)
        self.canvas.bind("<ButtonPress-1>", lambda event: self._begin_drag(event, "rotate"))
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Shift-ButtonPress-1>", lambda event: self._begin_drag(event, "pan"))
        self.canvas.bind("<Shift-B1-Motion>", self._drag)
        self.canvas.bind("<Shift-ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<ButtonPress-2>", lambda event: self._begin_drag(event, "pan"))
        self.canvas.bind("<B2-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-2>", self._end_drag)
        self.canvas.bind("<ButtonPress-3>", lambda event: self._begin_drag(event, "pan"))
        self.canvas.bind("<B3-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-3>", self._end_drag)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Double-Button-1>", self._canvas_reset)
        self.canvas.bind("<Motion>", self._motion)
        self.canvas.bind("<Leave>", self._leave)
        self.detail = tk.Label(
            self.parent,
            text="Select a system, intelligence marker or Universal Cartographics region.",
            fg=THEME.muted, bg=THEME.panel, font=("Cascadia Mono", 8),
            anchor="w",
        )
        self.detail.pack(fill=tk.X, pady=(5, 0), ipady=5)

    def _toggle_popout(self):
        if callable(self.popout_callback):
            self.popout_callback()

    def dispose(self):
        if self._render_job is not None:
            try:
                self.canvas.after_cancel(self._render_job)
            except tk.TclError:
                pass
        self._render_job = None
        self._background_photo = None

    def view_state(self):
        return {
            "mode": self.view_mode.get(),
            "camera_center": list(self._camera_center),
            "fit_radius": float(self._fit_radius),
            "zoom": float(self._zoom),
            "pan": list(self._pan),
            "yaw": float(self._yaw),
            "pitch": float(self._pitch),
            "layers": {name: bool(var.get()) for name, var in self.layer_vars.items()},
        }

    def apply_view_state(self, state):
        if not isinstance(state, dict):
            return
        mode = str(state.get("mode") or "Perspective")
        if mode in VIEW_PRESETS:
            self.view_mode.set(mode)
        centre = _position(state.get("camera_center"))
        if centre is not None:
            self._camera_center = list(centre)
        try:
            self._fit_radius = max(1.0, float(state.get("fit_radius", self._fit_radius)))
            self._zoom = max(0.08, min(80.0, float(state.get("zoom", self._zoom))))
            pan = state.get("pan") or self._pan
            self._pan = [float(pan[0]), float(pan[1])]
            self._yaw = float(state.get("yaw", self._yaw))
            self._pitch = max(
                -math.pi / 2.0,
                min(math.pi / 2.0, float(state.get("pitch", self._pitch))),
            )
        except (IndexError, TypeError, ValueError):
            pass
        for name, enabled in (state.get("layers") or {}).items():
            if name in self.layer_vars:
                self.layer_vars[name].set(bool(enabled))
        self._camera_ready = True
        self._schedule_render()

    def refresh(self, system_rows=None, value_rows=None):
        if system_rows is not None:
            self._system_rows = list(system_rows or [])
        if value_rows is not None:
            self._value_rows = list(value_rows or [])
        tracker = getattr(self.app, "deep_survey", None)
        self._snapshot = tracker.snapshot() if tracker else {}
        all_rows = [
            row for row in self._snapshot.get("route_points") or []
            if _position(row.get("pos")) is not None
        ]
        if len(all_rows) > MAX_ROUTE_POINTS:
            last = len(all_rows) - 1
            self._route_rows = [
                all_rows[round(index * last / (MAX_ROUTE_POINTS - 1))]
                for index in range(MAX_ROUTE_POINTS)
            ]
        else:
            self._route_rows = all_rows
        manager = getattr(self.app, "expedition_manager", None)
        self._bookmarks = manager.bookmarks() if manager else []
        if not self._camera_ready:
            self._reset_view(render=False)
            self._camera_ready = True
        self._update_summary(all_rows)
        self._schedule_render()

    def _data_positions(self, recent=False):
        rows = self._route_rows[-50:] if recent else self._route_rows
        positions = [_position(row.get("pos")) for row in rows]
        positions.extend(
            _position(bookmark.get("position")) for bookmark in self._bookmarks
        )
        return [position for position in positions if position is not None]

    @staticmethod
    def _bounds(positions):
        if not positions:
            return (0.0, 0.0, 0.0), 1000.0
        mins = [min(position[index] for position in positions) for index in range(3)]
        maxs = [max(position[index] for position in positions) for index in range(3)]
        centre = tuple((mins[index] + maxs[index]) / 2.0 for index in range(3))
        radius = max(
            math.sqrt(sum((position[index] - centre[index]) ** 2 for index in range(3)))
            for position in positions
        )
        return centre, max(100.0, radius * 1.12)

    def _reset_view(self, render=True):
        mode = self.view_mode.get()
        positions = self._data_positions(recent=mode == "Route Focus")
        centre, radius = self._bounds(positions)
        self._pan = [0.0, 0.0]
        self._zoom = 1.0
        if mode == "Galaxy Overview":
            self._camera_center = list(GALACTIC_CENTRE)
            self._fit_radius = GALAXY_RADIUS_LY * 1.08
            self._yaw = 0.0
            self._pitch = -math.pi / 2.0
            self._zoom = 0.92
        elif mode == "Top":
            self._camera_center = list(centre)
            self._fit_radius = radius
            self._yaw = 0.0
            self._pitch = -math.pi / 2.0
        elif mode == "Side":
            self._camera_center = list(centre)
            self._fit_radius = radius
            self._yaw = 0.0
            self._pitch = 0.0
        else:
            self._camera_center = list(centre)
            self._fit_radius = radius
            self._yaw = -0.55 if mode == "Perspective" else -0.35
            self._pitch = -0.62 if mode == "Perspective" else -0.72
        if render:
            self._schedule_render()

    def _focus_current(self):
        position = _position(getattr(self.app, "current_coords", None))
        if position is None and self._route_rows:
            position = _position(self._route_rows[-1].get("pos"))
        if position is None:
            return
        nearby = self._data_positions(recent=True)
        _centre, radius = self._bounds(nearby)
        self.view_mode.set("Perspective")
        self._camera_center = list(position)
        self._fit_radius = max(500.0, min(radius, 8000.0))
        self._zoom = 1.15
        self._pan = [0.0, 0.0]
        self._yaw = -0.55
        self._pitch = -0.62
        self._schedule_render()

    def _canvas_reset(self, _event=None):
        self._reset_view()
        return "break"

    def _schedule_render(self):
        if self._render_job is not None:
            return
        try:
            if not self.canvas.winfo_ismapped():
                self._render_pending = True
                return
            self._render_pending = False
            self._render_job = self.canvas.after(24, self._render)
        except tk.TclError:
            self._render_job = None

    def _on_canvas_mapped(self, _event=None):
        if self._render_pending or self._projection_context is None:
            self._schedule_render()

    def _begin_drag(self, event, mode):
        self._drag_mode = mode
        self._drag_origin = (event.x, event.y)
        self._drag_last = (event.x, event.y)
        self._drag_distance = 0.0

    def _drag(self, event):
        if not self._drag_mode or not self._drag_last:
            return
        dx = event.x - self._drag_last[0]
        dy = event.y - self._drag_last[1]
        self._drag_last = (event.x, event.y)
        self._drag_distance += abs(dx) + abs(dy)
        if self._drag_mode == "rotate":
            # Orbit behaves like grabbing the galaxy: its visible motion follows
            # the mouse instead of moving opposite to the drag.
            self._yaw -= dx * 0.005
            self._pitch = max(-1.50, min(1.35, self._pitch + dy * 0.005))
            if self.view_mode.get() in {"Top", "Side", "Galaxy Overview"}:
                self.view_mode.set("Perspective")
        else:
            self._pan[0] += dx
            self._pan[1] += dy
        self._schedule_render()

    def _end_drag(self, event):
        mode = self._drag_mode
        moved = self._drag_distance
        self._drag_mode = None
        self._drag_origin = None
        self._drag_last = None
        if mode == "rotate" and moved < 7:
            self._select_at(event.x, event.y)
        elif moved >= 7:
            # Restore the full-detail contour pass after the lightweight live
            # drag frame has kept rotation or panning responsive.
            self._schedule_render()

    def _wheel(self, event):
        steps = max(-4.0, min(4.0, event.delta / 120.0)) if event.delta else 0.0
        if not steps:
            return
        old_zoom = self._zoom
        new_zoom = max(0.08, min(80.0, old_zoom * (1.12 ** steps)))
        if abs(new_zoom - old_zoom) < 0.0001:
            return
        ratio = new_zoom / old_zoom
        width = max(240, self.canvas.winfo_width())
        height = max(180, self.canvas.winfo_height())
        old_cx = width / 2.0 + self._pan[0]
        old_cy = height / 2.0 + self._pan[1]
        new_cx = event.x - (event.x - old_cx) * ratio
        new_cy = event.y - (event.y - old_cy) * ratio
        self._pan[0] = new_cx - width / 2.0
        self._pan[1] = new_cy - height / 2.0
        self._zoom = new_zoom
        self._schedule_render()

    def _motion(self, event):
        if self._drag_mode:
            return
        point = self._nearest_point(event.x, event.y, 15)
        if point is self._hover_point:
            return
        self._hover_point = point
        self.canvas.config(cursor="hand2" if point else "crosshair")
        if point:
            self._show_record(point["record"], prefix="HOVER")
        elif self._selected_point:
            self._show_record(self._selected_point["record"], prefix="SELECTED")

    def _leave(self, _event=None):
        self._hover_point = None
        try:
            self.canvas.config(cursor="crosshair")
        except tk.TclError:
            pass

    def _nearest_point(self, x, y, radius=20):
        if not self._map_points:
            return None
        point = min(
            reversed(self._map_points),
            key=lambda item: (item["x"] - x) ** 2 + (item["y"] - y) ** 2,
        )
        return point if (point["x"] - x) ** 2 + (point["y"] - y) ** 2 <= radius ** 2 else None

    def _select_at(self, x, y):
        point = self._nearest_point(x, y, 20)
        if not point:
            return
        self._selected_point = point
        record = point["record"]
        self._show_record(record, prefix="SELECTED")
        if record.get("kind") != "Region" and callable(self.open_record_callback):
            self.open_record_callback(record)

    def _show_record(self, record, prefix="SELECTED"):
        raw = record.get("raw") or {}
        pos = _position(raw.get("pos") or record.get("position"))
        bits = [prefix, record.get("subject") or record.get("kind") or "Map record"]
        if record.get("system"):
            bits.append(record["system"])
        if record.get("detail"):
            bits.append(record["detail"])
        if pos:
            region = find_region(*pos)
            if region and record.get("kind") != "Region":
                bits.append(region[1])
            bits.append(f"{pos[0]:,.1f}, {pos[1]:,.1f}, {pos[2]:,.1f}")
        if raw.get("star_class"):
            bits.append(star_type_label(raw.get("star_class"), "Unknown"))
        self.detail.config(text=" · ".join(str(bit) for bit in bits if bit))

    def _projection(self):
        width = max(240, self.canvas.winfo_width())
        height = max(180, self.canvas.winfo_height())
        scale = min(width, height) * 0.43 / max(1.0, self._fit_radius) * self._zoom
        return {
            "width": width, "height": height, "scale": scale,
            "cx": width / 2.0 + self._pan[0],
            "cy": height / 2.0 + self._pan[1],
            "cos_yaw": math.cos(self._yaw), "sin_yaw": math.sin(self._yaw),
            "cos_pitch": math.cos(self._pitch), "sin_pitch": math.sin(self._pitch),
            "camera_distance": max(1000.0, self._fit_radius * 3.2),
        }

    def _project(self, position):
        context = self._projection_context
        dx = position[0] - self._camera_center[0]
        dy = position[1] - self._camera_center[1]
        dz = position[2] - self._camera_center[2]
        rotated_x = dx * context["cos_yaw"] - dz * context["sin_yaw"]
        rotated_z = dx * context["sin_yaw"] + dz * context["cos_yaw"]
        screen_y_world = dy * context["cos_pitch"] - rotated_z * context["sin_pitch"]
        depth = dy * context["sin_pitch"] + rotated_z * context["cos_pitch"]
        denominator = max(context["camera_distance"] * 0.18, context["camera_distance"] + depth)
        perspective = max(0.22, min(4.0, context["camera_distance"] / denominator))
        return (
            context["cx"] + rotated_x * context["scale"] * perspective,
            context["cy"] - screen_y_world * context["scale"] * perspective,
            depth,
            perspective,
        )

    def _visible_line(self, left, right, pad=80):
        width = self._projection_context["width"]
        height = self._projection_context["height"]
        return not (
            max(left[0], right[0]) < -pad or min(left[0], right[0]) > width + pad
            or max(left[1], right[1]) < -pad or min(left[1], right[1]) > height + pad
        )

    def _render(self):
        self._render_job = None
        canvas = self.canvas
        try:
            if not canvas.winfo_exists() or not canvas.winfo_ismapped():
                self._render_pending = True
                return
        except tk.TclError:
            return
        self._map_points = []
        self._projection_context = self._projection()
        width = int(self._projection_context["width"])
        height = int(self._projection_context["height"])
        background = Image.new("RGB", (width, height), THEME.inset)
        self._background_draw = ImageDraw.Draw(background)
        self._draw_starfield()
        self._draw_galaxy_structure()
        self._draw_grid()
        region_labels = ()
        if self.layer_vars.get("Regions") and self.layer_vars["Regions"].get():
            region_labels = self._draw_region_contours()
        if region_labels:
            self._draw_region_labels(region_labels)
        self._draw_route_and_markers()
        self._draw_hud_frame()
        self._background_draw = None
        self._background_photo = ImageTk.PhotoImage(background, master=canvas)
        if self._background_item is None:
            self._background_item = canvas.create_image(
                0, 0, image=self._background_photo, anchor="nw",
            )
        else:
            canvas.itemconfigure(self._background_item, image=self._background_photo)

    @staticmethod
    def _dashed_segment(draw, left, right, colour, width, dash):
        dx = right[0] - left[0]
        dy = right[1] - left[1]
        length = math.hypot(dx, dy)
        if length <= 0.01:
            return
        cursor = 0.0
        draw_on = True
        pattern_index = 0
        while cursor < length:
            span = max(1.0, float(dash[pattern_index % len(dash)]))
            end = min(length, cursor + span)
            if draw_on:
                start_ratio = cursor / length
                end_ratio = end / length
                draw.line(
                    (
                        left[0] + dx * start_ratio, left[1] + dy * start_ratio,
                        left[0] + dx * end_ratio, left[1] + dy * end_ratio,
                    ),
                    fill=colour, width=width,
                )
            cursor = end
            draw_on = not draw_on
            pattern_index += 1

    def _background_line(self, coordinates, colour, width=1, dash=None):
        points = list(zip(coordinates[0::2], coordinates[1::2]))
        if len(points) < 2:
            return
        draw = self._background_draw
        pixel_width = max(1, int(round(width)))
        if dash and not self._drag_mode:
            for left, right in zip(points, points[1:]):
                self._dashed_segment(draw, left, right, colour, pixel_width, dash)
        else:
            draw.line(points, fill=colour, width=pixel_width, joint="curve")

    def _background_text(self, x, y, text, colour, size=7, bold=False, anchor="center"):
        draw = self._background_draw
        font = _map_font(size, bold)
        text = str(text or "")
        bounds = draw.textbbox((0, 0), text, font=font)
        text_width = bounds[2] - bounds[0]
        text_height = bounds[3] - bounds[1]
        if anchor == "w":
            left, top = x, y - text_height / 2.0
        elif anchor == "sw":
            left, top = x, y - text_height
        elif anchor == "se":
            left, top = x - text_width, y - text_height
        else:
            left, top = x - text_width / 2.0, y - text_height / 2.0
        draw.text(
            (left - bounds[0], top - bounds[1]), text,
            font=font, fill=colour,
        )

    def _draw_starfield(self):
        draw = self._background_draw
        width = self._projection_context["width"]
        height = self._projection_context["height"]
        state = 0x5EED123
        for index in range(40 if self._drag_mode else 150):
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            x = (state % 10000) / 10000.0 * width
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            y = (state % 10000) / 10000.0 * height
            bright = index % 19 == 0
            colour = _mix(THEME.inset, THEME.text if bright else THEME.muted, 0.42 if bright else 0.22)
            radius = 1 if bright else 0
            if radius:
                draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=colour)
            else:
                draw.point((x, y), fill=colour)

    def _project_polyline(self, positions, colour, width=1, dash=None):
        projected = [self._project(position) for position in positions]
        points = []
        for left, right in zip(projected, projected[1:]):
            if self._visible_line(left, right):
                if not points:
                    points.extend((left[0], left[1]))
                points.extend((right[0], right[1]))
            elif len(points) >= 4:
                self._background_line(points, colour, width=width, dash=dash)
                points = []
        if len(points) >= 4:
            self._background_line(points, colour, width=width, dash=dash)

    def _draw_galaxy_structure(self):
        mode = self.view_mode.get()
        if mode != "Galaxy Overview" and self._fit_radius / max(self._zoom, 0.01) < 15000:
            return
        rim = []
        for index in range(97):
            angle = math.tau * index / 96.0
            rim.append((
                GALACTIC_CENTRE[0] + math.cos(angle) * GALAXY_RADIUS_LY,
                0.0,
                GALACTIC_CENTRE[2] + math.sin(angle) * GALAXY_RADIUS_LY * 0.92,
            ))
        self._project_polyline(rim, _mix(THEME.inset, THEME.border, 0.8), width=2)
        for arm in range(4):
            points = []
            for index in range(90):
                radius = 1500.0 + index / 89.0 * 47000.0
                angle = arm * math.pi / 2.0 + 0.7 + radius / 8700.0
                points.append((
                    GALACTIC_CENTRE[0] + math.cos(angle) * radius,
                    0.0,
                    GALACTIC_CENTRE[2] + math.sin(angle) * radius * 0.92,
                ))
            self._project_polyline(
                points, _mix(THEME.inset, THEME.accent, 0.16), width=2,
            )
        core = []
        for index in range(65):
            angle = math.tau * index / 64.0
            core.append((
                GALACTIC_CENTRE[0] + math.cos(angle) * 3500.0,
                0.0,
                GALACTIC_CENTRE[2] + math.sin(angle) * 3500.0,
            ))
        self._project_polyline(core, _mix(THEME.inset, THEME.orange, 0.35), width=2)

    def _nice_grid_step(self):
        visible_radius = self._fit_radius / max(self._zoom, 0.01)
        target = visible_radius / 6.0
        steps = (10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 20000)
        return min(steps, key=lambda value: abs(value - target))

    def _draw_grid(self):
        if self.view_mode.get() == "Galaxy Overview":
            for radius in (10000, 20000, 30000, 40000, 50000):
                ring = []
                for index in range(73):
                    angle = math.tau * index / 72.0
                    ring.append((
                        GALACTIC_CENTRE[0] + math.cos(angle) * radius,
                        0.0,
                        GALACTIC_CENTRE[2] + math.sin(angle) * radius,
                    ))
                self._project_polyline(ring, _mix(THEME.inset, THEME.border, 0.65), dash=(2, 5))
            for index in range(12):
                angle = math.tau * index / 12.0
                end = (
                    GALACTIC_CENTRE[0] + math.cos(angle) * GALAXY_RADIUS_LY,
                    0.0,
                    GALACTIC_CENTRE[2] + math.sin(angle) * GALAXY_RADIUS_LY,
                )
                self._project_polyline((GALACTIC_CENTRE, end), _mix(THEME.inset, THEME.border, 0.5), dash=(2, 6))
            return
        step = self._nice_grid_step()
        radius = self._fit_radius / max(self._zoom, 0.01) * 1.5
        centre_x = round(self._camera_center[0] / step) * step
        centre_z = round(self._camera_center[2] / step) * step
        count = min(14, max(5, math.ceil(radius / step)))
        colour = _mix(THEME.inset, THEME.border, 0.55)
        for offset in range(-count, count + 1):
            x = centre_x + offset * step
            self._project_polyline(
                ((x, 0.0, centre_z - count * step), (x, 0.0, centre_z + count * step)),
                colour,
            )
            z = centre_z + offset * step
            self._project_polyline(
                ((centre_x - count * step, 0.0, z), (centre_x + count * step, 0.0, z)),
                colour,
            )

    def _draw_region_contours(self):
        visible_radius = self._fit_radius / max(self._zoom, 0.01)
        contour_step = 32 if visible_radius > 16000 else (16 if visible_radius > 4500 else 8)
        if self._drag_mode:
            contour_step = min(128, contour_step * 4)
        # Contours become more detailed as the camera approaches them. Label
        # anchors stay fixed so names do not visibly drift between zoom levels.
        segments, _ignored_labels = region_geometry(contour_step)
        _ignored_segments, labels = region_geometry(16)
        boundary_colour = _mix(THEME.inset, THEME.orange, 0.38)
        for x1, z1, x2, z2, _left_region, _right_region in segments:
            left = self._project((x1, 0.0, z1))
            right = self._project((x2, 0.0, z2))
            if self._visible_line(left, right, pad=30):
                self._background_line(
                    (left[0], left[1], right[0], right[1]),
                    boundary_colour, width=1, dash=(3, 4),
                )
        return labels

    def _draw_region_labels(self, labels):
        width = self._projection_context["width"]
        height = self._projection_context["height"]
        label_colour = _mix(THEME.inset, THEME.text, 0.48)
        current = _position(getattr(self.app, "current_coords", None))
        current_region = find_region(*current) if current else None
        selected_region = None
        if self._selected_point:
            selected_record = self._selected_point.get("record") or {}
            if selected_record.get("kind") == "Region":
                selected_region = selected_record.get("subject")
        projected_labels = []
        for row in labels:
            px, py, depth, perspective = self._project(row["position"])
            if not (-80 <= px <= width + 80 and -20 <= py <= height + 20):
                continue
            projected_labels.append((row, px, py, depth, perspective))

        # Large outer regions get first choice of label space. The current and
        # selected regions always win, while the complete 42-region boundary
        # raster remains visible underneath at every galactic zoom level.
        projected_labels.sort(key=lambda item: (
            item[0]["name"] == selected_region,
            bool(current_region and item[0]["id"] == current_region[0]),
            item[0]["cells"],
        ), reverse=True)
        occupied = []
        size = 6 if self.view_mode.get() == "Galaxy Overview" else 7
        for row, px, py, depth, perspective in projected_labels:
            text = f"{row['id']:02d}  {row['name'].upper()}"
            half_width = max(22.0, len(text) * size * 0.31)
            half_height = size * 0.85
            bounds = (
                px - half_width - 3, py - half_height - 2,
                px + half_width + 3, py + half_height + 2,
            )
            forced = (
                row["name"] == selected_region
                or bool(current_region and row["id"] == current_region[0])
            )
            if self._drag_mode and not forced:
                continue
            overlaps = any(
                bounds[0] < other[2] and bounds[2] > other[0]
                and bounds[1] < other[3] and bounds[3] > other[1]
                for other in occupied
            )
            if overlaps and not forced:
                continue
            self._background_text(
                px, py, text, label_colour, size=size, bold=True,
            )
            occupied.append(bounds)
            self._map_points.append({
                "x": px, "y": py, "depth": depth,
                "record": {
                    "kind": "Region", "subject": row["name"],
                    "detail": f"Universal Cartographics region {row['id']} of 42",
                    "position": row["position"],
                },
            })

    def _draw_route_and_markers(self):
        draw = self._background_draw
        rows = self._route_rows
        mapped_points = [point for point in self._map_points if point["record"].get("kind") == "Region"]
        position_by_system = {}
        for row in rows:
            pos = _position(row.get("pos"))
            if pos is None:
                continue
            system = str(row.get("system") or "")
            if system:
                position_by_system[system.casefold()] = pos
        draw_rows = rows
        if self._drag_mode and len(rows) > 500:
            last = len(rows) - 1
            indexes = {
                round(sample * last / 499)
                for sample in range(500)
            }
            current_key = str(getattr(self.app, "current_sys", "") or "").casefold()
            indexes.update(
                index for index, row in enumerate(rows)
                if current_key and str(row.get("system") or "").casefold() == current_key
            )
            draw_rows = [rows[index] for index in sorted(indexes)]
        route_points = []
        for row in draw_rows:
            pos = _position(row.get("pos"))
            if pos is not None:
                route_points.append((self._project(pos), row, pos))
        self._draw_route_path(route_points)

        visible_indexes = [
            index for index, (projected, _row, _pos) in enumerate(route_points)
            if -30 <= projected[0] <= self._projection_context["width"] + 30
            and -30 <= projected[1] <= self._projection_context["height"] + 30
        ]
        current_system = str(getattr(self.app, "current_sys", "") or "")
        mandatory_indexes = {
            index for index in visible_indexes
            if index in {0, len(route_points) - 1}
            or (
                current_system
                and str(route_points[index][1].get("system") or "").casefold()
                == current_system.casefold()
            )
        }
        point_limit = 70 if self._drag_mode else 220
        if len(visible_indexes) > point_limit:
            last = len(visible_indexes) - 1
            visible_indexes = sorted(mandatory_indexes | {
                visible_indexes[round(sample * last / (point_limit - 1))]
                for sample in range(point_limit)
            })
        ordered = sorted(
            ((index, route_points[index]) for index in visible_indexes),
            key=lambda item: item[1][0][2], reverse=True,
        )
        for index, (projected, row, pos) in ordered:
            px, py, depth, perspective = projected
            if not (-30 <= px <= self._projection_context["width"] + 30
                    and -30 <= py <= self._projection_context["height"] + 30):
                continue
            system = str(row.get("system") or "")
            is_current = bool(system and system.casefold() == current_system.casefold())
            is_endpoint = index in {0, len(route_points) - 1}
            colour = THEME.orange if is_current else _star_colour(row.get("star_class"))
            radius = max(1.5, min(5.5, (4.2 if is_endpoint else 2.4) * perspective))
            glow = _mix(THEME.inset, colour, 0.28)
            draw.ellipse(
                (px - radius * 2.2, py - radius * 2.2, px + radius * 2.2, py + radius * 2.2),
                outline=glow,
            )
            draw.ellipse(
                (px - radius, py - radius, px + radius, py + radius), fill=colour,
            )
            if is_current:
                self._draw_target_brackets(px, py, 10, THEME.orange)
            if is_current or is_endpoint:
                self._background_text(
                    px + 10, py - 8, system or "UNKNOWN",
                    THEME.text if is_current else THEME.muted,
                    size=7, bold=True, anchor="w",
                )
            mapped_points.append({
                "x": px, "y": py, "depth": depth,
                "record": {
                    "kind": "System", "system": system,
                    "subject": "Current system" if is_current else "Route arrival",
                    "raw": row, "position": pos,
                },
            })

        markers = self._layer_markers(self._snapshot, self._bookmarks)
        marker_counts = defaultdict(int)
        plotted_markers = 0
        projected_markers = []
        for marker in markers:
            layer = marker["layer"]
            if not self.layer_vars[layer].get():
                continue
            pos = _position(marker.get("position"))
            if pos is None:
                pos = position_by_system.get(str(marker.get("system") or "").casefold())
            if pos is None:
                continue
            projected_markers.append((self._project(pos), marker, pos))
        for projected, marker, pos in sorted(projected_markers, key=lambda item: item[0][2], reverse=True):
            px, py, depth, perspective = projected
            if not (-25 <= px <= self._projection_context["width"] + 25
                    and -25 <= py <= self._projection_context["height"] + 25):
                continue
            system_key = str(marker.get("system") or "").casefold()
            offset_index = marker_counts[system_key]
            marker_counts[system_key] += 1
            px += ((offset_index % 3) - 1) * 9
            py += ((offset_index // 3) % 3 - 1) * 9
            self._draw_marker(px, py, marker["layer"], LAYER_COLOURS[marker["layer"]])
            marker["position"] = pos
            mapped_points.append({"x": px, "y": py, "depth": depth, "record": marker})
            plotted_markers += 1
        self._map_points = mapped_points
        self._plotted_markers = plotted_markers

    def _draw_route_path(self, route_points):
        sequence = []

        def flush():
            if len(sequence) < 2:
                return
            # A handful of depth bands retains the 3D cue without creating one
            # drawing object for every jump in a long expedition.
            band_count = min(12, max(1, math.ceil((len(sequence) - 1) / 80)))
            band_size = max(1, math.ceil((len(sequence) - 1) / band_count))
            for start in range(0, len(sequence) - 1, band_size):
                band = sequence[start:min(len(sequence), start + band_size + 1)]
                brightness = max(
                    0.25, min(0.85, sum(point[3] for point in band) / len(band) / 1.25),
                )
                coordinates = []
                for point in band:
                    coordinates.extend((point[0], point[1]))
                self._background_line(
                    coordinates, _mix(THEME.inset, THEME.orange, brightness), width=2,
                )

        for index in range(1, len(route_points)):
            left = route_points[index - 1][0]
            right = route_points[index][0]
            if self._visible_line(left, right):
                if not sequence:
                    sequence.append(left)
                sequence.append(right)
            else:
                flush()
                sequence.clear()
        flush()

    def _draw_target_brackets(self, x, y, radius, colour):
        gap = radius * 0.45
        outer = radius
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            self._background_line(
                (x + sx * gap, y + sy * outer, x + sx * outer, y + sy * outer),
                colour,
            )
            self._background_line(
                (x + sx * outer, y + sy * gap, x + sx * outer, y + sy * outer),
                colour,
            )

    def _draw_marker(self, x, y, layer, colour):
        draw = self._background_draw
        glow = _mix(THEME.inset, colour, 0.28)
        draw.ellipse((x - 7, y - 7, x + 7, y + 7), outline=glow)
        if layer == "Valuable":
            draw.polygon(
                ((x, y - 5), (x + 5, y), (x, y + 5), (x - 5, y)),
                outline=colour, fill=THEME.inset,
            )
        elif layer == "Biology":
            draw.polygon(
                ((x, y - 5), (x + 5, y + 4), (x - 5, y + 4)),
                outline=colour, fill=THEME.inset,
            )
        elif layer == "Codex":
            points = []
            for index in range(6):
                angle = math.tau * index / 6.0
                points.append((x + math.cos(angle) * 5, y + math.sin(angle) * 5))
            draw.polygon(points, outline=colour, fill=THEME.inset)
        elif layer == "Photos":
            draw.rectangle((x - 4, y - 4, x + 4, y + 4), outline=colour)
            draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=colour)
        elif layer == "Recon":
            self._background_line((x - 5, y, x + 5, y), colour, width=2)
            self._background_line((x, y - 5, x, y + 5), colour, width=2)
        else:
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), outline=colour, width=2)
            draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=colour)

    def _draw_hud_frame(self):
        width = self._projection_context["width"]
        height = self._projection_context["height"]
        colour = _mix(THEME.inset, THEME.accent, 0.65)
        length = 18
        margin = 8
        for x, y, sx, sy in (
            (margin, margin, 1, 1), (width - margin, margin, -1, 1),
            (margin, height - margin, 1, -1), (width - margin, height - margin, -1, -1),
        ):
            self._background_line((x, y, x + sx * length, y), colour)
            self._background_line((x, y, x, y + sy * length), colour)
        self._draw_axis_gizmo(width - 55, 47)
        self._background_text(
            16, height - 16,
            f"{self.view_mode.get().upper()}  ·  ZOOM {self._zoom:05.2f}x",
            THEME.dim, size=7, bold=True, anchor="sw",
        )
        current = _position(getattr(self.app, "current_coords", None))
        region = find_region(*current) if current else None
        if region:
            self._background_text(
                width - 16, height - 16,
                f"REGION {region[0]:02d} // {region[1].upper()}",
                THEME.orange, size=7, bold=True, anchor="se",
            )

    def _draw_axis_gizmo(self, centre_x, centre_y):
        context = self._projection_context
        axes = (
            ("+X", (1.0, 0.0, 0.0), THEME.red),
            ("+Y", (0.0, 1.0, 0.0), THEME.green),
            ("+Z", (0.0, 0.0, 1.0), THEME.accent),
        )
        self._background_draw.ellipse(
            (centre_x - 2, centre_y - 2, centre_x + 2, centre_y + 2),
            fill=THEME.text,
        )
        for label, (dx, dy, dz), colour in axes:
            rotated_x = dx * context["cos_yaw"] - dz * context["sin_yaw"]
            rotated_z = dx * context["sin_yaw"] + dz * context["cos_yaw"]
            screen_y_world = dy * context["cos_pitch"] - rotated_z * context["sin_pitch"]
            screen_dx = rotated_x
            screen_dy = -screen_y_world
            length = math.hypot(screen_dx, screen_dy)
            if length < 0.05:
                self._background_draw.ellipse(
                    (centre_x - 5, centre_y - 5, centre_x + 5, centre_y + 5),
                    outline=colour, width=2,
                )
                self._background_text(
                    centre_x, centre_y + 13, label, colour, size=6, bold=True,
                )
                continue
            end_x = centre_x + screen_dx / length * 18.0
            end_y = centre_y + screen_dy / length * 18.0
            self._background_line((centre_x, centre_y, end_x, end_y), colour, width=2)
            self._background_text(
                end_x + screen_dx / length * 7.0,
                end_y + screen_dy / length * 7.0,
                label, colour, size=6, bold=True,
            )

    def _update_summary(self, all_rows):
        total_ly = sum(float(row.get("jump_dist") or 0) for row in all_rows)
        unique = len({row.get("system") for row in all_rows if row.get("system")})
        current = _position(getattr(self.app, "current_coords", None))
        region = find_region(*current) if current else None
        region_text = f" · region {region[0]:02d} {region[1]}" if region else ""
        representative = (
            f" · {len(self._route_rows):,} representative points"
            if len(self._route_rows) != len(all_rows) else ""
        )
        self.summary.config(
            text=(
                f"{unique:,} systems · {total_ly:,.1f} ly journalled · "
                f"42 Codex regions offline{region_text}{representative}"
            )
        )

    def _layer_markers(self, snapshot, bookmarks):
        markers = []

        def grouped(rows, system_key="system"):
            groups = defaultdict(list)
            for row in rows:
                system = row.get(system_key)
                if system:
                    groups[str(system)].append(row)
            return groups

        for system, rows in grouped(self._value_rows).items():
            top = max(rows, key=lambda row: int(row.get("value") or 0))
            markers.append({
                "layer": "Valuable", "kind": "Valuable", "system": system,
                "subject": top.get("body") or f"{len(rows)} valuable worlds",
                "detail": f"{len(rows)} retained · top {int(top.get('value') or 0):,} cr",
            })
        for row in self._system_rows:
            if int(row.get("bio_signals") or 0) > 0:
                markers.append({
                    "layer": "Biology", "kind": "System", "system": row.get("system"),
                    "subject": "Biological survey",
                    "detail": f"{int(row.get('bio_signals') or 0)} biological signals",
                })
        for system, rows in grouped(snapshot.get("codex") or []).items():
            markers.append({
                "layer": "Codex", "kind": "Codex", "system": system,
                "subject": rows[-1].get("name") or "Codex records",
                "detail": f"{len(rows)} Codex record(s)",
            })
        for system, rows in grouped(snapshot.get("screenshots") or []).items():
            markers.append({
                "layer": "Photos", "kind": "Photo", "system": system,
                "subject": rows[-1].get("body") or "Screenshot",
                "detail": f"{len(rows)} screenshot(s)",
            })
        for row in snapshot.get("candidates") or []:
            markers.append({
                "layer": "Recon", "kind": "Recon", "system": row.get("system"),
                "subject": "Recon candidate",
                "detail": f"{int(row.get('score') or 0)}/100 {row.get('grade') or ''}",
            })
        for row in bookmarks:
            markers.append({
                "layer": "Bookmarks", "kind": "Bookmark", "system": row.get("system"),
                "subject": row.get("title") or row.get("kind") or "Bookmark",
                "detail": " · ".join(filter(None, (row.get("priority"), ", ".join(row.get("tags") or [])))),
                "position": row.get("position"), "bookmark_id": row.get("id"),
            })
        return markers
