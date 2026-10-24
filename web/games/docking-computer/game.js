// Docking Computer (5.6.3): the original's famous moment. A spinning
// station ahead, its slot turning with it: match the roll, line up, throttle
// down and fly through. Too fast or off-angle and you scrape and lose
// shields. Wireframe and green on black, as it was in 1984.
(() => {
  "use strict";

  const W = 600, H = 675, VIEW = 520, FOCAL = 460;
  const R = 500;                       // station radius, metres
  const SLOT = {w: 130, h: 40};        // half sizes
  const SHIP = {w: 26, h: 9};
  const SAFE_SPEED = 110;              // m/s through the slot
  const {clamp, between, chance} = Kit;
  const colours = {bg: "#000300", panel: "#020a03", accent: "#54ff7a", orange: "#ffb347", text: "#b8ffc8",
    muted: "#62c47a", dim: "#2f7a43", green: "#54ff7a", yellow: "#e8ff6a", red: "#ff5a4a"};
  const LINE = () => colours.accent;

  const cab = Kit.cabinet({width: W, height: H, colours, crt: true, start: startGame, update, draw, report, end: debugOver, card,
    onPause: () => waltz.stop()});
  const {ctx} = cab;
  const {text, glow} = cab.draw;
  const pointer = cab.input.pointer;

  // ---- The stations, built from their vertices; edges are the shortest pairs. ----
  function edgesOf(points, faces) {
    let shortest = Infinity;
    for (let a = 0; a < points.length; a += 1) for (let b = a + 1; b < points.length; b += 1) shortest = Math.min(shortest, dist(points[a], points[b]));
    const edges = [];
    for (let a = 0; a < points.length; a += 1) for (let b = a + 1; b < points.length; b += 1) if (dist(points[a], points[b]) < shortest * 1.02) edges.push([a, b]);
    return {points, edges, faces};
  }
  function dist(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }
  function scaleTo(points, radius) {
    const most = Math.max(...points.map((p) => Math.hypot(...p)));
    return points.map((p) => p.map((v) => v / most * radius));
  }

  const CORIOLIS = (() => {
    const points = [];
    for (const [i, j] of [[0, 1], [0, 2], [1, 2]]) {
      for (const a of [-1, 1]) for (const b of [-1, 1]) { const p = [0, 0, 0]; p[i] = a; p[j] = b; points.push(p); }
    }
    return {...edgesOf(scaleTo(points, R)), front: R / Math.SQRT2, name: "CORIOLIS"};
  })();

  const DODEC = (() => {
    const phi = (1 + Math.sqrt(5)) / 2, inv = 1 / phi;
    let points = [];
    for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) points.push([x, y, z]);
    for (const a of [-1, 1]) for (const b of [-1, 1]) points.push([0, a * inv, b * phi], [a * inv, b * phi, 0], [a * phi, 0, b * inv]);
    // Turn it so a face looks at you: face centres point like (0, ±1, ±phi).
    const tilt = Math.atan2(1, phi);
    points = points.map(([x, y, z]) => [x, y * Math.cos(tilt) - z * Math.sin(tilt), y * Math.sin(tilt) + z * Math.cos(tilt)]);
    points = scaleTo(points, R);
    const front = -Math.min(...points.map((p) => p[2]));
    return {...edgesOf(points), front: front * .985, name: "DODECAHEDRON"};
  })();

  const OCELLUS = (() => {
    const points = [], edges = [];
    const rings = 5, around = 10;
    for (let i = 1; i <= rings; i += 1) {
      const lat = -Math.PI / 2 + i * Math.PI / (rings + 1);
      for (let j = 0; j < around; j += 1) {
        const lon = j / around * Math.PI * 2;
        points.push([Math.cos(lat) * Math.cos(lon) * R, Math.cos(lat) * Math.sin(lon) * R, Math.sin(lat) * R]);
      }
    }
    for (let i = 0; i < rings; i += 1) {
      for (let j = 0; j < around; j += 1) {
        const here = i * around + j;
        edges.push([here, i * around + (j + 1) % around]);
        if (i < rings - 1) edges.push([here, here + around]);
      }
    }
    // The docking port's collar round the front.
    return {points, edges, front: Math.sin(Math.PI / 2 - Math.PI / (rings + 1)) * R * .96, name: "OCELLUS"};
  })();

  const TRAFFIC = edgesOf([[0, 0, 30], [-26, 0, -18], [26, 0, -18], [-14, 7, -18], [14, 7, -18], [-14, -5, -18], [14, -5, -18]].map(([x, y, z]) => [x, y, -z]));
  TRAFFIC.edges = [[0, 1], [0, 2], [1, 3], [3, 4], [4, 2], [1, 5], [5, 6], [6, 2], [0, 3], [0, 4], [0, 5], [0, 6]];

  const run = {score: 0, level: 0, shields: 3, docks: 0, scrapes: 0, banner: null, flash: 0};
  let station = null, traffic = [], stars = [];
  let me = null;

  // The Blue Danube's waltz (Strauss, public domain), while you're lined up.
  const waltz = (() => {
    const tune = [[62, 66, 69, 69, null, null, 81, null, 81, 78, null, 78], [62, 66, 69, 69, null, null, 81, null, 81, 79, null, 79],
      [61, 64, 71, 71, null, null, 83, null, 83, 79, null, 79], [61, 64, 71, 71, null, null, 83, null, 83, 78, null, 78]].flat();
    const bass = [[50, 57, 57], [50, 57, 57], [50, 57, 57], [50, 57, 57], [45, 55, 55], [45, 55, 55], [45, 55, 55], [45, 55, 55]];
    return cab.sound.track({bpm: 168, step: 1, parts: [
      {wave: "triangle", level: .09, notes: tune, hold: 1.4},
      {wave: "sine", level: .07, notes: [...bass, ...bass].flat()},
    ]});
  })();

  const sfx = {
    scrape() { cab.sound.hiss(.6, .7, 2600); cab.sound.tone("sawtooth", 300, 80, .5, .2); },
    bump() { cab.sound.hiss(.4, .5, 1200); },
    docked() { [523, 659, 784, 1047, 1319].forEach((f, i) => cab.sound.tone("square", f, f, .12, .12, i * .08)); },
    blip() { cab.sound.tone("square", 1200, 1200, .04, .05); },
    boom() { cab.sound.hiss(1.2, .9, 900); cab.sound.tone("sawtooth", 120, 30, 1, .3); },
  };

  function startGame() {
    Object.assign(run, {score: 0, level: 0, shields: 3, docks: 0, scrapes: 0, banner: null, flash: 0});
    pointer.active = false;
    stars = Array.from({length: 120}, () => [between(-1, 1) * 5000, between(-1, 1) * 5000, between(3000, 9000)]);
    nextStation();
  }

  function nextStation() {
    run.level += 1;
    const model = run.level <= 2 ? CORIOLIS : run.level <= 4 ? DODEC : OCELLUS;
    station = {model, spin: between(0, Math.PI * 2), rate: (.22 + run.level * .05) * (chance(.5) ? 1 : -1), z: 3200};
    me = {x: between(-220, 220), y: between(-160, 160), vx: 0, vy: 0, roll: 0, speed: 240, throttle: .8, drift: [0, 0], clock: 0, lined: false};
    traffic = [];
    run.banner = {text: model.name, sub: `STATION ${Kit.pad(run.level)} · ${Math.abs(station.rate * 57.3).toFixed(0)}°/S ${station.rate > 0 ? "ANTICLOCKWISE" : "CLOCKWISE"}`, t: 160};
  }

  // The slot's turn against yours, folded to ±90° (it's the same slot upside down).
  function rollError() {
    let diff = (station.spin - me.roll) % Math.PI;
    if (diff > Math.PI / 2) diff -= Math.PI;
    if (diff < -Math.PI / 2) diff += Math.PI;
    return diff;
  }

  function inSlotFrame() {
    const a = -station.spin;
    return [me.x * Math.cos(a) - me.y * Math.sin(a), me.x * Math.sin(a) + me.y * Math.cos(a)];
  }

  function lined() {
    const [u, v] = inSlotFrame();
    return Math.abs(rollError()) < .14 && Math.abs(u) < SLOT.w - SHIP.w && Math.abs(v) < SLOT.h * 2.5;
  }

  function update() {
    for (const star of stars) { star[2] -= (me?.speed || 60) / 60 * .2; if (star[2] < 1000) star[2] += 8000; }
    if (cab.state !== "play") { if (waltz.playing) waltz.stop(); return; }
    if (run.banner && --run.banner.t <= 0) run.banner = null;
    if (run.flash > 0) run.flash -= 1;
    const dt = 1 / 60;
    me.clock += dt;
    station.spin += station.rate * dt;

    // Steering (arrows or the mouse), roll, throttle.
    let sx = (cab.input.held("ArrowRight") ? 1 : 0) - (cab.input.held("ArrowLeft") ? 1 : 0);
    let sy = (cab.input.held("ArrowUp") ? 1 : 0) - (cab.input.held("ArrowDown") ? 1 : 0);
    if (sx || sy) pointer.active = false;
    else if (pointer.active && pointer.y < VIEW) {
      sx = clamp((pointer.x - W / 2) / 160, -1, 1);
      sy = clamp((VIEW / 2 - pointer.y) / 160, -1, 1);
    }
    const roll = (cab.input.held("KeyD", "KeyE") ? 1 : 0) - (cab.input.held("KeyA", "KeyQ") ? 1 : 0)
      + (pointer.down ? (pointer.button === 2 ? -1 : 1) : 0);
    me.roll += clamp(roll, -1, 1) * 1.1 * dt;
    if (cab.input.held("KeyW")) me.throttle = Math.min(1, me.throttle + .01);
    if (cab.input.held("KeyS")) me.throttle = Math.max(0, me.throttle - .01);
    const target = me.throttle * 300;
    me.speed += (target - me.speed) * .02;

    // Your steering is in your own frame, so it turns with your roll.
    const cos = Math.cos(me.roll), sin = Math.sin(me.roll);
    me.vx += (sx * cos - sy * sin) * 2.2 * dt * 60 * .08;
    me.vy += (sx * sin + sy * cos) * 2.2 * dt * 60 * .08;
    // Station-keeping wobble: it never sits still.
    if (chance(.02)) me.drift = [between(-1, 1) * (8 + run.level * 4), between(-1, 1) * (8 + run.level * 4)];
    me.vx += me.drift[0] * dt * .4;
    me.vy += me.drift[1] * dt * .4;
    me.vx *= .96;
    me.vy *= .96;
    me.x += me.vx;
    me.y += me.vy;
    station.z -= me.speed * dt;

    // The waltz plays while you're lined up.
    const nowLined = lined() && station.z < 2600;
    if (nowLined !== me.lined) { me.lined = nowLined; if (nowLined) { sfx.blip(); waltz.play(); } else waltz.stop(); }

    // Ships leaving the slot.
    if (run.level >= 2 && station.z > 600 && chance(.004 + run.level * .0012) && traffic.length < 2) {
      traffic.push({z: station.z + station.model.front * 0, x: 0, y: 0, vz: between(140, 220), spin: station.spin, drift: [between(-1, 1) * 30, between(-1, 1) * 30]});
      run.banner = {text: "TRAFFIC LEAVING THE SLOT", t: 90, small: true};
    }
    for (const ship of traffic) {
      ship.z -= (ship.vz + me.speed) * dt;
      ship.x += ship.drift[0] * dt;
      ship.y += ship.drift[1] * dt;
      if (!ship.hit && ship.z < 40 && ship.z > -40 && Math.hypot(ship.x - me.x, ship.y - me.y) < 70) {
        ship.hit = true;
        hurt("COLLISION");
      }
    }
    traffic = traffic.filter((ship) => ship.z > -200);

    if (station.z <= station.model.front * 0 + 0) arrive();
  }

  function hurt(reason) {
    run.shields -= 1;
    run.scrapes += 1;
    run.flash = 24;
    if (run.shields < 0) {
      sfx.boom();
      run.reason = reason;
      return cab.over({score: run.score, level: run.level, rank: Kit.rank(run.score, .4)});
    }
    sfx.scrape();
    run.banner = {text: reason, sub: run.shields > 0 ? `SHIELDS ${run.shields}/3` : "SHIELDS GONE · HULL NEXT", t: 120, bad: true};
  }

  function arrive() {
    const [u, v] = inSlotFrame();
    const angle = Math.abs(rollError());
    const fits = Math.abs(u) < SLOT.w - SHIP.w && Math.abs(v) < SLOT.h - SHIP.h + 6 && angle < .2;
    if (fits && me.speed <= SAFE_SPEED) {
      waltz.stop();
      const time = Math.max(0, 90 - me.clock) * 15;
      const smooth = Math.max(0, SAFE_SPEED - me.speed) * 5;
      const points = Math.round((1000 + time + smooth + Math.max(0, run.shields) * 250) * run.level);
      run.score += points;
      run.docks += 1;
      sfx.docked();
      run.banner = {text: "DOCKED", sub: `${Math.round(me.clock)} S · ${Math.round(me.speed)} M/S AT THE SLOT · +${points.toLocaleString()}`, t: 170, good: true};
      run.shields = Math.min(3, run.shields + 1);
      nextStation();
      run.banner.sub2 = run.banner.sub;
      return;
    }
    // Bounced off the face: back out to try again.
    hurt(!fits ? (angle >= .2 ? "SCRAPED: NOT MATCHING ROLL" : "SCRAPED: MISSED THE SLOT") : "SCRAPED: TOO FAST");
    if (cab.state !== "play") return;
    station.z = 700;
    me.speed = 30;
    me.throttle = .1;
  }

  // ---- Drawing. ----
  function toScreen([x, y, z]) {
    // World → your view: you're at the origin, rolled.
    const cos = Math.cos(-me.roll), sin = Math.sin(-me.roll);
    const rx = x * cos - y * sin, ry = x * sin + y * cos;
    if (z <= 5) return null;
    return [W / 2 + rx / z * FOCAL, VIEW / 2 - ry / z * FOCAL];
  }

  function stationPoint([x, y, z]) {
    const cos = Math.cos(station.spin), sin = Math.sin(station.spin);
    return [x * cos - y * sin - me.x, x * sin + y * cos - me.y, z + station.z + station.model.front];
  }

  function drawStation() {
    const model = station.model;
    const points = model.points.map((p) => toScreen(stationPoint(p)));
    ctx.beginPath();
    for (const [a, b] of model.edges) {
      const p = points[a], q = points[b];
      if (!p || !q) continue;
      ctx.moveTo(p[0], p[1]);
      ctx.lineTo(q[0], q[1]);
    }
    ctx.strokeStyle = LINE();
    ctx.lineWidth = 1.3;
    glow(LINE(), 6);
    ctx.stroke();
    // The slot, on the face towards you.
    const slot = [[-SLOT.w, -SLOT.h], [SLOT.w, -SLOT.h], [SLOT.w, SLOT.h], [-SLOT.w, SLOT.h]]
      .map(([x, y]) => toScreen(stationPoint([x, y, -model.front])));
    if (slot.every(Boolean)) {
      ctx.beginPath();
      slot.forEach(([x, y], i) => ctx[i ? "lineTo" : "moveTo"](x, y));
      ctx.closePath();
      ctx.fillStyle = "#000000";
      ctx.fill();
      ctx.strokeStyle = me.lined ? colours.yellow : LINE();
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    ctx.shadowBlur = 0;
  }

  function drawTraffic() {
    for (const ship of traffic) {
      const points = TRAFFIC.points.map(([x, y, z]) => {
        const cos = Math.cos(ship.spin), sin = Math.sin(ship.spin);
        return toScreen([x * cos - y * sin + ship.x - me.x, x * sin + y * cos + ship.y - me.y, z + ship.z]);
      });
      ctx.beginPath();
      for (const [a, b] of TRAFFIC.edges) {
        const p = points[a], q = points[b];
        if (!p || !q) continue;
        ctx.moveTo(p[0], p[1]);
        ctx.lineTo(q[0], q[1]);
      }
      ctx.strokeStyle = colours.yellow;
      ctx.lineWidth = 1.3;
      ctx.stroke();
    }
  }

  function drawDashboard() {
    const top = VIEW;
    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, top, W, H - top);
    ctx.strokeStyle = colours.dim;
    ctx.lineWidth = 1.5;
    ctx.strokeRect(1, top + 1, W - 2, H - top - 2);
    // The scanner: where the slot's axis is against you.
    const cx = W / 2, cy = top + 78;
    ctx.beginPath();
    ctx.ellipse(cx, cy, 120, 44, 0, 0, Math.PI * 2);
    ctx.strokeStyle = colours.dim;
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx - 120, cy); ctx.lineTo(cx + 120, cy); ctx.moveTo(cx, cy - 44); ctx.lineTo(cx, cy + 44);
    ctx.stroke();
    const [px, py] = (() => {
      const cos = Math.cos(-me.roll), sin = Math.sin(-me.roll);
      return [-(me.x * cos - me.y * sin), -(me.x * sin + me.y * cos)];
    })();
    const dot = [cx + clamp(px / 400, -1, 1) * 112, cy - clamp(py / 400, -1, 1) * 40];
    ctx.fillStyle = me.lined ? colours.yellow : colours.accent;
    ctx.fillRect(dot[0] - 3, dot[1] - 3, 6, 6);
    ctx.beginPath(); ctx.moveTo(dot[0], dot[1]); ctx.lineTo(dot[0], cy); ctx.strokeStyle = colours.accent; ctx.stroke();

    const bars = [["SPD", me.speed / 300, me.speed > SAFE_SPEED && station.z < 900 ? colours.red : colours.accent],
      ["THR", me.throttle, colours.accent], ["SH", Math.max(0, run.shields) / 3, run.shields <= 0 ? colours.red : colours.accent]];
    bars.forEach(([label, value, tone], index) => {
      const y = top + 26 + index * 22;
      text(label, 18, y + 7, 10, colours.muted, "left");
      cab.draw.bar(48, y, 110, 8, value, tone, "rgba(84,255,122,.08)");
    });
    // Roll match: the slot's angle against yours.
    const error = rollError();
    text("ROLL", W - 160, top + 33, 10, colours.muted, "left");
    ctx.strokeStyle = colours.dim;
    ctx.strokeRect(W - 120, top + 26, 100, 8);
    ctx.fillStyle = Math.abs(error) < .14 ? colours.yellow : colours.accent;
    ctx.fillRect(W - 70 + clamp(error / (Math.PI / 2), -1, 1) * 48 - 3, top + 24, 6, 12);
    text(`${Math.round(station.z)} M`, W - 20, top + 60, 14, colours.text, "right");
    text(`${Math.round(me.speed)} M/S`, W - 20, top + 80, 12, me.speed > SAFE_SPEED ? colours.orange : colours.text, "right");
    text(me.lined ? "LINED UP" : "", W - 20, top + 100, 11, colours.yellow, "right");
    text(`SCORE ${Kit.pad(run.score, 6)}`, 18, top + 108, 11, colours.text, "left");
    text(`BEST ${Kit.pad(Math.max(cab.best, run.score), 6)}`, 18, top + 126, 10, colours.muted, "left");
    text(`STATION ${Kit.pad(run.level)}`, W - 20, top + 126, 10, colours.muted, "right");
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 8, 8, colours.dim);
  }

  function draw() {
    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, 0, W, H);
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, W, VIEW);
    ctx.clip();
    if (me) {
      ctx.fillStyle = colours.muted;
      for (const star of stars) {
        const p = toScreen([star[0], star[1], star[2]]);
        if (p) ctx.fillRect(p[0], p[1], 1.4, 1.4);
      }
      if (station) drawStation();
      drawTraffic();
      // The sight in the middle of the view.
      ctx.strokeStyle = colours.accent;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(W / 2 - 24, VIEW / 2); ctx.lineTo(W / 2 - 8, VIEW / 2);
      ctx.moveTo(W / 2 + 8, VIEW / 2); ctx.lineTo(W / 2 + 24, VIEW / 2);
      ctx.moveTo(W / 2, VIEW / 2 - 24); ctx.lineTo(W / 2, VIEW / 2 - 8);
      ctx.moveTo(W / 2, VIEW / 2 + 8); ctx.lineTo(W / 2, VIEW / 2 + 24);
      ctx.stroke();
    }
    if (run.flash > 0) { ctx.fillStyle = `rgba(255, 90, 74, ${run.flash / 60})`; ctx.fillRect(0, 0, W, VIEW); }
    const banner = run.banner;
    if (banner && cab.state === "play") {
      ctx.globalAlpha = clamp(banner.t / 30, 0, 1);
      const tone = banner.good ? colours.yellow : banner.bad ? colours.red : colours.text;
      if (banner.small) text(banner.text, W / 2, 60, 14, colours.yellow);
      else {
        text(banner.text, W / 2, 70, 28, tone, "center", 700, Kit.MONO);
        if (banner.sub) text(banner.sub, W / 2, 94, 11, colours.muted);
      }
      ctx.globalAlpha = 1;
    }
    ctx.restore();
    if (me) drawDashboard();
    if (cab.state === "title") {
      cab.draw.shade("#000000", .55, W, H);
      text("DOCKING", W / 2, 150, 50, colours.accent, "center", 700, Kit.MONO);
      text("COMPUTER", W / 2, 204, 50, colours.text, "center", 700, Kit.MONO);
      text("A VOID COMPASS ARCADE CABINET", W / 2, 236, 11, colours.muted);
      const rows = [["MATCH THE STATION'S ROLL", "A D"], ["LINE UP ON THE SLOT", "ARROWS / MOUSE"], ["UNDER 110 M/S AT THE SLOT", "W S / WHEEL"],
        ["MOUSE BUTTONS", "ROLL RIGHT · LEFT"]];
      rows.forEach(([label, value], index) => {
        text(label, W / 2 - 200, 300 + index * 30, 12, colours.muted, "left");
        text(value, W / 2 + 200, 300 + index * 30, 12, colours.text, "right");
      });
      text("CORIOLIS · DODECAHEDRON · OCELLUS", W / 2, 440, 11, colours.yellow);
      if (Math.floor(cab.tick / 30) % 2) text("PRESS SPACE OR CLICK TO LAUNCH", W / 2, 500, 15, colours.text);
      text("P PAUSE · M SOUND · C SCREEN", W / 2, 530, 9, colours.dim);
    } else if (cab.state === "over") {
      cab.overScreen({heading: "SHIP DESTROYED", tone: colours.red, sub: run.reason || "", rank: Kit.rank(run.score, .4),
        lines: [["SCORE", run.score.toLocaleString()], ["STATIONS DOCKED", run.docks], ["SCRAPES", run.scrapes]]});
    }
  }

  cab.canvas.addEventListener("wheel", (event) => {
    if (cab.state !== "play") return;
    event.preventDefault();
    me.throttle = clamp(me.throttle - Math.sign(event.deltaY) * .05, 0, 1);
  }, {passive: false});

  function report() {
    return {score: run.score, level: run.level, shields: run.shields, z: station?.z ?? 0, speed: me?.speed ?? 0, lined: Boolean(me?.lined),
      station: station?.model.name ?? ""};
  }

  function debugOver() {
    run.score += 1234;
    run.shields = 0;
    hurt("TEST");
  }

  function card() {
    startGame();
    station.z = 1300;
    station.spin = .5;
    me.roll = .44;
    me.x = 30;
    me.y = -12;
    me.speed = 150;
    run.score = 4380;
    run.banner = null;
    traffic.push({z: 700, x: 120, y: 60, vz: 0, spin: .4, drift: [0, 0]});
  }

  window.dockingComputer = {state: () => ({...report(), state: cab.state}),
    // For tests: put you in the slot's path, lined up and slow.
    _line() { me.x = 0; me.y = 0; me.roll = station.spin; station.rate = 0; me.speed = 60; me.throttle = .2; station.z = 50; }};
})();
