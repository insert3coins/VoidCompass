"""Your stream's crew (5.8.3): the viewers who chat, kept per commander in
stream_crew.json. Who they are, how many of your streams they've been at,
their points from naming worlds and the crew rank those give, the worlds
chat has named, and each stream's own record for its end credits."""
from __future__ import annotations

import json
import os
import threading
import time

from voidcompass.core.persistence_queue import persistence_queue

# A new stream once chat has been quiet (or the app closed) this long.
NEW_STREAM_S = 3 * 3600
RANKS = ((0, "Recruit"), (3, "Deckhand"), (8, "Spacer"), (15, "Pilot"), (30, "Navigator"), (60, "First Officer"),
         (120, "Captain"), (250, "Legend of the Black"))
MAX_WORLDS = 200
MAX_STREAMS = 30


def rank_of(points):
    """(title, points to the next, the next title)."""
    points = int(points or 0)
    title, nxt = RANKS[0][1], None
    for index, (need, name) in enumerate(RANKS):
        if points >= need:
            title = name
            nxt = RANKS[index + 1] if index + 1 < len(RANKS) else None
    return title, (nxt[0] - points if nxt else 0), (nxt[1] if nxt else "")


class CrewStore:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.viewers = {}
        self.worlds = []
        self.streams = []
        self.load()

    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        with self.lock:
            self.viewers = {str(key): value for key, value in (data.get("viewers") or {}).items() if isinstance(value, dict)}
            self.worlds = [row for row in data.get("worlds") or () if isinstance(row, dict)][-MAX_WORLDS:]
            self.streams = [row for row in data.get("streams") or () if isinstance(row, dict)][-MAX_STREAMS:]

    def _payload(self):
        with self.lock:
            return json.loads(json.dumps({"schema": 1, "viewers": self.viewers, "worlds": self.worlds, "streams": self.streams}))

    def save(self, delay_s=2.0):
        if self.path:
            persistence_queue().submit_json(self.path, source=self._payload, indent=None, delay_s=delay_s)

    # -- the stream ---------------------------------------------------------------------
    def stream(self, now=None):
        """This stream's record, starting a new one after a long quiet."""
        now = time.time() if now is None else now
        with self.lock:
            current = self.streams[-1] if self.streams else None
            if current is None or now - float(current.get("last") or current.get("started") or 0) > NEW_STREAM_S:
                current = {"started": round(now, 1), "last": round(now, 1), "chatters": {}, "raids": [], "subs": [],
                           "winners": {}, "named": [], "games": 0, "bits": 0}
                self.streams.append(current)
                del self.streams[:-MAX_STREAMS]
            return current

    def seen(self, login, name, now=None):
        """A message from ``login``: {"new": first time ever, "back": first
        time this stream after earlier ones, "streams": how many, "messages"}."""
        now = time.time() if now is None else now
        with self.lock:
            stream = self.stream(now)
            stream["last"] = round(now, 1)
            viewer = self.viewers.get(login)
            new = viewer is None
            if new:
                viewer = self.viewers[login] = {"name": name, "first": round(now, 1), "streams": 0, "messages": 0, "points": 0, "wins": 0}
            viewer["name"] = name or viewer.get("name") or login
            this_stream = login not in stream["chatters"]
            if this_stream:
                viewer["streams"] = int(viewer.get("streams") or 0) + 1
                stream["chatters"][login] = viewer["name"]
            viewer["messages"] = int(viewer.get("messages") or 0) + 1
            viewer["last"] = round(now, 1)
            out = {"new": new, "back": this_stream and not new, "streams": viewer["streams"], "messages": viewer["messages"],
                   "first_this_stream": this_stream}
        self.save()
        return out

    def note(self, kind, row, now=None):
        """A raid, sub, gift or bits in this stream's record."""
        with self.lock:
            stream = self.stream(now)
            if kind == "bits":
                stream["bits"] = int(stream.get("bits") or 0) + int(row.get("bits") or 0)
            else:
                stream.setdefault(f"{kind}s" if not kind.endswith("s") else kind, []).append(row)
        self.save()

    # -- points and ranks ---------------------------------------------------------------
    def award(self, login, name, points, win=True, now=None):
        """Points for a guess or a name: (the viewer's points, a new rank title or "")."""
        with self.lock:
            viewer = self.viewers.setdefault(login, {"name": name, "first": round(time.time() if now is None else now, 1),
                                                     "streams": 0, "messages": 0, "points": 0, "wins": 0})
            before = rank_of(viewer.get("points"))[0]
            viewer["points"] = int(viewer.get("points") or 0) + int(points)
            if win:
                viewer["wins"] = int(viewer.get("wins") or 0) + 1
            stream = self.stream(now)
            stream.setdefault("winners", {})[login] = int(stream["winners"].get(login, 0)) + int(points)
            after = rank_of(viewer["points"])[0]
            points_now = viewer["points"]
        self.save()
        return points_now, (after if after != before else "")

    def viewer(self, login):
        with self.lock:
            found = self.viewers.get(login)
            return dict(found) if found else None

    def top(self, count=3, this_stream=False):
        """[{"login", "name", "points", "rank"}], most points first."""
        with self.lock:
            if this_stream and self.streams:
                scores = dict(self.streams[-1].get("winners") or {})
            else:
                scores = {login: int(row.get("points") or 0) for login, row in self.viewers.items()}
            rows = [{"login": login, "name": (self.viewers.get(login) or {}).get("name") or login, "points": points,
                     "rank": rank_of((self.viewers.get(login) or {}).get("points"))[0]}
                    for login, points in scores.items() if points > 0]
        return sorted(rows, key=lambda row: (-row["points"], row["name"].lower()))[:count]

    def reset_points(self):
        with self.lock:
            for viewer in self.viewers.values():
                viewer["points"], viewer["wins"] = 0, 0
            for stream in self.streams:
                stream["winners"] = {}
        self.save(delay_s=0.2)

    # -- worlds named by chat -----------------------------------------------------------
    def name_world(self, system, body, name, by, now=None):
        now = time.time() if now is None else now
        row = {"system": system, "body": body, "name": name, "by": by, "at": round(now, 1)}
        with self.lock:
            self.worlds = [kept for kept in self.worlds if (kept.get("system"), kept.get("body")) != (system, body)]
            self.worlds.append(row)
            del self.worlds[:-MAX_WORLDS]
            self.stream(now).setdefault("named", []).append(row)
        self.save()
        return row

    def world_name(self, system, body):
        with self.lock:
            return next((dict(row) for row in reversed(self.worlds)
                         if (str(row.get("system")).lower(), str(row.get("body")).lower()) == (str(system).lower(), str(body).lower())), None)

    def summary(self):
        with self.lock:
            stream = self.streams[-1] if self.streams else {}
            return {"crew": len(self.viewers), "worlds": len(self.worlds), "streams": len(self.streams),
                    "chatters": len(stream.get("chatters") or {}), "top": self.top(3)}


__all__ = ["CrewStore", "RANKS", "rank_of"]
