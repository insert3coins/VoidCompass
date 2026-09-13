"""Renderer-neutral cockpit model for Powerplay operations."""

from __future__ import annotations

from voidcompass.core.application_runtime import OverlayWindowState
from voidcompass.overlays import overlay_chrome
from voidcompass.core import themes


def build_powerplay_overlay_model(workspace):
    workspace = workspace if isinstance(workspace, dict) else {}
    power = workspace.get("powerplay") or {}
    location = workspace.get("location") or power.get("location") or {}
    cycle = workspace.get("cycle") or power.get("current_cycle") or {}
    objective = workspace.get("active_objective") or {}
    return {
        "active": bool(power.get("pledged") or objective),
        "pledged": bool(power.get("pledged")),
        "power": str(power.get("power") or "No active pledge"),
        "rank": power.get("rank"),
        "merits": power.get("merits"),
        "cycle_merits": int(cycle.get("merits_gained") or 0),
        "cycle_ends": cycle.get("ends"),
        "system": str(location.get("system") or ""),
        "controlling_power": str(location.get("controlling_power") or ""),
        "system_state": str(location.get("state") or ""),
        "cargo_collected": int(cycle.get("cargo_collected") or 0),
        "cargo_delivered": int(cycle.get("cargo_delivered") or 0),
        "objective": {
            "title": str(objective.get("title") or ""),
            "kind": str(objective.get("kind") or ""),
            "system": str(objective.get("system") or ""),
            "commodity": str(objective.get("commodity") or ""),
            "current": int(objective.get("current") or 0),
            "target": max(1, int(objective.get("target") or 1)),
        } if objective else {},
    }


class PowerplayHUD:
    """Invisible native proxy whose model is drawn by a semantic HTML overlay."""

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._html_render_model = build_powerplay_overlay_model({})
        self.win = OverlayWindowState(root)
        x = int(config.get("powerplay_hud_x", 820))
        y = int(config.get("powerplay_hud_y", 490))
        self._desired_pos = (x, y)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self.win.withdraw()

    def update(self, workspace):
        self._html_render_model = build_powerplay_overlay_model(workspace)
        if self._html_render_model["active"]:
            self.show()
        else:
            self.hide()

    def show(self):
        if not self._html_render_model.get("active"):
            return
        try:
            x = int(self.config.get("powerplay_hud_x", 820))
            y = int(self.config.get("powerplay_hud_y", 490))
            self._desired_pos = (x, y)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
        except Exception:
            pass

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
