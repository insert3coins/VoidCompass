"""Navigation HUD adapter for the shared HTML overlay runtime."""

from html_overlay_runtime import HtmlOverlaySurface


class HtmlNavigationHudBridge(HtmlOverlaySurface):
    def __init__(self, root, _config=None):
        super().__init__(
            root,
            "navigation",
            template="navigation",
            title="Void Compass Navigation HUD",
        )
