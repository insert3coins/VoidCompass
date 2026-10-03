// Colonisation tab (5.5.2): projects, what is assigned to you, the site you
// are docked at, fleet carriers, where to buy, the system planner, nexus
// plans, Raven Colonial's statistics and the journal's own record. After
// SrvSurvey's colonisation features and Raven Colonial's website.

import {plannerChange, plannerClick, renderPlanner, resetPlanner} from "./colonisation-planner.js";

let view = "projects";
const VIEWS = [
  ["projects", "PROJECTS"], ["assigned", "ASSIGNED"], ["site", "THIS SITE"], ["carriers", "FLEET CARRIERS"],
  ["markets", "WHERE TO BUY"], ["planner", "SYSTEM PLANNER"], ["nexus", "NEXUS"], ["stats", "RAVEN STATS"],
  ["journal", "JOURNAL"],
];

const n = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
const count = (value) => n(value).toLocaleString("en-GB");

function send(ui, operation, extra = {}) {
  return ui.command("workspace", {page: "colonisation", operation, ...extra});
}

function bar(fraction, tone = "") {
  const pct = Math.max(0, Math.min(100, n(fraction) * 100));
  return `<span class="co-bar ${tone}"><i style="--fill:${pct.toFixed(1)}%"></i></span>`;
}

function ago(seconds) {
  if (!seconds) return "never";
  const minutes = Math.max(0, Math.round((Date.now() / 1000 - n(seconds)) / 60));
  return minutes < 1 ? "just now" : minutes < 60 ? `${minutes} min ago` : `${Math.round(minutes / 60)} h ago`;
}

function since(iso) {
  const time = Date.parse(iso || "");
  return Number.isFinite(time) ? ago(time / 1000) : "";
}

function statusStrip(data, ui) {
  const raven = data.raven || {};
  const esc = ui.escapeHtml;
  const state = raven.active ? "linked" : raven.has_key ? "paused" : "local";
  const title = raven.active ? `RAVEN COLONIAL · ${esc(String(raven.cmdr || "").toUpperCase())}`
    : raven.has_key ? "RAVEN COLONIAL · SYNC OFF" : "JOURNAL ONLY";
  const detail = raven.active ? `Synced ${ago(raven.synced_at)}${raven.pending ? " · updating…" : ""}`
    : raven.has_key ? "Turn sync on in Settings › Integrations to share deliveries and carrier cargo."
    : "Add your Raven Colonial key in Settings › Integrations to share projects with your team.";
  return `<div class="co-status ${state}"><b>${title}</b><span>${esc(detail)}</span>`
    + (raven.active ? "" : `<button type="button" data-page="settings" data-settings-section="integrations">INTEGRATIONS</button>`)
    + `</div>${raven.error ? `<p class="co-error">${esc(raven.error)}</p>` : ""}`
    + `${data.error ? `<p class="co-error">${esc(data.error)}</p>` : ""}${data.notice ? `<p class="co-notice">${esc(data.notice)}</p>` : ""}`;
}

function tabs(data) {
  const counts = {projects: (data.projects || []).length, assigned: (data.assignments || []).length,
    carriers: (data.carriers || []).length, journal: (data.local || []).length};
  return `<nav class="co-tabs" role="tablist">${VIEWS.map(([id, label]) => {
    if (id === "site" && !data.site) return "";
    const badge = counts[id] ? ` <small>${counts[id]}</small>` : "";
    return `<button type="button" role="tab" data-co-view="${id}" class="${view === id ? "active" : ""}">${label}${badge}</button>`;
  }).join("")}</nav>`;
}

// -- projects -----------------------------------------------------------
function projectsView(data, ui) {
  const esc = ui.escapeHtml;
  const rows = data.projects || [];
  const loading = `<form class="co-inline co-loading" data-co-form="fc_loading"><input name="name" placeholder="New fleet carrier loading project" maxlength="120"><button type="submit">CREATE</button></form>`;
  if (!rows.length) {
    return `<div class="co-empty"><b>NO PROJECTS YET</b><span>${data.raven?.active
      ? "Dock at a construction site and create its project on THIS SITE, start one from a planned site in the SYSTEM PLANNER, or join one a teammate created."
      : "Projects you build appear here from Raven Colonial. Your journal's construction sites are under JOURNAL."}</span></div>${data.raven?.active ? loading : ""}`;
  }
  const selected = data.selected?.build_id;
  const list = rows.map((row) => `<article class="co-project${row.build_id === selected ? " selected" : ""}${row.visible ? "" : " hidden-project"}${row.complete ? " done" : ""}" data-co-select="${esc(row.build_id)}">
      <header><b>${row.primary ? "★ " : ""}${esc(row.name)}</b><span>${esc(row.system)}</span></header>
      <small>${esc(row.type)}${row.body ? ` · ${esc(row.body)}` : ""}</small>
      ${row.progress === null ? "" : bar(row.progress, row.complete ? "done" : "")}
      <footer><span>${row.complete ? "COMPLETE" : `${count(row.remaining)} LEFT${row.trips ? ` · ${count(row.trips)} TRIPS` : ""}`}</span>
        <span class="co-actions">
          <button type="button" title="${row.primary ? "Clear primary" : "Make primary"}" data-co-op="set_primary" data-build-id="${esc(row.build_id)}">${row.primary ? "★" : "☆"}</button>
          <button type="button" title="${row.visible ? "Hide from the overlay" : "Show on the overlay"}" data-co-op="toggle_visible" data-build-id="${esc(row.build_id)}">${row.visible ? "◉" : "○"}</button>
          <button type="button" title="Open on ravencolonial.com" data-co-op="open_raven" data-build-id="${esc(row.build_id)}">↗</button>
        </span></footer>
    </article>`).join("");
  const totals = data.totals || {};
  return `<div class="co-projects"><section class="co-list"><p class="co-totals">${count(totals.visible)} SHOWN · ${count(totals.remaining)} CARGO LEFT${totals.trips ? ` · ${count(totals.trips)} TRIPS IN THIS SHIP` : ""}</p>${list}${data.raven?.active ? loading : ""}</section>
    <section class="co-detail">${detailView(data.selected, data, ui)}</section></div>`;
}

function statsPanel(stats, esc) {
  if (!stats) return "";
  const top = Math.max(1, ...stats.cmdrs.map((row) => row.cargo));
  const peak = Math.max(1, ...stats.timeline.map((row) => row.cargo));
  const start = Date.parse(stats.start || "");
  const end = Date.parse(stats.end || "") || Date.now();
  const hours = Number.isFinite(start) ? Math.max(1, (end - start) / 3_600_000) : 0;
  return `<section class="co-stats"><h4>DELIVERIES</h4>
    <p>${count(stats.total_cargo)} T in ${count(stats.total_deliveries)} deliveries${hours ? ` · ${count(Math.round(stats.total_cargo / hours))} T an hour` : ""}${stats.start ? ` · since ${esc(String(stats.start).slice(0, 10))}` : ""}</p>
    ${stats.timeline.length ? `<div class="co-spark" title="Cargo delivered over time">${stats.timeline.map((row) => `<i style="--h:${(row.cargo / peak * 100).toFixed(1)}%" title="${esc(String(row.time || "").slice(0, 16).replace("T", " "))}: ${count(row.cargo)} T"></i>`).join("")}</div>` : ""}
    <ul class="co-bars">${stats.cmdrs.map((row) => `<li><span>${esc(row.name)}</span><i style="--fill:${(row.cargo / top * 100).toFixed(1)}%"></i><b>${count(row.cargo)}</b></li>`).join("")}</ul></section>`;
}

function detailView(project, data, ui) {
  if (!project) return `<div class="co-empty"><b>SELECT A PROJECT</b></div>`;
  const esc = ui.escapeHtml;
  const id = esc(project.build_id);
  const ready = new Set(project.ready || []);
  const groups = (project.groups || []).map((group) => `<tr class="co-group"><th colspan="6">${esc(group.name.toUpperCase())}</th></tr>`
    + group.rows.map((row) => `<tr class="${row.ship >= row.need || row.fc >= row.need ? "covered" : ""}${ready.has(row.id) ? " ready" : ""}">
        <td>${row.mine ? `<i class="co-pin">◆</i>` : row.assigned.length ? `<i class="co-pin others" title="${esc(row.assigned.join(", "))}">⊘</i>` : ""}${esc(row.name)}</td>
        <td class="num">${count(row.need)}</td><td class="num fc">${row.fc ? count(row.fc) : ""}</td><td class="num">${row.ship ? count(row.ship) : ""}</td>
        <td class="co-ready"><button type="button" class="pl-mini${ready.has(row.id) ? " on" : ""}" title="${ready.has(row.id) ? "Ready: loaded and on the way. Click to clear" : "Mark ready: loaded and on the way"}" data-co-op="project_ready" data-build-id="${id}" data-commodity="${esc(row.id)}" data-ready="${ready.has(row.id) ? "" : "1"}">${ready.has(row.id) ? "✓" : "·"}</button></td>
        <td class="co-assign">${project.member ? `<button type="button" data-co-op="${row.mine ? "unassign" : "assign"}" data-build-id="${id}" data-commodity="${esc(row.id)}">${row.mine ? "UNASSIGN" : "ASSIGN ME"}</button>` : esc(row.assigned.join(", "))}</td>
      </tr>`).join("")).join("");
  const commanders = (project.commanders || []).map((cmdr) => `<li class="${cmdr.me ? "me" : ""}"><b>${esc(cmdr.name)}</b>${cmdr.assigned.length ? `<small>${esc(cmdr.assigned.join(", "))}</small>` : ""}</li>`).join("");
  const carriers = (project.carriers || []).map((fc) => `<li>${fc.display_name ? `${esc(fc.display_name)} <small>${esc(fc.name)}</small>` : esc(fc.name)}</li>`).join("");
  const linkable = (data.carriers || []).filter((fc) => !(project.carriers || []).some((linked) => String(linked.market_id) === String(fc.market_id)));
  const stats = (data.stats || {})[project.build_id];
  return `<header class="co-detail-head"><div><p>${esc(project.type)}</p><h3>${project.primary ? "★ " : ""}${esc(project.name)}</h3>
      <span>${esc(project.system)}${project.body ? ` · ${esc(project.body)}` : ""}${project.faction ? ` · ${esc(project.faction)}` : ""}</span></div>
      <div class="co-head-actions"><button type="button" data-co-op="open_raven" data-build-id="${id}">OPEN ON RAVEN</button>
      ${project.discord ? `<button type="button" data-co-op="open_link" data-url="${esc(project.discord)}">DISCORD</button>` : ""}
      <button type="button" data-co-op="project_stats" data-build-id="${id}">${stats ? "REFRESH STATS" : "STATS"}</button>
      <button type="button" data-co-view-to="markets" data-co-market-for="${id}">WHERE TO BUY</button>
      ${project.member ? `<button type="button" data-co-op="leave" data-build-id="${id}">LEAVE</button>` : `<button type="button" class="primary" data-co-op="join" data-build-id="${id}">JOIN PROJECT</button>`}</div></header>
    <div class="co-meter">${bar(project.max_need ? 1 - project.remaining / project.max_need : 0, project.complete ? "done" : "")}<span>${project.complete ? "COMPLETE" : `${count(project.remaining)} of ${count(project.max_need)} still needed`}</span></div>
    ${statsPanel(stats, esc)}
    <table class="co-needs"><thead><tr><th>COMMODITY</th><th>NEED</th><th>CARRIERS</th><th>SHIP</th><th>READY</th><th>ASSIGNED</th></tr></thead><tbody>${groups || `<tr><td colspan="6">Nothing left to deliver.</td></tr>`}</tbody></table>
    <div class="co-columns">
      <section><h4>COMMANDERS</h4><ul class="co-people">${commanders || "<li>None linked</li>"}</ul></section>
      <section><h4>FLEET CARRIERS</h4><ul class="co-people">${carriers || "<li>None linked</li>"}</ul>
        ${linkable.length ? `<div class="co-inline"><select id="co-link-fc">${linkable.map((fc) => `<option value="${esc(fc.market_id)}">${esc(fc.display_name || fc.name)}</option>`).join("")}</select><button type="button" data-co-op="link_project_carrier" data-build-id="${id}">LINK</button></div>` : ""}</section>
    </div>
    <form class="co-form" data-co-form="details" data-build-id="${id}">
      <label><span>Name</span><input name="name" value="${esc(project.name)}" maxlength="120"></label>
      <label><span>Architect</span><input name="architect" value="${esc(project.architect)}" maxlength="80"></label>
      <label><span>Faction</span><input name="faction" value="${esc(project.faction)}" maxlength="120"></label>
      <label><span>Discord link</span><input name="discord" value="${esc(project.discord)}" maxlength="300" placeholder="https://discord.com/channels/…"></label>
      <label class="wide"><span>Notes</span><textarea name="notes" rows="3" maxlength="2000">${esc(project.notes)}</textarea></label>
      <div class="co-form-actions"><button type="submit" class="primary">SAVE DETAILS</button>
        ${project.complete ? "" : `<button type="button" class="danger-action" data-co-op="complete" data-build-id="${id}">MARK COMPLETE</button>`}
        ${project.architect_is_me ? `<button type="button" class="danger-action" data-co-op="project_delete" data-build-id="${id}">DELETE PROJECT</button>` : ""}</div>
    </form>`;
}

function assignedView(data, ui) {
  const esc = ui.escapeHtml;
  const rows = data.assignments || [];
  if (!rows.length) return `<div class="co-empty"><b>NOTHING ASSIGNED TO YOU</b><span>Use ASSIGN ME on a project's commodity to claim it; the overlay marks what is yours with ◆.</span></div>`;
  const total = rows.reduce((sum, row) => sum + row.need, 0);
  return `<p class="co-totals">${count(total)} T ASSIGNED TO YOU${data.capacity ? ` · ${count(Math.ceil(total / data.capacity))} TRIPS IN THIS SHIP` : ""}</p>
    <table class="co-needs"><thead><tr><th>COMMODITY</th><th>NEED</th><th>PROJECT</th><th>SYSTEM</th><th></th></tr></thead><tbody>${rows.map((row) => `<tr>
      <td><i class="co-pin">◆</i>${esc(row.name)}</td><td class="num">${count(row.need)}</td><td>${esc(row.project)}</td><td>${esc(row.system)}</td>
      <td class="co-assign"><button type="button" data-co-select="${esc(row.build_id)}" data-co-view-to="projects">OPEN</button><button type="button" data-co-op="unassign" data-build-id="${esc(row.build_id)}" data-commodity="${esc(row.id)}">UNASSIGN</button></td></tr>`).join("")}</tbody></table>`;
}

// -- this site ----------------------------------------------------------
function siteView(data, ui) {
  const site = data.site;
  const esc = ui.escapeHtml;
  if (!site) return `<div class="co-empty"><b>NOT DOCKED AT A CONSTRUCTION SITE</b><span>Dock at a construction site or one of your fleet carriers.</span></div>`;
  if (site.at_carrier) {
    return `<div class="co-site"><h3>${esc(site.station)}</h3><p>${site.carrier_linked ? "This fleet carrier is linked: its cargo counts toward your projects." : "Link this fleet carrier so its cargo counts toward your projects and stays in step as you load and unload."}</p>
      ${site.carrier_linked ? "" : `<button type="button" class="primary" data-co-op="link_carrier">LINK THIS CARRIER</button>`}</div>`;
  }
  const needs = (site.needs || []).map((row) => `<li><span>${esc(row.name)}</span><b>${count(row.need)}</b></li>`).join("");
  let body;
  if (site.tracked) {
    body = `<p class="co-good">Tracked: this site is one of your projects.</p><button type="button" data-co-select="${esc(site.build_id)}" data-co-view-to="projects">OPEN PROJECT</button>`;
  } else if (site.untracked) {
    body = `<p>${esc(site.untracked_name)} is tracked by another commander.</p><button type="button" class="primary" data-co-op="join" data-build-id="${esc(site.untracked_id)}">JOIN THEIR PROJECT</button>`;
  } else if (!data.raven?.active) {
    body = `<p>Add your Raven Colonial key in Settings › Integrations to create this project and share it.</p>`;
  } else if (!site.depot_known) {
    body = `<p>Open Construction Services in the game first, so the site's needs are known.</p>`;
  } else {
    const types = (data.build_types || []).filter((row) => (row.location === "orbital") === Boolean(site.orbital));
    const suggested = site.suggested_type;
    const layouts = (types.find((row) => row.build_type === suggested) || types[0] || {}).layouts || [];
    const plans = site.site_plans;
    body = `<form class="co-form" data-co-form="create">
      <label><span>Project name</span><input name="name" value="${esc(site.name)}" maxlength="120"></label>
      <label><span>Location</span><select name="location" data-co-location><option value="orbital"${site.orbital ? " selected" : ""}>Orbital</option><option value="surface"${site.orbital ? "" : " selected"}>Surface</option></select></label>
      <label><span>Build type</span><select name="build_type" data-co-build-type>${types.map((row) => `<option value="${esc(row.build_type)}"${row.build_type === suggested ? " selected" : ""}>Tier ${esc(row.tier)}: ${esc(row.name)}</option>`).join("")}</select></label>
      <label><span>Layout</span><select name="layout" data-co-layout>${layouts.map((layout) => `<option value="${esc(layout)}">${esc(layout.replace(/_/g, " "))}</option>`).join("")}</select></label>
      <label><span>Body</span><select name="body_id"><option value="-1">Unknown</option>${(site.bodies || []).map((body) => `<option value="${esc(body.id)}"${String(body.id) === String(site.body_id) ? " selected" : ""}>${esc(body.name)}</option>`).join("")}</select></label>
      <label><span>System plan</span>${plans === null ? `<button type="button" data-co-op="load_site_plans">LOAD PLANS</button>` : `<select name="site_id"><option value="">None</option>${plans.map((plan) => `<option value="${esc(plan.id)}">${esc(plan.name)} (${esc(plan.buildType || "?")})</option>`).join("")}</select>`}</label>
      <label><span>Architect</span><input name="architect" value="${esc(site.architect)}" maxlength="80"></label>
      <label class="wide"><span>Notes</span><textarea name="notes" rows="2" maxlength="2000"></textarea></label>
      <div class="co-form-actions"><button type="submit" class="primary">CREATE PROJECT</button>${suggested ? `<small>Suggested from the site's cargo: ${esc(suggested.replace(/_/g, " "))}</small>` : ""}</div>
    </form>`;
  }
  return `<div class="co-site"><p class="co-kicker">${site.primary_port ? "PRIMARY PORT · " : ""}CONSTRUCTION SITE</p><h3>${esc(site.name)}</h3><span>${esc(site.system)}</span>
    ${body}${needs ? `<h4>SITE NEEDS</h4><ul class="co-needlist">${needs}</ul>` : ""}</div>`;
}

// -- fleet carriers -----------------------------------------------------
function orders(rows, label, esc) {
  if (!rows || !rows.length) return "";
  return `<h5>${label}</h5><ul class="co-chips">${rows.map((row) => `<li>${esc(row.name)} <b>${count(row.outstanding ?? row.total)}</b>${row.price ? `<small>${count(row.price)} CR</small>` : ""}</li>`).join("")}</ul>`;
}

function carriersView(data, ui) {
  const esc = ui.escapeHtml;
  const rows = data.carriers || [];
  const search = data.carrier_search;
  const finder = `<form class="co-inline co-architect-load" data-co-form="carrier_search"><input name="name" value="${esc(search?.query || "")}" placeholder="Find a carrier: callsign or name" maxlength="60"><button type="submit">SEARCH</button></form>
    ${search ? `<ul class="co-results">${search.results.length ? search.results.map((row) => `<li><b>${esc(row.name)}</b>${row.carrier_name ? `<span>${esc(row.carrier_name)}</span>` : ""}${row.linked ? `<small>LINKED</small>` : `<button type="button" data-co-op="carrier_link_found" data-market-id="${esc(row.market_id)}">LINK</button>`}</li>`).join("") : "<li>No carriers match.</li>"}</ul>` : ""}`;
  if (!rows.length) return `${finder}<div class="co-empty"><b>NO LINKED FLEET CARRIERS</b><span>Search for your carrier above, or dock at it and use THIS SITE to link it.</span></div>`;
  return `${finder}<div class="co-carriers">${rows.map((fc) => `<article class="co-carrier" data-market-id="${esc(fc.market_id)}"><header><b>${esc(fc.display_name || fc.name)}</b><span>${esc(fc.name)}${fc.system ? ` · ${esc(fc.system)}` : ""}</span>
      <button type="button" class="pl-mini" data-co-op="carrier_refresh" data-market-id="${esc(fc.market_id)}" title="Refresh location and market orders">↻</button>
      <button type="button" data-co-op="unlink_carrier" data-market-id="${esc(fc.market_id)}">UNLINK</button></header>
      <p>${count(fc.cargo_total)} T OF CONSTRUCTION CARGO${fc.last_refresh ? ` · REFRESHED ${esc(since(fc.last_refresh)).toUpperCase()}` : ""}</p>
      <details class="co-edit-cargo"><summary>EDIT CARGO</summary><form class="co-cargo-form" data-co-form="carrier_cargo" data-market-id="${esc(fc.market_id)}">
        ${(data.build_commodities || []).map((item) => {
          const have = (fc.cargo.find((row) => row.id === item.id) || {}).count || 0;
          return `<label><span>${esc(item.name)}</span><input type="number" min="0" max="100000" name="${esc(item.id)}" value="${have}"></label>`;
        }).join("")}
        <div class="co-form-actions"><button type="submit" class="primary">SAVE CARGO</button><small>Sets each count outright on Raven Colonial.</small></div></form></details>
      <form class="co-inline" data-co-form="carrier_rename" data-market-id="${esc(fc.market_id)}"><input name="display_name" value="${esc(fc.display_name)}" placeholder="Display name" maxlength="80"><button type="submit">RENAME</button></form>
      <ul class="co-chips">${fc.cargo.map((item) => `<li>${esc(item.name)} <b>${count(item.count)}</b></li>`).join("") || "<li>Empty</li>"}</ul>
      ${orders(fc.purchases, "BUYING", esc)}${orders(fc.sales, "SELLING", esc)}</article>`).join("")}</div>`;
}

// -- where to buy -------------------------------------------------------
function marketsView(data, ui) {
  const esc = ui.escapeHtml;
  const found = data.markets;
  const options = found?.options || {};
  const limits = data.market_limits || {distance: 1000, arrival: 250000, sizes: ["large", "medium", "small"]};
  const projects = (data.projects || []).filter((row) => !row.complete);
  const chosen = found?.build_id ?? marketFor;
  const form = `<form class="co-form co-markets-form" data-co-form="markets">
    <label><span>Needs of</span><select name="build_id"><option value="">All shown projects</option>${projects.map((row) => `<option value="${esc(row.build_id)}"${row.build_id === chosen ? " selected" : ""}>${esc(row.name)} · ${esc(row.system)}</option>`).join("")}</select></label>
    <label><span>Near system</span><input name="ref_system" value="${esc(options.refSystem || data.current_system || "")}" maxlength="160"></label>
    <label><span>Within (ly)</span><input type="number" name="max_distance" min="0" max="${limits.distance}" value="${options.maxDistance ?? 100}"></label>
    <label><span>Station within (ls)</span><input type="number" name="max_arrival" min="0" max="${limits.arrival}" step="500" value="${options.maxArrival ?? 10000}"></label>
    <label><span>Landing pad</span><select name="ship_size">${limits.sizes.map((size) => `<option${size === (options.shipSize || "large") ? " selected" : ""}>${size}</option>`).join("")}</select></label>
    <label class="co-check"><input type="checkbox" name="no_surface"${options.noSurface ? " checked" : ""}><span>No surface ports</span></label>
    <label class="co-check"><input type="checkbox" name="no_fc"${options.noFC !== false ? " checked" : ""}><span>No fleet carriers</span></label>
    <label class="co-check"><input type="checkbox" name="require_need"${options.requireNeed ? " checked" : ""}><span>Enough stock of something</span></label>
    <label class="co-check"><input type="checkbox" name="has_shipyard"${options.hasShipyard ? " checked" : ""}><span>Has a shipyard</span></label>
    <div class="co-form-actions"><button type="submit" class="primary">FIND MARKETS</button><small>Market data from Spansh, via Raven Colonial.</small></div></form>`;
  if (!found) return `${form}<div class="co-empty"><b>WHERE TO BUY</b><span>Markets near a system that sell what your projects still need.</span></div>`;
  const rows = found.markets.map((row) => `<article class="co-market"><header><b>${esc(row.station)}</b><span>${esc(row.system)}${row.body ? ` · ${esc(row.body)}` : ""}</span>
      <small>${n(row.distance).toFixed(1)} ly · ${count(Math.round(n(row.arrival)))} ls · ${esc(row.pad)} pad${row.surface ? " · surface" : ""} · ${esc(row.type)}${row.updated ? ` · ${esc(since(row.updated))}` : ""}</small></header>
      <ul class="co-chips">${row.covers.map((item) => `<li class="${item.stock >= item.need ? "enough" : ""}">${esc(item.name)} <b>${count(item.stock)}</b><small>/ ${count(item.need)}</small></li>`).join("")}</ul></article>`).join("");
  return `${form}<p class="co-totals">${found.markets.length} MARKETS NEAR ${esc(String(options.refSystem || "").toUpperCase())} · ${found.needs.length} COMMODITIES NEEDED <button type="button" class="pl-mini" data-co-op="markets_clear" title="Clear">✕</button></p>
    <div class="co-markets">${rows || `<div class="co-empty"><b>NO MARKETS FOUND</b><span>Widen the distance or relax the filters.</span></div>`}</div>`;
}

// -- nexus --------------------------------------------------------------
function nexusView(data, ui) {
  const esc = ui.escapeHtml;
  const nexus = data.nexus;
  const list = Array.isArray(data.nexuses);
  const head = `<div class="co-nexus-head"><button type="button" data-co-op="nexus_list">${list ? "REFRESH" : "YOUR NEXUSES"}</button>
    <form class="co-inline" data-co-form="nexus_create"><input name="name" placeholder="New nexus name" maxlength="80"><button type="submit">CREATE</button></form></div>
    ${list ? `<ul class="co-results">${data.nexuses.length ? data.nexuses.map((row) => `<li><b>${esc(row.name)}</b><span>${esc(row.owner)}${row.open ? "" : " · private"}${row.destination ? ` · to ${esc(row.destination)}` : ""}</span><button type="button" data-co-op="nexus_open" data-id="${esc(row.id)}">OPEN</button></li>`).join("") : "<li>No nexuses yet.</li>"}</ul>` : ""}`;
  if (!nexus) return `${head}<div class="co-empty"><b>PLAN MANY SYSTEMS</b><span>A nexus is a plan for many systems: the systems on the way, who is working on them and the carriers serving them.</span></div>`;
  const total = nexus.systems.reduce((sum, row) => sum + row.total, 0);
  const done = nexus.systems.reduce((sum, row) => sum + row.progress, 0);
  const editable = nexus.mine;
  return `${head}<header class="co-detail-head"><div><p>NEXUS · ${esc(nexus.owner)}</p><h3>${esc(nexus.name)}</h3><span>${nexus.systems.length} systems · ${count(done)} of ${count(total)} T delivered</span></div>
      <div class="co-head-actions"><button type="button" data-co-op="nexus_open_raven">OPEN ON RAVEN</button><button type="button" data-co-op="nexus_close">CLOSE</button>
      ${editable ? `<button type="button" class="danger-action" data-co-op="nexus_delete" data-id="${esc(nexus.id)}">DELETE</button>` : ""}</div></header>
    ${total ? `<div class="co-meter">${bar(done / total)}</div>` : ""}
    <section class="pl-fields">
      <label><span>Name</span><input data-nx-field="name" value="${esc(nexus.name)}" maxlength="80"${editable ? "" : " disabled"}></label>
      <label class="co-check"><input type="checkbox" data-refresh-on-change data-co-change="nexus_set" data-field="open"${nexus.open ? " checked" : ""}${editable ? "" : " disabled"}><span>Open to everyone</span></label>
      <label class="wide"><span>Notes</span><textarea data-nx-field="notes" rows="2" maxlength="4000"${editable ? "" : " disabled"}>${esc(nexus.notes)}</textarea></label>
    </section>
    <table class="co-needs"><thead><tr><th>SYSTEM</th><th>TYPE</th><th>PROGRESS</th><th>BUILDS</th><th></th></tr></thead><tbody>${nexus.systems.map((row) => `<tr>
      <td>${esc(row.nickname || row.name)}${row.nickname ? `<small>${esc(row.name)}</small>` : ""}</td><td>${esc(row.type)}</td>
      <td>${row.total ? `${bar(row.progress / row.total)}<small>${count(row.progress)} / ${count(row.total)}</small>` : ""}</td><td class="num">${row.builds || ""}</td>
      <td class="co-assign"><button type="button" data-co-view-to="planner" data-co-op="planner_load" data-system="${esc(row.name)}">PLAN</button>${editable ? `<button type="button" data-co-op="nexus_remove_system" data-system="${esc(row.name)}">REMOVE</button>` : ""}</td></tr>`).join("") || `<tr><td colspan="5">No systems yet.</td></tr>`}</tbody></table>
    ${editable ? `<form class="co-inline" data-co-form="nexus_add_system"><input name="system" placeholder="Add a system" maxlength="160"><button type="submit">ADD SYSTEM</button></form>` : ""}
    <div class="co-columns">
      <section><h4>COMMANDERS</h4><ul class="co-people">${nexus.cmdrs.map((cmdr) => `<li><b>${esc(cmdr)}</b>${editable && cmdr.toLowerCase() !== nexus.owner.toLowerCase() ? `<button type="button" class="pl-mini" data-co-op="nexus_remove_cmdr" data-cmdr="${esc(cmdr)}">✕</button>` : ""}</li>`).join("") || "<li>None</li>"}</ul>
        ${editable ? `<form class="co-inline" data-co-form="nexus_add_cmdr"><input name="cmdr" placeholder="Commander" maxlength="80"><button type="submit">ADD</button></form>` : ""}</section>
      <section><h4>FLEET CARRIERS</h4><ul class="co-people">${nexus.fcs.map((fc) => `<li>${esc(fc.display_name || fc.name)} <small>${esc(fc.name)}</small></li>`).join("") || "<li>None</li>"}</ul>
        ${editable && (data.carriers || []).length ? `<div class="co-inline"><select id="co-nexus-fc">${data.carriers.map((fc) => `<option value="${esc(fc.market_id)}">${esc(fc.display_name || fc.name)}</option>`).join("")}</select><button type="button" data-co-op="nexus_add_fc">ADD</button></div>` : ""}</section>
    </div>`;
}

// -- raven statistics -----------------------------------------------------
function statsView(data, ui) {
  const esc = ui.escapeHtml;
  const stats = data.global_stats;
  if (!stats) return `<div class="co-empty"><b>RAVEN COLONIAL STATISTICS</b><span>Everyone's colonisation, as Raven Colonial has tracked it.</span><button type="button" class="primary" data-co-op="stats_load">LOAD STATISTICS</button></div>`;
  const t = stats.totals || {};
  const figures = [["ACTIVE PROJECTS", t.activeProjects], ["COMPLETED", t.completeProjects], ["COMMANDERS", t.commanders],
    ["ACTIVE THIS WEEK", t.commanders7d], ["FLEET CARRIERS", t.fleetCarriers], ["DELIVERIES THIS WEEK", t.countDeliveries7d],
    ["TONNES THIS WEEK", t.totalDelivered7d], ["TONNES EVER", t.totalDeliveredEver], ["ARCHITECTS", t.totalArchitects], ["PLANNED SYSTEMS", t.totalPlannedSystems]]
    .map(([label, value]) => `<div><small>${label}</small><b>${value == null ? "—" : count(value)}</b></div>`).join("");
  const board = (title, rows, unit = "") => `<section><h4>${title}</h4><ol class="co-board">${rows.map((row) => `<li><span>${esc(row.name)}</span><b>${count(row.value)}${unit}</b></li>`).join("")}</ol></section>`;
  return `<p class="co-totals">AS OF ${esc(String(stats.at || "").slice(0, 16).replace("T", " "))} <button type="button" class="pl-mini" data-co-op="stats_load" title="Refresh">↻</button></p>
    <div class="pl-figures co-global">${figures}</div>
    <div class="co-columns co-boards">
      ${board("TOP CONTRIBUTORS · 7 DAYS", stats.contributors, " T")}${board("TOP HELPERS · 7 DAYS", stats.helpers)}${board("TOP ARCHITECTS", stats.architects)}
      <section><h4>TOP SYSTEM SCORES</h4><ol class="co-board">${stats.systems.map((row) => `<li><span>${esc(row.system)}<small>${esc(row.architect)}</small></span><b>${count(row.score)}</b></li>`).join("")}</ol></section>
    </div>`;
}

// -- journal ------------------------------------------------------------
function journalView(data, ui) {
  const esc = ui.escapeHtml;
  const rows = data.local || [];
  if (!rows.length) return `<div class="co-empty"><b>NO CONSTRUCTION SITES IN YOUR JOURNAL YET</b><span>Construction depots you open in the game are recorded here, with or without Raven Colonial.</span></div>`;
  return `<div class="co-journal">${rows.map((row) => `<details class="co-local${row.complete ? " done" : ""}"><summary><b>${esc(row.name)}</b><span>${esc(row.system)}</span>${bar(row.progress, row.complete ? "done" : "")}<small>${row.complete ? "COMPLETE" : row.failed ? "FAILED" : `${(row.progress * 100).toFixed(1)}% · ${count(row.remaining)} LEFT`}</small></summary>
      <table class="co-needs"><thead><tr><th>COMMODITY</th><th>REQUIRED</th><th>PROVIDED</th><th>NEED</th></tr></thead><tbody>${row.resources.map((res) => `<tr class="${res.need ? "" : "covered"}"><td>${esc(res.name)}</td><td class="num">${count(res.required)}</td><td class="num">${count(res.provided)}</td><td class="num">${res.need ? count(res.need) : "✓"}</td></tr>`).join("")}</tbody></table>
      ${row.activity.length ? `<ul class="co-activity">${row.activity.slice().reverse().map((item) => `<li><b>${esc(item.type)}</b> ${esc(item.detail)}</li>`).join("")}</ul>` : ""}</details>`).join("")}</div>`;
}

let marketFor = "";
let lastData = null;

export function renderColonisation(data, ui) {
  const root = ui.byId("colonisation-workspace");
  if (!root) return;
  lastData = data;
  root.classList.remove("loading-panel");
  if (view === "site" && !data.site) view = "projects";
  const renderers = {projects: projectsView, assigned: assignedView, site: siteView, carriers: carriersView, markets: marketsView,
    planner: renderPlanner, nexus: nexusView, stats: statsView, journal: journalView};
  root.innerHTML = `${statusStrip(data, ui)}${tabs(data)}<div class="co-body">${renderers[view](data, ui)}</div>`;
  root.dataset.view = view;
}

const snake = (key) => key.replace(/[A-Z]/g, (char) => `_${char.toLowerCase()}`);

export function handleColonisationClick(event, ui, rerender) {
  const root = ui.byId("colonisation-workspace");
  if (!root || !root.contains(event.target)) return false;
  const viewButton = event.target.closest("[data-co-view]");
  if (viewButton) {
    view = viewButton.dataset.coView;
    rerender();
    return true;
  }
  const planner = plannerClick(event, (operation, extra) => send(ui, operation, extra));
  if (planner === "rerender") {
    rerender();
    return true;
  }
  if (planner === "handled-default") return true;
  const select = event.target.closest("[data-co-select]");
  if (select && !event.target.closest("button[data-co-op]")) {
    if (select.dataset.coViewTo) view = select.dataset.coViewTo;
    send(ui, "select", {build_id: select.dataset.coSelect});
    return true;
  }
  const button = event.target.closest("[data-co-op], [data-co-view-to]");
  if (!button) return false;
  event.preventDefault();
  if (button.dataset.coViewTo) {
    view = button.dataset.coViewTo;
    if (button.dataset.coMarketFor) marketFor = button.dataset.coMarketFor;
    if (!button.dataset.coOp) {
      rerender();
      return true;
    }
  }
  const operation = button.dataset.coOp;
  const extra = {};
  for (const [key, value] of Object.entries(button.dataset)) {
    if (!["coOp", "coViewTo", "coMarketFor", "systemFromInput"].includes(key)) extra[snake(key)] = value;
  }
  if (typeof extra.features === "string") extra.features = extra.features.split(",").filter(Boolean);
  if ("ready" in extra) extra.ready = Boolean(extra.ready);
  if ("refresh" in extra) extra.refresh = Boolean(extra.refresh);
  if (operation === "planner_fav") extra.value = Boolean(extra.value);
  if (button.dataset.systemFromInput) extra.system = root.querySelector(".co-architect-load input[name=system]")?.value || "";
  if (operation === "link_project_carrier") extra.market_id = ui.byId("co-link-fc")?.value || "";
  const nexus = lastData?.nexus;
  if (operation === "nexus_remove_system" && nexus) {
    return send(ui, "nexus_set", {field: "systems", value: nexus.systems.map((row) => row.name).filter((name) => name !== extra.system)}), true;
  }
  if (operation === "nexus_remove_cmdr" && nexus) {
    return send(ui, "nexus_set", {field: "cmdrs", value: nexus.cmdrs.filter((cmdr) => cmdr !== extra.cmdr)}), true;
  }
  if (operation === "nexus_add_fc" && nexus) {
    const marketId = ui.byId("co-nexus-fc")?.value;
    return send(ui, "nexus_set", {field: "fcs", value: [...new Set([...nexus.fcs.map((fc) => String(fc.market_id)), marketId])]}), true;
  }
  const confirms = {
    complete: "Mark this project complete on Raven Colonial? This cannot be undone.",
    project_delete: "Delete this project from Raven Colonial for everyone? This cannot be undone.",
    nexus_delete: "Delete this nexus for everyone?",
    planner_discard: "Discard your changes to this system plan?",
    planner_delete_save: "Delete this named save?",
    unlink_carrier: "Unlink this fleet carrier from your colonisation?",
    planner_remove: null,
  };
  if (confirms[operation]) {
    if (!window.confirm(confirms[operation])) return true;
    extra.confirmed = true;
  }
  send(ui, operation, extra);
  return true;
}

export function handleColonisationSubmit(event, ui) {
  const form = event.target.closest?.("[data-co-form]");
  if (!form || !ui.byId("colonisation-workspace")?.contains(form)) return false;
  event.preventDefault();
  const values = Object.fromEntries(new FormData(form).entries());
  const kind = form.dataset.coForm;
  const nexus = lastData?.nexus;
  if (kind === "details") send(ui, "save_details", {build_id: form.dataset.buildId, ...values});
  else if (kind === "create") send(ui, "create_project", values);
  else if (kind === "planner_load") send(ui, "planner_load", {system: values.system || ""});
  else if (kind === "planner_save_as") send(ui, "planner_save", {save_name: values.save_name || ""});
  else if (kind === "fc_loading") send(ui, "project_fc_loading", {name: values.name || ""});
  else if (kind === "carrier_search") send(ui, "carrier_search", {name: values.name || ""});
  else if (kind === "carrier_rename") send(ui, "carrier_rename", {market_id: form.dataset.marketId, display_name: values.display_name || ""});
  else if (kind === "carrier_cargo") send(ui, "carrier_cargo", {market_id: form.dataset.marketId, cargo: values});
  else if (kind === "markets") {
    marketFor = values.build_id || "";
    send(ui, "markets_find", {...values, no_surface: "no_surface" in values, no_fc: "no_fc" in values,
      require_need: "require_need" in values, has_shipyard: "has_shipyard" in values});
  } else if (kind === "nexus_create") send(ui, "nexus_create", {name: values.name || ""});
  else if (kind === "nexus_add_system" && nexus && values.system) {
    send(ui, "nexus_set", {field: "systems", value: [...nexus.systems.map((row) => row.name), values.system]});
  } else if (kind === "nexus_add_cmdr" && nexus && values.cmdr) {
    send(ui, "nexus_set", {field: "cmdrs", value: [...nexus.cmdrs, values.cmdr]});
  }
  return true;
}

export function handleColonisationChange(event, ui, data) {
  const root = ui.byId("colonisation-workspace");
  if (!root || !root.contains(event.target)) return false;
  const target = event.target;
  if (plannerChange(event, (operation, extra) => send(ui, operation, extra))) return true;
  if (target.matches("[data-nx-field]")) {
    send(ui, "nexus_set", {field: target.dataset.nxField, value: target.value});
    return true;
  }
  if (target.matches("[data-co-change]")) {
    const operation = target.dataset.coChange;
    const value = target.type === "checkbox" ? target.checked : target.value;
    if (operation === "planner_load") {
      send(ui, "planner_load", {system: target.dataset.system, [target.dataset.field]: value});
    } else {
      send(ui, operation, {field: target.dataset.field, value});
    }
    return true;
  }
  const form = target.closest("[data-co-form=create]");
  if (!form) return false;
  const types = data?.build_types || [];
  if (target.matches("[data-co-location]")) {
    const orbital = target.value === "orbital";
    const buildSelect = form.querySelector("[data-co-build-type]");
    buildSelect.innerHTML = types.filter((row) => (row.location === "orbital") === orbital)
      .map((row) => `<option value="${ui.escapeHtml(row.build_type)}">Tier ${ui.escapeHtml(row.tier)}: ${ui.escapeHtml(row.name)}</option>`).join("");
  }
  if (target.matches("[data-co-location], [data-co-build-type]")) {
    const chosen = types.find((row) => row.build_type === form.querySelector("[data-co-build-type]").value);
    form.querySelector("[data-co-layout]").innerHTML = (chosen?.layouts || [])
      .map((layout) => `<option value="${ui.escapeHtml(layout)}">${ui.escapeHtml(layout.replace(/_/g, " "))}</option>`).join("");
  }
  return true;
}

export function resetColonisation() {
  view = "projects";
  marketFor = "";
  lastData = null;
  resetPlanner();
}
