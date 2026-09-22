// Add another {id, text, source} entry to extend the offline startup deck.
// Keep facts short; no remote requests are made during startup.
const exploration = 'https://elite-dangerous.fandom.com/wiki/Explorer';
const supercharging = 'https://elite-dangerous.fandom.com/wiki/FSD_Supercharging';
const sagA = 'https://elite-dangerous.fandom.com/wiki/Sagittarius_A*';
export const BOOT_FACTS = Object.freeze([
  {id: 'galaxy', text: 'Elite Dangerous models a Milky Way with around 400 billion star systems.', source: 'https://en.wikipedia.org/wiki/Elite_Dangerous'},
  {id: 'scoop', text: 'KGB FOAM is the explorer’s mnemonic for scoopable star classes: K, G, B, F, O, A and M.', source: exploration},
  {id: 'honk', text: 'The Discovery Scanner’s familiar “honk” is the first step in surveying a new system.', source: exploration},
  {id: 'fss', text: 'The Full Spectrum System Scanner identifies distant bodies without visiting each one.', source: exploration},
  {id: 'mapping', text: 'The Detailed Surface Scanner launches probes to map individual planets and moons.', source: 'https://edfieldmanual.com/wiki/How_to_Map_a_Planet_or_Moon_with_a_Detailed_Surface_Scanner'},
  {id: 'cartography', text: 'Exploration data can be sold to Universal Cartographics at stations offering that service.', source: exploration},
  {id: 'codex', text: 'Your Composition Scanner can record organic and inorganic discoveries in the Codex.', source: exploration},
  {id: 'parallel', text: 'You can use the Discovery Scanner while fuel scooping—two exploration tasks in one stop.', source: exploration},
  {id: 'first-map', text: 'Being first to submit mapping data for an unmapped body can earn a permanent First Mapped By tag.', source: 'https://edfieldmanual.com/wiki/How_to_Map_a_Planet_or_Moon_with_a_Detailed_Surface_Scanner'},
  {id: 'footfall', text: 'First Footfall recognises the first commander to set foot on a world. It is separate from mapping it.', source: 'https://newp.io/exploration'},
  {id: 'supercharge', text: 'Flying through the jet cone of a neutron star can supercharge your FSD, roughly quadrupling your jump range for the next hop.', source: supercharging},
  {id: 'exobiology', text: 'The Genetic Sampler needs three samples of a species, taken far enough apart, before Vista Genomics will buy the data.', source: 'https://elite-dangerous.fandom.com/wiki/Exobiologist'},
  {id: 'guardian', text: 'Guardian ruins and structures hold million-year-old tech from an extinct civilisation, salvageable as materials for Guardian weapons and modules.', source: 'https://elite-dangerous.fandom.com/wiki/Guardian_Technology_Component'},
  {id: 'sag-a', text: 'Sagittarius A*, the supermassive black hole at the galaxy’s centre, sits 25,899.99 light years from Sol.', source: sagA},
  {id: 'beagle-point', text: 'Beagle Point, discovered in 3301 by the DSS Beagle, lies 65,279 light years from Sol on the far side of the galaxy.', source: 'https://elite-dangerous.fandom.com/wiki/Distant_Worlds'},
  {id: 'colonia', text: 'The Colonia region grew up around Jaques Station after a botched jump stranded it roughly 22,000 light years from Sol.', source: 'https://elite-dangerous.fandom.com/wiki/Colonia_Region'},
  {id: 'hutton', text: 'Hutton Orbital is famous among explorers for sitting about 0.22 light years from its system’s main arrival point.', source: 'https://elite-dangerous.fandom.com/wiki/Hutton_Orbital'},
  {id: 'elw', text: 'Naturally occurring Earth-like worlds are extremely rare, and Universal Cartographics pays some of its highest rates for finding one.', source: 'https://elite-dangerous.fandom.com/wiki/Earth-like_World'},
  {id: 'water-world', text: 'Water worlds are prized by explorers—life is likelier to have evolved wherever there’s liquid water.', source: 'https://elite-dangerous.fandom.com/wiki/Water_World'},
  {id: 'road-to-riches', text: 'A “Road to Riches” route strings together unexplored systems containing high-value Earth-like or water worlds for efficient cartography runs.', source: 'https://edtools.cc/expl?a=about'},
  {id: 'ranks', text: 'Explorer rank runs from Aimless up through Elite, based on the credits earned selling cartographic data to Universal Cartographics.', source: exploration},
  {id: 'black-hole', text: 'Black holes can’t be flown into directly—your ship auto-drops from supercruise at the exclusion zone before reaching the event horizon.', source: 'https://elite-dangerous.fandom.com/wiki/Black_Holes'},
  {id: 'signals', text: 'A Detailed Surface Scanner reveals how many biological and geological signal sites a landable world is hiding.', source: exploration},
  {id: 'jumponium', text: 'Synthesising the right raw materials—nicknamed “jumponium”—can boost your FSD range by up to 100% for a single jump.', source: 'https://elite-dangerous.fandom.com/wiki/Synthesis'},
  {id: 'wake-scanner', text: 'A wake scanner can analyse the high-energy FSD trail another ship leaves behind after a hyperspace jump.', source: 'https://elite-dangerous.fandom.com/wiki/Anomalous_FSD_Telemetry'},
  {id: 'neutron-highway', text: 'Charting a “neutron highway” lets explorers chain supercharged jumps from one neutron star to the next across vast distances.', source: supercharging},
  {id: 'stellar-phenomena', text: 'The Codex catalogues Notable Stellar Phenomena—rare sights like unusual clouds and space storms—alongside biological and geological finds.', source: exploration},
  {id: 'sol-permit', text: 'Sol itself is permit-locked—even the birthplace of humanity requires Federal Navy rank to enter.', source: 'https://elite-dangerous.fandom.com/wiki/Permits'},
  {id: 'explorers-anchorage', text: 'Explorer’s Anchorage, built during the Distant Worlds II expedition, sits just 3.66 light years from Sagittarius A*—the closest starport to the galactic centre.', source: sagA},
  {id: 'canonn', text: 'Canonn Research is a long-running commander science group that catalogues Guardian sites and other anomalies found across the galaxy.', source: 'https://canonn.science'},
]);