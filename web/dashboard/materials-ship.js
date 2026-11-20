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
let picking = false;
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
      for (const [id, module] of Object.entries(ships.modules)) if (module.symbol) ships.bySymbol[module.symbol] = id;
      for (const [symbol, id] of Object.entries(ships.aliases || {})) ships.bySymbol[symbol] ??= id;
      learnHulls();
      shipsState = "ready";
      draw();
    })
    .catch(() => { shipsState = "idle"; host && (host.innerHTML = `<p class="mt-empty">The ship tables didn't load. Trying again shortly…</p>`); setTimeout(draw, 4000); });
}

export function shipBuilderReset() {
  build = null;
  picking = false;
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
  const hardpoints = rows.map((row) => String(row.Slot || "").match(/^(Tiny|Small|Medium|Large|Huge)Hardpoint(\d+)$/)).filter(Boolean)
    .map((m) => ({class: SIZE_OF[m[1]], jname: m[0], n: Number(m[2])})).sort((a, b) => b.class - a.class || a.n - b.n);
  const internal = rows.filter((row) => /^(Slot\d+_Size\d+|Military\d+|Cargo\d+|PlanetaryApproachSuite)$/.test(String(row.Slot || "")))
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

// Slots that hold a module with mass (not paint, decals, the cockpit or the cargo hatch).
const FITTED_SLOT = /^(PowerPlant|MainEngines|FrameShiftDrive|LifeSupport|PowerDistributor|Radar|FuelTank|(Tiny|Small|Medium|Large|Huge)Hardpoint\d+|Slot\d+_Size\d+|Military\d+|Cargo\d+|Passenger\d+)$/;

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
  return {id: row.id, name: row.name, ship: row.ship, bulkhead: row.bulkhead, roll: row.roll,
    ...(ships.ships[row.ship]?.described ? {hull: ships.ships[row.ship]} : {}),
    slots: row.slots.map((slot) => ({module: slot.module, bp: slot.bp, grade: slot.grade, special: slot.special,
      ...(slot.roll != null ? {roll: slot.roll} : {}), ...(slot.jmods ? {jmods: slot.jmods} : {}),
      ...(slot.unknown ? {unknown: slot.unknown} : {}), ...(slot.bpName ? {bpName: slot.bpName, bpGrade: n(slot.bpGrade)} : {})}))};
}

function fromSaved(saved) {
  if (!knownHull(saved.ship, saved.hull)) return null;
  // A build saved while its hull was new to the tables moves onto the real hull, slot by slot name.
  const symbol = String(saved.ship || "").startsWith("described:") ? String(saved.ship).slice(10) : "";
  const known = symbol && Object.keys(ships.ships).find((key) => !ships.ships[key].described && ships.ships[key].symbol === symbol);
  const was = newBuild(saved.ship);
  const fresh = newBuild(known || saved.ship);
  const target = (index) => {
    if (!known) return fresh.slots[index];
    const old = was.slots[index];
    if (!old) return null;
    if (old.group === "standard") return fresh.slots.find((slot) => slot.group === "standard" && slot.index === old.index);
    return old.jname ? fresh.slots.find((slot) => slot.jname === old.jname) : null;
  };
  fresh.id = saved.id;
  fresh.name = saved.name;
  fresh.bulkhead = n(saved.bulkhead);
  fresh.roll = saved.roll == null ? 100 : n(saved.roll);
  (saved.slots || []).forEach((slot, index) => {
    const into = target(index);
    if (into) Object.assign(into, {module: slot.module || null, bp: slot.bp || "", grade: n(slot.grade), special: slot.special || "",
      roll: slot.roll == null ? null : n(slot.roll), jmods: slot.jmods || null, unknown: slot.unknown || "", bpName: slot.bpName || "",
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
  fresh.name = loadout.ShipName || ships.ships[key].name;
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
    slot.bp = ""; slot.bpName = ""; slot.bpGrade = 0; slot.grade = 0; slot.special = ""; slot.roll = null; slot.jmods = null;
    if (slot.module) engineer(slot, row);
  };
  fresh.slots.filter((slot) => slot.group === "standard").forEach((slot) => put(slot, bySlot[STANDARD_SLOTS[slot.index]]));
  const counters = {};
  fresh.slots.filter((slot) => slot.group === "hardpoints" || slot.group === "utility").forEach((slot) => {
    const size = HARDPOINT_SIZES[slot.size];
    counters[size] = (counters[size] || 0) + 1;
    put(slot, bySlot[slot.jname || `${size}Hardpoint${counters[size]}`]);
  });
  const internal = Object.keys(bySlot).filter((name) => /^Slot\d+_Size\d+$/.test(name)).sort();
  const military = Object.keys(bySlot).filter((name) => /^Military\d+$/.test(name)).sort();
  fresh.slots.filter((slot) => slot.group === "internal").forEach((slot) => {
    if (slot.jname) put(slot, bySlot[slot.jname]);
    else if (/approach/i.test(slot.name || "")) put(slot, bySlot.PlanetaryApproachSuite);
    else if (/military/i.test(slot.name || "")) put(slot, bySlot[military.shift()]);
    else put(slot, bySlot[internal.shift()]);
  });
  const armour = String(bySlot.Armour?.Item || "").toLowerCase();
  const grade = BULKHEAD_GRADES.findIndex((g) => armour.includes(`_${g}`));
  fresh.bulkhead = grade >= 0 ? grade : 0;
  return fresh;
}

// -- maths ---------------------------------------------------------------------------
function applyChange(out, key, value) {
  const method = ships.modifications[key]?.method || "multiplicative";
  if (method === "overwrite") out[key] = value;
  else if (!(key in out)) return;
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
    return out;
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
  const bulkhead = ship.bulkheads[b.bulkhead] || ship.bulkheads[0] || {};
  const fitted = b.slots.map((slot) => ({slot, m: engineered(slot, b)})).filter((row) => row.m);
  const sum = (key, filter = () => true) => fitted.filter(filter).reduce((total, row) => total + n(row.m[key]), 0);
  const moduleMass = sum("mass");
  const fuel = sum("fuel");
  const cargo = sum("cargo");
  const unladen = n(ship.hullMass) + n(bulkhead.mass) + moduleMass;
  const laden = unladen + fuel + cargo;
  const fsd = fitted.find((row) => row.slot.group === "standard" && row.slot.index === 2)?.m;
  const boost = sum("jumpboost");
  const jump = (mass, fuelUse) => fsd && fsd.optmass ? n(fsd.optmass) / mass * Math.pow(Math.min(n(fsd.maxfuel), fuelUse) / n(fsd.fuelmul), 1 / n(fsd.fuelpower)) + boost : 0;
  const thrusters = fitted.find((row) => row.slot.group === "standard" && row.slot.index === 1)?.m;
  const speedMul = thrusters ? curve(unladen + fuel, thrusters) : 1;
  const shield = fitted.find((row) => ["sg", "bsg", "psg"].includes(row.m.grp))?.m;
  const boosters = sum("shieldboost", (row) => row.m.grp === "sb");
  const shields = shield ? n(ship.baseShieldStrength) * curve(n(ship.hullMass), shield) * (1 + boosters) + sum("shieldaddition") : 0;
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
  const cost = n(ship.hullCost) + n(bulkhead.cost) + sum("cost");
  const hullParts = [bulkhead, ...fitted.filter((row) => ["hr", "mahr", "ghrp"].includes(row.m.grp)).map((row) => row.m)];
  const shieldParts = shield ? [shield, ...fitted.filter((row) => row.m.grp === "sb").map((row) => row.m)] : [];
  const res = (parts) => Object.fromEntries(["kinres", "thermres", "explres", "causres"].map((key) => [key, stack(parts.map((part) => part[key]))]));
  const weaponsHeat = fitted.filter((row) => row.slot.group === "hardpoints").reduce((total, row) => {
    const m = row.m;
    if (!m.thermload) return total;
    return total + (m.grp === "bl" ? n(m.thermload) : n(m.thermload) * (m.fireint ? 1 / n(m.fireint) : n(m.rof) || 1));
  }, 0);
  return {unladen, laden, fuel, cargo, jumpEmpty: jump(unladen + n(fsd?.maxfuel), n(fsd?.maxfuel)), jumpFull: jump(laden, n(fsd?.maxfuel)),
    speed: n(ship.speed) * speedMul, boost: n(ship.boost) * speedMul, shields, armour, power: n(plant?.pgen), draw, dps, cost,
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
  return items;
}

// -- drawing ---------------------------------------------------------------------------
function slotLabel(slot) {
  if (slot.group === "standard") return STANDARD_LABELS[slot.index];
  if (slot.group === "utility") return "Utility";
  if (slot.group === "hardpoints") return `${HARDPOINT_SIZES[slot.size]} hardpoint`;
  return slot.name ? `${slot.name.replace(/([a-z])([A-Z])/g, "$1 $2")} ${slot.size}` : `Internal ${slot.size}`;
}

function options(slot) {
  const fits = Object.entries(ships.modules).filter(([, m]) => {
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
  const groups = {};
  for (const [id, m] of fits) (groups[ships.groups[m.grp]?.label || m.grp] ||= []).push([id, m]);
  const label = (m) => `${m.class}${m.rating || ""} ${m.name || ""}${m.mount ? ` (${{F: "fixed", G: "gimballed", T: "turret"}[m.mount] || m.mount})` : ""}`;
  return `<option value="">— empty —</option>${Object.entries(groups).sort(([a], [b]) => a.localeCompare(b)).map(([group, rows]) =>
    `<optgroup label="${esc(group)}">${rows.sort(([, a], [, b]) => b.class - a.class || String(a.rating).localeCompare(String(b.rating))).map(([id, m]) =>
      `<option value="${esc(id)}"${id === slot.module ? " selected" : ""}>${esc(label(m))}</option>`).join("")}</optgroup>`).join("")}`;
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

function slotRows(group, title) {
  const rows = build.slots.filter((slot) => slot.group === group);
  if (!rows.length) return "";
  return `<h4>${title}</h4><table class="mt-table mt-slots"><tbody>${rows.map((slot) => {
    const m = engineered(slot);
    const index = build.slots.indexOf(slot);
    return `<tr><td class="mt-slot-name">${esc(slotLabel(slot))}<small>${slot.size ? `size ${slot.size}` : ""}</small></td>
      <td><select data-ms-slot="module" data-slot="${index}">${options(slot)}</select>${slot.unknown ? `<small class="mt-dim mt-unknown">Fitted: ${esc(slot.unknown)} (not in the builder's tables yet)</small>` : ""}</td>
      <td class="mt-slot-eng">${engineeringControls(slot)}</td>
      <td class="num mt-dim">${m ? `${fixed(m.mass || 0)} t · ${fixed(m.power || 0, 2)} MW` : ""}</td></tr>`;
  }).join("")}</tbody></table>`;
}

function statsPanel() {
  const s = stats();
  const ship = ships.ships[build.ship];
  const tiles = [["UNLADEN", `${fixed(s.unladen)} t`], ["LADEN", `${fixed(s.laden)} t`], ["JUMP (EMPTY)", `${fixed(s.jumpEmpty, 2)} ly`],
    ["JUMP (FULL)", `${fixed(s.jumpFull, 2)} ly`], ["SPEED", `${whole(s.speed)} m/s`], ["BOOST", `${whole(s.boost)} m/s`],
    ["SHIELDS", `${whole(s.shields)} MJ`], ["ARMOUR", whole(s.armour)], ["CARGO", `${whole(s.cargo)} t`], ["FUEL", `${whole(s.fuel)} t`],
    ["RAW DPS", fixed(s.dps)], ["COST", `${money(s.cost)} CR`]];
  const powerShare = s.power ? s.draw / s.power : 0;
  const pct = (value) => `${(n(value) * 100).toFixed(1)}%`;
  const resRow = (label, res) => `<tr><td>${label}</td>${["kinres", "thermres", "explres", "causres"].map((key) => `<td class="num${n(res[key]) < 0 ? " short" : ""}">${pct(res[key])}</td>`).join("")}</tr>`;
  const other = compareId ? (data.ship_builds || []).find((row) => row.id === compareId) : null;
  const versus = other ? fromSaved(other) : null;
  const cmp = versus ? stats(versus) : null;
  const diffRows = cmp ? [["Jump (empty)", "jumpEmpty", 2, " ly"], ["Jump (full)", "jumpFull", 2, " ly"], ["Speed", "speed", 0, " m/s"], ["Boost", "boost", 0, " m/s"],
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
  return `<div class="mt-tiles mt-ship-tiles">${tiles.map(([label, value]) => `<div class="mt-tile"><span>${label}</span><b>${esc(value)}</b></div>`).join("")}</div>
    <div class="mt-power ${powerShare > 1 ? "short" : "ok"}"><span>POWER ${fixed(s.draw, 2)} / ${fixed(s.power, 2)} MW</span><span class="mt-bar"><i style="width:${Math.min(100, powerShare * 100).toFixed(1)}%"></i></span>
      ${powerShare > 1 ? "<b>Over the plant's output: some modules will shut down</b>" : ""}</div>
    ${ship.described && !ship.hullMass ? `<p class="mt-note">The ${esc(ship.name)} isn't in the builder's tables yet: its slots and modules come from your build, but its own figures (mass, speed, shields, armour) aren't known, so jump range, speed and defences here leave the hull out.</p>` : ""}
    ${ship.described && ship.hullMass && ship.learned ? `<p class="mt-note">The ${esc(ship.name)} isn't in the builder's tables yet, so it was learned from your journal: its slots from your Loadout, and its mass (${fixed(ship.hullMass)} t, with the armour you fly) from the ship's unladen mass less its modules. Jump range and mass are right; speed, shields and armour aren't known yet, so those leave the hull out.</p>` : ""}
    <p class="mt-dim">${esc(ship.manufacturer || "")} · class ${esc(ship.class || "")} landing pad · mass lock ${esc(ship.masslock || "")} · rolls at ${whole(build.roll)}%. Figures are worked out here and can differ a little from the game's; slots marked GAME FIGURES use what your ship reported.</p>
    ${resistances}${heat}${compare}`;
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

function picker() {
  const wanted = shipFilter.toLowerCase();
  const rows = Object.entries(ships.ships).filter(([, ship]) => !wanted || `${ship.name} ${ship.manufacturer}`.toLowerCase().includes(wanted))
    .sort(([, a], [, b]) => a.name.localeCompare(b.name));
  return `<div class="mt-toolbar"><label class="mt-search"><input type="search" data-ms-filter value="${esc(shipFilter)}" placeholder="Find a hull" autocomplete="off"></label>
    ${build ? `<button type="button" class="ghost" data-ms-op="pick_close">BACK TO THE BUILD</button>` : ""}</div>${importBar()}
    <div class="mt-hulls">${rows.map(([key, ship]) => `<button type="button" class="mt-hull" data-ms-op="new" data-ship="${esc(key)}"><b>${esc(ship.name)}</b>
      <small>${ship.learned ? "New · learned from your journal" : `${esc(ship.manufacturer || "")} · ${["", "S", "M", "L"][ship.class] || ""} pad · ${money(ship.cost)} CR`}</small></button>`).join("")}</div>`;
}

function savedList() {
  const builds = data.ship_builds || [];
  return `<select data-ms-saved><option value="">${builds.length ? "Saved builds…" : "No saved builds"}</option>${builds.map((row) =>
    `<option value="${esc(row.id)}"${row.id === build?.id ? " selected" : ""}>${esc(row.name)} · ${esc(ships.ships[row.ship]?.name || row.ship)}</option>`).join("")}</select>`;
}

function draw() {
  if (!host || !host.isConnected) return;
  if (!ships) { load(); host.innerHTML = `<p class="mt-loading">Loading the hulls and modules…</p>`; return; }
  if (!build && !picking) {
    const current = data.ship_loadout ? fromLoadout(data.ship_loadout) : null;
    if (current) build = current;
    else picking = true;
  }
  if (picking) { host.innerHTML = picker(); return; }
  const ship = ships.ships[build.ship];
  host.innerHTML = `<div class="mt-toolbar mt-ship-bar">${savedList()}
      <input class="mt-name" data-ms-name value="${esc(build.name)}" maxlength="40" aria-label="Build name">
      <button type="button" data-ms-op="save">SAVE</button><button type="button" class="ghost" data-ms-op="save_as">CLONE</button>
      <button type="button" data-ms-op="wish">+ WISHLIST</button>
      ${build.id ? `<button type="button" class="ghost" data-ms-op="share">SHARE CODE</button><button type="button" class="ghost danger" data-ms-op="delete">DELETE</button>` : ""}
      <button type="button" class="ghost" data-ms-op="pick">NEW HULL</button>
      ${data.ship_loadout ? `<button type="button" class="ghost" data-ms-op="current">YOUR SHIP NOW</button>` : ""}</div>
    ${importBar()}
    <div class="mt-split mt-ship-split"><div><header class="mt-head"><h3>${esc(ship.name)}</h3>
      <label class="mt-select">ARMOUR <select data-ms-bulkhead>${ship.bulkheads.map((b, i) => `<option value="${i}"${i === build.bulkhead ? " selected" : ""}>${esc(b.name)}</option>`).join("")}</select></label>
      <label class="mt-select">ROLLS <select data-ms-roll>${[0, 25, 50, 75, 100].map((r) => `<option value="${r}"${r === n(build.roll) ? " selected" : ""}>${r}%</option>`).join("")}</select></label></header>
      ${slotRows("standard", "CORE")}${slotRows("hardpoints", "HARDPOINTS")}${slotRows("utility", "UTILITY")}${slotRows("internal", "OPTIONAL INTERNAL")}</div>
      <aside class="mt-side">${statsPanel()}${materialsPanel()}</aside></div>`;
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
      if (loaded) { build = loaded; picking = false; fresh = true; }
    }
  }
  // Only a build imported while the page is open (not one from an earlier session).
  if (ships && imported?.at && imported.at > importedAt && imported.at > OPENED_AT) {
    importedAt = imported.at;
    const loaded = fromLoadout(imported.loadout);
    if (loaded) { build = loaded; picking = false; fresh = true; }
  }
  const sig = JSON.stringify([(data.ship_builds || []).map((row) => [row.id, row.name, row.updated]), data.ship_loadout?.timestamp || "", data.options?.roll,
    Object.keys(data.seen_hulls || {})]);
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
  if (action === "pick") { picking = true; }
  else if (action === "pick_close") { picking = false; }
  else if (action === "new") { build = newBuild(control.dataset.ship); picking = false; }
  else if (action === "current") { const current = fromLoadout(data.ship_loadout); if (current) build = current; }
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
  if ("msFilter" in d) { shipFilter = target.value; draw(); const input = host.querySelector("[data-ms-filter]"); input?.focus(); return true; }
  if ("msName" in d) { build.name = target.value.slice(0, 40); return true; }
  if ("msCompare" in d) { compareId = target.value; draw(); return true; }
  if ("msSaved" in d) {
    const saved = (data.ship_builds || []).find((row) => row.id === target.value);
    const loaded = saved ? fromSaved(saved) : null;
    if (loaded) build = loaded;
    // Saved on a hull that was new then and is in the tables now: keep it on the real hull, so it
    // stays there and its share code no longer has to describe the hull.
    if (loaded && String(saved.ship).startsWith("described:") && loaded.ship !== saved.ship) op("build_save", {build: plain(loaded)});
  } else if ("msBulkhead" in d) build.bulkhead = Number(target.value);
  else if ("msRoll" in d) { build.roll = Number(target.value); build.slots.forEach((slot) => { slot.jmods = null; }); }
  else if (d.msSlot) {
    const slot = build.slots[Number(d.slot)];
    if (!slot) return true;
    slot.jmods = null;
    slot.bpName = "";
    if (d.msSlot === "module") slot.unknown = "";
    if (d.msSlot === "module") { slot.module = target.value || null; slot.bp = ""; slot.grade = 0; slot.special = ""; slot.roll = null; }
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
