import tkinter as tk
import json
from config import CONFIG_FILE, COLOR_ACCENT, COLOR_GREEN, COLOR_TEXT, COLOR_ORANGE

class TacticalHUD:
    def __init__(self, root, config):
        self.win = tk.Toplevel(root)
        self.config = config
        
        self.win.attributes("-topmost", True, "-transparentcolor", "black", "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg="black")
        
        self.canvas = tk.Canvas(self.win, width=460, height=215, bg="black", highlightthickness=0)
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

    def update(self, current_sys, dest_name, dist_ly, scanned, total, edsm_status, r_pos, organic_count, system_traffic):
        self.canvas.delete("all")
        
        self.canvas.create_rectangle(5, 5, 455, 210, fill="#010101", outline=COLOR_ACCENT, width=2)
        self.canvas.create_line(5, 35, 455, 35, fill=COLOR_ACCENT, width=1)
        
        txt = getattr(self, "anim_char", "⢄")
        self.canvas.create_text(32, 20, text=txt, fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="e", tags="anim_title")
        self.canvas.create_text(38, 20, text="SURVEY ANALYSIS", fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="w")
        if organic_count > 0:
            self.canvas.create_text(440, 20, text=f"BIO-LOGS: {organic_count}", fill=COLOR_GREEN, font=("Courier", 9, "bold"), anchor="e")

        self.canvas.create_text(20, 55, text=f"SYS: {current_sys.upper()}", fill=COLOR_TEXT, font=("Courier", 12, "bold"), anchor="w")
        
        route_text = "ROUTE: NO ACTIVE NAV-ARRAY"
        if r_pos:
            route_text = f"ROUTE: JUMP {r_pos[0]} OF {r_pos[1]}"
        self.canvas.create_text(20, 78, text=route_text, fill=COLOR_GREEN, font=("Courier", 10, "bold"), anchor="w")
        
        dest_txt = f"NAV: {dest_name.upper() if dest_name else '---'}"
        self.canvas.create_text(20, 98, text=dest_txt, fill=COLOR_ORANGE, font=("Courier", 10), anchor="w")
        self.canvas.create_text(440, 98, text=dist_ly, fill=COLOR_ORANGE, font=("Courier", 10), anchor="e")
        
        pct = (scanned / total) if total > 0 else 0
        self.canvas.create_rectangle(20, 120, 440, 135, outline="#333", width=1)
        if pct > 0:
            self.canvas.create_rectangle(20, 120, 20 + (420 * pct), 135, fill=COLOR_ACCENT, outline=COLOR_ACCENT)
        
        self.canvas.create_text(20, 150, text=f"SCAN: {scanned}/{total} BODIES", fill=COLOR_TEXT, font=("Courier", 9), anchor="w")
        self.canvas.create_text(440, 150, text=f"{int(pct*100)}%", fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="e")
        
        t_day = system_traffic.get('day', 0)
        t_week = system_traffic.get('week', 0)
        t_total = system_traffic.get('total', 0)
        self.canvas.create_text(20, 170, text=f"TRAFFIC: Today : {t_day}  This Week : {t_week}  Total : {t_total}", fill=COLOR_TEXT, font=("Courier", 9), anchor="w")

        status_color = COLOR_GREEN if edsm_status == "OK" else "red"
        self.canvas.create_text(20, 190, text=f"EDSM: {edsm_status}", fill=status_color, font=("Courier", 8, "bold"), anchor="w")