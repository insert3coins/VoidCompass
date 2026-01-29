import tkinter as tk
import json
from tkinter import messagebox
from config import CONFIG_FILE, COLOR_BG, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT

def open_settings(root, config, on_save_callback):
    win = tk.Toplevel(root)
    win.title("SYSTEM CONFIG")
    win.geometry(config.get("settings_geometry", "550x700"))
    win.configure(bg=COLOR_BG)
    win.attributes("-topmost", True)
    
    tk.Label(win, text="Data Link Configuration", font=("Courier", 14, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG).pack(pady=20)
    
    def create_entry(label, key):
        tk.Label(win, text=f"// {label}", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_BG).pack(anchor="w", padx=25, pady=(10, 0))
        e = tk.Entry(win, width=50, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT)
        e.insert(0, str(config.get(key, "")))
        e.pack(padx=20, pady=5)
        return e

    j_e = create_entry("Journal Path", "journal_path")
    d_e = create_entry("Discord Webhook", "discord_webhook")
    n_e = create_entry("EDSM Commander Name", "edsm_cmdr_name")
    k_e = create_entry("EDSM API Key", "edsm_api_key")
    
    ov_var = tk.BooleanVar(value=config.get("overlay_enabled", True))
    tk.Checkbutton(win, text="Enable Overlay", variable=ov_var, bg=COLOR_BG, fg=COLOR_ACCENT).pack(pady=20)

    def save():
        config.update({
            "journal_path": j_e.get(),
            "discord_webhook": d_e.get(),
            "edsm_cmdr_name": n_e.get(),
            "edsm_api_key": k_e.get(),
            "overlay_enabled": ov_var.get(),
            "settings_geometry": win.geometry()
        })
        with open(CONFIG_FILE, 'w') as f: json.dump(config, f, indent=4)
        
        on_save_callback()
        
        messagebox.showinfo("Saved", "Configuration Saved. Please restart app.")
        win.destroy()

    def on_close():
        config["settings_geometry"] = win.geometry()
        with open(CONFIG_FILE, 'w') as f: json.dump(config, f, indent=4)
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_close)
    tk.Button(win, text="[ SAVE CHANGES ]", command=save, bg=COLOR_ACCENT, fg="black", font=("Courier", 12, "bold")).pack(pady=20)