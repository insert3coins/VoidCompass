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

        self.text = tk.Text(body, bg="#0b0f13", fg=COLOR_TEXT, font=("Consolas", 9), relief=tk.FLAT, padx=8, pady=8, wrap=tk.NONE)
        self.text.pack(fill=tk.BOTH, expand=True)
        self.text.tag_config("hdr", foreground=COLOR_ORANGE, font=("Consolas", 9, "bold"))
        self.text.tag_config("key", foreground=COLOR_ACCENT)
        self.text.tag_config("muted", foreground=self.UI_MUTED)
        self.text.config(state=tk.DISABLED)

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
        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, "COMMANDER\n", "hdr")
        for key, value in (
            ("Name", name),
            ("FID", fid or "-"),
            ("Profile", profile_key),
            ("Current System", getattr(self.app, "current_sys", "---")),
            ("Credits", balance_text),
            ("Loan", loan_text),
            ("Session Jumps", getattr(self.app, "session_jump_count", 0)),
            ("Session LY", f"{getattr(self.app, 'session_ly', 0.0):,.1f}"),
        ):
            self.text.insert(tk.END, f"  {key:<18}", "key")
            self.text.insert(tk.END, f"{value}\n")

        self.text.insert(tk.END, "\nSHIP\n", "hdr")
        ship_type = ship.get("ship_localised") or ship.get("ship") or "-"
        ship_name = ship.get("ship_name") or "-"
        ship_ident = ship.get("ship_ident") or "-"
        for key, value in (
            ("Type", ship_type),
            ("Name", ship_name),
            ("Ident", ship_ident),
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
            self.text.insert(tk.END, f"  {key:<18}", "key")
            self.text.insert(tk.END, f"{value}\n")

        self.text.insert(tk.END, "\nRANKS\n", "hdr")
        for category in ("Combat", "Trade", "Explore", "Soldier", "Exobiologist", "Empire", "Federation", "CQC"):
            if category not in ranks and category not in progress:
                continue
            rank_text = self._rank_label(category, ranks.get(category))
            prog_text = self._fmt_percent(progress.get(category))
            self.text.insert(tk.END, f"  {category:<18}", "key")
            self.text.insert(tk.END, f"{rank_text:<22} {prog_text}\n")

        self.text.insert(tk.END, "\nREPUTATION\n", "hdr")
        if reputation:
            for key in ("Federation", "Empire", "Alliance", "Independent"):
                if key in reputation:
                    self.text.insert(tk.END, f"  {key:<18}", "key")
                    self.text.insert(tk.END, f"{self._fmt_percent(reputation.get(key))}\n")
        else:
            self.text.insert(tk.END, "  No reputation data seen yet.\n", "muted")

        self.text.insert(tk.END, "\nPROFILE STORAGE\n", "hdr")
        self.text.insert(tk.END, f"  {'Folder':<18}{profile_dir}\n", "key")
        self.text.insert(tk.END, f"  {'Size':<18}{self._fmt_bytes(self._folder_size(profile_dir))}\n", "key")
        for label, path in paths:
            exists = "OK" if path and os.path.exists(path) else "missing"
            self.text.insert(tk.END, f"  {label:<18}", "key")
            self.text.insert(tk.END, f"{exists:<8} {path}\n")

        self.text.insert(tk.END, "\nINTEGRATIONS\n", "hdr")
        self.text.insert(tk.END, f"  {'EDSM Upload':<18}{'On' if self.config.get('edsm_upload_enabled') else 'Off'}\n", "key")
        self.text.insert(tk.END, f"  {'EDSM Queue':<18}{self._queue_count()} event(s)\n", "key")
        self.text.insert(tk.END, f"  {'Carrier Discord':<18}{'Configured' if self.config.get('carrier_discord_webhook_url') else 'Not configured'}\n", "key")
        self.text.config(state=tk.DISABLED)

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
        self.win.destroy()
