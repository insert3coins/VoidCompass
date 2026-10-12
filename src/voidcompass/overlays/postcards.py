"""Postcards (5.5.3.7): take a screenshot in game and a card slides in with
the picture you just took and a caption: where you were, what you were
doing, and the date in Elite's own calendar.

The journal's Screenshot event names the file (``\\ED_Pictures\\...bmp``)
and, on a surface, the latitude and longitude. The game writes the picture
first; if Void Compass's screenshot converter is on, it may already have
turned the BMP into a PNG named for the system. Either is found here, made
into a small JPEG for the card, and (with Settings > Caption files) given a
caption beside it.
"""
from __future__ import annotations

import datetime as _datetime
import os
import time

from voidcompass.overlays.jump_info_hud import elite_date

HOLDS = (6, 10, 20, 30)
# The card's look (5.5.3.7): the overlay and saved postcards alike.
STYLES = ("polaroid", "airmail", "holo", "vintage")
DEFAULT_HOLD = 10
# The card's width in design px (it grows with the overlay text size).
SIZES = {"small": 280, "standard": 340, "large": 420}
THUMBNAIL_WIDTH = 640
# How long a run of screenshots stacks: within this many seconds of the last.
STACK_S = 90
MAX_STACK = 4


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


# The lettering over the place's name (5.5.3.8): the old travel postcard's
# "Greetings from…", "Wish you were here", your own words, or none.
GREETINGS = ("greetings", "wish", "custom", "none")
GREETING_WORDS = {"greetings": "Greetings from", "wish": "Wish you were here"}
GREETING_MAX = 40


def greeting_text(config):
    """The words the postcards carry over the place's name ("" for none);
    your own words, when chosen but left empty, are "Greetings from"."""
    config = config or {}
    kind = str(config.get("postcard_greeting") or "greetings").casefold()
    if kind == "none":
        return ""
    if kind == "custom":
        own = " ".join(str(config.get("postcard_greeting_text") or "").split())[:GREETING_MAX]
        return own or GREETING_WORDS["greetings"]
    return GREETING_WORDS.get(kind, GREETING_WORDS["greetings"])


def greeting_line(card):
    """The card's first line in words: "Greetings from Hatchooe AB 3",
    "Wish you were here · Hatchooe AB 3", or just the place."""
    title = str(card.get("title") or "")
    words = str(card.get("greeting", GREETING_WORDS["greetings"]) or "").strip()
    if not words:
        return title
    if words.split()[-1].casefold() in {"from", "at", "in", "to", "on", "near"}:
        return f"{words} {title}"
    return f"{words} · {title}"


def postcard_options(config):
    """Overlay Studio's choices for the postcards."""
    config = config or {}
    hold = _integer(config.get("postcard_hold_s"), DEFAULT_HOLD)
    size = str(config.get("postcard_size") or "standard").casefold()
    style = str(config.get("postcard_style") or "polaroid").casefold()
    return {
        "hold": hold if hold in HOLDS else DEFAULT_HOLD,
        "photo": bool(config.get("postcard_photo", True)),
        # What the journal knows of the place, and the Watcher's note.
        "facts": bool(config.get("postcard_facts", True)),
        "note": bool(config.get("postcard_note", True)),
        # What you were doing (in supercruise, landed, docked at…).
        "doing": bool(config.get("postcard_doing", True)),
        "style": style if style in STYLES else "polaroid",
        "size": size if size in SIZES else "standard",
        # The lettering over the place's name ("" for none, 5.5.3.8).
        "greeting": greeting_text(config),
    }


# What you were doing, from the Navigation HUD's flight state.
def doing(state, body="", station="", vehicle=""):
    state = str(state or "").upper()
    on = f" on {body}" if body else ""
    if state == "DOCKED":
        return f"Docked at {station}" if station else "Docked"
    if state == "LANDED":
        return f"Landed{on}"
    if state == "ONFOOT":
        return f"On foot at {station}" if station and not body else f"On foot{on}"
    if state in {"SRV", "NOMAD", "SCARAB", "SCORPION", "RHINO"}:
        name = state.title() if state != "SRV" else "the SRV"
        return f"Driving {name}{on}" if state == "SRV" else f"In the {name}{on}"
    if state == "SUPERCRUISE":
        return f"In supercruise near {body}" if body else "In supercruise"
    if state == "TAXI":
        return "Riding a taxi"
    if state == "MULTICREW":
        return "Crewing on another ship"
    if state == "FIGHTER" or "FIGHTER" in state:
        return "Flying a fighter"
    return f"In flight near {body}" if body else "In flight"


def _coordinate(value, positive, negative):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{abs(number):.4f}° {positive if number >= 0 else negative}"


# What a body is, as the journal names it, in the words a postcard uses.
_STARS = {"N": "Neutron star", "H": "Black hole", "SupermassiveBlackHole": "Supermassive black hole",
          "TTS": "T Tauri star", "AeBe": "Herbig Ae/Be star", "MS": "S-type star", "S": "S-type star",
          "X": "Exotic star"}
RARE_KINDS = frozenset({"earth-like world", "water world", "ammonia world"})


def body_kind(item):
    """'Water world', 'Class K star', 'Neutron star'… or '' (5.5.3.7)."""
    item = item or {}
    star = str(item.get("star_type") or "")
    if star:
        if star in _STARS:
            return _STARS[star]
        if star.startswith("D"):
            return "White dwarf"
        if star.startswith("W"):
            return "Wolf-Rayet star"
        if star.startswith("C"):
            return "Carbon star"
        if star in {"L", "T", "Y"}:
            return "Brown dwarf"
        return f"Class {star} star" if len(star) <= 2 else f"{star} star"
    planet = str(item.get("planet_class") or "").strip()
    if not planet or planet.casefold() == "unknown":
        return ""
    planet = {"Earthlike body": "Earth-like world", "Metal rich body": "Metal-rich world"}.get(planet, planet)
    planet = planet.replace("Sudarsky class ", "Class ")
    return planet[:-5] + " world" if planet.endswith(" body") else planet


def postcard_facts(item=None, from_sol=None):
    """What the journal knows of the place, in a few words each: what it is,
    terraformable, gravity, firsts, life, and how far from Sol (5.5.3.7)."""
    item = item or {}
    facts = []
    kind = body_kind(item)
    if kind:
        facts.append(kind)
    if item.get("terraformable"):
        facts.append("Terraformable")
    try:
        gravity = float(item.get("gravity_g"))
    except (TypeError, ValueError):
        gravity = None
    if gravity is not None and item.get("landable"):
        facts.append(f"{gravity:.2f} G")
    if item.get("first_footfall"):
        facts.append("First footfall")
    elif item.get("was_discovered") is False:
        facts.append("First discovered")
    try:
        life = int(item.get("bio_count") or 0)
    except (TypeError, ValueError):
        life = 0
    if life:
        facts.append(f"{life} biological signal{'s' if life != 1 else ''}")
    if from_sol is not None:
        facts.append(f"{float(from_sol):,.0f} ly from Sol")
    return facts


def postcard_card(raw, *, state="", system="", station="", body_name="", serial=0, now=None,
                  region="", facts=None, note="", kind=""):
    """One card from a Screenshot event and what the app knows of the moment:
    the region, the journal's facts and a note from the Watcher (5.5.3.7)."""
    raw = raw if isinstance(raw, dict) else {}
    body = str(raw.get("Body") or body_name or "").strip()
    system = str(raw.get("System") or system or "").strip()
    stamp = str(raw.get("timestamp") or "")
    date_text, moment = elite_date(stamp)
    local = ""
    if moment is not None:
        local = moment.replace(tzinfo=_datetime.timezone.utc).astimezone().strftime("%H:%M")
    title = body or system or "Somewhere out here"
    # The system on its own line when the title is a body in it.
    place = system if body and system and body.casefold() != system.casefold() else ""
    # On a surface: where exactly.
    latitude, longitude = raw.get("Latitude"), raw.get("Longitude")
    coordinates = ""
    if latitude is not None and longitude is not None:
        coordinates = f"{_coordinate(latitude, 'N', 'S')} · {_coordinate(longitude, 'E', 'W')}"
    filename = os.path.basename(str(raw.get("Filename") or "").replace("\\", "/"))
    return {
        "id": f"{int(now if now is not None else time.time() * 1000)}-{int(serial)}",
        "title": title,
        "place": place,
        # What you were doing, without repeating the title.
        "doing": doing(state, "", station if str(station or "").casefold() != title.casefold() else ""),
        "coordinates": coordinates,
        "date": date_text,
        "time": local,
        "file": filename,
        "high_res": filename.casefold().startswith("highres"),
        "photo": False,
        # For "Greetings from…": the place, and the region under it.
        "region": str(region or ""),
        "greeting": GREETING_WORDS["greetings"],
        "kind": str(kind or ""),
        "facts": [str(fact) for fact in (facts or ()) if fact],
        "note": str(note or ""),
    }


def caption_text(card):
    """The card as words, for a caption file beside the picture."""
    lines = [greeting_line(card)]
    where = " · ".join(part for part in (card.get("place"), card.get("region")) if part)
    if where:
        lines.append(where)
    lines.append(card.get("doing") or "")
    if card.get("coordinates"):
        lines.append(card["coordinates"])
    if card.get("facts"):
        lines.append(" · ".join(card["facts"]))
    if card.get("note"):
        lines.append(f'"{card["note"]}" (the Watcher)')
    when = " · ".join(part for part in (card.get("date"), card.get("time")) if part)
    if when:
        lines.append(when)
    return "\n".join(line for line in lines if line) + "\n"


def find_screenshot(folder, filename, taken_at=None):
    """The picture a Screenshot event names: the game's BMP, or, once the
    screenshot converter has been at it, the newest PNG written since."""
    if not folder or not os.path.isdir(folder):
        return None
    if filename:
        bmp = os.path.join(folder, filename)
        if os.path.isfile(bmp):
            return bmp
    since = (taken_at or time.time()) - 5.0
    newest = None
    try:
        for name in os.listdir(folder):
            if not name.lower().endswith(".png"):
                continue
            path = os.path.join(folder, name)
            try:
                modified = os.path.getmtime(path)
            except OSError:
                continue
            if modified >= since and (newest is None or modified > newest[0]):
                newest = (modified, path)
    except OSError:
        return None
    return newest[1] if newest else None


def make_thumbnail(path, width=THUMBNAIL_WIDTH):
    """A small JPEG of the picture for the card, or None if it can't be read
    yet (the game may still be writing it)."""
    from voidcompass.overlays.postcard_picture import jpeg_thumbnail, open_picture
    picture = open_picture(path)
    return jpeg_thumbnail(picture, width) if picture is not None else None
