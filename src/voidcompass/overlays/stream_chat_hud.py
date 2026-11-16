"""Stream Chat overlay (5.8.3): your companion's answers to stream chat, the
naming vote running, a banner for raids, subs and promotions, and the end
credits. Shown while stream chat is connected (or the credits roll); the
model is the deck's _stream_overlay_model."""
from __future__ import annotations

from voidcompass.overlays.colony_needs_hud import ColonyNeedsHUD, _integer


class StreamChatHUD(ColonyNeedsHUD):
    """Native window proxy for the semantic HTML Stream Chat page."""

    def _position(self):
        return (_integer(self.config.get("stream_chat_hud_x"), 40),
                _integer(self.config.get("stream_chat_hud_y"), 300))
