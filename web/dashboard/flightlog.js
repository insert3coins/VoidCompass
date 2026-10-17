// Session flight logs (5.5.3.8): one page for each night you flew, at the
// top of the Captain's Log. The nights down the side; the chosen one as a
// page: its trail, its figures and best moments, the postcards you took,
// tonight's star, and the Watcher's closing words.

let selected = "";
let lastKey = "";
let logs = [];

function token(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

// The night's trail, fitted to the box: where it began, where it ended.
function drawTrail(canvas, trail, part = "night") {
  const box = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(box.width)), height = Math.max(1, Math.round(box.height));
  canvas.width = width * ratio; canvas.height = height * ratio;
  const context = canvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  const bg = token("--bg", "#070b10"), accent = token("--accent", "#00d1ff"), orange = token("--orange", "#ff7a18"),
    border = token("--border", "#243746");
  context.fillStyle = bg;
  context.fillRect(0, 0, width, height);
  context.strokeStyle = border; context.lineWidth = 1; context.globalAlpha = .35;
  for (let x = 0; x <= width; x += 32) { context.beginPath(); context.moveTo(x + .5, 0); context.lineTo(x + .5, height); context.stroke(); }
  for (let y = 0; y <= height; y += 32) { context.beginPath(); context.moveTo(0, y + .5); context.lineTo(width, y + .5); context.stroke(); }
  context.globalAlpha = 1;
  if (!trail || trail.length < 2) {
    context.fillStyle = token("--muted", "#85939d");
    context.font = '12px "Segoe UI", sans-serif'; context.textAlign = "center";
    const when = part === "night" ? "tonight" : `this ${part}`;
    context.fillText(trail && trail.length ? `One system ${when}` : `No jumps ${when}`, width / 2, height / 2);
    return;
  }
  const xs = trail.map((point) => point[0]), zs = trail.map((point) => point[1]);
  const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...zs) - Math.min(...zs), 10);
  const scale = Math.min(width, height) * .8 / span;
  const cx = (Math.max(...xs) + Math.min(...xs)) / 2, cz = (Math.max(...zs) + Math.min(...zs)) / 2;
  const at = ([x, z]) => [width / 2 + (x - cx) * scale, height / 2 - (z - cz) * scale];
  const points = trail.map(at);
  context.lineJoin = "round"; context.lineCap = "round";
  context.strokeStyle = "rgba(0, 0, 0, .6)"; context.lineWidth = 4;
  context.beginPath(); context.moveTo(...points[0]); points.slice(1).forEach((point) => context.lineTo(...point)); context.stroke();
  context.shadowColor = accent; context.shadowBlur = 6;
  context.strokeStyle = accent; context.lineWidth = 1.8;
  context.beginPath(); context.moveTo(...points[0]); points.slice(1).forEach((point) => context.lineTo(...point)); context.stroke();
  context.shadowBlur = 0;
  const [sx, sy] = points[0], [ex, ey] = points[points.length - 1];
  context.fillStyle = bg; context.strokeStyle = accent; context.lineWidth = 1.6;
  context.beginPath(); context.arc(sx, sy, 4, 0, Math.PI * 2); context.fill(); context.stroke();
  context.fillStyle = orange;
  context.beginPath(); context.arc(ex, ey, 4.5, 0, Math.PI * 2); context.fill();
  context.strokeStyle = orange; context.globalAlpha = .5;
  context.beginPath(); context.arc(ex, ey, 9, 0, Math.PI * 2); context.stroke();
  context.globalAlpha = 1;
}

function stayed(minutes) {
  const value = Number(minutes || 0);
  if (value < 60) return `${value} min`;
  const hours = value / 60;
  return `${hours >= 10 ? Math.round(hours) : hours.toFixed(1).replace(/\.0$/, "")} h`;
}

function figure(ui, label, value) {
  return `<div class="flightlog-figure"><b>${value}</b><span>${ui.escapeHtml(label)}</span></div>`;
}

function credits(value) {
  const number = Number(value || 0);
  if (number >= 1e9) return `${(number / 1e9).toFixed(1)}B`;
  if (number >= 1e6) return `${(number / 1e6).toFixed(1)}M`;
  if (number >= 1e3) return `${Math.round(number / 1e3)}K`;
  return String(Math.round(number));
}

function page(log, ui) {
  const f = log.figures || {};
  const extras = [[f.rare, "rare world", "rare worlds"], [f.codex, "Codex entry", "Codex entries"], [f.bio, "species analysed", "species analysed"],
    [f.mapped, "world mapped", "worlds mapped"], [f.deaths, "ship lost", "ships lost"]]
    .filter(([count]) => count).map(([count, one, many]) => `<em>${ui.numeric(count)} ${count === 1 ? one : many}</em>`).join("");
  const highlights = (log.highlights || []).map((row) => `<li><b>${ui.escapeHtml(row.kind)}</b><span>${ui.escapeHtml(row.title)}${row.detail ? ` · <small>${ui.escapeHtml(row.detail)}</small>` : ""}</span></li>`).join("");
  const cards = (log.postcards || []).map((card) => `<img src="${ui.apiUrl(`/media/postcard-thumb/${encodeURIComponent(card.id)}.jpg`)}" alt="" title="${ui.escapeHtml(card.title)}" loading="lazy">`).join("");
  return `<article class="flightlog-page">
    <header><div><small>FLIGHT LOG · ${ui.escapeHtml(log.elite_date)}${log.open ? " · IN FLIGHT" : ""}</small>
      <h3>${ui.escapeHtml(log.date)}</h3>
      <p>${ui.escapeHtml(log.start_system)} → ${ui.escapeHtml(log.end_system)} · ${ui.escapeHtml(log.flown)}${log.ship ? ` · ${ui.escapeHtml(log.ship)}` : ""} · from ${ui.escapeHtml(log.time)}</p></div>
      <button type="button" class="primary flightlog-watch" data-flightlog-watch="${ui.escapeHtml(log.id)}" title="The Flight Recorder: this session played again on the Galactic Atlas">▶ WATCH AGAIN</button></header>
    <div class="flightlog-body">
      <div class="flightlog-map"><canvas id="flightlog-trail" aria-label="${ui.escapeHtml(log.whens || "The")} trail"></canvas></div>
      <div class="flightlog-facts">
        <div class="flightlog-figures">${figure(ui, "jumps", ui.numeric(f.jumps))}${figure(ui, "light years", ui.numeric(f.distance))}${figure(ui, "first discoveries", ui.numeric(f.firsts))}${figure(ui, "credits", credits(f.credits))}</div>
        ${extras ? `<p class="flightlog-extras">${extras}</p>` : ""}
        ${log.star ? `<p class="flightlog-star"><i>✧</i><span>${ui.escapeHtml(log.whens || "The session's")} star: <b>${ui.escapeHtml(log.star.system)}</b>, ${stayed(log.star.minutes)}</span><button type="button" data-page="constellation">YOUR SKY</button></p>` : ""}
        ${highlights ? `<ol class="flightlog-highlights">${highlights}</ol>` : ""}
        ${cards ? `<div class="flightlog-cards">${cards}</div>` : ""}
      </div>
    </div>
    <blockquote class="flightlog-words">${ui.escapeHtml(log.words)}<cite>the Watcher</cite></blockquote>
  </article>`;
}

// The whole Captain's Log entry for a night (the old session card): every
// highlight it kept, with its time; folded until opened.
function fullLog(log, session, ui) {
  if (!session) return "";
  const rows = (session.highlights || []).map((row) => `<li><b>${ui.escapeHtml(row.kind)}</b><span>${ui.escapeHtml(row.title)}${row.detail ? ` · <small>${ui.escapeHtml(row.detail)}</small>` : ""}</span><time>${ui.escapeHtml(String(row.timestamp || "").replace("T", " ").slice(11, 16))}</time></li>`).join("");
  return `<details class="flightlog-full" data-fold="full"${fullOpen ? " open" : ""}><summary>FULL LOG · ${ui.numeric((session.highlights || []).length)} ENTRIES · ${ui.numeric(session.fss)} FSS · ${ui.numeric(session.dss)} DSS · ${ui.numeric(session.bio)} BIO</summary>
    ${rows ? `<ol>${rows}</ol>` : `<p>No notable moments were kept for this flight.</p>`}</details>`;
}

let fullOpen = false;
let findsOpen = false;

// The session's field discoveries (5.5.3.8): new materials, data and
// datalink scans, vouchers; the same kind at the same place kept as one row.
function findsLog(log, ui) {
  const finds = log.finds || [];
  if (!finds.length) return "";
  const rows = finds.map((find) => {
    const what = find.count > 1 ? `${ui.numeric(find.count)} ${find.many}` : (find.titles[0] || find.one);
    const items = find.count > 1 ? find.titles.filter(Boolean).join(", ") : find.detail;
    const when = find.from === find.to ? find.from : `${find.from}–${find.to}`;
    return `<li><b>${ui.escapeHtml(find.kind)}</b><span>${ui.escapeHtml(what)}${find.place ? ` · <small>${ui.escapeHtml(find.place)}</small>` : ""}
      ${items ? `<em>${ui.escapeHtml(items)}</em>` : ""}${find.value && find.event === "MaterialDiscovered" ? `<em>Discovery no. ${ui.numeric(find.value)}</em>` : ""}${find.value && find.event === "DatalinkVoucher" ? `<em>${ui.numeric(find.value)} cr</em>` : ""}</span><time>${ui.escapeHtml(when)}</time></li>`;
  }).join("");
  return `<details class="flightlog-full flightlog-finds" data-fold="finds"${findsOpen ? " open" : ""}><summary>FIELD DISCOVERIES · ${ui.numeric(log.finds_total)}</summary><ol>${rows}</ol></details>`;
}
let sessions = {};
let filter = "";
let lastPageKey = "";

function show(ui, force = false) {
  const log = logs.find((row) => row.id === selected) || logs[0];
  if (!log) return;
  selected = log.id;
  ui.byId("flightlog-workspace").querySelectorAll("[data-flightlog]").forEach((button) =>
    button.classList.toggle("active", button.dataset.flightlog === log.id));
  const key = JSON.stringify([log, sessions[log.id]?.highlights?.length]);
  if (key === lastPageKey && !force) return;
  lastPageKey = key;
  ui.byId("flightlog-view").innerHTML = page(log, ui).replace("</article>", `${findsLog(log, ui)}${fullLog(log, sessions[log.id], ui)}</article>`);
  drawTrail(ui.byId("flightlog-trail"), log.trail, log.part);
}

function listNights(ui) {
  const words = filter.trim().toLowerCase();
  const shown = logs.filter((log) => !words || `${log.start_system} ${log.end_system} ${log.date} ${log.ship}`.toLowerCase().includes(words));
  let month = "";
  const items = [];
  for (const log of shown) {
    if (log.month !== month) {
      month = log.month;
      items.push(`<li class="flightlog-month">${ui.escapeHtml(month.toUpperCase())}</li>`);
    }
    const route = log.start_system === log.end_system ? log.start_system : `${log.start_system} → ${log.end_system}`;
    items.push(`<li><button type="button" data-flightlog="${ui.escapeHtml(log.id)}" class="${log.id === selected ? "active" : ""}">
      <b>${ui.escapeHtml(log.day)} · ${ui.escapeHtml(log.time)}${log.open ? " <em>NOW</em>" : ""}</b>
      <span class="flightlog-route">${ui.escapeHtml(route)}</span>
      <span>${ui.escapeHtml(log.flown)} · ${ui.numeric(log.figures?.jumps)} jumps</span></button></li>`);
  }
  ui.byId("flightlog-list").innerHTML = items.join("") || `<li class="flightlog-none">No flight matches that.</li>`;
}

export function renderFlightLogs(data = {}, ui, chronicle = []) {
  const root = ui.byId("flightlog-workspace");
  if (!root) return;
  logs = Array.isArray(data.logs) ? data.logs : [];
  sessions = Object.fromEntries((chronicle || []).map((session) => [session.started, session]));
  if (!logs.length) {
    root.innerHTML = "";
    lastKey = "";
    return;
  }
  if (!root.querySelector(".flightlog")) {
    // The frame, once: the search box keeps its words and focus.
    root.innerHTML = `<section class="flightlog" aria-label="Flight logs">
      <aside class="flightlog-nights"><h3>FLIGHT LOGS <b id="flightlog-count"></b></h3>
        <input type="search" id="flightlog-find" class="flightlog-find" placeholder="Find a system or a day…" aria-label="Find a flight log">
        <ol id="flightlog-list"></ol>
        <label class="flightlog-notice"><input type="checkbox" data-flightlog-notice><span>A notice when you log off</span></label>
      </aside>
      <div id="flightlog-view" class="flightlog-view"></div>
    </section>`;
    root.addEventListener("click", (event) => {
      const watch = event.target.closest("[data-flightlog-watch]");
      if (watch) ui.command("workspace", {page: "chronicle", operation: "watch_again", id: watch.dataset.flightlogWatch});
    });
    root.querySelector(".flightlog-nights").addEventListener("click", (event) => {
      const button = event.target.closest("[data-flightlog]");
      if (!button) return;
      selected = button.dataset.flightlog;
      show(ui, true);
    });
    ui.byId("flightlog-find").addEventListener("input", (event) => {
      filter = event.target.value;
      listNights(ui);
    });
    root.querySelector("[data-flightlog-notice]").addEventListener("change", (event) => {
      ui.command("workspace", {page: "flight_log", operation: "notice", value: event.target.checked});
    });
    // The full log stays open or folded as you leave it.
    root.addEventListener("toggle", (event) => {
      if (event.target.matches?.('[data-fold="full"]')) fullOpen = event.target.open;
      if (event.target.matches?.('[data-fold="finds"]')) findsOpen = event.target.open;
    }, true);
  }
  root.querySelector("[data-flightlog-notice]").checked = data.notice !== false;
  ui.byId("flightlog-count").textContent = ui.numeric(logs.length);
  const key = JSON.stringify(logs.map((log) => [log.id, log.flown, log.figures?.jumps]));
  if (key !== lastKey) {
    lastKey = key;
    listNights(ui);
  }
  show(ui);
}
