"""Pure helpers for low-noise, route-aware flight voice advisories."""


SCOOPABLE_PRIMARY = set("OBAFGKM")
SCOOPABLE_EXACT = {"TTS", "AEBE"}
NON_SCOOPABLE_EXACT = {"MS"}
FSD_INJECTION_BOOST = {"basic": 25, "standard": 50, "premium": 100}


def is_scoopable(star_class):
    """Return True/False for a known arrival star, or None when unknown."""
    star_class = str(star_class or "").strip().upper()
    if not star_class:
        return None
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
    fuel_fraction = (
        fuel_main / fuel_capacity
        if fuel_main is not None and fuel_capacity and fuel_capacity > 0 else None
    )

    if upcoming:
        next_scoop = next(
            (idx + 1 for idx, row in enumerate(upcoming) if row["scoopable"] is True),
            None,
        )
        unknown_before_scoop = any(
            row.get("scoopable") is None
            for row in upcoming[:next_scoop - 1 if next_scoop is not None else len(upcoming)]
        )
        dry = 0
        for row in upcoming:
            # Only a confirmed non-scoopable arrival star belongs in the dry
            # count. Missing NavRoute StarClass data is uncertainty, not "no".
            if row.get("scoopable") is not False:
                break
            dry += 1

        injection = _best_injection(synthesis)
        injection_text = (
            f" {injection[0].title()} F S D injection is ready, providing a "
            f"{FSD_INJECTION_BOOST[injection[0]]} percent range boost."
            if injection else ""
        )
        if jumps_left is not None:
            if next_scoop is None and not unknown_before_scoop and jumps_left < len(upcoming):
                return _advisory(
                    "critical", "no_fuel_on_route",
                    (
                        f"Warning. No scoopable arrival star is recorded on the remaining route. Fuel lasts about {jumps_left} jumps.{injection_text}",
                        f"Route fuel critical. The plotted course has no remaining scoopable primary, and reserve is approximately {jumps_left} jumps.{injection_text}",
                        f"No scoopable arrival primary lies ahead. Current fuel endurance is about {jumps_left} jumps.{injection_text}",
                        f"Fuel planning alert. The route records no arrival-star refuelling point, with roughly {jumps_left} jumps available.{injection_text}",
                    ),
                )
            if next_scoop is not None and next_scoop > jumps_left:
                if current and current["scoopable"]:
                    return _advisory(
                        "critical", "scoop_now",
                        (
                            f"Scoop now. The next confirmed scoopable arrival is {next_scoop} jumps away, and the tank lasts about {jumps_left}.",
                            f"Take fuel before departure. Endurance is about {jumps_left} jumps; the next confirmed scoopable primary is {next_scoop} away.",
                            f"This is the safe refuelling point. The next recorded fuel star is {next_scoop} jumps ahead against {jumps_left} jumps of reserve.",
                            f"Fuel opportunity now. We have roughly {jumps_left} jumps in the tank and {next_scoop} to the next confirmed scoopable arrival.",
                        ),
                    )
                return _advisory(
                    "critical", "strand_risk",
                    (
                        f"Warning. The next confirmed scoopable arrival is {next_scoop} jumps away, but fuel lasts about {jumps_left}. Consider replotting.{injection_text}",
                        f"Stranding risk. Fuel endurance is {jumps_left} jumps while the next confirmed scoopable primary is {next_scoop} away.{injection_text}",
                        f"The route exceeds our current fuel reserve: {next_scoop} jumps to a recorded fuel star, approximately {jumps_left} available.{injection_text}",
                        f"Navigation and fuel disagree. Replot or refuel; the next confirmed fuel star is {next_scoop} jumps away with only {jumps_left} jumps in reserve.{injection_text}",
                    ),
                )

        # A known dry prefix alone is not a reason to nag a well-fuelled ship.
        # Speak only when endurance is close to that prefix, or when endurance
        # is not yet learned and the tank is already meaningfully depleted.
        dry_needs_attention = (
            (jumps_left is not None and jumps_left <= dry + 2)
            or (jumps_left is None and fuel_fraction is not None and fuel_fraction < 0.75)
        )
        if current and current["scoopable"] is True and dry >= 2 and dry_needs_attention:
            return _advisory(
                "warn", "dry_stretch",
                (
                    f"Top off if needed. The next {dry} plotted arrival stars are non-scoopable.",
                    f"Refuelling advised here. A confirmed dry arrival stretch of {dry} jumps follows.",
                    f"This is the last confirmed arrival-star fuel opportunity before {dry} non-scoopable primaries.",
                    f"The next {dry} plotted arrival stars cannot be scooped. Consider filling the tank now.",
                ),
            )

    if fuel_fraction is not None:
        if fuel_fraction < 0.25:
            percent = round(fuel_fraction * 100)
            return _advisory("warn", "low_fuel", (
                f"Low fuel. {percent} percent.",
                f"Main tank reserve has fallen to {percent} percent.",
                f"Fuel warning. Only {percent} percent remains in the main tank.",
                f"Current fuel reserve is {percent} percent. Replenishment advised.",
            ))
    return None
