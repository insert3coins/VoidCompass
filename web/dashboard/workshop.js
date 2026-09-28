/* Ship Workshop: the Build Planner and Engineering pages.

   Build Planner: a hangar of builds; the bay, where the hull, the build's
   identity, its power distributor and its headline readouts share one
   panel; the loadout board with every slot on the ship; the module dock that
   fits and engineers the chosen slot; and the performance panels. Every
   number is the planner's own calculation (build_planner.calculate).

   Engineering: the fleet, what the journal says is engineered on the chosen
   ship, the plans sent from the Build Planner, the material locker, the
   engineers, a blueprint reference, sources, Tech Brokers and Odyssey.

   View state (the chosen slot, tabs, filters, searches) stays in the page;
   only data-ws-op buttons and the few commands below reach the backend. */

const GROUPS = {
  hardpoint: "HARDPOINTS", utility: "UTILITY MOUNTS", component: "CORE INTERNALS",
  military: "MILITARY", internal: "OPTIONAL INTERNALS", ship: "SHIP SYSTEMS",
};
// The board reads like the in-game outfitting screen: weapons and utilities,
// then the core, then the optional internals.
const BOARD_ORDER = ["hardpoint", "utility", "component", "ship", "internal", "military"];
const AXES = ["sys", "eng", "wep"];
const HARDPOINT_SIZES = {1: "Small", 2: "Medium", 3: "Large", 4: "Huge"};
const DAMAGE = [["absolute", "ABS"], ["thermal", "THM"], ["kinetic", "KIN"], ["explosive", "EXP"], ["antiXeno", "AX"], ["caustic", "CAU"]];
const RESISTS = [["kinres", "KIN"], ["thmres", "THM"], ["expres", "EXP"], ["caures", "CAU"]];
const HEAT = [["idle", "IDLE"], ["thrust", "FULL THRUST"], ["fsdCharge", "FSD CHARGE"], ["weaponsFiring", "WEAPONS FIRING"], ["shieldCell", "SHIELD CELL"]];
const ENGINEERING_TABS = [
  ["ship", "SHIP"], ["plans", "PLANS"], ["materials", "MATERIALS"], ["engineers", "ENGINEERS"],
  ["blueprints", "BLUEPRINTS"], ["sources", "SOURCES"], ["brokers", "TECH BROKERS"], ["odyssey", "ODYSSEY"],
];
const MATERIAL_FILTERS = [["all", "ALL"], ["needed", "NEEDED"], ["missing", "MISSING"], ["full", "FULL"], ["empty", "EMPTY"]];
const MATERIAL_ORDER = ["Raw", "Manufactured", "Encoded"];
const STATUS_ORDER = ["unlocked", "invited", "known", "unknown"];
// Cosmetic and fixed journal slots: never engineered, never worth a row.
const COSMETIC_SLOT = /^(VesselVoice|ShipCockpit|CargoHatch|PlanetaryApproachSuite|PaintJob|Decal\d|ShipName\d|ShipID\d|ShipKitSpoiler|ShipKitWings|ShipKitTail|ShipKitBumper|WeaponColour|EngineColour|StringLights|Bobble\d+|DataLinkScanner|CodexScanner|DiscoveryScanner)$/i;

const view = {
  // Build Planner
  slot: "", slotBuild: "", search: "", dock: "outfit", drawer: "", hull: "", pips: null, pipsBuild: "",
  // Engineering
  tab: "ship", engineer: "", filter: "all", find: "", type: "",
};
try {
  view.tab = window.localStorage.getItem("voidcompass.workshop.engineering") || "ship";
  view.dock = window.localStorage.getItem("voidcompass.workshop.dock") || "outfit";
} catch { /* storage may be blocked; the defaults stand */ }
if (!ENGINEERING_TABS.some(([id]) => id === view.tab)) view.tab = "ship";

let plannerData = null;
let engineeringData = null;
let searchTimer = 0;

const finite = (value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
const num = (value, fallback = 0) => finite(value) ? Number(value) : fallback;
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const lower = (value) => String(value || "").toLocaleLowerCase();
const remember = (key, value) => {
  try { window.localStorage.setItem(key, value); } catch { /* optional */ }
};

// --- The hull ---------------------------------------------------------------
// Ship art is the bundled line drawing. Loaded inline (once per hull) so the
// theme colours it and a hardpoint or utility mount can light up: the layers
// carry the journal's slot names (HugeHardpoint1, TinyHardpoint3).
const hulls = new Map();

function loadHull(asset) {
  hulls.set(asset, null);
  fetch(asset, {cache: "force-cache"})
    .then((response) => response.ok ? response.text() : "")
    .then((text) => {
      const start = text.indexOf("<svg");
      const open = start < 0 ? -1 : text.indexOf(">", start);
      // The drawing sizes to its box: the root's fixed width and height go.
      hulls.set(asset, open < 0 ? "" : text.slice(start, open).replace(/\s(width|height)="[^"]*"/g, "") + text.slice(open));
      document.querySelectorAll(".wk-hull[data-wk-hull]").forEach((node) => {
        if (node.dataset.wkHull === asset && hulls.get(asset)) node.innerHTML = hulls.get(asset);
      });
      paintHulls();
    })
    .catch(() => hulls.set(asset, ""));
}

function hull(asset, name, {lit = [], empty = [], esc}) {
  const svg = asset ? hulls.get(asset) : "";
  if (asset && svg === undefined) loadHull(asset);
  const inner = svg || (asset ? `<img src="${esc(asset)}" alt="${esc(name)}">` : `<span class="wk-hull-none">NO HULL DRAWING</span>`);
  return `<div class="wk-hull" data-wk-hull="${esc(asset)}" data-wk-lit="${esc(lit.join(" "))}" data-wk-empty="${esc(empty.join(" "))}">${inner}</div>`;
}

function paintHulls(root = document) {
  root.querySelectorAll(".wk-hull").forEach((node) => {
    const lit = new Set((node.dataset.wkLit || "").split(" ").filter(Boolean));
    const empty = new Set((node.dataset.wkEmpty || "").split(" ").filter(Boolean));
    node.querySelectorAll("[data-journal-slot]").forEach((layer) => {
      layer.classList.toggle("lit", lit.has(layer.dataset.journalSlot));
      layer.classList.toggle("empty", empty.has(layer.dataset.journalSlot));
    });
  });
}

// Hovering a slot shows where it sits on the hull.
document.addEventListener("mouseover", (event) => {
  const row = event.target.closest?.("[data-wk-journal]");
  const page = event.target.closest?.(".wk");
  if (!page) return;
  page.querySelectorAll(".wk-hull [data-journal-slot].hover").forEach((layer) => layer.classList.remove("hover"));
  if (!row?.dataset.wkJournal) return;
  page.querySelectorAll(`.wk-hull [data-journal-slot="${CSS.escape(row.dataset.wkJournal)}"]`).forEach((layer) => layer.classList.add("hover"));
});

// The planner numbers hardpoints by size in fitting order, as the journal does.
function journalSlots(slots) {
  const counts = {};
  const names = {};
  for (const row of slots) {
    if (row.group === "hardpoint") {
      const size = HARDPOINT_SIZES[row.size] || "Small";
      counts[size] = (counts[size] || 0) + 1;
      names[row.key] = `${size}Hardpoint${counts[size]}`;
    } else if (row.group === "utility") {
      names[row.key] = `TinyHardpoint${num(row.index) + 1}`;
    }
  }
  return names;
}

// --- Shared pieces ----------------------------------------------------------
function gradePips(grade, max = 5) {
  return `<i class="wk-grade" title="Grade ${grade}">${Array.from({length: max}, (_, index) => `<b class="${index < grade ? "on" : ""}"></b>`).join("")}</i>`;
}

// value − comparison, toned by whether that is better (better = 1: higher
// is better; −1: lower is better).
function delta(ui, value, other, digits = 1, better = 1, unit = "") {
  if (!finite(value) || !finite(other)) return "";
  const diff = Number(value) - Number(other);
  if (Math.abs(diff) < 0.5 * 10 ** -digits) return `<em class="wk-delta">±0</em>`;
  return `<em class="wk-delta ${diff * better > 0 ? "up" : "down"}">${diff > 0 ? "+" : "−"}${ui.numeric(Math.abs(diff), digits)}${unit}</em>`;
}

function bar(percent, tone = "") {
  return `<i class="wk-bar ${tone}"><b style="width:${clamp(num(percent), 0, 100)}%"></b></i>`;
}

// --- Build Planner ----------------------------------------------------------
function fitsSlot(row, slot, shipId) {
  const groupFit = slot.group === "component" ? (row.components || []).includes(num(slot.index)) : (row.groups || []).includes(slot.group);
  const typeFit = !(slot.allowedTypes || []).length || slot.allowedTypes.includes(row.type);
  const hullFit = !(row.reservedShips || []).length || row.reservedShips.includes(String(shipId));
  return groupFit && typeFit && hullFit && !row.hidden && num(row.class) <= num(slot.size);
}

function plannerAlerts(data, ui) {
  const analysis = data.analysis || {};
  const rows = [
    ...(data.error ? [["error", data.error]] : []),
    ...(data.notice ? [["notice", data.notice]] : []),
    ...(analysis.invalid || []).map((row) => ["error", row]),
    ...(analysis.warnings || []).map((row) => ["warning", row]),
  ];
  return rows.length ? `<div class="wk-alerts">${rows.map(([tone, message]) => `<p class="wk-alert ${tone}">${ui.escapeHtml(message)}</p>`).join("")}</div>` : "";
}

function hangar(data, ui) {
  const esc = ui.escapeHtml;
  const selected = data.selected || {};
  const live = data.live || {};
  const compareId = data.comparison?.build?.id || "";
  const tiles = [
    ...(live.available ? [{id: "live", name: live.name || "Current ship", ship: live.ship, asset: live.asset, live: true}] : []),
    ...(data.builds || []),
  ].map((row) => `<button type="button" class="wk-tile${row.id === selected.id ? " active" : ""}${row.live ? " live" : ""}" data-wk-build="${esc(row.id)}" title="${esc(row.name)} · ${esc(row.ship || "")}">
      ${row.asset ? `<img src="${esc(row.asset)}" alt="" loading="lazy">` : "<i></i>"}
      <span><small>${row.live ? "LIVE LOADOUT" : esc(row.ship || "")}</small><b>${esc(row.name)}</b></span>
      ${row.id === compareId ? `<em>COMPARING</em>` : ""}
    </button>`).join("");
  const compareOptions = [`<option value="">No comparison</option>`, ...(data.builds || []).filter((row) => row.id !== selected.id)
    .map((row) => `<option value="${esc(row.id)}" ${row.id === compareId ? "selected" : ""}>${esc(row.name)} · ${esc(row.ship)}</option>`)].join("");
  const preview = data.importPreview || {};
  const previewRows = (preview.summary || []).map((row) => `<div><b>${esc(row.name)}</b><span>${esc(row.ship)} · ${ui.numeric(row.modules)} modules</span></div>`).join("");
  const drawer = previewRows ? "import" : view.drawer;
  const chosen = view.hull || String((data.ships || [])[0]?.id || "");
  const hullPicks = (data.ships || []).map((row) => `<button type="button" class="wk-hullpick${String(row.id) === chosen ? " active" : ""}" data-wk-hullpick="${esc(row.id)}" title="${esc(row.name)}">
      <img src="${esc(row.asset)}" alt="" loading="lazy"><b>${esc(row.name)}</b><small>${["", "SMALL", "MEDIUM", "LARGE"][num(row.class)] || "—"} · ${ui.credits(row.cost)}</small></button>`).join("");
  return `<section class="wk-hangar">
    <header class="wk-strip-head">
      <span>HANGAR</span><b>${ui.numeric((data.builds || []).length)} SAVED${live.available ? " · 1 LIVE" : ""}</b>
      <label class="wk-compare">COMPARE WITH<select id="bp-compare-select" data-refresh-on-change>${compareOptions}</select></label>
    </header>
    <div class="wk-rail">${tiles}
      <button type="button" class="wk-tile add${drawer === "new" ? " active" : ""}" data-wk-drawer="new"><i>＋</i><span><small>STOCK HULL</small><b>New build</b></span></button>
      <button type="button" class="wk-tile add${drawer === "import" ? " active" : ""}" data-wk-drawer="import"><i>⇩</i><span><small>EDSY · SLEF · JOURNAL</small><b>Import</b></span></button>
    </div>
    <section class="bp-new-build wk-drawer" id="bp-new-build"${drawer === "new" ? "" : " hidden"}>
      <header><div><small>START A LOADOUT</small><strong>Choose a hull</strong></div>
        <label>BUILD NAME<input id="bp-new-name" maxlength="80" placeholder="Optional — the ship's name by default"></label>
        <input type="hidden" id="bp-new-ship" value="${esc(chosen)}">
        <button class="primary" data-ws-page="build-planner" data-ws-op="create">CREATE BUILD</button>
      </header>
      <div class="wk-hullpicks">${hullPicks}</div>
    </section>
    <section class="wk-drawer wk-import"${drawer === "import" ? "" : " hidden"}>
      <textarea id="bp-import" spellcheck="false" placeholder="Paste an EDSY link, an EDSY backup, a SLEF loadout or a journal Loadout event"></textarea>
      <div class="wk-import-side">
        <button data-ws-page="build-planner" data-ws-op="import_preview">VALIDATE</button>
        ${previewRows ? `<div class="wk-import-preview">${previewRows}</div><button class="primary" data-ws-page="build-planner" data-ws-op="import_apply">IMPORT ${ui.numeric(preview.count)} BUILD${num(preview.count) === 1 ? "" : "S"}</button>` : `<p class="wk-note">Validate first: nothing is added until you import.</p>`}
      </div>
    </section>
  </section>`;
}

function pipsPanel(selected, ui) {
  const pips = view.pipsBuild === selected.id && view.pips ? view.pips : {sys: num(selected.pips?.sys, 4), eng: num(selected.pips?.eng, 4), wep: num(selected.pips?.wep, 4)};
  const locked = !selected.editable;
  const columns = AXES.map((axis) => `<div class="wk-pipcol">
      <div class="wk-pipstack">${[8, 7, 6, 5, 4, 3, 2, 1].map((level) =>
        `<button type="button" class="wk-pip${pips[axis] >= level ? " on" : ""}${level % 2 ? " half" : ""}" data-wk-pip="${axis}" data-level="${level}" ${locked ? "disabled" : ""} aria-label="${axis.toUpperCase()} ${level / 2} pips"></button>`).join("")}</div>
      <b>${axis.toUpperCase()}</b><small>${ui.numeric(pips[axis] / 2, 1)}</small>
      <input type="hidden" id="bp-pip-${axis}" value="${pips[axis]}">
    </div>`).join("");
  return `<div class="wk-load">
    <header><span>DISTRIBUTOR</span><button type="button" class="wk-mini" data-wk-pip-reset ${locked ? "disabled" : ""}>4 · 4 · 4</button></header>
    <div class="wk-pips">${columns}</div>
    <div class="wk-loadfields">
      <label>FUEL T<input id="bp-fuel" type="number" min="0" step="0.1" placeholder="FULL" data-wk-load data-refresh-on-change value="${selected.fuel == null ? "" : ui.numeric(selected.fuel, 1).replace(/,/g, "")}" ${locked ? "disabled" : ""}></label>
      <label>CARGO T<input id="bp-cargo" type="number" min="0" step="1" data-wk-load data-refresh-on-change value="${num(selected.cargo)}" ${locked ? "disabled" : ""}></label>
    </div>
  </div>`;
}

function bay(data, ui) {
  const esc = ui.escapeHtml;
  const selected = data.selected || {};
  const analysis = data.analysis || {};
  const totals = analysis.totals || {};
  const slots = data.slots || [];
  const fitted = slots.filter((row) => num(row.module));
  const engineered = fitted.filter((row) => row.blueprint);
  const names = journalSlots(slots);
  const lit = names[view.slot] ? [names[view.slot]] : [];
  const empty = slots.filter((row) => names[row.key] && !num(row.module)).map((row) => names[row.key]);
  const editable = Boolean(selected.editable);
  const title = (selected.id === "live" ? data.live?.name : selected.name) || selected.ship || "Ship build";
  const status = analysis.valid
    ? `<span class="wk-flag ok">VALID BUILD</span>`
    : `<span class="wk-flag bad">${ui.numeric((analysis.invalid || []).length)} FITTING ERROR${(analysis.invalid || []).length === 1 ? "" : "S"}</span>`;
  const manage = editable
    ? `<div class="wk-rename"><input id="bp-name" maxlength="80" value="${esc(selected.name || "")}" aria-label="Build name"><button data-ws-page="build-planner" data-ws-op="rename">RENAME</button></div>
       <div class="wk-actions">
         <button data-ws-page="build-planner" data-ws-op="clone" title="Copy this build into a new one">DUPLICATE</button>
         <button data-ws-page="build-planner" data-ws-op="export_copy" title="Copy as a SLEF loadout for EDSY, Coriolis or Inara">COPY SLEF</button>
         <button data-ws-page="build-planner" data-ws-op="send_engineering" title="Reserve this build's engineering materials on the Engineering page">SEND TO ENGINEERING</button>
         <button class="danger-action" data-ws-page="build-planner" data-ws-op="delete">DELETE</button>
       </div>`
    : `<div class="wk-actions">
         <button class="primary" data-ws-page="build-planner" data-ws-op="clone" title="The live loadout is read-only: edit a copy">CLONE TO EDIT</button>
         <button data-ws-page="build-planner" data-ws-op="export_copy" title="Copy as a SLEF loadout for EDSY, Coriolis or Inara">COPY SLEF</button>
       </div>
       <p class="wk-note">The live loadout follows the journal and is read-only. Clone it to plan changes.</p>`;
  return `<section class="wk-bay">
    ${hull(selected.asset, selected.ship, {lit, empty, esc})}
    <div class="wk-ident">
      <small>${esc(selected.source || "VoidCompass build")}${selected.tag ? ` · ${esc(selected.tag)}` : ""}</small>
      <h2 title="${esc(title)}">${esc(title)}</h2>
      <p class="wk-shiptype">${esc(selected.ship || "")}</p>
      <div class="wk-flags">${status}<span class="wk-flag">${ui.numeric(fitted.length)} MODULES</span><span class="wk-flag">${ui.numeric(engineered.length)} ENGINEERED</span></div>
      <dl class="wk-value"><div><dt>BUILD COST</dt><dd>${ui.credits(totals.cost)}</dd></div><div><dt>REBUY</dt><dd>${ui.credits(totals.rebuy)}</dd></div></dl>
      ${manage}
    </div>
    ${pipsPanel(selected, ui)}
  </section>`;
}

function readouts(data, ui) {
  const analysis = data.analysis || {};
  const other = data.comparison?.analysis;
  const nav = analysis.navigation || {}, defenses = analysis.defenses || {}, weapons = analysis.weapons || {};
  const power = analysis.power || {}, thermal = analysis.thermal || {};
  const shieldResists = defenses.shieldResistances || {};
  const tiles = [
    ["JUMP", nav.currentJump, "LY", 2, 1, other?.navigation?.currentJump, `MAX ${ui.numeric(nav.maxJump, 2)} · LADEN ${ui.numeric(nav.ladenJump, 2)}`],
    ["TOTAL RANGE", nav.unladenRange, "LY", 1, 1, other?.navigation?.unladenRange, `LADEN ${ui.numeric(nav.ladenRange, 1)} LY`],
    ["SPEED", nav.speed, "M/S", 0, 1, other?.navigation?.speed, nav.boost ? `BOOST ${ui.numeric(nav.boost)} M/S` : "NO BOOST"],
    ["SHIELDS", defenses.shield, "MJ", 0, 1, other?.defenses?.shield, RESISTS.slice(0, 3).map(([key, label]) => `${label} ${ui.numeric(shieldResists[key])}`).join(" · ")],
    ["ARMOUR", defenses.armour, "", 0, 1, other?.defenses?.armour, `HARDNESS ${ui.numeric(defenses.hardness)}`],
    ["DPS", weapons.dps, "", 1, 1, other?.weapons?.dps, `SUSTAINED ${ui.numeric(weapons.sustainedDps, 1)}`],
    ["POWER", power.deployedPercent, "%", 0, -1, other?.power?.deployedPercent, `${ui.numeric(power.deployed, 1)} / ${ui.numeric(power.capacity, 1)} MW`, num(power.deployedPercent) > 100],
    ["HEAT", thermal.idle, "%", 0, -1, other?.thermal?.idle, `IDLE · ${ui.numeric(thermal.dissipation, 1)} MW OUT`, num(thermal.idle) > 100],
  ];
  const comparing = data.comparison?.build;
  return `<section class="wk-readouts${comparing ? " comparing" : ""}">
    ${comparing ? `<p class="wk-versus">DIFFERENCE AGAINST <b>${ui.escapeHtml(comparing.name)}</b> · ${ui.escapeHtml(comparing.ship)}</p>` : ""}
    ${tiles.map(([label, value, unit, digits, better, before, detail, warn]) => `<article class="${warn ? "warn" : ""}">
      <small>${label}</small><strong>${ui.numeric(value, digits)}<span>${unit}</span></strong>${delta(ui, value, before, digits, better)}<p>${detail}</p>
    </article>`).join("")}
  </section>`;
}

function board(data, ui) {
  const esc = ui.escapeHtml;
  const slots = data.slots || [];
  const names = journalSlots(slots);
  const blueprintName = (id) => (data.blueprints || []).find((row) => row.id === id)?.name || id;
  const effectName = (id) => (data.effects || []).find((row) => row.id === id)?.name || id;
  const groups = BOARD_ORDER.filter((group) => slots.some((row) => row.group === group)).map((group) => {
    const rows = slots.filter((row) => row.group === group).map((row) => {
      const fitted = num(row.module) > 0;
      return `<button type="button" class="wk-slot${row.key === view.slot ? " active" : ""}${fitted ? "" : " empty"}${row.enabled === false ? " off" : ""}" data-bp-slot="${esc(row.key)}"${names[row.key] ? ` data-wk-journal="${esc(names[row.key])}"` : ""}>
        <i class="wk-size">${row.group === "utility" ? "U" : num(row.size) || "·"}</i>
        <span class="wk-slot-main"><b>${fitted ? esc(row.moduleLabel) : "Empty"}</b>${row.blueprint
          ? `<small class="eng">${esc(blueprintName(row.blueprint))}${row.experimental ? ` <em>✦ ${esc(effectName(row.experimental))}</em>` : ""}</small>`
          : `<small>${esc(row.label)}</small>`}</span>
        ${row.blueprint ? gradePips(num(row.grade)) : ""}
        ${fitted && row.enabled === false ? `<em class="wk-off">OFF</em>` : ""}
      </button>`;
    }).join("");
    return `<section class="wk-group"><h4>${GROUPS[group] || group.toUpperCase()}<b>${slots.filter((row) => row.group === group && num(row.module)).length} / ${slots.filter((row) => row.group === group).length}</b></h4>${rows}</section>`;
  }).join("");
  return `<div class="wk-board"><header class="wk-strip-head"><span>LOADOUT</span><b>${ui.numeric(slots.length)} SLOTS · HOVER TO FIND ON THE HULL</b></header><div class="wk-board-cols">${groups}</div></div>`;
}

function dock(data, ui) {
  const esc = ui.escapeHtml;
  const selected = data.selected || {};
  const slot = (data.slots || []).find((row) => row.key === view.slot) || {};
  if (!slot.key) return `<aside class="wk-dock"><p class="wk-empty">Choose a slot on the board.</p></aside>`;
  const editable = Boolean(selected.editable);
  const module = (data.modules || []).find((row) => num(row.id) === num(slot.module)) || {};
  const fitted = num(slot.module) > 0;
  const tab = !fitted && view.dock !== "outfit" ? "outfit" : view.dock;
  const tabs = [["outfit", "OUTFIT"], ["engineer", "ENGINEER"], ["attributes", "ATTRIBUTES"]].map(([id, label]) =>
    `<button type="button" class="wk-docktab${tab === id ? " active" : ""}" data-wk-dock="${id}" ${id !== "outfit" && !fitted ? "disabled" : ""}>${label}</button>`).join("");
  let body = "";
  if (tab === "outfit") {
    const needle = lower(view.search);
    const candidates = (data.modules || []).filter((row) => fitsSlot(row, slot, selected.shipId)
      && (!needle || lower(`${row.name} ${row.label} ${row.typeName} ${row.mount}`).includes(needle)))
      .sort((a, b) => String(a.typeName).localeCompare(String(b.typeName)) || num(b.class) - num(a.class) || String(a.rating).localeCompare(String(b.rating)))
      .slice(0, 300);
    const rows = candidates.map((row) => {
      const current = num(row.id) === num(slot.module);
      return `<button type="button" class="wk-module${current ? " active" : ""}" data-bp-module="${row.id}" ${editable ? "" : "disabled"}>
        <i>${num(row.class)}${esc(row.rating)}${row.mount ? `<small>${esc(row.mount)}</small>` : ""}</i>
        <span><b>${esc(row.name)}</b><small>${esc(row.typeName)}</small></span>
        <span class="wk-mnum">${ui.numeric(row.mass, 1)} T${current || !fitted ? "" : delta(ui, row.mass, slot.mass, 1, -1)}</span>
        <span class="wk-mnum">${ui.numeric(row.power, 2)} MW${current || !fitted ? "" : delta(ui, row.power, slot.power, 2, -1)}</span>
        <span class="wk-mnum cost">${ui.credits(row.cost)}</span>
      </button>`;
    }).join("");
    body = `<div class="wk-search"><input id="bp-search" value="${esc(view.search)}" placeholder="Search modules that fit this slot…" autocomplete="off"></div>
      <div class="wk-modules">
        ${slot.group !== "component" && editable && fitted ? `<button type="button" class="wk-module clear" data-bp-module="0"><i>—</i><span><b>Remove module</b><small>Leave the slot empty</small></span></button>` : ""}
        ${rows || `<p class="wk-empty">No module that fits this slot matches “${esc(view.search)}”.</p>`}
      </div>`;
  } else if (tab === "engineer") {
    const blueprints = (module.blueprints || []).map((id) => (data.blueprints || []).find((row) => row.id === id) || {id, name: id, maxGrade: 5});
    const current = blueprints.find((row) => row.id === slot.blueprint);
    const maxGrade = num(current?.maxGrade, 5);
    const effects = (module.effects || []).map((id) => (data.effects || []).find((row) => row.id === id) || {id, name: id});
    const lock = editable ? "" : "disabled";
    body = blueprints.length ? `<div class="wk-engform">
        <label>BLUEPRINT<select id="bp-blueprint" ${lock}><option value="">No engineering</option>${blueprints.map((row) => `<option value="${esc(row.id)}" ${row.id === slot.blueprint ? "selected" : ""}>${esc(row.name)} · G${num(row.maxGrade, 5)}</option>`).join("")}</select></label>
        <div class="wk-field"><span>GRADE</span><div class="wk-seg" data-wk-seg="bp-grade">${[1, 2, 3, 4, 5].map((grade) =>
          `<button type="button" class="wk-segbtn${num(slot.grade) === grade ? " active" : ""}" data-value="${grade}" ${lock} ${grade > maxGrade ? "disabled" : ""}>G${grade}</button>`).join("")}</div>
          <input type="hidden" id="bp-grade" value="${num(slot.grade) || Math.min(5, maxGrade)}"></div>
        <label>ROLL<span class="wk-roll"><input id="bp-roll" type="range" min="0" max="100" step="1" value="${Math.round(num(slot.roll, 1) * 100)}" ${lock}><output id="bp-roll-value">${Math.round(num(slot.roll, 1) * 100)}%</output></span></label>
        <label>EXPERIMENTAL<select id="bp-experimental" ${lock}><option value="">None</option>${effects.map((row) => `<option value="${esc(row.id)}" ${row.id === slot.experimental ? "selected" : ""} title="${esc(row.description || "")}">${esc(row.name)}</option>`).join("")}</select></label>
        <div class="wk-field"><span>POWER PRIORITY</span><div class="wk-seg" data-wk-seg="bp-priority">${[1, 2, 3, 4, 5].map((priority) =>
          `<button type="button" class="wk-segbtn${num(slot.priority, 1) === priority ? " active" : ""}" data-value="${priority}" ${lock}>${priority}</button>`).join("")}</div>
          <input type="hidden" id="bp-priority" value="${num(slot.priority, 1)}"></div>
        <label class="wk-check"><input id="bp-enabled" type="checkbox" ${slot.enabled === false ? "" : "checked"} ${lock}>MODULE POWERED</label>
        <button class="primary" data-ws-page="build-planner" data-ws-op="configure_slot" ${lock}>APPLY TO ${esc(slot.label || "SLOT").toUpperCase()}</button>
      </div>` : `<p class="wk-empty">${esc(module.name || "This module")} takes no engineering. Power priority and the power switch are on the board's module when it has one.</p>`;
  } else {
    const metadata = Object.fromEntries((data.attributes || []).map((row) => [row.id, row]));
    const rows = Object.entries(slot.attrs || {}).filter(([id, value]) => num(value) !== 0 && !metadata[id]?.hidden).map(([id, value]) => {
      const info = metadata[id] || {};
      return `<div title="${esc(info.description || "")}"><span>${esc(info.name || id)}</span><b>${ui.numeric(value, Math.abs(num(value)) < 10 ? 2 : 0)} <small>${esc(String(info.unit || "").replace("&deg;", "°"))}</small></b></div>`;
    }).join("");
    body = `<div class="wk-attrs">${rows || `<p class="wk-empty">No numeric attributes.</p>`}</div>`;
  }
  return `<aside class="wk-dock">
    <header><small>${esc(slot.label || "")}</small><h3>${esc(fitted ? slot.moduleLabel : "Empty slot")}</h3>
      <p>${fitted ? `${ui.numeric(slot.mass, 1)} T · ${ui.numeric(slot.power, 2)} MW · ${ui.credits(slot.cost)}` : `Class ${num(slot.size)} ${esc(GROUPS[slot.group] || "").toLowerCase()}`}</p></header>
    <nav class="wk-docktabs">${tabs}</nav>
    ${body}
  </aside>`;
}

function rangeChart(curve, ui) {
  if (!Array.isArray(curve) || curve.length < 2) return "";
  const width = 300, height = 110, left = 34, right = 8, top = 8, bottom = 22;
  const maxCargo = num(curve[curve.length - 1].cargo);
  const jumps = curve.map((row) => num(row.jump));
  const high = Math.max(...jumps), low = Math.min(...jumps);
  const span = Math.max(0.01, high - low);
  const x = (cargo) => left + (width - left - right) * (maxCargo ? cargo / maxCargo : 0);
  const y = (jump) => top + (height - top - bottom) * (1 - (jump - low) / span);
  const line = curve.map((row) => `${x(num(row.cargo)).toFixed(1)},${y(num(row.jump)).toFixed(1)}`).join(" ");
  return `<figure class="wk-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Jump range against cargo">
      <line class="axis" x1="${left}" y1="${height - bottom}" x2="${width - right}" y2="${height - bottom}"></line>
      <line class="axis" x1="${left}" y1="${top}" x2="${left}" y2="${height - bottom}"></line>
      <polygon class="area" points="${left},${height - bottom} ${line} ${width - right},${height - bottom}"></polygon>
      <polyline class="line" points="${line}"></polyline>
      <text x="${left - 4}" y="${top + 4}" text-anchor="end">${ui.numeric(high, 1)}</text>
      <text x="${left - 4}" y="${height - bottom}" text-anchor="end">${ui.numeric(low, 1)}</text>
      <text x="${left}" y="${height - 6}">0 T</text>
      <text x="${width - right}" y="${height - 6}" text-anchor="end">${ui.numeric(maxCargo)} T CARGO</text>
    </svg><figcaption>JUMP (LY) AS THE HOLD FILLS · FULL TANK</figcaption></figure>`;
}

function performance(data, ui) {
  const analysis = data.analysis || {};
  const other = data.comparison?.analysis || {};
  const totals = analysis.totals || {}, nav = analysis.navigation || {}, defenses = analysis.defenses || {};
  const weapons = analysis.weapons || {}, power = analysis.power || {}, thermal = analysis.thermal || {}, handling = analysis.handling || {};
  const row = (label, value, digits, unit, before, better = 1) =>
    `<div class="wk-row"><span>${label}</span><b>${ui.numeric(value, digits)}${unit ? ` <small>${unit}</small>` : ""}</b>${delta(ui, value, before, digits, better)}</div>`;
  const creditRow = (label, value, before) =>
    `<div class="wk-row"><span>${label}</span><b>${ui.credits(value)}</b>${finite(before) ? delta(ui, value, before, 0, -1) : ""}</div>`;
  const panel = (title, badge, body, extra = "") => `<article class="wk-panel ${extra}"><header><span>${title}</span>${badge ? `<b>${badge}</b>` : ""}</header>${body}</article>`;

  const range = panel("FRAME SHIFT", `${ui.numeric(nav.currentJump, 2)} LY NOW`, `
    ${row("Max jump", nav.maxJump, 2, "LY", other.navigation?.maxJump)}
    ${row("Unladen jump", nav.unladenJump, 2, "LY", other.navigation?.unladenJump)}
    ${row("Laden jump", nav.ladenJump, 2, "LY", other.navigation?.ladenJump)}
    ${row("Range on a full tank", nav.unladenRange, 1, "LY", other.navigation?.unladenRange)}
    ${row("Laden range", nav.ladenRange, 1, "LY", other.navigation?.ladenRange)}
    ${rangeChart(nav.curve, ui)}`);

  const flight = panel("FLIGHT", nav.boost ? "BOOST READY" : "CANNOT BOOST", `
    ${row("Top speed", nav.speed, 0, "m/s", other.navigation?.speed)}
    ${row("Boost", nav.boost, 0, "m/s", other.navigation?.boost)}
    ${row("Boost interval", nav.boostInterval, 1, "s", other.navigation?.boostInterval, -1)}
    ${row("Pitch", handling.pitch, 1, "°/s", other.handling?.pitch)}
    ${row("Roll", handling.roll, 1, "°/s", other.handling?.roll)}
    ${row("Yaw", handling.yaw, 1, "°/s", other.handling?.yaw)}
    ${row("Half loop (pitch 180°)", handling.pitch180, 1, "s", other.handling?.pitch180, -1)}`);

  const resistGrid = `<div class="wk-resists"><span></span>${RESISTS.map(([, label]) => `<small>${label}</small>`).join("")}
    ${[["SHIELD", defenses.shieldResistances || {}], ["ARMOUR", defenses.armourResistances || {}]].map(([label, values]) => `<small>${label}</small>${RESISTS.map(([key]) =>
      `<div class="wk-resist${num(values[key]) < 0 ? " neg" : ""}">${bar(values[key])}<b>${ui.numeric(values[key], 1)}%</b></div>`).join("")}`).join("")}</div>`;
  const defence = panel("DEFENCE", defenses.shield ? `${ui.numeric(defenses.shield)} MJ SHIELD` : "NO SHIELD", `
    ${row("Shield strength", defenses.shield, 0, "MJ", other.defenses?.shield)}
    ${row("Armour", defenses.armour, 0, "", other.defenses?.armour)}
    ${row("Hardness", defenses.hardness, 0, "", other.defenses?.hardness)}
    ${resistGrid}`);

  const mix = DAMAGE.filter(([key]) => num(weapons[key]) > 0);
  const mixTotal = mix.reduce((sum, [key]) => sum + num(weapons[key]), 0);
  const offence = panel("OFFENCE", weapons.dps ? `${ui.numeric(weapons.dps, 1)} DPS` : "UNARMED", `
    ${row("Burst DPS", weapons.dps, 1, "", other.weapons?.dps)}
    ${row("Sustained DPS", weapons.sustainedDps, 1, "", other.weapons?.sustainedDps)}
    ${mixTotal ? `<div class="wk-mix">${mix.map(([key, label]) => `<b class="dmg-${key}" style="flex:${num(weapons[key])}" title="${label} ${ui.numeric(weapons[key], 1)} DPS"></b>`).join("")}</div>
      <div class="wk-mixkey">${mix.map(([key, label]) => `<span class="dmg-${key}"><i></i>${label} ${ui.numeric(num(weapons[key]) / mixTotal * 100)}%</span>`).join("")}</div>` : ""}
    ${row("Distributor draw", weapons.distributorDraw, 2, "MW", other.weapons?.distributorDraw, -1)}
    ${row("Weapons capacitor lasts", weapons.capacitorDuration, 1, "s", other.weapons?.capacitorDuration)}
    ${row("Ammunition lasts", weapons.ammoTime, 0, "s", other.weapons?.ammoTime)}`);

  const capacity = Math.max(0.001, num(power.capacity));
  const priorities = [1, 2, 3, 4, 5].map((priority, index) => {
    const deployed = num((power.prioritiesDeployed || [])[index]);
    const retracted = num((power.prioritiesRetracted || [])[index]);
    // The bars run to 125% of the plant so an overdraw shows past the line.
    return `<div class="wk-prio${deployed > capacity ? " over" : ""}"><small>P${priority}</small>
      <i><b class="ret" style="width:${clamp(retracted / capacity * 80, 0, 100)}%"></b><b class="dep" style="width:${clamp(deployed / capacity * 80, 0, 100)}%"></b><u style="left:80%"></u></i>
      <em>${ui.numeric(deployed / capacity * 100)}%</em></div>`;
  }).join("");
  const powerPanel = panel("POWER", `${ui.numeric(power.deployed, 2)} / ${ui.numeric(power.capacity, 2)} MW`, `
    <div class="wk-prios">${priorities}</div>
    <p class="wk-legend"><span class="ret"><i></i>HARDPOINTS RETRACTED</span><span class="dep"><i></i>DEPLOYED</span><span><u></u>PLANT OUTPUT</span></p>
    ${row("Retracted draw", power.retracted, 2, "MW", other.power?.retracted, -1)}
    ${row("Deployed draw", power.deployed, 2, "MW", other.power?.deployed, -1)}`, num(power.deployedPercent) > 100 ? "warn" : "");

  const heatRows = HEAT.map(([key, label]) => `<div class="wk-heat${num(thermal[key]) > 100 ? " over" : ""}"><span>${label}</span>
      <i><b style="width:${clamp(num(thermal[key]) * 0.66, 0, 100)}%"></b><u style="left:66%"></u></i><em>${ui.numeric(thermal[key])}%</em>${delta(ui, thermal[key], other.thermal?.[key], 0, -1)}</div>`).join("");
  const heat = panel("THERMAL", `IDLE ${ui.numeric(thermal.idle)}%`, `
    <div class="wk-heats">${heatRows}</div>
    ${row("Heat capacity", thermal.capacity, 0, "", other.thermal?.capacity)}
    ${row("Dissipation", thermal.dissipation, 1, "MW", other.thermal?.dissipation)}`);

  const mass = panel("MASS & VALUE", `${ui.numeric(totals.unladenMass, 1)} T UNLADEN`, `
    ${row("Hull and modules", totals.mass, 1, "T", other.totals?.mass, -1)}
    ${row("Unladen", totals.unladenMass, 1, "T", other.totals?.unladenMass, -1)}
    ${row("Laden", totals.ladenMass, 1, "T", other.totals?.ladenMass, -1)}
    ${row("Fuel capacity", totals.fuel, 0, "T", other.totals?.fuel)}
    ${row("Cargo capacity", totals.cargo, 0, "T", other.totals?.cargo)}
    ${row("Passenger berths", totals.passengers, 0, "", other.totals?.passengers)}
    ${creditRow("Build cost", totals.cost, other.totals?.cost)}
    ${creditRow("Rebuy (5%)", totals.rebuy, other.totals?.rebuy)}`);

  return `<section class="wk-perf">${range}${flight}${defence}${offence}${powerPanel}${heat}${mass}</section>`;
}

export function renderBuildPlanner(data, ui) {
  const root = ui.byId("build-planner-workspace");
  if (!root) return;
  plannerData = data;
  const slots = data.slots || [];
  if (view.slotBuild !== data.selected?.id) {
    view.slotBuild = data.selected?.id;
    view.slot = "";
    view.search = "";
  }
  if (!slots.some((row) => row.key === view.slot)) {
    view.slot = slots.find((row) => row.group === "hardpoint" && num(row.module))?.key
      || slots.find((row) => row.group === "component")?.key || slots[0]?.key || "";
  }
  // A pip change shows at once; the saved build takes over when it matches.
  const saved = data.selected?.pips || {};
  if (view.pips && (view.pipsBuild !== data.selected?.id || AXES.every((axis) => num(saved[axis]) === view.pips[axis]))) view.pips = null;
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="wk wk-planner">
    ${plannerAlerts(data, ui)}
    ${hangar(data, ui)}
    ${bay(data, ui)}
    ${readouts(data, ui)}
    <section class="wk-outfit">${board(data, ui)}${dock(data, ui)}</section>
    ${performance(data, ui)}
    <footer class="wk-source">EDSY DATA ${ui.escapeHtml(data.catalogueVersion || "")} · ${ui.escapeHtml(data.catalogueDate || "")} · CALCULATED OFFLINE · BUILDS ARE SAVED TO THIS PROFILE</footer>
  </div>`;
  paintHulls(root);
}

function sendLoad(ui, pips) {
  return ui.command("workspace", {
    page: "build-planner", operation: "set_load", pips,
    fuel: ui.byId("bp-fuel")?.value ?? "", cargo: ui.byId("bp-cargo")?.value || 0,
  });
}

// Moving one axis takes the difference evenly from the other two, as the
// ship's distributor does; the total stays at 12 half-pips.
function setPip(pips, axis, level) {
  const next = {...pips, [axis]: clamp(level, 0, 8)};
  let spare = pips[axis] - next[axis];
  for (let guard = 0; spare !== 0 && guard < 24; guard += 1) {
    const step = spare > 0 ? 1 : -1;
    const pool = AXES.filter((name) => name !== axis && (step > 0 ? next[name] < 8 : next[name] > 0))
      .sort((a, b) => step > 0 ? next[a] - next[b] : next[b] - next[a]);
    if (!pool.length) return pips;
    next[pool[0]] += step;
    spare -= step;
  }
  return next;
}

// --- Engineering ------------------------------------------------------------
function slotLabel(slot) {
  const value = String(slot || "");
  const optional = value.match(/^Slot(\d+)_Size(\d+)$/i);
  if (optional) return `Optional ${Number(optional[1])} · class ${optional[2]}`;
  const hardpoint = value.match(/^(Tiny|Small|Medium|Large|Huge)Hardpoint(\d+)$/i);
  if (hardpoint) return hardpoint[1].toLowerCase() === "tiny" ? `Utility ${hardpoint[2]}` : `${hardpoint[1]} hardpoint ${hardpoint[2]}`;
  const military = value.match(/^Military(\d+)$/i);
  if (military) return `Military ${Number(military[1])}`;
  return ({Armour: "Bulkheads", PowerPlant: "Power plant", MainEngines: "Thrusters", FrameShiftDrive: "Frame shift drive",
    LifeSupport: "Life support", PowerDistributor: "Power distributor", Radar: "Sensors", FuelTank: "Fuel tank"})[value]
    || value.replace(/([a-z])(\d)/g, "$1 $2");
}

// The journal names bulkheads by hull and grade; the game by material.
const ARMOUR = [[/grade1/i, "Lightweight Alloy"], [/grade2/i, "Reinforced Alloy"], [/grade3/i, "Military Grade Composite"],
  [/mirrored/i, "Mirrored Surface Composite"], [/reactive/i, "Reactive Surface Composite"]];
function moduleName(row) {
  if (String(row.slot) !== "Armour") return row.name;
  return ARMOUR.find(([pattern]) => pattern.test(String(row.moduleId || row.name)))?.[1] || row.name;
}

function slotGroup(row) {
  const slot = String(row.slot || "");
  if (/^TinyHardpoint/i.test(slot)) return "UTILITY MOUNTS";
  if (/Hardpoint/i.test(slot)) return "HARDPOINTS";
  if (row.category === "Core Internals" || row.category === "Fuel Tank") return "CORE INTERNALS";
  return "OPTIONAL INTERNALS";
}

function engineeredSlots(slots) {
  return slots.filter((row) => !COSMETIC_SLOT.test(String(row.slot || "")) && !row.empty);
}

function nextAction(data, ui) {
  const pins = data.pins || [];
  const esc = ui.escapeHtml;
  const plan = pins.find((row) => row.craftable) || pins[0];
  if (!plan) {
    return `<div class="wk-next"><small>NO PLANS YET</small><b>Plan a build</b><p>Design or clone a loadout in the Build Planner, then send it here to reserve its materials.</p><button data-page="build-planner">OPEN BUILD PLANNER</button></div>`;
  }
  const engineer = (data.engineers || []).find((person) => (person.offers || []).some((offer) => offer.name === plan.name && (!plan.type || offer.type === plan.type))
    && lower(person.progress) === "unlocked") || (data.engineers || []).find((person) => (person.offers || []).some((offer) => offer.name === plan.name));
  const missing = (plan.materials || []).filter((row) => row.missing).sort((a, b) => b.missing - a.missing);
  return plan.craftable
    ? `<div class="wk-next ready"><small>MATERIALS READY</small><b>Fly to ${esc(engineer?.name || "an engineer")}</b><p>${esc(plan.name)} G${ui.numeric(plan.grade)} · ${esc(plan.type)}${engineer ? ` · ${esc(engineer.system)}` : ""}</p>${engineer ? `<button data-ws-page="engineering" data-ws-op="copy_system" data-system="${esc(engineer.system)}">COPY ${esc(engineer.system).toUpperCase()}</button>` : ""}</div>`
    : `<div class="wk-next"><small>COLLECTION REQUIRED</small><b>Collect ${esc(missing[0]?.name || "materials")}</b><p>${ui.numeric(missing[0]?.missing)} more for ${esc(plan.name)} G${ui.numeric(plan.grade)} · ${ui.numeric(missing.length)} material${missing.length === 1 ? "" : "s"} short</p><button data-engineering-view="sources">WHERE TO FIND IT</button></div>`;
}

function fleetRail(data, ui) {
  const esc = ui.escapeHtml;
  const fleet = data.fleet || [];
  const follow = data.follow_current !== false;
  const tiles = fleet.map((row) => `<button type="button" class="wk-tile ship${row.id === data.selected_ship_id ? " active" : ""}${row.current ? " live" : ""}${row.observed ? "" : " unseen"}"
      data-ws-page="engineering" data-ws-op="select_ship" data-ship-id="${esc(row.id)}" title="${esc(row.label.trim() || row.type)} · ${esc(row.type)}">
      ${row.asset ? `<img src="${esc(row.asset)}" alt="" loading="lazy">` : "<i></i>"}
      <span><small>${row.current ? "CURRENT SHIP" : esc(row.type || "")}</small><b>${esc(row.label.trim() || row.type || "Unnamed")}</b></span>
      ${row.planned ? `<em>PLAN</em>` : ""}
    </button>`).join("");
  return `<section class="wk-hangar wk-fleet">
    <header class="wk-strip-head"><span>FLEET</span><b>${ui.numeric(fleet.length)} SHIP${fleet.length === 1 ? "" : "S"}</b>
      <button type="button" class="wk-follow${follow ? " on" : ""}" data-ws-page="engineering" data-ws-op="follow_current" ${follow ? "disabled" : ""}>${follow ? "● FOLLOWING THE SHIP YOU FLY" : "○ FOLLOW THE SHIP YOU FLY"}</button></header>
    <div class="wk-rail">${tiles || `<p class="wk-empty">The fleet appears after the journal records a Loadout or a visit to a shipyard.</p>`}</div>
  </section>`;
}

function engineeringHero(data, ui) {
  const esc = ui.escapeHtml;
  const ship = data.ship || {};
  const stats = data.ship_stats || {};
  const slots = engineeredSlots(data.slots || []);
  const done = slots.filter((row) => row.engineeringBlueprint);
  const lit = done.map((row) => row.slot).filter((slot) => /Hardpoint/i.test(slot));
  const histogram = [1, 2, 3, 4, 5].map((grade) => done.filter((row) => num(row.engineeringGrade) === grade).length);
  const peak = Math.max(1, ...histogram);
  const experimentals = done.filter((row) => row.experimentalEffect).length;
  const wishlist = data.wishlist || {};
  return `<section class="wk-bay wk-ebay">
    ${hull(ship.asset, ship.type, {lit, esc})}
    <div class="wk-ident">
      <small>${ship.current ? "THE SHIP YOU FLY" : esc(ship.location || "STORED")}${ship.ident ? ` · ${esc(ship.ident)}` : ""}</small>
      <h2>${esc(String(ship.label || "").trim() || ship.type || "No ship")}</h2>
      <p class="wk-shiptype">${esc(ship.type || "")}${ship.manufacturer ? ` · ${esc(ship.manufacturer)}` : ""}</p>
      ${ship.observed ? `<dl class="wk-value">
        <div><dt>JUMP (JOURNAL)</dt><dd>${ui.numeric(stats.jump_range, 2)} LY</dd></div>
        <div><dt>UNLADEN</dt><dd>${ui.numeric(stats.unladen_mass, 1)} T</dd></div>
        <div><dt>CARGO</dt><dd>${ui.numeric(stats.cargo)} T</dd></div>
        <div><dt>FUEL</dt><dd>${ui.numeric(stats.fuel)} T</dd></div></dl>`
        : `<p class="wk-note">No loadout recorded for this ship yet: fly it once and the journal fills this in.</p>`}
    </div>
    <div class="wk-grades">
      <header><span>ENGINEERED</span><b>${ui.numeric(done.length)} / ${ui.numeric(slots.length)}</b></header>
      <div class="wk-hist">${histogram.map((count, index) => `<div><i><b style="height:${count / peak * 100}%"></b></i><small>G${index + 1}</small><em>${count}</em></div>`).join("")}</div>
      <p>${ui.numeric(experimentals)} EXPERIMENTAL${experimentals === 1 ? "" : "S"} · ${ui.numeric(wishlist.plans)} PLAN${num(wishlist.plans) === 1 ? "" : "S"} · ${ui.numeric(wishlist.missing)} UNITS SHORT</p>
    </div>
    ${nextAction(data, ui)}
  </section>`;
}

function shipPanel(data, ui) {
  const esc = ui.escapeHtml;
  const ship = data.ship || {};
  const slots = engineeredSlots(data.slots || []);
  if (!ship.observed || !slots.length) {
    return `<p class="wk-empty">The journal has no loadout for ${esc(String(ship.label || "").trim() || "this ship")} yet. Board it once and its modules and engineering appear here.</p>`;
  }
  const groups = ["CORE INTERNALS", "OPTIONAL INTERNALS", "HARDPOINTS", "UTILITY MOUNTS"].map((group) => {
    const rows = slots.filter((row) => slotGroup(row) === group);
    if (!rows.length) return "";
    return `<section class="wk-shipgroup"><h4>${group}<b>${rows.filter((row) => row.engineeringBlueprint).length} / ${rows.length} ENGINEERED</b></h4>${rows.map((row) => {
      const quality = row.engineeringQualityKnown ? Math.round(num(row.engineeringQuality) * 100) : null;
      return `<div class="wk-mod${row.engineeringBlueprint ? " done" : ""}"${/Hardpoint/i.test(row.slot) ? ` data-wk-journal="${esc(row.slot)}"` : ""}>
        <small>${esc(slotLabel(row.slot))}</small>
        <b>${esc(moduleName(row))}${row.rating ? ` <em>${esc(row.rating)}</em>` : ""}</b>
        ${row.engineeringBlueprint ? `<span class="wk-mod-bp">${esc(row.blueprintName || row.engineeringBlueprint.replace(/_/g, " "))}${gradePips(num(row.engineeringGrade))}${quality === null ? "" : `<span class="wk-q" title="Roll progress at this grade">${bar(quality)}<em>${quality}%</em></span>`}</span>`
          : `<span class="wk-mod-bp none">${row.engineerable === false ? "NOT ENGINEERABLE" : "NOT ENGINEERED"}</span>`}
        ${row.experimentalEffect ? `<span class="wk-x">✦ ${esc(row.experimentalEffect)}</span>` : ""}
      </div>`;
    }).join("")}</section>`;
  }).join("");
  return `<div class="wk-panehead"><p>What the journal last recorded fitted to ${esc(String(ship.label || "").trim() || ship.type)}: every blueprint, its grade, how far the roll got, and any experimental.</p>
    <button data-ws-page="engineering" data-ws-op="export_copy" title="Copy this loadout for EDSY, Coriolis or Inara">COPY LOADOUT</button></div>
    <div class="wk-shipgroups">${groups}</div>`;
}

function plansPanel(data, ui) {
  const esc = ui.escapeHtml;
  const pins = data.pins || [];
  const wishlist = data.wishlist || {};
  const cards = pins.map((row) => `<article class="wk-plan ${row.craftable ? "ready" : "short"}">
      <header><span>${esc(row.type || "ENGINEERING")}</span><b>${row.craftable ? "READY" : "COLLECT"}</b></header>
      <h3>${esc(row.name)}</h3>
      <p>${esc(row.slot ? slotLabel(row.slot) : "Unbound plan")} · G${ui.numeric(row.current_grade)} → G${ui.numeric(row.grade)}${row.experimental ? ` · ✦ ${esc(row.experimental)}` : ""}</p>
      <div class="wk-planmats">${(row.materials || []).map((item) => `<span class="${item.missing ? "short" : "ok"}"><b>${ui.numeric(item.have)}/${ui.numeric(item.amount)}</b>${esc(item.name)}</span>`).join("") || "<small>Older plan: recipe from the original catalogue.</small>"}</div>
      <button class="danger-action" data-ws-page="engineering" data-ws-op="unpin" data-plan-id="${esc(row.id)}">REMOVE</button>
    </article>`).join("");
  const reserved = (data.materials || []).filter((row) => row.need > 0).sort((a, b) => b.missing - a.missing || a.name.localeCompare(b.name));
  const reserves = ui.workspaceTable([
    {label: "Material", render: (row) => `<b>${esc(row.name)}</b><small>${esc(row.category)} · G${ui.numeric(row.grade)}</small>`},
    {label: "Have", render: (row) => ui.numeric(row.have)}, {label: "Reserved", render: (row) => ui.numeric(row.need)},
    {label: "Short", render: (row) => `<b class="${row.missing ? "warn-text" : "ok-text"}">${ui.numeric(row.missing)}</b>`},
  ], reserved, "Nothing reserved yet.");
  return `<div class="wk-summary">
      <div><small>PLANS</small><b>${ui.numeric(wishlist.plans)}</b><span>${ui.numeric(wishlist.ready)} READY TO CRAFT</span></div>
      <div><small>RESERVED UNITS</small><b>${ui.numeric(wishlist.required)}</b><span>HELD FOR YOUR BUILDS</span></div>
      <div class="${num(wishlist.missing) ? "short" : "ok"}"><small>UNITS SHORT</small><b>${ui.numeric(wishlist.missing)}</b><span>${num(wishlist.missing) ? "TO COLLECT OR TRADE" : "ALL IN STOCK"}</span></div>
    </div>
    <section class="engineering-wishlist-grid wk-plans">${cards || `<p class="wk-empty">No plans yet. In the Build Planner, engineer a build and press SEND TO ENGINEERING: every blueprint becomes a plan here and its materials are reserved.</p>`}</section>
    <div class="wk-two">
      ${ui.workspaceCard("RESERVED MATERIALS", reserves, `${reserved.length} TYPES`)}
      ${ui.workspaceCard("BUILD PLANNER HANDOFF", `<p class="wk-note wk-cardnote">Loadouts, modules and EDSY or SLEF imports live in the Build Planner. SEND TO ENGINEERING there refreshes that build's plans here, so a build is never counted twice.</p><div class="workspace-actions"><button data-page="build-planner">OPEN BUILD PLANNER</button></div>`, "ONE SOURCE OF BUILDS")}
    </div>`;
}

function materialMatches(row) {
  const filter = view.filter;
  const passes = filter === "all" || (filter === "needed" && row.need > 0) || (filter === "missing" && row.missing > 0)
    || (filter === "full" && row.capacity && row.have >= row.capacity) || (filter === "empty" && !row.have);
  return passes && (!view.find || lower(`${row.name} ${row.category} ${(row.origins || []).join(" ")}`).includes(view.find));
}

function materialsPanel(data, ui) {
  const esc = ui.escapeHtml;
  const materials = data.materials || [];
  const blocks = MATERIAL_ORDER.map((category) => {
    const rows = materials.filter((row) => row.category === category);
    if (!rows.length) return "";
    const grades = [...new Set(rows.map((row) => num(row.grade)))].sort((a, b) => a - b);
    const held = rows.reduce((sum, row) => sum + num(row.have), 0);
    return `<section class="wk-matblock"><h4>${category.toUpperCase()}<b>${ui.numeric(held)} UNITS · ${rows.length} TYPES</b></h4>
      <div class="wk-matgrid" style="--grades:${grades.length}">${grades.map((grade) => `<div class="wk-matcol"><h5>GRADE ${grade}<small>${esc(rows.find((row) => num(row.grade) === grade)?.rarity || "")}</small></h5>${rows.filter((row) => num(row.grade) === grade)
        .sort((a, b) => a.name.localeCompare(b.name)).map((row) => {
          const percent = row.capacity ? row.have / row.capacity * 100 : 0;
          return `<div class="wk-mat${materialMatches(row) ? "" : " dim"}${row.missing ? " short" : row.need ? " held" : ""}${percent >= 100 ? " full" : ""}" title="${esc((row.origins || []).join(" · ") || "No source listed")}">
            <b>${esc(row.name)}</b><span>${ui.numeric(row.have)}<small>/${ui.numeric(row.capacity)}</small></span>${bar(percent)}
            ${row.need ? `<em>${row.missing ? `${ui.numeric(row.missing)} SHORT` : "RESERVED"} · ${ui.numeric(row.need)}</em>` : ""}
          </div>`;
        }).join("")}</div>`).join("")}</div></section>`;
  }).join("");
  return `<div class="wk-toolbar"><div class="wk-chips">${MATERIAL_FILTERS.map(([id, label]) => `<button type="button" class="wk-chip${view.filter === id ? " active" : ""}" data-engineering-material-filter="${id}">${label}</button>`).join("")}</div>
      <input id="engineering-search" value="${esc(view.find)}" placeholder="Find a material or where it comes from…" autocomplete="off"></div>
    <p class="wk-note">Matches stay lit; the rest dim so the locker keeps its shape. Hover a material for where it comes from.</p>
    ${blocks}`;
}

function engineersPanel(data, ui) {
  const esc = ui.escapeHtml;
  const engineers = data.engineers || [];
  if (!engineers.some((row) => row.name === view.engineer)) view.engineer = engineers[0]?.name || "";
  const person = engineers.find((row) => row.name === view.engineer) || {};
  const status = (row) => STATUS_ORDER.includes(lower(row.progress)) ? lower(row.progress) : "unknown";
  const card = (row) => `<button type="button" class="wk-engineer st-${status(row)}${row.name === view.engineer ? " active" : ""}${!view.find || lower(`${row.name} ${row.system} ${row.station}`).includes(view.find) ? "" : " dim"}" data-engineering-engineer="${esc(row.name)}">
      <img src="${esc(row.portrait)}" alt="" loading="lazy">
      <span><b>${esc(row.name)}</b><small>${esc(row.system)}</small></span>
      <em>${status(row) === "unlocked" && row.rank ? gradePips(num(row.rank)) : esc(String(row.progress || "Unknown").toUpperCase())}</em>
    </button>`;
  const sections = [["ship", "SHIP ENGINEERS"], ["pilot_equipment", "ON FOOT · ODYSSEY"]].map(([discipline, label]) => {
    const rows = engineers.filter((row) => (row.discipline || "ship") === discipline);
    return rows.length ? `<h4>${label}<b>${rows.filter((row) => status(row) === "unlocked").length} / ${rows.length} UNLOCKED</b></h4><div class="wk-engineers">${rows.map(card).join("")}</div>` : "";
  }).join("");
  const offers = {};
  for (const offer of person.offers || []) (offers[offer.type] ||= []).push(offer);
  const detail = person.name ? `<article class="wk-person st-${status(person)}">
      <header><img src="${esc(person.portrait)}" alt=""><div><small>${esc(String(person.progress || "UNKNOWN").toUpperCase())}${person.rank ? ` · GRADE ${ui.numeric(person.rank)}` : ""}</small><h3>${esc(person.name)}</h3><p>${esc(person.station)} · ${esc(person.system)}</p></div></header>
      <div class="workspace-actions"><button data-ws-page="engineering" data-ws-op="copy_system" data-system="${esc(person.system)}">COPY ${esc(person.system).toUpperCase()}</button></div>
      <ol class="wk-steps">${(person.steps || []).map((step) => `<li class="${step.done ? "done" : ""}"><b>${esc(step.label)}</b><span>${esc(step.detail)}</span></li>`).join("")}</ol>
      ${person.prerequisite ? `<p class="wk-note">Introduced by ${esc(person.prerequisite)}.</p>` : ""}
      <h4>WORKSHOP<b>${ui.numeric((person.offers || []).length)} BLUEPRINTS</b></h4>
      <div class="wk-offers">${Object.entries(offers).map(([type, rows]) => `<div><small>${esc(type)}</small>${rows.map((row) => `<span>${esc(row.name)} <b>G${ui.numeric(row.grade)}</b></span>`).join("")}</div>`).join("") || `<p class="wk-empty">No ship blueprints listed.</p>`}</div>
    </article>` : "";
  return `<div class="wk-toolbar"><input id="engineering-search" value="${esc(view.find)}" placeholder="Find an engineer or a system…" autocomplete="off"></div>
    <div class="wk-engineerlayout"><div>${sections}</div>${detail}</div>`;
}

function blueprintsPanel(data, ui) {
  const esc = ui.escapeHtml;
  const catalogue = data.catalogue || [];
  const stock = Object.fromEntries((data.materials || []).map((row) => [row.key, num(row.have)]));
  const engineers = Object.fromEntries((data.engineers || []).map((row) => [row.name, row]));
  const types = [...new Set(catalogue.map((row) => row.type))].sort((a, b) => a.localeCompare(b));
  const matching = types.filter((type) => !view.find || lower(type).includes(view.find)
    || catalogue.some((row) => row.type === type && lower(row.name).includes(view.find)));
  if (!types.includes(view.type)) view.type = types.includes("Frame Shift Drive") ? "Frame Shift Drive" : types[0] || "";
  const recipe = (ingredients) => {
    const rolls = ingredients.length ? Math.min(...ingredients.map((item) => Math.floor(num(stock[item.key]) / Math.max(1, num(item.amount))))) : 0;
    return {rolls, rows: ingredients.map((item) => `<span class="${num(stock[item.key]) >= num(item.amount) ? "ok" : "short"}"><b>${ui.numeric(stock[item.key])}/${ui.numeric(item.amount)}</b>${esc(item.name)} <small>G${ui.numeric(item.grade)}</small></span>`).join("")};
  };
  const effects = (rows) => rows.map((row) => `<span class="${row.good ? "good" : "bad"}">${esc(row.property)} <b>${esc(row.effect)}</b></span>`).join("");
  const cards = catalogue.filter((row) => row.type === view.type && (!view.find || lower(row.type).includes(view.find) || lower(row.name).includes(view.find))).map((row) => {
    const {rolls, rows} = recipe(row.ingredients || []);
    const who = (row.engineers || []).map((name) => {
      const person = engineers[name] || {};
      const grade = (person.offers || []).find((offer) => offer.type === row.type && offer.name === row.name)?.grade;
      return `<span class="wk-who st-${lower(person.progress) === "unlocked" ? "unlocked" : "locked"}" title="${esc(person.system || "")} · ${esc(person.progress || "Unknown")}">${esc(name)}${grade ? ` <b>G${grade}</b>` : ""}</span>`;
    }).join("");
    return `<article class="wk-blueprint">
      <header><h3>${esc(row.name)}</h3><b>MAX G${ui.numeric(row.max_grade)}</b></header>
      <div class="wk-effects">${effects(row.effects || [])}</div>
      <h5>G${ui.numeric(row.max_grade)} ROLL<em class="${rolls ? "ok" : "short"}">${rolls ? `${ui.numeric(rolls)} ROLL${rolls === 1 ? "" : "S"} IN STOCK` : "SHORT"}</em></h5>
      <div class="wk-recipe">${rows}</div>
      <h5>ENGINEERS</h5><div class="wk-whos">${who || "<small>Tech Broker or special source</small>"}</div>
    </article>`;
  }).join("");
  const experimentals = (data.experimentals || []).filter((row) => (row.module_types || []).includes(view.type) || row.type === view.type).map((row) => {
    const {rolls, rows} = recipe(row.ingredients || []);
    return `<article class="wk-blueprint x"><header><h3>✦ ${esc(row.name)}</h3><b class="${rolls ? "ok" : "short"}">${rolls ? `${ui.numeric(rolls)} IN STOCK` : "SHORT"}</b></header>
      <div class="wk-effects">${effects(row.effects || [])}</div><div class="wk-recipe">${rows}</div></article>`;
  }).join("");
  return `<div class="wk-toolbar"><input id="engineering-search" value="${esc(view.find)}" placeholder="Find a module or a blueprint…" autocomplete="off"></div>
    <div class="wk-bplayout">
      <nav class="wk-types">${matching.map((type) => `<button type="button" class="wk-type${type === view.type ? " active" : ""}" data-wk-type="${esc(type)}">${esc(type)}<b>${catalogue.filter((row) => row.type === type).length}</b></button>`).join("") || `<p class="wk-empty">No module matches.</p>`}</nav>
      <div class="wk-bpcards">
        <p class="wk-note">Recipes are one roll at the top grade; stock is your locker now. Lit engineers are unlocked.</p>
        ${cards || `<p class="wk-empty">No blueprint matches.</p>`}
        ${experimentals ? `<h4 class="wk-span">EXPERIMENTAL EFFECTS</h4>${experimentals}` : ""}
      </div>
    </div>`;
}

function sourcesPanel(data, ui) {
  const esc = ui.escapeHtml;
  const missing = (data.materials || []).filter((row) => row.missing).sort((a, b) => b.missing - a.missing);
  const sources = ui.workspaceTable([
    {label: "Material", render: (row) => `<b>${esc(row.name)}</b><small>${esc(row.category)} · G${ui.numeric(row.grade)}</small>`},
    {label: "Short", render: (row) => `<b class="warn-text">${ui.numeric(row.missing)}</b>`},
    {label: "Where it comes from", render: (row) => esc((row.origins || []).join(" · ") || "No source in the catalogue")},
  ], missing, "Nothing is short for your plans.");
  const traders = ui.workspaceTable([
    {label: "Trades", key: "category"},
    {label: "System", render: (row) => `<b>${esc(row.system)}</b><small>${esc(row.station)}</small>`},
    {label: "Distance", render: (row) => row.distance == null ? "—" : `${ui.numeric(row.distance, 1)} LY`},
    {label: "From star", render: (row) => row.distance_ls == null ? "—" : `${ui.numeric(row.distance_ls)} LS`},
    {label: "Pad", key: "pad"},
    {label: "", render: (row) => `<button data-ws-page="engineering" data-ws-op="copy_system" data-system="${esc(row.system)}">COPY</button>`},
  ], data.material_traders || [], "Nearest traders appear once the journal gives your position.");
  return `<div class="wk-two">${ui.workspaceCard("SHORT FOR YOUR PLANS", sources, `${missing.length} TYPES`)}${ui.workspaceCard("NEAREST MATERIAL TRADERS", traders, "RAW · MANUFACTURED · ENCODED")}</div>
    <div class="workspace-actions"><button data-page="planet-materials">OPEN PLANET MATERIALS</button></div>`;
}

function brokersPanel(data, ui) {
  const esc = ui.escapeHtml;
  const destinations = data.tech_broker_guidance?.recommended_destinations || {};
  const rows = [...(data.tech_brokers || [])].sort((a, b) => Number(b.ready) - Number(a.ready) || a.name.localeCompare(b.name));
  const cards = rows.map((row) => `<article class="wk-broker${row.ready ? " ready" : ""}"><header><span>${esc(row.broker).toUpperCase()}</span><b>${row.ready ? "READY" : `${row.materials.filter((item) => item.have >= item.need).length} / ${row.materials.length}`}</b></header>
      <h3>${esc(row.name)}</h3>${(row.materials || []).map((item) => `<p><span>${esc(item.name)}</span>${bar(item.need ? item.have / item.need * 100 : 0, item.have >= item.need ? "ok" : "")}<b>${ui.numeric(item.have)}/${ui.numeric(item.need)}</b></p>`).join("")}</article>`).join("");
  return `<div class="wk-summary">${Object.entries(destinations).map(([kind, row]) => `<div><small>${esc(kind).toUpperCase()} BROKER</small><b>${esc(row.system)}</b><span>${esc(row.station)}</span>
      <button data-ws-page="engineering" data-ws-op="copy_system" data-system="${esc(row.system)}">COPY</button></div>`).join("")}
      <div class="ok"><small>READY TO UNLOCK</small><b>${rows.filter((row) => row.ready).length}</b><span>OF ${rows.length} RECIPES</span></div></div>
    <section class="wk-brokers">${cards || `<p class="wk-empty">The Tech Broker catalogue is unavailable.</p>`}</section>`;
}

function odysseyPanel(data, ui) {
  const esc = ui.escapeHtml;
  const odyssey = data.odyssey || {};
  const goals = (odyssey.goals || []).map((row) => `<article class="wk-plan ${odyssey.complete ? "ready" : "short"}"><header><span>SUIT & WEAPON WORKSHOP</span><b>×${ui.numeric(row.quantity)}</b></header><h3>${esc(row.name)}</h3>
      <button class="danger-action" data-ws-page="engineering" data-ws-op="odyssey_unpin" data-name="${esc(row.name)}">REMOVE</button></article>`).join("");
  return `<div class="wk-summary">
      <div><small>GOALS</small><b>${ui.numeric((odyssey.goals || []).length)}</b><span>SUITS · PERSONAL WEAPONS</span></div>
      <div><small>UNITS NEEDED</small><b>${ui.numeric(odyssey.required)}</b><span>FROM THE SHIP LOCKER</span></div>
      <div class="${num(odyssey.missing) ? "short" : "ok"}"><small>UNITS SHORT</small><b>${ui.numeric(odyssey.missing)}</b><span>${odyssey.complete ? "ALL GOALS READY" : "TO COLLECT"}</span></div>
    </div>
    <section class="wk-odyssey-add"><label>UPGRADE<select id="odyssey-blueprint">${(odyssey.catalogue || []).map((name) => `<option>${esc(name)}</option>`).join("")}</select></label>
      <label>HOW MANY<input id="odyssey-quantity" type="number" min="1" max="99" value="1"></label><button class="primary" data-ws-page="engineering" data-ws-op="odyssey_pin">ADD GOAL</button></section>
    <section class="engineering-wishlist-grid wk-plans">${goals || `<p class="wk-empty">No suit or weapon goals yet.</p>`}</section>
    ${ui.workspaceCard("SHOPPING LIST", ui.workspaceTable([
      {label: "Material", key: "name"}, {label: "Have", render: (row) => ui.numeric(row.have)}, {label: "Need", render: (row) => ui.numeric(row.need)},
      {label: "Short", render: (row) => `<b class="${row.deficit ? "warn-text" : "ok-text"}">${ui.numeric(row.deficit)}</b>`},
    ], odyssey.materials || [], "Add a goal to see what it takes from your locker."), `${ui.numeric(odyssey.missing)} SHORT`)}`;
}

export function renderEngineering(data, ui) {
  const root = ui.byId("engineering-workspace");
  if (!root) return;
  engineeringData = data;
  const counts = {
    plans: (data.pins || []).length,
    engineers: `${(data.engineers || []).filter((row) => lower(row.progress) === "unlocked").length}/${(data.engineers || []).length}`,
    brokers: (data.tech_brokers || []).filter((row) => row.ready).length,
    odyssey: (data.odyssey?.goals || []).length,
  };
  const panels = {ship: shipPanel, plans: plansPanel, materials: materialsPanel, engineers: engineersPanel,
    blueprints: blueprintsPanel, sources: sourcesPanel, brokers: brokersPanel, odyssey: odysseyPanel};
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="wk wk-eng">
    ${fleetRail(data, ui)}
    ${engineeringHero(data, ui)}
    <nav class="wk-tabs">${ENGINEERING_TABS.map(([id, label]) => `<button type="button" class="wk-tab${view.tab === id ? " active" : ""}" data-engineering-view="${id}">${label}${counts[id] ? `<b>${counts[id]}</b>` : ""}</button>`).join("")}</nav>
    <div class="wk-pane wk-pane-${view.tab}">${(panels[view.tab] || shipPanel)(data, ui)}</div>
    <footer class="wk-source">${ui.escapeHtml(data.source || "")} · MATERIALS FROM THE JOURNAL · PLANS SAVED TO THIS PROFILE</footer>
  </div>`;
  paintHulls(root);
}

// --- Events -----------------------------------------------------------------
function rerender(which, ui) {
  if (which === "planner" && plannerData) renderBuildPlanner(plannerData, ui);
  if (which === "engineering" && engineeringData) renderEngineering(engineeringData, ui);
}

function refocus(ui, id) {
  const input = ui.byId(id);
  if (!input) return;
  input.focus({preventScroll: true});
  input.setSelectionRange(input.value.length, input.value.length);
}

// Clicks the workshop owns; true when handled.
export function handleWorkshopClick(event, ui) {
  const target = event.target;
  const build = target.closest("[data-wk-build]");
  if (build) {
    const id = build.dataset.wkBuild;
    if (id !== plannerData?.selected?.id) {
      ui.command("workspace", {page: "build-planner", operation: "select", build_id: id})
        .then((accepted) => { if (!accepted) ui.showToast("That build is unavailable"); });
    }
    return true;
  }
  const drawer = target.closest("[data-wk-drawer]");
  if (drawer) {
    view.drawer = view.drawer === drawer.dataset.wkDrawer ? "" : drawer.dataset.wkDrawer;
    rerender("planner", ui);
    if (view.drawer === "new") ui.byId("bp-new-name")?.focus({preventScroll: true});
    if (view.drawer === "import") ui.byId("bp-import")?.focus({preventScroll: true});
    return true;
  }
  if (target.closest("[data-bp-focus='new']")) {
    view.drawer = "new";
    rerender("planner", ui);
    const panel = ui.byId("bp-new-build");
    panel?.scrollIntoView({behavior: "smooth", block: "center"});
    panel?.classList.remove("attention");
    void panel?.offsetWidth;
    panel?.classList.add("attention");
    window.setTimeout(() => panel?.classList.remove("attention"), 900);
    ui.byId("bp-new-name")?.focus({preventScroll: true});
    return true;
  }
  const pick = target.closest("[data-wk-hullpick]");
  if (pick) {
    // Local: the name typed so far stays put.
    view.hull = pick.dataset.wkHullpick;
    const input = ui.byId("bp-new-ship");
    if (input) input.value = view.hull;
    pick.parentElement.querySelectorAll(".wk-hullpick").forEach((node) => node.classList.toggle("active", node === pick));
    return true;
  }
  const slot = target.closest("[data-bp-slot]");
  if (slot) {
    if (view.slot !== slot.dataset.bpSlot) view.search = "";
    view.slot = slot.dataset.bpSlot;
    rerender("planner", ui);
    return true;
  }
  const dockTab = target.closest("[data-wk-dock]");
  if (dockTab) {
    if (dockTab.disabled) return true;
    view.dock = dockTab.dataset.wkDock;
    remember("voidcompass.workshop.dock", view.dock);
    rerender("planner", ui);
    return true;
  }
  const moduleButton = target.closest("[data-bp-module]");
  if (moduleButton) {
    if (moduleButton.disabled) return true;
    ui.command("workspace", {page: "build-planner", operation: "set_module", slot: view.slot, module_id: moduleButton.dataset.bpModule})
      .then((accepted) => ui.showToast(accepted ? (moduleButton.dataset.bpModule === "0" ? "Module removed" : "Module fitted") : "That module cannot be fitted in this slot"));
    return true;
  }
  const segment = target.closest(".wk-seg .wk-segbtn");
  if (segment) {
    if (segment.disabled) return true;
    const group = segment.closest(".wk-seg");
    group.querySelectorAll(".wk-segbtn").forEach((node) => node.classList.toggle("active", node === segment));
    const input = ui.byId(group.dataset.wkSeg);
    if (input) input.value = segment.dataset.value;
    return true;
  }
  const pip = target.closest("[data-wk-pip], [data-wk-pip-reset]");
  if (pip) {
    const selected = plannerData?.selected;
    if (pip.disabled || !selected?.editable) return true;
    const current = view.pipsBuild === selected.id && view.pips ? view.pips : {sys: num(selected.pips?.sys, 4), eng: num(selected.pips?.eng, 4), wep: num(selected.pips?.wep, 4)};
    let next = {sys: 4, eng: 4, wep: 4};
    if (pip.dataset.wkPip) {
      const axis = pip.dataset.wkPip;
      const level = num(pip.dataset.level);
      // Clicking the top lit pip again drops that half-pip.
      next = setPip(current, axis, current[axis] === level ? level - 1 : level);
    }
    if (AXES.every((axis) => next[axis] === current[axis])) return true;
    view.pips = next;
    view.pipsBuild = selected.id;
    rerender("planner", ui);
    sendLoad(ui, next).then((accepted) => { if (!accepted) ui.showToast("The distributor could not be set"); });
    return true;
  }
  const tab = target.closest("[data-engineering-view]");
  if (tab) {
    view.tab = tab.dataset.engineeringView;
    view.find = "";
    remember("voidcompass.workshop.engineering", view.tab);
    rerender("engineering", ui);
    return true;
  }
  const engineer = target.closest("[data-engineering-engineer]");
  if (engineer) {
    view.engineer = engineer.dataset.engineeringEngineer;
    rerender("engineering", ui);
    return true;
  }
  const filter = target.closest("[data-engineering-material-filter]");
  if (filter) {
    view.filter = filter.dataset.engineeringMaterialFilter;
    rerender("engineering", ui);
    return true;
  }
  const type = target.closest("[data-wk-type]");
  if (type) {
    view.type = type.dataset.wkType;
    rerender("engineering", ui);
    return true;
  }
  return false;
}

export function handleWorkshopInput(event, ui) {
  const target = event.target;
  if (target.id === "bp-search") {
    view.search = target.value;
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => { rerender("planner", ui); refocus(ui, "bp-search"); }, 120);
    return true;
  }
  if (target.id === "bp-roll") {
    const output = ui.byId("bp-roll-value");
    if (output) output.textContent = `${target.value}%`;
    return true;
  }
  if (target.id === "engineering-search") {
    const value = lower(target.value.trim());
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => { view.find = value; rerender("engineering", ui); refocus(ui, "engineering-search"); }, 160);
    return true;
  }
  return false;
}

export function handleWorkshopChange(event, ui) {
  const target = event.target;
  if (target.id === "bp-compare-select") {
    ui.command("workspace", {page: "build-planner", operation: "compare", build_id: target.value})
      .then((accepted) => ui.showToast(accepted ? (target.value ? "Comparing builds" : "Comparison cleared") : "The comparison could not be changed"));
    return true;
  }
  if (target.matches("[data-wk-load]")) {
    const selected = plannerData?.selected;
    if (!selected?.editable) return true;
    const pips = view.pipsBuild === selected.id && view.pips ? view.pips : {sys: num(selected.pips?.sys, 4), eng: num(selected.pips?.eng, 4), wep: num(selected.pips?.wep, 4)};
    sendLoad(ui, pips).then((accepted) => { if (!accepted) ui.showToast("The load could not be set"); });
    return true;
  }
  return false;
}

// What the configure_slot button sends: the chosen slot and the dock's form.
export function engineeringPayload(ui) {
  return {
    slot: view.slot, blueprint: ui.byId("bp-blueprint")?.value || "",
    grade: ui.byId("bp-grade")?.value || 0, roll: num(ui.byId("bp-roll")?.value, 100) / 100,
    experimental: ui.byId("bp-experimental")?.value || "", priority: ui.byId("bp-priority")?.value || 1,
    enabled: Boolean(ui.byId("bp-enabled")?.checked),
  };
}

// A profile switch starts the workshop afresh.
export function resetWorkshop() {
  plannerData = null;
  engineeringData = null;
  Object.assign(view, {slot: "", slotBuild: "", search: "", drawer: "", hull: "", pips: null, pipsBuild: "", engineer: "", filter: "all", find: "", type: ""});
}
