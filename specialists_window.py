"""Integrated Mining, Combat/AX, Carrier, and Exobiology role console."""

from __future__ import annotations

import json
import math
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT
from ui_theme import THEME, ThemedWindowMixin, apply_window, button, configure_ttk, scrollbar, window_surface


def _cr(value):
    try:
        return f"{int(value or 0):,} cr"
    except (TypeError, ValueError):
        return "—"


def _num(value, suffix=""):
    if value is None:
        return "—"
    try:
        number = float(value)
        text = f"{number:,.2f}".rstrip("0").rstrip(".")
        return f"{text}{suffix}"
    except (TypeError, ValueError):
        return f"{value}{suffix}"


def _duration(seconds):
    try:
        seconds = max(0, int(seconds or 0))
    except (TypeError, ValueError):
        return "—"
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:d}:{secs:02d}"


def _human(value):
    text = str(value or "").strip().strip("$;")
    if text.casefold().endswith("_name"):
        text = text[:-5]
    return text.replace("_", " ").title() or "—"


class SpecialistsWindow(ThemedWindowMixin):
    UI_FONT = ("Segoe UI", 9)
    UI_BOLD = ("Segoe UI", 9, "bold")
    UI_MONO = ("Consolas", 9)
    UI_MONO_BOLD = ("Consolas", 10, "bold")

    def __init__(self, root, app, engine, embedded=False):
        self.root = root
        self.app = app
        self.engine = engine
        self.config = app.config
        self.embedded = embedded
        self._tick_job = None
        self._pin_rows = []
        self._tree_row_cache = {}
        self.win = window_surface(root, embedded=embedded)
        self.win.title("VOID COMPASS // SPECIALISTS")
        self.win.geometry(self.config.get("specialists_geometry", "1100x760"))
        apply_window(self.win)
        configure_ttk(self.win, prefix="Specialists")
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self.refresh()

    def is_open(self):
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False

    def _on_close(self):
        if self._tick_job is not None:
            try:
                self.win.after_cancel(self._tick_job)
            except Exception:
                pass
        self._tick_job = None
        try:
            if not self.embedded:
                self.config["specialists_geometry"] = self.win.geometry()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass

    def on_shown(self):
        self.refresh()
        self._schedule_tick()

    def _schedule_tick(self):
        if self._tick_job is not None or not self.is_open():
            return
        self._tick_job = self.win.after(1000, self._tick)

    def _tick(self):
        self._tick_job = None
        if not self.is_open():
            return
        if getattr(self.app, "_active_page", None) == "SPECIALISTS":
            if self._active_section() in {"mining", "combat", "exobiology"}:
                self.refresh()
            self._schedule_tick()

    def _panel(self, parent, title, subtitle=""):
        panel = tk.Frame(parent, bg=THEME.panel, highlightbackground=THEME.border, highlightthickness=1)
        panel.pack(fill=tk.X, padx=10, pady=(8, 0))
        tk.Frame(panel, bg=COLOR_ACCENT, height=2).pack(fill=tk.X)
        header = tk.Frame(panel, bg=THEME.panel)
        header.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(header, text=title, fg=COLOR_ORANGE, bg=THEME.panel, font=self.UI_BOLD).pack(side=tk.LEFT)
        if subtitle:
            tk.Label(header, text=f"  {subtitle}", fg=THEME.muted, bg=THEME.panel, font=("Segoe UI", 8)).pack(side=tk.LEFT)
        body = tk.Frame(panel, bg=THEME.panel)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        return body

    def _metric_grid(self, parent, names):
        frame = tk.Frame(parent, bg=THEME.panel)
        frame.pack(fill=tk.X)
        values = {}
        for index, name in enumerate(names):
            cell = tk.Frame(frame, bg=THEME.panel_alt, highlightbackground=THEME.border, highlightthickness=1)
            cell.grid(row=index // 3, column=index % 3, sticky="nsew", padx=3, pady=3)
            tk.Label(cell, text=name, fg=THEME.muted, bg=THEME.panel_alt, font=("Segoe UI", 7, "bold"), anchor="w").pack(fill=tk.X, padx=8, pady=(5, 0))
            value = tk.Label(cell, text="—", fg=COLOR_TEXT, bg=THEME.panel_alt, font=self.UI_MONO_BOLD, anchor="w")
            value.pack(fill=tk.X, padx=8, pady=(2, 6))
            values[name] = value
        for column in range(3):
            frame.grid_columnconfigure(column, weight=1)
        return values

    def _tree(self, parent, columns, height=7):
        wrap = tk.Frame(parent, bg=THEME.panel)
        tree = ttk.Treeview(wrap, columns=[row[0] for row in columns], show="headings", height=height, style="Specialists.Treeview")
        for key, title, width, anchor in columns:
            tree.heading(key, text=title)
            tree.column(key, width=width, minwidth=50, anchor=anchor, stretch=True)
        bar = scrollbar(wrap, orient=tk.VERTICAL, command=tree.yview, prefix="Specialists")
        tree.configure(yscrollcommand=bar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        wrap.pack(fill=tk.BOTH, expand=True)
        return tree

    @staticmethod
    def _clear(tree):
        children = tree.get_children()
        if children:
            tree.delete(*children)

    def _set_tree_rows(self, tree, rows):
        """Replace Treeview rows only when their displayed values changed."""
        rows = tuple(tuple(row) for row in rows)
        if self._tree_row_cache.get(tree) == rows:
            return False
        self._clear(tree)
        for row in rows:
            tree.insert("", tk.END, values=row)
        self._tree_row_cache[tree] = rows
        return True

    def _build(self):
        header = tk.Frame(self.win, bg=THEME.header)
        header.pack(fill=tk.X)
        tk.Label(header, text="SPECIALIST CONSOLE", fg=COLOR_ACCENT, bg=THEME.header, font=("Bahnschrift SemiCondensed", 16, "bold")).pack(side=tk.LEFT, padx=14, pady=10)
        self.global_status = tk.Label(header, text="LOCAL · PROFILE AWARE · JOURNAL DRIVEN", fg=THEME.muted, bg=THEME.header, font=("Consolas", 8, "bold"))
        self.global_status.pack(side=tk.RIGHT, padx=14)

        self.tabs = ttk.Notebook(self.win, style="Specialists.TNotebook")
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.mining_page = tk.Frame(self.tabs, bg=THEME.bg)
        self.combat_page = tk.Frame(self.tabs, bg=THEME.bg)
        self.carrier_page = tk.Frame(self.tabs, bg=THEME.bg)
        self.exobio_page = tk.Frame(self.tabs, bg=THEME.bg)
        self.tabs.add(self.mining_page, text="◆  MINING")
        self.tabs.add(self.combat_page, text="⌁  COMBAT / AX")
        self.tabs.add(self.carrier_page, text="⬢  CARRIER")
        self.tabs.add(self.exobio_page, text="⌾  EXOBIOLOGY")
        self._tab_sections = {
            str(self.mining_page): "mining",
            str(self.combat_page): "combat",
            str(self.carrier_page): "carrier",
            str(self.exobio_page): "exobiology",
        }
        self.tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed, add="+")
        self._build_mining()
        self._build_combat()
        self._build_carrier()
        self._build_exobio()

    def select_section(self, section):
        """Select a workflow when another dashboard control links here."""
        pages = {
            "mining": self.mining_page,
            "combat": self.combat_page,
            "ax": self.combat_page,
            "carrier": self.carrier_page,
            "exobiology": self.exobio_page,
            "exobio": self.exobio_page,
        }
        page = pages.get(str(section or "").strip().casefold())
        if page is not None:
            self.tabs.select(page)

    def _active_section(self):
        try:
            return self._tab_sections.get(str(self.tabs.select()), "mining")
        except Exception:
            return "mining"

    def _on_tab_changed(self, _event=None):
        self.refresh()

    def _build_mining(self):
        body = self._panel(self.mining_page, "MINING RUN", "journal-counted yield and attributed sales")
        actions = tk.Frame(body, bg=THEME.panel)
        actions.pack(fill=tk.X, pady=(0, 5))
        self.mining_state = tk.Label(actions, text="IDLE", fg=THEME.muted, bg=THEME.panel, font=self.UI_MONO_BOLD)
        self.mining_state.pack(side=tk.LEFT)
        button(actions, "START RUN", self._start_mining, accent=True).pack(side=tk.RIGHT)
        button(actions, "END RUN", self._end_mining).pack(side=tk.RIGHT, padx=(0, 6))
        self.mining_message = tk.Label(body, text="", fg=THEME.muted, bg=THEME.panel, font=self.UI_FONT, anchor="w")
        self.mining_message.pack(fill=tk.X, pady=(0, 5))
        self.mining_metrics = self._metric_grid(body, ("ELAPSED", "REFINED", "YIELD RATE", "PROSPECTED", "CORE CRACKS", "RUN REVENUE"))

        detail = tk.Frame(self.mining_page, bg=THEME.bg)
        detail.pack(fill=tk.BOTH, expand=True, padx=10, pady=(8, 0))
        left = tk.Frame(detail, bg=THEME.panel, highlightbackground=THEME.border, highlightthickness=1)
        right = tk.Frame(detail, bg=THEME.panel, highlightbackground=THEME.border, highlightthickness=1)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        tk.Label(left, text="REFINERY YIELD", fg=COLOR_ORANGE, bg=THEME.panel, font=self.UI_BOLD).pack(anchor="w", padx=8, pady=7)
        self.mining_yield = self._tree(left, (("name", "Commodity", 170, "w"), ("refined", "Refined", 70, "e"), ("delta", "Cargo Δ", 70, "e"), ("sold", "Sold", 65, "e")), 6)
        tk.Label(right, text="PROSPECTOR QUALITY", fg=COLOR_ORANGE, bg=THEME.panel, font=self.UI_BOLD).pack(anchor="w", padx=8, pady=7)
        self.mining_targets = self._tree(right, (("name", "Material", 160, "w"), ("seen", "Seen", 55, "e"), ("best", "Best", 65, "e"), ("avg", "Average", 70, "e")), 6)
        economics = self._panel(self.mining_page, "LIMPET ECONOMICS", "inventory, launches, and observed purchase cost")
        self.mining_limpets = tk.Label(economics, text="—", fg=COLOR_TEXT, bg=THEME.panel, font=self.UI_MONO, justify=tk.LEFT, anchor="w")
        self.mining_limpets.pack(fill=tk.X)
        history = self._panel(self.mining_page, "RECENT MINING RUNS", "durable per commander")
        self.mining_history = self._tree(history, (("when", "Started", 150, "w"), ("system", "System", 180, "w"), ("tons", "Refined", 75, "e"), ("rocks", "Rocks", 60, "e"), ("reason", "Ended", 90, "w")), 5)

    def _build_combat(self):
        ready = self._panel(self.combat_page, "COMBAT / AX READINESS", "latest Loadout observation; weapon fire is not journaled")
        top = tk.Frame(ready, bg=THEME.panel)
        top.pack(fill=tk.X)
        self.combat_level = tk.Label(top, text="NO LOADOUT OBSERVED", fg=COLOR_ORANGE, bg=THEME.panel, font=self.UI_MONO_BOLD)
        self.combat_level.pack(side=tk.LEFT)
        self.combat_score = tk.Label(top, text="0 / 100", fg=COLOR_ACCENT, bg=THEME.panel, font=("Consolas", 16, "bold"))
        self.combat_score.pack(side=tk.RIGHT)
        self.combat_checklist = tk.Label(
            ready, text="", fg=COLOR_TEXT, bg=THEME.panel, font=self.UI_MONO,
            justify=tk.LEFT, anchor="w", wraplength=900,
        )
        self.combat_checklist.pack(fill=tk.X, pady=(8, 6))
        self.combat_ammo = self._tree(ready, (("module", "Observed module", 260, "w"), ("slot", "Slot", 130, "w"), ("clip", "Clip", 60, "e"), ("hopper", "Hopper", 70, "e"), ("total", "Total", 60, "e")), 5)

        session = self._panel(self.combat_page, "COMBAT SESSION", "kills, claims, damage, synthesis, and AX contacts")
        actions = tk.Frame(session, bg=THEME.panel)
        actions.pack(fill=tk.X, pady=(0, 5))
        self.combat_state = tk.Label(actions, text="IDLE", fg=THEME.muted, bg=THEME.panel, font=self.UI_MONO_BOLD)
        self.combat_state.pack(side=tk.LEFT)
        button(actions, "START SESSION", self._start_combat, accent=True).pack(side=tk.RIGHT)
        button(actions, "END SESSION", self._end_combat).pack(side=tk.RIGHT, padx=(0, 6))
        self.combat_message = tk.Label(session, text="", fg=THEME.muted, bg=THEME.panel, font=self.UI_FONT, anchor="w")
        self.combat_message.pack(fill=tk.X, pady=(0, 5))
        self.combat_metrics = self._metric_grid(session, ("ELAPSED", "KILLS", "AX KILLS", "BOUNTIES", "BONDS", "DAMAGE EVENTS"))
        self.combat_detail = tk.Label(session, text="", fg=COLOR_TEXT, bg=THEME.panel, font=self.UI_MONO, justify=tk.LEFT, anchor="w")
        self.combat_detail.pack(fill=tk.X, pady=(8, 0))
        history = self._panel(self.combat_page, "RECENT COMBAT SESSIONS", "claims remain tracked until redemption")
        self.combat_history = self._tree(history, (("when", "Started", 145, "w"), ("kills", "Kills", 60, "e"), ("ax", "AX", 55, "e"), ("claims", "Claims", 110, "e"), ("damage", "Damage", 65, "e"), ("reason", "Ended", 80, "w")), 5)

    def _build_carrier(self):
        overview = self._panel(self.carrier_page, "CARRIER QUICK-LOOK", "journal status; detailed planning lives in Carrier Command")
        actions = tk.Frame(overview, bg=THEME.panel)
        actions.pack(fill=tk.X, pady=(0, 5))
        self.carrier_identity = tk.Label(actions, text="NO OWNER SNAPSHOT", fg=COLOR_ORANGE, bg=THEME.panel, font=self.UI_MONO_BOLD)
        self.carrier_identity.pack(side=tk.LEFT)
        button(actions, "OPEN FULL CARRIER", self.app.open_carrier_window, muted=True).pack(side=tk.RIGHT)
        self.carrier_message = tk.Label(overview, text="", fg=THEME.muted, bg=THEME.panel, font=self.UI_FONT, anchor="w")
        self.carrier_message.pack(fill=tk.X)
        self.carrier_metrics = self._metric_grid(overview, ("CARRIER BALANCE", "UPKEEP RESERVE", "TRITIUM TANK", "CARGO USED", "ROUTE PROGRESS", "BUY EXPOSURE"))

        route = self._panel(self.carrier_page, "EXPEDITION READINESS", "same saved route used by Carrier Command and the carrier overlay")
        self.carrier_route_result = tk.Label(
            route, text="No carrier expedition is currently saved.", fg=THEME.muted,
            bg=THEME.panel, font=self.UI_MONO, justify=tk.LEFT, anchor="w",
            wraplength=980,
        )
        self.carrier_route_result.pack(fill=tk.X)
        button(route, "PLAN / IMPORT / COPY WAYPOINTS", self.app.open_carrier_window, accent=True).pack(anchor="e", pady=(8, 0))

        orders = self._panel(self.carrier_page, "MARKET ORDERS", "latest owner-side CarrierTradeOrder observations")
        self.carrier_orders = self._tree(orders, (("commodity", "Commodity", 220, "w"), ("side", "Side", 70, "w"), ("quantity", "Quantity", 80, "e"), ("price", "Price", 110, "e"), ("exposure", "Exposure / stock", 140, "e")), 5)

    def _entry_row(self, parent, label, value=""):
        row = tk.Frame(parent, bg=THEME.panel)
        row.pack(fill=tk.X, padx=8, pady=3)
        tk.Label(row, text=label, fg=THEME.muted, bg=THEME.panel, font=("Segoe UI", 8), width=22, anchor="w").pack(side=tk.LEFT)
        entry = tk.Entry(row, bg=THEME.input, fg=COLOR_TEXT, insertbackground=COLOR_ACCENT, font=self.UI_MONO, relief=tk.FLAT)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        if value:
            entry.insert(0, value)
        return entry

    def _inline_entry(self, parent, label, value=""):
        box = tk.Frame(parent, bg=THEME.panel)
        box.pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(box, text=label, fg=THEME.muted, bg=THEME.panel, font=("Segoe UI", 8)).pack(side=tk.LEFT)
        entry = tk.Entry(box, width=10, bg=THEME.input, fg=COLOR_TEXT, insertbackground=COLOR_ACCENT, font=self.UI_MONO, relief=tk.FLAT)
        entry.pack(side=tk.LEFT, padx=(5, 0))
        if value:
            entry.insert(0, value)
        return entry

    def _build_exobio(self):
        current = self._panel(self.exobio_page, "EXOBIOLOGY OPERATIONS", "surface navigation stays in Void Compass's existing Ground tool")
        actions = tk.Frame(current, bg=THEME.panel)
        actions.pack(fill=tk.X)
        self.exobio_body = tk.Label(actions, text="NO SURFACE POSITION", fg=COLOR_ORANGE, bg=THEME.panel, font=self.UI_MONO_BOLD)
        self.exobio_body.pack(side=tk.LEFT)
        button(actions, "OPEN GROUND TOOL", self.app.open_ground_target_window, accent=True).pack(side=tk.RIGHT)
        button(actions, "OPEN EXPLORE", self.app.open_exploration_window, muted=True).pack(side=tk.RIGHT, padx=(0, 6))
        self.exobio_position = tk.Label(current, text="", fg=THEME.muted, bg=THEME.panel, font=self.UI_MONO, anchor="w")
        self.exobio_position.pack(fill=tk.X, pady=(7, 0))
        self.exobio_sampling = tk.Label(current, text="", fg=COLOR_TEXT, bg=THEME.panel, font=self.UI_MONO_BOLD, justify=tk.LEFT, anchor="w")
        self.exobio_sampling.pack(fill=tk.X, pady=(5, 0))

        pins = self._panel(self.exobio_page, "SURFACE PINS", "journal samples and manual positions can be sent to the Ground tool")
        form = tk.Frame(pins, bg=THEME.panel)
        form.pack(fill=tk.X, pady=(0, 7))
        self.pin_label = tk.Entry(form, bg=THEME.input, fg=COLOR_TEXT, insertbackground=COLOR_ACCENT, font=self.UI_MONO, relief=tk.FLAT)
        self.pin_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.pin_label.insert(0, "Return point")
        self.pin_kind = ttk.Combobox(form, values=("waypoint", "ship", "target", "hazard"), state="readonly", width=12, style="Specialists.TCombobox")
        self.pin_kind.set("waypoint")
        self.pin_kind.pack(side=tk.LEFT, padx=6)
        button(form, "PIN CURRENT POSITION", self._add_pin, accent=True).pack(side=tk.LEFT)
        button(form, "EXPORT GEOJSON", self._export_geojson).pack(side=tk.LEFT, padx=(6, 0))
        self.exobio_pins = self._tree(pins, (("label", "Pin", 240, "w"), ("kind", "Kind", 90, "w"), ("distance", "Distance", 85, "e"), ("bearing", "Bearing", 80, "e"), ("source", "Source", 100, "w")), 10)
        pin_actions = tk.Frame(pins, bg=THEME.panel)
        pin_actions.pack(fill=tk.X, pady=(7, 0))
        button(pin_actions, "SEND SELECTED TO GROUND", self._send_pin_to_ground, accent=True).pack(side=tk.LEFT)
        button(pin_actions, "REMOVE MANUAL PIN", self._remove_pin, muted=True).pack(side=tk.LEFT, padx=(6, 0))
        history = self._panel(self.exobio_page, "BODY RECORDS", "persistent per commander")
        self.exobio_surveys = self._tree(history, (("system", "System", 220, "w"), ("body", "Body", 250, "w"), ("pins", "Pins", 60, "e"), ("complete", "Analysed", 80, "e")), 6)

    # Actions --------------------------------------------------------
    def _start_mining(self):
        self.engine.start_mining({"system": self.app.current_sys, "body": self.app.current_body_name})
        self.refresh()

    def _end_mining(self):
        self.engine.end_mining()
        self.refresh()

    def _start_combat(self):
        self.engine.start_combat()
        self.refresh()

    def _end_combat(self):
        self.engine.end_combat()
        self.refresh()

    def _save_carrier_upkeep(self):
        try:
            self.engine.configure_carrier(self.carrier_weekly.get().strip(), self.carrier_target_weeks.get().strip())
            self.global_status.config(text="CARRIER UPKEEP INPUT SAVED LOCALLY", fg=COLOR_ACCENT)
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Carrier input", str(exc), parent=self.win)

    @staticmethod
    def _parse_inventory(text):
        rows = []
        for index, raw in enumerate(text.splitlines(), start=1):
            if not raw.strip():
                continue
            fields = [value.strip() for value in raw.replace("\t", "|").replace(",", "|").split("|")]
            if len(fields) < 2 or not fields[0]:
                raise ValueError(f"Inventory line {index}: use Commodity | tonnes")
            try:
                count = int(float(fields[-1]))
            except ValueError as exc:
                raise ValueError(f"Inventory line {index}: invalid tonnes") from exc
            if count < 0:
                raise ValueError(f"Inventory line {index}: tonnes cannot be negative")
            name = " | ".join(fields[:-1])
            rows.append({"name": name, "symbol": name.lower().replace(" ", "_"), "count": count})
        return rows

    def _save_carrier_inventory(self):
        try:
            rows = self._parse_inventory(self.carrier_inventory.get("1.0", tk.END))
            self.engine.set_carrier_inventory(rows)
            self.global_status.config(text="CARRIER INVENTORY SAVED LOCALLY", fg=COLOR_ACCENT)
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Carrier inventory", str(exc), parent=self.win)

    @staticmethod
    def _parse_route(text):
        rows = []
        for index, raw in enumerate(text.splitlines(), start=1):
            if not raw.strip():
                continue
            fields = [value.strip() for value in raw.replace("\t", "|").split("|")]
            if len(fields) < 2:
                raise ValueError(f"Route line {index}: use System | distance ly | optional tritium")
            try:
                distance = float(fields[1])
                fuel = float(fields[2]) if len(fields) > 2 and fields[2] else None
            except ValueError as exc:
                raise ValueError(f"Route line {index}: distance and tritium must be numeric") from exc
            rows.append({"system": fields[0], "distance_ly": distance, "tritium_t": fuel})
        return rows

    def _save_carrier_route(self):
        try:
            rows = self._parse_route(self.carrier_route.get("1.0", tk.END))
            per_jump = self.carrier_per_jump.get().strip()
            reserve = self.carrier_reserve.get().strip() or 0
            self.engine.plan_carrier_route(rows, None if not per_jump else float(per_jump), reserve)
            self.global_status.config(text="TRITIUM ROUTE RECALCULATED", fg=COLOR_ACCENT)
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Carrier route", str(exc), parent=self.win)

    def _add_pin(self):
        try:
            self.engine.add_pin(self.pin_label.get().strip() or "Return point", self.pin_kind.get())
            self.refresh()
        except Exception as exc:
            messagebox.showwarning("Surface pin", str(exc), parent=self.win)

    def _selected_pin(self):
        selection = self.exobio_pins.selection()
        if not selection:
            return None
        try:
            return self._pin_rows[self.exobio_pins.index(selection[0])]
        except (tk.TclError, ValueError, IndexError):
            return None

    def _send_pin_to_ground(self):
        pin = self._selected_pin()
        if not pin:
            messagebox.showinfo("Ground target", "Select a surface pin first.", parent=self.win)
            return
        if (self._current_exobio_position_body and self._current_exobio_map_body
                and str(self._current_exobio_position_body) != str(self._current_exobio_map_body)):
            messagebox.showwarning(
                "Ground target",
                f"This pin belongs to {self._current_exobio_map_body}. Return to that body before sending it to the Ground tool.",
                parent=self.win,
            )
            return
        self.app.target_lat = float(pin["lat"])
        self.app.target_lon = float(pin["lon"])
        self.app.target_latlon_active = True
        self.app.config.update({"ground_target_active": True, "ground_target_lat": self.app.target_lat, "ground_target_lon": self.app.target_lon})
        self.app._save_config_file()
        self.app.open_ground_target_window()
        for widget, value in ((getattr(self.app, "ground_lat_entry", None), self.app.target_lat), (getattr(self.app, "ground_lon_entry", None), self.app.target_lon)):
            if widget is not None:
                widget.delete(0, tk.END)
                widget.insert(0, f"{value:.6f}")
        self.app.update_ground_target_ui()

    def _remove_pin(self):
        pin = self._selected_pin()
        if not pin or pin.get("source") != "manual":
            messagebox.showinfo("Surface pin", "Only a selected manual pin can be removed.", parent=self.win)
            return
        self.engine.remove_pin(pin.get("id"))
        self.refresh()

    def _export_geojson(self):
        data = self.engine.geojson()
        if not data.get("features"):
            messagebox.showinfo("GeoJSON", "There are no pins on the current body to export.", parent=self.win)
            return
        body = (data.get("properties") or {}).get("body") or "surface-pins"
        safe = "".join(char if char.isalnum() or char in "-_" else "-" for char in str(body))
        path = filedialog.asksaveasfilename(parent=self.win, title="Export surface pins", initialfile=f"{safe}.geojson", defaultextension=".geojson", filetypes=(("GeoJSON", "*.geojson"), ("JSON", "*.json")))
        if not path:
            return
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        self.global_status.config(text=f"GEOJSON EXPORTED · {os.path.basename(path)}", fg=COLOR_ACCENT)

    # Rendering ------------------------------------------------------
    def refresh(self, section=None):
        if not self.is_open():
            return
        section = section or self._active_section()
        if section == "mining":
            self._render_mining(self.engine.mining_snapshot())
        elif section == "combat":
            self._render_combat(self.engine.combat_snapshot())
        elif section == "carrier":
            self._render_carrier(
                self.engine.carrier_snapshot(self.app.carrier_tracker.carrier_data)
            )
        elif section == "exobiology":
            self._render_exobio(self.engine.exobiology_snapshot())

    def _render_mining(self, mining):
        session = mining.get("session") or {}
        active = bool(mining.get("active"))
        self.mining_state.config(text="RUN ACTIVE" if active else "LAST RUN" if session else "IDLE", fg=COLOR_ACCENT if active else THEME.muted)
        self.mining_message.config(text=" · ".join(value for value in (session.get("system"), session.get("body")) if value) or "A run starts automatically when mining activity reaches the journal.")
        values = {"ELAPSED": _duration(session.get("duration_s")) if session else "—", "REFINED": _num(session.get("refined_t"), " t"), "YIELD RATE": _num(session.get("tons_per_hour"), " t/hr"), "PROSPECTED": _num(session.get("asteroids_prospected")), "CORE CRACKS": _num(session.get("asteroids_cracked")), "RUN REVENUE": _cr(session.get("attributed_revenue_cr")) if session else "—"}
        for key, value in values.items():
            self.mining_metrics[key].config(text=value)
        self._set_tree_rows(self.mining_yield, (
            (row.get("name"), _num(row.get("count"), " t"), _num(row.get("cargo_delta"), " t"), _num(row.get("sold_t"), " t"))
            for row in session.get("cargo_yield") or []
        ))
        self._set_tree_rows(self.mining_targets, (
            (row.get("name"), row.get("sightings"), _num(row.get("best_pct"), "%"), _num(row.get("average_pct"), "%"))
            for row in session.get("prospected_materials") or []
        ))
        limpets = session.get("limpets") or {}
        self.mining_limpets.config(text=f"Prospectors used: {_num(limpets.get('prospectors_used'))}    Collectors launched: {_num(limpets.get('collectors_launched'))}    Estimated used: {_num(limpets.get('estimated_used'))}    Remaining: {_num(limpets.get('remaining'))}\nCost / tonne: {_cr(limpets.get('cost_per_tonne_cr')) if limpets.get('cost_per_tonne_cr') is not None else '—'} ({limpets.get('cost_source') or 'purchase price not observed'})    Net after limpet cash: {_cr(session.get('net_after_limpet_cash_cr')) if session else '—'}")
        self._set_tree_rows(self.mining_history, (
            (self._stamp(row.get("started_ts")), row.get("system") or "—", _num(sum((item or {}).get("count", 0) for item in (row.get("refined") or {}).values()), " t"), row.get("asteroids_prospected", 0), _human(row.get("end_reason")))
            for row in mining.get("history") or []
        ))

    def _render_combat(self, combat):
        readiness = combat.get("readiness") or {}
        names = {"not_ax_equipped": "NO AX WEAPONS OBSERVED", "limited": "LIMITED AX TOOLING", "scout_or_support_ready": "SCOUT / SUPPORT TOOLING PRESENT", "interceptor_tooling_present": "INTERCEPTOR TOOLING PRESENT"}
        self.combat_level.config(text=names.get(readiness.get("level"), "NO LOADOUT OBSERVED"))
        self.combat_score.config(text=f"{readiness.get('score', 0)} / 100")
        labels = (("ax_weapons", "AX weapons"), ("heat_sinks", "Heat sinks"), ("xeno_scanners", "Xeno scanner"), ("flak", "Remote-release flak"), ("shutdown_neutralisers", "Shutdown neutraliser"), ("caustic_sinks", "Caustic sinks"), ("repair_or_decon", "Repair / decon limpets"), ("hull_reinforcement", "Hull reinforcement"), ("module_reinforcement", "Module reinforcement"))
        self.combat_checklist.config(text="    ".join(("✓" if readiness.get("checklist", {}).get(key) else "—") + " " + label for key, label in labels))
        self._set_tree_rows(self.combat_ammo, (
            (_human(row.get("item")), row.get("slot") or "—", row.get("clip", 0), row.get("hopper", 0), row.get("total", 0))
            for row in (readiness.get("ammo") or {}).get("by_module") or []
        ))
        session = combat.get("session") or {}
        active = bool(combat.get("active"))
        self.combat_state.config(text="SESSION ACTIVE" if active else "LAST SESSION" if session else "IDLE", fg=COLOR_ACCENT if active else THEME.muted)
        target = combat.get("target") or {}
        claims = max(0, session.get("bounty_cr", 0) + session.get("bond_cr", 0) - session.get("redeemed_cr", 0))
        self.combat_message.config(text=f"Target observation: {target.get('ship')}{' · THARGOID' if target.get('is_thargoid') else ''}" if target.get("ship") else f"{_cr(claims)} in session claims may still need redemption." if active else "A session starts automatically on a kill, attack, or damage event.")
        values = {"ELAPSED": _duration(session.get("duration_s")) if session else "—", "KILLS": _num(session.get("kills")), "AX KILLS": _num(session.get("ax_kills")), "BOUNTIES": _cr(session.get("bounty_cr")) if session else "—", "BONDS": _cr(session.get("bond_cr")) if session else "—", "DAMAGE EVENTS": _num(session.get("damage_events"))}
        for key, value in values.items():
            self.combat_metrics[key].config(text=value)
        ax = ", ".join(f"{_human(key)} ×{value}" for key, value in (session.get("ax_kills_by_type") or {}).items()) or "No AX kills in this session"
        synth = ", ".join(f"{_human(key)} ×{value}" for key, value in (session.get("synthesis") or {}).items()) or "No combat synthesis in this session"
        self.combat_detail.config(text=f"AX KILLS BY TYPE  //  {ax}\nSYNTHESIS USED   //  {synth}")
        self._set_tree_rows(self.combat_history, (
            (self._stamp(row.get("started_ts")), row.get("kills", 0), row.get("ax_kills", 0), _cr(row.get("bounty_cr", 0) + row.get("bond_cr", 0)), row.get("damage_events", 0), _human(row.get("end_reason")))
            for row in combat.get("history") or []
        ))

    def _render_carrier(self, workflow):
        cd, upkeep, route, orders = workflow.get("carrier") or {}, workflow.get("upkeep") or {}, workflow.get("route") or {}, workflow.get("orders") or {}
        observed = cd.get("carrier_id") is not None
        identity = cd.get("name") or "FLEET CARRIER"
        if cd.get("callsign"):
            identity += f" · {cd['callsign']}"
        self.carrier_identity.config(text=identity if observed else "NO OWNER SNAPSHOT")
        self.carrier_message.config(text=f"{cd.get('system') or 'Location not observed'} · {cd.get('body') or 'body not observed'} · {cd.get('docking_access') or 'access unknown'}" if observed else "Open Carrier Management in game to supply an authoritative status snapshot.")
        expedition = [row for row in cd.get("expedition_route") or [] if isinstance(row, dict)]
        visited = sum(1 for row in expedition if row.get("visited"))
        metrics = {"CARRIER BALANCE": _cr(cd.get("balance")) if cd.get("balance") is not None else "—", "UPKEEP RESERVE": _cr(cd.get("reserve_balance")) if cd.get("reserve_balance") is not None else "—", "TRITIUM TANK": _num(cd.get("fuel_level"), " t"), "CARGO USED": f"{_num(cd.get('space_cargo'))} / {_num(cd.get('space_total'))} t" if cd.get("space_total") is not None else "—", "ROUTE PROGRESS": f"{visited} / {len(expedition)}" if expedition else "NO ROUTE", "BUY EXPOSURE": _cr(orders.get("buy_order_exposure_cr"))}
        for key, value in metrics.items():
            self.carrier_metrics[key].config(text=value)
        remaining = max(0, len(expedition) - visited)
        fuel_required = cd.get("expedition_fuel_required_t")
        reserve = cd.get("expedition_reserve_fuel")
        route_name = cd.get("expedition_name") or "Carrier expedition"
        source = str(cd.get("expedition_route_source") or "manual").upper()
        if expedition:
            fuel_text = f" · {_num(fuel_required, ' t')} plotted fuel" if fuel_required is not None else " · fuel estimate pending"
            reserve_text = f" · {_num(reserve, ' t')} reserve" if reserve is not None else ""
            next_system = next((row.get("system") for row in expedition if not row.get("visited")), None)
            self.carrier_route_result.config(
                text=f"{route_name} · {visited}/{len(expedition)} complete · {remaining} remaining{fuel_text}{reserve_text}\n"
                     f"Next: {next_system or 'route complete'} · source {source}",
                fg=COLOR_ACCENT if not remaining else COLOR_TEXT,
            )
        else:
            self.carrier_route_result.config(
                text="No carrier expedition is currently saved. Open Carrier Command to plot with Spansh, import a result, or paste a route.",
                fg=THEME.muted,
            )
        order_rows = []
        for row in orders.get("items") or []:
            exposure = row.get("quantity", 0) * row.get("price_cr", 0) if row.get("side") == "buy" else row.get("quantity", 0)
            commodity = row.get("name") or "—"
            if row.get("black_market"):
                commodity += "  [BLACK MARKET]"
            order_rows.append((commodity, str(row.get("side") or "").upper(), _num(row.get("quantity"), " t"), _cr(row.get("price_cr")), _cr(exposure) if row.get("side") == "buy" else _num(exposure, " t stock")))
        self._set_tree_rows(self.carrier_orders, order_rows)

    def _render_exobio(self, workflow):
        position, current = workflow.get("position") or {}, workflow.get("current_map") or {}
        self._current_exobio_map_body = current.get("body")
        self._current_exobio_position_body = position.get("body")
        self.exobio_body.config(text=current.get("body") or position.get("body") or "NO SURFACE POSITION")
        self.exobio_position.config(text=f"{position.get('lat'):.5f}°, {position.get('lon'):.5f}°" + (f" · HDG {position.get('heading'):.0f}°" if position.get("heading") is not None else "") if position else "Latitude / longitude unavailable")
        sample = self.app._sampling_snapshot() or workflow.get("sampling")
        if sample:
            clearance = "CLEAR TO SAMPLE" if sample.get("clear") is True else f"MOVE {_num(sample.get('remaining_m'), ' m')} FARTHER" if sample.get("clear") is False else "CLEARANCE UNKNOWN"
            self.exobio_sampling.config(text=f"GENETIC SAMPLER  //  {sample.get('species') or sample.get('variant') or sample.get('genus') or 'Organism'}  ·  SAMPLE {sample.get('progress', 0)}/3  ·  {clearance}")
        else:
            self.exobio_sampling.config(text="GENETIC SAMPLER  //  NO ORGANISM IN PROGRESS")
        self._pin_rows = list(current.get("pins") or [])
        self._set_tree_rows(self.exobio_pins, (
            (row.get("label") or _human(row.get("kind")), _human(row.get("kind")), _num(row.get("distance_m"), " m"), _num(row.get("bearing_deg"), "°"), row.get("source") or "journal")
            for row in self._pin_rows
        ))
        self._set_tree_rows(self.exobio_surveys, (
            (row.get("system") or "—", row.get("body") or "—", row.get("pins", 0), row.get("completed", 0))
            for row in workflow.get("surveys") or []
        ))

    @staticmethod
    def _stamp(value):
        try:
            return __import__("datetime").datetime.fromtimestamp(float(value) / 1000).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError, OSError):
            return "—"
