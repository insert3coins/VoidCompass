"""Pure helpers for low-noise, route-aware flight voice advisories."""


SCOOPABLE_PRIMARY = set("OBAFGKM")
SCOOPABLE_EXACT = {"TTS", "AEBE"}
NON_SCOOPABLE_EXACT = {"MS"}
FSD_INJECTION_BOOST = {"basic": 25, "standard": 50, "premium": 100}


def is_scoopable(star_class):
    star_class = str(star_class or "").strip().upper()
    if not star_class:
        return False
    if star_class in SCOOPABLE_EXACT:
        return True
    if star_class in NON_SCOOPABLE_EXACT:
        return False
    return star_class[0] in SCOOPABLE_PRIMARY


def route_ahead(entries, current_system, current_star_class=None):
    """Return the current system plus remaining NavRoute entries.

    Elite normally retains the whole route, but some journal versions expose
    only upcoming hops. In that case the known current star is prepended.
    """
    route = [
        {
            "system": row.get("StarSystem"),
            "star_class": row.get("StarClass"),
            "scoopable": is_scoopable(row.get("StarClass")),
        }
        for row in (entries or [])
        if isinstance(row, dict) and row.get("StarSystem")
    ]
    if not route or not current_system:
        return []
    current_key = str(current_system).casefold()
    index = next(
        (idx for idx, row in enumerate(route) if str(row["system"]).casefold() == current_key),
        None,
    )
    if index is not None:
        return route[index:]
    return [{
        "system": current_system,
        "star_class": current_star_class,
        "scoopable": is_scoopable(current_star_class),
    }] + route


def _best_injection(synthesis):
    for tier in ("premium", "standard", "basic"):
        if synthesis and int(synthesis.get(tier) or 0) > 0:
            return tier, int(synthesis[tier])
    return None


def _advisory(level, code, say):
    return {"level": level, "code": code, "say": say}


def fuel_advisory(ahead, fuel_main, fuel_capacity, fuel_per_jump, synthesis=None):
    """Return the most important route/fuel advisory, or ``None``."""
    ahead = list(ahead or [])
    current = ahead[0] if ahead else None
    upcoming = ahead[1:]
    per_jump = fuel_per_jump if fuel_per_jump and fuel_per_jump > 0 else None
    jumps_left = int(fuel_main / per_jump) if per_jump and fuel_main is not None else None

    if upcoming:
        next_scoop = next((idx + 1 for idx, row in enumerate(upcoming) if row["scoopable"]), None)
        dry = 0
        for row in upcoming:
            if row["scoopable"]:
                break
            dry += 1

        injection = _best_injection(synthesis)
        injection_text = (
            f" {injection[0].title()} F S D injection is ready, providing a "
            f"{FSD_INJECTION_BOOST[injection[0]]} percent range boost."
            if injection else ""
        )
        if jumps_left is not None:
            if next_scoop is None and jumps_left < len(upcoming):
                return _advisory(
                    "critical", "no_fuel_on_route",
                    f"Warning. No scoopable star remains on this route. Fuel lasts about {jumps_left} jumps."
                    + injection_text,
                )
            if next_scoop is not None and next_scoop > jumps_left:
                if current and current["scoopable"]:
                    return _advisory(
                        "critical", "scoop_now",
                        f"Scoop now. The next fuel star is {next_scoop} jumps away, and the tank lasts about {jumps_left}.",
                    )
                return _advisory(
                    "critical", "strand_risk",
                    f"Warning. The next fuel star is {next_scoop} jumps away, but fuel lasts about {jumps_left}. Consider replotting."
                    + injection_text,
                )

        if current and current["scoopable"] and dry >= 2:
            return _advisory(
                "warn", "dry_stretch",
                f"Top off before leaving. The next {dry} jumps have no scoopable star.",
            )

    if fuel_main is not None and fuel_capacity:
        fraction = fuel_main / fuel_capacity
        if fraction < 0.25:
            return _advisory("warn", "low_fuel", f"Low fuel. {round(fraction * 100)} percent.")
    return None
