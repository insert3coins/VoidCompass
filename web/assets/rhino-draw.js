// The Rhino map, drawn the same on the Rhino Map overlay and the deck's
// Rhino page: you, your rigs and their spacing rings, the deposits you've
// marked (numbered in the order to drive them), where you refined, a traced
// rig plan, the planning circle, the survey's coverage, the ship and the
// target. Everything comes in metres east and north of one anchor.
(function () {
  const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;

  function rgb(hex, fallback = [0, 209, 255]) {
    const match = /^#?([0-9a-f]{6})$/i.exec(String(hex || "").trim());
    if (!match) return fallback;
    const value = parseInt(match[1], 16);
    return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
  }
  const css = (colour, alpha) => `rgba(${colour[0]}, ${colour[1]}, ${colour[2]}, ${alpha})`;

  // One colour per commodity everywhere it's drawn.
  const KNOWN = {
    iridium: [55, 198, 212], sapphire: [120, 150, 255], ruby: [255, 92, 120], diamond: [235, 240, 255],
    rhodplumsite: [166, 227, 110], bastnasite: [255, 196, 87], monazite: [255, 150, 70], painite: [220, 110, 255],
    alexandrite: [180, 120, 255], musgravite: [120, 230, 200], serendibite: [90, 220, 140], benitoite: [100, 190, 255],
    grandidierite: [70, 160, 230], platinum: [210, 220, 230], palladium: [200, 200, 170], gold: [255, 215, 70],
    silver: [190, 200, 210], osmium: [140, 170, 200], haematite: [200, 90, 70], thortveitite: [150, 210, 255],
    olivine: [150, 200, 80], periclase: [230, 210, 160], magnesite: [240, 230, 200], jadeite: [80, 200, 120],
    copper: [230, 140, 80], uranium: [140, 255, 120], lithium: [255, 170, 210], tantalum: [160, 160, 230],
  };
  function commodityColour(name) {
    const key = String(name || "").toLowerCase().replace(/[^a-z]/g, "");
    for (const [known, colour] of Object.entries(KNOWN)) if (key.startsWith(known)) return colour;
    let hash = 0;
    for (const char of key) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
    const hue = hash % 360, s = .7, l = .62;
    const f = (n) => {
      const k = (n + hue / 30) % 12, a = s * Math.min(l, 1 - l);
      return Math.round(255 * (l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))));
    };
    return [f(0), f(8), f(4)];
  }

  const RANGE_STEPS = [25, 50, 100, 250, 500, 1000, 2500, 5000];
  const metres = (value) => (value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)} KM` : `${Math.round(value)} M`);
  const shortName = (name) => String(name || "").toUpperCase().replace(/ CRYSTALS?$/, "").slice(0, 12);

  // Coverage bits drawn once into a small canvas, then scaled onto the map.
  let coverCache = {key: "", canvas: null};
  function coverCanvas(survey, colour) {
    const grid = number(survey.grid, 48), bits = String(survey.covered || "");
    const key = `${grid}:${colour.join(",")}:${bits.length}:${bits.slice(0, 64)}:${bits.slice(-64)}:${survey.percent}`;
    if (coverCache.key === key) return coverCache.canvas;
    const canvas = coverCache.canvas || document.createElement("canvas");
    canvas.width = grid; canvas.height = grid;
    const context = canvas.getContext("2d");
    const image = context.createImageData(grid, grid);
    for (let index = 0; index < bits.length; index += 1) {
      const nibble = parseInt(bits[index], 16);
      if (!nibble) continue;
      for (let bit = 0; bit < 4; bit += 1) {
        if (!(nibble & (1 << bit))) continue;
        const cell = index * 4 + bit, row = Math.floor(cell / grid), column = cell % grid;
        if (row >= grid) continue;
        // Row 0 is the south edge; the canvas's row 0 is its top.
        const at = ((grid - 1 - row) * grid + column) * 4;
        image.data[at] = colour[0]; image.data[at + 1] = colour[1]; image.data[at + 2] = colour[2]; image.data[at + 3] = 255;
      }
    }
    context.putImageData(image, 0, 0);
    coverCache = {key, canvas};
    return canvas;
  }

  // frame(): east/north metres to the screen, turned by the heading unless north is up.
  function frame(view, size) {
    const scale = Math.min(size.width, size.height) / 2 / view.half;
    const turn = view.up === "north" ? 0 : view.heading * Math.PI / 180;
    const cos = Math.cos(turn), sin = Math.sin(turn);
    const cx = size.width / 2 + number(view.offsetX), cy = size.height / 2 + number(view.offsetY);
    const at = (point) => {
      const dx = number(point[0]) - view.x, dy = number(point[1]) - view.y;
      return [cx + (dx * cos - dy * sin) * scale, cy - (dx * sin + dy * cos) * scale];
    };
    const back = ([px, py]) => {
      const x = (px - cx) / scale, y = -(py - cy) / scale;
      return [view.x + x * cos + y * sin, view.y - x * sin + y * cos];
    };
    return {at, back, scale, cx, cy, turn};
  }

  function draw(canvas, surface, view, palette = {}, options = {}) {
    const ratio = window.devicePixelRatio || 1;
    const box = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(box.width * ratio)), height = Math.max(1, Math.round(box.height * ratio));
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
    const size = {width: box.width, height: box.height};
    const context = canvas.getContext("2d");
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, size.width, size.height);
    const f = frame(view, size);
    const {at, cx, cy} = f;
    const centre = [size.width / 2, size.height / 2];
    const hud = rgb(palette.orange, [255, 122, 24]);
    const green = rgb(palette.green, [78, 229, 155]), yellow = rgb(palette.yellow, [255, 209, 102]);
    const text = rgb(palette.text, [220, 232, 239]), accent = rgb(palette.accent, [0, 209, 255]);
    const muted = rgb(palette.muted, [133, 147, 157]), red = rgb(palette.red, [255, 96, 117]);
    const amber = [255, 181, 69];
    const textScale = number(options.textScale, 1) || 1;
    const font = (px) => `700 ${px * textScale}px Bahnschrift, "Segoe UI", sans-serif`;
    const inside = ([px, py], pad = 6) => px >= pad && py >= pad && px <= size.width - pad && py <= size.height - pad;
    const placed = [];
    const hits = [];
    let unlabelled = 0;
    // A label where it touches nothing else: above, below, right or left; or not at all.
    const label = (words, [px, py], colour, prefer = -9, force = false) => {
      context.font = font(options.labelPx || 7.2);
      const w = context.measureText(words).width, h = (options.labelPx || 7.2) * textScale + 2;
      const tries = [[-w / 2, prefer], [-w / 2, 14], [9, 3], [-w - 9, 3]];
      // A label that must show (a rig's COLLECT or NEXT) still takes a free
      // place if there is one, and only lands on another where there's none.
      const draw = (x, y, rect) => {
        placed.push(rect);
        context.lineWidth = 2.6; context.strokeStyle = "rgba(0, 0, 0, .8)"; context.strokeText(words, x, y);
        context.fillStyle = css(colour, .95); context.fillText(words, x, y);
        return true;
      };
      const spots = tries.map(([dx, dy]) => {
        const x = Math.max(3, Math.min(size.width - w - 3, px + dx)), y = py + dy;
        return [x, y, [x - 1, y - h + 2, w + 2, h]];
      });
      for (const [x, y, rect] of spots) {
        if (placed.some((other) => rect[0] < other[0] + other[2] && other[0] < rect[0] + rect[2] && rect[1] < other[1] + other[3] && other[1] < rect[1] + rect[3])) continue;
        return draw(x, y, rect);
      }
      if (force) return draw(...spots[0]);
      unlabelled += 1;
      return false;
    };
    const edge = (point) => {
      const dx = point[0] - centre[0], dy = point[1] - centre[1];
      const reach = Math.min(Math.abs((size.width / 2 - 10) / (dx || 1e-6)), Math.abs((size.height / 2 - 10) / (dy || 1e-6)));
      return [centre[0] + dx * reach, centre[1] + dy * reach, Math.atan2(dy, dx)];
    };
    const pointer = ([x, y, angle], colour) => {
      context.save(); context.translate(x, y); context.rotate(angle);
      context.beginPath(); context.moveTo(6, 0); context.lineTo(-4, -4.5); context.lineTo(-1.5, 0); context.lineTo(-4, 4.5); context.closePath();
      context.fillStyle = "rgba(0, 0, 0, .8)"; context.fill();
      context.lineWidth = 1.4; context.strokeStyle = css(colour, 1); context.stroke();
      context.restore();
    };
    const ring = (point, radius, colour, alpha, dash = null, widthPx = 1) => {
      if (dash) context.setLineDash(dash);
      context.strokeStyle = css(colour, alpha); context.lineWidth = widthPx;
      context.beginPath(); context.arc(point[0], point[1], radius, 0, Math.PI * 2); context.stroke();
      if (dash) context.setLineDash([]);
    };
    const you = surface.you?.at;
    const youSpot = you ? at(you) : centre;

    // Range rings round you.
    const ringStep = RANGE_STEPS.find((step) => step * f.scale >= Math.min(size.width, size.height) * .16) || 5000;
    for (let n = 1; n * ringStep * f.scale < Math.hypot(size.width, size.height); n += 1) {
      ring(youSpot, n * ringStep * f.scale, accent, n % 2 ? .1 : .18);
    }
    if (view.up !== "north") {
      const radius = Math.min(size.width, size.height) / 2 - 12;
      const nx = centre[0] + Math.sin(-f.turn) * radius, ny = centre[1] - Math.cos(-f.turn) * radius;
      context.font = font(7.5); context.textAlign = "center"; context.textBaseline = "middle";
      context.lineWidth = 2.4; context.strokeStyle = "rgba(0, 0, 0, .8)"; context.strokeText("N", nx, ny);
      context.fillStyle = css(text, .8); context.fillText("N", nx, ny);
      context.textAlign = "start"; context.textBaseline = "alphabetic";
    }

    // The survey: its centre, then (once the edge is marked) coverage, the
    // edge and the sweep stops. Nothing here depends on the map's range.
    const survey = surface.survey;
    if (survey?.at) {
      const middle = at(survey.at);
      context.strokeStyle = css(accent, .9); context.lineWidth = 1.5;
      context.beginPath();
      context.moveTo(middle[0] - 6, middle[1]); context.lineTo(middle[0] + 6, middle[1]);
      context.moveTo(middle[0], middle[1] - 6); context.lineTo(middle[0], middle[1] + 6);
      context.stroke();
      if (!survey.edge) {
        if (inside(middle)) label("SURVEY CENTRE", middle, accent, -9);
        else { const point = edge(middle); pointer(point, accent); label(`CENTRE ${metres(number(survey.centre_m))}`, point, accent, point[1] < cy ? 14 : -8); }
      }
    }
    if (survey?.at && survey.edge) {
      const middle = at(survey.at);
      const radius = number(survey.radius_m) * f.scale;
      if (survey.covered && radius > 4) {
        context.save();
        context.beginPath(); context.arc(middle[0], middle[1], radius, 0, Math.PI * 2); context.clip();
        context.translate(middle[0], middle[1]);
        context.rotate(-f.turn);
        context.globalAlpha = .14;
        context.imageSmoothingEnabled = true;
        context.drawImage(coverCanvas(survey, accent), -radius, -radius, radius * 2, radius * 2);
        context.restore();
      }
      ring(middle, radius, accent, .65, [8, 5], 1.4);
      const following = survey.next?.at;
      for (const stop of survey.stops || []) {
        const spot = at(stop.at);
        if (!inside(spot)) continue;
        const isNext = following && stop.at[0] === following[0] && stop.at[1] === following[1];
        context.beginPath(); context.arc(spot[0], spot[1], isNext ? 4.5 : 3.2, 0, Math.PI * 2);
        if (stop.swept) { context.fillStyle = css(green, .75); context.fill(); }
        else { context.fillStyle = "rgba(0, 0, 0, .7)"; context.fill(); context.strokeStyle = css(isNext ? hud : accent, .9); context.lineWidth = 1.3; context.stroke(); }
      }
      if (following) {
        const spot = at(following);
        if (inside(spot)) label("SWEEP", spot, hud, -8);
        else { const point = edge(spot); pointer(point, hud); label(`SWEEP ${metres(number(survey.next.distance))}`, point, hud, point[1] < cy ? 14 : -8); }
      }
    }

    // The planning circle: rig and drive inside it.
    if (surface.circle?.at) {
      const spot = at(surface.circle.at);
      ring(spot, number(surface.circle.radius_m, 4500) * f.scale, number(surface.circle.room) < 0 ? red : yellow, .8, [10, 4], 1.6);
    }

    // Your trail.
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

    // A traced deposit edge, and the one being driven now.
    const outline = (points, colour, alpha, closed) => {
      if (!points || points.length < 2) return;
      const spots = points.map(at);
      context.setLineDash(closed ? [5, 3] : [2, 3]); context.strokeStyle = css(colour, alpha); context.lineWidth = 1.4;
      context.beginPath(); context.moveTo(...spots[0]); spots.slice(1).forEach((point) => context.lineTo(...point));
      if (closed) context.closePath();
      context.stroke(); context.setLineDash([]);
      if (closed) { context.fillStyle = css(colour, .06); context.fill(); }
    };
    outline(surface.traced?.outline, green, .7, true);
    outline(surface.tracing, hud, .95, false);

    // Where refining happened away from rigs and marked deposits.
    for (const spotRow of surface.refined || []) {
      const spot = at(spotRow.at);
      if (!inside(spot, -6)) continue;
      const radius = Math.min(7, 2 + Math.sqrt(number(spotRow.pulses, 1)));
      context.fillStyle = css(yellow, .14);
      context.beginPath(); context.arc(spot[0], spot[1], radius + 2.5, 0, Math.PI * 2); context.fill();
      context.fillStyle = css(yellow, .8);
      context.beginPath(); context.arc(spot[0], spot[1], radius * .5, 0, Math.PI * 2); context.fill();
    }

    // The best patch.
    if (surface.best_patch?.at) {
      const spot = at(surface.best_patch.at);
      if (inside(spot, -6)) {
        context.strokeStyle = css(yellow, .9); context.lineWidth = 1.2;
        context.setLineDash([2, 3]); context.beginPath(); context.arc(spot[0], spot[1], Math.max(14, 75 * f.scale), 0, Math.PI * 2); context.stroke(); context.setLineDash([]);
        const patch = surface.best_patch;
        label(patch.marked ? `BEST PATCH ${number(patch.rigs)}R` : `BEST ${number(patch.pulses)}`, [spot[0], spot[1] - Math.max(14, 75 * f.scale)], yellow, -3);
      } else {
        pointer(edge(spot), yellow);
      }
    }

    // The best patches: knots of five rigs' worth or more, with Cr/h once there's a value.
    const money = (value) => {
      const v = number(value);
      return v >= 1e6 ? `${(v / 1e6).toFixed(2)}M` : v >= 1e3 ? `${Math.round(v / 1e3)}K` : `${Math.round(v)}`;
    };
    for (const group of surface.groups || []) {
      const spot = at(group.at);
      const reach = Math.max(16, (number(group.reach_m) + 40) * f.scale);
      if (!inside(spot, -reach)) {
        if (group.n === 1) pointer(edge(spot), yellow);
        continue;
      }
      ring(spot, reach, yellow, .55, [6, 4], 1.2);
      const words = `PATCH ${group.n} · ${group.rigs}R${group.cr_per_h ? ` · ~${money(group.cr_per_h)}/H` : ""}`;
      label(words, [spot[0], spot[1] - reach], yellow, -3);
    }

    // From you: to the nearest deposit of what you're working (solid), and of
    // the next cheaper commodity here (dotted).
    const lines = surface.lines || {};
    for (const [row, dash] of [[lines.same, []], [lines.cheaper, [2, 4]]]) {
      if (!row?.at) continue;
      const spot = at(row.at);
      context.setLineDash(dash); context.strokeStyle = css(commodityColour(row.commodity), .55); context.lineWidth = 1.1;
      context.beginPath(); context.moveTo(...youSpot); context.lineTo(spot[0], spot[1]); context.stroke();
      context.setLineDash([]);
    }

    // Your marked deposits, coloured by commodity, numbered in driving order.
    const selected = options.selected;
    for (const deposit of surface.deposits || []) {
      const spot = at(deposit.at);
      const colour = deposit.depleted ? muted : commodityColour(deposit.commodity);
      if (!inside(spot, -8)) {
        if (deposit.n && deposit.n <= 3) {
          const point = edge(spot); pointer(point, colour);
          label(`${shortName(deposit.commodity)} ${metres(number(deposit.distance))}`, point, colour, point[1] < cy ? 14 : -8);
        }
        continue;
      }
      const radius = 4 + Math.min(4, number(deposit.rigs) * .6);
      context.fillStyle = "rgba(0, 0, 0, .85)";
      context.beginPath(); context.arc(spot[0], spot[1], radius + 1.5, 0, Math.PI * 2); context.fill();
      context.fillStyle = css(colour, deposit.depleted ? .45 : .95);
      context.beginPath(); context.arc(spot[0], spot[1], radius, 0, Math.PI * 2); context.fill();
      if (selected != null && String(selected) === String(deposit.id)) ring(spot, radius + 4, text, .95, null, 1.5);
      // Worked out a while ago: worth a look to see if it's grown back.
      if (deposit.due) ring(spot, radius + 7, yellow, .9, [3, 3], 1.4);
      if (deposit.n) {
        context.font = font(6.6); context.textAlign = "center"; context.textBaseline = "middle";
        context.fillStyle = "rgba(0, 0, 0, .9)"; context.fillText(String(deposit.n), spot[0], spot[1] + .5);
        context.textAlign = "start"; context.textBaseline = "alphabetic";
      }
      const range = deposit.distance != null && options.ranges !== false ? ` ${metres(number(deposit.distance))}` : "";
      const words = `${shortName(deposit.commodity)}${deposit.due ? " · RECHECK" : deposit.depleted ? " · MINED" : `${range}${deposit.rigs ? ` ${deposit.rigs}R` : ""}`}`;
      label(words, [spot[0], spot[1] - radius - (deposit.due ? 3 : 0)], deposit.due ? yellow : colour, -4);
      hits.push({kind: "deposit", id: deposit.id, at: spot, r: radius + 4});
    }

    // Saved sites that aren't deposits, and the compass target.
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
      } else pointer(edge(spot), green);
    }

    // The spacing ring round each rig: red inside, amber in the 2 m band, green clear.
    const spacing = number(surface.spacing_m, 78) * f.scale;
    const states = surface.radar?.rings || [];
    if (spacing > 5 && (surface.rigs || []).length < 6) {
      (surface.rigs || []).forEach((rig, index) => {
        const state = states[index] || "ok";
        const colour = state === "close" ? red : state === "edge" ? amber : green;
        ring(at(rig.at), spacing, colour, state === "ok" ? .35 : .85, null, state === "ok" ? 1 : 1.6);
      });
    }

    // Plan pins: P1..P6 from a traced edge, or the pattern round the first rig.
    for (const pin of surface.plan || []) {
      const spot = at(pin.at);
      if (!inside(spot)) continue;
      const filled = pin.filled, isNext = pin.next;
      const colour = filled ? green : isNext ? hud : green;
      context.setLineDash(filled ? [] : [2, 2]); context.strokeStyle = css(colour, filled ? .9 : isNext ? 1 : .55); context.lineWidth = isNext ? 1.6 : 1;
      context.beginPath(); context.moveTo(spot[0], spot[1] - 6); context.lineTo(spot[0] + 4.5, spot[1]);
      context.lineTo(spot[0], spot[1] + 6); context.lineTo(spot[0] - 4.5, spot[1]); context.closePath(); context.stroke();
      context.setLineDash([]);
      if (filled) { context.fillStyle = css(green, .35); context.fill(); }
      if (pin.n) label(`P${pin.n}`, [spot[0] + 6, spot[1] + 3], colour, 0);
    }

    // Where the next rig goes.
    const legal = surface.next_spot;
    if (legal && !legal.here && legal.at) {
      const spot = at(legal.at);
      if (inside(spot)) {
        context.setLineDash([3, 3]); context.strokeStyle = css(green, .6); context.lineWidth = 1.2;
        context.beginPath(); context.moveTo(...youSpot); context.lineTo(spot[0], spot[1]); context.stroke();
        context.setLineDash([]);
        context.fillStyle = css(green, .9);
        context.beginPath(); context.moveTo(spot[0], spot[1] - 6); context.lineTo(spot[0] + 4, spot[1]);
        context.lineTo(spot[0], spot[1] + 6); context.lineTo(spot[0] - 4, spot[1]); context.closePath(); context.fill();
        label(legal.pin ? `RIG P${legal.pin}` : "RIG HERE", spot, green, -9);
      }
    }

    // Your rigs: numbered squares in the colour of what they're working.
    const next = surface.next_rig;
    const farSlots = new Set((surface.too_far || []).map((row) => row.slot));
    for (const rig of surface.rigs || []) {
      const spot = at(rig.at);
      const isNext = rig.slot === next, far = farSlots.has(rig.slot);
      const tint = rig.commodity ? commodityColour(rig.commodity) : text;
      const colour = far ? red : rig.here ? green : tint;
      if (!inside(spot, -10)) {
        if (isNext || far) pointer(edge(spot), far ? red : hud);
        continue;
      }
      const reach = number(surface.here_m, 40) * f.scale;
      if (reach > 4) ring(spot, reach, colour, .45, [2, 3]);
      context.fillStyle = "rgba(0, 0, 0, .88)"; context.fillRect(spot[0] - 7, spot[1] - 7, 14, 14);
      context.strokeStyle = css(colour, 1); context.lineWidth = isNext ? 2 : 1.3; context.strokeRect(spot[0] - 6.2, spot[1] - 6.2, 12.4, 12.4);
      context.font = font(7.5); context.textAlign = "center"; context.textBaseline = "middle";
      context.fillStyle = css(colour, 1); context.fillText(String(rig.slot), spot[0], spot[1] + .5);
      context.textAlign = "start"; context.textBaseline = "alphabetic";
      if (rig.ready) label("COLLECT", spot, accent, -11, true);
      else if (isNext && !rig.here) label("NEXT", spot, hud, -11, true);
      if (rig.commodity && options.rigLabels !== false) label(`${shortName(rig.commodity)}${rig.tonnes ? ` ${rig.tonnes}T` : ""}`, [spot[0] + 10, spot[1] + 3], tint, 0);
      hits.push({kind: "rig", slot: rig.slot, at: spot, r: 9});
    }
    const nextRig = (surface.rigs || []).find((rig) => rig.slot === next);
    if (nextRig && !nextRig.here) {
      const spot = at(nextRig.at);
      context.setLineDash([4, 4]); context.strokeStyle = css(hud, .55); context.lineWidth = 1.2;
      context.beginPath(); context.moveTo(...youSpot); context.lineTo(spot[0], spot[1]); context.stroke();
      context.setLineDash([]);
    }

    // The ship.
    if (surface.ship?.at) {
      const spot = at(surface.ship.at);
      if (inside(spot)) {
        context.save(); context.translate(spot[0], spot[1]);
        context.beginPath(); context.moveTo(0, -6); context.lineTo(5, 5); context.lineTo(0, 2.5); context.lineTo(-5, 5); context.closePath();
        context.fillStyle = "rgba(0, 0, 0, .85)"; context.fill();
        context.strokeStyle = css(accent, 1); context.lineWidth = 1.5; context.stroke();
        context.restore();
        label("SHIP", spot, accent, -9);
      } else {
        const point = edge(spot); pointer(point, accent);
        label(`SHIP ${metres(number(surface.ship.distance))}`, point, accent, point[1] < cy ? 14 : -8);
      }
    }

    // You.
    if (you) {
      context.save(); context.translate(youSpot[0], youSpot[1]);
      context.rotate(view.up === "north" ? number(view.heading) * Math.PI / 180 : 0);
      context.beginPath(); context.moveTo(0, -8); context.lineTo(6, 6); context.lineTo(0, 3); context.lineTo(-6, 6); context.closePath();
      context.lineWidth = 3; context.strokeStyle = "rgba(0, 0, 0, .85)"; context.stroke();
      context.fillStyle = css(hud, 1); context.fill();
      context.restore();
    }

    const value = surface.value;
    if (value && options.header !== false) {
      context.font = font(7.2);
      const left = `${number(value.deposits)} DEP  ${number(value.rigs)}R${value.credits ? `  ~${money(value.credits)} CR` : ""}`;
      const right = `RADIUS ${metres(view.half)}`;
      context.lineWidth = 2.4; context.strokeStyle = "rgba(0, 0, 0, .75)";
      context.strokeText(left, 7, 12); context.fillStyle = css(yellow, .95); context.fillText(left, 7, 12);
      const width = context.measureText(right).width;
      context.strokeText(right, size.width - width - 7, 12); context.fillStyle = css(muted, .95); context.fillText(right, size.width - width - 7, 12);
    }
    context.font = font(7);
    const scaleText = `RINGS ${metres(ringStep)}${unlabelled ? ` · +${unlabelled} MORE` : ""}`;
    context.lineWidth = 2.4; context.strokeStyle = "rgba(0, 0, 0, .75)";
    context.strokeText(scaleText, 7, size.height - 7);
    context.fillStyle = css(muted, .95); context.fillText(scaleText, 7, size.height - 7);
    return {...f, hits, ringStep, youSpot};
  }

  // The words for the radar and the next rig, shared by every Rhino view.
  function rigWords(surface) {
    const rigs = surface.rigs || [];
    const far = (surface.too_far || [])[0];
    if (far) return {text: `RIG ${far.slot} ${(number(far.distance) / 1000).toFixed(1)} KM · LOST AT 5 KM`, tone: "warn"};
    const ready = rigs.find((rig) => rig.ready);
    if (ready) return {text: `COLLECT RIG ${ready.slot}`, tone: "route"};
    const state = surface.radar?.state;
    if (state === "full" || rigs.length >= 6) return {text: "ALL 6 RIGS DOWN", tone: ""};
    const spot = surface.next_spot;
    if (state === "close" && spot) return {text: `TOO CLOSE · NEXT RIG ${metres(number(spot.distance))} · ${String(Math.round(number(spot.bearing))).padStart(3, "0")}°`, tone: "warn"};
    if (state === "none") return {text: "NO ROOM FOR A RIG HERE", tone: "warn"};
    if (spot?.planned && !spot.here) return {text: `RIG P${spot.pin || ""} ${metres(number(spot.distance))} · ${String(Math.round(number(spot.bearing))).padStart(3, "0")}°`, tone: ""};
    if (state === "edge") return {text: "RIG OK HERE · JUST", tone: "edge"};
    if (state === "ok" || spot?.here) return {text: "RIG OK HERE", tone: "route"};
    return null;
  }

  function turnArrow(heading, bearing) {
    if (heading == null || bearing == null) return "";
    const offset = ((number(bearing) - number(heading) + 540) % 360) - 180;
    return Math.abs(offset) < 6 ? "▲" : Math.abs(offset) > 150 ? "▼" : offset > 0 ? "▶" : "◀";
  }

  function nextWords(surface) {
    const deposit = surface.next_deposit;
    if (!deposit) return null;
    const worth = number(surface.value?.credits);
    const money = worth >= 1e6 ? `${(worth / 1e6).toFixed(2)}M` : worth >= 1e3 ? `${Math.round(worth / 1e3)}K` : "";
    return `NEXT ${turnArrow(surface.you?.heading, deposit.bearing)} ${String(deposit.commodity).toUpperCase()} ${metres(number(deposit.distance))} ${String(Math.round(number(deposit.bearing)) % 360).padStart(3, "0")}°${money ? ` · ~${money} CR HERE` : ""}`;
  }

  window.VoidCompassRhinoDraw = {draw, frame, rgb, css, commodityColour, metres, rigWords, nextWords, turnArrow, number};
})();
