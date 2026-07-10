import tkinter as tk
from config import COLOR_ACCENT, COLOR_GREEN, COLOR_TEXT, COLOR_ORANGE, save_config
import overlay_chrome

class CargoHUD:
    def __init__(self, root, config):
        self.win = tk.Toplevel(root)
        self.config = config
        
        self.win.attributes("-topmost", True, "-transparentcolor", "#ff00ff", "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg="#ff00ff")
        
        self.canvas = tk.Canvas(self.win, width=300, height=400, bg="#ff00ff", highlightthickness=0)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)
        self.canvas.bind("<ButtonRelease-1>", self.save_final_pos)

        # Default to right middle side
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        default_x = screen_width - 320
        default_y = (screen_height // 2) - 200
        
        x = self._safe_int(self.config.get("cargo_hud_x"), default_x)
        y = self._safe_int(self.config.get("cargo_hud_y"), default_y)
        self._desired_pos = (x, y)
        self.win.geometry(f"300x400+{x}+{y}")
        self.win.after(0, self._apply_initial_position)
        self.win.after(250, self._apply_initial_position)
        self.win.after(700, self._apply_initial_position)
        
        self.force_topmost()
        self._save_job = None
        self.update([], 0)

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return int(default)

    def _apply_initial_position(self):
        try:
            x, y = self._desired_pos
            self.win.geometry(f"300x400+{x}+{y}")
        except Exception:
            pass

    def force_topmost(self):
        """Keeps the window on top of the game."""
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        refresh_ms = int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000)
        if refresh_ms < 2000:
            refresh_ms = 2000
        self.win.after(refresh_ms, self.force_topmost)

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.win.winfo_x() + deltax
        y = self.win.winfo_y() + deltay
        self.win.geometry(f"+{x}+{y}")
        # Persist while dragging so release outside the canvas still keeps the new position.
        self.config["cargo_hud_x"] = x
        self.config["cargo_hud_y"] = y
        self._schedule_config_save()

    def save_final_pos(self, event):
        self.config["cargo_hud_x"] = self.win.winfo_x()
        self.config["cargo_hud_y"] = self.win.winfo_y()
        self._write_config()

    def _write_config(self):
        save_config(self.config)

    def _schedule_config_save(self):
        if self._save_job:
            try:
                self.win.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.win.after(250, self._flush_scheduled_save)

    def _flush_scheduled_save(self):
        self._save_job = None
        try:
            self._write_config()
        except Exception:
            pass

    def draw_text(self, x, y, text, fill, font, anchor="w"):
        self.canvas.create_text(x+1, y+1, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    def update(self, inventory, capacity=0):
        inventory = list(inventory or [])
        self.canvas.delete("all")
        
        w = 300
        h = 400
        
        # Chrome
        overlay_chrome.draw_chrome(self.canvas, w, h)
        # Header separator
        self.canvas.create_line(16, 45, w-16, 45, fill="#1a2530", width=1)

        # Title + total (line 1)
        self.draw_text(16, 20, text="CARGO MANIFEST", fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="w")
        
        # Total Count
        total = sum(item.get("Count", 0) for item in inventory)
        bars = [
            "▱▱▱▱▱▱▱▱▱▱",
            "▰▱▱▱▱▱▱▱▱▱",
            "▰▰▱▱▱▱▱▱▱▱",
            "▰▰▰▱▱▱▱▱▱▱",
            "▰▰▰▰▱▱▱▱▱▱",
            "▰▰▰▰▰▱▱▱▱▱",
            "▰▰▰▰▰▰▱▱▱▱",
            "▰▰▰▰▰▰▰▱▱▱",
            "▰▰▰▰▰▰▰▰▱▱",
            "▰▰▰▰▰▰▰▰▰▱",
            "▰▰▰▰▰▰▰▰▰▰",
        ]
        
        if capacity > 0:
            pct = total / capacity
            if pct > 1.0: pct = 1.0
            idx = int(pct * 10)
            idx = max(0, min(idx, 10))
            self.draw_text(w-16, 35, text=bars[idx], fill=COLOR_ORANGE, font=("Segoe UI Symbol", 10), anchor="e")
            total_str = f"TOTAL: {total}/{capacity}"
        else:
            total_str = f"TOTAL: {total}"
            self.draw_text(w-16, 35, text=bars[0], fill="#777", font=("Segoe UI Symbol", 10), anchor="e")

        self.draw_text(w-16, 20, text=total_str, fill=COLOR_ORANGE, font=("Courier", 10, "bold"), anchor="e")
        
        y_pos = 60
        if not inventory:
            self.draw_text(w//2, h//2, text="[ HOLD EMPTY ]", fill="#555", font=("Courier", 10), anchor="center")
        else:
            # Sort alphabetically
            inventory.sort(key=lambda x: x.get("Name_Localised", x.get("Name", "Unknown")))
            
            for item in inventory:
                if y_pos > h - 25:
                    self.draw_text(w//2, y_pos, text="... overflow ...", fill="#555", font=("Courier", 8), anchor="center")
                    break
                
                name = item.get("Name_Localised", item.get("Name", "Unknown"))
                count = item.get("Count", 0)
                
                # Truncate name
                display_name = (name[:22] + '..') if len(name) > 22 else name
                
                self.draw_text(16, y_pos, text=display_name, fill=COLOR_TEXT, font=("Courier", 9), anchor="w")
                self.draw_text(w-16, y_pos, text=str(count), fill=COLOR_GREEN, font=("Courier", 9, "bold"), anchor="e")
                
                y_pos += 20
