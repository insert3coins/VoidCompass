"""Example expeditions (5.6.1): real community expeditions, to look through
or to fly. Distant Worlds 3 is added once per commander, paused, so nothing
is tracked until you RESUME it; the others wait in the NEW form.

Distant Worlds 3 ran from January to May 3312: from the Colonia region out
to Beagle Point, then around the far side of the galaxy to Sagittarius A*.
The waypoints, landing sites and dates are as its organisers published them
(https://distantworlds3.space/waypoints/); each system's position and body
name were checked against EDSM, so the stops tick off in game.
"""
from __future__ import annotations

# (waypoint, name, system, body, latitude, longitude, deadline, galactic x/y/z)
DISTANT_WORLDS_3 = (
    (0, "Carrier alpha", "Spoihaae XE-X d2-9", "Spoihaae XE-X d2-9 A 1", None, None, "25 Jan 3312",
     [-9346.125, -1472.09375, 19659.0625]),
    (1, "Rendezvous Point", "Rendezvous Point", "Rendezvous Point 3 c", -80.9136, -12.9063, "1 Feb 3312",
     [6026.09375, -5.0625, 42547.59375]),
    (2, "The Seldowitch Nebula", "Thuecheae WR-H d11-54", "Thuecheae WR-H d11-54 13 b", -84.28, -96.10, "8 Feb 3312",
     [-2269.5625, -65.15625, 53715.1875]),
    (3, "Beagle Point", "Beagle Point", "Beagle Point 2", -59.57, -112.52, "15 Feb 3312",
     [-1111.5625, -134.21875, 65269.75]),
    (4, "Eclipsion Halo", "Eictach KU-D d13-4", "Eictach KU-D d13-4 7 a a", -53.8, 139.0, "22 Feb 3312",
     [8112.625, -231.46875, 60245.53125]),
    (5, "Glaciem Nebula", "Blo Chroa XO-I d9-36", "Blo Chroa XO-I d9-36 4 d", -17.61, -79.64, "1 Mar 3312",
     [5964.4375, 73.53125, 53514.1875]),
    (6, "Veil's Ember", "Byua Auwsy NR-Q b46-6", "Byua Auwsy NR-Q b46-6 3", -51.013, 72.188, "8 Mar 3312",
     [10004.3125, 67.96875, 47307.03125]),
    (7, "Guardian of the Twins", "Byae Aowsy GR-N d6-52", "Byae Aowsy GR-N d6-52 4 f", 20.90, 25.62, "15 Mar 3312",
     [14407.625, 17.5, 44312.59375]),
    (8, "Khazad-dûm", "Roefoo ZE-H d10-0", "Roefoo ZE-H d10-0 AB 1", 47.998, 165.430, "29 Mar 3312",
     [21481.40625, -1004.5625, 43369.4375]),
    (9, "Phlegethon's Sentinels", "Phreia Byio PT-V c17-0", "Phreia Byio PT-V c17-0 2", -45.94, -138.11, "5 Apr 3312",
     [23977.53125, -620.25, 36817.71875]),
    (10, "Scylla and Charybdis", "Phrooe Blou AA-A h62", "Phrooe Blou AA-A h62 AB 1 c a", 26.16, -159.19, "12 Apr 3312",
     [18971.875, -72.5625, 34278.6875]),
    (11, "Starlit Dreamscape", "Hypua Pruae ZR-H d11-59", "Hypua Pruae ZR-H d11-59 2 a", 57.59, 17.66, "19 Apr 3312",
     [18451.46875, -94.8125, 25533.1875]),
    (12, "Syrenthis Verge", "Phrua Flyuae ZE-A e7", "Phrua Flyuae ZE-A e7 A 3 a", -7.64, -119.35, "26 Apr 3312",
     [11664.09375, -1072.0625, 23310.84375]),
    (13, "A Vestige of the Teal Nebula", "Eorl Auwsy SY-Z d13-971", "Eorl Auwsy SY-Z d13-971 6 a", 68.016, -128.472, "3 May 3312",
     [4929.53125, 177.875, 20649.0625]),
    (14, "Isegrim's View", "Huemo AA-A h256", "Huemo AA-A h256 B 1 b", -86.52, -146.01, "10 May 3312",
     [2566.125, -1996.5, 26382.71875]),
    # Near Sagittarius A*: the final base camp.
    (15, "Sagittarius A*", "Stuemeae EG-Y d4548", "Stuemeae EG-Y d4548 2 a", 32.328, 108.838, "17 May 3312",
     [6.125, -23.6875, 25913.3125]),
)



# (waypoint, base camp, system, body, latitude, longitude, note, galactic x/y/z): the base camps from the
# Elite Dangerous wiki's tables, each system and body checked against EDSM.
DISTANT_WORLDS_1 = (
    (1, "Laika's Rest", 'Fine Ring Sector JH-V c2-4', 'Fine Ring Sector JH-V c2-4 A 1', -19.15, 85.02, 'Base camp, 15 Jan 3302', [509.71875, 32.53125, 858.25]),
    (2, "Tinné's Endevour", 'NGC 6530 WFI 16706', 'NGC 6530 WFI 16706 A 1 a', -12.71, 70.28, 'Base camp, 22 Jan 3302', [-470.71875, -102.28125, 4465.0625]),
    (3, 'Camp Baatuta', 'Omega Sector EL-Y d60', 'Omega Sector EL-Y d60 2 a', 18.44, -139.3, 'Base camp, 23 Jan 3302', [-1420.34375, -68.34375, 5306.53125]),
    (4, 'Mt. Magellan', 'Eagle Sector EL-Y d203', 'Eagle Sector EL-Y d203 6 a', 40.36, 167.04, 'Base camp, 25 Jan 3302', [-2036.8125, 99.65625, 6687.0625]),
    (5, "Drake's Ridge", 'NGC 6357 Sector DL-Y e22', 'NGC 6357 Sector DL-Y e22 2', 47.77, -95.71, 'Base camp, 29 Jan 3302', [975.84375, 162.90625, 8117.90625]),
    (6, 'The Zheng He Plateau', 'Blaa Hypai UC-G c12-6', 'Blaa Hypai UC-G c12-6 2 a', 19.51, 162.19, 'Base camp, 4 Feb 3302', [1221.59375, -644.3125, 12258.125]),
    (7, 'da Gama Trench', 'Greae Phio LS-L c23-221', 'Greae Phio LS-L c23-221 1 b', 16.1, -167.73, 'Base camp, 7 Feb 3302', [1342.84375, -499.40625, 16591.125]),
    (8, 'Camp Uluru', 'Speamoea WU-E d12-543', 'Speamoea WU-E d12-543 C 1', -67.07, -104.66, 'Base camp, 11 Feb 3302', [2341.59375, -1834.5, 20462.375]),
    (9, 'Mt. Hillary', 'Athaip CR-C b55-4', 'Athaip CR-C b55-4 2 c', -15.82, -72.29, 'Base camp, 14 Feb 3302', [506.84375, -1022.71875, 23168.03125]),
    (10, "Tereshkova's Ridge", 'Myriesly EC-B c27-381', 'Myriesly EC-B c27-381 AB 3 b', -70.26, 47.59, 'Base camp, 17 Feb 3302', [-528.0625, 38.875, 25726.5625]),
    (11, 'Armstrong Landing', 'Stuemeae KM-W c1-342', 'Stuemeae KM-W c1-342 1 b', 57.25, 78.0, 'Base camp, 18 Feb 3302', [26.34375, -20.5625, 25899.25]),
    (12, "Gagarin's Reach", 'Nyuena JS-B d342', 'Nyuena JS-B d342 4 f a', -66.88, -96.0, 'Base camp, 22 Feb 3302', [29.09375, 1976.53125, 25859.5]),
    (13, 'The Needle', 'Phipoea DD-F c26-1311', 'Phipoea DD-F c26-1311 3 e', 24.58, -178.4, 'Base camp, 25 Feb 3302', [-482.40625, 513.09375, 28225.0625]),
    (14, 'Chrea Cauldron', 'Dryao Chrea VU-P e5-7481', 'Dryao Chrea VU-P e5-7481 B 3 a', -19.63, 39.73, 'Base camp, 26 Feb 3302', [-1105.125, 407.71875, 29433.84375]),
    (15, 'Gemstone Canyon', 'Eorld Byoe YA-W e2-4084', 'Eorld Byoe YA-W e2-4084 1 b', 7.7, -103.58, 'Base camp, 27 Feb 3302', [-1259.84375, -177.4375, 30270.28125]),
    (16, 'The Mound', 'Eok Gree TO-Q e5-3167', 'Eok Gree TO-Q e5-3167 2 d', 26.63, -120.95, 'Base camp, 28 Feb 3302', [-1502.9375, -329.46875, 30671.1875]),
    (17, 'The Sacagawea Tundra', 'Pheia Briae DK-A e303', 'Pheia Briae DK-A e303 8', 83.4, 35.45, 'Base camp, 5 Mar 3302', [1097.6875, 449.40625, 36082.8125]),
    (18, 'Camp Amundsen', 'Greeroi MD-Q d6-5', 'Greeroi MD-Q d6-5 B 1', -38.05, -82.51, 'Base camp, 8 Mar 3302', [4578.6875, 1052.34375, 37904.5]),
    (19, 'Columbus Basin', 'Rendezvous Point', 'Rendezvous Point 5 a', 9.58, -35.59, 'Base camp, 12 Mar 3302', [6026.09375, -5.0625, 42547.59375]),
    (20, 'The Pit', 'Oupailks BB-M c8-5', 'Oupailks BB-M c8-5 1', 3.73, -135.7, 'Base camp, 15 Mar 3302', [6776.71875, 376.78125, 46679.59375]),
    (21, 'Shackleton Plateau', 'Qautheia BA-A e0', 'Qautheia BA-A e0 A 1 a', 74.07, 141.47, 'Base camp, 21 Mar 3302', [7847.34375, 3.125, 55262.40625]),
    (22, 'Desolation Ridge', 'Cheae Eurl AA-A e0', 'Cheae Eurl AA-A e0 7', -48.63, 108.72, 'Base camp, 25 Mar 3302', [7632.3125, 3.625, 60397.75]),
    (23, "Darwin's Legacy", 'Beagle Point', 'Beagle Point 2', 48.56, -35.57, 'Base camp, 2 Apr 3302', [-1111.5625, -134.21875, 65269.75]),
)

DISTANT_WORLDS_2 = (
    (2, 'Roald Landing', 'Omega Sector VE-Q b5-15', 'Omega Sector VE-Q b5-15 7 b', 34.283, 79.552, 'Base camp, 18 Jan 3305', [-1444.3125, -85.8125, 5319.9375]),
    (3, 'Conflux Delta Site', 'Pru Aescs NC-M d7-192', 'Pru Aescs NC-M d7-192 A 3 a', -53.348, -48.923, 'Base camp, 1 Feb 3305. The abandoned Conflux Delta Site settlement', [-3183.53125, 73.59375, 8595.65625]),
    (4, 'Shepard Shallows', 'Clooku EW-Y c3-197', 'Clooku EW-Y c3-197 5 g a', 56.305, 111.854, 'Base camp, 8 Feb 3305', [-5476.1875, -61.84375, 11929.84375]),
    (5, 'Polo Harbour', 'Boewnst KS-S c20-959', 'Boewnst KS-S c20-959 A 2 a', 62.753, 48.669, 'Base camp, 15 Feb 3305. A surface port, the last on the road to Colonia', [-6195.46875, -140.28125, 16462.0625]),
    (6, 'New Aloros Ravine', 'Dryau Ausms KG-Y e3390', 'Dryau Ausms KG-Y e3390 AB 8 a a', 54.623, 161.206, 'Base camp, 22 Feb 3305', [-1523.75, 1340.6875, 20976.59375]),
    (7, 'Armstrong Landing', 'Stuemeae KM-W c1-342', 'Stuemeae KM-W c1-342 1 b', 58.078, 79.594, 'Base camp, 1 Mar 3305', [26.34375, -20.5625, 25899.25]),
    (8, 'Hades Edge', 'Swoals IL-Y e0', 'Swoals IL-Y e0 B 1', 59.588, -55.919, 'Base camp, 22 Mar 3305. Reachable only with neutron boosts or FSD injections', [2302.84375, 2852.1875, 32393.5625]),
    (9, 'Tranquility Valley', 'Phroi Bluae QI-T e3-3454', 'Phroi Bluae QI-T e3-3454 3 a', -23.467, 18.066, 'Base camp, 29 Mar 3305', [-681.09375, -950.5625, 34219.34375]),
    (10, 'Mors Pit', 'Bleethuae NI-B d674', 'Bleethuae NI-B d674 2 d a', -28.177, -177.98, 'Base camp, 5 Apr 3305', [17.3125, -669.46875, 37357.53125]),
    (11, 'Magnificent Desolation', 'Smootoae QY-S d3-202', 'Smootoae QY-S d3-202 3 a', -68.481, 64.218, 'Base camp, 19 Apr 3305', [-0.53125, 1.75, 51798.25]),
    (12, 'Legacy Crater', 'Beagle Point', 'Beagle Point 2', -16.001, 169.212, 'Base camp, 13 Jun 3305', [-1111.5625, -134.21875, 65269.75]),
)

# A Grand Day Out (DRX, 3303): a Bubble-side tour for new explorers. Only the ruins had a landing site.
GRAND_DAY_OUT = (
    (2, "Alcazar's Hope", 'Merope', 'Merope 2 a', None, None, "Merope 2 a, in the Pleiades: in 3303 the meet was on the plains outside Alcazar's Hope, 30 km from twin barnacle sites", [-78.59375, -149.625, -340.53125]),
    (3, 'Betelgeuse', 'Betelgeuse', 'Betelgeuse 2', None, None, 'A red supergiant, with a landable second planet for the photographs', [169.40625, -72.5, -462.625]),
    (4, 'The Witch Head Nebula', 'HIP 23759', '', None, None, 'The gateway to Orion, past the permit-locked systems; within reach on a 22 ly jump range', [359.84375, -385.53125, -718.375]),
    (5, 'The Orion Nebula', 'PMD2009 48', '', None, None, 'The Orion Nebula Tourist Centre, in the heart of the nebula', [594.90625, -431.4375, -1071.78125]),
    (6, 'Messier 78', 'Trapezium Sector CB-W c2-4', '', None, None, "Look back at Barnard's Loop and the Orion Nebula", [537.75, -321.40625, -1138.53125]),
    (7, 'Back to the Witch Head', 'HIP 23759', '', None, None, "If you can't plot straight to the ruins from here, go by HIP 22588", [359.84375, -385.53125, -718.375]),
    ('7A', 'HIP 22588', 'HIP 22588', '', None, None, 'The way round to the ruins', [324.65625, -400.03125, -591.03125]),
    (8, 'Guardian ruins', 'Synuefe TP-F b44-0', 'Synuefe TP-F b44-0 CD 1', 31.97, -100.16, 'Twin Guardian ruins sites, millions of years old', [838.75, -197.84375, -111.84375]),
    (9, 'Back to the bubble', 'Omicron Ursae Majoris', '', None, None, 'Home, at your own pace', [-58.75, 105.125, -132.59375]),
)

PALLAENI = [112.6875, 47.125, 128.4375]
OMICRON_URSAE_MAJORIS = [-58.75, 105.125, -132.59375]

def _stops(rows):
    """Waypoint rows as the stops the expedition manager takes: each landing
    site a surface stop, a body without one a planet stop."""
    return [{"name": system, "body": body, "lat": lat, "lon": lon, "coords": coords,
             "kind": "surface" if lat is not None else "planet" if body else "system",
             "title": f"Waypoint {number} · {name}", "note": note}
            for number, name, system, body, lat, lon, note, coords in rows]


def _dw3_rows():
    return [(number, name, system, body, lat, lon,
             f"Due {deadline}" + ("" if lat is not None else ". No landing site given: its orbit carries it through a white dwarf's jet"), coords)
            for number, name, system, body, lat, lon, deadline, coords in DISTANT_WORLDS_3]


EXAMPLES = {
    "distant_worlds_3": {
        "name": "Distant Worlds 3 (example)",
        "description": ("The community expedition of January to May 3312: from the Colonia region to Beagle Point, then around "
                        "the far side of the galaxy to Sagittarius A*. Sixteen waypoints, each a landing site. An example to look "
                        "through; RESUME it to fly it yourself."),
        "start_system": "Colonia", "start_pos": [-9530.5, -910.28125, 19808.125],
        "source_url": "https://distantworlds3.space/waypoints/",
        "credit": "Route: the Distant Worlds 3 organisers, distantworlds3.space",
        # Every commander gets this one; the others wait in the NEW form.
        "seed": True,
        "stops": _stops(_dw3_rows()),
    },
    "distant_worlds_1": {
        "name": "Distant Worlds (example)",
        "description": ("The first great community expedition, January to April 3302: from Pallaeni through the core nebulae "
                        "(the Lagoon, the Omega, the Eagle) to Sagittarius A*, then on to Beagle Point. Twenty-three base camps, "
                        "each a landing site. An example; RESUME it to fly it yourself."),
        "start_system": "Pallaeni", "start_pos": PALLAENI,
        "source_url": "https://elite-dangerous.fandom.com/wiki/Distant_Worlds",
        "credit": "Route: the Distant Worlds base camps, as the Elite Dangerous wiki records them",
        "stops": _stops(DISTANT_WORLDS_1),
    },
    "distant_worlds_2": {
        "name": "Distant Worlds 2 (example)",
        "description": ("The sequel, January to June 3305: from Pallaeni along the road to Colonia, through the galactic core to "
                        "Sagittarius A*, out to the Aphelion and on to Beagle Point. Eleven base camps, each a landing site, the "
                        "abandoned Conflux Delta Site among them. An example; RESUME it to fly it yourself."),
        "start_system": "Pallaeni", "start_pos": PALLAENI,
        "source_url": "https://elite-dangerous.fandom.com/wiki/Distant_Worlds_II",
        "credit": "Route: the Distant Worlds 2 base camps, as the Elite Dangerous wiki records them",
        "stops": _stops(DISTANT_WORLDS_2),
    },
    "grand_day_out": {
        "name": "A Grand Day Out (example)",
        "description": ("A short one, July to August 3303: Deep Recon X's training trip for new explorers, close to home. The "
                        "Pleiades barnacles, Betelgeuse, the Witch Head and Orion nebulae, Messier 78 and twin Guardian ruins, then "
                        "back to the bubble. An example; RESUME it to fly it yourself."),
        "start_system": "Omicron Ursae Majoris", "start_pos": OMICRON_URSAE_MAJORIS,
        "source_url": "https://elite-dangerous.fandom.com/wiki/Grand_Day_Out",
        "credit": "Route: Deep Recon X's A Grand Day Out, as the Elite Dangerous wiki records it",
        "stops": _stops(GRAND_DAY_OUT),
    },
}
