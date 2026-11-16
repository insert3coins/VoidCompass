/** The Route page (5.7.8, PLOT ROUTE out of Explore & Survey): every plotter in one place (Spansh's neutron and
 * exact plotters, Road to Riches, Exomastery, Earth-like, ammonia and
 * terraformable worlds, and a sweep through ticked systems), one route list
 * that follows you as you fly it, and the nearest place to
 * dock. After ED-Outrider's Plot Route (github.com/weslocke/ED-Outrider, GPLv3).
 * Trade routes stay on Trading, carrier routes on Carrier Command. */

import {credits, esc, fetchData, fixed, pref, renderTable, setPref, starPip} from "./explore-table.js";

const SURVEY = new Set(["riches", "exo", "elw", "aw", "tf"]);
const DOCK_SERVICES = [["uc", "Universal Cartographics"], ["vista", "Vista Genomics"], ["refuel", "Refuel"], ["repair", "Repair"],
  ["rearm", "Restock"], ["shipyard", "Shipyard"], ["outfitting", "Outfitting"], ["trader", "Material trader"],
  ["broker", "Technology broker"], ["factors", "Interstellar Factors"], ["market", "Market"], ["black_market", "Black market"]];

let st = {ui: null, root: null, profile: "", data: null, rev: -1, loading: false};

function form() {
  return pref(st.profile, "route.form", {plotter: "neutron", to: "", ship: "", range: "", conservative: false, conservative_ly: 2,
    efficiency: 60, radius: 25, max_results: 100, max_distance: 50, min_value: 1000000, loop: true, use_mapping_value: true,
    avoid_thargoids: true, injections: false, exclude_secondary: false, no_neutrons: false, supercharged: false,
    dock: {centre: "here", services: ["uc"], pad: "L", carriers: true, dssa: false, max_age_days: 30, trader: ""}});
}

function formMarkup(data) {
  const f = form();
  const kinds = Object.entries(data.kinds || {}).map(([id, name]) => `<button type="button" data-xr-plotter="${esc(id)}" aria-pressed="${f.plotter === id}">${esc(name.toUpperCase())}</button>`).join("");
  const ships = (data.ships || []).map((ship) => `<option value="${esc(ship.id)}" ${f.ship === ship.id || (!f.ship && ship.current) ? "selected" : ""}>${esc(ship.name || ship.type)}${ship.current ? " (now)" : ""} · ${fixed(ship.range, 1)} ly${ship.exact ? "" : " · neutron only"}${ship.scoop ? "" : " · no scoop"}</option>`).join("");
  const survey = SURVEY.has(f.plotter);
  const check = (key, text, title = "") => `<label${title ? ` title="${esc(title)}"` : ""}><input type="checkbox" data-xr-flag="${key}" ${f[key] ? "checked" : ""}> ${text}</label>`;
  const num = (key, text, attrs = "") => `<label>${text}<input type="number" data-xr-field="${key}" value="${esc(f[key])}" ${attrs}></label>`;
  return `<div class="xr-plotters" role="group" aria-label="Plotter">${kinds}</div>
    <div class="xr-form">
      <label>FROM<input data-xr-field="from" placeholder="${esc(data.current || "WHERE YOU ARE")}" value=""></label>
      ${f.plotter === "sweep" ? `<p class="xn-note">A sweep flies the systems you tick in Search, Firsts or your bookmarks, in the best order. Tick them there.</p>` : `<label>TO${survey ? " (OPTIONAL)" : ""}<input data-xr-field="to" placeholder="DESTINATION" value="${esc(f.to)}"></label>`}
      <label>SHIP<select data-xr-field="ship"><option value="">Type a range instead</option>${ships}</select></label>
      ${num("range", "RANGE LY", 'min="1" max="1000" step="0.1" placeholder="FROM THE SHIP"')}
      ${check("conservative", "conservative", "Plan with a slightly shorter range, so a fuller tank or cargo never leaves a jump out of reach")}
      ${f.conservative ? num("conservative_ly", "BY LY", 'min="0.5" max="10" step="0.5"') : ""}
      ${f.plotter === "neutron" ? num("efficiency", "EFFICIENCY", 'min="1" max="100"') : ""}
      ${f.plotter === "exact" ? [check("supercharged", "already supercharged"), check("no_neutrons", "no neutron boosts"),
        check("injections", "FSD injections"), check("exclude_secondary", "no secondary stars")].join("") : ""}
      ${survey ? [num("radius", "RADIUS", 'min="1" max="1000"'), num("max_results", "SYSTEMS", 'min="1" max="2000"'),
        num("max_distance", "MAX LS", 'min="1" max="1000000"'), f.plotter === "riches" || f.plotter === "exo" ? num("min_value", "MIN VALUE", 'min="1" step="100000"') : "",
        f.plotter === "riches" ? check("use_mapping_value", "count mapping") : "", check("avoid_thargoids", "avoid Thargoids"), check("loop", "back to the start")].join("") : ""}
      <button type="button" class="primary" data-xr-plot>PLOT</button>
      <button type="button" data-xr-waypoints title="Follow your waypoint route (and an expedition's FLY IT) here">FOLLOW MY WAYPOINTS</button>
      <button type="button" class="xr-autocopy" data-xr-autocopy aria-pressed="${Boolean(data.auto_copy)}" title="As you arrive in a system, the next stop goes on the clipboard (the same switch as in Settings)">AUTO-COPY NEXT · ${data.auto_copy ? "ON" : "OFF"}</button>
      <span class="xr-links"><button type="button" data-page="trading">TRADE ROUTES ›</button><button type="button" data-page="carrier">CARRIER ROUTES ›</button></span>
    </div>`;
}

function rowCell(row) {
  const marks = [row.neutron ? `<span class="xr-neutron" title="neutron star: supercharge">⚡</span>` : "",
    row.refuel ? `<span class="xr-refuel" title="refuel here">⛽</span>` : "",
    row.permit ? `<span class="xr-permit" title="needs a permit">🔒</span>` : ""].join("");
  return `${starPip(row.star_class || (row.neutron ? "N" : ""))}<b>${esc(row.system)}</b>${row.here ? ` <em class="xn-here">HERE</em>` : ""}${marks ? ` ${marks}` : ""}${row.left ? `<div class="xr-left">${esc(row.left)}</div>` : ""}${(row.bodies || []).length ? `<div class="xr-bodies">${row.bodies.slice(0, 5).map((body) =>
    `${esc(body.name)}${body.species?.length ? ` <small>${esc(body.species.map((s) => s.name).join(", "))}</small>` : body.map ? ` <small>${credits(body.map)}</small>` : ""}`).join(" · ")}</div>` : ""}`;
}

const COLUMNS = [
  {id: "n", label: "#", cell: (row) => row.index, cls: "xt-num"},
  {id: "system", label: "SYSTEM", cell: rowCell},
  {id: "jumps", label: "JUMPS", short: "J", cell: (row) => (row.index ? row.jumps : ""), cls: "xt-num", fit: 3},
  {id: "ly", label: "LY", cell: (row) => fixed(row.distance, 1), cls: "xt-num"},
  {id: "fuel", label: "FUEL LEFT", short: "FUEL", cell: (row) => (row.fuel_left !== null && row.fuel_left !== undefined ? `${fixed(row.fuel_left, 1)} t` : ""), cls: "xt-num", fit: 2},
  {id: "left", label: "TO GO", cell: (row) => fixed(row.remaining, 0), cls: "xt-num", fit: 3},
  {id: "act", label: "", cell: actCell},
];

// Each stop copies; the next one's copy stands out, and a stop ahead can be
// marked done to go on to the one after it.
function actCell(row) {
  if (!row.system) return "";
  const copy = `<button type="button" class="${row.next ? "xr-copy-next" : ""}" data-xr-copy="${esc(row.system)}" title="${row.next ? "Copy the next stop" : "Copy this system"}">${row.next ? "⧉ NEXT" : "⧉"}</button>`;
  const ahead = !row.passed && !row.here && row.index > 0;
  const skip = ahead ? `<button type="button" data-xr-skip="${row.index}" aria-pressed="${Boolean(row.skipped)}" title="${row.skipped ? "Fly to this stop after all" : "Mark done: skip this stop"}">${row.skipped ? "↺" : "✓"}</button>` : "";
  return `<span class="xn-acts">${copy}${skip}</span>`;
}

function headMarkup(data) {
  const route = data.route;
  const plotting = data.plotting || {};
  if (!route) return `<p class="xn-status">${esc(plotting.detail || "No route yet: plot one, or follow your waypoints.")}</p>`;
  const eta = route.eta_s ? `${Math.floor(route.eta_s / 3600)} h ${Math.round(route.eta_s % 3600 / 60)} min at your pace` : "";
  const warnings = [route.off_route ? `<div class="xr-warn">↯ Off the route: a detour. <button type="button" data-ws-page="explore" data-ws-op="plot_replot">RE-PLOT FROM HERE</button></div>` : "",
    route.other_ship ? `<div class="xr-warn">⚠ Plotted for your ${esc(route.ship?.name || route.ship?.type || "other ship")}, not the one you're flying.</div>` : "",
    route.fuel ? `<div class="xr-warn xr-fuel-${esc(route.fuel.state)}">⛽ ${esc(route.fuel.text)}</div>` : "",
    route.target_check ? `<div class="xr-target xr-target-${esc(route.target_check.state)}">${esc(route.target_check.text)}</div>` : "",
    route.permits ? `<div class="xr-note">🔒 ${route.permits} stop${route.permits === 1 ? " needs" : "s need"} a permit.</div>` : "",
    route.note ? `<div class="xr-note">${esc(route.note)}</div>` : "",
    route.done_at ? `<div class="xr-done">✓ Route complete: it clears itself when you move on.</div>` : ""].join("");
  return `<div class="xr-head"><div><small>${esc(route.label.toUpperCase())} · ${esc(route.from)} → ${esc(route.to)}</small>
      <b>${route.next ? `Next: ${esc(route.next)}` : "—"}</b>
      <span>${route.jumps_left || 0} jumps left${route.ly_left ? ` · ${fixed(route.ly_left, 0)} ly` : ""}${eta ? ` · ${eta}` : ""}${route.refuel_in ? ` · refuel in ${route.refuel_in}` : ""}</span></div>
      <div class="xr-tools"><button type="button" data-ws-page="explore" data-ws-op="plot_replot">RE-PLOT</button><button type="button" class="danger-action" data-ws-page="explore" data-ws-op="plot_clear">CLEAR</button></div></div>
    ${warnings}<p class="xn-status">${esc(plotting.detail || "")}</p>`;
}

function dockMarkup(data) {
  const f = form().dock;
  const dock = data.dock || {};
  const services = DOCK_SERVICES.map(([id, label]) => `<label><input type="checkbox" data-xr-dock-service value="${id}" ${f.services.includes(id) ? "checked" : ""}> ${label}</label>`).join("");
  const rows = (dock.rows || []).map((row) => `<tr><td><b>${esc(row.name)}</b>${row.dssa ? ` <em class="xr-dssa" title="Deep Space Support Array carrier">DSSA</em>` : ""}<div class="xn-dim">${esc(row.type)}</div></td><td>${esc(row.system)}</td>
      <td class="xt-num">${fixed(row.distance, 1)}</td><td class="xt-num">${row.ls ? Math.round(row.ls).toLocaleString() : ""}</td><td>${row.large ? "L" : "M"}</td><td>${esc(row.updated)}</td>
      <td><span class="xn-acts"><button type="button" data-xr-dock-copy="${esc(row.system)}" title="Copy the system">⧉</button></span></td></tr>`).join("");
  return `<section class="xr-dock"><h4>NEAREST PLACE TO DOCK</h4>
    <div class="xr-dock-form">
      <select data-xr-dock="centre">${[["here", "Around you"], ["destination", "Around your destination"], ["carrier", "Around your carrier"], ["next_stop", "Around your next stop"]]
        .map(([id, label]) => `<option value="${id}" ${f.centre === id ? "selected" : ""}>${label}</option>`).join("")}</select>
      <select data-xr-dock="pad"><option value="L" ${f.pad === "L" ? "selected" : ""}>Large pad</option><option value="M" ${f.pad === "M" ? "selected" : ""}>Medium pad</option><option value="S" ${f.pad === "S" ? "selected" : ""}>Any pad</option></select>
      <select data-xr-dock="trader"><option value="">Any trader</option>${["raw", "manufactured", "encoded"].map((kind) => `<option value="${kind}" ${f.trader === kind ? "selected" : ""}>${kind} trader</option>`).join("")}</select>
      <label>REPORTS UNDER<input type="number" data-xr-dock="max_age_days" min="1" max="3650" value="${esc(f.max_age_days)}"> DAYS</label>
      <label><input type="checkbox" data-xr-dock-flag="carriers" ${f.carriers ? "checked" : ""}> fleet carriers</label>
      <label title="Carriers the Deep Space Support Array keeps out in the black (EDAstro's list)"><input type="checkbox" data-xr-dock-flag="dssa" ${f.dssa ? "checked" : ""}> DSSA carriers</label>
      <button type="button" class="primary" data-xr-dock-go>FIND</button>
    </div>
    <div class="xr-dock-services">${services}</div>
    <p class="xn-status">${esc(dock.detail || "")}</p>
    <div class="xt-box"><table class="xt-table"><thead><tr><th>PLACE</th><th>SYSTEM</th><th class="xt-num">LY</th><th class="xt-num">LS</th><th>PAD</th><th>REPORTED</th><th></th></tr></thead><tbody>${rows || `<tr class="xt-empty"><td colspan="7">${dock.status === "working" ? "Looking…" : "Choose the services and FIND."}</td></tr>`}</tbody></table></div>
  </section>`;
}

function readForm() {
  const root = st.root;
  const f = form();
  const next = {...f};
  for (const input of root.querySelectorAll("[data-xr-field]")) {
    const key = input.dataset.xrField;
    if (key === "from") continue;
    next[key] = input.type === "number" ? (input.value === "" ? "" : Number(input.value)) : input.value;
  }
  for (const box of root.querySelectorAll("[data-xr-flag]")) next[box.dataset.xrFlag] = box.checked;
  const dock = {...f.dock};
  for (const input of root.querySelectorAll("[data-xr-dock]")) dock[input.dataset.xrDock] = input.type === "number" ? Number(input.value) : input.value;
  for (const box of root.querySelectorAll("[data-xr-dock-flag]")) dock[box.dataset.xrDockFlag] = box.checked;
  dock.services = [...root.querySelectorAll("[data-xr-dock-service]:checked")].map((box) => box.value);
  next.dock = dock;
  setPref(st.profile, "route.form", next);
  return next;
}

function bind(root) {
  if (root.dataset.xrBound) return;
  root.dataset.xrBound = "1";
  root.addEventListener("change", (event) => {
    if (!event.target.closest(".xr-form, .xr-dock")) return;
    readForm();
    if (event.target.matches('[data-xr-flag="conservative"]')) drawForm(true);
  });
  root.addEventListener("click", async (event) => {
    const ui = st.ui;
    const plotter = event.target.closest("[data-xr-plotter]");
    if (plotter) {
      setPref(st.profile, "route.form", {...readForm(), plotter: plotter.dataset.xrPlotter});
      drawForm(true);
      return;
    }
    if (event.target.closest("[data-xr-plot]")) {
      const f = readForm();
      const from = root.querySelector('[data-xr-field="from"]')?.value.trim() || "";
      ui.command("workspace", {page: "explore", operation: "plot_route", ...f, dock: undefined, from,
        range: f.ship ? "" : f.range, systems: f.plotter === "sweep" ? pref(st.profile, "sweep.systems", []) : undefined});
      return;
    }
    if (event.target.closest("[data-xr-waypoints]")) {
      ui.command("workspace", {page: "explore", operation: "plot_follow_waypoints"});
      return;
    }
    if (event.target.closest("[data-xr-autocopy]")) {
      const on = !st.data?.auto_copy;
      if (await ui.command("workspace", {page: "explore", operation: "set_auto_copy", enabled: on}) && st.data) {
        st.data.auto_copy = on;
        drawForm(true);
        ui.showToast?.(on ? "Auto-copy on: the next stop goes on the clipboard as you arrive" : "Auto-copy off");
      }
      return;
    }
    if (event.target.closest("[data-xr-dock-go]")) {
      const f = readForm();
      ui.command("workspace", {page: "explore", operation: "plot_dock", ...f.dock});
      return;
    }
    const copy = event.target.closest("[data-xr-dock-copy], [data-xr-copy]");
    if (copy) {
      const name = copy.dataset.xrDockCopy || copy.dataset.xrCopy;
      if (await ui.command("workspace", {page: "explore", operation: "copy_system", name})) ui.showToast?.(`${name} copied`);
      return;
    }
    const skip = event.target.closest("[data-xr-skip]");
    if (skip) {
      ui.command("workspace", {page: "explore", operation: "plot_skip", index: Number(skip.dataset.xrSkip),
        on: skip.getAttribute("aria-pressed") !== "true"});
    }
  });
}

function drawForm(force = false) {
  const slot = st.root.querySelector("[data-xr-form]");
  if (!slot || !st.data) return;
  if (!force && slot.contains(document.activeElement)) return;
  const html = formMarkup(st.data);
  if (force || slot._html !== html) {
    slot._html = html;
    slot.innerHTML = html;
  }
}

function draw() {
  const root = st.root;
  if (!root || !st.data) return;
  drawForm();
  const head = root.querySelector("[data-xr-head]");
  const headHtml = headMarkup(st.data);
  if (head && head._html !== headHtml) {
    head._html = headHtml;
    head.innerHTML = headHtml;
  }
  renderTable(root.querySelector("[data-xr-table]"), {
    id: "route", profile: st.profile, columns: COLUMNS, rows: st.data.route?.rows || [], key: (row) => `${row.index}`,
    rowClass: (row) => [row.passed ? "xr-passed" : "", row.here ? "xr-here" : "", row.finished ? "xr-finished" : "",
      row.skipped ? "xr-skipped" : "", row.next ? "xr-next" : ""].join(" "),
    sort: {col: "n", dir: "asc"}, empty: "No route.",
  });
  const dock = root.querySelector("[data-xr-dockslot]");
  // Kept while you type or pick in its form; a focused button (FIND) doesn't hold it.
  if (dock && !dock.contains(document.activeElement?.matches?.("input, select") ? document.activeElement : null)) {
    const html = dockMarkup(st.data);
    if (dock._html !== html) {
      dock._html = html;
      dock.innerHTML = html;
    }
  }
}

export function renderRoute(panel, ui, rev) {
  if (!panel) return;
  st.ui = ui;
  st.profile = ui.profileKey();
  if (!panel.querySelector(".xr-shell")) {
    // Three cards (5.7.8 redesign): the plotter, the route it made, and the nearest place to dock beside them.
    panel.innerHTML = `<div class="xr-shell"><section class="xr-plot xe-card"><header class="xe-card-head"><div><small>SPANSH PLOTTERS</small><h3>Plot a route</h3></div></header><div class="xr-plot-body" data-xr-form></div></section>
      <section class="xr-main xe-card"><div class="xr-list"><div class="xr-head-slot" data-xr-head></div><div class="xt-box" data-xr-table></div></div></section><div class="xr-dock-slot" data-xr-dockslot></div></div>`;
    st.root = panel;
    bind(panel);
    st.rev = -1;
  }
  st.root = panel;
  if (rev === st.rev) return;
  if (st.loading) {
    st.wanted = rev;
    return;
  }
  st.rev = rev;
  st.loading = true;
  fetchData(ui, "explore-route").then((data) => {
    st.data = data;
    draw();
  }).catch(() => {}).finally(() => {
    st.loading = false;
    const wanted = st.wanted;
    st.wanted = undefined;
    if (wanted !== undefined && wanted !== st.rev) renderRoute(st.root, st.ui, wanted);
  });
}

/** Systems ticked elsewhere (Search, Firsts, bookmarks) for the next sweep. */
export function setSweep(profile, systems) {
  setPref(profile, "sweep.systems", systems);
}
