// Touchdown (5.6.3): set the ship down on a pad, side-on, before the fuel
// runs out. The deck sends the world you're really at (its gravity, from the
// journal's scans) and the game lands there; away from any body, a world is
// made up. Over 2 g the warning goes red, as it does in the cockpit.
(() => {
  "use strict";

  const W = 600, H = 675;
  const G = .012;                  // px per step² for one g
  const METRES = .5;               // metres per px, for the read-outs
  const {clamp, between, pick} = Kit;
  const colours = {bg: "#03060a", panel: "#0b1118", accent: "#00d1ff", orange: "#ff8a3d", text: "#e6f0f6",
    muted: "#93a6b4", dim: "#5f7180", green: "#54e39a", yellow: "#f5c76d", red: "#ff5b61"};
  const GROUND = "#9fb4c3";

  const cab = Kit.cabinet({width: W, height: H, colours, start: startGame, update, draw, report, end: debugOver, card, onLive});
  const {ctx} = cab;
  const {text, glow} = cab.draw;
  const pointer = cab.input.pointer;

  const run = {score: 0, level: 0, ships: 3, fuel: 0, landings: 0, soft: 0, banner: null, flash: 0};
  let ship = null, terrain = [], pads = [], world = null, sparks = [], settle = 0;
  let live = null;
  const stars = Array.from({length: 80}, () => ({x: Math.random() * W, y: Math.random() * H * .7, a: Math.random()}));

  const sfx = {
    burn() { cab.sound.hiss(.12, .18, 900); },
    land() { [392, 523, 659, 784].forEach((f, i) => cab.sound.tone("triangle", f, f, .14, .2, i * .09)); },
    crash() { cab.sound.hiss(1, .9, 1400); cab.sound.tone("sawtooth", 140, 30, .9, .3); },
    warn() { cab.sound.tone("square", 880, 880, .08, .1); },
  };

  function onLive(data) {
    live = data && Number(data.gravity) > 0 ? {body: String(data.body || "THIS WORLD"), gravity: Number(data.gravity)} : null;
  }

  function madeUpWorld() {
    const letters = "ABCDEFGH";
    const name = `${pick(["HIP", "COL 285 SECTOR", "SYNUEFE", "PRAEA EUQ", "OUTOTZ", "WREGOE"])} ${Math.floor(between(10, 9999))} ${Math.floor(between(1, 9))} ${letters[Math.floor(between(0, 6))]}`;
    const gravity = Math.round(pick([between(.05, .3), between(.2, .9), between(.6, 1.6), between(1.4, 2.8)]) * 100) / 100;
    return {body: name, gravity, real: false};
  }

  function startGame() {
    Object.assign(run, {score: 0, level: 0, ships: 3, fuel: 1000, landings: 0, soft: 0, banner: null, flash: 0, demo: 0});
    pointer.active = false;
    nextWorld();
  }

  function nextWorld() {
    run.level += 1;
    world = live ? {...live, real: true} : madeUpWorld();
    makeTerrain();
    launch();
    const heavy = world.gravity > 2;
    run.banner = {text: world.real ? "YOUR WORLD" : `WORLD ${Kit.pad(run.level)}`, sub: `${world.body.toUpperCase()} · ${world.gravity.toFixed(2)} G`, t: 170, heavy};
  }

  function launch() {
    ship = {x: between(80, W - 80), y: 70, vx: between(-1.2, 1.2), vy: 0, angle: 0, burning: false, legs: 0};
    sparks = [];
    settle = 0;
  }

  // Rough ground with flat pads: the narrower the pad, the more it's worth.
  function makeTerrain() {
    const rough = 30 + Math.min(run.level, 8) * 9;
    const points = [];
    const step = 15;
    let y = between(H - 220, H - 120);
    for (let x = 0; x <= W; x += step) {
      y = clamp(y + between(-rough, rough) * .5, H - 330, H - 60);
      points.push([x, y]);
    }
    pads = [];
    const sizes = [[6, 2], [4, 3], [3, 5]];
    const taken = new Set();
    for (const [width, multiplier] of sizes.slice(0, Math.min(3, 1 + Math.ceil(run.level / 2)) + (run.level === 1 ? 1 : 0))) {
      let start = 0;
      for (let tries = 0; tries < 40; tries += 1) {
        start = Math.floor(between(2, points.length - width - 2));
        if (![...Array(width + 2).keys()].some((k) => taken.has(start + k - 1))) break;
      }
      for (let k = 0; k <= width; k += 1) taken.add(start + k);
      const level = points[start][1];
      for (let k = 0; k <= width; k += 1) points[start + k][1] = level;
      pads.push({x1: points[start][0], x2: points[start + width][0], y: level, multiplier});
    }
    terrain = points;
  }

  function groundAt(x) {
    const index = clamp(Math.floor(x / 15), 0, terrain.length - 2);
    const [x1, y1] = terrain[index], [x2, y2] = terrain[index + 1];
    return y1 + (y2 - y1) * clamp((x - x1) / (x2 - x1), 0, 1);
  }

  function thrustPower() {
    return Math.max(.035, world.gravity * G * 2.3);
  }

  function update() {
    if (cab.state !== "play") return;
    if (run.banner && --run.banner.t <= 0) run.banner = null;
    if (run.flash > 0) run.flash -= 1;
    for (const spark of sparks) { spark.x += spark.vx; spark.y += spark.vy; spark.vy += .05; spark.life -= 1; }
    sparks = sparks.filter((spark) => spark.life > 0);
    if (settle > 0) {
      if (--settle === 0) {
        if (ship.result === "landed") nextWorld();
        else if (run.ships <= 0 || run.fuel <= 0) finish();
        else launch();
      }
      return;
    }

    // Steering: keys, or point the ship at the mouse and hold the button to burn.
    let turn = (cab.input.held(...Kit.RIGHT) ? 1 : 0) - (cab.input.held(...Kit.LEFT) ? 1 : 0);
    if (turn) pointer.active = false;
    else if (pointer.active) {
      const want = clamp((pointer.x - ship.x) / 160, -1, 1) * 1.2;
      turn = clamp((want - ship.angle) * 8, -1, 1);
    }
    ship.angle = clamp(ship.angle + turn * .045, -Math.PI / 2, Math.PI / 2);
    ship.burning = run.fuel > 0 && (cab.input.held("Space", ...Kit.UP) || pointer.down || run.demo > 0);
    if (run.demo > 0) run.demo -= 1;
    ship.vy += world.gravity * G;
    if (ship.burning) {
      const power = thrustPower();
      ship.vx += Math.sin(ship.angle) * power;
      ship.vy -= Math.cos(ship.angle) * power;
      run.fuel = Math.max(0, run.fuel - (.9 + power * 18));
      if (cab.tick % 6 === 0) sfx.burn();
      if (run.fuel < 150 && cab.tick % 40 === 0) sfx.warn();
    }
    ship.x += ship.vx;
    ship.y += ship.vy;
    if (ship.x < 10 || ship.x > W - 10) { ship.x = clamp(ship.x, 10, W - 10); ship.vx *= -.3; }
    if (ship.y < 20) { ship.y = 20; ship.vy = Math.max(0, ship.vy); }
    const altitude = groundAt(ship.x) - (ship.y + 22);
    ship.legs = clamp(ship.legs + (altitude < 90 ? .05 : -.05), 0, 1);
    if (altitude <= 0) touch();
  }

  function touch() {
    const pad = pads.find((item) => ship.x - 10 >= item.x1 && ship.x + 10 <= item.x2);
    const down = ship.vy, across = Math.abs(ship.vx), tilt = Math.abs(ship.angle);
    ship.y = groundAt(ship.x) - 22;
    if (pad && ship.legs > .6 && down < 1.25 && across < .8 && tilt < .2) {
      const soft = down < .7 && across < .4;
      const points = Math.round(50 * pad.multiplier * (soft ? 2 : 1) * (1 + (run.level - 1) * .25) * Math.max(1, world.gravity));
      run.score += points;
      run.fuel = Math.min(1000, run.fuel + 260);
      run.landings += 1;
      if (soft) run.soft += 1;
      ship.result = "landed";
      ship.vx = ship.vy = 0;
      ship.angle = 0;
      run.banner = {text: soft ? "PERFECT TOUCHDOWN" : "HARD LANDING", sub: `×${pad.multiplier} PAD · +${points} · FUEL +260`, t: 150, good: true};
      sfx.land();
      settle = 150;
      return;
    }
    run.ships -= 1;
    ship.result = "crashed";
    run.flash = 20;
    for (let i = 0; i < 46; i += 1) {
      const a = between(Math.PI, Math.PI * 2);
      const speed = between(1, 5);
      sparks.push({x: ship.x, y: ship.y, vx: Math.cos(a) * speed, vy: Math.sin(a) * speed, life: between(30, 70), colour: pick([colours.orange, colours.yellow, "#ffffff"])});
    }
    const why = !pad ? "NOT ON A PAD" : down >= 1.25 ? "TOO FAST" : across >= .8 ? "SLIDING" : tilt >= .2 ? "NOT LEVEL" : "GEAR UP";
    run.banner = {text: "HULL BREACH", sub: `${why}${run.ships > 0 && run.fuel > 0 ? " · REBUY" : ""}`, t: 150};
    sfx.crash();
    settle = 150;
  }

  function finish() {
    cab.over({score: run.score, level: run.level, rank: Kit.rank(run.score, .1, "explore")});
  }

  // ---- Drawing. ----
  function drawShip() {
    if (!ship || ship.result === "crashed") return;
    ctx.save();
    ctx.translate(ship.x, ship.y);
    ctx.rotate(ship.angle);
    ctx.scale(1.3, 1.3);
    if (ship.burning && ship.result !== "landed") {
      const flame = 12 + Math.random() * 12;
      ctx.beginPath();
      ctx.moveTo(-6, 10);
      ctx.lineTo(0, 10 + flame);
      ctx.lineTo(6, 10);
      ctx.fillStyle = colours.orange;
      glow(colours.orange, 16);
      ctx.fill();
      ctx.shadowBlur = 0;
    }
    // The legs come down near the ground.
    ctx.strokeStyle = colours.text;
    ctx.lineWidth = 1.6;
    const leg = 4 + ship.legs * 8;
    for (const side of [-1, 1]) {
      ctx.beginPath();
      ctx.moveTo(side * 9, 6);
      ctx.lineTo(side * (12 + ship.legs * 4), 6 + leg);
      ctx.lineTo(side * (16 + ship.legs * 4), 6 + leg);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.moveTo(0, -14);
    ctx.lineTo(13, 4);
    ctx.lineTo(10, 10);
    ctx.lineTo(-10, 10);
    ctx.lineTo(-13, 4);
    ctx.closePath();
    ctx.fillStyle = colours.panel;
    ctx.fill();
    glow(colours.accent, 10);
    ctx.strokeStyle = colours.accent;
    ctx.lineWidth = 1.8;
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.beginPath();
    ctx.moveTo(0, -8);
    ctx.lineTo(5, 0);
    ctx.lineTo(-5, 0);
    ctx.closePath();
    ctx.fillStyle = "rgba(0, 209, 255, .5)";
    ctx.fill();
    ctx.restore();
  }

  function drawWorld() {
    for (const star of stars) {
      ctx.globalAlpha = .25 + star.a * .5;
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(star.x, star.y, 1.5, 1.5);
    }
    ctx.globalAlpha = 1;
    // The world's parent in the sky.
    const parent = ctx.createRadialGradient(W * .78, 150, 10, W * .82, 170, 150);
    parent.addColorStop(0, "#3a4a66");
    parent.addColorStop(1, "#0a0f18");
    ctx.beginPath();
    ctx.arc(W * .82, 170, 120, 0, Math.PI * 2);
    ctx.fillStyle = parent;
    ctx.globalAlpha = .7;
    ctx.fill();
    ctx.strokeStyle = "rgba(170, 190, 220, .35)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.ellipse(W * .82, 170, 200, 34, -.25, 0, Math.PI * 2);
    ctx.stroke();
    ctx.globalAlpha = 1;
    if (!terrain.length) return;
    ctx.beginPath();
    ctx.moveTo(0, H);
    terrain.forEach(([x, y]) => ctx.lineTo(x, y));
    ctx.lineTo(W, H);
    ctx.closePath();
    const fill = ctx.createLinearGradient(0, H - 330, 0, H);
    fill.addColorStop(0, "#1a222b");
    fill.addColorStop(1, "#06090c");
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.beginPath();
    terrain.forEach(([x, y], index) => (index ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.strokeStyle = GROUND;
    ctx.lineWidth = 1.4;
    ctx.stroke();
    for (const pad of pads) {
      const lit = Math.floor(cab.tick / 20) % 2;
      glow(colours.green, 12);
      ctx.fillStyle = colours.green;
      ctx.fillRect(pad.x1, pad.y - 2, pad.x2 - pad.x1, 3);
      ctx.shadowBlur = 0;
      for (const x of [pad.x1, pad.x2]) {
        ctx.fillStyle = lit ? colours.yellow : "#5a4a20";
        ctx.fillRect(x - 1.5, pad.y - 8, 3, 6);
      }
      text(`×${pad.multiplier}`, (pad.x1 + pad.x2) / 2, pad.y + 18, 12, colours.green);
    }
  }

  function drawHud() {
    cab.scoreBar(run.score, "WORLD", run.level);
    if (cab.state === "title" || !ship || !world) return;
    const altitude = Math.max(0, groundAt(ship.x) - (ship.y + 22)) * METRES;
    const rows = [["ALTITUDE", `${Math.round(altitude)} M`], ["HORIZONTAL", `${(ship.vx * 60 * METRES).toFixed(1)} M/S ${ship.vx > .05 ? "→" : ship.vx < -.05 ? "←" : ""}`],
      ["VERTICAL", `${(ship.vy * 60 * METRES).toFixed(1)} M/S ${ship.vy > .05 ? "↓" : ship.vy < -.05 ? "↑" : ""}`]];
    rows.forEach(([label, value], index) => {
      text(label, 18, 74 + index * 18, 10, colours.dim, "left");
      const danger = (index === 2 && ship.vy > 1.25) || (index === 1 && Math.abs(ship.vx) > .8);
      text(value, 190, 74 + index * 18, 11, danger ? colours.orange : colours.text, "right");
    });
    text("FUEL", W - 18, 74, 10, colours.dim, "right");
    cab.draw.bar(W - 138, 80, 120, 6, run.fuel / 1000, run.fuel < 150 ? colours.red : colours.yellow);
    text("SHIPS", W - 18, 104, 10, colours.dim, "right");
    for (let i = 0; i < run.ships; i += 1) {
      ctx.fillStyle = colours.accent;
      ctx.fillRect(W - 26 - i * 14, 110, 8, 8);
    }
    const heavy = world.gravity > 2;
    text(world.body.toUpperCase(), W / 2, 74, 10, colours.muted);
    text(`${world.gravity.toFixed(2)} G${world.real ? " · FROM YOUR JOURNAL" : ""}`, W / 2, 90, heavy ? 13 : 11, heavy ? colours.red : colours.text);
    if (heavy && Math.floor(cab.tick / 25) % 2) text("HIGH GRAVITY", W / 2, 108, 12, colours.red);
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 8, 8, colours.dim);
  }

  function drawBanner() {
    const banner = run.banner;
    if (!banner || cab.state !== "play") return;
    ctx.globalAlpha = clamp(banner.t / 30, 0, 1);
    const tone = banner.good ? colours.green : banner.text === "HULL BREACH" ? colours.red : colours.text;
    text(banner.text, W / 2, 250, 30, tone, "center", 700, Kit.DISPLAY);
    if (banner.sub) text(banner.sub, W / 2, 276, 12, banner.heavy ? colours.red : colours.accent);
    ctx.globalAlpha = 1;
  }

  function draw() {
    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, 0, W, H);
    drawWorld();
    if (cab.state !== "title") drawShip();
    for (const spark of sparks) {
      ctx.globalAlpha = clamp(spark.life / 40, 0, 1);
      ctx.fillStyle = spark.colour;
      ctx.fillRect(spark.x - 1.5, spark.y - 1.5, 3, 3);
    }
    ctx.globalAlpha = 1;
    if (run.flash > 0) { ctx.fillStyle = `rgba(255, 120, 60, ${run.flash / 50})`; ctx.fillRect(0, 0, W, H); }
    drawHud();
    drawBanner();
    if (cab.state === "title") {
      const note = live ? `YOU'RE AT ${live.body.toUpperCase()} · ${live.gravity.toFixed(2)} G: WE LAND THERE` : "AWAY FROM ANY WORLD: WE'LL FIND ONE";
      cab.titleScreen({top: "TOUCH", bottom: "DOWN", tone: colours.green, y: 170,
        rows: [["×2 PAD", "100"], ["×3 PAD", "150"], ["×5 PAD", "250"], ["SOFT ON THE PAD", "DOUBLE"]], note,
        how: "← → OR MOUSE TO TURN · ↑ / SPACE / HOLD CLICK TO BURN"});
    } else if (cab.state === "over") {
      cab.overScreen({heading: run.fuel <= 0 ? "OUT OF FUEL" : "NO SHIPS LEFT", tone: colours.red, sub: "LANDING DEBRIEF",
        rankLabel: "EXPLORER RANK", rank: Kit.rank(run.score, .1, "explore"),
        lines: [["SCORE", run.score.toLocaleString()], ["WORLDS", run.level], ["LANDINGS", run.landings], ["SOFT TOUCHDOWNS", run.soft],
          ["LAST WORLD", `${world.gravity.toFixed(2)} G`]]});
    }
  }

  function report() {
    return {score: run.score, level: run.level, ships: run.ships, fuel: run.fuel, gravity: world?.gravity ?? null, body: world?.body ?? "", real: Boolean(world?.real)};
  }

  function debugOver() {
    run.score += 1234;
    run.ships = 0;
    finish();
  }

  function card() {
    startGame();
    world = {body: "SYNUEFE XR-H D11-102 1 B", gravity: 2.38, real: false};
    run.score = 2450;
    run.level = 4;
    run.fuel = 610;
    run.banner = null;
    const pad = pads[pads.length - 1];
    ship.x = (pad.x1 + pad.x2) / 2 - 30;
    ship.y = pad.y - 120;
    ship.vx = .4;
    ship.vy = .6;
    ship.angle = -.18;
    ship.legs = .5;
    run.demo = 600;
  }

  window.touchdown = {state: () => ({...report(), state: cab.state})};
})();
