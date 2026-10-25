(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "expedition";
  const dom = Object.fromEntries(["expedition", "name", "share", "bar", "distance", "steps", "planet", "target-step", "target-name",
    "target-sub", "facts", "strip", "strip-canvas", "compass", "needle", "target-distance", "target-detail", "hint", "detour", "figures",
    "warnings"].map((id) => [id, document.getElementById(id)]));
  // From html_expedition_overlay.py: the width and least height the window is sized from.
  const DESIGN_WIDTH = 380, MIN_HEIGHT = 120;

  const number = (value, fallback = 0) => Number.isFinite(Number(value)) && value !== null ? Number(value) : fallback;
  const known = (value) => value !== null && value !== undefined && Number.isFinite(Number(value));
  const whole = (value) => Math.round(number(value)).toLocaleString("en-GB");
  const credits = (value) => {
    const v = number(value);
    return v >= 1e9 ? `${(v / 1e9).toFixed(2)} BN CR` : v >= 1e6 ? `${(v / 1e6).toFixed(1)} M CR` : `${whole(v)} CR`;
  };
  const metres = (value) => number(value) >= 1000
    ? `${(number(value) / 1000).toLocaleString("en-GB", {minimumFractionDigits: 1, maximumFractionDigits: 1})} KM` : `${whole(value)} M`;
  const upper = (value) => String(value || "").toUpperCase();

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  function figure(label, value, tone = "") {
    const box = node("div", `figure${tone ? ` ${tone}` : ""}`);
    box.append(node("small", "", label), node("b", "", value));
    return box;
  }

  // A body's look by its type: [light, dark, band] (a ring for gas giants).
  const LOOKS = [
    [/earth/i, ["#7fd0ff", "#1b5fae", "#3fa860"]], [/water/i, ["#7ab8ff", "#123d8a", ""]], [/ammonia/i, ["#e9d27a", "#7a5a18", ""]],
    [/high metal/i, ["#e0a878", "#5a3a22", ""]], [/metal rich/i, ["#c9b090", "#3e3226", ""]], [/rocky ice/i, ["#d8e4ee", "#5a6878", ""]],
    [/icy/i, ["#eef7ff", "#7896b4", ""]], [/rocky/i, ["#c2aa92", "#4a3c30", ""]], [/gas giant|giant/i, ["#f2c48a", "#8a4a20", "#d89a5a"]],
  ];
  const lookOf = (kind) => (LOOKS.find(([match]) => match.test(String(kind || ""))) || [0, ["#a8b4c0", "#3a4450", ""]])[1];
  const STEPS = {body: [["jump", "JUMP"], ["fly", "FLY"], ["land", "LAND"], ["arrived", "ARRIVE"]], system: [["jump", "JUMP"], ["arrived", "ARRIVE"]]};
  const STEP_WORDS = {jump: "JUMP TO", fly: "FLY TO", land: "LAND ON", ground: "ON THE GROUND", arrived: "YOU'RE HERE"};

  // The body (or, before you've jumped, the star) to aim for.
  function drawPlanet(guide) {
    const canvas = dom.planet, ctx = canvas.getContext("2d"), size = canvas.width, c = size / 2;
    ctx.clearRect(0, 0, size, size);
    if (!guide) return;
    const star = guide.stage === "jump";
    const info = guide.info || {};
    const [light, dark, band] = star ? ["#fff6d0", "#ffb040", ""] : lookOf(info.class || "");
    const r = size * .34;
    const halo = ctx.createRadialGradient(c, c, r * .6, c, c, r * 1.5);
    halo.addColorStop(0, star ? "rgba(255, 210, 120, .55)" : "rgba(120, 220, 255, .22)");
    halo.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = halo;
    ctx.fillRect(0, 0, size, size);
    const body = ctx.createRadialGradient(c - r * .4, c - r * .45, r * .1, c, c, r);
    body.addColorStop(0, light);
    body.addColorStop(1, dark);
    ctx.fillStyle = body;
    ctx.beginPath();
    ctx.arc(c, c, r, 0, Math.PI * 2);
    ctx.fill();
    if (band && !star) {
      ctx.save();
      ctx.beginPath(); ctx.arc(c, c, r, 0, Math.PI * 2); ctx.clip();
      ctx.globalAlpha = .35;
      ctx.fillStyle = band;
      for (const y of [-.35, .05, .4]) ctx.fillRect(c - r, c + y * r, r * 2, r * .16);
      ctx.restore();
    }
    if (!star) {
      // The night side.
      const night = ctx.createLinearGradient(c - r, c - r, c + r, c + r);
      night.addColorStop(.45, "rgba(0, 0, 0, 0)");
      night.addColorStop(1, "rgba(0, 0, 0, .55)");
      ctx.fillStyle = night;
      ctx.beginPath(); ctx.arc(c, c, r, 0, Math.PI * 2); ctx.fill();
    }
    if (info.rings && !star) {
      ctx.strokeStyle = "rgba(230, 210, 170, .7)";
      ctx.lineWidth = size * .025;
      ctx.beginPath(); ctx.ellipse(c, c, r * 1.45, r * .38, -.35, 0, Math.PI * 2); ctx.stroke();
    }
    // A target ring once you're on it.
    if (["land", "ground", "arrived"].includes(guide.stage)) {
      ctx.strokeStyle = guide.stage === "arrived" ? "#4ee59b" : "#00d1ff";
      ctx.lineWidth = size * .03;
      ctx.setLineDash([size * .06, size * .045]);
      ctx.beginPath(); ctx.arc(c, c, r * 1.22, 0, Math.PI * 2); ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  // The system's bodies by distance from the arrival star, yours ringed.
  function drawStrip(guide) {
    const canvas = dom["strip-canvas"], ratio = window.devicePixelRatio || 1, box = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(box.width * ratio)), height = Math.max(1, Math.round(box.height * ratio));
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, box.width, box.height);
    const bodies = guide.bodies || [];
    const far = Math.max(1, ...bodies.map((row) => number(row.ls)));
    const x = (ls) => 10 + Math.log10(1 + number(ls)) / Math.log10(1 + far) * (box.width - 20);
    const y = box.height * .42;
    ctx.strokeStyle = "rgba(133, 147, 157, .35)";
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(6, y); ctx.lineTo(box.width - 6, y); ctx.stroke();
    for (const row of bodies) {
      const [light] = row.star ? ["#ffd27a"] : lookOf(row.class);
      ctx.fillStyle = light;
      ctx.globalAlpha = row.target ? 1 : .55;
      ctx.beginPath(); ctx.arc(x(row.ls), y, row.star ? 4.5 : row.target ? 4 : 2.6, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
    const target = bodies.find((row) => row.target);
    if (target) {
      const tx = x(target.ls);
      ctx.strokeStyle = "#00d1ff";
      ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(tx, y, 8, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = "#00d1ff";
      ctx.font = '700 9px Bahnschrift, "Segoe UI", sans-serif';
      ctx.textAlign = tx > box.width - 50 ? "right" : tx < 50 ? "left" : "center";
      ctx.fillText(target.short, tx, box.height - 2);
    }
  }

  function chip(text, tone = "") {
    return node("span", tone, text);
  }

  function renderGuide(model) {
    const guide = model.guide;
    const surface = model.surface || {};
    if (!guide) {
      // Every leg reached (or an older model): the trip's end.
      dom.steps.replaceChildren();
      dom["target-step"].textContent = model.next ? `NEXT STOP · ${model.next.kind}` : "EVERY LEG REACHED";
      dom["target-name"].textContent = model.next ? upper(model.next.name) : "HOME AND DRY";
      dom["target-sub"].textContent = model.next ? upper(model.next.where) : "";
      dom.facts.hidden = dom.strip.hidden = dom.compass.hidden = dom.hint.hidden = true;
      drawPlanet(null);
      return;
    }
    const body = Boolean(guide.body);
    const stage = guide.stage === "ground" ? "land" : guide.stage;
    const steps = STEPS[body ? "body" : "system"];
    const at = steps.findIndex(([key]) => key === stage);
    dom.steps.replaceChildren(...steps.map(([key, label], index) => node("li", index < at ? "done" : index === at ? "now" : "", label)));

    const info = guide.info;
    dom["target-step"].textContent = `${STEP_WORDS[guide.stage] || "NEXT STOP"}${guide.kind === "destination" ? " · DESTINATION" : guide.kind === "home" ? " · HOME" : ""}`;
    dom["target-name"].textContent = guide.stage === "jump" ? upper(guide.system) : guide.stage === "arrived" || guide.stage === "ground"
      ? upper(guide.title) : upper(guide.short || guide.system);
    const sub = [];
    if (guide.stage === "jump") {
      sub.push(known(guide.jumps) ? `${whole(guide.jumps)} JUMP${number(guide.jumps) === 1 ? "" : "S"} TO GO` : "PLOT IT IN THE GALAXY MAP");
      if (body) sub.push(`THEN LAND ON ${guide.short}`);
    } else if (body && guide.title && upper(guide.title) !== upper(guide.short) && guide.stage !== "arrived" && guide.stage !== "ground") {
      sub.push(upper(guide.title));
    } else if (guide.stage === "ground" || guide.stage === "arrived") {
      if (body) sub.push(`ON ${guide.short}`);
    }
    dom["target-sub"].textContent = sub.join(" · ");
    dom["target-sub"].hidden = !sub.length;
    drawPlanet(guide);

    // What the body is, from your scans.
    const facts = [];
    if (info) {
      if (info.class) facts.push(chip(upper(info.class.replace(/ body$/i, ""))));
      if (known(info.ls)) facts.push(chip(`${whole(info.ls)} LS`));
      if (known(info.gravity)) facts.push(chip(`${number(info.gravity).toFixed(2)} G`, info.gravity > 2 ? "red" : info.gravity > 1.2 ? "yellow" : ""));
      if (known(info.temp)) facts.push(chip(`${whole(info.temp)} K`, info.temp > 800 ? "red" : info.temp < 100 ? "yellow" : ""));
      facts.push(chip(info.atmosphere ? upper(info.atmosphere) : "NO ATMOSPHERE", info.atmosphere ? "green" : ""));
      if (!info.landable) facts.push(chip("NOT LANDABLE", "red"));
      if (info.footfall) facts.push(chip(`FOOTFALL ${upper(info.footfall)}`, info.footfall === "LIKELY OPEN" ? "green" : ""));
      if (info.source === "EDSM") facts.push(chip("EDSM CATALOGUE"));
    }
    dom.facts.replaceChildren(...facts);
    dom.facts.hidden = !facts.length;

    dom.strip.hidden = !(guide.stage === "fly" && (guide.bodies || []).length > 1);
    if (!dom.strip.hidden) drawStrip(guide);

    const target = surface.target;
    dom.compass.hidden = !(target && (guide.stage === "land" || guide.stage === "ground"));
    if (!dom.compass.hidden) {
      dom.needle.style.setProperty("--turn", `${number(target.turn)}deg`);
      dom.needle.classList.toggle("unknown", !known(target.turn));
      dom["target-distance"].textContent = target.arrived ? "HERE" : metres(target.distance_m);
      dom["target-detail"].textContent = [`BEARING ${String(Math.round(number(target.bearing)) % 360).padStart(3, "0")}°`,
        known(surface.altitude_m) && number(surface.altitude_m) > 0 ? `ALT ${metres(surface.altitude_m)}` : ""].filter(Boolean).join(" · ");
    }

    // What to do next, in one line.
    const spot = known(guide.lat) && known(guide.lon) ? `${number(guide.lat).toFixed(4)}, ${number(guide.lon).toFixed(4)}` : "";
    const hint = {
      jump: "",
      fly: info ? `TARGET ${guide.short} IN THE NAV PANEL${known(info.ls) ? ` · ${whole(info.ls)} LS` : ""}` : `SCAN THE SYSTEM TO FIND ${guide.short}`,
      land: spot ? `LAND AT ${spot}` : "LAND ANYWHERE ON IT",
      ground: spot ? `HEAD FOR ${spot}` : "",
      arrived: "",
    }[guide.stage] || "";
    dom.hint.textContent = hint;
    dom.hint.hidden = !hint;
  }

  function render(snapshot = {}) {
    const root = dom.expedition;
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
    VoidCompassOverlay.fitToWindow(root, DESIGN_WIDTH, snapshot.effects || {});
    const model = snapshot.expedition || null;
    root.classList.toggle("empty", !model);
    if (!model) return;
    root.classList.toggle("over", Boolean(model.risk_over));
    dom.name.textContent = upper(model.name);
    const share = known(model.share) ? Math.max(0, Math.min(1, number(model.share))) : null;
    dom.share.textContent = share === null ? "" : `${Math.round(share * 100)}%`;
    dom.bar.style.setProperty("--share", `${share === null ? 0 : (share * 100).toFixed(1)}%`);
    dom.distance.textContent = [known(model.to_go_ly) && number(model.to_go_ly) > 0 ? `${whole(model.to_go_ly)} LY TO GO` : "",
      known(model.done_ly) && number(model.done_ly) > 0 ? `${whole(model.done_ly)} LY FLOWN` : ""].filter(Boolean).join(" · ") || "PLACE THE LEGS TO MEASURE IT";

    renderGuide(model);
    const detour = model.detour;
    dom.detour.textContent = detour
      ? `WORTH A DETOUR · ${upper(detour.system)} · ${upper(detour.body)} · ${upper(detour.reason)}${known(detour.distance_ly) ? ` · ${whole(detour.distance_ly)} LY AWAY` : ""}`
      : "";
    dom.detour.hidden = !detour;

    dom.figures.replaceChildren(
      figure("DATA AT RISK", model.risk ? credits(model.risk) : "—", model.risk_over ? "red" : "yellow"),
      figure("STREAK", `${whole(model.streak)} JUMPS`),
      figure("ETA", known(model.eta_hours) ? `${whole(model.eta_hours)} H` : "—"),
      figure("HULL", known(model.hull) ? `${Math.round(number(model.hull))}%` : "—"));
    const warnings = [
      ...(model.fuel_runs || []).map((run) => node("span", "warn", `NO STAR TO SCOOP: ${run.jumps} NEUTRON JUMPS FROM ${upper(run.from)}`)),
      ...((model.low || []).length ? [node("span", "warn", `RUNNING LOW · ${model.low.map(upper).join(" · ")}`)] : []),
      ...(model.ironman ? [node("span", "danger", "IRONMAN · ONE LIFE")] : []),
    ];
    dom.warnings.replaceChildren(...warnings);
    dom.warnings.hidden = !warnings.length;
  }

  function contentHeight() {
    return VoidCompassOverlay.designHeight(dom.expedition, MIN_HEIGHT);
  }

  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 250});
})();
