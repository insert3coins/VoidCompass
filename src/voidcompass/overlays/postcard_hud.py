"""Postcards overlay (5.5.3.7): the native window proxy for web/postcards.

Shown when a card arrives (a screenshot taken in game), hidden again after
Overlay Studio's hold time. Screenshots taken in a run stack, newest on top;
their photos are kept in memory (a small JPEG each) and served to the page
by id.
"""
from __future__ import annotations

import time

from voidcompass.overlays.colony_needs_hud import ColonyNeedsHUD, _integer
from voidcompass.overlays.postcards import MAX_STACK, STACK_S, postcard_options


class PostcardHUD(ColonyNeedsHUD):
    """Behaves as Construction Needs does (shown while it has a model), with
    a timer that puts the cards away."""

    def __init__(self, root, config):
        self._cards = []
        self._photos = {}
        self._hide_job = None
        self._last_at = 0.0
        super().__init__(root, config)

    def _position(self):
        return (_integer(self.config.get("postcard_hud_x"), 1700),
                _integer(self.config.get("postcard_hud_y"), 640))

    def _model(self):
        if not self._cards:
            return None
        return {"cards": [dict(card) for card in self._cards], "options": postcard_options(self.config)}

    def post(self, card, now=None):
        """A new card: on top of the stack if the last one was recent."""
        now = time.time() if now is None else now
        if now - self._last_at > STACK_S:
            self._cards = []
        self._last_at = now
        self._cards = [dict(card)] + self._cards[:MAX_STACK - 1]
        keep = {item["id"] for item in self._cards}
        self._photos = {key: value for key, value in self._photos.items() if key in keep}
        self.update(self._model())
        self._schedule_hide()
        return True

    def attach_photo(self, card_id, jpeg):
        """The picture for a card, once it's been read and shrunk."""
        for card in self._cards:
            if card["id"] == card_id:
                self._photos[card_id] = bytes(jpeg)
                card["photo"] = True
                self.update(self._model())
                # It stays a little longer once the picture is in.
                self._schedule_hide(minimum=6)
                return True
        return False

    def photo(self, card_id):
        return self._photos.get(str(card_id))

    def _schedule_hide(self, minimum=0):
        if self._hide_job is not None:
            try:
                self.win.cancel(self._hide_job)
            except Exception:
                pass
        hold = max(postcard_options(self.config)["hold"], minimum)
        try:
            self._hide_job = self.win.call_later(int(hold * 1000), self.put_away)
        except Exception:
            self._hide_job = None

    def put_away(self):
        """The hold time is up: the cards go (the next screenshot starts a
        new stack only after a while, so a quick series still stacks)."""
        self._hide_job = None
        self.update(None)

    def apply_settings(self):
        """Overlay Studio changed the hold, photo or size."""
        if self._cards and self.visible:
            self.update(self._model())

    def destroy(self):
        if self._hide_job is not None:
            try:
                self.win.cancel(self._hide_job)
            except Exception:
                pass
        super().destroy()
