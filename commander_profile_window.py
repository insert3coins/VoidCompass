import json
import os
import shutil
import time
import tkinter as tk
from tkinter import filedialog, messagebox

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, get_active_profile, get_profile_dir, save_config


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
    UI_BORDER = "#26313a"
    UI_MUTED = "#7d8891"

    def __init__(self, root, app):
        self.root = root
        self.app = app
        self.config = app.config
        self.win = tk.Toplevel(root)
        self.win.title("Commander Profile")
        self.win.geometry(self.config.get("profile_dashboard_geometry", "760x520"))
        self.win.configure(bg=self.UI_BG)
        self.win.minsize(650, 430)
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
        tk.Label(header, text="COMMANDER PROFILE", font=("Segoe UI", 13, "bold"), fg=COLOR_ACCENT, bg="#0c1014").pack(side=tk.LEFT, padx=14)
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
        tk.Label(card, text=title, font=("Segoe UI", 7, "bold"), fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w").pack(fill=tk.X, padx=10, pady=(8, 0))
        self._value_label(card, value, fg=COLOR_ACCENT if accent else COLOR_TEXT, font=("Consolas", 12, "bold")).pack(fill=tk.X, padx=10, pady=(2, 0))
        tk.Label(card, text=detail or "", font=("Consolas", 8), fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w").pack(fill=tk.X, padx=10, pady=(1, 8))
        return card

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

        hero = self._panel(self.content, border=COLOR_ACCENT)
        hero.pack(fill=tk.X, padx=2, pady=(0, 10))
        hero_grid = tk.Frame(hero, bg=self.UI_PANEL)
        hero_grid.pack(fill=tk.X, padx=8, pady=8)
        for col in range(4):
            hero_grid.grid_columnconfigure(col, weight=1, uniform="profile_metrics")
        self._metric_card(hero_grid, "COMMANDER", name, fid or "FID unknown", 0, 0, accent=True)
        self._metric_card(hero_grid, "CREDITS", balance_text, f"Loan {loan_text}", 0, 1)
        self._metric_card(hero_grid, "LOCATION", getattr(self.app, "current_sys", "---"), "Current journal system", 0, 2)
        self._metric_card(
            hero_grid,
            "SESSION",
            f"{getattr(self.app, 'session_jump_count', 0)} jumps",
            f"{getattr(self.app, 'session_ly', 0.0):,.1f} ly travelled",
            0,
            3,
        )

        main = tk.Frame(self.content, bg=self.UI_BG)
        main.pack(fill=tk.BOTH, expand=True)
        main.grid_columnconfigure(0, weight=1, uniform="profile_cols")
        main.grid_columnconfigure(1, weight=1, uniform="profile_cols")

        ship_type = ship.get("ship_localised") or ship.get("ship") or "-"
        ship_name = ship.get("ship_name") or "-"
        ship_ident = ship.get("ship_ident") or "-"
        ship_card = self._panel(main)
        ship_card.grid(row=0, column=0, sticky="nsew", padx=(2, 5), pady=5)
        self._section_label(ship_card, "ACTIVE SHIP")
        self._value_label(ship_card, ship_name if ship_name != "-" else ship_type, fg=COLOR_ACCENT, font=("Consolas", 13, "bold")).pack(fill=tk.X, padx=12)
        self._kv_row(ship_card, "Type", ship_type)
        self._kv_row(ship_card, "Ident", ship_ident)
        for key, value in (
            ("Ship ID", ship.get("ship_id") or "-"),
            ("Cargo", ship.get("cargo_capacity") if ship.get("cargo_capacity") is not None else "-"),
            ("Jump Range", f"{float(ship.get('max_jump_range')):.2f} ly" if isinstance(ship.get("max_jump_range"), (int, float)) else "-"),
            ("Rebuy", self._fmt_credits(ship.get("rebuy"))),
            ("Modules", self._fmt_credits(ship.get("modules_value"))),
            ("Hull", f"{float(ship.get('hull_health')) * 100:.1f}%" if isinstance(ship.get("hull_health"), (int, float)) else "-"),
            ("Fuel", f"{float(ship.get('fuel_level')):.1f}/{float(ship.get('fuel_capacity')):.1f} t" if isinstance(ship.get("fuel_level"), (int, float)) and isinstance(ship.get("fuel_capacity"), (int, float)) else "-"),
            ("Mode", ship.get("game_mode") or "-"),
            ("Group", ship.get("group") or "-"),
        ):
            self._kv_row(ship_card, key, value)

        rank_card = self._panel(main)
        rank_card.grid(row=0, column=1, sticky="nsew", padx=(5, 2), pady=5)
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

        rep_card = self._panel(main)
        rep_card.grid(row=1, column=0, sticky="nsew", padx=(2, 5), pady=5)
        self._section_label(rep_card, "REPUTATION")
        if reputation:
            for key in ("Federation", "Empire", "Alliance", "Independent"):
                if key in reputation:
                    self._bar_row(rep_card, key, self._fmt_percent(reputation.get(key)), reputation.get(key), COLOR_ORANGE)
        else:
            tk.Label(rep_card, text="No reputation data seen yet.", font=("Consolas", 9), fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w").pack(fill=tk.X, padx=12, pady=(0, 12))

        storage_card = self._panel(main)
        storage_card.grid(row=1, column=1, sticky="nsew", padx=(5, 2), pady=5)
        self._section_label(storage_card, "PROFILE STORAGE")
        self._kv_row(storage_card, "Folder", profile_dir)
        self._kv_row(storage_card, "Size", self._fmt_bytes(self._folder_size(profile_dir)))
        for label, path in paths:
            exists = "OK" if path and os.path.exists(path) else "missing"
            fg = COLOR_TEXT if exists == "OK" else "#ff9a3c"
            self._kv_row(storage_card, label, f"{exists}  {path}", fg=fg)

        integration_card = self._panel(self.content)
        integration_card.pack(fill=tk.X, padx=2, pady=(5, 2))
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
