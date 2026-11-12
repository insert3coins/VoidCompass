"""Nearby (5.7.8): every known system round a centre, one row each, for
Explore & Survey's OVERVIEW. Pure: the deck hands in Spansh's search rows,
the dumps it has fetched, its own scans and visits.

Modelled on ED-Outrider's Nearby (github.com/weslocke/ED-Outrider, GPLv3):
the status pills, the pre-Odyssey mark (Spansh data older than
2022-11-29 never reported biology), the body counts and the notable pills.
If the galaxy map shows a system that isn't on the list, nobody with an
uploader has been there.
"""

from __future__ import annotations

import math
import re

from voidcompass.exploration import bio_values

# Odyssey's live split: body data reported before it came from clients that
# marked thin-atmosphere worlds not landable and reported no biology.
LEGACY_CUTOFF = "2022-11-29"
RADII = (20, 25, 30, 40, 50)
DEFAULT_RADIUS = 25
SCOOPABLE = frozenset("KGBFOAM")

# Spansh's and the journal's names for the same kinds of world.
_KINDS = (
    ("elw", ("earth-like world", "earthlike body")),
    ("ww", ("water world",)),
    ("aw", ("ammonia world",)),
    ("wg", ("water giant",)),
    ("ggw", ("gas giant with water", "water-based life", "water based life")),
    ("gga", ("gas giant with ammonia", "ammonia-based life", "ammonia based life")),
    ("hgg", ("helium",)),
    ("gg", ("gas giant",)),
    ("hmc", ("high metal content",)),
    ("mr", ("metal rich", "metal-rich")),
    ("rockyice", ("rocky ice", "rocky-ice")),
    ("icy", ("icy body",)),
    ("rocky", ("rocky body",)),
)
KIND_LABELS = {
    "elw": "Earth-like world", "ww": "Water world", "aw": "Ammonia world", "wg": "Water giant",
    "ggw": "Gas giant, water life", "gga": "Gas giant, ammonia life", "hgg": "Helium gas giant", "gg": "Gas giant",
    "hmc": "High metal content", "mr": "Metal-rich body", "rockyice": "Rocky ice", "icy": "Icy body", "rocky": "Rocky body",
}
KIND_SHORT = {"elw": "ELW", "ww": "WW", "aw": "AW", "wg": "WG", "ggw": "GG·W", "gga": "GG·A", "hgg": "HeGG", "gg": "GG",
              "hmc": "HMC", "mr": "MR", "rockyice": "RI", "icy": "Icy", "rocky": "Rocky"}
NOTABLE_KINDS = ("elw", "ww", "aw")
# The Codex's genus codes ($Codex_Ent_Bacterial_Genus_Name;) as our genus names.
GENUS_CODES = {
    "Aleoids": "Aleoida", "Bacterial": "Bacterium", "Cactoid": "Cactoida", "Clypeus": "Clypeus", "Conchas": "Concha",
    "Electricae": "Electricae", "Fonticulus": "Fonticulua", "Shrubs": "Frutexa", "Fumerolas": "Fumerola",
    "Fungoids": "Fungoida", "Osseus": "Osseus", "Recepta": "Recepta", "Stratum": "Stratum", "Tubus": "Tubus",
    "Tussocks": "Tussock", "Brancae": "Brain Tree", "Ground_Struct_Ice": "Crystalline Shards", "Sphere": "Anemone",
    "Tube": "Sinuous Tubers", "Vents": "Amphora Plant", "Cone": "Bark Mounds",
}


def planet_kind(subtype):
    text = str(subtype or "").casefold()
    for kind, words in _KINDS:
        if any(word in text for word in words):
            if kind == "gg":
                match = re.search(r"class\s*(v|iv|iii|ii|i)\b", text)
                return f"gg{('i', 'ii', 'iii', 'iv', 'v').index(match.group(1)) + 1}" if match else "gg"
            return kind
    return ""


def star_class(subtype):
    """A star's class as Outrider shows it: K, M, DA, N, BH, W, TTS, Ae/Be..."""
    text = str(subtype or "").strip()
    low = text.casefold()
    if not text:
        return ""
    if "black hole" in low:
        return "BH"
    if "neutron" in low:
        return "N"
    if "white dwarf" in low:
        match = re.search(r"\((D[A-Z]*)\)", text)
        return match.group(1) if match else "D"
    if "wolf-rayet" in low:
        rest = low.replace("wolf-rayet", "").replace("star", "").strip().upper()
        return f"W{rest}" if rest else "W"
    if "t tauri" in low:
        return "TTS"
    if "herbig" in low:
        return "Ae/Be"
    if low.startswith("ms"):
        return "MS"
    if low.startswith("cn"):
        return "CN"
    if low.startswith("cj"):
        return "CJ"
    match = re.match(r"^([A-Z])\b", text)
    if match:
        return match.group(1)
    # The journal's own codes ("K", "M_RedGiant", "DA", "H", "N").
    code = text.split("_")[0]
    return {"H": "BH", "SupermassiveBlackHole": "BH"}.get(code, code[:4])


def scoopable(subtype):
    cls = star_class(subtype)
    return cls in SCOOPABLE


def is_giant_star(subtype):
    return "giant" in str(subtype or "").casefold()


def pre_odyssey(updated):
    """Spansh's newest report of a system, when it predates Odyssey: "fully
    scanned" may still hide biology and first footfalls."""
    day = str(updated or "")[:10]
    return day if day and day < LEGACY_CUTOFF else None


def jumps_for(distance, jump_range):
    try:
        distance, jump_range = float(distance), float(jump_range)
    except (TypeError, ValueError):
        return None
    if jump_range <= 0:
        return None
    return max(1, math.ceil(distance / jump_range - 1e-9))


def distance_between(a, b):
    try:
        return math.dist([float(v) for v in a[:3]], [float(v) for v in b[:3]])
    except (TypeError, ValueError, IndexError):
        return None


def _bio_up_to(body, region_id=None, coords=None):
    """What a body's biology could pay at most, from the genera it's known to
    have, or the likeliest ones for its signals."""
    count = int(body.get("bio") or 0)
    if count <= 0:
        return 0
    genera = [g for g in body.get("genera") or () if g]
    values = []
    if genera:
        for genus in genera:
            info = bio_values.genus_info(genus)
            values.append(int(info.get("max_value") or 0))
    else:
        try:
            predicted = bio_values.predict_genera(
                body.get("subtype"), body.get("atmosphere"), body.get("temperature"), body.get("gravity"),
                body.get("volcanism"), body.get("pressure"), region_id, coords,
            )
        except Exception:
            predicted = []
        for row in bio_values.likely_genera(predicted):
            species = [int(entry.get("value") or 0) for entry in row.get("species") or () if isinstance(entry, dict)]
            values.append(max(species) if species else int(row.get("max_value") or 0))
    values.sort(reverse=True)
    return sum(values[:count])


def _terraformable(state):
    text = str(state or "").strip().casefold()
    return bool(text) and "terraform" in text and not text.startswith("not")


def dump_bodies(system):
    """A Spansh dump's bodies as plain records (name short, as Outrider keeps them)."""
    name = str((system or {}).get("name") or "")
    out = []
    for body in (system or {}).get("bodies") or ():
        if not isinstance(body, dict):
            continue
        full = str(body.get("name") or "")
        short = full[len(name):].strip() if name and full.casefold().startswith(name.casefold()) else full
        signals = (body.get("signals") or {}).get("signals") or {}
        genera = []
        for genus in (body.get("signals") or {}).get("genuses") or ():
            label = genus.get("name") if isinstance(genus, dict) else genus
            label = str(label or "")
            match = re.search(r"Codex_Ent_([A-Za-z_]+?)_Genus", label)
            if match:
                label = GENUS_CODES.get(match.group(1), match.group(1))
            if label:
                genera.append(label)
        rings = [{"name": str(ring.get("name") or ""), "type": str(ring.get("type") or ""),
                  "hotspots": {str(k): int(v) for k, v in ((ring.get("signals") or {}).get("signals") or {}).items()
                               if isinstance(v, (int, float))},
                  "mapped": "signals" in ring}
                 for ring in body.get("rings") or () if isinstance(ring, dict)]
        out.append({
            "name": short or full, "full_name": full, "body_id": body.get("bodyId"),
            "type": body.get("type"), "subtype": body.get("subType"),
            "main": bool(body.get("mainStar")), "landable": bool(body.get("isLandable")),
            "terraformable": _terraformable(body.get("terraformingState")),
            "dist_ls": body.get("distanceToArrival"), "gravity": body.get("gravity"),
            "temperature": body.get("surfaceTemperature"), "pressure": body.get("surfacePressure"),
            "atmosphere": body.get("atmosphereType"), "volcanism": body.get("volcanismType"),
            "radius_km": body.get("radius"), "mass": body.get("earthMasses") or body.get("solarMasses"),
            "rings": rings, "belts": [str(b.get("type") or "") for b in body.get("belts") or () if isinstance(b, dict)],
            "bio": int(signals.get("$SAA_SignalType_Biological;") or 0),
            "geo": int(signals.get("$SAA_SignalType_Geological;") or 0),
            "genera": genera, "updated": body.get("updateTime"), "signals_known": "signals" in body,
            "parents": body.get("parents") or [], "sma_au": body.get("semiMajorAxis"),
            "luminosity": body.get("luminosity"), "spectral": body.get("spectralClass"),
            "reserve": body.get("reserveLevel"),
        })
    return out


def search_bodies(row):
    """A Spansh search row's bodies: what search gives (no signals or landability)."""
    name = str((row or {}).get("name") or "")
    out = []
    for body in (row or {}).get("bodies") or ():
        if not isinstance(body, dict):
            continue
        full = str(body.get("name") or "")
        short = full[len(name):].strip() if name and full.casefold().startswith(name.casefold()) else full
        out.append({"name": short or full, "full_name": full, "type": body.get("type"), "subtype": body.get("subtype"),
                    "main": bool(body.get("is_main_star")), "dist_ls": body.get("distance_to_arrival"),
                    "terraformable": _terraformable(body.get("terraforming_state")),
                    "value": body.get("estimated_mapping_value"), "scan_value": body.get("estimated_scan_value")})
    return out


def own_bodies(items):
    """Your own scans of a system (the deck's scan items) as the same plain records."""
    out = []
    for item in items or ():
        if not isinstance(item, dict):
            continue
        star = bool(item.get("is_star") or item.get("star_type"))
        reward = int(item.get("reward") or 0)
        mapped = bool(item.get("dss_complete"))
        rings = [ring for ring in item.get("rings") or () if isinstance(ring, dict)]
        out.append({
            "name": str(item.get("name") or ""), "full_name": str(item.get("full_name") or item.get("name") or ""),
            "body_id": item.get("body_id"), "type": "Star" if star else "Planet",
            "subtype": item.get("star_type") if star else item.get("planet_class"),
            "main": star and not item.get("distance_to_arrival"),
            "landable": bool(item.get("landable")), "terraformable": bool(item.get("terraformable")),
            "dist_ls": item.get("distance_to_arrival"), "gravity": item.get("gravity_g"),
            "temperature": item.get("surface_temp"), "atmosphere": item.get("atmosphere_type") or item.get("atmosphere"),
            "volcanism": item.get("volcanism"), "pressure": (float(item["surface_pressure"]) / 101325.0
                                                             if isinstance(item.get("surface_pressure"), (int, float)) else None),
            "rings": [{"name": str(r.get("Name") or ""), "type": str(r.get("RingClass") or ""), "hotspots": {}, "mapped": False}
                      for r in rings if "belt" not in str(r.get("Name") or "").casefold()],
            "bio": int(item.get("bio_count") or 0), "geo": int(item.get("geo_count") or 0),
            "genera": [str(g.get("Genus_Localised") or g.get("Genus") or "") if isinstance(g, dict) else str(g)
                       for g in item.get("genuses") or ()],
            "own": True, "mapped": mapped, "was_discovered": item.get("was_discovered"),
            "was_mapped": item.get("was_mapped"), "first_footfall": bool(item.get("first_footfall")),
            "value_now": int(item.get("dss_reward") or 0) if mapped else reward,
            "value": int(item.get("dss_reward") or reward or 0) or reward,
        })
    return out


def merge(spansh, own):
    """Spansh's records with yours laid over them (yours win: they're newer and exact)."""
    merged = {str(r.get("name") or "").casefold(): dict(r) for r in spansh or () if r.get("name")}
    for record in own or ():
        key = str(record.get("name") or "").casefold()
        base = merged.get(key) or {}
        keep = {k: v for k, v in base.items() if v not in (None, "", [], {})}
        merged[key] = {**keep, **{k: v for k, v in record.items() if v not in (None, "", [], {}) or k in ("landable", "mapped")}}
        if base.get("value") and not record.get("value"):
            merged[key]["value"] = base["value"]
    return list(merged.values())


def codex_new(records, codex, region_id):
    """Body types here not yet in your Codex: ("new" anywhere or "region"), with what they are."""
    if codex is None or not hasattr(codex, "type_state"):
        return []
    from voidcompass.outrider import codex_bodies
    out, seen = [], set()
    for record in records:
        entry = codex_bodies.entry_for({**record, "type": record.get("type")})
        if entry is None or entry in seen:
            continue
        seen.add(entry)
        state = codex.type_state(entry, region_id)
        if state:
            out.append({"state": state, "name": codex_bodies.NAMES.get(entry, str(entry)), "body": record.get("name")})
    return out


def summarise(row, records, body_count=None, *, visited=False, visits=0, bookmarked=False, first_found=False,
              footfall=False, jump_range=None, region_id=None, has_dump=False, own_count=0, codex=None):
    """One Nearby row from a system's merged records."""
    stars = [r for r in records if str(r.get("type") or "").casefold() == "star"]
    planets = [r for r in records if str(r.get("type") or "").casefold() == "planet"]
    main = next((r for r in stars if r.get("main")), stars[0] if len(stars) == 1 else None)
    kinds = [planet_kind(r.get("subtype")) for r in planets]
    known = len(stars) + len(planets)
    if body_count is None:
        body_count = (row or {}).get("body_count")
    try:
        body_count = int(body_count) if body_count is not None else None
    except (TypeError, ValueError):
        body_count = None
    coords = [row.get("x"), row.get("y"), row.get("z")] if row and row.get("x") is not None else None
    bio_max = sum(_bio_up_to(r, region_id, coords) for r in planets)
    value_max = sum(int(r.get("value") or 0) for r in records) + bio_max
    value_now = sum(int(r.get("value_now") or 0) for r in records if r.get("own"))
    if not known:
        status = "none"
    elif body_count and known >= body_count:
        status = "full"
    else:
        status = "partial"
    updated = (row or {}).get("updated_at")
    unusual = []
    for r in stars:
        cls = star_class(r.get("subtype"))
        if cls in ("BH", "N", "W", "WC", "WN", "WNC", "WO") or cls.startswith("W") or is_giant_star(r.get("subtype")):
            unusual.append(cls if not is_giant_star(r.get("subtype")) else f"{cls} giant")
    notable = []
    if bio_max:
        notable.append({"kind": "bio", "value": bio_max,
                        "bodies": sum(1 for r in planets if r.get("bio"))})
    for kind in NOTABLE_KINDS:
        n = kinds.count(kind)
        if n:
            notable.append({"kind": kind, "n": n})
    tf = sum(1 for r in planets if r.get("terraformable"))
    if tf:
        notable.append({"kind": "tf", "n": tf})
    if unusual:
        notable.append({"kind": "unusual", "what": sorted(set(unusual))})
    mapped_own = sum(1 for r in records if r.get("own") and r.get("mapped"))
    landable_known = has_dump or any(r.get("own") for r in planets)
    return {
        "id64": str((row or {}).get("id64") or ""),
        "name": str((row or {}).get("name") or ""),
        "coords": coords,
        "distance": round(float(row.get("distance")), 2) if row and row.get("distance") is not None else None,
        "jumps": jumps_for(row.get("distance"), jump_range) if row else None,
        "visited": bool(visited), "visits": int(visits or 0), "bookmarked": bool(bookmarked),
        "first_found": bool(first_found), "footfall": bool(footfall),
        "status": status, "known": known, "body_count": body_count,
        "mapped": mapped_own, "own_only": bool(own_count and not (row or {}).get("in_spansh", True)),
        "pre_odyssey": pre_odyssey(updated), "spansh_date": str(updated or "")[:10] or None,
        "main_star": star_class(main.get("subtype")) if main else "",
        "main_star_name": str(main.get("subtype") or "") if main else "",
        "scoop": bool(main and scoopable(main.get("subtype"))),
        "stars": len(stars),
        "planets": len(planets),
        "ringed": sum(1 for r in planets if r.get("rings")) if has_dump or own_count else None,
        "landable": sum(1 for r in planets if r.get("landable")) if landable_known else None,
        "elw": kinds.count("elw"),
        "notable": notable,
        "value_now": value_now, "value_max": value_max,
        "detail": bool(has_dump),
        "population": int((row or {}).get("population") or 0),
        "needs_permit": bool((row or {}).get("needs_permit")),
        "region": str((row or {}).get("region") or ""),
        "codex_new": codex_new(records, codex, region_id),
    }


def nearby_rows(results, *, dumps=None, own=None, visits=None, bookmarks=(), firsts=(), footfalls=(),
                jump_range=None, region_id=None, codex=None):
    """Every search result as a Nearby row. ``dumps``: {id64: dump system};
    ``own``: {name casefold: scan items}; ``visits``: {name casefold: count}."""
    dumps, own, visits = dumps or {}, own or {}, visits or {}
    bookmarks = {str(name).casefold() for name in bookmarks}
    firsts = {str(name).casefold() for name in firsts}
    footfalls = {str(name).casefold() for name in footfalls}
    rows = []
    for result in results or ():
        if not isinstance(result, dict) or not result.get("name"):
            continue
        key = str(result["name"]).casefold()
        dump = dumps.get(str(result.get("id64")))
        spansh = search_bodies(result)
        body_count = result.get("body_count")
        if dump:
            spansh = merge(spansh, dump_bodies(dump))
            body_count = dump.get("bodyCount") or body_count
        mine = own_bodies(own.get(key) or ())
        records = merge(spansh, mine)
        rows.append(summarise(result, records, body_count, visited=key in visits, visits=visits.get(key, 0),
                              bookmarked=key in bookmarks, first_found=key in firsts, footfall=key in footfalls,
                              jump_range=jump_range, region_id=region_id, has_dump=bool(dump), own_count=len(mine),
                              codex=codex))
    return rows
