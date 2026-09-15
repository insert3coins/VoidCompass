"""Commander-local surface mining sites, separate from journal scan evidence."""
import math
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from voidcompass.mining.rhino_intelligence import (
    AMOUNTS, DENSITIES, describe_tons, surface_distance_m,
)


class PlanetMaterialsStore:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS sites (
                id INTEGER PRIMARY KEY, system TEXT NOT NULL, body TEXT NOT NULL,
                name TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL,
                materials TEXT NOT NULL, notes TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(sites)")}
            if "body_details" not in columns:
                db.execute("ALTER TABLE sites ADD COLUMN body_details TEXT NOT NULL DEFAULT '{}'")
            if "density" not in columns:
                db.execute("ALTER TABLE sites ADD COLUMN density TEXT NOT NULL DEFAULT ''")
            if "depleted" not in columns:
                db.execute("ALTER TABLE sites ADD COLUMN depleted INTEGER NOT NULL DEFAULT 0")
            if "site_type" not in columns:
                db.execute("ALTER TABLE sites ADD COLUMN site_type TEXT NOT NULL DEFAULT 'site'")
            if "map_name" not in columns:
                db.execute("ALTER TABLE sites ADD COLUMN map_name TEXT NOT NULL DEFAULT ''")
            if "amount" not in columns:
                db.execute("ALTER TABLE sites ADD COLUMN amount TEXT NOT NULL DEFAULT ''")
            if "rigs" not in columns:
                db.execute("ALTER TABLE sites ADD COLUMN rigs INTEGER NOT NULL DEFAULT 0")
            if "planet_radius" not in columns:
                db.execute("ALTER TABLE sites ADD COLUMN planet_radius REAL")
            if "location_index" not in columns:
                db.execute("ALTER TABLE sites ADD COLUMN location_index INTEGER")

    def rows(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            rows = [dict(row) for row in db.execute(
                "SELECT * FROM sites ORDER BY system COLLATE NOCASE, body COLLATE NOCASE, name COLLATE NOCASE, id")]
            for row in rows:
                try:
                    details = json.loads(row.get("body_details") or "{}")
                except (TypeError, ValueError, json.JSONDecodeError):
                    details = {}
                row["body_details"] = details if isinstance(details, dict) else {}
                row["tons_left"] = describe_tons(row.get("rigs"), row.get("amount"))
            return rows

    def save(self, data):
        values = {}
        details = data.get("body_details") or {}
        if isinstance(details, str):
            details = json.loads(details)
        if not isinstance(details, dict):
            raise ValueError("Invalid planet scan details.")
        values["body_details"] = json.dumps(details, ensure_ascii=False, allow_nan=False)
        if len(values["body_details"]) > 16000:
            raise ValueError("Planet scan details are too large.")
        values["density"] = str(data.get("density") or "")
        if values["density"] not in {"", *DENSITIES}:
            raise ValueError("Choose low, medium or high density.")
        values["amount"] = str(data.get("amount") or "")
        if values["amount"] not in {"", *AMOUNTS}:
            raise ValueError("Choose high, medium, low or depleted Amount.")
        values["depleted"] = int(values["amount"] == "Depleted" or str(data.get("depleted") or "").casefold() in {
            "1", "true", "yes", "on",
        })
        if values["depleted"]:
            values["amount"] = "Depleted"
        try:
            values["rigs"] = int(data.get("rigs") or 0)
        except (TypeError, ValueError):
            raise ValueError("Rig positions must be a whole number.") from None
        if not 0 <= values["rigs"] <= 64:
            raise ValueError("Rig positions must be between 0 and 64.")
        radius = data.get("planet_radius")
        if radius in (None, ""):
            radius = details.get("radius_m") or details.get("radius")
        try:
            values["planet_radius"] = float(radius) if radius not in (None, "") else None
        except (TypeError, ValueError):
            raise ValueError("Planet radius must be numeric.") from None
        if values["planet_radius"] is not None and (
                not math.isfinite(values["planet_radius"]) or values["planet_radius"] <= 0):
            raise ValueError("Planet radius must be greater than zero.")
        location = data.get("location_index")
        try:
            values["location_index"] = int(location) if location not in (None, "") else None
        except (TypeError, ValueError):
            raise ValueError("Mining location must be a whole number.") from None
        if values["location_index"] is not None and not 1 <= values["location_index"] <= 9999:
            raise ValueError("Mining location must be between 1 and 9999.")
        values["site_type"] = str(data.get("site_type") or "site").strip().casefold()
        if values["site_type"] not in {"site", "drill"}:
            raise ValueError("Invalid surface marker type.")
        values["map_name"] = str(data.get("map_name") or "").strip()
        if len(values["map_name"]) > 120:
            raise ValueError("Surface map name is too long.")
        for key, limit in (("system", 140), ("body", 160), ("name", 120), ("materials", 2000), ("notes", 4000)):
            values[key] = str(data.get(key) or "").strip()
            optional = key == "notes" or (key == "materials" and values["site_type"] == "drill")
            if len(values[key]) > limit or (not optional and not values[key]):
                raise ValueError(f"Provide {key} (maximum {limit} characters).")
        if details and (
                details.get("system") != values["system"] or
                values["body"] not in (details.get("body"), details.get("short_name"))):
            raise ValueError("Captured scan details must match the site's system and planet.")
        for key, bound in (("latitude", 90), ("longitude", 180)):
            try:
                value = float(data.get(key, ""))
            except (ValueError, TypeError):
                raise ValueError(f"Provide a numeric {key}.") from None
            if not math.isfinite(value) or not -bound <= value <= bound:
                raise ValueError(f"{key.title()} must be between {-bound} and {bound}.")
            values[key] = value
        with closing(sqlite3.connect(self.path)) as db, db:
            if data.get("id"):
                values["id"] = int(data["id"])
                cursor = db.execute("""UPDATE sites SET system=:system, body=:body,
                    name=:name, latitude=:latitude, longitude=:longitude,
                    materials=:materials, notes=:notes, body_details=:body_details,
                    density=:density, depleted=:depleted, site_type=:site_type,
                    map_name=:map_name, amount=:amount, rigs=:rigs,
                    planet_radius=:planet_radius, location_index=:location_index,
                    updated_at=CURRENT_TIMESTAMP WHERE id=:id""", values)
                if not cursor.rowcount:
                    raise ValueError("This site no longer exists in the active profile.")
                return values["id"]
            nearby = self._nearby_deposit(db, values)
            if nearby is not None:
                db.execute("""UPDATE sites SET amount=:amount, density=:density,
                    depleted=:depleted, updated_at=CURRENT_TIMESTAMP WHERE id=:nearby_id""",
                    {**values, "nearby_id": nearby})
                return nearby
            return db.execute("""INSERT INTO sites (system,body,name,latitude,longitude,materials,notes,body_details,density,depleted,site_type,map_name,amount,rigs,planet_radius,location_index)
                VALUES (:system,:body,:name,:latitude,:longitude,:materials,:notes,:body_details,:density,:depleted,:site_type,:map_name,:amount,:rigs,:planet_radius,:location_index)""", values).lastrowid

    @staticmethod
    def _primary_material(value):
        return str(value or "").replace(";", ",").split(",", 1)[0].strip().casefold()

    @staticmethod
    def _body_key(system, body):
        system = str(system or "").strip()
        body = str(body or "").strip()
        if system and body.casefold().startswith((system + " ").casefold()):
            body = body[len(system):].strip()
        return body.casefold()

    def _nearby_deposit(self, db, values, maximum_m=100.0):
        """Existing same-material deposit close enough to be the same patch."""
        if values.get("site_type") != "site" or not values.get("planet_radius"):
            return None
        material = self._primary_material(values.get("materials"))
        if not material:
            return None
        db.row_factory = sqlite3.Row
        candidates = db.execute("""SELECT id,body,latitude,longitude,materials FROM sites
            WHERE site_type='site' AND system=? COLLATE NOCASE""",
            (values["system"],)).fetchall()
        nearest = None
        for row in candidates:
            if self._primary_material(row["materials"]) != material:
                continue
            if self._body_key(values["system"], row["body"]) != self._body_key(
                    values["system"], values["body"]):
                continue
            distance = surface_distance_m(
                values["latitude"], values["longitude"], row["latitude"], row["longitude"],
                values["planet_radius"],
            )
            if distance is not None and distance <= maximum_m and (
                    nearest is None or distance < nearest[0]):
                nearest = (distance, int(row["id"]))
        return nearest[1] if nearest else None

    def nearest_location(self, system, body, latitude, longitude, radius_m,
                         maximum_m=10000.0, rows=None):
        """Nearest numbered bookmark on this body within ``maximum_m``."""
        best = None
        for row in self.rows() if rows is None else rows:
            if row.get("location_index") is None:
                continue
            if str(row.get("system") or "").casefold() != str(system or "").casefold():
                continue
            if self._body_key(system, row.get("body")) != self._body_key(system, body):
                continue
            distance = surface_distance_m(
                latitude, longitude, row.get("latitude"), row.get("longitude"), radius_m,
            )
            if distance is not None and distance <= maximum_m and (
                    best is None or distance < best[0]):
                best = (distance, row)
        return best

    def delete(self, site_id):
        with closing(sqlite3.connect(self.path)) as db, db:
            return bool(db.execute("DELETE FROM sites WHERE id=?", (int(site_id),)).rowcount)

    def delete_drills_for_map(self, system, body, map_name):
        """Delete drill markers owned by one map, including pre-map legacy rows."""
        with closing(sqlite3.connect(self.path)) as db, db:
            cursor = db.execute("""DELETE FROM sites
                WHERE site_type='drill'
                AND system=? COLLATE NOCASE AND body=? COLLATE NOCASE
                AND (map_name=? COLLATE NOCASE OR map_name='')""",
                (str(system or ""), str(body or ""), str(map_name or "")))
            return max(0, int(cursor.rowcount))


# Frontier Rhino update 4.4.1.0 (2026-09-03):
# https://www.elitedangerous.com/news/updates/4-4-1-0
# Choices are a catalogue, never a claim that a particular planet contains them.
SURFACE_MINING_NEW = (
    "Bastnasite", "Deuterium", "Diamond", "Helium", "Helium-3", "Iridium",
    "Magnesite", "Olivine", "Periclase Dunite", "Quartz Pyroxenite",
    "Ruby", "Sapphire", "Thortveitite",
)


def mining_material_catalogue():
    from voidcompass.mining.mining_data import MINING_MATERIALS
    return sorted(set(MINING_MATERIALS) | set(SURFACE_MINING_NEW) | {
        "Aluminium", "Beryllium", "Copper", "Haematite", "Jadeite", "Lithium",
        "Tantalum", "Thorium", "Titanium", "Water", "Methane Clathrate",
        "Liquid Oxygen", "Hydrogen Peroxide",
    })
