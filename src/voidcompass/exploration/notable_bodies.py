"""Shared notable-body classification used by the persistent Survey Status HUD."""

from voidcompass.core import themes
_NOTABLE_PLANET_CLASSES = {"earthlike body", "water world", "ammonia world"}
DEFAULT_MIN_VALUE = 50_000
# Rare worlds (5.5.3.1): notable whatever they pay, and listed first in
# Survey's NOTABLE, the rarest at the top. (rarity, label)
_RARE_PLANET_CLASSES = {
    "helium gas giant": (3, "HELIUM GAS GIANT"),
    "helium rich gas giant": (2, "HELIUM-RICH GAS GIANT"),
    "water giant": (2, "WATER GIANT"),
}
# Earth-likes, water and ammonia worlds are already notable and keep their
# order by value (5.5.3).
# The game names a green gas giant only in its Codex entry (Name
# "$Codex_Ent_Green_...", EntryID 12001..12009 ending 02); the dashboard
# pairs that entry with the gas giant scanned in the same moment.
GREEN_GIANT = (4, "GREEN GAS GIANT")


def is_green_giant_codex(raw):
    """A Codex entry for a green gas giant."""
    if not isinstance(raw, dict) or raw.get("event") not in (None, "CodexEntry"):
        return False
    name = str(raw.get("Name") or "")
    if name.startswith("$Codex_Ent_Green_"):
        return True
    try:
        entry = int(raw.get("EntryID") or 0)
    except (TypeError, ValueError):
        return False
    return 1200102 <= entry <= 1200902 and entry % 100 == 2


def rarity(item):
    """(rarity, label) for a rare world, else (0, "")."""
    if not isinstance(item, dict) or item.get("is_star"):
        return 0, ""
    if item.get("green_giant"):
        return GREEN_GIANT
    return _RARE_PLANET_CLASSES.get(str(item.get("planet_class") or "").casefold().replace("-", " "), (0, ""))


def _is_interesting_body(item, min_value):
    if item.get("is_star"):
        return False
    # Biology is already a first-class Survey Operations target. Keep the
    # notable classification for an independent mapping/value reason so a bio
    # row is not redundantly labelled NOTABLE BODY merely for having signals.
    if item.get("terraformable") or rarity(item)[0]:
        return True
    if (item.get("planet_class") or "").lower() in _NOTABLE_PLANET_CLASSES:
        return True
    best_value = max(item.get("reward") or 0, item.get("dss_reward") or 0)
    return best_value >= min_value


def _fmt_credits(value):
    try:
        value = int(value or 0)
    except Exception:
        return "--"
    for suffix, divisor in (("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
        if value >= divisor:
            return f"{value / divisor:.1f}{suffix}"
    return f"{value:,}"


def build_notable_body_rows(scan_items, min_value=DEFAULT_MIN_VALUE, palette=None):
    """Return formatted notable bodies for the persistent Survey Status HUD."""
    palette = palette or themes.ACTIVE_PALETTE
    bodies = []
    for item in (scan_items or []):
        if not _is_interesting_body(item, min_value):
            continue
        icons = "".join(icon for icon in (item.get("icons") or []) if icon != "★")
        reward = item.get("reward") or 0
        dss_reward = item.get("dss_reward") or 0
        bio_count = item.get("bio_count") or 0
        if item.get("dss_complete") or dss_reward <= reward:
            value_line = f"{_fmt_credits(reward)} CR"
        else:
            value_line = f"{_fmt_credits(reward)} CR  ·  DSS {_fmt_credits(dss_reward)} CR"
        if bio_count:
            value_line += f"  ·  BIO {bio_count}"
        rare, rare_label = rarity(item)
        if rare:
            value_line = f"{rare_label}  ·  {value_line}"
        bodies.append({
            "body_id": item.get("body_id"),
            "name": item.get("name") or "Body",
            "icons": icons,
            "planet_class": item.get("planet_class") or "",
            "terraformable": bool(item.get("terraformable")),
            "name_color": palette["accent"] if bio_count else palette["orange"],
            "value_line": value_line,
            # What mapping it is worth: Survey lists notable bodies by it.
            "value": max(reward, dss_reward),
            # Rare worlds come first in NOTABLE, the rarest at the top.
            "rarity": rare,
            "rare_label": rare_label,
            "green_giant": bool(item.get("green_giant")),
            "value_color": palette["yellow"] if max(reward, dss_reward) >= min_value else palette["dim"],
        })
    return bodies
