"""Postcard notes in an officer-style companion's own hand (5.7.4)."""
import random
import string

from voidcompass.overlays.watcher_postcards import moments


def postcard_note(plain, voiced, card, *, restrained=False, from_sol=None, state="", rng=None, recent=()):
    """Use true context and rotate templates through the persona's persisted picker."""
    rng = rng or random.Random()
    fields = {"place": str(card.get("title") or ""), "kind": str(card.get("kind") or "").lower(),
              "region": str(card.get("region") or ""),
              "far": f"{float(from_sol):,.0f}" if from_sol is not None else ""}
    parser = string.Formatter()
    if str(state).upper() == "ONFOOT" and str(card.get("doing") or "").startswith("On foot at "):
        state = "DOCKED"  # A station concourse is not a planetary surface.
    for moment in (*moments(card, from_sol, state), "any"):
        if moment != "any" and rng.random() >= .7:
            continue
        lines = plain.get(moment, ()) + (() if restrained else voiced.get(moment, ()))
        eligible = [line for line in lines
                    if all(fields.get(name) for _, name, _, _ in parser.parse(line) if name)]
        if not eligible:
            continue
        picker = getattr(rng, "dialogue_choice", None)
        if callable(picker):
            # Templates, rather than rendered places, retain their rotation
            # when the commander photographs another world.
            line = picker(f"postcard:{'plain' if restrained else 'dry'}:{moment}", tuple(eligible))
        else:
            fresh = [line for line in eligible if line.format(**fields) not in recent]
            line = rng.choice(fresh or eligible)
        return line.format(**fields)
    return ""
