import tkinter as tk
import json
from config import CONFIG_FILE, COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE

class TacticalHUD:
    def __init__(self, root, config):
        self.win = tk.Toplevel(root)
        self.config = config
        
        self.win.attributes("-topmost", True, "-transparentcolor", "#ff00ff", "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg="#ff00ff")
        
        self.width = 460
        self.base_height = 175
        self.fss_base_height = 210
        self.canvas = tk.Canvas(self.win, width=self.width, height=self.base_height, bg="#ff00ff", highlightthickness=0)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)
        self.canvas.bind("<ButtonRelease-1>", self.save_final_pos)

        x = self.config.get("hud_x", 100)
        y = self.config.get("hud_y", 100)
        self.win.geometry(f"+{x}+{y}")
        
        self.force_topmost()
        
        self.anim_step = 0
        self.anim_char = "⢄"
        self.animate_ui()

    def force_topmost(self):
        """Keeps the window on top of the game."""
        self.win.attributes("-topmost", True)
        self.win.lift()
        self.win.after(2000, self.force_topmost)

    def animate_ui(self):
        try:
            frames = ["⢄", "⢂", "⢁", " ", "⡈", "⡐", "⡠", "⡰", "⣠", "⣐", "⣈", "⣁", "⣂", "⣄", "⣆", "⣇", "⣧", "⣷", "⣾", "⣶", "⣼", "⣸", "⣙", "⣉", "⣁"]
            self.anim_char = frames[self.anim_step]
            self.anim_step = (self.anim_step + 1) % len(frames)
            self.canvas.itemconfigure("anim_title", text=self.anim_char)
            self.win.after(75, self.animate_ui)
        except Exception:
            pass

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.win.winfo_x() + deltax
        y = self.win.winfo_y() + deltay
        self.win.geometry(f"+{x}+{y}")

    def save_final_pos(self, event):
        self.config["hud_x"] = self.win.winfo_x()
        self.config["hud_y"] = self.win.winfo_y()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def draw_text(self, x, y, text, fill, font, anchor="w", tags=None):
        self.canvas.create_text(x+1, y+1, text=text, fill="black", font=font, anchor=anchor, tags=tags)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor, tags=tags)

    def update(self, current_sys, dest_name, dist_ly, scanned, total, r_pos, organic_count, system_traffic, game_r_pos=None, fss_summary=None, fss_summary_active=False):
        # Build HV lines for dynamic sizing when FSS summary is active
        hv_lines = []
        if fss_summary_active and fss_summary:
            hv_items = fss_summary.get("high_value") or []
            if hv_items:
                max_len = 68
                current = "HV: "
                for item in hv_items:
                    chunk = ("" if current == "HV: " else " | ") + item
                    if len(current) + len(chunk) > max_len:
                        hv_lines.append(current)
                        current = "HV: " + item
                    else:
                        current += chunk
                hv_lines.append(current)
            else:
                hv_lines = ["HV: -"]

        extra_lines = len(hv_lines) - 1 if hv_lines else 0
        if fss_summary_active and fss_summary:
            target_h = self.fss_base_height + (extra_lines * 12)
        else:
            target_h = self.base_height
        if self.canvas.winfo_height() != target_h:
            self.canvas.config(height=target_h)
            x = self.win.winfo_x()
            y = self.win.winfo_y()
            self.win.geometry(f"{self.width}x{target_h}+{x}+{y}")
        self.canvas.delete("all")
        
        h = target_h
        self.canvas.create_rectangle(5, 5, self.width - 5, h - 5, fill="#010101", outline=COLOR_ACCENT, width=2)
        self.canvas.create_line(5, 35, self.width - 5, 35, fill=COLOR_ACCENT, width=1)
        
        txt = getattr(self, "anim_char", "⢄")
        self.draw_text(32, 20, text=txt, fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="e", tags="anim_title")
        self.draw_text(38, 20, text="NAVIGATION HUD", fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="w")
        # Bio logs hidden for now (counting disabled)

        self.draw_text(20, 48, text=f"SYS: {current_sys.upper()}", fill=COLOR_TEXT, font=("Courier", 10, "bold"), anchor="w")
        
        dest_txt = f"NAV: {dest_name.upper() if dest_name else '---'}"
        if game_r_pos:
            dest_txt += f" [{game_r_pos[0]}/{game_r_pos[1]}]"
        self.draw_text(20, 66, text=dest_txt, fill=COLOR_ORANGE, font=("Courier", 10, "bold"), anchor="w")
        self.draw_text(440, 66, text=dist_ly, fill=COLOR_ORANGE, font=("Courier", 10, "bold"), anchor="e")
        
        self.canvas.create_line(20, 80, 440, 80, fill="#333", width=1)
        
        pct = (scanned / total) if total > 0 else 0
        self.canvas.create_rectangle(20, 88, 440, 102, outline="#333", width=1)
        if pct > 0:
            self.canvas.create_rectangle(20, 88, 20 + (420 * pct), 102, fill=COLOR_ACCENT, outline=COLOR_ACCENT)
        
        self.draw_text(20, 116, text=f"SCAN: {scanned}/{total} BODIES", fill=COLOR_TEXT, font=("Courier", 9), anchor="w")
        self.draw_text(440, 116, text=f"{int(pct*100)}%", fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="e")
        
        if fss_summary_active and fss_summary:
            fss_line = f"FSS: {fss_summary.get('count')} bodies | {fss_summary.get('total')}"
            if len(fss_line) > 68:
                fss_line = fss_line[:65] + "..."
            self.draw_text(20, 134, text=fss_line, fill=COLOR_ACCENT, font=("Courier", 8), anchor="w")

            y_line = 146
            for hv_line in hv_lines:
                if len(hv_line) > 68:
                    hv_line = hv_line[:65] + "..."
                self.draw_text(20, y_line, text=hv_line, fill=COLOR_ACCENT, font=("Courier", 8), anchor="w")
                y_line += 12

            landable_count = fss_summary.get("landable_count", 0)
            land_line = f"LANDABLE: {landable_count}"
            self.draw_text(20, y_line, text=land_line, fill=COLOR_ACCENT, font=("Courier", 8), anchor="w")
            y_line += 12
            t_day = system_traffic.get('day', 0)
            t_week = system_traffic.get('week', 0)
            t_total = system_traffic.get('total', 0)
            self.draw_text(20, y_line, text=f"TRAFFIC: Today : {t_day}  This Week : {t_week}  Total : {t_total}", fill=COLOR_TEXT, font=("Courier", 8), anchor="w")
            route_y = y_line + 14
        else:
            t_day = system_traffic.get('day', 0)
            t_week = system_traffic.get('week', 0)
            t_total = system_traffic.get('total', 0)
            self.draw_text(20, 134, text=f"TRAFFIC: Today : {t_day}  This Week : {t_week}  Total : {t_total}", fill=COLOR_TEXT, font=("Courier", 9), anchor="w")
            route_y = 154

        route_text = "ROUTE: INACTIVE"
        if r_pos:
            if len(r_pos) > 2:
                route_text = f"ROUTE: {r_pos[0]} / {r_pos[1]} ({r_pos[2]})"
            else:
                route_text = f"ROUTE: {r_pos[0]} / {r_pos[1]}"
        self.draw_text(440, route_y, text=route_text, fill=COLOR_ACCENT, font=("Courier", 9, "bold"), anchor="e")
