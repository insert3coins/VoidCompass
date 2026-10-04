"""Deep Space Contacts overlay (5.5.2.3): shows the model the journal-driven
ContactLedger (exploration.contact_scope) builds for the current system.

This is the window's state; the page draws it (web/contact_scope). It hides
after ``contact_scope_timeout_s`` (0 keeps it up), while docked, and when
there is nothing to show.
"""
from __future__ import annotations

from voidcompass.core import themes
from voidcompass.core.application_runtime import OverlayWindowState
from voidcompass.overlays import overlay_chrome


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


class ContactScopeHUD:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._html_render_model = None
        self._last_model = None
        self._visible = False
        self._suppressed = False
        self._startup_pending_visible = False
        self._hide_job = None
        self.win = OverlayWindowState(root)
        x = _integer(config.get("contact_scope_hud_x"), 1180)
        y = _integer(config.get("contact_scope_hud_y"), 250)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self.win.withdraw()

    def update(self, model, *, present=True):
        self._last_model = model
        self._html_render_model = model or None
        if not self._html_render_model:
            self.hide()
            return False
        return self.show() if present else bool(self._visible)

    def clear(self):
        self._last_model = None
        self._html_render_model = None
        self.hide()

    def show(self):
        if not self._html_render_model or self._suppressed:
            return False
        if bool(getattr(self.root, "_voidcompass_startup_presentation_held", False)):
            self._startup_pending_visible = True
            try:
                self.win.withdraw()
            except Exception:
                pass
            return False
        if self._visible and self.win.state() == "normal":
            self._schedule_hide()
            return True
        try:
            x = _integer(self.config.get("contact_scope_hud_x"), 1180)
            y = _integer(self.config.get("contact_scope_hud_y"), 250)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
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
            self.win.cancel(self._hide_job)
        except Exception:
            pass
        self._hide_job = None

    def _schedule_hide(self):
        self._cancel_hide()
        timeout_s = max(0, _integer(self.config.get("contact_scope_timeout_s"), 45))
        if timeout_s <= 0:
            return False
        try:
            self._hide_job = self.win.call_later(timeout_s * 1000, self._auto_hide)
            return True
        except Exception:
            self._hide_job = None
            return False

    def _auto_hide(self):
        self._hide_job = None
        self.hide()

    def apply_auto_hide_setting(self):
        """Apply a changed timer without resurrecting a hidden scope."""
        self._cancel_hide()
        if self._visible:
            self._schedule_hide()
        return True

    def suppress(self):
        self._suppressed = True
        return self.hide()

    def resume(self, refresh=True):
        self._suppressed = False
        if refresh and self._last_model is not None:
            return self.update(self._last_model)
        return False

    def release_startup_visibility(self):
        if not self._startup_pending_visible:
            return False
        self._startup_pending_visible = False
        return self.show()

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)

    def destroy(self):
        self._cancel_hide()
        try:
            self.win.destroy()
        except Exception:
            pass
