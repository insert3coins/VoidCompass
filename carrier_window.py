"""Personal/Squadron Carrier command, routing and cargo intelligence."""
import threading
import tkinter as tk
import webbrowser
from datetime import datetime, timezone
from tkinter import messagebox, ttk

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config
from ui_theme import THEME, ThemedWindowMixin, apply_window, button, scrollbar, window_surface
from trade.spansh import SpanshError, fleet_carrier_route, import_fleet_carrier_route

COLOR_ACCENT = THEME.accent
COLOR_ORANGE = THEME.orange
COLOR_TEXT = THEME.text

# Weekly upkeep rates (active_cr, paused_cr) per service — from EDCM
_SERVICE_UPKEEP = {
    "Refuel":           (1_500_000,  750_000),
    "Repair":           (1_500_000,  750_000),
    "Rearm":            (1_500_000,  750_000),
    "Shipyard":         (6_500_000, 1_800_000),
    "Outfitting":       (5_000_000, 1_500_000),
    "Exploration":      (1_850_000,  700_000),
    "VistaGenomics":    (1_500_000,  700_000),
    "PioneerSupplies":  (5_000_000, 1_500_000),
    "Bartender":        (1_750_000, 1_250_000),
    "VoucherRedemption":(1_850_000,  850_000),
    "BlackMarket":      (2_000_000, 1_250_000),
}
_BASE_UPKEEP = 5_000_000  # cr/week


def _calc_weekly_upkeep(crew):
    total = _BASE_UPKEEP
    for member in crew:
        role = member.get("CrewRole", "")
        activated = member.get("Activated", False)
        enabled = member.get("Enabled", False)
        if role in _SERVICE_UPKEEP and activated:
            active_rate, paused_rate = _SERVICE_UPKEEP[role]
            total += active_rate if enabled else paused_rate
    return total


def _fmt_cr(val):
    if val is None:
        return "—"
    try:
        return f"{int(val):,} cr"
    except Exception:
        return str(val)


def _fmt_dt(ts_str):
    if not ts_str:
        return "—"
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts_str


class CarrierWindow(ThemedWindowMixin):
    UI_FONT  = ("Segoe UI", 9)
    UI_BOLD  = ("Segoe UI", 9, "bold")
    UI_MONO  = ("Consolas", 9)
    UI_MONO_B= ("Consolas", 10, "bold")

    def __init__(self, root, config, tracker, embedded=False, specialist_engine=None):
        self.root = root
        self.config = config
        self.tracker = tracker
        self.specialist_engine = specialist_engine
        self._after_job = None
        self._route_generation = 0
        self._cargo_editor_seeded = False
        self._cargo_profile_path = None
        try:
            self._carrier_profile_path = self.tracker._state_path()
        except Exception:
            self._carrier_profile_path = None

        self.embedded = embedded
        self.win = window_surface(root, embedded=embedded)
        self.win.title("Carrier Command")
        apply_window(self.win)
        self.win.geometry(config.get("carrier_window_geometry", "900x680"))
        self.win.resizable(True, True)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        # Wire the live-update hook
        self.tracker.on_updated = self._on_tracker_updated

        self._build_ui()
        self._refresh()

    def is_open(self):
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False

    def _on_close(self):
        self._route_generation += 1
        try:
            self.config["carrier_window_geometry"] = self.win.geometry()
            save_config(self.config)
        except Exception:
            pass
        self.tracker.on_updated = None
        if self._after_job:
            try:
                self.win.after_cancel(self._after_job)
            except Exception:
                pass
        try:
            self.win.destroy()
        except Exception:
            pass

    def _on_tracker_updated(self, _data):
        if self.is_open():
            try:
                profile_path = self.tracker._state_path()
            except Exception:
                profile_path = None
            if profile_path != self._carrier_profile_path:
                self._carrier_profile_path = profile_path
                self._route_generation += 1
                self._cargo_editor_seeded = False
                for name in ("spansh_plot_btn", "spansh_import_btn"):
                    control = getattr(self, name, None)
                    if control is not None:
                        control.config(state=tk.NORMAL)
            self.win.after(0, self._refresh)

    def on_specialist_updated(self):
        """Refresh the observed cargo manifest after a SpecialistEngine delta."""
        if self.is_open():
            self.win.after(0, lambda: self._refresh_cargo(self.tracker.carrier_data))

    def on_profile_switched(self):
        """Drop transient route/cargo UI state at the commander boundary."""
        self._route_generation += 1
        self._cargo_editor_seeded = False
        self._cargo_profile_path = None
        try:
            self._carrier_profile_path = self.tracker._state_path()
        except Exception:
            self._carrier_profile_path = None
        if hasattr(self, "spansh_import_var"):
            self.spansh_import_var.set("")
        if self.is_open():
            self.win.after(0, self._refresh)

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Title bar
        hdr = tk.Frame(self.win, bg="#0c1014", height=46)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        self.title_label = tk.Label(hdr, text="CARRIER COMMAND", font=("Segoe UI", 13, "bold"),
                                    fg=COLOR_ACCENT, bg="#0c1014")
        self.title_label.pack(side=tk.LEFT, padx=14, pady=8)
        self.status_badge = tk.Label(hdr, text="IDLE", fg="black", bg=self.UI_DIM,
                                     font=("Segoe UI", 8, "bold"), padx=8, pady=3)
        self.status_badge.pack(side=tk.RIGHT, padx=14, pady=10)

        # Tab bar
        tab_bar = tk.Frame(self.win, bg="#0c1014")
        tab_bar.pack(fill=tk.X)
        self._tabs = {}
        self._tab_frames = {}
        for name in ("Overview", "Squadron", "Expedition", "Cargo", "Finance", "Services"):
            btn = button(tab_bar, name, lambda n=name: self._show_tab(n), muted=True, padx=10, pady=6)
            btn.pack(side=tk.LEFT)
            self._tabs[name] = btn

        # Tab content area
        self._tab_area = tk.Frame(self.win, bg=self.UI_BG)
        self._tab_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        self._build_overview_tab()
        self._build_squadron_tab()
        self._build_expedition_tab()
        self._build_cargo_tab()
        self._build_finance_tab()
        self._build_services_tab()
        self._show_tab("Overview")

    def _show_tab(self, name):
        for n, frame in self._tab_frames.items():
            frame.pack_forget()
            self._tabs[n].config(fg=self.UI_MUTED, bg="#0c1014")
            self._tabs[n]._theme_resting_bg = "#0c1014"
            self._tabs[n]._theme_resting_fg = self.UI_MUTED
        self._tab_frames[name].pack(fill=tk.BOTH, expand=True)
        self._tabs[name].config(fg=COLOR_TEXT, bg=self.UI_PANEL)
        self._tabs[name]._theme_resting_bg = self.UI_PANEL
        self._tabs[name]._theme_resting_fg = COLOR_TEXT

    def _section(self, parent, title):
        tk.Label(parent, text=title, font=self.UI_BOLD, fg=COLOR_ORANGE,
                 bg=self.UI_PANEL, anchor="w").pack(fill=tk.X, padx=10, pady=(10, 3))

    def _row(self, parent, label, default="—"):
        f = tk.Frame(parent, bg=self.UI_PANEL)
        f.pack(fill=tk.X, padx=10, pady=1)
        tk.Label(f, text=label, font=self.UI_MONO, fg=self.UI_MUTED,
                 bg=self.UI_PANEL, width=20, anchor="w").pack(side=tk.LEFT)
        val = tk.Label(f, text=default, font=self.UI_MONO, fg=COLOR_TEXT,
                       bg=self.UI_PANEL, anchor="w")
        val.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return val

    # ---------- Overview tab ----------
    def _build_overview_tab(self):
        f = tk.Frame(self._tab_area, bg=self.UI_PANEL,
                     highlightbackground=self.UI_BORDER, highlightthickness=1)
        self._tab_frames["Overview"] = f

        self._section(f, "IDENTITY")
        self.id_name      = self._row(f, "Name")
        self.id_callsign  = self._row(f, "Callsign")
        self.id_type      = self._row(f, "Carrier Type")
        self.id_squadron  = self._row(f, "Squadron")
        self.id_system    = self._row(f, "Location")
        self.id_body      = self._row(f, "Body")
        self.id_purchased_at   = self._row(f, "Purchased At")
        self.id_spawn_system   = self._row(f, "Purchased In")
        self.id_last_synced    = self._row(f, "Last Synced")

        # Pending decommission warning
        self.decom_warning_lbl = tk.Label(f, text="WARNING // PENDING DECOMMISSION",
                                          font=self.UI_BOLD, fg=self.UI_WARN,
                                          bg=self.UI_PANEL, anchor="w")

        self._section(f, "JUMP SCHEDULE")
        self.jmp_dest    = self._row(f, "Destination")
        self.jmp_departs = self._row(f, "Departs")
        self.jmp_prev    = self._row(f, "Previous System")

        # Copy countdown button
        self._copy_btn = button(f, "Copy <t:…:R> to clipboard", self._copy_countdown, muted=True)
        self._copy_btn.pack(anchor="w", padx=10, pady=(2, 0))

        self._section(f, "CARRIER STATS")
        self.stat_fuel       = self._row(f, "Fuel")
        self.stat_jump_curr  = self._row(f, "Jump Range (curr)")
        self.stat_jump_max   = self._row(f, "Jump Range (max)")
        self.stat_docking    = self._row(f, "Docking Access")

        self._section(f, "PLANNED DESTINATION")
        tk.Label(f, text="Shown as Destination in Discord. Leave blank to show \"TBD\".",
                 font=("Segoe UI", 8), fg=self.UI_MUTED, bg=self.UI_PANEL,
                 anchor="w", wraplength=420).pack(fill=tk.X, padx=10, pady=(0, 4))
        dest_row = tk.Frame(f, bg=self.UI_PANEL)
        dest_row.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.dest_var = tk.StringVar()
        self.dest_entry = tk.Entry(
            dest_row, textvariable=self.dest_var,
            bg="#090c10", fg=COLOR_TEXT, font=self.UI_MONO,
            insertbackground=COLOR_ACCENT,
            relief=tk.FLAT, highlightthickness=1,
            highlightbackground=self.UI_BORDER,
            highlightcolor=COLOR_ACCENT,
        )
        self.dest_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        dest_btn = button(dest_row, "SET", self._save_destination)
        dest_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.dest_entry.bind("<Return>", lambda _e: self._save_destination())

        self._section(f, "STATUS NOTE")
        tk.Label(f, text="Shown as information in Discord notifications.",
                 font=("Segoe UI", 8), fg=self.UI_MUTED, bg=self.UI_PANEL,
                 anchor="w", wraplength=420).pack(fill=tk.X, padx=10, pady=(0, 4))
        note_row = tk.Frame(f, bg=self.UI_PANEL)
        note_row.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.note_var = tk.StringVar()
        self.note_entry = tk.Entry(
            note_row, textvariable=self.note_var,
            bg="#090c10", fg=COLOR_TEXT, font=self.UI_MONO,
            insertbackground=COLOR_ACCENT,
            relief=tk.FLAT, highlightthickness=1,
            highlightbackground=self.UI_BORDER,
            highlightcolor=COLOR_ACCENT,
        )
        self.note_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        note_btn = button(note_row, "SET", self._save_note)
        note_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.note_entry.bind("<Return>", lambda _e: self._save_note())

        # Manual Discord post — departure time
        self._section(f, "MANUAL DEPARTURE TIME")
        tk.Label(f,
                 text="Optional — shown as a local time in the manual post and converted for each reader.\n"
                      "Format:  18:30  or  26/05 18:30  or  2026-05-27 20:00  (your local time)",
                 font=("Segoe UI", 8), fg=self.UI_MUTED, bg=self.UI_PANEL,
                 anchor="w", justify=tk.LEFT, wraplength=420,
                 ).pack(fill=tk.X, padx=10, pady=(0, 4))
        dep_time_row = tk.Frame(f, bg=self.UI_PANEL)
        dep_time_row.pack(fill=tk.X, padx=10, pady=(0, 6))
        self.dep_time_var = tk.StringVar()
        self.dep_time_entry = tk.Entry(
            dep_time_row, textvariable=self.dep_time_var,
            bg="#090c10", fg=COLOR_TEXT, font=self.UI_MONO,
            insertbackground=COLOR_ACCENT,
            relief=tk.FLAT, highlightthickness=1,
            highlightbackground=self.UI_BORDER,
            highlightcolor=COLOR_ACCENT,
        )
        self.dep_time_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        button(dep_time_row, "CLEAR", lambda: self.dep_time_var.set(""), muted=True, padx=8).pack(side=tk.LEFT, padx=(6, 0))

        # Post button + feedback
        post_row = tk.Frame(f, bg=self.UI_PANEL)
        post_row.pack(fill=tk.X, padx=10, pady=(2, 12))
        self.post_discord_btn = button(post_row, "POST CARRIER STATUS TO DISCORD", self._post_status_to_discord, accent=True, padx=12, pady=6)
        self.post_discord_btn.pack(side=tk.LEFT)
        self.post_discord_status_lbl = tk.Label(
            post_row, text="", font=("Segoe UI", 8),
            fg=self.UI_MUTED, bg=self.UI_PANEL,
        )
        self.post_discord_status_lbl.pack(side=tk.LEFT, padx=(10, 0))

    # ---------- Squadron tab ----------
    def _build_squadron_tab(self):
        f = tk.Frame(self._tab_area, bg=self.UI_PANEL,
                     highlightbackground=self.UI_BORDER, highlightthickness=1)
        self._tab_frames["Squadron"] = f

        self._sq_canvas = tk.Canvas(
            f, bg=self.UI_PANEL, highlightthickness=0, bd=0,
        )
        sq_scroll = scrollbar(f, orient=tk.VERTICAL, command=self._sq_canvas.yview)
        self._sq_canvas.configure(yscrollcommand=sq_scroll.set)
        self._sq_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sq_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        body = tk.Frame(self._sq_canvas, bg=self.UI_PANEL)
        body_id = self._sq_canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind(
            "<Configure>",
            lambda _event: self._sq_canvas.configure(scrollregion=self._sq_canvas.bbox("all")),
        )
        self._sq_canvas.bind(
            "<Configure>",
            lambda event: self._sq_canvas.itemconfigure(body_id, width=event.width),
        )

        self._section(body, "SQUADRON CARRIER READINESS")
        self.sq_status = tk.Label(
            body, text="AWAITING JOURNAL DATA", font=("Segoe UI", 11, "bold"),
            fg=self.UI_DIM, bg=self.UI_PANEL, anchor="w",
        )
        self.sq_status.pack(fill=tk.X, padx=10, pady=(2, 3))
        self.sq_guidance = tk.Label(
            body, text="", font=("Segoe UI", 8), fg=self.UI_MUTED,
            bg=self.UI_PANEL, anchor="w", justify=tk.LEFT, wraplength=420,
        )
        self.sq_guidance.pack(fill=tk.X, padx=10, pady=(0, 8))

        self._section(body, "IDENTITY & ACCESS")
        self.sq_type = self._row(body, "Carrier Type")
        self.sq_name = self._row(body, "Squadron")
        self.sq_rank = self._row(body, "Commander Rank")
        self.sq_carrier = self._row(body, "Carrier")
        self.sq_callsign = self._row(body, "Callsign")
        self.sq_carrier_id = self._row(body, "Carrier ID")
        self.sq_synced = self._row(body, "Last Synced")

        self._section(body, "LIVE OPERATIONS")
        self.sq_system = self._row(body, "Current System")
        self.sq_jump = self._row(body, "Next Jump")
        self.sq_fuel = self._row(body, "Tritium")
        self.sq_range = self._row(body, "Jump Range")
        self.sq_docking = self._row(body, "Docking Access")

        self._section(body, "DISCORD & EXPEDITION")
        self.sq_discord = self._row(body, "Carrier Webhook")
        tk.Label(
            body,
            text="The shared Carrier Discord webhook automatically labels Squadron Carrier notifications and includes squadron name/rank when known.",
            font=("Segoe UI", 8), fg=self.UI_MUTED, bg=self.UI_PANEL,
            anchor="w", justify=tk.LEFT, wraplength=420,
        ).pack(fill=tk.X, padx=10, pady=(2, 6))
        actions = tk.Frame(body, bg=self.UI_PANEL)
        actions.pack(fill=tk.X, padx=10, pady=(0, 12))
        self.sq_expedition_btn = button(
            actions, "OPEN EXPEDITION", lambda: self._show_tab("Expedition"), muted=True,
        )
        self.sq_expedition_btn.pack(side=tk.LEFT)
        self.sq_discord_btn = button(
            actions, "POST SQUADRON STATUS", self._post_status_to_discord, accent=True,
        )
        self.sq_discord_btn.pack(side=tk.LEFT, padx=(6, 0))
        self._bind_squadron_wheel(body)

    def _bind_squadron_wheel(self, widget):
        widget.bind("<MouseWheel>", self._scroll_squadron, add="+")
        for child in widget.winfo_children():
            self._bind_squadron_wheel(child)

    def _scroll_squadron(self, event):
        direction = -1 if event.delta > 0 else 1
        self._sq_canvas.yview_scroll(direction, "units")
        return "break"

    def _copy_countdown(self):
        dep = self.tracker.carrier_data.get("jump_departure_time")
        if not dep:
            return
        try:
            dt = datetime.fromisoformat(dep.replace("Z", "+00:00"))
            token = f"<t:{int(dt.timestamp())}:R>"
            self.win.clipboard_clear()
            self.win.clipboard_append(token)
            self.win.update()
            orig = self._copy_btn.cget("text")
            self._copy_btn.config(text=token, fg=COLOR_ACCENT)
            self.win.after(3000, lambda: self._copy_btn.config(text=orig, fg=self.UI_MUTED) if self.is_open() else None)
        except Exception:
            pass

    def _save_destination(self):
        dest = self.dest_var.get().strip()
        try:
            self.tracker.set_destination_note(dest)
        except Exception:
            pass
        self.dest_entry.config(highlightcolor=self.UI_OK, highlightbackground=self.UI_OK)
        self.win.after(1200, lambda: self.dest_entry.config(
            highlightcolor=COLOR_ACCENT, highlightbackground=self.UI_BORDER
        ) if self.is_open() else None)

    def _save_note(self):
        note = self.note_var.get().strip()
        try:
            self.tracker.set_note(note)
        except Exception:
            pass
        # Brief visual confirmation
        self.note_entry.config(highlightcolor=self.UI_OK, highlightbackground=self.UI_OK)
        self.win.after(1200, lambda: self.note_entry.config(
            highlightcolor=COLOR_ACCENT, highlightbackground=self.UI_BORDER
        ) if self.is_open() else None)

    def _build_expedition_tab(self):
        f = tk.Frame(self._tab_area, bg=self.UI_PANEL,
                     highlightbackground=self.UI_BORDER, highlightthickness=1)
        self._tab_frames["Expedition"] = f
        self._section(f, "FLEET CARRIER EXPEDITION NAVIGATOR")
        tk.Label(
            f, text=("Paste one destination per line. Spansh calculates the jumps and tritium; "
                     "select any calculated row to copy that waypoint. Journal arrivals advance the route."),
            font=("Segoe UI", 8), fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w",
        ).pack(fill=tk.X, padx=10, pady=(0, 6))
        fields = tk.Frame(f, bg=self.UI_PANEL)
        fields.pack(fill=tk.X, padx=10)
        tk.Label(fields, text="EXPEDITION", fg=self.UI_MUTED, bg=self.UI_PANEL,
                 font=("Segoe UI", 7, "bold")).pack(side=tk.LEFT)
        self.expedition_name_var = tk.StringVar()
        self.expedition_name_entry = tk.Entry(fields, textvariable=self.expedition_name_var, bg="#090c10", fg=COLOR_TEXT,
                                              insertbackground=COLOR_ACCENT, relief=tk.FLAT, width=30)
        self.expedition_name_entry.pack(side=tk.LEFT, padx=(6, 14), ipady=4)
        tk.Label(fields, text="FUEL RESERVE", fg=self.UI_MUTED, bg=self.UI_PANEL,
                 font=("Segoe UI", 7, "bold")).pack(side=tk.LEFT)
        self.expedition_reserve_var = tk.StringVar(value="200")
        self.expedition_reserve_entry = tk.Entry(
            fields, textvariable=self.expedition_reserve_var, bg="#090c10", fg=COLOR_TEXT,
            insertbackground=COLOR_ACCENT, relief=tk.FLAT, width=7,
        )
        self.expedition_reserve_entry.pack(side=tk.LEFT, padx=6, ipady=4)
        tk.Label(fields, text="T", fg=self.UI_MUTED, bg=self.UI_PANEL).pack(side=tk.LEFT)

        route_wrap = tk.Frame(f, bg="#090c10")
        route_wrap.pack(fill=tk.X, padx=10, pady=8)
        self.expedition_route_text = tk.Text(
            route_wrap, bg="#090c10", fg=COLOR_TEXT, insertbackground=COLOR_ACCENT,
            relief=tk.FLAT, bd=0, font=self.UI_MONO, wrap=tk.NONE, padx=8, pady=8, height=5,
        )
        route_scroll = scrollbar(route_wrap, orient=tk.VERTICAL, command=self.expedition_route_text.yview)
        self.expedition_route_text.configure(yscrollcommand=route_scroll.set)
        self.expedition_route_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        route_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.expedition_route_text.tag_config("visited", foreground=self.UI_DIM)
        self.expedition_route_text.tag_config("next", foreground=COLOR_ORANGE)
        self.expedition_route_text.tag_config("pending", foreground=COLOR_TEXT)

        actions = tk.Frame(f, bg=self.UI_PANEL)
        actions.pack(fill=tk.X, padx=10, pady=(0, 6))
        button(actions, "SAVE / UPDATE ROUTE", self._save_expedition, accent=True).pack(side=tk.LEFT)
        self.spansh_plot_btn = button(actions, "PLOT WITH SPANSH", self._plot_spansh_expedition)
        self.spansh_plot_btn.pack(side=tk.LEFT, padx=(6, 0))
        button(actions, "COPY NEXT", self._copy_next_expedition).pack(side=tk.LEFT, padx=(6, 0))
        button(actions, "COPY SELECTED", self._copy_selected_expedition).pack(side=tk.LEFT, padx=(6, 0))
        self.spansh_result_btn = button(actions, "OPEN RESULT", self._open_spansh_result, muted=True)
        self.spansh_result_btn.pack(side=tk.LEFT, padx=(6, 0))

        import_row = tk.Frame(f, bg=self.UI_PANEL)
        import_row.pack(fill=tk.X, padx=10, pady=(0, 6))
        tk.Label(
            import_row, text="SPANSH RESULT", fg=self.UI_MUTED, bg=self.UI_PANEL,
            font=("Segoe UI", 7, "bold"),
        ).pack(side=tk.LEFT)
        self.spansh_import_var = tk.StringVar()
        self.spansh_import_entry = tk.Entry(
            import_row, textvariable=self.spansh_import_var,
            bg="#090c10", fg=COLOR_TEXT, insertbackground=COLOR_ACCENT,
            relief=tk.FLAT, highlightthickness=1,
            highlightbackground=self.UI_BORDER, highlightcolor=COLOR_ACCENT,
        )
        self.spansh_import_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6, ipady=4)
        self.spansh_import_btn = button(
            import_row, "IMPORT URL / JOB", self._import_spansh_expedition, muted=True,
        )
        self.spansh_import_btn.pack(side=tk.LEFT)
        self.spansh_import_entry.bind("<Return>", lambda _event: self._import_spansh_expedition())

        self.expedition_status = tk.Label(
            f, text="", fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Consolas", 8), anchor="w",
        )
        self.expedition_status.pack(fill=tk.X, padx=10, pady=(0, 5))

        tree_wrap = tk.Frame(f, bg=self.UI_PANEL)
        tree_wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))
        columns = ("stop", "system", "jump", "fuel", "tank", "restock")
        self.expedition_tree = ttk.Treeview(tree_wrap, columns=columns, show="headings", height=8)
        headings = {
            "stop": ("#", 42, "center"), "system": ("System", 260, "w"),
            "jump": ("Jump", 80, "e"), "fuel": ("Fuel", 75, "e"),
            "tank": ("Tank after", 85, "e"), "restock": ("Restock", 95, "e"),
        }
        for key, (label, width, anchor) in headings.items():
            self.expedition_tree.heading(key, text=label)
            self.expedition_tree.column(key, width=width, minwidth=35, anchor=anchor,
                                        stretch=key == "system")
        tree_y = scrollbar(tree_wrap, orient=tk.VERTICAL, command=self.expedition_tree.yview)
        self.expedition_tree.configure(yscrollcommand=tree_y.set)
        self.expedition_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.expedition_summary = tk.Label(
            f, text="", fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Consolas", 8), anchor="w",
        )
        self.expedition_summary.pack(fill=tk.X, padx=10, pady=(0, 8))

    def _route_systems_from_editor(self):
        systems = []
        for line in self.expedition_route_text.get("1.0", tk.END).splitlines():
            value = line.strip()
            if value.startswith(("✓", "→", "·")):
                value = value[1:].strip()
            if value:
                systems.append(value)
        return systems

    def _save_expedition(self):
        self.tracker.set_expedition(
            self.expedition_name_var.get(), self._route_systems_from_editor(),
            self.expedition_reserve_var.get(),
        )
        self.expedition_status.config(text="MANUAL · route saved", fg=self.UI_OK)

    def _plot_spansh_expedition(self):
        cd = self.tracker.carrier_data
        source = str(cd.get("system") or "").strip()
        destinations = self._route_systems_from_editor()
        if not source:
            self.expedition_status.config(
                text="Open Carrier Management or wait for CarrierLocation so the source system is known.",
                fg=self.UI_WARN,
            )
            return
        destinations = [row for row in destinations if row.casefold() != source.casefold()]
        if not destinations:
            self.expedition_status.config(text="Add at least one destination system.", fg=self.UI_WARN)
            return
        total, free = cd.get("space_total"), cd.get("space_free")
        used = max(0, int(total) - int(free)) if total is not None and free is not None else 0
        source_id64 = cd.get("system_address")
        carrier_type = cd.get("carrier_type") or "fleet"
        try:
            profile_path = self.tracker._state_path()
        except Exception:
            profile_path = None
        self._route_generation += 1
        generation = self._route_generation
        self.spansh_plot_btn.config(state=tk.DISABLED)
        self.expedition_status.config(text="SPANSH · resolving systems and calculating carrier jumps…", fg=COLOR_ACCENT)

        def worker():
            try:
                result = fleet_carrier_route(
                    source, destinations, source_id64=source_id64,
                    used_capacity=used, carrier_type=carrier_type,
                    calculate_starting_fuel=True,
                )
                error = None
            except Exception as exc:
                result, error = None, exc
            try:
                self.win.after(
                    0, lambda: self._finish_spansh_plot(
                        generation, profile_path, result, error, "plotted",
                    ),
                )
            except Exception:
                pass

        threading.Thread(target=worker, name="SpanshCarrierRoute", daemon=True).start()

    def _import_spansh_expedition(self):
        reference = self.spansh_import_var.get().strip()
        if not reference:
            self.expedition_status.config(
                text="Paste a Spansh Fleet Carrier results URL or job id.", fg=self.UI_WARN,
            )
            return
        try:
            profile_path = self.tracker._state_path()
        except Exception:
            profile_path = None
        self._route_generation += 1
        generation = self._route_generation
        self.spansh_plot_btn.config(state=tk.DISABLED)
        self.spansh_import_btn.config(state=tk.DISABLED)
        self.expedition_status.config(text="SPANSH · importing completed carrier route…", fg=COLOR_ACCENT)

        def worker():
            try:
                result, error = import_fleet_carrier_route(reference), None
            except Exception as exc:
                result, error = None, exc
            try:
                self.win.after(
                    0, lambda: self._finish_spansh_plot(
                        generation, profile_path, result, error, "imported",
                    ),
                )
            except Exception:
                pass

        threading.Thread(target=worker, name="SpanshCarrierImport", daemon=True).start()

    def _finish_spansh_plot(self, generation, profile_path, result, error, action="plotted"):
        try:
            current_profile_path = self.tracker._state_path()
        except Exception:
            current_profile_path = None
        if (generation != self._route_generation or profile_path != current_profile_path
                or not self.is_open()):
            return
        self.spansh_plot_btn.config(state=tk.NORMAL)
        self.spansh_import_btn.config(state=tk.NORMAL)
        if error:
            detail = str(error) if isinstance(error, SpanshError) else f"Unexpected route error: {error}"
            self.expedition_status.config(text=f"SPANSH · {detail}", fg=self.UI_FAIL)
            return
        self.tracker.set_spansh_expedition(
            self.expedition_name_var.get() or "Carrier Route", result,
            self.expedition_reserve_var.get(),
        )
        self.expedition_status.config(
            text=(f"SPANSH · {len(result.get('jumps') or []) - 1:,} jumps · "
                  f"{result.get('total_distance_ly') or 0:,.1f} LY · "
                  f"{result.get('fuel_required_t') or 0:,} T · {action}"),
            fg=self.UI_OK,
        )
        self.spansh_import_var.set(result.get("url") or "")
        self._refresh()

    def _next_expedition_system(self):
        for row in self.tracker.carrier_data.get("expedition_route") or []:
            if isinstance(row, dict) and not row.get("visited"):
                return row.get("system")
        return None

    def _copy_next_expedition(self):
        system = self._next_expedition_system()
        if system:
            self.win.clipboard_clear()
            self.win.clipboard_append(system)
            self.expedition_status.config(text=f"COPIED NEXT · {system}", fg=self.UI_OK)

    def _copy_selected_expedition(self):
        selected = self.expedition_tree.selection()
        if not selected:
            self.expedition_status.config(
                text="Select a route row, then use COPY SELECTED.", fg=self.UI_WARN,
            )
            return
        values = self.expedition_tree.item(selected[0], "values") or ()
        system = str(values[1] if len(values) > 1 else "").strip()
        if not system or system == "—":
            return
        self.win.clipboard_clear()
        self.win.clipboard_append(system)
        self.expedition_status.config(text=f"COPIED WAYPOINT · {system}", fg=self.UI_OK)

    def _open_spansh_result(self):
        url = self.tracker.carrier_data.get("expedition_spansh_url")
        webbrowser.open(url or "https://spansh.co.uk/fleet-carrier")

    def _refresh_expedition(self, cd):
        try:
            focused = self.win.focus_get() == self.expedition_route_text
        except Exception:
            focused = False
        route = cd.get("expedition_route") or []
        editor_route = (
            cd.get("expedition_requested_destinations") or route
            if cd.get("expedition_route_source") == "spansh" else route
        )
        if not focused:
            self.expedition_route_text.delete("1.0", tk.END)
            next_written = False
            for row in editor_route:
                if isinstance(row, str):
                    row = {"system": row}
                if not isinstance(row, dict):
                    continue
                if row.get("visited"):
                    marker, tag = "✓", "visited"
                elif not next_written:
                    marker, tag, next_written = "→", "next", True
                else:
                    marker, tag = "·", "pending"
                self.expedition_route_text.insert(tk.END, f"{marker} {row.get('system') or ''}\n", tag)
        if self.win.focus_get() != self.expedition_name_entry:
            self.expedition_name_var.set(cd.get("expedition_name") or "")
        if self.win.focus_get() != self.expedition_reserve_entry:
            self.expedition_reserve_var.set(str(cd.get("expedition_reserve_fuel") or 0))
        done = sum(1 for row in route if isinstance(row, dict) and row.get("visited"))
        remaining = max(0, len(route) - done)
        for item in self.expedition_tree.get_children():
            self.expedition_tree.delete(item)
        for index, row in enumerate(route, start=1):
            if not isinstance(row, dict):
                continue
            visited = bool(row.get("visited"))
            marker = "✓" if visited else "→" if index == done + 1 else str(index)
            distance = row.get("distance_ly")
            fuel_used = row.get("fuel_used_t")
            fuel_left = row.get("fuel_remaining_t")
            restock = row.get("restock_t")
            self.expedition_tree.insert("", tk.END, values=(
                marker, row.get("system") or "—",
                f"{float(distance):,.1f} LY" if distance is not None else "—",
                f"{int(fuel_used):,} T" if fuel_used is not None else "—",
                f"{int(fuel_left):,} T" if fuel_left is not None else "—",
                f"{int(restock):,} T" if restock else ("REQUIRED" if row.get("must_restock") else "—"),
            ))
        fuel = cd.get("fuel_level")
        reserve = int(cd.get("expedition_reserve_fuel") or 0)
        fuel_text = "fuel unknown" if fuel is None else f"{max(0, int(fuel) - reserve):,} T above reserve"
        source = str(cd.get("expedition_route_source") or "manual").upper()
        self.expedition_summary.config(
            text=f"{source} · {done}/{len(route)} stops · {remaining * 20} min nominal · {fuel_text}"
        )
        result_url = cd.get("expedition_spansh_url")
        self.spansh_result_btn.config(
            state=tk.NORMAL, text="OPEN RESULT" if result_url else "OPEN SPANSH",
        )
        try:
            import_focused = self.win.focus_get() == self.spansh_import_entry
        except Exception:
            import_focused = False
        if not import_focused:
            desired_result = result_url or ""
            if self.spansh_import_var.get() != desired_result:
                self.spansh_import_var.set(desired_result)
        if result_url and not self.expedition_status.cget("text"):
            self.expedition_status.config(
                text=f"SPANSH route saved · plotted {_fmt_dt(cd.get('expedition_plotted_at'))}", fg=self.UI_MUTED,
            )

    # ---------- Cargo tab ----------
    def _build_cargo_tab(self):
        f = tk.Frame(self._tab_area, bg=self.UI_PANEL,
                     highlightbackground=self.UI_BORDER, highlightthickness=1)
        self._tab_frames["Cargo"] = f
        self._section(f, "CARRIER CARGO INTELLIGENCE")
        self.cargo_totals = tk.Label(
            f, text="", font=("Consolas", 10, "bold"), fg=COLOR_ACCENT,
            bg=self.UI_PANEL, anchor="w",
        )
        self.cargo_totals.pack(fill=tk.X, padx=10, pady=(1, 2))
        self.cargo_evidence = tk.Label(
            f, text=("CarrierStats supplies the exact total cargo usage, but not a commodity manifest. "
                     "The rows below are your saved baseline plus transfers observed while docked at your own carrier."),
            font=("Segoe UI", 8), fg=self.UI_MUTED, bg=self.UI_PANEL,
            anchor="w", justify=tk.LEFT, wraplength=820,
        )
        self.cargo_evidence.pack(fill=tk.X, padx=10, pady=(0, 7))

        manifest_wrap = tk.Frame(f, bg=self.UI_PANEL)
        manifest_wrap.pack(fill=tk.BOTH, expand=True, padx=10)
        self.cargo_tree = ttk.Treeview(
            manifest_wrap, columns=("commodity", "tonnes"), show="headings", height=7,
        )
        self.cargo_tree.heading("commodity", text="Observed commodity")
        self.cargo_tree.heading("tonnes", text="Tonnes")
        self.cargo_tree.column("commodity", width=360, anchor="w", stretch=True)
        self.cargo_tree.column("tonnes", width=100, anchor="e", stretch=False)
        cargo_y = scrollbar(manifest_wrap, orient=tk.VERTICAL, command=self.cargo_tree.yview)
        self.cargo_tree.configure(yscrollcommand=cargo_y.set)
        self.cargo_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cargo_y.pack(side=tk.RIGHT, fill=tk.Y)

        self._section(f, "MANIFEST BASELINE")
        tk.Label(
            f, text="Use Commodity | tonnes. Save a fresh baseline after checking the carrier inventory in game.",
            font=("Segoe UI", 8), fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w",
        ).pack(fill=tk.X, padx=10, pady=(0, 3))
        editor_wrap = tk.Frame(f, bg="#090c10")
        editor_wrap.pack(fill=tk.X, padx=10)
        self.cargo_manifest_text = tk.Text(
            editor_wrap, height=4, bg="#090c10", fg=COLOR_TEXT,
            insertbackground=COLOR_ACCENT, relief=tk.FLAT, bd=0,
            font=self.UI_MONO, wrap=tk.NONE, padx=8, pady=6,
        )
        manifest_y = scrollbar(editor_wrap, orient=tk.VERTICAL, command=self.cargo_manifest_text.yview)
        self.cargo_manifest_text.configure(yscrollcommand=manifest_y.set)
        self.cargo_manifest_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        manifest_y.pack(side=tk.RIGHT, fill=tk.Y)
        cargo_actions = tk.Frame(f, bg=self.UI_PANEL)
        cargo_actions.pack(fill=tk.X, padx=10, pady=(6, 3))
        self.cargo_save_btn = button(cargo_actions, "SAVE MANIFEST BASELINE", self._save_cargo_manifest, accent=True)
        self.cargo_save_btn.pack(side=tk.LEFT)
        self.cargo_status = tk.Label(
            cargo_actions, text="", fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Consolas", 8), anchor="w",
        )
        self.cargo_status.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)

        self._section(f, "ACTIVE CARRIER MARKET ORDERS")
        order_wrap = tk.Frame(f, bg=self.UI_PANEL)
        order_wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        self.cargo_order_tree = ttk.Treeview(
            order_wrap, columns=("commodity", "side", "quantity", "price"), show="headings", height=4,
        )
        for key, label, width, anchor in (
            ("commodity", "Commodity", 280, "w"), ("side", "Order", 80, "center"),
            ("quantity", "Quantity", 100, "e"), ("price", "Price", 130, "e"),
        ):
            self.cargo_order_tree.heading(key, text=label)
            self.cargo_order_tree.column(key, width=width, anchor=anchor, stretch=key == "commodity")
        self.cargo_order_tree.pack(fill=tk.BOTH, expand=True)
        if self.specialist_engine is None:
            self.cargo_save_btn.config(state=tk.DISABLED)

    @staticmethod
    def _parse_cargo_manifest(text):
        rows = []
        for index, raw in enumerate(text.splitlines(), start=1):
            if not raw.strip():
                continue
            normalized = raw.replace("\t", "|")
            if "|" in normalized:
                fields = [value.strip() for value in normalized.split("|")]
            elif "," in normalized:
                fields = [value.strip() for value in normalized.split(",", 1)]
            else:
                fields = [normalized.strip()]
            if len(fields) < 2 or not fields[0]:
                raise ValueError(f"Manifest line {index}: use Commodity | tonnes")
            try:
                count = int(float(fields[-1].replace(",", "")))
            except ValueError as exc:
                raise ValueError(f"Manifest line {index}: invalid tonnes") from exc
            if count < 0:
                raise ValueError(f"Manifest line {index}: tonnes cannot be negative")
            name = " | ".join(fields[:-1])
            rows.append({"name": name, "symbol": name.lower().replace(" ", "_"), "count": count})
        return rows

    def _save_cargo_manifest(self):
        if self.specialist_engine is None:
            return
        try:
            rows = self._parse_cargo_manifest(self.cargo_manifest_text.get("1.0", tk.END))
            self.specialist_engine.set_carrier_inventory(rows, source="commander manifest baseline")
            self._cargo_editor_seeded = True
            self._refresh_cargo(self.tracker.carrier_data)
            self.cargo_status.config(text="BASELINE SAVED · future own-carrier transfers update it", fg=self.UI_OK)
        except Exception as exc:
            messagebox.showerror("Carrier manifest", str(exc), parent=self.win)

    def _refresh_cargo(self, cd):
        workflow = {}
        if self.specialist_engine is not None:
            try:
                profile_path = getattr(self.specialist_engine, "path", None)
                if profile_path != self._cargo_profile_path:
                    self._cargo_profile_path = profile_path
                    self._cargo_editor_seeded = False
                snapshot = getattr(self.specialist_engine, "carrier_snapshot", None)
                workflow = (snapshot(cd) if callable(snapshot)
                            else self.specialist_engine.snapshot(cd).get("carrier")) or {}
            except Exception:
                workflow = {}
        inventory = workflow.get("inventory") or {}
        rows = sorted(inventory.values(), key=lambda row: (-int(row.get("count") or 0), row.get("name") or ""))
        for item in self.cargo_tree.get_children():
            self.cargo_tree.delete(item)
        for row in rows:
            self.cargo_tree.insert("", tk.END, values=(row.get("name") or row.get("symbol") or "—",
                                                        f"{int(row.get('count') or 0):,}"))
        listed = sum(int(row.get("count") or 0) for row in rows)
        exact = cd.get("space_cargo")
        free = cd.get("space_free")
        reserved = cd.get("space_reserved")
        exact_text = "unknown" if exact is None else f"{int(exact):,} T"
        remainder = None if exact is None else int(exact) - listed
        comparison = (
            "manifest awaits baseline" if not rows
            else f"{remainder:,} T not itemised" if remainder is not None and remainder >= 0
            else f"manifest exceeds snapshot by {abs(remainder):,} T" if remainder is not None
            else "no aggregate snapshot"
        )
        self.cargo_totals.config(
            text=(f"JOURNAL CARGO {exact_text}   ·   MANIFEST {listed:,} T   ·   {comparison.upper()}   ·   "
                  f"FREE {int(free):,} T" if free is not None else
                  f"JOURNAL CARGO {exact_text}   ·   MANIFEST {listed:,} T   ·   {comparison.upper()}")
        )
        source = workflow.get("inventory_source") or "no manifest baseline"
        total_source = cd.get("cargo_total_source") or (
            "CarrierStats snapshot" if exact is not None else "CarrierStats not received"
        )
        reserve_text = f" · reserved {int(reserved):,} T" if reserved is not None else ""
        self.cargo_status.config(
            text=(f"{source}{reserve_text} · total: {total_source} "
                  f"{_fmt_dt(cd.get('cargo_updated_at') or cd.get('stats_updated_at'))}"),
            fg=self.UI_MUTED,
        )
        if not self._cargo_editor_seeded:
            self.cargo_manifest_text.delete("1.0", tk.END)
            for row in sorted(rows, key=lambda value: value.get("name") or ""):
                self.cargo_manifest_text.insert(
                    tk.END, f"{row.get('name') or row.get('symbol')} | {int(row.get('count') or 0)}\n"
                )
            self._cargo_editor_seeded = True
        for item in self.cargo_order_tree.get_children():
            self.cargo_order_tree.delete(item)
        orders = ((workflow.get("orders") or {}).get("items") or [])
        for row in orders:
            self.cargo_order_tree.insert("", tk.END, values=(
                row.get("name") or "—", str(row.get("side") or "—").upper(),
                f"{int(row.get('quantity') or 0):,}", f"{int(row.get('price_cr') or 0):,} cr",
            ))

    @staticmethod
    def _parse_departure_time(text):
        """Parse a user-typed local time string into a UTC Unix timestamp.

        Accepted formats (all treated as local time):
          18:30          → today at 18:30
          18:30:00       → today at 18:30:00
          26/05 18:30    → 26 May this year at 18:30
          26/05/2026 18:30
          2026-05-26 18:30
        Returns int Unix timestamp, or raises ValueError with a helpful message.
        """
        import re
        from datetime import datetime
        text = text.strip()
        now = datetime.now()
        dt = None

        # Try formats in order of specificity
        for fmt in (
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
            "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
        ):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                pass

        if dt is None:
            # DD/MM HH:MM — assume current year
            m = re.fullmatch(r"(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
            if m:
                day, mon, hh, mm, ss = m.groups()
                dt = datetime(now.year, int(mon), int(day), int(hh), int(mm), int(ss or 0))

        if dt is None:
            # HH:MM or HH:MM:SS — assume today
            m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
            if m:
                hh, mm, ss = m.groups()
                dt = datetime(now.year, now.month, now.day, int(hh), int(mm), int(ss or 0))

        if dt is None:
            raise ValueError(f"Unrecognised format: {text!r}")

        # Convert local → UTC unix timestamp
        import time as _time
        return int(_time.mktime(dt.timetuple()))

    def _post_status_to_discord(self):
        dep_ts = None
        raw_time = self.dep_time_var.get().strip()
        if raw_time:
            try:
                dep_ts = self._parse_departure_time(raw_time)
            except ValueError as exc:
                self.post_discord_status_lbl.config(
                    text=f"ERROR: Bad time: {exc}", fg=self.UI_FAIL)
                self.win.after(5000, lambda: self.post_discord_status_lbl.config(
                    text="") if self.is_open() else None)
                return

        ok, err = self.tracker.send_status_update(departure_ts=dep_ts)
        if ok:
            self.post_discord_status_lbl.config(text="SENT", fg=self.UI_OK)
        else:
            msg = err or "No webhook URL set in Configuration."
            self.post_discord_status_lbl.config(text=f"ERROR: {msg}", fg=self.UI_FAIL)
        self.win.after(4000, lambda: self.post_discord_status_lbl.config(
            text="") if self.is_open() else None)

    # ---------- Finance tab ----------
    def _build_finance_tab(self):
        f = tk.Frame(self._tab_area, bg=self.UI_PANEL,
                     highlightbackground=self.UI_BORDER, highlightthickness=1)
        self._tab_frames["Finance"] = f

        self._section(f, "BALANCE")
        self.fin_balance   = self._row(f, "Total Balance")
        self.fin_available = self._row(f, "Available")
        self.fin_reserve   = self._row(f, "Reserve")
        self.fin_reserve_pct = self._row(f, "Reserve %")

        self._section(f, "TAXES")
        self.fin_tax_refuel = self._row(f, "Refuel Tax")
        self.fin_tax_rearm  = self._row(f, "Rearm Tax")
        self.fin_tax_repair = self._row(f, "Repair Tax")

        self._section(f, "STORAGE")
        self.spc_total   = self._row(f, "Total Capacity")
        self.spc_free    = self._row(f, "Free Space")
        self.spc_cargo   = self._row(f, "Cargo")
        self.spc_crew    = self._row(f, "Crew Services")
        self.spc_reserved= self._row(f, "Reserved")
        self.spc_ships   = self._row(f, "Ship Packs")
        self.spc_modules = self._row(f, "Module Packs")

        self._section(f, "UPKEEP ESTIMATE")
        self.upkeep_base     = self._row(f, "Base (weekly)")
        self.upkeep_services = self._row(f, "Services (weekly)")
        self.upkeep_total    = self._row(f, "Total (weekly)")
        self.upkeep_funded   = self._row(f, "Funded For")

    # ---------- Services tab ----------
    def _build_services_tab(self):
        f = tk.Frame(self._tab_area, bg=self.UI_PANEL,
                     highlightbackground=self.UI_BORDER, highlightthickness=1)
        self._tab_frames["Services"] = f

        self._section(f, "ACTIVE SERVICES")
        self._svc_rows = {}
        display_roles = [
            "Refuel", "Repair", "Rearm", "Outfitting", "Shipyard",
            "Exploration", "VistaGenomics", "PioneerSupplies",
            "Bartender", "VoucherRedemption", "BlackMarket",
        ]
        for role in display_roles:
            row = tk.Frame(f, bg=self.UI_PANEL)
            row.pack(fill=tk.X, padx=10, pady=2)
            dot = tk.Label(row, text="●", font=self.UI_MONO, fg=self.UI_DIM,
                           bg=self.UI_PANEL, width=2)
            dot.pack(side=tk.LEFT)
            lbl = tk.Label(row, text=role, font=self.UI_MONO, fg=self.UI_MUTED,
                           bg=self.UI_PANEL, width=20, anchor="w")
            lbl.pack(side=tk.LEFT)
            state_lbl = tk.Label(row, text="", font=("Segoe UI", 8, "bold"),
                                 fg=self.UI_DIM, bg=self.UI_PANEL, anchor="w")
            state_lbl.pack(side=tk.LEFT)
            self._svc_rows[role] = (dot, lbl, state_lbl)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh_squadron(self, cd):
        carrier_type = cd.get("carrier_type")
        is_squadron = carrier_type == "SquadronCarrier"
        squadron = cd.get("squadron_name")
        rank = cd.get("squadron_rank_name") or cd.get("squadron_rank")

        if is_squadron:
            self.sq_status.config(text="TRACKING SQUADRON CARRIER", fg=self.UI_OK)
            self.sq_guidance.config(
                text="CarrierStats has identified this as the squadron-owned carrier. Identity, operations, expedition progress and Discord announcements update through the existing carrier journal path."
            )
        elif squadron:
            self.sq_status.config(text="SQUADRON KNOWN · CARRIER NOT SYNCED", fg=self.UI_WARN)
            self.sq_guidance.config(
                text="Squadron membership is known. Open the Squadron Carrier management screen in Elite so CarrierStats can identify and populate the carrier; unsupported details remain blank until then."
            )
        elif carrier_type == "FleetCarrier":
            self.sq_status.config(text="PERSONAL CARRIER ACTIVE", fg=self.UI_DIM)
            self.sq_guidance.config(
                text="The tracked carrier is personal. Join or load into a squadron, then open its carrier management screen to activate this command view."
            )
        else:
            self.sq_status.config(text="AWAITING SQUADRON JOURNAL DATA", fg=self.UI_DIM)
            self.sq_guidance.config(
                text="This tab is ready before ownership. SquadronStartup supplies membership and rank; CarrierStats supplies the carrier type, identity, fuel, finance, storage and services."
            )

        type_text = (
            "Squadron Carrier" if is_squadron
            else "Fleet Carrier" if carrier_type == "FleetCarrier"
            else "Awaiting CarrierStats"
        )
        self.sq_type.config(text=type_text)
        self.sq_name.config(text=squadron or "Awaiting SquadronStartup")
        self.sq_rank.config(text=str(rank) if rank is not None else "—")
        carrier_name = cd.get("name")
        self.sq_carrier.config(text=carrier_name or "—")
        self.sq_callsign.config(text=cd.get("callsign") or "—")
        carrier_id = str(cd.get("carrier_id")) if cd.get("carrier_id") is not None else "—"
        squadron_id = cd.get("squadron_id")
        if squadron_id is not None:
            carrier_id += f" · squadron {squadron_id}"
        self.sq_carrier_id.config(text=carrier_id)
        self.sq_synced.config(text=_fmt_dt(cd.get("last_updated")))
        self.sq_system.config(text=cd.get("system") or "—")

        destination = cd.get("jump_destination")
        departure = cd.get("jump_departure_time")
        jump_text = destination or "No jump scheduled"
        if destination and departure:
            jump_text += f" · {_fmt_dt(departure)}"
        self.sq_jump.config(text=jump_text)
        fuel = cd.get("fuel_level")
        self.sq_fuel.config(text=f"{int(fuel):,} T" if fuel is not None else "—")
        current_range = cd.get("jump_range_curr")
        maximum_range = cd.get("jump_range_max")
        if current_range is not None and maximum_range is not None:
            range_text = f"{float(current_range):.1f} / {float(maximum_range):.1f} LY"
        elif current_range is not None:
            range_text = f"{float(current_range):.1f} LY"
        else:
            range_text = "—"
        self.sq_range.config(text=range_text)
        self.sq_docking.config(text=(cd.get("docking_access") or "—").title())

        webhook_ready = bool((self.config.get("carrier_discord_webhook_url") or "").strip())
        self.sq_discord.config(
            text="CONFIGURED" if webhook_ready else "OFF · Settings > Integrations",
            fg=self.UI_OK if webhook_ready else self.UI_DIM,
        )
        self.sq_expedition_btn.config(state=tk.NORMAL if is_squadron else tk.DISABLED)
        self.sq_discord_btn.config(state=tk.NORMAL if is_squadron and webhook_ready else tk.DISABLED)

    def _refresh(self):
        if not self.is_open():
            return
        cd = self.tracker.carrier_data
        self._refresh_expedition(cd)
        self._refresh_cargo(cd)

        # Status badge
        status = cd.get("status", "idle")
        badge_cfg = {
            "idle":           ("IDLE",      self.UI_DIM),
            "jumping":        ("JUMPING",   COLOR_ACCENT),
            "cooldown":       ("COOLDOWN",  self.UI_WARN),
            "cooldown_cancel":("CANCELLED", self.UI_FAIL),
        }
        badge_text, badge_bg = badge_cfg.get(status, (status.upper(), self.UI_DIM))
        self.status_badge.config(text=badge_text, bg=badge_bg)

        # Overview
        carrier_type = cd.get("carrier_type")
        is_squadron_carrier = carrier_type == "SquadronCarrier"
        type_label = (
            "Squadron Carrier" if is_squadron_carrier
            else "Fleet Carrier" if carrier_type == "FleetCarrier"
            else "Awaiting CarrierStats"
        )
        self.title_label.config(text="SQUADRON CARRIER" if is_squadron_carrier else "FLEET CARRIER")
        self.id_name.config(text=cd.get("name") or "—")
        self.id_callsign.config(text=cd.get("callsign") or "—")
        self.id_type.config(text=type_label)
        squadron = cd.get("squadron_name")
        squadron_rank = cd.get("squadron_rank_name") or cd.get("squadron_rank")
        if squadron:
            rank_text = f" · rank {squadron_rank}" if squadron_rank is not None else ""
            self.id_squadron.config(text=f"{squadron}{rank_text}")
        elif is_squadron_carrier:
            self.id_squadron.config(text="Awaiting SquadronStartup")
        else:
            self.id_squadron.config(text="—")
        self.id_system.config(text=cd.get("system") or "—")
        body = cd.get("body") or ""
        self.id_body.config(text=body if body else "—")
        self.id_purchased_at.config(text=_fmt_dt(cd.get("carrier_purchased_at")))
        self.id_spawn_system.config(text=cd.get("carrier_spawn_system") or "—")
        self.id_last_synced.config(text=_fmt_dt(cd.get("last_updated")))
        self._refresh_squadron(cd)

        # Pending decom
        if cd.get("pending_decom"):
            self.decom_warning_lbl.pack(fill=tk.X, padx=10, pady=(0, 2))
        else:
            self.decom_warning_lbl.pack_forget()

        # Jump schedule
        dest = cd.get("jump_destination")
        dep  = cd.get("jump_departure_time")
        self.jmp_dest.config(text=dest or "—")
        self.jmp_departs.config(text=_fmt_dt(dep) if dep else "—")
        prev = cd.get("previous_system") or "—"
        prev_b = cd.get("previous_body") or ""
        self.jmp_prev.config(text=f"{prev}" + (f" / {prev_b}" if prev_b else ""))

        # Carrier stats
        fuel = cd.get("fuel_level")
        cap  = cd.get("fuel_capacity") or 1000
        self.stat_fuel.config(
            text=f"{fuel:,} / {cap:,} T" if fuel is not None else "—",
            fg=(self.UI_OK if fuel and (fuel / cap) > 0.4
                else self.UI_WARN if fuel and (fuel / cap) > 0.15
                else self.UI_FAIL) if fuel is not None else COLOR_TEXT
        )
        jr_c = cd.get("jump_range_curr")
        jr_m = cd.get("jump_range_max")
        self.stat_jump_curr.config(text=f"{jr_c:.1f} LY" if jr_c else "—")
        self.stat_jump_max.config(text=f"{jr_m:.1f} LY" if jr_m else "—")
        self.stat_docking.config(text=(cd.get("docking_access") or "all").title())

        # Finance
        self.fin_balance.config(text=_fmt_cr(cd.get("balance")))
        self.fin_available.config(text=_fmt_cr(cd.get("available_balance")))
        self.fin_reserve.config(text=_fmt_cr(cd.get("reserve_balance")))
        rp = cd.get("reserve_percent")
        self.fin_reserve_pct.config(text=f"{rp:.1f}%" if rp is not None else "—")
        self.fin_tax_refuel.config(text=f"{cd.get('tax_refuel') or 0:.0f}%")
        self.fin_tax_rearm.config(text=f"{cd.get('tax_rearm') or 0:.0f}%")
        self.fin_tax_repair.config(text=f"{cd.get('tax_repair') or 0:.0f}%")

        # Storage
        def _t(v): return f"{int(v):,}" if v is not None else "—"
        self.spc_total.config(text=_t(cd.get("space_total")))
        self.spc_free.config(text=_t(cd.get("space_free")))
        self.spc_cargo.config(text=_t(cd.get("space_cargo")))
        self.spc_crew.config(text=_t(cd.get("space_crew")))
        self.spc_reserved.config(text=_t(cd.get("space_reserved")))
        self.spc_ships.config(text=_t(cd.get("space_ship_packs")))
        self.spc_modules.config(text=_t(cd.get("space_module_packs")))

        # Upkeep estimate
        crew = cd.get("crew") or []
        weekly = _calc_weekly_upkeep(crew)
        svc_weekly = weekly - _BASE_UPKEEP
        if is_squadron_carrier:
            self.upkeep_base.config(text="Not inferred")
            self.upkeep_services.config(text="Not inferred")
            self.upkeep_total.config(text="Use journal finance", fg=self.UI_MUTED)
            self.upkeep_funded.config(text="—", fg=COLOR_TEXT)
        else:
            self.upkeep_base.config(text=_fmt_cr(_BASE_UPKEEP))
            self.upkeep_services.config(text=_fmt_cr(svc_weekly))
            self.upkeep_total.config(text=_fmt_cr(weekly), fg=COLOR_TEXT)
        avail = cd.get("available_balance")
        if not is_squadron_carrier and avail is not None and weekly > 0:
            weeks_funded = int(avail) / weekly
            if weeks_funded >= 52:
                funded_txt = f"{weeks_funded / 52:.1f} years"
                funded_fg = self.UI_OK
            elif weeks_funded >= 4:
                funded_txt = f"{weeks_funded:.0f} weeks"
                funded_fg = self.UI_OK
            else:
                funded_txt = f"{weeks_funded:.1f} weeks  [LOW]"
                funded_fg = self.UI_WARN if weeks_funded >= 1 else self.UI_FAIL
            self.upkeep_funded.config(text=funded_txt, fg=funded_fg)
        elif not is_squadron_carrier:
            self.upkeep_funded.config(text="—", fg=COLOR_TEXT)

        # Services
        crew_by_role = {m.get("CrewRole"): m for m in crew}
        for role, (dot, lbl, state_lbl) in self._svc_rows.items():
            member = crew_by_role.get(role)
            if member and member.get("Activated"):
                if member.get("Enabled"):
                    dot.config(fg=self.UI_OK)
                    lbl.config(fg=COLOR_TEXT)
                    state_lbl.config(text="", fg=self.UI_DIM)
                else:
                    dot.config(fg=self.UI_WARN)
                    lbl.config(fg=self.UI_WARN)
                    state_lbl.config(text="PAUSED", fg=self.UI_WARN)
            else:
                dot.config(fg=self.UI_DIM)
                lbl.config(fg=self.UI_DIM)
                state_lbl.config(text="", fg=self.UI_DIM)

        # Planned destination — only sync when not focused
        try:
            dest_focused = (self.win.focus_get() == self.dest_entry)
        except Exception:
            dest_focused = False
        if not dest_focused:
            stored_dest = cd.get("destination_note") or ""
            if self.dest_var.get() != stored_dest:
                self.dest_var.set(stored_dest)

        # Status note — only sync from tracker when entry isn't focused
        try:
            focused = (self.win.focus_get() == self.note_entry)
        except Exception:
            focused = False
        if not focused:
            stored_note = cd.get("notes") or ""
            if self.note_var.get() != stored_note:
                self.note_var.set(stored_note)
