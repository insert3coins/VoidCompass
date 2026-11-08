"""Crew Orders overlay (5.7.7): the order waiting for your answer, or the
one you're on, in the cockpit. Shown only while there is one; the model is
the deck's _orders_overlay_model.
"""
from __future__ import annotations

from voidcompass.overlays.colony_needs_hud import ColonyNeedsHUD, _integer


class OrdersHUD(ColonyNeedsHUD):
    """Native window proxy for the semantic HTML Crew Orders overlay page; it behaves
    as Construction Needs does (shown while it has a model)."""

    def _position(self):
        return (_integer(self.config.get("orders_hud_x"), 1520),
                _integer(self.config.get("orders_hud_y"), 640))

    def update_orders(self, model):
        return self.update(model)
