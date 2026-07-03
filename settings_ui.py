import json
import os
import tkinter as tk
import tkinter.messagebox

from config import CONFIG_FILE, DEPRECATED_CONFIG_KEYS, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_active_profile_config


UI_BG = "#080a0d"
UI_PANEL = "#12161b"
UI_PANEL_2 = "#171d23"
UI_BORDER = "#26313a"
UI_MUTED = "#7d8891"
UI_DIM = "#4e5962"
UI_INPUT = "#090c10"
UI_FONT = ("Segoe UI", 9)
UI_FONT_BOLD = ("Segoe UI", 9, "bold")
UI_FONT_TITLE = ("Segoe UI", 13, "bold")
UI_MONO = ("Consolas", 9)


def open_settings(root, config, on_save_callback, carrier_tracker=None):
    win = tk.Toplevel(root)
    win.title("SYSTEM CONFIGURATION")
    win.geometry(config.get("settings_geometry", "980x680"))
    win.minsize(880, 600)
    win.configure(bg=UI_BG)
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
        bg = COLOR_ACCENT if accent else parent.cget("bg")
        fg = "black" if accent else (UI_DIM if muted else COLOR_TEXT)
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=COLOR_ACCENT if accent else UI_PANEL_2,
            activeforeground="black" if accent else COLOR_TEXT,
            font=UI_FONT_BOLD,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
        )

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
    cargo_var = tk.BooleanVar(value=config.get("cargo_overlay_enabled", False))
    carrier_overlay_var = tk.BooleanVar(value=config.get("carrier_overlay_enabled", False))
    colony_var = tk.BooleanVar(value=config.get("colony_overlay_enabled", False))
    prosp_var = tk.BooleanVar(value=config.get("prospector_overlay_enabled", True))
    sysinfo_var = tk.BooleanVar(value=config.get("system_info_enabled", True))
    ss_var = tk.BooleanVar(value=config.get("screenshots_enabled", False))
    edsm_upload_var = tk.BooleanVar(value=config.get("edsm_upload_enabled", False))
    sq_platform_var = tk.StringVar(value=str(config.get("squadron_platform") or "PC").upper())

    if "screenshots_path" not in config:
        config["screenshots_path"] = os.path.join(os.path.expanduser("~"), "Pictures", "Frontier Developments", "Elite Dangerous")

    # Pages
    core_page = make_page("core", "Core", "Journal and screenshot paths.")
    overlay_page = make_page("overlays", "Overlays", "Runtime modules and display timing.")
    integrations_page = make_page("integrations", "Integrations", "EDSM, fleet carrier Discord, and squadron lookup.")

    nav_button("core", "Core")
    nav_button("overlays", "Overlays")
    nav_button("integrations", "Integrations")

    core_paths = section(core_page, "Paths")
    j_e = input_row(core_paths, "Journal Path", "journal_path")
    ss_e = input_row(core_paths, "Screenshot Folder", "screenshots_path")

    core_shots = section(core_page, "Screenshots")
    toggle_row(core_shots, "Convert BMP screenshots to PNG", ss_var)

    overlay_modules = section(overlay_page, "Modules")
    toggle_row(overlay_modules, "Tactical Overlay", ov_var)
    toggle_row(overlay_modules, "Cargo Manifest Overlay", cargo_var)
    toggle_row(overlay_modules, "Fleet Carrier Overlay", carrier_overlay_var)
    toggle_row(overlay_modules, "Colony Shopping Overlay", colony_var)
    toggle_row(overlay_modules, "Prospector Result Overlay", prosp_var)
    toggle_row(overlay_modules, "System Info Overlay", sysinfo_var)

    overlay_timing = section(overlay_page, "Timing")
    prosp_timeout_e = input_row(overlay_timing, "Prospector Auto-Hide", "prospector_hud_timeout_s")
    sysinfo_timeout_e = input_row(overlay_timing, "System Info Auto-Hide", "system_info_timeout_s")

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

    squadron_section = section(integrations_page, "Squadron")
    sq_tag_e = input_row(squadron_section, "Squadron Tag", "squadron_lookup_tag")
    option_row(squadron_section, "Platform", sq_platform_var, ("PC", "XBOX", "PS4"))

    def _test_squadron():
        import threading
        from squadron_window import fetch_squadron_info
        tag = sq_tag_e.get().strip()
        platform = sq_platform_var.get().strip().upper() or "PC"
        if not tag:
            tk.messagebox.showwarning("Missing tag", "Enter a Squadron Tag first.", parent=win)
            return

        def _do_test():
            result = fetch_squadron_info(tag, platform)
            if result.get("ok"):
                win.after(0, lambda: tk.messagebox.showinfo("Squadron Lookup", "Squadron info loaded successfully.", parent=win))
            else:
                msg = result.get("error") or f"HTTP {result.get('status')}"
                win.after(0, lambda: tk.messagebox.showwarning("Squadron Lookup", msg, parent=win))

        threading.Thread(target=_do_test, daemon=True).start()

    squadron_actions = row(squadron_section)
    action_button(squadron_actions, "Test Squadron Lookup", _test_squadron).pack(side=tk.LEFT)

    def remove_deprecated_keys():
        for key in DEPRECATED_CONFIG_KEYS:
            config.pop(key, None)

    def save_config():
        config.update({
            "journal_path": j_e.get().strip(),
            "overlay_enabled": ov_var.get(),
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
            "screenshots_enabled": ss_var.get(),
            "screenshots_path": ss_e.get().strip(),
            "carrier_discord_webhook_url": fc_wh_e.get().strip(),
            "squadron_lookup_tag": sq_tag_e.get().strip(),
            "squadron_platform": sq_platform_var.get().strip().upper() or "PC",
            "edsm_cmdr_name": edsm_cmdr_e.get().strip(),
            "edsm_api_key": edsm_key_e.get().strip(),
            "edsm_upload_enabled": edsm_upload_var.get(),
            "settings_geometry": win.geometry(),
        })
        save_active_profile_config(config)
        remove_deprecated_keys()
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        on_save_callback()
        win.destroy()

    def close_window():
        config["settings_geometry"] = win.geometry()
        save_active_profile_config(config)
        remove_deprecated_keys()
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        win.destroy()

    action_button(footer, "Cancel", close_window, muted=True).pack(side=tk.LEFT)
    action_button(footer, "Save Settings", save_config, accent=True).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

    win.protocol("WM_DELETE_WINDOW", close_window)
    show_page("core")
