"""Where rigs go on a deposit, worked out on a flat plane in metres east and
north (over a deposit a few hundred metres across that is accurate to far
less than the Rhino's width).

- **Tracing:** drive the deposit's edge with the trace key down; the loop
  closes itself when you come back near the start, or with the key again.
- **Packing:** up to six rigs inside what you drove, each at least the rig
  spacing from the next. Lattices at several turns and shifts, a greedy fill
  for odd shapes, and an exact pass that sweeps a fine grid from every side
  and swaps one rig for two where it can. The most rigs wins; then the layout
  furthest in from the edge.
- **The radar:** can the next rig go where you are, and if not, the nearest
  spot it can (exactly: on a ring, where two rings cross, or on the edge).
- **The planning circle:** 4.5 km round a spot. Rig and drive inside it and
  no rig is ever the 5 km away that the game takes it back at.
"""
from __future__ import annotations

import math

from voidcompass.overlays.rig_tracker import local_offset, surface_distance_m

SPACING_M = 78.0
MAX_PINS = 6
FIT_MOST = 12

TRACE_STEP_M = 5.0
TRACE_CLOSE_M = 15.0
TRACE_CLOSE_MAX_M = 60.0
# Status.json moves your position on in steps of about this much, so on a big
# body "back within 15 m" can be stepped straight over.
STATUS_STEP_DEG = 0.0005
TRACE_MIN_POINTS = 10
TRACE_MIN_PATH_M = 60.0
TRACE_MAX_SPAN_M = 3000.0
ON_EDGE_M = 1.0
MAX_CORNERS = 48
EXACT_CELLS = 2500
EXACT_CORNERS = 120
_TURNS = tuple(range(0, 60, 10))
_SHIFTS = 4

BAND_M = 2.0
_EPS = 1e-6

CIRCLE_M = 4500.0
# A plan is found again from this close to its middle.
PLAN_NEAR_M = 1500.0
# A new trace this close to a kept plan's middle replaces it.
PLAN_SAME_M = 60.0


# -- the polygon ----------------------------------------------------------------

def inside(polygon, x, y):
    hit = False
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def edge_distance(polygon, x, y):
    best = float("inf")
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        dx, dy = x2 - x1, y2 - y1
        length = dx * dx + dy * dy
        t = 0.0 if length == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / length))
        best = min(best, math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)))
    return best


def area(polygon):
    total = 0.0
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def usable(polygon, x, y):
    """Inside, or on the driven line to within a metre."""
    return inside(polygon, x, y) or edge_distance(polygon, x, y) <= ON_EDGE_M


def _thin(polygon, corners):
    if len(polygon) <= corners:
        return list(polygon)
    step = len(polygon) / float(corners)
    return [polygon[int(i * step)] for i in range(corners)]


def _far_enough(point, others, spacing):
    limit = (spacing - _EPS) ** 2
    return all((point[0] - x) ** 2 + (point[1] - y) ** 2 >= limit for x, y in others)


# -- packing ----------------------------------------------------------------------

def _lattice(polygon, spacing, turn_deg, shift_x, shift_y):
    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
    cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    reach = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) / 2.0 + spacing
    cos_t, sin_t = math.cos(math.radians(turn_deg)), math.sin(math.radians(turn_deg))
    row_step = spacing * math.sqrt(3) / 2.0
    rows, cols = int(reach / row_step) + 2, int(reach / spacing) + 2
    found = []
    for r in range(-rows, rows + 1):
        for c in range(-cols, cols + 1):
            u = c * spacing + (spacing / 2.0 if r % 2 else 0.0) + shift_x
            v = r * row_step + shift_y
            x, y = cx + u * cos_t - v * sin_t, cy + u * sin_t + v * cos_t
            if usable(polygon, x, y):
                found.append((x, y))
    return found


def _choose(points, polygon, want):
    """The tightest ``want`` of a lattice's points, sitting furthest in."""
    if len(points) <= want:
        return list(points)
    best = None
    for anchor in points:
        group = sorted(points, key=lambda p: (p[0] - anchor[0]) ** 2 + (p[1] - anchor[1]) ** 2)[:want]
        spread = max(math.hypot(p[0] - anchor[0], p[1] - anchor[1]) for p in group)
        margin = min(edge_distance(polygon, p[0], p[1]) for p in group)
        score = spread - margin * .5
        if best is None or score < best[0]:
            best = (score, group)
    return best[1]


def _greedy(polygon, spacing, want):
    """Deepest point first, then the next deepest a spacing from the rest."""
    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
    step = max(2.0, spacing / 8.0)
    candidates = []
    y = min(ys)
    while y <= max(ys):
        x = min(xs)
        while x <= max(xs):
            if usable(polygon, x, y):
                candidates.append((edge_distance(polygon, x, y) if inside(polygon, x, y) else 0.0, x, y))
            x += step
        y += step
    candidates.sort(reverse=True)
    taken = []
    for _depth, x, y in candidates:
        if _far_enough((x, y), taken, spacing):
            taken.append((x, y))
            if len(taken) >= want:
                break
    return taken


_SWEEPS = (
    lambda p: (p[0], p[1]), lambda p: (p[1], p[0]),
    lambda p: (-p[0], p[1]), lambda p: (p[1], -p[0]),
    lambda p: (p[0], -p[1]), lambda p: (-p[1], p[0]),
    lambda p: (-p[0], -p[1]), lambda p: (-p[1], -p[0]),
)


def pack_exact(polygon, spacing=SPACING_M, most=MAX_PINS):
    """The most rigs that fit, every one tested against the line as driven.
    Lattices miss tight shapes (160 by 80 m takes two rows of three)."""
    full = [(float(x), float(y)) for x, y in polygon or ()]
    if len(full) < 3 or area(full) < 1.0 or spacing <= 0:
        return []
    thin = _thin(full, EXACT_CORNERS)
    xs, ys = [p[0] for p in full], [p[1] for p in full]
    step = max(spacing / 6.0, math.sqrt(max((max(xs) - min(xs)) * (max(ys) - min(ys)), 1.0) / EXACT_CELLS))
    candidates = list(full[::max(1, len(full) // EXACT_CORNERS)])
    i = 0
    while min(xs) + i * step <= max(xs) + 1e-9:
        j = 0
        while min(ys) + j * step <= max(ys) + 1e-9:
            candidates.append((min(xs) + i * step, min(ys) + j * step))
            j += 1
        i += 1
    candidates = [c for c in candidates if usable(thin, c[0], c[1])]
    seen = {}

    def fits(point):
        if point not in seen:
            seen[point] = usable(full, point[0], point[1])
        return seen[point]

    def sweep(key):
        taken = []
        for point in sorted(candidates, key=key):
            if len(taken) >= most:
                break
            if _far_enough(point, taken, spacing) and fits(point):
                taken.append(point)
        return taken

    def margin(points):
        return min(edge_distance(full, x, y) for x, y in points) if points else 0.0

    best = max((sweep(key) for key in _SWEEPS), key=lambda points: (len(points), margin(points)))
    depth = sorted(candidates, key=lambda c: -edge_distance(thin, c[0], c[1]))[:400]
    for _ in range(most):
        if len(best) >= most:
            break
        grown = next((best + [point] for point in depth if _far_enough(point, best, spacing) and fits(point)), None)
        if grown is None:
            for k in range(len(best)):
                rest = best[:k] + best[k + 1:]
                free = [c for c in depth if _far_enough(c, rest, spacing) and fits(c)]
                pair = next(((a, b) for n, a in enumerate(free) for b in free[n + 1:] if _far_enough(a, [b], spacing)), None)
                if pair:
                    grown = rest + list(pair)
                    break
        if grown is None:
            break
        best = grown
    return best[:most]


def plan(polygon, spacing=SPACING_M, most=MAX_PINS):
    """Up to ``most`` rig spots inside the polygon, each ``spacing`` apart."""
    polygon = [(float(x), float(y)) for x, y in polygon or ()]
    if len(polygon) < 3 or area(polygon) < 1.0 or spacing <= 0:
        return []
    driven = list(polygon)
    polygon = _thin(polygon, MAX_CORNERS)
    best = None

    def consider(points):
        nonlocal best
        if points:
            key = (len(points), min(edge_distance(polygon, x, y) for x, y in points))
            if best is None or key > best[0]:
                best = (key, points)

    for turn in _TURNS:
        for i in range(_SHIFTS):
            for j in range(_SHIFTS):
                consider(_choose(_lattice(polygon, spacing, turn, spacing * i / _SHIFTS,
                                          spacing * math.sqrt(3) / 2.0 * j / _SHIFTS), polygon, most))
    consider(_greedy(polygon, spacing, most))
    exact = pack_exact(driven, spacing, most)
    if exact and (best is None or len(exact) > best[0][0]):
        best = ((len(exact), 0.0), exact)
    if best is None:
        xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
        middle = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
        return [middle] if usable(polygon, *middle) else [polygon[0]]
    return best[1]


def drive_order(pins, start=(0.0, 0.0)):
    """Nearest first, then nearest to that."""
    left, here, order = list(pins), start, []
    while left:
        nearest = min(left, key=lambda p: math.hypot(p[0] - here[0], p[1] - here[1]))
        left.remove(nearest)
        order.append(nearest)
        here = nearest
    return order


def _from_local(origin, east, north, radius_m):
    from voidcompass.overlays.rig_tracker import destination
    distance = math.hypot(east, north)
    if not distance:
        return float(origin[0]), float(origin[1])
    return destination(origin[0], origin[1], math.degrees(math.atan2(east, north)) % 360.0, distance, radius_m)


class Trace:
    """A deposit's edge as the Rhino drives it, in metres from where it began."""

    def __init__(self, lat, lon, radius_m):
        self.origin = (float(lat), float(lon))
        self.radius_m = float(radius_m)
        self.points = [(0.0, 0.0)]
        self.path_m = 0.0
        self.close_m = min(TRACE_CLOSE_MAX_M, max(TRACE_CLOSE_M, 1.5 * math.radians(STATUS_STEP_DEG) * self.radius_m))
        self.closed = False
        self.too_big = False

    def add(self, lat, lon):
        """One position; True when it closed the loop."""
        if self.closed:
            return False
        x, y = local_offset(self.origin, (lat, lon), self.radius_m)
        last = self.points[-1]
        step = math.hypot(x - last[0], y - last[1])
        if step < TRACE_STEP_M:
            return False
        if math.hypot(x, y) > TRACE_MAX_SPAN_M:
            self.too_big = True
            return False
        self.points.append((x, y))
        self.path_m += step
        if len(self.points) >= TRACE_MIN_POINTS and self.path_m >= TRACE_MIN_PATH_M and math.hypot(x, y) <= self.close_m:
            self.closed = True
            return True
        return False

    def close(self):
        """Closed by hand; False when there isn't a shape yet."""
        if len(self.points) < 3 or area(self.points) < 1.0:
            return False
        self.closed = True
        return True

    def outline(self):
        return [_from_local(self.origin, x, y, self.radius_m) for x, y in self.points]

    def pins(self, spacing=SPACING_M, start=None, most=MAX_PINS):
        """The rig spots as (lat, lon), in driving order from ``start``."""
        here = (0.0, 0.0) if start is None else local_offset(self.origin, start, self.radius_m)
        return [_from_local(self.origin, x, y, self.radius_m) for x, y in drive_order(plan(self.points, spacing, most), here)]


def plan_record(trace, spacing, start=None, now=0.0):
    """What's kept of a closed trace: its edge and pins as lat/lon."""
    outline = trace.outline()
    pins = trace.pins(spacing, start)
    middle = (sum(lat for lat, _lon in outline) / len(outline), sum(lon for _lat, lon in outline) / len(outline))
    return {"outline": [[round(lat, 7), round(lon, 7)] for lat, lon in outline],
            "pins": [[round(lat, 7), round(lon, 7)] for lat, lon in pins],
            "middle": [round(middle[0], 7), round(middle[1], 7)],
            "fits": max(len(pack_exact(trace.points, spacing, FIT_MOST)), len(pins)),
            "spacing": float(spacing), "at": round(float(now), 1)}


def plan_here(plans, lat, lon, radius_m, within_m=PLAN_NEAR_M):
    """The kept plan you're nearest, within reach of its middle."""
    best = None
    for record in plans or ():
        middle = record.get("middle") or ()
        if len(middle) != 2:
            continue
        distance = surface_distance_m(lat, lon, middle[0], middle[1], radius_m)
        if distance <= within_m and (best is None or distance < best[0]):
            best = (distance, record)
    return best[1] if best else None


# -- the radar --------------------------------------------------------------------

def is_legal(point, centres, spacing, polygon=None):
    x, y = point
    if any(math.hypot(x - cx, y - cy) < spacing - _EPS for cx, cy in centres):
        return False
    return polygon is None or usable(polygon, x, y)


def _circles_cross(a, b, radius):
    dx, dy = b[0] - a[0], b[1] - a[1]
    apart = math.hypot(dx, dy)
    if apart == 0 or apart > 2.0 * radius:
        return []
    half = math.sqrt(max(0.0, radius * radius - (apart / 2.0) ** 2))
    mx, my = a[0] + dx / 2.0, a[1] + dy / 2.0
    ox, oy = -dy / apart * half, dx / apart * half
    return [(mx + ox, my + oy), (mx - ox, my - oy)]


def _segment_circle(p, q, centre, radius):
    dx, dy = q[0] - p[0], q[1] - p[1]
    fx, fy = p[0] - centre[0], p[1] - centre[1]
    quad = dx * dx + dy * dy
    if quad == 0:
        return []
    half = fx * dx + fy * dy
    disc = half * half - quad * (fx * fx + fy * fy - radius * radius)
    if disc < 0:
        return []
    root = math.sqrt(disc)
    return [(p[0] + t * dx, p[1] + t * dy) for t in ((-half - root) / quad, (-half + root) / quad) if 0.0 <= t <= 1.0]


def _segment_foot(p, q, point):
    dx, dy = q[0] - p[0], q[1] - p[1]
    quad = dx * dx + dy * dy
    t = 0.0 if quad == 0 else max(0.0, min(1.0, ((point[0] - p[0]) * dx + (point[1] - p[1]) * dy) / quad))
    return p[0] + t * dx, p[1] + t * dy


def nearest_legal(point, centres, spacing, polygon=None):
    """The nearest spot a rig can land, or None when there's no room. The
    nearest legal spot outside the legal ground lies on its boundary: arcs of
    the rings and the traced edge, so those (and where they meet) are tried."""
    point = (float(point[0]), float(point[1]))
    centres = [(float(a), float(b)) for a, b in centres]
    spacing = float(spacing)
    corners = [(float(x), float(y)) for x, y in polygon] if polygon else None
    if is_legal(point, centres, spacing, corners):
        return point
    candidates = []
    for cx, cy in centres:
        apart = math.hypot(point[0] - cx, point[1] - cy)
        if apart == 0:
            candidates += [(cx + spacing * math.sin(math.radians(a)), cy + spacing * math.cos(math.radians(a)))
                           for a in range(0, 360, 45)]
        else:
            candidates.append((cx + (point[0] - cx) * spacing / apart, cy + (point[1] - cy) * spacing / apart))
    for i, first in enumerate(centres):
        for second in centres[i + 1:]:
            candidates += _circles_cross(first, second, spacing)
    if corners:
        for k, p in enumerate(corners):
            q = corners[(k + 1) % len(corners)]
            candidates += [p, _segment_foot(p, q, point)]
            for centre in centres:
                candidates += _segment_circle(p, q, centre, spacing)
    best = None
    for candidate in candidates:
        if is_legal(candidate, centres, spacing, corners):
            apart = math.hypot(candidate[0] - point[0], candidate[1] - point[1])
            if best is None or apart < best[1]:
                best = (candidate, apart)
    return best[0] if best else None


def radar(spot, centres, spacing=SPACING_M, polygon=None, most=MAX_PINS):
    """Can the next rig go at ``spot``? {"state": ok|edge|close|full|none,
    "need_m", "bearing", "legal", "rings": [{"at", "state"}]}. "edge" is
    legal but within BAND_M of a ring."""
    spot = (float(spot[0]), float(spot[1]))
    centres = [(float(a), float(b)) for a, b in centres]
    rings, close, near = [], False, False
    for cx, cy in centres:
        gap = math.hypot(spot[0] - cx, spot[1] - cy) - spacing
        state = "close" if gap < -_EPS else "edge" if gap <= BAND_M + _EPS else "ok"
        close, near = close or state == "close", near or state == "edge"
        rings.append({"at": [round(cx, 1), round(cy, 1)], "state": state})
    out = {"state": "ok", "need_m": 0, "bearing": None, "legal": [round(spot[0], 1), round(spot[1], 1)], "rings": rings}
    if len(centres) >= most:
        out.update(state="full", need_m=None, legal=None)
        return out
    if close or (polygon and not usable(polygon, *spot)):
        found = nearest_legal(spot, centres, spacing, polygon)
        if found is None:
            out.update(state="none", need_m=None, legal=None)
            return out
        east, north = found[0] - spot[0], found[1] - spot[1]
        out.update(state="close", legal=[round(found[0], 1), round(found[1], 1)],
                   need_m=max(1, int(math.ceil(math.hypot(east, north) - 1e-9))),
                   bearing=round(math.degrees(math.atan2(east, north)) % 360.0))
        return out
    if near:
        out["state"] = "edge"
    return out


# -- the planning circle -------------------------------------------------------------

def circle_room(centre, you=(0.0, 0.0)):
    """Metres from you to the circle's edge: positive inside, negative outside."""
    if not centre:
        return None
    return CIRCLE_M - math.hypot(centre[0] - you[0], centre[1] - you[1])
