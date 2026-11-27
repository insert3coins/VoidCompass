// The Rhino page: surface mining in one place.
// MAP is the working view: the site you're at and the keys as buttons down
// the left (grouped the way you work a signal), the deposit you picked to set
// and the deposits here under them; the figures, the big map and its line,
// and a card for each of the six rigs on the right.
// SITES is every mining location you've saved: compared on one scale, a list
// to pick from, and the one picked in full (its runs, what it took and is
// worth, its deposits) with REPORT to write it up for Discord or a file.
// DEPOSITS is every deposit you've marked anywhere, worked-out ones first
// when they're due a look; WHERE TO LAND is this system's Rhino ground.
// The map is /assets/rhino-draw.js, the same drawing as the Rhino Map overlay.

const VIEWS = [["map", "MAP"], ["sites", "SITES"], ["deposits", "DEPOSITS"], ["land", "WHERE TO LAND"]];
const n = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
const whole = (value) => Math.round(n(value)).toLocaleString("en-GB");
const distance = (metres) => n(metres) >= 1000 ? `${(n(metres) / 1000).toFixed(n(metres) >= 10000 ? 0 : 1)} km` : `${Math.round(n(metres))} m`;
const POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const compass = (bearing) => POINTS[Math.floor(((n(bearing) + 22.5) % 360) / 45)];
const way = (row) => `${distance(row.distance)} ${compass(row.bearing)}`;
const money = (value) => n(value) >= 1e9 ? `${(n(value) / 1e9).toFixed(2)}B` : n(value) >= 1e6 ? `${(n(value) / 1e6).toFixed(1)}M` : n(value) >= 1e3 ? `${Math.round(n(value) / 1e3)}K` : whole(value);
const DOING = {rhino: "In the Rhino", srv: "In an SRV", foot: "On foot", docked: "Docked", field: "In a ring", planet: "On a planet", flight: "In flight"};
const commodityOf = (row) => String(row?.materials || "").split(",")[0].trim() || "Deposit";
// A body's name without its system's in front: "AB 3 a".
const shortBody = (system, body) => {
  const s = String(system || ""), b = String(body || "");
  return s && b.toLowerCase().startsWith(`${s.toLowerCase()} `) ? b.slice(s.length + 1) : b;
};

let view = "map";
let last = null;
let lastUi = null;
let selected = null;
let filter = "";
let renaming = null;
// The deposit being edited from SITES or DEPOSITS, and the table it was
// opened from (it opens under that row).
let sitesEditing = null;
let sitesEditingIn = "all";
// The saved site shown in full on SITES, and whether its report is open.
let chosenSite = null;
let reportOpen = null;
const when = (seconds) => n(seconds) ? new Date(n(seconds) * 1000).toLocaleDateString("en-GB", {day: "numeric", month: "short", year: "numeric"}) : "—";
let confirming = {key: "", until: 0};
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
const attrsOf = (extra) => Object.entries(extra).map(([k, v]) => ` data-${k}="${lastUi.escapeHtml(String(v ?? ""))}"`).join("");
const tile = (label, value, detail = "", cls = "") => `<div class="rh-tile${cls ? ` ${cls}` : ""}"><span>${label}</span><b>${value}</b>${detail ? `<small>${detail}</small>` : ""}</div>`;

function button(data, op, label, action = "", extra = {}, cls = "") {
  return `<button type="button" class="rh-key${cls ? ` ${cls}` : ""}" data-rhino-op="${op}"${attrsOf(extra)}><b>${label}</b>${action ? key(data, action) : ""}</button>`;
}

function confirmButton(id, label, op, extra = {}) {
  const armed = confirming.key === id && Date.now() < confirming.until;
  return `<button type="button" class="rh-key rh-danger${armed ? " armed" : ""}" data-rhino-op="${op}" data-confirm-key="${lastUi.escapeHtml(id)}"${attrsOf(extra)}><b>${armed ? "SURE? AGAIN" : label}</b></button>`;
}

// -- the place bar -------------------------------------------------------------------
// Where you are, big; then the signal, what you're in, the holds as gauges and the run.
function statusStrip(data, esc) {
  const where = data.where || {};
  const run = data.run;
  const fact = (label, value, extra = "") => `<div class="rh-fact"><span>${label}</span><b>${value}</b>${extra}</div>`;
  const holds = (data.holds || []).map((hold) => {
    const capacity = Math.max(0, n(hold.capacity)), share = capacity ? Math.min(1, n(hold.used) / capacity) : 0;
    const state = share >= 1 ? "full" : share >= .9 ? "nearly" : "";
    return fact(`${esc(hold.name)} HOLD`, `${whole(hold.used)} / ${whole(capacity)} t`, `<i class="rh-gauge ${state}"><b style="width:${(share * 100).toFixed(1)}%"></b></i>`);
  }).join("");
  const body = shortBody(data.system, data.body);
  return `<div class="rh-status">
    <div class="rh-place"><b>${esc(body || "No planet")}</b><span>${esc(data.system || "Waiting for your location")}</span></div>
    <div class="rh-facts">
      ${fact("SIGNAL", data.signal != null ? `Location ${esc(data.signal)}` : n(data.signals) ? `${whole(data.signals)} here` : "—")}
      ${fact("DOING", esc(DOING[where.mode] || "—"))}
      ${holds}
      ${fact("RUN", run ? `${run.active ? "" : "Last · "}${whole(run.refined_t)} t${n(run.tons_per_hour) ? ` · ${n(run.tons_per_hour).toFixed(0)} t/h` : ""}` : "None going", run?.active ? `<em class="rh-live">LIVE</em>` : "")}
    </div>
  </div>`;
}

function tabsBar(data) {
  const depleted = (data.sites || []).filter((row) => row.depleted && row.regrowth?.due).length;
  const counts = {sites: (data.saved_sites || []).length, deposits: (data.sites || []).length};
  return `<nav class="co-tabs rh-tabs">${VIEWS.map(([id, label]) => {
    const count = counts[id] ? `<em>${whole(counts[id])}</em>` : "";
    const due = id === "deposits" && depleted ? `<em class="due">${whole(depleted)} DUE</em>` : "";
    return `<button type="button" class="${view === id ? "active" : ""}" data-rhino-op="view" data-view="${id}">${label}${count}${due}</button>`;
  }).join("")}</nav>`;
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

// The keys, in the order you work a signal: the survey, the deposits, the plan.
function keysPanel(data) {
  const plan = data.facts?.plan;
  const rigs = ((data.rigs || {}).rigs || []).length;
  const group = (label, keys, cls = "") => `<div class="rh-keygroup"><span>${label}</span><div class="rh-keys${cls ? ` ${cls}` : ""}">${keys}</div></div>`;
  const danger = `${data.facts?.survey ? confirmButton("survey", "CLEAR SURVEY", "survey_clear") : ""}${rigs ? confirmButton("rigs", "FORGET RIGS", "forget_rigs") : ""}`;
  return panel("KEYS", `${group("SURVEY", `${button(data, "survey_centre", "SURVEY CENTRE", "rhino_survey_centre")}${button(data, "survey_edge", "SURVEY EDGE", "rhino_survey_edge")}`)}
    ${group("DEPOSIT", button(data, "deposit_mark", "MARK DEPOSIT", "rhino_deposit_mark", {}, "primary"), "one")}
    ${group("PLAN", `${button(data, "trace", data.tracing ? "CLOSE TRACE" : "TRACE EDGE", "rhino_trace", {}, data.tracing ? "live" : "")}${button(data, "circle", "PLANNING CIRCLE", "rhino_circle")}${plan ? button(data, "trace_forget", "FORGET PLAN") : ""}`)}
    ${danger ? `<div class="rh-keys rh-keys-danger">${danger}</div>` : ""}
    <p class="rh-dim">The keys work in the game too (Settings › Helm › Shortcuts › Rhino). Rigs drop ${whole(data.settings?.drop_m)} m behind the cockpit and want ${whole(data.settings?.spacing_m)} m between them.</p>`, {cls: "rh-keys-panel"});
}

// The site you're at: its name to type over, and a name you give stays as
// the site's kept up to date as you work it.
function siteForm(data) {
  const esc = lastUi.escapeHtml, here = data.site_here;
  return `<form class="rh-site-form" data-rhino-form="site-save">
      <div class="rh-site-head"><span>${here ? "YOU'RE AT" : "THIS SPOT"}</span><em class="${here ? "saved" : ""}">${here ? `SAVED · ${when(here.updated)}` : "NOT SAVED YET"}</em></div>
      <div class="rh-site-row">
        <input name="name" value="${esc(here?.name || "")}" maxlength="80" placeholder="Name it (optional)" aria-label="Site name">
        <button type="submit" class="rh-key${here ? " down" : ""}"><b>${here ? "SAVE NAME" : "SAVE THIS SITE"}</b>${key(data, "rhino_site_save")}</button>
      </div>
      <p class="rh-dim">${here ? `It's kept up to date as you work it. <button type="button" class="rh-link" data-rhino-op="site_open" data-id="${esc(here.id)}">See it in SITES</button>` : "A site with a survey or marked deposits is saved as you work it."}</p>
    </form>`;
}

function sitePanel(data) {
  return panel("SITE", siteForm(data), {cls: "rh-site-panel"});
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

function rail(data, esc) {
  if (data.aboard) return `${aboardPanel(data, esc)}${sitePanel(data)}${depositEditor(data, esc)}${depositsList(data, esc)}`;
  return `${sitePanel(data)}${keysPanel(data)}${depositEditor(data, esc)}${depositsList(data, esc)}`;
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
  const material = commodityOf(row);
  const where = row.distance != null ? `${way(row)}${row.n ? ` · #${row.n} to drive` : ""}` : "";
  const timeline = row.depleted && row.regrowth?.text ? `<p class="rh-regrowth${row.regrowth.due ? " due" : ""}">${esc(row.regrowth.text.toUpperCase())}</p>` : "";
  const title = `${row.depleted ? "DEPOSIT · MINED OUT" : "DEPOSIT"}${chosen ? ` · ${esc(String(shortBody(row.system, row.body)).toUpperCase())}` : ""}`;
  return panel(title, `${timeline}<form class="rh-form" data-rhino-form="deposit" data-id="${esc(row.id)}">
      <label><span>COMMODITY</span><input name="materials" list="rh-commodities" value="${esc(material === "Unknown" || material === "Deposit" ? "" : material)}" placeholder="What it holds"></label>
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
    ${where || row.signal != null || row.estimate ? `<p class="rh-dim">${esc(where)}${row.signal != null ? ` · signal ${esc(row.signal)}` : ""}${row.estimate ? ` · ${esc(row.estimate)}` : ""}</p>` : ""}`);
}

const swatch = (name) => window.VoidCompassRhinoDraw ? `rgb(${window.VoidCompassRhinoDraw.commodityColour(name).join(",")})` : "var(--muted)";

function depositsList(data, esc) {
  const rows = data.deposits || [];
  if (!rows.length) return "";
  const list = rows.map((row) => {
    const on = String(row.id) === String(selected) ? " on" : "";
    const worth = (data.map?.deposits || []).find((item) => String(item.id) === String(row.id))?.value;
    return `<li class="${row.depleted ? "mined" : ""}${on}" data-rhino-op="select" data-id="${esc(row.id)}"><i style="background:${swatch(commodityOf(row))}">${row.n || ""}</i>
      <b>${esc(commodityOf(row))}</b><span>${row.rigs ? `${row.rigs}R` : ""}${row.amount ? ` · ${esc(row.amount)}` : ""}${worth ? ` · ~${money(worth)}` : ""}</span><em>${row.distance != null ? distance(row.distance) : ""}</em></li>`;
  }).join("");
  return panel(`DEPOSITS ON ${esc(String(shortBody(data.system, data.body)).toUpperCase())}`, `<ul class="rh-deposits">${list}</ul>`, {note: "numbered in the order to drive them"});
}

// -- MAP: the figures, the map, its line and the rigs ------------------------------------------
// Back aboard: the run, the holds and what's still out.
function aboardFigures(data) {
  const card = data.aboard;
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
  if (n(data.map?.elsewhere)) parts.push(`<span class="dim">+${whole(data.map.elsewhere)} MARKED ELSEWHERE ON THIS BODY · DEPOSITS</span>`);
  return parts.map((part) => `<i>${part}</i>`).join("");
}

// A rig's clock: how long still to go, or READY, once your rigs have taught
// how long they take; until then, how long it's been down.
function rigClock(rig) {
  // A completed collection counts from its last tonne at the rig.
  if (rig.collecting) return {text: "COLLECTING", cls: "collecting", sub: `${n(rig.haul)} t so far · refill timed from the last tonne`};
  const last = n(rig.haul) ? `last ${n(rig.haul)} t` : "";
  const clock = (seconds) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
  const down = Math.max(0, Date.now() / 1000 - n(rig.at));
  if (!n(rig.ready_s)) return {text: clock(down), cls: "learning", sub: ["down so far · learning its time", last].filter(Boolean).join(" · ")};
  // Filling since it went down, or since you last collected from it.
  const filling = Math.max(0, Date.now() / 1000 - n(rig.fill_from || rig.at));
  const left = Math.ceil(n(rig.ready_s) - filling);
  if (left <= 0) return {text: "READY", cls: "ready", sub: last || "collect it"};
  return {text: clock(left), cls: "", sub: ["to READY", last].filter(Boolean).join(" · ")};
}

// A card for each of the six rigs: out (what it's working, how far and which
// way, its clock) or free, with its key to put it down or pick it up.
function rigsGrid(data, esc) {
  const rows = new Map(((data.rigs || {}).rigs || []).map((rig) => [n(rig.slot), rig]));
  const keyed = !data.aboard;
  const order = (data.rigs?.collect_order || []).map((slot) => `#${slot}`).join(" → ");
  const cards = [1, 2, 3, 4, 5, 6].map((slot) => {
    const rig = rows.get(slot);
    const toggle = button(data, "rig", rig ? `RIG ${slot} UP` : `RIG ${slot} DOWN`, keyed ? `rig_${slot}` : "", {slot}, rig ? "down" : "");
    if (!rig) return `<div class="rh-rig free"><header><b>${slot}</b><span>FREE</span></header>${toggle}</div>`;
    const clock = rigClock(rig);
    const where = rig.here ? "HERE" : `${distance(rig.distance_m)} ${compass(rig.bearing)}`;
    return `<div class="rh-rig ${clock.cls}"><header><b>${slot}</b><span>${esc(rig.commodity || "Working")}${n(rig.tonnes) ? ` · ${whole(rig.tonnes)} t` : ""}</span><em>${where}</em></header>
      <strong>${clock.text}</strong><small>${esc(clock.sub)}</small>${toggle}</div>`;
  }).join("");
  return panel("RIGS", `<div class="rh-rigs">${cards}</div>${order ? `<p class="rh-dim">Collect in the order they went down: ${order}</p>` : ""}`,
    {note: keyed ? "the keys work in the Rhino" : "from the ship, the buttons put a rig right by hand", cls: "rh-rigs-panel"});
}

// The map and the keys are for the Rhino (and, back aboard after a run, the
// ship's summary); arriving at a planet in the ship, or on foot, the page waits.
const working = (data) => Boolean(data.in_rhino || data.aboard);

function mapView(data, esc) {
  if (!working(data)) {
    const where = data.on_surface ? `You're at ${esc(shortBody(data.system, data.body))}, not in the Rhino. ` : "";
    const next = data.on_surface ? "Deploy the Rhino" : "Land on a planet and deploy the Rhino";
    return `${targetBar(data, esc)}<div class="rh-waiting">
      <div class="rh-waiting-mark" aria-hidden="true"><i></i><i></i><i></i></div>
      <h3>${data.on_surface ? "Waiting for the Rhino" : "Waiting for you to be on a planet's surface"}</h3>
      <p>${where}${next}: the map, your keys, your rigs and the deposits round you come up here.</p>
      <div class="rh-waiting-links"><button type="button" data-rhino-op="view" data-view="sites">SITES · ${whole((data.saved_sites || []).length)} saved</button><button type="button" data-rhino-op="view" data-view="deposits">DEPOSITS · ${whole((data.sites || []).length)} marked</button><button type="button" data-rhino-op="view" data-view="land">WHERE TO LAND</button></div>
    </div>`;
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
      <div data-part="rigs">${rigsGrid(data, esc)}</div>
    </div>
  </div>`;
}

// -- SITES ---------------------------------------------------------------------------------
const words = () => filter.split(",").map((word) => word.trim().toLowerCase()).filter(Boolean);

function filterBar(data, esc, placeholder) {
  const wanted = words();
  const chips = [...(data.catalogue?.rhino || []), ...(data.catalogue?.found || [])].map((name) => {
    const on = wanted.includes(name.toLowerCase());
    return `<button type="button" class="rh-chip${on ? " on" : ""}" data-rhino-op="filter_chip" data-name="${esc(name)}" aria-pressed="${on}">${esc(name)}</button>`;
  }).join("");
  return `<div class="rh-filterbar"><form class="rh-filter" data-rhino-form="filter"><input name="filter" value="${esc(filter)}" placeholder="${placeholder}"></form>
    ${chips ? `<div class="rh-chips" role="group" aria-label="Rhino commodities">${chips}</div>` : ""}</div>`;
}

// A site's runs as dots on a line, oldest to newest, against ``top`` t/h.
function runStrip(runs, top, esc, width, height, label) {
  const pad = 6;
  const x = (index) => runs.length < 2 ? width / 2 : pad + (index * (width - 2 * pad)) / (runs.length - 1);
  const y = (tph) => height - pad - (n(tph) / top) * (height - 2 * pad);
  const line = runs.length > 1 ? `<polyline points="${runs.map((run, index) => `${x(index).toFixed(1)},${y(run.tph).toFixed(1)}`).join(" ")}"/>` : "";
  const dots = runs.map((run, index) => `<circle cx="${x(index).toFixed(1)}" cy="${y(run.tph).toFixed(1)}" r="4"${index === runs.length - 1 ? ' class="latest"' : ""}><title>${esc(when(run.docked))}: ${whole(run.tph)} t/h · ${whole(run.refined_t)} t in ${whole(run.minutes)} min</title></circle>`).join("");
  return `<svg class="rh-cmp-strip" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(label)}">${line}${dots}</svg>`;
}

// Sites compared (5.8.3): each saved site's usual rate as a bar, its best run
// as a tick on it, and its runs in order as a strip of dots, all on one scale.
// A row picks that site.
const STRIP_RUNS = 12;
function sitesCompared(data, esc) {
  const sites = (data.saved_sites || []).filter((site) => site.runs && (site.runs.runs || []).some((run) => n(run.tph) > 0))
    .sort((a, b) => n(b.runs.usual_tph) - n(a.runs.usual_tph));
  if (!sites.length) return "";
  const top = Math.max(...sites.map((site) => n(site.runs.best_tph)), 1);
  const scale = (value) => Math.max(0, Math.min(100, (n(value) / top) * 100));
  const rows = sites.map((site) => {
    const runs = (site.runs.runs || []).filter((run) => n(run.tph) > 0).slice(0, STRIP_RUNS).reverse();
    const usual = n(site.runs.usual_tph);
    const best = n(site.runs.best_tph);
    const label = `Usual ${whole(usual)} t/h over ${whole(site.runs.count)} run${site.runs.count === 1 ? "" : "s"}, best ${whole(best)} t/h`;
    const on = String(site.id) === String(chosenId(data)) ? " on" : "";
    return `<li class="${site.here ? "here" : ""}${on}" data-rhino-op="site_pick" data-id="${esc(site.id)}">
      <span class="rh-cmp-name"><b>${esc(site.name || "Mining location")}</b><small>${esc(shortBody(site.system, site.body))}${site.runs.best_commodity ? ` · ${esc(site.runs.best_commodity)}` : ""}</small></span>
      <span class="rh-cmp-bar" title="${esc(label)}" aria-label="${esc(label)}"><i style="width:${scale(usual).toFixed(1)}%"></i><em style="left:${scale(best).toFixed(1)}%"></em><b style="left:${Math.max(scale(usual), scale(best)).toFixed(1)}%">${whole(usual)}<small> t/h</small></b></span>
      ${runStrip(runs, top, esc, 132, 26, `Runs at ${site.name}, oldest to newest`)}
    </li>`;
  }).join("");
  const body = `<p class="rh-cmp-key"><span><i class="bar"></i>usual rate</span><span><i class="tick"></i>best run</span><span><i class="dot"></i>each run, oldest to newest (hover for it)</span></p>
    <ul class="rh-cmp">${rows}</ul>`;
  return panel("SITES COMPARED · TONNES AN HOUR", body, {note: `${whole(sites.length)} site${sites.length === 1 ? "" : "s"} with runs · pick one to see it`});
}

function siteMatches(site, wanted) {
  return !wanted.length || wanted.some((word) =>
    `${site.name} ${site.note} ${site.system} ${site.body} ${(site.deposits?.commodities || []).join(" ")} ${Object.keys(site.tonnes || {}).join(" ")}`.toLowerCase().includes(word));
}

function shownSites(data) {
  const wanted = words();
  return (data.saved_sites || []).filter((site) => siteMatches(site, wanted))
    .sort((a, b) => Number(Boolean(b.here)) - Number(Boolean(a.here)) || n(b.updated) - n(a.updated));
}

// The site shown in full: the one you picked, else the one you're at, else the newest.
function chosenId(data) {
  const sites = shownSites(data);
  return (sites.find((site) => String(site.id) === String(chosenSite)) || sites[0])?.id ?? null;
}

function siteList(data, esc) {
  const all = data.saved_sites || [];
  const sites = shownSites(data);
  const chosen = chosenId(data);
  const items = sites.map((site) => {
    const runs = site.runs;
    const meta = [runs ? `${whole(runs.count)} run${runs.count === 1 ? "" : "s"}` : "no runs yet", runs?.usual_tph ? `~${whole(runs.usual_tph)} t/h` : "",
      n(site.earned_total) ? `~${money(site.earned_total)} CR` : ""].filter(Boolean).join(" · ");
    return `<li class="${String(site.id) === String(chosen) ? "on" : ""}${site.here ? " here" : ""}" data-rhino-op="site_pick" data-id="${esc(site.id)}">
      <b>${esc(site.name || "Mining location")}</b>${site.here ? `<em>HERE</em>` : ""}
      <small>${esc(shortBody(site.system, site.body))}${site.signal != null ? ` · signal ${esc(site.signal)}` : ""}</small>
      <span>${esc(meta)}</span><time>${when(site.updated)}</time></li>`;
  }).join("");
  const body = sites.length ? `<ul class="rh-site-list">${items}</ul>`
    : empty(words().length ? "No saved site matches that." : "Press SAVE THIS SITE on the map (or its key) to keep a mining location: its signal, centre, survey, deposits, rig plan and what your rigs took. Leaving a planet with a survey or marked deposits saves it too.");
  return panel("SAVED MINING LOCATIONS", body, {note: `${whole(sites.length)} of ${whole(all.length)}`, cls: "rh-sites-panel"});
}

function siteDetail(data, esc) {
  const site = (data.saved_sites || []).find((row) => String(row.id) === String(chosenId(data)));
  if (!site) return "";
  const ids = {id: site.id, system: site.system, body: site.body};
  const attrs = attrsOf(ids);
  const deposits = site.deposits || {};
  const runs = site.runs;
  const centre = Array.isArray(site.centre) && site.centre.length === 2 ? ` · ${n(site.centre[0]).toFixed(4)}, ${n(site.centre[1]).toFixed(4)}` : "";
  const editing = renaming === site.id;
  const head = editing ? `<form class="rh-form rh-rename" data-rhino-form="site"${attrs}><input name="name" value="${esc(site.name || "")}" maxlength="80" placeholder="Name"><input name="note" value="${esc(site.note || "")}" maxlength="400" placeholder="A note"><button type="submit">KEEP</button></form>`
    : `<h3>${esc(site.name || "Mining location")}${site.here ? `<em>YOU'RE HERE</em>` : ""}</h3>${site.note ? `<p class="rh-note">${esc(site.note)}</p>` : ""}`;
  const actions = `<button type="button" data-rhino-op="site_target"${attrs}>TARGET</button>${site.here ? `<button type="button" data-rhino-op="site_resume"${attrs}>RESUME</button>` : ""}<button type="button" data-rhino-op="copy_system" data-system="${esc(site.system)}">COPY SYSTEM</button><button type="button" data-rhino-op="site_rename_open"${attrs}>${editing ? "CANCEL" : "RENAME"}</button><button type="button" class="${reportOpen === site.id ? "on" : ""}" data-rhino-op="site_report"${attrs} aria-expanded="${reportOpen === site.id}">REPORT</button>${confirmButton(`site-${site.id}`, "DELETE", "site_forget", ids)}`;
  const tiles = `<div class="rh-tiles detail">
    ${tile("SWEPT", site.swept != null ? `${Math.floor(n(site.swept))}%` : "—", site.swept != null ? (site.edge ? (n(site.radius_m) ? `of ${distance(site.radius_m)} round the centre` : "of the survey") : "edge not marked") : "no survey")}
    ${tile("DEPOSITS", n(deposits.live) || n(deposits.mined) ? `${whole(deposits.live)} live` : "—", n(deposits.live) || n(deposits.mined) ? [n(deposits.mined) ? `${whole(deposits.mined)} worked out` : "", n(deposits.rigs) ? `${whole(deposits.rigs)} rig spots` : ""].filter(Boolean).join(" · ") || esc((deposits.commodities || []).join(", ")) : "none marked")}
    ${tile("RUNS", runs ? whole(runs.count) : "—", runs ? `${whole(runs.tonnes)} t in all` : "a run is kept as you dock")}
    ${tile("RATE", runs?.usual_tph ? `${whole(runs.usual_tph)} t/h` : "—", runs?.best_tph ? `usual · best ${whole(runs.best_tph)} t/h` : "")}
    ${tile("WORTH", n(site.earned_total) ? `~${money(site.earned_total)} CR` : "—", n(site.earned_total) ? "what it took, at your sale price or the usual one" : "once something's taken", "worth")}
  </div>`;
  return `<section class="rh-detail">
    <header class="rh-detail-head"><div class="rh-detail-title">${head}<p class="rh-where">${esc(site.system)} · ${esc(shortBody(site.system, site.body))}${site.signal != null ? ` · signal ${esc(site.signal)}` : ""}${centre}</p></div>
      <div class="rh-detail-actions">${actions}</div></header>
    ${reportPanel(data, esc, site)}
    ${tiles}
    <div class="rh-two">${runsPanel(site, esc)}${takenPanel(site, esc)}</div>
    ${siteDeposits(data, esc, site)}
    <p class="rh-dim">TARGET puts its centre on the planet compass; RESUME carries its survey on when you're back on its planet; DELETE asks again before it goes (the deposits you marked there stay). Saved ${when(site.saved)}, last updated ${when(site.updated)}.</p>
  </section>`;
}

// REPORT: the site written up, to copy for Discord or save as a file.
function reportPanel(data, esc, site) {
  if (reportOpen !== site.id) return "";
  const ids = attrsOf({id: site.id, system: site.system, body: site.body});
  const text = data.report?.id === site.id ? data.report.text : "";
  return panel("REPORT", `${text ? `<pre class="rh-report">${esc(text)}</pre>` : empty("Writing it up…")}
    <div class="rh-actions"><button type="button" class="primary" data-rhino-op="site_report_copy"${ids}${text ? "" : " disabled"}>COPY FOR DISCORD</button><button type="button" data-rhino-op="site_report_save"${ids}${text ? "" : " disabled"}>SAVE AS A FILE</button><button type="button" data-rhino-op="site_report"${ids}>CLOSE</button></div>
    <p class="rh-dim">Plain text with bold headings: it pastes straight into a Discord message (one message's worth). SAVE puts it in a folder you choose as a .md file.</p>`, {cls: "rh-report-panel", note: text ? `${whole(text.length)} characters` : ""});
}

function runsPanel(site, esc) {
  const runs = site.runs;
  if (!runs) return panel("RUNS", empty("Each Rhino run worked here is kept as you dock back aboard: how long, what it refined and its tonnes an hour."));
  const best = runs.best_tph;
  const shown = (runs.runs || []).filter((run) => n(run.tph) > 0).slice(0, STRIP_RUNS).reverse();
  const top = Math.max(n(best), 1);
  const list = runs.runs.map((run) => {
    const taken = Object.entries(run.taken || {}).sort((a, b) => n(b[1]) - n(a[1])).map(([name, t]) => `${whole(t)} t ${esc(name)}`).join(" · ");
    return `<li><b>${when(run.docked)}</b><span>${whole(run.minutes)} min · ${whole(run.refined_t)} t${run.tph ? ` · <em class="${run.tph === best ? "best" : ""}">${whole(run.tph)} t/h</em>` : ""}</span><small>${taken}</small></li>`;
  }).join("");
  return panel("RUNS", `${shown.length > 1 ? `<div class="rh-run-chart">${runStrip(shown, top, esc, 320, 54, `Runs at ${site.name}, oldest to newest`)}</div>` : ""}<ul class="rh-runs">${list}</ul>`,
    {note: `best ${whole(best)} t/h${runs.best_commodity ? ` · most ${esc(runs.best_commodity)}` : ""}`});
}

function takenPanel(site, esc) {
  const rows = site.earned || [];
  if (!rows.length) return panel("TAKEN", empty("What your rigs take here, by commodity, and what it's worth."));
  const top = Math.max(...rows.map((row) => n(row.credits) || 0), 1);
  const list = rows.map((row) => `<li><i style="background:${swatch(row.commodity)}"></i><b>${esc(row.commodity)}</b><span>${whole(row.t)} t</span>
      <strong>${row.credits ? `~${money(row.credits)} CR` : "no price yet"}</strong><u><s style="width:${((n(row.credits) / top) * 100).toFixed(1)}%"></s></u></li>`).join("");
  return panel("TAKEN", `<ul class="rh-earned">${list}</ul>${n(site.earned_total) ? `<p class="rh-earned-total"><span>WORTH IN ALL</span><b>~${money(site.earned_total)} CR</b></p>` : ""}
    <p class="rh-dim">At what you've been paid for it, else its usual price.</p>`);
}

// The deposits saved with the site, from every deposit you've marked.
function siteDeposits(data, esc, site) {
  const ids = new Set((site.deposits?.ids || []).map(String));
  const rows = (data.sites || []).filter((row) => ids.has(String(row.id)));
  if (!rows.length) return "";
  const table = `<table class="rh-table"><thead><tr><th>COMMODITY</th><th>RIGS</th><th>AMOUNT</th><th>DENSITY</th><th>NOTES</th><th></th></tr></thead><tbody>${rows.map((row) =>
    `<tr class="${row.depleted ? "mined" : ""}"><td><i class="rh-swatch" style="background:${swatch(commodityOf(row))}"></i>${esc(commodityOf(row))}</td><td>${row.rigs || "—"}</td><td>${row.depleted ? (row.regrowth?.due ? `<b class="rh-due">Recheck due</b>` : "Worked out") : esc(row.amount || "—")}</td><td>${esc(row.density || "—")}</td><td>${esc(row.notes || "")}</td>
     <td class="rh-row-actions">${editButton(row, "site")}<button type="button" data-rhino-op="deposit_navigate" data-id="${esc(row.id)}">TARGET</button></td></tr>${editRow(data, esc, row, "site", 6)}`).join("")}</tbody></table>`;
  return panel("DEPOSITS AT THIS SITE", table, {note: `${whole(rows.length)}`});
}

function sitesView(data, esc) {
  const filtered = words().length > 0;
  return `${targetBar(data, esc)}${filterBar(data, esc, "Find a site: name, system, body or commodity; commas mean any of them")}
    ${filtered ? "" : sitesCompared(data, esc)}
    <div class="rh-sites">${siteList(data, esc)}${siteDetail(data, esc)}</div>`;
}

// -- DEPOSITS ---------------------------------------------------------------------------
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
function depletedPanel(data, esc, wanted) {
  const all = (data.sites || []).filter((row) => row.depleted);
  const rows = all.filter((row) => !wanted.length || wanted.some((word) => `${row.system} ${row.body} ${row.materials}`.toLowerCase().includes(word)))
    .sort((a, b) => (REGROWTH_ORDER[a.regrowth?.state] ?? 9) - (REGROWTH_ORDER[b.regrowth?.state] ?? 9) || n(b.regrowth?.age_days) - n(a.regrowth?.age_days));
  if (!all.length) return "";
  const due = all.filter((row) => row.regrowth?.due).length;
  const table = rows.length ? `<table class="rh-table rh-depleted"><thead><tr><th>COMMODITY</th><th>WHERE</th><th>WORKED OUT</th><th>NEXT</th><th></th></tr></thead><tbody>${rows.map((row) => {
      const info = row.regrowth || {};
      const next = {due: "Recheck due", expired: "Mark comes off", waiting: `Mark off in ${n(info.off_in_days)} d`, unknown: "Date not known",
        fresh: `Look in ${Math.max(0, 14 - n(info.age_days))} d`}[info.state] || "—";
      return `<tr class="${info.due ? "due" : ""}"><td><i class="rh-swatch" style="background:${swatch(commodityOf(row))}"></i>${esc(commodityOf(row))}</td><td>${esc(row.system)}<small>${esc(shortBody(row.system, row.body))}</small></td>
        <td>${info.age_days != null ? `${whole(info.age_days)} days ago` : "—"}${info.looks ? `<small>checked ${info.looks}×</small>` : ""}</td><td>${esc(next)}</td>
        <td class="rh-row-actions">${editButton(row, "depleted")}<button type="button" data-rhino-op="deposit_navigate" data-id="${esc(row.id)}">TARGET</button><button type="button" data-rhino-op="deposit_regrown" data-id="${esc(row.id)}">REGROWN</button>${confirmButton(`del-${row.id}`, "DELETE", "deposit_delete", {id: row.id})}</td></tr>${editRow(data, esc, row, "depleted", 5)}`;
    }).join("")}</tbody></table>` : empty("No worked-out deposit matches that.");
  return panel("WORKED-OUT DEPOSITS", `${table}<p class="rh-dim">Deposits grow back, nobody knows quite how fast. Two weeks after you work one out it's due a look: MINED OUT on it (or STILL DEPLETED here) if it's still empty, and the mark comes off a week later. A rig refining it again marks it grown back by itself.</p>`,
    {note: due ? `${whole(due)} due a look` : `${whole(all.length)}`, cls: due ? "rh-due-panel" : ""});
}

function depositsView(data, esc) {
  const wanted = words();
  const rows = (data.sites || []).filter((row) => !wanted.length || wanted.some((word) =>
    `${row.system} ${row.body} ${row.materials}`.toLowerCase().includes(word)));
  const here = String(data.body || "").toLowerCase();
  const table = rows.length ? `<table class="rh-table"><thead><tr><th>COMMODITY</th><th>SYSTEM</th><th>BODY</th><th>RIGS</th><th>AMOUNT</th><th>DENSITY</th><th>SIGNAL</th><th></th></tr></thead><tbody>${rows.map((row) =>
    `<tr class="${row.depleted ? "mined" : ""}${String(row.body || "").toLowerCase() === here ? " here" : ""}"><td><i class="rh-swatch" style="background:${swatch(commodityOf(row))}"></i>${esc(commodityOf(row))}</td><td>${esc(row.system)}</td><td>${esc(shortBody(row.system, row.body))}</td><td>${row.rigs || "—"}</td><td>${row.depleted ? `${row.regrowth?.due ? "<b class=\"rh-due\">Recheck due</b>" : "Depleted"}${row.regrowth?.age_days != null ? `<small>${whole(row.regrowth.age_days)} days</small>` : ""}` : esc(row.amount || "—")}</td><td>${esc(row.density || "—")}</td><td>${row.signal ?? "—"}</td>
     <td class="rh-row-actions">${editButton(row, "all")}<button type="button" data-rhino-op="copy_system" data-system="${esc(row.system)}">COPY SYSTEM</button><button type="button" data-rhino-op="deposit_navigate" data-id="${esc(row.id)}">TARGET</button>${confirmButton(`del-${row.id}`, "DELETE", "deposit_delete", {id: row.id})}</td></tr>${editRow(data, esc, row, "all", 8)}`).join("")}</tbody></table>`
    : empty(wanted.length ? "Nothing marked matches that." : "Deposits you mark show here, on every planet.");
  return `${targetBar(data, esc)}${filterBar(data, esc, "Find a deposit: system, body or commodity; commas mean any of them")}
    ${depletedPanel(data, esc, wanted)}${panel("EVERY DEPOSIT YOU'VE MARKED", table, {note: `${whole(rows.length)} of ${whole((data.sites || []).length)}`})}`;
}

// -- WHERE TO LAND -------------------------------------------------------------------------
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
  if (reportOpen != null && !(last.saved_sites || []).some((site) => site.id === reportOpen)) reportOpen = null;
  const skeleton = `${view}|${working(last) ? 1 : 0}|${last.aboard ? 1 : 0}`;
  // The map keeps its canvas between snapshots: only the parts round it are redrawn.
  if (root.dataset.skeleton !== skeleton || view !== "map") {
    const body = {map: mapView, sites: sitesView, deposits: depositsView, land: landView}[view] || mapView;
    const markup = `<div data-part="status">${statusStrip(last, esc)}</div><div data-part="tabs">${tabsBar(last)}</div><div class="rh-body rh-view-${view}">${body(last, esc)}</div>`;
    if (!force && view !== "map" && root.dataset.markup === markup) return;
    if (!force && view !== "map" && root.contains(document.activeElement) && document.activeElement.matches("input")) return;
    root.dataset.skeleton = skeleton;
    root.dataset.markup = markup;
    root.innerHTML = markup;
    drawnParts = {};
    bindMap(root);
  } else {
    renderPart(root, "status", statusStrip(last, esc));
    renderPart(root, "tabs", tabsBar(last));
    renderPart(root, "rail", rail(last, esc));
    renderPart(root, "target", targetBar(last, esc));
    renderPart(root, "figures", figures(last));
    renderPart(root, "line", mapLine(last, esc));
    renderPart(root, "rigs", rigsGrid(last, esc));
  }
  drawMap();
}

export function resetRhino() {
  selected = null; filter = ""; renaming = null; sitesEditing = null; chosenSite = null; reportOpen = null; view = "map";
  pan = null; chosenHalf = null; fitted = null; drawnParts = {};
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
  if (op === "site_pick") {
    chosenSite = control.dataset.id;
    renaming = null;
    renderRhino(last, ui, true);
    ui.byId("rhino-workspace")?.querySelector(".rh-detail")?.scrollIntoView({block: "nearest"});
    return true;
  }
  if (op === "site_open") { chosenSite = control.dataset.id; view = "sites"; renderRhino(last, ui, true); return true; }
  if (op === "site_report") {
    // REPORT opens its write-up under the site's name; the deck writes it.
    reportOpen = reportOpen === control.dataset.id ? null : control.dataset.id;
    renderRhino(last, ui, true);
  }
  if (op === "site_report_save") {
    const ids = {id: control.dataset.id, system: control.dataset.system, body: control.dataset.body};
    (async () => {
      try {
        const folder = await window.pywebview?.api?.choose_folder?.();
        if (folder) send(ui, op, {...ids, path: folder});
      } catch (error) {
        console.warn("No folder picker", error);
      }
    })();
    return true;
  }
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
      renderRhino(last, ui, true);
      setTimeout(() => { if (confirming.key === id) { drawnParts = {}; renderRhino(last, lastUi, true); } }, 4100);
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
