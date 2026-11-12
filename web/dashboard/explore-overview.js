/** OVERVIEW (5.7.8): Nearby and the system you're looking at, side by side,
 * each scrolling in its own box while the page itself stays put. The divider
 * drags, the panes swap or stack, and the choice is kept per commander.
 * After ED-Outrider's Overview (github.com/weslocke/ED-Outrider, GPLv3). */

import {credits, dual, esc, fetchData, fixed, pref, renderTable, setPref, starPip, valueBar, visibleRows} from "./explore-table.js";
import {loadSystem, renderBodies} from "./explore-bodies.js";

const MASS_CODES = ["all", "a", "b", "c", "d", "e", "f", "g", "h"];
const CENTRES = [["here", "You"], ["destination", "Destination"], ["next_stop", "Next stop"], ["carrier", "Carrier"], ["lock", "Locked"], ["system", "A system…"]];
const BOXEL = /^(.+ [A-Z][A-Z]-[A-Z] ([a-h])(?:\d+-)?)(\d+)$/;
const NOTABLE = {
  elw: ["ELW", "Earth-like world"], ww: ["WW", "Water world"], aw: ["AW", "Ammonia world"],
  tf: ["T", "terraformable"],
};

let state = {ui: null, root: null, profile: "", nearby: null, rev: -1, viewing: null, system: null, loading: false, polling: 0};
// The best system on the list, for the value bars.
let topValue = 0;

function filters() {
  return pref(state.profile, "nearby.filters", {visited: false, explored: false, one: false, noscan: false, mass: "all", mode: "standard"});
}

function setFilters(next) {
  setPref(state.profile, "nearby.filters", {...filters(), ...next});
}

function layout() {
  return pref(state.profile, "overview.layout.v2", {width: 55, swap: true, stack: false});
}

function statusPill(row) {
  if (row.status === "none") return `<span class="xn-pill xn-none" title="known to exist, but nobody has reported scanning it">${dual("no scan data", "—")}</span>`;
  if (row.status === "full") return `<span class="xn-pill xn-full">${dual("fully scanned", "✓")}</span>`;
  const pct = row.body_count ? Math.floor(100 * row.known / row.body_count) : null;
  return `<span class="xn-pill xn-part" title="${row.body_count ? `${row.known} of ${row.body_count} bodies known` : "body count unknown (no FSS honk reported)"}">${dual(pct !== null ? `${pct}% scanned` : "partly scanned", pct !== null ? `${pct}%` : "part")}</span>`;
}

function statusCell(row) {
  return [statusPill(row),
    row.mapped ? `<span class="xn-pill xn-mapped" title="bodies you mapped here">${dual(`${row.mapped} mapped`, `🗺${row.mapped}`)}</span>` : "",
    row.pre_odyssey ? `<span class="xn-pill xn-old" title="Spansh's newest report is from ${esc(row.pre_odyssey)}, before Odyssey: fully scanned may still hide biology and first footfalls">${dual("pre-Odyssey", "⏳")}</span>` : "",
    row.needs_permit ? `<span class="xn-pill xn-permit" title="needs a permit">${dual("permit", "🔒")}</span>` : "",
  ].join("");
}

function nameCell(row) {
  const marks = [row.first_found ? `<span title="you discovered something here first">⚑</span>` : "",
    row.footfall ? `<span title="your first footfall">👣</span>` : ""].join("");
  return `<b>${esc(row.name)}</b>${row.here ? ` <em class="xn-here">HERE</em>` : ""}${marks ? ` <span class="xn-marks">${marks}</span>` : ""}`;
}

function actionsCell(row) {
  const name = esc(row.name);
  return `<span class="xn-acts"><button type="button" data-xn-act="bookmark" data-name="${name}" aria-pressed="${row.bookmarked}" title="Bookmark">${row.bookmarked ? "★" : "☆"}</button><button type="button" data-xn-act="copy" data-name="${name}" title="Copy the name">⧉</button><button type="button" data-xn-act="target" data-name="${name}" title="Copy it and open the galaxy map (paste it into the search)">🎯</button><button type="button" data-xn-act="route" data-name="${name}" title="Add it to your waypoint route">＋</button></span>`;
}

function starCell(row) {
  if (!row.main_star) return `<span class="xn-dim">?</span>`;
  return `${starPip(row.main_star)}<span title="${esc(row.main_star_name)}">${esc(row.main_star)}</span>${row.scoop ? ` <span class="xn-scoop" title="scoopable">⛽</span>` : ` <span class="xn-noscoop" title="not scoopable">✕</span>`}`;
}

function bodiesCell(row) {
  if (!row.known) return `<span class="xn-dim">—</span>`;
  const bit = (n, mark, title) => (n ? `<span title="${title}">${mark}${n}</span>` : "");
  return [bit(row.stars, "★", "stars"), bit(row.planets, "○", "planets"),
    row.ringed === null ? "" : bit(row.ringed, "◎", "ringed planets"),
    row.landable === null ? "" : bit(row.landable, "⬇", "landable")].filter(Boolean).join(" ");
}

function codexPill(row) {
  const fresh = row.codex_new || [];
  if (!fresh.length) return "";
  const anywhere = fresh.some((item) => item.state === "new");
  return `<span class="xn-pill xn-codex" title="new to your Codex${anywhere ? "" : " in this region"}: ${esc(fresh.map((item) => `${item.name} (${item.body})${item.state === "new" ? ", anywhere" : ""}`).join("; "))}">${anywhere ? "✪" : "✦"}${fresh.length > 1 ? fresh.length : ""}</span>`;
}

function notableCell(row) {
  return codexPill(row) + (row.notable || []).map((note) => {
    if (note.kind === "bio") return `<span class="xn-pill xn-bio" title="biology on ${note.bodies} bod${note.bodies === 1 ? "y" : "ies"}, worth up to ${credits(note.value)}">🧬≤${credits(note.value)}</span>`;
    if (note.kind === "unusual") return `<span class="xn-pill xn-odd" title="something unusual: ${esc(note.what.join(", "))}">✧ ${esc(note.what.join(" "))}</span>`;
    const [label, title] = NOTABLE[note.kind] || [note.kind, note.kind];
    return `<span class="xn-pill xn-${esc(note.kind)}" title="${note.n} ${title}">${label}${note.n > 1 ? `×${note.n}` : ""}</span>`;
  }).join("");
}

function valueCell(row) {
  if (!row.value_max) return "";
  return `${row.value_now ? `<b>${credits(row.value_now)}</b> / ${credits(row.value_max)}` : credits(row.value_max)}${valueBar(row.value_max, topValue)}`;
}

const COLUMNS = [
  {id: "act", label: "", cell: actionsCell},
  {id: "name", label: "SYSTEM", cell: nameCell, sort: (row) => row.name},
  {id: "dist", label: "DIST", cell: (row) => fixed(row.distance, 2), sort: (row) => row.distance, cls: "xt-num"},
  {id: "jumps", label: "JUMPS", short: "J", cell: (row) => row.jumps ?? "", sort: (row) => row.jumps, cls: "xt-num", fit: 3},
  {id: "status", label: "STATUS", cell: statusCell, sort: (row) => ({full: 0, partial: 1, none: 2}[row.status])},
  {id: "star", label: "MAIN STAR", short: "★", cell: starCell, sort: (row) => row.main_star},
  {id: "bodies", label: "BODIES", cell: bodiesCell, sort: (row) => row.known, firstDir: "desc", fit: 2},
  {id: "notable", label: "NOTABLE", cell: notableCell, sort: (row) => (row.notable || []).reduce((sum, n) => sum + (n.value || 0) + (n.kind === "elw" ? 5e6 : n.kind === "ww" ? 2e6 : n.kind === "aw" ? 2e6 : 0), 0) || null, firstDir: "desc"},
  {id: "value", label: "VALUE NOW / MAX", short: "VALUE", cell: valueCell, sort: (row) => row.value_max || null, cls: "xt-num", firstDir: "desc"},
  {id: "known", label: "KNOWN", cell: (row) => (row.body_count ? `${row.known}/${row.body_count}` : row.known ? `${row.known}/?` : ""), sort: (row) => row.known, cls: "xt-num", fit: 3},
];

function massOf(name) {
  const match = BOXEL.exec(String(name || ""));
  return match ? match[2] : "";
}

function filtered(rows) {
  const f = filters();
  return rows.filter((row) => !(f.visited && row.visited) && !(f.explored && row.status === "full")
    && !(f.one && row.jumps > 1) && !(f.noscan && row.status !== "none") && (f.mass === "all" || massOf(row.name) === f.mass));
}

/** Boxel mode: the systems grouped by their boxel, and the numbers not seen yet to try next. */
function boxelMarkup(rows) {
  const groups = new Map();
  for (const row of rows) {
    const match = BOXEL.exec(row.name);
    if (!match) continue;
    const prefix = match[1];
    if (!groups.has(prefix)) groups.set(prefix, {prefix, mass: match[2], numbers: [], visited: 0, distance: row.distance});
    const group = groups.get(prefix);
    group.numbers.push(Number(match[3]));
    group.visited += row.visited ? 1 : 0;
    group.distance = Math.min(group.distance, row.distance);
  }
  const list = [...groups.values()].sort((a, b) => a.distance - b.distance);
  if (!list.length) return `<p class="workspace-empty">No procedurally named systems in range.</p>`;
  return `<div class="xn-boxels">${list.map((group) => {
    const known = new Set(group.numbers);
    const top = Math.max(...group.numbers);
    const missing = [];
    for (let n = 0; n <= top + 5 && missing.length < 6; n += 1) if (!known.has(n)) missing.push(n);
    const label = group.prefix.endsWith("-") ? group.prefix.slice(0, -1) : group.prefix;
    return `<article class="xn-boxel"><header><b>${esc(label)}</b><small>mass ${esc(group.mass)} · ${fixed(group.distance, 1)} ly · ${group.numbers.length} known, ${group.visited} visited</small></header>
      <div class="xn-boxel-try">${missing.map((n) => `<button type="button" data-xn-act="copy" data-name="${esc(group.prefix + n)}" title="Not on Spansh: copy it and try the galaxy map">${esc(group.prefix + n)}</button>`).join("") || "<span class='xn-dim'>every number up to the highest is known</span>"}</div></article>`;
  }).join("")}</div><p class="xn-note">A boxel's systems are numbered from 0 with no gaps. A number nobody has reported is a system nobody with an uploader has visited: copy it and search for it in the galaxy map.</p>`;
}

function controlsMarkup(data) {
  const f = filters();
  const centre = data?.centre || {};
  const kind = centre.kind || "here";
  return `<div class="xn-bar">
      <span class="xn-modes" role="group" aria-label="List or boxels"><button type="button" data-xn-mode="standard" aria-pressed="${f.mode !== "boxel"}">STANDARD</button><button type="button" data-xn-mode="boxel" aria-pressed="${f.mode === "boxel"}">BOXEL</button></span>
      <label class="xn-centre">FOCUS<select data-xn-centre>${CENTRES.map(([id, label]) => `<option value="${id}" ${id === kind ? "selected" : ""}>${label}</option>`).join("")}</select></label>
      <input class="xn-system" data-xn-system placeholder="SYSTEM NAME" value="${esc(kind === "system" || kind === "lock" ? centre.name || "" : "")}" ${kind === "system" ? "" : "hidden"}>
      <label>RADIUS<select data-xn-radius>${(data?.radii || [20, 25, 30, 40, 50]).map((r) => `<option value="${r}" ${r === data?.radius ? "selected" : ""}>${r} ly</option>`).join("")}</select></label>
      <button type="button" data-xn-refresh title="Ask Spansh again">↻ REFRESH</button>
      <button type="button" data-xn-lock title="Lock the list on the system you're in">LOCK HERE</button>
      <span class="xn-filters">
        <label title="Hide systems you've been to"><input type="checkbox" data-xn-filter="visited" ${f.visited ? "checked" : ""}> hide visited</label>
        <label title="Hide systems whose every body is known"><input type="checkbox" data-xn-filter="explored" ${f.explored ? "checked" : ""}> hide fully scanned</label>
        <label><input type="checkbox" data-xn-filter="one" ${f.one ? "checked" : ""}> 1 jump</label>
        <label title="Only systems nobody has reported scanning"><input type="checkbox" data-xn-filter="noscan" ${f.noscan ? "checked" : ""}> no scan data</label>
        <label>MASS<select data-xn-mass>${MASS_CODES.map((m) => `<option value="${m}" ${m === f.mass ? "selected" : ""}>${m}</option>`).join("")}</select></label>
      </span>
      <button type="button" data-xn-copy-visible title="Copy every system on the list, in this order">COPY VISIBLE</button>
      <span class="xn-layout"><button type="button" data-ov-swap title="Swap sides">⇄</button><button type="button" data-ov-stack title="Stack or side by side">${layout().stack ? "▥" : "▤"}</button></span>
    </div>`;
}

function statusLine(data) {
  if (!data) return "Loading…";
  const bits = [data.detail || ""];
  if (data.count) bits.push(`${data.not_visited} of ${data.count} not visited`);
  if (data.dumps_left) bits.push(`fetching ${data.dumps_left} systems' details…`);
  return bits.filter(Boolean).join(" · ");
}

function applyLayout() {
  const split = state.root?.querySelector(".ov-split");
  if (!split) return;
  const l = layout();
  split.style.setProperty("--ovw", `${Math.max(20, Math.min(70, Number(l.width) || 40))}%`);
  split.classList.toggle("swap", Boolean(l.swap));
  split.classList.toggle("stack", Boolean(l.stack));
}

function skeleton() {
  return `<div class="ov-split">
      <section class="ov-pane ov-near xe-card" aria-label="Nearby systems">
        <header class="xe-card-head"><div><small>WITHIN REACH · SPANSH</small><h3>Nearby systems</h3></div><p class="xn-status" data-xn-status></p></header>
        <details class="ov-ahead" data-ov-ahead open><summary>ROUTE AHEAD <span data-ov-ahead-label></span></summary><div class="xt-box" data-ov-ahead-table></div></details>
        <div data-xn-controls></div>
        <div class="xt-box" data-xn-table></div>
      </section>
      <div class="ov-divider" role="separator" aria-orientation="vertical" tabindex="0" title="Drag to resize"></div>
      <section class="ov-pane ov-here xe-card" aria-label="The system you're viewing">
        <header class="xb-head" data-xb-head></header>
        <div class="xt-box" data-xb-table></div>
        <footer class="xb-legend" data-xb-legend></footer>
      </section>
    </div>`;
}

function bindDivider(split) {
  const divider = split.querySelector(".ov-divider");
  if (!divider || divider.dataset.bound) return;
  divider.dataset.bound = "1";
  divider.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    divider.setPointerCapture(event.pointerId);
    const move = (moved) => {
      const box = split.getBoundingClientRect();
      const l = layout();
      const vertical = l.stack;
      const share = vertical ? (moved.clientY - box.top) / box.height : (moved.clientX - box.left) / box.width;
      // --ovw is the system pane's share.
      const system = l.swap ? share : 1 - share;
      const width = Math.round(Math.max(20, Math.min(70, system * 100)));
      setPref(state.profile, "overview.layout.v2", {...l, width});
      applyLayout();
    };
    const up = () => {
      divider.removeEventListener("pointermove", move);
      divider.removeEventListener("pointerup", up);
    };
    divider.addEventListener("pointermove", move);
    divider.addEventListener("pointerup", up);
  });
  divider.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
    const l = layout();
    const step = event.key === "ArrowLeft" || event.key === "ArrowUp" ? 2 : -2;
    setPref(state.profile, "overview.layout.v2", {...l, width: Math.max(20, Math.min(70, l.width + (l.swap ? -step : step)))});
    applyLayout();
  });
}

function bind(root) {
  if (root.dataset.ovBound) return;
  root.dataset.ovBound = "1";
  root.addEventListener("change", (event) => {
    const target = event.target;
    if (target.matches("[data-xn-filter]")) {
      setFilters({[target.dataset.xnFilter]: target.checked});
      renderNearby();
    } else if (target.matches("[data-xn-mass]")) {
      setFilters({mass: target.value});
      renderNearby();
    } else if (target.matches("[data-xn-centre]")) {
      const kind = target.value;
      const input = root.querySelector("[data-xn-system]");
      if (input) input.hidden = kind !== "system";
      if (kind === "system") {
        input?.focus();
        return;
      }
      state.ui.command("workspace", {page: "explore", operation: "nearby_refresh", centre: kind});
    } else if (target.matches("[data-xn-radius]")) {
      state.ui.command("workspace", {page: "explore", operation: "nearby_refresh", radius: Number(target.value)});
    }
  });
  root.addEventListener("keydown", (event) => {
    if (event.target.matches("[data-xn-system]") && event.key === "Enter") {
      const name = event.target.value.trim();
      if (name) state.ui.command("workspace", {page: "explore", operation: "nearby_refresh", centre: "system", name});
    }
  });
  root.addEventListener("click", async (event) => {
    const ui = state.ui;
    const act = event.target.closest("[data-xn-act]");
    if (act) {
      event.stopPropagation();
      const name = act.dataset.name;
      const row = (state.nearby?.rows || []).find((item) => item.name === name);
      const op = {bookmark: "bookmark", copy: "copy_system", target: "target_system", route: "add_route"}[act.dataset.xnAct];
      const done = await ui.command("workspace", {page: "explore", operation: op, name, coords: row?.coords || null, id64: row?.id64 || ""});
      if (done) ui.showToast?.({copy: `${name} copied`, target: `${name} copied: paste it into the galaxy map's search`, route: `${name} added to your route`}[act.dataset.xnAct] || "");
      return;
    }
    const mode = event.target.closest("[data-xn-mode]");
    if (mode) {
      setFilters({mode: mode.dataset.xnMode});
      renderNearby();
      return;
    }
    if (event.target.closest("[data-xn-refresh]")) {
      const kind = root.querySelector("[data-xn-centre]")?.value || "here";
      const name = kind === "system" ? root.querySelector("[data-xn-system]")?.value.trim() : "";
      ui.command("workspace", {page: "explore", operation: "nearby_refresh", centre: kind, name});
      return;
    }
    if (event.target.closest("[data-xn-lock]")) {
      ui.command("workspace", {page: "explore", operation: "nearby_lock"});
      return;
    }
    if (event.target.closest("[data-xn-copy-visible]")) {
      const box = root.querySelector("[data-xn-table]");
      const names = visibleRows(box).map((row) => row.name);
      if (!names.length) return;
      try {
        await navigator.clipboard.writeText(names.join("\n"));
        ui.showToast?.(`${names.length} systems copied`);
      } catch (_error) {
        ui.command("workspace", {page: "explore", operation: "copy_system", name: names.join("\n")});
      }
      return;
    }
    if (event.target.closest("[data-ov-swap]")) {
      const l = layout();
      setPref(state.profile, "overview.layout.v2", {...l, swap: !l.swap});
      applyLayout();
      return;
    }
    if (event.target.closest("[data-ov-stack]")) {
      const l = layout();
      setPref(state.profile, "overview.layout.v2", {...l, stack: !l.stack});
      applyLayout();
      renderControls(true);
      return;
    }
    // A Nearby (or route-ahead) row: its bodies on the right.
    const tr = event.target.closest(".ov-near tr[data-xt-key]");
    if (tr) {
      const row = (state.nearby?.rows || []).find((item) => item.name === tr.dataset.xtKey);
      openSystem(tr.dataset.xtKey, row?.id64 || "");
    }
  });
}

function renderControls(force = false) {
  const slot = state.root?.querySelector("[data-xn-controls]");
  if (!slot) return;
  // Not while you're choosing from one of its menus or typing.
  if (!force && slot.contains(document.activeElement) && document.activeElement.matches("select, input[type=text], input:not([type])")) return;
  const html = controlsMarkup(state.nearby);
  if (slot._html !== html) {
    slot._html = html;
    slot.innerHTML = html;
  }
}

function renderNearby() {
  const root = state.root;
  if (!root) return;
  renderControls();
  const data = state.nearby;
  const status = root.querySelector("[data-xn-status]");
  if (status) status.textContent = statusLine(data);
  const box = root.querySelector("[data-xn-table]");
  const rows = filtered(data?.rows || []);
  if (filters().mode === "boxel") {
    const html = boxelMarkup(rows);
    if (box._html !== html) {
      box._html = html;
      box._xtSpec = null;
      box.innerHTML = html;
    }
    return;
  }
  box._html = null;
  topValue = Math.max(0, ...rows.map((row) => Number(row.value_max) || 0));
  renderTable(box, {
    id: "nearby", profile: state.profile, columns: COLUMNS, rows, key: (row) => row.name,
    rowClass: (row) => [row.visited ? "xn-visited" : "", row.here ? "xn-here-row" : "",
      state.viewing && state.viewing.toLowerCase() === row.name.toLowerCase() ? "xn-viewing" : ""].join(" "),
    sort: {col: "dist", dir: "asc"},
    empty: data?.status === "working" ? "Asking Spansh…" : data?.status === "failed" ? esc(data.detail) : "Nothing matches the filters.",
  });
}

async function refreshSystem() {
  if (!state.root) return;
  const name = state.viewing || state.nearby?.here || "";
  if (!name) return;
  try {
    const data = await loadSystem(state.ui, name, state.viewingId || "");
    state.system = data;
    renderBodies(state.root.querySelector(".ov-here"), data, state.ui, {profile: state.profile, id: "ov-bodies"});
    clearTimeout(state.polling);
    if (data.status === "working") state.polling = setTimeout(refreshSystem, 1500);
  } catch (_error) { /* the next revision asks again */ }
}

export function openSystem(name, id64 = "") {
  state.viewing = name;
  state.viewingId = id64 || "";
  if (id64) state.ui.command("workspace", {page: "explore", operation: "system_open", id64});
  renderNearby();
  refreshSystem();
}

const AHEAD_COLUMNS = () => [{id: "stop", label: "#", cell: (row) => row.stop, sort: (row) => row.stop, cls: "xt-num"},
  ...COLUMNS.filter((col) => col.id !== "jumps")];

async function refreshAhead() {
  const box = state.root?.querySelector("[data-ov-ahead]");
  if (!box?.open) return;
  try {
    const data = await fetchData(state.ui, "explore-ahead");
    const label = state.root.querySelector("[data-ov-ahead-label]");
    if (label) label.textContent = data.rows?.length ? `· ${data.label} · ${data.rows.length} systems${data.status === "working" ? " · asking Spansh…" : ""}` : "· none: plot one in the game or on the Route page";
    // No route: one line, not an empty table.
    box.toggleAttribute("data-empty", !data.rows?.length);
    renderTable(state.root.querySelector("[data-ov-ahead-table]"), {
      id: "ahead", profile: state.profile, columns: AHEAD_COLUMNS(), rows: data.rows || [], key: (row) => row.name,
      rowClass: (row) => (row.visited ? "xn-visited" : ""), sort: {col: "stop", dir: "asc"},
      empty: "Plot a route in the game or on the Route page.",
    });
  } catch (_error) { /* asked again on the next revision */ }
}

async function refreshNearby() {
  if (state.loading) return;
  state.loading = true;
  try {
    state.nearby = await fetchData(state.ui, "explore-nearby");
    renderNearby();
  } catch (_error) {
    /* asked again on the next revision */
  } finally {
    state.loading = false;
  }
}

/** Draw OVERVIEW into its panel; `rev` is the survey revision from the snapshot. */
export function renderOverview(panel, ui, rev, here) {
  if (!panel) return;
  state.ui = ui;
  state.profile = ui.profileKey();
  if (!panel.querySelector(".ov-split")) {
    panel.innerHTML = skeleton();
    state.root = panel;
    bind(panel);
    panel.querySelector("[data-ov-ahead]")?.addEventListener("toggle", refreshAhead);
    bindDivider(panel.querySelector(".ov-split"));
    applyLayout();
    state.rev = -1;
  }
  state.root = panel;
  // Follow you between systems unless you picked one from the list.
  if (here && state.lastHere !== here) {
    if (!state.viewing || state.viewing === state.lastHere) state.viewing = here;
    state.lastHere = here;
  }
  if (rev !== state.rev) {
    state.rev = rev;
    refreshNearby();
    refreshSystem();
    refreshAhead();
  }
}

export function resetOverview() {
  state = {ui: null, root: null, profile: "", nearby: null, rev: -1, viewing: null, system: null, loading: false, polling: 0};
}
