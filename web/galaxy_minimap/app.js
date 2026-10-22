// Galaxy Minimap (5.5.3.7): the Milky Way from the Codex region map, the
// same raster (and the same regions.js) as the Galactic Atlas, with you on
// it: the here and now. The trail of this session's jumps, the route you've
// plotted (waypoint by waypoint, to its end), Sol and the galactic core.
//
// Two canvases: the galaxy, drawn again only when the view, size or theme
// changes, and the marks over it, drawn when the model changes. The ring
// round you is CSS, so nothing redraws every frame.
import {decodeRegions} from "/galactic_map/regions.js";

const params = new URLSearchParams(location.search);
const token = params.get("token") || "";
const overlay = params.get("overlay") || "galaxy-minimap";
const root = document.getElementById("minimap");
const map = document.getElementById("map");
const galaxy = document.getElementById("galaxy");
const marks = document.getElementById("marks");
const ring = document.getElementById("here-ring");
const charting = document.getElementById("charting");
const regionLabel = document.getElementById("region");
const viewMode = document.getElementById("view-mode");
// The view it's on, short, in the strip (Studio: Your route, Around you,
// Whole galaxy).
const VIEW_NAMES = {route: "ROUTE", local: "LOCAL", galaxy: "GALAXY"};
const facts = document.getElementById("facts");

// The whole galaxy, centred on the core (Sagittarius A* sits at z 25,900),
// and the close-up around you.
const CORE = {x: 25.2, z: 25900};
const GALAXY_HALF = 46000;
const LOCAL_HALF = 8000;

let regions = null;
let model = {};
let palette = {};
let backdropKey = "";
// Where to name the regions on show: the middle of each one's visible part
// (5.5.3.7), worked out with the galaxy and drawn under the marks.
let regionSpots = [];
// Smooth moves (5.5.3.7): the view and where you are as last shown, the view
// the galaxy layer was drawn for, and the glide under way.
let shownView = null;
let shownHere = null;
let galaxyView = null;
let gliding = 0;
const GLIDE_MS = 750;

const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const ly = (value) => Math.round(number(value)).toLocaleString("en-GB");

function rgb(hex, fallback = [0, 209, 255]) {
  const match = /^#?([0-9a-f]{6})$/i.exec(String(hex || "").trim());
  if (!match) return fallback;
  const value = parseInt(match[1], 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}
const css = (colour, alpha) => `rgba(${colour[0]}, ${colour[1]}, ${colour[2]}, ${alpha})`;

// The view: which square of the galactic plane the map shows.
// "Your route" (5.5.3.7, the default): framed on you, this session's trail
// and the route ahead, so they fill the map instead of a few pixels of it.
const ROUTE_MIN_HALF = 1000;

function routeFrame() {
  const points = [...(model.trail || []), ...((model.route && model.route.points) || []), ...((model.trip && model.trip.points) || [])];
  if (model.here) points.push([number(model.here.x), number(model.here.z)]);
  if (!points.length) return null;
  const xs = points.map((point) => number(point[0])), zs = points.map((point) => number(point[1]));
  const minX = Math.min(...xs), maxX = Math.max(...xs), minZ = Math.min(...zs), maxZ = Math.max(...zs);
  const half = Math.max(ROUTE_MIN_HALF, Math.max(maxX - minX, maxZ - minZ) / 2 * 1.25);
  return {centre: {x: (minX + maxX) / 2, z: (minZ + maxZ) / 2}, half};
}

function bounds() {
  const here = model.here;
  const view = model.options?.view;
  let centre = CORE, half = GALAXY_HALF, local = false;
  if (view === "local" && here) {
    centre = {x: number(here.x), z: number(here.z)};
    half = LOCAL_HALF;
    local = true;
  } else if (view === "route") {
    const frame = routeFrame();
    if (frame) ({centre, half} = frame);
    local = Boolean(frame);
  }
  return {left: centre.x - half, right: centre.x + half, top: centre.z + half, bottom: centre.z - half, span: half * 2, local};
}

function project(view, width, height, x, z) {
  return [(x - view.left) / view.span * width, (view.top - z) / view.span * height];
}

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

// A star's worth of sparkle per world cell, the same every redraw.
function hash(x, z) {
  let h = (Math.imul(x | 0, 374761393) + Math.imul(z | 0, 668265263)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

// The galaxy: each region's glow (bright arms, dark gaps), a sparkle of
// stars where it is bright, the borders between regions, and the region
// you're in picked out.
function drawGalaxy(view = bounds()) {
  const size = fit(galaxy);
  galaxy.style.removeProperty("transform");
  galaxyView = view;
  const hereId = model.here && regions ? regions.idAt(number(model.here.x), number(model.here.z)) : 0;
  const key = JSON.stringify([view.left, view.top, view.span, size.width, size.height, palette.accent, palette.text, palette.orange, hereId, Boolean(regions)]);
  if (key === backdropKey) return;
  backdropKey = key;
  const context = galaxy.getContext("2d");
  context.clearRect(0, 0, size.width, size.height);
  if (!regions) return;
  const light = rgb(palette.text, [220, 232, 239]);
  const accent = rgb(palette.accent);
  const hud = rgb(palette.orange, [255, 122, 24]);
  const warm = rgb(palette.yellow, [255, 209, 102]);
  const image = context.createImageData(size.width, size.height);
  const pixels = image.data;
  const step = view.span / size.width;
  const glow = regions.glow;
  const glowScale = glow.size / regions.extent;
  // Fewer stars in the close-up, where each pixel covers far less sky.
  const starDensity = view.local ? .45 : 1;
  const ids = new Uint8Array((size.width + 1) * (size.height + 1));
  for (let py = 0; py <= size.height; py += 1) {
    const z = view.top - (py + .5) * step;
    for (let px = 0; px <= size.width; px += 1) ids[py * (size.width + 1) + px] = regions.idAt(view.left + (px + .5) * step, z);
  }
  for (let py = 0; py < size.height; py += 1) {
    const z = view.top - (py + .5) * step;
    const gz = Math.floor((z - regions.z0) * glowScale);
    for (let px = 0; px < size.width; px += 1) {
      const id = ids[py * (size.width + 1) + px];
      if (!id) continue;
      const x = view.left + (px + .5) * step;
      const gx = Math.floor((x - regions.x0) * glowScale);
      const g = gz >= 0 && gz < glow.size && gx >= 0 && gx < glow.size ? glow.data[gz * glow.size + gx] / 255 : 0;
      // Dark between the arms; the light gathers along them, fading out
      // from the core, with a warm bulge at the centre.
      const fromCore = Math.hypot(x - CORE.x, z - CORE.z);
      const disc = Math.exp(-Math.pow(fromCore / 26000, 1.7));
      const bulge = Math.exp(-Math.pow(fromCore / 5200, 2));
      const level = Math.min(1, Math.pow(g, 1.6) * (.3 + .7 * disc) + .5 * bulge);
      const mix = .15 + .7 * level;
      let r = light[0] * mix + accent[0] * (1 - mix);
      let gg = light[1] * mix + accent[1] * (1 - mix);
      let b = light[2] * mix + accent[2] * (1 - mix);
      if (bulge > .02) { r = r + (warm[0] - r) * bulge * .6; gg = gg + (warm[1] - gg) * bulge * .6; b = b + (warm[2] - b) * bulge * .6; }
      let a = .02 + .36 * level;
      // Stars, one pixel each, anchored to the galaxy (not the window), so
      // they hold still as you move; more of them in the bright arms.
      const cell = hash(Math.floor(x / step), Math.floor(z / step));
      if (cell < (.006 + .055 * level) * starDensity) {
        const shine = .35 + .6 * hash(Math.floor(z / step), Math.floor(x / step));
        r = r + (255 - r) * shine; gg = gg + (255 - gg) * shine; b = b + (255 - b) * shine;
        a = Math.min(1, a + .5 * shine);
      }
      if (id === hereId) { r = r * .88 + hud[0] * .12; gg = gg * .88 + hud[1] * .12; b = b * .88 + hud[2] * .12; a += .05; }
      const right = ids[py * (size.width + 1) + px + 1], below = ids[(py + 1) * (size.width + 1) + px];
      if (right !== id || below !== id) {
        const mine = id === hereId || right === hereId || below === hereId;
        const border = mine ? hud : accent;
        r = border[0]; gg = border[1]; b = border[2]; a = Math.max(a, mine ? .6 : .22);
      }
      const at = (py * size.width + px) * 4;
      pixels[at] = r; pixels[at + 1] = gg; pixels[at + 2] = b; pixels[at + 3] = Math.round(Math.min(1, a) * 255);
    }
  }
  context.putImageData(image, 0, 0);
  // Each region's share of the map and the middle of what's in view.
  const sums = new Map();
  const stride = Math.max(1, Math.round(size.ratio * 2));
  for (let py = 0; py < size.height; py += stride) {
    for (let px = 0; px < size.width; px += stride) {
      const id = ids[py * (size.width + 1) + px];
      if (!id) continue;
      const sum = sums.get(id) || [0, 0, 0];
      sum[0] += px; sum[1] += py; sum[2] += 1;
      sums.set(id, sum);
    }
  }
  const cells = (size.width / stride) * (size.height / stride);
  regionSpots = [...sums.entries()]
    .filter(([, sum]) => sum[2] / cells >= .035)
    .sort((a, b) => b[1][2] - a[1][2])
    .map(([id, sum]) => ({id, name: regions.names[id] || "", x: sum[0] / sum[2] / size.ratio, y: sum[1] / sum[2] / size.ratio}));
}

// What's on the map: this session's trail, Sol, the core, the route ahead
// and you.
function drawMarks(view = bounds(), hereWorld = null, gliding = false) {
  const size = fit(marks);
  const context = marks.getContext("2d");
  context.setTransform(size.ratio, 0, 0, size.ratio, 0, 0);
  context.clearRect(0, 0, size.cssWidth, size.cssHeight);
  const at = (x, z) => project(view, size.cssWidth, size.cssHeight, x, z);
  const inside = ([px, py]) => px >= -4 && py >= -4 && px <= size.cssWidth + 4 && py <= size.cssHeight + 4;
  const hud = rgb(palette.orange, [255, 122, 24]);
  const green = rgb(palette.green, [78, 229, 155]), yellow = rgb(palette.yellow, [255, 209, 102]);
  const text = rgb(palette.text, [220, 232, 239]);
  const accent = rgb(palette.accent, [0, 209, 255]);
  const label = (words, [px, py], colour) => {
    context.font = `700 ${view.local ? 8 : 7.5}px Bahnschrift, "Segoe UI", sans-serif`;
    context.fillStyle = css(colour, .85);
    context.fillText(words, Math.min(size.cssWidth - context.measureText(words).width - 3, px + 5), Math.max(9, py - 4));
  };

  // The regions' names, small and quiet, under everything else; the one
  // you're in, in the HUD's colour. Names that would overlap are left out.
  if (model.options?.labels !== false && regions && !gliding) {
    const scale = Number(getComputedStyle(document.documentElement).getPropertyValue("--scale")) || 1;
    // Their own size from Overlay Studio (5.5.4), or the minimap's text size.
    const own = number(model.options?.region_text);
    const fontSize = 6.6 * (own > 0 ? own / 100 : scale);
    context.font = `700 ${fontSize}px Bahnschrift, "Segoe UI", sans-serif`;
    context.textAlign = "center"; context.textBaseline = "middle";
    const hereId = model.here ? regions.idAt(number(model.here.x), number(model.here.z)) : 0;
    const placed = [];
    for (const spot of regionSpots) {
      const words = spot.name.toUpperCase().split(" ");
      let lines = [words.join(" ")];
      if (context.measureText(lines[0]).width > size.cssWidth * .5 && words.length > 1) {
        // Two lines, split nearest the middle.
        let best = 1, gap = Infinity;
        for (let cut = 1; cut < words.length; cut += 1) {
          const diff = Math.abs(context.measureText(words.slice(0, cut).join(" ")).width - context.measureText(words.slice(cut).join(" ")).width);
          if (diff < gap) { gap = diff; best = cut; }
        }
        lines = [words.slice(0, best).join(" "), words.slice(best).join(" ")];
      }
      const width = Math.max(...lines.map((line) => context.measureText(line).width)) + 4;
      const height = lines.length * fontSize * 1.15 + 2;
      const x = Math.min(size.cssWidth - width / 2 - 2, Math.max(width / 2 + 2, spot.x));
      const y = Math.min(size.cssHeight - height / 2 - 2, Math.max(height / 2 + 2, spot.y));
      const box = [x - width / 2, y - height / 2, x + width / 2, y + height / 2];
      if (placed.some((other) => box[0] < other[2] && box[2] > other[0] && box[1] < other[3] && box[3] > other[1])) continue;
      placed.push(box);
      const mine = spot.id === hereId;
      lines.forEach((line, index) => {
        const ly = y + (index - (lines.length - 1) / 2) * fontSize * 1.15;
        context.lineWidth = 2.6; context.strokeStyle = "rgba(0, 0, 0, .75)";
        context.strokeText(line, x, ly);
        context.fillStyle = mine ? css(hud, .95) : css(text, .62);
        context.fillText(line, x, ly);
      });
    }
    context.textAlign = "start"; context.textBaseline = "alphabetic";
  }

  // Sol, and in the whole galaxy the core.
  const sol = at(0, 0);
  if (inside(sol)) {
    context.fillStyle = css(yellow, .9);
    context.beginPath(); context.arc(sol[0], sol[1], 1.8, 0, Math.PI * 2); context.fill();
    label("SOL", sol, yellow);
  }
  // Your home, when it isn't Sol (5.5.4): a small house-shaped diamond.
  const home = model.home;
  if (home && home.custom) {
    const spot = at(number(home.x), number(home.z));
    if (inside(spot)) {
      context.strokeStyle = css(yellow, .95); context.lineWidth = 1.2;
      context.beginPath();
      context.moveTo(spot[0], spot[1] - 3.5); context.lineTo(spot[0] + 3, spot[1]);
      context.lineTo(spot[0], spot[1] + 3.5); context.lineTo(spot[0] - 3, spot[1]); context.closePath();
      context.stroke();
      label(String(home.name || "HOME").toUpperCase(), spot, yellow);
    }
  }
  if (!view.local) {
    const core = at(CORE.x, CORE.z);
    context.strokeStyle = css(text, .45); context.lineWidth = 1;
    context.beginPath();
    context.moveTo(core[0] - 3, core[1]); context.lineTo(core[0] + 3, core[1]);
    context.moveTo(core[0], core[1] - 3); context.lineTo(core[0], core[1] + 3);
    context.stroke();
  }

  // This session's trail, fading back to where it began.
  const trail = (model.trail || []).map((point) => at(number(point[0]), number(point[1])));
  context.lineCap = "round"; context.lineJoin = "round";
  // A dark casing under the line, so it reads over the bright arms.
  if (trail.length > 1) {
    context.strokeStyle = "rgba(0, 0, 0, .65)"; context.lineWidth = 4.2;
    context.beginPath(); context.moveTo(...trail[0]);
    for (const point of trail.slice(1)) context.lineTo(...point);
    context.stroke();
  }
  for (let index = 1; index < trail.length; index += 1) {
    const age = index / Math.max(1, trail.length - 1);
    context.strokeStyle = css(hud, .45 + .55 * age);
    context.lineWidth = 2.2;
    context.beginPath(); context.moveTo(...trail[index - 1]); context.lineTo(...trail[index]); context.stroke();
  }
  if (trail.length > 1) {
    // Where the session began.
    context.fillStyle = "rgba(0, 0, 0, .7)";
    context.beginPath(); context.arc(trail[0][0], trail[0][1], 3.6, 0, Math.PI * 2); context.fill();
    context.strokeStyle = css(hud, .9); context.lineWidth = 1.4;
    context.beginPath(); context.arc(trail[0][0], trail[0][1], 2.6, 0, Math.PI * 2); context.stroke();
  }

  // Your sealed time capsules (5.5.3.7): a small gold hourglass each.
  for (const point of model.capsules || []) {
    const [x, y] = at(number(point[0]), number(point[1]));
    if (!inside([x, y])) continue;
    const hourglass = () => {
      context.beginPath();
      context.moveTo(x - 3.2, y - 4); context.lineTo(x + 3.2, y - 4); context.lineTo(x - 3.2, y + 4);
      context.lineTo(x + 3.2, y + 4); context.closePath();
    };
    context.strokeStyle = "rgba(0, 0, 0, .8)"; context.lineWidth = 3; context.lineJoin = "round";
    hourglass(); context.stroke();
    context.strokeStyle = css(yellow, 1); context.lineWidth = 1.3;
    hourglass(); context.stroke();
  }

  // The route ahead, through its waypoints, to where it ends.
  const hereAt = hereWorld || (model.here ? [number(model.here.x), number(model.here.z)] : null);
  const here = hereAt ? at(hereAt[0], hereAt[1]) : null;

  // The whole trip from Spansh (5.5.3.7): your waypoint route or neutron
  // plot, beyond the leg plotted in game. Fainter, in the theme's accent,
  // under the leg; its neutron stars spiked, its end a hollow diamond.
  const trip = model.trip;
  if (trip && Array.isArray(trip.points) && trip.points.length) {
    const stops = trip.points.map((point) => at(number(point[0]), number(point[1])));
    if (here) stops.unshift(here);
    if (stops.length > 1) {
      const path = () => {
        context.beginPath(); context.moveTo(...stops[0]);
        for (const stop of stops.slice(1)) context.lineTo(...stop);
      };
      context.strokeStyle = "rgba(0, 0, 0, .55)"; context.lineWidth = 3.4;
      path(); context.stroke();
      context.strokeStyle = css(accent, .8); context.lineWidth = 1.5; context.setLineDash([2, 3]);
      path(); context.stroke();
      context.setLineDash([]);
    }
    const offset = here ? 1 : 0;
    const neutrons = Array.isArray(trip.neutron) ? trip.neutron : [];
    // Only where they're far enough apart to tell.
    let last = null;
    for (const index of neutrons) {
      const stop = stops[index + offset];
      if (!stop || !inside(stop) || (last && Math.hypot(stop[0] - last[0], stop[1] - last[1]) < 7)) continue;
      last = stop;
      context.strokeStyle = "rgba(0, 0, 0, .7)"; context.lineWidth = 2.6;
      context.beginPath();
      context.moveTo(stop[0] - 3.5, stop[1]); context.lineTo(stop[0] + 3.5, stop[1]);
      context.moveTo(stop[0], stop[1] - 3.5); context.lineTo(stop[0], stop[1] + 3.5);
      context.stroke();
      context.strokeStyle = css(accent, 1); context.lineWidth = 1;
      context.stroke();
    }
    let end = stops[stops.length - 1];
    if (!inside(end) && here) {
      const dx = end[0] - here[0], dy = end[1] - here[1];
      const scale = Math.min(Math.abs((dx > 0 ? size.cssWidth - 6 - here[0] : here[0] - 6) / (dx || 1e-6)),
        Math.abs((dy > 0 ? size.cssHeight - 6 - here[1] : here[1] - 6) / (dy || 1e-6)));
      end = [here[0] + dx * scale, here[1] + dy * scale];
    }
    const diamond = (r) => {
      context.beginPath();
      context.moveTo(end[0], end[1] - r); context.lineTo(end[0] + r, end[1]);
      context.lineTo(end[0], end[1] + r); context.lineTo(end[0] - r, end[1]); context.closePath();
    };
    context.fillStyle = "rgba(0, 0, 0, .75)"; diamond(6.5); context.fill();
    context.strokeStyle = css(accent, 1); context.lineWidth = 1.6; diamond(4.2); context.stroke();
  }
  const route = model.route;
  if (route && Array.isArray(route.points) && route.points.length > 1) {
    const stops = route.points.map((point) => at(number(point[0]), number(point[1])));
    if (here) stops[0] = here;
    const path = () => {
      context.beginPath(); context.moveTo(...stops[0]);
      for (const stop of stops.slice(1)) context.lineTo(...stop);
    };
    context.strokeStyle = "rgba(0, 0, 0, .65)"; context.lineWidth = 4.2;
    path(); context.stroke();
    context.strokeStyle = css(green, .95); context.lineWidth = 2; context.setLineDash([5, 3]);
    path(); context.stroke();
    context.setLineDash([]);
    // Each waypoint's star, where they're far enough apart to tell:
    // scoopable stars warm, neutron stars bright with spikes, white dwarfs
    // as rings, the rest small. Dense routes show only the special ones.
    const kinds = Array.isArray(route.stars) ? route.stars : [];
    const spread = Math.hypot(stops[stops.length - 1][0] - stops[0][0], stops[stops.length - 1][1] - stops[0][1]);
    const roomy = stops.length <= 120 && spread / stops.length > 3.5;
    const neutron = [190, 236, 255];
    stops.forEach((stop, index) => {
      if (index === 0 || index === stops.length - 1) return;
      const kind = kinds[index] || "";
      if (!roomy && !kind) return;
      context.fillStyle = "rgba(0, 0, 0, .75)";
      context.beginPath(); context.arc(stop[0], stop[1], kind ? 3.6 : 2.4, 0, Math.PI * 2); context.fill();
      if (kind === "scoop") {
        context.fillStyle = css(yellow, 1);
        context.beginPath(); context.arc(stop[0], stop[1], 2.4, 0, Math.PI * 2); context.fill();
      } else if (kind === "neutron") {
        context.strokeStyle = css(neutron, 1); context.lineWidth = 1.2;
        context.beginPath();
        context.moveTo(stop[0] - 4.5, stop[1]); context.lineTo(stop[0] + 4.5, stop[1]);
        context.moveTo(stop[0], stop[1] - 4.5); context.lineTo(stop[0], stop[1] + 4.5);
        context.stroke();
        context.fillStyle = "#ffffff";
        context.beginPath(); context.arc(stop[0], stop[1], 1.8, 0, Math.PI * 2); context.fill();
      } else if (kind === "dwarf") {
        context.strokeStyle = "#ffffff"; context.lineWidth = 1.3;
        context.beginPath(); context.arc(stop[0], stop[1], 2.3, 0, Math.PI * 2); context.stroke();
      } else {
        context.fillStyle = css(green, .9);
        context.beginPath(); context.arc(stop[0], stop[1], 1.3, 0, Math.PI * 2); context.fill();
      }
    });
    let end = stops[stops.length - 1];
    if (!inside(end) && here) {
      // Off the close-up: on the edge, in its direction.
      const dx = end[0] - here[0], dy = end[1] - here[1];
      const scale = Math.min(Math.abs((dx > 0 ? size.cssWidth - 6 - here[0] : here[0] - 6) / (dx || 1e-6)),
        Math.abs((dy > 0 ? size.cssHeight - 6 - here[1] : here[1] - 6) / (dy || 1e-6)));
      end = [here[0] + dx * scale, here[1] + dy * scale];
    }
    const diamond = (r) => {
      context.beginPath();
      context.moveTo(end[0], end[1] - r); context.lineTo(end[0] + r, end[1]);
      context.lineTo(end[0], end[1] + r); context.lineTo(end[0] - r, end[1]); context.closePath();
    };
    context.fillStyle = "rgba(0, 0, 0, .75)"; diamond(6.5); context.fill();
    context.fillStyle = css(green, 1); diamond(4.8); context.fill();
  }

  // A scale bar in the corner: a round number of light years, about a
  // fifth of the map wide.
  const perPixel = view.span / size.cssWidth;
  const lengths = [100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000];
  const lengthLy = lengths.find((value) => value / perPixel >= size.cssWidth * .18) || lengths[lengths.length - 1];
  const bar = lengthLy / perPixel;
  const barX = 7, barY = size.cssHeight - 8;
  context.strokeStyle = "rgba(0, 0, 0, .7)"; context.lineWidth = 3.4;
  const barPath = () => {
    context.beginPath();
    context.moveTo(barX, barY - 3); context.lineTo(barX, barY); context.lineTo(barX + bar, barY); context.lineTo(barX + bar, barY - 3);
  };
  barPath(); context.stroke();
  context.strokeStyle = css(text, .85); context.lineWidth = 1.2;
  barPath(); context.stroke();
  const scaleText = `${lengthLy.toLocaleString("en-GB")} LY`;
  context.font = `700 ${7 * (Number(getComputedStyle(document.documentElement).getPropertyValue("--scale")) || 1)}px Bahnschrift, "Segoe UI", sans-serif`;
  context.lineWidth = 2.4; context.strokeStyle = "rgba(0, 0, 0, .75)";
  context.strokeText(scaleText, barX + 1, barY - 5);
  context.fillStyle = css(text, .85);
  context.fillText(scaleText, barX + 1, barY - 5);

  // You.
  if (here && inside(here)) {
    // A reticle round you: four ticks, then the dot with a white rim.
    context.strokeStyle = "rgba(0, 0, 0, .7)"; context.lineWidth = 3.4;
    const ticks = () => {
      context.beginPath();
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        context.moveTo(here[0] + dx * 7, here[1] + dy * 7); context.lineTo(here[0] + dx * 12, here[1] + dy * 12);
      }
    };
    ticks(); context.stroke();
    context.strokeStyle = css(hud, 1); context.lineWidth = 1.6;
    ticks(); context.stroke();
    context.fillStyle = "rgba(0, 0, 0, .8)";
    context.beginPath(); context.arc(here[0], here[1], 5.6, 0, Math.PI * 2); context.fill();
    context.fillStyle = "#ffffff";
    context.beginPath(); context.arc(here[0], here[1], 4.4, 0, Math.PI * 2); context.fill();
    context.fillStyle = css(hud, 1);
    context.beginPath(); context.arc(here[0], here[1], 3.1, 0, Math.PI * 2); context.fill();
    ring.style.left = `${here[0]}px`;
    ring.style.top = `${here[1]}px`;
    ring.hidden = false;
  } else {
    ring.hidden = true;
  }
}

function drawStrip() {
  const here = model.here;
  regionLabel.textContent = here?.region || (here ? "Deep space" : "Awaiting position");
  viewMode.textContent = VIEW_NAMES[model.options?.view] || VIEW_NAMES.route;
  const parts = [];
  const homeName = model.home && model.home.custom ? String(model.home.name || "HOME").toUpperCase() : "SOL";
  if (here) parts.push(`<b>${ly(here.from_home ?? here.from_sol)}</b> LY FROM ${escape(homeName)}`);
  if (model.trip && model.trip.distance != null) {
    const jumps = number(model.trip.jumps);
    // No system names in the strip (the Nav HUD has them): the trip's
    // length, in the accent its line is drawn in.
    parts.push(`<span class="trip">▸ ${ly(model.trip.distance)} LY${jumps ? ` · ${ly(jumps)} JUMP${jumps === 1 ? "" : "S"}` : ""}</span>`);
  } else if (model.route && model.route.distance != null) {
    const jumps = number(model.route.jumps);
    parts.push(`<span class="route">▸ ${ly(model.route.distance)} LY${jumps ? ` · ${ly(jumps)} JUMP${jumps === 1 ? "" : "S"}` : ""}</span>`);
  } else if (number(model.session_jumps) > 0) {
    parts.push(`<b>${ly(model.session_jumps)}</b> JUMP${number(model.session_jumps) === 1 ? "" : "S"} THIS SESSION`);
  } else if (number(model.regions_visited) > 0) {
    parts.push(`<b>${ly(model.regions_visited)}</b> OF ${ly(model.regions_total || 42)} REGIONS`);
  }
  facts.innerHTML = parts.join(" · ");
  root.setAttribute("aria-label", here ? `Galaxy minimap: ${here.system || ""}, ${here.region || "deep space"}` : "Galaxy minimap");
}

function escape(text) {
  return String(text ?? "").replace(/[&<>"']/g, (ch) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"}[ch]));
}

// The Rhino map (5.5.17): while you drive on a planet the minimap shows the
// ground round you instead of the galaxy. Metres east and north of the
// ship, turned so you head up (or north up), zoomed to fit the ship, your
// rigs and where you've drilled.
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

function drawSurfaceStrip(surface) {
  const body = String(surface.body || "");
  regionLabel.textContent = surface.vehicle === "RHINO" ? "RHINO MAP" : "GROUND MAP";
  viewMode.textContent = surface.up === "north" ? "NORTH UP" : "HEADING UP";
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
  facts.innerHTML = parts.join(" · ");
  root.setAttribute("aria-label", `Rhino map: ${body}`);
}

const ease = (t) => 1 - Math.pow(1 - t, 3);

// From one view to the next: the galaxy layer is moved and scaled as it
// stands (no redrawing it every frame), the marks are drawn for the view
// between, and you slide from where you were. The galaxy is drawn afresh
// for the new view at the end.
function glide(from, to, fromHere, toHere) {
  cancelAnimationFrame(gliding);
  const started = performance.now();
  const step = (now) => {
    const t = ease(Math.min(1, (now - started) / GLIDE_MS));
    const span = Math.exp(Math.log(from.span) + (Math.log(to.span) - Math.log(from.span)) * t);
    const cx = (from.left + from.span / 2) + ((to.left + to.span / 2) - (from.left + from.span / 2)) * t;
    const cz = (from.top - from.span / 2) + ((to.top - to.span / 2) - (from.top - from.span / 2)) * t;
    const view = {left: cx - span / 2, right: cx + span / 2, top: cz + span / 2, bottom: cz - span / 2, span, local: to.local};
    if (galaxyView) {
      const box = map.getBoundingClientRect();
      const scale = galaxyView.span / view.span;
      const tx = (galaxyView.left - view.left) / view.span * box.width;
      const ty = (view.top - galaxyView.top) / view.span * box.height;
      galaxy.style.transformOrigin = "0 0";
      galaxy.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    }
    const hereNow = fromHere && toHere
      ? [fromHere[0] + (toHere[0] - fromHere[0]) * t, fromHere[1] + (toHere[1] - fromHere[1]) * t] : toHere;
    drawMarks(view, hereNow, t < 1);
    if (t < 1) {
      gliding = requestAnimationFrame(step);
    } else {
      gliding = 0;
      backdropKey = "";
      drawGalaxy(to);
      drawMarks(to);
    }
  };
  gliding = requestAnimationFrame(step);
}

function draw() {
  const surface = model.surface;
  root.classList.toggle("surface", Boolean(surface));
  if (surface) {
    cancelAnimationFrame(gliding);
    gliding = 0;
    // Back to the galaxy later: appear there, no glide from the ground.
    shownView = null;
    shownHere = null;
    glideSurface(surface);
    drawSurfaceStrip(surface);
    return;
  }
  // Back to the galaxy: the next ground view starts afresh.
  cancelAnimationFrame(surfaceGlide);
  surfaceView = null;
  const target = bounds();
  const here = model.here ? [number(model.here.x), number(model.here.z)] : null;
  const moved = shownView && (Math.abs(shownView.left - target.left) > 1 || Math.abs(shownView.top - target.top) > 1
    || Math.abs(shownView.span - target.span) > 1);
  const stepped = shownHere && here && (shownHere[0] !== here[0] || shownHere[1] !== here[1]);
  // Only once you've been shown somewhere: the first view just appears.
  const still = root.classList.contains("reduced-motion") || !regions || !shownHere || !here;
  if (!still && (moved || stepped)) {
    glide(shownView, target, shownHere, here);
  } else if (!gliding) {
    drawGalaxy(target);
    drawMarks(target);
  }
  shownView = target;
  shownHere = here;
  drawStrip();
}

function render(snapshot = {}) {
  const effects = snapshot.effects || {};
  palette = window.VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, effects);
  model = snapshot.minimap || {};
  draw();
}

// The region raster, once: the same one the Galactic Atlas draws from.
async function loadRegions() {
  try {
    const response = await fetch(`/api/file?token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}&name=regions`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    regions = decodeRegions(await response.json());
    charting.classList.add("done");
    backdropKey = "";
    draw();
  } catch (_error) {
    charting.textContent = "NO MAP";
  }
}

new ResizeObserver(() => { backdropKey = ""; shownView = null; draw(); }).observe(map);
window.__minimap = {bounds, project, ready: () => Boolean(regions), model: () => model, spots: () => regionSpots,
  surface: () => {
    if (!model.surface) return null;
    const {turn, half, scale} = surfaceFrame(model.surface, fit(marks));
    return {turn, half, scale};
  }};
window.VoidCompassOverlay.startPolling({token, overlay, render, contentHeight: () => document.body.getBoundingClientRect().height, interval: 500});
loadRegions();
