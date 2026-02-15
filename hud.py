import tkinter as tk
import json
from config import CONFIG_FILE, COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE, COLOR_GREEN

class TacticalHUD:
    def __init__(self, root, config):
        self.win = tk.Toplevel(root)
        self.config = config
        
        self.win.attributes("-topmost", True, "-transparentcolor", "#ff00ff", "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg="#ff00ff")
        
        self.width = 460
        self.base_height = 180
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

    def update(
        self,
        current_sys,
        dest_name,
        dist_ly,
        scanned,
        total,
        r_pos,
        organic_count,
        system_traffic,
        game_r_pos=None,
        route_destination=None,
        route_counts=None,
        hud_status="OK",
    ):
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
        status_label = str(hud_status or "OK").upper()
        status_color = {
            "OK": COLOR_GREEN,
            "ALERT": COLOR_ORANGE,
            "FAIL": "#ff4d4d",
        }.get(status_label, COLOR_TEXT)
        self.draw_text(440, 20, text=f"● {status_label}", fill=status_color, font=("Courier", 9, "bold"), anchor="e")
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

        t_day = system_traffic.get('day', 0)
        t_week = system_traffic.get('week', 0)
        t_total = system_traffic.get('total', 0)
        self.draw_text(20, 140, text=f"TRAFFIC: Today : {t_day}  This Week : {t_week}  Total : {t_total}", fill=COLOR_TEXT, font=("Courier", 9), anchor="w")
        route_y = h - 18

        route_pct = 0.0
        route_count_txt = "ROUTE: 0/0"
        if route_counts and route_counts[1] > 0:
            route_pct = max(0.0, min(1.0, route_counts[0] / route_counts[1]))
            route_count_txt = f"ROUTE: {route_counts[0]}/{route_counts[1]}"
        route_text = f"{route_count_txt} ({int(route_pct * 100)}%)"
        if r_pos and len(r_pos) > 2 and r_pos[2]:
            route_text = f"{route_text} [{r_pos[2]}]"

        if route_destination:
            dest_text = f"DEST: {route_destination.upper()}"
            if len(dest_text) > 34:
                dest_text = dest_text[:31] + "..."
            self.draw_text(20, route_y, text=dest_text, fill=COLOR_ORANGE, font=("Courier", 9, "bold"), anchor="w")
        self.draw_text(440, route_y, text=route_text, fill=COLOR_ACCENT, font=("Courier", 9, "bold"), anchor="e")
