// System planner (5.5.2.1): a system's sites on Raven Colonial, with the
// website's economy, tier point, score and unlock model worked out on the
// Python side (colonisation/planner.py) as each change is sent.

const CLASS_ORDER = ["starport", "outpost", "installation", "hub", "settlement"];
const CLASS_NAMES = {starport: "Starports", outpost: "Outposts", installation: "Installations", hub: "Hubs", settlement: "Settlements"};
const expanded = new Set();
let showBodies = false;

const n = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
const count = (value) => n(value).toLocaleString("en-GB");
const signed = (value) => `${n(value) > 0 ? "+" : ""}${Number(n(value).toFixed(2))}`;

function typeOptions(plan, site, esc) {
  const current = String(site.build_type || "").toLowerCase();
  const points = plan.model.tier_points || {};
  const own = site.calc_needs || site.type.needs;
  const groups = {};
  for (const type of plan.types) (groups[type.class] ||= []).push(type);
  let found = !current;
  const html = CLASS_ORDER.filter((cls) => groups[cls]).map((cls) => `<optgroup label="${CLASS_NAMES[cls]}">${groups[cls].map((type) => type.layouts.map((layout) => {
    const value = layout.toLowerCase();
    if (value === current) found = true;
    let note = "";
    if (value !== current && type.needs.tier > 1 && type.needs.count > 0) {
      const available = n(points[`tier${type.needs.tier}`]) + (own && own.tier === type.needs.tier && site.in_calc ? n(own.count) : 0);
      if (available < type.needs.count) note = ` · short of T${type.needs.tier}`;
    }
    if (value !== current && !type.pre_req_ok) note += ` · ${type.pre_req}`;
    return `<option value="${esc(value)}"${value === current ? " selected" : ""}>T${type.tier} ${esc(type.name)} · ${esc(layout.replace(/_/g, " "))}${esc(note)}</option>`;
  }).join("")).join("")}</optgroup>`).join("");
  return `<option value=""${current ? "" : " selected"}>Unknown</option>${found ? "" : `<option value="${esc(current)}" selected>${esc(current)}</option>`}${html}`;
}

function economyText(site, names) {
  if (site.primary_economy) return names[site.primary_economy] || site.primary_economy;
  const inf = site.type.fixed || site.type.inf;
  return inf && inf !== "none" ? (names[inf] || inf) : "";
}

function summary(plan, esc) {
  const model = plan.model;
  const tp = model.tier_points || {};
  const effects = Object.entries(plan.effect_names).map(([key, label]) => {
    const value = n((model.effects || {})[key]);
    return `<li class="${value > 0 ? "up" : value < 0 ? "down" : ""}"><span>${esc(label)}</span><b>${signed(value)}</b></li>`;
  }).join("");
  const economies = Object.entries(model.economies || {}).map(([key, value]) => `<li><span>${esc(plan.economy_names[key] || key)}</span><b>${value}</b></li>`).join("") || "<li><span>None yet</span></li>";
  const unlocks = Object.entries(plan.unlock_info).map(([key, info]) => `<li class="${(model.unlocks || {})[key] ? "on" : ""}" title="Needs: ${esc(info.needs)}">${esc(info.title)}</li>`).join("");
  return `<section class="pl-summary">
    <div class="pl-figures">
      <div><small>SYSTEM SCORE</small><b>${count(model.score)}</b></div>
      <div class="${n(tp.tier2) < 0 ? "short" : ""}"><small>TIER 2 POINTS</small><b>${count(tp.tier2)}</b></div>
      <div class="${n(tp.tier3) < 0 ? "short" : ""}"><small>TIER 3 POINTS</small><b>${count(tp.tier3)}</b></div>
      <div><small>PLANNED HAUL</small><b>${count(plan.haul_planned)} T</b></div>
      <div><small>POPULATION</small><b>${plan.pop ? count(plan.pop.pop) : "—"}</b><button type="button" class="pl-mini" data-co-op="planner_pop" data-refresh="1" title="Refresh from Spansh and show the history">↻</button></div>
    </div>
    <div class="pl-options">
      <label class="co-check"><input type="checkbox" data-refresh-on-change data-co-change="planner_option" data-field="use_incomplete"${model.use_incomplete ? " checked" : ""}><span>Count planned and building sites (above the cut)</span></label>
      <label class="co-check"><input type="checkbox" data-refresh-on-change data-co-change="planner_option" data-field="buff_nerf"${model.buff_nerf ? " checked" : ""}><span>Apply the first-port buff and later nerf</span></label>
    </div>
    <div class="pl-columns">
      <section><h4>SYSTEM EFFECTS</h4><ul class="pl-effects">${effects}</ul></section>
      <section><h4>ECONOMIES</h4><ul class="pl-economies">${economies}</ul></section>
      <section><h4>SYSTEM UNLOCKS</h4><ul class="pl-unlocks">${unlocks}</ul></section>
    </div>
    ${plan.pop_history ? `<details class="pl-pop" open><summary>POPULATION HISTORY</summary><ol>${plan.pop_history.map((row) => `<li><span>${esc(String(row.time || "").slice(0, 10))}</span><b>${row.pop == null ? "—" : count(row.pop)}</b></li>`).join("")}</ol></details>` : ""}
  </section>`;
}

function siteRow(plan, site, esc, bodies, editable) {
  const names = plan.economy_names;
  const economies = Object.entries(site.economies || {}).sort((a, b) => b[1] - a[1]).slice(0, 3)
    .map(([key, value]) => `${esc(names[key] || key)} ${value.toFixed(2)}`).join(" · ");
  const needs = site.calc_needs || site.type.needs;
  const cost = needs && needs.tier > 1 && needs.count > 0 && site.index > 0 ? `−${needs.count} T${needs.tier}${site.calc_needs && site.calc_needs.count !== site.type.needs.count ? " (taxed)" : ""}` : "";
  const gives = site.type.gives && site.type.gives.tier > 1 && site.type.gives.count > 0 ? `+${site.type.gives.count} T${site.type.gives.tier}` : "";
  const links = site.links ? `${site.links.strong.length} strong · ${site.links.weak.length} weak` : site.parent_link ? `→ ${esc(site.parent_link)}` : "";
  const open = expanded.has(site.id);
  const dis = editable ? "" : " disabled";
  const project = site.project ? `<small class="pl-project">${site.project.remaining ? `${count(site.project.remaining)} left` : "building"}</small>` : "";
  return `<tr class="pl-site ${site.status}${site.in_calc ? "" : " out"}${site.dirty ? " dirty" : ""}${site.index === 0 ? " primary" : ""}" data-id="${esc(site.id)}">
    <td class="pl-order"><button type="button" class="pl-mini" data-co-op="planner_move" data-id="${esc(site.id)}" data-to="${site.index - 1}" title="Move up"${dis}>▲</button><button type="button" class="pl-mini" data-co-op="planner_move" data-id="${esc(site.id)}" data-to="${site.index + 1}" title="Move down"${dis}>▼</button></td>
    <td><input data-pl-site="name" data-id="${esc(site.id)}" value="${esc(site.name)}" maxlength="120"${dis}>${site.index === 0 ? `<small class="pl-tag">PRIMARY PORT</small>` : ""}${project}</td>
    <td><select data-refresh-on-change data-pl-site="bodyNum" data-id="${esc(site.id)}"${dis}><option value="-1">Unknown</option>${bodies}</select></td>
    <td><select data-refresh-on-change data-pl-site="buildType" data-id="${esc(site.id)}"${dis}>${typeOptions(plan, site, esc)}</select></td>
    <td><select data-refresh-on-change data-pl-site="status" data-id="${esc(site.id)}"${dis}>${plan.statuses.map((status) => `<option${status === site.status ? " selected" : ""}>${status}</option>`).join("")}</select></td>
    <td class="pl-econ"><b>${esc(economyText(site, names))}</b><small>${economies}</small></td>
    <td class="pl-links">${links}</td>
    <td class="num">${esc(cost)}${gives ? `<small>${esc(gives)}</small>` : ""}</td>
    <td class="pl-actions"><button type="button" class="pl-mini" data-pl-expand="${esc(site.id)}" title="Economy breakdown">${open ? "−" : "+"}</button>
      ${site.status === "plan" && site.build_type && !site.build_id && editable ? `<button type="button" class="pl-mini" data-co-op="planner_start_project" data-id="${esc(site.id)}" title="Start a Raven Colonial project for this site">▶</button>` : ""}
      <button type="button" class="pl-mini" data-co-op="planner_cut" data-index="${site.index + 1}" title="Cut the calculation below this site"${dis}>✂</button>
      <button type="button" class="pl-mini danger-action" data-co-op="planner_remove" data-id="${esc(site.id)}" title="Remove"${dis}>✕</button></td>
  </tr>${open ? `<tr class="pl-detail"><td colspan="9">${siteDetail(plan, site, esc)}</td></tr>` : ""}`;
}

function siteDetail(plan, site, esc) {
  const names = plan.economy_names;
  const audit = (site.audit || []).map((row) => `<li><span>${esc(names[row.inf] || row.inf)}</span><b class="${row.delta < 0 ? "down" : "up"}">${signed(row.delta)}</b><small>${esc(row.reason)}</small></li>`).join("");
  const effects = Object.entries(site.type.effects || {}).map(([key, value]) => `<li><span>${esc(plan.effect_names[key] || key)}</span><b>${signed(value)}</b></li>`).join("");
  const links = site.links ? Object.entries(site.links.economies || {}).map(([key, row]) => `<li><span>${esc(names[key] || key)}</span><b>${row.strong} strong · ${row.weak} weak</b></li>`).join("") : "";
  return `<div class="pl-detail-grid">
    <section><h4>${esc(site.type.name).toUpperCase()} · TIER ${site.type.tier}</h4><p>${esc(site.type.class)} · ${site.type.orbital ? "orbital" : "surface"} · ${esc(site.type.pad)} pads · score ${site.type.score} · ~${count(site.type.haul)} T to build</p><ul class="pl-effects">${effects || "<li>No system effects</li>"}</ul></section>
    <section><h4>ECONOMY BREAKDOWN</h4><ul class="pl-audit">${audit || "<li>No calculated economy (counts only when complete, or above the cut with planned sites counted).</li>"}</ul></section>
    <section><h4>LINKS</h4><ul class="pl-effects">${links || "<li>None</li>"}</ul>${site.links ? `<p><b>Strong:</b> ${esc(site.links.strong.join(", ") || "—")}</p><p><b>Weak:</b> ${esc(site.links.weak.join(", ") || "—")}</p>` : ""}</section>
  </div>`;
}

function bodiesPanel(plan, esc, editable) {
  const rows = plan.bodies.map((body) => {
    const features = plan.features.map((feature) => {
      const on = body.features.includes(feature);
      const next = on ? body.features.filter((item) => item !== feature) : [...body.features, feature];
      return `<button type="button" class="pl-chip${on ? " on" : ""}" data-co-op="planner_body_features" data-num="${body.num}" data-features="${esc(next.join(","))}"${editable ? "" : " disabled"}>${esc(feature)}</button>`;
    }).join("");
    const [orbital, surface] = body.slots || [-1, -1];
    return `<tr><td>${esc(body.name)}<small>${esc(body.type_name)}${body.sub_type ? ` · ${esc(body.sub_type)}` : ""}</small></td>
      <td class="num">${body.dist_ls == null || body.dist_ls < 0 ? "" : `${count(Math.round(body.dist_ls))} ls`}</td>
      <td class="pl-features">${features}</td>
      <td class="pl-slots"><input type="number" min="-1" max="20" value="${orbital}" data-refresh-on-change data-pl-slot="orbital" data-num="${body.num}" title="Orbital slots (-1 unknown)"${editable ? "" : " disabled"}>
        <input type="number" min="-1" max="20" value="${surface}" data-refresh-on-change data-pl-slot="surface" data-num="${body.num}" placeholder="${body.predicted_surface}" title="Surface slots (-1 unknown; about ${body.predicted_surface} expected)"${editable ? "" : " disabled"}></td>
      <td class="num">${body.sites || ""}</td></tr>`;
  }).join("");
  return `<details class="pl-bodies"${showBodies ? " open" : ""} data-pl-bodies><summary>BODIES (${plan.bodies.length})</summary>
    <table class="co-needs"><thead><tr><th>BODY</th><th>ARRIVAL</th><th>FEATURES</th><th>SLOTS O / S</th><th>SITES</th></tr></thead><tbody>${rows || `<tr><td colspan="5">No bodies yet: import them, or send your own scans.</td></tr>`}</tbody></table></details>`;
}

function identifyPanel(plan, esc) {
  const ident = plan.identify || {};
  if (!ident.active) return "";
  return `<section class="pl-identify"><header><b>STATION IDENTIFIER</b><span class="pl-phase">${esc(String(ident.phase || "").toUpperCase())}</span></header>
    <p>${esc(ident.message || "")}</p>${ident.pending_name ? `<p class="co-good">Waiting for the body ${esc(ident.pending_name)} orbits.</p>` : ""}
    ${(ident.log || []).length ? `<ul>${ident.log.map((line) => `<li>${esc(line)}</li>`).join("")}</ul>` : ""}
    <div class="co-form-actions">${ident.phase === "surface" ? `<button type="button" class="primary" data-co-op="planner_identify" data-action="finish">FINISHED</button>` : ""}
      ${ident.phase === "bodies" && plan.journal && plan.journal.ready ? `<button type="button" class="primary" data-co-op="planner_upload_bodies">UPLOAD MY SCANS</button>` : ""}
      <button type="button" data-co-op="planner_identify" data-action="stop">STOP</button></div></section>`;
}

export function renderPlanner(data, ui) {
  const esc = ui.escapeHtml;
  const plan = data.planner || {};
  const loader = `<form class="co-inline co-architect-load" data-co-form="planner_load"><input name="system" value="${esc(plan.loaded ? plan.name : plan.system_hint || "")}" placeholder="SYSTEM NAME" maxlength="160">
    <button type="submit">LOAD SYSTEM</button><button type="button" data-co-op="planner_mine">MY SYSTEMS</button>
    ${plan.loaded ? "" : `<button type="button" data-co-op="planner_import" data-kind="bodies" data-system-from-input="1">IMPORT FROM SPANSH</button>`}</form>`;
  const mine = Array.isArray(plan.mine) ? `<section class="pl-mine"><h4>YOUR SYSTEMS</h4>${plan.mine.length ? `<ul>${plan.mine.map((row) => `<li><button type="button" data-co-op="planner_load" data-system="${esc(row.name)}">${row.fav ? "★ " : ""}${esc(row.nickname || row.name)}</button><small>score ${count(row.score)}${row.tier_points ? ` · T2 ${row.tier_points.tier2} · T3 ${row.tier_points.tier3}` : ""}${row.stale ? " · stale" : ""}</small></li>`).join("")}</ul>` : "<p>You are not the architect of any system yet.</p>"}</section>` : "";
  if (!plan.loaded) {
    return `${loader}${mine}<div class="co-empty"><b>PLAN A SYSTEM</b><span>Load a system to plan its sites: tier points, economies, links, system effects, score and unlocks are worked out as you go, the way Raven Colonial's website does.</span></div>`;
  }
  const editable = plan.can_edit;
  const bodyOptions = plan.bodies.map((body) => `<option value="${body.num}">${esc(body.name)}</option>`).join("");
  const sites = plan.sites.map((site) => {
    const row = siteRow(plan, site, esc, bodyOptions.replace(`value="${site.body_num}"`, `value="${site.body_num}" selected`), editable);
    const cut = plan.idx_calc_limit === site.index + 1 && site.index + 1 < plan.sites.length
      ? `<tr class="pl-cut"><td colspan="9">CALCULATION CUT · sites below are left out when planned sites are counted</td></tr>` : "";
    return row + cut;
  }).join("");
  const status = plan.viewing_rev ? `VIEWING REVISION ${plan.viewing_rev}` : plan.save_name ? `NAMED SAVE: ${esc(plan.save_name)}` : `REVISION ${plan.rev ?? "—"}`;
  return `${loader}${mine}
    <header class="pl-head"><div><p>${status}${editable ? "" : " · READ ONLY (save a named copy)"}</p><h3>${plan.fav ? "★ " : ""}${esc(plan.fields.nickname || plan.name)}</h3><span>${esc(plan.name)}${plan.fields.architect ? ` · architect ${esc(plan.fields.architect)}` : ""}</span></div>
      <div class="co-head-actions">
        <button type="button" class="primary" data-co-op="planner_save"${plan.dirty && editable ? "" : " disabled"}>SAVE</button>
        <button type="button" data-co-op="planner_discard"${plan.dirty ? "" : " disabled"}>DISCARD</button>
        <button type="button" data-co-op="planner_fav" data-value="${plan.fav ? "" : "1"}">${plan.fav ? "UNFAVOURITE" : "FAVOURITE"}</button>
        <button type="button" data-co-op="planner_identify" data-action="start"${editable ? "" : " disabled"}>IDENTIFY STATIONS</button>
        ${plan.journal && plan.journal.ready ? `<button type="button" data-co-op="planner_upload_bodies" title="${plan.journal.scanned} of ${plan.journal.body_count} bodies scanned here">UPLOAD MY SCANS</button>` : ""}
        <button type="button" data-co-op="planner_import" data-system="${esc(plan.name)}" data-kind="bodies">RE-IMPORT BODIES</button>
        <button type="button" data-co-op="planner_open">OPEN ON RAVEN</button></div></header>
    <div class="pl-versions">
      ${plan.revs.length ? `<label><span>REVISIONS</span><select data-refresh-on-change data-co-change="planner_load" data-field="rev" data-system="${esc(plan.name)}"><option value="">Latest</option>${plan.revs.map((rev) => `<option value="${rev.rev}"${plan.viewing_rev === rev.rev ? " selected" : ""}>#${rev.rev} · ${esc(rev.cmdr)} · ${esc(String(rev.time || "").slice(0, 10))}</option>`).join("")}</select></label>` : ""}
      ${plan.saved_names.length ? `<label><span>NAMED SAVES</span><select data-refresh-on-change data-co-change="planner_load" data-field="save_name" data-system="${esc(plan.name)}"><option value="">—</option>${plan.saved_names.map((row) => `<option value="${esc(row.name)}"${plan.save_name === row.name ? " selected" : ""}>${esc(row.name)} · ${esc(row.cmdr)}</option>`).join("")}</select></label>
        ${plan.save_name ? `<button type="button" class="danger-action" data-co-op="planner_delete_save" data-save-name="${esc(plan.save_name)}">DELETE THIS SAVE</button>` : ""}` : ""}
      <form class="co-inline" data-co-form="planner_save_as"><input name="save_name" placeholder="Named copy" maxlength="80"><button type="submit">SAVE AS</button></form>
    </div>
    ${identifyPanel(plan, esc)}
    ${summary(plan, esc)}
    <section class="pl-fields">
      <label><span>Architect</span><input data-pl-field="architect" value="${esc(plan.fields.architect)}" maxlength="80"${editable ? "" : " disabled"}></label>
      <label><span>Nickname</span><input data-pl-field="nickname" value="${esc(plan.fields.nickname)}" maxlength="80"${editable ? "" : " disabled"}></label>
      <label><span>Reserve level</span><select data-refresh-on-change data-pl-field="reserveLevel"${editable ? "" : " disabled"}><option value="">Unknown (pristine)</option>${plan.reserves.map((level) => `<option${level === plan.fields.reserveLevel ? " selected" : ""}>${level}</option>`).join("")}</select></label>
      <label class="co-check"><input type="checkbox" data-refresh-on-change data-co-change="planner_field" data-field="open"${plan.fields.open ? " checked" : ""}${editable ? "" : " disabled"}><span>Open to other architects</span></label>
      <label class="wide"><span>Notes</span><textarea data-pl-field="notes" rows="2" maxlength="4000"${editable ? "" : " disabled"}>${esc(plan.fields.notes)}</textarea></label>
    </section>
    <div class="pl-table-wrap"><table class="co-sites pl-table"><thead><tr><th></th><th>SITE</th><th>BODY</th><th>BUILD TYPE</th><th>STATUS</th><th>ECONOMY</th><th>LINKS</th><th>POINTS</th><th></th></tr></thead>
      <tbody>${sites || `<tr><td colspan="9">No sites yet: the first one you add is the primary port.</td></tr>`}</tbody></table></div>
    <div class="co-form-actions"><button type="button" data-co-op="planner_add"${editable ? "" : " disabled"}>ADD SITE</button><button type="button" data-co-op="planner_cut" data-index="${plan.sites.length}"${editable ? "" : " disabled"}>NO CUT</button><small>${plan.sites.length} sites · ${plan.bodies.length} bodies</small></div>
    ${bodiesPanel(plan, esc, editable)}`;
}

export function plannerClick(event, send) {
  const expand = event.target.closest("[data-pl-expand]");
  if (expand) {
    const id = expand.dataset.plExpand;
    if (expanded.has(id)) expanded.delete(id); else expanded.add(id);
    return "rerender";
  }
  const bodies = event.target.closest("[data-pl-bodies] > summary");
  if (bodies) {
    showBodies = !bodies.parentElement.open;
    return "handled-default";
  }
  return null;
}

export function plannerChange(event, send) {
  const target = event.target;
  if (target.matches("[data-pl-site]")) {
    send("planner_site", {id: target.dataset.id, field: target.dataset.plSite, value: target.value});
    return true;
  }
  if (target.matches("[data-pl-field]")) {
    send("planner_field", {field: target.dataset.plField, value: target.value});
    return true;
  }
  if (target.matches("[data-pl-slot]")) {
    const row = target.closest(".pl-slots");
    send("planner_slots", {num: target.dataset.num, orbital: row.querySelector("[data-pl-slot=orbital]").value,
      surface: row.querySelector("[data-pl-slot=surface]").value});
    return true;
  }
  return false;
}

export function resetPlanner() {
  expanded.clear();
  showBodies = false;
}
