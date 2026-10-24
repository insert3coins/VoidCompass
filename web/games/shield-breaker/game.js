// Shield Breaker (5.6.3): bounce a shot off your ship to break a capital
// ship's shield panels, then its hull plates. Panels take two hits, armour
// three; each level is another ship's silhouette.
(() => {
  "use strict";

  const W = 600, H = 675, COLS = 20, CELL = 28, BRICK_H = 15, LEFT = (W - COLS * CELL) / 2, TOP = 96;
  const {clamp, between, chance, pick} = Kit;
  const colours = {bg: "#03050a", panel: "#0b1220", accent: "#00d1ff", orange: "#ff8a3d", text: "#e4eef5",
    muted: "#95a7b6", dim: "#5d6f7e", green: "#54e39a", yellow: "#f5c76d", red: "#ff6b70"};
  const KINDS = {
    shield: {hp: 2, score: 20, colour: "#3fd7ff"},
    hull: {hp: 1, score: 10, colour: "#8c9aa8"},
    armour: {hp: 3, score: 50, colour: "#f5c76d"},
    core: {hp: 2, score: 200, colour: "#ff5fd2"},
  };
  // The silhouettes, nose to the right: H is the ship, A armour, C its core.
  const SHIPS = [
    {name: "FARRAGUT BATTLE CRUISER", rows: [
      "......HH............", ".....HHHH...........", "..HHHHHHHHHHH.......", "HHHHHHHAHHHHHHHHH...",
      "HHHHHHHHHHCHHHHHHHHH", "HHHHHHHAHHHHHHHHH...", "..HHHHHHHHHHH.......", ".....HHHH...........", "......HH............"]},
    {name: "MAJESTIC INTERDICTOR", rows: [
      "HHHH................", "HHHHHH..............", "HHHHHHHHHHHHHHH.....", "HHAHHHHHHHHHHHHHHHHH",
      "HHHHHHHCHHHHHAHHHHHH", "HHAHHHHHHHHHHHHHHHHH", "HHHHHHHHHHHHHHH.....", "HHHHHH..............", "HHHH................"]},
    {name: "THARGOID TITAN", rows: [
      ".......HHHHHH.......", "....HHH.HHHH.HHH....", "..HHHHH..HH..HHHHH..", ".HHHAHHH....HHHAHHH.",
      "HHHH..HHHCCHHH..HHHH", "HHHH..HHHCCHHH..HHHH", ".HHHAHHH....HHHAHHH.", "..HHHHH..HH..HHHHH..", "....HHH.HHHH.HHH....",
      ".......HHHHHH......."]},
  ];
  const POWERS = {multi: {glyph: "M", colour: "#ff5fd2", label: "MULTIBALL"}, wide: {glyph: "W", colour: "#54e39a", label: "WIDER SHIP"},
    slow: {glyph: "S", colour: "#3fd7ff", label: "SLOW SHOT"}, life: {glyph: "+", colour: "#f5c76d", label: "REBUY +1"}};

  const cab = Kit.cabinet({width: W, height: H, colours, start: startGame, update, draw, report, end: debugOver, card});
  const {ctx} = cab;
  const {text, glow} = cab.draw;
  const pointer = cab.input.pointer;

  const run = {score: 0, level: 0, lives: 3, broken: 0, banner: null, clearing: 0, quake: 0};
  let paddle = null, balls = [], bricks = [], drops = [], sparks = [], ship = SHIPS[0];

  const sfx = {
    bounce() { cab.sound.tone("square", 440, 440, .04, .1); },
    shield() { cab.sound.tone("triangle", 1100, 800, .07, .12); },
    hull() { cab.sound.tone("square", 260, 180, .06, .12); },
    clank() { cab.sound.tone("square", 160, 150, .05, .14); },
    pop() { cab.sound.hiss(.2, .35, 2400); },
    power() { [659, 880, 1175].forEach((f, i) => cab.sound.tone("square", f, f, .07, .12, i * .06)); },
    lost() { cab.sound.tone("sawtooth", 400, 80, .6, .2); },
    clear() { [392, 523, 659, 784, 1047].forEach((f, i) => cab.sound.tone("triangle", f, f, .14, .18, i * .08)); },
  };

  function startGame() {
    Object.assign(run, {score: 0, level: 0, lives: 3, broken: 0, banner: null, clearing: 0, quake: 0});
    paddle = {x: W / 2, w: 84, wide: 0};
    pointer.active = false;
    nextLevel();
  }

  function nextLevel() {
    run.level += 1;
    ship = SHIPS[(run.level - 1) % SHIPS.length];
    const rows = ship.rows;
    const at = (r, c) => rows[r]?.[c] && rows[r][c] !== ".";
    bricks = [];
    const top = TOP + (12 - rows.length) * BRICK_H / 2;
    rows.forEach((line, r) => [...line].forEach((char, c) => {
      if (char === ".") return;
      const edge = !at(r - 1, c) || !at(r + 1, c) || !at(r, c - 1) || !at(r, c + 1);
      const kind = char === "A" ? "armour" : char === "C" ? "core" : edge ? "shield" : "hull";
      bricks.push({r, c, x: LEFT + c * CELL, y: top + r * BRICK_H, kind, hp: KINDS[kind].hp, flash: 0});
    }));
    serve();
    drops = [];
    run.banner = {text: ship.name, sub: `LEVEL ${Kit.pad(run.level)} · BREAK THE SHIELDS, THEN THE HULL`, t: 150};
  }

  function speed() {
    return Math.min(4.6 + run.level * .35, 8);
  }

  function serve() {
    balls = [{x: paddle.x, y: H - 70, vx: 0, vy: 0, stuck: true, slow: 0}];
  }

  function launch() {
    for (const ball of balls) {
      if (!ball.stuck) continue;
      ball.stuck = false;
      const a = between(-.5, .5);
      ball.vx = Math.sin(a) * speed();
      ball.vy = -Math.cos(a) * speed();
    }
  }

  function hitBrick(brick, ball) {
    brick.hp -= 1;
    brick.flash = 8;
    if (brick.hp > 0) {
      (brick.kind === "armour" ? sfx.clank : sfx.shield)();
      return;
    }
    brick.dead = true;
    run.broken += 1;
    run.score += KINDS[brick.kind].score;
    (brick.kind === "shield" ? sfx.pop : sfx.hull)();
    for (let i = 0; i < 10; i += 1) {
      const a = between(0, Math.PI * 2), v = between(.5, 3);
      sparks.push({x: brick.x + CELL / 2, y: brick.y + BRICK_H / 2, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: between(15, 35), colour: KINDS[brick.kind].colour});
    }
    if (chance(brick.kind === "core" ? 1 : .09)) {
      const roll = Math.random();
      const type = roll < .35 ? "multi" : roll < .7 ? "wide" : roll < .92 ? "slow" : "life";
      drops.push({x: brick.x + CELL / 2, y: brick.y, type});
    }
    // A little faster every hit, to a point.
    const length = Math.hypot(ball.vx, ball.vy);
    const want = Math.min(length * 1.006, speed() * 1.25);
    ball.vx *= want / length;
    ball.vy *= want / length;
  }

  function brickAt(x, y) {
    return bricks.find((brick) => !brick.dead && x >= brick.x && x < brick.x + CELL && y >= brick.y && y < brick.y + BRICK_H);
  }

  function collect(drop) {
    const spec = POWERS[drop.type];
    sfx.power();
    run.banner = {text: spec.label, t: 70, small: true, colour: spec.colour};
    if (drop.type === "multi") {
      const source = balls.find((ball) => !ball.stuck) || balls[0];
      for (const turn of [-.5, .5]) {
        const a = Math.atan2(source.vx, -source.vy) + turn;
        const s = Math.hypot(source.vx, source.vy) || speed();
        balls.push({x: source.x, y: source.y, vx: Math.sin(a) * s, vy: -Math.abs(Math.cos(a) * s), stuck: false, slow: 0});
      }
    } else if (drop.type === "wide") paddle.wide = 60 * 20;
    else if (drop.type === "slow") for (const ball of balls) ball.slow = 60 * 10;
    else run.lives = Math.min(6, run.lives + 1);
  }

  function finish() {
    cab.over({score: run.score, level: run.level, rank: Kit.rank(run.score, .3)});
  }

  function update() {
    for (const spark of sparks) { spark.x += spark.vx; spark.y += spark.vy; spark.vy += .05; spark.life -= 1; }
    sparks = sparks.filter((spark) => spark.life > 0);
    if (cab.state !== "play") return;
    if (run.banner && --run.banner.t <= 0) run.banner = null;
    if (run.quake > 0) run.quake -= 1;

    // The ship: the keys, or under the mouse.
    paddle.w = paddle.wide > 0 ? 130 : 84;
    if (paddle.wide > 0) paddle.wide -= 1;
    const move = (cab.input.held(...Kit.RIGHT) ? 1 : 0) - (cab.input.held(...Kit.LEFT) ? 1 : 0);
    if (move) { pointer.active = false; paddle.x += move * 8; }
    else if (pointer.active) paddle.x += clamp(pointer.x - paddle.x, -14, 14);
    paddle.x = clamp(paddle.x, paddle.w / 2 + 8, W - paddle.w / 2 - 8);
    if (cab.input.held("Space", ...Kit.UP) || cab.input.clicked()) launch();

    const top = H - 52;
    for (const ball of balls) {
      if (ball.stuck) { ball.x = paddle.x; ball.y = top - 7; continue; }
      if (ball.slow > 0) ball.slow -= 1;
      const pace = ball.slow > 0 ? .65 : 1;
      const steps = 3;
      for (let step = 0; step < steps; step += 1) {
        ball.x += ball.vx * pace / steps;
        if (ball.x < 10 || ball.x > W - 10) { ball.vx *= -1; ball.x = clamp(ball.x, 10, W - 10); sfx.bounce(); }
        let brick = brickAt(ball.x, ball.y);
        if (brick) { ball.vx *= -1; ball.x += ball.vx * pace / steps; hitBrick(brick, ball); }
        ball.y += ball.vy * pace / steps;
        if (ball.y < 70) { ball.vy = Math.abs(ball.vy); sfx.bounce(); }
        brick = brickAt(ball.x, ball.y);
        if (brick) { ball.vy *= -1; ball.y += ball.vy * pace / steps; hitBrick(brick, ball); }
        // Off your ship: the further from the middle, the sharper the angle.
        if (ball.vy > 0 && ball.y > top - 6 && ball.y < top + 8 && Math.abs(ball.x - paddle.x) < paddle.w / 2 + 5) {
          const offset = clamp((ball.x - paddle.x) / (paddle.w / 2), -1, 1);
          const s = Math.hypot(ball.vx, ball.vy);
          ball.vx = Math.sin(offset * 1.05) * s;
          ball.vy = -Math.abs(Math.cos(offset * 1.05) * s);
          ball.y = top - 7;
          sfx.bounce();
        }
      }
      if (ball.y > H + 10) ball.dead = true;
    }
    balls = balls.filter((ball) => !ball.dead);
    bricks = bricks.filter((brick) => !brick.dead);
    for (const brick of bricks) if (brick.flash > 0) brick.flash -= 1;
    for (const drop of drops) {
      drop.y += 2;
      if (drop.y > top - 6 && drop.y < top + 10 && Math.abs(drop.x - paddle.x) < paddle.w / 2 + 8) { drop.taken = true; collect(drop); }
    }
    drops = drops.filter((drop) => !drop.taken && drop.y < H + 10);

    if (!balls.length) {
      run.lives -= 1;
      run.quake = 14;
      sfx.lost();
      if (run.lives <= 0) return finish();
      paddle.wide = 0;
      serve();
      run.banner = {text: "SHOT LOST", sub: `${run.lives} LEFT`, t: 80};
    }
    if (!bricks.length) {
      if (!run.clearing) {
        run.clearing = 120;
        const bonus = 1000 * run.level;
        run.score += bonus;
        sfx.clear();
        run.banner = {text: `${ship.name.split(" ")[0]} DISABLED`, sub: `BONUS ${bonus.toLocaleString()}`, t: 120, good: true};
        balls = [];
      } else if (--run.clearing <= 0) {
        run.clearing = 0;
        nextLevel();
      }
    }
  }

  // ---- Drawing. ----
  function drawBrick(brick) {
    const spec = KINDS[brick.kind];
    const x = brick.x + 1, y = brick.y + 1, w = CELL - 2, h = BRICK_H - 2;
    const colour = brick.flash ? "#ffffff" : spec.colour;
    if (brick.kind === "shield") {
      ctx.fillStyle = brick.hp === 1 ? "rgba(63, 215, 255, .12)" : "rgba(63, 215, 255, .28)";
      ctx.fillRect(x, y, w, h);
      ctx.strokeStyle = colour;
      ctx.globalAlpha = brick.hp === 1 ? .5 : 1;
      ctx.lineWidth = 1;
      ctx.strokeRect(x + .5, y + .5, w - 1, h - 1);
      ctx.globalAlpha = 1;
    } else {
      const grad = ctx.createLinearGradient(0, y, 0, y + h);
      grad.addColorStop(0, colour);
      grad.addColorStop(1, brick.kind === "hull" ? "#3a4450" : brick.kind === "armour" ? "#7a5a20" : "#6a1a5a");
      ctx.fillStyle = grad;
      ctx.fillRect(x, y, w, h);
      if (brick.hp < spec.hp) {
        ctx.strokeStyle = "rgba(0,0,0,.6)";
        ctx.beginPath(); ctx.moveTo(x + 4, y + 2); ctx.lineTo(x + w / 2, y + h - 3); ctx.lineTo(x + w - 5, y + 3); ctx.stroke();
      }
      if (brick.kind === "core") {
        glow("#ff5fd2", 10);
        ctx.fillStyle = "#ffd0f4";
        ctx.fillRect(x + w / 2 - 3, y + h / 2 - 2, 6, 4);
        ctx.shadowBlur = 0;
      }
    }
  }

  function drawPaddle() {
    const y = H - 52, w = paddle.w;
    ctx.save();
    ctx.translate(paddle.x, y);
    ctx.beginPath();
    ctx.moveTo(-w / 2, 8); ctx.lineTo(-w / 2 + 14, -4); ctx.lineTo(-10, -9); ctx.lineTo(10, -9); ctx.lineTo(w / 2 - 14, -4); ctx.lineTo(w / 2, 8);
    ctx.closePath();
    ctx.fillStyle = colours.panel;
    ctx.fill();
    glow(paddle.wide > 0 ? colours.green : colours.accent, 12);
    ctx.strokeStyle = paddle.wide > 0 ? colours.green : colours.accent;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.fillStyle = colours.orange;
    for (const side of [-1, 1]) ctx.fillRect(side * (w / 4) - 4, 8, 8, 3 + Math.random() * 3);
    ctx.restore();
  }

  function draw() {
    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, 0, W, H);
    if (run.quake > 0) ctx.translate(between(-1, 1) * run.quake * .4, between(-1, 1) * run.quake * .4);
    for (let i = 0; i < 70; i += 1) {
      ctx.fillStyle = "rgba(255,255,255,.35)";
      ctx.fillRect((i * 137.5) % W, (i * 91.3 + cab.tick * (.2 + (i % 3) * .1)) % H, 1.2, 1.2);
    }
    bricks.forEach(drawBrick);
    for (const drop of drops) {
      const spec = POWERS[drop.type];
      ctx.beginPath();
      ctx.roundRect(drop.x - 14, drop.y - 8, 28, 16, 6);
      ctx.fillStyle = "#0b1220";
      ctx.fill();
      ctx.strokeStyle = spec.colour;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      text(spec.glyph, drop.x, drop.y + 4, 11, spec.colour);
    }
    if (cab.state !== "title" && paddle) drawPaddle();
    for (const ball of balls) {
      glow(ball.slow > 0 ? "#3fd7ff" : colours.orange, 14);
      ctx.beginPath();
      ctx.arc(ball.x, ball.y, 5.5, 0, Math.PI * 2);
      ctx.fillStyle = ball.slow > 0 ? "#bff2ff" : "#ffe0c2";
      ctx.fill();
      ctx.shadowBlur = 0;
    }
    for (const spark of sparks) {
      ctx.globalAlpha = clamp(spark.life / 25, 0, 1);
      ctx.fillStyle = spark.colour;
      ctx.fillRect(spark.x - 1, spark.y - 1, 2, 2);
    }
    ctx.globalAlpha = 1;
    ctx.setTransform(cab.scale, 0, 0, cab.scale, 0, 0);
    cab.scoreBar(run.score, "LEVEL", run.level);
    if (cab.state !== "title") {
      text(ship.name, W / 2, 64, 10, colours.muted);
      for (let i = 0; i < Math.max(0, run.lives - 1); i += 1) { ctx.fillStyle = colours.accent; ctx.fillRect(18 + i * 18, H - 18, 12, 4); }
      if (balls.some((ball) => ball.stuck) && cab.state === "play") text("SPACE OR CLICK TO LAUNCH", W / 2, H - 92, 12, colours.text);
    }
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 6, 8, colours.dim);
    const banner = run.banner;
    if (banner && cab.state === "play") {
      ctx.globalAlpha = clamp(banner.t / 30, 0, 1);
      if (banner.small) text(banner.text, W / 2, H - 120, 16, banner.colour || colours.text, "center", 700, Kit.DISPLAY);
      else {
        text(banner.text, W / 2, H / 2 + 60, 26, banner.good ? colours.green : colours.text, "center", 700, Kit.DISPLAY);
        if (banner.sub) text(banner.sub, W / 2, H / 2 + 84, 11, colours.accent);
      }
      ctx.globalAlpha = 1;
    }
    if (cab.state === "title") {
      cab.titleScreen({top: "SHIELD", bottom: "BREAKER", tone: "#3fd7ff", y: 160,
        rows: [["SHIELD PANEL · TWO HITS", "20"], ["HULL PLATE", "10"], ["ARMOUR · THREE HITS", "50"], ["CORE", "200"],
          ["SHIP DISABLED", "1,000 × LEVEL"]],
        note: "FARRAGUT · MAJESTIC · THARGOID TITAN",
        how: "MOUSE OR ← → TO MOVE · SPACE OR CLICK TO LAUNCH"});
    } else if (cab.state === "over") {
      cab.overScreen({heading: "OUT OF SHOTS", tone: colours.red, sub: "STRIKE DEBRIEF", rank: Kit.rank(run.score, .3),
        lines: [["SCORE", run.score.toLocaleString()], ["LEVEL", run.level], ["PLATES BROKEN", run.broken]]});
    }
  }

  function report() {
    return {score: run.score, level: run.level, lives: run.lives, bricks: bricks.length, balls: balls.length, ship: ship.name};
  }

  function debugOver() {
    run.score += 1234;
    run.lives = 1;
    balls = [];
  }

  function card() {
    startGame();
    run.level = 2;
    nextLevel();
    run.banner = null;
    launch();
    for (let i = 0; i < 400; i += 1) {
      cab.tick += 1;
      const lead = balls[0];
      if (lead) paddle.x = clamp(lead.x, 60, W - 60);
      update();
      if (!balls.length) serve(), launch();
    }
    drops.push({x: 220, y: 380, type: "multi"});
    run.score = Math.max(run.score, 2310);
    run.banner = null;
  }

  window.shieldBreaker = {state: () => ({...report(), state: cab.state}),
    // For tests: everything but one plate gone.
    _nearlyDone() { bricks = bricks.slice(0, 1); }};
})();
