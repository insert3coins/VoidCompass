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

from voidcompass.core import companion_features, ranks
from voidcompass.exploration import codex_index
from voidcompass.exploration.galactic_regions import find_region, region_names
from voidcompass.core.platform_support import application_dir
from voidcompass.llm import library_sources, llm_assets
from voidcompass.llm.llm_embed import Embedder
from voidcompass.mining.planet_materials import PlanetMaterialsStore
from voidcompass.mining.rhino_intelligence import rhino_forecast, surface_distance_m
from voidcompass.overlays import (
    watcher_copilot, watcher_deeper, watcher_habits, watcher_knowing, watcher_llm, watcher_mind, watcher_name,
    watcher_voice_lore, watcher_world,
)
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
ASKS_THE_QUESTION = {"life", "planet", "materials", "codex", "world", "record", "cargo", "market"}
# Short names commanders use for commodities.
COMMODITY_ALIASES = {"ltd": "Low Temperature Diamonds", "ltds": "Low Temperature Diamonds",
                     "vo": "Void Opal", "vos": "Void Opal"}
# "Where are the sites?" wants the sites first, not the crust's makeup.
SITES_ASKED = re.compile(r"\b(sites?|rigs?|deposits?|drill\w*|where)\b", re.I)
# A card from your sources is never kept if it names what the Watcher never
# speaks of, or reads like orders to it (a page's text is only ever reference).
SOURCE_REFUSED = re.compile("|".join((
    watcher_llm.MYSTERY.pattern, watcher_llm.BANNED.pattern,
    r"ignore\s+(all|any|previous|the\s+above)|disregard\s+(all|previous)|you\s+are\s+now\b|new\s+instructions",
)), re.I)


def _asked_words(question):
    """What you asked, lower case and padded, its punctuation gone: "on
    Colonia 4?" names Colonia 4 (the question mark hid it)."""
    return f" {' '.join(re.sub(r'[?!.,;:]+', ' ', str(question or '').casefold()).split())} "


class DashboardWatcherVoiceMixin:
    # -- the speaker ---------------------------------------------------------
    def _watcher_speaker(self):
        speaker = getattr(self, "_watcher_voice", None)
        if speaker is None:
            speaker = WatcherSpeaker(settings=lambda: self.config, on_change=self._watcher_voice_changed)
            self._watcher_voice = speaker
        return speaker

    def _watcher_voice_on(self):
        return bool(self.config.get("watcher_voice_enabled")) and voice_assets.installed()

    def _watcher_voice_attach(self, hud):
        """A new Watcher orb: give it the voice, and its own words."""
        if hud is None:
            return
        hud.voice_listener = self._watcher_voice_say
        self._watcher_voice_sync()
        mind = getattr(hud, "mind", None)
        if mind is not None:
            mind.llm = self._watcher_llm()
            mind.facts_provider = self._watcher_llm_facts
            mind.lookup_provider = self._watcher_llm_lookup
            mind.action_provider = self._watcher_mind_action
            mind.on_words = lambda _key: self._ui_post(self._schedule_html_dashboard_publish, key="watcher-mind-words")
            # Its mood and trust colour how it speaks.
            mind.llm.feeling_provider = lambda: watcher_deeper.words_for(mind.memory)
        self._watcher_llm().sync()
        # 5.7.1: its library search model, for those who woke it before it came.
        if self._watcher_mind_needs_download() and self._watcher_llm().installed():
            self._watcher_mind_start_download()

    def _watcher_voice_say(self, words, key=None, feel=None):
        if (getattr(self, "_closing", False) or self._watcher_voice_boot_held()
                or not self._watcher_voice_on() or self._watcher_voice_hushed()):
            return False
        said = self._watcher_speaker().say(words, key, feel=feel)
        if said and hasattr(self, "_api_publish"):
            self._voice_from = "api" if str(key or "").startswith("api-") else "watcher"
            self._api_publish("voice", {"state": "started", "text": words, "from": self._voice_from})
        return said

    def _watcher_voice_boot_held(self):
        root = getattr(self, "root", None)
        return bool(
            getattr(self, "_startup_presentation_held", False)
            or getattr(root, "_voidcompass_startup_presentation_held", False)
            or getattr(root, "_voidcompass_startup_splash", None) is not None
            or getattr(self, "_startup_overlay_handoff_pending", None) is not None
        )

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
        if was and not speaking:
            reason = getattr(self, "_voice_stop_reason", "") or "finished"
            self._voice_stop_reason = ""
            if hasattr(self, "_api_publish"):
                self._api_publish("voice", {"state": reason, "from": getattr(self, "_voice_from", "watcher")})

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
        return levels

    def _watcher_voice_close(self):
        """App shutdown: silent at once, the engine stopped, any download
        dropped; its own words' model unloaded."""
        for name in ("_watcher_voice_download", "_watcher_mind_download"):
            download = getattr(self, name, None)
            if download is not None:
                download.cancel()
        speaker = getattr(self, "_watcher_voice", None)
        if speaker is not None:
            speaker.close()
        llm = getattr(self, "_watcher_mind_llm", None)
        if llm is not None:
            llm.close()
        sources = getattr(self, "_watcher_source_library", None)
        if sources is not None:
            sources._closing = True
        embedder = getattr(self, "_watcher_search_model", None)
        if embedder is not None:
            embedder.close()
        self._watcher_listen_close()

    # -- its own words (5.7.1, experimental) ------------------------------------
    def _watcher_llm(self):
        llm = getattr(self, "_watcher_mind_llm", None)
        if llm is None:
            llm = watcher_llm.WatcherLLM(settings=lambda: self.config)
            # Loading, ready, failed or stopped: the Watcher page shows it at once.
            llm.on_change = lambda: self._ui_post(self._watcher_mind_watch, key="watcher-mind-state")
            # What you asked, looked up in your own sources too.
            llm.library_provider = lambda question: self._watcher_sources().for_prompt(question)
            self._watcher_mind_llm = llm
        return llm

    def _watcher_embedder(self):
        """Its library search by meaning (llm_embed): one small model on the CPU."""
        embedder = getattr(self, "_watcher_search_model", None)
        if embedder is None:
            embedder = self._watcher_search_model = Embedder()
        return embedder

    def _watcher_sources(self):
        """Your own sources for its library, kept in Void Compass's folder, and
        searched (by meaning, when its search model is here) with its own cards."""
        sources = getattr(self, "_watcher_source_library", None)
        if sources is None:
            sources = library_sources.SourceLibrary(
                application_dir() / "library", refused=SOURCE_REFUSED, embedder=self._watcher_embedder(),
                builtin=lambda: [{"title": card["title"], "text": card["text"], "subject": subject["subject"]}
                                 for subject in watcher_world.library() for card in subject["cards"]],
                on_change=lambda: self._ui_post(self._schedule_html_dashboard_publish, key="watcher-library"))
            self._watcher_source_library = sources
            sources.fill_vectors()
        return sources

    def _watcher_mind_needs_download(self):
        """Its words on, and the model or its search model still to fetch."""
        return bool(self.config.get("watcher_llm_enabled")) and not (
            self._watcher_llm().installed() and llm_assets.embedder_installed())

    def _html_watcher_sources(self):
        sources = self._watcher_sources()
        note, when = getattr(self, "_watcher_source_note", ("", 0.0))
        query = getattr(self, "_watcher_source_query", "")
        return {
            "list": sources.sources(),
            "running": sources.running(),
            "state": dict(sources.state),
            "cards": sources.card_count(),
            "note": note if time.time() - when < 12 else "",
            "query": query,
            "results": [{"title": card["title"], "text": card["text"][:420], "host": card["host"],
                         "subject": card.get("subject", ""), "own": bool(card.get("own"))}
                        for card in sources.search(query, 24)] if query else [],
            # Search by meaning: its model here, and cards still being read for it.
            "meaning": self._watcher_embedder().available(),
            "indexing": dict(sources.indexing),
            "pages": list(library_sources.PAGE_CHOICES),
        }

    def _watcher_llm_facts(self):
        """What's true right now, for its own words: only what the journal says."""
        ship = getattr(self, "cmdr_ship", None) or {}
        kind = watcher_world.ship_name(ship.get("ship")) or watcher_world.ship_name(ship.get("ship_localised")) \
            or str(ship.get("ship_localised") or "")
        station = str(getattr(self, "current_station_name", "") or "")
        body = str(getattr(self, "current_body_name", "") or "")
        if getattr(self, "current_on_foot", False):
            doing = f"on foot at {station}" if getattr(self, "current_docked", False) and station else "on foot"
        elif getattr(self, "current_in_srv", False):
            doing = f"driving the SRV on {body}" if body else "driving the SRV"
        elif getattr(self, "current_docked", False):
            doing = f"docked at {station}" if station else "docked"
        elif getattr(self, "current_landed", False):
            doing = f"landed on {body}" if body else "landed"
        elif int(getattr(self, "current_status_flags", 0) or 0) & 0x10:
            doing = "in supercruise"
        else:
            doing = "flying"
        facts = {"system": str(getattr(self, "current_sys", "") or ""), "ship": kind,
                 "ship name": str(ship.get("ship_name") or ""), "doing": doing}
        if body and not getattr(self, "current_docked", False):
            facts["near"] = body
        coords = getattr(self, "current_coords", None)
        try:
            x, y, z = (float(value) for value in list(coords)[:3])
            region = find_region(x, y, z)
            if region:
                facts["region"] = region[1]
            facts["distance from Sol"] = f"{(x * x + y * y + z * z) ** .5:,.0f} light years"
        except (TypeError, ValueError):
            pass
        return {key: value for key, value in facts.items() if value}

    def _watcher_llm_lookup(self, question):
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
        for topic in topics:
            try:
                lookup = getattr(self, f"_watcher_lookup_{topic}")
                lines += lookup(question) if topic in ASKS_THE_QUESTION else lookup()
            except Exception:
                logging.debug("Watcher lookup %s skipped", topic, exc_info=True)
        return lines[:watcher_copilot.LOOKUP_LIMIT]

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
            self._watcher_llm_facts().get("ship", ""), str(ship.get("ship_name") or ""), self._expedition_jump_range(),
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
        return watcher_copilot.materials_lines(getattr(self, "engineer_materials", None) or {}, question)

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
        rng = getattr(getattr(getattr(self, "heartbeat_hud", None), "mind", None), "random", None)
        fact = watcher_copilot.remember_request(text)
        if fact is not None:
            return watcher_copilot.reply(self._watcher_remember(fact), rng)
        wanted = watcher_copilot.intent(text)
        if wanted is None:
            return None
        outcome, fields = wanted, {}
        playing = bool((getattr(self, "_music_status", None) or {}).get("playing"))
        if wanted == "music_pause":
            outcome = wanted if playing and self.music_remote("toggle") else "music_not_playing"
        elif wanted == "music_play":
            outcome = "music_already" if playing else wanted if self.music_remote("toggle") else "unavailable"
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

    def _watcher_remember(self, fact):
        """"Remember that…" (5.7.2): kept in its library as you said it, like
        TEACH IT (its note-taker passes over requests). The reply's outcome."""
        if watcher_llm.BANNED.search(fact) or watcher_llm.MYSTERY.search(fact):
            return "remember_refused"
        mind = self._watcher_mind()
        with mind.lock:
            error = watcher_knowing.teach(mind.memory, fact, time.time())
        if not error:
            mind.save()
            self._schedule_html_dashboard_publish(immediate=True)
            return "remember"
        return "remember_known" if "already" in error else "remember_long"

    def _watcher_own_words(self, key, kind, text):
        """A page's paragraph in the Watcher's own words, once its mind has
        written them (5.7.1); the written one until then."""
        mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
        if mind is None or not text:
            return None
        try:
            return mind.own_paragraph(key, kind, text)
        except Exception:
            logging.debug("Watcher own words skipped", exc_info=True)
            return None

    def _watcher_own_flight_logs(self, logs, sessions, newest=5):
        """The newest finished nights' flight logs, in its own words where written."""
        ended = {str(row.get("started") or "") for row in sessions or () if isinstance(row, dict) and row.get("ended")}
        shown = list(logs)
        for index, log in enumerate(shown[:newest]):
            if log.get("id") in ended and log.get("words"):
                words = self._watcher_own_words(f"log:{log['id']}", "flight log for one night", log["words"])
                if words:
                    shown[index] = {**log, "words": words, "own_words": True}
        return shown

    def _watcher_own_verdict(self, story, key):
        """Void Wrapped's verdict, in its own words where written."""
        cards = (story or {}).get("cards") or []
        for index, card in enumerate(cards):
            if card.get("kind") == "verdict" and card.get("words"):
                words = self._watcher_own_words(key, "verdict on the commander's travels", card["words"])
                if words:
                    cards = list(cards)
                    cards[index] = {**card, "words": words, "own_words": True}
                    return {**story, "cards": cards}
        return story

    def _watcher_mind_downloader(self):
        download = getattr(self, "_watcher_mind_download", None)
        if download is None:
            download = llm_assets.MindDownload()
            self._watcher_mind_download = download
        return download

    def _watcher_mind_start_download(self):
        started = self._watcher_mind_downloader().start(self._watcher_llm().choice(), self._watcher_mind_downloaded)
        self._watcher_mind_progress()
        return started

    def _watcher_mind_progress(self):
        download = getattr(self, "_watcher_mind_download", None)
        if download is None or getattr(self, "_closing", False):
            return
        self._schedule_html_dashboard_publish(immediate=True)
        if download.running():
            self._watcher_mind_progress_job = self.root.call_later(700, self._watcher_mind_progress)

    def _watcher_mind_downloaded(self, state):
        stage = state.get("stage")
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            if stage == "done":
                feed("SYSTEM", "The Watcher's own words are downloaded and loading", severity="INFO")
            elif stage == "failed":
                feed("SYSTEM", f"The Watcher's own words didn't download: {state.get('error')}", severity="WARNING")
        work = lambda: (self._watcher_llm().sync(), self._watcher_mind_watch(), self._watcher_sources().fill_vectors())
        post = getattr(self, "_ui_post", None)
        if callable(post):
            post(work, key="watcher-mind-download")
        else:
            work()

    def _watcher_mind_watch(self):
        """Keep the page moving while the model loads or a reply is awaited."""
        if getattr(self, "_closing", False):
            return
        self._schedule_html_dashboard_publish(immediate=True)
        hud = getattr(self, "heartbeat_hud", None)
        mind = getattr(hud, "mind", None)
        loading = self._watcher_llm().state()["stage"] == "loading"
        if loading or (mind is not None and mind.talk_waiting()):
            self._watcher_mind_watch_job = self.root.call_later(600, self._watcher_mind_watch)

    def _html_watcher_mind(self, mind):
        llm = self._watcher_llm()
        download = getattr(self, "_watcher_mind_download", None)
        choice = llm.choice()
        state = download.state() if download is not None else {"stage": "idle", "done": 0, "total": 0, "error": ""}
        talk = [{"at": row.get("at"), "you": str(row.get("you") or ""), "it": str(row.get("it") or ""),
                 "voice": bool(row.get("voice"))}
                for row in (mind.memory.get("talk") or [])[-20:] if isinstance(row, dict)]
        happened = [row for row in mind.memory.get("happened") or [] if isinstance(row, dict)]
        hud = getattr(self, "heartbeat_hud", None)
        return {
            "enabled": bool(self.config.get("watcher_llm_enabled")),
            "installed": llm.installed(),
            "model": choice,
            "models": [{"id": key, "name": row["name"], "size_mb": round(row["size"] / 1_000_000),
                        "installed": llm_assets.installed(key)} for key, row in llm_assets.MODELS.items()],
            "device": llm.device(),
            "reword": bool(self.config.get("watcher_llm_reword", True)),
            "free_idle": bool(self.config.get("watcher_llm_free_idle")),
            "own_thoughts": bool(self.config.get("watcher_llm_own_thoughts", True)),
            "keeps_diary": bool(self.config.get("watcher_llm_diary", True)),
            # What it has seen you do, and its diary (5.7.1), newest first.
            "seen": [{"at": row.get("t"), "text": str(row.get("text") or "")} for row in reversed(happened[-14:])],
            "seen_count": len(happened),
            "diary": [{"at": row.get("at"), "text": str(row.get("text") or "")}
                      for row in reversed((mind.memory.get("diary") or [])[-20:]) if isinstance(row, dict)],
            "download": state,
            "download_mb": round(llm_assets.download_bytes(choice) / 1_000_000),
            **llm.state(),
            "notice": llm_assets.NOTICE,
            "talk": talk,
            # 5.7.1: what it said in its own words, newest first, and your votes on them.
            "said": self._html_watcher_said(mind),
            "liked": [{"at": row.get("at"), "topic": row.get("topic", ""), "text": row["text"]}
                      for row in reversed(mind.memory.get("liked") or []) if isinstance(row, dict) and row.get("text")],
            "disliked": [{"at": row.get("at"), "topic": row.get("topic", ""), "text": row["text"]}
                         for row in reversed(mind.memory.get("disliked") or []) if isinstance(row, dict) and row.get("text")],
            "waiting": bool(getattr(getattr(hud, "mind", None), "talk_waiting", lambda: False)()),
            "orb_on": hud is not None,
        }

    # -- the download --------------------------------------------------------
    def _watcher_voice_downloader(self):
        download = getattr(self, "_watcher_voice_download", None)
        if download is None:
            download = voice_assets.VoiceDownload()
            self._watcher_voice_download = download
        return download

    def _watcher_voice_start_download(self):
        """Start the download, and keep the Watcher page's progress moving."""
        started = self._watcher_voice_downloader().start(self._watcher_voice_downloaded)
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
                feed("SYSTEM", "The Watcher's voice is downloaded and ready", severity="INFO")
            elif stage == "failed":
                feed("SYSTEM", f"The Watcher's voice didn't download: {state.get('error')}", severity="WARNING")
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
            "heartbeat_thoughts": watcher_mind.frequency(self.config),
            "heartbeat_personality": watcher_mind.personality(self.config),
            "heartbeat_thought_side": thought_side_setting(self.config),
            "heartbeat_text_scale_percent": heartbeat_text_size(self.config.get("heartbeat_text_scale_percent")),
            "heartbeat_thought_colour": style["colour"],
            "heartbeat_thought_size": style["size"],
            "heartbeat_thought_hold": style["hold"],
            "heartbeat_thought_backdrop": style["backdrop"],
            "heartbeat_thought_heading": style["heading"],
            "text_sizes": list(HEARTBEAT_TEXT_SIZES),
        }

    def _html_watcher_voice(self, memory):
        download = getattr(self, "_watcher_voice_download", None)
        state = download.state() if download is not None else {"stage": "idle", "done": 0,
                                                                "total": voice_assets.DOWNLOAD_BYTES, "error": ""}
        speaker = getattr(self, "_watcher_voice", None)
        try:
            volume = int(float(self.config.get("watcher_voice_volume", 80)))
        except (TypeError, ValueError):
            volume = 80
        return {
            "enabled": bool(self.config.get("watcher_voice_enabled")),
            "installed": voice_assets.installed(),
            "download": state,
            "size_mb": round(voice_assets.DOWNLOAD_BYTES / 1_000_000),
            "rights": voice_assets.RIGHTS_NOTICE,
            "volume": max(0, min(100, volume)),
            "speed": str(self.config.get("watcher_voice_speed") or "standard"),
            "level": str(self.config.get("watcher_voice_level") or "every"),
            "speaking": bool(speaker is not None and speaker.live()),
            "finding": watcher_voice_lore.progress(memory),
            "orb_on": getattr(self, "heartbeat_hud", None) is not None,
        }

    def _html_watcher_extras(self, mind):
        """The Watcher page's settings, voice and what it knows of you."""
        return {"settings": self._html_watcher_settings(),
                "voice": self._html_watcher_voice(mind.memory),
                "habits": watcher_habits.summary(mind.memory, mind.bond()),
                # 5.7.1: the name the ship writes, what it calls you, how it says it.
                "name": watcher_name.page(mind.memory),
                # 5.7.1: its own words (experimental), and what it knows.
                "mind": self._html_watcher_mind(mind),
                # 5.7.1: talking to it by voice.
                "listen": self._html_watcher_listen(),
                "library": self._html_watcher_library(mind)}

    @staticmethod
    def _html_watcher_said(mind):
        liked = {row.get("text") for row in mind.memory.get("liked") or [] if isinstance(row, dict)}
        disliked = {row.get("text") for row in mind.memory.get("disliked") or [] if isinstance(row, dict)}
        return [{"at": row.get("at"), "topic": row.get("topic", ""), "text": row["text"],
                 "vote": "up" if row["text"] in liked else "down" if row["text"] in disliked else ""}
                for row in reversed((mind.memory.get("own_said") or [])[-20:]) if isinstance(row, dict) and row.get("text")]

    def _html_watcher_library(self, mind):
        """The Watcher page's LIBRARY (5.7.1): what its own mind may draw on."""
        memory = mind.memory
        note, when = getattr(self, "_watcher_teach_note", ("", 0.0))
        told = watcher_knowing.story_told(memory, limit=200)
        chapters = []
        for title, _words in told:
            if title not in chapters:
                chapters.append(title)
        return {
            "notes": [{"at": row.get("at"), "text": row["text"]} for row in watcher_knowing.notes(memory)],
            "taught": [{"at": row.get("at"), "text": row["text"]} for row in watcher_knowing.taught(memory)],
            "profile": watcher_knowing.profile(memory),
            "answers": watcher_knowing.answers(memory),
            "about": ({"text": about["text"], "at": about.get("at")}
                      if (about := watcher_knowing.about_you(memory)) else None),
            "story_told": len(told),
            "teach_note": note if time.time() - when < 10 else "",
            "chapters": chapters,
            "galaxy": watcher_world.library(),
            # 5.7.1: the pages you gave it to read.
            "sources": self._html_watcher_sources(),
        }

    def _handle_watcher_settings_command(self, operation, payload):
        """The Watcher page's own controls. True when handled and done."""
        if operation == "settings":
            values = payload.get("values") if isinstance(payload.get("values"), dict) else {}
            selects = {key: values[key] for key in WATCHER_SELECTS if key in values}
            done = True
            if selects:
                done = bool(self._html_overlay_settings_save(selects))
            for key in WATCHER_SWITCHES:
                if key in values:
                    done = bool(self._html_overlay_option_toggle(key, bool(values[key]))) and done
            return done
        if operation == "voice_toggle":
            self.config["watcher_voice_enabled"] = bool(payload.get("value"))
            self._persist_config()
            if self.config["watcher_voice_enabled"] and not voice_assets.installed():
                self._watcher_voice_start_download()
            self._watcher_voice_sync()
            return True
        if operation == "voice_settings":
            values = payload.get("values") if isinstance(payload.get("values"), dict) else {}
            if "watcher_voice_volume" in values:
                try:
                    self.config["watcher_voice_volume"] = max(0, min(100, int(float(values["watcher_voice_volume"]))))
                except (TypeError, ValueError):
                    return False
            if values.get("watcher_voice_speed") in SPEEDS:
                self.config["watcher_voice_speed"] = values["watcher_voice_speed"]
            if values.get("watcher_voice_level") in LEVELS:
                self.config["watcher_voice_level"] = values["watcher_voice_level"]
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
            done = voice_assets.remove()
            self._watcher_voice_sync()
            return done
        if operation == "voice_test":
            if (not voice_assets.installed() or self._watcher_voice_boot_held()
                    or getattr(self, "_closing", False)):
                return False
            return self._watcher_speaker().say(TEST_LINE, "test")
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
        if operation == "mind_toggle":
            self.config["watcher_llm_enabled"] = bool(payload.get("value"))
            self._persist_config()
            if self._watcher_mind_needs_download():
                self._watcher_mind_start_download()
            self._watcher_llm().sync()
            self._watcher_mind_watch()
            return True
        if operation == "mind_settings":
            values = payload.get("values") if isinstance(payload.get("values"), dict) else {}
            if values.get("watcher_llm_model") in llm_assets.MODELS:
                self.config["watcher_llm_model"] = values["watcher_llm_model"]
            if values.get("watcher_llm_device") in watcher_llm.DEVICES:
                self.config["watcher_llm_device"] = values["watcher_llm_device"]
            for key in ("watcher_llm_reword", "watcher_llm_free_idle", "watcher_llm_own_thoughts", "watcher_llm_diary"):
                if key in values:
                    self.config[key] = bool(values[key])
            self._persist_config()
            if self._watcher_mind_needs_download():
                self._watcher_mind_start_download()
            self._watcher_llm().sync()
            self._watcher_mind_watch()
            return True
        if operation == "mind_download":
            return self._watcher_mind_start_download()
        if operation == "mind_cancel":
            self._watcher_mind_downloader().cancel()
            return True
        if operation == "mind_remove":
            self._watcher_llm().stop()
            done = llm_assets.remove()
            self._schedule_html_dashboard_publish(immediate=True)
            return done
        if operation == "mind_talk":
            hud = getattr(self, "heartbeat_hud", None)
            mind = getattr(hud, "mind", None)
            if mind is None or not mind.talk(payload.get("text")):
                return False
            self._watcher_mind_watch()
            return True
        if operation in {"mind_teach", "mind_unteach", "mind_forget_note"}:
            # Its library (5.7.1): what you teach it, and its notes of what you said.
            mind = self._watcher_mind()
            text = " ".join(str(payload.get("text") or "").split())
            if operation == "mind_teach" and watcher_llm.BANNED.search(text):
                self._watcher_teach_note = ("That's something it never speaks of.", time.time())
                self._schedule_html_dashboard_publish(immediate=True)
                return False
            try:
                index = int(payload.get("index"))
            except (TypeError, ValueError):
                index = -1
            with mind.lock:
                if operation == "mind_teach":
                    error = watcher_knowing.teach(mind.memory, text, time.time())
                    done = not error
                else:
                    error = ""
                    done = watcher_knowing.forget(mind.memory, "taught" if operation == "mind_unteach" else "told_me", index)
            if operation == "mind_teach":
                # The command channel only says it arrived: why it wasn't kept
                # travels with the page.
                self._watcher_teach_note = (error, time.time())
            mind.save()
            self._schedule_html_dashboard_publish(immediate=True)
            return done
        if operation in {"library_add", "library_refresh", "library_remove", "library_cancel", "library_search"}:
            # Your own sources (5.7.1). Why one wasn't added travels with the page.
            sources = self._watcher_sources()
            if operation == "library_search":
                self._watcher_source_query = " ".join(str(payload.get("text") or "").split())[:80]
                return True
            if operation == "library_cancel":
                sources.cancel()
                return True
            if operation == "library_remove":
                return sources.remove(str(payload.get("id") or ""))
            if operation == "library_add":
                try:
                    pages = int(payload.get("pages") or 1)
                except (TypeError, ValueError):
                    pages = 1
                error = sources.add(payload.get("url"), follow=payload.get("follow") is True, pages=pages)
            else:
                error = sources.refresh(str(payload.get("id") or ""))
            self._watcher_source_note = (error, time.time())
            return not error
        if operation == "mind_rate":
            # 👍 / 👎 on a line in its own words (5.7.1): its tone, and what it steers clear of.
            mind = self._watcher_mind()
            done = mind.rate(payload.get("text"), str(payload.get("vote") or ""), str(payload.get("topic") or ""))
            mind.save()
            return done
        if operation == "mind_forget":
            mind = self._watcher_mind()
            with mind.lock:
                mind.memory["talk"] = []
            mind.save()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "name_hear":
            if (not voice_assets.installed() or self._watcher_voice_boot_held()
                    or getattr(self, "_closing", False)):
                return False
            known = watcher_name.record(self._watcher_mind().memory).get("known") or ""
            said = " ".join(str(payload.get("value") or "").split()) or watcher_name.auto_spoken(known)
            return bool(said) and self._watcher_speaker().say(f"{said}.", "test")
        return self._handle_watcher_listen_command(operation, payload)
