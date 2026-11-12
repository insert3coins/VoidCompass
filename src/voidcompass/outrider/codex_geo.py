"""Geology as codex entries (S22). Pure.

The codex logs a geological feature once per region (a "Silicate Vapour Gas Vent", a "Water Ice Geyser"...), the first
time you scan one there. A body's volcanism says which features it can have, so entries_for() gives the set of entries
a body could log, and the page marks a body where any of them is not in your codex for the region yet.

The mapping was read from EDDN's codex traffic joined to the scans of the same bodies (2026-10-12: 284 geology entries
on 81 bodies, every one inside the sets below; a geology entry's BodyID matched the scanned body every time). One
volcanism logs one of two to four entries: the material in the volcanism text, and on icy bodies its Ice form. No
volcanism text names sulphur dioxide or iron: metallic magma logs the sulphur dioxide fumarole and gas vent and the iron
magma lava spout; rocky magma the sulphur dioxide fumarole and gas vent and the silicate magma lava spout (and, on 2 of
its 6 bodies, the silicate vapour gas vent); silicate vapour geysers their fumarole and gas vent and the silicate magma
lava spout. On an icy body water (geysers or magma), carbon dioxide, ammonia, methane and nitrogen log that material's
Ice Fumarole and Ice Geyser. Never seen, so left out (no mark rather than a wrong one): the non-Ice water and carbon
dioxide entries, the Ice forms of sulphur dioxide and silicate vapour, any feature on a rocky ice body, silicate magma
and helium volcanism. Your codex's geology comes from its lines in your journals only (a scan logs no geology).
"""

# (material, icy) -> the entries a body of that volcanism can log
SOLID = {"metallic magma": (1400102, 1400402, 1400307), "rocky magma": (1400102, 1400402, 1400306, 1400414),
         "silicate vapour": (1400114, 1400414, 1400306)}
ICY = {"water": (1400158, 1400258), "carbon dioxide": (1400159, 1400259), "ammonia": (1400160, 1400260),
       "methane": (1400161, 1400261), "nitrogen": (1400162, 1400262)}
SOLID_CLASSES = ("metal rich body", "metal-rich body", "high metal content body", "high metal content world", "rocky body")
ICY_CLASSES = ("icy body",)
NAMES = {1400102: "Sulphur Dioxide Fumarole", 1400114: "Silicate Vapour Fumarole", 1400158: "Water Ice Fumarole",
         1400159: "Carbon Dioxide Ice Fumarole", 1400160: "Ammonia Ice Fumarole", 1400161: "Methane Ice Fumarole",
         1400162: "Nitrogen Ice Fumarole", 1400258: "Water Ice Geyser", 1400259: "Carbon Dioxide Ice Geyser",
         1400260: "Ammonia Ice Geyser", 1400261: "Methane Ice Geyser", 1400262: "Nitrogen Ice Geyser",
         1400306: "Silicate Magma Lava Spout", 1400307: "Iron Magma Lava Spout", 1400402: "Sulphur Dioxide Gas Vent",
         1400414: "Silicate Vapour Gas Vent"}
LOW, HIGH = 1400000, 1400499   # the geology entries' range (the 14xxxxx range also holds anomalies)


def material(volcanism):
    """The material a volcanism text names ("major silicate vapour geysers volcanism" -> "silicate vapour"), or None."""
    v = " ".join(str(volcanism or "").lower().split())
    for m in ("metallic magma", "rocky magma", "silicate vapour", "water", "carbon dioxide", "ammonia", "methane", "nitrogen"):
        if m in v:
            return m
    return None


def entries_for(r):
    """A body record (yours from the journal or Spansh's) -> the geology entries it could log, sorted ([] when none
    is known: not landable, no geological signals, no volcanism, or a combination never seen)."""
    if not isinstance(r, dict) or r.get("type") != "Planet" or not r.get("landable") or not r.get("geo"):
        return []
    ed = r.get("ed") if isinstance(r.get("ed"), dict) else {}
    cls = str(ed.get("PlanetClass") or r.get("subtype") or "").lower()
    m = material(r.get("volcanism"))
    if not m:
        return []
    table = SOLID if cls in SOLID_CLASSES else ICY if cls in ICY_CLASSES else {}
    return sorted(table.get(m, ()))
