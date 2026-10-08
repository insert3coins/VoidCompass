(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "jump-info";
  const SVG = "http://www.w3.org/2000/svg";
  const PHASES = {charging: "CHARGING", hyperspace: "WITCH SPACE", arrival: "ARRIVED"};
  const dom = Object.fromEntries([
    "jump", "content", "phase", "star-orb", "system-name", "star-line", "jump-distance",
    "jump-ly", "route", "route-count", "route-line", "route-total", "lines",
  ].map((id) => [id, document.getElementById(id)]));
  let lastRoute = null;
  let shownKeys = new Set();
  let shownSystem = "";

  const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }
  function svg(tag, attributes) {
    const element = document.createElementNS(SVG, tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
    return element;
  }
  const ly = (value) => `${number(value).toLocaleString("en-GB", {minimumFractionDigits: 1, maximumFractionDigits: 1})}`;

  // The plotted route to scale, as SrvSurvey draws it: every hop's length in
  // proportion, the jump under way lit, scoopable stars capped with an arc.
  function drawRoute(route) {
    const line = dom["route-line"];
    const width = Math.max(40, Math.round(line.getBoundingClientRect().width));
    const height = Math.max(14, Math.round(line.getBoundingClientRect().height));
    const middle = height / 2 + 2;
    const pad = 6;
    line.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const segments = Array.isArray(route?.segments) ? route.segments : [];
    const known = segments.map((segment) => number(segment.ly, NaN)).filter(Number.isFinite);
    const average = known.length ? known.reduce((sum, value) => sum + value, 0) / known.length : 1;
    const lengths = segments.map((segment) => Math.max(.01, number(segment.ly, average)));
    const total = lengths.reduce((sum, value) => sum + value, 0) || 1;
    const span = width - pad * 2;
    const roomy = span / Math.max(1, segments.length) >= 9;
    const parts = [];
    let x = pad;
    const points = [{x, state: "start"}];
    segments.forEach((segment, index) => {
      const next = x + lengths[index] / total * span;
      parts.push(svg("line", {class: `seg ${segment.state}`, x1: x, y1: middle, x2: next, y2: middle}));
      points.push({x: next, segment, index});
      x = next;
    });
    for (const point of points) {
      const segment = point.segment;
      const state = !segment ? "behind" : segment.state;
      const target = segment?.state === "next";
      const here = !segment ? number(route.hop) === 1 : segments[point.index + 1]?.state === "next";
      if (roomy) {
        if (segment?.scoop) {
          parts.push(svg("path", {
            class: `scoop ${state}`,
            d: `M ${point.x - 6} ${middle - 5} A 7 7 0 0 1 ${point.x + 6} ${middle - 5}`,
          }));
        }
        const classes = ["dot", target ? "target" : here ? "here" : state === "behind" ? "" : "ahead",
          segment?.neutron ? "neutron" : ""].filter(Boolean).join(" ");
        parts.push(svg("circle", {class: classes, cx: point.x, cy: middle, r: target ? 4.5 : 3.5}));
      } else {
        const tall = target ? 7 : segment?.scoop ? 5 : 3;
        parts.push(svg("line", {
          class: `tick ${target ? "target" : state === "behind" ? "behind" : ""}`,
          x1: point.x, y1: middle - tall, x2: point.x, y2: middle + tall,
        }));
      }
    }
    line.replaceChildren(...parts);
  }

  // The Navigation HUD's star families (styles.css carries their tones).
  function starFamily(value) {
    const code = String(value || "").trim().toUpperCase().split("_")[0];
    if (!code) return "unknown";
    if (["H", "BH", "SUPERMASSIVEBLACKHOLE"].includes(code)) return "blackhole";
    if (["N", "NS"].includes(code)) return "neutron";
    if (code.startsWith("D")) return "dwarf";
    if (code === "TTS") return "tauri";
    if (code === "AEBE") return "a";
    if (code.startsWith("W")) return "wolf";
    if (code.startsWith("C")) return "carbon";
    if (code.startsWith("S")) return "m";
    if (code === "X") return "exotic";
    const primary = code[0].toLowerCase();
    return "obafgkmlty".includes(primary) ? primary : "unknown";
  }

  function lineNode(row, fresh) {
    const item = node("div", `line tone-${row.tone || "text"}${fresh ? " fresh" : ""}`);
    item.dataset.key = String(row.key || "");
    for (const part of Array.isArray(row.items) ? row.items : []) {
      // A count reads as the HUD's boxed counter; words as a label and value.
      const count = /^[\d,]+$/.test(String(part.value || ""));
      const span = node("span", count ? "count" : "pair");
      if (part.label) span.appendChild(node("small", "", part.label));
      span.appendChild(node("b", "", part.value || ""));
      item.appendChild(span);
    }
    if (row.source) item.appendChild(node("em", "source", row.source));
    return item;
  }

  // Fit the panel to the window it actually gets (as the Navigation HUD
  // does, 5.5.2.7). The text size asks for a zoom; the window is sized for it
  // from the design width and the height this page reports, but a window
  // that ends up smaller (a height cap, Windows display scaling, an older
  // WebView2 measuring zoom differently) cut the panel off. Now the zoom
  // never exceeds what fits, and the page keeps reporting the height the
  // full text size needs, so the window grows back towards it.
  const DESIGN_WIDTH = 560;
  let requestedScale = 1;
  let fittedScale = 1;

  function setScale(scale) {
    fittedScale = scale;
    document.documentElement.style.setProperty("--scale", scale.toFixed(4));
  }

  function fitToWindow() {
    let scale = requestedScale;
    if (innerWidth > 0) scale = Math.min(scale, innerWidth / DESIGN_WIDTH);
    setScale(Math.max(.4, scale));
    const height = dom.content.getBoundingClientRect().height + 2;
    if (innerHeight > 0 && height > innerHeight + 1) {
      setScale(Math.max(.4, fittedScale * innerHeight / height));
    }
    return fittedScale;
  }

  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(dom.jump, snapshot.theme || {}, snapshot.effects || {});
    requestedScale = Number(document.documentElement.style.getPropertyValue("--scale")) || 1;
    const model = snapshot.jump || {};
    const system = String(model.system || "");
    dom.jump.classList.toggle("empty", !system);
    if (!system) return;
    const phase = String(model.phase || "charging");
    dom.jump.dataset.phase = phase;
    dom.phase.textContent = PHASES[phase] || "NEXT JUMP";
    dom["system-name"].textContent = system.toUpperCase();
    dom["system-name"].title = system;

    const star = model.star;
    dom["star-orb"].className = `star-orb star-${starFamily(star?.class)}`;
    dom["star-line"].replaceChildren();
    if (star) {
      dom["star-line"].append(`CLASS ${String(star.class || "").toUpperCase()} · `);
      dom["star-line"].appendChild(node("span", `tone-${star.tone}`, star.label));
    } else {
      dom["star-line"].textContent = "STAR CLASS UNKNOWN";
    }

    const route = model.route;
    const jumpLy = route ? number(route.jump_ly, NaN) : NaN;
    dom["jump-distance"].hidden = !Number.isFinite(jumpLy);
    dom["jump-ly"].textContent = Number.isFinite(jumpLy) ? ly(jumpLy) : "";
    dom.route.hidden = !route;
    lastRoute = route || null;
    if (route) {
      dom["route-count"].textContent = `JUMP ${number(route.hop)} OF ${number(route.hops)}`;
      dom["route-total"].textContent = `${ly(route.total_ly)} LY`;
      dom["route-total"].title = route.destination ? `Route to ${route.destination}` : "";
      drawRoute(route);
    }

    // New lines (EDSM's answer arriving) slide in; a new target starts fresh.
    if (system !== shownSystem) shownKeys = new Set();
    const rows = Array.isArray(model.lines) ? model.lines : [];
    const fresh = system === shownSystem;
    dom.lines.replaceChildren(...rows.map((row) => lineNode(row, fresh && !shownKeys.has(row.key))));
    shownKeys = new Set(rows.map((row) => row.key));
    shownSystem = system;
    fitToWindow();
  }

  // The height the panel needs at the requested text size (not the shrunk
  // one), so the app sizes the window for the full text.
  function contentHeight() {
    const shown = dom.content.getBoundingClientRect().height + 2;
    return Math.ceil(shown * requestedScale / (fittedScale || 1));
  }

  window.addEventListener("resize", () => { if (!dom.jump.classList.contains("empty")) fitToWindow(); });
  window.__jumpFit = () => ({requested: requestedScale, fitted: fittedScale});

  new ResizeObserver(() => { if (lastRoute && !dom.route.hidden) drawRoute(lastRoute); }).observe(dom["route-line"]);
  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 250});
})();
