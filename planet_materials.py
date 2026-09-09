"""Commander-local surface mining sites, separate from journal scan evidence."""
import math
import json
import sqlite3
from contextlib import closing
from pathlib import Path


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

    def rows(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            rows = [dict(row) for row in db.execute(
                "SELECT * FROM sites ORDER BY system COLLATE NOCASE, body COLLATE NOCASE, name COLLATE NOCASE, id")]
            for row in rows:
                row["body_details"] = json.loads(row["body_details"])
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
        if values["density"] not in {"", "Low", "Medium", "High"}:
            raise ValueError("Choose low, medium or high density.")
        for key, limit in (("system", 140), ("body", 160), ("name", 120), ("materials", 2000), ("notes", 4000)):
            values[key] = str(data.get(key) or "").strip()
            if len(values[key]) > limit or (key != "notes" and not values[key]):
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
                    density=:density, updated_at=CURRENT_TIMESTAMP WHERE id=:id""", values)
                if not cursor.rowcount:
                    raise ValueError("This site no longer exists in the active profile.")
                return values["id"]
            return db.execute("""INSERT INTO sites (system,body,name,latitude,longitude,materials,notes,body_details,density)
                VALUES (:system,:body,:name,:latitude,:longitude,:materials,:notes,:body_details,:density)""", values).lastrowid

    def delete(self, site_id):
        with closing(sqlite3.connect(self.path)) as db, db:
            return bool(db.execute("DELETE FROM sites WHERE id=?", (int(site_id),)).rowcount)


# Frontier Rhino update 4.4.1.0 (2026-09-03):
# https://www.elitedangerous.com/news/updates/4-4-1-0
# Choices are a catalogue, never a claim that a particular planet contains them.
SURFACE_MINING_NEW = (
    "Bastnasite", "Deuterium", "Diamond", "Helium", "Helium-3", "Iridium",
    "Magnesite", "Olivine", "Periclase Dunite", "Quartz Pyroxenite",
    "Ruby", "Sapphire", "Thortveitite",
)


def mining_material_catalogue():
    from mining_data import MINING_MATERIALS
    return sorted(set(MINING_MATERIALS) | set(SURFACE_MINING_NEW) | {
        "Aluminium", "Beryllium", "Copper", "Haematite", "Jadeite", "Lithium",
        "Tantalum", "Thorium", "Titanium", "Water", "Methane Clathrate",
        "Liquid Oxygen", "Hydrogen Peroxide",
    })
