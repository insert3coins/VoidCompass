"""Offline Elite Dangerous Codex region lookup and display geometry.

The underlying 42-region raster comes from Ben Peddell's MIT-licensed
EliteDangerousRegionMap project. VoidCompass keeps the complete pinned raster
for exact coordinate lookup and derives a lighter contour set for Tk drawing.
"""

from __future__ import annotations

import base64
from functools import lru_cache
import gzip
import json

from galactic_region_data import COMPRESSED_REGION_MAP_B64


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


def _merge_boundary_runs(entries, vertical, step):
    """Merge adjacent sampled cell edges into inexpensive world-space lines."""
    grouped = {}
    for fixed, moving, pair in entries:
        grouped.setdefault((fixed, pair), []).append(moving)
    segments = []
    for (fixed, pair), values in grouped.items():
        values.sort()
        start = previous = values[0]
        for value in values[1:] + [None]:
            if value is not None and value == previous + step:
                previous = value
                continue
            if vertical:
                x1, z1 = _pixel_world(fixed, start)
                x2, z2 = _pixel_world(fixed, previous + step)
            else:
                x1, z1 = _pixel_world(start, fixed)
                x2, z2 = _pixel_world(previous + step, fixed)
            segments.append((x1, z1, x2, z2, pair[0], pair[1]))
            if value is not None:
                start = value
                previous = value
    return segments


@lru_cache(maxsize=6)
def _sampled_grid(step):
    """Sample the source raster into a square grid of region identifiers."""
    size = SOURCE_SIZE // step
    _names, rows = _dataset()
    grid = []
    cells_by_region = {}
    for cell_z in range(size):
        pz = min(SOURCE_SIZE - 1, cell_z * step + step // 2)
        expanded = []
        for length, region_id in rows[pz]:
            expanded.extend([region_id] * length)
        sampled = []
        for cell_x in range(size):
            px = min(SOURCE_SIZE - 1, cell_x * step + step // 2)
            region_id = expanded[px]
            sampled.append(region_id)
            if region_id:
                cells_by_region.setdefault(region_id, []).append((px, pz))
        grid.append(sampled)
    return size, grid, cells_by_region


@lru_cache(maxsize=4)
def region_fills(sample_step=32):
    """Return merged world-space rectangles covering each region's interior.

    :func:`region_geometry` describes where regions meet; a filled map instead
    needs the area between those boundaries. Sampled cells are run-length
    encoded per row, then extended downwards while the row beneath repeats the
    same run, so the 42 regions become a few hundred rectangles rather than
    tens of thousands of individual cells.
    """
    step = max(4, min(128, int(sample_step)))
    size, grid, _cells = _sampled_grid(step)
    rectangles = []
    open_runs = {}
    # One extra pass past the final row closes every run still being extended.
    for cell_z in range(size + 1):
        row = grid[cell_z] if cell_z < size else []
        runs = set()
        start = 0
        while start < len(row):
            region_id = row[start]
            end = start + 1
            while end < len(row) and row[end] == region_id:
                end += 1
            if region_id:
                runs.add((start, end, region_id))
            start = end
        for key in tuple(open_runs):
            if key in runs:
                continue
            first_z = open_runs.pop(key)
            left, right, region_id = key
            x1, z1 = _pixel_world(left * step, first_z * step)
            x2, z2 = _pixel_world(right * step, cell_z * step)
            rectangles.append((x1, z1, x2, z2, region_id))
        for key in runs:
            open_runs.setdefault(key, cell_z)
    return tuple(rectangles)


@lru_cache(maxsize=4)
def region_geometry(sample_step=8):
    """Return bounded region contours and label anchors for map rendering.

    Exact coordinate lookup continues to use the complete source raster. The
    display contours sample it at roughly 395 ly with the default step, which
    preserves all 42 regions while keeping interactive redraws lightweight.
    """
    step = max(4, min(128, int(sample_step)))
    names, _rows = _dataset()
    size, grid, cells_by_region = _sampled_grid(step)

    vertical = []
    horizontal = []
    for cell_z, row in enumerate(grid):
        pz = cell_z * step
        for cell_x, region_id in enumerate(row):
            px = cell_x * step
            right = row[cell_x + 1] if cell_x + 1 < size else 0
            above = grid[cell_z + 1][cell_x] if cell_z + 1 < size else 0
            if right != region_id and (right or region_id):
                vertical.append((px + step, pz, tuple(sorted((region_id, right)))))
            if above != region_id and (above or region_id):
                horizontal.append((pz + step, px, tuple(sorted((region_id, above)))))

    segments = _merge_boundary_runs(vertical, True, step)
    segments.extend(_merge_boundary_runs(horizontal, False, step))
    labels = []
    for region_id in range(1, len(names)):
        cells = cells_by_region.get(region_id) or []
        if not cells:
            continue
        mean_x = sum(cell[0] for cell in cells) / len(cells)
        mean_z = sum(cell[1] for cell in cells) / len(cells)
        anchor_x, anchor_z = min(
            cells,
            key=lambda cell: (cell[0] - mean_x) ** 2 + (cell[1] - mean_z) ** 2,
        )
        world_x, world_z = _pixel_world(anchor_x, anchor_z)
        labels.append({
            "id": region_id, "name": names[region_id],
            "position": (world_x, 0.0, world_z), "cells": len(cells),
        })
    return tuple(segments), tuple(labels)
