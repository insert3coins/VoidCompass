// Your constellation (5.5.3.7, v2 in 5.5.4): each session, the place you
// stayed longest becomes a star; nine stars make a constellation, named by
// the Watcher. v2 adds the sky chart (every constellation where it lies in
// the galaxy), designations, the night behind each star, and an almanac.

let view = "detail";    // "chart" or "detail"
let selected = -1;      // which constellation is shown (-1: the latest)
let picked = "";        // the star whose night is open (its key)
let labels = true;
let designations = true;
let lastKey = "";
let lastChartKey = "";
let lastSettingsKey = "";
let sky = [];
let settings = {};
let lastData = null;
let tracing = null;     // {start, frame} while the lines are being traced
try { view = sessionStorage.getItem("vc-sky-view") || "detail"; } catch { /* the constellation, then */ }

const LINE_COLOURS = {white: "#e8f0ff", gold: "#ffd27a"};
const STAR_COLOURS = {
  O: "#9bb0ff", B: "#aabfff", A: "#cad7ff", F: "#f8f7ff", G: "#fff1dc", K: "#ffd2a1", M: "#ff9f73",
  L: "#d07a5c", T: "#b8654f", Y: "#9c5646", N: "#d8f0ff", H: "#b28cff",
};
// What a star's nights held, as small marks beside it.
const MARKS = {
  first: {glyph: "◆", colour: "#6fe3ff", label: "First discoveries"},
  rare: {glyph: "✦", colour: "#ffd27a", label: "A rare world"},
  photo: {glyph: "▣", colour: "#f2e6c9", label: "A postcard"},
  capsule: {glyph: "⧗", colour: "#c9a7ff", label: "A time capsule left here"},
};
// The sky chart's distance rings, light years from Sol.
const RINGS = [[100, "100 LY"], [1000, "1,000 LY"], [10000, "10,000 LY"], [26000, "26,000 LY"], [65000, "65,000 LY"]];
const GALAXY_RADIUS_LY = 70000;

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

function reducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || document.body.classList.contains("reduced-motion");
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

function night(context, width, height, rng, small) {
  const bg = token("--bg", "#070b10");
  const ground = context.createRadialGradient(width * .5, height * .45, 0, width * .5, height * .45, Math.max(width, height) * .75);
  ground.addColorStop(0, `color-mix(in srgb, ${bg} 70%, #10203a)`);
  ground.addColorStop(1, bg);
  context.fillStyle = bg;
  context.fillRect(0, 0, width, height);
  try { context.fillStyle = ground; context.fillRect(0, 0, width, height); } catch { /* older engines */ }
  const dust = small ? 90 : Math.round(width * height / 2600);
  for (let index = 0; index < dust; index += 1) {
    const x = rng() * width, y = rng() * height, r = rng() < .93 ? rng() * .8 + .2 : rng() * 1.2 + .6;
    context.fillStyle = `rgba(220, 232, 255, ${.15 + rng() * .5})`;
    context.beginPath(); context.arc(x, y, r * (small ? .7 : 1), 0, Math.PI * 2); context.fill();
  }
}

// One constellation into a 2D context of width x height (CSS pixels).
// ``progress`` (0..1) draws its lines only so far, in the order you flew.
function draw(context, item, width, height, {names = true, small = false, title = false, legend = true, progress = 1, focus = ""} = {}) {
  const text = token("--text", "#dce8ef");
  const accent = LINE_COLOURS[settings.constellation_lines] || token("--accent", "#00d1ff");
  const unit = title ? width / 1600 : 1;
  const drawn = [];
  context.save();
  const rng = random(seedOf(item.name));
  night(context, width, height, rng, small);
  // A soft band of the galaxy behind it.
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
  const reserve = title ? height * .2 : 0;
  const scale = Math.min(width * .4, (height - reserve) * .4);
  const cx = width / 2, cy = (height - reserve) / 2;
  const at = (star) => [cx + star.x * scale, cy - star.y * scale];
  const byKey = Object.fromEntries((item.keys || []).map((key, index) => [key, item.stars[index]]));
  // Lines, in the order flown; while tracing, only so far.
  const lines = item.lines || [];
  const shown = progress >= 1 ? lines.length : progress * lines.length;
  const reached = new Set(lines.length ? [lines[0][0]] : (item.keys || []).slice(0, 1));
  context.lineCap = "round";
  context.shadowColor = accent; context.shadowBlur = (small ? 3 : 8) * unit;
  context.strokeStyle = `color-mix(in srgb, ${accent} 55%, transparent)`;
  context.lineWidth = (small ? 1 : 1.6) * unit;
  lines.forEach(([a, b], index) => {
    if (!byKey[a] || !byKey[b] || index >= shown) return;
    const part = Math.min(1, shown - index);
    const [x1, y1] = at(byKey[a]), [x2, y2] = at(byKey[b]);
    context.beginPath(); context.moveTo(x1, y1); context.lineTo(x1 + (x2 - x1) * part, y1 + (y2 - y1) * part); context.stroke();
    reached.add(a);
    if (part >= 1) reached.add(b);
  });
  context.shadowBlur = 0;
  // Still growing: a dashed line out to where the next star will be.
  if (!item.complete && !small && progress >= 1 && item.stars.length) {
    const last = byKey[(item.keys || [])[item.keys.length - 1]];
    const mid = item.stars.reduce((sum, star) => [sum[0] + star.x / item.stars.length, sum[1] + star.y / item.stars.length], [0, 0]);
    let dx = last.x - mid[0], dy = last.y - mid[1];
    const length = Math.hypot(dx, dy) || 1;
    dx /= length; dy /= length;
    const [x1, y1] = at(last);
    const x2 = x1 + dx * scale * .3, y2 = y1 - dy * scale * .3;
    context.save();
    context.setLineDash([4 * unit, 6 * unit]);
    context.strokeStyle = `color-mix(in srgb, ${accent} 45%, transparent)`;
    context.lineWidth = unit;
    context.beginPath(); context.moveTo(x1, y1); context.lineTo(x2, y2); context.stroke();
    context.beginPath(); context.arc(x2, y2, 9 * unit, 0, Math.PI * 2); context.stroke();
    context.restore();
    context.fillStyle = `color-mix(in srgb, ${text} 45%, transparent)`;
    context.font = `italic ${11 * unit}px Georgia, serif`;
    context.textAlign = "center";
    context.fillText("next star", x2, y2 + 24 * unit);
    context.textAlign = "left";
  }
  // The stars: bigger the longer you stayed, coloured by their class.
  const longest = Math.max(...item.stars.map((star) => star.dwell), 1);
  const placed = [];
  item.stars.forEach((star, index) => {
    const key = (item.keys || [])[index];
    if (progress < 1 && !reached.has(key)) return;
    const [x, y] = at(star);
    const r = ((small ? 1.6 : 3) + (small ? 2 : 4.5) * Math.sqrt(star.dwell / longest)) * unit;
    drawn.push({x, y, r, star, key});
    const colour = starColour(star.star);
    const halo = context.createRadialGradient(x, y, 0, x, y, r * 4);
    halo.addColorStop(0, colour); halo.addColorStop(.25, `color-mix(in srgb, ${colour} 45%, transparent)`); halo.addColorStop(1, "transparent");
    try { context.fillStyle = halo; } catch { context.fillStyle = colour; }
    context.beginPath(); context.arc(x, y, r * 4, 0, Math.PI * 2); context.fill();
    context.fillStyle = "#ffffff";
    context.beginPath(); context.arc(x, y, r * .55, 0, Math.PI * 2); context.fill();
    if (star.dwell === longest && !small) {
      context.strokeStyle = "rgba(255, 255, 255, .7)"; context.lineWidth = unit;
      context.beginPath();
      context.moveTo(x - r * 3.2, y); context.lineTo(x + r * 3.2, y);
      context.moveTo(x, y - r * 3.2); context.lineTo(x, y + r * 3.2);
      context.stroke();
    }
    if (focus && key === focus && !small) {
      context.strokeStyle = accent; context.lineWidth = 1.4 * unit;
      context.beginPath(); context.arc(x, y, r * 2.4 + 4, 0, Math.PI * 2); context.stroke();
    }
    if (!small && (star.marks || []).length) {
      // What its nights held, in a little arc under it.
      context.font = `${9 * unit}px "Segoe UI Symbol", "Segoe UI", sans-serif`;
      context.textAlign = "center";
      star.marks.forEach((mark, place) => {
        const angle = Math.PI / 2 + (place - (star.marks.length - 1) / 2) * .55;
        context.fillStyle = MARKS[mark]?.colour || text;
        context.fillText(MARKS[mark]?.glyph || "•", x + Math.cos(angle) * (r * 2.2 + 9), y + Math.sin(angle) * (r * 2.2 + 9) + 3);
      });
      context.textAlign = "left";
    }
    if ((names || designations) && !small) {
      const size = (title ? 15 : 11) * unit;
      context.font = `600 ${size}px Bahnschrift, "Segoe UI", sans-serif`;
      context.fillStyle = `color-mix(in srgb, ${text} 72%, transparent)`;
      const label = [designations ? star.designation : "", names ? star.system : ""].filter(Boolean).join(" ");
      const wide = context.measureText(label).width;
      // Beside the star, or above or below it, wherever no other name is.
      const spots = [[x + r * 2 + 4, y - r - 3, "left"], [x - r * 2 - 4, y - r - 3, "right"],
        [x, y - r * 2 - 6, "center"], [x, y + r * 2 + size + 14, "center"]];
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
      context.textAlign = "left";
    }
  });
  if (title) {
    // The saved picture carries its name, epithet and legend.
    context.fillStyle = text;
    context.font = `italic 600 ${Math.round(height * .055)}px Georgia, "Times New Roman", serif`;
    context.fillText(item.name, width * .05, legend ? height * .86 : height * .93);
    if (legend) {
      context.fillStyle = `color-mix(in srgb, ${text} 72%, transparent)`;
      context.font = `${Math.round(height * .022)}px Georgia, "Times New Roman", serif`;
      context.fillText(`${item.epithet ? `${item.epithet}. ` : ""}${item.legend}`, width * .05, height * .91);
      context.fillStyle = accent;
      context.font = `700 ${Math.round(height * .016)}px Consolas, monospace`;
      const where = item.region ? ` · ${item.region.toUpperCase()}` : "";
      context.fillText(`${item.from.toUpperCase()} – ${item.to.toUpperCase()} · ${item.stars.length} STARS${where} · VOID COMPASS`, width * .05, height * .95);
    }
  }
  context.restore();
  return drawn;
}

function fit(canvas) {
  const box = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(box.width)), height = Math.max(1, Math.round(box.height));
  canvas.width = width * ratio; canvas.height = height * ratio;
  const context = canvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  return [context, width, height];
}

function paint(canvas, item, options) {
  const [context, width, height] = fit(canvas);
  canvas.stars = draw(context, item, width, height, options);
}

// -- The sky chart: every constellation where it lies --------------------------
function ringRadius(ly) {
  return .08 + .86 * Math.log1p(ly / 100) / Math.log1p(GALAXY_RADIUS_LY / 100);
}

function paintChart(canvas, ui) {
  const [context, width, height] = fit(canvas);
  const text = token("--text", "#dce8ef"), muted = token("--muted", "#91a8b7");
  const accent = LINE_COLOURS[settings.constellation_lines] || token("--accent", "#00d1ff");
  const rng = random(seedOf("the whole sky"));
  night(context, width, height, rng, false);
  const R = Math.min(width, height) * .46, cx = width / 2, cy = height / 2;
  // The core's glow, straight up from Sol.
  const coreY = cy - ringRadius(26000) * R;
  const core = context.createRadialGradient(cx, coreY, 0, cx, coreY, R * .45);
  core.addColorStop(0, "rgba(255, 214, 160, .22)"); core.addColorStop(.4, "rgba(200, 170, 255, .08)"); core.addColorStop(1, "rgba(0, 0, 0, 0)");
  context.fillStyle = core;
  context.beginPath(); context.arc(cx, cy, R, 0, Math.PI * 2); context.fill();
  // The astrolabe: rim, degree ticks, distance rings.
  context.strokeStyle = `color-mix(in srgb, ${muted} 45%, transparent)`;
  context.lineWidth = 1;
  context.beginPath(); context.arc(cx, cy, R, 0, Math.PI * 2); context.stroke();
  context.beginPath(); context.arc(cx, cy, R + 7, 0, Math.PI * 2); context.stroke();
  for (let degree = 0; degree < 360; degree += 5) {
    const angle = degree * Math.PI / 180, long = degree % 30 === 0 ? 7 : 3;
    context.beginPath();
    context.moveTo(cx + Math.sin(angle) * R, cy - Math.cos(angle) * R);
    context.lineTo(cx + Math.sin(angle) * (R + long), cy - Math.cos(angle) * (R + long));
    context.stroke();
  }
  context.font = '700 9px Consolas, monospace';
  context.fillStyle = `color-mix(in srgb, ${muted} 80%, transparent)`;
  context.textAlign = "center";
  context.fillText("TOWARD THE CORE", cx, cy - R - 14);
  context.fillText("TOWARD THE RIM", cx, cy + R + 22);
  context.setLineDash([2, 5]);
  for (const [ly, label] of RINGS) {
    const r = ringRadius(ly) * R;
    context.beginPath(); context.arc(cx, cy, r, 0, Math.PI * 2); context.stroke();
    context.fillText(label, cx + r * .72 + 4, cy + r * .72 + 3);
  }
  context.setLineDash([]);
  context.fillStyle = text;
  context.beginPath(); context.arc(cx, cy, 2.5, 0, Math.PI * 2); context.fill();
  context.fillStyle = muted;
  context.fillText("SOL", cx, cy + 14);
  // Each constellation, small, where its stars are.
  const hits = [];
  const labelBoxes = [];
  const mini = R * .075;
  sky.forEach((item, index) => {
    const [px, py] = item.place || [0, 0];
    const ox = cx + px * R, oy = cy - py * R;
    const byKey = Object.fromEntries((item.keys || []).map((key, place) => [key, item.stars[place]]));
    const at = (star) => [ox + star.x * mini, oy - star.y * mini];
    const current = index === (selected >= 0 ? selected : sky.length - 1);
    context.strokeStyle = `color-mix(in srgb, ${accent} ${current ? 85 : 50}%, transparent)`;
    context.lineWidth = current ? 1.4 : 1;
    for (const [a, b] of item.lines || []) {
      if (!byKey[a] || !byKey[b]) continue;
      const [x1, y1] = at(byKey[a]), [x2, y2] = at(byKey[b]);
      context.beginPath(); context.moveTo(x1, y1); context.lineTo(x2, y2); context.stroke();
    }
    for (const star of item.stars) {
      const [x, y] = at(star);
      context.fillStyle = starColour(star.star);
      context.beginPath(); context.arc(x, y, 1.6, 0, Math.PI * 2); context.fill();
    }
    if (!item.complete) {
      context.save();
      context.setLineDash([3, 4]);
      context.strokeStyle = `color-mix(in srgb, ${token("--yellow", "#f5c76d")} 70%, transparent)`;
      context.beginPath(); context.arc(ox, oy, mini * 1.35, 0, Math.PI * 2); context.stroke();
      context.restore();
    }
    context.font = `italic ${current ? 600 : 400} 11px Georgia, serif`;
    context.fillStyle = `color-mix(in srgb, ${text} ${current ? 95 : 70}%, transparent)`;
    // Under it, or over it when another name is already there.
    const label = item.name.replace(/^The /, ""), wide = context.measureText(label).width;
    for (const ly of [oy + mini + 14, oy - mini - 8, oy + mini + 28]) {
      const box = [ox - wide / 2 - 2, ly - 11, ox + wide / 2 + 2, ly + 3];
      if (labelBoxes.some((other) => box[0] < other[2] && box[2] > other[0] && box[1] < other[3] && box[3] > other[1])) continue;
      labelBoxes.push(box);
      context.fillText(label, ox, ly);
      break;
    }
    hits.push({x: ox, y: oy, r: mini * 1.4, index});
  });
  context.textAlign = "left";
  canvas.hits = hits;
  if (ui) ui.byId("sky-chart-count").textContent = `${sky.length} constellation${sky.length === 1 ? "" : "s"}`;
}

// -- The page ---------------------------------------------------------------------
function shell(root, ui) {
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="sky-page">
    <dl class="sky-almanac" id="sky-almanac"></dl>
    <nav class="sky-views" role="tablist" aria-label="Constellation views">
      <button type="button" role="tab" id="sky-tab-chart" data-sky-view="chart">SKY CHART</button>
      <button type="button" role="tab" id="sky-tab-detail" data-sky-view="detail">CONSTELLATION</button>
    </nav>
    <section class="sky-chart-view" id="sky-chart-view" role="tabpanel" aria-labelledby="sky-tab-chart" hidden>
      <div class="sky-chart"><canvas id="sky-chart" aria-label="Every constellation, where it lies in the galaxy"></canvas>
        <div class="sky-tip" id="sky-chart-tip" hidden></div></div>
      <aside class="sky-chart-key">
        <small id="sky-chart-count"></small>
        <h3>Your sky chart</h3>
        <p>Every constellation sits where its stars really are: the direction from Sol, the core straight up, and the distance on rings that soften the long hauls so home and the far side both fit.</p>
        <ul class="sky-key">
          <li><i class="ring"></i>Distance from Sol</li>
          <li><i class="grow"></i>Still growing</li>
          <li><i class="core"></i>The galactic core's glow</li>
        </ul>
        <p class="sky-hint">Click a constellation to open it.</p>
      </aside>
    </section>
    <section class="sky-main" id="sky-detail" role="tabpanel" aria-labelledby="sky-tab-detail">
      <div class="sky-canvas"><canvas id="sky-canvas" aria-label="Your constellation"></canvas><div class="sky-tip" id="sky-tip" hidden></div>
        <div class="sky-canvas-tools">
          <button type="button" data-sky="trace" title="Draw its lines in the order you flew">▶ TRACE</button>
          <button type="button" data-sky="names" id="sky-names" aria-pressed="true">NAMES</button>
          <button type="button" data-sky="designations" id="sky-designations" aria-pressed="true">α β γ</button>
        </div></div>
      <aside class="sky-about">
        <small id="sky-number"></small>
        <h3 id="sky-name"></h3>
        <p class="sky-epithet" id="sky-epithet"></p>
        <p class="sky-legend" id="sky-legend"></p>
        <p class="sky-lore" id="sky-lore"></p>
        <p class="sky-meta" id="sky-meta"></p>
        <div class="sky-figures" id="sky-figures"></div>
        <p class="sky-growing" id="sky-growing" hidden></p>
        <ol class="sky-stars" id="sky-stars"></ol>
        <div class="sky-night" id="sky-night" hidden></div>
        <div class="sky-tonight" id="sky-tonight" hidden></div>
        <div class="sky-actions"><button type="button" class="primary" data-sky="save">SAVE AS PICTURE</button></div>
      </aside>
    </section>
    <section class="sky-gallery" id="sky-gallery-box"><h3>YOUR CONSTELLATIONS</h3><div id="sky-gallery"></div></section>
    <section class="sky-saved" id="sky-saved-box" hidden>
      <header><h3>SAVED PICTURES</h3><button type="button" data-sky-saved-op="open_folder">OPEN FOLDER</button></header>
      <ol id="sky-saved"></ol></section>
    <div class="sky-viewer" id="sky-viewer" hidden role="dialog" aria-modal="true" aria-label="Saved constellation">
      <figure><img id="sky-viewer-img" alt=""><figcaption id="sky-viewer-title"></figcaption></figure>
      <div class="sky-viewer-actions"><button type="button" class="primary" data-sky-saved-op="copy">COPY</button>
        <button type="button" data-sky-saved-op="show">SHOW IN FOLDER</button><button type="button" data-sky-saved-op="close">CLOSE</button></div>
    </div>
    <p class="sky-empty" id="sky-empty" hidden>No stars yet. Stay somewhere a while and it becomes your first star.</p>
    <details class="keepsake-settings"><summary>CONSTELLATION SETTINGS</summary><div id="sky-settings"></div></details>
  </div>`;
  root.addEventListener("change", async (event) => {
    if (event.target.id === "sky-folder") return setFolder(ui, event.target.value.trim());
    const field = event.target.closest("[data-sky-setting]");
    if (!field) return;
    const value = field.type === "checkbox" ? field.checked : field.value;
    lastSettingsKey = "";
    if (!(await ui.command("workspace", {page: "constellation", operation: "set", key: field.dataset.skySetting, value}))) {
      ui.showToast("That setting wasn't saved");
    }
  });
  const canvas = ui.byId("sky-canvas"), tip = ui.byId("sky-tip");
  const hitStar = (event) => {
    const box = canvas.getBoundingClientRect();
    const x = event.clientX - box.left, y = event.clientY - box.top;
    return [(canvas.stars || []).find((star) => Math.hypot(star.x - x, star.y - y) <= Math.max(10, star.r * 2.5)), x, y, box];
  };
  canvas.addEventListener("mousemove", (event) => {
    const [hit, x, y, box] = hitStar(event);
    tip.hidden = !hit;
    canvas.style.cursor = hit ? "pointer" : "";
    if (!hit) return;
    const star = hit.star;
    const marks = (star.marks || []).map((mark) => MARKS[mark]?.label).filter(Boolean).join(" · ");
    tip.innerHTML = `<b>${ui.escapeHtml(`${star.designation || ""} ${star.system}`.trim())}</b><span>${ui.escapeHtml(star.star ? `Class ${star.star}` : "Star")} · stayed ${hours(star.dwell)}${star.visits > 1 ? ` over ${star.visits} visits` : ""}</span>${marks ? `<span>${ui.escapeHtml(marks)}</span>` : ""}<em>Click for the night behind it</em>`;
    tip.style.left = `${Math.min(box.width - 230, x + 14)}px`;
    tip.style.top = `${Math.max(4, y - 50)}px`;
  });
  canvas.addEventListener("mouseleave", () => { tip.hidden = true; });
  canvas.addEventListener("click", (event) => {
    const [hit] = hitStar(event);
    picked = hit ? (picked === hit.key ? "" : hit.key) : "";
    lastKey = "";
    show(ui);
  });
  const chart = ui.byId("sky-chart"), chartTip = ui.byId("sky-chart-tip");
  const hitChart = (event) => {
    const box = chart.getBoundingClientRect();
    const x = event.clientX - box.left, y = event.clientY - box.top;
    return [(chart.hits || []).find((hit) => Math.hypot(hit.x - x, hit.y - y) <= hit.r), x, y, box];
  };
  chart.addEventListener("mousemove", (event) => {
    const [hit, x, y, box] = hitChart(event);
    chartTip.hidden = !hit;
    chart.style.cursor = hit ? "pointer" : "";
    if (!hit) return;
    const item = sky[hit.index];
    chartTip.innerHTML = `<b>${ui.escapeHtml(item.name)}</b><span>${ui.escapeHtml(item.epithet || "")}</span>
      <span>${ui.escapeHtml([item.region, item.from_sol != null ? `${ui.numeric(item.from_sol)} ly from Sol` : "", `${item.stars.length} stars`].filter(Boolean).join(" · "))}</span>`;
    chartTip.style.left = `${Math.min(box.width - 240, x + 14)}px`;
    chartTip.style.top = `${Math.max(4, y - 54)}px`;
  });
  chart.addEventListener("mouseleave", () => { chartTip.hidden = true; });
  chart.addEventListener("click", (event) => {
    const [hit] = hitChart(event);
    if (!hit) return;
    selected = hit.index;
    picked = "";
    setView("detail", ui);
  });
  root.addEventListener("click", async (event) => {
    const tab = event.target.closest("[data-sky-view]");
    if (tab) return setView(tab.dataset.skyView, ui);
    const folder = event.target.closest("[data-sky-folder]");
    if (folder) {
      if (folder.dataset.skyFolder === "default") {
        ui.byId("sky-folder").value = "";
        return setFolder(ui, "");
      }
      const api = window.pywebview?.api;
      if (typeof api?.choose_folder !== "function") return ui.showToast("Choosing a folder works in the Void Compass window.");
      const chosen = await api.choose_folder();
      if (!chosen) return undefined;
      ui.byId("sky-folder").value = String(chosen);
      return setFolder(ui, String(chosen));
    }
    const pick = event.target.closest("[data-sky-pick]");
    if (pick) {
      selected = Number(pick.dataset.skyPick);
      picked = "";
      lastKey = "";
      return setView("detail", ui);
    }
    const star = event.target.closest("[data-sky-star]");
    if (star) {
      picked = picked === star.dataset.skyStar ? "" : star.dataset.skyStar;
      lastKey = "";
      return show(ui);
    }
    const button = event.target.closest("[data-sky]");
    if (!button) return undefined;
    const action = button.dataset.sky;
    if (action === "names" || action === "designations") {
      if (action === "names") labels = !labels; else designations = !designations;
      lastKey = "";
      show(ui);
      return ui.command("workspace", {page: "constellation", operation: "set",
        key: action === "names" ? "constellation_names" : "constellation_designations", value: action === "names" ? labels : designations});
    }
    if (action === "trace") return trace(ui);
    if (action === "save") return save(ui, button);
    return undefined;
  });
  window.addEventListener("resize", () => {
    lastKey = "";
    lastChartKey = "";
    show(ui);
  });
  // The viewer belongs to the window, not the page (as the albums' do): it
  // opens where you are, and shuts if you change page.
  const viewer = ui.byId("sky-viewer");
  document.querySelectorAll("#sky-viewer").forEach((stale) => { if (stale !== viewer) stale.remove(); });
  document.body.append(viewer);
  const savedClick = async (event) => {
    const open = event.target.closest("[data-sky-saved]");
    if (open) return openSaved(ui, open.dataset.skySaved);
    const button = event.target.closest("[data-sky-saved-op]");
    if (!button) {
      if (event.target === viewer) closeSaved(ui);
      return undefined;
    }
    const operation = button.dataset.skySavedOp;
    if (operation === "close") return closeSaved(ui);
    const done = await ui.command("workspace", {page: "constellation", operation, id: shownSaved?.id || ""});
    if (operation === "copy") ui.showToast(done ? "Constellation copied: paste it anywhere" : "It couldn't be copied");
    return undefined;
  };
  root.addEventListener("click", savedClick);
  viewer.addEventListener("click", savedClick);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !viewer.hidden) closeSaved(ui); });
  document.addEventListener("click", (event) => {
    if (!viewer.hidden && event.target.closest?.(".nav-item, [data-page]") && !viewer.contains(event.target)) closeSaved(ui);
  }, true);
}

// Constellations saved as pictures (5.5.4): here, not with the postcards.
let saved = [];
let shownSaved = null;

function drawSaved(ui, rows) {
  saved = Array.isArray(rows) ? rows : [];
  const box = ui.byId("sky-saved-box");
  box.hidden = !saved.length;
  const list = ui.byId("sky-saved");
  const key = JSON.stringify(saved.map((row) => [row.id, row.at]));
  if (list.dataset.key === key) return;
  list.dataset.key = key;
  list.innerHTML = saved.map((row) => `<li><button type="button" data-sky-saved="${ui.escapeHtml(row.id)}" title="${ui.escapeHtml(row.title)}">
      <img src="${ui.apiUrl(`/media/constellation-thumb/${row.id}.jpg?v=${encodeURIComponent(row.at)}`)}" alt="" loading="lazy">
      <b>${ui.escapeHtml(row.title)}</b><small>${ui.escapeHtml(savedOn(row.at))}</small></button></li>`).join("");
}

// Saved on, in the game's calendar like the rest of the page.
function savedOn(seconds) {
  const day = new Date(Number(seconds) * 1000);
  return `SAVED ${day.getDate()} ${day.toLocaleString("en", {month: "short"}).toUpperCase()} ${day.getFullYear() + 1286}`;
}

function openSaved(ui, id) {
  shownSaved = saved.find((row) => row.id === id) || null;
  if (!shownSaved) return;
  ui.byId("sky-viewer-img").src = ui.apiUrl(`/media/constellation/${shownSaved.id}.png?v=${encodeURIComponent(shownSaved.at)}`);
  ui.byId("sky-viewer-title").textContent = shownSaved.title;
  ui.byId("sky-viewer").hidden = false;
}

function closeSaved(ui) {
  shownSaved = null;
  ui.byId("sky-viewer").hidden = true;
  ui.byId("sky-viewer-img").removeAttribute("src");
}

function setView(next, ui) {
  view = next === "chart" ? "chart" : "detail";
  try { sessionStorage.setItem("vc-sky-view", view); } catch { /* not kept */ }
  lastKey = "";
  lastChartKey = "";
  show(ui);
}

// The lines drawn again in the order you flew them.
function trace(ui) {
  const item = current();
  if (!item) return;
  if (reducedMotion()) return ui.showToast("Tracing is off with reduced motion");
  if (tracing) cancelAnimationFrame(tracing.frame);
  const canvas = ui.byId("sky-canvas");
  const length = Math.max(2400, (item.lines || []).length * 650);
  tracing = {start: performance.now()};
  const step = (now) => {
    const progress = Math.min(1, (now - tracing.start) / length);
    paint(canvas, item, {names: labels, progress, focus: picked});
    if (progress < 1) tracing.frame = requestAnimationFrame(step);
    else tracing = null;
  };
  tracing.frame = requestAnimationFrame(step);
  return undefined;
}

async function save(ui, button) {
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
    ui.showToast(done ? `${item.name} saved: it's under SAVED PICTURES` : "The picture wasn't saved");
  } finally {
    button.disabled = false;
  }
}

function current() {
  return sky[selected >= 0 && selected < sky.length ? selected : sky.length - 1];
}

function hours(seconds) {
  const value = Number(seconds || 0) / 3600;
  return value >= 1 ? `${value.toFixed(1)} h` : `${Math.round(value * 60)} min`;
}

function chip(label, value) {
  return `<span><b>${value}</b><small>${label}</small></span>`;
}

function drawAlmanac(ui, data) {
  const book = data?.almanac || {};
  const cell = (label, value, detail = "") => `<div><dt>${label}</dt><dd>${value}</dd>${detail ? `<span>${detail}</span>` : ""}</div>`;
  ui.byId("sky-almanac").innerHTML = book.stars ? [
    cell("CONSTELLATIONS", ui.numeric(book.constellations), `${ui.numeric(book.complete)} finished`),
    cell("STARS", ui.numeric(book.stars), `${ui.numeric(book.hours)} hours lingered`),
    cell("POLE STAR", ui.escapeHtml(book.pole_star?.system || "Not yet"),
      book.pole_star ? `you came back ${ui.numeric(book.pole_star.visits)} times` : "a place you return to"),
    cell("BRIGHTEST", ui.escapeHtml(book.brightest?.system || "—"), book.brightest ? `${book.brightest.hours} h · ${ui.escapeHtml(book.brightest.in)}` : ""),
    cell("FARTHEST", ui.escapeHtml(book.farthest?.name || "—"),
      book.farthest ? `${ui.numeric(book.farthest.ly)} ly from Sol${book.farthest.region ? ` · ${ui.escapeHtml(book.farthest.region)}` : ""}` : ""),
  ].join("") : "";
}

function drawNight(ui, item) {
  const box = ui.byId("sky-night");
  const index = (item.keys || []).indexOf(picked);
  const star = index >= 0 ? item.stars[index] : null;
  box.hidden = !star;
  if (!star) return;
  const esc = ui.escapeHtml;
  const nights = (star.nights || []).map((night) => {
    const figures = night.figures || {};
    const chips = [
      figures.jumps ? chip("jumps", ui.numeric(figures.jumps)) : "",
      figures.distance ? chip("ly", ui.numeric(figures.distance)) : "",
      figures.firsts ? chip("firsts", ui.numeric(figures.firsts)) : "",
      figures.bio ? chip("bio", ui.numeric(figures.bio)) : "",
      figures.credits ? chip("credits", ui.numeric(figures.credits)) : "",
      figures.deaths ? chip("lost", ui.numeric(figures.deaths)) : "",
    ].join("");
    const cards = (night.postcards || []).map((card) => `<img src="${ui.apiUrl(`/media/postcard-thumb/${card.id}.jpg`)}" alt="${esc(card.title)}" title="${esc(card.title)}" loading="lazy">`).join("");
    return `<article><header><b>${esc(night.date)}</b><span>${esc(night.flown)}${night.ship ? ` · ${esc(night.ship)}` : ""}</span></header>
      ${chips ? `<div class="sky-chips">${chips}</div>` : ""}
      ${(night.highlights || []).length ? `<ul>${night.highlights.map((title) => `<li>✦ ${esc(title)}</li>`).join("")}</ul>` : ""}
      ${cards ? `<div class="sky-cards">${cards}</div>` : ""}</article>`;
  }).join("");
  box.innerHTML = `<small>THE NIGHT BEHIND ${esc(star.designation || "")} ${esc(star.system.toUpperCase())}</small>
    <p>${esc(star.star ? `A class ${star.star} star.` : "A star.")} You stayed ${hours(star.dwell)}${star.visits > 1 ? ` over ${star.visits} visits` : ""}.${star.capsules ? ` ${star.capsules} time capsule${star.capsules === 1 ? "" : "s"} left here.` : ""}</p>
    ${nights || "<p>No session record for it: it's older than the Captain's Log.</p>"}
    <div class="sky-night-actions"><button type="button" data-page="chronicle">FLIGHT LOGS</button>${star.capsules ? '<button type="button" data-page="capsules">TIME CAPSULES</button>' : ""}</div>`;
}

function show(ui, data = lastData) {
  const page = document.querySelector(".sky-page");
  if (!page || !page.offsetParent) return;
  const item = current();
  drawAlmanac(ui, data);
  ui.byId("sky-empty").hidden = Boolean(item);
  for (const [id, name] of [["sky-tab-chart", "chart"], ["sky-tab-detail", "detail"]]) {
    ui.byId(id).classList.toggle("active", view === name);
    ui.byId(id).setAttribute("aria-selected", String(view === name));
  }
  page.querySelector(".sky-views").hidden = !item;
  ui.byId("sky-chart-view").hidden = !item || view !== "chart";
  ui.byId("sky-detail").hidden = !item || view !== "detail";
  ui.byId("sky-gallery-box").hidden = !item;
  if (!item) return;
  if (view === "chart") {
    const chartKey = JSON.stringify([sky.map((other) => [other.name, other.stars.length, other.place]), selected,
      page.getBoundingClientRect().width, settings.constellation_lines]);
    if (chartKey !== lastChartKey) {
      lastChartKey = chartKey;
      paintChart(ui.byId("sky-chart"), ui);
    }
  }
  drawGallery(ui, item);
  if (view !== "detail") return;
  const key = JSON.stringify([item.name, item.stars.length, labels, designations, selected, picked, sky.length,
    page.getBoundingClientRect().width, data?.tonight, settings.constellation_lines, item.lines]);
  if (key === lastKey) return;
  lastKey = key;
  if (!tracing) paint(ui.byId("sky-canvas"), item, {names: labels, focus: picked});
  const esc = ui.escapeHtml;
  ui.byId("sky-number").textContent = `CONSTELLATION ${item.index} OF ${sky.length}${item.complete ? "" : " · GROWING"}`;
  ui.byId("sky-name").textContent = item.name;
  ui.byId("sky-epithet").textContent = item.epithet || "";
  ui.byId("sky-legend").textContent = item.legend;
  ui.byId("sky-lore").textContent = item.lore || "";
  ui.byId("sky-meta").textContent = [`${item.from} – ${item.to}`, `${item.stars.length} stars`, `${item.sessions} sessions`,
    item.region ? `over the ${item.region}` : "", item.from_sol != null ? `${Number(item.from_sol).toLocaleString()} ly from Sol` : ""].filter(Boolean).join(" · ");
  const totals = item.totals || {};
  ui.byId("sky-figures").innerHTML = [chip("hours", totals.hours ?? "—"), chip("jumps", ui.numeric(totals.jumps || 0)),
    chip("ly", ui.numeric(totals.distance || 0)), chip("firsts", ui.numeric(totals.firsts || 0)), chip("credits", esc(totals.credits_text || "0"))].join("");
  const growing = ui.byId("sky-growing");
  const toGo = (data && data.per ? data.per : 9) - item.stars.length;
  growing.hidden = item.complete;
  growing.textContent = `Still growing: ${toGo} more star${toGo === 1 ? "" : "s"} to finish it.`;
  const order = item.stars.map((star, index) => [star, item.keys[index]]).sort((a, b) => b[0].dwell - a[0].dwell);
  ui.byId("sky-stars").innerHTML = order.map(([star, starKey]) => `<li><button type="button" data-sky-star="${esc(starKey)}" class="${starKey === picked ? "active" : ""}">
      <em>${esc(star.designation || "")}</em><i style="--star:${starColour(star.star)}"></i><b>${esc(star.system)}</b>
      <span class="sky-marks">${(star.marks || []).map((mark) => `<i style="color:${MARKS[mark].colour}" title="${MARKS[mark].label}">${MARKS[mark].glyph}</i>`).join("")}</span>
      <span>${hours(star.dwell)}${star.visits > 1 ? ` · ${star.visits}×` : ""}</span></button></li>`).join("");
  drawNight(ui, item);
  const tonight = data?.tonight;
  const card = ui.byId("sky-tonight");
  card.hidden = !tonight || item.complete || item !== sky[sky.length - 1];
  if (tonight) {
    card.innerHTML = `<small>${esc(String(tonight.when || "This session").toUpperCase())} SO FAR</small><b>${esc(tonight.system)}</b>
      <span>${ui.numeric(tonight.minutes)} min${tonight.here ? ", and counting" : ""} · ${tonight.lingering
        ? "your next star, unless you stay somewhere longer"
        : `stay ${ui.numeric(settings.constellation_linger_min || 10)} min somewhere and it becomes a star`}</span>`;
  }
  for (const [id, on] of [["sky-names", labels], ["sky-designations", designations]]) {
    ui.byId(id).classList.toggle("active", on);
    ui.byId(id).setAttribute("aria-pressed", String(on));
  }
}

// Every constellation, by the year (in the game's calendar) it began.
function drawGallery(ui, item) {
  const gallery = ui.byId("sky-gallery");
  const key = JSON.stringify([sky.map((other) => [other.name, other.stars.length]), sky.indexOf(item)]);
  if (gallery.dataset.key === key) return;
  gallery.dataset.key = key;
  const years = [];
  sky.forEach((other, index) => {
    const year = String(other.from || "").split(" ").pop();
    if (years.at(-1)?.year !== year) years.push({year, rows: []});
    years.at(-1).rows.push(index);
  });
  gallery.innerHTML = years.map((group) => `<section><h4>${ui.escapeHtml(group.year)}<span>${group.rows.length}</span></h4><ol>${group.rows.map((index) => {
    const other = sky[index];
    return `<li><button type="button" data-sky-pick="${index}" class="${other === item ? "active" : ""}">
      <canvas data-sky-thumb="${index}"></canvas><b>${ui.escapeHtml(other.name)}</b>
      <small>${ui.escapeHtml(other.from)}${other.complete ? "" : " · GROWING"}${other.character ? ` · ${ui.escapeHtml(other.character.toUpperCase())}` : ""}</small></button></li>`;
  }).join("")}</ol></section>`).join("");
  gallery.querySelectorAll("[data-sky-thumb]").forEach((canvas) => paint(canvas, sky[Number(canvas.dataset.skyThumb)], {small: true, names: false}));
}

function field(ui, key, label, detail, value, options) {
  return `<label class="keepsake-field"><span><b>${ui.escapeHtml(label)}</b><small>${ui.escapeHtml(detail)}</small></span>
    <select data-sky-setting="${key}">${options.map(([option, name]) => `<option value="${option}"${String(option) === String(value) ? " selected" : ""}>${ui.escapeHtml(name)}</option>`).join("")}</select></label>`;
}

function toggle(ui, key, label, detail, checked) {
  return `<label class="keepsake-switch"><input type="checkbox" data-sky-setting="${key}"${checked ? " checked" : ""}>
    <span><b>${ui.escapeHtml(label)}</b><small>${ui.escapeHtml(detail)}</small></span></label>`;
}

// Where saved pictures go: your folder, or the one beside Void Compass.
function folderRow(ui) {
  const folder = lastData?.folder || {};
  return `<div class="sky-folder"><span><b>Saved pictures folder</b><small>Empty is the constellations folder beside Void Compass. Pictures already saved stay where they are.</small></span>
    <span class="sky-folder-row"><input type="text" id="sky-folder" aria-label="Saved pictures folder" value="${ui.escapeHtml(folder.path || "")}" placeholder="${ui.escapeHtml(folder.default || "constellations")}">
      <em class="sky-saved-note" id="sky-folder-note" aria-live="polite"></em>
      <button type="button" data-sky-folder="browse">BROWSE</button><button type="button" data-sky-folder="default">DEFAULT</button></span></div>`;
}

async function setFolder(ui, value) {
  const note = ui.byId("sky-folder-note");
  const done = await ui.command("workspace", {page: "constellation", operation: "folder", value});
  if (note) {
    note.textContent = done ? "Saved ✓" : "Not saved";
    note.dataset.tone = done ? "ok" : "bad";
  }
  return done;
}

function renderSettings(ui) {
  const key = JSON.stringify([settings, lastData?.folder]);
  const typing = document.activeElement?.id === "sky-folder";
  if (key === lastSettingsKey || typing) return;
  lastSettingsKey = key;
  ui.byId("sky-settings").innerHTML = `${folderRow(ui)}
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
    ${toggle(ui, "constellation_designations", "Designations", "Greek letters by brightness, as astronomers name stars: α is where you stayed longest.", settings.constellation_designations)}
    ${toggle(ui, "constellation_picture_legend", "Legend on the picture", "Its epithet, legend and dates under the name on a saved picture.", settings.constellation_picture_legend)}
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
    designations = settings.constellation_designations !== false;
    lastKey = "";
    lastChartKey = "";
  }
  const next = Array.isArray(data.sky) ? data.sky : [];
  if (JSON.stringify(next.map((item) => [item.name, item.stars.length])) !== JSON.stringify(sky.map((item) => [item.name, item.stars.length]))) {
    lastKey = "";
    lastChartKey = "";
  }
  sky = next;
  lastData = data;
  renderSettings(ui);
  drawSaved(ui, data.saved);
  if (selected >= sky.length) selected = -1;
  show(ui, lastData);
}
