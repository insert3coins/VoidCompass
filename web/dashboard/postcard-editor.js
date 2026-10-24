// The postcard editor (5.6.3): the card big in the middle, drawn live in the
// page, and everything on it yours to move. Drag the words, the postmark and
// the stickers; turn them and size them by their handles; pan and zoom the
// photo inside its frame. Undo and redo, duplicate, save over it or as a new
// card. What it shows is what's saved: the picture is this drawing.

import {BACKDROPS, BASES, CARD, FILTERS, FONTS, STICKERS, TOKENS, applyBase, colourOf, defaultDesign, drawCard, drawSticker, newId,
  renderPicture, stickerColour} from "./postcard-art.js";

const HISTORY = 80;
const ROLE_NAMES = {greeting: "Lettering", title: "Place name", place: "System & region", note: "Note", signed: "Signature",
  where: "Where", date: "Date", time: "Time", facts: "Journal facts", postmark: "Postmark", rule: "Dashed rule"};
const TEXT_PRESETS = [
  ["Heading", {font: "hud", size: 90, caps: true, skew: .16, colour: "accent", shadow: true, text: "Your words"}],
  ["Handwritten", {font: "hand", size: 50, colour: "ink", text: "Wish you were here", width: 900}],
  ["Caption", {font: "hud", size: 28, caps: true, spacing: .2, colour: "soft", text: "A caption"}],
  ["Neon sign", {font: "display", size: 72, caps: true, colour: "accent", glow: true, text: "NEON"}],
  ["Typewriter", {font: "mono", size: 30, colour: "ink", text: "LOG ENTRY 3312.10", spacing: .05}],
  ["Script", {font: "script", size: 64, colour: "accent", text: "Greetings", shadow: true}],
];
const SWATCHES = ["#ffffff", "#000000", "#ff7a18", "#ffd166", "#54e39a", "#00d1ff", "#7a5cff", "#ff5f8f", "#c8323c", "#2a4c9a", "#3b2a1a", "#e9dab6"];

let state = null;

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[char]));
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const copy = (value) => JSON.parse(JSON.stringify(value));

export function editorOpen() {
  return Boolean(state);
}

// open({ui, id, info, design, looks, themes, shots, photoUrl, onSaved, onClose})
export function openEditor(options) {
  closeEditor(true);
  const {info} = options;
  const base = options.design?.base || info.base || "polaroid";
  const design = options.design?.v === 2 ? copy(options.design) : defaultDesign(info, base, options.looks?.[base] || {});
  state = {...options, design, original: copy(design), past: [], future: [], selected: null, photo: null, view: {scale: 1, x: 0, y: 0},
    drag: null, dirty: false, tab: "look", preview: false, gesture: false};
  build();
  loadPhoto(options.photoUrl);
  resize();
  draw();
  inspect();
}

export function closeEditor(force = false) {
  if (!state) return true;
  if (!force && state.dirty && !window.confirm("Close the editor without saving your changes?")) return false;
  window.removeEventListener("resize", resize);
  document.removeEventListener("keydown", onKey, true);
  state.root?.remove();
  const done = state.onClose;
  state = null;
  done?.();
  return true;
}

function loadPhoto(url) {
  if (!url) { state.photo = null; draw(); return; }
  const image = new Image();
  image.onload = () => { if (state) { state.photo = image; draw(); } };
  image.onerror = () => { if (state) { state.photo = null; draw(); } };
  image.src = url;
}

// ---- History. ----
function remember() {
  state.past.push(JSON.stringify(state.design));
  if (state.past.length > HISTORY) state.past.shift();
  state.future = [];
  state.dirty = true;
  bar();
}

// Sliders and typing: one undo step per gesture, not per tick.
function begin() {
  if (state.gesture) return;
  state.gesture = true;
  remember();
}

function undo() {
  if (!state.past.length) return;
  state.future.push(JSON.stringify(state.design));
  state.design = JSON.parse(state.past.pop());
  state.dirty = true;
  if (state.selected && state.selected !== "photo" && !layer(state.selected)) state.selected = null;
  refresh();
}

function redo() {
  if (!state.future.length) return;
  state.past.push(JSON.stringify(state.design));
  state.design = JSON.parse(state.future.pop());
  state.dirty = true;
  refresh();
}

function refresh() {
  draw();
  inspect();
  layersList();
  bar();
}

const layer = (id) => state.design.layers.find((item) => item.id === id) || null;

// ---- The DOM. ----
function build() {
  const root = document.createElement("div");
  root.className = "pe";
  root.innerHTML = `
    <header class="pe-bar">
      <div class="pe-title"><small>EDITING POSTCARD</small><b>${esc(state.info.title || "Postcard")}</b></div>
      <div class="pe-tools">
        <button type="button" data-pe="undo" title="Undo (Ctrl+Z)">↶ UNDO</button>
        <button type="button" data-pe="redo" title="Redo (Ctrl+Y)">↷ REDO</button>
        <button type="button" data-pe="revert" title="Back to how it was when you opened it">REVERT</button>
        <button type="button" data-pe="fresh" title="The standard layout for this look, with your words">FRESH LAYOUT</button>
        <button type="button" data-pe="preview" title="See it tilted, as saved">PREVIEW</button>
      </div>
      <div class="pe-save">
        <span class="pe-dirty" id="pe-dirty"></span>
        <button type="button" data-pe="close">CLOSE</button>
        <button type="button" data-pe="save-new" title="Keep this one and save a copy">SAVE AS NEW</button>
        <button type="button" class="primary" data-pe="save" title="Save (Ctrl+S)">SAVE POSTCARD</button>
      </div>
    </header>
    <aside class="pe-left">
      <nav class="pe-tabs">${[["look", "LOOK"], ["add", "ADD"], ["layers", "LAYERS"]].map(([id, label]) =>
        `<button type="button" data-pe-tab="${id}">${label}</button>`).join("")}</nav>
      <div class="pe-tab" data-pe-panel="look" id="pe-look"></div>
      <div class="pe-tab" data-pe-panel="add" id="pe-add"></div>
      <div class="pe-tab" data-pe-panel="layers" id="pe-layers"></div>
    </aside>
    <main class="pe-stage" id="pe-stage"><canvas id="pe-canvas"></canvas>
      <p class="pe-hint">Drag anything · handles size and turn it · click the photo to pan and zoom it (wheel) · Delete removes · Ctrl+D duplicates · arrows nudge</p>
      <div class="pe-saving" id="pe-saving" hidden><b>SAVING</b><span>Drawing your postcard…</span></div></main>
    <aside class="pe-right" id="pe-inspector"></aside>`;
  document.body.append(root);
  state.root = root;
  state.canvas = root.querySelector("#pe-canvas");
  state.ctx = state.canvas.getContext("2d");
  root.addEventListener("click", onClick);
  root.addEventListener("input", onInput);
  root.addEventListener("change", onChange);
  state.canvas.addEventListener("pointerdown", onDown);
  state.canvas.addEventListener("pointermove", onMove);
  state.canvas.addEventListener("pointerup", onUp);
  state.canvas.addEventListener("pointercancel", onUp);
  state.canvas.addEventListener("dblclick", onDouble);
  state.canvas.addEventListener("wheel", onWheel, {passive: false});
  window.addEventListener("resize", resize);
  document.addEventListener("keydown", onKey, true);
  tab(state.tab);
  lookPanel();
  addPanel();
  layersList();
  bar();
}

function bar() {
  if (!state) return;
  const root = state.root;
  root.querySelector('[data-pe="undo"]').disabled = !state.past.length;
  root.querySelector('[data-pe="redo"]').disabled = !state.future.length;
  root.querySelector('[data-pe="preview"]').classList.toggle("active", state.preview);
  root.querySelector("#pe-dirty").textContent = state.dirty ? "UNSAVED CHANGES" : "";
}

function tab(id) {
  state.tab = id;
  for (const button of state.root.querySelectorAll("[data-pe-tab]")) button.classList.toggle("active", button.dataset.peTab === id);
  for (const panel of state.root.querySelectorAll("[data-pe-panel]")) panel.hidden = panel.dataset.pePanel !== id;
}

function resize() {
  if (!state) return;
  const stage = state.root.querySelector("#pe-stage");
  const box = stage.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  state.canvas.width = Math.max(1, Math.round(box.width * ratio));
  state.canvas.height = Math.max(1, Math.round(box.height * ratio));
  state.canvas.style.width = `${box.width}px`;
  state.canvas.style.height = `${box.height}px`;
  const scale = Math.min((box.width - 60) / CARD.w, (box.height - 70) / CARD.h);
  state.view = {scale: scale * ratio, x: (box.width - CARD.w * scale) / 2 * ratio, y: (box.height - CARD.h * scale) / 2 * ratio, ratio};
  draw();
}

// ---- Drawing the stage. ----
function draw() {
  if (!state) return;
  const {ctx, canvas, view, design} = state;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (state.preview) {
    const picture = renderPicture(design, state.photo, .5);
    const scale = Math.min(canvas.width / picture.width, canvas.height / picture.height) * .94;
    ctx.drawImage(picture, (canvas.width - picture.width * scale) / 2, (canvas.height - picture.height * scale) / 2, picture.width * scale, picture.height * scale);
    return;
  }
  ctx.setTransform(view.scale, 0, 0, view.scale, view.x, view.y);
  ctx.save();
  ctx.shadowColor = "rgba(0,0,0,.6)";
  ctx.shadowBlur = 40;
  ctx.shadowOffsetY = 16;
  ctx.fillStyle = design.paper;
  ctx.fillRect(0, 0, CARD.w, CARD.h);
  ctx.restore();
  state.boxes = drawCard(ctx, design, state.photo);
  // The selection: a box, a size handle and a turn handle.
  const k = 1 / view.scale * (view.ratio || 1);
  const guide = state.drag?.guide;
  if (guide) {
    ctx.strokeStyle = "#ff3fa4";
    ctx.lineWidth = 2 * k;
    ctx.setLineDash([10 * k, 8 * k]);
    if (guide.x !== undefined) { ctx.beginPath(); ctx.moveTo(guide.x, 0); ctx.lineTo(guide.x, CARD.h); ctx.stroke(); }
    if (guide.y !== undefined) { ctx.beginPath(); ctx.moveTo(0, guide.y); ctx.lineTo(CARD.w, guide.y); ctx.stroke(); }
    ctx.setLineDash([]);
  }
  if (state.selected === "photo") {
    const P = BASES[design.base].photo;
    ctx.strokeStyle = "#00d1ff";
    ctx.lineWidth = 3 * k;
    ctx.setLineDash([14 * k, 10 * k]);
    ctx.strokeRect(P.x, P.y, P.w, P.h);
    ctx.setLineDash([]);
  }
  const box = state.boxes.find((item) => item.id === state.selected);
  if (box) {
    ctx.save();
    ctx.translate(box.cx, box.cy);
    ctx.rotate(box.rotate * Math.PI / 180);
    const w = box.w + 20, h = box.h + 20;
    ctx.strokeStyle = "#00d1ff";
    ctx.lineWidth = 2.5 * k;
    ctx.setLineDash([10 * k, 7 * k]);
    ctx.strokeRect(-w / 2, -h / 2, w, h);
    ctx.setLineDash([]);
    ctx.fillStyle = "#00d1ff";
    ctx.fillRect(w / 2 - 9 * k, h / 2 - 9 * k, 18 * k, 18 * k);
    ctx.beginPath(); ctx.moveTo(0, -h / 2); ctx.lineTo(0, -h / 2 - 40 * k); ctx.stroke();
    ctx.beginPath(); ctx.arc(0, -h / 2 - 48 * k, 10 * k, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }
}

// ---- Pointer: select, drag, size, turn, pan. ----
function toCard(event) {
  const rect = state.canvas.getBoundingClientRect();
  const ratio = state.view.ratio || 1;
  return [((event.clientX - rect.left) * ratio - state.view.x) / state.view.scale, ((event.clientY - rect.top) * ratio - state.view.y) / state.view.scale];
}

function local(box, x, y) {
  const a = -box.rotate * Math.PI / 180, dx = x - box.cx, dy = y - box.cy;
  return [dx * Math.cos(a) - dy * Math.sin(a), dx * Math.sin(a) + dy * Math.cos(a)];
}

function hit(x, y) {
  const k = 1 / state.view.scale * (state.view.ratio || 1);
  const selected = state.boxes?.find((box) => box.id === state.selected);
  if (selected) {
    const [lx, ly] = local(selected, x, y);
    const w = selected.w + 20, h = selected.h + 20;
    if (Math.hypot(lx - w / 2, ly - h / 2) < 22 * k) return {id: selected.id, handle: "size"};
    if (Math.hypot(lx, ly + h / 2 + 48 * k) < 22 * k) return {id: selected.id, handle: "turn"};
  }
  for (const box of [...(state.boxes || [])].reverse()) {
    const [lx, ly] = local(box, x, y);
    if (Math.abs(lx) <= box.w / 2 + 12 && Math.abs(ly) <= box.h / 2 + 12) return {id: box.id};
  }
  const P = BASES[state.design.base].photo;
  if (x >= P.x && x <= P.x + P.w && y >= P.y && y <= P.y + P.h) return {id: "photo"};
  return {id: null};
}

function onDown(event) {
  if (state.preview) { state.preview = false; bar(); draw(); return; }
  const [x, y] = toCard(event);
  const found = hit(x, y);
  if (found.id !== state.selected) { state.selected = found.id; inspect(); layersList(); }
  state.canvas.setPointerCapture(event.pointerId);
  const target = found.id && found.id !== "photo" ? layer(found.id) : null;
  const box = state.boxes.find((item) => item.id === found.id);
  state.drag = {x, y, handle: found.handle || "move", id: found.id, start: target ? copy(target) : copy(state.design.photo || {}), box, moved: false};
  draw();
}

function onMove(event) {
  const drag = state?.drag;
  if (!drag) {
    if (state && !state.preview) {
      const [x, y] = toCard(event);
      const found = hit(x, y);
      state.canvas.style.cursor = found.handle === "size" ? "nwse-resize" : found.handle === "turn" ? "grab" : found.id === "photo" ? "move" : found.id ? "move" : "default";
    }
    return;
  }
  const [x, y] = toCard(event);
  const dx = x - drag.x, dy = y - drag.y;
  if (!drag.moved && Math.hypot(dx, dy) < 3) return;
  if (!drag.moved) { remember(); drag.moved = true; }
  if (drag.id === "photo") {
    const P = BASES[state.design.base].photo;
    const zoom = state.design.photo.zoom || 1;
    const excessX = Math.max(1, P.w * (zoom - 1) + 1), excessY = Math.max(1, P.h * (zoom - 1) + 1);
    state.design.photo.x = clamp((drag.start.x || 0) - dx / excessX * 2, -1, 1);
    state.design.photo.y = clamp((drag.start.y || 0) - dy / excessY * 2, -1, 1);
  } else if (drag.id) {
    const item = layer(drag.id);
    if (drag.handle === "size") {
      const [sx, sy] = local(drag.box, drag.x, drag.y);
      const [nx, ny] = local(drag.box, x, y);
      const ratio = Math.max(.1, Math.hypot(nx, ny) / Math.max(1, Math.hypot(sx, sy)));
      item.size = clamp(drag.start.size * ratio, 8, 600);
      if (item.width) item.width = clamp(drag.start.width * ratio, 80, CARD.w * 1.5);
    } else if (drag.handle === "turn") {
      let angle = Math.atan2(y - drag.box.cy, x - drag.box.cx) * 180 / Math.PI + 90;
      if (event.shiftKey) angle = Math.round(angle / 15) * 15;
      else if (Math.abs(angle) < 3) angle = 0;
      item.rotate = Math.round(angle * 10) / 10;
    } else {
      let nx = drag.start.x + dx, ny = drag.start.y + dy;
      // Snap the middle of it to the middle of the card.
      const centre = drag.box.cx + dx;
      drag.guide = null;
      if (!event.altKey && Math.abs(centre - CARD.w / 2) < 10) { nx += CARD.w / 2 - centre; drag.guide = {x: CARD.w / 2}; }
      item.x = Math.round(nx);
      item.y = Math.round(ny);
    }
  }
  draw();
  if (drag.handle !== "move") inspect(true);
}

function onUp() {
  if (!state?.drag) return;
  const moved = state.drag.moved;
  state.drag = null;
  draw();
  if (moved) inspect(true);
}

function onDouble(event) {
  const [x, y] = toCard(event);
  const found = hit(x, y);
  const item = found.id && found.id !== "photo" ? layer(found.id) : null;
  if (item?.kind === "text") {
    const field = state.root.querySelector('#pe-inspector [data-field="text"]');
    field?.focus();
    field?.select();
  }
}

function onWheel(event) {
  if (state.preview) return;
  event.preventDefault();
  const step = event.deltaY < 0 ? 1.06 : 1 / 1.06;
  begin();
  if (state.selected && state.selected !== "photo") {
    const item = layer(state.selected);
    item.size = clamp(item.size * step, 8, 600);
    if (item.width) item.width = clamp(item.width * step, 80, CARD.w * 1.5);
  } else {
    state.design.photo.zoom = clamp((state.design.photo.zoom || 1) * step, 1, 5);
  }
  state.gesture = false;
  draw();
  inspect(true);
}

function onKey(event) {
  if (!state) return;
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "");
  const mod = event.ctrlKey || event.metaKey;
  if (mod && event.key.toLowerCase() === "z" && !typing) { event.preventDefault(); event.shiftKey ? redo() : undo(); return; }
  if (mod && event.key.toLowerCase() === "y" && !typing) { event.preventDefault(); redo(); return; }
  if (mod && event.key.toLowerCase() === "s") { event.preventDefault(); save(false); return; }
  if (mod && event.key.toLowerCase() === "d" && !typing) { event.preventDefault(); duplicate(); return; }
  if (event.key === "Escape") {
    event.preventDefault();
    event.stopPropagation();
    if (typing) document.activeElement.blur();
    else if (state.preview) { state.preview = false; bar(); draw(); }
    else if (state.selected) { state.selected = null; refresh(); }
    else closeEditor();
    return;
  }
  if (typing) return;
  if ((event.key === "Delete" || event.key === "Backspace") && state.selected && state.selected !== "photo") { event.preventDefault(); removeSelected(); return; }
  const nudge = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]}[event.key];
  if (nudge && state.selected && state.selected !== "photo") {
    event.preventDefault();
    const item = layer(state.selected);
    const by = event.shiftKey ? 10 : 1;
    remember();
    item.x += nudge[0] * by;
    item.y += nudge[1] * by;
    draw();
  }
}

// ---- Layer actions. ----
function duplicate() {
  const item = state.selected && state.selected !== "photo" ? layer(state.selected) : null;
  if (!item) return;
  remember();
  const twin = {...copy(item), id: newId(item.kind), role: item.role === "postmark" ? "postmark" : undefined, x: item.x + 30, y: item.y + 30};
  state.design.layers.splice(state.design.layers.indexOf(item) + 1, 0, twin);
  state.selected = twin.id;
  refresh();
}

function removeSelected() {
  const item = layer(state.selected);
  if (!item) return;
  remember();
  state.design.layers = state.design.layers.filter((entry) => entry !== item);
  state.selected = null;
  refresh();
}

function reorder(step) {
  const item = layer(state.selected);
  if (!item) return;
  const list = state.design.layers, index = list.indexOf(item), to = clamp(index + step, 0, list.length - 1);
  if (to === index) return;
  remember();
  list.splice(index, 1);
  list.splice(to, 0, item);
  refresh();
}

function addLayer(made) {
  remember();
  state.added = (state.added || 0) + 1;
  const step = ((state.added - 1) % 6) * 46;
  const item = {id: newId(made.kind), rotate: 0, opacity: 1, hidden: false, ...made, x: made.x + step, y: made.y + step * .6};
  state.design.layers.push(item);
  state.selected = item.id;
  refresh();
}

function addText(preset) {
  addLayer({kind: "text", x: CARD.w / 2 - 200, y: CARD.h / 2, ...copy(preset)});
}

// What the journal knew of the moment, to drop on the card as words.
function journalWords() {
  const info = state.info || {};
  return [["Place", info.title], ["System", info.system !== info.title ? info.system : ""], ["Region", info.region], ["Date", info.date],
    ["Time", info.time], ["Where", info.coordinates], ["Doing", info.doing], ...(info.facts || []).map((fact) => ["Fact", fact])]
    .filter(([, words]) => words);
}

function addSticker(kind) {
  addLayer({kind: "sticker", sticker: kind, x: CARD.w / 2, y: CARD.h / 2 - 100, size: 220, rotate: -6});
}

function addPostmark() {
  const info = state.info;
  addLayer({kind: "postmark", role: "postmark", x: 1240, y: 960, size: 118, rotate: -14, colour: "accent",
    top: String(info.system || info.title || "").toUpperCase().slice(0, 26), middle: info.time || "", bottom: String(info.date || "").toUpperCase()});
}

// ---- Panels. ----
function lookPanel() {
  const d = state.design;
  const looks = state.looks || {};
  const bases = Object.entries(BASES).map(([id, spec]) => {
    const colours = looks[id] || {};
    return `<button type="button" class="pe-base${d.base === id ? " active" : ""}" data-pe-base="${id}">
      <i style="background:${esc(colours.paper || "#eee")}"><i style="background:${esc(colours.greet || "#f70")}"></i></i><span>${spec.name}</span></button>`;
  }).join("");
  const themes = Object.entries(state.themes || {}).map(([name, theme]) =>
    `<button type="button" class="pe-theme" data-pe-theme="${esc(name)}"><i style="background:${esc(theme.paper || "#eee")}"><i style="background:${esc(theme.greet || "#f70")}"></i></i><span>★ ${esc(name)}</span></button>`).join("");
  const colour = (key, label) => `<label class="pe-colour"><span>${label}</span><input type="color" data-design="${key}" value="${esc(d[key])}"></label>`;
  const filters = Object.entries(FILTERS).map(([id, spec]) => `<option value="${id}"${d.filter === id ? " selected" : ""}>${spec.name}</option>`).join("");
  state.root.querySelector("#pe-look").innerHTML = `
    <section><h5>THE LOOK</h5><div class="pe-bases">${bases}</div>${themes ? `<h6>YOUR THEMES</h6><div class="pe-bases">${themes}</div>` : ""}</section>
    <section><h5>COLOURS</h5><div class="pe-colours">${colour("paper", "Paper")}${colour("ink", "Ink")}${colour("soft", "Soft ink")}${colour("accent", "Lettering")}</div></section>
    <section><h5>THE CARD</h5>
      ${range("design.angle", "Tilt", d.angle, -15, 15, .5, "°")}
      <label class="pe-field"><span>Behind the card</span><select data-design="backdrop.kind">${Object.entries(BACKDROPS).map(([id, name]) =>
        `<option value="${id}"${d.backdrop.kind === id ? " selected" : ""}>${name}</option>`).join("")}</select></label>
      ${d.backdrop.kind === "colour" ? `<label class="pe-colour"><span>Backdrop</span><input type="color" data-design="backdrop.colour" value="${esc(d.backdrop.colour || "#1b2433")}"></label>` : ""}
      ${toggle("design.texture", "Paper grain", d.texture !== false)}${toggle("design.shade", "Shade under the lettering", d.shade !== false)}</section>
    <section><h5>THE PHOTO</h5>
      <label class="pe-field"><span>Filter</span><select data-design="filter">${filters}</select></label>
      ${range("design.adjust.bright", "Brightness", d.adjust.bright, 40, 160, 1, "%")}${range("design.adjust.contrast", "Contrast", d.adjust.contrast, 40, 170, 1, "%")}
      ${range("design.adjust.sat", "Colour", d.adjust.sat, 0, 220, 1, "%")}${range("design.photo.zoom", "Zoom", Math.round((d.photo.zoom || 1) * 100), 100, 500, 1, "%")}
      <div class="pe-row"><button type="button" data-pe="photo-centre">CENTRE THE PHOTO</button><button type="button" data-pe="photo-pick">CHANGE THE PICTURE</button></div>
      <div class="pe-shots" id="pe-shots" hidden></div></section>`;
}

function range(key, label, value, min, max, step, unit = "") {
  return `<label class="pe-range"><span>${label}<em data-out="${key}">${Math.round(Number(value) * 10) / 10}${unit}</em></span>
    <input type="range" data-range="${key}" data-unit="${unit}" min="${min}" max="${max}" step="${step}" value="${value}"></label>`;
}

function toggle(key, label, on) {
  return `<label class="pe-toggle"><input type="checkbox" data-toggle="${key}"${on ? " checked" : ""}><i></i><span>${label}</span></label>`;
}

function addPanel() {
  const stickers = Object.entries(STICKERS).map(([id, name]) =>
    `<button type="button" class="pe-sticker" data-pe-sticker="${id}" title="${esc(name)}"><canvas width="120" height="120" data-sticker-canvas="${id}"></canvas><span>${esc(name)}</span></button>`).join("");
  state.root.querySelector("#pe-add").innerHTML = `
    <section><h5>WORDS</h5><div class="pe-presets">${TEXT_PRESETS.map(([name], index) =>
      `<button type="button" data-pe-text="${index}"><b class="pe-preset-${index}">${esc(name)}</b></button>`).join("")}</div></section>
    ${journalWords().length ? `<section><h5>FROM YOUR JOURNAL</h5><div class="pe-journal">${journalWords().map(([label, words], index) =>
      `<button type="button" data-pe-journal="${index}" title="${esc(words)}"><small>${esc(label)}</small><b>${esc(words)}</b></button>`).join("")}</div></section>` : ""}
    <section><h5>STAMPS & STICKERS</h5><div class="pe-sticker-grid">${stickers}</div>
      <div class="pe-row"><button type="button" data-pe="add-postmark">ADD A POSTMARK</button></div></section>`;
  // Each sticker drawn small for its button.
  for (const canvas of state.root.querySelectorAll("[data-sticker-canvas]")) {
    drawSticker(canvas.getContext("2d"), state.design, {sticker: canvas.dataset.stickerCanvas, x: 60, y: 60, size: 100, rotate: 0});
  }
}

function layersList() {
  if (!state) return;
  const items = [...state.design.layers].reverse().map((item) => {
    const name = item.kind === "sticker" ? STICKERS[item.sticker] || "Sticker" : ROLE_NAMES[item.role] || (item.kind === "text" ? `“${String(item.text).slice(0, 22)}”` : item.kind);
    return `<li class="${item.id === state.selected ? "active" : ""}${item.hidden ? " hidden-layer" : ""}">
      <button type="button" class="pe-eye" data-pe-eye="${esc(item.id)}" title="${item.hidden ? "Show" : "Hide"}">${item.hidden ? "○" : "●"}</button>
      <button type="button" class="pe-layer" data-pe-select="${esc(item.id)}"><small>${esc(item.kind.toUpperCase())}</small><b>${esc(name)}</b></button></li>`;
  }).join("");
  state.root.querySelector("#pe-layers").innerHTML = `<section><h5>ON THE CARD · TOP FIRST</h5><ol class="pe-layer-list">${items}
    <li class="${state.selected === "photo" ? "active" : ""}"><span class="pe-eye">▣</span><button type="button" class="pe-layer" data-pe-select="photo"><small>PHOTO</small><b>The picture</b></button></li></ol></section>`;
}

function colourRow(item, key = "colour", label = "Colour") {
  const value = item[key] || "";
  const tokens = TOKENS.map((token) => `<button type="button" class="pe-swatch${value === token ? " active" : ""}" data-set="${key}" data-value="${token}"
    style="background:${esc(colourOf(state.design, token))}" title="${token === "accent" ? "Lettering" : token}"></button>`).join("");
  const swatches = SWATCHES.map((hex) => `<button type="button" class="pe-swatch${value === hex ? " active" : ""}" data-set="${key}" data-value="${hex}" style="background:${hex}"></button>`).join("");
  const current = colourOf(state.design, value || (item.kind === "sticker" ? stickerColour(item.sticker) : "ink"));
  return `<div class="pe-field"><span>${label}</span><div class="pe-swatches">${tokens}<i></i>${swatches}<input type="color" data-colour="${key}" value="${esc(/^#[0-9a-f]{6}$/i.test(current) ? current : "#ffffff")}"></div></div>`;
}

// The inspector: whatever's selected, or the card when nothing is.
function inspect(valuesOnly = false) {
  if (!state) return;
  const panel = state.root.querySelector("#pe-inspector");
  if (valuesOnly) {
    for (const input of panel.querySelectorAll("[data-range]")) {
      const value = readKey(input.dataset.range);
      if (value === undefined || document.activeElement === input) continue;
      input.value = input.dataset.range === "design.photo.zoom" ? Math.round(value * 100) : value;
      const out = panel.querySelector(`[data-out="${input.dataset.range}"]`) || state.root.querySelector(`[data-out="${input.dataset.range}"]`);
      if (out) out.textContent = `${Math.round(Number(input.value) * 10) / 10}${input.dataset.unit || ""}`;
    }
    return;
  }
  const item = state.selected && state.selected !== "photo" ? layer(state.selected) : null;
  if (state.selected === "photo") {
    panel.innerHTML = `<h4>THE PHOTO</h4><p class="pe-note">Drag on it to move it in its frame; the wheel zooms.</p>
      ${range("design.photo.zoom", "Zoom", Math.round((state.design.photo.zoom || 1) * 100), 100, 500, 1, "%")}
      <div class="pe-row"><button type="button" data-pe="photo-centre">CENTRE</button><button type="button" data-pe="photo-pick">CHANGE THE PICTURE</button></div>
      <p class="pe-note">Filters and colour are on the LOOK tab.</p>`;
    return;
  }
  if (!item) {
    panel.innerHTML = `<h4>THE CARD</h4><p class="pe-note">Click anything on the card to change it, or add words and stickers from the ADD tab.</p>
      <dl class="pe-facts">${[["Place", state.info.title], ["System", state.info.system], ["Region", state.info.region], ["Taken", [state.info.date, state.info.time].filter(Boolean).join(" · ")]]
        .filter(([, value]) => value).map(([label, value]) => `<dt>${label}</dt><dd>${esc(value)}</dd>`).join("")}</dl>`;
    return;
  }
  const common = `${range("layer.rotate", "Turn", item.rotate || 0, -180, 180, .5, "°")}${range("layer.opacity", "Opacity", Math.round((item.opacity ?? 1) * 100), 10, 100, 1, "%")}
    <div class="pe-row pe-actions"><button type="button" data-pe="forward">FORWARD</button><button type="button" data-pe="back">BACK</button>
      <button type="button" data-pe="duplicate">DUPLICATE</button><button type="button" class="danger-action" data-pe="remove">REMOVE</button></div>`;
  let body = "";
  if (item.kind === "text") {
    const fonts = Object.entries(FONTS).map(([id, spec]) => `<option value="${id}"${item.font === id ? " selected" : ""}>${spec.name}</option>`).join("");
    body = `<label class="pe-field"><span>Words</span><textarea data-field="text" rows="${item.width ? 4 : 2}" maxlength="400">${esc(item.text)}</textarea></label>
      <label class="pe-field"><span>Font</span><select data-field="font">${fonts}</select></label>
      ${range("layer.size", "Size", Math.round(item.size), 10, 260, 1, "px")}
      <div class="pe-field"><span>Align</span><div class="pe-seg">${["left", "center", "right"].map((align) =>
        `<button type="button" class="${(item.align || "left") === align ? "active" : ""}" data-set="align" data-value="${align}">${align.toUpperCase()}</button>`).join("")}</div></div>
      <div class="pe-toggles">${toggle("layer.caps", "Capitals", item.caps)}${toggle("layer.shadow", "Shadow", item.shadow)}${toggle("layer.glow", "Glow", item.glow)}${toggle("layer.italic", "Italic", item.italic)}</div>
      ${range("layer.spacing", "Letter spacing", Math.round((item.spacing || 0) * 100), -5, 60, 1, "")}
      ${range("layer.skew", "Lean", Math.round((item.skew || 0) * 100), -40, 40, 1, "")}
      ${range("layer.width", "Wrap at", Math.round(item.width || 0), 0, 1500, 10, "px")}
      ${colourRow(item)}${colourRow(item, "outline", "Outline")}`;
  } else if (item.kind === "sticker") {
    body = `<div class="pe-field"><span>Sticker</span><select data-field="sticker">${Object.entries(STICKERS).map(([id, name]) =>
      `<option value="${id}"${item.sticker === id ? " selected" : ""}>${esc(name)}</option>`).join("")}</select></div>
      ${range("layer.size", "Size", Math.round(item.size), 30, 700, 1, "px")}${colourRow(item)}
      <div class="pe-row"><button type="button" data-set="colour" data-value="">ITS OWN COLOUR</button></div>`;
  } else if (item.kind === "postmark") {
    body = `<label class="pe-field"><span>Round the top</span><input data-field="top" maxlength="30" value="${esc(item.top)}"></label>
      <label class="pe-field"><span>In the middle</span><input data-field="middle" maxlength="10" value="${esc(item.middle)}"></label>
      <label class="pe-field"><span>Round the bottom</span><input data-field="bottom" maxlength="30" value="${esc(item.bottom)}"></label>
      ${range("layer.size", "Size", Math.round(item.size), 40, 260, 1, "px")}${colourRow(item)}`;
  } else if (item.kind === "chips") {
    body = `<label class="pe-field"><span>Facts (one per line)</span><textarea data-field="items" rows="4">${esc(item.items.join("\n"))}</textarea></label>
      ${range("layer.size", "Size", Math.round(item.size), 12, 60, 1, "px")}${colourRow(item)}`;
  } else if (item.kind === "rule") {
    body = `${range("layer.width", "Length", Math.round(item.width), 40, 1500, 10, "px")}${colourRow(item)}`;
  }
  const name = item.kind === "sticker" ? STICKERS[item.sticker] : ROLE_NAMES[item.role] || (item.kind === "text" ? "Words" : item.kind);
  panel.innerHTML = `<h4>${esc(String(name || "").toUpperCase())}</h4>${body}${common}`;
}

function readKey(key) {
  const [scope, ...path] = key.split(".");
  let target = scope === "layer" ? layer(state.selected) : state.design;
  if (!target) return undefined;
  for (const part of path.slice(0, -1)) target = target?.[part];
  const value = target?.[path.at(-1)];
  if (key === "layer.opacity") return Math.round((value ?? 1) * 100);
  if (key === "layer.spacing" || key === "layer.skew") return Math.round((value || 0) * 100);
  return value;
}

function writeKey(key, raw) {
  const [scope, ...path] = key.split(".");
  let target = scope === "layer" ? layer(state.selected) : state.design;
  if (!target) return;
  for (const part of path.slice(0, -1)) target = target[part] = target[part] || {};
  let value = raw;
  if (key === "layer.opacity") value = raw / 100;
  else if (key === "layer.spacing" || key === "layer.skew") value = raw / 100;
  else if (key === "design.photo.zoom") value = raw / 100;
  else if (key === "layer.width" && raw === 0) value = 0;
  target[path.at(-1)] = value;
}

// ---- Events. ----
function onClick(event) {
  const button = event.target.closest("button");
  if (!button || !state) return;
  if (button.dataset.peTab) return tab(button.dataset.peTab);
  if (button.dataset.peSelect) { state.selected = button.dataset.peSelect; return refresh(); }
  if (button.dataset.peEye) {
    const item = layer(button.dataset.peEye);
    remember();
    item.hidden = !item.hidden;
    return refresh();
  }
  if (button.dataset.peBase) {
    remember();
    state.design = applyBase(state.design, button.dataset.peBase, state.looks?.[button.dataset.peBase] || {});
    lookPanel();
    return refresh();
  }
  if (button.dataset.peTheme) {
    const theme = state.themes?.[button.dataset.peTheme] || {};
    remember();
    const base = BASES[theme.base] ? theme.base : state.design.base;
    state.design = applyBase(state.design, base, {...state.looks?.[base], ...Object.fromEntries(Object.entries({paper: theme.paper, ink: theme.ink, greet: theme.greet}).filter(([, v]) => v))});
    if (theme.filter && FILTERS[theme.filter]) state.design.filter = theme.filter;
    if (theme.angle !== undefined && theme.angle !== null && theme.angle !== "") state.design.angle = Number(theme.angle);
    if (theme.font && FONTS[theme.font]) for (const item of state.design.layers) if (item.role === "title") item.font = theme.font;
    if (theme.background === "colour") state.design.backdrop = {kind: "colour", colour: theme.bg_colour || "#1b2433"};
    lookPanel();
    return refresh();
  }
  if (button.dataset.peText !== undefined) return addText(TEXT_PRESETS[Number(button.dataset.peText)][1]);
  if (button.dataset.peSticker) return addSticker(button.dataset.peSticker);
  if (button.dataset.peJournal !== undefined) {
    const [, words] = journalWords()[Number(button.dataset.peJournal)] || [];
    if (words) addText({font: "hud", size: 32, caps: true, spacing: .18, colour: "soft", text: String(words)});
    return undefined;
  }
  if (button.dataset.peShot) return pickShot(button.dataset.peShot);
  if (button.dataset.set !== undefined && state.selected && state.selected !== "photo") {
    remember();
    const item = layer(state.selected);
    if (button.dataset.value === "") delete item[button.dataset.set];
    else item[button.dataset.set] = button.dataset.value;
    draw();
    return inspect();
  }
  const action = button.dataset.pe;
  if (!action) return;
  if (action === "undo") return undo();
  if (action === "redo") return redo();
  if (action === "revert") { remember(); state.design = copy(state.original); lookPanel(); return refresh(); }
  if (action === "fresh") {
    remember();
    const fresh = defaultDesign(state.info, state.design.base, state.looks?.[state.design.base] || {});
    state.design = {...fresh, paper: state.design.paper, ink: state.design.ink, soft: state.design.soft, accent: state.design.accent,
      filter: state.design.filter, adjust: state.design.adjust, photo: state.design.photo, backdrop: state.design.backdrop, angle: state.design.angle};
    state.selected = null;
    return refresh();
  }
  if (action === "preview") { state.preview = !state.preview; state.selected = state.preview ? null : state.selected; bar(); return draw(); }
  if (action === "close") return closeEditor();
  if (action === "save") return save(false);
  if (action === "save-new") return save(true);
  if (action === "duplicate") return duplicate();
  if (action === "remove") return removeSelected();
  if (action === "forward") return reorder(1);
  if (action === "back") return reorder(-1);
  if (action === "add-postmark") return addPostmark();
  if (action === "photo-centre") { remember(); state.design.photo = {zoom: 1, x: 0, y: 0}; draw(); return inspect(true); }
  if (action === "photo-pick") return showShots();
}

function onInput(event) {
  if (!state) return;
  const target = event.target;
  if (target.dataset.range) {
    begin();
    writeKey(target.dataset.range, Number(target.value));
    const out = state.root.querySelector(`[data-out="${target.dataset.range}"]`);
    if (out) out.textContent = `${Math.round(Number(target.value) * 10) / 10}${target.dataset.unit || ""}`;
    return draw();
  }
  if (target.dataset.field) {
    begin();
    const item = layer(state.selected);
    if (!item) return;
    const field = target.dataset.field;
    item[field] = field === "items" ? target.value.split("\n").map((line) => line.trim()).filter(Boolean) : target.value;
    if (field === "font" || field === "sticker") state.gesture = false;
    draw();
    if (field !== "text" && field !== "items") layersList();
    return;
  }
  if (target.dataset.design) {
    begin();
    writeKey(`design.${target.dataset.design}`, target.value);
    return draw();
  }
  if (target.dataset.colour && state.selected) {
    begin();
    layer(state.selected)[target.dataset.colour] = target.value;
    return draw();
  }
}

function onChange(event) {
  if (!state) return;
  const target = event.target;
  state.gesture = false;
  if (target.dataset.toggle) {
    remember();
    writeKey(target.dataset.toggle, target.checked);
    return draw();
  }
  if (target.dataset.design === "backdrop.kind") lookPanel();
  if (target.dataset.field === "text" || target.dataset.field === "items") layersList();
  bar();
}

// ---- The picture: another screenshot, or a file. ----
function showShots() {
  tab("look");
  const box = state.root.querySelector("#pe-shots");
  if (!box) return;
  const shots = state.shots || [];
  box.hidden = !box.hidden;
  box.innerHTML = `${shots.length ? shots.map((shot) => `<button type="button" data-pe-shot="${esc(shot.id)}" title="${esc(shot.title)}">
      <img src="${esc(state.ui.apiUrl(`/media/shot-thumb/${shot.id}.jpg`))}" alt="" loading="lazy"></button>`).join("") : "<p>No screenshots found.</p>"}
    <button type="button" class="pe-file" data-pe-shot="file">FROM A FILE…</button>`;
}

async function pickShot(shot) {
  let done = false;
  if (shot === "file") {
    const api = window.pywebview?.api;
    if (typeof api?.choose_picture_file !== "function") return state.ui.showToast("Choosing a file works in the Void Compass window.");
    const chosen = await api.choose_picture_file();
    if (!chosen) return undefined;
    done = await state.ui.command("workspace", {page: "postcards", operation: "edit_photo", id: state.id, path: String(chosen)});
  } else {
    done = await state.ui.command("workspace", {page: "postcards", operation: "edit_photo", id: state.id, shot});
  }
  if (!done) return state.ui.showToast("That picture couldn't be used");
  remember();
  state.design.photo = {zoom: 1, x: 0, y: 0};
  loadPhoto(`${state.photoUrl.split("&v=")[0]}&v=${Date.now()}`);
  state.root.querySelector("#pe-shots").hidden = true;
  return state.ui.showToast("New picture in: save to keep it");
}

// ---- Saving: the drawing itself, as the PNG. ----
async function save(asNew) {
  if (!state || state.saving) return;
  state.saving = true;
  const busy = state.root.querySelector("#pe-saving");
  busy.hidden = false;
  try {
    const picture = renderPicture(state.design, state.photo, 1);
    const blob = await new Promise((resolve) => picture.toBlob(resolve, "image/png"));
    const png = await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
      reader.readAsDataURL(blob);
    });
    const response = await fetch(state.ui.apiUrl("/api/postcard-save"), {
      method: "POST", cache: "no-store", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({id: state.id, mode: asNew ? "new" : "replace", design: state.design, png}),
    });
    const reply = await response.json().catch(() => ({}));
    if (!response.ok || !reply.ok) throw new Error(reply.error || `HTTP ${response.status}`);
    state.dirty = false;
    state.original = copy(state.design);
    state.ui.showToast(asNew ? "Saved as a new postcard" : "Postcard saved");
    const saved = state.onSaved;
    if (asNew) state.id = reply.id;
    bar();
    saved?.(reply.id, asNew);
  } catch (error) {
    state?.ui.showToast(`The postcard wasn't saved: ${error.message}`);
  } finally {
    if (state) {
      state.saving = false;
      busy.hidden = true;
    }
  }
}

// For tests.
window.voidcompassPostcardEditor = {
  state: () => (state ? {id: state.id, selected: state.selected, layers: state.design.layers.length, base: state.design.base, dirty: state.dirty,
    undo: state.past.length, redo: state.future.length, photo: Boolean(state.photo), design: copy(state.design)} : null),
  select: (id) => { if (state) { state.selected = id; refresh(); } },
  // Where a layer's middle is on screen, in page pixels.
  at: (id) => {
    const box = state?.boxes?.find((item) => item.id === id);
    if (!box) return null;
    const rect = state.canvas.getBoundingClientRect(), ratio = state.view.ratio || 1;
    return [rect.left + (box.cx * state.view.scale + state.view.x) / ratio, rect.top + (box.cy * state.view.scale + state.view.y) / ratio];
  },
};
