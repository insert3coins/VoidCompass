"""The Games page (5.6.3): a card per game under web/games, each played in
the deck, with the best runs kept per commander.

A game is a folder holding a game.json (its card's words) and the page it
plays in. Its card picture, when there is one, is assets/gamecards/<id>.*,
a screenshot of the game taken by tools/game_cards.py.

A game can be told what the journal knows (its "live" data): Touchdown and
Scarab Patrol the gravity of the world you're at, Hatchling the pet itself.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

from voidcompass.core import hatchling
from voidcompass.core.config import get_active_profile, get_profile_file
from voidcompass.core.paths import resource_path
from voidcompass.overlays.hatchling_hud import REACTION_S, hatchling_overlay_options

logger = logging.getLogger(__name__)

GAMES_FILE = "games.json"
HATCHLING_FILE = "hatchling.json"
CARD_TYPES = (".webp", ".png", ".jpg", ".jpeg")
# What the card pictures are drawn at: 8:9, an arcade screen's shape, shown
# filling the card.
CARD_SIZE = (1200, 1350)
KEEP_RUNS = 10
_GAME_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


def games_root():
    return resource_path("web", "games")


def cards_root():
    return resource_path("assets", "gamecards")


def _text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _whole(value, low=0, high=10 ** 9):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return low
    return max(low, min(high, number))


def card_picture(game_id, folder=None):
    folder = folder or cards_root()
    for suffix in CARD_TYPES:
        if (folder / f"{game_id}{suffix}").is_file():
            return f"{game_id}{suffix}"
    return ""


def read_games(root=None, cards=None):
    """Every arcade cabinet, A to Z. Companions use their own workspace."""
    root = root or games_root()
    games = []
    try:
        folders = sorted(path for path in root.iterdir() if path.is_dir())
    except OSError:
        return games
    for folder in folders:
        game_id = folder.name.casefold()
        if not _GAME_ID.match(game_id):
            continue
        try:
            manifest = json.loads((folder / "game.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(manifest, dict):
            continue
        # Companion experiences have their own Cockpit workspace, not an
        # arcade card. Keep the manifest entry point for direct compatibility.
        if manifest.get("catalog", True) is False:
            continue
        entry = str(manifest.get("entry") or "index.html")
        if "/" in entry or "\\" in entry or entry.startswith(".") or not (folder / entry).is_file():
            continue
        controls = [[_text(pair[0], 24), _text(pair[1], 60)] for pair in manifest.get("controls") or []
                    if isinstance(pair, (list, tuple)) and len(pair) == 2]
        picture = card_picture(game_id, cards)
        games.append({
            "id": game_id,
            "title": _text(manifest.get("title") or game_id, 40),
            "tagline": _text(manifest.get("tagline"), 200),
            "description": _text(manifest.get("description"), 600),
            "genre": _text(manifest.get("genre"), 30),
            "stage": _text(manifest.get("stage") or "wave", 12).upper(),
            "players": _text(manifest.get("players") or "1 player", 20),
            # Keys only or mouse only, chosen on the page (a game built on clicks says no).
            "input_modes": manifest.get("input_modes") is not False,
            "controls": controls[:8],
            "accent": _text(manifest.get("accent"), 9) if re.match(r"^#[0-9a-fA-F]{6}$", str(manifest.get("accent") or "")) else "",
            "entry": f"/games/{game_id}/{entry}",
            "card": f"/gamecards/{picture}" if picture else "",
            "card_name": f"{game_id}.png",
        })
    games.sort(key=lambda game: game["title"].casefold())
    return games


class DashboardGamesMixin:
    """The deck's Games page and its scores."""

    def _games_path(self):
        return get_profile_file(get_active_profile(getattr(self, "config", None) or {}), GAMES_FILE)

    def _games_scores(self):
        path = self._games_path()
        cached = getattr(self, "_games_cache", None)
        if cached and cached[0] == path:
            return cached[1]
        try:
            with open(path, encoding="utf-8") as handle:
                scores = json.load(handle)
        except (OSError, ValueError):
            scores = {}
        if not isinstance(scores, dict):
            scores = {}
        self._games_cache = (path, scores)
        return scores

    def _games_save(self, scores):
        path = self._games_path()
        temp = f"{path}.tmp"
        try:
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(scores, handle, separators=(",", ":"))
            os.replace(temp, path)
        except OSError as exc:
            logger.warning("Could not save game scores: %s", exc)
            return False
        self._games_cache = (path, scores)
        return True

    def _html_games_workspace(self):
        scores = self._games_scores()
        games = []
        for game in read_games():
            record = scores.get(game["id"]) if isinstance(scores.get(game["id"]), dict) else {}
            runs = [run for run in record.get("runs") or [] if isinstance(run, dict)]
            games.append({**game, "best": runs[0] if runs else None, "runs": runs[:KEEP_RUNS],
                          "played": _whole(record.get("played")), "last": _whole(record.get("last")),
                          "live": self._games_live(game["id"])})
        return {"games": games, "card_size": list(CARD_SIZE), "card_folder": str(cards_root())}

    def _html_hatchling_workspace(self):
        """The live companion view for the dedicated Cockpit page."""
        return self._games_live("hatchling")

    def _games_live(self, game_id):
        if game_id == "hatchling":
            now = time.time()
            live = hatchling.view(self._hatchling_state(), now)
            if live.get("pet"):
                if now - float(live["pet"].get("reaction_at") or 0) >= REACTION_S:
                    live["pet"]["reaction"] = ""
                live["pet"]["music"] = self._hatchling_music()
                live["pet"]["music_started_at"] = getattr(self, "_hatchling_music_started_at", None) if live["pet"]["music"] else None
                live["pet"]["watcher"] = self._hatchling_watcher_seen(side=(0, -1))
                live["pet"]["options"] = hatchling_overlay_options(self.config)
            return live
        if game_id in {"touchdown", "scarab-patrol"}:
            return self._games_gravity()
        return None

    def _games_gravity(self):
        """The world you're at, for Touchdown and Scarab Patrol: its name and surface gravity."""
        body_id = getattr(self, "current_body_id", None)
        item = (getattr(self, "scan_items_by_id", None) or {}).get(body_id) if body_id is not None else None
        try:
            gravity = float((item or {}).get("gravity_g"))
        except (TypeError, ValueError):
            return None
        if not 0 < gravity < 50:
            return None
        return {"body": _text(getattr(self, "current_body_name", "") or (item or {}).get("name"), 60), "gravity": round(gravity, 2)}

    def _handle_games_command(self, operation, payload):
        payload = payload or {}
        game_id = str(payload.get("game") or "").casefold()
        if operation == "action" and game_id == "hatchling":
            return self._hatchling_action(payload)
        if operation != "score" or not _GAME_ID.match(game_id):
            return False
        if game_id not in {game["id"] for game in read_games()}:
            return False
        run = {
            "score": _whole(payload.get("score"), 0, 99_999_999),
            "wave": _whole(payload.get("wave") if payload.get("wave") is not None else payload.get("level"), 0, 9999),
            "accuracy": _whole(payload.get("accuracy"), 0, 100),
            "rank": _text(payload.get("rank"), 24),
            "at": int(time.time()),
        }
        scores = dict(self._games_scores())
        record = dict(scores.get(game_id) or {})
        runs = [entry for entry in record.get("runs") or [] if isinstance(entry, dict)]
        if run["score"] > 0:
            runs.append(run)
        runs.sort(key=lambda entry: (-_whole(entry.get("score")), _whole(entry.get("at"))))
        record.update(runs=runs[:KEEP_RUNS], played=_whole(record.get("played")) + 1, last=run["at"])
        scores[game_id] = record
        saved = self._games_save(scores)
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=True)
        return saved

    # -- Hatchling (5.6.3): the pet, one per commander ----------------------------------------------
    def _hatchling_path(self):
        return get_profile_file(get_active_profile(getattr(self, "config", None) or {}), HATCHLING_FILE)

    def _hatchling_state(self):
        path = self._hatchling_path()
        cached = getattr(self, "_hatchling_cache", None)
        if cached and cached[0] == path:
            return cached[1]
        try:
            with open(path, encoding="utf-8") as handle:
                state = hatchling.load_state(handle.read())
        except OSError:
            state = hatchling.new_state()
        self._hatchling_cache = (path, state)
        # Back after time away (5.6.4): it tells you what it did meanwhile.
        try:
            if hatchling.welcome(state, time.time()):
                self._hatchling_save()
        except Exception as exc:
            logger.debug("Hatchling welcome skipped: %s", exc)
        return state

    def _hatchling_save(self):
        path = self._hatchling_path()
        state = self._hatchling_state()
        temp = f"{path}.tmp"
        try:
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(state, handle, separators=(",", ":"))
            os.replace(temp, path)
        except OSError as exc:
            logger.warning("Could not save the Hatchling: %s", exc)
            return False
        return True

    def _hatchling_changed(self, immediate=True):
        # Note: a scan honk is dozens of events in a few seconds; each used to
        # write the file and redraw the whole deck at once (5.6.4).
        self._hatchling_save_soon()
        self._hatchling_overlay_refresh(force=True)
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=immediate)

    def _hatchling_save_soon(self, delay_ms=4000):
        """Save within a few seconds, once for a burst of changes."""
        root = getattr(self, "root", None)
        later = getattr(root, "call_later", None)
        if not callable(later):
            return self._hatchling_save()
        if getattr(self, "_hatchling_save_job", None) is not None:
            return True

        def save():
            self._hatchling_save_job = None
            self._hatchling_save()

        self._hatchling_save_job = later(delay_ms, save)
        return True

    def _hatchling_flush(self):
        """Closing: any change still waiting is written now."""
        job = getattr(self, "_hatchling_save_job", None)
        if job is None:
            return False
        try:
            self.root.cancel(job)
        except Exception:
            pass
        self._hatchling_save_job = None
        return self._hatchling_save()

    def _hatchling_action(self, payload):
        action = _text(payload.get("act"), 20)
        value = payload.get("value") if isinstance(payload.get("value"), dict) else {}
        changed, message = hatchling.act(self._hatchling_state(), action, value, time.time())
        # The page shows why nothing happened (the deck answers every command OK).
        self._hatchling_state()["notice"] = {"text": message, "at": time.time()} if message else None
        if changed:
            self._hatchling_watcher()
            moment = (self._hatchling_state().get("pet") or {}).get("moment") or {}
            if moment.get("kind") == "trick" and moment.get("at", 0) >= time.time() - 2:
                self._hatchling_chat("trick")
            self._hatchling_changed()
        else:
            publish = getattr(self, "_schedule_html_dashboard_publish", None)
            if callable(publish):
                publish(immediate=True)
        return True

    def _games_observe(self, event, raw, startup_replay=False):
        """Live journal events only: a replayed history never feeds the pet."""
        if startup_replay or not isinstance(raw, dict):
            return
        state = self._hatchling_state()
        if not state.get("pet"):
            return
        if raw.get("event") in {"Touchdown", "ApproachBody", "LaunchSRV", "Disembark"}:
            # The world you're on, for its hops and how warm it feels.
            world = self._hatchling_world()
            if world:
                raw = {**raw, "_world": world}
        try:
            noticed = hatchling.observe(state, raw, time.time())
        except Exception as exc:
            logger.debug("Hatchling skipped %s: %s", event, exc)
            return
        if noticed:
            self._hatchling_watcher()
            self._hatchling_react(state, raw)
            # The overlay acts a cue out at once; the deck catches up at its own pace.
            self._hatchling_changed(immediate=False)

    def _hatchling_tick(self):
        """Its needs move by the hour: the overlay catches up once a minute.
        It also hears the Watcher speak, and turns to look."""
        heard = self._hatchling_watcher_seen()
        if heard and not self._hatchling_watcher_busy() and heard["at"] != getattr(self, "_hatchling_answered", None):
            # Once the Watcher has finished, now and then it answers.
            self._hatchling_answered = heard["at"]
            if time.time() - heard["at"] < 90:
                self._hatchling_chat("answer")
        if heard and heard["at"] != getattr(self, "_hatchling_heard_at", None):
            self._hatchling_heard_at = heard["at"]
            self._hatchling_overlay_refresh(force=True)
            publish = getattr(self, "_schedule_html_dashboard_publish", None)
            if callable(publish):
                publish(immediate=False)
        now = time.monotonic()
        if now - float(getattr(self, "_hatchling_tick_at", 0.0) or 0.0) < 60.0:
            return
        self._hatchling_tick_at = now
        self._hatchling_sync_trip()
        self._hatchling_chat("idle")
        self._hatchling_overlay_refresh()
        # Now and then the Watcher remarks on it (it decides how often).
        pet = self._hatchling_state().get("pet")
        if pet and pet.get("stage") != "egg" and pet.get("dormant_since") is None and not pet.get("asleep"):
            self._hatchling_tell_watcher("hatchling_idle", {"name": pet["name"]})

    def _hatchling_active_trip(self):
        """The expedition being flown, as the pet knows it: {id, name, to}."""
        manager = getattr(self, "expedition_manager", None)
        data = getattr(manager, "data", None) or {}
        row = manager.get(data.get("active_id")) if manager is not None and data.get("active_id") else None
        if not row or row.get("status") != "active":
            return None
        legs = [leg for leg in row.get("legs") or () if leg.get("kind") != "home"]
        to = row.get("destination") or (legs[-1].get("system") if legs else "") or ""
        return {"id": str(row.get("id") or ""), "name": str(row.get("name") or "the expedition"), "to": str(to)}

    def _hatchling_sync_trip(self):
        """It comes along on the expedition you're flying (5.6.4)."""
        state = self._hatchling_state()
        if not state.get("pet"):
            return False
        if hatchling.join_trip(state, self._hatchling_active_trip(), time.time()):
            self._hatchling_changed(immediate=False)
            return True
        return False

    def _hatchling_trip_ended(self, expedition_id, completed):
        """An expedition finished: with it aboard and completed, a badge."""
        state = self._hatchling_state()
        badge = hatchling.finish_trip(state, expedition_id, time.time(), completed=completed)
        if badge:
            self._hatchling_tell_watcher("hatchling_grown", {"name": state["pet"]["name"], "form": "seasoned traveller"})
            self._hatchling_chat("tripdone")
        self._hatchling_changed()
        self._hatchling_sync_trip()
        return badge

    def _hatchling_trip_view(self, expedition_id):
        """For the expedition's page: who's aboard, and its diary of the trip."""
        state = self._hatchling_state()
        pet = state.get("pet") or {}
        story = hatchling.trip_story(state, expedition_id)
        aboard = isinstance(pet.get("trip"), dict) and pet["trip"].get("id") == str(expedition_id)
        if not story and not aboard:
            return None
        return {"name": pet.get("name") or "", "species": pet.get("species") or "", "aboard": aboard,
                "lines": (story or {}).get("lines", [])[-4:], "badge": (story or {}).get("badge", "")}

    def _hatchling_watcher_busy(self):
        """The Watcher has a thought on screen: the pet keeps quiet."""
        mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
        current = getattr(mind, "current", None)
        try:
            return bool(current()) if callable(current) else False
        except Exception:
            return False

    def _hatchling_react(self, state, raw):
        """A few words for what just happened, if it feels like it."""
        pet = state.get("pet") or {}
        cue = pet.get("cue") or {}
        moment = pet.get("moment") or {}
        now = pet.get("last")
        situation = ""
        if cue.get("at") == now and cue.get("kind") == "biology":
            situation = "biology"
        elif moment.get("kind") in {"toy", "trick"} and moment.get("at") == now:
            situation = moment["kind"]
        elif cue.get("at") == now:
            situation = cue.get("kind") or ""
            world = pet.get("world") or {}
            if situation == "touchdown" and world.get("temp"):
                situation = "cold" if world["temp"] < 180 else "hot" if world["temp"] > 500 else situation
        if situation:
            self._hatchling_chat(situation)

    def _hatchling_chat(self, situation):
        """Maybe a line of its own (5.6.4): rare, short, and never over the Watcher."""
        from voidcompass.core import hatchling_chatter
        state = self._hatchling_state()
        now = time.time()
        live = (hatchling.view(state, now) or {}).get("pet")
        said = hatchling_chatter.chatter(state, live, situation, now, hatchling_overlay_options(self.config)["chatter"],
                                         watcher_busy=self._hatchling_watcher_busy())
        if not said:
            return None
        # Very occasionally the Watcher picks up on it.
        if situation != "answer" and hatchling_chatter.random.random() < .1:
            self._hatchling_tell_watcher("hatchling_said", {"name": live.get("name") or "", "said": said.strip("…. ")})
        self._hatchling_overlay_refresh(force=True)
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=False)
        return said

    def _hatchling_world(self):
        body_id = getattr(self, "current_body_id", None)
        item = (getattr(self, "scan_items_by_id", None) or {}).get(body_id) if body_id is not None else None
        if not item:
            return None
        try:
            gravity = float(item.get("gravity_g") or 1.0)
            temp = float(item.get("surface_temp") or 0.0)
        except (TypeError, ValueError):
            return None
        return {"body": _text(item.get("name") or getattr(self, "current_body_name", ""), 60), "gravity": round(gravity, 2), "temp": round(temp)}

    def _hatchling_watcher_seen(self, side=None):
        """The Watcher's latest thought (5.6.4): when, which way it is from the
        pet's overlay, and whether it's the weary one."""
        heartbeat = getattr(self, "heartbeat_hud", None)
        last = getattr(getattr(heartbeat, "mind", None), "last_thought", None)
        if not isinstance(last, dict) or not last.get("at") or not self.config.get("heartbeat_overlay_enabled", True):
            return None
        if side is None:
            def at(key):
                try:
                    return float(self.config.get(key) or 0)
                except (TypeError, ValueError):
                    return 0.0
            # Monitors left of the main one have negative positions.
            dx = at("heartbeat_hud_x") - at("hatchling_hud_x")
            dy = at("heartbeat_hud_y") - at("hatchling_hud_y")
            side = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
        from voidcompass.overlays import watcher_mind
        return {"at": float(last["at"]), "side": list(side), "weary": watcher_mind.personality(self.config) == "weary"}

    def _hatchling_music(self):
        return bool((getattr(self, "_music_status", None) or {}).get("playing"))

    def _hatchling_watcher(self):
        """A moment worth the Watcher's notice (5.6.4): a toy, a trick, a fright, growing up."""
        pet = self._hatchling_state().get("pet") or {}
        moment = pet.get("moment")
        if not isinstance(moment, dict) or moment.get("at") == getattr(self, "_hatchling_moment_at", None):
            return
        self._hatchling_moment_at = moment.get("at")
        fields = {key: value for key, value in moment.items() if key not in {"kind", "at"}}
        self._hatchling_tell_watcher(f"hatchling_{moment.get('kind')}", {"name": pet.get("name") or "", **fields})

    def _hatchling_tell_watcher(self, kind, fields):
        heartbeat = getattr(self, "heartbeat_hud", None)
        if heartbeat is None or not hasattr(heartbeat, "note"):
            return
        try:
            heartbeat.note(kind, fields)
        except Exception as exc:
            logger.debug("The Watcher missed the Hatchling: %s", exc)

    def _hatchling_snap(self, png):
        """SNAP on its page (5.6.4): the pod as a postcard."""
        from io import BytesIO

        from PIL import Image

        from voidcompass.core import themes
        from voidcompass.dashboard.dashboard_keepsakes_mixin import postcards_folder
        from voidcompass.overlays.postcard_picture import keep_card, save_postcard_picture
        from voidcompass.overlays.postcards import postcard_card, postcard_options
        from voidcompass.services.postcard_album import postcard_id
        pet = self._hatchling_state().get("pet")
        if not pet or not png.startswith(b"\x89PNG"):
            return None
        try:
            picture = Image.open(BytesIO(png)).convert("RGB")
        except Exception:
            return None
        system = str(getattr(self, "current_sys", "") or "").replace("---", "")
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        card = postcard_card({"System": system, "timestamp": stamp}, system=system, serial=0, now=int(time.time() * 1000))
        card["greeting"] = f"Greetings from {pet['name']}"
        options = postcard_options(self.config)
        palette = dict(themes.ACTIVE_PALETTE or {})
        saved = save_postcard_picture(card, picture, postcards_folder(self.config), palette, style=options["style"],
                                      theme=options["theme"], postmark=options["postmark"], sizes=options["sizes"])
        if not saved:
            return None
        keep_card(saved, card, picture, {"style": options["style"], "theme": options["theme"], "palette": palette,
                                         "postmark": options["postmark"], "sizes": options["sizes"]})
        self._postcard_album_cache = None
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=True)
        return postcard_id(os.path.basename(saved))

    def _hatchling_overlay_refresh(self, force=False):
        hud = getattr(self, "hatchling_hud", None)
        if hud is None:
            return
        from voidcompass.overlays.hatchling_hud import build_hatchling_model
        now = time.time()
        playing = self._hatchling_music()
        model = build_hatchling_model(hatchling.view(self._hatchling_state(), now), now, music=playing,
                                      options=hatchling_overlay_options(self.config), watcher=self._hatchling_watcher_seen(),
                                      music_started_at=getattr(self, "_hatchling_music_started_at", None) if playing else None)
        if not force and model == getattr(self, "_hatchling_overlay_model", None):
            return
        self._hatchling_overlay_model = model
        hud.update_hatchling(model)
