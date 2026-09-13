"""Invisible native state proxy for the Rhino coverage minimap overlay."""

from __future__ import annotations

from voidcompass.core import themes
from voidcompass.core.application_runtime import OverlayWindowState
from voidcompass.overlays import overlay_chrome


class RhinoMinimapHUD:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._html_render_model = {"active": False, "vehicle": "RHINO"}
        self.win = OverlayWindowState(root)
        x = int(config.get("rhino_minimap_hud_x", 30))
        y = int(config.get("rhino_minimap_hud_y", 80))
        self._desired_pos = (x, y)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self.win.withdraw()

    def update(self, model):
        self._html_render_model = model if isinstance(model, dict) else {"active": False}
        if self._html_render_model.get("active"):
            self.show()
        else:
            self.hide()

    def show(self):
        if not self._html_render_model.get("active"):
            return False
        try:
            x = int(self.config.get("rhino_minimap_hud_x", 30))
            y = int(self.config.get("rhino_minimap_hud_y", 80))
            self._desired_pos = (x, y)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
            return True
        except Exception:
            return False

    def hide(self):
        try:
            self.win.withdraw()
        except Exception:
            pass

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)

