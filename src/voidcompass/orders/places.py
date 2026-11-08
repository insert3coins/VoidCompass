"""Places the crew can send you (5.7.7): the far landmarks for the
Watcher's long orders, and the nearest region you've never been to."""

from __future__ import annotations

import math
from functools import lru_cache

from voidcompass.exploration import galactic_regions

# id: (system, coords, how the Watcher thinks of it)
PLACES = {
    "sag_a": ("Sagittarius A*", (25.21875, -20.90625, 25899.96875), "the black hole at the middle of everything"),
    "colonia": ("Colonia", (-9530.5, -910.28125, 19808.125), "the colony out past the long dark"),
    "beagle_point": ("Beagle Point", (-1111.5625, -134.21875, 65269.75), "the far edge, where the stars run out"),
    "sol": ("Sol", (0.0, 0.0, 0.0), "the star your kind started from"),
    "alpha_centauri": ("Alpha Centauri", (3.03125, -0.09375, 3.15625), "the long, long supercruise to Hutton"),
}
REGION_STEP = 8


def distance(a, b):
    try:
        return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def _region_cells():
    """Region id -> the centres (x, z) of its cells on a coarse grid."""
    size, grid = galactic_regions._sampled_grid(REGION_STEP)
    scale = galactic_regions.SOURCE_SCALE * REGION_STEP
    cells = {}
    for cell_z, row in enumerate(grid):
        z = galactic_regions.Z0 + (cell_z + .5) * scale
        for cell_x, region in enumerate(row):
            if region:
                cells.setdefault(region, []).append((galactic_regions.X0 + (cell_x + .5) * scale, z))
    return cells


def nearest_unvisited_region(here, visited, max_ly=None):
    """The closest region you've never entered: {id, name, ly, coords}, or None.
    ``visited`` holds region ids. Distances are across the galactic plane,
    to about a region cell (400 ly), so they're said as "about"."""
    if not here:
        return None
    try:
        hx, hy, hz = (float(value) for value in here)
    except (TypeError, ValueError):
        return None
    names = galactic_regions.region_names()
    best = None
    for region, cells in _region_cells().items():
        if region in visited:
            continue
        for x, z in cells:
            gap = math.hypot(x - hx, z - hz)
            if best is None or gap < best[0]:
                best = (gap, region, (x, hy, z))
    if best is None or (max_ly is not None and best[0] > max_ly):
        return None
    gap, region, coords = best
    name = names[region - 1] if 0 < region <= len(names) else f"Region {region}"
    return {"id": region, "name": name, "ly": round(gap), "coords": [round(value, 1) for value in coords]}


def region_of(coords):
    found = galactic_regions.find_region(*coords) if coords else None
    return found if found else (None, "")
