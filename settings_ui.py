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
UI_SMALL = ("Segoe UI", 8)


def open_settings(root, config, on_save_callback, carrier_tracker=None):
    win = tk.Toplevel(root)
    win.title("SYSTEM CONFIGURATION")
    win.geometry(config.get("settings_geometry", "1120x720"))
    win.minsize(920, 620)
    win.configure(bg=UI_BG)
    win.attributes("-topmost", True)

    shell = tk.Frame(win, bg=UI_BG)
    shell.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

    header = tk.Frame(shell, bg="#0c1014", height=54)
    header.pack(fill=tk.X)
    header.pack_propagate(False)
    tk.Label(header, text="SYSTEM CONFIGURATION", font=("Segoe UI", 15, "bold"), fg=COLOR_ACCENT, bg="#0c1014").pack(side=tk.LEFT, padx=14)
    tk.Label(header, text="COMMANDER PROFILE SETTINGS", font=("Segoe UI", 8, "bold"), fg=UI_MUTED, bg="#0c1014").pack(side=tk.RIGHT, padx=14)

    body_wrap = tk.Frame(shell, bg=UI_BG)
    body_wrap.pack(fill=tk.BOTH, expand=True, pady=(12, 12))
    body_canvas = tk.Canvas(body_wrap, bg=UI_BG, highlightthickness=0, bd=0)
    body_scroll = tk.Scrollbar(body_wrap, orient=tk.VERTICAL, command=body_canvas.yview)
    body_canvas.configure(yscrollcommand=body_scroll.set)
    body_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    body_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    body = tk.Frame(body_canvas, bg=UI_BG)
    body_window = body_canvas.create_window((0, 0), window=body, anchor="nw")

    def _sync_scroll_region(_event=None):
        body_canvas.configure(scrollregion=body_canvas.bbox("all"))

    def _sync_body_width(event):
        body_canvas.itemconfigure(body_window, width=event.width)

    def _mousewheel(event):
        body_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    body.bind("<Configure>", _sync_scroll_region)
    body_canvas.bind("<Configure>", _sync_body_width)
    body_canvas.bind_all("<MouseWheel>", _mousewheel)
    for col in range(3):
        body.grid_columnconfigure(col, weight=1, uniform="settings_cols")

    footer = tk.Frame(shell, bg=UI_BG)
    footer.pack(side=tk.BOTTOM, fill=tk.X)

    def panel(parent, title):
        frame = tk.Frame(parent, bg=UI_PANEL, highlightbackground=UI_BORDER, highlightthickness=1, bd=0)
        tk.Label(frame, text=title, font=UI_FONT_BOLD, fg=COLOR_ORANGE, bg=UI_PANEL, anchor="w").pack(fill=tk.X, padx=10, pady=(8, 2))
        return frame

    def place_panel(frame, row, col):
        frame.grid(row=row, column=col, sticky="new", padx=5, pady=5)
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
        wrap.pack(fill=tk.X, padx=10, pady=(4, 7))
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
        entry.pack(fill=tk.X, pady=(2, 0), ipady=4)
        return entry

    def create_toggle(parent, label, variable):
        row = tk.Frame(parent, bg=UI_PANEL)
        row.pack(fill=tk.X, padx=10, pady=(5, 0))
        tk.Label(row, text=label, font=UI_SMALL, fg=COLOR_TEXT, bg=UI_PANEL, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn = tk.Button(row, font=("Segoe UI", 8, "bold"), relief=tk.FLAT, bd=0, width=8, cursor="hand2")

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

    sec_paths = place_panel(panel(body, "PATHS"), 0, 0)
    j_e = create_input(sec_paths, "Journal Path (leave empty to auto-detect)", "journal_path")

    sec_modules = place_panel(panel(body, "MODULES"), 1, 0)

    ov_var = tk.BooleanVar(value=config.get("overlay_enabled", True))
    cargo_var = tk.BooleanVar(value=config.get("cargo_overlay_enabled", False))
    carrier_overlay_var = tk.BooleanVar(value=config.get("carrier_overlay_enabled", False))
    colony_var = tk.BooleanVar(value=config.get("colony_overlay_enabled", False))
    prosp_var = tk.BooleanVar(value=config.get("prospector_overlay_enabled", True))
    sysinfo_var = tk.BooleanVar(value=config.get("system_info_enabled", True))
    create_toggle(sec_modules, "Tactical Overlay", ov_var)
    create_toggle(sec_modules, "Cargo Manifest Overlay", cargo_var)
    create_toggle(sec_modules, "Fleet Carrier Overlay", carrier_overlay_var)
    create_toggle(sec_modules, "Colony Shopping Overlay", colony_var)
    create_toggle(sec_modules, "Prospector Result Overlay", prosp_var)
    create_toggle(sec_modules, "System Info Overlay", sysinfo_var)
    tk.Frame(sec_modules, bg=UI_PANEL, height=6).pack(fill=tk.X)

    sec_timing = place_panel(panel(body, "OVERLAY TIMING"), 2, 0)
    prosp_timeout_e = create_input(sec_timing, "Prospector Auto-Hide (seconds)", "prospector_hud_timeout_s")
    sysinfo_timeout_e = create_input(sec_timing, "System Info Auto-Hide (seconds)", "system_info_timeout_s")

    sec_ss = place_panel(panel(body, "SCREENSHOTS"), 0, 1)
    ss_var = tk.BooleanVar(value=config.get("screenshots_enabled", False))
    create_toggle(sec_ss, "Convert BMP to PNG", ss_var)

    if "screenshots_path" not in config:
        config["screenshots_path"] = os.path.join(os.path.expanduser("~"), "Pictures", "Frontier Developments", "Elite Dangerous")
    ss_e = create_input(sec_ss, "Watch Folder", "screenshots_path")

    sec_fc = place_panel(panel(body, "FLEET CARRIER"), 1, 1)
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
    btn_row_fc.pack(fill=tk.X, padx=10, pady=(0, 8))
    action_button(btn_row_fc, "Send Test Message", _test_discord).pack(side=tk.LEFT)
    tk.Frame(sec_fc, bg=UI_PANEL, height=2).pack(fill=tk.X)

    sec_sq = place_panel(panel(body, "SQUADRON"), 2, 1)
    sq_tag_e = create_input(sec_sq, "Squadron Tag", "squadron_lookup_tag")
    tk.Label(sec_sq, text="Platform", fg=UI_MUTED, bg=UI_PANEL, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(2, 0))
    sq_platform_var = tk.StringVar(value=str(config.get("squadron_platform") or "PC").upper())
    sq_platform_menu = tk.OptionMenu(sec_sq, sq_platform_var, "PC", "XBOX", "PS4")
    sq_platform_menu.config(
        bg=UI_PANEL_2,
        fg=COLOR_TEXT,
        activebackground=UI_PANEL_2,
        activeforeground=COLOR_ACCENT,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        font=("Segoe UI", 9),
    )
    sq_platform_menu["menu"].config(bg=UI_PANEL_2, fg=COLOR_TEXT)
    sq_platform_menu.pack(fill=tk.X, padx=10, pady=(2, 8))

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

    btn_row_sq = tk.Frame(sec_sq, bg=UI_PANEL)
    btn_row_sq.pack(fill=tk.X, padx=10, pady=(0, 8))
    action_button(btn_row_sq, "Test Squadron Lookup", _test_squadron).pack(side=tk.LEFT)
    tk.Frame(sec_sq, bg=UI_PANEL, height=2).pack(fill=tk.X)

    sec_edsm = place_panel(panel(body, "EDSM UPLOAD"), 0, 2)
    edsm_cmdr_e = create_input(sec_edsm, "Commander Name", "edsm_cmdr_name")
    edsm_key_e = create_input(sec_edsm, "API Key", "edsm_api_key", is_password=True)
    edsm_upload_var = tk.BooleanVar(value=config.get("edsm_upload_enabled", False))
    create_toggle(sec_edsm, "Upload scan data to EDSM", edsm_upload_var)

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
                    params={
                        "commanderName": cmdr,
                        "apiKey": key,
                    },
                    headers={
                        "Accept": "application/json",
                        "User-Agent": f"VoidCompass/{APP_VERSION}",
                    },
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
                    win.after(0, lambda: tk.messagebox.showinfo(
                        "EDSM Test",
                        "Commander/API key accepted, but EDSM has no rank data stored yet.",
                        parent=win,
                    ))
                else:
                    win.after(0, lambda: tk.messagebox.showwarning("EDSM Test", f"EDSM response [{msgnum}]: {msg}", parent=win))
            except Exception as e:
                win.after(0, lambda: tk.messagebox.showerror("EDSM Test", f"Request failed: {e}", parent=win))
        threading.Thread(target=_do_test, daemon=True).start()

    btn_row_edsm = tk.Frame(sec_edsm, bg=UI_PANEL)
    btn_row_edsm.pack(fill=tk.X, padx=10, pady=(4, 8))
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

    def _cleanup_scroll_binding():
        try:
            body_canvas.unbind_all("<MouseWheel>")
        except Exception:
            pass

    action_button(footer, "Cancel", close_window, muted=True).pack(side=tk.LEFT)
    action_button(footer, "Save Settings", save_config, accent=True).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

    win.protocol("WM_DELETE_WINDOW", close_window)
    win.bind("<Destroy>", lambda _e: _cleanup_scroll_binding() if _e.widget == win else None)
