// Colonisation tab (5.5.2): projects, the site you are docked at, fleet
// carriers, system sites and the journal's own record. After SrvSurvey's
// colonisation features; Raven Colonial holds the shared projects.

let view = "projects";
let architectDraft = null;
let architectKey = "";
const VIEWS = [
  ["projects", "PROJECTS"], ["site", "THIS SITE"], ["carriers", "FLEET CARRIERS"],
  ["architect", "SYSTEM SITES"], ["journal", "JOURNAL"],
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
  const counts = {projects: (data.projects || []).length, carriers: (data.carriers || []).length, journal: (data.local || []).length};
  return `<nav class="co-tabs" role="tablist">${VIEWS.map(([id, label]) => {
    if (id === "site" && !data.site) return "";
    const badge = counts[id] ? ` <small>${counts[id]}</small>` : "";
    return `<button type="button" role="tab" data-co-view="${id}" class="${view === id ? "active" : ""}">${label}${badge}</button>`;
  }).join("")}</nav>`;
}

function projectsView(data, ui) {
  const esc = ui.escapeHtml;
  const rows = data.projects || [];
  if (!rows.length) {
    return `<div class="co-empty"><b>NO PROJECTS YET</b><span>${data.raven?.active
      ? "Dock at a construction site and create its project on THIS SITE, or join one a teammate created."
      : "Projects you build appear here from Raven Colonial. Your journal's construction sites are under JOURNAL."}</span></div>`;
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
  return `<div class="co-projects"><section class="co-list"><p class="co-totals">${count(totals.visible)} SHOWN · ${count(totals.remaining)} CARGO LEFT${totals.trips ? ` · ${count(totals.trips)} TRIPS IN THIS SHIP` : ""}</p>${list}</section>
    <section class="co-detail">${detailView(data.selected, data, ui)}</section></div>`;
}

function detailView(project, data, ui) {
  if (!project) return `<div class="co-empty"><b>SELECT A PROJECT</b></div>`;
  const esc = ui.escapeHtml;
  const id = esc(project.build_id);
  const groups = (project.groups || []).map((group) => `<tr class="co-group"><th colspan="5">${esc(group.name.toUpperCase())}</th></tr>`
    + group.rows.map((row) => `<tr class="${row.ship >= row.need || row.fc >= row.need ? "covered" : ""}">
        <td>${row.mine ? `<i class="co-pin">◆</i>` : row.assigned.length ? `<i class="co-pin others" title="${esc(row.assigned.join(", "))}">⊘</i>` : ""}${esc(row.name)}</td>
        <td class="num">${count(row.need)}</td><td class="num fc">${row.fc ? count(row.fc) : ""}</td><td class="num">${row.ship ? count(row.ship) : ""}</td>
        <td class="co-assign">${project.member ? `<button type="button" data-co-op="${row.mine ? "unassign" : "assign"}" data-build-id="${id}" data-commodity="${esc(row.id)}">${row.mine ? "UNASSIGN" : "ASSIGN ME"}</button>` : esc(row.assigned.join(", "))}</td>
      </tr>`).join("")).join("");
  const commanders = (project.commanders || []).map((cmdr) => `<li class="${cmdr.me ? "me" : ""}"><b>${esc(cmdr.name)}</b>${cmdr.assigned.length ? `<small>${esc(cmdr.assigned.join(", "))}</small>` : ""}</li>`).join("");
  const carriers = (project.carriers || []).map((fc) => `<li>${fc.display_name ? `${esc(fc.display_name)} <small>${esc(fc.name)}</small>` : esc(fc.name)}</li>`).join("");
  const linkable = (data.carriers || []).filter((fc) => !(project.carriers || []).some((linked) => String(linked.market_id) === String(fc.market_id)));
  return `<header class="co-detail-head"><div><p>${esc(project.type)}</p><h3>${project.primary ? "★ " : ""}${esc(project.name)}</h3>
      <span>${esc(project.system)}${project.body ? ` · ${esc(project.body)}` : ""}${project.faction ? ` · ${esc(project.faction)}` : ""}</span></div>
      <div class="co-head-actions"><button type="button" data-co-op="open_raven" data-build-id="${id}">OPEN ON RAVEN</button>
      ${project.member ? `<button type="button" data-co-op="leave" data-build-id="${id}">LEAVE</button>` : `<button type="button" class="primary" data-co-op="join" data-build-id="${id}">JOIN PROJECT</button>`}</div></header>
    <div class="co-meter">${bar(project.max_need ? 1 - project.remaining / project.max_need : 0, project.complete ? "done" : "")}<span>${project.complete ? "COMPLETE" : `${count(project.remaining)} of ${count(project.max_need)} still needed`}</span></div>
    <table class="co-needs"><thead><tr><th>COMMODITY</th><th>NEED</th><th>CARRIERS</th><th>SHIP</th><th>ASSIGNED</th></tr></thead><tbody>${groups || `<tr><td colspan="5">Nothing left to deliver.</td></tr>`}</tbody></table>
    <div class="co-columns">
      <section><h4>COMMANDERS</h4><ul class="co-people">${commanders || "<li>None linked</li>"}</ul></section>
      <section><h4>FLEET CARRIERS</h4><ul class="co-people">${carriers || "<li>None linked</li>"}</ul>
        ${linkable.length ? `<div class="co-inline"><select id="co-link-fc">${linkable.map((fc) => `<option value="${esc(fc.market_id)}">${esc(fc.display_name || fc.name)}</option>`).join("")}</select><button type="button" data-co-op="link_project_carrier" data-build-id="${id}">LINK</button></div>` : ""}</section>
    </div>
    <form class="co-form" data-co-form="details" data-build-id="${id}">
      <label><span>Name</span><input name="name" value="${esc(project.name)}" maxlength="120"></label>
      <label><span>Architect</span><input name="architect" value="${esc(project.architect)}" maxlength="80"></label>
      <label><span>Faction</span><input name="faction" value="${esc(project.faction)}" maxlength="120"></label>
      <label class="wide"><span>Notes</span><textarea name="notes" rows="3" maxlength="2000">${esc(project.notes)}</textarea></label>
      <div class="co-form-actions"><button type="submit" class="primary">SAVE DETAILS</button>
        ${project.complete ? "" : `<button type="button" class="danger-action" data-co-op="complete" data-build-id="${id}">MARK COMPLETE</button>`}</div>
    </form>`;
}

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

function carriersView(data, ui) {
  const esc = ui.escapeHtml;
  const rows = data.carriers || [];
  if (!rows.length) return `<div class="co-empty"><b>NO LINKED FLEET CARRIERS</b><span>Dock at your carrier and use THIS SITE to link it.</span></div>`;
  return `<div class="co-carriers">${rows.map((fc) => `<article class="co-carrier"><header><b>${esc(fc.display_name || fc.name)}</b><span>${esc(fc.name)}</span>
      <button type="button" data-co-op="unlink_carrier" data-market-id="${esc(fc.market_id)}">UNLINK</button></header>
      <p>${count(fc.cargo_total)} T OF CONSTRUCTION CARGO</p>
      <ul class="co-chips">${fc.cargo.map((item) => `<li>${esc(item.name)} <b>${count(item.count)}</b></li>`).join("") || "<li>Empty</li>"}</ul></article>`).join("")}</div>`;
}

function architectView(data, ui) {
  const esc = ui.escapeHtml;
  const model = data.architect;
  const key = model ? `${model.system}|${model.loaded_at}` : "";
  if (key !== architectKey) {
    architectKey = key;
    architectDraft = model ? {sites: model.sites.map((site) => ({...site})), deleted: []} : null;
  }
  const head = `<form class="co-inline co-architect-load" data-co-form="architect_load"><input name="system" value="${esc(model?.system || data.architect_system || "")}" placeholder="SYSTEM NAME" maxlength="160">
    <button type="submit">LOAD SYSTEM</button>${model ? `<button type="button" data-co-op="architect_import_bodies">IMPORT BODIES</button><button type="button" data-co-op="open_system" data-system="${esc(model.system)}">OPEN ON RAVEN</button>` : ""}</form>`;
  if (!model) return `${head}<div class="co-empty"><b>PLAN A SYSTEM'S SITES</b><span>Load a system to see and edit its planned, building and completed sites on Raven Colonial.</span></div>`;
  const bodies = model.bodies || [];
  const types = data.build_types || [];
  const rows = architectDraft.sites.map((site, index) => `<tr data-index="${index}">
      <td><input data-co-site="name" value="${esc(site.name)}" maxlength="120"></td>
      <td><select data-co-site="body_num"><option value="-1">—</option>${bodies.map((body) => `<option value="${esc(body.num)}"${String(body.num) === String(site.body_num) ? " selected" : ""}>${esc(body.name)}</option>`).join("")}</select></td>
      <td><select data-co-site="build_type"><option value="">Unknown</option>${types.map((row) => row.layouts.map((layout) => `<option value="${esc(layout.toLowerCase())}"${layout.toLowerCase() === String(site.build_type || "").toLowerCase() ? " selected" : ""}>T${esc(row.tier)} ${esc(row.name)}: ${esc(layout.replace(/_/g, " "))}</option>`).join("")).join("")}</select></td>
      <td><select data-co-site="status">${(model.statuses || []).map((status) => `<option${status === site.status ? " selected" : ""}>${status}</option>`).join("")}</select></td>
      <td><button type="button" class="danger-action" data-co-remove-site="${index}">REMOVE</button></td></tr>`).join("");
  return `${head}<form class="co-form co-architect" data-co-form="architect_save">
      <label><span>Architect</span><input name="architect" value="${esc(model.architect)}" maxlength="80"></label>
      <label><span>Reserve level</span><select name="reserve">${(model.reserves || []).map((level) => `<option value="${level}"${level === model.reserve ? " selected" : ""}>${level || "Unknown"}</option>`).join("")}</select></label>
      <label class="co-check"><input type="checkbox" name="open"${model.open ? " checked" : ""}><span>Open to other architects</span></label>
      <table class="co-sites"><thead><tr><th>SITE</th><th>BODY</th><th>BUILD TYPE</th><th>STATUS</th><th></th></tr></thead><tbody>${rows || `<tr><td colspan="5">No sites yet.</td></tr>`}</tbody></table>
      <div class="co-form-actions"><button type="button" data-co-add-site>ADD SITE</button><button type="submit" class="primary">SAVE TO RAVEN</button><small>${bodies.length} bodies known</small></div>
    </form>`;
}

function journalView(data, ui) {
  const esc = ui.escapeHtml;
  const rows = data.local || [];
  if (!rows.length) return `<div class="co-empty"><b>NO CONSTRUCTION SITES IN YOUR JOURNAL YET</b><span>Construction depots you open in the game are recorded here, with or without Raven Colonial.</span></div>`;
  return `<div class="co-journal">${rows.map((row) => `<details class="co-local${row.complete ? " done" : ""}"><summary><b>${esc(row.name)}</b><span>${esc(row.system)}</span>${bar(row.progress, row.complete ? "done" : "")}<small>${row.complete ? "COMPLETE" : row.failed ? "FAILED" : `${(row.progress * 100).toFixed(1)}% · ${count(row.remaining)} LEFT`}</small></summary>
      <table class="co-needs"><thead><tr><th>COMMODITY</th><th>REQUIRED</th><th>PROVIDED</th><th>NEED</th></tr></thead><tbody>${row.resources.map((res) => `<tr class="${res.need ? "" : "covered"}"><td>${esc(res.name)}</td><td class="num">${count(res.required)}</td><td class="num">${count(res.provided)}</td><td class="num">${res.need ? count(res.need) : "✓"}</td></tr>`).join("")}</tbody></table>
      ${row.activity.length ? `<ul class="co-activity">${row.activity.slice().reverse().map((item) => `<li><b>${esc(item.type)}</b> ${esc(item.detail)}</li>`).join("")}</ul>` : ""}</details>`).join("")}</div>`;
}

export function renderColonisation(data, ui) {
  const root = ui.byId("colonisation-workspace");
  if (!root) return;
  root.classList.remove("loading-panel");
  if (view === "site" && !data.site) view = "projects";
  const body = {projects: projectsView, site: siteView, carriers: carriersView, architect: architectView, journal: journalView}[view](data, ui);
  root.innerHTML = `${statusStrip(data, ui)}${tabs(data)}<div class="co-body">${body}</div>`;
  root.dataset.view = view;
}

function architectRows(root) {
  if (!architectDraft) return;
  root.querySelectorAll(".co-sites tbody tr[data-index]").forEach((tr) => {
    const site = architectDraft.sites[Number(tr.dataset.index)];
    if (!site) return;
    tr.querySelectorAll("[data-co-site]").forEach((input) => { site[input.dataset.coSite] = input.value; });
  });
}

export function handleColonisationClick(event, ui, rerender) {
  const root = ui.byId("colonisation-workspace");
  if (!root || !root.contains(event.target)) return false;
  const viewButton = event.target.closest("[data-co-view]");
  if (viewButton) {
    view = viewButton.dataset.coView;
    rerender();
    return true;
  }
  const select = event.target.closest("[data-co-select]");
  if (select && !event.target.closest("button[data-co-op]")) {
    if (select.dataset.coViewTo) view = select.dataset.coViewTo;
    send(ui, "select", {build_id: select.dataset.coSelect});
    return true;
  }
  if (event.target.closest("[data-co-add-site]")) {
    architectRows(root);
    architectDraft.sites.push({id: "", name: "", body_num: -1, build_type: "", status: "plan"});
    rerender();
    return true;
  }
  const remove = event.target.closest("[data-co-remove-site]");
  if (remove) {
    architectRows(root);
    const [site] = architectDraft.sites.splice(Number(remove.dataset.coRemoveSite), 1);
    if (site?.id) architectDraft.deleted.push(site.id);
    rerender();
    return true;
  }
  const button = event.target.closest("[data-co-op]");
  if (!button) return false;
  event.preventDefault();
  const operation = button.dataset.coOp;
  const extra = {};
  if (button.dataset.buildId) extra.build_id = button.dataset.buildId;
  if (button.dataset.commodity) extra.commodity = button.dataset.commodity;
  if (button.dataset.marketId) extra.market_id = button.dataset.marketId;
  if (button.dataset.system) extra.system = button.dataset.system;
  if (operation === "link_project_carrier") extra.market_id = ui.byId("co-link-fc")?.value || "";
  if (operation === "architect_import_bodies") extra.system = root.querySelector(".co-architect-load input[name=system]")?.value || "";
  if (operation === "complete") {
    if (!window.confirm("Mark this project complete on Raven Colonial? This cannot be undone.")) return true;
    extra.confirmed = true;
  }
  if (operation === "unlink_carrier" && !window.confirm("Unlink this fleet carrier from your colonisation?")) return true;
  send(ui, operation, extra);
  return true;
}

export function handleColonisationSubmit(event, ui) {
  const form = event.target.closest?.("[data-co-form]");
  if (!form || !ui.byId("colonisation-workspace")?.contains(form)) return false;
  event.preventDefault();
  const values = Object.fromEntries(new FormData(form).entries());
  const kind = form.dataset.coForm;
  if (kind === "details") send(ui, "save_details", {build_id: form.dataset.buildId, ...values});
  else if (kind === "create") send(ui, "create_project", values);
  else if (kind === "architect_load") send(ui, "architect_load", {system: values.system || ""});
  else if (kind === "architect_save") {
    architectRows(form);
    send(ui, "architect_save", {architect: values.architect || "", reserve: values.reserve || "", open: Boolean(values.open),
      sites: architectDraft?.sites || [], delete: architectDraft?.deleted || []});
  }
  return true;
}

export function handleColonisationChange(event, ui, data) {
  const root = ui.byId("colonisation-workspace");
  if (!root || !root.contains(event.target)) return false;
  // Keep site edits in the draft, so a fresh snapshot redraw keeps them.
  if (event.target.matches("[data-co-site]")) {
    architectRows(root);
    return true;
  }
  const form = event.target.closest("[data-co-form=create]");
  if (!form) return false;
  const types = data?.build_types || [];
  if (event.target.matches("[data-co-location]")) {
    const orbital = event.target.value === "orbital";
    const buildSelect = form.querySelector("[data-co-build-type]");
    buildSelect.innerHTML = types.filter((row) => (row.location === "orbital") === orbital)
      .map((row) => `<option value="${ui.escapeHtml(row.build_type)}">Tier ${ui.escapeHtml(row.tier)}: ${ui.escapeHtml(row.name)}</option>`).join("");
  }
  if (event.target.matches("[data-co-location], [data-co-build-type]")) {
    const chosen = types.find((row) => row.build_type === form.querySelector("[data-co-build-type]").value);
    form.querySelector("[data-co-layout]").innerHTML = (chosen?.layouts || [])
      .map((layout) => `<option value="${ui.escapeHtml(layout)}">${ui.escapeHtml(layout.replace(/_/g, " "))}</option>`).join("");
  }
  return true;
}

export function resetColonisation() {
  view = "projects";
  architectDraft = null;
  architectKey = "";
}
