"""Commander-owned names, spoken phrases and bound-action commands."""
from copy import copy
from functools import lru_cache
import re

from voidcompass.core import elite_macros
from voidcompass.overlays import watcher_ship, watcher_copilot, watcher_chat

POWER_NAMES = {"sys": "more power to systems", "eng": "more power to engines",
               "wep": "more power to weapons", "reset": "balance power"}


@lru_cache(maxsize=1)
def builtins():
    commands = list(watcher_ship.COMMANDS)
    for step, phrase in POWER_NAMES.items():
        command = watcher_ship.Command("power_" + step, phrase, "press",
            {where: actions[step] for where, actions in watcher_ship.POWER_ACTIONS.items()},
            re.escape(phrase), "Power", example=phrase)
        command.power_step = step
        commands.append(command)
    names = {"music_play": "play music", "music_pause": "stop music", "music_next": "next track",
             "music_previous": "previous track", "overlays_hide": "hide the overlays",
             "overlays_show": "show the overlays", "copy_next": "copy the next system",
             "hush": "be quiet", "unhush": "speak again"}
    def native(ident, phrase, group, target):
        command = watcher_ship.Command(ident, phrase, "press", {}, re.escape(phrase), group, example=phrase)
        command.native = target
        commands.append(command)
    for action, phrase in names.items():
        native("app_" + action, phrase, "Music" if action.startswith("music_") else "App controls",
               {"kind": "intent", "value": action})
    for overlay, aliases in watcher_copilot.OVERLAY_NAMES.items():
        for op in ("show", "hide", "on", "off"):
            verb = "turn " + op if op in ("on", "off") else op
            native("app_overlay_" + overlay.replace("-", "_") + "_" + op,
                   verb + " " + aliases[0], "Overlays", {"kind": "overlay", "overlay": overlay, "op": op})
    # 5.7.5: "hello", to any companion ("hello Meridian" works too); it was "hello watcher".
    native("app_greeting", "hello", "Conversation", {"kind": "chat", "value": "greeting"})
    native("app_capabilities", "what can you do", "Conversation", {"kind": "chat", "value": "capabilities"})
    for kind in ("buy", "sell"):
        native("app_uplink_" + kind, "where can I " + kind + " {commodity}", "Market uplink",
               {"kind": "uplink", "value": kind})
    return commands


def native_context(text):
    overlay = watcher_copilot.overlay_request(text)
    return {"overlay": overlay, "intent": None if overlay else watcher_copilot.intent(text),
            "chat": watcher_chat.intent(text), "uplink": ("buy" if watcher_copilot._TO_BUY.search(text) else "sell")
            if watcher_copilot._UPLINK.search(text) else None}


def native_matches(command, text, context=None):
    target = getattr(command, "native", {})
    kind = target.get("kind")
    if not kind:
        return False
    context = context if context is not None else native_context(text)
    if kind == "overlay":
        return context["overlay"] == {key: target[key] for key in ("overlay", "op")}
    return context.get(kind) == target.get("value")


def literal_match(command, text):
    words = watcher_ship.literal_words(text)
    for phrase in command.phrases:
        literal = watcher_ship.literal_words(phrase)
        if "{commodity}" not in literal:
            if literal == words:
                return {}
            continue
        pattern = re.escape(literal).replace(re.escape("{commodity}"), r"(?P<commodity>.+)")
        found = re.fullmatch(pattern, words)
        if found:
            return found.groupdict()
    return None


def native_request(text, definitions=None, kind=None):
    context = native_context(text)
    for command in catalogue(definitions):
        target = getattr(command, "native", None)
        if target is None or (kind is not None and target["kind"] != kind):
            continue
        matched = literal_match(command, text)
        if matched is not None or (command.keep_defaults and native_matches(command, text, context)):
            return command, matched or {}
    return None


def catalogue(definitions=None, include_disabled=False):
    definitions = definitions if isinstance(definitions, dict) else {}
    originals = {command.id: command for command in builtins()}
    commands = []
    for ident in (*originals, *(key for key in definitions if key not in originals)):
        data = definitions.get(ident, {})
        if not isinstance(data, dict):
            continue
        if ident in originals:
            command = copy(originals[ident])
        else:
            try:
                sequence = data.get("sequence", [])
                actions = elite_macros.actions_in(elite_macros.parse_macro(sequence))
                command = watcher_ship.Command(ident, data["name"], "press",
                    {where: actions[0] for where in data.get("places", ["ship"])},
                    re.escape(data["phrase"]), data.get("group") or "Custom commands",
                    example=data["phrase"], macro=sequence, done=(data.get("reply") or "Done.",))
            except (ValueError, KeyError, TypeError):
                continue
        command.custom = ident not in originals
        command.enabled = data.get("enabled", True)
        command.keep_defaults = data.get("keep_defaults", True) and not command.custom
        command.say = data.get("name") or command.say
        command.example = data.get("phrase") or command.example
        command.group = data.get("group") or command.group
        command.aliases = tuple(data.get("aliases", []))
        command.phrases = tuple(dict.fromkeys((command.example, *command.aliases)))
        if command.enabled or include_disabled:
            commands.append(command)
    return commands


def validate(value):
    if not isinstance(value, dict) or len(value) > 400:
        raise ValueError("Use an object with at most 400 command definitions.")
    known = {command.id for command in builtins()}
    result = {}
    for ident, raw in value.items():
        if ident not in known and not re.fullmatch(r"custom_[a-z0-9_]{1,48}", str(ident)):
            raise ValueError("Custom command IDs must start with custom_.")
        if not isinstance(raw, dict):
            raise ValueError("Each command needs a name, phrase and aliases.")
        data = {}
        for field in ("name", "phrase", "group", "reply"):
            if field in raw:
                text = raw[field]
                limit = 70 if field == "phrase" else 300 if field == "reply" else 80
                if not isinstance(text, str) or not text.strip() or len(text) > limit or any(ord(c) < 32 for c in text):
                    raise ValueError(f"{field.title()} must be non-empty text, up to {limit} characters.")
                data[field] = text.strip()
        aliases = raw.get("aliases", [])
        if not isinstance(aliases, list) or len(aliases) > 30 or any(
                not isinstance(alias, str) or not alias.strip() or len(alias) > 70 or any(ord(c) < 32 for c in alias)
                for alias in aliases):
            raise ValueError("Use at most 30 aliases, each up to 70 characters.")
        data["aliases"] = list(dict.fromkeys(alias.strip() for alias in aliases))
        for field in ("enabled", "keep_defaults"):
            if field in raw:
                if not isinstance(raw[field], bool):
                    raise ValueError(f"{field} must be on or off.")
                data[field] = raw[field]
        if ident not in known:
            if not data.get("name") or not data.get("phrase"):
                raise ValueError("Custom commands need a name and a spoken phrase.")
            sequence = raw.get("sequence")
            elite_macros.parse_macro(sequence)
            data["sequence"] = list(sequence)
            places = raw.get("places", ["ship"])
            if not isinstance(places, list) or not places or any(place not in ("ship", "srv", "foot") for place in places):
                raise ValueError("Choose ship, SRV or on foot for the command.")
            data["places"] = list(dict.fromkeys(places))
        result[ident] = data
    commands = catalogue(result, include_disabled=True)
    owners = {}
    for command in commands:
        if not command.enabled:
            continue
        for phrase in command.phrases:
            words = watcher_ship.literal_words(phrase)
            if not words:
                raise ValueError("Use a non-empty spoken phrase.")
            owner = owners.setdefault(words, command.id)
            if owner != command.id:
                raise ValueError(f"{phrase!r} is already used by another command.")
            if command.id in result:
                context = native_context(phrase)
                for other in commands:
                    if other.id != command.id and other.enabled and other.keep_defaults and (
                            native_matches(other, phrase, context) if hasattr(other, "native") else other.pattern.fullmatch(watcher_ship._clean(phrase))):
                        raise ValueError(f"{phrase!r} already matches {other.example!r}.")
                if command.custom and watcher_ship.power_request(phrase):
                    raise ValueError(f"{phrase!r} is already a power-distributor command.")
                if getattr(command, "native", {}).get("kind") == "uplink" and "{commodity}" not in phrase:
                    raise ValueError("Market-search phrases must include {commodity}.")
    return result
