import json
import os
import shutil
import time
import tkinter as tk
from tkinter import filedialog, messagebox

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, get_active_profile, get_profile_dir, save_config
from trade import marketdb as trade_marketdb


CORE_RANKS = {
    "Combat": ("Harmless", "Mostly Harmless", "Novice", "Competent", "Expert", "Master", "Dangerous", "Deadly", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Trade": ("Penniless", "Mostly Penniless", "Peddler", "Dealer", "Merchant", "Broker", "Entrepreneur", "Tycoon", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Explore": ("Aimless", "Mostly Aimless", "Scout", "Surveyor", "Trailblazer", "Pathfinder", "Ranger", "Pioneer", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "CQC": ("Helpless", "Mostly Helpless", "Amateur", "Semi Professional", "Professional", "Champion", "Hero", "Legend", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Soldier": ("Defenceless", "Mostly Defenceless", "Rookie", "Soldier", "Gunslinger", "Warrior", "Gladiator", "Deadeye", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Exobiologist": ("Directionless", "Mostly Directionless", "Compiler", "Collector", "Cataloguer", "Taxonomist", "Ecologist", "Geneticist", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
}

NAVY_RANKS = {
    "Empire": ("None", "Outsider", "Serf", "Master", "Squire", "Knight", "Lord", "Baron", "Viscount", "Count", "Earl", "Marquis", "Duke", "Prince", "King"),
    "Federation": ("None", "Recruit", "Cadet", "Midshipman", "Petty Officer", "Chief Petty Officer", "Warrant Officer", "Ensign", "Lieutenant", "Lt Commander", "Post Commander", "Post Captain", "Rear Admiral", "Vice Admiral", "Admiral"),
}


class CommanderProfileWindow:
    UI_BG = "#080a0d"
    UI_PANEL = "#12161b"
    UI_PANEL_2 = "#171d23"
    UI_BORDER = "#26313a"
    UI_MUTED = "#7d8891"

    def __init__(self, root, app):
        self.root = root
        self.app = app
        self.config = app.config
        self.win = tk.Toplevel(root)
        self.win.title("Commander Profile")
        self.win.geometry(self.config.get("profile_dashboard_geometry", "980x680"))
        self.win.configure(bg=self.UI_BG)
        self.win.minsize(860, 560)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._wheel_bound = False
        self._build()
        self.refresh()

    def is_open(self):
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False

    def lift(self):
        self.win.lift()
        self.win.focus_force()

    def _build(self):
        header = tk.Frame(self.win, bg="#0c1014", height=48)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        title_box = tk.Frame(header, bg="#0c1014")
        title_box.pack(side=tk.LEFT, padx=14)
        tk.Label(title_box, text="COMMANDER PROFILE", font=("Segoe UI", 14, "bold"), fg=COLOR_ACCENT, bg="#0c1014").pack(anchor="w", pady=(6, 0))
        tk.Label(title_box, text="live commander, ship, route, cargo, and profile state", font=("Consolas", 8), fg=self.UI_MUTED, bg="#0c1014").pack(anchor="w")
        self.summary = tk.Label(header, text="", font=("Consolas", 8), fg=self.UI_MUTED, bg="#0c1014")
        self.summary.pack(side=tk.RIGHT, padx=14)

        body = tk.Frame(self.win, bg=self.UI_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(body, bg=self.UI_BG, highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(body, orient=tk.VERTICAL, command=self.canvas.yview)
        self.content = tk.Frame(self.canvas, bg=self.UI_BG)
        self.content_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.content.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.content_window, width=e.width))
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)
        self.content.bind("<Enter>", self._bind_mousewheel)
        self.content.bind("<Leave>", self._unbind_mousewheel)

        footer = tk.Frame(self.win, bg=self.UI_BG)
        footer.pack(fill=tk.X, padx=10, pady=(0, 10))
        self._button(footer, "Refresh", self.refresh).pack(side=tk.LEFT)
        self._button(footer, "Open Profile Folder", self._open_profile_folder, accent=True).pack(side=tk.LEFT, padx=(8, 0))
        self._button(footer, "Backup Profile", self._backup_profile).pack(side=tk.LEFT, padx=(8, 0))

    def _button(self, parent, text, cmd, accent=False):
        return tk.Button(
            parent, text=text, command=cmd,
            bg=COLOR_ACCENT if accent else self.UI_PANEL,
            fg="black" if accent else COLOR_TEXT,
            activebackground=COLOR_ACCENT if accent else "#1a2430",
            activeforeground="black" if accent else COLOR_ACCENT,
            relief=tk.FLAT, bd=0, padx=12, pady=6,
            font=("Segoe UI", 8, "bold"), cursor="hand2",
        )

    def _bind_mousewheel(self, _event=None):
        if not self._wheel_bound:
            self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
            self._wheel_bound = True

    def _unbind_mousewheel(self, _event=None):
        if self._wheel_bound:
            self.canvas.unbind_all("<MouseWheel>")
            self._wheel_bound = False

    def _on_mousewheel(self, event):
        if not self.is_open():
            return
        try:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()

    def _panel(self, parent, border=None):
        return tk.Frame(
            parent,
            bg=self.UI_PANEL,
            highlightbackground=border or self.UI_BORDER,
            highlightthickness=1,
            bd=0,
        )

    def _band(self, parent, border=None):
        outer = self._panel(parent, border=border)
        tk.Frame(outer, bg=border or COLOR_ORANGE, height=2).pack(fill=tk.X)
        return outer

    def _section_label(self, parent, text):
        tk.Label(
            parent,
            text=text,
            font=("Segoe UI", 8, "bold"),
            fg=COLOR_ORANGE,
            bg=parent.cget("bg"),
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(10, 5))

    def _value_label(self, parent, value, fg=COLOR_TEXT, font=None):
        return tk.Label(
            parent,
            text=str(value),
            font=font or ("Consolas", 10, "bold"),
            fg=fg,
            bg=parent.cget("bg"),
            anchor="w",
        )

    def _metric_card(self, parent, title, value, detail="", row=0, col=0, accent=False):
        card = self._panel(parent, border=COLOR_ACCENT if accent else None)
        card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
        tk.Label(card, text=title, font=("Segoe UI", 7, "bold"), fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w").pack(fill=tk.X, padx=10, pady=(7, 0))
        self._value_label(card, value, fg=COLOR_ACCENT if accent else COLOR_TEXT, font=("Consolas", 11, "bold")).pack(fill=tk.X, padx=10, pady=(1, 0))
        tk.Label(card, text=detail or "", font=("Consolas", 8), fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w").pack(fill=tk.X, padx=10, pady=(1, 7))
        return card

    def _chip(self, parent, label, value, accent=False):
        chip = tk.Frame(parent, bg=self.UI_PANEL_2, highlightbackground=COLOR_ACCENT if accent else self.UI_BORDER, highlightthickness=1)
        tk.Label(chip, text=label.upper(), fg=self.UI_MUTED, bg=self.UI_PANEL_2, font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=9, pady=(5, 0))
        tk.Label(chip, text=str(value), fg=COLOR_ACCENT if accent else COLOR_TEXT, bg=self.UI_PANEL_2, font=("Consolas", 10, "bold"), anchor="w").pack(fill=tk.X, padx=9, pady=(1, 6))
        return chip

    def _kv_row(self, parent, label, value, fg=COLOR_TEXT):
        row = tk.Frame(parent, bg=parent.cget("bg"))
        row.pack(fill=tk.X, padx=12, pady=2)
        tk.Label(row, text=label.upper(), font=("Segoe UI", 7, "bold"), fg=self.UI_MUTED, bg=row.cget("bg"), width=18, anchor="w").pack(side=tk.LEFT)
        tk.Label(row, text=str(value), font=("Consolas", 9), fg=fg, bg=row.cget("bg"), anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _bar_row(self, parent, label, value_text, percent=None, color=COLOR_ACCENT):
        row = tk.Frame(parent, bg=parent.cget("bg"))
        row.pack(fill=tk.X, padx=12, pady=4)
        top = tk.Frame(row, bg=row.cget("bg"))
        top.pack(fill=tk.X)
        tk.Label(top, text=label.upper(), font=("Segoe UI", 7, "bold"), fg=self.UI_MUTED, bg=top.cget("bg"), anchor="w").pack(side=tk.LEFT)
        tk.Label(top, text=value_text, font=("Consolas", 8, "bold"), fg=COLOR_TEXT, bg=top.cget("bg"), anchor="e").pack(side=tk.RIGHT)
        track = tk.Frame(row, bg="#070a0e", height=7)
        track.pack(fill=tk.X, pady=(3, 0))
        track.pack_propagate(False)
        if isinstance(percent, (int, float)):
            pct = max(0.0, min(100.0, float(percent))) / 100.0
            fill = tk.Frame(track, bg=color, height=7)
            fill.place(x=0, y=0, relheight=1.0, relwidth=pct)

    def _queue_count(self):
        try:
            with self.app.db_lock:
                return self.app.conn.execute("SELECT COUNT(*) FROM edsm_queue").fetchone()[0]
        except Exception:
            return 0

    def _session_credit_delta(self):
        if not isinstance(getattr(self.app, "cmdr_balance", None), (int, float)):
            return None
        try:
            start_ts = float(getattr(self.app, "session_start_ts", 0) or 0)
            conn = trade_marketdb.connect()
            try:
                row = conn.execute(
                    "SELECT balance FROM balance_log WHERE ts >= ? ORDER BY ts ASC LIMIT 1",
                    (int(start_ts),),
                ).fetchone()
            finally:
                conn.close()
            if row and isinstance(row[0], (int, float)):
                return int(self.app.cmdr_balance) - int(row[0])
        except Exception:
            pass
        return None

    def _folder_size(self, path):
        total = 0
        try:
            for root, _dirs, files in os.walk(path):
                for filename in files:
                    try:
                        total += os.path.getsize(os.path.join(root, filename))
                    except OSError:
                        pass
        except Exception:
            return 0
        return total

    def _fmt_bytes(self, value):
        value = float(value or 0)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
            value /= 1024
        return f"{value:.1f} GB"

    def _fmt_credits(self, value):
        if isinstance(value, (int, float)):
            return f"{int(value):,} cr"
        return "-"

    def _fmt_delta_credits(self, value):
        if not isinstance(value, (int, float)):
            return "-"
        sign = "+" if value >= 0 else "-"
        return f"{sign}{abs(int(value)):,} cr"

    def _session_elapsed_text(self):
        try:
            elapsed = max(0, int(time.time() - float(getattr(self.app, "session_start_ts", time.time()))))
        except Exception:
            elapsed = 0
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _cargo_summary(self):
        inv = list(getattr(self.app, "current_cargo_inventory", []) or [])
        cap = int(getattr(self.app, "cargo_capacity", 0) or 0)
        tons = int(getattr(self.app, "current_cargo_tons", 0) or 0)
        if not tons and inv:
            tons = sum(int(item.get("Count", item.get("count", 0)) or 0) for item in inv if isinstance(item, dict))
        if cap:
            text = f"{tons}/{cap} t"
            detail = f"{(tons / cap) * 100:.0f}% hold used" if cap else ""
        else:
            text = f"{tons} t"
            detail = f"{len(inv)} commodity type(s)" if inv else "Cargo unavailable"
        if inv:
            top = []
            for item in inv[:3]:
                if not isinstance(item, dict):
                    continue
                name = item.get("Name_Localised") or item.get("Name") or item.get("name") or "Cargo"
                count = item.get("Count", item.get("count", 0))
                top.append(f"{name} x{count}")
            if top:
                detail = ", ".join(top)
        return text, detail

    def _route_summary(self):
        route = list(getattr(self.app, "route_list", []) or [])
        dest = getattr(self.app, "dest_name", None) or "-"
        if route:
            current = getattr(self.app, "current_sys", None)
            try:
                idx = route.index(current) + 1
            except Exception:
                idx = 0
            progress = f"{idx}/{len(route)}" if idx else f"{len(route)} jumps"
            return dest, progress
        waypoints = getattr(getattr(self.app, "waypoint_manager", None), "waypoints", []) or []
        if waypoints:
            visited = sum(1 for wp in waypoints if wp.get("visited"))
            next_wp = next((wp.get("name") for wp in waypoints if not wp.get("visited")), None)
            return next_wp or "Route complete", f"{visited}/{len(waypoints)} waypoints"
        return "-", "No active route"

    def _profile_alerts(self):
        alerts = []
        if getattr(self.app, "system_undiscovered", False):
            alerts.append("Undiscovered system")
        bio = int(getattr(self.app, "system_bio_signals", 0) or 0)
        if bio:
            alerts.append(f"{bio} bio signal(s)")
        valuable = getattr(self.app, "valuable_bodies", []) or []
        if valuable:
            alerts.append(f"{len(valuable)} valuable body/bodies")
        if getattr(self.app, "target_latlon_active", False):
            alerts.append("Ground target active")
        if getattr(self.app, "current_docked", False):
            alerts.append("Docked")
        if not alerts:
            alerts.append("No active alerts")
        return alerts

    def _fmt_percent(self, value):
        if isinstance(value, (int, float)):
            return f"{float(value):.0f}%"
        return "-"

    def _rank_label(self, category, value):
        try:
            value = int(value)
        except Exception:
            return "-"
        ranks = CORE_RANKS.get(category) or NAVY_RANKS.get(category)
        if not ranks:
            return str(value)
        if value < 0:
            return str(value)
        if value >= len(ranks):
            return f"{ranks[-1]} ({value})"
        return ranks[value]

    def _latest_journal_snapshot(self):
        journal_path = self.config.get("journal_path") or ""
        if not journal_path or not os.path.isdir(journal_path):
            return {}
        try:
            files = [
                os.path.join(journal_path, name)
                for name in os.listdir(journal_path)
                if name.startswith("Journal") and name.endswith(".log")
            ]
            files.sort(key=lambda path: os.path.getmtime(path), reverse=True)
        except Exception:
            return {}

        active_name = (self.config.get("active_commander_name") or "").strip().lower()
        active_fid = (self.config.get("active_commander_fid") or "").strip()
        snapshot = {"ranks": {}, "progress": {}, "reputation": {}, "ship": {}, "balance": None, "loan": None}
        matched_file = False
        for path in files[:12]:
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    events = [json.loads(line) for line in handle if line.strip()]
            except Exception:
                continue
            file_commander = ""
            file_fid = ""
            for event in events:
                ev = event.get("event")
                if ev == "Commander":
                    file_commander = event.get("Name") or file_commander
                    file_fid = event.get("FID") or file_fid
                elif ev == "LoadGame":
                    file_commander = event.get("Commander") or file_commander
                    file_fid = event.get("FID") or file_fid
            if active_fid and file_fid and file_fid != active_fid:
                continue
            if active_name and file_commander and file_commander.lower() != active_name:
                continue
            matched_file = True
            for event in events:
                ev = event.get("event")
                if ev == "Rank":
                    snapshot["ranks"].update({k: v for k, v in event.items() if k not in ("timestamp", "event")})
                elif ev == "Progress":
                    snapshot["progress"].update({k: v for k, v in event.items() if k not in ("timestamp", "event")})
                elif ev == "Reputation":
                    snapshot["reputation"].update({k: v for k, v in event.items() if k not in ("timestamp", "event")})
                elif ev == "LoadGame":
                    snapshot["balance"] = event.get("Credits")
                    snapshot["loan"] = event.get("Loan")
                    snapshot["ship"].update({
                        "ship": event.get("Ship"),
                        "ship_localised": event.get("Ship_Localised"),
                        "ship_id": event.get("ShipID"),
                        "ship_name": event.get("ShipName"),
                        "ship_ident": event.get("ShipIdent"),
                        "fuel_level": event.get("FuelLevel"),
                        "fuel_capacity": event.get("FuelCapacity"),
                        "game_mode": event.get("GameMode"),
                        "group": event.get("Group"),
                    })
                elif ev == "Loadout":
                    snapshot["ship"].update({
                        "ship": event.get("Ship") or snapshot["ship"].get("ship"),
                        "ship_id": event.get("ShipID") or snapshot["ship"].get("ship_id"),
                        "ship_name": event.get("ShipName") or snapshot["ship"].get("ship_name"),
                        "ship_ident": event.get("ShipIdent") or snapshot["ship"].get("ship_ident"),
                        "modules_value": event.get("ModulesValue"),
                        "hull_health": event.get("HullHealth"),
                        "max_jump_range": event.get("MaxJumpRange"),
                        "rebuy": event.get("Rebuy"),
                        "cargo_capacity": event.get("CargoCapacity"),
                    })
            if snapshot["ranks"] or snapshot["ship"] or snapshot["balance"] is not None:
                break
        return snapshot if matched_file else {}

    def refresh(self):
        profile_key = get_active_profile(self.config)
        profile_dir = get_profile_dir(profile_key)
        name = self.config.get("active_commander_name") or "Unknown Commander"
        fid = self.config.get("active_commander_fid") or ""
        journal_snapshot = self._latest_journal_snapshot()
        balance = self.app.cmdr_balance
        loan = self.app.cmdr_loan
        if balance is None:
            balance = journal_snapshot.get("balance")
        if loan is None:
            loan = journal_snapshot.get("loan")
        balance_text = self._fmt_credits(balance)
        loan_text = self._fmt_credits(loan)
        credit_delta = self._session_credit_delta()
        ship = dict(journal_snapshot.get("ship") or {})
        ship.update({
            key: value for key, value in (getattr(self.app, "cmdr_ship", {}) or {}).items()
            if value is not None and value != ""
        })
        ranks = dict(journal_snapshot.get("ranks") or {})
        ranks.update(getattr(self.app, "cmdr_ranks", {}) or {})
        progress = dict(journal_snapshot.get("progress") or {})
        progress.update(getattr(self.app, "cmdr_rank_progress", {}) or {})
        reputation = dict(journal_snapshot.get("reputation") or {})
        reputation.update(getattr(self.app, "cmdr_reputation", {}) or {})
        paths = [
            ("Exploration DB", getattr(self.app, "db_path", "")),
            ("Mining DB", self.config.get("mining_db_file", "")),
            ("Waypoints", self.config.get("waypoints_file", "")),
            ("Carrier State", self.config.get("carrier_state_file", "")),
            ("Colonisation", self.config.get("colonisation_data_file", "")),
            ("Engineer Materials", self.config.get("engineer_materials_file", "")),
        ]

        self.summary.config(text=profile_key)
        self._clear_content()

        ship_type = ship.get("ship_localised") or ship.get("ship") or "-"
        ship_name = ship.get("ship_name") or "-"
        ship_ident = ship.get("ship_ident") or "-"

        hero = self._band(self.content, border=COLOR_ACCENT)
        hero.pack(fill=tk.X, padx=2, pady=(0, 10))
        hero_body = tk.Frame(hero, bg=self.UI_PANEL)
        hero_body.pack(fill=tk.X, padx=14, pady=12)
        identity = tk.Frame(hero_body, bg=self.UI_PANEL)
        identity.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(identity, text=name.upper(), fg=COLOR_ACCENT, bg=self.UI_PANEL, font=("Segoe UI", 22, "bold"), anchor="w").pack(fill=tk.X)
        tk.Label(identity, text=fid or profile_key, fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Consolas", 9), anchor="w").pack(fill=tk.X, pady=(1, 0))
        ship_line = ship_name if ship_name != "-" else ship_type
        tk.Label(identity, text=f"{ship_line}  |  {ship_type}  |  {ship_ident}", fg=COLOR_TEXT, bg=self.UI_PANEL, font=("Consolas", 10, "bold"), anchor="w").pack(fill=tk.X, pady=(8, 0))

        chips = tk.Frame(hero_body, bg=self.UI_PANEL)
        chips.pack(side=tk.RIGHT, fill=tk.Y)
        credit_detail = f"{balance_text}\n{self._fmt_delta_credits(credit_delta)} session" if credit_delta is not None else f"{balance_text}\nLoan {loan_text}"
        for idx, (label, value, accent) in enumerate((
            ("Credits", credit_detail, True),
            ("System", getattr(self.app, "current_sys", "---"), False),
            ("Session", f"{self._session_elapsed_text()}\n{getattr(self.app, 'session_jump_count', 0)} jumps", False),
        )):
            chip = self._chip(chips, label, value, accent=accent)
            chip.grid(row=0, column=idx, sticky="nsew", padx=(8 if idx else 0, 0))
            chips.grid_columnconfigure(idx, weight=1, uniform="hero_chips")

        main = tk.Frame(self.content, bg=self.UI_BG)
        main.pack(fill=tk.BOTH, expand=True)
        main.grid_columnconfigure(0, weight=3, uniform="profile_cols")
        main.grid_columnconfigure(1, weight=2, uniform="profile_cols")

        left = tk.Frame(main, bg=self.UI_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(2, 5))
        right = tk.Frame(main, bg=self.UI_BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 2))

        ops_card = self._band(left, border=COLOR_ACCENT)
        ops_card.pack(fill=tk.X, pady=(0, 8))
        self._section_label(ops_card, "CURRENT OPERATIONS")
        cargo_text, cargo_detail = self._cargo_summary()
        route_target, route_detail = self._route_summary()
        station = getattr(self.app, "current_station_name", None) or "-"
        docked = "Docked" if getattr(self.app, "current_docked", False) else "In flight"
        trade_session = getattr(self.app, "trade_session", {}) or {}
        ops_grid = tk.Frame(ops_card, bg=self.UI_PANEL)
        ops_grid.pack(fill=tk.X, padx=8, pady=(0, 10))
        for col in range(2):
            ops_grid.grid_columnconfigure(col, weight=1, uniform="ops")
        self._metric_card(ops_grid, "STATION", f"{station}" if station != "-" else docked, docked, 0, 0)
        self._metric_card(ops_grid, "CARGO", cargo_text, cargo_detail, 0, 1)
        self._metric_card(ops_grid, "ROUTE TARGET", route_target, route_detail, 1, 0)
        self._metric_card(ops_grid, "TRADE SESSION", self._fmt_delta_credits(trade_session.get("profit", 0)), f"{trade_session.get('bought_units', 0):,}t bought / {trade_session.get('sold_units', 0):,}t sold", 1, 1)

        ship_card = self._panel(left)
        ship_card.pack(fill=tk.X, pady=(0, 8))
        self._section_label(ship_card, "ACTIVE SHIP")
        for key, value in (
            ("Type", ship_type),
            ("Ident", ship_ident),
            ("Ship ID", ship.get("ship_id") or "-"),
            ("Cargo Capacity", f"{ship.get('cargo_capacity')} t" if ship.get("cargo_capacity") is not None else "-"),
            ("Jump Range", f"{float(ship.get('max_jump_range')):.2f} ly" if isinstance(ship.get("max_jump_range"), (int, float)) else "-"),
            ("Rebuy", self._fmt_credits(ship.get("rebuy"))),
            ("Modules", self._fmt_credits(ship.get("modules_value"))),
            ("Hull", f"{float(ship.get('hull_health')) * 100:.1f}%" if isinstance(ship.get("hull_health"), (int, float)) else "-"),
            ("Fuel", f"{float(ship.get('fuel_level')):.1f}/{float(ship.get('fuel_capacity')):.1f} t" if isinstance(ship.get("fuel_level"), (int, float)) and isinstance(ship.get("fuel_capacity"), (int, float)) else "-"),
            ("Mode", ship.get("game_mode") or "-"),
            ("Group", ship.get("group") or "-"),
        ):
            self._kv_row(ship_card, key, value)

        rank_card = self._band(right, border=COLOR_ORANGE)
        rank_card.pack(fill=tk.X, pady=(0, 8))
        self._section_label(rank_card, "RANKS")
        rank_count = 0
        for category in ("Combat", "Trade", "Explore", "Soldier", "Exobiologist", "Empire", "Federation", "CQC"):
            if category not in ranks and category not in progress:
                continue
            rank_text = self._rank_label(category, ranks.get(category))
            progress_value = progress.get(category)
            prog_text = self._fmt_percent(progress_value)
            self._bar_row(rank_card, category, f"{rank_text}  {prog_text}", progress_value, COLOR_ACCENT)
            rank_count += 1
        if rank_count == 0:
            tk.Label(rank_card, text="No rank data seen yet.", font=("Consolas", 9), fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w").pack(fill=tk.X, padx=12, pady=(0, 12))

        alert_card = self._panel(right)
        alert_card.pack(fill=tk.X, pady=(0, 8))
        self._section_label(alert_card, "ACTIVE TASKS")
        for alert in self._profile_alerts():
            self._kv_row(alert_card, "Task", alert, fg=COLOR_ACCENT if alert != "No active alerts" else self.UI_MUTED)

        rep_card = self._panel(right)
        rep_card.pack(fill=tk.X, pady=(0, 8))
        self._section_label(rep_card, "REPUTATION")
        if reputation:
            for key in ("Federation", "Empire", "Alliance", "Independent"):
                if key in reputation:
                    self._bar_row(rep_card, key, self._fmt_percent(reputation.get(key)), reputation.get(key), COLOR_ORANGE)
        else:
            tk.Label(rep_card, text="No reputation data seen yet.", font=("Consolas", 9), fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w").pack(fill=tk.X, padx=12, pady=(0, 12))

        storage_card = self._panel(left)
        storage_card.pack(fill=tk.X, pady=(0, 8))
        self._section_label(storage_card, "PROFILE STORAGE")
        self._kv_row(storage_card, "Folder", profile_dir)
        self._kv_row(storage_card, "Size", self._fmt_bytes(self._folder_size(profile_dir)))
        for label, path in paths:
            exists = "OK" if path and os.path.exists(path) else "missing"
            fg = COLOR_TEXT if exists == "OK" else "#ff9a3c"
            self._kv_row(storage_card, label, f"{exists}  {path}", fg=fg)

        integration_card = self._panel(self.content)
        integration_card.pack(fill=tk.X, padx=2, pady=(2, 2))
        self._section_label(integration_card, "INTEGRATIONS")
        integration_grid = tk.Frame(integration_card, bg=self.UI_PANEL)
        integration_grid.pack(fill=tk.X, padx=7, pady=(0, 8))
        for col in range(3):
            integration_grid.grid_columnconfigure(col, weight=1, uniform="profile_integrations")
        self._metric_card(integration_grid, "EDSM UPLOAD", "ON" if self.config.get("edsm_upload_enabled") else "OFF", "Scan upload setting", 0, 0, accent=bool(self.config.get("edsm_upload_enabled")))
        self._metric_card(integration_grid, "EDSM QUEUE", f"{self._queue_count()} events", "Pending upload backlog", 0, 1)
        self._metric_card(integration_grid, "CARRIER DISCORD", "CONFIGURED" if self.config.get("carrier_discord_webhook_url") else "OFF", "Webhook notification setting", 0, 2)

        self.content.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _open_profile_folder(self):
        path = get_profile_dir(get_active_profile(self.config))
        try:
            os.startfile(path)
        except Exception:
            messagebox.showinfo("Profile Folder", path, parent=self.win)

    def _backup_profile(self):
        src = get_profile_dir(get_active_profile(self.config))
        target = filedialog.askdirectory(title="Choose backup destination", parent=self.win)
        if not target:
            return
        name = self.config.get("active_commander_profile") or "profile"
        stamp = time.strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(target, f"{name}_{stamp}")
        try:
            shutil.copytree(src, dst)
            messagebox.showinfo("Backup Complete", f"Profile copied to:\n{dst}", parent=self.win)
        except Exception as exc:
            messagebox.showerror("Backup Failed", str(exc), parent=self.win)

    def _on_close(self):
        try:
            self.config["profile_dashboard_geometry"] = self.win.geometry()
            save_config(self.config)
        except Exception:
            pass
        self._unbind_mousewheel()
        self.win.destroy()
