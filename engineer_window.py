"""Native Engineering Workshop for VoidCompass.

Combines live journal material/locker stock, engineer access, upgrade goals,
shared shopping requirements and nearby material traders.  Commander-specific
state is persisted in ``engineer_materials.json`` by the dashboard.
"""

import json
import os
import shutil
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config
from engineering_data import (
    BLUEPRINTS,
    BLUEPRINT_INFO,
    collection_priorities,
    engineer_blueprints,
    engineer_info,
    ENGINEERS,
    GRADE_CAP,
    MATERIALS,
    material_info,
    material_relevance,
    ODYSSEY_BLUEPRINTS,
    odyssey_item_use,
    odyssey_inventory_counts,
    odyssey_wishlist_plan,
    pinned_plans,
    wishlist_plan,
)
from trade import spansh
from companion_features import fsd_injections
from ui_theme import (
    THEME,
    ThemedWindowMixin,
    apply_window,
    button,
    configure_ttk,
    scrollbar,
    window_surface,
)

COLOR_ACCENT = THEME.accent
COLOR_ORANGE = THEME.orange
COLOR_TEXT = THEME.text

ENGINEER_MATERIALS_FILE = "engineer_materials.json"

def get_material_category(key: str) -> str:
    """Return 'raw', 'manufactured', or 'encoded' for an internal material name."""
    return material_info(key).get("category", "manufactured")


def load_engineer_materials(path=None) -> dict:
    path = path or os.path.join(os.getcwd(), ENGINEER_MATERIALS_FILE)
    if not os.path.exists(path):
        return {"raw": {}, "manufactured": {}, "encoded": {}, "engineers": {},
                "pinned_blueprints": [], "odyssey_goals": [], "ship_locker": {}, "last_updated": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for cat in ("raw", "manufactured", "encoded"):
            data.setdefault(cat, {})
        data.setdefault("engineers", {})
        data.setdefault("pinned_blueprints", [])
        data.setdefault("odyssey_goals", [])
        data.setdefault("ship_locker", {})
        return data
    except Exception as exc:
        backup = None
        try:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = f"{path}.corrupt-{stamp}"
            shutil.copy2(path, backup)
        except Exception:
            backup = None
        return {"raw": {}, "manufactured": {}, "encoded": {}, "engineers": {},
                "pinned_blueprints": [], "odyssey_goals": [], "ship_locker": {}, "last_updated": None,
                "_load_warning": f"Could not read engineering data: {exc}",
                "_corrupt_backup": backup}


def save_engineer_materials(materials: dict, path=None):
    path = path or os.path.join(os.getcwd(), ENGINEER_MATERIALS_FILE)
    temp_path = path + ".tmp"
    try:
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        payload = {key: value for key, value in materials.items() if not str(key).startswith("_")}
        with open(temp_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
        materials.pop("_save_error", None)
        return True
    except Exception as exc:
        materials["_save_error"] = str(exc)
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        return False


class EngineerWindow(ThemedWindowMixin):

    _TABS = [
        ("command",      "COMMAND",      "#67e8f9"),
        ("wishlist",     "WISHLIST",     "#b0d8a0"),
        ("inventory",    "INVENTORY",    "#93c5fd"),
        ("engineers",    "ENGINEERS",    "#c4b5fd"),
        ("odyssey",      "ODYSSEY",      "#f9a8d4"),
    ]

    def __init__(self, root, config: dict, materials: dict, save_callback,
                 get_current_system=None, get_current_coords=None,
                 plot_system_callback=None, is_active_callback=None,
                 embedded=False):
        self.root          = root
        self.config        = config
        self.materials     = materials
        self.save_callback = save_callback
        self.get_current_system = get_current_system or (lambda: "")
        self.get_current_coords = get_current_coords or (lambda: None)
        self.plot_system_callback = plot_system_callback
        self.is_active_callback = is_active_callback
        self._active_tab   = "command"
        self._row_meta = {}
        self._selected_engineer = None
        self._engineer_cards = {}
        self._search_job = None
        self._refresh_job = None
        self._refresh_pending = False
        self._trader_results = []
        self._trader_searching = False

        self.embedded = embedded
        self.win = window_surface(root, embedded=embedded)
        self.win.title("Engineering Command — Void Compass")
        apply_window(self.win)
        self.win.geometry(config.get("engineer_window_geometry", "740x560"))
        self.win.resizable(True, True)
        self.win.minsize(560, 380)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._redraw()

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

    def refresh(self):
        if not self.is_open():
            return
        if callable(self.is_active_callback) and not self.is_active_callback():
            self._refresh_pending = True
            return
        if self._refresh_job is not None:
            return
        self._refresh_job = self.win.after(100, self._run_refresh)

    def _run_refresh(self):
        self._refresh_job = None
        if not self.is_open():
            return
        self._refresh_pending = False
        self._redraw()

    def on_shown(self):
        if self._refresh_job is not None:
            try:
                self.win.after_cancel(self._refresh_job)
            except Exception:
                pass
            self._refresh_job = None
        self._refresh_pending = False
        self._redraw()

    def _on_close(self):
        if self._refresh_job is not None:
            try:
                self.win.after_cancel(self._refresh_job)
            except Exception:
                pass
            self._refresh_job = None
        if self._search_job is not None:
            try:
                self.win.after_cancel(self._search_job)
            except Exception:
                pass
            self._search_job = None
        try:
            self.config["engineer_window_geometry"] = self.win.geometry()
            save_config(self.config)
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        configure_ttk(self.win, "Engineer")

        # Header
        hdr = tk.Frame(self.win, bg="#0c1014", height=58)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        title_box = tk.Frame(hdr, bg="#0c1014")
        title_box.pack(side=tk.LEFT, padx=14)
        tk.Label(title_box, text="ENGINEERING COMMAND",
                 font=("Segoe UI", 14, "bold"), fg=COLOR_ACCENT, bg="#0c1014"
                 ).pack(anchor="w", pady=(7, 0))
        tk.Label(title_box, text="live inventory // shared wishlist // collection priorities",
                 font=("Consolas", 8), fg=self.UI_MUTED, bg="#0c1014"
                 ).pack(anchor="w")
        self._sync_lbl = tk.Label(hdr, text="Not yet synced",
                                   fg=self.UI_DIM, bg="#0c1014",
                                   font=("Consolas", 8))
        self._sync_lbl.pack(side=tk.RIGHT, padx=14)
        self._route_btn = button(hdr, "ROUTE SELECTED", self._plot_selected, muted=True,
                                 padx=8, pady=4)
        self._route_btn.pack(side=tk.RIGHT, padx=4, pady=12)
        self._route_btn.config(state=tk.DISABLED)

        metrics = tk.Frame(self.win, bg=self.UI_BG)
        metrics.pack(fill=tk.X, padx=8, pady=(7, 5))
        self._metric_values = {}
        for index, label in enumerate(("WISHLIST", "READY", "TO COLLECT", "ENGINEERS")):
            card = tk.Frame(metrics, bg=self.UI_PANEL, highlightbackground=self.UI_BORDER, highlightthickness=1)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 5, 0))
            metrics.grid_columnconfigure(index, weight=1)
            tk.Label(card, text=label, fg=self.UI_MUTED, bg=self.UI_PANEL,
                     font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=8, pady=(4, 0))
            value = tk.Label(card, text="-", fg=COLOR_TEXT, bg=self.UI_PANEL,
                             font=("Consolas", 9, "bold"), anchor="w")
            value.pack(fill=tk.X, padx=8, pady=(1, 5))
            self._metric_values[label] = value

        # Tab bar
        tab_bar = tk.Frame(self.win, bg="#0c1014", height=36)
        tab_bar.pack(fill=tk.X)
        tab_bar.pack_propagate(False)
        self._tab_btns: dict[str, tk.Button] = {}
        for key, label, _ in self._TABS:
            btn = button(tab_bar, label, lambda k=key: self._select_tab(k), muted=True, padx=18, pady=6)
            btn.pack(side=tk.LEFT)
            self._tab_btns[key] = btn
        self._style_tabs()

        self._planner_controls = tk.Frame(self.win, bg=self.UI_PANEL)
        tk.Label(self._planner_controls, text="ADD BLUEPRINT", bg=self.UI_PANEL,
                 fg=self.UI_DIM, font=("Consolas", 8, "bold")).grid(row=0, column=0, padx=(12, 5), pady=(6, 2))
        self._blueprint_var = tk.StringVar(value=next(iter(BLUEPRINTS)))
        self._blueprint_combo = ttk.Combobox(
            self._planner_controls, textvariable=self._blueprint_var,
            values=sorted(BLUEPRINTS), state="readonly", width=31,
        )
        self._blueprint_combo.grid(row=0, column=1, sticky="ew", padx=4, pady=(6, 2))
        self._blueprint_combo.bind("<<ComboboxSelected>>", lambda _event: self._redraw())
        tk.Label(self._planner_controls, text="FROM", bg=self.UI_PANEL,
                 fg=self.UI_DIM, font=("Consolas", 8, "bold")).grid(row=0, column=2, padx=(6, 3), pady=(6, 2))
        self._current_grade_var = tk.StringVar(value="0")
        ttk.Combobox(self._planner_controls, textvariable=self._current_grade_var,
                     values=("0", "1", "2", "3", "4"), state="readonly", width=3).grid(row=0, column=3, pady=(6, 2))
        tk.Label(self._planner_controls, text="TO", bg=self.UI_PANEL,
                 fg=self.UI_DIM, font=("Consolas", 8, "bold")).grid(row=0, column=4, padx=(6, 3), pady=(6, 2))
        self._grade_var = tk.StringVar(value="5")
        ttk.Combobox(self._planner_controls, textvariable=self._grade_var,
                     values=("1", "2", "3", "4", "5"), state="readonly", width=3).grid(row=0, column=5, pady=(6, 2))
        tk.Label(self._planner_controls, text="QTY", bg=self.UI_PANEL,
                 fg=self.UI_DIM, font=("Consolas", 8, "bold")).grid(row=0, column=6, padx=(6, 3), pady=(6, 2))
        self._quantity_var = tk.StringVar(value="1")
        tk.Spinbox(self._planner_controls, from_=1, to=99, textvariable=self._quantity_var,
                   width=3, bg=self.UI_BG, fg=COLOR_TEXT, insertbackground=COLOR_ACCENT,
                   buttonbackground=self.UI_PANEL_2, relief=tk.FLAT).grid(row=0, column=7, padx=(0, 10), pady=(6, 2))
        self._planner_controls.grid_columnconfigure(1, weight=1)
        button(self._planner_controls, "ADD GOAL", self._pin_blueprint,
               padx=10, pady=4).grid(row=1, column=0, padx=(12, 4), pady=(2, 6), sticky="w")
        button(self._planner_controls, "REMOVE SELECTED", self._unpin_selected,
               muted=True, padx=10, pady=4).grid(row=1, column=1, padx=2, pady=(2, 6), sticky="w")
        self._trader_btn = button(self._planner_controls, "FIND TRADERS", self._find_traders,
                                  muted=True, padx=10, pady=4)
        self._trader_btn.grid(row=1, column=6, columnspan=2, padx=(4, 10), pady=(2, 6), sticky="e")

        self._odyssey_goal_controls = tk.Frame(self.win, bg=self.UI_PANEL)
        tk.Label(
            self._odyssey_goal_controls, text="ODYSSEY MODIFICATION GOAL",
            bg=self.UI_PANEL, fg=self.UI_DIM, font=("Consolas", 8, "bold"),
        ).pack(side=tk.LEFT, padx=(12, 5), pady=7)
        self._odyssey_goal_var = tk.StringVar(value=next(iter(ODYSSEY_BLUEPRINTS)))
        self._odyssey_goal_combo = ttk.Combobox(
            self._odyssey_goal_controls, textvariable=self._odyssey_goal_var,
            values=sorted(ODYSSEY_BLUEPRINTS), state="readonly", width=31,
        )
        self._odyssey_goal_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), pady=6)
        tk.Label(
            self._odyssey_goal_controls, text="QTY", bg=self.UI_PANEL,
            fg=self.UI_DIM, font=("Consolas", 8, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 3))
        self._odyssey_quantity_var = tk.StringVar(value="1")
        tk.Spinbox(
            self._odyssey_goal_controls, from_=1, to=99,
            textvariable=self._odyssey_quantity_var, width=3,
            bg=self.UI_BG, fg=COLOR_TEXT, insertbackground=COLOR_ACCENT,
            buttonbackground=self.UI_PANEL_2, relief=tk.FLAT,
        ).pack(side=tk.LEFT, padx=(0, 8), pady=6)
        button(
            self._odyssey_goal_controls, "ADD GOAL", self._add_odyssey_goal,
            padx=9, pady=4,
        ).pack(side=tk.LEFT, padx=(0, 4), pady=5)
        button(
            self._odyssey_goal_controls, "REMOVE SELECTED", self._remove_odyssey_goal,
            muted=True, padx=9, pady=4,
        ).pack(side=tk.LEFT, padx=(0, 10), pady=5)

        self._filter_controls = tk.Frame(self.win, bg=self.UI_PANEL)
        tk.Label(self._filter_controls, text="SEARCH", bg=self.UI_PANEL, fg=self.UI_DIM,
                 font=("Consolas", 8, "bold")).pack(side=tk.LEFT, padx=(12, 5), pady=7)
        self._search_var = tk.StringVar()
        search_entry = tk.Entry(self._filter_controls, textvariable=self._search_var,
                                bg=self.UI_BG, fg=COLOR_TEXT, insertbackground=COLOR_ACCENT,
                                relief=tk.FLAT, font=("Segoe UI", 9))
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), pady=6, ipady=3)
        self._search_var.trace_add("write", lambda *_args: self._on_search_changed())
        self._category_label = tk.Label(
            self._filter_controls, text="TYPE", bg=self.UI_PANEL, fg=self.UI_DIM,
            font=("Consolas", 8, "bold"),
        )
        self._category_label.pack(side=tk.LEFT, padx=(0, 5))
        self._category_var = tk.StringVar(value="All types")
        self._category_combo = ttk.Combobox(
            self._filter_controls, textvariable=self._category_var,
            values=("All types", "Raw", "Manufactured", "Encoded"),
            state="readonly", width=13,
        )
        self._category_combo.pack(side=tk.LEFT, padx=(0, 10), pady=6)
        self._category_combo.bind("<<ComboboxSelected>>", lambda _event: self._redraw())
        tk.Label(self._filter_controls, text="VIEW", bg=self.UI_PANEL, fg=self.UI_DIM,
                 font=("Consolas", 8, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        self._view_var = tk.StringVar(value="All materials")
        self._view_combo = ttk.Combobox(self._filter_controls, textvariable=self._view_var,
                                        values=("All materials", "Wishlist only", "Missing only", "Held only", "Near capacity"),
                                        state="readonly", width=15)
        self._view_combo.pack(side=tk.LEFT, padx=(0, 12), pady=6)
        self._view_combo.bind("<<ComboboxSelected>>", lambda _event: self._redraw())

        # Reusable native table. The old canvas rebuilt several widgets per
        # material on every tab click, making page switches visibly stall.
        body = tk.Frame(self.win, bg=self.UI_BG)
        self._body = body
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 0))

        columns = ("grade", "material", "stock", "capacity")
        self._material_tree = ttk.Treeview(
            body,
            columns=columns,
            show="headings",
            style="Engineer.Treeview",
            selectmode="browse",
        )
        headings = {
            "grade": ("GRADE", 55, tk.CENTER, False),
            "material": ("MATERIAL", 220, tk.W, True),
            "stock": ("COUNT / CAP", 100, tk.E, False),
            "capacity": ("CAPACITY", 150, tk.W, False),
        }
        for column, (label, width, anchor, stretch) in headings.items():
            self._material_tree.heading(column, text=label)
            self._material_tree.column(
                column,
                width=width,
                minwidth=55,
                anchor=anchor,
                stretch=stretch,
            )
        self._material_tree.tag_configure("grade_header", foreground=self.UI_DIM)
        self._material_tree.tag_configure("near_cap", foreground="#e05050")
        self._material_tree.tag_configure("mid_cap", foreground=COLOR_ACCENT)
        self._material_tree.tag_configure("low_cap", foreground=COLOR_TEXT)
        self._material_tree.tag_configure("empty", foreground=self.UI_MUTED)

        self._page_scroll = scrollbar(body, orient=tk.VERTICAL, command=self._material_tree.yview)
        self._page_xscroll = scrollbar(body, orient=tk.HORIZONTAL, command=self._material_tree.xview)
        self._material_tree.configure(
            yscrollcommand=self._page_scroll.set,
            xscrollcommand=self._page_xscroll.set,
        )
        self._material_tree.bind("<<TreeviewSelect>>", self._selection_changed)
        self._page_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._page_xscroll.pack(side=tk.BOTTOM, fill=tk.X)
        self._material_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Card-based engineer roster (ENGINEERS tab). Kept as a separate scrollable
        # surface rather than shoehorned into the treeview, since progress bars and
        # grouped blueprint lists can't render as native tree rows. Uses the same
        # canvas+inner-frame+destroy-and-rebuild pattern as colonization_window.py's
        # site list, which already proves this scales fine at this row count.
        self._engineer_canvas = tk.Canvas(body, bg=self.UI_BG, highlightthickness=0)
        self._engineer_scroll = scrollbar(body, orient=tk.VERTICAL, command=self._engineer_canvas.yview)
        self._engineer_canvas.configure(yscrollcommand=self._engineer_scroll.set)
        self._engineer_list = tk.Frame(self._engineer_canvas, bg=self.UI_BG)
        self._engineer_window_id = self._engineer_canvas.create_window((0, 0), window=self._engineer_list, anchor="nw")
        self._engineer_list.bind(
            "<Configure>",
            lambda _e: self._engineer_canvas.configure(scrollregion=self._engineer_canvas.bbox("all")),
        )
        self._engineer_canvas.bind(
            "<Configure>",
            lambda e: self._engineer_canvas.itemconfig(self._engineer_window_id, width=e.width),
        )
        self._engineer_canvas.bind(
            "<MouseWheel>",
            lambda e: self._engineer_canvas.yview_scroll(-1 * (e.delta // 120), "units"),
        )

        # Footer
        foot = tk.Frame(self.win, bg="#0c1014", height=32)
        foot.pack(fill=tk.X, pady=(4, 0))
        foot.pack_propagate(False)
        self._total_lbl = tk.Label(foot, text="",
                                    fg=self.UI_MUTED, bg="#0c1014",
                                    font=("Consolas", 9))
        self._total_lbl.pack(side=tk.LEFT, padx=14)
        self._type_lbl = tk.Label(foot, text="",
                                   fg=self.UI_DIM, bg="#0c1014",
                                   font=("Consolas", 9))
        self._type_lbl.pack(side=tk.RIGHT, padx=14)

    def _select_tab(self, category: str):
        self._active_tab = category
        self._style_tabs()
        if category == "engineers":
            self._material_tree.pack_forget()
            self._page_scroll.pack_forget()
            self._page_xscroll.pack_forget()
            self._engineer_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._engineer_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        else:
            self._engineer_canvas.pack_forget()
            self._engineer_scroll.pack_forget()
            self._material_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._page_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            self._page_xscroll.pack(side=tk.BOTTOM, fill=tk.X)
        if category == "wishlist":
            self._filter_controls.pack_forget()
            self._odyssey_goal_controls.pack_forget()
            if not self._planner_controls.winfo_manager():
                self._planner_controls.pack(fill=tk.X, before=self._body)
        elif category in ("inventory", "engineers", "odyssey"):
            self._planner_controls.pack_forget()
            self._configure_filters(category)
            if category == "odyssey":
                if not self._odyssey_goal_controls.winfo_manager():
                    self._odyssey_goal_controls.pack(fill=tk.X, before=self._body)
            else:
                self._odyssey_goal_controls.pack_forget()
            if not self._filter_controls.winfo_manager():
                self._filter_controls.pack(fill=tk.X, before=self._body)
        else:
            self._planner_controls.pack_forget()
            self._filter_controls.pack_forget()
            self._odyssey_goal_controls.pack_forget()
        self._redraw()

    def _configure_filters(self, category: str):
        if category == "inventory":
            categories = ("All types", "Raw", "Manufactured", "Encoded")
            views = ("All materials", "Wishlist only", "Missing only", "Held only", "Near capacity")
            default_view = "All materials"
        elif category == "engineers":
            categories = ("All engineers", "Horizons", "Odyssey")
            views = ("Any access", "Unlocked", "Invited / Known", "Locked / Unsynced")
            default_view = "Any access"
        else:
            categories = ("All locker", "Items", "Components", "Data", "Consumables")
            views = ("All locker items", "Notable only", "Held only")
            default_view = "All locker items"
        if self._category_var.get() not in categories:
            self._category_var.set(categories[0])
        if self._view_var.get() not in views:
            self._view_var.set(default_view)
        self._category_combo.config(values=categories, state="readonly")
        self._view_combo.config(values=views, state="readonly")

    def _style_tabs(self):
        tab_colors = {key: col for key, _, col in self._TABS}
        for key, btn in self._tab_btns.items():
            if key == self._active_tab:
                btn.config(bg=self.UI_PANEL, fg=tab_colors[key])
                btn._theme_resting_bg = self.UI_PANEL
                btn._theme_resting_fg = tab_colors[key]
            else:
                btn.config(bg="#0c1014", fg=self.UI_DIM)
                btn._theme_resting_bg = "#0c1014"
                btn._theme_resting_fg = self.UI_DIM

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _redraw(self):
        rows = self._material_tree.get_children()
        if rows:
            self._material_tree.delete(*rows)
        self._row_meta = {}

        if self._active_tab == "command":
            self._redraw_overview()
        elif self._active_tab == "inventory":
            self._redraw_inventory()
        elif self._active_tab == "engineers":
            self._redraw_engineer_cards()
        elif self._active_tab == "wishlist":
            self._redraw_planner()
        else:
            self._redraw_odyssey()
        self._update_metrics()
        self._update_sync_label()
        self._selection_changed()

    def _configure_columns(self, headings):
        for column, (label, width, anchor, stretch) in headings.items():
            self._material_tree.heading(column, text=label)
            self._material_tree.column(column, width=width, minwidth=50,
                                       anchor=anchor, stretch=stretch)

    def _search_text(self):
        return self._search_var.get().strip().casefold()

    def _on_search_changed(self):
        # The ENGINEERS tab rebuilds a widget tree per card, which is too heavy
        # to redo on every keystroke — debounce so typing doesn't stall the UI.
        if self._search_job is not None:
            try:
                self.win.after_cancel(self._search_job)
            except Exception:
                pass
        self._search_job = self.win.after(150, self._run_search_redraw)

    def _run_search_redraw(self):
        self._search_job = None
        self._redraw()

    def _update_metrics(self):
        plans = pinned_plans(self.materials)
        ready = sum(1 for row in plans if row["craftable"])
        records = self.materials.get("engineers") or {}
        unlocked = sum(1 for row in records.values() if row.get("progress") == "Unlocked")
        shopping = wishlist_plan(self.materials)
        odyssey = odyssey_wishlist_plan(self.materials)
        missing_types = sum(1 for row in shopping["materials"] if row["deficit"])
        odyssey_ready = int(bool(odyssey["goals"]) and odyssey["complete"])
        total_goals = len(plans) + len(odyssey["goals"])
        total_missing = shopping["missing_units"] + odyssey["missing_units"]
        self._metric_values["WISHLIST"].config(text=f"{total_goals} goal{'s' if total_goals != 1 else ''}")
        self._metric_values["READY"].config(text=f"{ready + odyssey_ready} ready")
        self._metric_values["TO COLLECT"].config(text=f"{total_missing:,} · {missing_types + sum(1 for row in odyssey['materials'] if row['deficit'])} types")
        self._metric_values["ENGINEERS"].config(text=f"{unlocked} / {len(ENGINEERS)} unlocked")

    def _redraw_overview(self):
        self._configure_columns({
            "grade": ("PRIORITY", 100, tk.CENTER, False),
            "material": ("ENGINEERING OBJECTIVE", 245, tk.W, True),
            "stock": ("STATUS", 140, tk.E, False),
            "capacity": ("NEXT ACTION", 340, tk.W, True),
        })
        plans = pinned_plans(self.materials)
        shopping = wishlist_plan(self.materials)
        odyssey = odyssey_wishlist_plan(self.materials)
        ready = sum(1 for row in plans if row["craftable"])
        records = self.materials.get("engineers") or {}
        unlocked = sum(1 for row in records.values() if row.get("progress") == "Unlocked")
        relevance = material_relevance(self.materials)
        held_types = sum(1 for row in relevance.values() if row["have"])
        near_cap = sum(1 for row in relevance.values() if row["status"] == "NEAR CAP")
        raw_counts = {
            symbol: int(item.get("count", 0) if isinstance(item, dict) else item)
            for symbol, item in (self.materials.get("raw") or {}).items()
        }
        synth = fsd_injections(raw_counts)
        status_rows = [
            ("GOALS", "Shared engineering wishlist", f"{ready} ready / {len(plans)} goals",
             "Open Wishlist to add, change or remove upgrade goals"),
            ("COLLECT", "Outstanding shopping list", f"{shopping['missing_units']:,} units",
             "Highest-grade shortages are prioritised below" if shopping["missing_units"] else "All wishlist ingredients are held"),
            ("INVENTORY", "Journal-backed material stores", f"{held_types} held types",
             f"{near_cap} near capacity · Inventory marks useful, spare and missing stock"),
            ("ACCESS", "Engineer network", f"{unlocked} / {len(ENGINEERS)} unlocked",
             "Filter Horizons or Odyssey engineers and route directly to their system"),
            ("ODYSSEY", "Suit and weapon modification goals",
             f"{len(odyssey['goals'])} goals · {odyssey['missing_units']:,} missing",
             "Open Odyssey to add modifications and inspect locker relevance"),
            ("SYNTHESIS", "FSD injection reserves",
             f"B {synth['basic']} · S {synth['standard']} · P {synth['premium']}",
             "Basic +25% · Standard +50% · Premium +100%"),
        ]
        if self.materials.get("_load_warning"):
            status_rows.insert(0, ("STORAGE", "Engineering data recovered empty", "ATTENTION",
                                   self.materials.get("_load_warning")))
        for area, title, state, action in status_rows:
            self._material_tree.insert("", tk.END, values=(area, title, state, action),
                                       tags=("near_cap" if "ATTENTION" in state else "mid_cap",))
        missing = collection_priorities(self.materials, limit=8)
        if missing:
            self._material_tree.insert("", tk.END,
                values=("GATHER", "COLLECTION PRIORITIES", f"{len(missing)} shown", "Highest grade first · shared across every goal"),
                tags=("grade_header",))
            for row in missing:
                self._material_tree.insert("", tk.END,
                    values=(f"G{row['grade']}" if row.get("grade") else "—", f"  {row['name']}",
                            f"{row['have']} / {row['need']}", f"Need {row['deficit']} · {row['source']}"),
                    tags=("near_cap",))
        elif plans:
            self._material_tree.insert("", tk.END, values=("READY", "Combined shopping list complete", "ALL HELD", "Visit the appropriate engineer"), tags=("mid_cap",))
        else:
            self._material_tree.insert("", tk.END, values=("WISHLIST", "No engineering goal added", "STANDING BY", "Open Wishlist and add a blueprint target"), tags=("empty",))
        self._total_lbl.config(text=f"Command: {len(plans) + len(odyssey['goals'])} goals · {shopping['missing_units'] + odyssey['missing_units']:,} units outstanding")
        self._type_lbl.config(text="Live journal inventory · profile-aware local planning")

    def _redraw_inventory(self):
        self._configure_columns({
            "grade": ("STATE", 95, tk.CENTER, False),
            "material": ("MATERIAL", 230, tk.W, True),
            "stock": ("HAVE / NEED", 115, tk.E, False),
            "capacity": ("COLLECTION / TRADE GUIDANCE", 355, tk.W, True),
        })
        search = self._search_text()
        category_filter = self._category_var.get().casefold()
        view = self._view_var.get()
        rows = []
        for row in material_relevance(self.materials).values():
            category = row.get("category", "")
            if category_filter != "all types" and category != category_filter:
                continue
            if search and search not in f"{row['name']} {row['symbol']} {category} {row['family']} g{row.get('grade')}".casefold():
                continue
            if view == "Wishlist only" and not row["need"]:
                continue
            if view == "Missing only" and not row["deficit"]:
                continue
            if view == "Held only" and not row["have"]:
                continue
            if view == "Near capacity" and row["status"] != "NEAR CAP":
                continue
            rows.append(row)

        rows.sort(key=lambda row: (
            {"MISSING": 0, "READY": 1, "NEAR CAP": 2, "SPARE": 3, "UNHELD": 4}.get(row["status"], 5),
            row.get("category", ""), -(row.get("grade") or 0), row["name"],
        ))
        if not rows:
            self._material_tree.insert(
                "", tk.END,
                values=("", "No materials match this view", "", "Change the type, view or search filter"),
                tags=("empty",),
            )
        for row in rows:
            grade = f"G{row['grade']}" if row.get("grade") else "—"
            status = f"{row['status']} · {grade}"
            if row["need"]:
                stock = f"{row['have']:,} / {row['need']:,}"
            elif row["cap"]:
                stock = f"{row['have']:,} / {row['cap']:,}"
            else:
                stock = f"{row['have']:,}"
            if row["deficit"]:
                detail = f"Collect {row['deficit']:,} · {row['source']}"
                tag = "near_cap"
            elif row["need"]:
                detail = "Wishlist requirement held · protect this stock from trades"
                tag = "mid_cap"
            elif row["status"] == "NEAR CAP":
                detail = f"{row['fill'] * 100:.0f}% full · safe trader stock unless a future goal needs it"
                tag = "near_cap"
            else:
                detail = row["source"]
                tag = "low_cap" if row["have"] else "empty"
            self._material_tree.insert(
                "", tk.END,
                values=(status, row["name"], stock, detail),
                tags=(tag,),
            )

        held = sum(1 for row in material_relevance(self.materials).values() if row["have"])
        missing = sum(1 for row in material_relevance(self.materials).values() if row["deficit"])
        self._total_lbl.config(text=f"Inventory: {held} held types · {missing} wishlist shortages")
        self._type_lbl.config(text=f"{len(rows)} shown · journal-backed ship material storage")

    def _redraw_engineer_cards(self):
        for widget in self._engineer_list.winfo_children():
            widget.destroy()
        self._engineer_cards = {}
        records = self.materials.get("engineers") or {}
        search = self._search_text()
        division = self._category_var.get()
        access_filter = self._view_var.get()
        order = {"Unlocked": 0, "Invited": 1, "Known": 2, "Locked": 3, "Not synced": 4}
        merged = {
            name: records.get(name) or {"progress": "Not synced", "rank": None}
            for name in ENGINEERS
        }
        merged.update({name: rec for name, rec in records.items() if name not in merged})
        rows = sorted(merged.items(), key=lambda pair: (
            order.get(pair[1].get("progress") or "Not synced", 4), -int(pair[1].get("rank") or 0), pair[0]
        ))
        displayed = 0
        for name, rec in rows:
            info = engineer_info(name)
            if division == "Horizons" and info["odyssey"]:
                continue
            if division == "Odyssey" and not info["odyssey"]:
                continue
            progress = rec.get("progress") or "Not synced"
            if search and search not in f"{name} {info['system']} {info['offers']} {progress}".casefold():
                continue
            if access_filter == "Unlocked" and progress != "Unlocked":
                continue
            if access_filter == "Invited / Known" and progress not in ("Invited", "Known"):
                continue
            if access_filter == "Locked / Unsynced" and progress not in ("Locked", "Not synced"):
                continue
            self._build_engineer_card(self._engineer_list, name, info, rec, progress)
            displayed += 1
        if not displayed:
            tk.Label(self._engineer_list, text="No engineers match the search",
                     fg=self.UI_MUTED, bg=self.UI_BG, font=("Consolas", 9)).pack(pady=20)
        unlocked = sum(1 for rec in records.values() if rec.get("progress") == "Unlocked")
        self._total_lbl.config(text=f"Unlocked: {unlocked} / {len(ENGINEERS)} known engineers")
        self._type_lbl.config(text=f"{len(records)} synced from EngineerProgress · {displayed} shown · click a card to route")

    def _build_engineer_card(self, parent, name, info, rec, progress):
        rank = int(rec.get("rank") or 0)
        rank_progress = rec.get("rank_progress")
        state_color = (
            self.UI_OK if progress == "Unlocked"
            else COLOR_ORANGE if progress in ("Invited", "Known")
            else self.UI_DIM
        )
        # Plain bordered frame rather than the decorative panel() shell (extra
        # corner-bracket frames) — this tab rebuilds many cards per redraw, and
        # the decoration cost adds up across dozens of list rows.
        border = COLOR_ACCENT if self._selected_engineer == name else self.UI_BORDER
        card = tk.Frame(parent, bg=self.UI_PANEL, highlightbackground=border, highlightthickness=1)
        card.pack(fill=tk.X, padx=6, pady=4)
        self._engineer_cards[name] = card

        body = tk.Frame(card, bg=self.UI_PANEL)
        body.pack(fill=tk.X, padx=10, pady=(8, 8))

        header = tk.Frame(body, bg=self.UI_PANEL)
        header.pack(fill=tk.X)
        tk.Label(header, text=name, font=("Segoe UI", 10, "bold"), fg=state_color,
                 bg=self.UI_PANEL, anchor="w").pack(side=tk.LEFT)
        tk.Label(header, text="ODYSSEY" if info["odyssey"] else "HORIZONS",
                 font=("Consolas", 7, "bold"), fg=self.UI_MUTED, bg=self.UI_PANEL
                 ).pack(side=tk.LEFT, padx=(8, 0))
        badge_text = f"G{rank} / 5" if progress == "Unlocked" and rank else progress.upper()
        tk.Label(header, text=badge_text, font=("Consolas", 8, "bold"), fg=state_color,
                 bg=self.UI_PANEL).pack(side=tk.RIGHT)

        sub_text = " · ".join(value for value in (info["system"], info["offers"]) if value)
        tk.Label(body, text=sub_text, font=("Consolas", 8), fg=self.UI_MUTED, bg=self.UI_PANEL,
                 anchor="w").pack(fill=tk.X, pady=(1, 6))

        bar = tk.Frame(body, bg=self.UI_PANEL)
        bar.pack(fill=tk.X, pady=(0, 6))
        for grade in range(1, 6):
            trough = tk.Frame(bar, bg=self.UI_PANEL_2, height=6)
            trough.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0 if grade == 1 else 2, 0))
            trough.pack_propagate(False)
            if progress == "Unlocked" and rank >= grade:
                tk.Frame(trough, bg=COLOR_ACCENT).place(x=0, y=0, relwidth=1.0, relheight=1.0)
            elif progress == "Unlocked" and rank == grade - 1 and rank_progress:
                fill = max(0.0, min(1.0, float(rank_progress) / 100))
                tk.Frame(trough, bg=COLOR_ACCENT).place(x=0, y=0, relwidth=fill, relheight=1.0)

        if progress in ("Locked", "Not synced") and info.get("unlock"):
            tk.Label(body, text=info["unlock"], font=("Consolas", 8), fg=self.UI_MUTED,
                     bg=self.UI_PANEL, anchor="w", justify=tk.LEFT, wraplength=560
                     ).pack(fill=tk.X, pady=(0, 4))

        groups = engineer_blueprints(name)
        if groups:
            tk.Label(body, text=self._summarize_blueprint_groups(groups), font=("Consolas", 8),
                     fg=COLOR_TEXT, bg=self.UI_PANEL, anchor="w", justify=tk.LEFT, wraplength=560
                     ).pack(fill=tk.X)

        self._bind_recursive(card, lambda _event, n=name, i=info: self._select_engineer_card(n, i))
        return card

    @staticmethod
    def _summarize_blueprint_groups(groups: dict, max_chars: int = 220) -> str:
        parts = []
        for slot, names in groups.items():
            label = slot.rsplit(" - ", 1)[-1]
            parts.append(f"{label}: " + ", ".join(names))
        text = "  ·  ".join(parts)
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rsplit(" ", 1)[0] + " …"

    def _bind_recursive(self, widget, handler):
        widget.bind("<Button-1>", handler)
        try:
            widget.config(cursor="hand2")
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._bind_recursive(child, handler)

    def _select_engineer_card(self, name, info):
        previous = self._selected_engineer
        self._selected_engineer = name
        # Selection only changes a border color — recolor the (at most two)
        # affected cards in place instead of rebuilding the whole list.
        for target, border in ((previous, self.UI_BORDER), (name, COLOR_ACCENT)):
            card = self._engineer_cards.get(target)
            if card is not None and card.winfo_exists():
                card.config(highlightbackground=border)
        self._selection_changed()

    def _redraw_planner(self):
        self._configure_columns({
            "grade": ("TARGET", 90, tk.CENTER, False),
            "material": ("BLUEPRINT / MATERIAL", 235, tk.W, True),
            "stock": ("HAVE / NEED", 110, tk.E, False),
            "capacity": ("READINESS / COLLECTION OPTION", 350, tk.W, True),
        })
        raw_counts = {
            symbol: int(item.get("count", 0) if isinstance(item, dict) else item)
            for symbol, item in (self.materials.get("raw") or {}).items()
        }
        synth = fsd_injections(raw_counts)
        self._material_tree.insert(
            "", tk.END,
            values=("FSD", "Jumponium synthesis readiness",
                    f"B {synth['basic']} · S {synth['standard']} · P {synth['premium']}",
                    "Basic +25% · Standard +50% · Premium +100%"),
            tags=("mid_cap" if any(synth.values()) else "grade_header",),
        )
        plans = pinned_plans(self.materials)
        shopping = wishlist_plan(self.materials)
        relevance = material_relevance(self.materials)
        if not plans:
            self._material_tree.insert("", tk.END, values=("", "No wishlist goals yet", "", "Choose a blueprint and target grade above, then ADD GOAL"), tags=("empty",))
        for plan_row in plans:
            total = sum(row["need"] for row in plan_row["materials"])
            have = sum(min(row["have"], row["need"]) for row in plan_row["materials"])
            pct = round(have / total * 100) if total else 100
            current = plan_row.get("current_grade", 0)
            quantity = plan_row.get("quantity", 1)
            status = "READY TO ENGINEER" if plan_row["craftable"] else f"{pct}% collected"
            goal = f"G{current} → G{plan_row['grade']}"
            if quantity > 1:
                goal += f" · {quantity} modules"
            iid = self._material_tree.insert("", tk.END,
                values=(goal, plan_row["blueprint"], f"{have} / {total}", status),
                tags=("mid_cap" if plan_row["craftable"] else "grade_header",))
            self._row_meta[iid] = {"blueprint": plan_row["blueprint"]}
            for row in plan_row["materials"]:
                if row["deficit"]:
                    detail = f"Need {row['deficit']} more"
                    if row.get("trade"):
                        trade = row["trade"]
                        detail += f" · trade {trade['spend']}× {trade['from']} for {trade['covers']}"
                    else:
                        detail += f" · {relevance.get(row['symbol'], {}).get('source', '')}"
                    tag = "near_cap"
                else:
                    detail, tag = "Complete", "mid_cap"
                self._material_tree.insert("", tk.END,
                    values=(f"G{row['grade']}", f"  {row['name']}", f"{row['have']} / {row['need']}", detail),
                    tags=(tag,))
        if plans:
            self._material_tree.insert("", tk.END,
                values=("SHOPPING", "SHARED NON-DOUBLED SHOPPING LIST",
                        f"{shopping['required_units'] - shopping['missing_units']} / {shopping['required_units']}",
                        f"{shopping['missing_units']} units missing" if shopping['missing_units'] else "All required units held"),
                tags=("grade_header",))
            for row in shopping["materials"]:
                if not row["deficit"]:
                    continue
                self._material_tree.insert("", tk.END,
                    values=(f"G{row['grade']}" if row.get("grade") else "—", f"  {row['name']}",
                            f"{row['have']} / {row['need']}",
                            f"Need {row['deficit']} · {relevance.get(row['symbol'], {}).get('source', '')}"),
                    tags=("near_cap",))
        if self._trader_results or self._trader_searching:
            state = "Search in progress" if self._trader_searching else "Select a result, then ROUTE SELECTED"
            self._material_tree.insert("", tk.END, values=("TRADERS", "NEAREST MATERIAL TRADERS", "SPANSH", state), tags=("grade_header",))
            for kind, trader in self._trader_results:
                if trader:
                    detail = f"{trader.get('distance', 0):,.1f} ly · {trader.get('dist_ls') or '?'} ls"
                    if trader.get("large_pad"):
                        detail += " · L pad"
                    iid = self._material_tree.insert("", tk.END,
                        values=(kind.upper(), trader.get("station"), trader.get("system"), detail), tags=("mid_cap",))
                    self._row_meta[iid] = {"system": trader.get("system")}
                else:
                    self._material_tree.insert("", tk.END, values=(kind.upper(), "No trader found", "", ""), tags=("empty",))
        self._total_lbl.config(text=f"Wishlist: {len(plans)} goals · Missing: {shopping['missing_units']:,} units")
        selected = self._blueprint_var.get()
        info = BLUEPRINT_INFO.get(selected, {})
        self._type_lbl.config(text=info.get("what", "Verified high-use ship recipe set"))

    def _redraw_odyssey(self):
        self._configure_columns({
            "grade": ("TYPE", 100, tk.CENTER, False),
            "material": ("LOCKER ITEM", 280, tk.W, True),
            "stock": ("COUNT", 90, tk.E, False),
            "capacity": ("RELEVANCE / USE", 330, tk.W, True),
        })
        locker = self.materials.get("ship_locker") or {}
        search = self._search_text()
        group_filter = self._category_var.get().casefold()
        view = self._view_var.get()
        plan = odyssey_wishlist_plan(self.materials)
        locker_counts = odyssey_inventory_counts(self.materials)
        total = 0
        displayed = 0
        notable_count = 0
        if plan["goals"]:
            self._material_tree.insert(
                "", tk.END,
                values=("GOALS", "SUIT & WEAPON MODIFICATION WISHLIST",
                        f"{plan['required_units'] - plan['missing_units']} / {plan['required_units']}",
                        "READY" if plan["complete"] else f"{plan['missing_units']} units still required"),
                tags=("mid_cap" if plan["complete"] else "grade_header",),
            )
            for goal in plan["goals"]:
                recipe = ODYSSEY_BLUEPRINTS[goal["name"]]
                required = {
                    "".join(ch for ch in name.casefold() if ch.isalnum()): amount * goal["quantity"]
                    for name, amount in recipe.items()
                }
                need = sum(required.values())
                have = sum(min(int((locker_counts.get(key) or {}).get("count") or 0), amount)
                           for key, amount in required.items())
                iid = self._material_tree.insert(
                    "", tk.END,
                    values=("MOD", goal["name"], f"{have} / {need}",
                            "READY TO APPLY" if have >= need else f"{need - have} ingredient units missing"),
                    tags=("mid_cap" if have >= need else "low_cap",),
                )
                self._row_meta[iid] = {"odyssey_goal": goal["name"]}
            for row in plan["materials"]:
                if not row["deficit"]:
                    continue
                self._material_tree.insert(
                    "", tk.END,
                    values=("NEED", f"  {row['name']}", f"{row['have']} / {row['need']}",
                            f"Collect or obtain {row['deficit']} more from Odyssey settlements/missions"),
                    tags=("near_cap",),
                )
        else:
            self._material_tree.insert(
                "", tk.END,
                values=("GOALS", "No Odyssey modification goals", "", "Choose a modification above, then ADD GOAL"),
                tags=("empty",),
            )
        for group in ("items", "components", "data", "consumables"):
            rows = locker.get(group) or []
            if not rows:
                continue
            if group_filter != "all locker" and group != group_filter:
                continue
            visible = []
            for item in rows:
                if search and search not in f"{item.get('name', '')} {group}".casefold():
                    continue
                count = int(item.get("count") or 0)
                use, notable = odyssey_item_use(item.get("name", ""), group)
                if view == "Notable only" and not notable:
                    continue
                if view == "Held only" and count <= 0:
                    continue
                visible.append((item, count, use, notable))
            if not visible:
                continue
            self._material_tree.insert("", tk.END, values=(group.upper(), f"{group.upper()} · {len(visible)} shown", "", ""), tags=("grade_header",))
            for item, count, use, notable in visible:
                total += count
                displayed += 1
                notable_count += int(notable)
                self._material_tree.insert("", tk.END, values=(group.upper(), item.get("name"), count,
                                          use), tags=("mid_cap" if notable else "low_cap",))
        if not displayed and not plan["goals"]:
            message = "No Odyssey locker data" if not locker else "No locker items match this view"
            self._material_tree.insert("", tk.END, values=("", message, "", "ShipLocker.json syncs automatically"), tags=("empty",))
        self._total_lbl.config(text=f"Odyssey: {len(plan['goals'])} goals · {plan['missing_units']} missing · {total:,} locker units shown")
        self._type_lbl.config(text=f"{displayed} locker types · {notable_count} notable")

    def _pin_blueprint(self):
        name = self._blueprint_var.get()
        if name not in BLUEPRINTS:
            return
        grade = max(1, min(5, int(self._grade_var.get() or 5)))
        current_grade = max(0, min(grade - 1, int(self._current_grade_var.get() or 0)))
        quantity = max(1, min(99, int(self._quantity_var.get() or 1)))
        pins = [pin for pin in (self.materials.get("pinned_blueprints") or []) if pin.get("name") != name]
        pins.append({"name": name, "grade": grade, "current_grade": current_grade,
                     "target_grade": grade, "quantity": quantity})
        self.materials["pinned_blueprints"] = pins
        result = self.save_callback(self.materials)
        if result is False:
            self._total_lbl.config(text=f"Could not save engineering goal: {self.materials.get('_save_error', 'unknown error')}")
            return
        self._redraw()

    def _unpin_selected(self):
        selected = self._material_tree.selection()
        if not selected:
            return
        name = (self._row_meta.get(selected[0]) or {}).get("blueprint")
        if not name:
            return
        self.materials["pinned_blueprints"] = [
            pin for pin in (self.materials.get("pinned_blueprints") or []) if pin.get("name") != name
        ]
        result = self.save_callback(self.materials)
        if result is False:
            self._total_lbl.config(text=f"Could not save engineering goal: {self.materials.get('_save_error', 'unknown error')}")
            return
        self._redraw()

    def _add_odyssey_goal(self):
        name = self._odyssey_goal_var.get()
        if name not in ODYSSEY_BLUEPRINTS:
            return
        quantity = max(1, min(99, int(self._odyssey_quantity_var.get() or 1)))
        goals = [
            goal for goal in (self.materials.get("odyssey_goals") or [])
            if goal.get("name") != name
        ]
        goals.append({"name": name, "quantity": quantity})
        self.materials["odyssey_goals"] = goals
        result = self.save_callback(self.materials)
        if result is False:
            self._total_lbl.config(text=f"Could not save Odyssey goal: {self.materials.get('_save_error', 'unknown error')}")
            return
        self._redraw()

    def _remove_odyssey_goal(self):
        selected = self._material_tree.selection()
        if not selected:
            return
        name = (self._row_meta.get(selected[0]) or {}).get("odyssey_goal")
        if not name:
            return
        self.materials["odyssey_goals"] = [
            goal for goal in (self.materials.get("odyssey_goals") or [])
            if goal.get("name") != name
        ]
        result = self.save_callback(self.materials)
        if result is False:
            self._total_lbl.config(text=f"Could not save Odyssey goal: {self.materials.get('_save_error', 'unknown error')}")
            return
        self._redraw()

    def _find_traders(self):
        if self._trader_searching:
            return
        system = self.get_current_system() or ""
        coords = self.get_current_coords()
        if not system and not coords:
            self._total_lbl.config(text="No current system available for trader search")
            return
        self._trader_searching = True
        self._trader_results = []
        self._trader_btn.config(state=tk.DISABLED, text="SEARCHING…")
        self._redraw()

        def worker():
            try:
                found = []
                for kind in ("raw", "manufactured", "encoded"):
                    rows = spansh.material_traders(system, kind, size=1, coords=coords)
                    found.append((kind, rows[0] if rows else None))
                self.win.after(0, lambda: self._show_traders(found))
            except Exception as exc:
                message = str(exc)
                self.win.after(0, lambda msg=message: self._trader_failed(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _current_route_system(self):
        if self._active_tab == "engineers":
            return engineer_info(self._selected_engineer)["system"] if self._selected_engineer else None
        selected = self._material_tree.selection()
        return (self._row_meta.get(selected[0]) or {}).get("system") if selected else None

    def _plot_selected(self):
        system = self._current_route_system()
        if not system or not self.plot_system_callback:
            self._total_lbl.config(text="Select an engineer or trader row with a system first")
            return
        self.plot_system_callback(system)

    def _show_traders(self, found):
        if not self.is_open():
            return
        self._trader_searching = False
        self._trader_results = list(found)
        self._trader_btn.config(state=tk.NORMAL, text="REFRESH TRADERS")
        self._redraw()

    def _trader_failed(self, message):
        if not self.is_open():
            return
        self._trader_searching = False
        self._trader_btn.config(state=tk.NORMAL, text="FIND TRADERS")
        self._total_lbl.config(text=f"Trader search failed: {message}")

    def _selection_changed(self, _event=None):
        enabled = bool(self._current_route_system() and self.plot_system_callback)
        self._route_btn.config(state=tk.NORMAL if enabled else tk.DISABLED)

    def _update_footer(self, cat: str, cat_data: dict, displayed=None):
        total  = sum(
            int(v.get("count", 0) if isinstance(v, dict) else v)
            for v in cat_data.values()
        )
        n_mats = sum(1 for v in cat_data.values()
                     if int(v.get("count", 0) if isinstance(v, dict) else v) > 0)
        self._total_lbl.config(text=f"Total held: {total:,}")
        suffix = f" · {displayed} shown" if displayed is not None else ""
        self._type_lbl.config(
            text=f"{n_mats} held material type{'s' if n_mats != 1 else ''}{suffix}")

    def _update_sync_label(self):
        ts = self.materials.get("last_updated")
        if ts:
            try:
                dt_str = datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
                self._sync_lbl.config(text=f"Synced: {dt_str}")
                return
            except Exception:
                pass
        self._sync_lbl.config(text="Not yet synced")
