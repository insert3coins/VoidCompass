"""Chat names your discoveries (5.8.3): a world you're first to find, and
chat suggests names (!name), then votes (!vote). Plain state: the deck opens
it, feeds suggestions and votes, settles it, and shows ``view()`` on the
Stream Chat overlay."""
from __future__ import annotations

import re
import time

WINDOWS = {"name": 90.0, "vote": 60.0}
POINTS = {"name": 5, "vote": 1}
NOTABLE_WORLDS = {"earthlike body": "Earth-like world", "water world": "water world", "ammonia world": "ammonia world"}


class Game:
    kind = ""

    def __init__(self, now=None, closes_in=None, **facts):
        self.opened = time.time() if now is None else now
        self.closes = self.opened + closes_in if closes_in else None
        self.facts = dict(facts)
        self.guesses = {}     # login -> value
        self.names = {}       # login -> display name
        self.answer = None
        self.done = False

    def open_for(self, now):
        return not self.done and (self.closes is None or now < self.closes)

    def read(self, text):
        """A guess as this game takes it, or None."""
        return None

    def guess(self, login, name, text, now=None):
        """A viewer's guess (their latest counts): the value taken, or None."""
        now = time.time() if now is None else now
        if not self.open_for(now):
            return None
        value = self.read(text)
        if value is None:
            return None
        self.guesses[login] = value
        self.names[login] = name
        return value

    def close(self, now=None):
        now = time.time() if now is None else now
        if self.closes is None or self.closes > now:
            self.closes = now

    def tally(self):
        counts = {}
        for value in self.guesses.values():
            counts[value] = counts.get(value, 0) + 1
        return sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))

    def settle(self, answer):
        """The answer is in: [(login, name, points)] for the winners."""
        self.answer, self.done = answer, True
        return []

    def view(self, now=None):
        now = time.time() if now is None else now
        left = max(0, round((self.closes or now) - now)) if self.closes else None
        return {"kind": self.kind, "open": self.open_for(now), "closes_in": left, "guesses": len(self.guesses),
                "tally": [{"value": str(value), "count": count} for value, count in self.tally()[:6]],
                "answer": None if self.answer is None else str(self.answer), "done": self.done, **self.public()}

    def public(self):
        return {}


class NameGame(Game):
    """A world first discovered: suggestions (``!name``), then a vote (``!vote``)."""
    kind = "name"

    def __init__(self, now=None, closes_in=None, **facts):
        super().__init__(now=now, closes_in=closes_in or WINDOWS["name"], **facts)
        self.stage = "suggest"
        self.choices = []     # [(name, login, display name)]
        self.votes = {}

    def suggest(self, login, name, text, now=None):
        """A suggestion, already cleaned (stream_chat.shown_text): True if taken."""
        now = time.time() if now is None else now
        if self.stage != "suggest" or not self.open_for(now) or not text:
            return False
        if any(choice[0].lower() == text.lower() for choice in self.choices):
            return False
        if any(choice[1] == login for choice in self.choices):
            return False        # one each
        if len(self.choices) >= 4:
            return False
        self.choices.append((text, login, name))
        return True

    def start_vote(self, now=None):
        now = time.time() if now is None else now
        self.stage = "vote"
        self.closes = now + WINDOWS["vote"]

    def vote(self, login, name, text, now=None):
        now = time.time() if now is None else now
        if self.stage != "vote" or not self.open_for(now):
            return None
        match = re.search(r"\d", str(text or ""))
        if not match or not 1 <= int(match.group(0)) <= len(self.choices):
            return None
        self.votes[login] = int(match.group(0))
        self.names[login] = name
        return self.votes[login]

    def winner(self):
        """(name, by login, by name, votes) or None."""
        if not self.choices:
            return None
        counts = {index: 0 for index in range(1, len(self.choices) + 1)}
        for value in self.votes.values():
            counts[value] = counts.get(value, 0) + 1
        best = max(counts, key=lambda index: (counts[index], -index))
        name, login, display = self.choices[best - 1]
        return name, login, display, counts[best]

    def settle(self, answer=None):
        found = self.winner()
        self.done = True
        if not found:
            return []
        self.answer = found[0]
        index = next(i for i, choice in enumerate(self.choices, 1) if choice[0] == found[0])
        out = [(found[1], found[2], POINTS["name"])]
        out += [(login, self.names.get(login, login), POINTS["vote"]) for login, value in self.votes.items() if value == index and login != found[1]]
        return out

    def view(self, now=None):
        out = super().view(now)
        counts = {}
        for value in self.votes.values():
            counts[value] = counts.get(value, 0) + 1
        out["choices"] = [{"n": index, "name": name, "by": display, "votes": counts.get(index, 0)}
                          for index, (name, _login, display) in enumerate(self.choices, 1)]
        out["stage"] = self.stage
        return out

    def public(self):
        world = self.facts.get("world") or "this world"
        if getattr(self, "stage", "suggest") == "vote":
            return {"title": f"VOTE: NAME {str(world).upper()}", "prompt": "!vote 1, 2, 3 or 4"}
        return {"title": f"NAME {str(world).upper()}", "prompt": "!name your idea · four suggestions go to a vote"}


__all__ = ["Game", "NameGame", "NOTABLE_WORLDS", "POINTS", "WINDOWS"]
