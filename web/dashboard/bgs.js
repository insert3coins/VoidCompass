// BGS tab (5.5.2.4): the Background Simulation from your journal, with EDSM
// for any system you look up. Overview and alerts, factions, systems (with
// influence history), conflicts, your work per tick, and the states.

const VIEWS = [
  ["overview", "OVERVIEW"], ["factions", "FACTIONS"], ["systems", "SYSTEMS"],
  ["conflicts", "CONFLICTS"], ["activity", "MY WORK"], ["states", "STATES GUIDE"],
];
// Influence chart series: a validated categorical palette (colour-blind
// separation, contrast on the deck's dark panel), assigned by faction name so
// a faction keeps its colour. Past eight, factions fold into "others".
const SERIES = ["--bgs-s1", "--bgs-s2", "--bgs-s3", "--bgs-s4", "--bgs-s5", "--bgs-s6", "--bgs-s7", "--bgs-s8"];
let chartData = null;

const n = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
const count = (value) => n(value).toLocaleString("en-GB");
const pct = (value) => value == null ? "—" : `${(n(value) * 100).toFixed(1)}%`;
const credits = (value) => {
  const v = n(value);
  const abs = Math.abs(v);
  return abs >= 1e9 ? `${(v / 1e9).toFixed(2)}B` : abs >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : abs >= 1e3 ? `${(v / 1e3).toFixed(0)}K` : `${Math.round(v)}`;
};

function ago(ts) {
  if (!ts) return "";
  const seconds = Date.now() / 1000 - n(ts);
  if (seconds < 3600) return `${Math.max(1, Math.round(seconds / 60))} min ago`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} days ago`;
}

function send(ui, operation, extra = {}) {
  return ui.command("workspace", {page: "bgs", operation, ...extra});
}

function chip(state, esc, kind = "") {
  const label = state.label || state.name;
  const trend = state.trend > 0 ? " ▲" : state.trend < 0 ? " ▼" : "";
  return `<span class="bgs-chip tone-${esc(state.tone || "muted")}${kind ? ` ${kind}` : ""}" title="${esc(state.text || "")}">${kind === "pending" ? "→ " : kind === "recovering" ? "↺ " : ""}${esc(label)}${trend}</span>`;
}

function stateChips(row, esc) {
  return [...(row.active || []).map((state) => chip(state, esc)), ...(row.pending || []).map((state) => chip(state, esc, "pending")),
    ...(row.recovering || []).map((state) => chip(state, esc, "recovering"))].join("") || `<span class="bgs-dim">No state</span>`;
}

function delta(value) {
  if (value == null) return "";
  const points = n(value) * 100;
  if (Math.abs(points) < 0.05) return `<span class="bgs-delta flat">±0.0</span>`;
  return `<span class="bgs-delta ${points > 0 ? "up" : "down"}">${points > 0 ? "▲" : "▼"} ${Math.abs(points).toFixed(1)}</span>`;
}

function star(kind, key, on, esc) {
  return `<button type="button" class="bgs-star${on ? " on" : ""}" title="${on ? "Stop tracking" : "Track"}" data-bgs-op="${kind}" data-${kind === "track_faction" ? "name" : "address"}="${esc(key)}" data-value="${on ? "" : "1"}">${on ? "★" : "☆"}</button>`;
}

// -- shared pieces -------------------------------------------------------
function factionsTable(picture, esc, tracked) {
  const rows = picture.factions.map((row) => `<tr class="${row.controlling ? "controlling" : ""}${tracked.has(row.name) ? " tracked" : ""}">
      <td class="bgs-name">${star("track_faction", row.name, tracked.has(row.name), esc)}<button type="button" class="bgs-link" data-bgs-op="faction" data-name="${esc(row.name)}">${esc(row.name)}</button>
        ${row.controlling ? `<span class="bgs-tag">CONTROLS</span>` : ""}${row.player ? `<span class="bgs-tag dim">PLAYER</span>` : ""}${row.squadron ? `<span class="bgs-tag">YOUR SQUADRON</span>` : ""}${row.new ? `<span class="bgs-tag">NEW</span>` : ""}
        <small>${esc([row.allegiance, row.government].filter(Boolean).join(" · "))}</small></td>
      <td class="bgs-inf"><span class="bgs-bar"><i style="--fill:${Math.min(100, n(row.influence) * 100).toFixed(1)}%"></i></span><b>${pct(row.influence)}</b>${delta(row.delta)}</td>
      <td class="bgs-states">${stateChips(row, esc)}</td>
      <td class="bgs-small">${esc(row.happiness || "")}${row.reputation != null ? `<small>REP ${n(row.reputation).toFixed(0)}</small>` : ""}</td></tr>`).join("");
  return `<div class="bgs-table-wrap"><table class="bgs-table"><thead><tr><th>FACTION</th><th>INFLUENCE</th><th>STATES</th><th>MOOD</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function conflictCard(conflict, esc, showSystem = false) {
  const [a, b] = conflict.sides || [];
  const kind = conflict.type === "civilwar" ? "CIVIL WAR" : String(conflict.type || "").toUpperCase();
  const side = (row) => row ? `<div class="bgs-side${row.tracked ? " tracked" : ""}"><button type="button" class="bgs-link" data-bgs-op="faction" data-name="${esc(row.name)}">${esc(row.name)}</button>
      <b>${n(row.won_days)}</b><small>${row.stake ? `Stake: ${esc(row.stake)}` : "No stake"}${row.influence != null ? ` · ${pct(row.influence)}` : ""}</small></div>` : "";
  return `<article class="bgs-conflict ${esc(conflict.status)}"><header><span class="bgs-tag ${conflict.type === "election" ? "" : "danger"}">${esc(kind)}</span><b>${esc(String(conflict.status || "").toUpperCase())}</b>
      ${showSystem ? `<button type="button" class="bgs-link" data-bgs-op="system" data-address="${esc(conflict.system_address)}">${esc(conflict.system)}</button><small>${ago(conflict.ts)}</small>` : ""}</header>
    <div class="bgs-sides">${side(a)}<span class="bgs-vs">DAYS WON</span>${side(b)}</div></article>`;
}

function systemFacts(picture, esc) {
  const facts = [["POPULATION", picture.population ? count(picture.population) : ""], ["ALLEGIANCE", picture.allegiance],
    ["GOVERNMENT", picture.government], ["ECONOMY", [picture.economy, picture.second_economy].filter(Boolean).join(" / ")],
    ["SECURITY", picture.security], ["POWER", [picture.controlling_power, picture.power_state].filter(Boolean).join(" · ")]]
    .filter(([, value]) => value);
  return `<dl class="bgs-facts">${facts.map(([label, value]) => `<div><dt>${label}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>`;
}

function activityRows(rows, esc) {
  if (!rows || !rows.length) return `<p class="bgs-dim">None yet.</p>`;
  return `<ul class="bgs-kinds">${rows.map((row) => `<li class="${row.bad ? "bad" : ""}"><span>${esc(row.label)}</span><b>${row.credits ? `${credits(row.amount)} CR` : row.kind.startsWith("inf") ? `${n(row.amount) > 0 ? "+" : ""}${count(row.amount)} INF` : count(row.count)}</b></li>`).join("")}</ul>`;
}

// -- the influence chart -------------------------------------------------
function chartRanges(days) {
  return [[1, "24H"], [7, "7D"], [30, "30D"], [90, "90D"], [365, "1Y"], [3650, "ALL"]]
    .map(([value, label]) => `<button type="button" class="${days === value ? "active" : ""}" data-bgs-op="chart_days" data-days="${value}">${label}</button>`).join("");
}

function chart(history, esc, days) {
  if (!history || !history.length || !history.some((series) => series.points.filter((p) => p.influence != null).length > 1)) {
    // Keep the range buttons, so a short range with no data can be left.
    return `<div class="bgs-chart-head"><span>INFLUENCE OVER TIME</span><div class="bgs-ranges">${chartRanges(days)}</div></div>
      <p class="bgs-dim">${days === 1 ? "No influence changes recorded in the last 24 hours: try a longer range, or refresh from EDSM." : "Not enough history to chart yet: visit again after a tick, or refresh from EDSM."}</p>`;
  }
  const names = history.map((series) => series.faction).sort((a, b) => a.localeCompare(b));
  const colour = new Map(names.map((name, index) => [name, index < SERIES.length ? `var(${SERIES[index]})` : "var(--dim)"]));
  const all = history.flatMap((series) => series.points.filter((p) => p.influence != null));
  const t0 = Math.min(...all.map((p) => p.ts)), t1 = Math.max(...all.map((p) => p.ts));
  const top = Math.min(1, Math.ceil(Math.max(...all.map((p) => p.influence)) * 10 + 0.5) / 10);
  const W = 760, H = 230, L = 40, R = 150, T = 10, B = 26;
  const x = (ts) => L + (t1 > t0 ? (ts - t0) / (t1 - t0) : 0.5) * (W - L - R);
  const y = (v) => T + (1 - v / top) * (H - T - B);
  const grid = [];
  for (let v = 0; v <= top + 1e-9; v += top > 0.5 ? 0.2 : 0.1) {
    grid.push(`<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text class="axis" x="${L - 6}" y="${(y(v) + 3).toFixed(1)}" text-anchor="end">${Math.round(v * 100)}%</text>`);
  }
  const span = t1 - t0;
  const xticks = [0, 0.25, 0.5, 0.75, 1].map((f) => t0 + f * span).map((ts) => {
    const date = new Date(ts * 1000);
    const label = span > 86400 * 2 ? date.toISOString().slice(5, 10) : date.toISOString().slice(11, 16);
    return `<text class="axis" x="${x(ts).toFixed(1)}" y="${H - 8}" text-anchor="middle">${label}</text>`;
  });
  // A line breaks where EDSM says the faction was not in the system.
  const lines = history.flatMap((series) => {
    const segments = [[]];
    series.points.forEach((p) => {
      if (p.influence == null) {
        if (segments[segments.length - 1].length) segments.push([]);
        return;
      }
      segments[segments.length - 1].push(`${x(p.ts).toFixed(1)},${y(p.influence).toFixed(1)}`);
    });
    return segments.filter((segment) => segment.length).map((segment) => segment.length > 1
      ? `<polyline class="series" style="stroke:${colour.get(series.faction)}" points="${segment.join(" ")}"/>`
      : `<circle class="dot" cx="${segment[0].split(",")[0]}" cy="${segment[0].split(",")[1]}" r="2.5" style="fill:${colour.get(series.faction)}"/>`);
  });
  // Direct labels at the line ends for the top four (by last value).
  const labelled = history.filter((series) => series.points[series.points.length - 1].influence != null).slice(0, 4).map((series) => {
    const last = series.points[series.points.length - 1];
    return {name: series.faction, y: y(last.influence), x: x(last.ts)};
  }).sort((a, b) => a.y - b.y);
  for (let i = 1; i < labelled.length; i += 1) labelled[i].y = Math.max(labelled[i].y, labelled[i - 1].y + 12);
  const ends = labelled.map((item) => `<circle class="end" cx="${item.x.toFixed(1)}" cy="${y(history.find((s) => s.faction === item.name).points.slice(-1)[0].influence).toFixed(1)}" r="3" style="fill:${colour.get(item.name)}"/>
    <text class="end-label" x="${(W - R + 8).toFixed(1)}" y="${(item.y + 3).toFixed(1)}">${esc(item.name.length > 22 ? `${item.name.slice(0, 21)}…` : item.name)}</text>`);
  chartData = {history, x, y, t0, t1, L, R, W, H, T, B, colour: Object.fromEntries(colour)};
  const legend = names.map((name) => `<li><i style="background:${colour.get(name)}"></i>${esc(name)}</li>`).join("");
  const ranges = chartRanges(days);
  return `<div class="bgs-chart-head"><span>INFLUENCE OVER TIME</span><div class="bgs-ranges">${ranges}</div></div>
    <div class="bgs-chart-box"><svg class="bgs-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Influence of each faction over time">${grid.join("")}${xticks.join("")}${lines.join("")}${ends.join("")}
      <line class="crosshair" x1="0" x2="0" y1="${T}" y2="${H - B}" hidden/><rect class="hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}"/></svg>
      <div class="bgs-tooltip" hidden></div></div>
    <ul class="bgs-legend">${legend}</ul>`;
}

function bindChart(root) {
  const svg = root.querySelector(".bgs-chart");
  const tip = root.querySelector(".bgs-tooltip");
  if (!svg || !tip || !chartData) return;
  const hair = svg.querySelector(".crosshair");
  svg.addEventListener("mousemove", (event) => {
    const box = svg.getBoundingClientRect();
    const sx = (event.clientX - box.left) / box.width * chartData.W;
    const {t0, t1, L, R, W} = chartData;
    const ts = t0 + Math.max(0, Math.min(1, (sx - L) / (W - L - R))) * (t1 - t0);
    const rows = chartData.history.map((series) => {
      let best = null;
      for (const point of series.points) {
        if (point.ts <= ts + 1 && (!best || point.ts > best.ts)) best = point;
      }
      return best && best.influence != null ? {name: series.faction, point: best} : null;
    }).filter(Boolean).sort((a, b) => b.point.influence - a.point.influence);
    if (!rows.length) return;
    const at = Math.max(...rows.map((row) => row.point.ts));
    hair.setAttribute("x1", chartData.x(at));
    hair.setAttribute("x2", chartData.x(at));
    hair.hidden = false;
    tip.hidden = false;
    tip.replaceChildren();
    const head = document.createElement("b");
    head.textContent = new Date(at * 1000).toISOString().slice(0, 16).replace("T", " ") + " UTC";
    tip.appendChild(head);
    for (const row of rows) {
      const line = document.createElement("span");
      const swatch = document.createElement("i");
      swatch.style.background = chartData.colour[row.name];
      line.append(swatch, `${row.name}  ${(row.point.influence * 100).toFixed(1)}%${row.point.state && row.point.state !== "None" ? ` · ${row.point.state}` : ""}`);
      tip.appendChild(line);
    }
    const left = (chartData.x(at) / chartData.W) * box.width;
    tip.style.left = `${Math.min(box.width - tip.offsetWidth - 4, Math.max(4, left + 12))}px`;
  });
  svg.addEventListener("mouseleave", () => { hair.hidden = true; tip.hidden = true; });
}

// -- views ---------------------------------------------------------------
function overview(data, ui, tracked) {
  const esc = ui.escapeHtml;
  const current = data.current;
  const alerts = (data.alerts || []).map((row) => `<li class="${esc(row.level)}"><span class="bgs-level">${row.level === "danger" ? "▲ RISK" : row.level === "warn" ? "! WATCH" : row.level === "good" ? "✓ GAIN" : "· NOTE"}</span>
      <div><b>${esc(row.faction)}</b> in <button type="button" class="bgs-link" data-bgs-op="system" data-address="${esc(row.system_address)}">${esc(row.system)}</button><span>${esc(row.text)}</span></div><small>${ago(row.ts)}</small></li>`).join("");
  const trackedCards = (data.tracked || []).map((row) => `<button type="button" class="bgs-card" data-bgs-op="faction" data-name="${esc(row.name)}">
      <b>${esc(row.name)}</b><span>${row.systems} systems · controls ${row.controlled}</span>
      <small>${row.danger ? `<em class="danger">${row.danger} at risk</em>` : ""}${row.warn ? `<em class="warn">${row.warn} to watch</em>` : ""}${!row.danger && !row.warn ? "All steady" : ""}</small></button>`).join("");
  const work = data.this_tick;
  return `<div class="bgs-grid">
    <section class="bgs-panel wide">${current ? `<header class="bgs-head"><div><p>YOU ARE IN</p><h3><button type="button" class="bgs-link" data-bgs-op="system" data-address="${esc(current.system_address)}">${esc(current.system)}</button></h3>
        <span>Controlled by <b>${esc(current.controlling)}</b>${current.control_changed ? ` (was ${esc(current.previous_controlling)})` : ""} · seen ${ago(current.ts)}${current.since ? ` · change since ${new Date(current.since * 1000).toISOString().slice(0, 10)}` : ""}</span></div>
        ${star("track_system", current.system_address, data.tracked_systems.includes(String(current.system_address)), esc)}</header>
        ${systemFacts(current, esc)}${factionsTable(current, esc, tracked)}${(current.conflicts || []).filter((c) => c.status !== "").map((c) => conflictCard(c, esc)).join("")}`
      : `<div class="bgs-empty"><b>NO FACTIONS HERE</b><span>The system you are in has no factions (or you have not arrived anywhere yet this session).</span></div>`}</section>
    <section class="bgs-panel"><h4>ALERTS FOR WHAT YOU TRACK</h4>${alerts ? `<ul class="bgs-alerts">${alerts}</ul>` : `<p class="bgs-dim">${tracked.size ? "Nothing needs attention." : "Track a faction (☆) to watch its influence, conflicts and states."}</p>`}</section>
    <section class="bgs-panel"><h4>TRACKED FACTIONS</h4>${trackedCards ? `<div class="bgs-cards">${trackedCards}</div>` : `<p class="bgs-dim">None yet: press ☆ beside a faction.</p>`}
      <h4>THIS TICK'S WORK</h4>${work && work.systems.length ? `<ul class="bgs-kinds">${work.systems.map((system) => `<li><span>${esc(system.system)}</span><b>${system.factions.length} faction${system.factions.length === 1 ? "" : "s"}</b></li>`).join("")}</ul>
        <div class="bgs-actions"><button type="button" data-bgs-op="view" data-view="activity">DETAILS</button><button type="button" data-bgs-op="copy_report">COPY REPORT</button></div>` : `<p class="bgs-dim">No BGS work since the tick.</p>`}</section>
  </div>`;
}

function factionsView(data, ui, tracked) {
  const esc = ui.escapeHtml;
  const list = data.factions || {rows: [], total: 0};
  const rows = list.rows.map((row) => `<li class="${data.faction?.name === row.name ? "selected" : ""}">${star("track_faction", row.name, row.tracked, esc)}
      <button type="button" class="bgs-row-main" data-bgs-op="faction" data-name="${esc(row.name)}"><b>${esc(row.name)}</b><small>${row.systems} system${row.systems === 1 ? "" : "s"} · controls ${row.controlled} · best ${pct(row.best)}</small></button></li>`).join("");
  const detail = data.faction;
  let right = `<div class="bgs-empty"><b>SELECT A FACTION</b><span>${count(list.total)} factions in your record.</span></div>`;
  if (detail) {
    const systems = detail.systems.map((row) => `<tr class="${row.controlling ? "controlling" : ""}">
        <td><button type="button" class="bgs-link" data-bgs-op="system" data-address="${esc(row.system_address)}">${esc(row.system)}</button>${row.controlling ? `<span class="bgs-tag">CONTROLS</span>` : ""}<small>#${row.rank || "?"} of ${row.factions} · ${row.source === "edsm" ? "EDSM " : ""}${ago(row.ts)}</small></td>
        <td class="bgs-inf"><span class="bgs-bar"><i style="--fill:${Math.min(100, n(row.influence) * 100).toFixed(1)}%"></i></span><b>${pct(row.influence)}</b>${delta(row.delta)}</td>
        <td class="bgs-states">${stateChips(row, esc)}${row.conflicts.length ? `<span class="bgs-chip tone-red">${row.conflicts.length} conflict${row.conflicts.length === 1 ? "" : "s"}</span>` : ""}</td></tr>`).join("");
    const alerts = (detail.alerts || []).map((row) => `<li class="${esc(row.level)}"><span class="bgs-level">${row.level === "danger" ? "▲ RISK" : row.level === "warn" ? "! WATCH" : "· NOTE"}</span><div><b>${esc(row.system)}</b><span>${esc(row.text)}</span></div></li>`).join("");
    right = `<header class="bgs-head"><div><p>${esc([detail.allegiance, detail.government].filter(Boolean).join(" · ").toUpperCase())}${detail.player ? " · PLAYER FACTION" : ""}</p><h3>${esc(detail.name)}</h3>
        <span>${detail.systems.length} systems in your record · controls ${detail.controlled}${detail.reputation != null ? ` · your reputation ${n(detail.reputation).toFixed(0)}` : ""}</span></div>
        <div class="bgs-actions">${star("track_faction", detail.name, detail.tracked, esc)}<button type="button" data-bgs-op="open" data-kind="inara_faction" data-name="${esc(detail.name)}">INARA</button></div></header>
      ${alerts ? `<ul class="bgs-alerts">${alerts}</ul>` : ""}
      <div class="bgs-table-wrap"><table class="bgs-table"><thead><tr><th>SYSTEM</th><th>INFLUENCE</th><th>STATES</th></tr></thead><tbody>${systems}</tbody></table></div>
      <div class="bgs-columns"><section><h4>YOUR WORK THIS TICK</h4>${activityRows(detail.activity_tick, esc)}</section><section><h4>YOUR WORK, ALL TIME</h4>${activityRows(detail.activity, esc)}</section></div>`;
  }
  return `<div class="bgs-split"><section class="bgs-list"><form class="bgs-search" data-bgs-form="search_factions"><input name="query" value="${esc(list.query || "")}" placeholder="Find a faction" maxlength="80"><button type="submit">FIND</button></form>
      <ul>${rows || `<li class="bgs-dim">No factions match.</li>`}</ul>${list.total > list.rows.length ? `<p class="bgs-dim">Showing ${list.rows.length} of ${count(list.total)}: search to narrow.</p>` : ""}</section>
    <section class="bgs-panel">${right}</section></div>`;
}

function systemsView(data, ui, tracked) {
  const esc = ui.escapeHtml;
  const list = data.systems || {rows: [], total: 0};
  const rows = list.rows.map((row) => `<li class="${data.system?.system_address === row.system_address ? "selected" : ""}">${star("track_system", row.system_address, row.tracked, esc)}
      <button type="button" class="bgs-row-main" data-bgs-op="system" data-address="${esc(row.system_address)}"><b>${esc(row.system)}${row.conflicts ? ` <span class="bgs-chip tone-red">${row.conflicts} conflict${row.conflicts === 1 ? "" : "s"}</span>` : ""}</b><small>${esc(row.controlling)} · ${row.factions} factions · ${row.source === "edsm" ? "EDSM " : ""}${ago(row.ts)}</small></button></li>`).join("");
  const picture = data.system;
  let right = `<div class="bgs-empty"><b>SELECT OR LOOK UP A SYSTEM</b><span>${count(list.total)} systems in your record. Type any system name above to look it up on EDSM.</span></div>`;
  if (picture) {
    right = `<header class="bgs-head"><div><p>${picture.source === "edsm" ? "FROM EDSM" : "FROM YOUR JOURNAL"} · ${ago(picture.ts).toUpperCase()}${picture.visits ? ` · ${picture.visits} VISIT${picture.visits === 1 ? "" : "S"}` : ""}</p><h3>${esc(picture.system)}</h3>
        <span>Controlled by <b>${esc(picture.controlling)}</b>${picture.control_changed ? ` (was ${esc(picture.previous_controlling)})` : ""}</span></div>
        <div class="bgs-actions">${star("track_system", picture.system_address, picture.tracked, esc)}
          <button type="button" data-bgs-op="lookup" data-system="${esc(picture.system)}" data-refresh="1"${data.lookup?.pending ? " disabled" : ""}>${data.lookup?.pending ? "REFRESHING…" : "REFRESH FROM EDSM"}</button>
          <button type="button" data-bgs-op="open" data-kind="inara_system" data-name="${esc(picture.system)}">INARA</button>
          <button type="button" data-bgs-op="open" data-kind="edsm_system" data-name="${esc(picture.system)}">EDSM</button></div></header>
      ${systemFacts(picture, esc)}${chart(picture.history, esc, picture.chart_days)}${factionsTable(picture, esc, tracked)}
      ${(picture.conflicts || []).map((c) => conflictCard(c, esc)).join("")}
      <h4>YOUR WORK HERE</h4>${activityRows(picture.activity, esc)}`;
  }
  const filters = [["", "ALL"], ["tracked", "TRACKED"], ["conflicts", "IN CONFLICT"]]
    .map(([value, label]) => `<option value="${value}"${(list.filter || "") === value ? " selected" : ""}>${label}</option>`).join("");
  return `<div class="bgs-split"><section class="bgs-list"><form class="bgs-search" data-bgs-form="search_systems"><input name="query" value="${esc(list.query || "")}" placeholder="Filter your systems" maxlength="80">
      <select name="only" data-bgs-autosubmit>${filters}</select><button type="submit">FILTER</button></form>
      <ul>${rows || `<li class="bgs-dim">No systems match.</li>`}</ul></section>
    <section class="bgs-panel">${right}</section></div>`;
}

function conflictsView(data, ui) {
  const esc = ui.escapeHtml;
  const rows = data.conflicts || [];
  if (!rows.length) return `<div class="bgs-empty"><b>NO CONFLICTS IN YOUR RECORD</b><span>Wars, civil wars and elections in systems you visit show here.</span></div>`;
  return `<p class="bgs-dim">As last seen in each system. Tracked factions' conflicts first.</p><div class="bgs-conflicts">${rows.map((row) => conflictCard(row, esc, true)).join("")}</div>`;
}

function activityView(data, ui) {
  const esc = ui.escapeHtml;
  const work = data.activity || {periods: [], detail: null};
  const periods = work.periods.map((row) => `<li class="${work.detail?.start === row.start ? "selected" : ""}"><button type="button" class="bgs-row-main" data-bgs-op="tick" data-start="${row.start}">
      <b>${esc(row.label)}${row.estimated ? ` <span class="bgs-tag dim">EST</span>` : ""}</b><small>${row.events} event${row.events === 1 ? "" : "s"}</small></button></li>`).join("");
  const detail = work.detail;
  let right = `<div class="bgs-empty"><b>NO BGS WORK YET</b><span>Missions, trade, data, bounties, bonds and conflict zones you do are counted here, per tick.</span></div>`;
  if (detail) {
    right = `<header class="bgs-head"><div><p>TICK</p><h3>${esc(detail.label)}</h3></div><div class="bgs-actions"><button type="button" data-bgs-op="copy_report">COPY DISCORD REPORT</button></div></header>
      ${detail.systems.map((system) => `<section class="bgs-work"><h4><button type="button" class="bgs-link" data-bgs-op="system" data-address="${esc(system.system_address)}">${esc(system.system)}</button></h4>
        ${system.factions.map((faction) => `<div class="bgs-work-faction"><b><button type="button" class="bgs-link" data-bgs-op="faction" data-name="${esc(faction.name)}">${esc(faction.name)}</button></b>${activityRows(faction.kinds, esc)}</div>`).join("")}</section>`).join("")}
      <details class="bgs-report"><summary>REPORT PREVIEW</summary><pre>${esc(detail.report)}</pre></details>`;
  }
  return `<div class="bgs-split"><section class="bgs-list"><ul>${periods || `<li class="bgs-dim">No ticks with work.</li>`}</ul></section><section class="bgs-panel">${right}</section></div>`;
}

function statesView(data, ui) {
  const esc = ui.escapeHtml;
  const groups = {conflict: "CONFLICT", expansion: "EXPANSION", danger: "DANGER", good: "GOOD FOR TRADE AND SECURITY", bad: "TROUBLE"};
  return Object.entries(groups).map(([group, title]) => `<section class="bgs-panel"><h4>${title}</h4><ul class="bgs-guide">${(data.states || [])
    .filter((state) => state.group === group).map((state) => `<li>${chip(state, esc)}<span>${esc(state.text)}</span></li>`).join("")}</ul></section>`).join("")
    + `<p class="bgs-dim">→ pending (coming next tick or so) · ↺ recovering · ▲▼ the game's trend.</p>`;
}

export function renderBgs(data, ui) {
  const root = ui.byId("bgs-workspace");
  if (!root) return;
  root.classList.remove("loading-panel");
  const esc = ui.escapeHtml;
  if (!data.ready) {
    root.innerHTML = `<div class="bgs-empty"><b>OPENING THE BGS RECORD</b></div>`;
    return;
  }
  const tracked = new Set(data.tracked_factions || []);
  const tick = data.tick || {};
  const status = `<div class="bgs-status"><div><b>TICK</b><span>${tick.last ? `${esc(tick.last_label)} (${ago(tick.last)})` : `${esc(tick.current_label)} <em>estimated</em>`}</span></div>
    <div><b>RECORD</b><span>${count(data.counts?.systems)} systems · ${count(data.counts?.factions)} factions${data.import?.running ? " · reading your journals…" : ""}</span></div>
    <div><b>ONLINE</b><span>${data.online ? "EDSM lookups and the tick service" : `Off <button type="button" class="bgs-link" data-page="settings" data-settings-section="integrations">turn on</button>`}</span></div>
    <form class="bgs-lookup" data-bgs-form="lookup"><input name="system" placeholder="Look up any system" maxlength="160" value="${esc(data.lookup?.pending ? data.lookup.name : "")}"><button type="submit">${data.lookup?.pending ? "LOOKING…" : "LOOK UP"}</button></form></div>`;
  const tabs = `<nav class="co-tabs bgs-tabs">${VIEWS.map(([id, label]) => `<button type="button" class="${data.view === id ? "active" : ""}" data-bgs-op="view" data-view="${id}">${label}${id === "overview" && data.alert_count ? ` <small>${data.alert_count}</small>` : ""}</button>`).join("")}</nav>`;
  const messages = `${data.error ? `<p class="co-error">${esc(data.error)}</p>` : ""}${data.lookup?.error && !data.error ? `<p class="co-error">${esc(data.lookup.error)}</p>` : ""}${data.notice ? `<p class="co-notice">${esc(data.notice)}</p>` : ""}`;
  const body = {overview, factions: factionsView, systems: systemsView, conflicts: conflictsView, activity: activityView, states: statesView}[data.view] || overview;
  chartData = null;
  root.innerHTML = `${status}${messages}${tabs}<div class="bgs-body">${body(data, ui, tracked)}</div>`;
  bindChart(root);
}

const snake = (key) => key.replace(/[A-Z]/g, (char) => `_${char.toLowerCase()}`);

export function handleBgsClick(event, ui) {
  if (!event.target.closest?.('[data-page-name="bgs"]')) return false;
  const button = event.target.closest("[data-bgs-op]");
  if (!button) return false;
  event.preventDefault();
  const extra = {};
  for (const [key, value] of Object.entries(button.dataset)) {
    if (key !== "bgsOp") extra[snake(key)] = value;
  }
  if ("value" in extra) extra.value = Boolean(extra.value);
  send(ui, button.dataset.bgsOp, extra);
  return true;
}

export function handleBgsSubmit(event, ui) {
  const form = event.target.closest?.("[data-bgs-form]");
  if (!form || !ui.byId("bgs-workspace")?.contains(form)) return false;
  event.preventDefault();
  const values = Object.fromEntries(new FormData(form).entries());
  send(ui, form.dataset.bgsForm, values);
  return true;
}

export function handleBgsChange(event, ui) {
  const target = event.target;
  if (!target.matches?.("[data-bgs-autosubmit]") || !ui.byId("bgs-workspace")?.contains(target)) return false;
  const form = target.closest("[data-bgs-form]");
  send(ui, form.dataset.bgsForm, Object.fromEntries(new FormData(form).entries()));
  return true;
}
