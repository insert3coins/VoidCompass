import time
import tkinter as tk
import requests
import webbrowser
from datetime import datetime
from tkinter import scrolledtext

from config import COLOR_BG, COLOR_PANEL, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, COLOR_GREEN
from version import APP_VERSION


class DashboardUIMixin:
    def setup_layout(self):
        self.nav = tk.Frame(self.root, bg=COLOR_PANEL, height=50, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        self.nav.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        tk.Label(self.nav, text=f" > VOID COMPASS // V{APP_VERSION}", font=("Courier", 11, "bold"), fg=COLOR_ACCENT, bg=COLOR_PANEL).pack(side=tk.LEFT, padx=15)
        
        btn_conf = tk.Button(self.nav, text="[ CONFIGURATION ]", command=self.open_settings, bg=COLOR_PANEL, fg=COLOR_ORANGE, font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn_conf.pack(side=tk.RIGHT, padx=15)

        # Route Button
        btn_route = tk.Button(self.nav, text="[ ROUTE PLANNER ]", command=self.open_route_planner, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn_route.pack(side=tk.RIGHT, padx=5)
        
        # Screenshot Button
        btn_ss = tk.Button(self.nav, text="[ SCREENSHOTS ]", command=self.open_screenshots_folder, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn_ss.pack(side=tk.RIGHT, padx=5)

        self.summary_bar = tk.Frame(self.root, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1, height=34)
        self.summary_bar.pack(fill=tk.X, padx=10, pady=(8, 0))
        self.summary_bar.pack_propagate(False)

        def _summary_item(text):
            lbl = tk.Label(self.summary_bar, text=text, font=("Courier", 9, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL)
            lbl.pack(side=tk.LEFT, padx=14)
            return lbl

        self.summary_sys = _summary_item("SYS: ---")
        self.summary_route = _summary_item("ROUTE: INACTIVE")
        self.summary_scan = _summary_item("SCAN: 0/0")
        self.summary_traffic = _summary_item("TRAFFIC: 0/0/0")
        self.summary_session = _summary_item("SESSION: 00:00:00")

        self.alert_bar = tk.Frame(self.root, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1, height=30)
        self.alert_bar.pack(fill=tk.X, padx=10, pady=(6, 0))
        self.alert_bar.pack_propagate(False)
        tk.Label(self.alert_bar, text="ALERTS", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(side=tk.LEFT, padx=(10, 8))
        self.alert_lbl = tk.Label(self.alert_bar, text="NONE", font=("Courier", 9), fg="#888", bg=COLOR_PANEL, anchor="w")
        self.alert_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        body = tk.Frame(self.root, bg=COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.side = tk.Frame(body, bg=COLOR_PANEL, width=320, highlightbackground="#333", highlightthickness=1)
        self.side.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.side.pack_propagate(False)

        status_card = tk.Frame(self.side, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        status_card.pack(fill=tk.X, padx=10, pady=(10, 8))
        tk.Label(status_card, text="STATUS", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(6, 0))
        self.integration_lbl = tk.Label(status_card, text="HUD: ON | DISCORD: OFF | SHOTS: OFF", font=("Courier", 8), fg="#999", bg=COLOR_PANEL, anchor="w")
        self.integration_lbl.pack(fill=tk.X, padx=10, pady=(2, 8))

        metrics_card = tk.Frame(self.side, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        metrics_card.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(metrics_card, text="PINNED METRICS", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(6, 0))
        self.sys_stat = self.create_stat(metrics_card, "CURRENT SYSTEM", "---")
        self.nav_stat = self.create_stat(metrics_card, "NAV TARGET", "---")
        self.scan_stat = self.create_stat(metrics_card, "SCAN PROGRESS", "0 / 0")

        self.wp_panel = tk.Frame(self.side, bg=COLOR_PANEL, highlightbackground=COLOR_ACCENT, highlightthickness=1, height=180)
        self.wp_panel.pack(fill=tk.X, padx=10, pady=8)
        self.wp_panel.pack_propagate(False)
        header_row = tk.Frame(self.wp_panel, bg=COLOR_PANEL)
        header_row.pack(fill=tk.X, padx=10, pady=(5, 0))
        tk.Label(header_row, text="ROUTE NOTES", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(side=tk.LEFT)
        self.wp_dist_lbl = tk.Label(header_row, text="", font=("Courier", 9, "bold"), fg=COLOR_ACCENT, bg=COLOR_PANEL)
        self.wp_dist_lbl.pack(side=tk.RIGHT)
        self.wp_name_lbl = tk.Label(self.wp_panel, text="NO ACTIVE ROUTE", font=("Courier", 12, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL, anchor="w")
        self.wp_name_lbl.pack(fill=tk.X, padx=10, pady=(6, 0))
        self.wp_info_wrap = tk.Frame(self.wp_panel, bg=COLOR_PANEL)
        self.wp_info_wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2, 6))
        self.wp_info_scroll = tk.Scrollbar(self.wp_info_wrap, orient=tk.VERTICAL)
        self.wp_info_text = tk.Text(
            self.wp_info_wrap,
            bg=COLOR_PANEL,
            fg="#aaa",
            font=("Courier", 8),
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            wrap=tk.WORD,
            yscrollcommand=self.wp_info_scroll.set,
            height=7
        )
        self.wp_info_scroll.config(command=self.wp_info_text.yview)
        self.wp_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.wp_info_text.config(state=tk.DISABLED)
        self.wp_info_scroll_visible = False

        self.wp_info_text.bind("<Enter>", lambda e: self._toggle_wp_scrollbar(True))
        self.wp_info_text.bind("<Leave>", lambda e: self._toggle_wp_scrollbar(False))
        self.wp_info_text.bind("<MouseWheel>", self._on_wp_info_wheel)

        side_actions = tk.Frame(self.side, bg=COLOR_PANEL)
        side_actions.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        tk.Button(side_actions, text="[ REBUILD CACHE ]", command=self.scan_all_logs_threaded, bg=COLOR_PANEL, fg="#777", font=("Courier", 8, "bold"), relief=tk.FLAT, activebackground=COLOR_PANEL, activeforeground=COLOR_TEXT).pack(side=tk.LEFT)
        tk.Label(side_actions, text="© 2026 insert3coins", font=("Courier", 8), fg="#444", bg=COLOR_PANEL).pack(side=tk.RIGHT)

        center = tk.Frame(body, bg=COLOR_BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ops = tk.Frame(center, bg=COLOR_BG)
        ops.pack(fill=tk.X)
        for col in range(3):
            ops.grid_columnconfigure(col, weight=1)

        self.card_nav = self._build_ops_card(ops, "NAVIGATION", 0, 0)
        self.card_scan = self._build_ops_card(ops, "SCANNING", 0, 1)
        self.card_system = self._build_ops_card(ops, "SYSTEM INTEL", 0, 2)
        self.card_value = self._build_ops_card(ops, "ECONOMY", 1, 0)
        self.card_session = self._build_ops_card(ops, "SESSION", 1, 1)
        self.card_ops = self._build_ops_card(ops, "OPERATIONS", 1, 2)

        self.details_toggle = tk.Button(center, text="[ DETAILS: VISIBLE ]", command=self.toggle_details, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 8, "bold"), relief=tk.FLAT, activebackground=COLOR_PANEL, activeforeground=COLOR_ACCENT)
        self.details_toggle.pack(anchor="w", pady=(10, 4))

        self.details_drawer = tk.Frame(center, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        self.details_drawer.pack(fill=tk.X, pady=(0, 8))
        self.details_drawer.grid_columnconfigure(0, weight=1)
        self.details_drawer.grid_columnconfigure(1, weight=1)

        vf_wrap = tk.Frame(self.details_drawer, bg=COLOR_PANEL)
        vf_wrap.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        tk.Label(vf_wrap, text="VALUABLE FINDS", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w")
        self.valuable_list = tk.Listbox(vf_wrap, bg=COLOR_PANEL, fg=COLOR_ORANGE, font=("Courier", 9), height=7, relief=tk.FLAT, highlightthickness=0, borderwidth=0)
        self.valuable_list.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        rd_wrap = tk.Frame(self.details_drawer, bg=COLOR_PANEL)
        rd_wrap.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        tk.Label(rd_wrap, text="RECENT DISCOVERIES", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w")
        self.recent_list = tk.Listbox(rd_wrap, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 9), height=7, relief=tk.FLAT, highlightthickness=0, borderwidth=0)
        self.recent_list.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        log_frame = tk.Frame(center, bg=COLOR_PANEL, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        log_frame.pack(fill=tk.BOTH, expand=True)
        log_toolbar = tk.Frame(log_frame, bg=COLOR_PANEL)
        log_toolbar.pack(fill=tk.X, padx=6, pady=(6, 2))
        tk.Label(log_toolbar, text="ACTIVITY LOG", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(side=tk.LEFT)
        for tag in ("ALL", "JUMP", "SCAN", "ALERT", "ERROR"):
            tk.Button(log_toolbar, text=f"[ {tag} ]", command=lambda t=tag: self.set_log_filter(t), bg=COLOR_PANEL, fg=COLOR_TEXT if tag == "ALL" else "#888", font=("Courier", 8, "bold"), relief=tk.FLAT, activebackground=COLOR_PANEL, activeforeground=COLOR_ACCENT).pack(side=tk.RIGHT, padx=2)
        self.log_box = scrolledtext.ScrolledText(log_frame, bg="#000", fg=COLOR_GREEN, font=("Courier", 10), borderwidth=0)
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_stat(self, parent, label, val):
        tk.Label(parent, text=label, font=("Courier", 8), fg="#666", bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(8, 0))
        l = tk.Label(parent, text=val, font=("Courier", 10, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL)
        l.pack(anchor="w", padx=10)
        return l

    def _build_ops_card(self, parent, title, row, col):
        card = tk.Frame(parent, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        card.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        tk.Label(card, text=title, font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(6, 0))
        line1 = tk.Label(card, text="-", font=("Courier", 9, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL, anchor="w")
        line1.pack(fill=tk.X, padx=10, pady=(4, 0))
        line2 = tk.Label(card, text="-", font=("Courier", 8), fg="#aaa", bg=COLOR_PANEL, anchor="w")
        line2.pack(fill=tk.X, padx=10, pady=(2, 0))
        line3 = tk.Label(card, text="-", font=("Courier", 8), fg="#888", bg=COLOR_PANEL, anchor="w")
        line3.pack(fill=tk.X, padx=10, pady=(2, 8))
        card.line1 = line1
        card.line2 = line2
        card.line3 = line3
        return card

    def set_log_filter(self, mode):
        self.log_filter = mode
        self._refresh_log_view()

    def _matches_log_filter(self, text):
        t = text.upper()
        if self.log_filter == "ALL":
            return True
        if self.log_filter == "JUMP":
            return "JUMP" in t or "LOCATION" in t
        if self.log_filter == "SCAN":
            return "SCAN" in t or "HONK" in t or "FSS" in t
        if self.log_filter == "ALERT":
            return "BIO" in t or "VALUABLE" in t or "SYSTEM SCAN COMPLETE" in t
        if self.log_filter == "ERROR":
            return "ERROR" in t or "FAILED" in t or "ERR" in t
        return True

    def _refresh_log_view(self):
        if not hasattr(self, "log_box"):
            return
        self.log_box.delete("1.0", tk.END)
        for line in self.log_entries[-500:]:
            if self._matches_log_filter(line):
                self.log_box.insert(tk.END, line + "\n")
        self.log_box.see(tk.END)

    def log(self, msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        self.log_entries.append(line)
        self.root.after(0, self._refresh_log_view)

    def toggle_details(self):
        self.details_visible = not self.details_visible
        if self.details_visible:
            self.details_drawer.pack(fill=tk.X, pady=(0, 8))
            self.details_toggle.config(text="[ DETAILS: VISIBLE ]")
        else:
            self.details_drawer.pack_forget()
            self.details_toggle.config(text="[ DETAILS: HIDDEN ]")

    def schedule_dashboard_refresh(self, full=False):
        if full:
            self.dashboard_refresh_full_pending = True
        if self.dashboard_refresh_job is None:
            self.dashboard_refresh_job = self.root.after(120, self._run_scheduled_dashboard_refresh)

    def _run_scheduled_dashboard_refresh(self):
        self.dashboard_refresh_job = None
        if self.dashboard_refresh_full_pending:
            self.dashboard_refresh_full_pending = False
            self.update_dashboard_ui()
        else:
            self.update_dashboard_panels()

    def _get_session_elapsed_text(self):
        elapsed = max(int(time.time() - self.session_start_ts), 0)
        hrs = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"

    def _tick_session_clock(self):
        if not self.is_running:
            return
        if hasattr(self, "summary_session"):
            self.summary_session.config(text=f"SESSION: {self._get_session_elapsed_text()}")
        self.root.after(1000, self._tick_session_clock)

    def _toggle_wp_scrollbar(self, show):
        if show and not self.wp_info_scroll_visible:
            self.wp_info_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            self.wp_info_scroll_visible = True
        elif not show and self.wp_info_scroll_visible:
            self.wp_info_scroll.pack_forget()
            self.wp_info_scroll_visible = False

    def _on_wp_info_wheel(self, event):
        try:
            self.wp_info_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        except Exception:
            return None

    def _set_wp_info_text(self, text):
        self.wp_info_text.config(state=tk.NORMAL)
        self.wp_info_text.delete("1.0", tk.END)
        self.wp_info_text.insert("1.0", text or "")
        self.wp_info_text.config(state=tk.DISABLED)
        self.wp_info_text.yview_moveto(0.0)

    def check_updates(self):
        try:
            url = "https://api.github.com/repos/insert3coins/VoidCompass-Release/releases/latest"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                tag = data.get("tag_name", "").lstrip("v")
                html_url = data.get("html_url", "")
                
                current_v = [int(x) for x in APP_VERSION.split('.')]
                remote_v = [int(x) for x in tag.split('.')]
                
                if remote_v > current_v:
                    self.root.after(0, lambda: self.show_update_btn(html_url, tag))
        except Exception:
            pass

    def show_update_btn(self, url, tag):
        self.log(f"✨ UPDATE AVAILABLE: v{tag}")
        btn = tk.Button(self.nav, text="[ UPDATE AVAILABLE ]", command=lambda: webbrowser.open(url), bg=COLOR_PANEL, fg=COLOR_GREEN, font=("Courier", 9, "bold"), relief=tk.FLAT, activebackground=COLOR_PANEL, activeforeground=COLOR_GREEN)
        btn.pack(side=tk.RIGHT, padx=5)

    def update_nav_label(self):
        txt = "NO ROUTE"
        if self.dest_name:
            txt = self.dest_name
        
        if not self.batch_mode:
            self.root.after(0, lambda: self.nav_stat.config(text=txt))

    def update_dashboard_panels(self):
        """Refresh dashboard cards/summary without waypoint recompute."""
        sys_text = self.current_sys.upper()
        if self.star_class: sys_text += f" [{self.star_class}]"
        
        self.sys_stat.config(text=sys_text)
        self.scan_stat.config(text=f"{self.scanned} / {self.total}")
        self.update_nav_label()

        route_text = "INACTIVE"
        route_total = 0
        route_visited = 0
        next_waypoint_name = "NONE"
        if self.waypoint_manager.waypoints:
            route_total = len(self.waypoint_manager.waypoints)
            route_visited = sum(1 for wp in self.waypoint_manager.waypoints if wp.get("visited", False))
            route_text = f"{route_visited}/{route_total}"
            for wp in self.waypoint_manager.waypoints:
                if not wp.get("visited", False):
                    next_waypoint_name = wp.get("name", "UNKNOWN")
                    break

        traffic_day = self.system_traffic.get("day", 0)
        traffic_week = self.system_traffic.get("week", 0)
        traffic_total = self.system_traffic.get("total", 0)
        coords_text = "-"
        if isinstance(self.current_coords, (list, tuple)) and len(self.current_coords) == 3:
            try:
                coords_text = f"{self.current_coords[0]:,.0f},{self.current_coords[1]:,.0f},{self.current_coords[2]:,.0f}"
            except Exception:
                coords_text = str(self.current_coords)

        self.summary_sys.config(text=f"SYS: {self.current_sys}")
        self.summary_route.config(text=f"ROUTE: {route_text}")
        self.summary_scan.config(text=f"SCAN: {self.scanned}/{self.total}")
        self.summary_traffic.config(text=f"TRAFFIC: {traffic_day}/{traffic_week}/{traffic_total}")
        self.summary_session.config(text=f"SESSION: {self._get_session_elapsed_text()}")

        self.card_nav.line1.config(text=f"Target: {self.dest_name or 'NO ROUTE'}")
        self.card_nav.line2.config(text=f"Current: {self.current_sys}")
        self.card_nav.line3.config(text=f"Route Progress: {route_text}")

        scan_pct = int((self.scanned / self.total) * 100) if self.total > 0 else 0
        self.card_scan.line1.config(text=f"Scanned: {self.scanned}/{self.total} ({scan_pct}%)")
        self.card_scan.line2.config(text=f"Bodies Tracked: {len(self.scanned_bodies)}")
        self.card_scan.line3.config(text=f"FSS Summary: {'ACTIVE' if self.fss_summary_active else 'IDLE'}")

        self.card_system.line1.config(text=f"Star: {self.star_class or 'UNKNOWN'}")
        self.card_system.line2.config(text=f"System: {self.current_sys}")
        self.card_system.line3.config(text=f"Coords: {coords_text} | FSS: {'YES' if self.in_fss else 'NO'}")

        total_value = 0
        for item in self.scan_items:
            reward = item.get("dss_reward") if item.get("dss_complete") else item.get("reward")
            if isinstance(reward, (int, float)):
                total_value += int(reward)
        self.card_value.line1.config(text=f"System Value Est: {self._format_credits(total_value)}")
        self.card_value.line2.config(text=f"Valuable Bodies: {len(self.valuable_bodies)}")
        self.card_value.line3.config(text=f"Bio Signals: {self.system_bio_signals}")

        self.card_session.line1.config(text=f"Jumps: {self.session_jump_count}")
        self.card_session.line2.config(text=f"Distance: {self.session_ly:,.1f} LY")
        avg_jump = (self.session_ly / self.session_jump_count) if self.session_jump_count else 0.0
        self.card_session.line3.config(text=f"Avg Jump: {avg_jump:,.1f} LY")

        hud_on = "ON" if self.hud else "OFF"
        disc_on = "ON" if (self.config.get("discord_enabled", True) and self.config.get("discord_webhook")) else "OFF"
        shots_on = "ON" if self.config.get("screenshots_enabled", False) else "OFF"
        self.integration_lbl.config(text=f"HUD: {hud_on} | DISCORD: {disc_on} | SHOTS: {shots_on}")

        alerts = []
        if self.system_undiscovered:
            alerts.append("UNDISCOVERED SYSTEM")
        if self.system_bio_signals > 0:
            alerts.append(f"BIO SIGNALS: {self.system_bio_signals}")
        if self.valuable_bodies:
            alerts.append(f"VALUABLE FINDS: {len(self.valuable_bodies)}")
        if self.fss_summary_active:
            alerts.append("FSS SUMMARY ACTIVE")
        self.alert_lbl.config(text=" | ".join(alerts) if alerts else "NONE")

        planner_open = "YES" if (self.route_plotter and self.route_plotter.win.winfo_exists()) else "NO"
        auto_copy = "ON" if self.config.get("auto_copy_waypoint", False) else "OFF"
        self.card_ops.line1.config(text=f"Waypoints: {route_total} | Pending: {max(route_total - route_visited, 0)}")
        self.card_ops.line2.config(text=f"Next WP: {next_waypoint_name}")
        self.card_ops.line3.config(text=f"Auto-Copy: {auto_copy} | Planner Open: {planner_open}")

        self.valuable_list.delete(0, tk.END)
        for item in self.valuable_bodies:
            display_text = item[2:] if item.startswith("- ") else item
            self.valuable_list.insert(tk.END, display_text)

        self.recent_list.delete(0, tk.END)
        for item in self.scan_items[:10]:
            nm = item.get("name", "Unknown")
            reward = item.get("dss_reward") if item.get("dss_complete") else item.get("reward")
            reward_txt = self._format_credits(reward, hide_units=True)
            self.recent_list.insert(tk.END, f"{nm}  [{reward_txt}]")

    def update_dashboard_ui(self):
        """Force update full dashboard, including waypoint panel."""
        self.update_dashboard_panels()

        self.update_waypoint_display()

    def update_waypoint_display(self):
        if not self.waypoint_manager.waypoints:
            self.target_waypoint = None
            self.wp_name_lbl.config(text="NO ACTIVE ROUTE")
            self.wp_dist_lbl.config(text="")
            self._set_wp_info_text("")
            self.update_hud()
            return

        # Auto-mark visited based on location
        idx = self.waypoint_manager.get_waypoint_index(self.current_sys)
        if idx != -1:
            changed = False
            for i in range(idx + 1):
                if not self.waypoint_manager.waypoints[i].get('visited', False):
                    self.waypoint_manager.waypoints[i]['visited'] = True
                    changed = True
            if changed:
                self.waypoint_manager.save()

        # Find next target (first unvisited)
        self.target_waypoint = None
        for wp in self.waypoint_manager.waypoints:
            if not wp.get('visited', False):
                self.target_waypoint = wp
                break
        
        if self.target_waypoint is None:
             self.wp_name_lbl.config(text="ROUTE COMPLETE")
             self.wp_dist_lbl.config(text="")
             self._set_wp_info_text("")
             self.update_hud()
             return
        
        if self.target_waypoint:
            name = self.target_waypoint['name']
            coords = self.target_waypoint['coords']
            note = self.target_waypoint.get('note')
            dist_str = ""
            if coords and self.current_coords:
                d = self.waypoint_manager.get_distance(self.current_coords, coords)
                dist_str = f"({d:,.1f} LY)"

            # Fetch EDSM Info if not cached
            if name not in self.waypoint_cache:
                self.waypoint_cache[name] = {"fetching": True}
                def cb(data):
                    if data:
                        self.waypoint_cache[name] = data
                    else:
                        self.waypoint_cache[name] = {"error": True}
                    self.root.after(0, self.update_waypoint_display)
                self.edsm.fetch_system_details(name, cb)
            
            # Format Info String
            info_text = "Fetching data..."
            cached = self.waypoint_cache.get(name)
            if cached and not cached.get("fetching"):
                if cached.get("error"):
                    info_text = "EDSM Data Unavailable"
                else:
                    p_star = cached.get("primaryStar", {}).get("type", "Unknown Star")
                    if "Main Sequence" in p_star: p_star = p_star.replace(" Main Sequence Star", "")
                    
                    info = cached.get("information", {})
                    gov = info.get("government", "None")
                    alg = info.get("allegiance", "Independent")
                    
                    info_text = f"⭐ {p_star}  🏛️ {gov}  🚩 {alg}"
            
            if note:
                if info_text == "Fetching data..." or info_text == "EDSM Data Unavailable":
                     info_text = f"📝 {note}"
                else:
                     info_text = f"📝 {note}  {info_text}"

            self.wp_name_lbl.config(text=name)
            self.wp_dist_lbl.config(text=dist_str)
            self._set_wp_info_text(info_text)
            self.update_hud()

