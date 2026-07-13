import os
import time
import tkinter as tk
import tkinter.messagebox
from tkinter import colorchooser

import themes
import voice_callouts
import compass_llm as compass_llm_module
import compass_personas
from cockpit_ai_memory import DEFAULT_LIMITS as COCKPIT_MEMORY_DEFAULTS, LIMIT_BOUNDS as COCKPIT_MEMORY_BOUNDS
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
                  on_close_callback=None, voice_manager=None, cockpit_memory=None,
                  cockpit_brain=None, compass_llm=None):
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

    def make_page(key, title, subtitle, scrollable=False):
        page = tk.Frame(content, bg=UI_BG)
        pages[key] = page
        body = page
        if scrollable:
            canvas = tk.Canvas(
                page, bg=UI_BG, bd=0, highlightthickness=0,
                takefocus=True,
            )
            scrollbar = tk.Scrollbar(
                page, orient=tk.VERTICAL, command=canvas.yview,
                bg=UI_PANEL_2, activebackground=COLOR_ACCENT,
                troughcolor=UI_BG, relief=tk.FLAT, bd=0, width=12,
            )
            canvas.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
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
        if key == "compass":
            try:
                _refresh_compass_page()
            except (NameError, tk.TclError):
                pass

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
    voice_cache_auto_prune_var = tk.BooleanVar(
        value=config.get("voice_cache_auto_prune_enabled", True)
    )
    voice_cache_retention_var = tk.StringVar(
        value=str(config.get("voice_cache_retention_days", 7))
    )
    cockpit_memory_var = tk.BooleanVar(value=config.get("cockpit_memory_enabled", True))
    cockpit_ambient_var = tk.BooleanVar(value=config.get("cockpit_ambient_chatter_enabled", True))
    cockpit_greetings_var = tk.BooleanVar(value=config.get("cockpit_session_greetings_enabled", True))
    cockpit_callbacks_var = tk.BooleanVar(value=config.get("cockpit_memory_callbacks_enabled", True))
    cockpit_llm_var = tk.BooleanVar(value=config.get("cockpit_llm_enabled", False))
    cockpit_llm_advisor_var = tk.BooleanVar(
        value=config.get("cockpit_llm_advisor_enabled", True)
    )
    cockpit_llm_auto_var = tk.BooleanVar(value=config.get("cockpit_llm_auto_start", True))
    cockpit_llm_unload_var = tk.BooleanVar(value=config.get("cockpit_llm_unload_on_shutdown", True))
    cockpit_llm_model_var = tk.StringVar(
        value=str(config.get("cockpit_llm_model", compass_llm_module.DEFAULT_MODEL))
    )
    cockpit_llm_timeout_var = tk.StringVar(
        value=str(config.get("cockpit_llm_timeout_s", 2.5))
    )
    cockpit_llm_advisor_level_var = tk.StringVar(
        value=str(config.get("cockpit_llm_advisor_level", "Balanced"))
    )
    cockpit_personality_var = tk.StringVar(
        value=str(config.get("cockpit_personality_level", "Balanced") or "Balanced")
    )
    cockpit_persona_var = tk.StringVar(
        value=compass_personas.normalize_persona(config.get("cockpit_persona"))
    )
    cockpit_limit_vars = {
        "systems": tk.StringVar(value=str(config.get("cockpit_memory_system_limit", 300))),
        "species": tk.StringVar(value=str(config.get("cockpit_memory_species_limit", 200))),
        "ships": tk.StringVar(value=str(config.get("cockpit_memory_ship_limit", 30))),
        "memories": tk.StringVar(value=str(config.get("cockpit_memory_episode_limit", 80))),
    }
    voice_volume_var = tk.DoubleVar(value=float(config.get("voice_volume", 0.8) or 0.8))
    if "screenshots_path" not in config:
        config["screenshots_path"] = os.path.join(os.path.expanduser("~"), "Pictures", "Frontier Developments", "Elite Dangerous")

    # Pages
    core_page = make_page("core", "Core", "Journal and screenshot paths.")
    overlay_page = make_page("overlays", "Overlays", "Runtime modules and display timing.")
    crt_page = make_page("crt", "HUD Effects", "CRT styling for the native Navigation HUD.")
    voice_page = make_page(
        "voice", "Voice", "Optional local neural callouts. Voice audio never leaves this computer.",
        scrollable=True,
    )
    compass_page = make_page(
        "compass", "Compass AI",
        "Review and curate the local history Compass has learned from this commander.",
        scrollable=True,
    )
    theme_page = make_page("theme", "Theme", "Color theme for this commander profile. Applies when you save.")
    integrations_page = make_page("integrations", "Integrations", "EDSM upload and fleet carrier Discord.")
    diagnostics_page = make_page("diagnostics", "Diagnostics", "Runtime tracing and automatic crash or UI-freeze reports.")

    nav_button("core", "Core")
    nav_button("overlays", "Overlays")
    nav_button("crt", "HUD Effects")
    nav_button("voice", "Voice")
    nav_button("compass", "Compass AI")
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
    toggle_row(overlay_crt, "Subtle phosphor shimmer", hud_crt_motion_var)
    option_row(overlay_crt, "CRT intensity", hud_crt_intensity_var, ("Subtle", "Standard", "Strong"))

    # ---- Voice page ----
    voice_general = section(voice_page, "Voice Callouts")
    toggle_row(voice_general, "Enable voice callouts", voice_enabled_var)
    toggle_row(voice_general, "Safety and danger", voice_safety_var)
    toggle_row(voice_general, "Exploration and biology", voice_exploration_var)
    toggle_row(voice_general, "Navigation milestones", voice_navigation_var)
    toggle_row(voice_general, "Trade, Engineering, and missions", voice_objectives_var)
    toggle_row(voice_general, "Cache generated callouts", voice_cache_var)
    toggle_row(voice_general, "Automatically prune unused cached audio", voice_cache_auto_prune_var)
    option_row(
        voice_general, "Unused audio retention (days)", voice_cache_retention_var,
        ["1", "3", "7", "14", "30", "60", "90"],
    )

    memory_panel = section(voice_page, "Compass Memory")
    memory_controls = row(memory_panel)
    tk.Label(memory_controls, text="Learn from this commander", font=UI_FONT, fg=COLOR_TEXT,
             bg=UI_PANEL, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
    memory_toggle = tk.Button(
        memory_controls, font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
        bd=0, width=9, cursor="hand2",
    )

    def _refresh_memory_toggle():
        if cockpit_memory_var.get():
            memory_toggle.config(text="On", bg=COLOR_ACCENT, fg="black",
                                 activebackground=COLOR_ACCENT, activeforeground="black")
        else:
            memory_toggle.config(text="Off", bg=UI_PANEL_2, fg=UI_MUTED,
                                 activebackground=UI_PANEL_2, activeforeground=COLOR_TEXT)

    def _toggle_cockpit_memory():
        cockpit_memory_var.set(not cockpit_memory_var.get())
        _refresh_memory_toggle()

    memory_toggle.config(command=_toggle_cockpit_memory)
    memory_toggle.pack(side=tk.RIGHT)
    personality_menu = tk.OptionMenu(
        memory_controls, cockpit_personality_var, "Quiet", "Balanced", "Chatty"
    )
    personality_menu.config(
        bg=UI_PANEL_2, fg=COLOR_TEXT, activebackground=UI_PANEL_2,
        activeforeground=COLOR_ACCENT, relief=tk.FLAT, bd=0,
        highlightthickness=0, font=UI_FONT, width=9,
    )
    personality_menu["menu"].config(bg=UI_PANEL_2, fg=COLOR_TEXT)
    personality_menu.pack(side=tk.RIGHT, padx=(8, 8))
    tk.Label(memory_controls, text="Chatter", font=UI_FONT_BOLD, fg=UI_MUTED,
             bg=UI_PANEL).pack(side=tk.RIGHT)
    _refresh_memory_toggle()
    toggle_row(memory_panel, "Ambient chatter while cruising", cockpit_ambient_var)
    toggle_row(memory_panel, "Session greetings (welcome back / new day)", cockpit_greetings_var)
    toggle_row(memory_panel, "Memory callbacks in system remarks", cockpit_callbacks_var)
    memory_summary_var = tk.StringVar(value="Compass has not created a memory profile yet.")
    tk.Label(
        memory_panel, textvariable=memory_summary_var, font=UI_FONT,
        fg=UI_MUTED, bg=UI_PANEL, anchor="w", justify=tk.LEFT, wraplength=620,
    ).pack(fill=tk.X, padx=12, pady=(3, 6))

    def _reset_cockpit_memory():
        if cockpit_memory is None:
            return
        if not tk.messagebox.askyesno(
            "Reset Compass Memory",
            "Forget all systems, discoveries, habits, milestones, and shared history for this commander?",
            parent=win,
        ):
            return
        cockpit_memory.reset()
        memory_summary_var.set(cockpit_memory.summary_text())

    memory_actions = row(memory_panel)
    action_button(memory_actions, "Forget Learned History", _reset_cockpit_memory, muted=True).pack(side=tk.RIGHT)
    tk.Label(memory_actions, text="Caps", font=UI_FONT_BOLD, fg=UI_MUTED,
             bg=UI_PANEL).pack(side=tk.LEFT, padx=(0, 7))
    for limit_key, label in (("systems", "SYS"), ("species", "BIO"),
                             ("ships", "SHIPS"), ("memories", "NOTES")):
        tk.Label(memory_actions, text=label, font=("Segoe UI", 7, "bold"), fg=UI_DIM,
                 bg=UI_PANEL).pack(side=tk.LEFT, padx=(5, 2))
        entry = tk.Entry(
            memory_actions, textvariable=cockpit_limit_vars[limit_key], width=5,
            bg=UI_INPUT, fg=COLOR_TEXT, insertbackground=COLOR_ACCENT,
            font=UI_MONO, relief=tk.FLAT, justify=tk.CENTER,
            highlightthickness=1, highlightbackground=UI_BORDER,
            highlightcolor=COLOR_ACCENT,
        )
        entry.pack(side=tk.LEFT, ipady=3)

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

    def _voice_cache_retention_days():
        try:
            return max(1, min(365, int(voice_cache_retention_var.get())))
        except (TypeError, ValueError, tk.TclError):
            return voice_callouts.DEFAULT_CACHE_RETENTION_DAYS

    def _refresh_voice_status(schedule=True):
        if not win.winfo_exists():
            return
        chosen = _chosen_voice()
        state = voice_callouts.status(chosen)
        retention = _voice_cache_retention_days() if voice_cache_auto_prune_var.get() else None
        cache = voice_callouts.cache_status(retention)
        if cockpit_memory is not None:
            memory_summary_var.set(cockpit_memory.summary_text())
        retention_text = (
            f" · auto-prune after {retention} day{'s' if retention != 1 else ''} unused"
            if retention is not None else " · age pruning off"
        )
        voice_cache_status_var.set(
            f"Audio cache: {cache['files']} files · {cache['bytes'] / (1024 * 1024):.1f} MB "
            f"· maximum {cache['limit']} files{retention_text}"
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
            chosen = voice_callouts.set_selected_voice(config, _chosen_voice())
            if cockpit_memory is not None and cockpit_memory_var.get():
                cockpit_memory.voice_selected(
                    chosen, voice_callouts.VOICES.get(chosen, {}).get("label", chosen)
                )
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

    # ---- Compass persona ----
    persona_panel = section(compass_page, "Compass Persona")
    tk.Label(
        persona_panel,
        text=(
            "Persona controls Ollama's tone, humour, initiative, and preferred memory emphasis. "
            "It never changes journal facts, safety warnings, or the separate Chatter frequency setting."
        ),
        font=UI_FONT, fg=UI_MUTED, bg=UI_PANEL, anchor="w", justify=tk.LEFT,
        wraplength=650,
    ).pack(fill=tk.X, padx=12, pady=(2, 8))
    persona_menu = option_row(
        persona_panel, "Active persona", cockpit_persona_var,
        list(compass_personas.PERSONA_NAMES),
    )
    persona_menu.configure(width=24)
    persona_description_var = tk.StringVar()
    tk.Label(
        persona_panel, textvariable=persona_description_var, font=UI_FONT,
        fg=COLOR_TEXT, bg=UI_PANEL, anchor="w", justify=tk.LEFT, wraplength=650,
    ).pack(fill=tk.X, padx=12, pady=(3, 8))

    def _refresh_persona_description(*_args):
        profile = compass_personas.persona_profile(cockpit_persona_var.get())
        persona_description_var.set(
            f"{profile['description']}\n"
            f"Style: {profile['style']} · Memory emphasis: {profile['memory_bias']}"
        )

    cockpit_persona_var.trace_add("write", _refresh_persona_description)
    _refresh_persona_description()

    # ---- Compass generative language ----
    llm_panel = section(compass_page, "Local Generative Language")
    tk.Label(
        llm_panel,
        text=(
            "Optional Ollama working-brain layer for non-safety speech. It receives a compact verified "
            "pilot model, relevant memories, live state, and recent decisions, then chooses useful speech "
            "or silence. Urgent warnings remain deterministic; invalid or slow decisions use the existing line."
        ),
        font=UI_FONT, fg=UI_MUTED, bg=UI_PANEL, anchor="w", justify=tk.LEFT, wraplength=650,
    ).pack(fill=tk.X, padx=12, pady=(2, 8))
    toggle_row(llm_panel, "Enable generative Compass language", cockpit_llm_var)
    toggle_row(llm_panel, "Enable proactive situational adviser", cockpit_llm_advisor_var)
    toggle_row(llm_panel, "Start local Ollama automatically", cockpit_llm_auto_var)
    toggle_row(llm_panel, "Unload model when VoidCompass closes", cockpit_llm_unload_var)
    llm_model_menu = option_row(
        llm_panel, "Local model", cockpit_llm_model_var,
        list(compass_llm_module.MODEL_CHOICES),
    )
    llm_model_menu.configure(width=24)
    option_row(
        llm_panel, "Fallback timeout", cockpit_llm_timeout_var,
        ["1.5", "2.5", "4.0"],
    )
    option_row(
        llm_panel, "Advice frequency", cockpit_llm_advisor_level_var,
        ["Quiet", "Balanced", "Proactive"],
    )
    llm_status_var = tk.StringVar(value="Checking local language runtime...")
    tk.Label(
        llm_panel, textvariable=llm_status_var, font=UI_FONT, fg=COLOR_TEXT,
        bg=UI_PANEL, anchor="w", justify=tk.LEFT, wraplength=650,
    ).pack(fill=tk.X, padx=12, pady=(4, 8))

    def _llm_status_text(status=None):
        if compass_llm is None:
            return "Compass language service is unavailable in this session."
        status = status if isinstance(status, dict) else compass_llm.status()
        phase = str(status.get("phase") or "unknown").replace("_", " ").title()
        model = status.get("model") or cockpit_llm_model_var.get()
        details = [f"{phase} · {model}"]
        if status.get("installed"):
            details.append("installed")
        if status.get("processor"):
            details.append(str(status["processor"]))
        if status.get("last_latency_ms") is not None:
            details.append(f"last response {int(status['last_latency_ms']):,} ms")
        if status.get("last_action"):
            details.append(f"last decision {status['last_action']}")
        progress = status.get("download_progress")
        if progress is not None and status.get("phase") == "downloading":
            details.append(f"download {float(progress) * 100:.0f}%")
        text = " · ".join(details)
        if status.get("last_error"):
            text += f"\n{status['last_error']}"
        elif not status.get("executable"):
            text += "\nOllama is not installed or could not be found."
        return text

    def _set_llm_status(status=None):
        def apply():
            try:
                llm_status_var.set(_llm_status_text(status))
            except tk.TclError:
                pass
        try:
            win.after(0, apply)
        except tk.TclError:
            pass

    def _install_llm_model():
        if compass_llm is None:
            return
        llm_status_var.set(f"Preparing {cockpit_llm_model_var.get()} download...")
        compass_llm.install_model_async(cockpit_llm_model_var.get(), callback=_set_llm_status)

    def _warm_llm_model():
        if compass_llm is None:
            return
        llm_status_var.set(f"Loading {cockpit_llm_model_var.get()} into memory...")
        compass_llm.warm_async(
            force=True, model=cockpit_llm_model_var.get(), callback=_set_llm_status,
        )

    def _test_llm_model():
        if compass_llm is None:
            return
        llm_status_var.set("Generating a local Compass test line...")

        def completed(result):
            if isinstance(result, dict) and result.get("line"):
                status = compass_llm.status()
                prefix = "Generated" if result.get("used_llm") else "Fallback"
                status["last_error"] = (
                    f"{prefix}: {result['line']}"
                    + (f" ({result.get('error')})" if result.get("error") else "")
                )
                _set_llm_status(status)
                if result.get("used_llm") and voice_manager is not None:
                    voice_manager.say(
                        result["line"], category="ambient", cooldown_s=0,
                        key=f"compass-llm-test:{time.time_ns()}",
                    )
            else:
                _set_llm_status(result)

        compass_llm.test_async(cockpit_llm_model_var.get(), callback=completed)

    def _test_persona():
        if compass_llm is None:
            return
        profile = compass_personas.persona_profile(cockpit_persona_var.get())
        llm_status_var.set(f"Generating a {profile['name']} persona preview...")
        brain_context = cockpit_brain.model_context() if cockpit_brain is not None else {
            "identity": {"name": "Compass"}, "pilot_model": {},
            "working_memory": {}, "recent_decisions": [],
        }
        pilot = brain_context.setdefault("pilot_model", {})
        pilot["persona"] = profile
        brain_context.setdefault("working_memory", {})["purpose"] = "persona-preview"
        context = {
            "purpose": "persona-preview",
            "working_brain": brain_context,
            "approved_memory_texts": [],
        }

        def completed(result):
            if isinstance(result, dict) and result.get("line"):
                status = compass_llm.status()
                prefix = "Generated" if result.get("used_llm") else "Fallback"
                status["last_error"] = (
                    f"{prefix} {profile['name']}: {result['line']}"
                    + (f" ({result.get('error')})" if result.get("error") else "")
                )
                _set_llm_status(status)
                if result.get("used_llm") and voice_manager is not None:
                    voice_manager.say(
                        result["line"], category="ambient", cooldown_s=0,
                        key=f"compass-persona-test:{profile['name']}:{time.time_ns()}",
                    )
            else:
                _set_llm_status(result)

        compass_llm.test_async(
            cockpit_llm_model_var.get(), callback=completed, context=context,
            fallback="Compass persona preview is online; local language and voice systems are ready.",
            topic=f"persona-preview:{profile['name']}",
        )

    persona_actions = row(persona_panel)
    action_button(persona_actions, "Test Persona", _test_persona, accent=True).pack(side=tk.LEFT)

    llm_actions = row(llm_panel)
    action_button(llm_actions, "Install / Update Model", _install_llm_model, accent=True).pack(side=tk.LEFT)
    action_button(llm_actions, "Warm Up", _warm_llm_model).pack(side=tk.LEFT, padx=(8, 0))
    action_button(llm_actions, "Test Language", _test_llm_model).pack(side=tk.LEFT, padx=(8, 0))
    action_button(llm_actions, "Refresh", _set_llm_status, muted=True).pack(side=tk.RIGHT)
    _set_llm_status()

    # ---- Compass memory browser ----
    compass_overview = section(compass_page, "Current Intelligence State")
    compass_status_var = tk.StringVar(value="Compass memory is unavailable.")
    tk.Label(
        compass_overview, textvariable=compass_status_var, font=UI_FONT,
        fg=COLOR_TEXT, bg=UI_PANEL, anchor="w", justify=tk.LEFT, wraplength=650,
    ).pack(fill=tk.X, padx=12, pady=(4, 10))
    expedition_name_var = tk.StringVar(value="")
    expedition_row = row(compass_overview)
    tk.Label(expedition_row, text="Active expedition", font=UI_FONT_BOLD, fg=UI_MUTED,
             bg=UI_PANEL).pack(side=tk.LEFT, padx=(0, 8))
    tk.Entry(
        expedition_row, textvariable=expedition_name_var, bg=UI_INPUT, fg=COLOR_TEXT,
        insertbackground=COLOR_ACCENT, font=UI_FONT, relief=tk.FLAT,
        highlightthickness=1, highlightbackground=UI_BORDER,
        highlightcolor=COLOR_ACCENT,
    ).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

    def _rename_expedition():
        if cockpit_memory and cockpit_memory.rename_active_expedition(expedition_name_var.get()):
            _refresh_compass_page()

    action_button(expedition_row, "Rename", _rename_expedition).pack(side=tk.RIGHT, padx=(8, 0))

    compass_history = section(compass_page, "Notable Memory Timeline")
    memory_list = tk.Listbox(
        compass_history, height=12, bg=UI_INPUT, fg=COLOR_TEXT,
        selectbackground=COLOR_ACCENT, selectforeground="black",
        font=UI_MONO, relief=tk.FLAT, bd=0, highlightthickness=1,
        highlightbackground=UI_BORDER, highlightcolor=COLOR_ACCENT,
    )
    memory_list.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 6))
    memory_ids = []
    memory_edit_var = tk.StringVar(value="")
    edit_row = row(compass_history)
    tk.Label(edit_row, text="Selected memory", font=UI_FONT_BOLD, fg=UI_MUTED,
             bg=UI_PANEL).pack(side=tk.LEFT, padx=(0, 8))
    memory_edit = tk.Entry(
        edit_row, textvariable=memory_edit_var, bg=UI_INPUT, fg=COLOR_TEXT,
        insertbackground=COLOR_ACCENT, font=UI_FONT, relief=tk.FLAT,
        highlightthickness=1, highlightbackground=UI_BORDER,
        highlightcolor=COLOR_ACCENT,
    )
    memory_edit.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

    def _selected_memory_id():
        selected = memory_list.curselection()
        return memory_ids[selected[0]] if selected and selected[0] < len(memory_ids) else None

    def _memory_selected(_event=None):
        memory_id = _selected_memory_id()
        row_data = cockpit_memory.get_memory(memory_id) if cockpit_memory and memory_id else None
        memory_edit_var.set(row_data.get("text", "") if row_data else "")

    memory_list.bind("<<ListboxSelect>>", _memory_selected)

    def _refresh_compass_page():
        _set_llm_status()
        memory_list.delete(0, tk.END)
        memory_ids.clear()
        if cockpit_memory is None:
            compass_status_var.set("Compass memory is unavailable in this session.")
            return
        details = cockpit_memory.status_details()
        mood = details["mood"]
        habits = ", ".join(details["habits"]) if details["habits"] else "still learning flight habits"
        intentions = details["intentions"]
        intention_text = ", ".join(str(key).replace("_", " ") for key in intentions) if intentions else "no unfinished intentions"
        expedition = details.get("active_expedition")
        expedition_name_var.set(expedition.get("name", "") if expedition else "")
        expedition_text = (
            f"Active expedition: {expedition.get('name')} · {int(expedition.get('jumps') or 0):,} jumps"
            if expedition else f"Completed expeditions: {details['completed_expeditions']:,}"
        )
        awareness = details["gameplay_awareness"]
        biology = details["biology_awareness"]
        awareness_domains = ", ".join(awareness["domains"]) if awareness["domains"] else "still observing"
        traffic = details.get("current_system_traffic") or {}
        traffic_text = (
            f"D/W/T {int(traffic.get('day') or 0):,}/{int(traffic.get('week') or 0):,}/{int(traffic.get('total') or 0):,}"
            if traffic else "not checked"
        )
        brain_status = cockpit_brain.status() if cockpit_brain is not None else {}
        brain_last = brain_status.get("last_decision") or {}
        brain_text = (
            f"Working brain: {int(brain_status.get('decisions') or 0)} recent decisions"
            + (f" · last {brain_last.get('action')} for {brain_last.get('topic')}" if brain_last else "")
        )
        compass_status_var.set(
            f"{details['relationship']} · Voice stage: {str(details['voice_stage']).title()} · "
            f"Persona: {brain_status.get('persona') or 'Compass'}\n"
            f"Mood: {mood['name']} ({mood['reason']}) · Habits: {habits}\n"
            f"Intentions: {intention_text} · {expedition_text} · Sessions: {details['sessions']:,}\n"
            f"Exploration memory: {details['honks']:,} honks · "
            f"{details['fss_completed']:,} full FSS surveys · {details['dss_maps']:,} DSS maps · "
            f"{details['signal_bodies']:,} signal bodies · "
            f"{details.get('valuable_worlds', 0):,} valuable worlds\n"
            f"Biology memory: {biology['genera']:,} genera "
            f"({biology['detected_genera']:,} detected · {biology['predicted_genera']:,} predicted · "
            f"{biology['analysed_genera']:,} analysed) · {biology['samples']:,} samples · "
            f"{biology['analyses']:,} analyses · {biology['codex_entries']:,} biological Codex entries · "
            f"signals {biology['biological_signals']:,} bio / {biology['geological_signals']:,} geo\n"
            f"Traffic awareness: {details.get('traffic_known_systems', 0):,} travelled systems · "
            f"Current {traffic_text}\n"
            f"Gameplay awareness: {awareness_domains}\n"
            f"{brain_text}\n"
            f"Operational memory: {awareness['missions_completed']:,} missions · "
            f"{awareness['combat_victories']:,} combat victories · "
            f"{awareness['engineering_crafts']:,} engineering crafts · "
            f"{awareness['ground_operations']:,} ground events · "
            f"{awareness['carrier_jumps']:,} carrier jumps · "
            f"{awareness['colony_contributions']:,} colony contributions\n"
            f"Familiar system: {details['most_visited_system'] or 'none yet'} · "
            f"Most-used ship: {details['favorite_ship'] or 'none yet'}"
        )
        for memory_row in cockpit_memory.memory_rows():
            marker = "[PIN]" if memory_row.get("pinned") else "     "
            stamp = str(memory_row.get("timestamp") or "")[:10]
            memory_list.insert(tk.END, f"{marker} {stamp}  {memory_row.get('text', '')}")
            memory_ids.append(memory_row.get("id"))
        memory_edit_var.set("")

    def _pin_selected_memory():
        memory_id = _selected_memory_id()
        if memory_id and cockpit_memory.pin_memory(memory_id):
            _refresh_compass_page()

    def _save_selected_memory():
        memory_id = _selected_memory_id()
        if memory_id and cockpit_memory.rename_memory(memory_id, memory_edit_var.get()):
            _refresh_compass_page()

    def _delete_selected_memory():
        memory_id = _selected_memory_id()
        if not memory_id:
            return
        if tk.messagebox.askyesno("Delete Compass Memory", "Permanently forget the selected memory?", parent=win):
            cockpit_memory.delete_memory(memory_id)
            _refresh_compass_page()

    browser_actions = row(compass_history)
    action_button(browser_actions, "Refresh", _refresh_compass_page, muted=True).pack(side=tk.LEFT)
    action_button(browser_actions, "Pin / Unpin", _pin_selected_memory).pack(side=tk.LEFT, padx=(8, 0))
    action_button(browser_actions, "Save Edit", _save_selected_memory).pack(side=tk.LEFT, padx=(8, 0))
    action_button(browser_actions, "Delete", _delete_selected_memory, muted=True).pack(side=tk.RIGHT)

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
        memory_limits = {}
        for key, variable in cockpit_limit_vars.items():
            low, high = COCKPIT_MEMORY_BOUNDS[key]
            try:
                value = int(float(variable.get().strip()))
            except (TypeError, ValueError):
                value = COCKPIT_MEMORY_DEFAULTS[key]
            memory_limits[key] = max(low, min(high, value))
            variable.set(str(memory_limits[key]))
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
            "voice_cache_auto_prune_enabled": voice_cache_auto_prune_var.get(),
            "voice_cache_retention_days": _voice_cache_retention_days(),
            "cockpit_memory_enabled": cockpit_memory_var.get(),
            "cockpit_ambient_chatter_enabled": cockpit_ambient_var.get(),
            "cockpit_session_greetings_enabled": cockpit_greetings_var.get(),
            "cockpit_memory_callbacks_enabled": cockpit_callbacks_var.get(),
            "cockpit_llm_enabled": cockpit_llm_var.get(),
            "cockpit_llm_advisor_enabled": cockpit_llm_advisor_var.get(),
            "cockpit_llm_auto_start": cockpit_llm_auto_var.get(),
            "cockpit_llm_unload_on_shutdown": cockpit_llm_unload_var.get(),
            "cockpit_llm_model": cockpit_llm_model_var.get(),
            "cockpit_llm_timeout_s": float(cockpit_llm_timeout_var.get()),
            "cockpit_llm_advisor_level": cockpit_llm_advisor_level_var.get(),
            "cockpit_personality_level": cockpit_personality_var.get(),
            "cockpit_persona": compass_personas.normalize_persona(cockpit_persona_var.get()),
            "cockpit_memory_system_limit": memory_limits["systems"],
            "cockpit_memory_species_limit": memory_limits["species"],
            "cockpit_memory_ship_limit": memory_limits["ships"],
            "cockpit_memory_episode_limit": memory_limits["memories"],
            "voice_name": _chosen_voice(),
            "voice_volume": float(voice_volume_var.get()),
            "settings_geometry": win.geometry(),
        })
        if cockpit_memory is not None:
            cockpit_memory.configure_limits(memory_limits, save=True)
            memory_summary_var.set(cockpit_memory.summary_text())
        remove_deprecated_keys()
        persist_config(config)
        if voice_manager is not None:
            voice_manager.prune_cache_async()
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
    bind_scroll_tree(voice_page)
    bind_scroll_tree(compass_page)
    show_page("core")
    return win
