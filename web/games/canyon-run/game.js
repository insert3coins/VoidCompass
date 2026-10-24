// Canyon Run (5.6.3): a side-scrolling canyon, flown low and fast like the
// canyon racers do. The fuel is always running out: shoot or bomb the depots
// to fill up. Turrets, overhangs and narrow gaps on the way; every sector is
// against the clock, and flying low pays.
(() => {
  "use strict";

  const W = 600, H = 675, COLUMN = 20, SECTOR = 5200;
  const SECTORS = ["OPEN CANYON", "THE NARROWS", "OVERHANGS", "TURRET ALLEY"];
  const LOW = 46;
  const {clamp, between, chance, pick} = Kit;
  const colours = {bg: "#07050a", panel: "#140d10", accent: "#00d1ff", orange: "#ff8a3d", text: "#f1e8e2",
    muted: "#b39d93", dim: "#7a665d", green: "#54e39a", yellow: "#f5c76d", red: "#ff6b70"};
  const ROCK_TOP = "#d9774a", ROCK_FILL = "#2a1410";

  const cab = Kit.cabinet({width: W, height: H, colours, start: startGame, update, draw, report, end: debugOver, card, key});
  const {ctx} = cab;
  const {text, glow} = cab.draw;
  const pointer = cab.input.pointer;

  const run = {score: 0, lives: 3, fuel: 100, scroll: 0, speed: 3.2, clock: 0, sectorClock: 0, sector: 0, low: 0, kills: 0, depots: 0,
    banner: null, flash: 0, best: []};
  let ship = null, columns = [], objects = [], shots = [], bombs = [], bolts = [], sparks = [], words = [];
  let gen = null;

  const sfx = {
    shoot() { cab.sound.tone("square", 1300, 600, .05, .08); },
    bomb() { cab.sound.tone("sine", 700, 200, .35, .1); },
    boom() { cab.sound.hiss(.5, .6, 1500); cab.sound.tone("triangle", 220, 60, .3, .2); },
    fuel() { [523, 784, 1047].forEach((f, i) => cab.sound.tone("square", f, f, .07, .12, i * .06)); },
    crash() { cab.sound.hiss(1, .9, 1100); cab.sound.tone("sawtooth", 300, 30, .9, .3); },
    low() { cab.sound.tone("square", 520, 520, .07, .08); },
    checkpoint() { [392, 523, 659, 784, 1047].forEach((f, i) => cab.sound.tone("triangle", f, f, .12, .16, i * .07)); },
  };

  function key(code) {
    if (cab.state === "play" && ["KeyB", "KeyX", "ShiftLeft", "ShiftRight"].includes(code)) { dropBomb(); return true; }
    return false;
  }

  function startGame() {
    Object.assign(run, {score: 0, lives: 3, fuel: 100, scroll: 0, speed: 3.2, clock: 0, sectorClock: 0, sector: 0, low: 0, kills: 0, depots: 0,
      banner: null, flash: 0});
    seed();
    shots = []; bombs = []; bolts = []; sparks = []; words = [];
    ship = {x: 120, y: 260, vx: 0, vy: 0, cool: 0, bombCool: 0, guard: 120};
    pointer.active = false;
    run.banner = {text: SECTORS[0], sub: "SECTOR 1 · STAY LOW, KEEP FUELLED", t: 140};
  }

  function seed() {
    gen = {k: 0, floor: H - 110, ceil: -200, phase: [between(0, 9), between(0, 9), between(0, 9)]};
    columns = [];
    objects = [];
    while (columns.length < W / COLUMN + 4) generate();
  }

  function noise(k, i, scale) {
    const p = gen.phase;
    return Math.sin(k * scale + p[i]) * .6 + Math.sin(k * scale * 2.3 + p[(i + 1) % 3]) * .3 + Math.sin(k * scale * 5.1 + p[(i + 2) % 3]) * .1;
  }

  // One more column of canyon on the right.
  function generate() {
    const k = gen.k;
    const at = k * COLUMN;
    const sector = Math.floor(at / SECTOR) % 4, lap = Math.floor(at / SECTOR / 4);
    let floor, ceil;
    if (sector === 0) { floor = H - 120 + noise(k, 0, .08) * 70; ceil = -200; }
    else if (sector === 1) {
      floor = H - 170 + noise(k, 0, .06) * 110;
      ceil = floor - Math.max(118, 190 - lap * 20) + noise(k, 1, .1) * 20;
    } else if (sector === 2) {
      floor = H - 110 + noise(k, 0, .07) * 40;
      const dip = Math.max(0, Math.sin(k * .09 + gen.phase[1]));
      ceil = 70 + dip ** 3 * (floor - 70 - Math.max(120, 150 - lap * 10));
    } else { floor = H - 140 + noise(k, 0, .12) * 50; ceil = 40 + noise(k, 1, .05) * 30; }
    gen.floor += (floor - gen.floor) * .35;
    gen.ceil = ceil < -100 ? (gen.ceil < -100 ? -200 : gen.ceil - 12) : gen.ceil < -100 ? Math.max(ceil - 120, 0) : gen.ceil + (ceil - gen.ceil) * .35;
    if (gen.ceil > gen.floor - 110) gen.ceil = gen.floor - 110;
    columns.push({k, floor: gen.floor, ceil: gen.ceil});
    gen.k += 1;
    // Something on the ground now and then (never in the first stretch).
    if (k > 40 && k % 2 === 0) {
      const turret = sector === 3 ? .16 : sector === 0 ? .03 : .06;
      const roll = Math.random();
      if (roll < .045) objects.push({kind: "fuel", x: at, hp: 1});
      else if (roll < .045 + turret) objects.push({kind: "turret", x: at, hp: 1, cool: between(60, 160)});
      else if (roll < .045 + turret + .012) objects.push({kind: "dish", x: at, hp: 1});
    }
  }

  function column(worldX) {
    const index = Math.floor(worldX / COLUMN) - columns[0].k;
    const a = columns[clamp(index, 0, columns.length - 1)], b = columns[clamp(index + 1, 0, columns.length - 1)];
    const t = clamp(worldX / COLUMN - Math.floor(worldX / COLUMN), 0, 1);
    return {floor: a.floor + (b.floor - a.floor) * t, ceil: a.ceil + (b.ceil - a.ceil) * t};
  }

  function fire() {
    if (ship.cool > 0) return;
    shots.push({x: ship.x + 18, y: ship.y + 2, vx: 11});
    ship.cool = 10;
    sfx.shoot();
  }

  function dropBomb() {
    if (!ship || ship.dead || ship.bombCool > 0 || bombs.length >= 2) return;
    bombs.push({x: ship.x, y: ship.y + 8, vx: run.speed + 1.4, vy: 1});
    ship.bombCool = 28;
    sfx.bomb();
  }

  function burst(x, y, palette, count, speed = 3) {
    for (let i = 0; i < count; i += 1) {
      const a = between(0, Math.PI * 2), v = between(.5, speed);
      sparks.push({x, y, vx: Math.cos(a) * v - run.speed * .5, vy: Math.sin(a) * v, life: between(20, 45), colour: pick(palette)});
    }
  }

  function say(x, y, value, colour) {
    words.push({x, y, text: value, colour, life: 60});
  }

  function destroy(object) {
    object.dead = true;
    const sx = object.x - run.scroll, floor = column(object.x).floor;
    burst(sx, floor - 10, [colours.orange, colours.yellow, "#ffffff"], 22);
    sfx.boom();
    if (object.kind === "fuel") {
      run.fuel = Math.min(100, run.fuel + 28);
      run.depots += 1;
      run.score += 150;
      say(sx, floor - 30, "FUEL +28", colours.yellow);
      sfx.fuel();
    } else if (object.kind === "turret") {
      run.score += 100;
      run.kills += 1;
      say(sx, floor - 30, "100", colours.text);
    } else {
      run.score += 800;
      say(sx, floor - 30, "800", colours.accent);
    }
  }

  function crash(reason) {
    if (ship.dead || ship.guard > 0) return;
    ship.dead = true;
    ship.respawn = 100;
    run.lives -= 1;
    run.flash = 20;
    burst(ship.x, ship.y, [colours.accent, colours.orange, "#ffffff"], 50, 5);
    say(ship.x, ship.y - 20, reason, colours.red);
    sfx.crash();
  }

  function finish(reason) {
    run.reason = reason;
    cab.over({score: Math.round(run.score), wave: run.sector + 1, rank: Kit.rank(run.score, .3)});
  }

  function update() {
    for (const spark of sparks) { spark.x += spark.vx; spark.y += spark.vy; spark.vy += .05; spark.life -= 1; }
    sparks = sparks.filter((spark) => spark.life > 0);
    for (const word of words) { word.y -= .5; word.x -= run.speed * .3; word.life -= 1; }
    words = words.filter((word) => word.life > 0);
    if (cab.state !== "play") return;
    if (run.banner && --run.banner.t <= 0) run.banner = null;
    if (run.flash > 0) run.flash -= 1;
    const dt = 1 / 60;

    if (ship.dead) {
      if (--ship.respawn <= 0) {
        if (run.lives <= 0) return finish(run.fuel <= 0 ? "OUT OF FUEL" : "SHIP LOST");
        const here = column(run.scroll + 120);
        const top = here.ceil < -100 ? 60 : here.ceil;
        ship = {x: 120, y: (top + here.floor) / 2, vx: 0, vy: 0, cool: 0, bombCool: 0, guard: 140};
        run.fuel = Math.max(run.fuel, 45);
      }
    }

    run.clock += dt;
    run.sectorClock += dt;
    run.scroll += run.speed;
    while (columns.length > 2 && columns[1].k * COLUMN < run.scroll - COLUMN) columns.shift();
    while (columns[columns.length - 1].k * COLUMN < run.scroll + W + COLUMN * 2) generate();

    // A new sector: the clock's verdict, then faster.
    const sector = Math.floor(run.scroll / SECTOR);
    if (sector > run.sector) {
      const par = SECTOR / run.speed / 60;
      const bonus = 500 + Math.max(0, Math.round((par * 1.05 - run.sectorClock) * 150)) + run.low * 2;
      run.score += bonus;
      run.sector = sector;
      run.speed = Math.min(6, run.speed + .35);
      run.sectorClock = 0;
      run.banner = {text: `CHECKPOINT · ${SECTORS[sector % 4]}`, sub: `+${bonus.toLocaleString()} · LOW FLYING ${run.low}`, t: 150, good: true};
      run.low = 0;
      sfx.checkpoint();
    }

    if (!ship.dead) {
      run.fuel -= (.075 + run.sector * .006) * (run.speed / 3.2);
      if (run.fuel <= 0) { run.fuel = 0; run.lives = Math.min(run.lives, 1); crash("OUT OF FUEL"); }
      let mx = (cab.input.held(...Kit.RIGHT) ? 1 : 0) - (cab.input.held(...Kit.LEFT) ? 1 : 0);
      let my = (cab.input.held(...Kit.DOWN) ? 1 : 0) - (cab.input.held(...Kit.UP) ? 1 : 0);
      if (mx || my) pointer.active = false;
      else if (pointer.active) { mx = clamp((pointer.x - ship.x) / 40, -1, 1); my = clamp((pointer.y - ship.y) / 40, -1, 1); }
      ship.vx += (mx * 3 - ship.vx) * .2;
      ship.vy += (my * 3.6 - ship.vy) * .2;
      ship.x = clamp(ship.x + ship.vx, 30, W * .55);
      ship.y = clamp(ship.y + ship.vy, 20, H - 20);
      if (ship.cool > 0) ship.cool -= 1;
      if (ship.bombCool > 0) ship.bombCool -= 1;
      if (ship.guard > 0) ship.guard -= 1;
      if (cab.input.held("Space") || (pointer.down && pointer.button !== 2)) fire();
      if (pointer.down && pointer.button === 2) dropBomb();
      if (run.fuel < 20 && cab.tick % 45 === 0) sfx.low();

      // The rock: nose and tail against the floor and the roof.
      for (const dx of [-14, 0, 16]) {
        const here = column(run.scroll + ship.x + dx);
        if (ship.y + 7 > here.floor) crash("HIT THE FLOOR");
        else if (here.ceil > -100 && ship.y - 7 < here.ceil) crash("HIT THE ROOF");
      }
      const altitude = column(run.scroll + ship.x).floor - (ship.y + 7);
      if (!ship.dead && altitude < LOW) { run.low += 1; run.score += 1; }
    }

    for (const shot of shots) {
      shot.x += shot.vx;
      const here = column(run.scroll + shot.x);
      if (shot.y > here.floor || (here.ceil > -100 && shot.y < here.ceil)) shot.dead = true;
      for (const object of objects) {
        const sx = object.x - run.scroll, floor = column(object.x).floor;
        if (!object.dead && Math.abs(shot.x - sx) < 14 && shot.y > floor - 24 && shot.y < floor) { shot.dead = true; destroy(object); }
      }
    }
    shots = shots.filter((shot) => !shot.dead && shot.x < W + 10);
    for (const bomb of bombs) {
      bomb.vy += .12;
      bomb.x += bomb.vx - run.speed;
      bomb.y += bomb.vy;
      const floor = column(run.scroll + bomb.x).floor;
      if (bomb.y >= floor) {
        bomb.dead = true;
        burst(bomb.x, floor, [colours.orange, colours.yellow], 16);
        sfx.boom();
        for (const object of objects) if (!object.dead && Math.abs(object.x - run.scroll - bomb.x) < 26) destroy(object);
      }
    }
    bombs = bombs.filter((bomb) => !bomb.dead);

    for (const object of objects) {
      if (object.dead || object.kind !== "turret") continue;
      const sx = object.x - run.scroll;
      if (sx < 0 || sx > W || ship.dead) continue;
      if (--object.cool <= 0) {
        object.cool = Math.max(70, 150 - run.sector * 12) * between(.8, 1.3);
        const floor = column(object.x).floor;
        const a = Math.atan2(ship.y - (floor - 20), ship.x - sx);
        bolts.push({x: sx, y: floor - 20, vx: Math.cos(a) * 3.4 - run.speed * .2, vy: Math.sin(a) * 3.4});
        cab.sound.tone("square", 500, 260, .07, .06);
      }
    }
    objects = objects.filter((object) => !object.dead && object.x - run.scroll > -40);
    for (const bolt of bolts) {
      bolt.x += bolt.vx;
      bolt.y += bolt.vy;
      if (!ship.dead && Math.abs(bolt.x - ship.x) < 14 && Math.abs(bolt.y - ship.y) < 8) { bolt.dead = true; crash("SHOT DOWN"); }
    }
    bolts = bolts.filter((bolt) => !bolt.dead && bolt.x > -10 && bolt.x < W + 10 && bolt.y > -10 && bolt.y < H + 10);
  }

  // ---- Drawing. ----
  function drawCanyon() {
    const sky = ctx.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, "#0b0612");
    sky.addColorStop(1, "#2a1018");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, W, H);
    ctx.beginPath();
    ctx.arc(W * .72, 150, 70, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255, 150, 110, .14)";
    ctx.fill();
    // Far ridges, slower.
    ctx.fillStyle = "#1b0c10";
    ctx.beginPath();
    ctx.moveTo(0, H);
    for (let x = 0; x <= W; x += 12) ctx.lineTo(x, H - 240 + Math.sin((x + run.scroll * .3) * .012) * 40 + Math.sin((x + run.scroll * .3) * .031) * 18);
    ctx.lineTo(W, H);
    ctx.fill();
    const first = columns[0].k * COLUMN;
    const points = columns.map((item) => [item.k * COLUMN - run.scroll, item.floor, item.ceil]);
    ctx.beginPath();
    ctx.moveTo(points[0][0], H);
    for (const [x, floor] of points) ctx.lineTo(x, floor);
    ctx.lineTo(points[points.length - 1][0], H);
    ctx.closePath();
    const rock = ctx.createLinearGradient(0, H - 300, 0, H);
    rock.addColorStop(0, "#4a2216");
    rock.addColorStop(1, ROCK_FILL);
    ctx.fillStyle = rock;
    ctx.fill();
    ctx.beginPath();
    points.forEach(([x, floor], index) => ctx[index ? "lineTo" : "moveTo"](x, floor));
    ctx.strokeStyle = ROCK_TOP;
    ctx.lineWidth = 2;
    ctx.stroke();
    // The roof, where there is one.
    ctx.beginPath();
    let open = false;
    for (const [x, , ceil] of points) {
      if (ceil > -100) {
        if (!open) { ctx.moveTo(x, -2); open = true; }
        ctx.lineTo(x, ceil);
      } else if (open) { ctx.lineTo(x, -2); open = false; }
    }
    if (open) ctx.lineTo(points[points.length - 1][0], -2);
    ctx.fillStyle = "#3a1a12";
    ctx.fill();
    ctx.strokeStyle = ROCK_TOP;
    ctx.stroke();
    void first;
  }

  function drawObject(object) {
    const x = object.x - run.scroll, floor = column(object.x).floor;
    if (x < -30 || x > W + 30) return;
    ctx.save();
    ctx.translate(x, floor);
    if (object.kind === "fuel") {
      ctx.fillStyle = "#3a2a10";
      ctx.fillRect(-12, -24, 24, 24);
      ctx.strokeStyle = colours.yellow;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(-12, -24, 24, 24);
      text("FUEL", 0, -9, 8, colours.yellow);
    } else if (object.kind === "turret") {
      ctx.fillStyle = "#1c1c22";
      ctx.beginPath(); ctx.arc(0, 0, 13, Math.PI, 0); ctx.fill();
      ctx.strokeStyle = colours.red;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      const a = ship ? Math.atan2(ship.y - (floor - 10), ship.x - x) : -Math.PI / 2;
      ctx.beginPath(); ctx.moveTo(0, -8); ctx.lineTo(Math.cos(a) * 18, -8 + Math.sin(a) * 18); ctx.lineWidth = 3; ctx.stroke();
    } else {
      ctx.strokeStyle = colours.accent;
      ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -16); ctx.stroke();
      ctx.beginPath(); ctx.arc(0, -22, 10, Math.PI * .1 + cab.tick * .05, Math.PI * .9 + cab.tick * .05); ctx.stroke();
    }
    ctx.restore();
  }

  function drawShip() {
    if (!ship || ship.dead || (ship.guard > 0 && Math.floor(ship.guard / 5) % 2)) return;
    ctx.save();
    ctx.translate(ship.x, ship.y);
    ctx.rotate(clamp(ship.vy * .06, -.25, .25));
    ctx.fillStyle = colours.orange;
    glow(colours.orange, 10);
    ctx.fillRect(-22 - Math.random() * 6, -2, 8, 4);
    ctx.shadowBlur = 0;
    ctx.beginPath();
    ctx.moveTo(20, 2); ctx.lineTo(4, -6); ctx.lineTo(-14, -8); ctx.lineTo(-16, 6); ctx.lineTo(8, 7);
    ctx.closePath();
    ctx.fillStyle = "#0e1a22";
    ctx.fill();
    glow(colours.accent, 8);
    ctx.strokeStyle = colours.accent;
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.fillStyle = "rgba(0, 209, 255, .5)";
    ctx.fillRect(2, -4, 8, 3);
    ctx.restore();
  }

  function drawHud() {
    cab.scoreBar(Math.round(run.score), "SECTOR", run.sector + 1);
    if (cab.state === "title") return;
    text("FUEL", 18, 66, 10, colours.dim, "left");
    cab.draw.bar(18, 72, 140, 7, run.fuel / 100, run.fuel < 20 ? colours.red : colours.yellow);
    const minutes = Math.floor(run.clock / 60), seconds = (run.clock % 60).toFixed(1).padStart(4, "0");
    text(`${minutes}:${seconds}`, W / 2, 66, 14, colours.text);
    text(SECTORS[run.sector % 4], W / 2, 82, 9, colours.muted);
    const altitude = ship && !ship.dead ? column(run.scroll + ship.x).floor - (ship.y + 7) : 999;
    if (altitude < LOW && cab.state === "play") text("LOW · +1", W - 18, 66, 11, colours.green, "right");
    for (let i = 0; i < Math.max(0, run.lives - 1); i += 1) {
      ctx.fillStyle = colours.accent;
      ctx.fillRect(W - 26 - i * 16, 78, 10, 5);
    }
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 8, 8, colours.dim);
  }

  function draw() {
    drawCanyon();
    objects.forEach(drawObject);
    ctx.fillStyle = colours.accent;
    for (const shot of shots) ctx.fillRect(shot.x - 6, shot.y - 1, 12, 2);
    ctx.fillStyle = colours.yellow;
    for (const bomb of bombs) ctx.fillRect(bomb.x - 3, bomb.y - 3, 6, 6);
    ctx.fillStyle = colours.red;
    for (const bolt of bolts) { ctx.beginPath(); ctx.arc(bolt.x, bolt.y, 3, 0, Math.PI * 2); ctx.fill(); }
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
    if (run.flash > 0) { ctx.fillStyle = `rgba(255, 110, 70, ${run.flash / 50})`; ctx.fillRect(0, 0, W, H); }
    drawHud();
    const banner = run.banner;
    if (banner && cab.state === "play") {
      ctx.globalAlpha = clamp(banner.t / 30, 0, 1);
      text(banner.text, W / 2, 160, 26, banner.good ? colours.green : colours.text, "center", 700, Kit.DISPLAY);
      text(banner.sub, W / 2, 184, 11, colours.accent);
      ctx.globalAlpha = 1;
    }
    if (cab.state === "title") {
      cab.titleScreen({top: "CANYON", bottom: "RUN", tone: colours.orange, y: 160,
        rows: [["FUEL DEPOT", "150 + FUEL"], ["TURRET", "100"], ["RADAR DISH", "800"], ["UNDER PAR AT A CHECKPOINT", "TIME BONUS"],
          ["FLYING LOW", "+1 A STEP"]],
        note: "THE FUEL NEVER STOPS FALLING: SHOOT OR BOMB THE DEPOTS",
        how: "ARROWS OR MOUSE TO FLY · SPACE / CLICK FIRE · B / RIGHT-CLICK BOMB"});
    } else if (cab.state === "over") {
      cab.overScreen({heading: run.reason || "SHIP LOST", tone: colours.red, sub: "RUN DEBRIEF", rank: Kit.rank(run.score, .3),
        lines: [["SCORE", Math.round(run.score).toLocaleString()], ["SECTORS", run.sector + 1],
          ["TIME", `${Math.floor(run.clock / 60)}:${(run.clock % 60).toFixed(1).padStart(4, "0")}`], ["DEPOTS HIT", run.depots], ["TURRETS", run.kills]]});
    }
  }

  function report() {
    return {score: Math.round(run.score), sector: run.sector, fuel: run.fuel, lives: run.lives, objects: objects.length, clock: run.clock};
  }

  function debugOver() {
    run.score += 1234;
    run.lives = 1;
    ship.guard = 0;
    crash("TEST");
    ship.respawn = 1;
  }

  function card() {
    startGame();
    run.scroll = SECTOR * 2 - 600;
    gen.k = Math.floor(run.scroll / COLUMN) - 2;
    columns = [];
    objects = [];
    while (columns.length < W / COLUMN + 6) generate();
    for (let i = 0; i < 260; i += 1) {
      cab.tick += 1;
      ship.guard = 5;
      const here = column(run.scroll + ship.x + 40);
      ship.y = here.floor - 40;
      update();
      if (i % 12 === 0) fire();
    }
    run.score = 9120;
    run.fuel = 54;
    run.banner = null;
    ship.guard = 0;
  }

  seed();
  window.canyonRun = {state: () => ({...report(), state: cab.state})};
})();
