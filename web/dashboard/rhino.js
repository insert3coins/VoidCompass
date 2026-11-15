// The Rhino page: surface mining round one big map. The rail down the left
// has the keys as buttons (in the order you work a signal), the deposit you
// picked to set its details, and the deposits on this planet; the map has
// the figures over it and the rig radar's word under it. SITES is the mining
// locations you've saved and every deposit you've marked anywhere; WHERE TO
// LAND is this system's Rhino ground.
// The map is /assets/rhino-draw.js, the same drawing as the Rhino Map overlay.

const VIEWS = [["map", "MAP"], ["sites", "SITES"], ["land", "WHERE TO LAND"]];
const n = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
const whole = (value) => Math.round(n(value)).toLocaleString("en-GB");
const distance = (metres) => n(metres) >= 1000 ? `${(n(metres) / 1000).toFixed(n(metres) >= 10000 ? 0 : 1)} km` : `${Math.round(n(metres))} m`;
const POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const compass = (bearing) => POINTS[Math.floor(((n(bearing) + 22.5) % 360) / 45)];
const way = (row) => `${distance(row.distance)} ${compass(row.bearing)}`;
const money = (value) => n(value) >= 1e6 ? `${(n(value) / 1e6).toFixed(2)}M` : n(value) >= 1e3 ? `${Math.round(n(value) / 1e3)}K` : whole(value);
const DOING = {rhino: "In the Rhino", srv: "In an SRV", foot: "On foot", docked: "Docked", field: "In a ring", planet: "On a planet", flight: "In flight"};

let view = "map";
let last = null;
let lastUi = null;
let selected = null;
let filter = "";
let renaming = null;
// The deposit being edited on SITES (from anywhere, in the Rhino or not).
let sitesEditing = null;
// The saved site whose runs are listed.
let runsOpen = null;
const when = (seconds) => n(seconds) ? new Date(n(seconds) * 1000).toLocaleDateString("en-GB", {day: "numeric", month: "short", year: "numeric"}) : "—";
let confirming = {key: "", until: 0};
// SITES: the deposit being edited, and the table it was opened from (it opens
// under that row, as a saved site's runs do).
let sitesEditingIn = "all";
let drawnParts = {};
// The map's own view, apart from the Rhino Map overlay's range (its hotkey
// never touches this one). It opens fitted to the mining location being
// worked: its deposits, rigs, rig plan, the survey area and you, with room
// round them. The fit holds still while you drive about inside it; it only
// widens when something lands outside it. The wheel (or + and -) sets the
// radius in metres, 100 m at the closest, and it stays where you put it.
// Dragging pans. RECENTRE, a double-click or arriving somewhere new go back
// to the fit.
const FIT = {floor: 250, empty: 2500, cap: 15000, reach: 8000, room: 1.3, closest: 100, widest: 50000};
let mapUp = "north";
let chosenHalf = null;
let fitted = null;
let pan = null;
let drag = null;
let lastFrame = null;

function send(ui, operation, extra = {}) {
  return ui.command("workspace", {page: "rhino", operation, ...extra});
}

function panel(title, body, {note = "", cls = ""} = {}) {
  return `<section class="rh-panel${cls ? ` ${cls}` : ""}"><header><h4>${title}</h4>${note ? `<span>${note}</span>` : ""}</header>${body}</section>`;
}

const empty = (text) => `<p class="rh-dim">${text}</p>`;
const key = (data, action) => data.keys?.[action] ? `<kbd>${lastUi.escapeHtml(data.keys[action])}</kbd>` : "";

function button(data, op, label, action = "", extra = {}, cls = "") {
  const attrs = Object.entries(extra).map(([k, v]) => ` data-${k}="${lastUi.escapeHtml(String(v))}"`).join("");
  return `<button type="button" class="rh-key${cls ? ` ${cls}` : ""}" data-rhino-op="${op}"${attrs}><b>${label}</b>${action ? key(data, action) : ""}</button>`;
}

function confirmButton(id, label, op, extra = {}) {
  const armed = confirming.key === id && Date.now() < confirming.until;
  const attrs = Object.entries(extra).map(([k, v]) => ` data-${k}="${lastUi.escapeHtml(String(v))}"`).join("");
  return `<button type="button" class="rh-key rh-danger${armed ? " armed" : ""}" data-rhino-op="${op}" data-confirm-key="${lastUi.escapeHtml(id)}"${attrs}><b>${armed ? "SURE? AGAIN" : label}</b></button>`;
}

function holdBar(hold, esc) {
  const capacity = Math.max(0, n(hold.capacity)), used = n(hold.used);
  const share = capacity ? Math.min(1, used / capacity) : 0;
  const state = hold.partial ? "partial" : share >= 1 ? "full" : share >= .9 ? "nearly" : "";
  return `<div class="rh-hold ${state}"><span>${esc(hold.name)}</span><i><b style="width:${(share * 100).toFixed(1)}%"></b></i><em>${hold.partial ? "+" : ""}${whole(used)} / ${whole(capacity)} t</em></div>`;
}

// -- the status strip --------------------------------------------------------------
function statusStrip(data, esc) {
  const where = data.where || {};
  const holds = (data.holds || []).map((hold) => `<span class="rh-mini"><em>${esc(hold.name)}</em>${whole(hold.used)}/${whole(hold.capacity)} t</span>`).join("");
  const run = data.run;
  return `<div class="rh-status">
    <div><b>WHERE</b><span>${esc(data.system || "Waiting for your location")}${data.body ? ` · ${esc(data.body)}` : ""}</span></div>
    <div><b>SIGNAL</b><span>${data.signal != null ? `Mining location ${esc(data.signal)}` : n(data.signals) ? `${whole(data.signals)} on this body` : "—"}</span></div>
    <div><b>DOING</b><span>${esc(DOING[where.mode] || "—")}</span></div>
    <div><b>HOLDS</b><span>${holds || "—"}</span></div>
    <div><b>RUN</b><span>${run ? `${run.active ? "Going" : "Last"} · ${whole(run.refined_t)} t refined${n(run.tons_per_hour) ? ` · ${n(run.tons_per_hour).toFixed(1)} t an hour` : ""}` : "None going"}</span></div>
  </div>`;
}

// -- MAP: the rail -------------------------------------------------------------------
// Which run this was at the site, its rate, and the best one before it.
function historyWords(card) {
  const history = card.history;
  if (!history) return "";
  const nth = (k) => `${k}${["th", "st", "nd", "rd"][(k % 100 >= 11 && k % 100 <= 13) ? 0 : Math.min(k % 10, 4) % 4] || "th"}`;
  const rate = card.tph ? `${whole(card.tph)} t/h` : "";
  const best = history.best_tph ? ` · best before: ${whole(history.best_tph)} t/h` : "";
  return `Your ${nth(history.run)} run here${rate ? ` · ${rate}` : ""}${best}`;
}

// Back in the ship after a Rhino run: what it gave, what's still out, what's next.
function aboardPanel(data, esc) {
  const card = data.aboard;
  if (!card) return "";
  const taken = (card.taken || []).map((row) => `<li><b>${esc(row.commodity)}</b><em>${whole(row.t)} t</em></li>`).join("");
  const out = (card.out || []).map((rig) => `<p class="rh-out">RIG ${rig.slot} STILL OUT · ${distance(rig.distance_m)}${rig.commodity ? ` · ${esc(rig.commodity)}` : ""}</p>`).join("");
  return panel("BACK ABOARD", `<div class="rh-aboard">
      <div><span>REFINED</span><b>${whole(card.refined_t)} t</b></div><div><span>RIGS OUT</span><b>${(card.out || []).length || "None"}</b></div>
      ${card.minutes != null ? `<div><span>RUN</span><b>${whole(card.minutes)} min</b></div>` : ""}
    </div>${taken ? `<ul class="rh-taken">${taken}</ul>` : ""}${out}
    ${card.site ? `<p class="rh-sub">Saved as <b>${esc(card.site.name)}</b>${card.site.swept != null ? ` · ${Math.floor(n(card.site.swept))}% swept` : ""}</p>` : ""}
    ${historyWords(card) ? `<p class="rh-sub">${historyWords(card)}</p>` : ""}
    <p class="rh-dim">Next: ${esc(card.next)}</p>`, {cls: "rh-aboard-panel"});
}

function keysPanel(data) {
  const rigs = new Set(((data.rigs || {}).rigs || []).map((rig) => rig.slot));
  const plan = data.facts?.plan;
  const rigButtons = [1, 2, 3, 4, 5, 6].map((slot) => button(data, "rig", rigs.has(slot) ? `RIG ${slot} UP` : `RIG ${slot} DOWN`, `rig_${slot}`, {slot}, rigs.has(slot) ? "down" : "")).join("");
  return panel("KEYS", `<div class="rh-keys">
      ${button(data, "survey_centre", "SURVEY CENTRE", "rhino_survey_centre")}
      ${button(data, "survey_edge", "SURVEY EDGE", "rhino_survey_edge")}
      ${button(data, "deposit_mark", "MARK DEPOSIT", "rhino_deposit_mark", {}, "primary")}
      ${button(data, "trace", data.tracing ? "CLOSE TRACE" : "TRACE EDGE", "rhino_trace", {}, data.tracing ? "live" : "")}
      ${button(data, "circle", "PLANNING CIRCLE", "rhino_circle")}
      ${plan ? button(data, "trace_forget", "FORGET PLAN") : ""}
    </div>
    ${siteForm(data)}
    <div class="rh-keys rigs">${rigButtons}</div>
    <div class="rh-keys">${data.facts?.survey ? confirmButton("survey", "CLEAR SURVEY", "survey_clear") : ""}${rigs.size ? confirmButton("rigs", "FORGET RIGS", "forget_rigs") : ""}</div>
    <p class="rh-dim">The keys work in the game too (Settings › Hotkeys › Rhino). A site with a survey or marked deposits is saved as you work it. Rigs drop ${whole(data.settings?.drop_m)} m behind the cockpit and want ${whole(data.settings?.spacing_m)} m between them.</p>`, {cls: "rh-keys-panel"});
}

// Save the site here, named as you like: its name so far is filled in to
// type over, and a name you give stays as the site's kept up to date.
function siteForm(data) {
  const esc = lastUi.escapeHtml, here = data.site_here;
  return `<form class="rh-site-form" data-rhino-form="site-save">
      <div class="rh-site-head"><span>SITE</span><em class="${here ? "saved" : ""}">${here ? `SAVED · ${when(here.updated)}` : "NOT SAVED YET"}</em></div>
      <div class="rh-site-row">
        <input name="name" value="${esc(here?.name || "")}" maxlength="80" placeholder="Name it (optional)" aria-label="Site name">
        <button type="submit" class="rh-key${here ? " down" : ""}"><b>${here ? "SAVE NAME" : "SAVE THIS SITE"}</b>${key(data, "rhino_site_save")}</button>
      </div>
    </form>`;
}

// Where the planet compass is pointing, and a way to stop it. It clears by
// itself when you reach a deposit or site the page sent you to.
function targetBar(data, esc) {
  const target = data.target;
  if (!target) return "";
  const where = target.distance != null ? `${distance(target.distance)} ${compass(target.bearing)}` : target.body ? `on ${esc(target.body)}` : "";
  return `<div class="rh-target"><span>TARGET</span><b>${esc(target.label)}</b>${where ? `<em>${where}</em>` : ""}
    <button type="button" data-rhino-op="target_clear">CLEAR TARGET</button></div>`;
}

// Back aboard: the rig buttons alone, to put a rig right by hand (the keys
// only work from the SRV), and FORGET RIGS.
function rigsPanel(data) {
  const rigs = new Set(((data.rigs || {}).rigs || []).map((rig) => rig.slot));
  const rigButtons = [1, 2, 3, 4, 5, 6].map((slot) => button(data, "rig", rigs.has(slot) ? `RIG ${slot} UP` : `RIG ${slot} DOWN`, "", {slot}, rigs.has(slot) ? "down" : "")).join("");
  return panel("RIGS", `<div class="rh-keys rigs">${rigButtons}</div>
    ${rigs.size ? `<div class="rh-keys">${confirmButton("rigs", "FORGET RIGS", "forget_rigs")}</div>` : ""}
    <p class="rh-dim">From the ship, the buttons put a rig right by hand; the rig keys work from the Rhino.</p>`);
}

function rail(data, esc) {
  if (data.aboard) {
    return `${aboardPanel(data, esc)}${panel("SITE", siteForm(data))}${rigsPanel(data)}${depositEditor(data, esc)}${depositsList(data, esc)}`;
  }
  return `${keysPanel(data)}${depositEditor(data, esc)}${depositsList(data, esc)}`;
}

// The commodity box: the Rhino's surface commodities first (less the ones
// hidden in Settings), then every other one.
function commodityOptions(data, esc) {
  const list = data.catalogue || {};
  const rhino = Array.isArray(list) ? list : list.rhino || [];
  const found = Array.isArray(list) ? [] : list.found || [];
  const others = Array.isArray(list) ? [] : list.others || [];
  return [...rhino.map((name) => `<option value="${esc(name)}" label="RHINO">`), ...found.map((name) => `<option value="${esc(name)}" label="YOURS">`),
    ...others.map((name) => `<option value="${esc(name)}" label="other">`)].join("");
}

function depositEditor(data, esc, chosen = null) {
  const rows = data.deposits || [];
  const row = chosen || rows.find((item) => String(item.id) === String(selected)) || rows[0];
  if (!row) return panel("DEPOSIT", empty("Drive onto a deposit and press MARK DEPOSIT: it goes on the map with what's being refined round it. Set its rigs, amount and density here."));
  const choices = (list, value, blank) => `${blank ? `<option value="">${blank}</option>` : ""}${list.map((item) => `<option${String(item) === String(value) ? " selected" : ""}>${esc(item)}</option>`).join("")}`;
  const rigsChoice = Array.from({length: 13}, (_, index) => `<option value="${index}"${index === n(row.rigs) ? " selected" : ""}>${index || "—"}</option>`).join("");
  const material = String(row.materials || "").split(",")[0].trim();
  const where = row.distance != null ? `${way(row)}${row.n ? ` · #${row.n} to drive` : ""}` : "";
  const timeline = row.depleted && row.regrowth?.text ? `<p class="rh-regrowth${row.regrowth.due ? " due" : ""}">${esc(row.regrowth.text.toUpperCase())}</p>` : "";
  const title = `${row.depleted ? "DEPOSIT · MINED OUT" : "DEPOSIT"}${chosen ? ` · ${esc(String(row.body || "").toUpperCase())}` : ""}`;
  return panel(title, `${timeline}<form class="rh-form" data-rhino-form="deposit" data-id="${esc(row.id)}">
      <label><span>COMMODITY</span><input name="materials" list="rh-commodities" value="${esc(material === "Unknown" ? "" : material)}" placeholder="What it holds"></label>
      <label><span>RIGS IT TAKES</span><select name="rigs">${rigsChoice}</select></label>
      <label><span>AMOUNT</span><select name="amount">${choices(data.amounts || [], row.amount, "—")}</select></label>
      <label><span>DENSITY</span><select name="density">${choices(data.densities || [], row.density, "—")}</select></label>
      <label class="wide"><span>NOTES</span><input name="notes" value="${esc(row.notes || "")}" placeholder="Anything to remember"></label>
      <datalist id="rh-commodities">${commodityOptions(data, esc)}</datalist>
      <div class="rh-actions wide"><button type="submit" class="primary">SAVE</button>
        ${row.depleted ? `<button type="button" data-rhino-op="deposit_mined_out" data-id="${esc(row.id)}" title="You looked and it's still empty">STILL DEPLETED</button><button type="button" data-rhino-op="deposit_regrown" data-id="${esc(row.id)}" title="It has grown back">REGROWN</button>`
          : `<button type="button" data-rhino-op="deposit_mined_out" data-id="${esc(row.id)}">MINED OUT</button>`}
        <button type="button" data-rhino-op="deposit_navigate" data-id="${esc(row.id)}">GO THERE</button>
        ${confirmButton(`del-${row.id}`, "DELETE", "deposit_delete", {id: row.id})}
        ${chosen ? `<button type="button" data-rhino-op="sites_edit_done">DONE</button>` : ""}</div>
    </form>
    <p class="rh-dim">${esc(where)}${row.signal != null ? ` · signal ${esc(row.signal)}` : ""}${row.estimate ? ` · ${esc(row.estimate)}` : ""}</p>`);
}

function depositsList(data, esc) {
  const rows = data.deposits || [];
  if (!rows.length) return "";
  const list = rows.map((row) => {
    const colour = window.VoidCompassRhinoDraw ? window.VoidCompassRhinoDraw.commodityColour(String(row.materials || "").split(",")[0]) : [200, 200, 200];
    const on = String(row.id) === String(selected) ? " on" : "";
    const worth = (data.map?.deposits || []).find((item) => String(item.id) === String(row.id))?.value;
    return `<li class="${row.depleted ? "mined" : ""}${on}" data-rhino-op="select" data-id="${esc(row.id)}"><i style="background:rgb(${colour.join(",")})">${row.n || ""}</i>
      <b>${esc(String(row.materials || "").split(",")[0] || "Deposit")}</b><span>${row.rigs ? `${row.rigs}R` : ""}${row.amount ? ` · ${esc(row.amount)}` : ""}${worth ? ` · ~${money(worth)}` : ""}</span><em>${row.distance != null ? distance(row.distance) : ""}</em></li>`;
  }).join("");
  return panel(`DEPOSITS ON ${esc(String(data.body || "").toUpperCase())}`, `<ul class="rh-deposits">${list}</ul>`, {note: "numbered in the order to drive them"});
}

// -- MAP: the figures, the map and its line ------------------------------------------------
// Back aboard: the run, the holds and what's still out.
function aboardFigures(data) {
  const card = data.aboard;
  const tile = (label, value, detail = "") => `<div class="rh-tile"><span>${label}</span><b>${value}</b>${detail ? `<small>${detail}</small>` : ""}</div>`;
  const hold = (name) => (data.holds || []).find((row) => row.name === name);
  const ship = hold("SHIP"), rhino = hold("RHINO");
  const nearest = (card.out || []).slice().sort((a, b) => n(a.distance_m) - n(b.distance_m))[0];
  const kinds = (card.taken || []).length;
  return `<div class="rh-tiles aboard">
    ${tile("REFINED", `${whole(card.refined_t)} t`, kinds ? `${kinds} commodit${kinds === 1 ? "y" : "ies"} from your rigs` : "this run")}
    ${tile("RIGS OUT", (card.out || []).length ? `${(card.out || []).length}` : "None", nearest ? `rig ${nearest.slot} ${distance(nearest.distance_m)} away` : "all collected")}
    ${tile("SHIP HOLD", ship ? `${whole(ship.used)} / ${whole(ship.capacity)} t` : "—", ship ? `${whole(ship.free)} t free` : "")}
    ${tile("RHINO HOLD", rhino ? `${whole(rhino.used)} / ${whole(rhino.capacity)} t` : "—", rhino && n(rhino.used) ? "still aboard the Rhino" : "")}
    ${tile("RUN", card.minutes != null ? `${whole(card.minutes)} min` : "—", card.site ? `at ${lastUi.escapeHtml(card.site.name)}` : "")}
  </div>`;
}

function figures(data) {
  if (data.aboard) return aboardFigures(data);
  const rigs = (data.map?.rigs || []);
  const refined = rigs.reduce((sum, rig) => sum + n(rig.tonnes), 0);
  const facts = data.facts || {};
  const rhino = (data.holds || []).find((hold) => hold.name === "RHINO");
  const value = data.map?.value || {};
  const tile = (label, value, detail = "") => `<div class="rh-tile"><span>${label}</span><b>${value}</b>${detail ? `<small>${detail}</small>` : ""}</div>`;
  return `<div class="rh-tiles">
    ${tile("RIGS DOWN", `${rigs.length} / 6`, refined ? `${whole(refined)} t from them` : "")}
    ${tile("SWEPT", facts.survey?.edge ? `${Math.floor(n(facts.survey.percent))}%` : "—", facts.survey ? (facts.survey.edge ? `of ${distance(facts.survey.radius_m)} round the centre` : `edge not marked · centre ${distance(facts.survey.centre_m)} away`) : "no survey")}
    ${tile("RIG PLAN", facts.plan ? `${whole(facts.plan.filled)} / ${whole(facts.plan.pins)}` : "—", facts.plan ? (facts.plan.next ? `P${facts.plan.next.n} ${way(facts.plan.next)}` : "every pin filled") : "trace a deposit's edge")}
    ${tile("RHINO HOLD", rhino ? `${whole(rhino.used)} / ${whole(rhino.capacity)} t` : "—", rhino ? `${whole(rhino.free)} t free` : "")}
    ${tile("EST. VALUE", value.credits ? `~${money(value.credits)} CR` : "—", value.per_rig ? `${whole(value.deposits)} deposits · ${whole(value.rigs)}R · a rig gives ~${whole(value.per_rig)} t${value.unpriced ? ` · ${value.unpriced} unpriced` : ""}` : "once a few rigs are worked")}
  </div>`;
}

function mapLine(data, esc) {
  const parts = [];
  if (data.tracing) parts.push(`<span class="route">TRACING · DRIVE ROUND THE EDGE BACK TO THE START</span>`);
  if (data.aboard) parts.push(`<span class="green">IN THE SHIP · ${esc(String(data.aboard.next || "").toUpperCase())}</span>`);
  else if (data.rig_words) parts.push(`<span class="${esc(data.rig_words.tone)}">${esc(data.rig_words.text)}</span>`);
  const facts = data.facts || {};
  const following = data.map && window.VoidCompassRhinoDraw ? window.VoidCompassRhinoDraw.nextWords(data.map) : "";
  if (following) parts.push(`<b>${esc(following)}</b>`);
  else if (facts.deposits?.next) parts.push(`NEXT DEPOSIT <b>${esc(String(facts.deposits.next.commodity).toUpperCase())}</b> ${way(facts.deposits.next)}`);
  for (const group of data.map?.groups || []) {
    parts.push(`<span class="yellow">PATCH ${group.n} · ${group.rigs}R${group.cr_per_h ? ` · ~${money(group.cr_per_h)} CR/H` : ""} · ${way(group)}</span>`);
  }
  if (facts.survey?.next) parts.push(`SWEEP STOP <b>${way(facts.survey.next)}</b>`);
  if (facts.patch) parts.push(`BEST PATCH <b>${n(facts.patch.distance) < 40 ? "HERE" : way(facts.patch)}</b>`);
  if (facts.circle) parts.push(n(facts.circle.room) >= 0 ? `CIRCLE <b>${distance(facts.circle.room)}</b> TO ITS EDGE` : `<span class="red">OUTSIDE THE CIRCLE BY ${distance(-n(facts.circle.room))}</span>`);
  if (data.map?.ship?.distance != null) parts.push(`SHIP <b>${distance(data.map.ship.distance)}</b>`);
  if (n(data.map?.elsewhere)) parts.push(`<span class="dim">+${whole(data.map.elsewhere)} MARKED ELSEWHERE ON THIS BODY · SITES</span>`);
  return parts.map((part) => `<i>${part}</i>`).join("");
}

// A rig's time: how long still to go, or READY, once your rigs have taught
// how long they take; until then, how long it's been down.
function readyWords(rig) {
  // Still collecting from it: its clock starts again as you drive off (5.8.3).
  if (rig.collecting) return `<b class="rh-collecting">COLLECTING</b> · ${n(rig.haul)} t so far · its clock starts once you've driven off`;
  const down = Math.max(0, Date.now() / 1000 - n(rig.at));
  if (!n(rig.ready_s)) return `${Math.floor(down / 60)}:${String(Math.floor(down % 60)).padStart(2, "0")} down`;
  // Filling since it went down, or since you last collected from it.
  const filling = Math.max(0, Date.now() / 1000 - n(rig.fill_from || rig.at));
  const left = Math.ceil(n(rig.ready_s) - filling);
  const last = n(rig.haul) ? ` · last ${n(rig.haul)} t` : "";
  return (left <= 0 ? `<b class="rh-ready">READY</b>` : `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")} to go`) + last;
}

function rigsTable(data, esc) {
  const rows = ((data.rigs || {}).rigs || []).slice().sort((a, b) => n(a.slot) - n(b.slot));
  if (!rows.length) return "";
  const order = (data.rigs.collect_order || []).map((slot) => `#${slot}`).join(" → ");
  return panel("RIGS", `<table class="rh-table"><thead><tr><th>RIG</th><th>WORKING</th><th>REFINED</th><th>WHERE</th><th>DOWN</th></tr></thead><tbody>${rows.map((rig) =>
    `<tr><td>#${rig.slot}</td><td>${esc(rig.commodity || "—")}</td><td>${n(rig.tonnes) ? `${whole(rig.tonnes)} t` : "—"}</td><td>${rig.here ? "HERE" : `${distance(rig.distance_m)} ${compass(rig.bearing)}`}</td><td>${readyWords(rig)}</td></tr>`).join("")}</tbody></table>
    ${order ? `<p class="rh-dim">Collect in the order they went down: ${order}</p>` : ""}`);
}

// The map and the keys are for the Rhino (and, back aboard after a run, the
// ship's summary); arriving at a planet in the ship, or on foot, the page waits.
const working = (data) => Boolean(data.in_rhino || data.aboard);

function mapView(data, esc) {
  if (!working(data)) {
    const where = data.on_surface ? `You're at ${esc(data.body)}, not in the Rhino. ` : "";
    const next = data.on_surface ? "Deploy the Rhino" : "Land on a planet and deploy the Rhino";
    return `${targetBar(data, esc)}<div class="rh-grid"><div class="rh-rail">${panel("THE RHINO", empty(`${where}${next}: the map, your keys and the deposits round you come up. SITES has your saved locations and every deposit you've marked; WHERE TO LAND has this system's Rhino ground.`))}</div>
      <div class="rh-main">${panel("THE MAP", empty(data.on_surface ? "Waiting for the Rhino." : "Waiting for you to be on a planet's surface."))}</div></div>`;
  }
  return `<div class="rh-grid">
    <div class="rh-rail" data-part="rail">${rail(data, esc)}</div>
    <div class="rh-main">
      <div data-part="target">${targetBar(data, esc)}</div>
      <div data-part="figures">${figures(data)}</div>
      <section class="rh-mapbox">
        <canvas id="rh-map-canvas" aria-label="The ground round you"></canvas>
        <div class="rh-map-controls">
          <button type="button" data-rhino-op="map_up" title="North up, or the way you're heading">${mapUp === "north" ? "NORTH UP" : "HEADING UP"}</button>
          <button type="button" data-rhino-op="map_zoom" data-step="in" title="Closer">+</button>
          <button type="button" data-rhino-op="map_zoom" data-step="out" title="Further">−</button>
          <button type="button" data-rhino-op="map_centre" title="Back to the whole location, fitted">RECENTRE</button>
        </div>
      </section>
      <div class="rh-line" data-part="line">${mapLine(data, esc)}</div>
      <div data-part="rigs">${rigsTable(data, esc)}</div>
    </div>
  </div>`;
}

// -- SITES and WHERE TO LAND ------------------------------------------------------------
// Sites compared (5.8.3): each saved site's usual rate as a bar, its best run
// as a tick on it, and its runs in order as a strip of dots, all on one scale.
const STRIP_RUNS = 12;
function sitesCompared(data, esc) {
  const sites = (data.saved_sites || []).filter((site) => site.runs && (site.runs.runs || []).some((run) => n(run.tph) > 0))
    .sort((a, b) => n(b.runs.usual_tph) - n(a.runs.usual_tph));
  if (!sites.length) return "";
  const top = Math.max(...sites.map((site) => n(site.runs.best_tph)), 1);
  const scale = (value) => Math.max(0, Math.min(100, (n(value) / top) * 100));
  const rows = sites.map((site) => {
    const runs = (site.runs.runs || []).filter((run) => n(run.tph) > 0).slice(0, STRIP_RUNS).reverse();
    const width = 132, height = 26, pad = 6;
    const x = (index) => runs.length < 2 ? width / 2 : pad + (index * (width - 2 * pad)) / (runs.length - 1);
    const y = (tph) => height - pad - (n(tph) / top) * (height - 2 * pad);
    const line = runs.length > 1 ? `<polyline points="${runs.map((run, index) => `${x(index).toFixed(1)},${y(run.tph).toFixed(1)}`).join(" ")}"/>` : "";
    const dots = runs.map((run, index) => `<circle cx="${x(index).toFixed(1)}" cy="${y(run.tph).toFixed(1)}" r="4"${index === runs.length - 1 ? ' class="latest"' : ""}><title>${esc(when(run.docked))}: ${whole(run.tph)} t/h · ${whole(run.refined_t)} t in ${whole(run.minutes)} min</title></circle>`).join("");
    const usual = n(site.runs.usual_tph);
    const best = n(site.runs.best_tph);
    const label = `Usual ${whole(usual)} t/h over ${whole(site.runs.count)} run${site.runs.count === 1 ? "" : "s"}, best ${whole(best)} t/h`;
    return `<li class="${site.here ? "here" : ""}">
      <span class="rh-cmp-name"><b>${esc(site.name || "Mining location")}</b><small>${esc(site.body)}${site.runs.best_commodity ? ` · ${esc(site.runs.best_commodity)}` : ""}</small></span>
      <span class="rh-cmp-bar" title="${esc(label)}" aria-label="${esc(label)}"><i style="width:${scale(usual).toFixed(1)}%"></i><em style="left:${scale(best).toFixed(1)}%"></em><b style="left:${Math.max(scale(usual), scale(best)).toFixed(1)}%">${whole(usual)}<small> t/h</small></b></span>
      <svg class="rh-cmp-strip" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(`Runs at ${site.name}, oldest to newest`)}">${line}${dots}</svg>
    </li>`;
  }).join("");
  const body = `<p class="rh-cmp-key"><span><i class="bar"></i>usual rate</span><span><i class="tick"></i>best run</span><span><i class="dot"></i>each run, oldest to newest (hover for it)</span></p>
    <ul class="rh-cmp">${rows}</ul>`;
  return panel("SITES COMPARED · TONNES AN HOUR", body, {note: `${whole(sites.length)} site${sites.length === 1 ? "" : "s"} with runs`});
}

function savedSites(data, esc, words) {
  const all = data.saved_sites || [];
  const rows = all.filter((row) => !words.length || words.some((word) =>
    `${row.name} ${row.note} ${row.system} ${row.body} ${(row.deposits?.commodities || []).join(" ")} ${Object.keys(row.tonnes || {}).join(" ")}`.toLowerCase().includes(word)));
  const row = (site) => {
    const deposits = site.deposits || {};
    const commodities = deposits.commodities || [];
    const tonnes = Object.entries(site.tonnes || {}).sort((a, b) => n(b[1]) - n(a[1]));
    const ids = {id: site.id, system: site.system, body: site.body};
    const attrs = Object.entries(ids).map(([k, v]) => ` data-${k}="${esc(String(v ?? ""))}"`).join("");
    const editing = renaming === site.id;
    const name = editing ? `<form class="rh-form rh-rename" data-rhino-form="site"${attrs}><input name="name" value="${esc(site.name || "")}" maxlength="80" placeholder="Name"><input name="note" value="${esc(site.note || "")}" maxlength="400" placeholder="A note"><button type="submit">KEEP</button></form>`
      : `<b>${esc(site.name || "Mining location")}</b>${site.note ? `<small>${esc(site.note)}</small>` : ""}`;
    return `<tr class="${site.here ? "here" : ""}"><td class="rh-site-name">${name}</td><td>${esc(site.system)}<small>${esc(site.body)}</small></td><td>${site.signal != null ? esc(site.signal) : "—"}</td>
      <td>${site.swept != null ? `${Math.floor(n(site.swept))}%${site.edge ? "" : " <small>no edge</small>"}` : "—"}</td>
      <td>${n(deposits.live) || n(deposits.mined) ? `${whole(deposits.live)} live${n(deposits.mined) ? ` · ${whole(deposits.mined)} mined` : ""}${n(deposits.rigs) ? ` · ${whole(deposits.rigs)}R` : ""}<small>${esc(commodities.join(", "))}</small>` : "—"}</td>
      <td>${site.runs ? `<button type="button" class="rh-runs-toggle" data-rhino-op="site_runs" data-id="${esc(site.id)}" aria-expanded="${runsOpen === site.id}">${whole(site.runs.count)} run${site.runs.count === 1 ? "" : "s"}</button><small>${whole(site.runs.tonnes)} t${site.runs.usual_tph ? ` · ~${whole(site.runs.usual_tph)} t/h` : ""}</small>` : "—"}</td>
      <td>${tonnes.length ? tonnes.map(([name, t]) => `${whole(t)} t ${esc(name)}`).join("<br>") : "—"}</td><td>${when(site.updated)}</td>
      <td class="rh-row-actions"><button type="button" data-rhino-op="site_target"${attrs}>TARGET</button>${site.here ? `<button type="button" data-rhino-op="site_resume"${attrs}>RESUME</button>` : ""}<button type="button" data-rhino-op="copy_system" data-system="${esc(site.system)}">COPY SYSTEM</button><button type="button" data-rhino-op="site_rename_open"${attrs}>${editing ? "CANCEL" : "RENAME"}</button>${confirmButton(`site-${site.id}`, "DELETE", "site_forget", ids)}</td></tr>`;
  };
  const table = rows.length ? `<table class="rh-table rh-saved-sites"><thead><tr><th>SITE</th><th>WHERE</th><th>SIGNAL</th><th>SWEPT</th><th>DEPOSITS</th><th>RUNS</th><th>TAKEN</th><th>SAVED</th><th></th></tr></thead><tbody>${rows.map((site) => row(site) + runsRows(site, esc)).join("")}</tbody></table>`
    : empty(words.length ? "No saved site matches that." : "Press SAVE THIS SITE on the map (or its key) to keep a mining location: its signal, centre, survey, deposits, rig plan and what your rigs took. Leaving a planet with a survey or marked deposits saves it too.");
  return panel("SAVED MINING LOCATIONS", `${table}<p class="rh-dim">TARGET puts its centre on the compass; RESUME carries its survey on when you're back on the planet; DELETE asks again before it goes (the deposits you marked there stay).</p>`,
    {note: `${whole(rows.length)} of ${whole(all.length)}`});
}

// EDIT on a deposit's row, and its editor under that row while it's open.
function editButton(row, where) {
  const open = String(sitesEditing) === String(row.id) && sitesEditingIn === where;
  return `<button type="button" data-rhino-op="${open ? "sites_edit_done" : "sites_edit"}" data-id="${lastUi.escapeHtml(String(row.id))}" data-where="${where}" aria-expanded="${open}">${open ? "CLOSE" : "EDIT"}</button>`;
}

function editRow(data, esc, row, where, columns) {
  if (String(sitesEditing) !== String(row.id) || sitesEditingIn !== where) return "";
  return `<tr class="rh-edit-row"><td colspan="${columns}"><div class="rh-sites-editor">${depositEditor(data, esc, row)}</div></td></tr>`;
}

// Worked-out deposits and when to look again: due a look first, then those
// checked (the mark comes off), then the freshest.
const REGROWTH_ORDER = {due: 0, expired: 1, unknown: 2, waiting: 3, fresh: 4};
function depletedPanel(data, esc, words) {
  const all = (data.sites || []).filter((row) => row.depleted);
  const rows = all.filter((row) => !words.length || words.some((word) => `${row.system} ${row.body} ${row.materials}`.toLowerCase().includes(word)))
    .sort((a, b) => (REGROWTH_ORDER[a.regrowth?.state] ?? 9) - (REGROWTH_ORDER[b.regrowth?.state] ?? 9) || n(b.regrowth?.age_days) - n(a.regrowth?.age_days));
  if (!all.length) return "";
  const due = all.filter((row) => row.regrowth?.due).length;
  const table = rows.length ? `<table class="rh-table rh-depleted"><thead><tr><th>COMMODITY</th><th>WHERE</th><th>WORKED OUT</th><th>NEXT</th><th></th></tr></thead><tbody>${rows.map((row) => {
      const info = row.regrowth || {};
      const next = {due: "Recheck due", expired: "Mark comes off", waiting: `Mark off in ${n(info.off_in_days)} d`, unknown: "Date not known",
        fresh: `Look in ${Math.max(0, 14 - n(info.age_days))} d`}[info.state] || "—";
      return `<tr class="${info.due ? "due" : ""}"><td>${esc(String(row.materials || "").split(",")[0])}</td><td>${esc(row.system)}<small>${esc(row.body)}</small></td>
        <td>${info.age_days != null ? `${whole(info.age_days)} days ago` : "—"}${info.looks ? `<small>checked ${info.looks}×</small>` : ""}</td><td>${esc(next)}</td>
        <td class="rh-row-actions">${editButton(row, "depleted")}<button type="button" data-rhino-op="deposit_navigate" data-id="${esc(row.id)}">TARGET</button><button type="button" data-rhino-op="deposit_regrown" data-id="${esc(row.id)}">REGROWN</button>${confirmButton(`del-${row.id}`, "DELETE", "deposit_delete", {id: row.id})}</td></tr>${editRow(data, esc, row, "depleted", 5)}`;
    }).join("")}</tbody></table>` : empty("No worked-out deposit matches that.");
  return panel("WORKED-OUT DEPOSITS", `${table}<p class="rh-dim">Deposits grow back, nobody knows quite how fast. Two weeks after you work one out it's due a look: MINED OUT on it (or STILL DEPLETED here) if it's still empty, and the mark comes off a week later. A rig refining it again marks it grown back by itself.</p>`,
    {note: due ? `${whole(due)} due a look` : `${whole(all.length)}`});
}

// A saved site's runs, newest first, when its RUNS is open.
function runsRows(site, esc) {
  if (runsOpen !== site.id || !site.runs) return "";
  const best = site.runs.best_tph;
  const rows = site.runs.runs.map((run) => {
    const taken = Object.entries(run.taken || {}).sort((a, b) => n(b[1]) - n(a[1])).map(([name, t]) => `${whole(t)} t ${esc(name)}`).join(" · ");
    return `<li><b>${when(run.docked)}</b><span>${whole(run.minutes)} min · ${whole(run.refined_t)} t${run.tph ? ` · <em class="${run.tph === best ? "best" : ""}">${whole(run.tph)} t/h</em>` : ""}</span><small>${taken}</small></li>`;
  }).join("");
  return `<tr class="rh-runs-row"><td colspan="9"><ul class="rh-runs">${rows}</ul>${site.runs.best_commodity ? `<p class="rh-dim">Most from here: ${esc(site.runs.best_commodity)}. Best run ${whole(best)} t/h.</p>` : ""}</td></tr>`;
}

function sitesView(data, esc) {
  const words = filter.split(",").map((word) => word.trim().toLowerCase()).filter(Boolean);
  const rows = (data.sites || []).filter((row) => !words.length || words.some((word) =>
    `${row.system} ${row.body} ${row.materials}`.toLowerCase().includes(word)));
  const here = String(data.body || "").toLowerCase();
  const table = rows.length ? `<table class="rh-table"><thead><tr><th>SYSTEM</th><th>BODY</th><th>COMMODITY</th><th>RIGS</th><th>AMOUNT</th><th>DENSITY</th><th>SIGNAL</th><th></th></tr></thead><tbody>${rows.map((row) =>
    `<tr class="${row.depleted ? "mined" : ""}${String(row.body || "").toLowerCase() === here ? " here" : ""}"><td>${esc(row.system)}</td><td>${esc(row.body)}</td><td>${esc(row.materials)}</td><td>${row.rigs || "—"}</td><td>${row.depleted ? `${row.regrowth?.due ? "<b class=\"rh-due\">Recheck due</b>" : "Depleted"}${row.regrowth?.age_days != null ? `<small>${whole(row.regrowth.age_days)} days</small>` : ""}` : esc(row.amount || "—")}</td><td>${esc(row.density || "—")}</td><td>${row.signal ?? "—"}</td>
     <td class="rh-row-actions">${editButton(row, "all")}<button type="button" data-rhino-op="copy_system" data-system="${esc(row.system)}">COPY SYSTEM</button><button type="button" data-rhino-op="deposit_navigate" data-id="${esc(row.id)}">TARGET</button>${confirmButton(`del-${row.id}`, "DELETE", "deposit_delete", {id: row.id})}</td></tr>${editRow(data, esc, row, "all", 8)}`).join("")}</tbody></table>`
    : empty(words.length ? "Nothing marked matches that." : "Deposits you mark show here, on every planet.");
  const chips = [...(data.catalogue?.rhino || []), ...(data.catalogue?.found || [])].map((name) => {
    const on = words.includes(name.toLowerCase());
    return `<button type="button" class="rh-chip${on ? " on" : ""}" data-rhino-op="filter_chip" data-name="${esc(name)}" aria-pressed="${on}">${esc(name)}</button>`;
  }).join("");
  return `${targetBar(data, esc)}<form class="rh-filter" data-rhino-form="filter"><input name="filter" value="${esc(filter)}" placeholder="Filter: name, system, body or commodity; commas mean any of them"></form>
    ${chips ? `<div class="rh-chips" role="group" aria-label="Rhino commodities">${chips}</div>` : ""}
    ${words.length ? "" : sitesCompared(data, esc)}${savedSites(data, esc, words)}${depletedPanel(data, esc, words)}${panel("EVERY DEPOSIT YOU'VE MARKED", table, {note: `${whole(rows.length)} of ${whole((data.sites || []).length)}`})}`;
}

function landView(data, esc) {
  const rows = data.prospects || [];
  const list = rows.length ? `<ul class="rh-prospects">${rows.map((row) => `<li><b>${esc(row.short || row.body)}</b><span>${esc(row.ground)}${row.mining_count ? ` · <em>${row.mining_count} MINING SITES</em>` : ""}</span>
      <small>${(row.materials || []).map((item) => `${esc(item.material)} ${n(item.pct).toFixed(0)}%`).join(" · ")}</small><strong>${whole(row.expected)} CR a t</strong></li>`).join("")}</ul>`
    : empty("Scan the system's landable bodies to see which ground is worth the Rhino.");
  const ground = data.ground;
  const groundRows = ground ? (ground.expected_materials || []).slice().sort((a, b) => n(b.pct) - n(a.pct)).slice(0, 10) : [];
  const groundPanel = ground ? panel("THIS GROUND", `<p class="rh-sub"><b>${esc(ground.ground_label)}</b>${ground.gravity != null ? ` · ${n(ground.gravity).toFixed(2)} g` : ""}</p>
      <ul class="rh-ground">${groundRows.map((row) => `<li><span>${esc(row.material)}</span><i><b style="width:${Math.min(100, n(row.pct)).toFixed(1)}%"></b></i><strong>${n(row.pct).toFixed(0)}%</strong><small>${row.median ? `${whole(row.median)} CR a t` : ""}</small></li>`).join("")}</ul>
      <p class="rh-dim">How often each turns up at a mining site on this kind of ground, and its usual price: EDIntel's ground mining table. A guide, not a promise.</p>`) : "";
  return `<div class="rh-two">${panel("RHINO GROUND IN THIS SYSTEM", `${list}<p class="rh-dim">Bodies with mining sites found come first, then by what their best material is likely worth a tonne.</p>`)}${groundPanel}</div>`;
}

// -- the map canvas -----------------------------------------------------------------------
function palette() {
  const style = getComputedStyle(document.documentElement);
  const read = (name) => style.getPropertyValue(name).trim();
  return {orange: read("--orange"), green: read("--green"), yellow: read("--yellow"), red: read("--red"),
    text: read("--text"), accent: read("--accent"), muted: read("--muted")};
}

// The location's things: deposits, rigs, plan pins and the survey (its
// centre, and its whole circle once the edge is marked), within 8 km of you.
function locationPoints(surface) {
  const you = surface.you.at;
  const points = [];
  const add = (at) => { if (at && Math.hypot(n(at[0]) - n(you[0]), n(at[1]) - n(you[1])) <= FIT.reach) points.push([n(at[0]), n(at[1])]); };
  for (const item of surface.deposits || []) add(item.at);
  for (const rig of surface.rigs || []) add(rig.at);
  for (const pin of surface.plan || []) add(pin.at);
  const survey = surface.survey;
  if (survey?.at) {
    const [x, y] = survey.at, r = survey.edge ? n(survey.radius_m) : 0;
    for (const at of r ? [[x + r, y], [x - r, y], [x, y + r], [x, y - r]] : [[x, y]]) add(at);
  }
  return points;
}

// Round radii, so a view that has to widen does it in a few clear steps.
const STEPS = [250, 500, 1000, 1500, 2500, 4000, 6000, 8000, 12000, 15000];
const stepUp = (metres) => STEPS.find((step) => step >= metres) || FIT.cap;

// Centred on the location's things and holding them and you. A survey with
// only its centre so far gets a location's worth of ground (2.5 km), so
// driving out to mark the edge doesn't move it.
function fitView(surface, things, atLeast = 0) {
  const you = surface.you.at;
  const xs = things.map((p) => p[0]), ys = things.map((p) => p[1]);
  const centre = [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
  const near = Math.hypot(n(you[0]) - centre[0], n(you[1]) - centre[1]) <= FIT.reach ? [you] : [];
  const spread = Math.max(...[...things, ...near].map((p) => Math.hypot(n(p[0]) - centre[0], n(p[1]) - centre[1])));
  const onlyCentre = things.length === 1 && surface.survey?.at && !surface.survey.edge;
  const floor = onlyCentre ? FIT.empty : FIT.floor;
  return {centre, half: stepUp(Math.max(floor, spread * FIT.room, atLeast))};
}

// The map holds still while you work: it fits again only when something is
// added or taken away (a deposit, a rig, the edge), or, if you drive right
// off it, it widens a step or two round the same middle. Nothing worked here
// yet: the scanner's ground round you, following you.
function settledFit(surface) {
  const place = `${last?.system || ""}|${last?.body || ""}|${last?.signal ?? ""}`;
  if (fitted && fitted.place !== place) { fitted = null; chosenHalf = null; pan = null; }
  const things = locationPoints(surface);
  if (!things.length) return (fitted = {centre: surface.you.at, half: FIT.empty, place, key: ""});
  const key = `${things.length}|${surface.survey?.edge ? 1 : 0}`;
  if (fitted && fitted.key === key) {
    const you = surface.you.at;
    if (Math.hypot(n(you[0]) - fitted.centre[0], n(you[1]) - fitted.centre[1]) <= fitted.half * .92) return fitted;
    return (fitted = {...fitView(surface, things, fitted.half * 1.5), place, key});
  }
  return (fitted = {...fitView(surface, things), place, key});
}

function drawMap() {
  const canvas = document.getElementById("rh-map-canvas");
  const surface = last?.map;
  const Draw = window.VoidCompassRhinoDraw;
  if (!canvas || !surface?.you || !Draw) return;
  const fit = settledFit(surface);
  const centre = pan || fit.centre;
  const view = {x: n(centre[0]), y: n(centre[1]), heading: n(surface.you.heading), up: mapUp, half: chosenHalf || fit.half};
  const shown = last.aboard ? {...surface, radar: null, next_spot: null} : surface;
  lastFrame = Draw.draw(canvas, shown, view, palette(), {selected, labelPx: 8.4});
}

window.__rhinoPageView = () => ({half: chosenHalf || fitted?.half, centre: pan || fitted?.centre, chosen: chosenHalf});

function zoomBy(factor) {
  const from = chosenHalf || fitted?.half || FIT.empty;
  chosenHalf = Math.max(FIT.closest, Math.min(FIT.widest, from * factor));
  drawMap();
}

function recentre() {
  pan = null; chosenHalf = null; fitted = null;
  drawMap();
}

function renderPart(root, name, markup) {
  const node = root.querySelector(`[data-part="${name}"]`);
  if (!node || drawnParts[name] === markup) return;
  if (node.contains(document.activeElement) && document.activeElement.matches("input, select, textarea")) return;
  drawnParts[name] = markup;
  node.innerHTML = markup;
}

export function renderRhino(data, ui, force = false) {
  const root = ui.byId("rhino-workspace");
  if (!root) return;
  last = data || {};
  lastUi = ui;
  root.classList.remove("loading-panel");
  const esc = ui.escapeHtml;
  if (selected != null && !(last.deposits || []).some((row) => String(row.id) === String(selected))) selected = null;
  const tabs = `<nav class="co-tabs rh-tabs">${VIEWS.map(([id, label]) => `<button type="button" class="${view === id ? "active" : ""}" data-rhino-op="view" data-view="${id}">${label}</button>`).join("")}</nav>`;
  const skeleton = `${view}|${working(last) ? 1 : 0}|${last.aboard ? 1 : 0}`;
  // The map keeps its canvas between snapshots: only the parts round it are redrawn.
  if (root.dataset.skeleton !== skeleton || view !== "map") {
    const body = {map: mapView, sites: sitesView, land: landView}[view] || mapView;
    const markup = `<div data-part="status">${statusStrip(last, esc)}</div>${tabs}<div class="rh-body">${body(last, esc)}</div>`;
    if (!force && view !== "map" && root.dataset.markup === markup) return;
    if (!force && view !== "map" && root.contains(document.activeElement) && document.activeElement.matches("input")) return;
    root.dataset.skeleton = skeleton;
    root.dataset.markup = markup;
    root.innerHTML = markup;
    drawnParts = {};
    bindMap(root);
  } else {
    renderPart(root, "status", statusStrip(last, esc));
    renderPart(root, "rail", rail(last, esc));
    renderPart(root, "target", targetBar(last, esc));
    renderPart(root, "figures", figures(last));
    renderPart(root, "line", mapLine(last, esc));
    renderPart(root, "rigs", rigsTable(last, esc));
  }
  drawMap();
}

export function resetRhino() {
  selected = null; filter = ""; renaming = null; sitesEditing = null; view = "map"; pan = null; chosenHalf = null; fitted = null; drawnParts = {};
  const root = document.getElementById("rhino-workspace");
  if (root) { delete root.dataset.skeleton; delete root.dataset.markup; }
}

function bindMap(root) {
  const canvas = root.querySelector("#rh-map-canvas");
  if (!canvas) return;
  new ResizeObserver(() => drawMap()).observe(canvas);
  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    zoomBy(event.deltaY > 0 ? 1.25 : 1 / 1.25);
  }, {passive: false});
  canvas.addEventListener("pointerdown", (event) => {
    drag = {x: event.clientX, y: event.clientY, moved: false};
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!drag || !lastFrame || !last?.map?.you) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx, dy) < 4) return;
    drag.moved = true;
    const box = canvas.getBoundingClientRect();
    const middle = [box.width / 2, box.height / 2];
    pan = lastFrame.back([middle[0] - dx, middle[1] - dy]);
    drag.x = event.clientX; drag.y = event.clientY;
    drawMap();
  });
  canvas.addEventListener("pointerup", (event) => {
    const wasDrag = drag?.moved;
    drag = null;
    if (wasDrag || !lastFrame) return;
    const box = canvas.getBoundingClientRect();
    const x = event.clientX - box.left, y = event.clientY - box.top;
    const hit = (lastFrame.hits || []).filter((item) => item.kind === "deposit")
      .find((item) => Math.hypot(item.at[0] - x, item.at[1] - y) <= item.r + 3);
    if (hit) {
      selected = hit.id;
      drawnParts.rail = null;
      renderRhino(last, lastUi);
    }
  });
  canvas.addEventListener("dblclick", recentre);
}

export function handleRhinoClick(event, ui) {
  if (!event.target.closest?.('[data-page-name="rhino"]')) return false;
  const control = event.target.closest("[data-rhino-op]");
  if (!control || control.disabled) return false;
  event.preventDefault();
  const op = control.dataset.rhinoOp;
  if (op === "view") { view = control.dataset.view || "map"; renderRhino(last, ui); return true; }
  if (op === "select") { selected = control.dataset.id; drawnParts.rail = null; renderRhino(last, ui); return true; }
  if (op === "map_up") { mapUp = mapUp === "north" ? "heading" : "north"; control.textContent = mapUp === "north" ? "NORTH UP" : "HEADING UP"; drawMap(); return true; }
  if (op === "map_zoom") { zoomBy(control.dataset.step === "in" ? 1 / 1.4 : 1.4); return true; }
  if (op === "map_centre") { recentre(); return true; }
  if (op === "site_runs") { runsOpen = runsOpen === control.dataset.id ? null : control.dataset.id; renderRhino(last, ui, true); return true; }
  if (op === "sites_edit") {
    sitesEditing = control.dataset.id;
    sitesEditingIn = control.dataset.where || "all";
    renderRhino(last, ui, true);
    ui.byId("rhino-workspace")?.querySelector(".rh-sites-editor")?.scrollIntoView({block: "nearest"});
    return true;
  }
  if (op === "sites_edit_done") { sitesEditing = null; renderRhino(last, ui, true); return true; }
  if (op === "filter_chip") {
    // A commodity chip adds itself to the filter, or takes itself off.
    const name = String(control.dataset.name || "").toLowerCase();
    const parts = filter.split(",").map((word) => word.trim()).filter(Boolean);
    const kept = parts.filter((word) => word.toLowerCase() !== name);
    filter = (kept.length === parts.length ? [...parts, control.dataset.name] : kept).join(", ");
    renderRhino(last, ui, true);
    return true;
  }
  if (op === "site_rename_open") { renaming = renaming === control.dataset.id ? null : control.dataset.id; renderRhino(last, ui, true); return true; }
  if (control.dataset.confirmKey) {
    const id = control.dataset.confirmKey;
    if (confirming.key !== id || Date.now() > confirming.until) {
      confirming = {key: id, until: Date.now() + 4000};
      drawnParts = {};
      renderRhino(last, ui);
      setTimeout(() => { if (confirming.key === id) { drawnParts = {}; renderRhino(last, lastUi); } }, 4100);
      return true;
    }
    confirming = {key: "", until: 0};
  }
  const extra = {};
  for (const [name, value] of Object.entries(control.dataset)) {
    if (!["rhinoOp", "confirmKey"].includes(name)) extra[name.replace(/[A-Z]/g, (char) => `_${char.toLowerCase()}`)] = value;
  }
  if (control.dataset.confirmKey) extra.confirmed = true;
  send(ui, op, extra);
  return true;
}

export function handleRhinoSubmit(event, ui) {
  const form = event.target.closest?.("[data-rhino-form]");
  if (!form || !ui.byId("rhino-workspace")?.contains(form)) return false;
  event.preventDefault();
  if (form.dataset.rhinoForm === "filter") return true;
  if (form.dataset.rhinoForm === "site-save") {
    send(ui, "site_save", {name: String(form.elements.name?.value || "").trim()});
    document.activeElement?.blur?.();
    return true;
  }
  const values = {id: form.dataset.id};
  for (const element of form.elements) if (element.name) values[element.name] = element.value;
  if (form.dataset.rhinoForm === "site") {
    renaming = null;
    send(ui, "site_rename", {...values, system: form.dataset.system, body: form.dataset.body});
  } else send(ui, "deposit_save", values);
  document.activeElement?.blur?.();
  return true;
}

export function handleRhinoInput(event, ui) {
  const form = event.target.closest?.("[data-rhino-form='filter']");
  if (!form || !ui.byId("rhino-workspace")?.contains(form)) return false;
  filter = event.target.value || "";
  const caret = event.target.selectionStart;
  const root = ui.byId("rhino-workspace");
  renderRhino(last, ui, true);
  const input = root.querySelector(".rh-filter input");
  if (input) { input.focus(); input.setSelectionRange(caret, caret); }
  return true;
}
