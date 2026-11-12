/** SEARCH (5.7.8): find exactly this. Tick boxes in sections; any tick in a
 * section counts, and a system must match every section you ticked. Spansh
 * searches what other commanders reported; Local only your own scans, which
 * can say what Spansh can't. After ED-Outrider's Search
 * (github.com/weslocke/ED-Outrider, GPLv3). Exploration Scout's prospect
 * searches stay below as presets. */

import {esc, fetchData, fixed, pref, renderTable, setPref} from "./explore-table.js";

const LABELS = {
  stars: {o: "O", b: "B", a: "A", f: "F", g: "G", k: "K", m: "M", brown: "Brown dwarf", neutron: "Neutron star",
    black_hole: "Black hole", white_dwarf: "White dwarf", wolf_rayet: "Wolf-Rayet", carbon: "Carbon star", proto: "T Tauri / Herbig", giant: "Giant"},
  planets: {elw: "Earth-like", ww: "Water world", aw: "Ammonia world", ggw: "GG water life", gga: "GG ammonia life", wg: "Water giant",
    tf: "Terraformable", landable: "Landable"},
  rings: {icy: "Icy", rocky: "Rocky", metal_rich: "Metal rich", metallic: "Metallic"},
  mining: {geo: "Geological signals", mining: "Mining locations (Local)", ggg: "Potential green gas giant (Local)"},
};
const SECTION_NAMES = {stars: "STARS", planets: "PLANETS", rings: "RINGS", hotspots: "HOTSPOTS", bio: "EXOBIOLOGY", mining: "PLANETARY MINING"};

let st = {ui: null, root: null, profile: "", data: null, rev: -1, ticked: new Set(), loading: false};

function form() {
  return pref(st.profile, "search.form", {source: "spansh", ticks: {}, radius: 100, at_least: 1, arrival_only: false,
    two_hotspots: false, min_signals: 1, centre: "here", name: ""});
}

function label(section, tick) {
  if (LABELS[section]?.[tick]) return LABELS[section][tick];
  if (section === "bio") return tick === "any" ? "Any biology (signals ≥ N)" : tick === "bio_left" ? "Unfinished biology (Local)" : tick;
  return tick;
}

function formMarkup(options) {
  const f = form();
  const sections = Object.keys(SECTION_NAMES).map((section) => {
    const ticks = options?.[section] || [];
    const chosen = new Set(f.ticks?.[section] || []);
    return `<fieldset class="xs-section"><legend>${SECTION_NAMES[section]}</legend>${ticks.map((tick) =>
      `<label class="${options.local_only?.includes(tick) || tick === "mining" || tick === "ggg" ? "xs-local" : ""}"><input type="checkbox" data-xs-tick="${esc(section)}" value="${esc(tick)}" ${chosen.has(tick) ? "checked" : ""}> ${esc(label(section, tick))}</label>`).join("")}</fieldset>`;
  }).join("");
  return `<div class="xs-find"><input data-xs-find placeholder="FIND A SYSTEM BY NAME"><button type="button" data-xs-find-go>FIND</button></div>
    <div class="xs-form">
      <div class="xs-top">
        <span class="xs-source" role="group" aria-label="Search where"><button type="button" data-xs-source="spansh" aria-pressed="${f.source !== "local"}">SPANSH</button><button type="button" data-xs-source="local" aria-pressed="${f.source === "local"}" title="Only your own scans: it can find unfinished biology, mining locations and potential green gas giants, but only where you've been">LOCAL</button></span>
        <label>WITHIN<input type="number" data-xs-field="radius" min="1" max="1000" value="${esc(f.radius)}"> LY OF</label>
        <select data-xs-field="centre">${[["here", "you"], ["destination", "your destination"], ["carrier", "your carrier"], ["next_stop", "your next stop"], ["system", "a system…"]]
          .map(([id, text]) => `<option value="${id}" ${f.centre === id ? "selected" : ""}>${text}</option>`).join("")}</select>
        <input data-xs-field="name" placeholder="SYSTEM" value="${esc(f.name || "")}" ${f.centre === "system" ? "" : "hidden"}>
        <label>AT LEAST<input type="number" data-xs-field="at_least" min="1" max="20" value="${esc(f.at_least)}"></label>
        <label title="Exobiology's 'any biology': how many signals at least">SIGNALS ≥<input type="number" data-xs-field="min_signals" min="1" max="20" value="${esc(f.min_signals)}"></label>
        <label><input type="checkbox" data-xs-flag="arrival_only" ${f.arrival_only ? "checked" : ""}> arrival star only</label>
        <label><input type="checkbox" data-xs-flag="two_hotspots" ${f.two_hotspots ? "checked" : ""}> 2+ hotspots in a ring</label>
        <button type="button" class="primary" data-xs-run>SEARCH</button>
        <button type="button" data-xs-clear>CLEAR</button>
      </div>
      <div class="xs-sections">${sections}</div>
    </div>`;
}

function matchesCell(row) {
  const groups = {};
  for (const match of row.matches || []) (groups[match.section] ||= []).push(`${esc(match.body)} <small>${esc(label(match.section, match.what))}</small>`);
  return Object.entries(groups).map(([section, bodies]) => `<div><b>${SECTION_NAMES[section] || section}</b> ${bodies.slice(0, 6).join(", ")}${bodies.length > 6 ? ` +${bodies.length - 6}` : ""}</div>`).join("");
}

const COLUMNS = [
  {id: "tick", label: "", cell: (row) => `<input type="checkbox" data-xs-pick value="${esc(row.system)}" ${st.ticked.has(row.system) ? "checked" : ""} aria-label="Tick ${esc(row.system)} for a sweep">`},
  {id: "system", label: "SYSTEM", cell: (row) => `<b>${esc(row.system)}</b>${row.visited ? ` <small class="xn-dim">visited</small>` : ""}`, sort: (row) => row.system},
  {id: "dist", label: "DIST", cell: (row) => `<span title="${row.from_you !== null && row.from_you !== undefined ? `${fixed(row.from_you, 1)} ly from you` : ""}">${fixed(row.distance, 1)}</span>`, sort: (row) => row.distance, cls: "xt-num"},
  {id: "matches", label: "MATCHES", cell: matchesCell, sort: (row) => (row.matches || []).length, firstDir: "desc"},
  {id: "act", label: "", cell: (row) => `<span class="xn-acts"><button type="button" data-xs-act="open" data-name="${esc(row.system)}" title="Open its bodies">⌕</button><button type="button" data-xs-act="copy" data-name="${esc(row.system)}" title="Copy">⧉</button><button type="button" data-xs-act="target" data-name="${esc(row.system)}" title="Copy and open the galaxy map">🎯</button><button type="button" data-xs-act="route" data-name="${esc(row.system)}" title="Add to your waypoint route">＋</button></span>`},
];

function readForm() {
  const root = st.root;
  const f = form();
  const ticks = {};
  for (const box of root.querySelectorAll("[data-xs-tick]:checked")) (ticks[box.dataset.xsTick] ||= []).push(box.value);
  const field = (name) => root.querySelector(`[data-xs-field="${name}"]`)?.value;
  const next = {...f, ticks, radius: Number(field("radius")) || 100, at_least: Number(field("at_least")) || 1,
    min_signals: Number(field("min_signals")) || 1, centre: field("centre") || "here", name: field("name") || "",
    arrival_only: Boolean(root.querySelector('[data-xs-flag="arrival_only"]')?.checked),
    two_hotspots: Boolean(root.querySelector('[data-xs-flag="two_hotspots"]')?.checked)};
  setPref(st.profile, "search.form", next);
  return next;
}

function bind(root) {
  if (root.dataset.xsBound) return;
  root.dataset.xsBound = "1";
  root.addEventListener("change", (event) => {
    if (event.target.matches("[data-xs-pick]")) {
      if (event.target.checked) st.ticked.add(event.target.value); else st.ticked.delete(event.target.value);
      renderSweep();
      return;
    }
    if (event.target.matches('[data-xs-field="centre"]')) {
      const name = root.querySelector('[data-xs-field="name"]');
      if (name) name.hidden = event.target.value !== "system";
    }
    if (event.target.closest(".xs-form")) readForm();
  });
  root.addEventListener("click", async (event) => {
    const ui = st.ui;
    const source = event.target.closest("[data-xs-source]");
    if (source) {
      setPref(st.profile, "search.form", {...readForm(), source: source.dataset.xsSource});
      drawForm(true);
      return;
    }
    if (event.target.closest("[data-xs-run]")) {
      const f = readForm();
      ui.command("workspace", {page: "explore", operation: "search_run", ...f});
      return;
    }
    if (event.target.closest("[data-xs-clear]")) {
      st.ticked.clear();
      ui.command("workspace", {page: "explore", operation: "search_clear"});
      return;
    }
    if (event.target.closest("[data-xs-find-go]")) {
      const name = root.querySelector("[data-xs-find]")?.value.trim();
      if (name) ui.command("workspace", {page: "explore", operation: "search_find", name});
      return;
    }
    if (event.target.closest("[data-xs-sweep]")) {
      const systems = [...st.ticked];
      if (!systems.length) return;
      await ui.command("workspace", {page: "explore", operation: "plot_route", plotter: "sweep", systems});
      ui.setView?.("route");
      return;
    }
    const act = event.target.closest("[data-xs-act]");
    if (act) {
      const name = act.dataset.name;
      const row = (st.data?.results || []).find((item) => item.system === name) || st.data?.found;
      if (act.dataset.xsAct === "open") {
        ui.openSystem?.(name, row?.id64 || "");
        return;
      }
      const op = {copy: "copy_system", target: "target_system", route: "add_route"}[act.dataset.xsAct];
      if (await ui.command("workspace", {page: "explore", operation: op, name, coords: row?.coords || null})) {
        ui.showToast?.({copy: `${name} copied`, target: `${name} copied: paste it into the galaxy map's search`, route: `${name} added to your route`}[act.dataset.xsAct]);
      }
    }
  });
  root.addEventListener("keydown", (event) => {
    if (event.target.matches("[data-xs-find]") && event.key === "Enter") root.querySelector("[data-xs-find-go]")?.click();
  });
}

function drawForm(force = false) {
  const slot = st.root.querySelector("[data-xs-form]");
  if (!slot || !st.data) return;
  if (!force && slot.contains(document.activeElement)) return;
  const html = formMarkup(st.data.options || {});
  if (slot._html !== html || force) {
    slot._html = html;
    slot.innerHTML = html;
  }
}

function renderSweep() {
  const bar = st.root?.querySelector("[data-xs-sweepbar]");
  if (!bar) return;
  bar.innerHTML = st.ticked.size ? `<span>${st.ticked.size} ticked</span><button type="button" class="primary" data-xs-sweep>PLOT A SWEEP THROUGH THEM</button>` : "";
}

function foundMarkup(found) {
  if (!found) return "";
  const bits = [found.source === "yours" ? "in your records" : "on Spansh",
    found.visits ? `${found.visits.count} visit${found.visits.count === 1 ? "" : "s"}, last ${esc(String(found.visits.last).slice(0, 10))}` : "never visited",
    found.bodies ? `${found.bodies} bodies` : "", found.firsts ? `${found.firsts} first discoveries yours` : ""].filter(Boolean);
  return `<div class="xs-found"><b>${esc(found.name)}</b><span>${bits.join(" · ")}</span><span class="xn-acts"><button type="button" data-xs-act="open" data-name="${esc(found.name)}">OPEN</button><button type="button" data-xs-act="copy" data-name="${esc(found.name)}">COPY</button><button type="button" data-xs-act="target" data-name="${esc(found.name)}">🎯</button></span></div>`;
}

function draw() {
  if (!st.root || !st.data) return;
  drawForm();
  const status = st.root.querySelector("[data-xs-status]");
  if (status) status.textContent = st.data.detail || "";
  const found = st.root.querySelector("[data-xs-found]");
  if (found) found.innerHTML = foundMarkup(st.data.found);
  renderTable(st.root.querySelector("[data-xs-table]"), {
    id: "search", profile: st.profile, columns: COLUMNS, rows: st.data.results || [], key: (row) => row.system,
    rowClass: (row) => (row.visited ? "xn-visited" : ""), sort: {col: "dist", dir: "asc"},
    empty: st.data.status === "working" ? "Searching…" : "No results yet.",
  });
  renderSweep();
}

export function renderSearch(panel, ui, rev) {
  if (!panel) return;
  st.ui = ui;
  st.profile = ui.profileKey();
  if (!panel.querySelector(".xs-shell")) {
    // What to look for down the left, what was found on the right (5.7.8 redesign).
    panel.insertAdjacentHTML("afterbegin", `<div class="xs-shell">
      <aside class="xs-side xe-card"><header class="xe-card-head"><div><small>SPANSH OR YOUR OWN SCANS</small><h3>Search</h3></div></header><div class="xs-side-body" data-xs-form></div></aside>
      <section class="xs-main xe-card"><header class="xe-card-head"><div><small>RESULTS</small><h3>Systems found</h3></div><p class="xn-status" data-xs-status></p></header>
        <div class="xs-found-slot" data-xs-found></div><div class="xs-sweepbar" data-xs-sweepbar></div><div class="xt-box xs-results" data-xt-results data-xs-table></div></section></div>`);
    st.root = panel;
    bind(panel);
    st.rev = -1;
  }
  st.root = panel;
  if (rev === st.rev || st.loading) return;
  st.rev = rev;
  st.loading = true;
  fetchData(ui, "explore-search").then((data) => {
    st.data = data;
    draw();
  }).catch(() => {}).finally(() => { st.loading = false; });
}
