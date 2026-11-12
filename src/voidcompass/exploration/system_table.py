"""The body table (5.7.8): every body of one system as a sortable row, for
Explore & Survey's OVERVIEW and SYSTEM tabs. Pure.

Rows come from your own scans (exact, with sample progress and firsts) laid
over Spansh's dump (everyone else's scans). Columns follow ED-Outrider's Here
view (github.com/weslocke/ED-Outrider, GPLv3): class, distance from arrival
with the distance from its parent under it, gravity, biology and geology,
rings and hotspots, firsts, value now and max.
"""

from __future__ import annotations

import re

from voidcompass.exploration import bio_values, nearby
from voidcompass.outrider import codex_bodies, codex_geo, ggg

LIGHT_SECOND_M = 299_792_458.0
AU_LS = 499.004784
HIGH_GRAVITY = 2.0
_SAMPLE = re.compile(r"SAMPLE\s+(\d)/3")


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _species_colour(display):
    """("Bacterium Aurasus", "Lime") from "Bacterium Aurasus - Lime"."""
    text = str(display or "")
    if " - " in text:
        name, colour = text.rsplit(" - ", 1)
        return name.strip(), colour.strip()
    return text, ""


def _own_bio(item):
    """Your own biology on a body: the survey overlay's detail rows, as cells."""
    from voidcompass.overlays.survey_status_hud import _body_detail_rows
    cells = []
    try:
        details = _body_detail_rows(item)
    except Exception:
        details = []
    for detail in details:
        status = str(detail.get("status") or "")
        name, colour = _species_colour(detail.get("display_name") or detail.get("name"))
        state = {"COMPLETE": "done", "LOGGED": "logged", "DETECTED": "detected"}.get(status)
        progress = 0
        match = _SAMPLE.match(status)
        if match:
            state, progress = "sampling", int(match.group(1))
        if state is None:
            state = "guess"
        value = detail.get("value") or detail.get("max_value") or 0
        cells.append({"name": name, "colour": colour or str(detail.get("variant") or ""), "state": state,
                      "progress": progress, "value": int(value or 0), "low": int(detail.get("min_value") or value or 0)})
    return cells


def _guess_bio(record, region_id=None, coords=None, stars=()):
    """Spansh's bodies: the genera reported, or the likeliest for the signals."""
    count = int(record.get("bio") or 0)
    if count <= 0:
        return []
    cells = []
    genera = [g for g in record.get("genera") or () if g]
    if genera:
        for genus in genera:
            info = bio_values.genus_info(genus)
            cells.append({"name": genus, "colour": "", "state": "detected", "progress": 0,
                          "value": int(info.get("max_value") or 0), "low": int(info.get("min_value") or 0)})
        return cells
    try:
        predicted = bio_values.predict_genera(record.get("subtype"), record.get("atmosphere"), record.get("temperature"),
                                              record.get("gravity"), record.get("volcanism"), record.get("pressure"),
                                              region_id, coords, system_stars=stars, geo=bool(record.get("geo")),
                                              distance_ls=record.get("dist_ls"))
    except Exception:
        predicted = []
    options = []
    for row in predicted or ():
        species = [entry for entry in row.get("species") or () if isinstance(entry, dict)]
        best = max(species, key=lambda entry: int(entry.get("value") or 0), default=None)
        options.append({"name": (best or {}).get("name") or row.get("name") or "", "colour": "", "state": "guess",
                        "progress": 0, "value": int((best or {}).get("value") or row.get("max_value") or 0),
                        "low": int(row.get("min_value") or 0), "likely": bool(row.get("likely", True))})
    options.sort(key=lambda cell: (not cell.pop("likely"), -cell["value"]))
    return options[:count]


def _record_of(item):
    """A scan item as an Outrider-style record (for the codex and GGG helpers)."""
    star = bool(item.get("is_star") or item.get("star_type"))
    atmosphere = item.get("atmosphere_type")
    if atmosphere is None:
        atmosphere = item.get("atmosphere")
    return {"type": "Star" if star else "Planet", "subtype": item.get("star_type") if star else item.get("planet_class"),
            "ed": {"StarType": item.get("star_type"), "PlanetClass": item.get("planet_class"), "MassEM": item.get("mass")},
            "luminosity": item.get("luminosity"), "terraformable": bool(item.get("terraformable")),
            "atmosphere": atmosphere if atmosphere is not None else "", "landable": bool(item.get("landable")),
            "geo": int(item.get("geo_count") or 0), "volcanism": item.get("volcanism")}


def _parent(item_parents, names, main_id):
    """The parent's body id and name, when it isn't the arrival star (Outrider's ↳ line)."""
    for entry in item_parents or ():
        if not isinstance(entry, dict) or not entry:
            continue
        (kind, body_id), = list(entry.items())[:1]
        if kind == "Null":
            return None
        if body_id == main_id:
            return None
        return {"id": body_id, "name": names.get(body_id) or f"#{body_id}"}
    return None


def carto_value(record, mapped=True):
    """What a body pays scanned and mapped (no first-discovery bonus), by the
    same formula our own scans use; for bodies only Spansh knows."""
    mass = _num(record.get("mass")) or 0.0
    if str(record.get("type") or "").casefold() == "star":
        cls = nearby.star_class(record.get("subtype"))
        k = 22628 if cls in ("N", "BH") else 14057 if cls.startswith("W") else 1200
        return int(round(k + mass * k / 66.25))
    kind = nearby.planet_kind(record.get("subtype"))
    tf = bool(record.get("terraformable"))
    k = {"mr": 21790, "aw": 96932, "gg1": 1656, "gg2": 9654, "hmc": 9654, "ww": 64831, "elw": 64831 + 116295}.get(kind, 300)
    if tf and kind in ("hmc", "gg2"):
        k += 100677
    elif tf and kind == "ww":
        k += 116295
    elif tf and kind not in ("elw", "mr", "aw", "gg1"):
        k += 93328
    value = k + k * 0.56591828 * pow(max(mass, 0.0), 0.2)
    if mapped:
        value *= 3.3333333333
        value += max(value * 0.3, 555)
        value *= 1.25
    return int(round(max(500, value)))


def _value_max(item):
    table = item.get("value_table") or {}
    if item.get("is_star") or item.get("star_type"):
        return int(item.get("reward") or table.get("base") or 0)
    if item.get("was_discovered") is False:
        return int(table.get("first_discovered_mapped") or item.get("dss_reward") or item.get("reward") or 0)
    if item.get("was_mapped") is False:
        return int(table.get("first_mapped") or item.get("dss_reward") or item.get("reward") or 0)
    return int(table.get("mapped") or item.get("dss_reward") or item.get("reward") or 0)


def body_rows(system, own_items=(), dump=None, *, search_values=None, codex=None, region_id=None, coords=None,
              records=None, footfalls=(), barycentres=None):
    """The table: ([rows], meta). ``codex``: a CodexIndex (new-to-Codex marks);
    ``records``: {(system casefold, body casefold): label} of your records;
    ``footfalls``: body names you walked first."""
    system = str(system or "")
    records = records or {}
    search_values = search_values or {}
    footfalls = {str(name).casefold() for name in footfalls or ()}
    own = [item for item in own_items or () if isinstance(item, dict) and (item.get("name") or item.get("body_id") is not None)]
    spansh = nearby.dump_bodies(dump) if dump else []
    by_id, by_name = {}, {}
    for record in spansh:
        if record.get("body_id") is not None:
            by_id[record["body_id"]] = record
        by_name[str(record.get("name") or "").casefold()] = record
    names = {}
    main_id = None
    for record in spansh:
        names[record.get("body_id")] = record.get("name")
        if record.get("main"):
            main_id = record.get("body_id")
    for item in own:
        names[item.get("body_id")] = item.get("name")
        if (item.get("is_star") or item.get("star_type")) and not item.get("distance_to_arrival"):
            main_id = item.get("body_id")
    rows, used = [], set()
    # The system's stars, as journal star types, for the species that need one.
    stars = [("H" if nearby.star_class(record.get("subtype")) == "BH" else nearby.star_class(record.get("subtype")))
             for record in spansh if str(record.get("type") or "").casefold() == "star"]
    stars += [item.get("star_type") for item in own if item.get("star_type")]

    def codex_state(entry_id):
        if codex is None or entry_id is None or not hasattr(codex, "type_state"):
            return ""
        return codex.type_state(entry_id, region_id)

    for item in own:
        spansh_record = by_id.get(item.get("body_id")) or by_name.get(str(item.get("name") or "").casefold())
        if spansh_record is not None:
            used.add(id(spansh_record))
        star = bool(item.get("is_star") or item.get("star_type"))
        record = _record_of(item)
        type_entry = codex_bodies.entry_for(record)
        geo_entries = codex_geo.entries_for(record)
        geo_new = [codex_geo.NAMES.get(entry, str(entry)) for entry in geo_entries if codex_state(entry)]
        sma = _num(item.get("semi_major_axis"))
        parent = _parent(item.get("parents"), names, main_id)
        ggg_guess = None
        if not star and "giant" in str(item.get("planet_class") or "").casefold():
            ggg_guess = ggg.predict({"PlanetClass": item.get("planet_class"), "SurfaceTemperature": item.get("surface_temp"),
                                     "MassEM": item.get("mass"), "Radius": item.get("radius")})
        mapped = bool(item.get("dss_complete"))
        rows.append({
            "key": f"own:{item.get('body_id')}:{item.get('name')}", "own": True,
            "body_id": item.get("body_id"), "name": str(item.get("name") or ""),
            "kind": "star" if star else "planet",
            "cls": nearby.star_class(item.get("star_type")) if star else str(item.get("planet_class") or ""),
            "cls_full": str(item.get("class") or item.get("planet_class") or item.get("star_type") or ""),
            "short": "" if star else nearby.KIND_SHORT.get(nearby.planet_kind(item.get("planet_class")), ""),
            "dist_ls": _num(item.get("distance_to_arrival")),
            "parent": ({**parent, "ls": round(sma / LIGHT_SECOND_M, 1) if sma else None} if parent else None),
            "gravity": _num(item.get("gravity_g")), "landable": bool(item.get("landable")),
            "terraformable": bool(item.get("terraformable")), "atmosphere": str(item.get("atmosphere") or ""),
            "scoop": star and nearby.scoopable(item.get("star_type")),
            "bio_count": int(item.get("bio_count") or 0), "bio": _own_bio(item),
            "geo_count": int(item.get("geo_count") or 0), "geo_new": geo_new,
            "rings": [{"name": str(r.get("Name") or ""), "type": str(r.get("RingClass") or "").replace("eRingClass_", "")}
                      for r in item.get("rings") or () if isinstance(r, dict) and "belt" not in str(r.get("Name") or "").casefold()],
            "hotspots": (spansh_record or {}).get("rings") and sum(sum(r.get("hotspots", {}).values()) for r in spansh_record["rings"]) or 0,
            "mining": int(item.get("mining_count") or 0),
            "first_discovered": item.get("was_discovered") is False,
            "first_mapped": mapped and item.get("was_mapped") is False,
            "footfall_open": bool(item.get("first_footfall")),
            "footfall_mine": str(item.get("name") or "").casefold() in footfalls,
            "mapped": mapped,
            "value_now": int(item.get("dss_reward") or 0) if mapped else int(item.get("reward") or 0),
            "value_max": _value_max(item),
            "codex_type": codex_state(type_entry),
            "codex_type_name": codex_bodies.NAMES.get(type_entry, "") if type_entry else "",
            "ggg": ggg_guess and {"chance": ggg_guess["chance"], "border": ggg_guess["border"]},
            "green": bool(item.get("green_giant")),
            "record": records.get((system.casefold(), str(item.get("name") or "").casefold()), ""),
            "updated": None,
        })
        bio_value = sum(cell["value"] for cell in rows[-1]["bio"] if cell["state"] in ("done", "sampling", "logged"))
        rows[-1]["value_now"] += sum(cell["value"] for cell in rows[-1]["bio"] if cell["state"] == "done")
        rows[-1]["value_max"] += max(bio_value, sum(cell["value"] for cell in rows[-1]["bio"]))
    for record in spansh:
        if id(record) in used or str(record.get("type") or "").casefold() not in ("star", "planet"):
            continue
        star = str(record.get("type") or "").casefold() == "star"
        type_entry = codex_bodies.entry_for(record)
        geo_entries = codex_geo.entries_for(record)
        sma = _num(record.get("sma_au"))
        parent = _parent(record.get("parents"), names, main_id)
        bio = _guess_bio(record, region_id, coords, stars)
        value = int(search_values.get(str(record.get("name") or "").casefold()) or 0) or carto_value(record)
        rows.append({
            "key": f"spansh:{record.get('body_id')}:{record.get('name')}", "own": False,
            "body_id": record.get("body_id"), "name": str(record.get("name") or ""),
            "kind": "star" if star else "planet",
            "cls": nearby.star_class(record.get("subtype")) if star else str(record.get("subtype") or ""),
            "cls_full": str(record.get("subtype") or ""),
            "short": "" if star else nearby.KIND_SHORT.get(nearby.planet_kind(record.get("subtype")), ""),
            "dist_ls": _num(record.get("dist_ls")),
            "parent": ({**parent, "ls": round(sma * AU_LS, 1) if sma else None} if parent else None),
            "gravity": _num(record.get("gravity")), "landable": bool(record.get("landable")),
            "terraformable": bool(record.get("terraformable")), "atmosphere": str(record.get("atmosphere") or ""),
            "scoop": star and nearby.scoopable(record.get("subtype")),
            "bio_count": int(record.get("bio") or 0), "bio": bio,
            "geo_count": int(record.get("geo") or 0),
            "geo_new": [codex_geo.NAMES.get(entry, str(entry)) for entry in geo_entries if codex_state(entry)],
            "rings": [{"name": r.get("name"), "type": r.get("type")} for r in record.get("rings") or ()],
            "hotspots": sum(sum((r.get("hotspots") or {}).values()) for r in record.get("rings") or ()),
            "mining": 0, "first_discovered": False, "first_mapped": False, "footfall_open": False, "footfall_mine": False,
            "mapped": False, "value_now": 0, "value_max": value + sum(cell["value"] for cell in bio),
            "codex_type": codex_state(type_entry), "codex_type_name": codex_bodies.NAMES.get(type_entry, "") if type_entry else "",
            "ggg": None, "green": False, "record": "",
            "updated": str(record.get("updated") or "")[:10] or None,
            "pre_odyssey": nearby.pre_odyssey(record.get("updated")),
        })
    rows.sort(key=lambda row: (row["dist_ls"] is None, row["dist_ls"] or 0, row["name"]))
    ordered = scan_order(own, rows, barycentres)
    meta = {
        "known": len(rows), "own": sum(1 for row in rows if row["own"]),
        "body_count": int((dump or {}).get("bodyCount") or 0) or None,
        "spansh_date": max((row["updated"] for row in rows if row.get("updated")), default=None),
        "value_now": sum(row["value_now"] for row in rows), "value_max": sum(row["value_max"] for row in rows),
        "high_gravity": HIGH_GRAVITY, "ordered": ordered,
    }
    meta["pre_odyssey"] = nearby.pre_odyssey(meta["spansh_date"]) if not meta["own"] else None
    return rows, meta


def _scan_of(item):
    """A scan item as the journal's Scan keys, for the orbit maths."""
    keys = {"body_id": "BodyID", "parents": "Parents", "semi_major_axis": "SemiMajorAxis", "eccentricity": "Eccentricity",
            "orbital_inclination": "OrbitalInclination", "periapsis": "Periapsis", "ascending_node": "AscendingNode",
            "mean_anomaly": "MeanAnomaly", "orbital_period": "OrbitalPeriod", "scan_timestamp": "timestamp",
            "star_type": "StarType", "planet_class": "PlanetClass", "distance_to_arrival": "DistanceFromArrivalLS"}
    return {journal: item.get(ours) for ours, journal in keys.items() if item.get(ours) is not None}


def scan_order(own_items, rows, barycentres=None, at=None, worth=500_000):
    """The suggested order to fly to the bodies with work left (biology, or a
    map worth having), nearest first from the arrival star, by where the bodies
    are now (ED-Outrider's orbits.py). Sets row["order"]; returns how many."""
    import time as _time
    from voidcompass.outrider import orbits
    scans = [_scan_of(item) for item in own_items or () if item.get("body_id") is not None]
    if not scans:
        return 0
    try:
        bary = {row["body_id"]: _scan_of(row) for row in barycentres or () if isinstance(row, dict) and row.get("body_id") is not None}
        pos, _approx = orbits.positions(scans, bary, at or _time.time())
    except Exception:
        return 0
    todo = []
    for row in rows:
        if not row.get("own") or row.get("body_id") not in pos:
            continue
        bio_left = row["bio_count"] and any(cell["state"] != "done" for cell in row["bio"]) or (row["bio_count"] and not row["bio"])
        map_left = row["kind"] == "planet" and not row["mapped"] and (row["value_max"] - row["value_now"] >= worth)
        if bio_left or map_left:
            todo.append(row)
    here = pos.get(min(pos, key=lambda body: (pos[body][0] ** 2 + pos[body][1] ** 2 + pos[body][2] ** 2))) if pos else (0, 0, 0)
    order = 0
    while todo:
        nearest = min(todo, key=lambda row: orbits.distance(here, pos[row["body_id"]]))
        order += 1
        nearest["order"] = order
        nearest["leg_ls"] = round(orbits.distance(here, pos[nearest["body_id"]]))
        here = pos[nearest["body_id"]]
        todo.remove(nearest)
    return order


def legend(rows):
    """Only the marks this table is showing (Outrider's footer)."""
    marks = []

    def add(key, test):
        if any(test(row) for row in rows):
            marks.append(key)

    add("scoop", lambda r: r["scoop"])
    add("rings", lambda r: r["rings"])
    add("hotspots", lambda r: r["hotspots"])
    add("first_discovered", lambda r: r["first_discovered"])
    add("first_mapped", lambda r: r["first_mapped"])
    add("footfall_open", lambda r: r["footfall_open"])
    add("done", lambda r: any(c["state"] == "done" for c in r["bio"]))
    add("sampling", lambda r: any(c["state"] == "sampling" for c in r["bio"]))
    add("guess", lambda r: any(c["state"] == "guess" for c in r["bio"]))
    add("codex", lambda r: r["codex_type"] or r["geo_new"])
    add("ggg", lambda r: r["ggg"] or r["green"])
    add("record", lambda r: r["record"])
    add("terraformable", lambda r: r["terraformable"])
    add("landable", lambda r: r["landable"])
    add("geo", lambda r: r["geo_count"])
    add("high_g", lambda r: (r["gravity"] or 0) >= HIGH_GRAVITY)
    return marks


def summary_markdown(system, rows, meta):
    """One button's worth: a short Markdown write-up of the system."""
    lines = [f"**{system}**: {meta['known']} bodies known"
             + (f" of {meta['body_count']}" if meta.get("body_count") else "")
             + (f", worth up to {meta['value_max']:,} cr" if meta.get("value_max") else "")]
    notable = []
    for row in rows:
        bits = []
        if row["short"] in ("ELW", "WW", "AW"):
            bits.append(row["cls"])
        if row["terraformable"]:
            bits.append("terraformable")
        if row["bio_count"]:
            bits.append(f"{row['bio_count']} biological")
        if row["geo_count"]:
            bits.append(f"{row['geo_count']} geological")
        if row["ggg"] or row["green"]:
            bits.append("green gas giant" if row["green"] else "potential green gas giant")
        if row["first_discovered"]:
            bits.append("first discovered")
        if bits:
            notable.append(f"- {row['name']}: {', '.join(bits)}")
    lines += notable[:20]
    return "\n".join(lines)
