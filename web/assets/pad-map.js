// Where your landing pad is (5.8.6), drawn the same on the Bridge's pad card and
// the Nav HUD: a starport's ring of pads, a carrier's deck, or at a surface
// station the pads known there around you, ahead up, with yours lit.
// window.VoidPadMap.svg(map, className) gives the SVG markup ("" with no map).
(function () {
  const fixed = (value) => Number(value).toFixed(1);

  function starport(map, css) {
    const dots = (map.pads || []).map(([sector, depth, place, count], index) => {
      const angle = (sector * 30 + (place - (count + 1) / 2) * 7) * Math.PI / 180;
      const r = 18 + depth * 11;
      const on = index + 1 === map.pad;
      return `<circle cx="${fixed(50 + r * Math.sin(angle))}" cy="${fixed(50 - r * Math.cos(angle))}" r="${on ? 4 : 2.2}" class="${on ? "pm-pad-on" : "pm-pad"}"/>`;
    }).join("");
    return `<svg class="${css}" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="48" class="pm-ring"/><rect x="44" y="94" width="12" height="5" class="pm-slot"/>${dots}</svg>`;
  }

  function carrier(map, css) {
    const boxes = map.pads || [];
    const xs = boxes.flatMap(([x, , w]) => [x, x + w]);
    const minX = Math.min(-30, ...xs) - 2, maxX = Math.max(30, ...xs) + 2;
    const outline = (map.outline || []).map(([x, y]) => `${x},${y}`).join(" ");
    const rects = boxes.map(([x, y, w, h], index) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" class="${index + 1 === map.pad ? "pm-pad-on" : "pm-pad"}"/>`).join("");
    return `<svg class="${css}" viewBox="${minX} -50 ${maxX - minX} 95" aria-hidden="true">${outline ? `<polygon points="${outline}" class="pm-ring"/>` : ""}${rects}</svg>`;
  }

  // Pads as [number, metres right, metres ahead] of you. The view is wide
  // enough for yours and at least 150 m; pads beyond it aren't drawn.
  function surface(map, css) {
    const pads = (map.pads || []).filter((row) => Array.isArray(row) && row.length >= 3);
    const mine = pads.find(([number]) => number === map.pad);
    const reach = Math.max(150, mine ? Math.hypot(mine[1], mine[2]) * 1.15 : 150);
    const scale = 42 / reach;
    const spot = ([, x, y]) => [50 + x * scale, 50 - y * scale];
    const others = pads.filter((row) => row !== mine).map((row) => {
      const [px, py] = spot(row);
      return Math.hypot(px - 50, py - 50) > 46 ? "" : `<circle cx="${fixed(px)}" cy="${fixed(py)}" r="2.2" class="pm-pad"/>`;
    }).join("");
    let target = "";
    if (mine) {
      const [px, py] = spot(mine);
      target = `<line x1="50" y1="50" x2="${fixed(px)}" y2="${fixed(py)}" class="pm-line"/>`
        + `<circle cx="${fixed(px)}" cy="${fixed(py)}" r="4.2" class="pm-pad-on"/>`
        + `<text x="${fixed(px)}" y="${fixed(py - 6.5)}" class="pm-label">${Number(map.pad)}</text>`;
    }
    // Ahead is up when the ship's heading is known; north is, otherwise.
    const north = map.heading_up ? "" : `<text x="50" y="9" class="pm-label pm-north">N</text>`;
    const ship = `<path d="M50 44.5 L54 54 L50 51.5 L46 54 Z" class="pm-ship"/>`;
    return `<svg class="${css}" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="48" class="pm-ring"/><circle cx="50" cy="50" r="24" class="pm-ring pm-ring-inner"/>${north}${others}${target}${ship}</svg>`;
  }

  function svg(map, css = "pad-map") {
    if (!map || typeof map !== "object") return "";
    if (map.kind === "starport") return starport(map, css);
    if (map.kind === "surface") return surface(map, css);
    if (Array.isArray(map.pads)) return carrier(map, css);
    return "";
  }

  window.VoidPadMap = {svg};
})();
