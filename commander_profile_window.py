import json
import os
import time
import tkinter as tk
import webbrowser
from datetime import datetime, timezone
from tkinter import filedialog, messagebox, ttk

from config import (
    COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, get_active_profile, get_profile_dir,
    get_profile_file, save_config,
)
from ui_theme import (
    THEME, ThemedWindowMixin, apply_window, button, configure_ttk, scrollbar,
    window_surface,
)
import companion_features
from platform_support import open_path
from profile_backups import schedule_restore, snapshot_profile, validate_backup

COLOR_ACCENT = THEME.accent
COLOR_ORANGE = THEME.orange
COLOR_TEXT = THEME.text


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


class CommanderProfileWindow(ThemedWindowMixin):

    def __init__(self, root, app, embedded=False):
        self.root = root
        self.app = app
        self.config = app.config
        self.embedded = embedded
        self.win = window_surface(root, embedded=embedded)
        self.win.title("Commander Profile")
        self.win.geometry(self.config.get("profile_dashboard_geometry", "980x680"))
        apply_window(self.win)
        self.win.minsize(860, 560)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._wheel_bound = False
        self._last_queue_count = 0
        self._journal_snapshot_cache = {}
        self._journal_snapshot_profile = None
        self._folder_size_cache = {}
        self._credit_delta_cache = (0.0, None)
        self._achievement_cache_key = None
        self._achievement_cache = None
        self._tab_fingerprints = {}
        self._tab_canvases = {}
        self._tab_contents = {}
        self._refreshing = False
        self._refresh_pending = False
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
        header = tk.Frame(self.win, bg="#0c1014", height=66)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        title_box = tk.Frame(header, bg="#0c1014")
        title_box.pack(side=tk.LEFT, padx=14)
        tk.Label(title_box, text="COMMANDER RECORD", font=("Segoe UI", 16, "bold"), fg=COLOR_ACCENT, bg="#0c1014").pack(anchor="w", pady=(10, 0))
        tk.Label(title_box, text="career progression // fleet // responsibilities // profile custody", font=("Consolas", 8), fg=self.UI_MUTED, bg="#0c1014").pack(anchor="w", pady=(1, 0))
        self.summary = tk.Label(header, text="", font=("Consolas", 8), fg=self.UI_MUTED, bg="#0c1014")
        self.summary.pack(side=tk.RIGHT, padx=14)

        self.hero = self._band(self.win, border=COLOR_ACCENT)
        self.hero.pack(fill=tk.X, padx=10, pady=(10, 8))
        hero_body = tk.Frame(self.hero, bg=self.UI_PANEL)
        hero_body.pack(fill=tk.X, padx=14, pady=10)
        identity = tk.Frame(hero_body, bg=self.UI_PANEL)
        identity.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.hero_name = tk.Label(identity, text="-", fg=COLOR_ACCENT, bg=self.UI_PANEL, font=("Segoe UI", 19, "bold"), anchor="w")
        self.hero_name.pack(fill=tk.X)
        self.hero_fid = tk.Label(identity, text="-", fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Consolas", 8), anchor="w")
        self.hero_fid.pack(fill=tk.X)
        self.hero_ship = tk.Label(identity, text="-", fg=COLOR_TEXT, bg=self.UI_PANEL, font=("Consolas", 9, "bold"), anchor="w")
        self.hero_ship.pack(fill=tk.X, pady=(6, 0))

        hero_metrics = tk.Frame(hero_body, bg=self.UI_PANEL)
        hero_metrics.pack(side=tk.RIGHT, fill=tk.Y)
        self.hero_values = {}
        for idx, label in enumerate(("CREDITS", "CAREER", "SESSION")):
            card = tk.Frame(hero_metrics, bg=self.UI_PANEL_2, highlightbackground=self.UI_BORDER, highlightthickness=1)
            card.grid(row=0, column=idx, sticky="nsew", padx=(7 if idx else 0, 0))
            tk.Label(card, text=label, fg=self.UI_MUTED, bg=self.UI_PANEL_2, font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=9, pady=(5, 0))
            value = tk.Label(card, text="-", fg=COLOR_ACCENT if idx == 0 else COLOR_TEXT, bg=self.UI_PANEL_2, font=("Consolas", 9, "bold"), anchor="w", justify=tk.LEFT)
            value.pack(fill=tk.X, padx=9, pady=(2, 6))
            self.hero_values[label] = value

        style = configure_ttk(self.win, "CommanderProfile")
        style.configure("CommanderProfile.TNotebook", background=self.UI_BG, borderwidth=0)
        style.configure(
            "CommanderProfile.TNotebook.Tab", background=self.UI_PANEL,
            foreground=COLOR_TEXT, padding=(15, 7), borderwidth=0,
            font=("Segoe UI", 8, "bold"),
        )
        style.map(
            "CommanderProfile.TNotebook.Tab",
            background=[("selected", self.UI_PANEL_2)],
            foreground=[("selected", COLOR_ACCENT)],
        )
        self.tabs = ttk.Notebook(self.win, style="CommanderProfile.TNotebook")
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        for name in ("Career Overview", "Fleet & Loadouts", "Missions", "Data & Backups"):
            self._make_scroll_tab(name)
        self.tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        footer = tk.Frame(self.win, bg=self.UI_BG)
        footer.pack(fill=tk.X, padx=10, pady=(0, 8))
        self._button(footer, "Refresh", lambda: self.refresh(force=True)).pack(side=tk.LEFT)
        self.footer_hint = tk.Label(footer, text="Live events update only the visible profile section", font=("Consolas", 8), fg=self.UI_MUTED, bg=self.UI_BG)
        self.footer_hint.pack(side=tk.RIGHT)

    def _make_scroll_tab(self, name):
        tab = tk.Frame(self.tabs, bg=self.UI_BG)
        self.tabs.add(tab, text=name)
        canvas = tk.Canvas(tab, bg=self.UI_BG, highlightthickness=0, bd=0)
        bar = scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        content = tk.Frame(canvas, bg=self.UI_BG)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        content.bind("<Configure>", lambda _e, c=canvas: c.configure(scrollregion=c.bbox("all")))
        canvas.bind("<Configure>", lambda e, c=canvas, wid=window_id: c.itemconfigure(wid, width=e.width))
        canvas.bind("<Enter>", lambda _e, c=canvas: self._bind_mousewheel(canvas=c))
        canvas.bind("<Leave>", self._unbind_mousewheel)
        content.bind("<Enter>", lambda _e, c=canvas: self._bind_mousewheel(canvas=c))
        content.bind("<Leave>", self._unbind_mousewheel)
        self._tab_canvases[name] = canvas
        self._tab_contents[name] = content

    def _on_tab_changed(self, _event=None):
        if not self._refreshing:
            self.refresh(force=False)

    def _button(self, parent, text, cmd, accent=False):
        return button(parent, text, cmd, accent=accent, padx=12, pady=6)

    def _bind_mousewheel(self, _event=None, canvas=None):
        self.canvas = canvas or getattr(self, "canvas", None)
        if not self._wheel_bound:
            self.win.bind_all("<MouseWheel>", self._on_mousewheel)
            self._wheel_bound = True

    def _unbind_mousewheel(self, _event=None):
        if self._wheel_bound:
            self.win.unbind_all("<MouseWheel>")
            self._wheel_bound = False

    def _on_mousewheel(self, event):
        if not self.is_open():
            return
        try:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _clear_content(self, content=None):
        content = content or self._tab_contents.get(self._active_tab_name())
        if content is None:
            return
        for child in content.winfo_children():
            child.destroy()

    def _active_tab_name(self):
        try:
            return str(self.tabs.tab(self.tabs.select(), "text"))
        except Exception:
            return "Career Overview"

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
        lock = getattr(self.app, "db_lock", None)
        if lock is None or not lock.acquire(blocking=False):
            # The watcher processes journal batches while holding db_lock. It
            # can also be waiting for Tk to service a queued callback. Waiting
            # for that lock on the Tk thread creates a lock inversion and a
            # permanent Not Responding window, so show the last known count.
            return self._last_queue_count
        try:
            self._last_queue_count = self.app.conn.execute(
                "SELECT COUNT(*) FROM edsm_queue"
            ).fetchone()[0]
            return self._last_queue_count
        except Exception:
            return self._last_queue_count
        finally:
            lock.release()

    def _session_credit_delta(self):
        current = getattr(self.app, "cmdr_balance", None)
        start = getattr(self.app, "session_start_balance", None)
        if not isinstance(current, (int, float)) or not isinstance(start, (int, float)):
            return None
        return int(current) - int(start)

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

    @staticmethod
    def _mission_expiry_text(value):
        if not value:
            return ""
        try:
            expiry = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            remaining = int((expiry - datetime.now(timezone.utc)).total_seconds())
            if remaining <= 0:
                return "EXPIRED"
            hours, rem = divmod(remaining, 3600)
            minutes = rem // 60
            return f"{hours}h {minutes}m left"
        except Exception:
            return str(value)

    def _session_elapsed_text(self):
        try:
            elapsed = max(0, int(time.time() - float(getattr(self.app, "session_start_ts", time.time()))))
        except Exception:
            elapsed = 0
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

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

    def _latest_journal_snapshot(self, force=False):
        profile_key = get_active_profile(self.config)
        if (not force and self._journal_snapshot_profile == profile_key
                and self._journal_snapshot_cache):
            return self._journal_snapshot_cache
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
        if active_name in ("unknown commander", "cmdr"):
            active_name = ""
        active_fid = (self.config.get("active_commander_fid") or "").strip()
        snapshot = {
            "ranks": {}, "progress": {}, "reputation": {}, "statistics": {},
            "ship": {}, "balance": None, "loan": None,
        }
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
            file_snapshot = {
                "ranks": {}, "progress": {}, "reputation": {}, "statistics": {},
                "ship": {}, "balance": None, "loan": None,
            }
            for event in events:
                ev = event.get("event")
                if ev == "Rank":
                    file_snapshot["ranks"].update({k: v for k, v in event.items() if k not in ("timestamp", "event")})
                elif ev == "Progress":
                    file_snapshot["progress"].update({k: v for k, v in event.items() if k not in ("timestamp", "event")})
                elif ev == "Reputation":
                    file_snapshot["reputation"].update({k: v for k, v in event.items() if k not in ("timestamp", "event")})
                elif ev == "Statistics":
                    file_snapshot["statistics"] = {
                        k: v for k, v in event.items() if k not in ("timestamp", "event")
                    }
                elif ev == "LoadGame":
                    file_snapshot["balance"] = event.get("Credits")
                    file_snapshot["loan"] = event.get("Loan")
                    file_snapshot["ship"], _ = companion_features.update_active_ship(
                        file_snapshot["ship"], ev, event
                    )
                elif ev in ("Loadout", "ShipyardBuy", "ShipyardNew",
                            "ShipyardSwap", "SetUserShipName"):
                    file_snapshot["ship"], _ = companion_features.update_active_ship(
                        file_snapshot["ship"], ev, event
                    )
            # Files are newest first. Fill each category once so an older
            # journal can provide missing Statistics without overwriting the
            # newest ship, balance or rank snapshot.
            for key in ("ranks", "progress", "reputation", "statistics", "ship"):
                if not snapshot[key] and file_snapshot[key]:
                    snapshot[key] = file_snapshot[key]
            if snapshot["balance"] is None and file_snapshot["balance"] is not None:
                snapshot["balance"] = file_snapshot["balance"]
                snapshot["loan"] = file_snapshot["loan"]
            if (snapshot["statistics"] and
                    (snapshot["ranks"] or snapshot["ship"] or snapshot["balance"] is not None)):
                break
        result = snapshot if matched_file else {}
        self._journal_snapshot_profile = profile_key
        self._journal_snapshot_cache = result
        return result

    def _cached_session_credit_delta(self, force=False):
        cached_at, cached_value = self._credit_delta_cache
        if not force and time.monotonic() - cached_at < 20.0:
            return cached_value
        value = self._session_credit_delta()
        self._credit_delta_cache = (time.monotonic(), value)
        return value

    def _cached_folder_size(self, path, force=False):
        cached_at, cached_value = self._folder_size_cache.get(path, (0.0, 0))
        if force or time.monotonic() - cached_at >= 60.0:
            cached_value = self._folder_size(path)
            self._folder_size_cache[path] = (time.monotonic(), cached_value)
        return cached_value

    @staticmethod
    def _stat_value(statistics, *names):
        wanted = {str(name).lower() for name in names}
        pending = [statistics]
        while pending:
            current = pending.pop()
            if not isinstance(current, dict):
                continue
            for key, value in current.items():
                if str(key).lower() in wanted and not isinstance(value, (dict, list)):
                    return value
                if isinstance(value, dict):
                    pending.append(value)
        return None

    @staticmethod
    def _fmt_number(value, decimals=0):
        if not isinstance(value, (int, float)):
            return "-"
        if decimals:
            return f"{float(value):,.{decimals}f}"
        return f"{int(value):,}"

    @staticmethod
    def _fingerprint(value):
        try:
            return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
        except Exception:
            return repr(value)

    def _achievement_summary(self):
        engine = getattr(self.app, "achievement_engine", None)
        if engine is None:
            return {"unlocked": 0, "total": 0, "totalPoints": 0, "recent": []}
        state = getattr(engine, "state", {}) or {}
        unlocked_ids = tuple(sorted(
            (key, str(record.get("unlockedAt") or "") if isinstance(record, dict) else "")
            for key, record in (state.get("unlocked") or {}).items()
        ))
        cache_key = (
            id(engine), unlocked_ids,
            tuple(sorted(getattr(engine, "disabled_categories", ()) or ())),
        )
        if cache_key == self._achievement_cache_key and self._achievement_cache is not None:
            return self._achievement_cache
        try:
            snapshot = engine.snapshot()
        except Exception:
            return {"unlocked": 0, "total": 0, "totalPoints": 0, "recent": []}
        recent = sorted(
            (row for row in snapshot.get("achievements", []) if row.get("unlocked")),
            key=lambda row: str(row.get("unlockedAt") or ""), reverse=True,
        )[:6]
        result = {
            "unlocked": int(snapshot.get("unlocked") or 0),
            "total": int(snapshot.get("total") or 0),
            "totalPoints": int(snapshot.get("totalPoints") or 0),
            "recent": recent,
        }
        self._achievement_cache_key = cache_key
        self._achievement_cache = result
        return result

    def _captain_summary(self):
        log = getattr(self.app, "captains_log", None)
        try:
            sessions = log.sessions() if log is not None else []
        except Exception:
            sessions = []
        totals = {
            "sessions": len(sessions), "jumps": 0, "distance_ly": 0.0,
            "codex": 0, "bio_analyses": 0, "trade_profit": 0,
            "exploration_sales": 0, "biology_sales": 0, "highlights": [],
        }
        for session in sessions:
            for key in ("jumps", "codex", "bio_analyses", "trade_profit", "exploration_sales", "biology_sales"):
                totals[key] += int(session.get(key) or 0)
            totals["distance_ly"] += float(session.get("distance_ly") or 0)
        for session in sessions[:8]:
            totals["highlights"].extend(reversed(session.get("highlights") or []))
            if len(totals["highlights"]) >= 8:
                break
        totals["highlights"] = totals["highlights"][:8]
        return totals

    def _profile_model(self, active_tab, force=False):
        profile_key = get_active_profile(self.config)
        journal = self._latest_journal_snapshot(force=force)
        companion_state = getattr(self.app, "companion_state", {}) or {}
        ship = dict(journal.get("ship") or {})
        live_ship = dict(getattr(self.app, "cmdr_ship", {}) or {})
        journal_id = ship.get("ship_id")
        live_id = live_ship.get("ship_id")
        journal_type = ship.get("ship")
        live_type = live_ship.get("ship")
        identity_changed = bool(
            (journal_id is not None and live_id is not None
             and str(journal_id) != str(live_id))
            or (journal_type and live_type
                and str(journal_type).casefold() != str(live_type).casefold())
        )
        if identity_changed:
            ship = live_ship
        else:
            # Empty name/ident values are authoritative for a newly bought
            # vessel and must replace the outgoing ship's journal values.
            ship.update(live_ship)
        ranks = dict(journal.get("ranks") or {})
        ranks.update(getattr(self.app, "cmdr_ranks", {}) or {})
        progress = dict(journal.get("progress") or {})
        progress.update(getattr(self.app, "cmdr_rank_progress", {}) or {})
        reputation = dict(journal.get("reputation") or {})
        reputation.update(getattr(self.app, "cmdr_reputation", {}) or {})
        balance = getattr(self.app, "cmdr_balance", None)
        loan = getattr(self.app, "cmdr_loan", None)
        if balance is None:
            balance = journal.get("balance")
        if loan is None:
            loan = journal.get("loan")
        statistics = companion_state.get("statistics") or journal.get("statistics") or {}
        model = {
            "profile_key": profile_key,
            "profile_dir": get_profile_dir(profile_key),
            "name": self.config.get("active_commander_name") or "Unknown Commander",
            "fid": self.config.get("active_commander_fid") or "",
            "balance": balance, "loan": loan, "ship": ship,
            "ranks": ranks, "progress": progress, "reputation": reputation,
            "statistics": statistics, "companion_state": companion_state,
        }
        if active_tab == "Career Overview":
            model["credit_delta"] = self._cached_session_credit_delta(force=force)
            model["achievements"] = self._achievement_summary()
            model["captain"] = self._captain_summary()
        elif active_tab == "Fleet & Loadouts":
            model["carrier"] = dict(getattr(getattr(self.app, "carrier_tracker", None), "carrier_data", {}) or {})
        elif active_tab == "Missions":
            model["cargo"] = list(getattr(self.app, "current_cargo_inventory", []) or [])
        elif active_tab == "Data & Backups":
            model["paths"] = [
                ("Exploration DB", getattr(self.app, "db_path", "")),
                ("Mining DB", self.config.get("mining_db_file", "")),
                ("Waypoints", self.config.get("waypoints_file", "")),
                ("Carrier State", self.config.get("carrier_state_file", "")),
                ("Colonisation", self.config.get("colonisation_data_file", "")),
                ("Engineer Materials", self.config.get("engineer_materials_file", "")),
                ("Companion State", self.config.get("companion_state_file", "")),
                ("Achievements", get_profile_file(profile_key, "achievements_state.json")),
                ("Captain's Log", get_profile_file(profile_key, "captains_log.json")),
            ]
            model["folder_size"] = self._cached_folder_size(model["profile_dir"], force=force)
            model["queue_count"] = self._queue_count()
        return model

    def _update_hero(self, model):
        ship = model["ship"]
        ship_type = ship.get("ship_localised") or ship.get("ship") or "-"
        ship_name = ship.get("ship_name") or ship_type
        ship_ident = ship.get("ship_ident") or "-"
        self.summary.config(text=model["profile_key"])
        self.hero_name.config(text=model["name"].upper())
        self.hero_fid.config(text=model["fid"] or model["profile_key"])
        self.hero_ship.config(text=f"{ship_name}  |  {ship_type}  |  {ship_ident}")
        self.hero_values["CREDITS"].config(text=self._fmt_credits(model["balance"]))
        achievement_state = getattr(getattr(self.app, "achievement_engine", None), "state", {}) or {}
        unlocked = len(achievement_state.get("unlocked") or {})
        sessions = len((getattr(getattr(self.app, "captains_log", None), "data", {}) or {}).get("sessions") or [])
        self.hero_values["CAREER"].config(text=f"{unlocked} awards\n{sessions} logged flights")
        self.hero_values["SESSION"].config(
            text=f"{self._session_elapsed_text()}\n{getattr(self.app, 'session_jump_count', 0)} jumps"
        )

    def refresh(self, force=False):
        if self._refreshing or not self.is_open():
            return
        self._refreshing = True
        try:
            active_tab = self._active_tab_name()
            model = self._profile_model(active_tab, force=force)
            self._update_hero(model)
            content = self._tab_contents[active_tab]
            fingerprint_model = {key: value for key, value in model.items() if key != "companion_state"}
            companion_keys = {
                "Career Overview": ("statistics",),
                "Fleet & Loadouts": ("stored_ships", "loadout"),
                "Missions": ("missions", "faction_kills"),
                "Data & Backups": (),
            }[active_tab]
            fingerprint_model["companion_state"] = {
                key: model["companion_state"].get(key)
                for key in companion_keys
            }
            fingerprint = self._fingerprint(fingerprint_model)
            if not force and self._tab_fingerprints.get(active_tab) == fingerprint:
                return
            self._tab_fingerprints[active_tab] = fingerprint
            self._clear_content(content)
            {
                "Career Overview": self._render_career,
                "Fleet & Loadouts": self._render_fleet,
                "Missions": self._render_missions,
                "Data & Backups": self._render_data,
            }[active_tab](content, model)
            content.update_idletasks()
            canvas = self._tab_canvases[active_tab]
            canvas.configure(scrollregion=canvas.bbox("all"))
            self.footer_hint.config(text=f"{active_tab} updated {time.strftime('%H:%M:%S')} // selective live refresh")
        finally:
            self._refreshing = False

    def _two_columns(self, parent, left_weight=1, right_weight=1):
        grid = tk.Frame(parent, bg=self.UI_BG)
        grid.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        grid.grid_columnconfigure(0, weight=left_weight, uniform="profile_columns")
        grid.grid_columnconfigure(1, weight=right_weight, uniform="profile_columns")
        left = tk.Frame(grid, bg=self.UI_BG)
        right = tk.Frame(grid, bg=self.UI_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        return left, right

    def _render_career(self, parent, model):
        left, right = self._two_columns(parent, 1, 1)
        ranks_card = self._band(left, border=COLOR_ACCENT)
        ranks_card.pack(fill=tk.X, pady=(0, 8))
        self._section_label(ranks_card, "CAREER RANKS")
        rank_count = 0
        for category in ("Combat", "Trade", "Explore", "Soldier", "Exobiologist", "Empire", "Federation", "CQC"):
            if category not in model["ranks"] and category not in model["progress"]:
                continue
            rank = self._rank_label(category, model["ranks"].get(category))
            progress = model["progress"].get(category)
            self._bar_row(ranks_card, category, f"{rank}  {self._fmt_percent(progress)}", progress, COLOR_ACCENT)
            rank_count += 1
        if not rank_count:
            self._kv_row(ranks_card, "Ranks", "Awaiting Rank and Progress journal data", fg=self.UI_MUTED)

        rep_card = self._panel(left)
        rep_card.pack(fill=tk.X, pady=(0, 8))
        self._section_label(rep_card, "SUPERPOWER REPUTATION")
        shown = False
        for key in ("Federation", "Empire", "Alliance", "Independent"):
            if key in model["reputation"]:
                shown = True
                value = model["reputation"].get(key)
                self._bar_row(rep_card, key, self._fmt_percent(value), value, COLOR_ORANGE)
        if not shown:
            self._kv_row(rep_card, "Reputation", "Awaiting Reputation journal data", fg=self.UI_MUTED)

        stats = model["statistics"]
        records = self._panel(left)
        records.pack(fill=tk.X, pady=(0, 8))
        self._section_label(records, "CAREER RECORDS")
        stats_grid = tk.Frame(records, bg=self.UI_PANEL)
        stats_grid.pack(fill=tk.X, padx=7, pady=(0, 8))
        for col in range(2):
            stats_grid.grid_columnconfigure(col, weight=1, uniform="career_stats")
        career_metrics = (
            ("SYSTEMS VISITED", self._fmt_number(self._stat_value(stats, "Systems_Visited")), "Journal Statistics"),
            ("HYPERSPACE", f"{self._fmt_number(self._stat_value(stats, 'Total_Hyperspace_Distance'), 1)} ly", f"{self._fmt_number(self._stat_value(stats, 'Total_Hyperspace_Jumps'))} jumps"),
            ("EXPLORATION PROFIT", self._fmt_credits(self._stat_value(stats, "Exploration_Profits")), f"best {self._fmt_credits(self._stat_value(stats, 'Highest_Payout'))}"),
            ("FIRST FOOTFALLS", self._fmt_number(self._stat_value(stats, "First_Footfalls")), f"{self._fmt_number(self._stat_value(stats, 'Planet_Footfalls'))} total footfalls"),
            ("MARKET PROFIT", self._fmt_credits(self._stat_value(stats, "Market_Profits")), f"{self._fmt_number(self._stat_value(stats, 'Markets_Traded_With'))} markets"),
            ("MINING PROFIT", self._fmt_credits(self._stat_value(stats, "Mining_Profits")), f"{self._fmt_number(self._stat_value(stats, 'Quantity_Mined'))} refined"),
            ("BOUNTIES", self._fmt_number(self._stat_value(stats, "Bounties_Claimed")), self._fmt_credits(self._stat_value(stats, "Bounty_Hunting_Profit"))),
            ("ORGANIC DATA", self._fmt_credits(self._stat_value(stats, "Organic_Data_Profits")), f"{self._fmt_number(self._stat_value(stats, 'Organic_Species_Encountered'))} species"),
        )
        for idx, (title, value, detail) in enumerate(career_metrics):
            self._metric_card(stats_grid, title, value, detail, idx // 2, idx % 2, accent=idx == 0)
        if not stats:
            self._kv_row(records, "Statistics", "Elite will supply lifetime records through its Statistics event", fg=self.UI_MUTED)

        achievements = model["achievements"]
        award_card = self._band(right, border=COLOR_ORANGE)
        award_card.pack(fill=tk.X, pady=(0, 8))
        self._section_label(award_card, "ACHIEVEMENTS")
        award_grid = tk.Frame(award_card, bg=self.UI_PANEL)
        award_grid.pack(fill=tk.X, padx=7, pady=(0, 6))
        for col in range(3):
            award_grid.grid_columnconfigure(col, weight=1, uniform="award_stats")
        completion = (achievements["unlocked"] / achievements["total"] * 100) if achievements["total"] else 0
        self._metric_card(award_grid, "UNLOCKED", f"{achievements['unlocked']}/{achievements['total']}", f"{completion:.1f}% complete", 0, 0, accent=True)
        self._metric_card(award_grid, "POINTS", self._fmt_number(achievements["totalPoints"]), "earned", 0, 1)
        self._metric_card(award_grid, "RECENT", self._fmt_number(len(achievements["recent"])), "latest milestones", 0, 2)
        for row in achievements["recent"]:
            when = str(row.get("unlockedAt") or "")[:10] or "Unlocked"
            self._kv_row(award_card, row.get("category") or "Award", f"{row.get('title') or row.get('id')} · {when}", fg=COLOR_ACCENT)
        if not achievements["recent"]:
            self._kv_row(award_card, "Milestones", "No achievements unlocked yet", fg=self.UI_MUTED)

        captain = model["captain"]
        log_card = self._panel(right)
        log_card.pack(fill=tk.X, pady=(0, 8))
        self._section_label(log_card, "CAPTAIN'S LOG TOTALS")
        log_grid = tk.Frame(log_card, bg=self.UI_PANEL)
        log_grid.pack(fill=tk.X, padx=7, pady=(0, 6))
        for col in range(2):
            log_grid.grid_columnconfigure(col, weight=1, uniform="log_stats")
        for idx, (title, value, detail) in enumerate((
            ("FLIGHTS", self._fmt_number(captain["sessions"]), "logged sessions"),
            ("TRAVEL", f"{captain['distance_ly']:,.1f} ly", f"{captain['jumps']:,} jumps"),
            ("DISCOVERIES", self._fmt_number(captain["codex"]), f"{captain['bio_analyses']:,} bio analyses"),
            ("DATA SALES", self._fmt_credits(captain["exploration_sales"] + captain["biology_sales"]), "exploration + biology"),
        )):
            self._metric_card(log_grid, title, value, detail, idx // 2, idx % 2, accent=idx == 0)
        self._section_label(log_card, "RECENT CAREER HIGHLIGHTS")
        for row in captain["highlights"][:6]:
            detail = f" · {row.get('detail')}" if row.get("detail") else ""
            self._kv_row(log_card, row.get("kind") or "Log", f"{row.get('title') or 'Event'}{detail}")
        if not captain["highlights"]:
            self._kv_row(log_card, "Chronicle", "Captain's Log will collect notable sessions and discoveries", fg=self.UI_MUTED)

    def _render_fleet(self, parent, model):
        left, right = self._two_columns(parent, 3, 2)
        ship = model["ship"]
        companion_state = model["companion_state"]
        active = self._band(left, border=COLOR_ACCENT)
        active.pack(fill=tk.X, pady=(0, 8))
        self._section_label(active, "ACTIVE SHIP & LOADOUT")
        ship_type = ship.get("ship_localised") or ship.get("ship") or "-"
        ship_name = ship.get("ship_name") or ship_type
        for key, value in (
            ("Name", ship_name), ("Type", ship_type), ("Ident", ship.get("ship_ident") or "-"),
            ("Ship ID", ship.get("ship_id") or "-"),
            ("Cargo Capacity", f"{ship.get('cargo_capacity')} t" if ship.get("cargo_capacity") is not None else "-"),
            ("Jump Range", f"{float(ship.get('max_jump_range')):.2f} ly" if isinstance(ship.get("max_jump_range"), (int, float)) else "-"),
            ("Rebuy", self._fmt_credits(ship.get("rebuy"))),
            ("Modules", self._fmt_credits(ship.get("modules_value"))),
            ("Hull", f"{float(ship.get('hull_health')) * 100:.1f}%" if isinstance(ship.get("hull_health"), (int, float)) else "-"),
            ("Mode", ship.get("game_mode") or "-"), ("Group", ship.get("group") or "-"),
        ):
            self._kv_row(active, key, value)
        actions = tk.Frame(active, bg=self.UI_PANEL)
        actions.pack(fill=tk.X, padx=12, pady=(8, 10))
        edsy = self._button(actions, "Open in EDSY", self._open_loadout_edsy, accent=True)
        edsy.pack(side=tk.LEFT)
        slef = self._button(actions, "Copy SLEF", self._copy_loadout_slef)
        slef.pack(side=tk.LEFT, padx=(8, 0))
        if not companion_state.get("loadout"):
            edsy.config(state=tk.DISABLED)
            slef.config(state=tk.DISABLED)

        fleet = companion_state.get("stored_ships") or {}
        rows = list(fleet.get("here") or []) + list(fleet.get("remote") or [])
        fleet_card = self._panel(left)
        fleet_card.pack(fill=tk.X, pady=(0, 8))
        self._section_label(fleet_card, f"STORED FLEET · {len(rows)} SHIPS")
        for stored in rows:
            location = stored.get("system") or fleet.get("system") or fleet.get("station") or "Local shipyard"
            detail = location
            if stored.get("in_transit"):
                detail += " · IN TRANSIT"
            elif stored.get("transfer_cr"):
                detail += f" · transfer {self._fmt_credits(stored.get('transfer_cr'))}"
            self._kv_row(fleet_card, stored.get("name") or stored.get("type") or "Ship", detail, fg="#ff7777" if stored.get("hot") else COLOR_TEXT)
        if not rows:
            self._kv_row(fleet_card, "Fleet", "Open a shipyard in Elite to sync stored ships", fg=self.UI_MUTED)

        carrier = model.get("carrier") or {}
        carrier_card = self._band(right, border=COLOR_ORANGE)
        carrier_card.pack(fill=tk.X, pady=(0, 8))
        self._section_label(carrier_card, "FLEET CARRIER")
        if carrier.get("carrier_id") or carrier.get("callsign"):
            for key, value in (
                ("Carrier", carrier.get("name") or carrier.get("callsign") or "-"),
                ("Callsign", carrier.get("callsign") or "-"),
                ("Location", carrier.get("system") or "-"),
                ("Status", str(carrier.get("status") or "idle").upper()),
                ("Tritium", f"{carrier.get('fuel_level'):,} t" if isinstance(carrier.get("fuel_level"), (int, float)) else "-"),
                ("Balance", self._fmt_credits(carrier.get("balance"))),
                ("Expedition", carrier.get("expedition_name") or "No active expedition"),
            ):
                self._kv_row(carrier_card, key, value)
            open_carrier = getattr(self.app, "open_carrier_window", None)
            if callable(open_carrier):
                self._button(carrier_card, "Open Carrier Navigator", open_carrier, accent=True).pack(anchor="w", padx=12, pady=(8, 10))
        else:
            self._kv_row(carrier_card, "Carrier", "No owned fleet carrier data has been received", fg=self.UI_MUTED)

        identity = self._panel(right)
        identity.pack(fill=tk.X, pady=(0, 8))
        self._section_label(identity, "FLEET IDENTITY")
        self._kv_row(identity, "Active vessel", ship_name)
        self._kv_row(identity, "Stored vessels", self._fmt_number(len(rows)))
        hot = sum(1 for row in rows if row.get("hot"))
        self._kv_row(identity, "Hot ships", self._fmt_number(hot), fg="#ff7777" if hot else self.UI_MUTED)
        self._kv_row(identity, "Loadout export", "Ready" if companion_state.get("loadout") else "Awaiting Loadout event", fg=COLOR_ACCENT if companion_state.get("loadout") else self.UI_MUTED)

    def _render_missions(self, parent, model):
        companion_state = model["companion_state"]
        missions = list((companion_state.get("missions") or {}).values())
        cargo_by_symbol = {}
        for item in model.get("cargo") or []:
            symbol = str(item.get("Name") or item.get("name") or "").strip("$;").lower().removesuffix("_name")
            cargo_by_symbol[symbol] = cargo_by_symbol.get(symbol, 0) + int(item.get("Count", item.get("count", 0)) or 0)
        stacks = companion_features.massacre_stacks(companion_state)
        expiring = sum(1 for row in missions if "h left" in self._mission_expiry_text(row.get("expiry")) and int(self._mission_expiry_text(row.get("expiry")).split("h", 1)[0]) < 3)
        summary = self._band(parent, border=COLOR_ACCENT)
        summary.pack(fill=tk.X, padx=2, pady=(2, 8))
        self._section_label(summary, "MISSION RESPONSIBILITIES")
        grid = tk.Frame(summary, bg=self.UI_PANEL)
        grid.pack(fill=tk.X, padx=7, pady=(0, 8))
        for col in range(3):
            grid.grid_columnconfigure(col, weight=1, uniform="mission_summary")
        self._metric_card(grid, "ACTIVE", self._fmt_number(len(missions)), "tracked missions", 0, 0, accent=True)
        self._metric_card(grid, "EXPIRING", self._fmt_number(expiring), "under three hours", 0, 1)
        self._metric_card(grid, "MASSACRE STACKS", self._fmt_number(len(stacks)), f"{sum(int(row.get('reward') or 0) for row in stacks):,} cr rewards", 0, 2)

        mission_card = self._panel(parent)
        mission_card.pack(fill=tk.X, padx=2, pady=(0, 8))
        self._section_label(mission_card, "ACTIVE MISSIONS")
        for mission in sorted(missions, key=lambda row: row.get("expiry") or ""):
            destination = " · ".join(value for value in (mission.get("destination_system"), mission.get("destination_station")) if value)
            details = []
            if destination:
                details.append(destination)
            if mission.get("to_deliver"):
                details.append(f"{mission.get('delivered') or 0}/{mission['to_deliver']} delivered")
            elif mission.get("commodity_symbol") and mission.get("count"):
                held = cargo_by_symbol.get(mission["commodity_symbol"], 0)
                details.append(f"cargo {held}/{mission['count']}")
            expiry = self._mission_expiry_text(mission.get("expiry"))
            if expiry:
                details.append(expiry)
            self._kv_row(mission_card, mission.get("kind") or "Mission", f"{mission.get('name') or 'Mission'} · {' · '.join(details) or 'No destination'}", fg=COLOR_ORANGE if expiry == "EXPIRED" else COLOR_TEXT)
        if not missions:
            self._kv_row(mission_card, "Missions", "No active tracked missions", fg=self.UI_MUTED)

        stack_card = self._panel(parent)
        stack_card.pack(fill=tk.X, padx=2, pady=(0, 8))
        self._section_label(stack_card, "MASSACRE STACKS")
        for stack in stacks:
            self._bar_row(stack_card, stack["faction"], f"{stack['kills_done']}/{stack['kills_needed']} kills · {self._fmt_credits(stack['reward'])}", (stack["kills_done"] / stack["kills_needed"] * 100) if stack["kills_needed"] else 0, "#21d189" if stack["complete"] else COLOR_ORANGE)
        if not stacks:
            self._kv_row(stack_card, "Stacks", "No active massacre mission stacks", fg=self.UI_MUTED)

    def _render_data(self, parent, model):
        left, right = self._two_columns(parent, 3, 2)
        storage = self._band(left, border=COLOR_ACCENT)
        storage.pack(fill=tk.X, pady=(0, 8))
        self._section_label(storage, "PROFILE STORAGE")
        self._kv_row(storage, "Profile", model["profile_key"])
        self._kv_row(storage, "Folder", model["profile_dir"])
        self._kv_row(storage, "Size", self._fmt_bytes(model.get("folder_size")))
        for label, path in model.get("paths") or []:
            exists = bool(path and os.path.exists(path))
            self._kv_row(storage, label, f"{'OK' if exists else 'missing'}  {path or '-'}", fg=COLOR_TEXT if exists else "#ff9a3c")

        actions = self._panel(left)
        actions.pack(fill=tk.X, pady=(0, 8))
        self._section_label(actions, "PROFILE CUSTODY")
        tk.Label(actions, text="Backups include the active commander's databases, route state, achievements, Captain's Log and exploration data.", wraplength=590, justify=tk.LEFT, font=("Consolas", 8), fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w").pack(fill=tk.X, padx=12, pady=(0, 8))
        action_row = tk.Frame(actions, bg=self.UI_PANEL)
        action_row.pack(fill=tk.X, padx=12, pady=(0, 10))
        self._button(action_row, "Open Profile Folder", self._open_profile_folder, accent=True).pack(side=tk.LEFT)
        self._button(action_row, "Backup Profile", self._backup_profile).pack(side=tk.LEFT, padx=(8, 0))
        self._button(action_row, "Restore Backup", self._restore_profile).pack(side=tk.LEFT, padx=(8, 0))

        integrations = self._band(right, border=COLOR_ORANGE)
        integrations.pack(fill=tk.X, pady=(0, 8))
        self._section_label(integrations, "INTEGRATIONS")
        self._kv_row(integrations, "EDSM upload", "ON" if self.config.get("edsm_upload_enabled") else "OFF", fg=COLOR_ACCENT if self.config.get("edsm_upload_enabled") else self.UI_MUTED)
        self._kv_row(integrations, "EDSM queue", f"{model.get('queue_count', 0)} pending events")
        self._kv_row(integrations, "Carrier Discord", "CONFIGURED" if self.config.get("carrier_discord_webhook_url") else "OFF", fg=COLOR_ACCENT if self.config.get("carrier_discord_webhook_url") else self.UI_MUTED)

        identity = self._panel(right)
        identity.pack(fill=tk.X, pady=(0, 8))
        self._section_label(identity, "PROFILE IDENTITY")
        self._kv_row(identity, "Commander", model["name"])
        self._kv_row(identity, "FID", model["fid"] or "-")
        self._kv_row(identity, "Credits", self._fmt_credits(model["balance"]))
        self._kv_row(identity, "Loan", self._fmt_credits(model["loan"]))
        self._kv_row(identity, "Journal folder", self.config.get("journal_path") or "Not configured", fg=COLOR_TEXT if self.config.get("journal_path") else "#ff9a3c")

    def _open_loadout_edsy(self):
        loadout = (getattr(self.app, "companion_state", {}) or {}).get("loadout")
        if not loadout:
            messagebox.showinfo("Ship Export", "No full Loadout event has been received yet.", parent=self.win)
            return
        webbrowser.open(companion_features.edsy_url(loadout))

    def _copy_loadout_slef(self):
        loadout = (getattr(self.app, "companion_state", {}) or {}).get("loadout")
        if not loadout:
            messagebox.showinfo("Ship Export", "No full Loadout event has been received yet.", parent=self.win)
            return
        self.win.clipboard_clear()
        self.win.clipboard_append(companion_features.slef(loadout))
        self.win.update_idletasks()
        messagebox.showinfo("Ship Export", "SLEF copied for Coriolis, Inara or EDSY.", parent=self.win)

    def _open_profile_folder(self):
        path = get_profile_dir(get_active_profile(self.config))
        if not open_path(path):
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
            snapshot_profile(src, dst)
            messagebox.showinfo("Backup Complete", f"Profile copied to:\n{dst}", parent=self.win)
        except Exception as exc:
            messagebox.showerror("Backup Failed", str(exc), parent=self.win)

    def _restore_profile(self):
        source = filedialog.askdirectory(title="Choose VoidCompass profile backup", parent=self.win)
        if not source:
            return
        valid, detail = validate_backup(source)
        if not valid:
            messagebox.showerror("Restore Backup", detail, parent=self.win)
            return
        if not messagebox.askyesno(
            "Restore Commander Profile",
            "Restore this backup into the active commander profile?\n\n"
            "The current profile is automatically preserved as a rollback snapshot. "
            "The restore takes effect after VoidCompass is closed and started again.",
            parent=self.win,
        ):
            return
        try:
            schedule_restore(source, get_active_profile(self.config))
        except Exception as exc:
            messagebox.showerror("Restore Backup", str(exc), parent=self.win)
            return
        messagebox.showinfo(
            "Restore Scheduled",
            "The profile backup will be restored on the next VoidCompass start.\n\n"
            "Close the application normally, then open it again.",
            parent=self.win,
        )

    def _on_close(self):
        try:
            self.config["profile_dashboard_geometry"] = self.win.geometry()
            save_config(self.config)
        except Exception:
            pass
        self._unbind_mousewheel()
        self.win.destroy()
