// Pod Rescue (5.6.3): a side-scrolling patrol over a settlement, after the
// 80s classic. Thargoid Scouts come down and snatch escape pods off the
// ground; shoot one carrying a pod and catch the pod before it hits the
// ground. A pod carried off the top is lost, and its Scout comes back as a
// hunter. Shock mines clear the screen.
(() => {
  "use strict";

  const W = 600, H = 675, WORLD = W * 5, GROUND = H - 70, TOP = 92;
  const {clamp, between, chance, pick, wrap} = Kit;
  const colours = {bg: "#03050a", panel: "#0b1220", accent: "#00d1ff", orange: "#ff8a3d", text: "#e6eef5",
    muted: "#97a8b6", dim: "#5d6f7e", green: "#54e39a", yellow: "#f5c76d", red: "#ff6b70"};
  const CAUSTIC = "#8dffb8", SCOUT = "#b48cff", HUNTER = "#ff5fd2";

  const cab = Kit.cabinet({width: W, height: H, colours, start: startGame, update, draw, report, end: debugOver, card, key});
  const {ctx} = cab;
  const {text, glow} = cab.draw;
  const pointer = cab.input.pointer;

  const run = {score: 0, wave: 0, lives: 3, mines: 3, rescued: 0, lost: 0, kills: 0, banner: null, flash: 0, quake: 0, clearing: 0};
  let ship = null, camera = 0, pods = [], scouts = [], shots = [], bolts = [], sparks = [], words = [], queue = 0, spawnClock = 0;
  const stars = Array.from({length: 120}, () => ({x: between(0, WORLD), y: between(TOP, GROUND - 120), z: between(.2, 1)}));
  const hills = Array.from({length: 40}, (_, i) => ({x: i * WORLD / 40, h: between(30, 90)}));

  const sfx = {
    shoot() { cab.sound.tone("square", 1500, 500, .05, .08); },
    pop() { cab.sound.hiss(.25, .45, 2600); cab.sound.tone("triangle", 330, 70, .16, .18); },
    grab() { cab.sound.tone("sawtooth", 300, 700, .4, .1); },
    catch() { [659, 880, 1175].forEach((f, i) => cab.sound.tone("square", f, f, .08, .12, i * .06)); },
    lost() { cab.sound.tone("sawtooth", 600, 120, .7, .14); },
    mine() { cab.sound.hiss(1.2, .9, 4000); cab.sound.tone("sine", 900, 40, 1, .3); },
    hit() { cab.sound.hiss(.9, .8, 1000); cab.sound.tone("sawtooth", 500, 40, .8, .3); },
    thrust() { cab.sound.hiss(.06, .07, 500); },
  };

  function key(code) {
    if (cab.state === "play" && ["KeyB", "KeyX", "ShiftLeft", "ShiftRight"].includes(code)) { shockMine(); return true; }
    return false;
  }

  function startGame() {
    Object.assign(run, {score: 0, wave: 0, lives: 3, mines: 3, rescued: 0, lost: 0, kills: 0, banner: null, flash: 0, quake: 0, clearing: 0});
    ship = {x: WORLD / 2, y: H / 2, vx: 0, vy: 0, face: 1, cool: 0, guard: 120, carrying: null};
    camera = ship.x - W / 2;
    pods = Array.from({length: 10}, (_, i) => ({x: (i + .5) * WORLD / 10 + between(-60, 60), y: GROUND - 6, state: "ground", vy: 0}));
    pointer.active = false;
    nextWave();
  }

  function nextWave() {
    run.wave += 1;
    queue = 8 + run.wave * 3;
    spawnClock = 60;
    shots = []; bolts = [];
    // A pod or two back on the ground each wave, if any are left to save.
    if (run.wave > 1 && pods.length < 10) for (let i = 0; i < 2 && pods.length < 10; i += 1) pods.push({x: between(0, WORLD), y: GROUND - 6, state: "ground", vy: 0});
    run.banner = {text: `WAVE ${Kit.pad(run.wave)}`, sub: `${queue} SCOUTS · ${pods.length} PODS ON THE GROUND`, t: 140};
  }

  // Positions wrap round the world; this is the shortest way from a to b.
  const toward = (a, b) => { let d = b - a; if (d > WORLD / 2) d -= WORLD; if (d < -WORLD / 2) d += WORLD; return d; };
  const screenX = (x) => wrap(x - camera + W / 2, WORLD) - W / 2;

  function spawnScout(hunter = false, x = null) {
    const at = x ?? wrap(ship.x + pick([-1, 1]) * between(W * .7, WORLD / 2), WORLD);
    scouts.push({x: at, y: hunter ? between(TOP + 20, GROUND - 200) : TOP + 10, vx: 0, vy: 0, hunter, target: null, cool: between(60, 160), flash: 0, wobble: between(0, 6)});
  }

  function fire() {
    if (ship.cool > 0) return;
    shots.push({x: ship.x + ship.face * 20, y: ship.y + 2, vx: ship.face * 15 + ship.vx, life: 34});
    ship.cool = 7;
    sfx.shoot();
  }

  function shockMine() {
    if (!ship || ship.dead || run.mines <= 0) return;
    run.mines -= 1;
    run.flash = 24;
    run.quake = 16;
    sfx.mine();
    for (const scout of scouts) if (Math.abs(screenX(scout.x)) < W / 2 + 20) kill(scout);
    bolts = [];
  }

  function burst(x, y, palette, count, speed = 3) {
    for (let i = 0; i < count; i += 1) {
      const a = between(0, Math.PI * 2), v = between(.5, speed);
      sparks.push({x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: between(20, 45), colour: pick(palette)});
    }
  }

  function say(x, y, value, colour) {
    words.push({x, y, text: value, colour, life: 60});
  }

  function kill(scout) {
    scout.dead = true;
    run.kills += 1;
    const points = scout.hunter ? 250 : scout.target ? 200 : 150;
    run.score += points;
    burst(scout.x, scout.y, [scout.hunter ? HUNTER : SCOUT, CAUSTIC, "#ffffff"], 24, 3.5);
    say(scout.x, scout.y - 14, String(points), colours.text);
    sfx.pop();
    // Its pod drops: catch it before it lands too hard.
    if (scout.target && scout.target.state === "carried") {
      scout.target.state = "falling";
      scout.target.vy = 0;
      scout.target.from = scout.target.y;
    }
  }

  function hurtShip() {
    if (ship.guard > 0 || ship.dead) return;
    ship.dead = true;
    ship.respawn = 120;
    run.lives -= 1;
    run.quake = 22;
    burst(ship.x, ship.y, [colours.accent, colours.orange, "#ffffff"], 50, 5);
    if (ship.carrying) { ship.carrying.state = "falling"; ship.carrying.vy = 0; ship.carrying.from = ship.y; ship.carrying = null; }
    sfx.hit();
  }

  function finish() {
    cab.over({score: run.score, wave: run.wave, rank: Kit.rank(run.score, .4)});
  }

  function update() {
    for (const spark of sparks) { spark.x += spark.vx; spark.y += spark.vy; spark.vy += .03; spark.life -= 1; }
    sparks = sparks.filter((spark) => spark.life > 0);
    for (const word of words) { word.y -= .5; word.life -= 1; }
    words = words.filter((word) => word.life > 0);
    if (cab.state !== "play") return;
    if (run.banner && --run.banner.t <= 0) run.banner = null;
    if (run.flash > 0) run.flash -= 1;
    if (run.quake > 0) run.quake -= 1;

    if (ship.dead) {
      if (--ship.respawn <= 0) {
        if (run.lives <= 0) return finish();
        Object.assign(ship, {dead: false, y: H / 2, vx: 0, vy: 0, guard: 140});
      }
    } else moveShip();
    camera = wrap(camera + toward(camera, ship.x + ship.face * W * .18) * .08, WORLD);

    if (queue > 0 && --spawnClock <= 0) {
      spawnScout();
      queue -= 1;
      spawnClock = Math.max(40, 130 - run.wave * 10) * between(.6, 1.3);
    }

    for (const shot of shots) {
      shot.x = wrap(shot.x + shot.vx, WORLD);
      shot.life -= 1;
      for (const scout of scouts) {
        if (!scout.dead && Math.abs(toward(shot.x, scout.x)) < 18 && Math.abs(shot.y - scout.y) < 14) { kill(scout); shot.life = 0; break; }
      }
    }
    shots = shots.filter((shot) => shot.life > 0);
    moveScouts();
    movePods();
    for (const bolt of bolts) {
      bolt.x = wrap(bolt.x + bolt.vx, WORLD);
      bolt.y += bolt.vy;
      bolt.life -= 1;
      if (!ship.dead && Math.abs(toward(bolt.x, ship.x)) < 12 && Math.abs(bolt.y - ship.y) < 9) { bolt.life = 0; hurtShip(); }
    }
    bolts = bolts.filter((bolt) => bolt.life > 0 && bolt.y > TOP && bolt.y < GROUND);
    scouts = scouts.filter((scout) => !scout.dead);

    if (!queue && !scouts.length) {
      if (!run.clearing) {
        run.clearing = 130;
        const saved = pods.filter((pod) => pod.state === "ground").length;
        const bonus = saved * 100 * run.wave;
        run.score += bonus;
        run.mines = Math.min(5, run.mines + 1);
        run.banner = {text: "WAVE CLEARED", sub: `${saved} PODS SAFE × ${100 * run.wave} · BONUS ${bonus.toLocaleString()} · +1 SHOCK MINE`, t: 130, good: true};
      } else if (--run.clearing <= 0) {
        run.clearing = 0;
        nextWave();
      }
    }
  }

  function moveShip() {
    let mx = (cab.input.held(...Kit.RIGHT) ? 1 : 0) - (cab.input.held(...Kit.LEFT) ? 1 : 0);
    let my = (cab.input.held(...Kit.DOWN) ? 1 : 0) - (cab.input.held(...Kit.UP) ? 1 : 0);
    if (mx || my) pointer.active = false;
    else if (pointer.active) {
      const sx = screenX(ship.x) + W / 2;
      mx = Math.abs(pointer.x - sx) > 30 ? Math.sign(pointer.x - sx) : 0;
      my = clamp((pointer.y - ship.y) / 40, -1, 1);
    }
    if (mx) { ship.face = mx; ship.vx += mx * .45; if (cab.tick % 5 === 0) sfx.thrust(); }
    ship.vx *= .96;
    ship.vx = clamp(ship.vx, -11, 11);
    ship.vy += (my * 4.2 - ship.vy) * .25;
    ship.x = wrap(ship.x + ship.vx, WORLD);
    ship.y = clamp(ship.y + ship.vy, TOP + 14, GROUND - 16);
    if (ship.cool > 0) ship.cool -= 1;
    if (ship.guard > 0) ship.guard -= 1;
    ship.thrusting = Boolean(mx);
    if (cab.input.held("Space") || (pointer.down && pointer.button !== 2)) fire();
    if (pointer.down && pointer.button === 2) { pointer.down = false; shockMine(); }
    // Set a carried pod down by flying low.
    if (ship.carrying && ship.y > GROUND - 40) {
      const pod = ship.carrying;
      pod.state = "ground";
      pod.y = GROUND - 6;
      pod.x = ship.x;
      ship.carrying = null;
      run.score += 500;
      run.rescued += 1;
      say(ship.x, ship.y - 24, "POD SAFE +500", colours.green);
      sfx.catch();
    }
  }

  function moveScouts() {
    for (const scout of scouts) {
      scout.wobble += .05;
      if (scout.flash > 0) scout.flash -= 1;
      if (scout.hunter) {
        // Hunters come straight for you.
        const dx = toward(scout.x, ship.x), dy = ship.y - scout.y;
        scout.vx += Math.sign(dx) * .12;
        scout.vy += Math.sign(dy) * .1;
        scout.vx = clamp(scout.vx, -4.5 - run.wave * .2, 4.5 + run.wave * .2);
        scout.vy = clamp(scout.vy, -2.6, 2.6);
      } else if (scout.target) {
        if (scout.target.state === "carried") {
          // Up and away with it.
          scout.vx *= .9;
          scout.vy = -(.7 + run.wave * .06);
          scout.target.x = scout.x;
          scout.target.y = scout.y + 18;
          if (scout.y < TOP + 6) {
            scout.target.state = "gone";
            run.lost += 1;
            say(scout.x, TOP + 30, "POD LOST", colours.red);
            sfx.lost();
            scout.hunter = true;
            scout.target = null;
          }
        } else if (scout.target.state !== "ground") scout.target = null;
        else {
          const dx = toward(scout.x, scout.target.x);
          scout.vx = clamp(dx * .03, -2, 2);
          scout.vy = clamp((scout.target.y - 22 - scout.y) * .03, -1.6, 1.6);
          if (Math.abs(dx) < 6 && Math.abs(scout.target.y - 22 - scout.y) < 6) {
            scout.target.state = "carried";
            say(scout.x, scout.y - 18, "POD TAKEN!", colours.orange);
            sfx.grab();
          }
        }
      } else {
        // Drift, and pick a pod nobody's after.
        scout.vx = Math.cos(scout.wobble) * 1.2;
        scout.vy = Math.sin(scout.wobble * 1.3) * .5 + .25;
        if (scout.y > GROUND - 200) scout.vy = -.4;
        const taken = new Set(scouts.map((other) => other.target));
        const free = pods.filter((pod) => pod.state === "ground" && !taken.has(pod));
        if (free.length && chance(.004 + run.wave * .001)) scout.target = free.sort((a, b) => Math.abs(toward(scout.x, a.x)) - Math.abs(toward(scout.x, b.x)))[0];
      }
      scout.x = wrap(scout.x + scout.vx, WORLD);
      scout.y = clamp(scout.y + scout.vy, TOP, GROUND - 20);
      // Their caustic shots, at you when you're near.
      if (--scout.cool <= 0 && !ship.dead && Math.abs(toward(scout.x, ship.x)) < W * .6) {
        scout.cool = Math.max(50, 150 - run.wave * 10) * between(.7, 1.3) * (scout.hunter ? .6 : 1);
        const dx = toward(scout.x, ship.x), dy = ship.y - scout.y, d = Math.hypot(dx, dy) || 1;
        bolts.push({x: scout.x, y: scout.y, vx: dx / d * 3.6, vy: dy / d * 3.6, life: 160});
      }
      if (!ship.dead && Math.abs(toward(scout.x, ship.x)) < 20 && Math.abs(scout.y - ship.y) < 16) { kill(scout); hurtShip(); }
    }
  }

  function movePods() {
    for (const pod of pods) {
      if (pod.state === "falling") {
        pod.vy += .12;
        pod.y += pod.vy;
        if (!ship.dead && !ship.carrying && Math.abs(toward(pod.x, ship.x)) < 22 && Math.abs(pod.y - ship.y) < 22) {
          pod.state = "held";
          ship.carrying = pod;
          run.score += 250;
          say(ship.x, ship.y - 24, "CAUGHT +250 · SET IT DOWN", colours.yellow);
          sfx.catch();
        } else if (pod.y >= GROUND - 6) {
          pod.y = GROUND - 6;
          if (pod.y - pod.from < 150) { pod.state = "ground"; say(pod.x, pod.y - 16, "SAFE LANDING", colours.green); }
          else { pod.state = "gone"; run.lost += 1; burst(pod.x, pod.y, [colours.orange, "#ffffff"], 20); say(pod.x, pod.y - 16, "POD BROKEN", colours.red); sfx.lost(); }
        }
      } else if (pod.state === "held") {
        pod.x = ship.x;
        pod.y = ship.y + 18;
      }
    }
    pods = pods.filter((pod) => pod.state !== "gone");
    // Every pod gone: the settlement is overrun, and everything hunts you.
    if (!pods.length && !run.overrun) {
      run.overrun = true;
      for (const scout of scouts) scout.hunter = true;
      run.banner = {text: "SETTLEMENT OVERRUN", sub: "EVERY POD IS GONE · THEY'RE ALL HUNTING NOW", t: 160, alarm: true};
    }
  }

  // ---- Drawing. ----
  function drawWorld() {
    const sky = ctx.createLinearGradient(0, TOP, 0, GROUND);
    sky.addColorStop(0, "#02040a");
    sky.addColorStop(1, "#12081e");
    ctx.fillStyle = sky;
    ctx.fillRect(0, TOP, W, GROUND - TOP);
    for (const star of stars) {
      const x = wrap(star.x - camera * star.z, WORLD);
      if (x < 0 || x > W) continue;
      ctx.globalAlpha = .3 + star.z * .6;
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(x, star.y, star.z > .7 ? 2 : 1, star.z > .7 ? 2 : 1);
    }
    ctx.globalAlpha = 1;
    // Mountains on the horizon, at half the speed.
    ctx.fillStyle = "#1a0f24";
    ctx.beginPath();
    ctx.moveTo(0, GROUND);
    for (let x = 0; x <= W; x += 10) {
      const world = wrap(x + camera * .5, WORLD);
      const index = Math.floor(world / (WORLD / 40)), k = (world % (WORLD / 40)) / (WORLD / 40);
      const a = hills[index % 40].h, b = hills[(index + 1) % 40].h;
      ctx.lineTo(x, GROUND - 40 - (a + (b - a) * k));
    }
    ctx.lineTo(W, GROUND);
    ctx.fill();
    ctx.strokeStyle = "#5a3a7a";
    ctx.stroke();
    // The settlement's ground, with its lit pads.
    ctx.fillStyle = "#0e1610";
    ctx.fillRect(0, GROUND, W, H - GROUND);
    ctx.fillStyle = colours.green;
    ctx.fillRect(0, GROUND, W, 2);
    for (let i = 0; i < 12; i += 1) {
      const x = screenX(i * WORLD / 12) + W / 2;
      if (x < -60 || x > W + 60) continue;
      ctx.fillStyle = "#18242c";
      ctx.fillRect(x - 24, GROUND - 22, 48, 22);
      ctx.strokeStyle = colours.accent;
      ctx.strokeRect(x - 24, GROUND - 22, 48, 22);
      ctx.fillStyle = Math.floor(cab.tick / 30 + i) % 2 ? colours.yellow : "#3a3010";
      ctx.fillRect(x - 16, GROUND - 14, 4, 4);
      ctx.fillRect(x + 12, GROUND - 14, 4, 4);
    }
  }

  function drawPod(pod) {
    const x = screenX(pod.x) + W / 2;
    if (x < -20 || x > W + 20) return;
    ctx.save();
    ctx.translate(x, pod.y);
    ctx.beginPath();
    ctx.ellipse(0, 0, 9, 6, 0, 0, Math.PI * 2);
    ctx.fillStyle = "#e6eef5";
    ctx.fill();
    ctx.fillStyle = colours.orange;
    ctx.fillRect(-9, -1, 18, 2);
    if (pod.state !== "ground" && Math.floor(cab.tick / 8) % 2) {
      ctx.strokeStyle = colours.yellow;
      ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.arc(0, 0, 13, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.restore();
  }

  function drawScout(scout) {
    const x = screenX(scout.x) + W / 2;
    if (x < -30 || x > W + 30) return;
    const tone = scout.hunter ? HUNTER : SCOUT;
    ctx.save();
    ctx.translate(x, scout.y);
    ctx.scale(1 + Math.sin(cab.tick * .2 + scout.wobble) * .06, 1);
    ctx.beginPath();
    ctx.moveTo(0, 13); ctx.lineTo(9, 1); ctx.lineTo(14, -10); ctx.lineTo(5, -5); ctx.lineTo(0, -12); ctx.lineTo(-5, -5); ctx.lineTo(-14, -10); ctx.lineTo(-9, 1);
    ctx.closePath();
    ctx.fillStyle = "#120b1f";
    ctx.fill();
    glow(tone, 10);
    ctx.strokeStyle = tone;
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, 3.4, 0, Math.PI * 2); ctx.fillStyle = CAUSTIC; ctx.fill();
    ctx.restore();
    ctx.shadowBlur = 0;
    if (scout.target?.state === "carried") {
      ctx.strokeStyle = "rgba(141, 255, 184, .6)";
      ctx.beginPath(); ctx.moveTo(x, scout.y + 8); ctx.lineTo(x, scout.y + 14); ctx.stroke();
    }
  }

  function drawShip() {
    if (!ship || ship.dead || (ship.guard > 0 && Math.floor(ship.guard / 5) % 2)) return;
    const x = screenX(ship.x) + W / 2;
    ctx.save();
    ctx.translate(x, ship.y);
    ctx.scale(ship.face, 1);
    if (ship.thrusting) {
      ctx.fillStyle = colours.orange;
      glow(colours.orange, 12);
      ctx.fillRect(-28 - Math.random() * 8, -3, 10, 6);
      ctx.shadowBlur = 0;
    }
    ctx.beginPath();
    ctx.moveTo(24, 2); ctx.lineTo(6, -7); ctx.lineTo(-18, -9); ctx.lineTo(-20, 7); ctx.lineTo(10, 8);
    ctx.closePath();
    ctx.fillStyle = colours.panel;
    ctx.fill();
    glow(colours.accent, 10);
    ctx.strokeStyle = colours.accent;
    ctx.lineWidth = 1.8;
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.fillStyle = "rgba(0, 209, 255, .5)";
    ctx.fillRect(2, -5, 9, 4);
    ctx.restore();
  }

  function drawScanner() {
    // The whole world in a strip along the top, like the old scanners.
    const x0 = 120, y0 = 54, w = W - 240, h = 32;
    ctx.fillStyle = "rgba(0, 20, 30, .7)";
    ctx.fillRect(x0, y0, w, h);
    ctx.strokeStyle = colours.dim;
    ctx.strokeRect(x0 + .5, y0 + .5, w - 1, h - 1);
    const map = (x, y) => [x0 + wrap(x - ship.x + WORLD / 2, WORLD) / WORLD * w, y0 + (y - TOP) / (GROUND - TOP) * h];
    const view = W / WORLD * w;
    ctx.strokeStyle = "rgba(255,255,255,.25)";
    ctx.strokeRect(x0 + w / 2 - view / 2, y0 + 1, view, h - 2);
    for (const pod of pods) { const [x, y] = map(pod.x, pod.y); ctx.fillStyle = pod.state === "ground" ? colours.green : colours.yellow; ctx.fillRect(x - 1, y - 1, 2, 2); }
    for (const scout of scouts) { const [x, y] = map(scout.x, scout.y); ctx.fillStyle = scout.hunter ? HUNTER : SCOUT; ctx.fillRect(x - 1.5, y - 1.5, 3, 3); }
    const [sx, sy] = map(ship.x, ship.y);
    ctx.fillStyle = colours.accent;
    ctx.fillRect(sx - 2, sy - 2, 4, 4);
  }

  function draw() {
    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, 0, W, H);
    if (run.quake > 0) ctx.translate(between(-1, 1) * run.quake * .4, between(-1, 1) * run.quake * .4);
    drawWorld();
    pods.forEach(drawPod);
    scouts.forEach(drawScout);
    ctx.fillStyle = colours.accent;
    for (const shot of shots) {
      const x = screenX(shot.x) + W / 2;
      ctx.fillRect(x - 12, shot.y - 1, 24, 2);
    }
    ctx.fillStyle = CAUSTIC;
    for (const bolt of bolts) { ctx.beginPath(); ctx.arc(screenX(bolt.x) + W / 2, bolt.y, 3, 0, Math.PI * 2); ctx.fill(); }
    if (cab.state !== "title" && ship) drawShip();
    for (const spark of sparks) {
      ctx.globalAlpha = clamp(spark.life / 30, 0, 1);
      ctx.fillStyle = spark.colour;
      ctx.fillRect(screenX(spark.x) + W / 2 - 1, spark.y - 1, 2, 2);
    }
    ctx.globalAlpha = 1;
    for (const word of words) {
      ctx.globalAlpha = clamp(word.life / 30, 0, 1);
      text(word.text, screenX(word.x) + W / 2, word.y, 11, word.colour);
    }
    ctx.globalAlpha = 1;
    ctx.setTransform(cab.scale, 0, 0, cab.scale, 0, 0);
    if (run.flash > 0) { ctx.fillStyle = `rgba(200, 240, 255, ${run.flash / 40})`; ctx.fillRect(0, 0, W, H); }
    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, 0, W, TOP - 2);
    cab.scoreBar(run.score, "WAVE", run.wave);
    if (ship && cab.state !== "title") {
      drawScanner();
      text(`MINES ${run.mines}`, 18, 78, 10, colours.orange, "left");
      for (let i = 0; i < Math.max(0, run.lives - (ship.dead ? 0 : 1)); i += 1) { ctx.fillStyle = colours.accent; ctx.fillRect(W - 30 - i * 16, 72, 10, 5); }
      text(`PODS ${pods.filter((pod) => pod.state === "ground").length}`, W - 18, 88, 10, colours.green, "right");
    }
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 8, 8, colours.dim);
    const banner = run.banner;
    if (banner && cab.state === "play") {
      ctx.globalAlpha = clamp(banner.t / 30, 0, 1);
      text(banner.text, W / 2, H / 2 - 40, 30, banner.alarm ? colours.red : banner.good ? colours.green : colours.text, "center", 700, Kit.DISPLAY);
      text(banner.sub, W / 2, H / 2 - 16, 11, colours.accent);
      ctx.globalAlpha = 1;
    }
    if (cab.state === "title") {
      cab.titleScreen({top: "POD", bottom: "RESCUE", tone: SCOUT, y: 170,
        rows: [["THARGOID SCOUT", "150"], ["SCOUT WITH A POD", "200"], ["CATCH A FALLING POD", "250"], ["SET IT DOWN SAFE", "500"], ["HUNTER", "250"]],
        note: "A POD CARRIED OFF THE TOP IS LOST, AND ITS SCOUT HUNTS YOU",
        how: "ARROWS OR MOUSE TO FLY · SPACE / CLICK FIRE · B / RIGHT-CLICK SHOCK MINE"});
    } else if (cab.state === "over") {
      cab.overScreen({heading: "SHIP DESTROYED", tone: colours.red, sub: "PATROL DEBRIEF", rank: Kit.rank(run.score, .4),
        lines: [["SCORE", run.score.toLocaleString()], ["WAVE", run.wave], ["PODS RESCUED", run.rescued], ["PODS LOST", run.lost], ["SCOUTS DOWNED", run.kills]]});
    }
  }

  function report() {
    return {score: run.score, wave: run.wave, lives: run.lives, mines: run.mines, pods: pods.length, scouts: scouts.length, queue};
  }

  function debugOver() {
    run.score += 1234;
    run.lives = 1;
    ship.guard = 0;
    hurtShip();
    ship.respawn = 1;
  }

  function card() {
    startGame();
    run.wave = 2;
    queue = 0;
    run.score = 5650;
    for (let i = 0; i < 120; i += 1) { cab.tick += 1; update(); }
    scouts = [];
    bolts = [];
    shots = [];
    words = [];
    Object.assign(ship, {y: 380, vx: 6, face: 1, guard: 0, thrusting: true, dead: false});
    camera = wrap(ship.x + W * .18, WORLD);
    const near = pods.reduce((best, item) => (Math.abs(toward(ship.x + 200, item.x)) < Math.abs(toward(ship.x + 200, best.x)) ? item : best));
    for (const [dx, y, hunter] of [[-230, 170, false], [-120, 230, false], [260, 200, false], [150, 300, true], [-200, 470, false]]) spawnScout(hunter, wrap(ship.x + dx, WORLD)), scouts[scouts.length - 1].y = y;
    spawnScout(false, wrap(ship.x + 200, WORLD));
    const carrier = scouts[scouts.length - 1];
    Object.assign(carrier, {y: 330, target: near, cool: 999});
    Object.assign(near, {state: "carried", x: carrier.x, y: 348});
    for (const scout of scouts) scout.cool = 999;
    for (let i = 0; i < 4; i += 1) shots.push({x: wrap(ship.x + 40 + i * 60, WORLD), y: 382, vx: 15, life: 6});
    bolts.push({x: wrap(ship.x + 90, WORLD), y: 250, vx: -1, vy: 1, life: 60});
    run.banner = null;
  }

  window.podRescue = {state: () => ({...report(), state: cab.state})};
})();
