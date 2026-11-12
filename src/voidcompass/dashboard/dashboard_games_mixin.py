"""The Games page (5.6.3): a card per game under web/games, each played in
the deck, with the best runs kept per commander.

A game is a folder holding a game.json (its card's words) and the page it
plays in. Its card picture, when there is one, is assets/gamecards/<id>.*,
a screenshot of the game taken by tools/game_cards.py.

A game can be told what the journal knows (its "live" data): Touchdown and
Scarab Patrol the gravity of the world you're at.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

from voidcompass.core.config import get_active_profile, get_profile_file
from voidcompass.core.paths import resource_path

logger = logging.getLogger(__name__)

GAMES_FILE = "games.json"
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

    def _games_live(self, game_id):
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
