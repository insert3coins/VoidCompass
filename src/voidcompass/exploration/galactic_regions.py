"""Offline Elite Dangerous Codex region lookup and display geometry.

The underlying 42-region raster comes from Ben Peddell's MIT-licensed
EliteDangerousRegionMap project. VoidCompass keeps the complete pinned raster
for exact coordinate lookup, and hands the same raster to the HTML Galactic
Atlas, which draws the borders from it directly.
"""

from __future__ import annotations

import base64
from functools import lru_cache
import gzip
import json

from voidcompass.exploration.galactic_region_data import COMPRESSED_REGION_MAP_B64


X0 = -49985.0
Z0 = -24105.0
SOURCE_SIZE = 2048
SOURCE_SCALE = 4096.0 / 83.0


@lru_cache(maxsize=1)
def _dataset():
    packed = base64.b64decode(COMPRESSED_REGION_MAP_B64)
    payload = json.loads(gzip.decompress(packed).decode("utf-8"))
    return tuple(payload["regions"]), tuple(
        tuple((int(length), int(region)) for length, region in row)
        for row in payload["regionmap"]
    )


def region_names():
    """Return the 42 Universal Cartographics region names in game order."""
    return _dataset()[0][1:]


def _region_at_pixel(px, pz):
    if px < 0 or pz < 0 or px >= SOURCE_SIZE or pz >= SOURCE_SIZE:
        return 0
    _names, rows = _dataset()
    cursor = 0
    for length, region_id in rows[pz]:
        cursor += length
        if px < cursor:
            return region_id
    return 0


def find_region(x, y=0.0, z=0.0):
    """Return ``(region_id, name)`` for an Elite ``StarPos`` coordinate."""
    del y  # Codex regions are divisions of the galactic X/Z plane.
    try:
        pixel_x = (float(x) - X0) * 83.0 / 4096.0
        pixel_z = (float(z) - Z0) * 83.0 / 4096.0
    except (TypeError, ValueError):
        return None
    if not (0.0 <= pixel_x < SOURCE_SIZE and 0.0 <= pixel_z < SOURCE_SIZE):
        return None
    px = int(pixel_x)
    pz = int(pixel_z)
    region_id = _region_at_pixel(px, pz)
    names, _rows = _dataset()
    if not region_id or region_id >= len(names):
        return None
    return region_id, names[region_id]


def _pixel_world(px, pz):
    return X0 + px * SOURCE_SCALE, Z0 + pz * SOURCE_SCALE


def region_raster():
    """The complete region raster for the HTML atlas, as it is stored.

    Each of the 2048 rows (south to north, from Z0) is a flat list of
    ``length, region`` runs across X from X0; region 0 is outside every
    region. The atlas draws borders and answers "which region is this?" from
    it at the raster's own resolution (about 49 ly), so nothing is traced
    or simplified.
    """
    names, rows = _dataset()
    return {
        "x0": X0, "z0": Z0, "size": SOURCE_SIZE, "scale": SOURCE_SCALE,
        "names": list(names[1:]),
        "rows": [[value for run in row for value in run] for row in rows],
    }


@lru_cache(maxsize=6)
def _sampled_grid(step):
    """Sample the source raster into a square grid of region identifiers."""
    size = SOURCE_SIZE // step
    _names, rows = _dataset()
    grid = []
    for cell_z in range(size):
        pz = min(SOURCE_SIZE - 1, cell_z * step + step // 2)
        expanded = []
        for length, region_id in rows[pz]:
            expanded.extend([region_id] * length)
        grid.append([expanded[min(SOURCE_SIZE - 1, cell_x * step + step // 2)] for cell_x in range(size)])
    return size, grid


@lru_cache(maxsize=2)
def region_labels(sample_step=8):
    """Where each region's name reads best: the point deepest inside it.

    A region's average position can fall outside a curved one (an arm, say),
    so each label goes where a chamfer distance transform finds the cell
    farthest from any other region. ``cells`` is the region's size in sampled
    cells, which the atlas uses to rank and scale its labels.
    """
    step = max(4, min(64, int(sample_step)))
    names, _rows = _dataset()
    size, grid = _sampled_grid(step)
    far = float(size * 4)
    distance = [[far] * size for _ in range(size)]
    for z in range(size):
        row = grid[z]
        for x in range(size):
            here = row[x]
            if (x == 0 or z == 0 or x == size - 1 or z == size - 1
                    or row[x - 1] != here or row[x + 1] != here
                    or grid[z - 1][x] != here or grid[z + 1][x] != here):
                distance[z][x] = 0.0
    diagonal = 1.4142
    for z in range(1, size):
        for x in range(1, size - 1):
            value = distance[z][x]
            if value:
                distance[z][x] = min(value, distance[z][x - 1] + 1, distance[z - 1][x] + 1,
                                     distance[z - 1][x - 1] + diagonal, distance[z - 1][x + 1] + diagonal)
    for z in range(size - 2, -1, -1):
        for x in range(size - 2, 0, -1):
            value = distance[z][x]
            if value:
                distance[z][x] = min(value, distance[z][x + 1] + 1, distance[z + 1][x] + 1,
                                     distance[z + 1][x + 1] + diagonal, distance[z + 1][x - 1] + diagonal)
    best = {}
    cells = {}
    for z in range(size):
        for x in range(size):
            region_id = grid[z][x]
            if not region_id:
                continue
            cells[region_id] = cells.get(region_id, 0) + 1
            if distance[z][x] > best.get(region_id, (-1.0, 0, 0))[0]:
                best[region_id] = (distance[z][x], x, z)
    labels = []
    for region_id in range(1, len(names)):
        if region_id not in best:
            continue
        _depth, x, z = best[region_id]
        world_x, world_z = _pixel_world(x * step + step / 2, z * step + step / 2)
        labels.append({"id": region_id, "name": names[region_id],
                       "position": [round(world_x, 1), 0.0, round(world_z, 1)],
                       "cells": cells[region_id]})
    return tuple(labels)
