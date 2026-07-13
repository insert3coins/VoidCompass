"""Biological catalogue derived from the packaged SrvSurvey Codex reference.

``codexRef.json`` is the same reference consumed by SrvSurvey.  This module
turns its flat Codex entries into the small genus/species/variant view needed
by the native survey HUD without introducing a runtime dependency on the
SrvSurvey checkout.
"""

from functools import lru_cache
import json
import os
import sys


def _resource_path(filename):
    roots = [
        getattr(sys, "_MEIPASS", None),
        os.path.dirname(os.path.abspath(__file__)),
        os.getcwd(),
    ]
    for root in roots:
        if root:
            path = os.path.join(root, filename)
            if os.path.isfile(path):
                return path
    return os.path.join(os.getcwd(), filename)


def _split_biology_name(entry):
    english = str(entry.get("english_name") or "").strip()
    platform = str(entry.get("platform") or "").lower()
    if platform == "odyssey" and entry.get("hud_category") == "Biology":
        species, separator, variant = english.partition(" - ")
        words = species.split()
        genus = words[0] if words else species
        return genus, species, variant if separator else ""

    # Legacy entries use the Codex subclass as their biological family.
    genus = str(entry.get("sub_class") or english).strip()
    aliases = {
        "Anemone": "Luteolum Anemone",
        "Mounds": "Bark Mounds",
        "Plant": "Amphora Plant",
        "Shards": "Crystalline Shards",
    }
    return aliases.get(genus, genus), english, ""


@lru_cache(maxsize=1)
def catalogue():
    """Return genus and species indexes built from the packaged Codex data."""
    try:
        with open(_resource_path("codexRef.json"), "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError, TypeError):
        return {"genera": {}, "species": {}, "entry_count": 0}

    genera = {}
    species_index = {}
    entry_count = 0
    for entry in raw.values():
        reward = int(entry.get("reward") or 0)
        if not (reward > 0 or entry.get("hud_category") == "Biology"):
            continue
        genus_name, species_name, variant_name = _split_biology_name(entry)
        if not genus_name or not species_name:
            continue
        entry_count += 1
        genus = genera.setdefault(genus_name, {
            "name": genus_name,
            "odyssey": str(entry.get("platform") or "").lower() == "odyssey",
            "species": {},
            "min_value": None,
            "max_value": None,
        })
        species = genus["species"].setdefault(species_name, {
            "name": species_name,
            "value": reward,
            "variants": [],
        })
        if reward:
            species["value"] = reward
            genus["min_value"] = reward if genus["min_value"] is None else min(genus["min_value"], reward)
            genus["max_value"] = reward if genus["max_value"] is None else max(genus["max_value"], reward)
        if variant_name and variant_name not in species["variants"]:
            species["variants"].append(variant_name)
        species_index[species_name.casefold()] = species

    for genus in genera.values():
        genus["species"] = sorted(genus["species"].values(), key=lambda row: row["name"])
        for species in genus["species"]:
            species["variants"].sort()
    return {"genera": genera, "species": species_index, "entry_count": entry_count}


def species_info(name):
    if not name:
        return None
    return catalogue()["species"].get(str(name).strip().casefold())


def genus_info(name):
    if not name:
        return None
    wanted = str(name).strip().casefold()
    for genus_name, info in catalogue()["genera"].items():
        if genus_name.casefold() == wanted:
            return info
    return None

