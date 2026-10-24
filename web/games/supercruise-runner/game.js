// Supercruise Runner (5.6.3): a race to the station in supercruise, drawn
// like an 80s road racer. Keep the speed up, steer round the stars, planets
// and traffic, and be in the blue zone for the last seven seconds or you
// overshoot. Every drop buys more time.
(() => {
  "use strict";

  const W = 600, H = 675;
  const HORIZON = 262, FOCAL = 300, CAMERA = 100, NEAR = CAMERA * FOCAL / (H - HORIZON), FAR = 3200, LANE = 80;
  const TOP_SPEED = 300;           // c
  const BLUE = [.55, .72];         // the throttle's blue zone
  const DROP_AT = 25;              // Ls: close enough to drop
  const {clamp, between, chance, pick} = Kit;
  const colours = {bg: "#0a0216", panel: "#160a2a", accent: "#29e6ff", orange: "#ff8a3d", text: "#f3e9ff",
    muted: "#b9a6d6", dim: "#7a6898", green: "#54e39a", yellow: "#ffd166", red: "#ff4f7b"};
  const PINK = "#ff3fa4", VIOLET = "#9b5cff";
  const STATIONS = ["VANCE RING", "OKAFOR PORT", "LINDQVIST HUB", "MOREAU ORBITAL", "HALDANE GATEWAY", "IKEDA DOCK",
    "BRANNIGAN STATION", "NAKAMURA TERMINAL", "OYELARAN HIGH", "SOLBERG REACH"];

  const cab = Kit.cabinet({width: W, height: H, colours, crt: true, start: startGame, update, draw, report, end: debugOver,
    card, onPause: () => tune.stop(), onResume: () => tune.play()});
  const {ctx} = cab;
  const {text, glow} = cab.draw;
  const pointer = cab.input.pointer;

  const run = {score: 0, leg: 0, time: 0, hull: 100, distance: 0, legLength: 1, throttle: 0, speed: 0, track: 0,
    x: 0, bank: 0, flash: 0, banner: null, perfect: 0, overshoots: 0, flown: 0, dropping: 0};
  let hazards = [], nextHazard = 0, offsets = new Float32Array(1);
  const stars = Array.from({length: 90}, () => ({x: Math.random() * W, y: Math.random() * HORIZON * .92, z: Math.random()}));

  // A synthwave loop: bass, arpeggio and a lead over Am F C G.
  const tune = (() => {
    const roots = [45, 41, 48, 43];
    const bass = [], arp = [], lead = [];
    const melody = [69, null, 72, null, 76, null, 74, 72, 69, null, null, 67, 69, null, 72, null];
    roots.forEach((root, bar) => {
      const third = [3, 4, 4, 4][bar];
      for (let step = 0; step < 16; step += 1) {
        bass.push(step % 2 ? null : root + (step % 4 === 2 ? 12 : 0));
        arp.push(root + 24 + [0, third, 7, 12][step % 4]);
        lead.push(bar % 2 ? melody[(step + 8) % 16] : melody[step]);
      }
    });
    return cab.sound.track({bpm: 116, step: .25, parts: [
      {wave: "sawtooth", level: .05, notes: bass, hold: 1.6},
      {wave: "square", level: .018, notes: arp},
      {wave: "triangle", level: .07, notes: lead, hold: 1.8},
    ]});
  })();

  const sfx = {
    bump() { cab.sound.hiss(.3, .5, 1200); cab.sound.tone("square", 160, 70, .2, .2); },
    heat() { cab.sound.hiss(1, .7, 3000); cab.sound.tone("sawtooth", 300, 40, .9, .25); },
    well() { cab.sound.tone("sine", 220, 40, 1.1, .3); },
    drop() { [523, 659, 784, 1047, 1319].forEach((f, i) => cab.sound.tone("triangle", f, f, .14, .2, i * .07)); },
    overshoot() { cab.sound.tone("sawtooth", 620, 120, .7, .2); },
    warn() { cab.sound.tone("square", 990, 990, .08, .08); },
  };

  function curveAt(s) {
    return .00026 * Math.sin(s / 1400) + .00017 * Math.sin(s / 610 + 1.3) + .00008 * Math.sin(s / 260 + run.leg);
  }

  function startGame() {
    Object.assign(run, {score: 0, leg: 0, time: 50, hull: 100, throttle: .9, speed: 120, track: 0, x: 0, bank: 0, flash: 0,
      banner: null, perfect: 0, overshoots: 0, flown: 0, dropping: 0});
    pointer.active = false;
    nextLeg();
    tune.restart();
    tune.play();
  }

  function nextLeg() {
    run.leg += 1;
    run.legLength = 3200 + run.leg * 1400;
    run.distance = run.legLength;
    hazards = [];
    nextHazard = run.track + 900;
    run.banner = {text: STATIONS[(run.leg - 1) % STATIONS.length], sub: `DESTINATION ${run.leg} · ${Math.round(run.legLength).toLocaleString()} LS`, t: 150};
  }

  function topSpeed() {
    return Math.max(30, Math.min(TOP_SPEED, run.distance / 4.2));
  }

  function eta() {
    return run.speed > 0 ? run.distance / run.speed : 99;
  }

  function inBlue() {
    return run.throttle >= BLUE[0] && run.throttle <= BLUE[1];
  }

  function spawn(s) {
    const roll = Math.random(), late = Math.min(run.leg, 6);
    if (roll < .45) hazards.push({kind: "ship", s, x: between(-60, 60), r: 14, drift: between(.25, .55), hue: pick([PINK, colours.accent, colours.yellow])});
    else if (roll < .78) hazards.push({kind: "planet", s, x: pick([-1, 1]) * between(30, 110), r: between(48, 78), hue: pick(["#ff9f43", "#5fd4ff", "#c38bff", "#7bed9f"]), ring: chance(.4)});
    else hazards.push({kind: "star", s, x: pick([-1, 1]) * between(late > 2 ? 40 : 130, 210), r: 64, hue: pick(["#fff3b0", "#ffd28a", "#a8d8ff"])});
  }

  function hurt(hazard) {
    hazard.hit = true;
    if (hazard.kind === "ship") {
      run.speed *= .5;
      run.hull -= 5;
      run.flash = 10;
      say("BUMPED · WATCH THE TRAFFIC", colours.orange);
      sfx.bump();
    } else if (hazard.kind === "planet") {
      run.speed *= .15;
      run.time -= 3;
      say("GRAVITY WELL · SLOWED", colours.accent);
      sfx.well();
    } else {
      run.speed = 0;
      run.hull -= 25;
      run.time -= 6;
      run.flash = 30;
      say("EMERGENCY DROP · TOO CLOSE TO THE STAR", colours.red);
      sfx.heat();
    }
    if (run.hull <= 0) finish("SHIP DESTROYED");
  }

  function say(text, colour) {
    run.banner = {text, colour, t: 110, small: true};
  }

  function finish(reason) {
    run.reason = reason;
    tune.stop();
    cab.over({score: Math.round(run.score), wave: run.leg, rank: Kit.rank(run.score, 1, "explore")});
  }

  function update() {
    for (const star of stars) {
      star.x -= (run.bank * 1.2 + curveAt(run.track) * 2000) * (.3 + star.z);
      if (star.x < 0) star.x += W;
      if (star.x > W) star.x -= W;
    }
    if (cab.state !== "play") return;
    const step = 1 / 60;
    run.time -= step;
    if (run.banner && --run.banner.t <= 0) run.banner = null;
    if (run.flash > 0) run.flash -= 1;
    if (run.time <= 0) { run.time = 0; finish("TIME UP"); return; }

    // Throttle and steering.
    if (cab.input.held(...Kit.UP)) run.throttle = Math.min(1, run.throttle + .012);
    if (cab.input.held(...Kit.DOWN)) run.throttle = Math.max(0, run.throttle - .012);
    let steer = (cab.input.held(...Kit.RIGHT) ? 1 : 0) - (cab.input.held(...Kit.LEFT) ? 1 : 0);
    if (steer) pointer.active = false;
    else if (pointer.active) steer = clamp((pointer.x - W / 2) / (W * .3), -1, 1);
    const target = run.throttle * topSpeed();
    run.speed += (target - run.speed) * .03;
    const flow = 3 + run.speed / TOP_SPEED * 19;
    run.track += flow;
    run.x += steer * 2.6 - curveAt(run.track + 120) * flow * 150;
    run.x = clamp(run.x, -260, 260);
    run.bank += (steer - run.bank) * .15;
    // Off the nav lane: dust and drag.
    if (Math.abs(run.x) > LANE) run.speed *= .995;
    run.distance = Math.max(0, run.distance - run.speed * step);
    run.flown += run.speed * step;
    run.score += run.speed * step;

    // The last seven seconds: be in the blue zone.
    if (eta() < 7 && run.distance > DROP_AT && !inBlue() && cab.tick % 20 === 0) sfx.warn();
    if (run.distance <= DROP_AT) {
      if (run.throttle > BLUE[1]) {
        run.overshoots += 1;
        run.distance = 400 + (run.throttle - BLUE[1]) * 2400;
        run.time -= 4;
        say("OVERSHOOT · LOOPING BACK", colours.red);
        sfx.overshoot();
      } else {
        const perfect = inBlue();
        const bonus = 2000 * run.leg + (perfect ? 3000 : 0) + Math.round(run.time) * 20;
        run.score += bonus;
        if (perfect) run.perfect += 1;
        run.time += 26 + Math.min(run.leg, 6) * 2;
        sfx.drop();
        nextLeg();
        run.banner = {text: perfect ? "PERFECT DROP" : "DROPPED", sub: `+${bonus.toLocaleString()} · NEXT: ${STATIONS[(run.leg - 1) % STATIONS.length]}`,
          t: 160, colour: perfect ? colours.accent : colours.text};
      }
    }

    // What's ahead.
    while (nextHazard < run.track + FAR) {
      spawn(nextHazard);
      nextHazard += Math.max(520, 1400 - run.leg * 110) * between(.7, 1.3);
    }
    for (const hazard of hazards) {
      if (hazard.kind === "ship") hazard.s += flow * hazard.drift;
      const z = hazard.s - run.track;
      if (!hazard.hit && z < NEAR + 12 && z > NEAR - 24 && Math.abs(hazard.x - run.x) < hazard.r * (hazard.kind === "ship" ? 1 : .8) + 14) hurt(hazard);
    }
    hazards = hazards.filter((hazard) => hazard.s - run.track > NEAR - 40);
  }

  // ---- Drawing. ----
  function offsetsAhead() {
    const count = Math.ceil((FAR - NEAR) / 10) + 2;
    if (offsets.length !== count) offsets = new Float32Array(count);
    let off = 0, dx = 0;
    for (let i = 0; i < count; i += 1) {
      offsets[i] = off;
      dx += curveAt(run.track + NEAR + i * 10) * 10;
      off += dx * 10;
    }
  }

  function offsetAt(z) {
    const index = clamp((z - NEAR) / 10, 0, offsets.length - 1);
    const low = Math.floor(index), k = index - low;
    return offsets[low] * (1 - k) + (offsets[Math.min(offsets.length - 1, low + 1)] || 0) * k;
  }

  function screenOf(z, x) {
    const scale = FOCAL / z;
    return [W / 2 + (offsetAt(z) + x - run.x) * scale, HORIZON + CAMERA * scale, scale];
  }

  function drawSky() {
    const sky = ctx.createLinearGradient(0, 0, 0, HORIZON);
    sky.addColorStop(0, "#07021a");
    sky.addColorStop(.6, "#2a0845");
    sky.addColorStop(1, "#ff3f8e");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, W, HORIZON);
    for (const star of stars) {
      ctx.globalAlpha = .3 + star.z * .6;
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(star.x, star.y, star.z > .7 ? 2 : 1, star.z > .7 ? 2 : 1);
    }
    ctx.globalAlpha = 1;
    // The destination's star: a striped synthwave sun that grows as you close in.
    const near = 1 - clamp(run.distance / Math.max(1, run.legLength), 0, 1);
    const r = 70 + near * 40;
    const cx = W / 2 + offsetAt(FAR) * FOCAL / FAR - run.x * .05, cy = HORIZON - 18;
    const sun = ctx.createLinearGradient(0, cy - r, 0, cy + r);
    sun.addColorStop(0, "#ffe66d");
    sun.addColorStop(.55, "#ff6fb5");
    sun.addColorStop(1, "#b13cff");
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, W, HORIZON);
    ctx.clip();
    glow("#ff6fb5", 40);
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = sun;
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.fillStyle = "#2a0845";
    for (let i = 0; i < 6; i += 1) {
      const y = cy + r * (.1 + i * .16);
      ctx.fillRect(cx - r, y, r * 2, 2 + i * 1.6);
    }
    // The station against it, a little wire ring.
    const size = 8 + near * 30;
    ctx.strokeStyle = colours.accent;
    ctx.lineWidth = 1.5;
    glow(colours.accent, 10);
    ctx.beginPath();
    ctx.ellipse(cx, cy - r * .2, size, size * .35, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx, cy - r * .2 - size * .5);
    ctx.lineTo(cx, cy - r * .2 + size * .5);
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.restore();
  }

  function drawGround() {
    ctx.fillStyle = "#0d0320";
    ctx.fillRect(0, HORIZON, W, H - HORIZON);
    let lastY = H;
    for (let y = H; y > HORIZON + 1; y -= 2) {
      const z = CAMERA * FOCAL / (y - HORIZON);
      if (z > FAR) break;
      const scale = FOCAL / z;
      const cx = W / 2 + (offsetAt(z) - run.x) * scale;
      const half = LANE * scale;
      const band = Math.floor((z + run.track) / 120) % 2;
      // The nav lane, and its neon edges.
      ctx.fillStyle = band ? "#1b0a3a" : "#160832";
      ctx.fillRect(cx - half, y - 2, half * 2, lastY - y + 2);
      const edge = Math.max(1, half * .06);
      ctx.fillStyle = band ? PINK : "#ff7ac6";
      ctx.fillRect(cx - half - edge, y - 2, edge, 2);
      ctx.fillRect(cx + half, y - 2, edge, 2);
      if (band && z < 1600) {
        ctx.fillStyle = "rgba(41, 230, 255, .55)";
        ctx.fillRect(cx - edge * .6, y - 2, edge * 1.2, 2);
      }
      // The grid's cross lines.
      if (Math.floor((z + run.track) / 120) !== Math.floor((z + 9 + run.track) / 120)) {
        ctx.fillStyle = `rgba(155, 92, 255, ${clamp(1.2 - z / FAR, .15, .8)})`;
        ctx.fillRect(0, y - 1, cx - half - edge, 1);
        ctx.fillRect(cx + half + edge, y - 1, W, 1);
      }
      lastY = y;
    }
    // The grid's long lines, converging on the horizon.
    ctx.strokeStyle = "rgba(155, 92, 255, .4)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = -10; i <= 10; i += 1) {
      if (Math.abs(i) < 2) continue;
      const [x1, y1] = screenOf(NEAR, i * 90);
      const [x2, y2] = screenOf(FAR, i * 90);
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
    }
    ctx.stroke();
    ctx.fillStyle = "#ff3f8e";
    ctx.fillRect(0, HORIZON, W, 1);
  }

  function drawHazard(hazard) {
    const z = hazard.s - run.track;
    if (z < NEAR - 20 || z > FAR) return;
    const [x, y, scale] = screenOf(z, hazard.x);
    const r = hazard.r * scale;
    const fade = clamp((FAR - z) / 600, 0, 1);
    ctx.globalAlpha = fade;
    if (hazard.kind === "ship") {
      const w = r * 1.6, h = r * .8, top = y - h * 1.6;
      glow(hazard.hue, 10);
      ctx.strokeStyle = hazard.hue;
      ctx.lineWidth = Math.max(1, scale * 2.4);
      ctx.fillStyle = "#12061f";
      ctx.beginPath();
      ctx.moveTo(x - w, top + h);
      ctx.lineTo(x, top);
      ctx.lineTo(x + w, top + h);
      ctx.lineTo(x, top + h * .7);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = colours.orange;
      ctx.fillRect(x - w * .3, top + h * .75, w * .6, Math.max(1, h * .18));
      ctx.shadowBlur = 0;
    } else if (hazard.kind === "planet") {
      const cy = y - r;
      const body = ctx.createRadialGradient(x - r * .35, cy - r * .35, r * .1, x, cy, r);
      body.addColorStop(0, hazard.hue);
      body.addColorStop(1, "#14052a");
      ctx.beginPath();
      ctx.arc(x, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = body;
      ctx.fill();
      if (hazard.ring) {
        ctx.strokeStyle = "rgba(255, 220, 255, .6)";
        ctx.lineWidth = Math.max(1, r * .06);
        ctx.beginPath();
        ctx.ellipse(x, cy, r * 1.7, r * .35, -.2, 0, Math.PI * 2);
        ctx.stroke();
      }
    } else {
      const cy = y - r * 1.2;
      glow(hazard.hue, 40 * Math.min(1, scale * 2) + 10);
      ctx.beginPath();
      ctx.arc(x, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = hazard.hue;
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.globalAlpha = fade * .25;
      ctx.beginPath();
      ctx.arc(x, cy, r * 1.6, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function drawShip() {
    const x = W / 2, y = H - 92;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(run.bank * .18);
    const flame = 8 + run.speed / TOP_SPEED * 20 + Math.random() * 6;
    ctx.fillStyle = colours.accent;
    glow(colours.accent, 18);
    ctx.fillRect(-26, 14, 12, flame * .6);
    ctx.fillRect(14, 14, 12, flame * .6);
    ctx.shadowBlur = 0;
    ctx.beginPath();
    ctx.moveTo(-70, 18);
    ctx.lineTo(-20, -20);
    ctx.lineTo(20, -20);
    ctx.lineTo(70, 18);
    ctx.lineTo(30, 24);
    ctx.lineTo(-30, 24);
    ctx.closePath();
    ctx.fillStyle = "#1a0a30";
    ctx.fill();
    glow(PINK, 12);
    ctx.strokeStyle = PINK;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.beginPath();
    ctx.moveTo(-16, -14);
    ctx.lineTo(16, -14);
    ctx.lineTo(10, -2);
    ctx.lineTo(-10, -2);
    ctx.closePath();
    ctx.fillStyle = "rgba(41, 230, 255, .5)";
    ctx.fill();
    ctx.restore();
  }

  function drawHud() {
    cab.scoreBar(Math.round(run.score), "DROP", run.leg);
    if (cab.state === "title") return;
    // The time, big, Out-Run style.
    const tone = run.time < 10 ? colours.red : colours.yellow;
    text("TIME", W / 2, 66, 10, colours.dim);
    glow(tone, 12);
    text(String(Math.ceil(run.time)), W / 2, 100, 34, tone, "center", 700, Kit.DISPLAY);
    ctx.shadowBlur = 0;

    // The speed gauge with its blue zone.
    const gx = W - 46, gy = H - 250, gh = 200, gw = 18;
    ctx.fillStyle = "rgba(255,255,255,.06)";
    ctx.fillRect(gx, gy, gw, gh);
    ctx.fillStyle = "rgba(41, 120, 255, .45)";
    ctx.fillRect(gx, gy + gh * (1 - BLUE[1]), gw, gh * (BLUE[1] - BLUE[0]));
    ctx.fillStyle = inBlue() ? colours.accent : run.throttle > BLUE[1] ? colours.orange : colours.text;
    ctx.fillRect(gx - 6, gy + gh * (1 - run.throttle) - 2, gw + 12, 4);
    ctx.strokeStyle = colours.dim;
    ctx.strokeRect(gx + .5, gy + .5, gw - 1, gh - 1);
    text("THR", gx + gw / 2, gy - 8, 9, colours.dim);

    const seconds = eta();
    const close = seconds < 7 && run.distance > DROP_AT;
    text(`${Math.round(run.speed)} c`, gx - 14, gy + gh - 4, 13, colours.text, "right");
    text(`${Math.round(run.distance).toLocaleString()} Ls`, 18, H - 52, 15, colours.text, "left");
    text(`ETA ${seconds >= 99 ? "--" : `00:${String(Math.min(99, Math.round(seconds))).padStart(2, "0")}`}`, 18, H - 30, 13, close ? colours.accent : colours.muted, "left");
    if (close && !inBlue() && Math.floor(cab.tick / 12) % 2) {
      text(run.throttle > BLUE[1] ? "TOO FAST · THROTTLE INTO THE BLUE" : "THROTTLE INTO THE BLUE ZONE", W / 2, H - 22, 13, colours.orange);
    }
    // The hull.
    text("HULL", 18, 68, 9, colours.dim, "left");
    cab.draw.bar(18, 74, 90, 5, run.hull / 100, run.hull < 35 ? colours.red : colours.green);
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 6, 8, colours.dim);
  }

  function drawBanner() {
    const banner = run.banner;
    if (!banner || cab.state !== "play") return;
    ctx.globalAlpha = clamp(banner.t / 30, 0, 1);
    if (banner.small) text(banner.text, W / 2, 168, 16, banner.colour || colours.text, "center", 700, Kit.DISPLAY);
    else {
      glow(banner.colour || colours.accent, 16);
      text(banner.text, W / 2, 170, 30, banner.colour || colours.text, "center", 700, Kit.DISPLAY);
      ctx.shadowBlur = 0;
      if (banner.sub) text(banner.sub, W / 2, 194, 11, colours.accent);
    }
    ctx.globalAlpha = 1;
  }

  function draw() {
    offsetsAhead();
    drawSky();
    drawGround();
    hazards.slice().sort((a, b) => b.s - a.s).forEach(drawHazard);
    if (cab.state !== "title") drawShip();
    if (run.flash > 0) {
      ctx.fillStyle = `rgba(255, 80, 120, ${run.flash / 60})`;
      ctx.fillRect(0, 0, W, H);
    }
    drawHud();
    drawBanner();
    if (cab.state === "title") {
      cab.titleScreen({top: "SUPERCRUISE", bottom: "RUNNER", tone: PINK, y: 190,
        rows: [["DROP AT THE STATION", "+2,000 × DROP"], ["IN THE BLUE ZONE", "+3,000"], ["TOO FAST", "OVERSHOOT"]],
        note: "STARS, PLANETS AND TRAFFIC ON THE LANE · EACH DROP BUYS TIME",
        how: "← → OR MOUSE TO STEER · ↑ ↓ OR WHEEL FOR THROTTLE"});
    } else if (cab.state === "over") {
      cab.overScreen({heading: run.reason || "TIME UP", tone: run.reason === "SHIP DESTROYED" ? colours.red : colours.yellow,
        sub: "FLIGHT DEBRIEF", rankLabel: "EXPLORER RANK", rank: Kit.rank(run.score, 1, "explore"),
        lines: [["SCORE", Math.round(run.score).toLocaleString()], ["STATIONS REACHED", run.leg - 1], ["PERFECT DROPS", run.perfect],
          ["OVERSHOOTS", run.overshoots], ["DISTANCE FLOWN", `${Math.round(run.flown).toLocaleString()} LS`]]});
    }
  }

  cab.canvas.addEventListener("wheel", (event) => {
    if (cab.state !== "play") return;
    event.preventDefault();
    run.throttle = clamp(run.throttle - Math.sign(event.deltaY) * .05, 0, 1);
  }, {passive: false});

  function report() {
    return {score: Math.round(run.score), leg: run.leg, time: run.time, speed: run.speed, throttle: run.throttle, distance: run.distance, hazards: hazards.length};
  }

  function debugOver() {
    run.score += 1234;
    finish("TIME UP");
  }

  function card() {
    startGame();
    tune.stop();
    run.leg = 2;
    run.legLength = 6000;
    run.distance = 2400;
    run.time = 38;
    run.score = 12840;
    run.throttle = .64;
    run.speed = 240;
    hazards = [];
    nextHazard = run.track + 300;
    for (let i = 0; i < 70; i += 1) { cab.tick += 1; update(); }
    run.banner = null;
    run.x = 18;
    run.bank = -.4;
    run.speed = 240;
    hazards = hazards.filter((hazard) => hazard.s - run.track > 1400);
    hazards.push({kind: "planet", s: run.track + 620, x: -170, r: 72, hue: "#5fd4ff", ring: true},
      {kind: "ship", s: run.track + 380, x: 46, r: 14, drift: .4, hue: colours.yellow},
      {kind: "ship", s: run.track + 900, x: -30, r: 14, drift: .4, hue: PINK},
      {kind: "star", s: run.track + 1200, x: 230, r: 64, hue: "#fff3b0"});
  }

  window.supercruiseRunner = {state: () => ({...report(), state: cab.state})};
})();
