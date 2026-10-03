"""Construction Needs overlay (5.5.2): what a colonisation project still
needs, against what is in the hold and on linked fleet carriers. After
SrvSurvey's build commodities panel; the model is colonisation.views.
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


class ColonyNeedsHUD:
    """Native window proxy for the semantic HTML Construction Needs page."""

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._html_render_model = None
        self._visible = False
        self._startup_pending_visible = False
        self.win = OverlayWindowState(root)
        self.win.geometry(overlay_chrome.position_geometry(*self._position()))
        self.win.withdraw()

    def _position(self):
        return (_integer(self.config.get("colony_needs_hud_x"), 1520),
                _integer(self.config.get("colony_needs_hud_y"), 120))

    @property
    def visible(self):
        return bool(self._visible)

    def update(self, model):
        self._html_render_model = model or None
        return self.show() if self._html_render_model else self.hide()

    def clear(self):
        self._html_render_model = None
        return self.hide()

    def show(self):
        if not self._html_render_model:
            return False
        if bool(getattr(self.root, "_voidcompass_startup_presentation_held", False)):
            self._startup_pending_visible = True
            try:
                self.win.withdraw()
            except Exception:
                pass
            return False
        if self._visible:
            return True
        try:
            self.win.geometry(overlay_chrome.position_geometry(*self._position()))
            self.win.deiconify()
            self._visible = True
            self._startup_pending_visible = False
            return True
        except Exception:
            return False

    def hide(self):
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

    def release_startup_visibility(self):
        if not self._startup_pending_visible:
            return False
        self._startup_pending_visible = False
        return self.show()

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass
