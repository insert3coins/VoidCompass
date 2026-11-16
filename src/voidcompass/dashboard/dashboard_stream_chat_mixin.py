"""Stream chat (5.8.3): your Twitch chat talks to your companion.

Viewers ask with commands (!where, !ship, !route, !session, !rigs, !ask…) and
the companion on watch answers in its own voice and on the Stream Chat
overlay. It welcomes newcomers and regulars by name, thanks raids, subs and
bits, lets chat name the worlds you're first to find, keeps
everyone's points and crew rank, and at the end rolls the stream's credits.

Kept safe for a stream: viewers' words are never said aloud (only their
names, filtered); answers wait while you're in danger or docking; a mute
key; cooldowns; nothing can press a key or change the ship; and !where
can give only the region, or where you were a while ago.
"""
from __future__ import annotations

import logging
import random
import time

from voidcompass.core import companions, stream_chat, stream_games
from voidcompass.core.config import get_active_profile, get_profile_file
from voidcompass.core.stream_crew import CrewStore, rank_of
from voidcompass.overlays import stream_chat_lines

TICK_MS = 1000
VOICE_GAP_S = 6.0          # between spoken replies
VOICE_QUEUE = 3            # more waiting than this and the rest go on the overlay only
CARD_S = 22.0              # how long an answer card stays on the overlay
CARDS = 4
BANNER_S = 9.0
WELCOME_BATCH_S = 20.0     # welcomes said together this often at most
RAID_QUIET_S = 120.0       # after a raid its crew aren't welcomed one by one
CREDITS_S = 75.0
MUTE_QUIET_S = 600.0       # !quiet from a moderator
FLAG_IN_DANGER, FLAG_INTERDICTED = 1 << 22, 1 << 23
WHERE_CHOICES = ("exact", "region", "delay10", "delay30")
COMMANDS = ("where", "ship", "route", "session", "rigs", "crew", "rank", "top", "ask", "name", "vote", "help", "commands")
MOD_COMMANDS = ("quiet", "unquiet", "credits")
# !ask: what a viewer may ask about. Credits, rebuy and missions stay private;
# places only when the stream says where you are.
ASK_TOPICS = {"survey", "life", "planet", "world", "codex", "ship", "cargo", "ranks", "record", "galnet", "music", "materials"}
ASK_PLACES = {"where", "route", "station", "factions", "market", "carrier", "expedition"}
PRIVATE_LINE = ("Credits:", "Rebuy", "Legal", "Wanted", "Bounty", "Fines")
# The overlay's look (Overlay Studio): a chat box in the Neon styles, or the
# Navigation HUD's frame ("hud").
STYLES = ("neon", "bubbles", "boxed", "clean", "card", "hud")
CARD_STYLES = ("synthwave", "cybernetik", "glitch2", "iridescent", "clearview", "bubble-trouble", "blossom-breeze", "snow-blaster",
               "cupids-aim", "champion", "construct", "electro-junkie", "sticker-bomb", "nova-pixel", "amused", "flow")
ACCENTS = ("#FF2BD6", "#00F0FF", "#9B5CFF", "#39FF88", "#FFC53D", "#FF7A45", "companion")
HEIGHTS = (360, 480, 600, 720, 900)
LINES_KEPT = 40
# Other bots' lines stay off the chat box.
CHAT_BOTS = {"streamelements", "nightbot", "moobot", "streamlabs", "fossabot", "wizebot", "soundalerts", "sery_bot"}


def _stream_text(value, limit=200):
    return " ".join(str(value or "").split())[:limit]


class DashboardStreamChatMixin:
    # -- the store and the connection ---------------------------------------------------
    def stream_crew_store(self):
        key = get_active_profile(getattr(self, "config", None) or {})
        store = getattr(self, "_stream_crew", None)
        if store is None or getattr(self, "_stream_crew_key", None) != key:
            store = CrewStore(get_profile_file(key, "stream_crew.json"))
            self._stream_crew, self._stream_crew_key = store, key
        return store

    def _stream_blocked_words(self):
        return [word.strip() for word in str(self.config.get("stream_chat_blocked") or "").split(",") if word.strip()]

    def _stream_chat_sync(self):
        """Connect, disconnect or switch channel to match Settings."""
        config = getattr(self, "config", None) or {}
        channel = stream_chat.channel_name(config.get("stream_chat_channel"))
        wanted = bool(config.get("stream_chat_enabled")) and bool(channel)
        client = getattr(self, "_stream_client", None)
        if client is not None and (not wanted or client.channel != channel):
            client.stop()
            self._stream_client = client = None
            watch = getattr(self, "_stream_live_watch", None)
            if watch is not None:
                watch.stop()
            self._stream_live_watch, self._stream_on_air = None, None
        if wanted and client is None:
            client = self._stream_client = stream_chat.TwitchChat(
                channel, on_event=self._stream_chat_received,
                on_status=lambda status, error: self._ui_post(self._stream_status_changed, status, error, key="stream-status"))
            client.start()
            self._stream_started = time.time()
            self._stream_session_reset()
            # Whether you're live: asked of Twitch once a minute.
            self._stream_on_air = None
            self._stream_live_watch = stream_chat.LiveWatch(
                channel, on_change=lambda live: self._ui_post(self._stream_on_air_changed, live, key="stream-live"))
            self._stream_live_watch.start()
        if not getattr(self, "_stream_ticking", False):
            self._stream_ticking = True
            self.root.call_later(TICK_MS, self._tick_stream_chat)
        self._stream_overlay_update()

    def _stream_chat_close(self):
        client = getattr(self, "_stream_client", None)
        if client is not None:
            client.stop()
        watch = getattr(self, "_stream_live_watch", None)
        if watch is not None:
            watch.stop()
        self._stream_client, self._stream_live_watch = None, None

    def _stream_on_air_changed(self, live, now=None):
        """You went live, or off air. Tonight's figures start when you go
        live, and stop counting when you go off air."""
        now = time.time() if now is None else now
        before = getattr(self, "_stream_on_air", None)
        self._stream_on_air = bool(live)
        session = getattr(self, "_stream_session", None)
        if live and before is not True:
            if before is False or session is None or session.get("ended"):
                self._stream_session_reset(now)
            else:
                # Chat was connected before Twitch said: the stream starts now.
                session["started"] = now
            words = "you're live"
        elif not live and before is True:
            if session is not None:
                session["ended"] = now
            words = "off air"
        else:
            words = ""
        if words:
            feed = getattr(self, "add_event_feed_entry", None)
            if callable(feed):
                feed("STREAM", f"Stream chat: {words}", severity="INFO")
        self._stream_overlay_update()
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish()

    def _stream_on_air_s(self, now=None):
        """How long tonight's stream has been (or was) on air, in seconds."""
        now = time.time() if now is None else now
        session = getattr(self, "_stream_session", None) or {}
        started = float(session.get("started") or now)
        return max(0.0, float(session.get("ended") or now) - started)

    def _stream_status_changed(self, status, error):
        previous = getattr(self, "_stream_status_seen", None)
        self._stream_status_seen = status
        if status != previous and status in ("connected", "reconnecting", "error"):
            feed = getattr(self, "add_event_feed_entry", None)
            if callable(feed):
                words = {"connected": f"Stream chat: listening to #{getattr(getattr(self, '_stream_client', None), 'channel', '')}",
                         "reconnecting": "Stream chat: reconnecting to Twitch", "error": f"Stream chat: {error}"}[status]
                feed("STREAM", words, severity="INFO" if status == "connected" else "WARN")
        self._stream_overlay_update()
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish()

    def _stream_chat_state(self):
        client = getattr(self, "_stream_client", None)
        return {"status": client.status if client is not None else "off", "error": client.error if client is not None else "",
                "channel": client.channel if client is not None else stream_chat.channel_name(self.config.get("stream_chat_channel")),
                "on_air": getattr(self, "_stream_on_air", None) if client is not None else None,
                "on_air_s": round(self._stream_on_air_s()) if client is not None and getattr(self, "_stream_on_air", None) is not None else None}

    def _stream_look(self):
        """How the overlay looks, from Overlay Studio."""
        config = self.config
        style = str(config.get("stream_chat_style") or "neon")
        card = str(config.get("stream_chat_card") or "synthwave")
        accent = str(config.get("stream_chat_accent") or "#FF2BD6")
        try:
            height = int(config.get("stream_chat_height") or 480)
        except (TypeError, ValueError):
            height = 480
        return {"style": style if style in STYLES else "neon", "card": card if card in CARD_STYLES else "synthwave",
                "accent": accent if accent in ACCENTS else "#FF2BD6", "height": height if height in HEIGHTS else 480,
                "show_chat": bool(config.get("stream_chat_show_chat", True))}

    def _stream_add_line(self, line):
        """One more line for the chat box: viewers, the companion and events, in order."""
        lines = self.__dict__.setdefault("_stream_lines", [])
        self._stream_line_seq = getattr(self, "_stream_line_seq", 0) + 1
        lines.append({"id": f"l{self._stream_line_seq}", "at": time.time(), **line})
        del lines[:-LINES_KEPT]

    # -- tonight's figures, for !session and the credits ---------------------------------
    def _stream_session_reset(self, now=None):
        self._stream_session = {"started": time.time() if now is None else now, "ended": None, "jumps": 0, "ly": 0.0, "scans": 0, "firsts": 0, "mapped": 0,
                                "bio": 0, "tonnes": 0, "earned": 0, "systems": []}

    def _stream_session_note(self, event, raw):
        if getattr(self, "_stream_on_air", None) is False:
            return      # off air: your flying isn't the stream's
        session = getattr(self, "_stream_session", None)
        if session is None:
            self._stream_session_reset()
            session = self._stream_session
        if event == "FSDJump":
            session["jumps"] += 1
            session["ly"] += float(raw.get("JumpDist") or 0)
            if raw.get("StarSystem"):
                session["systems"] = (session["systems"] + [str(raw["StarSystem"])])[-400:]
        elif event == "Scan" and raw.get("ScanType") in ("Detailed", "AutoScan", "Basic", "NavBeaconDetail"):
            session["scans"] += 1
            from voidcompass.core.discovery import our_first
            try:
                if our_first(raw):
                    session["firsts"] += 1
            except Exception:
                pass
        elif event == "SAAScanComplete":
            session["mapped"] += 1
        elif event == "ScanOrganic" and raw.get("ScanType") == "Analyse":
            session["bio"] += 1
        elif event == "MiningRefined":
            session["tonnes"] += 1
        elif event == "MarketSell":
            session["earned"] += int(raw.get("TotalSale") or 0)
        elif event in ("SellExplorationData", "MultiSellExplorationData"):
            session["earned"] += int(raw.get("TotalEarnings") or 0)
        elif event == "SellOrganicData":
            session["earned"] += sum(int(row.get("Value") or 0) + int(row.get("Bonus") or 0) for row in raw.get("BioData") or ()
                                     if isinstance(row, dict))
        elif event == "RedeemVoucher":
            session["earned"] += int(raw.get("Amount") or 0)

    # -- where you are, as the stream may hear it -----------------------------------------
    def _stream_where_mode(self):
        mode = str(self.config.get("stream_chat_where") or "region")
        return mode if mode in WHERE_CHOICES else "region"

    def _stream_note_place(self):
        history = self.__dict__.setdefault("_stream_places", [])
        place = (str(getattr(self, "current_sys", "") or ""), str(getattr(self, "current_body_name", "") or ""))
        if place[0] and (not history or history[-1][1:] != place):
            history.append((time.time(), *place))
            del history[:-200]

    def _stream_region(self):
        try:
            from voidcompass.orders.places import region_of
            return region_of(list(getattr(self, "current_coords", None) or ()))[1] or ""
        except Exception:
            return ""

    def _stream_doing(self):
        if getattr(self, "current_docked", False):
            return "docked"
        if getattr(self, "current_on_foot", False):
            return "on foot"
        if getattr(self, "current_in_srv", False):
            vehicle = str(getattr(self, "current_vehicle_name", "") or "").upper()
            return "in the Rhino" if "RHINO" in vehicle else "in the SRV"
        if getattr(self, "current_landed", False):
            return "landed"
        if getattr(self, "on_planet", False):
            return "flying low over a planet"
        return ""

    def _stream_where(self):
        mode = self._stream_where_mode()
        doing = self._stream_doing()
        system = str(getattr(self, "current_sys", "") or "")
        body = str(getattr(self, "current_body_name", "") or "")
        if mode == "region":
            region = self._stream_region()
            words = f"Somewhere in {region}" if region else "Out in the black"
            return f"{words}, {doing}." if doing else f"{words}."
        if mode.startswith("delay"):
            minutes = int(mode[5:])
            then = time.time() - minutes * 60
            past = [row for row in getattr(self, "_stream_places", None) or () if row[0] <= then]
            if not past:
                return f"I'll say where we were {minutes} minutes from now. Stream-sniping rules."
            _at, system, body = past[-1]
            return f"{minutes} minutes ago: {body or system}" + (f", in {system}" if body and not body.startswith(system) else "") + "."
        station = str(getattr(self, "current_station_name", "") or "")
        if getattr(self, "current_docked", False) and station:
            return f"Docked at {station}, in {system}."
        if body and body != system:
            if doing.startswith("flying"):
                return f"Flying low over {body}."
            return f"{doing[:1].upper() + doing[1:]} on {body}." if doing else f"Near {body}."
        return f"In {system}." if system else "Somewhere I can't name yet."

    # -- incoming ----------------------------------------------------------------------
    def _stream_chat_received(self, event):
        """From the chat thread: handled on the UI thread."""
        self._ui_post(self._stream_chat_handle, event)

    def _stream_chat_handle(self, event, now=None):
        now = time.time() if now is None else now
        kind = event.get("kind")
        login = str(event.get("login") or "")
        if kind in ("delete", "clear_user", "clear"):
            return self._stream_deleted(kind, event)
        if not login and kind == "chat":
            return None
        extra = self._stream_blocked_words()
        speakable = stream_chat.spoken_name(event.get("name"), extra)
        store = self.stream_crew_store()
        shown = event.get("name") if event.get("name") and not stream_chat.blocked(event.get("name"), extra) else "Someone"
        if kind in ("raid", "sub", "gift"):
            words = {"raid": f"raided with {int(event.get('viewers') or 0)}", "sub": f"subscribed · {int(event.get('months') or 1)} months",
                     "gift": f"gifted {int(event.get('count') or 1)} sub{'s' if int(event.get('count') or 1) != 1 else ''}"}[kind]
            self._stream_add_line({"kind": "event", "type": kind, "who": shown, "text": words})
        if kind == "raid":
            store.note("raid", {"name": event.get("name"), "viewers": int(event.get("viewers") or 0), "at": round(now)}, now)
            self._stream_raid_until = now + RAID_QUIET_S
            self._stream_line("raid", banner="raid", name=speakable or "a friend", viewers=int(event.get("viewers") or 0))
            return "raid"
        if kind == "sub":
            store.note("sub", {"name": event.get("name"), "months": int(event.get("months") or 1), "at": round(now)}, now)
            self._stream_line("sub", banner="sub", name=speakable or "Someone", months=int(event.get("months") or 1))
            return "sub"
        if kind == "gift":
            store.note("gift", {"name": event.get("name"), "count": int(event.get("count") or 1), "at": round(now)}, now)
            self._stream_line("gift", banner="sub", name=speakable or "Someone", count=int(event.get("count") or 1))
            return "gift"
        if kind != "chat":
            return None
        seen = store.seen(login, event.get("name") or login, now)
        text = str(event.get("text") or "")
        if self._stream_look()["show_chat"] and not text.lstrip().startswith("!") and login not in CHAT_BOTS                 and not stream_chat.blocked(text, extra) and not stream_chat.blocked(event.get("name"), extra):
            self._stream_add_line({"kind": "chat", "msg": str(event.get("id") or ""), "login": login,
                                   "who": str(event.get("name") or login), "color": event.get("color") or "",
                                   "badges": list(event.get("badges") or ([] if not event.get("broadcaster") else ["broadcaster"])),
                                   "fragments": event.get("fragments") or [{"type": "text", "text": text}],
                                   "first": bool(seen["new"]), "back": bool(seen["back"])})
        if int(event.get("bits") or 0) > 0:
            self._stream_add_line({"kind": "event", "type": "bits", "who": shown, "text": f"cheered {int(event['bits'])} bits"})
            store.note("bits", {"bits": int(event["bits"])}, now)
            self._stream_line("bits", banner="sub", name=speakable or "Someone", bits=int(event["bits"]))
        if seen["first_this_stream"] and not event.get("broadcaster") and self.config.get("stream_chat_welcomes", True)                 and now >= getattr(self, "_stream_raid_until", 0):
            self.__dict__.setdefault("_stream_welcomes", []).append((login, speakable, seen))
        asked = stream_chat.command_of(event.get("text"))
        if not asked:
            return None
        command, rest = asked
        mod = bool(event.get("mod") or event.get("broadcaster"))
        if command in MOD_COMMANDS:
            return self._stream_mod_command(command, mod, now) if mod else None
        if command not in COMMANDS:
            return None
        who = {"login": login, "name": str(event.get("name") or login), "speak": speakable, "color": event.get("color") or "",
               "badge": "broadcaster" if event.get("broadcaster") else "mod" if event.get("mod") else "sub" if event.get("sub") else ""}
        if command in ("name", "vote"):
            return self._stream_play(who, command, rest, now)
        last = self.__dict__.setdefault("_stream_asked", {})
        cooldown = max(5, int(self.config.get("stream_chat_cooldown_s") or 20))
        if not mod and now - last.get((login, command), -1e9) < cooldown:
            return None
        last[(login, command)] = now
        try:
            answer = self._stream_answer(command, rest, who)
        except Exception:
            logging.debug("Stream chat: %s not answered", command, exc_info=True)
            answer = None
        if answer:
            self._stream_reply(who, f"!{command}", answer)
        return answer

    def _stream_deleted(self, kind, event):
        """A moderator deleted chat: the box follows. One message goes by its
        id; a viewer timed out or banned loses all their lines, the answers
        to them and their welcome, and their guesses and suggestions in a
        game; /clear empties the box."""
        lines = getattr(self, "_stream_lines", None) or []
        cards = getattr(self, "_stream_cards", None) or []
        before = len(lines) + len(cards)
        if kind == "delete":
            target = str(event.get("id") or "")
            if not target:
                return None
            self._stream_lines = [line for line in lines if not (line.get("kind") == "chat" and line.get("msg") == target)]
        elif kind == "clear_user":
            login = str(event.get("login") or "").lower()
            if not login:
                return None
            self._stream_lines = [line for line in lines if line.get("login") != login and line.get("to_login") != login]
            self._stream_cards = [card for card in cards if card.get("login") != login]
            self._stream_welcomes = [row for row in getattr(self, "_stream_welcomes", None) or () if row[0] != login]
            game = getattr(self, "_stream_game", None)
            if game is not None and not game.done:
                game.guesses.pop(login, None)
                if isinstance(game, stream_games.NameGame):
                    game.votes.pop(login, None)
                    if game.stage == "suggest":
                        game.choices = [choice for choice in game.choices if choice[1] != login]
        else:
            self._stream_lines, self._stream_cards = [], []
        removed = before - len(getattr(self, "_stream_lines", None) or []) - len(getattr(self, "_stream_cards", None) or [])
        self._stream_overlay_update()
        return removed

    def _stream_mod_command(self, command, mod, now):
        if command == "quiet":
            self._stream_muted_until = now + MUTE_QUIET_S
            self._stream_voice_queue = []
            self._stream_banner("muted", "Quiet for ten minutes: a moderator asked")
        elif command == "unquiet":
            self._stream_muted_until = 0
            self._stream_banner("muted", "Back on air")
        elif command == "credits":
            self._stream_credits(now)
        self._stream_overlay_update()
        return command

    # -- answers ------------------------------------------------------------------------
    def _stream_answer(self, command, rest, who):
        if command in ("help", "commands"):
            return ("!where · !ship · !route · !session · !rigs · !crew · !rank · !top · !ask a question. "
                    "When a world needs a name: !name, then !vote.")
        if command == "where":
            return self._stream_where()
        if command == "ship":
            from voidcompass.core.ship_names import ship_name
            ship = getattr(self, "cmdr_ship", None) or {}
            kind = ship_name(ship.get("ship"), ship.get("ship_localised")) if ship.get("ship") else ""
            name = _stream_text(ship.get("ship_name"), 40)
            jump = self._expedition_jump_range() if hasattr(self, "_expedition_jump_range") else 0
            if not kind:
                return "The ship hasn't told me what it is yet."
            words = f"A {kind}" + (f", the {name}" if name else "")
            return words + (f". Jump range {float(jump):.1f} light years." if jump else ".")
        if command == "route":
            nav = self._build_navigation_hud_context() if hasattr(self, "_build_navigation_hud_context") else {}
            remaining = (nav or {}).get("route_remaining")
            if not (nav or {}).get("next") or str(nav.get("next")) == "---":
                return "No route plotted right now."
            if self._stream_where_mode() != "exact":
                return f"{remaining} jumps to go on the route." if remaining else "On a route. Where to stays a secret."
            from voidcompass.overlays import watcher_copilot
            return " ".join(line.rstrip(".") + "." for line in watcher_copilot.route_lines(nav)[:3])
        if command == "session":
            return self._stream_session_words()
        if command == "rigs":
            return self._stream_rigs_words()
        if command == "crew":
            summary = self.stream_crew_store().summary()
            return (f"{companions.name(self.config)} is on watch. {summary['chatters']} crew in chat tonight, "
                    f"{summary['crew']} all told.")
        if command == "rank":
            viewer = self.stream_crew_store().viewer(who["login"]) or {}
            title, to_next, nxt = rank_of(viewer.get("points"))
            points = int(viewer.get("points") or 0)
            tail = f" {to_next} more to {nxt}." if nxt else " The top of the ladder."
            return f"{who['name']}: {title}, {points} point{'s' if points != 1 else ''}.{tail}"
        if command == "top":
            tonight = "tonight" in rest.lower()
            rows = self.stream_crew_store().top(3, this_stream=tonight)
            if not rows:
                return "Nobody's on the board yet. Name a world we discover to get there."
            return ("Top tonight: " if tonight else "Top crew: ") + ", ".join(f"{row['name']} {row['points']}" for row in rows) + "."
        if command == "ask":
            return self._stream_ask(rest)
        return None

    def _stream_session_words(self):
        session = getattr(self, "_stream_session", None) or {}
        minutes = int(self._stream_on_air_s() // 60)
        if getattr(self, "_stream_on_air", None) is False and not session.get("ended"):
            return "Off air right now. Catch the next stream!"
        parts = [f"{minutes // 60} h {minutes % 60:02d} min on air" if minutes >= 60 else f"{minutes} min on air"]
        if session.get("jumps"):
            parts.append(f"{session['jumps']} jumps, {round(session.get('ly') or 0):,} light years")
        if session.get("scans"):
            parts.append(f"{session['scans']} bodies scanned")
        if session.get("firsts"):
            parts.append(f"{session['firsts']} first discoveries")
        if session.get("bio"):
            parts.append(f"{session['bio']} biology samples")
        if session.get("tonnes"):
            parts.append(f"{session['tonnes']} tonnes refined")
        if session.get("earned"):
            from voidcompass.mining.rhino_report import credits_text
            parts.append(f"{credits_text(session['earned'])} credits earned")
        if getattr(self, "_stream_on_air", None) is False:
            return "Off air now. The last stream: " + ", ".join(parts) + "."
        return "Tonight: " + ", ".join(parts) + "."

    def _stream_rigs_words(self):
        rigs = (self.api_rigs() if hasattr(self, "api_rigs") else {}).get("rigs") or []
        if not rigs:
            return "No rigs out right now."
        words = []
        for rig in sorted(rigs, key=lambda row: int(row.get("slot") or 0)):
            slot = rig.get("slot")
            if rig.get("collecting"):
                words.append(f"rig {slot} collecting")
            elif rig.get("ready"):
                words.append(f"rig {slot} READY")
            elif rig.get("ready_s") and rig.get("fill_s") is not None:
                left = max(0, int(float(rig["ready_s"]) - float(rig["fill_s"])))
                words.append(f"rig {slot} in {left // 60}:{left % 60:02d}")
            else:
                words.append(f"rig {slot} filling")
        text = ", ".join(words)
        return text[:1].upper() + text[1:] + "."

    def _stream_ask(self, question):
        """A plain question about the game, answered from what the ship shows:
        never an action, never private figures, and places only if the stream
        says where you are."""
        from voidcompass.overlays import watcher_copilot
        question = _stream_text(question, 200)
        if len(question) < 3:
            return "Ask me something: !ask how many bodies are here?"
        exact = self._stream_where_mode() == "exact"
        allowed = ASK_TOPICS | (ASK_PLACES if exact else set())
        topics = [topic for topic in watcher_copilot.topics_for(question) if topic in allowed]
        if not topics:
            return ("I can answer about the ship, this system's bodies and life, planets, ranks and Galnet."
                    + ("" if exact else " Where we are stays off air."))
        lines = []
        from voidcompass.dashboard.dashboard_watcher_voice_mixin import ASKS_THE_QUESTION
        for topic in topics:
            lookup = getattr(self, f"_watcher_lookup_{topic}", None)
            if not callable(lookup):
                continue
            try:
                lines += lookup(question) if topic in ASKS_THE_QUESTION else lookup()
            except Exception:
                logging.debug("Stream chat: !ask %s skipped", topic, exc_info=True)
        lines = [str(line) for line in lines if line and not str(line).startswith(PRIVATE_LINE)]
        if not exact:
            hidden = [str(getattr(self, "current_sys", "") or ""), str(getattr(self, "current_body_name", "") or ""),
                      str(getattr(self, "current_station_name", "") or "")]
            for name in sorted((name for name in hidden if len(name) > 2), key=len, reverse=True):
                lines = [line.replace(name, "here") for line in lines]
        return watcher_copilot.plain_answer(lines, limit=3) or "Nothing on the instruments about that."

    # -- saying it ------------------------------------------------------------------------
    def _stream_rng(self):
        rng = getattr(self, "_stream_random", None)
        if rng is None:
            rng = self._stream_random = random.Random()
        return rng

    def _stream_identity(self):
        return companions.identity(getattr(self, "config", None) or {})

    def _stream_reply(self, who, asked, answer):
        """An answer: a card on the overlay, and said aloud with the viewer's
        name (if it's safe to say) unless replies are muted or busy."""
        shown = who["name"] if not stream_chat.blocked(who["name"], self._stream_blocked_words()) else "A viewer"
        card = {"id": f"{time.time():.3f}", "login": who.get("login") or "", "who": shown, "color": who.get("color") or "", "badge": who.get("badge") or "",
                "asked": asked, "text": answer, "at": time.time(), "kind": "answer"}
        cards = self.__dict__.setdefault("_stream_cards", [])
        cards.insert(0, card)
        del cards[CARDS:]
        self._stream_add_line({"kind": "reply", "who": companions.name(self.config), "identity": self._stream_identity(),
                               "to": shown, "to_login": who.get("login") or "", "asked": asked, "text": answer})
        prefix = stream_chat_lines.line(self._stream_identity(), "asked", self._stream_rng(), name=who["speak"]) if who.get("speak") else ""
        self._stream_speak(prefix + answer)
        self._stream_overlay_update()
        api = getattr(self, "_api_publish", None)
        if callable(api):
            api("stream", {"kind": "answer", "who": who["name"], "asked": asked, "text": answer})

    def _stream_line(self, key, banner=None, **fields):
        """One of the companion's own lines (a welcome, thanks, a game's
        call or result, a promotion): in the chat box and as a banner, but
        never said aloud. It only speaks to answer a command."""
        text = stream_chat_lines.line(self._stream_identity(), key, self._stream_rng(), **fields)
        self._stream_add_line({"kind": "companion", "who": companions.name(self.config), "identity": self._stream_identity(), "text": text})
        if banner:
            self._stream_banner(banner, text)
        return text

    def _stream_banner(self, kind, text):
        """A banner: shown in turn, each for BANNER_S, so a result isn't
        lost under the promotion that follows it."""
        queue = self.__dict__.setdefault("_stream_banners", [])
        if kind == "raid":
            queue.insert(0, {"kind": kind, "text": text, "at": None})   # a raid goes straight up
        else:
            queue.append({"kind": kind, "text": text, "at": None})
        del queue[6:]
        self._stream_overlay_update()

    def _stream_banner_shown(self, now):
        queue = getattr(self, "_stream_banners", None) or []
        while queue and queue[0]["at"] is not None and now - queue[0]["at"] > BANNER_S:
            queue.pop(0)
        if queue and queue[0]["at"] is None:
            queue[0]["at"] = now
        return queue[0] if queue else None

    def _stream_muted(self):
        return time.time() < float(getattr(self, "_stream_muted_until", 0) or 0)

    def _stream_holding(self):
        """Busy flying: replies wait (in danger, interdicted, docking)."""
        flags = int(getattr(self, "current_status_flags", 0) or 0)
        quiet = time.monotonic() < float(getattr(self, "_danger_quiet_until", 0.0) or 0.0)
        danger = bool(flags & FLAG_IN_DANGER) and not quiet and not getattr(self, "current_docked", False)
        return danger or bool(flags & FLAG_INTERDICTED) or bool(getattr(self, "_stream_docking", False))

    def _stream_speak(self, text):
        if not text or not self.config.get("stream_chat_voice", True) or self._stream_muted():
            return False
        queue = self.__dict__.setdefault("_stream_voice_queue", [])
        if len(queue) >= VOICE_QUEUE:
            return False         # busy: it's on the overlay
        queue.append(text)
        return True

    def _stream_voice_due(self, now):
        queue = getattr(self, "_stream_voice_queue", None)
        if not queue or self._stream_muted() or self._stream_holding():
            return None
        if now - float(getattr(self, "_stream_voice_at", 0) or 0) < VOICE_GAP_S:
            return None
        text = queue.pop(0)
        self._stream_voice_at = now
        mind = getattr(self, "_orders_mind", lambda: None)()
        if mind is not None and hasattr(mind, "crew_say"):
            try:
                mind.crew_say(self._stream_identity(), text, heading="STREAM CHAT", topic="stream_chat", converse=False)
            except Exception:
                logging.debug("Stream chat line not said", exc_info=True)
        return text

    def _stream_welcome_due(self, now):
        waiting = getattr(self, "_stream_welcomes", None)
        if not waiting or now - float(getattr(self, "_stream_welcome_at", 0) or 0) < WELCOME_BATCH_S:
            return None
        self._stream_welcomes = []
        self._stream_welcome_at = now
        new = [row for row in waiting if row[2]["new"]]
        back = [row for row in waiting if not row[2]["new"]]
        said = []
        if new:
            names = [row[1] for row in new if row[1]]
            said.append(self._stream_line("welcome_new", name=stream_chat_lines.names_text(names)) if names
                        else self._stream_line("welcome_anon"))
        if back:
            named = [row for row in back if row[1]]
            if len(named) == 1:
                said.append(self._stream_line("welcome_back", name=named[0][1], streams=named[0][2]["streams"]))
            elif named:
                said.append(self._stream_line("welcome_back", name=stream_chat_lines.names_text([row[1] for row in named]),
                                              streams=max(row[2]["streams"] for row in named)))
        self._stream_banner("welcome", " · ".join(said))
        return said

    # -- the games ---------------------------------------------------------------------
    def _stream_game_ok(self, now, kind):
        if not self.config.get("stream_chat_enabled") or getattr(self, "_stream_client", None) is None:
            return False
        if not self.config.get("stream_chat_naming", True):
            return False
        game = getattr(self, "_stream_game", None)
        if game is not None and not game.done:
            return False
        gap = max(0, int(self.config.get("stream_chat_game_gap_min") or 3)) * 60
        return now - float(getattr(self, "_stream_game_started", 0) or 0) >= gap

    def _stream_open(self, game, key, **fields):
        self._stream_game = game
        self._stream_game_started = game.opened
        self.stream_crew_store().stream(game.opened)["games"] = int(self.stream_crew_store().stream(game.opened).get("games") or 0) + 1
        self._stream_line(key, **fields)
        self._stream_overlay_update()

    def _stream_play(self, who, command, rest, now):
        game = getattr(self, "_stream_game", None)
        if game is None or game.done:
            return None
        if command == "name" and isinstance(game, stream_games.NameGame):
            text = stream_chat.shown_text(rest, self._stream_blocked_words())
            taken = game.suggest(who["login"], who["name"], text, now) or None
            if taken and len(game.choices) >= 4:
                game.start_vote(now)
                self._stream_line("name_vote")
        elif command == "vote" and isinstance(game, stream_games.NameGame):
            taken = game.vote(who["login"], who["name"], rest, now)
        else:
            taken = None
        if taken is not None:
            self._stream_overlay_update()
        return taken

    def _stream_settle(self, game, answer, key, **fields):
        winners = game.settle(answer)
        store = self.stream_crew_store()
        names = []
        for login, name, points in winners:
            _points, promoted = store.award(login, name, points)
            names.append(stream_chat.spoken_name(name, self._stream_blocked_words()) or name)
            if promoted:
                speak = stream_chat.spoken_name(name, self._stream_blocked_words())
                if speak:
                    self.__dict__.setdefault("_stream_promotions", []).append((speak, promoted))
        for speak, rank in getattr(self, "_stream_promotions", None) or ():
            self._stream_line("rank_up", banner="rank", name=speak, rank=rank)
        self._stream_promotions = []
        self._stream_overlay_update()
        return winners

    def _stream_chat_event(self, event, raw, startup_replay=False):
        """The journal, for the games, the figures and where you are."""
        if startup_replay or not isinstance(raw, dict):
            return
        try:
            self._stream_session_note(event, raw)
            if event in ("FSDJump", "Location", "CarrierJump", "ApproachBody", "LeaveBody", "Docked", "Touchdown"):
                self._stream_note_place()
            if event == "DockingGranted":
                self._stream_docking = True
            elif event in ("Docked", "DockingCancelled", "DockingTimeout", "DockingDenied", "Undocked"):
                self._stream_docking = False
            self._stream_game_event(event, raw, time.time())
        except Exception:
            logging.debug("Stream chat: %s not taken in", event, exc_info=True)

    def _stream_game_event(self, event, raw, now):
        if event == "Scan" and self._stream_game_ok(now, "name"):
            from voidcompass.core.discovery import our_first
            kind = str(raw.get("PlanetClass") or "").casefold()
            notable = stream_games.NOTABLE_WORLDS.get(kind) or ("terraformable world" if raw.get("TerraformState") == "Terraformable" else "")
            if notable and raw.get("BodyName") and our_first(raw):
                system = str(raw.get("StarSystem") or getattr(self, "current_sys", "") or "")
                body = str(raw["BodyName"])
                if self.stream_crew_store().world_name(system, body) is None:
                    from voidcompass.mining.rhino_report import short_body
                    world = short_body(system, body) or body
                    self._stream_open(stream_games.NameGame(now=now, system=system, body=body, world=world, notable=notable),
                                      "name_open", world=f"{world}, a {notable}")

    def _stream_game_tick(self, now):
        game = getattr(self, "_stream_game", None)
        if game is None:
            return
        if game.done:
            if now - float(getattr(self, "_stream_game_done_at", now) or now) > 25:
                self._stream_game = None
                self._stream_overlay_update()
            return
        if isinstance(game, stream_games.NameGame):
            if game.stage == "suggest" and not game.open_for(now):
                if len(game.choices) >= 2:
                    game.start_vote(now)
                    self._stream_line("name_vote")
                elif game.choices:
                    self._stream_name_won(game, now)
                else:
                    game.done, self._stream_game = True, None
            elif game.stage == "vote" and not game.open_for(now):
                self._stream_name_won(game, now)
        self._stream_overlay_update()

    def _stream_name_won(self, game, now):
        found = game.winner()
        self._stream_game_done_at = now
        if found:
            # The name goes up first; the points and any promotions after it.
            name, _login, by, _votes = found
            self.stream_crew_store().name_world(game.facts["system"], game.facts["body"], name, by, now)
            speak = stream_chat.spoken_name(by, self._stream_blocked_words()) or "chat"
            self._stream_banner("named", f"{game.facts.get('world')} · named “{name}” by {by}")
            self._stream_add_line({"kind": "companion", "who": companions.name(self.config), "identity": self._stream_identity(),
                                   "text": stream_chat_lines.line(self._stream_identity(), "name_won", self._stream_rng(), by=speak)})
        winners = self._stream_settle(game, None, "name_won")
        if not found:
            return winners
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            feed("STREAM", f"Chat named {game.facts.get('body')}: “{name}”, suggested by {by}", severity="INFO")
        return winners

    # -- the credits -------------------------------------------------------------------
    def _stream_credits_model(self, now=None):
        now = time.time() if now is None else now
        store = self.stream_crew_store()
        stream = store.stream(now)
        session = getattr(self, "_stream_session", None) or {}
        from voidcompass.mining.rhino_report import credits_text
        minutes = int(self._stream_on_air_s(now) // 60)
        figures = [("ON AIR", f"{minutes // 60} h {minutes % 60:02d} min")]
        for key, label, fmt in (("jumps", "JUMPS", "{:,}"), ("ly", "LIGHT YEARS", "{:,.0f}"), ("scans", "BODIES SCANNED", "{:,}"),
                                ("firsts", "FIRST DISCOVERIES", "{:,}"), ("bio", "BIOLOGY SAMPLES", "{:,}"),
                                ("tonnes", "TONNES REFINED", "{:,}")):
            if session.get(key):
                figures.append((label, fmt.format(session[key])))
        if session.get("earned"):
            figures.append(("CREDITS EARNED", credits_text(session["earned"])))
        crew = sorted(set((stream.get("chatters") or {}).values()), key=str.lower)
        return {
            "rolling": True, "started": stream.get("started"), "until": now + CREDITS_S,
            "title": f"{str(self.config.get('active_commander_name') or 'Commander').upper()} · TONIGHT'S FLIGHT",
            "companion": companions.name(self.config),
            "figures": [{"label": label, "value": value} for label, value in figures],
            "top": [{"name": row["name"], "points": row["points"], "rank": row["rank"]} for row in store.top(5, this_stream=True)],
            "raids": [{"name": row.get("name"), "viewers": row.get("viewers")} for row in stream.get("raids") or ()],
            "supporters": sorted({str(row.get("name")) for key in ("subs", "gifts") for row in stream.get(key) or () if row.get("name")}),
            "named": [{"world": row.get("body"), "name": row.get("name"), "by": row.get("by")} for row in stream.get("named") or ()],
            "crew": crew[:300], "bits": int(stream.get("bits") or 0),
            "signoff": stream_chat_lines.line(self._stream_identity(), "credits", self._stream_rng()),
        }

    def _stream_credits(self, now=None):
        """Roll the credits on the overlay: tonight's crew, winners, raids and named worlds."""
        model = self._stream_credits_model(now)
        self._stream_credits_now = model
        self._stream_speak(model["signoff"])
        self._stream_overlay_update()
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            feed("STREAM", f"Rolling the credits: {len(model['crew'])} crew tonight", severity="INFO")
        return model

    def _stream_mute_toggle(self):
        if self._stream_muted():
            self._stream_muted_until = 0
            words = "Stream chat replies back on"
        else:
            self._stream_muted_until = time.time() + 365 * 86400
            self._stream_voice_queue = []
            words = "Stream chat replies muted"
        toast = getattr(self, "toast_hud", None)
        if toast is not None and hasattr(toast, "push"):
            toast.push("STREAM CHAT", words, severity="info", duration_s=3.0)
        self._stream_overlay_update()
        return not self._stream_muted()

    # -- the tick and the overlay -----------------------------------------------------------
    def _tick_stream_chat(self):
        if not getattr(self, "is_running", True):
            self._stream_ticking = False
            return
        now = time.time()
        try:
            self._stream_welcome_due(now)
            self._stream_game_tick(now)
            self._stream_voice_due(now)
            credits = getattr(self, "_stream_credits_now", None)
            if credits and now > float(credits.get("until") or 0):
                self._stream_credits_now = None
            self._stream_overlay_update()
        except Exception:
            logging.debug("Stream chat tick skipped", exc_info=True)
        if getattr(self, "_stream_client", None) is None and not getattr(self, "_stream_credits_now", None) \
                and not getattr(self, "_stream_game", None):
            self._stream_ticking = False
            return
        self.root.call_later(TICK_MS, self._tick_stream_chat)

    def _stream_overlay_model(self, now=None):
        now = time.time() if now is None else now
        client = getattr(self, "_stream_client", None)
        credits = getattr(self, "_stream_credits_now", None)
        if client is None and not credits:
            return None
        cards = [card for card in getattr(self, "_stream_cards", None) or () if now - card["at"] < CARD_S]
        self._stream_cards = cards
        banner = self._stream_banner_shown(now)
        game = getattr(self, "_stream_game", None)
        model = {
            "status": client.status if client is not None else "off", "channel": client.channel if client is not None else "",
            "on_air": getattr(self, "_stream_on_air", None) if client is not None else None,
            "companion": companions.name(self.config), "identity": self._stream_identity(),
            "muted": self._stream_muted(), "holding": self._stream_holding() and bool(getattr(self, "_stream_voice_queue", None)),
            "cards": [{key: card[key] for key in ("id", "who", "color", "badge", "asked", "text")} for card in cards],
            # (who sent a line and its Twitch id stay here: they're for deletions)
            "game": game.view(now) if game is not None else None,
            "banner": {"kind": banner["kind"], "text": banner["text"]} if banner else None,
            "credits": credits if credits else None,
            "hint": bool(self.config.get("stream_chat_hint", True)),
            "look": self._stream_look(),
            "lines": [{key: value for key, value in line.items() if key not in ("at", "msg", "login", "to_login")}
                      for line in (getattr(self, "_stream_lines", None) or ())[-30:]],
            "commands": "!where · !ship · !route · !session · !rigs · !ask · !rank",
        }
        emotes = getattr(client, "emotes", None)
        if emotes:
            for line in model["lines"]:
                if line.get("kind") == "chat":
                    line["fragments"] = emotes.expand(line.get("fragments", []))
        if not (model["cards"] or model["game"] or model["banner"] or model["credits"] or model["hint"] or model["lines"]):
            return None
        return model

    def _stream_overlay_update(self):
        hud = getattr(self, "stream_chat_hud", None)
        if hud is None:
            return
        try:
            model = self._stream_overlay_model()
            if model != getattr(self, "_stream_overlay_last", None):
                self._stream_overlay_last = model
                hud.update(model)
        except Exception:
            logging.debug("Stream Chat overlay not updated", exc_info=True)

    # -- Settings and the Local API -------------------------------------------------------
    def _stream_chat_settings(self):
        try:
            summary = self.stream_crew_store().summary()
        except Exception:
            summary = {"crew": 0, "worlds": 0, "streams": 0, "chatters": 0, "top": []}
        return {**self._stream_chat_state(), **summary, "muted": self._stream_muted()}

    def _stream_chat_test(self, text):
        """Settings › TRY IT: a message as if from chat, to see and hear it."""
        text = _stream_text(text or "!where", 200)
        event = {"kind": "chat", "login": "voidcompass_test", "name": "TestPilot", "color": "#00d1ff", "text": text,
                 "broadcaster": False, "mod": True, "sub": False, "vip": False, "bits": 0}
        if getattr(self, "_stream_client", None) is None and not getattr(self, "_stream_ticking", False):
            self._stream_ticking = True
            self.root.call_later(TICK_MS, self._tick_stream_chat)
        return self._stream_chat_handle(event)

    def api_stream(self):
        game = getattr(self, "_stream_game", None)
        store = self.stream_crew_store()
        return {**self._stream_chat_state(), "muted": self._stream_muted(), "game": game.view() if game is not None else None,
                "top": store.top(10), "tonight": store.top(10, this_stream=True), "worlds": list(store.worlds[-20:]),
                "session": dict(getattr(self, "_stream_session", None) or {}, systems=None)}

    def api_stream_credits(self):
        return self._stream_credits()

    def api_stream_mute(self):
        return {"muted": not self._stream_mute_toggle()}


__all__ = ["DashboardStreamChatMixin"]
