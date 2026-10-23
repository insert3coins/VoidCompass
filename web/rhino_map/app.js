// Rhino Map (5.5.18): the ground round you while you work the Rhino, in an
// overlay of its own. It used to take over the Galaxy Minimap; now the
// minimap stays the galaxy and this one shows only while there's ground to
// map: in the Rhino, or while your rigs are out.
const params = new URLSearchParams(location.search);
const token = params.get("token") || "";
const overlay = params.get("overlay") || "rhino-map";
const root = document.getElementById("rhinomap");
const map = document.getElementById("map");
const marks = document.getElementById("marks");
const ring = document.getElementById("here-ring");
const regionLabel = document.getElementById("region");
const viewMode = document.getElementById("view-mode");
const facts = document.getElementById("facts");

let model = {};
let palette = {};

const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;

function rgb(hex, fallback = [0, 209, 255]) {
  const match = /^#?([0-9a-f]{6})$/i.exec(String(hex || "").trim());
  if (!match) return fallback;
  const value = parseInt(match[1], 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}
const css = (colour, alpha) => `rgba(${colour[0]}, ${colour[1]}, ${colour[2]}, ${alpha})`;
const ease = (t) => 1 - Math.pow(1 - t, 3);

function fit(canvas) {
  const box = map.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(box.width * ratio)), height = Math.max(1, Math.round(box.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  return {width, height, ratio, cssWidth: box.width, cssHeight: box.height};
}

// Metres east and north of the ship, turned so you head up (or north up),
// zoomed to fit your rigs and where you've drilled (or a fixed range).
const RANGE_STEPS = [25, 50, 100, 250, 500, 1000, 2500, 5000];

// Where the map is drawn from: you, your heading and the zoom, which glide
// between updates (they come about twice a second) instead of jumping.
let surfaceView = null;
let surfaceGlide = 0;
const SURFACE_GLIDE_MS = 600;

function surfaceTarget(surface) {
  return {x: number(surface.you?.at?.[0]), y: number(surface.you?.at?.[1]),
    heading: number(surface.you?.heading), half: Math.max(50, number(surface.half_m, 150))};
}

function glideSurface(surface) {
  const target = surfaceTarget(surface);
  cancelAnimationFrame(surfaceGlide);
  surfaceGlide = 0;
  const from = surfaceView;
  const jump = from && Math.hypot(target.x - from.x, target.y - from.y) > target.half;
  if (!from || jump || root.classList.contains("reduced-motion")) {
    surfaceView = target;
    drawSurface(surface);
    return;
  }
  const started = performance.now();
  const turn = ((target.heading - from.heading + 540) % 360) - 180;
  const step = (now) => {
    const t = ease(Math.min(1, (now - started) / SURFACE_GLIDE_MS));
    surfaceView = {x: from.x + (target.x - from.x) * t, y: from.y + (target.y - from.y) * t,
      heading: (from.heading + turn * t + 360) % 360,
      half: Math.exp(Math.log(from.half) + (Math.log(target.half) - Math.log(from.half)) * t)};
    drawSurface(surface);
    surfaceGlide = t < 1 ? requestAnimationFrame(step) : 0;
  };
  surfaceGlide = requestAnimationFrame(step);
}

function surfaceFrame(surface, size) {
  const view = surfaceView || surfaceTarget(surface);
  const you = [view.x, view.y];
  const half = view.half;
  const scale = Math.min(size.cssWidth, size.cssHeight) / 2 / half;
  const turn = surface.up === "north" ? 0 : view.heading * Math.PI / 180;
  const cos = Math.cos(turn), sin = Math.sin(turn);
  const cx = size.cssWidth / 2, cy = size.cssHeight / 2;
  // East/north metres to the screen: turned by your heading, north up when not.
  const at = (point) => {
    const dx = number(point[0]) - number(you[0]), dy = number(point[1]) - number(you[1]);
    const x = dx * cos - dy * sin, y = dx * sin + dy * cos;
    return [cx + x * scale, cy - y * scale];
  };
  return {at, scale, cx, cy, turn, half};
}

function drawSurface(surface) {
  const size = fit(marks);
  const context = marks.getContext("2d");
  context.setTransform(size.ratio, 0, 0, size.ratio, 0, 0);
  context.clearRect(0, 0, size.cssWidth, size.cssHeight);
  const frame = surfaceFrame(surface, size);
  const {at, cx, cy} = frame;
  const hud = rgb(palette.orange, [255, 122, 24]);
  const green = rgb(palette.green, [78, 229, 155]), yellow = rgb(palette.yellow, [255, 209, 102]);
  const text = rgb(palette.text, [220, 232, 239]), accent = rgb(palette.accent, [0, 209, 255]);
  const muted = rgb(palette.muted, [133, 147, 157]);
  const textScale = Number(getComputedStyle(document.documentElement).getPropertyValue("--scale")) || 1;
  const inside = ([px, py], pad = 6) => px >= pad && py >= pad && px <= size.cssWidth - pad && py <= size.cssHeight - pad;
  const font = (px) => `700 ${px * textScale}px Bahnschrift, "Segoe UI", sans-serif`;
  const tag = (words, [px, py], colour, dy = -7) => {
    context.font = font(7.2);
    const width = context.measureText(words).width;
    const x = Math.max(3, Math.min(size.cssWidth - width - 3, px - width / 2));
    context.lineWidth = 2.6; context.strokeStyle = "rgba(0, 0, 0, .8)";
    context.strokeText(words, x, py + dy);
    context.fillStyle = css(colour, .95);
    context.fillText(words, x, py + dy);
  };
  // Something off the map: on its edge, in its direction, with how far.
  const edge = (point) => {
    const dx = point[0] - cx, dy = point[1] - cy;
    const reach = Math.min(Math.abs((size.cssWidth / 2 - 10) / (dx || 1e-6)), Math.abs((size.cssHeight / 2 - 10) / (dy || 1e-6)));
    return [cx + dx * reach, cy + dy * reach, Math.atan2(dy, dx)];
  };
  const pointer = ([x, y, angle], colour) => {
    context.save(); context.translate(x, y); context.rotate(angle);
    context.beginPath(); context.moveTo(6, 0); context.lineTo(-4, -4.5); context.lineTo(-1.5, 0); context.lineTo(-4, 4.5); context.closePath();
    context.fillStyle = "rgba(0, 0, 0, .8)"; context.fill();
    context.lineWidth = 1.4; context.strokeStyle = css(colour, 1); context.stroke();
    context.restore();
  };
  const metres = (value) => (value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)} KM` : `${Math.round(value)} M`);

  // Range rings round you, a round number of metres apart.
  const ringStep = RANGE_STEPS.find((step) => step * frame.scale >= Math.min(size.cssWidth, size.cssHeight) * .16) || 5000;
  context.lineWidth = 1;
  for (let ring = 1; ring * ringStep * frame.scale < Math.hypot(size.cssWidth, size.cssHeight) / 2; ring += 1) {
    context.strokeStyle = css(accent, ring % 2 ? .1 : .18);
    context.beginPath(); context.arc(cx, cy, ring * ringStep * frame.scale, 0, Math.PI * 2); context.stroke();
  }
  // North, on the first ring out, when the map turns with you.
  if (surface.up !== "north") {
    const radius = Math.min(size.cssWidth, size.cssHeight) / 2 - 12;
    const nx = cx + Math.sin(-frame.turn) * radius, ny = cy - Math.cos(-frame.turn) * radius;
    context.font = font(7.5); context.textAlign = "center"; context.textBaseline = "middle";
    context.lineWidth = 2.4; context.strokeStyle = "rgba(0, 0, 0, .8)"; context.strokeText("N", nx, ny);
    context.fillStyle = css(text, .8); context.fillText("N", nx, ny);
    context.textAlign = "start"; context.textBaseline = "alphabetic";
  }

  // The scanner's reach round you (2 km), once the map is wide enough to show it.
  const scanner = number(surface.scanner_m, 2000) * frame.scale;
  if (scanner < Math.hypot(size.cssWidth, size.cssHeight) / 2 && scanner > 24) {
    context.setLineDash([6, 5]); context.strokeStyle = css(accent, .35); context.lineWidth = 1;
    context.beginPath(); context.arc(cx, cy, scanner, 0, Math.PI * 2); context.stroke();
    context.setLineDash([]);
  }

  // Your trail this drive.
  const trail = (surface.trail || []).map(at);
  if (trail.length > 1) {
    context.lineCap = "round"; context.lineJoin = "round";
    context.strokeStyle = "rgba(0, 0, 0, .6)"; context.lineWidth = 3.6;
    context.beginPath(); context.moveTo(...trail[0]); trail.slice(1).forEach((point) => context.lineTo(...point)); context.stroke();
    for (let index = 1; index < trail.length; index += 1) {
      context.strokeStyle = css(hud, .2 + .55 * index / trail.length); context.lineWidth = 1.6;
      context.beginPath(); context.moveTo(...trail[index - 1]); context.lineTo(...trail[index]); context.stroke();
    }
  }

  // Where your drill refined: amber, bigger for more pulses.
  for (const deposit of surface.deposits || []) {
    const spot = at(deposit.at);
    if (!inside(spot, -6)) continue;
    const radius = Math.min(9, 3 + Math.sqrt(number(deposit.pulses, 1)));
    context.fillStyle = css(yellow, .16);
    context.beginPath(); context.arc(spot[0], spot[1], radius + 3, 0, Math.PI * 2); context.fill();
    context.fillStyle = css(yellow, .9);
    context.beginPath(); context.arc(spot[0], spot[1], radius * .55, 0, Math.PI * 2); context.fill();
  }

  // Saved sites, and the compass target.
  for (const site of surface.sites || []) {
    const spot = at(site.at);
    if (!inside(spot)) continue;
    context.strokeStyle = css(accent, .9); context.lineWidth = 1.3;
    context.beginPath(); context.moveTo(spot[0], spot[1] - 4); context.lineTo(spot[0] + 4, spot[1]);
    context.lineTo(spot[0], spot[1] + 4); context.lineTo(spot[0] - 4, spot[1]); context.closePath(); context.stroke();
  }
  if (surface.target?.at) {
    const spot = at(surface.target.at);
    if (inside(spot)) {
      context.strokeStyle = css(green, 1); context.lineWidth = 1.4;
      context.beginPath(); context.arc(spot[0], spot[1], 5, 0, Math.PI * 2);
      context.moveTo(spot[0] - 8, spot[1]); context.lineTo(spot[0] - 3, spot[1]); context.moveTo(spot[0] + 3, spot[1]); context.lineTo(spot[0] + 8, spot[1]);
      context.stroke();
    } else {
      pointer(edge(spot), green);
    }
  }

  // Rig spacing (after EDSMT): a ring round each rig, red where you're too
  // close to put down another, green round them all when you're clear.
  const red = rgb(palette.red, [255, 96, 117]);
  const spacing = number(surface.spacing_m, 78) * frame.scale;
  if (spacing > 5 && (surface.rigs || []).length < 6) {
    for (const rig of surface.rigs || []) {
      const spot = at(rig.at);
      const close = surface.too_close === rig.slot;
      context.strokeStyle = css(close ? red : surface.too_close == null ? green : muted, close ? .8 : .35);
      context.lineWidth = close ? 1.6 : 1;
      context.beginPath(); context.arc(spot[0], spot[1], spacing, 0, Math.PI * 2); context.stroke();
    }
  }
  // Where the next rig can go: here, or the nearest spot clear of them all.
  const legal = surface.next_spot;
  if (legal && !legal.here) {
    const spot = at(legal.at);
    if (inside(spot)) {
      context.setLineDash([3, 3]); context.strokeStyle = css(green, .6); context.lineWidth = 1.2;
      context.beginPath(); context.moveTo(cx, cy); context.lineTo(spot[0], spot[1]); context.stroke();
      context.setLineDash([]);
      context.fillStyle = css(green, .9);
      context.beginPath(); context.moveTo(spot[0], spot[1] - 6); context.lineTo(spot[0] + 4, spot[1]);
      context.lineTo(spot[0], spot[1] + 6); context.lineTo(spot[0] - 4, spot[1]); context.closePath(); context.fill();
      tag("RIG HERE", spot, green, -9);
    }
  }

  // Your rigs: their HERE ring, the number, and the next to collect.
  const next = surface.next_rig;
  const farSlots = new Set((surface.too_far || []).map((row) => row.slot));
  for (const rig of surface.rigs || []) {
    const spot = at(rig.at);
    const isNext = rig.slot === next;
    const far = farSlots.has(rig.slot);
    const colour = far ? red : rig.here ? green : isNext ? hud : text;
    if (!inside(spot, -10)) {
      if (isNext || far) pointer(edge(spot), far ? red : hud);
      continue;
    }
    const reach = number(surface.here_m, 40) * frame.scale;
    if (reach > 4) {
      context.setLineDash([2, 3]); context.strokeStyle = css(colour, .5); context.lineWidth = 1;
      context.beginPath(); context.arc(spot[0], spot[1], reach, 0, Math.PI * 2); context.stroke();
      context.setLineDash([]);
    }
    context.fillStyle = "rgba(0, 0, 0, .85)";
    context.beginPath(); context.arc(spot[0], spot[1], 7, 0, Math.PI * 2); context.fill();
    context.strokeStyle = css(colour, 1); context.lineWidth = isNext ? 2 : 1.3;
    context.beginPath(); context.arc(spot[0], spot[1], 6.2, 0, Math.PI * 2); context.stroke();
    context.font = font(7.5); context.textAlign = "center"; context.textBaseline = "middle";
    context.fillStyle = css(colour, 1); context.fillText(String(rig.slot), spot[0], spot[1] + .5);
    context.textAlign = "start"; context.textBaseline = "alphabetic";
    if (rig.ready) tag("COLLECT", spot, accent, -10);
    else if (isNext && !rig.here) tag("NEXT", spot, hud, -10);
  }
  // A line to the next rig.
  const nextRig = (surface.rigs || []).find((rig) => rig.slot === next);
  if (nextRig && !nextRig.here) {
    const spot = at(nextRig.at);
    context.setLineDash([4, 4]); context.strokeStyle = css(hud, .55); context.lineWidth = 1.2;
    context.beginPath(); context.moveTo(cx, cy); context.lineTo(spot[0], spot[1]); context.stroke();
    context.setLineDash([]);
  }

  // The ship: a chevron where it waits, or on the edge pointing to it.
  if (surface.ship?.at) {
    const spot = at(surface.ship.at);
    if (inside(spot)) {
      context.save(); context.translate(spot[0], spot[1]);
      context.beginPath(); context.moveTo(0, -6); context.lineTo(5, 5); context.lineTo(0, 2.5); context.lineTo(-5, 5); context.closePath();
      context.fillStyle = "rgba(0, 0, 0, .85)"; context.fill();
      context.strokeStyle = css(accent, 1); context.lineWidth = 1.5; context.stroke();
      context.restore();
      tag("SHIP", spot, accent, -9);
    } else {
      const point = edge(spot);
      pointer(point, accent);
      tag(`SHIP ${metres(number(surface.ship.distance))}`, [point[0], point[1]], accent, point[1] < cy ? 14 : -8);
    }
  }

  // You: an arrow the way you face.
  context.save(); context.translate(cx, cy);
  context.rotate(surface.up === "north" ? (surfaceView?.heading ?? number(surface.you?.heading)) * Math.PI / 180 : 0);
  context.beginPath(); context.moveTo(0, -8); context.lineTo(6, 6); context.lineTo(0, 3); context.lineTo(-6, 6); context.closePath();
  context.fillStyle = "rgba(0, 0, 0, .85)"; context.lineWidth = 3; context.strokeStyle = "rgba(0, 0, 0, .85)"; context.stroke();
  context.fillStyle = css(hud, 1); context.fill();
  context.restore();

  // The scale: the ring spacing.
  context.font = font(7);
  const scaleText = `RINGS ${metres(ringStep)}`;
  context.lineWidth = 2.4; context.strokeStyle = "rgba(0, 0, 0, .75)";
  context.strokeText(scaleText, 7, size.cssHeight - 7);
  context.fillStyle = css(muted, .95);
  context.fillText(scaleText, 7, size.cssHeight - 7);
  ring.style.left = `${cx}px`;
  ring.style.top = `${cy}px`;
  ring.hidden = false;
}

let shownRange = "";
let rangeFlash = 0;

function drawSurfaceStrip(surface) {
  const body = String(surface.body || "");
  regionLabel.textContent = surface.vehicle === "RHINO" ? "RHINO MAP" : "GROUND MAP";
  // Which way is up, and the map's range (5.5.18): it lights up a moment
  // when the range hotkey changes it.
  const range = String(surface.range || "YOUR RIGS");
  viewMode.textContent = `${surface.up === "north" ? "NORTH UP" : "HEADING UP"} · ${range}`;
  if (shownRange && shownRange !== range) {
    viewMode.classList.remove("flash");
    void viewMode.offsetWidth;
    viewMode.classList.add("flash");
    window.clearTimeout(rangeFlash);
    rangeFlash = window.setTimeout(() => viewMode.classList.remove("flash"), 1800);
  }
  shownRange = range;
  const metres = (value) => (value >= 1000 ? `${(value / 1000).toFixed(1)} KM` : `${Math.round(value)} M`);
  const parts = [];
  if (surface.ship?.distance != null) parts.push(`SHIP <b>${metres(number(surface.ship.distance))}</b>`);
  const nextRig = (surface.rigs || []).find((rig) => rig.slot === surface.next_rig);
  const far = (surface.too_far || [])[0];
  // Warnings first: a rig about to be lost, then one too close to another.
  if (far) parts.push(`<span class="warn">RIG ${far.slot} ${(number(far.distance) / 1000).toFixed(1)} KM · LOST AT 5 KM</span>`);
  else if (surface.too_close != null && (surface.rigs || []).length < 6) parts.push(`<span class="warn">TOO CLOSE TO RIG ${surface.too_close}</span>`);
  else if (surface.next_spot && !surface.next_spot.here && (surface.rigs || []).length < 6) parts.push(`NEXT RIG SPOT <b>${metres(number(surface.next_spot.distance))}</b>`);
  if (!far && nextRig) parts.push(nextRig.here ? `<span class="route">RIG ${nextRig.slot} HERE</span>` : `RIG ${nextRig.slot} <b>${metres(number(nextRig.distance))}</b>`);
  else if (!far && (surface.rigs || []).length === 0 && surface.vehicle === "RHINO") parts.push("NO RIGS MARKED");
  if (number(surface.signals) > 0) parts.push(`<b>${number(surface.signals)}</b> MINING SITE${number(surface.signals) === 1 ? "" : "S"}`);
  // Each fact in one piece: the strip wraps between them, never inside one.
  facts.innerHTML = parts.map((part) => `<i class="fact">${part}</i>`).join(" · ");
  root.setAttribute("aria-label", `Rhino map: ${body}`);
}

function draw() {
  if (!model.you) return;
  glideSurface(model);
  drawSurfaceStrip(model);
}

function render(snapshot = {}) {
  const effects = snapshot.effects || {};
  palette = window.VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, effects);
  model = snapshot.rhino || {};
  // Drawn at another scale than its window was sized for, it fits itself
  // (overlayfix.md): the square map's design size is its design width.
  window.VoidCompassOverlay.fitToWindow(root, designSize(), effects);
  draw();
}

const designSize = () => number(model.size, 240);

new ResizeObserver(() => draw()).observe(map);
window.__rhinomap = {model: () => model, frame: () => {
  if (!model.you) return null;
  const {turn, half, scale} = surfaceFrame(model, fit(marks));
  return {turn, half, scale};
}};
// The map and its strip, as tall as at the design width: the window follows.
window.VoidCompassOverlay.startPolling({token, overlay, render,
  contentHeight: () => window.VoidCompassOverlay.designHeight(root, designSize()), interval: 500});
