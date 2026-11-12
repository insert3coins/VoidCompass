"""Where each species can live, by Starling's rules (5.7.8).

data/bio_rules.json is Starling's reduced copy of the EDEXO project's species
data (https://github.com/bahuckel/EDEXO, CC BY-NC-SA 3.0), adjusted by
Starling's author (Daddyg88) with real play data, and used here with his
permission. It stays under that licence. ``fits`` follows Starling's own
matching (journal/bio_predict.py). Scored on our own journals it listed every
species really analysed, where the older rules missed a fifth of them, so
it decides what could be there and the older rules say what's likeliest
(bio_values.predict_genera).
"""

from __future__ import annotations

import json
import re

_RULES = None


def norm(text):
    """'Carbon dioxide-rich' -> 'carbondioxiderich', 'Rocky body' -> 'rocky'."""
    text = re.sub(r"\bbody\b", "", str(text or "").lower())
    return re.sub(r"[^a-z]", "", text)


def rules():
    global _RULES
    if _RULES is None:
        from voidcompass.core.paths import resource_path
        try:
            with open(resource_path("data", "bio_rules.json"), encoding="utf-8") as handle:
                data = json.load(handle)
            _RULES = [rule for rule in data.get("species") or () if isinstance(rule, dict) and rule.get("n")]
        except (OSError, ValueError):
            _RULES = []
    return _RULES


def star_letter(star_type):
    """A star as Starling keys it: its first letter; Herbig Ae/Be as 'h'."""
    star = str(star_type or "").lower()
    return "h" if star.startswith("ae") else star[:1]


def fits(rule, body, stars=(), geo=False):
    """Can this species live on ``body``? body: pc, atm, thin, g, k, volc, ls."""
    if rule.get("p") and body["pc"] not in rule["p"]:
        return False
    atmos = rule.get("a")
    if atmos is not None and body["atm"] not in atmos:
        return False
    if rule.get("thin") and not body["thin"]:
        return False
    if atmos and "none" in atmos and body["atm"] != "none" and not body["thin"]:
        return False
    if "gmax" in rule and body["g"] is not None and body["g"] > rule["gmax"] + 0.0005:
        return False
    k = body["k"]
    if k is not None:
        if "tmin" in rule and k < rule["tmin"]:
            return False
        if "tmax" in rule and k > rule["tmax"]:
            return False
        link = rule.get("lk")
        if link and body["atm"] in link["a"]:
            if link.get("tmin") is not None and k < link["tmin"]:
                return False
            if link.get("tmax") is not None and k > link["tmax"]:
                return False
    if rule.get("v") and not any(word in body["volc"] for word in rule["v"]):
        return False
    if rule.get("vreq") and not body["volc"]:
        return False
    if rule.get("geo") and not geo:
        return False
    stars = set(stars or ())
    if rule.get("stars") and stars and not (set(rule["stars"]) & stars):
        return False
    if rule.get("lsmin") and isinstance(body.get("ls"), (int, float)) and body["ls"] < rule["lsmin"]:
        return False
    return True


def candidates(planet_class, atmosphere, temp_k, gravity_g, volcanism, *, thin=None, distance_ls=None,
               system_stars=(), geo=False):
    """The species whose rules fit: [{"name", "genus"}]. ``thin`` defaults to
    "has an atmosphere" (a landable world's atmosphere is always thin)."""
    atm = norm(atmosphere) or "none"
    if atm.endswith("atmosphere"):
        atm = atm[:-len("atmosphere")]
    atm = re.sub(r"^(thin|thick|hot)", "", atm) or "none"
    body = {"pc": norm(planet_class), "atm": atm,
            "thin": bool(thin) if thin is not None else atm != "none",
            "g": gravity_g if isinstance(gravity_g, (int, float)) else None,
            "k": temp_k if isinstance(temp_k, (int, float)) else None,
            "volc": str(volcanism or "").lower(), "ls": distance_ls}
    letters = {star_letter(star) for star in system_stars or () if star}
    return [{"name": rule["n"], "genus": rule.get("g") or ""} for rule in rules()
            if fits(rule, body, letters, bool(geo))]
