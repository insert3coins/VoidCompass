"""Trade Route overlay (5.5.2.6): the next step of the trade route you are
following (what to buy or sell, where), hop by hop, with price warnings. It
shows only while a route is followed; the model is trading.route.next_step.
"""
from __future__ import annotations

from voidcompass.overlays.colony_needs_hud import ColonyNeedsHUD, _integer


class TradeRouteHUD(ColonyNeedsHUD):
    """Native window proxy for the semantic HTML Trade Route page; it behaves
    as Construction Needs does (shown while it has a model)."""

    def _position(self):
        return (_integer(self.config.get("trade_route_hud_x"), 1520),
                _integer(self.config.get("trade_route_hud_y"), 480))

    def update_route(self, step):
        return self.update(step)
