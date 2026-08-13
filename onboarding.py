"""Small first-run setup for the packaged public release."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog

from onboarding_splash import FirstRunBoot
from ui_theme import THEME, apply_window, button
from version import APP_VERSION


def should_show(config):
    return not bool((config or {}).get("onboarding_complete", False))


def show_first_run(root, config, on_complete, *, standalone=False):
    journal_var = tk.StringVar(master=root, value=str(config.get("journal_path") or ""))
    adaptive_var = tk.BooleanVar(master=root, value=bool(config.get("adaptive_command_enabled", True)))
    overlays_var = tk.BooleanVar(master=root, value=bool(config.get("overlay_enabled", True)))
    passthrough_var = tk.BooleanVar(master=root, value=bool(config.get("overlay_mouse_passthrough", True)))

    win = tk.Toplevel(root)
    win.title("VOID COMPASS // FIRST RUN")
    if not standalone:
        win.transient(root)
    else:
        # The real dashboard root is deliberately withdrawn during bootstrap.
        # Keeping this Toplevel non-transient allows it to be the only mapped
        # application window on a genuine first run.
        win.attributes("-topmost", True)
        win.overrideredirect(True)
    win.grab_set()
    apply_window(win)

    try:
        requested_scale = float(config.get("ui_scale_percent", 100) or 100) / 100.0
    except (TypeError, ValueError):
        requested_scale = 1.0
    scale = max(1.0, min(1.35, requested_scale))
    base_width, base_height = (900, 590) if standalone else (840, 570)
    window_width, window_height = round(base_width * scale), round(base_height * scale)
    screen_width = max(800, win.winfo_screenwidth())
    screen_height = max(600, win.winfo_screenheight())
    window_width = min(window_width, screen_width - 40)
    window_height = min(window_height, screen_height - 70)
    x = max(0, (screen_width - window_width) // 2)
    y = max(0, (screen_height - window_height) // 2)
    win.geometry(f"{window_width}x{window_height}+{x}+{y}")
    win.minsize(min(780, window_width), min(530, window_height))

    shell = tk.Frame(
        win, bg=THEME.bg, highlightbackground=THEME.accent,
        highlightthickness=1 if standalone else 0,
    )
    shell.pack(fill=tk.BOTH, expand=True)
    drag_origin = {"x": 0, "y": 0}

    if standalone:
        chrome = tk.Frame(shell, bg=THEME.header, height=34)
        chrome.pack(fill=tk.X)
        chrome.pack_propagate(False)
        tk.Label(
            chrome, text=f"VOID COMPASS  //  FIRST COMMISSIONING  //  v{APP_VERSION}",
            bg=THEME.header, fg=THEME.muted,
            font=("Cascadia Mono", 7, "bold"), anchor="w",
        ).pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=11)
        close_btn = tk.Button(
            chrome, text="×", command=lambda: abort_first_run(), bg=THEME.header,
            fg=THEME.muted, activebackground=THEME.red,
            activeforeground=THEME.text, relief=tk.FLAT, bd=0,
            font=("Segoe UI", 11, "bold"), width=4, cursor="hand2",
        )
        close_btn.pack(side=tk.RIGHT, fill=tk.Y)

        def begin_drag(event):
            drag_origin["x"] = event.x_root - win.winfo_x()
            drag_origin["y"] = event.y_root - win.winfo_y()

        def drag_window(event):
            win.geometry(
                f"+{event.x_root - drag_origin['x']}+{event.y_root - drag_origin['y']}"
            )

        for widget in (chrome, *chrome.winfo_children()[:-1]):
            widget.bind("<ButtonPress-1>", begin_drag, add="+")
            widget.bind("<B1-Motion>", drag_window, add="+")

    stage = tk.Frame(shell, bg=THEME.bg)
    stage.pack(fill=tk.BOTH, expand=True)
    state = {"boot": None, "finished": False}

    def finish():
        if state["finished"]:
            return
        state["finished"] = True
        boot = state.get("boot")
        if boot is not None:
            boot.stop()
        config.update({
            "journal_path": journal_var.get().strip(),
            "adaptive_command_enabled": adaptive_var.get(),
            "overlay_enabled": overlays_var.get(),
            "overlay_mouse_passthrough": passthrough_var.get(),
            "onboarding_complete": True,
        })
        try:
            win.grab_release()
        except tk.TclError:
            pass
        win.destroy()
        on_complete()

    def abort_first_run():
        """Treat closing mandatory commissioning as an application exit."""
        if state["finished"]:
            return
        state["finished"] = True
        boot = state.get("boot")
        if boot is not None:
            boot.stop()
        try:
            win.grab_release()
        except tk.TclError:
            pass
        try:
            win.destroy()
        except tk.TclError:
            pass

    def show_setup():
        boot = state.get("boot")
        if boot is not None:
            boot.stop()
            state["boot"] = None
        for child in stage.winfo_children():
            child.destroy()

        body = tk.Frame(stage, bg=THEME.bg)
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        hero = tk.Frame(
            body, bg=THEME.header, width=278,
            highlightbackground=THEME.border, highlightthickness=1,
        )
        hero.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 14))
        hero.pack_propagate(False)
        tk.Label(
            hero, text="VOID\nCOMPASS", bg=THEME.header, fg=THEME.accent,
            font=("Bahnschrift SemiCondensed", 25, "bold"),
            justify=tk.LEFT, anchor="w",
        ).pack(fill=tk.X, padx=18, pady=(21, 0))
        tk.Label(
            hero, text="EXPLORATION FLIGHT SYSTEM", bg=THEME.header,
            fg=THEME.orange, font=("Cascadia Mono", 7, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=19, pady=(2, 19))
        tk.Frame(hero, bg=THEME.accent, height=2).pack(fill=tk.X, padx=18)
        tk.Label(
            hero,
            text=(
                "Connect your commander journal, commission the flight deck "
                "and begin with a safe local-first configuration."
            ),
            bg=THEME.header, fg=THEME.text, font=("Segoe UI", 9),
            justify=tk.LEFT, wraplength=230, anchor="nw",
        ).pack(fill=tk.X, padx=18, pady=(18, 22))
        for number, heading, detail in (
            ("01", "JOURNAL LINK", "Live Frontier telemetry"),
            ("02", "SURVEY DECK", "Exploration intelligence"),
            ("03", "NATIVE OVERLAYS", "Profile-aware flight HUDs"),
        ):
            row = tk.Frame(hero, bg=THEME.header)
            row.pack(fill=tk.X, padx=18, pady=5)
            tk.Label(
                row, text=number, bg=THEME.panel_raised, fg=THEME.accent,
                font=("Cascadia Mono", 8, "bold"), width=3, pady=5,
            ).pack(side=tk.LEFT)
            text = tk.Frame(row, bg=THEME.header)
            text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(9, 0))
            tk.Label(
                text, text=heading, bg=THEME.header, fg=THEME.text,
                font=("Segoe UI", 8, "bold"), anchor="w",
            ).pack(fill=tk.X)
            tk.Label(
                text, text=detail, bg=THEME.header, fg=THEME.dim,
                font=("Segoe UI", 7), anchor="w",
            ).pack(fill=tk.X)
        tk.Label(
            hero, text="LOCAL-FIRST  //  NO ACCOUNT REQUIRED",
            bg=THEME.header, fg=THEME.green,
            font=("Cascadia Mono", 7, "bold"), anchor="w",
        ).pack(side=tk.BOTTOM, fill=tk.X, padx=18, pady=18)

        setup = tk.Frame(body, bg=THEME.bg)
        setup.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(
            setup, text="COMMANDER SETUP", bg=THEME.bg, fg=THEME.accent,
            font=("Bahnschrift SemiCondensed", 18, "bold"), anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            setup,
            text="Everything selected here remains editable from Settings.",
            bg=THEME.bg, fg=THEME.muted, font=("Segoe UI", 9), anchor="w",
        ).pack(fill=tk.X, pady=(2, 13))

        panel = tk.Frame(
            setup, bg=THEME.panel,
            highlightbackground=THEME.border, highlightthickness=1,
        )
        panel.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            panel, text="ELITE DANGEROUS JOURNAL FOLDER", bg=THEME.panel,
            fg=THEME.orange, font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=14, pady=(13, 4))
        tk.Label(
            panel, text="Void Compass reads Frontier's local journal files; it never modifies them.",
            bg=THEME.panel, fg=THEME.muted, font=("Segoe UI", 8), anchor="w",
        ).pack(fill=tk.X, padx=14, pady=(0, 7))
        path_row = tk.Frame(panel, bg=THEME.panel)
        path_row.pack(fill=tk.X, padx=14, pady=(0, 13))
        entry = tk.Entry(
            path_row, textvariable=journal_var, bg=THEME.input, fg=THEME.text,
            insertbackground=THEME.accent, relief=tk.FLAT,
            highlightbackground=THEME.border, highlightcolor=THEME.accent,
            highlightthickness=1, font=("Cascadia Mono", 8),
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)

        def browse_journal():
            selected = filedialog.askdirectory(parent=win)
            if selected:
                journal_var.set(selected)

        button(path_row, "BROWSE", browse_journal).pack(side=tk.LEFT, padx=(7, 0))

        tk.Frame(panel, bg=THEME.border_soft, height=1).pack(fill=tk.X, padx=14)
        tk.Label(
            panel, text="INITIAL FLIGHT DECK", bg=THEME.panel,
            fg=THEME.orange, font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=14, pady=(13, 5))
        for text, variable in (
            ("Adaptive Command Deck and activity modes", adaptive_var),
            ("Native navigation and safety overlays", overlays_var),
            (
                "Mouse passthrough while playing"
                if os.name == "nt" else
                "Mouse passthrough (Windows only; Linux overlays remain interactive)",
                passthrough_var,
            ),
        ):
            tk.Checkbutton(
                panel, text=text, variable=variable, bg=THEME.panel,
                fg=THEME.text, selectcolor=THEME.input,
                activebackground=THEME.panel, activeforeground=THEME.accent,
                anchor="w", highlightthickness=0,
            ).pack(fill=tk.X, padx=14, pady=4)
        tk.Label(
            panel,
            text=(
                "No account or cloud database is required. Network integrations "
                "remain disabled until you configure them."
            ),
            bg=THEME.panel, fg=THEME.muted, font=("Segoe UI", 8),
            wraplength=460, justify=tk.LEFT, anchor="w",
        ).pack(fill=tk.X, padx=14, pady=(10, 13))

        footer = tk.Frame(setup, bg=THEME.bg)
        footer.pack(fill=tk.X, pady=(13, 0))
        tk.Label(
            footer, text="READY FOR FIRST FLIGHT", bg=THEME.bg,
            fg=THEME.green, font=("Cascadia Mono", 7, "bold"),
        ).pack(side=tk.LEFT, pady=8)
        start = button(footer, "START VOID COMPASS", finish, accent=True, padx=16, pady=8)
        start.pack(side=tk.RIGHT)
        win.bind("<Return>", lambda _event: finish(), add="+")
        entry.focus_set()

    win.protocol("WM_DELETE_WINDOW", abort_first_run if standalone else finish)
    if standalone:
        state["boot"] = FirstRunBoot(
            stage, show_setup,
            reduced_motion=bool(config.get("reduced_motion_enabled", False)),
        )
    else:
        show_setup()
    win.update_idletasks()
    win.lift()
    win.focus_force()
    return win
