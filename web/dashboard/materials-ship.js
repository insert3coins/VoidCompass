// The Materials page's ship builder (5.8.4): pick a hull, fit each slot,
// engineer it (blueprint, grade, how good the rolls were, an experimental),
// and read what it does: mass, jump range, speed, shields, armour,
// resistances, power, heat and damage. The ship you fly comes in with the
// game's own engineered figures. Builds are saved with the commander, can be
// compared, and their engineering goes onto the ship wishlist in one click.
// Hulls and modules come from /materials-ships.json, loaded once.

const STANDARD_LABELS = ["Power Plant", "Thrusters", "Frame Shift Drive", "Life Support", "Power Distributor", "Sensors", "Fuel Tank"];
const STANDARD_SLOTS = ["PowerPlant", "MainEngines", "FrameShiftDrive", "LifeSupport", "PowerDistributor", "Radar", "FuelTank"];
const HARDPOINT_SIZES = {0: "Tiny", 1: "Small", 2: "Medium", 3: "Large", 4: "Huge"};
const BULKHEAD_GRADES = ["grade1", "grade2", "grade3", "mirrored", "reactive"];

const n = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
const whole = (value) => Math.round(n(value)).toLocaleString("en-GB");
const fixed = (value, digits = 1) => n(value).toLocaleString("en-GB", {minimumFractionDigits: digits, maximumFractionDigits: digits});
const money = (value) => n(value) >= 1e9 ? `${(n(value) / 1e9).toFixed(2)}B` : n(value) >= 1e6 ? `${(n(value) / 1e6).toFixed(1)}M` : whole(value);

let ships = null;
let shipsState = "idle";
let build = null;
let compareId = "";
// After a shared build's code is imported: open the build that wasn't there before.
let openNewest = null;
let importedAt = 0;
const OPENED_AT = Date.now() / 1000 - 2;
let shipFilter = "";
let mode = "outfit";   // the Ship Builder page (5.8.5): "outfit", "yard" or "hangar"
let signature = "";
let host = null;
let ui = null;
let data = {};
let ref = null;

function esc(value) {
  return (ui?.escapeHtml || ((text) => String(text ?? "")))(value);
}

async function op(operation, extra = {}) {
  try {
    const response = await fetch(ui.apiUrl("/api/command"), {
      method: "POST", cache: "no-store", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action: "workspace", page: "materials", operation, ...extra}),
    });
    const reply = await response.json().catch(() => ({}));
    return Boolean(reply.accepted);
  } catch {
    return false;
  }
}

function load() {
  if (shipsState !== "idle") return;
  shipsState = "loading";
  fetch(ui.apiUrl("/materials-ships.json"), {cache: "no-cache"})
    .then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .then((json) => {
      ships = json;
      ships.bySymbol = {};
      // A pre-engineered variant (the Sirius heat sink, an Expanded Capacity cargo rack...) shares its plain
      // module's symbol; the journal names the plain one and says what was engineered.
      for (const [id, module] of Object.entries(ships.modules)) {
        const had = ships.modules[ships.bySymbol[module.symbol]];
        if (module.symbol && (!had || !module.preEngineered || had.preEngineered)) ships.bySymbol[module.symbol] = id;
      }
      for (const [symbol, id] of Object.entries(ships.aliases || {})) ships.bySymbol[symbol] ??= id;
      learnHulls();
      shipsState = "ready";
      draw();
    })
    .catch(() => { shipsState = "idle"; host && (host.innerHTML = `<p class="mt-empty">The ship tables didn't load. Trying again shortly…</p>`); setTimeout(draw, 4000); });
}

export function shipBuilderReset() {
  build = null;
  mode = "outfit";
  signature = "";
}

// -- builds --------------------------------------------------------------------
function moduleOf(id) {
  return id ? ships.modules[String(id)] || null : null;
}

function standardModule(group, classRating) {
  const text = String(classRating || "");
  const size = Number(text.slice(0, -1));
  const rating = text.slice(-1);
  const hit = Object.entries(ships.modules).find(([, m]) => m.grp === group && m.class === size && m.rating === rating);
  return hit ? hit[0] : null;
}

function newBuild(key) {
  const ship = ships.ships[key];
  const slots = [];
  (ship.slots.standard || []).forEach((size, index) => {
    slots.push({group: "standard", index, size, module: standardModule(ships.standard[index], ship.defaults?.standard?.[index]), bp: "", grade: 0, special: ""});
  });
  (ship.slots.hardpoints || []).forEach((entry, index) => {
    const size = typeof entry === "object" ? entry.class : entry;
    const id = ship.defaults?.hardpoints?.[index];
    slots.push({group: size ? "hardpoints" : "utility", index, size, jname: typeof entry === "object" ? entry.jname : "",
      module: id ? `hardpoints:${id}` : null, bp: "", grade: 0, special: ""});
  });
  (ship.slots.internal || []).forEach((entry, index) => {
    const size = typeof entry === "object" ? entry.class : entry;
    const id = ship.defaults?.internal?.[index];
    slots.push({group: "internal", index, size, name: typeof entry === "object" ? entry.name || "" : "", jname: typeof entry === "object" ? entry.jname || "" : "",
      eligible: typeof entry === "object" && entry.eligible ? Object.keys(entry.eligible) : null, module: id ? `internal:${id}` : null, bp: "", grade: 0, special: ""});
  });
  return {id: "", name: ship.name, ship: key, bulkhead: 0, roll: defaultRoll(), slots};
}

function defaultRoll() {
  const roll = Number((data.options || {}).roll);
  return Number.isFinite(roll) ? Math.max(0, Math.min(100, roll)) : 100;
}

// A hull the tables don't have (a new ship), described by an import: its slots
// from the game's slot names and module sizes, its figures as EDSY gave them.
const SIZE_OF = {Tiny: 0, Small: 1, Medium: 2, Large: 3, Huge: 4};

function describedHull(loadout, hull) {
  const symbol = String(loadout?.Ship || "").toLowerCase();
  if (!symbol) return null;
  const rows = loadout.Modules || [];
  const sizeOf = (item) => Number((String(item || "").match(/size(\d)/i) || [])[1] || 0);
  const standard = STANDARD_SLOTS.map((name) => sizeOf(rows.find((row) => row.Slot === name)?.Item) || 1);
  const hardpoints = rows.map((row) => String(row.Slot || "").match(/^(Tiny|Small|Medium|Large|Huge)(?:Mining)?Hardpoint(\d+)$/)).filter(Boolean)
    .map((m) => ({class: SIZE_OF[m[1]], jname: m[0], n: Number(m[2])})).sort((a, b) => b.class - a.class || a.n - b.n);
  const internal = rows.filter((row) => /^(Slot\d+_Size\d+|Military\d+|Cargo\d+|PlanetaryApproachSuite|LimpetController\d+|FighterBay\d+)$/.test(String(row.Slot || "")))
    .map((row) => ({class: Number((String(row.Slot).match(/_Size(\d+)$/) || [])[1]) || sizeOf(row.Item) || 1, jname: row.Slot,
      name: /^Military/.test(row.Slot) ? "Military" : /^Cargo/.test(row.Slot) ? "Cargo" : /Approach/.test(row.Slot) ? "PlanetaryApproachSuite" : ""}))
    .sort((a, b) => a.jname.localeCompare(b.jname));
  const h = hull || {};
  const pretty = h.name || symbol.replace(/mkii$/, " Mk II").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return {symbol, name: pretty, manufacturer: "", described: true, hullMass: n(h.mass), speed: n(h.topspd), boost: n(h.bstspd),
    minthrust: n(h.minthrust), boostEnergy: n(h.boostcost), baseShieldStrength: n(h.shields), baseArmour: n(h.armour), hardness: n(h.hardness),
    heatCapacity: n(h.heatcap), masslock: n(h.masslock), reserveFuelCapacity: n(h.fuelreserve), crew: n(h.crew), cost: 0, hullCost: 0,
    bulkheads: standardBulkheads(),
    slots: {standard, hardpoints, internal}, defaults: {}};
}

// Ship types you've flown that the tables don't have yet, from their latest Loadout:
// slots and modules as fitted, the name the shipyard gave it, and the hull's mass
// (with its armour) as the ship's unladen mass less what its modules weigh.
function learnHulls() {
  if (!ships) return;
  correctHullMasses();
  const known = new Set(Object.values(ships.ships).filter((ship) => !ship.described).map((ship) => ship.symbol));
  for (const [symbol, seen] of Object.entries(data.seen_hulls || {})) {
    const key = `described:${symbol}`;
    if (known.has(symbol) || (ships.ships[key] && !ships.ships[key].learned)) continue;
    let moduleMass = 0;
    let unknown = false;
    for (const row of seen.modules || []) {
      if (row.Slot === "Armour") continue;
      const id = ships.bySymbol[row.Item];
      if (id) moduleMass += n(ships.modules[id].mass) * (row.mass_ratio || 1);
      else if (FITTED_SLOT.test(row.Slot)) unknown = true;
    }
    const mass = !unknown && n(seen.unladen) > moduleMass ? Math.round((n(seen.unladen) - moduleMass) * 100) / 100 : 0;
    const hull = describedHull({Ship: symbol, Modules: seen.modules}, {name: (data.ship_names || {})[symbol], mass, fuelreserve: seen.reserve});
    if (!hull) continue;
    hull.learned = true;
    // The armour's own mass is in the hull's: whichever grade you pick, the mass stays as you fly it.
    hull.armourInMass = Boolean(mass);
    ships.ships[key] = hull;
  }
}

// A hull the tables have, but at a mass the game doesn't agree with (the Caspian's is
// 950 t in the tables, about 832 t as flown): the game's unladen mass less what its
// modules and armour weigh, from the latest Loadout of that type. Only when every
// module is known, and only when it's out by more than a tonne.
function correctHullMasses() {
  for (const ship of Object.values(ships.ships)) {
    const seen = !ship.described && (data.seen_hulls || {})[ship.symbol];
    if (!seen || !n(seen.unladen)) continue;
    ship.tableHullMass ??= ship.hullMass;
    let modules = 0;
    let unknown = false;
    for (const row of seen.modules || []) {
      if (row.Slot === "Armour") {
        const grade = BULKHEAD_GRADES.findIndex((g) => String(row.Item || "").includes(`_${g}`));
        modules += n(ship.bulkheads?.[Math.max(0, grade)]?.mass) * (row.mass_ratio || 1);
        continue;
      }
      const id = ships.bySymbol[row.Item];
      if (id) modules += n(ships.modules[id].mass) * (row.mass_ratio || 1);
      else if (FITTED_SLOT.test(row.Slot)) unknown = true;
    }
    const hull = Math.round((n(seen.unladen) - modules) * 100) / 100;
    const right = !unknown && hull > 0 && Math.abs(hull - n(ship.tableHullMass)) > 1;
    ship.hullMass = right ? hull : ship.tableHullMass;
    ship.massFromJournal = right;
  }
}

// Slots that hold a module with mass (not paint, decals, the cockpit or the cargo hatch).
const FITTED_SLOT = /^(PowerPlant|MainEngines|FrameShiftDrive|LifeSupport|PowerDistributor|Radar|FuelTank|(Tiny|Small|Medium|Large|Huge)(Mining)?Hardpoint\d+|Slot\d+_Size\d+|Military\d+|Cargo\d+|Passenger\d+|LimpetController\d+|FighterBay\d+)$/;

// The armour grades' resistances are the same on every hull; a described hull's mass and boost aren't known.
function standardBulkheads() {
  return (Object.values(ships.ships).find((ship) => !ship.described && (ship.bulkheads || []).length === 5)?.bulkheads || [{name: "As fitted"}])
    .map((b) => ({name: b.name, mass: 0, hullboost: 0, cost: 0, kinres: n(b.kinres), thermres: n(b.thermres), explres: n(b.explres), causres: n(b.causres)}));
}

function knownHull(key, saved) {
  if (!ships.ships[key] && saved) ships.ships[key] = {...saved, bulkheads: saved.bulkheads?.length ? saved.bulkheads : standardBulkheads()};
  return Boolean(ships.ships[key]);
}

function plain(row) {
  // What's saved: the ship, its armour and each slot's module and engineering.
  return {id: row.id, name: row.name, ship: row.ship, bulkhead: row.bulkhead, ...(row.armourEng ? {armourEng: row.armourEng} : {}), armourGrades: (ships.ships[row.ship]?.bulkheads || []).length, layout: row.slots.length, roll: row.roll,
    ...(row.armour ? {armour: row.armour} : {}),
    ...(ships.ships[row.ship]?.described ? {hull: ships.ships[row.ship]} : {}),
    slots: row.slots.map((slot) => ({module: slot.module, bp: slot.bp, grade: slot.grade, special: slot.special,
      ...(slot.roll != null ? {roll: slot.roll} : {}), ...(slot.jmods ? {jmods: slot.jmods} : {}),
      ...(slot.unknown ? {unknown: slot.unknown} : {}), ...(slot.bpName ? {bpName: slot.bpName, bpGrade: n(slot.bpGrade)} : {}),
      ...(slot.off ? {off: true} : {})}))};
}

// Hulls whose slots the game laid out again after 5.8.4 (a build without its layout count is from before).
const RELAID = new Set(["asp_scout", "federation_dropship", "empire_trader", "type6", "type7"]);

function fromSaved(saved) {
  if (!knownHull(saved.ship, saved.hull)) return null;
  // A build saved while its hull was new to the tables moves onto the real hull, slot by slot name.
  const symbol = String(saved.ship || "").startsWith("described:") ? String(saved.ship).slice(10) : "";
  const known = symbol && Object.keys(ships.ships).find((key) => !ships.ships[key].described && ships.ships[key].symbol === symbol);
  const was = newBuild(saved.ship);
  const fresh = newBuild(known || saved.ship);
  // A hull whose layout the game has changed since the build was saved (5.8.4.1: the Asp Scout,
  // Federal Dropship, Imperial Clipper, Type-6 and Type-7): its modules go to the same kind of slot
  // in the same order, where they fit.
  const relaid = !known && (saved.layout != null ? n(saved.layout) !== fresh.slots.length : RELAID.has(ships.ships[fresh.ship]?.symbol));
  const taken = new Set();
  const kindOf = (id) => (String(id || "").startsWith("internal:") ? "internal" : moduleOf(id)?.class === 0 ? "utility" : "hardpoints");
  const target = (index) => {
    if (relaid) {
      const slot = (saved.slots || [])[index];
      if (index < 7) return fresh.slots[index];
      if (!slot?.module) return null;
      const into = fresh.slots.find((row, at) => !taken.has(at) && row.group === kindOf(slot.module) && n(moduleOf(slot.module)?.class) <= n(row.size));
      if (into) taken.add(fresh.slots.indexOf(into));
      return into || null;
    }
    if (!known) return fresh.slots[index];
    const old = was.slots[index];
    if (!old) return null;
    if (old.group === "standard") return fresh.slots.find((slot) => slot.group === "standard" && slot.index === old.index);
    return old.jname ? fresh.slots.find((slot) => slot.jname === old.jname) : null;
  };
  fresh.id = saved.id;
  fresh.name = saved.name;
  fresh.bulkhead = n(saved.bulkhead);
  // The Caspian's armour list had an extra grade in front before 5.8.4.1.
  if (saved.armourGrades == null && ships.ships[fresh.ship]?.symbol === "explorer_nx" && fresh.bulkhead > 0) fresh.bulkhead -= 1;
  fresh.armour = saved.armour || null;
  fresh.armourEng = saved.armourEng || null;
  fresh.roll = saved.roll == null ? 100 : n(saved.roll);
  (saved.slots || []).forEach((slot, index) => {
    const into = target(index);
    if (into) Object.assign(into, {module: slot.module || null, bp: slot.bp || "", grade: n(slot.grade), special: slot.special || "",
      roll: slot.roll == null ? null : n(slot.roll), jmods: slot.jmods || null, unknown: slot.unknown || "", bpName: slot.bpName || "", off: Boolean(slot.off),
      bpGrade: n(slot.bpGrade)});
  });
  fresh.slots.forEach(recheck);
  return fresh;
}

// A module or blueprint that wasn't in the tables when it was saved may be now.
function recheck(slot) {
  if (!slot.module && slot.unknown && ships.bySymbol[slot.unknown.toLowerCase()]) {
    slot.module = ships.bySymbol[slot.unknown.toLowerCase()];
    slot.unknown = "";
  }
  if (slot.module && slot.bpName && !slot.bp) {
    const key = moduleBlueprint(slot.module, slot.bpName);
    const grades = Object.keys(ships.eligible[moduleOf(slot.module)?.grp]?.blueprints?.[key]?.grades || {}).map(Number);
    if (key && grades.length) {
      slot.bp = key;
      slot.bpName = "";
      // Saved before the game's grade was kept with it: its best grade until you set it.
      slot.grade = grades.includes(n(slot.bpGrade)) ? n(slot.bpGrade) : Math.max(...grades);
      slot.bpGrade = 0;
    }
  }
}

function moduleBlueprint(moduleId, name) {
  const key = blueprintKey(name);
  const eligible = Object.keys(ships.eligible[moduleOf(moduleId)?.grp]?.blueprints || {});
  if (!eligible.length || eligible.includes(key)) return key;
  const tail = String(name || "").split("_").slice(1).join("_").toLowerCase();
  const letters = (text) => String(text || "").toLowerCase().replace(/[^a-z]/g, "");
  // A newer blueprint can go by another name in the journal: FuelScoop_ScoopRateEnhanced is "Scoop Rate Enhanced".
  return eligible.find((candidate) => candidate.split("_").slice(1).join("_").toLowerCase() === tail)
    || eligible.find((candidate) => ships.blueprints[candidate]?.nofigures && letters(ships.blueprints[candidate].name) === letters(tail)) || "";
}

function blueprintKey(name) {
  const wanted = String(name || "").toLowerCase();
  return Object.keys(ships.blueprints).find((key) => key.toLowerCase() === wanted) || "";
}

// The ship you're flying, from the journal's last Loadout.
function fromLoadout(loadout, hull) {
  const symbol = String(loadout?.Ship || "").toLowerCase();
  let key = Object.keys(ships.ships).find((k) => ships.ships[k].symbol === symbol);
  if (!key) {
    const described = describedHull(loadout, hull);
    if (!described) return null;
    key = `described:${symbol}`;
    ships.ships[key] = described;
  }
  const fresh = newBuild(key);
  fresh.name = String(loadout.ShipName || "").trim() || ships.ships[key].name;
  const bySlot = Object.fromEntries((loadout.Modules || []).map((row) => [row.Slot, row]));
  const engineer = (slot, row) => {
    const eng = row?.Engineering;
    if (!eng) return;
    slot.bp = moduleBlueprint(slot.module, eng.BlueprintName);
    // One the tables don't have yet (a new blueprint): its name is shown, its figures are the game's.
    slot.bpName = slot.bp ? "" : String(eng.BlueprintName || "");
    slot.grade = slot.bp ? n(eng.Level) : 0;
    slot.bpGrade = slot.bp ? 0 : n(eng.Level);
    const effect = String(eng.ExperimentalEffect || "").toLowerCase();
    // A few experimentals go by another name in the builder's tables.
    slot.special = !effect ? "" : ships.specials[effect] && !ships.specials[effect].name?.includes("Legacy") ? effect
      : Object.keys(ships.specials).find((key) => ships.specials[key].journal === effect) || (ships.specials[effect] ? effect : "");
    if (eng.Quality != null) slot.roll = Math.round(n(eng.Quality) * 100);
    // The game's own figures: each engineered value against the module's stock one.
    const jmods = {};
    for (const mod of eng.Modifiers || []) {
      const field = ships.journal_fields?.[mod.Label];
      if (field && n(mod.OriginalValue)) jmods[field] = n(mod.Value) / n(mod.OriginalValue);
    }
    slot.jmods = Object.keys(jmods).length ? jmods : null;
  };
  const put = (slot, row) => {
    slot.module = row ? ships.bySymbol[String(row.Item || "").toLowerCase()] || null : null;
    // A module the tables don't have yet (a new one) keeps its game name, so the slot doesn't look empty.
    slot.unknown = row && !slot.module ? String(row.Item || "") : "";
    slot.off = row?.On === false;
    slot.bp = ""; slot.bpName = ""; slot.bpGrade = 0; slot.grade = 0; slot.special = ""; slot.roll = null; slot.jmods = null;
    if (slot.module) engineer(slot, row);
  };
  fresh.slots.filter((slot) => slot.group === "standard").forEach((slot) => put(slot, bySlot[STANDARD_SLOTS[slot.index]]));
  const counters = {};
  fresh.slots.filter((slot) => slot.group === "hardpoints" || slot.group === "utility").forEach((slot) => {
    const size = HARDPOINT_SIZES[slot.size];
    counters[size] = (counters[size] || 0) + 1;
    // A mining hull's mining mounts are numbered with the rest of their size (MediumMiningHardpoint1, MediumHardpoint3).
    // Every hull's slots carry the game's names (5.8.4.2); counting is for one described from an import.
    put(slot, slot.jname ? bySlot[slot.jname] : bySlot[`${size}${slot.name === "Mining" ? "Mining" : ""}Hardpoint${counters[size]}`]
      || bySlot[`${size}Hardpoint${counters[size]}`] || bySlot[`${size}MiningHardpoint${counters[size]}`]);
  });
  const named = (pattern) => Object.keys(bySlot).filter((name) => pattern.test(name)).sort();
  const internal = named(/^Slot\d+_Size\d+$/);
  // Slots kept for one kind of module have names of their own in the journal.
  const kept = {military: named(/^Military\d+$/), limpets: named(/^LimpetController\d+$/), fighter: named(/^FighterBay\d+$/),
    cargo: named(/^Cargo\d+$/), passenger: named(/^Passenger\d+$/)};
  fresh.slots.filter((slot) => slot.group === "internal").forEach((slot) => {
    const kind = Object.keys(kept).find((key) => new RegExp(key, "i").test(slot.name || ""));
    if (slot.jname) put(slot, bySlot[slot.jname]);
    else if (/approach/i.test(slot.name || "")) put(slot, bySlot.PlanetaryApproachSuite);
    else if (kind && kept[kind].length) put(slot, bySlot[kept[kind].shift()]);
    else if (kind === "military") put(slot, null);
    else put(slot, bySlot[internal.shift()]);
  });
  const armour = String(bySlot.Armour?.Item || "").toLowerCase();
  const grade = BULKHEAD_GRADES.findIndex((g) => armour.includes(`_${g}`));
  fresh.bulkhead = grade >= 0 ? grade : 0;
  fresh.armour = armourFigures(bySlot.Armour);
  fresh.armourEng = armourEngineering(bySlot.Armour?.Engineering);
  return fresh;
}

// Armour's blueprint, grade, roll and experimental (5.8.4.2): what an import without the game's
// figures (Inara's SLEF) still says, and what the ARMOUR controls set.
function armourEngineering(eng) {
  const bp = eng ? blueprintKey(eng.BlueprintName) : "";
  if (!bp) return null;
  const effect = String(eng.ExperimentalEffect || "").toLowerCase();
  const special = !effect ? "" : ships.specials[effect] ? effect : Object.keys(ships.specials).find((key) => ships.specials[key].journal === effect) || "";
  return {bp, grade: n(eng.Level) || 1, roll: eng.Quality != null ? Math.round(n(eng.Quality) * 100) : null, special};
}

// The armour as engineered: hull boost works on 1 + boost (Lightweight G3: 1.8 x 0.97 - 1 = 74.6%), resistances
// on the damage let through, mass straight. Checked against the game's own figures for each.
function engineeredArmour(stock, eng, b) {
  const out = {...stock};
  if (!eng?.bp && !eng?.special) return out;
  const roll = Math.max(0, Math.min(1, n(eng.roll ?? b.roll) / 100));
  const change = (key, value) => {
    if (key === "hullboost") out.hullboost = (1 + n(out.hullboost)) * (1 + value) - 1;
    else if (key in out || RESISTANCES.has(key)) applyChange(out, key, value);
  };
  for (const [key, range] of Object.entries(ships.blueprints[eng.bp]?.grades?.[eng.grade]?.features || {})) {
    if (Array.isArray(range)) change(key, n(range[0]) + (n(range[1]) - n(range[0])) * roll);
  }
  for (const [key, value] of Object.entries(ships.special_actions?.[eng.special] || {})) change(key, n(value));
  return out;
}

// Engineered armour, as the game reported it: its hull boost and resistances as they are
// (not against the stock figure, which can be 0), its mass against the stock mass.
const ARMOUR_FIELDS = {DefenceModifierHealthMultiplier: "hullboost", KineticResistance: "kinres", ThermicResistance: "thermres",
  ExplosiveResistance: "explres", CausticResistance: "causres"};

function armourFigures(row) {
  const eng = row?.Engineering;
  if (!eng?.Modifiers?.length) return null;
  const figures = {blueprint: String(eng.BlueprintName || ""), grade: n(eng.Level)};
  for (const mod of eng.Modifiers) {
    if (ARMOUR_FIELDS[mod.Label]) figures[ARMOUR_FIELDS[mod.Label]] = n(mod.Value) / 100;
    else if (mod.Label === "Mass" && n(mod.OriginalValue)) figures.massRatio = n(mod.Value) / n(mod.OriginalValue);
  }
  return figures;
}

// -- maths ---------------------------------------------------------------------------
const RESISTANCES = new Set(["kinres", "thermres", "explres", "causres"]);

function applyChange(out, key, value) {
  const method = ships.modifications[key]?.method || "multiplicative";
  if (method === "overwrite") out[key] = value;
  else if (!(key in out)) return;
  // A resistance takes its share of the damage that gets through: 1 - (1 - r)(1 - m), as the game does.
  else if (method === "additive" && RESISTANCES.has(key)) out[key] = 1 - (1 - n(out[key])) * (1 - value);
  else if (method === "additive") out[key] = n(out[key]) + value;
  else out[key] = n(out[key]) * (1 + value);
}

// A blueprint grade's figures as your own rolls showed them, for a blueprint the
// ship data has no figures for (the journal's blueprint name, matched like an import).
function learnedFor(slot) {
  if (!slot.bp || !slot.grade) return null;
  for (const [name, grades] of Object.entries(data.learned_figures || {})) {
    const entry = grades[String(slot.grade)];
    if (entry && moduleBlueprint(slot.module, name) === slot.bp) return entry;
  }
  return null;
}

function slotRoll(slot, b = build) {
  return Math.max(0, Math.min(1, n(slot.roll ?? b.roll) / 100));
}

function engineered(slot, b = build) {
  const base = moduleOf(slot.module);
  if (!base) return null;
  const out = {...base};
  if (slot.jmods) {
    // Imported from your ship: the game's figures, experimental and all.
    for (const [key, ratio] of Object.entries(slot.jmods)) if (key in out) out[key] = n(out[key]) * ratio;
    return wholeCurve(base, out);
  }
  const features = slot.bp && slot.grade ? ships.blueprints[slot.bp]?.grades?.[slot.grade]?.features || {} : {};
  const roll = slotRoll(slot, b);
  const learned = Object.keys(features).length ? null : learnedFor(slot);
  for (const [label, [low, high]] of Object.entries(learned?.fields || {})) {
    const key = ships.journal_fields?.[label];
    if (key && key in out) out[key] = n(out[key]) * (n(low) + (n(high) - n(low)) * roll);
  }
  for (const [key, range] of Object.entries(features)) {
    if (!Array.isArray(range)) continue;
    const [low, high] = range;
    applyChange(out, key, n(low) + (n(high) - n(low)) * roll);
  }
  for (const [key, value] of Object.entries(ships.special_actions?.[slot.special] || {})) applyChange(out, key, n(value));
  return wholeCurve(base, out);
}

// Engineering a thruster's or shield generator's optimal multiplier or optimal mass moves its whole
// curve, as the game does: the minimum and maximum go with it.
function wholeCurve(base, out) {
  for (const [opt, ends] of [["optmul", ["minmul", "maxmul"]], ["optmulspeed", ["minmulspeed", "maxmulspeed"]], ["optmass", ["minmass", "maxmass"]]]) {
    if (!n(base[opt]) || n(out[opt]) === n(base[opt])) continue;
    const ratio = n(out[opt]) / n(base[opt]);
    for (const end of ends) {
      // A shield generator's maximum mass only follows its optimal mass up (Optimised leaves it where it was).
      if (end === "maxmass" && ratio < 1 && ["sg", "bsg", "psg"].includes(base.grp)) continue;
      if (end in base && out[end] === base[end]) out[end] = n(base[end]) * ratio;
    }
  }
  return out;
}

function curve(mass, m) {
  // How a thruster or shield generator scales with the mass it carries.
  const [minMass, optMass, maxMass] = [n(m.minmass), n(m.optmass), n(m.maxmass)];
  const [minMul, optMul, maxMul] = [n(m.minmul) || n(m.minmulspeed) || 1, n(m.optmul) || n(m.optmulspeed) || 1, n(m.maxmul) || n(m.maxmulspeed) || 1];
  if (!maxMass || maxMass <= minMass || maxMul === minMul) return optMul || 1;
  const xnorm = Math.max(0, Math.min(1, (maxMass - mass) / (maxMass - minMass)));
  const opt = Math.min(1, (maxMass - optMass) / (maxMass - minMass));
  const exponent = Math.log((optMul - minMul) / (maxMul - minMul)) / Math.log(opt);
  const ynorm = Number.isFinite(exponent) ? Math.pow(xnorm, exponent) : xnorm;
  return minMul + ynorm * (maxMul - minMul);
}

// Resistances stack: each takes its share of what the others let through.
const stack = (values) => 1 - values.reduce((left, value) => left * (1 - n(value)), 1);

function stats(b = build) {
  const ship = ships.ships[b.ship];
  const stock = ship.bulkheads[b.bulkhead] || ship.bulkheads[0] || {};
  const game = b.armour;
  const bulkhead = game ? {...stock, ...Object.fromEntries(Object.values(ARMOUR_FIELDS).filter((key) => key in game).map((key) => [key, game[key]])),
    mass: n(stock.mass) * (game.massRatio || 1)} : engineeredArmour(stock, b.armourEng, b);
  // A module switched off in the game (or here) still weighs and costs what it does, and holds
  // its cargo and fuel; it adds no shields, draws no power and fires nothing.
  const every = b.slots.map((slot) => ({slot, m: engineered(slot, b)})).filter((row) => row.m);
  const fitted = every.filter((row) => !row.slot.off);
  const sum = (key, filter = () => true, rows = fitted) => rows.filter(filter).reduce((total, row) => total + n(row.m[key]), 0);
  const moduleMass = sum("mass", undefined, every);
  const fuel = sum("fuel", undefined, every);
  const cargo = sum("cargo", undefined, every);
  const unladen = n(ship.hullMass) + n(bulkhead.mass) + moduleMass;
  const laden = unladen + fuel + cargo;
  const fsd = fitted.find((row) => row.slot.group === "standard" && row.slot.index === 2)?.m;
  const boost = sum("jumpboost");
  const jump = (mass, fuelUse) => fsd && fsd.optmass ? n(fsd.optmass) / mass * Math.pow(Math.min(n(fsd.maxfuel), fuelUse) / n(fsd.fuelmul), 1 / n(fsd.fuelpower)) + boost : 0;
  const thrusters = fitted.find((row) => row.slot.group === "standard" && row.slot.index === 1)?.m;
  const speedMul = thrusters ? curve(unladen + fuel, thrusters) : 1;
  const shield = fitted.find((row) => ["sg", "bsg", "psg"].includes(row.m.grp))?.m;
  const boosters = sum("shieldboost", (row) => row.m.grp === "sb");
  // A hull heavier than the generator's maximum mass gets no shields from it.
  const shields = shield && !(n(shield.maxmass) && n(ship.hullMass) > n(shield.maxmass))
    ? n(ship.baseShieldStrength) * curve(n(ship.hullMass), shield) * (1 + boosters) + sum("shieldaddition") : 0;
  // Boosting takes the boost cost from the engine capacitor at once: one too small can't boost at all.
  const distributor = fitted.find((row) => row.slot.group === "standard" && row.slot.index === 4)?.m;
  const canBoost = !distributor || !n(ship.boostEnergy) || n(distributor.engcap) >= n(ship.boostEnergy);
  const armour = n(ship.baseArmour) * (1 + n(bulkhead.hullboost) + sum("hullboost", (row) => row.m.grp !== "bh")) + sum("hullreinforcement");
  const plant = fitted.find((row) => row.slot.group === "standard" && row.slot.index === 0)?.m;
  const draw = sum("power");
  const dps = fitted.filter((row) => row.slot.group === "hardpoints").reduce((total, row) => {
    const m = row.m;
    if (!m.damage) return total;
    if (m.grp === "bl") return total + n(m.damage);
    const perSecond = m.fireint ? 1 / n(m.fireint) : n(m.rof) || 1;
    return total + n(m.damage) * perSecond * (n(m.roundspershot) || 1);
  }, 0);
  const cost = n(ship.hullCost) + n(bulkhead.cost) + sum("cost", undefined, every);
  const hullParts = [bulkhead, ...fitted.filter((row) => ["hr", "mahr", "ghrp"].includes(row.m.grp)).map((row) => row.m)];
  const shieldParts = shield ? [shield, ...fitted.filter((row) => row.m.grp === "sb").map((row) => row.m)] : [];
  const res = (parts) => Object.fromEntries(["kinres", "thermres", "explres", "causres"].map((key) => [key, stack(parts.map((part) => part[key]))]));
  const weaponsHeat = fitted.filter((row) => row.slot.group === "hardpoints").reduce((total, row) => {
    const m = row.m;
    if (!m.thermload) return total;
    return total + (m.grp === "bl" ? n(m.thermload) : n(m.thermload) * (m.fireint ? 1 / n(m.fireint) : n(m.rof) || 1));
  }, 0);
  return {unladen, laden, fuel, cargo, jumpEmpty: jump(unladen + n(fsd?.maxfuel), n(fsd?.maxfuel)), jumpFull: jump(laden, n(fsd?.maxfuel)),
    speed: n(ship.speed) * speedMul, boost: canBoost ? n(ship.boost) * speedMul : 0, canBoost, shields, armour, power: n(plant?.pgen), draw, dps, cost,
    wepcap: n(fitted.find((row) => row.slot.group === "standard" && row.slot.index === 4)?.m?.wepcap),
    hullRes: res(hullParts), shieldRes: res(shieldParts), heatCapacity: n(ship.heatCapacity),
    idleHeat: n(plant?.eff) * draw, jumpHeat: n(fsd?.thermload), weaponsHeat};
}

// -- the wishlist ---------------------------------------------------------------------
function groupLabel(module) {
  return ships.groups[module?.grp]?.label || "";
}

function wishItems() {
  const items = [];
  for (const slot of build.slots) {
    const module = moduleOf(slot.module);
    if (!module) continue;
    if (slot.bp && slot.grade && ref?.blueprints) {
      const wanted = slot.bp.toLowerCase();
      const label = groupLabel(module);
      let found = null;
      for (const [mod, blueprints] of Object.entries(ref.blueprints)) {
        for (const [name, entry] of Object.entries(blueprints)) {
          if (!(entry.fdnames || [entry.fdname]).some((fdname) => String(fdname).toLowerCase() === wanted)) continue;
          if (!found || mod.toLowerCase() === label.toLowerCase()) found = [mod, name];
        }
      }
      if (found) items.push({type: "blueprint", module: found[0], name: found[1], from: 0, grade: slot.grade, slot: `${slotLabel(slot)}: ${module.name || label}`});
    }
    const special = ref?.experimentals?.[slot.special] ? slot.special : ships.specials[slot.special]?.journal;
    if (special && ref?.experimentals?.[special]) items.push({type: "experimental", fdname: special, module: groupLabel(module)});
  }
  const armour = build.armourEng;
  if (armour?.bp && armour.grade && ref?.blueprints) {
    const wanted = armour.bp.toLowerCase();
    for (const [mod, blueprints] of Object.entries(ref.blueprints)) {
      const name = Object.keys(blueprints).find((key) => (blueprints[key].fdnames || [blueprints[key].fdname]).some((fd) => String(fd).toLowerCase() === wanted));
      if (name) { items.push({type: "blueprint", module: mod, name, from: 0, grade: armour.grade, slot: "Armour"}); break; }
    }
  }
  const armourSpecial = ref?.experimentals?.[armour?.special] ? armour.special : ships.specials[armour?.special]?.journal;
  if (armourSpecial && ref?.experimentals?.[armourSpecial]) items.push({type: "experimental", fdname: armourSpecial, module: "Armour"});
  return items;
}

// -- drawing ---------------------------------------------------------------------------
function slotLabel(slot) {
  if (slot.group === "standard") return STANDARD_LABELS[slot.index];
  if (slot.group === "utility") return "Utility";
  if (slot.group === "hardpoints") return `${HARDPOINT_SIZES[slot.size]} hardpoint`;
  return slot.name ? `${slot.name.replace(/([a-z])([A-Z])/g, "$1 $2")} ${slot.size}` : `Internal ${slot.size}`;
}

// Every module that fits a slot, as [id, module].
function fits(slot) {
  return Object.entries(ships.modules).filter(([, m]) => {
    if (slot.group === "standard") return m.grp === ships.standard[slot.index] && m.class <= slot.size;
    const kind = ships.groups[m.grp]?.kind;
    if (slot.group === "utility") return kind === "hardpoints" && m.class === 0;
    if (slot.group === "hardpoints") return kind === "hardpoints" && m.class > 0 && m.class <= slot.size;
    if (kind !== "internal" || m.class > slot.size) return false;
    // Mk II cargo racks fit only a ship's dedicated cargo slots.
    if (m.restriction && String(slot.name || "").toLowerCase() !== String(m.restriction).toLowerCase()) return false;
    if (slot.eligible) return slot.eligible.includes(m.grp);
    return !["pas"].includes(m.grp);
  });
}

const MOUNT_WORD = {F: "Fixed", G: "Gimballed", T: "Turreted"};
const moduleTitle = (m) => `${m.name || groupLabel(m)}${m.mount ? ` · ${MOUNT_WORD[m.mount] || m.mount}` : ""}`;

function armourControls() {
  const eligible = ships.eligible.bh || {};
  const eng = build.armourEng || {};
  const grades = eng.bp ? Object.keys(ships.blueprints[eng.bp]?.grades || {}).map(Number) : [];
  return `<select data-ms-armour="bp" aria-label="Armour blueprint"><option value="">No blueprint</option>${Object.keys(eligible.blueprints || {}).map((key) =>
      `<option value="${esc(key)}"${key === eng.bp ? " selected" : ""}>${esc(ships.blueprints[key]?.name || key)}</option>`).join("")}</select>
    ${eng.bp ? `<select data-ms-armour="grade" aria-label="Armour grade">${grades.map((g) => `<option value="${g}"${g === n(eng.grade) ? " selected" : ""}>G${g}</option>`).join("")}</select>` : ""}
    ${(eligible.specials || []).length ? `<select data-ms-armour="special" aria-label="Armour experimental"><option value="">No experimental</option>${eligible.specials.map((key) =>
      `<option value="${esc(key)}"${key === eng.special ? " selected" : ""}>${esc(ships.specials[key]?.name || key)}</option>`).join("")}</select>` : ""}`;
}

function engineeringControls(slot) {
  const module = moduleOf(slot.module);
  const eligible = module ? ships.eligible[module.grp] : null;
  if (!eligible) return `<span class="mt-dim">—</span>`;
  // A few newer blueprints are for one size of module only.
  const blueprints = Object.keys(eligible.blueprints || {}).filter((key) => {
    const only = eligible.blueprints[key].symbols;
    return !only || key === slot.bp || new RegExp(only).test(module.symbol || "");
  });
  const grades = slot.bp ? Object.keys(eligible.blueprints?.[slot.bp]?.grades || {}).map(Number) : [];
  const specials = eligible.specials || [];
  return `<select data-ms-slot="bp" data-slot="${build.slots.indexOf(slot)}"><option value="">No blueprint</option>${blueprints.map((key) =>
      `<option value="${esc(key)}"${key === slot.bp ? " selected" : ""}>${esc(ships.blueprints[key]?.name || key)}</option>`).join("")}</select>
    ${slot.bp ? `<select data-ms-slot="grade" data-slot="${build.slots.indexOf(slot)}">${grades.map((g) => `<option value="${g}"${g === slot.grade ? " selected" : ""}>G${g}</option>`).join("")}</select>` : ""}
    ${slot.bp ? `<select data-ms-slot="roll" data-slot="${build.slots.indexOf(slot)}" title="How good this module's rolls are">${[["", `Rolls ${n(build.roll)}%`], ...[0, 25, 50, 75, 100].map((r) => [String(r), `${r}%`])].map(([value, label]) =>
      `<option value="${value}"${String(slot.roll ?? "") === value ? " selected" : ""}>${label}</option>`).join("")}</select>` : ""}
    ${slot.bpName ? `<span class="mt-tag" title="A blueprint the builder's tables don't have yet">${esc(slot.bpName)}</span>` : ""}
    ${slot.bp && ships.blueprints[slot.bp]?.nofigures && !slot.jmods ? (learnedFor(slot)
      ? `<span class="mt-tag" title="Figures from ${learnedFor(slot).rolls} reading${learnedFor(slot).rolls === 1 ? "" : "s"} of your own engineering at this grade">LEARNED FIGURES</span>`
      : `<span class="mt-tag" title="A newer blueprint: its materials go on the wishlist; its figures fill in once you engineer one at this grade">MATERIALS ONLY</span>`) : ""}
    ${slot.jmods ? `<span class="mt-tag" title="The figures your ship reported, until you change this slot">GAME FIGURES</span>` : ""}
    ${specials.length ? `<select data-ms-slot="special" data-slot="${build.slots.indexOf(slot)}"><option value="">No experimental</option>${specials.map((key) =>
      `<option value="${esc(key)}"${key === slot.special ? " selected" : ""}>${esc(ships.specials[key]?.name || key)}</option>`).join("")}</select>` : ""}`;
}

// Under the fitting panel (5.8.5): the build's figures, one tab at a time.
const ANALYSIS = [["figures", "FIGURES"], ["defence", "DEFENCE"], ["heat", "HEAT & POWER"], ["compare", "COMPARE"], ["materials", "MATERIALS"]];
let analysisTab = "figures";

function analysis() {
  const s = stats();
  const ship = ships.ships[build.ship];
  const tiles = [["UNLADEN", `${fixed(s.unladen)} t`], ["LADEN", `${fixed(s.laden)} t`], ["JUMP (MAX)", `${fixed(s.jumpEmpty, 2)} ly`],
    ["JUMP (LADEN)", `${fixed(s.jumpFull, 2)} ly`], ["SPEED", `${whole(s.speed)} m/s`], ["BOOST", s.canBoost ? `${whole(s.boost)} m/s` : "CAN'T BOOST"],
    ["SHIELDS", `${whole(s.shields)} MJ`], ["ARMOUR", whole(s.armour)], ["CARGO", `${whole(s.cargo)} t`], ["FUEL", `${whole(s.fuel)} t`],
    ["RAW DPS", fixed(s.dps)], ["COST", `${money(s.cost)} CR`]];
  const powerShare = s.power ? s.draw / s.power : 0;
  const pct = (value) => `${(n(value) * 100).toFixed(1)}%`;
  const resRow = (label, res) => `<tr><td>${label}</td>${["kinres", "thermres", "explres", "causres"].map((key) => `<td class="num${n(res[key]) < 0 ? " short" : ""}">${pct(res[key])}</td>`).join("")}</tr>`;
  const other = compareId ? (data.ship_builds || []).find((row) => row.id === compareId) : null;
  const versus = other ? fromSaved(other) : null;
  const cmp = versus ? stats(versus) : null;
  const diffRows = cmp ? [["Jump (max)", "jumpEmpty", 2, " ly"], ["Jump (laden)", "jumpFull", 2, " ly"], ["Speed", "speed", 0, " m/s"], ["Boost", "boost", 0, " m/s"],
    ["Shields", "shields", 0, " MJ"], ["Armour", "armour", 0, ""], ["Cargo", "cargo", 0, " t"], ["Raw DPS", "dps", 1, ""], ["Power spare", null, 2, " MW"], ["Cost", "cost", 0, " CR"]]
    .map(([label, key, digits, unit]) => {
      const mine = key ? s[key] : s.power - s.draw, theirs = key ? cmp[key] : cmp.power - cmp.draw;
      const diff = mine - theirs;
      const better = key === "cost" ? diff < 0 : diff > 0;
      return `<tr><td>${label}</td><td class="num">${fixed(mine, digits)}${unit}</td><td class="num">${fixed(theirs, digits)}${unit}</td><td class="num ${Math.abs(diff) < 1e-6 ? "" : better ? "ok" : "short"}">${diff > 0 ? "+" : ""}${fixed(diff, digits)}</td></tr>`;
    }).join("") : "";
  const compare = `<h4>COMPARE</h4><select data-ms-compare><option value="">Against another saved build…</option>${(data.ship_builds || []).filter((row) => row.id !== build.id).map((row) =>
    `<option value="${esc(row.id)}"${row.id === compareId ? " selected" : ""}>${esc(row.name)} · ${esc(ships.ships[row.ship]?.name || row.ship)}</option>`).join("")}</select>
    ${cmp ? `<table class="mt-table mt-compare"><thead><tr><th></th><th class="num">THIS</th><th class="num">${esc(versus.name)}</th><th class="num">±</th></tr></thead><tbody>${diffRows}</tbody></table>` : ""}`;
  const heat = `<h4>HEAT</h4><table class="mt-table"><tbody><tr><td>Heat capacity</td><td class="num">${s.heatCapacity ? whole(s.heatCapacity) : `<span class="mt-dim" title="Not published for this hull yet">not known yet</span>`}</td></tr>
    <tr><td>Heat from the power plant (at this draw)</td><td class="num">${fixed(s.idleHeat, 2)} /s</td></tr>${s.jumpHeat ? `<tr><td>Heat per jump (FSD)</td><td class="num">${fixed(s.jumpHeat, 1)}</td></tr>` : ""}
    <tr><td>Weapons firing</td><td class="num">${fixed(s.weaponsHeat, 1)} /s</td></tr></tbody></table>`;
  const resistances = `<h4>RESISTANCES</h4><table class="mt-table"><thead><tr><th></th><th class="num">KIN</th><th class="num">THERM</th><th class="num">EXPL</th><th class="num">CAUS</th></tr></thead>
    <tbody>${resRow("Hull", s.hullRes)}${s.shields ? resRow("Shields", s.shieldRes) : ""}</tbody></table>
    <p class="mt-dim">Stacked as fitted; the game softens resistances above about 30%.</p>`;
  const power = `<div class="mt-power ${powerShare > 1 ? "short" : "ok"}"><span>POWER ${fixed(s.draw, 2)} / ${fixed(s.power, 2)} MW</span><span class="mt-bar"><i style="width:${Math.min(100, powerShare * 100).toFixed(1)}%"></i></span>
      ${powerShare > 1 ? "<b>Over the plant's output: some modules will shut down</b>" : ""}</div>`;
  const notes = `${ship.described && !ship.hullMass ? `<p class="mt-note">The ${esc(ship.name)} isn't in the builder's tables yet: its slots and modules come from your build, but its own figures (mass, speed, shields, armour) aren't known, so jump range, speed and defences here leave the hull out.</p>` : ""}
    ${ship.massFromJournal ? `<p class="mt-note">The ${esc(ship.name)}'s hull mass is ${fixed(ship.hullMass)} t, from your journal: the game's own figures for the one you fly put it there, not at the ${fixed(ship.tableHullMass)} t the builder's tables give.</p>` : ""}
    ${ship.described && ship.hullMass && ship.learned ? `<p class="mt-note">The ${esc(ship.name)} isn't in the builder's tables yet, so it was learned from your journal: its slots from your Loadout, and its mass (${fixed(ship.hullMass)} t, with the armour you fly) from the ship's unladen mass less its modules. Jump range and mass are right; speed, shields and armour aren't known yet, so those leave the hull out.</p>` : ""}
`;
  const about = `<p class="mt-dim">${esc(ship.manufacturer || "")} · class ${esc(ship.class || "")} landing pad · mass lock ${esc(ship.masslock || "")} · rolls at ${whole(build.roll)}%. Figures are worked out here and can differ a little from the game's; slots marked GAME FIGURES use what your ship reported.</p>`;
  const defence = `<div class="mt-tiles mt-ship-tiles sb-defence-tiles">${[["SHIELDS", `${whole(s.shields)} MJ`], ["ARMOUR", whole(s.armour)],
    ["HARDNESS", ship.hardness ? whole(ship.hardness) : "—"]].map(([label, value]) => `<div class="mt-tile"><span>${label}</span><b>${esc(value)}</b></div>`).join("")}</div>${resistances}`;
  const body = {
    figures: `<div class="mt-tiles mt-ship-tiles">${tiles.map(([label, value]) => `<div class="mt-tile"><span>${label}</span><b>${esc(value)}</b></div>`).join("")}</div>${about}`,
    defence, heat: `${power}${heat}`, compare, materials: materialsPanel(),
  }[analysisTab] || "";
  const tabs = ANALYSIS.map(([key, label]) => `<button type="button" class="sb-tab${analysisTab === key ? " on" : ""}" data-ms-op="analysis" data-tab="${key}">${label}${
    key === "compare" && cmp ? " <small>●</small>" : key === "heat" && powerShare > 1 ? " <small class=\"warn\">!</small>" : ""}</button>`).join("");
  return `<section class="sb-analysis">${notes}<nav class="sb-tabs">${tabs}</nav><div class="sb-analysis-body">${body}</div></section>`;
}

function materialsPanel() {
  if (!ref?.blueprints) return "";
  const need = {};
  for (const item of wishItems()) {
    const entry = item.type === "blueprint" ? ref.blueprints[item.module]?.[item.name] : null;
    const add = (list, times) => (list || []).forEach((row) => { need[row.symbol] = (need[row.symbol] || {name: row.name, count: 0}); need[row.symbol].count += row.count * times; });
    if (entry) Object.entries(entry.grades).forEach(([grade, recipe]) => { if (Number(grade) <= item.grade) add(recipe.ingredients, Number(grade)); });
    if (item.type === "experimental") add(ref.experimentals[item.fdname]?.ingredients, 1);
  }
  const owned = (data.have || {}).horizons || {};
  const rows = Object.entries(need).sort(([, a], [, b]) => a.name.localeCompare(b.name));
  if (!rows.length) return `<p class="mt-dim">Pick blueprints to see the materials this build takes.</p>`;
  return `<h4>MATERIALS FROM STOCK</h4><table class="mt-table"><tbody>${rows.map(([symbol, row]) => {
    const got = n(owned[symbol]);
    return `<tr class="${got >= row.count ? "ok" : "short"}"><td>${esc(row.name)}</td><td class="num">${whole(got)} / ${whole(row.count)}</td></tr>`;
  }).join("")}</tbody></table>`;
}

function importBar() {
  return `<form class="mt-codebar" data-ms-import><input name="code" placeholder="Paste a build: SLEF (EDSY: Outfitting › Export...), a journal Loadout, an EDMC ship link or a shared build code" autocomplete="off" spellcheck="false"><button type="submit">IMPORT BUILD</button></form>`;
}

// Your ships and builds in alphabetical order, by name, then hull.
const byName = (name, hull) => (a, b) => name(a).localeCompare(name(b), undefined, {sensitivity: "base"}) || hull(a).localeCompare(hull(b));
const fleetName = (row) => String(row.name || "").trim() || fleetHull(row);
const fleetHull = (row) => Object.values(ships.ships).find((ship) => ship.symbol === row.ship)?.name || (data.ship_names || {})[row.ship] || row.ship;
const sortedFleet = () => [...(data.fleet || [])].sort(byName(fleetName, fleetHull));
const sortedBuilds = () => [...(data.ship_builds || [])].sort(byName((row) => String(row.name || ""), (row) => ships.ships[row.ship]?.name || String(row.ship)));

function savedList() {
  const builds = sortedBuilds();
  return `<select data-ms-saved><option value="">${builds.length ? "Saved builds…" : "No saved builds"}</option>${builds.map((row) =>
    `<option value="${esc(row.id)}"${row.id === build?.id ? " selected" : ""}>${esc(row.name)} · ${esc(ships.ships[row.ship]?.name || row.ship)}</option>`).join("")}</select>`;
}

// Every ship you own (its latest Loadout), the one you're in first. Only names come with
// each refresh; a ship's whole Loadout is fetched when you open it.
function fleetList() {
  const fleet = sortedFleet();
  if (!fleet.length) return data.ship_loadout ? `<button type="button" class="ghost" data-ms-op="current">YOUR SHIP NOW</button>` : "";
  const type = (row) => Object.values(ships.ships).find((ship) => ship.symbol === row.ship)?.name || (data.ship_names || {})[row.ship] || row.ship;
  return `<select data-ms-fleet title="Open one of your ships as you last flew it"><option value="">Your ships…</option>${fleet.map((row) =>
    `<option value="${esc(row.id)}"${row.id === build?.fleet ? " selected" : ""}>${esc(String(row.name || "").trim() || type(row))}${row.ident ? ` [${esc(row.ident)}]` : ""} · ${esc(type(row))}${row.now ? " (flying)" : ""}</option>`).join("")}</select>`;
}

function openSaved(id) {
  const saved = (data.ship_builds || []).find((row) => row.id === id);
  const loaded = saved ? fromSaved(saved) : null;
  if (!loaded) return;
  build = loaded;
  mode = "outfit";
  // Saved on a hull that was new then and is in the tables now: keep it on the real hull, so it
  // stays there and its share code no longer has to describe the hull.
  if (String(saved.ship).startsWith("described:") && loaded.ship !== saved.ship) op("build_save", {build: plain(loaded)});
}

async function openShip(id) {
  try {
    const response = await fetch(ui.apiUrl(`/api/data/materials-ship?id=${encodeURIComponent(id)}`), {cache: "no-store"});
    const loadout = response.ok ? await response.json() : null;
    const loaded = loadout?.Ship ? fromLoadout(loadout) : null;
    if (!loaded) { ui.showToast?.("That ship's loadout isn't one the builder can read yet"); return; }
    loaded.fleet = id;
    build = loaded;
      mode = "outfit";
  } catch {
    ui.showToast?.("Couldn't open that ship");
  }
  draw();
}

// -- the look (5.8.5): a shipyard, a slot ledger, the hull's anatomy and a fitting panel ----------
// The hulls' illustrations and top and bottom schematics (with where each mount sits) are masks the
// theme colours fill: ship-art/<symbol>/ and ship-art/index.json, credited in THIRD_PARTY_NOTICES.md.
let art = null;
let artState = "idle";
let selected = null;        // the slot being fitted: an index into build.slots, or "armour"
let selectedFor = null;     // the build that selection belongs to
let category = "";
let side = "top";          // the hull view: its "top" or "bottom" schematic
let ledgerTab = "all";
let yardSize = "all";
let yardSort = ["name", 1];
let yardPick = "";

const PAD = ["", "Small", "Medium", "Large"];
const SIZE_LETTER = {4: "H", 3: "L", 2: "M", 1: "S"};
const LEDGER = [["hardpoints", "HARDPOINTS"], ["utility", "UTILITY MOUNTS"], ["standard", "CORE INTERNALS"], ["internal", "OPTIONAL INTERNALS"]];
const CORE_SHORT = ["PWR", "THR", "FSD", "LIFE", "DIST", "SENS", "FUEL"];

function loadArt() {
  if (artState !== "idle") return;
  artState = "loading";
  fetch(ui.apiUrl("/ship-art/index.json"), {cache: "no-cache"})
    .then((response) => (response.ok ? response.json() : {}))
    .catch(() => ({}))
    .then((json) => { art = json || {}; artState = "ready"; draw(); });
}

const artUrl = (ship, file) => ui.apiUrl(`/ship-art/${encodeURIComponent(ship.symbol)}/${file}.webp`);
const artMask = (ship, file, cls) => `<i class="mt-art ${cls}" style="--art: url('${artUrl(ship, file)}')" aria-hidden="true"></i>`;

function hullSlots(ship) {
  const hp = (ship.slots.hardpoints || []).map((x) => (typeof x === "object" ? x.class : x));
  const internal = (ship.slots.internal || []).filter((x) => !(typeof x === "object" && x.name === "PlanetaryApproachSuite"))
    .map((x) => (typeof x === "object" ? x.class : x));
  return {hard: hp.filter((x) => x > 0), utility: hp.filter((x) => x === 0).length, core: ship.slots.standard || [], internal};
}

function mountSummary(ship) {
  const counts = {};
  for (const size of hullSlots(ship).hard) counts[size] = (counts[size] || 0) + 1;
  return [4, 3, 2, 1].filter((size) => counts[size]).map((size) => `${counts[size]}${SIZE_LETTER[size]}`).join(" ");
}

function sizeChips(sizes) {
  const counts = {};
  for (const size of sizes) counts[size] = (counts[size] || 0) + 1;
  return Object.keys(counts).map(Number).sort((a, b) => b - a)
    .map((size) => `<span class="mt-chipbox">${counts[size] > 1 ? `<small>${counts[size]} ×</small> ` : ""}${size}</span>`).join("");
}

// -- the shipyard -------------------------------------------------------------------------------
function yardRows() {
  const wanted = shipFilter.toLowerCase();
  const [key, dir] = yardSort;
  const value = (ship) => key === "name" ? ship.name : key === "maker" ? ship.manufacturer || "" : key === "size" ? n(ship.class)
    : key === "mounts" ? hullSlots(ship).hard.reduce((sum, size) => sum + size * 10 + 1, 0) : n(ship.cost);
  return Object.entries(ships.ships)
    .filter(([, ship]) => !wanted || `${ship.name} ${ship.manufacturer}`.toLowerCase().includes(wanted))
    .filter(([, ship]) => yardSize === "all" || PAD[ship.class]?.toLowerCase() === yardSize)
    .sort(([, a], [, b]) => {
      const x = value(a), y = value(b);
      return (typeof x === "string" ? x.localeCompare(y) : x - y) * dir || a.name.localeCompare(b.name);
    });
}

function shipCard(key) {
  const ship = ships.ships[key];
  if (!ship) return `<aside class="mt-card"><p class="mt-dim">Pick a hull.</p></aside>`;
  const slots = hullSlots(ship);
  const stat = (label, value) => `<div><span>${label}</span><b>${value || "—"}</b></div>`;
  return `<aside class="mt-card">
    <div class="mt-card-art">${art?.[ship.symbol] ? artMask(ship, "illustration", "mt-art-illustration") : `<span class="mt-dim">No illustration yet</span>`}</div>
    <h3>${esc(ship.name)}</h3>
    <p class="mt-card-sub">${ship.learned ? "New · learned from your journal" : `${esc(ship.manufacturer || "")}${ship.class ? ` · ${PAD[ship.class]} landing pad` : ""}`}</p>
    <div class="mt-card-stats">${stat("SPEED m/s", ship.speed && whole(ship.speed))}${stat("BOOST m/s", ship.boost && whole(ship.boost))}
      ${stat("SHIELD MJ", ship.baseShieldStrength && whole(ship.baseShieldStrength))}${stat("ARMOUR", ship.baseArmour && whole(ship.baseArmour))}
      ${stat("HULL MASS t", ship.hullMass && whole(ship.hullMass))}${stat("HARDNESS", ship.hardness && whole(ship.hardness))}
      ${stat("CREW", ship.crew && whole(ship.crew))}${stat("MASS LOCK", ship.masslock && whole(ship.masslock))}</div>
    <h4>HARDPOINTS <small>${slots.hard.length}</small></h4><div class="mt-chips">${[4, 3, 2, 1].filter((size) => slots.hard.includes(size))
      .map((size) => `<span class="mt-chipbox">${slots.hard.filter((x) => x === size).length} <small>${["", "SMALL", "MED", "LARGE", "HUGE"][size]}</small></span>`).join("") || `<span class="mt-dim">None</span>`}</div>
    <h4>UTILITY MOUNTS <small>${slots.utility}</small></h4>
    <h4>CORE INTERNALS</h4><div class="mt-chips">${slots.core.map((size, i) => `<span class="mt-chipbox"><small>${CORE_SHORT[i]}</small> ${size}</span>`).join("")}</div>
    <h4>OPTIONAL INTERNALS <small>${slots.internal.length}</small></h4><div class="mt-chips">${sizeChips(slots.internal)}</div>
    <div class="mt-card-price"><span>HULL PRICE</span><b>${ship.cost ? `${whole(ship.cost)} <small>cr</small>` : "—"}</b></div>
    <button type="button" class="mt-hull" data-ms-op="new" data-ship="${esc(key)}">BUILD THIS HULL</button>
  </aside>`;
}

function shipyard() {
  const rows = yardRows();
  const pick = yardPick && ships.ships[yardPick] ? yardPick : rows[0]?.[0] || "";
  const head = (key, label, num) => `<th class="${num ? "num " : ""}mt-sort${yardSort[0] === key ? " on" : ""}" data-ms-op="yard_sort" data-key="${key}">${label}${yardSort[0] === key ? (yardSort[1] > 0 ? " ▲" : " ▼") : ""}</th>`;
  return `<div class="mt-yard">
    <div class="mt-yard-split"><div class="mt-yard-list">
      <div class="mt-yard-tools"><label class="mt-search"><input type="search" data-ms-filter value="${esc(shipFilter)}" placeholder="Search ships or makers" autocomplete="off"></label>
        <div class="mt-seg">${["all", "small", "medium", "large"].map((size) => `<button type="button" class="mt-seg-btn${yardSize === size ? " on" : ""}" data-ms-op="yard_size" data-size="${size}">${size.toUpperCase()}</button>`).join("")}</div></div>
      <table class="mt-table mt-yard-table"><thead><tr>${head("name", "SHIP")}${head("maker", "MAKER")}${head("size", "SIZE")}${head("mounts", "HARDPOINTS", true)}${head("price", "PRICE Mcr", true)}</tr></thead>
      <tbody>${rows.map(([key, ship]) => `<tr class="mt-yard-row${key === pick ? " on" : ""}" data-ms-op="yard_pick" data-ship="${esc(key)}">
        <td><b>${esc(ship.name)}</b>${ship.learned ? ` <span class="mt-tag">NEW</span>` : ""}</td><td>${esc(ship.manufacturer || "")}</td>
        <td class="mt-dim">${["", "SML", "MED", "LRG"][ship.class] || ""}</td><td class="num">${mountSummary(ship)}</td>
        <td class="num">${ship.cost ? (n(ship.cost) / 1e6).toFixed(2) : "—"}</td></tr>`).join("")}</tbody></table></div>
      ${shipCard(pick)}</div></div>`;
}

// -- outfitting ---------------------------------------------------------------------------------
// Each slot's number within its group, as the ledger and the hull's anatomy show it.
function slotNumbers() {
  const counts = {}, numbers = new Map();
  for (const slot of build.slots) {
    counts[slot.group] = (counts[slot.group] || 0) + 1;
    numbers.set(slot, counts[slot.group]);
  }
  return numbers;
}

function engineeringLine(slot, m) {
  const parts = [];
  if (m?.mount) parts.push(MOUNT_WORD[m.mount] || m.mount);
  if (slot.bp) parts.push(`${ships.blueprints[slot.bp]?.name || slot.bp} G${slot.grade}`);
  else if (slot.bpName) parts.push(`${slot.bpName} G${slot.bpGrade}`);
  if (slot.special) parts.push(ships.specials[slot.special]?.name || slot.special);
  return parts.join(" · ");
}

function ledgerRow(slot, numbers) {
  const index = build.slots.indexOf(slot);
  const m = moduleOf(slot.module);
  const title = m ? moduleTitle(m).split(" · ")[0] : slot.unknown ? slot.unknown : slot.group === "standard" ? slotLabel(slot) : "Empty";
  const engineered = slot.bp || slot.special || slot.bpName || slot.jmods;
  return `<div class="mt-led${index === selected ? " on" : ""}${m || slot.unknown ? "" : " empty"}${slot.off ? " off" : ""}" role="button" tabindex="0"
      data-ms-op="select" data-slot="${index}" data-group="${slot.group}" data-module="${esc(slot.module || "")}" data-bp="${esc(slot.bp || "")}">
    <span class="mt-led-size">${slot.size}</span><span class="mt-led-num">${numbers.get(slot)}</span>
    <span class="mt-led-main"><b>${esc(title)}</b>${m ? `<i class="mt-led-chip">${m.class}${esc(m.rating || "")}</i>` : ""}
      <small>${esc(slot.unknown && !m ? "not in the builder's tables yet" : engineeringLine(slot, m) || (slot.group === "standard" && m ? slotLabel(slot) : ""))}</small></span>
    ${m ? `<button type="button" class="mt-onoff${slot.off ? " off" : ""}" data-ms-op="power" data-slot="${index}" title="${slot.off ? "Switched off: adds no shields, draws no power, fires nothing. Switch it on" : "Switch this module off"}">${slot.off ? "OFF" : "ON"}</button>` : ""}
    ${engineered ? `<span class="mt-led-eng" title="Engineered">⚙</span>` : ""}</div>`;
}

function ledger() {
  const numbers = slotNumbers();
  const ship = ships.ships[build.ship];
  const bulkhead = ship.bulkheads[build.bulkhead] || {};
  const armourEng = build.armourEng?.bp ? `${ships.blueprints[build.armourEng.bp]?.name || build.armourEng.bp} G${build.armourEng.grade}` : "";
  const tabs = [["all", "ALL"], ...LEDGER.map(([group, label]) => [group, label.split(" ")[0]])].map(([key, label]) => {
    const rows = key === "all" ? build.slots : build.slots.filter((slot) => slot.group === key);
    return `<button type="button" class="mt-seg-btn${ledgerTab === key ? " on" : ""}" data-ms-op="ledger_tab" data-tab="${key}">${label} <small>${rows.filter((slot) => slot.module).length}/${rows.length}</small></button>`;
  }).join("");
  const groups = LEDGER.filter(([group]) => ledgerTab === "all" || ledgerTab === group).map(([group, label]) => {
    const rows = build.slots.filter((slot) => slot.group === group);
    if (!rows.length) return "";
    const armour = group === "standard" ? `<div class="mt-led${selected === "armour" ? " on" : ""}" role="button" tabindex="0" data-ms-op="select" data-slot="armour">
        <span class="mt-led-size" title="Armour">◆</span><span class="mt-led-num">·</span>
        <span class="mt-led-main"><b>${esc(bulkhead.name || "Armour")}</b><small>${esc(armourEng || "Armour")}</small></span>
        ${armourEng || build.armour ? `<span class="mt-led-eng" title="Engineered">⚙</span>` : ""}</div>` : "";
    return `<h4>${label} <small>${rows.length}</small></h4>${armour}${rows.map((slot) => ledgerRow(slot, numbers)).join("")}`;
  }).join("");
  return `<section class="mt-ledger"><div class="mt-seg mt-ledger-tabs">${tabs}</div>${groups}</section>`;
}

function anatomy() {
  const ship = ships.ships[build.ship];
  const plan = art?.[ship.symbol];
  if (!plan) return `<section class="mt-anatomy"><h4>HULL ANATOMY</h4><p class="mt-dim">${artState === "ready" ? "No schematic for this hull yet." : "Loading the hull's schematic…"}</p></section>`;
  const numbers = slotNumbers();
  const byName = new Map(build.slots.filter((slot) => slot.jname).map((slot) => [slot.jname, slot]));
  const plate = (view) => {
    const marks = view.mounts.map((mount) => {
      const slot = byName.get(mount.slot);
      if (!slot) return "";
      const index = build.slots.indexOf(slot);
      const cls = [slot.group === "utility" ? "utility" : "", slot.module ? "fitted" : "empty", index === selected ? "on" : "", slot.off ? "off" : ""].join(" ");
      const m = moduleOf(slot.module);
      return `<button type="button" class="mt-mark ${cls}" style="left: ${(mount.x / view.view[0] * 100).toFixed(2)}%; top: ${(mount.y / view.view[1] * 100).toFixed(2)}%"
        data-ms-op="select" data-slot="${index}" title="${esc(slotLabel(slot))} ${numbers.get(slot)}${m ? `: ${m.class}${m.rating || ""} ${moduleTitle(m)}` : ": empty"}">${numbers.get(slot)}</button>`;
    }).join("");
    return `<figure class="mt-plate">
      <div class="mt-plate-box" style="aspect-ratio: ${view.view[0]} / ${view.view[1]}">${artMask(ship, side, "mt-art-plan")}${marks}</div></figure>`;
  };
  const toggle = ["top", "bottom"].map((key) => `<button type="button" class="mt-seg-btn${side === key ? " on" : ""}" data-ms-op="side" data-side="${key}">${key.toUpperCase()}</button>`).join("");
  return `<section class="mt-anatomy"><header class="sb-anatomy-head"><h4>HULL ANATOMY</h4><div class="mt-seg">${toggle}</div></header>${plate(plan[side])}
    <p class="mt-legend"><i class="mt-mark on"></i> selected <i class="mt-mark fitted"></i> fitted <i class="mt-mark empty"></i> empty <i class="mt-mark utility fitted"></i> utility</p></section>`;
}

const DETAILS = [["mass", "Mass", " t", 2], ["power", "Power draw", " MW", 2], ["integrity", "Integrity", "", 0], ["pgen", "Power capacity", " MW", 1],
  ["eff", "Heat efficiency", "", 2], ["optmass", "Optimal mass", " t", 1], ["maxfuel", "Max fuel per jump", " t", 2], ["jumpboost", "Jump range", " ly", 2],
  ["optmul", "Optimal multiplier", "%", 0], ["damage", "Damage", "", 2], ["range", "Range", " m", 0], ["distdraw", "Distributor draw", " MW", 2],
  ["thermload", "Thermal load", "", 2], ["shieldboost", "Shield boost", "%", 1], ["hullreinforcement", "Hull reinforcement", "", 0],
  ["kinres", "Kinetic resistance", "%", 1], ["thermres", "Thermal resistance", "%", 1], ["explres", "Explosive resistance", "%", 1],
  ["cargo", "Cargo", " t", 0], ["fuel", "Fuel", " t", 0], ["wepcap", "Weapons capacitor", " MJ", 0], ["engcap", "Engines capacitor", " MJ", 0],
  ["syscap", "Systems capacitor", " MJ", 0], ["passengers", "Passengers", "", 0], ["bays", "Bays", "", 0]];

function moduleDetails(slot) {
  const base = moduleOf(slot.module);
  const out = engineered(slot);
  if (!base || !out) return "";
  const percent = (key) => ["optmul", "shieldboost", "kinres", "thermres", "explres"].includes(key);
  const show = (key, value, digits) => percent(key) ? fixed(n(value) * 100, digits) : fixed(value, digits);
  const rows = DETAILS.filter(([key]) => base[key] != null && base[key] !== 0).map(([key, label, unit, digits]) => {
    const changed = Math.abs(n(out[key]) - n(base[key])) > 1e-9;
    return `<tr><td>${label}</td><td class="num mt-dim">${show(key, base[key], digits)}${unit}</td><td class="num${changed ? " ok" : ""}">${changed ? `${show(key, out[key], digits)}${unit}` : ""}</td></tr>`;
  }).join("");
  return rows ? `<h4>MODULE DETAILS</h4><table class="mt-table mt-details"><thead><tr><th></th><th class="num">STOCK</th><th class="num">FITTED</th></tr></thead><tbody>${rows}</tbody></table>` : "";
}

// Fitting the slot picked (5.8.5): what goes in it on the right ({lists}), and its engineering under the
// hull ({engineering}), so the two columns of the workbench come out even.
function fitting() {
  const numbers = slotNumbers();
  if (selected === "armour") {
    const ship = ships.ships[build.ship];
    return {
      lists: `<section class="mt-fit"><header class="mt-fit-head"><h4>FITTING · ARMOUR</h4></header>
        <div class="mt-fit-cols mt-fit-one"><div class="mt-fit-col"><h5>GRADE</h5>${ship.bulkheads.map((b, i) => `<button type="button" class="mt-fit-item${i === build.bulkhead ? " on" : ""}" data-ms-op="bulkhead" data-index="${i}">
          <b>${esc(b.name)}</b><small>${fixed(b.mass || 0)} t · hull +${whole(n(b.hullboost) * 100)}%</small></button>`).join("")}</div></div></section>`,
      engineering: `<section class="sb-engineering"><h4>ENGINEERING · ARMOUR</h4><div class="mt-fit-eng">${armourControls()}
        ${build.armour ? `<span class="mt-tag" title="The figures your ship reported, until you change the armour">GAME FIGURES</span>` : ""}</div></section>`,
    };
  }
  const slot = build.slots[selected];
  if (!slot) return {lists: "", engineering: ""};
  const families = {};
  for (const [id, m] of fits(slot)) (families[groupLabel(m) || m.grp] ||= []).push([id, m]);
  const names = Object.keys(families).sort((a, b) => a.localeCompare(b));
  const current = moduleOf(slot.module);
  const family = category && families[category] ? category : current && families[groupLabel(current)] ? groupLabel(current) : names[0] || "";
  const list = (families[family] || []).sort(([, a], [, b]) => b.class - a.class || String(a.rating).localeCompare(String(b.rating)) || String(a.mount || "").localeCompare(String(b.mount || "")));
  const label = `${esc(slotLabel(slot).toUpperCase())} ${numbers.get(slot)}`;
  // One kind of module only (a core slot): no CATEGORY column, the modules take the width.
  const single = names.length <= 1;
  return {
    lists: `<section class="mt-fit"><header class="mt-fit-head"><h4>FITTING · ${label}</h4>
        ${slot.module ? `<button type="button" class="ghost" data-ms-op="fit" data-module="">REMOVE MODULE</button>` : ""}</header>
      ${slot.unknown && !current ? `<p class="mt-dim mt-unknown">Fitted: ${esc(slot.unknown)} (not in the builder's tables yet)</p>` : ""}
      <div class="mt-fit-cols${single ? " mt-fit-one" : ""}">
        ${single ? "" : `<div class="mt-fit-col"><h5>CATEGORY</h5>${names.map((name) => `<button type="button" class="mt-fit-item${name === family ? " on" : ""}" data-ms-op="category" data-category="${esc(name)}">
          <b>${esc(name.toUpperCase())}</b><small>${families[name].length}</small></button>`).join("")}</div>`}
        <div class="mt-fit-col"><h5>${single ? esc(family.toUpperCase()) || "MODULE" : "MODULE"}</h5>${list.map(([id, m]) => `<button type="button" class="mt-fit-item${id === slot.module ? " on" : ""}" data-ms-op="fit" data-module="${esc(id)}">
          <b>${esc(moduleTitle(m))}</b><small>${m.class}${esc(m.rating || "")} · ${m.cost ? `${whole(m.cost)} cr` : "—"}</small></button>`).join("") || `<p class="mt-dim">Nothing fits here.</p>`}</div>
      </div></section>`,
    engineering: `<section class="sb-engineering"><h4>ENGINEERING · ${label}</h4>${current ? `<div class="mt-fit-eng">${engineeringControls(slot)}</div>${moduleDetails(slot)}`
      : `<p class="mt-dim">Fit a module to engineer it.</p>`}</section>`,
  };
}

// -- the page (5.8.5): a hero for the ship on the bench, then OUTFITTING, SHIPYARD and HANGAR --------------
function hero() {
  const ship = ships.ships[build.ship];
  const s = stats();
  const share = s.power ? s.draw / s.power : 0;
  const owned = build.fleet && (data.fleet || []).find((row) => row.id === build.fleet);
  const kicker = [ship.manufacturer, ship.class ? `${PAD[ship.class]} landing pad` : "", owned ? (owned.now ? "the ship you're flying" : "your ship")
    : build.id ? "saved build" : "new build"].filter(Boolean).join(" · ");
  const readout = (label, value, sub, cls = "") => `<div class="sb-readout ${cls}"><span>${label}</span><b>${value}</b>${sub ? `<small>${sub}</small>` : ""}</div>`;
  return `<header class="sb-hero">
    <div class="sb-hero-art">${art?.[ship.symbol] ? artMask(ship, "illustration", "sb-hero-illustration") : ""}</div>
    <div class="sb-hero-id"><p class="sb-kicker">${esc(kicker.toUpperCase())}</p>
      <h2 class="sb-hull">${esc(ship.name)}</h2>
      <input class="mt-name sb-name" data-ms-name value="${esc(build.name)}" maxlength="40" aria-label="Build name">
      <div class="sb-actions"><button type="button" data-ms-op="save">SAVE</button><button type="button" class="ghost" data-ms-op="save_as">CLONE</button>
        <button type="button" data-ms-op="wish">+ WISHLIST</button>
        ${build.id ? `<button type="button" class="ghost" data-ms-op="share">SHARE CODE</button><button type="button" class="ghost danger" data-ms-op="delete">DELETE</button>` : ""}</div></div>
    <div class="sb-readouts">${readout("JUMP", `${fixed(s.jumpEmpty, 2)}<small> ly</small>`, `${fixed(s.jumpFull, 2)} ly laden`)}
      ${readout("SPEED", `${whole(s.speed)}<small> m/s</small>`, s.canBoost ? `${whole(s.boost)} m/s boost` : "can't boost", s.canBoost ? "" : "warn")}
      ${readout("SHIELDS", `${whole(s.shields)}<small> MJ</small>`)}${readout("ARMOUR", whole(s.armour))}
      ${readout("DPS", fixed(s.dps))}${readout("CARGO", `${whole(s.cargo)}<small> t</small>`)}
      ${readout("MASS", `${whole(s.unladen)}<small> t</small>`, `${whole(s.laden)} t laden`)}
      ${readout("POWER", `${Math.round(share * 100)}<small>%</small>`, `${fixed(s.draw, 1)} / ${fixed(s.power, 1)} MW`, share > 1 ? "warn" : "")}</div>
  </header>`;
}

function modeBar() {
  const count = (data.fleet || []).length + (data.ship_builds || []).length;
  const tab = (key, op, label, extra = "") => `<button type="button" class="sb-mode${mode === key ? " on" : ""}" data-ms-op="${op}"${key === "outfit" && !build ? " disabled" : ""}>${label}${extra}</button>`;
  return `<nav class="sb-modes">${tab("outfit", "pick_close", "OUTFITTING")}${tab("yard", "pick", "SHIPYARD", ` <small>${Object.keys(ships.ships).length}</small>`)}
    ${tab("hangar", "hangar", "HANGAR", count ? ` <small>${count}</small>` : "")}
    <span class="sb-modes-right">${savedList()}${fleetList()}</span></nav>`;
}

// Your ships and your saved builds, each a card with its hull's illustration.
function hangar() {
  const card = (ship, title, lines, op, id, badge = "") => `<article class="sb-bay">
    <div class="sb-bay-art">${ship && art?.[ship.symbol] ? artMask(ship, "illustration", "sb-bay-illustration") : ""}${badge}</div>
    <h3>${esc(title)}</h3><p>${lines.filter(Boolean).map(esc).join(" · ")}</p>
    <button type="button" class="ghost" data-ms-op="${op}" data-id="${esc(id)}">OPEN</button></article>`;
  const hullOf = (symbol) => Object.values(ships.ships).find((ship) => ship.symbol === symbol);
  const fleet = sortedFleet().map((row) => {
    const ship = hullOf(row.ship);
    return card(ship, String(row.name || "").trim() || ship?.name || row.ship, [ship?.name || (data.ship_names || {})[row.ship] || row.ship, row.ident, row.at ? `last flown ${String(row.at).slice(0, 10)}` : ""],
      "open_ship", row.id, row.now ? `<span class="sb-badge">FLYING</span>` : "");
  }).join("");
  const builds = sortedBuilds().map((row) => {
    const ship = ships.ships[row.ship];
    return card(ship, row.name, [ship?.name || row.ship, row.updated ? `saved ${new Date(n(row.updated) * 1000).toISOString().slice(0, 10)}` : ""], "open_saved", row.id);
  }).join("");
  return `<div class="sb-hangar">
    <section><h4>YOUR SHIPS <small>${(data.fleet || []).length}</small></h4>${fleet ? `<div class="sb-bays">${fleet}</div>`
      : `<p class="mt-dim">Your ships appear here as you fly them: each one's latest loadout from your journal.</p>`}</section>
    <section><h4>SAVED BUILDS <small>${(data.ship_builds || []).length}</small></h4>${builds ? `<div class="sb-bays">${builds}</div>`
      : `<p class="mt-dim">Builds you SAVE (and shared codes you import) are kept here, each a file in your profile's ship_builds folder.</p>`}</section></div>`;
}

function strip() {
  const s = stats();
  const cell = (label, value) => `<div><span>${label}</span><b>${value}</b></div>`;
  const share = s.power ? s.draw / s.power : 0;
  return `<div class="mt-strip">${cell("DPS", fixed(s.dps))}${cell("SHIELD", whole(s.shields))}${cell("ARMOUR", whole(s.armour))}${cell("JUMP", fixed(s.jumpEmpty, 1))}
    ${cell("SPEED", whole(s.speed))}${cell("MASS", whole(s.unladen))}<div class="mt-strip-power${share > 1 ? " short" : ""}"><span>POWER</span><b>${Math.round(share * 100)}%</b></div></div>`;
}

// The workbench: the hull with the picked slot's engineering under it, and what goes in the slot beside them.
function workbench() {
  const fit = fitting();
  return `<div class="sb-workbench"><div class="sb-workbench-left">${anatomy()}${fit.engineering}</div>${fit.lists}</div>`;
}

function outfitting() {
  const ship = ships.ships[build.ship];
  if (selectedFor !== build) {
    // A build just opened: the first hardpoint, else the first slot, is the one being fitted.
    selectedFor = build;
    const first = build.slots.findIndex((slot) => slot.group === "hardpoints");
    selected = first >= 0 ? first : 0;
    category = "";
    side = "top";
    }
  return `<div class="mt-outfit">
    <header class="mt-head sb-fitbar">
      <label class="mt-select">ARMOUR <select data-ms-bulkhead>${ship.bulkheads.map((b, i) => `<option value="${i}"${i === build.bulkhead ? " selected" : ""}>${esc(b.name)}</option>`).join("")}</select></label>
      <label class="mt-select">ROLLS <select data-ms-roll>${[0, 25, 50, 75, 100].map((r) => `<option value="${r}"${r === n(build.roll) ? " selected" : ""}>${r}%</option>`).join("")}</select></label></header>
    <div class="mt-outfit-grid">${ledger()}<div class="mt-bench">${workbench()}${analysis()}</div></div></div>`;
}

function draw() {
  if (!host || !host.isConnected) return;
  if (!ships) { load(); host.innerHTML = `<p class="mt-loading">Loading the hulls and modules…</p>`; return; }
  loadArt();
  if (!build && mode === "outfit") {
    const current = data.ship_loadout ? fromLoadout(data.ship_loadout) : null;
    if (current) { build = current; build.fleet = data.ship_loadout.ShipID != null ? String(data.ship_loadout.ShipID) : ""; }
    else mode = "yard";
  }
  host.innerHTML = `<div class="sb-page">${build ? hero() : ""}${modeBar()}${importBar()}
    ${mode === "yard" ? shipyard() : mode === "hangar" ? hangar() : outfitting()}</div>`;
}

export function renderShipBuilder(element, snapshot, reference, deckUi, fresh) {
  host = element;
  ui = deckUi;
  data = snapshot || {};
  ref = reference;
  learnHulls();
  const imported = data.imported_build;
  if (ships && openNewest) {
    const added = (data.ship_builds || []).find((row) => !openNewest.has(row.id));
    if (added) {
      openNewest = null;
      const loaded = fromSaved(added);
      if (loaded) { build = loaded; mode = "outfit"; fresh = true; }
    }
  }
  // Only a build imported while the page is open (not one from an earlier session).
  if (ships && imported?.at && imported.at > importedAt && imported.at > OPENED_AT) {
    importedAt = imported.at;
    const loaded = fromLoadout(imported.loadout);
    if (loaded) { build = loaded; mode = "outfit"; fresh = true; }
  }
  const sig = JSON.stringify([(data.ship_builds || []).map((row) => [row.id, row.name, row.updated]), data.ship_loadout?.timestamp || "", data.options?.roll,
    Object.keys(data.seen_hulls || {}), (data.fleet || []).map((row) => [row.id, row.name, row.ident, row.at, row.now])]);
  if (!fresh && sig === signature) return;
  const focused = document.activeElement;
  if (!fresh && host?.contains(focused) && focused.matches("input, select")) return;
  signature = sig;
  draw();
}

export function handleShipClick(event, deckUi, snapshot, reference) {
  const control = event.target.closest?.("[data-ms-op]");
  if (!control || !host?.contains(control)) return false;
  event.preventDefault();
  ui = deckUi; data = snapshot || data; ref = reference || ref;
  const action = control.dataset.msOp;
  if (action === "pick") { mode = "yard"; yardPick = build ? build.ship : yardPick; }
  else if (action === "hangar") { mode = "hangar"; }
  else if (action === "open_ship") { openShip(control.dataset.id); return true; }
  else if (action === "open_saved") { openSaved(control.dataset.id); }
  else if (action === "yard_pick") { yardPick = control.dataset.ship; }
  else if (action === "yard_size") { yardSize = control.dataset.size; }
  else if (action === "yard_sort") {
    const key = control.dataset.key;
    yardSort = [key, yardSort[0] === key ? -yardSort[1] : key === "name" || key === "maker" ? 1 : -1];
  } else if (action === "select") {
    selected = control.dataset.slot === "armour" ? "armour" : Number(control.dataset.slot);
    category = "";
    // A mount that's only on the other side of the hull turns the view over to show it.
    const plan = art?.[ships.ships[build.ship]?.symbol];
    const jname = build.slots[selected]?.jname;
    const on = (view) => (plan?.[view]?.mounts || []).some((mount) => mount.slot === jname);
    if (jname && plan && !on(side) && on(side === "top" ? "bottom" : "top")) side = side === "top" ? "bottom" : "top";
  } else if (action === "side") { side = control.dataset.side === "bottom" ? "bottom" : "top"; }
  else if (action === "ledger_tab") { ledgerTab = control.dataset.tab; }
  else if (action === "category") { category = control.dataset.category; }
  else if (action === "analysis") { analysisTab = control.dataset.tab; }
  else if (action === "bulkhead") { build.bulkhead = Number(control.dataset.index); build.armour = null; }
  else if (action === "fit") {
    const slot = build.slots[selected];
    if (slot) Object.assign(slot, {module: control.dataset.module || null, bp: "", grade: 0, special: "", roll: null, jmods: null, unknown: "", bpName: "", off: false});
  }
  else if (action === "pick_close") { mode = "outfit"; }
  else if (action === "new") { build = newBuild(control.dataset.ship); mode = "outfit"; }
  else if (action === "power") { const slot = build.slots[Number(control.dataset.slot)]; if (slot) slot.off = !slot.off; }
  else if (action === "current") { const current = fromLoadout(data.ship_loadout); if (current) { build = current; build.fleet = String(data.ship_loadout.ShipID ?? ""); } }
  else if (action === "save" || action === "save_as") {
    if (action === "save_as" || !build.id) build.id = Math.random().toString(16).slice(2, 12);
    op("build_save", {build: plain(build)}).then((ok) => ui.showToast?.(ok ? "Build saved" : "Couldn't save it (60 builds at most)"));
  } else if (action === "delete") {
    if (build.id && window.confirm("Delete this saved build?")) { op("build_delete", {build_id: build.id}); build.id = ""; }
  } else if (action === "share") {
    op("share_build", {id: build.id}).then((ok) => ui.showToast?.(ok ? "Build code copied" : "Save it first"));
  } else if (action === "wish") {
    const items = wishItems();
    if (!items.length) { ui.showToast?.("Pick a blueprint or experimental on a slot first"); return true; }
    op("wish_add", {game: "horizons", items}).then((ok) => ui.showToast?.(ok ? `${items.length} added to the ship wishlist` : "Couldn't add them"));
  }
  draw();
  return true;
}

export function handleShipChange(event, deckUi, snapshot, reference) {
  const target = event.target;
  if (!host?.contains(target)) return false;
  ui = deckUi; data = snapshot || data; ref = reference || ref;
  const d = target.dataset || {};
  // Typing filters as it goes (the input event); its change, fired as the box loses focus, has nothing to add
  // and redrawing then would pull the box out from under its own blur.
  if ("msFilter" in d) {
    if (event.type === "change") return true;
    shipFilter = target.value;
    draw();
    const input = host.querySelector("[data-ms-filter]");
    input?.focus();
    input?.setSelectionRange?.(input.value.length, input.value.length);
    return true;
  }
  if ("msName" in d) { build.name = target.value.slice(0, 40); return true; }
  if ("msCompare" in d) { compareId = target.value; analysisTab = "compare"; draw(); return true; }
  if ("msFleet" in d) { if (target.value) openShip(target.value); return true; }
  if ("msSaved" in d) openSaved(target.value);
  else if ("msBulkhead" in d) { build.bulkhead = Number(target.value); build.armour = null; }
  else if (d.msArmour) {
    // Engineering the armour here: the game's figures give way to the blueprint's.
    const eng = build.armourEng || {bp: "", grade: 0, roll: null, special: ""};
    if (d.msArmour === "bp") {
      eng.bp = target.value;
      eng.grade = eng.bp ? Math.max(0, ...Object.keys(ships.blueprints[eng.bp]?.grades || {}).map(Number)) : 0;
    } else if (d.msArmour === "grade") eng.grade = Number(target.value);
    else if (d.msArmour === "special") eng.special = target.value;
    eng.roll = null;
    build.armourEng = eng.bp || eng.special ? eng : null;
    build.armour = null;
  }
  // ROLLS sets every slot, the ones a loaded ship brought its own rolls for too.
  else if ("msRoll" in d) { build.roll = Number(target.value); build.slots.forEach((slot) => { slot.jmods = null; slot.roll = null; }); }
  else if (d.msSlot) {
    const slot = build.slots[Number(d.slot)];
    if (!slot) return true;
    slot.jmods = null;
    slot.bpName = "";
    if (d.msSlot === "module") slot.unknown = "";
    if (d.msSlot === "module") { slot.module = target.value || null; slot.bp = ""; slot.grade = 0; slot.special = ""; slot.roll = null; slot.off = false; }
    else if (d.msSlot === "roll") slot.roll = target.value === "" ? null : Number(target.value);
    else if (d.msSlot === "bp") {
      slot.bp = target.value;
      const grades = Object.keys(ships.eligible[moduleOf(slot.module)?.grp]?.blueprints?.[slot.bp]?.grades || {}).map(Number);
      slot.grade = slot.bp ? Math.max(0, ...grades) : 0;
    } else if (d.msSlot === "grade") slot.grade = Number(target.value);
    else if (d.msSlot === "special") slot.special = target.value;
  } else return false;
  draw();
  return true;
}

export function handleShipSubmit(event, deckUi) {
  const form = event.target.closest?.("[data-ms-import]");
  if (!form || !host?.contains(form)) return false;
  event.preventDefault();
  ui = deckUi || ui;
  const code = form.querySelector("input")?.value || "";
  if (/^\s*(https?:\/\/)?(www\.)?edsy\.org\/#\/L=/i.test(code)) { ui.showToast?.("That's an EDSY link, which only EDSY can read. In EDSY, open the build's Outfitting page, press Export..., copy the SLEF text and paste that here."); return true; }
  if (/^\s*(VCMAT|VCB[12])-/.test(code)) {
    // A build someone shared: it joins your saved builds and opens.
    const before = new Set((data.ship_builds || []).map((row) => row.id));
    op("import_code", {code: code.trim()}).then((ok) => {
      ui.showToast?.(ok ? "Shared build added to your saved builds" : "That code isn't a ship build");
      if (ok) openNewest = before;
    });
    return true;
  }
  op("build_import", {code}).then((ok) => ui.showToast?.(ok ? "Build imported" : "That isn't a build this page can read: paste SLEF, a journal Loadout, or an EDSY or Coriolis export link"));
  return true;
}
