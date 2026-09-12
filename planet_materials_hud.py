"""Live, renderer-neutral surface materials overlay model."""

from __future__ import annotations

import math
import re

from application_runtime import OverlayWindowState
import overlay_chrome
import themes


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _body_key(value, system=""):
    value = str(value or "").strip()
    system = str(system or "").strip()
    if system and value.casefold().startswith(f"{system} ".casefold()):
        value = value[len(system):].strip()
    return value.casefold()


def _material_names(value):
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = re.split(r"[,;\n|]+", str(value or ""))
    return [str(item).strip() for item in values if str(item).strip()][:12]


def _surface_distance_m(lat1, lon1, lat2, lon2, radius_m):
    values = tuple(_number(value) for value in (lat1, lon1, lat2, lon2, radius_m))
    if any(value is None for value in values) or values[-1] <= 0:
        return None
    lat1, lon1, lat2, lon2, radius_m = values
    z = (
        math.sin(math.radians(lat1)) * math.sin(math.radians(lat2))
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.cos(math.radians(lon2 - lon1))
    )
    return math.acos(max(-1.0, min(1.0, z))) * radius_m


def build_planet_materials_model(
    workspace, *, latitude=None, longitude=None, heading=None, radius_m=None,
    vehicle_name="",
):
    """Condense the Planet Materials workspace into a cockpit-sized model."""
    workspace = workspace if isinstance(workspace, dict) else {}
    system = str(workspace.get("system") or "").strip()
    body = str(workspace.get("body") or "").strip()
    body_key = _body_key(body, system)
    bodies = [row for row in workspace.get("bodies") or () if isinstance(row, dict)]
    details = next((row for row in bodies if body_key and body_key in {
        _body_key(row.get("body"), system), _body_key(row.get("short_name"), system),
    }), {})
    if not body and details:
        body = str(details.get("body") or details.get("short_name") or "").strip()
        body_key = _body_key(body, system)

    materials = []
    for item in details.get("materials") or ():
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("symbol") or "").strip()
        if not name:
            continue
        materials.append({
            "name": name,
            "percent": round(max(0.0, _number(item.get("percent")) or 0.0), 2),
            "rare": bool(item.get("rare")),
        })
    materials.sort(key=lambda row: (not row["rare"], -row["percent"], row["name"].casefold()))

    latitude = _number(latitude)
    longitude = _number(longitude)
    heading = _number(heading)
    radius_m = _number(radius_m)
    sites = []
    for row in workspace.get("sites") or ():
        if not isinstance(row, dict):
            continue
        if str(row.get("system") or "").strip().casefold() != system.casefold():
            continue
        if _body_key(row.get("body"), system) != body_key:
            continue
        site_lat = _number(row.get("latitude"))
        site_lon = _number(row.get("longitude"))
        sites.append({
            "id": row.get("id"),
            "name": str(row.get("name") or "Surface site").strip(),
            "density": str(row.get("density") or "").strip(),
            "materials": _material_names(row.get("materials")),
            "latitude": site_lat,
            "longitude": site_lon,
            "distance_m": _surface_distance_m(
                latitude, longitude, site_lat, site_lon, radius_m,
            ),
        })
    sites.sort(key=lambda row: (
        row["distance_m"] is None,
        row["distance_m"] if row["distance_m"] is not None else float("inf"),
        row["name"].casefold(),
    ))

    target = workspace.get("navigation_target") or {}
    target_here = bool(
        target.get("active")
        and str(target.get("system") or "").casefold() == system.casefold()
        and _body_key(target.get("body"), system) == body_key
    )
    vehicle = str(vehicle_name or "").strip().upper()
    on_planet = bool(workspace.get("on_planet"))
    return {
        "active": bool(body and (details or on_planet or sites)),
        "system": system,
        "body": body,
        "short_body": str(details.get("short_name") or body).strip(),
        "vehicle": vehicle,
        "rhino_active": vehicle == "RHINO",
        "on_planet": on_planet,
        "position": {
            "latitude": latitude,
            "longitude": longitude,
            "heading": heading,
        } if latitude is not None and longitude is not None else None,
        "details": {
            "class": str(details.get("class") or "Unknown").strip(),
            "volcanism": str(details.get("volcanism") or "None detected").strip(),
            "gravity": _number(details.get("gravity")),
            "temperature": _number(details.get("temperature")),
            "landable": bool(details.get("landable")),
            "mining_locations": max(0, int(_number(details.get("mining_locations")) or 0)),
        },
        "materials": materials[:8],
        "sites": sites[:8],
        "site_count": len(sites),
        "target": {
            "active": target_here,
            "label": str(target.get("label") or "Surface site").strip(),
            "site_id": target.get("site_id"),
        },
    }


class PlanetMaterialsHUD:
    """Invisible native state proxy for the semantic HTML field overlay."""

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._html_render_model = build_planet_materials_model({})
        self.win = OverlayWindowState(root)
        x = int(config.get("planet_materials_hud_x", 820))
        y = int(config.get("planet_materials_hud_y", 80))
        self._desired_pos = (x, y)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self.win.withdraw()

    def update(self, workspace, **live):
        self._html_render_model = build_planet_materials_model(workspace, **live)
        if self._html_render_model["active"]:
            self.show()
        else:
            self.hide()

    def show(self):
        if not self._html_render_model.get("active"):
            return
        try:
            x = int(self.config.get("planet_materials_hud_x", 820))
            y = int(self.config.get("planet_materials_hud_y", 80))
            self._desired_pos = (x, y)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
        except Exception:
            pass

    def hide(self):
        try:
            self.win.withdraw()
        except Exception:
            pass

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
