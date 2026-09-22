// Add another {id, text, source} entry to extend the offline startup deck.
// Keep facts short; no remote requests are made during startup.
const exploration = 'https://elite-dangerous.fandom.com/wiki/Explorer';
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
]);
