// Planetary (5.5.12): Materials & Sites and Ground & Exobio as one page, in
// three tabs. ON THE GROUND is the compass, the field map and the planet;
// EXOBIOLOGY is what lives here, as Survey Operations reads it, and the
// sample you're working on; SITES is your saved surface sites.
//
// Compass, marker and trail buttons are the deck's own ground commands
// (data-ws-page="ground"), so their toasts and cockpit refresh stay as they
// were. Site forms keep unsaved edits through redraws.

// An arrowhead, not a triangle: an equilateral ▲ turned 60° reads as ▼.
const ARROW = '<svg viewBox="0 0 20 20"><path d="M10 1.5 L15.5 17.5 L10 13.5 L4.5 17.5 Z"/></svg>';
const VIEWS = [["ground", "ON THE GROUND"], ["exobio", "EXOBIOLOGY"], ["sites", "SITES"]];
const CODEX = {new: "NEW TO THE CODEX", region: "NEW IN THIS REGION"};
const KINDS = {complete: "done", sample: "working", detected: "found", predicted: "likely", possible: "maybe"};

let view = "";
// "" picks for you: this planet when you're on one with sites, else all of them.
let sitesView = "";
let siteSearch = "";
let selectedPlanet = "";
let bodyMaterial = "";
let material = "";
let newSiteOpen = false;
let last = null;
let drawn = "";

const n = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
const known = (value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
const whole = (value) => Math.round(n(value)).toLocaleString("en-GB");
const credits = (value) => {
  const v = n(value), abs = Math.abs(v);
  return abs >= 1e9 ? `${(v / 1e9).toFixed(2)}B` : abs >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : abs >= 1e3 ? `${(v / 1e3).toFixed(0)}K` : `${Math.round(v)}`;
};
const cr = (value) => `${credits(value)} CR`;
const range = (low, high) => !n(high) ? "—" : n(low) === n(high) ? cr(high) : `${credits(low)}–${cr(high)}`;
const metres = (value) => n(value) >= 1000 ? `${(n(value) / 1000).toFixed(n(value) >= 10000 ? 0 : 1)} km` : `${whole(value)} m`;
const clean = (value) => String(value || "").normalize("NFKC").trim().replace(/\s+/g, " ");
const folded = (value) => clean(value).toLocaleLowerCase();

export function setPlanetaryView(name) {
  if (VIEWS.some(([id]) => id === name)) view = name;
}

// -- small pieces ---------------------------------------------------------------------
function panel(title, body, {note = "", wide = false, cls = ""} = {}) {
  return `<section class="po-panel${wide ? " wide" : ""}${cls ? ` ${cls}` : ""}"><header><h4>${title}</h4>${note ? `<span>${note}</span>` : ""}</header>${body}</section>`;
}

const empty = (text) => `<p class="po-dim">${text}</p>`;
const fact = (label, value) => `<div><small>${label}</small><b>${value}</b></div>`;

function codexChip(flag) {
  return CODEX[flag] ? `<em class="po-codex ${flag}">${CODEX[flag]}</em>` : "";
}

// -- the planet ----------------------------------------------------------------------------
function planetBody(data) {
  const position = data.current_position || {};
  const here = data.exobiology?.here || {};
  const name = position.body || here.full_name || data.ground?.body || "";
  const scanned = (data.bodies || []).find((row) => folded(row.body) === folded(name) || folded(row.short_name) === folded(name)) || {};
  return {...scanned, ...(position.body_details || {}), name: name || scanned.body || ""};
}

function planetFacts(body, esc) {
  const rows = [
    ["CLASS", body.class || "—"], ["GRAVITY", known(body.gravity) ? `${n(body.gravity).toFixed(2)} g` : "—"],
    ["TEMPERATURE", known(body.temperature) ? `${whole(body.temperature)} K` : "—"],
    ["ATMOSPHERE", body.atmosphere === "" ? "None" : body.atmosphere || "—"],
    ["VOLCANISM", body.volcanism === "" ? "None" : body.volcanism || "—"],
    ["MINING SITES (DSS)", known(body.mining_locations) ? whole(body.mining_locations) : "—"],
  ];
  const materials = (body.materials || []).map((row) => `<li><span>${esc(row.name)}</span><i><b style="width:${Math.min(100, n(row.percent)).toFixed(1)}%"></b></i><strong>${n(row.percent).toFixed(1)}%</strong></li>`).join("");
  return `<div class="po-facts">${rows.map(([label, value]) => fact(label, esc(value))).join("")}</div>
    ${materials ? `<h5>RAW MATERIALS</h5><ul class="po-bars">${materials}</ul>` : empty("Raw materials show once the planet is scanned.")}`;
}

// -- the surface map (5.5.12) ------------------------------------------------------------
// North up, in metres from the ship. Everything the backend put in one frame:
// you, the ship, your trail, samples (with the range each needs), markers,
// Codex finds, saved sites and the compass target. FIT ALL shows the lot;
// AROUND ME follows you; + and − zoom. Click a point to steer to it.
let mapMode = "fit";
let mapZoom = 1;
const STEPS = [5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000, 50000];
const MW = 1000, MH = 640, PAD = 46;

function mapBounds(map, focus) {
  const pts = [];
  const add = (at, r = 0) => { if (at) pts.push([at[0] - r, at[1] - r], [at[0] + r, at[1] + r]); };
  const colony = n(map.sampling?.colony_m);
  if (focus === "samples") {
    (map.pins || []).filter((pin) => pin.kind === "organic_sample" && (!map.sampling?.group || pin.group === map.sampling.group))
      .forEach((pin) => add(pin.at, colony));
    add(map.you?.at);
  } else {
    add(map.you?.at); add(map.ship?.at); add(map.target?.at);
    (map.trail || []).forEach((at) => add(at));
    (map.pins || []).forEach((pin) => add(pin.at, pin.kind === "organic_sample" && pin.group === map.sampling?.group ? colony : 0));
    (map.sites || []).forEach((site) => add(site.at));
  }
  if (!pts.length) return null;
  const es = pts.map((p) => p[0]), ns = pts.map((p) => p[1]);
  return {e0: Math.min(...es), e1: Math.max(...es), n0: Math.min(...ns), n1: Math.max(...ns)};
}

function surfaceMap(map, esc, {focus = "all", controls = true} = {}) {
  if (!map) return empty("The map starts when you land: your trail, samples and markers show here.");
  const bounds = mapBounds(map, focus);
  if (!bounds) return empty("Nothing to map yet: land, or drive a little.");
  let centre, half;
  if (focus === "all" && mapMode === "me" && map.you) {
    centre = map.you.at;
    half = 300;
  } else {
    centre = [(bounds.e0 + bounds.e1) / 2, (bounds.n0 + bounds.n1) / 2];
    half = Math.max(60, (bounds.e1 - bounds.e0) / 2 * (MH / MW), (bounds.n1 - bounds.n0) / 2) * 1.12;
  }
  half /= focus === "all" ? mapZoom : 1;
  const scale = (MH / 2 - PAD) / half;
  const x = (e) => MW / 2 + (e - centre[0]) * scale;
  const y = (north) => MH / 2 - (north - centre[1]) * scale;
  const step = STEPS.find((value) => value * scale >= 70) || STEPS[STEPS.length - 1];
  const parts = [];
  // Grid at the step, then rings around you.
  const grid = [];
  const eStart = Math.ceil((centre[0] - MW / 2 / scale) / step) * step;
  for (let e = eStart; x(e) <= MW; e += step) grid.push(`M${x(e).toFixed(1)} 0V${MH}`);
  const nStart = Math.ceil((centre[1] - MH / 2 / scale) / step) * step;
  for (let north = nStart; y(north) >= 0; north += step) grid.push(`M0 ${y(north).toFixed(1)}H${MW}`);
  parts.push(`<path class="grid" d="${grid.join("")}"/>`);
  if (map.you) {
    const [ux, uy] = [x(map.you.at[0]), y(map.you.at[1])];
    for (let ring = 1; ring <= 3; ring += 1) {
      const r = ring * step * 2 * scale;
      parts.push(`<circle class="ring" cx="${ux.toFixed(1)}" cy="${uy.toFixed(1)}" r="${r.toFixed(1)}"/><text class="ring-label" x="${ux.toFixed(1)}" y="${(uy - r - 4).toFixed(1)}" text-anchor="middle">${metres(ring * step * 2)}</text>`);
    }
  }
  // The range each sample of the species you're on needs.
  const colony = n(map.sampling?.colony_m);
  const active = (pin) => pin.kind === "organic_sample" && map.sampling?.group && pin.group === map.sampling.group;
  if (colony) {
    (map.pins || []).filter(active).forEach((pin) => parts.push(`<circle class="colony" cx="${x(pin.at[0]).toFixed(1)}" cy="${y(pin.at[1]).toFixed(1)}" r="${(colony * scale).toFixed(1)}"/>`));
  }
  if ((map.trail || []).length > 1) {
    parts.push(`<polyline class="trail" points="${map.trail.map((at) => `${x(at[0]).toFixed(1)},${y(at[1]).toFixed(1)}`).join(" ")}"/>`);
  }
  if (map.target && map.you) {
    parts.push(`<line class="to-target" x1="${x(map.you.at[0]).toFixed(1)}" y1="${y(map.you.at[1]).toFixed(1)}" x2="${x(map.target.at[0]).toFixed(1)}" y2="${y(map.target.at[1]).toFixed(1)}"/>`);
  }
  const feature = (cls, at, body, tip, extra = "") => `<g class="feat ${cls}" transform="translate(${x(at[0]).toFixed(1)} ${y(at[1]).toFixed(1)})" data-tip="${esc(tip)}"${extra}><circle class="hit" r="16"/>${body}</g>`;
  const distanceFromYou = (at) => map.you ? Math.hypot(at[0] - map.you.at[0], at[1] - map.you.at[1]) : null;
  const away = (at) => { const d = distanceFromYou(at); return d === null ? "" : ` · ${metres(d)} away`; };
  (map.sites || []).forEach((site) => parts.push(feature("site", site.at, `<rect x="-7" y="-7" width="14" height="14"/><text x="12" y="4">${esc(site.label)}</text>`,
    `Saved site: ${site.label}${away(site.at)} · click to steer to it`, ` data-goto-lat="${site.lat}" data-goto-lon="${site.lon}"`)));
  (map.pins || []).forEach((pin) => {
    const tip = `${pin.label || pin.kind}${away(pin.at)}`;
    const go = ` data-goto-lat="${pin.lat}" data-goto-lon="${pin.lon}"`;
    if (pin.kind === "organic_sample") {
      parts.push(feature(`sample${active(pin) ? " active" : ""}`, pin.at, `<circle r="${active(pin) ? 10 : 6}"/>${active(pin) && pin.progress ? `<text y="4" text-anchor="middle">${pin.progress}</text>` : ""}`,
        `Sample: ${tip}`, go));
    } else if (pin.kind === "codex") {
      parts.push(feature("codex", pin.at, `<path d="M0 -9L9 0L0 9L-9 0Z"/>`, `Codex: ${tip}`, go));
    } else if (pin.kind === "landing") {
      if (!map.ship) parts.push(feature("landing", pin.at, `<rect x="-6" y="-6" width="12" height="12" rx="2"/>`, `Landed${away(pin.at)}`, go));
    } else {
      parts.push(feature("marker", pin.at, `<path d="M0 0L-6 -12A7 7 0 1 1 6 -12Z"/><text x="10" y="-8">${esc(pin.label || "Marker")}</text>`,
        `Marker: ${tip} · click to steer to it`, go));
    }
  });
  if (map.ship) parts.push(feature("ship", map.ship.at, `<path d="M0 -12L9 9L0 4L-9 9Z"/><text x="13" y="5">SHIP</text>`, `Your ship${away(map.ship.at)} · click to head back`, ' data-goto-ship="1"'));
  if (map.target) parts.push(feature("target", map.target.at, `<circle r="11"/><path d="M-16 0H-6M6 0H16M0 -16V-6M0 6V16"/><text x="16" y="-12">${esc(map.target.label || "Target")}</text>`,
    `Compass target: ${map.target.label || "target"}${away(map.target.at)}`));
  if (map.you) {
    const heading = known(map.you.heading) ? n(map.you.heading) : 0;
    parts.push(`<g class="you" transform="translate(${x(map.you.at[0]).toFixed(1)} ${y(map.you.at[1]).toFixed(1)})"><circle class="halo" r="22"/><g transform="rotate(${heading.toFixed(0)})"><path d="M0 -16L10 12L0 6L-10 12Z"/></g></g>`);
  }
  // North and the scale.
  parts.push(`<g class="north" transform="translate(${MW - 34} 38)"><path d="M0 -18L7 4L0 0L-7 4Z"/><text y="22" text-anchor="middle">N</text></g>`);
  const bar = step * scale;
  parts.push(`<g class="scale" transform="translate(${PAD - 20} ${MH - 22})"><path d="M0 -6V0H${bar.toFixed(1)}V-6"/><text x="${(bar / 2).toFixed(1)}" y="-10" text-anchor="middle">${metres(step)}</text></g>`);
  const legend = [
    map.you ? ["you", "You"] : null, map.ship ? ["ship", "Ship"] : null, (map.trail || []).length > 1 ? ["trail", "Your trail"] : null,
    map.target ? ["target", "Compass target"] : null,
    (map.pins || []).some((pin) => pin.kind === "organic_sample") ? ["sample", colony ? `Samples (rings: ${metres(colony)} apart)` : "Samples"] : null,
    (map.pins || []).some((pin) => pin.kind === "codex") ? ["codex", "Codex finds"] : null,
    (map.pins || []).some((pin) => !["organic_sample", "codex", "landing"].includes(pin.kind)) ? ["marker", "Your markers"] : null,
    (map.sites || []).length ? ["site", "Saved sites"] : null,
  ].filter(Boolean).map(([cls, label]) => `<li class="${cls}"><i></i>${label}</li>`).join("");
  const tools = controls && focus === "all" ? `<div class="po-map-tools">
      <button type="button" class="${mapMode === "fit" ? "active" : ""}" data-po-op="map_mode" data-mode="fit">FIT ALL</button>
      <button type="button" class="${mapMode === "me" ? "active" : ""}" data-po-op="map_mode" data-mode="me"${map.you ? "" : " disabled"}>AROUND ME</button>
      <button type="button" data-po-op="map_zoom" data-step="1.6" title="Zoom in">+</button><button type="button" data-po-op="map_zoom" data-step="0.625" title="Zoom out">−</button></div>` : "";
  return `${tools}<div class="po-surface"><svg viewBox="0 0 ${MW} ${MH}" role="img" aria-label="Map of the surface around you">${parts.join("")}</svg><div class="po-map-tip" hidden></div></div><ul class="po-legend">${legend}</ul>`;
}

function bindSurfaceMaps(root, ui) {
  root.querySelectorAll(".po-surface").forEach((box) => {
    const tip = box.querySelector(".po-map-tip");
    box.addEventListener("mousemove", (event) => {
      const feat = event.target.closest?.(".feat");
      if (!feat) { tip.hidden = true; return; }
      tip.textContent = feat.dataset.tip;
      tip.hidden = false;
      const rect = box.getBoundingClientRect();
      tip.style.left = `${Math.max(4, Math.min(rect.width - tip.offsetWidth - 4, event.clientX - rect.left + 14))}px`;
      tip.style.top = `${Math.max(4, event.clientY - rect.top + 14)}px`;
    });
    box.addEventListener("mouseleave", () => { tip.hidden = true; });
  });
}

// -- ON THE GROUND ---------------------------------------------------------------------------
function compassPanel(data, ui, esc) {
  const ground = data.ground || {};
  const target = ground.target || {};
  const elite = ground.elite_target || {};
  const delta = n(target.heading_delta);
  const readout = target.active && known(target.distance)
    ? `<div class="po-readout"><i class="po-needle" style="transform:rotate(${delta.toFixed(0)}deg)" aria-hidden="true">${ARROW}</i><div><b>${metres(target.distance)}</b><span>${known(target.bearing) ? `bearing ${whole(target.bearing)}°` : ""}${target.direction ? ` · ${esc(target.direction)}` : ""}</span></div></div>`
    : `<div class="po-readout off"><i class="po-needle" aria-hidden="true">${ARROW}</i><div><b>${target.active ? "Target set" : "No target"}</b><span>${target.active ? "Land or drive to get a heading" : "Paste coordinates, or use where you are"}</span></div></div>`;
  const eliteStrip = elite.name ? `<p class="po-elite${elite.is_current_body ? " here" : ""}">⌖ ELITE TARGET <b>${esc(elite.name)}</b>${elite.is_current_body ? " · you're here" : " · approach or land for surface guidance"}</p>` : "";
  return panel("COMPASS", `${readout}
    <div class="po-coords"><label>LATITUDE<input id="ground-lat" type="number" min="-90" max="90" step="0.000001" value="${target.active && known(target.lat) ? target.lat : ""}" placeholder="32.328000"></label>
      <label>LONGITUDE<input id="ground-lon" type="number" min="-180" max="180" step="0.000001" value="${target.active && known(target.lon) ? target.lon : ""}" placeholder="108.838000"></label></div>
    <div class="po-actions">
      <button type="button" class="primary" data-ws-page="ground" data-ws-op="set">SET TARGET</button>
      <button type="button" data-ws-page="ground" data-ws-op="set_current"${ground.on_planet ? "" : " disabled"}>USE WHERE I AM</button>
      <button type="button" data-ws-page="mission" data-ws-op="mark_here"${ground.on_planet ? "" : " disabled"} title="Keep this spot as one of the expedition's places">+ EXPEDITION PLACE</button>
      <button type="button" data-ws-page="ground" data-ws-op="return_ship">BACK TO THE SHIP</button>
      <button type="button" data-ws-page="ground" data-ws-op="clear"${target.active ? "" : " disabled"}>CLEAR</button>
      <button type="button" data-ws-page="ground" data-ws-op="toggle_popup" aria-pressed="${Boolean(target.popup)}">COCKPIT POPUP ${target.popup ? "ON" : "OFF"}</button>
      <button type="button" data-po-op="save_spot"${data.current_position ? "" : " disabled"}>SAVE THIS SPOT AS A SITE</button>
    </div>${eliteStrip}`, {note: target.active && target.label ? esc(target.label) : ""});
}

function mapPanel(data, ui, esc) {
  const ground = data.ground || {};
  const field = ground.field_map || {};
  const trail = ground.trail || {};
  const pins = (field.pins || []).slice().reverse().slice(0, 30).map((row) => `<li class="${esc(row.kind)}"><i></i><span><b>${esc(row.label || row.kind)}</b><small>${known(row.distance) ? `${metres(row.distance)} · ${whole(row.bearing)}°` : esc(row.source || "field record")}</small></span>${row.manual ? `<button type="button" class="row-delete" data-ws-page="ground" data-ws-op="remove_pin" data-pin-id="${esc(row.id)}" title="Remove this marker">×</button>` : ""}</li>`).join("");
  const facts = `<div class="po-trail"><span>TRAVELLED <b>${known(trail.travelled) ? metres(trail.travelled) : "—"}</b></span><span>SHIP <b>${known(trail.return_distance) ? `${metres(trail.return_distance)} @ ${whole(trail.return_bearing)}°` : "—"}</b></span></div>`;
  return panel("FIELD MAP", `${surfaceMap(data.map, esc)}${facts}
    <div class="po-marker"><input id="field-marker-label" placeholder="Note for a marker where you are" maxlength="160"><button type="button" data-ws-page="ground" data-ws-op="add_pin">MARK HERE</button><button type="button" data-ws-page="ground" data-ws-op="clear_trail">CLEAR TRAIL</button></div>
    ${pins ? `<ul class="po-pins">${pins}</ul>` : empty("Landings, samples, Codex finds and your markers show here.")}`,
    {note: field.body ? esc(field.body) : "", cls: "po-map-panel"});
}

function groundView(data, ui, esc) {
  const body = planetBody(data);
  return `<div class="po-grid po-ground">${compassPanel(data, ui, esc)}${mapPanel(data, ui, esc)}</div>
    ${panel(body.name ? `THIS PLANET · ${esc(body.name).toUpperCase()}` : "THIS PLANET", body.name ? planetFacts(body, esc) : empty("Approach or land on a planet."), {wide: true})}`;
}

// -- EXOBIOLOGY --------------------------------------------------------------------------------
function samplingPanel(data, ui, esc) {
  const sampling = data.exobiology?.sampling;
  if (!sampling?.species) return "";
  const progress = Math.max(0, Math.min(3, n(sampling.progress)));
  const colony = n(sampling.colony_m);
  const nearest = known(sampling.min_distance_m) ? n(sampling.min_distance_m) : null;
  const dots = [1, 2, 3].map((step) => `<i class="${step <= progress ? "done" : step === progress + 1 ? "next" : ""}">${step}</i>`).join("");
  let distance = empty("Take the first sample anywhere.");
  if (progress >= 3) distance = `<p class="po-clear ok">All three samples taken. Analysed.</p>`;
  else if (colony && nearest !== null) {
    const share = Math.min(1, nearest / colony);
    distance = `<div class="po-distance ${sampling.clear ? "ok" : "wait"}"><i><b style="width:${(share * 100).toFixed(1)}%"></b></i>
      <p>${sampling.clear ? `<b>Far enough.</b> ${metres(nearest)} from your last sample: take the next one.` : `<b>Move ${metres(colony - nearest)} further.</b> ${metres(nearest)} of the ${metres(colony)} this genus needs between samples.`}</p></div>`;
  } else if (colony) distance = empty(`This genus needs ${metres(colony)} between samples.`);
  return panel("SAMPLING", `<div class="po-sample"><div><b>${esc(sampling.species)}</b><small>${esc(sampling.genus || "")}</small></div><div class="po-dots" aria-label="${progress} of 3 samples">${dots}</div></div>${distance}`,
    {note: colony ? `${metres(colony)} apart` : "", cls: "po-sampling"});
}

function speciesRow(row, esc) {
  const value = row.value ? cr(row.value) : range(row.min_value, row.max_value);
  const lines = (row.lines || []).map((line) => `<li><span>${esc(line.species)}</span>${line.colours.length
    ? line.colours.map((colour) => `<em class="po-colour ${esc(colour.flag)}">${esc(colour.name)}</em>`).join("")
    : codexChip(line.flag)}</li>`).join("");
  return `<li class="po-species ${KINDS[row.kind] || ""}"><span class="po-state">${esc(row.status)}</span>
    <div><b>${esc(row.name)}</b>${row.variant ? `<small>${esc(row.variant)}</small>` : ""}${lines ? `<ul class="po-lines">${lines}</ul>` : ""}</div>
    <strong>${value}</strong>${codexChip(row.codex)}</li>`;
}

function herePanel(data, esc) {
  const here = data.exobiology?.here;
  if (!here) return panel("THIS PLANET'S BIOLOGY", empty("Land on, or approach, a planet with biological signals. Scan it with the FSS and the surface scanner and its species show here."), {wide: true});
  const rows = here.rows || [];
  const order = ["complete", "sample", "detected", "predicted", "possible"];
  const sorted = rows.slice().sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind));
  const done = rows.filter((row) => row.kind === "complete").length;
  const head = `<div class="po-here"><div><b>${esc(here.name)}</b><small>${esc([here.planet_class, known(here.gravity_g) ? `${n(here.gravity_g).toFixed(2)} g` : "", known(here.temperature_k) ? `${whole(here.temperature_k)} K` : "", here.atmosphere].filter(Boolean).join(" · "))}</small></div>
    <div class="po-figures"><span>SIGNALS <b>${whole(done)} / ${whole(here.bio_count)}</b></span><span>WORTH <b>${range(here.min_value, here.max_value)}</b></span>${here.first_footfall ? `<span class="po-footfall">FIRST FOOTFALL <b>×5</b></span>` : ""}</div></div>`;
  const list = sorted.length ? `<ul class="po-species-list">${sorted.map((row) => speciesRow(row, esc)).join("")}</ul>` : empty("No biology here, or none scanned yet.");
  return panel("THIS PLANET'S BIOLOGY", `${head}${list}`, {wide: true, note: data.exobiology?.codex_flags ? "Codex flags as on Survey Operations" : ""});
}

function systemPanel(data, esc) {
  const rows = data.exobiology?.system_bodies || [];
  if (!rows.length) return "";
  const body = `<table class="po-table"><thead><tr><th>PLANET</th><th>SIGNALS</th><th>WORTH</th><th>GRAVITY</th><th></th></tr></thead><tbody>${rows.map((row) => `<tr class="${row.here ? "here" : ""}${row.complete >= row.bio_count ? " done" : ""}">
      <td><b>${esc(row.name)}</b>${row.here ? "<small>you're here</small>" : row.first_footfall ? "<small>first footfall ×5</small>" : ""}</td>
      <td>${whole(row.complete)} / ${whole(row.bio_count)}</td><td>${range(row.min_value, row.max_value)}</td>
      <td>${known(row.gravity_g) ? `${n(row.gravity_g).toFixed(2)} g` : "—"}${row.landable === false ? "<small>not landable</small>" : ""}</td>
      <td>${codexChip(row.codex)}</td></tr>`).join("")}</tbody></table>`;
  return panel(`BIOLOGY IN ${esc(String(data.exobiology?.system || "THIS SYSTEM").toUpperCase())}`, body, {wide: true, note: "unfinished planets first, richest first"});
}

function exobioView(data, ui, esc) {
  const exo = data.exobiology || {};
  const field = data.ground?.field_map || {};
  const sampling = samplingPanel(data, ui, esc);
  const unsold = n(exo.unsold);
  const aboard = unsold ? `<p class="po-unsold">Unsold biology aboard: <b>${cr(unsold)}</b>${unsold > n(exo.unsold_base) ? ` (with ${cr(unsold - n(exo.unsold_base))} of first-footfall bonus)` : ""}. Sell it at a Vista Genomics.</p>` : "";
  const top = sampling
    ? `<div class="po-grid">${sampling}${panel("WHERE YOU'VE SAMPLED", `${surfaceMap(data.map, esc, {focus: "samples", controls: false})}<p class="po-dim">Each ring is how far the next sample must be from that one. Outside every ring: sample away.</p>`, {cls: "po-map-panel"})}</div>`
    : "";
  return `${aboard}${top}${herePanel(data, esc)}${systemPanel(data, esc)}`;
}

// -- SITES ----------------------------------------------------------------------------------------
function sitesModel(data) {
  const localBody = (body) => {
    const system = clean(body?.system || data.system);
    const name = clean(body?.body || body?.short_name);
    const prefix = `${folded(system)} `;
    return system && folded(name).startsWith(prefix) ? name.slice(system.length).trim() : name;
  };
  const planetKey = (body) => JSON.stringify([folded(body?.system || data.system), folded(localBody(body))]);
  const planetLabel = (body) => `${clean(body?.system || data.system) || "Unknown system"} / ${localBody(body) || "Unknown planet"}`;
  const merged = new Map();
  const add = (body) => {
    if (!body || !clean(body.body || body.short_name)) return;
    const key = planetKey(body);
    const prior = merged.get(key) || {};
    merged.set(key, {...body, ...prior, system: clean(prior.system || body.system || data.system), body: clean(prior.body || body.body || body.short_name)});
  };
  (data.bodies || []).forEach(add);
  (data.sites || []).forEach((site) => add({...site.body_details, system: site.system, body: site.body}));
  const bodies = [...merged.values()].sort((a, b) => planetLabel(a).localeCompare(planetLabel(b), undefined, {numeric: true, sensitivity: "base"}));
  const live = data.current_position ? planetKey(data.current_position) : "";
  const selected = bodies.find((body) => planetKey(body) === selectedPlanet) || bodies.find((body) => planetKey(body) === live) || bodies[0] || {};
  const materialsFor = (site) => clean(site.materials).split(",").map(clean).filter(Boolean);
  return {bodies, selected, planetKey, planetLabel, materialsFor};
}

function siteFields(data, site, esc) {
  const position = data.current_position || {};
  const input = (key, label, value, extra = "") => `<label>${label}<input name="${key}" value="${esc(value ?? "")}" ${extra}></label>`;
  return `<input type="hidden" name="id" value="${esc(site.id || "")}"><input type="hidden" name="site_type" value="${esc(site.site_type || "site")}">
    <input type="hidden" name="map_name" value="${esc(site.map_name || "")}"><input type="hidden" name="planet_radius" value="${esc(site.planet_radius || position.planet_radius || "")}">
    <input type="hidden" name="body_details" value="${esc(JSON.stringify(site.body_details || {}))}">
    ${input("system", "SYSTEM", site.system || position.system || data.system || "", 'maxlength="140" required')}
    ${input("body", "PLANET", site.body || position.body || "", 'maxlength="160" required')}
    ${input("name", "SITE NAME", site.name || "", 'maxlength="120" required')}
    ${input("latitude", "LATITUDE", site.latitude ?? "", 'type="number" step="any" min="-90" max="90" required')}
    ${input("longitude", "LONGITUDE", site.longitude ?? "", 'type="number" step="any" min="-180" max="180" required')}
    ${input("materials", "MATERIALS (YOUR NOTES)", site.materials || "", `maxlength="2000"${site.site_type === "drill" ? "" : " required"}`)}
    <label>ADD A MATERIAL<select data-material-choice><option value="">Choose…</option>${(data.mining_catalogue || []).map((name) => `<option value="${esc(name)}">${esc(name)}${(data.new_mining_materials || []).includes(name) ? " · NEW" : ""}</option>`).join("")}</select></label>
    ${input("location_index", "MINING LOCATION NO.", site.location_index ?? position.location_index ?? "", 'type="number" min="1" max="9999" step="1" placeholder="optional"')}
    <label>AMOUNT LEFT<select name="amount">${["", "High", "Medium", "Low", "Depleted"].map((value) => `<option value="${value}"${site.amount === value ? " selected" : ""}>${value || "Unrecorded"}</option>`).join("")}</select></label>
    <label>DENSITY<select name="density">${["", "Low", "Medium", "High"].map((value) => `<option value="${value}"${site.density === value ? " selected" : ""}>${value || "Unrecorded"}</option>`).join("")}</select></label>
    ${input("rigs", "RIG POSITIONS", n(site.rigs) || 0, 'type="number" min="0" max="64" step="1" title="The rig circles drawn at this deposit, not rigs you placed"')}
    <label class="po-check"><input type="checkbox" name="depleted" value="1"${site.depleted ? " checked" : ""}>Mined out</label>
    ${input("notes", "NOTES", site.notes || "", 'maxlength="4000"')}
    <div class="po-actions"><button type="button" data-current-coordinates${data.current_position ? "" : " disabled"}>USE WHERE I AM</button>
      <button type="submit" class="primary">${site.id ? "SAVE CHANGES" : "ADD SITE"}</button>${site.id ? `<button type="button" class="danger-action" data-site-delete="${esc(site.id)}">DELETE SITE</button>` : ""}</div>
    <p class="po-dim" data-captured>${site.body_details?.body ? `Planet scan captured: ${esc(site.body_details.body)}` : "USE WHERE I AM captures the planet's scan with the site."}</p>`;
}

function sitesView_(data, esc) {
  const {bodies, selected, planetKey, planetLabel, materialsFor} = sitesModel(data);
  const navigation = data.navigation_target || {};
  const activeSite = (site) => Boolean(navigation.active && (navigation.site_id != null ? String(navigation.site_id) === String(site.id)
    : planetKey(site) === planetKey(navigation) && Math.abs(n(site.latitude) - n(navigation.latitude)) < 1e-6 && Math.abs(n(site.longitude) - n(navigation.longitude)) < 1e-6));
  const onPlanet = (data.sites || []).filter((site) => planetKey(site) === planetKey(selected));
  const live = data.current_position ? planetKey(data.current_position) : "";
  const shown = sitesView || ((data.sites || []).some((site) => planetKey(site) === live) ? "body" : "all");
  const choices = [...new Set(onPlanet.flatMap(materialsFor))].sort((a, b) => a.localeCompare(b, undefined, {sensitivity: "base"}));
  if (!choices.some((value) => folded(value) === folded(bodyMaterial))) bodyMaterial = "";
  const visible = bodyMaterial ? onPlanet.filter((site) => materialsFor(site).some((value) => folded(value) === folded(bodyMaterial))) : onPlanet;
  const card = (site) => `<details class="po-site${site.depleted ? " depleted" : ""}${site.site_type === "drill" ? " drill" : ""}" data-site-id="${esc(site.id)}">
      <summary><span><b>${esc(site.name)}</b><small>${site.location_index ? `Location ${whole(site.location_index)} · ` : ""}${n(site.latitude).toFixed(4)}, ${n(site.longitude).toFixed(4)}</small></span>
        <span class="po-tags">${materialsFor(site).map((name) => `<i>${esc(name)}</i>`).join("")}</span>
        <em>${site.depleted ? "MINED OUT" : esc(site.tons_left || [site.amount, site.density].filter(Boolean).join(" · ") || "")}</em>
        <button type="button" class="${activeSite(site) ? "active" : ""}" data-site-navigate="${esc(site.id)}">${activeSite(site) ? "COMPASS ON IT" : "SEND TO COMPASS"}</button></summary>
      ${site.notes ? `<p class="po-dim">${esc(site.notes)}</p>` : ""}<form class="po-form" data-site-form>${siteFields(data, site, esc)}</form></details>`;
  const cards = visible.map(card).join("");
  const toolbar = `<div class="po-toolbar">
    <nav class="po-subtabs">${[["all", `ALL SITES (${whole((data.sites || []).length)})`], ["body", "THIS PLANET"], ["heat", "HEAT MAP"], ["material", "BY MATERIAL"]].map(([key, label]) => `<button type="button" class="${shown === key ? "active" : ""}" data-po-op="sites_view" data-view="${key}">${label}</button>`).join("")}</nav>
    <button type="button" class="primary" data-po-op="new_site" aria-expanded="${newSiteOpen}">${newSiteOpen ? "CLOSE THE NEW SITE" : "ADD A SITE"}</button></div>`;
  const newSite = newSiteOpen ? panel("NEW SITE", `<form class="po-form" data-site-form data-new-site>${siteFields(data, {}, esc)}</form>`, {wide: true, cls: "po-new-site"}) : "";
  let body;
  if (shown === "all") {
    // Every saved site, by planet: this system first, then A to Z.
    const groups = new Map();
    for (const site of data.sites || []) {
      const key = planetKey(site);
      if (!groups.has(key)) groups.set(key, {key, label: planetLabel(site), system: clean(site.system), sites: []});
      groups.get(key).sites.push(site);
    }
    const here = folded(data.system);
    const ordered = [...groups.values()].sort((a, b) => (folded(a.system) !== here) - (folded(b.system) !== here)
      || a.label.localeCompare(b.label, undefined, {numeric: true, sensitivity: "base"}));
    const list = ordered.map((group) => {
      const materials = [...new Set(group.sites.flatMap(materialsFor))];
      const words = folded([group.label, ...materials, ...group.sites.map((site) => site.name)].join(" "));
      return `<section class="po-group${group.key === live ? " here" : ""}" data-search="${esc(words)}">
        <header><div><b>${esc(group.label)}</b><small>${whole(group.sites.length)} site${group.sites.length === 1 ? "" : "s"}${materials.length ? ` · ${esc(materials.join(", "))}` : ""}${group.key === live ? " · you're here" : folded(group.system) === here ? " · in this system" : ""}</small></div>
          <button type="button" data-po-op="open_planet" data-planet="${esc(group.key)}">THIS PLANET</button></header>
        ${group.sites.map(card).join("")}</section>`;
    }).join("");
    body = panel("ALL SAVED SITES", list ? `<label class="po-pick po-search">FIND<input data-po-site-search value="${esc(siteSearch)}" placeholder="A planet, system, site or material" autocomplete="off"></label>
      <div class="po-groups">${list}</div><p class="po-dim" data-po-no-match hidden>Nothing matches.</p>
      <p class="po-dim">SEND TO COMPASS on any site: the cockpit compass picks it up when you land on its planet.</p>`
      : empty("No sites saved yet. ADD A SITE, or SAVE THIS SPOT from ON THE GROUND."),
      {wide: true, note: `${whole((data.sites || []).length)} sites on ${whole(groups.size)} planet${groups.size === 1 ? "" : "s"}`});
  } else if (shown === "heat") {
    const minerals = [...new Map((data.sites || []).flatMap(materialsFor).map((name) => [folded(name), name])).values()].sort((a, b) => a.localeCompare(b, undefined, {sensitivity: "base"}));
    const classes = [...new Set((data.sites || []).map((site) => site.body_details?.class || "Unreported"))].sort();
    const rows = minerals.map((name) => `<tr><th>${esc(name)}</th>${classes.map((cls) => {
      const count = (data.sites || []).filter((site) => (site.body_details?.class || "Unreported") === cls && materialsFor(site).some((value) => folded(value) === folded(name))).length;
      return `<td class="${count ? "on" : ""}">${count || "—"}</td>`;
    }).join("")}</tr>`).join("");
    body = panel("WHERE YOU'VE FOUND WHAT", rows ? `<div class="po-scroll"><table class="po-table po-heat"><thead><tr><th>MATERIAL</th>${classes.map((cls) => `<th>${esc(cls)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>` : empty("Save some sites and they're compared here by material and planet class."), {wide: true, note: "your saved sites, by planet class"});
  } else if (shown === "material") {
    const minerals = [...new Map((data.sites || []).flatMap(materialsFor).map((name) => [folded(name), name])).values()].sort((a, b) => a.localeCompare(b, undefined, {sensitivity: "base"}));
    if (!minerals.some((name) => folded(name) === folded(material))) material = minerals[0] || "";
    const matches = (data.sites || []).filter((site) => materialsFor(site).some((value) => folded(value) === folded(material)));
    body = panel("FIND A MATERIAL", `<label class="po-pick">MATERIAL<select data-po-material>${minerals.map((name) => `<option${folded(name) === folded(material) ? " selected" : ""}>${esc(name)}</option>`).join("") || "<option>No materials noted yet</option>"}</select></label>
      ${matches.length ? `<table class="po-table"><thead><tr><th>SITE</th><th>PLANET</th><th>POSITION</th><th>DENSITY</th></tr></thead><tbody>${matches.map((site) => `<tr><td><b>${esc(site.name)}</b></td><td>${esc(site.system)} / ${esc(site.body)}</td><td>${n(site.latitude).toFixed(4)}, ${n(site.longitude).toFixed(4)}</td><td>${esc(site.density || "—")}</td></tr>`).join("")}</tbody></table>` : empty("No sites with it yet.")}`, {wide: true});
  } else {
    const picker = `<div class="po-pickers"><label class="po-pick">PLANET<select data-po-planet>${bodies.map((body) => `<option value="${esc(planetKey(body))}"${body === selected ? " selected" : ""}>${esc(planetLabel(body))}</option>`).join("") || "<option value=\"\">No planets scanned or saved</option>"}</select></label>
      <label class="po-pick">MATERIAL<select data-po-body-material><option value="">All</option>${choices.map((value) => `<option${folded(value) === folded(bodyMaterial) ? " selected" : ""}>${esc(value)}</option>`).join("")}</select></label></div>`;
    body = panel("SAVED SITES", `${picker}${cards || empty("No sites saved on this planet. ADD A SITE, or SAVE THIS SPOT from ON THE GROUND.")}
      <p class="po-dim">What this kind of ground tends to hold, and its Rhino value, is on <button type="button" class="po-link" data-page="mining">Mining</button>'s live run in the Rhino.</p>`,
      {wide: true, note: `${whole(onPlanet.length)} here · ${whole((data.sites || []).length)} in all`});
  }
  return `${toolbar}${newSite}${body}`;
}

// -- the page ---------------------------------------------------------------------------------
function statusStrip(data, esc) {
  const ground = data.ground || {};
  const position = ground.position || {};
  const target = ground.target || {};
  const sampling = data.exobiology?.sampling;
  const body = data.current_position?.body || ground.body || "";
  return `<div class="po-status">
    <div><b>WHERE</b><span>${esc(data.system || ground.system || "Waiting for your location")}${body ? ` · ${esc(body)}` : ""}</span></div>
    <div><b>STATE</b><span>${ground.on_planet ? "On the surface" : body ? "Near the planet" : "In flight"}</span></div>
    <div><b>POSITION</b><span>${known(position.lat) ? `${n(position.lat).toFixed(4)}, ${n(position.lon).toFixed(4)}${known(position.heading) ? ` · ${whole(position.heading)}°` : ""}` : "—"}</span></div>
    <div><b>COMPASS</b><span>${target.active ? `${known(target.distance) ? metres(target.distance) : "set"}${known(target.bearing) ? ` @ ${whole(target.bearing)}°` : ""}` : "Off"}</span></div>
    <div><b>SAMPLING</b><span>${sampling?.species ? `${esc(sampling.species)} · ${whole(sampling.progress)}/3` : "—"}</span></div>
  </div>`;
}

function defaultView(data) {
  if (data.exobiology?.sampling?.species || (data.ground?.on_planet && n(data.exobiology?.here?.bio_count))) return "exobio";
  return "ground";
}

function keepDrafts(root) {
  const drafts = [];
  root.querySelectorAll("form[data-dirty]").forEach((form) => {
    const draft = Object.fromEntries(new FormData(form));
    if (form.elements.depleted) draft.depleted = form.elements.depleted.checked ? "1" : "0";
    drafts.push({key: form.dataset.newSite !== undefined ? "__new__" : form.elements.id?.value || "", draft,
      captured: form.querySelector("[data-captured]")?.innerHTML || ""});
  });
  const open = [...root.querySelectorAll("details[data-site-id][open]")].map((node) => node.dataset.siteId);
  return {drafts, open};
}

function restoreDrafts(root, kept) {
  for (const id of kept.open) root.querySelector(`details[data-site-id="${CSS.escape(id)}"]`)?.setAttribute("open", "");
  for (const {key, draft, captured} of kept.drafts) {
    const form = key === "__new__" ? root.querySelector("form[data-new-site]")
      : [...root.querySelectorAll("form[data-site-form]")].find((candidate) => candidate.elements.id?.value === key);
    if (!form) continue;
    for (const [name, value] of Object.entries(draft)) {
      const field = form.elements[name];
      if (!field) continue;
      if (field.type === "checkbox") field.checked = value === "1";
      else field.value = value;
    }
    form.dataset.dirty = "true";
    const note = form.querySelector("[data-captured]");
    if (note && captured) note.innerHTML = captured;
    form.closest("details")?.setAttribute("open", "");
  }
}

export function renderPlanetary(data, ui) {
  const root = ui.byId("planet-materials-workspace");
  if (!root) return;
  if (root.dataset.profileKey !== String(data?.profile_key || "")) {
    root.dataset.profileKey = String(data?.profile_key || "");
    selectedPlanet = bodyMaterial = material = "";
    newSiteOpen = false;
  }
  last = data || {};
  root.planetData = last;
  root.classList.remove("loading-panel");
  if (!view) view = defaultView(last);
  const esc = ui.escapeHtml;
  const tabs = `<nav class="co-tabs po-tabs">${VIEWS.map(([id, label]) => `<button type="button" class="${view === id ? "active" : ""}" data-po-op="view" data-view="${id}">${label}${id === "exobio" && last.exobiology?.sampling?.species ? " <small>●</small>" : ""}</button>`).join("")}</nav>`;
  const body = view === "exobio" ? exobioView(last, ui, esc) : view === "sites" ? sitesView_(last, esc) : groundView(last, ui, esc);
  const markup = `${statusStrip(last, esc)}${tabs}<div class="po-body">${body}</div>`;
  if (markup === drawn && root.firstElementChild) return;
  const kept = keepDrafts(root);
  drawn = markup;
  root.innerHTML = markup;
  restoreDrafts(root, kept);
  filterSites(root);
  bindSurfaceMaps(root, ui);
  ui.decorate?.(root);
}

function rerender(ui) {
  drawn = "";
  renderPlanetary(last, ui);
}

function capture(form, data, ui) {
  const position = data.current_position;
  if (!position) {
    ui.showToast("Your planet position isn't known yet: land, or drive on the surface.");
    return false;
  }
  for (const key of ["system", "body", "latitude", "longitude"]) form.elements[key].value = position[key];
  form.elements.planet_radius.value = position.planet_radius || "";
  form.elements.location_index.value = position.location_index || "";
  if (!form.elements.name.value) form.elements.name.value = `Site ${n(position.latitude).toFixed(4)}, ${n(position.longitude).toFixed(4)}`;
  form.elements.body_details.value = JSON.stringify(position.body_details || {});
  const note = form.querySelector("[data-captured]");
  if (note) note.textContent = `Planet scan captured: ${position.body}`;
  form.dataset.dirty = "true";
  return true;
}

async function refreshAfter(ui) {
  ui.forgetFingerprint("planet-materials");
  window.setTimeout(() => ui.syncSnapshot?.(), 120);
}

export function handlePlanetaryClick(event, ui) {
  const root = ui.byId("planet-materials-workspace");
  if (!root || !root.contains(event.target)) return false;
  const point = event.target.closest?.(".po-surface .feat[data-goto-lat], .po-surface .feat[data-goto-ship]");
  if (point) {
    const payload = point.dataset.gotoShip ? {page: "ground", operation: "return_ship"}
      : {page: "ground", operation: "set", lat: point.dataset.gotoLat, lon: point.dataset.gotoLon};
    ui.command("workspace", payload).then((accepted) => {
      ui.showToast(accepted ? `Compass on: ${point.dataset.tip.split(" · ")[0]}` : "That point couldn't be sent to the compass.");
      if (accepted) refreshAfter(ui);
    });
    return true;
  }
  const button = event.target.closest("[data-po-op], [data-site-navigate], [data-site-delete], [data-current-coordinates]");
  if (!button || button.disabled) return false;
  event.preventDefault();
  if (button.dataset.poOp === "map_mode") {
    mapMode = button.dataset.mode === "me" ? "me" : "fit";
    mapZoom = 1;
    rerender(ui);
  } else if (button.dataset.poOp === "map_zoom") {
    mapZoom = Math.max(0.25, Math.min(12, mapZoom * Number(button.dataset.step || 1)));
    rerender(ui);
  } else if (button.dataset.poOp === "view") {
    view = button.dataset.view;
    rerender(ui);
  } else if (button.dataset.poOp === "open_planet") {
    selectedPlanet = button.dataset.planet;
    bodyMaterial = "";
    sitesView = "body";
    rerender(ui);
  } else if (button.dataset.poOp === "sites_view") {
    sitesView = button.dataset.view;
    rerender(ui);
  } else if (button.dataset.poOp === "new_site") {
    newSiteOpen = !newSiteOpen;
    rerender(ui);
  } else if (button.dataset.poOp === "save_spot") {
    view = "sites";
    sitesView = "body";
    newSiteOpen = true;
    rerender(ui);
    const form = root.querySelector("form[data-new-site]");
    if (form && capture(form, last, ui)) {
      form.elements.name?.focus();
      form.elements.name?.select();
      ui.showToast("Spot captured: name it if you like, then ADD SITE.");
    }
  } else if (button.dataset.currentCoordinates !== undefined) {
    capture(button.closest("form"), last, ui);
  } else if (button.dataset.siteNavigate) {
    event.stopPropagation();
    const site = (last.sites || []).find((row) => String(row.id) === String(button.dataset.siteNavigate));
    if (!site) return true;
    ui.command("workspace", {page: "planet-materials", operation: "navigate_site", id: site.id, profile_key: root.dataset.profileKey})
      .then((accepted) => {
        ui.showToast(accepted ? `Compass on ${site.name}. It opens on ${site.body}.` : "That site couldn't be sent to the compass.");
        if (accepted) refreshAfter(ui);
      });
  } else if (button.dataset.siteDelete) {
    if (!window.confirm("Delete this site from this commander's saved sites?")) return true;
    ui.command("workspace", {page: "planet-materials", operation: "delete_site", id: button.dataset.siteDelete, profile_key: root.dataset.profileKey})
      .then((accepted) => { if (accepted) refreshAfter(ui); });
  }
  return true;
}

export function handlePlanetaryChange(event, ui) {
  const root = ui.byId("planet-materials-workspace");
  if (!root || !root.contains(event.target)) return false;
  const target = event.target;
  if (target.matches("[data-po-planet]")) { selectedPlanet = target.value; bodyMaterial = ""; rerender(ui); return true; }
  if (target.matches("[data-po-body-material]")) { bodyMaterial = target.value; rerender(ui); return true; }
  if (target.matches("[data-po-material]")) { material = target.value; rerender(ui); return true; }
  const form = target.closest("form[data-site-form]");
  if (!form) return false;
  form.dataset.dirty = "true";
  if (target.name === "amount" && form.elements.depleted) form.elements.depleted.checked = target.value === "Depleted";
  if (target.name === "depleted") {
    if (target.checked) form.elements.amount.value = "Depleted";
    else if (form.elements.amount.value === "Depleted") form.elements.amount.value = "";
  }
  if (target.matches("[data-material-choice]") && target.value) {
    const values = clean(form.elements.materials.value).split(",").map(clean).filter(Boolean);
    if (!values.some((value) => folded(value) === folded(target.value))) values.push(target.value);
    form.elements.materials.value = values.join(", ");
    target.value = "";
  }
  return true;
}

// The site search hides what doesn't match in place: redrawing would take
// the box's focus mid-word.
function filterSites(root) {
  const words = folded(siteSearch).split(" ").filter(Boolean);
  const groups = [...root.querySelectorAll(".po-group[data-search]")];
  groups.forEach((group) => { group.hidden = !words.every((word) => group.dataset.search.includes(word)); });
  const none = root.querySelector("[data-po-no-match]");
  if (none) none.hidden = !groups.length || groups.some((group) => !group.hidden);
}

export function handlePlanetaryInput(event, ui) {
  if (event.target.matches?.("[data-po-site-search]")) {
    siteSearch = event.target.value;
    filterSites(ui.byId("planet-materials-workspace"));
    return true;
  }
  const form = event.target.closest?.("form[data-site-form]");
  if (!form || !ui.byId("planet-materials-workspace")?.contains(form)) return false;
  form.dataset.dirty = "true";
  if (["system", "body"].includes(event.target.name)) {
    form.elements.body_details.value = "{}";
    form.elements.planet_radius.value = "";
    form.elements.location_index.value = "";
    const note = form.querySelector("[data-captured]");
    if (note) note.textContent = "Planet changed: USE WHERE I AM again to capture its scan.";
  }
  return true;
}

export function handlePlanetarySubmit(event, ui) {
  const form = event.target.closest?.("form[data-site-form]");
  if (!form || !ui.byId("planet-materials-workspace")?.contains(form)) return false;
  event.preventDefault();
  if (form.dataset.saving) return true;
  form.dataset.saving = "true";
  const payload = Object.fromEntries(new FormData(form));
  ui.command("workspace", {...payload, page: "planet-materials", operation: "save", profile_key: ui.byId("planet-materials-workspace").dataset.profileKey})
    .then((accepted) => {
      delete form.dataset.saving;
      if (!accepted) return ui.showToast("That site couldn't be saved. Check the fields.");
      delete form.dataset.dirty;
      if (form.dataset.newSite !== undefined) newSiteOpen = false;
      document.activeElement?.blur();
      ui.showToast("Site saved");
      refreshAfter(ui);
    });
  return true;
}

export function resetPlanetary() {
  view = "";
  sitesView = "";
  siteSearch = "";
  selectedPlanet = bodyMaterial = material = "";
  newSiteOpen = false;
  drawn = "";
}
