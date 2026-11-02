"""Readable ship names for journal symbols and spoken name hints."""
from __future__ import annotations

import re

SHIP_NAMES = {
    'adder': 'Adder',
    'typex3': 'Alliance Challenger',
    'typex': 'Alliance Chieftain',
    'typex2': 'Alliance Crusader',
    'anaconda': 'Anaconda',
    'anacondamkii': 'Anaconda MkII',
    'asp': 'Asp Explorer',
    'aspscout': 'Asp Scout',
    'belugaliner': 'Beluga Liner',
    'explorernx': 'Caspian Explorer',
    'cobramkiii': 'Cobra Mk III',
    'cobramkiv': 'Cobra Mk IV',
    'cobramkv': 'Cobra Mk V',
    'corsair': 'Corsair',
    'empiretradernx': 'Corsair',
    'diamondbackxl': 'Diamondback Explorer',
    'diamondback': 'Diamondback Scout',
    'dolphin': 'Dolphin',
    'eagle': 'Eagle Mk II',
    'federationdropshipmkii': 'Federal Assault Ship',
    'federationcorvette': 'Federal Corvette',
    'federationdropship': 'Federal Dropship',
    'federationgunship': 'Federal Gunship',
    'ferdelance': 'Fer-de-Lance',
    'hauler': 'Hauler',
    'empiretrader': 'Imperial Clipper',
    'empirecourier': 'Imperial Courier',
    'cutter': 'Imperial Cutter',
    'empireeagle': 'Imperial Eagle',
    'keelback': 'Keelback',
    'smallcombat01nx': 'Kestrel Mk II',
    'kraitmkii': 'Krait Mk II',
    'kraitlight': 'Krait Phantom',
    'mediumtransport01': 'Lynx Highliner',
    'mamba': 'Mamba',
    'mandalay': 'Mandalay',
    'orca': 'Orca',
    'panthermkii': 'Panther Clipper Mk II',
    'python': 'Python',
    'pythonnx': 'Python Mk II',
    'sidewinder': 'Sidewinder',
    'type6': 'Type-6 Transporter',
    'type7': 'Type-7 Transporter',
    'type8': 'Type-8 Transporter',
    'type9': 'Type-9 Heavy',
    'type9military': 'Type-10 Defender',
    'lakonminer': 'Type-11 Prospector',
    'viper': 'Viper Mk III',
    'vipermkiv': 'Viper Mk IV',
    'vulture': 'Vulture',
}


def ship_name(symbol, localised=""):
    if localised:
        return str(localised)
    text = str(symbol or "").strip()
    key = re.sub(r"[^a-z0-9]", "", text.casefold())
    return SHIP_NAMES.get(key) or text
