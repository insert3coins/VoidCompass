"""Interactive 2D galactic atlas with expedition intelligence overlays."""

from __future__ import annotations

from collections import defaultdict
import colorsys
from datetime import datetime
from functools import lru_cache
import math
from pathlib import Path
import random
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import weakref

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageTk

from galactic_regions import find_region, region_fills, region_geometry
from explorer_fieldcraft import sector_grid
from exploration_intelligence import route_context
from stellar_types import star_type_label
from ui_theme import THEME, button, configure_ttk


LAYER_COLOURS = {
    "Regions": THEME.dim,
    "Valuable": THEME.orange,
    "Biology": THEME.green,
    "Codex": THEME.accent,
    "Photos": THEME.text,
    "Recon": THEME.red,
    "Revisit": THEME.orange,
    "Bookmarks": THEME.yellow,
    "Annotations": THEME.orange,
    "Planned": THEME.accent,
    "Return": THEME.green,
    "Sectors": THEME.dim,
}

ANNOTATION_TYPES = (
    "Note",
    "Danger",
    "Region of Interest",
    "Survey Target",
    "Waypoint",
)

VIEW_PRESETS = (
    "Galactic Atlas",
    "Route Focus",
    "Current Vicinity",
)

GALACTIC_CENTRE = (0.0, 0.0, 25899.0)
GALAXY_RADIUS_LY = 51500.0
MAX_ROUTE_POINTS = 1500
REGION_HUE_STEP = 0.381966  # (3 - sqrt 5) / 2 turns, the golden angle
REGION_FILL_ALPHA = 14
REGION_FILL_STEP = 8
REGION_FILL_MIN_TILT = 0.15
FIT_MARGIN = 0.88
# Wheel zoom arrives as a burst of discrete events. Treating the burst as
# motion keeps each step on the cheap redraw path; full detail returns once
# the commander stops turning the wheel.
MOTION_WINDOW_S = 0.18
NAVIGATION_ANIMATION_MS = 120
GALAXY_TEXTURE_SIZE = 768
GALAXY_PREVIEW_SIZE = 384
GALAXY_MOTION_SIZE = 192
MAX_GALAXY_TEXTURE_THEMES = 4
ATLAS_ASSET = Path("Images") / "Galaxy" / "voidcompass-galactic-atlas.png"
_GALAXY_TEXTURES = {}
_GALAXY_TEXTURE_WAITERS = {}
_GALAXY_TEXTURE_LOCK = threading.Lock()


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


def _rgba(colour, alpha):
    return (*_hex_rgb(colour), max(0, min(255, int(alpha))))


def _resource_path(relative_path):
    """Resolve bundled image assets in source and PyInstaller builds."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


@lru_cache(maxsize=256)
def _region_fill_opaque(region_id, accent, alpha, backdrop):
    """Pre-blend a region wash against the map backdrop.

    Compositing a translucent layer costs about as much as the rest of a
    motion frame, so while the camera moves the same colour is flattened
    against the background once and drawn directly.
    """
    red, green, blue, _alpha = _region_fill_rgba(region_id, accent, alpha)
    base = _hex_rgb(backdrop)
    weight = max(0, min(255, int(alpha))) / 255.0
    return tuple(
        round(base[index] + (channel - base[index]) * weight)
        for index, channel in enumerate((red, green, blue))
    )


@lru_cache(maxsize=256)
def _region_fill_rgba(region_id, accent, alpha):
    """Give each Codex region its own hue without leaving the active theme.

    Rotating by the golden angle keeps neighbouring region identifiers far
    apart on the colour wheel, so adjacent areas stay distinguishable, while
    saturation and brightness follow the commander's accent.
    """
    red, green, blue = _hex_rgb(accent)
    hue, saturation, value = colorsys.rgb_to_hsv(red / 255.0, green / 255.0, blue / 255.0)
    hue = (hue + region_id * REGION_HUE_STEP) % 1.0
    saturation = max(0.34, min(0.86, saturation if saturation > 0.05 else 0.62))
    value = max(0.46, min(0.96, value * 0.86 + 0.22))
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
    return (round(red * 255), round(green * 255), round(blue * 255), max(0, min(255, int(alpha))))


def _build_galaxy_texture(key):
    """Build one original, theme-tinted top-down Milky Way texture."""
    size, accent, orange, text = key
    rng = random.Random(0x5A17C0DE)
    centre = size / 2.0
    radius = size * 0.465
    flatten = 0.92
    arm_colour = _mix(accent, text, 0.48)
    warm_colour = _mix(orange, text, 0.62)
    cool_colour = _mix(accent, "#bcdcff", 0.46)

    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    haze = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    haze_draw = ImageDraw.Draw(haze, "RGBA")

    # A diffuse stellar disc prevents the arms from looking like four clean
    # painted lines. Particles are generated once off the UI thread, then
    # softened into overlapping star clouds.
    for _index in range(5200):
        radial = rng.random() ** 0.63
        angle = rng.random() * math.tau
        x = centre + math.cos(angle) * radius * radial
        y = centre - math.sin(angle) * radius * radial * flatten
        particle = 1.0 + rng.random() * (4.0 - radial * 2.2)
        alpha = 5 + int((1.0 - radial) * 18)
        colour = warm_colour if radial < 0.28 else arm_colour
        haze_draw.ellipse(
            (x - particle, y - particle, x + particle, y + particle),
            fill=_rgba(colour, alpha),
        )

    arm_glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    arm_draw = ImageDraw.Draw(arm_glow, "RGBA")
    for arm in range(4):
        path = []
        for index in range(180):
            radial = 0.055 + index / 179.0 * 0.91
            angle = arm * math.pi / 2.0 + 0.64 + radial * 5.15
            path.append((
                centre + math.cos(angle) * radius * radial,
                centre - math.sin(angle) * radius * radial * flatten,
            ))
        arm_draw.line(
            path, fill=_rgba(arm_colour, 35),
            width=max(5, round(size * 0.035)), joint="curve",
        )
    arm_glow = arm_glow.filter(ImageFilter.GaussianBlur(max(3, size / 60.0)))
    haze = haze.filter(ImageFilter.GaussianBlur(max(2, size / 95.0)))
    base = Image.alpha_composite(base, haze)
    base = Image.alpha_composite(base, arm_glow)

    core = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    core_draw = ImageDraw.Draw(core, "RGBA")
    for fraction, alpha in ((0.22, 22), (0.15, 42), (0.09, 78), (0.045, 125)):
        rx = radius * fraction
        ry = rx * 0.72
        core_draw.ellipse(
            (centre - rx, centre - ry, centre + rx, centre + ry),
            fill=_rgba(warm_colour, alpha),
        )
    bar_angle = math.radians(24)
    bar_dx = math.cos(bar_angle) * radius * 0.20
    bar_dy = math.sin(bar_angle) * radius * 0.20
    core_draw.line(
        (centre - bar_dx, centre + bar_dy, centre + bar_dx, centre - bar_dy),
        fill=_rgba(warm_colour, 92), width=max(9, round(size * 0.035)),
    )
    core = core.filter(ImageFilter.GaussianBlur(max(4, size / 48.0)))
    base = Image.alpha_composite(base, core)

    stars = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    star_draw = ImageDraw.Draw(stars, "RGBA")
    for arm in range(4):
        for _index in range(1900):
            radial = 0.07 + rng.random() ** 0.72 * 0.90
            width = 0.07 + radial * 0.12
            angle = (
                arm * math.pi / 2.0 + 0.64 + radial * 5.15
                + rng.gauss(0.0, width)
            )
            radial = max(0.02, min(1.0, radial + rng.gauss(0.0, 0.018 + radial * 0.018)))
            x = centre + math.cos(angle) * radius * radial
            y = centre - math.sin(angle) * radius * radial * flatten
            roll = rng.random()
            colour = warm_colour if radial < 0.24 else (cool_colour if roll < 0.45 else arm_colour)
            alpha = 48 + int(rng.random() * 115 * (1.08 - radial * 0.35))
            point_size = 1 if rng.random() < 0.93 else 2
            star_draw.ellipse(
                (x - point_size, y - point_size, x + point_size, y + point_size),
                fill=_rgba(colour, alpha),
            )
    for _index in range(2700):
        radial = rng.random() ** 0.58
        angle = rng.random() * math.tau
        x = centre + math.cos(angle) * radius * radial
        y = centre - math.sin(angle) * radius * radial * flatten
        colour = warm_colour if radial < 0.22 else arm_colour
        alpha = 25 + int(rng.random() * 70 * (1.0 - radial * 0.28))
        star_draw.point((x, y), fill=_rgba(colour, alpha))
    for _index in range(1500):
        x = centre + rng.gauss(0.0, radius * 0.095)
        y = centre + rng.gauss(0.0, radius * 0.060)
        point_size = 1 if rng.random() < 0.88 else 2
        star_draw.ellipse(
            (x - point_size, y - point_size, x + point_size, y + point_size),
            fill=_rgba(warm_colour, 105 + int(rng.random() * 130)),
        )
    base = Image.alpha_composite(base, stars)

    # Offset logarithmic lanes obscure parts of the arms and create the dark,
    # irregular rifts visible in a galactic disc without copying game artwork.
    dust = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dust_draw = ImageDraw.Draw(dust, "RGBA")
    for arm in range(4):
        path = []
        for index in range(150):
            radial = 0.14 + index / 149.0 * 0.78
            angle = arm * math.pi / 2.0 + 0.79 + radial * 5.15
            jitter = math.sin(index * 0.31 + arm) * radius * 0.004
            path.append((
                centre + math.cos(angle) * (radius * radial + jitter),
                centre - math.sin(angle) * (radius * radial + jitter) * flatten,
            ))
        dust_draw.line(
            path, fill=(0, 2, 5, 70),
            width=max(5, round(size * 0.018)), joint="curve",
        )
    dust = dust.filter(ImageFilter.GaussianBlur(max(2, size / 180.0)))
    base = Image.alpha_composite(base, dust)

    edge_mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(edge_mask)
    margin = round(size * 0.025)
    mask_draw.ellipse((margin, margin, size - margin, size - margin), fill=255)
    edge_mask = edge_mask.filter(ImageFilter.GaussianBlur(max(8, size / 28.0)))
    base.putalpha(ImageChops.multiply(base.getchannel("A"), edge_mask))
    preview = base.resize(
        (GALAXY_PREVIEW_SIZE, GALAXY_PREVIEW_SIZE), Image.Resampling.LANCZOS,
    )
    motion = preview.resize(
        (GALAXY_MOTION_SIZE, GALAXY_MOTION_SIZE), Image.Resampling.LANCZOS,
    )
    return base, preview, motion


def _finish_galaxy_texture(key):
    try:
        bundle = _build_galaxy_texture(key)
    except Exception:
        bundle = None
    with _GALAXY_TEXTURE_LOCK:
        if bundle is not None:
            while (
                len(_GALAXY_TEXTURES) >= MAX_GALAXY_TEXTURE_THEMES
                and key not in _GALAXY_TEXTURES
            ):
                _GALAXY_TEXTURES.pop(next(iter(_GALAXY_TEXTURES)))
            _GALAXY_TEXTURES[key] = bundle
        waiters = _GALAXY_TEXTURE_WAITERS.pop(key, set())
    for view_ref in waiters:
        view = view_ref()
        if view is None:
            continue
        post = getattr(view.app, "_ui_post", None)
        if callable(post):
            post(lambda ref=view_ref, ready_key=key: _deliver_galaxy_texture(ref, ready_key))


def _deliver_galaxy_texture(view_ref, key):
    view = view_ref()
    if view is not None:
        view._on_galaxy_texture_ready(key)


def _request_galaxy_texture(view, key):
    view_ref = weakref.ref(view)
    start_worker = False
    with _GALAXY_TEXTURE_LOCK:
        bundle = _GALAXY_TEXTURES.get(key)
        if bundle is not None:
            return bundle
        waiters = _GALAXY_TEXTURE_WAITERS.get(key)
        if waiters is None:
            waiters = set()
            _GALAXY_TEXTURE_WAITERS[key] = waiters
            start_worker = True
        waiters.add(view_ref)
    if start_worker:
        threading.Thread(
            target=_finish_galaxy_texture, args=(key,),
            name="VoidCompassGalaxyTexture", daemon=True,
        ).start()
    return None


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
    def __init__(self, parent, app, open_record_callback=None):
        self.parent = parent
        self.app = app
        self.open_record_callback = open_record_callback
        self._map_points = []
        self._system_rows = []
        self._value_rows = []
        self._route_rows = []
        self._all_route_rows = []
        self._snapshot = {}
        self._bookmarks = []
        self._annotation_profile_key = str(
            (getattr(self.app, "config", None) or {}).get("active_commander_profile") or ""
        )
        self._annotations = self._normalise_annotations(
            (getattr(self.app, "config", None) or {}).get("explore_map_annotations")
        )
        self._position_by_system = {}
        self._marker_cache = []
        self._marker_glow_cache = {}
        self._camera_center = [0.0, 0.0, 0.0]
        self._fit_radius = 1000.0
        self._zoom = 1.0
        self._pan = [0.0, 0.0]
        self._yaw = -0.55
        self._pitch = -0.62
        self._projection_context = None
        self._background_image = None
        self._background_draw = None
        self._background_photo = None
        self._background_item = None
        self._galaxy_warp_key = None
        self._galaxy_warp_image = None
        self._atlas_source = None
        self._atlas_source_failed = False
        self._last_persisted_state = None
        self._render_job = None
        self._render_pending = False
        self._camera_ready = False
        self._drag_mode = None
        self._drag_origin = None
        self._drag_last = None
        self._drag_distance = 0.0
        self._hover_point = None
        self._selected_point = None
        self._fit_pending = False
        self._motion_until = 0.0
        self._settle_job = None
        self._motion_frame = False
        self._navigation_route_path = []
        self._navigation_waypoint = None
        self._navigation_current = None
        self._animation_job = None
        self._animation_phase = 0.0
        self._animation_items = {}
        self._animation_route = None
        self._annotation_dialog = None
        self._annotation_dialog_close = None
        self._context_menu = None
        self._disposed = False
        configure_ttk(parent, "ExpeditionMap")
        self._build()

    def _build(self):
        toolbar = tk.Frame(self.parent, bg=THEME.panel)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        tk.Label(
            toolbar, text="GALACTIC ATLAS // EXPEDITION INTELLIGENCE", fg=THEME.orange,
            bg=THEME.panel, font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.LEFT, padx=10, pady=8)
        tk.Label(
            toolbar, text="drag move · wheel zoom · click inspect · ctrl+click mark · 2× reset", fg=THEME.muted,
            bg=THEME.panel, font=("Cascadia Mono", 7),
        ).pack(side=tk.LEFT)
        button(toolbar, "RESET", self._reset_and_remember).pack(side=tk.RIGHT, padx=(0, 8), pady=5)
        button(toolbar, "CURRENT", self._focus_current).pack(side=tk.RIGHT, padx=(0, 6), pady=5)
        button(toolbar, "MARK", self._edit_annotation).pack(side=tk.RIGHT, padx=(0, 6), pady=5)
        self.view_mode = tk.StringVar(value="Galactic Atlas")
        combo = ttk.Combobox(
            toolbar, textvariable=self.view_mode, state="readonly", width=16,
            values=VIEW_PRESETS, style="ExpeditionMap.TCombobox",
        )
        combo.pack(side=tk.RIGHT, padx=(0, 6), pady=5)
        combo.bind("<<ComboboxSelected>>", self._preset_changed)
        config = getattr(self.app, "config", None) or {}
        initial_scope = str(config.get("explore_map_scope") or "All History")
        if initial_scope not in ("All History", "Current Session", "Active Expedition"):
            initial_scope = "All History"
        self.scope_var = tk.StringVar(value=initial_scope)
        scope = ttk.Combobox(
            toolbar, textvariable=self.scope_var, state="readonly", width=15,
            values=("All History", "Current Session", "Active Expedition"),
            style="ExpeditionMap.TCombobox",
        )
        scope.pack(side=tk.RIGHT, padx=(0, 6), pady=5)
        scope.bind("<<ComboboxSelected>>", self._scope_changed)

        layers = tk.Frame(self.parent, bg=THEME.inset)
        layers.pack(fill=tk.X, pady=(0, 5))
        tk.Label(
            layers, text="DISPLAY", fg=THEME.muted, bg=THEME.inset,
            font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.LEFT, padx=(8, 5), pady=4)
        self.layer_vars = {}
        for name in ("Regions", "Sectors", "Planned", "Return", "Valuable", "Biology", "Codex", "Photos", "Recon", "Revisit", "Bookmarks", "Annotations"):
            var = tk.BooleanVar(value=name != "Return")
            self.layer_vars[name] = var
            tk.Checkbutton(
                layers, text=(
                    "MARKS" if name == "Annotations" else
                    "GRID" if name == "Sectors" else name.upper()
                ),
                variable=var, command=self._layer_changed,
                fg=LAYER_COLOURS[name], bg=THEME.inset, selectcolor=THEME.input,
                activebackground=THEME.inset, activeforeground=LAYER_COLOURS[name],
                font=("Cascadia Mono", 7, "bold"), bd=0, highlightthickness=0,
            ).pack(side=tk.LEFT, padx=(0, 8), pady=3)
        button(layers, "FIND", self._find_target).pack(side=tk.RIGHT, padx=(4, 8), pady=3)
        self.search_var = tk.StringVar()
        search = ttk.Entry(
            layers, textvariable=self.search_var, width=22,
            style="ExpeditionMap.TEntry",
        )
        search.pack(side=tk.RIGHT, padx=(4, 0), pady=3)
        search.bind("<Return>", self._find_target)
        tk.Label(
            layers, text="SYSTEM / REGION / MARK", fg=THEME.muted, bg=THEME.inset,
            font=("Cascadia Mono", 7, "bold"),
        ).pack(side=tk.RIGHT, padx=(8, 0), pady=3)

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
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Map>", self._on_canvas_mapped)
        self.canvas.bind("<ButtonPress-1>", lambda event: self._begin_drag(event, "pan"))
        self.canvas.bind("<Control-Button-1>", self._annotate_at_canvas)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Shift-ButtonPress-1>", lambda event: self._begin_drag(event, "pan"))
        self.canvas.bind("<Shift-B1-Motion>", self._drag)
        self.canvas.bind("<Shift-ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<ButtonPress-2>", lambda event: self._begin_drag(event, "pan"))
        self.canvas.bind("<B2-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-2>", self._end_drag)
        self.canvas.bind("<ButtonPress-3>", lambda event: self._begin_drag(event, "context"))
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

    def dispose(self):
        self._disposed = True
        for job in (self._render_job, self._settle_job, self._animation_job):
            if job is None:
                continue
            try:
                self.canvas.after_cancel(job)
            except tk.TclError:
                pass
        self._render_job = None
        self._settle_job = None
        self._animation_job = None
        self._background_image = None
        self._background_photo = None
        self._galaxy_warp_image = None
        self._atlas_source = None
        if callable(self._annotation_dialog_close):
            try:
                self._annotation_dialog_close()
            except tk.TclError:
                pass
        elif self._annotation_dialog is not None:
            try:
                self._annotation_dialog.destroy()
            except tk.TclError:
                pass
        self._annotation_dialog = None
        self._annotation_dialog_close = None
        if self._context_menu is not None:
            try:
                self._context_menu.destroy()
            except tk.TclError:
                pass
            self._context_menu = None

    def _galaxy_texture_key(self):
        return (
            GALAXY_TEXTURE_SIZE,
            str(THEME.accent),
            str(THEME.orange),
            str(THEME.text),
        )

    def _on_galaxy_texture_ready(self, key):
        """Refresh after the background worker has prepared this theme."""
        if self._disposed or key != self._galaxy_texture_key():
            return
        self._galaxy_warp_key = None
        self._galaxy_warp_image = None
        self._schedule_render()

    @staticmethod
    def _normalise_annotations(rows):
        """Return safe, portable commander-owned map annotations."""
        annotations = []
        for index, row in enumerate(rows or ()):
            if not isinstance(row, dict):
                continue
            position = _position(row.get("position"))
            if position is None:
                continue
            category = str(row.get("category") or "Note").strip()
            if category not in ANNOTATION_TYPES:
                category = "Note"
            title = str(row.get("title") or category).strip() or category
            annotation_id = str(row.get("id") or "").strip()
            if not annotation_id:
                coordinate_key = "-".join(f"{value:.3f}" for value in position)
                annotation_id = f"legacy-{index}-{coordinate_key}"
            annotations.append({
                "id": annotation_id,
                "category": category,
                "title": title[:120],
                "note": str(row.get("note") or "").strip()[:2000],
                "system": str(row.get("system") or "").strip()[:120],
                "position": list(position),
                "created": str(row.get("created") or ""),
            })
        return annotations

    @staticmethod
    def _annotation_marker(row):
        note = " ".join(str(row.get("note") or "").split())
        category = str(row.get("category") or "Note")
        return {
            "layer": "Annotations",
            "kind": "Annotation",
            "system": row.get("system"),
            "subject": row.get("title") or category,
            "detail": f"{category} · {note}" if note else category,
            "position": row.get("position"),
            "annotation_id": row.get("id"),
            "category": category,
            "note": row.get("note") or "",
        }

    def _persist_annotations(self):
        config = getattr(self.app, "config", None)
        if not isinstance(config, dict):
            return
        config["explore_map_annotations"] = [dict(row) for row in self._annotations]
        persist = getattr(self.app, "_persist_config", None)
        if callable(persist):
            persist()

    def _annotation_target(self):
        record = (self._selected_point or {}).get("record") or {}
        annotation_id = str(record.get("annotation_id") or "")
        existing = next(
            (row for row in self._annotations if row.get("id") == annotation_id),
            None,
        )
        if existing is not None:
            return _position(existing.get("position")), existing.get("system") or "", existing
        raw = record.get("raw") or {}
        position = _position(raw.get("pos") or record.get("position"))
        system = str(record.get("system") or "")
        if position is None:
            position = _position(getattr(self.app, "current_coords", None))
            system = str(getattr(self.app, "current_sys", "") or "")
        return position, system, None

    def _canvas_position(self, event):
        context = self._projection_context or self._projection()
        scale = float(context.get("scale") or 0.0)
        if scale <= 0.0:
            return None
        return (
            self._camera_center[0] + (event.x - context["cx"]) / scale,
            0.0,
            self._camera_center[2] - (event.y - context["cy"]) / scale,
        )

    def _annotate_at_canvas(self, event):
        position = self._canvas_position(event)
        if position is None:
            return "break"
        region = find_region(*position)
        suggestion = region[1] if region else "Galactic marker"
        self._open_annotation_dialog(position, "", None, suggestion)
        return "break"

    def _edit_annotation(self):
        position, system, existing = self._annotation_target()
        if position is None:
            messagebox.showinfo(
                "Map Annotation",
                "Select a mapped system or region first, or wait until the current system has coordinates.",
                parent=self.parent.winfo_toplevel(),
            )
            return
        suggestion = system or ((self._selected_point or {}).get("record") or {}).get("subject")
        self._open_annotation_dialog(position, system, existing, suggestion)

    def _delete_annotation(self, annotation_id, parent=None):
        existing = next(
            (row for row in self._annotations if row.get("id") == annotation_id),
            None,
        )
        if existing is None:
            return False
        if not messagebox.askyesno(
            "Delete Map Annotation",
            f"Delete ‘{existing.get('title') or 'this annotation'}’ from this commander profile?",
            parent=parent or self.parent.winfo_toplevel(),
        ):
            return False
        self._annotations = [
            item for item in self._annotations if item.get("id") != annotation_id
        ]
        self._persist_annotations()
        self._marker_cache = self._layer_markers(self._snapshot, self._bookmarks)
        self._update_summary(self._scoped_route_rows())
        self._selected_point = None
        self._hover_point = None
        self.detail.config(text="Map annotation deleted from this commander profile.")
        self._schedule_render()
        feed = getattr(self.app, "add_event_feed_entry", None)
        if callable(feed):
            feed(
                "MAP", f"Annotation deleted: {existing.get('title') or 'Map mark'}",
                severity="INFO",
            )
        return True

    def _show_context_menu(self, event):
        point = self._nearest_point(event.x, event.y, 20)
        record = (point or {}).get("record") or {}
        try:
            if self._context_menu is not None:
                self._context_menu.destroy()
        except tk.TclError:
            pass
        menu = tk.Menu(
            self.canvas, tearoff=False, bg=THEME.panel, fg=THEME.text,
            activebackground=THEME.accent, activeforeground=THEME.bg,
            disabledforeground=THEME.dim, relief=tk.FLAT, bd=1,
        )
        self._context_menu = menu
        if record.get("kind") == "Annotation" and record.get("annotation_id"):
            self._selected_point = point
            self._show_record(record, prefix="SELECTED")
            annotation_id = record["annotation_id"]
            menu.add_command(label="Edit annotation", command=self._edit_annotation)
            menu.add_command(
                label="Delete annotation",
                command=lambda value=annotation_id: self._delete_annotation(value),
            )
        else:
            raw = record.get("raw") or {}
            position = _position(raw.get("pos") or record.get("position"))
            system = str(record.get("system") or "")
            suggestion = str(record.get("subject") or system or "")
            if position is None:
                position = self._canvas_position(event)
            if position is not None:
                region = find_region(*position)
                suggestion = suggestion or (region[1] if region else "Galactic marker")
                menu.add_command(
                    label="Add annotation here",
                    command=lambda pos=position, name=system, title=suggestion: (
                        self._open_annotation_dialog(pos, name, None, title)
                    ),
                )
        if menu.index("end") is None:
            menu.add_command(label="No map action available", state=tk.DISABLED)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass
        return "break"

    def _open_annotation_dialog(self, position, system="", existing=None, suggestion=""):
        if self._annotation_dialog is not None:
            try:
                if self._annotation_dialog.winfo_exists():
                    self._annotation_dialog.lift()
                    self._annotation_dialog.focus_force()
                    return
            except tk.TclError:
                pass
        position = _position(position)
        if position is None:
            return
        top = tk.Toplevel(self.parent.winfo_toplevel())
        self._annotation_dialog = top
        top.title("VoidCompass // Map Annotation")
        top.configure(bg=THEME.bg)
        config = getattr(self.app, "config", None) or {}
        try:
            top.geometry(str(config.get("explore_map_annotation_geometry") or "470x360"))
        except tk.TclError:
            top.geometry("470x360")
        top.minsize(420, 330)
        top.transient(self.parent.winfo_toplevel())

        body = tk.Frame(top, bg=THEME.panel, highlightthickness=1, highlightbackground=THEME.border)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        tk.Label(
            body, text="GALACTIC MAP ANNOTATION", fg=THEME.orange, bg=THEME.panel,
            font=("Segoe UI", 10, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(10, 3))
        location = system or (find_region(*position) or (None, "Deep space"))[1]
        tk.Label(
            body,
            text=f"{location} · {position[0]:,.1f}, {position[1]:,.1f}, {position[2]:,.1f}",
            fg=THEME.muted, bg=THEME.panel, font=("Cascadia Mono", 8), anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(0, 10))

        form = tk.Frame(body, bg=THEME.panel)
        form.pack(fill=tk.BOTH, expand=True, padx=12)
        form.columnconfigure(1, weight=1)
        tk.Label(form, text="TYPE", fg=THEME.muted, bg=THEME.panel, font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 7))
        category_var = tk.StringVar(value=(existing or {}).get("category") or "Note")
        category = ttk.Combobox(
            form, textvariable=category_var, state="readonly", values=ANNOTATION_TYPES,
            style="ExpeditionMap.TCombobox", width=24,
        )
        category.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(0, 7))
        tk.Label(form, text="TITLE", fg=THEME.muted, bg=THEME.panel, font=("Segoe UI", 8, "bold")).grid(row=1, column=0, sticky="w", pady=(0, 7))
        title_var = tk.StringVar(value=(existing or {}).get("title") or suggestion or "")
        title_entry = ttk.Entry(form, textvariable=title_var, style="ExpeditionMap.TEntry")
        title_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(0, 7))
        tk.Label(form, text="NOTES", fg=THEME.muted, bg=THEME.panel, font=("Segoe UI", 8, "bold")).grid(row=2, column=0, sticky="nw", pady=(2, 0))
        note = tk.Text(
            form, height=7, wrap="word", bg=THEME.input, fg=THEME.text,
            insertbackground=THEME.accent, relief=tk.FLAT, highlightthickness=1,
            highlightbackground=THEME.border, highlightcolor=THEME.accent,
            font=("Segoe UI", 9),
        )
        note.grid(row=2, column=1, sticky="nsew", padx=(10, 0))
        note.insert("1.0", (existing or {}).get("note") or "")
        form.rowconfigure(2, weight=1)

        actions = tk.Frame(body, bg=THEME.panel)
        actions.pack(fill=tk.X, padx=12, pady=12)

        def close_dialog():
            try:
                geometry = top.geometry()
            except tk.TclError:
                geometry = ""
            config = getattr(self.app, "config", None)
            if isinstance(config, dict) and geometry:
                config["explore_map_annotation_geometry"] = geometry
                persist = getattr(self.app, "_persist_config", None)
                if callable(persist):
                    persist()
            self._annotation_dialog = None
            self._annotation_dialog_close = None
            try:
                top.grab_release()
            except tk.TclError:
                pass
            top.destroy()

        def save_annotation():
            category_value = category_var.get() if category_var.get() in ANNOTATION_TYPES else "Note"
            title_value = title_var.get().strip() or category_value
            row = {
                "id": (existing or {}).get("id") or f"map-{time.time_ns():x}",
                "category": category_value,
                "title": title_value[:120],
                "note": note.get("1.0", "end-1c").strip()[:2000],
                "system": str(system or (existing or {}).get("system") or "")[:120],
                "position": list(position),
                "created": (existing or {}).get("created") or datetime.now().astimezone().isoformat(),
            }
            self._annotations = [
                item for item in self._annotations if item.get("id") != row["id"]
            ] + [row]
            self._persist_annotations()
            self.layer_vars["Annotations"].set(True)
            self._persist_view_state()
            self._marker_cache = self._layer_markers(self._snapshot, self._bookmarks)
            self._update_summary(self._scoped_route_rows())
            marker = self._annotation_marker(row)
            self._selected_point = {"x": -1000, "y": -1000, "record": marker}
            self._show_record(marker)
            self._schedule_render()
            feed = getattr(self.app, "add_event_feed_entry", None)
            if callable(feed):
                feed("MAP", f"Annotation saved: {row['title']}", severity="INFO")
            close_dialog()

        def delete_annotation():
            if existing is not None and self._delete_annotation(existing.get("id"), parent=top):
                close_dialog()

        button(actions, "SAVE MARK", save_annotation).pack(side=tk.RIGHT)
        button(actions, "CANCEL", close_dialog).pack(side=tk.RIGHT, padx=(0, 6))
        if existing is not None:
            button(actions, "DELETE", delete_annotation).pack(side=tk.LEFT)
        self._annotation_dialog_close = close_dialog
        top.protocol("WM_DELETE_WINDOW", close_dialog)
        top.grab_set()
        title_entry.focus_set()

    def view_state(self):
        return {
            "mode": self.view_mode.get(),
            "scope": self.scope_var.get(),
            "camera_center": list(self._camera_center),
            "fit_radius": float(self._fit_radius),
            "zoom": float(self._zoom),
            "pan": list(self._pan),
            "layers": {name: bool(var.get()) for name, var in self.layer_vars.items()},
        }

    def _persist_view_state(self):
        state = self.view_state()
        if state == self._last_persisted_state:
            return
        self._last_persisted_state = state
        config = getattr(self.app, "config", None)
        if not isinstance(config, dict):
            return
        config["explore_map_view_state"] = state
        persist = getattr(self.app, "_persist_config", None)
        if callable(persist):
            persist()

    def _layer_changed(self):
        self._schedule_render()
        self._persist_view_state()

    def _preset_changed(self, _event=None):
        self._reset_view()
        self._persist_view_state()

    def _reset_and_remember(self):
        self._reset_view()
        self._persist_view_state()

    def apply_view_state(self, state):
        if not isinstance(state, dict):
            return
        mode = str(state.get("mode") or "Galactic Atlas")
        # Migrate profile state saved by the retired 3D camera.
        legacy_camera = mode in {"Perspective", "Galaxy Overview", "Top", "Side"}
        if legacy_camera:
            mode = "Galactic Atlas"
        if mode in VIEW_PRESETS:
            self.view_mode.set(mode)
        scope = str(state.get("scope") or "All History")
        if scope in ("All History", "Current Session", "Active Expedition"):
            self.scope_var.set(scope)
        if not legacy_camera:
            centre = _position(state.get("camera_center"))
            if centre is not None:
                self._camera_center = list(centre)
            try:
                self._fit_radius = max(1.0, float(state.get("fit_radius", self._fit_radius)))
                self._zoom = max(0.08, min(80.0, float(state.get("zoom", self._zoom))))
                pan = state.get("pan") or self._pan
                self._pan = [float(pan[0]), float(pan[1])]
            except (IndexError, TypeError, ValueError):
                pass
        for name, enabled in (state.get("layers") or {}).items():
            if name in self.layer_vars:
                self.layer_vars[name].set(bool(enabled))
        if self._all_route_rows:
            self._route_rows = self._sample_route_rows(self._scoped_route_rows())
        if legacy_camera:
            self._reset_view()
            return
        # A restored camera is the commander's own framing, so it must not be
        # replaced by a deferred automatic fit.
        self._fit_pending = False
        self._camera_ready = True
        self._last_persisted_state = self.view_state()
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
        self._all_route_rows = all_rows
        scoped_rows = self._scoped_route_rows(all_rows)
        self._route_rows = self._sample_route_rows(scoped_rows)
        manager = getattr(self.app, "expedition_manager", None)
        self._bookmarks = manager.bookmarks() if manager else []
        annotation_profile_key = str(
            (getattr(self.app, "config", None) or {}).get("active_commander_profile") or ""
        )
        if annotation_profile_key != self._annotation_profile_key:
            self._annotation_profile_key = annotation_profile_key
            self._selected_point = None
            self._hover_point = None
        self._annotations = self._normalise_annotations(
            (getattr(self.app, "config", None) or {}).get("explore_map_annotations")
        )
        self._position_by_system = {
            str(row.get("system") or "").casefold(): position
            for row in scoped_rows
            if (position := _position(row.get("pos"))) is not None
            and str(row.get("system") or "").strip()
        }
        self._position_by_system.update({
            str(row.get("system") or "").casefold(): position
            for row in self._bookmarks
            if (position := _position(row.get("position"))) is not None
            and str(row.get("system") or "").strip()
        })
        self._marker_cache = self._layer_markers(self._snapshot, self._bookmarks)
        if not self._camera_ready:
            self._reset_view(render=False)
            self._camera_ready = True
        self._update_summary(scoped_rows)
        self._schedule_render()

    @staticmethod
    def _row_epoch(row):
        value = (row or {}).get("timestamp")
        try:
            return datetime.fromisoformat(str(value or "").replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return 0.0

    def _scoped_route_rows(self, rows=None):
        rows = list(self._all_route_rows if rows is None else rows)
        scope = self.scope_var.get() if hasattr(self, "scope_var") else "All History"
        if scope == "Current Session":
            started = float(getattr(self.app, "session_start_ts", 0.0) or 0.0)
            return [row for row in rows if self._row_epoch(row) >= started]
        if scope == "Active Expedition":
            manager = getattr(self.app, "expedition_manager", None)
            active = manager.active() if manager else None
            started = self._row_epoch({"timestamp": (active or {}).get("started")})
            systems = {
                str(name).casefold()
                for name in ((active or {}).get("stats") or {}).get("systems") or []
            }
            selected = [
                row for row in rows
                if str(row.get("system") or "").casefold() in systems
                and (not started or self._row_epoch(row) >= started)
            ]
            start_system = str((active or {}).get("start_system") or "").casefold()
            origin = next((
                row for row in reversed(rows)
                if start_system
                and str(row.get("system") or "").casefold() == start_system
                and (not started or self._row_epoch(row) <= started)
            ), None)
            if origin is not None and (not selected or selected[0] is not origin):
                selected.insert(0, origin)
            return selected
        return rows

    def _scope_changed(self, _event=None):
        config = getattr(self.app, "config", None)
        if isinstance(config, dict):
            config["explore_map_scope"] = self.scope_var.get()
        persist = getattr(self.app, "_persist_config", None)
        if callable(persist):
            persist()
        self.refresh(self._system_rows, self._value_rows)
        self._reset_view()
        self._persist_view_state()

    @staticmethod
    def _sample_route_rows(rows):
        rows = list(rows or [])
        if len(rows) <= MAX_ROUTE_POINTS:
            return rows
        last = len(rows) - 1
        return [
            rows[round(index * last / (MAX_ROUTE_POINTS - 1))]
            for index in range(MAX_ROUTE_POINTS)
        ]

    def _data_positions(self, recent=False):
        rows = self._route_rows[-50:] if recent else self._route_rows
        positions = [_position(row.get("pos")) for row in rows]
        if not recent:
            positions.extend(
                _position(bookmark.get("position")) for bookmark in self._bookmarks
            )
        return [position for position in positions if position is not None]

    @staticmethod
    def _bounds(positions):
        if not positions:
            return (0.0, 0.0, 0.0), 1000.0
        min_x = min(position[0] for position in positions)
        max_x = max(position[0] for position in positions)
        min_z = min(position[2] for position in positions)
        max_z = max(position[2] for position in positions)
        centre = ((min_x + max_x) / 2.0, 0.0, (min_z + max_z) / 2.0)
        radius = max(
            math.hypot(position[0] - centre[0], position[2] - centre[2])
            for position in positions
        )
        return centre, max(100.0, radius * 1.12)

    def _reset_view(self, render=True):
        mode = self.view_mode.get()
        positions = self._data_positions(
            recent=mode in {"Route Focus", "Current Vicinity"},
        )
        centre, radius = self._bounds(positions)
        self._pan = [0.0, 0.0]
        self._zoom = 1.0
        if mode == "Galactic Atlas":
            self._camera_center = list(GALACTIC_CENTRE)
            self._fit_radius = GALAXY_RADIUS_LY * 1.08
            self._zoom = 0.92
        elif mode == "Current Vicinity":
            current = _position(getattr(self.app, "current_coords", None))
            self._camera_center = list(current or centre)
            self._fit_radius = max(500.0, min(radius, 8000.0))
            self._zoom = 1.15
        else:
            self._camera_center = list(centre)
            self._fit_radius = radius
        if mode != "Galactic Atlas":
            # Galactic Atlas deliberately frames the whole disc, so only the
            # data-driven cameras are re-fitted to the canvas.
            self._fit_to_canvas(positions)
        if render:
            self._schedule_render()

    def _fit_to_canvas(self, positions):
        """Use the whole canvas, not just the square that fits its short side.

        ``_bounds`` measures a sphere around the data, and the scale derived
        from it divides by ``min(width, height)``. A route is usually far
        longer than it is tall, so that framing leaves most of a wide canvas
        empty. Projecting once with the spherical framing gives the real
        screen extent, which is then grown to whichever axis truly constrains
        it and recentred.
        """
        if not positions:
            return
        try:
            sized = (
                self.canvas.winfo_ismapped()
                and self.canvas.winfo_width() > 1 and self.canvas.winfo_height() > 1
            )
        except tk.TclError:
            sized = False
        if not sized:
            # This view is built while its workspace is still unpacked, so the
            # canvas has no size to fit against yet. Retry once it does rather
            # than baking a framing derived from the placeholder size.
            self._fit_pending = True
            return
        self._fit_pending = False
        context = self._projection()
        self._projection_context = context
        projected = [self._project(position) for position in positions]
        xs = [point[0] for point in projected]
        ys = [point[1] for point in projected]
        span_x = max(xs) - min(xs)
        span_y = max(ys) - min(ys)
        usable_x = context["width"] * FIT_MARGIN
        usable_y = context["height"] * FIT_MARGIN
        corrections = []
        if span_x > 1.0:
            corrections.append(usable_x / span_x)
        if span_y > 1.0:
            corrections.append(usable_y / span_y)
        if not corrections:
            return
        correction = min(corrections)
        zoom = max(0.08, min(80.0, self._zoom * correction))
        # Clamping the zoom would otherwise leave the framing off-centre.
        correction = zoom / self._zoom if self._zoom else 1.0
        self._zoom = zoom
        centre_x = (max(xs) + min(xs)) / 2.0
        centre_y = (max(ys) + min(ys)) / 2.0
        self._pan = [
            self._pan[0] - (centre_x - context["width"] / 2.0) * correction,
            self._pan[1] - (centre_y - context["height"] / 2.0) * correction,
        ]

    def _focus_current(self):
        position = _position(getattr(self.app, "current_coords", None))
        if position is None and self._route_rows:
            position = _position(self._route_rows[-1].get("pos"))
        if position is None:
            return
        nearby = self._data_positions(recent=True)
        _centre, radius = self._bounds(nearby)
        self.view_mode.set("Current Vicinity")
        self._camera_center = list(position)
        self._fit_radius = max(500.0, min(radius, 8000.0))
        self._zoom = 1.15
        self._pan = [0.0, 0.0]
        self._schedule_render()
        self._persist_view_state()

    def focus_system(self, system):
        """Centre the camera on a retained system and expose its markers."""
        wanted = str(system or "").strip().casefold()
        position = self._position_by_system.get(wanted)
        if position is None:
            position = next(
                (_position(row.get("position")) for row in self._marker_cache
                 if str(row.get("system") or "").strip().casefold() == wanted
                 and _position(row.get("position")) is not None),
                None,
            )
        if position is None:
            return False
        if "Revisit" in self.layer_vars:
            self.layer_vars["Revisit"].set(True)
        self.view_mode.set("Current Vicinity")
        self._camera_center = list(position)
        self._fit_radius = 1200.0
        self._zoom = 1.25
        self._pan = [0.0, 0.0]
        self._schedule_render()
        self._persist_view_state()
        return True

    def _find_target(self, _event=None):
        """Focus a retained system or canonical Codex region by name."""
        query = str(self.search_var.get() or "").strip()
        wanted = query.casefold()
        if not wanted:
            return "break"
        matches = [name for name in self._position_by_system if wanted in name]
        if matches:
            match = min(matches, key=lambda name: (name != wanted, len(name), name))
            self.focus_system(match)
            display = next(
                (str(row.get("system") or match) for row in self._all_route_rows
                 if str(row.get("system") or "").casefold() == match),
                match,
            )
            self.search_var.set(display)
            return "break"

        annotation_matches = [
            row for row in self._annotations
            if wanted in str(row.get("title") or "").casefold()
            or wanted in str(row.get("note") or "").casefold()
        ]
        if annotation_matches:
            row = min(
                annotation_matches,
                key=lambda item: (
                    str(item.get("title") or "").casefold() != wanted,
                    len(str(item.get("title") or "")),
                ),
            )
            position = _position(row.get("position"))
            self.view_mode.set("Current Vicinity")
            self.layer_vars["Annotations"].set(True)
            self._camera_center = list(position)
            self._fit_radius = 1200.0
            self._zoom = 1.25
            self._pan = [0.0, 0.0]
            self.search_var.set(row.get("title") or "Map annotation")
            record = self._annotation_marker(row)
            self._selected_point = {"x": -1000, "y": -1000, "record": record}
            self._show_record(record)
            self._schedule_render()
            self._persist_view_state()
            return "break"

        _segments, regions = region_geometry(16)
        region_matches = [row for row in regions if wanted in row["name"].casefold()]
        if region_matches:
            row = min(
                region_matches,
                key=lambda item: (item["name"].casefold() != wanted, len(item["name"])),
            )
            self.view_mode.set("Current Vicinity")
            self.layer_vars["Regions"].set(True)
            self._camera_center = list(row["position"])
            self._fit_radius = 12_000.0
            self._zoom = 1.0
            self._pan = [0.0, 0.0]
            self.search_var.set(row["name"])
            record = {
                "kind": "Region", "subject": row["name"],
                "detail": f"Universal Cartographics region {row['id']} of 42",
                "position": row["position"],
            }
            self._selected_point = {"x": -1000, "y": -1000, "record": record}
            self._show_record(record)
            self._schedule_render()
            self._persist_view_state()
            return "break"

        self.detail.config(text=f"SEARCH · {query} is not present in retained profile map data")
        return "break"

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
            # Motion frames are already deliberately lighter, so do not add a
            # long timer delay on top of their render time. Settled redraws can
            # remain gently coalesced because they contain the full data layer.
            delay = 1 if self._moving else 24
            self._render_job = self.canvas.after(delay, self._render)
        except tk.TclError:
            self._render_job = None

    def _on_canvas_configure(self, _event=None):
        if self._fit_pending:
            # Only ever completes a framing that never got a real canvas; a
            # later resize must not discard the commander's own zoom and pan.
            self._reset_view()
            return
        self._schedule_render()

    def _on_canvas_mapped(self, _event=None):
        if self._fit_pending:
            self._reset_view()
            return
        if self._render_pending or self._projection_context is None:
            self._schedule_render()

    @property
    def _moving(self):
        """Whether redraws should take the lightweight motion path."""
        return bool(self._drag_mode) or time.monotonic() < self._motion_until

    def on_shown(self):
        """Draw the first frame after becoming visible on the cheap path.

        Opening the workspace otherwise pays a full-detail frame, which the UI
        stall watchdog records as a page-open spike. The settle timer restores
        full detail immediately afterwards.
        """
        self._begin_motion()

    def _begin_motion(self):
        """Open a short motion window and queue the full-detail redraw."""
        self._motion_until = time.monotonic() + MOTION_WINDOW_S
        if self._settle_job is not None:
            try:
                self.canvas.after_cancel(self._settle_job)
            except tk.TclError:
                pass
            self._settle_job = None
        try:
            self._settle_job = self.canvas.after(
                int(MOTION_WINDOW_S * 1000) + 40, self._settle_render,
            )
        except tk.TclError:
            self._settle_job = None

    def _settle_render(self):
        self._settle_job = None
        self._motion_until = 0.0
        if not self._disposed:
            self._schedule_render()
            self._persist_view_state()

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
        self._pan[0] += dx
        self._pan[1] += dy
        self._schedule_render()

    def _end_drag(self, event):
        mode = self._drag_mode
        moved = self._drag_distance
        self._drag_mode = None
        self._drag_origin = None
        self._drag_last = None
        if mode == "context" and moved < 7:
            self._show_context_menu(event)
        elif mode and moved < 7:
            self._select_at(event.x, event.y)
        elif moved >= 7:
            # Restore the full-detail contour pass after the lightweight live
            # drag frame has kept rotation or panning responsive.
            self._schedule_render()
            self._persist_view_state()

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
        self._begin_motion()
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

    def _cluster_radius(self):
        """Return a screen-space grouping radius for the current scale."""
        visible_radius = self._fit_radius / max(self._zoom, 0.01)
        if self._motion_frame:
            return 34.0
        if visible_radius > 20_000:
            return 30.0
        if visible_radius > 6_000:
            return 26.0
        if visible_radius > 1_800:
            return 22.0
        if visible_radius > 600:
            return 18.0
        return 0.0

    @staticmethod
    def _cluster_screen_items(items, radius):
        """Group nearby projected records in roughly linear time.

        Each item starts with a projected ``(x, y, depth, perspective)`` tuple.
        A small spatial hash avoids all-pairs comparisons while neighbouring
        cells prevent visible seams at grid boundaries.
        """
        items = list(items or ())
        if radius <= 0.0:
            return [{"items": [item], "x": item[0][0], "y": item[0][1]} for item in items]
        cell_size = max(1.0, float(radius))
        radius_sq = float(radius) ** 2
        clusters = []
        cells = defaultdict(list)
        for item in items:
            x, y = item[0][0], item[0][1]
            cell = (math.floor(x / cell_size), math.floor(y / cell_size))
            match = None
            best_distance = radius_sq + 1.0
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for cluster in cells.get((cell[0] + dx, cell[1] + dy), ()):
                        distance = (cluster["x"] - x) ** 2 + (cluster["y"] - y) ** 2
                        if distance <= radius_sq and distance < best_distance:
                            match = cluster
                            best_distance = distance
            if match is None:
                match = {"items": [], "x": x, "y": y, "sum_x": 0.0, "sum_y": 0.0}
                clusters.append(match)
                cells[cell].append(match)
            match["items"].append(item)
            match["sum_x"] += x
            match["sum_y"] += y
            count = len(match["items"])
            match["x"] = match["sum_x"] / count
            match["y"] = match["sum_y"] / count
        return clusters

    def _focus_cluster(self, record):
        positions = [
            position for value in record.get("positions") or ()
            if (position := _position(value)) is not None
        ]
        if not positions:
            return
        centre, radius = self._bounds(positions)
        self.view_mode.set("Current Vicinity")
        self._camera_center = list(centre)
        self._fit_radius = max(100.0, radius * 1.18)
        self._zoom = 1.0
        self._pan = [0.0, 0.0]
        self._fit_to_canvas(positions)
        self._begin_motion()
        self._schedule_render()
        self._persist_view_state()

    def _select_at(self, x, y):
        point = self._nearest_point(x, y, 20)
        if not point:
            return
        self._selected_point = point
        record = point["record"]
        self._show_record(record, prefix="SELECTED")
        if record.get("kind") == "Cluster":
            self._focus_cluster(record)
            return
        if record.get("kind") not in {"Region", "Annotation"} and callable(self.open_record_callback):
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
        }

    def _project(self, position):
        context = self._projection_context
        dx = position[0] - self._camera_center[0]
        dy = position[1] - self._camera_center[1]
        dz = position[2] - self._camera_center[2]
        return (
            context["cx"] + dx * context["scale"],
            context["cy"] - dz * context["scale"],
            dy,
            1.0,
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
        # Resolved once: the drawing paths below read this thousands of times
        # per frame, and re-deriving it from the clock in those loops measured
        # more expensive than the detail reduction it selects.
        self._motion_frame = self._moving
        self._map_points = []
        self._projection_context = self._projection()
        width = int(self._projection_context["width"])
        height = int(self._projection_context["height"])
        background = Image.new("RGBA", (width, height), _rgba(THEME.inset, 255))
        self._background_image = background
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
        self._background_image = None
        self._background_photo = ImageTk.PhotoImage(background, master=canvas)
        if self._background_item is None:
            self._background_item = canvas.create_image(
                0, 0, image=self._background_photo, anchor="nw",
            )
        else:
            canvas.itemconfigure(self._background_item, image=self._background_photo)
        self._sync_navigation_animation()

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
        if dash and not self._motion_frame:
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
        for index in range(24 if self._motion_frame else 150):
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

    def _regions_will_cover_disc(self):
        """The flat atlas always keeps its base imagery under region washes."""
        return False

    def _draw_galaxy_structure(self):
        textured = self._draw_galaxy_texture()
        rim_divisions = 48 if self._motion_frame else 96
        rim = []
        for index in range(rim_divisions + 1):
            angle = math.tau * index / rim_divisions
            rim.append((
                GALACTIC_CENTRE[0] + math.cos(angle) * GALAXY_RADIUS_LY,
                0.0,
                GALACTIC_CENTRE[2] + math.sin(angle) * GALAXY_RADIUS_LY * 0.92,
            ))
        self._project_polyline(rim, _mix(THEME.inset, THEME.border, 0.74), width=2)
        # Retain a lightweight deterministic fallback if a damaged build is
        # missing the atlas artwork.
        if not textured:
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
        core_divisions = 32 if self._motion_frame else 64
        core = []
        for index in range(core_divisions + 1):
            angle = math.tau * index / core_divisions
            core.append((
                GALACTIC_CENTRE[0] + math.cos(angle) * 3500.0,
                0.0,
                GALACTIC_CENTRE[2] + math.sin(angle) * 3500.0,
            ))
        self._project_polyline(core, _mix(THEME.inset, THEME.orange, 0.35), width=2)

    def _draw_galaxy_texture(self):
        """Crop and scale only the visible part of the 2D atlas artwork.

        Even at very high zoom the resized image never exceeds the canvas.
        Panning therefore remains bounded and avoids rebuilding an enormous
        off-screen bitmap, which was the main risk in replacing the 3D map
        with a detailed raster atlas.
        """
        if self._background_image is None:
            return False
        if self._atlas_source is None and not self._atlas_source_failed:
            try:
                with Image.open(_resource_path(ATLAS_ASSET)) as source:
                    source = source.convert("RGBA")
                # Lighten-blend the luminous detail into the active theme.
                # Near-black source pixels therefore become the real map
                # backdrop instead of exposing the square image boundary.
                black = Image.new("RGBA", source.size, (0, 0, 0, 255))
                source = Image.blend(black, source, 0.78)
                backdrop = Image.new("RGBA", source.size, _rgba(THEME.inset, 255))
                self._atlas_source = ImageChops.lighter(backdrop, source)
            except (OSError, ValueError):
                self._atlas_source_failed = True
        source = self._atlas_source
        if source is None:
            return False

        context = self._projection_context
        centre = self._project(GALACTIC_CENTRE)
        diameter = 2.0 * GALAXY_RADIUS_LY * context["scale"]
        if diameter < 2.0:
            return False
        full_left = centre[0] - diameter / 2.0
        full_top = centre[1] - diameter / 2.0
        full_right = full_left + diameter
        full_bottom = full_top + diameter
        clip_left = max(0, int(math.floor(full_left)))
        clip_top = max(0, int(math.floor(full_top)))
        clip_right = min(context["width"], int(math.ceil(full_right)))
        clip_bottom = min(context["height"], int(math.ceil(full_bottom)))
        if clip_right <= clip_left or clip_bottom <= clip_top:
            return False

        source_width, source_height = source.size
        sx1 = max(0, min(source_width - 1, round((clip_left - full_left) / diameter * source_width)))
        sy1 = max(0, min(source_height - 1, round((clip_top - full_top) / diameter * source_height)))
        sx2 = max(sx1 + 1, min(source_width, round((clip_right - full_left) / diameter * source_width)))
        sy2 = max(sy1 + 1, min(source_height, round((clip_bottom - full_top) / diameter * source_height)))
        target_width = clip_right - clip_left
        target_height = clip_bottom - clip_top
        warp_key = (
            sx1, sy1, sx2, sy2, target_width, target_height,
            bool(self._motion_frame), str(THEME.inset),
        )
        if self._galaxy_warp_key != warp_key or self._galaxy_warp_image is None:
            resample = (
                Image.Resampling.BILINEAR
                if self._motion_frame else Image.Resampling.BICUBIC
            )
            self._galaxy_warp_image = source.crop((sx1, sy1, sx2, sy2)).resize(
                (target_width, target_height), resample=resample,
            )
            self._galaxy_warp_key = warp_key
        self._background_image.alpha_composite(
            self._galaxy_warp_image, dest=(clip_left, clip_top),
        )
        return True

    def _nice_grid_step(self):
        visible_radius = self._fit_radius / max(self._zoom, 0.01)
        target = visible_radius / 6.0
        steps = (10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 20000)
        return min(steps, key=lambda value: abs(value - target))

    def _draw_grid(self):
        if self.view_mode.get() == "Galactic Atlas":
            divisions = 36 if self._motion_frame else 72
            for radius in (10000, 20000, 30000, 40000, 50000):
                ring = []
                for index in range(divisions + 1):
                    angle = math.tau * index / divisions
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

    def _draw_region_fills(self, contour_step):
        """Wash every Codex region in its own hue, as the in-game map does."""
        background = self._background_image
        if background is None:
            return
        width = int(self._projection_context["width"])
        height = int(self._projection_context["height"])
        accent = str(THEME.accent)
        alpha = REGION_FILL_ALPHA
        # Interiors are the one part of the map read as shape rather than
        # detail, so they always use the finest raster; coarse fills stair-step
        # badly. A world-space pre-cull was measured and rejected: at shallow
        # pitch the plane recedes to the horizon, so distant regions really do
        # project into the top of the frame and no finite margin is safe.
        fill_step = REGION_FILL_STEP
        project = self._project
        visible = []
        # Allocating and compositing a whole-canvas layer costs more than the
        # geometry does, so the reachable bounds are accumulated here and the
        # wash is confined to them.
        left = top = float("inf")
        right = bottom = float("-inf")
        for x1, z1, x2, z2, region_id in region_fills(fill_step):
            corners = (
                project((x1, 0.0, z1)), project((x2, 0.0, z1)),
                project((x2, 0.0, z2)), project((x1, 0.0, z2)),
            )
            xs = [corner[0] for corner in corners]
            ys = [corner[1] for corner in corners]
            low_x = min(xs)
            high_x = max(xs)
            low_y = min(ys)
            high_y = max(ys)
            if high_x < 0 or low_x > width or high_y < 0 or low_y > height:
                continue
            left = min(left, low_x)
            right = max(right, high_x)
            top = min(top, low_y)
            bottom = max(bottom, high_y)
            visible.append((
                [(corner[0], corner[1]) for corner in corners],
                _region_fill_rgba(region_id, accent, alpha),
            ))
        if not visible:
            return
        left = max(0, int(math.floor(left)))
        top = max(0, int(math.floor(top)))
        right = min(width, int(math.ceil(right)) + 1)
        bottom = min(height, int(math.ceil(bottom)) + 1)
        if right <= left or bottom <= top:
            return
        # ImageDraw replaces alpha on an RGBA surface instead of blending it,
        # so the wash is collected on its own layer and composited once.
        overlay = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for points, colour in visible:
            draw.polygon([(x - left, y - top) for x, y in points], fill=colour)
        background.alpha_composite(overlay, dest=(left, top))

    def _draw_region_contours(self):
        visible_radius = self._fit_radius / max(self._zoom, 0.01)
        contour_step = 32 if visible_radius > 16000 else (16 if visible_radius > 4500 else 8)
        if self._motion_frame:
            contour_step = min(256, contour_step * 8)
        # Contours become more detailed as the camera approaches them. Label
        # anchors stay fixed so names do not visibly drift between zoom levels.
        segments, _ignored_labels = region_geometry(contour_step)
        _ignored_segments, labels = region_geometry(16)
        # During live movement the boundaries retain geographic context while
        # the translucent wash is deferred until the settled frame. Avoiding
        # that per-frame composition is what keeps atlas panning responsive.
        if not self._motion_frame:
            self._draw_region_fills(contour_step)
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
        # Names now sit over a coloured wash rather than bare background.
        label_colour = _mix(THEME.inset, THEME.text, 0.74)
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
        size = 6 if self.view_mode.get() == "Galactic Atlas" else 7
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
            if self._motion_frame and not forced:
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
            # Region names are deliberately not hover or click targets. Their
            # anchors sit at region centroids, which in populated space are
            # exactly where marker density is highest, so leaving them in the
            # hit-test pool let a label win clicks meant for a system, cluster
            # or annotation. Region search still selects a region by name.

    def _draw_route_and_markers(self):
        draw = self._background_draw
        self._navigation_route_path = []
        self._navigation_waypoint = None
        self._navigation_current = None
        rows = self._route_rows
        mapped_points = []
        position_by_system = self._position_by_system
        draw_rows = rows
        if self._motion_frame and len(rows) > 160:
            last = len(rows) - 1
            indexes = {
                round(sample * last / 159)
                for sample in range(160)
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
        if self.layer_vars.get("Planned") and self.layer_vars["Planned"].get():
            self._draw_planned_route()
        self._draw_route_path(route_points)
        if self.layer_vars.get("Return") and self.layer_vars["Return"].get():
            self._draw_return_trail(route_points)

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
        route_items = [
            (route_points[index][0], route_points[index][1], route_points[index][2], index)
            for index in visible_indexes
        ]
        mandatory_items = [item for item in route_items if item[3] in mandatory_indexes]
        ordinary_items = [item for item in route_items if item[3] not in mandatory_indexes]
        route_clusters = self._cluster_screen_items(ordinary_items, self._cluster_radius())
        point_limit = 70 if self._motion_frame else 320
        if len(route_clusters) > point_limit:
            last = len(route_clusters) - 1
            route_clusters = [
                route_clusters[round(sample * last / (point_limit - 1))]
                for sample in range(point_limit)
            ]
        for cluster in route_clusters:
            items = cluster["items"]
            if len(items) == 1:
                self._draw_route_system(items[0], mapped_points, current_system, len(route_points))
                continue
            positions = [item[2] for item in items]
            systems = [str(item[1].get("system") or "") for item in items]
            centre = self._mean_position(positions)
            self._draw_cluster_badge(cluster["x"], cluster["y"], len(items), THEME.muted)
            mapped_points.append({
                "x": cluster["x"], "y": cluster["y"], "depth": 0.0,
                "record": {
                    "kind": "Cluster", "subject": "Visited system cluster",
                    "detail": f"{len(items)} nearby visited systems · click to expand",
                    "system": systems[0] if systems and len(set(systems)) == 1 else "",
                    "position": centre, "positions": positions,
                },
            })
        for item in mandatory_items:
            self._draw_route_system(item, mapped_points, current_system, len(route_points))

        markers = self._marker_cache
        if self._motion_frame and len(markers) > 120:
            last = len(markers) - 1
            indexes = {
                round(sample * last / 119)
                for sample in range(120)
            }
            # Keep a bounded selection of human-authored bookmarks visible
            # while moving, then restore every intelligence marker on release.
            bookmark_indexes = [
                index for index, marker in enumerate(markers)
                if marker.get("layer") in {"Bookmarks", "Revisit", "Annotations"}
            ]
            if len(bookmark_indexes) > 40:
                bookmark_last = len(bookmark_indexes) - 1
                bookmark_indexes = [
                    bookmark_indexes[round(sample * bookmark_last / 39)]
                    for sample in range(40)
                ]
            indexes.update(bookmark_indexes)
            markers = [markers[index] for index in sorted(indexes)]
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
        projected_markers = [
            item for item in projected_markers
            if -25 <= item[0][0] <= self._projection_context["width"] + 25
            and -25 <= item[0][1] <= self._projection_context["height"] + 25
        ]
        annotations = [item for item in projected_markers if item[1]["layer"] == "Annotations"]
        intelligence = [item for item in projected_markers if item[1]["layer"] != "Annotations"]
        marker_clusters = self._cluster_screen_items(intelligence, self._cluster_radius())
        cluster_limit = 80 if self._motion_frame else 320
        if len(marker_clusters) > cluster_limit:
            last = len(marker_clusters) - 1
            marker_clusters = [
                marker_clusters[round(sample * last / (cluster_limit - 1))]
                for sample in range(cluster_limit)
            ]
        marker_counts = defaultdict(int)
        for cluster in marker_clusters:
            items = cluster["items"]
            plotted_markers += len(items)
            if len(items) > 1:
                positions = [item[2] for item in items]
                counts = defaultdict(int)
                systems = set()
                for _projected, marker, _position_value in items:
                    counts[marker["layer"]] += 1
                    if marker.get("system"):
                        systems.add(str(marker["system"]))
                detail = " · ".join(
                    f"{layer} {count}" for layer, count in sorted(counts.items())
                )
                centre = self._mean_position(positions)
                self._draw_cluster_badge(cluster["x"], cluster["y"], len(items), THEME.accent)
                mapped_points.append({
                    "x": cluster["x"], "y": cluster["y"], "depth": 0.0,
                    "record": {
                        "kind": "Cluster", "subject": "Discovery cluster",
                        "detail": f"{detail} · click to expand",
                        "system": next(iter(systems)) if len(systems) == 1 else "",
                        "position": centre, "positions": positions,
                    },
                })
                continue
            projected, marker, pos = items[0]
            px, py, depth, _perspective = projected
            system_key = str(marker.get("system") or "").casefold()
            offset_index = marker_counts[system_key]
            marker_counts[system_key] += 1
            px += ((offset_index % 3) - 1) * 9
            py += ((offset_index // 3) % 3 - 1) * 9
            self._draw_marker(
                px, py, marker["layer"], marker.get("colour") or LAYER_COLOURS[marker["layer"]], marker,
            )
            marker["position"] = pos
            mapped_points.append({"x": px, "y": py, "depth": depth, "record": marker})
        for projected, marker, pos in annotations:
            px, py, depth, _perspective = projected
            system_key = str(marker.get("system") or marker.get("annotation_id") or "").casefold()
            offset_index = marker_counts[system_key]
            marker_counts[system_key] += 1
            px += ((offset_index % 3) - 1) * 11
            py += ((offset_index // 3) % 3 - 1) * 11
            colour = self._annotation_colour(marker.get("category"))
            self._draw_marker(px, py, "Annotations", colour, marker)
            marker["position"] = pos
            mapped_points.append({"x": px, "y": py, "depth": depth, "record": marker})
            plotted_markers += 1

        current_position = _position(getattr(self.app, "current_coords", None))
        if current_position is None and current_system:
            current_position = position_by_system.get(current_system.casefold())
        if current_position is not None:
            px, py, depth, _perspective = self._project(current_position)
            if (
                -35 <= px <= self._projection_context["width"] + 35
                and -35 <= py <= self._projection_context["height"] + 35
            ):
                self._draw_current_locator(px, py, current_system)
                self._navigation_current = (px, py)
                mapped_points.append({
                    "x": px, "y": py, "depth": depth,
                    "record": {
                        "kind": "System", "system": current_system,
                        "subject": "You are here",
                        "detail": "Current commander location",
                        "position": current_position,
                    },
                })
        self._map_points = mapped_points
        self._plotted_markers = plotted_markers

    @staticmethod
    def _mean_position(positions):
        positions = [position for position in positions if position is not None]
        if not positions:
            return None
        count = len(positions)
        return tuple(sum(position[axis] for position in positions) / count for axis in range(3))

    def _draw_route_system(self, item, mapped_points, current_system, total_points):
        projected, row, pos, index = item
        px, py, depth, perspective = projected
        system = str(row.get("system") or "")
        is_current = bool(system and system.casefold() == current_system.casefold())
        is_endpoint = index in {0, total_points - 1}
        colour = THEME.orange if is_current else _star_colour(row.get("star_class"))
        radius = max(1.5, min(5.5, (4.2 if is_endpoint else 2.4) * perspective))
        if not is_current:
            glow = _mix(THEME.inset, colour, 0.28)
            self._background_draw.ellipse(
                (px - radius * 2.2, py - radius * 2.2,
                 px + radius * 2.2, py + radius * 2.2),
                outline=glow,
            )
            self._background_draw.ellipse(
                (px - radius, py - radius, px + radius, py + radius), fill=colour,
            )
        if is_endpoint and not is_current:
            self._background_text(
                px + 10, py - 8, system or "UNKNOWN",
                THEME.muted, size=7, bold=True, anchor="w",
            )
        mapped_points.append({
            "x": px, "y": py, "depth": depth,
            "record": {
                "kind": "System", "system": system,
                "subject": "Current system" if is_current else "Route arrival",
                "raw": row, "position": pos,
            },
        })

    def _draw_cluster_badge(self, x, y, count, colour):
        draw = self._background_draw
        radius = 9 if count < 100 else 11
        glow = _mix(THEME.inset, colour, 0.25)
        draw.ellipse((x - radius - 3, y - radius - 3, x + radius + 3, y + radius + 3), outline=glow)
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=THEME.inset, outline=colour, width=2,
        )
        label = str(count) if count < 100 else "99+"
        self._background_text(x, y, label, colour, size=6, bold=True)

    @staticmethod
    def _annotation_colour(category):
        return {
            "Danger": THEME.red,
            "Region of Interest": THEME.accent,
            "Survey Target": THEME.green,
            "Waypoint": THEME.yellow,
        }.get(str(category or ""), THEME.orange)

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
        if not self._motion_frame and len(route_points) >= 2:
            recent = route_points[-min(24, len(route_points)):]
            coordinates = []
            for projected, _row, _pos in recent:
                coordinates.extend((projected[0], projected[1]))
            self._background_line(
                coordinates, _mix(THEME.inset, THEME.orange, 0.94), width=2,
            )
            stride = max(2, len(recent) // 5)
            for index in range(stride, len(recent), stride):
                self._draw_direction_arrow(
                    recent[index - 1][0], recent[index][0], THEME.orange,
                )

    def _draw_planned_route(self):
        route = route_context(self.app)
        planned = route.get("planned") or ()
        next_system = str(route.get("next_system") or "").casefold()
        for source, dash in (("game", (7, 5)), ("waypoint", (2, 5))):
            points = []
            for row in planned:
                if row.get("source") != source:
                    continue
                pos = _position(row.get("pos"))
                if pos is not None:
                    points.append((self._project(pos), row, pos))
            if not self._navigation_route_path and len(points) >= 2:
                self._navigation_route_path = [
                    (projected[0], projected[1]) for projected, _row, _pos in points
                ]
            if self._navigation_waypoint is None and next_system:
                target = next((
                    point for point in points
                    if str(point[1].get("system") or "").casefold() == next_system
                ), None)
                if target is not None:
                    self._navigation_waypoint = (
                        target[0][0], target[0][1], target[1].get("system") or "Waypoint",
                    )
            if len(points) < 2:
                continue
            for index in range(1, len(points)):
                left, right = points[index - 1][0], points[index][0]
                if not self._visible_line(left, right):
                    continue
                self._background_line(
                    (left[0], left[1], right[0], right[1]),
                    LAYER_COLOURS["Planned"], width=2, dash=dash,
                )
                if not self._motion_frame and index % max(1, len(points) // 5) == 0:
                    self._draw_direction_arrow(left, right, LAYER_COLOURS["Planned"])

    def _ensure_animation_items(self):
        if self._animation_items:
            return
        canvas = self.canvas
        self._animation_items = {
            "pulse": canvas.create_oval(0, 0, 0, 0, outline=THEME.orange, width=1, state="hidden"),
            "tracer_glow": canvas.create_oval(0, 0, 0, 0, outline=_mix(THEME.inset, THEME.accent, 0.34), width=2, state="hidden"),
            "tracer": canvas.create_oval(0, 0, 0, 0, fill=THEME.accent, outline=THEME.text, width=1, state="hidden"),
            "beacon_outer": canvas.create_oval(0, 0, 0, 0, outline=THEME.yellow, width=1, state="hidden"),
            "beacon_inner": canvas.create_oval(0, 0, 0, 0, outline=_mix(THEME.inset, THEME.yellow, 0.72), width=1, state="hidden"),
        }

    def _hide_animation_items(self):
        for item in self._animation_items.values():
            try:
                self.canvas.itemconfigure(item, state="hidden")
            except tk.TclError:
                return

    @staticmethod
    def _prepare_animation_route(points):
        points = [(float(x), float(y)) for x, y in points or ()]
        if len(points) < 2:
            return None
        cumulative = [0.0]
        for left, right in zip(points, points[1:]):
            cumulative.append(cumulative[-1] + math.hypot(right[0] - left[0], right[1] - left[1]))
        if cumulative[-1] < 1.0:
            return None
        return points, cumulative, cumulative[-1]

    @staticmethod
    def _animation_route_point(route, fraction):
        points, cumulative, total = route
        distance = max(0.0, min(1.0, fraction)) * total
        for index in range(1, len(cumulative)):
            if cumulative[index] < distance:
                continue
            span = max(0.001, cumulative[index] - cumulative[index - 1])
            amount = (distance - cumulative[index - 1]) / span
            left, right = points[index - 1], points[index]
            return (
                left[0] + (right[0] - left[0]) * amount,
                left[1] + (right[1] - left[1]) * amount,
            )
        return points[-1]

    def _sync_navigation_animation(self):
        """Place cheap Canvas animation above the cached atlas bitmap."""
        try:
            self._ensure_animation_items()
        except tk.TclError:
            return
        self._hide_animation_items()
        if self._disposed or self._moving:
            return
        reduced_motion = bool(
            (getattr(self.app, "config", None) or {}).get("reduced_motion_enabled", False)
        )
        self._animation_route = self._prepare_animation_route(self._navigation_route_path)
        waypoint = self._navigation_waypoint
        if waypoint is not None:
            x, y, _name = waypoint
            radius = 10
            self.canvas.coords(
                self._animation_items["beacon_outer"],
                x - radius, y - radius, x + radius, y + radius,
            )
            self.canvas.coords(
                self._animation_items["beacon_inner"], x - 4, y - 4, x + 4, y + 4,
            )
            self.canvas.itemconfigure(self._animation_items["beacon_outer"], state="normal")
            self.canvas.itemconfigure(self._animation_items["beacon_inner"], state="normal")
        if reduced_motion:
            if self._animation_job is not None:
                try:
                    self.canvas.after_cancel(self._animation_job)
                except tk.TclError:
                    pass
                self._animation_job = None
            return
        self._animate_navigation()

    def _animate_navigation(self):
        if self._animation_job is not None:
            try:
                self.canvas.after_cancel(self._animation_job)
            except tk.TclError:
                pass
            self._animation_job = None
        if self._disposed or self._moving:
            self._hide_animation_items()
            return
        try:
            if not self.canvas.winfo_ismapped():
                self._hide_animation_items()
                return
        except tk.TclError:
            return
        self._animation_phase = (self._animation_phase + 0.16) % math.tau
        pulse_amount = (math.sin(self._animation_phase) + 1.0) / 2.0
        if self._navigation_current is not None:
            x, y = self._navigation_current
            radius = 11.0 + pulse_amount * 5.0
            self.canvas.coords(
                self._animation_items["pulse"], x - radius, y - radius, x + radius, y + radius,
            )
            self.canvas.itemconfigure(
                self._animation_items["pulse"], state="normal",
                outline=_mix(THEME.inset, THEME.orange, 0.32 + pulse_amount * 0.34),
            )
        if self._animation_route is not None:
            x, y = self._animation_route_point(
                self._animation_route, (self._animation_phase / math.tau) % 1.0,
            )
            self.canvas.coords(
                self._animation_items["tracer_glow"], x - 6, y - 6, x + 6, y + 6,
            )
            self.canvas.coords(
                self._animation_items["tracer"], x - 2, y - 2, x + 2, y + 2,
            )
            self.canvas.itemconfigure(self._animation_items["tracer_glow"], state="normal")
            self.canvas.itemconfigure(self._animation_items["tracer"], state="normal")
        if self._navigation_waypoint is not None:
            x, y, _name = self._navigation_waypoint
            beacon_amount = (math.sin(self._animation_phase * 0.72) + 1.0) / 2.0
            radius = 9.0 + beacon_amount * 4.0
            self.canvas.coords(
                self._animation_items["beacon_outer"],
                x - radius, y - radius, x + radius, y + radius,
            )
            self.canvas.itemconfigure(
                self._animation_items["beacon_outer"], state="normal",
                outline=_mix(THEME.inset, THEME.yellow, 0.42 + beacon_amount * 0.30),
            )
            self.canvas.itemconfigure(self._animation_items["beacon_inner"], state="normal")
        for item in self._animation_items.values():
            self.canvas.tag_raise(item)
        try:
            self._animation_job = self.canvas.after(
                NAVIGATION_ANIMATION_MS, self._animate_navigation,
            )
        except tk.TclError:
            self._animation_job = None

    def _draw_return_trail(self, route_points):
        points = list(reversed(route_points[-min(60, len(route_points)):]))
        if len(points) < 2:
            return
        for index in range(1, len(points)):
            left, right = points[index - 1][0], points[index][0]
            if not self._visible_line(left, right):
                continue
            self._background_line(
                (left[0], left[1], right[0], right[1]),
                LAYER_COLOURS["Return"], width=1, dash=(2, 6),
            )
            if not self._motion_frame and index % max(2, len(points) // 4) == 0:
                self._draw_direction_arrow(left, right, LAYER_COLOURS["Return"])

    def _draw_direction_arrow(self, left, right, colour):
        dx, dy = right[0] - left[0], right[1] - left[1]
        length = math.hypot(dx, dy)
        if length < 8:
            return
        ux, uy = dx / length, dy / length
        cx, cy = (left[0] + right[0]) / 2.0, (left[1] + right[1]) / 2.0
        size = 4.5
        self._background_draw.polygon((
            (cx + ux * size, cy + uy * size),
            (cx - ux * size - uy * size * 0.7, cy - uy * size + ux * size * 0.7),
            (cx - ux * size + uy * size * 0.7, cy - uy * size - ux * size * 0.7),
        ), fill=colour)

    def _draw_current_locator(self, x, y, _system):
        """Draw a compact, topmost ship glyph at the commander location."""
        draw = self._background_draw
        accent = THEME.orange
        glow = _mix(THEME.inset, accent, 0.32)
        draw.ellipse((x - 13, y - 13, x + 13, y + 13), outline=glow)
        self._draw_ship_glyph(x, y, 1.0, accent)

    def _current_ship_identity(self):
        ship = getattr(self.app, "cmdr_ship", None)
        if not isinstance(ship, dict):
            return "VoidCompass"
        return str(
            ship.get("ship_localised") or ship.get("ship")
            or ship.get("ship_name") or "VoidCompass"
        )

    def _ship_glyph_points(self, x, y, scale=1.0):
        """Generate a stable ship silhouette from the active vessel identity."""
        identity = self._current_ship_identity()
        seed = sum(
            (index + 1) * ord(character)
            for index, character in enumerate(identity.casefold())
        )
        nose = 9.0 + seed % 3
        wing_span = 7.0 + (seed // 3) % 4
        wing_sweep = 1.0 + (seed // 11) % 4
        tail = 7.0 + (seed // 17) % 3
        shoulder = 2.4 + ((seed // 23) % 3) * 0.45
        raw = (
            (0.0, -nose),
            (shoulder, -3.0),
            (wing_span, wing_sweep),
            (wing_span - 1.5, wing_sweep + 3.5),
            (3.6, 3.4),
            (3.0, tail),
            (0.0, tail - 2.0),
            (-3.0, tail),
            (-3.6, 3.4),
            (-wing_span + 1.5, wing_sweep + 3.5),
            (-wing_span, wing_sweep),
            (-shoulder, -3.0),
        )
        return tuple((x + dx * scale, y + dy * scale) for dx, dy in raw)

    def _draw_ship_glyph(self, x, y, scale, colour):
        draw = self._background_draw
        points = self._ship_glyph_points(x, y, scale)
        draw.polygon(points, fill=THEME.inset, outline=colour, width=2)
        draw.line(
            ((x, y - 5.5 * scale), (x, y + 4.5 * scale)),
            fill=_mix(THEME.inset, THEME.text, 0.70),
            width=max(1, round(scale)),
        )
        cockpit = max(1.2, 1.8 * scale)
        draw.ellipse(
            (x - cockpit, y - 2.4 * scale - cockpit,
             x + cockpit, y - 2.4 * scale + cockpit),
            fill=colour,
        )
        engine_y = y + (5.0 + (sum(ord(ch) for ch in self._current_ship_identity()) % 2)) * scale
        engine_radius = max(0.8, 1.2 * scale)
        for engine_x in (x - 2.0 * scale, x + 2.0 * scale):
            draw.ellipse(
                (engine_x - engine_radius, engine_y - engine_radius,
                 engine_x + engine_radius, engine_y + engine_radius),
                fill=THEME.accent,
            )

    def _draw_marker(self, x, y, layer, colour, marker=None):
        draw = self._background_draw
        glow_key = (THEME.inset, colour)
        glow = self._marker_glow_cache.get(glow_key)
        if glow is None:
            glow = _mix(THEME.inset, colour, 0.28)
            self._marker_glow_cache[glow_key] = glow
        draw.ellipse((x - 7, y - 7, x + 7, y + 7), outline=glow)
        if layer == "Annotations":
            category = str((marker or {}).get("category") or "Note")
            if category == "Danger":
                draw.polygon(
                    ((x, y - 7), (x + 7, y + 6), (x - 7, y + 6)),
                    outline=colour, fill=THEME.inset,
                )
                self._background_text(x, y + 1, "!", colour, size=6, bold=True)
            elif category == "Region of Interest":
                draw.rectangle((x - 6, y - 6, x + 6, y + 6), outline=colour, width=2)
                draw.ellipse((x - 2, y - 2, x + 2, y + 2), outline=colour)
            elif category == "Survey Target":
                draw.polygon(
                    ((x, y - 6), (x + 6, y + 5), (x - 6, y + 5)),
                    outline=colour, fill=THEME.inset,
                )
                draw.ellipse((x - 1, y, x + 1, y + 2), fill=colour)
            elif category == "Waypoint":
                draw.polygon(
                    ((x, y - 6), (x + 6, y), (x, y + 6), (x - 6, y)),
                    outline=colour, fill=THEME.inset,
                )
            else:
                draw.ellipse((x - 5, y - 5, x + 5, y + 5), outline=colour, width=2)
                draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=colour)
        elif layer == "Valuable":
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
        elif layer == "Sectors":
            status = str((marker or {}).get("status") or "untouched")
            draw.rectangle((x - 4, y - 4, x + 4, y + 4), outline=colour, width=2)
            if status == "surveyed":
                self._background_line((x - 3, y, x - 1, y + 3, x + 4, y - 3), colour, width=1)
            elif status == "incomplete":
                draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=colour)
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
        # Fixed legend explains the compact live-position symbol without
        # attaching a large label to the route itself.
        self._draw_ship_glyph(24, 28, 0.72, THEME.orange)
        self._background_text(
            38, 28, "CURRENT SHIP", THEME.muted,
            size=7, bold=True, anchor="w",
        )
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
        self._background_draw.ellipse(
            (centre_x - 2, centre_y - 2, centre_x + 2, centre_y + 2),
            fill=THEME.text,
        )
        for label, screen_dx, screen_dy, colour in (
            ("+X", 1.0, 0.0, THEME.red),
            ("+Z", 0.0, -1.0, THEME.accent),
        ):
            end_x = centre_x + screen_dx * 18.0
            end_y = centre_y + screen_dy * 18.0
            self._background_line((centre_x, centre_y, end_x, end_y), colour, width=2)
            self._background_text(
                end_x + screen_dx * 7.0,
                end_y + screen_dy * 7.0,
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
        route = route_context(self.app)
        route_text = ""
        if route.get("off_route"):
            distance = route.get("nearest_distance_ly")
            route_text = (
                f" · OFF ROUTE {distance:,.1f} ly from {route.get('nearest_system')}"
                if distance is not None else " · OFF ROUTE"
            )
        sector_text = ""
        manager = getattr(self.app, "expedition_manager", None)
        active = manager.active() if manager else None
        plan = (active or {}).get("sector_plan")
        if isinstance(plan, dict) and plan.get("center"):
            sector = sector_grid(
                self._snapshot.get("route_points") or (), plan.get("center"),
                plan.get("radius_ly", 500), plan.get("cell_size_ly", 100),
            )
            sector_text = f" · sector {sector.get('completion_percent', 0)}%"
        scope = self.scope_var.get() if hasattr(self, "scope_var") else "All History"
        self.summary.config(
            text=(
                f"{scope.upper()} · {unique:,} systems · {total_ly:,.1f} ly journalled · "
                f"42 Codex regions offline"
                f"{' · ' + str(len(self._annotations)) + ' map mark(s)' if self._annotations else ''}"
                f"{region_text}{representative}{route_text}{sector_text}"
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
        for row in snapshot.get("revisit_queue") or []:
            markers.append({
                "layer": "Revisit", "kind": "Revisit", "system": row.get("system"),
                "subject": "Unfinished exploration",
                "detail": row.get("detail") or "Worthwhile survey work remains",
                "position": row.get("position"),
            })
        for row in bookmarks:
            markers.append({
                "layer": "Bookmarks", "kind": "Bookmark", "system": row.get("system"),
                "subject": row.get("title") or row.get("kind") or "Bookmark",
                "detail": " · ".join(filter(None, (row.get("priority"), ", ".join(row.get("tags") or [])))),
                "position": row.get("position"), "bookmark_id": row.get("id"),
            })
        manager = getattr(self.app, "expedition_manager", None)
        active = manager.active() if manager else None
        plan = (active or {}).get("sector_plan")
        if isinstance(plan, dict) and plan.get("center"):
            grid = sector_grid(
                snapshot.get("route_points") or (), plan.get("center"),
                plan.get("radius_ly", 500), plan.get("cell_size_ly", 100),
            )
            cells = list(grid.get("cells") or [])
            important = [row for row in cells if row.get("status") != "untouched"]
            untouched = [row for row in cells if row.get("status") == "untouched"]
            # Keep the planning layer light on a galaxy-wide view. Visited
            # cells are never sampled out; untouched cells provide a bounded
            # wireframe around them.
            allowance = max(0, 140 - len(important))
            if allowance and len(untouched) > allowance:
                last = len(untouched) - 1
                untouched = [
                    untouched[round(index * last / max(1, allowance - 1))]
                    for index in range(allowance)
                ]
            for cell in important + untouched[:allowance]:
                status = str(cell.get("status") or "untouched")
                colour = (
                    THEME.green if status == "surveyed"
                    else THEME.orange if status == "incomplete" else THEME.dim
                )
                markers.append({
                    "layer": "Sectors", "kind": "Sector", "system": "",
                    "subject": f"{plan.get('name') or 'Expedition sector'} · cell {cell.get('id')}",
                    "detail": (
                        f"{status.title()} · {int(cell.get('surveyed_systems') or 0)}/"
                        f"{int(cell.get('visited_systems') or 0)} visited systems FSS complete"
                    ),
                    "position": cell.get("position"), "status": status, "colour": colour,
                })
        markers.extend(self._annotation_marker(row) for row in self._annotations)
        return markers
