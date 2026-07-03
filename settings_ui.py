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
UI_MONO = ("Consolas", 9)


def open_settings(root, config, on_save_callback, carrier_tracker=None):
    win = tk.Toplevel(root)
    win.title("SYSTEM CONFIGURATION")
    win.geometry(config.get("settings_geometry", "720x620"))
    win.minsize(620, 520)
    win.configure(bg=UI_BG)
    win.attributes("-topmost", True)

    shell = tk.Frame(win, bg=UI_BG)
    shell.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

    header = tk.Frame(shell, bg="#0c1014", height=64)
    header.pack(fill=tk.X)
    header.pack_propagate(False)
    tk.Label(header, text="SYSTEM CONFIGURATION", font=("Segoe UI", 15, "bold"), fg=COLOR_ACCENT, bg="#0c1014").pack(anchor="w", padx=14, pady=(10, 0))
    tk.Label(header, text="LOCAL CONTROL SURFACE", font=("Segoe UI", 8, "bold"), fg=UI_MUTED, bg="#0c1014").pack(anchor="w", padx=14)

    body = tk.Frame(shell, bg=UI_BG)
    body.pack(fill=tk.BOTH, expand=True, pady=(12, 12))

    footer = tk.Frame(shell, bg=UI_BG)
    footer.pack(side=tk.BOTTOM, fill=tk.X)

    def panel(parent, title):
        frame = tk.Frame(parent, bg=UI_PANEL, highlightbackground=UI_BORDER, highlightthickness=1, bd=0)
        frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(frame, text=title, font=UI_FONT_BOLD, fg=COLOR_ORANGE, bg=UI_PANEL, anchor="w").pack(fill=tk.X, padx=12, pady=(10, 2))
        return frame

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

    def create_input(parent, label, key, is_password=False):
        wrap = tk.Frame(parent, bg=UI_PANEL)
        wrap.pack(fill=tk.X, padx=12, pady=(6, 10))
        tk.Label(wrap, text=label, font=("Segoe UI", 8, "bold"), fg=UI_MUTED, bg=UI_PANEL, anchor="w").pack(fill=tk.X)
        entry = tk.Entry(
            wrap,
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
        entry.pack(fill=tk.X, pady=(3, 0), ipady=5)
        return entry

    def create_toggle(parent, label, variable):
        row = tk.Frame(parent, bg=UI_PANEL)
        row.pack(fill=tk.X, padx=12, pady=(8, 0))
        tk.Label(row, text=label, font=UI_FONT, fg=COLOR_TEXT, bg=UI_PANEL, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn = tk.Button(row, font=UI_FONT_BOLD, relief=tk.FLAT, bd=0, width=10, cursor="hand2")

        def refresh():
            if variable.get():
                btn.config(text="Enabled", bg=COLOR_ACCENT, fg="black", activebackground=COLOR_ACCENT, activeforeground="black")
            else:
                btn.config(text="Disabled", bg=UI_PANEL_2, fg=UI_MUTED, activebackground=UI_PANEL_2, activeforeground=COLOR_TEXT)

        def toggle():
            variable.set(not variable.get())
            refresh()

        btn.config(command=toggle)
        btn.pack(side=tk.RIGHT)
        refresh()
        return btn

    sec_gen = panel(body, "GENERAL")
    j_e = create_input(sec_gen, "Journal Path (leave empty to auto-detect)", "journal_path")

    ov_var = tk.BooleanVar(value=config.get("overlay_enabled", True))
    cargo_var = tk.BooleanVar(value=config.get("cargo_overlay_enabled", False))
    carrier_overlay_var = tk.BooleanVar(value=config.get("carrier_overlay_enabled", False))
    colony_var = tk.BooleanVar(value=config.get("colony_overlay_enabled", False))
    prosp_var = tk.BooleanVar(value=config.get("prospector_overlay_enabled", True))
    sysinfo_var = tk.BooleanVar(value=config.get("system_info_enabled", True))
    create_toggle(sec_gen, "Tactical Overlay", ov_var)
    create_toggle(sec_gen, "Cargo Manifest Overlay", cargo_var)
    create_toggle(sec_gen, "Fleet Carrier Overlay", carrier_overlay_var)
    create_toggle(sec_gen, "Colony Shopping Overlay", colony_var)
    create_toggle(sec_gen, "Prospector Result Overlay", prosp_var)
    prosp_timeout_e = create_input(sec_gen, "Prospector Overlay Auto-Hide (seconds)  —  60 = 1 min  ·  120 = 2 min  ·  300 = 5 min", "prospector_hud_timeout_s")
    create_toggle(sec_gen, "System Info Overlay  (shows on jump arrival)", sysinfo_var)
    sysinfo_timeout_e = create_input(sec_gen, "System Info Auto-Hide (seconds)  —  15 = quick  ·  30 = default  ·  60 = slow", "system_info_timeout_s")
    tk.Frame(sec_gen, bg=UI_PANEL, height=10).pack(fill=tk.X)

    sec_ss = panel(body, "SCREENSHOTS")
    ss_var = tk.BooleanVar(value=config.get("screenshots_enabled", False))
    create_toggle(sec_ss, "Convert BMP to PNG", ss_var)

    if "screenshots_path" not in config:
        config["screenshots_path"] = os.path.join(os.path.expanduser("~"), "Pictures", "Frontier Developments", "Elite Dangerous")
    ss_e = create_input(sec_ss, "Watch Folder", "screenshots_path")

    sec_fc = panel(body, "FLEET CARRIER")
    fc_wh_e = create_input(sec_fc, "Discord Webhook URL  (leave empty to disable notifications)", "carrier_discord_webhook_url")

    def _test_discord():
        url = fc_wh_e.get().strip()
        if not url:
            tk.messagebox.showwarning("No URL", "Enter a webhook URL first.", parent=win)
            return
        if carrier_tracker is not None:
            import threading
            threading.Thread(target=carrier_tracker.send_test_discord, args=(url,), daemon=True).start()
            tk.messagebox.showinfo("Test Sent", "Test message dispatched — check your Discord channel.", parent=win)
        else:
            tk.messagebox.showinfo("Not Available", "Carrier tracker not connected; save and reopen settings.", parent=win)

    btn_row_fc = tk.Frame(sec_fc, bg=UI_PANEL)
    btn_row_fc.pack(fill=tk.X, padx=12, pady=(0, 10))
    action_button(btn_row_fc, "Send Test Message", _test_discord).pack(side=tk.LEFT)
    tk.Frame(sec_fc, bg=UI_PANEL, height=2).pack(fill=tk.X)

    sec_edsm = panel(body, "EDSM UPLOAD")
    edsm_cmdr_e = create_input(sec_edsm, "Commander Name", "edsm_cmdr_name")
    edsm_key_e = create_input(sec_edsm, "API Key", "edsm_api_key", is_password=True)
    edsm_upload_var = tk.BooleanVar(value=config.get("edsm_upload_enabled", False))
    create_toggle(sec_edsm, "Upload scan data to EDSM", edsm_upload_var)

    def _test_edsm():
        import threading, requests as _req, time
        cmdr = edsm_cmdr_e.get().strip()
        key = edsm_key_e.get().strip()
        game_version = str(config.get("edsm_game_version") or "").strip()
        game_build = str(config.get("edsm_game_build") or "").strip()
        if not cmdr or not key:
            tk.messagebox.showwarning("Missing credentials", "Enter Commander Name and API Key first.", parent=win)
            return
        if not game_version or not game_build:
            tk.messagebox.showwarning(
                "Game version unavailable",
                "Start Elite and let VoidCompass read a FileHeader or LoadGame event before testing EDSM.",
                parent=win,
            )
            return
        def _do_test():
            try:
                from version import APP_VERSION
                probe_event = {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "event": "Status",
                }
                r = _req.post(
                    "https://www.edsm.net/api-journal-v1",
                    json={
                        "commanderName": cmdr,
                        "apiKey": key,
                        "fromSoftware": "VoidCompass",
                        "fromSoftwareVersion": APP_VERSION,
                        "fromGameVersion": game_version,
                        "fromGameBuild": game_build,
                        "message": [probe_event],
                    },
                    timeout=10,
                )
                body_text = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
                if isinstance(body_text, dict) and body_text.get("msgnum") in (100, 304):
                    win.after(0, lambda: tk.messagebox.showinfo("EDSM Test", "API key verified successfully.", parent=win))
                else:
                    msg = body_text.get("msg", str(body_text)) if isinstance(body_text, dict) else str(body_text)
                    win.after(0, lambda: tk.messagebox.showwarning("EDSM Test", f"EDSM response: {msg}", parent=win))
            except Exception as e:
                win.after(0, lambda: tk.messagebox.showerror("EDSM Test", f"Request failed: {e}", parent=win))
        threading.Thread(target=_do_test, daemon=True).start()

    btn_row_edsm = tk.Frame(sec_edsm, bg=UI_PANEL)
    btn_row_edsm.pack(fill=tk.X, padx=12, pady=(6, 10))
    action_button(btn_row_edsm, "Test API Key", _test_edsm).pack(side=tk.LEFT)
    tk.Frame(sec_edsm, bg=UI_PANEL, height=2).pack(fill=tk.X)

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
