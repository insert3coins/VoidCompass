"""What the Watcher knows of the galaxy, for its own words (5.7.1).

A small model knows little of Elite and fills the gaps with inventions, so
the facts it may use come from here: short cards picked by what the commander
asks about, the ships (from the Navigation HUD's catalogue, with the maker,
pad and role only where we're sure), and the powers (from Powerplay's own
dossiers). Nothing here names the mysteries the Watcher never speaks of.
"""
from __future__ import annotations

import re

# name: (journal symbols, maker, landing pad, what it's for). An empty maker
# or pad is one we aren't sure of: better unsaid than wrong.
SHIPS = {
    "Adder": (("adder",), "Zorgon Peterson", "small", "a light all-rounder"),
    "Alliance Challenger": (("typex3",), "Lakon", "medium", "an Alliance combat ship"),
    "Alliance Chieftain": (("typex",), "Lakon", "medium", "an Alliance combat ship"),
    "Alliance Crusader": (("typex2",), "Lakon", "medium", "an Alliance combat ship with a fighter bay"),
    "Anaconda": (("anaconda",), "Faulcon DeLacy", "large", "a big multirole flagship"),
    "Anaconda MkII": (("anacondamkii",), "Faulcon DeLacy", "large", "a big combat-minded multirole ship"),
    "Asp Explorer": (("asp",), "Lakon", "medium", "an explorer's ship"),
    "Asp Scout": (("aspscout",), "Lakon", "medium", "a light multirole ship"),
    "Beluga Liner": (("belugaliner",), "Saud Kruger", "large", "a luxury passenger liner"),
    "Caspian Explorer": (("explorernx",), "", "", "an explorer's ship"),
    "Cobra Mk III": (("cobramkiii",), "Faulcon DeLacy", "small", "the classic all-rounder"),
    "Cobra Mk IV": (("cobramkiv",), "Faulcon DeLacy", "small", "an all-rounder"),
    "Cobra Mk V": (("cobramkv",), "Faulcon DeLacy", "small", "an all-rounder"),
    "Corsair": (("corsair", "empiretradernx"), "Gutamaya", "medium", "a multirole ship"),
    "Diamondback Explorer": (("diamondbackxl",), "Lakon", "small", "a long-range explorer"),
    "Diamondback Scout": (("diamondback",), "Lakon", "small", "a light combat ship"),
    "Dolphin": (("dolphin",), "Saud Kruger", "small", "a small passenger ship"),
    "Eagle Mk II": (("eagle",), "Core Dynamics", "small", "a light fighter"),
    "Federal Assault Ship": (("federationdropshipmkii",), "Core Dynamics", "medium", "a Federal combat ship"),
    "Federal Corvette": (("federationcorvette",), "Core Dynamics", "large", "the Federation's heavy warship"),
    "Federal Dropship": (("federationdropship",), "Core Dynamics", "medium", "a Federal troop and combat ship"),
    "Federal Gunship": (("federationgunship",), "Core Dynamics", "medium", "a Federal gunship"),
    "Fer-de-Lance": (("ferdelance",), "Zorgon Peterson", "medium", "a combat ship"),
    "Hauler": (("hauler",), "Zorgon Peterson", "small", "a small freighter"),
    "Imperial Clipper": (("empiretrader",), "Gutamaya", "large", "an elegant Imperial multirole ship"),
    "Imperial Courier": (("empirecourier",), "Gutamaya", "small", "a fast light combat ship"),
    "Imperial Cutter": (("cutter",), "Gutamaya", "large", "the Empire's great trader and warship"),
    "Imperial Eagle": (("empireeagle",), "Gutamaya", "small", "a light fighter"),
    "Keelback": (("keelback",), "Lakon", "medium", "an armed freighter with a fighter bay"),
    "Kestrel Mk II": (("smallcombat01nx",), "", "small", "a light combat ship"),
    "Krait Mk II": (("kraitmkii",), "Faulcon DeLacy", "medium", "a multirole ship with a fighter bay"),
    "Krait Phantom": (("kraitlight",), "Faulcon DeLacy", "medium", "a light multirole and exploration ship"),
    "Lynx Highliner": (("mediumtransport01",), "", "medium", "a passenger ship"),
    "Mamba": (("mamba",), "Zorgon Peterson", "medium", "a fast combat ship"),
    "Mandalay": (("mandalay",), "Zorgon Peterson", "medium", "an explorer's ship"),
    "Orca": (("orca",), "Saud Kruger", "large", "a passenger liner"),
    "Panther Clipper Mk II": (("panthermkii",), "Zorgon Peterson", "large", "a heavy freighter"),
    "Python": (("python",), "Faulcon DeLacy", "medium", "a heavy multirole ship"),
    "Python Mk II": (("pythonnx",), "Faulcon DeLacy", "medium", "a combat ship"),
    "Sidewinder": (("sidewinder",), "Faulcon DeLacy", "small", "the ship every pilot starts in"),
    "Type-6 Transporter": (("type6",), "Lakon", "medium", "a freighter"),
    "Type-7 Transporter": (("type7",), "Lakon", "large", "a freighter"),
    "Type-8 Transporter": (("type8",), "Lakon", "medium", "a freighter"),
    "Type-9 Heavy": (("type9",), "Lakon", "large", "a heavy freighter"),
    "Type-10 Defender": (("type9military",), "Lakon", "large", "a heavy warship"),
    "Type-11 Prospector": (("lakonminer",), "Lakon", "", "a mining ship"),
    "Viper Mk III": (("viper",), "Faulcon DeLacy", "small", "a light combat ship"),
    "Viper Mk IV": (("vipermkiv",), "Faulcon DeLacy", "small", "a light combat ship"),
    "Vulture": (("vulture",), "Core Dynamics", "small", "a heavy fighter"),
}
_BY_SYMBOL = {symbol: name for name, row in SHIPS.items() for symbol in row[0]}

# What it knows of the galaxy, by subject: (title, words that bring it up,
# what it knows). Plain, safe, unchanging; never the mysteries it won't name.
LIBRARY = (
    ("THE GALAXY", (
        ("The galaxy", ("galaxy", "milky way", "stars"),
         "The galaxy holds some 400 billion star systems; people have charted only a sliver of them."),
        ("The bubble", ("bubble", "human space", "populated", "inhabited"),
         "The bubble is human space, roughly 200 light years around Sol, where the stations, factions and superpowers are."),
        ("Sol", ("sol", "earth", "mars", "home system"),
         "Sol is humanity's home system, with Earth and Mars; it is Federation space and needs a permit."),
        ("Achenar", ("achenar",), "Achenar is the Empire's capital system; it needs a permit."),
        ("Alioth", ("alioth",), "Alioth is the Alliance's capital system; it needs a permit."),
        ("Shinrarta Dezhra", ("shinrarta", "dezhra", "jameson memorial", "founders"),
         "Shinrarta Dezhra is the Pilots Federation's home, with Jameson Memorial station; only pilots ranked Elite may go there."),
        ("Colonia", ("colonia", "jaques"),
         "Colonia is a settled region about 22,000 light years from Sol, centred on Jaques Station, reached by pilots who made the long trip."),
        ("The galactic centre", ("centre", "center", "sagittarius", "galactic core", "sag a"),
         "Sagittarius A*, the black hole at the galaxy's centre, is about 25,900 light years from Sol."),
        ("Beagle Point", ("beagle point", "far side", "rim"),
         "Beagle Point is near the galaxy's far rim, about 65,000 light years from Sol, a classic explorer's goal."),
        ("Hutton Orbital", ("hutton", "mug"),
         "Hutton Orbital, in Alpha Centauri, is about 0.22 light years from its star: the longest supercruise in the bubble, rewarded with a mug."),
        ("The Old Worlds", ("lave", "diso", "leesti", "old worlds"),
         "Lave, Diso and Leesti are among the Old Worlds, some of the oldest settled systems in the bubble."),
        ("Galactic regions", ("region", "regions", "orion spur", "codex region"),
         "The galaxy is divided into 42 named regions, such as the Inner Orion Spur around Sol; the Codex records finds region by region."),
    )),
    ("POWERS & FACTIONS", (
        ("The Federation", ("federation", "federal", "president"),
         "The Federation is a democratic superpower centred on Sol, led by a president."),
        ("The Empire", ("empire", "imperial", "emperor"),
         "The Empire is a superpower ruled from Achenar by an emperor, built on patronage and honour."),
        ("The Alliance", ("alliance", "prime minister"),
         "The Alliance is a superpower of independent systems centred on Alioth, led by a prime minister."),
        ("Independents", ("independent", "independents"),
         "Many systems answer to no superpower: independent factions, cooperatives and the lawless."),
        ("The Pilots Federation", ("pilots federation", "rank", "ranks", "elite rank"),
         "The Pilots Federation ranks commanders in combat, trade, exploration, CQC, mercenary work and exobiology; Elite is the highest rank in each."),
        ("Minor factions", ("faction", "factions", "influence", "bgs", "background simulation"),
         "Minor factions control stations and systems; missions, trade, bounties and data sold shift their influence."),
        ("System states", ("boom", "war", "civil war", "election", "expansion", "lockdown", "outbreak", "famine"),
         "Factions pass through states like Boom, War, Civil War, Election, Expansion, Lockdown and Outbreak, which change markets and missions."),
        ("Powerplay", ("powerplay", "power", "powers", "merits", "pledge"),
         "In Powerplay, commanders pledge to one of the galaxy's powers and earn merits to strengthen its hold on systems."),
        ("Powerplay control", ("exploited", "fortified", "stronghold", "control"),
         "A power's systems are Exploited, Fortified or Strongholds, each tier stronger and reaching further."),
    )),
    ("FLYING", (
        ("The frame shift drive", ("frame shift", "fsd", "jump", "hyperspace", "witch-space", "witch space"),
         "The frame shift drive jumps between stars through witch-space and powers supercruise within a system."),
        ("Supercruise", ("supercruise", "assist"),
         "Supercruise lets a ship cross a star system faster than light, dropping out at stations, planets and signals; supercruise assist can fly it for you."),
        ("Supercruise overcharge", ("overcharge", "sco"),
         "Newer frame shift drives can overcharge in supercruise for far more speed, at a cost in heat and fuel."),
        ("Fuel scooping", ("fuel", "scoop", "scooping", "kgbfoam"),
         "A fuel scoop takes hydrogen from main sequence stars: the scoopable classes are K, G, B, F, O, A and M."),
        ("Jet cone boosts", ("neutron", "white dwarf", "jet", "boost", "jumponium"),
         "Flying through a neutron star's jet supercharges the frame shift drive for one much longer jump; a white dwarf gives a smaller boost. Both strain the drive."),
        ("Heat", ("heat", "overheat", "temperature"),
         "Heat builds near stars, when overcharging and in combat; above 100% it damages modules."),
        ("Docking", ("dock", "docking", "pad", "landing pad"),
         "Ships request docking and land on small, medium or large pads; large ships need large pads."),
        ("Rebuy", ("rebuy", "insurance", "destroyed"),
         "If a ship is destroyed, its insurance rebuy, a share of its value, replaces it at a station."),
        ("Interdiction", ("interdiction", "interdicted", "pirate", "pirates", "attack"),
         "Pirates can interdict a ship in supercruise and pull it out to fight; submitting or escaping are both choices."),
    )),
    ("SHIPS & MAKERS", (
        ("Shipbuilders", ("manufacturer", "makers", "shipbuilder", "faulcon", "lakon", "gutamaya", "core dynamics", "saud kruger", "zorgon"),
         "The great shipbuilders are Faulcon DeLacy, Lakon Spaceways, Core Dynamics, Gutamaya, Saud Kruger and Zorgon Peterson."),
        ("Navy ships", ("navy", "permit ship", "rank locked"),
         "The Federal and Imperial navies' ships, like the Corvette and the Cutter, are earned with naval rank."),
        ("Outfitting", ("outfitting", "module", "modules", "loadout"),
         "Ships are fitted at outfitting with core and optional modules; engineers improve them further."),
    )),
    ("EXPLORATION", (
        ("Exploring", ("explore", "exploration", "cartographics", "scan", "fss", "honk", "discovery scanner"),
         "Explorers honk with the discovery scanner, resolve bodies in the full spectrum scanner, map them with probes, and sell the data at Universal Cartographics."),
        ("First discoveries", ("first discovery", "first", "discovered", "tag", "footfall", "mapped"),
         "The first commander to sell a body's data gets their name on it as its discoverer; mapping and footfall have their own tags."),
        ("Valuable worlds", ("earth-like", "earthlike", "water world", "ammonia", "terraform", "valuable"),
         "Earth-like, water and ammonia worlds are among the most valuable finds to scan and map; terraformable worlds are worth more too."),
        ("Stars", ("star", "stars", "black hole", "neutron star", "wolf-rayet", "carbon star", "brown dwarf"),
         "Stars range from brown dwarfs to giants; neutron stars, black holes and Wolf-Rayet stars are among the rarer sights."),
        ("Nebulae", ("nebula", "nebulae"),
         "Nebulae are clouds of gas and dust where stars are born, often thick with young stars and rare bodies."),
        ("The Codex", ("codex",),
         "The Codex records what a commander has found, region by region, across the galaxy's 42 regions."),
        ("Stellar phenomena", ("phenomena", "lagrange", "notable stellar"),
         "Notable stellar phenomena, like Lagrange clouds, hide strange formations and life out in the black."),
    )),
    ("EXOBIOLOGY", (
        ("Exobiology", ("exobiology", "bio", "biology", "species", "organic", "sample", "sampler", "life"),
         "Exobiologists take three samples of a species with the genetic sampler, each far enough from the last, and sell them to Vista Genomics."),
        ("Where life grows", ("atmosphere", "landable", "where life"),
         "Life grows on landable worlds with thin atmospheres; the species depend on the atmosphere, gravity, temperature and star."),
        ("Being first", ("first logged", "bonus"),
         "Being the first to log a species on a world earns a large bonus when the samples are sold."),
    )),
    ("MINING & TRADE", (
        ("Mining", ("mining", "mine", "asteroid", "laser", "rings", "prospector", "collector", "limpet", "refinery"),
         "Miners work planetary rings with lasers and prospector and collector limpets, refining what they break off."),
        ("Core mining", ("core", "seismic", "fissure", "cracking", "pulse wave"),
         "Core mining cracks asteroid cores with seismic charges for the richest fragments; a pulse wave analyser finds them."),
        ("Precious finds", ("painite", "void opal", "low temperature diamonds", "platinum", "monazite", "musgravite", "alexandrite"),
         "Painite, void opals, low temperature diamonds, platinum, monazite, musgravite and alexandrite are among the most valuable minerals."),
        ("Trading", ("trade", "trading", "commodity", "market", "cargo", "profit"),
         "Traders buy where goods are cheap and sell where they are wanted; markets differ by each station's economy."),
        ("Economies", ("economy", "economies", "industrial", "agriculture", "high tech", "extraction", "refinery economy", "tourism"),
         "Station economies, such as Extraction, Refinery, Industrial, High Tech, Agriculture and Tourism, shape what they buy and sell."),
        ("Credits", ("credits", "money", "rich"),
         "Credits are the galaxy's money; exploration data, exobiology, trade, mining and bounties all earn them."),
    )),
    ("ENGINEERING", (
        ("Engineers", ("engineer", "engineers", "engineering", "blueprint", "blueprints"),
         "Engineers improve modules with blueprints, grade 1 to 5, and experimental effects, for materials and favours."),
        ("Materials", ("materials", "raw", "manufactured", "encoded", "material trader"),
         "Engineering takes raw, manufactured and encoded materials; material traders swap one kind for another."),
    )),
    ("ON FOOT", (
        ("On foot", ("on foot", "suit", "suits", "settlement", "odyssey", "concourse"),
         "On foot, commanders wear suits like the Maverick, Dominator and Artemis, visiting settlements and station concourses."),
        ("Weapons", ("weapon", "weapons", "rifle", "kinematic", "takada", "manticore"),
         "Hand weapons come from makers like Kinematic Armaments, Takada and Manticore."),
        ("Concourse services", ("bartender", "pioneer supplies", "vista genomics", "frontline solutions", "apex"),
         "Station concourses have the Bartender, Pioneer Supplies, Vista Genomics, Frontline Solutions and Apex Interstellar taxis."),
        ("The SRV", ("srv", "scarab", "scorpion", "rover", "buggy"),
         "The SRV is a surface rover for driving on landable worlds; the Scarab and Scorpion are two kinds."),
    )),
    ("CARRIERS & COLONIES", (
        ("Fleet carriers", ("carrier", "fleet carrier", "tritium"),
         "A fleet carrier is a commander's own mobile station, bought for about 5 billion credits, that jumps up to 500 light years at a time burning tritium."),
        ("Squadrons", ("squadron", "squadrons"),
         "Squadrons are groups of commanders flying together, with their own ranks and a squadron carrier of their own."),
        ("Colonisation", ("colonisation", "colonise", "colony", "construction", "architect"),
         "Commanders can claim and build out new systems through colonisation, hauling materials to construction sites."),
    )),
)
CARDS = tuple((keys, text) for _subject, rows in LIBRARY for _title, keys, text in rows)

ALWAYS_WORDS = ("Commander", "Watcher", "I", "Elite", "Sol", "Mm", "Hm", "Hmm")


def ship_name(symbol_or_name):
    """A journal ship symbol (or a name) as its proper name; '' when unknown."""
    text = str(symbol_or_name or "").strip()
    if text in SHIPS:
        return text
    return _BY_SYMBOL.get(re.sub(r"[^a-z0-9]", "", text.casefold()), "")


def ship_card(name):
    row = SHIPS.get(name)
    if not row:
        return ""
    _symbols, maker, pad, role = row
    made = f"made by {maker}, " if maker else ""
    pad = f"it needs a {pad} pad" if pad else ""
    return f"The {name} is {role}, {made}{pad}".rstrip(", ") + "."


def powers():
    """(name, allegiance, capital) for each power, from Powerplay's own dossiers."""
    try:
        from voidcompass.powerplay.powerplay_operations import POWER_DOSSIERS
    except Exception:
        return []
    return [(row["name"], row.get("allegiance") or "", row.get("headquarters") or "") for row in POWER_DOSSIERS]


def cards_for(text, limit=5):
    """The cards the words bring up, most matches first, and a card for every
    ship and power they name."""
    words = f" {str(text or '').casefold()} "
    scored = []
    for keys, card in CARDS:
        hits = sum(1 for key in keys if re.search(rf"\b{re.escape(key)}\b", words))
        if hits:
            scored.append((hits, card))
    scored.sort(key=lambda row: -row[0])
    found = [card for _hits, card in scored]
    for name in SHIPS:
        if re.search(rf"\b{re.escape(name.casefold())}\b", words):
            found.append(ship_card(name))
    for name, allegiance, capital in powers():
        if name.casefold() in words or name.split()[-1].casefold() in words.split():
            found.append(power_card(name, allegiance, capital))
    return found[:limit]


def power_card(name, allegiance, capital):
    return f"{name} is a power{f' of the {allegiance}' if allegiance else ''}{f', with a capital at {capital}' if capital else ''}."


def library():
    """All it knows of the galaxy, for the Watcher page's LIBRARY: each
    subject's cards, then every ship and every power."""
    subjects = [{"subject": subject, "cards": [{"title": title, "text": text} for title, _keys, text in rows]}
                for subject, rows in LIBRARY]
    subjects.append({"subject": "SHIPS", "cards": [{"title": name, "text": ship_card(name)} for name in SHIPS]})
    rows = powers()
    if rows:
        subjects.append({"subject": "THE POWERS", "cards": [{"title": name, "text": power_card(name, allegiance, capital)}
                                                            for name, allegiance, capital in rows]})
    return subjects


def vocabulary():
    """Every name the cards and lists may give the Watcher: words it may use
    capitalised without making them up."""
    words = set(ALWAYS_WORDS)
    texts = [card for _keys, card in CARDS] + [ship_card(name) for name in SHIPS] + list(SHIPS)
    texts += [" ".join(row) for row in powers()]
    for text in texts:
        words.update(re.findall(r"[A-Za-z][A-Za-z'\-*]*", text))
    return {word.casefold().rstrip("'s").removesuffix("'s") for word in words}
