import tkinter as tk
import json
from tkinter import messagebox
from config import COLOR_BG, COLOR_PANEL, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, CONFIG_FILE
from waypoint_manager import WaypointManager


class RoutePlotter:
    def __init__(self, root, edsm_handler, current_coords=None, current_sys="Unknown", config=None, manager=None, on_change_callback=None):
        self.root = root
        self.edsm = edsm_handler
        self.manager = manager if manager else WaypointManager()
        self.current_coords = current_coords
        self.current_sys = current_sys
        self.config = config if config is not None else {}
        self.on_change_callback = on_change_callback

        self.win = tk.Toplevel(root)
        self.win.title("ROUTE & WAYPOINT MANAGER")
        self.win.geometry(self.config.get("route_plotter_geometry", "920x640"))
        self.win.configure(bg=COLOR_BG)
        self.win.protocol("WM_DELETE_WINDOW", self.on_close)

        self.setup_ui()
        self.refresh_list()

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
        input_panel.grid_columnconfigure(1, weight=2)
        input_panel.grid_columnconfigure(3, weight=1)

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
            activestyle="none"
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
        self.sel_state_lbl = tk.Label(side, text="State: -", font=("Courier", 8), fg="#888", bg=COLOR_PANEL, anchor="w")
        self.sel_state_lbl.pack(fill=tk.X, padx=10, pady=(2, 8))

        def mk_btn(parent, text, cmd, bg=COLOR_PANEL, fg=COLOR_TEXT):
            return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, font=("Courier", 9, "bold"), relief=tk.FLAT, width=20)

        mk_btn(side, "COPY SELECTED", self.copy_selected, COLOR_ACCENT, "black").pack(padx=10, pady=2)
        mk_btn(side, "DELETE SELECTED", self.remove, "#331111", "red").pack(padx=10, pady=2)
        mk_btn(side, "EDIT SELECTED", self.edit_selected).pack(padx=10, pady=2)
        mk_btn(side, "TOGGLE DONE", self.toggle_visited).pack(padx=10, pady=2)
        mk_btn(side, "MOVE UP", self.move_up).pack(padx=10, pady=(8, 2))
        mk_btn(side, "MOVE DOWN", self.move_down).pack(padx=10, pady=2)
        mk_btn(side, "CLEAR ALL", self.clear_all, "#331111", "red").pack(padx=10, pady=(10, 2))

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

    def get_selected_index(self):
        sel = self.listbox.curselection()
        return sel[0] if sel else None

    def add_system(self):
        sys_name = self.entry.get().strip()
        note = self.note_entry.get().strip() or None
        if not sys_name:
            return

        self.entry.delete(0, tk.END)
        self.entry.insert(0, "Searching...")
        self.entry.config(state=tk.DISABLED)
        self.note_entry.config(state=tk.DISABLED)

        def cb(name, coords):
            self.entry.config(state=tk.NORMAL)
            self.note_entry.config(state=tk.NORMAL)
            self.entry.delete(0, tk.END)
            self.note_entry.delete(0, tk.END)
            self.manager.add_waypoint(name, coords, note)
            self.refresh_list(select_last=True)

        self.edsm.fetch_system_coords(sys_name, cb)

    def refresh_list(self, select_index=None, select_last=False):
        previous = self.get_selected_index()
        self.listbox.delete(0, tk.END)
        total_dist = 0.0
        prev_coords = self.current_coords

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
        idx = self.get_selected_index()
        if idx is None or idx >= len(self.manager.waypoints):
            self.sel_name_lbl.config(text="Name: -")
            self.sel_note_lbl.config(text="Note: -")
            self.sel_dist_lbl.config(text="Distance: -")
            self.sel_state_lbl.config(text="State: -")
            return

        wp = self.manager.waypoints[idx]
        name = wp.get("name", "Unknown")
        note = wp.get("note") or "-"
        visited = wp.get("visited", False)
        coords = wp.get("coords")

        dist = "---"
        if coords and self.current_coords:
            try:
                d = self.manager.get_distance(self.current_coords, coords)
                dist = f"{d:,.1f} LY"
            except Exception:
                pass

        self.sel_name_lbl.config(text=f"Name: {name}")
        self.sel_note_lbl.config(text=f"Note: {note}")
        self.sel_dist_lbl.config(text=f"Distance: {dist}")
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
            new_note = note_entry.get().strip() or None
            if not new_name:
                save_geometry()
                dlg.destroy()
                return
            name_entry.config(state=tk.DISABLED)
            note_entry.config(state=tk.DISABLED)

            def cb(name, coords):
                self.manager.edit_waypoint(idx, name, coords, new_note)
                self.refresh_list(select_index=idx)
                save_geometry()
                dlg.destroy()

            self.edsm.fetch_system_coords(new_name, cb)

        tk.Button(dlg, text="[ SAVE ]", command=on_save, bg=COLOR_ACCENT, fg="black", font=("Courier", 9, "bold"), relief=tk.FLAT).pack(pady=16)
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

    def remove(self):
        idx = self.get_selected_index()
        if idx is None:
            return
        self.manager.remove_waypoint(idx)
        new_idx = idx if idx < len(self.manager.waypoints) else len(self.manager.waypoints) - 1
        self.refresh_list(select_index=new_idx if new_idx >= 0 else None)

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
        for line in systems:
            name = line
            note = None
            if "," in line:
                parts = line.split(",", 1)
                name = parts[0].strip()
                if len(parts) > 1 and parts[1].strip():
                    note = parts[1].strip()
            self.manager.add_waypoint(name, None, note)
        self.refresh_list()

        for line in systems:
            name = line.split(",", 1)[0].strip() if "," in line else line.strip()
            self.edsm.fetch_system_coords(name, self._bulk_update_cb)

    def _bulk_update_cb(self, name, coords):
        if not coords:
            return
        for i, wp in enumerate(self.manager.waypoints):
            if wp["coords"] is None and wp["name"].lower() == name.lower():
                self.manager.update_coords(i, coords)
                self.refresh_list(select_index=i)
                break

    def toggle_auto_copy(self):
        self.config["auto_copy_waypoint"] = self.ac_var.get()

    def on_close(self):
        if self.config:
            self.config["route_plotter_geometry"] = self.win.geometry()
            try:
                with open(CONFIG_FILE, "w") as f:
                    json.dump(self.config, f, indent=4)
            except Exception:
                pass
        self.win.destroy()
