"""
engineer_window.py — Engineer Material Tracker for VoidCompass.

Displays current Raw / Manufactured / Encoded material stock synced live
from the journal (Materials, MaterialCollected, MaterialDiscarded, etc.).
Persisted to engineer_materials.json next to the executable.
"""

import json
import os
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
    material_info,
    pinned_plans,
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
    except Exception:
        return {"raw": {}, "manufactured": {}, "encoded": {}, "engineers": {},
                "pinned_blueprints": [], "ship_locker": {}, "last_updated": None}


def save_engineer_materials(materials: dict, path=None):
    path = path or os.path.join(os.getcwd(), ENGINEER_MATERIALS_FILE)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(materials, f, indent=2)
    except Exception:
        pass


class EngineerWindow(ThemedWindowMixin):

    _TABS = [
        ("raw",          "RAW",          "#b0d8a0"),
        ("manufactured", "MANUFACTURED", "#93c5fd"),
        ("encoded",      "ENCODED",      "#fde68a"),
        ("engineers",    "ENGINEERS",    "#c4b5fd"),
        ("planner",      "PLANNER",      "#67e8f9"),
        ("odyssey",      "ODYSSEY",      "#f9a8d4"),
    ]

    def __init__(self, root, config: dict, materials: dict, save_callback,
                 get_current_system=None, get_current_coords=None,
                 plot_system_callback=None, embedded=False):
        self.root          = root
        self.config        = config
        self.materials     = materials
        self.save_callback = save_callback
        self.get_current_system = get_current_system or (lambda: "")
        self.get_current_coords = get_current_coords or (lambda: None)
        self.plot_system_callback = plot_system_callback
        self._active_tab   = "raw"
        self._row_meta = {}

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
        self.win.after(0, self._redraw)

    def _on_close(self):
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
        hdr = tk.Frame(self.win, bg="#0c1014", height=46)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="ENGINEER MATERIALS",
                 font=("Segoe UI", 13, "bold"), fg=COLOR_ACCENT, bg="#0c1014"
                 ).pack(side=tk.LEFT, padx=14, pady=8)
        self._sync_lbl = tk.Label(hdr, text="Not yet synced",
                                   fg=self.UI_DIM, bg="#0c1014",
                                   font=("Consolas", 8))
        self._sync_lbl.pack(side=tk.RIGHT, padx=14)
        button(hdr, "ROUTE SELECTED", self._plot_selected, muted=True,
               padx=8, pady=4).pack(side=tk.RIGHT, padx=4, pady=7)

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
                 fg=self.UI_DIM, font=("Consolas", 8, "bold")).pack(side=tk.LEFT, padx=(12, 5), pady=7)
        self._blueprint_var = tk.StringVar(value=next(iter(BLUEPRINTS)))
        self._blueprint_combo = ttk.Combobox(
            self._planner_controls, textvariable=self._blueprint_var,
            values=sorted(BLUEPRINTS), state="readonly", width=27,
        )
        self._blueprint_combo.pack(side=tk.LEFT, padx=4, pady=6)
        self._blueprint_combo.bind("<<ComboboxSelected>>", lambda _event: self._redraw())
        tk.Label(self._planner_controls, text="GRADE", bg=self.UI_PANEL,
                 fg=self.UI_DIM, font=("Consolas", 8, "bold")).pack(side=tk.LEFT, padx=(8, 4))
        self._grade_var = tk.StringVar(value="5")
        ttk.Combobox(self._planner_controls, textvariable=self._grade_var,
                     values=("1", "2", "3", "4", "5"), state="readonly", width=3).pack(side=tk.LEFT, pady=6)
        button(self._planner_controls, "PIN", self._pin_blueprint,
               padx=10, pady=5).pack(side=tk.LEFT, padx=8, pady=5)
        button(self._planner_controls, "UNPIN", self._unpin_selected,
               muted=True, padx=10, pady=5).pack(side=tk.LEFT, padx=2, pady=5)
        button(self._planner_controls, "FIND TRADERS", self._find_traders,
               muted=True, padx=10, pady=5).pack(side=tk.RIGHT, padx=10, pady=5)

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
            if not self._planner_controls.winfo_manager():
                self._planner_controls.pack(fill=tk.X, before=self._body)
        else:
            self._planner_controls.pack_forget()
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

        if self._active_tab in ("raw", "manufactured", "encoded"):
            self._redraw_materials(self._active_tab)
        elif self._active_tab == "engineers":
            self._redraw_engineers()
        elif self._active_tab == "planner":
            self._redraw_planner()
        else:
            self._redraw_odyssey()
        self._update_sync_label()

    def _configure_columns(self, headings):
        for column, (label, width, anchor, stretch) in headings.items():
            self._material_tree.heading(column, text=label)
            self._material_tree.column(column, width=width, minwidth=50,
                                       anchor=anchor, stretch=stretch)

    def _redraw_materials(self, cat):
        self._configure_columns({
            "grade": ("GRADE", 55, tk.CENTER, False),
            "material": ("MATERIAL", 235, tk.W, True),
            "stock": ("COUNT / CAP", 105, tk.E, False),
            "capacity": ("CAPACITY", 155, tk.W, False),
        })
        cat_data = self.materials.get(cat, {})

        items_with_count = []
        for key, item in cat_data.items():
            count = int(item.get("count", 0) if isinstance(item, dict) else item)
            if count > 0:
                items_with_count.append((key, item, count))

        if not items_with_count:
            self._material_tree.insert(
                "",
                tk.END,
                values=("", f"No {cat.upper()} materials on record", "", "Log into Elite Dangerous to sync"),
                tags=("empty",),
            )
            self._update_footer(cat, cat_data)
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

        self._update_footer(cat, cat_data)

    def _redraw_engineers(self):
        self._configure_columns({
            "grade": ("STATUS", 90, tk.CENTER, False),
            "material": ("ENGINEER", 190, tk.W, True),
            "stock": ("ACCESS", 90, tk.CENTER, False),
            "capacity": ("SYSTEM · SPECIALTY", 300, tk.W, True),
        })
        records = self.materials.get("engineers") or {}
        order = {"Unlocked": 0, "Invited": 1, "Known": 2}
        rows = sorted(records.items(), key=lambda pair: (
            order.get(pair[1].get("progress"), 3), -int(pair[1].get("rank") or 0), pair[0]
        ))
        if not rows:
            self._material_tree.insert("", tk.END, values=("", "No engineer progress recorded", "", "Launch Elite Dangerous to sync"), tags=("empty",))
        for name, rec in rows:
            system, offers, on_foot = ENGINEERS.get(name, ("", "", False))
            progress = rec.get("progress") or "Unknown"
            rank = int(rec.get("rank") or 0)
            access = f"G{rank} / 5" if progress == "Unlocked" and rank else progress.upper()
            label = f"{name}  [ON-FOOT]" if on_foot else name
            iid = self._material_tree.insert("", tk.END, values=(progress.upper(), label, access,
                                             " · ".join(value for value in (system, offers) if value)),
                                             tags=("mid_cap" if progress == "Unlocked" else "low_cap",))
            if system:
                self._row_meta[iid] = {"system": system}
        unlocked = sum(1 for rec in records.values() if rec.get("progress") == "Unlocked")
        self._total_lbl.config(text=f"Unlocked: {unlocked} / {len(records)} recorded")
        self._type_lbl.config(text="EngineerProgress journal data")

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
        if not plans:
            self._material_tree.insert("", tk.END, values=("", "Nothing pinned yet", "", "Choose a blueprint and grade above, then PIN"), tags=("empty",))
        for plan_row in plans:
            total = sum(row["need"] for row in plan_row["materials"])
            have = sum(min(row["have"], row["need"]) for row in plan_row["materials"])
            pct = round(have / total * 100) if total else 100
            status = "READY TO ENGINEER" if plan_row["craftable"] else f"{pct}% collected"
            iid = self._material_tree.insert("", tk.END,
                values=(f"G{plan_row['grade']}", plan_row["blueprint"], f"{have} / {total}", status),
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
        self._total_lbl.config(text=f"Pinned blueprints: {len(plans)}")
        selected = self._blueprint_var.get()
        info = BLUEPRINT_INFO.get(selected, {})
        self._type_lbl.config(text=info.get("what", "Verified starter recipe set"))

    def _redraw_odyssey(self):
        self._configure_columns({
            "grade": ("TYPE", 100, tk.CENTER, False),
            "material": ("LOCKER ITEM", 280, tk.W, True),
            "stock": ("COUNT", 90, tk.E, False),
            "capacity": ("USE", 260, tk.W, True),
        })
        locker = self.materials.get("ship_locker") or {}
        total = 0
        for group in ("items", "components", "data", "consumables"):
            rows = locker.get(group) or []
            if not rows:
                continue
            self._material_tree.insert("", tk.END, values=(group.upper(), f"{group.upper()} · {len(rows)} types", "", ""), tags=("grade_header",))
            for item in rows:
                count = int(item.get("count") or 0)
                total += count
                self._material_tree.insert("", tk.END, values=(group.upper(), item.get("name"), count,
                                          "Bartenders / on-foot engineering"), tags=("low_cap",))
        if not total:
            self._material_tree.insert("", tk.END, values=("", "No Odyssey locker data", "", "ShipLocker.json syncs automatically"), tags=("empty",))
        self._total_lbl.config(text=f"Locker total: {total:,}")
        self._type_lbl.config(text="Goods · assets · data · consumables")

    def _pin_blueprint(self):
        name = self._blueprint_var.get()
        if name not in BLUEPRINTS:
            return
        grade = max(1, min(5, int(self._grade_var.get() or 5)))
        pins = [pin for pin in (self.materials.get("pinned_blueprints") or []) if pin.get("name") != name]
        pins.append({"name": name, "grade": grade})
        self.materials["pinned_blueprints"] = pins
        self.save_callback(self.materials)
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
        self.save_callback(self.materials)
        self._redraw()

    def _find_traders(self):
        system = self.get_current_system() or ""
        coords = self.get_current_coords()
        if not system and not coords:
            self._total_lbl.config(text="No current system available for trader search")
            return
        self._total_lbl.config(text="Searching for nearby material traders…")

        def worker():
            try:
                found = []
                for kind in ("raw", "manufactured", "encoded"):
                    rows = spansh.material_traders(system, kind, size=1, coords=coords)
                    found.append((kind, rows[0] if rows else None))
                self.win.after(0, lambda: self._show_traders(found))
            except Exception as exc:
                message = str(exc)
                self.win.after(0, lambda msg=message: self._total_lbl.config(text=f"Trader search failed: {msg}"))

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
        rows = self._material_tree.get_children()
        if rows:
            self._material_tree.delete(*rows)
        self._row_meta = {}
        for kind, trader in found:
            if trader:
                detail = f"{trader.get('distance', 0):,.1f} ly · {trader.get('dist_ls') or '?'} ls"
                if trader.get("large_pad"):
                    detail += " · L pad"
                iid = self._material_tree.insert("", tk.END, values=(kind.upper(), trader.get("station"), trader.get("system"), detail), tags=("mid_cap",))
                self._row_meta[iid] = {"system": trader.get("system")}
            else:
                self._material_tree.insert("", tk.END, values=(kind.upper(), "No trader found", "", ""), tags=("empty",))
        self._total_lbl.config(text="Nearest material traders from Spansh")
        self._type_lbl.config(text="Select PLANNER again to restore blueprint plans")

    def _update_footer(self, cat: str, cat_data: dict):
        total  = sum(
            int(v.get("count", 0) if isinstance(v, dict) else v)
            for v in cat_data.values()
        )
        n_mats = sum(1 for v in cat_data.values()
                     if int(v.get("count", 0) if isinstance(v, dict) else v) > 0)
        self._total_lbl.config(text=f"Total held: {total:,}")
        self._type_lbl.config(
            text=f"{n_mats} material type{'s' if n_mats != 1 else ''}")

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
