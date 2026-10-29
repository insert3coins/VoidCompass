"""Hatchling (5.6.3): a pocket pet in the cockpit, after the Tamagotchi.

It lives in real time, VoidCompass open or not: its needs fall by the hour
and catch up from the clock when it's loaded. How it fares comes partly
from the Games page (feeding, playing, venting the hold) and partly from
how you really play, read from the journal: food bought at a market stocks
its larder, exploring keeps it curious, combat scares it.

It can't die. Left long enough with no health it hibernates, and care
brings it back; a week hibernating and it is gone for good, into the
memorial, and a new egg can be chosen.

Since 5.6.4 it also notices what you're doing right now (a cue for the page
to act out), finds toys on your trips, learns tricks, grows a personality
from how it's raised, and dreams of where you've been. It knows the world
you're on (its gravity and heat), rides along in the SRV, misses you on
foot, greets you after time away, keeps a diary for the Captain's Log and
earns outfits. It comes along on your expeditions, keeps its own diary of
each, and earns a badge for every one you finish together.

Everything here is plain data in, plain data out: the deck keeps one per
commander in the profile folder.
"""

from __future__ import annotations

import copy
import json
import re

from voidcompass.core import hatchling_chatter

NEEDS = ("hunger", "mood", "clean", "health", "energy")
STAGES = (("egg", 0.5), ("hatchling", 24.0), ("juvenile", 72.0), ("adult", None))
HIBERNATE_DAYS = 7
STORES_EVERY_H = 24
STORES_COUNT = 3
LARDER_MOST = 99
LOG_KEEP = 14
STEP_H = 1 / 6          # the clock catches up ten minutes at a time
CATCH_UP_DAYS = 30

SPECIES = {
    "larva": {
        "name": "Thargoid larva", "food": "HUNGER", "stores": "foodcartridges",
        "blurb": "From a strange egg found in a damaged Thargoid structure. It hums, glows green when happy, and hates Guardian things.",
        "forms": {"standard": "Drone", "explored": "Wanderer", "scarred": "Battle-born", "neglected": "Husk", "rare": "Hive Herald"},
        "names": ("Hum", "Glim", "Xeno", "Pip", "Thrumm"),
    },
    "thargoid": {
        "name": "Thargoid foundling", "food": "NOURISHMENT", "stores": "foodcartridges",
        "blurb": "Found by the Watcher, this little traveller grows from Scout to Thargon to Orthrus.",
        "forms": {"standard": "Orthrus", "explored": "Wayfarer Orthrus", "scarred": "Weathered Orthrus",
                  "neglected": "Quiet Orthrus", "rare": "Hive-lit Orthrus"},
        "names": ("Vela", "Khepri", "Nacre", "Nyx", "Glimmer"),
        "stages": {"egg": "Egg", "hatchling": "Scout", "juvenile": "Thargon", "adult": "Orthrus"},
    },
    "bot": {
        "name": "Remlok companion bot", "food": "POWER", "stores": "hydrogenfuel",
        "blurb": "A little maintenance drone that beeps and wants upgrades, not food.",
        "forms": {"standard": "Maintenance Unit", "explored": "Pathfinder", "scarred": "Salvager", "neglected": "Rust Bucket",
                  "rare": "Cartographer Prime"},
        "names": ("Bolt", "Widget", "R3-MK", "Sprocket", "Beep"),
    },
    "sample": {
        "name": "Exobiology sample", "food": "NUTRIENTS", "stores": "algae",
        "blurb": "Grown in a sample canister: it needs light, warmth and the right atmosphere.",
        "forms": {"standard": "Colony", "explored": "Wildbloom", "scarred": "Scorched", "neglected": "Wilted", "rare": "Luminous Bloom"},
        "names": ("Spore", "Moss", "Tubby", "Fungi", "Bloom"),
    },
}
SAMPLE_KINDS = {"bacterium": "Bacterium", "tubus": "Tubus", "fungoida": "Fungoida"}

# The larder: journal commodity symbols, who eats them and what they do.
ITEMS = {
    "foodcartridges": {"name": "Food Cartridges", "kind": "snack", "fill": 14, "mood": 0, "for": ("larva", "thargoid")},
    "syntheticmeat": {"name": "Synthetic Meat", "kind": "meal", "fill": 30, "mood": 2, "for": ("larva", "thargoid")},
    "animalmeat": {"name": "Animal Meat", "kind": "meal", "fill": 36, "mood": 4, "for": ("larva", "thargoid")},
    "fish": {"name": "Fish", "kind": "meal", "fill": 34, "mood": 6, "for": ("larva", "thargoid")},
    "fruitandvegetables": {"name": "Fruit and Vegetables", "kind": "meal", "fill": 26, "mood": 3, "for": ("larva", "thargoid", "sample")},
    "coffee": {"name": "Coffee", "kind": "treat", "fill": 6, "mood": 14, "for": ("larva", "thargoid", "sample")},
    "tea": {"name": "Tea", "kind": "treat", "fill": 6, "mood": 12, "for": ("larva", "thargoid", "sample")},
    "lavianbrandy": {"name": "Lavian Brandy", "kind": "treat", "fill": 4, "mood": 20, "for": ("larva", "thargoid")},
    "algae": {"name": "Algae", "kind": "snack", "fill": 14, "mood": 0, "for": ("sample",)},
    "grain": {"name": "Grain", "kind": "meal", "fill": 28, "mood": 2, "for": ("sample",)},
    "biowaste": {"name": "Biowaste", "kind": "meal", "fill": 34, "mood": 6, "for": ("sample",)},
    "hydrogenfuel": {"name": "Hydrogen Fuel", "kind": "snack", "fill": 14, "mood": 0, "for": ("bot",)},
    "powergenerators": {"name": "Power Generators", "kind": "meal", "fill": 36, "mood": 4, "for": ("bot",)},
    "robotics": {"name": "Robotics", "kind": "meal", "fill": 30, "mood": 8, "for": ("bot",)},
    "powerconverter": {"name": "Power Converter", "kind": "treat", "fill": 8, "mood": 16, "for": ("bot",)},
    "basicmedicines": {"name": "Basic Medicines", "kind": "medicine", "fill": 0, "mood": 0, "for": ("larva", "thargoid")},
    "advancedmedicines": {"name": "Advanced Medicines", "kind": "medicine", "fill": 0, "mood": 4, "for": ("larva", "thargoid")},
    "agronomictreatment": {"name": "Agronomic Treatment", "kind": "medicine", "fill": 0, "mood": 0, "for": ("sample",)},
    "microcontrollers": {"name": "Micro Controllers", "kind": "medicine", "fill": 0, "mood": 0, "for": ("bot",)},
}

# How long a cue stays worth acting out, and how many toys and places it keeps.
CUE_S = 30
TOYS_KEEP = 6
PLACES_KEEP = 12
LOW_FUEL = .25

# A trick is learned from what you do together (5.6.4).
TRICKS = (("spin", "games", "limpet", 4), ("flip", "games", "thargon", 4), ("wave", "care", "pats", 15),
          ("juggle", "care", "plays", 12), ("bow", "care", "treats", 8))
# Its personality: whichever has grown furthest past its mark.
TRAITS = {
    "curious": lambda care: (care["explored"] + 2 * care["discoveries"] + 5 * care["codex"]) / 60,
    "brave": lambda care: (care["scares"] + 3 * care["rebuys"] + care["fights"] / 2) / 25,
    "lazy": lambda care: care["naps"] / 12,
    "greedy": lambda care: (2 * care["treats"] + care["meals"] / 2) / 30,
    "clingy": lambda care: (care["pats"] + care["plays"]) / 30,
}
GAMES = {"limpet": "Catch the Limpet", "thargon": "Where did the Thargon go?"}
# Outfits it earns: (name, the count that earns it, how many).
OUTFITS = {
    "visor": ("Scanner visor", "explored", 500), "helmet": ("Mining helmet", "mined", 100),
    "charm": ("Guardian charm", "guardian", 3), "scarf": ("Explorer's scarf", "discoveries", 50),
    "bowtie": ("Bow tie", "treats", 30),
}
DIARY_KEEP = 200
WELCOME_AFTER_H = 3
WELCOME_SHOWN_S = 600

# Per hour: awake, then asleep (energy comes back while it sleeps).
# A day away leaves it hungry, not ill; about three and it hibernates.
DECAY = {"hunger": (3.0, 1.5), "mood": (2.0, 0.0), "clean": (2.0, 1.0), "energy": (4.0, -16.0)}


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_name(value, species):
    name = re.sub(r"[^\w '\-.]", "", str(value or ""), flags=re.UNICODE).strip()[:16]
    return name or SPECIES[species]["names"][0]


def new_pet(species, name="", kind="", now=0.0):
    species = species if species in SPECIES else "larva"
    kind = kind if species == "sample" and kind in SAMPLE_KINDS else ("bacterium" if species == "sample" else "")
    return {
        "species": species, "kind": kind, "name": _clean_name(name, species),
        "born": now, "last": now, "stage": "egg", "form": "",
        "needs": {"hunger": 70.0, "mood": 70.0, "clean": 100.0, "health": 100.0, "energy": 80.0},
        "asleep": False, "sick": False, "dormant_since": None, "revived": 0,
        "larder": {SPECIES[species]["stores"]: STORES_COUNT}, "stores_at": now,
        "care": {key: 0 for key in ("meals", "treats", "plays", "vents", "explored", "discoveries", "codex",
                                    "scares", "rebuys", "thargoid", "guardian", "neglect_h", "stations", "pats", "naps", "mined",
                                    "fights", "missions", "ranks")},
        "stations": [], "supercruise_since": None, "log": [], "reaction": "", "reaction_at": 0.0,
        "cue": None, "place": "space", "low_fuel": False, "fuel_capacity": 0.0, "foods": {}, "games": {},
        "toys": [], "tricks": [], "places": [], "moment": None,
        "world": None, "welcome": None, "diary": [], "outfits": [], "outfit": "", "ship": "",
        "trip": None, "badges": [],
    }


def new_state():
    return {"version": 1, "pet": None, "memorial": [], "forms_seen": []}


def load_state(text):
    try:
        state = json.loads(text)
    except (TypeError, ValueError):
        return new_state()
    if not isinstance(state, dict):
        return new_state()
    base = new_state()
    base.update({key: state.get(key) for key in base if key in state})
    if not isinstance(base["pet"], dict) or base["pet"].get("species") not in SPECIES:
        base["pet"] = None
    else:
        fresh = new_pet(base["pet"]["species"], base["pet"].get("name"), base["pet"].get("kind"))
        for key, value in fresh.items():
            base["pet"].setdefault(key, value)
        for key, value in fresh["care"].items():
            base["pet"]["care"].setdefault(key, value)
    base["memorial"] = [item for item in base["memorial"] or () if isinstance(item, dict)][-20:]
    base["forms_seen"] = [str(item) for item in base["forms_seen"] or ()][:60]
    return base


def moment(pet, now, kind, diary="", **fields):
    """Something worth the Watcher's notice (the deck passes it on), and a
    line in its diary for the Captain's Log."""
    pet["moment"] = {"kind": kind, "at": now, **{key: str(value) for key, value in fields.items()}}
    if diary:
        row = {"at": now, "text": str(diary)[:120]}
        if isinstance(pet.get("trip"), dict):
            row["trip"] = pet["trip"].get("id")
        pet["diary"] = (list(pet.get("diary") or []) + [row])[-DIARY_KEEP:]


def say(pet, now, text, tone="", reaction=""):
    pet["log"] = ([{"at": now, "text": str(text), "tone": tone}] + list(pet.get("log") or []))[:LOG_KEEP]
    if reaction:
        pet["reaction"], pet["reaction_at"] = reaction, now


def _stage_for(age_h):
    for name, until in STAGES:
        if until is None or age_h < until:
            return name
    return "adult"


def _adult_form(pet):
    care = pet["care"]
    rare = {"larva": care["thargoid"] >= 5, "thargoid": care["thargoid"] >= 5,
            "bot": care["discoveries"] >= 50, "sample": care["codex"] >= 3}[pet["species"]]
    if rare:
        return "rare"
    if care["neglect_h"] >= 24 or pet.get("revived"):
        return "neglected"
    if care["scares"] + care["rebuys"] * 5 >= 20:
        return "scarred"
    if care["explored"] >= 40 or care["discoveries"] >= 20:
        return "explored"
    return "standard"


def _grow(state, pet, now):
    stage = _stage_for((now - pet["born"]) / 3600)
    if stage == pet["stage"]:
        return
    pet["stage"] = stage
    if stage == "hatchling":
        say(pet, now, f"{pet['name']} hatched!", "good", "hatched")
        moment(pet, now, "grown", f"{pet['name']} hatched.", form="hatchling")
    elif stage == "juvenile":
        say(pet, now, f"{pet['name']} is growing up.", "good")
    elif stage == "adult":
        pet["form"] = _adult_form(pet)
        label = SPECIES[pet["species"]]["forms"][pet["form"]]
        seen = f"{pet['species']}:{pet['form']}"
        if seen not in state["forms_seen"]:
            state["forms_seen"].append(seen)
        say(pet, now, f"Fully grown: {label}.", "good", "grown")
        moment(pet, now, "grown", f"{pet['name']} grew up into a {label}.", form=label)


def _hour(state, pet, now, hours):
    """Let `hours` of real time pass (a short step)."""
    needs = pet["needs"]
    if pet["stage"] == "egg":
        return
    asleep = pet["asleep"]
    for need, (awake_rate, sleep_rate) in DECAY.items():
        needs[need] = _clamp(needs[need] - (sleep_rate if asleep else awake_rate) * hours)
    if pet["sick"]:
        needs["mood"] = _clamp(needs["mood"] - 2 * hours)
    low = [need for need in ("hunger", "clean", "mood") if needs[need] < 15]
    if low or pet["sick"]:
        needs["health"] = _clamp(needs["health"] - min(4.0, 2 * len(low) + (1.5 if pet["sick"] else 0)) * hours)
    elif needs["hunger"] > 50 and needs["clean"] > 50:
        needs["health"] = _clamp(needs["health"] + 2 * hours)
    if any(needs[need] < 20 for need in ("hunger", "mood", "clean", "health")):
        pet["care"]["neglect_h"] += hours
    if not pet["sick"] and needs["health"] < 40:
        pet["sick"] = True
        say(pet, now, f"{pet['name']} is ill.", "bad", "ill")
    if not asleep and needs["energy"] <= 5:
        pet["asleep"] = True
        say(pet, now, f"{pet['name']} fell asleep where it was.", "", "asleep")
    elif asleep and needs["energy"] >= 100:
        pet["asleep"] = False
        say(pet, now, f"{pet['name']} woke up.", "", "awake")
    if needs["health"] <= 0:
        pet["dormant_since"] = now
        pet["asleep"] = True
        say(pet, now, f"{pet['name']} has gone into hibernation. Care can still bring it back.", "bad", "dormant")


def advance(state, now):
    """Bring the pet up to `now`: its needs, its growing up, the ship's
    stores, and a hibernation that has lasted too long."""
    pet = state.get("pet")
    if not pet:
        return state
    last = _number(pet.get("last"), now)
    if now <= last:
        return state
    last = max(last, now - CATCH_UP_DAYS * 86400)
    while last < now:
        if pet.get("dormant_since") is not None:
            if now - pet["dormant_since"] >= HIBERNATE_DAYS * 86400:
                _lose(state, pet, pet["dormant_since"] + HIBERNATE_DAYS * 86400)
                return state
            last = now
            break
        step = min(STEP_H * 3600, now - last)
        last += step
        _grow(state, pet, last)
        _hour(state, pet, last, step / 3600)
    pet["last"] = now
    if now - _number(pet.get("stores_at"), now) >= STORES_EVERY_H * 3600 and pet.get("dormant_since") is None:
        item = SPECIES[pet["species"]]["stores"]
        pet["larder"][item] = min(LARDER_MOST, max(pet["larder"].get(item, 0), STORES_COUNT))
        pet["stores_at"] = now
    return state


def _lose(state, pet, when):
    state["memorial"] = (state.get("memorial") or [])[-19:] + [{
        "name": pet["name"], "species": pet["species"], "form": pet.get("form") or "",
        "stage": pet["stage"], "born": pet["born"], "lost": when,
    }]
    state["pet"] = None


def _fed_up(pet):
    return pet.get("dormant_since") is not None or pet["stage"] == "egg"


# ---- What you do on the Games page. ---------------------------------------------------------

def act(state, action, payload, now):
    """One thing done on the pet's screen. Returns (changed, message)."""
    payload = payload or {}
    advance(state, now)
    pet = state.get("pet")
    if action == "hatch":
        if pet:
            return False, "There's already one aboard."
        species = str(payload.get("species") or "")
        if species not in SPECIES:
            return False, "Choose an egg first."
        state["pet"] = new_pet(species, payload.get("name"), str(payload.get("kind") or ""), now)
        say(state["pet"], now, "An egg, warm in its cradle.", "good", "egg")
        return True, ""
    if not pet:
        return False, "Nothing aboard yet."
    needs, name = pet["needs"], pet["name"]
    if action == "rename":
        pet["name"] = _clean_name(payload.get("name"), pet["species"])
        return True, ""
    if action == "revive":
        if pet.get("dormant_since") is None:
            return False, f"{name} isn't hibernating."
        medicine = _medicine(pet)
        if not medicine:
            return False, f"Buy medicine for it at a market: {_medicine_names(pet['species'])}."
        _use(pet, medicine)
        pet.update(dormant_since=None, asleep=False, sick=False, revived=int(pet.get("revived") or 0) + 1)
        needs.update(hunger=max(needs["hunger"], 45.0), mood=max(needs["mood"], 40.0), clean=max(needs["clean"], 60.0),
                     health=50.0, energy=max(needs["energy"], 50.0))
        say(pet, now, f"{name} stirred and opened its eyes. It's back.", "good", "revived")
        return True, ""
    if action == "wear":
        outfit = str(payload.get("outfit") or "")
        if outfit and outfit not in pet["outfits"]:
            return False, "It hasn't earned that one yet."
        pet["outfit"] = outfit
        return True, ""
    if action == "welcomed":
        pet["welcome"] = None
        return True, ""
    if action == "release":
        _lose(state, pet, now)
        state["memorial"][-1]["released"] = True
        return True, ""
    if _fed_up(pet):
        return False, "It's still an egg." if pet["stage"] == "egg" else f"{name} is hibernating."
    if action == "lights":
        if pet["asleep"]:
            pet["asleep"] = False
            if needs["energy"] < 60:
                needs["mood"] = _clamp(needs["mood"] - 6)
                say(pet, now, f"Lights on. {name} grumbled awake.", "bad", "grumpy")
            else:
                say(pet, now, f"Lights on. {name} is up.", "", "awake")
            return True, ""
        if needs["energy"] > 75:
            return False, f"{name} isn't tired."
        pet["asleep"] = True
        pet["care"]["naps"] += 1
        say(pet, now, f"Lights off. {name} curled up to sleep.", "", "asleep")
        return True, ""
    if pet["asleep"]:
        return False, f"{name} is asleep. Turn the lights on first."
    if action == "feed":
        item = str(payload.get("item") or "")
        spec = ITEMS.get(item)
        if not spec or pet["larder"].get(item, 0) <= 0:
            return False, "That isn't in the larder."
        if pet["species"] not in spec["for"]:
            return False, f"{name} won't touch {spec['name']}."
        if spec["kind"] == "medicine":
            return act(state, "medicine", {"item": item}, now)
        if needs["hunger"] >= 96 and spec["kind"] != "treat":
            return False, f"{name} is full."
        _use(pet, item)
        needs["hunger"] = _clamp(needs["hunger"] + spec["fill"])
        needs["mood"] = _clamp(needs["mood"] + spec["mood"])
        pet["care"]["treats" if spec["kind"] == "treat" else "meals"] += 1
        pet["foods"][item] = pet["foods"].get(item, 0) + 1
        say(pet, now, f"{name} had the {spec['name']}.", "good", "treat" if spec["kind"] == "treat" else "eat")
        _learn(pet, now)
        _earn(pet, now)
        return True, ""
    if action == "medicine":
        item = str(payload.get("item") or "") or _medicine(pet)
        spec = ITEMS.get(item or "")
        if not spec or spec["kind"] != "medicine" or pet["larder"].get(item, 0) <= 0 or pet["species"] not in spec["for"]:
            return False, f"No medicine for it in the larder: {_medicine_names(pet['species'])}."
        if not pet["sick"] and needs["health"] >= 90:
            return False, f"{name} is well."
        _use(pet, item)
        pet["sick"] = False
        needs["health"] = _clamp(needs["health"] + 35)
        needs["mood"] = _clamp(needs["mood"] + spec["mood"])
        say(pet, now, f"{spec['name']} given. {name} feels better.", "good", "cured")
        return True, ""
    if action == "vent":
        if needs["clean"] >= 95:
            return False, "The hold is clean."
        needs["clean"] = 100.0
        pet["care"]["vents"] += 1
        say(pet, now, "Hold vented. Spotless.", "good", "clean")
        return True, ""
    if action == "play":
        if needs["energy"] < 8:
            return False, f"{name} is too tired to play."
        won = bool(payload.get("won"))
        needs["mood"] = _clamp(needs["mood"] + (18 if won else 9))
        needs["energy"] = _clamp(needs["energy"] - 7)
        needs["hunger"] = _clamp(needs["hunger"] - 3)
        pet["care"]["plays"] += 1
        game_id = str(payload.get("game"))
        if game_id in GAMES:
            pet["games"][game_id] = pet["games"].get(game_id, 0) + 1
            held = pet.get("cue") if isinstance(pet.get("cue"), dict) else {}
            # Share the result animation with both views, while keeping a
            # fresh danger reaction ahead of a game played at the same time.
            if held.get("kind") != "danger" or now - _number(held.get("at")) > 10:
                pet["cue"] = {"kind": f"game_{game_id}", "at": now}
        game = GAMES.get(game_id, "a game")
        say(pet, now, f"Played {game}: {'won!' if won else 'it had fun anyway.'}", "good", "happy" if won else "play")
        _learn(pet, now)
        return True, ""
    if action == "pet":
        # Every touch has a shared visual response; the care boost is limited.
        held = pet.get("cue") if isinstance(pet.get("cue"), dict) else {}
        can_react = held.get("kind") != "danger" or now - _number(held.get("at")) > 10
        if can_react:
            pet["cue"] = {"kind": "petted", "at": now}
        if now - _number(pet.get("petted_at"), 0) < 90:
            return can_react, ""
        pet["petted_at"] = now
        pet["care"]["pats"] += 1
        needs["mood"] = _clamp(needs["mood"] + 3)
        pet["reaction"], pet["reaction_at"] = "petted", now
        _learn(pet, now)
        return True, ""
    return False, "Nothing happened."


def _learn(pet, now):
    """A trick it has picked up from what you do together."""
    for trick, where, key, enough in TRICKS:
        have = (pet.get(where) or {}).get(key, 0)
        if trick not in pet["tricks"] and have >= enough:
            pet["tricks"].append(trick)
            say(pet, now, f"{pet['name']} learned a trick: {trick}!", "good", "excited")
            moment(pet, now, "trick", f"Learned to {trick}.", trick=trick)
            return


def _earn(pet, now):
    """An outfit earned by how you play; it can wear one."""
    earned = False
    for outfit, (label, count, enough) in OUTFITS.items():
        if outfit not in pet["outfits"] and pet["care"].get(count, 0) >= enough:
            pet["outfits"].append(outfit)
            say(pet, now, f"{pet['name']} earned an outfit: the {label}.", "good", "excited")
            moment(pet, now, "outfit", f"Earned the {label}.", outfit=label)
            earned = True
    return earned


def join_trip(state, trip, now):
    """The expedition you're flying (5.6.4): it comes along, or steps off
    when none is. ``trip`` is {id, name, to} or None. True when it changed."""
    pet = state.get("pet")
    if not pet:
        return False
    held = pet.get("trip") if isinstance(pet.get("trip"), dict) else None
    if not trip:
        if held:
            pet["trip"] = None
            return True
        return False
    if held and held.get("id") == trip.get("id"):
        if (held.get("name"), held.get("to")) != (trip.get("name"), trip.get("to")):
            held.update(name=str(trip.get("name") or "")[:80], to=str(trip.get("to") or "")[:80])
            return True
        return False
    pet["trip"] = {"id": str(trip.get("id") or ""), "name": str(trip.get("name") or "the expedition")[:80],
                   "to": str(trip.get("to") or "")[:80], "since": now}
    if pet["stage"] != "egg":
        say(pet, now, f"{pet['name']} is coming along on {pet['trip']['name']}.", "good", "excited")
        moment(pet, now, "trip", f"Set off with you on {pet['trip']['name']}.")
    return True


def finish_trip(state, trip_id, now, completed=True):
    """The expedition ended. Completed with it aboard: a badge, and a party."""
    pet = state.get("pet")
    held = (pet or {}).get("trip") if isinstance((pet or {}).get("trip"), dict) else None
    if not pet or not held or held.get("id") != str(trip_id):
        return None
    pet["trip"] = None
    if not completed:
        return None
    where = held.get("to") or held.get("name")
    badge = {"id": held["id"], "name": held.get("name") or "", "text": f"Travelled with you to {where}", "at": now}
    pet["badges"] = ([row for row in pet.get("badges") or [] if row.get("id") != held["id"]] + [badge])[-40:]
    say(pet, now, f"{pet['name']} made it all the way to {where} with you. A badge for that.", "good", "excited")
    pet["cue"] = {"kind": "tripdone", "at": now}
    moment(pet, now, "badge", f"Finished {held.get('name') or 'the expedition'}: travelled with you to {where}.")
    for row in pet["diary"][-1:]:
        row["trip"] = held["id"]
    return badge


def trip_story(state, trip_id):
    """Its side of an expedition, for the trip's Void Wrapped: its diary of
    it and the badge it earned (None when it wasn't along)."""
    pet = state.get("pet")
    if not pet:
        return None
    lines = [row["text"] for row in pet.get("diary") or () if row.get("trip") == str(trip_id)]
    badge = next((row for row in pet.get("badges") or () if row.get("id") == str(trip_id)), None)
    if not lines and not badge:
        return None
    # "sample_kind", not "kind": the Wrapped card's own kind is "hatchling".
    return {"name": pet["name"], "species": pet["species"], "sample_kind": pet.get("kind") or "", "stage": pet["stage"],
            "form": pet.get("form") or "", "outfit": pet.get("outfit") or "", "lines": lines[-6:], "moments": len(lines),
            "badge": badge["text"] if badge else ""}


def welcome(state, now):
    """Opening Void Compass after time away: what it did meanwhile. Called
    once a session, before its clock catches up. True when it greeted you."""
    pet = state.get("pet")
    if not pet or pet["stage"] == "egg" or pet.get("dormant_since") is not None:
        advance(state, now)
        return False
    away_h = (now - _number(pet.get("last"), now)) / 3600
    before = dict(pet["needs"])
    advance(state, now)
    pet = state.get("pet")
    if not pet or away_h < WELCOME_AFTER_H:
        return False
    day = int(now // 86400)
    lines = [f"You were away {round(away_h)} hours."]
    naps = int(away_h // 7)
    if naps:
        lines.append(f"It napped {naps} time{'s' if naps > 1 else ''}.")
    games = ("It kept a limpet up {n} times in a row.", "It built a canister tower. It fell over.",
             "It chased a mote of light around the pod.", "It joined up stars into a constellation.",
             "It played tag with a Thargon and lost.")
    lines.append(games[day % len(games)].format(n=7 + day % 13))
    if pet["needs"]["hunger"] < before["hunger"] - 20:
        lines.append("It got hungry waiting.")
    if sum(count for item, count in pet["larder"].items() if ITEMS.get(item, {}).get("kind") != "medicine") < 3:
        lines.append("The larder is nearly empty.")
    if pet["toys"]:
        lines.append(f"It played with {pet['toys'][day % len(pet['toys'])]['label']}.")
    lines.append("It missed you.")
    pet["welcome"] = {"at": now, "hours": round(away_h, 1), "lines": lines}
    pet["cue"] = {"kind": "welcome", "at": now}
    say(pet, now, f"{pet['name']} missed you: {round(away_h)} hours away.", "good", "excited")
    moment(pet, now, "welcome", f"Greeted you after {round(away_h)} hours away.", hours=round(away_h))
    return True


def _use(pet, item):
    left = pet["larder"].get(item, 0) - 1
    if left > 0:
        pet["larder"][item] = left
    else:
        pet["larder"].pop(item, None)


def _medicine(pet):
    return next((item for item, count in pet["larder"].items()
                 if count > 0 and ITEMS.get(item, {}).get("kind") == "medicine" and pet["species"] in ITEMS[item]["for"]), "")


def _medicine_names(species):
    return " or ".join(spec["name"] for spec in ITEMS.values() if spec["kind"] == "medicine" and species in spec["for"])


# ---- What you do in the game. -----------------------------------------------------------------

def _mentions(event, *words):
    text = json.dumps(event, ensure_ascii=False).casefold()
    return any(word in text for word in words)


# What it acts out for each live event (5.6.4), and where that leaves you.
CUES = {"StartJump": "jump", "CarrierJump": "jump", "FSDJump": "arrive", "SupercruiseEntry": "cruise", "SupercruiseExit": "drop",
        "Docked": "dock", "Undocked": "undock", "Touchdown": "touchdown", "Liftoff": "liftoff", "FuelScoop": "scoop",
        "HeatWarning": "heat", "UnderAttack": "danger", "Interdicted": "danger", "HullDamage": "danger", "Died": "danger",
        "LaunchSRV": "srv", "DockSRV": "srvback", "Disembark": "leave", "Embark": "welcome",
        "Bounty": "victory", "FactionKillBond": "victory", "MissionCompleted": "mission", "MissionFailed": "sad",
        "MissionAbandoned": "sad", "Promotion": "party", "ShipyardSwap": "newship", "SellExplorationData": "paid",
        "MultiSellExplorationData": "paid", "SellOrganicData": "paid", "EngineerCraft": "upgrade", "RepairAll": "repaired",
        "EscapeInterdiction": "phew", "JetConeBoost": "boost", "Screenshot": "pose", "CommitCrime": "naughty",
        "DockingDenied": "rude", "LaunchFighter": "fighter", "FSSAllBodiesFound": "allfound", "SAAScanComplete": "mapped",
        "ApproachSettlement": "settlement", "FSSDiscoveryScan": "honk", "ScanOrganic": "biology"}
PLACES = {"SupercruiseEntry": "supercruise", "SupercruiseExit": "space", "Docked": "docked", "Undocked": "space",
          "Touchdown": "landed", "Liftoff": "space", "FSDJump": "supercruise", "Died": "space",
          "LaunchSRV": "srv", "DockSRV": "landed", "Disembark": "away"}


def _cue(pet, name, event, now):
    kind = CUES.get(name, "")
    if name == "StartJump" and event.get("JumpType") != "Hyperspace":
        kind = ""
    if name in {"Touchdown", "Liftoff"} and event.get("PlayerControlled") is False:
        kind = ""
    if name == "ShieldState" and event.get("ShieldsUp") is False:
        kind = "danger"
    if (name == "Scan" and event.get("WasDiscovered") is False) or (name == "CodexEntry" and event.get("IsNewEntry")):
        kind = "discovery"
    if name in PLACES:
        pet["place"] = PLACES[name]
    if name == "Embark":
        pet["place"] = "docked" if event.get("OnStation") else "landed" if event.get("OnPlanet") else "space"
    if name == "Disembark" and event.get("SRV"):
        kind = ""
    if name == "Loadout":
        pet["fuel_capacity"] = _number((event.get("FuelCapacity") or {}).get("Main"), pet.get("fuel_capacity") or 0.0)
        pet["ship"] = _ship_name(event.get("ShipName"), event.get("Ship_Localised") or event.get("Ship"))
    if name == "ShipyardSwap":
        pet["ship"] = _ship_name("", event.get("ShipType_Localised") or event.get("ShipType"))
    if name == "SAAScanComplete" and _number(event.get("ProbesUsed"), 99) > _number(event.get("EfficiencyTarget"), 0):
        kind = ""
    if name == "ScanOrganic" and event.get("ScanType") != "Analyse":
        kind = ""
    if name == "RefuelAll" or (name in {"FuelScoop", "RefuelPartial"} and pet.get("fuel_capacity")
                               and _number(event.get("Total")) / pet["fuel_capacity"] > LOW_FUEL):
        pet["low_fuel"] = False
    if name == "FSDJump" and pet.get("fuel_capacity"):
        low = _number(event.get("FuelLevel"), pet["fuel_capacity"]) / pet["fuel_capacity"] < LOW_FUEL
        if low and not pet.get("low_fuel"):
            kind = "lowfuel"
        pet["low_fuel"] = low
    if name == "FSDJump" and event.get("StarSystem"):
        system = str(event["StarSystem"])[:40]
        pet["places"] = ([{"name": system, "at": now}] + [row for row in pet["places"] if row.get("name") != system])[:PLACES_KEEP]
    held = pet.get("cue") if isinstance(pet.get("cue"), dict) else {}
    if kind and held.get("kind") == kind and now - _number(held.get("at")) < 15:
        return False  # Still acting this one out (a honk is dozens of discoveries).
    if kind:
        pet["cue"] = {"kind": kind, "at": now}
    return bool(kind)


def _ship_name(given, kind):
    """Your ship as it would say it: its own name, else its type ("krait_mkii" → "Krait Mkii")."""
    given = str(given or "").strip()
    if given:
        return given[:30]
    kind = str(kind or "")
    if " " in kind and kind != kind.lower():
        return kind[:30]
    words = [part.capitalize() for part in kind.replace("_", " ").split()]
    marks = {"Mkii": "Mk II", "Mkiii": "Mk III", "Mkiv": "Mk IV"}
    return " ".join(marks.get(word, word) for word in words)[:30]


def _toy(pet, now, kind, label):
    """A keepsake from the trip, kept in its pod (one of each kind)."""
    label = str(label)[:48]
    held = next((toy for toy in pet["toys"] if toy.get("kind") == kind), None)
    if held and now - _number(held.get("at")) < 3600:
        return False
    pet["toys"] = ([toy for toy in pet["toys"] if toy.get("kind") != kind] + [{"kind": kind, "label": label, "at": now}])[-TOYS_KEEP:]
    say(pet, now, f"{pet['name']} found a toy: {label}.", "good", "excited")
    moment(pet, now, "toy", f"Found {label}.", toy=label)
    return True


def _toys(pet, name, event, now):
    system = str(event.get("StarSystem") or event.get("SystemName") or "")
    if name == "CodexEntry" and _mentions(event, "guardian", "ancient"):
        return _toy(pet, now, "relic", "a Guardian relic" + (f" from {system}" if system else ""))
    if name in {"FSSSignalDiscovered", "CodexEntry"} and _mentions(event, "thargoid", "nonhuman"):
        return _toy(pet, now, "sensor", "a Thargoid sensor")
    if name == "MiningRefined":
        return _toy(pet, now, "fragment", f"a chunk of {event.get('Type_Localised') or 'ore'}")
    if name == "ScanOrganic" and event.get("ScanType") == "Analyse":
        return _toy(pet, now, "pebble", f"a pebble from beside {event.get('Species_Localised') or 'something alive'}")
    if name == "Scan" and event.get("WasDiscovered") is False and event.get("StarType"):
        return _toy(pet, now, "beacon", f"a beacon from {event.get('BodyName') or 'a new star'}")
    if name == "Docked" and str(event.get("MarketID") or event.get("StationName") or "") not in pet["stations"]:
        return _toy(pet, now, "model", f"a model of {event.get('StationName') or 'a station'}")
    return False


def observe(state, event, now):
    """One live journal event. Returns True when the pet noticed."""
    pet = state.get("pet")
    if not pet or not isinstance(event, dict):
        return False
    advance(state, now)
    if not state.get("pet"):
        return True
    name = str(event.get("event") or "")
    needs, care, who = pet["needs"], pet["care"], pet["name"]
    species = pet["species"]

    if name == "MarketBuy":
        item = str(event.get("Type") or "").casefold()
        spec = ITEMS.get(item)
        if not spec or species not in spec["for"]:
            return False
        count = max(1, int(_number(event.get("Count"), 1)))
        pet["larder"][item] = min(LARDER_MOST, pet["larder"].get(item, 0) + count)
        say(pet, now, f"{spec['name']} into the larder ({pet['larder'][item]}).", "good")
        return True
    if _fed_up(pet):
        return False
    asleep = pet["asleep"]
    cued = _cue(pet, name, event, now)
    toyed = _toys(pet, name, event, now)
    noticed = _observe_mood(pet, name, event, now, needs, care, who, species, asleep)
    if noticed and name in {"ShieldState", "HullDamage", "Died"}:
        moment(pet, now, "scared", "Hid under the console when the ship was hit.")
    if name == "MiningRefined":
        care["mined"] += 1
    if isinstance(event.get("_world"), dict) and name in {"Touchdown", "ApproachBody", "LaunchSRV", "Disembark"}:
        world = event["_world"]
        pet["world"] = {"body": str(world.get("body") or "")[:60], "gravity": _number(world.get("gravity"), 1.0),
                        "temp": _number(world.get("temp"), 0.0)}
    if name in {"LeaveBody", "FSDJump"}:
        pet["world"] = None
    earned = _earn(pet, now)
    return noticed or cued or toyed or earned


def _observe_mood(pet, name, event, now, needs, care, who, species, asleep):
    def mood(change, text, tone="", reaction=""):
        needs["mood"] = _clamp(needs["mood"] + change)
        say(pet, now, text, tone or ("good" if change > 0 else "bad"), reaction)
        return True

    if name == "FSDJump":
        care["explored"] += 1
        # You arrive in supercruise: the clock on a long one starts here.
        pet["supercruise_since"] = now
    if name in {"FSSSignalDiscovered", "CodexEntry", "ApproachSettlement", "SupercruiseDestinationDrop", "FSDJump"}:
        thargoid = _mentions(event, "thargoid", "nonhuman", "\"thargoidwar\"")
        guardian = _mentions(event, "guardian", "ancient")
        if thargoid and not (name == "FSDJump" and not event.get("ThargoidWar")):
            care["thargoid"] += 1
            if species in {"larva", "thargoid"}:
                return mood(10, f"Thargoid signals. {who} is glowing and humming.", "good", "excited")
            return mood(-4, f"Something Thargoid out there. {who} has gone quiet.", "bad", "scared")
        if guardian and name != "FSDJump":
            care["guardian"] += 1
            if species in {"larva", "thargoid"}:
                return mood(-10, f"Guardian things. {who} hates them.", "bad", "angry")
            if species == "bot":
                return mood(4, f"Guardian tech: {who}'s sensors whirr.", "good", "curious")
    if name == "FSDJump":
        if asleep:
            return True
        return mood(2, "A new star outside. Curious.", "good", "curious")
    if name == "Scan" and event.get("WasDiscovered") is False and event.get("ScanType") in {"Detailed", "AutoScan", "Basic"}:
        care["discoveries"] += 1
        return mood(3, f"First to find {event.get('BodyName') or 'it'}!", "good", "happy")
    if name == "CodexEntry" and event.get("IsNewEntry"):
        care["codex"] += 1
        return mood(9, f"A new codex entry: {event.get('Name_Localised') or 'something new'}.", "good", "amazed")
    if name == "ScanOrganic" and species == "sample":
        return mood(6, f"{who} sensed a cousin out there.", "good", "happy")
    if name == "ShieldState" and event.get("ShieldsUp") is False:
        care["scares"] += 1
        return mood(-8, f"Shields down! {who} hid under the console.", "bad", "scared")
    if name == "HullDamage" and event.get("PlayerPilot", True) and not event.get("Fighter"):
        care["scares"] += 1
        needs["health"] = _clamp(needs["health"] - 2)
        return mood(-5, f"The hull shook. {who} is frightened.", "bad", "scared")
    if name == "Died":
        return mood(-22, f"The ship was lost. {who} made it to the escape pod.", "bad", "distraught")
    if name == "Resurrect" and str(event.get("Option") or "").casefold() == "rebuy":
        care["rebuys"] += 1
        return mood(-25, f"A rebuy. {who} is very upset.", "bad", "distraught")
    if name == "Docked":
        pet["supercruise_since"] = None
        market = str(event.get("MarketID") or event.get("StationName") or "")
        if market and market not in pet["stations"]:
            pet["stations"] = (pet["stations"] + [market])[-400:]
            care["stations"] += 1
            return mood(6, f"Somewhere new: {event.get('StationName') or 'a station'}. A little treat.", "good", "happy")
        return False
    if name == "SupercruiseEntry":
        pet["supercruise_since"] = now
        return False
    if name == "SupercruiseExit" and pet.get("supercruise_since"):
        minutes = (now - pet["supercruise_since"]) / 60
        pet["supercruise_since"] = None
        if minutes > 5 and not asleep:
            return mood(-min(10, round((minutes - 5) / 2)), f"{round(minutes)} minutes of supercruise. {who} is bored.", "bad", "bored")
        return False
    if name in {"Bounty", "FactionKillBond"}:
        care["fights"] += 1
        if _mentions(event, "thargoid") and species in {"larva", "thargoid"}:
            return mood(-8, f"A Thargoid fell. {who} went very quiet.", "bad", "distraught")
        return mood(3, f"Got them. {who} cheered.", "good", "excited")
    if name == "MissionCompleted":
        care["missions"] += 1
        return mood(5, f"Mission done: {event.get('LocalisedName') or event.get('Name') or 'a job'}. {who} is proud.", "good", "happy")
    if name in {"MissionFailed", "MissionAbandoned"}:
        return mood(-4, f"A mission lost. {who} is sorry.", "bad", "")
    if name == "Promotion":
        care["ranks"] += 1
        return mood(10, f"Promoted! {who} is so proud of you.", "good", "excited")
    if name == "ShipyardSwap":
        return mood(5, f"A different ship. {who} is sniffing every corner.", "good", "curious")
    if name in {"SellExplorationData", "MultiSellExplorationData", "SellOrganicData"}:
        return mood(3, f"Paid for what we found. {who} likes credits.", "good", "happy")
    if name == "EngineerCraft":
        return mood(8 if species == "bot" else 2, f"Upgrades! {who} {'whirrs with joy' if species == 'bot' else 'watched closely'}.", "good", "excited")
    if name == "RepairAll":
        needs["health"] = _clamp(needs["health"] + 3)
        return mood(2, f"The ship's mended. {who} feels safer.", "good", "")
    if name == "EscapeInterdiction":
        return mood(4, f"Got away! {who} cheered.", "good", "excited")
    if name == "Screenshot":
        return mood(1, f"{who} posed for the picture.", "good", "happy")
    if name == "CommitCrime":
        return mood(-2, f"{who} saw that.", "bad", "")
    if name == "FSSAllBodiesFound":
        care["discoveries"] += 1
        return mood(4, f"Every world in the system found. {who} is delighted.", "good", "happy")
    if name == "CarrierJump":
        if asleep:
            needs["energy"] = _clamp(needs["energy"] + 10)
            say(pet, now, f"{who} slept right through the carrier jump.", "good")
            return True
        return mood(-5, f"The carrier jump startled {who}.", "bad", "scared")
    return False


# ---- What the Games page and the overlay are shown. ---------------------------------------------

def _mood_word(pet):
    needs = pet["needs"]
    if pet.get("dormant_since") is not None:
        return "HIBERNATING"
    if pet["stage"] == "egg":
        return "INCUBATING"
    if pet["asleep"]:
        return "ASLEEP"
    if pet["sick"]:
        return "ILL"
    mood = needs["mood"]
    return "HAPPY" if mood > 80 else "CONTENT" if mood > 55 else "RESTLESS" if mood > 30 else "SAD" if mood > 10 else "MISERABLE"


def _wants(pet):
    needs = pet["needs"]
    if pet.get("dormant_since") is not None:
        return "REVIVE IT"
    if pet["stage"] == "egg" or pet["asleep"]:
        return ""
    if pet["sick"]:
        return "MEDICINE"
    order = (("hunger", 35, "FOOD" if pet["species"] != "bot" else "POWER"), ("clean", 35, "A CLEAN HOLD"),
             ("mood", 35, "PLAY"), ("energy", 20, "SLEEP"))
    low = sorted((needs[need], word) for need, limit, word in order if needs[need] < limit)
    return low[0][1] if low else ""


def view(state, now):
    """The pet as the game page and the overlay see it."""
    advance(state, now)
    pet = state.get("pet")
    memorial = [{"name": item.get("name"), "species": item.get("species"),
                 "form": SPECIES.get(item.get("species"), SPECIES["larva"])["forms"].get(item.get("form") or "", ""),
                 "lost": item.get("lost"), "released": bool(item.get("released"))} for item in state.get("memorial") or ()][-8:]
    collection = []
    for key in state.get("forms_seen") or ():
        species, _, form = key.partition(":")
        if species in SPECIES and form in SPECIES[species]["forms"]:
            collection.append({"species": species, "form": form, "label": SPECIES[species]["forms"][form]})
    base = {"pet": None, "memorial": memorial, "collection": collection,
            "species": {key: {"name": spec["name"], "blurb": spec["blurb"], "names": list(spec["names"])}
                        for key, spec in SPECIES.items()},
            "kinds": SAMPLE_KINDS, "notice": state.get("notice")}
    if not pet:
        return base
    species = SPECIES[pet["species"]]
    larder = sorted(({"id": item, "name": ITEMS[item]["name"], "kind": ITEMS[item]["kind"], "count": count}
                     for item, count in pet["larder"].items() if item in ITEMS and count > 0),
                    key=lambda row: (("snack", "meal", "treat", "medicine").index(row["kind"]), row["name"]))
    dormant = pet.get("dormant_since")
    hatch_at = pet["born"] + STAGES[0][1] * 3600
    base["pet"] = {
        "name": pet["name"], "species": pet["species"], "species_name": species["name"], "kind": pet.get("kind") or "",
        "kind_name": SAMPLE_KINDS.get(pet.get("kind") or "", ""), "stage": pet["stage"],
        "stage_name": species.get("stages", {}).get(pet["stage"], pet["stage"].title()),
        "form": pet.get("form") or "", "form_name": species["forms"].get(pet.get("form") or "", ""),
        "born": pet["born"], "age_hours": round((now - pet["born"]) / 3600, 1),
        "needs": {need: int(round(pet["needs"][need])) for need in NEEDS},
        "food_label": species["food"], "asleep": bool(pet["asleep"]), "sick": bool(pet["sick"]),
        "dormant": dormant is not None,
        "dormant_hours_left": round(max(0.0, HIBERNATE_DAYS * 24 - (now - dormant) / 3600), 1) if dormant is not None else None,
        "hatch_minutes": max(0, round((hatch_at - now) / 60)) if pet["stage"] == "egg" else 0,
        "mood_word": _mood_word(pet), "wants": _wants(pet),
        "mess": 0 if pet["stage"] == "egg" else min(4, int((100 - pet["needs"]["clean"]) // 20)),
        "larder": larder, "medicine": _medicine_names(pet["species"]),
        "stores_hours": round(max(0.0, STORES_EVERY_H - (now - _number(pet.get("stores_at"), now)) / 3600), 1),
        "log": [{"at": row.get("at"), "text": row.get("text"), "tone": row.get("tone")} for row in pet.get("log") or ()][:8],
        "reaction": pet.get("reaction") or "", "reaction_at": pet.get("reaction_at") or 0,
        "care": {key: int(value) for key, value in pet["care"].items()},
        **_character(pet, now),
    }
    return base


def _character(pet, now):
    """Who it has become (5.6.4): personality, favourites, toys, tricks and
    dreams, and what's happening right now for the page to act out."""
    scores = {trait: round(min(3.0, score(pet["care"])), 2) for trait, score in TRAITS.items()}
    best = max(scores, key=scores.get)
    foods = {item: count for item, count in (pet.get("foods") or {}).items() if item in ITEMS}
    games = {game: count for game, count in (pet.get("games") or {}).items() if game in GAMES}
    cue = pet.get("cue") if isinstance(pet.get("cue"), dict) and now - _number(pet["cue"].get("at")) < CUE_S else None
    return {
        "trait": best if scores[best] >= 1 else "", "traits": scores,
        "favourite_food": ITEMS[max(foods, key=foods.get)]["name"] if foods else "",
        "favourite_game": GAMES[max(games, key=games.get)] if games else "",
        "toys": [{"kind": toy.get("kind"), "label": toy.get("label")} for toy in pet.get("toys") or ()],
        "tricks": list(pet.get("tricks") or ()),
        "dreams": [row["name"] for row in pet.get("places") or () if now - _number(row.get("at")) < 36 * 3600][:5],
        "cue": {"kind": cue.get("kind"), "at": cue.get("at")} if cue else None,
        "place": pet.get("place") or "space", "low_fuel": bool(pet.get("low_fuel")),
        "world": dict(pet["world"]) if isinstance(pet.get("world"), dict) and pet.get("place") in {"landed", "srv", "away"} else None,
        "welcome": dict(pet["welcome"]) if isinstance(pet.get("welcome"), dict)
        and now - _number(pet["welcome"].get("at")) < WELCOME_SHOWN_S else None,
        "outfit": pet.get("outfit") or "", "ship": pet.get("ship") or "",
        "trip": {"name": pet["trip"].get("name"), "to": pet["trip"].get("to")} if isinstance(pet.get("trip"), dict) else None,
        "badges": [{"text": row.get("text"), "name": row.get("name")} for row in pet.get("badges") or ()][-12:],
        # Its few words (5.6.4), while they're on screen.
        "chat": hatchling_chatter.shown(pet, now),
        "outfits": [{"id": outfit, "label": label, "earned": outfit in (pet.get("outfits") or ()),
                     "how": f"{pet['care'].get(count, 0)} / {enough} {count}"} for outfit, (label, count, enough) in OUTFITS.items()],
    }


def diary(state, start, end):
    """Its diary lines between two moments (a Captain's Log session)."""
    pet = state.get("pet")
    if not pet:
        return []
    return [row["text"] for row in pet.get("diary") or () if start <= _number(row.get("at")) <= end][-6:]


def snapshot(state):
    return copy.deepcopy(state)
