// Rhino Map (5.5.18): the ground round you while you work the Rhino, in an
// overlay of its own. The drawing is /assets/rhino-draw.js, shared with the
// deck's Rhino page.
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
const Draw = window.VoidCompassRhinoDraw;

let model = {};
let palette = {};

const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const ease = (t) => 1 - Math.pow(1 - t, 3);

// You, your heading and the zoom glide between updates (about twice a
// second) instead of jumping.
let surfaceView = null;
let surfaceGlide = 0;
const SURFACE_GLIDE_MS = 600;

function surfaceTarget(surface) {
  return {x: number(surface.you?.at?.[0]), y: number(surface.you?.at?.[1]),
    heading: number(surface.you?.heading), half: Math.max(50, number(surface.half_m, 150))};
}

function textScale() {
  return Number(getComputedStyle(document.documentElement).getPropertyValue("--scale")) || 1;
}

function drawSurface(surface) {
  const view = {...(surfaceView || surfaceTarget(surface)), up: surface.up};
  const drawn = Draw.draw(marks, surface, view, palette, {textScale: textScale()});
  ring.style.left = `${drawn.youSpot[0]}px`;
  ring.style.top = `${drawn.youSpot[1]}px`;
  ring.hidden = false;
  return drawn;
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

let shownRange = "";
let rangeFlash = 0;

function drawSurfaceStrip(surface) {
  const body = String(surface.body || "");
  regionLabel.textContent = surface.signal != null ? `SIGNAL ${surface.signal}` : surface.vehicle === "RHINO" ? "RHINO MAP" : "GROUND MAP";
  // Which way is up, and the map's range: it lights up a moment when the
  // range hotkey changes it.
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
  const metres = Draw.metres;
  const parts = [];
  if (surface.tracing) parts.push(`<span class="route">TRACING · DRIVE BACK TO THE START</span>`);
  const words = Draw.rigWords(surface);
  if (words) parts.push(words.tone ? `<span class="${words.tone === "edge" ? "edge" : words.tone}">${words.text}</span>` : words.text);
  const rigs = surface.rigs || [];
  const nextRig = rigs.find((rig) => rig.slot === surface.next_rig);
  if (nextRig && !nextRig.here && !(surface.too_far || []).length) parts.push(`RIG ${nextRig.slot} <b>${metres(number(nextRig.distance))}</b>`);
  else if (!rigs.length && surface.vehicle === "RHINO" && !surface.next_deposit) parts.push("NO RIGS MARKED");
  const following = Draw.nextWords(surface);
  if (following && !rigs.length) parts.push(`<b>${following}</b>`);
  if (surface.circle) parts.push(number(surface.circle.room) >= 0 ? `CIRCLE <b>${metres(number(surface.circle.room))}</b> LEFT` : `<span class="warn">OUTSIDE CIRCLE ${metres(-number(surface.circle.room))}</span>`);
  if (surface.survey?.edge) parts.push(`SWEPT <b>${Math.floor(number(surface.survey.percent))}%</b>`);
  else if (surface.survey) parts.push(surface.survey.edge_ok ? `MARK THE <b>SURVEY EDGE</b> HERE?` : `SURVEY · <b>DRIVE TO ITS EDGE</b>`);
  if (surface.ship?.distance != null) parts.push(`SHIP <b>${metres(number(surface.ship.distance))}</b>`);
  if (number(surface.signals) > 0 && surface.signal == null) parts.push(`<b>${number(surface.signals)}</b> MINING SITE${number(surface.signals) === 1 ? "" : "S"}`);
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
  const {turn, scale} = drawSurface(model);
  return {turn, half: (surfaceView || surfaceTarget(model)).half, scale};
}};
// The map and its strip, as tall as at the design width: the window follows.
window.VoidCompassOverlay.startPolling({token, overlay, render,
  contentHeight: () => window.VoidCompassOverlay.designHeight(root, designSize()), interval: 500});
