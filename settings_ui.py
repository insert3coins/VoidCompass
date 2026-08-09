import os
import time
import tkinter as tk
import tkinter.messagebox
from tkinter import colorchooser

import themes
from adaptive_command import FOCUSED_MODES as ADAPTIVE_MODES, MODE_LABELS as ADAPTIVE_MODE_LABELS, normalize_mode
from config import DEPRECATED_CONFIG_KEYS, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config as persist_config
from diagnostic_logs import application_base_dir
from global_hotkeys import (
    DEFAULT_OVERLAY_HOTKEYS, OVERLAY_HOTKEY_SPECS,
    validate_hotkey_bindings,
)
from platform_support import default_screenshot_path, open_path
from trade.eddn_upload import UPLOADER as eddn_market_uploader
from ui_theme import (
    THEME, FONT_MONO, FONT_TITLE, FONT_UI, FONT_UI_BOLD,
    apply_window, apply_ui_scale, button, scrollbar as themed_scrollbar, window_surface,
)

COLOR_ACCENT = THEME.accent
COLOR_ORANGE = THEME.orange
COLOR_TEXT = THEME.text


UI_BG = THEME.bg
UI_PANEL = THEME.panel
UI_PANEL_2 = THEME.panel_alt
UI_BORDER = THEME.border
UI_MUTED = THEME.muted
UI_DIM = THEME.dim
UI_INPUT = THEME.input
UI_FONT = FONT_UI
UI_FONT_BOLD = FONT_UI_BOLD
UI_FONT_TITLE = FONT_TITLE
UI_MONO = FONT_MONO


def open_settings(root, config, on_save_callback, carrier_tracker=None, embedded=False,
                  on_close_callback=None,
                  support_bundle_callback=None, rerun_setup_callback=None,
                  health_provider=None, ui_post_callback=None,
                  overlay_layout_callback=None):
    win = window_surface(root, embedded=embedded)
    win.title("SYSTEM CONFIGURATION")
    win.geometry(config.get("settings_geometry", "980x800"))
    win.minsize(880, 600)
    apply_window(win)
    win.attributes("-topmost", True)

    shell = tk.Frame(win, bg=UI_BG)
    shell.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

    header = tk.Frame(shell, bg="#0c1014", height=54)
    header.pack(fill=tk.X)
    header.pack_propagate(False)
    tk.Label(header, text="SYSTEM CONFIGURATION", font=("Segoe UI", 15, "bold"), fg=COLOR_ACCENT, bg="#0c1014").pack(side=tk.LEFT, padx=14)
    tk.Label(header, text="COMMANDER PROFILE", font=("Segoe UI", 8, "bold"), fg=UI_MUTED, bg="#0c1014").pack(side=tk.RIGHT, padx=14)

    main = tk.Frame(shell, bg=UI_BG)
    main.pack(fill=tk.BOTH, expand=True, pady=(10, 10))

    nav = tk.Frame(main, bg="#0c1014", width=190)
    nav.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
    nav.pack_propagate(False)

    content = tk.Frame(main, bg=UI_BG)
    content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    footer = tk.Frame(shell, bg=UI_BG)
    footer.pack(side=tk.BOTTOM, fill=tk.X)

    pages = {}
    nav_buttons = {}
    scroll_canvases = {}
    active_page = {"key": None}

    def action_button(parent, text, command, accent=False, muted=False):
        return button(parent, text, command, accent=accent, muted=muted, padx=12, pady=7)

    def ui_post(callback):
        if callable(ui_post_callback):
            ui_post_callback(callback)
        else:
            win.after(0, callback)

    def make_page(key, title, subtitle, scrollable=False):
        page = tk.Frame(content, bg=UI_BG)
        pages[key] = page
        body = page
        if scrollable:
            canvas = tk.Canvas(
                page, bg=UI_BG, bd=0, highlightthickness=0,
                takefocus=True,
            )
            page_scrollbar = themed_scrollbar(
                page, orient=tk.VERTICAL, command=canvas.yview,
            )
            canvas.configure(yscrollcommand=page_scrollbar.set)
            page_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            body = tk.Frame(canvas, bg=UI_BG)
            window_id = canvas.create_window((0, 0), window=body, anchor="nw")

            def fit_content(_event=None, c=canvas, inner=body):
                c.configure(scrollregion=c.bbox("all"))

            def fit_width(event, c=canvas, item=window_id):
                c.itemconfigure(item, width=max(1, event.width))

            body.bind("<Configure>", fit_content)
            canvas.bind("<Configure>", fit_width)
            scroll_canvases[key] = canvas
        tk.Label(body, text=title, font=UI_FONT_TITLE, fg=COLOR_ACCENT, bg=UI_BG, anchor="w").pack(fill=tk.X)
        tk.Label(body, text=subtitle, font=("Segoe UI", 8), fg=UI_MUTED, bg=UI_BG, anchor="w").pack(fill=tk.X, pady=(2, 10))
        return body

    def show_page(key):
        for page in pages.values():
            page.pack_forget()
        pages[key].pack(fill=tk.BOTH, expand=True)
        active_page["key"] = key
        for name, btn in nav_buttons.items():
            selected = name == key
            btn.config(
                bg=UI_PANEL_2 if selected else "#0c1014",
                fg=COLOR_ACCENT if selected else UI_MUTED,
                activebackground=UI_PANEL_2,
                activeforeground=COLOR_ACCENT,
            )

    def scroll_active_page(event):
        canvas = scroll_canvases.get(active_page.get("key"))
        if canvas is None or not event.delta:
            return None
        steps = max(1, abs(int(event.delta)) // 120)
        canvas.yview_scroll(-steps if event.delta > 0 else steps, "units")
        return "break"

    def bind_scroll_tree(widget):
        widget.bind("<MouseWheel>", scroll_active_page, add="+")
        for child in widget.winfo_children():
            bind_scroll_tree(child)

    win.bind("<MouseWheel>", scroll_active_page, add="+")

    def nav_button(key, text):
        btn = tk.Button(
            nav,
            text=text,
            command=lambda: show_page(key),
            bg="#0c1014",
            fg=UI_MUTED,
            activebackground=UI_PANEL_2,
            activeforeground=COLOR_ACCENT,
            font=UI_FONT_BOLD,
            relief=tk.FLAT,
            bd=0,
            anchor="w",
            padx=14,
            pady=10,
            cursor="hand2",
        )
        btn.pack(fill=tk.X, padx=8, pady=(8 if not nav_buttons else 0, 4))
        nav_buttons[key] = btn

    def section(parent, title):
        frame = tk.Frame(parent, bg=UI_PANEL, highlightbackground=UI_BORDER, highlightthickness=1, bd=0)
        frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(frame, text=title, font=UI_FONT_BOLD, fg=COLOR_ORANGE, bg=UI_PANEL, anchor="w").pack(fill=tk.X, padx=12, pady=(10, 4))
        return frame

    def row(parent):
        frame = tk.Frame(parent, bg=UI_PANEL)
        frame.pack(fill=tk.X, padx=12, pady=(5, 6))
        return frame

    def _parse_float(text, fallback):
        try:
            return max(0.5, float(str(text).strip()))
        except Exception:
            return fallback

    def input_row(parent, label, key, is_password=False):
        frame = row(parent)
        tk.Label(frame, text=label, font=UI_FONT_BOLD, fg=UI_MUTED, bg=UI_PANEL, anchor="w", width=24).pack(side=tk.LEFT)
        entry = tk.Entry(
            frame,
            bg=UI_INPUT,
            fg=COLOR_TEXT,
            font=UI_MONO,
            insertbackground=COLOR_ACCENT,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=UI_BORDER,
            highlightcolor=COLOR_ACCENT,
        )
        if is_password:
            entry.config(show="*")
        entry.insert(0, str(config.get(key, "")))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        return entry

    def toggle_row(parent, label, variable):
        frame = row(parent)
        tk.Label(frame, text=label, font=UI_FONT, fg=COLOR_TEXT, bg=UI_PANEL, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
        btn = tk.Button(frame, font=("Segoe UI", 8, "bold"), relief=tk.FLAT, bd=0, width=9, cursor="hand2")

        def refresh():
            if variable.get():
                btn.config(text="On", bg=COLOR_ACCENT, fg="black", activebackground=COLOR_ACCENT, activeforeground="black")
            else:
                btn.config(text="Off", bg=UI_PANEL_2, fg=UI_MUTED, activebackground=UI_PANEL_2, activeforeground=COLOR_TEXT)

        def toggle():
            variable.set(not variable.get())
            refresh()

        btn.config(command=toggle)
        btn.pack(side=tk.RIGHT)
        refresh()
        return btn

    def option_row(parent, label, variable, values):
        frame = row(parent)
        tk.Label(frame, text=label, font=UI_FONT_BOLD, fg=UI_MUTED, bg=UI_PANEL, anchor="w", width=24).pack(side=tk.LEFT)
        menu = tk.OptionMenu(frame, variable, *values)
        menu.config(
            bg=UI_PANEL_2,
            fg=COLOR_TEXT,
            activebackground=UI_PANEL_2,
            activeforeground=COLOR_ACCENT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=UI_FONT,
            width=14,
        )
        menu["menu"].config(bg=UI_PANEL_2, fg=COLOR_TEXT)
        menu.pack(side=tk.LEFT)
        return menu

    # Variables
    overlay_hotkeys_var = tk.BooleanVar(value=config.get("overlay_hotkeys_enabled", True))
    reduced_motion_var = tk.BooleanVar(value=config.get("reduced_motion_enabled", False))
    ui_scale_var = tk.StringVar(value=str(config.get("ui_scale_percent", 100)))
    ss_var = tk.BooleanVar(value=config.get("screenshots_enabled", False))
    edsm_upload_var = tk.BooleanVar(value=config.get("edsm_upload_enabled", False))
    eddn_market_upload_var = tk.BooleanVar(
        value=config.get("eddn_market_upload_enabled", True)
    )
    runtime_trace_var = tk.BooleanVar(value=config.get("runtime_trace_enabled", True))
    crash_reporting_var = tk.BooleanVar(value=config.get("crash_reporting_enabled", True))
    recovery_safe_mode_var = tk.BooleanVar(value=config.get("recovery_safe_mode_enabled", True))
    adaptive_enabled_var = tk.BooleanVar(value=config.get("adaptive_command_enabled", True))
    adaptive_mode_labels = {"Automatic": "auto"}
    adaptive_mode_labels.update({ADAPTIVE_MODE_LABELS[key].title(): key for key in ADAPTIVE_MODES})
    adaptive_mode_key = normalize_mode(config.get("adaptive_mode_lock", "auto"), "auto")
    adaptive_mode_var = tk.StringVar(
        value=next(
            (label for label, key in adaptive_mode_labels.items() if key == adaptive_mode_key),
            "Automatic",
        )
    )
    if "screenshots_path" not in config:
        config["screenshots_path"] = default_screenshot_path(config.get("journal_path"))

    # Pages
    core_page = make_page("core", "Core", "Journal and screenshot paths.", scrollable=True)
    hotkey_page = make_page(
        "hotkeys", "Hotkeys",
        "Profile-aware global shortcuts for overlays, layout and field actions.",
        scrollable=True,
    )
    command_page = make_page(
        "command", "Adaptive Command Deck",
        "Activity-aware workspace, operational queue and overlay scenes.",
        scrollable=True,
    )
    theme_page = make_page("theme", "Theme", "Color theme for this commander profile. Applies when you save.", scrollable=True)
    integrations_page = make_page(
        "integrations", "Integrations",
        "Optional EDSM, EDDN and fleet carrier services.",
        scrollable=True,
    )
    diagnostics_page = make_page("diagnostics", "Diagnostics", "Runtime tracing and automatic crash or UI-freeze reports.", scrollable=True)

    nav_button("core", "Core")
    nav_button("hotkeys", "Hotkeys")
    nav_button("command", "Command Deck")
    nav_button("theme", "Theme")
    nav_button("integrations", "Integrations")
    nav_button("diagnostics", "Diagnostics")

    core_paths = section(core_page, "Paths")
    j_e = input_row(core_paths, "Journal Path", "journal_path")
    ss_e = input_row(core_paths, "Screenshot Folder", "screenshots_path")

    core_shots = section(core_page, "Screenshots")
    toggle_row(core_shots, "Convert BMP screenshots to PNG", ss_var)

    core_accessibility = section(core_page, "Accessibility")
    option_row(core_accessibility, "Application scale", ui_scale_var, ("90", "100", "110", "125", "140"))
    toggle_row(core_accessibility, "Reduced motion and gentler activity pulses", reduced_motion_var)

    if callable(overlay_layout_callback):
        overlay_studio = section(core_page, "Overlay Layout Studio")
        layout_actions = row(overlay_studio)
        action_button(
            layout_actions, "Open Overlay Layout Studio", overlay_layout_callback, accent=True,
        ).pack(side=tk.LEFT)
        tk.Label(
            layout_actions,
            text="Enable, position and configure every overlay from one themed workspace.",
            font=UI_FONT, fg=UI_MUTED, bg=UI_PANEL, anchor="w",
        ).pack(side=tk.LEFT, padx=10)

    overlay_hotkeys = section(hotkey_page, "Global Hotkeys")
    toggle_row(
        overlay_hotkeys,
        "Enable system-wide overlay hotkeys"
        if os.name == "nt" else
        "System-wide overlay hotkeys (Windows only)",
        overlay_hotkeys_var,
    )
    hotkey_entries = {}
    for action, key, label, _overlay_attr in OVERLAY_HOTKEY_SPECS:
        hotkey_entries[action] = input_row(overlay_hotkeys, label, key)

    hotkey_actions = row(overlay_hotkeys)

    def _reset_overlay_hotkeys():
        for _action, key, _label, _overlay_attr in OVERLAY_HOTKEY_SPECS:
            entry = hotkey_entries[_action]
            entry.delete(0, tk.END)
            default = DEFAULT_OVERLAY_HOTKEYS.get(key, "")
            if default:
                entry.insert(0, default)

    action_button(hotkey_actions, "Restore Defaults", _reset_overlay_hotkeys, muted=True).pack(side=tk.RIGHT)
    tk.Label(
        overlay_hotkeys,
        text=(
            "Shortcuts are system-wide and work while Elite Dangerous has focus. "
            "Use Ctrl, Alt, Shift or Win plus a letter, number, F-key or navigation key. "
            "Clear a field to leave that action unbound."
        ),
        font=UI_FONT,
        fg=UI_MUTED,
        bg=UI_PANEL,
        anchor="w",
        justify=tk.LEFT,
        wraplength=620,
    ).pack(fill=tk.X, padx=12, pady=(0, 12))

    # ---- Adaptive Command Deck ----
    command_control = section(command_page, "Activity Control")
    tk.Label(
        command_control,
        text=(
            "VoidCompass follows exploration, mining, surface survey, Carrier expeditions and "
            "station/data-sale activity from verified journal state. A manual lock stays with this commander profile; "
            "enabled overlays remain independent of the selected activity."
        ),
        font=UI_FONT, fg=UI_MUTED, bg=UI_PANEL, anchor="w", justify=tk.LEFT,
        wraplength=650,
    ).pack(fill=tk.X, padx=12, pady=(2, 8))
    toggle_row(command_control, "Enable adaptive activity detection", adaptive_enabled_var)
    mode_menu = option_row(
        command_control, "Activity mode", adaptive_mode_var,
        list(adaptive_mode_labels.keys()),
    )
    mode_menu.configure(width=20)

    command_behavior = section(command_page, "Adaptive Behaviour")
    tk.Label(
        command_behavior,
        text=(
            "Activity modes prioritise the dashboard without hiding any overlay enabled in "
            "Overlay Layout Studio."
        ),
        font=UI_FONT, fg=UI_MUTED, bg=UI_PANEL, anchor="w", justify=tk.LEFT,
        wraplength=650,
    ).pack(fill=tk.X, padx=12, pady=(2, 10))

    command_health = section(command_page, "Command Health")
    command_health_var = tk.StringVar(value="Health telemetry is unavailable in this session.")

    def _refresh_command_health():
        if not callable(health_provider):
            return
        try:
            health = health_provider() or {}
            ui = health.get("ui") or {}
            persistence = health.get("persistence") or {}
            stall = float(health.get("last_ui_stall_age_s") or 0)
            stall_text = f" · last UI stall {stall:.0f}s ago" if stall > 0 else ""
            command_health_var.set(
                f"{health.get('level') or 'NOMINAL'} · UI queue "
                f"{int(ui.get('pending') or health.get('ui_pending') or 0)} · max lag "
                f"{float(ui.get('max_lag_ms') or health.get('ui_max_lag_ms') or 0):.0f} ms · disk queue "
                f"{int(persistence.get('pending') or health.get('writes_pending') or 0)} · writes "
                f"{int(persistence.get('writes') or 0)} · retries "
                f"{int(persistence.get('retries') or 0)}{stall_text}"
            )
        except Exception as exc:
            command_health_var.set(f"Health telemetry unavailable: {exc}")

    tk.Label(
        command_health, textvariable=command_health_var, font=UI_MONO,
        fg=COLOR_TEXT, bg=UI_PANEL, anchor="w", justify=tk.LEFT,
    ).pack(fill=tk.X, padx=12, pady=(4, 8))
    command_health_actions = row(command_health)
    action_button(command_health_actions, "Refresh Health", _refresh_command_health, muted=True).pack(side=tk.LEFT)
    _refresh_command_health()

    # ---- Theme page ----
    custom_themes = {
        str(name): themes.normalize_theme(palette)
        for name, palette in (config.get("ui_custom_themes") or {}).items()
        if isinstance(palette, dict)
    }
    saved_theme_name = str(config.get("ui_theme_name") or themes.DEFAULT_THEME_NAME)

    def _all_theme_names():
        return list(themes.BUILTIN_THEMES.keys()) + sorted(custom_themes.keys())

    def _theme_palette(name):
        if name in custom_themes:
            return dict(custom_themes[name])
        return dict(themes.BUILTIN_THEMES.get(name) or themes.BUILTIN_THEMES[themes.DEFAULT_THEME_NAME])

    theme_var = tk.StringVar(value=saved_theme_name if saved_theme_name in _all_theme_names() else themes.DEFAULT_THEME_NAME)
    editor_vars = {}     # color key -> tk.StringVar (hex)
    editor_swatches = {} # color key -> swatch Label

    pick_section = section(theme_page, "Active Theme")
    pick_row = row(pick_section)
    tk.Label(pick_row, text="Theme", font=UI_FONT_BOLD, fg=UI_MUTED, bg=UI_PANEL, anchor="w", width=24).pack(side=tk.LEFT)
    theme_menu = tk.OptionMenu(pick_row, theme_var, *_all_theme_names())
    theme_menu.config(
        bg=UI_PANEL_2, fg=COLOR_TEXT, activebackground=UI_PANEL_2, activeforeground=COLOR_ACCENT,
        relief=tk.FLAT, bd=0, highlightthickness=0, font=UI_FONT, width=18,
    )
    theme_menu["menu"].config(bg=UI_PANEL_2, fg=COLOR_TEXT)
    theme_menu.pack(side=tk.LEFT)
    preview_row = tk.Frame(pick_section, bg=UI_PANEL)
    preview_row.pack(fill=tk.X, padx=12, pady=(2, 10))

    def _rebuild_theme_menu():
        menu = theme_menu["menu"]
        menu.delete(0, tk.END)
        for name in _all_theme_names():
            menu.add_command(label=name, command=lambda n=name: (theme_var.set(n), _on_theme_selected()))

    def _refresh_preview(palette):
        for child in preview_row.winfo_children():
            child.destroy()
        for key in ("bg", "panel", "border", "accent", "orange", "text", "muted", "green", "yellow", "red"):
            cell = tk.Frame(preview_row, bg=UI_PANEL)
            cell.pack(side=tk.LEFT, padx=(0, 6))
            tk.Frame(cell, bg=palette[key], width=34, height=20,
                     highlightbackground=UI_BORDER, highlightthickness=1).pack()
            tk.Label(cell, text=key, font=("Segoe UI", 7), fg=UI_DIM, bg=UI_PANEL).pack()

    def _load_editor(palette):
        for key in themes.THEME_KEYS:
            editor_vars[key].set(palette[key])
            editor_swatches[key].config(bg=palette[key])

    def _on_theme_selected(*_args):
        palette = _theme_palette(theme_var.get())
        _refresh_preview(palette)
        _load_editor(palette)
        _refresh_delete_state()

    editor_section = section(theme_page, "Theme Editor")
    grid = tk.Frame(editor_section, bg=UI_PANEL)
    grid.pack(fill=tk.X, padx=12, pady=(2, 8))

    def _editor_palette():
        return themes.normalize_theme(
            {key: var.get().strip() for key, var in editor_vars.items()},
            base=_theme_palette(theme_var.get()),
        )

    def _make_color_row(parent, key, col_row, col):
        holder = tk.Frame(parent, bg=UI_PANEL)
        holder.grid(row=col_row, column=col, sticky="w", padx=(0, 24), pady=2)
        tk.Label(holder, text=key, font=UI_FONT, fg=UI_MUTED, bg=UI_PANEL, width=12, anchor="w").pack(side=tk.LEFT)
        var = tk.StringVar()
        editor_vars[key] = var
        ent = tk.Entry(holder, textvariable=var, width=9, bg=UI_INPUT, fg=COLOR_TEXT, font=UI_MONO,
                       insertbackground=COLOR_ACCENT, relief=tk.FLAT,
                       highlightthickness=1, highlightbackground=UI_BORDER, highlightcolor=COLOR_ACCENT)
        ent.pack(side=tk.LEFT, ipady=2)
        swatch = tk.Label(holder, width=3, bg=UI_PANEL_2, relief=tk.FLAT, cursor="hand2")
        swatch.pack(side=tk.LEFT, padx=(6, 0), ipady=2)
        editor_swatches[key] = swatch

        def _pick(_event=None):
            initial = var.get() if themes.is_hex_color(var.get()) else "#808080"
            _rgb, hex_value = colorchooser.askcolor(color=initial, parent=win, title=f"Pick {key}")
            if hex_value:
                var.set(hex_value)
                swatch.config(bg=hex_value)
                _refresh_preview(_editor_palette())

        def _typed(_event=None):
            if themes.is_hex_color(var.get().strip()):
                swatch.config(bg=var.get().strip())
                _refresh_preview(_editor_palette())

        swatch.bind("<Button-1>", _pick)
        ent.bind("<KeyRelease>", _typed)

    half = (len(themes.THEME_KEYS) + 1) // 2
    for i, key in enumerate(themes.THEME_KEYS):
        _make_color_row(grid, key, i % half, i // half)

    actions = row(editor_section)
    name_entry = tk.Entry(actions, width=22, bg=UI_INPUT, fg=COLOR_TEXT, font=UI_MONO,
                          insertbackground=COLOR_ACCENT, relief=tk.FLAT,
                          highlightthickness=1, highlightbackground=UI_BORDER, highlightcolor=COLOR_ACCENT)
    name_entry.insert(0, "My Theme")

    def _save_custom():
        name = name_entry.get().strip()
        if not name:
            tk.messagebox.showwarning("Theme name", "Give the custom theme a name first.", parent=win)
            return
        if name in themes.BUILTIN_THEMES:
            tk.messagebox.showwarning("Theme name", f"'{name}' is a built-in theme - pick another name.", parent=win)
            return
        custom_themes[name] = _editor_palette()
        _rebuild_theme_menu()
        theme_var.set(name)
        _on_theme_selected()

    def _delete_custom():
        name = theme_var.get()
        if name not in custom_themes:
            return
        if not tk.messagebox.askyesno("Delete theme", f"Delete custom theme '{name}'?", parent=win):
            return
        custom_themes.pop(name, None)
        _rebuild_theme_menu()
        theme_var.set(themes.DEFAULT_THEME_NAME)
        _on_theme_selected()

    action_button(actions, "Save as Custom Theme", _save_custom).pack(side=tk.LEFT)
    name_entry.pack(side=tk.LEFT, padx=(8, 0), ipady=3)
    delete_btn = action_button(actions, "Delete Custom Theme", _delete_custom, muted=True)
    delete_btn.pack(side=tk.RIGHT)

    def _refresh_delete_state():
        deletable = theme_var.get() in custom_themes
        delete_btn.configure(state=tk.NORMAL if deletable else tk.DISABLED)

    tk.Label(
        theme_page,
        text="The selected theme is saved per commander profile and applies to the app and overlays when you hit Save Settings.",
        font=UI_FONT, fg=UI_MUTED, bg=UI_BG, anchor="w", justify=tk.LEFT, wraplength=640,
    ).pack(fill=tk.X, pady=(2, 0))

    _rebuild_theme_menu()
    _on_theme_selected()

    edsm_section = section(integrations_page, "EDSM Upload")
    edsm_cmdr_e = input_row(edsm_section, "Commander Name", "edsm_cmdr_name")
    edsm_key_e = input_row(edsm_section, "API Key", "edsm_api_key", is_password=True)
    toggle_row(edsm_section, "Upload scan data to EDSM", edsm_upload_var)

    def _test_edsm():
        import threading, requests as _req
        cmdr = edsm_cmdr_e.get().strip()
        key = edsm_key_e.get().strip()
        if not cmdr or not key:
            tk.messagebox.showwarning("Missing credentials", "Enter Commander Name and API Key first.", parent=win)
            return

        def _do_test():
            try:
                from version import APP_VERSION
                r = _req.get(
                    "https://www.edsm.net/api-commander-v1/get-ranks",
                    params={"commanderName": cmdr, "apiKey": key},
                    headers={"Accept": "application/json", "User-Agent": f"VoidCompass/{APP_VERSION}"},
                    timeout=10,
                )
                content_type = r.headers.get("content-type", "")
                if not content_type.startswith("application/json"):
                    text = r.text or ""
                    if "cloudflare" in text.lower() or "attention required" in text.lower():
                        msg = "EDSM/Cloudflare blocked the credential test request. Try again later, or verify the key on EDSM.net."
                    else:
                        msg = f"EDSM returned an unexpected non-JSON response (HTTP {r.status_code})."
                    ui_post(lambda message=msg: tk.messagebox.showwarning("EDSM Test", message, parent=win))
                    return

                body = r.json()
                msgnum = body.get("msgnum")
                msg = body.get("msg", "Unknown EDSM response")
                if msgnum == 100:
                    ui_post(lambda: tk.messagebox.showinfo("EDSM Test", "API key verified successfully.", parent=win))
                elif msgnum == 207:
                    ui_post(lambda: tk.messagebox.showinfo("EDSM Test", "Commander/API key accepted, but EDSM has no rank data stored yet.", parent=win))
                else:
                    ui_post(lambda number=msgnum, message=msg: tk.messagebox.showwarning("EDSM Test", f"EDSM response [{number}]: {message}", parent=win))
            except Exception as e:
                ui_post(lambda error=str(e): tk.messagebox.showerror("EDSM Test", f"Request failed: {error}", parent=win))

        threading.Thread(target=_do_test, daemon=True).start()

    edsm_actions = row(edsm_section)
    action_button(edsm_actions, "Test API Key", _test_edsm).pack(side=tk.LEFT)

    eddn_section = section(integrations_page, "EDDN Community Market Uploads")
    toggle_row(
        eddn_section,
        "Upload fresh markets visited in game",
        eddn_market_upload_var,
    )
    tk.Label(
        eddn_section,
        text=(
            "When enabled, VoidCompass publishes fresh Market.json commodity snapshots "
            "from stations you visit. EDDN receives the commander name as uploader ID, "
            "game version, system, station and commodity market data. VoidCompass does "
            "not download an EDDN feed or maintain a local trade database."
        ),
        font=UI_FONT, fg=UI_MUTED, bg=UI_PANEL, anchor="w", justify=tk.LEFT,
        wraplength=620,
    ).pack(fill=tk.X, padx=12, pady=(0, 6))
    eddn_status_var = tk.StringVar(value="")
    tk.Label(
        eddn_section, textvariable=eddn_status_var,
        font=UI_MONO, fg=COLOR_TEXT, bg=UI_PANEL, anchor="w", justify=tk.LEFT,
        wraplength=620,
    ).pack(fill=tk.X, padx=12, pady=(0, 6))

    def _refresh_eddn_status():
        stats = eddn_market_uploader.stats()
        enabled = eddn_market_upload_var.get()
        parts = [
            "ENABLED" if enabled else "DISABLED",
            f"{int(stats.get('uploads') or 0):,} upload(s) this run",
        ]
        if stats.get("last_upload_at"):
            parts.append(f"last {stats['last_upload_at']}")
        if stats.get("last_error"):
            parts.append(f"last error: {stats['last_error']}")
        eddn_status_var.set("  ·  ".join(parts))

    eddn_actions = row(eddn_section)
    action_button(eddn_actions, "Refresh Status", _refresh_eddn_status).pack(side=tk.LEFT)
    _refresh_eddn_status()

    carrier_section = section(integrations_page, "Carrier Discord (Personal / Squadron)")
    fc_wh_e = input_row(carrier_section, "Discord Webhook URL", "carrier_discord_webhook_url")
    tk.Label(
        carrier_section,
        text="One webhook handles personal and Squadron Carrier jump, cooldown, cancellation and manual status posts. Themed embeds include journal-backed fuel, capacity, access, services and expedition progress; plotted targets stay plain text until arrival.",
        font=UI_FONT, fg=UI_MUTED, bg=UI_PANEL, anchor="w", justify=tk.LEFT,
        wraplength=620,
    ).pack(fill=tk.X, padx=12, pady=(0, 6))

    def _test_discord():
        url = fc_wh_e.get().strip()
        if not url:
            tk.messagebox.showwarning("No URL", "Enter a webhook URL first.", parent=win)
            return
        if carrier_tracker is not None:
            import threading

            def _send_test():
                ok, error = carrier_tracker.send_test_discord(url)
                if ok:
                    ui_post(lambda: tk.messagebox.showinfo(
                        "Test Sent",
                        "The themed carrier preview was accepted by Discord.",
                        parent=win,
                    ))
                else:
                    ui_post(lambda detail=error or "Unknown error": tk.messagebox.showerror(
                        "Discord Test Failed",
                        f"The webhook did not accept the preview:\n{detail}",
                        parent=win,
                    ))

            threading.Thread(target=_send_test, daemon=True).start()
        else:
            tk.messagebox.showinfo("Not Available", "Carrier tracker not connected; save and reopen settings.", parent=win)

    carrier_actions = row(carrier_section)
    action_button(carrier_actions, "Send Test Message", _test_discord).pack(side=tk.LEFT)

    diagnostics_section = section(diagnostics_page, "Runtime Diagnostics")
    toggle_row(diagnostics_section, "Runtime performance trace log", runtime_trace_var)
    toggle_row(diagnostics_section, "Crash and UI-freeze reporter", crash_reporting_var)
    toggle_row(diagnostics_section, "Recover safely after an unclean shutdown", recovery_safe_mode_var)

    def _open_logs_folder():
        path = application_base_dir() / "logs"
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            tk.messagebox.showerror(
                "Logs Folder", f"Could not open {path}:\n{exc}", parent=win,
            )
            return
        if not open_path(path):
            tk.messagebox.showerror(
                "Logs Folder", f"Could not open {path}.", parent=win,
            )

    diagnostics_actions = row(diagnostics_section)
    action_button(diagnostics_actions, "Open Logs Folder", _open_logs_folder).pack(side=tk.LEFT)
    if callable(support_bundle_callback):
        action_button(
            diagnostics_actions, "Create Support Bundle", support_bundle_callback, accent=True,
        ).pack(side=tk.LEFT, padx=(8, 0))
    if callable(rerun_setup_callback):
        action_button(
            diagnostics_actions, "Run Setup", rerun_setup_callback, muted=True,
        ).pack(side=tk.RIGHT)
    tk.Label(
        diagnostics_section,
        text=(
            "Current and timestamped previous-run logs are kept in the logs folder. "
            "Changes take effect after restarting VoidCompass. Ctrl+Alt+D writes a manual "
            "stack dump when crash reporting is enabled."
        ),
        font=UI_FONT,
        fg=UI_MUTED,
        bg=UI_PANEL,
        anchor="w",
        justify=tk.LEFT,
        wraplength=620,
    ).pack(fill=tk.X, padx=12, pady=(2, 12))

    def remove_deprecated_keys():
        for key in DEPRECATED_CONFIG_KEYS:
            config.pop(key, None)

    def save_config():
        raw_hotkeys = {
            action: hotkey_entries[action].get().strip()
            for action, _key, _label, _overlay_attr in OVERLAY_HOTKEY_SPECS
        }
        normalized_hotkeys, hotkey_errors = validate_hotkey_bindings(raw_hotkeys)
        if hotkey_errors:
            labels = {action: label for action, _key, label, _attr in OVERLAY_HOTKEY_SPECS}
            details = "\n".join(
                f"{labels.get(action, action)}: {error}"
                for action, error in hotkey_errors.items()
            )
            tkinter.messagebox.showerror(
                "Invalid Overlay Hotkey",
                f"Correct the following shortcut settings:\n\n{details}",
                parent=win,
            )
            return
        config.update({
            "journal_path": j_e.get().strip(),
            "overlay_hotkeys_enabled": overlay_hotkeys_var.get(),
            "reduced_motion_enabled": reduced_motion_var.get(),
            "ui_scale_percent": int(ui_scale_var.get()),
            "ui_theme_name": theme_var.get(),
            "ui_custom_themes": dict(custom_themes),
            "screenshots_enabled": ss_var.get(),
            "screenshots_path": ss_e.get().strip(),
            "carrier_discord_webhook_url": fc_wh_e.get().strip(),
            "edsm_cmdr_name": edsm_cmdr_e.get().strip(),
            "edsm_api_key": edsm_key_e.get().strip(),
            "edsm_upload_enabled": edsm_upload_var.get(),
            "eddn_market_upload_enabled": eddn_market_upload_var.get(),
            "runtime_trace_enabled": runtime_trace_var.get(),
            "crash_reporting_enabled": crash_reporting_var.get(),
            "recovery_safe_mode_enabled": recovery_safe_mode_var.get(),
            "adaptive_command_enabled": adaptive_enabled_var.get(),
            "adaptive_mode_lock": adaptive_mode_labels.get(adaptive_mode_var.get(), "auto"),
            "settings_geometry": win.geometry(),
        })
        for action, key, _label, _overlay_attr in OVERLAY_HOTKEY_SPECS:
            config[key] = normalized_hotkeys.get(action, "")
        remove_deprecated_keys()
        persist_config(config)
        eddn_market_uploader.set_enabled(eddn_market_upload_var.get())
        apply_ui_scale(root, config.get("ui_scale_percent", 100))
        saved_name = theme_var.get()
        saved_palette = _theme_palette(saved_name)
        if saved_name != themes.ACTIVE_THEME_NAME or saved_palette != themes.ACTIVE_PALETTE:
            from ui_theme import apply_theme_live
            try:
                # Settings is embedded inside the dashboard.  Walking only
                # this frame updates the global palette before the dashboard
                # and its Toplevel overlays have been recoloured, leaving the
                # later whole-app pass with no old/new mapping to apply.
                live_root = root.winfo_toplevel()
                apply_theme_live(live_root, saved_name, saved_palette)
            except Exception:
                pass
        on_save_callback()
        if embedded:
            win.pack_forget()
        else:
            win.destroy()

    def close_window():
        config["settings_geometry"] = win.geometry()
        remove_deprecated_keys()
        persist_config(config)
        if embedded:
            win.pack_forget()
            if callable(on_close_callback):
                on_close_callback()
        else:
            win.destroy()

    action_button(footer, "Cancel", close_window, muted=True).pack(side=tk.LEFT)
    action_button(footer, "Save Settings", save_config, accent=True).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

    win.protocol("WM_DELETE_WINDOW", close_window)
    for scroll_page in (
        core_page, hotkey_page,
        command_page, theme_page, integrations_page, diagnostics_page,
    ):
        bind_scroll_tree(scroll_page)
    show_page("core")
    return win
