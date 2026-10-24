// Postcards drawn in the page (5.6.3): the editor's card. A design is the
// card's look (paper, ink, lettering colour, the photo's crop and filter, the
// frame, the angle, what's behind it) and its layers: every word, the
// postmark, the chips and the stickers, each placed where you put it. What
// the editor shows is what gets saved: the PNG is this drawing.
//
// Card coordinates are pixels on a 1500-wide card; the editor scales them.

export const CARD = {w: 1500, h: 1170};
export const BASES = {
  polaroid: {name: "Polaroid", photo: {x: 44, y: 44, w: 1412, h: 794}},
  airmail: {name: "Airmail", photo: {x: 74, y: 74, w: 1352, h: 760}},
  holo: {name: "Holo", photo: {x: 36, y: 36, w: 1428, h: 803}},
  vintage: {name: "Vintage", photo: {x: 64, y: 64, w: 1372, h: 772}},
};
export const FONTS = {
  hud: {name: "Cockpit capitals", family: '"Bahnschrift SemiCondensed", Bahnschrift, "Segoe UI", sans-serif', weight: 700},
  hand: {name: "Handwriting", family: '"Segoe Print", "Ink Free", "Comic Sans MS", cursive', weight: 400},
  script: {name: "Script", family: '"Segoe Script", "Segoe Print", cursive', weight: 400},
  serif: {name: "Serif", family: 'Georgia, "Times New Roman", serif', weight: 700},
  display: {name: "Heavy", family: '"Segoe UI Black", "Arial Black", sans-serif', weight: 900},
  mono: {name: "Terminal", family: 'Consolas, "Courier New", monospace', weight: 700},
};
export const FILTERS = {
  none: {name: "Natural"}, vivid: {name: "Vivid"}, sepia: {name: "Sepia"}, mono: {name: "Black & white"},
  cool: {name: "Cool"}, warm: {name: "Warm"}, dusk: {name: "Dusk"}, neon: {name: "Neon"}, faded: {name: "Faded film"},
};
export const BACKDROPS = {none: "Nothing (see-through)", colour: "A colour", desk: "A desk", space: "Deep space", hangar: "Hangar floor"};
export const STICKERS = {
  wings: "Wings", first: "First discovered", explorer: "Explorer badge", postage: "Postage stamp", thargoid: "Thargoid",
  guardian: "Guardian glyph", planet: "Ringed planet", star: "Star", heart: "Heart", o7: "o7", wish: "Wish you were here",
  fragile: "Handle with care", elite: "Elite", tape: "Tape", arrow: "Arrow", ring: "Circled", sparkle: "Sparkle", fuel: "Fuel low",
};
// The colour names a layer can follow, so a new look recolours it.
export const TOKENS = ["ink", "soft", "accent", "paper", "white", "black"];

const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
let uid = 0;
export const newId = (kind) => `${kind}-${Date.now().toString(36)}-${(uid += 1)}`;

export function mix(a, b, k) {
  const pa = parseInt(String(a).slice(1), 16), pb = parseInt(String(b).slice(1), 16);
  if (!Number.isFinite(pa) || !Number.isFinite(pb)) return a;
  const ch = (shift) => Math.round(((pa >> shift) & 255) * (1 - k) + ((pb >> shift) & 255) * k);
  return `#${[16, 8, 0].map((shift) => ch(shift).toString(16).padStart(2, "0")).join("")}`;
}

export function colourOf(design, value) {
  if (!value) return design.ink;
  if (value === "white") return "#ffffff";
  if (value === "black") return "#000000";
  if (TOKENS.includes(value)) return design[value] || design.ink;
  return value;
}

// ---- The card's starting design: as the app draws it, but every part movable. ----
export function defaultDesign(info, base = "polaroid", look = {}) {
  base = BASES[base] ? base : "polaroid";
  const P = BASES[base].photo;
  const colours = {paper: look.paper || "#f3efe2", ink: look.ink || "#141a22", soft: look.soft || "#5a6470", accent: look.greet || look.accent || "#ff7a18"};
  const font = look.font || (base === "vintage" ? "serif" : "hud");
  const sizes = info.sizes || {};
  const kl = (sizes.lettering || 100) / 100, kn = (sizes.note || 100) / 100, kd = (sizes.details || 100) / 100;
  const bottom = P.y + P.h;
  const layers = [];
  const add = (layer) => { layers.push({id: newId(layer.role || layer.kind), rotate: 0, opacity: 1, hidden: false, ...layer}); };
  const onPhoto = Boolean(info.photo);
  const greeting = String(info.greeting ?? "Greetings from");
  if (greeting) add({kind: "text", role: "greeting", text: greeting, x: P.x + 50, y: onPhoto ? bottom - 172 * kl : P.y + 70, size: 34 * kl, font: "hud",
    caps: true, spacing: .3, colour: onPhoto ? "white" : "soft", shadow: onPhoto});
  add({kind: "text", role: "title", text: info.title || "Somewhere out here", x: P.x + 46, y: onPhoto ? bottom - 78 * kl : P.y + 180, size: 108 * kl,
    font, caps: font === "hud", skew: font === "hud" ? .16 : 0, colour: "accent", shadow: onPhoto, fit: P.w - 100});
  const place = [info.place, info.region].filter(Boolean).join(" · ");
  if (place) add({kind: "text", role: "place", text: place, x: P.x + 50, y: onPhoto ? bottom - 32 : P.y + 226, size: 26 * kl, font: "hud", caps: true,
    spacing: .2, colour: onPhoto ? "white" : "soft", shadow: onPhoto});
  const noteY = bottom + 92 * kn;
  if (info.note) {
    add({kind: "text", role: "note", text: info.note, x: 70, y: noteY, size: 50 * kn, font: "hand", colour: "ink", width: info.postmark ? 900 : 1300});
    add({kind: "text", role: "signed", text: `— ${info.signed || "the Watcher"}`, x: info.postmark ? 960 : 1430, y: noteY + 80 * kn, size: 44 * kn,
      font: "hand", colour: "soft", align: "right"});
  }
  if (info.postmark) add({kind: "postmark", role: "postmark", x: 1270, y: bottom + 150, size: 118, rotate: -14, colour: "accent",
    top: String(info.system || info.title || "").toUpperCase().slice(0, 26), middle: info.time || "", bottom: String(info.date || "").toUpperCase()});
  if ((info.facts || []).length) add({kind: "chips", role: "facts", items: info.facts.map((fact) => String(fact).toUpperCase()), x: 70, y: CARD.h - 196 * kd, size: 26 * kd, colour: "soft"});
  const where = [info.note ? info.doing : "", info.coordinates].filter(Boolean).join(" · ");
  if (where) add({kind: "text", role: "where", text: where, x: 70, y: CARD.h - 108 * kd, size: 26 * kd, font: "hud", caps: true, spacing: .2, colour: "soft"});
  add({kind: "rule", role: "rule", x: 70, y: CARD.h - 78, width: CARD.w - 140, colour: "soft"});
  add({kind: "text", role: "date", text: info.date || "", x: 70, y: CARD.h - 34, size: 28 * kd, font: "hud", caps: true, spacing: .25, colour: "soft"});
  if (info.time) add({kind: "text", role: "time", text: info.time, x: CARD.w - 70, y: CARD.h - 34, size: 28 * kd, font: "hud", caps: true, spacing: .25, colour: "soft", align: "right"});
  return {
    v: 2, base, ...colours, font,
    filter: look.filter && FILTERS[look.filter] ? look.filter : base === "vintage" ? "sepia" : "none",
    adjust: {bright: 100, contrast: 100, sat: 100},
    angle: look.angle ?? -1.2, backdrop: {kind: look.backdrop || "none", colour: look.bg_colour || "#1b2433"},
    photo: {zoom: 1, x: 0, y: 0}, shade: true, texture: true, layers,
  };
}

// A new look keeps your words where you put them; only the colours change.
export function applyBase(design, base, look = {}) {
  const P0 = BASES[design.base]?.photo || BASES.polaroid.photo, P1 = BASES[base].photo;
  const next = {...design, base, paper: look.paper || design.paper, ink: look.ink || design.ink, soft: look.soft || design.soft, accent: look.greet || design.accent};
  if (base === "vintage" && design.filter === "none") next.filter = "sepia";
  if (design.base === "vintage" && base !== "vintage" && design.filter === "sepia") next.filter = "none";
  // Words on the photo move with the photo's frame.
  next.layers = design.layers.map((layer) => (layer.y < P0.y + P0.h + 10
    ? {...layer, x: P1.x + (layer.x - P0.x) * P1.w / P0.w, y: P1.y + (layer.y - P0.y) * P1.h / P0.h} : layer));
  return next;
}

// ---- Drawing. ----
function photoFilter(design) {
  const a = design.adjust || {};
  const parts = [`brightness(${(a.bright ?? 100) / 100})`, `contrast(${(a.contrast ?? 100) / 100})`, `saturate(${(a.sat ?? 100) / 100})`];
  const extra = {vivid: "saturate(1.45) contrast(1.08)", sepia: "sepia(.85) contrast(1.05)", mono: "grayscale(1) contrast(1.1)",
    cool: "saturate(.9) hue-rotate(-8deg)", warm: "sepia(.25) saturate(1.2)", dusk: "saturate(1.2) hue-rotate(-18deg) contrast(1.05)",
    neon: "saturate(1.8) contrast(1.15)", faded: "contrast(.82) saturate(.75) brightness(1.08)"}[design.filter];
  if (extra) parts.push(extra);
  return parts.join(" ");
}

function tint(design) {
  return {cool: ["rgba(40, 110, 200, .16)", "soft-light"], warm: ["rgba(255, 150, 60, .14)", "soft-light"],
    dusk: ["rgba(180, 60, 160, .2)", "soft-light"], neon: ["rgba(0, 220, 255, .12)", "screen"], faded: ["rgba(240, 225, 200, .18)", "screen"]}[design.filter];
}

function drawPhoto(ctx, design, photo, P) {
  ctx.save();
  ctx.beginPath();
  if (design.base === "vintage") ctx.roundRect(P.x, P.y, P.w, P.h, 18);
  else ctx.rect(P.x, P.y, P.w, P.h);
  ctx.clip();
  if (photo && photo.width) {
    const zoom = clamp(design.photo?.zoom || 1, 1, 5);
    const scale = Math.max(P.w / photo.width, P.h / photo.height) * zoom;
    const w = photo.width * scale, h = photo.height * scale;
    const x = P.x + (P.w - w) / 2 - clamp(design.photo?.x || 0, -1, 1) * (w - P.w) / 2;
    const y = P.y + (P.h - h) / 2 - clamp(design.photo?.y || 0, -1, 1) * (h - P.h) / 2;
    ctx.filter = photoFilter(design);
    ctx.drawImage(photo, x, y, w, h);
    ctx.filter = "none";
    const wash = tint(design);
    if (wash) {
      ctx.globalCompositeOperation = wash[1];
      ctx.fillStyle = wash[0];
      ctx.fillRect(P.x, P.y, P.w, P.h);
      ctx.globalCompositeOperation = "source-over";
    }
  } else {
    // No picture: a night sky, so the card still reads.
    const sky = ctx.createLinearGradient(0, P.y, 0, P.y + P.h);
    sky.addColorStop(0, "#05070f");
    sky.addColorStop(1, mix(design.accent, "#05070f", .78));
    ctx.fillStyle = sky;
    ctx.fillRect(P.x, P.y, P.w, P.h);
    ctx.fillStyle = "#ffffff";
    for (let i = 0; i < 160; i += 1) {
      ctx.globalAlpha = .2 + ((i * 37) % 10) / 14;
      ctx.fillRect(P.x + (i * 389) % P.w, P.y + (i * 233) % P.h, i % 7 ? 1.5 : 3, i % 7 ? 1.5 : 3);
    }
    ctx.globalAlpha = 1;
  }
  if (design.base === "holo") {
    ctx.fillStyle = "rgba(0, 0, 0, .22)";
    for (let y = P.y; y < P.y + P.h; y += 5) ctx.fillRect(P.x, y, P.w, 1.4);
  }
  if (design.shade !== false) {
    const shade = ctx.createLinearGradient(0, P.y + P.h * .5, 0, P.y + P.h);
    shade.addColorStop(0, "rgba(0,0,0,0)");
    shade.addColorStop(1, "rgba(0,0,0,.72)");
    ctx.fillStyle = shade;
    ctx.fillRect(P.x, P.y + P.h * .5, P.w, P.h * .5);
  }
  ctx.restore();
  // The photo's edge.
  ctx.strokeStyle = design.base === "holo" ? mix(design.accent, design.paper, .4) : "rgba(0,0,0,.25)";
  ctx.lineWidth = design.base === "holo" ? 2 : 1.5;
  ctx.beginPath();
  if (design.base === "vintage") ctx.roundRect(P.x, P.y, P.w, P.h, 18);
  else ctx.rect(P.x, P.y, P.w, P.h);
  ctx.stroke();
}

let grain = null;
function paperGrain() {
  if (grain) return grain;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 160;
  const g = canvas.getContext("2d");
  const image = g.createImageData(160, 160);
  for (let i = 0; i < image.data.length; i += 4) {
    const v = 128 + (Math.random() - .5) * 60;
    image.data[i] = image.data[i + 1] = image.data[i + 2] = v;
    image.data[i + 3] = 22;
  }
  g.putImageData(image, 0, 0);
  grain = canvas;
  return grain;
}

function cardShape(ctx, design) {
  ctx.beginPath();
  if (design.base === "vintage") {
    // A deckled edge: small even scallops round the card.
    const step = 30, r = 6;
    ctx.moveTo(0, 0);
    for (let x = 0; x < CARD.w; x += step) ctx.quadraticCurveTo(x + step / 2, -r, x + step, 0);
    for (let y = 0; y < CARD.h; y += step) ctx.quadraticCurveTo(CARD.w + r, y + step / 2, CARD.w, y + step);
    for (let x = CARD.w; x > 0; x -= step) ctx.quadraticCurveTo(x - step / 2, CARD.h + r, x - step, CARD.h);
    for (let y = CARD.h; y > 0; y -= step) ctx.quadraticCurveTo(-r, y - step / 2, 0, y - step);
    ctx.closePath();
  } else ctx.rect(0, 0, CARD.w, CARD.h);
}

function drawPaper(ctx, design) {
  cardShape(ctx, design);
  if (design.base === "holo") {
    const panel = ctx.createLinearGradient(0, 0, CARD.w, CARD.h);
    panel.addColorStop(0, mix(design.paper, "#000000", .15));
    panel.addColorStop(1, design.paper);
    ctx.fillStyle = panel;
  } else ctx.fillStyle = design.paper;
  ctx.fill();
  if (design.texture !== false && design.base !== "holo") {
    ctx.save();
    cardShape(ctx, design);
    ctx.clip();
    ctx.fillStyle = ctx.createPattern(paperGrain(), "repeat");
    ctx.fillRect(0, 0, CARD.w, CARD.h);
    if (design.base === "vintage") {
      const age = ctx.createRadialGradient(CARD.w / 2, CARD.h / 2, CARD.h * .3, CARD.w / 2, CARD.h / 2, CARD.w * .7);
      age.addColorStop(0, "rgba(120, 80, 30, 0)");
      age.addColorStop(1, "rgba(120, 80, 30, .28)");
      ctx.fillStyle = age;
      ctx.fillRect(0, 0, CARD.w, CARD.h);
    }
    ctx.restore();
  }
}

function drawFrame(ctx, design) {
  if (design.base === "airmail") {
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, CARD.w, CARD.h);
    ctx.rect(30, 30, CARD.w - 60, CARD.h - 60);
    ctx.clip("evenodd");
    const band = 44;
    for (let i = -CARD.h; i < CARD.w + CARD.h; i += band * 2) {
      ctx.fillStyle = (i / (band * 2)) % 2 ? "#2a4c9a" : "#c8323c";
      ctx.beginPath();
      ctx.moveTo(i, 0); ctx.lineTo(i + band, 0); ctx.lineTo(i + band - CARD.h, CARD.h); ctx.lineTo(i - CARD.h, CARD.h);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  } else if (design.base === "holo") {
    ctx.strokeStyle = mix(design.accent, design.paper, .55);
    ctx.lineWidth = 3;
    ctx.strokeRect(1.5, 1.5, CARD.w - 3, CARD.h - 3);
    ctx.fillStyle = design.accent;
    ctx.shadowColor = design.accent;
    ctx.shadowBlur = 18;
    const arm = 70, thick = 8;
    for (const [x, y, sx, sy] of [[0, 0, 1, 1], [CARD.w, 0, -1, 1], [0, CARD.h, 1, -1], [CARD.w, CARD.h, -1, -1]]) {
      ctx.fillRect(x, y, sx * arm, sy * thick);
      ctx.fillRect(x, y, sx * thick, sy * arm);
    }
    ctx.shadowBlur = 0;
  }
}

function fontOf(layer) {
  return FONTS[layer.font] || FONTS.hud;
}

function setFont(ctx, layer, size) {
  const font = fontOf(layer);
  ctx.font = `${layer.italic ? "italic " : ""}${layer.weight || font.weight} ${size}px ${font.family}`;
  ctx.letterSpacing = `${(layer.spacing || 0) * size}px`;
}

function lines(ctx, layer, size) {
  const raw = String(layer.text ?? "");
  const text = layer.caps ? raw.toUpperCase() : raw;
  const out = [];
  for (const paragraph of text.split("\n")) {
    if (!layer.width) { out.push(paragraph); continue; }
    let line = "";
    for (const word of paragraph.split(/\s+/)) {
      const next = line ? `${line} ${word}` : word;
      if (line && ctx.measureText(next).width > layer.width) { out.push(line); line = word; }
      else line = next;
    }
    out.push(line);
  }
  return out;
}

// Each layer's box, for the editor: centre, size and turn, in card pixels.
function measure(ctx, design, layer) {
  if (layer.kind === "text") {
    let size = layer.size;
    setFont(ctx, layer, size);
    let rows = lines(ctx, layer, size);
    let widest = Math.max(1, ...rows.map((row) => ctx.measureText(row).width));
    if (layer.fit && widest > layer.fit) {
      size = Math.max(12, size * layer.fit / widest);
      setFont(ctx, layer, size);
      rows = lines(ctx, layer, size);
      widest = Math.max(1, ...rows.map((row) => ctx.measureText(row).width));
    }
    const lineH = size * (layer.font === "hand" || layer.font === "script" ? 1.32 : 1.12);
    const height = rows.length * lineH;
    const w = widest + size * Math.abs(layer.skew || 0);
    const left = layer.align === "right" ? layer.x - w : layer.align === "center" ? layer.x - w / 2 : layer.x;
    return {size, rows, lineH, w, h: height, cx: left + w / 2, cy: layer.y - size * .8 + height / 2 - lineH * .1};
  }
  if (layer.kind === "chips") {
    ctx.font = `700 ${layer.size}px ${FONTS.hud.family}`;
    ctx.letterSpacing = `${layer.size * .1}px`;
    const pad = layer.size * .6;
    const widths = layer.items.map((item) => ctx.measureText(item).width + pad * 2);
    const w = widths.reduce((sum, width) => sum + width, 0) + (widths.length - 1) * layer.size * .45;
    const h = layer.size * 1.75;
    return {widths, w, h, cx: layer.x + w / 2, cy: layer.y + h / 2};
  }
  if (layer.kind === "rule") return {w: layer.width, h: 12, cx: layer.x + layer.width / 2, cy: layer.y};
  // Postmarks and stickers: a square round their centre.
  const span = layer.kind === "postmark" ? layer.size * 2.7 : layer.size;
  return {w: span, h: layer.kind === "postmark" ? layer.size * 2.1 : layer.size, cx: layer.kind === "postmark" ? layer.x - layer.size * .3 : layer.x, cy: layer.y};
}

function drawText(ctx, design, layer, box) {
  setFont(ctx, layer, box.size);
  ctx.textBaseline = "alphabetic";
  ctx.textAlign = "left";
  const colour = colourOf(design, layer.colour);
  box.rows.forEach((row, index) => {
    const width = ctx.measureText(row).width;
    const x = layer.align === "right" ? layer.x - width : layer.align === "center" ? layer.x - width / 2 : layer.x;
    const y = layer.y + index * box.lineH;
    ctx.save();
    if (layer.skew) {
      ctx.translate(x, y);
      ctx.transform(1, 0, -layer.skew, 1, 0, 0);
      ctx.translate(-x, -y);
    }
    if (layer.outline) {
      ctx.lineWidth = Math.max(2, box.size * .08);
      ctx.strokeStyle = colourOf(design, layer.outline);
      ctx.lineJoin = "round";
      ctx.strokeText(row, x, y);
    }
    if (layer.shadow) {
      ctx.shadowColor = "rgba(0,0,0,.75)";
      ctx.shadowBlur = box.size * .22;
      ctx.shadowOffsetY = box.size * .04;
    }
    if (layer.glow) {
      ctx.shadowColor = colour;
      ctx.shadowBlur = box.size * .45;
    }
    ctx.fillStyle = colour;
    ctx.fillText(row, x, y);
    ctx.restore();
  });
  ctx.letterSpacing = "0px";
}

function drawChips(ctx, design, layer, box) {
  const colour = colourOf(design, layer.colour);
  let x = layer.x;
  ctx.font = `700 ${layer.size}px ${FONTS.hud.family}`;
  ctx.letterSpacing = `${layer.size * .1}px`;
  ctx.textBaseline = "middle";
  layer.items.forEach((item, index) => {
    const w = box.widths[index];
    ctx.beginPath();
    ctx.roundRect(x, layer.y, w, box.h, layer.size * .25);
    ctx.strokeStyle = mix(colour, design.paper, .25);
    ctx.lineWidth = Math.max(1.5, layer.size * .1);
    ctx.stroke();
    ctx.fillStyle = colour;
    ctx.fillText(item, x + layer.size * .6, layer.y + box.h / 2 + 1);
    x += w + layer.size * .45;
  });
  ctx.textBaseline = "alphabetic";
  ctx.letterSpacing = "0px";
}

function arcText(ctx, text, radius, middle, downward, size) {
  ctx.font = `700 ${size}px ${FONTS.hud.family}`;
  const chars = [...text];
  const widths = chars.map((char) => ctx.measureText(char).width + size * .12);
  const total = widths.reduce((sum, width) => sum + width, 0);
  let angle = middle + (downward ? 1 : -1) * total / radius / 2;
  for (const [index, char] of chars.entries()) {
    const step = widths[index] / radius;
    const at = angle + (downward ? -1 : 1) * step / 2;
    ctx.save();
    ctx.rotate(at);
    ctx.translate(0, -radius);
    if (downward) ctx.rotate(Math.PI);
    ctx.fillText(char, -ctx.measureText(char).width / 2, size * .35);
    ctx.restore();
    angle += (downward ? -1 : 1) * step;
  }
}

function drawPostmark(ctx, design, layer) {
  const colour = colourOf(design, layer.colour);
  const r = layer.size;
  ctx.save();
  ctx.translate(layer.x, layer.y);
  ctx.rotate(layer.rotate * Math.PI / 180);
  ctx.globalAlpha *= .85;
  ctx.strokeStyle = colour;
  ctx.fillStyle = colour;
  ctx.lineWidth = r * .045;
  // The cancellation waves off to the left.
  for (let i = -2; i <= 2; i += 1) {
    ctx.beginPath();
    for (let x = -r * 2.4; x <= -r * .9; x += 4) ctx.lineTo(x, i * r * .2 + Math.sin(x / (r * .18)) * r * .05);
    ctx.stroke();
  }
  ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.stroke();
  ctx.lineWidth = r * .03;
  ctx.beginPath(); ctx.arc(0, 0, r * .62, 0, Math.PI * 2); ctx.stroke();
  arcText(ctx, String(layer.top || ""), r * .81, 0, false, r * .19);
  arcText(ctx, String(layer.bottom || ""), r * .81, Math.PI, true, r * .17);
  ctx.font = `700 ${r * .3}px ${FONTS.hud.family}`;
  ctx.textAlign = "center";
  ctx.fillText(String(layer.middle || ""), 0, r * .11);
  ctx.textAlign = "left";
  ctx.restore();
}

// ---- Stickers: drawn here, so nothing to download. A 100-unit box. ----
function stamp(ctx, words, colour, sub = "") {
  ctx.strokeStyle = colour; ctx.fillStyle = colour;
  ctx.lineWidth = 4;
  ctx.beginPath(); ctx.roundRect(-48, -24, 96, 48, 6); ctx.stroke();
  ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.roundRect(-43, -19, 86, 38, 4); ctx.stroke();
  ctx.textAlign = "center";
  ctx.font = `900 ${words.length > 9 ? 11 : 15}px ${FONTS.display.family}`;
  ctx.fillText(words, 0, sub ? 0 : 5);
  if (sub) { ctx.font = `700 9px ${FONTS.hud.family}`; ctx.fillText(sub, 0, 13); }
  ctx.textAlign = "left";
}

function star(ctx, r, inner = .45) {
  ctx.beginPath();
  for (let i = 0; i < 10; i += 1) {
    const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * inner : r;
    ctx.lineTo(Math.cos(a) * rr, Math.sin(a) * rr);
  }
  ctx.closePath();
}

const STICKER_COLOURS = {wings: "#e8c66a", first: "#c8323c", explorer: "#2fa3d6", postage: "#2a4c9a", thargoid: "#4ee5b0", guardian: "#5fd4ff",
  planet: "#e8a36a", star: "#ffd166", heart: "#ff5f8f", o7: "#ffffff", wish: "#c8323c", fragile: "#d23a2a", elite: "#e8c66a", tape: "#f3e7b0",
  arrow: "#ff7a18", ring: "#ff3b3b", sparkle: "#ffffff", fuel: "#ff8a3d"};

export function stickerColour(kind) {
  return STICKER_COLOURS[kind] || "#ffffff";
}

export function drawSticker(ctx, design, layer) {
  const colour = colourOf(design, layer.colour || stickerColour(layer.sticker));
  ctx.save();
  ctx.translate(layer.x, layer.y);
  ctx.rotate((layer.rotate || 0) * Math.PI / 180);
  ctx.scale(layer.size / 100, layer.size / 100);
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  const kind = layer.sticker;
  if (kind === "wings") {
    ctx.fillStyle = colour;
    for (const side of [-1, 1]) {
      for (let i = 0; i < 4; i += 1) {
        ctx.beginPath();
        ctx.moveTo(side * 10, -4 + i * 7);
        ctx.quadraticCurveTo(side * (30 + i * 4), -18 + i * 9, side * (48 - i * 6), -10 + i * 9);
        ctx.quadraticCurveTo(side * (30 + i * 2), -2 + i * 7, side * 10, 4 + i * 7);
        ctx.fill();
      }
    }
    star(ctx, 13);
    ctx.fill();
    ctx.strokeStyle = "rgba(0,0,0,.35)"; ctx.lineWidth = 1.5; ctx.stroke();
  } else if (kind === "first" || kind === "fragile" || kind === "elite") {
    const words = {first: ["FIRST", "DISCOVERED"], fragile: ["HANDLE", "WITH CARE"], elite: ["ELITE", "PILOT"]}[kind];
    ctx.globalAlpha *= .9;
    if (kind === "first") {
      ctx.strokeStyle = colour; ctx.fillStyle = colour; ctx.lineWidth = 4;
      ctx.beginPath(); ctx.arc(0, 0, 46, 0, Math.PI * 2); ctx.stroke();
      ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(0, 0, 39, 0, Math.PI * 2); ctx.stroke();
      star(ctx, 9); ctx.fill();
      ctx.save(); ctx.translate(0, 0);
      arcText(ctx, "FIRST DISCOVERED", 31, 0, false, 10);
      arcText(ctx, "· EXPLORER ·", 31, Math.PI, true, 9);
      ctx.restore();
    } else stamp(ctx, words[0], colour, words[1]);
  } else if (kind === "explorer") {
    ctx.beginPath();
    for (let i = 0; i < 6; i += 1) ctx.lineTo(Math.cos(i * Math.PI / 3 + Math.PI / 6) * 46, Math.sin(i * Math.PI / 3 + Math.PI / 6) * 46);
    ctx.closePath();
    ctx.fillStyle = mix(colour, "#06121c", .7); ctx.fill();
    ctx.strokeStyle = colour; ctx.lineWidth = 4; ctx.stroke();
    ctx.beginPath(); ctx.arc(0, -6, 16, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-6, -12); ctx.lineTo(8, -2); ctx.stroke();
    ctx.fillStyle = colour; ctx.textAlign = "center"; ctx.font = `700 11px ${FONTS.hud.family}`;
    ctx.fillText("EXPLORER", 0, 28); ctx.textAlign = "left";
  } else if (kind === "postage") {
    ctx.fillStyle = "#fbf6ea";
    ctx.beginPath();
    for (let i = 0; i <= 12; i += 1) ctx.arc(-40 + i * 6.66, -50, 3, 0, Math.PI, true);
    ctx.lineTo(40, 50);
    for (let i = 0; i <= 12; i += 1) ctx.arc(40 - i * 6.66, 50, 3, 0, Math.PI, false);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = colour; ctx.fillRect(-32, -42, 64, 62);
    ctx.fillStyle = "#ffd166"; ctx.beginPath(); ctx.arc(14, -24, 9, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#fbf6ea";
    ctx.beginPath(); ctx.moveTo(-24, 6); ctx.lineTo(4, -10); ctx.lineTo(22, 4); ctx.lineTo(2, 2); ctx.closePath(); ctx.fill();
    ctx.fillStyle = colour; ctx.textAlign = "center"; ctx.font = `700 9px ${FONTS.hud.family}`;
    ctx.fillText("VIA WITCH SPACE", 0, 34); ctx.font = `900 11px ${FONTS.display.family}`; ctx.fillText("5 CR", 0, 45); ctx.textAlign = "left";
  } else if (kind === "thargoid") {
    ctx.fillStyle = "#0b1512";
    ctx.strokeStyle = colour; ctx.lineWidth = 3;
    for (let i = 0; i < 8; i += 1) {
      ctx.save(); ctx.rotate(i * Math.PI / 4);
      ctx.beginPath(); ctx.ellipse(0, -30, 10, 18, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.restore();
    }
    ctx.beginPath(); ctx.arc(0, 0, 16, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.fillStyle = colour; ctx.shadowColor = colour; ctx.shadowBlur = 14;
    ctx.beginPath(); ctx.arc(0, 0, 7, 0, Math.PI * 2); ctx.fill();
  } else if (kind === "guardian") {
    ctx.strokeStyle = colour; ctx.lineWidth = 4; ctx.shadowColor = colour; ctx.shadowBlur = 10;
    ctx.beginPath(); ctx.moveTo(0, -44); ctx.lineTo(38, 22); ctx.lineTo(-38, 22); ctx.closePath(); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, -18); ctx.lineTo(16, 10); ctx.lineTo(-16, 10); ctx.closePath(); ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, 4, 0, Math.PI * 2); ctx.fillStyle = colour; ctx.fill();
    ctx.beginPath(); ctx.moveTo(0, 22); ctx.lineTo(0, 44); ctx.moveTo(-20, 34); ctx.lineTo(20, 34); ctx.stroke();
  } else if (kind === "planet") {
    const body = ctx.createRadialGradient(-12, -12, 4, 0, 0, 32);
    body.addColorStop(0, mix(colour, "#ffffff", .4)); body.addColorStop(1, mix(colour, "#000000", .6));
    ctx.strokeStyle = mix(colour, "#ffffff", .3); ctx.lineWidth = 3;
    ctx.beginPath(); ctx.ellipse(0, 0, 48, 13, -.35, Math.PI, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = body; ctx.beginPath(); ctx.arc(0, 0, 30, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(0, 0, 48, 13, -.35, 0, Math.PI); ctx.stroke();
  } else if (kind === "star") {
    star(ctx, 46); ctx.fillStyle = colour; ctx.shadowColor = colour; ctx.shadowBlur = 12; ctx.fill();
  } else if (kind === "heart") {
    ctx.beginPath();
    ctx.moveTo(0, 38);
    ctx.bezierCurveTo(-60, -6, -24, -56, 0, -22);
    ctx.bezierCurveTo(24, -56, 60, -6, 0, 38);
    ctx.fillStyle = colour; ctx.fill();
  } else if (kind === "o7") {
    ctx.fillStyle = "rgba(10, 16, 24, .85)";
    ctx.beginPath(); ctx.roundRect(-44, -30, 88, 52, 14); ctx.fill();
    ctx.beginPath(); ctx.moveTo(-18, 20); ctx.lineTo(-28, 40); ctx.lineTo(0, 22); ctx.fill();
    ctx.fillStyle = colour; ctx.textAlign = "center"; ctx.font = `900 34px ${FONTS.display.family}`; ctx.fillText("o7", 0, 10); ctx.textAlign = "left";
  } else if (kind === "wish") {
    ctx.fillStyle = mix(colour, "#000000", .3);
    ctx.beginPath(); ctx.moveTo(-50, -6); ctx.lineTo(-62, 6); ctx.lineTo(-50, 18); ctx.lineTo(-40, 6); ctx.fill();
    ctx.beginPath(); ctx.moveTo(50, -6); ctx.lineTo(62, 6); ctx.lineTo(50, 18); ctx.lineTo(40, 6); ctx.fill();
    ctx.fillStyle = colour; ctx.fillRect(-48, -12, 96, 26);
    ctx.fillStyle = "#ffffff"; ctx.textAlign = "center"; ctx.font = `700 9.5px ${FONTS.hud.family}`; ctx.fillText("WISH YOU WERE HERE", 0, 5); ctx.textAlign = "left";
  } else if (kind === "tape") {
    ctx.fillStyle = colour; ctx.globalAlpha *= .55;
    ctx.beginPath(); ctx.moveTo(-50, -14);
    for (let i = 0; i <= 6; i += 1) ctx.lineTo(-50 + (i % 2) * 3, -14 + i * 4.6);
    ctx.lineTo(50, 14);
    for (let i = 0; i <= 6; i += 1) ctx.lineTo(50 - (i % 2) * 3, 14 - i * 4.6);
    ctx.closePath(); ctx.fill();
  } else if (kind === "arrow") {
    ctx.strokeStyle = colour; ctx.lineWidth = 7;
    ctx.beginPath(); ctx.moveTo(-44, 26); ctx.quadraticCurveTo(-10, -30, 34, -14); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(18, -32); ctx.lineTo(38, -13); ctx.lineTo(14, 0); ctx.stroke();
  } else if (kind === "ring") {
    ctx.strokeStyle = colour; ctx.lineWidth = 5;
    ctx.beginPath(); ctx.ellipse(0, 0, 46, 30, -.1, .2, Math.PI * 2.1); ctx.stroke();
  } else if (kind === "sparkle") {
    ctx.fillStyle = colour; ctx.shadowColor = colour; ctx.shadowBlur = 16;
    star(ctx, 46, .18); ctx.fill();
  } else if (kind === "fuel") {
    stamp(ctx, "FUEL LOW", colour, "SCOOP THE NEXT STAR");
  }
  ctx.restore();
}

// ---- The whole card. ----
// Draws at card pixels (the caller scales); returns each layer's box.
export function drawCard(ctx, design, photo, {selection = null} = {}) {
  const P = BASES[design.base]?.photo || BASES.polaroid.photo;
  const boxes = [];
  ctx.save();
  drawPaper(ctx, design);
  ctx.save();
  cardShape(ctx, design);
  ctx.clip();
  drawPhoto(ctx, design, photo, P);
  drawFrame(ctx, design);
  for (const layer of design.layers) {
    if (layer.hidden) continue;
    const box = measure(ctx, design, layer);
    boxes.push({id: layer.id, ...box, rotate: layer.rotate || 0});
    ctx.save();
    ctx.globalAlpha = clamp(layer.opacity ?? 1, 0, 1);
    if (layer.rotate && layer.kind !== "postmark" && layer.kind !== "sticker") {
      ctx.translate(box.cx, box.cy);
      ctx.rotate(layer.rotate * Math.PI / 180);
      ctx.translate(-box.cx, -box.cy);
    }
    if (layer.kind === "text") drawText(ctx, design, layer, box);
    else if (layer.kind === "chips") drawChips(ctx, design, layer, box);
    else if (layer.kind === "rule") {
      ctx.strokeStyle = mix(colourOf(design, layer.colour), design.paper, .35);
      ctx.lineWidth = 2;
      ctx.setLineDash([12, 12]);
      ctx.beginPath(); ctx.moveTo(layer.x, layer.y); ctx.lineTo(layer.x + layer.width, layer.y); ctx.stroke();
      ctx.setLineDash([]);
    } else if (layer.kind === "postmark") drawPostmark(ctx, design, layer);
    else if (layer.kind === "sticker") drawSticker(ctx, design, layer);
    ctx.restore();
  }
  ctx.restore();
  ctx.restore();
  if (selection) boxes.selected = boxes.find((box) => box.id === selection) || null;
  return boxes;
}

function drawBackdrop(ctx, design, w, h) {
  const kind = design.backdrop?.kind || "none";
  if (kind === "none") return;
  if (kind === "colour") { ctx.fillStyle = design.backdrop.colour || "#1b2433"; ctx.fillRect(0, 0, w, h); return; }
  if (kind === "desk") {
    const wood = ctx.createLinearGradient(0, 0, w, h);
    wood.addColorStop(0, "#3a2416"); wood.addColorStop(.5, "#5a3820"); wood.addColorStop(1, "#2a180e");
    ctx.fillStyle = wood; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(0,0,0,.18)";
    for (let y = 0; y < h; y += 9) {
      ctx.lineWidth = 1 + (y * 7) % 3;
      ctx.beginPath(); ctx.moveTo(0, y);
      for (let x = 0; x <= w; x += 60) ctx.lineTo(x, y + Math.sin((x + y * 3) / 140) * 4);
      ctx.stroke();
    }
    return;
  }
  if (kind === "hangar") {
    ctx.fillStyle = "#1b1f24"; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(255,255,255,.06)"; ctx.lineWidth = 3;
    for (let x = 0; x < w; x += 120) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
    for (let y = 0; y < h; y += 120) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
    ctx.fillStyle = "rgba(255, 200, 40, .5)";
    for (let x = -h; x < w; x += 80) { ctx.beginPath(); ctx.moveTo(x, h - 50); ctx.lineTo(x + 40, h - 50); ctx.lineTo(x + 70, h); ctx.lineTo(x + 30, h); ctx.fill(); }
    return;
  }
  const space = ctx.createRadialGradient(w * .3, h * .3, 10, w * .5, h * .5, Math.max(w, h));
  space.addColorStop(0, "#1a1440"); space.addColorStop(1, "#02030a");
  ctx.fillStyle = space; ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = "#ffffff";
  for (let i = 0; i < 400; i += 1) { ctx.globalAlpha = .2 + (i % 10) / 14; ctx.fillRect((i * 733) % w, (i * 397) % h, i % 9 ? 1.5 : 3, i % 9 ? 1.5 : 3); }
  ctx.globalAlpha = 1;
}

// The finished picture: the card tilted, with a shadow, on what's behind it.
export function renderPicture(design, photo, scale = 1) {
  const angle = (design.angle || 0) * Math.PI / 180;
  const margin = 90;
  const w = Math.ceil((Math.abs(Math.cos(angle)) * CARD.w + Math.abs(Math.sin(angle)) * CARD.h + margin * 2) * scale);
  const h = Math.ceil((Math.abs(Math.sin(angle)) * CARD.w + Math.abs(Math.cos(angle)) * CARD.h + margin * 2) * scale);
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  drawBackdrop(ctx, design, w, h);
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  ctx.translate(w / scale / 2, h / scale / 2);
  ctx.rotate(angle);
  ctx.translate(-CARD.w / 2, -CARD.h / 2);
  ctx.save();
  ctx.shadowColor = "rgba(0,0,0,.55)";
  ctx.shadowBlur = 40;
  ctx.shadowOffsetY = 18;
  cardShape(ctx, design);
  ctx.fillStyle = design.paper;
  ctx.fill();
  ctx.restore();
  drawCard(ctx, design, photo);
  return canvas;
}
