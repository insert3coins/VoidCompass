// Rock Rats (5.6.3): mining in a vector asteroid field. Break rocks into
// smaller rocks; send limpets for the fragments; a full hold banks them.
// Cores are worth far more than the gravel, pristine rocks give more, and
// now and then a pirate comes to see what you've got.
(() => {
  "use strict";

  const W = 600, H = 675;
  const HOLD = 16;
  const {clamp, between, chance, pick, wrap} = Kit;
  const colours = {bg: "#04070a", panel: "#0c1218", accent: "#7ee8ff", orange: "#ff8a3d", text: "#e8f1f6",
    muted: "#97a9b6", dim: "#5f707c", green: "#54e39a", yellow: "#f5c76d", red: "#ff6b70"};
  const ROCK = {3: {r: 46, score: 20, speed: .7}, 2: {r: 26, score: 50, speed: 1.2}, 1: {r: 13, score: 100, speed: 1.8}};
  const FRAGMENT = {gravel: {score: 10, colour: "#b9c3cc", label: "GRAVEL"}, pristine: {score: 25, colour: "#7ee8ff", label: "PRISTINE"},
    core: {score: 150, colour: "#ff7ad9", label: "CORE"}};
  const PIRATES = {sidewinder: {r: 14, hp: 2, score: 200, speed: 1.3, aim: .5, every: 110, colour: "#f5c76d"},
    viper: {r: 15, hp: 3, score: 500, speed: 2.3, aim: .9, every: 70, colour: "#ff6b70"}};

  const cab = Kit.cabinet({width: W, height: H, colours, start: startGame, update, draw, report, end: debugOver, card, key});
  const {ctx} = cab;
  const {text, glow} = cab.draw;
  const pointer = cab.input.pointer;

  const run = {score: 0, wave: 0, lives: 3, banked: 0, cores: 0, pirates: 0, banner: null, clearing: 0, quake: 0};
  let ship = null, rocks = [], shots = [], bolts = [], fragments = [], limpets = [], pirates = [], sparks = [], words = [];
  let hold = [], limpetStock = 0, pirateClock = 0;

  const sfx = {
    shoot() { cab.sound.tone("square", 1400, 500, .06, .1); },
    crack(size) { cab.sound.hiss(.15 + size * .1, .45, 1600 - size * 300); },
    collect() { cab.sound.tone("triangle", 880, 1320, .08, .12); },
    bank() { [523, 659, 784, 1047].forEach((f, i) => cab.sound.tone("square", f, f, .09, .12, i * .07)); },
    thrust() { cab.sound.hiss(.08, .12, 600); },
    hit() { cab.sound.hiss(.8, .8, 1100); cab.sound.tone("sawtooth", 400, 40, .7, .3); },
    pirate() { for (let i = 0; i < 2; i += 1) cab.sound.tone("sawtooth", 520, 390, .25, .12, i * .3); },
  };

  function key(code) {
    if (code === "KeyE" || code === "KeyF" || code === "ShiftLeft") { if (cab.state === "play") sendLimpet(); return cab.state === "play"; }
    return false;
  }

  function startGame() {
    Object.assign(run, {score: 0, wave: 0, lives: 3, banked: 0, cores: 0, pirates: 0, banner: null, clearing: 0, quake: 0});
    shots = []; bolts = []; fragments = []; limpets = []; pirates = []; sparks = []; words = []; hold = [];
    ship = newShip();
    pointer.active = false;
    nextWave();
  }

  function newShip() {
    return {x: W / 2, y: H / 2, vx: 0, vy: 0, angle: -Math.PI / 2, cool: 0, guard: 150, thrusting: false};
  }

  function nextWave() {
    run.wave += 1;
    rocks = [];
    const count = Math.min(3 + run.wave, 11);
    for (let i = 0; i < count; i += 1) {
      let x, y;
      do { x = between(0, W); y = between(0, H); } while (Math.hypot(x - ship.x, y - ship.y) < 170);
      rocks.push(newRock(3, x, y));
    }
    limpetStock = Math.min(limpetStock + 8, 20);
    pirateClock = Math.max(500, 1300 - run.wave * 90);
    run.banner = {text: `FIELD ${Kit.pad(run.wave)}`, sub: `${count} ROCKS · +8 LIMPETS`, t: 130};
  }

  function newRock(size, x, y, kind) {
    const a = between(0, Math.PI * 2), speed = ROCK[size].speed * between(.6, 1.2) * (1 + run.wave * .05);
    const sides = 9 + size * 2;
    const shape = Array.from({length: sides}, () => between(.72, 1.08));
    const type = kind || (chance(.16) ? "core" : chance(.2) ? "pristine" : "plain");
    return {size, x, y, vx: Math.cos(a) * speed, vy: Math.sin(a) * speed, angle: between(0, 7), spin: between(-.02, .02), shape, kind: type};
  }

  function aim() {
    if (pointer.active) return Math.atan2(pointer.y - ship.y, pointer.x - ship.x);
    return null;
  }

  function fire() {
    if (ship.cool > 0 || shots.length >= 7) return;
    shots.push({x: ship.x + Math.cos(ship.angle) * 16, y: ship.y + Math.sin(ship.angle) * 16,
      vx: Math.cos(ship.angle) * 9 + ship.vx, vy: Math.sin(ship.angle) * 9 + ship.vy, life: 52});
    ship.cool = 9;
    sfx.shoot();
  }

  function sendLimpet() {
    if (!ship || ship.dead || limpetStock <= 0 || hold.length + limpets.length >= HOLD) return;
    const taken = new Set(limpets.map((limpet) => limpet.target));
    const target = fragments.filter((item) => !taken.has(item))
      .sort((a, b) => Math.hypot(a.x - ship.x, a.y - ship.y) - Math.hypot(b.x - ship.x, b.y - ship.y))[0];
    if (!target) return;
    limpetStock -= 1;
    limpets.push({x: ship.x, y: ship.y, target, carrying: null, life: 900});
    cab.sound.tone("sine", 600, 900, .1, .1);
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

  function breakRock(rock) {
    rock.dead = true;
    run.score += ROCK[rock.size].score;
    sfx.crack(rock.size);
    burst(rock.x, rock.y, ["#d9e2ea", "#8a97a3"], 8 + rock.size * 5, 2.5);
    if (rock.size > 1) {
      for (let i = 0; i < 2; i += 1) rocks.push(newRock(rock.size - 1, rock.x, rock.y, rock.kind === "core" && i === 1 ? "plain" : rock.kind));
    }
    // What falls out: gravel always, more from a pristine rock, the core itself last.
    const drops = rock.kind === "pristine" ? 2 : 1;
    for (let i = 0; i < drops; i += 1) {
      const type = rock.kind === "pristine" ? "pristine" : "gravel";
      if (rock.size === 1 || chance(.4)) fragments.push(fragment(rock, type));
    }
    if (rock.kind === "core" && rock.size === 1) {
      fragments.push(fragment(rock, "core"));
      say(rock.x, rock.y - 18, "CORE EXPOSED", FRAGMENT.core.colour);
    }
  }

  function fragment(rock, type) {
    const a = between(0, Math.PI * 2);
    return {x: rock.x, y: rock.y, vx: rock.vx * .4 + Math.cos(a) * .6, vy: rock.vy * .4 + Math.sin(a) * .6, type, life: 1500, spin: between(0, 6)};
  }

  function bank(reason) {
    if (!hold.length) return;
    const value = hold.reduce((sum, type) => sum + FRAGMENT[type].score, 0);
    const bonus = hold.length >= HOLD ? Math.round(value * .5) : 0;
    run.score += value + bonus;
    run.banked += hold.length;
    say(ship.x, ship.y - 30, `${reason} +${(value + bonus).toLocaleString()}`, colours.green);
    hold = [];
    sfx.bank();
  }

  function hurtShip() {
    if (ship.guard > 0 || ship.dead) return;
    ship.dead = true;
    run.lives -= 1;
    run.quake = 20;
    burst(ship.x, ship.y, [colours.accent, colours.orange, "#ffffff"], 50, 5);
    if (hold.length) say(ship.x, ship.y - 20, `${hold.length} T LOST`, colours.red);
    hold = [];
    limpets = [];
    sfx.hit();
    ship.respawn = 110;
  }

  function finish() {
    cab.over({score: run.score, wave: run.wave, rank: Kit.rank(run.score, .4, "trade")});
  }

  function spawnPirate() {
    const kind = run.wave > 2 && chance(.45) ? "viper" : "sidewinder";
    const spec = PIRATES[kind];
    const side = chance(.5);
    pirates.push({kind, ...spec, x: side ? -20 : W + 20, y: between(60, H - 60), vx: 0, vy: 0, cool: spec.every, flash: 0, wobble: between(0, 6)});
    run.banner = {text: kind === "viper" ? "VIPER INBOUND" : "SIDEWINDER INBOUND", sub: "A PIRATE WANTS YOUR CARGO", t: 100, alarm: true};
    sfx.pirate();
  }

  function update() {
    for (const spark of sparks) { spark.x += spark.vx; spark.y += spark.vy; spark.vx *= .96; spark.vy *= .96; spark.life -= 1; }
    sparks = sparks.filter((spark) => spark.life > 0);
    for (const word of words) { word.y -= .5; word.life -= 1; }
    words = words.filter((word) => word.life > 0);
    for (const rock of rocks) { rock.x = wrap(rock.x + rock.vx, W); rock.y = wrap(rock.y + rock.vy, H); rock.angle += rock.spin; }
    if (cab.state !== "play") return;
    if (run.banner && --run.banner.t <= 0) run.banner = null;
    if (run.quake > 0) run.quake -= 1;

    if (ship.dead) {
      if (--ship.respawn <= 0) {
        if (run.lives <= 0) return finish();
        ship = newShip();
      }
    } else moveShip();

    for (const shot of shots) {
      shot.x = wrap(shot.x + shot.vx, W);
      shot.y = wrap(shot.y + shot.vy, H);
      shot.life -= 1;
      for (const rock of rocks) {
        if (!rock.dead && Math.hypot(shot.x - rock.x, shot.y - rock.y) < ROCK[rock.size].r) { shot.life = 0; breakRock(rock); break; }
      }
      for (const pirate of pirates) {
        if (shot.life > 0 && Math.hypot(shot.x - pirate.x, shot.y - pirate.y) < pirate.r + 3) {
          shot.life = 0;
          pirate.hp -= 1;
          pirate.flash = 6;
          if (pirate.hp <= 0) {
            pirate.dead = true;
            run.score += pirate.score;
            run.pirates += 1;
            say(pirate.x, pirate.y, String(pirate.score), colours.yellow);
            burst(pirate.x, pirate.y, [pirate.colour, colours.orange, "#ffffff"], 36, 4);
            sfx.hit();
          }
        }
      }
    }
    shots = shots.filter((shot) => shot.life > 0);
    rocks = rocks.filter((rock) => !rock.dead);

    for (const item of fragments) {
      item.x = wrap(item.x + item.vx, W);
      item.y = wrap(item.y + item.vy, H);
      item.vx *= .995;
      item.vy *= .995;
      item.spin += .05;
      item.life -= 1;
    }
    moveLimpets();
    fragments = fragments.filter((item) => item.life > 0 && !item.taken);
    movePirates();
    if (!ship.dead) {
      for (const rock of rocks) if (Math.hypot(rock.x - ship.x, rock.y - ship.y) < ROCK[rock.size].r * .85 + 9) hurtShip();
    }
    if (--pirateClock <= 0) {
      pirateClock = Math.max(600, 1400 - run.wave * 80) * between(.8, 1.2);
      if (pirates.length < 2) spawnPirate();
    }
    if (!rocks.length && !pirates.length) {
      if (!run.clearing) {
        run.clearing = 110;
        bank("FIELD CLEARED");
        const bonus = 400 * run.wave;
        run.score += bonus;
        run.banner = {text: `FIELD ${Kit.pad(run.wave)} MINED OUT`, sub: `BONUS ${bonus.toLocaleString()}`, t: 110};
      } else if (--run.clearing <= 0) {
        run.clearing = 0;
        nextWave();
      }
    }
  }

  function moveShip() {
    const turn = (cab.input.held(...Kit.RIGHT) ? 1 : 0) - (cab.input.held(...Kit.LEFT) ? 1 : 0);
    if (turn) {
      pointer.active = false;
      ship.angle += turn * .075;
    } else {
      const want = aim();
      if (want !== null) {
        let delta = Math.atan2(Math.sin(want - ship.angle), Math.cos(want - ship.angle));
        ship.angle += clamp(delta, -.11, .11);
      }
    }
    ship.thrusting = cab.input.held(...Kit.UP);
    if (ship.thrusting) {
      ship.vx += Math.cos(ship.angle) * .13;
      ship.vy += Math.sin(ship.angle) * .13;
      if (cab.tick % 5 === 0) sfx.thrust();
    }
    if (cab.input.held(...Kit.DOWN)) { ship.vx *= .95; ship.vy *= .95; }
    const speed = Math.hypot(ship.vx, ship.vy);
    if (speed > 6.5) { ship.vx *= 6.5 / speed; ship.vy *= 6.5 / speed; }
    ship.vx *= .992;
    ship.vy *= .992;
    ship.x = wrap(ship.x + ship.vx, W);
    ship.y = wrap(ship.y + ship.vy, H);
    if (ship.cool > 0) ship.cool -= 1;
    if (ship.guard > 0) ship.guard -= 1;
    if (cab.input.held("Space") || pointer.down) fire();
  }

  function moveLimpets() {
    for (const limpet of limpets) {
      limpet.life -= 1;
      const goal = limpet.carrying || limpet.target.taken ? ship : limpet.target;
      if (!limpet.carrying && (limpet.target.taken || limpet.target.life <= 0)) limpet.lost = true;
      const dx = goal.x - limpet.x, dy = goal.y - limpet.y, d = Math.hypot(dx, dy) || 1;
      limpet.x += dx / d * 3.4;
      limpet.y += dy / d * 3.4;
      if (!limpet.carrying && !limpet.lost && d < 8) {
        limpet.carrying = limpet.target.type;
        limpet.target.taken = true;
      } else if ((limpet.carrying || limpet.lost) && goal === ship && d < 12 && !ship.dead) {
        limpet.done = true;
        if (limpet.carrying) {
          hold.push(limpet.carrying);
          if (limpet.carrying === "core") run.cores += 1;
          say(ship.x, ship.y - 22, `${FRAGMENT[limpet.carrying].label} +1 T`, FRAGMENT[limpet.carrying].colour);
          sfx.collect();
          if (hold.length >= HOLD) bank("HOLD FULL · BANKED");
        } else limpetStock += 1;
      }
    }
    limpets = limpets.filter((limpet) => !limpet.done && limpet.life > 0);
  }

  function movePirates() {
    for (const pirate of pirates) {
      const target = ship.dead ? {x: W / 2, y: H / 2} : ship;
      const dx = target.x - pirate.x, dy = target.y - pirate.y, d = Math.hypot(dx, dy) || 1;
      const keep = pirate.kind === "viper" ? 140 : 200;
      const pull = d > keep ? 1 : -.6;
      pirate.wobble += .04;
      pirate.vx += (dx / d * pull + Math.cos(pirate.wobble) * .5) * .06;
      pirate.vy += (dy / d * pull + Math.sin(pirate.wobble * 1.3) * .5) * .06;
      const speed = Math.hypot(pirate.vx, pirate.vy);
      if (speed > pirate.speed) { pirate.vx *= pirate.speed / speed; pirate.vy *= pirate.speed / speed; }
      pirate.x += pirate.vx;
      pirate.y += pirate.vy;
      pirate.angle = Math.atan2(dy, dx);
      if (pirate.flash > 0) pirate.flash -= 1;
      if (--pirate.cool <= 0 && !ship.dead) {
        pirate.cool = pirate.every * between(.8, 1.3);
        const spread = (1 - pirate.aim) * .8;
        const a = pirate.angle + between(-spread, spread);
        bolts.push({x: pirate.x, y: pirate.y, vx: Math.cos(a) * 4.2, vy: Math.sin(a) * 4.2, life: 120});
        cab.sound.tone("square", 700, 300, .08, .08);
      }
      if (!ship.dead && d < pirate.r + 10) hurtShip();
    }
    pirates = pirates.filter((pirate) => !pirate.dead && pirate.x > -60 && pirate.x < W + 60);
    for (const bolt of bolts) {
      bolt.x += bolt.vx;
      bolt.y += bolt.vy;
      bolt.life -= 1;
      if (!ship.dead && Math.hypot(bolt.x - ship.x, bolt.y - ship.y) < 10) { bolt.life = 0; hurtShip(); }
    }
    bolts = bolts.filter((bolt) => bolt.life > 0 && bolt.x > -10 && bolt.x < W + 10 && bolt.y > -10 && bolt.y < H + 10);
  }

  // ---- Drawing. ----
  function drawRock(rock) {
    const r = ROCK[rock.size].r;
    ctx.save();
    ctx.translate(rock.x, rock.y);
    ctx.rotate(rock.angle);
    ctx.beginPath();
    rock.shape.forEach((k, i) => {
      const a = i / rock.shape.length * Math.PI * 2;
      ctx[i ? "lineTo" : "moveTo"](Math.cos(a) * r * k, Math.sin(a) * r * k);
    });
    ctx.closePath();
    ctx.fillStyle = "#0b1015";
    ctx.fill();
    const edge = rock.kind === "pristine" ? colours.accent : "#c9d3db";
    glow(edge, rock.kind === "pristine" ? 10 : 4);
    ctx.strokeStyle = edge;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.shadowBlur = 0;
    if (rock.kind === "core") {
      ctx.beginPath();
      ctx.arc(0, 0, r * .28 + Math.sin(cab.tick * .1) * 1.5, 0, Math.PI * 2);
      ctx.fillStyle = FRAGMENT.core.colour;
      glow(FRAGMENT.core.colour, 14);
      ctx.globalAlpha = .7;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.shadowBlur = 0;
    }
    ctx.restore();
  }

  function drawShip() {
    if (!ship || ship.dead || (ship.guard > 0 && Math.floor(ship.guard / 5) % 2)) return;
    ctx.save();
    ctx.translate(ship.x, ship.y);
    ctx.rotate(ship.angle);
    // A little Adder-ish prospector, nose to the right.
    ctx.beginPath();
    ctx.moveTo(16, 0);
    ctx.lineTo(-10, -11);
    ctx.lineTo(-6, 0);
    ctx.lineTo(-10, 11);
    ctx.closePath();
    ctx.fillStyle = colours.panel;
    ctx.fill();
    glow(colours.accent, 8);
    ctx.strokeStyle = colours.accent;
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.shadowBlur = 0;
    if (ship.thrusting) {
      ctx.beginPath();
      ctx.moveTo(-8, -4);
      ctx.lineTo(-16 - Math.random() * 8, 0);
      ctx.lineTo(-8, 4);
      ctx.strokeStyle = colours.orange;
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawPirate(pirate) {
    ctx.save();
    ctx.translate(pirate.x, pirate.y);
    ctx.rotate(pirate.angle);
    const colour = pirate.flash ? "#ffffff" : pirate.colour;
    ctx.beginPath();
    if (pirate.kind === "viper") {
      ctx.moveTo(17, 0); ctx.lineTo(-8, -12); ctx.lineTo(-12, -4); ctx.lineTo(-12, 4); ctx.lineTo(-8, 12);
    } else {
      ctx.moveTo(10, -6); ctx.lineTo(10, 6); ctx.lineTo(-10, 13); ctx.lineTo(-12, 0); ctx.lineTo(-10, -13);
    }
    ctx.closePath();
    ctx.fillStyle = "#1a0d0d";
    ctx.fill();
    glow(colour, 10);
    ctx.strokeStyle = colour;
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.restore();
    ctx.shadowBlur = 0;
  }

  function drawHud() {
    cab.scoreBar(run.score, "FIELD", run.wave);
    if (cab.state === "title") return;
    // The hold, a ton a cell.
    const cell = 12, gap = 3, x0 = 18, y0 = H - 30;
    text(`HOLD ${hold.length}/${HOLD} T`, x0, y0 - 8, 10, colours.dim, "left");
    for (let i = 0; i < HOLD; i += 1) {
      ctx.fillStyle = i < hold.length ? FRAGMENT[hold[i]].colour : "rgba(255,255,255,.07)";
      ctx.fillRect(x0 + i * (cell + gap), y0, cell, 10);
    }
    text(`LIMPETS ${limpetStock}`, W - 18, H - 38, 11, limpetStock ? colours.orange : colours.red, "right");
    text("E / SHIFT TO SEND ONE", W - 18, H - 22, 9, colours.dim, "right");
    for (let i = 0; i < Math.max(0, run.lives - (ship?.dead ? 0 : 1)); i += 1) {
      ctx.save();
      ctx.translate(26 + i * 22, 66);
      ctx.rotate(-Math.PI / 2);
      ctx.beginPath(); ctx.moveTo(9, 0); ctx.lineTo(-6, -6); ctx.lineTo(-3, 0); ctx.lineTo(-6, 6); ctx.closePath();
      ctx.strokeStyle = colours.accent; ctx.lineWidth = 1.2; ctx.stroke();
      ctx.restore();
    }
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 8, 8, colours.dim);
  }

  function draw() {
    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, 0, W, H);
    if (run.quake > 0) ctx.translate(between(-1, 1) * run.quake * .4, between(-1, 1) * run.quake * .4);
    rocks.forEach(drawRock);
    for (const item of fragments) {
      const spec = FRAGMENT[item.type];
      ctx.save();
      ctx.translate(item.x, item.y);
      ctx.rotate(item.spin);
      ctx.fillStyle = spec.colour;
      glow(spec.colour, item.type === "core" ? 14 : 6);
      const s = item.type === "core" ? 6 : 4;
      ctx.globalAlpha = item.life < 180 && Math.floor(item.life / 8) % 2 ? .3 : 1;
      ctx.beginPath(); ctx.moveTo(0, -s); ctx.lineTo(s, 0); ctx.lineTo(0, s); ctx.lineTo(-s, 0); ctx.closePath(); ctx.fill();
      ctx.restore();
      ctx.shadowBlur = 0;
      ctx.globalAlpha = 1;
    }
    for (const limpet of limpets) {
      ctx.fillStyle = colours.orange;
      ctx.fillRect(limpet.x - 3, limpet.y - 3, 6, 6);
      if (limpet.carrying) { ctx.fillStyle = FRAGMENT[limpet.carrying].colour; ctx.fillRect(limpet.x - 1.5, limpet.y - 1.5, 3, 3); }
    }
    pirates.forEach(drawPirate);
    ctx.fillStyle = colours.accent;
    for (const shot of shots) ctx.fillRect(shot.x - 1.5, shot.y - 1.5, 3, 3);
    ctx.fillStyle = colours.red;
    for (const bolt of bolts) ctx.fillRect(bolt.x - 2, bolt.y - 2, 4, 4);
    if (cab.state !== "title") drawShip();
    for (const spark of sparks) {
      ctx.globalAlpha = clamp(spark.life / 30, 0, 1);
      ctx.fillStyle = spark.colour;
      ctx.fillRect(spark.x - 1, spark.y - 1, 2, 2);
    }
    ctx.globalAlpha = 1;
    for (const word of words) {
      ctx.globalAlpha = clamp(word.life / 30, 0, 1);
      text(word.text, word.x, word.y, 11, word.colour);
    }
    ctx.globalAlpha = 1;
    ctx.setTransform(cab.scale, 0, 0, cab.scale, 0, 0);
    drawHud();
    const banner = run.banner;
    if (banner && cab.state === "play") {
      ctx.globalAlpha = clamp(banner.t / 30, 0, 1);
      text(banner.text, W / 2, H / 2 - 40, 30, banner.alarm ? colours.red : colours.text, "center", 700, Kit.DISPLAY);
      text(banner.sub, W / 2, H / 2 - 16, 12, banner.alarm ? colours.orange : colours.accent);
      ctx.globalAlpha = 1;
    }
    if (cab.state === "title") {
      cab.titleScreen({top: "ROCK", bottom: "RATS", tone: colours.accent, y: 170,
        rows: [["GRAVEL", "10 A TON"], ["PRISTINE (BLUE ROCKS)", "25 A TON"], ["CORE (THE GLOW INSIDE)", "150 A TON"],
          ["A FULL HOLD", "+50%"], ["SIDEWINDER · VIPER", "200 · 500"]],
        note: "LOSE THE SHIP AND YOU LOSE WHAT'S IN THE HOLD",
        how: "MOUSE TO AIM · CLICK TO FIRE · ↑ THRUST · E OR SHIFT FOR A LIMPET"});
    } else if (cab.state === "over") {
      cab.overScreen({heading: "SHIP LOST", tone: colours.red, sub: "MINING DEBRIEF", rankLabel: "TRADE RANK", rank: Kit.rank(run.score, .4, "trade"),
        lines: [["SCORE", run.score.toLocaleString()], ["FIELDS", run.wave], ["TONS BANKED", run.banked], ["CORES FOUND", run.cores], ["PIRATES DOWNED", run.pirates]]});
    }
  }

  function report() {
    return {score: run.score, wave: run.wave, lives: run.lives, rocks: rocks.length, hold: hold.length, limpets: limpetStock, fragments: fragments.length};
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
    nextWave();
    run.score = 3870;
    hold = ["gravel", "gravel", "pristine", "core", "gravel", "pristine", "gravel"];
    ship.guard = 0;
    ship.angle = -.9;
    for (let i = 0; i < 4; i += 1) breakRock(rocks[i]);
    rocks.push(newRock(2, ship.x + 90, ship.y - 80, "core"));
    spawnPirate();
    pirates[0].x = 520;
    pirates[0].y = 140;
    for (let i = 0; i < 40; i += 1) { cab.tick += 1; update(); if (i % 10 === 0) fire(); ship.guard = 5; }
    sendLimpet();
    sendLimpet();
    for (let i = 0; i < 12; i += 1) { cab.tick += 1; update(); }
    run.banner = null;
    words = [];
    ship.guard = 0;
  }

  window.rockRats = {state: () => ({...report(), state: cab.state})};
})();
