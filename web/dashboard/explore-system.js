/** SYSTEM (5.7.8): one system's body table, full width, with a body's
 * details beside it when you click one: everything about it, the genera its
 * conditions allow and those they don't, what your own runs found on worlds
 * like it, and the species other commanders reported there. The old survey
 * board (pin, skip, done) is the QUEUE mode. After ED-Outrider's Here view and
 * body panel (github.com/weslocke/ED-Outrider, GPLv3). */

import {credits, esc, fetchData, fixed, pref, setPref} from "./explore-table.js";
import {loadSystem, renderBodies} from "./explore-bodies.js";

let st = {ui: null, root: null, profile: "", system: "", id64: "", data: null, body: null, detail: null, rev: -1, polling: 0};

function factsMarkup(facts) {
  const rows = [["Class", facts.planet_class || facts.star_type], ["Atmosphere", facts.atmosphere], ["Volcanism", facts.volcanism],
    ["Temperature", facts.surface_temp !== undefined ? `${Math.round(facts.surface_temp)} K` : ""],
    ["Gravity", facts.gravity_g !== undefined ? `${fixed(facts.gravity_g, 2)} g` : ""],
    ["Pressure", facts.surface_pressure !== undefined ? `${fixed(facts.surface_pressure / 101325, 3)} atm` : ""],
    ["Radius", facts.radius ? `${Math.round(facts.radius / 1000).toLocaleString()} km` : ""],
    ["Distance", facts.distance_to_arrival !== undefined ? `${Math.round(facts.distance_to_arrival).toLocaleString()} ls` : ""],
    ["Landable", facts.landable ? "yes" : facts.landable === false ? "no" : ""], ["Terraformable", facts.terraformable ? "yes" : ""],
    ["Reserves", facts.reserve_level]].filter(([, value]) => value);
  return `<dl class="xy-facts">${rows.map(([key, value]) => `<dt>${esc(key)}</dt><dd>${esc(value)}</dd>`).join("")}</dl>`;
}

function detailMarkup(row, detail) {
  if (!row) return `<div class="xe-empty"><i aria-hidden="true">◎</i><b>No body picked</b><span>Click a body in the table for everything about it: its conditions and the genera they allow, what you found on worlds like it, and what other commanders reported there.</span></div>`;
  const bio = (row.bio || []).map((cell) => `<li class="xb-${esc(cell.state)}">${cell.state === "done" ? "✓ " : cell.state === "sampling" ? `${cell.progress}/3 ` : cell.state === "guess" ? "? " : ""}${esc(cell.name)}${cell.colour ? ` · ${esc(cell.colour)}` : ""} <small>${credits(cell.value)}</small></li>`).join("");
  const parts = [`<header><small>${esc(row.kind === "star" ? "STAR" : row.cls)}</small><h3>${esc(row.name)}</h3>
      <span>${row.first_discovered ? "⚑ first discovered by you · " : ""}${row.first_mapped ? "🗺 first mapped by you · " : ""}${row.footfall_open ? "👣 nobody has walked here · " : ""}now ${credits(row.value_now) || "0"} · max ${credits(row.value_max) || "0"}</span></header>`];
  if (detail?.facts && Object.keys(detail.facts).length) parts.push(factsMarkup(detail.facts));
  if (bio) parts.push(`<section><h4>BIOLOGY</h4><ul class="xy-list">${bio}</ul></section>`);
  if (detail?.expected?.length || detail?.not_expected?.length) {
    parts.push(`<section><h4>GENERA</h4><p><b>Its conditions allow:</b> ${esc((detail.expected || []).join(", ") || "none")}</p>
      <p class="xn-dim"><b>Not expected here</b> (temperature, gravity, atmosphere, volcanism or region rule them out): ${esc((detail.not_expected || []).join(", "))}</p></section>`);
  }
  if (detail?.similar?.length) {
    parts.push(`<section><h4>ON WORLDS LIKE THIS, YOU FOUND</h4><ul class="xy-list">${detail.similar.map(([name, count]) => `<li>${esc(name)} <small>×${count}</small></li>`).join("")}</ul></section>`);
  }
  const reported = (detail?.reported || []).filter((item) => !row.name || String(item.body || "").toLowerCase().endsWith(String(row.name).toLowerCase()));
  parts.push(`<section><h4>REPORTED BY OTHER COMMANDERS</h4>${reported.length ? `<ul class="xy-list">${reported.flatMap((item) => (item.variants || []).map(([species, colour]) => `<li>${esc(species)} · ${esc(colour)}</li>`)).join("")}</ul>`
    : `<p class="xn-dim">${detail?.reported_status === "working" ? "Asking Spansh…" : "Nothing reported on Spansh for this body."}</p>`}</section>`);
  const sites = detail?.sites || [];
  parts.push(`<section><h4>KNOWN SITES · CANONN</h4>${sites.length ? `<ul class="xy-list">${sites.map((site) => {
    const point = site.points ? site.points[0] : [site.lat, site.lon];
    return `<li>${esc(site.name)}${site.n ? ` <small>${site.n} reports</small>` : ""} <button type="button" data-xy-pin data-lat="${esc(point?.[0])}" data-lon="${esc(point?.[1])}" data-label="${esc(site.name)}" title="Pin it: the planet compass points you there">PIN</button></li>`;
  }).join("")}</ul>` : `<p class="xn-dim">${detail?.sites_status === "working" ? "Asking Canonn…" : "No Guardian sites or geology reported on this body."}</p>`}</section>`);
  if ((row.rings || []).length) parts.push(`<section><h4>RINGS</h4><ul class="xy-list">${row.rings.map((ring) => `<li>${esc(ring.name)} · ${esc(ring.type)}</li>`).join("")}</ul>${row.hotspots ? `<p>${row.hotspots} hotspots reported: see Mining Command for the best prices.</p>` : ""}</section>`);
  if (row.geo_new?.length) parts.push(`<section><h4>GEOLOGY NEW TO YOUR CODEX</h4><p>${esc(row.geo_new.join(", "))}: logged when you scan one on the surface.</p></section>`);
  return parts.join("");
}

async function openBody(row) {
  st.body = row;
  st.detail = null;
  drawDetail();
  st.ui.command("workspace", {page: "explore", operation: "system_reported", name: st.system, body: row.name,
    body_id: row.body_id ?? "", id64: st.data?.id64 || st.id64 || ""});
  try {
    st.detail = await fetchData(st.ui, "explore-body", {system: st.system, body: row.name});
  } catch (_error) {
    st.detail = null;
  }
  drawDetail();
}

function drawDetail() {
  const side = st.root?.querySelector("[data-xy-detail]");
  if (!side) return;
  side.innerHTML = detailMarkup(st.body, st.detail);
  if (!side.dataset.bound) {
    side.dataset.bound = "1";
    side.addEventListener("click", async (event) => {
      const pin = event.target.closest("[data-xy-pin]");
      if (!pin) return;
      if (await st.ui.command("workspace", {page: "explore", operation: "system_pin_site", lat: pin.dataset.lat, lon: pin.dataset.lon,
        label: pin.dataset.label, system: st.system, body: st.body?.name || ""})) st.ui.showToast?.(`${pin.dataset.label}: pinned on the planet compass`);
    });
  }
}

async function refresh() {
  if (!st.root || !st.system) return;
  try {
    const data = await loadSystem(st.ui, st.system, st.id64);
    st.data = data;
    renderBodies(st.root.querySelector(".xy-table"), data, st.ui, {profile: st.profile, id: "sys-bodies", onRow: openBody});
    if (st.body) {
      st.body = (data.rows || []).find((row) => row.key === st.body.key) || st.body;
      if (st.detail?.reported_status === "working" || st.detail?.sites_status === "working") {
        fetchData(st.ui, "explore-body", {system: st.system, body: st.body.name}).then((detail) => { st.detail = detail; drawDetail(); }).catch(() => {});
      }
    }
    clearTimeout(st.polling);
    if (data.status === "working") st.polling = setTimeout(refresh, 1500);
  } catch (_error) { /* asked again on the next revision */ }
}

/** Show a system's table. `rev` changes when anything it shows might have. */
export function renderSystemTable(panel, ui, rev, system, id64 = "") {
  if (!panel) return;
  st.ui = ui;
  st.profile = ui.profileKey();
  if (!panel.querySelector(".xy-shell")) {
    panel.innerHTML = `<div class="xy-shell"><section class="xy-table xe-card"><header class="xb-head" data-xb-head></header><div class="xt-box" data-xb-table></div><footer class="xb-legend" data-xb-legend></footer></section>
      <aside class="xy-detail xe-card" data-xy-detail></aside></div>`;
    st.root = panel;
    st.rev = -1;
    drawDetail();
  }
  st.root = panel;
  if (system && system !== st.system) {
    st.system = system;
    st.id64 = id64;
    st.body = null;
    st.detail = null;
    st.rev = -1;
    drawDetail();
  }
  if (rev === st.rev) return;
  st.rev = rev;
  refresh();
}

export function systemModes(profile) {
  return pref(profile, "system.mode", "table");
}

export function setSystemMode(profile, mode) {
  setPref(profile, "system.mode", mode);
}
