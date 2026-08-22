(() => {
  'use strict';

  const normalise = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  const artUrl = (filename) => `/ship-art/${String(filename).split('/').map(encodeURIComponent).join('/')}`;

  // Frontier's journal symbols are intentionally kept beside display-name
  // aliases.  The localised name is a useful fallback, but symbols remain the
  // stable primary key when the commander changes language or renames a ship.
  const ships = [
    ['Adder', 'Adder.png', ['adder']],
    ['Alliance Challenger', 'Alliance Challenger.png', ['typex3']],
    ['Alliance Chieftain', 'Alliance Chieftain.png', ['typex']],
    ['Alliance Crusader', 'Alliance Crusader.png', ['typex2']],
    ['Anaconda', 'Anaconda.png', ['anaconda']],
    ['Asp Explorer', 'Asp Explorer.png', ['asp']],
    ['Asp Scout', 'Asp Scout.png', ['aspscout']],
    ['Beluga Liner', 'Beluga Liner.png', ['belugaliner']],
    ['Caspian Explorer', 'Caspian Explorer.png', ['explorernx']],
    ['Cobra Mk III', 'Cobra Mk III.png', ['cobramkiii']],
    ['Cobra Mk IV', 'Cobra Mk IV.png', ['cobramkiv']],
    ['Cobra Mk V', 'Cobra Mk V.png', ['cobramkv']],
    ['Corsair', 'Corsair.png', ['corsair', 'empiretradernx']],
    ['Diamondback Explorer', 'DiamondBack Explorer.png', ['diamondbackxl']],
    ['Diamondback Scout', 'Diamondback Scout.png', ['diamondback']],
    ['Dolphin', 'Dolphin.png', ['dolphin']],
    ['Eagle Mk II', 'Eagle Mk II.png', ['eagle']],
    ['Federal Assault Ship', 'Federal Assault Ship.png', ['federationdropshipmkii']],
    ['Federal Corvette', 'Federal Corvette.png', ['federationcorvette']],
    ['Federal Dropship', 'Federal Dropship.png', ['federationdropship']],
    ['Federal Gunship', 'Federal Gunship.png', ['federationgunship']],
    ['Fer-de-Lance', 'Fer De Lance.png', ['ferdelance']],
    ['Hauler', 'Hauler.png', ['hauler']],
    ['Imperial Clipper', 'Imperial Clipper.png', ['empiretrader']],
    ['Imperial Courier', 'Imperial Courier.png', ['empirecourier']],
    ['Imperial Cutter', 'Imperial Cutter.png', ['cutter']],
    ['Imperial Eagle', 'Imperial Eagle.png', ['empireeagle']],
    ['Keelback', 'Keelback.png', ['keelback']],
    ['Kestrel Mk II', 'Kestrel Mk II.png', ['smallcombat01nx']],
    ['Krait Mk II', 'Krait Mk II.png', ['kraitmkii']],
    ['Krait Phantom', 'Krait Phantom.png', ['kraitlight']],
    ['Lynx Highliner', 'Lynx Highliner.png', ['mediumtransport01']],
    ['Mamba', 'Mamba.png', ['mamba']],
    ['Mandalay', 'Mandalay.png', ['mandalay']],
    ['Orca', 'Orca.png', ['orca']],
    ['Panther Clipper Mk II', 'Panther Clipper Mk II.png', ['panthermkii']],
    ['Python', 'Python.png', ['python']],
    ['Python Mk II', 'Python Mk II.png', ['pythonnx']],
    ['Sidewinder', 'Sidewinder.png', ['sidewinder']],
    ['Type-6 Transporter', 'Type 6 Transporter.png', ['type6']],
    ['Type-7 Transporter', 'Type 7 Transporter.png', ['type7']],
    ['Type-8 Transporter', 'Type-8 Transporter.png', ['type8']],
    ['Type-9 Heavy', 'Type 9 Heavy.png', ['type9']],
    ['Type-10 Defender', 'Type 10 Defender.png', ['type9military']],
    ['Type-11 Prospector', 'Type-11 Prospector.png', ['lakonminer']],
    ['Viper Mk III', 'Viper Mk III.png', ['viper']],
    ['Viper Mk IV', 'Viper Mk IV.png', ['vipermkiv']],
    ['Vulture', 'Vulture.png', ['vulture']],
  ].map(([name, file, aliases]) => ({name, file, aliases}));

  const shipLookup = new Map();
  for (const ship of ships) {
    for (const alias of [ship.name, ship.file.replace(/\.png$/i, ''), ...ship.aliases]) {
      shipLookup.set(normalise(alias), ship);
    }
  }

  const vehicles = {
    carrier: {key: 'carrier', name: 'Drake-Class Fleet Carrier', file: 'Drake-Class Fleet Carrier.png'},
    fighter: {key: 'fighter', name: 'Taipan ship-launched fighter', file: 'Taipan.png'},
    onfoot: {key: 'onfoot', name: 'Commander on foot', file: 'Commander On Foot.png'},
    nomad: {key: 'nomad', name: 'Nomad ship-launched vessel', file: 'Nomad.png'},
    scarab: {key: 'scarab', name: 'Scarab SRV', file: 'SRV Scarab.png'},
    scorpion: {key: 'scorpion', name: 'Scorpion SRV', file: 'SRV Scorpion.png'},
  };

  function presentation(item, alt) {
    return item ? {
      key: normalise(item.key || item.name),
      src: artUrl(item.file),
      alt: String(alt || item.name),
    } : null;
  }

  function resolveShip(vehicle = {}) {
    const symbol = normalise(vehicle.ship_symbol);
    const type = normalise(vehicle.ship_type);
    const ship = shipLookup.get(symbol) || shipLookup.get(type);
    return presentation(ship, vehicle.ship_name || vehicle.ship_type || ship?.name);
  }

  function resolveSurface(value) {
    const key = normalise(value);
    if (key.includes('nomad') || key === 'lander01') return presentation(vehicles.nomad);
    if (key.includes('scorpion') || key.includes('combatmulticrewsrv01')) {
      return presentation(vehicles.scorpion);
    }
    if (!key || key === 'srv' || key.includes('scarab') || key === 'testbuggy') {
      return presentation(vehicles.scarab);
    }
    // New surface craft deliberately receive no incorrect portrait until
    // Frontier exposes their final journal alias and production silhouette.
    return null;
  }

  window.VoidCompassShipCatalog = Object.freeze({
    ships: Object.freeze(ships),
    resolveShip,
    resolveSurface,
    onFoot: () => presentation(vehicles.onfoot),
    fighter: () => presentation(vehicles.fighter),
    carrier: () => presentation(vehicles.carrier),
  });
})();
