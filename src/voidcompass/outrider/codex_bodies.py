"""Star and planet types as codex entries (a review suggestion the author picked, 2026-10-12). Pure.

The codex logs a body type once per region ("K Type Star", "Terraformable" ...: its localised names are ambiguous for
planets, so the EntryID is the key), the first time you scan one there. entry_for() says which entry a body record
would log, so a body whose entry is not in your codex for the region can be marked before you scan it.

The IDs are the game's, read from journals (the author's and EDDN's codex traffic, 2026-10-12). Giants and
supergiants: a star's luminosity class III logs the type's Giant entry, I (Ia0, Ia, Iab, Ib) its SuperGiant one, as
EDDN's codex entries paired with the scans of their bodies show; class II is left out (no entry was seen for it). The
explicitly giant journal types (K_OrangeGiant, M_RedGiant, the *SuperGiant ones) log their giant entry whatever their
class. A solid planet's "Ter" entries are the ones with an atmosphere (thin ones too), "No_Atmos" the airless: of
EDDN's 1,100-odd terrestrial entries, none of either kind had only bodies of the other kind of its class in its system.
A type with no ID seen is left out (no mark rather than a wrong one).
"""
import re

# (entry id, words for the mark's tooltip)
STARS = {   # main sequence (xx01), giant (xx02), supergiant (xx03)
    "O": (1100101, None, 1100103), "B": (1100201, 1100202, 1100203), "A": (1100301, 1100302, 1100303),
    "F": (1100401, 1100402, 1100403), "G": (1100501, 1100502, 1100503), "K": (1100601, 1100602, None),
    "M": (1100701, 1100702, 1100703), "L": (1100801, None, None), "T": (1100901, None, None),
    "TTS": (1101001, None, None), "AeBe": (1101101, None, None), "Y": (1101201, None, None),
    "C": (None, 1101402, None), "CN": (None, 1101502, None), "MS": (None, 1101902, None),
}
# the journal's giant types: (its class, giant (2) or supergiant (3))
GIANT_TYPES = {"A_BlueWhiteSuperGiant": ("A", 3), "B_BlueWhiteSuperGiant": ("B", 3), "F_WhiteSuperGiant": ("F", 3),
               "G_WhiteSuperGiant": ("G", 3), "M_RedSuperGiant": ("M", 3), "K_OrangeGiant": ("K", 2), "M_RedGiant": ("M", 2)}
OTHER_STARS = {"W": 1102101, "WC": 1102102, "WN": 1102103, "WNC": 1102104, "WO": 1102105,
               "N": 1102300, "H": 1102400, "SupermassiveBlackHole": 1102500}
# white dwarfs: 11022nn in the journal's order of the classes (D 01 ... DX 15; 9 of the 15 seen, all in this order)
WHITE_DWARFS = ["D", "DA", "DAB", "DAO", "DAV", "DAZ", "DB", "DBZ", "DBV", "DO", "DOV", "DQ", "DC", "DCV", "DX"]
GIANTS = {"Sudarsky class I gas giant": 1200501, "Sudarsky class II gas giant": 1200601,
          "Sudarsky class III gas giant": 1200701, "Sudarsky class IV gas giant": 1200801,
          "Sudarsky class V gas giant": 1200901, "Helium rich gas giant": 1201001, "Water giant": 1200101,
          "Gas giant with water based life": 1200301, "Gas giant with ammonia based life": 1200401}
# terrestrials: (plain, terraformable) without an atmosphere, then with one; ELW, water and ammonia worlds have no
# atmosphere split
SOLIDS = {"Metal rich body": ((1300401, None), (1301401, 1301402)),
          "High metal content body": ((1300501, 1300502), (1301501, 1301502)),
          "Rocky body": ((1300601, 1300602), (1301601, 1301602)),
          "Rocky ice body": ((1300701, None), (1301701, None)),
          "Icy body": ((1300801, None), (1301801, None))}
WORLDS = {"Earthlike body": (1300100, 1300100), "Water world": (1300301, 1300302), "Ammonia world": (1300202, None)}

STAR_WORDS = {"O": "O", "B": "B", "A": "A", "F": "F", "G": "G", "K": "K", "M": "M", "L": "L", "T": "T", "Y": "Y",
              "C": "C (carbon)", "CN": "CN (carbon)", "MS": "MS"}
SOLID_WORDS = {"Metal rich body": "metal-rich body", "High metal content body": "high metal content world",
               "Rocky body": "rocky body", "Rocky ice body": "rocky ice world", "Icy body": "icy body"}


def _names():
    out = {}
    for cls, ids in STARS.items():
        base = {"TTS": "T Tauri star", "AeBe": "Herbig Ae/Be star"}.get(cls) or f"{STAR_WORDS[cls]}-type star"
        for i, suffix in zip(ids, ("", " giant", " supergiant")):
            if i:
                out[i] = base.replace(" star", suffix) if suffix else base
    out.update({1102101: "Wolf-Rayet star", 1102102: "Wolf-Rayet C star", 1102103: "Wolf-Rayet N star",
                1102104: "Wolf-Rayet NC star", 1102105: "Wolf-Rayet O star", 1102300: "neutron star",
                1102400: "black hole", 1102500: "supermassive black hole"})
    for n, cls in enumerate(WHITE_DWARFS, 1):
        out[1102200 + n] = f"{cls} white dwarf"
    out.update({1200501: "class I gas giant", 1200601: "class II gas giant", 1200701: "class III gas giant",
                1200801: "class IV gas giant", 1200901: "class V gas giant", 1201001: "helium-rich gas giant",
                1200101: "water giant", 1200301: "gas giant with water-based life",
                1200401: "gas giant with ammonia-based life", 1300100: "Earth-like world", 1300301: "water world",
                1300302: "terraformable water world", 1300202: "ammonia world"})
    for cls, ((bare, bare_t), (atm, atm_t)) in SOLIDS.items():
        w = SOLID_WORDS[cls]
        for i, words in ((bare, f"{w}, no atmosphere"), (bare_t, f"terraformable {w}, no atmosphere"),
                         (atm, f"{w} with an atmosphere"), (atm_t, f"terraformable {w} with an atmosphere")):
            if i:
                out[i] = words
    return out


NAMES = _names()

# Spansh's wording back to the journal's (the records keep Spansh's: ed_outrider.JOURNAL_STARS / JOURNAL_PLANETS)
SPANSH_STAR = {"O (Blue-White) Star": "O", "B (Blue-White) Star": "B", "A (Blue-White) Star": "A", "F (White) Star": "F",
               "G (White-Yellow) Star": "G", "K (Yellow-Orange) Star": "K", "M (Red dwarf) Star": "M",
               "L (Brown dwarf) Star": "L", "T (Brown dwarf) Star": "T", "Y (Brown dwarf) Star": "Y",
               "T Tauri Star": "TTS", "Herbig Ae/Be Star": "AeBe", "Wolf-Rayet Star": "W", "Wolf-Rayet N Star": "WN",
               "Wolf-Rayet NC Star": "WNC", "Wolf-Rayet C Star": "WC", "Wolf-Rayet O Star": "WO", "C Star": "C",
               "CN Star": "CN", "MS-type Star": "MS", "Neutron Star": "N", "Black Hole": "H",
               "Supermassive Black Hole": "SupermassiveBlackHole",
               "A (Blue-White super giant) Star": "A_BlueWhiteSuperGiant",
               "B (Blue-White super giant) Star": "B_BlueWhiteSuperGiant", "F (White super giant) Star": "F_WhiteSuperGiant",
               "G (White-Yellow super giant) Star": "G_WhiteSuperGiant", "K (Yellow-Orange giant) Star": "K_OrangeGiant",
               "M (Red giant) Star": "M_RedGiant", "M (Red super giant) Star": "M_RedSuperGiant"}
SPANSH_PLANET = {"Metal-rich body": "Metal rich body", "High metal content world": "High metal content body",
                 "Rocky body": "Rocky body", "Rocky Ice world": "Rocky ice body", "Icy body": "Icy body",
                 "Earth-like world": "Earthlike body", "Water world": "Water world", "Ammonia world": "Ammonia world",
                 "Water giant": "Water giant", "Gas giant with water-based life": "Gas giant with water based life",
                 "Gas giant with ammonia-based life": "Gas giant with ammonia based life",
                 "Helium-rich gas giant": "Helium rich gas giant"}
NO_ATMOSPHERE = {"", "none", "no atmosphere"}


def size_of(luminosity):
    """1 (main sequence and below), 2 (giant), 3 (supergiant) from a luminosity class ("Vab", "III", "Ia0"), or None
    (class II, or not known)."""
    m = re.match(r"^(VII|VI|V|IV|III|II|I|0)", str(luminosity or ""))
    if not m:
        return None
    return {"III": 2, "II": None, "I": 3, "0": 3}.get(m.group(1), 1)


def star_entry(code, luminosity):
    """The codex entry a star of journal type `code` logs, or None."""
    if code in GIANT_TYPES:
        cls, size = GIANT_TYPES[code]
        return STARS[cls][size - 1]
    if code in OTHER_STARS:
        return OTHER_STARS[code]
    if code in WHITE_DWARFS:
        return 1102200 + WHITE_DWARFS.index(code) + 1
    if code in STARS:
        size = size_of(luminosity)
        return STARS[code][size - 1] if size else None
    return None


def planet_entry(cls, terraformable, atmosphere):
    """The codex entry a planet of journal class `cls` logs, or None. atmosphere: its type, "None" / "No atmosphere"
    / "" for none, None when not known (then a solid body's entry cannot be told)."""
    if cls in GIANTS:
        return GIANTS[cls]
    if cls in WORLDS:
        return WORLDS[cls][1 if terraformable else 0]
    if cls in SOLIDS:
        if atmosphere is None:
            return None
        has = str(atmosphere).strip().lower() not in NO_ATMOSPHERE
        return SOLIDS[cls][1 if has else 0][1 if terraformable else 0]
    return None


def entry_for(r):
    """A body record (yours from the journal or Spansh's) -> the codex entry its type logs, or None."""
    if not isinstance(r, dict):
        return None
    ed = r.get("ed") if isinstance(r.get("ed"), dict) else {}
    st = r.get("subtype") or ""
    if r.get("type") == "Star":
        code = ed.get("StarType") or SPANSH_STAR.get(st)
        if not code:
            m = re.match(r"^White Dwarf \((\w+)\) Star$", st)
            code = m.group(1) if m else None
        return star_entry(code, r.get("luminosity"))
    if r.get("type") == "Planet":
        cls = ed.get("PlanetClass") or SPANSH_PLANET.get(st)
        if not cls:
            m = re.match(r"^Class (\w+) gas giant$", st)
            cls = f"Sudarsky class {m.group(1)} gas giant" if m else None
        # Spansh's search records carry no atmosphere: unknown there (a dump's or your scan's says)
        return planet_entry(cls, bool(r.get("terraformable")), r.get("atmosphere") if "atmosphere" in r else None)
    return None
