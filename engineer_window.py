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
    ENGINEERS,
    GRADE_CAP,
    MATERIALS,
    material_info,
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
                "pinned_blueprints": [], "ship_locker": {}, "last_updated": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for cat in ("raw", "manufactured", "encoded"):
            data.setdefault(cat, {})
        data.setdefault("engineers", {})
        data.setdefault("pinned_blueprints", [])
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
                "pinned_blueprints": [], "ship_locker": {}, "last_updated": None,
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
        ("overview",     "OVERVIEW",     "#67e8f9"),
        ("raw",          "RAW",          "#b0d8a0"),
        ("manufactured", "MFG",          "#93c5fd"),
        ("encoded",      "DATA",         "#fde68a"),
        ("engineers",    "ENGINEERS",    "#c4b5fd"),
        ("planner",      "PLANNER",      "#67e8f9"),
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
        self._active_tab   = "overview"
        self._row_meta = {}
        self._refresh_job = None
        self._refresh_pending = False
        self._trader_results = []
        self._trader_searching = False

        self.embedded = embedded
        self.win = window_surface(root, embedded=embedded)
        self.win.title("Engineer Materials — Void Compass")
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
        tk.Label(title_box, text="ENGINEERING WORKSHOP",
                 font=("Segoe UI", 14, "bold"), fg=COLOR_ACCENT, bg="#0c1014"
                 ).pack(anchor="w", pady=(7, 0))
        tk.Label(title_box, text="inventory // engineers // upgrade goals",
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
        for index, label in enumerate(("HELD TYPES", "READY GOALS", "ENGINEERS", "MISSING UNITS")):
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
        tk.Label(self._planner_controls, text="BLUEPRINT", bg=self.UI_PANEL,
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
        button(self._planner_controls, "PIN", self._pin_blueprint,
               padx=10, pady=4).grid(row=1, column=0, padx=(12, 4), pady=(2, 6), sticky="w")
        button(self._planner_controls, "UNPIN", self._unpin_selected,
               muted=True, padx=10, pady=4).grid(row=1, column=1, padx=2, pady=(2, 6), sticky="w")
        self._trader_btn = button(self._planner_controls, "FIND TRADERS", self._find_traders,
                                  muted=True, padx=10, pady=4)
        self._trader_btn.grid(row=1, column=6, columnspan=2, padx=(4, 10), pady=(2, 6), sticky="e")

        self._filter_controls = tk.Frame(self.win, bg=self.UI_PANEL)
        tk.Label(self._filter_controls, text="SEARCH", bg=self.UI_PANEL, fg=self.UI_DIM,
                 font=("Consolas", 8, "bold")).pack(side=tk.LEFT, padx=(12, 5), pady=7)
        self._search_var = tk.StringVar()
        search_entry = tk.Entry(self._filter_controls, textvariable=self._search_var,
                                bg=self.UI_BG, fg=COLOR_TEXT, insertbackground=COLOR_ACCENT,
                                relief=tk.FLAT, font=("Segoe UI", 9))
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), pady=6, ipady=3)
        self._search_var.trace_add("write", lambda *_args: self._redraw())
        tk.Label(self._filter_controls, text="VIEW", bg=self.UI_PANEL, fg=self.UI_DIM,
                 font=("Consolas", 8, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        self._view_var = tk.StringVar(value="Held only")
        self._view_combo = ttk.Combobox(self._filter_controls, textvariable=self._view_var,
                                        values=("Held only", "All materials", "Near capacity"),
                                        state="readonly", width=14)
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

        page_scroll = scrollbar(body, orient=tk.VERTICAL, command=self._material_tree.yview)
        self._material_tree.configure(yscrollcommand=page_scroll.set)
        self._material_tree.bind("<<TreeviewSelect>>", self._selection_changed)
        self._material_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        page_scroll.pack(side=tk.RIGHT, fill=tk.Y)

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
        if category == "planner":
            self._filter_controls.pack_forget()
            if not self._planner_controls.winfo_manager():
                self._planner_controls.pack(fill=tk.X, before=self._body)
        elif category in ("raw", "manufactured", "encoded", "engineers", "odyssey"):
            self._planner_controls.pack_forget()
            if not self._filter_controls.winfo_manager():
                self._filter_controls.pack(fill=tk.X, before=self._body)
            self._view_combo.config(state="readonly" if category in ("raw", "manufactured", "encoded") else tk.DISABLED)
        else:
            self._planner_controls.pack_forget()
            self._filter_controls.pack_forget()
        self._redraw()

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

        if self._active_tab == "overview":
            self._redraw_overview()
        elif self._active_tab in ("raw", "manufactured", "encoded"):
            self._redraw_materials(self._active_tab)
        elif self._active_tab == "engineers":
            self._redraw_engineers()
        elif self._active_tab == "planner":
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

    def _update_metrics(self):
        held_types = sum(
            1 for cat in ("raw", "manufactured", "encoded")
            for item in (self.materials.get(cat) or {}).values()
            if int(item.get("count", 0) if isinstance(item, dict) else item) > 0
        )
        plans = pinned_plans(self.materials)
        ready = sum(1 for row in plans if row["craftable"])
        records = self.materials.get("engineers") or {}
        unlocked = sum(1 for row in records.values() if row.get("progress") == "Unlocked")
        shopping = wishlist_plan(self.materials)
        self._metric_values["HELD TYPES"].config(text=f"{held_types} / {len(MATERIALS)} known")
        self._metric_values["READY GOALS"].config(text=f"{ready} / {len(plans)}")
        self._metric_values["ENGINEERS"].config(text=f"{unlocked} / {len(ENGINEERS)} unlocked")
        self._metric_values["MISSING UNITS"].config(text=f"{shopping['missing_units']:,}")

    def _redraw_overview(self):
        self._configure_columns({
            "grade": ("AREA", 100, tk.CENTER, False),
            "material": ("WORKSHOP STATUS", 240, tk.W, True),
            "stock": ("STATE", 135, tk.E, False),
            "capacity": ("NEXT ACTION", 320, tk.W, True),
        })
        plans = pinned_plans(self.materials)
        shopping = wishlist_plan(self.materials)
        ready = sum(1 for row in plans if row["craftable"])
        records = self.materials.get("engineers") or {}
        unlocked = sum(1 for row in records.values() if row.get("progress") == "Unlocked")
        held_types = sum(
            1 for cat in ("raw", "manufactured", "encoded")
            for item in (self.materials.get(cat) or {}).values()
            if int(item.get("count", 0) if isinstance(item, dict) else item) > 0
        )
        near_cap = 0
        for cat in ("raw", "manufactured", "encoded"):
            for symbol, item in (self.materials.get(cat) or {}).items():
                grade = material_info(symbol).get("grade")
                cap = GRADE_CAP.get(grade)
                count = int(item.get("count", 0) if isinstance(item, dict) else item)
                near_cap += int(bool(cap and count / cap >= 0.85))
        raw_counts = {
            symbol: int(item.get("count", 0) if isinstance(item, dict) else item)
            for symbol, item in (self.materials.get("raw") or {}).items()
        }
        synth = fsd_injections(raw_counts)
        status_rows = [
            ("GOALS", "Pinned engineering goals", f"{ready} ready / {len(plans)} pinned",
             "Open Planner to build or adjust the shared shopping list"),
            ("MATERIALS", "Ship engineering inventory", f"{held_types} held types",
             f"{near_cap} near capacity · filter inventory before gathering more"),
            ("ENGINEERS", "Engineer access network", f"{unlocked} / {len(ENGINEERS)} unlocked",
             "Select an engineer row to hand its system to Route Command"),
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
        missing = [row for row in shopping["materials"] if row["deficit"]]
        if missing:
            self._material_tree.insert("", tk.END,
                values=("SHOPPING", "Highest shared shortages", f"{shopping['missing_units']:,} units", "Across every pinned goal"),
                tags=("grade_header",))
            for row in missing[:8]:
                self._material_tree.insert("", tk.END,
                    values=(f"G{row['grade']}" if row.get("grade") else "—", f"  {row['name']}",
                            f"{row['have']} / {row['need']}", f"Need {row['deficit']} more"),
                    tags=("near_cap",))
        elif plans:
            self._material_tree.insert("", tk.END, values=("READY", "Combined shopping list complete", "ALL HELD", "Visit the appropriate engineer"), tags=("mid_cap",))
        else:
            self._material_tree.insert("", tk.END, values=("PLANNER", "No engineering goal pinned", "STANDING BY", "Choose a verified blueprint in Planner"), tags=("empty",))
        self._total_lbl.config(text=f"Workshop: {len(plans)} goal{'s' if len(plans) != 1 else ''}")
        self._type_lbl.config(text="Live journal inventory · local planning")

    def _redraw_materials(self, cat):
        self._configure_columns({
            "grade": ("GOAL", 105, tk.CENTER, False),
            "material": ("MATERIAL", 235, tk.W, True),
            "stock": ("COUNT / CAP", 105, tk.E, False),
            "capacity": ("CAPACITY", 155, tk.W, False),
        })
        cat_data = self.materials.get(cat, {})
        search = self._search_text()
        view = self._view_var.get()

        items_with_count = []
        known = {key: {"name": value["name"], "count": 0}
                 for key, value in MATERIALS.items() if value.get("category") == cat}
        known.update(cat_data)
        for key, item in known.items():
            count = int(item.get("count", 0) if isinstance(item, dict) else item)
            ref = material_info(key)
            name = (item.get("name") if isinstance(item, dict) else None) or ref["name"]
            grade = ref.get("grade")
            cap = GRADE_CAP.get(grade)
            if search and search not in f"{name} {key} g{grade}".casefold():
                continue
            if view == "Held only" and count <= 0:
                continue
            if view == "Near capacity" and not (cap and count / cap >= 0.85):
                continue
            items_with_count.append((key, item, count))

        if not items_with_count:
            self._material_tree.insert(
                "",
                tk.END,
                values=("", f"No {cat.upper()} materials on record", "", "Log into Elite Dangerous to sync"),
                tags=("empty",),
            )
            self._update_footer(cat, cat_data, 0)
            return

        by_grade: dict[int | None, list] = {}
        for key, item, count in items_with_count:
            g = material_info(key).get("grade")
            by_grade.setdefault(g, []).append((key, item, count, g))

        for grade in sorted(by_grade.keys(), key=lambda value: value if value is not None else 99):
            cap = GRADE_CAP.get(grade)
            rows = sorted(by_grade[grade], key=lambda x: (-(x[2]), (
                x[1].get("name") if isinstance(x[1], dict) else x[0]).lower()))

            self._material_tree.insert(
                "",
                tk.END,
                values=((f"G{grade}" if grade else "—"),
                        (f"GRADE {grade}  —  individual cap {cap:,}" if grade else "SPECIAL MATERIALS"), "", ""),
                tags=("grade_header",),
            )

            for key, item, count, g in rows:
                ref = material_info(key)
                name = (item.get("name") if isinstance(item, dict) else None) or ref["name"]
                fill = min(1.0, count / cap) if cap else 0

                if cap and fill >= 0.85:
                    row_tag = "near_cap"
                elif cap and fill >= 0.50:
                    row_tag = "mid_cap"
                else:
                    row_tag = "low_cap"

                if cap:
                    segments = 10
                    filled = max(0, min(segments, round(fill * segments)))
                    capacity = "█" * filled + "░" * (segments - filled) + f"  {fill * 100:>3.0f}%"
                    stock = f"{count:,} / {cap:,}"
                else:
                    capacity, stock = "Not material-trader stock", f"{count:,}"
                self._material_tree.insert(
                    "",
                    tk.END,
                    values=((f"G{g}" if g else "—"), name, stock, capacity),
                    tags=(row_tag,),
                )

        self._update_footer(cat, cat_data, len(items_with_count))

    def _redraw_engineers(self):
        self._configure_columns({
            "grade": ("STATUS", 90, tk.CENTER, False),
            "material": ("ENGINEER", 190, tk.W, True),
            "stock": ("ACCESS", 90, tk.CENTER, False),
            "capacity": ("SYSTEM · SPECIALTY", 300, tk.W, True),
        })
        records = self.materials.get("engineers") or {}
        search = self._search_text()
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
            system, offers, on_foot = ENGINEERS.get(name, ("", "", False))
            if search and search not in f"{name} {system} {offers} {rec.get('progress', '')}".casefold():
                continue
            progress = rec.get("progress") or "Not synced"
            rank = int(rec.get("rank") or 0)
            access = f"G{rank} / 5" if progress == "Unlocked" and rank else progress.upper()
            label = f"{name}  [ON-FOOT]" if on_foot else name
            iid = self._material_tree.insert("", tk.END, values=(progress.upper(), label, access,
                                             " · ".join(value for value in (system, offers) if value)),
                                             tags=("mid_cap" if progress == "Unlocked" else "low_cap",))
            if system:
                self._row_meta[iid] = {"system": system}
            displayed += 1
        unlocked = sum(1 for rec in records.values() if rec.get("progress") == "Unlocked")
        if not displayed:
            self._material_tree.insert("", tk.END, values=("", "No engineers match the search", "", "Clear the search filter"), tags=("empty",))
        self._total_lbl.config(text=f"Unlocked: {unlocked} / {len(ENGINEERS)} known engineers")
        self._type_lbl.config(text=f"{len(records)} synced from EngineerProgress · {displayed} shown")

    def _redraw_planner(self):
        self._configure_columns({
            "grade": ("GRADE", 55, tk.CENTER, False),
            "material": ("BLUEPRINT / MATERIAL", 235, tk.W, True),
            "stock": ("HAVE / NEED", 110, tk.E, False),
            "capacity": ("SHORTFALL / TRADER OPTION", 330, tk.W, True),
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
        if not plans:
            self._material_tree.insert("", tk.END, values=("", "Nothing pinned yet", "", "Choose a blueprint and grade above, then PIN"), tags=("empty",))
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
                tags=("near_cap" if plan_row["craftable"] else "grade_header",))
            self._row_meta[iid] = {"blueprint": plan_row["blueprint"]}
            for row in plan_row["materials"]:
                if row["deficit"]:
                    detail = f"Need {row['deficit']} more"
                    if row.get("trade"):
                        trade = row["trade"]
                        detail += f" · trade {trade['spend']}× {trade['from']} for {trade['covers']}"
                    tag = "near_cap"
                else:
                    detail, tag = "Complete", "mid_cap"
                self._material_tree.insert("", tk.END,
                    values=(f"G{row['grade']}", f"  {row['name']}", f"{row['have']} / {row['need']}", detail),
                    tags=(tag,))
        if plans:
            self._material_tree.insert("", tk.END,
                values=("SHOPPING", "COMBINED NON-DOUBLED SHOPPING LIST",
                        f"{shopping['required_units'] - shopping['missing_units']} / {shopping['required_units']}",
                        f"{shopping['missing_units']} units missing" if shopping['missing_units'] else "All required units held"),
                tags=("grade_header",))
            for row in shopping["materials"]:
                if not row["deficit"]:
                    continue
                self._material_tree.insert("", tk.END,
                    values=(f"G{row['grade']}" if row.get("grade") else "—", f"  {row['name']}",
                            f"{row['have']} / {row['need']}", f"Need {row['deficit']} more across all goals"),
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
        self._total_lbl.config(text=f"Pinned goals: {len(plans)} · Missing: {shopping['missing_units']:,} units")
        selected = self._blueprint_var.get()
        info = BLUEPRINT_INFO.get(selected, {})
        self._type_lbl.config(text=info.get("what", "Verified high-use ship recipe set"))

    def _redraw_odyssey(self):
        self._configure_columns({
            "grade": ("TYPE", 100, tk.CENTER, False),
            "material": ("LOCKER ITEM", 280, tk.W, True),
            "stock": ("COUNT", 90, tk.E, False),
            "capacity": ("USE", 260, tk.W, True),
        })
        locker = self.materials.get("ship_locker") or {}
        search = self._search_text()
        total = 0
        for group in ("items", "components", "data", "consumables"):
            rows = locker.get(group) or []
            if not rows:
                continue
            self._material_tree.insert("", tk.END, values=(group.upper(), f"{group.upper()} · {len(rows)} types", "", ""), tags=("grade_header",))
            for item in rows:
                if search and search not in f"{item.get('name', '')} {group}".casefold():
                    continue
                count = int(item.get("count") or 0)
                total += count
                self._material_tree.insert("", tk.END, values=(group.upper(), item.get("name"), count,
                                          "Locker inventory · recipe purpose not inferred"), tags=("low_cap",))
        if not total:
            self._material_tree.insert("", tk.END, values=("", "No Odyssey locker data", "", "ShipLocker.json syncs automatically"), tags=("empty",))
        self._total_lbl.config(text=f"Locker total: {total:,}")
        self._type_lbl.config(text="Goods · assets · data · consumables · live inventory only")

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

    def _plot_selected(self):
        selected = self._material_tree.selection()
        system = (self._row_meta.get(selected[0]) or {}).get("system") if selected else None
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
        selected = self._material_tree.selection()
        system = (self._row_meta.get(selected[0]) or {}).get("system") if selected else None
        enabled = bool(system and self.plot_system_callback)
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
