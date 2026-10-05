"""Commodity names: the journal's symbols ("gold", "$opal_name;") and the
English names Spansh searches by ("Gold", "Void Opal").

Spansh only matches its exact English names, so a symbol is resolved in this
order: Frontier's quirky symbols below; the symbol folded against Spansh's own
list of names (/api/stations/field_values/market); a name the journal gave us
(Type_Localised, Name_Localised: English on an English game client, which is
why it comes after Spansh's list); and last the symbol title-cased, which is
right for every one-word commodity."""

from __future__ import annotations

import re

# Symbols whose words differ from the name (checked against Spansh's names).
ALIASES = {
    "agriculturalmedicines": "Agri-Medicines",
    "basicnarcotics": "Narcotics",
    "heliostaticfurnaces": "Microbial Furnaces",
    "marinesupplies": "Marine Equipment",
    "hazardousenvironmentsuits": "H.E. Suits",
    "terrainenrichmentsystems": "Land Enrichment Systems",
    "atmosphericextractors": "Atmospheric Processors",
    "drones": "Limpets",
    "trinketsoffortune": "Trinkets of Hidden Fortune",
    "encripteddatastorage": "Encrypted Data Storage",
    "comercialsamples": "Commercial Samples",
    "mutomimager": "Muon Imager",
    "skimercomponents": "Skimmer Components",
    "coolinghoses": "Micro-weave Cooling Hoses",
    "powergridassembly": "Energy Grid Assembly",
    "powertransferconduits": "Power Transfer Bus",
    "diagnosticsensor": "Hardware Diagnostic Sensor",
    "platinumaloy": "Platinum Alloy",
    "opal": "Void Opal",
    "lowtemperaturediamond": "Low Temperature Diamonds",
    "occupiedcryopod": "Occupied Escape Pod",
    "unocuppiedescapepod": "Unoccupied Escape Pod",
    "usscargoblackbox": "Black Box",
    "usscargotradedata": "Trade Data",
    "usscargomilitaryplans": "Military Plans",
    "usscargoancientartefact": "Ancient Artefact",
    "usscargorareartwork": "Rare Artwork",
    "usscargoexperimentalchemicals": "Experimental Chemicals",
    "usscargorebeltransmissions": "Rebel Transmissions",
    "usscargoprototypetech": "Prototype Tech",
    "usscargotechnicalblueprints": "Technical Blueprints",
    "largeexplorationdatacash": "Large Survey Data Cache",
    "smallexplorationdatacash": "Small Survey Data Cache",
}


def fold(text):
    return re.sub(r"[^a-z0-9]", "", str(text or "").casefold())


def symbol(value):
    """'$Gold_Name;' / 'Gold' / 'gold' -> 'gold'."""
    text = str(value or "").strip()
    match = re.fullmatch(r"\$(.+?)_name;", text, flags=re.IGNORECASE)
    return fold(match.group(1) if match else text)


class CommodityNames:
    """Learns names as the journal and Spansh show them; resolves symbols."""

    def __init__(self, learned=None, spansh_names=()):
        self.learned = dict(learned or {})     # symbol -> name, from the journal
        self.by_fold = {}
        self.add_spansh_names(spansh_names)

    def add_spansh_names(self, names):
        for name in names or ():
            if name:
                self.by_fold.setdefault(fold(name), str(name))

    def learn(self, raw_symbol, localised):
        key, name = symbol(raw_symbol), str(localised or "").strip()
        if not key or not name or name.startswith("$") or self.learned.get(key) == name:
            return False
        self.learned[key] = name
        return True

    def name(self, raw_symbol):
        """The best English name for a journal symbol."""
        key = symbol(raw_symbol)
        if not key:
            return ""
        if key in ALIASES:
            return ALIASES[key]
        if key in self.by_fold:
            return self.by_fold[key]
        if key + "s" in self.by_fold:
            return self.by_fold[key + "s"]
        if key in self.learned:
            return self.learned[key]
        text = re.sub(r"^\$|_name;$", "", str(raw_symbol or ""), flags=re.IGNORECASE)
        return text[:1].upper() + text[1:] if text else key

    def spansh_name(self, text):
        """A commodity typed by the commander -> Spansh's exact name, if known."""
        key = fold(text)
        if key in self.by_fold:
            return self.by_fold[key]
        resolved = self.name(text)
        return self.by_fold.get(fold(resolved), resolved)

    def all_names(self):
        return sorted(set(self.by_fold.values()) | set(self.learned.values()), key=str.casefold)
