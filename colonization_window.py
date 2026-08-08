"""
colonization_window.py — Colonization Tracker popup for VoidCompass.

Tracks Elite Dangerous construction depot projects: required commodities,
delivery progress, notes.  Persisted to colonisation_data.json next to
the executable (so players can back it up / inspect it).

Usage:
    win = ColonizationWindow(root, config, projects_dict, save_callback)
    win.refresh()   # call whenever projects_dict has changed externally
"""

import json
import os
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config
from ui_theme import THEME, ThemedWindowMixin, apply_window, button, configure_ttk, scrollbar, window_surface

COLOR_ACCENT = THEME.accent
COLOR_ORANGE = THEME.orange
COLOR_TEXT = THEME.text

# ── JSON persistence ──────────────────────────────────────────────────────────

COLONISATION_DATA_FILE = "colonisation_data.json"


def load_colonisation_data(path=None) -> dict:
    """Load all tracked projects from JSON.  Returns {market_id(int): project_dict}."""
    path = path or os.path.join(os.getcwd(), COLONISATION_DATA_FILE)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # Keys stored as strings; cast back to int
        return {int(k): v for k, v in raw.items()}
    except Exception:
        return {}


def save_colonisation_data(projects: dict, path=None):
    """Save all tracked projects to JSON."""
    path = path or os.path.join(os.getcwd(), COLONISATION_DATA_FILE)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in projects.items()}, f, indent=2)
    except Exception:
        pass


# ── Window ────────────────────────────────────────────────────────────────────

class ColonizationWindow(ThemedWindowMixin):
    # Theme — matches VoidCompass dark palette
    UI_FONT   = ("Segoe UI", 9)
    UI_BOLD   = ("Segoe UI", 9, "bold")
    UI_MONO   = ("Consolas", 9)
    UI_MONO_B = ("Consolas", 10, "bold")

    def __init__(self, root, config: dict, projects: dict, save_callback, overlay_callback=None,
                 cargo_capacity_provider=None, embedded=False, ui_post_callback=None):
        """
        projects     – live reference to dashboard's colonisation_projects dict
        save_callback – callable(projects) that persists changes to JSON
        """
        self.root          = root
        self.config        = config
        self.projects      = projects       # shared reference — always current
        self.save_callback = save_callback
        self.overlay_callback = overlay_callback
        self.cargo_capacity_provider = cargo_capacity_provider
        self.ui_post_callback = ui_post_callback
        self._selected_mid = None
        self._notes_dirty  = False

        self.embedded = embedded
        self.win = window_surface(root, embedded=embedded)
        self.win.title("Architect Command Centre — Void Compass")
        apply_window(self.win)
        self.win.geometry(config.get("colonisation_window_geometry", "740x560"))
        self.win.resizable(True, True)
        self.win.minsize(560, 420)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._refresh_list()
        self._refresh_planner()
        self._refresh_command()

        # Auto-select most recently updated project
        if self.projects:
            best = max(self.projects.values(), key=lambda p: p.get("last_updated") or 0)
            self._select(best["market_id"])

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def is_open(self) -> bool:
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False

    def _post_ui(self, callback, key=None):
        if callable(self.ui_post_callback):
            return self.ui_post_callback(callback, key=key)
        return self.root.after(0, callback)

    def lift(self):
        try:
            self.win.lift()
            self.win.focus_force()
        except Exception:
            pass

    def refresh(self):
        """Call when projects data changed externally (new depot event, etc.)."""
        if not self.is_open():
            return
        self.win.after(0, self._do_refresh)

    def _do_refresh(self):
        self._refresh_list()
        self._refresh_planner()
        self._refresh_command()
        if self._selected_mid is not None:
            if self._selected_mid in self.projects:
                self._render(self._selected_mid)
            else:
                self._clear_detail()

    def _on_close(self):
        if self._notes_dirty:
            self._flush_notes()
        try:
            self.config["colonisation_window_geometry"] = self.win.geometry()
            save_config(self.config)
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        configure_ttk(self.win, "Colony")
        # ── Header bar ────────────────────────────────────────────────────────
        hdr = tk.Frame(self.win, bg="#0c1014", height=46)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="ARCHITECT COMMAND CENTRE",
                 font=("Segoe UI", 13, "bold"), fg=COLOR_ACCENT, bg="#0c1014").pack(
            side=tk.LEFT, padx=14, pady=8)
        self._status_badge = tk.Label(hdr, text="", fg="black", bg=self.UI_DIM,
                                       font=("Segoe UI", 7, "bold"), padx=8, pady=3)
        self._status_badge.pack(side=tk.RIGHT, padx=14, pady=12)

        # ── Main split ────────────────────────────────────────────────────────
        main = tk.Frame(self.win, bg=self.UI_BG)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 8))

        # ── Left: project list ────────────────────────────────────────────────
        left = tk.Frame(main, bg=self.UI_PANEL, width=210)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        left.pack_propagate(False)

        tk.Label(left, text="CONSTRUCTION SITES",
                 font=("Segoe UI", 8, "bold"), fg=COLOR_ORANGE, bg=self.UI_PANEL
                 ).pack(anchor="w", padx=10, pady=(10, 4))

        list_wrap = tk.Frame(left, bg=self.UI_PANEL)
        list_wrap.pack(fill=tk.BOTH, expand=True, padx=4)

        list_scroll = scrollbar(list_wrap, orient=tk.VERTICAL)
        self._list_canvas = tk.Canvas(list_wrap, bg=self.UI_PANEL,
                                       highlightthickness=0,
                                       yscrollcommand=list_scroll.set)
        list_scroll.config(command=self._list_canvas.yview)
        self._list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._list_inner = tk.Frame(self._list_canvas, bg=self.UI_PANEL)
        self._list_window = self._list_canvas.create_window(
            (0, 0), window=self._list_inner, anchor="nw")

        self._list_inner.bind("<Configure>", self._on_list_configure)
        self._list_canvas.bind("<Configure>", self._on_canvas_configure)
        self._list_canvas.bind("<MouseWheel>",
                               lambda e: self._list_canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        # ── Right: project detail + planner tabs ─────────────────────────────
        right = tk.Frame(main, bg=self.UI_PANEL)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._tabs = ttk.Notebook(right, style="Colony.TNotebook")
        self._tabs.pack(fill=tk.BOTH, expand=True)

        detail_tab = tk.Frame(self._tabs, bg=self.UI_PANEL)
        planner_tab = tk.Frame(self._tabs, bg=self.UI_BG)
        command_tab = tk.Frame(self._tabs, bg=self.UI_BG)
        self._tabs.add(command_tab, text="Command")
        self._tabs.add(detail_tab, text="Project Details")
        self._tabs.add(planner_tab, text="Shopping List")
        self._build_command_tab(command_tab)
        self._build_planner_tab(planner_tab)
        right = detail_tab

        # Site info labels
        info = tk.Frame(right, bg=self.UI_PANEL)
        info.pack(fill=tk.X, padx=12, pady=(10, 0))
        self._sys_lbl = tk.Label(info, text="Select a construction site →",
                                  font=("Segoe UI", 12, "bold"), fg=COLOR_TEXT,
                                  bg=self.UI_PANEL, anchor="w")
        self._sys_lbl.pack(fill=tk.X)
        self._body_lbl = tk.Label(info, text="",
                                   font=self.UI_MONO, fg=self.UI_MUTED,
                                   bg=self.UI_PANEL, anchor="w")
        self._body_lbl.pack(fill=tk.X)

        # Progress
        prog_row = tk.Frame(right, bg=self.UI_PANEL)
        prog_row.pack(fill=tk.X, padx=12, pady=(8, 2))
        self._prog_lbl = tk.Label(prog_row, text="Progress: —",
                                   font=("Segoe UI", 9, "bold"),
                                   fg=COLOR_ACCENT, bg=self.UI_PANEL)
        self._prog_lbl.pack(side=tk.LEFT)
        self._prog_pct = tk.Label(prog_row, text="",
                                   font=self.UI_MONO, fg=self.UI_MUTED, bg=self.UI_PANEL)
        self._prog_pct.pack(side=tk.RIGHT)

        bar_bg = tk.Frame(right, bg="#1a2430", height=10)
        bar_bg.pack(fill=tk.X, padx=12, pady=(0, 8))
        bar_bg.pack_propagate(False)
        self._bar_fill = tk.Frame(bar_bg, bg=COLOR_ACCENT, height=10)
        self._bar_fill.place(x=0, y=0, relheight=1.0, relwidth=0.0)

        # Commodity table
        tbl_wrap = tk.Frame(right, bg="#0b0f13")
        tbl_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 4))
        tbl_scroll = scrollbar(tbl_wrap, orient=tk.VERTICAL)
        self._table = tk.Text(
            tbl_wrap,
            bg="#0b0f13", fg=COLOR_TEXT,
            font=("Consolas", 9),
            relief=tk.FLAT, highlightthickness=0, borderwidth=0,
            wrap=tk.NONE, padx=6, pady=4,
            yscrollcommand=tbl_scroll.set,
            state=tk.DISABLED,
        )
        tbl_scroll.config(command=self._table.yview)
        self._table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tbl_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._table.tag_config("hdr",      foreground=COLOR_ORANGE, font=("Consolas", 9, "bold"))
        self._table.tag_config("done",     foreground="#00cc44")
        self._table.tag_config("partial",  foreground=COLOR_ORANGE)
        self._table.tag_config("pending",  foreground=self.UI_MUTED)
        self._table.tag_config("sep",      foreground="#1a2228")
        self._table.tag_config("total",    foreground=COLOR_ACCENT, font=("Consolas", 9, "bold"))
        self._table.tag_config("complete", foreground="#00cc44",    font=("Consolas", 9, "bold"))
        self._table.tag_config("failed",   foreground="#cc0000")

        # Notes
        tk.Label(right, text="NOTES", font=("Segoe UI", 8, "bold"),
                 fg=self.UI_MUTED, bg=self.UI_PANEL
                 ).pack(anchor="w", padx=12, pady=(4, 0))
        notes_bg = tk.Frame(right, bg="#0b0f13", height=62)
        notes_bg.pack(fill=tk.X, padx=12, pady=(2, 4))
        notes_bg.pack_propagate(False)
        self._notes = tk.Text(
            notes_bg,
            bg="#0b0f13", fg=COLOR_TEXT, insertbackground=COLOR_ACCENT,
            font=("Consolas", 9),
            relief=tk.FLAT, highlightthickness=0, borderwidth=0,
            wrap=tk.WORD, padx=6, pady=4,
        )
        self._notes.pack(fill=tk.BOTH, expand=True)
        self._notes.bind("<<Modified>>", self._on_notes_modified)

        # Footer
        foot = tk.Frame(right, bg=self.UI_PANEL)
        foot.pack(fill=tk.X, padx=12, pady=(0, 10))

        self._action_button(foot, "Copy Shopping List",
                            self._copy_shopping_list).pack(side=tk.LEFT)
        if self.overlay_callback:
            self._action_button(foot, "Toggle Overlay",
                                self.overlay_callback, accent=True).pack(side=tk.LEFT, padx=(8, 0))
        self._action_button(foot, "Delete Project",
                            self._delete_project, muted=True).pack(side=tk.LEFT, padx=(8, 0))
        self._updated_lbl = tk.Label(foot, text="",
                                      font=("Consolas", 8), fg=self.UI_DIM, bg=self.UI_PANEL)
        self._updated_lbl.pack(side=tk.RIGHT)

    def _action_button(self, parent, text, cmd, accent=False, muted=False):
        return button(parent, text, cmd, accent=accent, muted=muted, pady=4)

    def _build_command_tab(self, parent):
        cards = tk.Frame(parent, bg=self.UI_BG)
        cards.pack(fill=tk.X, padx=10, pady=10)
        self._command_labels = {}
        for key, title, colour in (
            ("sites", "ACTIVE SITES", COLOR_ACCENT), ("progress", "DELIVERED", self.UI_OK),
            ("remaining", "REMAINING", COLOR_ORANGE), ("trips", "CARGO TRIPS", COLOR_TEXT),
        ):
            card = tk.Frame(cards, bg=self.UI_PANEL, highlightbackground=self.UI_BORDER, highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
            tk.Frame(card, bg=colour, height=2).pack(fill=tk.X)
            tk.Label(card, text=title, fg=self.UI_MUTED, bg=self.UI_PANEL,
                     font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
            value = tk.Label(card, text="—", fg=colour, bg=self.UI_PANEL,
                             font=("Consolas", 12, "bold"))
            value.pack(anchor="w", padx=10, pady=(2, 8))
            self._command_labels[key] = value
        tk.Label(parent, text="RECENT CONSTRUCTION ACTIVITY", fg=COLOR_ORANGE, bg=self.UI_BG,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(2, 4))
        self._command_activity = tk.Text(
            parent, bg="#0b0f13", fg=COLOR_TEXT, relief=tk.FLAT, bd=0,
            padx=10, pady=8, font=("Consolas", 9), wrap=tk.WORD,
        )
        self._command_activity.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._command_activity.configure(state=tk.DISABLED)

    def _refresh_command(self):
        if not hasattr(self, "_command_activity"):
            return
        active = [p for p in self.projects.values() if not p.get("complete") and not p.get("failed")]
        required = delivered = remaining = 0
        for project in active:
            for resource in project.get("resources") or []:
                req = int(resource.get("required") or 0)
                done = min(req, int(resource.get("provided") or 0))
                required += req
                delivered += done
                remaining += max(0, req - done)
        try:
            cargo_capacity = max(0, int(self.cargo_capacity_provider() or 0)) if self.cargo_capacity_provider else 0
        except Exception:
            cargo_capacity = 0
        trips = ((remaining + cargo_capacity - 1) // cargo_capacity) if cargo_capacity else None
        self._command_labels["sites"].config(text=str(len(active)))
        pct = (delivered / required * 100) if required else 0
        self._command_labels["progress"].config(text=f"{delivered:,} T / {pct:.0f}%")
        self._command_labels["remaining"].config(text=f"{remaining:,} T")
        self._command_labels["trips"].config(text=str(trips) if trips is not None else "SET BY SHIP")
        activity = []
        for project in self.projects.values():
            name = project.get("system_name") or project.get("body_name") or "Unknown site"
            for row in project.get("activity") or []:
                activity.append((row.get("timestamp"), name, row))
        activity.sort(key=lambda item: str(item[0] or ""), reverse=True)
        lines = []
        for stamp, name, row in activity[:80]:
            if isinstance(stamp, (int, float)):
                when = datetime.fromtimestamp(stamp).strftime("%Y-%m-%d %H:%M")
            else:
                when = str(stamp or "").replace("T", " ")[:16]
            lines.append(f"{when}  [{row.get('type') or 'UPDATE'}]  {name}\n    {row.get('detail') or ''}")
        if not lines:
            lines = ["No contribution activity recorded yet. Visit a construction depot or make a delivery."]
        self._command_activity.configure(state=tk.NORMAL)
        self._command_activity.delete("1.0", tk.END)
        self._command_activity.insert(tk.END, "\n\n".join(lines))
        self._command_activity.configure(state=tk.DISABLED)

    def _build_planner_tab(self, parent):
        header = tk.Frame(parent, bg=self.UI_BG)
        header.pack(fill=tk.X, padx=10, pady=(10, 6))
        self._planner_summary = tk.Label(
            header, text="", font=("Consolas", 8),
            fg=self.UI_MUTED, bg=self.UI_BG,
        )
        self._planner_summary.pack(side=tk.RIGHT)
        self._action_button(
            header, "Copy Shopping List",
            self._copy_global_shopping_list, accent=True,
        ).pack(side=tk.LEFT)

        style = configure_ttk(self.win, "Colony")
        style.configure(
            "ColonyPlanner.Treeview",
            background="#0b0f13",
            foreground=COLOR_TEXT,
            fieldbackground="#0b0f13",
            rowheight=24,
            borderwidth=0,
        )
        style.configure(
            "ColonyPlanner.Treeview.Heading",
            background=self.UI_PANEL,
            foreground=COLOR_ORANGE,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
        )
        style.map(
            "ColonyPlanner.Treeview",
            background=[("selected", "#12313c")],
            foreground=[("selected", COLOR_TEXT)],
        )

        frame = tk.Frame(parent, bg=self.UI_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        cols = ("commodity", "remaining", "required", "delivered", "projects")
        self._planner_tree = ttk.Treeview(frame, columns=cols, show="headings", style="ColonyPlanner.Treeview")
        specs = (
            ("commodity", "Commodity", 210, tk.W),
            ("remaining", "Remaining", 90, tk.E),
            ("required", "Required", 90, tk.E),
            ("delivered", "Delivered", 90, tk.E),
            ("projects", "Projects", 260, tk.W),
        )
        for col, label, width, anchor in specs:
            self._planner_tree.heading(col, text=label)
            self._planner_tree.column(col, width=width, anchor=anchor)
        scroll = scrollbar(frame, orient=tk.VERTICAL, command=self._planner_tree.yview)
        self._planner_tree.configure(yscrollcommand=scroll.set)
        self._planner_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _planner_rows(self):
        totals = {}
        active_projects = 0
        for project in self.projects.values():
            if project.get("complete") or project.get("failed"):
                continue
            active_projects += 1
            project_name = project.get("system_name") or project.get("body_name") or "Unknown"
            for res in project.get("resources") or []:
                name = res.get("display") or res.get("name") or "Unknown"
                required = int(res.get("required") or 0)
                delivered = min(int(res.get("provided") or 0), required)
                remaining = max(0, required - delivered)
                if remaining <= 0:
                    continue
                entry = totals.setdefault(
                    name,
                    {"commodity": name, "remaining": 0, "required": 0, "delivered": 0, "projects": set()},
                )
                entry["remaining"] += remaining
                entry["required"] += required
                entry["delivered"] += delivered
                entry["projects"].add(project_name)
        rows = sorted(totals.values(), key=lambda row: (-row["remaining"], row["commodity"].lower()))
        return active_projects, rows

    def _refresh_planner(self):
        if not hasattr(self, "_planner_tree"):
            return
        active_projects, rows = self._planner_rows()
        for item_id in self._planner_tree.get_children():
            self._planner_tree.delete(item_id)
        for row in rows:
            self._planner_tree.insert(
                "",
                tk.END,
                values=(
                    row["commodity"],
                    f"{row['remaining']:,}",
                    f"{row['required']:,}",
                    f"{row['delivered']:,}",
                    ", ".join(sorted(row["projects"])[:4]),
                ),
            )
        self._planner_summary.config(
            text=f"{active_projects} active projects | {sum(r['remaining'] for r in rows):,} tons remaining"
        )

    def _copy_global_shopping_list(self):
        _active_projects, rows = self._planner_rows()
        lines = ["Colonisation shopping list"]
        for row in rows:
            lines.append(f"{row['commodity']}: {row['remaining']:,}")
        if len(lines) == 1:
            lines.append("(nothing remaining)")
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))

    def _on_list_configure(self, event):
        self._list_canvas.configure(scrollregion=self._list_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._list_canvas.itemconfig(self._list_window, width=event.width)

    # ── Project list ──────────────────────────────────────────────────────────

    def _refresh_list(self):
        for w in self._list_inner.winfo_children():
            w.destroy()

        # Badge: total / complete
        total    = len(self.projects)
        complete = sum(1 for p in self.projects.values() if p.get("complete"))
        if total:
            self._status_badge.config(text=f"{complete}/{total} COMPLETE",
                                       bg="#00884a" if complete == total else self.UI_DIM)
        else:
            self._status_badge.config(text="NO SITES", bg=self.UI_DIM)

        if not self.projects:
            tk.Label(self._list_inner,
                     text="No sites tracked yet.\n\nVisit a construction\ndepot in-game to\nbegin tracking.",
                     font=("Consolas", 8), fg=self.UI_MUTED, bg=self.UI_PANEL,
                     justify=tk.LEFT
                     ).pack(anchor="w", padx=8, pady=10)
            return

        # Sort: active first (by progress desc), then complete, then failed
        def _sort_key(p):
            if p.get("complete"):
                return (2, -(p.get("last_updated") or 0))
            if p.get("failed"):
                return (3, -(p.get("last_updated") or 0))
            return (0, -(p.get("progress") or 0))

        for proj in sorted(self.projects.values(), key=_sort_key):
            self._add_list_row(proj)

    def _add_list_row(self, proj):
        mid      = proj.get("market_id")
        sys_name = proj.get("system_name", "Unknown")
        pct      = int((proj.get("progress") or 0) * 100)
        complete = proj.get("complete", False)
        failed   = proj.get("failed", False)

        is_sel   = (mid == self._selected_mid)
        row_bg   = "#0d1317" if is_sel else self.UI_PANEL
        sep_col  = COLOR_ACCENT if is_sel else self.UI_BORDER

        row = tk.Frame(self._list_inner, bg=row_bg, cursor="hand2",
                       highlightbackground=sep_col, highlightthickness=1)
        row.pack(fill=tk.X, pady=(0, 3))

        # Name (truncated)
        name_disp = sys_name if len(sys_name) <= 22 else sys_name[:21] + "…"
        tk.Label(row, text=name_disp,
                 font=("Segoe UI", 9, "bold" if is_sel else "normal"),
                 fg=COLOR_ACCENT if is_sel else COLOR_TEXT,
                 bg=row_bg, anchor="w"
                 ).pack(fill=tk.X, padx=8, pady=(4, 0))

        # Status / progress text
        if complete:
            status_txt = "✓ Complete"
            status_fg  = "#00cc44"
        elif failed:
            status_txt = "✗ Failed"
            status_fg  = "#cc0000"
        else:
            notes_mark = "  [NOTE]" if (proj.get("notes") or "").strip() else ""
            status_txt = f"{pct}% delivered{notes_mark}"
            status_fg  = COLOR_ACCENT if pct > 0 else self.UI_MUTED

        tk.Label(row, text=status_txt,
                 font=("Consolas", 8), fg=status_fg, bg=row_bg, anchor="w"
                 ).pack(fill=tk.X, padx=8, pady=(0, 4))

        # Mini progress bar
        if not complete and not failed and pct > 0:
            mini_bg = tk.Frame(row, bg="#1a2430", height=3)
            mini_bg.pack(fill=tk.X, padx=8, pady=(0, 4))
            mini_bg.pack_propagate(False)
            tk.Frame(mini_bg, bg=COLOR_ACCENT, height=3).place(
                x=0, y=0, relheight=1.0, relwidth=min(1.0, pct / 100))

        for w in row.winfo_children():
            w.bind("<Button-1>", lambda e, m=mid: self._select(m))
        row.bind("<Button-1>", lambda e, m=mid: self._select(m))

    # ── Detail panel ──────────────────────────────────────────────────────────

    def _select(self, market_id):
        if self._notes_dirty:
            self._flush_notes()
        self._selected_mid = market_id
        self._refresh_list()
        self._render(market_id)

    def _render(self, market_id):
        proj = self.projects.get(market_id)
        if not proj:
            self._clear_detail()
            return

        sys_name   = proj.get("system_name", "Unknown")
        body_name  = proj.get("body_name", "")
        body_short = (body_name.replace(sys_name, "").strip()
                      if body_name.startswith(sys_name) else body_name)

        self._sys_lbl.config(text=sys_name)
        self._body_lbl.config(text=body_short or body_name)

        progress   = float(proj.get("progress") or 0)
        pct_int    = int(progress * 100)
        complete   = proj.get("complete", False)
        failed     = proj.get("failed", False)

        if complete:
            prog_txt = "CONSTRUCTION COMPLETE"
            bar_col  = "#00cc44"
            prog_fg  = "#00cc44"
            pct_txt  = "100%"
        elif failed:
            prog_txt = "CONSTRUCTION FAILED"
            bar_col  = "#cc0000"
            prog_fg  = "#cc0000"
            pct_txt  = f"{pct_int}%"
        else:
            prog_txt = "Progress"
            bar_col  = COLOR_ACCENT
            prog_fg  = COLOR_ACCENT
            pct_txt  = f"{pct_int}%"

        self._prog_lbl.config(text=prog_txt, fg=prog_fg)
        self._prog_pct.config(text=pct_txt)
        self._bar_fill.config(bg=bar_col)
        self._bar_fill.place(relwidth=min(1.0, progress))

        # Last updated
        ts = proj.get("last_updated", 0)
        try:
            dt_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""
            self._updated_lbl.config(text=f"Updated: {dt_str}" if dt_str else "")
        except Exception:
            self._updated_lbl.config(text="")

        # Commodity table
        resources = proj.get("resources") or []
        self._table.config(state=tk.NORMAL)
        self._table.delete("1.0", tk.END)

        if not resources:
            self._table.insert(tk.END,
                "  No resource data yet.\n"
                "  Visit the construction depot to load requirements.\n",
                "pending")
        else:
            # Header row
            self._table.insert(
                tk.END,
                f"  {'COMMODITY':<30} {'REQUIRED':>9} {'DELIVERED':>10} {'REMAINING':>10}\n",
                "hdr",
            )
            self._table.insert(tk.END, "  " + "─" * 63 + "\n", "sep")

            total_req  = 0
            total_done = 0

            for r in sorted(resources, key=lambda x: x.get("display", "").lower()):
                name  = r.get("display") or r.get("name", "")
                req   = int(r.get("required") or 0)
                prov  = min(int(r.get("provided") or 0), req)
                left  = max(0, req - prov)
                total_req  += req
                total_done += prov

                name_disp = name if len(name) <= 30 else name[:29] + "…"

                if prov >= req:
                    tag  = "done"
                    tick = " ✓"
                elif prov > 0:
                    tag  = "partial"
                    tick = ""
                else:
                    tag  = "pending"
                    tick = ""

                line = f"  {name_disp:<30} {req:>9,} {prov:>10,} {left:>10,}{tick}\n"
                self._table.insert(tk.END, line, tag)

            total_left = max(0, total_req - total_done)
            self._table.insert(tk.END, "  " + "─" * 63 + "\n", "sep")
            total_tag = "complete" if total_left == 0 else "total"
            self._table.insert(
                tk.END,
                f"  {'TOTAL':<30} {total_req:>9,} {total_done:>10,} {total_left:>10,}\n",
                total_tag,
            )

        self._table.config(state=tk.DISABLED)

        # Notes — load without firing the Modified event
        self._notes.config(state=tk.NORMAL)
        self._notes.delete("1.0", tk.END)
        self._notes.insert("1.0", proj.get("notes", ""))
        self._notes.edit_modified(False)
        self._notes_dirty = False

    def _clear_detail(self):
        self._sys_lbl.config(text="Select a construction site →")
        self._body_lbl.config(text="")
        self._prog_lbl.config(text="Progress: —", fg=COLOR_ACCENT)
        self._prog_pct.config(text="")
        self._bar_fill.place(relwidth=0.0)
        self._table.config(state=tk.NORMAL)
        self._table.delete("1.0", tk.END)
        self._table.config(state=tk.DISABLED)
        self._notes.delete("1.0", tk.END)
        self._notes.edit_modified(False)
        self._notes_dirty = False
        self._updated_lbl.config(text="")

    # ── Notes ─────────────────────────────────────────────────────────────────

    def _on_notes_modified(self, _event):
        if self._notes.edit_modified():
            self._notes_dirty = True

    def _flush_notes(self):
        if self._selected_mid is None:
            return
        proj = self.projects.get(self._selected_mid)
        if proj is not None:
            proj["notes"] = self._notes.get("1.0", tk.END).rstrip("\n")
        self._notes.edit_modified(False)
        self._notes_dirty = False
        self.save_callback(self.projects)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _copy_shopping_list(self):
        mid = self._selected_mid
        if mid is None:
            return
        proj = self.projects.get(mid)
        if not proj:
            return
        lines = [f"Shopping list — {proj.get('system_name', 'Unknown')}"]
        any_left = False
        for r in sorted(proj.get("resources") or [], key=lambda x: x.get("display", "").lower()):
            left = max(0, int(r.get("required") or 0) - int(r.get("provided") or 0))
            if left > 0:
                lines.append(f"  {r.get('display') or r.get('name', '?')}: {left:,}")
                any_left = True
        if not any_left:
            lines.append("  (nothing remaining — construction complete!)")
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(lines))
        except Exception:
            pass

    def _delete_project(self):
        mid = self._selected_mid
        if mid is None:
            return
        proj = self.projects.get(mid)
        if not proj:
            return
        sys_name = proj.get("system_name", "Unknown")
        if not messagebox.askyesno(
            "Delete Project",
            f"Delete colonization record for\n{sys_name}?\n\nThis cannot be undone.",
            parent=self.win,
        ):
            return
        self.projects.pop(mid, None)
        self._selected_mid = None
        self.save_callback(self.projects)
        self._refresh_list()
        self._clear_detail()
