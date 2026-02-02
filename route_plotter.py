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
        self.win.geometry(self.config.get("route_plotter_geometry", "600x600"))
        self.win.configure(bg=COLOR_BG)
        self.win.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.setup_ui()
        self.refresh_list()

    def setup_ui(self):
        # Header
        header = tk.Frame(self.win, bg=COLOR_PANEL, height=40)
        header.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(header, text=" // FLIGHT PLANNER", font=("Courier", 14, "bold"), fg=COLOR_ACCENT, bg=COLOR_PANEL).pack(side=tk.LEFT, padx=10, pady=5)
        
        # Input Area
        input_frame = tk.Frame(self.win, bg=COLOR_BG)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(input_frame, text="SYSTEM NAME:", font=("Courier", 10), fg="#888", bg=COLOR_BG).pack(side=tk.LEFT)
        self.entry = tk.Entry(input_frame, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, ipady=3)
        self.entry.bind("<Return>", lambda e: self.add_system())
        
        btn_add = tk.Button(input_frame, text="[ ADD ]", command=self.add_system, bg=COLOR_ACCENT, fg="black", font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn_add.pack(side=tk.RIGHT)

        btn_imp = tk.Button(input_frame, text="[ IMPORT ]", command=self.open_import_dialog, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn_imp.pack(side=tk.RIGHT, padx=5)

        # List Area
        list_frame = tk.Frame(self.win, bg=COLOR_BG)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Column Header
        header_str = f"{'ID':<2} {'S':<1} {'SYSTEM NAME':<25} | {'DISTANCE'}    {'NOTE'}"
        tk.Label(list_frame, text=header_str, font=("Courier", 10), fg="#888", bg=COLOR_BG, anchor="w").pack(fill=tk.X, pady=(0, 2))

        self.listbox = tk.Listbox(list_frame, bg="#050505", fg=COLOR_TEXT, font=("Courier", 10), relief=tk.FLAT, highlightthickness=1, highlightbackground="#333", selectbackground=COLOR_ACCENT, selectforeground="black")
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        sb = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=sb.set)

        # Controls
        ctrl_frame = tk.Frame(self.win, bg=COLOR_BG)
        ctrl_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def mk_btn(txt, cmd, color=COLOR_PANEL, fg=COLOR_TEXT):
            return tk.Button(ctrl_frame, text=txt, command=cmd, bg=color, fg=fg, font=("Courier", 9, "bold"), relief=tk.FLAT, width=12)

        mk_btn("MOVE UP", self.move_up).pack(side=tk.LEFT, padx=(0, 5))
        mk_btn("MOVE DOWN", self.move_down).pack(side=tk.LEFT, padx=5)
        mk_btn("EDIT", self.edit_selected).pack(side=tk.LEFT, padx=5)
        mk_btn("MARK DONE", self.toggle_visited, COLOR_ACCENT, "black").pack(side=tk.LEFT, padx=5)
        mk_btn("REMOVE", self.remove, "#331111", "red").pack(side=tk.RIGHT, padx=(5, 0))
        mk_btn("CLEAR ALL", self.clear_all, "#331111", "red").pack(side=tk.RIGHT)

        # Stats Footer
        self.stats_lbl = tk.Label(self.win, text="TOTAL DISTANCE: 0.0 LY", font=("Courier", 10, "bold"), fg=COLOR_ORANGE, bg=COLOR_BG)
        self.stats_lbl.pack(side=tk.BOTTOM, pady=10)

        # Auto-Copy Checkbox
        self.ac_var = tk.BooleanVar(value=self.config.get("auto_copy_waypoint", False))
        cb = tk.Checkbutton(self.win, text="AUTO-COPY NEXT WAYPOINT", variable=self.ac_var, command=self.toggle_auto_copy, bg=COLOR_BG, fg=COLOR_TEXT, selectcolor=COLOR_BG, activebackground=COLOR_BG, activeforeground=COLOR_TEXT, font=("Courier", 8))
        cb.pack(side=tk.BOTTOM, anchor="w", padx=10, pady=(0, 5))

    def add_system(self):
        sys_name = self.entry.get().strip()
        if not sys_name: return
        
        self.entry.delete(0, tk.END)
        self.entry.insert(0, "Searching...")
        self.entry.config(state=tk.DISABLED)
        
        def cb(name, coords):
            self.entry.config(state=tk.NORMAL)
            self.entry.delete(0, tk.END)
            if coords:
                self.manager.add_waypoint(name, coords)
                self.refresh_list()
            else:
                # Add anyway but without coords
                self.manager.add_waypoint(name, None)
                self.refresh_list()
        
        self.edsm.fetch_system_coords(sys_name, cb)

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        total_dist = 0.0
        prev_coords = self.current_coords
        
        # Determine current waypoint index for status markers
        current_idx = self.manager.get_waypoint_index(self.current_sys)
        
        for i, wp in enumerate(self.manager.waypoints):
            name = wp['name']
            coords = wp['coords']
            note = wp.get('note')
            is_visited = wp.get('visited', False)
            dist_str = "---"
            
            if coords and prev_coords:
                d = self.manager.get_distance(prev_coords, coords)
                total_dist += d
                dist_str = f"{d:,.1f} LY"
                prev_coords = coords
            elif coords:
                prev_coords = coords # Start measuring from here if we lost the chain
            
            marker = "|"
            if i == current_idx:
                marker = "📍"
            elif is_visited:
                marker = "✓"
            
            display = f"{i+1:02d} {marker} {name:<25} | +{dist_str}"
            if note:
                display += f" [{note}]"
            self.listbox.insert(tk.END, display)
            
            # Highlight current and dim completed
            if i == current_idx:
                self.listbox.itemconfig(i, {'fg': COLOR_ORANGE})
            elif is_visited:
                self.listbox.itemconfig(i, {'fg': '#555'})
            
        self.stats_lbl.config(text=f"TOTAL PLOTTED DISTANCE: {total_dist:,.1f} LY")

        if self.on_change_callback:
            self.root.after(0, self.on_change_callback)

    def update_current_system(self, sys_name, coords):
        self.current_sys = sys_name
        self.current_coords = coords
        self.refresh_list()

    def move_up(self):
        sel = self.listbox.curselection()
        if not sel: return
        idx = sel[0]
        if self.manager.move_up(idx):
            self.refresh_list()
            self.listbox.selection_set(idx-1)

    def move_down(self):
        sel = self.listbox.curselection()
        if not sel: return
        idx = sel[0]
        if self.manager.move_down(idx):
            self.refresh_list()
            self.listbox.selection_set(idx+1)

    def toggle_visited(self):
        sel = self.listbox.curselection()
        if not sel: return
        idx = sel[0]
        wp = self.manager.waypoints[idx]
        wp['visited'] = not wp.get('visited', False)
        
        self.manager.save()
            
        self.refresh_list()

    def edit_selected(self):
        sel = self.listbox.curselection()
        if not sel: return
        idx = sel[0]
        current_wp = self.manager.waypoints[idx]
        current_note = current_wp.get("note")
        
        dlg = tk.Toplevel(self.win)
        dlg.title("EDIT WAYPOINT")
        dlg.geometry(self.config.get("edit_dialog_geometry", "300x150"))
        dlg.configure(bg=COLOR_BG)
        dlg.grab_set()
        
        tk.Label(dlg, text="SYSTEM NAME:", font=("Courier", 10), fg="#888", bg=COLOR_BG).pack(pady=(20, 5))
        
        e = tk.Entry(dlg, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        e.insert(0, current_wp['name'])
        e.pack(fill=tk.X, padx=20, ipady=3)
        e.select_range(0, tk.END)
        e.focus_set()
        
        def save_geometry():
            self.config["edit_dialog_geometry"] = dlg.geometry()
            try:
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(self.config, f, indent=4)
            except:
                pass

        def on_save():
            new_name = e.get().strip()
            if new_name:
                e.config(state=tk.DISABLED)
                def cb(name, coords):
                    self.manager.edit_waypoint(idx, name, coords, current_note)
                    self.refresh_list()
                    save_geometry()
                    dlg.destroy()
                self.edsm.fetch_system_coords(new_name, cb)
            else:
                save_geometry()
                dlg.destroy()

        tk.Button(dlg, text="[ SAVE ]", command=on_save, bg=COLOR_ACCENT, fg="black", font=("Courier", 9, "bold"), relief=tk.FLAT).pack(pady=20)
        dlg.bind("<Return>", lambda event: on_save())
        dlg.protocol("WM_DELETE_WINDOW", lambda: (save_geometry(), dlg.destroy()))

    def remove(self):
        sel = self.listbox.curselection()
        if not sel: return
        self.manager.remove_waypoint(sel[0])
        self.refresh_list()

    def clear_all(self):
        if messagebox.askyesno("Confirm", "Clear all waypoints?"):
            self.manager.clear()
            self.refresh_list()

    def open_import_dialog(self):
        dlg = tk.Toplevel(self.win)
        dlg.title("BULK IMPORT")
        dlg.geometry(self.config.get("import_dialog_geometry", "400x500"))
        dlg.configure(bg=COLOR_BG)
        dlg.grab_set()
        
        tk.Label(dlg, text="PASTE SYSTEM LIST (ONE PER LINE):", font=("Courier", 10), fg=COLOR_ORANGE, bg=COLOR_BG).pack(pady=10)
        
        txt = tk.Text(dlg, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), height=20, relief=tk.FLAT, insertbackground=COLOR_ACCENT)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        txt.focus_set()
        
        def save_geometry():
            self.config["import_dialog_geometry"] = dlg.geometry()
            try:
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(self.config, f, indent=4)
            except:
                pass

        def on_dlg_close():
            save_geometry()
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", on_dlg_close)

        def do_import():
            content = txt.get("1.0", tk.END)
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            save_geometry()
            dlg.destroy()
            self.process_bulk_list(lines)
            
        tk.Button(dlg, text="[ PROCESS LIST ]", command=do_import, bg=COLOR_ACCENT, fg="black", font=("Courier", 10, "bold"), relief=tk.FLAT).pack(fill=tk.X, padx=10, pady=10)

    def process_bulk_list(self, systems):
        if not systems: return
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
        if not coords: return
        for i, wp in enumerate(self.manager.waypoints):
            if wp['coords'] is None and wp['name'].lower() == name.lower():
                self.manager.update_coords(i, coords)
                self.refresh_list()
                break

    def toggle_auto_copy(self):
        self.config["auto_copy_waypoint"] = self.ac_var.get()

    def on_close(self):
        if self.config:
            self.config["route_plotter_geometry"] = self.win.geometry()
            try:
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(self.config, f, indent=4)
            except:
                pass
        self.win.destroy()