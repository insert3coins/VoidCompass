"""Semantic HTML renderer attachment for the Hatchling overlay."""

from voidcompass.overlays.hatchling_hud import hatchling_pet_window
from voidcompass.overlays.html_jump_info_overlay import HtmlJumpInfoBridge
from voidcompass.overlays.html_model_overlay import attach_html_model_overlay


class HtmlHatchlingBridge(HtmlJumpInfoBridge):
    """The panel sizes itself to its content; the pet on its own (5.6.4) has
    a fixed see-through strip, set by its size and how far it roams."""

    levels = None

    def _dimensions(self):
        window = hatchling_pet_window(self.config)
        return window if window else super()._dimensions()

    def set_enabled(self, enabled):
        # Your music's levels, for its dances (5.6.4), as the music overlay reads them.
        live = super().set_enabled(enabled)
        register = getattr(getattr(self.surface, "server", None), "set_live_provider", None)
        if live and callable(register):
            register(self.overlay_id, lambda: self.levels() if callable(self.levels) else {})
        return live


def attach_html_hatchling_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key, levels=None):
    # The height follows the page: a log line comes and goes under the bars.
    attached = attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_hatchling_bridge", template="hatchling",
        snapshot_key="hatchling", model_attr="_html_render_model",
        log_name="Hatchling", width=250,
        min_height=110, default_height=176, max_height=320,
        bridge_class=HtmlHatchlingBridge,
    )
    bridge = getattr(overlay, "_html_hatchling_bridge", None)
    if bridge is not None:
        bridge.levels = levels
    return attached
