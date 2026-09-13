"""Display labels for Elite Dangerous journal ``StarType`` identifiers.

Raw identifiers must remain intact for route fuel, valuation, and biological
prediction logic.  UI code should use :func:`star_type_label` instead.
"""

from __future__ import annotations

import re


_STAR_TYPE_LABELS = {
    "TTS": "T Tauri Star",
    "AeBe": "Herbig Ae/Be Star",
    "W": "Wolf-Rayet Star",
    "WN": "Wolf-Rayet N Star",
    "WNC": "Wolf-Rayet NC Star",
    "WC": "Wolf-Rayet C Star",
    "WO": "Wolf-Rayet O Star",
    "CS": "Carbon Star (CS)",
    "C": "Carbon Star",
    "CN": "Carbon Star (CN)",
    "CJ": "Carbon Star (CJ)",
    "CHd": "Carbon Star (CHd)",
    "MS": "MS-type Star",
    "S": "S-type Star",
    "D": "White Dwarf (D)",
    "DA": "White Dwarf (DA)",
    "DAB": "White Dwarf (DAB)",
    "DAO": "White Dwarf (DAO)",
    "DAZ": "White Dwarf (DAZ)",
    "DAV": "White Dwarf (DAV)",
    "DB": "White Dwarf (DB)",
    "DBZ": "White Dwarf (DBZ)",
    "DBV": "White Dwarf (DBV)",
    "DO": "White Dwarf (DO)",
    "DOV": "White Dwarf (DOV)",
    "DQ": "White Dwarf (DQ)",
    "DC": "White Dwarf (DC)",
    "DCV": "White Dwarf (DCV)",
    "DX": "White Dwarf (DX)",
    "N": "Neutron Star",
    "NS": "Neutron Star",
    "H": "Black Hole",
    "BH": "Black Hole",
    "SupermassiveBlackHole": "Supermassive Black Hole",
    "X": "Exotic Star",
    "A_BlueWhiteSuperGiant": "A Blue-White Supergiant",
    "B_BlueWhiteSuperGiant": "B Blue-White Supergiant",
    "F_WhiteSuperGiant": "F White Supergiant",
    "G_WhiteSuperGiant": "G White Supergiant",
    "K_OrangeGiant": "K Orange Giant",
    "M_RedGiant": "M Red Giant",
    "M_RedSuperGiant": "M Red Supergiant",
    "RoguePlanet": "Rogue Planet",
    "Nebula": "Nebula",
    "StellarRemnantNebula": "Stellar Remnant Nebula",
}


def star_type_label(star_type, default="", *, include_star=False):
    """Return a readable label while accepting unknown future identifiers."""
    raw = str(star_type or "").strip()
    if not raw:
        return default
    if include_star and raw in {"O", "B", "A", "F", "G", "K", "M", "L", "T", "Y"}:
        return f"{raw} Star"
    known = _STAR_TYPE_LABELS.get(raw)
    if known:
        return known
    words = raw.replace("_", " ")
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", words)
    return re.sub(r"\s+", " ", words).strip()
