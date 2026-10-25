// Expeditions (5.6.1): Mission Control, rebuilt. A named trip with a route of
// legs Spansh plots, objectives the journal ticks off, the data you carry,
// your supplies and a streak, a day-by-day log, and at the end its own Void
// Wrapped and a replay on the Atlas. The waypoint route stays the one route the
// HUD follows: FLY IT sends a leg there.

import {routeMarkup} from "./explore.js";

const VIEWS = [["overview", "OVERVIEW"], ["route", "ROUTE"], ["places", "PLACES"], ["objectives", "OBJECTIVES"], ["log", "LOG"], ["wrapped", "WRAPPED"]];
const KINDS = [["stop", "Stop"], ["destination", "Destination"], ["home", "Home"], ["carrier", "Carrier jump"]];
const STATUS = {active: "ACTIVE", paused: "PAUSED", completed: "COMPLETE", failed: "FAILED"};

// "+ 0" turns a negative zero into 0, which would otherwise print as "-0".
const n = (value) => (Number.isFinite(Number(value)) ? Number(value) + 0 : 0);
const whole = (value) => Math.round(n(value)).toLocaleString("en-GB");
const ly = (value) => `${n(value).toLocaleString("en-GB", {maximumFractionDigits: n(value) >= 100 ? 0 : 1})} ly`;
const cr = (value) => {
  const v = n(value);
  return v >= 1e9 ? `${(v / 1e9).toFixed(2)} BN CR` : v >= 1e6 ? `${(v / 1e6).toFixed(1)} M CR` : `${whole(v)} CR`;
};
const day = (stamp) => String(stamp || "").slice(0, 10);

let view = "overview";
let selected = "";
let creating = false;
let renaming = "";
let last = {};
let drawn = "";
let confirming = {key: "", until: 0};
let placeFilter = "all";
let addingPlace = false;
let fileNote = "";
const drafts = {};

const field = (form, name, value = "") => (drafts[form] && name in drafts[form] ? drafts[form][name] : value);
const send = (ui, operation, extra = {}) => ui.command("workspace", {page: "mission", operation, ...extra});

function panel(title, body, {note = "", cls = ""} = {}) {
  return `<section class="ex-panel${cls ? ` ${cls}` : ""}"><header><h4>${title}</h4>${note ? `<span>${note}</span>` : ""}</header>${body}</section>`;
}

function tile(label, value, detail = "", tone = "") {
  return `<div class="ex-tile${tone ? ` ${tone}` : ""}"><span>${label}</span><b>${value}</b>${detail ? `<small>${detail}</small>` : ""}</div>`;
}

function bar(share, tone = "") {
  return `<i class="ex-bar ${tone}"><b style="width:${(Math.max(0, Math.min(1, n(share))) * 100).toFixed(1)}%"></b></i>`;
}

function button(label, op, extra = {}, esc, cls = "") {
  const data = Object.entries(extra).map(([key, value]) => ` data-${key}="${esc(String(value))}"`).join("");
  return `<button type="button" class="${cls}" data-ex-op="${op}"${data}>${label}</button>`;
}

function confirmButton(key, label, op, extra, esc) {
  const armed = confirming.key === key && Date.now() < confirming.until;
  return button(armed ? "SURE? CLICK AGAIN" : label, op, {...extra, "confirm-key": key}, esc, `danger-action${armed ? " armed" : ""}`);
}

function options(list, chosen) {
  return list.map(([value, label]) => `<option value="${value}"${String(value) === String(chosen) ? " selected" : ""}>${label}</option>`).join("");
}

// -- your expeditions and a new one ------------------------------------------------------------------
// A strip across the top (5.6.1, laid out again): the chosen trip gets the
// whole width below it.
function tripBar(data, esc) {
  const chips = (data.expeditions || []).map((row) => `<button type="button" class="ex-trip${row.id === selected ? " active" : ""}" data-ex-op="select" data-id="${esc(row.id)}">
      <i class="${esc(row.status)}"></i><span><b>${esc(row.name)}</b><small>${STATUS[row.status] || esc(row.status)}${row.destination ? ` · ${esc(row.destination)}` : ""}</small></span></button>`).join("");
  const form = creating ? `<form class="ex-form ex-create" data-ex-form="create">
      <label><span>NAME</span><input name="name" maxlength="100" placeholder="Colonia run" value="${esc(field("create", "name"))}" required></label>
      <label><span>DESTINATION</span><input name="destination" maxlength="120" placeholder="Colonia" value="${esc(field("create", "destination"))}"></label>
      <label><span>HOME AFTERWARDS</span><input name="return_system" maxlength="120" placeholder="${esc(data.here || "Sol")}" value="${esc(field("create", "return_system"))}"></label>
      <label><span>WHAT IT'S FOR</span><input name="description" maxlength="400" value="${esc(field("create", "description"))}"></label>
      <div class="ex-actions"><button type="submit" class="primary">START IT</button>${button("CANCEL", "new", {}, esc)}
        <small>It starts from ${esc(data.here || "where you are")}, now. Starting it pauses any other.</small></div>
      ${(data.examples || []).length ? `<div class="ex-examples"><span>OR ADD A REAL ONE</span>${data.examples.map((example) => `<div class="ex-line"><b>${esc(example.name)}</b>
        <small>${esc(example.description)}</small>${button("ADD IT", "add_example", {example: example.key}, esc)}</div>`).join("")}</div>` : ""}</form>` : "";
  return `<nav class="ex-trips" aria-label="Your expeditions">${chips}${button(creating ? "CANCEL" : "+ NEW EXPEDITION", "new", {}, esc, creating ? "" : "primary")}</nav>${form}`;
}

// -- the selected expedition -------------------------------------------------------------------------
// The voyage as a track: the start, each leg, the way home. A long community
// route keeps its ends and the stops around the next one; the rest fold into
// "N more".
function voyage(row, esc) {
  const legs = row.legs || [];
  const nextIndex = row.live?.progress?.next_index ?? legs.findIndex((leg) => !leg.reached);
  const stops = [{system: row.start_system || "—", kind: "start", reached: true},
    ...legs.map((leg, index) => ({...leg, next: index === nextIndex}))];
  if (stops.length < 2) return "";
  const keep = new Set([0, 1, stops.length - 1, stops.length - 2, nextIndex, nextIndex + 1, nextIndex + 2]);
  const shown = [];
  stops.forEach((stop, index) => {
    if (stops.length <= 9 || keep.has(index)) shown.push(stop);
    else if (shown.at(-1)?.fold) shown.at(-1).fold += 1;
    else shown.push({fold: 1, reached: stop.reached});
  });
  const kind = (stop) => stop.kind === "start" ? "Start" : (KINDS.find(([key]) => key === stop.kind) || [0, stop.kind])[1];
  return `<ol class="ex-voyage">${shown.map((stop) => stop.fold
    ? `<li class="fold${stop.reached ? " reached" : ""}"><i></i><b>${whole(stop.fold)} more</b><small>&nbsp;</small></li>`
    : `<li class="${stop.reached ? "reached" : stop.next ? "next" : "ahead"} kind-${esc(stop.kind || "")}" title="${esc([stop.body, stop.system].filter(Boolean).join(" · "))}"><i></i>
      <b>${esc(legName(stop))}</b><small>${stop.next ? "NEXT" : esc(kind(stop))}</small></li>`).join("")}</ol>`;
}

function hero(row, data, esc) {
  const live = row.live || {};
  const progress = live.progress || {};
  const statusButtons = row.status === "active"
    ? `${button("PAUSE", "status", {status: "paused", "expedition-id": row.id}, esc)}${button("COMPLETE", "status", {status: "completed", "expedition-id": row.id}, esc, "primary")}`
    : row.status === "failed" ? "" : button("RESUME", "status", {status: "active", "expedition-id": row.id}, esc, "primary");
  const job = data.job?.text ? `<p class="ex-job ${esc(data.job.tone || "")}${data.job.busy ? " busy" : ""}">${esc(data.job.text)}</p>` : "";
  const figure = progress.share != null && row.status === "active"
    ? `<b>${Math.round(n(progress.share) * 100)}%</b><small>${progress.to_go_ly ? `${ly(progress.to_go_ly)} to go` : progress.next ? "find where the legs are to measure it" : "every leg reached"}</small>`
    : `<b>${ly(row.stats?.ly)}</b><small>flown</small>`;
  const title = renaming === row.id
    ? `<form class="ex-form ex-rename" data-ex-form="rename" data-expedition-id="${esc(row.id)}">
      <label><span>NAME</span><input name="name" maxlength="100" value="${esc(field("rename", "name", row.name))}" required></label>
      <label><span>WHAT IT'S FOR</span><input name="description" maxlength="400" value="${esc(field("rename", "description", row.description || ""))}"></label>
      <div class="ex-actions"><button type="submit" class="primary">SAVE</button>${button("CANCEL", "rename_form", {}, esc)}</div></form>`
    : `<h3>${esc(row.name)}</h3>${row.description ? `<span>${esc(row.description)}</span>` : ""}`;
  return `<section class="ex-hero ${esc(row.status)}">
    <div class="ex-hero-head"><div class="ex-hero-title"><small>${STATUS[row.status] || esc(row.status)}${row.ironman ? " · IRONMAN" : ""} · SINCE ${esc(day(row.started))}</small>
      ${title}
      ${row.example ? `<p class="ex-credit">${esc(row.credit)}${row.source_url ? ` · ${button("SOURCE PAGE", "open_link", {url: row.source_url}, esc, "ex-linkish")}` : ""}</p>` : ""}</div>
      <div class="ex-hero-figure">${figure}</div></div>
    ${voyage(row, esc)}
    <div class="ex-actions">${statusButtons}${button("EDIT NAME", "rename_form", {id: row.id}, esc)}${confirmButton(`delete-${row.id}`, "DELETE", "delete", {"expedition-id": row.id}, esc)}</div>
  </section>${job}`;
}

// A stop on a planet goes by its place's name (or the body's); others by the system.
const legName = (leg) => leg.body ? leg.note || leg.body : leg.system;

// What a leg needs said about it: plotted or not, a dry neutron run, a carrier short of tritium.
// The planet to land on (5.6.5), as the Expedition overlay shows it: which
// step you're at, and the body's facts from your scans.
function landOn(guide, esc) {
  if (!guide || !guide.body) return "";
  const words = {jump: "JUMP THERE FIRST", fly: "FLY TO IT", land: "LAND", ground: "ON THE GROUND", arrived: "YOU'RE HERE"};
  const info = guide.info || {};
  const facts = [info.class ? info.class.replace(/ body$/i, "") : "", info.ls != null ? `${Math.round(info.ls).toLocaleString("en-GB")} Ls` : "",
    info.gravity != null ? `${Number(info.gravity).toFixed(2)} g` : "", info.temp != null ? `${Math.round(info.temp)} K` : "",
    guide.info ? (info.atmosphere || "no atmosphere") : ""].filter(Boolean);
  return `<p class="ex-land"><b>LAND ON ${esc(guide.short)}</b> · ${esc(words[guide.stage] || "")}${facts.length ? `<br><span>${esc(facts.join(" · "))}</span>` : ""}</p>`;
}

function legNotes(leg, esc) {
  const plot = leg.plot;
  const runs = (leg.fuel_runs || []).map((run) => `<small class="ex-warn">No star to scoop: ${run.jumps} neutron jumps from ${esc(run.from)}</small>`).join("");
  const carrier = leg.kind === "carrier" && leg.carrier ? `<small>${whole(leg.carrier.jumps)} carrier jumps · ${whole(leg.carrier.tritium)} t tritium${leg.carrier.short ? ` · <em class="ex-warn">${whole(leg.carrier.short)} t short</em>` : ""} · about ${whole(leg.carrier.minutes)} min</small>` : "";
  const plotted = leg.reached ? `<small>Reached ${esc(day(leg.reached))}</small>`
    : plot ? `<small>${whole(plot.total_jumps)} jumps plotted${plot.range ? ` at ${n(plot.range).toFixed(1)} ly` : ""}</small>` : `<small>Not plotted yet</small>`;
  const target = leg.lat != null ? `<small class="ex-site">Landing site · ${n(leg.lat).toFixed(4)}, ${n(leg.lon).toFixed(4)}</small>` : "";
  return `${target}${plotted}${leg.coords ? "" : `<small class="ex-warn">Place unknown: FIND WHERE THEY ARE</small>`}${leg.note && !leg.body ? `<small>${esc(leg.note)}</small>` : ""}${runs}${carrier}`;
}

function overview(row, data, esc) {
  const live = row.live;
  const s = row.stats || {};
  const found = `<div class="ex-tiles">${tile("FSS", whole(s.fss))}${tile("MAPPED", whole(s.dss))}${tile("BIOLOGY", whole(s.bio))}
    ${tile("CODEX", whole(s.codex), s.codex_new ? `${whole(s.codex_new)} new to you` : "")}${tile("FIRST DISCOVERIES", whole(s.firsts))}
    ${tile("FIRST FOOTFALLS", whole(s.footfalls))}${tile("REGIONS", whole(s.regions))}${tile("FURTHEST", ly(s.furthest), "from the start")}</div>`;
  const pet = row.pet ? `<section class="ex-pet"><small>${row.pet.aboard ? "ABOARD" : "CAME ALONG"}</small>
      <b>${esc(row.pet.name)}</b>${row.pet.badge ? `<span class="ex-pet-badge">✦ ${esc(row.pet.badge)}</span>` : ""}
      ${(row.pet.lines || []).length ? `<ul>${row.pet.lines.map((line) => `<li>${esc(line)}</li>`).join("")}</ul>` : `<p class="ex-dim">Watching the stars go by.</p>`}</section>` : "";
  if (!live) {
    return `${pet}<div class="ex-tiles big">${tile("FLOWN", ly(s.ly), `${whole(s.jumps)} jumps`)}${tile("SYSTEMS", whole(s.systems))}
      ${tile("SESSIONS", whole(s.sessions))}${tile("STREAK", `${whole(row.streak?.jumps)} jumps`, `best ${whole(row.streak?.best_jumps)}`)}</div>
      ${panel("WHAT YOU FOUND", found)}<p class="ex-dim">${row.status === "paused" ? "RESUME it to follow it live: the route, the data at risk and your supplies." : ""}</p>`;
  }
  const progress = live.progress || {};
  const eta = live.eta;
  const risk = live.risk || {};
  const streak = live.streak || {};
  const next = progress.next ? (row.legs || []).find((leg) => leg.id === progress.next.id) || progress.next : null;
  const nextCard = next ? `<section class="ex-next"><small>NEXT STOP · ${esc((KINDS.find(([key]) => key === next.kind) || [0, next.kind])[1]).toUpperCase()}</small>
      <h3>${esc(legName(next))}</h3>${next.body ? `<p class="ex-dim">${esc(next.note ? next.body : next.system)}</p>` : ""}${landOn(live.guide, esc)}<div class="ex-notes">${legNotes(next, esc)}</div>
      <div class="ex-actions">${button("FLY IT", "use_route", {"expedition-id": row.id, "leg-id": next.id}, esc, "primary")}${button("PLOT", "plot_leg", {"expedition-id": row.id, "leg-id": next.id}, esc)}</div></section>`
    : `<section class="ex-next"><small>NEXT STOP</small><h3>${(row.legs || []).length ? "Every leg reached" : "No legs yet"}</h3>
      <p class="ex-dim">${(row.legs || []).length ? "COMPLETE it when you're home, and it's told back as its own Void Wrapped." : "Add the stops on the way in ROUTE."}</p></section>`;
  const top = `${pet}<div class="ex-top">${nextCard}<div class="ex-tiles ex-figures">
    ${tile("ROUTE", progress.share != null ? `${Math.round(n(progress.share) * 100)}%` : "—", progress.total_ly ? `${ly(progress.done_ly)} of ${ly(progress.total_ly)}` : "Place the legs to measure it")}
    ${tile("AT YOUR PACE", eta ? `${whole(eta.hours)} h` : "—", eta ? `about ${whole(eta.jumps)} jumps${eta.sessions ? ` · ${eta.sessions} session${eta.sessions === 1 ? "" : "s"}` : ""}` : "after a few jumps")}
    ${tile("STREAK", `${whole(streak.jumps)} jumps`, `${ly(streak.ly)}${streak.days != null ? ` · ${streak.days} days` : ""} since the last close call`)}</div></div>`;
  const share = risk.threshold ? Math.min(1, n(risk.value) / n(risk.threshold)) : 0;
  const sellers = (data.sell || []).map((row) => `<div class="ex-line"><b>${esc(row.station)}</b><small>${esc(row.service)} · ${esc(row.system)} · ${ly(row.distance)}${row.large_pad ? " · L pad" : ""}</small>
      ${button("ROUTE THERE", "route_to", {system: row.system}, esc)}</div>`).join("");
  const riskPanel = panel("DATA AT RISK", `<div class="ex-risk${risk.over ? " over" : ""}"><b>${cr(risk.value)}</b>${bar(share, risk.over ? "red" : "yellow")}
      <small>${risk.threshold ? `Nudges at ${cr(risk.threshold)} (Settings › Flight)` : "Nudges are off (Settings › Flight)"}${risk.hull != null ? ` · hull ${Math.round(n(risk.hull))}%` : ""}${risk.home_ly != null ? ` · ${ly(risk.home_ly)} from ${esc(risk.home || "home")}` : ""}</small></div>
      <div class="ex-actions">${button("GO HOME", "go_home", {"expedition-id": row.id}, esc)}${button("SELL NOW", "sell_now", {"expedition-id": row.id}, esc, "primary")}</div>${sellers}`,
    {note: "Unsold exploration and biology, lost if the ship is"});
  const supplies = (live.supplies?.rows || []).map((row) => `<div class="ex-line${row.low ? " low" : ""}"><b>${esc(row.name)}</b><em>${esc(row.value)}</em><small>${esc(row.detail)}</small></div>`).join("");
  const suppliesPanel = panel("SHIP AND SUPPLIES", supplies || `<p class="ex-dim">Your loadout arrives with the next Loadout event.</p>`,
    {note: (live.supplies?.low || []).length ? `Running low: ${esc(live.supplies.low.join(", "))}` : "Nothing running low"});
  const ironman = `<label class="ex-switch"><input type="checkbox" data-ex-op="ironman" data-expedition-id="${esc(row.id)}"${row.ironman ? " checked" : ""}>
    <span><b>IRONMAN</b><small>One life: the expedition fails if the ship is lost.</small></span></label>`;
  // A place the Watcher has asked to be taken (5.6.1).
  const wish = data.pilgrimage ? panel("THE WATCHER WANTS TO GO TO…", `<div class="ex-line"><b>${esc(data.pilgrimage.words)}</b><small>${esc(data.pilgrimage.how)}${data.pilgrimage.system ? ` · ${esc(data.pilgrimage.system)}` : ""}</small>
      ${button("ADD AS AN OBJECTIVE", "add_pilgrimage", {"expedition-id": row.id}, esc, "primary")}</div>`, {note: "A chapter of its story waits there"}) : "";
  return `${top}${wish}<div class="ex-grid">${riskPanel}${suppliesPanel}</div>${panel("WHAT YOU FOUND", found)}${ironman}`;
}

function routeView(row, data, esc, ui) {
  const legs = row.legs || [];
  const nextIndex = row.live?.progress?.next_index ?? legs.findIndex((leg) => !leg.reached);
  const rows = legs.map((leg, index) => `<li class="ex-leg ${leg.reached ? "reached" : index === nextIndex ? "next" : "ahead"}">
      <i>${index + 1}</i>
      <div><p><b>${esc(legName(leg))}</b>${leg.body && leg.note ? `<em>${esc(leg.body)}</em>` : ""}<em>${esc((KINDS.find(([key]) => key === leg.kind) || [0, leg.kind])[1])}</em>${index === nextIndex ? "<em class=\"now\">NEXT</em>" : ""}</p>
        <div class="ex-notes">${legNotes(leg, esc)}</div></div>
      <div class="ex-leg-actions">${leg.reached ? "" : `${button("FLY IT", "use_route", {"expedition-id": row.id, "leg-id": leg.id}, esc, "primary")}${button("PLOT", "plot_leg", {"expedition-id": row.id, "leg-id": leg.id}, esc)}`}
        ${button("↑", "move_leg", {"expedition-id": row.id, "leg-id": leg.id, step: -1}, esc, "ex-icon")}${button("↓", "move_leg", {"expedition-id": row.id, "leg-id": leg.id, step: 1}, esc, "ex-icon")}
        ${button("✕", "remove_leg", {"expedition-id": row.id, "leg-id": leg.id}, esc, "ex-icon")}</div></li>`).join("");
  const table = `<ol class="ex-legs"><li class="ex-leg reached start"><i>0</i><div><p><b>${esc(row.start_system || "—")}</b><em>Start</em></p>
    <div class="ex-notes"><small>Where it began, ${esc(day(row.started))}</small></div></div><div></div></li>${rows}</ol>`;
  const add = `<form class="ex-inline" data-ex-form="add_leg" data-expedition-id="${esc(row.id)}">
    <input name="system" maxlength="120" placeholder="Add a system" value="${esc(field("add_leg", "system"))}" required>
    <select name="kind">${options(KINDS, field("add_leg", "kind", "stop"))}</select><button type="submit">ADD LEG</button></form>`;
  const tools = `<div class="ex-actions">${button("FLY THE NEXT LEG", "use_route", {"expedition-id": row.id}, esc, "primary")}${button("FIND WHERE THEY ARE", "locate", {"expedition-id": row.id}, esc)}</div>
    <p class="ex-dim">PLOT asks Spansh for a neutron route at your jump range${data.jump_range ? ` (${n(data.jump_range).toFixed(1)} ly)` : ""}; a carrier leg plots a carrier route. FLY IT makes the leg your waypoint route, which the HUD, the minimap and COPY NEXT follow.</p>`;
  const importer = `<form class="ex-form" data-ex-form="import" data-expedition-id="${esc(row.id)}">
    <label><span>IMPORT A COMMUNITY EXPEDITION</span><textarea name="text" rows="4" placeholder="One system per line, a CSV with a System column (and x, y, z if it has them), or a Spansh results link">${esc(field("import", "text"))}</textarea></label>
    <div class="ex-actions"><button type="submit">IMPORT</button><button type="button" data-ex-file-open="import">LOAD A FILE…</button>
      <input type="file" accept=".txt,.csv,.tsv,.json,text/plain,text/csv,application/json" data-ex-file="import" hidden>
      <small>${fileNote ? esc(fileNote) : "A list, a CSV (System, and Body, Latitude, Longitude, Name, Notes if it has them), a JSON list or a Spansh link. It replaces the stops (your way home stays). Landing sites and named places become places too."}</small></div></form>`;
  // The waypoint route itself (Explore & Survey's ROUTE until 5.6.1): what the
  // HUD, the minimap and COPY NEXT follow, with the NavRoute and the plotter.
  const routeUi = {...ui, number: (value, fallback = 0) => (Number.isFinite(Number(value)) ? Number(value) : fallback)};
  const waypoints = `<div class="explore-columns explore-route-grid">${routeMarkup(data.route_tools || {}, routeUi)}</div>`;
  return `${panel("THE ROUTE", `${table}${add}${tools}`, {note: `${legs.length} leg${legs.length === 1 ? "" : "s"}`})}
    ${panel("YOUR WAYPOINT ROUTE", waypoints, {note: "Elite's plotted route, your waypoints and the neutron plotter"})}${panel("IMPORT", importer)}`;
}

function objectivesView(row, data, esc) {
  const items = (row.objectives || []).map((objective) => `<div class="ex-objective${objective.complete ? " done" : ""}">
      ${button(objective.complete ? "✓" : "○", "toggle_objective", {"expedition-id": row.id, "objective-id": objective.id}, esc, "ex-check")}
      <span><b>${esc(objective.title)}</b>${objective.count > 1 ? `${bar(objective.progress / objective.count, objective.complete ? "green" : "")}<small>${whole(objective.progress)} / ${whole(objective.count)}</small>` : ""}</span>
      ${button("✕", "remove_objective", {"expedition-id": row.id, "objective-id": objective.id, confirmed: 1}, esc)}</div>`).join("");
  const add = `<form class="ex-inline" data-ex-form="add_objective" data-expedition-id="${esc(row.id)}">
    <select name="kind">${options(data.kinds || [], field("add_objective", "kind", "codex_new_count"))}</select>
    <input name="target" maxlength="200" placeholder="Target (a system, species…)" value="${esc(field("add_objective", "target"))}">
    <input name="count" type="number" min="1" max="100000" value="${esc(field("add_objective", "count", "1"))}"><button type="submit">ADD</button></form>`;
  const templates = (data.templates || []).map((template) => `<div class="ex-line"><b>${esc(template.name)}</b><small>${esc(template.tier)} · ${esc(template.description)}</small>
      ${button("ADD THESE", "template", {"expedition-id": row.id, template: template.key}, esc)}</div>`).join("");
  const done = (row.objectives || []).filter((objective) => objective.complete).length;
  return `${panel("OBJECTIVES", `${items || `<p class="ex-dim">No objectives yet. The journal ticks them off as you fly.</p>`}${add}`, {note: `${done} of ${(row.objectives || []).length} done`})}
    ${panel("READY-MADE SETS", templates)}`;
}

function logView(row, data, esc, ui) {
  const days = [...(row.days || [])].reverse().map((entry) => `<article class="ex-day"><header><b>${esc(entry.day)}</b>
      <small>${entry.jumps ? `${whole(entry.jumps)} jumps · ${ly(entry.ly)}${entry.from ? ` · ${esc(entry.from)} → ${esc(entry.to)}` : ""}` : "No jumps"}</small></header>
      ${(entry.highlights || []).map((line) => `<p>${esc(line)}</p>`).join("")}
      <form class="ex-inline" data-ex-form="day_note" data-expedition-id="${esc(row.id)}" data-day="${esc(entry.day)}">
        <input name="text" maxlength="2000" placeholder="Your note for the day" value="${esc(field(`note-${entry.day}`, "text", entry.note || ""))}"><button type="submit">SAVE</button></form></article>`).join("");
  const album = (row.album || []).map((photo) => `<figure class="ex-photo"><img src="${ui.apiUrl(photo.kind === "postcard" ? `/media/postcard-thumb/${photo.id}.jpg` : `/media/shot-thumb/${photo.id}.jpg`)}" alt="" loading="lazy">
      <figcaption>${esc(photo.title)}</figcaption></figure>`).join("");
  const events = (row.events || []).slice(0, 30).map((event) => `<div class="ex-line"><em>${esc(event.kind)}</em><b>${esc(event.title)}</b><small>${esc(String(event.at).replace("T", " ").slice(0, 16))}</small></div>`).join("");
  return `${panel("DAY BY DAY", days || `<p class="ex-dim">Each day of the trip gets a line here once you fly.</p>`)}
    ${panel("PHOTO ALBUM", album ? `<div class="ex-album">${album}</div>` : `<p class="ex-dim">Screenshots and postcards taken on the trip gather here.</p>`, {note: `${(row.album || []).length} pictures`})}
    ${panel("RECENT", events || `<p class="ex-dim">Nothing yet.</p>`)}`;
}

function wrappedView(row, data, esc) {
  const ready = n(row.stats?.jumps) > 0;
  return `${panel("THE TRIP, TOLD BACK", `<p class="ex-dim">The trip as Void Wrapped tells a year: the distance, the systems, the firsts, the music and the Watcher's verdict, one card at a time, ready to save or share.</p>
      <div class="ex-actions">${ready ? `${button("TELL IT", "wrapped", {"expedition-id": row.id}, esc, "primary")}${button("WATCH THE REPLAY", "replay", {"expedition-id": row.id}, esc)}` : `<small>Fly a little first.</small>`}</div>`)}
    ${panel("SHARE IT", `<div class="ex-actions">${button("COPY AS A FILE'S WORTH", "export", {"expedition-id": row.id}, esc)}</div>
      <form class="ex-form" data-ex-form="import_file"><label><span>PASTE A FRIEND'S EXPEDITION</span><textarea name="text" rows="3" placeholder="What COPY gave them">${esc(field("import_file", "text"))}</textarea></label>
      <div class="ex-actions"><button type="submit">ADD IT</button></div></form>`)}`;
}

// -- places along the way (Part 5) -------------------------------------------------------------------
const PLACE_KINDS = [["planet", "Planet"], ["surface", "Surface site"], ["poi", "Point of interest"], ["station", "Station"], ["system", "System"], ["note", "Note"]];
const PLACE_FILTERS = [["all", "ALL"], ["planet", "PLANETS"], ["surface", "SURFACE SITES"], ["poi", "POINTS OF INTEREST"], ["station", "STATIONS"], ["system", "SYSTEMS"], ["note", "NOTES"]];
const FIND_LABELS = {valuable: "VALUABLE WORLD", codex: "NEW CODEX", footfall: "FIRST FOOTFALL"};
const spot = (lat, lon) => `${n(lat).toFixed(4)}, ${n(lon).toFixed(4)}`;
const thumb = (photo, ui) => ui.apiUrl(photo.kind === "postcard" ? `/media/postcard-thumb/${photo.id}.jpg` : `/media/shot-thumb/${photo.id}.jpg`);

function placeCard(place, row, esc, ui) {
  // A body's name usually starts with its system's; then the body says both.
  const inSystem = place.body && String(place.body).toLowerCase().startsWith(String(place.system || "").toLowerCase());
  const where = inSystem ? place.body : [place.body, place.system].filter(Boolean).join(" · ");
  const photo = (place.pictures || [])[0];
  const id = {"expedition-id": row.id, "place-id": place.id};
  const badges = [place.visited ? `<em class="done">VISITED</em>` : "",
    place.on_route ? `<em>${place.reached ? "REACHED" : "ON THE ROUTE"}</em>` : "",
    place.found ? "<em>FOUND ON THE TRIP</em>" : "",
    String(place.source || "").startsWith("edastro:") ? "<em>EDASTRO</em>" : ""].join("");
  const actions = [place.on_route || place.kind === "note" ? "" : button("ADD TO ROUTE", "place_to_route", id, esc, "primary"),
    place.lat != null ? button("GUIDE ME", "guide_place", id, esc) : "",
    button(place.visited ? "NOT VISITED" : "VISITED", "place_visited", place.visited ? id : {...id, on: 1}, esc),
    place.url ? button("OPEN PAGE", "open_link", {url: place.url}, esc) : "",
    confirmButton(`place-${place.id}`, "REMOVE", "remove_place", id, esc)].join("");
  const notes = `<form class="ex-place-notes" data-ex-form="place_note" data-expedition-id="${esc(row.id)}" data-place-id="${esc(place.id)}">
    <textarea name="notes" rows="2" maxlength="1000" placeholder="Your notes">${esc(field(`place-${place.id}`, "notes", place.notes || ""))}</textarea>
    <button type="submit">SAVE NOTE</button></form>`;
  return `<article class="ex-place kind-${esc(place.kind)}${place.visited ? " visited" : ""}">
    ${photo ? `<div class="ex-place-pic"><img src="${thumb(photo, ui)}" alt="" loading="lazy">${place.pictures.length > 1 ? `<span>+${place.pictures.length - 1}</span>` : ""}</div>` : ""}
    <div class="ex-place-body"><small class="ex-kind">${esc(String(place.kind_label || "Place").toUpperCase())}</small>
      <h5>${esc(place.title || where)}</h5>${place.title && where !== place.title ? `<p>${esc(where)}</p>` : ""}
      ${place.lat != null ? `<p class="ex-spot">${spot(place.lat, place.lon)}</p>` : ""}
      ${badges ? `<div class="ex-badges">${badges}</div>` : ""}${notes}<div class="ex-actions">${actions}</div></div></article>`;
}

function nearbyPanel(row, esc) {
  const nearby = row.nearby;
  if (!nearby) {
    return `<p class="ex-dim">Points of interest from EDAstro's catalogue are switched off (Settings › Flight › EXPEDITIONS).</p>`;
  }
  const id = {"expedition-id": row.id};
  const rows = (nearby.rows || []).map((poi) => `<div class="ex-poi">
      <div><b>${esc(poi.name)}</b><small>${esc(poi.type)} · ${esc(poi.system)}${poi.region ? ` · ${esc(poi.region)}` : ""}</small>
        ${poi.summary ? `<p>${esc(poi.summary)}</p>` : ""}<small>${ly(poi.off_ly)} off the route · ${ly(poi.along_ly)} along it${poi.rating ? ` · rated ${n(poi.rating).toFixed(1)}` : ""}</small></div>
      <div class="ex-actions">${poi.kept ? "<em>KEPT</em>" : `${button("KEEP", "add_poi", {...id, "poi-id": poi.id}, esc, "primary")}${button("ADD TO ROUTE", "add_poi", {...id, "poi-id": poi.id, route: 1}, esc)}`}
        ${button("OPEN PAGE", "open_link", {url: poi.url}, esc)}</div></div>`).join("");
  const empty = nearby.waiting ? "Fetching EDAstro's catalogue…"
    : nearby.error ? `EDAstro's catalogue couldn't be fetched (${esc(nearby.error)}). It tries again later.`
    : (row.legs || []).some((leg) => leg.coords) ? `Nothing in the catalogue within ${ly(nearby.range_ly)} of the route.`
    : "Find where the legs are (ROUTE › FIND WHERE THEY ARE) to see what's near the route.";
  return `${rows || `<p class="ex-dim">${empty}</p>`}
    <p class="ex-credit">${esc(nearby.credit)} · ${button("EDASTRO.COM/GEC", "open_link", {url: nearby.credit_url}, esc, "ex-linkish")}</p>`;
}

function placesView(row, data, esc, ui) {
  const places = row.places || [];
  const counts = {all: places.length};
  for (const place of places) counts[place.kind] = (counts[place.kind] || 0) + 1;
  if (placeFilter !== "all" && !counts[placeFilter]) placeFilter = "all";
  const chips = PLACE_FILTERS.filter(([id]) => id === "all" || counts[id]).map(([id, label]) => `<button type="button" class="ex-chip${placeFilter === id ? " active" : ""}" data-ex-op="place_filter" data-kind="${id}">${label} <b>${whole(counts[id])}</b></button>`).join("");
  const shown = places.filter((place) => placeFilter === "all" || place.kind === placeFilter);
  const tools = `<div class="ex-actions">${button("MARK WHERE I AM", "mark_here", {}, esc, "primary")}${button(addingPlace ? "CANCEL" : "+ ADD A PLACE", "place_form", {}, esc)}
      ${button("SAVE AS A FILE", "save_file", {"expedition-id": row.id}, esc)}${button("OPEN THE FOLDER", "open_folder", {}, esc)}</div>
    <p class="ex-dim">MARK WHERE I AM is a hotkey too (Settings › Hotkeys › Expedition: mark this place). On a planet it keeps the exact spot, and GUIDE ME points the planet compass back to it. Screenshots taken at a place are added to it.</p>`;
  const form = addingPlace ? `<form class="ex-form ex-place-form" data-ex-form="add_place" data-expedition-id="${esc(row.id)}">
      <label><span>SYSTEM</span><input name="system" maxlength="120" placeholder="${esc(data.here || "Where it is")}" value="${esc(field("add_place", "system"))}"></label>
      <label><span>BODY</span><input name="body" maxlength="160" placeholder="A planet or moon, if it's on one" value="${esc(field("add_place", "body"))}"></label>
      <label><span>NAME</span><input name="title" maxlength="200" placeholder="What to call it" value="${esc(field("add_place", "title"))}"></label>
      <label><span>KIND</span><select name="kind">${options(PLACE_KINDS, field("add_place", "kind", "planet"))}</select></label>
      <label><span>LATITUDE</span><input name="lat" type="number" step="any" min="-90" max="90" placeholder="Optional" value="${esc(field("add_place", "lat"))}"></label>
      <label><span>LONGITUDE</span><input name="lon" type="number" step="any" min="-180" max="180" placeholder="Optional" value="${esc(field("add_place", "lon"))}"></label>
      <label class="wide"><span>NOTES</span><input name="notes" maxlength="1000" value="${esc(field("add_place", "notes"))}"></label>
      <div class="ex-actions wide"><label class="ex-tick"><input type="checkbox" name="route"${field("add_place", "route") ? " checked" : ""}> Also a stop on the route</label>
        <button type="submit" class="primary">ADD PLACE</button></div></form>` : "";
  const finds = (row.finds || []).map((find) => `<div class="ex-find"><em>${FIND_LABELS[find.kind] || esc(String(find.kind).toUpperCase())}</em>
      <div><b>${esc(find.title)}</b><small>${esc(find.detail)}${find.system && find.title !== find.system ? ` · ${esc(find.system)}` : ""}</small></div>
      <div class="ex-actions">${button("KEEP", "keep_find", {"expedition-id": row.id, "find-id": find.id}, esc, "primary")}${button("LET GO", "dismiss_find", {"expedition-id": row.id, "find-id": find.id}, esc)}</div></div>`).join("");
  const list = shown.length ? `<div class="ex-places">${shown.map((place) => placeCard(place, row, esc, ui)).join("")}</div>`
    : `<p class="ex-dim">No places yet. Mark where you are, add one by hand, keep a find, or pick from what's near the route below.</p>`;
  return `${panel("PLACES", `${tools}${form}${places.length ? `<div class="ex-chips">${chips}</div>` : ""}${list}`, {note: `${whole(places.length)} kept · ${whole(places.filter((place) => place.visited).length)} visited`})}
    ${finds ? panel("KEEP THESE?", finds, {note: "Found on this trip"}) : ""}
    ${panel("WORTH SEEING NEAR YOUR ROUTE", nearbyPanel(row, esc), {note: row.nearby ? `Within ${ly(row.nearby.range_ly)} of the route, in the order you'd pass them` : ""})}`;
}

// -- the page ------------------------------------------------------------------------------------------
export function renderExpeditions(data, ui) {
  const root = ui.byId("mission-workspace");
  if (!root) return;
  last = data || {};
  const esc = ui.escapeHtml;
  const rows = last.expeditions || [];
  if (!selected || !rows.some((row) => row.id === selected)) selected = last.active_id || rows[0]?.id || "";
  const row = rows.find((item) => item.id === selected);
  const tabs = `<nav class="co-tabs ex-tabs">${VIEWS.map(([id, label]) => `<button type="button" class="${view === id ? "active" : ""}" data-ex-op="view" data-view="${id}">${label}</button>`).join("")}</nav>`;
  const body = row ? {overview, route: routeView, places: placesView, objectives: objectivesView, log: logView, wrapped: wrappedView}[view](row, last, esc, ui) : "";
  // Without an expedition, the waypoint route still has a home here.
  const routeUi = {...ui, number: (value, fallback = 0) => (Number.isFinite(Number(value)) ? Number(value) : fallback)};
  const loose = !row && last.route_tools ? `<section class="ex-panel"><header><h4>YOUR WAYPOINT ROUTE</h4></header><div class="explore-columns explore-route-grid">${routeMarkup(last.route_tools, routeUi)}</div></section>` : "";
  const detail = row ? `${hero(row, last, esc)}${tabs}<div class="ex-body">${body}</div>`
    : `<section class="ex-empty"><h3>Plan a long trip</h3><p>Colonia, Beagle Point, a loop of biology worlds: name it, set where it goes and the way home, and Void Compass follows it from the first jump. Spansh plots the legs, the journal ticks off your objectives, and at the end the trip is told back as its own Void Wrapped.</p></section>${loose}`;
  const markup = `${tripBar(last, esc)}<div class="ex-detail">${detail}</div>`;
  // Only redraw what changed: a redraw closes a dropdown and loses focus.
  if (markup === drawn && root.firstElementChild) return;
  const focus = document.activeElement && root.contains(document.activeElement) ? document.activeElement.name : null;
  drawn = markup;
  root.classList.remove("loading-panel");
  root.innerHTML = markup;
  if (focus) root.querySelector(`[name="${CSS.escape(focus)}"]`)?.focus();
}

const camel = (key) => key.replace(/[A-Z]/g, (char) => `_${char.toLowerCase()}`);

export function handleExpeditionsClick(event, ui) {
  if (!event.target.closest?.('[data-page-name="mission"]')) return false;
  const opener = event.target.closest("[data-ex-file-open]");
  if (opener) {
    opener.closest("form")?.querySelector(`[data-ex-file="${opener.dataset.exFileOpen}"]`)?.click();
    return true;
  }
  const control = event.target.closest("[data-ex-op]");
  if (!control || control.disabled || control.tagName === "INPUT") return false;
  event.preventDefault();
  const op = control.dataset.exOp;
  const redraw = () => { drawn = ""; renderExpeditions(last, ui); };
  if (op === "view") { view = control.dataset.view || "overview"; redraw(); return true; }
  if (op === "select") { selected = control.dataset.id || ""; redraw(); return true; }
  if (op === "new") { creating = !creating; redraw(); return true; }
  if (op === "rename_form") {
    renaming = renaming || !control.dataset.id ? "" : control.dataset.id;
    delete drafts.rename;
    redraw();
    return true;
  }
  if (op === "place_filter") { placeFilter = control.dataset.kind || "all"; redraw(); return true; }
  if (op === "place_form") { addingPlace = !addingPlace; redraw(); return true; }
  if (control.dataset.confirmKey) {
    const key = control.dataset.confirmKey;
    if (confirming.key !== key || Date.now() > confirming.until) {
      confirming = {key, until: Date.now() + 4000};
      redraw();
      setTimeout(() => { if (confirming.key === key) { confirming = {key: "", until: 0}; redraw(); } }, 4100);
      return true;
    }
    confirming = {key: "", until: 0};
  }
  const extra = {};
  for (const [key, value] of Object.entries(control.dataset)) {
    if (!["exOp", "confirmKey"].includes(key)) extra[camel(key)] = value;
  }
  if (control.dataset.confirmKey) extra.confirmed = true;
  send(ui, op, extra);
  return true;
}

export function handleExpeditionsChange(event, ui) {
  // LOAD A FILE: its text goes in the box to check, and nothing is saved until IMPORT.
  const picker = event.target.closest?.("#mission-workspace input[type=\"file\"][data-ex-file]");
  if (picker) {
    const file = picker.files?.[0];
    if (!file) return true;
    file.text().then((text) => {
      const form = picker.dataset.exFile;
      drafts[form] = {...(drafts[form] || {}), text: text.slice(0, 200000)};
      const lines = text.split(/\r?\n/).filter((line) => line.trim()).length;
      fileNote = `Read ${file.name}: ${whole(lines)} line${lines === 1 ? "" : "s"}. Check it above, then IMPORT.`;
      drawn = "";
      renderExpeditions(last, ui);
    }).catch(() => ui.showToast("That file couldn't be read"));
    return true;
  }
  const box = event.target.closest?.('#mission-workspace input[type="checkbox"][data-ex-op]');
  if (!box) return false;
  send(ui, box.dataset.exOp, {expedition_id: box.dataset.expeditionId, on: box.checked});
  return true;
}

const draftKey = (form) => form.dataset.exForm === "day_note" ? `note-${form.dataset.day}`
  : form.dataset.exForm === "place_note" ? `place-${form.dataset.placeId}` : form.dataset.exForm;

export function handleExpeditionsInput(event) {
  const form = event.target.closest?.("#mission-workspace [data-ex-form]");
  if (!form || !event.target.name) return false;
  const key = draftKey(form);
  drafts[key] = {...(drafts[key] || {}), [event.target.name]: event.target.type === "checkbox" ? (event.target.checked ? "1" : "") : event.target.value};
  return true;
}

export function handleExpeditionsSubmit(event, ui) {
  const form = event.target.closest?.("#mission-workspace [data-ex-form]");
  if (!form) return false;
  event.preventDefault();
  const name = form.dataset.exForm;
  const values = {};
  for (const element of form.elements) {
    if (element.name) values[element.name] = element.type === "checkbox" ? element.checked : element.value;
  }
  const extra = {expedition_id: form.dataset.expeditionId || selected};
  if (name === "day_note") extra.day = form.dataset.day;
  if (form.dataset.placeId) extra.place_id = form.dataset.placeId;
  delete drafts[draftKey(form)];
  if (name === "create") creating = false;
  if (name === "rename") renaming = "";
  if (name === "add_place") addingPlace = false;
  if (name === "import") fileNote = "";
  send(ui, name, {...values, ...extra});
  return true;
}

export function resetExpeditions() {
  Object.keys(drafts).forEach((key) => delete drafts[key]);
  selected = "";
  creating = false;
  renaming = "";
  drawn = "";
}
