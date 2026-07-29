"""Pure exploration fieldcraft helpers shared by UI, HUD, and tests."""

from __future__ import annotations

from datetime import datetime, timezone
import math

from flight_callouts import is_scoopable, route_ahead


WHITE_DWARF_CLASSES = {
    "D", "DA", "DAB", "DAO", "DAZ", "DAV", "DB", "DBZ", "DBV",
    "DO", "DOV", "DQ", "DC", "DCV", "DX",
}
HIGH_VALUE_WORLDS = {"Earthlike body", "Water world", "Ammonia world"}


def _number(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value, default=0):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def route_safety_forecast(entries, current_system="", current_star_class="",
                          fuel_main=None, fuel_capacity=None, fuel_samples=()):
    """Summarise the verified hazards and refuelling horizon of NavRoute."""
    ahead = route_ahead(entries, current_system, current_star_class)
    pending = ahead[1:] if ahead else []
    if not pending:
        return {
            "status": "IDLE", "level": "muted", "headline": "NO ACTIVE GAME ROUTE",
            "detail": "Plot a route in Elite to calculate scoop and stellar-hazard intelligence.",
            "jumps": 0, "eta_minutes": 0, "badge": None,
        }

    known = [row for row in pending if row.get("scoopable") is not None]
    scoopable = [row for row in pending if row.get("scoopable") is True]
    unknown = len(pending) - len(known)
    neutron = []
    white_dwarfs = []
    for row in pending:
        star_class = str(row.get("star_class") or "").strip().upper()
        if star_class in {"N", "NS"}:
            neutron.append(row)
        elif star_class in WHITE_DWARF_CLASSES:
            white_dwarfs.append(row)

    next_scoop = next(
        (index + 1 for index, row in enumerate(pending) if row.get("scoopable") is True),
        None,
    )
    longest_dry = 0
    dry_now = 0
    dry_start = None
    dry_span = None
    for index, row in enumerate(pending):
        if row.get("scoopable") is False:
            if dry_now == 0:
                dry_start = index
            dry_now += 1
            if dry_now > longest_dry:
                longest_dry = dry_now
                dry_span = (dry_start, index)
        else:
            dry_now = 0
            dry_start = None

    conservative_sample = max(
        (_number(value, 0.0) or 0.0 for value in (fuel_samples or ())),
        default=0.0,
    )
    current_fuel = _number(fuel_main)
    capacity = _number(fuel_capacity)
    endurance = (
        max(0, int(current_fuel / conservative_sample))
        if current_fuel is not None and conservative_sample > 0 else None
    )
    fuel_percent = (
        max(0, min(100, round(current_fuel * 100 / capacity)))
        if current_fuel is not None and capacity and capacity > 0 else None
    )
    current_scoopable = is_scoopable(current_star_class)

    level, status = "ok", "READY"
    if next_scoop is not None and endurance is not None and endurance < next_scoop:
        level, status = (
            ("warn", "TOP OFF NOW") if current_scoopable is True
            else ("alert", "FUEL RISK")
        )
    elif next_scoop is None and not unknown and endurance is not None and endurance < len(pending):
        level, status = "alert", "NO FUEL STAR"
    elif white_dwarfs or longest_dry >= 4:
        level, status = "warn", "CAUTION"
    elif unknown:
        level, status = "info", "PARTIAL DATA"

    scoop_text = (
        f"next scoopable in {next_scoop} jump{'s' if next_scoop != 1 else ''}"
        if next_scoop is not None else
        ("no scoopable primary recorded" if not unknown else "next scoop point uncertain")
    )
    dry_text = f"longest confirmed dry stretch {longest_dry}"
    if dry_span:
        start_name = pending[dry_span[0]].get("system") or "?"
        end_name = pending[dry_span[1]].get("system") or "?"
        dry_text += f" ({start_name} → {end_name})"
    fuel_text = (
        f"tank {fuel_percent}% · about {endurance} conservative jumps"
        if endurance is not None and fuel_percent is not None else
        f"tank {fuel_percent}% · jump burn still learning"
        if fuel_percent is not None else "fuel endurance unavailable"
    )
    hazard_bits = []
    if neutron:
        hazard_bits.append(f"{len(neutron)} neutron")
    if white_dwarfs:
        hazard_bits.append(f"{len(white_dwarfs)} white dwarf")
    if unknown:
        hazard_bits.append(f"{unknown} unknown class")
    hazards = ", ".join(hazard_bits) or "no compact-star hazards recorded"
    badge = None
    if level == "alert":
        badge = "ROUTE FUEL"
    elif white_dwarfs:
        badge = f"WD {len(white_dwarfs)}"
    elif longest_dry >= 4:
        badge = f"DRY {longest_dry}"

    return {
        "status": status,
        "level": level,
        "headline": f"{status} · {len(pending)} jumps · ~{max(1, math.ceil(len(pending) * 55 / 60))} min nominal",
        "detail": f"{scoop_text} · {dry_text} · {fuel_text} · {hazards}",
        "jumps": len(pending),
        "eta_minutes": max(1, math.ceil(len(pending) * 55 / 60)),
        "known_classes": len(known),
        "unknown_classes": unknown,
        "scoopable_count": len(scoopable),
        "next_scoop_jumps": next_scoop,
        "longest_dry": longest_dry,
        "neutron_count": len(neutron),
        "white_dwarf_count": len(white_dwarfs),
        "fuel_percent": fuel_percent,
        "fuel_endurance_jumps": endurance,
        "badge": badge,
        "badge_state": "alert" if level == "alert" else "info",
    }


def revisit_candidate(system, bodies, scanned=0, total=0, position=None, timestamp=None):
    """Return a worthwhile unfinished-system record, or ``None`` for noise."""
    system = str(system or "").strip()
    if not system or system in {"---", "Unknown"}:
        return None
    reasons = []
    body_names = []
    score = 0
    valuable_unmapped = 0
    biology_remaining = 0
    for item in bodies or []:
        if not isinstance(item, dict) or item.get("is_star"):
            continue
        body_class = str(item.get("planet_class") or item.get("class") or "")
        reward = _integer(item.get("dss_reward") or item.get("reward"))
        mapped = bool(item.get("dss_complete") or item.get("mapped"))
        terraformable = bool(item.get("terraformable"))
        valuable = body_class in HIGH_VALUE_WORLDS or terraformable or reward >= 250_000
        if valuable and not mapped:
            valuable_unmapped += 1
            score += 45 if body_class in HIGH_VALUE_WORLDS else 30
            body_names.append(str(item.get("full_name") or item.get("name") or body_class))
        bio_total = _integer(item.get("bio_count"))
        bio_done = max(
            _integer(item.get("organic_complete_count")),
            sum(1 for row in (item.get("organic_scans") or {}).values()
                if isinstance(row, dict) and row.get("is_complete")),
        )
        if bio_total > bio_done:
            remaining = bio_total - bio_done
            biology_remaining += remaining
            score += 35 + min(25, remaining * 5)
            body_names.append(str(item.get("full_name") or item.get("name") or "Biology body"))

    remaining_fss = max(0, _integer(total) - _integer(scanned))
    if valuable_unmapped:
        reasons.append(f"{valuable_unmapped} valuable mapping target(s)")
    if biology_remaining:
        reasons.append(f"{biology_remaining} biological analysis/analyses")
    # Retain an incomplete FSS record when some worthwhile evidence is already
    # known, or when a substantial portion of a larger system remains unknown.
    if remaining_fss and (reasons or remaining_fss >= 5):
        reasons.append(f"FSS {_integer(scanned)}/{_integer(total)}")
        score += min(25, remaining_fss * 3)
    if not reasons:
        return None
    return {
        "system": system,
        "timestamp": str(timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")),
        "position": list(position[:3]) if isinstance(position, (list, tuple)) and len(position) >= 3 else None,
        "score": min(100, score),
        "reasons": reasons,
        "detail": " · ".join(reasons),
        "bodies": list(dict.fromkeys(body_names))[:8],
        "scanned": _integer(scanned),
        "total": _integer(total),
        "valuable_unmapped": valuable_unmapped,
        "biology_remaining": biology_remaining,
    }


def data_vault_snapshot(companion_state, sessions=()):
    """Build a truthful unsold/sold explorer-data summary."""
    state = companion_state if isinstance(companion_state, dict) else {}
    sessions = [row for row in (sessions or ()) if isinstance(row, dict)]
    exploration = _integer(state.get("unsold_exploration_cr"))
    biology = _integer(state.get("unsold_bio_cr"))
    bonus = _integer(state.get("unsold_bio_bonus_potential_cr"))
    keys = len(state.get("unsold_scan_keys") or [])
    last_cartographic = state.get("last_exploration_sale") or {}
    last_biology = state.get("last_bio_sale") or {}
    if not last_cartographic:
        session = next((row for row in sessions if _integer(row.get("exploration_sales"))), None)
        if session:
            last_cartographic = {
                "timestamp": session.get("ended") or session.get("started"),
                "value": _integer(session.get("exploration_sales")),
            }
    if not last_biology:
        session = next((row for row in sessions if _integer(row.get("biology_sales"))), None)
        if session:
            last_biology = {
                "timestamp": session.get("ended") or session.get("started"),
                "value": _integer(session.get("biology_sales")),
            }
    return {
        "exploration_cr": exploration,
        "biology_cr": biology,
        "biology_bonus_cr": bonus,
        "minimum_total_cr": exploration + biology,
        "maximum_total_cr": exploration + biology + bonus,
        "systems_represented": keys,
        "last_exploration_sale": dict(last_cartographic),
        "last_bio_sale": dict(last_biology),
        "lost_at": state.get("exploration_data_lost_at"),
    }


def save_expedition_share_card(path, title, session, snapshot, palette):
    """Write a themed 1200×675 PNG from retained expedition facts."""
    from PIL import Image, ImageDraw, ImageFont

    palette = dict(palette or {})
    bg = palette.get("bg", "#070b10")
    panel = palette.get("panel", "#0d141c")
    accent = palette.get("accent", "#00d1ff")
    orange = palette.get("orange", "#ff8a3d")
    text = palette.get("text", "#dcebf3")
    muted = palette.get("muted", "#91a8b7")
    image = Image.new("RGB", (1200, 675), bg)
    draw = ImageDraw.Draw(image)

    def font(size, bold=False):
        candidates = (
            "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        )
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    session = session if isinstance(session, dict) else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    route = [row for row in snapshot.get("route_points") or [] if isinstance(row, dict)]
    draw.rectangle((28, 28, 1172, 647), fill=panel, outline=accent, width=2)
    draw.line((28, 102, 1172, 102), fill=accent, width=2)
    draw.text((58, 48), str(title or "EXPEDITION").upper()[:60], fill=accent, font=font(31, True))
    draw.text((58, 82), "VOIDCOMPASS // EXPEDITION CHRONICLE", fill=orange, font=font(13, True))

    stats = (
        ("JUMPS", _integer(session.get("jumps"))),
        ("DISTANCE", f"{_number(session.get('distance_ly'), 0.0):,.1f} LY"),
        ("FSS", _integer(session.get("fss_surveys"))),
        ("DSS", _integer(session.get("dss_maps"))),
        ("BIO", _integer(session.get("bio_analyses"))),
        ("CODEX", _integer(session.get("codex"))),
    )
    for index, (label, value) in enumerate(stats):
        x = 58 + (index % 3) * 190
        y = 132 + (index // 3) * 92
        draw.text((x, y), label, fill=muted, font=font(12, True))
        draw.text((x, y + 23), str(value), fill=text, font=font(23, True))

    map_box = (650, 130, 1135, 520)
    draw.rectangle(map_box, fill=bg, outline=palette.get("border", "#243746"), width=2)
    points = []
    for row in route:
        pos = row.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) >= 3:
            try:
                points.append((float(pos[0]), float(pos[2])))
            except (TypeError, ValueError):
                pass
    if points:
        min_x, max_x = min(x for x, _ in points), max(x for x, _ in points)
        min_y, max_y = min(y for _, y in points), max(y for _, y in points)
        span_x, span_y = max(1.0, max_x - min_x), max(1.0, max_y - min_y)
        projected = [(
            map_box[0] + 24 + (x - min_x) / span_x * (map_box[2] - map_box[0] - 48),
            map_box[3] - 24 - (y - min_y) / span_y * (map_box[3] - map_box[1] - 48),
        ) for x, y in points]
        if len(projected) > 1:
            draw.line(projected, fill=orange, width=3)
        for index, point in enumerate(projected):
            radius = 7 if index in (0, len(projected) - 1) else 3
            draw.ellipse((point[0] - radius, point[1] - radius,
                          point[0] + radius, point[1] + radius),
                         fill=accent if index == len(projected) - 1 else orange)
    else:
        draw.text((795, 310), "NO ROUTE COORDINATES", fill=muted, font=font(14, True))

    start = session.get("start_system") or (route[0].get("system") if route else "Unknown")
    end = session.get("end_system") or (route[-1].get("system") if route else "Unknown")
    draw.text((58, 350), "ROUTE", fill=orange, font=font(13, True))
    draw.text((58, 378), f"{start}  →  {end}", fill=text, font=font(21, True))
    sales = _integer(session.get("exploration_sales")) + _integer(session.get("biology_sales"))
    draw.text((58, 438), "DATA SOLD", fill=muted, font=font(12, True))
    draw.text((58, 462), f"{sales:,} CR", fill=accent, font=font(24, True))
    date = str(session.get("started") or datetime.now(timezone.utc).isoformat())[:10]
    draw.text((58, 590), f"{date}  //  Generated locally from Elite journal evidence",
              fill=muted, font=font(12))
    image.save(path, format="PNG", optimize=True)
    return path
