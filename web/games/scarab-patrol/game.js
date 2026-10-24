// Scarab Patrol (5.6.3): an SRV across a planet's surface, side-on, after
// the 80s moon-buggy classic. Hop craters and rocks on the Scarab's
// thrusters and shoot skimmer drones ahead and above. The deck sends the
// gravity of the world you're really at: low g is long floaty hops, high g
// short hard ones (and the warning goes red over 2 g).
(() => {
  "use strict";

  const W = 600, H = 675, GROUND = 540, CAR_X = 150, LEG = 1600;
  const {clamp, between, chance, pick} = Kit;
  const colours = {bg: "#020306", panel: "#0c1118", accent: "#00d1ff", orange: "#ff8a3d", text: "#e8eef3",
    muted: "#9aa9b5", dim: "#5f6f7c", green: "#54e39a", yellow: "#f5c76d", red: "#ff5b61"};
  const SKIMMER = "#ff6b70";

  const cab = Kit.cabinet({width: W, height: H, colours, start: startGame, update, draw, report, end: debugOver, card, onLive, key});
  const {ctx} = cab;
  const {text, glow} = cab.draw;
  const pointer = cab.input.pointer;

  const run = {score: 0, lives: 3, distance: 0, waypoint: 0, legClock: 0, banner: null, flash: 0, jumps: 0, kills: 0, quake: 0};
  let car = null, world = null, live = null, things = [], skimmers = [], shots = [], bombs = [], sparks = [], words = [], next = 0, waveClock = 0;
  const stars = Array.from({length: 110}, () => ({x: between(0, W), y: between(0, GROUND - 160), a: between(.2, 1)}));
  const ridges = [0, 1].map((layer) => Array.from({length: 24}, () => between(40, layer ? 70 : 140)));

  const sfx = {
    jump() { cab.sound.hiss(.3, .35, 900); cab.sound.tone("sine", 180, 420, .25, .12); },
    land() { cab.sound.tone("triangle", 120, 60, .12, .18); },
    shoot() { cab.sound.tone("square", 1100, 500, .05, .08); cab.sound.tone("square", 1500, 900, .04, .05, .02); },
    pop() { cab.sound.hiss(.25, .45, 2400); cab.sound.tone("triangle", 300, 80, .15, .16); },
    crash() { cab.sound.hiss(1, .9, 1100); cab.sound.tone("sawtooth", 260, 30, .9, .3); },
    waypoint() { [523, 659, 784, 1047].forEach((f, i) => cab.sound.tone("square", f, f, .1, .12, i * .08)); },
    bomb() { cab.sound.tone("sine", 900, 300, .4, .06); },
  };

  function onLive(data) {
    live = data && Number(data.gravity) > 0 ? {body: String(data.body || "THIS WORLD"), gravity: Number(data.gravity)} : null;
  }

  function key(code) {
    if (cab.state !== "play") return false;
    if (["Space", "ArrowUp", "KeyW"].includes(code)) { jump(); return true; }
    return false;
  }

  function madeUpWorld() {
    const name = `${pick(["HIP", "COL 285 SECTOR", "SYNUEFE", "PRAEA EUQ", "OUTOTZ", "WREGOE"])} ${Math.floor(between(10, 9999))} ${Math.floor(between(1, 9))} ${"ABCDEF"[Math.floor(between(0, 6))]}`;
    return {body: name, gravity: Math.round(pick([between(.08, .3), between(.25, .9), between(.6, 1.5), between(1.4, 2.6)]) * 100) / 100, real: false};
  }

  // Low g floats, high g drops like a stone: air time goes as 1/√g-ish.
  function physics() {
    const g = clamp(world.gravity, .08, 4);
    return {fall: .16 * g ** .75, lift: 4.2 * g ** .3};
  }

  function startGame() {
    Object.assign(run, {score: 0, lives: 3, distance: 0, waypoint: 0, legClock: 0, banner: null, flash: 0, jumps: 0, kills: 0, quake: 0});
    world = live ? {...live, real: true} : madeUpWorld();
    pointer.active = false;
    things = []; skimmers = []; shots = []; bombs = []; sparks = []; words = [];
    next = 500;
    waveClock = 400;
    newCar();
    run.banner = {text: world.real ? "YOUR WORLD" : "PATROL START", sub: `${world.body.toUpperCase()} · ${world.gravity.toFixed(2)} G`, t: 170, heavy: world.gravity > 2};
  }

  function newCar() {
    car = {y: GROUND, vy: 0, air: false, speed: 3.6, cool: 0, guard: 120, tilt: 0, bounce: 0, dead: false};
  }

  function jump() {
    if (!car || car.dead || car.air) return;
    car.vy = -physics().lift;
    car.air = true;
    run.jumps += 1;
    sfx.jump();
  }

  function fire() {
    if (car.cool > 0) return;
    shots.push({x: CAR_X + 36, y: car.y - 16, vx: 9, vy: 0, life: 50});
    shots.push({x: CAR_X - 2, y: car.y - 30, vx: car.speed * .2, vy: -9, life: 60});
    car.cool = 12;
    sfx.shoot();
  }

  // What's on the road ahead, by distance; it gets busier the further you go.
  function spawnAhead() {
    while (next < run.distance + W + 200) {
      const level = Math.min(run.waypoint, 10);
      const roll = Math.random();
      if (roll < .38) things.push({kind: "crater", x: next, w: between(40, 70 + level * 6)});
      else if (roll < .7) things.push({kind: "rock", x: next, w: 22, h: 18, hp: 1});
      else if (roll < .85) things.push({kind: "boulder", x: next, w: 34, h: 32, hp: 2});
      else things.push({kind: "mine", x: next, w: 18, h: 8, hp: 1});
      next += between(220, 420) * (1 - level * .04);
    }
  }

  function burst(x, y, palette, count, speed = 3) {
    for (let i = 0; i < count; i += 1) {
      const a = between(Math.PI, Math.PI * 2), v = between(.5, speed);
      sparks.push({x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: between(20, 45), colour: pick(palette)});
    }
  }

  function say(x, y, value, colour) {
    words.push({x, y, text: value, colour, life: 60});
  }

  function crash(reason) {
    if (car.dead || car.guard > 0) return;
    car.dead = true;
    car.respawn = 120;
    run.lives -= 1;
    run.flash = 22;
    run.quake = 20;
    burst(CAR_X, car.y - 12, [colours.orange, colours.yellow, "#ffffff"], 50, 5);
    say(CAR_X, car.y - 60, reason, colours.red);
    sfx.crash();
  }

  function finish() {
    cab.over({score: run.score, wave: run.waypoint, rank: Kit.rank(run.score, .3, "explore")});
  }

  function update() {
    for (const spark of sparks) { spark.x += spark.vx; spark.y += spark.vy; spark.vy += .08; spark.life -= 1; }
    sparks = sparks.filter((spark) => spark.life > 0);
    for (const word of words) { word.y -= .5; word.life -= 1; }
    words = words.filter((word) => word.life > 0);
    if (cab.state !== "play") return;
    if (run.banner && --run.banner.t <= 0) run.banner = null;
    if (run.flash > 0) run.flash -= 1;
    if (run.quake > 0) run.quake -= 1;

    if (car.dead) {
      if (--car.respawn <= 0) {
        if (run.lives <= 0) return finish();
        // Back a little, onto clear ground.
        things = things.filter((thing) => thing.x - run.distance > 260 || thing.x - run.distance < -100);
        newCar();
      }
      return;
    }

    // Speed: right is faster, left slower (or where the mouse is across the screen).
    let want = car.speed;
    if (cab.input.held(...Kit.RIGHT)) { want = 6.2; pointer.active = false; }
    else if (cab.input.held(...Kit.LEFT)) { want = 2; pointer.active = false; }
    else if (pointer.active) want = 2 + clamp(pointer.x / W, 0, 1) * 4.2;
    else want = 3.6;
    car.speed += (want - car.speed) * .05;
    run.distance += car.speed;
    run.score += car.speed * .05;
    run.legClock += 1;
    if (car.cool > 0) car.cool -= 1;
    if (car.guard > 0) car.guard -= 1;
    if (cab.input.held("KeyF", "Enter", "ShiftLeft") || (pointer.down && pointer.button !== 2)) fire();
    if (pointer.down && pointer.button === 2) jump();

    const {fall} = physics();
    if (car.air) {
      car.vy += fall;
      car.y += car.vy;
      if (car.y >= GROUND) {
        car.y = GROUND;
        car.vy = 0;
        car.air = false;
        car.bounce = 6;
        sfx.land();
      }
    }
    if (car.bounce > 0) car.bounce -= 1;
    car.tilt += ((car.air ? car.vy * .03 : 0) - car.tilt) * .2;

    // A waypoint every so often: the clock's verdict.
    const waypoint = Math.floor(run.distance / LEG);
    if (waypoint > run.waypoint) {
      run.waypoint = waypoint;
      const par = LEG / 4 / 60;
      const seconds = run.legClock / 60;
      const bonus = 500 + Math.max(0, Math.round((par - seconds) * 200));
      run.score += bonus;
      run.legClock = 0;
      run.banner = {text: `WAYPOINT ${String.fromCharCode(64 + Math.min(26, waypoint))}`, sub: `${seconds.toFixed(1)} S · PAR ${par.toFixed(1)} · +${bonus}`, t: 140, good: true};
      sfx.waypoint();
    }

    spawnAhead();
    // The road: craters to clear, rocks to clear or shoot.
    for (const thing of things) {
      const sx = thing.x - run.distance;
      if (thing.kind === "crater") {
        const over = CAR_X + 18 > sx + 6 && CAR_X - 18 < sx + thing.w - 6;
        if (over && !car.air) crash("INTO A CRATER");
        if (!thing.cleared && sx + thing.w < CAR_X - 20) { thing.cleared = true; run.score += 40; say(CAR_X, GROUND - 70, "+40", colours.text); }
      } else if (!thing.dead) {
        const over = CAR_X + 26 > sx && CAR_X - 22 < sx + thing.w;
        if (over && car.y > GROUND - thing.h - 2) crash(thing.kind === "mine" ? "HIT A MINE" : "HIT A ROCK");
        if (!thing.cleared && sx + thing.w < CAR_X - 24) { thing.cleared = true; run.score += 60; say(CAR_X, GROUND - 70, "+60", colours.text); }
      }
    }
    things = things.filter((thing) => thing.x - run.distance > -200 && !thing.dead);

    // Skimmers come over in threes and drop bombs.
    if (--waveClock <= 0) {
      waveClock = Math.max(200, 520 - run.waypoint * 30) * between(.8, 1.2);
      const count = Math.min(2 + Math.floor(run.waypoint / 2), 5);
      for (let i = 0; i < count; i += 1) skimmers.push({x: W + 40 + i * 50, y: between(150, 300), phase: between(0, 6), cool: between(40, 120), hp: 1, base: between(150, 300)});
    }
    for (const skimmer of skimmers) {
      skimmer.phase += .04;
      skimmer.x += Math.sin(skimmer.phase * .7) * 2.2 - .6;
      if (skimmer.x < 60) skimmer.x += 2;
      skimmer.y = skimmer.base + Math.sin(skimmer.phase) * 50;
      if (--skimmer.cool <= 0) {
        skimmer.cool = Math.max(50, 140 - run.waypoint * 8) * between(.7, 1.3);
        bombs.push({x: skimmer.x, y: skimmer.y + 8, vy: 0});
        sfx.bomb();
      }
    }
    for (const bomb of bombs) {
      bomb.vy += fall * .7;
      bomb.y += bomb.vy;
      bomb.x -= car.speed * .15;
      if (Math.abs(bomb.x - CAR_X) < 22 && bomb.y > car.y - 34 && bomb.y < car.y) { bomb.dead = true; crash("BOMBED"); }
      else if (bomb.y >= GROUND) {
        bomb.dead = true;
        burst(bomb.x, GROUND, ["#c9b79a", colours.orange], 16, 3);
        // It leaves a small crater where it fell.
        if (bomb.x > CAR_X + 60) things.push({kind: "crater", x: bomb.x + run.distance - 18, w: 36});
      }
    }
    bombs = bombs.filter((bomb) => !bomb.dead);

    for (const shot of shots) {
      shot.x += shot.vx;
      shot.y += shot.vy;
      shot.life -= 1;
      for (const skimmer of skimmers) {
        if (!skimmer.dead && Math.abs(shot.x - skimmer.x) < 18 && Math.abs(shot.y - skimmer.y) < 12) {
          skimmer.dead = true;
          shot.life = 0;
          run.kills += 1;
          run.score += 100;
          say(skimmer.x, skimmer.y - 12, "100", colours.yellow);
          burst(skimmer.x, skimmer.y, [SKIMMER, colours.yellow, "#ffffff"], 24, 3);
          sfx.pop();
        }
      }
      if (shot.vy === 0) {
        for (const thing of things) {
          if (thing.kind === "crater" || thing.dead) continue;
          const sx = thing.x - run.distance;
          if (shot.x > sx && shot.x < sx + thing.w && shot.y > GROUND - thing.h - 4) {
            shot.life = 0;
            thing.hp -= 1;
            burst(sx + thing.w / 2, GROUND - thing.h / 2, ["#c9b79a", "#ffffff"], 10, 2.5);
            if (thing.hp <= 0) {
              thing.dead = true;
              const points = thing.kind === "boulder" ? 150 : thing.kind === "mine" ? 80 : 50;
              run.score += points;
              say(sx + thing.w / 2, GROUND - 40, String(points), colours.text);
              sfx.pop();
            } else cab.sound.tone("square", 200, 160, .05, .12);
            break;
          }
        }
      }
    }
    shots = shots.filter((shot) => shot.life > 0 && shot.y > 0 && shot.x < W + 10);
    skimmers = skimmers.filter((skimmer) => !skimmer.dead);
  }

  // ---- Drawing. ----
  function drawSky() {
    const sky = ctx.createLinearGradient(0, 0, 0, GROUND);
    sky.addColorStop(0, "#010205");
    sky.addColorStop(1, "#141018");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, W, GROUND);
    for (const star of stars) {
      ctx.globalAlpha = star.a * .8;
      ctx.fillStyle = "#ffffff";
      ctx.fillRect((star.x - run.distance * .02 + W * 10) % W, star.y, 1.4, 1.4);
    }
    ctx.globalAlpha = 1;
    // The parent world, huge, with its rings.
    const cx = W * .72, cy = 190;
    const planet = ctx.createRadialGradient(cx - 60, cy - 50, 10, cx, cy, 130);
    planet.addColorStop(0, "#d9a46a"); planet.addColorStop(.6, "#7a4a2a"); planet.addColorStop(1, "#1a0f08");
    ctx.fillStyle = planet;
    ctx.beginPath(); ctx.arc(cx, cy, 120, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "rgba(255, 220, 180, .35)";
    ctx.lineWidth = 3;
    ctx.beginPath(); ctx.ellipse(cx, cy, 210, 36, -.3, 0, Math.PI * 2); ctx.stroke();
    // Two ridges, far and near, at their own speeds.
    ridges.forEach((heights, layer) => {
      const speed = layer ? .35 : .12, base = GROUND - (layer ? 30 : 70);
      ctx.fillStyle = layer ? "#1c1a20" : "#121117";
      ctx.beginPath();
      ctx.moveTo(0, GROUND);
      const span = 80;
      const offset = (run.distance * speed) % span;
      for (let i = -1; i <= W / span + 1; i += 1) {
        const index = ((Math.floor(run.distance * speed / span) + i) % heights.length + heights.length) % heights.length;
        ctx.lineTo(i * span - offset, base - heights[index]);
      }
      ctx.lineTo(W, GROUND);
      ctx.closePath();
      ctx.fill();
    });
  }

  function drawGround() {
    ctx.fillStyle = "#3a3632";
    ctx.fillRect(0, GROUND, W, H - GROUND);
    const top = ctx.createLinearGradient(0, GROUND, 0, H);
    top.addColorStop(0, "#5a544c");
    top.addColorStop(1, "#1a1816");
    ctx.fillStyle = top;
    ctx.fillRect(0, GROUND, W, H - GROUND);
    ctx.fillStyle = "rgba(0,0,0,.25)";
    for (let i = 0; i < 40; i += 1) {
      const x = ((i * 97 - run.distance) % (W + 40) + W + 40) % (W + 40) - 20;
      ctx.fillRect(x, GROUND + 8 + (i * 37) % 90, 10 + (i % 4) * 6, 2);
    }
    for (const thing of things) {
      const x = thing.x - run.distance;
      if (x > W + 40 || x + thing.w < -40) continue;
      if (thing.kind === "crater") {
        ctx.fillStyle = "#070608";
        ctx.beginPath();
        ctx.moveTo(x, GROUND);
        ctx.quadraticCurveTo(x + thing.w / 2, GROUND + 46, x + thing.w, GROUND);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = "#6a6258";
        ctx.fillRect(x - 6, GROUND - 3, 8, 3);
        ctx.fillRect(x + thing.w - 2, GROUND - 3, 8, 3);
      } else if (thing.kind === "mine") {
        ctx.fillStyle = "#2a1a1a";
        ctx.fillRect(x, GROUND - thing.h, thing.w, thing.h);
        ctx.fillStyle = Math.floor(cab.tick / 10) % 2 ? colours.red : "#401010";
        ctx.beginPath(); ctx.arc(x + thing.w / 2, GROUND - thing.h, 3, 0, Math.PI * 2); ctx.fill();
      } else {
        ctx.fillStyle = thing.kind === "boulder" ? "#6a6058" : "#7a7066";
        ctx.beginPath();
        ctx.moveTo(x, GROUND);
        ctx.lineTo(x + 3, GROUND - thing.h * .7);
        ctx.lineTo(x + thing.w * .4, GROUND - thing.h);
        ctx.lineTo(x + thing.w * .8, GROUND - thing.h * .85);
        ctx.lineTo(x + thing.w, GROUND);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,.2)";
        ctx.stroke();
        if (thing.hp < (thing.kind === "boulder" ? 2 : 1)) {
          ctx.strokeStyle = "rgba(0,0,0,.6)";
          ctx.beginPath(); ctx.moveTo(x + 8, GROUND - thing.h + 4); ctx.lineTo(x + thing.w / 2, GROUND - 6); ctx.stroke();
        }
      }
    }
    ctx.fillStyle = "#8a8070";
    ctx.fillRect(0, GROUND, W, 2);
  }

  function drawScarab() {
    if (!car || car.dead || (car.guard > 0 && Math.floor(car.guard / 5) % 2)) return;
    const y = car.y - (car.bounce ? Math.sin(car.bounce / 6 * Math.PI) * -3 : 0);
    ctx.save();
    ctx.translate(CAR_X, y);
    ctx.rotate(car.tilt);
    // Thrusters lit while it's in the air.
    if (car.air && car.vy < 1) {
      ctx.fillStyle = colours.accent;
      glow(colours.accent, 16);
      for (const x of [-20, 20]) ctx.fillRect(x - 3, -4, 6, 8 + Math.random() * 8);
      ctx.shadowBlur = 0;
    }
    // Six wheels on long legs.
    const spin = run.distance * .2;
    for (const [x, side] of [[-24, 1], [0, 1], [24, 1]]) {
      const drop = car.air ? 6 : 0;
      ctx.strokeStyle = "#5a636e";
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.moveTo(x, -16); ctx.lineTo(x, -8 + drop); ctx.stroke();
      ctx.beginPath(); ctx.arc(x, -8 + drop, 8, 0, Math.PI * 2);
      ctx.fillStyle = "#14171c"; ctx.fill();
      ctx.strokeStyle = "#8a96a3"; ctx.lineWidth = 1.6; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x + Math.cos(spin) * 7, -8 + drop + Math.sin(spin) * 7); ctx.lineTo(x - Math.cos(spin) * 7, -8 + drop - Math.sin(spin) * 7); ctx.stroke();
      void side;
    }
    // The body, the cab's glass and the turret on top.
    ctx.beginPath();
    ctx.moveTo(-34, -16); ctx.lineTo(-30, -30); ctx.lineTo(8, -32); ctx.lineTo(30, -26); ctx.lineTo(36, -16);
    ctx.closePath();
    const hull = ctx.createLinearGradient(0, -32, 0, -16);
    hull.addColorStop(0, "#d7dde3"); hull.addColorStop(1, "#6e7884");
    ctx.fillStyle = hull;
    ctx.fill();
    ctx.strokeStyle = colours.orange;
    ctx.lineWidth = 1.4;
    ctx.stroke();
    ctx.beginPath(); ctx.moveTo(10, -31); ctx.lineTo(28, -26); ctx.lineTo(24, -20); ctx.lineTo(8, -22); ctx.closePath();
    ctx.fillStyle = "rgba(0, 209, 255, .65)"; ctx.fill();
    ctx.fillStyle = "#3a424c";
    ctx.fillRect(-12, -40, 16, 8);
    ctx.fillRect(-4, -46, 3, 8);
    ctx.fillRect(2, -38, 14, 3);
    ctx.fillStyle = colours.orange;
    ctx.fillRect(-30, -22, 10, 3);
    ctx.restore();
  }

  function drawSkimmer(skimmer) {
    ctx.save();
    ctx.translate(skimmer.x, skimmer.y);
    ctx.rotate(Math.sin(skimmer.phase) * .2);
    ctx.beginPath();
    ctx.moveTo(-16, 0); ctx.lineTo(-6, -6); ctx.lineTo(6, -6); ctx.lineTo(16, 0); ctx.lineTo(6, 5); ctx.lineTo(-6, 5);
    ctx.closePath();
    ctx.fillStyle = "#22262c";
    ctx.fill();
    glow(SKIMMER, 10);
    ctx.strokeStyle = SKIMMER;
    ctx.lineWidth = 1.4;
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.fillStyle = Math.floor(cab.tick / 6) % 2 ? SKIMMER : "#ffffff";
    ctx.beginPath(); ctx.arc(0, 0, 2.6, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }

  function drawHud() {
    cab.scoreBar(Math.round(run.score), "WAYPOINT", run.waypoint);
    if (cab.state === "title" || !world) return;
    const heavy = world.gravity > 2;
    text(world.body.toUpperCase(), W / 2, 70, 10, colours.muted);
    text(`${world.gravity.toFixed(2)} G${world.real ? " · FROM YOUR JOURNAL" : ""}`, W / 2, 86, heavy ? 13 : 11, heavy ? colours.red : colours.text);
    if (heavy && Math.floor(cab.tick / 25) % 2) text("HIGH GRAVITY", W / 2, 104, 12, colours.red);
    // How far to the next waypoint.
    const share = (run.distance % LEG) / LEG;
    ctx.fillStyle = "rgba(255,255,255,.08)";
    ctx.fillRect(18, H - 30, W - 36, 5);
    ctx.fillStyle = colours.accent;
    ctx.fillRect(18, H - 30, (W - 36) * share, 5);
    text(`NEXT ${String.fromCharCode(65 + Math.min(25, run.waypoint))}`, W - 18, H - 38, 9, colours.dim, "right");
    text(`${Math.round(car?.speed * 12 || 0)} M/S`, 18, H - 38, 10, colours.text, "left");
    for (let i = 0; i < Math.max(0, run.lives - (car?.dead ? 0 : 1)); i += 1) { ctx.fillStyle = colours.orange; ctx.fillRect(W - 30 - i * 16, 70, 10, 5); }
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 8, 8, colours.dim);
  }

  function draw() {
    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, 0, W, H);
    if (run.quake > 0) ctx.translate(between(-1, 1) * run.quake * .4, between(-1, 1) * run.quake * .4);
    drawSky();
    drawGround();
    skimmers.forEach(drawSkimmer);
    ctx.fillStyle = colours.yellow;
    for (const bomb of bombs) { ctx.beginPath(); ctx.arc(bomb.x, bomb.y, 3.5, 0, Math.PI * 2); ctx.fill(); }
    ctx.fillStyle = colours.accent;
    for (const shot of shots) shot.vy === 0 ? ctx.fillRect(shot.x - 8, shot.y - 1, 16, 2) : ctx.fillRect(shot.x - 1, shot.y - 8, 2, 16);
    if (cab.state !== "title") drawScarab();
    for (const spark of sparks) {
      ctx.globalAlpha = clamp(spark.life / 30, 0, 1);
      ctx.fillStyle = spark.colour;
      ctx.fillRect(spark.x - 1.5, spark.y - 1.5, 3, 3);
    }
    ctx.globalAlpha = 1;
    for (const word of words) {
      ctx.globalAlpha = clamp(word.life / 30, 0, 1);
      text(word.text, word.x, word.y, 11, word.colour);
    }
    ctx.globalAlpha = 1;
    ctx.setTransform(cab.scale, 0, 0, cab.scale, 0, 0);
    if (run.flash > 0) { ctx.fillStyle = `rgba(255, 120, 60, ${run.flash / 50})`; ctx.fillRect(0, 0, W, H); }
    drawHud();
    const banner = run.banner;
    if (banner && cab.state === "play") {
      ctx.globalAlpha = clamp(banner.t / 30, 0, 1);
      text(banner.text, W / 2, 170, 28, banner.good ? colours.green : colours.text, "center", 700, Kit.DISPLAY);
      if (banner.sub) text(banner.sub, W / 2, 194, 11, banner.heavy ? colours.red : colours.accent);
      ctx.globalAlpha = 1;
    }
    if (cab.state === "title") {
      const note = live ? `YOU'RE AT ${live.body.toUpperCase()} · ${live.gravity.toFixed(2)} G: WE DRIVE THERE` : "AWAY FROM ANY WORLD: WE'LL FIND ONE";
      cab.titleScreen({top: "SCARAB", bottom: "PATROL", tone: colours.orange, y: 160,
        rows: [["SKIMMER DRONE", "100"], ["ROCK · BOULDER", "50 · 150"], ["CLEARED A CRATER", "40"], ["WAYPOINT UNDER PAR", "TIME BONUS"]],
        note, how: "SPACE / ↑ / RIGHT-CLICK HOP · F / CLICK FIRE · ← → OR MOUSE FOR SPEED"});
    } else if (cab.state === "over") {
      cab.overScreen({heading: "SRV LOST", tone: colours.red, sub: "PATROL DEBRIEF", rankLabel: "EXPLORER RANK", rank: Kit.rank(run.score, .3, "explore"),
        lines: [["SCORE", Math.round(run.score).toLocaleString()], ["WAYPOINTS", run.waypoint], ["HOPS", run.jumps], ["SKIMMERS DOWNED", run.kills],
          ["GRAVITY", `${world.gravity.toFixed(2)} G`]]});
    }
  }

  function report() {
    return {score: Math.round(run.score), waypoint: run.waypoint, lives: run.lives, distance: run.distance, air: Boolean(car?.air),
      gravity: world?.gravity ?? null, body: world?.body ?? "", real: Boolean(world?.real)};
  }

  function debugOver() {
    run.score += 1234;
    run.lives = 1;
    car.guard = 0;
    crash("TEST");
    car.respawn = 1;
  }

  function card() {
    startGame();
    world = {body: "COL 285 SECTOR KZ-C B14-3 2 A", gravity: .46, real: false};
    run.banner = null;
    run.score = 4820;
    run.waypoint = 3;
    run.distance = LEG * 3 + 300;
    things = [{kind: "crater", x: run.distance + 190, w: 70}, {kind: "boulder", x: run.distance + 420, w: 34, h: 32, hp: 2},
      {kind: "rock", x: run.distance + 560, w: 22, h: 18, hp: 1}];
    next = run.distance + 800;
    skimmers = [{x: 330, y: 200, phase: 1, cool: 999, base: 210}, {x: 420, y: 240, phase: 2, cool: 999, base: 240}, {x: 510, y: 180, phase: 3, cool: 999, base: 190}];
    bombs = [{x: 300, y: 330, vy: 1}];
    car.guard = 0;
    car.air = true;
    car.y = GROUND - 60;
    car.vy = -1;
    shots = [{x: CAR_X + 120, y: car.y - 16, vx: 9, vy: 0, life: 60}, {x: CAR_X - 2, y: car.y - 140, vx: .7, vy: -9, life: 60}];
  }

  window.scarabPatrol = {state: () => ({...report(), state: cab.state})};
})();
