// The Materials page (5.8.4): on-foot and ship engineering in one place.
// Each side (ON FOOT, SHIP) has five tabs:
//   PLAN     your goals (wishlist items, pins) and the next steps the deck works out
//   HOLD     what you have: the locker, or your materials and cargo
//   RECIPES  what can be made, by item or by engineer
//   BUILD    loadout designs, or the ship builder
//   SOURCES  where things come from: bartender and settlements, or HGEs and traders
// OTHER keeps community goals and permits. Rows stay quiet: picking anything
// opens it in the inspector on the right, where its actions are. One search
// finds anything. The fixed tables come once from /api/data/materials-reference;
// each refresh brings only what you hold, your lists, designs and the plan.


const SIDE_TABS = [["plan", "PLAN"], ["hold", "HOLD"], ["recipes", "RECIPES"], ["build", "BUILD"], ["sources", "SOURCES"]];
const GROUPS = [
  ["odyssey", "ON FOOT", SIDE_TABS],
  // The ship builder is a page of its own (5.8.5).
  ["horizons", "SHIP", SIDE_TABS.filter(([key]) => key !== "build")],
  ["other", "OTHER", [["goals", "COMMUNITY GOALS"], ["permits", "PERMITS"]]],
];
// Tabs with the inspector beside them.
const INSPECTED = new Set(["plan", "hold", "recipes", "sources"]);
const KIND = {item: "Goods", component: "Assets", data: "Data", consumable: "Consumables"};
const PROGRESS = {Known: "Known", Invited: "Invited", Acquainted: "Acquainted", Unlocked: "Unlocked", Barred: "Barred"};

const n = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
const whole = (value) => Math.round(n(value)).toLocaleString("en-GB");
const money = (value) => n(value) >= 1e9 ? `${(n(value) / 1e9).toFixed(2)}B` : n(value) >= 1e6 ? `${(n(value) / 1e6).toFixed(1)}M`
  : n(value) >= 1e4 ? `${Math.round(n(value) / 1e3)}K` : whole(value);
const ly = (value) => value == null ? "" : `${n(value) >= 100 ? whole(value) : n(value).toFixed(1)} ly`;
const fold = (value) => String(value || "").toLowerCase();

let ref = null;
let refState = "idle";
let last = {};
let lastUi = null;
let group = "odyssey";
const sub = {odyssey: "plan", horizons: "plan", other: "goals"};
const recipesBy = {odyssey: "items", horizons: "items"};
let inspect = null;
let globalQuery = "";
const query = {};
let lockerShow = "all";
let lockerKind = "all";
let lockerSort = "name";
let lockerAll = false;
let lockerPick = null;
let engShow = "all";
let equipPick = "tacticalsuit";
let designPick = null;
let draft = null;
let hCategory = "all";
let bpModule = null;
let bpTab = "modules";
let expModule = "";      // RECIPES › EXPERIMENTALS: the module picked
let brokerPick = "";     // RECIPES › TECH BROKER: "broker|what it unlocks"
let synthPick = "";      // RECIPES › SYNTHESIS: the synthesis picked
let addGrade = {from: 0, to: 5};
let codeOpen = false;
// PLAN shows one view at a time; the shopping list can be cut down and grouped.
const planTab = {odyssey: "steps", horizons: "steps"};
let shopShow = "short";
let shopGroup = "kind";
let bound = null;
let optionsApplied = false;

function esc(value) {
  return (lastUi?.escapeHtml || ((text) => String(text ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]))))(value);
}

// The deck answers {accepted}: true when the change was made.
async function op(operation, extra = {}) {
  if (!lastUi) return false;
  try {
    const response = await fetch(lastUi.apiUrl("/api/command"), {
      method: "POST", cache: "no-store", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action: "workspace", page: "materials", operation, ...extra}),
    });
    const reply = await response.json().catch(() => ({}));
    return Boolean(reply.accepted);
  } catch {
    return false;
  }
}

function loadRef(ui) {
  if (refState !== "idle") return;
  refState = "loading";
  fetch(ui.apiUrl("/api/data/materials-reference"), {cache: "no-store"})
    .then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .then((data) => { ref = data; refState = "ready"; renderMaterials(last, ui, true); })
    .catch(() => { refState = "idle"; setTimeout(() => renderMaterials(last, ui, true), 4000); });
}

// -- shared bits ------------------------------------------------------------
const have = (game) => (last.have || {})[game === "odyssey" ? "odyssey" : "horizons"] || {};
const wishes = (game) => (last.wishlists || {})[game] || {};
const summary = (game) => wishes(game).summary || null;
const needOf = (game) => Object.fromEntries((summary(game)?.materials || []).map((row) => [row.symbol, row]));
const here = () => last.here || {};

function distanceTo(info) {
  const coords = here().coords;
  if (!coords || info?.x == null) return null;
  return Math.hypot(coords[0] - info.x, coords[1] - info.y, coords[2] - info.z);
}

// Used by something: what the recipes and engineers say, unless you've said otherwise.
function isUsed(symbol) {
  const mark = (last.relevance || {})[symbol];
  if (mark) return mark === "used";
  return (ref.uses[symbol] || []).some((use) => use.game === "odyssey");
}

function microName(symbol) {
  return ref?.micro?.[symbol]?.name || horizonsInfo(symbol)?.name || String(symbol || "").replace(/_/g, " ");
}

function horizonsInfo(symbol) {
  if (!ref) return null;
  if (!ref._horizonsBy) ref._horizonsBy = Object.fromEntries(ref.horizons.map((row) => [row.symbol, row]));
  return ref._horizonsBy[symbol] || null;
}

function search(key, placeholder) {
  return `<label class="mt-search"><input type="search" data-mt-search="${key}" value="${esc(query[key] || "")}" placeholder="${esc(placeholder)}" autocomplete="off" spellcheck="false"></label>`;
}

const matches = (key, ...texts) => {
  const wanted = fold(query[key]).trim();
  return !wanted || texts.some((text) => fold(text).includes(wanted));
};

function chips(name, current, options) {
  return `<div class="mt-chips" role="group">${options.map(([value, label, count]) =>
    `<button type="button" class="mt-chip${value === current ? " on" : ""}" data-mt-op="chip" data-name="${name}" data-value="${esc(value)}">${esc(label)}${count != null ? ` <b>${esc(count)}</b>` : ""}</button>`).join("")}</div>`;
}

function bar(value, max, cls = "") {
  const share = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  return `<span class="mt-bar ${cls}"><i style="width:${(share * 100).toFixed(1)}%"></i></span>`;
}

function ingredients(list, game, multiplier = 1) {
  const owned = have(game);
  return `<ul class="mt-ingredients">${(list || []).map((row) => {
    const need = row.count * multiplier;
    const got = n(owned[row.symbol]);
    return `<li class="${got >= need ? "ok" : "short"}"><span>${esc(row.name)}</span><b>${whole(got)} / ${whole(need)}</b></li>`;
  }).join("")}</ul>`;
}

function card(title, body, extra = "") {
  return `<section class="mt-card ${extra}"><h3>${title}</h3>${body}</section>`;
}

function empty(text) {
  return `<p class="mt-empty">${esc(text)}</p>`;
}

function engineerState(name) {
  const row = (last.progress || {})[name];
  if (!row) return {label: "Not met", cls: "none", rank: 0};
  const label = PROGRESS[row.progress] || row.progress || "Known";
  return {label, cls: fold(label), rank: n(row.rank)};
}

// -- tabs -------------------------------------------------------------------
function counts() {
  const plan = last.plan || {};
  return {
    "odyssey.plan": (plan.odyssey || []).length,
    "odyssey.hold": Object.values(have("odyssey")).filter((value) => n(value) > 0).length,
    "odyssey.build": (last.loadouts || []).length,
    "horizons.plan": (plan.horizons || []).length,
    "horizons.build": (last.ship_builds || []).length,
    "horizons.sources": (last.hge?.visits || []).length,
    "other.goals": (last.goals || []).filter((goal) => !goal.complete).length,
  };
}

function tabs() {
  const count = counts();
  const top = GROUPS.map(([key, label]) =>
    `<button type="button" class="mt-group${key === group ? " on" : ""}" data-mt-op="group" data-group="${key}">${label}</button>`).join("");
  const views = GROUPS.find(([key]) => key === group)[2];
  const lower = views.map(([key, label]) => {
    const c = count[`${group}.${key}`];
    return `<button type="button" class="mt-tab${key === sub[group] ? " on" : ""}" data-mt-op="view" data-view="${key}">${label}${c ? ` <b>${c}</b>` : ""}</button>`;
  }).join("");
  return `<nav class="mt-groups">${top}<span class="mt-code"><label class="mt-global"><input type="search" data-mt-global value="${esc(globalQuery)}" placeholder="Find anything: a material, blueprint, engineer, suit or weapon" autocomplete="off" spellcheck="false"></label>
</span><div class="mt-global-results" id="mt-global-results">${globalResults()}</div></nav>
    <nav class="mt-tabs">${lower}</nav>`;
}

// An import box where it belongs: PLAN takes wishlists (and pins), ON FOOT › BUILD takes loadout designs.
function codeBar(where) {
  const hint = where === "design" ? "Paste a loadout design's code (VCMAT-...)"
    : group === "horizons" ? "Paste a wishlist or pins code, an EDSY or Coriolis wishlist, an edomh:// link, or SLEF to turn a build's engineering into a wishlist"
      : "Paste a wishlist code (VCMAT-...)";
  return `<form class="mt-codebar" data-mt-form="code"><input name="code" placeholder="${esc(hint)}" autocomplete="off" spellcheck="false">
    <button type="submit">IMPORT</button><button type="button" class="ghost" data-mt-op="code_close">CLOSE</button></form>`;
}

// -- ON FOOT: locker ----------------------------------------------------------
function lockerRows() {
  const owned = have("odyssey");
  const pack = (last.have || {}).backpack || {};
  const need = needOf("odyssey");
  const rows = [];
  for (const [symbol, info] of Object.entries(ref.micro)) {
    const count = n(owned[symbol]);
    if (!lockerAll && count <= 0 && !need[symbol]) continue;
    const used = (ref.uses[symbol] || []).filter((use) => use.game === "odyssey");
    rows.push({symbol, ...info, count, backpack: n(pack[symbol]), need: need[symbol]?.need || 0, used, inUse: isUsed(symbol),
      mark: (last.relevance || {})[symbol] || "", worth: n(info.value) * count});
  }
  return rows;
}

function lockerView() {
  const rows = lockerRows();
  const pass = rows.filter((row) => {
    if (lockerKind !== "all" && row.kind !== lockerKind) return false;
    if (lockerShow === "wanted" && !row.need) return false;
    if (lockerShow === "used" && !row.inUse) return false;
    if (lockerShow === "spare" && (row.inUse || row.count <= 0)) return false;
    if (lockerShow === "backpack" && !row.backpack) return false;
    return matches("locker", row.name, row.symbol);
  });
  const sorters = {name: (a, b) => a.name.localeCompare(b.name), count: (a, b) => b.count - a.count || a.name.localeCompare(b.name),
    worth: (a, b) => b.worth - a.worth || a.name.localeCompare(b.name), need: (a, b) => (b.need - b.count) - (a.need - a.count)};
  pass.sort(sorters[lockerSort] || sorters.name);
  const owned = rows.filter((row) => row.count > 0);
  const total = (kind) => owned.filter((row) => row.kind === kind).reduce((sum, row) => sum + row.count, 0);
  const tiles = [["GOODS", total("item")], ["ASSETS", total("component")], ["DATA", total("data")],
    ["CONSUMABLES", total("consumable")], ["IN BACKPACK", Object.values((last.have || {}).backpack || {}).reduce((a, b) => a + n(b), 0)],
    ["WORTH", `${money(owned.reduce((sum, row) => sum + row.worth, 0))} CR`]];
  const seen = last.locker_seen ? "" : `<p class="mt-note">Nothing from your ship locker yet: it fills in when Elite writes ShipLocker.json (log in on foot or open the locker).</p>`;
  return `${seen}<div class="mt-tiles">${tiles.map(([label, value]) => `<div class="mt-tile"><span>${label}</span><b>${typeof value === "number" ? whole(value) : esc(value)}</b></div>`).join("")}</div>
    <div class="mt-toolbar">${search("locker", "Find an item")}
      ${chips("lockerShow", lockerShow, [["all", "ALL"], ["wanted", "WISHLIST"], ["used", "USED"], ["spare", "NOT USED"], ["backpack", "BACKPACK"]])}
      ${chips("lockerKind", lockerKind, [["all", "ANY KIND"], ["item", "GOODS"], ["component", "ASSETS"], ["data", "DATA"], ["consumable", "CONSUMABLES"]])}
      <label class="mt-select">SORT <select data-mt-change="lockerSort">${[["name", "Name"], ["count", "Count"], ["worth", "Worth"], ["need", "Most short"]].map(([value, label]) => `<option value="${value}"${value === lockerSort ? " selected" : ""}>${label}</option>`).join("")}</select></label>
      <label class="mt-check"><input type="checkbox" data-mt-change="lockerAll"${lockerAll ? " checked" : ""}> Every item</label></div>
    <div class="mt-table-wrap"><table class="mt-table"><thead><tr><th>ITEM</th><th>KIND</th><th class="num">HAVE</th><th class="num">WISHLIST</th><th>USED FOR</th><th class="num">WORTH</th></tr></thead>
    <tbody>${pass.map((row) => `<tr class="${picked("micro", row.symbol) ? "picked" : ""}${row.need && row.count < row.need ? " short" : ""}" data-mt-op="inspect" data-type="micro" data-key="${esc(row.symbol)}" tabindex="0">
      <td>${esc(row.name)}${row.backpack ? ` <small class="mt-tag">PACK ${whole(row.backpack)}</small>` : ""}</td><td>${esc(KIND[row.kind] || row.kind)}</td>
      <td class="num">${whole(row.count)}</td><td class="num">${row.need ? whole(row.need) : ""}</td>
      <td class="mt-uses">${row.mark ? `<small class="mt-tag">${row.mark === "used" ? "MARKED USED" : "MARKED NOT USED"}</small> ` : ""}${row.inUse ? esc(row.used.length === 1 ? row.used[0].label : row.used.length ? `${row.used.length} recipes` : "Kept by you") : `<span class="mt-dim">Not used: sell it</span>`}</td>
      <td class="num">${row.value ? money(row.value) : ""}</td></tr>`).join("") || `<tr><td colspan="6">${empty("Nothing matches.")}</td></tr>`}</tbody></table></div>`;
}

function lockerDetail(row) {
  const used = row.used || [];
  const where = [["Found in", (row.origin || []).join(", ")], ["Buildings", (row.buildings || []).join(", ")],
    ["Containers", (row.containers || []).join(", ")], ["Settlements", (row.settlements || []).join(", ")]].filter(([, value]) => value);
  return inspectorCard(esc(row.name), "ON-FOOT ITEM", `<dl class="mt-facts"><dt>Kind</dt><dd>${esc(KIND[row.kind] || row.kind)}</dd><dt>You have</dt><dd>${whole(row.count)}</dd>
      ${row.value ? `<dt>Worth</dt><dd>${whole(row.value)} CR</dd>` : ""}${row.barter_value ? `<dt>Bartender pays</dt><dd>${whole(row.barter_value)} pts</dd>` : ""}
      ${row.barter_cost ? `<dt>Bartender asks</dt><dd>${whole(row.barter_cost)} pts</dd>` : ""}
      ${where.map(([label, value]) => `<dt>${label}</dt><dd>${esc(value)}</dd>`).join("")}</dl>
    <h4>USED FOR</h4>${used.length ? `<ul class="mt-list">${used.map((use) => `<li>${esc(use.label)}</li>`).join("")}</ul>` : empty("No upgrade, mod or engineer asks for it: safe to sell.")}
    <h4>YOUR CALL</h4><div class="mt-actions">${[["used", "MARK USED"], ["unused", "MARK NOT USED"], ["auto", "AS THE RECIPES SAY"]].map(([value, label]) =>
      `<button type="button" class="${(row.mark || "auto") === value ? "" : "ghost"}" data-mt-op="relevance" data-symbol="${esc(row.symbol)}" data-value="${value}">${label}</button>`).join("")}</div>
    <p class="mt-dim">Marked items count as used (or not) in the filters and at the bartender, whatever the recipes say.</p>`);
}

// -- ON FOOT: engineers -------------------------------------------------------
function odysseyEngineers(onFoot) {
  return Object.values(ref.engineers).filter((row) => Boolean(row.odyssey) === onFoot)
    .map((row) => ({...row, state: engineerState(row.name), distance: distanceTo(row)}))
    .filter((row) => engShow === "all" || (engShow === "pinned" ? (last.pins || []).some((pin) => pin.engineer === row.name)
      : engShow === "unlocked" ? row.state.label === "Unlocked" : row.state.label !== "Unlocked"))
    .filter((row) => matches(onFoot ? "oeng" : "heng", row.name, row.system, ...(row.mods || []), ...Object.keys(row.blueprints || {})))
    .sort((a, b) => (a.distance ?? 1e12) - (b.distance ?? 1e12) || a.name.localeCompare(b.name));
}

function engineersView(onFoot) {
  const rows = odysseyEngineers(onFoot);
  const cards = rows.map((row) => {
    const pins = (last.pins || []).filter((pin) => pin.engineer === row.name);
    const offers = onFoot ? `${(row.mods || []).length} mods` : `${Object.keys(row.blueprints || {}).length} blueprints`;
    return `<article class="mt-eng ${row.state.cls}${picked("engineer", row.name) ? " picked" : ""}" data-mt-op="inspect" data-type="engineer" data-key="${esc(row.name)}" tabindex="0">
      <header><div><h3>${esc(row.name)}</h3><p>${esc(row.system)} · ${esc(row.base)}</p></div>
      <div class="mt-eng-state"><b>${esc(row.state.label)}</b>${row.state.rank ? `<span>Grade ${row.state.rank}</span>` : ""}${row.distance != null ? `<span>${ly(row.distance)}</span>` : ""}</div></header>
      <p class="mt-dim">${offers}${pins.length ? ` · <b class="mt-accent">${pins.length} pinned</b>` : ""}${row.permit ? " · permit" : ""}</p></article>`;
  }).join("");
  return `<div class="mt-toolbar">${search(onFoot ? "oeng" : "heng", onFoot ? "Find an engineer or a mod" : "Find an engineer or a blueprint")}
    ${chips("engShow", engShow, [["all", "ALL"], ["unlocked", "UNLOCKED"], ["locked", "STILL TO UNLOCK"], ...(onFoot ? [] : [["pinned", "WITH PINS", (last.pins || []).length || null]])])}
    ${!onFoot && (last.pins || []).length ? `<button type="button" class="ghost" data-mt-op="share_pins">SHARE PINS</button><button type="button" class="ghost danger" data-mt-op="pin_clear">CLEAR PINS</button>` : ""}
    ${here().coords ? `<span class="mt-dim">Nearest first from ${esc(here().system)}</span>` : ""}</div>
    <div class="mt-eng-grid">${cards || empty("No engineer matches.")}</div>`;
}

// What a pinned blueprint takes from stock to its grade (the usual rolls), against what you hold.
function pinCover(pin) {
  const entry = ref.blueprints[pin.module]?.[pin.name];
  const owned = have("horizons");
  const need = {};
  for (const [grade, recipe] of Object.entries(entry?.grades || {})) {
    if (Number(grade) > pin.grade) continue;
    for (const row of recipe.ingredients) need[row.symbol] = {name: row.name, count: (need[row.symbol]?.count || 0) + row.count * Number(grade)};
  }
  const rows = Object.entries(need).map(([symbol, row]) => ({...row, have: n(owned[symbol])}));
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  const got = rows.reduce((sum, row) => sum + Math.min(row.count, row.have), 0);
  return {share: total ? got / total : 0, short: rows.filter((row) => row.have < row.count)};
}

function pinnedFor(engineer) {
  const pins = (last.pins || []).filter((pin) => pin.engineer === engineer);
  if (!pins.length) return "";
  return `<h4>PINNED</h4><ul class="mt-pins">${pins.map((pin) => {
    const cover = pinCover(pin);
    return `<li class="${cover.short.length ? "short" : "ok"}"><span><b>${esc(pin.module)}: ${esc(pin.name)}</b> <i>G${pin.grade}</i>
      <small>${cover.short.length ? `${Math.round(cover.share * 100)}% · short of ${esc(cover.short.slice(0, 3).map((row) => row.name).join(", "))}${cover.short.length > 3 ? "…" : ""}` : "Everything for it is in the hold"}</small></span>
      ${bar(cover.share, 1, cover.short.length ? "short" : "ok")}
      <button type="button" class="ghost" data-mt-op="wish_add_pin" data-module="${esc(pin.module)}" data-name="${esc(pin.name)}" data-grade="${pin.grade}">+ WISHLIST</button>
      <button type="button" class="ghost danger" data-mt-op="pin_remove" data-id="${esc(pin.id)}" aria-label="Unpin">×</button></li>`;
  }).join("")}</ul>`;
}

function engineerBlueprints(blueprints) {
  const byModule = {};
  for (const [label, grade] of Object.entries(blueprints)) {
    const [module, name] = label.split(": ");
    (byModule[module] ||= []).push([name, grade]);
  }
  return `<div class="mt-eng-bps">${Object.entries(byModule).sort(([a], [b]) => a.localeCompare(b)).map(([module, rows]) =>
    `<div><b>${esc(module)}</b>${rows.sort(([a], [b]) => a.localeCompare(b)).map(([name, grade]) => `<span>${esc(name)} <i>G${grade}</i></span>`).join("")}</div>`).join("")}</div>`;
}

// -- ON FOOT: upgrades and mods ---------------------------------------------------
function equipmentList() {
  return [...Object.values(ref.suits), ...Object.values(ref.weapons)];
}

function upgradeRecipe(model, grade) {
  return ref.upgrades.find((row) => row.kind === model.kind && row.grade === grade && (model.kind === "suit" || row.maker === model.maker));
}

function modsFor(model) {
  const seen = {};
  for (const row of ref.mods) {
    if (row.kind !== model.kind || (model.kind === "weapon" && !["All", model.maker].includes(row.maker))) continue;
    if (!seen[row.fdname] || row.maker === model.maker) seen[row.fdname] = row;
  }
  return Object.values(seen).sort((a, b) => a.name.localeCompare(b.name));
}

function upgradesView() {
  const list = equipmentList();
  const row = (item) => `<tr class="${picked("equip", item.key) ? "picked" : ""}">
      <th class="mt-grid-name" data-mt-op="inspect" data-type="equip" data-key="${esc(item.key)}" tabindex="0"><b>${esc(item.name)}</b><small class="mt-dim mt-sub">${esc(item.kind === "suit" ? "Suit · Remlok" : `${item.maker}${item.class ? ` · ${item.class}` : ""}`)}</small></th>
      ${[2, 3, 4, 5].map((grade) => gradeCell(upgradeRecipe(item, grade)?.ingredients, "odyssey", "upgrade", `${item.key}|${grade}`)).join("")}
      <td class="num mt-dim">${modsFor(item).filter((mod) => makeable(mod.ingredients, "odyssey")).length} / ${modsFor(item).length}</td>
      <td class="mt-grid-act"><button type="button" class="ghost" data-mt-op="wish_add_upgrade" data-key="${esc(item.key)}" data-from="1" data-grade="5" title="G1 to G5 on the wishlist">+ G5</button></td></tr>`;
  const grid = ["suit", "weapon"].map((kind) => `<tr class="mt-grid-group"><td colspan="7">${kind === "suit" ? "SUITS" : "WEAPONS"}</td></tr>${list.filter((item) => item.kind === kind).map(row).join("")}`).join("");
  return `<div class="mt-table-wrap"><table class="mt-table mt-grid"><thead><tr><th>SUIT OR WEAPON</th><th>G2</th><th>G3</th><th>G4</th><th>G5</th><th>MODS READY</th><th></th></tr></thead><tbody>${grid}</tbody></table></div>
    <p class="mt-dim">✓ you can make that upgrade now · ◐ some of it in hand · ✗ none of it. Upgrades are made at any Pioneer Supplies. Pick a name for its mods, or a cell for that grade's materials.</p>`;
}

// -- ON FOOT: loadouts ---------------------------------------------------------
function blankPart(kind) {
  const first = kind === "suit" ? Object.values(ref.suits)[0] : Object.values(ref.weapons)[0];
  return {key: first.key, grade: 1, target: 1, mods: [], want_mods: []};
}

function newDraft() {
  return {id: "", name: "New loadout", suit: blankPart("suit"), weapons: [blankPart("weapon")]};
}

function fromGame(row) {
  const suitKey = ref.suits[row.suit] ? row.suit : Object.keys(ref.suits)[0];
  return {id: "", name: row.name || "Loadout", suit: {key: suitKey, grade: row.grade || 1, target: row.grade || 1, mods: row.suit_mods || [], want_mods: []},
    weapons: Object.values(row.weapons || {}).filter((w) => ref.weapons[w.key]).slice(0, 3)
      .map((w) => ({key: w.key, grade: w.grade || 1, target: w.grade || 1, mods: w.mods || [], want_mods: []}))};
}

function partStats(part, kind, grade) {
  const model = kind === "suit" ? ref.suits[part.key] : ref.weapons[part.key];
  const stats = {...((model?.grades || {})[grade] || {})};
  for (const mod of part.mods || []) {
    for (const [key, factor] of Object.entries(ref.mod_effects[mod] || {})) {
      if (key in stats) stats[key] = kind === "suit" && ["items", "components", "data"].includes(key) ? stats[key] * factor : stats[key] * factor;
    }
  }
  return stats;
}

function statLines(part, kind) {
  const now = partStats(part, kind, part.grade);
  const then = partStats({...part, mods: [...part.mods, ...part.want_mods]}, kind, part.target);
  const rows = kind === "suit"
    ? [["Shield", "shield"], ["Shield regen /s", "shield_regen"], ["Battery", "battery"], ["Oxygen s", "oxygen"], ["Goods", "items"], ["Assets", "components"], ["Data", "data"]]
    : [["Damage", "damage"], ["Shots /s", "rate"], ["Damage /s", "dps"], ["Magazine", "clip"], ["Reserve", "hopper"], ["Range m", "range"], ["Headshot ×", "headshot"]];
  if (kind === "weapon") { now.dps = n(now.damage) * n(now.rate); then.dps = n(then.damage) * n(then.rate); }
  const fmt = (value) => Number.isInteger(n(value)) ? whole(value) : n(value).toFixed(2);
  return `<table class="mt-stats"><thead><tr><th></th><th class="num">G${part.grade}</th><th class="num">G${part.target}${part.want_mods.length ? " + MODS" : ""}</th></tr></thead><tbody>${rows.map(([label, key]) =>
    now[key] == null ? "" : `<tr><td>${label}</td><td class="num">${fmt(now[key])}</td><td class="num${n(then[key]) > n(now[key]) ? " up" : ""}">${fmt(then[key])}</td></tr>`).join("")}</tbody></table>`;
}

function partEditor(part, kind, index) {
  const models = kind === "suit" ? Object.values(ref.suits) : Object.values(ref.weapons);
  const model = (kind === "suit" ? ref.suits : ref.weapons)[part.key];
  const mods = modsFor(model);
  const grade = (field, value) => `<select data-mt-draft="${field}" data-kind="${kind}" data-index="${index}">${[1, 2, 3, 4, 5].map((g) => `<option value="${g}"${g === value ? " selected" : ""}>G${g}</option>`).join("")}</select>`;
  return `<div class="mt-part"><header><select data-mt-draft="key" data-kind="${kind}" data-index="${index}">${models.map((row) => `<option value="${esc(row.key)}"${row.key === part.key ? " selected" : ""}>${esc(row.name)}</option>`).join("")}</select>
      <label>NOW ${grade("grade", part.grade)}</label><label>GOING TO ${grade("target", part.target)}</label>
      ${kind === "weapon" ? `<button type="button" class="ghost" data-mt-op="draft_remove_weapon" data-index="${index}">REMOVE</button>` : ""}</header>
    <div class="mt-mods">${mods.map((mod) => {
      const has = part.mods.includes(mod.fdname), wants = part.want_mods.includes(mod.fdname);
      return `<button type="button" class="mt-mod${has ? " has" : wants ? " wants" : ""}" data-mt-op="draft_mod" data-kind="${kind}" data-index="${index}" data-mod="${esc(mod.fdname)}" title="Click: fitted → wanted → off">${esc(mod.name)}<small>${has ? "FITTED" : wants ? "WANTED" : ""}</small></button>`;
    }).join("")}</div>${statLines(part, kind)}</div>`;
}

function loadoutsView() {
  const designs = last.loadouts || [];
  const game = last.suit_loadouts || [];
  if (!draft) {
    const chosen = designs.find((row) => row.id === designPick);
    draft = chosen ? JSON.parse(JSON.stringify(chosen)) : newDraft();
  }
  const list = `<h4>YOUR DESIGNS</h4>${designs.map((row) => `<button type="button" class="mt-rail-item${row.id === designPick ? " on" : ""}" data-mt-op="design_pick" data-id="${esc(row.id)}"><b>${esc(row.name)}</b><small>${esc(ref.suits[row.suit?.key]?.name || "")} · ${(row.weapons || []).length} weapons</small></button>`).join("") || empty("None saved yet.")}
    <button type="button" class="ghost" data-mt-op="design_new">+ NEW DESIGN</button>
    <button type="button" class="ghost" data-mt-op="code_open" data-where="design">IMPORT A DESIGN</button>${codeOpen === "design" ? codeBar("design") : ""}
    <h4>IN THE GAME</h4>${game.map((row) => `<button type="button" class="mt-rail-item" data-mt-op="design_from_game" data-id="${esc(row.id)}"><b>${esc(row.name || "Loadout")}</b><small>${esc(ref.suits[row.suit]?.name || row.suit || "")} G${esc(row.grade || "")} · copy to a design</small></button>`).join("") || empty("Your suit loadouts appear here once the journal shows them.")}`;
  const editor = `<header class="mt-head"><input class="mt-name" data-mt-draft="name" value="${esc(draft.name)}" maxlength="40" aria-label="Design name">
      <div class="mt-actions"><button type="button" data-mt-op="design_save">SAVE</button>
      ${draft.id ? `<button type="button" data-mt-op="design_wish">+ WISHLIST</button><button type="button" class="ghost" data-mt-op="design_share">SHARE CODE</button><button type="button" class="ghost danger" data-mt-op="design_delete">DELETE</button>` : ""}</div></header>
    <p class="mt-note">Grade "now" and fitted mods are what you have; "going to" and wanted mods are what you're after. Save, then + WISHLIST adds the upgrades and mods it takes.</p>
    <h4>SUIT</h4>${partEditor(draft.suit, "suit", 0)}
    <h4>WEAPONS</h4>${draft.weapons.map((part, index) => partEditor(part, "weapon", index)).join("")}
    ${draft.weapons.length < 3 ? `<button type="button" class="ghost" data-mt-op="draft_add_weapon">+ WEAPON</button>` : ""}`;
  return `<div class="mt-split mt-split-rail"><nav class="mt-rail">${list}</nav><div class="mt-editor">${editor}</div></div>`;
}

// -- PLAN: goals and next steps ----------------------------------------------------------
function ring(share, label, cls = "") {
  const r = 17, c = 2 * Math.PI * r, part = Math.max(0, Math.min(1, share));
  return `<svg class="mt-ring ${cls}" viewBox="0 0 44 44" aria-hidden="true"><circle cx="22" cy="22" r="${r}" class="track"/><circle cx="22" cy="22" r="${r}" class="fill" stroke-dasharray="${(c * part).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 22 22)"/><text x="22" y="26">${esc(label)}</text></svg>`;
}

const STEP_ICON = {engineer: "⚙", trade: "⇄", collect: "◇", bartender: "◈"};

function listBar(game) {
  const index = wishes(game);
  const lists = index.lists || [];
  return `<div class="mt-toolbar mt-listbar"><label class="mt-select">WISHLIST <select data-mt-change="wish_select" data-game="${game}">${lists.map((row) => `<option value="${esc(row.id)}"${row.id === index.selected ? " selected" : ""}>${esc(row.name)} (${row.count})</option>`).join("")}</select></label>
    <button type="button" class="ghost" data-mt-op="wish_new" data-game="${game}">+ NEW</button>
    <button type="button" class="ghost" data-mt-op="wish_rename" data-game="${game}">RENAME</button>
    <button type="button" class="ghost" data-mt-op="wish_share" data-game="${game}">SHARE</button>
    <button type="button" class="ghost" data-mt-op="code_open" data-where="plan">IMPORT</button>
    <button type="button" class="ghost" data-mt-op="wish_clear" data-game="${game}">CLEAR</button>
    <button type="button" class="ghost danger" data-mt-op="wish_delete" data-game="${game}">DELETE</button></div>`;
}

function planView(game) {
  const sum = summary(game);
  const steps = (last.plan || {})[game] || [];
  const pins = game === "horizons" ? (last.pins || []) : [];
  const route = (last.routes || {})[game] || [];
  const items = sum?.items || [];
  const short = (sum?.materials || []).filter((row) => row.missing).length;
  const ready = items.filter((item) => item.ready && item.visible !== false).length;
  const total = sum?.progress ?? 0;
  const head = items.length || pins.length ? `<div class="mt-plan-sum">${ring(total / 100, `${total}%`, sum?.complete ? "ok" : "")}<div>
      <b>${esc(sum?.name || "Wishlist")}</b><span>${items.length} goal${items.length === 1 ? "" : "s"} · <em class="ok">${ready} ready</em> · <em class="${short ? "short" : "ok"}">${short} short</em>${sum?.credits ? ` · ${money(sum.credits)} CR in fees` : ""}</span></div></div>` : "";
  const tabsRow = [["steps", "NEXT STEPS", steps.length], ["goals", "GOALS", items.length + pins.length],
    ["shopping", "SHOPPING LIST", short], ["engineers", "ENGINEERS", route.length]].map(([key, label, count]) =>
    `<button type="button" class="mt-tab${planTab[game] === key ? " on" : ""}" data-mt-op="plan_tab" data-tab="${key}">${label}${count ? ` <b>${count}</b>` : ""}</button>`).join("");
  let body;
  if (!items.length && !pins.length) {
    body = empty(game === "odyssey" ? "No goals yet: add upgrades and mods from RECIPES, or a loadout from BUILD."
      : "No goals yet: add blueprints from RECIPES (or PIN one to an engineer), or engineering from the Ship Builder.");
  } else if (planTab[game] === "goals") body = goalsTable(game, sum, pins);
  else if (planTab[game] === "shopping") body = shoppingList(game, sum);
  else if (planTab[game] === "engineers") body = engineerRoute(game);
  else {
    const rows = steps.map((step, index) => `<li class="mt-step ${esc(step.kind)}${picked("step", String(index)) ? " picked" : ""}" data-mt-op="inspect" data-type="step" data-key="${index}" tabindex="0">
      <i>${STEP_ICON[step.kind] || "•"}</i><span><b>${esc(step.title)}</b><small>${esc(step.items.slice(0, 3).join(" · "))}${step.items.length > 3 ? ` · +${step.items.length - 3}` : ""}</small></span>
      <em>${step.ly != null ? ly(step.ly) : esc(step.detail || "")}</em></li>`).join("");
    body = `${rows ? `<ol class="mt-steps">${rows}</ol>` : empty("Nothing to do but collect: every goal is waiting on materials the deck can't suggest a source for.")}
      <p class="mt-dim">Worked out from what you hold now: a step goes as soon as the journal sees it done.</p>`;
  }
  return `${listBar(game)}${codeOpen === "plan" ? codeBar("plan") : ""}${head}<nav class="mt-tabs mt-plan-tabs">${tabsRow}</nav>${body}`;
}

// The goals as a table: ready to make, then in progress (closest to done first), then left out.
function goalsTable(game, sum, pins) {
  const items = sum?.items || [];
  const nextOf = (item) => {
    if (item.ready) return "Ready to make";
    if (item.type === "blueprint") {
      const grade = n(item.from) + 1;
      const rolls = n((item.rolls || {})[grade] ?? grade) * Math.max(1, n(item.qty) || 1);
      const done = n((item.done || {})[grade]);
      return `G${grade}: ${done ? `${done} of ${rolls} rolled` : `${rolls} roll${rolls === 1 ? "" : "s"}`}`;
    }
    if (item.type === "upgrade") return `Upgrade to G${n(item.from) + 1}`;
    if (item.type === "mod") return item.credits ? `${money(item.credits)} CR fee` : "Mod";
    return item.type === "experimental" ? "Experimental" : "";
  };
  const row = (item) => `<tr class="${item.ready ? "ok" : ""}${picked("goal", item.id) ? " picked" : ""}" data-mt-op="inspect" data-type="goal" data-key="${esc(item.id)}" tabindex="0">
      <td><b>${esc(item.label)}</b>${item.qty > 1 ? ` <small class="mt-dim">×${item.qty}</small>` : ""}</td>
      <td class="mt-goal-bar">${bar(n(item.progress), 100, item.ready ? "ok" : "")}<small>${n(item.progress)}%</small></td>
      <td class="mt-dim">${esc(nextOf(item))}</td></tr>`;
  const sections = [
    ["READY TO MAKE", items.filter((item) => item.ready && item.visible !== false)],
    ["IN PROGRESS", items.filter((item) => !item.ready && item.visible !== false).sort((a, b) => n(b.progress) - n(a.progress))],
    ["LEFT OUT FOR NOW", items.filter((item) => item.visible === false)],
  ].filter(([, rows]) => rows.length);
  const tables = sections.map(([title, rows]) => `<h4>${title} · ${rows.length}</h4><div class="mt-table-wrap"><table class="mt-table mt-goal-table"><tbody>${rows.map(row).join("")}</tbody></table></div>`).join("");
  const pinRows = pins.map((pin) => {
    const cover = pinCover(pin);
    return `<tr class="${cover.short.length ? "" : "ok"}${picked("pin", pin.id) ? " picked" : ""}" data-mt-op="inspect" data-type="pin" data-key="${esc(pin.id)}" tabindex="0">
      <td><b>${esc(pin.module)}: ${esc(pin.name)} G${pin.grade}</b></td><td class="mt-goal-bar">${bar(cover.share, 1, cover.short.length ? "" : "ok")}<small>${Math.round(cover.share * 100)}%</small></td>
      <td class="mt-dim">Pinned to ${esc(pin.engineer)}</td></tr>`;
  }).join("");
  return `${tables}${pinRows ? `<h4>PINNED BLUEPRINTS · ${pins.length}</h4><div class="mt-table-wrap"><table class="mt-table mt-goal-table"><tbody>${pinRows}</tbody></table></div>` : ""}`;
}

// Every material the list needs against what you hold: short ones (or all), by kind or by where to get them.
function shoppingList(game, sum) {
  const type = game === "odyssey" ? "micro" : "material";
  const trades = {};
  for (const trade of sum.trades || []) (trades[trade.for] ||= []).push(trade);
  const usedBy = (symbol) => (sum.items || []).filter((item) => item.visible !== false && (item.need || {})[symbol]).length;
  const source = (row) => {
    if (game === "odyssey") {
      const info = ref.micro[row.symbol] || {};
      const building = (info.buildings || [])[0];
      return building ? ref.buildings[building] || building : (info.origin || [])[0] || "Missions";
    }
    if (trades[row.name]) return "Material trader";
    const info = horizonsInfo(row.symbol);
    if (!info) return row.kind === "commodity" ? "Market" : "Elsewhere";
    if (["guardian", "thargoid"].includes(info.family)) return info.family === "guardian" ? "Guardian sites" : "Thargoid sites";
    if (info.category === "raw") return "Surface and mining";
    if (info.category === "encoded") return "Scanning";
    return n(info.grade) >= 4 ? "High grade emissions" : "Salvage and signals";
  };
  const rows = sum.materials.filter((row) => shopShow === "all" || row.missing);
  const groups = {};
  for (const row of rows) (groups[shopGroup === "source" ? source(row) : (KIND[row.kind] || row.kind)] ||= []).push(row);
  const tables = Object.entries(groups).map(([title, list]) => `<h4>${esc(String(title).toUpperCase())} · ${list.length}</h4><div class="mt-table-wrap"><table class="mt-table mt-shop"><tbody>${list.map((row) =>
    `<tr class="${row.missing ? "short" : "ok"}${picked(type, row.symbol) ? " picked" : ""}"${row.kind === "commodity" ? "" : ` data-mt-op="inspect" data-type="${type}" data-key="${esc(row.symbol)}" tabindex="0"`}>
      <td><b>${esc(row.name)}</b>${row.grade ? ` <small class="mt-dim">G${row.grade}</small>` : ""}</td>
      <td class="mt-goal-bar">${bar(row.have, row.need, row.missing ? "short" : "ok")}<small>${whole(row.have)} / ${whole(row.need)}</small></td>
      <td class="num">${row.missing ? `<b class="short">−${whole(row.missing)}</b>` : "✓"}</td>
      <td class="mt-dim">${esc(trades[row.name] ? trades[row.name].map((t) => `${whole(t.spend)} ${t.from}`).join(", ") : source(row))}</td>
      <td class="num mt-dim">${usedBy(row.symbol)} goal${usedBy(row.symbol) === 1 ? "" : "s"}</td></tr>`).join("")}</tbody></table></div>`).join("");
  return `<div class="mt-toolbar">${chips("shopShow", shopShow, [["short", "SHORT", sum.materials.filter((row) => row.missing).length], ["all", "EVERYTHING", sum.materials.length]])}
      ${chips("shopGroup", shopGroup, [["kind", "BY KIND"], ["source", "BY WHERE TO GET IT"]])}</div>
    ${tables || empty(shopShow === "short" ? "Nothing short: everything on the list is in hand." : "Nothing to collect.")}`;
}

function engineerRoute(game) {
  const route = (last.routes || {})[game] || [];
  const stops = route.map((stop) => `<li data-mt-op="inspect" data-type="engineer" data-key="${esc(stop.engineer)}" tabindex="0"${picked("engineer", stop.engineer) ? ` class="picked"` : ""}>
      <b>${esc(stop.engineer)}</b><span>${esc(stop.system)}${stop.jump_ly != null ? ` · ${ly(stop.jump_ly)}` : ""} · ${esc(engineerState(stop.engineer).label)}</span>
      <small>${esc(stop.items.join(" · "))}</small></li>`).join("");
  return `<h4>ENGINEERS TO SEE</h4>${stops ? `<ol class="mt-route">${stops}</ol>` : empty(game === "odyssey" ? "No mods on the list: grade upgrades are made at any Pioneer Supplies." : "No blueprints on the list need an engineer yet.")}
    <p class="mt-dim">For every goal, ready or not: the fewest stops, each the nearest from the last${game === "odyssey" ? "; grade upgrades are made at any Pioneer Supplies" : ""}.</p>`;
}

// -- HOLD, RECIPES, SOURCES -------------------------------------------------------------
function holdView(game) {
  return game === "odyssey" ? lockerView() : `${materialsView()}<h4>CARGO</h4>${commoditiesView()}`;
}

function recipesView(game) {
  const by = recipesBy[game];
  const switcher = chips(`recipes_${game}`, by, [["items", game === "odyssey" ? "BY SUIT AND WEAPON" : "BY MODULE"], ["engineers", "BY ENGINEER"]]);
  const inner = by === "engineers" ? engineersView(game === "odyssey") : game === "odyssey" ? upgradesView() : blueprintsView();
  return `<div class="mt-toolbar">${switcher}</div>${inner}`;
}

function sourcesView(game) {
  if (game === "odyssey") {
    const short = (summary("odyssey")?.materials || []).filter((row) => row.missing);
    const places = {};
    for (const row of short) {
      const info = ref.micro[row.symbol] || {};
      for (const code of (info.buildings || []).slice(0, 3)) (places[ref.buildings[code] || code] ||= []).push(row);
    }
    const where = Object.entries(places).sort((a, b) => b[1].length - a[1].length).map(([place, rows]) => `<tr><td><b>${esc(place)}</b></td><td>${rows.map((row) =>
      `<span class="mt-link" data-mt-op="inspect" data-type="micro" data-key="${esc(row.symbol)}">${esc(row.name)} ×${whole(row.missing)}</span>`).join(" · ")}</td></tr>`).join("");
    return `${bartenderView()}<h4>WHERE YOUR SHORT ITEMS TURN UP</h4>${where ? `<div class="mt-table-wrap"><table class="mt-table"><tbody>${where}</tbody></table></div>` : empty("Nothing short, or nothing with a known place.")}`;
  }
  const trades = summary("horizons")?.trades || [];
  return `<h4>MATERIAL TRADERS AND BROKERS</h4><div class="mt-toolbar">${nearestButtons(["raw", "manufactured", "encoded", "broker_guardian", "broker_human", "broker"]) || `<span class="mt-dim">Switch on Trading searches (Settings › Integrations) to find the nearest traders and brokers.</span>`}</div>${nearestResults()}
    ${trades.length ? `<div class="mt-table-wrap"><table class="mt-table"><thead><tr><th>SWAP FOR YOUR WISHLIST</th><th class="num">SPEND</th><th class="num">GET</th></tr></thead><tbody>${trades.map((t) => `<tr><td>${esc(t.from)} → ${esc(t.for)}</td><td class="num">${whole(t.spend)}</td><td class="num">${whole(t.covers)}</td></tr>`).join("")}</tbody></table></div>` : ""}
    <h4>HIGH GRADE EMISSIONS</h4>${hgeView()}`;
}

// -- the inspector ----------------------------------------------------------------------
function picked(type, key) {
  return inspect?.type === type && String(inspect.key) === String(key);
}

function inspectorCard(title, kicker, body) {
  return `<header class="mt-insp-head"><div><small>${esc(kicker)}</small><h3>${title}</h3></div><button type="button" class="mt-eye" data-mt-op="inspect_close" aria-label="Close">×</button></header><div class="mt-insp-body">${body}</div>`;
}

function inspectorView(game) {
  if (!inspect) return `<div class="mt-insp-empty"><b>INSPECTOR</b><p>Pick anything (a goal, a step, an item, a blueprint, an engineer) to see all of it here, with what you can do about it.</p></div>`;
  const {type, key} = inspect;
  if (type === "micro" && ref.micro[key]) {
    const owned = n(have("odyssey")[key]);
    const used = (ref.uses[key] || []).filter((use) => use.game === "odyssey");
    return lockerDetail({symbol: key, ...ref.micro[key], count: owned, used, mark: (last.relevance || {})[key] || ""});
  }
  if (type === "material") return materialInspector(key);
  if (type === "blueprint") return blueprintInspector(...String(key).split("|"));
  if (type === "engineer") return engineerInspector(key);
  if (type === "goal") return goalInspector(game, key);
  if (type === "pin") {
    const pin = (last.pins || []).find((row) => row.id === key);
    return pin ? blueprintInspector(pin.module, pin.name) : inspectorGone();
  }
  if (type === "step") return stepInspector(game, Number(key));
  if (type === "grade") return gradeInspector(...String(key).split("|"));
  if (type === "recipe") return recipeInspector(...String(key).split("|"));
  if (type === "upgrade") return upgradeInspector(...String(key).split("|"));
  if (type === "mod") return modInspector(...String(key).split("|"));
  if (type === "equip") return equipInspector(key);
  return inspectorGone();
}

function gradeInspector(module, name, grade) {
  const recipe = ref.blueprints[module]?.[name]?.grades?.[grade];
  if (!recipe) return inspectorGone();
  const times = makeable(recipe.ingredients, "horizons");
  if (recipe.pending) return inspectorCard(`${esc(name)} G${esc(grade)}`, `${module.toUpperCase()} · ONE ROLL`, `
    <p><b>A new blueprint: its materials aren't known yet.</b> They'll show here once the game data has them.</p>
    <h4>WHO MAKES IT</h4><ul class="mt-list">${recipe.engineers.map((engineer) => `<li><span class="mt-link" data-mt-op="inspect" data-type="engineer" data-key="${esc(engineer)}">${esc(engineer)}</span> · ${esc(engineerState(engineer).label)}</li>`).join("")}</ul>`);
  return inspectorCard(`${esc(name)} G${esc(grade)}`, `${module.toUpperCase()} · ONE ROLL`, `
    <p><b>${times ? `You can make ${times} roll${times === 1 ? "" : "s"} now.` : "Not enough in hand for a roll yet."}</b></p>
    ${recipe.coins ? `<p class="mt-dim">A Merc blueprint: each roll also costs ${esc(recipe.coins)} Merc Coin${recipe.coins === 1 ? "" : "s"}.</p>` : ""}
    ${ingredients(recipe.ingredients, "horizons")}
    <h4>WHO MAKES IT</h4><ul class="mt-list">${recipe.engineers.map((engineer) => `<li><span class="mt-link" data-mt-op="inspect" data-type="engineer" data-key="${esc(engineer)}">${esc(engineer)}</span> · ${esc(engineerState(engineer).label)}${distanceTo(ref.engineers[engineer]) != null ? ` · ${ly(distanceTo(ref.engineers[engineer]))}` : ""}</li>`).join("")}</ul>
    <div class="mt-actions mt-insp-actions"><button type="button" data-mt-op="wish_add_bp" data-module="${esc(module)}" data-name="${esc(name)}" data-top="${esc(grade)}" data-from="${n(grade) - 1}">+ G${esc(grade)} TO WISHLIST</button>
      <span class="mt-link" data-mt-op="inspect" data-type="blueprint" data-key="${esc(`${module}|${name}`)}">Every grade</span></div>`);
}

function recipeInspector(type, id, extra) {
  const row = type === "synthesis" ? ref.synthesis.find((r) => r.name === id && r.level === extra)
    : type === "broker" ? ref.broker.find((r) => r.fdname === id && r.name === extra) : ref.experimentals[id];
  if (!row) return inspectorGone();
  const data = type === "broker" ? `data-fdname="${esc(row.fdname)}" data-name="${esc(row.name)}"` : type === "synthesis" ? `data-name="${esc(row.name)}" data-level="${esc(row.level)}"` : `data-fdname="${esc(row.fdname)}"`;
  const kicker = type === "broker" ? `TECH BROKER · ${row.broker} · ${row.module}` : type === "synthesis" ? `SYNTHESIS · ${row.level}` : `EXPERIMENTAL · ${(row.modules || []).join(", ")}`;
  return inspectorCard(esc(row.name), kicker.toUpperCase(), `${ingredients(row.ingredients, "horizons")}
    <div class="mt-actions mt-insp-actions"><button type="button" data-mt-op="wish_add_simple" data-type="${type}" ${data}>+ WISHLIST</button>${type === "broker" ? nearestButtons([brokerKind(row.broker)]) : ""}</div>`);
}

// A suit or weapon: its grade upgrades and every mod, each against what you hold.
function equipInspector(key) {
  const model = ref.suits[key] || ref.weapons[key];
  if (!model) return inspectorGone();
  const owned = have("odyssey");
  const cover = (list) => {
    const need = list.reduce((sum, item) => sum + item.count, 0);
    return need ? list.reduce((sum, item) => sum + Math.min(item.count, n(owned[item.symbol])), 0) / need : 0;
  };
  const upgrades = [2, 3, 4, 5].map((grade) => {
    const recipe = upgradeRecipe(model, grade);
    if (!recipe) return "";
    const share = cover(recipe.ingredients);
    return `<li data-mt-op="inspect" data-type="upgrade" data-key="${esc(`${key}|${grade}`)}" tabindex="0" class="${share >= 1 ? "ok" : ""}">
      <b>G${grade - 1} → G${grade}</b>${bar(share, 1, share >= 1 ? "ok" : "")}<small>${Math.round(share * 100)}%</small></li>`;
  }).join("");
  const mods = modsFor(model).map((mod) => {
    const share = cover(mod.ingredients);
    return `<li data-mt-op="inspect" data-type="mod" data-key="${esc(`${key}|${mod.fdname}`)}" tabindex="0" class="${share >= 1 ? "ok" : ""}">
      <b>${esc(mod.name)}</b>${bar(share, 1, share >= 1 ? "ok" : "")}<small>${Math.round(share * 100)}%</small></li>`;
  }).join("");
  return inspectorCard(esc(model.name), model.kind === "suit" ? "SUIT · REMLOK" : `${model.maker} · ${model.class || ""}`.toUpperCase(), `
    <div class="mt-actions mt-insp-actions"><button type="button" data-mt-op="wish_add_upgrade" data-key="${esc(key)}" data-from="1" data-grade="5">+ G1 → G5 TO WISHLIST</button></div>
    <h4>GRADE UPGRADES · PIONEER SUPPLIES</h4><ul class="mt-cover-list">${upgrades}</ul>
    <h4>MODS · ${modsFor(model).length}</h4><ul class="mt-cover-list">${mods}</ul>
    <p class="mt-dim">Pick one for what it takes, who fits it and + WISHLIST.</p>`);
}

function upgradeInspector(key, grade) {
  const model = ref.suits[key] || ref.weapons[key];
  const recipe = model && upgradeRecipe(model, n(grade));
  if (!recipe) return inspectorGone();
  return inspectorCard(`${esc(model.name)} G${esc(grade)}`, "GRADE UPGRADE · PIONEER SUPPLIES", `${ingredients(recipe.ingredients, "odyssey")}
    <div class="mt-actions mt-insp-actions"><button type="button" data-mt-op="wish_add_upgrade" data-key="${esc(key)}" data-from="${n(grade) - 1}" data-grade="${esc(grade)}">+ G${n(grade) - 1} → G${esc(grade)} TO WISHLIST</button></div>`);
}

function modInspector(key, fdname) {
  const model = ref.suits[key] || ref.weapons[key];
  const mod = model && modsFor(model).find((row) => row.fdname === fdname);
  if (!mod) return inspectorGone();
  return inspectorCard(esc(mod.name), `${model.name.toUpperCase()} MOD · ${money(mod.credits)} CR`, `${ingredients(mod.ingredients, "odyssey")}
    <h4>WHO FITS IT</h4><ul class="mt-list">${mod.engineers.map((engineer) => `<li><span class="mt-link" data-mt-op="inspect" data-type="engineer" data-key="${esc(engineer)}">${esc(engineer)}</span> · ${esc(engineerState(engineer).label)}</li>`).join("")}</ul>
    <div class="mt-actions mt-insp-actions"><button type="button" data-mt-op="wish_add_mod" data-key="${esc(key)}" data-mod="${esc(fdname)}">+ WISHLIST</button></div>`);
}

function inspectorGone() {
  return inspectorCard("Gone", "", `<p class="mt-dim">That's no longer here (made, removed or moved on).</p>`);
}

function materialInspector(symbol) {
  const info = horizonsInfo(symbol);
  if (!info) return inspectorGone();
  const count = n(have("horizons")[symbol]);
  const need = needOf("horizons")[symbol];
  const used = (ref.uses[symbol] || []).filter((use) => use.game === "horizons");
  const family = ref.horizons.filter((row) => row.family === info.family && row.symbol !== symbol).sort((a, b) => a.grade - b.grade);
  const swaps = family.map((row) => {
    const from = n(have("horizons")[row.symbol]);
    const rate = row.grade > info.grade ? `1 → ${3 ** (row.grade - info.grade)}` : `${6 ** (info.grade - row.grade)} → 1`;
    return `<tr><td><span class="mt-link" data-mt-op="inspect" data-type="material" data-key="${esc(row.symbol)}">${esc(row.name)}</span> <small class="mt-dim">G${row.grade}</small></td><td class="num">${whole(from)}</td><td class="num mt-dim">${rate}</td></tr>`;
  }).join("");
  const special = ["guardian", "thargoid", "special"].includes(info.family);
  return inspectorCard(esc(info.name), `${info.category.toUpperCase()} · G${info.grade} · ${info.family.toUpperCase()}`, `
    <div class="mt-insp-figure">${ring(count / info.cap, whole(count))}<div><b>${whole(count)} of ${whole(info.cap)}</b>${need ? `<span class="${need.missing ? "short" : "ok"}">Wishlist needs ${whole(need.need)}${need.missing ? ` · ${whole(need.missing)} short` : " · covered"}</span>` : "<span>Not on your wishlist</span>"}</div></div>
    <h4>HOW TO GET IT</h4><p>${esc(ref.hints[symbol] || "")}</p>
    ${special ? "" : `<h4>AT A TRADER (SAME FAMILY)</h4><table class="mt-table"><thead><tr><th>FROM</th><th class="num">HELD</th><th class="num">RATE</th></tr></thead><tbody>${swaps}</tbody></table>${nearestButtons([info.category])}`}
    <h4>USED IN ${used.length}</h4><ul class="mt-list">${used.slice(0, 14).map((use) => `<li>${esc(use.label)}</li>`).join("")}${used.length > 14 ? `<li class="mt-dim">and ${used.length - 14} more</li>` : ""}</ul>`);
}

function blueprintInspector(module, name) {
  const entry = ref.blueprints[module]?.[name];
  if (!entry) return inspectorGone();
  const top = Math.max(...Object.keys(entry.grades).map(Number));
  const grades = Object.entries(entry.grades).map(([grade, recipe]) => `<div class="mt-recipe"><header><b>G${grade}</b><span class="mt-dim">${esc(recipe.engineers.map((name) => `${name}${engineerState(name).label === "Unlocked" ? " ✓" : ""}`).join(", "))}</span></header>${ingredients(recipe.ingredients, "horizons")}</div>`).join("");
  const specials = Object.values(ref.experimentals).filter((row) => (row.modules || []).includes(module));
  return inspectorCard(esc(name), `${module.toUpperCase()} BLUEPRINT · G1–G${top}`, `
    <div class="mt-actions mt-insp-actions">
      <select data-mt-change="add_from">${[0, 1, 2, 3, 4].map((g) => `<option value="${g}"${g === addGrade.from ? " selected" : ""}>${g ? `from G${g}` : "from stock"}</option>`).join("")}</select>
      <select data-mt-change="add_to">${[1, 2, 3, 4, 5].filter((g) => g <= top).map((g) => `<option value="${g}"${g === Math.min(addGrade.to, top) ? " selected" : ""}>to G${g}</option>`).join("")}</select>
      <button type="button" data-mt-op="wish_add_bp" data-module="${esc(module)}" data-name="${esc(name)}" data-top="${top}">+ WISHLIST</button>
      ${pinSelect(module, name, entry)}</div>
    ${pinChips(module, name)}
    <p class="mt-dim">The wishlist counts the usual rolls: one at G1, two at G2, up to five at G5.</p>
    <div class="mt-recipes mt-recipes-one">${grades}</div>
    ${specials.length ? `<h4>EXPERIMENTALS</h4>${recipeTable(specials, "experimental")}` : ""}`);
}

function engineerInspector(name) {
  const row = ref.engineers[name];
  if (!row) return inspectorGone();
  const state = engineerState(name);
  const distance = distanceTo(row);
  const offers = row.odyssey ? `<ul class="mt-list">${(row.mods || []).map((mod) => `<li>${esc(mod)}</li>`).join("")}</ul>` : engineerBlueprints(row.blueprints || {});
  return inspectorCard(esc(name), `${row.odyssey ? "ON-FOOT" : "SHIP"} ENGINEER · ${state.label.toUpperCase()}${state.rank ? ` · GRADE ${state.rank}` : ""}`, `
    <dl class="mt-facts"><dt>Where</dt><dd>${esc(row.system)} · ${esc(row.base)}${row.body ? ` (${esc(row.body)})` : ""}${distance != null ? ` · ${ly(distance)}` : ""}</dd>
      ${row.discovery ? `<dt>Find</dt><dd>${esc(row.discovery)}</dd>` : ""}${row.meeting ? `<dt>Meet</dt><dd>${esc(row.meeting)}</dd>` : ""}
      ${row.unlock ? `<dt>${row.odyssey ? "Referral" : "Unlock"}</dt><dd>${esc(row.unlock)}</dd>` : ""}${row.reputation ? `<dt>Reputation</dt><dd>${esc(row.reputation)}</dd>` : ""}
      ${row.permit ? `<dt>Permit</dt><dd>Needs a system permit</dd>` : ""}</dl>
    <div class="mt-actions"><button type="button" class="ghost" data-mt-op="copy" data-text="${esc(row.system)}">COPY SYSTEM</button></div>
    ${row.odyssey ? "" : pinnedFor(name)}
    <h4>${row.odyssey ? "MODS" : "BLUEPRINTS"}</h4>${offers}`);
}

function goalInspector(game, id) {
  const item = (summary(game)?.items || []).find((row) => row.id === id);
  if (!item) return inspectorGone();
  const owned = have(game);
  const rows = Object.entries(item.need || {}).map(([symbol, count]) => {
    const got = n(owned[symbol]);
    const kind = game === "odyssey" ? "micro" : "material";
    return `<tr class="${got >= count ? "ok" : "short"}"><td><span class="mt-link" data-mt-op="inspect" data-type="${kind}" data-key="${esc(symbol)}">${esc(microName(symbol))}</span></td><td class="num">${whole(got)} / ${whole(count)}</td><td>${bar(got, count, got >= count ? "ok" : "short")}</td></tr>`;
  }).join("");
  const blueprint = item.type === "blueprint" ? `<div class="mt-actions"><span class="mt-link" data-mt-op="inspect" data-type="blueprint" data-key="${esc(`${item.module}|${item.name}`)}">Open the blueprint</span></div>` : "";
  return inspectorCard(esc(item.label), item.ready ? "GOAL · READY TO MAKE" : `GOAL · ${n(item.progress)}%`, `
    <div class="mt-insp-figure">${ring(n(item.progress) / 100, item.ready ? "✓" : `${n(item.progress)}%`, item.ready ? "ok" : "")}<div><b>${item.ready ? "Everything for it is in hand" : "Still collecting"}</b>
      <span>${Object.entries(item.done || {}).map(([grade, count]) => `G${grade}: ${count} rolled`).join(" · ") || (item.credits ? `${money(item.credits)} CR fee` : "")}</span></div></div>
    ${game === "horizons" && item.type === "blueprint" ? `<h4>GRADES AND HOW MANY</h4>${gradeEditor(item)}` : ""}
    <h4>WHAT IT TAKES</h4>${rows ? `<table class="mt-table"><tbody>${rows}</tbody></table>` : empty("Nothing left to collect.")}${blueprint}
    <div class="mt-actions mt-insp-actions">
      <button type="button" class="ghost" data-mt-op="wish_toggle" data-game="${game}" data-id="${esc(item.id)}">${item.visible === false ? "COUNT IT AGAIN" : "LEAVE IT OUT FOR NOW"}</button>
      <button type="button" data-mt-op="wish_done" data-game="${game}" data-id="${esc(item.id)}">MADE IT</button>
      <button type="button" class="ghost danger" data-mt-op="wish_remove" data-game="${game}" data-id="${esc(item.id)}">REMOVE</button></div>
    <p class="mt-dim">${game === "horizons" ? "Rolls you make at an engineer come off by themselves; MADE IT is for anything the journal can't match." : "Grade upgrades move on by themselves; MADE IT ticks off a mod once it's fitted."}</p>`);
}

function stepInspector(game, index) {
  const step = ((last.plan || {})[game] || [])[index];
  if (!step) return inspectorGone();
  const lookup = step.trader ? nearestButtons([step.trader]) : "";
  return inspectorCard(esc(step.title), `NEXT STEP${step.ly != null ? ` · ${ly(step.ly)}` : ""}`, `
    ${step.detail ? `<p><b>${esc(step.detail)}</b></p>` : ""}${step.why ? `<p class="mt-dim">${esc(step.why)}</p>` : ""}
    <ul class="mt-list">${step.items.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>
    <div class="mt-actions mt-insp-actions">${step.system ? `<button type="button" data-mt-op="copy" data-text="${esc(step.system)}">COPY ${esc(step.system.toUpperCase())}</button>` : ""}
      ${step.engineer ? `<button type="button" class="ghost" data-mt-op="inspect" data-type="engineer" data-key="${esc(step.engineer)}">ABOUT ${esc(step.engineer.toUpperCase())}</button>` : ""}${lookup}</div>
    ${step.trader ? nearestResults() : ""}`);
}

// -- one search across everything ---------------------------------------------------------
function globalResults() {
  const wanted = fold(globalQuery).trim();
  if (!ref || wanted.length < 2) return "";
  const hit = (text) => fold(text).includes(wanted);
  const groups = [
    ["SHIP MATERIALS", ref.horizons.filter((row) => hit(row.name)).slice(0, 6).map((row) => ["material", row.symbol, row.name, `G${row.grade} ${row.category}`, "horizons"])],
    ["ON-FOOT ITEMS", Object.entries(ref.micro).filter(([, row]) => hit(row.name)).slice(0, 6).map(([symbol, row]) => ["micro", symbol, row.name, KIND[row.kind] || row.kind, "odyssey"])],
    ["BLUEPRINTS", Object.entries(ref.blueprints).flatMap(([module, rows]) => Object.keys(rows).filter((name) => hit(name) || hit(module)).map((name) => ["blueprint", `${module}|${name}`, name, module, "horizons"])).slice(0, 8)],
    ["ENGINEERS", Object.values(ref.engineers).filter((row) => hit(row.name) || hit(row.system)).slice(0, 6).map((row) => ["engineer", row.name, row.name, row.system, row.odyssey ? "odyssey" : "horizons"])],
  ].filter(([, rows]) => rows.length);
  if (!groups.length) return `<div class="mt-global-box">${empty("Nothing by that name.")}</div>`;
  return `<div class="mt-global-box">${groups.map(([title, rows]) => `<h4>${title}</h4>${rows.map(([type, key, name, sub, side]) =>
    `<button type="button" class="mt-global-row" data-mt-op="inspect" data-type="${type}" data-key="${esc(key)}" data-side="${side}"><b>${esc(name)}</b><small>${esc(sub)}</small></button>`).join("")}`).join("")}</div>`;
}

function gradeEditor(item) {
  const opts = (value, from) => [0, 1, 2, 3, 4, 5].filter((g) => from ? g < 5 : g > 0).map((g) => `<option value="${g}"${g === value ? " selected" : ""}>${from ? (g ? `from G${g}` : "stock") : `to G${g}`}</option>`).join("");
  return `<span class="mt-grades"><select data-mt-change="wish_from" data-id="${esc(item.id)}">${opts(item.from, true)}</select><select data-mt-change="wish_to" data-id="${esc(item.id)}">${opts(item.grade, false)}</select>
    <select data-mt-change="wish_qty" data-id="${esc(item.id)}">${[1, 2, 3, 4, 5, 6, 8, 10].map((q) => `<option value="${q}"${q === item.qty ? " selected" : ""}>×${q}</option>`).join("")}</select></span>`;
}

// -- ON FOOT: bartender -------------------------------------------------------------
function bartenderView() {
  const owned = have("odyssey");
  const need = needOf("odyssey");
  const sell = [];
  for (const [symbol, count] of Object.entries(owned)) {
    const info = ref.micro[symbol];
    if (!info?.barter_value || n(count) <= 0) continue;
    const used = isUsed(symbol);
    const keep = need[symbol]?.need || 0;
    const spare = Math.max(0, n(count) - keep);
    if (spare <= 0) continue;
    sell.push({symbol, name: info.name, kind: info.kind, spare, used, value: info.barter_value, total: spare * info.barter_value});
  }
  sell.sort((a, b) => Number(a.used) - Number(b.used) || b.total - a.total);
  const buy = (summary("odyssey")?.materials || []).filter((row) => row.missing).map((row) => ({...row, cost: n(ref.micro[row.symbol]?.barter_cost)}));
  const sellable = sell.filter((row) => !row.used).reduce((total, row) => total + row.total, 0);
  const cost = buy.reduce((total, row) => total + row.missing * row.cost, 0);
  return `<div class="mt-tiles"><div class="mt-tile"><span>NOT-USED ITEMS ARE WORTH</span><b>${whole(sellable)} pts</b></div>
      <div class="mt-tile"><span>WISHLIST SHORTFALL COSTS</span><b>${whole(cost)} pts</b></div>
      <div class="mt-tile ${sellable >= cost ? "ok" : "short"}"><span>${sellable >= cost ? "SELLING COVERS IT" : "STILL SHORT"}</span><b>${whole(Math.abs(sellable - cost))} pts</b></div></div>
    <p class="mt-note">Bartenders in station concourses swap goods, assets and data at their own rates (points shown are their usual buy and sell rates; a station's own prices vary with its economy and state). Items your wishlist needs are held back.</p>
    <div class="mt-split mt-split-even">${card("YOU COULD SELL", `<table class="mt-table"><thead><tr><th>ITEM</th><th class="num">SPARE</th><th class="num">EACH</th><th class="num">TOTAL</th></tr></thead><tbody>${sell.map((row) =>
      `<tr class="${row.used ? "mt-muted" : ""}"><td>${esc(row.name)}${row.used ? ` <small class="mt-tag">USED</small>` : ""}</td><td class="num">${whole(row.spare)}</td><td class="num">${whole(row.value)}</td><td class="num">${whole(row.total)}</td></tr>`).join("") || `<tr><td colspan="4">${empty("Nothing spare to sell.")}</td></tr>`}</tbody></table>`)}
    ${card("YOUR WISHLIST STILL NEEDS", `<table class="mt-table"><thead><tr><th>ITEM</th><th class="num">SHORT</th><th class="num">EACH</th><th class="num">TOTAL</th></tr></thead><tbody>${buy.map((row) =>
      `<tr><td>${esc(row.name)}</td><td class="num">${whole(row.missing)}</td><td class="num">${row.cost ? whole(row.cost) : "—"}</td><td class="num">${row.cost ? whole(row.cost * row.missing) : "—"}</td></tr>`).join("") || `<tr><td colspan="4">${empty("Nothing short.")}</td></tr>`}</tbody></table>`)}</div>`;
}

// -- SHIP: materials -------------------------------------------------------------
function materialsView() {
  const owned = have("horizons");
  const need = needOf("horizons");
  const cats = [["raw", "RAW"], ["manufactured", "MANUFACTURED"], ["encoded", "ENCODED"]];
  const shown = cats.filter(([key]) => hCategory === "all" || hCategory === key);
  const blocks = shown.map(([category, label]) => {
    const rows = ref.horizons.filter((row) => row.category === category && matches("hmat", row.name, row.family));
    const families = {};
    for (const row of rows) (families[row.family] ||= []).push(row);
    const total = rows.reduce((sum, row) => sum + n(owned[row.symbol]), 0);
    return `<section class="mt-trader"><header><h3>${label}</h3><span>${whole(total)} held</span>${nearestButtons([category])}</header>
      ${Object.entries(families).map(([family, list]) => `<div class="mt-family"><span class="mt-family-name">${esc(family)}</span>${list.sort((a, b) => n(a.grade) - n(b.grade)).map((row) => {
        const count = n(owned[row.symbol]);
        const wanted = need[row.symbol];
        return `<div class="mt-mat${wanted ? (wanted.missing ? " short" : " ok") : ""}${picked("material", row.symbol) ? " picked" : ""}" data-mt-op="inspect" data-type="material" data-key="${esc(row.symbol)}" tabindex="0" title="${esc(`${row.name}: ${count} of ${row.cap}${wanted ? `, wishlist needs ${wanted.need}` : ""}`)}">
          <b>${esc(row.name)}</b><span>G${row.grade} · ${whole(count)}/${whole(row.cap)}${wanted ? ` · need ${whole(wanted.need)}` : ""}</span>${bar(count, row.cap)}</div>`;
      }).join("")}</div>`).join("")}</section>`;
  }).join("");
  return `<div class="mt-toolbar">${search("hmat", "Find a material")}${chips("hCategory", hCategory, [["all", "ALL"], ["raw", "RAW"], ["manufactured", "MANUFACTURED"], ["encoded", "ENCODED"]])}</div>
    ${nearestResults()}<div class="mt-traders">${blocks}</div>
    <p class="mt-note">Traders swap within a family: one grade down gives 3, one grade up takes 6. Your wishlist's swaps are in its PLAN.</p>`;
}

// A broker unlock's broker: Guardian (and Guardian Weapons) or Human.
const brokerKind = (broker) => /^guardian/i.test(String(broker || "")) ? "broker_guardian" : "broker_human";

function nearestButtons(kinds) {
  if (!last.online) return "";
  const label = {raw: "NEAREST RAW TRADER", manufactured: "NEAREST MANUFACTURED", encoded: "NEAREST ENCODED", broker: "NEAREST BROKER (ANY KIND)",
    broker_guardian: "NEAREST GUARDIAN BROKER", broker_human: "NEAREST HUMAN BROKER"};
  return `<span class="mt-nearest-buttons">${kinds.map((kind) => `<button type="button" class="ghost" data-mt-op="nearest" data-kind="${kind}">${label[kind]}</button>`).join("")}</span>`;
}

function nearestResults() {
  const rows = Object.entries(last.nearest || {});
  if (!rows.length) return "";
  // Spansh doesn't know every broker's kind (colony starports, rescue megaships): those say so.
  const kindOf = (key, station) => station.broker ? ` · <b class="mt-broker-kind">${esc(station.broker)} broker</b>${station.learned
    ? ` <span class="mt-dim" title="Spansh doesn't know; you've unlocked something there">(from your visit)</span>` : ""}`
    : key.startsWith("broker") ? ` · <span class="mt-dim" title="Spansh hasn't been told whether this is a Guardian or Human broker">kind not reported</span>` : "";
  return `<div class="mt-nearest">${rows.map(([key, row]) => `<div><b>${esc(row.label)}</b>${row.waiting ? "<span>Asking Spansh…</span>" : row.error ? `<span>${esc(row.error)}</span>`
    : (row.rows || []).map((station) => `<span><button type="button" class="ghost" data-mt-op="copy" data-text="${esc(station.system)}">${esc(station.system)}</button> ${esc(station.station)}${kindOf(key, station)} · ${ly(station.distance)}${station.large_pad ? " · L" : ""}</span>`).join("") || "<span>None found.</span>"}</div>`).join("")}</div>`;
}

// -- SHIP: high grade emissions ----------------------------------------------------
function hgeView() {
  const hge = last.hge || {};
  const visits = hge.visits || [];
  const states = Object.entries(hge.by_state || {});
  const wanted = hge.wanted || [];
  const top = (tally) => Object.entries(tally).slice(0, 6).map(([name, count]) => `${esc(name)} <b>${whole(count)}</b>`).join(" · ");
  const want = wanted.length ? card("YOUR SHIP WISHLIST WANTS", `<table class="mt-table"><tbody>${wanted.map((row) =>
    `<tr class="short"><td>${esc(row.name)} <small class="mt-dim">G${row.grade}</small></td><td class="num">−${whole(row.missing)}</td><td class="mt-dim">${row.states.length ? `Found in ${esc(row.states.slice(0, 3).join(", "))}` : "Not from your HGEs yet"}</td></tr>`).join("")}</tbody></table>`) : "";
  const allegiance = card("ONLY FROM ONE SIDE", `<ul class="mt-list">${Object.entries(hge.allegiance || {}).map(([side, names]) => `<li><b>${esc(side)}</b> systems: ${esc(names.join(", "))}</li>`).join("")}</ul>
    <p class="mt-dim">The rest come from the faction's state: the table below is what your own HGEs gave in each.</p>`);
  const byState = states.length ? card("WHAT EACH STATE GAVE YOU", `<table class="mt-table"><tbody>${states.map(([name, tally]) => `<tr><td>${esc(name)}</td><td>${top(tally)}</td></tr>`).join("")}</tbody></table>`) : "";
  const systems = (hge.systems || []).map((row) => `<article class="mt-goal"><header><div><h3>${esc(row.system)}</h3><p>${esc(row.allegiance || "")}${row.factions.length ? ` · ${esc(row.factions.join(", "))}` : ""}</p></div>
      <div class="mt-eng-state"><b>${whole(row.visits)} HGE${row.visits === 1 ? "" : "S"}</b><span>${esc(row.last ? new Date(row.last).toLocaleString() : "")}</span></div></header>
      <dl class="mt-facts">${row.states.length ? `<dt>States</dt><dd>${esc(row.states.join(", "))}</dd>` : ""}<dt>Collected</dt><dd>${top(row.collected) || "Nothing picked up"}</dd></dl>
      <footer><button type="button" class="ghost" data-mt-op="copy" data-text="${esc(row.system)}">COPY SYSTEM</button></footer></article>`).join("");
  const recent = visits.length ? card("MOST RECENT", `<table class="mt-table"><tbody>${visits.slice(0, 12).map((visit) => `<tr><td>${esc(new Date(visit.at).toLocaleString())}</td><td>${esc(visit.system)}</td><td>${esc(visit.faction)}${visit.state ? ` <small class="mt-dim">${esc(visit.state)}</small>` : ""}</td>
      <td>${top(Object.fromEntries(Object.values(visit.collected).map((item) => [item.name, item.count]))) || "—"}</td><td><button type="button" class="ghost danger" data-mt-op="hge_forget" data-id="${esc(visit.id)}" aria-label="Forget">×</button></td></tr>`).join("")}</tbody></table>`) : "";
  if (!visits.length) {
    return `${empty("High grade emissions you drop into are kept here: the system, the faction and its state, and what you picked up. Find them with the FSS or in supercruise near systems in Boom, Outbreak, War and other states.")}<div class="mt-split mt-split-even">${allegiance}${want}</div>`;
  }
  return `<div class="mt-split"><div class="mt-goals">${systems}</div><aside class="mt-side">${want}${allegiance}${byState}${recent}</aside></div>`;
}

// -- SHIP: blueprints ------------------------------------------------------------
function blueprintsView() {
  const tabsRow = chips("bpTab", bpTab, [["modules", "MODULES"], ["experimentals", "EXPERIMENTALS"], ["broker", "TECH BROKER"], ["synthesis", "SYNTHESIS"]]);
  if (bpTab === "broker") return brokerView(tabsRow);
  if (bpTab === "synthesis") return synthesisView(tabsRow);
  if (bpTab === "experimentals") return experimentalsView(tabsRow);
  const all = Object.keys(ref.blueprints).filter((module) => module !== "Unknown Type");
  const modules = all.filter((module) => matches("bp", module, ...Object.keys(ref.blueprints[module])));
  if (!bpModule || !ref.blueprints[bpModule]) bpModule = modules[0] || all[0];
  const wanted = new Set((summary("horizons")?.items || []).map((item) => item.module).filter(Boolean));
  const grouped = new Set(MODULE_GROUPS.flatMap(([, names]) => names));
  const groups = [...MODULE_GROUPS, ["OPTIONAL", all.filter((module) => !grouped.has(module)).sort()]];
  const picker = groups.map(([title, names]) => {
    const shown = names.filter((module) => modules.includes(module));
    return shown.length ? `<div class="mt-picker-group"><span>${title}</span><div>${shown.map((module) =>
      `<span class="mt-pick${module === bpModule ? " on" : ""}" role="button" tabindex="0" data-mt-op="bp_module" data-module="${esc(module)}"${wanted.has(module) ? ` title="On your wishlist"` : ""}>${esc(module)}${wanted.has(module) ? "<i></i>" : ""}</span>`).join("")}</div></div>` : "";
  }).join("");
  const onList = new Set((summary("horizons")?.items || []).filter((item) => item.type === "blueprint").map((item) => `${item.module}|${item.name}`));
  const entries = Object.entries(ref.blueprints[bpModule] || {}).sort(([a], [b]) => a.localeCompare(b));
  const rows = entries.map(([name, entry]) => {
    const top = Math.max(...Object.keys(entry.grades).map(Number));
    const key = `${bpModule}|${name}`;
    const pins = (last.pins || []).filter((pin) => pin.module === bpModule && pin.name === name);
    return `<tr${picked("blueprint", key) ? ` class="picked"` : ""}>
      <th class="mt-grid-name" data-mt-op="inspect" data-type="blueprint" data-key="${esc(key)}" tabindex="0"><b>${esc(name)}</b>
        ${onList.has(key) ? `<small class="mt-tag">ON WISHLIST</small>` : ""}${pins.map((pin) => `<small class="mt-tag">PINNED ${esc(pin.engineer.split(" ").slice(-1)[0])}</small>`).join("")}</th>
      ${[1, 2, 3, 4, 5].map((grade) => gradeCell(entry.grades[grade]?.ingredients, "horizons", "grade", `${key}|${grade}`)).join("")}
      <td class="mt-dim mt-grid-eng">${esc(shortNames(entry.grades[top]?.engineers || []))}</td>
      <td class="mt-grid-act"><button type="button" class="ghost" data-mt-op="wish_add_bp" data-module="${esc(bpModule)}" data-name="${esc(name)}" data-top="${top}" title="G1 to G${top} on the wishlist">+ G${top}</button></td></tr>`;
  }).join("");
  const specials = Object.values(ref.experimentals).filter((row) => (row.modules || []).includes(bpModule));
  return `<div class="mt-toolbar">${tabsRow}${search("bp", "Find a module or blueprint")}</div>
    <div class="mt-picker">${picker || empty("No module matches.")}</div>
    <h4>${esc(bpModule.toUpperCase())}</h4>
    <div class="mt-table-wrap"><table class="mt-table mt-grid"><thead><tr><th>BLUEPRINT</th><th>G1</th><th>G2</th><th>G3</th><th>G4</th><th>G5</th><th>TOP GRADE BY</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="mt-dim">✓ you can make it now (✓3: three times) · ◐ some of it in hand · ✗ none of it. Pick a cell for that grade's materials, or a blueprint for all of it, PIN and the grades to add.</p>
    ${specials.length ? `<h4>EXPERIMENTALS FOR ${esc(bpModule.toUpperCase())}</h4>${recipeTable(specials, "experimental")}` : ""}`;
}

// A grouped picker of plain chips (the deck's skins frame every <button>); a dot marks what your wishlist uses.
function pickBlock(groups, name, current, wanted = new Set(), label = (value) => value) {
  return groups.filter(([, values]) => values.length).map(([title, values]) => `<div class="mt-picker-group"><span>${title}</span><div>${values.map((value) =>
    `<span class="mt-pick${value === current ? " on" : ""}" role="button" tabindex="0" data-mt-op="chip" data-name="${name}" data-value="${esc(value)}"${wanted.has(value) ? ` title="On your wishlist"` : ""}>${esc(label(value))}${wanted.has(value) ? "<i></i>" : ""}</span>`).join("")}</div></div>`).join("");
}

function wishlisted(type) {
  return (summary("horizons")?.items || []).filter((item) => item.type === type);
}

// EXPERIMENTALS: pick a module, as for blueprints; the four that suit any weapon are with every weapon.
function experimentalsView(tabsRow) {
  const all = Object.values(ref.experimentals);
  const weapons = new Set(MODULE_GROUPS.find(([title]) => title === "WEAPONS")[1]);
  const forModule = (module) => all.filter((row) => (row.modules || []).includes(module) || (weapons.has(module) && (row.modules || []).includes("Weapon")))
    .sort((a, b) => a.name.localeCompare(b.name));
  const modules = [...new Set(all.flatMap((row) => row.modules || []))].filter((module) => module !== "Weapon");
  const shown = modules.filter((module) => matches("exp", module, ...forModule(module).map((row) => row.name)));
  const listed = new Set(wishlisted("experimental").map((item) => item.fdname));
  const wanted = new Set(modules.filter((module) => forModule(module).some((row) => listed.has(row.fdname))));
  if (!shown.includes(expModule)) expModule = shown.find((module) => wanted.has(module)) || shown[0] || "";
  const grouped = new Set(MODULE_GROUPS.flatMap(([, names]) => names));
  const groups = [...MODULE_GROUPS.map(([title, names]) => [title, names.filter((module) => shown.includes(module))]),
    ["OPTIONAL", shown.filter((module) => !grouped.has(module)).sort()]];
  const rows = expModule ? forModule(expModule).filter((row) => matches("exp", row.name, expModule)) : [];
  return `<div class="mt-toolbar">${tabsRow}${search("exp", "Find a module or experimental")}</div>
    <div class="mt-picker">${pickBlock(groups, "expModule", expModule, wanted) || empty("No experimental matches.")}</div>
    ${expModule ? `<h4>EXPERIMENTALS FOR ${esc(expModule.toUpperCase())} · ${rows.length}</h4>${recipeTable(rows, "experimental")}` : ""}
    ${weapons.has(expModule) ? `<p class="mt-dim">Double Braced, Flow Control, Oversized and Stripped Down suit any weapon.</p>` : ""}`;
}

// TECH BROKER: pick the broker and what it unlocks.
const BROKER_LABEL = {Module: "Modules", "Vanity Type": "Cosmetics", Fighter: "Fighters"};

function brokerView(tabsRow) {
  const keyOf = (row) => `${row.broker}|${row.module}`;
  const rows = ref.broker.filter((row) => matches("broker", row.name, row.module, row.broker));
  const keys = [...new Set(rows.map(keyOf))];
  const listed = new Set(wishlisted("broker").map((item) => item.fdname));
  const wanted = new Set(ref.broker.filter((row) => listed.has(row.fdname)).map(keyOf));
  const label = (key) => { const module = key.split("|")[1]; return BROKER_LABEL[module] || module; };
  const brokers = [...new Set(ref.broker.map((row) => row.broker))];
  const groups = brokers.map((broker) => [broker.toUpperCase(), keys.filter((key) => key.startsWith(`${broker}|`)).sort((a, b) => label(a).localeCompare(label(b)))]);
  const order = groups.flatMap(([, list]) => list);
  if (!keys.includes(brokerPick)) brokerPick = order.find((key) => wanted.has(key)) || order[0] || "";
  const [broker, module] = brokerPick.split("|");
  const picked = rows.filter((row) => keyOf(row) === brokerPick).sort((a, b) => a.name.localeCompare(b.name));
  return `<div class="mt-toolbar">${tabsRow}${search("broker", "Find a broker unlock")}${nearestButtons(["broker_guardian", "broker_human", "broker"])}</div>${nearestResults()}
    <div class="mt-picker">${pickBlock(groups, "brokerPick", brokerPick, wanted, label) || empty("No broker unlock matches.")}</div>
    ${brokerPick ? `<h4>${esc(broker.toUpperCase())} BROKER · ${esc(label(brokerPick).toUpperCase())} · ${picked.length}</h4>${recipeTable(picked, "broker")}` : ""}`;
}

// SYNTHESIS: pick one (ship, ammunition or SRV), then its levels, each against what you hold.
const SYNTH_LEVELS = ["Basic", "Standard", "Premium"];
const SYNTH_GROUPS = [["SHIP", (name) => !/Munitions|^SRV |Mining Rig/.test(name)], ["AMMUNITION", (name) => /Munitions|Mining Rig/.test(name)],
  ["SRV", (name) => /^SRV /.test(name)]];

function synthesisView(tabsRow) {
  const names = [...new Set(ref.synthesis.filter((row) => matches("synth", row.name, row.level)).map((row) => row.name))].sort((a, b) => a.localeCompare(b));
  const wanted = new Set(wishlisted("synthesis").map((item) => item.name));
  if (!names.includes(synthPick)) synthPick = names.find((name) => wanted.has(name)) || (names.includes("FSD") ? "FSD" : names[0]) || "";
  const groups = SYNTH_GROUPS.map(([title, test]) => [title, names.filter(test)]);
  const levels = ref.synthesis.filter((row) => row.name === synthPick).sort((a, b) => SYNTH_LEVELS.indexOf(a.level) - SYNTH_LEVELS.indexOf(b.level));
  return `<div class="mt-toolbar">${tabsRow}${search("synth", "Find a synthesis")}</div>
    <div class="mt-picker">${pickBlock(groups, "synthPick", synthPick, wanted) || empty("No synthesis matches.")}</div>
    ${synthPick ? `<h4>${esc(synthPick.toUpperCase())} · ${levels.length === 1 ? "ONE LEVEL" : `${levels.length} LEVELS`}</h4>${recipeTable(levels, "synthesis")}` : ""}`;
}

const MODULE_GROUPS = [
  ["CORE", ["Armour", "Power Plant", "Thrusters", "Frame Shift Drive", "Life Support", "Power Distributor", "Sensor"]],
  ["WEAPONS", ["Beam Laser", "Burst Laser", "Pulse Laser", "Multi Cannon", "Cannon", "Fragment Cannon", "Plasma Accelerator", "Rail Gun", "Missile Rack", "Seeker Missile Rack", "Torpedo Pylon",
    "Mine Launcher", "AX Missile Rack", "Enzyme Missile Rack", "Mining Laser", "Abrasion Blaster"]],
  ["UTILITY", ["Shield Booster", "Chaff Launcher", "Electronic Countermeasure", "Heat Sink Launcher", "Caustic Sink Launcher", "Point Defence",
    "Kill Warrant Scanner", "Cargo Scanner", "Wake Scanner"]],
];

// How many times a recipe can be made from what you hold (0 when short of anything).
function makeable(list, game) {
  const owned = have(game);
  if (!list?.length) return 0;
  return Math.min(...list.map((row) => Math.floor(n(owned[row.symbol]) / Math.max(1, row.count))));
}

function holdsAny(list, game) {
  const owned = have(game);
  return (list || []).some((row) => n(owned[row.symbol]) > 0);
}

// One cell of a grade grid: ✓n can make n now, ◐ some of it in hand, ✗ none.
function gradeCell(list, game, type, key) {
  if (!list) return `<td class="mt-cell none"></td>`;
  if (!list.length) return `<td class="mt-cell pending${picked(type, key) ? " picked" : ""}" data-mt-op="inspect" data-type="${type}" data-key="${esc(key)}" tabindex="0" title="Its materials aren't known yet">?</td>`;
  const times = makeable(list, game);
  const state = times ? "ok" : holdsAny(list, game) ? "part" : "no";
  return `<td class="mt-cell ${state}${picked(type, key) ? " picked" : ""}" data-mt-op="inspect" data-type="${type}" data-key="${esc(key)}" tabindex="0" title="${times ? `You can make it ${times} time${times === 1 ? "" : "s"} now` : state === "part" ? "Some of it in hand" : "None of it in hand"}">${times ? `✓${times > 1 ? times : ""}` : state === "part" ? "◐" : "✗"}</td>`;
}

function shortNames(names) {
  const list = names.map((name) => `${name.replace(/^(The |Professor |Colonel |Tod '|Lei |Hera )/, (m) => m).split(" ").slice(-1)[0].replace(/'$/, "")}${engineerState(name).label === "Unlocked" ? " ✓" : ""}`);
  return list.length > 3 ? `${list.slice(0, 3).join(" · ")} +${list.length - 3}` : list.join(" · ");
}

function pinSelect(module, name, entry) {
  const best = {};
  for (const [grade, recipe] of Object.entries(entry.grades)) for (const engineer of recipe.engineers) best[engineer] = Math.max(best[engineer] || 0, Number(grade));
  const pinned = new Set((last.pins || []).filter((pin) => pin.module === module && pin.name === name).map((pin) => pin.engineer));
  const options = Object.entries(best).filter(([engineer]) => !pinned.has(engineer)).sort(([a, ga], [b, gb]) => gb - ga || a.localeCompare(b));
  if (!options.length) return "";
  return `<select data-mt-change="pin" data-module="${esc(module)}" data-name="${esc(name)}" aria-label="Pin to an engineer"><option value="">PIN TO…</option>${options.map(([engineer, grade]) =>
    `<option value="${esc(engineer)}">${esc(engineer)} (G${grade}${engineerState(engineer).label === "Unlocked" ? "" : `, ${esc(engineerState(engineer).label.toLowerCase())}`})</option>`).join("")}</select>`;
}

function pinChips(module, name) {
  const pins = (last.pins || []).filter((pin) => pin.module === module && pin.name === name);
  if (!pins.length) return "";
  return `<p class="mt-pinned">PINNED TO ${pins.map((pin) => `<span class="mt-tag">${esc(pin.engineer)} G${pin.grade} <button type="button" class="mt-eye" data-mt-op="pin_remove" data-id="${esc(pin.id)}" aria-label="Unpin">×</button></span>`).join(" ")}</p>`;
}

// A recipe list as quiet rows: what it is, how much of it you hold, + WISHLIST; pick one for its materials.
function recipeTable(rows, type) {
  const owned = have("horizons");
  const body = rows.map((row) => {
    const key = type === "synthesis" ? `${type}|${row.name}|${row.level}` : `${type}|${row.fdname}|${row.name}`;
    const need = row.ingredients.reduce((sum, item) => sum + item.count, 0);
    const got = row.ingredients.reduce((sum, item) => sum + Math.min(item.count, n(owned[item.symbol])), 0);
    const short = row.ingredients.filter((item) => n(owned[item.symbol]) < item.count).map((item) => item.name);
    const sub = type === "broker" ? `${row.broker} · ${row.module}` : type === "synthesis" ? row.level : (row.modules || []).join(", ");
    const data = type === "broker" ? `data-fdname="${esc(row.fdname)}" data-name="${esc(row.name)}"` : type === "synthesis" ? `data-name="${esc(row.name)}" data-level="${esc(row.level)}"` : `data-fdname="${esc(row.fdname)}"`;
    return `<tr class="${short.length ? "" : "ok"}${picked("recipe", key) ? " picked" : ""}" data-mt-op="inspect" data-type="recipe" data-key="${esc(key)}" tabindex="0">
      <td><b>${esc(row.name)}</b><small class="mt-dim mt-sub">${esc(sub)}</small></td>
      <td class="mt-goal-bar">${bar(got, need, short.length ? "" : "ok")}<small>${need ? Math.round(100 * got / need) : 0}%</small></td>
      <td class="mt-dim">${short.length ? `Short of ${esc(short.slice(0, 2).join(", "))}${short.length > 2 ? ` +${short.length - 2}` : ""}` : "All in hand"}</td>
      <td class="mt-grid-act"><button type="button" class="ghost" data-mt-op="wish_add_simple" data-type="${type}" ${data}>+ WISHLIST</button></td></tr>`;
  }).join("");
  return body ? `<div class="mt-table-wrap"><table class="mt-table mt-recipe-table"><tbody>${body}</tbody></table></div>` : empty("Nothing matches.");
}

// -- SHIP: commodities -------------------------------------------------------------
function commoditiesView() {
  const cargo = last.cargo || [];
  const wanted = (summary("horizons")?.materials || []).filter((row) => row.kind === "commodity");
  const carrier = last.carrier;
  const rows = cargo.map((row) => {
    const name = row.name || row.Name_Localised || row.Name || row.commodity || "";
    const count = n(row.count ?? row.Count ?? row.amount);
    return `<tr><td>${esc(name)}</td><td class="num">${whole(count)}</td></tr>`;
  }).join("");
  return `<div class="mt-split mt-split-even">${card(`SHIP CARGO${last.cargo_capacity ? ` · ${whole(last.cargo_capacity)} T HOLD` : ""}`, `<table class="mt-table"><tbody>${rows || `<tr><td>${empty("The hold is empty.")}</td></tr>`}</tbody></table>`)}
    <div>${card("FOR YOUR SHIP WISHLIST", wanted.length ? `<table class="mt-table"><tbody>${wanted.map((row) => `<tr class="${row.missing ? "short" : "ok"}"><td>${esc(row.name)}</td><td class="num">${whole(row.need)} t needed</td></tr>`).join("")}</tbody></table><p class="mt-dim">Tech broker unlocks take these commodities from your hold.</p>` : empty("No commodities on the wishlist."))}
    ${card(`FLEET CARRIER${carrier?.name ? ` · ${esc(carrier.name)}` : ""}`, carrier ? `<table class="mt-table"><tbody>${(carrier.orders || []).map((order) => `<tr><td>${esc(order.commodity || order.name || "")}</td><td>${esc(order.kind || order.type || (order.purchase ? "Buying" : order.sale ? "Selling" : ""))}</td><td class="num">${whole(order.amount ?? order.purchase ?? order.sale ?? 0)}</td><td class="num">${order.price ? `${whole(order.price)} CR` : ""}</td></tr>`).join("") || `<tr><td>${empty("No trade orders.")}</td></tr>`}</tbody></table>${carrier.space_cargo != null ? `<p class="mt-dim">${whole(carrier.space_cargo)} t of cargo aboard.</p>` : ""}` : empty("No carrier of yours seen in the journal."))}</div></div>`;
}

// -- OTHER: community goals -------------------------------------------------------------
function goalChart(goal) {
  const points = (goal.history || []).map(([stamp, total]) => [Date.parse(stamp), n(total)]).filter(([t]) => Number.isFinite(t));
  if (points.length < 2) return `<p class="mt-dim">The chart fills in as the goal's figures move.</p>`;
  const [t0, t1] = [points[0][0], points.at(-1)[0]];
  const max = Math.max(...points.map(([, v]) => v), n(goal.top_tier?.Name ? 0 : 0)) || 1;
  const x = (t) => 8 + (t1 > t0 ? (t - t0) / (t1 - t0) : 1) * 584;
  const y = (v) => 112 - (v / max) * 100;
  const path = points.map(([t, v], i) => `${i ? "L" : "M"}${x(t).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return `<svg class="mt-chart" viewBox="0 0 600 120" role="img" aria-label="Goal total over time"><line x1="8" y1="112" x2="592" y2="112" class="axis"/><path d="${path}" class="line"/><circle cx="${x(points.at(-1)[0]).toFixed(1)}" cy="${y(points.at(-1)[1]).toFixed(1)}" r="3.5" class="dot"/></svg>
    <p class="mt-dim">${whole(points[0][1])} → ${whole(points.at(-1)[1])} since ${new Date(t0).toLocaleDateString()}</p>`;
}

function goalsView() {
  const goals = last.goals || [];
  if (!goals.length) return empty("Community goals appear here once the journal reports one (the game writes them when you're signed up, or open the community goals panel).");
  return `<div class="mt-goals">${goals.map((goal) => {
    const tier = String(goal.tier || "").replace(/\D+/g, "");
    const top = String(goal.top_tier?.Name || "").replace(/\D+/g, "");
    return `<article class="mt-goal${goal.complete ? " done" : ""}"><header><div><h3>${esc(goal.title)}</h3><p>${esc(goal.system)} · ${esc(goal.station)}</p></div>
      <div class="mt-eng-state"><b>${goal.complete ? "Finished" : goal.expiry ? `Ends ${esc(new Date(goal.expiry).toLocaleString())}` : ""}</b><span>Tier ${esc(tier || "0")}${top ? ` of ${esc(top)}` : ""}</span></div></header>
      <div class="mt-tiles"><div class="mt-tile"><span>TOTAL</span><b>${whole(goal.total)}</b></div><div class="mt-tile"><span>YOURS</span><b>${whole(goal.mine)}</b></div>
        <div class="mt-tile"><span>COMMANDERS</span><b>${whole(goal.contributors)}</b></div><div class="mt-tile"><span>YOUR BAND</span><b>Top ${whole(goal.percentile)}%</b></div>
        ${goal.bonus ? `<div class="mt-tile"><span>YOUR REWARD</span><b>${money(goal.bonus)} CR</b></div>` : ""}</div>
      ${tier && top ? `<div class="mt-progress">${bar(n(tier), n(top))}<b>Tier ${tier} / ${top}</b></div>` : ""}
      ${goalChart(goal)}${goal.top_tier?.Bonus ? `<p class="mt-dim">Top tier: ${esc(goal.top_tier.Bonus)}</p>` : ""}
      <footer><button type="button" class="ghost" data-mt-op="copy" data-text="${esc(goal.system)}">COPY SYSTEM</button><button type="button" class="ghost" data-mt-op="goal_forget" data-id="${esc(goal.id)}">FORGET</button></footer></article>`;
  }).join("")}</div>`;
}

// -- OTHER: permits ----------------------------------------------------------------------
function permitsView() {
  const rows = (ref.permits || []).filter((row) => matches("permit", row.name, row.unlock));
  return `<div class="mt-toolbar">${search("permit", "Find a permit system or region")}</div>
    <div class="mt-permits">${rows.map((row) => `<article class="mt-permit"><h3>${esc(row.name)}</h3><p>${esc(row.unlock || "Unknown")}</p>
      <button type="button" class="ghost" data-mt-op="copy" data-text="${esc(row.name)}">COPY</button></article>`).join("") || empty("Nothing matches.")}</div>
    <p class="mt-note">The journal doesn't list the permits you hold, so every permit is shown with how it's earned.</p>`;
}

// -- render -----------------------------------------------------------------------------
function body() {
  const view = sub[group];
  if (group === "other") return {goals: goalsView, permits: permitsView}[view]();
  const game = group;
  let main;
  if (view === "plan") main = planView(game);
  else if (view === "hold") main = holdView(game);
  else if (view === "recipes") main = recipesView(game);
  else if (view === "sources") main = sourcesView(game);
  else main = loadoutsView();
  if (!INSPECTED.has(view)) return main;
  return `<div class="mt-layout${inspect ? " inspecting" : ""}"><div class="mt-main">${main}</div><aside class="mt-inspector">${inspectorView(game)}</aside></div>`;
}

export function renderMaterials(data, ui, force = false) {
  const root = ui.byId("materials-workspace");
  if (!root) return;
  last = data || {};
  lastUi = ui;
  bind(root);
  if (!optionsApplied && last.options) {
    optionsApplied = true;
    lockerSort = last.options.locker_sort || lockerSort;
    if (last.options.hide_unused) lockerShow = "used";
  }
  root.classList.remove("loading-panel");
  if (!ref) {
    loadRef(ui);
    root.innerHTML = `<div class="mt-loading">Reading the engineering tables…</div>`;
    root.dataset.markup = "";
    return;
  }
  const markup = `${tabs()}<div class="mt-body mt-view-${group}-${sub[group]}">${body()}</div>`;
  if (!force && root.dataset.markup === markup) return;
  const focused = document.activeElement;
  if (!force && root.contains(focused) && focused.matches("input, textarea, select")) return;
  root.dataset.markup = markup;
  root.innerHTML = markup;
}

function redraw(keepFocus) {
  if (!lastUi) return;
  const root = lastUi.byId("materials-workspace");
  let caret = null;
  const key = keepFocus?.dataset?.mtSearch;
  if (key) caret = keepFocus.selectionStart;
  renderMaterials(last, lastUi, true);
  if (key) {
    const input = root.querySelector(`[data-mt-search="${key}"]`);
    if (input) { input.focus(); try { input.setSelectionRange(caret, caret); } catch { /* search inputs */ } }
  }
}

export function resetMaterials() {
  optionsApplied = false;
  lockerPick = null;
  inspect = null;
  designPick = null;
  draft = null;
  const root = document.getElementById("materials-workspace");
  if (root) root.dataset.markup = "";
}

// -- events -------------------------------------------------------------------------------
function bind(root) {
  if (bound === root) return;
  bound = root;
  root.addEventListener("click", onClick);
  root.addEventListener("input", onInput);
  root.addEventListener("change", onChange);
  root.addEventListener("submit", onSubmit);
}

function wishAdd(game, items) {
  return op("wish_add", {game, items}).then((ok) => {
    lastUi?.showToast?.(ok ? "Added to the wishlist" : "Couldn't add that");
  });
}

function draftPart(kind, index) {
  return kind === "suit" ? draft.suit : draft.weapons[Number(index)];
}

function onClick(event) {
  const control = event.target.closest("[data-mt-op]");
  if (!control || control.disabled) return;
  event.preventDefault();
  const d = control.dataset;
  const name = d.mtOp;
  const game = d.game || (group === "horizons" ? "horizons" : "odyssey");
  switch (name) {
    case "group": group = d.group; inspect = null; break;
    case "view": sub[group] = d.view; break;
    case "inspect":
      if (d.side && d.side !== group) { group = d.side; if (!INSPECTED.has(sub[group])) sub[group] = "plan"; }
      inspect = picked(d.type, d.key) && !d.side ? null : {type: d.type, key: d.key};
      if (d.side) { globalQuery = ""; }
      if (d.type === "equip") equipPick = d.key;
      if (d.type === "blueprint") bpModule = String(d.key).split("|")[0];
      break;
    case "inspect_close": inspect = null; break;
    case "plan_tab": planTab[group] = d.tab; break;
    case "chip": {
      const set = {lockerShow: (v) => { lockerShow = v; }, lockerKind: (v) => { lockerKind = v; }, engShow: (v) => { engShow = v; },
        hCategory: (v) => { hCategory = v; }, bpTab: (v) => { bpTab = v; },
        recipes_odyssey: (v) => { recipesBy.odyssey = v; }, recipes_horizons: (v) => { recipesBy.horizons = v; },
        shopShow: (v) => { shopShow = v; }, shopGroup: (v) => { shopGroup = v; },
        expModule: (v) => { expModule = v; }, brokerPick: (v) => { brokerPick = v; }, synthPick: (v) => { synthPick = v; }};
      set[d.name]?.(d.value);
      break;
    }
    case "code_open": codeOpen = codeOpen === d.where ? false : d.where; break;
    case "code_close": codeOpen = false; break;
    case "locker_pick": lockerPick = lockerPick === d.symbol ? null : d.symbol; break;
    case "equip": equipPick = d.key; break;
    case "bp_module": bpModule = d.module; break;
    case "copy": op("copy_text", {text: d.text, label: "system"}); return;
    case "nearest": op("nearest", {kind: d.kind}); return;
    case "goal_forget": op("goal_forget", {goal_id: d.id}); return;
    case "hge_forget": op("hge_forget", {visit_id: d.id}); return;
    case "relevance": op("relevance_set", {symbol: d.symbol, value: d.value}); return;
    case "pin_remove": op("pin_remove", {pin_id: d.id}); return;
    case "pin_clear":
      if (window.confirm("Take every pin off?")) op("pin_clear");
      return;
    case "share_pins": op("share_pins").then((ok) => lastUi?.showToast?.(ok ? "Pins code copied" : "No pins to share")); return;
    case "wish_add_pin": wishAdd("horizons", [{type: "blueprint", module: d.module, name: d.name, from: 0, grade: Number(d.grade)}]); return;
    case "wish_add_upgrade": wishAdd("odyssey", [{type: "upgrade", target: d.key, from: Number(d.from), grade: Number(d.grade)}]); return;
    case "wish_add_mod": wishAdd("odyssey", [{type: "mod", target: d.key, mod: d.mod}]); return;
    case "wish_add_bp": {
      // A single grade (its inspector), stock to top (the grid's + G5), or the blueprint's own choosers.
      let from, to;
      if (d.from != null) { from = Number(d.from); to = Number(d.top) || 5; }
      else if (control.closest(".mt-grid")) { from = 0; to = Number(d.top) || 5; }
      else { from = addGrade.from; to = Math.min(Number(d.top) || 5, Math.max(addGrade.from + 1, addGrade.to)); }
      wishAdd("horizons", [{type: "blueprint", module: d.module, name: d.name, from, grade: Math.max(from + 1, to)}]);
      return;
    }
    case "wish_add_simple": wishAdd("horizons", [{type: d.type, fdname: d.fdname, name: d.name, level: d.level}]); return;
    case "wish_new": {
      const label = window.prompt("Name the new wishlist", "");
      if (label !== null) op("wish_new", {game, name: label});
      return;
    }
    case "wish_rename": {
      const label = window.prompt("Rename this wishlist", summary(game)?.name || "");
      if (label) op("wish_rename", {game, name: label});
      return;
    }
    case "wish_delete":
      if (window.confirm("Delete this wishlist?")) op("wish_delete", {game});
      return;
    case "wish_clear":
      if (window.confirm("Take everything off this wishlist?")) op("wish_clear", {game});
      return;
    case "wish_share": op("wish_share", {game}).then((ok) => lastUi?.showToast?.(ok ? "Wishlist code copied" : "Couldn't copy it")); return;
    case "wish_toggle": case "wish_remove": case "wish_done": op(name, {game, item_id: d.id}); return;
    case "design_pick": designPick = d.id; draft = null; break;
    case "design_new": designPick = null; draft = newDraft(); break;
    case "design_from_game": {
      const row = (last.suit_loadouts || []).find((item) => String(item.id) === d.id);
      if (row) { designPick = null; draft = fromGame(row); }
      break;
    }
    case "draft_add_weapon": if (draft.weapons.length < 3) draft.weapons.push(blankPart("weapon")); break;
    case "draft_remove_weapon": draft.weapons.splice(Number(d.index), 1); break;
    case "draft_mod": {
      const part = draftPart(d.kind, d.index);
      const mod = d.mod;
      if (part.mods.includes(mod)) { part.mods = part.mods.filter((m) => m !== mod); part.want_mods.push(mod); }
      else if (part.want_mods.includes(mod)) part.want_mods = part.want_mods.filter((m) => m !== mod);
      else if (part.mods.length + part.want_mods.length < 4) part.mods.push(mod);
      break;
    }
    case "design_save": {
      if (!draft.id) draft.id = Math.random().toString(16).slice(2, 12);
      designPick = draft.id;
      op("design_save", {design: draft}).then((ok) => lastUi?.showToast?.(ok ? "Design saved" : "Couldn't save it (40 designs at most)"));
      break;
    }
    case "design_delete":
      if (draft?.id && window.confirm("Delete this design?")) { op("design_delete", {design_id: draft.id}); designPick = null; draft = null; }
      break;
    case "design_wish": op("wish_from_design", {design_id: draft.id}).then((ok) => lastUi?.showToast?.(ok ? "Added to the on-foot wishlist" : "Nothing to add: set a higher grade or wanted mods, then save")); return;
    case "design_share": op("share_design", {id: draft.id}).then((ok) => lastUi?.showToast?.(ok ? "Design code copied" : "Save it first")); return;
    default: return;
  }
  redraw();
  // Picked from far down a long list: bring the inspector into view (in a narrow window it sits above the list).
  if (name === "inspect" && inspect) {
    const panel = lastUi?.byId("materials-workspace")?.querySelector(".mt-inspector");
    const box = panel?.getBoundingClientRect();
    if (box && (box.bottom < 60 || box.top > window.innerHeight - 60)) panel.scrollIntoView({block: "nearest"});
  }
}

function onInput(event) {
  const ds = event.target.dataset || {};
  if ("mtGlobal" in ds) {
    // Only the results redraw, so the box keeps its focus.
    globalQuery = event.target.value;
    const box = lastUi?.byId("mt-global-results");
    if (box) box.innerHTML = globalResults();
    return;
  }
  const key = ds.mtSearch;
  if (key) { query[key] = event.target.value; redraw(event.target); return; }
  if (event.target.dataset?.mtDraft === "name" && draft) draft.name = event.target.value.slice(0, 40);
}

function onChange(event) {
  const target = event.target;
  const d = target.dataset || {};
  if ("mtGlobal" in d) return;
  if (d.mtDraft && draft) {
    const part = d.mtDraft === "name" ? null : draftPart(d.kind, d.index);
    if (d.mtDraft === "key") { Object.assign(part, {key: target.value, mods: [], want_mods: []}); }
    else if (d.mtDraft === "grade") { part.grade = Number(target.value); part.target = Math.max(part.target, part.grade); }
    else if (d.mtDraft === "target") { part.target = Math.max(part.grade, Number(target.value)); }
    redraw();
    return;
  }
  switch (d.mtChange) {
    case "lockerSort": lockerSort = target.value; break;
    case "lockerAll": lockerAll = target.checked; break;
    case "add_from": addGrade.from = Number(target.value); addGrade.to = Math.max(addGrade.to, addGrade.from + 1); break;
    case "add_to": addGrade.to = Number(target.value); break;
    case "wish_select": op("wish_select", {game: d.game, list_id: target.value}); return;
    case "pin":
      if (target.value) op("pin_add", {module: d.module, name: d.name, engineer: target.value}).then((ok) => lastUi?.showToast?.(ok ? `Pinned to ${target.value}` : "Couldn't pin it"));
      return;
    case "wish_from": case "wish_to": case "wish_qty": {
      const field = {wish_from: "from", wish_to: "grade", wish_qty: "qty"}[d.mtChange];
      op("wish_edit", {game: "horizons", item_id: d.id, item: {[field]: Number(target.value)}});
      return;
    }
    default: return;
  }
  redraw();
}

function onSubmit(event) {
  const form = event.target.closest("[data-mt-form='code']");
  if (!form) return;
  event.preventDefault();
  const code = form.querySelector("input")?.value || "";
  if (/^\s*(https?:\/\/)?(www\.)?edsy\.org\/#\/L=/i.test(code)) { lastUi?.showToast?.("That's an EDSY link, which only EDSY can read. In EDSY, open the build's Outfitting page, press Export..., copy the SLEF text and paste that here."); return; }
  op("import_code", {code}).then((ok) => {
    lastUi?.showToast?.(ok ? "Imported" : "That isn't a code this page knows");
    if (ok) { codeOpen = false; redraw(); }
  });
}
