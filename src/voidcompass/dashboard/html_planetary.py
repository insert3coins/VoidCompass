"""The Planetary page (5.5.12): Materials & Sites and Ground & Exobio as one,
in three tabs (on the ground, exobiology, sites). This adds what the page
shows beyond the sites builder: the ground workspace (compass, field map,
trail) and the biology of the planet you're on, as Survey Operations reads it.

Added only for the page itself: the Planet Materials overlay refreshes from
the sites builder alone, often, and doesn't need any of this."""
from __future__ import annotations

import logging

import math

from voidcompass.core import companion_features
from voidcompass.overlays.survey_status_hud import annotate_codex, body_codex_flag, build_survey_model


def _int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _bio_row(row):
    """One species (or genus) on the planet, as the overlay lists it."""
    return {
        "status": str(row.get("status") or ""),
        "name": str(row.get("display_name") or row.get("name") or ""),
        "genus": str(row.get("name") or ""),
        "variant": str(row.get("variant") or ""),
        "kind": str(row.get("kind") or ""),
        "progress": _int(row.get("progress")),
        "value": _int(row.get("value")) or None,
        "min_value": _int(row.get("min_value")) or None,
        "max_value": _int(row.get("max_value")) or None,
        "codex": str(row.get("codex") or ""),
        "lines": [{"species": str(line.get("species") or ""), "flag": str(line.get("flag") or ""),
                   "colours": [{"name": str(part.get("text") or ""), "flag": str(part.get("flag") or "")}
                               for part in line.get("variants") or ()]}
                  for line in row.get("codex_lines") or () if isinstance(line, dict)],
    }


def _point(row):
    try:
        lat, lon = float(row["lat"]), float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    return (lat, lon) if math.isfinite(lat) and math.isfinite(lon) else None


class _Plane:
    """Metres east and north of an anchor on a sphere of ``radius``: close
    enough for the few kilometres a survey covers."""

    def __init__(self, anchor, radius):
        self.lat0, self.lon0 = anchor
        self.radius = float(radius)
        self.cos0 = math.cos(math.radians(self.lat0))

    def __call__(self, point):
        lat, lon = point
        dlon = (lon - self.lon0 + 540.0) % 360.0 - 180.0
        return [round(math.radians(dlon) * self.radius * self.cos0, 1), round(math.radians(lat - self.lat0) * self.radius, 1)]


class HtmlPlanetaryMixin:
    def _planetary_map(self):
        """Everything on the surface in one frame (5.5.12): you, the ship, your
        trail, samples, markers, Codex finds, saved sites and the compass
        target, in metres from the ship (or where you started)."""
        radius = _num(getattr(self, "current_planet_radius", None))
        body = str(getattr(self, "current_body_name", "") or "")
        on_planet = bool(getattr(self, "on_planet", False))
        here = _point({"lat": getattr(self, "current_latitude", None), "lon": getattr(self, "current_longitude", None)}) if on_planet else None
        ship = _point(getattr(self, "surface_ship_position", None) or {})
        trail = [point for point in (_point(row) for row in getattr(self, "surface_trail", None) or ()) if point]
        specialist = getattr(self, "specialist_engine", None)
        try:
            exo = specialist.exobiology_snapshot() if specialist is not None else {}
        except Exception:
            exo = {}
        survey = exo.get("current_map") or {}
        if survey.get("body") and body and str(survey.get("body")).casefold() != body.casefold():
            survey = {}
        radius = radius or _num(survey.get("radius_m"))
        anchor = ship or (trail[0] if trail else None) or here or next(
            (point for point in (_point(row) for row in survey.get("pins") or ()) if point), None)
        if not radius or not anchor:
            self._planetary_plane = None
            return None
        plane = _Plane(anchor, radius)
        self._planetary_plane = plane
        step = max(1, len(trail) // 400)
        pins = []
        for row in survey.get("pins") or ():
            point = _point(row)
            if not point:
                continue
            meta = row.get("metadata") or {}
            pins.append({"id": str(row.get("id") or ""), "kind": str(row.get("kind") or ""), "label": str(row.get("label") or ""),
                         "at": plane(point), "lat": point[0], "lon": point[1], "manual": str(row.get("source") or "").casefold() == "manual",
                         "group": str(meta.get("sample_group") or ""), "progress": _int(meta.get("progress"))})
        sites = []
        store = getattr(self, "_planet_materials_store", None)
        if callable(store) and body:
            try:
                for row in store().rows():
                    point = _point({"lat": row.get("latitude"), "lon": row.get("longitude")})
                    if point and str(row.get("body") or "").casefold() == body.casefold():
                        sites.append({"id": row.get("id"), "label": str(row.get("name") or "Site"), "at": plane(point),
                                      "lat": point[0], "lon": point[1]})
            except Exception as exc:
                logging.debug("Planetary map sites skipped: %s", exc)
        target = None
        if getattr(self, "target_latlon_active", False):
            point = _point({"lat": getattr(self, "target_lat", None), "lon": getattr(self, "target_lon", None)})
            target_body = str(getattr(self, "ground_target_body", "") or "")
            if point and (not target_body or not body or target_body.casefold() == body.casefold()):
                target = {"at": plane(point), "label": str(getattr(self, "ground_target_label", "") or "Target")}
        sampling = exo.get("sampling") or {}
        return {
            "body": body or str(survey.get("body") or ""),
            "you": {"at": plane(here), "heading": _num(getattr(self, "current_heading", None))} if here else None,
            "ship": {"at": plane(ship)} if ship else None,
            "trail": [plane(point) for point in trail[::step]] + ([plane(here)] if here and trail else []),
            "pins": pins[-200:], "sites": sites[:40], "target": target,
            "sampling": {"group": str(sampling.get("sample_group") or ""), "colony_m": _num(sampling.get("colony_m")),
                         "species": str(sampling.get("species") or "")} if sampling else None,
        }

    def _planetary_extras(self):
        try:
            ground = self._html_ground_workspace()
        except Exception as exc:
            logging.debug("Planetary ground data skipped: %s", exc)
            ground = {}
        try:
            exobiology = self._planetary_exobiology(ground)
        except Exception as exc:
            logging.warning("Planetary exobiology skipped: %s", exc)
            exobiology = {}
        try:
            surface = self._planetary_map()
        except Exception as exc:
            logging.warning("Planetary map skipped: %s", exc)
            surface = None
        return {"ground": ground, "exobiology": exobiology, "map": surface}

    def _planetary_codex(self):
        if not (getattr(self, "config", None) or {}).get("survey_codex_flags", True):
            return None, None
        return getattr(self, "_survey_codex_lookup", None), getattr(self, "_survey_codex_variants", None)

    def _planetary_exobiology(self, ground=None):
        ground = ground or {}
        system = str(getattr(self, "current_sys", "") or "")
        items = list(getattr(self, "scan_items", None) or [])
        signals = getattr(self, "body_signals", None) or {}
        field = ground.get("field_map") or {}
        body_name = str(field.get("body") or getattr(self, "current_body_name", "") or "")
        sampling = self._sampling_snapshot() if getattr(self, "bio_sampling", None) else None
        lookup, variants = self._planetary_codex()
        here = None
        if body_name:
            model = build_survey_model(system, items, focused_body_name=body_name, sampling=sampling, body_signals=signals)
            if model.get("mode") == "body":
                if callable(lookup):
                    annotate_codex(model, lookup, variants)
                body = model.get("body") or {}
                rows = [_bio_row(row) for row in model.get("rows") or ()]
                here = {
                    "name": str(model.get("body_display") or body.get("name") or body_name),
                    "full_name": str(body.get("name") or body_name),
                    "planet_class": str(body.get("planet_class") or ""),
                    "atmosphere": str(body.get("atmosphere_type") or body.get("atmosphere") or ""),
                    "temperature_k": _num(body.get("surface_temp")),
                    "gravity_g": _num(body.get("gravity_g")),
                    "volcanism": str(body.get("volcanism") or ""),
                    "landable": body.get("landable"),
                    "first_footfall": bool(body.get("first_footfall")),
                    "bio_count": _int(body.get("bio_count")),
                    "complete": sum(1 for row in rows if row["kind"] == "complete"),
                    "min_value": _int(model.get("min_value")),
                    "max_value": _int(model.get("max_value")),
                    "rows": rows,
                }
        system_rows = []
        overview = build_survey_model(system, items, body_signals=signals)
        for row in overview.get("rows") or ():
            if not _int(row.get("bio_count")):
                continue
            entry = {
                "name": str(row.get("display_name") or row.get("name") or ""),
                "full_name": str(row.get("name") or ""),
                "bio_count": _int(row.get("bio_count")),
                "complete": _int(row.get("complete")),
                "min_value": _int(row.get("min_value")),
                "max_value": _int(row.get("max_value")),
                "gravity_g": _num(row.get("gravity_g")),
                "landable": row.get("landable") if row.get("landable_known") else None,
                "first_footfall": bool(row.get("first_footfall")),
                "here": bool(here and str(row.get("name") or "").casefold() == here["full_name"].casefold()),
                "codex": "",
            }
            if callable(lookup):
                source = next((item for item in items if str(item.get("body_id")) == str(row.get("body_id"))), None)
                if source:
                    try:
                        entry["codex"] = body_codex_flag(source, lookup, variants)
                    except Exception:
                        pass
            system_rows.append(entry)
        system_rows.sort(key=lambda row: (row["complete"] >= row["bio_count"], -row["max_value"], row["name"]))
        state = getattr(self, "companion_state", None) or {}
        return {
            "system": system,
            "here": here,
            "sampling": dict(sampling or {}) or None,
            "system_bodies": system_rows,
            "unsold": companion_features.unsold_bio_value(state),
            "unsold_base": _int(state.get("unsold_bio_cr")),
            "codex_flags": callable(lookup),
        }
