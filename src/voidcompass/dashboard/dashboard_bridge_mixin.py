"""The Dashboard as the whole ship (5.7.8): what's happening across everything
you do, led by what you're doing now. Exploring, mining, trading, fighting,
on foot or docked decides which panels lead; a panel appears only when there's
something in it (a mining run, a trade route, a colony site needing goods,
this week's Powerplay, a carrier jump), never as an empty card. The panels
reuse the Navigation HUD's page builders, so the HUD and the deck agree.
"""

from __future__ import annotations

import logging
import math
import time

from voidcompass.core import companions
from voidcompass.overlays.music_player_hud import _track

logger = logging.getLogger(__name__)

# Which panels lead for each activity, first to last; the rest follow.
LEAD = {
    "fighting": ("combat", "crew", "orders"),
    "mining": ("mining", "crew", "orders", "carrier"),
    "trading": ("trade", "station", "crew", "orders"),
    "docked": ("station", "colony", "carrier", "trade", "crew", "orders"),
    "on_foot": ("crew", "orders"),
    "exploring": ("crew", "orders", "expedition"),
}
ACTIVITY_LABELS = {"fighting": "FIGHTING", "mining": "MINING", "trading": "TRADING", "docked": "DOCKED",
                   "on_foot": "ON FOOT", "exploring": "EXPLORING"}


class DashboardBridgeMixin:

    def _bridge_activity(self, facts):
        engine = getattr(self, "specialist_engine", None)
        session = {}
        try:
            session = ((engine.combat_snapshot() or {}).get("session") or {}) if engine is not None and hasattr(engine, "combat_snapshot") else {}
        except Exception:
            session = {}
        if facts.get("target") or session.get("active"):
            return "fighting"
        if facts.get("prospecting"):
            return "mining"
        if getattr(self, "current_on_foot", False):
            return "on_foot"
        if facts.get("trading"):
            return "trading"
        if facts.get("docked"):
            return "docked"
        return "exploring"

    def _bridge_page(self, page):
        try:
            built = self._hud_page_build(page)
        except Exception:
            return None
        if not built or not built.get("blocks"):
            return None
        return {"id": page, "title": built.get("title") or built.get("label") or page.upper(),
                "label": built.get("label") or page.upper(), "blocks": built["blocks"]}

    def _bridge_crew(self):
        identity = companions.identity(self.config)
        name = companions.name(self.config)
        rota = ""
        try:
            status = self._crew_rota_status() if self.config.get("crew_rota") else None
            rota = str((status or {}).get("text") or "")
        except Exception:
            rota = ""
        thought = self._html_watcher_thought() if hasattr(self, "_html_watcher_thought") else {}
        return {"id": "crew", "identity": identity, "name": name, "rota": rota, "thought": thought.get("text") or "",
                "at": thought.get("at")}

    def _bridge_orders(self):
        try:
            model = self._orders_overlay_model()
        except Exception:
            model = None
        if not model or not model.get("items"):
            return None
        items = []
        ledger = getattr(self, "order_ledger", None)
        for item in model["items"][:4]:
            items.append({**{k: item.get(k) for k in ("id", "plot", "tag", "title", "officer_name", "officer", "distance", "progress", "state")},
                          "step": (item.get("steps") or [{}])[0].get("text", "")})
        return {"id": "orders", "items": items}

    def _bridge_small(self):
        small = []
        pad = self._pad_panel() if hasattr(self, "_pad_panel") else None
        if pad:
            small.append({"kind": "pad", "label": f"PAD {pad['pad']}" + (f" · {pad['station']}" if pad.get("station") else ""),
                          "text": pad.get("words") or "", "map": pad.get("map")})
        try:
            galnet = self._html_dashboard_galnet() or {}
            headline = (galnet.get("articles") or [{}])[0] if isinstance(galnet, dict) else {}
            if headline and headline.get("title"):
                small.append({"kind": "galnet", "label": "GALNET", "text": str(headline["title"])[:160]})
        except Exception:
            pass
        try:
            days = self._on_this_day() or []
            if days:
                day = days[0]
                text = day.get("text") or f"{day.get('years_ago', '')} years ago today: {day.get('system') or ''}"
                small.append({"kind": "on_this_day", "label": "ON THIS DAY", "text": str(text)[:160]})
        except Exception:
            pass
        try:
            sealed = [row for row in self.capsule_store().rows() if not row.get("opened_at")]
            here = str(getattr(self, "current_sys", "") or "").casefold()
            nxt = ""
            manager = getattr(self, "waypoint_manager", None)
            if manager is not None:
                nxt = str(manager.get_next_waypoint(getattr(self, "current_sys", "")) or "").casefold()
            waiting = [row for row in sealed if str(row.get("system") or "").casefold() in (here, nxt)]
            if waiting:
                small.append({"kind": "capsule", "label": "TIME CAPSULE", "text": f"A capsule waits in {waiting[0]['system']}."})
            elif sealed:
                small.append({"kind": "capsule", "label": "TIME CAPSULES", "text": f"{len(sealed)} sealed, waiting for you somewhere."})
        except Exception:
            pass
        try:
            now = self._bridge_now_playing()
            if now.get("state") == "playing":
                small.append({"kind": "music", "label": "NOW PLAYING", "text": f"{now.get('title')}{' · ' + now['artist'] if now.get('artist') else ''}"})
        except Exception:
            pass
        return small

    def _bridge_now_playing(self):
        status = getattr(self, "_music_status", None) or {}
        library = self.music_library() if callable(getattr(self, "music_library", None)) else None
        track = _track(library, status.get("track_id"))
        if track is None:
            return {"state": "idle"}
        return {"state": "playing" if status.get("playing") else "paused",
                "title": track["title"], "artist": track["artist"]}

    def _html_dashboard_activity(self):
        """The Dashboard's panels, in the order what you're doing now wants them."""
        try:
            facts = self._hud_pages_facts()
        except Exception:
            facts = {}
        activity = self._bridge_activity(facts)
        panels = {}
        crew = self._bridge_crew()
        if crew.get("thought") or crew.get("rota"):
            panels["crew"] = crew
        orders = self._bridge_orders()
        if orders:
            panels["orders"] = orders
        wanted = {"mining": facts.get("prospecting"), "combat": activity == "fighting", "station": facts.get("docked"),
                  "colony": facts.get("at_colony"), "trade": facts.get("trading"), "expedition": facts.get("expedition")}
        carrier = getattr(getattr(self, "carrier_tracker", None), "carrier_data", None) or {}
        wanted["carrier"] = str(carrier.get("status") or "") in ("jumping", "cooldown") or facts.get("on_own_carrier")
        try:
            from voidcompass.overlays.powerplay_hud import build_powerplay_overlay_model
            pp = build_powerplay_overlay_model(self._html_powerplay_workspace())
            wanted["powerplay"] = bool(pp.get("pledged") and pp.get("cycle_merits"))
        except Exception:
            wanted["powerplay"] = False
        for page, show in wanted.items():
            if show:
                built = self._bridge_page(page)
                if built:
                    panels[page] = built
        lead = LEAD.get(activity, ())
        order = [page for page in lead if page in panels] + [page for page in panels if page not in lead]
        return {"activity": activity, "label": ACTIVITY_LABELS[activity], "order": order,
                "panels": [panels[page] for page in order], "small": self._bridge_small()}
