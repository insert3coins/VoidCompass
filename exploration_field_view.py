"""Compact exploration field computer embedded in Route Intelligence."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from exploration_intelligence import build_intelligence
from ui_theme import THEME, button, configure_ttk, scrollbar


class ExplorationFieldView:
    def __init__(self, parent, app, on_change=None):
        self.parent = parent
        self.app = app
        self.on_change = on_change
        self._cell_rows = {}
        self._entry_widgets = []
        configure_ttk(parent, "FieldComputer")
        self._build()

    @staticmethod
    def _number(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _build(self):
        shell = tk.Frame(
            self.parent, bg=THEME.panel, highlightbackground=THEME.border,
            highlightthickness=1, bd=0,
        )
        shell.pack(fill=tk.X, pady=(0, 8))
        head = tk.Frame(shell, bg=THEME.panel)
        head.pack(fill=tk.X)
        tk.Label(
            head, text="EXPLORATION FIELD COMPUTER", fg=THEME.orange,
            bg=THEME.panel, font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.LEFT, padx=10, pady=8)
        self.summary = tk.Label(
            head, text="", fg=THEME.muted, bg=THEME.panel,
            font=("Cascadia Mono", 8), anchor="e",
        )
        self.summary.pack(side=tk.RIGHT, padx=10)

        cards = tk.Frame(shell, bg=THEME.bg)
        cards.pack(fill=tk.X, padx=7, pady=(0, 7))
        self.return_text = self._card(cards, "RETURN TO BASE", 0)
        self.endurance_text = self._card(cards, "ROUTE ENDURANCE", 1)

        return_row = tk.Frame(shell, bg=THEME.inset)
        return_row.pack(fill=tk.X, padx=7, pady=(0, 7))
        tk.Label(
            return_row, text="RETURN BASE", fg=THEME.muted, bg=THEME.inset,
            font=("Segoe UI", 7, "bold"),
        ).pack(side=tk.LEFT, padx=(8, 5), pady=7)
        self.return_system = tk.StringVar()
        self.return_entry = ttk.Entry(
            return_row, textvariable=self.return_system,
            style="FieldComputer.TEntry",
        )
        self.return_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=7)
        self._entry_widgets.append(self.return_entry)
        button(return_row, "SAVE", self._set_return_system, accent=True).pack(
            side=tk.LEFT, padx=7, pady=5,
        )

        sector = tk.Frame(shell, bg=THEME.inset)
        sector.pack(fill=tk.X, padx=7, pady=(0, 7))
        tk.Label(
            sector, text="EXPEDITION SECTOR SURVEY", fg=THEME.orange,
            bg=THEME.inset, font=("Segoe UI", 8, "bold"),
        ).grid(row=0, column=0, columnspan=9, sticky="w", padx=8, pady=(7, 4))
        self.sector_name = tk.StringVar(value="Expedition sector")
        self.sector_radius = tk.StringVar(value="500")
        self.sector_cell = tk.StringVar(value="100")
        for column, (title, variable, width) in enumerate((
            ("NAME", self.sector_name, 24), ("RADIUS LY", self.sector_radius, 9),
            ("CELL LY", self.sector_cell, 8),
        )):
            offset = column * 2
            tk.Label(
                sector, text=title, fg=THEME.muted, bg=THEME.inset,
                font=("Segoe UI", 7, "bold"),
            ).grid(row=1, column=offset, sticky="w", padx=(8, 3), pady=(0, 7))
            entry = ttk.Entry(
                sector, textvariable=variable, width=width,
                style="FieldComputer.TEntry",
            )
            entry.grid(row=1, column=offset + 1, sticky="ew", padx=(0, 8), pady=(0, 7))
            self._entry_widgets.append(entry)
        button(sector, "SET CURRENT", self._set_sector, accent=True).grid(row=1, column=6, padx=4, pady=(0, 7))
        button(sector, "CLEAR", self._clear_sector).grid(row=1, column=7, padx=4, pady=(0, 7))
        button(sector, "MAP", self._open_map).grid(row=1, column=8, padx=(4, 8), pady=(0, 7))
        sector.grid_columnconfigure(1, weight=1)

        tree_wrap = tk.Frame(shell, bg=THEME.bg)
        tree_wrap.pack(fill=tk.X, padx=7, pady=(0, 7))
        columns = ("cell", "state", "visits", "complete", "centre")
        self.sector_tree = ttk.Treeview(
            tree_wrap, columns=columns, show="headings", height=4,
            style="FieldComputer.Treeview",
        )
        for key, title, width, anchor in (
            ("cell", "Cell", 75, tk.CENTER), ("state", "Survey state", 115, tk.CENTER),
            ("visits", "Systems", 75, tk.CENTER), ("complete", "FSS complete", 90, tk.CENTER),
            ("centre", "Cell centre (X / Z)", 230, tk.W),
        ):
            self.sector_tree.heading(key, text=title)
            self.sector_tree.column(key, width=width, anchor=anchor)
        self.sector_tree.tag_configure("surveyed", foreground=THEME.green)
        self.sector_tree.tag_configure("incomplete", foreground=THEME.orange)
        self.sector_tree.tag_configure("untouched", foreground=THEME.dim)
        bar = scrollbar(tree_wrap, orient=tk.VERTICAL, command=self.sector_tree.yview)
        self.sector_tree.configure(yscrollcommand=bar.set)
        self.sector_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        bar.pack(side=tk.RIGHT, fill=tk.Y)

    def _card(self, parent, title, column):
        frame = tk.Frame(
            parent, bg=THEME.inset, highlightbackground=THEME.border,
            highlightthickness=1,
        )
        frame.grid(row=0, column=column, sticky="nsew", padx=(0, 4) if column == 0 else (4, 0))
        parent.grid_columnconfigure(column, weight=1, uniform="field-card")
        tk.Label(
            frame, text=title, fg=THEME.orange, bg=THEME.inset,
            font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=9, pady=(7, 2))
        label = tk.Label(
            frame, text="Awaiting route evidence", fg=THEME.text,
            bg=THEME.inset, font=("Cascadia Mono", 8), anchor="nw",
            justify=tk.LEFT, wraplength=500,
        )
        label.pack(fill=tk.X, padx=9, pady=(0, 8))
        return label

    def _intelligence(self):
        getter = getattr(self.app, "_exploration_intelligence_snapshot", None)
        try:
            snapshot = getter() if callable(getter) else None
        except Exception:
            snapshot = None
        if not isinstance(snapshot, dict) or "return_plan" not in snapshot:
            try:
                snapshot = build_intelligence(self.app)
            except Exception:
                snapshot = {}
        return snapshot or {}

    def refresh(self):
        intelligence = self._intelligence()
        field = intelligence.get("field") or intelligence
        return_plan = field.get("return_plan") or {}
        endurance = field.get("endurance") or {}
        sector = field.get("sector") or {}

        target = return_plan.get("target_system") or "No return base selected"
        editing = self.parent.focus_get() in self._entry_widgets
        if not editing:
            self.return_system.set(return_plan.get("target_system") or "")
        distance = return_plan.get("distance_ly")
        jumps = return_plan.get("jumps")
        eta = return_plan.get("eta_minutes")
        route_line = "Route unavailable"
        if distance is not None:
            route_line = f"{distance:,.1f} ly · {jumps if jumps is not None else '?'} jumps · {eta if eta is not None else '?'} min"
        minimum = int(return_plan.get("unsold_min_cr") or 0)
        maximum = int(return_plan.get("unsold_max_cr") or minimum)
        cargo = f"{minimum:,} cr" if maximum <= minimum else f"{minimum:,}-{maximum:,} cr"
        services = str(return_plan.get("service_text") or "Services unverified")
        issues = "; ".join(return_plan.get("issues") or []) or "No verified return warnings"
        self.return_text.config(text=f"{target}\n{route_line}\nUnsold data {cargo}\n{services}\n{issues}")

        route = endurance.get("route") or {}
        fuel_line = str(route.get("headline") or "Fuel projection unavailable")
        afmu = (
            str(endurance.get("afmu_ammo")) if endurance.get("afmu_ammo") is not None
            else "INSTALLED / AMMO ?" if endurance.get("afmu_installed")
            else "NO" if endurance.get("afmu_installed") is False else "?"
        )
        sinks = (
            str(endurance.get("heat_sinks")) if endurance.get("heat_sinks") is not None
            else "INSTALLED / AMMO ?" if endurance.get("heat_sink_installed")
            else "NO" if endurance.get("heat_sink_installed") is False else "?"
        )
        hardware_line = " · ".join((
            f"HULL {endurance.get('hull_percent') if endurance.get('hull_percent') is not None else '?'}%",
            f"FSD {endurance.get('fsd_health_percent') if endurance.get('fsd_health_percent') is not None else '?'}%",
            f"AFMU {afmu}",
            f"SINKS {sinks}",
            f"SRV {'YES' if endurance.get('srv_available') else 'NO' if endurance.get('srv_available') is False else '?'}",
        ))
        injections = endurance.get("injections") or {}
        reserve_line = "Jumponium " + (
            ", ".join(f"{key.title()} {value}" for key, value in injections.items())
            or "not journalled"
        )
        self.endurance_text.config(text=f"{fuel_line}\n{hardware_line}\n{reserve_line}")

        cells = list(sector.get("cells") or [])
        counts = sector.get("counts") or {}
        self.summary.config(text=(
            f"SIGNIFICANCE {int((field.get('significance') or {}).get('score') or 0):02d} · "
            f"SECTOR {int(counts.get('surveyed') or 0)}/{len(cells)}"
        ))
        plan = sector.get("plan") or {}
        if plan and not editing:
            self.sector_name.set(str(plan.get("name") or "Expedition sector"))
            self.sector_radius.set(f"{self._number(plan.get('radius_ly'), 500):g}")
            self.sector_cell.set(f"{self._number(plan.get('cell_size_ly'), 100):g}")
        children = self.sector_tree.get_children()
        if children:
            self.sector_tree.delete(*children)
        visible = [cell for cell in cells if cell.get("status") != "untouched"]
        if len(visible) < 30:
            visible.extend(cell for cell in cells if cell.get("status") == "untouched")
        for cell in visible[:80]:
            centre = cell.get("position") or (0, 0, 0)
            state = str(cell.get("status") or "untouched")
            self.sector_tree.insert("", tk.END, values=(
                cell.get("id") or "-", state.title(), int(cell.get("visited_systems") or 0),
                int(cell.get("surveyed_systems") or 0), f"{centre[0]:,.0f} / {centre[2]:,.0f}",
            ), tags=(state,))
        if not cells:
            self.sector_tree.insert("", tk.END, values=(
                "-", "No active sector", "-", "-", "Set the sector from your current system",
            ))

    def _selected_expedition(self):
        manager = getattr(self.app, "expedition_manager", None)
        return manager.active() if manager else None

    def _set_sector(self):
        expedition = self._selected_expedition()
        coords = getattr(self.app, "current_coords", None)
        if not expedition or not isinstance(coords, (list, tuple)) or len(coords) < 3:
            messagebox.showinfo(
                "Expedition Sector", "Start an expedition and arrive in a system with known coordinates first.",
                parent=self.parent,
            )
            return
        try:
            self.app.expedition_manager.set_sector_plan(
                expedition["id"], coords, self.sector_radius.get(), self.sector_cell.get(),
                self.sector_name.get(),
            )
        except (TypeError, ValueError) as exc:
            messagebox.showerror("Expedition Sector", str(exc), parent=self.parent)
            return
        self._changed()

    def _set_return_system(self):
        expedition = self._selected_expedition()
        if not expedition:
            messagebox.showinfo(
                "Return Base", "Start or activate an expedition first.", parent=self.parent,
            )
            return
        self.app.expedition_manager.set_return_system(
            expedition["id"], self.return_system.get(),
        )
        self._changed()

    def _clear_sector(self):
        expedition = self._selected_expedition()
        if expedition:
            self.app.expedition_manager.clear_sector_plan(expedition["id"])
            self._changed()

    def _changed(self):
        invalidate = getattr(self.app, "_invalidate_exploration_intelligence", None)
        if callable(invalidate):
            invalidate()
        self.refresh()
        if callable(self.on_change):
            self.on_change()

    def _open_map(self):
        opener = getattr(self.app, "open_galaxy_map_page", None)
        if callable(opener):
            opener()
