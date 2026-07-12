"""
bgs_window.py - BGS (Background Simulation) visit tracker for VoidCompass.

Stores faction influence snapshots for every inhabited system visited.
Shows live influence %, trend vs. the previous visit, government/allegiance,
and active/pending BGS states.
"""

import json
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config
from ui_theme import THEME, ThemedWindowMixin, apply_window, configure_ttk, scrollbar, window_surface

COLOR_ACCENT = THEME.accent
COLOR_ORANGE = THEME.orange
COLOR_TEXT = THEME.text

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


class BGSWindow(ThemedWindowMixin):

    def __init__(
        self,
        root,
        config: dict,
        load_systems_cb:  Callable[[], list],
        load_factions_cb: Callable[[str], list],
        delete_system_cb: Callable[[str], bool] | None = None,
        purge_cb: Callable[[], bool] | None = None,
        purge_empty_cb: Callable[[], int | None] | None = None,
        embedded=False,
    ):
        """
        load_systems_cb  — () → [(system_name, last_updated_epoch)]
        load_factions_cb — (system_name) → list of snapshot dicts
        """
        self.root              = root
        self.config            = config
        self._load_systems     = load_systems_cb
        self._load_factions    = load_factions_cb
        self._delete_system    = delete_system_cb
        self._purge_bgs        = purge_cb
        self._purge_empty_bgs  = purge_empty_cb
        self._selected_system: str | None = None
        self._all_systems: list = []
        self._system_iids: dict[str, str] = {}
        self._initial_retry_job = None

        self.embedded = embedded
        self.win = window_surface(root, embedded=embedded)
        self.win.title("BGS Visit Tracker - Void Compass")
        apply_window(self.win)
        self.win.geometry(config.get("bgs_window_geometry", "880x580"))
        self.win.resizable(True, True)
        self.win.minsize(660, 420)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        # Let the dashboard display the page before querying and populating BGS.
        self.win.after_idle(self._initial_load)

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
        self._all_systems = self._load_systems()
        self._reload_list()
        if self._selected_system:
            self._render_factions(self._selected_system)

    def _on_close(self):
        if self._initial_retry_job is not None:
            try:
                self.win.after_cancel(self._initial_retry_job)
            except Exception:
                pass
            self._initial_retry_job = None
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
        configure_ttk(self.win, "BGS")

        # Header bar
        hdr = tk.Frame(self.win, bg="#0c1014", height=46)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="BGS VISIT TRACKER",
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

        self._system_tree = ttk.Treeview(
            list_wrap,
            columns=("system", "updated"),
            show="headings",
            style="BGS.Treeview",
            selectmode="browse",
        )
        self._system_tree.heading("system", text="SYSTEM")
        self._system_tree.heading("updated", text="UPDATED")
        self._system_tree.column("system", width=137, minwidth=90, anchor=tk.W, stretch=True)
        self._system_tree.column("updated", width=72, minwidth=68, anchor=tk.E, stretch=False)
        self._system_tree.tag_configure("no_factions", foreground=self.UI_DIM)
        self._system_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        list_scroll = scrollbar(list_wrap, orient=tk.VERTICAL, command=self._system_tree.yview)
        self._system_tree.configure(yscrollcommand=list_scroll.set)
        self._system_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        actions = tk.Frame(left, bg=self.UI_PANEL)
        actions.pack(fill=tk.X, padx=4, pady=(5, 5))
        self._delete_btn = self._action_button(
            actions, "DELETE", self._delete_selected, danger=True, padx=7, pady=4
        )
        self._delete_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        self._purge_empty_btn = self._action_button(
            actions, "PURGE EMPTY", self._purge_empty, danger=True, padx=7, pady=4
        )
        self._purge_empty_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        self._purge_btn = self._action_button(
            actions, "PURGE ALL", self._purge_all, danger=True, padx=7, pady=4
        )
        self._purge_btn.pack(fill=tk.X, pady=(4, 0))

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
        detail_scroll = scrollbar(detail_wrap, orient=tk.VERTICAL)
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

    def _initial_load(self, attempt=0):
        if not self.is_open():
            return
        self._initial_retry_job = None
        self._all_systems = self._load_systems()
        self._reload_list()

        if self._all_systems:
            first_system = self._selected_system or self._all_systems[0][0]
            self._select_system(first_system, reload_list=False)
            return

        # A startup journal replay may briefly own the shared DB lock. The DB
        # callbacks intentionally return their cache instead of blocking Tk, so
        # retry a few times to replace an empty first read as soon as it is free.
        if attempt < 4:
            delay_ms = 150 * (2 ** attempt)
            self._initial_retry_job = self.win.after(
                delay_ms, lambda: self._initial_load(attempt + 1)
            )

    def _reload_list(self):
        systems = self._all_systems
        query   = (self._search_var.get() or "").strip().lower()

        children = self._system_tree.get_children()
        if children:
            self._system_tree.delete(*children)
        self._system_iids = {}

        shown = 0
        for row in systems:
            sys_name, last_updated = row[0], row[1]
            has_factions = row[2] if len(row) > 2 else True
            if query and query not in sys_name.lower():
                continue
            shown += 1
            ts_str = ""
            if last_updated:
                try:
                    ts_str = datetime.fromtimestamp(float(last_updated)).strftime("%d %b")
                except Exception:
                    pass
            iid = self._system_tree.insert(
                "",
                tk.END,
                values=(sys_name, ts_str),
                tags=() if has_factions else ("no_factions",),
            )
            self._system_iids[sys_name] = iid

        if not shown:
            message = f'No match for "{query}".' if query else "No systems visited yet"
            self._system_tree.insert("", tk.END, values=(message, ""), tags=("no_factions",))

        selected_iid = self._system_iids.get(self._selected_system)
        if selected_iid:
            self._system_tree.selection_set(selected_iid)
            self._system_tree.see(selected_iid)

        total = len(systems)
        self._sys_count_lbl.config(
            text=f"{total} system{'s' if total != 1 else ''}")
        self._update_action_states()

    def _on_tree_select(self, _event=None):
        selection = self._system_tree.selection()
        if not selection:
            return
        values = self._system_tree.item(selection[0], "values")
        sys_name = values[0] if values else ""
        if sys_name not in self._system_iids:
            return
        if sys_name == self._selected_system:
            return
        self._select_system(sys_name, reload_list=False)

    # ── Faction detail ────────────────────────────────────────────────────────

    def _select_system(self, sys_name: str, reload_list=True):
        self._selected_system = sys_name
        if reload_list:
            self._reload_list()
        iid = self._system_iids.get(sys_name)
        if iid and self._system_tree.selection() != (iid,):
            self._system_tree.selection_set(iid)
            self._system_tree.see(iid)
        self._render_factions(sys_name)
        self._update_action_states()

    def _update_action_states(self):
        can_delete = bool(
            self._delete_system
            and self._selected_system
            and any(row[0] == self._selected_system for row in self._all_systems)
        )
        can_purge_empty = bool(
            self._purge_empty_bgs
            and any(len(row) > 2 and not row[2] for row in self._all_systems)
        )
        can_purge = bool(self._purge_bgs and self._all_systems)
        self._delete_btn.config(state=tk.NORMAL if can_delete else tk.DISABLED)
        self._purge_empty_btn.config(state=tk.NORMAL if can_purge_empty else tk.DISABLED)
        self._purge_btn.config(state=tk.NORMAL if can_purge else tk.DISABLED)

    def _clear_detail(self):
        self._detail_sys_lbl.config(text="Select a system →")
        self._detail_date_lbl.config(text="")
        self._detail.config(state=tk.NORMAL)
        self._detail.delete("1.0", tk.END)
        self._detail.insert(tk.END, "  No BGS system selected.\n", "muted")
        self._detail.config(state=tk.DISABLED)

    def _reload_after_delete(self):
        self._selected_system = None
        self._all_systems = self._load_systems()
        self._reload_list()
        if self._all_systems:
            self._select_system(self._all_systems[0][0], reload_list=False)
        else:
            self._clear_detail()
            self._update_action_states()

    def _delete_selected(self):
        system_name = self._selected_system
        if not system_name or not self._delete_system:
            return
        if not messagebox.askyesno(
            "Delete BGS System",
            f"Remove {system_name} from BGS and delete its faction snapshots?\n\n"
            "Exploration history is retained. The system will return to BGS if you revisit it.",
            parent=self.win,
        ):
            return
        if not self._delete_system(system_name):
            messagebox.showwarning(
                "BGS Database Busy",
                "The BGS database is busy. Nothing was deleted; please try again.",
                parent=self.win,
            )
            return
        self._reload_after_delete()

    def _purge_empty(self):
        if not self._purge_empty_bgs:
            return
        empty_count = sum(
            1 for row in self._all_systems if len(row) > 2 and not row[2]
        )
        if not empty_count:
            return
        if not messagebox.askyesno(
            "Purge Empty BGS Systems",
            f"Remove {empty_count} system{'s' if empty_count != 1 else ''} with no faction snapshots?\n\n"
            "Populated BGS systems and Exploration History are retained. Removed systems return if revisited.",
            parent=self.win,
        ):
            return
        removed = self._purge_empty_bgs()
        if removed is None:
            messagebox.showwarning(
                "BGS Database Busy",
                "The BGS database is busy. Nothing was purged; please try again.",
                parent=self.win,
            )
            return
        self._reload_after_delete()

    def _purge_all(self):
        if not self._all_systems or not self._purge_bgs:
            return
        count = len(self._all_systems)
        if not messagebox.askyesno(
            "Purge BGS History",
            f"Remove all {count} systems from BGS and delete every faction snapshot?\n\n"
            "Exploration history is retained. Revisited systems will be added to BGS again.\n\n"
            "This cannot be undone.",
            parent=self.win,
        ):
            return
        if not self._purge_bgs():
            messagebox.showwarning(
                "BGS Database Busy",
                "The BGS database is busy. Nothing was purged; please try again.",
                parent=self.win,
            )
            return
        self._reload_after_delete()

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
