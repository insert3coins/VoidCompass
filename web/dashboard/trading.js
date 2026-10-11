// Trading tab (5.5.2.6): your trading from the journal, with charts, and
// Spansh (online, when you ask) for routes, loops, selling your cargo,
// finding any commodity and station markets. The docked station's own market
// comes from the game's Market.json.

const VIEWS = [
  ["overview", "OVERVIEW"], ["route", "ROUTE PLANNER"], ["cargo", "SELL CARGO"],
  ["find", "FIND COMMODITY"], ["station", "MARKET"], ["history", "HISTORY"],
];
const RANGES = [[1, "24H"], [7, "7D"], [30, "30D"], [90, "90D"], [365, "1Y"], [3650, "ALL"]];
// Chart series: two of the validated categorical palette (see trading.css).
const TRADE = "var(--tr-s1)", OTHER = "var(--tr-s2)";

const n = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
const count = (value) => Math.round(n(value)).toLocaleString("en-GB");
const credits = (value) => {
  const v = n(value), abs = Math.abs(v);
  return abs >= 1e9 ? `${(v / 1e9).toFixed(2)}B` : abs >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : abs >= 1e3 ? `${(v / 1e3).toFixed(0)}K` : `${Math.round(v)}`;
};
const cr = (value) => `${credits(value)} CR`;
const signed = (value) => `${n(value) > 0 ? "+" : ""}${credits(value)}`;

function ago(ts) {
  if (!ts) return "unknown age";
  const seconds = Date.now() / 1000 - n(ts);
  if (seconds < 120) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} days ago`;
}

const dateLabel = (ts, hourly) => {
  const d = new Date(ts * 1000);
  return hourly ? d.toISOString().slice(11, 16) : d.toISOString().slice(5, 10);
};

function send(ui, operation, extra = {}) {
  return ui.command("workspace", {page: "trading", operation, ...extra});
}

// Form drafts survive a redraw until they are sent.
const drafts = {};
const field = (form, name, value) => (drafts[form] && name in drafts[form] ? drafts[form][name] : value);

// -- charts ----------------------------------------------------------------
let tips = [];

function niceMax(value) {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  return [1, 2, 2.5, 5, 10].map((step) => step * power).find((step) => step >= value) || value;
}

// Bars per bucket: trading profit (can be a loss, below the zero line) and
// other sales stacked on top of it when positive.
function profitChart(series, days) {
  if (!series?.length || !series.some((row) => row.trade || row.other)) {
    return `<p class="tr-dim">No sales in this range yet.</p>`;
  }
  const hourly = days === 1;
  const W = 760, H = 220, L = 52, R = 12, T = 12, B = 26;
  const top = niceMax(Math.max(...series.map((row) => Math.max(0, row.trade) + row.other)));
  const bottom = Math.min(0, ...series.map((row) => row.trade));
  const low = bottom < 0 ? -niceMax(-bottom) : 0;
  const y = (v) => T + (top - v) / (top - low) * (H - T - B);
  const slot = (W - L - R) / series.length;
  const bar = Math.max(1, Math.min(28, slot - 2));
  const grid = [];
  for (let i = 0; i <= 4; i += 1) {
    const v = low + (top - low) * i / 4;
    grid.push(`<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text class="axis" x="${L - 6}" y="${(y(v) + 3).toFixed(1)}" text-anchor="end">${credits(v)}</text>`);
  }
  const every = Math.ceil(series.length / 8);
  const marks = [];
  tips = [];
  series.forEach((row, index) => {
    const x = L + index * slot + (slot - bar) / 2;
    const tradeTop = y(Math.max(0, row.trade)), tradeBottom = y(Math.min(0, row.trade));
    if (row.trade) marks.push(`<rect class="bar" x="${x.toFixed(1)}" y="${tradeTop.toFixed(1)}" width="${bar.toFixed(1)}" height="${Math.max(1, tradeBottom - tradeTop).toFixed(1)}" rx="${Math.min(4, bar / 3).toFixed(1)}" style="fill:${TRADE}"/>`);
    if (row.other) {
      const base = Math.max(0, row.trade);
      const y1 = y(base + row.other), y0 = y(base);
      // A 2px gap separates the stacked segments.
      marks.push(`<rect class="bar" x="${x.toFixed(1)}" y="${y1.toFixed(1)}" width="${bar.toFixed(1)}" height="${Math.max(1, y0 - y1 - (row.trade > 0 ? 2 : 0)).toFixed(1)}" rx="${Math.min(4, bar / 3).toFixed(1)}" style="fill:${OTHER}"/>`);
    }
    if (index % every === 0) marks.push(`<text class="axis" x="${(x + bar / 2).toFixed(1)}" y="${H - 8}" text-anchor="middle">${dateLabel(row.ts, hourly)}</text>`);
    tips.push({head: hourly ? `${new Date(row.ts * 1000).toISOString().slice(0, 16).replace("T", " ")} UTC` : `${new Date(row.ts * 1000).toISOString().slice(0, 10)}`,
      lines: [[TRADE, `Trading profit ${signed(row.trade)}`], [OTHER, `Other sales ${credits(row.other)}`], ["", `${count(row.tonnes)} t sold`]]});
    marks.push(`<rect class="hit" data-tip="${index}" x="${(L + index * slot).toFixed(1)}" y="${T}" width="${slot.toFixed(1)}" height="${H - T - B}"/>`);
  });
  const zero = low < 0 ? `<line class="zero" x1="${L}" x2="${W - R}" y1="${y(0).toFixed(1)}" y2="${y(0).toFixed(1)}"/>` : "";
  return `<div class="tr-chart-box"><svg class="tr-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Trading profit and other sales per ${hourly ? "hour" : "day"}">${grid.join("")}${zero}${marks.join("")}</svg><div class="tr-tooltip" hidden></div></div>
    <ul class="tr-legend"><li><i style="background:${TRADE}"></i>Trading profit</li><li><i style="background:${OTHER}"></i>Other sales (mined, salvaged)</li></ul>`;
}

// Running total of trading profit over the range, one line.
function cumulativeChart(series, days) {
  if (!series?.length || !series.some((row) => row.trade)) return "";
  let total = 0;
  // From zero at the start of the range, so the first day's profit shows as a rise.
  const step = series.length > 1 ? series[1].ts - series[0].ts : 86400;
  const points = [{ts: series[0].ts - step, v: 0}, ...series.map((row) => ({ts: row.ts, v: (total += row.trade)}))];
  const W = 760, H = 150, L = 52, R = 12, T = 12, B = 22;
  const top = niceMax(Math.max(0, ...points.map((p) => p.v)));
  const low = Math.min(0, ...points.map((p) => p.v));
  const bottom = low < 0 ? -niceMax(-low) : 0;
  const x = (i) => L + (points.length > 1 ? i / (points.length - 1) : 0.5) * (W - L - R);
  const y = (v) => T + (top - v) / (top - bottom) * (H - T - B);
  const grid = [0, 0.5, 1].map((f) => bottom + (top - bottom) * f).map((v) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text class="axis" x="${L - 6}" y="${(y(v) + 3).toFixed(1)}" text-anchor="end">${credits(v)}</text>`);
  const line = points.map((p, i) => `${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
  const last = points[points.length - 1];
  const offset = tips.length;
  points.forEach((p) => tips.push({head: dateLabel(p.ts, days === 1), lines: [[TRADE, `Trading profit so far ${signed(p.v)}`]]}));
  const hits = points.map((p, i) => `<rect class="hit" data-tip="${offset + i}" x="${(x(i) - (W - L - R) / points.length / 2).toFixed(1)}" y="${T}" width="${((W - L - R) / points.length).toFixed(1)}" height="${H - T - B}"/>`);
  return `<div class="tr-chart-box"><svg class="tr-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Trading profit added up over the range">${grid.join("")}
    <polyline class="series" points="${line}" style="stroke:${TRADE}"/><circle class="end" cx="${x(points.length - 1).toFixed(1)}" cy="${y(last.v).toFixed(1)}" r="4" style="fill:${TRADE}"/>${hits.join("")}</svg><div class="tr-tooltip" hidden></div></div>`;
}

// Profit per hour of each session, newest on the right.
function sessionChart(sessions) {
  const rows = (sessions || []).filter((row) => row.trade).slice(0, 20).reverse();
  if (rows.length < 2) return "";
  const W = 760, H = 160, L = 52, R = 12, T = 12, B = 24;
  const top = niceMax(Math.max(...rows.map((row) => Math.max(0, row.per_hour))));
  const y = (v) => T + (top - Math.max(0, v)) / top * (H - T - B);
  const slot = (W - L - R) / rows.length, bar = Math.min(30, slot - 4);
  const offset = tips.length;
  const marks = rows.map((row, i) => {
    tips.push({head: `${new Date(row.start * 1000).toISOString().slice(0, 16).replace("T", " ")} UTC · ${row.hours} h`,
      lines: [[TRADE, `${cr(row.per_hour)} per hour`], ["", `Trading profit ${signed(row.trade)}`], ["", `${count(row.tonnes)} t sold`]]});
    const x = L + i * slot + (slot - bar) / 2;
    return `<rect class="bar" x="${x.toFixed(1)}" y="${y(row.per_hour).toFixed(1)}" width="${bar.toFixed(1)}" height="${Math.max(1, y(0) - y(row.per_hour)).toFixed(1)}" rx="4" style="fill:${TRADE}"/>
      <text class="axis" x="${(x + bar / 2).toFixed(1)}" y="${H - 8}" text-anchor="middle">${dateLabel(row.start)}</text>
      <rect class="hit" data-tip="${offset + i}" x="${(L + i * slot).toFixed(1)}" y="${T}" width="${slot.toFixed(1)}" height="${H - T - B}"/>`;
  });
  const grid = [0, 0.5, 1].map((f) => top * f).map((v) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text class="axis" x="${L - 6}" y="${(y(v) + 3).toFixed(1)}" text-anchor="end">${credits(v)}</text>`);
  return `<div class="tr-chart-box"><svg class="tr-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Trading profit per hour for each session">${grid.join("")}${marks.join("")}</svg><div class="tr-tooltip" hidden></div></div>`;
}

function bindCharts(root) {
  root.querySelectorAll(".tr-chart-box").forEach((box) => {
    const tip = box.querySelector(".tr-tooltip");
    const svg = box.querySelector("svg");
    if (!tip || !svg) return;
    svg.addEventListener("mousemove", (event) => {
      const hit = event.target.closest?.(".hit");
      if (!hit) return;
      const data = tips[n(hit.dataset.tip)];
      if (!data) return;
      svg.querySelectorAll(".hit.on").forEach((node) => node.classList.remove("on"));
      hit.classList.add("on");
      tip.replaceChildren();
      const head = document.createElement("b");
      head.textContent = data.head;
      tip.appendChild(head);
      for (const [colour, text] of data.lines) {
        const line = document.createElement("span");
        if (colour) {
          const swatch = document.createElement("i");
          swatch.style.background = colour;
          line.appendChild(swatch);
        }
        line.append(text);
        tip.appendChild(line);
      }
      tip.hidden = false;
      const rect = box.getBoundingClientRect();
      const left = event.clientX - rect.left + 14;
      tip.style.left = `${Math.max(4, Math.min(rect.width - tip.offsetWidth - 4, left))}px`;
    });
    svg.addEventListener("mouseleave", () => {
      tip.hidden = true;
      svg.querySelectorAll(".hit.on").forEach((node) => node.classList.remove("on"));
    });
  });
}

// Horizontal bars for a ranked list (one series, so no legend).
function rankBars(rows, valueKey, label, esc, extra = () => "") {
  if (!rows?.length) return `<p class="tr-dim">Nothing yet.</p>`;
  const top = Math.max(...rows.map((row) => Math.max(0, n(row[valueKey])))) || 1;
  return `<ol class="tr-ranks">${rows.map((row) => `<li><span class="tr-rank-name">${esc(row.name)}</span>
    <span class="tr-rank-bar"><i style="width:${Math.max(1, n(row[valueKey]) / top * 100).toFixed(1)}%"></i></span>
    <b>${label(row)}</b><small>${extra(row)}</small></li>`).join("")}</ol>`;
}

// -- shared pieces -----------------------------------------------------------
function ranges(days) {
  return `<div class="tr-ranges">${RANGES.map(([value, label]) => `<button type="button" class="${days === value ? "active" : ""}" data-trade-op="days" data-days="${value}">${label}</button>`).join("")}</div>`;
}

function tile(label, value, note = "") {
  return `<div class="tr-tile"><span>${label}</span><b>${value}</b>${note ? `<small>${note}</small>` : ""}</div>`;
}

function followCard(step, esc) {
  if (!step) return "";
  if (step.done) {
    return `<section class="tr-follow done"><div><p>ROUTE COMPLETE</p><h3>${cr(step.profit)} profit over ${step.hops} hop${step.hops === 1 ? "" : "s"}</h3></div>
      <div class="tr-actions"><button type="button" data-trade-op="stop_route">CLEAR</button></div></section>`;
  }
  const warn = (step.warnings || []).map((text) => `<p class="tr-warn">⚠ ${esc(text)}</p>`).join("");
  return `<section class="tr-follow"><div><p>FOLLOWING · HOP ${step.hop} OF ${step.hops}${step.here ? " · YOU ARE HERE" : ""}</p>
      <h3>${esc(step.action)}</h3><span>${step.phase === "buy" ? "at" : "at"} <b>${esc(step.station)}</b> · ${esc(step.system)}${step.phase === "sell" && step.distance ? ` · ${n(step.distance).toFixed(1)} ly` : ""}</span>
      <small>Planned for this hop ${cr(step.expected)} · made so far ${cr(step.profit)}</small>${warn}</div>
    <div class="tr-actions"><button type="button" data-trade-op="copy" data-text="${esc(step.system)}">COPY SYSTEM</button><button type="button" data-trade-op="skip_hop">SKIP HOP</button><button type="button" data-trade-op="stop_route">STOP</button></div></section>`;
}

function stationCell(row, esc) {
  const tags = [row.pad ? `${row.pad} PAD` : "", row.planetary ? "PLANETARY" : "", row.carrier ? "CARRIER" : ""].filter(Boolean);
  return `<b>${esc(row.station)}</b><small>${esc(row.system)}${row.arrival_ls != null ? ` · ${count(row.arrival_ls)} ls` : ""}${tags.length ? ` · ${tags.join(" · ")}` : ""}</small>`;
}

// -- views -------------------------------------------------------------------
function overview(data, ui) {
  const esc = ui.escapeHtml;
  const s = data.summary || {};
  const totals = s.totals?.range || {}, today = s.totals?.today || {};
  const best = s.best;
  const tiles = `<div class="tr-tiles">
    ${tile("TRADING PROFIT", cr(totals.trade_profit), `${count(totals.trades)} sales · ${count(totals.traded_t)} t`)}
    ${tile("PROFIT PER HOUR", s.per_hour != null ? cr(s.per_hour) : "—", "over your game sessions")}
    ${tile("OTHER SALES", cr(totals.other_sales), `mined and salvaged · ${count(totals.other_t)} t`)}
    ${tile("TODAY", cr(today.trade_profit), `${cr(today.other_sales)} other sales`)}
    ${tile("BEST SALE", best ? cr(best.profit) : "—", best ? `${esc(best.name)} · ${esc(best.station)}` : "")}</div>`;
  const routes = (s.routes || []).slice(0, 5).map((row) => `<li><b>${esc(row.commodity)}</b><span>${esc(row.from)} → ${esc(row.to)}</span>
    <small>${esc(row.from_system)} → ${esc(row.to_system)} · ${row.runs} run${row.runs === 1 ? "" : "s"} · ${cr(row.per_t)}/t</small><em>${cr(row.profit)}</em></li>`).join("");
  const recent = (s.recent || []).map((row) => `<li class="${row.kind}"><span>${row.kind === "buy" ? "BOUGHT" : "SOLD"}</span><b>${count(row.count)} t ${esc(row.name)}</b>
    <small>${esc(row.station)} · ${ago(row.ts)}</small><em>${row.kind === "buy" ? `−${credits(row.total)}` : row.profit != null ? signed(row.profit) : `+${credits(row.total)}`}</em></li>`).join("");
  return `${followCard(data.followed, esc)}
    <div class="tr-head"><span>${data.import?.running ? "Reading your journals…" : "From your journal"}</span>${ranges(data.days)}</div>
    ${tiles}
    <section class="tr-panel wide"><h4>PROFIT PER ${data.days === 1 ? "HOUR" : "DAY"}</h4>${profitChart(s.series, data.days)}</section>
    <section class="tr-panel wide"><h4>TRADING PROFIT, ADDED UP</h4>${cumulativeChart(s.series, data.days) || `<p class="tr-dim">No trading profit in this range.</p>`}</section>
    <div class="tr-grid">
      <section class="tr-panel"><h4>BEST COMMODITIES</h4>${rankBars(s.commodities, "profit", (row) => cr(row.profit), esc, (row) => `${count(row.tonnes)} t · ${cr(row.per_t)}/t`)}</section>
      <section class="tr-panel"><h4>BEST ROUTES YOU'VE FLOWN</h4>${routes ? `<ol class="tr-list">${routes}</ol>` : `<p class="tr-dim">Buy somewhere and sell somewhere else, and your routes show here.</p>`}</section>
      <section class="tr-panel"><h4>OTHER SALES</h4>${rankBars(s.other_sales, "income", (row) => cr(row.income), esc, (row) => `${count(row.tonnes)} t`)}</section>
      <section class="tr-panel"><h4>RECENT</h4>${recent ? `<ul class="tr-recent">${recent}</ul>` : `<p class="tr-dim">No trades yet.</p>`}</section>
    </div>`;
}

function check(name, label, value) {
  return `<label class="tr-check"><input type="checkbox" name="${name}" ${n(field("route", name, value)) ? "checked" : ""}><span>${label}</span></label>`;
}

// Spansh only says queued, then started, then done: the steps show which,
// with the time so far (it ticks on its own, see tickElapsed).
// A system search (5.5.3.4): the system's markets first, then one line per
// station the router is trying, each with its own state, on one timer.
const START_STATES = {queued: ["", "In Spansh's queue"], started: ["›", "Working out the cargo for each hop"],
  done: ["✓", "Done"], failed: ["✕", "Failed"]};

function systemProgress(route, esc) {
  const starts = route.starts || [];
  const lines = starts.map((row) => {
    const [mark, label] = START_STATES[row.state] || START_STATES.queued;
    return `<li class="${row.state === "done" ? "done" : row.state === "started" ? "now" : row.state === "failed" ? "failed" : ""}"><i>${mark}</i><b>${esc(row.station)}</b> · ${label}</li>`;
  }).join("");
  const markets = route.stage === "markets";
  return `<section class="tr-panel wide tr-progress"><div class="tr-result-head"><div><p>PLANNING ON SPANSH · ANY STATION IN ${esc(String(route.system || "").toUpperCase())}</p>
      <h3><span data-tr-since="${n(route.started)}">0:00</span></h3>
      <span>${markets ? "Reading every market in the system, to pick the best stations to start from." : `${starts.length} station${starts.length === 1 ? "" : "s"}: Spansh plans them one after another, so each adds about as long as one search.`}</span></div>
      <div class="tr-actions"><button type="button" data-trade-op="stop_plan">STOP</button></div></div>
    <div class="tr-bar"><i></i></div><ol class="tr-steps"><li class="${markets ? "now" : "done"}"><i>${markets ? "›" : "✓"}</i>The system's markets</li>${lines}</ol></section>`;
}

// What a system search compared: each start's best route, best first.
function startsCompared(route, esc) {
  const starts = route.starts || [];
  if (!starts.length) return "";
  const good = starts.filter((row) => row.result?.hops?.length);
  const headline = good.slice(0, 3).map((row) => `${esc(row.station)} ${credits(row.result.profit)}`).join(" · ");
  const leftOut = Object.entries(route.left_out || {}).map(([key, value]) => `${count(value)} ${LEFT_OUT[key] || key}`).join(", ");
  const rows = starts.map((row, index) => {
    const plan = row.result;
    const tags = [row.pad ? `${row.pad} PAD` : "", row.planetary ? "PLANETARY" : ""].filter(Boolean).join(" · ");
    const worth = plan?.hops?.length ? `<em>${cr(plan.profit)}</em><small>${plan.hops.length} hop${plan.hops.length === 1 ? "" : "s"} · ${cr(plan.profit / plan.hops.length)} a hop</small>`
      : `<em class="none">—</em><small>${row.error ? esc(row.error) : "No profitable route from here"}</small>`;
    return `<li class="${index === route.pick ? "picked" : ""}">
      <div><b>${esc(row.station)}</b><small>${esc(row.type || "")}${row.arrival_ls != null ? ` · ${count(row.arrival_ls)} ls` : ""}${tags ? ` · ${tags}` : ""} · ${count(row.in_stock)} goods in stock · prices ${ago(row.updated)}</small></div>
      <div class="tr-start-worth">${worth}</div>
      <div class="tr-actions">${plan?.hops?.length ? `<button type="button" data-trade-op="pick_start" data-index="${index}" ${index === route.pick ? "disabled" : ""}>${index === route.pick ? "SHOWN" : "SHOW"}</button>` : ""}</div></li>`;
  }).join("");
  return `<section class="tr-panel wide"><div class="tr-result-head"><div><p>BEST START IN ${esc(String(route.system || "").toUpperCase())}</p><h3>${headline || "No profitable route"}</h3>
      <span>Tried the ${starts.length} most promising of ${count(route.fitting)} station${route.fitting === 1 ? "" : "s"} that fit your settings (${count(route.markets)} with a market${leftOut ? `; left out: ${esc(leftOut)}` : ""}). Picked by goods in stock and fresh prices: a guess, which Spansh then priced.</span></div></div>
    <ol class="tr-starts">${rows}</ol></section>`;
}

const LEFT_OUT = {pad: "no large pad", carrier: "fleet carriers", planetary: "planetary", old: "prices too old",
  far: "too far from the star", empty: "nothing in stock"};

function routeProgress(route) {
  const order = ["station", "queued", "started"];
  const at = order.indexOf(route.stage || "station");
  const steps = [["station", "Finding the station"], ["queued", "Waiting in Spansh's queue"], ["started", "Spansh is working out the best cargo for each hop"]];
  const items = steps.map(([id, label], index) => `<li class="${index < at ? "done" : index === at ? "now" : ""}"><i>${index < at ? "✓" : index === at ? "›" : ""}</i>${label}</li>`).join("");
  const hops = n(route.hops);
  return `<section class="tr-panel wide tr-progress"><div class="tr-result-head"><div><p>PLANNING ON SPANSH</p>
      <h3><span data-tr-since="${n(route.started)}">0:00</span></h3>
      <span>${hops >= 4 ? `${hops} hops usually take one to three minutes; fewer hops come back quicker.` : `${hops} hop${hops === 1 ? "" : "s"} usually take under a minute.`}</span></div>
      <div class="tr-actions"><button type="button" data-trade-op="stop_plan">STOP</button></div></div>
    <div class="tr-bar"><i></i></div><ol class="tr-steps">${items}</ol></section>`;
}

function routeView(data, ui) {
  const esc = ui.escapeHtml;
  const f = data.form || {};
  const input = (name, label, type = "number", extra = "") => `<label><span>${label}</span><input name="${name}" type="${type}" value="${esc(field("route", name, f[name] ?? ""))}" ${extra}></label>`;
  const busy = (data.busy || []).includes("route");
  // From any station in the system (5.5.3.4): no station needed, and how
  // many of the system's best stations to try.
  const whole = Boolean(n(field("route", "whole_system", f.whole_system)));
  const form = `<form class="tr-form" data-trade-form="plan">
    <div class="tr-fields">${input("system", "FROM SYSTEM", "text", 'maxlength="120" required')}${input("station", whole ? "FROM STATION (ANY)" : "FROM STATION", "text", `maxlength="120" data-tr-station ${whole ? "disabled" : "required"}`)}
      <label data-tr-try ${whole ? "" : "hidden"}><span title="Each station adds about one search's time">STATIONS TO TRY</span><select name="try_stations">${[1, 2, 3, 4, 5, 6].map((value) => `<option value="${value}" ${n(field("route", "try_stations", f.try_stations || 3)) === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
      ${input("max_cargo", "CARGO (T)", "number", 'min="1"')}${input("starting_capital", "CREDITS", "number", 'min="0"')}
      ${input("max_hop_distance", "MAX HOP (LY)", "number", 'min="1" step="1"')}${input("max_hops", "HOPS (EACH ADDS TIME)", "number", 'min="1" max="20"')}
      ${input("max_system_distance", "MAX FROM STAR (LS)", "number", 'min="10"')}${input("max_price_age_days", "PRICES NO OLDER THAN (DAYS)", "number", 'min="1" max="365"')}</div>
    <div class="tr-checks">${check("whole_system", "From any station in this system", f.whole_system)}${check("requires_large_pad", "Large pad", f.requires_large_pad)}${check("allow_planetary", "Planetary ports", f.allow_planetary)}
      ${check("allow_player_owned", "Fleet carriers", f.allow_player_owned)}${check("allow_prohibited", "Illegal goods", f.allow_prohibited)}
      ${check("permit", "Permit systems", f.permit)}${check("allow_restricted_access", "Restricted stations", f.allow_restricted_access)}
      ${check("unique", "Don't revisit a station", f.unique)}</div>
    <div class="tr-actions"><button type="submit" class="primary" ${busy ? "disabled" : ""}>${busy ? "PLANNING ON SPANSH…" : "PLAN ROUTE"}</button><button type="button" data-trade-op="form_reset">USE MY SHIP AND LOCATION</button></div></form>`;
  const route = data.route || {};
  let result = "";
  if (route.error) result = `<p class="co-error">${esc(route.error)}</p>`;
  if (route.choices) {
    const c = route.choices;
    const shown = c.stations.filter((row) => !row.carrier || n(f.allow_player_owned));
    result = `<section class="tr-panel wide"><h4>WHICH STATION?</h4>
      <p class="tr-dim">${shown.length ? `There's no station called <b>${esc(c.typed)}</b> in ${esc(c.system)}. Pick one with a market:` : `Spansh has no station with a market in ${esc(c.system)}.`}</p>
      <div class="tr-picks">${shown.map((row) => `<button type="button" data-trade-op="pick_station" data-system="${esc(c.system)}" data-station="${esc(row.name)}">
        <b>${esc(row.name)}</b><small>${esc(row.type)}${row.arrival_ls != null ? ` · ${count(row.arrival_ls)} ls` : ""}</small></button>`).join("")}</div></section>`;
  }
  const plan = route.result;
  if (plan?.hops?.length) {
    const top = Math.max(...plan.hops.map((hop) => hop.cumulative)) || 1;
    const hops = plan.hops.map((hop, i) => `<section class="tr-hop"><header><span class="tr-hop-n">${i + 1}</span>
        <div><b>${esc(hop.from.station)}</b><small>${esc(hop.from.system)} · prices ${ago(hop.from.updated)}</small></div><span class="tr-arrow">→ ${n(hop.distance).toFixed(1)} ly →</span>
        <div><b>${esc(hop.to.station)}</b><small>${esc(hop.to.system)}${hop.to.arrival_ls != null ? ` · ${count(hop.to.arrival_ls)} ls` : ""} · prices ${ago(hop.to.updated)}</small></div>
        <em>${cr(hop.profit)}</em></header>
      <table class="tr-table"><thead><tr><th>COMMODITY</th><th>AMOUNT</th><th>BUY</th><th>SELL</th><th>PROFIT/T</th><th>PROFIT</th><th>STOCK / DEMAND</th></tr></thead>
        <tbody>${hop.goods.map((item) => `<tr><td>${esc(item.name)}</td><td>${count(item.amount)} t</td><td>${count(item.buy)}</td><td>${count(item.sell)}</td><td>${count(item.profit)}</td><td>${cr(item.total)}</td><td>${count(item.supply)} / ${count(item.demand)}</td></tr>`).join("")}</tbody></table>
      <div class="tr-hop-bar" title="Profit so far: ${cr(hop.cumulative)}"><i style="width:${(hop.cumulative / top * 100).toFixed(1)}%"></i><span>${cr(hop.cumulative)} so far</span></div>
      <div class="tr-actions"><button type="button" data-trade-op="copy" data-text="${esc(hop.to.system)}">COPY ${esc(hop.to.system)}</button>
        <button type="button" data-trade-op="loop" data-market-a="${esc(hop.from.market_id)}" data-market-b="${esc(hop.to.market_id)}">LOOP THESE TWO</button>
        <button type="button" data-trade-op="station" data-market-id="${esc(hop.to.market_id)}">MARKET</button>
        <button type="button" data-trade-op="open" data-kind="station" data-market-id="${esc(hop.to.market_id)}">SPANSH</button></div></section>`).join("");
    result += `<section class="tr-panel wide"><div class="tr-result-head"><div><p>SPANSH TRADE ROUTE${route.whole && route.station ? ` FROM ${esc(String(route.station).toUpperCase())}` : ""}</p><h3>${cr(plan.profit)} over ${plan.hops.length} hop${plan.hops.length === 1 ? "" : "s"}</h3>
        <span>${n(plan.distance).toFixed(1)} ly · ${cr(plan.profit / plan.hops.length)} a hop · planned ${ago(route.planned_at)}</span></div>
        <div class="tr-actions"><button type="button" class="primary" data-trade-op="follow">FOLLOW THIS ROUTE</button></div></div>${hops}</section>`;
  }
  const loop = data.loop || {};
  let loopHtml = "";
  if (loop.pending || (data.busy || []).includes("loop")) loopHtml = `<p class="tr-dim">Working out the loop from both markets…</p>`;
  else if (loop.error) loopHtml = `<p class="co-error">${esc(loop.error)}</p>`;
  else if (loop.result) {
    const r = loop.result;
    const leg = (item, a, b) => item ? `<li><b>${esc(a.station)} → ${esc(b.station)}</b><span>${count(item.amount)} t ${esc(item.name)} · buy ${count(item.buy)}, sell ${count(item.sell)} · ${cr(item.profit)}/t</span><em>${cr(item.total)}</em></li>`
      : `<li><b>${esc(a.station)} → ${esc(b.station)}</b><span>Nothing profitable to carry this way: fly it empty.</span><em>0</em></li>`;
    loopHtml = `<section class="tr-panel wide"><div class="tr-result-head"><div><p>LOOP ROUTE</p><h3>${cr(r.profit)} a round trip</h3>
        <span>${esc(r.a.station)} (${esc(r.a.system)}) ⇄ ${esc(r.b.station)} (${esc(r.b.system)}) · from both markets on Spansh</span></div>
        <div class="tr-actions"><button type="button" class="primary" data-trade-op="follow_loop">FOLLOW THIS LOOP</button></div></div>
      <ol class="tr-list">${leg(r.out, r.a, r.b)}${leg(r.back, r.b, r.a)}</ol></section>`;
  }
  return `${followCard(data.followed, esc)}<section class="tr-panel wide"><h4>PLAN A ROUTE</h4>
    <p class="tr-dim">Spansh's trade router finds the best cargo for each hop from a station, with prices from players' game data. Your ship, credits and location are filled in from the journal.</p>${form}</section>
    ${busy && route.pending ? (route.whole ? systemProgress(route, esc) : routeProgress(route)) : ""}${route.whole && !route.pending ? startsCompared(route, esc) : ""}${result}${loopHtml}`;
}

function cargoView(data, ui) {
  const esc = ui.escapeHtml;
  const hold = data.hold || [];
  const cargo = data.cargo || {};
  const busy = (data.busy || []).includes("cargo");
  // By price (the best five payers) or by distance (the five nearest), both
  // from the same search (5.5.3.5).
  const byDistance = data.cargo_sort === "distance";
  const holdList = hold.length ? `<ul class="tr-hold">${hold.map((row) => `<li><b>${count(row.count)} t</b><span>${esc(row.name)}</span>${row.stolen ? `<small>${count(row.stolen)} stolen</small>` : ""}</li>`).join("")}</ul>`
    : `<p class="tr-dim">Your hold is empty.</p>`;
  let results = "";
  if (cargo.error) results = `<p class="co-error">${esc(cargo.error)}</p>`;
  for (const row of cargo.rows || []) {
    const best = row.stations[0];
    const listed = byDistance && Array.isArray(row.nearest) ? row.nearest : row.stations;
    results += `<section class="tr-panel wide"><div class="tr-result-head"><div><p>${count(row.count)} T</p><h3>${esc(row.name)}</h3>
        <span>${best ? `Best nearby: ${cr(best.price * row.count)} at ${esc(best.station)}` : "Nowhere nearby wants it in Spansh's data."}</span>
        ${row.here ? `<small class="tr-here">In ${esc(cargo.system)}: ${esc(row.here.station)} pays ${count(row.here.price)}${best && best.market_id !== row.here.market_id ? ` (${cr(row.here.price * row.count)} for yours)` : ", the best nearby"}</small>` : ""}</div></div>
      ${listed.length ? `<table class="tr-table"><thead><tr><th>STATION</th><th>DISTANCE</th><th>PRICE</th><th>FOR YOUR ${count(row.count)} T</th><th>DEMAND</th><th>PRICES</th><th></th></tr></thead><tbody>
        ${listed.map((s) => `<tr${s.stock < row.count ? ' class="short"' : ""}><td>${stationCell(s, esc)}</td><td>${n(s.distance).toFixed(1)} ly</td><td>${count(s.price)}</td><td>${cr(s.price * Math.min(row.count, s.stock))}</td>
          <td>${count(s.stock)}${s.stock < row.count ? " (less than you have)" : ""}</td><td>${ago(s.updated)}</td><td><button type="button" data-trade-op="copy" data-text="${esc(s.system)}">COPY</button></td></tr>`).join("")}</tbody></table>` : ""}</section>`;
  }
  return `<section class="tr-panel wide"><h4>IN YOUR HOLD</h4>${holdList}
    <div class="tr-actions"><button type="button" class="primary" data-trade-op="cargo" ${busy || !hold.length ? "disabled" : ""}>${busy ? "ASKING SPANSH…" : "FIND THE BEST PRICES NEAR ME"}</button></div>
    ${busy && cargo.pending ? `<div class="tr-bar determinate"><i style="width:${(n(cargo.done) / Math.max(1, n(cargo.total)) * 100).toFixed(0)}%"></i></div>
      <p class="tr-dim">Checking ${n(cargo.done) + 1} of ${n(cargo.total)}: ${esc(cargo.current || "")}</p>` : ""}
    ${cargo.rows ? `<div class="tr-sort-row"><p class="tr-dim">Near ${esc(cargo.system)} · ${ago(cargo.at)} · each commodity's ${byDistance ? "five nearest stations that buy it" : "best five stations by price"}.</p>
      <div class="tr-ranges"><button type="button" class="${byDistance ? "" : "active"}" data-trade-op="cargo_sort" data-sort="price">BY PRICE</button><button type="button" class="${byDistance ? "active" : ""}" data-trade-op="cargo_sort" data-sort="distance">BY DISTANCE</button></div></div>` : ""}</section>${results}`;
}

function findView(data, ui) {
  const esc = ui.escapeHtml;
  const f = data.find || {};
  const busy = (data.busy || []).includes("find");
  const kind = field("find", "kind", f.kind || "sell");
  const options = (data.names || []).map((name) => `<option value="${esc(name)}"></option>`).join("");
  const form = `<form class="tr-form" data-trade-form="find">
    <div class="tr-fields">
      <label><span>I WANT TO</span><select name="kind"><option value="sell" ${kind === "sell" ? "selected" : ""}>Sell it</option><option value="buy" ${kind === "buy" ? "selected" : ""}>Buy it</option></select></label>
      <label class="grow"><span>COMMODITY</span><input name="commodity" list="tr-commodities" maxlength="80" required value="${esc(field("find", "commodity", f.commodity || ""))}"></label>
      <label><span>NEAR SYSTEM</span><input name="system" maxlength="120" value="${esc(field("find", "system", f.system || data.where?.system || ""))}"></label>
      <label><span>AMOUNT (T)</span><input name="amount" type="number" min="1" value="${esc(field("find", "amount", f.amount || 1))}"></label></div>
    <div class="tr-checks"><label class="tr-check"><input type="checkbox" name="large" ${n(field("find", "large", f.large)) ? "checked" : ""}><span>Large pad only</span></label>
      <label class="tr-check"><input type="checkbox" name="carriers" ${n(field("find", "carriers", f.carriers)) ? "checked" : ""}><span>Fleet carriers</span></label>
      <label class="tr-check"><input type="checkbox" name="planetary" ${n(field("find", "planetary", f.planetary)) ? "checked" : ""}><span>Planetary ports</span></label></div>
    <div class="tr-actions"><button type="submit" class="primary" ${busy ? "disabled" : ""}>${busy ? "SEARCHING SPANSH…" : "SEARCH"}</button></div>
    <datalist id="tr-commodities">${options}</datalist></form>`;
  let rows = (f.results || []).filter((row) => (!n(f.large) || row.pad === "L") && (n(f.carriers) || !row.carrier) && (n(f.planetary) || !row.planetary));
  rows = [...rows].sort(f.sort === "distance" ? (a, b) => n(a.distance) - n(b.distance)
    : f.searched?.[0] === "buy" ? (a, b) => a.price - b.price : (a, b) => b.price - a.price);
  const buying = f.searched?.[0] === "buy";
  // What the searched system's own stations pay or charge (5.5.3.4).
  const here = (f.here || []).map((row) => `${esc(row.station)} ${buying ? "charges" : "pays"} ${count(row.price)}`).join(" · ");
  const table = rows.length ? `<div class="tr-result-head"><div><p>${buying ? "WHERE TO BUY" : "WHERE TO SELL"}</p><h3>${esc(f.resolved || f.commodity)}</h3><span>near ${esc(f.searched?.[1] || "")} · ${rows.length} station${rows.length === 1 ? "" : "s"}</span>
      ${here ? `<small class="tr-here">In ${esc(f.searched?.[1] || "")}: ${here}</small>` : f.searched ? `<small class="tr-here">No station in ${esc(f.searched[1])} itself ${buying ? "sells" : "buys"} it with these settings.</small>` : ""}</div>
      <div class="tr-ranges"><button type="button" class="${f.sort !== "distance" ? "active" : ""}" data-trade-op="find_sort" data-sort="price">BY PRICE</button><button type="button" class="${f.sort === "distance" ? "active" : ""}" data-trade-op="find_sort" data-sort="distance">BY DISTANCE</button></div></div>
    <table class="tr-table"><thead><tr><th>STATION</th><th>DISTANCE</th><th>${buying ? "COSTS" : "PAYS"}</th><th>${buying ? "STOCK" : "DEMAND"}</th><th>PRICES</th><th></th></tr></thead><tbody>
      ${rows.map((row) => `<tr><td>${stationCell(row, esc)}</td><td>${n(row.distance).toFixed(1)} ly</td><td>${count(row.price)}</td><td>${count(row.stock)}</td><td>${ago(row.updated)}</td>
        <td><button type="button" data-trade-op="copy" data-text="${esc(row.system)}">COPY</button><button type="button" data-trade-op="station" data-market-id="${esc(row.market_id)}">MARKET</button></td></tr>`).join("")}</tbody></table>` : "";
  return `<section class="tr-panel wide"><h4>FIND A COMMODITY</h4>${form}${f.error ? `<p class="co-error">${esc(f.error)}</p>` : ""}</section>${table ? `<section class="tr-panel wide">${table}</section>` : ""}`;
}

function marketTable(station, esc, local) {
  const rows = station.market || [];
  let category = "";
  const body = rows.map((row) => {
    const head = row.category !== category ? `<tr class="cat"><td colspan="${local ? 7 : 6}">${esc((category = row.category) || "Other")}</td></tr>` : "";
    return `${head}<tr><td>${esc(row.name)}</td><td>${row.buy ? count(row.buy) : "—"}</td><td>${row.sell ? count(row.sell) : "—"}</td>
      <td>${row.supply ? count(row.supply) : "—"}</td><td>${row.demand ? count(row.demand) : "—"}</td>
      ${local ? `<td>${row.mean ? count(row.mean) : "—"}</td>` : ""}
      <td>${row.supply ? `<button type="button" data-trade-op="sell_here" data-commodity="${esc(row.name)}">WHERE TO SELL</button>` : ""}</td></tr>`;
  }).join("");
  return `<table class="tr-table market"><thead><tr><th>COMMODITY</th><th>BUY</th><th>SELL</th><th>STOCK</th><th>DEMAND</th>${local ? `<th title="The game's own galactic average price">GALACTIC AVERAGE</th>` : ""}<th></th></tr></thead><tbody>${body}</tbody></table>`;
}

function stationView(data, ui) {
  const esc = ui.escapeHtml;
  const st = data.station || {};
  const local = st.local, remote = st.remote;
  let html = "";
  if (local) {
    html += `<section class="tr-panel wide"><div class="tr-result-head"><div><p>DOCKED · FROM THE GAME</p><h3>${esc(local.station)}</h3><span>${esc(local.system)} · market read ${ago(local.updated)}</span></div>
      <div class="tr-actions"><button type="button" class="primary" data-trade-op="plan_from" data-system="${esc(local.system)}" data-station="${esc(local.station)}">PLAN A ROUTE FROM HERE</button></div></div>
      ${marketTable(local, esc, true)}</section>`;
  } else if (data.where?.docked) {
    html += `<section class="tr-panel wide"><p class="tr-dim">Open the commodity market in game and this station's prices show here, straight from the game.</p></section>`;
  } else {
    html += `<section class="tr-panel wide"><p class="tr-dim">Dock and open the commodity market to see it here. Any station from a route or search can be opened with its MARKET button.</p></section>`;
  }
  // Any station in a system, from one request (5.5.3.4).
  const list = st.list || {};
  const busyList = (data.busy || []).includes("markets");
  const stations = (list.stations || []).map((row) => `<button type="button" data-trade-op="station" data-market-id="${esc(row.market_id)}">
      <b>${esc(row.station)}</b><small>${esc(row.type || "")}${row.arrival_ls != null ? ` · ${count(row.arrival_ls)} ls` : ""}${row.pad ? ` · ${row.pad} pad` : ""} · ${count(row.in_stock)} for sale · ${count(row.wanted)} wanted · prices ${ago(row.updated)}</small></button>`).join("");
  const listHtml = `<section class="tr-panel wide"><h4>ANY STATION IN A SYSTEM</h4>
    <form class="tr-form tr-inline" data-trade-form="system_markets"><div class="tr-fields"><label class="grow"><span>SYSTEM</span><input name="system" maxlength="120" required value="${esc(field("system_markets", "system", list.system || data.where?.system || ""))}"></label></div>
      <div class="tr-actions"><button type="submit" class="primary" ${busyList ? "disabled" : ""}>${busyList ? "ASKING SPANSH…" : "LIST ITS STATIONS"}</button></div></form>
    ${list.error ? `<p class="co-error">${esc(list.error)}</p>` : ""}
    ${list.stations ? (stations ? `<p class="tr-dim">${count(list.stations.length)} station${list.stations.length === 1 ? "" : "s"} with a market in ${esc(list.system)}, nearest the star first. Open one to see its market.</p><div class="tr-picks">${stations}</div>`
      : `<p class="tr-dim">Spansh has no station with a market in ${esc(list.system)}.</p>`) : ""}</section>`;
  if (st.error) html += `<p class="co-error">${esc(st.error)}</p>`;
  if (remote && (!local || remote.market_id !== local.market_id)) {
    html += `<section class="tr-panel wide"><div class="tr-result-head"><div><p>FROM SPANSH</p><h3>${esc(remote.station)}</h3><span>${esc(remote.system)} · prices ${ago(remote.updated)}${remote.pad ? ` · ${remote.pad} pad` : ""}</span></div>
      <div class="tr-actions"><button type="button" data-trade-op="copy" data-text="${esc(remote.system)}">COPY SYSTEM</button><button type="button" data-trade-op="plan_from" data-system="${esc(remote.system)}" data-station="${esc(remote.station)}">PLAN FROM HERE</button></div></div>
      ${marketTable(remote, esc, false)}</section>`;
  }
  return html + listHtml;
}

function historyView(data, ui) {
  const esc = ui.escapeHtml;
  const s = data.summary || {};
  const totals = s.totals?.range || {};
  const sessions = (s.sessions || []).map((row) => `<tr><td>${new Date(row.start * 1000).toISOString().slice(0, 16).replace("T", " ")}</td><td>${row.hours} h</td>
    <td>${row.trade ? signed(row.trade) : "—"}</td><td>${row.trade ? cr(row.per_hour) : "—"}</td><td>${cr(row.other)}</td><td>${count(row.tonnes)} t</td></tr>`).join("");
  const routes = (s.routes || []).map((row) => `<tr><td>${esc(row.commodity)}</td><td>${esc(row.from)}<small>${esc(row.from_system)}</small></td><td>${esc(row.to)}<small>${esc(row.to_system)}</small></td>
    <td>${row.runs}</td><td>${count(row.tonnes)} t</td><td>${cr(row.per_t)}</td><td>${cr(row.profit)}</td></tr>`).join("");
  const stations = (s.stations || []).map((row) => `<tr><td>${esc(row.station)}<small>${esc(row.system)}</small></td><td>${row.sales}</td><td>${count(row.tonnes)} t</td><td>${cr(row.income)}</td><td>${cr(row.profit)}</td></tr>`).join("");
  const trades = (s.recent || []).map((row) => `<tr class="${row.kind}"><td>${new Date(row.ts * 1000).toISOString().slice(0, 16).replace("T", " ")}</td><td>${row.kind === "buy" ? "Bought" : "Sold"}</td>
    <td>${esc(row.name)}${row.flags.length ? ` <small>${row.flags.map((flag) => flag.replace("_", " ")).join(", ")}</small>` : ""}</td><td>${count(row.count)} t</td><td>${count(row.price)}</td><td>${cr(row.total)}</td>
    <td>${row.kind === "sell" ? (row.profit != null ? signed(row.profit) : "no cost") : ""}</td><td>${esc(row.station)}<small>${esc(row.system)}</small></td></tr>`).join("");
  return `<div class="tr-head"><span>${cr(totals.trade_profit)} trading profit · ${cr(totals.other_sales)} other sales · ${cr(totals.spent)} spent</span>${ranges(data.days)}</div>
    <section class="tr-panel wide"><div class="tr-result-head"><div><h4>PROFIT PER HOUR, BY SESSION</h4></div><div class="tr-actions"><button type="button" data-trade-op="copy_report">COPY DISCORD REPORT</button></div></div>
      ${sessionChart(s.sessions) || `<p class="tr-dim">Two or more sessions with trading make a chart here.</p>`}
      ${sessions ? `<table class="tr-table"><thead><tr><th>SESSION</th><th>LENGTH</th><th>TRADING</th><th>PER HOUR</th><th>OTHER SALES</th><th>SOLD</th></tr></thead><tbody>${sessions}</tbody></table>` : ""}</section>
    <section class="tr-panel wide"><h4>ROUTES YOU'VE FLOWN</h4>${routes ? `<table class="tr-table"><thead><tr><th>COMMODITY</th><th>BOUGHT AT</th><th>SOLD AT</th><th>RUNS</th><th>CARRIED</th><th>PER T</th><th>PROFIT</th></tr></thead><tbody>${routes}</tbody></table>` : `<p class="tr-dim">None in this range.</p>`}</section>
    <section class="tr-panel wide"><h4>WHERE YOU SELL</h4>${stations ? `<table class="tr-table"><thead><tr><th>STATION</th><th>SALES</th><th>SOLD</th><th>INCOME</th><th>TRADING PROFIT</th></tr></thead><tbody>${stations}</tbody></table>` : `<p class="tr-dim">None in this range.</p>`}</section>
    <section class="tr-panel wide"><h4>EVERY TRADE (LATEST ${(s.recent || []).length})</h4>${trades ? `<table class="tr-table"><thead><tr><th>WHEN (UTC)</th><th></th><th>COMMODITY</th><th>AMOUNT</th><th>PRICE</th><th>TOTAL</th><th>PROFIT</th><th>STATION</th></tr></thead><tbody>${trades}</tbody></table>` : `<p class="tr-dim">No trades yet.</p>`}</section>`;
}

// -- render & events -----------------------------------------------------------
export function renderTrading(data, ui) {
  const root = ui.byId("trading-workspace");
  if (!root) return;
  root.classList.remove("loading-panel");
  const esc = ui.escapeHtml;
  if (!data.ready) {
    root.innerHTML = `<div class="tr-empty"><b>OPENING YOUR TRADING RECORD</b></div>`;
    return;
  }
  const where = data.where || {};
  const status = `<div class="tr-status"><div><b>WHERE</b><span>${esc(where.station || "In flight")}${where.system ? ` · ${esc(where.system)}` : ""}</span></div>
    <div><b>HOLD</b><span>${count(where.cargo_capacity)} t</span></div><div><b>CREDITS</b><span>${where.credits != null ? cr(where.credits) : "—"}</span></div>
    <div><b>SPANSH</b><span>${data.online ? "Searches on request" : `Off <button type="button" class="tr-link" data-page="settings" data-settings-section="integrations">turn on</button>`}</span></div></div>`;
  const tabs = `<nav class="co-tabs tr-tabs">${VIEWS.map(([id, label]) => `<button type="button" class="${data.view === id ? "active" : ""}" data-trade-op="view" data-view="${id}">${label}${id === "route" && data.followed && !data.followed.done ? " <small>●</small>" : ""}</button>`).join("")}</nav>`;
  const messages = `${data.error ? `<p class="co-error">${esc(data.error)}</p>` : ""}${data.notice ? `<p class="co-notice">${esc(data.notice)}</p>` : ""}`;
  const body = {overview, route: routeView, cargo: cargoView, find: findView, station: stationView, history: historyView}[data.view] || overview;
  tips = [];
  root.innerHTML = `${status}${messages}${tabs}<div class="tr-body">${body(data, ui)}</div>`;
  bindCharts(root);
  tickElapsed();
}

const snake = (key) => key.replace(/[A-Z]/g, (char) => `_${char.toLowerCase()}`);

export function handleTradingClick(event, ui) {
  if (!event.target.closest?.('[data-page-name="trading"]')) return false;
  const button = event.target.closest("[data-trade-op]");
  if (!button || button.disabled) return false;
  event.preventDefault();
  const extra = {};
  for (const [key, value] of Object.entries(button.dataset)) {
    if (key !== "tradeOp") extra[snake(key)] = value;
  }
  // These refill the route form, so a half-typed draft must not cover them.
  if (["form_reset", "plan_from", "pick_station"].includes(button.dataset.tradeOp)) delete drafts.route;
  send(ui, button.dataset.tradeOp, extra);
  return true;
}

function formValues(form) {
  const values = {};
  for (const element of form.elements) {
    if (!element.name) continue;
    values[element.name] = element.type === "checkbox" ? (element.checked ? 1 : 0) : element.value;
  }
  return values;
}

export function handleTradingSubmit(event, ui) {
  const form = event.target.closest?.("[data-trade-form]");
  if (!form || !ui.byId("trading-workspace")?.contains(form)) return false;
  event.preventDefault();
  const name = form.dataset.tradeForm;
  delete drafts[name === "plan" ? "route" : name];
  send(ui, name, formValues(form));
  return true;
}

export function handleTradingInput(event, ui) {
  const form = event.target.closest?.("[data-trade-form]");
  if (!form || !ui.byId("trading-workspace")?.contains(form) || !event.target.name) return false;
  const key = form.dataset.tradeForm === "plan" ? "route" : form.dataset.tradeForm;
  drafts[key] = {...(drafts[key] || {}), [event.target.name]: event.target.type === "checkbox" ? (event.target.checked ? 1 : 0) : event.target.value};
  if (event.target.name === "whole_system") {
    // From any station in the system: the station isn't needed (5.5.3.4).
    const whole = event.target.checked;
    const station = form.querySelector("[data-tr-station]");
    if (station) {
      station.disabled = whole;
      station.required = !whole;
      station.previousElementSibling.textContent = whole ? "FROM STATION (ANY)" : "FROM STATION";
    }
    const tries = form.querySelector("[data-tr-try]");
    if (tries) tries.hidden = !whole;
  }
  return true;
}

// Running times tick here, between snapshots.
function tickElapsed() {
  document.querySelectorAll("#trading-workspace [data-tr-since]").forEach((node) => {
    const seconds = Math.max(0, Math.round(Date.now() / 1000 - n(node.dataset.trSince)));
    node.textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  });
}
window.setInterval(tickElapsed, 1000);

export function resetTrading() {
  Object.keys(drafts).forEach((key) => delete drafts[key]);
}
