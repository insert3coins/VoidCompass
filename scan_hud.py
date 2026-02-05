import tkinter as tk
import json
from config import CONFIG_FILE, COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE


class ScanHUD:
    def __init__(self, root, config):
        self.win = tk.Toplevel(root)
        self.config = config

        self.win.attributes("-topmost", True, "-transparentcolor", "#ff00ff", "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg="#ff00ff")

        self.width = 360
        self.height = 680
        self.canvas = tk.Canvas(self.win, width=self.width, height=self.height, bg="#ff00ff", highlightthickness=0)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)
        self.canvas.bind("<ButtonRelease-1>", self.save_final_pos)

        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        default_x = screen_width - (self.width + 30)
        default_y = (screen_height // 2) - (self.height // 2)

        x = self.config.get("scan_hud_x", default_x)
        y = self.config.get("scan_hud_y", default_y)
        self.win.geometry(f"+{x}+{y}")

        self.force_topmost()

    def force_topmost(self):
        self.win.attributes("-topmost", True)
        self.win.lift()
        self.win.after(2000, self.force_topmost)

    def show(self):
        try:
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
        except Exception:
            pass

    def hide(self):
        try:
            self.win.withdraw()
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
        self.config["scan_hud_x"] = self.win.winfo_x()
        self.config["scan_hud_y"] = self.win.winfo_y()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def draw_text(self, x, y, text, fill, font, anchor="w"):
        self.canvas.create_text(x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    def update(self, system_name, system_undiscovered, fss_all_bodies, scanned_count, total_value, items):
        self.canvas.delete("all")

        w = self.width
        h = self.height

        self.canvas.create_rectangle(5, 5, w - 5, h - 5, fill="#010101", outline=COLOR_ACCENT, width=2)

        # Header box
        header_top = 8
        header_bottom = 46
        self.canvas.create_rectangle(8, header_top, w - 8, header_bottom, outline=COLOR_ACCENT, width=1)

        header_name = f"⚑ {system_name}" if system_undiscovered else system_name
        if fss_all_bodies:
            header_name += " ✔️"
        self.draw_text(14, 18, text=header_name, fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="w")

        total_txt = self._format_credits(total_value, hide_units=False)
        if fss_all_bodies:
            summary = f"Scanned all {scanned_count} bodies: {total_txt}"
        else:
            summary = f"Scanned {scanned_count} bodies: {total_txt}"
        self.draw_text(14, 34, text=summary, fill=COLOR_ORANGE, font=("Courier", 9), anchor="w")

        y = 54
        row_h = 34
        max_rows = (h - 120) // row_h

        if not items:
            self.draw_text(w // 2, h // 2, text="(scan to populate)", fill="#555", font=("Courier", 9), anchor="center")
            return

        icon_font = ("Segoe UI Symbol", 9)

        for item in items[:max_rows]:
            line1 = f"{item['name']} - {item['class']}"

            reward = item.get("reward")
            dss_reward = item.get("dss_reward")
            dss_complete = item.get("dss_complete")
            reward_txt = self._format_credits(reward, hide_units=True)

            line2_parts = []
            if dss_complete:
                line2_parts.append(f"✔️ {reward_txt}")
            else:
                line2_parts.append(reward_txt)
                if not item.get("is_star") and dss_reward:
                    line2_parts.append(self._format_credits(dss_reward, hide_units=True))

            bio_count = item.get("bio_count", 0)
            if bio_count:
                line2_parts.append(f"{bio_count} Genus")

            line2 = " | ".join([p for p in line2_parts if p])

            color = item.get("color", COLOR_TEXT)
            self.draw_text(12, y, text=line1, fill=color, font=("Courier", 9, "bold"), anchor="w")
            icon_text = " ".join(item.get("icons", []))
            if icon_text:
                self.draw_text(w - 12, y, text=icon_text, fill=color, font=icon_font, anchor="e")
            if line2:
                self.draw_text(24, y + 14, text=line2, fill=COLOR_TEXT, font=("Courier", 8), anchor="w")

            self.canvas.create_line(12, y + row_h - 4, w - 12, y + row_h - 4, fill="#101010", width=1)
            y += row_h

        self.draw_text(12, h - 32, text="Scan value | DSS value", fill=COLOR_ORANGE, font=("Courier", 8), anchor="w")
        self.draw_text(12, h - 18, text="🌎 Terraformable   🚀 Landable   ⚑ Undiscovered   🦶 First Footfall", fill=COLOR_ORANGE, font=("Courier", 8), anchor="w")

    def _format_credits(self, credits, hide_units=False):
        if credits is None:
            return ""
        try:
            credits = int(credits)
        except Exception:
            return ""

        if credits < 1_000:
            txt = f"{credits:,}"
        elif credits < 100_000:
            txt = f"{credits / 1_000:.2f} K"
        elif credits < 1_000_000:
            txt = f"{credits / 1_000:.0f} K"
        elif credits < 100_000_000:
            txt = f"{credits / 1_000_000:.2f} M"
        elif credits < 1_000_000_000:
            txt = f"{credits / 1_000_000:.0f} M"
        else:
            txt = f"{credits / 1_000_000_000:.3f} B"

        if not hide_units:
            txt += " CR"
        return txt
