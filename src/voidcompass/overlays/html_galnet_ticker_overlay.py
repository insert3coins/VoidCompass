"""Dedicated semantic HTML renderer for the Galnet ticker bar."""

from voidcompass.overlays.galnet_ticker_hud import TICKER_HEIGHT, ticker_options
from voidcompass.overlays.html_model_overlay import (
    HtmlModelOverlayBridge,
    attach_html_model_overlay,
)


def _text_scale(config):
    try:
        percent = int(float((config or {}).get("overlay_text_scale_percent", 100)))
    except (TypeError, ValueError):
        percent = 100
    return max(75, min(200, percent)) / 100.0


class HtmlGalnetTickerBridge(HtmlModelOverlayBridge):
    """The bar is as long as Overlay Studio says; its height follows text size."""

    def _dimensions(self):
        return ticker_options(self.config)["width"], round(TICKER_HEIGHT * _text_scale(self.config))


def attach_html_galnet_ticker_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    config = getattr(overlay, "config", {})
    width = ticker_options(config)["width"]
    height = round(TICKER_HEIGHT * _text_scale(config))
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_galnet_ticker_bridge", template="galnet_ticker",
        snapshot_key="ticker", model_attr="_html_render_model",
        log_name="Galnet Ticker", width=width,
        min_height=height, default_height=height, max_height=height,
        bridge_class=HtmlGalnetTickerBridge,
    )
