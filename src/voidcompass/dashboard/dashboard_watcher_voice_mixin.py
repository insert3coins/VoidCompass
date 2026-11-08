"""The Watcher's voice and its settings page (5.5.4), for MainDashboard.

The voice is Piper with the HAL model, downloaded on first use. Its switch,
download, test and settings live on the Watcher page, with the Watcher's
thought settings (moved there from Overlay Studio).
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import time

from voidcompass.core import companion_features, crew_rota, home_anchor, ranks, companions
from voidcompass.core.overlay_registry import OVERLAY_SPECS
from voidcompass.exploration import codex_index
from voidcompass.exploration.galactic_regions import region_names
from voidcompass.core.ship_names import ship_name
from voidcompass.core.watcher_retirement import retired_speech
from voidcompass.mining.planet_materials import PlanetMaterialsStore
from voidcompass.mining.rhino_intelligence import rhino_forecast, surface_distance_m
from voidcompass.overlays import (
    watcher_copilot, watcher_habits, watcher_mind, watcher_name, watcher_voice_lore,
)
from voidcompass.services import spansh
from voidcompass.trading import market as trade_market
from voidcompass.trading.commodities import symbol
from voidcompass.overlays.heartbeat_hud import HEARTBEAT_TEXT_SIZES, heartbeat_text_size, thought_side_setting
from voidcompass.voice import voice_assets
from voidcompass.voice.watcher_voice import LEVELS, SPEEDS, WatcherSpeaker

# The Watcher's thought settings, now on its own page: select values go
# through Overlay Studio's checks, switches through its toggles.
WATCHER_SELECTS = (
    "heartbeat_thoughts", "heartbeat_personality", "heartbeat_thought_side", "heartbeat_text_scale_percent",
    "heartbeat_thought_colour", "heartbeat_thought_size", "heartbeat_thought_hold",
)
WATCHER_SWITCHES = ("heartbeat_thought_backdrop", "heartbeat_thought_heading")
TEST_LINE = "This is my voice, Commander. I can hear you. Well. I can hear the ship."
# The lookups that need what you asked: the world you name, the material you name.
ASKS_THE_QUESTION = {"life", "planet", "materials", "codex", "world", "record", "cargo", "market", "engineers"}
# The nearest station with a service: this many results asked of Spansh, the
# carriers among them dropped unless you asked for one.
STATION_SEARCH_SIZE = 8
# Short names commanders use for commodities.
COMMODITY_ALIASES = {"ltd": "Low Temperature Diamonds", "ltds": "Low Temperature Diamonds",
                     "vo": "Void Opal", "vos": "Void Opal"}
# "Where are the sites?" wants the sites first, not the crust's makeup.
SITES_ASKED = re.compile(r"\b(sites?|rigs?|deposits?|drill\w*|where)\b", re.I)


def _asked_words(question):
    """What you asked, lower case and padded, its punctuation gone: "on
    Colonia 4?" names Colonia 4 (the question mark hid it)."""
    return f" {' '.join(re.sub(r'[?!.,;:]+', ' ', str(question or '').casefold()).split())} "



def _rota_of(deck):
    rota = getattr(deck, "_crew_rota", None)
    if rota is None:
        rota = deck._crew_rota = crew_rota.Rota()
    return rota


class DashboardWatcherVoiceMixin:
    # -- the speaker ---------------------------------------------------------
    def _watcher_speaker(self):
        speaker = getattr(self, "_watcher_voice", None)
        if speaker is None:
            speaker = WatcherSpeaker(settings=lambda: companions.settings(self.config), on_change=self._watcher_voice_changed)
            self._watcher_voice = speaker
        return speaker

    def _watcher_voice_on(self):
        return not companions.overlay_only(self.config) and bool(companions.settings(self.config).get("watcher_voice_enabled")) and self._companion_voice_installed()

    def _crewmate_voice_on(self, selected):
        if selected not in companions.IDENTITIES or companions.overlay_only(selected):
            return False
        installed = voice_assets.installed(model=selected) if selected != "watcher" else voice_assets.installed()
        return bool(companions.settings(self.config, selected).get("watcher_voice_enabled")) and installed

    def _companion_voice_installed(self):
        selected = companions.identity(self.config)
        if companions.overlay_only(selected):
            return False
        return voice_assets.installed(model=selected) if selected != "watcher" else voice_assets.installed()

    def _companion_switch(self, selected, by_rota=False):
        previous = companions.identity(self.config)
        done = self._companion_switch_inner(selected)
        if done and not by_rota and previous != selected:
            # 5.7.6: your own choice holds the watch before the rota takes over again.
            _rota_of(self).hold(time.time())
        if done and hasattr(self, "_stamp_session_companion"):
            self._stamp_session_companion(switched=True)
        hud = getattr(self, "heartbeat_hud", None)
        if done and previous != selected and hud is not None and hasattr(hud, "note"):
            # 5.7.4: the incoming companion takes the watch from the last one by name.
            try:
                hud.note("crew_handover", {"previous": previous})
            except Exception:
                logging.debug("Crew handover skipped", exc_info=True)
        return done

    def _crew_rota_state(self):
        return _rota_of(self)

    def _crew_rota_schedule(self):
        """While the rota is on, it looks again every few seconds: docked and
        idle, Status.json may not change for minutes, and the watch never
        changed (5.7.6)."""
        if getattr(self, "_crew_rota_job", None) is not None or not self.config.get("crew_rota"):
            return
        call_later = getattr(getattr(self, "root", None), "call_later", None)
        if not callable(call_later):
            return

        def look():
            self._crew_rota_job = None
            try:
                self._crew_rota_tick()
            except Exception:
                logging.debug("Watch rota skipped", exc_info=True)
            self._crew_rota_schedule()

        try:
            self._crew_rota_job = call_later(int(crew_rota.TICK_S * 1000), look)
        except Exception:
            self._crew_rota_job = None

    def _crew_rota_status(self, now=None, facts=None):
        """5.7.7: what the rota is doing, for the companion page."""
        now = time.time() if now is None else now
        return self._crew_rota_state().status(facts or self._crew_rota_facts(), now, companions.identity(self.config),
                                              enabled=bool(self.config.get("crew_rota")),
                                              rota_duties=crew_rota.duties(self.config))

    def _crew_rota_facts(self):
        mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
        try:
            home_ly = home_anchor.distance(getattr(self, "current_coords", None), self.config)
        except Exception:
            home_ly = None
        return {"docked": bool(getattr(self, "current_docked", False)), "gui_focus": getattr(self, "current_gui_focus", None),
                "on_planet": bool(getattr(self, "on_planet", False)), "on_foot": bool(getattr(self, "current_on_foot", False)),
                "in_srv": bool(getattr(self, "current_in_srv", False)), "route_left": getattr(mind, "_route_left", None),
                "home_ly": home_ly, "deep_ly": crew_rota.deep_ly(self.config)}

    def _crew_rota_tick(self, now=None):
        """5.7.6: with the watch rota on, the companion follows what you're
        doing (crew_rota.py). Runs on each Status.json update."""
        if not self.config.get("crew_rota") or getattr(self, "heartbeat_hud", None) is None:
            return None
        self._crew_rota_schedule()
        now = time.time() if now is None else now
        facts = self._crew_rota_facts()
        target = self._crew_rota_state().step(facts, now, companions.identity(self.config),
                                              rota_duties=crew_rota.duties(self.config))
        # 5.7.7: each decision, for the live debugger: duty, who's wanted, and why not yet.
        logging.debug("Watch rota: %s", self._crew_rota_status(now, facts))
        if target and self._companion_switch(target, by_rota=True):
            return target
        return None

    def _companion_switch_inner(self, selected):
        if selected not in companions.IDENTITIES:
            return False
        if selected == companions.identity(self.config):
            return True
        download = getattr(self, "_watcher_voice_download", None)
        if download is not None and download.running():
            return False
        self._companion_generation = getattr(self, "_companion_generation", 0) + 1
        speaker = getattr(self, "_watcher_voice", None)
        if speaker is not None:
            speaker.close()
            self._watcher_voice = None
        listener = getattr(self, "_watcher_listen", None)
        if listener is not None:
            listener.close()
            self._watcher_listen = None
        # The newcomer keeps the shared Studio settings (size, motion, focus, liveliness); colour stays its own.
        self.config.update(companions.shared_look(self.config))
        self._companion_first_pace(selected)
        self.config["companion_identity"] = selected
        self._watcher_voice_download = None
        hud = getattr(self, "heartbeat_hud", None)
        if hud is not None:
            generation = self._companion_generation
            hud._check_profile()
            if self._companion_generation == generation:
                self._watcher_voice_attach(hud)
            hud._redraw()
            bridge = getattr(hud, "_html_heartbeat_bridge", None)
            if bridge is not None and callable(getattr(bridge, "sync_window", None)):
                bridge.sync_window()
        self._persist_config()
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _companion_first_pace(self, selected):
        """5.7.4: a companion's first watch starts at the Watcher's Thoughts
        pace rather than a fixed default. Later changes are its own."""
        if selected == "watcher" or companions.overlay_only(selected):
            return
        from voidcompass.overlays import heartbeat_hud
        try:
            path = heartbeat_hud._memory_path({**self.config, "companion_identity": selected})
            if path is None or os.path.exists(path):
                return
        except Exception:
            return
        pace = str(self.config.get("heartbeat_thoughts") or "").casefold()
        if pace in {"off", "rare", "occasional", "chatty"}:
            self.config[f"{selected}_thoughts"] = pace

    def _watcher_voice_attach(self, hud):
        """A new Watcher orb: attach its speaker and the ship's plain answers."""
        if hud is None:
            return
        hud.companion_listener = self._companion_profile_changed
        hud.voice_listener = self._watcher_voice_say
        hud.voice_status_listener = self._watcher_voice_status
        self._watcher_voice_sync()
        if self.config.get("watcher_listen_enabled") and not companions.overlay_only(self.config):
            self._watcher_listener().warm()
        mind = getattr(hud, "mind", None)
        if mind is not None:
            mind.lookup_provider = self._watcher_lookup
            mind.action_provider = self._watcher_mind_action

    def _companion_profile_changed(self):
        self._companion_generation = getattr(self, "_companion_generation", 0) + 1
        speaker = getattr(self, "_watcher_voice", None)
        if speaker is not None:
            speaker.close()
            self._watcher_voice = None
        listener = getattr(self, "_watcher_listen", None)
        if listener is not None:
            listener.close()
            self._watcher_listen = None
        download = getattr(self, "_watcher_voice_download", None)
        if download is not None:
            download.cancel()
            self._watcher_voice_download = None
        hud = getattr(self, "heartbeat_hud", None)
        if hud is not None:
            self._watcher_voice_attach(hud)

    def _watcher_voice_say(self, words, key=None, feel=None):
        if (getattr(self, "_closing", False) or self._watcher_voice_boot_held()
                or not self._watcher_voice_on() or self._watcher_voice_hushed()):
            return False
        # 5.7.4: a crewmate off watch speaks in its own voice, or not at all.
        crewmate = (feel or {}).get("voice") if isinstance(feel, dict) else None
        if crewmate and crewmate != companions.identity(self.config) and not self._crewmate_voice_on(crewmate):
            return False
        said = self._watcher_speaker().say(words, key, feel=feel)
        if said and hasattr(self, "_api_publish"):
            self._voice_from = "api" if str(key or "").startswith("api-") else "watcher"
            self._api_publish("voice", {"state": "started", "text": words, "from": self._voice_from,
                                         "companion": companions.identity(self.config)})
        return said

    def _watcher_voice_boot_held(self):
        root = getattr(self, "root", None)
        return bool(
            getattr(self, "_startup_presentation_held", False)
            or getattr(root, "_voidcompass_startup_presentation_held", False)
            or getattr(root, "_voidcompass_startup_splash", None) is not None
            or getattr(self, "_startup_overlay_handoff_pending", None) is not None
        )

    def _watcher_voice_status(self, key):
        speaker = getattr(self, "_watcher_voice", None)
        return speaker.status(key) if speaker is not None else "cancelled"

    # -- hush (5.6.1): another app's voice asks it to keep quiet ------------------
    def _watcher_voice_hushed(self):
        return float(getattr(self, "_voice_hush_until", 0.0) or 0.0) > time.time()

    def _watcher_voice_hush(self, seconds=None):
        """Quiet now and for ``seconds`` (None: until lifted; 0 lifts it).
        Thoughts still show beside the orb; they just aren't said."""
        if seconds is not None and seconds <= 0:
            self._voice_hush_until = 0.0
            return
        self._voice_hush_until = math.inf if seconds is None else time.time() + float(seconds)
        speaker = getattr(self, "_watcher_voice", None)
        if speaker is not None:
            self._voice_stop_reason = "hushed"
            speaker.stop()

    def _watcher_voice_hush_left(self):
        """Seconds of hush left: 0 when not hushed, None until lifted."""
        until = float(getattr(self, "_voice_hush_until", 0.0) or 0.0)
        if until == math.inf:
            return None
        return max(0, round(until - time.time()))

    def _watcher_voice_changed(self):
        """The speaker started or stopped (any thread). A line ending goes out
        on the API as a voice event: finished, stopped or hushed."""
        speaker = getattr(self, "_watcher_voice", None)
        speaking = speaker is not None and speaker.live() is not None
        was = bool(getattr(self, "_voice_speaking", False))
        self._voice_speaking = speaking
        hud = getattr(self, "heartbeat_hud", None)
        post = getattr(self, "_ui_post", None)
        if hud is not None and callable(post):
            post(hud._redraw)
        if was and not speaking:
            reason = getattr(self, "_voice_stop_reason", "") or "finished"
            self._voice_stop_reason = ""
            if hasattr(self, "_api_publish"):
                self._api_publish("voice", {"state": reason, "from": getattr(self, "_voice_from", "watcher"),
                                             "companion": companions.identity(self.config)})

    def _watcher_voice_sync(self):
        """Voice on and downloaded: warm it and tell the orb. Otherwise hush."""
        on = self._watcher_voice_on()
        hud = getattr(self, "heartbeat_hud", None)
        if hud is not None and hasattr(hud, "set_voice_active"):
            hud.set_voice_active(on and not self._watcher_voice_boot_held())
        speaker = getattr(self, "_watcher_voice", None)
        if on:
            self._watcher_speaker().warm()
        elif speaker is not None:
            speaker.stop()
            speaker._stop_engine()

    def _watcher_live_levels(self):
        """The orb's live feed: the Music player's levels and its own voice."""
        levels = dict(self.music_levels() or {})
        speaker = getattr(self, "_watcher_voice", None)
        levels["speech"] = speaker.live() if speaker is not None else None
        # 5.7.1: listening to you, or working out what you said.
        levels["hearing"] = self._watcher_listen_live()
        mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
        levels["working"] = bool(mind is not None and getattr(mind, "talk_waiting", lambda: False)())
        levels["identity"] = companions.identity(self.config)
        levels["generation"] = getattr(self, "_companion_generation", 0)
        model = getattr(getattr(self, "heartbeat_hud", None), "_html_render_model", None)
        thought = model.get("thought") if isinstance(model, dict) else None
        levels["thought"] = dict(thought) if isinstance(thought, dict) else None
        return levels

    def _watcher_voice_close(self):
        """Stop the voice, hearing and any voice download on app shutdown."""
        download = getattr(self, "_watcher_voice_download", None)
        if download is not None:
            download.cancel()
        speaker = getattr(self, "_watcher_voice", None)
        if speaker is not None:
            speaker.close()
        self._watcher_listen_close()

    # -- plain answers --------------------------------------------------------

    def _watcher_lookup(self, question):
        """What the ship's systems show about what you asked it (5.7.1): only
        the systems the question is about, each as plain lines of fact."""
        lines = []
        topics = watcher_copilot.topics_for(question)
        # "What's my tritium worth?": a commodity you're carrying, and its value.
        if "cargo" not in topics and watcher_copilot.VALUE_ASKED.search(str(question or "")):
            words = _asked_words(question)
            held = {str(row.get("Name_Localised") or row.get("Name") or "").casefold()
                    for row in getattr(self, "current_cargo_inventory", None) or () if isinstance(row, dict)}
            if any(name and f" {name}" in words for name in held):
                topics.append("cargo")
        # "What's gold going for?": a commodity named with a price word.
        if "market" not in topics and "data" not in topics and watcher_copilot.VALUE_ASKED.search(str(question or "")):
            if self._watcher_commodities_named(question, self._watcher_market_file().get("items") or ()):
                topics.append("market")
        # 5.7.6: "How much arsenic do I have?": a material you hold, by name.
        if "materials" not in topics and "planet" not in topics and not watcher_copilot._SOMEWHERE.search(str(question or "")):
            stock = getattr(self, "engineer_materials", None) or {}
            words = _asked_words(question)
            held = {str(entry.get("name") or "").casefold() for kind in ("raw", "manufactured", "encoded")
                    for entry in (stock.get(kind) or {}).values() if isinstance(entry, dict)}
            if any(name and f" {name} " in words for name in held):
                topics.append("materials")
        # 5.7.6: "What rank am I with Farseer?": an engineer you know, by name.
        if "engineers" not in topics:
            known = ((getattr(self, "engineer_materials", None) or {}).get("engineers") or {})
            words = _asked_words(question)
            if any(len(part) > 3 and f" {part} " in words for name in known for part in str(name).casefold().split()):
                topics.append("engineers")
        for topic in topics:
            try:
                lookup = getattr(self, f"_watcher_lookup_{topic}")
                lines += lookup(question) if topic in ASKS_THE_QUESTION else lookup()
            except Exception:
                logging.debug("Watcher lookup %s skipped", topic, exc_info=True)
        return lines[:watcher_copilot.LOOKUP_LIMIT]

    def _watcher_lookup_where(self):
        docked = bool(getattr(self, "current_docked", False))
        return watcher_copilot.where_lines(str(getattr(self, "current_sys", "") or ""),
                                           str(getattr(self, "current_station_name", "") or "") if docked else "",
                                           str(getattr(self, "current_body_name", "") or ""))

    def _watcher_lookup_route(self):
        return watcher_copilot.route_lines(self._build_navigation_hud_context())

    def _watcher_lookup_survey(self):
        return watcher_copilot.survey_lines(
            str(getattr(self, "current_sys", "") or ""), getattr(self, "scanned", 0), getattr(self, "total", 0),
            getattr(self, "system_bio_signals", 0), getattr(self, "organic_count", 0),
            len(getattr(self, "valuable_bodies", None) or ()), bool(getattr(self, "system_undiscovered", False)),
            len(getattr(self, "body_dss_complete", None) or ()))

    def _watcher_lookup_ship(self):
        ship = getattr(self, "cmdr_ship", None) or {}
        tons = int(getattr(self, "current_cargo_tons", 0) or 0)
        return watcher_copilot.ship_lines(
            ship_name(ship.get("ship"), ship.get("ship_localised")), str(ship.get("ship_name") or ""), self._expedition_jump_range(),
            self._current_fuel_percent(), tons, self._active_cargo_capacity(),
            self._format_hud_credits(self._latest_hud_balance()) if self._latest_hud_balance() is not None else "",
            getattr(self, "current_hull_percent", None),
            ((getattr(self, "companion_state", None) or {}).get("loadout") or {}).get("Rebuy") or ship.get("rebuy"),
            getattr(self, "current_legal_state", "") or "")

    def _watcher_lookup_cargo(self, question=""):
        hold = str(getattr(self, "current_cargo_vessel", "Ship") or "Ship")
        capacity = self._active_cargo_capacity() if hold.casefold() == "ship" else 0
        lines = watcher_copilot.cargo_lines(getattr(self, "current_cargo_inventory", None) or [], capacity, hold)
        if watcher_copilot.VALUE_ASKED.search(str(question or "")):
            # Asked what it's worth: the value first, then what's in the hold.
            lines = self._watcher_cargo_value() + lines[1:]
        return lines

    def _watcher_market_file(self):
        """The game's Market.json (the last commodity market opened): its
        station, its items by symbol, and how old it is."""
        journal_path = self.config.get("journal_path") or getattr(getattr(self, "watcher", None), "journal_path", None)
        try:
            with open(os.path.join(str(journal_path or ""), "Market.json"), "r", encoding="utf-8") as handle:
                market = json.load(handle)
        except (OSError, ValueError):
            return {}
        if not isinstance(market, dict):
            return {}
        names = getattr(self, "trading_names", None)
        items = []
        for item in market.get("Items") or ():
            if not isinstance(item, dict) or not item.get("Name"):
                continue
            key = symbol(item.get("Name"))
            name = str(item.get("Name_Localised") or (names.name(item.get("Name")) if names else key) or key)
            items.append({"symbol": key, "name": name, "buy": int(item.get("BuyPrice") or 0),
                          "sell": int(item.get("SellPrice") or 0), "mean": int(item.get("MeanPrice") or 0),
                          "stock": int(item.get("Stock") or 0), "demand": int(item.get("Demand") or 0)})
        docked = bool(getattr(self, "current_docked", False) and market.get("MarketID")
                      and market.get("MarketID") == getattr(self, "current_station_market_id", None))
        return {"station": str(market.get("StationName") or ""), "items": items, "docked": docked,
                "timestamp": market.get("timestamp")}

    def _watcher_commodities_named(self, question, items=()):
        """The commodities your words name, as (symbol, name), longest first:
        from the last market's list and every name the Trading page knows."""
        words = _asked_words(question)
        known = {row["name"]: row["symbol"] for row in items or ()}
        names = getattr(self, "trading_names", None)
        if names is not None:
            for name in names.all_names():
                known.setdefault(name, symbol(name))
        for alias, name in COMMODITY_ALIASES.items():
            if f" {alias} " in words:
                words += f" {name.casefold()} "
        found, taken = [], set()
        for name in sorted(known, key=len, reverse=True):
            folded = name.casefold()
            if len(folded) > 2 and f" {folded}" in words and not any(folded in other for other in taken):
                found.append((known[name], name))
                taken.add(folded)
        return found[:3]

    def _watcher_lookup_market(self, question=""):
        """Commodity prices: the market you're at or last opened, the galactic
        averages, and Spansh's best prices (fetched once a session, never waited on)."""
        market = self._watcher_market_file()
        items = market.get("items") or []
        asked = self._watcher_commodities_named(question, items)
        ranges = getattr(self, "_trading_price_ranges", None)
        fetching = False
        if asked and ranges is None and self._trading_online():
            self._trading_warm_up()
            fetching = True
        best = {name: ((ranges or {}).get(name) or {}) for _key, name in asked}
        best = {name: (row.get("buy_min"), row.get("sell_max")) for name, row in best.items() if row}
        age = time.time() - watcher_copilot._when(market.get("timestamp")) if market.get("timestamp") else None
        return watcher_copilot.market_lines(market.get("station") or "", items, asked, market.get("docked"), age,
                                            best, fetching)

    def _watcher_cargo_value(self):
        """The hold priced (5.7.2): Market.json gives the docked station's own
        prices and the galactic average for what it lists; the trade store,
        what you paid; Spansh's best prices, only if already fetched."""
        held = self._trading_cargo()
        market = self._watcher_market_file()
        items = market.get("items") or []
        averages = {row["symbol"]: row["mean"] for row in items if row["mean"]}
        station, here = "", {}
        if market.get("docked"):
            station = market.get("station") or ""
            here = {row["symbol"]: row["sell"] for row in items if row["sell"] > 0}
        ranges = getattr(self, "_trading_price_ranges", None) or {}
        best = {row["symbol"]: (ranges.get(row["name"]) or {}).get("sell_max") for row in held
                if (ranges.get(row["name"]) or {}).get("sell_max")}
        paid = {row["symbol"]: price for row in held if (price := self._watcher_paid(row["symbol"], row["count"]))}
        return watcher_copilot.cargo_value_lines(held, station, here, averages, best, paid)

    def _watcher_paid(self, commodity, count):
        """What you paid a tonne for what you hold: your buys since you last
        sold it (mined or salvaged cargo cost nothing, and gets no price)."""
        store = getattr(self, "trading_store", None)
        if store is None or count <= 0:
            return None
        try:
            rows = store.query("SELECT kind, count, price FROM trades WHERE commodity = ? ORDER BY ts DESC LIMIT 40",
                               (commodity,))
        except Exception:
            return None
        bought = spent = 0
        for row in rows:
            if row["kind"] != "buy" or bought >= count:
                break
            take = min(int(row["count"] or 0), count - bought)
            bought += take
            spent += take * int(row["price"] or 0)
        return round(spent / bought) if bought else None

    def _watcher_lookup_station(self):
        if not getattr(self, "current_docked", False):
            return watcher_copilot.station_lines("")
        faction = getattr(self, "current_station_faction", None) or {}
        return watcher_copilot.station_lines(
            str(getattr(self, "current_station_name", "") or ""), getattr(self, "current_station_type", "") or "",
            str(getattr(self, "current_sys", "") or ""), faction.get("name") or "", faction.get("state") or "",
            getattr(self, "current_station_government", "") or "", getattr(self, "current_station_allegiance", "") or "",
            getattr(self, "current_station_economy", "") or "", getattr(self, "current_station_services", None) or (),
            getattr(self, "current_station_landing_pads", None), getattr(self, "current_station_dist_ls", None))

    def _watcher_lookup_factions(self):
        store = getattr(self, "bgs_store", None)
        address = getattr(self, "current_system_address", None)
        snap = store.latest_snapshot(address) if store is not None and address is not None else None
        return watcher_copilot.faction_lines(snap, str(getattr(self, "current_sys", "") or ""), now=time.time())

    def _watcher_lookup_planet(self, question=""):
        """The planet you're at (or name), its scan's materials, what its ground
        tends to hold and your saved mining sites and rigs on it (5.7.2)."""
        workspace = self._html_planet_materials_workspace()
        system = str(workspace.get("system") or "")
        bodies = [row for row in workspace.get("bodies") or () if isinstance(row, dict)]
        words = _asked_words(question)
        named = next((row for row in sorted(bodies, key=lambda row: -len(str(row.get("body") or "")))
                      if f" {str(row.get('body') or '').casefold()} " in words
                      or (row.get("short_name") and f" {str(row['short_name']).casefold()} " in words
                          and len(str(row["short_name"])) > 2)), None)
        current = str(workspace.get("body") or "")
        details = named or next((row for row in bodies if current and current in (row.get("body"), row.get("short_name"))), {})
        body = str(details.get("body") or current)
        key = PlanetMaterialsStore._body_key
        sites = [row for row in workspace.get("sites") or ()
                 if str(row.get("system") or "").casefold() == system.casefold()]
        here = [row for row in sites if body and key(system, row.get("body")) == key(system, body)]
        position = workspace.get("current_position") or {}
        for row in here:
            radius = position.get("planet_radius") or row.get("planet_radius")
            if position and not named:
                row["distance_m"] = surface_distance_m(position.get("latitude"), position.get("longitude"),
                                                       row.get("latitude"), row.get("longitude"), radius)
        counts = {}
        for row in sites:
            if row not in here:
                counts[str(row.get("body") or "")] = counts.get(str(row.get("body") or ""), 0) + 1
        rigs = self.rig_store().rigs(system, body) if body else {}
        return watcher_copilot.planet_lines(
            body, details.get("materials") or (), rhino_forecast(details) if details else (),
            details.get("ground_label") if details.get("ground") else "", here, details.get("mining_locations") or 0,
            rigs, sorted(counts.items()), system, focus="sites" if SITES_ASKED.search(str(question or "")) else "materials")

    def _watcher_lookup_codex(self, question=""):
        """Your Codex (biology), from the index the Survey flags use."""
        index = getattr(self, "codex_index", None)
        rows = index.entries() if index is not None else []
        region, _coords = self._bio_location_context()
        names = region_names()
        region_name = names[region - 1] if region and 0 < region <= len(names) else ""
        here = []
        if index is not None and re.search(r"\b(here|this (planet|world|moon|body))\b", str(question or ""), re.I):
            here = index.entries_on(getattr(self, "current_system_address", None), getattr(self, "current_body_id", None))
        return watcher_copilot.codex_lines(rows, codex_index.reference(), region, region_name, question, here,
                                           now=time.time())

    def _watcher_lookup_missions(self):
        missions = (getattr(self, "companion_state", None) or {}).get("missions") or {}
        return watcher_copilot.missions_lines(list(missions.values()) if isinstance(missions, dict) else list(missions),
                                              time.time())

    def _watcher_lookup_ranks(self):
        return watcher_copilot.ranks_lines(getattr(self, "cmdr_ranks", None), getattr(self, "cmdr_rank_progress", None),
                                           getattr(self, "cmdr_reputation", None), names=ranks.name)

    def _watcher_lookup_squadron(self):
        tracker = getattr(self, "carrier_tracker", None)
        context = dict(getattr(tracker, "_squadron_context", None) or {}) if tracker is not None else {}
        return watcher_copilot.squadron_lines(context.get("squadron_name"), context.get("squadron_rank_name"))

    def _watcher_lookup_carrier(self):
        tracker = getattr(self, "carrier_tracker", None)
        return watcher_copilot.carrier_lines(tracker.display_carrier() if tracker is not None else None, now=time.time())

    def _watcher_lookup_data(self):
        state = getattr(self, "companion_state", None) or {}
        return watcher_copilot.data_lines(state.get("unsold_exploration_cr"), companion_features.unsold_bio_value(state))

    def _watcher_lookup_world(self, question=""):
        """The world you name, or the one you're at, from its scan."""
        items = [item for item in getattr(self, "scan_items", None) or () if isinstance(item, dict)]
        words = _asked_words(question)

        def named(item):
            short = str(item.get("name") or "").casefold().strip()
            return bool(short) and re.search(rf"(?<![\w-]){re.escape(short)}(?![\w-])", words) is not None

        here = str(getattr(self, "current_body_name", "") or "").casefold()
        chosen = (sorted((item for item in items if named(item)), key=lambda item: -len(str(item.get("name") or "")))[:1]
                  or [item for item in items if here and here in (str(item.get("full_name") or "").casefold(),
                                                                  str(item.get("name") or "").casefold())][:1])
        return watcher_copilot.world_lines(chosen[0] if chosen else None, question)

    def _watcher_lookup_record(self, question=""):
        return watcher_copilot.record_lines((getattr(self, "companion_state", None) or {}).get("statistics"), question)

    def _watcher_lookup_materials(self, question=""):
        from voidcompass.engineering.engineering_data import material_info
        return watcher_copilot.materials_lines(getattr(self, "engineer_materials", None) or {}, question,
                                               grade_of=lambda symbol: material_info(symbol).get("grade"))

    def _watcher_lookup_engineers(self, question=""):
        return watcher_copilot.engineer_lines(((getattr(self, "engineer_materials", None) or {}).get("engineers") or {}), question)

    def _watcher_lookup_goals(self):
        goals = (getattr(self, "companion_state", None) or {}).get("community_goals") or {}
        return watcher_copilot.community_goal_lines(list(goals.values()) if isinstance(goals, dict) else list(goals), time.time())

    def _watcher_lookup_colony(self):
        colony = getattr(self, "colony", None)
        if colony is None:
            return []
        from voidcompass.colonisation import catalogue
        projects = colony.visible_projects()
        needs = colony.needs(projects, self._colony_cmdr())["commodities"]
        return watcher_copilot.colony_lines(
            [(str(row.get("buildName") or "a project"), str(row.get("systemName") or "")) for row in projects],
            {catalogue.commodity_name(name): count for name, count in needs.items()})

    def _watcher_lookup_powerplay(self):
        return watcher_copilot.powerplay_lines((getattr(self, "companion_state", None) or {}).get("powerplay"))

    def _watcher_lookup_expedition(self):
        manager = getattr(self, "expedition_manager", None)
        return watcher_copilot.expedition_lines(manager.active() if manager is not None else None)

    def _watcher_lookup_galnet(self):
        return watcher_copilot.galnet_lines(row.get("title") for row in self._html_dashboard_galnet().get("articles") or [])

    def _watcher_lookup_music(self):
        status = getattr(self, "_music_status", None) or {}
        track = self.music_library().track(status.get("track_id")) if status.get("track_id") else None
        return watcher_copilot.music_lines(status, str((track or {}).get("title") or ""),
                                           str((track or {}).get("artist") or ""))

    def _watcher_lookup_life(self, question=""):
        """What could live on a world, from Survey's own predictions: one you
        name ("what's on 3 a?"), the one you're at, or this system's worlds
        with life, the most valuable first."""
        items = [item for item in getattr(self, "scan_items", None) or () if isinstance(item, dict)
                 and not item.get("is_star")]
        words = _asked_words(question)

        def named(item):
            short = str(item.get("name") or "").casefold().strip()
            return bool(short) and re.search(rf"(?<![\w-]){re.escape(short)}(?![\w-])", words) is not None

        def best(item):
            return max((row.get("max_value") or 0 for row in item.get("predicted_genuses") or ()), default=0)

        here = str(getattr(self, "current_body_name", "") or "").casefold()
        chosen = (sorted((item for item in items if named(item)), key=lambda item: -len(str(item.get("name") or "")))[:1]
                  or [item for item in items if here and here in (str(item.get("full_name") or "").casefold(),
                                                                  str(item.get("name") or "").casefold())][:1]
                  or sorted((item for item in items if item.get("bio_count")), key=lambda item: -best(item))[:3]
                  or sorted((item for item in items if item.get("predicted_genuses")), key=lambda item: -best(item))[:3])
        bodies = []
        for item in chosen:
            colours = {species: rows[0].get("colour") for species, rows in
                       self._survey_codex_variants(item.get("body_id")).items() if rows and rows[0].get("colour")}
            bodies.append({"name": item.get("full_name") or item.get("name"), "signals": item.get("bio_count"),
                           "known": [str(genus) for genus in item.get("genuses") or () if not str(genus).startswith("$")],
                           "genera": item.get("predicted_genuses") or [], "colours": colours})
        return watcher_copilot.life_lines(bodies)

    def _watcher_mind_action(self, text):
        """The small things it does when you ask (5.7.1): the music, the
        overlays, the next system to the clipboard, its own voice. Its reply,
        or None when nothing was asked."""
        original_text = text
        text = companions.addressed(text, companions.identity(self.config))
        mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
        rng = getattr(mind, "random", None)
        # 5.7.4: asked of a crewmate off watch, worded in its own lines.
        who = getattr(mind, "talking_as", None)
        if who and who != companions.identity(self.config):
            from voidcompass.overlays import crew_voices
            rng = crew_voices.CrewRandom(rng, who)
        from voidcompass.core import voice_commands
        resolved = voice_commands.native_request(text, self.config.get("watcher_ship_commands"))
        native = resolved[0].native if resolved else {}
        if native.get("kind") == "uplink":
            fields = resolved[1]
            question = f"where can I {native['value']} {fields['commodity']}" if fields.get("commodity") else text
            commodities = self._watcher_uplink_commodities(question)
            request = {"kind": native["value"] if commodities else None,
                       "commodity": str(commodities[0][1]) if commodities else ""}
            return self._watcher_uplink(original_text, request, rng)
        if native.get("kind") == "overlay":
            return self._watcher_overlay({key: native[key] for key in ("overlay", "op")}, rng)
        # 5.7.6: the nearest station with a service, and how far to a system.
        station = watcher_copilot.station_request(text)
        if station:
            return self._watcher_station_search(original_text, station, rng)
        # 5.7.7: Crew Orders, asked about by name ("any orders?", "accept the order").
        orders = self._orders_talk(text) if hasattr(self, "_orders_talk") else None
        if orders:
            return orders
        target = watcher_copilot.distance_request(text)
        if target:
            return self._watcher_distance(original_text, target, rng)
        # 5.7.3: the ship's own controls, pressed in Elite.
        ship = getattr(self, "_watcher_ship", None)
        done = ship(text, rng) if callable(ship) else None
        if done is not None:
            return done
        wanted = native.get("value") if native.get("kind") == "intent" else None
        if wanted is None:
            return None
        outcome, fields = wanted, {}
        status = getattr(self, "_music_status", None) or {}
        playing = bool(status.get("playing"))
        # Play and pause, never a toggle (5.7.3): the app's idea of what's
        # playing can lag the deck's, and "play" then paused it, or "stop" was
        # met with "nothing is playing".
        if wanted == "music_pause":
            outcome = wanted if self.music_remote("pause") else "unavailable"
        elif wanted == "music_play":
            sent = self.music_remote("play")
            outcome = ("unavailable" if not sent else "music_blocked" if status.get("blocked")
                       else "music_already" if playing else wanted)
        elif wanted in {"music_next", "music_previous"}:
            outcome = wanted if self.music_remote(wanted.split("_")[1]) else "unavailable"
        elif wanted in {"overlays_hide", "overlays_show"}:
            hidden = bool(getattr(self, "_overlay_hotkey_global_hidden", False))
            if hidden == (wanted == "overlays_hide"):
                outcome = "overlays_already_hidden" if hidden else "overlays_already_shown"
            else:
                self._ui_post(self._handle_overlay_hotkey, "toggle_all", key="watcher-overlays")
        elif wanted == "copy_next":
            nav = self._build_navigation_hud_context()
            system = str(nav.get("next") or "")
            if system and system != "---" and self._copy_waypoint_to_clipboard(system, "NEXT SYSTEM"):
                fields["system"] = system
            else:
                outcome = "copy_none"
        elif wanted == "hush":
            self._watcher_voice_hush(900)
        elif wanted == "unhush":
            self._watcher_voice_hush(0)
        return watcher_copilot.reply(outcome, rng, **fields)

    def _watcher_overlay(self, asked, rng=None):
        """One overlay by name (5.7.3): hidden or shown as its hotkey does it,
        or switched off or on as Overlay Studio does (shown, a switched-off
        one is switched on). Its reply."""
        spec = next((row for row in OVERLAY_SPECS if row.overlay_id == asked["overlay"]), None)
        if spec is None:
            return watcher_copilot.reply("unavailable", rng)
        spoken = watcher_copilot.OVERLAY_SPOKEN.get(spec.overlay_id, spec.label)
        fields = {"label": spoken[:1].upper() + spoken[1:], "label_l": spoken}
        enabled = bool(self.config.get(spec.enabled_key, False))
        op = asked["op"]

        def reply(outcome):
            return watcher_copilot.reply(outcome, rng, **fields)

        if op in ("on", "off") or (op == "show" and not enabled):
            wanted = op != "off"
            if wanted == enabled:
                return reply("overlay_already_on" if enabled else "overlay_already_off")
            self._ui_post(self._html_overlay_toggle, spec.attr, key=f"watcher-overlay-{spec.attr}")
            return reply("overlay_on" if wanted else "overlay_off")
        if not enabled:
            return reply("overlay_already_off")
        if getattr(self, "_overlay_hotkey_global_hidden", False):
            return reply("overlay_curtain") if op == "show" else reply("overlay_already_hidden")
        hidden = spec.attr in (getattr(self, "_overlay_hotkey_hidden", None) or set())
        window = self._overlay_window(getattr(self, spec.attr, None))
        shown = bool(window is not None and self._overlay_window_is_shown(window))
        if op == "hide":
            if hidden or not shown:
                return reply("overlay_already_hidden")
            self._ui_post(self._handle_overlay_hotkey, spec.hotkey_action, key=f"watcher-overlay-{spec.attr}")
            return reply("overlay_self") if spec.overlay_id == "heartbeat" else reply("overlay_hidden")
        if shown and not hidden:
            return reply("overlay_already_shown")
        if not hidden:
            # On, but nothing to show just now (the Rhino Map out of the Rhino, say).
            return reply("overlay_waiting")
        self._ui_post(self._handle_overlay_hotkey, spec.hotkey_action, key=f"watcher-overlay-{spec.attr}")
        return reply("overlay_shown")

    def _watcher_uplink_commodities(self, text):
        """What the uplink would look up: the commodities you named, or
        (asking about your cargo) the most you're carrying."""
        named = self._watcher_commodities_named(text, self._watcher_market_file().get("items") or ())
        if named or not re.search(r"\b(cargo|hold|it all|everything)\b", str(text or ""), re.I):
            return named
        held = self._trading_cargo() if getattr(self, "trading_names", None) is not None else []
        return [(held[0]["symbol"], held[0]["name"])] if held else []

    def _watcher_uplink(self, text, request, rng=None):
        """The uplink (5.7.3): the Trading page's Spansh search for where to
        sell (or buy) a commodity. Selling favours reports within a day and
        returns two distinct buyers within your Sell cargo radius."""
        if not request.get("kind"):
            return watcher_copilot.reply("uplink_what", rng)
        if not self._trading_online():
            return watcher_copilot.reply("uplink_off", rng)
        kind, commodity = request["kind"], request["commodity"]
        system = str(getattr(self, "current_sys", "") or "")
        options = self._trading_cargo_options()
        held = {row["symbol"]: row["count"] for row in self._trading_cargo()} if kind == "sell" else {}
        amount = max(1, int(held.get(symbol(commodity)) or 1))
        generation = getattr(self, "_companion_generation", 0)
        requested_mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)

        def work():
            self._trading_spansh_names()
            name = self.trading_names.spansh_name(commodity)
            choice = {"large_pad": options["large"], "carriers": options["carriers"], "planetary": options["planetary"]}
            if kind == "sell":
                fresh = trade_market.parse_commodity(spansh.commodity_stations(
                    kind, system, name, amount, size=5, sort="price", radius=options["radius"], max_age_days=1, **choice), name, kind)
                best = watcher_copilot.uplink_sell_results(fresh, time.time())
                if len(best) < 2:
                    older = trade_market.parse_commodity(spansh.commodity_stations(
                        kind, system, name, amount, size=5, sort="price", radius=options["radius"], **choice), name, kind)
                    best = watcher_copilot.uplink_sell_results([*fresh, *older], time.time())
                return {"name": name, "best": best, "near": []}
            best = trade_market.parse_commodity(spansh.commodity_stations(
                kind, system, name, amount, size=5, sort="price", radius=options["radius"], **choice), name, kind)
            near = trade_market.parse_commodity(spansh.commodity_stations(kind, system, name, amount, size=5, **choice),
                                                name, kind)
            best.sort(key=lambda row: -row["price"] if kind == "sell" else row["price"])
            near.sort(key=lambda row: row.get("distance") or 0.0)
            return {"name": name, "best": best, "near": near}

        def done(result, error):
            if generation != getattr(self, "_companion_generation", 0) or requested_mind is not getattr(getattr(self, "heartbeat_hud", None), "mind", None):
                return
            result = result or {}
            lines = watcher_copilot.uplink_lines(kind, result.get("name") or commodity, result.get("best"),
                                                 result.get("near"), system, options["radius"], time.time(), error)
            mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
            if mind is not None and mind.uplink_answer(text, lines):
                self._watcher_mind_watch()

        # A cached reply answers at once: after this question is in, not inside it.
        self._trading_task("watcher-uplink", work, lambda result, error: self._ui_post(done, result, error),
                           cache_key=("watcher-uplink-fresh-two", kind, system, commodity, amount, tuple(sorted(options.items()))))
        return {"waiting": True, "say": watcher_copilot.reply("uplink_opening", rng, commodity=commodity, verb=kind)}

    def _watcher_station_search(self, text, station, rng=None):
        """5.7.6: "Where's the nearest material trader?" Spansh's station
        search from where you are, answered when it comes back."""
        if not self._trading_online():
            return watcher_copilot.reply("uplink_off", rng)
        system = str(getattr(self, "current_sys", "") or "")
        coords = self._galaxy_minimap_position() if hasattr(self, "_galaxy_minimap_position") else None
        if not system and not coords:
            return watcher_copilot.reply("distance_nowhere", rng)
        generation = getattr(self, "_companion_generation", 0)
        requested_mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)

        def work():
            if station["trader"]:
                rows = spansh.material_traders(system, station["trader"], size=STATION_SEARCH_SIZE, coords=coords)
            else:
                rows = spansh.service_stations(system, station["service"], size=STATION_SEARCH_SIZE, coords=coords)
            return [row for row in rows if station["carriers"] or not row.get("carrier")]

        def done(result, error):
            if generation != getattr(self, "_companion_generation", 0) or requested_mind is not getattr(getattr(self, "heartbeat_hud", None), "mind", None):
                return
            lines = watcher_copilot.nearest_station_lines(station["label"], result, system, error)
            mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
            if mind is not None and mind.uplink_answer(text, lines):
                self._watcher_mind_watch()

        self._trading_task("watcher-station", work, lambda result, error: self._ui_post(done, result, error),
                           cache_key=("watcher-station", system, station["service"], station["trader"], station["carriers"]))
        return {"waiting": True, "say": watcher_copilot.reply("station_opening", rng, label=station["label"])}

    def _watcher_distance(self, text, name, rng=None):
        """5.7.6: "How far is Colonia?" From your own history first (or a
        well-known place, or home), else Spansh when trading searches are on."""
        here = self._galaxy_minimap_position() if hasattr(self, "_galaxy_minimap_position") else None
        if here is None:
            return watcher_copilot.reply("distance_nowhere", rng)
        here_name = str(getattr(self, "current_sys", "") or "")
        try:
            reach = float(self._expedition_jump_range() or 0)
        except Exception:
            reach = 0.0
        found = None
        if name.casefold() in ("home", "home system", "my home", "our home"):
            anchor = home_anchor.home(self.config)
            found = {"name": anchor["name"], "coords": anchor["pos"]}
        if found is None:
            history = getattr(self, "travel_history", None)
            rows = []
            if history is not None:
                lock = getattr(history, "lock", None)
                if lock is not None:
                    with lock:
                        rows = list(getattr(history, "rows", None) or ())
                else:
                    rows = list(getattr(history, "rows", None) or ())
            position = home_anchor.from_history(rows, name) if rows else None
            if position is not None:
                spelled = next((str(row[1]) for row in reversed(rows) if str(row[1]).casefold() == name.casefold()), name)
                found = {"name": spelled, "coords": position}
        found = found or watcher_copilot.landmark(name)
        if found is not None:
            return watcher_copilot.plain_answer(watcher_copilot.distance_lines(found["name"], found["coords"], here_name, here, reach))
        if not self._trading_online():
            return watcher_copilot.reply("distance_unknown", rng, name=name)
        generation = getattr(self, "_companion_generation", 0)
        requested_mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)

        def done(result, error):
            if generation != getattr(self, "_companion_generation", 0) or requested_mind is not getattr(getattr(self, "heartbeat_hud", None), "mind", None):
                return
            if error:
                lines = [f"The uplink couldn't find {name}: {error}"]
            elif not result:
                lines = [f"Spansh doesn't know a system called {name}"]
            else:
                lines = watcher_copilot.distance_lines(result["name"], result["coords"], here_name, here, reach)
            mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
            if mind is not None and mind.uplink_answer(text, lines):
                self._watcher_mind_watch()

        self._trading_task("watcher-distance", lambda: spansh.system_position(name),
                           lambda result, error: self._ui_post(done, result, error),
                           cache_key=("watcher-distance", name.casefold()))
        return {"waiting": True, "say": watcher_copilot.reply("distance_opening", rng, name=name)}

    def _watcher_mind_watch(self):
        """Speak and publish a new command reply or uplink answer immediately."""
        if not getattr(self, "_closing", False):
            hud = getattr(self, "heartbeat_hud", None)
            if hud is not None and callable(getattr(hud, "_redraw", None)):
                hud._redraw()
            self._schedule_html_dashboard_publish(immediate=True)

    def _html_watcher_talk(self, mind):
        retired = {text for topic, text in retired_speech(mind.memory) if topic == "talk"}
        return {
            "talk": [{"at": row.get("at"), "you": str(row.get("you") or ""),
                      "it": "" if " ".join(str(row.get("it") or "").split()) in retired else str(row.get("it") or ""),
                      "voice": bool(row.get("voice")),
                      **({"who": row["who"]} if row.get("who") in companions.IDENTITIES else {})}
                     for row in (mind.memory.get("talk") or [])[-20:] if isinstance(row, dict)],
            "orb_on": getattr(self, "heartbeat_hud", None) is not None,
        }

    # -- the download --------------------------------------------------------
    def _watcher_voice_downloader(self):
        if companions.overlay_only(self.config):
            raise ValueError("This companion has no voice model yet")
        download = getattr(self, "_watcher_voice_download", None)
        selected = companions.identity(self.config)
        if download is None or getattr(download, "model", "watcher") != selected:
            download = voice_assets.VoiceDownload(model=selected) if selected != "watcher" else voice_assets.VoiceDownload()
            self._watcher_voice_download = download
        return download

    def _watcher_voice_start_download(self):
        """Start the download, and keep the Watcher page's progress moving."""
        generation = getattr(self, "_companion_generation", 0)
        started = self._watcher_voice_downloader().start(lambda state: self._watcher_voice_downloaded(state) if generation == getattr(self, "_companion_generation", 0) else None)
        self._watcher_voice_progress()
        return started

    def _watcher_voice_progress(self):
        download = getattr(self, "_watcher_voice_download", None)
        if download is None or getattr(self, "_closing", False):
            return
        self._schedule_html_dashboard_publish(immediate=True)
        if download.running():
            self._watcher_voice_progress_job = self.root.call_later(700, self._watcher_voice_progress)

    def _watcher_voice_downloaded(self, state):
        stage = state.get("stage")
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            if stage == "done":
                feed("SYSTEM", f"{companions.name(self.config)}’s voice is downloaded and ready", severity="INFO")
            elif stage == "failed":
                feed("SYSTEM", f"{companions.name(self.config)}’s voice didn’t download: {state.get('error')}", severity="WARNING")
        post = getattr(self, "_ui_post", None)
        work = lambda: (self._watcher_voice_sync(), self._schedule_html_dashboard_publish(immediate=True))
        if callable(post):
            post(work, key="watcher-voice-download")
        else:
            work()

    # -- the page ------------------------------------------------------------
    def _html_watcher_settings(self):
        style = watcher_mind.thought_style(self.config)
        return {
            "heartbeat_thoughts": watcher_mind.frequency(companions.settings(self.config)),
            "aster_humour": self.config.get("aster_humour", "dry"),
            # The active persona's own commentary choice (5.7.4).
            **self._companion_humour_payload(),
            "heartbeat_personality": watcher_mind.personality(self.config),
            "heartbeat_thought_side": thought_side_setting(self.config),
            "heartbeat_text_scale_percent": heartbeat_text_size(self.config.get("heartbeat_text_scale_percent")),
            "heartbeat_thought_colour": style["colour"],
            "heartbeat_thought_size": style["size"],
            "heartbeat_thought_hold": style["hold"],
            "heartbeat_thought_backdrop": style["backdrop"],
            "heartbeat_thought_heading": style["heading"],
            "crew_rota": bool(self.config.get("crew_rota")),
            **{crew_rota.duty_key(duty): who for duty, who in crew_rota.duties(self.config).items()},
            "crew_rota_deep_ly": str(crew_rota.deep_ly(self.config)),
            "rota_status": self._crew_rota_status() if self.config.get("crew_rota") else None,
            # 5.7.7: crew banter, on the same page.
            **(self._banter_settings() if hasattr(self, "_banter_settings") else {}),
            "text_sizes": list(HEARTBEAT_TEXT_SIZES),
        }

    def _companion_humour_payload(self):
        from voidcompass.overlays import companion_personas
        persona = companion_personas.get(companions.identity(self.config))
        if persona is None:
            return {"companion_humour": None}
        return {"companion_humour": {"value": self.config.get(persona.humour_key, "dry"), "label": persona.humour_label,
                                     "choices": [list(row) for row in persona.humour_choices]}}

    def _html_watcher_voice(self, memory):
        selected = companions.identity(self.config)
        if companions.overlay_only(selected):
            return {"identity": selected, "available": False, "model_name": "Voice pending", "enabled": False,
                    "installed": False, "download": {"stage": "idle"}, "size_mb": 0, "speaking": False,
                    "orb_on": getattr(self, "heartbeat_hud", None) is not None}
        config = companions.settings(self.config)
        download = getattr(self, "_watcher_voice_download", None)
        state = download.state() if download is not None else {"stage": "idle", "done": 0,
                                                                "total": voice_assets.download_bytes(selected), "error": ""}
        speaker = getattr(self, "_watcher_voice", None)
        try:
            volume = int(float(config.get("watcher_voice_volume", 80)))
        except (TypeError, ValueError):
            volume = 80
        return {
            "identity": selected,
            "model_name": voice_assets.model_name(selected),
            "enabled": bool(config.get("watcher_voice_enabled")),
            "installed": self._companion_voice_installed(),
            "download": state,
            "size_mb": round(voice_assets.download_bytes(selected) / 1_000_000),
            "rights": voice_assets.notice(selected),
            "volume": max(0, min(100, volume)),
            "speed": str(config.get("watcher_voice_speed") or "standard"),
            "level": str(config.get("watcher_voice_level") or "every"),
            "speaking": bool(speaker is not None and speaker.live()),
            "finding": {"stage": 4, "found": True, "told": [], "minutes": 0} if selected != "watcher" else watcher_voice_lore.progress(memory),
            "orb_on": getattr(self, "heartbeat_hud", None) is not None,
        }

    def _html_watcher_extras(self, mind):
        """The Watcher's written thoughts, voice and command conversation."""
        return {"settings": self._html_watcher_settings(),
                "voice": self._html_watcher_voice(mind.memory),
                "habits": watcher_habits.summary(mind.memory, mind.bond()),
                "name": mind.name_page() if getattr(mind, "identity", "watcher") != "watcher" else watcher_name.page(mind.memory),
                "talk": self._html_watcher_talk(mind),
                "listen": self._html_watcher_listen()}

    def _handle_watcher_settings_command(self, operation, payload):
        """The Watcher page's own controls. True when handled and done."""
        if operation == "companion_identity":
            return self._companion_switch(str(payload.get("value") or ""))
        if companions.overlay_only(self.config) and operation != "settings":
            return False
        if operation in ("aster_humour", "companion_humour"):
            key = "aster_humour" if operation == "aster_humour" else companions.humour_key(self.config)
            if not key or payload.get("value") not in ("off", "dry"):
                return False
            self.config[key] = payload["value"]
            self._persist_config()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "rota_release":
            # 5.7.7: give the watch back to the rota now, instead of waiting out your pick.
            self._crew_rota_state().release()
            self._crew_rota_tick()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "settings":
            values = payload.get("values") if isinstance(payload.get("values"), dict) else {}
            if companions.identity(self.config) != "watcher" and "heartbeat_thoughts" in values:
                if values["heartbeat_thoughts"] not in watcher_mind.FREQUENCIES:
                    return False
                self.config[companions.key(self.config, "heartbeat_thoughts")] = values["heartbeat_thoughts"]
                self._persist_config()
                values = {key: value for key, value in values.items() if key != "heartbeat_thoughts"}
            if "crew_rota" in values:
                # 5.7.6: the watch rota, a commander setting of its own.
                self.config["crew_rota"] = bool(values["crew_rota"])
                self._crew_rota_state().held_until = 0.0
                self._persist_config()
                values = {key: value for key, value in values.items() if key != "crew_rota"}
                if self.config["crew_rota"]:
                    self._crew_rota_tick()
            if "crew_rota_deep_ly" in values:
                # 5.7.6: where deep space starts, light years from home.
                try:
                    reach = int(values["crew_rota_deep_ly"])
                except (TypeError, ValueError):
                    return False
                if reach not in crew_rota.DEEP_CHOICES:
                    return False
                self.config["crew_rota_deep_ly"] = reach
                self._crew_rota_state().candidate = None
                self._persist_config()
                values = {key: value for key, value in values.items() if key != "crew_rota_deep_ly"}
                if not values:
                    self._schedule_html_dashboard_publish(immediate=True)
                    return True
            duty_keys = {crew_rota.duty_key(duty) for duty, _label, _who in crew_rota.DUTIES}
            if duty_keys & set(values):
                # 5.7.6: who takes each duty on the watch rota.
                for key in duty_keys & set(values):
                    who = str(values[key] or "").casefold()
                    if who not in crew_rota.CREW and who != crew_rota.KEEP:
                        return False
                    self.config[key] = who
                self._crew_rota_state().candidate = None
                self._persist_config()
                values = {key: value for key, value in values.items() if key not in duty_keys}
                if not values:
                    self._schedule_html_dashboard_publish(immediate=True)
                    return True
            if hasattr(self, "_banter_save_settings") and any(str(key).startswith("crew_banter") for key in values):
                # 5.7.7: crew banter, how often, how many and when.
                rest = self._banter_save_settings(values)
                if rest is None:
                    return False
                self._persist_config()
                values = rest
                if not values:
                    self._schedule_html_dashboard_publish(immediate=True)
                    return True
            selects = {key: values[key] for key in WATCHER_SELECTS if key in values}
            done = True
            if selects:
                done = bool(self._html_overlay_settings_save(selects))
            for key in WATCHER_SWITCHES:
                if key in values:
                    done = bool(self._html_overlay_option_toggle(key, bool(values[key]))) and done
            return done
        if operation == "voice_toggle":
            self.config[companions.key(self.config, "watcher_voice_enabled")] = bool(payload.get("value"))
            self._persist_config()
            if companions.settings(self.config).get("watcher_voice_enabled") and not self._companion_voice_installed():
                self._watcher_voice_start_download()
            self._watcher_voice_sync()
            return True
        if operation == "voice_settings":
            values = payload.get("values") if isinstance(payload.get("values"), dict) else {}
            if "watcher_voice_volume" in values:
                try:
                    self.config[companions.key(self.config, "watcher_voice_volume")] = max(0, min(100, int(float(values["watcher_voice_volume"]))))
                except (TypeError, ValueError):
                    return False
            if values.get("watcher_voice_speed") in SPEEDS:
                self.config[companions.key(self.config, "watcher_voice_speed")] = values["watcher_voice_speed"]
            if values.get("watcher_voice_level") in LEVELS:
                self.config[companions.key(self.config, "watcher_voice_level")] = values["watcher_voice_level"]
            self._persist_config()
            return True
        if operation == "voice_download":
            self._watcher_voice_start_download()
            return True
        if operation == "voice_cancel":
            self._watcher_voice_downloader().cancel()
            return True
        if operation == "voice_remove":
            speaker = getattr(self, "_watcher_voice", None)
            if speaker is not None:
                speaker.stop()
                speaker._stop_engine()
            selected = companions.identity(self.config)
            done = voice_assets.remove(model=selected) if selected != "watcher" else voice_assets.remove()
            self._watcher_voice_sync()
            return done
        if operation == "voice_test":
            if (not self._companion_voice_installed() or self._watcher_voice_boot_held()
                    or getattr(self, "_closing", False)):
                return False
            from voidcompass.overlays import companion_personas
            persona = companion_personas.get(companions.identity(self.config))
            line = persona.test_line if persona else TEST_LINE
            return self._watcher_speaker().say(line, "test")
        if operation == "voice_stop":
            speaker = getattr(self, "_watcher_voice", None)
            if speaker is not None:
                speaker.stop()
            return True
        if operation in {"name_call", "name_nickname", "name_spoken"}:
            # Your name (5.7.1): kept in the Watcher's memory of this commander.
            mind = self._watcher_mind()
            value = payload.get("value")
            with mind.lock:
                if operation == "name_call":
                    done = watcher_name.set_call(mind.memory, str(value or ""))
                elif operation == "name_nickname":
                    done = watcher_name.set_nickname(mind.memory, value) is not None
                else:
                    done = watcher_name.set_spoken(mind.memory, value) is not None
            mind.save()
            publish = getattr(self, "_schedule_html_dashboard_publish", None)
            if callable(publish):
                publish(immediate=True)
            return done
        if operation == "talk":
            hud = getattr(self, "heartbeat_hud", None)
            mind = getattr(hud, "mind", None)
            if mind is None or not mind.talk(payload.get("text")):
                return False
            self._watcher_mind_watch()
            return True
        if operation == "talk_forget":
            mind = self._watcher_mind()
            with mind.lock:
                mind.memory["talk"] = []
            mind.save()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "name_hear":
            if (not self._companion_voice_installed() or self._watcher_voice_boot_held()
                    or getattr(self, "_closing", False)):
                return False
            known = watcher_name.record(self._watcher_mind().memory).get("known") or ""
            said = " ".join(str(payload.get("value") or "").split()) or watcher_name.auto_spoken(known)
            return bool(said) and self._watcher_speaker().say(f"{said}.", "test")
        return self._handle_watcher_listen_command(operation, payload)
