import os
import tkinter as tk
import tkinter.messagebox
from tkinter import colorchooser

import themes
import voice_callouts
from config import DEPRECATED_CONFIG_KEYS, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config as persist_config
from ui_theme import THEME, FONT_MONO, FONT_TITLE, FONT_UI, FONT_UI_BOLD, apply_window, button, window_surface

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
                  on_close_callback=None, voice_manager=None):
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

    def action_button(parent, text, command, accent=False, muted=False):
        return button(parent, text, command, accent=accent, muted=muted, padx=12, pady=7)

    def make_page(key, title, subtitle):
        page = tk.Frame(content, bg=UI_BG)
        tk.Label(page, text=title, font=UI_FONT_TITLE, fg=COLOR_ACCENT, bg=UI_BG, anchor="w").pack(fill=tk.X)
        tk.Label(page, text=subtitle, font=("Segoe UI", 8), fg=UI_MUTED, bg=UI_BG, anchor="w").pack(fill=tk.X, pady=(2, 10))
        pages[key] = page
        return page

    def show_page(key):
        for page in pages.values():
            page.pack_forget()
        pages[key].pack(fill=tk.BOTH, expand=True)
        for name, btn in nav_buttons.items():
            selected = name == key
            btn.config(
                bg=UI_PANEL_2 if selected else "#0c1014",
                fg=COLOR_ACCENT if selected else UI_MUTED,
                activebackground=UI_PANEL_2,
                activeforeground=COLOR_ACCENT,
            )

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
    ov_var = tk.BooleanVar(value=config.get("overlay_enabled", True))
    hud_compact_var = tk.BooleanVar(value=config.get("hud_compact_mode", False))
    cargo_var = tk.BooleanVar(value=config.get("cargo_overlay_enabled", False))
    carrier_overlay_var = tk.BooleanVar(value=config.get("carrier_overlay_enabled", False))
    colony_var = tk.BooleanVar(value=config.get("colony_overlay_enabled", False))
    prosp_var = tk.BooleanVar(value=config.get("prospector_overlay_enabled", True))
    sysinfo_var = tk.BooleanVar(value=config.get("system_info_enabled", True))
    gravity_var = tk.BooleanVar(value=config.get("gravity_warning_overlay_enabled", True))
    station_info_var = tk.BooleanVar(value=config.get("station_info_overlay_enabled", True))
    survey_status_var = tk.BooleanVar(value=config.get("survey_status_overlay_enabled", True))
    toast_var = tk.BooleanVar(value=config.get("toast_overlay_enabled", True))
    hud_crt_var = tk.BooleanVar(value=config.get("hud_crt_enabled", True))
    hud_crt_motion_var = tk.BooleanVar(value=config.get("hud_crt_motion_enabled", True))
    hud_crt_intensity_var = tk.StringVar(value=str(config.get("hud_crt_intensity", "Subtle") or "Subtle"))
    sample_clear_var = tk.BooleanVar(value=config.get("sample_clear_notifications_enabled", True))
    rebuy_warning_var = tk.BooleanVar(value=config.get("rebuy_warnings_enabled", True))
    data_risk_var = tk.BooleanVar(value=config.get("data_risk_warnings_enabled", True))
    heartbeat_var = tk.BooleanVar(value=config.get("heartbeat_overlay_enabled", True))
    ss_var = tk.BooleanVar(value=config.get("screenshots_enabled", False))
    edsm_upload_var = tk.BooleanVar(value=config.get("edsm_upload_enabled", False))
    runtime_trace_var = tk.BooleanVar(value=config.get("runtime_trace_enabled", True))
    crash_reporting_var = tk.BooleanVar(value=config.get("crash_reporting_enabled", True))
    voice_enabled_var = tk.BooleanVar(value=config.get("voice_callouts_enabled", False))
    voice_safety_var = tk.BooleanVar(value=config.get("voice_safety_enabled", True))
    voice_exploration_var = tk.BooleanVar(value=config.get("voice_exploration_enabled", True))
    voice_navigation_var = tk.BooleanVar(value=config.get("voice_navigation_enabled", True))
    voice_objectives_var = tk.BooleanVar(value=config.get("voice_objectives_enabled", True))
    voice_cache_var = tk.BooleanVar(value=config.get("voice_cache_enabled", True))
    voice_volume_var = tk.DoubleVar(value=float(config.get("voice_volume", 0.8) or 0.8))
    if "screenshots_path" not in config:
        config["screenshots_path"] = os.path.join(os.path.expanduser("~"), "Pictures", "Frontier Developments", "Elite Dangerous")

    # Pages
    core_page = make_page("core", "Core", "Journal and screenshot paths.")
    overlay_page = make_page("overlays", "Overlays", "Runtime modules and display timing.")
    crt_page = make_page("crt", "HUD Effects", "CRT styling for the native Navigation HUD.")
    voice_page = make_page("voice", "Voice", "Optional local neural callouts. Voice audio never leaves this computer.")
    theme_page = make_page("theme", "Theme", "Color theme for this commander profile. Applies when you save.")
    integrations_page = make_page("integrations", "Integrations", "EDSM upload and fleet carrier Discord.")
    diagnostics_page = make_page("diagnostics", "Diagnostics", "Runtime tracing and automatic crash or UI-freeze reports.")

    nav_button("core", "Core")
    nav_button("overlays", "Overlays")
    nav_button("crt", "HUD Effects")
    nav_button("voice", "Voice")
    nav_button("theme", "Theme")
    nav_button("integrations", "Integrations")
    nav_button("diagnostics", "Diagnostics")

    core_paths = section(core_page, "Paths")
    j_e = input_row(core_paths, "Journal Path", "journal_path")
    ss_e = input_row(core_paths, "Screenshot Folder", "screenshots_path")

    core_shots = section(core_page, "Screenshots")
    toggle_row(core_shots, "Convert BMP screenshots to PNG", ss_var)

    overlay_modules = section(overlay_page, "Modules")
    toggle_row(overlay_modules, "Tactical Overlay", ov_var)
    toggle_row(overlay_modules, "Compact Tactical HUD", hud_compact_var)
    toggle_row(overlay_modules, "Cargo Manifest Overlay", cargo_var)
    toggle_row(overlay_modules, "Fleet Carrier Overlay", carrier_overlay_var)
    toggle_row(overlay_modules, "Colony Shopping Overlay", colony_var)
    toggle_row(overlay_modules, "Prospector Result Overlay", prosp_var)
    toggle_row(overlay_modules, "System Info Overlay", sysinfo_var)
    toggle_row(overlay_modules, "Gravity Warning Overlay", gravity_var)
    toggle_row(overlay_modules, "Station Info Overlay", station_info_var)
    toggle_row(overlay_modules, "Survey Status Strip", survey_status_var)
    toggle_row(overlay_modules, "Toast Notifications", toast_var)
    toggle_row(overlay_modules, "Journal Heartbeat Pulse", heartbeat_var)

    overlay_alerts = section(overlay_page, "Actionable Alerts")
    toggle_row(overlay_alerts, "Clear-to-sample notifications", sample_clear_var)
    toggle_row(overlay_alerts, "Rebuy coverage warnings", rebuy_warning_var)
    toggle_row(overlay_alerts, "Unsold exploration-data risk warnings", data_risk_var)

    overlay_timing = section(overlay_page, "Timing")
    prosp_timeout_e = input_row(overlay_timing, "Prospector Auto-Hide", "prospector_hud_timeout_s")
    sysinfo_timeout_e = input_row(overlay_timing, "System Info Auto-Hide", "system_info_timeout_s")
    gravity_threshold_e = input_row(overlay_timing, "Gravity Warning Threshold (g)", "gravity_warning_threshold_g")

    overlay_crt = section(crt_page, "Navigation HUD CRT")
    toggle_row(overlay_crt, "CRT effects", hud_crt_var)
    toggle_row(overlay_crt, "Moving refresh and flicker", hud_crt_motion_var)
    option_row(overlay_crt, "CRT intensity", hud_crt_intensity_var, ("Subtle", "Standard", "Strong"))

    # ---- Voice page ----
    voice_general = section(voice_page, "Voice Callouts")
    toggle_row(voice_general, "Enable voice callouts", voice_enabled_var)
    toggle_row(voice_general, "Safety and danger", voice_safety_var)
    toggle_row(voice_general, "Exploration and biology", voice_exploration_var)
    toggle_row(voice_general, "Navigation milestones", voice_navigation_var)
    toggle_row(voice_general, "Trade, Engineering, and missions", voice_objectives_var)
    toggle_row(voice_general, "Cache generated callouts", voice_cache_var)

    voice_catalog = section(voice_page, "Neural Voice Pack")
    voice_names = list(voice_callouts.VOICES)
    voice_labels = {
        name: f"{item['label']} ({item['mb']} MB)"
        for name, item in voice_callouts.VOICES.items()
    }
    label_to_voice = {label: name for name, label in voice_labels.items()}
    initial_voice = voice_callouts.selected_voice(config)
    voice_choice_var = tk.StringVar(value=voice_labels[initial_voice])
    voice_menu = option_row(voice_catalog, "Voice", voice_choice_var, [voice_labels[name] for name in voice_names])
    voice_menu.configure(width=34)

    volume_frame = row(voice_catalog)
    tk.Label(volume_frame, text="Volume", font=UI_FONT_BOLD, fg=UI_MUTED,
             bg=UI_PANEL, anchor="w", width=24).pack(side=tk.LEFT)
    volume_scale = tk.Scale(
        volume_frame, from_=0.1, to=1.0, resolution=0.05, orient=tk.HORIZONTAL,
        variable=voice_volume_var, showvalue=True, length=260,
        bg=UI_PANEL, fg=COLOR_TEXT, troughcolor=UI_PANEL_2,
        activebackground=COLOR_ACCENT, highlightthickness=0, bd=0,
    )
    volume_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)

    voice_status_var = tk.StringVar(value="Checking installed voice packs...")
    voice_status_label = tk.Label(
        voice_catalog, textvariable=voice_status_var, font=UI_FONT, fg=UI_MUTED,
        bg=UI_PANEL, anchor="w", justify=tk.LEFT, wraplength=620,
    )
    voice_status_label.pack(fill=tk.X, padx=12, pady=(2, 6))
    voice_cache_status_var = tk.StringVar(value="")
    tk.Label(
        voice_catalog, textvariable=voice_cache_status_var, font=UI_FONT,
        fg=UI_DIM, bg=UI_PANEL, anchor="w",
    ).pack(fill=tk.X, padx=12, pady=(0, 2))
    voice_actions = row(voice_catalog)

    def _chosen_voice():
        return label_to_voice.get(voice_choice_var.get(), voice_callouts.DEFAULT_VOICE)

    def _install_voice():
        try:
            voice_callouts.start_download(_chosen_voice())
            _refresh_voice_status(False)
        except voice_callouts.VoiceError as exc:
            tk.messagebox.showwarning("Voice Pack", str(exc), parent=win)

    def _test_voice():
        chosen = _chosen_voice()
        if not voice_callouts.ready(chosen):
            tk.messagebox.showwarning("Voice Test", "Install the selected voice pack first.", parent=win)
            return
        try:
            if voice_manager is None:
                raise voice_callouts.VoiceError("Voice playback is not connected. Restart VoidCompass and try again.")
            voice_manager.test(chosen, voice_volume_var.get(), voice_cache_var.get())
            voice_status_var.set("Test callout queued.")
        except voice_callouts.VoiceError as exc:
            tk.messagebox.showwarning("Voice Test", str(exc), parent=win)

    install_voice_btn = action_button(voice_actions, "Download Voice Pack", _install_voice, accent=True)
    install_voice_btn.pack(side=tk.LEFT)
    test_voice_btn = action_button(voice_actions, "Test Voice", _test_voice)
    test_voice_btn.pack(side=tk.LEFT, padx=(8, 0))

    def _clear_voice_cache():
        result = voice_callouts.clear_cache()
        freed_mb = result["bytes"] / (1024 * 1024)
        voice_cache_status_var.set(f"Cleared {result['files']} cached files ({freed_mb:.1f} MB).")

    action_button(voice_actions, "Clear Cache", _clear_voice_cache, muted=True).pack(side=tk.RIGHT)

    def _refresh_voice_status(schedule=True):
        if not win.winfo_exists():
            return
        chosen = _chosen_voice()
        state = voice_callouts.status(chosen)
        cache = voice_callouts.cache_status()
        voice_cache_status_var.set(
            f"Audio cache: {cache['files']} files · {cache['bytes'] / (1024 * 1024):.1f} MB "
            f"· maximum {cache['limit']} files"
        )
        if state["downloading"]:
            active = state.get("download_voice") or chosen
            label = voice_callouts.VOICES.get(active, {}).get("label", active)
            voice_status_var.set(f"Downloading {label}: {state['progress'] * 100:.0f}%")
            install_voice_btn.configure(state=tk.DISABLED, text="Downloading...")
        elif state["ready"]:
            playback_error = getattr(voice_manager, "last_error", None) if voice_manager else None
            voice_status_var.set(
                f"Playback error: {playback_error}" if playback_error
                else "Selected voice pack is installed and active for live callouts."
            )
            install_voice_btn.configure(state=tk.DISABLED, text="Installed")
        elif state["error"] and state.get("download_voice") == chosen:
            voice_status_var.set(state["error"])
            install_voice_btn.configure(state=tk.NORMAL, text="Retry Download")
        else:
            size = voice_callouts.VOICES[chosen]["mb"]
            voice_status_var.set(f"Not installed. Download size is approximately {size} MB, plus the Piper runtime on first install.")
            install_voice_btn.configure(state=tk.NORMAL, text="Download Voice Pack")
        test_voice_btn.configure(state=tk.NORMAL if state["ready"] else tk.DISABLED)
        if schedule:
            try:
                win.after(750, _refresh_voice_status)
            except tk.TclError:
                pass

    def _voice_changed(*_args):
        try:
            voice_callouts.set_selected_voice(config, _chosen_voice())
            # Voice choice is a live setting: the callout manager holds this
            # same config object, so future queued calls use it immediately.
            # Persist it now so closing Settings without Save does not silently
            # restore the previous voice on restart.
            persist_config(config)
        except voice_callouts.VoiceError as exc:
            voice_status_var.set(str(exc))
            return
        _refresh_voice_status(False)

    voice_choice_var.trace_add("write", _voice_changed)
    _refresh_voice_status()

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
                    win.after(0, lambda: tk.messagebox.showwarning("EDSM Test", msg, parent=win))
                    return

                body = r.json()
                msgnum = body.get("msgnum")
                msg = body.get("msg", "Unknown EDSM response")
                if msgnum == 100:
                    win.after(0, lambda: tk.messagebox.showinfo("EDSM Test", "API key verified successfully.", parent=win))
                elif msgnum == 207:
                    win.after(0, lambda: tk.messagebox.showinfo("EDSM Test", "Commander/API key accepted, but EDSM has no rank data stored yet.", parent=win))
                else:
                    win.after(0, lambda: tk.messagebox.showwarning("EDSM Test", f"EDSM response [{msgnum}]: {msg}", parent=win))
            except Exception as e:
                win.after(0, lambda: tk.messagebox.showerror("EDSM Test", f"Request failed: {e}", parent=win))

        threading.Thread(target=_do_test, daemon=True).start()

    edsm_actions = row(edsm_section)
    action_button(edsm_actions, "Test API Key", _test_edsm).pack(side=tk.LEFT)

    carrier_section = section(integrations_page, "Fleet Carrier Discord")
    fc_wh_e = input_row(carrier_section, "Discord Webhook URL", "carrier_discord_webhook_url")

    def _test_discord():
        url = fc_wh_e.get().strip()
        if not url:
            tk.messagebox.showwarning("No URL", "Enter a webhook URL first.", parent=win)
            return
        if carrier_tracker is not None:
            import threading
            threading.Thread(target=carrier_tracker.send_test_discord, args=(url,), daemon=True).start()
            tk.messagebox.showinfo("Test Sent", "Test message dispatched - check your Discord channel.", parent=win)
        else:
            tk.messagebox.showinfo("Not Available", "Carrier tracker not connected; save and reopen settings.", parent=win)

    carrier_actions = row(carrier_section)
    action_button(carrier_actions, "Send Test Message", _test_discord).pack(side=tk.LEFT)

    diagnostics_section = section(diagnostics_page, "Runtime Diagnostics")
    toggle_row(diagnostics_section, "Runtime performance trace log", runtime_trace_var)
    toggle_row(diagnostics_section, "Crash and UI-freeze reporter", crash_reporting_var)
    tk.Label(
        diagnostics_section,
        text="Changes take effect after restarting VoidCompass. Ctrl+Alt+D writes a manual stack dump when crash reporting is enabled.",
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
        config.update({
            "journal_path": j_e.get().strip(),
            "overlay_enabled": ov_var.get(),
            "hud_compact_mode": hud_compact_var.get(),
            "cargo_overlay_enabled": cargo_var.get(),
            "carrier_overlay_enabled": carrier_overlay_var.get(),
            "colony_overlay_enabled": colony_var.get(),
            "prospector_overlay_enabled": prosp_var.get(),
            "prospector_hud_timeout_s": max(5, int(prosp_timeout_e.get().strip() or 45))
                if prosp_timeout_e.get().strip().isdigit() else
                config.get("prospector_hud_timeout_s", 45),
            "system_info_enabled": sysinfo_var.get(),
            "system_info_timeout_s": max(5, int(sysinfo_timeout_e.get().strip() or 30))
                if sysinfo_timeout_e.get().strip().isdigit() else
                config.get("system_info_timeout_s", 30),
            "gravity_warning_overlay_enabled": gravity_var.get(),
            "gravity_warning_threshold_g": _parse_float(gravity_threshold_e.get(), config.get("gravity_warning_threshold_g", 3.0)),
            "station_info_overlay_enabled": station_info_var.get(),
            "survey_status_overlay_enabled": survey_status_var.get(),
            "toast_overlay_enabled": toast_var.get(),
            "hud_crt_enabled": hud_crt_var.get(),
            "hud_crt_motion_enabled": hud_crt_motion_var.get(),
            "hud_crt_intensity": hud_crt_intensity_var.get(),
            "sample_clear_notifications_enabled": sample_clear_var.get(),
            "rebuy_warnings_enabled": rebuy_warning_var.get(),
            "data_risk_warnings_enabled": data_risk_var.get(),
            "heartbeat_overlay_enabled": heartbeat_var.get(),
            "ui_theme_name": theme_var.get(),
            "ui_custom_themes": dict(custom_themes),
            "screenshots_enabled": ss_var.get(),
            "screenshots_path": ss_e.get().strip(),
            "carrier_discord_webhook_url": fc_wh_e.get().strip(),
            "edsm_cmdr_name": edsm_cmdr_e.get().strip(),
            "edsm_api_key": edsm_key_e.get().strip(),
            "edsm_upload_enabled": edsm_upload_var.get(),
            "runtime_trace_enabled": runtime_trace_var.get(),
            "crash_reporting_enabled": crash_reporting_var.get(),
            "voice_callouts_enabled": voice_enabled_var.get(),
            "voice_safety_enabled": voice_safety_var.get(),
            "voice_exploration_enabled": voice_exploration_var.get(),
            "voice_navigation_enabled": voice_navigation_var.get(),
            "voice_objectives_enabled": voice_objectives_var.get(),
            "voice_cache_enabled": voice_cache_var.get(),
            "voice_name": _chosen_voice(),
            "voice_volume": float(voice_volume_var.get()),
            "settings_geometry": win.geometry(),
        })
        remove_deprecated_keys()
        persist_config(config)
        saved_name = theme_var.get()
        saved_palette = _theme_palette(saved_name)
        if saved_name != themes.ACTIVE_THEME_NAME or saved_palette != themes.ACTIVE_PALETTE:
            from ui_theme import apply_theme_live
            try:
                apply_theme_live(root, saved_name, saved_palette)
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
    show_page("core")
    return win
