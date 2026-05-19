import json
import tkinter as tk

from config import CONFIG_FILE, COLOR_ACCENT, COLOR_GREEN, COLOR_ORANGE, COLOR_TEXT


def _clean_name(value):
    text = str(value or "").strip().strip(";").lstrip("$")
    if not text:
        return ""
    text = text.replace("_", " ")
    if text.lower().startswith("material content"):
        text = text[len("material content"):].strip(": ")
    aliases = {
        "lowtemperaturediamond": "Low Temperature Diamonds",
        "low temperature diamond": "Low Temperature Diamonds",
        "low temperature diamonds": "Low Temperature Diamonds",
        "low temp diamonds": "Low Temperature Diamonds",
        "low temp. diamonds": "Low Temperature Diamonds",
        "opal": "Void Opals",
        "void opal": "Void Opals",
        "void opals": "Void Opals",
    }
    return aliases.get(text.lower(), text.title())


class ProspectorOverlay:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.width = 430
        self.height = 260
        self.hide_job = None
        self._save_job = None

        self.win = tk.Toplevel(root)
        self.win.attributes("-topmost", True, "-transparentcolor", "#ff00ff", "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg="#ff00ff")
        self.win.withdraw()

        self.canvas = tk.Canvas(self.win, width=self.width, height=self.height, bg="#ff00ff", highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)
        self.canvas.bind("<ButtonRelease-1>", self.save_final_pos)

        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        default_x = screen_width - self.width - 40
        default_y = max(40, int(screen_height * 0.18))
        x = self._safe_int(self.config.get("prospector_overlay_x"), default_x)
        y = self._safe_int(self.config.get("prospector_overlay_y"), default_y)
        self._desired_pos = (x, y)
        self.win.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.win.after(0, self._apply_initial_position)
        self.win.after(250, self._apply_initial_position)
        self.force_topmost()

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return int(default)

    def _apply_initial_position(self):
        try:
            x, y = self._desired_pos
            self.win.geometry(f"{self.width}x{self.height}+{x}+{y}")
        except Exception:
            pass

    def force_topmost(self):
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        refresh_ms = int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000)
        if refresh_ms < 2000:
            refresh_ms = 2000
        try:
            self.win.after(refresh_ms, self.force_topmost)
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
        self.config["prospector_overlay_x"] = x
        self.config["prospector_overlay_y"] = y
        self._schedule_config_save()

    def save_final_pos(self, event=None):
        self.config["prospector_overlay_x"] = self.win.winfo_x()
        self.config["prospector_overlay_y"] = self.win.winfo_y()
        self._write_config()

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

    def _write_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)

    def hide(self):
        if self.hide_job:
            try:
                self.win.after_cancel(self.hide_job)
            except Exception:
                pass
            self.hide_job = None
        try:
            self.win.withdraw()
        except Exception:
            pass

    def destroy(self):
        try:
            self.hide()
            self.win.destroy()
        except Exception:
            pass

    def draw_text(self, x, y, text, fill, font, anchor="w"):
        self.canvas.create_text(x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    def show_prospector(self, raw_event):
        materials = []
        for item in raw_event.get("Materials", []) or []:
            name = _clean_name(item.get("Name_Localised") or item.get("Name"))
            if not name:
                continue
            try:
                pct = float(item.get("Proportion") or item.get("Percent") or 0)
            except Exception:
                pct = 0.0
            if pct <= 1 and item.get("Proportion") is not None:
                pct *= 100.0
            materials.append((name, pct))

        materials.sort(key=lambda pair: pair[1], reverse=True)
        core = _clean_name(raw_event.get("MotherlodeMaterial_Localised") or raw_event.get("MotherlodeMaterial"))
        content = raw_event.get("Content_Localised") or raw_event.get("Content") or ""
        content = str(content).replace("Material Content:", "").strip()
        if content.startswith("$"):
            content = _clean_name(content)
        try:
            remaining = float(raw_event.get("Remaining"))
        except Exception:
            remaining = 100.0

        row_count = min(6, len(materials))
        target_h = 152 + (row_count * 24) + (26 if core else 0) + (22 if content else 0)
        target_h = max(210, min(360, target_h))
        if target_h != self.height:
            self.height = target_h
            self.canvas.config(height=self.height)
            self.win.geometry(f"{self.width}x{self.height}+{self.win.winfo_x()}+{self.win.winfo_y()}")

        self.canvas.delete("all")
        w = self.width
        h = self.height
        self.canvas.create_rectangle(5, 5, w - 5, h - 5, fill="#010101", outline=COLOR_ACCENT, width=2)
        self.canvas.create_line(5, 42, w - 5, 42, fill=COLOR_ACCENT, width=1)
        self.draw_text(16, 21, "LIMPET (PROSPECTOR)", COLOR_ACCENT, ("Courier", 11, "bold"))
        self.draw_text(w - 16, 21, "MINING", COLOR_ORANGE, ("Courier", 9, "bold"), anchor="e")

        y = 58
        if core:
            self.draw_text(18, y, "CORE DETECTED:", COLOR_ORANGE, ("Courier", 9, "bold"))
            self.draw_text(150, y, core.upper(), COLOR_ACCENT, ("Courier", 9, "bold"))
            y += 26

        remaining_text = "DEPLETED" if remaining <= 0.0 else f"{remaining:.2f}%"
        remaining_color = COLOR_ORANGE if remaining <= 0.0 else COLOR_GREEN
        self.draw_text(18, y, "MINERALS REMAINING:", COLOR_TEXT, ("Courier", 9, "bold"))
        self.draw_text(w - 18, y, remaining_text, remaining_color, ("Courier", 10, "bold"), anchor="e")
        y += 20
        bar_x = 18
        bar_y = y
        bar_w = w - 36
        pct = max(0.0, min(1.0, remaining / 100.0))
        self.canvas.create_rectangle(bar_x, bar_y, bar_x + bar_w, bar_y + 8, outline="#26313a", fill="#11161c")
        self.canvas.create_rectangle(bar_x, bar_y, bar_x + int(bar_w * pct), bar_y + 8, outline="", fill=remaining_color)
        y += 24

        if materials:
            self.draw_text(18, y, "MATERIAL CONTENT", COLOR_ORANGE, ("Courier", 8, "bold"))
            y += 18
            for name, pct_value in materials[:6]:
                color = COLOR_ACCENT if pct_value >= 20.0 else COLOR_TEXT
                self.draw_text(28, y, name.upper(), color, ("Courier", 9, "bold"))
                self.draw_text(w - 24, y, f"{pct_value:.2f}%", color, ("Courier", 9, "bold"), anchor="e")
                y += 22
        else:
            self.draw_text(18, y, "NO MATERIAL DATA", "#555555", ("Courier", 9, "bold"))
            y += 22

        if content:
            y += 4
            self.canvas.create_line(18, y, w - 18, y, fill="#17232c", width=1)
            y += 16
            self.draw_text(18, y, f"CONTENT: {content.upper()}", COLOR_TEXT, ("Courier", 8, "bold"))

        try:
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
        except Exception:
            pass

        if self.hide_job:
            try:
                self.win.after_cancel(self.hide_job)
            except Exception:
                pass
        duration = int(self.config.get("prospector_overlay_duration_ms", 12000) or 12000)
        if duration > 0:
            self.hide_job = self.win.after(duration, self.hide)
