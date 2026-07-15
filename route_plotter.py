import tkinter as tk
import json
import os
import csv
import time
import threading
import requests
from tkinter import messagebox, filedialog
from tkinter import ttk
from config import COLOR_BG, COLOR_PANEL, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config
from ui_theme import THEME, ThemedWindowMixin, apply_window, button, configure_ttk, scrollbar, window_surface
from waypoint_manager import WaypointManager

COLOR_BG = THEME.bg
COLOR_PANEL = THEME.panel
COLOR_ACCENT = THEME.accent
COLOR_ORANGE = THEME.orange
COLOR_TEXT = THEME.text


SPANSH_BASE = "https://spansh.co.uk/api"
SPANSH_HEADERS = {"User-Agent": "VoidCompass/1.0 (personal ED companion app)"}
SPANSH_SUBMIT_TIMEOUT = 20
SPANSH_POLL_TIMEOUT = 20
SPANSH_MAX_WAIT_SECONDS = 90


class SpanshRouteError(Exception):
    pass


class RoutePlotter(ThemedWindowMixin):
    def __init__(self, root, edsm_handler, current_coords=None, current_sys="Unknown", config=None,
                 manager=None, on_change_callback=None, event_callback=None, embedded=False,
                 navigation_state_callback=None, copy_waypoint_callback=None,
                 is_active_callback=None):
        self.root = root
        self.edsm = edsm_handler
        self.manager = manager if manager else WaypointManager()
        self.current_coords = current_coords
        self.current_sys = current_sys
        self.config = config if config is not None else {}
        self.on_change_callback = on_change_callback
        self.event_callback = event_callback
        self.navigation_state_callback = navigation_state_callback
        self.copy_waypoint_callback = copy_waypoint_callback
        self.is_active_callback = is_active_callback
        self.route_refresh_running = False
        self.neutron_route_running = False
        self.neutron_waypoints = []
        self._route_refresh_state = None
        self.duplicate_mode = self.config.get("route_duplicate_mode", "skip")
        self.pending_import_jobs = {}
        self._refresh_pending = False

        self.embedded = embedded
        self.win = window_surface(root, embedded=embedded)
        self.win.title("ROUTE & WAYPOINT MANAGER")
        self.win.geometry(self.config.get("route_plotter_geometry", "1020x700"))
        apply_window(self.win)
        self.win.protocol("WM_DELETE_WINDOW", self.on_close)

        self.setup_ui()
        self.refresh_list()

    def _emit_event(self, tag, message, severity="INFO", copy_text=None):
        if not callable(self.event_callback):
            return
        try:
            self.event_callback(tag, message, severity=severity, copy_text=copy_text, system_name=self.current_sys)
        except Exception:
            pass

    def setup_ui(self):
        wrapper = tk.Frame(self.win, bg=COLOR_BG)
        wrapper.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        header = tk.Frame(wrapper, bg=COLOR_PANEL, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        header.pack(fill=tk.X)
        tk.Label(header, text=" // FLIGHT PLANNER", font=("Courier", 14, "bold"), fg=COLOR_ACCENT, bg=COLOR_PANEL).pack(side=tk.LEFT, padx=10, pady=8)
        self.header_current_lbl = tk.Label(header, text=f"CURRENT: {self.current_sys}", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL)
        self.header_current_lbl.pack(side=tk.RIGHT, padx=10)

        style = configure_ttk(self.win, "Route")
        style.configure("Route.TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure("Route.TNotebook.Tab", background=COLOR_PANEL, foreground=COLOR_TEXT, padding=(14, 6), font=("Courier", 9, "bold"))
        style.map("Route.TNotebook.Tab", background=[("selected", "#111111")], foreground=[("selected", COLOR_ACCENT)])
        style.configure("Route.Treeview", background="#050505", foreground=COLOR_TEXT, fieldbackground="#050505", rowheight=25, borderwidth=0, font=("Courier", 9))
        style.configure("Route.Treeview.Heading", background=COLOR_PANEL, foreground=COLOR_ORANGE, relief="flat", font=("Courier", 8, "bold"))
        style.map("Route.Treeview", background=[("selected", COLOR_ACCENT)], foreground=[("selected", "black")])

        self.tabs = ttk.Notebook(wrapper, style="Route.TNotebook")
        self.tabs.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        overview_tab = tk.Frame(self.tabs, bg=COLOR_BG)
        route_tab = tk.Frame(self.tabs, bg=COLOR_BG)
        plotter_tab = tk.Frame(self.tabs, bg=COLOR_BG)
        self.tabs.add(overview_tab, text="Route Overview")
        self.tabs.add(route_tab, text="Waypoints")
        self.tabs.add(plotter_tab, text="Neutron Plotter")

        self._build_route_overview_tab(overview_tab)
        self._build_waypoint_tab(route_tab)
        self._build_system_plotter_tab(plotter_tab)
        self.tabs.bind("<<NotebookTabChanged>>", lambda _e: self._refresh_route_overview())

    def _build_route_overview_tab(self, wrapper):
        summary = tk.Frame(wrapper, bg=COLOR_PANEL, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        summary.pack(fill=tk.X, pady=(0, 8))
        self.overview_metrics = {}
        for idx, label in enumerate(("GAME ROUTE", "EXPEDITION", "NEXT STOP", "REMAINING")):
            card = tk.Frame(summary, bg=COLOR_PANEL)
            card.grid(row=0, column=idx, sticky="nsew", padx=10, pady=8)
            summary.grid_columnconfigure(idx, weight=1, uniform="route_overview_metrics")
            tk.Label(card, text=label, font=("Courier", 8, "bold"), fg="#777", bg=COLOR_PANEL, anchor="w").pack(fill=tk.X)
            value = tk.Label(card, text="-", font=("Courier", 10, "bold"), fg=COLOR_ACCENT if idx < 2 else COLOR_TEXT, bg=COLOR_PANEL, anchor="w")
            value.pack(fill=tk.X, pady=(2, 0))
            self.overview_metrics[label] = value

        lanes = tk.Frame(wrapper, bg=COLOR_BG)
        lanes.pack(fill=tk.BOTH, expand=True)
        lanes.grid_columnconfigure(0, weight=1, uniform="route_lanes")
        lanes.grid_columnconfigure(1, weight=1, uniform="route_lanes")
        lanes.grid_rowconfigure(0, weight=1)

        game = tk.Frame(lanes, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        game.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        tk.Label(game, text="LIVE ELITE ROUTE", font=("Courier", 10, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL, anchor="w").pack(fill=tk.X, padx=10, pady=(9, 2))
        self.game_route_detail = tk.Label(game, text="NavRoute.json has no active route", font=("Courier", 8), fg="#999", bg=COLOR_PANEL, anchor="w")
        self.game_route_detail.pack(fill=tk.X, padx=10, pady=(0, 6))
        game_list_frame = tk.Frame(game, bg=COLOR_PANEL)
        game_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.game_route_list = tk.Listbox(game_list_frame, bg="#050505", fg=COLOR_TEXT, font=("Courier", 9), relief=tk.FLAT, highlightthickness=1, highlightbackground="#333", selectbackground=COLOR_ACCENT, selectforeground="black", activestyle="none")
        self.game_route_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        game_sb = scrollbar(game_list_frame, orient=tk.VERTICAL, command=self.game_route_list.yview)
        game_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.game_route_list.config(yscrollcommand=game_sb.set)

        expedition = tk.Frame(lanes, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        expedition.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        tk.Label(expedition, text="EXPEDITION WAYPOINTS", font=("Courier", 10, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL, anchor="w").pack(fill=tk.X, padx=10, pady=(9, 2))
        self.expedition_detail = tk.Label(expedition, text="No saved waypoints", font=("Courier", 8), fg="#999", bg=COLOR_PANEL, anchor="w")
        self.expedition_detail.pack(fill=tk.X, padx=10, pady=(0, 6))
        expedition_list_frame = tk.Frame(expedition, bg=COLOR_PANEL)
        expedition_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.expedition_route_list = tk.Listbox(expedition_list_frame, bg="#050505", fg=COLOR_TEXT, font=("Courier", 9), relief=tk.FLAT, highlightthickness=1, highlightbackground="#333", selectbackground=COLOR_ACCENT, selectforeground="black", activestyle="none")
        self.expedition_route_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        expedition_sb = scrollbar(expedition_list_frame, orient=tk.VERTICAL, command=self.expedition_route_list.yview)
        expedition_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.expedition_route_list.config(yscrollcommand=expedition_sb.set)

        actions = tk.Frame(wrapper, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        actions.pack(fill=tk.X, pady=(8, 0))
        button(actions, "COPY NEXT", self.copy_next_destination, accent=True).pack(side=tk.LEFT, padx=8, pady=8)
        button(actions, "MANAGE WAYPOINTS", lambda: self.tabs.select(1)).pack(side=tk.LEFT, padx=(0, 8), pady=8)
        button(actions, "PLOT NEUTRON ROUTE", lambda: self.tabs.select(2)).pack(side=tk.LEFT, padx=(0, 8), pady=8)
        self.overview_source_lbl = tk.Label(actions, text="Game navigation and saved waypoints remain separate", font=("Courier", 8), fg="#888", bg=COLOR_PANEL)
        self.overview_source_lbl.pack(side=tk.RIGHT, padx=10)

    def _navigation_state(self):
        if callable(self.navigation_state_callback):
            try:
                state = self.navigation_state_callback()
                if isinstance(state, dict):
                    return state
            except Exception:
                pass
        return {"current_system": self.current_sys, "route": [], "entries": [], "destination": None}

    def _route_overview_values(self):
        state = self._navigation_state()
        current = state.get("current_system") or self.current_sys
        route = list(state.get("route") or [])
        entries = list(state.get("entries") or [])
        current_index = next(
            (index for index, name in enumerate(route)
             if str(name).casefold() == str(current).casefold()),
            -1,
        )
        if current_index >= 0:
            game_pending = route[current_index + 1:]
        else:
            game_pending = route
        pending_waypoints = [row for row in self.manager.waypoints if not row.get("visited", False)]
        remaining_distance = 0.0
        previous = self.current_coords
        for row in pending_waypoints:
            coords = row.get("coords")
            if coords and previous:
                try:
                    remaining_distance += self.manager.get_distance(previous, coords)
                except Exception:
                    pass
            if coords:
                previous = coords
        next_game = game_pending[0] if game_pending else None
        next_waypoint = pending_waypoints[0].get("name") if pending_waypoints else None
        return {
            "state": state, "current": current, "route": route, "entries": entries,
            "game_pending": game_pending, "pending_waypoints": pending_waypoints,
            "remaining_distance": remaining_distance,
            "next_game": next_game, "next_waypoint": next_waypoint,
            "next": next_game or next_waypoint,
            "source": "GAME ROUTE" if next_game else ("WAYPOINT" if next_waypoint else "NONE"),
        }

    def _refresh_route_overview(self):
        if not hasattr(self, "game_route_list"):
            return
        values = self._route_overview_values()
        route = values["route"]
        game_pending = values["game_pending"]
        waypoints = self.manager.waypoints
        pending = values["pending_waypoints"]
        visited = len(waypoints) - len(pending)
        self.overview_metrics["GAME ROUTE"].config(text=f"{len(game_pending)} JUMPS" if route else "NO ROUTE")
        self.overview_metrics["EXPEDITION"].config(text=f"{visited}/{len(waypoints)} COMPLETE" if waypoints else "NO WAYPOINTS")
        self.overview_metrics["NEXT STOP"].config(text=values["next"] or "-")
        remaining_bits = []
        if game_pending:
            remaining_bits.append(f"{len(game_pending)} jumps")
        if pending:
            remaining_bits.append(f"{values['remaining_distance']:,.0f} ly")
        self.overview_metrics["REMAINING"].config(text=" / ".join(remaining_bits) or "-")
        self.overview_source_lbl.config(text=f"COPY NEXT SOURCE: {values['source']}")

        self.game_route_list.delete(0, tk.END)
        if route:
            current = values["current"]
            entry_by_name = {
                str(row.get("StarSystem") or "").casefold(): row
                for row in values["entries"] if isinstance(row, dict)
            }
            for index, name in enumerate(route):
                if str(name).casefold() == str(current).casefold():
                    marker = "CURRENT"
                elif name == values["next_game"]:
                    marker = "NEXT"
                else:
                    marker = f"{index + 1:02d}"
                star_class = entry_by_name.get(str(name).casefold(), {}).get("StarClass")
                suffix = f"  [{star_class}]" if star_class else ""
                self.game_route_list.insert(tk.END, f"{marker:<8} {name}{suffix}")
                row_index = self.game_route_list.size() - 1
                if marker == "CURRENT":
                    self.game_route_list.itemconfig(row_index, {"fg": COLOR_ORANGE})
                elif marker == "NEXT":
                    self.game_route_list.itemconfig(row_index, {"fg": COLOR_ACCENT})
            destination = values["state"].get("destination") or route[-1]
            self.game_route_detail.config(text=f"{len(game_pending)} jumps remaining · destination {destination}")
        else:
            self.game_route_list.insert(tk.END, "NO ACTIVE GAME ROUTE")
            self.game_route_list.itemconfig(0, {"fg": "#777"})
            self.game_route_detail.config(text="NavRoute.json has no active route")

        self.expedition_route_list.delete(0, tk.END)
        if waypoints:
            next_name = values["next_waypoint"]
            for index, row in enumerate(waypoints):
                name = row.get("name") or "Unknown"
                if row.get("visited", False):
                    marker = "DONE"
                elif name == next_name:
                    marker = "NEXT"
                else:
                    marker = f"{index + 1:02d}"
                note_value = str(row.get("note") or "")
                note = f" · {note_value[:60]}" if note_value else ""
                self.expedition_route_list.insert(tk.END, f"{marker:<6} {name}{note}")
                row_index = self.expedition_route_list.size() - 1
                if marker == "DONE":
                    self.expedition_route_list.itemconfig(row_index, {"fg": "#666"})
                elif marker == "NEXT":
                    self.expedition_route_list.itemconfig(row_index, {"fg": COLOR_ACCENT})
            self.expedition_detail.config(text=f"{len(pending)} pending · {visited} complete · {values['remaining_distance']:,.1f} ly remaining")
        else:
            self.expedition_route_list.insert(tk.END, "NO SAVED WAYPOINTS")
            self.expedition_route_list.itemconfig(0, {"fg": "#777"})
            self.expedition_detail.config(text="No saved waypoint expedition")

    def copy_next_destination(self):
        values = self._route_overview_values()
        destination = values.get("next")
        if not destination:
            messagebox.showinfo("Route Overview", "No pending game-route hop or waypoint to copy.", parent=self.win)
            return
        label = "NEXT GAME HOP" if values.get("next_game") else "NEXT WAYPOINT"
        if callable(self.copy_waypoint_callback):
            self.copy_waypoint_callback(destination, label)
        else:
            self.root.clipboard_clear()
            self.root.clipboard_append(destination)
            self._emit_event("ROUTE", f"Copied {label}: {destination}", "INFO", copy_text=destination)

    def on_shown(self):
        if self._refresh_pending:
            self._refresh_pending = False
            self.refresh_list()
        else:
            self._refresh_route_overview()

    def update_navigation_state(self):
        if callable(self.is_active_callback) and not self.is_active_callback():
            self._refresh_pending = True
            return
        self._refresh_route_overview()

    def _build_waypoint_tab(self, wrapper):
        input_panel = tk.Frame(wrapper, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        input_panel.pack(fill=tk.X)
        tk.Label(input_panel, text="SYSTEM", font=("Courier", 8, "bold"), fg="#888", bg=COLOR_PANEL).grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(7, 2))
        self.entry = tk.Entry(input_panel, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(7, 2), ipady=3)
        self.entry.bind("<Return>", lambda _e: self.add_system())
        tk.Label(input_panel, text="NOTE", font=("Courier", 8, "bold"), fg="#888", bg=COLOR_PANEL).grid(row=0, column=2, sticky="w", padx=(6, 6), pady=(7, 2))
        self.note_entry = tk.Entry(input_panel, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.note_entry.grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=(7, 2), ipady=3)
        button(input_panel, "ADD WAYPOINT", self.add_system, accent=True).grid(row=0, column=4, padx=(0, 10), pady=(7, 2))
        input_panel.grid_columnconfigure(1, weight=2)
        input_panel.grid_columnconfigure(3, weight=1)

        import_row = tk.Frame(input_panel, bg=COLOR_PANEL)
        import_row.grid(row=1, column=0, columnspan=5, sticky="ew", padx=8, pady=(3, 7))
        button(import_row, "PASTE LIST", self.open_import_dialog).pack(side=tk.LEFT)
        button(import_row, "IMPORT SPANSH CSV", self.import_spansh_csv).pack(side=tk.LEFT, padx=(6, 0))
        self.dup_btn = button(import_row, "", self.cycle_duplicate_mode, muted=True)
        self.dup_btn.pack(side=tk.LEFT, padx=(6, 0))
        self._update_duplicate_mode_btn()
        tk.Label(import_row, text="Imports resolve coordinates through EDSM; plotting remains manual.", font=("Courier", 8), fg="#777", bg=COLOR_PANEL).pack(side=tk.RIGHT, padx=4)

        list_wrap = tk.Frame(wrapper, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        list_wrap.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        tree_frame = tk.Frame(list_wrap, bg=COLOR_PANEL)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        columns = ("index", "state", "system", "segment", "cumulative", "note")
        self.waypoint_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="extended", style="Route.Treeview", height=5)
        headings = {
            "index": ("#", 42, False), "state": ("STATUS", 72, False),
            "system": ("SYSTEM", 220, True), "segment": ("SEGMENT", 90, False),
            "cumulative": ("CUMULATIVE", 105, False), "note": ("NOTE", 300, True),
        }
        for key, (title, width, stretch) in headings.items():
            self.waypoint_tree.heading(key, text=title, anchor="w")
            self.waypoint_tree.column(key, width=width, minwidth=40, stretch=stretch, anchor="w")
        self.waypoint_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_sb = scrollbar(tree_frame, orient=tk.VERTICAL, command=self.waypoint_tree.yview)
        tree_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.waypoint_tree.configure(yscrollcommand=tree_sb.set)
        self.waypoint_tree.tag_configure("current", foreground=COLOR_ORANGE)
        self.waypoint_tree.tag_configure("visited", foreground="#666")
        self.waypoint_tree.bind("<<TreeviewSelect>>", lambda _e: self._update_selection_panel())
        self.waypoint_tree.bind("<Double-Button-1>", lambda _e: self.edit_selected())
        self.waypoint_tree.bind("<Delete>", lambda _e: self.remove_selected_batch())
        self.waypoint_tree.bind("<Control-c>", lambda _e: self.copy_selected_batch())

        selection = tk.Frame(wrapper, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        selection.pack(fill=tk.X, pady=(8, 0))
        for column in range(3):
            selection.grid_columnconfigure(column, weight=1, uniform="route_selection")
        self.sel_name_lbl = tk.Label(selection, text="Name: -", font=("Courier", 9, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL, anchor="w")
        self.sel_name_lbl.grid(row=0, column=0, sticky="ew", padx=10, pady=(7, 2))
        self.sel_dist_lbl = tk.Label(selection, text="Distance: -", font=("Courier", 8), fg="#aaa", bg=COLOR_PANEL, anchor="w")
        self.sel_dist_lbl.grid(row=0, column=1, sticky="ew", padx=10, pady=(7, 2))
        self.sel_state_lbl = tk.Label(selection, text="State: -", font=("Courier", 8), fg="#aaa", bg=COLOR_PANEL, anchor="w")
        self.sel_state_lbl.grid(row=0, column=2, sticky="ew", padx=10, pady=(7, 2))
        self.sel_note_lbl = tk.Label(selection, text="Note: -", font=("Courier", 8), fg="#aaa", bg=COLOR_PANEL, anchor="w")
        self.sel_note_lbl.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 7))
        self.sel_seg_lbl = tk.Label(selection, text="Segment: -", font=("Courier", 8), fg="#aaa", bg=COLOR_PANEL, anchor="w")
        self.sel_seg_lbl.grid(row=1, column=1, sticky="ew", padx=10, pady=(2, 7))
        self.sel_cum_lbl = tk.Label(selection, text="Cumulative: -", font=("Courier", 8), fg="#aaa", bg=COLOR_PANEL, anchor="w")
        self.sel_cum_lbl.grid(row=1, column=2, sticky="ew", padx=10, pady=(2, 7))

        actions = tk.Frame(wrapper, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        actions.pack(fill=tk.X, pady=(8, 0))
        selection_actions = tk.Frame(actions, bg=COLOR_PANEL)
        selection_actions.pack(fill=tk.X, padx=8, pady=(7, 3))
        for text, command, accent, danger in (
            ("COPY", self.copy_selected, True, False), ("EDIT", self.edit_selected, False, False),
            ("TOGGLE DONE", self.toggle_visited, False, False), ("MARK DONE", self.mark_selected_done, False, False),
            ("MARK TODO", self.mark_selected_todo, False, False), ("DELETE", self.remove_selected_batch, False, True),
        ):
            button(selection_actions, text, command, accent=accent, danger=danger, width=13).pack(side=tk.LEFT, padx=(0, 6))

        route_actions = tk.Frame(actions, bg=COLOR_PANEL)
        route_actions.pack(fill=tk.X, padx=8, pady=(3, 7))
        button(route_actions, "MOVE UP", self.move_up, width=13).pack(side=tk.LEFT, padx=(0, 6))
        button(route_actions, "MOVE DOWN", self.move_down, width=13).pack(side=tk.LEFT, padx=(0, 6))
        self.refresh_route_btn = button(route_actions, "REFRESH EDSM", self.refresh_route_from_edsm, width=15)
        self.refresh_route_btn.pack(side=tk.LEFT, padx=(0, 6))
        button(route_actions, "EXPORT CSV", self.export_route_csv, width=13).pack(side=tk.LEFT, padx=(0, 6))
        button(route_actions, "CLEAR ROUTE", self.clear_all, danger=True, width=13).pack(side=tk.LEFT, padx=(0, 6))
        self.health_lbl = tk.Label(route_actions, text="", font=("Courier", 8), fg="#999", bg=COLOR_PANEL, anchor="e")
        self.health_lbl.pack(side=tk.RIGHT, padx=4)

        footer = tk.Frame(wrapper, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        footer.pack(fill=tk.X, pady=(8, 0))
        self.stats_lbl = tk.Label(footer, text="TOTAL PLOTTED DISTANCE: 0.0 LY", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL)
        self.stats_lbl.pack(side=tk.LEFT, padx=10, pady=7)
        self.ac_var = tk.BooleanVar(value=self.config.get("auto_copy_waypoint", False))
        tk.Checkbutton(footer, text="AUTO-COPY NEXT WAYPOINT", variable=self.ac_var, command=self.toggle_auto_copy,
            bg=COLOR_PANEL, fg=COLOR_TEXT, selectcolor=COLOR_PANEL, activebackground=COLOR_PANEL,
            activeforeground=COLOR_TEXT, font=("Courier", 8)).pack(side=tk.RIGHT, padx=10)
        self.auto_note_var = tk.BooleanVar(value=self.config.get("route_auto_note_from_edsm", True))
        tk.Checkbutton(footer, text="AUTO NOTE FROM EDSM", variable=self.auto_note_var, command=self.toggle_auto_note,
            bg=COLOR_PANEL, fg=COLOR_TEXT, selectcolor=COLOR_PANEL, activebackground=COLOR_PANEL,
            activeforeground=COLOR_TEXT, font=("Courier", 8)).pack(side=tk.RIGHT, padx=(4, 10))


    def _entry_box(self, parent, label, width):
        box = tk.Frame(parent, bg=parent.cget("bg"))
        box.pack(side=tk.LEFT, padx=(0, 8), pady=(0, 6))
        tk.Label(box, text=label, font=("Courier", 8, "bold"), fg="#888", bg=parent.cget("bg")).pack(anchor="w")
        entry = tk.Entry(box, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT, width=width)
        entry.pack(anchor="w", ipady=3)
        return entry

    def _build_system_plotter_tab(self, wrapper):
        controls = tk.Frame(wrapper, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        controls.pack(fill=tk.X)

        saved = self.config.get("system_plotter_form") or {}
        form_row = tk.Frame(controls, bg=COLOR_PANEL)
        form_row.pack(fill=tk.X, padx=8, pady=(7, 1))
        self.neutron_from_entry = self._entry_box(form_row, "FROM", 22)
        self.neutron_from_entry.insert(0, saved.get("from") or (self.current_sys if self.current_sys != "Unknown" else ""))
        self.neutron_from_entry.bind("<Return>", lambda _e: self.find_neutron_route())
        self.neutron_to_entry = self._entry_box(form_row, "DESTINATION", 24)
        self.neutron_to_entry.insert(0, saved.get("to") or "")
        self.neutron_to_entry.bind("<Return>", lambda _e: self.find_neutron_route())
        self.neutron_range_entry = self._entry_box(form_row, "JUMP LY", 8)
        self.neutron_range_entry.insert(0, str(saved.get("range") or 30))
        self.neutron_eff_entry = self._entry_box(form_row, "EFF %", 7)
        self.neutron_eff_entry.insert(0, str(saved.get("efficiency") or 60))
        mode_box = tk.Frame(form_row, bg=form_row.cget("bg"))
        mode_box.pack(side=tk.LEFT, padx=(0, 8), pady=(0, 6))
        tk.Label(mode_box, text="SUPERCHARGE", font=("Courier", 8, "bold"), fg="#888", bg=form_row.cget("bg")).pack(anchor="w")
        self.neutron_supercharge_var = tk.StringVar(value=self._supercharge_mode_from_saved(saved.get("supercharge_multiplier")))
        supercharge_menu = tk.OptionMenu(mode_box, self.neutron_supercharge_var, "Normal 4x", "Overcharge 6x")
        supercharge_menu.config(bg="#111", fg=COLOR_TEXT, activebackground=COLOR_PANEL, activeforeground=COLOR_ACCENT, relief=tk.FLAT, highlightthickness=0, font=("Courier", 9), width=14)
        supercharge_menu["menu"].config(bg="#111", fg=COLOR_TEXT, activebackground=COLOR_ACCENT, activeforeground="black", font=("Courier", 9))
        supercharge_menu.pack(anchor="w")

        action_row = tk.Frame(controls, bg=COLOR_PANEL)
        action_row.pack(fill=tk.X, padx=8, pady=(1, 7))
        self.neutron_plot_btn = button(action_row, "PLOT", self.find_neutron_route, accent=True)
        self.neutron_plot_btn.pack(side=tk.LEFT, padx=(0, 6))
        button(action_row, "IMPORT TO ROUTE", self.import_neutron_route).pack(side=tk.LEFT, padx=(0, 6))
        button(action_row, "COPY LIST", self.copy_neutron_route).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(action_row, text="Manual Spansh neutron route · no automatic plotting", font=("Courier", 8), fg="#777", bg=COLOR_PANEL).pack(side=tk.RIGHT, padx=4)

        body = tk.Frame(wrapper, bg=COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        list_wrap = tk.Frame(body, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        list_wrap.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(list_wrap, text=f"{'#':<4}{'SYSTEM':<30}{'JUMPED':<10}{'LEFT':<10}{'N':<3}JUMPS", font=("Courier", 9, "bold"), fg="#777", bg=COLOR_PANEL, anchor="w").pack(fill=tk.X, padx=8, pady=(8, 4))
        list_frame = tk.Frame(list_wrap, bg=COLOR_PANEL)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.neutron_listbox = tk.Listbox(
            list_frame, bg="#050505", fg=COLOR_TEXT, font=("Courier", 10), relief=tk.FLAT,
            highlightthickness=1, highlightbackground="#333", selectbackground=COLOR_ACCENT, selectforeground="black",
            activestyle="none", selectmode=tk.EXTENDED
        )
        self.neutron_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        nsb = scrollbar(list_frame, orient=tk.VERTICAL, command=self.neutron_listbox.yview)
        nsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.neutron_listbox.config(yscrollcommand=nsb.set)
        self.neutron_listbox.bind("<Control-c>", lambda _e: self.copy_neutron_route())

        side = tk.Frame(body, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        side.grid(row=0, column=1, sticky="nsew")
        tk.Label(side, text="PLOT SUMMARY", font=("Courier", 10, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(8, 4))
        self.neutron_status_lbl = tk.Label(side, text="Ready.", font=("Courier", 9), fg="#aaa", bg=COLOR_PANEL, justify=tk.LEFT, wraplength=230, anchor="w")
        self.neutron_status_lbl.pack(fill=tk.X, padx=10, pady=2)
        self.neutron_total_lbl = tk.Label(side, text="Route: -", font=("Courier", 9, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL, justify=tk.LEFT, wraplength=230, anchor="w")
        self.neutron_total_lbl.pack(fill=tk.X, padx=10, pady=(8, 2))
        tk.Label(side, text="IMPORT NOTES", font=("Courier", 8, "bold"), fg="#777", bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(12, 2))
        tk.Label(
            side,
            text="Import sends the plotted systems into the Waypoints tab and resolves coordinates through EDSM. Duplicate handling uses the current route duplicate mode.",
            font=("Courier", 8), fg="#aaa", bg=COLOR_PANEL, justify=tk.LEFT, wraplength=230, anchor="w"
        ).pack(fill=tk.X, padx=10, pady=(0, 8))

    def _save_system_plotter_form(self):
        self.config["system_plotter_form"] = {
            "from": self.neutron_from_entry.get().strip(),
            "to": self.neutron_to_entry.get().strip(),
            "range": self.neutron_range_entry.get().strip(),
            "efficiency": self.neutron_eff_entry.get().strip(),
            "supercharge_multiplier": self._selected_supercharge_multiplier(),
        }
        try:
            save_config(self.config)
        except Exception:
            pass

    def find_neutron_route(self):
        if self.neutron_route_running:
            return
        from_system = self.neutron_from_entry.get().strip() or self.current_sys
        to_system = self.neutron_to_entry.get().strip()
        if not from_system or from_system == "Unknown":
            messagebox.showwarning("Neutron Plotter", "No starting system known yet.")
            return
        if not to_system:
            messagebox.showwarning("Neutron Plotter", "Enter a destination system.")
            return
        try:
            jump_range = float(self.neutron_range_entry.get().strip())
            efficiency = int(float(self.neutron_eff_entry.get().strip()))
            supercharge_multiplier = self._selected_supercharge_multiplier()
        except Exception:
            messagebox.showwarning("Neutron Plotter", "Jump range and efficiency must be numbers.")
            return

        self._save_system_plotter_form()
        self.neutron_route_running = True
        self.neutron_plot_btn.config(state=tk.DISABLED, text="[ PLOTTING... ]")
        self.neutron_status_lbl.config(text="Submitting Spansh neutron highway job...")
        self.neutron_total_lbl.config(text="Route: pending")
        self.neutron_listbox.delete(0, tk.END)
        self.neutron_waypoints = []
        self._emit_event("ROUTE", f"Neutron plot started: {from_system} to {to_system} ({supercharge_multiplier}x)", "INFO", copy_text=to_system)

        def worker():
            try:
                route = self._spansh_neutron_route(from_system, to_system, jump_range, efficiency, supercharge_multiplier)
                self.root.after(0, lambda: self._on_neutron_route_ready(route))
            except Exception as exc:
                self.root.after(0, lambda e=exc: self._on_neutron_route_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_neutron_route_ready(self, route):
        self.neutron_route_running = False
        self.neutron_plot_btn.config(state=tk.NORMAL, text="[ PLOT ]")
        self.neutron_waypoints = route.get("waypoints") or []
        self.neutron_listbox.delete(0, tk.END)
        neutron_count = 0
        for idx, wp in enumerate(self.neutron_waypoints, start=1):
            if wp.get("neutron"):
                neutron_count += 1
            line = (
                f"{idx:<4}{(wp.get('system') or '-'):<30}"
                f"{self._fmt_ly(wp.get('distance_jumped')):<10}"
                f"{self._fmt_ly(wp.get('distance_left')):<10}"
                f"{'Y' if wp.get('neutron') else '-':<3}{wp.get('jumps') or '-'}"
            )
            self.neutron_listbox.insert(tk.END, line)
            if wp.get("neutron"):
                self.neutron_listbox.itemconfig(idx - 1, {"fg": COLOR_ORANGE})

        total_jumps = route.get("total_jumps") or len(self.neutron_waypoints)
        self.neutron_status_lbl.config(text=f"Ready. {len(self.neutron_waypoints)} waypoints, {neutron_count} neutron boosts.")
        self.neutron_total_lbl.config(text=f"Route: {total_jumps} jumps")
        self._emit_event("ROUTE", f"Neutron plot ready: {len(self.neutron_waypoints)} waypoints", "INFO")

    def _on_neutron_route_error(self, exc):
        self.neutron_route_running = False
        self.neutron_plot_btn.config(state=tk.NORMAL, text="[ PLOT ]")
        self.neutron_status_lbl.config(text=f"Plot failed: {exc}")
        self.neutron_total_lbl.config(text="Route: failed")
        self._emit_event("ROUTE", f"Neutron plot failed: {exc}", "FAIL")
        messagebox.showerror("Neutron Plotter", f"Neutron route failed:\n{exc}")

    def import_neutron_route(self):
        if not self.neutron_waypoints:
            messagebox.showinfo("Import Route", "No plotted system route to import.")
            return
        records = []
        for wp in self.neutron_waypoints:
            name = wp.get("system")
            if not name:
                continue
            records.append({"name": name, "coords": None, "note": None})
        if not records:
            messagebox.showwarning("Import Route", "The plotted route did not contain system names.")
            return
        self.tabs.select(1)
        self._start_import_job(records, enrich_notes=False)
        self._emit_event("ROUTE", f"Neutron route import queued: {len(records)} systems", "INFO")

    def copy_neutron_route(self):
        if not self.neutron_waypoints:
            return
        selected = list(self.neutron_listbox.curselection())
        if selected:
            names = [self.neutron_waypoints[i].get("system") for i in selected if i < len(self.neutron_waypoints)]
        else:
            names = [wp.get("system") for wp in self.neutron_waypoints]
        text = "\n".join(n for n in names if n)
        if not text:
            return
        self.win.clipboard_clear()
        self.win.clipboard_append(text)
        self._emit_event("ROUTE", "Copied neutron route systems", "INFO", copy_text=text)

    def _fmt_ly(self, value):
        try:
            return f"{float(value):.1f}"
        except Exception:
            return "-"

    def _supercharge_mode_from_saved(self, value):
        try:
            if int(value) == 6:
                return "Overcharge 6x"
        except Exception:
            pass
        return "Normal 4x"

    def _selected_supercharge_multiplier(self):
        return 6 if self.neutron_supercharge_var.get().startswith("Overcharge") else 4

    def _spansh_neutron_route(self, from_system, to_system, jump_range, efficiency, supercharge_multiplier=4):
        payload = {
            "from": from_system,
            "to": to_system,
            "range": float(jump_range),
            "efficiency": int(efficiency),
            "supercharge_multiplier": int(supercharge_multiplier),
        }
        result = self._spansh_submit_and_poll("route", payload)
        jumps = result.get("system_jumps") if isinstance(result, dict) else None
        if not jumps:
            raise SpanshRouteError("Spansh returned no route. Check system names and jump range.")
        return {
            "total_jumps": result.get("total_jumps"),
            "waypoints": [
                {
                    "system": j.get("system"),
                    "distance_jumped": j.get("distance_jumped"),
                    "distance_left": j.get("distance_left"),
                    "neutron": bool(j.get("neutron_star")),
                    "jumps": j.get("jumps"),
                    "supercharge_multiplier": int(supercharge_multiplier),
                }
                for j in jumps
            ],
        }

    def _spansh_submit_and_poll(self, path, payload):
        try:
            resp = requests.post(
                f"{SPANSH_BASE}/{path}",
                data=payload,
                headers=SPANSH_HEADERS,
                timeout=SPANSH_SUBMIT_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise SpanshRouteError(f"Could not reach Spansh: {exc}") from exc

        if resp.status_code >= 400:
            raise SpanshRouteError(self._spansh_error_text(resp))
        try:
            job = resp.json().get("job")
        except ValueError as exc:
            raise SpanshRouteError(f"Spansh returned invalid JSON: {resp.text[:200]}") from exc
        if not job:
            raise SpanshRouteError(f"Spansh did not return a job id: {resp.text[:200]}")

        deadline = time.monotonic() + SPANSH_MAX_WAIT_SECONDS
        while time.monotonic() < deadline:
            try:
                poll = requests.get(f"{SPANSH_BASE}/results/{job}", headers=SPANSH_HEADERS, timeout=SPANSH_POLL_TIMEOUT)
            except requests.RequestException as exc:
                raise SpanshRouteError(f"Lost connection to Spansh: {exc}") from exc
            if poll.status_code >= 400:
                raise SpanshRouteError(self._spansh_error_text(poll))
            data = poll.json()
            status = data.get("status")
            if status == "ok":
                return data.get("result")
            if status in ("queued", "processing"):
                time.sleep(1.5)
                continue
            raise SpanshRouteError(f"Spansh job failed: {data.get('error') or status}")
        raise SpanshRouteError("Spansh took too long to compute a route; try again.")

    def _spansh_error_text(self, resp):
        try:
            detail = resp.json().get("error")
        except ValueError:
            detail = None
        return f"Spansh error ({resp.status_code}): {detail or resp.text[:200]}"

    def get_selected_index(self):
        selected = self.get_selected_indices()
        return selected[0] if selected else None

    def _run_on_ui(self, fn):
        self.root.after(0, fn)

    def get_selected_indices(self):
        try:
            return sorted(int(item) for item in self.waypoint_tree.selection())
        except Exception:
            return []

    def _update_duplicate_mode_btn(self):
        label = {"skip": "DUP: SKIP", "append": "DUP: APPEND NOTE", "keep": "DUP: KEEP BOTH"}.get(self.duplicate_mode, "DUP: SKIP")
        self.dup_btn.config(text=f"[ {label} ]")

    def cycle_duplicate_mode(self):
        modes = ["skip", "append", "keep"]
        idx = modes.index(self.duplicate_mode) if self.duplicate_mode in modes else 0
        self.duplicate_mode = modes[(idx + 1) % len(modes)]
        self.config["route_duplicate_mode"] = self.duplicate_mode
        try:
            save_config(self.config)
        except Exception:
            pass
        self._update_duplicate_mode_btn()
        self._emit_event("ROUTE", f"Duplicate mode: {self.duplicate_mode.upper()}", "INFO")

    def _find_waypoint_index(self, name):
        if not name:
            return -1
        for i, wp in enumerate(self.manager.waypoints):
            if wp.get("name", "").lower() == name.lower():
                return i
        return -1

    def _apply_duplicate_policy(self, name, coords, note):
        existing_idx = self._find_waypoint_index(name)
        if existing_idx == -1:
            self.manager.add_waypoint(name, coords, note)
            return "added", existing_idx

        if self.duplicate_mode == "skip":
            return "skipped", existing_idx

        if self.duplicate_mode == "append":
            wp = self.manager.waypoints[existing_idx]
            if coords and not wp.get("coords"):
                wp["coords"] = coords
            merged = self._merge_notes(wp.get("note"), note)
            wp["note"] = merged
            self.manager.save()
            return "merged", existing_idx

        self.manager.add_waypoint(name, coords, note)
        return "added_duplicate", len(self.manager.waypoints) - 1

    def add_system(self):
        sys_name = self.entry.get().strip()
        manual_note = self.note_entry.get().strip() or None
        if not sys_name:
            return

        self.entry.delete(0, tk.END)
        self.entry.insert(0, "Searching...")
        self.entry.config(state=tk.DISABLED)
        self.note_entry.config(state=tk.DISABLED)

        def cb(name, coords):
            self._run_on_ui(lambda: self._on_add_coords(name, coords, manual_note))

        self.edsm.fetch_system_coords(sys_name, cb)

    def _on_add_coords(self, name, coords, manual_note):
        self.entry.config(state=tk.NORMAL)
        self.note_entry.config(state=tk.NORMAL)
        self.entry.delete(0, tk.END)
        self.note_entry.delete(0, tk.END)
        self._fetch_edsm_note(name, lambda edsm_note: self._add_waypoint_with_notes(name, coords, manual_note, edsm_note))

    def _add_waypoint_with_notes(self, name, coords, manual_note, edsm_note):
        if not coords:
            messagebox.showwarning("Add Waypoint", f"System not found on EDSM:\n{name}\n\nWaypoint was not added.")
            self._emit_event("ROUTE", f"Waypoint lookup failed: {name}", "WARN", copy_text=name)
            return
        final_note = self._merge_notes(manual_note, edsm_note)
        outcome, idx = self._apply_duplicate_policy(name, coords, final_note)
        if outcome in ("added", "added_duplicate"):
            self.refresh_list(select_last=True)
        else:
            self.refresh_list(select_index=idx)
        if outcome in ("added", "added_duplicate"):
            self._emit_event("ROUTE", f"Waypoint added: {name}", "INFO", copy_text=name)
        elif outcome == "merged":
            self._emit_event("ROUTE", f"Waypoint merged: {name}", "INFO", copy_text=name)
        else:
            self._emit_event("ROUTE", f"Waypoint skipped (duplicate): {name}", "INFO", copy_text=name)

    def refresh_list(self, select_index=None, select_last=False):
        if callable(self.is_active_callback) and not self.is_active_callback():
            self._refresh_pending = True
            return
        previous = self.get_selected_indices()
        self.waypoint_tree.delete(*self.waypoint_tree.get_children())
        total_dist = 0.0
        prev_coords = self.current_coords
        missing_coords = 0
        current_idx = self.manager.get_waypoint_index(self.current_sys)

        for i, wp in enumerate(self.manager.waypoints):
            name = wp.get("name") or "Unknown"
            coords = wp.get("coords")
            note = wp.get("note") or ""
            is_visited = bool(wp.get("visited", False))
            segment = None
            if coords and prev_coords:
                try:
                    segment = self.manager.get_distance(prev_coords, coords)
                    total_dist += segment
                except Exception:
                    segment = None
                prev_coords = coords
            elif coords:
                prev_coords = coords
            else:
                missing_coords += 1

            if i == current_idx:
                state = "CURRENT"
                tags = ("current",)
            elif is_visited:
                state = "DONE"
                tags = ("visited",)
            else:
                state = "PENDING"
                tags = ()
            self.waypoint_tree.insert(
                "", tk.END, iid=str(i), tags=tags,
                values=(
                    i + 1, state, name,
                    f"{segment:,.1f} LY" if segment is not None else "---",
                    f"{total_dist:,.1f} LY" if coords else "---",
                    note,
                ),
            )

        visited_count = sum(1 for wp in self.manager.waypoints if wp.get("visited", False))
        pending_count = len(self.manager.waypoints) - visited_count
        names = [str(wp.get("name") or "").casefold() for wp in self.manager.waypoints]
        duplicate_count = len(names) - len(set(names))
        self.stats_lbl.config(text=f"ROUTE DISTANCE: {total_dist:,.1f} LY  //  {len(self.manager.waypoints)} WAYPOINTS")
        self.header_current_lbl.config(text=f"CURRENT: {self.current_sys}")
        storage_error = getattr(self.manager, "last_error", None)
        if storage_error:
            self.health_lbl.config(text=f"WAYPOINT SAVE ERROR · {storage_error}", fg="#ff7777")
        else:
            self.health_lbl.config(text=f"{pending_count} pending · {visited_count} done · {missing_coords} missing · {duplicate_count} duplicates", fg="#999")

        targets = previous
        if select_last and self.manager.waypoints:
            targets = [len(self.manager.waypoints) - 1]
        elif select_index is not None:
            targets = [select_index]
        valid_targets = [str(index) for index in targets if 0 <= index < len(self.manager.waypoints)]
        if valid_targets:
            self.waypoint_tree.selection_set(valid_targets)
            self.waypoint_tree.see(valid_targets[0])

        self._update_selection_panel()
        self._refresh_route_overview()
        if self.on_change_callback:
            self.root.after(0, self.on_change_callback)


    def _update_selection_panel(self):
        selected = self.get_selected_indices()
        if not selected:
            self.sel_name_lbl.config(text="Name: -")
            self.sel_note_lbl.config(text="Note: -")
            self.sel_dist_lbl.config(text="Distance: -")
            self.sel_seg_lbl.config(text="Segment: -")
            self.sel_cum_lbl.config(text="Cumulative: -")
            self.sel_state_lbl.config(text="State: -")
            return
        if len(selected) > 1:
            self.sel_name_lbl.config(text=f"Selection: {len(selected)} items")
            self.sel_note_lbl.config(text="Note: Batch selection")
            self.sel_dist_lbl.config(text="Distance: Batch")
            self.sel_seg_lbl.config(text="Segment: Batch")
            self.sel_cum_lbl.config(text="Cumulative: Batch")
            self.sel_state_lbl.config(text="State: Mixed")
            return

        idx = selected[0]
        if idx >= len(self.manager.waypoints):
            return

        wp = self.manager.waypoints[idx]
        name = wp.get("name", "Unknown")
        note = wp.get("note") or "-"
        visited = wp.get("visited", False)
        coords = wp.get("coords")

        dist_from_current = "---"
        if coords and self.current_coords:
            try:
                d = self.manager.get_distance(self.current_coords, coords)
                dist_from_current = f"{d:,.1f} LY"
            except Exception:
                pass

        segment = "---"
        cumulative = "---"
        prev_coords = self.current_coords
        cumulative_val = 0.0
        for i, item in enumerate(self.manager.waypoints):
            c = item.get("coords")
            if c and prev_coords:
                seg = self.manager.get_distance(prev_coords, c)
                cumulative_val += seg
                if i == idx:
                    segment = f"{seg:,.1f} LY"
                    cumulative = f"{cumulative_val:,.1f} LY"
                    break
                prev_coords = c
            elif c:
                prev_coords = c

        self.sel_name_lbl.config(text=f"Name: {name}")
        self.sel_note_lbl.config(text=f"Note: {note}")
        self.sel_dist_lbl.config(text=f"From Current: {dist_from_current}")
        self.sel_seg_lbl.config(text=f"Segment: {segment}")
        self.sel_cum_lbl.config(text=f"Cumulative: {cumulative}")
        self.sel_state_lbl.config(text=f"State: {'VISITED' if visited else 'PENDING'}")

    def update_current_system(self, sys_name, coords):
        old_sys = self.current_sys
        self.current_sys = sys_name
        self.current_coords = coords
        if hasattr(self, "neutron_from_entry"):
            from_value = self.neutron_from_entry.get().strip()
            if not from_value or from_value == "Unknown" or from_value == old_sys:
                self.neutron_from_entry.delete(0, tk.END)
                self.neutron_from_entry.insert(0, sys_name if sys_name != "Unknown" else "")
        if callable(self.is_active_callback) and not self.is_active_callback():
            self._refresh_pending = True
            return
        self.refresh_list()

    def move_up(self):
        idx = self.get_selected_index()
        if idx is None:
            return
        if self.manager.move_up(idx):
            self.refresh_list(select_index=idx - 1)

    def move_down(self):
        idx = self.get_selected_index()
        if idx is None:
            return
        if self.manager.move_down(idx):
            self.refresh_list(select_index=idx + 1)

    def toggle_visited(self):
        idx = self.get_selected_index()
        if idx is None:
            return
        wp = self.manager.waypoints[idx]
        wp["visited"] = not wp.get("visited", False)
        self.manager.save()
        self.refresh_list(select_index=idx)

    def edit_selected(self):
        idx = self.get_selected_index()
        if idx is None:
            return

        current_wp = self.manager.waypoints[idx]
        current_note = current_wp.get("note") or ""

        dlg = tk.Toplevel(self.win)
        dlg.title("EDIT WAYPOINT")
        dlg.geometry(self.config.get("edit_dialog_geometry", "380x190"))
        dlg.configure(bg=COLOR_BG)
        dlg.grab_set()

        tk.Label(dlg, text="SYSTEM NAME:", font=("Courier", 10), fg="#888", bg=COLOR_BG).pack(pady=(16, 4))
        name_entry = tk.Entry(dlg, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        name_entry.insert(0, current_wp["name"])
        name_entry.pack(fill=tk.X, padx=20, ipady=3)

        tk.Label(dlg, text="NOTE:", font=("Courier", 10), fg="#888", bg=COLOR_BG).pack(pady=(10, 4))
        note_entry = tk.Entry(dlg, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        note_entry.insert(0, current_note)
        note_entry.pack(fill=tk.X, padx=20, ipady=3)
        name_entry.select_range(0, tk.END)
        name_entry.focus_set()

        def save_geometry():
            self.config["edit_dialog_geometry"] = dlg.geometry()
            try:
                save_config(self.config)
            except Exception:
                pass

        def on_save():
            new_name = name_entry.get().strip()
            manual_note = note_entry.get().strip() or None
            if not new_name:
                save_geometry()
                dlg.destroy()
                return
            name_entry.config(state=tk.DISABLED)
            note_entry.config(state=tk.DISABLED)

            def cb(name, coords):
                def _apply_note(edsm_note):
                    final_note = self._merge_notes(manual_note, edsm_note)
                    self.manager.edit_waypoint(idx, name, coords, final_note)
                    self.refresh_list(select_index=idx)
                    save_geometry()
                    dlg.destroy()
                self._fetch_edsm_note(name, _apply_note)

            self.edsm.fetch_system_coords(new_name, lambda n, c: self._run_on_ui(lambda: cb(n, c)))

        btn_row = tk.Frame(dlg, bg=COLOR_BG)
        btn_row.pack(fill=tk.X, padx=20, pady=16)
        button(btn_row, "CANCEL", lambda: (save_geometry(), dlg.destroy()), muted=True, width=10).pack(side=tk.LEFT)
        button(btn_row, "SAVE", on_save, accent=True, width=10).pack(side=tk.RIGHT)
        dlg.bind("<Return>", lambda event: on_save())
        dlg.protocol("WM_DELETE_WINDOW", lambda: (save_geometry(), dlg.destroy()))

    def copy_selected(self):
        idx = self.get_selected_index()
        if idx is None:
            return
        name = self.manager.waypoints[idx].get("name")
        if not name:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(name)
        self._emit_event("ROUTE", f"Copied waypoint: {name}", "INFO", copy_text=name)

    def copy_selected_batch(self):
        idxs = self.get_selected_indices()
        if not idxs:
            return
        names = []
        for idx in idxs:
            if 0 <= idx < len(self.manager.waypoints):
                nm = self.manager.waypoints[idx].get("name")
                if nm:
                    names.append(nm)
        if not names:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(names))
        self._emit_event("ROUTE", f"Copied {len(names)} selected waypoints", "INFO", copy_text="\n".join(names))

    def remove(self):
        idx = self.get_selected_index()
        if idx is None:
            return
        self.manager.remove_waypoint(idx)
        new_idx = idx if idx < len(self.manager.waypoints) else len(self.manager.waypoints) - 1
        self.refresh_list(select_index=new_idx if new_idx >= 0 else None)

    def remove_selected_batch(self):
        idxs = self.get_selected_indices()
        if not idxs:
            return
        if not messagebox.askyesno("Confirm", f"Delete {len(idxs)} selected waypoint(s)?"):
            return
        self.manager.remove_waypoints(idxs)
        next_idx = min(idxs) if self.manager.waypoints else None
        self.refresh_list(select_index=next_idx)

    def mark_selected_done(self):
        idxs = self.get_selected_indices()
        if not idxs:
            return
        changed = False
        for idx in idxs:
            if 0 <= idx < len(self.manager.waypoints):
                if not self.manager.waypoints[idx].get("visited", False):
                    self.manager.waypoints[idx]["visited"] = True
                    changed = True
        if changed:
            self.manager.save()
        self.refresh_list(select_index=min(idxs))

    def mark_selected_todo(self):
        idxs = self.get_selected_indices()
        if not idxs:
            return
        changed = False
        for idx in idxs:
            if 0 <= idx < len(self.manager.waypoints):
                if self.manager.waypoints[idx].get("visited", False):
                    self.manager.waypoints[idx]["visited"] = False
                    changed = True
        if changed:
            self.manager.save()
        self.refresh_list(select_index=min(idxs))

    def clear_all(self):
        if messagebox.askyesno("Confirm", "Clear all waypoints?"):
            self.manager.clear()
            self.refresh_list()

    def open_import_dialog(self):
        dlg = tk.Toplevel(self.win)
        dlg.title("BULK IMPORT")
        dlg.geometry(self.config.get("import_dialog_geometry", "440x540"))
        dlg.configure(bg=COLOR_BG)
        dlg.grab_set()

        tk.Label(dlg, text="PASTE SYSTEM LIST (ONE PER LINE):", font=("Courier", 10), fg=COLOR_ORANGE, bg=COLOR_BG).pack(pady=10)

        txt = tk.Text(dlg, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), height=20, relief=tk.FLAT, insertbackground=COLOR_ACCENT)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        txt.focus_set()

        def save_geometry():
            self.config["import_dialog_geometry"] = dlg.geometry()
            try:
                save_config(self.config)
            except Exception:
                pass

        def on_dlg_close():
            save_geometry()
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", on_dlg_close)

        def do_import():
            content = txt.get("1.0", tk.END)
            lines = [line.strip() for line in content.split("\n") if line.strip()]
            save_geometry()
            dlg.destroy()
            self.process_bulk_list(lines)

        button(dlg, "PROCESS LIST", do_import, accent=True).pack(fill=tk.X, padx=10, pady=10)

    def process_bulk_list(self, systems):
        if not systems:
            return
        records = []
        for line in systems:
            name = line
            note = None
            if "," in line:
                parts = line.split(",", 1)
                name = parts[0].strip()
                if len(parts) > 1 and parts[1].strip():
                    note = parts[1].strip()
            if name:
                records.append({"name": name, "coords": None, "note": note})
        self._start_import_job(records)

    def _start_import_job(self, records, enrich_notes=True):
        if not records:
            return
        job_id = str(time.time())
        self.pending_import_jobs[job_id] = {
            "added": 0,
            "skipped": 0,
            "merged": 0,
            "resolved": 0,
            "unresolved": 0,
            "remaining": len(records),
            "records": records,
            "results": [None] * len(records),
            "enrich_notes": enrich_notes,
        }
        for idx, rec in enumerate(records):
            coords = rec.get("coords")
            if coords is not None:
                self._on_import_coord_resolved(job_id, idx, rec.get("name"), coords)
                continue
            name = rec.get("name")
            self.edsm.fetch_system_coords(
                name,
                lambda n, c, j=job_id, i=idx: self._run_on_ui(lambda: self._on_import_coord_resolved(j, i, n, c))
            )

    def _on_import_coord_resolved(self, job_id, index, name, coords):
        job = self.pending_import_jobs.get(job_id)
        if not job:
            return
        if not (0 <= index < len(job["results"])):
            return

        if job["results"][index] is not None:
            return

        record = job["records"][index]
        resolved_name = (name or record.get("name") or "").strip()
        job["results"][index] = {"name": resolved_name, "coords": coords}
        if coords:
            job["resolved"] += 1
        else:
            job["unresolved"] += 1
        job["remaining"] -= 1

        if job["remaining"] == 0:
            self._apply_import_job(job_id)

    def _apply_import_job(self, job_id):
        job = self.pending_import_jobs.get(job_id)
        if not job:
            return

        for i, rec in enumerate(job["records"]):
            result = job["results"][i]
            if not result or not result.get("coords"):
                continue
            name = result.get("name") or rec.get("name")
            note = rec.get("note")
            outcome, _ = self._apply_duplicate_policy(name, result.get("coords"), note)
            if outcome in ("added", "added_duplicate"):
                job["added"] += 1
            elif outcome == "merged":
                job["merged"] += 1
            else:
                job["skipped"] += 1
            if job["enrich_notes"]:
                self._fetch_edsm_note(name, lambda edsm_note, n=name: self._apply_edsm_note_to_waypoints(n, edsm_note))

        self.refresh_list()
        self._finalize_import_job(job_id)

    def _finalize_import_job(self, job_id):
        job = self.pending_import_jobs.pop(job_id, None)
        if not job:
            return
        msg = (
            f"Added: {job['added']}\n"
            f"Merged Duplicates: {job['merged']}\n"
            f"Skipped Duplicates: {job['skipped']}\n"
            f"Coords Resolved: {job['resolved']}\n"
            f"Unresolved Removed: {job['unresolved']}"
        )
        messagebox.showinfo("Import Report", msg)
        self._emit_event(
            "ROUTE",
            f"Import complete: added {job['added']}, merged {job['merged']}, skipped {job['skipped']}, unresolved {job['unresolved']}",
            "INFO",
        )

    def import_spansh_csv(self):
        path = filedialog.askopenfilename(
            title="Import Spansh CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return
        self._emit_event("ROUTE", f"Spansh CSV import started: {os.path.basename(path)}", "INFO", copy_text=path)

        records = []
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    messagebox.showerror("Import Spansh CSV", "CSV has no header row.")
                    return
                for row in reader:
                    name = self._extract_spansh_name(row)
                    if not name:
                        continue
                    coords = self._extract_spansh_coords(row)
                    records.append({"name": name, "coords": coords, "note": None})
        except Exception as e:
            messagebox.showerror("Import Spansh CSV", f"Failed to read CSV:\n{e}")
            return

        if not records:
            messagebox.showwarning("Import Spansh CSV", "No valid systems found in CSV.")
            return

        self._start_import_job(records)

    def _extract_spansh_name(self, row):
        for key in ("System Name", "system", "name", "system_name", "starsystem", "star_system", "Star System"):
            val = row.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        for key, val in row.items():
            if isinstance(val, str) and val.strip():
                return val.strip()
        return None

    def _extract_spansh_coords(self, row):
        x = self._to_float(row.get("x", row.get("X")))
        y = self._to_float(row.get("y", row.get("Y")))
        z = self._to_float(row.get("z", row.get("Z")))
        if x is None or y is None or z is None:
            return None
        return {"x": x, "y": y, "z": z}

    def _to_float(self, value):
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    def toggle_auto_copy(self):
        self.config["auto_copy_waypoint"] = self.ac_var.get()
        try:
            save_config(self.config)
        except Exception:
            pass
        self._emit_event("ROUTE", f"Auto-copy next waypoint: {'ON' if self.ac_var.get() else 'OFF'}", "INFO")

    def toggle_auto_note(self):
        self.config["route_auto_note_from_edsm"] = self.auto_note_var.get()
        try:
            save_config(self.config)
        except Exception:
            pass
        self._emit_event("ROUTE", f"Automatic EDSM notes: {'ON' if self.auto_note_var.get() else 'OFF'}", "INFO")

    def _fetch_edsm_note(self, system_name, callback):
        if not self.auto_note_var.get():
            callback(None)
            return

        def _blurb_cb(blurb):
            if blurb:
                self._run_on_ui(lambda: callback(blurb))
                return

            def _meta_cb(data):
                self._run_on_ui(lambda: callback(self._build_edsm_note(data)))

            self.edsm.fetch_system_details(system_name, _meta_cb)

        self.edsm.fetch_system_blurb(system_name, _blurb_cb)

    def _build_edsm_note(self, data):
        if not isinstance(data, dict):
            return None
        info = data.get("information", {})
        if not isinstance(info, dict):
            return None

        parts = []
        alg = info.get("allegiance")
        if alg:
            parts.append(f"Alg {alg}")
        gov = info.get("government")
        if gov:
            parts.append(f"Gov {gov}")
        sec = info.get("security")
        if sec:
            parts.append(f"Sec {sec}")
        eco = info.get("economy")
        eco2 = info.get("secondEconomy")
        if eco and eco2:
            parts.append(f"Eco {eco}/{eco2}")
        elif eco:
            parts.append(f"Eco {eco}")
        pop = info.get("population")
        if isinstance(pop, int) and pop > 0:
            parts.append(f"Pop {self._format_population(pop)}")
        reserve = info.get("reserve")
        if reserve:
            parts.append(f"Res {reserve}")
        faction = info.get("faction")
        faction_state = info.get("factionState")
        if faction and faction_state and faction_state != "None":
            parts.append(f"Fac {faction} ({faction_state})")
        elif faction:
            parts.append(f"Fac {faction}")
        return " | ".join(parts) if parts else None

    def _format_population(self, value):
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.1f}B"
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        if value >= 1_000:
            return f"{value / 1_000:.1f}K"
        return str(value)

    def _merge_notes(self, manual_note, edsm_note):
        if manual_note and edsm_note:
            return f"{manual_note} | {edsm_note}"
        return manual_note or edsm_note

    def _apply_edsm_note_to_waypoints(self, system_name, edsm_note):
        if not edsm_note or not system_name:
            return
        changed = False
        for wp in self.manager.waypoints:
            if wp.get("name", "").lower() != system_name.lower():
                continue
            current = wp.get("note")
            if not current:
                wp["note"] = edsm_note
                changed = True
            elif edsm_note not in current:
                wp["note"] = f"{current} | {edsm_note}"
                changed = True
        if changed:
            self.manager.save()
            self.refresh_list()

    def export_route_csv(self):
        if not self.manager.waypoints:
            messagebox.showinfo("Export Route", "No waypoints to export.")
            self._emit_event("ROUTE", "CSV export skipped: no waypoints", "WARN")
            return

        filename = f"route_export_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        path = os.path.join(os.getcwd(), filename)

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["index", "name", "visited", "note", "x", "y", "z", "segment_ly", "cumulative_ly"])
                prev_coords = self.current_coords
                cumulative = 0.0
                for i, wp in enumerate(self.manager.waypoints, start=1):
                    coords = wp.get("coords")
                    segment = ""
                    x = y = z = ""
                    if isinstance(coords, dict):
                        x = coords.get("x", "")
                        y = coords.get("y", "")
                        z = coords.get("z", "")
                    if coords and prev_coords:
                        try:
                            segment_val = self.manager.get_distance(prev_coords, coords)
                            cumulative += segment_val
                            segment = f"{segment_val:.2f}"
                        except Exception:
                            segment = ""
                        prev_coords = coords
                    elif coords:
                        prev_coords = coords
                    w.writerow([
                        i,
                        wp.get("name", ""),
                        "yes" if wp.get("visited", False) else "no",
                        wp.get("note", "") or "",
                        x, y, z,
                        segment,
                        f"{cumulative:.2f}" if segment else "",
                    ])
            messagebox.showinfo("Export Route", f"Exported route to:\n{path}")
            self._emit_event("ROUTE", f"CSV export complete: {os.path.basename(path)}", "INFO", copy_text=path)
        except Exception as e:
            messagebox.showerror("Export Route", f"Export failed:\n{e}")
            self._emit_event("ROUTE", f"CSV export failed: {e}", "FAIL")

    def refresh_route_from_edsm(self):
        if self.route_refresh_running:
            return
        if not self.manager.waypoints:
            messagebox.showinfo("Refresh Route", "No waypoints to refresh.")
            self._emit_event("ROUTE", "EDSM refresh skipped: no waypoints", "WARN")
            return

        self.route_refresh_running = True
        self.refresh_route_btn.config(state=tk.DISABLED, text="[ REFRESHING... ]")
        self._emit_event("ROUTE", "EDSM refresh started", "INFO")
        self._route_refresh_state = {
            "remaining": len(self.manager.waypoints),
            "updated_coords": 0,
            "updated_names": 0,
            "updated_notes": 0,
            "failed": 0,
            "changed": False,
        }

        for idx, wp in enumerate(list(self.manager.waypoints)):
            name = wp.get("name", "")
            self.edsm.fetch_system_coords(
                name,
                lambda resolved_name, coords, i=idx: self.root.after(
                    0, lambda: self._on_refreshed_coords(i, resolved_name, coords)
                ),
            )

    def _on_refreshed_coords(self, index, resolved_name, coords):
        if not self.route_refresh_running:
            return
        lookup_name = resolved_name
        if not lookup_name and 0 <= index < len(self.manager.waypoints):
            lookup_name = self.manager.waypoints[index].get("name")
        self._fetch_edsm_note(lookup_name, lambda note: self._apply_refreshed_waypoint(index, resolved_name, coords, note))

    def _apply_refreshed_waypoint(self, index, resolved_name, coords, edsm_note):
        if not self.route_refresh_running or not self._route_refresh_state:
            return
        st = self._route_refresh_state

        if 0 <= index < len(self.manager.waypoints):
            wp = self.manager.waypoints[index]
            if resolved_name and wp.get("name") != resolved_name:
                wp["name"] = resolved_name
                st["updated_names"] += 1
                st["changed"] = True
            if coords is None:
                st["failed"] += 1
            elif wp.get("coords") != coords:
                wp["coords"] = coords
                st["updated_coords"] += 1
                st["changed"] = True
            if edsm_note:
                current_note = wp.get("note")
                if not current_note:
                    wp["note"] = edsm_note
                    st["updated_notes"] += 1
                    st["changed"] = True
                elif edsm_note not in current_note:
                    wp["note"] = f"{current_note} | {edsm_note}"
                    st["updated_notes"] += 1
                    st["changed"] = True
        else:
            st["failed"] += 1

        st["remaining"] -= 1
        if st["remaining"] <= 0:
            if st["changed"]:
                self.manager.save()
            unchanged = len(self.manager.waypoints) - st["updated_coords"] - st["updated_names"] - st["updated_notes"] - st["failed"]
            self.refresh_list()
            self.route_refresh_running = False
            self.refresh_route_btn.config(state=tk.NORMAL, text="REFRESH FROM EDSM")
            self._route_refresh_state = None
            messagebox.showinfo(
                "Refresh Route",
                (
                    f"Updated Coords: {st['updated_coords']}\n"
                    f"Updated Names: {st['updated_names']}\n"
                    f"Updated Notes: {st['updated_notes']}\n"
                    f"Unchanged: {max(unchanged, 0)}\n"
                    f"Unresolved: {st['failed']}"
                ),
            )
            self._emit_event(
                "ROUTE",
                f"EDSM refresh done: coords {st['updated_coords']}, names {st['updated_names']}, notes {st['updated_notes']}, unresolved {st['failed']}",
                "INFO",
            )

    def on_close(self):
        if self.config:
            self.config["route_plotter_geometry"] = self.win.geometry()
            if hasattr(self, "neutron_from_entry"):
                self.config["system_plotter_form"] = {
                    "from": self.neutron_from_entry.get().strip(),
                    "to": self.neutron_to_entry.get().strip(),
                    "range": self.neutron_range_entry.get().strip(),
                    "efficiency": self.neutron_eff_entry.get().strip(),
                    "supercharge_multiplier": self._selected_supercharge_multiplier(),
                }
            try:
                save_config(self.config)
            except Exception:
                pass
        self.win.destroy()
