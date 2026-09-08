"""GravityWarningHUD — transient warning overlay for high-gravity landable bodies.

Shown when the body the commander is currently approaching (ApproachBody)
has a known surface gravity (from an earlier Scan this session) at or
above a configurable threshold. Auto-hides after a timeout, same pattern
as ProspectorHUD.
"""
from application_runtime import OverlayWindowState
from config import save_config
import overlay_chrome
import themes
_CHROMA = '#ff00ff'

class GravityWarningHUD:
    WIDTH = 300
    HEIGHT = 90

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._hide_job = None
        self._last_body = None
        self._last_gravity = None
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self.win = OverlayWindowState(root)
        screen_w = root.winfo_screenwidth()
        default_x = max(30, screen_w - self.WIDTH - 30)
        x = self._safe_int(config.get('gravity_warning_hud_x'), default_x)
        y = self._safe_int(config.get('gravity_warning_hud_y'), 530)
        self.config['gravity_warning_hud_x'] = x
        self.config['gravity_warning_hud_y'] = y
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self.win.withdraw()

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return int(default)

    def _startup_held(self):
        """Return whether the bootloader still owns the visible cockpit."""
        return bool(getattr(self.root, '_voidcompass_startup_presentation_held', False))

    def show(self):
        if self._startup_held():
            self.hide()
            return False
        try:
            x = self._safe_int(self.config.get('gravity_warning_hud_x'), 30)
            y = self._safe_int(self.config.get('gravity_warning_hud_y'), 30)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
            return True
        except Exception:
            return False

    def hide(self):
        if self._hide_job:
            try:
                self.win.cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None
        try:
            self.win.withdraw()
        except Exception:
            pass

    def _schedule_hide(self):
        if self._hide_job:
            try:
                self.win.cancel(self._hide_job)
            except Exception:
                pass
        timeout_s = max(5, int(self.config.get('gravity_warning_hud_timeout_s') or 20))
        self._hide_job = self.win.call_later(timeout_s * 1000, self._auto_hide)

    def _auto_hide(self):
        self._hide_job = None
        self.hide()

    def _threshold(self):
        try:
            return max(0.5, float(self.config.get('gravity_warning_threshold_g', 3.0) or 3.0))
        except Exception:
            return 3.0

    def check_body(self, body_name, gravity_g):
        """Show/refresh/hide the warning for the currently-approached body.

        Silently does nothing if gravity_g is unknown (body not yet scanned
        this session) — this overlay can only warn about bodies we already
        have data for, same limitation as the local-data-only game state.
        """
        if self._startup_held():
            self.clear()
            return
        if not body_name or gravity_g is None:
            return
        if gravity_g < self._threshold():
            if self._last_body == body_name:
                self.clear()
            return
        if body_name == self._last_body and gravity_g == self._last_gravity:
            if self.show():
                self._schedule_hide()
            return
        self._last_body = body_name
        self._last_gravity = gravity_g
        self._redraw(body_name, gravity_g)
        if self.show():
            self._schedule_hide()

    def clear(self):
        """Called on LeaveBody — drop tracked state and hide immediately."""
        self._last_body = None
        self._last_gravity = None
        self.hide()

    def _redraw(self, body_name, g):
        self._last_body, self._last_gravity = (body_name, g)

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        if self._last_body is not None and self._last_gravity is not None:
            self._redraw(self._last_body, self._last_gravity)
