"""BetterTTV's public emote catalogue, refreshed away from the chat/UI threads."""
from __future__ import annotations

import json
import re
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = "https://api.betterttv.net/3/cached/"
CDN = "https://cdn.betterttv.net/emote/{}/2x"
REFRESH_S, RETRY_S = 900, 60
MAX_BYTES = 2 * 1024 * 1024


def fetch_catalogue(path):
    request = Request(API + path, headers={"Accept": "application/json", "User-Agent": "VoidCompass/stream-emotes"})
    try:
        with urlopen(request, timeout=6) as response:
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("Emote catalogue too large")
        return json.loads(body)
    except HTTPError as exc:
        if exc.code == 404 and path.startswith("users/twitch/"):
            return {"channelEmotes": [], "sharedEmotes": []}
        raise


def catalogue(rows):
    out = {}
    for row in rows[:5000] if isinstance(rows, list) else ():
        if not isinstance(row, dict):
            continue
        code, ident = str(row.get("code") or ""), str(row.get("id") or "")
        if 0 < len(code) <= 100 and not re.search(r"\s", code) and re.fullmatch(r"[a-fA-F0-9]{24}", ident):
            out[code] = CDN.format(ident)
    return out


class BttvEmotes:
    def __init__(self, fetch=None, clock=None):
        self._fetch, self._clock = fetch or fetch_catalogue, clock or time.monotonic
        self._lock = threading.Lock()
        self._stop, self._wake = threading.Event(), threading.Event()
        self._thread = None
        self._global, self._channel = {}, {}
        self._global_due = self._channel_due = 0
        self.channel_id = ""

    def set_channel(self, channel_id):
        ident = str(channel_id or "")
        if not re.fullmatch(r"[0-9]{1,20}", ident):
            return
        with self._lock:
            if ident == self.channel_id:
                return
            self.channel_id, self._channel, self._channel_due = ident, {}, 0
        self._wake.set()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="stream-emotes", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def refresh(self):
        now = self._clock()
        with self._lock:
            ident, global_due, channel_due = self.channel_id, self._global_due, self._channel_due
        for path, due in (("emotes/global", global_due), (f"users/twitch/{ident}", channel_due)):
            global_catalogue = path == "emotes/global"
            if self._stop.is_set() or now < due or (not global_catalogue and not ident):
                continue
            try:
                data = self._fetch(path)
                if global_catalogue:
                    if not isinstance(data, list):
                        raise ValueError("Invalid global emotes")
                    emotes = catalogue(data)
                else:
                    if not isinstance(data, dict) or not all(isinstance(data.get(k), list) for k in ("channelEmotes", "sharedEmotes")):
                        raise ValueError("Invalid channel emotes")
                    emotes = catalogue(data["sharedEmotes"]) | catalogue(data["channelEmotes"])
                delay = REFRESH_S
            except Exception:
                emotes, delay = None, RETRY_S
            with self._lock:
                if self._stop.is_set():
                    return
                if global_catalogue:
                    if emotes is not None:
                        self._global = emotes
                    self._global_due = now + delay
                elif self.channel_id == ident:
                    if emotes is not None:
                        self._channel = emotes
                    self._channel_due = now + delay

    def _run(self):
        while not self._stop.is_set():
            self._wake.clear()
            self.refresh()
            self._wake.wait(5)

    def expand(self, fragments):
        with self._lock:
            known = self._global | self._channel
        out = []
        for part in fragments or ():
            if part.get("type") != "text":
                out.append(dict(part))
                continue
            for word in re.split(r"(\s+)", str(part.get("text") or "")):
                if not word:
                    continue
                if word in known:
                    out.append({"type": "emote", "text": word, "url": known[word], "provider": "bttv"})
                elif out and out[-1].get("type") == "text":
                    out[-1]["text"] += word
                else:
                    out.append({"type": "text", "text": word})
        return out
