"""Live, profile-aware overlay arrangement studio."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from config import save_config
from overlay_input import set_mouse_passthrough
from ui_theme import (
    FONT_DISPLAY,
    FONT_MONO,
    FONT_TITLE,
    THEME,
    apply_window,
    button,
    configure_ttk,
    header,
    panel,
    scrollbar,
    section_label,
)


DEFAULT_POSITIONS = {
    "hud": (100, 100), "cargo_hud": (800, 400), "carrier_hud": (30, 180),
    "prospector_hud": (30, 600), "system_info_hud": (30, 30),
    "gravity_warning_hud": (1200, 530), "station_info_hud": (30, 380),
    "survey_status_hud": (30, 520), "toast_hud": (1200, 80),
    "heartbeat_hud": (24, 24), "colony_overlay": (40, 40),
}

OVERLAY_LABELS = {
    "hud": "Navigation HUD",
    "cargo_hud": "Cargo HUD",
    "carrier_hud": "Fleet Carrier HUD",
    "prospector_hud": "Prospector HUD",
    "system_info_hud": "System Information",
    "gravity_warning_hud": "Gravity Warning",
    "station_info_hud": "Station Information",
    "survey_status_hud": "Survey Status",
    "toast_hud": "Event Toast",
    "heartbeat_hud": "Journal Heartbeat",
    "colony_overlay": "Colony Overlay",
}


def _position_geometry(x, y):
    """Return Tk position geometry that also supports negative monitor offsets."""
    return f"{int(x):+d}{int(y):+d}"


class OverlayLayoutStudio:
    def __init__(self, root, app):
        self.app = app
        self.config = app.config
        self._rows = {}
        self._original_visibility = {}
        self._refresh_job = None
        self._closing = False
        self.win = tk.Toplevel(root)
        self.win.title("Overlay Layout Studio")
        try:
            self.win.geometry(self.config.get("overlay_layout_studio_geometry", "820x620"))
        except tk.TclError:
            self.win.geometry("820x620")
        self.win.minsize(720, 520)
        apply_window(self.win)
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.bind("<Escape>", lambda _event: self.close())
        self.win.bind("<F5>", lambda _event: self.refresh())
        self._expose_overlays()
        self._build()
        self.refresh()
        self._schedule_refresh()

    def is_open(self):
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def lift(self):
        self.win.lift()
        self.win.focus_force()

    def _overlay_records(self):
        for attr, x_key, y_key in self.app._OVERLAY_POSITION_SPECS:
            overlay = getattr(self.app, attr, None)
            window = getattr(overlay, "win", overlay)
            if window is None:
                continue
            try:
                if not window.winfo_exists():
                    continue
            except tk.TclError:
                continue
            yield attr, x_key, y_key, window

    def _expose_overlays(self):
        for attr, _x, _y, window in self._overlay_records():
            try:
                self._original_visibility[attr] = bool(window.winfo_viewable())
                set_mouse_passthrough(window, False)
                window.deiconify()
                window.lift()
            except tk.TclError:
                pass

    def _build(self):
        masthead = header(
            self.win,
            "OVERLAY LAYOUT STUDIO",
            "ARRANGE THE ACTIVE COMMANDER'S COCKPIT WORKSPACE",
            height=66,
        )
        masthead.pack(fill=tk.X, padx=14, pady=(14, 8))
        identity = tk.Frame(masthead, bg=THEME.header)
        identity.pack(side=tk.RIGHT, fill=tk.Y, padx=14)
        tk.Label(
            identity,
            text=str(self.config.get("active_commander_name") or "Unknown Commander").upper(),
            bg=THEME.header,
            fg=THEME.text,
            font=FONT_DISPLAY,
        ).pack(anchor="e", pady=(12, 0))
        tk.Label(
            identity,
            text="LIVE EDIT  •  INPUT UNLOCKED",
            bg=THEME.header,
            fg=THEME.green,
            font=("Cascadia Mono", 8, "bold"),
        ).pack(anchor="e", pady=(2, 0))

        guide = panel(self.win)
        guide.pack(fill=tk.X, padx=14, pady=(0, 8))
        guide_body = tk.Frame(guide, bg=THEME.panel)
        guide_body.pack(fill=tk.X, padx=12, pady=10)
        for number, title, detail in (
            ("01", "DRAG", "Move any visible overlay directly on screen"),
            ("02", "ALIGN", "Select a row and snap it to a nearby edge"),
            ("03", "SAVE", "Keep the positions or store a reusable preset"),
        ):
            item = tk.Frame(guide_body, bg=THEME.panel)
            item.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
            tk.Label(item, text=number, bg=THEME.panel, fg=THEME.accent,
                     font=FONT_TITLE).pack(side=tk.LEFT, padx=(0, 8))
            copy = tk.Frame(item, bg=THEME.panel)
            copy.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(copy, text=title, bg=THEME.panel, fg=THEME.orange,
                     font=FONT_DISPLAY, anchor="w").pack(fill=tk.X)
            tk.Label(copy, text=detail, bg=THEME.panel, fg=THEME.dim,
                     font=("Segoe UI", 8), anchor="w").pack(fill=tk.X)

        layout_card = panel(self.win, accent=True)
        layout_card.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))
        list_header = tk.Frame(layout_card, bg=THEME.panel)
        list_header.pack(fill=tk.X, padx=12, pady=(10, 7))
        section_label(list_header, "ACTIVE OVERLAYS").pack(side=tk.LEFT)
        self.count_var = tk.StringVar(value="0 WINDOWS")
        tk.Label(list_header, textvariable=self.count_var, bg=THEME.panel,
                 fg=THEME.muted, font=FONT_MONO).pack(side=tk.RIGHT)

        style = configure_ttk(self.win, "OverlayLayout")
        style.configure(
            "OverlayLayout.Treeview",
            background=THEME.inset,
            fieldbackground=THEME.inset,
            foreground=THEME.text,
            rowheight=28,
            borderwidth=0,
            font=FONT_MONO,
        )
        style.configure(
            "OverlayLayout.Treeview.Heading",
            background=THEME.panel_raised,
            foreground=THEME.orange,
            font=FONT_DISPLAY,
        )
        wrap = tk.Frame(layout_card, bg=THEME.panel)
        wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.tree = ttk.Treeview(
            wrap,
            columns=("overlay", "position", "size", "visible"),
            show="headings",
            selectmode="browse",
            style="OverlayLayout.Treeview",
        )
        for key, title, width, stretch in (
            ("overlay", "OVERLAY", 260, True),
            ("position", "POSITION", 130, False),
            ("size", "SIZE", 120, False),
            ("visible", "BEFORE STUDIO", 110, False),
        ):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=80, anchor=tk.W, stretch=stretch)
        bar = scrollbar(wrap, orient=tk.VERTICAL, command=self.tree.yview, prefix="OverlayLayout")
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        self.tree.bind("<Double-1>", self.focus_selected)

        controls = tk.Frame(self.win, bg=THEME.bg)
        controls.pack(fill=tk.X, padx=14, pady=(0, 8))

        preset_card = panel(controls)
        preset_card.pack(side=tk.LEFT, fill=tk.X, expand=True)
        preset_inner = tk.Frame(preset_card, bg=THEME.panel)
        preset_inner.pack(fill=tk.X, padx=12, pady=10)
        tk.Label(preset_inner, text="PROFILE PRESET", bg=THEME.panel, fg=THEME.muted,
                 font=FONT_DISPLAY).pack(side=tk.LEFT, padx=(0, 8))
        self.preset_var = tk.StringVar()
        self.preset_box = ttk.Combobox(
            preset_inner,
            textvariable=self.preset_var,
            state="readonly",
            width=19,
            style="OverlayLayout.TCombobox",
        )
        self.preset_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        button(preset_inner, "APPLY", self.apply_preset, accent=True).pack(side=tk.LEFT, padx=(8, 0))
        button(preset_inner, "SAVE", self.save_preset).pack(side=tk.LEFT, padx=(6, 0))
        button(preset_inner, "DELETE", self.delete_preset, danger=True).pack(side=tk.LEFT, padx=(6, 0))

        actions = tk.Frame(self.win, bg=THEME.bg)
        actions.pack(fill=tk.X, padx=14, pady=(0, 14))
        self.status_var = tk.StringVar(value="Positions update live. Press Done when the cockpit is arranged.")
        tk.Label(
            actions,
            textvariable=self.status_var,
            bg=THEME.bg,
            fg=THEME.muted,
            font=("Cascadia Mono", 8),
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        button(actions, "REFRESH", self.refresh, muted=True).pack(side=tk.LEFT, padx=(8, 0))
        button(actions, "BRING FORWARD", self.focus_selected).pack(side=tk.LEFT, padx=(6, 0))
        button(actions, "SNAP", self.snap_selected).pack(side=tk.LEFT, padx=(6, 0))
        button(actions, "RESET", self.reset_selected, danger=True).pack(side=tk.LEFT, padx=(6, 0))
        button(actions, "DONE", self.close, accent=True).pack(side=tk.LEFT, padx=(12, 0))

    def _schedule_refresh(self):
        if self._closing or not self.is_open():
            return
        self._refresh_job = self.win.after(450, self._poll_positions)

    def _poll_positions(self):
        self._refresh_job = None
        if self._closing or not self.is_open():
            return
        self.refresh(quiet=True)
        self._schedule_refresh()

    def _set_status(self, message):
        try:
            self.status_var.set(message)
        except (AttributeError, tk.TclError):
            pass

    def refresh(self, quiet=False):
        selected_attr = self.tree.selection()[0] if self.tree.selection() else None
        live_attrs = set()
        for attr, x_key, y_key, window in self._overlay_records():
            try:
                x, y = int(window.winfo_x()), int(window.winfo_y())
                width, height = int(window.winfo_width()), int(window.winfo_height())
            except tk.TclError:
                continue
            live_attrs.add(attr)
            values = (
                OVERLAY_LABELS.get(attr, attr.replace("_", " ").title()),
                f"{x:+d}, {y:+d}",
                f"{width} × {height}",
                "SHOWN" if self._original_visibility.get(attr) else "HIDDEN",
            )
            if self.tree.exists(attr):
                self.tree.item(attr, values=values)
            else:
                self.tree.insert("", tk.END, iid=attr, values=values)
            self._rows[attr] = (attr, x_key, y_key, window)
        for iid in self.tree.get_children():
            if iid not in live_attrs:
                self.tree.delete(iid)
                self._rows.pop(iid, None)
        children = self.tree.get_children()
        if children:
            chosen = selected_attr if selected_attr in live_attrs else children[0]
            if self.tree.selection() != (chosen,):
                self.tree.selection_set(chosen)
        self.count_var.set(f"{len(children)} WINDOW{'S' if len(children) != 1 else ''}")

        names = sorted((self.config.get("overlay_layout_presets") or {}).keys(), key=str.casefold)
        self.preset_box.configure(values=names)
        if names and self.preset_var.get() not in names:
            self.preset_var.set(names[0])
        elif not names:
            self.preset_var.set("")
        if not quiet:
            self._set_status("Overlay positions refreshed from the live desktop.")

    def _selected(self):
        chosen = self.tree.selection()
        return self._rows.get(chosen[0]) if chosen else None

    def _selection_changed(self, _event=None):
        row = self._selected()
        if row:
            self._set_status(f"Selected {OVERLAY_LABELS.get(row[0], row[0])}.")

    def focus_selected(self, _event=None):
        row = self._selected()
        if not row:
            self._set_status("Select an overlay first.")
            return
        attr, _x_key, _y_key, window = row
        try:
            window.deiconify()
            window.lift()
            self.win.after(120, self.win.lift)
            self._set_status(f"Brought {OVERLAY_LABELS.get(attr, attr)} forward.")
        except tk.TclError:
            pass

    def _capture(self):
        result = {}
        for attr, x_key, y_key, window in self._overlay_records():
            try:
                result[attr] = {
                    "x": int(window.winfo_x()),
                    "y": int(window.winfo_y()),
                    "x_key": x_key,
                    "y_key": y_key,
                }
            except tk.TclError:
                pass
        return result

    @staticmethod
    def _desktop_bounds(window):
        """Return virtual-desktop bounds, including monitors left of the primary."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            left = int(user32.GetSystemMetrics(76))
            top = int(user32.GetSystemMetrics(77))
            width = int(user32.GetSystemMetrics(78))
            height = int(user32.GetSystemMetrics(79))
            if width > 0 and height > 0:
                return left, top, left + width, top + height
        except (AttributeError, OSError):
            pass
        try:
            left, top = int(window.winfo_vrootx()), int(window.winfo_vrooty())
            width, height = int(window.winfo_vrootwidth()), int(window.winfo_vrootheight())
            if width > 0 and height > 0:
                return left, top, left + width, top + height
        except (AttributeError, tk.TclError):
            pass
        return 0, 0, int(window.winfo_screenwidth()), int(window.winfo_screenheight())

    def snap_selected(self):
        row = self._selected()
        if not row:
            self._set_status("Select an overlay first.")
            return
        attr, _x_key, _y_key, window = row
        x, y = int(window.winfo_x()), int(window.winfo_y())
        width, height = int(window.winfo_width()), int(window.winfo_height())
        left, top, right, bottom = self._desktop_bounds(window)
        candidates_x = [left, max(left, right - width)]
        candidates_y = [top, max(top, bottom - height)]
        for other_attr, _x, _y, other in self._overlay_records():
            if other_attr == attr:
                continue
            ox, oy = int(other.winfo_x()), int(other.winfo_y())
            ow, oh = int(other.winfo_width()), int(other.winfo_height())
            candidates_x.extend((ox, ox + ow, ox - width, ox + ow - width))
            candidates_y.extend((oy, oy + oh, oy - height, oy + oh - height))
        nearest_x = min(candidates_x, key=lambda value: abs(value - x))
        nearest_y = min(candidates_y, key=lambda value: abs(value - y))
        x = nearest_x if abs(nearest_x - x) <= 20 else x
        y = nearest_y if abs(nearest_y - y) <= 20 else y
        x = max(left, min(x, right - width))
        y = max(top, min(y, bottom - height))
        window.geometry(_position_geometry(x, y))
        self._set_status(f"Snapped {OVERLAY_LABELS.get(attr, attr)} to the nearest edge.")
        self.win.after(60, lambda: self.refresh(quiet=True))

    def reset_selected(self):
        row = self._selected()
        if not row:
            self._set_status("Select an overlay first.")
            return
        attr, _x_key, _y_key, window = row
        x, y = DEFAULT_POSITIONS.get(attr, (30, 30))
        window.geometry(_position_geometry(x, y))
        self._set_status(f"Reset {OVERLAY_LABELS.get(attr, attr)} to its default position.")
        self.win.after(60, lambda: self.refresh(quiet=True))

    def save_preset(self):
        name = simpledialog.askstring("Save Overlay Preset", "Preset name:", parent=self.win)
        if not name or not str(name).strip():
            return
        name = str(name).strip()[:50]
        presets = self.config.setdefault("overlay_layout_presets", {})
        if name in presets and not messagebox.askyesno(
            "Replace Overlay Preset", f"Replace the existing '{name}' preset?", parent=self.win,
        ):
            return
        presets[name] = self._capture()
        save_config(self.config)
        self.preset_var.set(name)
        self.refresh(quiet=True)
        self._set_status(f"Saved '{name}' for this commander profile.")

    def apply_preset(self):
        name = self.preset_var.get()
        preset = (self.config.get("overlay_layout_presets") or {}).get(name) or {}
        if not preset:
            self._set_status("Choose a saved profile preset first.")
            return
        records = {attr: window for attr, _x, _y, window in self._overlay_records()}
        applied = 0
        for attr, pos in preset.items():
            window = records.get(attr)
            if not window or not isinstance(pos, dict):
                continue
            try:
                window.geometry(_position_geometry(pos.get("x", 0), pos.get("y", 0)))
                applied += 1
            except (TypeError, ValueError, tk.TclError):
                pass
        self.app._capture_overlay_positions()
        save_config(self.config)
        self._set_status(f"Applied '{name}' to {applied} overlay{'s' if applied != 1 else ''}.")
        self.win.after(60, lambda: self.refresh(quiet=True))

    def delete_preset(self):
        name = self.preset_var.get()
        presets = self.config.get("overlay_layout_presets") or {}
        if not name or name not in presets:
            self._set_status("Choose a saved profile preset first.")
            return
        if not messagebox.askyesno("Delete Overlay Preset", f"Delete '{name}'?", parent=self.win):
            return
        presets.pop(name, None)
        self.preset_var.set("")
        save_config(self.config)
        self.refresh(quiet=True)
        self._set_status(f"Deleted '{name}' from this commander profile.")

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self._refresh_job is not None:
            try:
                self.win.after_cancel(self._refresh_job)
            except tk.TclError:
                pass
            self._refresh_job = None
        try:
            self.config["overlay_layout_studio_geometry"] = self.win.geometry()
            self.app._capture_overlay_positions()
            for attr, _x, _y, window in self._overlay_records():
                if not self._original_visibility.get(attr):
                    window.withdraw()
                set_mouse_passthrough(window, bool(self.config.get("overlay_mouse_passthrough", True)))
            save_config(self.config)
        except Exception:
            pass
        try:
            self.win.destroy()
        except tk.TclError:
            pass
