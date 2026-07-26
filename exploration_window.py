import json
import math
import os
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import requests

import bio_values
from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT
from deep_survey import (
    architecture_rows, expedition_report_markdown, recon_report, survey_plan,
    wonder_rows,
)
from discoveries_view import DiscoveriesView
from expedition_map_view import ExpeditionMapView
from expedition_mission_view import ExpeditionMissionView
from route_plotter import RoutePlotter
from stellar_types import star_type_label
from ui_theme import THEME, ThemedWindowMixin, apply_window, button, configure_ttk, scrollbar, window_surface

COLOR_ACCENT = THEME.accent
COLOR_ORANGE = THEME.orange
COLOR_TEXT = THEME.text


SCOOPABLE_STAR_CLASSES = {"O", "B", "A", "F", "G", "K", "M"}


class ExplorationWindow(ThemedWindowMixin):

    def __init__(self, root, app, embedded=False):
        self.root = root
        self.app = app
        self.config = app.config
        self.body_items_by_iid = {}
        self._last_survey_bodies = []
        self._survey_plan_by_key = {}
        self._edsm_cache = self._load_edsm_cache()
        self._edsm_pending = set()
        self._edsm_lock = threading.Lock()
        self._edsm_worker_active = False
        self._edsm_last_request_ts = 0.0
        self._last_session_stats = {"systems": 0, "bodies": 0, "value": 0, "valuable": 0}
        self._last_db_stats = {"systems": 0, "visits": 0, "bodies": 0, "value": 0, "valuable": 0}
        self._last_route_status = {}
        self._last_ledger_refresh_ts = 0.0
        self.system_history_rows = []
        self.ledger_rows = []
        self._last_history_refresh_ts = 0.0
        self._closing = False
        self._restoring_view_state = False
        self.route_plotter = None
        self.discoveries_view = None
        self.expedition_map_view = None
        self.expedition_mission_view = None
        self._map_focus_host = None
        self._map_focus_bind_target = None
        self._map_focus_escape_binding = None
        self._map_split = None
        self._map_host = None
        self._map_intelligence_host = None
        self.embedded = embedded
        self.win = window_surface(root, embedded=embedded)
        self.win.title("Exploration")
        self.win.geometry(self.config.get("exploration_window_geometry", "1040x680"))
        apply_window(self.win)
        self.win.minsize(860, 520)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self.refresh()

    def is_open(self):
        try:
            return bool(not self._closing and self.win and self.win.winfo_exists())
        except Exception:
            return False

    def lift(self):
        if not self.is_open():
            return
        self.win.lift()
        self.win.focus_force()

    @staticmethod
    def _widget_alive(widget):
        try:
            return bool(widget and widget.winfo_exists())
        except Exception:
            return False

    def _build(self):
        header = tk.Frame(self.win, bg="#0c1014", height=76)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        title_box = tk.Frame(header, bg="#0c1014")
        title_box.pack(side=tk.LEFT, fill=tk.Y, padx=14)
        tk.Label(
            title_box,
            text="EXPLORATION & ROUTES",
            font=("Segoe UI", 16, "bold"),
            fg=COLOR_ACCENT,
            bg="#0c1014",
            anchor="w",
        ).pack(anchor="w", pady=(12, 0))
        self.header_subtitle = tk.Label(
            title_box,
            text="System survey, expedition, discoveries and logbook",
            font=("Consolas", 8),
            fg=self.UI_MUTED,
            bg="#0c1014",
            anchor="w",
        )
        self.header_subtitle.pack(anchor="w", pady=(2, 0))

        self.header_summary = tk.Label(
            header,
            text="",
            font=("Consolas", 9, "bold"),
            fg=COLOR_TEXT,
            bg="#0c1014",
            justify=tk.RIGHT,
        )
        self.header_summary.pack(side=tk.RIGHT, padx=14)

        toolbar = tk.Frame(self.win, bg="#10151a")
        toolbar.pack(fill=tk.X, padx=10, pady=(10, 8))
        self._button(toolbar, "Refresh", self.refresh).pack(side=tk.LEFT)
        self._button(toolbar, "Copy Summary", self._copy_summary, accent=True).pack(side=tk.LEFT, padx=(8, 0))
        self._button(toolbar, "Copy Next Route", self._copy_next_route).pack(side=tk.LEFT, padx=(8, 0))
        self._button(toolbar, "Route Planner", self.show_route_planning).pack(side=tk.LEFT, padx=(8, 0))
        open_galaxy = getattr(self.app, "open_bgs_window", None)
        if callable(open_galaxy):
            self._button(toolbar, "Galaxy", open_galaxy).pack(side=tk.LEFT, padx=(8, 0))
        self._button(toolbar, "Open EDSM", self._open_current_edsm).pack(side=tk.LEFT, padx=(8, 0))
        self._button(toolbar, "Reset Session", self._reset_session).pack(side=tk.RIGHT)

        summary = tk.Frame(self.win, bg=self.UI_BG)
        summary.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.system_card = self._summary_card(summary, "SYSTEM", accent=COLOR_ACCENT)
        self.scan_card = self._summary_card(summary, "SCAN VALUE", accent=self.UI_OK)
        self.route_card = self._summary_card(summary, "ROUTE", accent=COLOR_ORANGE)
        self.bio_card = self._summary_card(summary, "BIO SIGNALS", accent="#86efac")
        self.trip_card = self._summary_card(summary, "SESSION", accent="#a5b4fc")
        self._build_expedition_strip()

        style = configure_ttk(self.win, "Explore")
        style.configure("Explore.TNotebook", background=self.UI_BG, borderwidth=0)
        style.configure("Explore.TNotebook.Tab", background=self.UI_PANEL, foreground=COLOR_TEXT, padding=(12, 7), borderwidth=0)
        style.map("Explore.TNotebook.Tab", background=[("selected", self.UI_PANEL_2)], foreground=[("selected", COLOR_ACCENT)])
        style.configure("Explore.Section.TNotebook", background=self.UI_BG, borderwidth=0)
        style.configure("Explore.Section.TNotebook.Tab", background=self.UI_PANEL_2, foreground=self.UI_MUTED, padding=(11, 6), borderwidth=0)
        style.map("Explore.Section.TNotebook.Tab", background=[("selected", "#0b0f13")], foreground=[("selected", COLOR_ORANGE)])
        style.configure("Explore.Treeview", background="#0b0f13", foreground=COLOR_TEXT, fieldbackground="#0b0f13", rowheight=24, borderwidth=0)
        style.configure("Explore.Treeview.Heading", background=self.UI_PANEL, foreground=COLOR_ORANGE, relief="flat", font=("Segoe UI", 8, "bold"))
        style.map("Explore.Treeview", background=[("selected", "#12313c")], foreground=[("selected", COLOR_TEXT)])

        self.tabs = ttk.Notebook(self.win, style="Explore.TNotebook")
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.survey_workspace = tk.Frame(self.tabs, bg=self.UI_BG)
        self.expedition_workspace = tk.Frame(self.tabs, bg=self.UI_BG)
        self.discoveries_workspace = tk.Frame(self.tabs, bg=self.UI_BG)
        self.logbook_workspace = tk.Frame(self.tabs, bg=self.UI_BG)
        # Compatibility aliases for route callbacks and older direct links.
        self.route_workspace = self.expedition_workspace
        self.chronicle_workspace = self.logbook_workspace
        self.tabs.add(self.survey_workspace, text="System Survey")
        self.tabs.add(self.expedition_workspace, text="Expedition")
        self.tabs.add(self.discoveries_workspace, text="Discoveries")
        self.tabs.add(self.logbook_workspace, text="Logbook")

        self._build_bodies_tab()
        self._build_route_workspace()
        self.discoveries_view = DiscoveriesView(
            self.discoveries_workspace,
            self.app,
            initial_filter=self.config.get("explore_discovery_filter", "All"),
            on_filter_change=self._on_discovery_filter_changed,
            bookmark_callback=self._bookmark_discovery,
        )
        self._build_logbook_workspace()
        self.tabs.bind("<<NotebookTabChanged>>", self._on_workspace_changed)
        self._restore_view_state()

    def _build_route_workspace(self):
        """Host the existing route engine inside the unified Explore page."""
        self.route_plotter = RoutePlotter(
            self.route_workspace,
            self.app.edsm,
            self.app.current_coords,
            self.app.current_sys,
            self.config,
            self.app.waypoint_manager,
            on_change_callback=self.app.update_waypoint_display,
            event_callback=self.app._on_route_event,
            embedded=True,
            navigation_state_callback=self.app._route_panel_navigation_state,
            copy_waypoint_callback=self.app._copy_waypoint_to_clipboard,
            is_active_callback=self.is_route_active,
            compact=True,
            flat_navigation=True,
            section_change_callback=self._on_expedition_section_changed,
            persist_config_callback=getattr(self.app, "_persist_config", None),
        )
        self.route_plotter.win.pack(fill=tk.BOTH, expand=True)
        self.app.route_plotter = self.route_plotter
        mission_section = self.route_plotter.add_section("Mission Control")
        self.expedition_mission_view = ExpeditionMissionView(
            mission_section, self.app,
            on_change=self._on_expedition_changed,
            copy_report_callback=self._copy_named_expedition_report,
        )
        map_section = self.route_plotter.add_section("Map & Intelligence")
        split = tk.PanedWindow(
            map_section, orient=tk.VERTICAL, bg=self.UI_BG,
            sashwidth=6, sashrelief=tk.FLAT, bd=0,
        )
        split.pack(fill=tk.BOTH, expand=True)
        map_host = tk.Frame(split, bg=self.UI_BG)
        intelligence_host = tk.Frame(split, bg=self.UI_BG)
        self._map_split = split
        self._map_host = map_host
        self._map_intelligence_host = intelligence_host
        split.add(map_host, minsize=380)
        split.add(intelligence_host, minsize=165)
        self.expedition_map_view = ExpeditionMapView(
            map_host, self.app, open_record_callback=self._open_map_record,
            popout_callback=self._toggle_map_popout,
        )
        self._build_route_tab(intelligence_host, embedded=True)

    def _on_workspace_changed(self, _event=None):
        self._remember_active_page()
        if self.is_route_active() and self.route_plotter:
            self.route_plotter.on_shown()
        try:
            selected = self.tabs.select()
            if selected == str(self.discoveries_workspace) and self.discoveries_view:
                self.discoveries_view.refresh(self.system_history_rows, self.ledger_rows)
            elif selected == str(self.expedition_workspace) and self.expedition_map_view:
                section = self.route_plotter.current_section() if self.route_plotter else ""
                if section == "Map & Intelligence":
                    self._refresh_visible_map()
                if section == "Mission Control" and self.expedition_mission_view:
                    self.expedition_mission_view.refresh()
        except Exception:
            pass

    def _save_view_setting(self, key, value):
        if self._restoring_view_state or self.config.get(key) == value:
            return
        self.config[key] = value
        try:
            persist = getattr(self.app, "_persist_config", None)
            if callable(persist):
                persist()
        except Exception:
            pass

    def _remember_active_page(self):
        try:
            selected = self.tabs.select()
        except Exception:
            return
        labels = {
            str(self.survey_workspace): "System Survey",
            str(self.expedition_workspace): "Expedition",
            str(self.discoveries_workspace): "Discoveries",
            str(self.logbook_workspace): "Logbook",
        }
        if selected in labels:
            self._save_view_setting("explore_active_page", labels[selected])

    def _on_survey_filter_changed(self, _event=None):
        self._save_view_setting("explore_survey_filter", self.survey_filter_var.get())
        self._render_bodies(self._last_survey_bodies)

    def _on_discovery_filter_changed(self, value):
        self._save_view_setting("explore_discovery_filter", value)

    def _on_expedition_section_changed(self, value):
        self._save_view_setting("explore_expedition_section", value)
        if (
            value == "Map & Intelligence" and self.expedition_map_view
            and not self._map_popout_is_open()
        ):
            self.expedition_map_view.refresh(self.system_history_rows, self.ledger_rows)

    def _map_popout_is_open(self):
        return self._widget_alive(self._map_focus_host)

    def _toggle_map_popout(self):
        if self._map_popout_is_open():
            self._dock_map_popout()
        else:
            self._open_map_popout()

    def _open_map_popout(self):
        if self._map_popout_is_open():
            self._map_focus_host.lift()
            return
        state = self.expedition_map_view.view_state() if self.expedition_map_view else None
        target = getattr(self.app, "root", None)
        if not self._widget_alive(target):
            target = self.win.winfo_toplevel()
        focus_host = tk.Frame(target, bg=self.UI_BG, bd=0, highlightthickness=0)
        focus_host.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        focus_host.lift()
        self._map_focus_host = focus_host
        self._map_focus_bind_target = target
        self._map_focus_escape_binding = target.bind(
            "<Escape>", lambda _event: self._dock_map_popout(), add="+",
        )
        try:
            focus_view = ExpeditionMapView(
                focus_host, self.app,
                open_record_callback=self._open_map_record,
                popout_callback=self._toggle_map_popout,
                focus_mode=True,
            )
            focus_view.refresh(self.system_history_rows, self.ledger_rows)
            focus_view.apply_view_state(state)
        except Exception:
            self._remove_map_focus_host()
            raise
        old_view = self.expedition_map_view
        if old_view:
            old_view.dispose()
        if self._widget_alive(self._map_host):
            for child in self._map_host.winfo_children():
                child.destroy()
        self.expedition_map_view = focus_view
        focus_host.lift()

    def _dock_map_popout(self, sync=True):
        if not self._map_popout_is_open():
            return
        focus_view = self.expedition_map_view
        state = focus_view.view_state() if focus_view else None
        if sync and self._widget_alive(self._map_host):
            try:
                embedded_view = ExpeditionMapView(
                    self._map_host, self.app,
                    open_record_callback=self._open_map_record,
                    popout_callback=self._toggle_map_popout,
                )
                embedded_view.refresh(self.system_history_rows, self.ledger_rows)
                embedded_view.apply_view_state(state)
            except Exception as exc:
                for child in self._map_host.winfo_children():
                    child.destroy()
                self._log_error(f"Could not restore embedded galaxy map: {exc}")
                return
        else:
            embedded_view = None
        if focus_view:
            focus_view.dispose()
        self._remove_map_focus_host()
        self.expedition_map_view = embedded_view

    def _remove_map_focus_host(self):
        target = self._map_focus_bind_target
        binding = self._map_focus_escape_binding
        if target is not None and binding:
            try:
                target.unbind("<Escape>", binding)
            except tk.TclError:
                pass
        focus_host = self._map_focus_host
        self._map_focus_host = None
        self._map_focus_bind_target = None
        self._map_focus_escape_binding = None
        try:
            if focus_host and focus_host.winfo_exists():
                focus_host.destroy()
        except tk.TclError:
            pass

    def _refresh_visible_map(self):
        if self._map_popout_is_open() and self.expedition_map_view:
            self.expedition_map_view.refresh(self.system_history_rows, self.ledger_rows)
            return
        if (
            self.expedition_map_view and self.is_route_active()
            and self.route_plotter
            and self.route_plotter.current_section() == "Map & Intelligence"
        ):
            self.expedition_map_view.refresh(self.system_history_rows, self.ledger_rows)

    def _restore_view_state(self):
        self._restoring_view_state = True
        try:
            page = str(self.config.get("explore_active_page") or "System Survey")
            page_frame = {
                "System Survey": self.survey_workspace,
                "Expedition": self.expedition_workspace,
                "Discoveries": self.discoveries_workspace,
                "Logbook": self.logbook_workspace,
            }.get(page, self.survey_workspace)
            self.tabs.select(page_frame)
            survey_filter = str(self.config.get("explore_survey_filter") or "All bodies")
            if survey_filter in ("All bodies", "Actionable", "Biology", "Geology", "Valuable"):
                self.survey_filter_var.set(survey_filter)
            if self.discoveries_view:
                self.discoveries_view.set_filter(
                    str(self.config.get("explore_discovery_filter") or "All"),
                    notify=False,
                )
            if self.route_plotter:
                self.route_plotter.show_flat_section(
                    str(self.config.get("explore_expedition_section") or "Overview")
                )
        finally:
            self._restoring_view_state = False

    def is_route_active(self):
        try:
            return bool(
                getattr(self.app, "_active_page", None) == "EXPLORE"
                and self.tabs.select() == str(self.route_workspace)
            )
        except Exception:
            return False

    def show_section(self, section=None):
        section = str(section or "survey").strip().casefold()
        target = {
            "survey": self.survey_workspace,
            "system survey": self.survey_workspace,
            "current system": self.survey_workspace,
            "biology": self.survey_workspace,
            "planner": self.survey_workspace,
            "architecture": self.survey_workspace,
            "recon": self.survey_workspace,
            "deep": self.survey_workspace,
            "deep survey": self.survey_workspace,
            "route": self.expedition_workspace,
            "route planning": self.expedition_workspace,
            "expedition": self.expedition_workspace,
            "mission": self.expedition_workspace,
            "mission control": self.expedition_workspace,
            "objectives": self.expedition_workspace,
            "bookmarks": self.expedition_workspace,
            "waypoints": self.expedition_workspace,
            "neutron": self.expedition_workspace,
            "map": self.expedition_workspace,
            "discoveries": self.discoveries_workspace,
            "research": self.discoveries_workspace,
            "atlas": self.discoveries_workspace,
            "history": self.discoveries_workspace,
            "ledger": self.discoveries_workspace,
            "chronicle": self.logbook_workspace,
            "logbook": self.logbook_workspace,
        }.get(section, self.survey_workspace)
        self.tabs.select(target)
        self._remember_active_page()
        if target is self.expedition_workspace and self.route_plotter:
            self.route_plotter.on_shown()
            section_name = {
                "route": "Overview", "route planning": "Overview",
                "waypoints": "Waypoints", "neutron": "Neutron",
                "mission": "Mission Control", "mission control": "Mission Control",
                "objectives": "Mission Control", "bookmarks": "Mission Control",
                "map": "Map & Intelligence",
            }.get(section)
            if section_name and hasattr(self.route_plotter, "show_flat_section"):
                self.route_plotter.show_flat_section(section_name)
        elif target is self.discoveries_workspace and self.discoveries_view:
            filter_name = {"research": "All", "atlas": "Photos", "history": "Systems", "ledger": "Valuable"}.get(section)
            if filter_name:
                self.discoveries_view.set_filter(filter_name)
            self.discoveries_view.refresh(self.system_history_rows, self.ledger_rows)

    def show_route_planning(self):
        self.show_section("route")

    def on_shown(self, section=None):
        if section:
            self.show_section(section)
        self.refresh()
        if self.is_route_active() and self.route_plotter:
            self.route_plotter.on_shown()

    def _summary_card(self, parent, title, accent=None):
        accent = accent or COLOR_ACCENT
        card = tk.Frame(parent, bg=self.UI_PANEL, highlightbackground=self.UI_BORDER, highlightthickness=1, bd=0)
        card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Frame(card, bg=accent, height=2).pack(fill=tk.X)
        tk.Label(card, text=title, fg=COLOR_ORANGE, bg=self.UI_PANEL, font=("Segoe UI", 8, "bold"), anchor="w").pack(fill=tk.X, padx=10, pady=(8, 0))
        value = tk.Label(card, text="-", fg=COLOR_TEXT, bg=self.UI_PANEL, font=("Consolas", 10, "bold"), anchor="w", justify=tk.LEFT, height=2)
        value.pack(fill=tk.X, padx=10, pady=(3, 8))
        return value

    def _build_expedition_strip(self):
        self.expedition_strip = tk.Frame(
            self.win, bg=self.UI_PANEL, highlightbackground=self.UI_BORDER,
            highlightthickness=1, bd=0,
        )
        self.expedition_strip.pack(fill=tk.X, padx=10, pady=(0, 8))
        tk.Frame(self.expedition_strip, bg=COLOR_ORANGE, width=3).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(
            self.expedition_strip, text="MISSION CONTROL", fg=COLOR_ORANGE,
            bg=self.UI_PANEL, font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.LEFT, padx=(10, 8), pady=8)
        self.expedition_strip_text = tk.Label(
            self.expedition_strip, text="No active expedition", fg=COLOR_TEXT,
            bg=self.UI_PANEL, font=("Consolas", 9, "bold"), anchor="w",
        )
        self.expedition_strip_text.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=8)
        self.expedition_strip_status_btn = self._button(
            self.expedition_strip, "PAUSE", self._toggle_active_expedition,
        )
        self.expedition_strip_status_btn.pack(side=tk.RIGHT, padx=(0, 8), pady=5)
        self._button(
            self.expedition_strip, "OPEN", lambda: self.show_section("mission"), accent=True,
        ).pack(side=tk.RIGHT, padx=(0, 7), pady=5)

    def _refresh_expedition_strip(self):
        manager = getattr(self.app, "expedition_manager", None)
        expedition = manager.active() if manager else None
        if not expedition:
            self.expedition_strip_text.config(
                text="No active expedition · open Mission Control to create or resume one",
                fg=self.UI_MUTED,
            )
            self.expedition_strip_status_btn.config(text="PAUSE", state=tk.DISABLED)
            return
        complete, total = manager.progress(expedition)
        pending = next((
            row for row in expedition.get("objectives") or []
            if row.get("status") != "complete"
        ), None)
        stats = expedition.get("stats") or {}
        next_text = pending.get("title") if pending else "All objectives complete"
        self.expedition_strip_text.config(
            text=(
                f"{expedition.get('name')} · {complete}/{total} goals · "
                f"{len(stats.get('systems') or []):,} systems / "
                f"{float(stats.get('distance_ly') or 0):,.1f} ly · NEXT: {next_text}"
            ),
            fg=COLOR_TEXT,
        )
        self.expedition_strip_status_btn.config(text="PAUSE", state=tk.NORMAL)

    def _toggle_active_expedition(self):
        manager = getattr(self.app, "expedition_manager", None)
        expedition = manager.active() if manager else None
        if expedition:
            manager.set_status(expedition["id"], "paused")
            self._on_expedition_changed()

    def _on_expedition_changed(self):
        self._refresh_expedition_strip()
        if self.expedition_mission_view:
            self.expedition_mission_view.refresh()
        self._refresh_visible_map()
        try:
            self.app.schedule_dashboard_refresh()
        except Exception:
            pass

    def _build_bodies_tab(self):
        frame = self.survey_workspace
        left = tk.Frame(frame, bg=self.UI_BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = tk.Frame(frame, bg=self.UI_PANEL, highlightbackground=self.UI_BORDER, highlightthickness=1, bd=0, width=300)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        right.pack_propagate(False)

        system_bar = tk.Frame(left, bg="#0b0f13", highlightbackground=self.UI_BORDER, highlightthickness=1, bd=0)
        system_bar.pack(fill=tk.X, pady=(0, 8))
        self.body_metric_labels = {}
        for key, title in (
            ("status", "CURRENT SYSTEM"),
            ("bodies", "DISCOVERED BODIES"),
            ("signals", "SIGNALS"),
            ("value", "EST. VALUE"),
            ("activity", "CURRENT ACTIVITY"),
        ):
            cell = tk.Frame(system_bar, bg="#0b0f13")
            cell.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=7)
            tk.Label(cell, text=title, fg=COLOR_ORANGE, bg="#0b0f13", font=("Segoe UI", 7, "bold"), anchor="w").pack(fill=tk.X)
            lbl = tk.Label(cell, text="-", fg=COLOR_ACCENT, bg="#0b0f13", font=("Consolas", 9, "bold"), anchor="w", justify=tk.LEFT)
            lbl.pack(fill=tk.X, pady=(2, 0))
            self.body_metric_labels[key] = lbl

        legend = tk.Frame(left, bg=self.UI_BG)
        legend.pack(fill=tk.X, pady=(0, 6))
        tk.Label(
            legend, text="VIEW", fg=self.UI_MUTED, bg=self.UI_BG,
            font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 6))
        initial_filter = str(self.config.get("explore_survey_filter") or "All bodies")
        if initial_filter not in ("All bodies", "Actionable", "Biology", "Geology", "Valuable"):
            initial_filter = "All bodies"
        self.survey_filter_var = tk.StringVar(value=initial_filter)
        survey_filter = ttk.Combobox(
            legend, textvariable=self.survey_filter_var, state="readonly", width=15,
            values=("All bodies", "Actionable", "Biology", "Geology", "Valuable"),
            style="Explore.TCombobox",
        )
        survey_filter.pack(side=tk.LEFT, padx=(0, 18))
        survey_filter.bind("<<ComboboxSelected>>", self._on_survey_filter_changed)
        for text, fg in (
            ("High value", COLOR_ACCENT),
            ("Bio/organic", self.UI_OK),
            ("Star", self.UI_MUTED),
            ("Mapped/DSS", COLOR_ORANGE),
        ):
            tk.Label(legend, text=text, fg=fg, bg=self.UI_BG, font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 14))

        self.sampling_banner = tk.Label(
            left, text="", fg=COLOR_TEXT, bg="#0b0f13", font=("Consolas", 10, "bold"),
            anchor="w", padx=12, pady=9, highlightbackground=self.UI_BORDER,
            highlightthickness=1,
        )
        self.sampling_banner.pack(fill=tk.X, pady=(0, 8))
        self.sampling_banner.pack_forget()

        cols = ("body", "type", "action", "priority", "value", "signals", "discover", "distance")
        self.bodies_tree = self._tree(left, cols, {
            "body": ("System architecture", 250, tk.W),
            "type": ("Type", 180, tk.W),
            "action": ("Next action", 130, tk.W),
            "priority": ("Priority", 65, tk.E),
            "value": ("Value", 90, tk.E),
            "signals": ("Signals", 95, tk.CENTER),
            "discover": ("Discovery", 90, tk.CENTER),
            "distance": ("Distance", 85, tk.E),
        })
        self.bodies_tree.tag_configure("valuable", foreground=COLOR_ACCENT)
        self.bodies_tree.tag_configure("star", foreground=self.UI_MUTED)
        self.bodies_tree.tag_configure("bio", foreground=self.UI_OK)
        self.bodies_tree.tag_configure("actionable", foreground=COLOR_ORANGE)
        self.bodies_tree.bind("<<TreeviewSelect>>", self._on_body_selected)
        self.survey_tree_wrap = self.bodies_tree.master

        tk.Frame(right, bg=COLOR_ACCENT, height=2).pack(fill=tk.X)
        tk.Label(right, text="BODY DETAIL", fg=COLOR_ORANGE, bg=self.UI_PANEL, font=("Segoe UI", 8, "bold"), anchor="w").pack(fill=tk.X, padx=10, pady=(9, 0))
        self.body_detail_title = tk.Label(right, text="Select a body", fg=COLOR_ACCENT, bg=self.UI_PANEL, font=("Segoe UI", 11, "bold"), anchor="w", wraplength=270, justify=tk.LEFT)
        self.body_detail_title.pack(fill=tk.X, padx=10, pady=(2, 0))
        self.body_detail = tk.Text(
            right,
            bg=self.UI_PANEL,
            fg=COLOR_TEXT,
            insertbackground=COLOR_ACCENT,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=8,
            font=("Consolas", 9),
            wrap=tk.WORD,
        )
        self.body_detail.pack(fill=tk.BOTH, expand=True)
        self.body_detail.configure(state=tk.DISABLED)

        self.recon_status = tk.Label(
            right, text="RECON · awaiting system data", fg=self.UI_MUTED,
            bg=self.UI_PANEL, font=("Consolas", 8, "bold"), anchor="w",
        )
        self.recon_status.pack(fill=tk.X, padx=10, pady=(4, 5))
        recon_actions = tk.Frame(right, bg=self.UI_PANEL)
        recon_actions.pack(fill=tk.X, padx=10, pady=(0, 9))
        self._button(recon_actions, "Save Recon", self._save_recon_candidate, accent=True).pack(side=tk.LEFT)
        self._button(recon_actions, "Copy", self._copy_recon_dossier).pack(side=tk.LEFT, padx=(6, 0))
        self._button(recon_actions, "Bookmark", self._bookmark_selected_body).pack(side=tk.LEFT, padx=(6, 0))
        self._button(
            recon_actions, "Architect",
            lambda: getattr(self.app, "open_colonization_window", lambda: None)(),
        ).pack(side=tk.LEFT, padx=(6, 0))

    def _build_logbook_workspace(self):
        frame = self.logbook_workspace
        toolbar = tk.Frame(frame, bg=self.UI_BG)
        toolbar.pack(fill=tk.X, padx=8, pady=(8, 6))
        tk.Label(
            toolbar, text="EXPEDITION LOGBOOK", fg=COLOR_ORANGE, bg=self.UI_BG,
            font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.LEFT)
        self._button(toolbar, "Save Report", self._save_expedition_report).pack(side=tk.RIGHT)
        self._button(toolbar, "Copy Report", self._copy_expedition_report, accent=True).pack(side=tk.RIGHT, padx=(0, 7))
        self._button(toolbar, "Copy Session", self._copy_captains_log).pack(side=tk.RIGHT, padx=(0, 7))
        self._button(toolbar, "Reset Session", self._reset_session).pack(side=tk.RIGHT, padx=(0, 7))
        self.captains_log_summary = tk.Label(
            toolbar, text="", fg=self.UI_MUTED, bg=self.UI_BG, font=("Consolas", 8),
        )
        self.captains_log_summary.pack(side=tk.RIGHT, padx=12)

        split = tk.PanedWindow(
            frame, orient=tk.HORIZONTAL, bg=self.UI_BG,
            sashwidth=6, sashrelief=tk.FLAT, bd=0,
        )
        split.pack(fill=tk.BOTH, expand=True)
        left = tk.Frame(split, bg=self.UI_BG)
        right = tk.Frame(split, bg=self.UI_PANEL)
        split.add(left, minsize=520)
        split.add(right, minsize=390)

        self.history_text = tk.Text(
            left, bg="#0b0f13", fg=COLOR_TEXT, insertbackground=COLOR_ACCENT,
            relief=tk.FLAT, bd=0, padx=10, pady=8, height=10,
            font=("Consolas", 9), wrap=tk.WORD,
        )
        self.history_text.pack(fill=tk.X, pady=(0, 8))
        self.history_text.configure(state=tk.DISABLED)
        self.captains_log_tree = self._tree(
            left, ("date", "route", "jumps", "discoveries", "sales"), {
                "date": ("Session", 140, tk.W), "route": ("Route", 250, tk.W),
                "jumps": ("Jumps", 60, tk.E), "discoveries": ("Discoveries", 90, tk.E),
                "sales": ("Data Sold", 100, tk.E),
            },
        )
        self.captains_log_tree.bind("<<TreeviewSelect>>", self._on_captains_log_selected)
        self.captains_log_rows = {}
        tk.Frame(right, bg=COLOR_ACCENT, height=2).pack(fill=tk.X)
        tk.Label(
            right, text="SELECTED SESSION", fg=COLOR_ORANGE, bg=self.UI_PANEL,
            font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=10, pady=(8, 2))
        self.captains_log_text = tk.Text(
            right, bg="#0b0f13", fg=COLOR_TEXT, insertbackground=COLOR_ACCENT,
            relief=tk.FLAT, bd=0, padx=12, pady=10,
            font=("Consolas", 9), wrap=tk.WORD,
        )
        self.captains_log_text.pack(fill=tk.BOTH, expand=True)
        self.captains_log_text.configure(state=tk.DISABLED)

    def _build_bio_tab(self):
        frame = tk.Frame(self.survey_tabs, bg=self.UI_BG)
        self.survey_tabs.add(frame, text="Biology")

        top = tk.Frame(frame, bg=self.UI_BG)
        top.pack(fill=tk.X, pady=(0, 8))
        self.bio_summary_labels = {}
        for key, title in (
            ("bodies", "BODIES WITH BIO"),
            ("signals", "SIGNALS"),
            ("genus", "BIO TYPES"),
            ("complete", "COMPLETED SCANS"),
        ):
            tile = tk.Frame(top, bg="#0b0f13", highlightbackground=self.UI_BORDER, highlightthickness=1, bd=0)
            tile.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
            tk.Label(tile, text=title, fg=COLOR_ORANGE, bg="#0b0f13", font=("Segoe UI", 7, "bold"), anchor="w").pack(fill=tk.X, padx=10, pady=(7, 0))
            lbl = tk.Label(tile, text="-", fg=COLOR_ACCENT, bg="#0b0f13", font=("Consolas", 11, "bold"), anchor="w")
            lbl.pack(fill=tk.X, padx=10, pady=(2, 8))
            self.bio_summary_labels[key] = lbl

        self.sampling_banner = tk.Label(
            frame, text="", fg=COLOR_TEXT, bg="#0b0f13", font=("Consolas", 10, "bold"),
            anchor="w", padx=12, pady=9, highlightbackground=self.UI_BORDER,
            highlightthickness=1,
        )
        self.sampling_banner.pack(fill=tk.X, pady=(0, 8))
        self.sampling_banner.pack_forget()

        cols = ("body", "class", "bio", "geo", "genus", "spacing", "value", "samples", "status")
        self.bio_tree = self._tree(frame, cols, {
            "body": ("Body", 230, tk.W),
            "class": ("Class", 155, tk.W),
            "bio": ("Bio", 55, tk.E),
            "geo": ("Geo", 55, tk.E),
            "genus": ("Genus / Predicted", 210, tk.W),
            "spacing": ("Spacing", 80, tk.E),
            "value": ("Vista", 95, tk.E),
            "samples": ("Samples", 95, tk.CENTER),
            "status": ("Status", 120, tk.W),
        })
        self.bio_tree.tag_configure("complete", foreground=self.UI_OK)
        self.bio_tree.tag_configure("pending", foreground=COLOR_ORANGE)
        self.bio_tree.tag_configure("empty", foreground=self.UI_MUTED)

    def _build_route_tab(self, parent, embedded=False):
        frame = parent if embedded else tk.Frame(parent, bg=self.UI_BG)
        if not embedded:
            parent.add(frame, text="Survey Intelligence")
        cols = ("idx", "system", "star", "scoop", "distance", "edsm", "valuable", "status")
        self.route_tree = self._tree(frame, cols, {
            "idx": ("#", 48, tk.E),
            "system": ("System", 250, tk.W),
            "star": ("Star", 90, tk.CENTER),
            "scoop": ("Scoop", 80, tk.CENTER),
            "distance": ("Distance", 100, tk.E),
            "edsm": ("EDSM Value", 105, tk.E),
            "valuable": ("Valuable", 80, tk.CENTER),
            "status": ("Status", 150, tk.W),
        })
        self.route_tree.tag_configure("current", foreground=COLOR_ACCENT)
        self.route_tree.tag_configure("next", foreground=COLOR_ORANGE)
        self.route_tree.tag_configure("pending", foreground=self.UI_MUTED)

    def _build_history_tab(self):
        frame = tk.Frame(self.chronicle_tabs, bg=self.UI_BG)
        self.chronicle_tabs.add(frame, text="Trip & History")
        self.history_text = tk.Text(
            frame,
            bg="#0b0f13",
            fg=COLOR_TEXT,
            insertbackground=COLOR_ACCENT,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=10,
            font=("Consolas", 10),
            wrap=tk.WORD,
        )
        self.history_text.pack(fill=tk.BOTH, expand=True)
        self.history_text.configure(state=tk.DISABLED)

    def _build_captains_log_tab(self):
        frame = tk.Frame(self.chronicle_tabs, bg=self.UI_BG)
        self.chronicle_tabs.add(frame, text="Captain's Log")
        toolbar = tk.Frame(frame, bg=self.UI_BG)
        toolbar.pack(fill=tk.X, padx=10, pady=(10, 6))
        tk.Label(toolbar, text="EXPEDITION CHRONICLE", fg=COLOR_ORANGE, bg=self.UI_BG,
                 font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
        self._button(toolbar, "Copy Markdown", self._copy_captains_log, accent=True).pack(side=tk.RIGHT)
        self.captains_log_summary = tk.Label(toolbar, text="", fg=self.UI_MUTED, bg=self.UI_BG,
                                             font=("Consolas", 8))
        self.captains_log_summary.pack(side=tk.RIGHT, padx=12)

        split = tk.PanedWindow(frame, orient=tk.HORIZONTAL, bg=self.UI_BG, sashwidth=6,
                               sashrelief=tk.FLAT, bd=0)
        split.pack(fill=tk.BOTH, expand=True)
        left = tk.Frame(split, bg=self.UI_BG)
        right = tk.Frame(split, bg=self.UI_PANEL)
        split.add(left, minsize=390)
        split.add(right, minsize=350)
        self.captains_log_tree = self._tree(left, ("date", "route", "jumps", "discoveries", "sales"), {
            "date": ("Session", 145, tk.W), "route": ("Route", 260, tk.W),
            "jumps": ("Jumps", 60, tk.E), "discoveries": ("Discoveries", 95, tk.E),
            "sales": ("Data Sold", 100, tk.E),
        })
        self.captains_log_tree.bind("<<TreeviewSelect>>", self._on_captains_log_selected)
        self.captains_log_rows = {}
        self.captains_log_text = tk.Text(
            right, bg="#0b0f13", fg=COLOR_TEXT, insertbackground=COLOR_ACCENT,
            relief=tk.FLAT, bd=0, padx=12, pady=10, font=("Consolas", 9), wrap=tk.WORD,
        )
        self.captains_log_text.pack(fill=tk.BOTH, expand=True)
        self.captains_log_text.configure(state=tk.DISABLED)

    def _build_system_history_tab(self):
        frame = tk.Frame(self.chronicle_tabs, bg=self.UI_BG)
        self.chronicle_tabs.add(frame, text="System History")

        controls = tk.Frame(frame, bg=self.UI_BG)
        controls.pack(fill=tk.X, padx=10, pady=(10, 6))
        tk.Label(controls, text="Filter", fg=self.UI_MUTED, bg=self.UI_BG, font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
        self.system_history_filter_var = tk.StringVar()
        self.system_history_filter_var.trace_add("write", lambda *_: self._render_system_history())
        tk.Entry(
            controls,
            textvariable=self.system_history_filter_var,
            bg="#0b0f13",
            fg=COLOR_TEXT,
            insertbackground=COLOR_ACCENT,
            relief=tk.FLAT,
            width=34,
        ).pack(side=tk.LEFT, padx=(8, 10), ipady=4)
        self._button(controls, "Copy History", self._copy_system_history, accent=True).pack(side=tk.LEFT)
        self.system_history_summary = tk.Label(controls, text="", font=("Consolas", 8), fg=self.UI_MUTED, bg=self.UI_BG)
        self.system_history_summary.pack(side=tk.RIGHT)

        cols = ("last", "system", "star", "bodies", "value", "bio", "valuable", "source")
        list_wrap = tk.Frame(frame, bg=self.UI_BG)
        list_wrap.pack(fill=tk.BOTH, expand=True)
        self.system_history_tree = self._tree(list_wrap, cols, {
            "last": ("Last Visit", 125, tk.W),
            "system": ("System", 260, tk.W),
            "star": ("Star", 70, tk.CENTER),
            "bodies": ("Bodies", 85, tk.CENTER),
            "value": ("Value", 95, tk.E),
            "bio": ("Bio", 75, tk.CENTER),
            "valuable": ("Valuable", 80, tk.CENTER),
            "source": ("Source", 65, tk.CENTER),
        })
        self.system_history_tree.tag_configure("current", foreground=COLOR_ACCENT)
        self.system_history_tree.tag_configure("valuable", foreground=COLOR_ORANGE)
        self.system_history_tree.tag_configure("bio", foreground=self.UI_OK)
        self.system_history_tree.bind("<<TreeviewSelect>>", self._on_system_history_selected)
        self.system_history_by_iid = {}

        detail = tk.Frame(frame, bg=self.UI_PANEL, highlightbackground=self.UI_BORDER, highlightthickness=1, bd=0)
        detail.pack(fill=tk.X, padx=0, pady=(8, 0))
        tk.Frame(detail, bg=COLOR_ACCENT, height=2).pack(fill=tk.X)
        tk.Label(detail, text="SYSTEM DETAIL", fg=COLOR_ORANGE, bg=self.UI_PANEL, font=("Segoe UI", 8, "bold"), anchor="w").pack(fill=tk.X, padx=10, pady=(7, 0))
        self.system_history_detail = tk.Text(
            detail,
            bg=self.UI_PANEL,
            fg=COLOR_TEXT,
            insertbackground=COLOR_ACCENT,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=6,
            height=7,
            font=("Consolas", 9),
            wrap=tk.WORD,
        )
        self.system_history_detail.pack(fill=tk.X)
        self.system_history_detail.configure(state=tk.DISABLED)

    def _build_ledger_tab(self):
        frame = tk.Frame(self.chronicle_tabs, bg=self.UI_BG)
        self.chronicle_tabs.add(frame, text="Value Ledger")

        controls = tk.Frame(frame, bg=self.UI_BG)
        controls.pack(fill=tk.X, padx=10, pady=(10, 6))
        tk.Label(controls, text="Filter", fg=self.UI_MUTED, bg=self.UI_BG, font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
        self.ledger_filter_var = tk.StringVar()
        self.ledger_filter_var.trace_add("write", lambda *_: self._render_ledger())
        tk.Entry(
            controls,
            textvariable=self.ledger_filter_var,
            bg="#0b0f13",
            fg=COLOR_TEXT,
            insertbackground=COLOR_ACCENT,
            relief=tk.FLAT,
            width=34,
        ).pack(side=tk.LEFT, padx=(8, 10), ipady=4)
        self._button(controls, "Copy Ledger", self._copy_ledger_summary, accent=True).pack(side=tk.LEFT)
        self.ledger_summary = tk.Label(controls, text="", font=("Consolas", 8), fg=self.UI_MUTED, bg=self.UI_BG)
        self.ledger_summary.pack(side=tk.RIGHT)

        cols = ("system", "body", "class", "value", "mapped", "flags")
        self.ledger_tree = self._tree(frame, cols, {
            "system": ("System", 190, tk.W),
            "body": ("Body", 230, tk.W),
            "class": ("Class", 180, tk.W),
            "value": ("Est. Value", 95, tk.E),
            "mapped": ("Mapped", 75, tk.E),
            "flags": ("Flags", 180, tk.W),
        })
        self.ledger_rows = []

    def _tree(self, parent, cols, specs):
        wrap = tk.Frame(parent, bg=self.UI_BG)
        wrap.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(wrap, columns=cols, show="headings", style="Explore.Treeview")
        for col in cols:
            label, width, anchor = specs[col]
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor=anchor)
        scroll = scrollbar(wrap, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    def _button(self, parent, text, cmd, accent=False):
        return button(parent, text, cmd, accent=accent)

    def refresh(self):
        if not self.is_open() or not self._widget_alive(getattr(self, "header_summary", None)):
            return
        try:
            current = getattr(self.app, "current_sys", "---") or "---"
            scanned = int(getattr(self.app, "scanned", 0) or 0)
            total = int(getattr(self.app, "total", 0) or 0)
            bodies = [item for item in list(getattr(self.app, "scan_items", []) or []) if isinstance(item, dict)]
            current_value = sum(self._item_value(item) for item in bodies)
            valuable_count = sum(1 for item in bodies if self._is_valuable(item))
            complete = f"{scanned}/{total}" if total else f"{scanned}/0"

            star = star_type_label(getattr(self.app, "star_class", ""), "-")
            traffic = getattr(self.app, "system_traffic", {}) or {}
            self.header_summary.config(text=current)
            self.system_card.config(text=f"{current}\nStar {star} | Traffic {traffic.get('day', 0)}/{traffic.get('week', 0)}/{traffic.get('total', 0)}")
            self.scan_card.config(text=f"{complete} bodies | {current_value:,} cr\n{valuable_count} valuable bodies")
            self.route_card.config(text=self._route_card_text())
            session_stats = self._session_stats()
            self.trip_card.config(text=self._trip_card_text(session_stats))
            self._refresh_expedition_strip()
            bio_summary = self._bio_summary(bodies)
            self.bio_card.config(text=f"{bio_summary['bio_bodies']} bodies | {bio_summary['bio_signals']} signals\n{bio_summary['complete']} complete")
            self._render_body_metrics(current, bodies, scanned, total, current_value)
            self._render_bodies(bodies)
            self._render_bio(bodies, bio_summary)
            self._render_sampling()
            self._refresh_system_history_rows(current, bodies, current_value, valuable_count, bio_summary, scanned, total)
            self._render_system_history()
            self._request_route_enrichment()
            self._render_route()
            self._render_history(current_value, valuable_count, session_stats)
            self._render_captains_log()
            self._refresh_ledger()
            selected_workspace = self.tabs.select()
            if selected_workspace == str(self.discoveries_workspace) and self.discoveries_view:
                self.discoveries_view.refresh(self.system_history_rows, self.ledger_rows)
            if self._map_popout_is_open() or (
                selected_workspace == str(self.expedition_workspace)
                and self.expedition_map_view and self.route_plotter
                and self.route_plotter.current_section() == "Map & Intelligence"
            ):
                self._refresh_visible_map()
            elif (
                selected_workspace == str(self.expedition_workspace)
                and self.expedition_mission_view
                and self.route_plotter
                and self.route_plotter.current_section() == "Mission Control"
            ):
                self.expedition_mission_view.refresh()
        except Exception as exc:
            self._log_error(f"Exploration refresh failed: {exc}")

    def _log_error(self, message):
        try:
            if hasattr(self.app, "log"):
                self.app.log(message)
        except Exception:
            pass

    def _item_value(self, item):
        try:
            if item.get("dss_complete"):
                return int(item.get("dss_reward") or item.get("reward") or 0)
            return int(item.get("reward") or 0)
        except Exception:
            return 0

    def _is_valuable(self, item):
        planet = item.get("planet_class") or item.get("class") or ""
        return bool(
            item.get("terraformable")
            or planet in ("Earthlike body", "Water world", "Ammonia world")
            or self._item_value(item) >= 500000
        )

    def _flag_text(self, item):
        flags = []
        if item.get("terraformable"):
            flags.append("Terraformable")
        if item.get("landable"):
            flags.append("Landable")
        if item.get("was_discovered") is False:
            flags.append("Undiscovered")
        if item.get("first_footfall"):
            flags.append("First footfall available")
        if item.get("was_mapped") is False:
            flags.append("Unmapped")
        return ", ".join(flags)

    def _signal_text(self, item):
        bio = self._safe_int(item.get("bio_count"))
        geo = self._safe_int(item.get("geo_count"))
        organic_done = self._safe_int(item.get("organic_complete_count"))
        signals = []
        if bio:
            signals.append(f"Bio {bio}")
        if geo:
            signals.append(f"Geo {geo}")
        if organic_done:
            signals.append(f"Done {organic_done}")
        return ", ".join(signals) or "-"

    def _body_status(self, item):
        if item.get("is_star"):
            return "Star"
        if item.get("organic_complete_count"):
            return "Bio done"
        if self._safe_int(item.get("bio_count")) > 0:
            return "Bio"
        if item.get("dss_complete"):
            return "Mapped"
        if self._is_valuable(item):
            return "High value"
        if item.get("was_discovered") is False:
            return "New"
        return "Scanned"

    def _safe_int(self, value, default=0):
        try:
            return int(value or default)
        except Exception:
            return default

    def _body_discovery_text(self, item):
        bits = []
        if item.get("was_discovered") is False:
            bits.append("First")
        else:
            bits.append("Known")
        if item.get("dss_complete") or item.get("was_mapped"):
            bits.append("DSS")
        elif item.get("was_mapped") is False:
            bits.append("Unmapped")
        return " / ".join(bits)

    def _body_distance_text(self, item):
        value = item.get("distance_to_arrival")
        if value is None or value == "":
            return "-"
        try:
            return f"{float(value):,.0f} ls"
        except Exception:
            return str(value)

    def _render_body_metrics(self, current, bodies, scanned, total, current_value):
        labels = getattr(self, "body_metric_labels", {})
        if not labels:
            return
        status = "complete" if total and scanned >= total else ("partial" if scanned else "unknown")
        star = star_type_label(getattr(self.app, "star_class", ""), "-")
        bio_total = sum(self._safe_int(item.get("bio_count")) for item in bodies)
        geo_total = sum(self._safe_int(item.get("geo_count")) for item in bodies)
        edsm = self._edsm_summary(current)
        edsm_value = "-"
        if edsm:
            edsm_value = self._format_credits(edsm.get("estimatedValueMapped") or edsm.get("estimatedValue"))
        next_route = self._next_route_system()
        activity = "Exploring system"
        if next_route:
            activity = f"Next route: {next_route}"
        labels["status"].config(text=f"{current}\n{status} | star {star}")
        labels["bodies"].config(text=f"{scanned} of {total or len(bodies)}")
        labels["signals"].config(text=f"Bio {bio_total} | Geo {geo_total}")
        labels["value"].config(text=f"Local {self._format_credits(current_value)}\nEDSM {edsm_value}")
        labels["activity"].config(text=activity)

    def _render_bodies(self, bodies):
        self._last_survey_bodies = list(bodies or [])
        selected_body_id = None
        selected = self.bodies_tree.selection()
        if selected:
            selected_item = self.body_items_by_iid.get(selected[0])
            selected_body_id = selected_item.get("body_id") if selected_item else None
        children = self.bodies_tree.get_children()
        if children:
            self.bodies_tree.delete(*children)
        self.body_items_by_iid = {}
        plans = survey_plan(bodies)

        def key_for(item):
            body_id = item.get("body_id")
            return ("id", str(body_id)) if body_id is not None else ("name", str(item.get("full_name") or item.get("name") or ""))

        plan_by_name = {str(row.get("body") or ""): row for row in plans}
        self._survey_plan_by_key = {}
        for item in bodies:
            plan = plan_by_name.get(str(item.get("name") or "")) or plan_by_name.get(str(item.get("full_name") or ""))
            if plan:
                self._survey_plan_by_key[key_for(item)] = plan

        filter_var = getattr(self, "survey_filter_var", None)
        selected_filter = filter_var.get() if filter_var else "All bodies"

        def visible(item):
            plan = self._survey_plan_by_key.get(key_for(item))
            if selected_filter == "All bodies":
                return True
            if selected_filter == "Actionable":
                return bool(plan and plan.get("action") not in ("Observe", "Review biology"))
            if selected_filter == "Biology":
                return bool(self._safe_int(item.get("bio_count")) or item.get("organic_scans") or item.get("genuses"))
            if selected_filter == "Geology":
                return self._safe_int(item.get("geo_count")) > 0
            if selected_filter == "Valuable":
                return self._is_valuable(item)
            return True

        architecture = architecture_rows(bodies)
        rows = [row for row in architecture if visible(row["item"])]
        chosen = None
        for architecture_row in rows:
            item = architecture_row["item"]
            body = item.get("full_name") or item.get("name") or "Body"
            depth = architecture_row.get("depth", 0) if selected_filter == "All bodies" else 0
            display_body = f"{'   ' * depth}{'↳ ' if depth else ''}{body}"
            body_class = (
                star_type_label(item.get("star_type"), include_star=True)
                if item.get("star_type") else item.get("planet_class") or item.get("class") or ""
            )
            value = self._item_value(item)
            plan = self._survey_plan_by_key.get(key_for(item))
            action = plan.get("action") if plan else ("Primary star" if item.get("is_star") else "Reference")
            priority = plan.get("score") if plan else "-"
            tags = []
            if item.get("is_star"):
                tags.append("star")
            elif item.get("bio_count") or item.get("organic_complete_count"):
                tags.append("bio")
            elif self._is_valuable(item):
                tags.append("valuable")
            if plan and int(plan.get("score") or 0) >= 50:
                tags.append("actionable")
            iid = self.bodies_tree.insert(
                "",
                tk.END,
                values=(
                    display_body,
                    body_class,
                    action,
                    priority,
                    self._format_credits(value),
                    self._signal_text(item),
                    self._body_discovery_text(item),
                    self._body_distance_text(item),
                ),
                tags=tuple(tags),
            )
            self.body_items_by_iid[iid] = item
            if selected_body_id is not None and str(item.get("body_id")) == str(selected_body_id):
                chosen = iid
        first = self.bodies_tree.get_children()
        if first:
            iid = chosen or first[0]
            self.bodies_tree.selection_set(iid)
            self._show_body_detail(self.body_items_by_iid.get(iid))
        else:
            self._show_body_detail(None)
        self._update_recon_status()

    def _genus_labels(self, item):
        labels = []
        for genus in item.get("genuses") or []:
            if isinstance(genus, dict):
                label = genus.get("Genus_Localised") or genus.get("Name_Localised") or genus.get("Genus") or genus.get("Name")
            else:
                label = str(genus)
            if label and label not in labels:
                labels.append(label)
        for scan in (item.get("organic_scans") or {}).values():
            label = scan.get("genus") or scan.get("species")
            if label and label not in labels:
                labels.append(label)
        return labels

    def _organic_sample_text(self, item):
        scans = item.get("organic_scans") or {}
        if not scans:
            return "-"
        complete = sum(1 for scan in scans.values() if scan.get("is_complete"))
        sample_nums = [
            self._safe_int(scan.get("sample_idx"))
            for scan in scans.values()
            if self._safe_int(scan.get("sample_idx")) > 0 and not scan.get("is_complete")
        ]
        if complete:
            return f"{complete} complete"
        if sample_nums:
            return f"sample {max(sample_nums)}"
        return f"{len(scans)} logged"

    def _predicted_genus_labels(self, item):
        labels = []
        for pred in item.get("predicted_genuses") or []:
            label = pred.get("name") if isinstance(pred, dict) else str(pred)
            if label and label not in labels:
                labels.append(label)
        return labels

    def _bio_spacing_text(self, item, names):
        scans = item.get("organic_scans") or {}
        for scan in scans.values():
            spacing = scan.get("colony_m")
            if spacing:
                return f"{int(spacing):,} m"
        for name in names:
            spacing = bio_values.GENUS_COLONY_M.get(name)
            if spacing:
                return f"{int(spacing):,} m"
        return "-"

    def _bio_complete_value(self, item):
        value = 0
        for scan in (item.get("organic_scans") or {}).values():
            if not scan.get("is_complete"):
                continue
            try:
                value += int(scan.get("species_value") or 0)
            except Exception:
                pass
        return value

    def _bio_value_text(self, item, names):
        complete_value = self._bio_complete_value(item)
        if complete_value:
            return self._format_credits(complete_value)
        ranges = []
        for name in names:
            info = bio_values.genus_info(name)
            lo, hi = info.get("min_value"), info.get("max_value")
            if lo and hi:
                ranges.append((int(lo), int(hi)))
        if not ranges:
            return "-"
        lo = min(pair[0] for pair in ranges)
        hi = max(pair[1] for pair in ranges)
        if lo == hi:
            return self._format_credits(lo)
        return f"{self._format_credits(lo)}-{self._format_credits(hi)}"

    def _bio_summary(self, bodies):
        bio_bodies = 0
        bio_signals = 0
        geo_signals = 0
        genus_names = set()
        complete = 0
        completed_value = 0
        for item in bodies:
            bio = self._safe_int(item.get("bio_count"))
            geo = self._safe_int(item.get("geo_count"))
            done = self._safe_int(item.get("organic_complete_count"))
            genuses = self._genus_labels(item)
            predicted = self._predicted_genus_labels(item)
            if bio or geo or done or genuses or predicted:
                bio_bodies += 1
            bio_signals += bio
            geo_signals += geo
            complete += done
            completed_value += self._bio_complete_value(item)
            genus_names.update(genuses)
        return {
            "bio_bodies": bio_bodies,
            "bio_signals": bio_signals,
            "geo_signals": geo_signals,
            "genus": len(genus_names),
            "complete": complete,
            "completed_value": completed_value,
        }

    def _render_bio(self, bodies, summary=None):
        if not hasattr(self, "bio_tree"):
            return
        summary = summary or self._bio_summary(bodies)
        labels = getattr(self, "bio_summary_labels", {})
        if labels:
            labels["bodies"].config(text=str(summary["bio_bodies"]))
            labels["signals"].config(text=f"Bio {summary['bio_signals']} | Geo {summary['geo_signals']}")
            labels["genus"].config(text=str(summary["genus"]))
            value_text = self._format_credits(summary.get("completed_value", 0))
            labels["complete"].config(text=f"{summary['complete']} | {value_text}")

        for item_id in self.bio_tree.get_children():
            self.bio_tree.delete(item_id)
        rows = []
        for item in bodies:
            genuses = self._genus_labels(item)
            predicted = self._predicted_genus_labels(item)
            bio = self._safe_int(item.get("bio_count"))
            geo = self._safe_int(item.get("geo_count"))
            done = self._safe_int(item.get("organic_complete_count"))
            if bio or geo or done or genuses or predicted:
                rows.append((item, genuses, predicted, bio, geo, done))
        rows.sort(key=lambda row: (-(row[3] + row[5]), row[0].get("body_id") or 99999, row[0].get("name") or ""))

        if not rows:
            self.bio_tree.insert("", tk.END, values=("No biological or geological signals recorded for this system yet.", "", "", "", "", "", "", "", ""), tags=("empty",))
            return

        for item, genuses, predicted, bio, geo, done in rows:
            names = genuses or predicted
            tags = ("complete",) if done else ("pending",)
            if done:
                status = "Complete"
            elif genuses or bio:
                status = "Signals found"
            elif predicted:
                status = "Predicted"
            else:
                status = "Geo only"
            genus_text = ", ".join(genuses[:4]) if genuses else ("Pred: " + ", ".join(predicted[:3]) if predicted else "-")
            self.bio_tree.insert(
                "",
                tk.END,
                values=(
                    item.get("full_name") or item.get("name") or "Body",
                    item.get("planet_class") or item.get("class") or "-",
                    bio,
                    geo,
                    genus_text,
                    self._bio_spacing_text(item, names),
                    self._bio_value_text(item, names),
                    self._organic_sample_text(item),
                    status,
                ),
                tags=tags,
            )

    def _render_sampling(self):
        banner = getattr(self, "sampling_banner", None)
        if not banner:
            return
        sample = self.app._sampling_snapshot() if hasattr(self.app, "_sampling_snapshot") else None
        if not sample:
            banner.pack_forget()
            return
        if not banner.winfo_manager():
            banner.pack(fill=tk.X, pady=(0, 8), before=self.survey_tree_wrap)
        minimum = sample.get("min_distance_m")
        colony = sample.get("colony_m")
        if sample.get("clear"):
            status = "CLEAR TO SAMPLE"
            color = self.UI_OK
        elif minimum is not None and colony:
            status = f"MOVE · {minimum:,} / {colony:,} m"
            color = COLOR_ORANGE
        else:
            status = "MOVE TO THE NEXT SAMPLE SITE"
            color = COLOR_ORANGE
        banner.config(
            text=f"GENETIC SAMPLER · {sample.get('species')} · sample {sample.get('progress', 1)}/3 · {status}",
            fg=color,
        )

    def _route_entries(self):
        entries = list(getattr(self.app, "nav_route_entries", []) or [])
        if entries:
            return entries
        return [{"StarSystem": name} for name in (getattr(self.app, "route_list", []) or [])]

    def _route_names(self):
        return [entry.get("StarSystem") for entry in self._route_entries() if entry.get("StarSystem")]

    def _next_route_system(self):
        current = getattr(self.app, "current_sys", None)
        names = self._route_names()
        if not names:
            return None
        if current in names:
            idx = names.index(current)
            return names[idx + 1] if idx + 1 < len(names) else None
        return names[0]

    def _route_card_text(self):
        entries = self._route_entries()
        if not entries:
            return "No active in-game route\nNavRoute.json is empty"
        next_name = self._next_route_system() or "Route complete"
        dest = entries[-1].get("StarSystem") or "-"
        enriched = sum(1 for entry in entries if self._edsm_summary(entry.get("StarSystem")))
        return f"{len(entries)} systems | next {next_name}\nEDSM {enriched}/{len(entries)} | dest {dest}"

    def _on_body_selected(self, _event=None):
        selected = self.bodies_tree.selection()
        self._show_body_detail(self.body_items_by_iid.get(selected[0]) if selected else None)

    def _fmt_num(self, value, suffix=""):
        if value is None or value == "":
            return "-"
        try:
            number = float(value)
            if abs(number) >= 1000:
                text = f"{number:,.0f}"
            else:
                text = f"{number:.2f}".rstrip("0").rstrip(".")
            return f"{text}{suffix}"
        except Exception:
            return str(value)

    def _show_body_detail(self, item):
        lines = []
        if item:
            if hasattr(self, "body_detail_title"):
                self.body_detail_title.config(text=item.get("full_name") or item.get("name") or "Body")
            lines.extend([
                f"Status: {self._body_status(item)}",
                f"Class: {star_type_label(item.get('star_type'), include_star=True) if item.get('star_type') else item.get('planet_class') or item.get('class') or '-'}",
                f"Estimated value: {self._item_value(item):,} cr",
                f"DSS value: {int(item.get('dss_reward') or 0):,} cr",
                f"DSS complete: {'Yes' if item.get('dss_complete') else 'No'}",
                f"Distance: {self._fmt_num(item.get('distance_to_arrival'), ' ls')}",
                "",
                f"Landable: {'Yes' if item.get('landable') else 'No'}",
                f"Terraforming: {'Terraformable' if item.get('terraformable') else 'No'}",
                f"Discovered: {'No' if item.get('was_discovered') is False else 'Yes'}",
                f"Mapped: {'Yes' if item.get('was_mapped') else 'No'}",
                "",
                f"Atmosphere: {item.get('atmosphere') or '-'}",
                f"Volcanism: {item.get('volcanism') or '-'}",
                f"Gravity: {self._fmt_num(item.get('surface_gravity'), ' G')}",
                f"Temperature: {self._fmt_num(item.get('surface_temp'), ' K')}",
                f"Radius: {self._fmt_num(item.get('radius'), ' m')}",
                f"Mass: {self._fmt_num(item.get('mass'))}",
                "",
                f"Signals: {self._signal_text(item)}",
            ])
            genuses = item.get("genuses") or []
            if genuses:
                lines.append("")
                lines.append("Detected genus:")
                for genus in genuses:
                    if isinstance(genus, dict):
                        lines.append(f"- {genus.get('Genus_Localised') or genus.get('Name_Localised') or genus.get('Genus') or genus.get('Name') or genus}")
                    else:
                        lines.append(f"- {genus}")
            organic_scans = item.get("organic_scans") or {}
            if organic_scans:
                lines.append("")
                lines.append("Organic scans:")
                for scan in organic_scans.values():
                    status = "complete" if scan.get("is_complete") else f"sample {scan.get('sample_idx') or '-'}"
                    details = [status]
                    if scan.get("colony_m"):
                        details.append(f"{int(scan.get('colony_m')):,} m spacing")
                    if scan.get("species_value"):
                        details.append(self._format_credits(scan.get("species_value")))
                    lines.append(f"- {scan.get('species') or scan.get('genus') or 'Organic'} ({', '.join(details)})")
            predictions = item.get("predicted_genuses") or []
            if predictions:
                lines.append("")
                lines.append("Predicted genus candidates:")
                for pred in predictions[:8]:
                    value = "-"
                    lo, hi = pred.get("min_value"), pred.get("max_value")
                    if lo and hi:
                        value = self._format_credits(lo) if lo == hi else f"{self._format_credits(lo)}-{self._format_credits(hi)}"
                    spacing = f"{int(pred.get('colony_m')):,} m" if pred.get("colony_m") else "-"
                    lines.append(f"- {pred.get('name') or 'Organic'} | {spacing} spacing | {value}")
            key = (
                ("id", str(item.get("body_id"))) if item.get("body_id") is not None
                else ("name", str(item.get("full_name") or item.get("name") or ""))
            )
            plan = self._survey_plan_by_key.get(key)
            if plan:
                lines.extend([
                    "", "Survey plan:",
                    f"- {plan.get('action')} · priority {plan.get('score')}",
                    f"- {plan.get('reason')}",
                ])
            parents = item.get("parents") or []
            if parents:
                parent_text = " → ".join(
                    f"{kind} {value}"
                    for parent in parents if isinstance(parent, dict)
                    for kind, value in parent.items()
                )
                lines.extend(["", f"Architecture: {parent_text or 'Root body'}"])
            orbital = item.get("orbital_period")
            rotation = item.get("rotation_period")
            if orbital or rotation or item.get("eccentricity") is not None:
                lines.append(
                    "Orbit: "
                    f"{float(orbital or 0) / 86400:.2f} d · rotation {float(rotation or 0) / 3600:.2f} h · "
                    f"e {float(item.get('eccentricity') or 0):.3f}"
                )
            body_name = item.get("full_name") or item.get("name")
            findings = [row for row in wonder_rows([item]) if row.get("body") == body_name]
            if findings:
                lines.extend(["", "Notable findings:"])
                lines.extend(f"- {row['kind']}: {row['detail']}" for row in findings)
        else:
            if hasattr(self, "body_detail_title"):
                self.body_detail_title.config(text="Select a body")
            lines = ["Select a body to view scan details."]
        self.body_detail.configure(state=tk.NORMAL)
        self.body_detail.delete("1.0", tk.END)
        self.body_detail.insert(tk.END, "\n".join(lines))
        self.body_detail.configure(state=tk.DISABLED)

    def _current_recon_report(self):
        return recon_report(
            getattr(self.app, "current_sys", "Unknown"), self._last_survey_bodies,
            int(getattr(self.app, "scanned", 0) or 0),
            int(getattr(self.app, "total", 0) or 0),
            getattr(self.app, "system_traffic", {}) or {},
        )

    def _update_recon_status(self):
        if not hasattr(self, "recon_status"):
            return
        report = self._current_recon_report()
        gaps = len(report.get("gaps") or [])
        self.recon_status.config(
            text=f"RECON · {report['score']}/100 {report['grade'].upper()} · {gaps} gap(s)",
            fg=self.UI_OK if report["score"] >= 85 else COLOR_ORANGE if report["score"] >= 40 else self.UI_MUTED,
        )

    def _save_recon_candidate(self):
        tracker = getattr(self.app, "deep_survey", None)
        if not tracker:
            return
        report = self._current_recon_report()
        tracker.save_candidate(report)
        logbook = getattr(self.app, "captains_log", None)
        if logbook and hasattr(logbook, "add_manual_highlight"):
            logbook.add_manual_highlight(
                "RECON", f"Recon candidate saved: {report['system']}",
                f"Survey readiness {report['score']}/100",
            )
        if hasattr(self.app, "add_event_feed_entry"):
            self.app.add_event_feed_entry(
                "SURVEY", f"Recon candidate saved: {report['system']} ({report['score']}/100)",
                severity="INFO",
            )
        manager = getattr(self.app, "expedition_manager", None)
        if manager:
            completed = manager.observe_recon(report["system"], report["score"])
            if completed and hasattr(self.app, "add_event_feed_entry"):
                self.app.add_event_feed_entry(
                    "EXPEDITION", f"Objective complete: {completed[0]}", severity="INFO",
                )
            self._on_expedition_changed()
        self._update_recon_status()

    def _copy_recon_dossier(self):
        tracker = getattr(self.app, "deep_survey", None)
        if not tracker:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(tracker.recon_markdown(self._current_recon_report()))

    def _bookmark_selected_body(self):
        selected = self.bodies_tree.selection()
        item = self.body_items_by_iid.get(selected[0]) if selected else None
        if not item:
            return
        system = getattr(self.app, "current_sys", "")
        body = item.get("full_name") or item.get("name") or "Body"
        kind = "Biology" if self._safe_int(item.get("bio_count")) else (
            "Valuable" if self._is_valuable(item) else "Body"
        )
        self._add_expedition_bookmark(
            kind, system=system, body=body, title=body,
            tags=[kind.casefold(), "survey"], source="system-survey",
            position=getattr(self.app, "current_coords", None),
        )

    def _bookmark_discovery(self, row):
        raw = row.get("raw") or {}
        system = row.get("system") or ""
        subject = row.get("subject") or row.get("kind") or "Discovery"
        position = raw.get("pos")
        if not position and str(system).casefold() == str(getattr(self.app, "current_sys", "")).casefold():
            position = getattr(self.app, "current_coords", None)
        self._add_expedition_bookmark(
            row.get("kind") or "Discovery", system=system,
            body=raw.get("body") or "", title=subject,
            tags=[str(row.get("kind") or "discovery").casefold()],
            source="discoveries", position=position,
        )

    def _add_expedition_bookmark(self, kind, **kwargs):
        manager = getattr(self.app, "expedition_manager", None)
        if not manager:
            return None
        bookmark = manager.add_bookmark(kind, **kwargs)
        if hasattr(self.app, "add_event_feed_entry"):
            self.app.add_event_feed_entry(
                "EXPEDITION", f"Bookmark saved: {bookmark.get('title')}", severity="INFO",
            )
        self._on_expedition_changed()
        return bookmark

    def _open_map_record(self, record):
        if self._map_popout_is_open():
            self._dock_map_popout()
        kind = str((record or {}).get("kind") or "")
        if kind in {"Bookmark", "Recon"}:
            self.show_section("mission")
            bookmark_id = (record or {}).get("bookmark_id")
            if bookmark_id and self.expedition_mission_view:
                self.expedition_mission_view.open_bookmark(bookmark_id)
            return
        self.tabs.select(self.discoveries_workspace)
        if self.discoveries_view:
            self.discoveries_view.refresh(self.system_history_rows, self.ledger_rows)
            self.discoveries_view.select_record(
                kind=kind, system=(record or {}).get("system"),
                subject=(record or {}).get("subject"),
            )

    def _trip_card_text(self, session_stats=None):
        jumps = int(getattr(self.app, "session_jump_count", 0) or 0)
        ly = float(getattr(self.app, "session_ly", 0.0) or 0.0)
        start = float(getattr(self.app, "session_start_ts", time.time()) or time.time())
        age_min = max(0, int((time.time() - start) / 60))
        session_stats = session_stats or self._session_stats()
        return f"{jumps} jumps | {ly:.1f} ly | {session_stats['value']:,} cr\n{session_stats['systems']} systems | {age_min} min"

    def _render_route(self):
        for item_id in self.route_tree.get_children():
            self.route_tree.delete(item_id)
        entries = self._route_entries()
        current = getattr(self.app, "current_sys", None)
        next_name = self._next_route_system()
        local_status = self._route_status_map([entry.get("StarSystem") for entry in entries])
        for idx, entry in enumerate(entries, 1):
            name = entry.get("StarSystem") or ""
            raw_star = entry.get("StarClass") or "-"
            star = star_type_label(raw_star, "-")
            scoop = "Yes" if raw_star[:1].upper() in SCOOPABLE_STAR_CLASSES else ("-" if raw_star == "-" else "No")
            distance = self._distance_from_current(entry)
            edsm = self._edsm_summary(name)
            edsm_value = self._format_credits(edsm.get("estimatedValueMapped") or edsm.get("estimatedValue")) if edsm else "..."
            valuable = str(edsm.get("valuableCount", 0)) if edsm else "..."
            status_parts = [local_status.get(name, "Unvisited")]
            tags = []
            if name == current:
                status_parts.append("Current")
                tags.append("current")
            elif name == next_name:
                status_parts.append("Next")
                tags.append("next")
            if not edsm:
                tags.append("pending")
            status = " / ".join(part for part in status_parts if part)
            self.route_tree.insert("", tk.END, values=(idx, name, star, scoop, distance, edsm_value, valuable, status), tags=tuple(tags))

    def _format_credits(self, value):
        try:
            value = int(value or 0)
        except Exception:
            return "-"
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}m"
        if value >= 1_000:
            return f"{value / 1_000:.0f}k"
        return str(value)

    def _route_status_map(self, system_names):
        wanted = [name for name in system_names if name]
        if not wanted:
            return {}
        result = {name: "Unvisited" for name in wanted}
        acquired = False
        try:
            acquired = self.app.db_lock.acquire(blocking=False)
            if not acquired:
                cached = getattr(self, "_last_route_status", {}) or {}
                return {name: cached.get(name, result[name]) for name in wanted}
            cur = self.app.conn.cursor()
            for name in wanted:
                cur.execute("SELECT total, scanned_count FROM systems WHERE name=?", (name,))
                row = cur.fetchone()
                if not row:
                    continue
                total = int(row[0] or 0)
                scanned = int(row[1] or 0)
                if total > 0 and scanned >= total:
                    result[name] = "Complete"
                elif scanned > 0 or total > 0:
                    result[name] = f"Partial {scanned}/{total}"
                else:
                    result[name] = "Visited"
            self._last_route_status = dict(result)
        except Exception:
            pass
        finally:
            if acquired:
                try:
                    self.app.db_lock.release()
                except Exception:
                    pass
        return result

    def _distance_from_current(self, entry):
        pos = entry.get("StarPos")
        cur = getattr(self.app, "current_coords", None)
        if not isinstance(pos, (list, tuple)) or len(pos) < 3:
            return "-"
        if not isinstance(cur, (list, tuple)) or len(cur) < 3:
            return "-"
        try:
            dist = math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(pos[:3], cur[:3])))
            return f"{dist:.1f} ly"
        except Exception:
            return "-"

    def _cache_path(self):
        try:
            return self.app._profile_path("exploration_edsm_cache.json")
        except Exception:
            return os.path.abspath("exploration_edsm_cache.json")

    def _trip_archive_path(self):
        try:
            return self.app._profile_path("exploration_trip_archive.json")
        except Exception:
            return os.path.abspath("exploration_trip_archive.json")

    def _load_edsm_cache(self):
        path = self._cache_path()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
        except Exception:
            pass
        return {}

    def _save_edsm_cache(self):
        path = self._cache_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._edsm_cache, f, indent=2)
        except Exception:
            pass

    def _edsm_summary(self, system_name):
        if not system_name:
            return None
        entry = self._edsm_cache.get(system_name)
        if not isinstance(entry, dict) or not entry.get("ok"):
            return None
        return entry

    def _request_route_enrichment(self):
        now = time.time()
        with self._edsm_lock:
            if self._edsm_worker_active or (now - self._edsm_last_request_ts) < 2.0:
                return
        entries = self._route_entries()
        current = getattr(self.app, "current_sys", None)
        if current and current not in ("---", "Unknown"):
            entries = [{"StarSystem": current}] + entries
        if not entries:
            return
        targets = []
        with self._edsm_lock:
            for entry in entries:
                name = entry.get("StarSystem")
                if not name or name in self._edsm_pending:
                    continue
                cached = self._edsm_cache.get(name) or {}
                age = now - float(cached.get("updated", 0) or 0)
                if cached.get("ok") and age < 7 * 24 * 3600:
                    continue
                if cached and not cached.get("ok") and age < 3600:
                    continue
                targets.append(name)
                self._edsm_pending.add(name)
                if len(targets) >= 8:
                    break
        if targets:
            with self._edsm_lock:
                self._edsm_worker_active = True
                self._edsm_last_request_ts = now
            threading.Thread(target=self._fetch_edsm_values, args=(targets,), daemon=True).start()

    def _fetch_edsm_values(self, systems):
        changed = False
        try:
            for system_name in systems:
                payload = {"updated": time.time(), "ok": False}
                try:
                    resp = requests.get(
                        "https://www.edsm.net/api-system-v1/estimated-value",
                        params={"systemName": system_name},
                        timeout=8,
                        headers={"User-Agent": "VoidCompass"},
                    )
                    if resp.ok and "application/json" in resp.headers.get("content-type", ""):
                        data = resp.json()
                        valuable = data.get("valuableBodies") or []
                        payload.update({
                            "ok": True,
                            "estimatedValue": int(data.get("estimatedValue") or 0),
                            "estimatedValueMapped": int(data.get("estimatedValueMapped") or 0),
                            "valuableCount": len(valuable),
                            "valuableBodies": valuable[:20],
                            "url": data.get("url") or "",
                        })
                except Exception as exc:
                    self._log_error(f"EDSM value lookup failed for {system_name}: {exc}")
                with self._edsm_lock:
                    self._edsm_cache[system_name] = payload
                    self._edsm_pending.discard(system_name)
                    changed = True
        finally:
            with self._edsm_lock:
                self._edsm_worker_active = False
        if changed:
            self._save_edsm_cache()
            try:
                if hasattr(self.app, "_refresh_exploration_window"):
                    self.app._refresh_exploration_window()
            except Exception:
                pass

    def _load_trip_archive(self):
        path = self._trip_archive_path()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except Exception:
            pass
        return []

    def _save_trip_archive(self, archive):
        path = self._trip_archive_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(archive[-100:], f, indent=2)
        except Exception:
            pass

    def _history_detail_payload(self, items):
        stars = []
        bodies = []
        bio = []
        valuable = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("full_name") or item.get("name") or "Body"
            body_class = (
                star_type_label(item.get("star_type"), include_star=True)
                if item.get("star_type") else item.get("planet_class") or item.get("class") or "-"
            )
            value = self._item_value(item)
            row = {
                "name": name,
                "class": body_class,
                "value": value,
                "status": self._body_status(item),
                "bio_count": self._safe_int(item.get("bio_count")),
                "geo_count": self._safe_int(item.get("geo_count")),
                "genus": self._genus_labels(item),
                "mapped": bool(item.get("dss_complete") or item.get("was_mapped")),
                "distance": item.get("distance_to_arrival"),
            }
            if item.get("is_star"):
                stars.append(row)
            else:
                bodies.append(row)
                if row["bio_count"] or row["genus"] or self._safe_int(item.get("organic_complete_count")):
                    bio.append(row)
                if self._is_valuable(item):
                    valuable.append(row)
        bodies.sort(key=lambda row: (row["name"], row["class"]))
        valuable.sort(key=lambda row: row["value"], reverse=True)
        bio.sort(key=lambda row: (-row["bio_count"], row["name"]))
        return {
            "stars": stars,
            "bodies": bodies[:80],
            "bio": bio[:40],
            "valuable": valuable[:40],
        }

    def _history_row_from_items(self, system, address, last_seen, scanned, total, items):
        stars = sorted({
            star_type_label(item.get("star_type"))
            for item in items
            if isinstance(item, dict) and item.get("is_star") and item.get("star_type")
        })
        value = 0
        valuable = 0
        bio_signals = 0
        bio_bodies = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            value += self._item_value(item)
            if self._is_valuable(item):
                valuable += 1
            bio_count = self._safe_int(item.get("bio_count"))
            organic_done = self._safe_int(item.get("organic_complete_count"))
            if bio_count or organic_done or self._genus_labels(item):
                bio_bodies += 1
            bio_signals += bio_count
        return {
            "system": system,
            "system_address": address,
            "last_seen_ts": float(last_seen or 0),
            "star_class": stars[0] if stars else "-",
            "stars": stars,
            "scanned_bodies": int(scanned or len(items) or 0),
            "total_bodies": int(total or 0),
            "estimated_value": int(value or 0),
            "valuable_bodies": int(valuable or 0),
            "bio_signals": int(bio_signals or 0),
            "bio_bodies": int(bio_bodies or 0),
            "source": "DB",
            "details": self._history_detail_payload(items),
        }

    def _refresh_system_history_rows(self, current, bodies, current_value, valuable_count, bio_summary, scanned, total):
        now = time.time()
        if (now - getattr(self, "_last_history_refresh_ts", 0.0)) < 1.5 and self.system_history_rows:
            self._overlay_current_history_row(current, bodies, current_value, valuable_count, bio_summary, scanned, total)
            return
        self._last_history_refresh_ts = now

        visits = []
        system_totals = {}
        grouped_items = {}
        acquired = False
        try:
            acquired = self.app.db_lock.acquire(blocking=False)
            if not acquired:
                self._overlay_current_history_row(current, bodies, current_value, valuable_count, bio_summary, scanned, total)
                return
            cur = self.app.conn.cursor()
            cur.execute("SELECT system_name, system_address, last_visited_at FROM visited_systems")
            visits = cur.fetchall()
            cur.execute("SELECT name, total, scanned_count FROM systems")
            system_totals = {
                name: (int(total or 0), int(scanned_count or 0))
                for name, total, scanned_count in cur.fetchall()
            }
            cur.execute("SELECT system_name, data_json FROM scan_hud_items")
            for system_name, payload in cur.fetchall():
                try:
                    item = json.loads(payload)
                except Exception:
                    continue
                if isinstance(item, dict):
                    grouped_items.setdefault(system_name, []).append(item)
        except Exception:
            self._overlay_current_history_row(current, bodies, current_value, valuable_count, bio_summary, scanned, total)
            return
        finally:
            if acquired:
                try:
                    self.app.db_lock.release()
                except Exception:
                    pass

        rows = []
        for system, address, last_seen in visits:
            if not system:
                continue
            total_count, scanned_count = system_totals.get(system, (0, 0))
            rows.append(
                self._history_row_from_items(
                    system,
                    address,
                    last_seen,
                    scanned_count,
                    total_count,
                    grouped_items.get(system, []),
                )
            )
        self.system_history_rows = rows
        self._overlay_current_history_row(current, bodies, current_value, valuable_count, bio_summary, scanned, total)

    def _overlay_current_history_row(self, current, bodies, current_value, valuable_count, bio_summary, scanned, total):
        if not current or current in ("---", "Unknown"):
            return
        rows = [row for row in self.system_history_rows if row.get("system") != current]
        stars = sorted({
            star_type_label(item.get("star_type"))
            for item in bodies
            if isinstance(item, dict) and item.get("is_star") and item.get("star_type")
        })
        if not stars and getattr(self.app, "star_class", None):
            stars = [star_type_label(getattr(self.app, "star_class"))]
        rows.append({
            "system": current,
            "system_address": getattr(self.app, "current_system_address", None),
            "last_seen_ts": time.time(),
            "star_class": star_type_label(
                getattr(self.app, "star_class", ""), stars[0] if stars else "-",
            ),
            "stars": stars,
            "scanned_bodies": int(scanned or 0),
            "total_bodies": int(total or 0),
            "estimated_value": int(current_value or 0),
            "valuable_bodies": int(valuable_count or 0),
            "bio_signals": int(bio_summary.get("bio_signals", 0) or 0),
            "bio_bodies": int(bio_summary.get("bio_bodies", 0) or 0),
            "source": "Live",
            "details": self._history_detail_payload(bodies),
        })
        self.system_history_rows = rows

    def _db_stats(self):
        stats = {
            "systems": 0,
            "visits": 0,
            "bodies": 0,
            "value": 0,
            "valuable": 0,
        }
        acquired = False
        try:
            acquired = self.app.db_lock.acquire(blocking=False)
            if not acquired:
                return dict(self._last_db_stats)
            cur = self.app.conn.cursor()
            cur.execute("SELECT COUNT(*) FROM systems")
            stats["systems"] = int(cur.fetchone()[0] or 0)
            cur.execute("SELECT COUNT(*) FROM visited_systems")
            stats["visits"] = int(cur.fetchone()[0] or 0)
            cur.execute("SELECT data_json FROM scan_hud_items")
            for (payload,) in cur.fetchall():
                try:
                    item = json.loads(payload)
                except Exception:
                    continue
                if not isinstance(item, dict):
                    continue
                stats["bodies"] += 1
                value = self._item_value(item)
                stats["value"] += value
                if self._is_valuable(item):
                    stats["valuable"] += 1
            self._last_db_stats = dict(stats)
        except Exception:
            pass
        finally:
            if acquired:
                try:
                    self.app.db_lock.release()
                except Exception:
                    pass
        return stats

    def _refresh_ledger(self):
        now = time.time()
        if now - getattr(self, "_last_ledger_refresh_ts", 0.0) < 1.5:
            self._render_ledger()
            return
        rows = []
        acquired = False
        try:
            acquired = self.app.db_lock.acquire(blocking=False)
            if not acquired:
                self._render_ledger()
                return
            cur = self.app.conn.execute("SELECT system_name, data_json FROM scan_hud_items")
            for system, payload in cur.fetchall():
                try:
                    item = json.loads(payload)
                except Exception:
                    continue
                if not isinstance(item, dict) or item.get("is_star"):
                    continue
                if not self._is_valuable(item):
                    continue
                rows.append({
                    "system": system,
                    "body": item.get("full_name") or item.get("name") or "",
                    "class": item.get("planet_class") or item.get("class") or "",
                    "value": self._item_value(item),
                    "mapped": "Yes" if item.get("dss_complete") or item.get("was_mapped") else "No",
                    "flags": self._flag_text(item),
                })
            self._last_ledger_refresh_ts = now
        except Exception:
            rows = list(getattr(self, "ledger_rows", []) or [])
        finally:
            if acquired:
                try:
                    self.app.db_lock.release()
                except Exception:
                    pass
        self.ledger_rows = sorted(rows, key=lambda row: row["value"], reverse=True)
        self._render_ledger()

    def _render_ledger(self):
        if not hasattr(self, "ledger_tree"):
            return
        for item_id in self.ledger_tree.get_children():
            self.ledger_tree.delete(item_id)
        query = (self.ledger_filter_var.get() or "").strip().lower()
        shown = []
        for row in self.ledger_rows:
            haystack = " ".join(str(v) for v in row.values()).lower()
            if query and query not in haystack:
                continue
            shown.append(row)
            self.ledger_tree.insert(
                "",
                tk.END,
                values=(row["system"], row["body"], row["class"], f"{row['value']:,}", row["mapped"], row["flags"]),
            )
        self.ledger_summary.config(text=f"{len(shown)} bodies | {sum(row['value'] for row in shown):,} cr")

    def _copy_ledger_summary(self):
        lines = ["System Value Ledger"]
        for row in self.ledger_rows[:40]:
            lines.append(f"{row['system']} | {row['body']} | {row['class']} | {row['value']:,} cr | {row['flags']}")
        if len(lines) == 1:
            lines.append("(nothing tracked yet)")
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))

    def _session_stats(self):
        systems = set(getattr(self.app, "session_systems", set()) or set())
        current = getattr(self.app, "current_sys", None)
        if current and current not in ("---", "Unknown"):
            systems.add(current)
        stats = {"systems": len(systems), "bodies": 0, "value": 0, "valuable": 0}
        if not systems:
            self._last_session_stats = dict(stats)
            return stats
        acquired = False
        try:
            acquired = self.app.db_lock.acquire(blocking=False)
            if not acquired:
                cached = dict(self._last_session_stats)
                cached["systems"] = stats["systems"]
                return cached
            cur = self.app.conn.cursor()
            for system in systems:
                cur.execute("SELECT data_json FROM scan_hud_items WHERE system_name=?", (system,))
                for (payload,) in cur.fetchall():
                    try:
                        item = json.loads(payload)
                    except Exception:
                        continue
                    if not isinstance(item, dict):
                        continue
                    stats["bodies"] += 1
                    stats["value"] += self._item_value(item)
                    if self._is_valuable(item):
                        stats["valuable"] += 1
            self._last_session_stats = dict(stats)
        except Exception:
            pass
        finally:
            if acquired:
                try:
                    self.app.db_lock.release()
                except Exception:
                    pass
        return stats

    def _render_history(self, current_value, valuable_count, session_stats=None):
        session_stats = session_stats or self._session_stats()
        stats = self._db_stats()
        lines = [
            f"Current system: {getattr(self.app, 'current_sys', '---')}",
            f"Current system estimated scan value: {current_value:,} cr",
            f"Current valuable bodies: {valuable_count}",
            "",
            f"Session jumps: {int(getattr(self.app, 'session_jump_count', 0) or 0)}",
            f"Session distance: {float(getattr(self.app, 'session_ly', 0.0) or 0.0):.1f} ly",
            f"Session systems: {session_stats['systems']:,}",
            f"Session scan bodies stored: {session_stats['bodies']:,}",
            f"Session estimated scan value: {session_stats['value']:,} cr",
            f"Session valuable bodies: {session_stats['valuable']:,}",
            "",
            f"Profile systems stored: {stats['systems']:,}",
            f"Profile systems visited: {stats['visits']:,}",
            f"Profile scan bodies stored: {stats['bodies']:,}",
            f"Profile estimated scan value: {stats['value']:,} cr",
            f"Profile valuable bodies: {stats['valuable']:,}",
        ]
        archive = self._load_trip_archive()
        if archive:
            lines.extend(["", "Archived trips:"])
            for trip in reversed(archive[-8:]):
                ended = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(trip.get("ended_ts", 0) or 0)))
                lines.append(
                    f"- {ended} | {trip.get('systems', 0)} systems | "
                    f"{trip.get('jumps', 0)} jumps | {float(trip.get('ly', 0.0) or 0.0):.1f} ly | "
                    f"{int(trip.get('value', 0) or 0):,} cr"
                )
        self.history_text.configure(state=tk.NORMAL)
        self.history_text.delete("1.0", tk.END)
        self.history_text.insert(tk.END, "\n".join(lines))
        self.history_text.configure(state=tk.DISABLED)

    def _render_captains_log(self):
        if not hasattr(self, "captains_log_tree"):
            return
        selected_started = None
        selected = self.captains_log_tree.selection()
        if selected:
            row = self.captains_log_rows.get(selected[0])
            selected_started = row.get("started") if row else None
        for iid in self.captains_log_tree.get_children():
            self.captains_log_tree.delete(iid)
        self.captains_log_rows = {}
        journal = getattr(self.app, "captains_log", None)
        sessions = journal.sessions() if journal else []
        chosen = None
        for session in sessions:
            started = str(session.get("started") or "")
            route = f"{session.get('start_system') or '?'} → {session.get('end_system') or '?'}"
            discoveries = int(session.get("codex") or 0) + int(session.get("bio_analyses") or 0)
            sales = int(session.get("exploration_sales") or 0) + int(session.get("biology_sales") or 0)
            iid = self.captains_log_tree.insert("", tk.END, values=(
                started[:16].replace("T", " "), route, int(session.get("jumps") or 0),
                discoveries, self._format_credits(sales),
            ))
            self.captains_log_rows[iid] = session
            if selected_started and started == selected_started:
                chosen = iid
        self.captains_log_summary.config(text=f"{len(sessions)} retained sessions | bounded local journal")
        children = self.captains_log_tree.get_children()
        if chosen or children:
            iid = chosen or children[0]
            self.captains_log_tree.selection_set(iid)
            self._show_captains_log(self.captains_log_rows.get(iid))
        else:
            self._show_captains_log(None)

    def _on_captains_log_selected(self, _event=None):
        selected = self.captains_log_tree.selection()
        self._show_captains_log(self.captains_log_rows.get(selected[0]) if selected else None)

    def _show_captains_log(self, session):
        journal = getattr(self.app, "captains_log", None)
        text = journal.markdown(session) if journal and session else "No journal session has been recorded yet."
        self.captains_log_text.configure(state=tk.NORMAL)
        self.captains_log_text.delete("1.0", tk.END)
        self.captains_log_text.insert(tk.END, text)
        self.captains_log_text.configure(state=tk.DISABLED)

    def _copy_captains_log(self):
        selected = self.captains_log_tree.selection()
        session = self.captains_log_rows.get(selected[0]) if selected else None
        journal = getattr(self.app, "captains_log", None)
        text = journal.markdown(session) if journal and session else ""
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

    def _selected_expedition_session(self):
        selected = self.captains_log_tree.selection() if hasattr(self, "captains_log_tree") else ()
        session = self.captains_log_rows.get(selected[0]) if selected else None
        if session:
            return session
        journal = getattr(self.app, "captains_log", None)
        sessions = journal.sessions() if journal else []
        return sessions[0] if sessions else {}

    def _expedition_report(self, expedition_id=None):
        manager = getattr(self.app, "expedition_manager", None)
        named_expedition = (
            manager.get(expedition_id) if manager and expedition_id
            else manager.active() if manager else None
        )
        session = (
            manager.report_session(named_expedition)
            if manager and named_expedition else self._selected_expedition_session()
        )
        active_session = bool(session and not session.get("ended"))
        tracker = getattr(self.app, "deep_survey", None)
        snapshot = tracker.snapshot() if tracker else {}
        current = (
            getattr(self.app, "current_sys", "")
            if active_session or not session else session.get("end_system") or ""
        )
        bodies = self._last_survey_bodies if active_session or not session else []
        if named_expedition:
            session_systems = list((named_expedition.get("stats") or {}).get("systems") or [])
            expedition_keys = {str(name).casefold() for name in session_systems}
            value_rows = [
                row for row in self.ledger_rows
                if str(row.get("system") or "").casefold() in expedition_keys
            ]
            snapshot = dict(snapshot)
            snapshot["candidates"] = [
                row for row in snapshot.get("candidates") or []
                if str(row.get("system") or "").casefold() in expedition_keys
            ]
        else:
            session_systems = (
                sorted(set(getattr(self.app, "session_systems", set()) or set()))
                if active_session else None
            )
            value_rows = self.ledger_rows
        report = expedition_report_markdown(
            snapshot=snapshot,
            session=session,
            current_system=current,
            current_scan={
                "scanned": int(getattr(self.app, "scanned", 0) or 0) if bodies else 0,
                "total": int(getattr(self.app, "total", 0) or 0) if bodies else 0,
                "value": sum(self._item_value(item) for item in bodies),
            },
            system_rows=self.system_history_rows,
            value_rows=value_rows,
            wonders=wonder_rows(bodies),
            session_systems=session_systems,
        )
        if named_expedition and manager:
            _first_line, separator, remainder = report.partition("\n")
            report = (
                f"# VoidCompass Expedition Report — {named_expedition.get('name') or 'Unnamed'}"
                + (separator + remainder if separator else "")
            )
            report += "\n" + manager.markdown_appendix(named_expedition)
        return report

    def _copy_expedition_report(self):
        report = self._expedition_report()
        self.root.clipboard_clear()
        self.root.clipboard_append(report)
        if hasattr(self.app, "add_event_feed_entry"):
            self.app.add_event_feed_entry(
                "SURVEY", "Expedition report copied to clipboard", severity="INFO",
            )

    def _copy_named_expedition_report(self, expedition_id):
        report = self._expedition_report(expedition_id=expedition_id)
        self.root.clipboard_clear()
        self.root.clipboard_append(report)
        if hasattr(self.app, "add_event_feed_entry"):
            self.app.add_event_feed_entry(
                "EXPEDITION", "Full named-expedition report copied", severity="INFO",
            )

    def _save_expedition_report(self):
        manager = getattr(self.app, "expedition_manager", None)
        named_expedition = manager.active() if manager else None
        session = manager.report_session(named_expedition) if named_expedition else self._selected_expedition_session()
        report_date = str(session.get("started") or time.strftime("%Y-%m-%d"))[:10]
        report_name = named_expedition.get("name") if named_expedition else "Expedition"
        safe_name = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in str(report_name or "Expedition")
        )[:60]
        path = filedialog.asksaveasfilename(
            parent=self.win,
            title="Save Expedition Report",
            initialfile=f"VoidCompass-{safe_name}-{report_date}.md",
            defaultextension=".md",
            filetypes=(("Markdown", "*.md"), ("Text", "*.txt"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self._expedition_report())
        except OSError as exc:
            messagebox.showerror("Save Expedition Report", f"Could not save the report:\n{exc}", parent=self.win)
            return
        if hasattr(self.app, "add_event_feed_entry"):
            self.app.add_event_feed_entry(
                "SURVEY", f"Expedition report saved: {os.path.basename(path)}", severity="INFO",
            )

    def _format_history_time(self, ts):
        try:
            value = float(ts or 0)
            if value <= 0:
                return "-"
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(value))
        except Exception:
            return "-"

    def _render_system_history(self):
        if not hasattr(self, "system_history_tree"):
            return
        selected_system = None
        try:
            selected = self.system_history_tree.selection()
            if selected:
                selected_row = self.system_history_by_iid.get(selected[0])
                selected_system = selected_row.get("system") if selected_row else None
        except Exception:
            selected_system = None
        for item_id in self.system_history_tree.get_children():
            self.system_history_tree.delete(item_id)
        self.system_history_by_iid = {}
        query = (self.system_history_filter_var.get() or "").strip().lower()
        current = getattr(self.app, "current_sys", None)
        rows = sorted(
            self.system_history_rows,
            key=lambda row: float(row.get("last_seen_ts", 0) or 0),
            reverse=True,
        )
        shown = []
        for row in rows:
            haystack = " ".join(
                str(row.get(key, ""))
                for key in ("system", "star_class", "stars", "system_address")
            ).lower()
            if query and query not in haystack:
                continue
            shown.append(row)
            tags = []
            if row.get("system") == current:
                tags.append("current")
            elif int(row.get("valuable_bodies", 0) or 0) > 0:
                tags.append("valuable")
            elif int(row.get("bio_signals", 0) or 0) > 0:
                tags.append("bio")
            star = row.get("star_class") or "-"
            stars = row.get("stars") or []
            if stars and star in ("", "-"):
                star = "/".join(stars[:3])
            bodies = f"{int(row.get('scanned_bodies', 0) or 0)}/{int(row.get('total_bodies', 0) or 0)}"
            bio = f"{int(row.get('bio_bodies', 0) or 0)}/{int(row.get('bio_signals', 0) or 0)}"
            iid = self.system_history_tree.insert(
                "",
                tk.END,
                values=(
                    self._format_history_time(row.get("last_seen_ts")),
                    row.get("system") or "-",
                    star,
                    bodies,
                    self._format_credits(row.get("estimated_value")),
                    bio,
                    int(row.get("valuable_bodies", 0) or 0),
                    row.get("source") or "DB",
                ),
                tags=tuple(tags),
            )
            self.system_history_by_iid[iid] = row
            if selected_system and row.get("system") == selected_system:
                self.system_history_tree.selection_set(iid)
        total_value = sum(int(row.get("estimated_value", 0) or 0) for row in shown)
        self.system_history_summary.config(
            text=f"{len(shown)} systems | {self._format_credits(total_value)} | profile DB"
        )
        selected = self.system_history_tree.selection()
        if selected:
            self._show_system_history_detail(self.system_history_by_iid.get(selected[0]))
        elif shown:
            first = self.system_history_tree.get_children()[0]
            self.system_history_tree.selection_set(first)
            self._show_system_history_detail(self.system_history_by_iid.get(first))
        else:
            self._show_system_history_detail(None)

    def _on_system_history_selected(self, _event=None):
        selected = self.system_history_tree.selection()
        self._show_system_history_detail(self.system_history_by_iid.get(selected[0]) if selected else None)

    def _show_system_history_detail(self, row):
        if not hasattr(self, "system_history_detail"):
            return
        lines = []
        if row:
            details = row.get("details") or {}
            lines.extend([
                f"{row.get('system') or '-'}",
                f"Last visit: {self._format_history_time(row.get('last_seen_ts'))} | Source: {row.get('source') or 'DB'}",
                f"Scan: {int(row.get('scanned_bodies', 0) or 0)}/{int(row.get('total_bodies', 0) or 0)} bodies | Value: {self._format_credits(row.get('estimated_value'))}",
                f"Bio: {int(row.get('bio_bodies', 0) or 0)} bodies / {int(row.get('bio_signals', 0) or 0)} signals | Valuable: {int(row.get('valuable_bodies', 0) or 0)}",
                "",
            ])
            stars = details.get("stars") or []
            lines.append("Stars:")
            if stars:
                for star in stars[:8]:
                    lines.append(f"- {star.get('name')} | {star.get('class')} | {self._format_credits(star.get('value'))}")
            else:
                star_class = row.get("star_class") or "-"
                lines.append(f"- {star_class}")

            valuable = details.get("valuable") or []
            lines.append("")
            lines.append("Valuable bodies:")
            if valuable:
                for body in valuable[:10]:
                    lines.append(f"- {body.get('name')} | {body.get('class')} | {self._format_credits(body.get('value'))} | {body.get('status')}")
            else:
                lines.append("- None recorded")

            bio = details.get("bio") or []
            lines.append("")
            lines.append("Bio data:")
            if bio:
                for body in bio[:12]:
                    genus = ", ".join(body.get("genus") or []) or "-"
                    lines.append(f"- {body.get('name')} | bio {body.get('bio_count', 0)} | {genus}")
            else:
                lines.append("- None recorded")

            bodies = details.get("bodies") or []
            lines.append("")
            lines.append("Scanned bodies:")
            if bodies:
                for body in bodies[:18]:
                    mapped = "mapped" if body.get("mapped") else "scan"
                    lines.append(f"- {body.get('name')} | {body.get('class')} | {mapped} | {self._format_credits(body.get('value'))}")
                if len(bodies) > 18:
                    lines.append(f"- ... {len(bodies) - 18} more")
            else:
                lines.append("- None recorded")
        else:
            lines = ["Select a system history row to view stars, scans, values, and bio data."]
        self.system_history_detail.configure(state=tk.NORMAL)
        self.system_history_detail.delete("1.0", tk.END)
        self.system_history_detail.insert(tk.END, "\n".join(lines))
        self.system_history_detail.configure(state=tk.DISABLED)

    def _copy_system_history(self):
        rows = sorted(
            self.system_history_rows,
            key=lambda row: float(row.get("last_seen_ts", 0) or 0),
            reverse=True,
        )
        lines = ["Exploration System History"]
        for row in rows[:80]:
            lines.append(
                f"{self._format_history_time(row.get('last_seen_ts'))} | "
                f"{row.get('system') or '-'} | "
                f"Star {row.get('star_class') or '-'} | "
                f"{int(row.get('scanned_bodies', 0) or 0)}/{int(row.get('total_bodies', 0) or 0)} bodies | "
                f"{self._format_credits(row.get('estimated_value'))} | "
                f"Bio {int(row.get('bio_bodies', 0) or 0)}/{int(row.get('bio_signals', 0) or 0)}"
            )
        if len(lines) == 1:
            lines.append("(nothing tracked yet)")
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))

    def _copy_summary(self):
        current = getattr(self.app, "current_sys", "---") or "---"
        lines = [
            f"Exploration summary: {current}",
            f"Scan: {getattr(self.app, 'scanned', 0)}/{getattr(self.app, 'total', 0)}",
            f"Route next: {self._next_route_system() or '-'}",
            f"Session: {int(getattr(self.app, 'session_jump_count', 0) or 0)} jumps, {float(getattr(self.app, 'session_ly', 0.0) or 0.0):.1f} ly",
        ]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))

    def _reset_session(self):
        session_stats = self._session_stats()
        systems = sorted(set(getattr(self.app, "session_systems", set()) or set()))
        current = getattr(self.app, "current_sys", None)
        if current and current not in ("---", "Unknown") and current not in systems:
            systems.append(current)
        if session_stats["systems"] or int(getattr(self.app, "session_jump_count", 0) or 0):
            archive = self._load_trip_archive()
            archive.append({
                "started_ts": float(getattr(self.app, "session_start_ts", time.time()) or time.time()),
                "ended_ts": time.time(),
                "jumps": int(getattr(self.app, "session_jump_count", 0) or 0),
                "ly": float(getattr(self.app, "session_ly", 0.0) or 0.0),
                "systems": session_stats["systems"],
                "bodies": session_stats["bodies"],
                "value": session_stats["value"],
                "valuable": session_stats["valuable"],
                "system_names": systems,
            })
            self._save_trip_archive(archive)
        self.app.session_start_ts = time.time()
        self.app.session_jump_count = 0
        self.app.session_ly = 0.0
        current = getattr(self.app, "current_sys", None)
        self.app.session_systems = {current} if current and current not in ("---", "Unknown") else set()
        self.refresh()

    def _copy_next_route(self):
        next_name = self._next_route_system()
        if not next_name:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(next_name)

    def _open_current_edsm(self):
        current = getattr(self.app, "current_sys", None)
        if current and current != "---":
            webbrowser.open(f"https://www.edsm.net/show-system?systemName={current.replace(' ', '+')}")

    def _on_close(self):
        self._closing = True
        self._remember_active_page()
        self._dock_map_popout(sync=False)
        plotter = self.route_plotter
        try:
            if plotter and self._widget_alive(plotter.win):
                plotter.on_close()
        except Exception:
            pass
        self.route_plotter = None
        if getattr(self.app, "route_plotter", None) is plotter:
            self.app.route_plotter = None
        try:
            if self.win and self.win.winfo_exists():
                self.config["exploration_window_geometry"] = self.win.geometry()
                persist = getattr(self.app, "_persist_config", None)
                if callable(persist):
                    persist()
                self.win.destroy()
        except Exception:
            pass
        self.win = None
