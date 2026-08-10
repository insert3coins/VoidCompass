"""Live, profile-aware overlay arrangement studio."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from config import save_config
from ui_theme import (
    FONT_DISPLAY,
    FONT_MONO,
    FONT_TITLE,
    THEME,
    apply_window,
    button,
    configure_ttk,
    header,
    panel,
    scrollbar,
    section_label,
)


DEFAULT_POSITIONS = {
    "hud": (100, 100), "cargo_hud": (800, 400),
    "carrier_hud": (30, 180),
    "prospector_hud": (30, 600), "system_info_hud": (30, 30),
    "gravity_warning_hud": (1200, 530), "station_info_hud": (30, 380),
    "survey_status_hud": (30, 520), "toast_hud": (1200, 80),
    "heartbeat_hud": (24, 24), "colony_overlay": (40, 40),
}

DEFAULT_SIZES = {
    "hud": (430, 230), "cargo_hud": (360, 220),
    "carrier_hud": (430, 270),
    "prospector_hud": (380, 220), "system_info_hud": (560, 386),
    "gravity_warning_hud": (280, 90), "station_info_hud": (520, 442),
    "survey_status_hud": (520, 340), "toast_hud": (340, 110),
    "heartbeat_hud": (42, 42), "colony_overlay": (380, 220),
}

OVERLAY_LABELS = {
    "hud": "Navigation HUD",
    "cargo_hud": "Cargo HUD",
    "carrier_hud": "Fleet / Squadron Carrier HUD",
    "prospector_hud": "Prospector Analysis",
    "system_info_hud": "System Intelligence",
    "gravity_warning_hud": "Gravity Warning",
    "station_info_hud": "Station Information",
    "survey_status_hud": "Survey Operations",
    "toast_hud": "Event Toast",
    "heartbeat_hud": "Journal Heartbeat",
    "colony_overlay": "Colony Logistics",
}

OVERLAY_CARD_LABELS = {
    "hud": "NAVIGATION",
    "cargo_hud": "CARGO",
    "carrier_hud": "CARRIER",
    "prospector_hud": "PROSPECTOR",
    "system_info_hud": "SYS INTEL",
    "gravity_warning_hud": "GRAVITY",
    "station_info_hud": "STATION",
    "survey_status_hud": "SURVEY",
    "toast_hud": "TOASTS",
    "heartbeat_hud": "HEARTBEAT",
    "colony_overlay": "COLONY",
}

OVERLAY_ENABLE_KEYS = {
    "hud": "overlay_enabled",
    "cargo_hud": "cargo_overlay_enabled",
    "carrier_hud": "carrier_overlay_enabled",
    "prospector_hud": "prospector_overlay_enabled",
    "system_info_hud": "system_info_enabled",
    "gravity_warning_hud": "gravity_warning_overlay_enabled",
    "station_info_hud": "station_info_overlay_enabled",
    "survey_status_hud": "survey_status_overlay_enabled",
    "toast_hud": "toast_overlay_enabled",
    "heartbeat_hud": "heartbeat_overlay_enabled",
    "colony_overlay": "colony_overlay_enabled",
}

# Retained internally so existing profile data and old releases remain
# readable, but no longer offered by the exploration/mining cockpit catalogue.
HIDDEN_LEGACY_OVERLAYS = {"colony_overlay"}


def _position_geometry(x, y):
    """Return absolute Tk coordinates, including negative virtual-screen values."""
    return f"{int(x):+d}{int(y):+d}"


class OverlayLayoutStudio:
    def __init__(self, root, app):
        self.app = app
        self.config = app.config
        self._rows = {}
        self._drag_state = None
        self._preview_transform = None
        self._preview_fingerprint = None
        self._preview_resize_job = None
        self._refresh_job = None
        self._closing = False
        self.win = tk.Toplevel(root)
        self.win.title("Overlay Layout Studio")
        try:
            self.win.geometry(self.config.get("overlay_layout_studio_geometry", "1080x720"))
        except tk.TclError:
            self.win.geometry("1080x720")
        self.win.minsize(880, 620)
        apply_window(self.win)
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.bind("<Escape>", lambda _event: self.close())
        self.win.bind("<F5>", lambda _event: self.refresh())
        self._build()
        self.refresh()
        self._schedule_refresh()

    def is_open(self):
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def lift(self):
        self.win.lift()
        self.win.focus_force()

    def _overlay_records(self):
        for attr, x_key, y_key in self.app._OVERLAY_POSITION_SPECS:
            if attr in HIDDEN_LEGACY_OVERLAYS:
                continue
            overlay = getattr(self.app, attr, None)
            window = getattr(overlay, "win", overlay)
            if window is not None:
                try:
                    if not window.winfo_exists():
                        window = None
                except (AttributeError, tk.TclError):
                    window = None
            yield attr, x_key, y_key, window

    @staticmethod
    def _window_is_shown(window):
        try:
            return bool(window.winfo_viewable()) and str(window.state()) not in ("withdrawn", "iconic")
        except (AttributeError, tk.TclError):
            return False

    def _overlay_metrics(self, row):
        attr, x_key, y_key, window = row
        shown = self._window_is_shown(window)
        try:
            live_x, live_y = int(window.winfo_x()), int(window.winfo_y())
            width = max(int(window.winfo_width()), int(window.winfo_reqwidth()), 40)
            height = max(int(window.winfo_height()), int(window.winfo_reqheight()), 24)
        except (AttributeError, tk.TclError):
            live_x, live_y = DEFAULT_POSITIONS.get(attr, (30, 30))
            width, height = DEFAULT_SIZES.get(attr, (160, 70))
        # Layout Studio edits the saved commander layout, so its coordinates
        # remain authoritative even while Tk is still delivering a move for a
        # visible window.  Reading the old live coordinate here made the card
        # and profile jump back immediately after release on some overlays.
        if x_key in self.config and y_key in self.config:
            try:
                live_x = int(float(self.config[x_key]))
                live_y = int(float(self.config[y_key]))
            except (TypeError, ValueError):
                pass
        return live_x, live_y, width, height, shown

    def _set_overlay_position(self, row, x, y):
        attr, x_key, y_key, window = row
        x, y = int(round(x)), int(round(y))
        app_setter = getattr(self.app, "_set_overlay_position", None)
        if callable(app_setter):
            return app_setter(attr, x, y, authority_s=3.0)
        # Update the profile and any overlay-owned position cache before moving
        # the Tk window. Dynamic overlays (notably CarrierHUD) redraw on a
        # timer; leaving their private target stale makes that redraw snap the
        # window back over a position chosen in the Studio.
        self.config[x_key], self.config[y_key] = x, y
        overlay = getattr(self.app, attr, None)
        if overlay is not None and hasattr(overlay, "_desired_pos"):
            overlay._desired_pos = (x, y)
        if window is not None:
            window.geometry(_position_geometry(x, y))
        saved = getattr(self.app, "_overlay_pos_last_saved", None)
        if isinstance(saved, dict):
            saved[attr] = (x, y)
        return x, y

    def _build(self):
        masthead = header(
            self.win,
            "OVERLAY LAYOUT STUDIO",
            "ARRANGE THE ACTIVE COMMANDER'S COCKPIT WORKSPACE",
            height=66,
        )
        masthead.pack(fill=tk.X, padx=14, pady=(14, 8))
        identity = tk.Frame(masthead, bg=THEME.header)
        identity.pack(side=tk.RIGHT, fill=tk.Y, padx=14)
        tk.Label(
            identity,
            text=str(self.config.get("active_commander_name") or "Unknown Commander").upper(),
            bg=THEME.header,
            fg=THEME.text,
            font=FONT_DISPLAY,
        ).pack(anchor="e", pady=(12, 0))
        tk.Label(
            identity,
            text="LIVE EDIT  •  PASSTHROUGH SAFE",
            bg=THEME.header,
            fg=THEME.green,
            font=("Cascadia Mono", 8, "bold"),
        ).pack(anchor="e", pady=(2, 0))

        view_nav = tk.Frame(self.win, bg=THEME.bg)
        view_nav.pack(fill=tk.X, padx=14, pady=(0, 8))
        self.layout_tab_button = button(
            view_nav, "LAYOUT", lambda: self._show_view("layout"), accent=True,
        )
        self.layout_tab_button.pack(side=tk.LEFT)
        self.options_tab_button = button(
            view_nav, "OVERLAY SETTINGS", lambda: self._show_view("options"),
        )
        self.options_tab_button.pack(side=tk.LEFT, padx=(7, 0))
        tk.Label(
            view_nav,
            text="ONE WORKSPACE FOR MODULES, POSITIONING AND OVERLAY BEHAVIOUR",
            bg=THEME.bg, fg=THEME.dim, font=("Cascadia Mono", 8),
        ).pack(side=tk.RIGHT)

        self.view_host = tk.Frame(self.win, bg=THEME.bg)
        self.view_host.pack(fill=tk.BOTH, expand=True)
        self.layout_view = tk.Frame(self.view_host, bg=THEME.bg)
        self.options_view = tk.Frame(self.view_host, bg=THEME.bg)

        guide = panel(self.layout_view)
        guide.pack(fill=tk.X, padx=14, pady=(0, 8))
        guide_body = tk.Frame(guide, bg=THEME.panel)
        guide_body.pack(fill=tk.X, padx=12, pady=10)
        for number, title, detail in (
            ("01", "DRAG", "Move overlay cards inside the desktop preview"),
            ("02", "ALIGN", "Select a row and snap it to a nearby edge"),
            ("03", "SAVE", "Keep the positions or store a reusable preset"),
        ):
            item = tk.Frame(guide_body, bg=THEME.panel)
            item.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
            tk.Label(item, text=number, bg=THEME.panel, fg=THEME.accent,
                     font=FONT_TITLE).pack(side=tk.LEFT, padx=(0, 8))
            copy = tk.Frame(item, bg=THEME.panel)
            copy.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(copy, text=title, bg=THEME.panel, fg=THEME.orange,
                     font=FONT_DISPLAY, anchor="w").pack(fill=tk.X)
            tk.Label(copy, text=detail, bg=THEME.panel, fg=THEME.dim,
                     font=("Segoe UI", 8), anchor="w").pack(fill=tk.X)

        layout_card = panel(self.layout_view, accent=True)
        layout_card.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))
        workspace = tk.Frame(layout_card, bg=THEME.panel)
        workspace.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        preview_side = tk.Frame(workspace, bg=THEME.panel)
        preview_side.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        preview_header = tk.Frame(preview_side, bg=THEME.panel)
        preview_header.pack(fill=tk.X, pady=(0, 7))
        section_label(preview_header, "DESKTOP PREVIEW").pack(side=tk.LEFT)
        tk.Label(
            preview_header,
            text="DRAG A CARD TO POSITION ITS OVERLAY",
            bg=THEME.panel,
            fg=THEME.muted,
            font=("Cascadia Mono", 8),
        ).pack(side=tk.RIGHT)
        self.preview_canvas = tk.Canvas(
            preview_side,
            bg=THEME.inset,
            highlightbackground=THEME.border,
            highlightcolor=THEME.accent,
            highlightthickness=1,
            bd=0,
            cursor="hand2",
        )
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        self.preview_canvas.bind("<Configure>", self._preview_resized)
        self.preview_canvas.bind("<ButtonPress-1>", self._preview_press)
        self.preview_canvas.bind("<B1-Motion>", self._preview_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self._preview_release)

        list_side = tk.Frame(workspace, bg=THEME.panel, width=390)
        list_side.pack(side=tk.RIGHT, fill=tk.BOTH)
        list_side.pack_propagate(False)
        list_header = tk.Frame(list_side, bg=THEME.panel)
        list_header.pack(fill=tk.X, pady=(0, 7))
        section_label(list_header, "OVERLAY INDEX").pack(side=tk.LEFT)
        self.count_var = tk.StringVar(value="0 OVERLAYS")
        tk.Label(list_header, textvariable=self.count_var, bg=THEME.panel,
                 fg=THEME.muted, font=FONT_MONO).pack(side=tk.RIGHT)

        style = configure_ttk(self.win, "OverlayLayout")
        style.configure(
            "OverlayLayout.Treeview",
            background=THEME.inset,
            fieldbackground=THEME.inset,
            foreground=THEME.text,
            rowheight=28,
            borderwidth=0,
            font=FONT_MONO,
        )
        style.configure(
            "OverlayLayout.Treeview.Heading",
            background=THEME.panel_raised,
            foreground=THEME.orange,
            font=FONT_DISPLAY,
        )
        wrap = tk.Frame(list_side, bg=THEME.panel)
        wrap.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            wrap,
            columns=("overlay", "position", "size", "visible"),
            show="headings",
            selectmode="browse",
            style="OverlayLayout.Treeview",
        )
        for key, title, width, stretch in (
            ("overlay", "OVERLAY", 160, True),
            ("position", "POSITION", 105, False),
            ("size", "SIZE", 80, False),
            ("visible", "STATE", 65, False),
        ):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=80, anchor=tk.W, stretch=stretch)
        bar = scrollbar(wrap, orient=tk.VERTICAL, command=self.tree.yview, prefix="OverlayLayout")
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)

        controls = tk.Frame(self.layout_view, bg=THEME.bg)
        controls.pack(fill=tk.X, padx=14, pady=(0, 8))

        preset_card = panel(controls)
        preset_card.pack(side=tk.LEFT, fill=tk.X, expand=True)
        preset_inner = tk.Frame(preset_card, bg=THEME.panel)
        preset_inner.pack(fill=tk.X, padx=12, pady=10)
        tk.Label(preset_inner, text="PROFILE PRESET", bg=THEME.panel, fg=THEME.muted,
                 font=FONT_DISPLAY).pack(side=tk.LEFT, padx=(0, 8))
        self.preset_var = tk.StringVar()
        self.preset_box = ttk.Combobox(
            preset_inner,
            textvariable=self.preset_var,
            state="readonly",
            width=19,
            style="OverlayLayout.TCombobox",
        )
        self.preset_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        button(preset_inner, "APPLY", self.apply_preset, accent=True).pack(side=tk.LEFT, padx=(8, 0))
        button(preset_inner, "SAVE", self.save_preset).pack(side=tk.LEFT, padx=(6, 0))
        button(preset_inner, "DELETE", self.delete_preset, danger=True).pack(side=tk.LEFT, padx=(6, 0))

        actions = tk.Frame(self.layout_view, bg=THEME.bg)
        actions.pack(fill=tk.X, padx=14, pady=(0, 14))
        self.status_var = tk.StringVar(value="Drag overlay cards above; mouse passthrough can remain enabled.")
        tk.Label(
            actions,
            textvariable=self.status_var,
            bg=THEME.bg,
            fg=THEME.muted,
            font=("Cascadia Mono", 8),
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        button(actions, "REFRESH", self.refresh, muted=True).pack(side=tk.LEFT, padx=(8, 0))
        self.selected_toggle_button = button(
            actions, "ENABLE SELECTED", self.toggle_selected_overlay,
        )
        self.selected_toggle_button.pack(side=tk.LEFT, padx=(6, 0))
        button(actions, "SNAP", self.snap_selected).pack(side=tk.LEFT, padx=(6, 0))
        button(actions, "RESET", self.reset_selected, danger=True).pack(side=tk.LEFT, padx=(6, 0))
        button(actions, "DONE", self.close, accent=True).pack(side=tk.LEFT, padx=(12, 0))
        self._build_overlay_options()
        self._show_view("layout")

    @staticmethod
    def _set_button_resting(widget, bg, fg):
        widget.configure(bg=bg, fg=fg)
        widget._theme_resting_bg = bg
        widget._theme_resting_fg = fg

    def _show_view(self, name):
        self.layout_view.pack_forget()
        self.options_view.pack_forget()
        target = self.options_view if name == "options" else self.layout_view
        target.pack(fill=tk.BOTH, expand=True)
        active, inactive = THEME.accent, THEME.panel_raised
        self._set_button_resting(
            self.layout_tab_button,
            active if name == "layout" else inactive,
            THEME.bg if name == "layout" else THEME.text,
        )
        self._set_button_resting(
            self.options_tab_button,
            active if name == "options" else inactive,
            THEME.bg if name == "options" else THEME.text,
        )
        if name == "options":
            self._refresh_overlay_options()

    def _option_card(self, parent, title):
        card = panel(parent)
        heading = tk.Frame(card, bg=THEME.panel)
        heading.pack(fill=tk.X, padx=12, pady=(10, 5))
        section_label(heading, title).pack(side=tk.LEFT)
        body = tk.Frame(card, bg=THEME.panel)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))
        return card, body

    def _build_overlay_options(self):
        self._option_buttons = {}
        self._module_buttons = {}
        scroll_host = tk.Frame(self.options_view, bg=THEME.bg)
        scroll_host.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))
        self.options_canvas = tk.Canvas(
            scroll_host,
            bg=THEME.bg,
            bd=0,
            highlightthickness=0,
        )
        options_bar = scrollbar(
            scroll_host,
            orient=tk.VERTICAL,
            command=self.options_canvas.yview,
            prefix="OverlayLayout",
        )
        self.options_canvas.configure(yscrollcommand=options_bar.set)
        self.options_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        options_bar.pack(side=tk.RIGHT, fill=tk.Y, padx=(7, 0))

        body = tk.Frame(self.options_canvas, bg=THEME.bg)
        self._options_canvas_window = self.options_canvas.create_window(
            (0, 0), window=body, anchor="nw",
        )
        body.bind("<Configure>", self._options_content_resized)
        self.options_canvas.bind("<Configure>", self._options_canvas_resized)

        modules_card, modules = self._option_card(body, "OVERLAY MODULES")
        modules_card.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            modules,
            text="Switch modules live. Disabled modules remain positionable as OFF cards on the Layout view.",
            bg=THEME.panel, fg=THEME.dim, font=("Segoe UI", 8), anchor="w",
        ).grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 7))
        for column in range(4):
            modules.grid_columnconfigure(column, weight=1, uniform="overlay-module")
        for index, attr in enumerate(OVERLAY_ENABLE_KEYS):
            module_button = button(
                modules,
                OVERLAY_LABELS.get(attr, attr),
                lambda selected=attr: self.toggle_overlay(selected),
                padx=8,
                pady=6,
            )
            module_button.grid(
                row=1 + index // 4, column=index % 4,
                sticky="ew", padx=(0 if index % 4 == 0 else 6, 0), pady=(0, 6),
            )
            self._module_buttons[attr] = module_button

        columns = tk.Frame(body, bg=THEME.bg)
        columns.pack(fill=tk.BOTH, expand=True)
        columns.grid_columnconfigure(0, weight=1, uniform="overlay-options")
        columns.grid_columnconfigure(1, weight=1, uniform="overlay-options")
        columns.grid_rowconfigure(0, weight=1)
        columns.grid_rowconfigure(1, weight=1)

        interaction_card, interaction = self._option_card(columns, "DISPLAY & INTERACTION")
        interaction_card.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 8))
        self._option_toggle(interaction, "Mouse passthrough", "overlay_mouse_passthrough")
        self._option_toggle(interaction, "Compact Navigation HUD", "hud_compact_mode")
        self.overlay_scale_var = tk.StringVar(
            value=str(self.config.get("overlay_text_scale_percent", 100))
        )
        self._option_entry(interaction, "Overlay text scale (%)", self.overlay_scale_var)

        alerts_card, alerts = self._option_card(columns, "ACTIONABLE ALERTS")
        alerts_card.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 8))
        self._option_toggle(alerts, "Clear-to-sample notifications", "sample_clear_notifications_enabled")
        self._option_toggle(alerts, "Rebuy coverage warnings", "rebuy_warnings_enabled")
        self._option_toggle(alerts, "Unsold data-risk warnings", "data_risk_warnings_enabled")

        timing_card, timing = self._option_card(columns, "TIMING & THRESHOLDS")
        timing_card.grid(row=1, column=0, sticky="nsew", padx=(0, 4))
        self.prospector_timeout_var = tk.StringVar(
            value=str(self.config.get("prospector_hud_timeout_s", 45))
        )
        self.system_timeout_var = tk.StringVar(
            value=str(self.config.get("system_info_timeout_s", 30))
        )
        self.gravity_timeout_var = tk.StringVar(
            value=str(self.config.get("gravity_warning_hud_timeout_s", 20))
        )
        self.station_timeout_var = tk.StringVar(
            value=str(self.config.get("station_info_timeout_s", 30))
        )
        self.gravity_threshold_var = tk.StringVar(
            value=str(self.config.get("gravity_warning_threshold_g", 3.0))
        )
        self._option_entry(timing, "Prospector auto-hide (seconds)", self.prospector_timeout_var)
        self._option_entry(timing, "System Intelligence auto-hide (seconds)", self.system_timeout_var)
        self._option_entry(timing, "Gravity warning auto-hide (seconds)", self.gravity_timeout_var)
        self._option_toggle(timing, "Auto-hide Station Link", "station_info_auto_hide_enabled")
        self.station_timeout_entry = self._option_entry(
            timing, "Station Link hide delay (seconds)", self.station_timeout_var,
        )
        self._option_entry(timing, "Gravity warning threshold (g)", self.gravity_threshold_var)

        crt_card, crt = self._option_card(columns, "NAVIGATION HUD EFFECTS")
        crt_card.grid(row=1, column=1, sticky="nsew", padx=(4, 0))
        self._option_toggle(crt, "CRT effects", "hud_crt_enabled")
        self._option_toggle(crt, "Subtle phosphor shimmer", "hud_crt_motion_enabled")
        intensity_row = tk.Frame(crt, bg=THEME.panel)
        intensity_row.pack(fill=tk.X, pady=(4, 0))
        tk.Label(
            intensity_row, text="CRT intensity", bg=THEME.panel, fg=THEME.text,
            font=("Segoe UI", 9), anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.crt_intensity_var = tk.StringVar(
            value=str(self.config.get("hud_crt_intensity", "Subtle") or "Subtle").title()
        )
        intensity_menu = tk.OptionMenu(
            intensity_row, self.crt_intensity_var, "Subtle", "Standard", "Strong",
        )
        intensity_menu.configure(
            bg=THEME.panel_raised, fg=THEME.text, activebackground=THEME.panel_alt,
            activeforeground=THEME.accent, relief=tk.FLAT, bd=0,
            highlightthickness=1, highlightbackground=THEME.border, width=10,
        )
        intensity_menu["menu"].configure(bg=THEME.panel_raised, fg=THEME.text)
        intensity_menu.pack(side=tk.RIGHT)

        self._bind_options_mousewheel(body)

        footer = tk.Frame(self.options_view, bg=THEME.bg)
        footer.pack(fill=tk.X, padx=14, pady=(0, 14))
        self.options_status_var = tk.StringVar(
            value="Changes are commander-profile settings and apply to the live overlays."
        )
        tk.Label(
            footer, textvariable=self.options_status_var, bg=THEME.bg, fg=THEME.muted,
            font=("Cascadia Mono", 8), anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        button(footer, "APPLY SETTINGS", self.save_overlay_options, accent=True).pack(side=tk.RIGHT)

    def _options_content_resized(self, _event=None):
        try:
            self.options_canvas.configure(scrollregion=self.options_canvas.bbox("all"))
        except tk.TclError:
            pass

    def _options_canvas_resized(self, event):
        try:
            self.options_canvas.itemconfigure(self._options_canvas_window, width=max(1, event.width))
        except tk.TclError:
            pass

    def _bind_options_mousewheel(self, widget):
        widget.bind("<MouseWheel>", self._options_mousewheel, add="+")
        widget.bind("<Button-4>", self._options_mousewheel, add="+")
        widget.bind("<Button-5>", self._options_mousewheel, add="+")
        for child in widget.winfo_children():
            self._bind_options_mousewheel(child)

    def _options_mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            units = -1
        elif getattr(event, "num", None) == 5:
            units = 1
        else:
            delta = int(getattr(event, "delta", 0) or 0)
            units = -max(-3, min(3, int(delta / 120))) if delta else 0
        if units:
            self.options_canvas.yview_scroll(units, "units")
        return "break"

    def _option_toggle(self, parent, label, key):
        row = tk.Frame(parent, bg=THEME.panel)
        row.pack(fill=tk.X, pady=(3, 4))
        tk.Label(
            row, text=label, bg=THEME.panel, fg=THEME.text,
            font=("Segoe UI", 9), anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        control = button(row, "OFF", lambda setting=key: self.toggle_option(setting), padx=10, pady=4)
        control.pack(side=tk.RIGHT)
        self._option_buttons[key] = control
        return control

    @staticmethod
    def _option_entry(parent, label, variable):
        row = tk.Frame(parent, bg=THEME.panel)
        row.pack(fill=tk.X, pady=(3, 4))
        tk.Label(
            row, text=label, bg=THEME.panel, fg=THEME.text,
            font=("Segoe UI", 9), anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        entry = tk.Entry(
            row, textvariable=variable, width=11, bg=THEME.input, fg=THEME.text,
            insertbackground=THEME.accent, relief=tk.FLAT, bd=0,
            highlightthickness=1, highlightbackground=THEME.border,
            highlightcolor=THEME.accent, justify=tk.RIGHT,
        )
        entry.pack(side=tk.RIGHT)
        return entry

    def _refresh_toggle_button(self, widget, enabled, on_text="ON", off_text="OFF"):
        bg = THEME.accent if enabled else THEME.panel_raised
        fg = THEME.bg if enabled else THEME.muted
        widget.configure(text=on_text if enabled else off_text)
        self._set_button_resting(widget, bg, fg)

    def _refresh_overlay_options(self):
        for attr, widget in self._module_buttons.items():
            enabled = self._overlay_enabled(attr)
            label = OVERLAY_CARD_LABELS.get(attr, attr.replace("_", " ").upper())
            self._refresh_toggle_button(widget, enabled, f"{label}  ON", f"{label}  OFF")
        for key, widget in self._option_buttons.items():
            self._refresh_toggle_button(widget, bool(self.config.get(key, False)))
        self.overlay_scale_var.set(str(self.config.get("overlay_text_scale_percent", 100)))
        self.prospector_timeout_var.set(str(self.config.get("prospector_hud_timeout_s", 45)))
        self.system_timeout_var.set(str(self.config.get("system_info_timeout_s", 30)))
        self.gravity_timeout_var.set(str(self.config.get("gravity_warning_hud_timeout_s", 20)))
        self.station_timeout_var.set(str(self.config.get("station_info_timeout_s", 30)))
        self.gravity_threshold_var.set(str(self.config.get("gravity_warning_threshold_g", 3.0)))
        self.crt_intensity_var.set(str(self.config.get("hud_crt_intensity", "Subtle") or "Subtle").title())
        self.station_timeout_entry.configure(
            state=tk.NORMAL if self.config.get("station_info_auto_hide_enabled", False) else tk.DISABLED,
            disabledbackground=THEME.panel_raised,
            disabledforeground=THEME.muted,
        )

    def _overlay_enabled(self, attr):
        key = OVERLAY_ENABLE_KEYS.get(attr)
        return bool(self.config.get(key, False)) if key else False

    def toggle_option(self, key):
        self.config[key] = not bool(self.config.get(key, False))
        save_config(self.config)
        if key == "overlay_mouse_passthrough":
            self.app._apply_overlay_mouse_passthrough()
        elif key in ("hud_compact_mode", "hud_crt_enabled", "hud_crt_motion_enabled"):
            self.app.update_hud()
        elif key == "station_info_auto_hide_enabled":
            self._apply_station_info_policy()
        self._refresh_overlay_options()
        if key == "station_info_auto_hide_enabled":
            state = "enabled" if self.config.get(key, False) else "disabled; visible while docked"
            self.options_status_var.set(f"Station Link auto-hide {state} for this commander.")
        else:
            self.options_status_var.set(f"Saved {key.replace('_', ' ')} for this commander.")

    def _apply_station_info_policy(self):
        """Apply Station Link visibility/timing immediately to the docked session."""
        station_hud = getattr(self.app, "station_info_hud", None)
        if station_hud is None:
            return
        if getattr(self.app, "current_docked", False) and getattr(
            self.app, "current_station_name", None
        ):
            station_hud.on_docked(self.app)
        else:
            station_hud.hide()

    def save_overlay_options(self):
        try:
            scale = max(75, min(200, int(float(self.overlay_scale_var.get()))))
            prospector_timeout = max(5, int(float(self.prospector_timeout_var.get())))
            system_timeout = max(5, int(float(self.system_timeout_var.get())))
            gravity_timeout = max(5, int(float(self.gravity_timeout_var.get())))
            station_timeout = max(5, int(float(self.station_timeout_var.get())))
            gravity_threshold = max(0.5, float(self.gravity_threshold_var.get()))
        except (TypeError, ValueError):
            messagebox.showerror(
                "Overlay Settings",
                "Use numbers for text scale, auto-hide times and gravity threshold.",
                parent=self.win,
            )
            return
        self.config.update({
            "overlay_text_scale_percent": scale,
            "prospector_hud_timeout_s": prospector_timeout,
            "system_info_timeout_s": system_timeout,
            "gravity_warning_hud_timeout_s": gravity_timeout,
            "station_info_timeout_s": station_timeout,
            "gravity_warning_threshold_g": gravity_threshold,
            "hud_crt_intensity": self.crt_intensity_var.get(),
        })
        save_config(self.config)
        self.app.update_hud()
        self._apply_station_info_policy()
        self._refresh_overlay_options()
        self.options_status_var.set(
            "Overlay settings saved. Station Link timing is active now; text scale applies as overlays reopen."
        )

    def _preview_resized(self, _event=None):
        if self._preview_resize_job is not None:
            try:
                self.win.after_cancel(self._preview_resize_job)
            except tk.TclError:
                pass
        self._preview_resize_job = self.win.after(40, self._finish_preview_resize)

    def _finish_preview_resize(self):
        self._preview_resize_job = None
        self._draw_desktop_preview(force=True)

    def _selected_attr(self):
        chosen = self.tree.selection()
        return chosen[0] if chosen else None

    def _draw_desktop_preview(self, force=False):
        if not hasattr(self, "preview_canvas") or not self.is_open():
            return
        canvas = self.preview_canvas
        canvas_w = max(160, int(canvas.winfo_width()))
        canvas_h = max(120, int(canvas.winfo_height()))
        left, top, right, bottom = self._desktop_bounds(self.win)
        desktop_w, desktop_h = max(1, right - left), max(1, bottom - top)
        records = list(self._overlay_records())
        metrics = [(row, self._overlay_metrics(row)) for row in records]
        fingerprint = (
            canvas_w, canvas_h, left, top, right, bottom, self._selected_attr(),
            tuple((row[0],) + tuple(values) for row, values in metrics),
        )
        if not force and fingerprint == self._preview_fingerprint:
            return
        self._preview_fingerprint = fingerprint

        pad = 22
        scale = min(
            max(1, canvas_w - pad * 2) / desktop_w,
            max(1, canvas_h - pad * 2) / desktop_h,
        )
        draw_w, draw_h = desktop_w * scale, desktop_h * scale
        origin_x = (canvas_w - draw_w) / 2
        origin_y = (canvas_h - draw_h) / 2
        self._preview_transform = (left, top, right, bottom, origin_x, origin_y, scale)

        canvas.delete("all")
        canvas.create_rectangle(
            origin_x, origin_y, origin_x + draw_w, origin_y + draw_h,
            fill=THEME.input, outline=THEME.accent, width=2,
        )
        for step in range(1, 4):
            gx = origin_x + draw_w * step / 4
            gy = origin_y + draw_h * step / 4
            canvas.create_line(gx, origin_y, gx, origin_y + draw_h, fill=THEME.border, dash=(2, 5))
            canvas.create_line(origin_x, gy, origin_x + draw_w, gy, fill=THEME.border, dash=(2, 5))

        try:
            primary_w = int(self.win.winfo_screenwidth())
            primary_h = int(self.win.winfo_screenheight())
            px1 = origin_x + (0 - left) * scale
            py1 = origin_y + (0 - top) * scale
            px2 = px1 + primary_w * scale
            py2 = py1 + primary_h * scale
            if left != 0 or top != 0 or desktop_w != primary_w or desktop_h != primary_h:
                canvas.create_rectangle(
                    px1, py1, px2, py2, outline=THEME.muted, dash=(5, 4), width=1,
                )
                canvas.create_text(
                    px1 + 7, py1 + 7, text="PRIMARY", anchor="nw",
                    fill=THEME.muted, font=("Cascadia Mono", 7, "bold"),
                )
        except tk.TclError:
            pass

        selected = self._selected_attr()
        for row, (x, y, width, height, shown) in metrics:
            attr = row[0]
            enabled = self._overlay_enabled(attr)
            x1 = origin_x + (x - left) * scale
            y1 = origin_y + (y - top) * scale
            display_w = max(50, width * scale)
            display_h = max(24, height * scale)
            x2 = min(origin_x + draw_w, x1 + display_w)
            y2 = min(origin_y + draw_h, y1 + display_h)
            x1 = max(origin_x, min(x1, origin_x + draw_w - 12))
            y1 = max(origin_y, min(y1, origin_y + draw_h - 12))
            if x2 <= x1:
                x2 = min(origin_x + draw_w, x1 + 50)
            if y2 <= y1:
                y2 = min(origin_y + draw_h, y1 + 24)
            chosen = attr == selected
            outline = THEME.accent if chosen else (THEME.orange if enabled else THEME.muted)
            fill = THEME.selection if chosen else (THEME.panel_raised if enabled else THEME.panel)
            tag = f"overlay:{attr}"
            canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=fill,
                outline=outline,
                width=2 if chosen else 1,
                dash=() if enabled or chosen else (4, 3),
                tags=("overlay-card", tag),
            )
            label = OVERLAY_CARD_LABELS.get(attr, attr.replace("_", " ").upper()[:12])
            if not enabled:
                label += " · OFF"
            canvas.create_text(
                (x1 + x2) / 2, (y1 + y2) / 2,
                text=label,
                anchor="center",
                fill=THEME.text if enabled or chosen else THEME.muted,
                font=("Segoe UI", 7, "bold"),
                tags=("overlay-card", tag),
            )
        if selected:
            canvas.tag_raise(f"overlay:{selected}")
        canvas.create_text(
            origin_x + 7, origin_y + draw_h - 7,
            text=f"VIRTUAL DESKTOP  {desktop_w} × {desktop_h}",
            anchor="sw", fill=THEME.dim, font=("Cascadia Mono", 7),
        )

    def _preview_attr_at(self, x, y):
        try:
            items = self.preview_canvas.find_overlapping(x - 2, y - 2, x + 2, y + 2)
            for item in reversed(items):
                for tag in self.preview_canvas.gettags(item):
                    if tag.startswith("overlay:"):
                        return tag.split(":", 1)[1]
        except tk.TclError:
            pass
        return None

    def _preview_press(self, event):
        attr = self._preview_attr_at(event.x, event.y)
        row = self._rows.get(attr)
        if row is None:
            self._drag_state = None
            return
        self.tree.selection_set(attr)
        self.tree.see(attr)
        x, y, _width, _height, _shown = self._overlay_metrics(row)
        self._drag_state = {
            "attr": attr,
            "canvas_x": event.x,
            "canvas_y": event.y,
            "screen_x": x,
            "screen_y": y,
        }
        self._draw_desktop_preview(force=True)
        self._set_status(f"Moving {OVERLAY_LABELS.get(attr, attr)} — release to save.")

    def _preview_drag(self, event):
        state = self._drag_state
        transform = self._preview_transform
        if not state or not transform:
            return
        row = self._rows.get(state["attr"])
        if row is None:
            return
        left, top, right, bottom, _origin_x, _origin_y, scale = transform
        _old_x, _old_y, width, height, _shown = self._overlay_metrics(row)
        x = state["screen_x"] + (event.x - state["canvas_x"]) / scale
        y = state["screen_y"] + (event.y - state["canvas_y"]) / scale
        x = max(left, min(int(round(x)), right - width))
        y = max(top, min(int(round(y)), bottom - height))
        try:
            self._set_overlay_position(row, x, y)
        except tk.TclError:
            return
        self._preview_fingerprint = None
        self._draw_desktop_preview(force=True)

    def _preview_release(self, _event):
        state = self._drag_state
        self._drag_state = None
        if not state:
            return
        row = self._rows.get(state["attr"])
        if row is None:
            return
        try:
            self.win.update_idletasks()
            self.app._capture_overlay_positions()
            save_config(self.config)
        except Exception:
            pass
        x, y, _width, _height, _shown = self._overlay_metrics(row)
        self.refresh(quiet=True)
        self._set_status(
            f"Saved {OVERLAY_LABELS.get(state['attr'], state['attr'])} at {x:+d}, {y:+d}."
        )

    def _schedule_refresh(self):
        if self._closing or not self.is_open():
            return
        self._refresh_job = self.win.after(450, self._poll_positions)

    def _poll_positions(self):
        self._refresh_job = None
        if self._closing or not self.is_open():
            return
        if self._drag_state is None:
            self.refresh(quiet=True)
        self._schedule_refresh()

    def _set_status(self, message):
        try:
            self.status_var.set(message)
        except (AttributeError, tk.TclError):
            pass

    def refresh(self, quiet=False):
        selected_attr = self.tree.selection()[0] if self.tree.selection() else None
        live_attrs = set()
        for attr, x_key, y_key, window in self._overlay_records():
            row = (attr, x_key, y_key, window)
            x, y, width, height, shown = self._overlay_metrics(row)
            live_attrs.add(attr)
            enabled = self._overlay_enabled(attr)
            state = "OFF" if not enabled else ("SHOWN" if shown else ("READY" if window else "STARTING"))
            values = (
                OVERLAY_LABELS.get(attr, attr.replace("_", " ").title()),
                f"{x:+d}, {y:+d}",
                f"{width} × {height}",
                state,
            )
            if self.tree.exists(attr):
                self.tree.item(attr, values=values)
            else:
                self.tree.insert("", tk.END, iid=attr, values=values)
            self._rows[attr] = row
        for iid in self.tree.get_children():
            if iid not in live_attrs:
                self.tree.delete(iid)
                self._rows.pop(iid, None)
        children = self.tree.get_children()
        if children:
            chosen = selected_attr if selected_attr in live_attrs else children[0]
            if self.tree.selection() != (chosen,):
                self.tree.selection_set(chosen)
        self.count_var.set(f"{len(children)} OVERLAY{'S' if len(children) != 1 else ''}")

        names = sorted((self.config.get("overlay_layout_presets") or {}).keys(), key=str.casefold)
        self.preset_box.configure(values=names)
        if names and self.preset_var.get() not in names:
            self.preset_var.set(names[0])
        elif not names:
            self.preset_var.set("")
        self._refresh_selected_toggle()
        self._draw_desktop_preview()
        if not quiet:
            self._set_status("Overlay positions refreshed from the live desktop.")

    def _selected(self):
        chosen = self.tree.selection()
        return self._rows.get(chosen[0]) if chosen else None

    def _selection_changed(self, _event=None):
        row = self._selected()
        if row:
            self._set_status(f"Selected {OVERLAY_LABELS.get(row[0], row[0])}.")
            self._refresh_selected_toggle()
            self._draw_desktop_preview(force=True)

    def _refresh_selected_toggle(self):
        if not hasattr(self, "selected_toggle_button"):
            return
        attr = self._selected_attr()
        enabled = self._overlay_enabled(attr) if attr else False
        self._refresh_toggle_button(
            self.selected_toggle_button,
            enabled,
            "DISABLE SELECTED",
            "ENABLE SELECTED",
        )

    def toggle_selected_overlay(self):
        attr = self._selected_attr()
        if not attr:
            self._set_status("Select an overlay first.")
            return
        self.toggle_overlay(attr)

    def toggle_overlay(self, attr):
        key = OVERLAY_ENABLE_KEYS.get(attr)
        if not key:
            return
        enabled = not bool(self.config.get(key, False))
        self.config[key] = enabled
        save_config(self.config)
        try:
            self.app._apply_runtime_feature_toggles()
        except Exception as exc:
            self.config[key] = not enabled
            save_config(self.config)
            messagebox.showerror(
                "Overlay Module",
                f"Could not {'enable' if enabled else 'disable'} {OVERLAY_LABELS.get(attr, attr)}:\n{exc}",
                parent=self.win,
            )
            return
        try:
            self.app.add_event_feed_entry(
                "SYSTEM",
                f"{OVERLAY_LABELS.get(attr, attr)} {'enabled' if enabled else 'disabled'} in Layout Studio",
                severity="INFO",
            )
        except Exception:
            pass
        self._set_status(
            f"{OVERLAY_LABELS.get(attr, attr)} {'enabled' if enabled else 'disabled'} for this commander."
        )
        self.win.after(100, lambda: self.refresh(quiet=True))
        self._refresh_overlay_options()

    def _capture(self):
        result = {}
        for attr, x_key, y_key, window in self._overlay_records():
            x, y, _width, _height, _shown = self._overlay_metrics(
                (attr, x_key, y_key, window)
            )
            result[attr] = {"x": x, "y": y, "x_key": x_key, "y_key": y_key}
        return result

    @staticmethod
    def _desktop_bounds(window):
        """Return virtual-desktop bounds, including monitors left of the primary."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            left = int(user32.GetSystemMetrics(76))
            top = int(user32.GetSystemMetrics(77))
            width = int(user32.GetSystemMetrics(78))
            height = int(user32.GetSystemMetrics(79))
            if width > 0 and height > 0:
                return left, top, left + width, top + height
        except (AttributeError, OSError):
            pass
        try:
            left, top = int(window.winfo_vrootx()), int(window.winfo_vrooty())
            width, height = int(window.winfo_vrootwidth()), int(window.winfo_vrootheight())
            if width > 0 and height > 0:
                return left, top, left + width, top + height
        except (AttributeError, tk.TclError):
            pass
        return 0, 0, int(window.winfo_screenwidth()), int(window.winfo_screenheight())

    def snap_selected(self):
        row = self._selected()
        if not row:
            self._set_status("Select an overlay first.")
            return
        attr, _x_key, _y_key, window = row
        x, y, width, height, _shown = self._overlay_metrics(row)
        left, top, right, bottom = self._desktop_bounds(window or self.win)
        candidates_x = [left, max(left, right - width)]
        candidates_y = [top, max(top, bottom - height)]
        for other_attr, _x, _y, other in self._overlay_records():
            if other_attr == attr:
                continue
            ox, oy, ow, oh, _shown = self._overlay_metrics(
                (other_attr, _x, _y, other)
            )
            candidates_x.extend((ox, ox + ow, ox - width, ox + ow - width))
            candidates_y.extend((oy, oy + oh, oy - height, oy + oh - height))
        nearest_x = min(candidates_x, key=lambda value: abs(value - x))
        nearest_y = min(candidates_y, key=lambda value: abs(value - y))
        x = nearest_x if abs(nearest_x - x) <= 20 else x
        y = nearest_y if abs(nearest_y - y) <= 20 else y
        x = max(left, min(x, right - width))
        y = max(top, min(y, bottom - height))
        self._set_overlay_position(row, x, y)
        save_config(self.config)
        self._set_status(f"Snapped {OVERLAY_LABELS.get(attr, attr)} to the nearest edge.")
        self.win.after(60, lambda: self.refresh(quiet=True))

    def reset_selected(self):
        row = self._selected()
        if not row:
            self._set_status("Select an overlay first.")
            return
        attr, _x_key, _y_key, window = row
        x, y = DEFAULT_POSITIONS.get(attr, (30, 30))
        self._set_overlay_position(row, x, y)
        save_config(self.config)
        self._set_status(f"Reset {OVERLAY_LABELS.get(attr, attr)} to its default position.")
        self.win.after(60, lambda: self.refresh(quiet=True))

    def save_preset(self):
        name = simpledialog.askstring("Save Overlay Preset", "Preset name:", parent=self.win)
        if not name or not str(name).strip():
            return
        name = str(name).strip()[:50]
        presets = self.config.setdefault("overlay_layout_presets", {})
        if name in presets and not messagebox.askyesno(
            "Replace Overlay Preset", f"Replace the existing '{name}' preset?", parent=self.win,
        ):
            return
        presets[name] = self._capture()
        save_config(self.config)
        self.preset_var.set(name)
        self.refresh(quiet=True)
        self._set_status(f"Saved '{name}' for this commander profile.")

    def apply_preset(self):
        name = self.preset_var.get()
        preset = (self.config.get("overlay_layout_presets") or {}).get(name) or {}
        if not preset:
            self._set_status("Choose a saved profile preset first.")
            return
        records = {
            attr: (attr, x_key, y_key, window)
            for attr, x_key, y_key, window in self._overlay_records()
        }
        applied = 0
        for attr, pos in preset.items():
            row = records.get(attr)
            if not row or not isinstance(pos, dict):
                continue
            try:
                self._set_overlay_position(row, pos.get("x", 0), pos.get("y", 0))
                applied += 1
            except (TypeError, ValueError, tk.TclError):
                pass
        self.win.update_idletasks()
        self.app._capture_overlay_positions()
        save_config(self.config)
        self._set_status(f"Applied '{name}' to {applied} overlay{'s' if applied != 1 else ''}.")
        self.win.after(60, lambda: self.refresh(quiet=True))

    def delete_preset(self):
        name = self.preset_var.get()
        presets = self.config.get("overlay_layout_presets") or {}
        if not name or name not in presets:
            self._set_status("Choose a saved profile preset first.")
            return
        if not messagebox.askyesno("Delete Overlay Preset", f"Delete '{name}'?", parent=self.win):
            return
        presets.pop(name, None)
        self.preset_var.set("")
        save_config(self.config)
        self.refresh(quiet=True)
        self._set_status(f"Deleted '{name}' from this commander profile.")

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self._refresh_job is not None:
            try:
                self.win.after_cancel(self._refresh_job)
            except tk.TclError:
                pass
            self._refresh_job = None
        if self._preview_resize_job is not None:
            try:
                self.win.after_cancel(self._preview_resize_job)
            except tk.TclError:
                pass
            self._preview_resize_job = None
        try:
            self.config["overlay_layout_studio_geometry"] = self.win.geometry()
            self.win.update_idletasks()
            self.app._capture_overlay_positions()
            save_config(self.config)
        except Exception:
            pass
        try:
            self.win.destroy()
        except tk.TclError:
            pass
