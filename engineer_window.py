"""
engineer_window.py — Engineer Material Tracker for VoidCompass.

Displays current Raw / Manufactured / Encoded material stock synced live
from the journal (Materials, MaterialCollected, MaterialDiscarded, etc.).
Persisted to engineer_materials.json next to the executable.
"""

import json
import os
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config
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

# Individual material cap by grade
_GRADE_CAP = {1: 300, 2: 250, 3: 200, 4: 150, 5: 100}

# Total capacity per category
_CAT_CAP = {"raw": 1000, "manufactured": 1000, "encoded": 500}

# internal journal name (lowercase, no spaces) → grade
_RAW_GRADES: dict[str, int] = {
    # G1
    "carbon": 1, "iron": 1, "lead": 1, "nickel": 1,
    "phosphorus": 1, "rhenium": 1, "sulphur": 1,
    # G2
    "arsenic": 2, "chromium": 2, "germanium": 2, "manganese": 2,
    "vanadium": 2, "zinc": 2, "zirconium": 2,
    # G3
    "mercury": 3, "molybdenum": 3, "niobium": 3, "tin": 3, "tungsten": 3,
    # G4
    "antimony": 4, "cadmium": 4, "polonium": 4, "ruthenium": 4,
    "selenium": 4, "technetium": 4, "tellurium": 4, "yttrium": 4,
}

_MFD_GRADES: dict[str, int] = {
    # G1
    "basicconductors": 1, "chemicalstorage": 1, "compactcomposites": 1,
    "crystalshards": 1, "gridresistors": 1, "heatconductionwiring": 1,
    "mechanicalscrap": 1, "salvagedalloys": 1, "wornshieldemitters": 1,
    # G2
    "chemicalprocessors": 2, "conductivecomponents": 2, "filamentcomposites": 2,
    "galvanisingalloys": 2, "heatdispersionplate": 2, "hybridcapacitors": 2,
    "mechanicalequipment": 2, "shieldemitters": 2,
    # G3
    "chemicaldistillery": 3, "conductiveceramics": 3, "electrochemicalarrays": 3,
    "highdensitycomposites": 3, "heatexchangers": 3, "mechanicalcomponents": 3,
    "phasealloys": 3, "precipitatedalloys": 3, "shieldingsensors": 3,
    # G4
    "chemicalmanipulators": 4, "compoundshielding": 4, "conductivepolymers": 4,
    "configurablecomponents": 4, "heatvanes": 4, "polymercapacitors": 4,
    "proprietarycomposites": 4, "protolightalloys": 4, "refinedfocuscrystals": 4,
    "temperedalloys": 4,
    # G5
    "biotechconductors": 5, "coredynamicscomposites": 5, "exquisitefocuscrystals": 5,
    "imperialshielding": 5, "improvisedcomponents": 5, "militarygradealloys": 5,
    "militarysupercapacitors": 5, "pharmaceuticalisolators": 5,
    "protoheatradiators": 5, "protoradiolicalloys": 5,
}

_ENC_GRADES: dict[str, int] = {
    # G1
    "bulkscandata": 1, "disruptedwakeechoes": 1, "encodedscandata": 1,
    "scandatabanks": 1, "scrambledemissiondata": 1, "shieldcyclerecordings": 1,
    "shieldfrequencydata": 1, "unidentifiedscanarchives": 1,
    # G2
    "aberrantshieldpatternanalysis": 2, "atypicaldisruptedwakeechoes": 2,
    "classifiedscandata": 2, "divergentscandata": 2,
    "inconsistentshieldsoakanalysis": 2, "irregularemissiondata": 2,
    "modifiedconsumerfirmware": 2, "strangewakesolutions": 2,
    "unexpectedemissiondata": 2,
    # G3
    "classifiedscanfragment": 3, "crackedindustrialfirmware": 3,
    "dataminedwakeexceptions": 3, "disorganisedfeedbackloop": 3,
    "modifiedembeddedfirmware": 3, "opensymmetrickeys": 3,
    "securityfirmwarepatch": 3, "specialisedlegacyfirmware": 3,
    "unusualencryptedfiles": 3, "untypicalshieldscans": 3,
    # G4
    "abnormalcompactemissionsdata": 4, "atypicalencryptionarchives": 4,
    "embeddedfirmware": 4, "hyperspacetrajectories": 4,
    "smearedshieldpatternanalysis": 4, "symmetrickeys": 4,
    "wakesolutions": 4,
    # G5
    "adaptiveencryptors": 5, "classifiedscanfragments": 5,
    "encryptedscandatabanks": 5, "legacyfirmware": 5,
    "securitykeys": 5,
}

# Combined lookup: internal_name → category
_MAT_CATEGORY: dict[str, str] = {}
for _k in _RAW_GRADES:
    _MAT_CATEGORY[_k] = "raw"
for _k in _MFD_GRADES:
    _MAT_CATEGORY[_k] = "manufactured"
for _k in _ENC_GRADES:
    _MAT_CATEGORY[_k] = "encoded"

# Combined grade lookup across all categories
_GRADE: dict[str, int] = {}
_GRADE.update(_RAW_GRADES)
_GRADE.update(_MFD_GRADES)
_GRADE.update(_ENC_GRADES)


def get_material_category(key: str) -> str:
    """Return 'raw', 'manufactured', or 'encoded' for an internal material name."""
    return _MAT_CATEGORY.get(key.lower(), "manufactured")


def load_engineer_materials(path=None) -> dict:
    path = path or os.path.join(os.getcwd(), ENGINEER_MATERIALS_FILE)
    if not os.path.exists(path):
        return {"raw": {}, "manufactured": {}, "encoded": {}, "last_updated": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for cat in ("raw", "manufactured", "encoded"):
            data.setdefault(cat, {})
        return data
    except Exception:
        return {"raw": {}, "manufactured": {}, "encoded": {}, "last_updated": None}


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
    ]

    def __init__(self, root, config: dict, materials: dict, save_callback, embedded=False):
        self.root          = root
        self.config        = config
        self.materials     = materials
        self.save_callback = save_callback
        self._active_tab   = "raw"

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

        # Reusable native table. The old canvas rebuilt several widgets per
        # material on every tab click, making page switches visibly stall.
        body = tk.Frame(self.win, bg=self.UI_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 0))

        columns = ("grade", "material", "stock", "capacity")
        self._material_tree = ttk.Treeview(
            body,
            columns=columns,
            show="headings",
            style="Engineer.Treeview",
            selectmode="none",
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

        cat      = self._active_tab
        cat_data = self.materials.get(cat, {})

        # Collect only materials with count > 0
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
            self._update_sync_label()
            return

        # Group by grade
        by_grade: dict[int, list] = {}
        for key, item, count in items_with_count:
            g = _GRADE.get(key, 3)
            by_grade.setdefault(g, []).append((key, item, count, g))

        for grade in sorted(by_grade.keys()):
            cap = _GRADE_CAP.get(grade, 200)
            rows = sorted(by_grade[grade], key=lambda x: (-(x[2]), (
                x[1].get("name") if isinstance(x[1], dict) else x[0]).lower()))

            self._material_tree.insert(
                "",
                tk.END,
                values=(f"G{grade}", f"GRADE {grade}  —  individual cap {cap:,}", "", ""),
                tags=("grade_header",),
            )

            for key, item, count, g in rows:
                name  = (item.get("name") if isinstance(item, dict) else None) or key.replace("_", " ").title()
                fill  = min(1.0, count / cap)

                if fill >= 0.85:
                    row_tag = "near_cap"
                elif fill >= 0.50:
                    row_tag = "mid_cap"
                else:
                    row_tag = "low_cap"

                segments = 10
                filled = max(0, min(segments, round(fill * segments)))
                capacity = "█" * filled + "░" * (segments - filled) + f"  {fill * 100:>3.0f}%"
                self._material_tree.insert(
                    "",
                    tk.END,
                    values=(f"G{g}", name, f"{count:,} / {cap:,}", capacity),
                    tags=(row_tag,),
                )

        self._update_footer(cat, cat_data)
        self._update_sync_label()

    def _update_footer(self, cat: str, cat_data: dict):
        total  = sum(
            int(v.get("count", 0) if isinstance(v, dict) else v)
            for v in cat_data.values()
        )
        cap    = _CAT_CAP.get(cat, 1000)
        n_mats = sum(1 for v in cat_data.values()
                     if int(v.get("count", 0) if isinstance(v, dict) else v) > 0)
        pct    = int(total / cap * 100) if cap else 0
        self._total_lbl.config(text=f"Total: {total:,} / {cap:,}  ({pct}%)")
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
