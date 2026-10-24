// Station Defence (5.6.3): Thargoid caustic missiles rain on a surface
// settlement. Three point-defence turrets, aimed with the mouse: a shot
// bursts where you click, and the burst takes out whatever flies into it.
// Missiles split, waves get faster, and Scouts cross the sky dropping seeds.
(() => {
  "use strict";

  const W = 600, H = 675, GROUND = H - 62;
  const {clamp, between, chance, pick} = Kit;
  const colours = {bg: "#040608", panel: "#0d141b", accent: "#00d1ff", orange: "#ff8a3d", text: "#e2edf3",
    muted: "#93a6b3", dim: "#5d6f7c", green: "#54e39a", yellow: "#f5c76d", red: "#ff6b70"};
  const CAUSTIC = "#9dff6a";
  const TURRETS = [60, W / 2, W - 60];
  const BUILDINGS = [120, 175, 230, 370, 425, 480];
  const BONUS_EVERY = 10000;

  const cab = Kit.cabinet({width: W, height: H, colours, crt: true, start: startGame, update, draw, report, end: debugOver, card, key});
  const {ctx} = cab;
  const {text, glow} = cab.draw;
  const pointer = cab.input.pointer;

  const run = {score: 0, wave: 0, banner: null, nextBonus: BONUS_EVERY, downed: 0, scouts: 0, quake: 0, spare: 0};
  let turrets = [], buildings = [], missiles = [], shots = [], blasts = [], scouts = [], sparks = [];
  let queue = 0, spawnClock = 0, waveDone = 0, aim = {x: W / 2, y: H / 2}, keyboardAim = false;

  const sfx = {
    fire() { cab.sound.tone("square", 900, 300, .1, .1); },
    blast() { cab.sound.hiss(.4, .4, 2200); },
    impact() { cab.sound.hiss(.9, .8, 900); cab.sound.tone("sawtooth", 180, 40, .8, .25); },
    split() { cab.sound.tone("sine", 1400, 700, .15, .08); },
    scout() { cab.sound.tone("sawtooth", 260, 300, .6, .06); },
    bonus() { [659, 784, 988, 1319].forEach((f, i) => cab.sound.tone("triangle", f, f, .12, .16, i * .08)); },
    empty() { cab.sound.tone("square", 160, 140, .08, .08); },
  };

  function key(code) {
    if (cab.state !== "play") return false;
    const index = {Digit1: 0, KeyA: 0, Digit2: 1, KeyS: 1, Digit3: 2, KeyD: 2}[code];
    if (index !== undefined) { fireFrom(index); return true; }
    if (code === "Space") { fireNearest(); return true; }
    return false;
  }

  function startGame() {
    Object.assign(run, {score: 0, wave: 0, banner: null, nextBonus: BONUS_EVERY, downed: 0, scouts: 0, quake: 0, spare: 0});
    buildings = BUILDINGS.map((x, index) => ({x, alive: true, kind: index % 3}));
    pointer.active = false;
    nextWave();
  }

  function nextWave() {
    run.wave += 1;
    turrets = TURRETS.map((x, index) => ({x, ammo: 10, alive: turrets[index]?.alive ?? true}));
    for (const turret of turrets) turret.alive = true;
    missiles = []; shots = []; blasts = []; scouts = [];
    queue = 10 + run.wave * 3;
    spawnClock = 90;
    waveDone = 0;
    run.banner = {text: `WAVE ${Kit.pad(run.wave)}`, sub: `${queue} CAUSTIC MISSILES INBOUND · ×${multiplier()} POINTS`, t: 140};
  }

  function multiplier() {
    return 1 + Math.floor((run.wave - 1) / 2) * .5;
  }

  function targets() {
    return [...buildings.filter((item) => item.alive).map((item) => ({x: item.x, y: GROUND - 6})),
      ...turrets.filter((item) => item.alive).map((item) => ({x: item.x, y: GROUND - 10}))];
  }

  function launch(x, y, speedScale = 1) {
    const goals = targets();
    if (!goals.length) return;
    const goal = pick(goals);
    const speed = (.45 + run.wave * .07) * between(.85, 1.15) * speedScale;
    const splits = run.wave > 1 && chance(Math.min(.12 + run.wave * .04, .4));
    missiles.push({sx: x, sy: y, x, y, tx: goal.x + between(-6, 6), ty: goal.y, speed,
      split: splits ? between(H * .25, H * .5) : null});
  }

  function fireFrom(index) {
    const turret = turrets[index];
    if (!turret?.alive) return;
    if (turret.ammo <= 0) { sfx.empty(); return; }
    const tx = clamp(aim.x, 0, W), ty = clamp(aim.y, 30, GROUND - 30);
    turret.ammo -= 1;
    shots.push({x: turret.x, y: GROUND - 16, sx: turret.x, sy: GROUND - 16, tx, ty, speed: index === 1 ? 11 : 8});
    sfx.fire();
  }

  function fireNearest() {
    const ready = turrets.map((turret, index) => ({turret, index})).filter(({turret}) => turret.alive && turret.ammo > 0);
    if (!ready.length) { sfx.empty(); return; }
    ready.sort((a, b) => Math.abs(a.turret.x - aim.x) - Math.abs(b.turret.x - aim.x));
    fireFrom(ready[0].index);
  }

  function blast(x, y, friendly, max = 38) {
    blasts.push({x, y, r: 2, max, grow: true, friendly});
    if (friendly) sfx.blast();
  }

  function addScore(points) {
    run.score += Math.round(points);
    if (run.score >= run.nextBonus) {
      run.nextBonus += BONUS_EVERY;
      const lost = buildings.find((item) => !item.alive);
      if (lost) {
        lost.alive = true;
        run.banner = {text: "BONUS BUILDING", sub: "A HAB REBUILT", t: 100, good: true};
      } else run.spare += 1;
      sfx.bonus();
    }
  }

  function update() {
    for (const spark of sparks) { spark.x += spark.vx; spark.y += spark.vy; spark.vy += .04; spark.life -= 1; }
    sparks = sparks.filter((spark) => spark.life > 0);
    if (cab.state !== "play") return;
    if (run.banner && --run.banner.t <= 0) run.banner = null;
    if (run.quake > 0) run.quake -= 1;

    // The crosshair: the mouse, or the arrow keys.
    const kx = (cab.input.held(...Kit.RIGHT) ? 1 : 0) - (cab.input.held(...Kit.LEFT) ? 1 : 0);
    const ky = (cab.input.held(...Kit.DOWN) ? 1 : 0) - (cab.input.held(...Kit.UP) ? 1 : 0);
    if (kx || ky) { keyboardAim = true; aim.x = clamp(aim.x + kx * 6, 0, W); aim.y = clamp(aim.y + ky * 6, 30, GROUND - 30); }
    else if (pointer.active && !keyboardAim) { aim.x = pointer.x; aim.y = pointer.y; }
    if (pointer.active && keyboardAim && Math.hypot(pointer.x - aim.x, pointer.y - aim.y) > 40) keyboardAim = false;
    if (cab.input.clicked()) { aim.x = pointer.x; aim.y = pointer.y; fireNearest(); }

    // Missiles keep coming until the wave's are spent.
    if (queue > 0 && --spawnClock <= 0) {
      const burst = Math.min(queue, chance(.3) ? 3 : chance(.5) ? 2 : 1);
      for (let i = 0; i < burst; i += 1) launch(between(20, W - 20), -10);
      queue -= burst;
      spawnClock = Math.max(40, 150 - run.wave * 9) * between(.6, 1.3);
    }
    if (run.wave > 1 && queue > 4 && !scouts.length && chance(.003 + run.wave * .0006)) {
      const left = chance(.5);
      scouts.push({x: left ? -30 : W + 30, y: between(70, 160), vx: (left ? 1 : -1) * between(1.2, 1.8), seeds: 2 + Math.min(run.wave, 4), drop: between(60, 140)});
      sfx.scout();
    }

    for (const scout of scouts) {
      scout.x += scout.vx;
      if (scout.seeds > 0 && --scout.drop <= 0) {
        scout.seeds -= 1;
        scout.drop = between(50, 110);
        launch(scout.x, scout.y + 8, 1.1);
      }
    }
    scouts = scouts.filter((scout) => !scout.dead && scout.x > -50 && scout.x < W + 50);

    for (const missile of missiles) {
      const dx = missile.tx - missile.x, dy = missile.ty - missile.y, d = Math.hypot(dx, dy) || 1;
      missile.x += dx / d * missile.speed;
      missile.y += dy / d * missile.speed;
      if (missile.split && missile.y > missile.split) {
        missile.dead = true;
        sfx.split();
        for (let i = 0; i < (chance(.4) ? 3 : 2); i += 1) launch(missile.x, missile.y, 1.05);
        continue;
      }
      if (d < missile.speed + 1) {
        missile.dead = true;
        impact(missile.tx, missile.ty);
      }
    }
    for (const shot of shots) {
      const dx = shot.tx - shot.x, dy = shot.ty - shot.y, d = Math.hypot(dx, dy) || 1;
      if (d <= shot.speed) { shot.dead = true; blast(shot.tx, shot.ty, true); continue; }
      shot.x += dx / d * shot.speed;
      shot.y += dy / d * shot.speed;
    }
    shots = shots.filter((shot) => !shot.dead);

    for (const item of blasts) {
      if (item.grow) { item.r += 1.4; if (item.r >= item.max) item.grow = false; }
      else item.r -= .9;
      if (!item.friendly) continue;
      for (const missile of missiles) {
        if (!missile.dead && Math.hypot(missile.x - item.x, missile.y - item.y) < item.r) {
          missile.dead = true;
          run.downed += 1;
          addScore(25 * multiplier());
          blasts.push({x: missile.x, y: missile.y, r: 2, max: 22, grow: true, friendly: true});
        }
      }
      for (const scout of scouts) {
        if (!scout.dead && Math.hypot(scout.x - item.x, scout.y - item.y) < item.r + 12) {
          scout.dead = true;
          run.scouts += 1;
          addScore(125 * multiplier());
          burst(scout.x, scout.y, ["#b48cff", CAUSTIC, "#ffffff"], 30);
          run.banner = {text: "SCOUT DOWN", sub: `+${Math.round(125 * multiplier())}`, t: 70, good: true};
        }
      }
    }
    blasts = blasts.filter((item) => item.r > 0);
    missiles = missiles.filter((missile) => !missile.dead);

    if (!buildings.some((item) => item.alive)) return finish();
    if (!queue && !missiles.length && !scouts.length && !blasts.length) {
      if (!waveDone) {
        waveDone = 150;
        const ammo = turrets.reduce((sum, turret) => sum + (turret.alive ? turret.ammo : 0), 0);
        const standing = buildings.filter((item) => item.alive).length;
        const bonus = Math.round((ammo * 5 + standing * 100) * multiplier());
        addScore(bonus);
        run.banner = {text: "WAVE HELD", sub: `${ammo} SHOTS × 5 · ${standing} HABS × 100 · BONUS ${bonus.toLocaleString()}`, t: 150, good: true};
      } else if (--waveDone <= 0) nextWave();
    }
  }

  function impact(x, y) {
    run.quake = 12;
    blast(x, y, false, 30);
    burst(x, y, [CAUSTIC, colours.yellow, "#ffffff"], 24);
    sfx.impact();
    for (const item of buildings) if (item.alive && Math.abs(item.x - x) < 26) item.alive = false;
    for (const turret of turrets) if (turret.alive && Math.abs(turret.x - x) < 22) { turret.alive = false; turret.ammo = 0; }
  }

  function burst(x, y, palette, count) {
    for (let i = 0; i < count; i += 1) {
      const a = between(Math.PI, Math.PI * 2), v = between(.5, 3.5);
      sparks.push({x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: between(20, 50), colour: pick(palette)});
    }
  }

  function finish() {
    cab.over({score: run.score, wave: run.wave, rank: Kit.rank(run.score, .5)});
  }

  // ---- Drawing. ----
  function drawGround() {
    const sky = ctx.createLinearGradient(0, 0, 0, GROUND);
    sky.addColorStop(0, "#04060a");
    sky.addColorStop(1, "#0c1520");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, W, GROUND);
    ctx.fillStyle = "#131a14";
    ctx.beginPath();
    ctx.moveTo(0, GROUND);
    for (let x = 0; x <= W; x += 20) ctx.lineTo(x, GROUND - 4 + Math.sin(x * .07) * 3);
    ctx.lineTo(W, H);
    ctx.lineTo(0, H);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "#3b4a3a";
    ctx.stroke();
    for (const item of buildings) {
      const x = item.x;
      if (!item.alive) {
        ctx.fillStyle = "#2a2a22";
        ctx.fillRect(x - 16, GROUND - 6, 32, 6);
        ctx.fillStyle = CAUSTIC;
        ctx.globalAlpha = .3 + Math.sin(cab.tick * .1 + x) * .15;
        ctx.fillRect(x - 12, GROUND - 4, 24, 2);
        ctx.globalAlpha = 1;
        continue;
      }
      ctx.fillStyle = "#1b2633";
      ctx.strokeStyle = colours.accent;
      ctx.lineWidth = 1.2;
      if (item.kind === 0) {
        ctx.beginPath(); ctx.arc(x, GROUND - 2, 16, Math.PI, 0); ctx.closePath(); ctx.fill(); ctx.stroke();
      } else if (item.kind === 1) {
        ctx.fillRect(x - 10, GROUND - 32, 20, 32); ctx.strokeRect(x - 10, GROUND - 32, 20, 32);
      } else {
        ctx.fillRect(x - 17, GROUND - 18, 34, 18); ctx.strokeRect(x - 17, GROUND - 18, 34, 18);
      }
      ctx.fillStyle = colours.yellow;
      for (let i = 0; i < 3; i += 1) if ((Math.floor(cab.tick / 40) + i + item.kind) % 3) ctx.fillRect(x - 8 + i * 6, GROUND - 12, 3, 3);
    }
    turrets.forEach((turret, index) => {
      ctx.fillStyle = turret.alive ? "#18222c" : "#2a2a22";
      ctx.beginPath();
      ctx.moveTo(turret.x - 22, GROUND + 2);
      ctx.lineTo(turret.x - 12, GROUND - 14);
      ctx.lineTo(turret.x + 12, GROUND - 14);
      ctx.lineTo(turret.x + 22, GROUND + 2);
      ctx.closePath();
      ctx.fill();
      if (!turret.alive) return;
      ctx.strokeStyle = colours.orange;
      ctx.stroke();
      const a = Math.atan2(aim.y - (GROUND - 16), aim.x - turret.x);
      ctx.beginPath();
      ctx.moveTo(turret.x, GROUND - 14);
      ctx.lineTo(turret.x + Math.cos(a) * 16, GROUND - 14 + Math.sin(a) * 16);
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.lineWidth = 1.2;
      // Its shots left, as pips under it.
      for (let i = 0; i < turret.ammo; i += 1) {
        ctx.fillStyle = colours.orange;
        ctx.fillRect(turret.x - 22 + (i % 5) * 9, GROUND + 14 + Math.floor(i / 5) * 7, 6, 4);
      }
      text(String(index + 1), turret.x, GROUND + 44, 9, colours.dim);
    });
  }

  function draw() {
    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, 0, W, H);
    if (run.quake > 0) ctx.translate(between(-1, 1) * run.quake * .4, between(-1, 1) * run.quake * .4);
    drawGround();
    ctx.lineWidth = 1.4;
    for (const missile of missiles) {
      const trail = ctx.createLinearGradient(missile.sx, missile.sy, missile.x, missile.y);
      trail.addColorStop(0, "rgba(157, 255, 106, 0)");
      trail.addColorStop(1, "rgba(157, 255, 106, .75)");
      ctx.strokeStyle = trail;
      ctx.beginPath();
      ctx.moveTo(missile.sx, missile.sy);
      ctx.lineTo(missile.x, missile.y);
      ctx.stroke();
      ctx.fillStyle = Math.floor(cab.tick / 4) % 2 ? "#ffffff" : CAUSTIC;
      ctx.fillRect(missile.x - 2, missile.y - 2, 4, 4);
    }
    ctx.strokeStyle = colours.accent;
    for (const shot of shots) {
      ctx.beginPath(); ctx.moveTo(shot.sx, shot.sy); ctx.lineTo(shot.x, shot.y); ctx.globalAlpha = .5; ctx.stroke(); ctx.globalAlpha = 1;
      ctx.fillStyle = "#ffffff"; ctx.fillRect(shot.x - 1.5, shot.y - 1.5, 3, 3);
      ctx.strokeStyle = colours.accent;
      ctx.beginPath(); ctx.moveTo(shot.tx - 4, shot.ty - 4); ctx.lineTo(shot.tx + 4, shot.ty + 4); ctx.moveTo(shot.tx + 4, shot.ty - 4); ctx.lineTo(shot.tx - 4, shot.ty + 4); ctx.stroke();
    }
    for (const item of blasts) {
      const tone = item.friendly ? (Math.floor(cab.tick / 3) % 2 ? colours.accent : "#ffffff") : CAUSTIC;
      ctx.beginPath();
      ctx.arc(item.x, item.y, item.r, 0, Math.PI * 2);
      ctx.fillStyle = tone;
      ctx.globalAlpha = .35;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = tone;
      glow(tone, 12);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }
    for (const scout of scouts) {
      ctx.save();
      ctx.translate(scout.x, scout.y);
      ctx.scale(Math.sign(scout.vx), 1);
      ctx.beginPath();
      ctx.moveTo(16, 0); ctx.lineTo(-6, -10); ctx.lineTo(-14, -4); ctx.lineTo(-10, 0); ctx.lineTo(-14, 4); ctx.lineTo(-6, 10);
      ctx.closePath();
      ctx.fillStyle = "#120b1f";
      ctx.fill();
      glow("#b48cff", 12);
      ctx.strokeStyle = "#b48cff";
      ctx.lineWidth = 1.6;
      ctx.stroke();
      ctx.beginPath(); ctx.arc(0, 0, 3, 0, Math.PI * 2); ctx.fillStyle = CAUSTIC; ctx.fill();
      ctx.restore();
      ctx.shadowBlur = 0;
    }
    for (const spark of sparks) {
      ctx.globalAlpha = clamp(spark.life / 30, 0, 1);
      ctx.fillStyle = spark.colour;
      ctx.fillRect(spark.x - 1, spark.y - 1, 2, 2);
    }
    ctx.globalAlpha = 1;
    ctx.setTransform(cab.scale, 0, 0, cab.scale, 0, 0);
    if (cab.state === "play") {
      ctx.strokeStyle = colours.text;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.arc(aim.x, aim.y, 9, 0, Math.PI * 2);
      ctx.moveTo(aim.x - 15, aim.y); ctx.lineTo(aim.x - 5, aim.y);
      ctx.moveTo(aim.x + 5, aim.y); ctx.lineTo(aim.x + 15, aim.y);
      ctx.moveTo(aim.x, aim.y - 15); ctx.lineTo(aim.x, aim.y - 5);
      ctx.moveTo(aim.x, aim.y + 5); ctx.lineTo(aim.x, aim.y + 15);
      ctx.stroke();
    }
    cab.scoreBar(run.score, "WAVE", run.wave);
    if (cab.state === "play") text(`NEXT HAB AT ${run.nextBonus.toLocaleString()}`, W / 2, 62, 9, colours.dim);
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 6, 8, colours.dim);
    const banner = run.banner;
    if (banner && cab.state === "play") {
      ctx.globalAlpha = clamp(banner.t / 30, 0, 1);
      text(banner.text, W / 2, H / 2 - 40, 30, banner.good ? colours.green : colours.text, "center", 700, Kit.DISPLAY);
      text(banner.sub, W / 2, H / 2 - 16, 11, colours.accent);
      ctx.globalAlpha = 1;
    }
    if (cab.state === "title") {
      cab.titleScreen({top: "STATION", bottom: "DEFENCE", tone: CAUSTIC, y: 160,
        rows: [["CAUSTIC MISSILE", "25"], ["THARGOID SCOUT", "125"], ["SHOTS LEFT", "5 EACH"], ["HABS STANDING", "100 EACH"],
          ["EVERY 10,000", "A HAB REBUILT"]],
        note: "SHOTS BURST WHERE YOU CLICK · ONE BURST CAN TAKE SEVERAL",
        how: "MOUSE TO AIM · CLICK OR SPACE TO FIRE · 1 2 3 FOR A TURRET"});
    } else if (cab.state === "over") {
      cab.overScreen({heading: "SETTLEMENT LOST", tone: colours.red, sub: "DEFENCE DEBRIEF", rank: Kit.rank(run.score, .5),
        lines: [["SCORE", run.score.toLocaleString()], ["WAVES HELD", run.wave - 1], ["MISSILES DOWNED", run.downed], ["SCOUTS DOWNED", run.scouts]]});
    }
  }

  function report() {
    return {score: run.score, wave: run.wave, missiles: missiles.length, queue, buildings: buildings.filter((item) => item.alive).length,
      ammo: turrets.map((turret) => turret.ammo)};
  }

  function debugOver() {
    run.score += 1234;
    for (const item of buildings) item.alive = false;
  }

  function card() {
    startGame();
    run.wave = 3;
    nextWave();
    run.score = 6475;
    run.banner = null;
    buildings[1].alive = false;
    for (let i = 0; i < 9; i += 1) launch(between(40, W - 40), between(-10, 200));
    scouts.push({x: 210, y: 120, vx: 1.4, seeds: 3, drop: 999});
    for (let i = 0; i < 160; i += 1) { cab.tick += 1; update(); }
    aim = {x: missiles[0]?.x ?? 300, y: (missiles[0]?.y ?? 300) + 30};
    fireFrom(1);
    aim = {x: 160, y: 300};
    fireFrom(0);
    blast(420, 260, true, 40);
    blasts[blasts.length - 1].r = 30;
    for (let i = 0; i < 20; i += 1) { cab.tick += 1; update(); }
    run.banner = null;
  }

  window.stationDefence = {state: () => ({...report(), state: cab.state})};
})();
