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

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config
from ui_theme import THEME, ThemedWindowMixin, apply_window, button, scrollbar, window_surface

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

        # Scrollable list
        body = tk.Frame(self.win, bg=self.UI_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 0))

        page_scroll = scrollbar(body, orient=tk.VERTICAL)
        self._canvas = tk.Canvas(body, bg=self.UI_PANEL,
                                  highlightthickness=0,
                                  yscrollcommand=page_scroll.set)
        page_scroll.config(command=self._canvas.yview)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        page_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._inner = tk.Frame(self._canvas, bg=self.UI_PANEL)
        self._inner_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>",
                         lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfig(self._inner_id, width=e.width))
        self._canvas.bind("<MouseWheel>",
                          lambda e: self._canvas.yview_scroll(-1 * (e.delta // 120), "units"))

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
        for w in self._inner.winfo_children():
            w.destroy()

        cat      = self._active_tab
        cat_data = self.materials.get(cat, {})

        # Collect only materials with count > 0
        items_with_count = []
        for key, item in cat_data.items():
            count = int(item.get("count", 0) if isinstance(item, dict) else item)
            if count > 0:
                items_with_count.append((key, item, count))

        if not items_with_count:
            tk.Label(
                self._inner,
                text=(
                    f"No {cat.upper()} materials on record.\n\n"
                    "Log into Elite Dangerous — the app will\n"
                    "sync your inventory from the journal."
                ),
                font=("Consolas", 9), fg=self.UI_MUTED, bg=self.UI_PANEL,
                justify=tk.LEFT,
            ).pack(anchor="w", padx=16, pady=16)
            self._update_footer(cat, cat_data)
            self._update_sync_label()
            return

        # Group by grade
        by_grade: dict[int, list] = {}
        for key, item, count in items_with_count:
            g = _GRADE.get(key, 3)
            by_grade.setdefault(g, []).append((key, item, count, g))

        # Column header row
        hdr_row = tk.Frame(self._inner, bg="#0b0e12")
        hdr_row.pack(fill=tk.X, padx=8, pady=(4, 0))
        tk.Label(hdr_row, text=" G ", font=("Consolas", 8, "bold"),
                 fg=self.UI_DIM, bg="#0b0e12", width=3).pack(side=tk.LEFT)
        tk.Label(hdr_row, text="MATERIAL", font=("Consolas", 8, "bold"),
                 fg=COLOR_ORANGE, bg="#0b0e12", anchor="w").pack(side=tk.LEFT, padx=(4, 0))
        tk.Label(hdr_row, text="COUNT / CAP", font=("Consolas", 8, "bold"),
                 fg=COLOR_ORANGE, bg="#0b0e12").pack(side=tk.RIGHT, padx=12)
        tk.Frame(self._inner, bg="#1a2228", height=1).pack(fill=tk.X, padx=8, pady=(2, 0))

        for grade in sorted(by_grade.keys()):
            cap = _GRADE_CAP.get(grade, 200)
            rows = sorted(by_grade[grade], key=lambda x: (-(x[2]), (
                x[1].get("name") if isinstance(x[1], dict) else x[0]).lower()))

            # Grade section separator
            g_hdr = tk.Frame(self._inner, bg="#0f1318")
            g_hdr.pack(fill=tk.X, padx=8, pady=(6, 0))
            tk.Label(g_hdr, text=f"  G{grade}  —  individual cap: {cap:,}",
                     font=("Consolas", 8, "bold"), fg=self.UI_DIM, bg="#0f1318",
                     anchor="w").pack(side=tk.LEFT, padx=4, pady=2)

            for key, item, count, g in rows:
                name  = (item.get("name") if isinstance(item, dict) else None) or key.replace("_", " ").title()
                fill  = min(1.0, count / cap)

                if fill >= 0.85:
                    bar_col = "#e05050"    # near cap — warn red
                elif fill >= 0.50:
                    bar_col = COLOR_ACCENT # half full — cyan
                else:
                    bar_col = "#3a7d9e"    # low — dim blue

                row_frame = tk.Frame(self._inner, bg=self.UI_PANEL)
                row_frame.pack(fill=tk.X, padx=8, pady=(1, 0))

                # Grade badge
                tk.Label(row_frame, text=f" G{g}",
                         font=("Consolas", 8), fg=self.UI_DIM,
                         bg=self.UI_PANEL, width=3, anchor="w").pack(side=tk.LEFT)

                # Material name (fixed-width, truncated)
                name_disp = name if len(name) <= 34 else name[:33] + "…"
                tk.Label(row_frame, text=name_disp,
                         font=("Consolas", 9), fg=COLOR_TEXT,
                         bg=self.UI_PANEL, anchor="w", width=34,
                         ).pack(side=tk.LEFT, padx=(4, 8))

                # Count / cap text (right-aligned)
                count_txt = f"{count:>4} / {cap}"
                tk.Label(row_frame, text=count_txt,
                         font=("Consolas", 9, "bold"),
                         fg=bar_col if fill >= 0.85 else COLOR_TEXT,
                         bg=self.UI_PANEL).pack(side=tk.RIGHT, padx=(0, 12))

                # Fill bar
                bar_bg = tk.Frame(row_frame, bg="#1a2430", height=8, width=110)
                bar_bg.pack(side=tk.RIGHT, pady=5, padx=(0, 8))
                bar_bg.pack_propagate(False)
                tk.Frame(bar_bg, bg=bar_col, height=8).place(
                    x=0, y=0, relheight=1.0, relwidth=fill)

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
