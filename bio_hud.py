import tkinter as tk
import json
from config import CONFIG_FILE, COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE


class BioHUD:
    def __init__(self, root, config):
        self.win = tk.Toplevel(root)
        self.config = config

        self.win.attributes("-topmost", True, "-transparentcolor", "#ff00ff", "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg="#ff00ff")

        self.width = 520
        self.height = 176
        self.canvas = tk.Canvas(self.win, width=self.width, height=self.height, bg="#ff00ff", highlightthickness=0)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)
        self.canvas.bind("<ButtonRelease-1>", self.save_final_pos)

        screen_width = root.winfo_screenwidth()
        default_x = (screen_width // 2) - (self.width // 2)
        default_y = 30

        x = self.config.get("bio_hud_x", default_x)
        y = self.config.get("bio_hud_y", default_y)
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
        self.config["bio_hud_x"] = self.win.winfo_x()
        self.config["bio_hud_y"] = self.win.winfo_y()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def draw_text(self, x, y, text, fill, font, anchor="w"):
        self.canvas.create_text(x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    def update(self, system_name, body_name, genus, species, sample_idx, max_samples, scan_type, is_new_entry, is_new_sample, biome=None, planet_class=None, sample_distance=None):
        self.canvas.delete("all")

        w = self.width
        h = self.height

        self.canvas.create_rectangle(5, 5, w - 5, h - 5, fill="#010101", outline=COLOR_ACCENT, width=2)
        self.canvas.create_line(5, 34, w - 5, 34, fill=COLOR_ACCENT, width=1)

        self.draw_text(12, 20, text="EXOBIO SCAN", fill=COLOR_ACCENT, font=("Courier", 10, "bold"), anchor="w")
        if scan_type:
            self.draw_text(w - 12, 20, text=scan_type.upper(), fill=COLOR_ORANGE, font=("Courier", 9, "bold"), anchor="e")

        species_txt = species or "---"
        genus_txt = genus or "---"
        self.draw_text(12, 50, text=f"SPECIES: {species_txt}", fill=COLOR_TEXT, font=("Courier", 10, "bold"), anchor="w")
        self.draw_text(12, 66, text=f"GENUS:   {genus_txt}", fill=COLOR_TEXT, font=("Courier", 9), anchor="w")

        biome_txt = biome or "---"
        planet_txt = planet_class or "---"
        dist_txt = "---"
        if sample_distance is not None:
            try:
                dist_txt = f"{float(sample_distance):.0f} m"
            except Exception:
                dist_txt = str(sample_distance)
        self.draw_text(12, 82, text=f"BIOME:   {biome_txt}", fill=COLOR_TEXT, font=("Courier", 9), anchor="w")
        self.draw_text(12, 96, text=f"PLANET:  {planet_txt}", fill=COLOR_TEXT, font=("Courier", 9), anchor="w")
        self.draw_text(w - 12, 96, text=f"DIST: {dist_txt}", fill=COLOR_TEXT, font=("Courier", 9), anchor="e")

        status_parts = []
        if is_new_entry:
            status_parts.append("NEW ENTRY")
        if is_new_sample:
            status_parts.append("NEW SAMPLE")
        status_txt = " | ".join(status_parts) if status_parts else "UPDATE"
        sample_txt = f"{sample_idx}/{max_samples}" if sample_idx else f"0/{max_samples}"
        self.draw_text(12, 116, text=f"SAMPLE: {sample_txt}", fill=COLOR_ORANGE, font=("Courier", 9, "bold"), anchor="w")
        self.draw_text(w - 12, 116, text=status_txt, fill=COLOR_ACCENT, font=("Courier", 9, "bold"), anchor="e")

        # Progress bar
        bar_x1 = 12
        bar_x2 = w - 12
        bar_y1 = 128
        bar_y2 = 140
        self.canvas.create_rectangle(bar_x1, bar_y1, bar_x2, bar_y2, outline="#333", width=1)
        if max_samples and sample_idx:
            pct = min(max(sample_idx / max_samples, 0), 1)
            self.canvas.create_rectangle(bar_x1, bar_y1, bar_x1 + ((bar_x2 - bar_x1) * pct), bar_y2, fill=COLOR_ACCENT, outline=COLOR_ACCENT)

        sys_txt = system_name.upper() if system_name else "---"
        body_txt = body_name.upper() if body_name else "---"
        self.draw_text(12, 160, text=f"SYS: {sys_txt}", fill=COLOR_TEXT, font=("Courier", 8), anchor="w")
        self.draw_text(w - 12, 160, text=f"BODY: {body_txt}", fill=COLOR_TEXT, font=("Courier", 8), anchor="e")
