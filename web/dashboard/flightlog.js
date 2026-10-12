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
function drawTrail(canvas, trail) {
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
    context.fillText(trail && trail.length ? "One system tonight" : "No jumps tonight", width / 2, height / 2);
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
      <p>${ui.escapeHtml(log.start_system)} → ${ui.escapeHtml(log.end_system)} · ${ui.escapeHtml(log.flown)}${log.ship ? ` · ${ui.escapeHtml(log.ship)}` : ""} · from ${ui.escapeHtml(log.time)}</p></div></header>
    <div class="flightlog-body">
      <div class="flightlog-map"><canvas id="flightlog-trail" aria-label="Tonight's trail"></canvas></div>
      <div class="flightlog-facts">
        <div class="flightlog-figures">${figure(ui, "jumps", ui.numeric(f.jumps))}${figure(ui, "light years", ui.numeric(f.distance))}${figure(ui, "first discoveries", ui.numeric(f.firsts))}${figure(ui, "credits", credits(f.credits))}</div>
        ${extras ? `<p class="flightlog-extras">${extras}</p>` : ""}
        ${log.star ? `<p class="flightlog-star"><i>✧</i><span>Tonight's star: <b>${ui.escapeHtml(log.star.system)}</b>, ${stayed(log.star.minutes)}</span><button type="button" data-page="constellation">YOUR SKY</button></p>` : ""}
        ${highlights ? `<ol class="flightlog-highlights">${highlights}</ol>` : ""}
        ${cards ? `<div class="flightlog-cards">${cards}</div>` : ""}
      </div>
    </div>
    <blockquote class="flightlog-words">${ui.escapeHtml(log.words)}<cite>the Watcher</cite></blockquote>
  </article>`;
}

function show(ui) {
  const root = ui.byId("flightlog-workspace");
  const log = logs.find((row) => row.id === selected) || logs[0];
  if (!log) return;
  selected = log.id;
  root.querySelectorAll("[data-flightlog]").forEach((button) => button.classList.toggle("active", button.dataset.flightlog === log.id));
  ui.byId("flightlog-view").innerHTML = page(log, ui);
  drawTrail(ui.byId("flightlog-trail"), log.trail);
}

export function renderFlightLogs(data = {}, ui) {
  const root = ui.byId("flightlog-workspace");
  if (!root) return;
  logs = Array.isArray(data.logs) ? data.logs : [];
  const key = JSON.stringify([logs.map((log) => [log.id, log.flown, log.figures?.jumps]), data.notice]);
  if (key === lastKey) return;
  lastKey = key;
  if (!logs.length) {
    root.innerHTML = "";
    return;
  }
  root.innerHTML = `<section class="flightlog" aria-label="Flight logs">
    <aside class="flightlog-nights"><h3>FLIGHT LOGS <b>${ui.numeric(logs.length)}</b></h3>
      <ol>${logs.map((log) => `<li><button type="button" data-flightlog="${ui.escapeHtml(log.id)}">
        <b>${ui.escapeHtml(log.date.replace(/ \d{4}$/, ""))}</b><span>${ui.escapeHtml(log.flown)} · ${ui.numeric(log.figures?.jumps)} jumps${log.open ? " · now" : ""}</span></button></li>`).join("")}</ol>
      <label class="flightlog-notice"><input type="checkbox" data-flightlog-notice${data.notice !== false ? " checked" : ""}><span>A notice when you log off</span></label>
    </aside>
    <div id="flightlog-view" class="flightlog-view"></div>
  </section>`;
  root.querySelector(".flightlog-nights").addEventListener("click", (event) => {
    const button = event.target.closest("[data-flightlog]");
    if (!button) return;
    selected = button.dataset.flightlog;
    show(ui);
  });
  root.querySelector("[data-flightlog-notice]").addEventListener("change", (event) => {
    ui.command("workspace", {page: "flight_log", operation: "notice", value: event.target.checked});
  });
  show(ui);
}
