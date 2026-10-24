// No Fire Zone (5.6.3): cross a busy station approach to its five pads.
// Lanes of traffic at different speeds, then lanes of drifting cargo
// canisters to hop across (the open thruster wake between them burns).
// Station rules: bump someone and you're fined, hop too fast and you're
// fined for speeding, and fire your guns and the station opens up on you.
(() => {
  "use strict";

  const W = 600, H = 675, TILE = 40, ROW = 42, TOP = 64, COLUMNS = W / TILE;
  const PADS = 5, WAKE = [1, 2, 3, 4, 5], MEDIAN = 6, LANES = [7, 8, 9, 10, 11], START = 12;
  const {clamp, between, chance, pick} = Kit;
  const colours = {bg: "#03070b", panel: "#0b141c", accent: "#00d1ff", orange: "#ff8a3d", text: "#e3eef4",
    muted: "#94a8b5", dim: "#5d717e", green: "#54e39a", yellow: "#f5c76d", red: "#ff5b61"};
  const HULLS = [{name: "SIDEWINDER", tiles: 1, hue: "#f5c76d"}, {name: "COBRA", tiles: 2, hue: "#00d1ff"},
    {name: "TYPE-9", tiles: 3, hue: "#ff8a3d"}, {name: "ANACONDA", tiles: 4, hue: "#c38bff"}];

  const cab = Kit.cabinet({width: W, height: H, colours, crt: true, start: startGame, update, draw, report, end: debugOver, card, key});
  const {ctx} = cab;
  const {text, glow} = cab.draw;
  const pointer = cab.input.pointer;

  const run = {score: 0, level: 0, lives: 3, fines: 0, finesTotal: 0, pads: [], best: START, timer: 0, banner: null, flash: 0, docked: 0};
  let me = null, lanes = [], hops = [], sparks = [], warning = 0, stationFire = 0;

  const sfx = {
    hop() { cab.sound.tone("square", 520, 700, .05, .08); },
    bump() { cab.sound.tone("sawtooth", 200, 120, .3, .2); cab.sound.hiss(.25, .4, 1200); },
    fine() { [440, 330].forEach((f, i) => cab.sound.tone("square", f, f, .15, .12, i * .16)); },
    burn() { cab.sound.hiss(.8, .7, 2200); cab.sound.tone("sawtooth", 500, 60, .7, .2); },
    pad() { [523, 659, 784, 1047].forEach((f, i) => cab.sound.tone("triangle", f, f, .12, .16, i * .08)); },
    alarm() { for (let i = 0; i < 4; i += 1) cab.sound.tone("sawtooth", 880, 660, .18, .14, i * .2); },
  };

  function key(code) {
    if (cab.state !== "play" || !me || me.dead) return false;
    const move = {ArrowUp: [0, -1], KeyW: [0, -1], ArrowDown: [0, 1], KeyS: [0, 1], ArrowLeft: [-1, 0], KeyA: [-1, 0], ArrowRight: [1, 0], KeyD: [1, 0]}[code];
    if (move) { if (cab.input.mode !== "mouse") hop(...move); return true; }
    if (code === "KeyF" || code === "Space") { openFire(); return true; }
    return false;
  }

  function rowY(row) {
    return TOP + row * ROW;
  }

  function startGame() {
    Object.assign(run, {score: 0, level: 0, lives: 3, fines: 0, finesTotal: 0, best: START, banner: null, flash: 0, docked: 0});
    pointer.active = false;
    nextLevel();
  }

  function nextLevel() {
    run.level += 1;
    run.pads = Array(PADS).fill(false);
    const pace = 1 + (run.level - 1) * .18;
    lanes = [];
    for (const row of LANES) {
      const dir = row % 2 ? 1 : -1, speed = between(.5, 1.4) * pace * dir;
      const hull = HULLS[(row + run.level) % HULLS.length];
      const gap = hull.tiles * TILE + between(90, 190) / pace;
      const items = [];
      for (let x = between(0, 80); x < W + 200; x += gap + between(0, 60)) items.push({x, w: hull.tiles * TILE - 6, hull});
      lanes.push({row, kind: "traffic", speed, items, span: Math.max(W + 200, items.length * gap)});
    }
    for (const row of WAKE) {
      const dir = row % 2 ? -1 : 1, speed = between(.45, 1.1) * pace * dir;
      const items = [];
      let x = between(0, 60);
      while (x < W + 220) {
        const length = Math.floor(between(2, 5 - Math.min(run.level - 1, 2)));
        items.push({x, w: length * TILE - 4, count: length, sink: chance(.25 + run.level * .05) ? between(0, 600) : null});
        x += length * TILE + between(70, 150) * (1 + (run.level - 1) * .12);
      }
      lanes.push({row, kind: "cans", speed, items, span: Math.max(W + 220, x)});
    }
    respawn();
    run.banner = {text: `APPROACH ${Kit.pad(run.level)}`, sub: "FILL ALL FIVE PADS · NO SPEEDING · NO WEAPONS", t: 140};
  }

  function respawn() {
    me = {col: Math.floor(COLUMNS / 2), row: START, x: Math.floor(COLUMNS / 2) * TILE + TILE / 2, hop: 0, dead: false};
    run.timer = 30;
    run.best = START;
    hops = [];
  }

  function hop(dx, dy) {
    if (me.hop > 0) return;
    const row = me.row + dy;
    if (row > START || row < 0) return;
    if (row === 0) {
      const pad = padAt(me.x + dx * TILE);
      if (pad < 0) { warning = 30; return; }
    }
    me.row = row;
    me.x = clamp(me.x + dx * TILE, TILE / 2, W - TILE / 2);
    me.hop = 8;
    sfx.hop();
    if (me.row < run.best) { run.best = me.row; run.score += 10; }
    // Speeding: too many hops too quickly.
    hops.push(cab.tick);
    hops = hops.filter((at) => cab.tick - at < 60);
    if (hops.length > 5) { hops = []; fine("SPEEDING IN THE NO FIRE ZONE", 100, false); }
  }

  function padAt(x) {
    const width = W / PADS;
    const index = Math.floor(x / width);
    const centre = index * width + width / 2;
    return Math.abs(x - centre) < TILE * .8 ? index : -1;
  }

  function fine(reason, amount, sendBack) {
    run.fines += 1;
    run.finesTotal += 1;
    run.score = Math.max(0, run.score - amount);
    run.flash = 12;
    sfx.fine();
    if (run.fines >= 3) {
      run.fines = 0;
      return lose("PERMIT REVOKED · THREE FINES");
    }
    run.banner = {text: `FINED ${amount} CR`, sub: `${reason} · ${run.fines}/3`, t: 110, bad: true};
    if (sendBack) respawn();
  }

  function openFire() {
    stationFire = 90;
    sfx.alarm();
    run.banner = {text: "WEAPONS IN THE NO FIRE ZONE", sub: "THE STATION OPENS FIRE", t: 120, bad: true};
  }

  function lose(reason) {
    if (me.dead) return;
    me.dead = true;
    me.respawnIn = 90;
    run.lives -= 1;
    run.flash = 24;
    for (let i = 0; i < 40; i += 1) {
      const a = between(0, Math.PI * 2), v = between(.5, 4);
      sparks.push({x: me.x, y: rowY(me.row) + ROW / 2, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: between(20, 50), colour: pick([colours.orange, colours.yellow, "#ffffff"])});
    }
    sfx.burn();
    run.banner = {text: reason, sub: run.lives > 0 ? `${run.lives} SHIP${run.lives === 1 ? "" : "S"} LEFT` : "", t: 120, bad: true};
  }

  function finish() {
    cab.over({score: run.score, level: run.level, rank: Kit.rank(run.score, .2, "trade")});
  }

  function update() {
    for (const spark of sparks) { spark.x += spark.vx; spark.y += spark.vy; spark.vx *= .95; spark.vy *= .95; spark.life -= 1; }
    sparks = sparks.filter((spark) => spark.life > 0);
    for (const lane of lanes) {
      for (const item of lane.items) {
        item.x += lane.speed;
        if (lane.speed > 0 && item.x > W + 40) item.x -= lane.span;
        if (lane.speed < 0 && item.x + item.w < -40) item.x += lane.span;
        if (item.sink !== null && item.sink !== undefined) item.sink = (item.sink + 1) % 600;
      }
    }
    if (cab.state !== "play") return;
    if (run.banner && --run.banner.t <= 0) run.banner = null;
    if (run.flash > 0) run.flash -= 1;
    if (warning > 0) warning -= 1;
    if (me.dead) {
      if (--me.respawnIn <= 0) {
        if (run.lives <= 0) return finish();
        respawn();
      }
      return;
    }
    if (me.hop > 0) me.hop -= 1;
    if (stationFire > 0 && --stationFire === 0) lose("SHOT BY THE STATION");

    // A click hops towards it.
    if (cab.input.clicked()) {
      const dx = pointer.x - me.x, dy = pointer.y - (rowY(me.row) + ROW / 2);
      if (Math.abs(dx) > Math.abs(dy)) hop(Math.sign(dx), 0);
      else hop(0, Math.sign(dy));
    }

    run.timer -= 1 / 60;
    if (run.timer <= 0) return lose("DOCKING REQUEST TIMED OUT");

    const lane = lanes.find((item) => item.row === me.row);
    if (lane?.kind === "traffic" && me.hop === 0) {
      const hit = lane.items.find((item) => me.x + 12 > item.x && me.x - 12 < item.x + item.w);
      if (hit) {
        sfx.bump();
        fine(`BUMPED A ${hit.hull.name}`, 200, true);
      }
    } else if (lane?.kind === "cans" && me.hop === 0) {
      const can = lane.items.find((item) => me.x > item.x - 4 && me.x < item.x + item.w + 4 && !sunk(item));
      if (!can) return lose("INTO THE THRUSTER WAKE");
      me.x += lane.speed;
      if (me.x < 4 || me.x > W - 4) return lose("DRIFTED OUT OF THE LANE");
    }
    if (me.row === 0 && me.hop === 0) {
      const pad = padAt(me.x);
      if (pad >= 0 && !run.pads[pad]) {
        run.pads[pad] = true;
        run.docked += 1;
        const points = 50 + Math.round(run.timer) * 10;
        run.score += points;
        sfx.pad();
        run.banner = {text: `PAD ${pad + 1} CLEARED`, sub: `+${points}`, t: 90, good: true};
        if (run.pads.every(Boolean)) {
          run.score += 1000 * run.level;
          nextLevel();
          run.banner = {text: "ALL PADS FILLED", sub: `+${(1000 * (run.level - 1)).toLocaleString()} · THE APPROACH GETS BUSIER`, t: 150, good: true};
        } else respawn();
      } else if (pad >= 0) {
        lose("PAD ALREADY TAKEN");
      }
    }
  }

  function sunk(item) {
    return item.sink !== null && item.sink !== undefined && item.sink > 460;
  }

  // ---- Drawing. ----
  function drawLanes() {
    // The station's face along the top, with its pads.
    ctx.fillStyle = "#0e1822";
    ctx.fillRect(0, rowY(0), W, ROW);
    const width = W / PADS;
    for (let i = 0; i < PADS; i += 1) {
      const cx = i * width + width / 2;
      ctx.fillStyle = run.pads[i] ? "#123a24" : "#020507";
      ctx.fillRect(cx - TILE * .8, rowY(0) + 4, TILE * 1.6, ROW - 6);
      ctx.strokeStyle = run.pads[i] ? colours.green : colours.accent;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(cx - TILE * .8, rowY(0) + 4, TILE * 1.6, ROW - 6);
      text(run.pads[i] ? "✓" : String(i + 1), cx, rowY(0) + ROW / 2 + 5, 13, run.pads[i] ? colours.green : colours.dim);
    }
    // The thruster wake: hot and flickering.
    for (const row of WAKE) {
      const y = rowY(row);
      const wake = ctx.createLinearGradient(0, y, 0, y + ROW);
      wake.addColorStop(0, "#1a0a20");
      wake.addColorStop(.5, `rgba(${120 + Math.sin(cab.tick * .1 + row) * 30}, 40, 90, 1)`);
      wake.addColorStop(1, "#1a0a20");
      ctx.fillStyle = wake;
      ctx.fillRect(0, y, W, ROW);
    }
    ctx.fillStyle = "#0c1a12";
    ctx.fillRect(0, rowY(MEDIAN), W, ROW);
    for (let x = 10; x < W; x += 40) { ctx.fillStyle = Math.floor(cab.tick / 30 + x / 40) % 2 ? colours.yellow : "#3a3010"; ctx.fillRect(x, rowY(MEDIAN) + ROW / 2 - 2, 6, 4); }
    for (const row of LANES) {
      const y = rowY(row);
      ctx.fillStyle = row % 2 ? "#06101a" : "#081420";
      ctx.fillRect(0, y, W, ROW);
      ctx.fillStyle = "rgba(0, 209, 255, .12)";
      for (let x = (cab.tick * (row % 2 ? 1 : -1)) % 40; x < W; x += 40) ctx.fillRect(x, y + ROW - 2, 18, 1);
    }
    ctx.fillStyle = "#0c1a12";
    ctx.fillRect(0, rowY(START), W, ROW);
    text("NO FIRE ZONE · SPEED LIMIT ENFORCED", W / 2, rowY(MEDIAN) + ROW / 2 + 4, 10, colours.dim);
  }

  function drawItems() {
    for (const lane of lanes) {
      const y = rowY(lane.row);
      for (const item of lane.items) {
        if (item.x > W + 10 || item.x + item.w < -10) continue;
        if (lane.kind === "traffic") {
          const hue = item.hull.hue, facing = Math.sign(lane.speed);
          ctx.save();
          ctx.translate(item.x + item.w / 2, y + ROW / 2);
          ctx.scale(facing, 1);
          const half = item.w / 2, tall = 10 + item.hull.tiles * 2;
          ctx.beginPath();
          ctx.moveTo(half, 0); ctx.lineTo(half - 14, -tall); ctx.lineTo(-half, -tall * .7); ctx.lineTo(-half, tall * .7); ctx.lineTo(half - 14, tall);
          ctx.closePath();
          ctx.fillStyle = "#0d1620";
          ctx.fill();
          glow(hue, 8);
          ctx.strokeStyle = hue;
          ctx.lineWidth = 1.5;
          ctx.stroke();
          ctx.shadowBlur = 0;
          ctx.fillStyle = colours.orange;
          ctx.fillRect(-half - 6, -3, 6, 6);
          ctx.restore();
        } else {
          const gone = sunk(item);
          const fading = item.sink !== null && item.sink > 400 && !gone;
          if (gone) continue;
          ctx.globalAlpha = fading && Math.floor(cab.tick / 5) % 2 ? .35 : 1;
          for (let i = 0; i < item.count; i += 1) {
            const cx = item.x + i * TILE + TILE / 2 - 2;
            ctx.fillStyle = "#26303a";
            ctx.fillRect(cx - 15, y + 8, 30, ROW - 16);
            ctx.strokeStyle = colours.yellow;
            ctx.lineWidth = 1.2;
            ctx.strokeRect(cx - 15, y + 8, 30, ROW - 16);
            ctx.beginPath(); ctx.moveTo(cx - 15, y + ROW / 2); ctx.lineTo(cx + 15, y + ROW / 2); ctx.stroke();
          }
          ctx.globalAlpha = 1;
        }
      }
    }
  }

  function drawMe() {
    if (!me || me.dead) return;
    const lift = me.hop > 0 ? Math.sin(me.hop / 8 * Math.PI) * 6 : 0;
    const y = rowY(me.row) + ROW / 2 - lift;
    ctx.save();
    ctx.translate(me.x, y);
    ctx.beginPath();
    ctx.moveTo(0, -13); ctx.lineTo(11, 9); ctx.lineTo(0, 4); ctx.lineTo(-11, 9);
    ctx.closePath();
    ctx.fillStyle = "#102018";
    ctx.fill();
    glow(colours.green, 10);
    ctx.strokeStyle = colours.green;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.restore();
    ctx.shadowBlur = 0;
    if (stationFire > 0) {
      for (const sx of [40, W - 40]) {
        if (Math.floor(cab.tick / 3) % 2) cab.draw.line(sx, rowY(0), me.x, y, colours.red, 2, 8);
      }
    }
  }

  function drawHud() {
    cab.scoreBar(run.score, "APPROACH", run.level);
    if (cab.state === "title") return;
    const y = rowY(START) + ROW + 18;
    text("PERMISSION", 18, y, 10, colours.dim, "left");
    cab.draw.bar(18, y + 6, 160, 7, run.timer / 30, run.timer < 8 ? colours.red : colours.accent);
    text(`FINES ${run.fines}/3`, W / 2, y + 10, 12, run.fines ? colours.orange : colours.muted);
    text("SHIPS", W - 18, y, 10, colours.dim, "right");
    for (let i = 0; i < run.lives; i += 1) { ctx.fillStyle = colours.green; ctx.fillRect(W - 28 - i * 16, y + 6, 10, 8); }
    if (warning > 0) text("NO PAD THERE", me.x, rowY(1) - 4, 11, colours.orange);
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 6, 8, colours.dim);
  }

  function draw() {
    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, 0, W, H);
    drawLanes();
    drawItems();
    if (cab.state !== "title") drawMe();
    for (const spark of sparks) {
      ctx.globalAlpha = clamp(spark.life / 30, 0, 1);
      ctx.fillStyle = spark.colour;
      ctx.fillRect(spark.x - 1, spark.y - 1, 2, 2);
    }
    ctx.globalAlpha = 1;
    if (run.flash > 0) { ctx.fillStyle = `rgba(255, 91, 97, ${run.flash / 60})`; ctx.fillRect(0, 0, W, H); }
    drawHud();
    const banner = run.banner;
    if (banner && cab.state === "play") {
      ctx.globalAlpha = clamp(banner.t / 30, 0, 1);
      ctx.fillStyle = "rgba(0,0,0,.6)";
      ctx.fillRect(0, rowY(MEDIAN) - 4, W, ROW + 8);
      text(banner.text, W / 2, rowY(MEDIAN) + 18, 20, banner.bad ? colours.red : banner.good ? colours.green : colours.text, "center", 700, Kit.DISPLAY);
      if (banner.sub) text(banner.sub, W / 2, rowY(MEDIAN) + 36, 10, colours.accent);
      ctx.globalAlpha = 1;
    }
    if (cab.state === "title") {
      cab.titleScreen({top: "NO FIRE", bottom: "ZONE", tone: colours.green, y: 160,
        rows: [["EACH ROW FORWARD", "10"], ["A PAD", "50 + TIME LEFT"], ["ALL FIVE PADS", "1,000 × APPROACH"], ["BUMPING A SHIP", "FINED 200"],
          ["FIRING YOUR GUNS", "DON'T"]],
        note: "RIDE THE CANISTERS ACROSS · THE WAKE BETWEEN THEM BURNS",
        how: "ARROWS / WASD OR CLICK TO HOP · THREE FINES LOSES THE PERMIT"});
    } else if (cab.state === "over") {
      cab.overScreen({heading: "PERMIT REVOKED", tone: colours.red, sub: "STATION CONTROL", rankLabel: "TRADE RANK", rank: Kit.rank(run.score, .2, "trade"),
        lines: [["SCORE", run.score.toLocaleString()], ["APPROACHES", run.level], ["PADS FILLED", run.docked], ["FINES", run.finesTotal]]});
    }
  }

  function report() {
    return {score: run.score, level: run.level, lives: run.lives, fines: run.fines, row: me?.row ?? START, pads: run.pads.filter(Boolean).length};
  }

  function debugOver() {
    run.score += 1234;
    run.lives = 1;
    lose("TEST");
    me.respawnIn = 1;
  }

  function card() {
    startGame();
    for (let i = 0; i < 90; i += 1) { cab.tick += 1; update(); }
    run.pads = [true, false, true, false, false];
    run.score = 1460;
    me.row = MEDIAN;
    me.x = 300;
    run.timer = 21;
    run.banner = null;
  }

  window.noFireZone = {state: () => ({...report(), state: cab.state})};
})();
