"""Profile-local presentation models for Void Compass stellar cartography.

The journal remains authoritative.  These helpers turn retained scan, route,
surface and region facts into bounded JSON models for the HTML command deck;
they do not infer terrain or unreported astronomical state.
"""

from __future__ import annotations

from datetime import datetime, timezone
import html
import json
import math

import bio_values
from deep_survey import HIGH_VALUE_WORLDS, item_value, survey_plan
from galactic_regions import region_names


def _number(value, default=None):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _integer(value, default=0):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError, OverflowError):
        return default


def _text(value, limit=240):
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _epoch(value):
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError):
        return 0.0


def _parent_id(item, known_ids):
    own = str(item.get("body_id")) if item.get("body_id") is not None else ""
    for parent in item.get("parents") or ():
        if not isinstance(parent, dict):
            continue
        for kind, value in parent.items():
            if kind not in {"Star", "Planet"}:
                continue
            candidate = str(value)
            if candidate != own and candidate in known_ids:
                return candidate
    return None


def _body_matches_target(item, target):
    """Match a Status.json Destination to one current-system scan row."""
    if not isinstance(target, dict) or not target:
        return False
    target_body = target.get("body")
    item_body = item.get("body_id")
    body_matches = None
    if target_body is not None and item_body is not None:
        try:
            body_matches = int(target_body) == int(item_body)
        except (TypeError, ValueError):
            body_matches = str(target_body).strip() == str(item_body).strip()
    wanted = _text(target.get("name"), 180).casefold()
    if not wanted:
        return bool(body_matches)
    names = {
        _text(item.get("name"), 180).casefold(),
        _text(item.get("full_name"), 180).casefold(),
    }
    name_matches = wanted in names
    return name_matches and body_matches is not False


def edsm_bodies_to_orrery_items(payload, system_name=None):
    """Translate public EDSM body architecture into display-only scan rows.

    These rows are deliberately suitable for the schematic orrery only. They
    never claim commander discovery, mapping, biology or geology progress and
    are not written to the profile's journal-backed scan cache.
    """
    payload = payload if isinstance(payload, dict) else {}
    system_name = _text(system_name or payload.get("name"), 180)
    system_address = payload.get("id64")
    rows = []
    for body in payload.get("bodies") or ():
        if not isinstance(body, dict) or body.get("bodyId") is None:
            continue
        full_name = _text(body.get("name"), 180)
        short_name = full_name
        if system_name and full_name.casefold().startswith(system_name.casefold()):
            short_name = full_name[len(system_name):].strip() or system_name
        body_type = _text(body.get("type"), 30).casefold()
        is_star = body_type == "star"
        body_class = _text(body.get("subType") or body.get("type") or "Unknown", 120)
        terraforming = _text(body.get("terraformingState"), 80).casefold()
        terraformable = bool(
            terraforming
            and "terraform" in terraforming
            and not terraforming.startswith("not ")
        )
        orbital_days = _number(body.get("orbitalPeriod"))
        rotation_days = _number(body.get("rotationalPeriod"))
        semi_major_au = _number(body.get("semiMajorAxis"))
        radius_km = _number(body.get("radius"))
        rows.append({
            "body_id": body.get("bodyId"),
            "system_address": system_address,
            "name": short_name or f"Body {body.get('bodyId')}",
            "full_name": full_name or short_name,
            "class": body_class,
            "star_type": body_class if is_star else None,
            "planet_class": None if is_star else body_class,
            "is_star": is_star,
            "parents": list(body.get("parents") or []),
            "distance_to_arrival": _number(body.get("distanceToArrival")),
            "landable": bool(body.get("isLandable")),
            "terraformable": terraformable,
            "mass": _number(
                body.get("solarMasses") if is_star else body.get("earthMasses"),
                1.0,
            ),
            "gravity_g": _number(body.get("gravity")),
            "radius": radius_km * 1000.0 if radius_km is not None else None,
            "surface_temp": _number(body.get("surfaceTemperature")),
            "surface_pressure": _number(body.get("surfacePressure")),
            "atmosphere_type": _text(body.get("atmosphereType"), 100),
            "volcanism": _text(body.get("volcanismType"), 100),
            "rings": list(body.get("rings") or []),
            "reserve_level": _text(body.get("reserveLevel"), 80),
            # EDSM publishes these periods in days and axes in AU; the journal
            # model retained by Void Compass uses seconds and metres.
            "orbital_period": orbital_days * 86400.0 if orbital_days is not None else None,
            "rotation_period": rotation_days * 86400.0 if rotation_days is not None else None,
            "semi_major_axis": semi_major_au * 149597870700.0 if semi_major_au is not None else None,
            "eccentricity": _number(body.get("orbitalEccentricity")),
            "axial_tilt": _number(body.get("axialTilt")),
            "tidal_lock": bool(body.get("rotationalPeriodTidallyLocked")),
            "was_discovered": True,
            "was_mapped": False,
            "dss_complete": False,
            "bio_count": 0,
            "geo_count": 0,
            "icons": [],
            "_orrery_source": "edsm",
        })
    return rows


def build_orrery(items, target=None):
    """Return a compact, schematic system architecture model."""
    source = [row for row in (items or ()) if isinstance(row, dict)]
    known_ids = {
        str(row.get("body_id")) for row in source if row.get("body_id") is not None
    }
    bodies = []
    for ordinal, item in enumerate(sorted(
        source,
        key=lambda row: (_integer(row.get("body_id"), 999999), _text(row.get("name"))),
    )):
        body_id = str(item.get("body_id")) if item.get("body_id") is not None else f"n{ordinal}"
        body_class = _text(item.get("planet_class") or item.get("class") or "Unknown", 120)
        is_star = bool(item.get("is_star") or item.get("star_type"))
        mapped = bool(item.get("dss_complete") or item.get("was_mapped"))
        organic = item.get("organic_scans") or {}
        analysed = sum(
            1 for row in (organic.values() if isinstance(organic, dict) else organic)
            if isinstance(row, dict) and (
                str(row.get("scan_type") or "").casefold() == "analyse"
                or row.get("is_complete")
            )
        )
        flags = []
        if item.get("terraformable"):
            flags.append("TERRAFORMABLE")
        if item.get("landable"):
            flags.append("LANDABLE")
        if item.get("was_discovered") is False:
            flags.append("FIRST DISCOVERY")
        if item.get("first_footfall"):
            flags.append("FIRST FOOTFALL")
        if mapped:
            flags.append("DSS COMPLETE")
        bodies.append({
            "id": body_id,
            "body_id": item.get("body_id"),
            "parent_id": _parent_id(item, known_ids),
            "name": _text(item.get("name") or item.get("full_name") or f"Body {body_id}", 160),
            "full_name": _text(item.get("full_name") or item.get("name"), 180),
            "class": body_class,
            "kind": "star" if is_star else "planet",
            "star_type": _text(item.get("star_type"), 40),
            "semi_major_axis": _number(item.get("semi_major_axis")),
            "orbital_period": _number(item.get("orbital_period")),
            "rotation_period": _number(item.get("rotation_period")),
            "eccentricity": _number(item.get("eccentricity")),
            "distance_ls": _number(item.get("distance_to_arrival")),
            "mass": _number(item.get("mass")),
            "gravity_g": _number(item.get("gravity_g")),
            "temperature_k": _number(item.get("surface_temp")),
            "atmosphere": _text(item.get("atmosphere_type") or item.get("atmosphere") or "Airless", 100),
            "rings": len(item.get("rings") or ()),
            "bio": max(0, _integer(item.get("bio_count"))),
            "bio_complete": analysed,
            "geo": max(0, _integer(item.get("geo_count"))),
            "value": max(0, item_value(item)),
            "mapped": mapped,
            "landable": bool(item.get("landable")),
            "terraformable": bool(item.get("terraformable")),
            "targeted": _body_matches_target(item, target),
            "flags": flags,
        })
    children = {row["parent_id"] for row in bodies if row.get("parent_id")}
    targeted = next((row for row in bodies if row["targeted"]), None)
    target_model = None
    if isinstance(target, dict) and target:
        target_model = {
            "name": _text(target.get("name"), 180),
            "body": target.get("body"),
            "system": target.get("system"),
            "resolved": targeted is not None,
            "id": targeted.get("id") if targeted else None,
            "body_id": targeted.get("body_id") if targeted else target.get("body"),
        }
    return {
        "bodies": bodies,
        "stars": sum(1 for row in bodies if row["kind"] == "star"),
        "planets": sum(1 for row in bodies if row["kind"] == "planet"),
        "mapped": sum(1 for row in bodies if row["kind"] == "planet" and row["mapped"]),
        "roots": sum(1 for row in bodies if not row.get("parent_id")),
        "parents": len(children),
        "mode": "SCHEMATIC JOURNAL ARCHITECTURE",
        "target": target_model,
    }


def build_survey_queue(items, state=None, target=None):
    """Combine the conservative survey plan with commander queue choices."""
    state = state if isinstance(state, dict) else {}
    pinned = {str(value) for value in state.get("pinned") or ()}
    skipped = {str(value) for value in state.get("skipped") or ()}
    completed = {str(value) for value in state.get("completed") or ()}
    normalized_items = []
    for source in (items or ()):
        if not isinstance(source, dict):
            continue
        item = dict(source)
        organic = item.get("organic_scans") or {}
        organic_rows = organic.values() if isinstance(organic, dict) else organic
        analysed = sum(
            1 for row in organic_rows if isinstance(row, dict) and (
                str(row.get("scan_type") or "").casefold() == "analyse"
                or row.get("is_complete")
            )
        )
        item["organic_complete_count"] = max(
            _integer(item.get("organic_complete_count")), analysed,
        )
        normalized_items.append(item)
    by_name = {
        str(row.get("name") or row.get("full_name") or "").casefold(): row
        for row in normalized_items
    }
    rows = []
    for plan in survey_plan(normalized_items):
        item = by_name.get(str(plan.get("body") or "").casefold(), {})
        key = (
            f"body:{item.get('body_id')}"
            if item.get("body_id") is not None else f"name:{str(plan.get('body') or '').casefold()}"
        )
        auto_complete = bool(
            plan.get("mapped")
            and (not _integer(plan.get("bio")) or _integer(item.get("organic_complete_count")) >= _integer(plan.get("bio")))
            and not _integer(plan.get("geo"))
        )
        status = (
            "complete" if key in completed or auto_complete
            else "skipped" if key in skipped
            else "pinned" if key in pinned
            else "pending"
        )
        rows.append({
            **plan,
            "key": key,
            "status": status,
            "pinned": key in pinned,
            "manual_complete": key in completed,
            "targeted": _body_matches_target(item, target),
        })
    order = {"pinned": 0, "pending": 1, "skipped": 2, "complete": 3}
    rows.sort(key=lambda row: (
        0 if row["targeted"] else 1,
        order.get(row["status"], 9),
        -_integer(row.get("score")),
        row.get("distance_ls") or 0,
    ))
    return {
        "rows": rows,
        "pending": sum(1 for row in rows if row["status"] in {"pinned", "pending"}),
        "pinned": sum(1 for row in rows if row["status"] == "pinned"),
        "complete": sum(1 for row in rows if row["status"] == "complete"),
        "skipped": sum(1 for row in rows if row["status"] == "skipped"),
        "next": next((row for row in rows if row["status"] in {"pinned", "pending"}), None),
    }


def build_science_lab(scan_rows):
    """Aggregate profile-local scan evidence into explainable correlations."""
    systems = set()
    body_classes = {}
    atmospheres = {}
    gravity = {"MICRO <0.15G": 0, "LOW 0.15–0.5G": 0, "MID 0.5–1.5G": 0, "HIGH >1.5G": 0, "UNKNOWN": 0}
    star_classes = {}
    species = {}
    bodies = landable = terraformable = valuable = firsts = 0
    biological_bodies = 0
    for system, item in scan_rows or ():
        if not isinstance(item, dict):
            continue
        system = _text(system, 160)
        systems.add(system.casefold())
        if item.get("is_star") or item.get("star_type"):
            label = _text(item.get("class") or item.get("star_type") or "Unknown star", 100)
            star_classes[label] = star_classes.get(label, 0) + 1
            continue
        bodies += 1
        body_class = _text(item.get("planet_class") or item.get("class") or "Unknown", 100)
        body_classes[body_class] = body_classes.get(body_class, 0) + 1
        if item.get("landable"):
            landable += 1
        if item.get("terraformable"):
            terraformable += 1
        if item.get("terraformable") or body_class in HIGH_VALUE_WORLDS:
            valuable += 1
        if item.get("was_discovered") is False:
            firsts += 1
        organic = item.get("organic_scans") or {}
        organic_rows = organic.values() if isinstance(organic, dict) else organic
        analysed = [
            row for row in organic_rows if isinstance(row, dict) and (
                str(row.get("scan_type") or "").casefold() == "analyse"
                or row.get("is_complete")
            )
        ]
        if _integer(item.get("bio_count")) or analysed:
            biological_bodies += 1
            atmosphere = _text(item.get("atmosphere_type") or item.get("atmosphere") or "Airless", 100)
            atmospheres[atmosphere] = atmospheres.get(atmosphere, 0) + 1
            g = _number(item.get("gravity_g"))
            band = (
                "UNKNOWN" if g is None else "MICRO <0.15G" if g < 0.15
                else "LOW 0.15–0.5G" if g < 0.5 else "MID 0.5–1.5G" if g <= 1.5
                else "HIGH >1.5G"
            )
            gravity[band] += 1
        for record in analysed:
            name = _text(record.get("species") or record.get("genus") or "Unknown organic", 140)
            entry = species.setdefault(name, {
                "name": name,
                "genus": _text(record.get("genus") or name.split(" ")[0], 80),
                "analyses": 0,
                "systems": set(),
                "worlds": set(),
                "value": max(0, _integer(bio_values.species_value(name))),
            })
            entry["analyses"] += 1
            entry["systems"].add(system.casefold())
            entry["worlds"].add(f"{system.casefold()}|{item.get('body_id')}|{item.get('name')}")

    def ranked(mapping, limit=12):
        return [
            {"label": label, "count": count}
            for label, count in sorted(mapping.items(), key=lambda row: (-row[1], row[0]))[:limit]
            if count
        ]

    species_rows = []
    for row in species.values():
        species_rows.append({
            "name": row["name"], "genus": row["genus"],
            "analyses": row["analyses"], "systems": len(row["systems"]),
            "worlds": len(row["worlds"]), "value": row["value"],
        })
    species_rows.sort(key=lambda row: (-row["analyses"], -row["value"], row["name"]))
    return {
        "systems": len(systems), "bodies": bodies, "landable": landable,
        "terraformable": terraformable, "valuable": valuable,
        "first_discoveries": firsts, "biological_bodies": biological_bodies,
        "species_total": len(species_rows), "analyses": sum(row["analyses"] for row in species_rows),
        "species": species_rows[:80], "body_classes": ranked(body_classes),
        "atmospheres": ranked(atmospheres), "gravity": ranked(gravity),
        "star_classes": ranked(star_classes),
    }


def build_region_passport(region_stats):
    region_stats = region_stats if isinstance(region_stats, dict) else {}
    rows = []
    for region_id, name in enumerate(region_names(), start=1):
        source = region_stats.get(str(region_id)) or region_stats.get(region_id) or {}
        systems = source.get("systems") or ()
        visits = max(0, _integer(source.get("visits")))
        rows.append({
            "id": region_id, "name": name, "visited": bool(visits or systems),
            "visits": visits, "systems": len(systems),
            "distance": round(max(0.0, _number(source.get("distance_ly"), 0.0)), 1),
            "fss": max(0, _integer(source.get("fss"))),
            "dss": max(0, _integer(source.get("dss"))),
            "biology": max(0, _integer(source.get("biology"))),
            "codex": max(0, _integer(source.get("codex"))),
            "screenshots": max(0, _integer(source.get("screenshots"))),
            "notable": max(0, _integer(source.get("notable"))),
            "first_visit": _text(source.get("first_visit"), 50),
            "last_visit": _text(source.get("last_visit"), 50),
            "last_system": _text(source.get("last_system"), 160),
            "last_photo": _text(source.get("last_photo"), 500),
        })
    visited = sum(1 for row in rows if row["visited"])
    return {
        "rows": rows, "visited": visited, "total": len(rows),
        "percent": round(visited * 100.0 / len(rows), 1) if rows else 0.0,
        "systems": sum(row["systems"] for row in rows),
        "distance": round(sum(row["distance"] for row in rows), 1),
        "biology": sum(row["biology"] for row in rows),
    }


def build_replay(sessions, survey_snapshot, max_points=1200):
    """Build one bounded timeline shared by recent Captain's Log sessions."""
    sessions = list(sessions or ())
    survey_snapshot = survey_snapshot if isinstance(survey_snapshot, dict) else {}
    points = []
    for row in sorted(survey_snapshot.get("route_points") or (), key=lambda item: _epoch(item.get("timestamp"))):
        pos = row.get("pos")
        if not isinstance(pos, (list, tuple)) or len(pos) < 3:
            continue
        try:
            clean_pos = [round(float(pos[index]), 3) for index in range(3)]
        except (TypeError, ValueError):
            continue
        points.append({
            "timestamp": _text(row.get("timestamp"), 50), "epoch": _epoch(row.get("timestamp")),
            "system": _text(row.get("system") or "Unknown", 160), "pos": clean_pos,
            "event": _text(row.get("event") or "FSDJump", 30),
            "jump_dist": round(max(0.0, _number(row.get("jump_dist"), 0.0)), 2),
            "star_class": _text(row.get("star_class"), 40),
            "discoveries": max(0, _integer(row.get("discoveries"))),
            "codex": max(0, _integer(row.get("codex"))),
            "screenshots": max(0, _integer(row.get("screenshots"))),
            "fss_complete": bool(row.get("fss_complete")),
        })
    points = points[-max(100, int(max_points)):]
    highlight_context = []
    for session in sessions:
        for row in session.get("highlights") or ():
            if not isinstance(row, dict) or str(row.get("kind") or "").upper() == "PHOTO":
                continue
            epoch = _epoch(row.get("timestamp"))
            if epoch:
                highlight_context.append({
                    "epoch": epoch, "timestamp": _text(row.get("timestamp"), 50),
                    "event": _text(row.get("kind"), 30),
                    "label": _text(row.get("title"), 180),
                    "detail": _text(row.get("detail"), 260),
                })

    photos = []
    for row in (survey_snapshot.get("screenshots") or ())[-240:]:
        if not isinstance(row, dict):
            continue
        photo_epoch = _epoch(row.get("timestamp"))
        nearby = None
        if not row.get("nearby_label") and photo_epoch:
            candidates = [
                item for item in highlight_context
                if abs(item["epoch"] - photo_epoch) <= 600
            ]
            nearby = min(
                candidates, default=None,
                key=lambda item: abs(item["epoch"] - photo_epoch),
            )
        nearby = nearby or {}
        photos.append({
            "timestamp": _text(row.get("timestamp"), 50), "epoch": _epoch(row.get("timestamp")),
            "system": _text(row.get("system"), 160), "body": _text(row.get("body"), 180),
            "filename": _text(row.get("filename"), 500),
            "latitude": _number(row.get("latitude")), "longitude": _number(row.get("longitude")),
            "nearby_event": _text(row.get("nearby_event") or nearby.get("event"), 30),
            "nearby_label": _text(row.get("nearby_label") or nearby.get("label"), 180),
            "nearby_detail": _text(row.get("nearby_detail") or nearby.get("detail"), 260),
            "nearby_timestamp": _text(row.get("nearby_timestamp") or nearby.get("timestamp"), 50),
        })
    rendered_sessions = []
    for index, session in enumerate(sessions):
        start = _epoch(session.get("started"))
        end = _epoch(session.get("ended")) or float("inf")
        matching = [idx for idx, row in enumerate(points) if start <= row["epoch"] <= end]
        rendered_sessions.append({
            "index": index, "started": _text(session.get("started"), 50),
            "ended": _text(session.get("ended"), 50),
            "start_system": _text(session.get("start_system"), 160),
            "end_system": _text(session.get("end_system") or session.get("start_system"), 160),
            "point_start": matching[0] if matching else None,
            "point_end": matching[-1] if matching else None,
        })
    return {"points": points, "photos": photos, "sessions": rendered_sessions}


def replay_export_html(title, commander, replay, session=None):
    """Create a standalone, dependency-free interactive expedition replay."""
    selected = session if isinstance(session, dict) else {}
    start_index = selected.get("point_start")
    end_index = selected.get("point_end")
    points = list((replay or {}).get("points") or ())
    if isinstance(start_index, int) and isinstance(end_index, int):
        points = points[start_index:end_index + 1]
    data = json.dumps({
        "title": _text(title, 180), "commander": _text(commander, 120), "points": points,
    }, ensure_ascii=False).replace("</", "<\\/")
    safe_title = html.escape(_text(title or "Void Compass Expedition Replay", 180))
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{safe_title}</title>
<style>:root{{--bg:#05090d;--panel:#0b131a;--line:#243541;--text:#d6e6ed;--muted:#76909c;--cyan:#42c8e8;--orange:#ff9b36}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 40% 30%,#10212c,#030608 64%);color:var(--text);font:14px Segoe UI,Arial,sans-serif}}header{{padding:28px 34px;border-bottom:1px solid var(--line)}}small{{color:var(--cyan);letter-spacing:.16em}}h1{{margin:.3rem 0 0;font-weight:500}}main{{padding:24px;display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:18px}}section,aside{{background:rgba(8,15,21,.92);border:1px solid var(--line);padding:18px}}svg{{width:100%;height:65vh;min-height:430px}}path{{fill:none;stroke:var(--cyan);stroke-width:1.5;opacity:.55}}circle{{fill:var(--orange);stroke:#fff;stroke-width:1}}#ship{{fill:#fff;stroke:var(--cyan);stroke-width:5}}input{{width:100%}}button{{background:#10232c;color:var(--text);border:1px solid var(--cyan);padding:8px 12px}}ol{{padding-left:22px;max-height:45vh;overflow:auto}}li{{margin:0 0 9px;color:var(--muted)}}li b{{display:block;color:var(--text)}}@media(max-width:800px){{main{{grid-template-columns:1fr}}}}</style></head>
<body><header><small>VOID COMPASS // EXPEDITION CHRONICLE</small><h1>{safe_title}</h1><p id=\"summary\"></p></header><main><section><svg id=\"chart\" viewBox=\"0 0 1000 620\"><path id=\"route\"/><circle id=\"ship\" r=\"7\"/></svg><input id=\"time\" type=\"range\" min=\"0\" value=\"0\"><p id=\"readout\"></p><button id=\"play\">PLAY</button></section><aside><small>JOURNEY LOG</small><ol id=\"log\"></ol></aside></main>
<script>const DATA={data};const pts=DATA.points||[];const svg=document.getElementById('chart'),route=document.getElementById('route'),ship=document.getElementById('ship'),slider=document.getElementById('time'),readout=document.getElementById('readout');slider.max=Math.max(0,pts.length-1);let projected=[];if(pts.length){{const xs=pts.map(p=>p.pos[0]),zs=pts.map(p=>p.pos[2]),minX=Math.min(...xs),maxX=Math.max(...xs),minZ=Math.min(...zs),maxZ=Math.max(...zs),span=Math.max(1,maxX-minX,maxZ-minZ);projected=pts.map(p=>[70+(p.pos[0]-minX)*860/span,550-(p.pos[2]-minZ)*500/span]);route.setAttribute('d',projected.map((p,i)=>(i?'L':'M')+p[0]+' '+p[1]).join(' '));document.getElementById('log').innerHTML=pts.map(p=>'<li><b>'+p.system+'</b>'+p.timestamp.replace('T',' ').slice(0,16)+' · '+p.jump_dist.toFixed(1)+' LY</li>').join('');}}function draw(){{const i=+slider.value,p=pts[i],xy=projected[i];if(!p||!xy)return;ship.setAttribute('cx',xy[0]);ship.setAttribute('cy',xy[1]);readout.textContent=(i+1)+' / '+pts.length+' · '+p.system+' · '+p.jump_dist.toFixed(1)+' LY';}}slider.oninput=draw;let timer=null;document.getElementById('play').onclick=e=>{{if(timer){{clearInterval(timer);timer=null;e.target.textContent='PLAY';return}}e.target.textContent='PAUSE';timer=setInterval(()=>{{slider.value=(+slider.value+1)%Math.max(1,pts.length);draw()}},420)}};document.getElementById('summary').textContent=(DATA.commander?'CMDR '+DATA.commander+' · ':'')+pts.length+' retained systems';draw();</script></body></html>"""
