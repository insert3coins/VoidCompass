"""Animated startup and first-commissioning boot scene for Void Compass.

The scene is deliberately code-native: no image asset, web view, or additional
runtime dependency is needed by the Windows or Linux package.
"""

from __future__ import annotations

import math
import random
import re
import time
import tkinter as tk

from ui_theme import THEME, apply_window
from version import APP_VERSION


BOOT_LINES = (
    ("FLIGHT COMPUTER", "CORE SERVICES READY", "accent"),
    ("PROFILE VAULT", "COMMANDER ISOLATION READY", "text"),
    ("JOURNAL LINK", "AWAITING LIVE TELEMETRY", "orange"),
    ("SURVEY ENGINE", "FSS · DSS · EXOBIOLOGY READY", "text"),
    ("ROUTE INTELLIGENCE", "NAVIGATION CORE READY", "text"),
    ("OVERLAY BUS", "NATIVE FLIGHT DECK READY", "orange"),
    ("EXPEDITION MEMORY", "LOCAL DATA STORE READY", "text"),
    ("VOID COMPASS", "FIRST COMMISSIONING READY", "green"),
)

STARTUP_BOOT_LINES = (
    ("FLIGHT COMPUTER", "CORE SERVICES READY", "accent"),
    ("PROFILE VAULT", "ACTIVE COMMANDER READY", "text"),
    ("JOURNAL LINK", "LIVE TELEMETRY PREPARED", "orange"),
    ("SURVEY ENGINE", "DISCOVERY CACHE READY", "text"),
    ("ROUTE INTELLIGENCE", "NAVIGATION STATE READY", "text"),
    ("OVERLAY BUS", "SAVED FLIGHT DECK READY", "orange"),
    ("EXPEDITION MEMORY", "LOCAL RECORDS READY", "text"),
    ("VOID COMPASS", "DASHBOARD LAUNCH READY", "green"),
)


def _mix_colour(first, second, amount):
    """Blend two Tk hex colours without needing an image/alpha layer."""
    try:
        amount = max(0.0, min(1.0, float(amount)))
        left = tuple(int(first[index:index + 2], 16) for index in (1, 3, 5))
        right = tuple(int(second[index:index + 2], 16) for index in (1, 3, 5))
    except (TypeError, ValueError):
        return first
    mixed = tuple(round(a + (b - a) * amount) for a, b in zip(left, right))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


class FirstRunBoot:
    """Mandatory, lightweight flight-computer readiness scene."""

    FRAME_MS = 40

    def __init__(
        self, parent, on_done, *, reduced_motion=False, commissioning=True,
        hold_after_ready=False,
    ):
        self.parent = parent
        self.on_done = on_done
        self.reduced_motion = bool(reduced_motion)
        self.commissioning = bool(commissioning)
        self.hold_after_ready = bool(hold_after_ready)
        self.boot_lines = BOOT_LINES if self.commissioning else STARTUP_BOOT_LINES
        self.runtime_status = ""
        self.runtime_detail = ""
        self.runtime_progress = None
        self.frame = tk.Frame(parent, bg="#03070b")
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            self.frame, bg="#03070b", bd=0, highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        rng = random.Random(7319)
        self.stars = [
            [rng.random(), rng.random(), rng.choice((0.00035, 0.0006, 0.0011)),
             rng.choice((1, 1, 1, 2))]
            for _ in range(105)
        ]
        # A seeded galactic dust lane and survey contacts add depth without an
        # image asset, I/O, or non-Tk dependency during the critical path.
        self.galactic_dust = [
            (rng.random(), rng.gauss(0.0, 0.34), rng.choice((1, 1, 2, 2, 3)),
             rng.random())
            for _ in range(82)
        ]
        self.scope_contacts = [
            (rng.uniform(0.15, 0.92), rng.uniform(0.0, math.tau),
             rng.random() * math.tau, rng.choice(("accent", "orange", "green")))
            for _ in range(6)
        ]
        self.started_at = time.monotonic()
        self.line_index = 0
        self.visible_lines = []
        self._frame_job = None
        self._line_job = None
        self._finish_job = None
        self._stopped = False
        self._ready_emitted = False
        self._frame_job = self.parent.after(40, self._tick)
        self._line_job = self.parent.after(220, self._advance_line)

    @staticmethod
    def _colour(slot):
        return {
            "accent": THEME.accent,
            "orange": THEME.orange,
            "green": THEME.green,
            "text": THEME.text,
        }.get(slot, THEME.text)

    def _advance_line(self):
        self._line_job = None
        if self._stopped:
            return
        if self.line_index >= len(self.boot_lines):
            self._finish_job = self.parent.after(450, self.finish)
            return
        self.visible_lines.append(self.boot_lines[self.line_index])
        self.line_index += 1
        delay = 120 if self.reduced_motion else 165
        self._line_job = self.parent.after(delay, self._advance_line)

    def _draw_ship(self, canvas, x, y, pulse):
        accent = THEME.accent
        orange = THEME.orange
        halo = _mix_colour("#03070b", accent, 0.22 + pulse * 0.08)
        canvas.create_oval(
            x - 35 - pulse * 3, y - 24 - pulse * 3,
            x + 35 + pulse * 3, y + 24 + pulse * 3,
            outline=halo,
        )
        canvas.create_polygon(
            x + 22, y,
            x + 6, y - 6,
            x - 19, y - 5,
            x - 27, y,
            x - 19, y + 5,
            x + 6, y + 6,
            fill="#0b1820", outline=accent, width=2,
        )
        canvas.create_polygon(
            x + 3, y - 5, x - 17, y - 17, x - 22, y - 4,
            fill="#071117", outline=orange,
        )
        canvas.create_polygon(
            x + 3, y + 5, x - 17, y + 17, x - 22, y + 4,
            fill="#071117", outline=orange,
        )
        exhaust = 11 + 5 * pulse
        canvas.create_line(
            x - 27, y, x - 27 - exhaust, y,
            fill=orange, width=2,
        )

    @staticmethod
    def _corner_frame(canvas, left, top, right, bottom, colour, length=18):
        """Draw quiet instrument corners rather than a heavy enclosing box."""
        segments = (
            (left, top + length, left, top, left + length, top),
            (right - length, top, right, top, right, top + length),
            (right, bottom - length, right, bottom, right - length, bottom),
            (left + length, bottom, left, bottom, left, bottom - length),
        )
        for points in segments:
            canvas.create_line(*points, fill=colour, width=1)

    def _draw_background(self, canvas, width, height, elapsed):
        bg = _mix_colour("#010306", THEME.bg, 0.72)
        deep = _mix_colour(bg, THEME.panel, 0.34)
        for index in range(14):
            top = height * index / 14
            bottom = height * (index + 1) / 14 + 1
            amount = 0.12 + 0.25 * math.sin((index / 13) * math.pi)
            canvas.create_rectangle(
                0, top, width, bottom,
                fill=_mix_colour(bg, deep, amount), outline="",
            )

        grid = _mix_colour(bg, THEME.border, 0.25)
        for index in range(1, 10):
            x = width * index / 10
            canvas.create_line(x, 112, x, height - 82, fill=grid)
        for index in range(1, 6):
            y = 112 + (height - 194) * index / 6
            canvas.create_line(24, y, width - 24, y, fill=grid)

        # Diagonal Milky Way suggestion, deliberately subtle behind telemetry.
        for along, spread, size, brightness in self.galactic_dust:
            x = width * (0.34 + along * 0.68)
            y = height * (0.08 + along * 0.55 + spread * 0.16)
            if not (-4 <= x <= width + 4 and -4 <= y <= height + 4):
                continue
            twinkle = 0 if self.reduced_motion else math.sin(elapsed + along * 13) * 0.018
            colour = _mix_colour(
                bg, THEME.muted, 0.08 + brightness * 0.13 + twinkle,
            )
            canvas.create_oval(x - size, y - size, x + size, y + size,
                               fill=colour, outline="")
        return bg

    def _draw_header(self, canvas, width, bg):
        shadow = _mix_colour(bg, THEME.accent, 0.18)
        canvas.create_text(
            37, 35, anchor="nw", text="VOID COMPASS",
            fill=shadow, font=("Bahnschrift SemiCondensed", 30, "bold"),
        )
        canvas.create_text(
            34, 32, anchor="nw", text="VOID COMPASS",
            fill=THEME.accent,
            font=("Bahnschrift SemiCondensed", 30, "bold"),
        )
        canvas.create_text(
            36, 78, anchor="nw",
            text=f"EXPLORATION FLIGHT SYSTEM   v{APP_VERSION}",
            fill=THEME.orange, font=("Cascadia Mono", 8, "bold"),
        )
        canvas.create_line(36, 103, width - 36, 103, fill=THEME.border, width=1)
        canvas.create_rectangle(36, 101, 112, 104, fill=THEME.accent, outline="")

        chips = (("LOCAL DATA", THEME.green), ("PROFILE SAFE", THEME.accent),
                 ("JOURNAL LINK", THEME.orange))
        chip_right = width - 36
        for label, colour in reversed(chips):
            chip_width = 88 if label != "PROFILE SAFE" else 96
            chip_left = chip_right - chip_width
            canvas.create_rectangle(
                chip_left, 44, chip_right, 66,
                fill=_mix_colour(bg, colour, 0.10),
                outline=_mix_colour(bg, colour, 0.52),
            )
            canvas.create_oval(
                chip_left + 8, 52, chip_left + 13, 57,
                fill=colour, outline="",
            )
            canvas.create_text(
                chip_left + 19, 55, anchor="w", text=label,
                fill=_mix_colour(THEME.dim, colour, 0.45),
                font=("Cascadia Mono", 7, "bold"),
            )
            chip_right = chip_left - 7

    @staticmethod
    def _main_panel_geometry(width, height):
        """Return shared boot-log and exploration-panel boundaries."""
        top = 124
        bottom = height - 91
        log_left = 30
        log_right = min(478, width * 0.54)
        instrument_left = max(log_right + 24, width * 0.57)
        instrument_right = width - 30
        return log_left, log_right, instrument_left, instrument_right, top, bottom

    def _draw_boot_log(self, canvas, width, height, bg):
        left, right, _, _, top, bottom = self._main_panel_geometry(width, height)
        panel_fill = _mix_colour(bg, THEME.panel, 0.68)
        canvas.create_polygon(
            left, top + 12, left + 12, top, right, top,
            right, bottom - 12, right - 12, bottom, left, bottom,
            fill=panel_fill, outline=THEME.border_soft,
        )
        self._corner_frame(canvas, left, top, right, bottom, THEME.border)
        heading = (
            "FIRST COMMISSIONING"
            if self.commissioning else "FLIGHT DECK SYNCHRONISATION"
        )
        canvas.create_text(
            left + 15, top + 14, anchor="nw", text=heading,
            fill=THEME.text, font=("Segoe UI", 9, "bold"),
        )
        canvas.create_text(
            right - 15, top + 17, anchor="ne",
            text=f"CHECK {len(self.visible_lines):02d}/{len(self.boot_lines):02d}",
            fill=THEME.dim, font=("Cascadia Mono", 7, "bold"),
        )
        canvas.create_line(
            left + 15, top + 42, right - 15, top + 42,
            fill=THEME.border_soft,
        )

        log_y = top + 57
        available = max(8, int((bottom - log_y - 8) / 29))
        for index, (system, status, colour_slot) in enumerate(
            self.visible_lines[-available:]
        ):
            y = log_y + index * 29
            colour = self._colour(colour_slot)
            canvas.create_rectangle(
                left + 15, y + 3, left + 20, y + 8,
                fill=colour, outline="",
            )
            canvas.create_text(
                left + 29, y, anchor="nw", text=system,
                fill=THEME.muted, font=("Cascadia Mono", 8, "bold"),
            )
            canvas.create_text(
                left + 183, y, anchor="nw", text=status,
                fill=colour, font=("Cascadia Mono", 8),
            )

    def _draw_scope(self, canvas, width, height, elapsed, pulse, bg):
        _, _, left, right, top, bottom = self._main_panel_geometry(width, height)
        panel_fill = _mix_colour(bg, THEME.panel, 0.68)
        canvas.create_polygon(
            left, top + 12, left + 12, top, right, top,
            right, bottom - 12, right - 12, bottom, left, bottom,
            fill=panel_fill, outline=THEME.border_soft,
        )
        self._corner_frame(canvas, left, top, right, bottom, THEME.border)
        canvas.create_text(
            left + 15, top + 14, anchor="nw", text="EXPLORATION ARRAY",
            fill=THEME.text, font=("Segoe UI", 9, "bold"),
        )
        canvas.create_text(
            right - 15, top + 17, anchor="ne", text="FSS  //  PASSIVE",
            fill=THEME.dim, font=("Cascadia Mono", 7, "bold"),
        )
        canvas.create_line(
            left + 15, top + 42, right - 15, top + 42,
            fill=THEME.border_soft,
        )

        radar_x = (left + right) / 2
        radar_y = top + 132
        radar_r = min(64, (right - left) * 0.19, (bottom - top) * 0.20)
        frame_colour = _mix_colour(bg, THEME.accent, 0.45)
        for factor in (1.0, 0.66, 0.33):
            radius = radar_r * factor
            canvas.create_oval(
                radar_x - radius, radar_y - radius,
                radar_x + radius, radar_y + radius,
                outline=frame_colour if factor == 1 else THEME.border_soft,
            )
        canvas.create_line(
            radar_x - radar_r, radar_y, radar_x + radar_r, radar_y,
            fill=THEME.border_soft,
        )
        canvas.create_line(
            radar_x, radar_y - radar_r, radar_x, radar_y + radar_r,
            fill=THEME.border_soft,
        )
        for angle in range(0, 360, 30):
            radians = math.radians(angle)
            inner = radar_r - (7 if angle % 90 == 0 else 4)
            canvas.create_line(
                radar_x + math.cos(radians) * inner,
                radar_y + math.sin(radians) * inner,
                radar_x + math.cos(radians) * radar_r,
                radar_y + math.sin(radians) * radar_r,
                fill=frame_colour,
            )

        sweep = elapsed * (0.12 if self.reduced_motion else 0.82)
        for trail, strength in ((-0.13, 0.18), (-0.065, 0.32), (0, 0.78)):
            angle = sweep + trail
            canvas.create_line(
                radar_x, radar_y,
                radar_x + math.cos(angle) * radar_r,
                radar_y + math.sin(angle) * radar_r,
                fill=_mix_colour(bg, THEME.accent, strength),
                width=2 if trail == 0 else 1,
            )
        for radius, angle, phase, slot in self.scope_contacts:
            x = radar_x + math.cos(angle) * radar_r * radius
            y = radar_y + math.sin(angle) * radar_r * radius
            contact_pulse = 0.5 if self.reduced_motion else (
                math.sin(elapsed * 2.3 + phase) + 1
            ) / 2
            colour = self._colour(slot)
            size = 2.0 + contact_pulse * 1.8
            canvas.create_oval(x - size, y - size, x + size, y + size,
                               fill=colour, outline="")
            if contact_pulse > 0.78:
                canvas.create_oval(
                    x - 7, y - 7, x + 7, y + 7,
                    outline=_mix_colour(bg, colour, 0.4),
                )
        canvas.create_oval(
            radar_x - 3, radar_y - 3, radar_x + 3, radar_y + 3,
            fill=THEME.accent, outline="",
        )
        canvas.create_text(
            radar_x, radar_y + radar_r + 15,
            text=f"CONTACTS {len(self.scope_contacts):02d}   RANGE  AUTO",
            fill=THEME.dim, font=("Cascadia Mono", 7, "bold"),
        )

    def _draw_route(self, canvas, width, height, elapsed, progress, pulse, bg):
        _, _, panel_left, panel_right, _, bottom = self._main_panel_geometry(
            width, height,
        )
        # Keep the animated ship halo inside the shared right-hand panel.
        left, right = panel_left + 42, panel_right - 42
        route_y = bottom - 47
        label_y = bottom - 110
        offsets = (7, -2, 5, -7, 1, -4, 4)
        points = [
            (left + (right - left) * index / 6, route_y + offsets[index])
            for index in range(7)
        ]
        canvas.create_text(
            panel_left + 15, label_y, anchor="nw", text="NAVIGATION SOLUTION",
            fill=THEME.dim, font=("Cascadia Mono", 7, "bold"),
        )
        canvas.create_text(
            panel_right - 15, label_y, anchor="ne", text="DEEP SPACE VECTOR",
            fill=THEME.orange, font=("Cascadia Mono", 7, "bold"),
        )
        canvas.create_line(
            *[coordinate for point in points for coordinate in point],
            fill=THEME.border, width=2, smooth=True,
        )
        scaled = max(0.0, min(1.0, progress)) * 6
        segment = min(5, int(scaled))
        fraction = scaled - segment
        current_x = points[segment][0] + (
            points[segment + 1][0] - points[segment][0]
        ) * fraction
        current_y = points[segment][1] + (
            points[segment + 1][1] - points[segment][1]
        ) * fraction
        reached = points[:segment + 1] + [(current_x, current_y)]
        if len(reached) > 1:
            canvas.create_line(
                *[coordinate for point in reached for coordinate in point],
                fill=THEME.accent, width=2, smooth=True,
            )
        for index, (x, y) in enumerate(points):
            complete = index <= scaled + 1e-6
            radius = 4 if complete else 3
            canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill=THEME.accent if complete else bg,
                outline=THEME.accent if complete else THEME.dim,
            )
        ship_y = current_y - 23 + (
            0 if self.reduced_motion else math.sin(elapsed * 2.2) * 2
        )
        self._draw_ship(canvas, current_x, ship_y, pulse)

    def _draw_readiness(self, canvas, width, height, progress, bg):
        left, right = 30, width - 30
        top, bottom = height - 76, height - 15
        canvas.create_rectangle(
            left, top, right, bottom,
            fill=_mix_colour(bg, THEME.panel, 0.82),
            outline=THEME.border_soft,
        )
        status = self.runtime_status or (
            "READY FOR COMMANDER SETUP"
            if progress >= 1 and self.commissioning else
            "READY TO LAUNCH DASHBOARD"
            if progress >= 1 else
            "PREPARING LOCAL FLIGHT DECK"
        )
        status_colour = THEME.green if progress >= 1 else THEME.accent
        canvas.create_text(
            left + 12, top + 9, anchor="nw", text=status,
            fill=status_colour, font=("Cascadia Mono", 8, "bold"),
        )
        detail = self.runtime_detail or "Verifying profile-aware exploration systems"
        canvas.create_text(
            left + 12, top + 29, anchor="nw", text=detail,
            fill=THEME.dim, font=("Cascadia Mono", 8),
        )
        canvas.create_text(
            right - 12, top + 10, anchor="ne",
            text=f"READINESS  {round(progress * 100):03d}%",
            fill=THEME.muted, font=("Cascadia Mono", 7, "bold"),
        )
        bar_left, bar_right = left + 12, right - 12
        bar_y = bottom - 9
        gap, segments = 3, 28
        segment_width = (bar_right - bar_left - gap * (segments - 1)) / segments
        active = progress * segments
        for index in range(segments):
            x = bar_left + index * (segment_width + gap)
            colour = THEME.accent if index < active else THEME.border_soft
            if progress >= 1 and index < active:
                colour = THEME.green
            canvas.create_rectangle(
                x, bar_y, x + segment_width, bar_y + 3,
                fill=colour, outline="",
            )

    def _tick(self):
        self._frame_job = None
        if self._stopped:
            return
        canvas = self.canvas
        try:
            width = max(640, canvas.winfo_width())
            height = max(420, canvas.winfo_height())
        except tk.TclError:
            return
        elapsed = time.monotonic() - self.started_at
        progress = min(1.0, self.line_index / max(1, len(self.boot_lines)))
        if self.runtime_progress is not None:
            progress = max(0.0, min(1.0, float(self.runtime_progress)))
        pulse = (math.sin(elapsed * 4.0) + 1.0) / 2.0

        canvas.delete("all")
        bg = self._draw_background(canvas, width, height, elapsed)

        for star in self.stars:
            if not self.reduced_motion:
                star[0] -= star[2]
                if star[0] < 0:
                    star[0] += 1.0
                    star[1] = (star[1] * 1.731 + 0.193) % 1.0
            x = star[0] * width
            y = star[1] * height
            size = star[3]
            colour = THEME.dim if size == 1 else THEME.muted
            canvas.create_oval(x, y, x + size, y + size, fill=colour, outline="")

        self._draw_header(canvas, width, bg)
        self._draw_boot_log(canvas, width, height, bg)
        self._draw_scope(canvas, width, height, elapsed, pulse, bg)
        self._draw_route(canvas, width, height, elapsed, progress, pulse, bg)
        self._draw_readiness(canvas, width, height, progress, bg)

        try:
            self._frame_job = self.parent.after(self.FRAME_MS, self._tick)
        except tk.TclError:
            self._frame_job = None

    def stop(self):
        if self._stopped:
            return
        self._stopped = True
        for job in (self._frame_job, self._line_job, self._finish_job):
            if job is not None:
                try:
                    self.parent.after_cancel(job)
                except tk.TclError:
                    pass
        self._frame_job = self._line_job = self._finish_job = None

    def set_runtime_status(self, status, detail="", progress=None):
        """Publish a real startup phase while the boot scene remains mapped."""
        self.runtime_status = str(status or "")
        self.runtime_detail = str(detail or "")
        if progress is not None:
            try:
                self.runtime_progress = max(0.0, min(1.0, float(progress)))
            except (TypeError, ValueError):
                pass

    def finish(self):
        if self._stopped or self._ready_emitted:
            return
        self._ready_emitted = True
        if self.hold_after_ready:
            for job in (self._line_job, self._finish_job):
                if job is not None:
                    try:
                        self.parent.after_cancel(job)
                    except tk.TclError:
                        pass
            self._line_job = self._finish_job = None
            self.line_index = len(self.boot_lines)
            if not self.runtime_status:
                self.set_runtime_status(
                    "BUILDING DASHBOARD CORE",
                    "Loading profile-aware flight systems",
                    0.18,
                )
        else:
            self.stop()
        try:
            self.on_done()
        except tk.TclError:
            pass


_WINDOW_GEOMETRY_RE = re.compile(
    r"^(?P<width>\d+)x(?P<height>\d+)(?P<x>[+-]\d+)(?P<y>[+-]\d+)$"
)


def startup_boot_geometry(root, config, width=900, height=590):
    """Centre the boot scene over the profile's saved main-window footprint."""
    flight_log = bool((config or {}).get("flight_log_mode_enabled", False))
    geometry_key = "flight_log_geometry" if flight_log else "dashboard_window_geometry"
    raw = str((config or {}).get(geometry_key) or "")
    match = _WINDOW_GEOMETRY_RE.fullmatch(raw)
    if match:
        dashboard_width = int(match.group("width"))
        dashboard_height = int(match.group("height"))
        dashboard_x = int(match.group("x"))
        dashboard_y = int(match.group("y"))
        x = dashboard_x + (dashboard_width - width) // 2
        y = dashboard_y + (dashboard_height - height) // 2
        return f"{width}x{height}{x:+d}{y:+d}"
    screen_width = max(width, int(root.winfo_screenwidth() or width))
    screen_height = max(height, int(root.winfo_screenheight() or height))
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    return f"{width}x{height}{x:+d}{y:+d}"


def show_startup_boot(root, config, on_ready):
    """Show the returning-commander boot window and hand its window to on_ready.

    The caller keeps the final frame mapped until the Dashboard reaches its
    live journal tail, avoiding the blank or stale pre-load window retired by
    the readiness gate.
    """
    win = tk.Toplevel(root)
    win.title("VOID COMPASS // STARTUP")
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    apply_window(win, background="#03070b")
    win.geometry(startup_boot_geometry(root, config))
    win.resizable(False, False)

    shell = tk.Frame(
        win, bg="#03070b", highlightbackground=THEME.accent,
        highlightthickness=1,
    )
    shell.pack(fill=tk.BOTH, expand=True)
    chrome = tk.Frame(shell, bg=THEME.header, height=34)
    chrome.pack(fill=tk.X)
    chrome.pack_propagate(False)
    title = tk.Label(
        chrome, text=f"VOID COMPASS  //  STARTUP  //  v{APP_VERSION}",
        bg=THEME.header, fg=THEME.muted,
        font=("Cascadia Mono", 7, "bold"), anchor="w",
    )
    title.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=11)

    state = {"handoff": False, "closed": False, "boot": None}

    def abort_startup():
        if state["closed"]:
            return
        state["closed"] = True
        boot = state.get("boot")
        if boot is not None:
            boot.stop()
        try:
            win.grab_release()
        except tk.TclError:
            pass
        try:
            win.destroy()
        finally:
            root.destroy()

    close_btn = tk.Button(
        chrome, text="×", command=abort_startup, bg=THEME.header,
        fg=THEME.muted, activebackground=THEME.red,
        activeforeground=THEME.text, relief=tk.FLAT, bd=0,
        font=("Segoe UI", 11, "bold"), width=4, cursor="hand2",
    )
    close_btn.pack(side=tk.RIGHT, fill=tk.Y)

    drag_origin = {"x": 0, "y": 0}

    def begin_drag(event):
        drag_origin["x"] = event.x_root - win.winfo_x()
        drag_origin["y"] = event.y_root - win.winfo_y()

    def drag_window(event):
        win.geometry(
            f"+{event.x_root - drag_origin['x']}+{event.y_root - drag_origin['y']}"
        )

    for widget in (chrome, title):
        widget.bind("<ButtonPress-1>", begin_drag, add="+")
        widget.bind("<B1-Motion>", drag_window, add="+")

    stage = tk.Frame(shell, bg="#03070b")
    stage.pack(fill=tk.BOTH, expand=True)

    def ready():
        if state["handoff"] or state["closed"]:
            return
        state["handoff"] = True
        try:
            win.grab_release()
        except tk.TclError:
            pass
        # Leave the final scene mapped through synchronous construction and
        # asynchronous journal/history recovery. MainDashboard retires it only
        # after every startup readiness gate has passed.
        win.after_idle(lambda: on_ready(win))

    state["boot"] = FirstRunBoot(
        stage, ready,
        reduced_motion=bool((config or {}).get("reduced_motion_enabled", False)),
        commissioning=False,
        hold_after_ready=True,
    )
    win._voidcompass_boot = state["boot"]
    win.protocol("WM_DELETE_WINDOW", abort_startup)
    win.grab_set()
    win.lift()
    win.focus_force()
    return win
