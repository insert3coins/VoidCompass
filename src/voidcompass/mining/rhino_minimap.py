"""Persistent, renderer-neutral Rhino surface coverage maps.

The coverage behaviour is adapted from Fumlop/EDRhinoSpotter's GPL-3.0
``rs_core.coverage`` and ``rs_core.coverstore`` modules (commit
694bd8b2a531af94e83f423eaab88472708426e5).  Void Compass keeps the same
field semantics but publishes geometry to its HTML overlay rather than using
Pillow/Tk.  See THIRD_PARTY_NOTICES.md.

"Painted" means the Rhino has driven within the estimated scanner radius.  It
does not claim that Elite reported a completed scan; Status.json has no such
evidence.
"""

from __future__ import annotations

import gzip
import json
import math
import os
import re
import time
from pathlib import Path


SCAN_RADIUS_M = 2000.0
VIEW_M = 6000.0
REACH_M = 10000.0
MASK_M_PER_PX = 50.0
STAMP_M = 250.0
GRID_M = 1000.0
DRIVE_OVERLAP_M = 250.0
DRIVE_STEP_M = 2 * SCAN_RADIUS_M - DRIVE_OVERLAP_M
RANGE_RINGS_M = (3000.0, 5000.0)
MASK_PX = int(2 * REACH_M / MASK_M_PER_PX)
SCHEMA_VERSION = 1


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _short_body(body, system=""):
    body = str(body or "").strip()
    system = str(system or "").strip()
    if system and body.casefold().startswith((system + " ").casefold()):
        return body[len(system):].strip()
    return body


def location_index(destination):
    """Return Elite's numbered planetary mining location, when targeted."""
    if isinstance(destination, dict):
        destination = destination.get("Name")
    match = re.search(r"#index=(\d+)", str(destination or ""))
    return int(match.group(1)) if match else None


def drive_radii(border_m):
    """Coverage-driving rings for a known circular location, outside-in."""
    border = max(0.0, float(border_m or 0.0))
    radii = []
    radius = border - SCAN_RADIUS_M
    while radius - SCAN_RADIUS_M > 0:
        radii.append(radius)
        radius -= DRIVE_STEP_M
    radii.append(max(radius, 0.0))
    return radii


def surface_xy(origin, lat, lon, radius_m):
    """Metres east/north of origin using the source minimap's local plane."""
    lat0, lon0 = origin
    lon = lon0 + (float(lon) - lon0 + 180.0) % 360.0 - 180.0
    scale = float(radius_m) * math.pi / 180.0
    return (
        (lon - lon0) * scale * math.cos(math.radians(lat0)),
        (float(lat) - lat0) * scale,
    )


def bearing_deg(x, y, target_x, target_y):
    return math.degrees(math.atan2(target_x - x, target_y - y)) % 360.0


_MATERIAL_CODES = {
    "alexandrite": "A", "bastnasite": "B", "copper": "C",
    "deuterium": "DE", "diamond": "D", "gold": "GO",
    "grandidierite": "G", "haematite": "HA", "helium": "H",
    "helium-3": "HE", "iridium": "I", "jadeite": "J", "lithium": "LI",
    "low temp diamonds": "L", "magnesite": "MA",
    "methanol monohydrate crystals": "ME", "monazite": "M",
    "olivine": "OL", "osmium": "O", "palladium": "PA",
    "periclase dunite": "P", "platinum": "PL", "quartz pyroxenite": "Q",
    "rhodplumsite": "R", "ruby": "RU", "samarium": "SM",
    "sapphire": "SA", "serendibite": "S", "silver": "SI",
    "tantalum": "TA", "thorium": "TH", "thortveitite": "T",
    "titanium": "TI", "tritium": "TR", "uraninite": "U",
    "uranium": "UR", "water": "W",
}


def _material_code(material):
    known = _MATERIAL_CODES.get(str(material or "").strip().casefold())
    if known:
        return known
    words = re.findall(r"[A-Za-z0-9]+", str(material or ""))
    if not words:
        return ""
    if len(words) == 1:
        return words[0][:2].upper()
    return "".join(word[0] for word in words[:3]).upper()


class CoverageMap:
    """One persisted surface map and its compact raster coverage mask."""

    def __init__(self, body, lat, lon, radius_m, *, name=None):
        self.body = str(body)
        self.origin = (float(lat), float(lon))
        self.radius_m = float(radius_m)
        self.name = name
        self.centered = False
        self.border_m = None
        self.drop = self.origin
        self.location = None
        self.stamps = []
        self.version = 0
        self.saved = 0.0
        self._last_xy = None
        self._mask = bytearray(MASK_PX * MASK_PX)
        self._painted_pixels = 0

    def xy(self, lat, lon):
        return surface_xy(self.origin, lat, lon, self.radius_m)

    def reaches(self, lat, lon):
        x, y = self.xy(lat, lon)
        return abs(x) <= REACH_M and abs(y) <= REACH_M

    def launch(self, lat, lon):
        self.drop = (float(lat), float(lon))
        self._last_xy = None

    def anchor(self):
        return (0.0, 0.0) if self.centered else self.xy(*self.drop)

    def _inside(self, x, y):
        return self.border_m is None or math.hypot(x, y) <= self.border_m

    def _stamp(self, x, y):
        cx = (x + REACH_M) / MASK_M_PER_PX
        cy = (REACH_M - y) / MASK_M_PER_PX
        radius_px = SCAN_RADIUS_M / MASK_M_PER_PX
        low_x = max(0, int(math.floor(cx - radius_px)))
        high_x = min(MASK_PX - 1, int(math.ceil(cx + radius_px)))
        low_y = max(0, int(math.floor(cy - radius_px)))
        high_y = min(MASK_PX - 1, int(math.ceil(cy + radius_px)))
        border_px = None if self.border_m is None else self.border_m / MASK_M_PER_PX
        changed = False
        for py in range(low_y, high_y + 1):
            dy = py + 0.5 - cy
            for px in range(low_x, high_x + 1):
                dx = px + 0.5 - cx
                if dx * dx + dy * dy > radius_px * radius_px:
                    continue
                if border_px is not None:
                    map_dx = px + 0.5 - MASK_PX / 2
                    map_dy = py + 0.5 - MASK_PX / 2
                    if map_dx * map_dx + map_dy * map_dy > border_px * border_px:
                        continue
                offset = py * MASK_PX + px
                if not self._mask[offset]:
                    self._mask[offset] = 1
                    self._painted_pixels += 1
                    changed = True
        if changed:
            self.version += 1
        return changed

    def _repaint(self, points):
        self._mask = bytearray(MASK_PX * MASK_PX)
        self._painted_pixels = 0
        kept = []
        for lat, lon in points:
            x, y = self.xy(lat, lon)
            if not self._inside(x, y):
                continue
            if abs(x) <= REACH_M + SCAN_RADIUS_M and abs(y) <= REACH_M + SCAN_RADIUS_M:
                self._stamp(x, y)
            kept.append((float(lat), float(lon)))
        self.stamps = kept
        self.version += 1
        self._last_xy = None

    def add(self, lat, lon):
        x, y = self.xy(lat, lon)
        if abs(x) > REACH_M or abs(y) > REACH_M:
            return False
        if self._last_xy is not None and math.hypot(
            x - self._last_xy[0], y - self._last_xy[1],
        ) < STAMP_M:
            return True
        self._last_xy = (x, y)
        if self._inside(x, y) and self._stamp(x, y):
            self.stamps.append((float(lat), float(lon)))
        return True

    def recenter(self, lat, lon):
        self.origin = (float(lat), float(lon))
        self.centered = True
        self._repaint(list(self.stamps))

    def set_border(self, lat, lon):
        if not self.centered:
            return False
        self.border_m = math.hypot(*self.xy(lat, lon))
        self._repaint(list(self.stamps))
        return True

    @property
    def painted_km2(self):
        return self._painted_pixels * (MASK_M_PER_PX / 1000.0) ** 2

    def to_dict(self):
        point = lambda p: [round(p[0], 6), round(p[1], 6)]
        data = {
            "origin": point(self.origin), "radius": self.radius_m,
            "location": self.location,
            "stamps": [point(value) for value in self.stamps],
            "saved": time.time(),
        }
        if self.centered:
            data["center"] = point(self.origin)
        if self.border_m is not None:
            data["border_m"] = round(self.border_m)
        return data

    @classmethod
    def from_dict(cls, body, data, name=None):
        try:
            lat, lon = data.get("center") or data["origin"]
            result = cls(body, float(lat), float(lon), float(data["radius"]), name=name)
            result.centered = bool(data.get("center"))
            border = _number(data.get("border_m"))
            result.border_m = border if result.centered and border is not None else None
            result.location = data.get("location")
            result.saved = _number(data.get("saved")) or 0.0
            points = [(float(p[0]), float(p[1])) for p in data.get("stamps") or ()]
            result._repaint(points)
            return result
        except (KeyError, IndexError, TypeError, ValueError):
            return None


class RhinoMinimapTracker:
    """Profile-local coverage lifecycle plus overlay snapshot generation."""

    def __init__(self, path):
        self.path = str(path)
        self.maps = {}
        self.active = None
        self.in_rhino = False
        self.here = None
        self.heading = None
        self.system = ""
        self.in_reach = True
        self.notice = ""
        self.notice_until = 0.0
        self._dirty = False
        self._last_save = 0.0
        self.load()

    def switch(self, path):
        self.flush()
        self.path = str(path)
        self.maps = {}
        self.active = None
        self.in_rhino = False
        self.here = None
        self.load()

    def load(self):
        try:
            with gzip.open(self.path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError, json.JSONDecodeError):
            return False
        maps = payload.get("maps") if isinstance(payload, dict) else None
        if not isinstance(maps, dict):
            return False
        for body, records in maps.items():
            loaded = []
            for name, data in (records or {}).items():
                cover = CoverageMap.from_dict(body, data, name)
                if cover is not None:
                    loaded.append(cover)
            if loaded:
                self.maps[str(body)] = loaded
        return True

    def _next_name(self, body):
        numbers = []
        for cover in self.maps.get(body, ()):
            match = re.fullmatch(r"map (\d+)", str(cover.name or ""))
            if match:
                numbers.append(int(match.group(1)))
        return f"map {max(numbers, default=0) + 1}"

    def _pick_saved(self, body, lat, lon, *, skip=None):
        found = []
        covers = next((
            rows for name, rows in self.maps.items()
            if name.casefold() == str(body).casefold()
        ), ())
        for cover in covers:
            if cover.name == skip or not cover.reaches(lat, lon):
                continue
            found.append((-cover.saved, math.hypot(*cover.xy(lat, lon)), cover))
        return min(found, key=lambda row: row[:2])[2] if found else None

    def update(self, *, body="", system="", latitude=None, longitude=None,
               radius_m=None, heading=None, in_srv=False, vehicle="",
               destination=None):
        lat, lon, radius = _number(latitude), _number(longitude), _number(radius_m)
        body = str(body or "").strip()
        is_rhino = bool(
            in_srv and str(vehicle or "").strip().upper() == "RHINO"
            and body and lat is not None and lon is not None and radius and radius > 0
        )
        if not is_rhino:
            if self.in_rhino:
                self.flush()
            self.in_rhino = False
            self.here = None
            return False

        fresh_launch = not self.in_rhino
        previous = self.active
        if previous is None or previous.body.casefold() != body.casefold() or (
            fresh_launch and not previous.reaches(lat, lon)
        ):
            skip = previous.name if previous and previous.body.casefold() == body.casefold() else None
            self.active = self._pick_saved(body, lat, lon, skip=skip)
            if self.active is None:
                self.active = CoverageMap(body, lat, lon, radius, name=self._next_name(body))
                self.maps.setdefault(body, []).append(self.active)
            fresh_launch = True
        if fresh_launch:
            self.active.launch(lat, lon)

        self.in_rhino = True
        self.here = (lat, lon)
        self.heading = _number(heading)
        self.system = str(system or "").strip()
        before = (self.active.version, self.active.location)
        self.in_reach = self.active.add(lat, lon)
        index = location_index(destination)
        if index is not None:
            self.active.location = index
        if before != (self.active.version, self.active.location) or previous is not self.active:
            self._dirty = True
        self.flush_if_due()
        return True

    def center_here(self):
        if not self.in_rhino or self.active is None or self.here is None:
            self._notice("Center unavailable outside the Rhino")
            return False
        self.active.recenter(*self.here)
        self._dirty = True
        self.flush(force=True)
        self._notice("Coverage center set")
        return True

    def border_here(self):
        if not self.in_rhino or self.active is None or self.here is None:
            self._notice("Border unavailable outside the Rhino")
            return False
        if not self.active.set_border(*self.here):
            self._notice("Set the coverage center first")
            return False
        self._dirty = True
        self.flush(force=True)
        self._notice(f"Coverage border set at {self.active.border_m / 1000.0:.1f} km")
        return True

    def reset_active(self):
        """Replace the current map with a clean map anchored at the Rhino.

        The map keeps its name and Elite location number so a reset does not
        create a misleading extra saved-map entry. Coverage, custom center,
        border and any previous exported PNG are discarded. The Rhino's
        present scanner footprint becomes the first coverage stamp.
        """
        if not self.in_rhino or self.active is None or self.here is None:
            self._notice("Map reset unavailable outside the Rhino")
            return False
        previous = self.active
        replacement = CoverageMap(
            previous.body, *self.here, previous.radius_m, name=previous.name,
        )
        replacement.location = previous.location
        replacement.launch(*self.here)
        replacement.add(*self.here)
        replaced = False
        for covers in self.maps.values():
            for index, cover in enumerate(covers):
                if cover is previous:
                    covers[index] = replacement
                    replaced = True
                    break
            if replaced:
                break
        if not replaced:
            self.maps.setdefault(previous.body, []).append(replacement)
        self.active = replacement
        self.in_reach = True
        self._dirty = True
        self.flush(force=True)
        try:
            self._picture_path(previous).unlink(missing_ok=True)
        except OSError:
            pass
        self._notice("Coverage map reset")
        return True

    def _notice(self, text):
        self.notice = str(text)
        self.notice_until = time.monotonic() + 5.0

    def show_notice(self, text):
        """Show a short confirmation over the active coverage map."""
        self._notice(text)

    def flush_if_due(self):
        if self._dirty and time.monotonic() - self._last_save >= 2.0:
            return self.flush()
        return False

    def flush(self, force=False):
        if not self._dirty and not force:
            return False
        payload = {"schema": SCHEMA_VERSION, "maps": {}}
        for body, covers in self.maps.items():
            payload["maps"][body] = {cover.name: cover.to_dict() for cover in covers}
        path = Path(self.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=6) as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            os.replace(temporary, path)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            return False
        self._dirty = False
        self._last_save = time.monotonic()
        for cover in self.maps.values():
            for item in cover:
                item.saved = time.time()
        return True

    def snapshot(self, sites=(), *, center_hotkey="", border_hotkey="",
                 drill_hotkey="", reset_hotkey=""):
        cover = self.active
        if not self.in_rhino or cover is None or self.here is None:
            return {"active": False, "vehicle": "RHINO"}
        x, y = cover.xy(*self.here)
        anchor_x, anchor_y = cover.anchor()
        distance = math.hypot(anchor_x - x, anchor_y - y)
        direction = bearing_deg(x, y, anchor_x, anchor_y) if distance > 0.5 else None
        marks = []
        for site in sites or ():
            if not isinstance(site, dict):
                continue
            if str(site.get("system") or "").casefold() != self.system.casefold():
                continue
            if str(site.get("body") or "").casefold() != cover.body.casefold():
                continue
            lat, lon = _number(site.get("latitude")), _number(site.get("longitude"))
            if lat is None or lon is None:
                continue
            mx, my = cover.xy(lat, lon)
            kind = "drill" if str(site.get("site_type") or "").casefold() == "drill" else "site"
            materials = re.split(r"[,;|\n]+", str(site.get("materials") or ""))
            material = next((item.strip() for item in materials if item.strip()), "")
            label = str(site.get("name") or material or "Surface site")
            drill_number = re.search(r"\b(\d+)\b", label) if kind == "drill" else None
            marks.append({
                "x": round(mx, 1), "y": round(my, 1),
                "code": f"D{drill_number.group(1)}" if drill_number else (
                    "D" if kind == "drill" else _material_code(material)
                ),
                "kind": kind,
                "label": label,
                "depleted": bool(site.get("depleted")),
            })
        notice = self.notice if time.monotonic() < self.notice_until else ""
        stamp_xy = [cover.xy(lat, lon) for lat, lon in cover.stamps]
        header = _short_body(cover.body, self.system)
        if cover.location is not None:
            header = f"loc {cover.location}  {header}"
        return {
            "active": True,
            "vehicle": "RHINO",
            "system": self.system,
            "body": cover.body,
            "header": header,
            "map_name": cover.name,
            "location": cover.location,
            "in_reach": bool(self.in_reach),
            "position": {"x": round(x, 1), "y": round(y, 1), "heading": self.heading},
            "origin": {"latitude": cover.origin[0], "longitude": cover.origin[1]},
            "anchor": {"x": round(anchor_x, 1), "y": round(anchor_y, 1)},
            "centered": cover.centered,
            "border_m": cover.border_m,
            "distance_m": round(distance, 1),
            "bearing": None if direction is None else round(direction, 1),
            "painted_km2": round(cover.painted_km2, 2),
            "stamps": [{"x": round(px, 1), "y": round(py, 1)} for px, py in stamp_xy],
            "bookmarks": marks,
            "drill_count": sum(mark["kind"] == "drill" for mark in marks),
            "drive_rings": drive_radii(cover.border_m) if cover.border_m is not None else [],
            "range_rings": list(RANGE_RINGS_M),
            "scan_radius_m": SCAN_RADIUS_M,
            "view_m": VIEW_M,
            "reach_m": REACH_M,
            "mask_m_per_px": MASK_M_PER_PX,
            "grid_m": GRID_M,
            "version": cover.version,
            "notice": notice,
            "hotkeys": {
                "center": center_hotkey,
                "border": border_hotkey,
                "drill": drill_hotkey,
                "reset": reset_hotkey,
            },
            "coverage_is_estimate": True,
        }

    @property
    def map_folder(self):
        return Path(self.path).parent / "rhino_maps"

    def usage(self):
        folder = self.map_folder
        count = sum(len(covers) for covers in self.maps.values())
        try:
            files = list(folder.rglob("*.png"))
            size = sum(item.stat().st_size for item in files)
            profile_map = Path(self.path)
            if profile_map.is_file():
                size += profile_map.stat().st_size
            return count, size
        except OSError:
            return count, 0

    @staticmethod
    def _safe_path_name(value):
        value = re.sub(r"[^A-Za-z0-9._ -]+", "_", str(value or "map")).strip(" .")
        return value[:100] or "map"

    def _picture_path(self, cover=None):
        cover = cover or self.active
        if cover is None:
            return self.map_folder / "map.png"
        return (
            self.map_folder / self._safe_path_name(cover.body)
            / f"{self._safe_path_name(cover.name)}.png"
        )

    def export_picture(self, sites=()):
        """Write the active map and bookmark legend as a shareable PNG."""
        cover = self.active
        if cover is None:
            return None
        try:
            from PIL import Image, ImageChops, ImageDraw, ImageFilter

            raw = bytes(255 if pixel else 0 for pixel in cover._mask)
            mask = Image.frombytes("L", (MASK_PX, MASK_PX), raw)
            background = Image.new("RGB", mask.size, "#070b10")
            fill = Image.new("RGB", mask.size, "#0c3947")
            image = Image.composite(fill, background, mask)
            expanded = mask.filter(ImageFilter.MaxFilter(3))
            edge = ImageChops.subtract(expanded, mask)
            image = Image.composite(Image.new("RGB", mask.size, "#00b7df"), image, edge)
            draw = ImageDraw.Draw(image)
            metres_per_pixel = 2 * REACH_M / MASK_PX
            for value in range(int(-REACH_M), int(REACH_M) + 1, int(GRID_M)):
                pixel = int(round((value + REACH_M) / metres_per_pixel))
                draw.line((pixel, 0, pixel, MASK_PX), fill="#16313c", width=1)
                draw.line((0, MASK_PX - pixel, MASK_PX, MASK_PX - pixel), fill="#16313c", width=1)
            if cover.border_m is not None:
                radius = cover.border_m / metres_per_pixel
                center = MASK_PX / 2
                draw.ellipse((center-radius, center-radius, center+radius, center+radius), outline="#dcebf3", width=2)

            marks = []
            for site in sites or ():
                if not isinstance(site, dict):
                    continue
                if str(site.get("system") or "").casefold() != self.system.casefold():
                    continue
                if str(site.get("body") or "").casefold() != cover.body.casefold():
                    continue
                lat, lon = _number(site.get("latitude")), _number(site.get("longitude"))
                if lat is None or lon is None or not cover.reaches(lat, lon):
                    continue
                x, y = cover.xy(lat, lon)
                material = next((part.strip() for part in re.split(
                    r"[,;|\n]+", str(site.get("materials") or "")
                ) if part.strip()), "")
                kind = "drill" if str(site.get("site_type") or "").casefold() == "drill" else "site"
                name = str(site.get("name") or "Surface site")
                drill_number = re.search(r"\b(\d+)\b", name) if kind == "drill" else None
                code = f"D{drill_number.group(1)}" if drill_number else (
                    "D" if kind == "drill" else _material_code(material)
                )
                marks.append((x, y, code, material, name, bool(site.get("depleted")), kind))
            for x, y, code, _material, _name, depleted, kind in marks:
                px = (x + REACH_M) / metres_per_pixel
                py = (REACH_M - y) / metres_per_pixel
                colour = "#ff6b70" if depleted else ("#ff8a3d" if kind == "drill" else "#54e39a")
                if kind == "drill":
                    draw.polygon(((px, py-8), (px+8, py), (px, py+8), (px-8, py)),
                                 fill=colour, outline="#070b10")
                else:
                    draw.ellipse((px-6, py-6, px+6, py+6), fill=colour, outline="#070b10", width=2)
                draw.text((px+9, py-6), code, fill=colour, stroke_width=2, stroke_fill="#070b10")

            facts = [str(cover.name or "map")]
            if cover.centered:
                facts.append(f"center {cover.origin[0]:.6f} / {cover.origin[1]:.6f}")
            if cover.border_m is not None:
                facts.append(f"border {cover.border_m / 1000.0:.1f} km")
            if cover.location is not None:
                facts.append(f"loc {cover.location}")
            facts.append(f"{cover.painted_km2:.1f} km² covered")
            title = f"{cover.body}  //  {'  ·  '.join(facts)}"
            legend_height = 18 * len(marks)
            sheet = Image.new("RGB", (MASK_PX, 38 + MASK_PX + 12 + legend_height), "#070b10")
            sheet_draw = ImageDraw.Draw(sheet)
            sheet_draw.text((10, 11), title, fill="#dcebf3")
            sheet.paste(image, (0, 38))
            y = 38 + MASK_PX + 8
            for _x, _y, code, material, name, depleted, kind in marks:
                colour = "#ff6b70" if depleted else ("#ff8a3d" if kind == "drill" else "#54e39a")
                detail = f"{code or '-'}  {material or 'Unidentified'}  ·  {name}"
                if depleted:
                    detail += "  ·  depleted"
                sheet_draw.text((10, y), detail, fill=colour)
                y += 18

            target = self._picture_path(cover)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".png.tmp")
            sheet.save(temporary, format="PNG", optimize=True)
            os.replace(temporary, target)
            return target
        except (OSError, ValueError, ImportError):
            return None
