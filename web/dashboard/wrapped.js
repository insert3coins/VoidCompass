// Void Wrapped (5.5.10): your year in Elite, told as a story you click
// through. Python finds the story (exploration/void_wrapped.py); this page
// tells it: one animated card after another on a canvas, each one saved or
// copied as a picture for Discord, and the whole year saved at once.

const W = 1080, H = 1350;          // a card's design size (4:5)
const EXPORT_SCALE = 1;            // saved cards are 1080 × 1350
const DURATIONS = {intro: 5.5, verdict: 12, finale: 14, distance: 8, rare: 8, constellations: 8};
const NAMES = {
  intro: "Your year", distance: "Light years", jumps: "Jumps", time: "Hours", busiest: "Busiest night",
  longest_jump: "Longest jump", furthest: "Furthest out", regions: "Where you lived", home: "Home",
  discoveries: "First discoveries", rare: "Rarest find", codex: "Codex personality", biology: "Organics",
  money: "Credits", bgs: "Factions", music: "Soundtrack", postcards: "Postcards", constellations: "Constellations",
  achievements: "Achievements", combat: "Combat", everyday: "The everyday", deaths: "Rebuys", places: "Places", hatchling: "Along for the ride", verdict: "The verdict", finale: "The whole year",
};
const PALETTES = {
  intro: ["#070a22", "#341060", "#7ae7ff"], distance: ["#03101f", "#0b3d6e", "#5be0ff"],
  jumps: ["#14081f", "#521a6e", "#ff7ad9"], time: ["#170c04", "#5a2c08", "#ffb648"],
  busiest: ["#1c0712", "#6b1032", "#ff6b8a"], longest_jump: ["#03141a", "#0a5560", "#4dfff0"],
  furthest: ["#0b0b1c", "#2c2c80", "#b3acff"], regions: ["#05170f", "#0e5a3a", "#5cf0a4"],
  home: ["#1a1005", "#6b4610", "#ffd27a"], discoveries: ["#05101c", "#0c3c6a", "#6fd3ff"],
  rare: ["#071509", "#1f5a2a", "#a6ff8f"], codex: ["#140922", "#4b1d7a", "#c792ff"],
  biology: ["#05170d", "#1d6b3a", "#7dffa8"], money: ["#171204", "#5e4b0b", "#ffe066"],
  bgs: ["#190707", "#6b1d16", "#ff8a5c"], music: ["#0a081c", "#3f1468", "#ff5ce1"],
  postcards: ["#181007", "#5a3b14", "#ffcf8a"], constellations: ["#04081a", "#16205e", "#a3b5ff"],
  achievements: ["#181204", "#6b520b", "#ffd84d"], deaths: ["#170405", "#5a0b10", "#ff5c66"],
  places: ["#04130f", "#0f4a3c", "#6fffd2"],
  hatchling: ["#06140f", "#14523a", "#9dffd2"],
  combat: ["#170506", "#5e1012", "#ff4d4d"], everyday: ["#08121a", "#174256", "#7fd8ff"],
  verdict: ["#040509", "#141826", "#00d1ff"], finale: ["#05070c", "#0f2033", "#00d1ff"],
};
const SANS = '"Bahnschrift SemiBold", "Bahnschrift", "Segoe UI", sans-serif';
const LIGHT = '"Bahnschrift Light", "Bahnschrift", "Segoe UI", sans-serif';
const MONO = 'Consolas, "Cascadia Mono", monospace';
const SERIF = 'Georgia, "Times New Roman", serif';
const INK = "#f3f7ff", SOFT = "rgba(232, 240, 255, .72)", FAINT = "rgba(232, 240, 255, .42)";

let ui = null;
let years = [];
let year = 0;
// 5.6.1: an expedition's story, told by the same cards over its dates.
let trips = [];
let trip = "";
let tripSeq = 0;
let lastTripsKey = "";
const span = () => (story?.trip ? "trip" : "year");
const nameOf = (card) => (story?.trip && card?.kind === "intro" ? "Your trip" : story?.trip && card?.kind === "finale" ? "The whole trip"
  : NAMES[card?.kind] || card?.kind || "");
let story = null;
let fetching = 0;
let pollTimer = 0;
let lastYearsKey = "";
let images = new Map();
const player = {index: 0, start: 0, paused: true, held: false, pausedAt: 0, frame: 0, from: null, fromAt: 0, playing: false};

// -- small helpers -----------------------------------------------------------------
const clamp = (value, low = 0, high = 1) => Math.max(low, Math.min(high, value));
const ease = (t) => 1 - Math.pow(1 - clamp(t), 3);
const easeExpo = (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * clamp(t)));
const appear = (t, at, length = .7) => ease((t - at) / length);
const fmt = (value, digits = 0) => Number(value || 0).toLocaleString(undefined, {minimumFractionDigits: digits, maximumFractionDigits: digits});
const count = (value, t, at = .3, length = 1.8, digits = 0) => fmt(Number(value || 0) * easeExpo((t - at) / length), digits);

function credits(value) {
  const number = Number(value || 0);
  if (number >= 1e9) return `${(number / 1e9).toFixed(2)}B`;
  if (number >= 1e6) return `${(number / 1e6).toFixed(1)}M`;
  if (number >= 1e3) return `${Math.round(number / 1e3)}K`;
  return fmt(number);
}

function random(seed) {
  let state = seed >>> 0 || 1;
  return () => {
    state = Math.imul(state ^ (state >>> 15), 2246822507) ^ Math.imul(state ^ (state >>> 13), 3266489909);
    state ^= state >>> 16;
    return (state >>> 0) / 4294967296;
  };
}

function seedOf(text) {
  let hash = 2166136261;
  for (const char of String(text)) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  return hash >>> 0;
}

function token(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function reducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || document.body.classList.contains("reduced-motion");
}

function rgba(hex, alpha) {
  const value = String(hex || "#ffffff").replace("#", "");
  const full = value.length === 3 ? value.split("").map((c) => c + c).join("") : value.padEnd(6, "0");
  const n = parseInt(full.slice(0, 6), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function palette(card) {
  const colours = PALETTES[card.kind] || PALETTES.intro;
  if (card.kind === "verdict" || card.kind === "finale") return [colours[0], colours[1], token("--accent", colours[2])];
  return colours;
}

// -- type --------------------------------------------------------------------------------
// A canvas font: a style ("italic") goes before the size.
function fontOf(px, font) {
  return font.startsWith("italic ") ? `italic ${px}px ${font.slice(7)}` : `${px}px ${font}`;
}

function text(c, value, x, y, {size = 40, font = SANS, colour = INK, align = "left", alpha = 1, spacing = 0, max = 0, baseline = "alphabetic"} = {}) {
  if (alpha <= 0 || value === "" || value == null) return 0;
  c.save();
  c.globalAlpha *= clamp(alpha);
  let px = size;
  c.font = fontOf(px, font);
  if ("letterSpacing" in c) c.letterSpacing = `${spacing}px`;
  if (max) {
    while (px > 12 && c.measureText(String(value)).width > max) {
      px -= 2;
      c.font = fontOf(px, font);
    }
  }
  c.fillStyle = colour;
  c.textAlign = align;
  c.textBaseline = baseline;
  c.fillText(String(value), x, y);
  const width = c.measureText(String(value)).width;
  c.restore();
  return width;
}

function lines(c, value, width, size, font) {
  c.save();
  c.font = fontOf(size, font);
  const out = [];
  for (const paragraph of String(value || "").split("\n")) {
    let line = "";
    for (const word of paragraph.split(/\s+/)) {
      const next = line ? `${line} ${word}` : word;
      if (c.measureText(next).width > width && line) {
        out.push(line);
        line = word;
      } else {
        line = next;
      }
    }
    if (line) out.push(line);
  }
  c.restore();
  return out;
}

function paragraph(c, value, x, y, {width = 860, size = 38, font = SANS, colour = SOFT, leading = 1.32, alpha = 1, align = "left", chars = Infinity} = {}) {
  const rows = lines(c, value, width, size, font);
  let left = chars;
  rows.forEach((row, index) => {
    if (left <= 0) return;
    const shown = row.slice(0, Math.max(0, left));
    left -= row.length + 1;
    text(c, shown, x, y + index * size * leading, {size, font, colour, alpha, align});
  });
  return rows.length * size * leading;
}

function kicker(c, value, t, colour) {
  const a = appear(t, .05, .5);
  c.save();
  c.globalAlpha = a;
  c.fillStyle = colour;
  c.fillRect(90, 152, 46 * a, 4);
  c.restore();
  text(c, String(value).toUpperCase(), 152, 162, {size: 24, font: MONO, colour, spacing: 6, alpha: a});
}

// A big headline that slides up into place.
function headline(c, value, x, y, t, at, {size = 92, colour = INK, max = 900, font = SANS, align = "left"} = {}) {
  const a = appear(t, at, .8);
  return text(c, value, x, y + (1 - a) * 40, {size, colour, alpha: a, max, font, align});
}

// -- backgrounds ---------------------------------------------------------------------------
function backdrop(c, card, time, seed) {
  const [deep, mid, glow] = palette(card);
  const ground = c.createLinearGradient(0, 0, W * .3, H);
  ground.addColorStop(0, mid);
  ground.addColorStop(.55, deep);
  ground.addColorStop(1, "#020306");
  c.fillStyle = ground;
  c.fillRect(0, 0, W, H);
  const rng = random(seed);
  // Nebulae, drifting slowly.
  for (let index = 0; index < 4; index += 1) {
    const x = W * (.1 + rng() * .8) + Math.sin(time * .12 + index) * 30;
    const y = H * (.1 + rng() * .8) + Math.cos(time * .1 + index * 2) * 30;
    const r = 260 + rng() * 420;
    const cloud = c.createRadialGradient(x, y, 0, x, y, r);
    cloud.addColorStop(0, rgba(index % 2 ? glow : mid, .22 + rng() * .12));
    cloud.addColorStop(1, rgba(index % 2 ? glow : mid, 0));
    c.fillStyle = cloud;
    c.fillRect(0, 0, W, H);
  }
  // Stars, twinkling.
  for (let index = 0; index < 240; index += 1) {
    const x = rng() * W, y = rng() * H, size = rng() < .92 ? rng() * 1.6 + .4 : rng() * 2.6 + 1.4;
    const twinkle = .45 + .55 * Math.abs(Math.sin(time * (.4 + rng()) + index));
    c.fillStyle = `rgba(240, 246, 255, ${(.18 + rng() * .6) * twinkle})`;
    c.beginPath();
    c.arc((x + time * (4 + size * 3)) % W, y, size, 0, Math.PI * 2);
    c.fill();
  }
  // A soft vignette.
  const shade = c.createRadialGradient(W / 2, H / 2, H * .35, W / 2, H / 2, H * .85);
  shade.addColorStop(0, "rgba(0,0,0,0)");
  shade.addColorStop(1, "rgba(0,0,0,.55)");
  c.fillStyle = shade;
  c.fillRect(0, 0, W, H);
}

function footer(c, card, index, total) {
  const commander = story?.commander ? `CMDR ${story.commander}`.toUpperCase() : "";
  text(c, "VOID WRAPPED", 90, H - 74, {size: 22, font: MONO, colour: FAINT, spacing: 6});
  text(c, `${story?.elite_year || ""}${commander ? `  ·  ${commander}` : ""}`, 90, H - 42, {size: 20, font: MONO, colour: FAINT, spacing: 3});
  text(c, `${String(index + 1).padStart(2, "0")} / ${String(total).padStart(2, "0")}`, W - 90, H - 58, {size: 22, font: MONO, colour: FAINT, align: "right", spacing: 4});
}

function glowLine(c, points, colour, width = 4, progress = 1) {
  if (points.length < 2) return;
  const shown = Math.max(2, Math.floor(points.length * clamp(progress)));
  c.save();
  c.lineJoin = "round";
  c.lineCap = "round";
  c.shadowColor = colour;
  c.shadowBlur = 18;
  c.strokeStyle = colour;
  c.lineWidth = width;
  c.beginPath();
  c.moveTo(points[0][0], points[0][1]);
  for (let index = 1; index < shown; index += 1) c.lineTo(points[index][0], points[index][1]);
  c.stroke();
  c.restore();
  return points[shown - 1];
}

function dot(c, x, y, r, colour, glow = 0) {
  c.save();
  if (glow) { c.shadowColor = colour; c.shadowBlur = glow; }
  c.fillStyle = colour;
  c.beginPath();
  c.arc(x, y, r, 0, Math.PI * 2);
  c.fill();
  c.restore();
}

function statTile(c, x, y, w, label, value, t, at, colour) {
  const a = appear(t, at, .6);
  c.save();
  c.globalAlpha = a;
  c.fillStyle = "rgba(255,255,255,.06)";
  c.strokeStyle = rgba(colour, .35);
  c.lineWidth = 2;
  c.beginPath();
  c.roundRect?.(x, y + (1 - a) * 20, w, 150, 18);
  if (!c.roundRect) c.rect(x, y + (1 - a) * 20, w, 150);
  c.fill();
  c.stroke();
  c.restore();
  text(c, value, x + 28, y + 86 + (1 - a) * 20, {size: 58, colour: INK, alpha: a, max: w - 50});
  text(c, String(label).toUpperCase(), x + 28, y + 124 + (1 - a) * 20, {size: 19, font: MONO, colour: rgba(colour, .9), alpha: a, spacing: 3, max: w - 50});
}

function bars(c, rows, x, y, width, t, at, colour, {label = "name", value = "count", suffix = ""} = {}) {
  const top = Math.max(1, ...rows.map((row) => Number(row[value]) || 0));
  rows.forEach((row, index) => {
    const a = appear(t, at + index * .18, .9);
    const yy = y + index * 108;
    text(c, row[label], x, yy, {size: 36, colour: INK, alpha: a, max: width - 160});
    text(c, `${fmt(row[value])}${suffix}`, x + width, yy, {size: 32, font: SANS, colour: rgba(colour, 1), alpha: a, align: "right"});
    c.save();
    c.globalAlpha = a;
    c.fillStyle = "rgba(255,255,255,.08)";
    c.fillRect(x, yy + 22, width, 14);
    c.shadowColor = colour;
    c.shadowBlur = 14;
    c.fillStyle = colour;
    c.fillRect(x, yy + 22, width * (Number(row[value]) || 0) / top * ease((t - at - index * .18) / 1.1), 14);
    c.restore();
  });
}

// -- shapes of the galaxy ------------------------------------------------------------------
function fitTrail(trail, box) {
  const xs = trail.map((p) => p[0]), zs = trail.map((p) => p[1]);
  const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...zs) - Math.min(...zs), 40);
  const cx = (Math.max(...xs) + Math.min(...xs)) / 2, cz = (Math.max(...zs) + Math.min(...zs)) / 2;
  const scale = Math.min(box.w, box.h) * .86 / span;
  return {span, at: ([x, z]) => [box.x + box.w / 2 + (x - cx) * scale, box.y + box.h / 2 - (z - cz) * scale]};
}

function galaxyDisc(c, box, time, colour, alpha = .5) {
  // The galaxy seen from above, Sol low in the disc, the core above it.
  const cx = box.x + box.w / 2, cy = box.y + box.h / 2;
  const r = Math.min(box.w, box.h) / 2;
  c.save();
  c.globalAlpha = alpha;
  const core = c.createRadialGradient(cx, cy, 0, cx, cy, r);
  core.addColorStop(0, rgba("#fff3d6", .7));
  core.addColorStop(.18, rgba(colour, .32));
  core.addColorStop(1, rgba(colour, 0));
  c.fillStyle = core;
  c.beginPath();
  c.arc(cx, cy, r, 0, Math.PI * 2);
  c.fill();
  const rng = random(77);
  for (let arm = 0; arm < 4; arm += 1) {
    for (let index = 0; index < 220; index += 1) {
      const along = index / 220;
      const angle = arm * Math.PI / 2 + along * 4.2 + time * .02;
      const radius = r * (.12 + along * .86) + (rng() - .5) * r * .1;
      c.fillStyle = `rgba(220, 230, 255, ${.08 + rng() * .25})`;
      c.fillRect(cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius, 2, 2);
    }
  }
  c.restore();
}

// Galactic x/z in light years onto the disc drawn above (core at 0, 25,900).
function onDisc(box, [x, z]) {
  const r = Math.min(box.w, box.h) / 2;
  const scale = r / 48000;
  return [box.x + box.w / 2 + x * scale, box.y + box.h / 2 - (z - 25900) * scale];
}

// -- the cards ------------------------------------------------------------------------------
const PAINT = {
  intro(c, card, t, colour) {
    // Warp: streaks from the middle, slowing as the year comes into view.
    const rng = random(seedOf(`${card.year}`));
    const speed = 1 - ease(t / 2.4);
    c.save();
    for (let index = 0; index < 180; index += 1) {
      const angle = rng() * Math.PI * 2;
      const base = (rng() * 600 + t * 900 * (.4 + speed)) % 760;
      const length = 10 + speed * 160 * rng();
      const x1 = W / 2 + Math.cos(angle) * base, y1 = H * .44 + Math.sin(angle) * base;
      const x2 = W / 2 + Math.cos(angle) * (base + length), y2 = H * .44 + Math.sin(angle) * (base + length);
      c.strokeStyle = `rgba(220, 240, 255, ${.15 + rng() * .5})`;
      c.lineWidth = 1 + rng() * 2;
      c.beginPath();
      c.moveTo(x1, y1);
      c.lineTo(x2, y2);
      c.stroke();
    }
    c.restore();
    const a = appear(t, .9, 1.2);
    c.save();
    c.shadowColor = colour;
    c.shadowBlur = 60 * a;
    if (card.trip) text(c, String(card.trip), W / 2, H * .5 + (1 - a) * 60, {size: 110, align: "center", alpha: a, colour: INK, max: 960});
    else text(c, String(card.elite_year), W / 2, H * .5 + (1 - a) * 60, {size: 250, align: "center", alpha: a, colour: INK});
    c.restore();
    text(c, card.trip ? "YOUR EXPEDITION, TOLD BACK" : "YOUR YEAR IN THE BLACK", W / 2, H * .5 + 90, {size: 30, font: MONO, align: "center", colour, spacing: 10, alpha: appear(t, 1.6)});
    if (card.commander) text(c, `CMDR ${card.commander}`.toUpperCase(), W / 2, H * .22, {size: 40, font: SANS, align: "center", colour: SOFT, spacing: 6, alpha: appear(t, 1.2), max: 900});
    const facts = [card.sessions ? `${fmt(card.sessions)} sessions` : "", card.days ? `${fmt(card.days)} days in the cockpit` : ""].filter(Boolean).join("  ·  ");
    text(c, facts, W / 2, H * .5 + 160, {size: 34, align: "center", colour: SOFT, alpha: appear(t, 2.1)});
    if (card.first_day) text(c, `${card.first_day} – ${card.last_day}`, W / 2, H * .5 + 214, {size: 28, font: LIGHT, align: "center", colour: FAINT, alpha: appear(t, 2.4)});
    text(c, "Let's look back.", W / 2, H * .76, {size: 46, font: SERIF, align: "center", colour: INK, alpha: appear(t, 3)});
  },

  distance(c, card, t, colour) {
    kicker(c, `This ${span()} you flew`, t, colour);
    const box = {x: 90, y: 560, w: W - 180, h: 560};
    const trail = card.trail || [];
    if (trail.length > 1) {
      const fitted = fitTrail(trail, box);
      if (fitted.span > 8000) {
        galaxyDisc(c, box, t, colour, appear(t, .2, 1));
        const points = trail.map((p) => onDisc(box, p));
        const head = glowLine(c, points, colour, 3, ease((t - .6) / 3.2));
        if (head) dot(c, head[0], head[1], 9, INK, 30);
      } else {
        c.save();
        c.globalAlpha = .18 * appear(t, .2);
        c.strokeStyle = colour;
        for (let gx = box.x; gx <= box.x + box.w; gx += 60) { c.beginPath(); c.moveTo(gx, box.y); c.lineTo(gx, box.y + box.h); c.stroke(); }
        for (let gy = box.y; gy <= box.y + box.h; gy += 60) { c.beginPath(); c.moveTo(box.x, gy); c.lineTo(box.x + box.w, gy); c.stroke(); }
        c.restore();
        const points = trail.map(fitted.at);
        const head = glowLine(c, points, colour, 3.5, ease((t - .6) / 3.2));
        if (head) dot(c, head[0], head[1], 9, INK, 30);
      }
    }
    c.save();
    c.shadowColor = colour;
    c.shadowBlur = 40;
    text(c, count(card.ly, t, .4, 2.4), 90, 380, {size: 170, colour: INK, max: 900});
    c.restore();
    text(c, "LIGHT YEARS", 96, 450, {size: 34, font: MONO, colour, spacing: 10, alpha: appear(t, .8)});
    const comparison = card.comparison;
    if (comparison) {
      text(c, `That's ${fmt(comparison.times, comparison.times < 10 ? 1 : 0)} × ${comparison.words}.`, 90, 1168, {size: 36, colour: INK, alpha: appear(t, 3.2), max: 900});
    }
    if (card.hours) {
      text(c, `Light would need ${fmt(card.ly)} years for that. You took ${fmt(card.hours)} hours.`, 90, 1222, {size: 28, font: LIGHT, colour: SOFT, alpha: appear(t, 4), max: 900});
    }
  },

  jumps(c, card, t, colour) {
    kicker(c, "Jump after jump", t, colour);
    text(c, count(card.jumps, t, .3, 2), 90, 380, {size: 190, colour: INK, max: 900});
    text(c, "HYPERSPACE JUMPS", 96, 450, {size: 32, font: MONO, colour, spacing: 8, alpha: appear(t, .7)});
    // A dot for every system, the new ones lit gold.
    const shown = Math.min(card.systems || 0, 1400), fresh = Math.round(shown * (card.new_systems || 0) / Math.max(1, card.systems || 1));
    const columns = 40, size = (W - 180) / columns;
    const grown = Math.floor(shown * ease((t - .8) / 2.6));
    for (let index = 0; index < grown; index += 1) {
      const x = 90 + (index % columns) * size + size / 2, y = 540 + Math.floor(index / columns) * size + size / 2;
      if (y > 1060) break;
      dot(c, x, y, size * .28, index < fresh ? "#ffd27a" : rgba(colour, .75), index < fresh ? 8 : 0);
    }
    text(c, `${fmt(card.systems)} systems`, 90, 1150, {size: 54, colour: INK, alpha: appear(t, 2.6)});
    text(c, `${fmt(card.new_systems)} of them you'd never been to before.`, 90, 1210, {size: 32, colour: "#ffd27a", alpha: appear(t, 3.1), max: 900});
    if (card.carrier_jumps) text(c, `+ ${fmt(card.carrier_jumps)} carrier jumps`, W - 90, 1150, {size: 28, font: MONO, colour: SOFT, align: "right", alpha: appear(t, 3.4)});
  },

  time(c, card, t, colour) {
    kicker(c, "Time in the cockpit", t, colour);
    text(c, count(card.hours, t, .3, 2, card.hours < 10 ? 1 : 0), 90, 380, {size: 190, colour: INK});
    text(c, "HOURS FLOWN", 96, 450, {size: 32, font: MONO, colour, spacing: 8, alpha: appear(t, .7)});
    // A day clock: each part of the day, as much as you flew in it.
    const cx = W / 2, cy = 790, r = 230;
    const parts = [["morning", 5, 12], ["afternoon", 12, 17], ["evening", 17, 21], ["night", 21, 29]];
    const grow = ease((t - .9) / 1.6);
    parts.forEach(([name, from, to]) => {
      const share = (card.parts?.[name] || 0) / 100;
      const a0 = (from / 24) * Math.PI * 2 - Math.PI / 2, a1 = (to / 24) * Math.PI * 2 - Math.PI / 2;
      c.save();
      c.strokeStyle = "rgba(255,255,255,.08)";
      c.lineWidth = 46;
      c.beginPath(); c.arc(cx, cy, r, a0 + .02, a1 - .02); c.stroke();
      c.strokeStyle = name === card.part ? colour : rgba(colour, .45);
      c.shadowColor = colour;
      c.shadowBlur = name === card.part ? 24 : 0;
      c.lineWidth = 14 + 70 * share * grow;
      c.beginPath(); c.arc(cx, cy, r, a0 + .02, a1 - .02); c.stroke();
      c.restore();
      const mid = (a0 + a1) / 2;
      text(c, name.toUpperCase(), cx + Math.cos(mid) * (r + 92), cy + Math.sin(mid) * (r + 92) + 8, {size: 20, font: MONO, align: "center", colour: SOFT, alpha: appear(t, 1.4), spacing: 3});
    });
    const label = {morning: "A morning flyer", afternoon: "An afternoon flyer", evening: "An evening flyer", night: "A night owl"}[card.part] || "";
    text(c, label, cx, cy - 6, {size: 44, align: "center", colour: INK, alpha: appear(t, 1.8), max: 380});
    text(c, `${card.part_share}% of your hours`, cx, cy + 46, {size: 28, align: "center", colour: SOFT, alpha: appear(t, 2), max: 380});
    text(c, `Favourite day: ${card.weekday}`, 90, 1170, {size: 36, colour: INK, alpha: appear(t, 2.6)});
    if (card.longest) text(c, `Longest session: ${fmt(card.longest.hours, 1)} hours, on ${card.longest.date}`, 90, 1222, {size: 30, colour: SOFT, alpha: appear(t, 3), max: 900});
  },

  busiest(c, card, t, colour) {
    kicker(c, "Your busiest session", t, colour);
    headline(c, card.date, 90, 330, t, .3, {size: 76, max: 900});
    // A comet across the card.
    const along = .8 * ease((t - .5) / 2.5);
    const x = -100 + along * (W + 200), y = 520 + Math.sin(along * Math.PI) * -90;
    c.save();
    const tail = c.createLinearGradient(x - 420, y + 60, x, y);
    tail.addColorStop(0, rgba(colour, 0));
    tail.addColorStop(1, rgba(colour, .9));
    c.strokeStyle = tail;
    c.lineWidth = 10;
    c.lineCap = "round";
    c.beginPath(); c.moveTo(x - 420, y + 60); c.lineTo(x, y); c.stroke();
    c.restore();
    dot(c, x, y, 12, INK, 40);
    statTile(c, 90, 680, 280, "jumps", fmt(card.jumps), t, 1.2, colour);
    statTile(c, 400, 680, 280, "light years", fmt(card.ly), t, 1.4, colour);
    statTile(c, 710, 680, 280, "hours", fmt(card.hours, 1), t, 1.6, colour);
    if (card.from) text(c, card.from === card.to ? `All of it around ${card.from}` : `${card.from}  →  ${card.to}`, 90, 960, {size: 38, colour: INK, alpha: appear(t, 2.2), max: 900});
    if (card.firsts) text(c, `${fmt(card.firsts)} first discoveries along the way`, 90, 1020, {size: 32, colour: SOFT, alpha: appear(t, 2.5), max: 900});
    text(c, card.part === "night" ? "A long night." : `A long ${card.part}.`, 90, 1180, {size: 46, font: SERIF, colour: INK, alpha: appear(t, 3)});
  },

  longest_jump(c, card, t, colour) {
    kicker(c, "Your longest jump", t, colour);
    c.save();
    c.shadowColor = colour;
    c.shadowBlur = 50;
    text(c, count(card.ly, t, .3, 1.6, 2), 90, 420, {size: 200, colour: INK});
    c.restore();
    text(c, "LIGHT YEARS IN ONE JUMP", 96, 490, {size: 30, font: MONO, colour, spacing: 8, alpha: appear(t, .8)});
    // The jump: a charge, then a beam.
    const charge = ease((t - 1) / .9), beam = ease((t - 1.9) / .5);
    const ax = 170, bx = W - 170, y = 760;
    c.save();
    c.strokeStyle = rgba(colour, .5 * charge);
    c.lineWidth = 3;
    for (let ring = 0; ring < 3; ring += 1) {
      c.beginPath();
      c.arc(ax, y, 30 + ring * 22 * charge + (t * 40 % 22), 0, Math.PI * 2);
      c.stroke();
    }
    c.restore();
    dot(c, ax, y, 14, INK, 30);
    if (beam > 0) {
      c.save();
      c.shadowColor = colour;
      c.shadowBlur = 30;
      c.strokeStyle = colour;
      c.lineWidth = 6;
      c.beginPath(); c.moveTo(ax, y); c.lineTo(ax + (bx - ax) * beam, y); c.stroke();
      c.restore();
      dot(c, bx, y, 14 * beam, INK, 30);
    }
    text(c, card.from || "", ax, y + 80, {size: 30, colour: SOFT, alpha: appear(t, 1.2), max: 420});
    text(c, card.to || "", bx, y + 80, {size: 30, colour: INK, align: "right", alpha: appear(t, 2.2), max: 420});
    text(c, card.date ? `On ${card.date}.` : "", 90, 1040, {size: 40, colour: INK, alpha: appear(t, 2.8)});
    text(c, "Most ships never jump that far in their whole lives.", 90, 1100, {size: 30, font: LIGHT, colour: SOFT, alpha: appear(t, 3.3), max: 900});
  },

  furthest(c, card, t, colour) {
    kicker(c, "The furthest you went", t, colour);
    text(c, count(card.ly, t, .3, 2), 90, 380, {size: 180, colour: INK});
    text(c, "LIGHT YEARS FROM SOL", 96, 450, {size: 32, font: MONO, colour, spacing: 8, alpha: appear(t, .7)});
    const box = {x: 140, y: 520, w: W - 280, h: 560};
    galaxyDisc(c, box, t, colour, appear(t, .3, 1));
    const sol = onDisc(box, [0, 0]);
    const far = onDisc(box, card.pos || [0, 0]);
    const grow = ease((t - 1.1) / 1.6);
    c.save();
    c.setLineDash([10, 12]);
    c.strokeStyle = INK;
    c.lineWidth = 3;
    c.beginPath(); c.moveTo(sol[0], sol[1]); c.lineTo(sol[0] + (far[0] - sol[0]) * grow, sol[1] + (far[1] - sol[1]) * grow); c.stroke();
    c.restore();
    dot(c, sol[0], sol[1], 7, "#ffd27a", 20);
    text(c, "SOL", sol[0] + 14, sol[1] + 6, {size: 20, font: MONO, colour: "#ffd27a", alpha: appear(t, .8)});
    if (grow >= 1) dot(c, far[0], far[1], 10 + Math.sin(t * 4) * 2, colour, 30);
    text(c, card.system, 90, 1170, {size: 50, colour: INK, alpha: appear(t, 2.6), max: 900});
    text(c, [card.region, card.date].filter(Boolean).join("  ·  "), 90, 1226, {size: 30, colour: SOFT, alpha: appear(t, 3), max: 900});
  },

  regions(c, card, t, colour) {
    kicker(c, "You lived in", t, colour);
    headline(c, card.lived_in, 90, 330, t, .3, {size: 96, max: 900});
    text(c, `${card.lived_share}% of your arrivals`, 90, 400, {size: 32, colour: SOFT, alpha: appear(t, .9)});
    bars(c, card.top || [], 90, 540, W - 180, t, 1.2, colour, {label: "name", value: "arrivals"});
    const a = appear(t, 2.6);
    text(c, `${card.visited} of ${card.of} regions visited this ${span()}`, 90, 1120, {size: 38, colour: INK, alpha: a});
    if (card.new_count) {
      text(c, `${card.new_count} for the very first time${card.new?.length ? `: ${card.new.slice(0, 3).join(", ")}${card.new_count > 3 ? "…" : ""}` : ""}`,
        90, 1176, {size: 28, colour: rgba(colour, 1), alpha: appear(t, 3), max: 900});
    }
  },

  home(c, card, t, colour) {
    kicker(c, "The system you kept coming back to", t, colour);
    // Rings, one for each return.
    const cx = W / 2, cy = 700;
    const rings = Math.min(card.visits || 0, 36);
    const grown = Math.floor(rings * ease((t - .4) / 2.4));
    for (let index = 0; index < grown; index += 1) {
      c.save();
      c.strokeStyle = rgba(colour, .5 - index / rings * .4);
      c.lineWidth = 2;
      c.beginPath();
      c.arc(cx, cy, 60 + index * 9 + Math.sin(t * 2 + index * .4) * 2, 0, Math.PI * 2);
      c.stroke();
      c.restore();
    }
    dot(c, cx, cy, 36, colour, 60);
    dot(c, cx, cy, 18, INK, 20);
    headline(c, card.system, W / 2, 330, t, .3, {size: 84, max: 900, align: "center"});
    text(c, `${fmt(card.visits)} arrivals, on ${fmt(card.days)} different days`, W / 2, 1110, {size: 40, colour: INK, align: "center", alpha: appear(t, 2.4), max: 900});
    text(c, `From ${card.first} to ${card.last}`, W / 2, 1166, {size: 30, colour: SOFT, align: "center", alpha: appear(t, 2.8)});
  },

  discoveries(c, card, t, colour) {
    kicker(c, "Where nobody had been", t, colour);
    // Flags falling into place.
    const rng = random(seedOf("flags"));
    const flags = Math.min(60, card.firsts || 0);
    for (let index = 0; index < flags; index += 1) {
      const fall = ease((t - .3 - index * .02) / 1.2);
      const x = 120 + rng() * (W - 240), y = 520 + rng() * 300;
      text(c, "⚑", x, y - (1 - fall) * 200, {size: 26 + rng() * 22, colour: rgba(colour, .3 + rng() * .5), alpha: fall});
    }
    c.save();
    c.shadowColor = colour;
    c.shadowBlur = 40;
    text(c, count(card.firsts, t, .3, 2), 90, 380, {size: 190, colour: INK});
    c.restore();
    text(c, "FIRST DISCOVERIES", 96, 450, {size: 32, font: MONO, colour, spacing: 8, alpha: appear(t, .7)});
    statTile(c, 90, 880, 280, "bodies scanned", fmt(card.scanned), t, 1.4, colour);
    statTile(c, 400, 880, 280, "worlds mapped", fmt(card.mapped), t, 1.6, colour);
    statTile(c, 710, 880, 280, "first footfalls", fmt(card.footfalls), t, 1.8, colour);
    if (card.best) {
      text(c, `Worth the most: ${card.best.name}`, 90, 1130, {size: 34, colour: INK, alpha: appear(t, 2.4), max: 900});
      text(c, `${card.best.class}, ${credits(card.best.value)} cr`, 90, 1180, {size: 28, colour: SOFT, alpha: appear(t, 2.7), max: 900});
    }
    if (card.sold) text(c, `${credits(card.sold)} cr of cartographic data sold`, 90, 1236, {size: 28, colour: rgba(colour, 1), alpha: appear(t, 3), max: 900});
  },

  rare(c, card, t, colour) {
    kicker(c, "The rarest thing you found", t, colour);
    planet(c, card, W / 2, 660, 230 * appear(t, .2, 1.2), t);
    headline(c, card.label, W / 2, 1010, t, 1.2, {size: 76, max: 940, align: "center"});
    text(c, card.name, W / 2, 1074, {size: 36, colour: INK, align: "center", alpha: appear(t, 1.8), max: 940});
    text(c, [card.first ? "Discovered by you" : "", card.date].filter(Boolean).join("  ·  "), W / 2, 1126, {size: 28, colour: rgba(colour, 1), align: "center", alpha: appear(t, 2.2)});
    const tally = (card.tally || []).filter((row) => row.label !== card.label || row.count > 1).slice(0, 4);
    if (tally.length) {
      text(c, tally.map((row) => `${row.count} × ${row.label}`).join("   "), W / 2, 1196, {size: 24, font: MONO, colour: SOFT, align: "center", alpha: appear(t, 2.8), max: 940});
    }
  },

  codex(c, card, t, colour) {
    kicker(c, "Your Codex personality", t, colour);
    headline(c, card.personality, 90, 340, t, .3, {size: 110, max: 900});
    paragraph(c, card.line, 90, 430, {size: 36, colour: SOFT, alpha: appear(t, 1), width: 880});
    // The mix as a ring.
    const cx = W / 2, cy = 820, r = 190;
    const mix = card.mix || [];
    const total = mix.reduce((sum, row) => sum + row.count, 0) || 1;
    const tones = [colour, "#7dffa8", "#ffd27a", "#6fd3ff", "#ff8a5c"];
    let angle = -Math.PI / 2;
    const grow = ease((t - 1.2) / 1.6);
    mix.forEach((row, index) => {
      const sweep = row.count / total * Math.PI * 2 * grow;
      c.save();
      c.strokeStyle = tones[index % tones.length];
      c.shadowColor = tones[index % tones.length];
      c.shadowBlur = 16;
      c.lineWidth = 46;
      c.beginPath(); c.arc(cx, cy, r, angle + .03, angle + sweep - .03); c.stroke();
      c.restore();
      text(c, `${row.kind} · ${row.count}`, 90, 1110 + index * 44, {size: 28, colour: tones[index % tones.length], alpha: appear(t, 2 + index * .2)});
      angle += sweep;
    });
    text(c, fmt(card.entries), cx, cy + 20, {size: 80, align: "center", colour: INK, alpha: appear(t, 1.4)});
    text(c, "CODEX ENTRIES", cx, cy + 62, {size: 20, font: MONO, align: "center", colour: SOFT, spacing: 4, alpha: appear(t, 1.6)});
  },

  biology(c, card, t, colour) {
    kicker(c, "Life, catalogued", t, colour);
    growth(c, W - 150, 1010, t, colour);
    text(c, count(card.analysed, t, .3, 1.8), 90, 380, {size: 190, colour: INK});
    text(c, "ORGANICS ANALYSED", 96, 450, {size: 32, font: MONO, colour, spacing: 8, alpha: appear(t, .7)});
    if (card.genus) text(c, `Your favourite: ${card.genus}`, 90, 560, {size: 46, colour: INK, alpha: appear(t, 1.2), max: 640});
    (card.top || []).forEach((row, index) => {
      text(c, `${row.name}`, 90, 660 + index * 62, {size: 32, colour: SOFT, alpha: appear(t, 1.6 + index * .2), max: 560});
      text(c, `× ${row.count}`, 680, 660 + index * 62, {size: 30, font: MONO, colour, alpha: appear(t, 1.6 + index * .2)});
    });
    text(c, `${fmt(card.species)} species`, 90, 1120, {size: 40, colour: INK, alpha: appear(t, 2.6)});
    if (card.sold) text(c, `${credits(card.sold)} cr from Vista Genomics`, 90, 1176, {size: 30, colour: rgba(colour, 1), alpha: appear(t, 3)});
  },

  money(c, card, t, colour) {
    kicker(c, "Earned the long way", t, colour);
    c.save();
    c.shadowColor = colour;
    c.shadowBlur = 40;
    text(c, `${credits(Number(card.earned || 0) * easeExpo((t - .3) / 2))}`, 90, 400, {size: 200, colour: INK});
    c.restore();
    text(c, "CREDITS", 96, 470, {size: 32, font: MONO, colour, spacing: 10, alpha: appear(t, .7)});
    const parts = [["Exploration", card.exploration, "#6fd3ff"], ["Organics", card.biology, "#7dffa8"], ["Trade", card.trade, colour],
      ["Mining", card.mining, "#c792ff"]]
      .filter((row) => row[1] > 0);
    const total = parts.reduce((sum, row) => sum + row[1], 0) || 1;
    let x = 90;
    const grow = ease((t - 1.1) / 1.4);
    parts.forEach(([name, value, tone], index) => {
      const width = (W - 180) * value / total * grow;
      c.save();
      c.fillStyle = tone;
      c.shadowColor = tone;
      c.shadowBlur = 16;
      c.fillRect(x, 560, Math.max(0, width - 6), 40);
      c.restore();
      text(c, `${name}  ${credits(value)}`, 90, 670 + index * 54, {size: 32, colour: tone, alpha: appear(t, 1.6 + index * .2)});
      x += width;
    });
    if (card.best_trade) {
      const trade = card.best_trade;
      const a = appear(t, 2.4);
      text(c, "YOUR BEST TRADE", 90, 920, {size: 24, font: MONO, colour, spacing: 6, alpha: a});
      text(c, `${fmt(trade.count)} × ${trade.commodity}`, 90, 990, {size: 52, colour: INK, alpha: a, max: 900});
      text(c, `${credits(trade.profit)} cr profit${trade.date ? ` on ${trade.date}` : ""}`, 90, 1046, {size: 32, colour: SOFT, alpha: appear(t, 2.7), max: 900});
      if (trade.from || trade.to) text(c, `${trade.from || "?"}  →  ${trade.to || "?"}`, 90, 1098, {size: 28, colour: FAINT, alpha: appear(t, 3), max: 900});
    }
    if (card.top_commodity) text(c, `Your commodity of the ${span()}: ${card.top_commodity}`, 90, 1200, {size: 32, colour: INK, alpha: appear(t, 3.3), max: 900});
  },

  bgs(c, card, t, colour) {
    kicker(c, "The factions you carried", t, colour);
    headline(c, card.top_faction, 90, 320, t, .3, {size: 76, max: 900});
    text(c, `${fmt(card.top_actions)} jobs for them alone`, 90, 390, {size: 32, colour: SOFT, alpha: appear(t, .9)});
    bars(c, card.top || [], 90, 520, W - 180, t, 1.2, colour, {label: "name", value: "actions"});
    text(c, `${fmt(card.actions)} jobs · ${fmt(card.factions)} factions · ${fmt(card.systems)} systems`, 90, 1120, {size: 34, colour: INK, alpha: appear(t, 2.6), max: 900});
    if (card.work?.length) text(c, card.work.map((row) => `${row.count} ${row.kind}`).join("  ·  "), 90, 1176, {size: 26, font: MONO, colour: SOFT, alpha: appear(t, 3), max: 900});
  },

  music(c, card, t, colour) {
    kicker(c, "Your soundtrack", t, colour);
    // An equaliser, playing along.
    const columns = 28;
    for (let index = 0; index < columns; index += 1) {
      const level = .25 + .75 * Math.abs(Math.sin(t * (1.6 + index * .13) + index * .7)) * appear(t, .3);
      const height = 260 * level;
      c.save();
      c.fillStyle = rgba(colour, .3 + level * .6);
      c.shadowColor = colour;
      c.shadowBlur = 12;
      c.fillRect(90 + index * ((W - 180) / columns), 760 - height, (W - 180) / columns - 8, height);
      c.restore();
    }
    headline(c, card.title, 90, 330, t, .3, {size: 80, max: 900});
    text(c, card.artist, 90, 400, {size: 40, colour: SOFT, alpha: appear(t, .9), max: 900});
    text(c, `played ${fmt(card.track_plays)} times`, 90, 456, {size: 30, font: MONO, colour, alpha: appear(t, 1.2)});
    (card.top || []).slice(1, 4).forEach((row, index) => {
      text(c, `${index + 2}.  ${row.title}${row.artist ? ` · ${row.artist}` : ""}`, 90, 880 + index * 58, {size: 32, colour: SOFT, alpha: appear(t, 1.8 + index * .2), max: 900});
    });
    text(c, `${fmt(card.plays)} plays, ${fmt(card.tracks)} different tracks`, 90, 1150, {size: 36, colour: INK, alpha: appear(t, 2.6), max: 900});
    if (card.top_artist) text(c, `Most played artist: ${card.top_artist}`, 90, 1206, {size: 30, colour: rgba(colour, 1), alpha: appear(t, 3), max: 900});
  },

  postcards(c, card, t, colour) {
    kicker(c, "Places worth keeping", t, colour);
    text(c, count(card.count, t, .3, 1.4), 90, 340, {size: 160, colour: INK});
    text(c, card.count === 1 ? "POSTCARD" : "POSTCARDS", 96, 404, {size: 32, font: MONO, colour, spacing: 8, alpha: appear(t, .7)});
    const picture = images.get(card.featured?.id);
    const a = appear(t, .9, 1.1);
    c.save();
    c.translate(W / 2, 780);
    c.rotate((-4 + 4 * (1 - a)) * Math.PI / 180);
    c.globalAlpha = a;
    const pw = 760, ph = picture ? Math.min(520, pw * picture.height / picture.width) : 460;
    c.shadowColor = "rgba(0,0,0,.6)";
    c.shadowBlur = 50;
    c.fillStyle = "#f5efe2";
    c.fillRect(-pw / 2 - 26, -ph / 2 - 26, pw + 52, ph + 120);
    c.shadowBlur = 0;
    if (picture) c.drawImage(picture, -pw / 2, -ph / 2, pw, ph);
    else { c.fillStyle = "#28313d"; c.fillRect(-pw / 2, -ph / 2, pw, ph); }
    text(c, card.featured?.title || "", 0, ph / 2 + 62, {size: 34, font: SERIF, colour: "#2a2a2a", align: "center", max: 720});
    c.restore();
    if (card.featured?.date) text(c, card.featured.date, W / 2, 1200, {size: 28, colour: SOFT, align: "center", alpha: appear(t, 2)});
  },

  constellations(c, card, t, colour) {
    kicker(c, "Written in your sky", t, colour);
    const item = card.featured || {};
    const stars = item.stars || [], keys = item.keys || stars.map((star) => String(star.system).toLowerCase());
    const where = new Map(keys.map((key, index) => [key, [W / 2 + stars[index].x * 380, 720 - stars[index].y * 330]]));
    const grow = ease((t - .8) / 2.6);
    (item.lines || []).forEach(([a, b], index, all) => {
      const share = clamp(grow * all.length - index);
      if (share <= 0 || !where.has(a) || !where.has(b)) return;
      const [x1, y1] = where.get(a), [x2, y2] = where.get(b);
      c.save();
      c.strokeStyle = rgba(colour, .85);
      c.shadowColor = colour;
      c.shadowBlur = 14;
      c.lineWidth = 3;
      c.beginPath(); c.moveTo(x1, y1); c.lineTo(x1 + (x2 - x1) * share, y1 + (y2 - y1) * share); c.stroke();
      c.restore();
    });
    stars.forEach((star, index) => {
      const [x, y] = where.get(keys[index]) || [0, 0];
      dot(c, x, y, 7 + Math.sin(t * 3 + index) * 1.5, INK, 26 * appear(t, .3 + index * .1));
    });
    headline(c, item.name || "", W / 2, 330, t, .3, {size: 80, max: 940, align: "center"});
    paragraph(c, item.legend || "", W / 2, 1100, {size: 32, font: SERIF, colour: SOFT, width: 880, align: "center", alpha: appear(t, 2.6)});
    const others = (card.names || []).filter((name) => name !== item.name);
    text(c, card.count > 1 ? `${card.count} constellations finished this ${span()}${others.length ? `, with ${others.slice(0, 2).join(" and ")}` : ""}` : "Finished this year",
      W / 2, 1218, {size: 26, font: MONO, colour, align: "center", alpha: appear(t, 3), max: 940});
  },

  achievements(c, card, t, colour) {
    kicker(c, "Milestones", t, colour);
    // A medal.
    const cx = W / 2, cy = 700, r = 170 * appear(t, .4, 1);
    c.save();
    c.fillStyle = rgba(colour, .9);
    c.beginPath(); c.moveTo(cx - 90, cy - 330); c.lineTo(cx - 30, cy - r + 10); c.lineTo(cx + 30, cy - r + 10); c.lineTo(cx + 90, cy - 330); c.closePath();
    c.globalAlpha = .5 * appear(t, .4);
    c.fill();
    c.restore();
    const medal = c.createRadialGradient(cx - r * .3, cy - r * .3, 0, cx, cy, r);
    medal.addColorStop(0, "#fff6c8");
    medal.addColorStop(.6, colour);
    medal.addColorStop(1, "#6b520b");
    c.save();
    c.fillStyle = medal;
    c.shadowColor = colour;
    c.shadowBlur = 50;
    c.beginPath(); c.arc(cx, cy, Math.max(1, r), 0, Math.PI * 2); c.fill();
    c.restore();
    text(c, count(card.count, t, .6, 1.4), cx, cy + 40, {size: 120, align: "center", colour: "#2a1f02"});
    headline(c, `${fmt(card.count)} achievements unlocked`, 90, 330, t, .3, {size: 60, max: 900});
    if (card.best?.title) {
      text(c, `The biggest: ${card.best.title}`, 90, 1040, {size: 42, colour: INK, alpha: appear(t, 2), max: 900});
      paragraph(c, card.best.detail, 90, 1096, {size: 28, colour: SOFT, alpha: appear(t, 2.3), width: 900});
    }
    text(c, `${fmt(card.points)} points`, 90, 1214, {size: 30, font: MONO, colour, alpha: appear(t, 2.8)});
  },

  combat(c, card, t, colour) {
    kicker(c, "When it came to a fight", t, colour);
    // A scope: rings, a sweep, and a blip for each kill.
    const cx = W / 2, cy = 700, r = 250;
    const grow = appear(t, .2, 1);
    c.save();
    c.strokeStyle = rgba(colour, .35 * grow);
    c.lineWidth = 2;
    for (let ring = 1; ring <= 4; ring += 1) { c.beginPath(); c.arc(cx, cy, r * ring / 4, 0, Math.PI * 2); c.stroke(); }
    c.beginPath(); c.moveTo(cx - r, cy); c.lineTo(cx + r, cy); c.moveTo(cx, cy - r); c.lineTo(cx, cy + r); c.stroke();
    const sweep = t * 1.6;
    const beam = c.createConicGradient ? c.createConicGradient(sweep - .9, cx, cy) : null;
    if (beam) {
      beam.addColorStop(0, rgba(colour, 0));
      beam.addColorStop(.14, rgba(colour, .35 * grow));
      beam.addColorStop(.15, rgba(colour, 0));
      c.fillStyle = beam;
      c.beginPath(); c.arc(cx, cy, r, 0, Math.PI * 2); c.fill();
    }
    c.restore();
    const rng = random(seedOf(`kills${card.kills}`));
    const blips = Math.min(60, card.kills || 0);
    for (let index = 0; index < blips; index += 1) {
      const angle = rng() * Math.PI * 2, distance = r * (.15 + rng() * .8);
      const shown = appear(t, .6 + index * .04, .3);
      dot(c, cx + Math.cos(angle) * distance, cy + Math.sin(angle) * distance, 5, rgba(colour, .9 * shown), 14 * shown);
    }
    c.save();
    c.shadowColor = colour;
    c.shadowBlur = 40;
    text(c, count(card.kills, t, .3, 1.8), 90, 380, {size: 190, colour: INK});
    c.restore();
    text(c, card.kills === 1 ? "KILL" : "KILLS", 96, 450, {size: 32, font: MONO, colour, spacing: 10, alpha: appear(t, .7)});
    const side = card.ax_kills ? ["Thargoids", fmt(card.ax_kills)] : ["other pilots", fmt(card.pvp_kills)];
    statTile(c, 90, 980, 280, "in bounties", credits(card.bounty_cr), t, 1.6, colour);
    statTile(c, 400, 980, 280, "in combat bonds", credits(card.bond_cr), t, 1.8, colour);
    statTile(c, 710, 980, 280, side[0], side[1], t, 2, colour);
    const lines = [];
    if (card.biggest) lines.push(`Biggest bounty: ${credits(card.biggest.value)} cr${card.biggest.target ? ` for ${/^[aeiou]/i.test(card.biggest.target) ? "an" : "a"} ${card.biggest.target}` : ""}, ${card.biggest.date}`);
    if (card.interdicted) lines.push(`Interdicted ${fmt(card.interdicted)} time${card.interdicted === 1 ? "" : "s"}${card.escaped ? `, got away ${fmt(card.escaped)}` : ""}`);
    if (card.nemesis) lines.push(`Your nemesis: ${card.nemesis}`);
    else if (card.top_target) lines.push(`Most hunted: ${card.top_target}`);
    if (card.rank) lines.push(`Promoted to ${card.rank}`);
    lines.slice(0, 2).forEach((line, index) => text(c, line, 90, 1180 + index * 44, {size: 30, colour: index ? SOFT : INK, alpha: appear(t, 2.6 + index * .3), max: 900}));
  },

  everyday(c, card, t, colour) {
    kicker(c, "And everything in between", t, colour);
    headline(c, "The everyday", 90, 330, t, .3, {size: 96});
    text(c, "The bits nobody screenshots.", 90, 396, {size: 34, font: SERIF, colour: SOFT, alpha: appear(t, .8)});
    const tiles = [["missions done", fmt(card.missions)], ["times docked", fmt(card.docked)], ["landings", fmt(card.landed)],
      ["tonnes of fuel scooped", fmt(card.scooped)], ["engineering rolls", fmt(card.engineered)], ["ships bought", fmt((card.ships || []).length)]];
    tiles.forEach(([label, value], index) => statTile(c, 90 + (index % 3) * 310, 500 + Math.floor(index / 3) * 190, 280, label, value, t, .9 + index * .15, colour));
    const lines = [];
    if (card.mission_cr) lines.push(`${credits(card.mission_cr)} cr from missions`);
    if (card.station) lines.push(`Docked most at ${card.station}`);
    if (card.engineer) lines.push(`Your engineer: ${card.engineer}`);
    if ((card.ships || []).length) lines.push(`New ships: ${card.ships.slice(0, 3).join(", ")}`);
    lines.slice(0, 4).forEach((line, index) => text(c, line, 90, 960 + index * 54, {size: 34, colour: index ? SOFT : INK, alpha: appear(t, 2 + index * .25), max: 900}));
  },

  deaths(c, card, t, colour) {
    kicker(c, "We don't talk about these", t, colour);
    // Cracks across the glass.
    const rng = random(seedOf(`cracks${card.deaths}`));
    const crack = ease((t - .5) / .6);
    c.save();
    c.strokeStyle = `rgba(255, 240, 240, ${.35 * crack})`;
    c.lineWidth = 2;
    for (let line = 0; line < 9; line += 1) {
      let x = W * .62, y = H * .46;
      const angle = rng() * Math.PI * 2;
      c.beginPath();
      c.moveTo(x, y);
      for (let step = 0; step < 6; step += 1) {
        x += Math.cos(angle + (rng() - .5) * .9) * 70 * crack;
        y += Math.sin(angle + (rng() - .5) * .9) * 70 * crack;
        c.lineTo(x, y);
      }
      c.stroke();
    }
    c.restore();
    text(c, count(card.deaths, t, .3, 1), 90, 520, {size: 260, colour: INK});
    text(c, card.deaths === 1 ? "REBUY" : "REBUYS", 96, 600, {size: 34, font: MONO, colour, spacing: 10, alpha: appear(t, .7)});
    const words = card.deaths === 1 ? "Just the one. It happens to the best of us."
      : card.deaths < 5 ? "A few. Each one taught you something." : "The insurance people know you by name.";
    paragraph(c, words, 90, 900, {size: 50, font: SERIF, colour: INK, alpha: appear(t, 1.6), width: 900});
    text(c, "You came back every time.", 90, 1180, {size: 34, colour: SOFT, alpha: appear(t, 2.6)});
  },

  // An expedition's places (5.6.1): a pin for each, scattered like a chart.
  places(c, card, t, colour) {
    kicker(c, "The places you kept", t, colour);
    const rng = random(seedOf(`places${card.count}`));
    for (let index = 0; index < Math.min(28, card.count); index += 1) {
      const x = 120 + rng() * (W - 240), y = 230 + rng() * 210;
      c.save();
      c.globalAlpha = appear(t, .2 + index * .05);
      c.fillStyle = colour;
      c.beginPath();
      c.arc(x, y, 7, 0, Math.PI * 2);
      c.fill();
      c.restore();
    }
    text(c, count(card.count, t, .3, 1), 90, 680, {size: 260, colour: INK});
    text(c, card.count === 1 ? "PLACE" : "PLACES", 96, 760, {size: 34, font: MONO, colour, spacing: 10, alpha: appear(t, .7)});
    text(c, `${card.visited} of them visited`, 96, 820, {size: 34, colour: SOFT, alpha: appear(t, 1)});
    (card.names || []).slice(0, 5).forEach((name, index) => text(c, name, 90, 930 + index * 56, {size: 36, colour: index ? SOFT : INK, alpha: appear(t, 1.4 + index * .2), max: 900}));
    text(c, "Somewhere to come back to.", 90, 1240, {size: 34, colour: SOFT, alpha: appear(t, 2.6)});
  },

  // Your Hatchling's side of an expedition (5.6.4): it, its diary, its badge.
  hatchling(c, card, t, colour) {
    kicker(c, "Along for the ride", t, colour);
    const art = window.HatchlingArt;
    if (art) {
      c.save();
      c.globalAlpha = appear(t, .2, 1);
      art.draw(c, {name: card.name, species: card.species, kind: card.sample_kind, stage: card.stage, form: card.form,
        mood_word: "HAPPY", needs: {mood: 95}, reaction: t > 1 ? "happy" : ""},
      {x: W / 2, y: 440 + Math.sin(t * 2.2) * 8, size: 330, t, look: [Math.sin(t * .8) * .5, -.15]});
      c.restore();
    }
    text(c, String(card.name || "").toUpperCase(), W / 2, 700, {size: 76, colour: INK, align: "center", alpha: appear(t, .6)});
    text(c, `${card.moments} ${card.moments === 1 ? "MOMENT" : "MOMENTS"} IN ITS DIARY`, W / 2, 752, {size: 28, font: MONO, colour, spacing: 6, align: "center", alpha: appear(t, .9)});
    (card.lines || []).slice(-5).forEach((line, index) => text(c, line, 90, 850 + index * 54, {size: 32, colour: index ? SOFT : INK, alpha: appear(t, 1.2 + index * .25), max: 900}));
    if (card.badge) text(c, `✦ ${card.badge}`, W / 2, 1240, {size: 38, colour, align: "center", alpha: appear(t, 2.6)});
  },

  verdict(c, card, t, colour) {
    kicker(c, "The Watcher's verdict", t, colour);
    // The Watcher: the orb, breathing.
    const cx = W / 2, cy = 540;
    const breathe = 1 + Math.sin(t * 1.6) * .04;
    const r = 120 * breathe * appear(t, .2, 1.2);
    const halo = c.createRadialGradient(cx, cy, 0, cx, cy, r * 2.6);
    halo.addColorStop(0, rgba(colour, .55));
    halo.addColorStop(1, rgba(colour, 0));
    c.fillStyle = halo;
    c.fillRect(0, 0, W, H);
    const orb = c.createRadialGradient(cx - r * .25, cy - r * .3, r * .05, cx, cy, Math.max(1, r));
    orb.addColorStop(0, "#ffffff");
    orb.addColorStop(.25, colour);
    orb.addColorStop(1, rgba(colour, .15));
    c.save();
    c.fillStyle = orb;
    c.shadowColor = colour;
    c.shadowBlur = 80;
    c.beginPath(); c.arc(cx, cy, Math.max(1, r), 0, Math.PI * 2); c.fill();
    c.restore();
    headline(c, card.title, W / 2, 840, t, 1.2, {size: 64, max: 940, align: "center"});
    // Its words, as it says them.
    const chars = Math.floor(Math.max(0, t - 2) * 34);
    paragraph(c, card.words, 110, 940, {size: 38, font: `italic ${SERIF}`, colour: INK, width: 860, chars, leading: 1.4});
  },

  finale(c, card, t, colour) {
    text(c, "VOID WRAPPED", W / 2, 150, {size: 30, font: MONO, align: "center", colour, spacing: 12, alpha: appear(t, .1)});
    headline(c, String(card.trip || card.elite_year), W / 2, 290, t, .2, {size: card.trip ? 76 : 150, align: "center", max: 960});
    if (card.commander) text(c, `CMDR ${card.commander}`.toUpperCase(), W / 2, 350, {size: 32, font: SANS, align: "center", colour: SOFT, spacing: 5, alpha: appear(t, .6), max: 900});
    text(c, card.title, W / 2, 420, {size: 40, font: `italic ${SERIF}`, align: "center", colour: INK, alpha: appear(t, .9), max: 940});
    const tiles = [["light years", fmt(card.ly)], ["jumps", fmt(card.jumps)], ["systems", fmt(card.systems)],
      ["hours", fmt(card.hours)], ["first discoveries", fmt(card.firsts)], ["credits", credits(card.credits)]];
    tiles.forEach(([label, value], index) => statTile(c, 90 + (index % 3) * 310, 500 + Math.floor(index / 3) * 180, 280, label, value, t, 1.1 + index * .15, colour));
    const box = {x: 90, y: 860, w: W - 180, h: 300};
    const trail = card.trail || [];
    if (trail.length > 1) {
      const fitted = fitTrail(trail, box);
      if (fitted.span > 8000) {
        galaxyDisc(c, box, t, colour, .7 * appear(t, 1.8));
        glowLine(c, trail.map((p) => onDisc(box, p)), colour, 2.5, ease((t - 2) / 2.5));
      } else {
        glowLine(c, trail.map(fitted.at), colour, 3, ease((t - 2) / 2.5));
      }
    }
    const extras = [card.regions ? `${card.regions} regions` : "", card.bio ? `${fmt(card.bio)} organics` : "", card.home ? `home: ${card.home}` : ""].filter(Boolean).join("  ·  ");
    text(c, extras, W / 2, 1212, {size: 26, font: MONO, align: "center", colour: SOFT, alpha: appear(t, 3), max: 940});
  },
};

// A planet (or a star) for the rarest find, turning slowly.
function planet(c, card, cx, cy, r, t) {
  if (r <= 1) return;
  const label = String(card.label || "").toLowerCase();
  if (label.includes("black hole")) {
    c.save();
    for (let ring = 0; ring < 3; ring += 1) {
      c.strokeStyle = `rgba(255, ${170 + ring * 30}, 90, ${.55 - ring * .15})`;
      c.lineWidth = 16 - ring * 4;
      c.beginPath();
      c.ellipse(cx, cy, r * (1.7 + ring * .25), r * (.38 + ring * .05), -.2 + Math.sin(t * .3) * .03, 0, Math.PI * 2);
      c.stroke();
    }
    c.fillStyle = "#000";
    c.shadowColor = "#ffb066";
    c.shadowBlur = 60;
    c.beginPath(); c.arc(cx, cy, r * .75, 0, Math.PI * 2); c.fill();
    c.restore();
    return;
  }
  const tones = label.includes("earth") ? ["#2f8cff", "#3fbf6a", "#e9f4ff"]
    : label.includes("ammonia") ? ["#9b6a3a", "#d9b27a", "#f1dcb5"]
      : label.includes("water") ? ["#1a5bd8", "#4ab0ff", "#d8f0ff"]
        : label.includes("green") ? ["#2e8a3a", "#8cff72", "#e2ffd4"]
          : label.includes("helium") ? ["#c9c2b6", "#f0ebe2", "#ffffff"]
            : label.includes("neutron") || label.includes("white dwarf") ? ["#9fc7ff", "#e8f2ff", "#ffffff"]
              : label.includes("wolf") ? ["#7d8cff", "#d6dcff", "#ffffff"]
                : label.includes("carbon") ? ["#b3361d", "#ff8a5c", "#ffd2b8"] : ["#4a6b8a", "#9fc0dd", "#ffffff"];
  const star = /neutron|dwarf|wolf|carbon/.test(label);
  c.save();
  c.shadowColor = tones[1];
  c.shadowBlur = star ? 120 : 60;
  const body = c.createRadialGradient(cx - r * .35, cy - r * .35, r * .1, cx, cy, r);
  body.addColorStop(0, tones[2]);
  body.addColorStop(.45, tones[1]);
  body.addColorStop(1, tones[0]);
  c.fillStyle = body;
  c.beginPath(); c.arc(cx, cy, r, 0, Math.PI * 2); c.fill();
  c.restore();
  if (!star) {
    // Bands or continents, drifting across.
    c.save();
    c.beginPath(); c.arc(cx, cy, r, 0, Math.PI * 2); c.clip();
    const rng = random(seedOf(card.name || "world"));
    for (let band = 0; band < 9; band += 1) {
      const y = cy - r + rng() * r * 2;
      c.fillStyle = `rgba(255,255,255,${.04 + rng() * .1})`;
      c.beginPath();
      c.ellipse(cx + ((t * 18 + rng() * r * 2) % (r * 3)) - r * 1.5, y, r * (.3 + rng() * .6), r * (.04 + rng() * .1), 0, 0, Math.PI * 2);
      c.fill();
    }
    const shade = c.createLinearGradient(cx - r, cy, cx + r, cy);
    shade.addColorStop(0, "rgba(0,0,0,0)");
    shade.addColorStop(.65, "rgba(0,0,0,.15)");
    shade.addColorStop(1, "rgba(0,0,0,.7)");
    c.fillStyle = shade;
    c.fillRect(cx - r, cy - r, r * 2, r * 2);
    c.restore();
  } else {
    // Jets from the poles.
    c.save();
    c.globalAlpha = .55;
    const jet = c.createLinearGradient(cx, cy - r * 3, cx, cy + r * 3);
    jet.addColorStop(0, "rgba(180,220,255,0)");
    jet.addColorStop(.5, "rgba(220,240,255,.8)");
    jet.addColorStop(1, "rgba(180,220,255,0)");
    c.fillStyle = jet;
    c.fillRect(cx - 6 - Math.sin(t * 6) * 2, cy - r * 3, 12, r * 6);
    c.restore();
  }
}

// A plant growing in the corner of the organics card.
function growth(c, x, y, t, colour) {
  const grow = ease((t - .2) / 3);
  const rng = random(9);
  function branch(bx, by, angle, length, depth) {
    if (depth > 6 || length < 8) return;
    const share = clamp(grow * 7 - depth);
    if (share <= 0) return;
    const ex = bx + Math.cos(angle) * length * share, ey = by + Math.sin(angle) * length * share;
    c.strokeStyle = rgba(colour, .7 - depth * .08);
    c.lineWidth = Math.max(1, 7 - depth);
    c.beginPath(); c.moveTo(bx, by); c.lineTo(ex, ey); c.stroke();
    if (share >= 1) {
      branch(ex, ey, angle - .45 - rng() * .3 + Math.sin(t + depth) * .03, length * .74, depth + 1);
      branch(ex, ey, angle + .4 + rng() * .3 + Math.cos(t + depth) * .03, length * .7, depth + 1);
    } else if (depth > 3) {
      dot(c, ex, ey, 3, colour, 10);
    }
  }
  c.save();
  c.lineCap = "round";
  c.shadowColor = colour;
  c.shadowBlur = 10;
  branch(x, y, -Math.PI / 2, 120, 0);
  c.restore();
}

// -- drawing a card -------------------------------------------------------------------------------
function draw(c, card, index, total, t, time) {
  const [, , colour] = palette(card);
  backdrop(c, card, time, seedOf(`${card.kind}${story?.year}`));
  try {
    PAINT[card.kind]?.(c, card, t, colour);
  } catch (error) {
    console.warn("Void Wrapped card failed", card.kind, error);
  }
  footer(c, card, index, total);
}

function cardDuration(card) {
  return DURATIONS[card.kind] || 7;
}

// The card at rest: every animation finished.
function settledTime(card) {
  return card.kind === "verdict" ? 60 : cardDuration(card) + 2;
}

// -- the player ------------------------------------------------------------------------------------
function stage() {
  return ui?.byId("wrapped-canvas");
}

function cards() {
  return story?.cards || [];
}

function resize() {
  const canvas = stage();
  if (!canvas) return;
  const box = canvas.getBoundingClientRect();
  const ratio = Math.min(2, window.devicePixelRatio || 1);
  const width = Math.max(2, Math.round(box.width * ratio)), height = Math.max(2, Math.round(box.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
}

function frame(now) {
  player.frame = 0;
  const canvas = stage();
  const list = cards();
  if (!canvas || !list.length || !canvas.isConnected) return;
  resize();
  const c = canvas.getContext("2d");
  const index = clamp(player.index, 0, list.length - 1);
  const card = list[index];
  const still = player.paused || player.held;
  // Reduced motion draws each card finished, but the story still moves on in time.
  const elapsed = still ? player.pausedAt : (now - player.start) / 1000;
  const t = reducedMotion() ? settledTime(card) : elapsed;
  c.setTransform(canvas.width / W, 0, 0, canvas.height / H, 0, 0);
  draw(c, card, index, list.length, t, reducedMotion() ? 0 : now / 1000);
  // The card before, fading out over the new one.
  if (player.from && now - player.fromAt < 600) {
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.globalAlpha = 1 - (now - player.fromAt) / 600;
    c.drawImage(player.from, 0, 0, canvas.width, canvas.height);
    c.globalAlpha = 1;
  } else {
    player.from = null;
  }
  progress(index, elapsed, card);
  if (!still && elapsed >= cardDuration(card) && index < list.length - 1 && player.playing) {
    go(index + 1);
  }
  if (!player.frame && pageShown()) player.frame = requestAnimationFrame(frame);
}

// The room between the page's top and the deck's status bar: the stage
// (4:5) and its controls fit in it, and the side list scrolls within it.
function fit() {
  const wrap = ui?.byId("wrapped-stage-wrap"), stageNode = ui?.byId("wrapped-stage");
  if (!wrap || !stageNode || document.fullscreenElement || !wrap.offsetParent) return;
  const floor = document.querySelector(".statusbar")?.getBoundingClientRect().top || window.innerHeight;
  const room = Math.max(320, floor - wrap.getBoundingClientRect().top - 16);
  const controls = ui.byId("wrapped-stage-wrap").querySelector(".wrapped-controls")?.offsetHeight || 40;
  const height = Math.max(260, room - controls - 12);
  stageNode.style.width = `${Math.min(wrap.clientWidth, height * .8)}px`;
  const side = document.querySelector(".wrapped-side");
  if (side) side.style.maxHeight = `${room}px`;
}

function pageShown() {
  const page = document.querySelector('[data-page-name="wrapped"]');
  return Boolean(page?.classList.contains("active")) || Boolean(document.fullscreenElement);
}

function run() {
  if (!player.frame) player.frame = requestAnimationFrame(frame);
}

function snapshotOld() {
  const canvas = stage();
  if (!canvas || !canvas.width) return null;
  const copy = document.createElement("canvas");
  copy.width = canvas.width;
  copy.height = canvas.height;
  copy.getContext("2d").drawImage(canvas, 0, 0);
  return copy;
}

function go(index, {play = true} = {}) {
  const list = cards();
  if (!list.length) return;
  player.from = snapshotOld();
  player.fromAt = performance.now();
  player.index = clamp(index, 0, list.length - 1);
  player.start = performance.now();
  player.pausedAt = 0;
  player.paused = !play;
  player.playing = play || player.playing;
  renderIndex();
  run();
}

function togglePause() {
  if (!cards().length) return;
  if (player.paused) {
    player.start = performance.now() - player.pausedAt * 1000;
    player.paused = false;
    player.playing = true;
  } else {
    player.pausedAt = (performance.now() - player.start) / 1000;
    player.paused = true;
  }
  renderControls();
  run();
}

function progress(index, t, card) {
  const host = ui?.byId("wrapped-progress");
  if (!host) return;
  const list = cards();
  if (host.childElementCount !== list.length) {
    host.innerHTML = list.map(() => "<i><b></b></i>").join("");
  }
  [...host.children].forEach((bar, at) => {
    const fill = at < index ? 1 : at > index ? 0 : clamp(t / cardDuration(card));
    bar.firstElementChild.style.width = `${fill * 100}%`;
  });
}

// -- the page around the stage -------------------------------------------------------------------------
function shell(root) {
  root.innerHTML = `<div class="wrapped-page">
    <aside class="wrapped-side">
      <header class="wrapped-brand"><small>YOUR YEAR, TOLD BACK</small><h3>Void Wrapped</h3>
        <p>Everything you did in the black this year, as a story. Click through it, then keep the cards: each one saves or copies as a picture for Discord.</p></header>
      <section class="wrapped-years" aria-label="Years"><h4>CHOOSE A YEAR</h4><div id="wrapped-years"></div></section>
      <section class="wrapped-years wrapped-trips" aria-label="Expeditions" id="wrapped-trips-panel" hidden><h4>OR AN EXPEDITION</h4><div id="wrapped-trips"></div></section>
      <section class="wrapped-index" aria-label="Cards"><h4>THE STORY</h4><ol id="wrapped-index"></ol></section>
      <footer class="wrapped-actions">
        <button type="button" data-wrapped="refresh" title="Tell your year again, with everything that's happened since">↻ REFRESH MY YEAR</button>
        <button type="button" class="primary" data-wrapped="save_all">SAVE EVERY CARD</button>
        <button type="button" data-wrapped="open_folder">OPEN FOLDER</button>
        <small id="wrapped-saved"></small>
      </footer>
    </aside>
    <section class="wrapped-stage-wrap" id="wrapped-stage-wrap">
      <div class="wrapped-stage" id="wrapped-stage">
        <div class="wrapped-progress" id="wrapped-progress" aria-hidden="true"></div>
        <canvas id="wrapped-canvas" width="1080" height="1350" role="img" aria-label="Void Wrapped"></canvas>
        <div class="wrapped-loading" id="wrapped-loading" hidden><i></i><span>Gathering your year…</span></div>
        <button type="button" class="wrapped-start" id="wrapped-start" hidden>▶ PLAY YOUR YEAR</button>
      </div>
      <nav class="wrapped-controls" aria-label="Story controls">
        <button type="button" data-wrapped="previous" title="Previous card (←)">◀</button>
        <button type="button" data-wrapped="pause" id="wrapped-pause" title="Pause (Space)">❚❚</button>
        <button type="button" data-wrapped="next" title="Next card (→)">▶</button>
        <span id="wrapped-where">—</span>
        <button type="button" data-wrapped="save" title="Save this card as a picture">SAVE CARD</button>
        <button type="button" data-wrapped="copy" title="Copy this card, to paste into Discord">COPY</button>
        <button type="button" data-wrapped="fullscreen" title="Full screen (F)">⛶</button>
      </nav>
    </section>
  </div>`;
  const canvas = ui.byId("wrapped-canvas");
  let downAt = 0;
  canvas.addEventListener("pointerdown", () => {
    downAt = performance.now();
    holdTimer = window.setTimeout(() => {
      if (!player.paused) {
        player.held = true;
        player.pausedAt = (performance.now() - player.start) / 1000;
      }
    }, 220);
  });
  const release = (event) => {
    window.clearTimeout(holdTimer);
    if (player.held) {
      player.held = false;
      player.start = performance.now() - player.pausedAt * 1000;
      run();
      return;
    }
    if (event.type !== "pointerup" || performance.now() - downAt > 600 || !cards().length) return;
    const box = canvas.getBoundingClientRect();
    if (event.clientX - box.left < box.width * .3) go(player.index - 1);
    else if (player.index < cards().length - 1) go(player.index + 1);
  };
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointerleave", release);
  root.addEventListener("click", onClick);
  document.addEventListener("keydown", onKey);
  new ResizeObserver(() => { fit(); run(); }).observe(ui.byId("wrapped-stage-wrap"));
  window.addEventListener("resize", fit);
  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement) fit();
    else ui.byId("wrapped-stage").style.width = "";
    run();
  });
}
let holdTimer = 0;

function onKey(event) {
  if (!pageShown() || event.target.closest?.("input, textarea, select, [contenteditable]")) return;
  if (event.key === "ArrowRight") { go(player.index + 1); event.preventDefault(); }
  else if (event.key === "ArrowLeft") { go(player.index - 1); event.preventDefault(); }
  else if (event.code === "Space" && !event.repeat) { togglePause(); event.preventDefault(); }
  else if (event.key === "f" || event.key === "F") fullscreen();
}

function fullscreen() {
  const host = ui.byId("wrapped-stage-wrap");
  if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
  else host.requestFullscreen?.().then(() => run()).catch(() => ui.showToast("Full screen isn't available here"));
}

async function onClick(event) {
  const pick = event.target.closest("[data-wrapped-year]");
  if (pick) {
    choose(Number(pick.dataset.wrappedYear));
    return;
  }
  const pickTrip = event.target.closest("[data-wrapped-trip]");
  if (pickTrip) {
    chooseTrip(pickTrip.dataset.wrappedTrip);
    return;
  }
  const jump = event.target.closest("[data-wrapped-card]");
  if (jump) {
    go(Number(jump.dataset.wrappedCard), {play: !player.paused});
    return;
  }
  if (event.target.closest("#wrapped-start")) {
    ui.byId("wrapped-start").hidden = true;
    go(0);
    return;
  }
  const button = event.target.closest("[data-wrapped]");
  if (!button) return;
  const action = button.dataset.wrapped;
  if (action === "previous") go(player.index - 1, {play: !player.paused});
  else if (action === "next") go(player.index + 1, {play: !player.paused});
  else if (action === "pause") togglePause();
  else if (action === "fullscreen") fullscreen();
  else if (action === "save" || action === "copy") await keep(player.index, action, button);
  else if (action === "save_all") await keepAll(button);
  else if (action === "open_folder") ui.command("workspace", {page: "wrapped", operation: "open_folder"});
  else if (action === "refresh" && trip) {
    story = null;
    await load(year, trip);
  } else if (action === "refresh" && year) {
    // Told again from scratch: new journals, trades and the rest counted.
    button.disabled = true;
    await ui.command("workspace", {page: "wrapped", operation: "retell", year});
    story = null;
    await load(year);
    button.disabled = false;
  }
}

function picture(index) {
  const card = cards()[index];
  const canvas = document.createElement("canvas");
  canvas.width = W * EXPORT_SCALE;
  canvas.height = H * EXPORT_SCALE;
  const c = canvas.getContext("2d");
  c.setTransform(EXPORT_SCALE, 0, 0, EXPORT_SCALE, 0, 0);
  draw(c, card, index, cards().length, settledTime(card), 3.2);
  return canvas.toDataURL("image/jpeg", .93);
}

async function keep(index, action, button) {
  const card = cards()[index];
  if (!card) return false;
  if (button) button.disabled = true;
  const done = await ui.command("workspace", {page: "wrapped", operation: action, picture: picture(index), year: story.year,
    index: index + 1, card: nameOf(card)});
  if (button) button.disabled = false;
  if (action === "copy") ui.showToast(done ? "Card copied: paste it into Discord" : "The card couldn't be copied");
  else ui.showToast(done ? "Card saved in the wrapped folder" : "The card couldn't be saved");
  return done;
}

async function keepAll(button) {
  const list = cards();
  if (!list.length) return;
  button.disabled = true;
  let saved = 0;
  for (let index = 0; index < list.length; index += 1) {
    button.textContent = `SAVING ${index + 1} / ${list.length}…`;
    const done = await ui.command("workspace", {page: "wrapped", operation: "save", picture: picture(index), year: story.year,
      index: index + 1, card: nameOf(list[index]), last: index === list.length - 1});
    if (done) saved += 1;
    await new Promise((resolve) => setTimeout(resolve, 30));
  }
  button.disabled = false;
  button.textContent = "SAVE EVERY CARD";
  ui.showToast(saved === list.length ? `All ${saved} cards saved in the wrapped folder` : `${saved} of ${list.length} cards saved`);
}

function renderTrips() {
  const host = ui.byId("wrapped-trips");
  const key = JSON.stringify([trips, trip]);
  if (!host || key === lastTripsKey) return;
  lastTripsKey = key;
  ui.byId("wrapped-trips-panel").hidden = !trips.length;
  host.innerHTML = trips.map((row) => `<button type="button" data-wrapped-trip="${ui.escapeHtml(row.id)}" class="${row.id === trip ? "active" : ""}">
      <b>${ui.escapeHtml(row.name)}</b><small>${ui.escapeHtml(String(row.status || "").toUpperCase())} · ${fmt(row.jumps)} jumps</small></button>`).join("");
}

function renderYears() {
  const host = ui.byId("wrapped-years");
  const key = JSON.stringify([years, year, trip]);
  if (!host || key === lastYearsKey) return;
  lastYearsKey = key;
  host.innerHTML = years.length ? years.map((row) => `<button type="button" data-wrapped-year="${row.year}" class="${row.year === year && !trip ? "active" : ""}">
      <b>${row.elite_year}</b><small>${row.year} · ${fmt(row.jumps)} jumps · ${fmt(row.sessions)} sessions</small></button>`).join("")
    : `<p class="wrapped-empty">Your journal hasn't been read yet. Fly a little, and your year will be here.</p>`;
}

function renderIndex() {
  const host = ui.byId("wrapped-index");
  if (!host) return;
  const list = cards();
  const key = JSON.stringify([story?.year, list.map((card) => card.kind), player.index]);
  if (host.dataset.key !== key) {
    host.dataset.key = key;
    host.innerHTML = list.map((card, index) => `<li><button type="button" data-wrapped-card="${index}" class="${index === player.index ? "active" : ""}">
      <i style="--dot:${palette(card)[2]}"></i>${ui.escapeHtml(nameOf(card))}</button></li>`).join("");
  }
  renderControls();
}

function renderControls() {
  const where = ui.byId("wrapped-where");
  if (where) where.textContent = cards().length ? `${player.index + 1} / ${cards().length} · ${nameOf(cards()[player.index])}` : "—";
  const pause = ui.byId("wrapped-pause");
  if (pause) {
    const state = player.paused ? "▶" : "❚❚";
    if (pause.textContent !== state) pause.textContent = state;
    pause.title = player.paused ? "Play (Space)" : "Pause (Space)";
  }
}

async function load(wanted, tripId = "") {
  const ticket = ++fetching;
  window.clearTimeout(pollTimer);
  const loading = ui.byId("wrapped-loading");
  try {
    const query = tripId ? `expedition=${encodeURIComponent(tripId)}` : `year=${wanted}`;
    const response = await fetch(ui.apiUrl(`/api/data/wrapped?${query}`), {cache: "no-store"});
    const answer = await response.json();
    if (ticket !== fetching) return;
    if (answer.working) {
      loading.hidden = false;
      pollTimer = window.setTimeout(() => load(wanted, tripId), 1200);
      return;
    }
    loading.hidden = true;
    const changed = JSON.stringify(answer.cards?.map((card) => card.kind)) !== JSON.stringify(story?.cards?.map((card) => card.kind))
      || answer.year !== story?.year || answer.trip?.id !== story?.trip?.id;
    story = answer;
    await preload();
    if (changed) {
      player.index = 0;
      player.paused = true;
      player.playing = false;
      player.pausedAt = 4;
      ui.byId("wrapped-start").hidden = !cards().length || story.empty;
    }
    if (story.empty) ui.showToast("Nothing flown that year yet");
    renderIndex();
    run();
  } catch (error) {
    if (ticket === fetching) {
      loading.hidden = true;
      ui.showToast("Your year couldn't be gathered");
    }
  }
}

async function preload() {
  const wanted = cards().filter((card) => card.kind === "postcards" && card.featured?.id).map((card) => card.featured.id);
  await Promise.all(wanted.filter((id) => !images.has(id)).map((id) => new Promise((resolve) => {
    const image = new Image();
    image.onload = () => { images.set(id, image); resolve(); };
    image.onerror = () => resolve();
    image.src = ui.apiUrl(`/media/postcard/${id}.png`);
  })));
}

function choose(wanted) {
  if (!wanted || (wanted === year && !trip)) return;
  year = wanted;
  trip = "";
  lastYearsKey = lastTripsKey = "";
  renderYears();
  renderTrips();
  load(year);
}

function chooseTrip(id) {
  if (!id || id === trip) return;
  trip = id;
  lastYearsKey = lastTripsKey = "";
  renderYears();
  renderTrips();
  load(year, trip);
}

export function renderWrapped(data = {}, shared) {
  ui = shared;
  const root = ui.byId("wrapped-workspace");
  if (!root) return;
  if (!root.querySelector(".wrapped-page")) shell(root);
  root.classList.remove("loading-panel");
  years = Array.isArray(data.years) ? data.years : [];
  trips = Array.isArray(data.trips) ? data.trips : [];
  // TELL IT on the Expeditions page opens here on that trip.
  const asked = data.trip_request || {};
  if (asked.id && Number(asked.seq || 0) > tripSeq) {
    tripSeq = Number(asked.seq || 0);
    chooseTrip(asked.id);
  }
  const saved = data.saved || {};
  ui.byId("wrapped-saved").textContent = saved.count ? `${fmt(saved.count)} saved in ${data.folder || "the wrapped folder"}` : "";
  if (!year && years.length) {
    // December onwards (and January) the year just ending; otherwise this year.
    const now = new Date();
    const fresh = years.find((row) => row.year === (now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear()) && row.jumps);
    year = (fresh || years.find((row) => row.jumps) || years[0]).year;
    load(year);
  }
  renderYears();
  renderTrips();
  fit();
  run();
}
