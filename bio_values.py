"""Exobiology reference values and lightweight genus prediction helpers."""

import bio_reference

GENUS_COLONY_M = {
    "Aleoida": 150, "Bacterium": 500, "Cactoida": 300, "Clypeus": 150,
    "Concha": 150, "Electricae": 1000, "Fonticulua": 500, "Frutexa": 150,
    "Fumerola": 100, "Fungoida": 300, "Osseus": 800, "Recepta": 150,
    "Stratum": 500, "Tubus": 800, "Tussock": 200,
    "Anemone": 100, "Amphora Plant": 100, "Bark Mounds": 100,
    "Brain Tree": 100, "Sinuous Tubers": 100,
}

SPECIES_VALUES = {
    "Aleoida Arcus": 7252500, "Aleoida Coronamus": 6284600, "Aleoida Gravis": 12934900,
    "Aleoida Laminiae": 3385200, "Aleoida Spica": 3385200,
    "Bacterium Acies": 1000000, "Bacterium Alcyoneum": 1658500, "Bacterium Aurasus": 1000000,
    "Bacterium Bullaris": 1152500, "Bacterium Cerbrus": 1689800, "Bacterium Informem": 8418000,
    "Bacterium Nebulus": 9116600, "Bacterium Omentum": 4638900, "Bacterium Scopulum": 8633800,
    "Bacterium Tela": 1949000, "Bacterium Verrata": 3897000, "Bacterium Vesicula": 1000000,
    "Bacterium Volu": 7774700,
    "Cactoida Cortexum": 3667600, "Cactoida Lapis": 2483600, "Cactoida Peperatis": 2483600,
    "Cactoida Pullulanta": 3667600, "Cactoida Vermis": 16202800,
    "Clypeus Lacrimam": 8418000, "Clypeus Margaritus": 11873200, "Clypeus Speculumi": 16202800,
    "Concha Aureolas": 7774700, "Concha Biconcavis": 19010800, "Concha Labiata": 2352400,
    "Concha Renibus": 4572400,
    "Electricae Pluma": 6284600, "Electricae Radialem": 6284600,
    "Fonticulua Campestris": 1000000, "Fonticulua Digitos": 1804100, "Fonticulua Fluctus": 20000000,
    "Fonticulua Lapida": 3111000, "Fonticulua Segmentatus": 19010800, "Fonticulua Upupam": 5727600,
    "Frutexa Acus": 7774700, "Frutexa Collum": 1639800, "Frutexa Fera": 1632500,
    "Frutexa Flabellum": 1808900, "Frutexa Flammasis": 10326000, "Frutexa Metallicum": 1632500,
    "Frutexa Sponsae": 5988000,
    "Fumerola Aquatis": 6284600, "Fumerola Carbosis": 6284600, "Fumerola Extremus": 16202800,
    "Fumerola Nitris": 7500900,
    "Fungoida Bullarum": 3703200, "Fungoida Gelata": 3330300, "Fungoida Setisis": 1670100,
    "Fungoida Stabitis": 2680300,
    "Osseus Cornibus": 1483000, "Osseus Discus": 12934900, "Osseus Fractus": 4027800,
    "Osseus Pellebantus": 9739000, "Osseus Pumice": 3156300, "Osseus Spiralis": 2404700,
    "Recepta Conditivus": 14313700, "Recepta Deltahedronix": 16202800, "Recepta Umbrux": 12934900,
    "Stratum Araneamus": 2448900, "Stratum Cucumisis": 16202800, "Stratum Excutitus": 2448900,
    "Stratum Frigus": 2637500, "Stratum Laminamus": 2788300, "Stratum Limaxus": 1362000,
    "Stratum Paleas": 1362000, "Stratum Tectonicas": 19010800,
    "Tubus Cavas": 11873200, "Tubus Compagibus": 7774700, "Tubus Conifer": 2415500,
    "Tubus Rosarium": 2637500, "Tubus Sororibus": 5727600,
    "Tussock Albata": 3252500, "Tussock Capillum": 7025800, "Tussock Caputus": 3472400,
    "Tussock Catena": 1766600, "Tussock Cultro": 1766600, "Tussock Divisa": 1766600,
    "Tussock Ignis": 1849000, "Tussock Pennata": 5853800, "Tussock Pennatis": 1000000,
    "Tussock Propagito": 1000000, "Tussock Serrati": 4447100, "Tussock Stigmasis": 19010800,
    "Tussock Triticum": 7774700, "Tussock Ventusa": 3227700, "Tussock Virgam": 14313700,
    "Amphora Plant": 3626400, "Bark Mounds": 1471900, "Sinuous Tubers": 3425600,
}

GENUS_VALUE_RANGE = {}
for species, value in SPECIES_VALUES.items():
    first = species.split(" ")[0]
    genus = first if first in GENUS_COLONY_M else species
    lo, hi = GENUS_VALUE_RANGE.get(genus, (value, value))
    GENUS_VALUE_RANGE[genus] = (min(lo, value), max(hi, value))
GENUS_VALUE_RANGE.setdefault("Anemone", (1499900, 5100900))
GENUS_VALUE_RANGE.setdefault("Brain Tree", (3565100, 3565100))

ROCKY = {"Rocky body", "High metal content body"}
ICY = {"Icy body", "Rocky ice body"}
PREDICTION_RULES = {
    "Bacterium": (None, (20, 400), 0.61, None, False),
    "Tussock": ({"carbon dioxide", "ammonia", "argon", "methane", "sulphur dioxide", "water", "nitrogen"}, (145, 197), 0.28, ROCKY, False),
    "Stratum": ({"carbon dioxide", "ammonia", "sulphur dioxide", "water", "oxygen"}, (165, 400), 0.58, ROCKY, False),
    "Cactoida": ({"carbon dioxide", "ammonia", "water"}, (160, 197), 0.28, ROCKY, False),
    "Clypeus": ({"carbon dioxide", "water"}, (190, 455), 0.28, ROCKY, False),
    "Concha": ({"carbon dioxide", "ammonia", "water", "nitrogen"}, (160, 200), 0.28, ROCKY, False),
    "Frutexa": ({"carbon dioxide", "ammonia", "sulphur dioxide", "water", "nitrogen"}, (146, 200), 0.28, ROCKY, False),
    "Fonticulua": ({"argon", "neon", "methane", "nitrogen", "oxygen", "carbon dioxide"}, (50, 150), 0.28, ICY, False),
    "Fungoida": ({"carbon dioxide", "ammonia", "argon", "methane"}, (160, 210), 0.28, ROCKY | ICY, False),
    "Osseus": ({"carbon dioxide", "ammonia", "argon", "methane", "nitrogen"}, (160, 200), 0.28, ROCKY | ICY, False),
    "Aleoida": ({"carbon dioxide", "ammonia"}, (152, 197), 0.28, ROCKY, False),
    "Electricae": ({"argon", "neon", "helium"}, (50, 150), 0.28, {"Icy body"}, False),
    "Recepta": ({"sulphur dioxide", "carbon dioxide"}, (130, 300), 0.28, ROCKY | ICY, False),
    "Tubus": ({"carbon dioxide", "ammonia", "argon", "methane", "nitrogen"}, (160, 197), 0.16, {"Rocky body"}, False),
    "Fumerola": ({"carbon dioxide", "ammonia", "argon", "methane", "sulphur dioxide", "water"}, (50, 450), 0.28, None, True),
}


def species_value(species_localised):
    reference = bio_reference.species_info(species_localised)
    if reference and reference.get("value") is not None:
        return reference["value"]
    return SPECIES_VALUES.get(species_localised)


def genus_info(genus_localised):
    lo, hi = GENUS_VALUE_RANGE.get(genus_localised, (None, None))
    reference = bio_reference.genus_info(genus_localised)
    if reference:
        lo = reference.get("min_value") if reference.get("min_value") is not None else lo
        hi = reference.get("max_value") if reference.get("max_value") is not None else hi
    return {
        "name": genus_localised,
        "min_value": lo,
        "max_value": hi,
        "colony_m": GENUS_COLONY_M.get(genus_localised),
    }


def predict_genera(planet_class, atmosphere, temp_k, gravity_g, volcanism):
    atmo = (atmosphere or "").lower()
    if "thin" not in atmo or temp_k is None or gravity_g is None:
        return []
    has_volcanism = bool(volcanism)
    out = []
    for genus, (keywords, (t_lo, t_hi), g_max, classes, needs_volcanism) in PREDICTION_RULES.items():
        if keywords is not None and not any(k in atmo for k in keywords):
            continue
        if not (t_lo <= float(temp_k) <= t_hi) or float(gravity_g) > g_max:
            continue
        if classes is not None and planet_class not in classes:
            continue
        if needs_volcanism and not has_volcanism:
            continue
        out.append(genus_info(genus))
    return out
