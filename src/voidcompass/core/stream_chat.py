"""Twitch chat, read-only, with no account (5.8.3).

Twitch lets anyone read a channel's chat anonymously over IRC: a "justinfan"
nickname, no password. With its tags and commands asked for, each message
carries the viewer's display name, colour and badges, cheers carry their bits,
and raids and subs arrive as USERNOTICEs. Nothing is ever sent to the channel.

The client runs on its own thread and hands each event to ``on_event`` as a
plain dict; it reconnects by itself, backing off, and says how it's doing in
``status``. ``parse`` and the filters below are plain functions for the rest
of the app (and the tests).
"""
from __future__ import annotations

import random
import re
import socket
import ssl
import threading
import time
import unicodedata

from voidcompass.core.stream_emotes import BttvEmotes

HOST, PORT = "irc.chat.twitch.tv", 6697
# Twitch pings every five minutes or so: this long with nothing at all and the
# connection is taken as gone.
SILENT_S = 420.0
BACKOFF_S = (2, 5, 10, 20, 40, 60)

CHANNEL = re.compile(r"^[a-z0-9_]{3,25}$")


def channel_name(text):
    """A channel as Twitch names it ("twitch.tv/Foo" or "#Foo" → "foo"), or ""."""
    value = str(text or "").strip().lower()
    value = re.sub(r"^(https?://)?(www\.)?(m\.)?twitch\.tv/", "", value).lstrip("#@").split("/")[0].split("?")[0]
    return value if CHANNEL.match(value) else ""


def _unescape(value):
    out, index = [], 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            out.append({"s": " ", ":": ";", "\\": "\\", "r": "\r", "n": "\n"}.get(value[index + 1], value[index + 1]))
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def parse(line):
    """One IRC line: {"tags", "nick", "command", "params", "text"}, or None."""
    line = str(line or "").rstrip("\r\n")
    if not line:
        return None
    tags = {}
    if line.startswith("@"):
        raw, _, line = line.partition(" ")
        for part in raw[1:].split(";"):
            key, _, value = part.partition("=")
            tags[key] = _unescape(value)
    nick = ""
    if line.startswith(":"):
        prefix, _, line = line.partition(" ")
        nick = prefix[1:].split("!", 1)[0]
    text = ""
    if " :" in line:
        line, _, text = line.partition(" :")
    elif line.startswith(":"):
        text, line = line[1:], ""
    parts = line.split()
    if not parts:
        return None
    return {"tags": tags, "nick": nick, "command": parts[0].upper(), "params": parts[1:], "text": text}


def badges(tags):
    return {part.split("/", 1)[0] for part in str((tags or {}).get("badges") or "").split(",") if part}


def badge_list(tags):
    """The badges in Twitch's order, without repeats ("broadcaster", "subscriber"...)."""
    out = []
    for part in str((tags or {}).get("badges") or "").split(","):
        name = part.split("/", 1)[0]
        if name and name not in out:
            out.append(name)
    return out[:4]


EMOTE_URL = "https://static-cdn.jtvnw.net/emoticons/v2/{id}/default/dark/2.0"


def fragments(text, emotes_tag):
    """A message split into text and Twitch emotes, from its "emotes" tag
    ("25:0-4,12-16/1902:6-10", by character): [{"type": "text"|"emote", "text", "url"}]."""
    text = str(text or "")
    spans = []
    for group in str(emotes_tag or "").split("/"):
        ident, _, places = group.partition(":")
        if not ident or not places or not re.fullmatch(r"[A-Za-z0-9_]+", ident):
            continue
        for place in places.split(","):
            try:
                start, end = (int(value) for value in place.split("-", 1))
            except ValueError:
                continue
            if 0 <= start <= end < len(text):
                spans.append((start, end, ident))
    out, at = [], 0
    for start, end, ident in sorted(spans):
        if start < at:
            continue
        if start > at:
            out.append({"type": "text", "text": text[at:start]})
        out.append({"type": "emote", "text": text[start:end + 1], "url": EMOTE_URL.format(id=ident)})
        at = end + 1
    if at < len(text) or not out:
        out.append({"type": "text", "text": text[at:]})
    return out[:80]


def event_of(message):
    """A parsed line as the app's event: {"kind": "chat"|"raid"|"sub"|"gift",
    ...}, or None for lines that aren't for it."""
    if not message:
        return None
    tags = message.get("tags") or {}
    command = message.get("command")
    login = str(tags.get("login") or message.get("nick") or "").lower()
    name = str(tags.get("display-name") or login)
    marks = badges(tags)
    who = {"login": login, "name": name, "color": tags.get("color") or "",
           "broadcaster": "broadcaster" in marks, "mod": "moderator" in marks or "broadcaster" in marks or tags.get("mod") == "1",
           "sub": "subscriber" in marks or "founder" in marks, "vip": "vip" in marks}
    if command == "PRIVMSG":
        try:
            bits = int(tags.get("bits") or 0)
        except ValueError:
            bits = 0
        text = str(message.get("text") or "")[:500]
        return {"kind": "chat", **who, "text": text, "bits": bits, "first": tags.get("first-msg") == "1",
                "id": str(tags.get("id") or ""), "badges": badge_list(tags), "fragments": fragments(text, tags.get("emotes"))}
    # A moderator's deletions: one message, a viewer's (timed out or banned),
    # or the whole chat (/clear).
    if command == "CLEARMSG":
        return {"kind": "delete", "id": str(tags.get("target-msg-id") or ""), "login": login}
    if command == "CLEARCHAT":
        target = str(message.get("text") or "").strip().lower()
        if target:
            return {"kind": "clear_user", "login": target, "banned": not tags.get("ban-duration")}
        return {"kind": "clear"}
    if command == "USERNOTICE":
        kind = tags.get("msg-id") or ""

        def number(key):
            try:
                return int(tags.get(key) or 0)
            except ValueError:
                return 0
        if kind == "raid":
            raider = str(tags.get("msg-param-displayName") or name)
            return {"kind": "raid", **who, "name": raider, "viewers": number("msg-param-viewerCount")}
        if kind in ("sub", "resub"):
            return {"kind": "sub", **who, "months": number("msg-param-cumulative-months") or 1}
        if kind in ("subgift", "submysterygift", "anonsubgift", "anonsubmysterygift"):
            return {"kind": "gift", **who, "count": number("msg-param-mass-gift-count") or 1}
    return None


# -- what may be shown and said ------------------------------------------------------
# A short list; Settings › Stream chat adds the streamer's own words. Matched
# on letters only, with the usual look-alike characters folded first.
# Anywhere in the text, spaces and dressing-up taken out:
BLOCKED = (
    "fuck", "shit", "cunt", "bitch", "whore", "slut", "twat", "wank", "bollock", "pussy", "penis", "vagina",
    "porn", "rape", "nazi", "hitler", "nigg", "nigr", "faggot", "retard", "chink", "kike", "tranny", "killyourself",
)
# Only as a word of their own (Essex, raccoon and spice are fine):
BLOCKED_WORDS = ("sex", "dick", "cock", "fag", "spic", "paki", "gook", "coon", "dyke", "kys", "heil", "suicide")
_FOLD = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i", "|": "i", "+": "t"})


def _folded(text, keep_spaces=False):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[_\-.]+", " ", text.translate(_FOLD))
    return " ".join(re.sub(r"[^a-z ]", "", text).split()) if keep_spaces else re.sub(r"[^a-z]", "", text)


def blocked(text, extra=()):
    """Whether ``text`` has a blocked word in it, however it's dressed up.
    ``extra`` are the streamer's own words, matched anywhere."""
    folded = _folded(text)
    if any(word and word in folded for word in (*BLOCKED, *(_folded(item) for item in extra or ()))):
        return True
    tokens = set(_folded(text, keep_spaces=True).split())
    return any(word in tokens for word in BLOCKED_WORDS)


def spoken_name(name, extra=()):
    """A viewer's name as the companion may say it ("xX_Dave_Xx" → "Dave"),
    or "" when it shouldn't be said at all."""
    value = unicodedata.normalize("NFKC", str(name or ""))
    value = re.sub(r"[_\-.]+", " ", value)
    value = re.sub(r"(?i)^(x+ )+|( x+)+$", "", value).strip()
    value = re.sub(r"[^\w '’]", "", value).strip()
    value = " ".join(value.split())[:24]
    if len(value) < 2 or blocked(value, extra) or blocked(name, extra):
        return ""
    return value


def shown_text(text, extra=(), limit=28):
    """A viewer's suggestion (a name for a world) fit to show, or ""."""
    value = " ".join(unicodedata.normalize("NFKC", str(text or "")).split())
    value = re.sub(r"[^\w '’\-]", "", value).strip()[:limit]
    if len(value) < 3 or blocked(value, extra) or "http" in value.lower() or "www" in value.lower():
        return ""
    return value


def command_of(text):
    """("where", "the rest") for "!where the rest", or None."""
    match = re.match(r"^\s*!([a-z0-9]{1,16})\b\s*(.*)$", str(text or ""), re.I)
    return (match.group(1).lower(), match.group(2).strip()[:200]) if match else None


# Whether the channel is live: Twitch serves a live channel's preview
# picture, and sends an offline one to its placeholder. Asked once a minute.
PREVIEW = "https://static-cdn.jtvnw.net/previews-ttv/live_user_{}-80x45.jpg?t={}"
LIVE_EVERY_S = 60.0


def stream_is_live(channel, opener=None):
    """True while ``channel`` is live, False while it isn't, None when Twitch
    couldn't be asked."""
    from urllib.request import Request, urlopen
    name = channel_name(channel)
    if not name:
        return None
    request = Request(PREVIEW.format(name, int(time.time() // 60)), method="HEAD",
                      headers={"User-Agent": "VoidCompass/stream-live", "Cache-Control": "no-cache"})
    try:
        with (opener or urlopen)(request, timeout=8) as response:
            return "404_preview" not in str(response.geturl())
    except Exception:
        return None


class LiveWatch:
    """Asks every minute whether the channel is live, on its own thread, and
    says when that changes: ``on_change(True or False)``."""

    def __init__(self, channel, on_change, check=None, every=LIVE_EVERY_S):
        self.channel, self.on_change = channel_name(channel), on_change
        self.check, self.every = check or stream_is_live, every
        self.live = None
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if not self.channel or (self._thread and self._thread.is_alive()):
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="stream-live", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()

    def poll(self):
        found = self.check(self.channel)
        if found is not None and found != self.live:
            self.live = found
            try:
                self.on_change(found)
            except Exception:
                pass
        return found

    def _run(self):
        while not self._stop.is_set():
            self.poll()
            self._stop.wait(self.every)


class TwitchChat:
    """One channel's chat, read on a thread of its own."""

    def __init__(self, channel, on_event, on_status=None, connect=None, emotes=None):
        self.channel = channel_name(channel)
        self.on_event = on_event
        self.on_status = on_status
        self._connect = connect or self._open
        self._stop = threading.Event()
        self._thread = None
        self._sock = None
        self.status = "off"
        self.error = ""
        self.connected_at = None
        self.emotes = BttvEmotes() if emotes is None else emotes

    def _set(self, status, error=""):
        self.status, self.error = status, error
        if callable(self.on_status):
            try:
                self.on_status(status, error)
            except Exception:
                pass

    def start(self):
        if not self.channel or (self._thread and self._thread.is_alive()):
            return False
        self._stop.clear()
        if self.emotes:
            self.emotes.start()
        self._thread = threading.Thread(target=self._run, name="stream-chat", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()
        if self.emotes:
            self.emotes.stop()
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        self._set("off")

    @staticmethod
    def _open():
        raw = socket.create_connection((HOST, PORT), timeout=15)
        sock = ssl.create_default_context().wrap_socket(raw, server_hostname=HOST)
        sock.settimeout(1.0)
        return sock

    def _send(self, line):
        if self._sock is not None:
            self._sock.sendall((line + "\r\n").encode("utf-8"))

    def _run(self):
        attempt = 0
        while not self._stop.is_set():
            self._set("connecting" if attempt == 0 else "reconnecting")
            try:
                self._sock = self._connect()
                self._send("CAP REQ :twitch.tv/tags twitch.tv/commands")
                self._send("PASS SCHMOOPIIE")
                self._send(f"NICK justinfan{random.randint(10000, 99999)}")
                self._send(f"JOIN #{self.channel}")
                self._live = False
                attempt = self._read()
            except (OSError, ssl.SSLError) as exc:
                if self._stop.is_set():
                    break           # stopped: the socket was closed under it
                if getattr(self, "_live", False):
                    attempt = 0  # it was live: a dropped line comes straight back
                self._set("reconnecting", str(exc)[:120])
            finally:
                sock, self._sock = self._sock, None
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass
            if self._stop.is_set():
                break
            wait = BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)]
            attempt += 1
            self._stop.wait(wait)
        self._set("off")

    def _read(self):
        """Read until the connection goes; the attempt count to carry on with
        (0 once it was live, so a dropped live connection retries quickly)."""
        buffer, heard, live = b"", time.monotonic(), False
        while not self._stop.is_set():
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                if time.monotonic() - heard > SILENT_S:
                    raise OSError("chat went quiet")
                continue
            if not chunk:
                raise OSError("Twitch closed the connection")
            heard = time.monotonic()
            buffer += chunk
            while b"\r\n" in buffer:
                line, buffer = buffer.split(b"\r\n", 1)
                message = parse(line.decode("utf-8", "replace"))
                if not message:
                    continue
                command = message["command"]
                if command == "PING":
                    self._send(f"PONG :{message['text'] or 'tmi.twitch.tv'}")
                elif command == "RECONNECT":
                    raise OSError("Twitch asked for a reconnect")
                elif command in ("ROOMSTATE", "366") or (command == "JOIN" and not live):
                    if command == "ROOMSTATE" and self.emotes:
                        self.emotes.set_channel(message["tags"].get("room-id"))
                    if not live:
                        live = self._live = True
                        self.connected_at = time.time()
                        self._set("connected")
                elif command == "NOTICE" and "msg_channel_suspended" in str(message["tags"].get("msg-id") or ""):
                    self._set("error", "that channel is suspended")
                    self._stop.wait(300)
                else:
                    event = event_of(message)
                    if event is not None and event.get("kind") == "chat" and self.emotes:
                        try:
                            event["fragments"] = self.emotes.expand(event["fragments"])
                        except Exception:
                            pass
                    if event is not None:
                        try:
                            self.on_event(event)
                        except Exception:
                            pass
        return 0 if live else 1


__all__ = ["LiveWatch", "TwitchChat", "blocked", "stream_is_live", "channel_name", "command_of", "event_of", "parse", "shown_text", "spoken_name"]
