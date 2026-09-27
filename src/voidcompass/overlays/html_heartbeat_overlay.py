"""Dedicated semantic HTML renderer for the journal watcher orb."""

from voidcompass.overlays.heartbeat_hud import orb_size
from voidcompass.overlays.html_model_overlay import (
    HtmlModelOverlayBridge,
    attach_html_model_overlay,
)


class HtmlHeartbeatBridge(HtmlModelOverlayBridge):
    """The orb is a square window of the size chosen in Overlay Studio."""

    def _dimensions(self):
        size = orb_size(self.config)
        return size, size


def attach_html_heartbeat_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    size = orb_size(getattr(overlay, "config", {}))
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_heartbeat_bridge", template="heartbeat",
        snapshot_key="heartbeat", model_attr="_html_render_model",
        log_name="Journal Heartbeat", width=size,
        min_height=size, default_height=size, max_height=size,
        bridge_class=HtmlHeartbeatBridge,
    )
