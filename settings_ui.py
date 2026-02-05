import tkinter as tk
import os
import json
from config import CONFIG_FILE, COLOR_BG, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT

def open_settings(root, config, on_save_callback):
    win = tk.Toplevel(root)
    win.title("SYSTEM CONFIGURATION")
    win.geometry(config.get("settings_geometry", "600x900"))
    win.configure(bg=COLOR_BG)
    win.attributes("-topmost", True)
    
    # Main container with padding
    container = tk.Frame(win, bg=COLOR_BG)
    container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Header
    tk.Label(container, text=" // SYSTEM CONFIGURATION", font=("Courier", 16, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG).pack(anchor="w", pady=(0, 20))
    
    # Footer Buttons Frame (Packed early to ensure visibility)
    btn_frame = tk.Frame(container, bg=COLOR_BG)
    btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

    # --- Helper Functions ---
    def create_section(parent, title):
        frame = tk.LabelFrame(parent, text=f" {title} ", font=("Courier", 10, "bold"), fg=COLOR_ORANGE, bg=COLOR_BG, bd=1, relief=tk.SOLID)
        frame.pack(fill=tk.X, pady=10, ipady=5)
        return frame

    def create_input(parent, label, key, is_password=False):
        f = tk.Frame(parent, bg=COLOR_BG)
        f.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(f, text=label, font=("Courier", 9), fg="#888", bg=COLOR_BG).pack(anchor="w")
        
        e = tk.Entry(f, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT, highlightthickness=1, highlightbackground="#333", highlightcolor=COLOR_ACCENT)
        if is_password:
            e.config(show="*")
        e.insert(0, str(config.get(key, "")))
        e.pack(fill=tk.X, pady=(2, 0), ipady=4)
        return e

    # --- General Settings ---
    sec_gen = create_section(container, "GENERAL")
    j_e = create_input(sec_gen, "Journal Path (Leave empty to auto-detect)", "journal_path")
    
    # Custom Toggle for Overlay
    toggle_frame = tk.Frame(sec_gen, bg=COLOR_BG)
    toggle_frame.pack(fill=tk.X, padx=15, pady=10)
    
    tk.Label(toggle_frame, text="Tactical Overlay", font=("Courier", 9), fg="#888", bg=COLOR_BG).pack(side=tk.LEFT)
    
    ov_var = tk.BooleanVar(value=config.get("overlay_enabled", True))
    
    def toggle_overlay():
        ov_var.set(not ov_var.get())
        update_toggle_visuals()
        
    def update_toggle_visuals():
        if ov_var.get():
            toggle_btn.config(text="[ ENABLED ]", fg=COLOR_ACCENT)
        else:
            toggle_btn.config(text="[ DISABLED ]", fg="#555")

    toggle_btn = tk.Button(toggle_frame, text="[ ENABLED ]", font=("Courier", 9, "bold"), bg=COLOR_BG, activebackground=COLOR_BG, bd=0, command=toggle_overlay, cursor="hand2")
    toggle_btn.pack(side=tk.RIGHT)
    update_toggle_visuals()
    
    # Custom Toggle for Cargo Overlay
    cargo_frame = tk.Frame(sec_gen, bg=COLOR_BG)
    cargo_frame.pack(fill=tk.X, padx=15, pady=(0, 10))
    
    tk.Label(cargo_frame, text="Cargo Manifest Overlay", font=("Courier", 9), fg="#888", bg=COLOR_BG).pack(side=tk.LEFT)
    
    cargo_var = tk.BooleanVar(value=config.get("cargo_overlay_enabled", False))
    
    def toggle_cargo():
        cargo_var.set(not cargo_var.get())
        update_cargo_visuals()
        
    def update_cargo_visuals():
        if cargo_var.get():
            cargo_btn.config(text="[ ENABLED ]", fg=COLOR_ACCENT)
        else:
            cargo_btn.config(text="[ DISABLED ]", fg="#555")

    cargo_btn = tk.Button(cargo_frame, text="[ DISABLED ]", font=("Courier", 9, "bold"), bg=COLOR_BG, activebackground=COLOR_BG, bd=0, command=toggle_cargo, cursor="hand2")
    cargo_btn.pack(side=tk.RIGHT)
    update_cargo_visuals()

    # Custom Toggle for Scan Overlay
    scan_frame = tk.Frame(sec_gen, bg=COLOR_BG)
    scan_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

    tk.Label(scan_frame, text="Scan Results Overlay", font=("Courier", 9), fg="#888", bg=COLOR_BG).pack(side=tk.LEFT)

    scan_var = tk.BooleanVar(value=config.get("scan_overlay_enabled", True))

    def toggle_scan():
        scan_var.set(not scan_var.get())
        update_scan_visuals()

    def update_scan_visuals():
        if scan_var.get():
            scan_btn.config(text="[ ENABLED ]", fg=COLOR_ACCENT)
        else:
            scan_btn.config(text="[ DISABLED ]", fg="#555")

    scan_btn = tk.Button(scan_frame, text="[ ENABLED ]", font=("Courier", 9, "bold"), bg=COLOR_BG, activebackground=COLOR_BG, bd=0, command=toggle_scan, cursor="hand2")
    scan_btn.pack(side=tk.RIGHT)
    update_scan_visuals()

    # --- EDSM Settings ---
    sec_edsm = create_section(container, "EDSM UPLINK")
    
    # Toggle EDSM
    edsm_toggle_frame = tk.Frame(sec_edsm, bg=COLOR_BG)
    edsm_toggle_frame.pack(fill=tk.X, padx=15, pady=(5, 5))
    tk.Label(edsm_toggle_frame, text="Enable EDSM Integration", font=("Courier", 9), fg="#888", bg=COLOR_BG).pack(side=tk.LEFT)
    
    edsm_var = tk.BooleanVar(value=config.get("edsm_enabled", True))
    
    def toggle_edsm():
        edsm_var.set(not edsm_var.get())
        update_edsm_visuals()
        
    def update_edsm_visuals():
        if edsm_var.get():
            edsm_btn.config(text="[ ENABLED ]", fg=COLOR_ACCENT)
        else:
            edsm_btn.config(text="[ DISABLED ]", fg="#555")

    edsm_btn = tk.Button(edsm_toggle_frame, text="[ ENABLED ]", font=("Courier", 9, "bold"), bg=COLOR_BG, activebackground=COLOR_BG, bd=0, command=toggle_edsm, cursor="hand2")
    edsm_btn.pack(side=tk.RIGHT)
    update_edsm_visuals()

    n_e = create_input(sec_edsm, "Commander Name", "edsm_cmdr_name")
    k_e = create_input(sec_edsm, "API Key", "edsm_api_key", is_password=True)

    # --- Discord Settings ---
    sec_disc = create_section(container, "DISCORD TELEMETRY")
    
    # Toggle Discord
    disc_toggle_frame = tk.Frame(sec_disc, bg=COLOR_BG)
    disc_toggle_frame.pack(fill=tk.X, padx=15, pady=(5, 5))
    tk.Label(disc_toggle_frame, text="Enable Discord Integration", font=("Courier", 9), fg="#888", bg=COLOR_BG).pack(side=tk.LEFT)
    
    disc_var = tk.BooleanVar(value=config.get("discord_enabled", True))
    
    def toggle_disc():
        disc_var.set(not disc_var.get())
        update_disc_visuals()
        
    def update_disc_visuals():
        if disc_var.get():
            disc_btn.config(text="[ ENABLED ]", fg=COLOR_ACCENT)
        else:
            disc_btn.config(text="[ DISABLED ]", fg="#555")

    disc_btn = tk.Button(disc_toggle_frame, text="[ ENABLED ]", font=("Courier", 9, "bold"), bg=COLOR_BG, activebackground=COLOR_BG, bd=0, command=toggle_disc, cursor="hand2")
    disc_btn.pack(side=tk.RIGHT)
    update_disc_visuals()

    d_e = create_input(sec_disc, "Webhook URL", "discord_webhook")

    # --- Screenshot Settings ---
    sec_ss = create_section(container, "SCREENSHOTS")
    
    ss_toggle_frame = tk.Frame(sec_ss, bg=COLOR_BG)
    ss_toggle_frame.pack(fill=tk.X, padx=15, pady=(5, 5))
    tk.Label(ss_toggle_frame, text="Convert BMP to PNG", font=("Courier", 9), fg="#888", bg=COLOR_BG).pack(side=tk.LEFT)
    
    ss_var = tk.BooleanVar(value=config.get("screenshots_enabled", False))
    
    def toggle_ss():
        ss_var.set(not ss_var.get())
        update_ss_visuals()
        
    def update_ss_visuals():
        if ss_var.get():
            ss_btn.config(text="[ ENABLED ]", fg=COLOR_ACCENT)
        else:
            ss_btn.config(text="[ DISABLED ]", fg="#555")

    ss_btn = tk.Button(ss_toggle_frame, text="[ DISABLED ]", font=("Courier", 9, "bold"), bg=COLOR_BG, activebackground=COLOR_BG, bd=0, command=toggle_ss, cursor="hand2")
    ss_btn.pack(side=tk.RIGHT)
    update_ss_visuals()

    if "screenshots_path" not in config:
        config["screenshots_path"] = os.path.join(os.path.expanduser("~"), "Pictures", "Frontier Developments", "Elite Dangerous")
    ss_e = create_input(sec_ss, "Watch Folder", "screenshots_path")

    # --- Footer Buttons ---
    # btn_frame is created at the top to ensure visibility

    def save_config():
        config.update({
            "journal_path": j_e.get().strip(),
            "discord_webhook": d_e.get().strip(),
            "edsm_cmdr_name": n_e.get().strip(),
            "edsm_api_key": k_e.get().strip(),
            "edsm_enabled": edsm_var.get(),
            "discord_enabled": disc_var.get(),
            "overlay_enabled": ov_var.get(),
            "cargo_overlay_enabled": cargo_var.get(),
            "scan_overlay_enabled": scan_var.get(),
            "screenshots_enabled": ss_var.get(),
            "screenshots_path": ss_e.get().strip(),
            "settings_geometry": win.geometry()
        })
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        
        on_save_callback()
        win.destroy()

    def close_window():
        config["settings_geometry"] = win.geometry()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        win.destroy()

    tk.Button(btn_frame, text="CANCEL", command=close_window, bg="#222", fg="#888", font=("Courier", 10, "bold"), relief=tk.FLAT, width=12).pack(side=tk.LEFT)
    tk.Button(btn_frame, text="SAVE SETTINGS", command=save_config, bg=COLOR_ACCENT, fg="black", font=("Courier", 10, "bold"), relief=tk.FLAT).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

    win.protocol("WM_DELETE_WINDOW", close_window)
