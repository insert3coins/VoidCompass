import re
import tkinter as tk
import tkinter.font as tkfont

from config import COLOR_ACCENT, COLOR_BG, COLOR_ORANGE, COLOR_TEXT


class BioEstimatePopup:
    def __init__(self, root, config, save_config_cb, format_credits_cb):
        self.root = root
        self.config = config
        self.save_config_cb = save_config_cb
        self.format_credits_cb = format_credits_cb
        self.enabled = bool(self.config.get("bio_estimate_popup_enabled", True))
        self.win = None
        self.header_lbl = None
        self.rows_canvas = None
        self.footer_lbl = None
        self.ff_lbl = None
        self._last_key = None
        self._manually_hidden = False
        self._drag_origin = None
        self._save_job = None
        self._palette = self._build_palette()

    @staticmethod
    def _hex_to_rgb(color):
        color = str(color or "").lstrip("#")
        if len(color) != 6:
            return (255, 255, 255)
        try:
            return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
        except Exception:
            return (255, 255, 255)

    @staticmethod
    def _rgb_to_hex(rgb):
        r, g, b = rgb
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        return f"#{r:02x}{g:02x}{b:02x}"

    @classmethod
    def _mix(cls, c1, c2, ratio):
        r1, g1, b1 = cls._hex_to_rgb(c1)
        r2, g2, b2 = cls._hex_to_rgb(c2)
        rr = max(0.0, min(1.0, float(ratio)))
        return cls._rgb_to_hex((r1 + (r2 - r1) * rr, g1 + (g2 - g1) * rr, b1 + (b2 - b1) * rr))

    @classmethod
    def _darken(cls, color, amount=0.25):
        return cls._mix(color, "#000000", amount)

    @classmethod
    def _lighten(cls, color, amount=0.25):
        return cls._mix(color, "#ffffff", amount)

    def _build_palette(self):
        return {
            "panel_bg": COLOR_BG,
            "header": COLOR_ACCENT,
            "stripe_bright": COLOR_ACCENT,
            "stripe_dim": self._darken(COLOR_ACCENT, 0.62),
            "text_main": COLOR_TEXT,
            "text_dim": self._darken(COLOR_TEXT, 0.42),
            "accent": COLOR_ACCENT,
            "accent_dim": self._darken(COLOR_ACCENT, 0.45),
            "orange_dim": self._darken(COLOR_ORANGE, 0.35),
            "orange_deep": self._darken(COLOR_ORANGE, 0.58),
            "hatch": self._lighten(COLOR_BG, 0.35),
            "unknown": self._mix(COLOR_TEXT, COLOR_BG, 0.72),
        }

    def _ensure(self):
        if self.win and self.win.winfo_exists():
            return

        self.win = tk.Toplevel(self.root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=self._palette["panel_bg"])
        self.win.geometry(self.config.get("bio_estimate_popup_geometry", "286x304+1450+180"))
        self.win.minsize(250, 180)

        outer = tk.Frame(self.win, bg=self._palette["panel_bg"], highlightbackground=self._palette["header"], highlightthickness=1)
        outer.pack(fill=tk.BOTH, expand=True)

        self.header_lbl = tk.Label(
            outer,
            text="Bio signals: 0",
            bg=self._palette["panel_bg"],
            fg=self._palette["header"],
            font=("Consolas", 12),
            anchor="w",
        )
        self.header_lbl.pack(fill=tk.X, padx=3, pady=(2, 0))

        self._add_orange_stripe(outer)

        self.rows_canvas = tk.Canvas(
            outer,
            bg=self._palette["panel_bg"],
            highlightthickness=0,
            bd=0,
            relief=tk.FLAT,
            height=220,
        )
        self.rows_canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=(1, 1))

        self._add_orange_stripe(outer)

        self.footer_lbl = tk.Label(
            outer,
            text="Rewards: 0",
            bg=self._palette["panel_bg"],
            fg=self._palette["header"],
            font=("Consolas", 12),
            anchor="w",
        )
        self.footer_lbl.pack(fill=tk.X, padx=3, pady=(0, 0))

        self.ff_lbl = tk.Label(
            outer,
            text="",
            bg=self._palette["panel_bg"],
            fg=self._palette["accent"],
            font=("Consolas", 10),
            anchor="e",
        )
        self.ff_lbl.pack(fill=tk.X, padx=3, pady=(0, 2))

        for w in (self.win, outer, self.header_lbl, self.rows_canvas, self.footer_lbl, self.ff_lbl):
            w.bind("<ButtonPress-1>", self._on_drag_press)
            w.bind("<B1-Motion>", self._on_drag_motion)
            w.bind("<ButtonRelease-1>", self._on_drag_release)

        self.win.bind("<Configure>", self._on_configure)

    def _add_orange_stripe(self, parent):
        stripe = tk.Canvas(parent, bg=self._palette["panel_bg"], height=3, highlightthickness=0, bd=0)
        stripe.pack(fill=tk.X, padx=2, pady=(1, 1))
        stripe.create_line(0, 0, 1000, 0, fill=self._palette["stripe_dim"])
        stripe.create_line(0, 1, 1000, 1, fill=self._palette["stripe_bright"])
        stripe.create_line(0, 2, 1000, 2, fill=self._palette["stripe_dim"])

    def _money_short(self, value):
        try:
            v = float(value or 0)
        except Exception:
            v = 0.0
        av = abs(v)
        if av >= 1_000_000_000:
            return f"{v / 1_000_000_000:.2f} B"
        if av >= 1_000_000:
            txt = f"{v / 1_000_000:.2f}".rstrip("0").rstrip(".")
            return f"{txt} M"
        if av >= 1_000:
            txt = f"{v / 1_000:.2f}".rstrip("0").rstrip(".")
            return f"{txt} K"
        return f"{int(v)}"

    def _fmt_range(self, min_v, max_v):
        min_v = int(min_v or 0)
        max_v = int(max_v or 0)
        if min_v == max_v:
            return self._money_short(min_v)
        return f"{self._money_short(min_v)} ~ {self._money_short(max_v)}"

    def _short_body(self, system_name, body_name):
        body = str(body_name or "")
        sys_name = str(system_name or "")
        if sys_name and body.startswith(sys_name):
            short = body[len(sys_name):].strip()
            return short or body
        return body

    def _format_body_label(self, short_body):
        s = str(short_body or "").strip()
        # Format simple numeric+letter body IDs like "2a" / "2 a" as "2(a)".
        m = re.match(r"^(\d+)\s*([A-Za-z])$", s)
        if m:
            return f"{m.group(1)}({m.group(2).lower()})"
        return s

    def _natural_key(self, text):
        return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(text or ""))]

    def _bar_colors(self, highlight=False, complete=False):
        if complete:
            return {
                "edge": self._palette["orange_deep"],
                "min": self._palette["orange_dim"],
                "max": self._palette["orange_deep"],
                "text": self._palette["orange_dim"],
                "value": self._palette["text_dim"],
                "hatch": self._palette["hatch"],
            }
        if highlight:
            return {
                "edge": self._palette["accent_dim"],
                "min": self._palette["accent"],
                "max": self._palette["accent_dim"],
                "text": COLOR_ORANGE,
                "value": self._palette["accent"],
                "hatch": self._palette["hatch"],
            }
        return {
            "edge": self._palette["orange_dim"],
            "min": self._palette["header"],
            "max": self._palette["orange_dim"],
            "text": COLOR_ORANGE,
            "value": COLOR_ORANGE,
            "hatch": self._palette["hatch"],
        }

    def _draw_volume_bar(self, cv, x, y, min_reward, max_reward, colors, prediction=False):
        # y is baseline; emulate SrvSurvey mini stacked reward bars.
        w = 9
        h = 17
        top = y - 13

        cv.create_rectangle(x, top, x + w, top + h, outline=colors["edge"], dash=(1, 2))
        if max_reward <= 0:
            cv.create_text(x + 5, y - 3, text="?", fill=self._palette["unknown"], font=("Consolas", 8, "bold"))
            return

        buckets = [0, 1_000_000, 6_000_000, 12_000_000]
        yy = y
        for bucket in buckets:
            seg_top = yy
            seg_bottom = yy + 3
            if min_reward > bucket:
                cv.create_rectangle(x, seg_top, x + w, seg_bottom, outline=colors["min"], fill=colors["min"])
            elif max_reward > bucket:
                cv.create_rectangle(x, seg_top, x + w, seg_bottom, outline=colors["max"], fill=colors["max"])
            yy -= 4

        if prediction:
            # Hatch-like diagonal pattern overlay.
            for dx in range(1, w, 2):
                cv.create_line(x + dx, top + 2, x + dx - 4, top + h - 1, fill=colors["hatch"])

    def _render_rows(self, model):
        cv = self.rows_canvas
        cv.delete("all")

        bodies = list(model.get("bodies", []) or [])
        bodies.sort(key=lambda b: (b.get("body_id") if b.get("body_id") is not None else 10_000_000, self._natural_key(self._short_body(model.get("system_name", ""), b.get("name", "")))))

        if not bodies:
            cv.create_text(6, 18, anchor="w", text="No bio signals", fill=self._palette["unknown"], font=("Consolas", 11))
            return

        row_h = 28
        top_pad = 4
        name_x = 4

        max_signals = max(int(b.get("signals", 0) or 0) for b in bodies)
        max_signals = max(1, max_signals)

        canvas_w = cv.winfo_width()
        if canvas_w <= 1:
            try:
                canvas_w = self.win.winfo_width() - 8
            except Exception:
                canvas_w = 286
        canvas_w = max(260, canvas_w)
        system_name = model.get("system_name", "")
        labels = [self._format_body_label(self._short_body(system_name, b.get("name", ""))) for b in bodies]
        name_font = tkfont.Font(family="Consolas", size=12)
        max_label_px = max((name_font.measure(lbl) for lbl in labels), default=16)
        label_gap_px = 10
        # Keep clear spacing between body label and first bar.
        box_left = max(40, min(120, name_x + max_label_px + label_gap_px))
        box_w = (max_signals * 11) + 2
        value_x = box_left + box_w + 10
        # If too tight, shift bars left a little and clamp value column.
        if value_x > canvas_w - 96:
            overflow = value_x - (canvas_w - 96)
            box_left = max(28, box_left - overflow)
            value_x = box_left + box_w + 8

        width = max(260, canvas_w)
        height = top_pad + (len(bodies) * row_h) + 4
        cv.config(scrollregion=(0, 0, width, height))

        # Short body IDs like 2a/3e should fit without truncation.
        char_px = 7
        name_max_chars = max(2, int((box_left - name_x - 14) / char_px))

        def _fit_name(txt):
            s = str(txt or "")
            if len(s) <= name_max_chars:
                return s
            if name_max_chars <= 1:
                return s[:1]
            return s[:name_max_chars - 1] + "…"

        for i, body in enumerate(bodies):
            y = top_pad + (i * row_h)
            short = self._format_body_label(self._short_body(system_name, body.get("name", "")))
            scanned = int(body.get("scanned", 0) or 0)
            signals = int(body.get("signals", 0) or 0)
            signals = max(0, signals)
            complete = signals > 0 and scanned >= signals
            highlight = (not complete) and scanned > 0
            colors = self._bar_colors(highlight=highlight, complete=complete)

            text_color = colors["text"] if not complete else self._palette["text_dim"]
            value_color = colors.get("value", COLOR_ORANGE if not complete else self._palette["text_dim"])
            display_name = _fit_name(short)
            name_id = cv.create_text(name_x, y + 14, anchor="w", text=display_name, fill=text_color, font=("Consolas", 12))

            # Dotted outer container showing total body signal count.
            outer_w = (signals * 11) + 2
            if outer_w > 2:
                cv.create_rectangle(box_left - 3, y + 2, box_left - 3 + outer_w, y + 23, outline=colors["edge"], dash=(1, 2))

            # Compute per-signal distributions.
            body_actual = int(body.get("actual", 0) or 0)
            pending = max(signals - scanned, 0)
            avg_scanned = int(body_actual / scanned) if scanned > 0 else 0
            pending_min_total = max(int(body.get("est_min", 0) or 0) - body_actual, 0)
            pending_max_total = max(int(body.get("est_max", 0) or 0) - body_actual, 0)
            avg_pending_min = int(pending_min_total / pending) if pending > 0 else 0
            avg_pending_max = int(pending_max_total / pending) if pending > 0 else 0

            x = box_left
            for idx in range(signals):
                if idx < scanned:
                    self._draw_volume_bar(cv, x, y + 16, avg_scanned, avg_scanned, colors, prediction=False)
                else:
                    self._draw_volume_bar(cv, x, y + 16, avg_pending_min, avg_pending_max, colors, prediction=True)
                x += 11

            value_txt = self._fmt_range(body.get("est_min", 0), body.get("est_max", 0))
            value_id = cv.create_text(value_x, y + 14, anchor="w", text=value_txt, fill=value_color, font=("Consolas", 12))

            if complete:
                # Strike-through complete rows like SrvSurvey.
                nbox = cv.bbox(name_id)
                if nbox:
                    yy = (nbox[1] + nbox[3]) / 2
                    cv.create_line(nbox[0], yy, nbox[2], yy, fill=self._palette["orange_deep"])
                vbox = cv.bbox(value_id)
                if vbox:
                    yy = (vbox[1] + vbox[3]) / 2
                    cv.create_line(vbox[0], yy, vbox[2], yy, fill=self._palette["orange_deep"])

    def _save_geometry(self):
        if not (self.win and self.win.winfo_exists()):
            return
        try:
            w = self.win.winfo_width()
            h = self.win.winfo_height()
            x = self.win.winfo_x()
            y = self.win.winfo_y()
            geom = f"{w}x{h}+{x}+{y}"
            if self.config.get("bio_estimate_popup_geometry") != geom:
                self.config["bio_estimate_popup_geometry"] = geom
                self.save_config_cb()
        except Exception:
            pass

    def _on_configure(self, _event):
        if not (self.win and self.win.winfo_exists()):
            return
        if self._save_job:
            try:
                self.win.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.win.after(250, self._save_geometry)

    def _on_drag_press(self, event):
        if not (self.win and self.win.winfo_exists()):
            self._drag_origin = None
            return
        self._drag_origin = (event.x_root, event.y_root, self.win.winfo_x(), self.win.winfo_y())

    def _on_drag_motion(self, event):
        if not (self.win and self.win.winfo_exists()) or not self._drag_origin:
            return
        ox, oy, wx, wy = self._drag_origin
        nx = wx + (event.x_root - ox)
        ny = wy + (event.y_root - oy)
        self.win.geometry(f"+{nx}+{ny}")

    def _on_drag_release(self, _event):
        self._drag_origin = None
        self._save_geometry()

    def show(self):
        self._ensure()
        if self.win and self.win.winfo_exists():
            self.win.deiconify()
            self.win.lift()
            self._manually_hidden = False

    def hide(self):
        self._save_geometry()
        if self.win and self.win.winfo_exists():
            self.win.withdraw()
            self._manually_hidden = True

    def destroy(self):
        self._save_geometry()
        if self.win and self.win.winfo_exists():
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win = None

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.config["bio_estimate_popup_enabled"] = self.enabled
        self.save_config_cb()
        if self.enabled:
            self._manually_hidden = False
            self.show()
        else:
            self.hide()

    def update(self, model):
        if not self.enabled:
            self.hide()
            return

        self._ensure()
        if not (self.win and self.win.winfo_exists()):
            return

        if not model:
            model = {
                "system_name": "---",
                "signals_scanned": 0,
                "total_signals": 0,
                "est_min": 0,
                "est_max": 0,
                "est_ff_min": 0,
                "est_ff_max": 0,
                "bodies": [],
            }

        render_key = (
            model.get("system_name"),
            model.get("total_signals"),
            model.get("est_min"),
            model.get("est_max"),
            model.get("est_ff_min"),
            model.get("est_ff_max"),
            tuple(
                (
                    b.get("body_id"),
                    b.get("name"),
                    b.get("signals"),
                    b.get("scanned"),
                    b.get("actual"),
                    b.get("est_min"),
                    b.get("est_max"),
                    b.get("first_footfall"),
                )
                for b in model.get("bodies", [])
            ),
        )
        if self._last_key == render_key:
            return
        self._last_key = render_key

        self.header_lbl.config(text=f"Bio signals: {int(model.get('total_signals', 0) or 0)}")
        rewards = self._fmt_range(model.get("est_min", 0), model.get("est_max", 0))
        self.footer_lbl.config(text=f"Rewards: {rewards}")

        any_ff = any(bool(b.get("first_footfall")) for b in model.get("bodies", []))
        if any_ff:
            ff_txt = self._fmt_range(model.get("est_ff_min", 0), model.get("est_ff_max", 0))
            self.ff_lbl.config(text=f"(FF bonus: {ff_txt})")
            self.ff_lbl.pack(fill=tk.X, padx=3, pady=(0, 2))
        else:
            self.ff_lbl.config(text="")
            self.ff_lbl.pack_forget()

        self._render_rows(model)
        if not self._manually_hidden:
            self.show()
