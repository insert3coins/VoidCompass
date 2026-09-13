"""Route-aware arrival-star helpers used by exploration fieldcraft."""


SCOOPABLE_PRIMARY = set("OBAFGKM")
SCOOPABLE_EXACT = {"TTS", "AEBE"}
NON_SCOOPABLE_EXACT = {"MS"}


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
    """Return the current system plus remaining NavRoute entries."""
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
        (
            idx for idx, row in enumerate(route)
            if str(row["system"]).casefold() == current_key
        ),
        None,
    )
    if index is not None:
        return route[index:]
    return [{
        "system": current_system,
        "star_class": current_star_class,
        "scoopable": is_scoopable(current_star_class),
    }] + route
