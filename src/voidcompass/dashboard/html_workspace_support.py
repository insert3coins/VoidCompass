"""Small validation helpers shared by HTML dashboard workspace controllers."""

import math


def integer(value, default=0):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError, OverflowError):
        return default


def number(value, default=None):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError, OverflowError):
        return default


def text(value, limit=180):
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]
