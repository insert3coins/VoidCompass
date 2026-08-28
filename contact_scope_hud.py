"""Contextual deep-space contact overlay for FSS non-body signals."""

from __future__ import annotations

import tkinter as tk

from config import save_config
import overlay_chrome
import themes


_CHROMA = "#ff00ff"
WIDTH = 480


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _text(value):
    value = str(value or "").strip()
    if value.startswith("$"):
        value = value.strip("$;")
        value = value.replace("_Name", "").replace("_", " ")
    return " ".join(value.split())


def _contact_kind(row):
    name = _text(row.get("name")).casefold()
    signal_type = _text(row.get("type")).casefold()
    if row.get("is_station"):
        return "STATION", "accent"
    if "notable stellar phenomena" in name or "stellar phenomena" in name:
        return "PHENOMENA", "green"
    if "megaship" in name or "generation ship" in name:
        return "VESSEL", "yellow"
    if "distress" in name or "mayday" in name:
        return "DISTRESS", "orange"
    if signal_type:
        return signal_type.upper(), "orange" if _integer(row.get("threat")) else "accent"
    if _integer(row.get("threat")):
        return "USS", "orange"
    return "SIGNAL", "muted"


def build_contact_scope_model(system_name, expected, contacts):
    """Return the unique, current-system facts shown by Contact Scope."""
    expected = max(0, _integer(expected))
    rows = []
    for raw in contacts or ():
        if not isinstance(raw, dict):
            continue
        name = _text(raw.get("name")) or "Unidentified signal"
        kind, tone = _contact_kind(raw)
        rows.append({
            "key": str(raw.get("key") or name.casefold()),
            "name": name,
            "kind": kind,
            "tone": tone,
            "threat": max(0, _integer(raw.get("threat"))),
            "expires_at": raw.get("expires_at"),
            "is_station": bool(raw.get("is_station")),
            "faction": _text(raw.get("faction")),
        })
    rows.sort(key=lambda row: (
        row["kind"] not in {"PHENOMENA", "DISTRESS"},
        -row["threat"], row["name"].casefold(),
    ))
    resolved = len(rows)
    total = max(expected, resolved)
    return {
        "system": str(system_name or ""),
        "expected": expected,
        "resolved": resolved,
        "total": total,
        "complete": bool(total and resolved >= total),
        "contacts": rows,
    }


class ContactScopeHUD:
    """Small native proxy and fallback for the semantic HTML contact scope."""

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._html_render_model = None
        self._last_update = None
        self._visible = False
        self._suppressed = False
        self._startup_pending_visible = False
        self._hide_job = None

        self.win = tk.Toplevel(root)
        overlay_bg = overlay_chrome.configure_overlay_window(self.win, _CHROMA)
        self.canvas = tk.Canvas(
            self.win, width=WIDTH, height=120,
            bg=overlay_bg, highlightthickness=0,
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        x = _integer(config.get("contact_scope_hud_x"), 1180)
        y = _integer(config.get("contact_scope_hud_y"), 250)
        self._desired_pos = (x, y)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        self.win.withdraw()

    def update(self, system_name, expected, contacts, *, present=True):
        self._last_update = (system_name, expected, list(contacts or ()))
        model = build_contact_scope_model(system_name, expected, contacts)
        self._html_render_model = model if model["total"] else None
        if not self._html_render_model:
            self.hide()
            return False
        self._redraw(model)
        return self.show() if present else bool(self._visible)

    def clear(self):
        self._last_update = None
        self._html_render_model = None
        self.canvas.delete("all")
        self.hide()

    def show(self):
        if not self._html_render_model or self._suppressed:
            return False
        if bool(getattr(
            self.root, "_voidcompass_startup_presentation_held", False,
        )):
            self._startup_pending_visible = True
            try:
                self.win.withdraw()
                self.win.attributes("-alpha", 0.0)
            except Exception:
                pass
            return False
        if self._visible:
            self._schedule_hide()
            return True
        try:
            x = _integer(self.config.get("contact_scope_hud_x"), 1180)
            y = _integer(self.config.get("contact_scope_hud_y"), 250)
            self._desired_pos = (x, y)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
            self._visible = True
            self._startup_pending_visible = False
            self._schedule_hide()
            return True
        except Exception:
            return False

    def hide(self):
        self._cancel_hide()
        pending = self._startup_pending_visible
        self._startup_pending_visible = False
        if not self._visible:
            return bool(pending)
        try:
            self.win.withdraw()
        except Exception:
            return False
        self._visible = False
        return True

    def _cancel_hide(self):
        if self._hide_job is None:
            return
        try:
            self.win.after_cancel(self._hide_job)
        except Exception:
            pass
        self._hide_job = None

    def _schedule_hide(self):
        self._cancel_hide()
        timeout_s = max(0, _integer(self.config.get("contact_scope_timeout_s"), 45))
        if timeout_s <= 0:
            return False
        try:
            self._hide_job = self.win.after(timeout_s * 1000, self._auto_hide)
            return True
        except Exception:
            self._hide_job = None
            return False

    def _auto_hide(self):
        self._hide_job = None
        self.hide()

    def apply_auto_hide_setting(self):
        """Apply a changed timer without resurrecting an already hidden scope."""
        self._cancel_hide()
        if self._visible:
            self._schedule_hide()
        return True

    def suppress(self):
        self._suppressed = True
        return self.hide()

    def resume(self, refresh=True):
        self._suppressed = False
        if refresh and self._last_update is not None:
            return self.update(*self._last_update)
        return False

    def release_startup_visibility(self):
        if not self._startup_pending_visible:
            return False
        self._startup_pending_visible = False
        return self.show()

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        if self._html_render_model:
            self._redraw(self._html_render_model)

    def _redraw(self, model):
        palette = self._palette
        rows = list(model.get("contacts") or ())[:8]
        height = max(92, 70 + len(rows) * 25)
        self.canvas.config(width=WIDTH, height=height)
        x, y = self._desired_pos
        self.win.geometry(overlay_chrome.position_geometry(x, y, WIDTH, height))
        self.canvas.delete("all")
        overlay_chrome.draw_chrome(
            self.canvas, WIDTH, height, accent=palette["accent"],
            bracket_len=12, scanlines=False,
        )
        self._draw_text(16, 18, "DEEP SPACE CONTACTS", palette["accent"], ("Courier", 11, "bold"))
        self._draw_text(
            WIDTH - 16, 18,
            f'{model.get("resolved", 0)}/{model.get("total", 0)}',
            palette["green"] if model.get("complete") else palette["orange"],
            ("Courier", 10, "bold"), "e",
        )
        self._draw_text(16, 42, str(model.get("system") or "SYSTEM").upper(), palette["muted"], ("Courier", 9, "bold"))
        row_y = 66
        for row in rows:
            tone = palette.get(row.get("tone"), palette["text"])
            self._draw_text(16, row_y, row.get("kind"), tone, ("Courier", 8, "bold"))
            self._draw_text(112, row_y, row.get("name"), palette["text"], ("Courier", 9, "bold"))
            threat = _integer(row.get("threat"))
            if threat:
                self._draw_text(WIDTH - 16, row_y, f"THREAT {threat}", palette["orange"], ("Courier", 8, "bold"), "e")
            row_y += 25

    def _draw_text(self, x, y, value, color, font, anchor="w"):
        font = overlay_chrome.scaled_font(font, self.config)
        self.canvas.create_text(x + 1, y + 1, text=value, fill="#000000", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=value, fill=color, font=font, anchor=anchor)

    def _drag_start(self, event):
        self._dx, self._dy = event.x, event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + event.x - self._dx
        y = self.win.winfo_y() + event.y - self._dy
        self._desired_pos = (x, y)
        self.config["contact_scope_hud_x"] = x
        self.config["contact_scope_hud_y"] = y
        self.win.geometry(overlay_chrome.position_geometry(x, y))

    def _drag_end(self, _event):
        x, y = self.win.winfo_x(), self.win.winfo_y()
        self._desired_pos = (x, y)
        self.config["contact_scope_hud_x"] = x
        self.config["contact_scope_hud_y"] = y
        save_config(self.config)

    def destroy(self):
        self._cancel_hide()
        try:
            self.win.destroy()
        except Exception:
            pass
