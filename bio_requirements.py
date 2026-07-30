"""Species-level exobiology spawn requirements.

Vendored from Silarn's EDMC-BioScan, which publishes these rulesets under the
GNU General Public License version 2 or later; VoidCompass uses them under
GPL-3.0-only. The upstream project compiles them from Canonn Research Group
data, the community Codex NSP / Bio requirements spreadsheet and the Deep
Space Network.

    source: https://github.com/Silarn/EDMC-BioScan
    path:   src/bio_scan/bio_data/rulesets/
    commit: 5f0d2e445a95681bf2e85223f883d5c552a7726b

The data is reproduced as published, including the upstream authors' own
accuracy caveats, so a prediction never claims more confidence than the
observations behind it. Keys are the raw Codex entry identifiers that Elite
writes into ScanOrganic and CodexEntry, so they join directly to journal
payloads without name matching.

Regenerate rather than hand-edit.
"""

from typing import Mapping

CATALOG: dict[str, dict[str, Mapping]] = {
    # ---- aleoida.py ----
    '$Codex_Ent_Aleoids_Genus_Name;': {
        '$Codex_Ent_Aleoids_01_Name;': {
            'name': 'Aleoida Arcus',
            'value': 7252500,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 175.0,
                    'max_temperature': 180.0,
                    'min_pressure': 0.0161,
                    'body_type': ['Rocky body', 'High metal content body'],
                    'volcanism': 'None'
                }
            ],
        },
        '$Codex_Ent_Aleoids_02_Name;': {
            'name': 'Aleoida Coronamus',
            'value': 6284600,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 180.0,
                    'max_temperature': 190.0,
                    'min_pressure': 0.025,
                    'body_type': ['Rocky body', 'High metal content body'],
                    'volcanism': 'None'
                }
            ],
        },
        '$Codex_Ent_Aleoids_03_Name;': {
            'name': 'Aleoida Spica',
            'value': 3385200,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 170.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                    'body_type': ['Rocky body', 'High metal content body'],
                    'regions': ['!orion-cygnus-core', '!sagittarius-carina-core']
                }
            ],
        },
        '$Codex_Ent_Aleoids_04_Name;': {
            'name': 'Aleoida Laminiae',
            'value': 3385200,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 152.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                    'body_type': ['Rocky body', 'High metal content body'],
                    'regions': ['orion-cygnus', 'sagittarius-carina']
                }
            ],
        },
        '$Codex_Ent_Aleoids_05_Name;': {
            'name': 'Aleoida Gravis',
            'value': 12934900,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 190.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.054,
                    'body_type': ['Rocky body', 'High metal content body'],
                    'volcanism': 'None'
                }
            ],
        }
    },
    # ---- anemone.py ----
    '$Codex_Ent_Sphere_Name;': {
        '$Codex_Ent_Sphere_Name;': {
            'name': 'Luteolum Anemone',
            'value': 1499900,
            'rulesets': [
                {
                    'min_gravity': 0.044,
                    'max_gravity': 1.28,
                    'max_temperature': 440.0,
                    'min_temperature': 200.0,
                    'volcanism': ['metallic', 'silicate', 'rocky', 'water'],
                    'body_type': ['Rocky body'],
                    'star': [('B', 'IV'), ('B', 'V')],
                    'regions': ['anemone-a']
                }
            ],
        },
        '$Codex_Ent_SphereABCD_01_Name;': {
            'name': 'Croceum Anemone',
            'value': 1499900,
            'rulesets': [
                {
                    'min_gravity': 0.047,
                    'max_gravity': 0.37,
                    'max_temperature': 440.0,
                    'min_temperature': 200.0,
                    'volcanism': ['silicate', 'rocky', 'metallic'],
                    'body_type': ['Rocky body'],
                    'star': [('B', 'V'), ('B', 'VI'), ('A', 'III')],
                    'regions': ['anemone-a']
                }
            ],
        },
        '$Codex_Ent_SphereABCD_02_Name;': {
            'name': 'Puniceum Anemone',
            'value': 1499900,
            'rulesets': [
                {
                    'min_gravity': 0.17,
                    'max_gravity': 2.52,
                    'max_temperature': 800.0,
                    'min_temperature': 65.0,
                    'volcanism': 'None',
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'star': ['O'],
                    'regions': ['anemone-a']
                },
                {
                    'min_gravity': 0.17,
                    'max_gravity': 2.52,
                    'max_temperature': 800.0,
                    'min_temperature': 65.0,
                    'volcanism': ['carbon dioxide geysers'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'star': ['O'],
                    'regions': ['anemone-a']
                }
            ],
        },
        '$Codex_Ent_SphereABCD_03_Name;': {
            'name': 'Roseum Anemone',
            'value': 1499900,
            'rulesets': [
                {
                    'min_gravity': 0.045,
                    'max_gravity': 0.37,
                    'max_temperature': 440.0,
                    'min_temperature': 200.0,
                    'volcanism': ['silicate', 'rocky', 'metallic'],
                    'body_type': ['Rocky body'],
                    'star': [('B', 'I'), ('B', 'II'), ('B', 'III'), ('B', 'IV')],
                    'regions': ['anemone-a']
                }
            ],
        },
        '$Codex_Ent_SphereEFGH_01_Name;': {
            'name': 'Rubeum Bioluminescent Anemone',
            'value': 1499900,
            'rulesets': [
                {
                    'min_gravity': 0.036,
                    'max_gravity': 4.61,
                    'min_temperature': 160.0,
                    'max_temperature': 1800.0,
                    'volcanism': 'Any',
                    'body_type': ['Metal rich body', 'High metal content body'],
                    'star': [('B', 'VI'), ['A', 'I'], ['A', 'II'], ['A', 'III'], 'N']
                }
            ],
        },
        '$Codex_Ent_SphereEFGH_02_Name;': {
            'name': 'Prasinum Bioluminescent Anemone',
            'value': 1499900,
            'rulesets': [
                {
                    'min_gravity': 0.036,
                    'min_temperature': 110.0,
                    'max_temperature': 3050.0,
                    'body_type': ['Metal rich body', 'Rocky body', 'High metal content body'],
                    'star': ['O']
                }
            ],
        },
        '$Codex_Ent_SphereEFGH_03_Name;': {
            'name': 'Roseum Bioluminescent Anemone',
            'value': 1499900,
            'rulesets': [
                {
                    'min_gravity': 0.036,
                    'max_gravity': 4.61,
                    'min_temperature': 400.0,
                    'volcanism': 'Any',
                    'body_type': ['Metal rich body', 'High metal content body'],
                    'star': [('B', 'I'), ('B', 'II'), ('B', 'III')]
                }
            ],
        },
        '$Codex_Ent_SphereEFGH_Name;': {
            'name': 'Blatteum Bioluminescent Anemone',
            'value': 1499900,
            'rulesets': [
                {
                    'min_temperature': 220.0,
                    'volcanism': 'Any',
                    'body_type': ['Metal rich body', 'High metal content body'],
                    'star': [('B', 'IV'), ('B', 'V')],
                    'regions': ['anemone-a']
                }
            ],
        },
    },
    # ---- bacterium.py ----
    '$Codex_Ent_Bacterial_Genus_Name;': {
        '$Codex_Ent_Bacterial_01_Name;': {
            'name': 'Bacterium Aurasus',
            'value': 1000000,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body', 'Rocky ice body'],
                    'min_gravity': 0.039,
                    'max_gravity': 0.608,
                    'min_temperature': 145.0,
                    'max_temperature': 400.0,
                }
            ],
        },
        '$Codex_Ent_Bacterial_02_Name;': {
            'name': 'Bacterium Nebulus',
            'value': 5289900,
            'rulesets': [
                {
                    'atmosphere': ['Helium'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.4,
                    'max_gravity': 0.55,
                    'min_temperature': 20.0,
                    'max_temperature': 21.0,
                    'min_pressure': 0.067
                },
                { # Only one sample, likely inaccurate
                    'atmosphere': ['Helium'],
                    'body_type': ['Rocky ice body'],
                    'min_gravity': 0.4,
                    'max_gravity': 0.7,
                    'min_temperature': 20.0,
                    'max_temperature': 21.0,
                    'min_pressure': 0.067
                }
            ],
        },
        '$Codex_Ent_Bacterial_03_Name;': {
            'name': 'Bacterium Scopulum',
            'value': 4934500,
            'rulesets': [
                {
                    'atmosphere': ['Argon'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.15,
                    'max_gravity': 0.26,
                    'min_temperature': 56,
                    'max_temperature': 150,
                    'volcanism': ['carbon dioxide', 'methane']
                },
                {
                    'atmosphere': ['Helium'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.48,
                    'max_gravity': 0.51,
                    'min_temperature': 20,
                    'max_temperature': 21,
                    'min_pressure': 0.075,
                    'volcanism': ['methane']
                },
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.025,
                    'max_gravity': 0.047,
                    'min_temperature': 84,
                    'max_temperature': 110,
                    'min_pressure': 0.03,
                    'volcanism': ['methane']
                },
                {
                    'atmosphere': ['Neon'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.025,
                    'max_gravity': 0.61,
                    'min_temperature': 20,
                    'max_temperature': 65,
                    'max_pressure': 0.008,
                    'volcanism': ['carbon dioxide', 'methane']
                },
                {
                    'atmosphere': ['NeonRich'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.025,
                    'max_gravity': 0.61,
                    'min_temperature': 20,
                    'max_temperature': 65,
                    'min_pressure': 0.005,
                    'volcanism': ['carbon dioxide', 'methane']
                },
                {
                    'atmosphere': ['Nitrogen'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.2,
                    'max_gravity': 0.3,
                    'min_temperature': 60,
                    'max_temperature': 70,
                    'volcanism': ['carbon dioxide', 'methane']
                },
                {
                    'atmosphere': ['Oxygen'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.27,
                    'max_gravity': 0.40,
                    'min_temperature': 150,
                    'max_temperature': 220,
                    'min_pressure': 0.01,
                    'volcanism': ['carbon dioxide', 'methane']
                }
            ],
        },
        '$Codex_Ent_Bacterial_04_Name;': {
            'name': 'Bacterium Acies',
            'value': 1000000,
            'rulesets': [
                {
                    'atmosphere': ['Neon'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.255,
                    'max_gravity': 0.61,
                    'min_temperature': 20.0,
                    'max_temperature': 61.0,
                    'max_pressure': 0.01
                }
            ],
        },
        '$Codex_Ent_Bacterial_05_Name;': {
            'name': 'Bacterium Vesicula',
            'value': 1000000,
            'rulesets': [
                {
                    'atmosphere': ['Argon'],
                    'min_gravity': 0.027,
                    'max_gravity': 0.51,
                    'min_temperature': 50.0,
                    'max_temperature': 245.0
                }
            ],
        },
        '$Codex_Ent_Bacterial_06_Name;': {
            'name': 'Bacterium Alcyoneum',
            'value': 1658500,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.376,
                    'min_temperature': 152.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135
                }
            ],
        },
        '$Codex_Ent_Bacterial_07_Name;': {
            'name': 'Bacterium Tela',
            'value': 1949000,
            'rulesets': [
                {
                    'atmosphere': ['Argon'],
                    'body_type': ['Icy body', 'Rocky ice body', 'High metal content body'],
                    'min_gravity': 0.045,
                    'max_gravity': 0.45,
                    'min_temperature': 50.0,
                    # 'max_temperature': 200.0,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['ArgonRich'],
                    'min_gravity': 0.24,
                    'max_gravity': 0.45,
                    'min_temperature': 50.0,
                    'max_temperature': 150.0,
                    'max_pressure': 0.05,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['Ammonia'],
                    'min_gravity': 0.025,
                    'max_gravity': 0.23,
                    'min_temperature': 165.0,
                    'max_temperature': 177.0,
                    'min_pressure': 0.0025,
                    'max_pressure': 0.02,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.45,
                    'max_gravity': 0.61,
                    'min_temperature': 300.0,
                    #'max_temperature': 500.0,
                    'min_pressure': 0.006,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['CarbonDioxide', 'CarbonDioxideRich'],
                    'min_gravity': 0.025,
                    'max_gravity': 0.61,
                    'min_temperature': 167.0,
                    #'max_temperature': 300.0,
                    'min_pressure': 0.006,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['Helium'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.025,
                    'max_gravity': 0.61,
                    'min_temperature': 20.0,
                    'max_temperature': 21.0,
                    'min_pressure': 0.067,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Icy body', 'Rocky body', 'High metal content body'],
                    'min_gravity': 0.026,
                    'max_gravity': 0.126,
                    'min_temperature': 80.0,
                    'max_temperature': 109.0,
                    'min_pressure': 0.012,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['Neon'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.27,
                    'max_gravity': 0.61,
                    'min_temperature': 20.0,
                    'max_temperature': 95.0,
                    'max_pressure': 0.008,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['NeonRich'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.27,
                    'max_gravity': 0.61,
                    'min_temperature': 20.0,
                    'max_temperature': 95.0,
                    'min_pressure': 0.003,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['Nitrogen'],
                    'min_gravity': 0.21,
                    'max_gravity': 0.35,
                    'min_temperature': 55.0,
                    'max_temperature': 80.0,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['Oxygen'],
                    'min_gravity': 0.23,
                    'max_gravity': 0.5,
                    'min_temperature': 150.0,
                    'max_temperature': 240.0,
                    'min_pressure': 0.01,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'min_gravity': 0.18,
                    'max_gravity': 0.61,
                    'min_temperature': 148.0,
                    'max_temperature': 550.0,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'min_gravity': 0.18,
                    'max_gravity': 0.61,
                    'min_temperature': 300.0,
                    'max_temperature': 550.0,
                    'volcanism': 'None'
                },
                {  # Hot thin sulphur dioxide atmos
                    'atmosphere': ['SulphurDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.5,
                    'max_gravity': 0.55,
                    'min_temperature': 500.0,
                    'max_temperature': 650.0,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.063,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['WaterRich'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.315,
                    'max_gravity': 0.44,
                    'min_temperature': 190.0,
                    'max_temperature': 330.0,
                    'min_pressure': 0.01,
                    'volcanism': 'Any'
                }
            ],
        },
        '$Codex_Ent_Bacterial_08_Name;': {
            'name': 'Bacterium Informem',
            'value': 8418000,
            'rulesets': [
                {
                    'atmosphere': ['Nitrogen'],
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body'],
                    'min_gravity': 0.05,
                    'max_gravity': 0.6,
                    'min_temperature': 42.5,
                    'max_temperature': 151.0,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Nitrogen'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.17,
                    'max_gravity': 0.63,
                    'min_temperature': 50.0,
                    'max_temperature': 90.0
                }
            ],
        },
        '$Codex_Ent_Bacterial_09_Name;': {
            'name': 'Bacterium Volu',
            'value': 7774700,
            'rulesets': [
                {
                    'atmosphere': ['Oxygen'],
                    'min_gravity': 0.239,
                    'max_gravity': 0.61,
                    'min_temperature': 143.5,
                    'max_temperature': 246.0,
                    'min_pressure': 0.013,
                }
            ],
        },
        '$Codex_Ent_Bacterial_10_Name;': {
            'name': 'Bacterium Bullaris',
            'value': 1152500,
            'rulesets': [
                {
                    'atmosphere': ['Methane'],
                    'min_gravity': 0.0245,
                    'max_gravity': 0.35,
                    'min_temperature': 67.0,
                    'max_temperature': 109.0
                },
                {
                    'atmosphere': ['MethaneRich'],
                    'min_gravity': 0.44,
                    'max_gravity': 0.6,
                    'min_temperature': 74.0,
                    'max_temperature': 141.0,
                    'min_pressure': 0.01,
                    'max_pressure': 0.05,
                    'volcanism': 'None',
                    'body_type': ['Rocky body', 'High metal content body']
                }
            ],
        },
        '$Codex_Ent_Bacterial_11_Name;': {
            'name': 'Bacterium Omentum',
            'value': 4638900,
            'rulesets': [
                {
                    'atmosphere': ['Argon'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.045,
                    'max_gravity': 0.45,
                    'min_temperature': 50.0,
                    'volcanism': ['nitrogen', 'ammonia']
                },
                {
                    'atmosphere': ['ArgonRich'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.23,
                    'max_gravity': 0.45,
                    'min_temperature': 80.0,
                    'max_temperature': 90.0,
                    'min_pressure': 0.01,
                    'volcanism': ['nitrogen', 'ammonia']
                },
                {
                    'atmosphere': ['Helium'],
                    'min_gravity': 0.4,
                    'max_gravity': 0.51,
                    'min_temperature': 20.0,
                    'max_temperature': 21.0,
                    'min_pressure': 0.065,
                    'body_type': ['Icy body'],
                    'volcanism': ['nitrogen', 'ammonia']
                },
                {
                    'atmosphere': ['Methane'],
                    'min_gravity': 0.0265,
                    'max_gravity': 0.0455,
                    'min_temperature': 84.0,
                    'max_temperature': 108.0,
                    'min_pressure': 0.035,
                    'body_type': ['Icy body'],
                    'volcanism': ['nitrogen', 'ammonia']
                },
                {
                    'atmosphere': ['Neon'],
                    'min_gravity': 0.31,
                    'max_gravity': 0.6,
                    'min_temperature': 20.0,
                    'max_temperature': 61.0,
                    'max_pressure': 0.0065,
                    'body_type': ['Icy body'],
                    'volcanism': ['nitrogen', 'ammonia']
                },
                {
                    'atmosphere': ['NeonRich'],
                    'min_gravity': 0.27,
                    'max_gravity': 0.61,
                    'min_temperature': 20.0,
                    'max_temperature': 93.0,
                    'min_pressure': 0.0027,
                    'body_type': ['Icy body'],
                    'volcanism': ['nitrogen', 'ammonia']
                },
                {
                    'atmosphere': ['Nitrogen'],
                    'min_gravity': 0.2,
                    'max_gravity': 0.26,
                    'min_temperature': 60.0,
                    'max_temperature': 80.0,
                    'body_type': ['Icy body'],
                    'volcanism': ['nitrogen', 'ammonia']
                },
                {
                    'atmosphere': ['WaterRich'],
                    'min_gravity': 0.38,
                    'max_gravity': 0.45,
                    'min_temperature': 190.0,
                    'max_temperature': 330.0,
                    'min_pressure': 0.07,
                    'body_type': ['Icy body'],
                    'volcanism': ['nitrogen', 'ammonia']
                }
            ],
        },
        '$Codex_Ent_Bacterial_12_Name;': {
            'name': 'Bacterium Cerbrus',
            'value': 1689800,
            'rulesets': [
                {
                    'atmosphere': ['SulphurDioxide'],
                    'min_gravity': 0.042,
                    'max_gravity': 0.605,
                    'min_temperature': 132.0,
                    'max_temperature': 500.0,
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body']
                },
                {
                    'atmosphere': ['Water'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.064,
                    'body_type': ['Rocky body', 'High metal content body'],
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Water'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.064,
                    'body_type': ['Rocky body', 'High metal content body'],
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['WaterRich'],
                    'min_gravity': 0.4,
                    'max_gravity': 0.5,
                    'min_temperature': 190.0,
                    'max_temperature': 330.0,
                    'body_type': ['Rocky ice body'],
                    'volcanism': 'None'
                }
            ],
        },
        '$Codex_Ent_Bacterial_13_Name;': {
            'name': 'Bacterium Verrata',
            'value': 3897000,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'Rocky ice body', 'Icy body'],
                    'min_gravity': 0.03,
                    'max_gravity': 0.09,
                    'min_temperature': 160.0,
                    'max_temperature': 180.0,
                    'max_pressure': 0.0135,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['Argon'],
                    'body_type': ['Rocky ice body', 'Icy body'],
                    'min_gravity': 0.165,
                    'max_gravity': 0.33,
                    'min_temperature': 57.5,
                    'max_temperature': 145.0,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['ArgonRich'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.08,
                    'min_temperature': 80.0,
                    'max_temperature': 90.0,
                    'max_pressure': 0.01,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['CarbonDioxide', 'CarbonDioxideRich'],
                    'body_type': ['Rocky ice body', 'Icy body'],
                    'min_gravity': 0.25,
                    'max_gravity': 0.32,
                    'min_temperature': 167.0,
                    'max_temperature': 240.0,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['Helium'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.49,
                    'max_gravity': 0.53,
                    'min_temperature': 20.0,
                    'max_temperature': 21.0,
                    'min_pressure': 0.065,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['Neon'],
                    'body_type': ['Rocky ice body', 'Icy body'],
                    'min_gravity': 0.29,
                    'max_gravity': 0.61,
                    'min_temperature': 20.0,
                    'max_temperature': 51.0,
                    'max_pressure': 0.075,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['NeonRich'],
                    'body_type': ['Rocky ice body', 'Icy body'],
                    'min_gravity': 0.43,
                    'max_gravity': 0.61,
                    'min_temperature': 20.0,
                    'max_temperature': 65.0,
                    'min_pressure': 0.005,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['Nitrogen'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.205,
                    'max_gravity': 0.241,
                    'min_temperature': 60.0,
                    'max_temperature': 80.0,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['Oxygen'],
                    'body_type': ['Rocky ice body', 'Icy body'],
                    'min_gravity': 0.24,
                    'max_gravity': 0.35,
                    'min_temperature': 154.0,
                    'max_temperature': 220.0,
                    'min_pressure': 0.01,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.054,
                    'volcanism': ['water']
                }
            ]
        }
    },
    # ---- brain_tree.py ----
    '$Codex_Ent_Brancae_Name;': {
        '$Codex_Ent_Seed_Name;': {
            'name': 'Roseum Brain Tree',
            'value': 1593700,
            'rulesets': [
                {
                    'min_temperature': 200.0,
                    'max_temperature': 500.0,
                    'volcanism': 'Any',
                    'guardian': True,
                    'region': ['brain-tree']
                }
            ],
        },
        '$Codex_Ent_SeedABCD_01_Name;': {
            'name': 'Gypseeum Brain Tree',
            'value': 1593700,
            'rulesets': [
                {
                    'body_type': ['Rocky body'],
                    'min_temperature': 200.0,
                    'max_temperature': 400.0,
                    'max_gravity': 0.42,
                    'volcanism': ['metallic', 'rocky', 'silicate', 'water'],
                    'guardian': True,
                    'region': ['brain-tree'],
                    'bodies': ['Earthlike body', 'Gas giant with water based life', 'Water giant']
                }
            ],
        },
        '$Codex_Ent_SeedABCD_02_Name;': {
            'name': 'Ostrinum Brain Tree',
            'value': 1593700,
            'rulesets': [
                {
                    'body_type': ['Metal rich body', 'Rocky body', 'High metal content body'],
                    'volcanism': ['metallic', 'rocky', 'silicate'],
                    'guardian': True,
                    'region': ['brain-tree']
                }
            ],
        },
        '$Codex_Ent_SeedABCD_03_Name;': {
            'name': 'Viride Brain Tree',
            'value': 1593700,
            'rulesets': [
                {
                    'body_type': ['Rocky ice body'],
                    'min_temperature': 100.0,
                    'max_temperature': 270.0,
                    'max_gravity': 0.4,
                    'volcanism': 'Any',
                    'guardian': True,
                    'region': ['brain-tree'],
                    'bodies': ['Earthlike body', 'Gas giant with water based life', 'Water giant']
                }
            ],
        },
        '$Codex_Ent_SeedEFGH_01_Name;': {
            'name': 'Aureum Brain Tree',
            'value': 1593700,
            'rulesets': [
                {
                    'body_type': ['Metal rich body', 'High metal content body'],
                    'min_temperature': 300.0,
                    'max_temperature': 500.0,
                    'max_gravity': 2.9,
                    'volcanism': ['metallic', 'rocky', 'silicate'],
                    'guardian': True,
                    'region': ['brain-tree'],
                    #'bodies': ['Earthlike body', 'Gas giant with water based life', 'Water giant']
                }
            ],
        },
        '$Codex_Ent_SeedEFGH_02_Name;': {
            'name': 'Puniceum Brain Tree',
            'value': 1593700,
            'rulesets': [
                {
                    'body_type': ['Metal rich body', 'High metal content body'],
                    'volcanism': 'Any',
                    'guardian': True,
                    'region': ['brain-tree'],
                    'bodies': ['Earthlike body', 'Gas giant with water based life', 'Water giant']
                }
            ],
        },
        '$Codex_Ent_SeedEFGH_03_Name;': {
            'name': 'Lindigoticum Brain Tree',
            'value': 1593700,
            'rulesets': [
                {
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_temperature': 300.0,
                    'max_temperature': 500.0,
                    'max_gravity': 2.7,
                    'volcanism': ['rocky', 'silicate', 'metallic'],
                    'guardian': True,
                    'region': ['brain-tree'],
                    'bodies': ['Earthlike body', 'Gas giant with water based life', 'Water giant']
                }
            ],
        },
        '$Codex_Ent_SeedEFGH_Name;': {
            'name': 'Lividum Brain Tree',
            'value': 1593700,
            'rulesets': [
                {
                    'body_type': ['Rocky body'],
                    'min_temperature': 300.0,
                    'max_temperature': 500.0,
                    'max_gravity': 0.5,
                    'volcanism': ['metallic', 'rocky', 'silicate', 'water'],
                    'guardian': True,
                    'region': ['brain-tree'],
                    #'bodies': ['Earthlike body', 'Gas giant with water based life', 'Water giant']
                }
            ],
        },
    },
    # ---- cactoida.py ----
    '$Codex_Ent_Cactoid_Genus_Name;': {
        '$Codex_Ent_Cactoid_01_Name;': {
            'name': 'Cactoida Cortexum',
            'value': 3667600,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 180.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.025,
                    'volcanism': 'None',
                    'regions': ['orion-cygnus']
                }
            ],
        },
        '$Codex_Ent_Cactoid_02_Name;': {
            'name': 'Cactoida Lapis',
            'value': 2483600,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 160.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                    'regions': ['sagittarius-carina']
                }
            ],
        },
        '$Codex_Ent_Cactoid_03_Name;': {
            'name': 'Cactoida Vermis',
            'value': 16202800,
            'rulesets': [
                {
                    'atmosphere': ['SulphurDioxide'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.265,
                    'max_gravity': 0.276,
                    'min_temperature': 160.0,
                    'max_temperature': 210.0,
                    'max_pressure': 0.005,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'volcanism': ['water']
                }
            ],
        },
        '$Codex_Ent_Cactoid_04_Name;': {
            'name': 'Cactoida Pullulanta',
            'value': 3667600,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 180.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.025,
                    'volcanism': 'None',
                    'regions': ['perseus']
                }
            ],
        },
        '$Codex_Ent_Cactoid_05_Name;': {
            'name': 'Cactoida Peperatis',
            'value': 2483600,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 160.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                    'regions': ['scutum-centaurus']
                }
            ],
        },
    },
    # ---- clypeus.py ----
    '$Codex_Ent_Clypeus_Genus_Name;': {
        '$Codex_Ent_Clypeus_01_Name;': {
            'name': 'Clypeus Lacrimam',
            'value': 8418000,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 190.0,
                    # 'max_temperature': 197.0,
                    'min_pressure': 0.054,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'volcanism': ['water']
                }
            ],
        },
        '$Codex_Ent_Clypeus_02_Name;': {
            'name': 'Clypeus Margaritus',
            'value': 11873200,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 190.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.054,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'volcanism': 'None'
                }
            ],
        },
        '$Codex_Ent_Clypeus_03_Name;': {
            'name': 'Clypeus Speculumi',
            'value': 16202800,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 190.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.055,
                    'body_type': ['Rocky body'],
                    'volcanism': 'None',
                    'distance': 2000.0
                },
                {
                    'atmosphere': ['Water'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'body_type': ['Rocky body'],
                    'volcanism': 'None',
                    'distance': 2000.0
                },
                {
                    'atmosphere': ['Water'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'body_type': ['Rocky body'],
                    'volcanism': ['water'],
                    'distance': 2000.0
                }
            ],
        },
    },
    # ---- concha.py ----
    '$Codex_Ent_Conchas_Genus_Name;': {
        '$Codex_Ent_Conchas_01_Name;': {
            'name': 'Concha Renibus',
            'value': 4572400,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.045,
                    'min_temperature': 176.0,
                    'max_temperature': 177.0,
                    'volcanism': ['silicate', 'metallic']
                },
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 180.0,
                    #'max_temperature': 197.0,
                    'min_pressure': 0.025,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.15,
                    'min_temperature': 78.0,
                    'max_temperature': 100.0,
                    'min_pressure': 0.01,
                    'volcanism': ['silicate', 'metallic']
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.65,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.65,
                    'volcanism': ['water']
                }
            ],
        },
        '$Codex_Ent_Conchas_02_Name;': {
            'name': 'Concha Aureolas',
            'value': 7774700,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 152.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135
                }
            ],
        },
        '$Codex_Ent_Conchas_03_Name;': {
            'name': 'Concha Labiata',
            'value': 2352400,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 150.0,
                    'max_temperature': 200.0,
                    'min_pressure': 0.002,
                    'volcanism': 'None'
                }
            ],
        },
        '$Codex_Ent_Conchas_04_Name;': {
            'name': 'Concha Biconcavis',
            'value': 16777215,
            'rulesets': [
                {
                    'atmosphere': ['Nitrogen'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.053,
                    'max_gravity': 0.275,
                    'min_temperature': 42.0,
                    'max_temperature': 52.0,
                    'max_pressure': 0.0047,
                    'volcanism': 'None'
                }
            ],
        },
    },
    # ---- electricae.py ----
    '$Codex_Ent_Electricae_Genus_Name;': {
        '$Codex_Ent_Electricae_01_Name;': {
            'name': 'Electricae Pluma',
            'value': 6284600,
            'rulesets': [
                {
                    'atmosphere': ['Argon', 'ArgonRich'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.025,
                    'max_gravity': 0.276,
                    'min_temperature': 50.0,
                    'max_temperature': 150.0,
                    'parent_star': ['A', 'N', 'D', 'H', 'AeBe']
                },
                {
                    'atmosphere': ['Neon', 'NeonRich'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.26,
                    'max_gravity': 0.276,
                    'min_temperature': 20.0,
                    'max_temperature': 70.0,
                    'max_pressure': 0.005,
                    'parent_star': ['A', 'N', 'D', 'H', 'AeBe']
                }
            ],
        },
        '$Codex_Ent_Electricae_02_Name;': {
            'name': 'Electricae Radialem',
            'value': 6284600,
            'rulesets': [
                {
                    'atmosphere': ['Argon', 'ArgonRich'],
                    'min_gravity': 0.025,
                    'max_gravity': 0.276,
                    'min_temperature': 50.0,
                    'max_temperature': 150.0,
                    'body_type': ['Icy body'],
                    'nebula': 'all'
                },
                {
                    'atmosphere': ['Neon', 'NeonRich'],
                    'min_gravity': 0.026,
                    'max_gravity': 0.276,
                    'min_temperature': 20.0,
                    'max_temperature': 70.0,
                    'max_pressure': 0.005,
                    'body_type': ['Icy body'],
                    'nebula': 'all'
                }
            ],
        },
    },
    # ---- fonticulua.py ----
    '$Codex_Ent_Fonticulus_Genus_Name;': {
        '$Codex_Ent_Fonticulus_01_Name;': {
            'name': 'Fonticulua Segmentatus',
            'value': 19010800,
            'rulesets': [
                {
                    'atmosphere': ['Neon', 'NeonRich'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.25,
                    'max_gravity': 0.276,
                    'min_temperature': 50.0,
                    'max_temperature': 75.0,
                    'max_pressure': 0.006,
                    'volcanism': 'None'
                }
            ],
        },
        '$Codex_Ent_Fonticulus_02_Name;': {
            'name': 'Fonticulua Campestris',
            'value': 1000000,
            'rulesets': [
                {
                    'atmosphere': ['Argon'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.027,
                    'max_gravity': 0.276,
                    'min_temperature': 50.0,
                    'max_temperature': 150.0
                }
            ],
        },
        '$Codex_Ent_Fonticulus_03_Name;': {
            'name': 'Fonticulua Upupam',
            'value': 5727600,
            'rulesets': [
                {
                    'atmosphere': ['ArgonRich'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.209,
                    'max_gravity': 0.276,
                    'min_temperature': 61.0,
                    'max_temperature': 125.0,
                    'min_pressure': 0.0175
                }
            ],
        },
        '$Codex_Ent_Fonticulus_04_Name;': {
            'name': 'Fonticulua Lapida',
            'value': 3111000,
            'rulesets': [
                {
                    'atmosphere': ['Nitrogen'],
                    'min_gravity': 0.19,
                    'max_gravity': 0.276,
                    'min_temperature': 50.0,
                    'max_temperature': 81.0,
                    'body_type': ['Icy body', 'Rocky ice body']
                }
            ],
        },
        '$Codex_Ent_Fonticulus_05_Name;': {
            'name': 'Fonticulua Fluctus',
            'value': 20000000,
            'rulesets': [
                {
                    'atmosphere': ['Oxygen'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.235,
                    'max_gravity': 0.276,
                    'min_temperature': 143.0,
                    'max_temperature': 200.0,
                    'min_pressure': 0.012
                }
            ],
        },
        '$Codex_Ent_Fonticulus_06_Name;': {
            'name': 'Fonticulua Digitos',
            'value': 1804100,
            'rulesets': [
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.025,
                    'max_gravity': 0.07,
                    'min_temperature': 83.0,
                    'max_temperature': 109.0,
                    'min_pressure': 0.03
                }
            ],
        },
    },
    # ---- frutexa.py ----
    '$Codex_Ent_Shrubs_Genus_Name;': {
        '$Codex_Ent_Shrubs_01_Name;': {
            'name': 'Frutexa Flabellum',
            'value': 1808900,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 152.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                    'regions': ['!scutum-centaurus']
                }
            ],
        },
        '$Codex_Ent_Shrubs_02_Name;': {
            'name': 'Frutexa Acus',
            'value': 7774700,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.237,
                    'min_temperature': 146.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.0029,
                    'volcanism': 'None',
                    'regions': ['orion-cygnus']
                }
            ],
        },
        '$Codex_Ent_Shrubs_03_Name;': {
            'name': 'Frutexa Metallicum',
            'value': 1632500,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 152.0,
                    'max_temperature': 176.0,
                    'max_pressure': 0.01,
                    'volcanism': 'None',
                },
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 146.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.002,
                    'volcanism': 'None',
                },
                { # Only two samples
                    'atmosphere': ['Methane'],
                    'body_type': ['High metal content body'],
                    'min_gravity': 0.05,
                    'max_gravity': 0.1,
                    'min_temperature': 100.0,
                    'max_temperature': 300.0,
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.07,
                    'max_temperature': 400.0,
                    'max_pressure': 0.07,
                    'volcanism': 'None',
                }
            ],
        },
        '$Codex_Ent_Shrubs_04_Name;': {
            'name': 'Frutexa Flammasis',
            'value': 10326000,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 152.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                    'regions': ['scutum-centaurus']
                }
            ],
        },
        '$Codex_Ent_Shrubs_05_Name;': {
            'name': 'Frutexa Fera',
            'value': 1632500,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 146.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.003,
                    'volcanism': 'None',
                    'regions': ['outer']
                }
            ],
        },
        '$Codex_Ent_Shrubs_06_Name;': {
            'name': 'Frutexa Sponsae',
            'value': 5988000,
            'rulesets': [
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.056,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.056,
                    'volcanism': ['water']
                }
            ],
        },
        '$Codex_Ent_Shrubs_07_Name;': {
            'name': 'Frutexa Collum',
            'value': 1639800,
            'rulesets': [
                {
                    'atmosphere': ['SulphurDioxide'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 132.0,
                    'max_temperature': 215.0,
                    'max_pressure': 0.004
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'body_type': ['High metal content body'],
                    'min_gravity': 0.265,
                    'max_gravity': 0.276,
                    'min_temperature': 132.0,
                    'max_temperature': 135.0,
                    'max_pressure': 0.004,
                    'volcanism': 'None'
                }
            ],
        },
    },
    # ---- fumerola.py ----
    '$Codex_Ent_Fumerolas_Genus_Name;': {
        '$Codex_Ent_Fumerolas_01_Name;': {
            'name': 'Fumerola Carbosis',
            'value': 6284600,
            'rulesets': [
                {
                    'atmosphere': ['Argon'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.168,
                    'max_gravity': 0.276,
                    'min_temperature': 57.0,
                    'max_temperature': 150.0,
                    'volcanism': ['carbon', 'methane']
                },
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.025,
                    'max_gravity': 0.047,
                    'min_temperature': 84.0,
                    'max_temperature': 110.0,
                    'min_pressure': 0.03,
                    'volcanism': ['methane magma']
                },
                {
                    'atmosphere': ['Neon'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.26,
                    'max_gravity': 0.276,
                    'min_temperature': 40.0,
                    'max_temperature': 60.0,
                    'volcanism': ['carbon', 'methane']
                },
                {
                    'atmosphere': ['Nitrogen'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.2,
                    'max_gravity': 0.276,
                    'min_temperature': 57.0,
                    'max_temperature': 70.0,
                    'volcanism': ['carbon', 'methane']
                },
                {
                    'atmosphere': ['Oxygen'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.26,
                    'max_gravity': 0.276,
                    'min_temperature': 160.0,
                    'max_temperature': 180.0,
                    'volcanism': ['carbon']
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.185,
                    'max_gravity': 0.276,
                    'min_temperature': 149.0,
                    'max_temperature': 272.0,
                    'volcanism': ['carbon', 'methane']
                },
                {  # Probably incomplete
                    'atmosphere': ['Ammonia', 'ArgonRich', 'CarbonDioxideRich'],
                    'body_type': ['Icy body'],
                    'max_gravity': 0.276,
                    'volcanism': ['carbon']
                }
            ],
        },
        '$Codex_Ent_Fumerolas_02_Name;': {
            'name': 'Fumerola Extremus',
            'value': 16202800,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.09,
                    'min_temperature': 161.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                    'volcanism': ['silicate', 'metallic', 'rocky']
                },
                {
                    'atmosphere': ['Argon'],
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body'],
                    'min_gravity': 0.07,
                    'max_gravity': 0.276,
                    'min_temperature': 50.0,
                    'max_temperature': 121.0,
                    'volcanism': ['silicate', 'metallic', 'rocky']
                },
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body'],
                    'min_gravity': 0.025,
                    'max_gravity': 0.127,
                    'min_temperature': 77.0,
                    'max_temperature': 109.0,
                    'min_pressure': 0.01,
                    'volcanism': ['silicate', 'metallic', 'rocky']
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'body_type': ['Rocky body', 'Rocky ice body'],
                    'min_gravity': 0.07,
                    'max_gravity': 0.276,
                    'min_temperature': 54.0,
                    'max_temperature': 210.0,
                    'volcanism': ['silicate', 'metallic', 'rocky']
                },
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['High metal content body'],
                    'min_gravity': 0.05,
                    'max_gravity': 0.276,
                    'min_temperature': 500.0,
                    #'max_temperature': 210.0,
                    'volcanism': ['silicate', 'metallic', 'rocky']
                }
            ],
        },
        '$Codex_Ent_Fumerolas_03_Name;': {
            'name': 'Fumerola Nitris',
            'value': 7500900,
            'rulesets': [
                { # Only one example
                    'atmosphere': ['Neon'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 30.0,
                    'max_temperature': 129.0,
                    'volcanism': ['nitrogen', 'ammonia']
                },
                {
                    'atmosphere': ['Argon', 'ArgonRich', 'NeonRich'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.044,
                    'max_gravity': 0.276,
                    'min_temperature': 50.0,
                    'max_temperature': 141.0,
                    'volcanism': ['nitrogen', 'ammonia']
                },
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.025,
                    'max_gravity': 0.1,
                    'min_temperature': 83.0,
                    'max_temperature': 109.0,
                    'volcanism': ['nitrogen']
                },
                {
                    'atmosphere': ['Nitrogen'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.21,
                    'max_gravity': 0.276,
                    'min_temperature': 60.0,
                    'max_temperature': 81.0,
                    'volcanism': ['nitrogen', 'ammonia']
                },
                {
                    'atmosphere': ['Oxygen'],
                    'body_type': ['Icy body'],
                    'max_gravity': 0.276,
                    'min_temperature': 150.0,
                    'volcanism': ['nitrogen', 'ammonia']
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.21,
                    'max_gravity': 0.276,
                    'min_temperature': 160.0,
                    'max_temperature': 250.0,
                    'volcanism': ['nitrogen', 'ammonia']
                },
            ],
        },
        '$Codex_Ent_Fumerolas_04_Name;': {
            'name': 'Fumerola Aquatis',
            'value': 6284600,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Icy body', 'Rocky ice body', 'Rocky body'],
                    'min_gravity': 0.028,
                    'max_gravity': 0.276,
                    'min_temperature': 161.0,
                    'max_temperature': 177.0,
                    'min_pressure': 0.002,
                    'max_pressure': 0.02,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['Argon', 'ArgonRich'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.166,
                    'max_gravity': 0.276,
                    'min_temperature': 57.0,
                    'max_temperature': 150.0,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.25,
                    'max_gravity': 0.276,
                    'min_temperature': 160.0,
                    'max_temperature': 180.0,
                    'min_pressure': 0.01,
                    'max_pressure': 0.03,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 80.0,
                    'max_temperature': 100.0,
                    'min_pressure': 0.01,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['Neon'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.26,
                    'max_gravity': 0.276,
                    'min_temperature': 20.0,
                    'max_temperature': 60.0,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['Nitrogen'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.195,
                    'max_gravity': 0.245,
                    'min_temperature': 56.0,
                    'max_temperature': 80.0,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['Oxygen'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.23,
                    'max_gravity': 0.276,
                    'min_temperature': 153.0,
                    'max_temperature': 190.0,
                    'min_pressure': 0.01,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'body_type': ['Icy body', 'Rocky ice body', 'Rocky body'],
                    'min_gravity': 0.18,
                    'max_gravity': 0.276,
                    'min_temperature': 150.0,
                    'max_temperature': 270.0,
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.06,
                    'volcanism': ['water']
                }
            ],
        },
    },
    # ---- fungoida.py ----
    '$Codex_Ent_Fungoids_Genus_Name;': {
        '$Codex_Ent_Fungoids_01_Name;': {
            'name': 'Fungoida Setisis',
            'value': 1670100,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 152.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135
                },
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Rocky ice body'],
                    'min_gravity': 0.033,
                    'max_gravity': 0.276,
                    'min_temperature': 68.0,
                    'max_temperature': 109.0,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.033,
                    'max_gravity': 0.276,
                    'min_temperature': 67.0,
                    'max_temperature': 109.0
                }
            ],
        },
        '$Codex_Ent_Fungoids_02_Name;': {
            'name': 'Fungoida Stabitis',
            'value': 2680300,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'Rocky ice body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.045,
                    'min_temperature': 172.0,
                    'max_temperature': 177.0,
                    'volcanism': ['silicate'],
                    'regions': ['orion-cygnus']
                },
                {
                    'atmosphere': ['Argon'],
                    'body_type': ['Rocky ice body'],
                    'min_gravity': 0.20,
                    'max_gravity': 0.23,
                    'min_temperature': 60.0,
                    'max_temperature': 90.0,
                    'volcanism': ['silicate', 'rocky'],
                    'regions': ['orion-cygnus']
                },
                { # Only one sample
                    'atmosphere': ['ArgonRich'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.3,
                    'max_gravity': 0.5,
                    'min_temperature': 60.0,
                    'max_temperature': 90.0,
                    'regions': ['orion-cygnus']
                },
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.0405,
                    'max_gravity': 0.27,
                    'min_temperature': 180.0,
                    #'max_temperature': 197.0,
                    'min_pressure': 0.025,
                    'volcanism': 'None',
                    'regions': ['orion-cygnus']
                },
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.043,
                    'max_gravity': 0.126,
                    'min_temperature': 78.5,
                    'max_temperature': 109.0,
                    'min_pressure': 0.012,
                    'volcanism': ['major silicate'],
                    'regions': ['orion-cygnus']
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.039,
                    'max_gravity': 0.064,
                    'volcanism': 'None',
                    'regions': ['orion-cygnus']
                }
            ],
        },
        '$Codex_Ent_Fungoids_03_Name;': {
            'name': 'Fungoida Bullarum',
            'value': 3703200,
            'rulesets': [
                {
                    'atmosphere': ['Argon'],
                    'min_gravity': 0.058,
                    'max_gravity': 0.276,
                    'min_temperature': 50.0,
                    'max_temperature': 129.0,
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body'],
                    'volcanism': 'None',
                },
                {
                    'atmosphere': ['Nitrogen'],
                    'min_gravity': 0.155,
                    'max_gravity': 0.276,
                    'min_temperature': 50.0,
                    'max_temperature': 70.0,
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body'],
                    'volcanism': 'None',
                }
            ],
        },
        '$Codex_Ent_Fungoids_04_Name;': {
            'name': 'Fungoida Gelata',
            'value': 3330300,
            'rulesets': [
                { # Only one sample - review
                    'atmosphere': ['Argon'],
                    'body_type': ['Rocky body', 'Rocky ice body'],
                    'min_gravity': 0.041,
                    'max_gravity': 0.276,
                    'min_temperature': 160.0,
                    'max_temperature': 180.0,
                    'max_pressure': 0.0135,
                    'volcanism': ['major silicate'],
                    'regions': ['!orion-cygnus-core']
                },
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'Rocky ice body'],
                    'min_gravity': 0.042,
                    'max_gravity': 0.071,
                    'min_temperature': 160.0,
                    'max_temperature': 180.0,
                    'max_pressure': 0.0135,
                    'volcanism': ['major silicate'],
                    'regions': ['!orion-cygnus-core']
                },
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['High metal content body'],
                    'min_gravity': 0.042,
                    'max_gravity': 0.071,
                    'min_temperature': 160.0,
                    'max_temperature': 180.0,
                    'max_pressure': 0.0135,
                    'volcanism': ['major rocky'],
                    'regions': ['!orion-cygnus-core']
                },
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.041,
                    'max_gravity': 0.276,
                    'min_temperature': 180.0,
                    #'max_temperature': 200.0,
                    'min_pressure': 0.025,
                    'body_type': ['Rocky body', 'High metal content body'],
                    'volcanism': 'None',
                    'regions': ['!orion-cygnus-core']
                },
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.044,
                    'max_gravity': 0.125,
                    'min_temperature': 80.0,
                    'max_temperature': 110.0,
                    'min_pressure': 0.01,
                    'volcanism': ['major silicate', 'major metallic'],
                    'regions': ['!orion-cygnus-core']
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.039,
                    'max_gravity': 0.063,
                    'volcanism': 'None',
                    'regions': ['!orion-cygnus-core']
                }
            ],
        },
    },
    # ---- osseus.py ----
    '$Codex_Ent_Osseus_Genus_Name;': {
        '$Codex_Ent_Osseus_01_Name;': {
            'name': 'Osseus Fractus',
            'value': 4027800,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 180.0,
                    #'max_temperature': 190.0,
                    'min_pressure': 0.025,
                    'volcanism': 'None',
                    'regions': ['!perseus']
                }
            ],
        },
        '$Codex_Ent_Osseus_02_Name;': {
            'name': 'Osseus Discus',
            'value': 12934900,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.088,
                    'min_temperature': 161.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['Argon'],
                    'body_type': ['Rocky ice body'],
                    'min_gravity': 0.2,
                    'max_gravity': 0.276,
                    'min_temperature': 65.0,
                    'max_temperature': 120.0,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['High metal content body'],
                    'min_gravity': 0.026,
                    'max_gravity': 0.276,
                    'min_temperature': 500.0,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.127,
                    'min_temperature': 80.0,
                    'max_temperature': 110.0,
                    'min_pressure': 0.012,
                    'volcanism': 'Any'
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.055,
                }
            ],
        },
        '$Codex_Ent_Osseus_03_Name;': {
            'name': 'Osseus Spiralis',
            'value': 2404700,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 160.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135
                }
            ],
        },
        '$Codex_Ent_Osseus_04_Name;': {
            'name': 'Osseus Pumice',
            'value': 3156300,
            'rulesets': [
                {
                    'atmosphere': ['Argon'],
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body'],
                    'min_gravity': 0.059,
                    'max_gravity': 0.276,
                    'min_temperature': 50.0,
                    'max_temperature': 135.0,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Argon'],
                    'body_type': ['Rocky ice body'],
                    'min_gravity': 0.059,
                    'max_gravity': 0.276,
                    'min_temperature': 50.0,
                    'max_temperature': 135.0,
                    'volcanism': ['water', 'geysers']
                },
                {
                    'atmosphere': ['ArgonRich'],
                    'body_type': ['Rocky ice body'],
                    'min_gravity': 0.035,
                    'max_gravity': 0.276,
                    'min_temperature': 60.0,
                    'max_temperature': 80.5,
                    'min_pressure': 0.03,
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Methane'],
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body'],
                    'min_gravity': 0.033,
                    'max_gravity': 0.276,
                    'min_temperature': 67.0,
                    'max_temperature': 109.0
                },
                {
                    'atmosphere': ['Nitrogen'],
                    'body_type': ['Rocky body', 'Rocky ice body', 'High metal content body'],
                    'min_gravity': 0.05,
                    'max_gravity': 0.276,
                    'min_temperature': 42.0,
                    'max_temperature': 70.1,
                    'volcanism': 'None'
                }
            ],
        },
        '$Codex_Ent_Osseus_05_Name;': {
            'name': 'Osseus Cornibus',
            'value': 1483000,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.0405,
                    'max_gravity': 0.276,
                    'min_temperature': 180.0,
                    #'max_temperature': 197.0,
                    'min_pressure': 0.025,
                    'volcanism': 'None',
                    'regions': ['perseus']
                }
            ],
        },
        '$Codex_Ent_Osseus_06_Name;': {
            'name': 'Osseus Pellebantus',
            'value': 9739000,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.0405,
                    'max_gravity': 0.276,
                    'min_temperature': 191.0,
                    #'max_temperature': 197.0,
                    'min_pressure': 0.057,
                    'volcanism': 'None',
                    'regions': ['!perseus']
                }
            ],
        },
    },
    # ---- recepta.py ----
    '$Codex_Ent_Recepta_Genus_Name;': {
        '$Codex_Ent_Recepta_01_Name;': {
            'name': 'Recepta Umbrux',
            'value': 12934900,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 151.0,
                    'max_temperature': 200.0,
                    'atmosphere_component': {'SulphurDioxide': 1.05}
                },
                {
                    'atmosphere': ['Oxygen'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.23,
                    'max_gravity': 0.276,
                    'min_temperature': 154.0,
                    'max_temperature': 175.0,
                    'min_pressure': 0.01,
                    'volcanism': 'None',
                    'atmosphere_component': {'SulphurDioxide': 1.05}
                },
                {
                    'atmosphere': ['Oxygen'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.23,
                    'max_gravity': 0.276,
                    'min_temperature': 154.0,
                    'max_temperature': 175.0,
                    'min_pressure': 0.01,
                    'volcanism': ['water'],
                    'atmosphere_component': {'SulphurDioxide': 1.05}
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 132.0,
                    'max_temperature': 273.0,
                    'atmosphere_component': {'SulphurDioxide': 1.05}
                }
            ],
        },
        '$Codex_Ent_Recepta_02_Name;': {
            'name': 'Recepta Deltahedronix',
            'value': 16202800,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 150.0,
                    'max_temperature': 195.0,
                    'volcanism': 'None',
                    'atmosphere_component': {'SulphurDioxide': 1.05}
                },
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Icy body', 'Rocky ice body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 150.0,
                    'max_temperature': 195.0,
                    'volcanism': ['water'],
                    'atmosphere_component': {'SulphurDioxide': 1.05}
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 132.0,
                    'max_temperature': 272.0,
                    'atmosphere_component': {'SulphurDioxide': 1.05}
                }
            ],
        },
        '$Codex_Ent_Recepta_03_Name;': {
            'name': 'Recepta Conditivus',
            'value': 14313700,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide', 'CarbonDioxideRich'],
                    'body_type': ['Icy body', 'Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 150.0,
                    'max_temperature': 195.0,
                    'volcanism': 'None',
                    'atmosphere_component': {'SulphurDioxide': 1.05}
                },
                {
                    'atmosphere': ['Oxygen'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.23,
                    'max_gravity': 0.276,
                    'min_temperature': 154.0,
                    'max_temperature': 175.0,
                    'min_pressure': 0.01,
                    'volcanism': 'None',
                    'atmosphere_component': {'SulphurDioxide': 1.05}
                },
                {
                    'atmosphere': ['Oxygen'],
                    'body_type': ['Icy body'],
                    'min_gravity': 0.23,
                    'max_gravity': 0.276,
                    'min_temperature': 154.0,
                    'max_temperature': 175.0,
                    'min_pressure': 0.01,
                    'volcanism': ['water'],
                    'atmosphere_component': {'SulphurDioxide': 1.05}
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 132.0,
                    'max_temperature': 275.0,
                    'atmosphere_component': {'SulphurDioxide': 1.05}
                }
            ],
        },
    },
    # ---- shard.py ----
    '$Codex_Ent_Ground_Struct_Ice_Name;': {
        '$Codex_Ent_Ground_Struct_Ice_Name;': {
            'name': 'Crystalline Shards',
            'value': 1628800,
            'rulesets': [
                {
                    'atmosphere': ['None', 'Argon', 'ArgonRich', 'CarbonDioxide', 'CarbonDioxideRich',
                                   'Helium', 'Methane', 'Neon', 'NeonRich'],
                    'max_gravity': 2.0,
                    'max_temperature': 273.0,
                    'star': ['A', 'F', 'G', 'K', 'MS', 'S'],
                    'distance': 12000.0,
                    'bodies': ['Earthlike body', 'Ammonia world', 'Water world', 'Gas giant with water based life',
                               'Gas giant with ammonia based life', 'Water giant'],
                    'regions': ['exterior']
                }
            ]
        }
    },
    # ---- stratum.py ----
    '$Codex_Ent_Stratum_04_Name;': {
        '$Codex_Ent_Stratum_04_Name;': {
            'name': 'Stratum Aranaemus',
            'value': 2448900,
            'rulesets': []
        }
    },
    '$Codex_Ent_Stratum_Genus_Name;': {
        '$Codex_Ent_Stratum_01_Name;': {
            'name': 'Stratum Excutitus',
            'value': 2448900,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.48,
                    'min_temperature': 165.0,
                    'max_temperature': 190.0,
                    'min_pressure': 0.0035,
                    'body_type': ['Rocky body'],
                    'volcanism': 'None',
                    'regions': ['orion-cygnus']
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'min_gravity': 0.27,
                    'max_gravity': 0.4,
                    'min_temperature': 165.0,
                    'max_temperature': 190.0,
                    'body_type': ['Rocky body'],
                    'regions': ['orion-cygnus']
                }
            ],
        },
        '$Codex_Ent_Stratum_02_Name;': {
            'name': 'Stratum Paleas',
            'value': 1362000,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.35,
                    'min_temperature': 165.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                    'body_type': ['Rocky body']
                },
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.585,
                    'min_temperature': 165.0,
                    'max_temperature': 395.0,
                    'body_type': ['Rocky body'],
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['CarbonDioxideRich'],
                    'min_gravity': 0.43,
                    'max_gravity': 0.585,
                    'min_temperature': 185.0,
                    'max_temperature': 260.0,
                    'min_pressure': 0.015,
                    'body_type': ['Rocky body'],
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Water'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.056,
                    'body_type': ['Rocky body'],
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['Water'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.056,
                    'min_pressure': 0.065,
                    'body_type': ['Rocky body'],
                    'volcanism': ['water']
                },
                {
                    'atmosphere': ['Oxygen'],
                    'min_gravity': 0.39,
                    'max_gravity': 0.59,
                    'min_temperature': 165.0,
                    'max_temperature': 250.0,
                    'min_pressure': 0.022,
                    'body_type': ['Rocky body']
                }
            ],
        },
        '$Codex_Ent_Stratum_03_Name;': {
            'name': 'Stratum Laminamus',
            'value': 2788300,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.34,
                    'min_temperature': 165.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                    'body_type': ['Rocky body'],
                    'regions': ['orion-cygnus']
                }
            ],
        },
        '$Codex_Ent_Stratum_04_Name;': {
            'name': 'Stratum Araneamus',
            'value': 2448900,
            'rulesets': [
                {
                    'atmosphere': ['SulphurDioxide'],
                    'min_gravity': 0.26,
                    'max_gravity': 0.57,
                    'min_temperature': 165.0,
                    'max_temperature': 373.0,
                    'body_type': ['Rocky body']
                }
            ],
        },
        '$Codex_Ent_Stratum_05_Name;': {
            'name': 'Stratum Limaxus',
            'value': 1362000,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.03,
                    'max_gravity': 0.4,
                    'min_temperature': 165.0,
                    'max_temperature': 190.0,
                    'min_pressure': 0.05,
                    'body_type': ['Rocky body'],
                    'volcanism': 'None',
                    'regions': ['scutum-centaurus-core']
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'min_gravity': 0.27,
                    'max_gravity': 0.4,
                    'min_temperature': 165.0,
                    'max_temperature': 190.0,
                    'body_type': ['Rocky body'],
                    'regions': ['scutum-centaurus-core']
                }
            ],
        },
        '$Codex_Ent_Stratum_06_Name;': {
            'name': 'Stratum Cucumisis',
            'value': 16202800,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.6,
                    'min_temperature': 191.0,
                    'max_temperature': 371.0,
                    'body_type': ['Rocky body'],
                    'volcanism': 'None',
                    'regions': ['sagittarius-carina']
                },
                {
                    'atmosphere': ['CarbonDioxideRich'],
                    'min_gravity': 0.44,
                    'max_gravity': 0.56,
                    'min_temperature': 210.0,
                    'max_temperature': 246.0,
                    'min_pressure': 0.01,
                    'body_type': ['Rocky body'],
                    'volcanism': 'None',
                    'regions': ['sagittarius-carina']
                },
                {
                    'atmosphere': ['Oxygen'],
                    'min_gravity': 0.4,
                    'max_gravity': 0.6,
                    'min_temperature': 200.0,
                    'max_temperature': 250.0,
                    'min_pressure': 0.01,
                    'body_type': ['Rocky body'],
                    'regions': ['sagittarius-carina']
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'min_gravity': 0.26,
                    'max_gravity': 0.55,
                    'min_temperature': 191.0,
                    'max_temperature': 373.0,
                    'body_type': ['Rocky body'],
                    'regions': ['sagittarius-carina']
                }
            ],
        },
        '$Codex_Ent_Stratum_07_Name;': {
            'name': 'Stratum Tectonicas',
            'value': 19010800,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'min_gravity': 0.045,
                    'max_gravity': 0.38,
                    'min_temperature': 165.0,
                    'max_temperature': 177.0,
                    'body_type': ['High metal content body']
                },
                {
                    'atmosphere': ['Argon', 'ArgonRich'],
                    'min_gravity': 0.485,
                    'max_gravity': 0.54,
                    'min_temperature': 167.0,
                    'max_temperature': 199.0,
                    'body_type': ['High metal content body'],
                    'volcanism': 'None'
                },
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.045,
                    'max_gravity': 0.61,
                    'min_temperature': 165.0,
                    'max_temperature': 430.0,
                    'body_type': ['High metal content body']
                },
                {
                    'atmosphere': ['CarbonDioxideRich'],
                    'min_gravity': 0.035,
                    'max_gravity': 0.61,
                    'min_temperature': 165.0,
                    'max_temperature': 260.0,
                    'body_type': ['High metal content body']
                },
                {
                    'atmosphere': ['Oxygen'],
                    'min_gravity': 0.4,
                    'max_gravity': 0.52,
                    'min_temperature': 165.0,
                    'max_temperature': 246.0,
                    'body_type': ['High metal content body']
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'min_gravity': 0.29,
                    'max_gravity': 0.62,
                    'min_temperature': 165.0,
                    'max_temperature': 450.0,
                    'body_type': ['High metal content body']
                },
                {
                    'atmosphere': ['Water'],
                    'min_gravity': 0.045,
                    'max_gravity': 0.063,
                    'body_type': ['High metal content body'],
                    'volcanism': 'None'
                },
            ],
        },
        '$Codex_Ent_Stratum_08_Name;': {
            'name': 'Stratum Frigus',
            'value': 2637500,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.043,
                    'max_gravity': 0.54,
                    'min_temperature': 191.0,
                    'max_temperature': 365.0,
                    'min_pressure': 0.001,
                    'body_type': ['Rocky body'],
                    'volcanism': 'None',
                    'regions': ['perseus-core']
                },
                {
                    'atmosphere': ['CarbonDioxideRich'],
                    'min_gravity': 0.45,
                    'max_gravity': 0.56,
                    'min_temperature': 200.0,
                    'max_temperature': 250.0,
                    'min_pressure': 0.01,
                    'body_type': ['Rocky body'],
                    'volcanism': 'None',
                    'regions': ['perseus-core']
                },
                {
                    'atmosphere': ['SulphurDioxide'],
                    'min_gravity': 0.29,
                    'max_gravity': 0.52,
                    'min_temperature': 191.0,
                    'max_temperature': 369.0,
                    'body_type': ['Rocky body'],
                    'regions': ['perseus-core']
                }
            ],
        },
    },
    # ---- tubers.py ----
    '$Codex_Ent_Tube_Name;': {
        '$Codex_Ent_Tube_Name;': {
            'name': 'Roseum Sinuous Tubers',
            'value': 1514500,
            'rulesets': [
                {
                    'body_type': ['High metal content body'],
                    'min_temperature': 200.0,
                    'max_temperature': 500.0,
                    'volcanism': ['rocky magma'],
                    'tuber': ['Galactic Center', 'Odin A', 'Ryker B']
                }
            ],
        },
        '$Codex_Ent_TubeABCD_01_Name;': {
            'name': 'Prasinum Sinuous Tubers',
            'value': 1514500,
            'rulesets': [
                {
                    'body_type': ['Metal rich body', 'High metal content body', 'Rocky body'],
                    'min_temperature': 200.0,
                    'max_temperature': 500.0,
                    'volcanism': 'Any',
                    'tuber': ['Inner S-C Arm B 1']
                },
                {
                    'body_type': ['Metal rich body', 'High metal content body'],
                    'min_temperature': 200.0,
                    'max_temperature': 500.0,
                    'volcanism': ['major rocky magma', 'major silicate vapour'],
                    'tuber': ['Inner S-C Arm D', 'Norma Expanse B', 'Odin B']
                },
                {
                    'body_type': ['Metal rich body', 'High metal content body'],
                    'min_temperature': 200.0,
                    'max_temperature': 500.0,
                    'volcanism': ['major rocky magma', 'major silicate vapour'],
                    'regions': ['empyrean-straits']
                }
            ],
        },
        '$Codex_Ent_TubeABCD_02_Name;': {  # High % sulphur requirement?
            'name': 'Albidum Sinuous Tubers',
            'value': 1514500,
            'rulesets': [
                {
                    'body_type': ['Rocky body'],
                    'min_temperature': 200.0,
                    'max_temperature': 500.0,
                    'max_orbital_period': 86400,
                    'volcanism': ['major silicate vapour', 'major metallic magma'],
                    'tuber': ['Inner S-C Arm B 2', 'Inner S-C Arm D', 'Trojan Belt']
                }
            ],
        },
        '$Codex_Ent_TubeABCD_03_Name;': {
            'name': 'Caeruleum Sinuous Tubers',
            'value': 1514500,
            'rulesets': [
                {
                    'body_type': ['Rocky body'],
                    'min_temperature': 200.0,
                    'max_temperature': 500.0,
                    'max_orbital_period': 86400,
                    'volcanism': ['major silicate vapour'],
                    'tuber': ['Galactic Center', 'Inner S-C Arm D', 'Norma Arm A']
                },
                {
                    'body_type': ['Rocky body'],
                    'min_temperature': 200.0,
                    'max_temperature': 500.0,
                    'volcanism': ['major silicate vapour'],
                    'regions': ['empyrean-straits']
                }
            ],
        },
        '$Codex_Ent_TubeEFGH_01_Name;': {
            'name': 'Lindigoticum Sinuous Tubers',
            'value': 1514500,
            'rulesets': [
                {
                    'body_type': ['Rocky body'],
                    'min_temperature': 200.0,
                    'max_temperature': 500.0,
                    'max_orbital_period': 86400,
                    'volcanism': ['major silicate vapour'],
                    'tuber': ['Inner S-C Arm A', 'Inner S-C Arm C', 'Hawking B', 'Norma Expanse A', 'Odin B']
                }
            ],
        },
        '$Codex_Ent_TubeEFGH_02_Name;': {
            'name': 'Violaceum Sinuous Tubers',
            'value': 1514500,
            'rulesets': [
                {
                    'body_type': ['Metal rich body', 'High metal content body'],
                    'min_temperature': 200.0,
                    'max_temperature': 500.0,
                    'volcanism': ['major rocky magma', 'major silicate vapour'],
                    'tuber': ['Arcadian Stream', 'Empyrean Straits', 'Norma Arm B']
                }
            ],
        },
        '$Codex_Ent_TubeEFGH_03_Name;': {
            'name': 'Viride Sinuous Tubers',
            'value': 1514500,
            'rulesets': [
                {
                    'body_type': ['High metal content body'],
                    'min_temperature': 200.0,
                    'max_temperature': 500.0,
                    'volcanism': ['major rocky magma', 'major silicate vapour'],
                    'tuber': ['Inner O-P Conflux', 'Izanami', 'Ryker A']
                },
                {
                    'body_type': ['Rocky body'],
                    'min_temperature': 200.0,
                    'max_temperature': 500.0,
                    'max_orbital_period': 86400,
                    'volcanism': ['major rocky magma', 'major silicate vapour'],
                    'tuber': ['Inner O-P Conflux', 'Izanami', 'Ryker A']
                }
            ],
        },
        '$Codex_Ent_TubeEFGH_Name;': {
            'name': 'Blatteum Sinuous Tubers',
            'value': 1514500,
            'rulesets': [
                {
                    'body_type': ['Metal rich body', 'High metal content body'],
                    'min_temperature': 200.0,
                    'max_temperature': 500.0,
                    'volcanism': ['=metallic magma volcanism', '=rocky magma volcanism', 'major silicate vapour'],
                    'tuber': ['Arcadian Stream', 'Inner Orion Spur', 'Inner S-C Arm B 2', 'Hawking A']
                }
            ],
        },
    },
    # ---- tubus.py ----
    '$Codex_Ent_Tubus_Genus_Name;': {
        '$Codex_Ent_Tubus_01_Name;': {
            'name': 'Tubus Conifer',
            'value': 2415500,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.041,
                    'max_gravity': 0.153,
                    'min_temperature': 160.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.003,
                    'volcanism': 'None',
                    'regions': ['perseus']
                },
            ],
        },
        '$Codex_Ent_Tubus_02_Name;': {
            'name': 'Tubus Sororibus',
            'value': 5727600,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['High metal content body'],
                    'min_gravity': 0.045,
                    'max_gravity': 0.152,
                    'min_temperature': 160.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                },
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['High metal content body'],
                    'min_gravity': 0.045,
                    'max_gravity': 0.152,
                    'min_temperature': 160.0,
                    'max_temperature': 195.0,
                    'volcanism': 'None'
                }
            ],
        },
        '$Codex_Ent_Tubus_03_Name;': {
            'name': 'Tubus Cavas',
            'value': 11873200,
            'rulesets': [
                {
                    'body_type': ['Rocky body'],
                    'atmosphere': ['CarbonDioxide'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.152,
                    'min_temperature': 160.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.003,
                    'volcanism': 'None',
                    'regions': ['scutum-centaurus']
                },
            ],
        },
        '$Codex_Ent_Tubus_04_Name;': {
            'name': 'Tubus Rosarium',
            'value': 2637500,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.153,
                    'min_temperature': 160.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135
                },
            ],
        },
        '$Codex_Ent_Tubus_05_Name;': {
            'name': 'Tubus Compagibus',
            'value': 7774700,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.153,
                    'min_temperature': 160.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.003,
                    'volcanism': 'None',
                    'regions': ['sagittarius-carina']
                },
            ],
        },
    },
    # ---- tussock.py ----
    '$Codex_Ent_Tussocks_Genus_Name;': {
        '$Codex_Ent_Tussocks_01_Name;': {
            'name': 'Tussock Pennata',
            'value': 5853800,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.09,
                    'min_temperature': 146.0,
                    'max_temperature': 154.0,
                    'min_pressure': 0.00289,
                    'volcanism': 'None',
                    'regions': ['sagittarius-carina-core-9', 'perseus-core', 'orion-cygnus-core']
                }
            ],
        },
        '$Codex_Ent_Tussocks_02_Name;': {
            'name': 'Tussock Ventusa',
            'value': 3227700,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.13,
                    'min_temperature': 155.0,
                    'max_temperature': 160.0,
                    'min_pressure': 0.00289,
                    'volcanism': 'None',
                    'regions': ['sagittarius-carina-core-9', 'perseus-core', 'orion-cygnus-core']
                }
            ],
        },
        '$Codex_Ent_Tussocks_03_Name;': {
            'name': 'Tussock Ignis',
            'value': 1849000,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.2,
                    'min_temperature': 161.0,
                    'max_temperature': 170.0,
                    'min_pressure': 0.00289,
                    'volcanism': 'None',
                    'regions': ['sagittarius-carina-core-9', 'perseus-core', 'orion-cygnus-core']
                }
            ],
        },
        '$Codex_Ent_Tussocks_04_Name;': {
            'name': 'Tussock Cultro',
            'value': 1766600,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 152.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                    'regions': ['orion-cygnus']
                }
            ],
        },
        '$Codex_Ent_Tussocks_05_Name;': {
            'name': 'Tussock Catena',
            'value': 1766600,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 152.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                    'regions': ['scutum-centaurus-core']
                }
            ],
        },
        '$Codex_Ent_Tussocks_06_Name;': {
            'name': 'Tussock Pennatis',
            'value': 1000000,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 147.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.00289,
                    'volcanism': 'None',
                    'regions': ['outer']
                }
            ],
        },
        '$Codex_Ent_Tussocks_07_Name;': {
            'name': 'Tussock Serrati',
            'value': 4447100,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.042,
                    'max_gravity': 0.23,
                    'min_temperature': 171.0,
                    'max_temperature': 174.0,
                    'min_pressure': 0.01,
                    'max_pressure': 0.071,
                    'volcanism': 'None',
                    'regions': ['sagittarius-carina-core-9', 'perseus-core', 'orion-cygnus-core']
                }
            ],
        },
        '$Codex_Ent_Tussocks_08_Name;': {
            'name': 'Tussock Albata',
            'value': 3252500,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.042,
                    'max_gravity': 0.276,
                    'min_temperature': 175.0,
                    'max_temperature': 180.0,
                    'min_pressure': 0.016,
                    'volcanism': 'None',
                    'regions': ['sagittarius-carina-core-9', 'perseus-core', 'orion-cygnus-core']
                }
            ],
        },
        '$Codex_Ent_Tussocks_09_Name;': {
            'name': 'Tussock Propagito',
            'value': 1000000,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 145.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.00289,
                    'volcanism': 'None',
                    'regions': ['scutum-centaurus']
                }
            ],
        },
        '$Codex_Ent_Tussocks_10_Name;': {
            'name': 'Tussock Divisa',
            'value': 1766600,
            'rulesets': [
                {
                    'atmosphere': ['Ammonia'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.042,
                    'max_gravity': 0.276,
                    'min_temperature': 152.0,
                    'max_temperature': 177.0,
                    'max_pressure': 0.0135,
                    'regions': ['perseus-core']
                }
            ],
        },
        '$Codex_Ent_Tussocks_11_Name;': {
            'name': 'Tussock Caputus',
            'value': 3472400,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.041,
                    'max_gravity': 0.27,
                    'min_temperature': 181.0,
                    'max_temperature': 190.0,
                    'min_pressure': 0.0275,
                    'volcanism': 'None',
                    'regions': ['sagittarius-carina-core-9', 'perseus-core', 'orion-cygnus-core']
                }
            ],
        },
        '$Codex_Ent_Tussocks_12_Name;': {
            'name': 'Tussock Triticum',
            'value': 7774700,
            'rulesets': [
                {
                    'atmosphere': ['CarbonDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 191.0,
                    'max_temperature': 197.0,
                    'min_pressure': 0.058,
                    'volcanism': 'None',
                    'regions': ['sagittarius-carina-core-9', 'perseus-core', 'orion-cygnus-core']
                }
            ],
        },
        '$Codex_Ent_Tussocks_13_Name;': {
            'name': 'Tussock Stigmasis',
            'value': 19010800,
            'rulesets': [
                {
                    'atmosphere': ['SulphurDioxide'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.276,
                    'min_temperature': 132.0,
                    'max_temperature': 180.0,
                    'max_pressure': 0.01
                }
            ],
        },
        '$Codex_Ent_Tussocks_14_Name;': {
            'name': 'Tussock Virgam',
            'value': 14313700,
            'rulesets': [
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.065,
                    'volcanism': 'None',
                },
                {
                    'atmosphere': ['Water'],
                    'body_type': ['Rocky body', 'High metal content body'],
                    'min_gravity': 0.04,
                    'max_gravity': 0.065,
                    'volcanism': ['water'],
                }
            ],
        },
        '$Codex_Ent_Tussocks_15_Name;': {
            'name': 'Tussock Capillum',
            'value': 7025800,
            'rulesets': [
                {
                    'atmosphere': ['Argon'],
                    'min_gravity': 0.22,
                    'max_gravity': 0.276,
                    'min_temperature': 80.0,
                    'max_temperature': 129.0,
                    'body_type': ['Rocky ice body']
                },
                {
                    'atmosphere': ['Methane'],
                    'min_gravity': 0.033,
                    'max_gravity': 0.276,
                    'min_temperature': 80.0,
                    'max_temperature': 110.0,
                    'body_type': ['Rocky body', 'Rocky ice body']
                }
            ],
        },
    },
}


# Constraints that a body scan alone can decide. Anything else in a ruleset
# (galactic region groupings, star luminosity classes, Guardian or nebula
# proximity, parent-body composition) needs context this matcher is not given,
# so it is reported as unchecked rather than quietly assumed true.
_BODY_CONSTRAINTS = frozenset({
    "body_type", "atmosphere", "volcanism",
    "min_gravity", "max_gravity",
    "min_temperature", "max_temperature",
    "min_pressure", "max_pressure",
})


def _normalise(value):
    return "".join(character for character in str(value or "").lower() if character.isalnum())


def _atmosphere_matches(required, atmosphere):
    """Match a required atmosphere list against a journal atmosphere string.

    Elite reports either ``AtmosphereType`` ("CarbonDioxide") or the prose
    ``Atmosphere`` ("thin carbon dioxide atmosphere"); normalising both to
    bare alphanumerics lets one comparison serve either form.
    """
    actual = _normalise(atmosphere)
    for option in required:
        wanted = _normalise(option)
        if wanted in ("none", ""):
            if not actual or actual in ("none", "noatmosphere"):
                return True
            continue
        if wanted and wanted in actual:
            return True
    return False


def _volcanism_matches(required, volcanism):
    actual = str(volcanism or "").strip().lower()
    for option in required:
        wanted = str(option or "").strip().lower()
        if wanted == "any":
            if actual and actual != "no volcanism":
                return True
            continue
        if wanted == "none":
            if not actual or actual == "no volcanism":
                return True
            continue
        # A leading '=' marks an exact upstream match rather than a keyword.
        if wanted.startswith("="):
            if actual == wanted[1:].strip():
                return True
            continue
        if wanted and wanted in actual:
            return True
    return False


def _within(value, low, high):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if low is not None and value < float(low):
        return False
    if high is not None and value > float(high):
        return False
    return True


def _ruleset_verdict(rule, planet_class, atmosphere, temp_k, gravity_g, volcanism,
                     pressure_atm, region_id=None, coords=None):
    """Return ``(matched, unchecked)`` for one published ruleset."""
    unchecked = set(rule) - _BODY_CONSTRAINTS - _LOCATION_CONSTRAINTS
    required_regions = [
        entry for key in _REGION_KEYS for entry in (rule.get(key) or ())
    ]
    for name, verdict in (
        ("regions", _regions_allow(required_regions, region_id)
            if required_regions else True),
        ("guardian", _guardian_allows(rule.get("guardian"), coords)
            if "guardian" in rule else True),
        ("tuber", _tuber_allows(rule.get("tuber"), coords)
            if "tuber" in rule else True),
    ):
        if verdict is False:
            return False, sorted(unchecked)
        if verdict is None:
            # Position was not supplied, so this requirement stays undecided.
            unchecked.add(name)
    unchecked = sorted(unchecked)
    if "body_type" in rule and planet_class not in (rule.get("body_type") or ()):
        return False, unchecked
    if "atmosphere" in rule and not _atmosphere_matches(rule["atmosphere"] or (), atmosphere):
        return False, unchecked
    if "volcanism" in rule and not _volcanism_matches(rule["volcanism"] or (), volcanism):
        return False, unchecked
    for value, low, high, label in (
        (gravity_g, rule.get("min_gravity"), rule.get("max_gravity"), "gravity"),
        (temp_k, rule.get("min_temperature"), rule.get("max_temperature"), "temperature"),
        (pressure_atm, rule.get("min_pressure"), rule.get("max_pressure"), "pressure"),
    ):
        if low is None and high is None:
            continue
        verdict = _within(value, low, high)
        if verdict is False:
            return False, unchecked
        if verdict is None:
            # The body scan did not report this measurement.
            unchecked = sorted(set(unchecked) | {label})
    return True, unchecked


def candidate_species(planet_class, atmosphere, temp_k, gravity_g, volcanism,
                      pressure_atm=None, region_id=None, coords=None):
    """Return published species whose requirements fit this body.

    ``region_id`` is a Codex region identifier as returned by
    :func:`galactic_regions.find_region`, and ``coords`` the system's
    ``StarPos``. Supplying them decides the region, Guardian-zone and Sinuous
    Tuber requirements that would otherwise be reported as untested.

    Each result carries ``unchecked``: the constraints that could not be
    decided here. An empty list means every published requirement was tested
    and satisfied; otherwise the species is possible rather than confirmed.
    """
    found = []
    for genus_key, species_map in CATALOG.items():
        for species_key, species in species_map.items():
            rulesets = species.get("rulesets") or ()
            if not rulesets:
                continue
            best = None
            for rule in rulesets:
                matched, unchecked = _ruleset_verdict(
                    rule, planet_class, atmosphere, temp_k, gravity_g, volcanism,
                    pressure_atm, region_id, coords,
                )
                if not matched:
                    continue
                if best is None or len(unchecked) < len(best):
                    best = unchecked
                if not best:
                    break
            if best is None:
                continue
            found.append({
                "genus_key": genus_key,
                "species_key": species_key,
                "name": species.get("name"),
                "value": species.get("value"),
                "unchecked": best,
                "confirmed": not best,
            })
    found.sort(key=lambda row: (len(row["unchecked"]), -(row["value"] or 0), row["name"] or ""))
    return found


# Flora are named "Genus Species - Colour"; the non-flora families are named
# "Colour Family", so neither a leading nor a trailing word alone identifies a
# genus. These are the family names the catalogue actually uses, longest first
# so "Brain Tree" wins over any shorter accidental match.
_FAMILY_NAMES = (
    "Amphora Plant", "Crystalline Shards", "Sinuous Tubers", "Bark Mounds",
    "Brain Tree", "Anemone",
    "Aleoida", "Bacterium", "Cactoida", "Clypeus", "Concha", "Electricae",
    "Fonticulua", "Frutexa", "Fumerola", "Fungoida", "Osseus", "Recepta",
    "Stratum", "Tubus", "Tussock",
)


def family_for_species(species_name):
    """Return the genus or family a catalogue species name belongs to."""
    name = str(species_name or "").strip()
    if not name:
        return ""
    for family in _FAMILY_NAMES:
        if name.startswith(family) or name.endswith(family):
            return family
    return name.split(" ")[0]


def _build_family_map():
    families = {}
    for genus_key, species_map in CATALOG.items():
        counts = {}
        for species in species_map.values():
            family = family_for_species(species.get("name"))
            if family:
                counts[family] = counts.get(family, 0) + 1
        if counts:
            families[genus_key] = max(counts, key=counts.get)
    return families


# Codex genus identifier -> the family name shown to the commander.
GENUS_FAMILIES = _build_family_map()


# ---------------------------------------------------------------------------
# Region, Guardian-nebula and Sinuous Tuber zones, vendored from the same
# pinned EDMC-BioScan commit (src/bio_scan/bio_data/regions.py).
#
# REGION_MAP values are Codex region identifiers 1-42 -- exactly what
# galactic_regions.find_region() returns -- so these constraints can be decided
# from the commander's own position without any further lookup.
# ---------------------------------------------------------------------------

REGION_MAP: dict[str, list[int]] = {
    'orion-cygnus': [1, 4, 7, 8, 16, 17, 18, 35],
    'orion-cygnus-1': [4, 7, 8, 16, 17, 18, 35],
    'orion-cygnus-core': [7, 8, 16, 17, 18, 35],
    'sagittarius-carina': [1, 4, 9, 18, 19, 20, 21, 22, 23, 40],
    'sagittarius-carina-core': [9, 18, 19, 20, 21, 22, 23, 40],
    'sagittarius-carina-core-9': [18, 19, 20, 21, 22, 23, 40],
    'scutum-centaurus': [1, 4, 9, 10, 11, 12, 24, 25, 26, 42, 28],
    'scutum-centaurus-core': [9, 10, 11, 12, 24, 25, 26, 42, 28],
    'outer': [1, 2, 5, 6, 13, 14, 27, 29, 31, 41, 37],
    'perseus': [1, 3, 7, 15, 30, 32, 33, 34, 36, 38, 39],
    'perseus-core': [3, 7, 15, 30, 32, 33, 34, 36, 38, 39],
    'exterior': [14, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 34, 36,
                 37, 38, 39, 40, 41, 42],
    'anemone-a': [7, 8, 13, 14, 15, 16, 17, 18, 27, 30, 32],
    'amphora': [10, 19, 20, 21, 22],
    'brain-tree': [2, 9, 10, 17, 18, 35],
    'empyrean-straits': [2],
    'center': [1, 2, 3]
}

GUARDIAN_NEBULAE: dict[str, tuple[int, tuple[float, float, float]]] = {
    'Hen 2-333': (750, (-840.65625, -561.15625, 13361.8125)),
    'Gamma Velorum': (750, (1099.21875, -146.6875, -133.59375)),
    'Skaudai AA-A h71': (100, (-5493.09375, -589.28125, 10424.4375)),
    'Blaa Hypai AA-A h68': (100,  (1220.40625, -694.625, 12312.8125)),
    'Eorl Auwsy AA-A h72': (100, (4949.9375, 164, 20640.125)),
    'Prai Hypoo AA-A h60': (100, (-9294.875, -458.40625, 7905.71875)),
    'Eta Carina Nebula': (100, (8579.96875, -138.96875, 2701.375)),
    'NGC 3199': (100, (14574.15625, -259.625, 3511.90625))
}

TUBER_ZONES: dict[str, tuple[tuple[int, int], tuple[float, float, float]]] = {
    'Arcadian Stream': ((200, 600), (8885, -20, 20535)),
    'Empyrean Straits': ((200, 400), (4325, 400, 21185)),
    'Galactic Center': ((500, 1000), (44.5, 492.7, 25916)),
    'Hawking A': ((150, 600), (5788, 150, 6335)),
    'Hawking B': ((200, 600), (9990, -40, 8335)),
    'Inner Orion Spur': ((200, 600), (-3485, 39, 7320)),
    'Inner O-P Conflux': ((350, 750), (-13245, -80, 30285)),
    'Inner S-C Arm A': ((200, 600), (-1600, -37, 10720)),
    'Inner S-C Arm B 1': ((150, 300), (-6645, 0, 12590)),
    'Inner S-C Arm B 2': ((200, 600), (-6645, 0, 12590)),
    'Inner S-C Arm C': ((200, 600), (-9355, -50, 17175)),
    'Inner S-C Arm D': ((300, 400), (-12000, 232, 22670)),
    'Izanami': ((200, 750), (-4610, 370, 37225)),
    'Norma Arm A': ((500, 1000), (3722.6, 200, 16441)),
    'Norma Arm B': ((200, 500), (3740, 175, 16460)),
    'Norma Expanse A': ((200, 600), (4245, -42, 12071)),
    'Norma Expanse B': ((150, 250), (5580, 40, 11727)),
    'Odin A': ((750, 1000), (-7945, 230, 28025)),
    'Odin B': ((200, 600), (-5329, -68, 18647)),
    'Ryker A': ((250, 750), (1715, 766, 34070)),
    'Ryker B': ((750, 1500), (-1445, 345, 30345)),
    'Trojan Belt': ((250, 500), (18600, 65, 31750)),
}


# Constraints decidable from the commander's own position, given the Codex
# region identifier and system coordinates.
#
# 'region' is the singular spelling the Brain Tree entries use. Upstream's
# evaluator has no branch for it, so there it is silently ignored and Brain
# Trees are never region-filtered at all — even though its own region map
# defines 'brain-tree'. The value has the same shape as 'regions' and names a
# real group, so it is treated as the same requirement here. This is a
# deliberate divergence from upstream behaviour.
_REGION_KEYS = ("regions", "region")
_LOCATION_CONSTRAINTS = frozenset({"regions", "region", "guardian", "tuber"})


def _distance_ly(left, right):
    return sum((float(a) - float(b)) ** 2 for a, b in zip(left, right)) ** 0.5


def _regions_allow(required, region_id):
    """Apply the published region rule to a Codex region identifier.

    Mirrors the upstream evaluation: a ``!name`` entry excludes its regions
    outright, and any plain entries then act as an allow-list which the region
    must satisfy at least one of.
    """
    if region_id is None:
        return None
    for entry in required:
        name = str(entry)
        if name.startswith("!") and region_id in (REGION_MAP.get(name[1:]) or ()):
            return False
    allowed = [str(entry) for entry in required if not str(entry).startswith("!")]
    if not allowed:
        return True
    return any(region_id in (REGION_MAP.get(name) or ()) for name in allowed)


def _guardian_allows(required, coords):
    if not required:
        return True
    if coords is None:
        return None
    return any(
        _distance_ly(coords, position) < max_distance
        for max_distance, position in GUARDIAN_NEBULAE.values()
    )


def _tuber_allows(required, coords):
    if coords is None:
        return None
    for zone, (bounds, position) in TUBER_ZONES.items():
        if required != "Any" and zone not in required:
            continue
        low, high = bounds
        if low <= _distance_ly(coords, position) <= high:
            return True
    return False
