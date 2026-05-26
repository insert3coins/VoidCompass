"""
carrier_window.py — Fleet Carrier detail window for VoidCompass.
Tabs: Overview, Finance, Services.
All data comes from CarrierTracker.carrier_data.
"""
import tkinter as tk
from datetime import datetime, timezone

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT

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


class CarrierWindow:
    UI_BG    = "#080a0d"
    UI_PANEL = "#12161b"
    UI_BORDER= "#26313a"
    UI_MUTED = "#7d8891"
    UI_DIM   = "#4e5962"
    UI_OK    = "#21d189"
    UI_WARN  = "#ff9a3c"
    UI_FAIL  = "#ff5c5c"
    UI_FONT  = ("Segoe UI", 9)
    UI_BOLD  = ("Segoe UI", 9, "bold")
    UI_MONO  = ("Consolas", 9)
    UI_MONO_B= ("Consolas", 10, "bold")

    def __init__(self, root, config, tracker):
        self.root = root
        self.config = config
        self.tracker = tracker
        self._after_job = None

        self.win = tk.Toplevel(root)
        self.win.title("Fleet Carrier")
        self.win.configure(bg=self.UI_BG)
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
            from config import CONFIG_FILE
            import json
            with open(CONFIG_FILE, "w") as _f:
                json.dump(self.config, _f, indent=4)
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
        tk.Label(hdr, text="FLEET CARRIER", font=("Segoe UI", 13, "bold"),
                 fg=COLOR_ACCENT, bg="#0c1014").pack(side=tk.LEFT, padx=14, pady=8)
        self.status_badge = tk.Label(hdr, text="IDLE", fg="black", bg=self.UI_DIM,
                                     font=("Segoe UI", 8, "bold"), padx=8, pady=3)
        self.status_badge.pack(side=tk.RIGHT, padx=14, pady=10)

        # Tab bar
        tab_bar = tk.Frame(self.win, bg="#0c1014")
        tab_bar.pack(fill=tk.X)
        self._tabs = {}
        self._tab_frames = {}
        for name in ("Overview", "Finance", "Services"):
            btn = tk.Button(tab_bar, text=name, relief=tk.FLAT, bd=0,
                            font=self.UI_BOLD, bg="#0c1014", fg=self.UI_MUTED,
                            activebackground=self.UI_PANEL, activeforeground=COLOR_TEXT,
                            padx=14, pady=6, cursor="hand2",
                            command=lambda n=name: self._show_tab(n))
            btn.pack(side=tk.LEFT)
            self._tabs[name] = btn

        # Tab content area
        self._tab_area = tk.Frame(self.win, bg=self.UI_BG)
        self._tab_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        self._build_overview_tab()
        self._build_finance_tab()
        self._build_services_tab()
        self._show_tab("Overview")

    def _show_tab(self, name):
        for n, frame in self._tab_frames.items():
            frame.pack_forget()
            self._tabs[n].config(fg=self.UI_MUTED, bg="#0c1014")
        self._tab_frames[name].pack(fill=tk.BOTH, expand=True)
        self._tabs[name].config(fg=COLOR_TEXT, bg=self.UI_PANEL)

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
        self.id_system    = self._row(f, "Location")
        self.id_body      = self._row(f, "Body")
        self.id_purchased_at   = self._row(f, "Purchased At")
        self.id_spawn_system   = self._row(f, "Purchased In")
        self.id_last_synced    = self._row(f, "Last Synced")

        # Pending decommission warning
        self.decom_warning_lbl = tk.Label(f, text="⚠  PENDING DECOMMISSION",
                                          font=self.UI_BOLD, fg=self.UI_WARN,
                                          bg=self.UI_PANEL, anchor="w")

        self._section(f, "JUMP SCHEDULE")
        self.jmp_dest    = self._row(f, "Destination")
        self.jmp_departs = self._row(f, "Departs")
        self.jmp_prev    = self._row(f, "Previous System")

        # Copy countdown button
        self._copy_btn = tk.Button(f, text="Copy <t:…:R> to clipboard",
                                   font=self.UI_FONT, fg=self.UI_MUTED,
                                   bg=self.UI_PANEL, relief=tk.FLAT, bd=0,
                                   activebackground=self.UI_PANEL,
                                   activeforeground=COLOR_ACCENT,
                                   cursor="hand2",
                                   command=self._copy_countdown)
        self._copy_btn.pack(anchor="w", padx=10, pady=(2, 0))

        self._section(f, "CARRIER STATS")
        self.stat_fuel       = self._row(f, "Fuel")
        self.stat_jump_curr  = self._row(f, "Jump Range (curr)")
        self.stat_jump_max   = self._row(f, "Jump Range (max)")
        self.stat_docking    = self._row(f, "Docking Access")

        self._section(f, "STATUS NOTE")
        tk.Label(f, text="Shown in Discord notifications as ℹ️  at the bottom of each message.",
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
        note_btn = tk.Button(
            note_row, text="Set",
            bg=self.UI_PANEL, fg=COLOR_ACCENT,
            activebackground=self.UI_BORDER, activeforeground=COLOR_ACCENT,
            font=self.UI_BOLD, relief=tk.FLAT, bd=0,
            padx=10, cursor="hand2",
            command=self._save_note,
        )
        note_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.note_entry.bind("<Return>", lambda _e: self._save_note())

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
        self.id_name.config(text=cd.get("name") or "—")
        self.id_callsign.config(text=cd.get("callsign") or "—")
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
        self.upkeep_base.config(text=_fmt_cr(_BASE_UPKEEP))
        self.upkeep_services.config(text=_fmt_cr(svc_weekly))
        self.upkeep_total.config(text=_fmt_cr(weekly))
        avail = cd.get("available_balance")
        if avail is not None and weekly > 0:
            weeks_funded = int(avail) / weekly
            if weeks_funded >= 52:
                funded_txt = f"{weeks_funded / 52:.1f} years"
                funded_fg = self.UI_OK
            elif weeks_funded >= 4:
                funded_txt = f"{weeks_funded:.0f} weeks"
                funded_fg = self.UI_OK
            else:
                funded_txt = f"{weeks_funded:.1f} weeks  ⚠ LOW"
                funded_fg = self.UI_WARN if weeks_funded >= 1 else self.UI_FAIL
            self.upkeep_funded.config(text=funded_txt, fg=funded_fg)
        else:
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

        # Status note — only sync from tracker when entry isn't focused
        try:
            focused = (self.win.focus_get() == self.note_entry)
        except Exception:
            focused = False
        if not focused:
            stored_note = cd.get("notes") or ""
            if self.note_var.get() != stored_note:
                self.note_var.set(stored_note)
