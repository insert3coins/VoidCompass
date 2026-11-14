"""The Rig Tracker's Rhino sections: everything about working a mining
location in the one overlay, each section on or off in Overlay Studio.

- **Guide:** the step you're on in working a mining location, the key for it,
  and what comes next. It moves on by itself as each step is done.
- **Deposit:** the marked deposit you're nearest, what's known of it and
  the location it's in (the Rhino Map is the map: no radar here).
- **Targets:** the nearest deposits, which way and how far, and what the
  ground round you is worth by commodity. Not the rigs: the dials have them.
- **Status:** an estimate of what's here, the drive through it, what a rig
  gives, the rig radar's word and the best patches; and a red bar for high
  gravity or a rig about to be lost.

Built from the Rhino map's model (surface_map), so they always agree."""
from __future__ import annotations

import math

SECTIONS = ("guide", "deposit", "targets", "status")
DEPOSIT_NEAR_M = 500.0
TARGETS_SHOWN = 6
STEPS = 8


def section_options(config):
    config = config or {}
    return {name: bool(config.get(f"rig_tracker_{name}", True)) for name in SECTIONS}


def guide_step(facts, keys=None):
    """{"step", "total", "title", "detail", "key", "next"} for where you are
    in working a mining location. The survey is the start of the work, not a
    gate: once a deposit is marked or a rig is down, the guide follows that."""
    keys = keys or {}
    rigs, live = int(facts.get("rigs") or 0), int(facts.get("deposits") or 0)

    def step(number, title, detail, key="", following=""):
        bound = keys.get(key, "") if key else ""
        if key and not bound and keys:
            bound = "NO KEY SET · SETTINGS › HOTKEYS"
        return {"step": number, "total": STEPS, "title": title, "detail": detail, "key": bound, "next": following}

    if not facts.get("on_planet"):
        signals = int(facts.get("signals") or 0)
        detail = (f"{signals} mining location{'s' if signals != 1 else ''} on this body: target one and land by it"
                  if signals else "Map a body with the DSS: it shows its mining locations. Target one and land by it")
        return step(1, "FIND A MINING LOCATION", detail, following="Deploy the Rhino")
    if not facts.get("in_srv"):
        return step(2, "DEPLOY THE RHINO", "Out of glide, down under 30 m, then deploy", following="Mark the survey centre")
    if facts.get("ready"):
        return step(8, f"COLLECT RIG {facts['ready']}", "It's had its time: drive back to it and collect it",
                    f"rig_{facts['ready']}", "Next rig, or back to the ship")
    if facts.get("hold_full"):
        return step(8, "BACK TO THE SHIP", "The Rhino's hold is full: dock it and move the cargo across", following="Next deposit")
    if rigs >= 6:
        return step(8, "COLLECT THE RIGS", "All six down: collect each when its dial says READY, in the order they went down",
                    f"rig_{facts.get('next_rig') or 1}", "Next deposit")
    if rigs:
        slot = int(facts.get("free_slot") or rigs + 1)
        return step(7, f"RIG {slot} DOWN", facts.get("rig_words") or "Where the next rig can go", f"rig_{slot}",
                    "Collect each when its dial says READY")
    if live and not facts.get("plan"):
        return step(6, "PLAN THE RIGS", "Trace the deposit's edge, or just put rig 1 down", "rhino_trace", "Rigs down")
    if live:
        return step(7, "RIG 1 DOWN", facts.get("rig_words") or "On the first pin of your plan", "rig_1",
                    "Collect each when its dial says READY")
    if not facts.get("survey"):
        return step(3, "MARK THE SURVEY CENTRE", "Drive to the middle of the mining location, or mark a deposit if you're on one",
                    "rhino_survey_centre", "Mark its edge")
    if not facts.get("edge"):
        detail = (f"Keep the scanner held. The centre is {facts['centre']} away: mark the edge on the location's edge line"
                  if facts.get("edge_ok") else "Hold the mineral scanner down and drive out to the location's edge line")
        return step(4, "MARK THE SURVEY EDGE", detail, "rhino_survey_edge", "Mark the deposits")
    sweep = facts.get("sweep")
    detail = f"Keep the scanner held. Next sweep stop {sweep}" if sweep else "Drive onto each deposit the scanner shows"
    return step(5, "MARK THE DEPOSITS", detail, "rhino_deposit_mark", "Plan the rigs")


def _way(you, at):
    dx, dy = at[0] - you[0], at[1] - you[1]
    return round(math.hypot(dx, dy)), round(math.degrees(math.atan2(dx, dy)) % 360.0)


def _metres(value):
    return f"{value / 1000:.1f} km" if value >= 1000 else f"{round(value)} m"


def sections_model(surface, *, keys=None, holds=(), gravity=None, threshold=3.0, facts=None, options=None, prices=None):
    """The Rig Tracker's sections from the Rhino map's model, or None without one."""
    if not surface or not (surface.get("you") or {}).get("at"):
        return None
    options = options or section_options({})
    you = surface["you"]["at"]
    deposits = list(surface.get("deposits") or ())
    live = [item for item in deposits if not item.get("depleted")]
    rigs = list(surface.get("rigs") or ())
    value = surface.get("value") or {}
    from voidcompass.overlays.surface_map import price_of, rig_words
    words = rig_words(surface)
    # Your rigs and what they've refined: shown when nothing is marked yet, and
    # priced at what you're paid (or the usual price).
    worked = []
    for rig in rigs:
        if not rig.get("at"):
            continue
        distance, bearing = _way(you, rig["at"])
        price = price_of(rig.get("commodity"), prices) if rig.get("tonnes") else None
        worked.append({"slot": rig["slot"], "commodity": rig.get("commodity") or "", "tonnes": int(rig.get("tonnes") or 0),
                       "distance": distance, "bearing": bearing, "at": rig["at"],
                       "value": round(price * int(rig["tonnes"])) if price else None})
    model = {"heading": surface["you"].get("heading"), "sections": [name for name in SECTIONS if options.get(name)],
             "signal": surface.get("signal")}

    # A red bar: a rig about to be lost, else high gravity.
    last = next((row for row in surface.get("too_far") or () if row.get("last")), None)
    if last:
        model["hazard"] = f"RIG {last['slot']} {last['distance'] / 1000:.1f} KM · LOST AT 5 KM"
    elif gravity is not None and gravity >= threshold:
        model["hazard"] = f"HIGH GRAVITY · {gravity:.2f} G"

    if options.get("guide"):
        ready = next((rig["slot"] for rig in rigs if rig.get("ready")), None)
        taken = {rig["slot"] for rig in rigs}
        rhino = next((row for row in holds or () if row.get("name") == "RHINO"), None)
        survey = surface.get("survey") or {}
        sweep = survey.get("next")
        model["guide"] = guide_step({
            "on_planet": True, "in_srv": surface.get("vehicle") in ("RHINO", "SRV"),
            "survey": bool(survey), "edge": bool(survey.get("edge")), "edge_ok": bool(survey.get("edge_ok")),
            "centre": _metres(survey["centre_m"]) if survey.get("centre_m") is not None else "",
            "deposits": len(live), "rigs": len(rigs),
            "plan": any(pin.get("n") for pin in surface.get("plan") or ()) and bool(surface.get("traced")),
            "ready": ready, "hold_full": bool(rhino and rhino.get("free") == 0),
            "free_slot": next((slot for slot in range(1, 7) if slot not in taken), 1), "next_rig": surface.get("next_rig"),
            "rig_words": words[0] if words else "", "signals": surface.get("signals"),
            "sweep": _metres(sweep["distance"]) if sweep else "",
            **(facts or {})}, keys)

    if options.get("deposit"):
        near = min(deposits, key=lambda item: item.get("distance") or 0, default=None)
        card = None
        if near and (near.get("distance") or 0) <= DEPOSIT_NEAR_M:
            card = {key: near.get(key) for key in ("commodity", "distance", "bearing", "rigs", "density", "amount",
                                                   "depleted", "value", "signal", "regrowth", "due")}
        else:
            # Nothing marked here: the rig you're nearest, and what it has given.
            rig = min(worked, key=lambda row: row["distance"], default=None)
            if rig and rig["distance"] <= DEPOSIT_NEAR_M:
                card = {"rig": rig["slot"], "commodity": rig["commodity"], "distance": rig["distance"],
                        "bearing": rig["bearing"], "tonnes": rig["tonnes"], "value": rig["value"]}
        model["deposit"] = {"near": card, "count": len(live), "rigs": value.get("rigs") or 0,
                            "credits": value.get("credits"),
                            "refined": sum(rig["tonnes"] for rig in worked),
                            "refined_value": sum(rig["value"] or 0 for rig in worked) or None}

    if options.get("targets"):
        rows = [{"commodity": item["commodity"], "distance": item.get("distance"), "bearing": item.get("bearing"),
                 "rigs": item.get("rigs") or 0, "depleted": bool(item.get("depleted"))} for item in deposits]
        rows = sorted(rows, key=lambda row: row.get("distance") or 0)[:TARGETS_SHOWN]
        worth, refined = {}, False
        for item in live:
            if item.get("value"):
                worth[item["commodity"]] = worth.get(item["commodity"], 0) + item["value"]
        if not worth:
            # Before there's a deposit value, what your rigs have refined here.
            for rig in worked:
                if rig["value"]:
                    worth[rig["commodity"]] = worth.get(rig["commodity"], 0) + rig["value"]
                    refined = True
        model["targets"] = {"rows": rows, "refined": refined,
                            "bars": [{"commodity": name, "credits": credits} for name, credits in
                                     sorted(worth.items(), key=lambda pair: -pair[1])[:6]]}

    if options.get("status"):
        model["status"] = {
            "deposits": value.get("deposits", len(live)), "rigs": value.get("rigs", 0),
            "credits": value.get("credits"), "unpriced": value.get("unpriced", 0), "per_rig": value.get("per_rig"),
            "route_m": value.get("route_m", 0),
            "words": words[0] if words else "", "tone": words[1] if words else "",
            "groups": [{key: group.get(key) for key in ("n", "rigs", "credits", "cr_per_h", "distance", "bearing")}
                       for group in surface.get("groups") or ()],
        }
    return model
