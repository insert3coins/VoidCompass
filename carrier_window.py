"""
carrier_window.py — Personal/Squadron Carrier detail window for VoidCompass.
Tabs: Overview, Expedition, Finance, Services.
All data comes from CarrierTracker.carrier_data.
"""
import tkinter as tk
import webbrowser
from datetime import datetime, timezone

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config
from ui_theme import THEME, ThemedWindowMixin, apply_window, button, window_surface

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

    def __init__(self, root, config, tracker, embedded=False):
        self.root = root
        self.config = config
        self.tracker = tracker
        self._after_job = None

        self.embedded = embedded
        self.win = window_surface(root, embedded=embedded)
        self.win.title("Carrier Command")
        apply_window(self.win)
        self.win.geometry(config.get("carrier_window_geometry", "480x560"))
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
        for name in ("Overview", "Expedition", "Finance", "Services"):
            btn = button(tab_bar, name, lambda n=name: self._show_tab(n), muted=True, padx=14, pady=6)
            btn.pack(side=tk.LEFT)
            self._tabs[name] = btn

        # Tab content area
        self._tab_area = tk.Frame(self.win, bg=self.UI_BG)
        self._tab_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        self._build_overview_tab()
        self._build_expedition_tab()
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
            f, text="Paste one system per line. CarrierJump/CarrierLocation marks arrivals automatically.",
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
        route_wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        self.expedition_route_text = tk.Text(
            route_wrap, bg="#090c10", fg=COLOR_TEXT, insertbackground=COLOR_ACCENT,
            relief=tk.FLAT, bd=0, font=self.UI_MONO, wrap=tk.NONE, padx=8, pady=8,
        )
        self.expedition_route_text.pack(fill=tk.BOTH, expand=True)
        self.expedition_route_text.tag_config("visited", foreground=self.UI_DIM)
        self.expedition_route_text.tag_config("next", foreground=COLOR_ORANGE)
        self.expedition_route_text.tag_config("pending", foreground=COLOR_TEXT)

        actions = tk.Frame(f, bg=self.UI_PANEL)
        actions.pack(fill=tk.X, padx=10, pady=(0, 6))
        button(actions, "SAVE / UPDATE ROUTE", self._save_expedition, accent=True).pack(side=tk.LEFT)
        button(actions, "COPY NEXT", self._copy_next_expedition).pack(side=tk.LEFT, padx=(6, 0))
        button(actions, "OPEN SPANSH ROUTER", self._open_spansh_carrier).pack(side=tk.LEFT, padx=(6, 0))
        self.expedition_summary = tk.Label(actions, text="", fg=self.UI_MUTED, bg=self.UI_PANEL,
                                           font=("Consolas", 8))
        self.expedition_summary.pack(side=tk.RIGHT)

    def _save_expedition(self):
        systems = []
        for line in self.expedition_route_text.get("1.0", tk.END).splitlines():
            value = line.strip()
            if value.startswith(("✓", "→", "·")):
                value = value[1:].strip()
            if value:
                systems.append(value)
        self.tracker.set_expedition(
            self.expedition_name_var.get(), systems, self.expedition_reserve_var.get()
        )

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

    @staticmethod
    def _open_spansh_carrier():
        webbrowser.open("https://spansh.co.uk/fleet-carrier")

    def _refresh_expedition(self, cd):
        try:
            focused = self.win.focus_get() == self.expedition_route_text
        except Exception:
            focused = False
        route = cd.get("expedition_route") or []
        if not focused:
            self.expedition_route_text.delete("1.0", tk.END)
            next_written = False
            for row in route:
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
        fuel = cd.get("fuel_level")
        reserve = int(cd.get("expedition_reserve_fuel") or 0)
        fuel_text = "fuel unknown" if fuel is None else f"{max(0, int(fuel) - reserve):,} T above reserve"
        self.expedition_summary.config(text=f"{done}/{len(route)} stops | {remaining * 20} min nominal | {fuel_text}")

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

    def _refresh(self):
        if not self.is_open():
            return
        cd = self.tracker.carrier_data
        self._refresh_expedition(cd)

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
        squadron_rank = cd.get("squadron_rank")
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
