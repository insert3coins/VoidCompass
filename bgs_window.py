"""
bgs_window.py — BGS (Background Simulation) Tracker for VoidCompass.

Stores faction influence snapshots for every inhabited system visited.
Shows live influence %, trend vs. the previous visit, government/allegiance,
and active/pending BGS states.
"""

import tkinter as tk
from datetime import datetime
from typing import Callable

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config

# State → colour tag (used in the Text widget)
_STATE_TAG: dict[str, str] = {
    "War":          "state_war",
    "CivilWar":     "state_war",
    "Bust":         "state_war",
    "PirateAttack": "state_war",
    "Famine":       "state_neg",
    "Lockdown":     "state_neg",
    "CivilUnrest":  "state_neg",
    "Outbreak":     "state_neg",
    "Boom":         "state_pos",
    "Expansion":    "state_pos",
    "CivilLiberty": "state_pos",
    "Investment":   "state_pos",
    "Election":     "state_neu",
    "PublicHoliday":"state_neu",
    "Retreat":      "state_neg",
    "Infrastructure Failure": "state_neg",
}

_ALLEGIANCE_TAG: dict[str, str] = {
    "Federation":        "ally_fed",
    "Empire":            "ally_emp",
    "Alliance":          "ally_all",
    "Independent":       "ally_ind",
    "Pilots Federation": "ally_pf",
}


class BGSWindow:
    UI_BG     = "#080a0d"
    UI_PANEL  = "#12161b"
    UI_BORDER = "#26313a"
    UI_MUTED  = "#7d8891"
    UI_DIM    = "#4e5962"

    def __init__(
        self,
        root,
        config: dict,
        load_systems_cb:  Callable[[], list],
        load_factions_cb: Callable[[str], list],
    ):
        """
        load_systems_cb  — () → [(system_name, last_updated_epoch)]
        load_factions_cb — (system_name) → list of snapshot dicts
        """
        self.root              = root
        self.config            = config
        self._load_systems     = load_systems_cb
        self._load_factions    = load_factions_cb
        self._selected_system: str | None = None

        self.win = tk.Toplevel(root)
        self.win.title("BGS Tracker — Void Compass")
        self.win.configure(bg=self.UI_BG)
        self.win.geometry(config.get("bgs_window_geometry", "880x580"))
        self.win.resizable(True, True)
        self.win.minsize(660, 420)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._reload_list()

        # Auto-select the most recently updated system
        systems = self._load_systems()
        if systems:
            self._select_system(systems[0][0])

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def is_open(self) -> bool:
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False

    def lift(self):
        try:
            self.win.lift()
            self.win.focus_force()
        except Exception:
            pass

    def refresh_current(self):
        """Reload the system list and re-render the selected system."""
        if not self.is_open():
            return
        self.win.after(0, self._do_refresh)

    def _do_refresh(self):
        self._reload_list()
        if self._selected_system:
            self._render_factions(self._selected_system)

    def _on_close(self):
        try:
            self.config["bgs_window_geometry"] = self.win.geometry()
            save_config(self.config)
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Header bar
        hdr = tk.Frame(self.win, bg="#0c1014", height=46)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="BGS TRACKER",
                 font=("Segoe UI", 13, "bold"), fg=COLOR_ACCENT, bg="#0c1014"
                 ).pack(side=tk.LEFT, padx=14, pady=8)
        self._sys_count_lbl = tk.Label(hdr, text="",
                                        fg=self.UI_DIM, bg="#0c1014",
                                        font=("Consolas", 8))
        self._sys_count_lbl.pack(side=tk.RIGHT, padx=14)

        # Main split: left list + right detail
        main = tk.Frame(self.win, bg=self.UI_BG)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 8))

        # ── Left: system list ─────────────────────────────────────────────────
        left = tk.Frame(main, bg=self.UI_PANEL, width=230)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        left.pack_propagate(False)

        tk.Label(left, text="SYSTEMS",
                 font=("Segoe UI", 8, "bold"), fg=COLOR_ORANGE, bg=self.UI_PANEL
                 ).pack(anchor="w", padx=10, pady=(10, 2))

        # Search entry
        search_wrap = tk.Frame(
            left, bg="#0b0e12",
            highlightbackground=self.UI_BORDER, highlightthickness=1)
        search_wrap.pack(fill=tk.X, padx=6, pady=(0, 4))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._reload_list())
        tk.Entry(search_wrap, textvariable=self._search_var,
                 bg="#0b0e12", fg=COLOR_TEXT, insertbackground=COLOR_ACCENT,
                 font=("Consolas", 9), relief=tk.FLAT, bd=4,
                 ).pack(fill=tk.X)

        list_wrap = tk.Frame(left, bg=self.UI_PANEL)
        list_wrap.pack(fill=tk.BOTH, expand=True, padx=4)

        list_scroll = tk.Scrollbar(list_wrap, orient=tk.VERTICAL)
        self._list_canvas = tk.Canvas(list_wrap, bg=self.UI_PANEL,
                                       highlightthickness=0,
                                       yscrollcommand=list_scroll.set)
        list_scroll.config(command=self._list_canvas.yview)
        self._list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._list_inner = tk.Frame(self._list_canvas, bg=self.UI_PANEL)
        self._list_wid = self._list_canvas.create_window(
            (0, 0), window=self._list_inner, anchor="nw")
        self._list_inner.bind(
            "<Configure>",
            lambda e: self._list_canvas.configure(
                scrollregion=self._list_canvas.bbox("all")))
        self._list_canvas.bind(
            "<Configure>",
            lambda e: self._list_canvas.itemconfig(self._list_wid, width=e.width))
        self._list_canvas.bind(
            "<MouseWheel>",
            lambda e: self._list_canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        # ── Right: faction detail ─────────────────────────────────────────────
        right = tk.Frame(main, bg=self.UI_PANEL)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        detail_hdr = tk.Frame(right, bg=self.UI_PANEL)
        detail_hdr.pack(fill=tk.X, padx=12, pady=(10, 0))
        self._detail_sys_lbl = tk.Label(
            detail_hdr, text="Select a system →",
            font=("Segoe UI", 12, "bold"), fg=COLOR_TEXT,
            bg=self.UI_PANEL, anchor="w")
        self._detail_sys_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._detail_date_lbl = tk.Label(
            detail_hdr, text="",
            font=("Consolas", 8), fg=self.UI_DIM, bg=self.UI_PANEL)
        self._detail_date_lbl.pack(side=tk.RIGHT)

        detail_wrap = tk.Frame(right, bg="#0b0f13")
        detail_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=(6, 4))
        detail_scroll = tk.Scrollbar(detail_wrap, orient=tk.VERTICAL)
        self._detail = tk.Text(
            detail_wrap,
            bg="#0b0f13", fg=COLOR_TEXT,
            font=("Consolas", 9),
            relief=tk.FLAT, highlightthickness=0, borderwidth=0,
            wrap=tk.NONE, padx=6, pady=4,
            yscrollcommand=detail_scroll.set,
            state=tk.DISABLED,
        )
        detail_scroll.config(command=self._detail.yview)
        self._detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Text tags
        self._detail.tag_config("hdr",      foreground=COLOR_ORANGE, font=("Consolas", 9, "bold"))
        self._detail.tag_config("sep",      foreground="#1a2228")
        self._detail.tag_config("name",     foreground=COLOR_TEXT,   font=("Consolas", 9, "bold"))
        self._detail.tag_config("name_dim", foreground=self.UI_MUTED)
        self._detail.tag_config("inf_hi",   foreground="#21d189")
        self._detail.tag_config("inf_mid",  foreground=COLOR_ACCENT)
        self._detail.tag_config("inf_lo",   foreground=self.UI_MUTED)
        self._detail.tag_config("up",       foreground="#21d189")
        self._detail.tag_config("down",     foreground="#ff5c5c")
        self._detail.tag_config("flat",     foreground=self.UI_DIM)
        self._detail.tag_config("no_prev",  foreground=self.UI_DIM)
        self._detail.tag_config("state_pos",foreground="#21d189")
        self._detail.tag_config("state_neu",foreground="#93c5fd")
        self._detail.tag_config("state_neg",foreground="#ff9a3c")
        self._detail.tag_config("state_war",foreground="#ff5c5c")
        self._detail.tag_config("pend",     foreground="#7d8891",    font=("Consolas", 8))
        self._detail.tag_config("muted",    foreground=self.UI_DIM)
        self._detail.tag_config("ally_fed", foreground="#5b9bd5")
        self._detail.tag_config("ally_emp", foreground="#c9a050")
        self._detail.tag_config("ally_all", foreground="#5cb85c")
        self._detail.tag_config("ally_ind", foreground=self.UI_MUTED)
        self._detail.tag_config("ally_pf",  foreground=COLOR_ACCENT)
        self._detail.tag_config("bar_hi",   foreground="#21d189")
        self._detail.tag_config("bar_mid",  foreground=COLOR_ACCENT)
        self._detail.tag_config("bar_lo",   foreground="#3a7d9e")

    # ── System list ───────────────────────────────────────────────────────────

    def _reload_list(self):
        systems = self._load_systems()
        query   = (self._search_var.get() or "").strip().lower()

        for w in self._list_inner.winfo_children():
            w.destroy()

        shown = 0
        for row in systems:
            sys_name, last_updated = row[0], row[1]
            has_factions = row[2] if len(row) > 2 else True
            if query and query not in sys_name.lower():
                continue
            shown += 1
            self._add_list_row(sys_name, last_updated, has_factions)

        if not shown:
            if query:
                msg = f'No match for "{query}".'
            else:
                msg = "No systems visited yet.\n\nJump to any system\nto start tracking."
            tk.Label(self._list_inner, text=msg,
                     font=("Consolas", 8), fg=self.UI_MUTED, bg=self.UI_PANEL,
                     justify=tk.LEFT
                     ).pack(anchor="w", padx=8, pady=10)

        total = len(systems)
        self._sys_count_lbl.config(
            text=f"{total} system{'s' if total != 1 else ''}")

    def _add_list_row(self, sys_name: str, last_updated, has_factions: bool = True):
        is_sel  = (sys_name == self._selected_system)
        row_bg  = "#0d1317" if is_sel else self.UI_PANEL
        bdr_col = COLOR_ACCENT if is_sel else self.UI_BORDER

        row = tk.Frame(self._list_inner, bg=row_bg, cursor="hand2",
                       highlightbackground=bdr_col, highlightthickness=1)
        row.pack(fill=tk.X, pady=(0, 3))

        name_disp = sys_name if len(sys_name) <= 23 else sys_name[:22] + "…"
        name_color = (COLOR_ACCENT if is_sel else COLOR_TEXT) if has_factions else self.UI_DIM
        tk.Label(row, text=name_disp,
                 font=("Segoe UI", 9, "bold" if is_sel else "normal"),
                 fg=name_color,
                 bg=row_bg, anchor="w"
                 ).pack(fill=tk.X, padx=8, pady=(4, 0))

        ts_str = ""
        if last_updated:
            try:
                ts_str = datetime.fromtimestamp(float(last_updated)).strftime("%d %b  %H:%M")
            except Exception:
                pass
        tk.Label(row, text=ts_str,
                 font=("Consolas", 8), fg=self.UI_DIM, bg=row_bg, anchor="w"
                 ).pack(fill=tk.X, padx=8, pady=(0, 4))

        def _click(e, s=sys_name):
            self._select_system(s)

        row.bind("<Button-1>", _click)
        for child in row.winfo_children():
            child.bind("<Button-1>", _click)

    # ── Faction detail ────────────────────────────────────────────────────────

    def _select_system(self, sys_name: str):
        self._selected_system = sys_name
        self._reload_list()
        self._render_factions(sys_name)

    def _render_factions(self, sys_name: str):
        snapshots = self._load_factions(sys_name)
        self._detail_sys_lbl.config(text=sys_name)

        latest_ts = max(
            (s.get("recorded_at", 0) for s in snapshots), default=None)
        if latest_ts:
            try:
                dt_str = datetime.fromtimestamp(float(latest_ts)).strftime(
                    "%Y-%m-%d  %H:%M")
                self._detail_date_lbl.config(text=f"Last data: {dt_str}")
            except Exception:
                self._detail_date_lbl.config(text="")
        else:
            self._detail_date_lbl.config(text="")

        t = self._detail
        t.config(state=tk.NORMAL)
        t.delete("1.0", tk.END)

        if not snapshots:
            t.insert(tk.END, "  No faction data for this system.\n", "muted")
            t.config(state=tk.DISABLED)
            return

        # Build per-faction latest and previous snapshots
        latest: dict[str, dict] = {}
        prev:   dict[str, dict] = {}
        for snap in sorted(snapshots, key=lambda x: x.get("recorded_at", 0)):
            fname = snap["faction_name"]
            if fname in latest:
                prev[fname] = latest[fname]
            latest[fname] = snap

        sorted_factions = sorted(
            latest.values(), key=lambda x: -float(x.get("influence", 0)))

        # Header
        t.insert(tk.END,
            f"  {'FACTION':<35} {'INF':>6}  {'TREND':>8}  {'ALLEGIANCE':<14}  STATES\n",
            "hdr")
        t.insert(tk.END, "  " + "─" * 82 + "\n", "sep")

        for snap in sorted_factions:
            fname = snap.get("faction_name", "Unknown")
            inf   = float(snap.get("influence", 0))
            gov   = snap.get("government") or ""
            ally  = (snap.get("allegiance") or "").strip()

            try:
                active  = json.loads(snap.get("active_states")  or "[]")
                pending = json.loads(snap.get("pending_states") or "[]")
            except Exception:
                active, pending = [], []

            # Trend vs. previous snapshot
            prev_snap = prev.get(fname)
            if prev_snap:
                delta = inf - float(prev_snap.get("influence", 0))
                if delta > 0.0005:
                    trend_txt = f"▲{delta*100:+.2f}%"
                    trend_tag = "up"
                elif delta < -0.0005:
                    trend_txt = f"▼{delta*100:+.2f}%"
                    trend_tag = "down"
                else:
                    trend_txt = "  ═  —"
                    trend_tag = "flat"
            else:
                trend_txt = "  —"
                trend_tag = "no_prev"

            # Influence colour
            if inf >= 0.30:
                inf_tag  = "inf_hi"
                bar_tag  = "bar_hi"
            elif inf >= 0.10:
                inf_tag  = "inf_mid"
                bar_tag  = "bar_mid"
            else:
                inf_tag  = "inf_lo"
                bar_tag  = "bar_lo"

            ally_tag  = _ALLEGIANCE_TAG.get(ally, "ally_ind")
            ally_disp = ally[:14] if ally else "—"

            fname_disp = fname if len(fname) <= 35 else fname[:34] + "…"

            # Faction row
            t.insert(tk.END, f"  {fname_disp:<35} ", "name")
            t.insert(tk.END, f"{inf*100:>5.1f}%",         inf_tag)
            t.insert(tk.END, f"  {trend_txt:<10} ",       trend_tag)
            t.insert(tk.END, f"{ally_disp:<14}  ",        ally_tag)

            # Active states
            for entry in active:
                s = entry.get("State") if isinstance(entry, dict) else str(entry)
                if not s or s == "None":
                    continue
                stag = _STATE_TAG.get(s, "state_neu")
                t.insert(tk.END, f"[{s}] ", stag)

            # Pending states (smaller, in parens)
            for entry in pending:
                s = entry.get("State") if isinstance(entry, dict) else str(entry)
                if not s or s == "None":
                    continue
                t.insert(tk.END, f"({s}) ", "pend")

            t.insert(tk.END, "\n")

            # Inline influence bar (80-char wide)
            bar_w   = 78
            filled  = max(0, min(bar_w, round(bar_w * inf)))
            bar_str = "  " + "█" * filled + "░" * (bar_w - filled) + "\n"
            t.insert(tk.END, bar_str, bar_tag)

        t.config(state=tk.DISABLED)
