// Mining (5.5.12): asteroid and Rhino mining on one page. The live run
// changes with what you're mining in; FIND looks for rings and Rhino ground,
// SELL prices your haul, RECORD is all your mining from the journals.

// An arrowhead, not a triangle: an equilateral ▲ turned 60° reads as ▼.
const ARROW = '<svg viewBox="0 0 20 20"><path d="M10 1.5 L15.5 17.5 L10 13.5 L4.5 17.5 Z"/></svg>';
const VIEWS = [["live", "LIVE RUN"], ["find", "FIND"], ["sell", "SELL"], ["record", "RECORD"]];
// Ship and Rhino, wherever they're charted: the deck's validated pair (trading.css).
const SHIP = "var(--mn-s1)", RHINO = "var(--mn-s2)";
const DECISIONS = {MINE: "go", CORE: "go", OPTIONAL: "maybe", SKIP: "stop", ASSESS: "wait"};
const DOING = {
  rhino: "In the Rhino", srv: "In an SRV", foot: "On foot", docked: "Docked", field: "In a ring",
  planet: "On a planet", flight: "In flight",
};

const n = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
const known = (value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
const whole = (value) => Math.round(n(value)).toLocaleString("en-GB");
const tonnes = (value) => `${whole(value)} t`;
const credits = (value) => {
  const v = n(value), abs = Math.abs(v);
  return abs >= 1e9 ? `${(v / 1e9).toFixed(2)}B` : abs >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : abs >= 1e3 ? `${(v / 1e3).toFixed(0)}K` : `${Math.round(v)}`;
};
const cr = (value) => `${credits(value)} CR`;
const percent = (value, digits = 1) => `${n(value).toFixed(digits)}%`;
const distance = (metres) => n(metres) >= 1000 ? `${(n(metres) / 1000).toFixed(n(metres) >= 10000 ? 0 : 1)} km` : `${Math.round(n(metres))} m`;

function clock(seconds) {
  const total = Math.max(0, Math.round(n(seconds)));
  const h = Math.floor(total / 3600), m = Math.floor(total % 3600 / 60), s = total % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}

function since(seconds) {
  const minutes = Math.max(0, Math.floor(n(seconds) / 60));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return hours < 48 ? `${hours} h ${minutes % 60} min` : `${Math.floor(hours / 24)} days`;
}

function ago(ts) {
  if (!ts) return "";
  const seconds = Date.now() / 1000 - n(ts);
  if (seconds < 120) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} days ago`;
}

const monthLabel = (key) => {
  const [year, month] = String(key).split("-").map(Number);
  return new Date(Date.UTC(year, (month || 1) - 1, 1)).toLocaleString("en-GB", {month: "short", year: "2-digit", timeZone: "UTC"});
};

// Every month from the first to the last, quiet ones too, so time reads evenly.
function everyMonth(rows, blank) {
  const keyed = new Map((rows || []).map((row) => [row.month, row]));
  const keys = [...keyed.keys()].sort();
  if (!keys.length) return [];
  const out = [];
  let [year, month] = keys[0].split("-").map(Number);
  const [endYear, endMonth] = keys[keys.length - 1].split("-").map(Number);
  while (year < endYear || (year === endYear && month <= endMonth)) {
    const key = `${year}-${String(month).padStart(2, "0")}`;
    out.push(keyed.get(key) || {month: key, ...blank});
    month += 1;
    if (month > 12) { month = 1; year += 1; }
  }
  return out;
}

let view = "live";
let last = null;
let drawn = "";
let lastUi = null;
let tips = [];
let confirming = {key: "", until: 0};
// Form drafts survive a redraw until they are sent.
const drafts = {};
const field = (form, name, value) => (drafts[form] && name in drafts[form] ? drafts[form][name] : value);

function send(ui, operation, extra = {}) {
  return ui.command("workspace", {page: "mining", operation, ...extra});
}

// -- small pieces -------------------------------------------------------------------
// A running clock is drawn from the run's fixed start and filled in by the
// tick, so its markup stays the same from one snapshot to the next.
function runClock(session, live) {
  const started = n(session?.started) / 1000;
  if (live && started > 0) return `<time data-mn-since="${started}" data-mn-live="1"></time>`;
  return `<time>${clock(session?.duration)}</time>`;
}

function panel(title, body, {note = "", wide = false, cls = ""} = {}) {
  return `<section class="mn-panel${wide ? " wide" : ""}${cls ? ` ${cls}` : ""}"><header><h4>${title}</h4>${note ? `<span>${note}</span>` : ""}</header>${body}</section>`;
}

function tile(label, value, detail = "") {
  return `<div class="mn-tile"><span>${label}</span><b>${value}</b>${detail ? `<small>${detail}</small>` : ""}</div>`;
}

function empty(text) {
  return `<p class="mn-dim">${text}</p>`;
}

function holdBar(hold, esc) {
  const capacity = Math.max(0, n(hold.capacity)), used = n(hold.used);
  const share = capacity ? Math.min(1, used / capacity) : 0;
  const state = hold.partial ? "partial" : share >= 1 ? "full" : share >= 0.9 ? "nearly" : "";
  const free = hold.partial ? "this trip" : share >= 1 ? "FULL" : `${whole(hold.free)} t free`;
  return `<div class="mn-hold ${state}"><span>${esc(hold.name)}</span><i><b style="width:${(share * 100).toFixed(1)}%"></b></i><em>${hold.partial ? "+" : ""}${whole(used)} / ${whole(capacity)} t</em><small>${free}</small></div>`;
}

function confirmButton(key, label, op, extra, esc) {
  const armed = confirming.key === key && Date.now() < confirming.until;
  const data = Object.entries(extra || {}).map(([k, v]) => ` data-${k}="${esc(String(v))}"`).join("");
  return `<button type="button" class="danger-action mn-danger${armed ? " armed" : ""}" data-mine-op="${op}" data-confirm-key="${esc(key)}"${data}>${armed ? "SURE? CLICK AGAIN" : label}</button>`;
}

const attr = (text) => String(text).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

function options(list, selected, blank) {
  return `${blank ? `<option value="">${blank}</option>` : ""}${(list || []).map((value) => {
    const [key, label] = Array.isArray(value) ? value : [value, value];
    return `<option value="${attr(key)}"${String(key) === String(selected) ? " selected" : ""}>${attr(label)}</option>`;
  }).join("")}`;
}

// -- charts -------------------------------------------------------------------------
function niceMax(value) {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  return [1, 2, 2.5, 5, 10].map((step) => step * power).find((step) => step >= value) || value;
}

function chartBox(svg, label, legend = "") {
  return `<div class="mn-chart-box">${svg.replace("<svg", `<svg role="img" aria-label="${label}"`)}<div class="mn-tooltip" hidden></div></div>${legend}`;
}

const legend = (rows) => `<ul class="mn-legend">${rows.map(([colour, text]) => `<li><i style="background:${colour}"></i>${text}</li>`).join("")}</ul>`;

// Tonnes a month, ship and Rhino stacked.
function monthChart(months) {
  const rows = everyMonth(months, {ship: 0, rhino: 0}).slice(-24);
  if (!rows.some((row) => n(row.ship) + n(row.rhino))) return empty("No mining in your journals yet.");
  const W = 760, H = 210, L = 52, R = 12, T = 12, B = 26;
  const top = niceMax(Math.max(...rows.map((row) => n(row.ship) + n(row.rhino))));
  const y = (v) => T + (top - v) / top * (H - T - B);
  const slot = (W - L - R) / rows.length, bar = Math.max(2, Math.min(34, slot - 4));
  const marks = [];
  for (let i = 0; i <= 4; i += 1) {
    const v = top * i / 4;
    marks.push(`<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text class="axis" x="${L - 6}" y="${(y(v) + 3).toFixed(1)}" text-anchor="end">${whole(v)}</text>`);
  }
  const every = Math.ceil(rows.length / 10);
  const offset = tips.length;
  rows.forEach((row, index) => {
    const x = L + index * slot + (slot - bar) / 2;
    const ship = n(row.ship), rhino = n(row.rhino);
    if (ship) marks.push(`<rect x="${x.toFixed(1)}" y="${y(ship).toFixed(1)}" width="${bar.toFixed(1)}" height="${Math.max(1, y(0) - y(ship)).toFixed(1)}" rx="${Math.min(4, bar / 3).toFixed(1)}" style="fill:${SHIP}"/>`);
    if (rhino) {
      const y1 = y(ship + rhino), y0 = y(ship) - (ship ? 2 : 0);
      marks.push(`<rect x="${x.toFixed(1)}" y="${y1.toFixed(1)}" width="${bar.toFixed(1)}" height="${Math.max(1, y0 - y1).toFixed(1)}" rx="${Math.min(4, bar / 3).toFixed(1)}" style="fill:${RHINO}"/>`);
    }
    if (index % every === 0) marks.push(`<text class="axis" x="${(x + bar / 2).toFixed(1)}" y="${H - 8}" text-anchor="middle">${monthLabel(row.month)}</text>`);
    tips.push({head: monthLabel(row.month), lines: [[SHIP, `Ship ${tonnes(ship)}`], [RHINO, `Rhino ${tonnes(rhino)}`], ["", `Together ${tonnes(ship + rhino)}`]]});
    marks.push(`<rect class="hit" data-tip="${offset + index}" x="${(L + index * slot).toFixed(1)}" y="${T}" width="${slot.toFixed(1)}" height="${H - T - B}"/>`);
  });
  return chartBox(`<svg class="mn-chart" viewBox="0 0 ${W} ${H}">${marks.join("")}</svg>`, "Tonnes mined each month, ship and Rhino",
    legend([[SHIP, "Ship (asteroids)"], [RHINO, "Rhino (planets)"]]));
}

// Mining income a month, one series.
function incomeChart(months) {
  const rows = everyMonth(months, {credits: 0}).slice(-24);
  if (!rows.some((row) => n(row.credits))) return empty("Sell something you mined and it shows here.");
  const W = 760, H = 170, L = 52, R = 12, T = 12, B = 26;
  const top = niceMax(Math.max(...rows.map((row) => n(row.credits))));
  const y = (v) => T + (top - v) / top * (H - T - B);
  const slot = (W - L - R) / rows.length, bar = Math.max(2, Math.min(34, slot - 4));
  const marks = [0, 0.5, 1].map((f) => top * f).map((v) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text class="axis" x="${L - 6}" y="${(y(v) + 3).toFixed(1)}" text-anchor="end">${credits(v)}</text>`);
  const every = Math.ceil(rows.length / 10);
  const offset = tips.length;
  rows.forEach((row, index) => {
    const x = L + index * slot + (slot - bar) / 2;
    if (n(row.credits)) marks.push(`<rect x="${x.toFixed(1)}" y="${y(n(row.credits)).toFixed(1)}" width="${bar.toFixed(1)}" height="${Math.max(1, y(0) - y(n(row.credits))).toFixed(1)}" rx="${Math.min(4, bar / 3).toFixed(1)}" style="fill:${SHIP}"/>`);
    if (index % every === 0) marks.push(`<text class="axis" x="${(x + bar / 2).toFixed(1)}" y="${H - 8}" text-anchor="middle">${monthLabel(row.month)}</text>`);
    tips.push({head: monthLabel(row.month), lines: [["", cr(row.credits)]]});
    marks.push(`<rect class="hit" data-tip="${offset + index}" x="${(L + index * slot).toFixed(1)}" y="${T}" width="${slot.toFixed(1)}" height="${H - T - B}"/>`);
  });
  return chartBox(`<svg class="mn-chart" viewBox="0 0 ${W} ${H}">${marks.join("")}</svg>`, "Mining income each month");
}

// The last rocks prospected, oldest on the left: each bar the target's share,
// the line your minimum. Rocks below it are faded and say so on hover.
function gradeChart(prospects, minimum, target) {
  const rows = (prospects || []).slice(0, 24).reverse();
  if (!rows.length) return empty("Fire a prospector limpet: each rock you check lands here.");
  const W = 760, H = 150, L = 40, R = 10, T = 10, B = 18;
  const top = Math.max(10, niceMax(Math.max(n(minimum), ...rows.map((row) => n(row.target_percent)))));
  const y = (v) => T + (top - Math.min(top, v)) / top * (H - T - B);
  const slot = (W - L - R) / Math.max(rows.length, 12), bar = Math.max(4, Math.min(26, slot - 4));
  const marks = [0, top / 2, top].map((v) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text class="axis" x="${L - 6}" y="${(y(v) + 3).toFixed(1)}" text-anchor="end">${whole(v)}%</text>`);
  const offset = tips.length;
  rows.forEach((row, index) => {
    const x = L + index * slot + (slot - bar) / 2;
    const value = row.motherlode ? top : n(row.target_percent);
    const low = !row.motherlode && value < n(minimum);
    const height = value > 0 ? Math.max(1, y(0) - y(value)) : 3;
    marks.push(`<rect class="${low ? "low" : ""}" x="${x.toFixed(1)}" y="${(y(0) - height).toFixed(1)}" width="${bar.toFixed(1)}" height="${height.toFixed(1)}" rx="${Math.min(4, bar / 3, height / 2).toFixed(1)}" style="fill:${SHIP}"/>`);
    tips.push({head: row.decision || "ASSESS", lines: [["", row.motherlode ? `Motherlode: ${row.motherlode}` : `${row.target || target || "Target"} ${percent(row.target_percent)}`],
      ["", low ? `Below your ${percent(minimum, 0)} minimum` : `${tonnes(row.refined)} refined after it`]]});
    marks.push(`<rect class="hit" data-tip="${offset + index}" x="${(L + index * slot).toFixed(1)}" y="${T}" width="${slot.toFixed(1)}" height="${H - T - B}"/>`);
  });
  if (n(minimum) > 0) marks.push(`<line class="threshold" x1="${L}" x2="${W - R}" y1="${y(n(minimum)).toFixed(1)}" y2="${y(n(minimum)).toFixed(1)}"/>`);
  return chartBox(`<svg class="mn-chart" viewBox="0 0 ${W} ${H}">${marks.join("")}</svg>`, "Target share of the last rocks prospected");
}

function bindCharts(root) {
  root.querySelectorAll(".mn-chart-box").forEach((box) => {
    const tip = box.querySelector(".mn-tooltip");
    const svg = box.querySelector("svg");
    if (!tip || !svg) return;
    svg.addEventListener("mousemove", (event) => {
      const hit = event.target.closest?.(".hit");
      const data = hit && tips[n(hit.dataset.tip)];
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
      tip.style.left = `${Math.max(4, Math.min(rect.width - tip.offsetWidth - 4, event.clientX - rect.left + 14))}px`;
    });
    svg.addEventListener("mouseleave", () => {
      tip.hidden = true;
      svg.querySelectorAll(".hit.on").forEach((node) => node.classList.remove("on"));
    });
  });
}

// -- the plan, shared by both kinds of run --------------------------------------------
function planPanel(data, esc) {
  const plan = data.plan || {};
  const surface = (data.where || {}).mode === "rhino";
  const materials = surface ? data.surface_materials : data.ring_materials;
  const methods = [["auto", "Work it out"], ["laser", "Laser"], ["core", "Core (motherlodes)"], ["subsurface", "Sub-surface"], ["surface", "Rhino / surface"]];
  const run = data.active
    ? `<button type="button" data-mine-op="end_run">END THIS RUN</button>`
    : `<button type="button" data-mine-op="start_run">START A RUN</button>`;
  return panel("THE PLAN", `<form class="mn-form" data-mine-form="plan">
      <label>TARGET<select name="target">${options(materials || [], field("plan", "target", plan.target || ""), "Anything worth it")}</select></label>
      <label>MINIMUM %<input name="minimum" type="number" min="0" max="100" step="0.5" value="${esc(String(field("plan", "minimum", n(plan.minimum) || 20)))}"></label>
      <label>FILL TO (T)<input name="cargo_goal" type="number" min="0" max="100000" value="${esc(String(field("plan", "cargo_goal", n(plan.cargo_goal))))}" placeholder="0 = the hold"></label>
      <label>METHOD<select name="method">${options(methods, field("plan", "method", plan.method || "auto"))}</select></label>
      <div class="mn-actions"><button type="submit" class="primary">SAVE PLAN</button>${run}</div>
    </form><p class="mn-dim">Runs start by themselves when you prospect, refine or launch a limpet, and end when you dock the Rhino or log off.</p>`);
}

// -- LIVE: asteroids ------------------------------------------------------------------
function rockPanel(data, esc) {
  const current = (data.session || {}).current || {};
  const plan = data.plan || {};
  const decision = String(current.decision || "ASSESS").toUpperCase();
  const materials = (current.materials || []).slice().sort((a, b) => n(b.percent) - n(a.percent));
  const minimum = n(plan.minimum);
  const bars = materials.map((row) => {
    const isTarget = plan.target && String(row.name).toLowerCase() === String(plan.target).toLowerCase();
    return `<li class="${isTarget ? "target" : ""}"><span>${esc(row.name)}${isTarget ? " <em>TARGET</em>" : ""}</span><i><b style="width:${Math.min(100, n(row.percent)).toFixed(1)}%"></b>${isTarget && minimum ? `<u style="left:${Math.min(100, minimum)}%"></u>` : ""}</i><strong>${percent(row.percent)}</strong></li>`;
  }).join("");
  const content = String(current.content || "").replace(/^Material Content:\s*/i, "");
  const body = materials.length || current.motherlode
    ? `<div class="mn-verdict ${DECISIONS[decision] || "wait"}"><b>${esc(decision === "CORE" ? "CRACK IT" : decision)}</b><span>${esc(current.motherlode ? `${current.motherlode} motherlode` : current.target ? `${current.target} ${percent(current.target_percent)}` : "No target set: judge it yourself")}</span></div>
       <div class="mn-facts"><span>CONTENT <b>${esc(content || "—")}</b></span><span>LEFT <b>${known(current.remaining) ? percent(current.remaining, 0) : "—"}</b></span><span>SINCE <b>${tonnes(current.refined_since_prospect)}</b></span></div>
       <ul class="mn-grades">${bars}</ul>`
    : empty("Fire a prospector limpet at a rock: what's in it, and whether it's worth it, shows here.");
  return panel("THIS ROCK", body, {cls: "mn-rock"});
}

function runTiles(data) {
  const session = data.session || {};
  const holds = data.holds || [];
  const ship = holds.find((row) => row.name === "SHIP") || {};
  const rate = n(session.tons_per_hour);
  const free = n(ship.free);
  const fullIn = rate > 0 && free > 0 ? `full in ~${clock(free / rate * 3600)}` : free === 0 && ship.capacity ? "hold full" : "";
  const value = (session.yield || []).reduce((sum, row) => sum + Math.max(0, n(row.count)) * priceOf(data, row.name), 0);
  return `<div class="mn-tiles">
    ${tile("TIME", runClock(session, data.active), data.active ? "running" : "last run")}
    ${tile("REFINED", tonnes(session.refined_t), rate ? `${rate.toFixed(1)} t an hour` : "")}
    ${tile("ROCKS", whole(session.prospected), known(session.hit_rate) ? `${percent(session.hit_rate, 0)} had your target` : "")}
    ${tile("LIMPETS", whole(data.limpets), session.limpets?.limpets_per_tonne ? `${n(session.limpets.limpets_per_tonne).toFixed(2)} a tonne` : "in the hold")}
    ${tile("HOLD", ship.capacity ? `${whole(ship.used)} / ${whole(ship.capacity)} t` : "—", fullIn)}
    ${tile("WORTH ABOUT", value ? cr(value) : "—", value ? "at what you've been paid" : "")}
  </div>`;
}

function priceOf(data, name) {
  const key = String(name || "").toLowerCase();
  const mine = (data.income?.prices || []).find((row) => String(row.name).toLowerCase() === key);
  if (mine?.avg) return n(mine.avg);
  const haul = (data.haul || []).find((row) => String(row.name).toLowerCase() === key);
  return n(haul?.each);
}

function yieldPanel(data, esc) {
  const rows = (data.session?.yield || []).filter((row) => n(row.count) || n(row.cargo_delta));
  if (!rows.length) return panel("REFINED THIS RUN", empty("Nothing refined yet."));
  const body = `<table class="mn-table"><thead><tr><th>MATERIAL</th><th>REFINED</th><th>WORTH ABOUT</th></tr></thead><tbody>${rows.map((row) => {
    const each = priceOf(data, row.name);
    return `<tr><td>${esc(row.name)}</td><td>${tonnes(row.count || row.cargo_delta)}</td><td>${each ? cr(each * n(row.count || row.cargo_delta)) : "—"}</td></tr>`;
  }).join("")}</tbody></table>`;
  return panel("REFINED THIS RUN", body);
}

function shipPanel(data, esc) {
  const readiness = data.readiness || {};
  const labels = {refinery: "Refinery", prospector: "Prospector limpets", collector: "Collector limpets", laser: "Mining laser",
    seismic: "Seismic charges", abrasion: "Abrasion blaster", subsurface: "Sub-surface missiles", dss: "Surface scanner"};
  const kit = Object.entries(readiness.equipment || {}).filter(([key]) => labels[key])
    .map(([key, present]) => `<li class="${present ? "yes" : "no"}"><i>${present ? "✓" : "✕"}</i>${labels[key]}</li>`).join("");
  const missing = (readiness.missing || []).length ? `<p class="mn-warn">Missing: ${(readiness.missing || []).map(esc).join(", ")}</p>` : "";
  return panel("YOUR SHIP", `<p class="mn-sub">${esc(readiness.ship || "Waiting for your loadout")} · ${tonnes(readiness.cargo_capacity)} hold</p><ul class="mn-kit">${kit || "<li>Your loadout shows here once the game sends it.</li>"}</ul>${missing}${readiness.dss_recommended ? `<p class="mn-dim">A detailed surface scanner shows a ring's hotspots.</p>` : ""}`);
}

function asteroidLive(data, esc) {
  const session = data.session || {};
  return `<div class="mn-grid">${rockPanel(data, esc)}${panel("THIS RUN", runTiles(data))}</div>
    ${panel("THE LAST ROCKS", gradeChart(session.prospects, data.plan?.minimum, data.plan?.target), {note: `oldest on the left${n(data.plan?.minimum) ? ` · dashed line: your ${percent(data.plan.minimum, 0)} minimum` : ""}`, wide: true})}
    <div class="mn-grid">${yieldPanel(data, esc)}${planPanel(data, esc)}</div>
    ${shipPanel(data, esc)}`;
}

// -- LIVE: the Rhino --------------------------------------------------------------------
function rigsPanel(data, esc) {
  const rigs = data.rigs || {};
  const rows = (rigs.rigs || []).slice().sort((a, b) => n(a.slot) - n(b.slot));
  const where = esc(rigs.body || data.where?.body || "this planet");
  if (!rows.length) {
    return panel(`RIGS ON ${where.toUpperCase()}`, `${empty("No rigs marked here. Press the rig key (Ctrl+Alt+1 for rig 1, up to 6) as you deploy each one, and again as you collect it.")}
      ${(rigs.elsewhere || []).length ? `<p class="mn-dim">Rigs left elsewhere: ${(rigs.elsewhere || []).map((row) => `${esc(row.body)} (#${row.rigs.join(", #")})`).join(" · ")}</p>` : ""}`);
  }
  const list = rows.map((row) => `<li class="${row.here ? "here" : row.nearest ? "nearest" : ""}"><b>#${row.slot}</b>
      <i class="mn-arrow" style="transform:rotate(${n(row.relative).toFixed(0)}deg)" aria-hidden="true">${ARROW}</i>
      <span>${row.here ? "HERE" : distance(row.distance_m)}</span><small>down ${since(row.age_s)}</small></li>`).join("");
  const order = (rigs.collect_order || []).length > 1 ? `<p class="mn-order">COLLECT ▸ ${(rigs.collect_order || []).map((slot) => `#${slot}`).join(" → ")}</p>` : "";
  return panel(`RIGS ON ${where.toUpperCase()}`, `<ul class="mn-rigs">${list}</ul>${order}<div class="mn-actions">${confirmButton("rigs", "FORGET THE RIGS HERE", "forget_rigs", {}, esc)}</div>`,
    {note: `${rows.length} out · arrows point from where you face`});
}

function groundPanel(data, esc) {
  const ground = data.ground;
  if (!ground) return panel("THIS GROUND", empty("Scan the planet you're on (FSS, or the surface scanner) to see what its ground tends to hold."));
  const rows = (ground.expected_materials || []).slice().sort((a, b) => n(b.pct) - n(a.pct)).slice(0, 10);
  const list = rows.map((row) => `<li><span>${esc(row.material)}</span><i><b style="width:${Math.min(100, n(row.pct)).toFixed(1)}%"></b></i><strong>${percent(row.pct, 0)}</strong><small>${row.median ? `${cr(row.median)} a t` : ""}</small></li>`).join("");
  return panel("THIS GROUND", `<p class="mn-sub"><b>${esc(ground.ground_label)}</b>${known(ground.gravity) ? ` · ${n(ground.gravity).toFixed(2)} g` : ""}</p>
    <ul class="mn-ground">${list}</ul>
    <p class="mn-dim">How often each turns up at a mining site on this kind of ground, and its usual price, from ${whole(ground.ground_sample)} sites charted by EDRhinoSpotter's community sheet. A guide, not a promise.</p>`);
}

function sitesPanel(data, esc) {
  const sites = data.sites || [];
  const body = sites.length
    ? `<ul class="mn-list">${sites.map((row) => `<li><b>${esc(row.name || `Site ${row.location ?? ""}`)}</b><span>${esc((row.materials || []).join(", ") || "Materials not noted")}</span><em>${row.depleted ? "DEPLETED" : esc(row.estimate || row.amount || "")}</em></li>`).join("")}</ul>`
    : empty("No sites saved on this planet.");
  return panel("YOUR SITES HERE", `${body}<div class="mn-actions"><button type="button" data-page="planet-materials">OPEN MATERIALS &amp; SITES</button></div>`);
}

function rhinoLive(data, esc) {
  const session = data.session || {};
  const holds = (data.holds || []).map((hold) => holdBar(hold, esc)).join("");
  const tiles = `<div class="mn-tiles">
    ${tile("TIME", runClock(session, data.active), data.active ? "running" : "last run")}
    ${tile("HAULED", tonnes(session.refined_t), n(session.tons_per_hour) ? `${n(session.tons_per_hour).toFixed(1)} t an hour` : "")}
    ${tile("TO THE SHIP", tonnes(session.cargo_removed_t), "moved out of the Rhino")}
    ${data.srv_fuel ? tile("FUEL", known(data.srv_fuel.percent) ? `${Math.round(n(data.srv_fuel.percent))}%` : known(data.srv_fuel.tonnes) ? `${n(data.srv_fuel.tonnes).toFixed(2)} t` : "—",
      known(data.srv_fuel.percent) ? (n(data.srv_fuel.percent) <= 25 ? "low: head for the ship" : "in the Rhino's tank") : "learning the tank's size") : ""}
  </div>`;
  return `<div class="mn-grid">${rigsPanel(data, esc)}${panel("HOLDS", `${holds || empty("Waiting for your cargo.")}${tiles}`)}</div>
    <div class="mn-grid">${groundPanel(data, esc)}${yieldPanel(data, esc)}</div>
    <div class="mn-grid">${sitesPanel(data, esc)}${planPanel(data, esc)}</div>`;
}

function standby(data, esc) {
  const history = data.history || [];
  const lastRun = history[0];
  const lastText = lastRun ? `<p class="mn-sub">Last run: <b>${esc(lastRun.system || "somewhere")}</b> · ${tonnes(lastRun.refined)} in ${clock(lastRun.duration)}${lastRun.tons_per_hour ? ` · ${n(lastRun.tons_per_hour).toFixed(1)} t an hour` : ""} · ${ago(n(lastRun.ended || lastRun.started) / 1000)}</p>` : "";
  const how = `<div class="mn-how"><div><b>IN A RING</b><span>Prospect a rock and this page reads it: what's in it, whether it beats your minimum, how fast you're filling up.</span></div>
    <div><b>IN THE RHINO</b><span>Deploy the Rhino and this page follows your rigs, both holds and what the ground tends to hold.</span></div></div>`;
  return `${panel("NO RUN GOING", `${lastText}${how}`, {wide: true})}<div class="mn-grid">${planPanel(data, esc)}${shipPanel(data, esc)}</div>`;
}

function liveView(data, esc) {
  const mode = data.where?.mode;
  if (mode === "rhino" || (data.active && data.session?.mode === "surface")) return rhinoLive(data, esc);
  if (data.active || mode === "field") return asteroidLive(data, esc);
  return standby(data, esc);
}

// -- FIND -------------------------------------------------------------------------------
function ringFinder(data, esc) {
  const tools = data.tools || {};
  const rows = tools.ring_results || [];
  const form = `<form class="mn-form" data-mine-form="rings">
    <label>NEAR<input name="reference" value="${esc(field("rings", "reference", data.system || ""))}" required></label>
    <label>MINERAL<select name="material">${options(data.ring_materials || [], field("rings", "material", ""), "Any")}</select></label>
    <label>RING<select name="ring_type">${options(["Metallic", "Metal Rich", "Rocky", "Icy"], field("rings", "ring_type", ""), "Any")}</select></label>
    <label>WITHIN (LY)<input name="range" type="number" min="1" max="5000" value="${esc(String(field("rings", "range", 300)))}"></label>
    <div class="mn-actions"><button type="submit" class="primary"${tools.ring_status === "working" ? " disabled" : ""}>${tools.ring_status === "working" ? "SEARCHING…" : "FIND RINGS"}</button>${rows.length || tools.ring_detail || tools.ring_status === "working" ? `<button type="button" data-mine-op="ring_clear" data-clears="rings">CLEAR</button>` : ""}</div></form>`;
  const table = rows.length ? `<table class="mn-table"><thead><tr><th>RING</th><th>MINERAL</th><th>HOTSPOTS</th><th>DISTANCE</th><th></th></tr></thead><tbody>${rows.map((row, index) => `<tr>
      <td><b>${esc(row.body || row.system)}</b><small>${esc(row.ring_type || "")}${row.reserve ? ` · ${esc(row.reserve)}` : ""} · ${esc(row.source || "")}</small></td>
      <td>${esc(row.material || "—")}</td><td>${row.hotspots ? whole(row.hotspots) : "—"}</td>
      <td>${known(row.distance) ? `${n(row.distance).toFixed(1)} ly` : "—"}<small>${known(row.arrival) ? `${whole(row.arrival)} ls` : ""}</small></td>
      <td class="mn-row-actions"><button type="button" data-mine-op="ring_copy" data-result-index="${index}">COPY</button><button type="button" data-mine-op="ring_bookmark" data-result-index="${index}">SAVE</button><button type="button" data-mine-op="ring_open" data-result-index="${index}">SPANSH</button></td></tr>`).join("")}</tbody></table>` : "";
  const status = tools.ring_detail ? `<p class="mn-dim${tools.ring_status === "failed" ? " mn-error" : ""}">${esc(tools.ring_detail)}</p>` : "";
  return panel("RINGS", `${form}${status}${table}`, {note: "your own surface scans, then Spansh", wide: true});
}

function groundFinder(data, esc) {
  const finder = data.finder || {};
  const grounds = data.grounds || [];
  const material = field("ground", "material", "");
  const suggestions = material ? (data.material_grounds || {})[material] || [] : [];
  const suggest = material ? (suggestions.length
    ? `<ul class="mn-ground pick">${suggestions.slice(0, 6).map((row) => `<li><span>${esc(row.label)}</span><i><b style="width:${Math.min(100, n(row.pct)).toFixed(1)}%"></b></i><strong>${percent(row.pct, 0)}</strong><small>${row.median ? `${cr(row.median)} a t` : ""}</small>${row.searchable ? `<button type="button" data-mine-op="ground_pick" data-ground="${esc(row.ground)}">USE</button>` : ""}</li>`).join("")}</ul>
       <p class="mn-dim">The share of charted sites on each ground where ${esc(material)} turned up (EDRhinoSpotter).</p>`
    : empty(`${esc(material)} hasn't been charted on any ground yet.`)) : "";
  const form = `<form class="mn-form" data-mine-form="ground">
    <label>FOR<select name="material">${options(data.surface_materials || [], material, "Choose a material…")}</select></label>
    <label>GROUND<select name="ground">${options(grounds.map((row) => [row.key, row.label]), field("ground", "ground", finder.ground || grounds[0]?.key || ""))}</select></label>
    <label>NEAR<input name="reference" value="${esc(field("ground", "reference", finder.reference || data.system || ""))}" required></label>
    <label>WITHIN (LY)<input name="range" type="number" min="1" max="5000" value="${esc(String(field("ground", "range", 200)))}"></label>
    <label>GRAVITY UP TO (G)<input name="gravity" type="number" min="0" max="10" step="0.1" value="${esc(String(field("ground", "gravity", "")))}" placeholder="any"></label>
    <label>ARRIVAL UP TO (LS)<input name="max_ls" type="number" min="0" value="${esc(String(field("ground", "max_ls", "")))}" placeholder="any"></label>
    <div class="mn-actions"><button type="submit" class="primary"${finder.status === "working" ? " disabled" : ""}>${finder.status === "working" ? "SEARCHING…" : "FIND PLANETS"}</button>${(finder.results || []).length || finder.detail || material || finder.status === "working" ? `<button type="button" data-mine-op="ground_clear" data-clears="ground">CLEAR</button>` : ""}</div></form>`;
  const rows = finder.results || [];
  const table = rows.length ? `<table class="mn-table"><thead><tr><th>PLANET</th><th>VOLCANISM</th><th>GRAVITY</th><th>DISTANCE</th><th></th></tr></thead><tbody>${rows.map((row, index) => `<tr>
      <td><b>${esc(row.body)}</b></td><td>${esc(row.volcanism || "—")}</td><td>${known(row.gravity) ? `${n(row.gravity).toFixed(2)} g` : "—"}</td>
      <td>${known(row.distance) ? `${n(row.distance).toFixed(1)} ly` : "—"}<small>${known(row.arrival) ? `${whole(row.arrival)} ls` : ""}</small></td>
      <td class="mn-row-actions"><button type="button" data-mine-op="ground_copy" data-result-index="${index}">COPY</button><button type="button" data-mine-op="ground_open" data-result-index="${index}">SPANSH</button></td></tr>`).join("")}</tbody></table>` : "";
  const status = finder.detail ? `<p class="mn-dim${finder.status === "failed" ? " mn-error" : ""}">${esc(finder.detail)}</p>` : "";
  return panel("RHINO GROUND", `${form}${suggest}${status}${table}`, {note: "landable planets of the ground you pick, from Spansh", wide: true});
}

function recordsPanel(data, esc) {
  const rings = (data.ring_scans || []).flatMap((row) => (row.signals || []).map((signal) => `<li><b>${esc(signal.name)}</b><span>${esc(row.body)}</span><em>${whole(signal.count)} hotspot${n(signal.count) === 1 ? "" : "s"}</em></li>`));
  const planets = (data.surface_scans || []).map((row) => `<li><b>${esc(row.body || "Planet")}</b><span>${esc(row.system || "")}</span><em>${whole(row.mining_locations)} mining site${n(row.mining_locations) === 1 ? "" : "s"}</em></li>`);
  const saved = (data.bookmarks || []).map((row) => `<li><b>${esc(row.body || row.system)}</b><span>${esc(row.material || "Any mineral")}${row.notes ? ` · ${esc(row.notes)}` : ""}</span><em>${confirmButton(`bookmark-${row.id}`, "REMOVE", "delete_bookmark", {"bookmark-id": row.id}, esc)}</em></li>`);
  return `<div class="mn-grid">
    ${panel("RINGS YOU'VE SCANNED", rings.length ? `<ul class="mn-list">${rings.slice(0, 40).join("")}</ul>` : empty("Map a ring with the surface scanner and its hotspots are kept here."))}
    ${panel("PLANETS WITH MINING SITES", planets.length ? `<ul class="mn-list">${planets.slice(0, 30).join("")}</ul>` : empty("Planets your scans showed mining sites on show here."))}
  </div>${panel("SAVED", saved.length ? `<ul class="mn-list">${saved.join("")}</ul>` : empty("SAVE a ring from the results to keep it here."), {wide: true})}`;
}

function findView(data, esc) {
  return `${ringFinder(data, esc)}${groundFinder(data, esc)}${recordsPanel(data, esc)}`;
}

// -- SELL ---------------------------------------------------------------------------------
function sellView(data, esc) {
  const haul = data.haul || [];
  const total = haul.reduce((sum, row) => sum + n(row.value), 0);
  const haulBody = haul.length ? `<table class="mn-table"><thead><tr><th>CARGO</th><th>SHIP</th><th>RHINO</th><th>EACH</th><th>WORTH ABOUT</th><th></th></tr></thead><tbody>${haul.map((row) => `<tr class="${row.mined ? "" : "dim"}">
      <td><b>${esc(row.name)}</b></td><td>${row.ship ? tonnes(row.ship) : "—"}</td><td>${row.rhino ? tonnes(row.rhino) : "—"}</td>
      <td>${row.each ? cr(row.each) : "—"}<small>${row.source === "yours" ? "what you've had" : row.source === "typical" ? "usual price" : ""}</small></td>
      <td>${row.value ? cr(row.value) : "—"}</td>
      <td class="mn-row-actions"><button type="button" data-mine-op="sell_search" data-commodity="${esc(row.name)}" data-amount="${n(row.ship) + n(row.rhino)}">FIND BUYERS</button></td></tr>`).join("")}</tbody></table>`
    : empty("Your holds are empty.");
  const sell = data.sell || {};
  const best = sell.results || [];
  const nearest = sell.nearest || [];
  const stationRows = (rows, op) => rows.map((row, index) => `<tr><td><b>${esc(row.station)}</b><small>${esc(row.system)}${row.carrier ? " · carrier" : row.planetary ? " · planetary" : ""}</small></td>
      <td>${cr(row.price)}</td><td>${whole(row.stock)}</td><td>${known(row.distance) ? `${n(row.distance).toFixed(1)} ly` : "—"}<small>${known(row.arrival_ls) ? `${whole(row.arrival_ls)} ls` : ""}</small></td>
      <td>${esc(row.pad || "")}</td><td><small>${ago(row.updated)}</small></td>
      <td class="mn-row-actions">${op ? `<button type="button" data-mine-op="${op}" data-result-index="${index}">COPY</button>` : ""}</td></tr>`).join("");
  const head = `<thead><tr><th>STATION</th><th>PAYS</th><th>WANTS</th><th>DISTANCE</th><th>PAD</th><th>PRICES</th><th></th></tr></thead>`;
  const buyers = sell.commodity ? panel(`BUYERS FOR ${esc(String(sell.commodity).toUpperCase())}`,
    `${sell.detail ? `<p class="mn-dim${sell.status === "failed" ? " mn-error" : ""}">${esc(sell.detail)}</p>` : ""}
     ${best.length ? `<h5>BEST PAYERS</h5><table class="mn-table">${head}<tbody>${stationRows(best, "sell_copy")}</tbody></table>` : ""}
     ${nearest.length ? `<h5>NEAREST</h5><table class="mn-table">${head}<tbody>${stationRows(nearest, "")}</tbody></table>` : ""}
     <div class="mn-actions"><button type="button" data-mine-op="sell_clear">CLEAR</button></div>`,
    {note: `within ${whole(sell.radius || data.sell_radius)} ly`, wide: true}) : "";
  const prices = data.income?.prices || [];
  const priceBody = prices.length ? `<table class="mn-table"><thead><tr><th>MATERIAL</th><th>SOLD</th><th>AVERAGE</th><th>BEST</th><th>LAST</th><th>EARNED</th></tr></thead><tbody>${prices.map((row) => `<tr><td><b>${esc(row.name)}</b></td>
      <td>${tonnes(row.sold_t)}</td><td>${cr(row.avg)}</td><td>${cr(row.best)}</td><td>${cr(row.last)}<small>${ago(row.last_at)}</small></td><td>${cr(row.credits)}</td></tr>`).join("")}</tbody></table>`
    : empty("Nothing mined sold yet.");
  const missions = data.missions || [];
  const missionBody = missions.length ? `<ul class="mn-list">${missions.map((row) => `<li><b>${esc(row.commodity)}</b><span>${esc(row.destination || "")}</span><em>${whole(row.delivered)} / ${whole(row.required)} t</em></li>`).join("")}</ul>` : "";
  const near = `<p class="mn-dim">Buyers are searched within your Sell cargo distance (${whole(data.sell_radius)} ly) and market choices, the same as <button type="button" class="mn-link" data-page="trading">Trading › Sell cargo</button>.</p>`;
  return `${panel("YOUR HAUL", `${haulBody}${near}`, {note: total ? `worth about ${cr(total)}` : "", wide: true})}
    ${buyers}
    ${missions.length ? panel("MINING CONTRACTS", missionBody, {wide: true}) : ""}
    ${panel("WHAT YOU'VE BEEN PAID", priceBody, {note: data.income?.total ? `${cr(data.income.total)} in all` : "", wide: true})}`;
}

// -- RECORD -------------------------------------------------------------------------------
function recordView(data, esc) {
  const record = data.record || {};
  const s = record.summary;
  const status = record.status === "reading" ? "Reading your journals…" : record.status === "refreshing" ? "Catching up…" : record.at ? `Read ${ago(record.at)}` : "";
  const refresh = `<div class="mn-head"><span>${esc(status)}</span><button type="button" data-mine-op="record_refresh"${record.status === "reading" || record.status === "refreshing" ? " disabled" : ""}>↻ READ AGAIN</button></div>`;
  if (!s) return `${refresh}${panel("YOUR MINING", empty("Reading every journal for your mining. The first time takes a few seconds."), {wide: true})}`;
  const income = n(data.income?.total);
  const content = s.content || {};
  const limpets = s.limpets || {};
  const tiles = `<div class="mn-tiles big">
    ${tile("MINED IN THE SHIP", tonnes(s.ship_t), "asteroid refining")}
    ${tile("HAULED IN THE RHINO", tonnes(s.rhino_t), `${whole(s.deployments)} Rhino runs`)}
    ${tile("MINING INCOME", income ? cr(income) : "—", "mined cargo sold")}
    ${tile("ROCKS PROSPECTED", whole(s.prospected), `${whole(content.High)} high · ${whole(content.Medium)} medium · ${whole(content.Low)} low`)}
    ${tile("MOTHERLODES", whole((s.motherlodes || []).reduce((sum, row) => sum + n(row.count), 0)), `${whole(s.cracked)} cracked`)}
    ${tile("LIMPETS LAUNCHED", whole(Object.values(limpets).reduce((sum, v) => sum + n(v), 0)), `${whole(limpets.Prospector)} prospectors · ${whole(limpets.Collection)} collectors`)}
    ${tile("DAYS MINING", whole(s.days), s.first ? `since ${new Date(n(s.first) * 1000).toLocaleDateString("en-GB", {day: "numeric", month: "short", year: "numeric"})}` : "")}
    ${tile("RINGS SCANNED", whole(s.rings_scanned), "with the surface scanner")}
  </div>`;
  const materials = s.materials || [];
  const top = Math.max(1, ...materials.map((row) => n(row.ship) + n(row.rhino)));
  const paid = Object.fromEntries((data.income?.prices || []).map((row) => [String(row.name).toLowerCase(), row]));
  const ranks = materials.length ? `<ul class="mn-ranks">${materials.slice(0, 16).map((row) => {
    const ship = n(row.ship), rhino = n(row.rhino), money = paid[String(row.name).toLowerCase()];
    return `<li><span>${esc(row.name)}</span><i title="Ship ${tonnes(ship)} · Rhino ${tonnes(rhino)}">${ship ? `<b style="width:${(ship / top * 100).toFixed(2)}%;background:${SHIP}"></b>` : ""}${rhino ? `<b style="width:${(rhino / top * 100).toFixed(2)}%;background:${RHINO}"></b>` : ""}</i><strong>${tonnes(ship + rhino)}</strong><small>${money ? `${cr(money.credits)} sold` : ""}</small></li>`;
  }).join("")}</ul>${legend([[SHIP, "Ship"], [RHINO, "Rhino"]])}` : empty("Nothing mined yet.");
  const places = (s.places || []).length ? `<ul class="mn-list">${s.places.map((row) => `<li><b>${esc(row.body || row.system)}</b><span>${row.mode === "rhino" ? "Rhino" : "Ship"} · ${esc(row.system)} · ${ago(row.last)}</span><em>${tonnes(row.tonnes)}</em></li>`).join("")}</ul>` : empty("No places yet.");
  const best = (s.best || []).length ? `<ul class="mn-ground">${s.best.map((row) => `<li><span>${esc(row.name)}</span><i><b style="width:${Math.min(100, n(row.percent)).toFixed(1)}%"></b></i><strong>${percent(row.percent)}</strong></li>`).join("")}</ul>` : empty("Prospect a rock to start this list.");
  const history = data.history || [];
  const runs = history.length ? `<table class="mn-table"><thead><tr><th>WHEN</th><th>WHERE</th><th>REFINED</th><th>RATE</th><th>ROCKS</th><th>HIT RATE</th></tr></thead><tbody>${history.slice(0, 30).map((row) => `<tr>
      <td>${row.started ? new Date(n(row.started)).toLocaleDateString("en-GB", {day: "numeric", month: "short"}) : "—"}<small>${clock(row.duration)}</small></td>
      <td><b>${esc(row.system || "—")}</b><small>${esc(row.target || "")}</small></td><td>${tonnes(row.refined)}</td>
      <td>${n(row.tons_per_hour) ? `${n(row.tons_per_hour).toFixed(1)} t/h` : "—"}</td><td>${whole(row.prospected)}</td><td>${known(row.hit_rate) ? percent(row.hit_rate, 0) : "—"}</td></tr>`).join("")}</tbody></table>` : empty("Your last runs show here.");
  return `${refresh}${tiles}
    ${panel("TONNES A MONTH", monthChart(s.months), {wide: true})}
    ${panel("INCOME A MONTH", incomeChart(data.income?.months), {wide: true})}
    <div class="mn-grid">${panel("WHAT YOU'VE MINED", ranks)}${panel("WHERE YOU'VE MINED", places)}</div>
    <div class="mn-grid">${panel("YOUR RICHEST ROCKS", best, {note: "best share seen of each"})}${panel("RECENT RUNS", runs)}</div>`;
}

// -- the page -------------------------------------------------------------------------------
function statusStrip(data, esc) {
  const where = data.where || {};
  const place = where.mode === "docked" ? where.station : where.mode === "field" ? where.field_name : where.body;
  const holds = (data.holds || []).map((hold) => `<span class="mn-mini"><em>${esc(hold.name)}</em>${hold.partial ? "+" : ""}${whole(hold.used)}/${whole(hold.capacity)} t</span>`).join("");
  const session = data.session || {};
  return `<div class="mn-status">
    <div><b>WHERE</b><span>${esc(where.system || "Waiting for your location")}${place ? ` · ${esc(place)}` : ""}</span></div>
    <div><b>DOING</b><span>${esc(where.mode === "field" ? `In a ${where.field === "belt" ? "belt" : where.field === "cluster" ? "rock cluster" : "ring"}` : DOING[where.mode] || "—")}</span></div>
    <div><b>HOLDS</b><span>${holds || "—"}</span></div>
    <div><b>LIMPETS</b><span>${whole(data.limpets)}</span></div>
    <div><b>RUN</b><span>${data.active ? `${session.mode === "surface" ? "Rhino" : "Asteroids"} · ${runClock(session, true)}` : "None going"}</span></div>
  </div>`;
}

export function renderMining(data, ui) {
  const root = ui.byId("mining-workspace");
  if (!root) return;
  last = data || {};
  lastUi = ui;
  root.classList.remove("loading-panel");
  const esc = ui.escapeHtml;
  const tabs = `<nav class="co-tabs mn-tabs">${VIEWS.map(([id, label]) => `<button type="button" class="${view === id ? "active" : ""}" data-mine-op="view" data-view="${id}">${label}${id === "live" && last.active ? " <small>●</small>" : ""}</button>`).join("")}</nav>`;
  const body = {live: liveView, find: findView, sell: sellView, record: recordView}[view] || liveView;
  tips = [];
  const markup = `${statusStrip(last, esc)}${tabs}<div class="mn-body">${body(last, esc)}</div>`;
  // Only redraw what changed to the eye: a redraw closes an open dropdown,
  // drops a chart's tooltip and can swallow a click.
  if (markup === drawn && root.isConnected && root.firstElementChild) return;
  drawn = markup;
  root.innerHTML = markup;
  bindCharts(root);
  tick();
}

const snake = (key) => key.replace(/[A-Z]/g, (char) => `_${char.toLowerCase()}`);

export function handleMiningClick(event, ui) {
  if (!event.target.closest?.('[data-page-name="mining"]')) return false;
  const button = event.target.closest("[data-mine-op]");
  if (!button || button.disabled) return false;
  event.preventDefault();
  const op = button.dataset.mineOp;
  if (op === "view") {
    view = button.dataset.view || "live";
    renderMining(last, ui);
    return true;
  }
  // A cleared search starts its form afresh too.
  if (button.dataset.clears) delete drafts[button.dataset.clears];
  if (op === "ground_pick") {
    drafts.ground = {...(drafts.ground || {}), ground: button.dataset.ground};
    renderMining(last, ui);
    return true;
  }
  if (button.dataset.confirmKey) {
    const key = button.dataset.confirmKey;
    if (confirming.key !== key || Date.now() > confirming.until) {
      confirming = {key, until: Date.now() + 4000};
      renderMining(last, ui);
      setTimeout(() => { if (confirming.key === key && Date.now() > confirming.until) renderMining(last, lastUi); }, 4100);
      return true;
    }
    confirming = {key: "", until: 0};
  }
  const extra = {};
  for (const [key, value] of Object.entries(button.dataset)) {
    if (!["mineOp", "confirmKey"].includes(key)) extra[snake(key)] = value;
  }
  if (button.dataset.confirmKey) extra.confirmed = true;
  send(ui, op, extra);
  return true;
}

function formValues(form) {
  const values = {};
  for (const element of form.elements) {
    if (element.name) values[element.name] = element.type === "checkbox" ? (element.checked ? 1 : 0) : element.value;
  }
  return values;
}

export function handleMiningSubmit(event, ui) {
  const form = event.target.closest?.("[data-mine-form]");
  if (!form || !ui.byId("mining-workspace")?.contains(form)) return false;
  event.preventDefault();
  const name = form.dataset.mineForm;
  const values = formValues(form);
  const op = {plan: "save_plan", rings: "ring_search", ground: "ground_search"}[name];
  if (name !== "ground") delete drafts[name];
  if (op) send(ui, op, values);
  return true;
}

export function handleMiningInput(event, ui) {
  const form = event.target.closest?.("[data-mine-form]");
  if (!form || !ui.byId("mining-workspace")?.contains(form) || !event.target.name) return false;
  const key = form.dataset.mineForm;
  drafts[key] = {...(drafts[key] || {}), [event.target.name]: event.target.value};
  // Choosing a material shows where it turns up, and picks the likeliest ground.
  if (key === "ground" && event.target.name === "material") {
    const best = ((last?.material_grounds || {})[event.target.value] || []).find((row) => row.searchable);
    if (best) drafts.ground.ground = best.ground;
    renderMining(last, ui);
  }
  return true;
}

// Running times tick between snapshots.
function tick() {
  document.querySelectorAll('#mining-workspace [data-mn-live="1"]').forEach((node) => {
    node.textContent = clock(Date.now() / 1000 - n(node.dataset.mnSince));
  });
}
window.setInterval(tick, 1000);

export function resetMining() {
  Object.keys(drafts).forEach((key) => delete drafts[key]);
  drawn = "";
  confirming = {key: "", until: 0};
}
