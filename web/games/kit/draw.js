// Drawing for the cabinets: glow lines, text, wireframes in 3D, and the
// small sums every game needs.
(() => {
  "use strict";
  const Kit = window.Kit = window.Kit || {};

  Kit.DISPLAY = '"Bahnschrift SemiCondensed", "Arial Narrow", sans-serif';
  Kit.MONO = "Consolas, monospace";
  Kit.pad = (value, size = 2) => String(value).padStart(size, "0");
  Kit.clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  Kit.lerp = (from, to, t) => from + (to - from) * t;
  Kit.chance = (p) => Math.random() < p;
  Kit.between = (low, high) => low + Math.random() * (high - low);
  Kit.pick = (items) => items[Math.floor(Math.random() * items.length)];
  Kit.wrap = (value, size) => ((value % size) + size) % size;

  // Elite's ranks, and the score each takes here (a game can scale them).
  Kit.RANKS = [[0, "HARMLESS"], [2000, "MOSTLY HARMLESS"], [6000, "NOVICE"], [15000, "COMPETENT"], [30000, "EXPERT"],
    [60000, "MASTER"], [100000, "DANGEROUS"], [160000, "DEADLY"], [250000, "ELITE"]];
  Kit.TITLES = {
    combat: Kit.RANKS.map(([, label]) => label),
    trade: ["PENNILESS", "MOSTLY PENNILESS", "PEDDLER", "DEALER", "MERCHANT", "BROKER", "ENTREPRENEUR", "TYCOON", "ELITE"],
    explore: ["AIMLESS", "MOSTLY AIMLESS", "SCOUT", "SURVEYOR", "TRAILBLAZER", "PATHFINDER", "RANGER", "PIONEER", "ELITE"],
    mercenary: ["DEFENCELESS", "MOSTLY DEFENCELESS", "ROOKIE", "SOLDIER", "GUNSLINGER", "WARRIOR", "GLADIATOR", "DEADEYE", "ELITE"],
  };
  Kit.rank = (score, scale = 1, kind = "combat") => {
    const titles = Kit.TITLES[kind] || Kit.TITLES.combat;
    let index = 0;
    Kit.RANKS.forEach(([floor], step) => { if (score >= floor * scale) index = step; });
    return titles[index];
  };

  Kit.draw = function draw(ctx) {
    function poly(points, close = true) {
      ctx.beginPath();
      points.forEach(([x, y], index) => (index ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      if (close) ctx.closePath();
    }
    function glow(colour, blur) {
      ctx.shadowColor = colour;
      ctx.shadowBlur = blur;
    }
    function text(value, x, y, size, colour, align = "center", weight = 700, family = Kit.MONO) {
      ctx.font = `${weight} ${size}px ${family}`;
      ctx.textAlign = align;
      ctx.fillStyle = colour;
      ctx.fillText(value, x, y);
    }
    function line(x1, y1, x2, y2, colour, width = 1.5, blur = 0) {
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = colour;
      ctx.lineWidth = width;
      if (blur) glow(colour, blur);
      ctx.stroke();
      if (blur) ctx.shadowBlur = 0;
    }
    function circle(x, y, r, fill, stroke, width = 1.5) {
      ctx.beginPath();
      ctx.arc(x, y, Math.max(0, r), 0, Math.PI * 2);
      if (fill) { ctx.fillStyle = fill; ctx.fill(); }
      if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = width; ctx.stroke(); }
    }
    function shade(colour, alpha, w, h) {
      ctx.fillStyle = colour;
      ctx.globalAlpha = alpha;
      ctx.fillRect(0, 0, w, h);
      ctx.globalAlpha = 1;
    }
    // A bar from 0 to 1, with its label.
    function bar(x, y, w, h, value, colour, back = "rgba(255,255,255,.08)") {
      ctx.fillStyle = back;
      ctx.fillRect(x, y, w, h);
      ctx.fillStyle = colour;
      ctx.fillRect(x, y, w * Kit.clamp(value, 0, 1), h);
    }
    return {ctx, poly, glow, text, line, circle, shade, bar};
  };

  // ---- 3D wireframes: a model is {points: [[x,y,z]...], edges: [[a,b]...]}. ----
  Kit.rotate = ([x, y, z], yaw = 0, pitch = 0, roll = 0) => {
    let cos = Math.cos(roll), sin = Math.sin(roll);
    [x, y] = [x * cos - y * sin, x * sin + y * cos];
    cos = Math.cos(pitch); sin = Math.sin(pitch);
    [y, z] = [y * cos - z * sin, y * sin + z * cos];
    cos = Math.cos(yaw); sin = Math.sin(yaw);
    [x, z] = [x * cos + z * sin, -x * sin + z * cos];
    return [x, y, z];
  };

  // Camera space to the screen: null when behind the eye.
  Kit.project = ([x, y, z], cx, cy, focal) => (z <= 1 ? null : [cx + x / z * focal, cy - y / z * focal, focal / z]);

  Kit.wire = function wire(ctx, model, {at = [0, 0, 0], yaw = 0, pitch = 0, roll = 0, scale = 1, cx, cy, focal,
    colour = "#54e39a", width = 1.4, blur = 6, fill = null} = {}) {
    const points = model.points.map((point) => {
      const [x, y, z] = Kit.rotate(point.map((value) => value * scale), yaw, pitch, roll);
      return Kit.project([x + at[0], y + at[1], z + at[2]], cx, cy, focal);
    });
    if (fill && model.faces) {
      ctx.fillStyle = fill;
      for (const face of model.faces) {
        const corners = face.map((index) => points[index]);
        if (corners.some((point) => !point)) continue;
        ctx.beginPath();
        corners.forEach(([x, y], index) => (index ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        ctx.closePath();
        ctx.fill();
      }
    }
    ctx.beginPath();
    for (const [a, b] of model.edges) {
      const p = points[a], q = points[b];
      if (!p || !q) continue;
      ctx.moveTo(p[0], p[1]);
      ctx.lineTo(q[0], q[1]);
    }
    ctx.strokeStyle = colour;
    ctx.lineWidth = width;
    ctx.shadowColor = colour;
    ctx.shadowBlur = blur;
    ctx.stroke();
    ctx.shadowBlur = 0;
    return points;
  };
})();
