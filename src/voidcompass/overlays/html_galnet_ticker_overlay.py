"""Dedicated semantic HTML renderer for the Galnet ticker bar."""

from voidcompass.overlays.galnet_ticker_hud import (
    TICKER_HEIGHT, ticker_crt_level, ticker_options, ticker_text_scale,
)
from voidcompass.overlays.html_model_overlay import (
    HtmlModelOverlayBridge,
    attach_html_model_overlay,
)


class HtmlGalnetTickerBridge(HtmlModelOverlayBridge):
    """The bar is as long as Overlay Studio says; its height follows its text size."""

    def _dimensions(self):
        return ticker_options(self.config)["width"], round(TICKER_HEIGHT * ticker_text_scale(self.config))

    def _snapshot(self):
        # The page sizes its type from effects.text_scale; the ticker can have
        # its own size rather than the one every overlay shares.
        payload = super()._snapshot()
        payload["effects"]["text_scale"] = ticker_text_scale(self.config)
        # Its CRT screen may be its own or follow the shared CRT switch and
        # intensity; the page draws whichever level this resolves to.
        level = ticker_crt_level(self.config)
        payload["effects"]["crt"] = level != "off"
        payload["effects"]["crt_level"] = level
        return payload

    def _quick_fingerprint(self):
        # The shared CRT intensity is not in the base fingerprint, but the
        # ticker follows it by default.
        return super()._quick_fingerprint(), ticker_crt_level(self.config)


def attach_html_galnet_ticker_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    config = getattr(overlay, "config", {})
    width = ticker_options(config)["width"]
    height = round(TICKER_HEIGHT * ticker_text_scale(config))
    return attach_html_model_overlay(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
        bridge_attr="_html_galnet_ticker_bridge", template="galnet_ticker",
        snapshot_key="ticker", model_attr="_html_render_model",
        log_name="Galnet Ticker", width=width,
        min_height=height, default_height=height, max_height=height,
        bridge_class=HtmlGalnetTickerBridge,
    )
