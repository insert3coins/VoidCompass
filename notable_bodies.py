"""Shared notable-body classification used by the persistent Survey Status HUD."""

from config import COLOR_ACCENT, COLOR_ORANGE


_COL_DIM = "#7a8a98"
_COL_GOLD = "#e8c97a"
_NOTABLE_PLANET_CLASSES = {"earthlike body", "water world", "ammonia world"}
DEFAULT_MIN_VALUE = 50_000


def _is_interesting_body(item, min_value):
    if item.get("is_star"):
        return False
    if (item.get("bio_count") or 0) > 0:
        return True
    if item.get("terraformable"):
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


def build_notable_body_rows(scan_items, min_value=DEFAULT_MIN_VALUE):
    """Return formatted notable bodies for the persistent Survey Status HUD."""
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
        bodies.append({
            "body_id": item.get("body_id"),
            "name": item.get("name") or "Body",
            "icons": icons,
            "planet_class": item.get("planet_class") or "",
            "terraformable": bool(item.get("terraformable")),
            "name_color": COLOR_ACCENT if bio_count else COLOR_ORANGE,
            "value_line": value_line,
            "value_color": _COL_GOLD if max(reward, dss_reward) >= min_value else _COL_DIM,
        })
    return bodies
