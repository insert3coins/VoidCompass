"""Small first-run setup for the packaged public release."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog

from ui_theme import THEME, apply_window, button


def should_show(config):
    return not bool((config or {}).get("onboarding_complete", False))


def show_first_run(root, config, on_complete, *, standalone=False):
    win = tk.Toplevel(root)
    win.title("VOID COMPASS // FIRST RUN")
    win.geometry("620x480")
    win.minsize(560, 430)
    if not standalone:
        win.transient(root)
    else:
        # The real dashboard root is deliberately withdrawn during bootstrap.
        # Keeping this Toplevel non-transient allows it to be the only mapped
        # application window on a genuine first run.
        win.attributes("-topmost", True)
    win.grab_set()
    apply_window(win)

    body = tk.Frame(win, bg=THEME.bg)
    body.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)
    tk.Label(body, text="WELCOME TO VOID COMPASS", bg=THEME.bg, fg=THEME.accent,
             font=("Bahnschrift SemiCondensed", 18, "bold"), anchor="w").pack(fill=tk.X)
    tk.Label(body, text="Connect the live journal and choose a safe starting configuration. Everything remains editable in Settings.",
             bg=THEME.bg, fg=THEME.text, font=("Segoe UI", 9), justify=tk.LEFT,
             wraplength=560, anchor="w").pack(fill=tk.X, pady=(5, 16))

    panel = tk.Frame(body, bg=THEME.panel, highlightbackground=THEME.border, highlightthickness=1)
    panel.pack(fill=tk.X)
    tk.Label(panel, text="ELITE JOURNAL FOLDER", bg=THEME.panel, fg=THEME.orange,
             font=("Segoe UI", 8, "bold"), anchor="w").pack(fill=tk.X, padx=12, pady=(10, 4))
    path_row = tk.Frame(panel, bg=THEME.panel)
    path_row.pack(fill=tk.X, padx=12, pady=(0, 10))
    journal_var = tk.StringVar(value=str(config.get("journal_path") or ""))
    entry = tk.Entry(path_row, textvariable=journal_var, bg=THEME.input, fg=THEME.text,
                     insertbackground=THEME.accent, relief=tk.FLAT)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
    button(path_row, "BROWSE", lambda: journal_var.set(filedialog.askdirectory(parent=win) or journal_var.get())).pack(side=tk.LEFT, padx=(7, 0))

    adaptive_var = tk.BooleanVar(value=bool(config.get("adaptive_command_enabled", True)))
    overlays_var = tk.BooleanVar(value=bool(config.get("overlay_enabled", True)))
    passthrough_var = tk.BooleanVar(value=bool(config.get("overlay_mouse_passthrough", True)))
    voice_var = tk.BooleanVar(value=bool(config.get("voice_callouts_enabled", False)))
    for text, variable in (
        ("Adaptive Command Deck and activity modes", adaptive_var),
        ("Native navigation and safety overlays", overlays_var),
        (
            "Mouse passthrough while playing"
            if os.name == "nt" else
            "Mouse passthrough (Windows only; Linux overlays remain interactive)",
            passthrough_var,
        ),
        ("Voice callouts (uses the configured local Piper voice)", voice_var),
    ):
        tk.Checkbutton(panel, text=text, variable=variable, bg=THEME.panel, fg=THEME.text,
                       selectcolor=THEME.input, activebackground=THEME.panel,
                       activeforeground=THEME.accent, anchor="w").pack(fill=tk.X, padx=12, pady=4)
    tk.Label(panel, text="No account or cloud database is required. Network integrations remain off until configured.",
             bg=THEME.panel, fg=THEME.muted, font=("Segoe UI", 8),
             wraplength=540, justify=tk.LEFT, anchor="w").pack(fill=tk.X, padx=12, pady=(9, 12))

    def finish():
        config.update({
            "journal_path": journal_var.get().strip(),
            "adaptive_command_enabled": adaptive_var.get(),
            "overlay_enabled": overlays_var.get(),
            "overlay_mouse_passthrough": passthrough_var.get(),
            "voice_callouts_enabled": voice_var.get(),
            "onboarding_complete": True,
        })
        try:
            win.grab_release()
        except tk.TclError:
            pass
        win.destroy()
        on_complete()

    footer = tk.Frame(body, bg=THEME.bg)
    footer.pack(side=tk.BOTTOM, fill=tk.X, pady=(14, 0))
    button(footer, "START VOID COMPASS", finish, accent=True).pack(side=tk.RIGHT)
    win.protocol("WM_DELETE_WINDOW", finish)
    if standalone:
        win.update_idletasks()
        x = max(0, (win.winfo_screenwidth() - win.winfo_width()) // 2)
        y = max(0, (win.winfo_screenheight() - win.winfo_height()) // 2)
        win.geometry(f"+{x}+{y}")
        win.lift()
        win.focus_force()
    return win
