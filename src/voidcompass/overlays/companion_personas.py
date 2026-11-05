"""Each officer-style companion's own writing, behind one shared mind (5.7.4).

The Watcher keeps its own mind. Aster, Axiom and Meridian share AsterMind's
plumbing (pacing, rotation, memory, name flow, queue) and differ only in what
they say and how their story unfolds.
"""
from types import SimpleNamespace

_SPEC = {
    "aster": {"lines": "aster_lines", "lore": "aster_lore", "name": "aster_name", "postcards": "aster_postcards", "keepsakes": "aster_keepsakes",
              "humour": ("Officer’s commentary", (("dry", "Dry wit"), ("off", "Restrained"))),
              "watch": "OFFICER ON WATCH", "advisory": "FLIGHT ADVISORY", "reply": "OFFICER'S REPLY",
              "asks": "ASTER ASKS", "pace": 1.02, "signature": "Aster",
              "test": "Aster, reporting for duty. Clear instructions, a sound ship, and room for an occasional improvement to the itinerary."},
    "axiom": {"lines": "axiom_lines", "lore": "axiom_lore", "name": "axiom_name", "postcards": "axiom_postcards", "keepsakes": "axiom_keepsakes",
              "humour": ("Axiom’s commentary", (("dry", "Curious"), ("off", "Precise"))),
              "watch": "AXIOM · OBSERVING", "advisory": "AXIOM · ADVISORY", "reply": "AXIOM'S ANSWER",
              "asks": "AXIOM ASKS", "pace": 1.0, "signature": "Axiom",
              "test": "Axiom online. This is my voice. I have checked it twice. Ready to assist with your next observation, Commander."},
    "meridian": {"lines": "meridian_lines", "lore": "meridian_lore", "name": "meridian_name", "postcards": "meridian_postcards", "keepsakes": "meridian_keepsakes",
                 "humour": ("Meridian’s commentary", (("dry", "Reflective"), ("off", "Plain"))),
                 "watch": "MERIDIAN · ON THE BRIDGE", "advisory": "MERIDIAN · NAVIGATION", "reply": "MERIDIAN'S REPLY",
                 "asks": "MERIDIAN ASKS", "pace": .98, "signature": "Meridian",
                 "test": "Meridian, on watch. This is my voice. Steady as she goes, Commander. Ready when you are."},
}
IDENTITIES = tuple(_SPEC)
_CACHE = {}


def _module(name):
    return _modules()[name]


def _modules():
    # Note: explicit imports, not importlib by name. PyInstaller only bundles
    # modules it can see imported, and the frozen app crashed without these.
    from voidcompass.overlays import (
        aster_keepsakes, aster_lines, aster_lore, aster_name, aster_postcards,
        axiom_keepsakes, axiom_lines, axiom_lore, axiom_name, axiom_postcards,
        meridian_keepsakes, meridian_lines, meridian_lore, meridian_name, meridian_postcards,
    )
    return {module.__name__.rsplit(".", 1)[-1]: module for module in (
        aster_keepsakes, aster_lines, aster_lore, aster_name, aster_postcards,
        axiom_keepsakes, axiom_lines, axiom_lore, axiom_name, axiom_postcards,
        meridian_keepsakes, meridian_lines, meridian_lore, meridian_name, meridian_postcards)}


def get(identity):
    """The persona for an identity, or None for the Watcher/unknown IDs."""
    if identity not in _SPEC:
        return None
    if identity not in _CACHE:
        spec = _SPEC[identity]
        lore = _module(spec["lore"])
        name = _module(spec["name"])
        label, choices = spec["humour"]
        _CACHE[identity] = SimpleNamespace(
            identity=identity, lines=_module(spec["lines"]), lore=lore, story=lore.STORY,
            naming=getattr(name, "ARC", name), postcards=_module(spec["postcards"]), keepsakes=_module(spec["keepsakes"]),
            humour_key=f"{identity}_humour", humour_label=label, humour_choices=choices,
            watch_heading=spec["watch"], advisory_heading=spec["advisory"], reply_heading=spec["reply"],
            asks_heading=spec["asks"], lore_pace=spec["pace"], signature=spec["signature"], test_line=spec["test"],
            interests=dict(getattr(_module(spec["lines"]), "INTERESTS", {})))
    return _CACHE[identity]


def restrained(identity, config):
    persona = get(identity)
    return bool(persona) and (config or {}).get(persona.humour_key, "dry") == "off"
