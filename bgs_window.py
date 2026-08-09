"""
bgs_window.py - BGS (Background Simulation) visit tracker for VoidCompass.

Stores faction influence snapshots for every inhabited system visited.
Shows live influence %, trend vs. the previous visit, government/allegiance,
and active/pending BGS states.
"""

import json
import tkinter as tk
from datetime import datetime, timezone
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
        get_galaxy_state_cb: Callable[[], dict] | None = None,
        toggle_faction_watch_cb: Callable[[str], bool] | None = None,
        get_carrier_state_cb: Callable[[], dict] | None = None,
        open_carrier_cb: Callable[[], None] | None = None,
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
        self._get_galaxy_state = get_galaxy_state_cb or (lambda: {})
        self._toggle_faction_watch = toggle_faction_watch_cb
        self._get_carrier_state = get_carrier_state_cb or (lambda: {})
        self._open_carrier = open_carrier_cb
        self._selected_system: str | None = None
        self._all_systems: list = []
        self._system_iids: dict[str, str] = {}
        self._initial_retry_job = None
        self._galaxy_resize_job = None
        self._galaxy_compact = None
        self._galaxy_detail = None
        self._squadron_compact = None

        self.embedded = embedded
        self.win = window_surface(root, embedded=embedded)
        self.win.title("Galaxy - Void Compass")
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

    def select_section(self, section=None):
        """Select the optional-operation area requested by the launchpad."""
        key = str(section or "galaxy").strip().casefold()
        target = {
            "galaxy": self._galaxy_tab,
            "overview": self._galaxy_tab,
            "powerplay": self._galaxy_tab,
            "squadron": self._squadron_tab,
            "bgs": self._history_tab,
            "history": self._history_tab,
        }.get(key, self._galaxy_tab)
        try:
            self._tabs.select(target)
        except tk.TclError:
            pass

    def refresh_current(self):
        """Reload the system list and re-render the selected system."""
        if not self.is_open():
            return
        self.win.after(0, self._do_refresh)

    def _do_refresh(self):
        self._render_galaxy_overview()
        self._render_squadron_command()
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
        if self._galaxy_resize_job is not None:
            try:
                self.win.after_cancel(self._galaxy_resize_job)
            except Exception:
                pass
            self._galaxy_resize_job = None
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
        tk.Label(hdr, text="GALAXY",
                 font=("Segoe UI", 13, "bold"), fg=COLOR_ACCENT, bg="#0c1014"
                 ).pack(side=tk.LEFT, padx=14, pady=8)
        self._sys_count_lbl = tk.Label(hdr, text="",
                                        fg=self.UI_DIM, bg="#0c1014",
                                        font=("Consolas", 8))
        self._sys_count_lbl.pack(side=tk.RIGHT, padx=14)
        self._refresh_btn = self._action_button(
            hdr, "REFRESH", self.refresh_current, muted=True, padx=9, pady=3)
        self._refresh_btn.pack(side=tk.RIGHT, padx=(0, 4), pady=7)

        self._tabs = ttk.Notebook(self.win, style="BGS.TNotebook")
        self._tabs.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 8))
        self._galaxy_tab = tk.Frame(self._tabs, bg=self.UI_BG)
        self._squadron_tab = tk.Frame(self._tabs, bg=self.UI_BG)
        self._history_tab = tk.Frame(self._tabs, bg=self.UI_BG)
        self._tabs.add(self._galaxy_tab, text="GALAXY OVERVIEW")
        self._tabs.add(self._squadron_tab, text="SQUADRON COMMAND")
        self._tabs.add(self._history_tab, text="BGS HISTORY")
        self._build_galaxy_overview()
        self._build_squadron_command()

        # Main split: left list + right detail
        main = tk.Frame(self._history_tab, bg=self.UI_BG)
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
        detail_hscroll = scrollbar(detail_wrap, orient=tk.HORIZONTAL)
        self._detail = tk.Text(
            detail_wrap,
            bg="#0b0f13", fg=COLOR_TEXT,
            font=("Consolas", 9),
            relief=tk.FLAT, highlightthickness=0, borderwidth=0,
            wrap=tk.NONE, padx=6, pady=4,
            yscrollcommand=detail_scroll.set,
            xscrollcommand=detail_hscroll.set,
            state=tk.DISABLED,
        )
        detail_scroll.config(command=self._detail.yview)
        detail_hscroll.config(command=self._detail.xview)
        detail_hscroll.pack(side=tk.BOTTOM, fill=tk.X)
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

    # ── Live Galaxy overview ─────────────────────────────────────────────────

    def _build_galaxy_overview(self):
        body = tk.Frame(self._galaxy_tab, bg=self.UI_BG)
        body.pack(fill=tk.BOTH, expand=True)
        self._galaxy_canvas = tk.Canvas(body, bg=self.UI_BG, highlightthickness=0, bd=0)
        scroll = scrollbar(body, orient=tk.VERTICAL, command=self._galaxy_canvas.yview)
        self._galaxy_content = tk.Frame(self._galaxy_canvas, bg=self.UI_BG)
        window = self._galaxy_canvas.create_window((0, 0), window=self._galaxy_content, anchor="nw")
        self._galaxy_canvas.configure(yscrollcommand=scroll.set)
        self._galaxy_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._galaxy_content.bind(
            "<Configure>", lambda _event: self._galaxy_canvas.configure(scrollregion=self._galaxy_canvas.bbox("all")))
        self._galaxy_window = window
        self._galaxy_canvas.bind("<Configure>", self._on_galaxy_canvas_configure)
        self._bind_galaxy_scroll(self._galaxy_canvas)
        self._bind_galaxy_scroll(self._galaxy_content)
        self._render_galaxy_overview()

    def _bind_galaxy_scroll(self, widget):
        widget.bind("<MouseWheel>", self._on_galaxy_mousewheel, add="+")

    def _on_galaxy_mousewheel(self, event):
        if self._galaxy_canvas.bbox("all"):
            self._galaxy_canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _on_galaxy_canvas_configure(self, event):
        self._galaxy_canvas.itemconfigure(self._galaxy_window, width=event.width)
        compact = event.width < 760
        previous = self._galaxy_compact
        self._galaxy_compact = compact
        if previous is None:
            if not compact:
                return
            # The first layout is rendered as two columns before Tk reports its
            # actual width, so a compact initial width still needs one reflow.
        elif compact == previous:
            return
        if self._galaxy_resize_job is not None:
            try:
                self.win.after_cancel(self._galaxy_resize_job)
            except Exception:
                pass
        self._galaxy_resize_job = self.win.after(80, self._render_galaxy_overview)

    def _galaxy_card(self, parent, title, row, column, columnspan=1, accent=None):
        card = tk.Frame(parent, bg=self.UI_PANEL, highlightbackground=accent or self.UI_BORDER,
                        highlightthickness=1, bd=0)
        card.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=5, pady=5)
        tk.Frame(card, bg=accent or COLOR_ORANGE, height=2).pack(fill=tk.X)
        tk.Label(card, text=title, fg=accent or COLOR_ORANGE, bg=self.UI_PANEL,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill=tk.X, padx=12, pady=(9, 5))
        self._bind_galaxy_scroll(card)
        for child in card.winfo_children():
            self._bind_galaxy_scroll(child)
        return card

    def _galaxy_line(self, parent, title, detail="", fg=COLOR_TEXT):
        row = tk.Frame(parent, bg=self.UI_PANEL)
        row.pack(fill=tk.X, padx=12, pady=3)
        title_label = tk.Label(row, text=str(title), fg=fg, bg=self.UI_PANEL,
                               font=("Consolas", 9, "bold"), anchor="w")
        title_label.pack(side=tk.LEFT)
        detail_label = None
        if detail not in ("", None):
            detail_label = tk.Label(row, text=str(detail), fg=self.UI_MUTED, bg=self.UI_PANEL,
                                    font=("Consolas", 8), anchor="e", justify=tk.RIGHT,
                                    wraplength=250 if self._galaxy_compact else 480)
            detail_label.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self._bind_galaxy_scroll(row)
        self._bind_galaxy_scroll(title_label)
        if detail_label:
            self._bind_galaxy_scroll(detail_label)
        return row

    # ── Squadron command ─────────────────────────────────────────────────────

    def _build_squadron_command(self):
        body = tk.Frame(self._squadron_tab, bg=self.UI_BG)
        body.pack(fill=tk.BOTH, expand=True)
        self._squadron_canvas = tk.Canvas(body, bg=self.UI_BG, highlightthickness=0, bd=0)
        scroll = scrollbar(body, orient=tk.VERTICAL, command=self._squadron_canvas.yview)
        self._squadron_content = tk.Frame(self._squadron_canvas, bg=self.UI_BG)
        window = self._squadron_canvas.create_window(
            (0, 0), window=self._squadron_content, anchor="nw")
        self._squadron_canvas.configure(yscrollcommand=scroll.set)
        self._squadron_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._squadron_content.bind(
            "<Configure>",
            lambda _event: self._squadron_canvas.configure(
                scrollregion=self._squadron_canvas.bbox("all")),
        )
        self._squadron_canvas.bind(
            "<Configure>",
            lambda event: self._on_squadron_canvas_configure(window, event),
        )
        self._bind_squadron_scroll(self._squadron_canvas)
        self._bind_squadron_scroll(self._squadron_content)
        self._render_squadron_command()

    def _bind_squadron_scroll(self, widget):
        widget.bind("<MouseWheel>", self._on_squadron_mousewheel, add="+")

    def _on_squadron_mousewheel(self, event):
        if self._squadron_canvas.bbox("all"):
            self._squadron_canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _on_squadron_canvas_configure(self, window, event):
        self._squadron_canvas.itemconfigure(window, width=event.width)
        compact = event.width < 760
        if compact != self._squadron_compact:
            self._squadron_compact = compact
            self.win.after_idle(self._render_squadron_command)

    def _squadron_card(self, parent, title, row, column, columnspan=1, accent=None):
        card = tk.Frame(
            parent, bg=self.UI_PANEL, highlightbackground=accent or self.UI_BORDER,
            highlightthickness=1, bd=0,
        )
        card.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=5, pady=5)
        tk.Frame(card, bg=accent or "#c4b5fd", height=2).pack(fill=tk.X)
        tk.Label(
            card, text=title, fg=accent or "#c4b5fd", bg=self.UI_PANEL,
            font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(9, 5))
        self._bind_squadron_scroll(card)
        for child in card.winfo_children():
            self._bind_squadron_scroll(child)
        return card

    def _squadron_line(self, parent, title, detail="", fg=COLOR_TEXT):
        row = tk.Frame(parent, bg=self.UI_PANEL)
        row.pack(fill=tk.X, padx=12, pady=3)
        title_label = tk.Label(
            row, text=str(title), fg=fg, bg=self.UI_PANEL,
            font=("Consolas", 9, "bold"), anchor="w",
        )
        title_label.pack(side=tk.LEFT)
        if detail not in ("", None):
            detail_label = tk.Label(
                row, text=str(detail), fg=self.UI_MUTED, bg=self.UI_PANEL,
                font=("Consolas", 8), anchor="e", justify=tk.RIGHT,
                wraplength=230 if self._squadron_compact else 390,
            )
            detail_label.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            self._bind_squadron_scroll(detail_label)
        self._bind_squadron_scroll(row)
        self._bind_squadron_scroll(title_label)
        return row

    @staticmethod
    def _squadron_event_label(event):
        return {
            "AppliedToSquadron": "APPLICATION",
            "InvitedToSquadron": "INVITATION",
            "JoinedSquadron": "JOINED",
            "SquadronCreated": "CREATED",
            "SquadronPromotion": "PROMOTION",
            "SquadronDemotion": "DEMOTION",
            "LeftSquadron": "LEFT",
            "KickedFromSquadron": "REMOVED",
            "DisbandedSquadron": "DISBANDED",
            "SharedBookmarkToSquadron": "BOOKMARK",
            "WonATrophyForSquadron": "TROPHY",
        }.get(event, str(event or "EVENT").upper())

    @staticmethod
    def _short_timestamp(value):
        if not value:
            return "time not reported"
        try:
            stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return stamp.astimezone().strftime("%Y-%m-%d %H:%M")
        except Exception:
            return str(value)

    def _open_squadron_bgs(self):
        self._tabs.select(self._galaxy_tab)
        self._render_galaxy_overview()

    def _render_squadron_command(self):
        content = getattr(self, "_squadron_content", None)
        if not content:
            return
        for child in content.winfo_children():
            child.destroy()
        compact = bool(self._squadron_compact)
        columns = 1 if compact else 2
        content.grid_columnconfigure(0, weight=1, uniform="squadron")
        content.grid_columnconfigure(1, weight=0 if compact else 1,
                                     uniform="" if compact else "squadron")

        state = self._get_galaxy_state() or {}
        carrier = self._get_carrier_state() or {}
        squadron = state.get("squadron") or {}
        application = state.get("squadron_application") or {}
        invitation = state.get("squadron_invitation") or {}
        activity = [row for row in state.get("squadron_activity") or [] if isinstance(row, dict)]
        trophies = state.get("squadron_trophies") or []
        bookmarks = state.get("squadron_bookmarks") or []
        watched = list(state.get("watched_factions") or [])

        hero = self._squadron_card(
            content, "SQUADRON COMMAND STATUS", 0, 0, columns, "#c4b5fd")
        if squadron:
            rank = squadron.get("rank_name")
            if not rank and squadron.get("rank") is not None:
                rank = f"Rank {squadron.get('rank')}"
            self._squadron_line(
                hero, str(squadron.get("name") or "UNKNOWN SQUADRON").upper(),
                rank or "Rank awaiting journal sync", "#c4b5fd")
            identity = f"ID {squadron.get('id')}" if squadron.get("id") is not None else "ID not reported"
            self._squadron_line(
                hero, "Membership active", f"{identity} · {self._freshness_text(squadron.get('updated'))}",
                "#21d189")
        elif application:
            self._squadron_line(
                hero, "APPLICATION REPORTED", application.get("name") or "Unknown squadron", "#fde68a")
            self._squadron_line(hero, "Submitted", self._short_timestamp(application.get("timestamp")))
        elif invitation:
            self._squadron_line(
                hero, "INVITATION REPORTED", invitation.get("name") or "Unknown squadron", "#fde68a")
            self._squadron_line(hero, "Received", self._short_timestamp(invitation.get("timestamp")))
        else:
            self._squadron_line(
                hero, "NO ACTIVE SQUADRON", "Waiting for SquadronStartup, an application, or an invitation", self.UI_MUTED)

        actions = tk.Frame(hero, bg=self.UI_PANEL)
        actions.pack(fill=tk.X, padx=12, pady=(5, 10))
        self._action_button(
            actions, "GALAXY OBJECTIVES", self._open_squadron_bgs,
            accent=True, padx=9, pady=3,
        ).pack(side=tk.LEFT)
        if self._open_carrier:
            self._action_button(
                actions, "CARRIER COMMAND", self._open_carrier,
                muted=True, padx=9, pady=3,
            ).pack(side=tk.LEFT, padx=(6, 0))

        row = 1
        membership_card = self._squadron_card(content, "IDENTITY & ENGAGEMENT", row, 0)
        self._squadron_line(
            membership_card, "Current rank",
            squadron.get("rank_name") or (f"Rank {squadron.get('rank')}" if squadron.get("rank") is not None else "Not reported"))
        self._squadron_line(membership_card, "Journal actions", f"{len(activity):,} retained")
        self._squadron_line(membership_card, "Trophy wins", f"{len(trophies):,} retained")
        self._squadron_line(membership_card, "Shared bookmarks", f"{len(bookmarks):,} retained")
        pending = []
        if application:
            pending.append(f"Applied: {application.get('name') or 'unknown'}")
        if invitation:
            pending.append(f"Invited: {invitation.get('name') or 'unknown'}")
        self._squadron_line(membership_card, "Journal signals", " · ".join(pending) or "None reported")

        carrier_card = self._squadron_card(content, "SQUADRON CARRIER", row if not compact else row + 1,
                                           1 if not compact else 0)
        is_squadron_carrier = carrier.get("carrier_type") == "SquadronCarrier"
        self._squadron_line(
            carrier_card,
            carrier.get("name") or ("Carrier not synced" if squadron else "No squadron carrier context"),
            carrier.get("callsign") or "Open carrier management in Elite to sync",
            "#21d189" if is_squadron_carrier else self.UI_MUTED,
        )
        self._squadron_line(
            carrier_card, "Carrier type",
            "Squadron Carrier" if is_squadron_carrier else
            "Personal Fleet Carrier" if carrier.get("carrier_type") == "FleetCarrier" else "Awaiting CarrierStats")
        self._squadron_line(carrier_card, "Location", carrier.get("system") or "Not reported")
        destination = carrier.get("jump_destination")
        if isinstance(destination, dict):
            destination = destination.get("system") or destination.get("StarSystem")
        self._squadron_line(carrier_card, "Next jump", destination or "None plotted")

        ops_row = row + (2 if compact else 1)
        objective_card = self._squadron_card(content, "SQUADRON OBJECTIVES", ops_row, 0)
        self._squadron_line(
            objective_card, "Watched factions", f"{len(watched):,}",
            "#21d189" if watched else self.UI_MUTED)
        if watched:
            current_factions = {row.get("name"): row for row in state.get("factions") or []}
            for name in watched[:6]:
                faction = current_factions.get(name) or {}
                influence = faction.get("influence")
                detail = (f"{float(influence) * 100:.2f}% in current system"
                          if isinstance(influence, (int, float)) else "Watch active")
                self._squadron_line(objective_card, name, detail)
            if len(watched) > 6:
                self._squadron_line(objective_card, f"+{len(watched) - 6} more", "Open Galaxy Overview")
        else:
            self._squadron_line(
                objective_card, "No objectives selected",
                "Open a faction in Galaxy Overview and choose Watch Faction", self.UI_MUTED)
        self._squadron_line(
            objective_card, "Current-system conflicts", f"{len(state.get('conflicts') or []):,}")
        self._squadron_line(
            objective_card, "Community goals", f"{len(state.get('community_goals') or {}):,}")

        activity_card = self._squadron_card(
            content, "ACTIVITY TIMELINE", ops_row if not compact else ops_row + 1,
            1 if not compact else 0)
        if activity:
            for item in activity[:10]:
                detail_parts = [item.get("detail"), item.get("squadron"), self._short_timestamp(item.get("timestamp"))]
                self._squadron_line(
                    activity_card, self._squadron_event_label(item.get("event")),
                    " · ".join(str(value) for value in detail_parts if value))
        else:
            self._squadron_line(
                activity_card, "No retained squadron activity",
                "New journal actions will appear here", self.UI_MUTED)

        limit_row = ops_row + (2 if compact else 1)
        limits = self._squadron_card(content, "JOURNAL COVERAGE", limit_row, 0, columns, self.UI_BORDER)
        self._squadron_line(
            limits, "Tracked",
            "membership · rank changes · applications · invitations · trophy wins · shared bookmarks")
        self._squadron_line(
            limits, "Not exposed by the journal",
            "member roster · online status · squadron chat · full leaderboard tables · application outcome", self.UI_MUTED)
        self._squadron_line(
            limits, "Objective model",
            "Existing Galaxy faction watches act as persistent squadron BGS objectives")

        content.update_idletasks()
        self._squadron_canvas.configure(scrollregion=self._squadron_canvas.bbox("all"))

    @staticmethod
    def _reputation_band(value):
        if value is None:
            return "", "#7a8a98"
        if value <= -35:
            return "HOSTILE", "#ff5c5c"
        if value <= -10:
            return "UNFRIENDLY", "#ff7777"
        if value < 10:
            return "NEUTRAL", "#7a8a98"
        if value < 35:
            return "CORDIAL", "#93c5fd"
        if value < 90:
            return "FRIENDLY", "#21d189"
        return "ALLIED", "#21d189"

    @staticmethod
    def _goal_expiry(value):
        if not value:
            return ""
        try:
            expiry = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            seconds = int((expiry - datetime.now(timezone.utc)).total_seconds())
            if seconds <= 0:
                return "ENDED"
            hours = seconds // 3600
            return f"{hours // 24}d {hours % 24}h left" if hours >= 24 else f"{hours}h left"
        except Exception:
            return str(value)

    @staticmethod
    def _freshness_text(value):
        if not value:
            return "No journal timestamp · cached state"
        try:
            updated = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            seconds = max(0, int((datetime.now(timezone.utc) - updated).total_seconds()))
            if seconds < 60:
                age = "just now"
            elif seconds < 3600:
                age = f"{seconds // 60}m ago"
            elif seconds < 86400:
                age = f"{seconds // 3600}h ago"
            else:
                age = f"{seconds // 86400}d ago"
            status = "STALE" if seconds >= 1800 else "CURRENT"
            return f"{status} · {age} · {updated.astimezone().strftime('%Y-%m-%d %H:%M')}"
        except Exception:
            return f"Cached · {value}"

    def _faction_history_deltas(self, system_name, factions):
        """Compare current journal influence with the preceding stored visit."""
        snapshots = self._load_factions(system_name) if system_name else []
        by_name = {}
        for snapshot in snapshots:
            by_name.setdefault(snapshot.get("faction_name"), []).append(snapshot)
        deltas = {}
        for faction in factions or []:
            name = faction.get("name")
            current = float(faction.get("influence") or 0)
            history = by_name.get(name) or []
            if not history:
                continue
            # The newest DB record normally represents the event being rendered.
            # If it does, compare with the next record; otherwise compare with the
            # newest cached record returned by the non-blocking loader.
            previous_index = 1 if abs(float(history[0].get("influence") or 0) - current) < 1e-9 else 0
            if previous_index < len(history):
                deltas[name] = current - float(history[previous_index].get("influence") or 0)
        return deltas

    @staticmethod
    def _bind_click(widget, callback):
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", lambda _event: callback(), add="+")
        for child in widget.winfo_children():
            child.configure(cursor="hand2")
            child.bind("<Button-1>", lambda _event: callback(), add="+")

    def _open_history_for_system(self, system_name):
        if not system_name or system_name == "No current system":
            return
        self._tabs.select(self._history_tab)
        self._all_systems = self._load_systems()
        self._reload_list()
        if system_name in self._system_iids:
            self._select_system(system_name, reload_list=False)

    def _show_galaxy_detail(self, kind, key=None):
        self._galaxy_detail = (kind, key)
        self._render_galaxy_overview()
        try:
            self._galaxy_canvas.yview_moveto(0)
        except Exception:
            pass

    def _close_galaxy_detail(self):
        self._galaxy_detail = None
        self._render_galaxy_overview()

    def _galaxy_detail_line(self, parent, kind, key, title, detail="", fg=COLOR_TEXT):
        line = self._galaxy_line(parent, title, detail, fg)
        self._bind_click(line, lambda k=kind, value=key: self._show_galaxy_detail(k, value))
        return line

    def _render_galaxy_detail(self, content, state, system, row, deltas):
        selection = self._galaxy_detail
        if not selection:
            return False
        kind, key = selection
        titles = {
            "system": "SYSTEM DETAIL",
            "faction": "FACTION DETAIL",
            "powerplay": "POWERPLAY DETAIL",
            "squadron": "SQUADRON DETAIL",
            "conflict": "CONFLICT DETAIL",
            "goal": "COMMUNITY GOAL DETAIL",
        }
        card = self._galaxy_card(
            content, titles.get(kind, "GALAXY DETAIL"), row, 0,
            1 if self._galaxy_compact else 2, COLOR_ACCENT)
        actions = tk.Frame(card, bg=self.UI_PANEL)
        actions.pack(fill=tk.X, padx=12, pady=(0, 6))
        self._action_button(actions, "CLOSE", self._close_galaxy_detail, muted=True,
                            padx=9, pady=3).pack(side=tk.RIGHT)
        if system and system != "No current system" and kind in ("system", "faction", "conflict"):
            self._action_button(
                actions, "OPEN BGS HISTORY",
                lambda s=system: self._open_history_for_system(s), accent=True,
                padx=9, pady=3).pack(side=tk.LEFT)

        if kind == "system":
            self._galaxy_line(card, system.upper(),
                              f"Controlling faction: {state.get('controlling_faction') or 'Unknown'}",
                              COLOR_ACCENT)
            self._galaxy_line(
                card, "Journal freshness",
                self._freshness_text(state.get("galaxy_system_updated") or state.get("galaxy_updated")))
            self._galaxy_line(
                card, "Data source",
                state.get("galaxy_system_source") or state.get("galaxy_source") or "Saved companion state")
            self._galaxy_line(card, "Known factions", f"{len(state.get('factions') or []):,}")
            self._galaxy_line(card, "Active conflicts", f"{len(state.get('conflicts') or []):,}")
            pp = state.get("pp_system") or {}
            self._galaxy_line(card, "Powerplay control",
                              f"{pp.get('controlling') or 'Uncontrolled'} · {pp.get('state') or 'Unknown'}")

        elif kind == "faction":
            faction = next((row for row in state.get("factions") or [] if row.get("name") == key), None)
            if not faction:
                self._galaxy_line(card, "Faction data is no longer available", "Refresh after entering the system", self.UI_MUTED)
            else:
                name = faction.get("name") or "Unknown faction"
                influence = float(faction.get("influence") or 0)
                delta = deltas.get(name)
                change = "No previous visit to compare"
                if delta is not None:
                    change = f"{delta * 100:+.2f}% since previous visit"
                self._galaxy_line(card, name, "CONTROLLING FACTION" if name == state.get("controlling_faction") else "System faction",
                                  "#21d189" if name == state.get("controlling_faction") else COLOR_TEXT)
                self._galaxy_line(card, "Influence", f"{influence * 100:.2f}% · {change}")
                self._galaxy_line(card, "Government", faction.get("government") or "Unknown")
                self._galaxy_line(card, "Allegiance", faction.get("allegiance") or "Independent/Unknown")
                self._galaxy_line(card, "Faction state", faction.get("state") or "None")
                rep, rep_color = self._reputation_band(faction.get("my_reputation"))
                rep_value = faction.get("my_reputation")
                rep_text = f"{float(rep_value):.1f} · {rep}" if rep_value is not None else "Not reported"
                self._galaxy_line(card, "Commander reputation", rep_text, rep_color)
                for label, values in (
                    ("Active states", faction.get("active_states")),
                    ("Pending states", faction.get("pending_states")),
                    ("Recovering states", faction.get("recovering_states")),
                ):
                    self._galaxy_line(card, label, ", ".join(values or []) or "None")
                if self._toggle_faction_watch:
                    watched = name in set(state.get("watched_factions") or [])
                    self._action_button(
                        actions, "STOP WATCHING" if watched else "WATCH FACTION",
                        lambda n=name: self._toggle_watch_and_render(n),
                        muted=watched, padx=9, pady=3).pack(side=tk.LEFT, padx=(6, 0))

        elif kind == "powerplay":
            powerplay = state.get("powerplay") or {}
            pp = state.get("pp_system") or {}
            if not powerplay and not pp:
                self._galaxy_line(card, "No Powerplay data recorded", "Pledge or enter a Powerplay system", self.UI_MUTED)
            else:
                pledged = int(powerplay.get("time_pledged_s") or 0)
                pledged_text = f"{pledged // 86400}d {(pledged % 86400) // 3600}h" if pledged else "Not reported"
                self._galaxy_line(card, "Pledged power", powerplay.get("power") or "Not pledged", "#93c5fd")
                self._galaxy_line(card, "Rating", powerplay.get("rank") or 0)
                self._galaxy_line(card, "Merits", f"{int(powerplay.get('merits') or 0):,}")
                self._galaxy_line(card, "Session merits", f"+{int(powerplay.get('session_merits') or 0):,}")
                self._galaxy_line(card, "Time pledged", pledged_text)
                self._galaxy_line(card, "System controller", pp.get("controlling") or "Uncontrolled")
                self._galaxy_line(card, "System Powerplay state", pp.get("state") or "Unknown")
                control = pp.get("control_progress")
                self._galaxy_line(card, "Control progress",
                                  f"{float(control) * 100:.2f}%" if isinstance(control, (int, float)) else "Unknown")
                self._galaxy_line(card, "Powers present", ", ".join(pp.get("powers") or []) or "None reported")
                self._galaxy_line(card, "Reinforcement", f"{int(pp.get('reinforcement') or 0):,}")
                self._galaxy_line(card, "Undermining", f"{int(pp.get('undermining') or 0):,}")

        elif kind == "squadron":
            squadron = state.get("squadron") or {}
            if squadron:
                self._galaxy_line(card, squadron.get("name") or "Unknown Squadron", "Current commander squadron", "#c4b5fd")
                rank = squadron.get("rank_name") or (
                    f"Rank {squadron.get('rank')}" if squadron.get("rank") is not None else "Not reported")
                self._galaxy_line(card, "Commander squadron rank", rank)
                self._galaxy_line(card, "Squadron ID", squadron.get("id") or "Not reported")
                self._galaxy_line(card, "Source", squadron.get("source") or "Saved journal state")
                self._action_button(
                    actions, "OPEN SQUADRON COMMAND",
                    lambda: self._tabs.select(self._squadron_tab), accent=True,
                    padx=9, pady=3).pack(side=tk.LEFT, padx=(6, 0))
            else:
                self._galaxy_line(card, "No squadron recorded", "The journal has not reported an active squadron", self.UI_MUTED)

        elif kind == "conflict":
            conflicts = state.get("conflicts") or []
            try:
                conflict = conflicts[int(key)]
            except (IndexError, TypeError, ValueError):
                conflict = None
            if not conflict:
                message = "No active conflicts in the current system" if not conflicts else "Conflict data is no longer available"
                self._galaxy_line(card, message, "Refresh the current system", self.UI_MUTED)
            else:
                one, two = conflict.get("faction1") or {}, conflict.get("faction2") or {}
                one_score, two_score = int(one.get("won_days") or 0), int(two.get("won_days") or 0)
                leader = one.get("name") if one_score > two_score else two.get("name") if two_score > one_score else "Tied"
                self._galaxy_line(card, str(conflict.get("war_type") or "Conflict").title(),
                                  str(conflict.get("status") or "Active").title(), "#ff7777")
                self._galaxy_line(card, "Current leader", leader, "#21d189" if leader != "Tied" else COLOR_TEXT)
                self._galaxy_line(card, one.get("name") or "Faction one",
                                  f"{one_score} won day(s) · Stake: {one.get('stake') or 'None reported'}")
                self._galaxy_line(card, two.get("name") or "Faction two",
                                  f"{two_score} won day(s) · Stake: {two.get('stake') or 'None reported'}")
                self._galaxy_line(card, "Score", f"{one_score}–{two_score}")

        elif kind == "goal":
            goal = (state.get("community_goals") or {}).get(str(key))
            if not goal:
                message = "No joined Community Goals" if not state.get("community_goals") else "Community Goal data is no longer available"
                self._galaxy_line(card, message, "Wait for the next CommunityGoal journal event", self.UI_MUTED)
            else:
                self._galaxy_line(card, goal.get("title") or "Community Goal",
                                  "COMPLETE" if goal.get("complete") else self._goal_expiry(goal.get("expiry")),
                                  "#21d189" if goal.get("complete") else "#fde68a")
                self._galaxy_line(card, "Location", f"{goal.get('system') or 'Unknown'} · {goal.get('market') or 'Unknown station'}")
                self._galaxy_line(card, "Commander contribution", f"{int(goal.get('contribution') or 0):,}")
                self._galaxy_line(card, "Tier reached", goal.get("tier") or "Not reported")
                self._galaxy_line(card, "Percentile band", f"Top {goal.get('percentile')}%" if goal.get("percentile") is not None else "Not reported")
                self._galaxy_line(card, "Galaxy total", f"{int(goal.get('current_total') or 0):,}")
                self._galaxy_line(card, "Contributors", f"{int(goal.get('contributors') or 0):,}")
                self._galaxy_line(card, "Top rank", "Yes" if goal.get("top_rank") else "No")
                self._galaxy_line(card, "Bonus", goal.get("bonus") or "None reported")
                self._galaxy_line(card, "Expiry", goal.get("expiry") or "Not reported")
        return True

    def _render_galaxy_overview(self):
        self._galaxy_resize_job = None
        content = getattr(self, "_galaxy_content", None)
        if not content:
            return
        for child in content.winfo_children():
            child.destroy()
        compact = bool(self._galaxy_compact)
        content.grid_columnconfigure(0, weight=1, uniform="galaxy")
        content.grid_columnconfigure(1, weight=0 if compact else 1,
                                     uniform="" if compact else "galaxy")
        state = self._get_galaxy_state() or {}
        system = state.get("galaxy_system") or "No current system"
        factions = state.get("factions") or []
        deltas = self._faction_history_deltas(system, factions)

        hero = self._galaxy_card(content, "CURRENT GALAXY CONTEXT", 0, 0, 1 if compact else 2, COLOR_ACCENT)
        hero_line = self._galaxy_line(
            hero, system.upper(),
            f"Controlling faction: {state.get('controlling_faction') or 'Unknown'}",
            COLOR_ACCENT)
        self._bind_click(hero_line, lambda: self._show_galaxy_detail("system"))
        freshness = self._freshness_text(state.get("galaxy_system_updated") or state.get("galaxy_updated"))
        freshness_line = self._galaxy_line(
            hero,
            freshness,
            f"Source: {state.get('galaxy_system_source') or state.get('galaxy_source') or 'saved companion state'} · click for details",
            "#ff7777" if freshness.startswith("STALE") else "#21d189" if state.get("galaxy_system_updated") else self.UI_MUTED,
        )
        self._bind_click(freshness_line, lambda: self._show_galaxy_detail("system"))

        detail_open = self._render_galaxy_detail(content, state, system, 1, deltas)
        row_offset = 1 if detail_open else 0

        powerplay = state.get("powerplay") or {}
        pp_system = state.get("pp_system") or {}
        pp_card = self._galaxy_card(content, "POWERPLAY", 1 + row_offset, 0, accent="#93c5fd")
        if powerplay:
            pledged_seconds = int(powerplay.get("time_pledged_s") or 0)
            pledged = f"{pledged_seconds // 604800} week(s) pledged" if pledged_seconds else "Pledge active"
            self._galaxy_detail_line(
                pp_card, "powerplay", None, powerplay.get("power") or "Unknown Power",
                f"Rating {powerplay.get('rank') or 0} · {int(powerplay.get('merits') or 0):,} merits")
            self._galaxy_detail_line(
                pp_card, "powerplay", None,
                f"+{int(powerplay.get('session_merits') or 0):,} this session", pledged, "#21d189")
        else:
            self._galaxy_detail_line(
                pp_card, "powerplay", None, "Not pledged",
                "Powerplay progress appears after the game reports it", self.UI_MUTED)
        if pp_system:
            control = pp_system.get("control_progress")
            control_text = f"Control {float(control) * 100:.1f}%" if isinstance(control, (int, float)) else "Control unknown"
            self._galaxy_detail_line(
                pp_card, "powerplay", None, pp_system.get("controlling") or "Uncontrolled",
                f"{pp_system.get('state') or 'Unknown'} · {control_text}")
            powers = pp_system.get("powers") or []
            if len(powers) > 1:
                self._galaxy_detail_line(pp_card, "powerplay", None, "Contested", ", ".join(powers), COLOR_ORANGE)
            self._galaxy_detail_line(
                pp_card, "powerplay", None,
                f"▲ {int(pp_system.get('reinforcement') or 0):,} reinforced",
                f"▼ {int(pp_system.get('undermining') or 0):,} undermined")

        squad_card = self._galaxy_card(content, "SQUADRON", (2 if compact else 1) + row_offset,
                                        0 if compact else 1, accent="#c4b5fd")
        squadron = state.get("squadron") or {}
        if squadron:
            rank = squadron.get("rank_name") or (
                f"Rank {squadron.get('rank')}" if squadron.get("rank") is not None else "Rank not reported")
            self._galaxy_detail_line(
                squad_card, "squadron", None, squadron.get("name") or "Unknown Squadron",
                rank)
        else:
            self._galaxy_detail_line(
                squad_card, "squadron", None, "No squadron recorded",
                "SquadronStartup journal data", self.UI_MUTED)

        faction_card = self._galaxy_card(content, "CURRENT SYSTEM FACTIONS · ★ WATCH ALERTS", (3 if compact else 2) + row_offset,
                                         0, 1 if compact else 2, COLOR_ORANGE)
        watched = set(state.get("watched_factions") or [])
        if not factions:
            self._galaxy_line(faction_card, "No faction data", "Jump into or load inside a populated system", self.UI_MUTED)
        for faction in factions:
            influence = float(faction.get("influence") or 0)
            controls = faction.get("name") == state.get("controlling_faction")
            rep, rep_color = self._reputation_band(faction.get("my_reputation"))
            states = ([str(value) for value in faction.get("active_states") or []]
                      + [f"{value} (pending)" for value in faction.get("pending_states") or []]
                      + [f"{value} (recovering)" for value in faction.get("recovering_states") or []])
            detail = f"{influence * 100:.1f}% · {faction.get('government') or '—'} · {faction.get('allegiance') or '—'}"
            delta = deltas.get(faction.get("name"))
            if delta is not None:
                arrow = "▲" if delta > 0.0005 else "▼" if delta < -0.0005 else "═"
                detail += f" · {arrow} {delta * 100:+.2f}% since previous visit"
            if controls:
                detail += " · CONTROLS"
            if states:
                detail += " · " + ", ".join(states)
            faction_name = faction.get("name") or "Unknown faction"
            line = self._galaxy_line(
                faction_card, faction_name, detail,
                "#fde68a" if faction_name in watched else COLOR_TEXT)
            self._bind_click(line, lambda name=faction_name: self._show_galaxy_detail("faction", name))
            if self._toggle_faction_watch and faction.get("name"):
                watch_button = tk.Button(
                    line, text="★" if faction_name in watched else "☆",
                    command=lambda name=faction_name: self._toggle_watch_and_render(name),
                    bg=self.UI_PANEL, fg="#fde68a" if faction_name in watched else self.UI_DIM,
                    activebackground=self.UI_PANEL, activeforeground="#fde68a",
                    relief=tk.FLAT, bd=0, padx=4, cursor="hand2",
                    font=("Segoe UI Symbol", 10))
                watch_button.pack(side=tk.RIGHT, padx=(5, 0))
                self._bind_galaxy_scroll(watch_button)
            if rep:
                tk.Label(line, text=rep, fg=rep_color, bg=self.UI_PANEL,
                         font=("Segoe UI", 7, "bold"), padx=6).pack(side=tk.RIGHT, padx=(8, 0))
            bar = tk.Frame(faction_card, bg="#070a0e", height=5)
            bar.pack(fill=tk.X, padx=12, pady=(0, 5))
            tk.Frame(bar, bg="#21d189" if controls else COLOR_ACCENT).place(
                x=0, y=0, relheight=1, relwidth=max(0.0, min(1.0, influence)))
            self._bind_click(bar, lambda name=faction_name: self._show_galaxy_detail("faction", name))

        conflict_card = self._galaxy_card(content, "CONFLICTS", (4 if compact else 3) + row_offset, 0, accent="#ff7777")
        conflicts = state.get("conflicts") or []
        if not conflicts:
            self._galaxy_detail_line(
                conflict_card, "conflict", None, "No active conflicts",
                "Wars and elections appear here", self.UI_MUTED)
        for conflict_index, conflict in enumerate(conflicts):
            one, two = conflict.get("faction1") or {}, conflict.get("faction2") or {}
            one_score = int(one.get("won_days") or 0)
            two_score = int(two.get("won_days") or 0)
            score = f"{one_score}–{two_score}"
            leader = one.get("name") if one_score > two_score else two.get("name") if two_score > one_score else None
            conflict_detail = f"{str(conflict.get('war_type') or 'Conflict').title()} · {str(conflict.get('status') or 'active').title()}"
            if leader:
                conflict_detail += f" · Leader: {leader}"
            self._galaxy_detail_line(
                conflict_card, "conflict", conflict_index,
                f"{one.get('name') or '?'}  {score}  {two.get('name') or '?'}",
                conflict_detail, "#21d189" if leader else COLOR_TEXT)
            self._galaxy_detail_line(
                conflict_card, "conflict", conflict_index,
                f"{one.get('name') or '?'} stake: {one.get('stake') or '—'}",
                f"{two.get('name') or '?'} stake: {two.get('stake') or '—'}",
                self.UI_MUTED)

        goal_card = self._galaxy_card(content, "COMMUNITY GOALS", (5 if compact else 3) + row_offset,
                                      0 if compact else 1, accent="#fde68a")
        goals = list((state.get("community_goals") or {}).items())
        if not goals:
            self._galaxy_detail_line(
                goal_card, "goal", None, "No joined community goals",
                "Join at the named station mission board", self.UI_MUTED)
        for goal_id, goal in goals:
            detail = (f"{int(goal.get('contribution') or 0):,} contributed · Tier {goal.get('tier') or '—'}"
                      f" · Top {goal.get('percentile') or '—'}%")
            expiry = self._goal_expiry(goal.get("expiry"))
            if expiry:
                detail += f" · {expiry}"
            if goal.get("complete"):
                detail += " · COMPLETE"
            self._galaxy_detail_line(
                goal_card, "goal", goal_id, goal.get("title") or "Community Goal", detail,
                "#21d189" if goal.get("complete") else COLOR_TEXT)
            extra = f"Galaxy total {int(goal.get('current_total') or 0):,} · {int(goal.get('contributors') or 0):,} contributors"
            if goal.get("top_rank"):
                extra += " · TOP RANK"
            if goal.get("bonus"):
                extra += f" · Bonus {goal.get('bonus')}"
            self._galaxy_detail_line(
                goal_card, "goal", goal_id, extra,
                f"{goal.get('system') or '—'} · {goal.get('market') or '—'}", self.UI_MUTED)

        content.update_idletasks()
        self._galaxy_canvas.configure(scrollregion=self._galaxy_canvas.bbox("all"))

    def _toggle_watch_and_render(self, faction_name):
        if self._toggle_faction_watch:
            self._toggle_faction_watch(faction_name)
            self._render_galaxy_overview()

    # ── System list ───────────────────────────────────────────────────────────

    def _initial_load(self, attempt=0):
        if not self.is_open():
            return
        self._initial_retry_job = None
        self._render_galaxy_overview()
        self._render_squadron_command()
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
        self._render_galaxy_summary(t, sys_name)

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

    def _render_galaxy_summary(self, text, system_name):
        state = self._get_galaxy_state() or {}
        powerplay = state.get("powerplay") or {}
        goals = list((state.get("community_goals") or {}).values())
        squadron = state.get("squadron") or {}
        same_system = state.get("galaxy_system") == system_name
        pp_system = state.get("pp_system") if same_system else None
        conflicts = state.get("conflicts") if same_system else []
        if not any((powerplay, goals, squadron, pp_system, conflicts)):
            return
        text.insert(tk.END, "  GALAXY STATUS\n", "hdr")
        if powerplay:
            text.insert(tk.END,
                        f"  POWERPLAY  {powerplay.get('power') or '—'}  |  Rank {powerplay.get('rank') or 0}"
                        f"  |  {int(powerplay.get('merits') or 0):,} merits"
                        f"  |  +{int(powerplay.get('session_merits') or 0):,} this session\n",
                        "name")
        if pp_system:
            text.insert(tk.END,
                        f"  SYSTEM     {pp_system.get('controlling') or '—'}  |  {pp_system.get('state') or 'Unknown'}"
                        f"  |  Reinforcement {pp_system.get('reinforcement') or 0}"
                        f"  |  Undermining {pp_system.get('undermining') or 0}\n",
                        "name")
        for conflict in conflicts or []:
            one, two = conflict.get("faction1") or {}, conflict.get("faction2") or {}
            text.insert(tk.END,
                        f"  {str(conflict.get('war_type') or 'CONFLICT').upper():<10} "
                        f"{one.get('name') or '?'} {one.get('won_days') or 0}–{two.get('won_days') or 0} "
                        f"{two.get('name') or '?'}  |  {one.get('stake') or two.get('stake') or 'No stake'}\n",
                        "state_war")
        if squadron:
            text.insert(tk.END, f"  SQUADRON   {squadron.get('name') or '—'}  |  Rank {squadron.get('rank') or 0}\n", "name")
        for goal in goals:
            text.insert(tk.END,
                        f"  COMMUNITY  {goal.get('title') or 'Goal'}  |  {int(goal.get('contribution') or 0):,} contributed"
                        f"  |  Tier {goal.get('tier') or '—'}  |  Top {goal.get('percentile') or '—'}%\n",
                        "name")
        text.insert(tk.END, "  " + "─" * 82 + "\n", "sep")
