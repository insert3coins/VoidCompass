/** Flight readouts and the route ahead, with the full details one click away. */

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[ch]));
const num = (value, digits = 0) => (Number.isFinite(Number(value)) ? Number(value).toLocaleString(undefined, {minimumFractionDigits: digits, maximumFractionDigits: digits}) : "—");
function cr(value) {
  const n = Number(value) || 0;
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${Math.round(n / 1e3)}k`;
  return String(Math.round(n));
}

let folded = null;
let lastRoute = "";
let profile = "";
let currentTiles = {};
let currentUi = null;

function isFolded() {
  if (folded === null) {
    try { folded = localStorage.getItem(`voidcompass.tiles.folded.${profile}`) !== "0"; } catch (_error) { folded = true; }
  }
  return folded;
}

function tile(id, label, lines, mark = "") {
  return `<article class="st-tile st-${id}" data-st-tile="${id}"><small>${label}${mark}</small>${lines.filter(Boolean).map((line, index) => (index ? `<span>${line}</span>` : `<b>${line}</b>`)).join("")}</article>`;
}

function age(seconds) {
  if (seconds === null || seconds === undefined) return "";
  if (seconds < 90) return `${Math.round(seconds)} s ago`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} days ago`;
}

function whereTile(w) {
  if (!w?.system) return tile("where", "WHERE", ["Waiting for the journal"]);
  const dots = (w.streak || []).map((on) => `<i class="${on ? "on" : ""}"></i>`).join("");
  return tile("where", "WHERE YOU ARE", [
    `${esc(w.system)}${w.from ? ` <em>from ${esc(w.from.name)}${w.from.ly ? ` (${num(w.from.ly, 1)} ly)` : ""}</em>` : ""}`,
    [w.region, w.sol !== null ? `Sol ${num(w.sol)} ly` : "", w.colonia !== null ? `Colonia ${num(w.colonia)} ly` : ""].filter(Boolean).map(esc).join(" · "),
    w.known !== null && w.known !== undefined ? `${num(w.known)} known within ${num(w.radius)} ly · ${num(w.not_visited)} not visited` : "",
    w.coords ? `Coord: ${w.coords.map((v) => num(v, 2)).join(" / ")}${w.visit ? ` · visit ${num(w.visit)}` : ""}` : "",
    (w.streak || []).length ? `<span class="st-streak" title="Your last ${w.streak.length} arrivals: lit where the system was new to you">${num(w.new)}/${w.streak.length} new ${dots}</span>` : "",
  ]);
}

function rank(r, label) {
  return r?.name ? `${label}: ${esc(r.name)}${r.percent !== null && r.percent !== undefined ? ` ${num(r.percent)}%` : ""}${r.next ? ` <em>next ${esc(r.next)}</em>` : ""}` : "";
}

function cmdrTile(c) {
  if (!c) return "";
  return tile("cmdr", `CMDR ${esc(String(c.name || "").toUpperCase())}`, [
    c.credits !== null && c.credits !== undefined ? `${cr(c.credits)} cr` : "—",
    esc(c.ship || c.ship_type),
    c.max_range ? `max jump ${num(c.max_range, 1)} ly${c.laden ? ` · ${num(c.laden, 1)} laden` : ""}` : "",
    rank(c.explorer, "Explorer"), rank(c.exobiologist, "Exobiologist"),
  ]);
}

function fuelTile(f) {
  if (!f || f.fuel === null || f.fuel === undefined) return tile("fuel", "FUEL", ["—"]);
  return tile("fuel", "FUEL", [
    `${num(f.fuel, 1)} / ${num(f.capacity, 0)} t · ${num(f.percent)}%`,
    f.jumps !== null && f.jumps !== undefined ? `≈${num(f.jumps)} jumps at max range (${num(f.ly)} ly)` : "",
    f.own?.jumps ? `≈${num(f.own.jumps)} at your pace (${num(f.own.pace_ly, 1)} ly hops, ${num(f.own.per_hop, 2)} t each)` : "",
    f.own?.range ? `range now ${num(f.own.range, 1)} ly${f.own.to_full_s ? ` · full in ${num(Math.ceil(f.own.to_full_s / 60))} min scooping` : ""}` : "",
    f.since_scoop !== null && f.since_scoop !== undefined ? `${num(f.since_scoop)} jumps since the last scoop` : "",
    f.scoopable !== null && f.scoopable !== undefined ? `scoopable: ${num(f.scoopable)} of last ${num(f.of)}` : "",
  ]);
}

function carrierTile(c) {
  if (!c) return "";
  const jump = c.status === "jumping" && c.destination ? `jumping to ${esc(c.destination)}${c.departure ? ` at ${esc(new Date(c.departure).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}))}` : ""}` : "";
  return tile("carrier", "CARRIER", [
    `${esc(c.name || c.callsign)} <em>${esc(c.kind)}</em>`,
    `${esc(c.system)}${c.here ? " · here" : ""}`,
    jump,
    [c.fuel !== null && c.fuel !== undefined ? `Tritium ${num(c.fuel)}${c.fuel_capacity ? `/${num(c.fuel_capacity)}` : ""} t` : "",
      c.balance !== null && c.balance !== undefined ? `Balance ${cr(c.balance)}` : ""].filter(Boolean).join(" · "),
  ]);
}

function unsoldTile(u) {
  if (!u) return "";
  const warn = u.days !== null && u.days !== undefined && u.days > 7 && u.total ? " ⚠" : "";
  return tile("unsold", "UNSOLD", [
    `${cr(u.total)} cr`,
    u.total ? `${cr(u.carto)} cartographics · ${cr(u.bio)} exobiology${u.samples ? ` (${num(u.samples)} samples)` : ""}` : "nothing unsold",
    u.days !== null && u.days !== undefined ? `${num(u.days, u.days < 10 ? 1 : 0)} days since you last sold` : "",
    u.sell_here?.length ? `<b class="st-sell">Sell here: ${u.sell_here.map(esc).join(" · ")}</b>` : "",
  ], warn);
}

function service(label, row) {
  if (!row || !row.state) return "";
  return `<span class="st-svc st-${esc(row.state)}" title="${esc(row.error || "")}">${label} ${esc(row.label || "")}</span>`;
}

function dataTile(d) {
  if (!d) return "";
  const seconds = d.journal_at ? Date.now() / 1000 - d.journal_at : null;
  const warn = d.spansh?.state === "warn" || d.edsm?.state === "warn" || d.inara?.state === "warn" ? " ⚠" : "";
  return tile("data", "DATA", [
    `journal ${seconds !== null ? age(seconds) : "—"}`,
    [service("Spansh", d.spansh), service("EDSM", d.edsm), service("Inara", d.inara), service("EDDN", d.eddn)].filter(Boolean).join(" "),
  ], warn);
}

function routeLine(r) {
  if (!r) return `<small>NEXT JUMP <em>IN-GAME ROUTE</em></small><strong class="st-route-idle">No route plotted</strong><span>Plot a course in Elite, or on the Route page.</span>`;
  const shown = (r.chips || []).slice(0, 12);
  const chips = shown.map((chip) => `<i class="st-chip${chip.scoop ? " scoop" : ""}" title="${esc(chip.name)}: ${esc(chip.cls || "?")}${chip.scoop ? " · scoopable" : ""}">${esc(chip.cls || "?")}</i>`).join("");
  const more = Math.max(0, (r.chips || []).length - shown.length) + (Number(r.more) || 0);
  const plotted = r.source === "plot";
  return `<small>${plotted ? `NEXT STOP <em>${esc(String(r.label || "").toUpperCase())} · ${num(r.stops)} STOPS · ${num(r.jumps)} JUMPS · ${num(r.ly)} LY</em>` : `NEXT JUMP <em>${num(r.jumps)} JUMPS · ${num(r.ly)} LY</em>`}</small>
    <strong title="Next stop: ${esc(r.next)}">${esc(r.next)} <em>${esc(r.next_cls)}${r.neutron ? " ⚡" : ""}</em></strong>
    <span class="st-route-destination" title="Destination: ${esc(r.destination)}">TO ${esc(r.destination || r.next)}${r.to_scoop ? ` · SCOOP IN ${num(r.to_scoop)}` : " · NO SCOOP AHEAD"}</span>
    <span class="st-chips" aria-label="Stars ahead; highlighted stars are scoopable">${chips}${more ? `<em>+${num(more)}</em>` : ""}</span>`;
}

function compactTiles(t) {
  const f = t.fuel;
  const known = (value) => value !== null && value !== undefined;
  const fuel = known(f?.fuel)
    ? `${num(f.fuel, 1)} / ${num(f.capacity)} t${known(f.own?.jumps) ? ` <em>≈${num(f.own.jumps)} jumps</em>` : known(f.jumps) ? ` <em>≈${num(f.jumps)} jumps</em>` : ""}` : "Awaiting fuel";
  const meter = f?.percent !== null && f?.percent !== undefined
    ? `<i class="st-meter${f.percent < 20 ? " low" : ""}" style="--fuel:${Math.max(0, Math.min(100, Number(f.percent) || 0))}%" aria-hidden="true"></i>` : "";
  const seconds = t.data?.journal_at ? Date.now() / 1000 - t.data.journal_at : null;
  const w = t.where || {};
  const fresh = (w.streak || []).slice(-1)[0] === 1;
  const down = ["spansh", "edsm", "inara", "eddn"].filter((key) => t.data?.[key]?.state === "warn")
    .map((key) => ({spansh: "Spansh", edsm: "EDSM", inara: "Inara", eddn: "EDDN"})[key]);
  const u = t.unsold || {};
  const c = t.carrier || {};
  return [
    tile("where", "WHERE", [w.region || w.system
      ? `${esc(w.region || w.system)}${known(w.sol) ? ` <em>Sol ${num(w.sol)} ly</em>` : ""}${fresh ? ' <em class="st-new">NEW</em>' : ""}`
      : "Waiting for the journal"]),
    tile("cmdr", "JUMP RANGE", [t.cmdr?.max_range ? `${num(t.cmdr.max_range, 1)} ly${t.cmdr.laden ? ` <em>${num(t.cmdr.laden, 1)} laden</em>` : ""}` : "Awaiting loadout"]),
    tile("fuel", "FUEL", [fuel + meter]),
    tile("unsold", "DATA ABOARD", [`${cr(u.total)} cr${u.sell_here?.length ? ' <em class="st-sell">SELL HERE</em>' : u.samples ? ` <em>${num(u.samples)} samples</em>` : ""}`]),
    tile("carrier", "CARRIER", [c.name || c.callsign ? `${esc(c.name || c.callsign)}${c.here ? ' <em class="st-live">HERE</em>' : c.system ? ` <em>${esc(c.system)}</em>` : ""}` : "None linked"]),
    tile("data", "JOURNAL", [`${seconds === null ? "Waiting" : seconds < 90 ? '<em class="st-live">Connected</em>' : esc(age(Math.floor(seconds / 60) * 60))}${down.length ? ` <em class="st-warn" title="Not answering">⚠ ${esc(down.join(", "))}</em>` : ""}`]),
  ];
}

export function renderStatusStrip(tiles = {}, ui) {
  if (document.documentElement.classList.contains("solo-window") || document.body.classList.contains("solo")) return;
  const nextProfile = ui?.profileKey?.() || "default";
  if (nextProfile !== profile) {
    profile = nextProfile;
    folded = null;
  }
  currentTiles = tiles;
  currentUi = ui;
  const strip = document.getElementById("status-strip");
  const route = document.getElementById("status-route");
  if (route) {
    if (!route.dataset.keys) {
      // It's a button to the Route page (the deck's [data-page] click opens it).
      route.dataset.keys = "1";
      route.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        route.click();
      });
    }
    const html = routeLine(tiles?.route);
    if (html !== lastRoute) {
      lastRoute = html;
      route.innerHTML = html;
    }
  }
  if (!strip) return;
  let button = strip.querySelector("[data-st-fold]");
  if (!button) {
    button = document.createElement("button");
    button.type = "button";
    button.className = "st-fold";
    button.dataset.stFold = "";
    strip.append(button);
  }
  const compact = isFolded();
  const label = compact ? "FLIGHT DETAILS +" : "LESS DETAIL −";
  if (button.textContent !== label) button.textContent = label;
  button.title = compact ? "Show full location, ship, fuel and data readings" : "Show compact flight readings";
  button.setAttribute("aria-expanded", String(!compact));
  strip.classList.toggle("folded", compact);
  const parts = compact ? compactTiles(tiles) : [whereTile(tiles.where), cmdrTile(tiles.cmdr) || tile("cmdr", "COMMANDER", ["Awaiting profile"]), fuelTile(tiles.fuel),
    carrierTile(tiles.carrier) || tile("carrier", "CARRIER", ["No carrier linked"]), unsoldTile(tiles.unsold) || tile("unsold", "DATA ABOARD", ["Awaiting records"]), dataTile(tiles.data) || tile("data", "DATA", ["Waiting for the journal"])];
  for (const html of parts.filter(Boolean)) {
    const id = /data-st-tile="([^"]+)"/.exec(html)[1];
    const existing = strip.querySelector(`[data-st-tile="${id}"]`);
    if (existing?.dataset.markup === html) continue;
    const template = document.createElement("template");
    template.innerHTML = html;
    const node = template.content.firstElementChild;
    node.dataset.markup = html;
    if (existing) existing.replaceWith(node);
    else strip.append(node);
  }
  if (!strip.dataset.bound) {
    strip.dataset.bound = "1";
    strip.addEventListener("click", (event) => {
      if (!event.target.closest("[data-st-fold]")) return;
      folded = !isFolded();
      try { localStorage.setItem(`voidcompass.tiles.folded.${profile}`, folded ? "1" : "0"); } catch (_error) { /* convenience */ }
      renderStatusStrip(currentTiles, currentUi);
    });
  }
}
