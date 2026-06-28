import json
import math
import tkinter as tk

from config import CONFIG_FILE, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT
from colonisation_commodities import (
    CATEGORY_ORDER,
    SOURCE_ORDER,
    get_commodity_category,
    get_commodity_display_name,
    get_primary_source,
    normalize_commodity_name,
)


class ColonyOverlay:
    """Always-on-top local colony shopping overlay.

    This is intentionally independent of the EDCOLONY EDMC plugin and server. It
    renders from VoidCompass' local colonisation projects plus the latest local
    Cargo.json snapshot.
    """

    BG_KEY = "#ff00ff"
    PANEL = "#010101"
    PANEL_2 = "#0b1117"
    MUTED = "#7a8a98"
    DIM = "#46525d"
    BLUE = COLOR_ACCENT

    def __init__(self, root, config, projects_getter, cargo_getter, capacity_getter):
        self.root = root
        self.config = config
        self.projects_getter = projects_getter
        self.cargo_getter = cargo_getter
        self.capacity_getter = capacity_getter
        self._font_scale = 1.0
        self._sort_mode = "alpha"
        self._show_trips = True
        self._save_job = None
        self._drag_x = 0
        self._drag_y = 0

        self.win = tk.Toplevel(root)
        self.win.title("Colony Shopping List")
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True, "-transparentcolor", self.BG_KEY, "-toolwindow", True)
        self.win.config(bg=self.BG_KEY)

        x = self._safe_int(config.get("colony_overlay_x"), 40)
        y = self._safe_int(config.get("colony_overlay_y"), 40)
        w = self._safe_int(config.get("colony_overlay_w"), 300)
        h = self._safe_int(config.get("colony_overlay_h"), 260)
        self.win.geometry(f"{w}x{h}+{x}+{y}")

        self.canvas = tk.Canvas(self.win, bg=self.BG_KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.panel = tk.Frame(self.canvas, bg=self.PANEL)
        self.panel_window = self.canvas.create_window(7, 7, window=self.panel, anchor="nw")

        self._load_prefs()
        self._build_ui()
        self.canvas.bind("<Configure>", self._redraw_background)
        self.win.bind("<Destroy>", lambda _e: self._save_geometry())
        self.force_topmost()
        self.update()

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return int(default)

    def is_open(self):
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False

    def lift(self):
        try:
            self.win.lift()
        except Exception:
            pass

    def force_topmost(self):
        if not self.is_open():
            return
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        refresh_ms = max(2000, int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000))
        self.win.after(refresh_ms, self.force_topmost)

    def _prefs_path(self):
        return "colony_overlay_prefs.json"

    def _load_prefs(self):
        try:
            with open(self._prefs_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            self._sort_mode = str(data.get("sort_mode") or "alpha")
            self._show_trips = bool(data.get("show_trips", True))
            self._font_scale = max(0.8, min(1.8, float(data.get("font_scale", 1.0))))
        except Exception:
            pass

    def _save_prefs(self):
        try:
            with open(self._prefs_path(), "w", encoding="utf-8") as f:
                json.dump({
                    "sort_mode": self._sort_mode,
                    "show_trips": self._show_trips,
                    "font_scale": self._font_scale,
                }, f, indent=2)
        except Exception:
            pass

    def _build_ui(self):
        header = tk.Frame(self.panel, bg=self.PANEL)
        header.pack(fill=tk.X)
        self.title_label = tk.Label(
            header, text="COLONY SHOPPING", fg=COLOR_ACCENT, bg=self.PANEL,
            font=("Courier", self._font(10), "bold"),
        )
        self.title_label.pack(side=tk.LEFT, padx=10, pady=(8, 6))

        close = tk.Button(
            header, text="X", command=self.win.destroy, bg=self.PANEL,
            fg=self.MUTED, activebackground=self.PANEL_2, activeforeground=COLOR_ACCENT,
            relief=tk.FLAT, bd=0, padx=7, pady=2,
            font=("Courier", self._font(8), "bold"),
        )
        close.pack(side=tk.RIGHT, padx=(2, 8), pady=(6, 4))

        self._hud_button(header, "A+", lambda: self._scale(0.1)).pack(side=tk.RIGHT, padx=(4, 0), pady=(6, 4))
        self._hud_button(header, "A-", lambda: self._scale(-0.1)).pack(side=tk.RIGHT, padx=(4, 0), pady=(6, 4))

        self.trips_var = tk.BooleanVar(value=self._show_trips)
        tk.Checkbutton(
            header, text="Trips", variable=self.trips_var, command=self._toggle_trips,
            bg=self.PANEL, fg=self.MUTED, selectcolor=self.PANEL,
            activebackground=self.PANEL, activeforeground=COLOR_ACCENT,
            highlightthickness=0, font=("Courier", self._font(8), "bold"),
        ).pack(side=tk.RIGHT, padx=(6, 0), pady=(6, 4))

        header.bind("<Button-1>", self._start_move)
        header.bind("<B1-Motion>", self._do_move)
        header.bind("<ButtonRelease-1>", self._end_move)
        self.title_label.bind("<Button-1>", self._start_move)
        self.title_label.bind("<B1-Motion>", self._do_move)
        self.title_label.bind("<ButtonRelease-1>", self._end_move)

        tk.Frame(self.panel, bg=COLOR_ACCENT, height=1).pack(fill=tk.X, padx=0, pady=(0, 6))

        sort_row = tk.Frame(self.panel, bg=self.PANEL)
        sort_row.pack(fill=tk.X, padx=10, pady=(0, 5))
        tk.Label(sort_row, text="SORT:", fg=self.MUTED, bg=self.PANEL, font=("Courier", self._font(8), "bold")).pack(side=tk.LEFT, padx=(0, 8))
        self.sort_var = tk.StringVar(value=self._sort_mode)
        for text, value in (("Alpha", "alpha"), ("Category", "category"), ("Source", "source")):
            tk.Radiobutton(
                sort_row, text=text.upper(), value=value, variable=self.sort_var,
                command=self._set_sort_mode, bg=self.PANEL, fg=self.MUTED,
                selectcolor=self.PANEL, activebackground=self.PANEL,
                activeforeground=COLOR_ACCENT, highlightthickness=0,
                font=("Courier", self._font(8), "bold"),
            ).pack(side=tk.LEFT, padx=(0, 6))

        self.summary_label = tk.Label(
            self.panel, text="", fg=COLOR_ORANGE, bg=self.PANEL,
            font=("Courier", self._font(9), "bold"), anchor="w",
        )
        self.summary_label.pack(fill=tk.X, padx=10, pady=(0, 4))

        self.body = tk.Frame(self.panel, bg=self.PANEL)
        self.body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(3, 9))

    def _hud_button(self, parent, text, command):
        return tk.Button(
            parent, text=text, command=command,
            bg=self.PANEL, fg=self.MUTED,
            activebackground=self.PANEL_2, activeforeground=COLOR_ACCENT,
            relief=tk.FLAT, bd=0, padx=5, pady=2,
            font=("Courier", self._font(8), "bold"),
        )

    def _font(self, size):
        return max(8, int(round(size * self._font_scale)))

    def _scale(self, delta):
        self._font_scale = max(0.8, min(1.8, self._font_scale + delta))
        self._save_prefs()
        self.update()

    def _toggle_trips(self):
        self._show_trips = bool(self.trips_var.get())
        self._save_prefs()
        self.update()

    def _set_sort_mode(self):
        self._sort_mode = self.sort_var.get()
        self._save_prefs()
        self.update()

    def _start_move(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_move(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.win.geometry(f"+{x}+{y}")
        self.config["colony_overlay_x"] = x
        self.config["colony_overlay_y"] = y
        self._schedule_config_save()

    def _end_move(self, _event):
        self._save_geometry()

    def _redraw_background(self, _event=None):
        try:
            w = max(int(self.canvas.winfo_width()), 50)
            h = max(int(self.canvas.winfo_height()), 50)
            m = 5
            self.canvas.delete("bg")
            self.canvas.create_rectangle(m, m, w - m, h - m, fill=self.PANEL, outline=COLOR_ACCENT, width=2, tags="bg")
            self.canvas.tag_lower("bg")
            self.canvas.coords(self.panel_window, m + 2, m + 2)
            self.canvas.itemconfig(self.panel_window, width=max(0, w - (2 * m + 4)), height=max(0, h - (2 * m + 4)))
        except Exception:
            pass

    def _save_geometry(self):
        if not self.is_open():
            return
        try:
            self.win.update_idletasks()
            self.config["colony_overlay_x"] = int(self.win.winfo_x())
            self.config["colony_overlay_y"] = int(self.win.winfo_y())
            self.config["colony_overlay_w"] = max(260, int(self.win.winfo_width()))
            self.config["colony_overlay_h"] = max(120, int(self.win.winfo_height()))
            self._write_config()
        except Exception:
            pass

    def _write_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)

    def _schedule_config_save(self):
        if self._save_job:
            try:
                self.win.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.win.after(250, self._flush_scheduled_save)

    def _flush_scheduled_save(self):
        self._save_job = None
        try:
            self._write_config()
        except Exception:
            pass

    def _cargo_counts(self):
        counts = {}
        for item in self.cargo_getter() or []:
            name = item.get("Name") or item.get("Name_Localised") or ""
            key = normalize_commodity_name(name)
            if not key:
                continue
            try:
                count = int(item.get("Count") or 0)
            except Exception:
                count = 0
            counts[key] = counts.get(key, 0) + count
        return counts

    def _shopping_items(self):
        totals = {}
        for proj in (self.projects_getter() or {}).values():
            if proj.get("complete") or proj.get("failed"):
                continue
            for res in proj.get("resources") or []:
                key = normalize_commodity_name(res.get("name") or res.get("display") or "")
                if not key:
                    continue
                required = int(res.get("required") or 0)
                provided = min(required, int(res.get("provided") or 0))
                left = max(0, required - provided)
                if left <= 0:
                    continue
                row = totals.setdefault(key, {"commodity": key, "remaining": 0, "in_hold": 0, "needed": 0})
                row["remaining"] += left

        cargo = self._cargo_counts()
        items = []
        for key, row in totals.items():
            in_hold = int(cargo.get(key, 0))
            row["in_hold"] = in_hold
            row["needed"] = max(0, int(row["remaining"]) - in_hold)
            if row["needed"] > 0:
                items.append(row)
        return items

    def _display_name(self, item):
        return get_commodity_display_name(item.get("commodity", ""))

    def _sorted_items(self, items):
        if self._sort_mode == "category":
            return self._with_headers(items, get_commodity_category, CATEGORY_ORDER)
        if self._sort_mode == "source":
            return self._with_headers(items, get_primary_source, SOURCE_ORDER)
        return sorted(items, key=self._display_name)

    def _with_headers(self, items, grouper, order):
        buckets = {}
        for item in items:
            buckets.setdefault(grouper(item.get("commodity", "")), []).append(item)
        out = []
        for header in order:
            rows = buckets.pop(header, [])
            if rows:
                out.append({"header": header})
                out.extend(sorted(rows, key=self._display_name))
        for header in sorted(buckets):
            rows = buckets[header]
            if rows:
                out.append({"header": header})
                out.extend(sorted(rows, key=self._display_name))
        return out

    def update(self):
        if not self.is_open():
            return
        self.win.after(0, self._render)

    def _render(self):
        try:
            for child in list(self.body.children.values()):
                child.destroy()

            items = self._shopping_items()
            total_needed = sum(int(i.get("needed") or 0) for i in items)
            capacity = int(self.capacity_getter() or 0)
            if self._show_trips and capacity > 0 and total_needed > 0:
                self.summary_label.config(text=f"Trips Left: {math.ceil(total_needed / capacity)}  (Cap: {capacity}t)")
            elif capacity > 0:
                self.summary_label.config(text=f"Capacity: {capacity}t")
            else:
                self.summary_label.config(text="")

            if not items:
                tk.Label(
                    self.body, text="No colony resources needed", fg=self.MUTED,
                    bg=self.PANEL, font=("Courier", self._font(9), "bold"),
                ).pack(anchor="nw")
                self._fit_height(150)
                return

            for item in self._sorted_items(items):
                if "header" in item:
                    if self.body.winfo_children():
                        tk.Frame(self.body, bg="#1a2228", height=1).pack(fill=tk.X, pady=(4, 3))
                    tk.Label(
                        self.body, text=str(item["header"]).upper(), fg=COLOR_ORANGE,
                        bg=self.PANEL, font=("Courier", self._font(8), "bold"),
                        anchor="w",
                    ).pack(fill=tk.X, pady=(0, 1))
                    continue
                row = tk.Frame(self.body, bg=self.PANEL)
                row.pack(fill=tk.X, pady=1)
                tk.Label(
                    row, text=self._display_name(item), fg=COLOR_TEXT, bg=self.PANEL,
                    font=("Courier", self._font(9), "bold"), anchor="w",
                ).pack(side=tk.LEFT)
                qty = f"{int(item.get('needed') or 0):,}"
                if item.get("in_hold"):
                    qty = f"{qty}  ({int(item.get('in_hold')):,} hold)"
                tk.Label(
                    row, text=qty, fg=self.BLUE if item.get("in_hold") else "#9ad",
                    bg=self.PANEL, font=("Courier", self._font(9), "bold"),
                    anchor="e",
                ).pack(side=tk.RIGHT)

            self._fit_height()
        except Exception:
            pass

    def _fit_height(self, fallback=None):
        try:
            self.win.update_idletasks()
            width = max(280, int(self.win.winfo_width() or 300))
            panel_h = fallback or int(self.panel.winfo_reqheight() or 160)
            screen_h = int(self.win.winfo_screenheight() or 900)
            height = max(130, min(screen_h - 80, panel_h + 14))
            x = int(self.win.winfo_x())
            y = int(self.win.winfo_y())
            self.win.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass
