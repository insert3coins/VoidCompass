import tkinter as tk
import json
import os
import csv
import time
from tkinter import messagebox, filedialog
from config import COLOR_BG, COLOR_PANEL, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, CONFIG_FILE
from waypoint_manager import WaypointManager


class RoutePlotter:
    def __init__(self, root, edsm_handler, current_coords=None, current_sys="Unknown", config=None, manager=None, on_change_callback=None, event_callback=None):
        self.root = root
        self.edsm = edsm_handler
        self.manager = manager if manager else WaypointManager()
        self.current_coords = current_coords
        self.current_sys = current_sys
        self.config = config if config is not None else {}
        self.on_change_callback = on_change_callback
        self.event_callback = event_callback
        self.route_refresh_running = False
        self._route_refresh_state = None
        self.duplicate_mode = self.config.get("route_duplicate_mode", "skip")
        self.pending_import_jobs = {}

        self.win = tk.Toplevel(root)
        self.win.title("ROUTE & WAYPOINT MANAGER")
        self.win.geometry(self.config.get("route_plotter_geometry", "1020x700"))
        self.win.configure(bg=COLOR_BG)
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

        input_panel = tk.Frame(wrapper, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        input_panel.pack(fill=tk.X, pady=(8, 0))
        tk.Label(input_panel, text="SYSTEM:", font=("Courier", 9), fg="#888", bg=COLOR_PANEL).grid(row=0, column=0, sticky="w", padx=(10, 6), pady=8)
        self.entry = tk.Entry(input_panel, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=8, ipady=3)
        self.entry.bind("<Return>", lambda e: self.add_system())

        tk.Label(input_panel, text="NOTE:", font=("Courier", 9), fg="#888", bg=COLOR_PANEL).grid(row=0, column=2, sticky="w", padx=(6, 6), pady=8)
        self.note_entry = tk.Entry(input_panel, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.note_entry.grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=8, ipady=3)

        tk.Button(input_panel, text="[ ADD ]", command=self.add_system, bg=COLOR_ACCENT, fg="black", font=("Courier", 9, "bold"), relief=tk.FLAT).grid(row=0, column=4, padx=(0, 6))
        tk.Button(input_panel, text="[ IMPORT ]", command=self.open_import_dialog, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 9, "bold"), relief=tk.FLAT).grid(row=0, column=5, padx=(0, 10))
        tk.Button(input_panel, text="[ IMPORT SPANSH CSV ]", command=self.import_spansh_csv, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 9, "bold"), relief=tk.FLAT).grid(row=0, column=6, padx=(0, 10))
        self.dup_btn = tk.Button(input_panel, text="", command=self.cycle_duplicate_mode, bg=COLOR_PANEL, fg="#aaa", font=("Courier", 8, "bold"), relief=tk.FLAT)
        self.dup_btn.grid(row=0, column=7, padx=(0, 10))
        input_panel.grid_columnconfigure(1, weight=2)
        input_panel.grid_columnconfigure(3, weight=1)
        self._update_duplicate_mode_btn()

        content = tk.Frame(wrapper, bg=COLOR_BG)
        content.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        list_wrap = tk.Frame(content, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        list_wrap.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(list_wrap, text=f"{'ID':<3}{'S':<2}{'SYSTEM':<30}{'DIST':<12}NOTE", font=("Courier", 9, "bold"), fg="#777", bg=COLOR_PANEL, anchor="w").pack(fill=tk.X, padx=8, pady=(8, 4))

        list_frame = tk.Frame(list_wrap, bg=COLOR_PANEL)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.listbox = tk.Listbox(
            list_frame, bg="#050505", fg=COLOR_TEXT, font=("Courier", 10), relief=tk.FLAT,
            highlightthickness=1, highlightbackground="#333", selectbackground=COLOR_ACCENT, selectforeground="black",
            activestyle="none", selectmode=tk.EXTENDED
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=sb.set)
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._update_selection_panel())
        self.listbox.bind("<Double-Button-1>", lambda e: self.edit_selected())
        self.listbox.bind("<Delete>", lambda e: self.remove())
        self.listbox.bind("<Control-c>", lambda e: self.copy_selected())

        side = tk.Frame(content, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        side.grid(row=0, column=1, sticky="nsew")
        tk.Label(side, text="SELECTION", font=("Courier", 10, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(8, 4))
        self.sel_name_lbl = tk.Label(side, text="Name: -", font=("Courier", 9, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL, anchor="w")
        self.sel_name_lbl.pack(fill=tk.X, padx=10, pady=2)
        self.sel_note_lbl = tk.Label(side, text="Note: -", font=("Courier", 8), fg="#aaa", bg=COLOR_PANEL, anchor="w", justify=tk.LEFT, wraplength=210)
        self.sel_note_lbl.pack(fill=tk.X, padx=10, pady=2)
        self.sel_dist_lbl = tk.Label(side, text="Distance: -", font=("Courier", 8), fg="#aaa", bg=COLOR_PANEL, anchor="w")
        self.sel_dist_lbl.pack(fill=tk.X, padx=10, pady=2)
        self.sel_seg_lbl = tk.Label(side, text="Segment: -", font=("Courier", 8), fg="#aaa", bg=COLOR_PANEL, anchor="w")
        self.sel_seg_lbl.pack(fill=tk.X, padx=10, pady=2)
        self.sel_cum_lbl = tk.Label(side, text="Cumulative: -", font=("Courier", 8), fg="#aaa", bg=COLOR_PANEL, anchor="w")
        self.sel_cum_lbl.pack(fill=tk.X, padx=10, pady=2)
        self.sel_state_lbl = tk.Label(side, text="State: -", font=("Courier", 8), fg="#888", bg=COLOR_PANEL, anchor="w")
        self.sel_state_lbl.pack(fill=tk.X, padx=10, pady=(2, 6))

        tk.Label(side, text="ROUTE HEALTH", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(8, 2))
        self.health_lbl = tk.Label(side, text="Pending: 0 | Visited: 0 | Missing Coords: 0 | Duplicates: 0", font=("Courier", 8), fg="#aaa", bg=COLOR_PANEL, justify=tk.LEFT, wraplength=230, anchor="w")
        self.health_lbl.pack(fill=tk.X, padx=10, pady=(0, 8))

        def mk_btn(parent, text, cmd, bg=COLOR_PANEL, fg=COLOR_TEXT):
            return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, font=("Courier", 9, "bold"), relief=tk.FLAT, width=22)

        def section(title):
            tk.Label(side, text=title, font=("Courier", 8, "bold"), fg="#777", bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(8, 2))

        section("SELECTION ACTIONS")
        mk_btn(side, "COPY SELECTED", self.copy_selected, COLOR_ACCENT, "black").pack(padx=10, pady=2)
        mk_btn(side, "EDIT SELECTED", self.edit_selected).pack(padx=10, pady=2)
        mk_btn(side, "TOGGLE DONE", self.toggle_visited).pack(padx=10, pady=2)
        mk_btn(side, "DELETE SELECTED", self.remove, "#331111", "red").pack(padx=10, pady=2)

        section("BATCH ACTIONS")
        mk_btn(side, "COPY SELECTED (BATCH)", self.copy_selected_batch).pack(padx=10, pady=2)
        mk_btn(side, "MARK SELECTED DONE", self.mark_selected_done).pack(padx=10, pady=2)
        mk_btn(side, "MARK SELECTED TODO", self.mark_selected_todo).pack(padx=10, pady=2)
        mk_btn(side, "DELETE SELECTED (BATCH)", self.remove_selected_batch, "#331111", "red").pack(padx=10, pady=2)

        section("ROUTE STRUCTURE")
        mk_btn(side, "MOVE UP", self.move_up).pack(padx=10, pady=2)
        mk_btn(side, "MOVE DOWN", self.move_down).pack(padx=10, pady=2)
        self.refresh_route_btn = mk_btn(side, "REFRESH FROM EDSM", self.refresh_route_from_edsm, COLOR_PANEL, COLOR_ACCENT)
        self.refresh_route_btn.pack(padx=10, pady=2)
        mk_btn(side, "CLEAR ALL", self.clear_all, "#331111", "red").pack(padx=10, pady=2)

        section("DATA I/O")
        mk_btn(side, "EXPORT ROUTE CSV", self.export_route_csv, COLOR_PANEL, COLOR_ACCENT).pack(padx=10, pady=(2, 6))

        footer = tk.Frame(wrapper, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        footer.pack(fill=tk.X, pady=(8, 0))
        self.stats_lbl = tk.Label(footer, text="TOTAL PLOTTED DISTANCE: 0.0 LY", font=("Courier", 10, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL)
        self.stats_lbl.pack(side=tk.LEFT, padx=10, pady=8)
        self.ac_var = tk.BooleanVar(value=self.config.get("auto_copy_waypoint", False))
        cb = tk.Checkbutton(
            footer, text="AUTO-COPY NEXT WAYPOINT", variable=self.ac_var, command=self.toggle_auto_copy,
            bg=COLOR_PANEL, fg=COLOR_TEXT, selectcolor=COLOR_PANEL, activebackground=COLOR_PANEL, activeforeground=COLOR_TEXT,
            font=("Courier", 8)
        )
        cb.pack(side=tk.RIGHT, padx=10)
        self.auto_note_var = tk.BooleanVar(value=self.config.get("route_auto_note_from_edsm", True))
        auto_note_cb = tk.Checkbutton(
            footer, text="AUTO NOTE FROM EDSM", variable=self.auto_note_var, command=self.toggle_auto_note,
            bg=COLOR_PANEL, fg=COLOR_TEXT, selectcolor=COLOR_PANEL, activebackground=COLOR_PANEL, activeforeground=COLOR_TEXT,
            font=("Courier", 8)
        )
        auto_note_cb.pack(side=tk.RIGHT, padx=(4, 10))

    def get_selected_index(self):
        sel = self.listbox.curselection()
        return sel[0] if sel else None

    def _run_on_ui(self, fn):
        self.root.after(0, fn)

    def get_selected_indices(self):
        return list(self.listbox.curselection())

    def _update_duplicate_mode_btn(self):
        label = {"skip": "DUP: SKIP", "append": "DUP: APPEND NOTE", "keep": "DUP: KEEP BOTH"}.get(self.duplicate_mode, "DUP: SKIP")
        self.dup_btn.config(text=f"[ {label} ]")

    def cycle_duplicate_mode(self):
        modes = ["skip", "append", "keep"]
        idx = modes.index(self.duplicate_mode) if self.duplicate_mode in modes else 0
        self.duplicate_mode = modes[(idx + 1) % len(modes)]
        self.config["route_duplicate_mode"] = self.duplicate_mode
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
        previous = self.get_selected_index()
        self.listbox.delete(0, tk.END)
        total_dist = 0.0
        prev_coords = self.current_coords
        missing_coords = 0

        current_idx = self.manager.get_waypoint_index(self.current_sys)
        for i, wp in enumerate(self.manager.waypoints):
            name = wp["name"]
            coords = wp.get("coords")
            note = wp.get("note")
            is_visited = wp.get("visited", False)

            dist_str = "---"
            if coords and prev_coords:
                d = self.manager.get_distance(prev_coords, coords)
                total_dist += d
                dist_str = f"{d:,.1f} LY"
                prev_coords = coords
            elif coords:
                prev_coords = coords
            else:
                missing_coords += 1

            marker = "|"
            if i == current_idx:
                marker = ">"
            elif is_visited:
                marker = "x"

            note_text = f" [{note}]" if note else ""
            line = f"{i+1:02d} {marker:<2}{name:<30}{dist_str:<12}{note_text}"
            self.listbox.insert(tk.END, line)

            if i == current_idx:
                self.listbox.itemconfig(i, {"fg": COLOR_ORANGE})
            elif is_visited:
                self.listbox.itemconfig(i, {"fg": "#555"})

        self.stats_lbl.config(text=f"TOTAL PLOTTED DISTANCE: {total_dist:,.1f} LY")
        self.header_current_lbl.config(text=f"CURRENT: {self.current_sys}")

        visited_count = sum(1 for wp in self.manager.waypoints if wp.get("visited", False))
        pending_count = len(self.manager.waypoints) - visited_count
        seen = set()
        dup_count = 0
        for wp in self.manager.waypoints:
            n = wp.get("name", "").lower()
            if n in seen:
                dup_count += 1
            else:
                seen.add(n)
        self.health_lbl.config(
            text=f"Pending: {pending_count} | Visited: {visited_count}\nMissing Coords: {missing_coords} | Duplicates: {dup_count}"
        )

        target = previous
        if select_last and self.manager.waypoints:
            target = len(self.manager.waypoints) - 1
        if select_index is not None:
            target = select_index
        if target is not None and 0 <= target < len(self.manager.waypoints):
            self.listbox.selection_set(target)
            self.listbox.see(target)

        self._update_selection_panel()

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
        self.current_sys = sys_name
        self.current_coords = coords
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
                with open(CONFIG_FILE, "w") as f:
                    json.dump(self.config, f, indent=4)
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
        tk.Button(btn_row, text="CANCEL", command=lambda: (save_geometry(), dlg.destroy()), bg="#222", fg="#888", font=("Courier", 9, "bold"), relief=tk.FLAT, width=10).pack(side=tk.LEFT)
        tk.Button(btn_row, text="SAVE", command=on_save, bg=COLOR_ACCENT, fg="black", font=("Courier", 9, "bold"), relief=tk.FLAT, width=10).pack(side=tk.RIGHT)
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
        self.root.update()

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
        self.root.update()

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
        for idx in sorted(idxs, reverse=True):
            if 0 <= idx < len(self.manager.waypoints):
                self.manager.remove_waypoint(idx)
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
                with open(CONFIG_FILE, "w") as f:
                    json.dump(self.config, f, indent=4)
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

        tk.Button(dlg, text="[ PROCESS LIST ]", command=do_import, bg=COLOR_ACCENT, fg="black", font=("Courier", 10, "bold"), relief=tk.FLAT).pack(fill=tk.X, padx=10, pady=10)

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

    def _start_import_job(self, records):
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

    def toggle_auto_note(self):
        self.config["route_auto_note_from_edsm"] = self.auto_note_var.get()

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
            try:
                with open(CONFIG_FILE, "w") as f:
                    json.dump(self.config, f, indent=4)
            except Exception:
                pass
        self.win.destroy()
