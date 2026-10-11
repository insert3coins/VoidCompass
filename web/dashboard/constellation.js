// Your constellation (5.5.3.7): each session, the place you stayed longest
// becomes a star; nine stars make a constellation, named by the Watcher. One
// drawing for the page, the sky's thumbnails and the saved picture.

let selected = -1;      // which constellation is shown (-1: the latest)
let labels = true;
let lastKey = "";
let lastSettingsKey = "";
let sky = [];
let settings = {};

const LINE_COLOURS = {white: "#e8f0ff", gold: "#ffd27a"};

const STAR_COLOURS = {
  O: "#9bb0ff", B: "#aabfff", A: "#cad7ff", F: "#f8f7ff", G: "#fff1dc", K: "#ffd2a1", M: "#ff9f73",
  L: "#d07a5c", T: "#b8654f", Y: "#9c5646", N: "#d8f0ff", H: "#b28cff",
};

function starColour(star) {
  const kind = String(star || "").toUpperCase();
  if (kind.startsWith("D")) return "#eef6ff";
  if (kind.startsWith("W")) return "#c4d4ff";
  if (kind.includes("SUPERMASSIVE") || kind === "H") return STAR_COLOURS.H;
  return STAR_COLOURS[kind.charAt(0)] || "#e8eef5";
}

function token(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

// The same sky every time for the same constellation.
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

// Draw one constellation into a 2D context of width x height (CSS pixels).
function draw(context, item, width, height, {names = true, small = false, title = false, legend = true} = {}) {
  const bg = token("--bg", "#070b10"), text = token("--text", "#dce8ef");
  const accent = LINE_COLOURS[settings.constellation_lines] || token("--accent", "#00d1ff");
  // A bigger picture: the same drawing, scaled.
  const unit = title ? width / 1600 : 1;
  const drawn = [];
  context.save();
  // The night: the theme's ground, deepened, with a soft band of the galaxy.
  const ground = context.createRadialGradient(width * .5, height * .45, 0, width * .5, height * .45, Math.max(width, height) * .75);
  ground.addColorStop(0, `color-mix(in srgb, ${bg} 70%, #10203a)`);
  ground.addColorStop(1, bg);
  context.fillStyle = bg;
  context.fillRect(0, 0, width, height);
  try { context.fillStyle = ground; context.fillRect(0, 0, width, height); } catch (_error) { /* older engines */ }
  const rng = random(seedOf(item.name));
  context.save();
  context.translate(width / 2, height / 2);
  context.rotate(-.5 + rng() * .4);
  const band = context.createLinearGradient(0, -height * .35, 0, height * .35);
  band.addColorStop(0, "rgba(140, 170, 255, 0)");
  band.addColorStop(.5, "rgba(140, 170, 255, .07)");
  band.addColorStop(1, "rgba(140, 170, 255, 0)");
  context.fillStyle = band;
  context.fillRect(-width, -height * .35, width * 2, height * .7);
  context.restore();
  const dust = small ? 90 : Math.round(width * height / 2600);
  for (let index = 0; index < dust; index += 1) {
    const x = rng() * width, y = rng() * height, r = rng() < .93 ? rng() * .8 + .2 : rng() * 1.2 + .6;
    context.fillStyle = `rgba(220, 232, 255, ${.15 + rng() * .5})`;
    context.beginPath(); context.arc(x, y, r * (small ? .7 : 1), 0, Math.PI * 2); context.fill();
  }
  // Where the stars go: the shape kept whole, room around it for names.
  const reserve = title ? height * .2 : 0;
  const scale = Math.min(width * .4, (height - reserve) * .4);
  const cx = width / 2, cy = (height - reserve) / 2;
  const at = (star) => [cx + star.x * scale, cy - star.y * scale];
  const byKey = Object.fromEntries((item.keys || []).map((key, index) => [key, item.stars[index]]));
  // The lines, faint and glowing.
  context.lineCap = "round";
  context.shadowColor = accent; context.shadowBlur = (small ? 3 : 8) * unit;
  context.strokeStyle = `color-mix(in srgb, ${accent} 55%, transparent)`;
  context.lineWidth = (small ? 1 : 1.6) * unit;
  for (const [a, b] of item.lines || []) {
    if (!byKey[a] || !byKey[b]) continue;
    const [x1, y1] = at(byKey[a]), [x2, y2] = at(byKey[b]);
    context.beginPath(); context.moveTo(x1, y1); context.lineTo(x2, y2); context.stroke();
  }
  context.shadowBlur = 0;
  // The stars: bigger the longer you stayed, coloured by their class.
  const longest = Math.max(...item.stars.map((star) => star.dwell), 1);
  const placed = [];
  item.stars.forEach((star) => {
    const [x, y] = at(star);
    const r = ((small ? 1.6 : 3) + (small ? 2 : 4.5) * Math.sqrt(star.dwell / longest)) * unit;
    drawn.push({x, y, r, star});
    const colour = starColour(star.star);
    const halo = context.createRadialGradient(x, y, 0, x, y, r * 4);
    halo.addColorStop(0, colour); halo.addColorStop(.25, `color-mix(in srgb, ${colour} 45%, transparent)`); halo.addColorStop(1, "transparent");
    try { context.fillStyle = halo; } catch (_error) { context.fillStyle = colour; }
    context.beginPath(); context.arc(x, y, r * 4, 0, Math.PI * 2); context.fill();
    context.fillStyle = "#ffffff";
    context.beginPath(); context.arc(x, y, r * .55, 0, Math.PI * 2); context.fill();
    if (star.dwell === longest && !small) {
      // The brightest: a four-pointed glint.
      context.strokeStyle = "rgba(255, 255, 255, .7)"; context.lineWidth = unit;
      context.beginPath();
      context.moveTo(x - r * 3.2, y); context.lineTo(x + r * 3.2, y);
      context.moveTo(x, y - r * 3.2); context.lineTo(x, y + r * 3.2);
      context.stroke();
    }
    if (names && !small) {
      context.font = `600 ${(title ? 15 : 11) * unit}px Bahnschrift, "Segoe UI", sans-serif`;
      context.fillStyle = `color-mix(in srgb, ${text} 70%, transparent)`;
      const label = star.system;
      const size = (title ? 15 : 11) * unit;
      const wide = context.measureText(label).width;
      // Beside the star, or above or below it, wherever no other name is.
      const spots = [[x + r * 2 + 4, y - r - 3, "left"], [x - r * 2 - 4, y - r - 3, "right"],
        [x, y - r * 2 - 6, "center"], [x, y + r * 2 + size + 2, "center"]];
      for (const [lx, ly, align] of spots) {
        const left = align === "left" ? lx : align === "right" ? lx - wide : lx - wide / 2;
        const box = [left - 2, ly - size, left + wide + 2, ly + 3];
        if (box[0] < 2 || box[2] > width - 2 || box[1] < 2 || box[3] > height - 2) continue;
        if (placed.some((other) => box[0] < other[2] && box[2] > other[0] && box[1] < other[3] && box[3] > other[1])) continue;
        placed.push(box);
        context.textAlign = align;
        context.fillText(label, lx, ly);
        break;
      }
    }
  });
  context.textAlign = "left";
  if (title) {
    // The saved picture carries its name and legend.
    context.fillStyle = text;
    context.font = `italic 600 ${Math.round(height * .055)}px Georgia, "Times New Roman", serif`;
    context.fillText(item.name, width * .05, legend ? height * .86 : height * .93);
    if (legend) {
      context.fillStyle = `color-mix(in srgb, ${text} 72%, transparent)`;
      context.font = `${Math.round(height * .022)}px Georgia, "Times New Roman", serif`;
      context.fillText(item.legend, width * .05, height * .91);
      context.fillStyle = accent;
      context.font = `700 ${Math.round(height * .016)}px Consolas, monospace`;
      context.fillText(`${item.from.toUpperCase()} – ${item.to.toUpperCase()} · ${item.stars.length} STARS · VOID COMPASS`, width * .05, height * .95);
    }
  }
  context.restore();
  return drawn;
}

function paint(canvas, item, options) {
  const box = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(box.width)), height = Math.max(1, Math.round(box.height));
  canvas.width = width * ratio; canvas.height = height * ratio;
  const context = canvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  canvas.stars = draw(context, item, width, height, options);
}

function shell(root, ui) {
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="sky-page">
    <section class="sky-main">
      <div class="sky-canvas"><canvas id="sky-canvas" aria-label="Your constellation"></canvas><div class="sky-tip" id="sky-tip" hidden></div></div>
      <aside class="sky-about">
        <small id="sky-number"></small>
        <h3 id="sky-name"></h3>
        <p id="sky-legend"></p>
        <p class="sky-meta" id="sky-meta"></p>
        <p class="sky-growing" id="sky-growing" hidden></p>
        <ol class="sky-stars" id="sky-stars"></ol>
        <div class="sky-tonight" id="sky-tonight" hidden></div>
        <div class="sky-actions">
          <button type="button" data-sky="names" id="sky-names" aria-pressed="true">NAMES</button>
          <button type="button" class="primary" data-sky="save">SAVE AS PICTURE</button>
        </div>
      </aside>
    </section>
    <section class="sky-gallery"><h3>YOUR SKY</h3><ol id="sky-gallery"></ol></section>
    <p class="sky-empty" id="sky-empty" hidden>No stars yet. Stay somewhere a while and it becomes your first star.</p>
    <details class="keepsake-settings"><summary>CONSTELLATION SETTINGS</summary><div id="sky-settings"></div></details>
  </div>`;
  root.addEventListener("change", async (event) => {
    const field = event.target.closest("[data-sky-setting]");
    if (!field) return;
    const value = field.type === "checkbox" ? field.checked : field.value;
    lastSettingsKey = "";
    if (!(await ui.command("workspace", {page: "constellation", operation: "set", key: field.dataset.skySetting, value}))) {
      ui.showToast("That setting wasn't saved");
    }
  });
  const canvas = ui.byId("sky-canvas"), tip = ui.byId("sky-tip");
  canvas.addEventListener("mousemove", (event) => {
    const box = canvas.getBoundingClientRect();
    const x = event.clientX - box.left, y = event.clientY - box.top;
    const hit = (canvas.stars || []).find((star) => Math.hypot(star.x - x, star.y - y) <= Math.max(9, star.r * 2.5));
    tip.hidden = !hit;
    canvas.style.cursor = hit ? "help" : "";
    if (!hit) return;
    const star = hit.star;
    tip.innerHTML = `<b>${ui.escapeHtml(star.system)}</b><span>${ui.escapeHtml(star.star ? `Class ${star.star}` : "Star")} · stayed ${hours(star.dwell)}${star.visits > 1 ? ` over ${star.visits} visits` : ""}</span>`;
    tip.style.left = `${Math.min(box.width - 220, x + 14)}px`;
    tip.style.top = `${Math.max(4, y - 44)}px`;
  });
  canvas.addEventListener("mouseleave", () => {
    tip.hidden = true;
  });
  root.addEventListener("click", async (event) => {
    const pick = event.target.closest("[data-sky-pick]");
    if (pick) {
      selected = Number(pick.dataset.skyPick);
      lastKey = "";
      show(ui);
      return;
    }
    const button = event.target.closest("[data-sky]");
    if (!button) return;
    if (button.dataset.sky === "names") {
      labels = !labels;
      lastKey = "";
      show(ui);
      await ui.command("workspace", {page: "constellation", operation: "set", key: "constellation_names", value: labels});
      return;
    }
    if (button.dataset.sky === "save") {
      const item = current();
      if (!item) return;
      const width = Number(settings.constellation_picture) || 1600, height = Math.round(width * .625);
      const canvas = document.createElement("canvas");
      canvas.width = width; canvas.height = height;
      draw(canvas.getContext("2d"), item, width, height, {names: labels, title: true, legend: settings.constellation_picture_legend !== false});
      // A JPEG on the way (a PNG of a starry sky is too big to send), as fine
      // as fits; kept as a PNG.
      let picture = "";
      for (const quality of [.95, .9, .82, .72, .6]) {
        picture = canvas.toDataURL("image/jpeg", quality);
        if (picture.length < 1900000) break;
      }
      button.disabled = true;
      try {
        const done = await ui.command("workspace", {page: "constellation", operation: "save", name: item.name, picture});
        ui.showToast(done ? `${item.name} saved with your postcards` : "The picture wasn't saved");
      } finally {
        button.disabled = false;
      }
    }
  });
  window.addEventListener("resize", () => {
    lastKey = "";
    show(ui);
  });
}

function current() {
  return sky[selected >= 0 && selected < sky.length ? selected : sky.length - 1];
}

function hours(seconds) {
  const value = Number(seconds || 0) / 3600;
  return value >= 1 ? `${value.toFixed(1)} h` : `${Math.round(value * 60)} min`;
}

function show(ui, data = lastData) {
  const page = document.querySelector(".sky-page");
  if (!page || !page.offsetParent) return;
  const item = current();
  ui.byId("sky-empty").hidden = Boolean(item);
  page.querySelector(".sky-main").hidden = !item;
  page.querySelector(".sky-gallery").hidden = !item;
  if (!item) return;
  const key = JSON.stringify([item.name, item.stars.length, labels, selected, sky.length, page.getBoundingClientRect().width,
    data?.tonight, settings.constellation_lines, item.lines]);
  if (key === lastKey) return;
  lastKey = key;
  paint(ui.byId("sky-canvas"), item, {names: labels});
  ui.byId("sky-number").textContent = `CONSTELLATION ${item.index} OF ${sky.length}`;
  ui.byId("sky-name").textContent = item.name;
  ui.byId("sky-legend").textContent = item.legend;
  ui.byId("sky-meta").textContent = `${item.from} – ${item.to} · ${item.stars.length} stars · ${item.sessions} sessions`;
  const growing = ui.byId("sky-growing");
  const toGo = (data && data.per ? data.per : 9) - item.stars.length;
  growing.hidden = item.complete;
  growing.textContent = `Still growing: ${toGo} more star${toGo === 1 ? "" : "s"} to finish it.`;
  ui.byId("sky-stars").innerHTML = [...item.stars].sort((a, b) => b.dwell - a.dwell)
    .map((star) => `<li><i style="--star:${starColour(star.star)}"></i><b>${ui.escapeHtml(star.system)}</b><span>${hours(star.dwell)}${star.visits > 1 ? ` · ${star.visits} visits` : ""}</span></li>`).join("");
  const tonight = data?.tonight;
  const card = ui.byId("sky-tonight");
  card.hidden = !tonight;
  if (tonight) {
    card.innerHTML = `<small>TONIGHT SO FAR</small><b>${ui.escapeHtml(tonight.system)}</b>
      <span>${ui.numeric(tonight.minutes)} min${tonight.here ? ", and counting" : ""} · ${tonight.lingering
        ? "your next star, unless you stay somewhere longer"
        : `stay ${ui.numeric(settings.constellation_linger_min || 10)} min somewhere and it becomes a star`}</span>`;
  }
  const names = ui.byId("sky-names");
  names.classList.toggle("active", labels);
  names.setAttribute("aria-pressed", String(labels));
  const gallery = ui.byId("sky-gallery");
  gallery.innerHTML = sky.map((other, index) => `<li><button type="button" data-sky-pick="${index}" class="${other === item ? "active" : ""}">
      <canvas data-sky-thumb="${index}"></canvas><b>${ui.escapeHtml(other.name)}</b><small>${ui.escapeHtml(other.from)}${other.complete ? "" : " · GROWING"}</small></button></li>`).join("");
  gallery.querySelectorAll("[data-sky-thumb]").forEach((canvas) => paint(canvas, sky[Number(canvas.dataset.skyThumb)], {small: true, names: false}));
}

let lastData = null;

function field(ui, key, label, detail, value, options) {
  return `<label class="keepsake-field"><span><b>${ui.escapeHtml(label)}</b><small>${ui.escapeHtml(detail)}</small></span>
    <select data-sky-setting="${key}">${options.map(([option, name]) => `<option value="${option}"${String(option) === String(value) ? " selected" : ""}>${ui.escapeHtml(name)}</option>`).join("")}</select></label>`;
}

function toggle(ui, key, label, detail, checked) {
  return `<label class="keepsake-switch"><input type="checkbox" data-sky-setting="${key}"${checked ? " checked" : ""}>
    <span><b>${ui.escapeHtml(label)}</b><small>${ui.escapeHtml(detail)}</small></span></label>`;
}

function renderSettings(ui) {
  const key = JSON.stringify(settings);
  if (key === lastSettingsKey) return;
  lastSettingsKey = key;
  ui.byId("sky-settings").innerHTML = `
    ${field(ui, "constellation_stars", "Stars in a constellation", "How many stars before one is finished and the next begins.", settings.constellation_stars,
      [5, 6, 7, 8, 9, 10, 11, 12].map((count) => [count, `${count} stars`]))}
    ${field(ui, "constellation_linger_min", "A star is a stay of", "How long you must stay somewhere for it to count.", settings.constellation_linger_min,
      [[5, "5 minutes"], [10, "10 minutes"], [20, "20 minutes"], [30, "30 minutes"], [60, "An hour"]])}
    ${field(ui, "constellation_source", "Stars come from", "One star a session, or every place you stayed that long.", settings.constellation_source,
      [["session", "The longest stay each session"], ["every", "Every stay"]])}
    ${field(ui, "constellation_shape", "Shape", "Your own branching shape, or the stars where they really are (seen from above the galaxy).", settings.constellation_shape,
      [["branching", "Branching"], ["map", "True to the map"]])}
    ${field(ui, "constellation_lines", "Lines", "The colour the stars are joined in.", settings.constellation_lines,
      [["accent", "Your theme's accent"], ["white", "Starlight white"], ["gold", "Old gold"]])}
    ${field(ui, "constellation_picture", "Saved picture size", "SAVE AS PICTURE, 16:10.", settings.constellation_picture,
      [[1600, "1600 × 1000"], [2560, "2560 × 1600"], [3840, "3840 × 2400"]])}
    ${toggle(ui, "constellation_names", "Star names", "Each star's system name beside it.", settings.constellation_names)}
    ${toggle(ui, "constellation_picture_legend", "Legend on the picture", "Its legend and dates under the name on a saved picture.", settings.constellation_picture_legend)}
    ${toggle(ui, "constellation_watcher", "The Watcher names new ones", "When a constellation is finished, the Watcher tells you its name.", settings.constellation_watcher)}`;
}

export function renderConstellation(data = {}, ui) {
  const root = ui.byId("constellation-workspace");
  if (!root) return;
  if (!root.querySelector(".sky-page")) shell(root, ui);
  const before = JSON.stringify(settings);
  settings = data.settings || {};
  if (JSON.stringify(settings) !== before) {
    labels = settings.constellation_names !== false;
    lastKey = "";
  }
  renderSettings(ui);
  const next = Array.isArray(data.sky) ? data.sky : [];
  if (JSON.stringify(next.map((item) => [item.name, item.stars.length])) !== JSON.stringify(sky.map((item) => [item.name, item.stars.length]))) {
    lastKey = "";
  }
  sky = next;
  lastData = data;
  if (selected >= sky.length) selected = -1;
  show(ui, lastData);
}
