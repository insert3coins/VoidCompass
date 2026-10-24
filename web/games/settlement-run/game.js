// Settlement Run (5.6.3): on foot in an Odyssey settlement, after the 80s
// maze classic. Pick up every data port in the corridors while security
// patrols hunt you; an Energy Link overloads their suits for a while and
// the hunt turns round.
(() => {
  "use strict";

  // Left half of the maze (column 11 is the middle); the right is its mirror.
  // # wall, . data port, o Energy Link, - the security office door, , you, T the airlock tunnel.
  const LEFT = [
    "############", "#...........", "#o##.####.#.", "#...........", "#.##.#.#####", "#....#.....#",
    "####.####..#", "####.#......", "####.#.#.##-", "T........#  ", "####.#.#.###", "####.#......",
    "####.#.#####", "#...........", "#.##.####.#.", "#o.#.......,", "##.#.#.#####", "#....#.....#",
    "#.#######..#", "#...........", "############",
  ];
  const MAZE = LEFT.map((line) => line + [...line.slice(0, 11)].reverse().join(""));
  const COLS = MAZE[0].length, ROWS = MAZE.length, TILE = 26;
  const W = 600, H = 675, LEFT_X = (W - COLS * TILE) / 2, TOP_Y = 76;
  const DOOR = {x: 11, y: 8}, OUTSIDE = {x: 11, y: 7}, HOUSE = {x: 11, y: 9};
  const DIRS = [[0, -1], [-1, 0], [0, 1], [1, 0]];
  const {clamp, between, pick} = Kit;
  const colours = {bg: "#04060a", panel: "#0c1219", accent: "#00d1ff", orange: "#ff8a3d", text: "#e6eef5",
    muted: "#97a8b6", dim: "#5d6f7e", green: "#54e39a", yellow: "#f5c76d", red: "#ff6b70"};
  const GUARDS = [
    {name: "SENTRY", colour: "#ff5b61", corner: [COLS - 2, 0]},
    {name: "HUNTER", colour: "#ff8adf", corner: [1, 0]},
    {name: "WARDEN", colour: "#5fe0ff", corner: [COLS - 2, ROWS - 1]},
    {name: "OFFICER", colour: "#ffb35c", corner: [1, ROWS - 1]},
  ];
  // Scatter then chase, in seconds; the last chase lasts.
  const MODES = [7, 20, 7, 20, 5, 9999];

  const cab = Kit.cabinet({width: W, height: H, colours, start: startGame, update, draw, report, end: debugOver, card});
  const {ctx} = cab;
  const {text, glow} = cab.draw;
  const pointer = cab.input.pointer;

  const run = {score: 0, level: 0, lives: 3, banner: null, ports: 0, zapped: 0, chain: 0, link: 0, mode: 0, modeClock: 0, dying: 0, cleared: 0, bonus: null};
  let grid = MAZE.map((line) => [...line]), me = null, guards = [], words = [], eaten = 0, total = 0;

  const sfx = {
    port() { cab.sound.tone("square", cab.tick % 2 ? 520 : 600, 500, .04, .06); },
    link() { [330, 440, 554, 660].forEach((f, i) => cab.sound.tone("sawtooth", f, f, .1, .1, i * .05)); },
    zap() { cab.sound.tone("square", 1400, 200, .3, .14); },
    caught() { for (let i = 0; i < 6; i += 1) cab.sound.tone("triangle", 700 - i * 90, 650 - i * 90, .12, .14, i * .12); },
    bonus() { [784, 988, 1319].forEach((f, i) => cab.sound.tone("triangle", f, f, .1, .14, i * .07)); },
    clear() { [523, 659, 784, 1047, 1319].forEach((f, i) => cab.sound.tone("square", f, f, .12, .12, i * .09)); },
    alarm() { cab.sound.tone("sawtooth", 440, 330, .12, .04); },
  };

  function startGame() {
    Object.assign(run, {score: 0, level: 0, lives: 3, banner: null, ports: 0, zapped: 0, chain: 0, link: 0, dying: 0, cleared: 0, bonus: null});
    pointer.active = false;
    nextLevel();
  }

  function nextLevel() {
    run.level += 1;
    grid = MAZE.map((line) => [...line]);
    total = grid.flat().filter((c) => c === "." || c === "o").length;
    eaten = 0;
    run.banner = {text: `SETTLEMENT ${Kit.pad(run.level)}`, sub: "EVERY DATA PORT · KEEP AWAY FROM SECURITY", t: 140};
    placeEveryone();
  }

  function placeEveryone() {
    let start = {x: 11, y: 15};
    grid.forEach((row, y) => row.forEach((c, x) => { if (c === ",") { start = {x, y}; grid[y][x] = " "; } }));
    me = {x: start.x, y: start.y, dir: [-1, 0], want: [-1, 0], mouth: 0};
    guards = GUARDS.map((spec, index) => ({...spec, x: index === 0 ? OUTSIDE.x : 10 + (index - 1), y: index === 0 ? OUTSIDE.y : HOUSE.y,
      dir: [index % 2 ? 1 : -1, 0], state: index === 0 ? "out" : "home", wait: index * 4 * 60, stun: 0}));
    run.mode = 0;
    run.modeClock = MODES[0] * 60;
    run.link = 0;
  }

  const wrapX = (x) => ((x % COLS) + COLS) % COLS;
  const cell = (x, y) => (y < 0 || y >= ROWS ? "#" : grid[y][wrapX(x)]);
  const open = (x, y, guard = null) => {
    const c = cell(x, y);
    if (c === "#") return false;
    if (c === "-") return Boolean(guard) && (guard.state === "eyes" || guard.state === "leaving");
    return true;
  };

  function speeds() {
    const pace = Math.min(1 + (run.level - 1) * .06, 1.35);
    return {me: .118 * pace, guard: .108 * pace, stunned: .06, eyes: .24};
  }

  // Move along the grid: turns are taken at a tile's centre.
  function step(body, speed, choose) {
    const cx = Math.round(body.x), cy = Math.round(body.y);
    // Only the step that crosses the centre counts, or it would snap back there every step.
    const near = Math.abs(body.x - cx) + Math.abs(body.y - cy) <= speed / 2;
    if (near) {
      body.x = cx;
      body.y = cy;
      const dir = choose(cx, cy);
      if (dir) body.dir = dir;
      if (!open(cx + body.dir[0], cy + body.dir[1], body.guard ? body : null)) return false;
    }
    body.x += body.dir[0] * speed;
    body.y += body.dir[1] * speed;
    if (body.x < -.5) body.x += COLS;
    if (body.x > COLS - .5) body.x -= COLS;
    return true;
  }

  function moveMe() {
    const turn = cab.input.held(...Kit.UP) ? [0, -1] : cab.input.held(...Kit.DOWN) ? [0, 1]
      : cab.input.held(...Kit.LEFT) ? [-1, 0] : cab.input.held(...Kit.RIGHT) ? [1, 0] : null;
    if (turn) { me.want = turn; pointer.active = false; }
    else if (pointer.active) {
      const dx = pointer.x - (LEFT_X + (me.x + .5) * TILE), dy = pointer.y - (TOP_Y + (me.y + .5) * TILE);
      if (Math.hypot(dx, dy) > 18) me.want = Math.abs(dx) > Math.abs(dy) ? [Math.sign(dx), 0] : [0, Math.sign(dy)];
    }
    // Turning straight back needn't wait for a centre.
    if (me.want[0] === -me.dir[0] && me.want[1] === -me.dir[1]) me.dir = me.want;
    const moved = step(me, speeds().me, (x, y) => (open(x + me.want[0], y + me.want[1]) ? me.want : null));
    if (moved) me.mouth += .25;
    const tx = wrapX(Math.round(me.x)), ty = Math.round(me.y);
    const here = cell(tx, ty);
    if (here === "." || here === "o") {
      grid[ty][tx] = " ";
      eaten += 1;
      if (here === ".") { run.score += 10; run.ports += 1; if (cab.tick % 4 === 0) sfx.port(); }
      else energyLink();
      if (eaten === 70 || eaten === 170) run.bonus = {x: 11, y: 11, life: 9 * 60};
    }
    if (run.bonus && Math.abs(me.x - run.bonus.x) + Math.abs(me.y - run.bonus.y) < .6) {
      const points = Math.min(5000, 100 * 2 ** (run.level - 1) * 3);
      run.score += points;
      say(run.bonus.x, run.bonus.y, `PLANS +${points}`, colours.yellow);
      sfx.bonus();
      run.bonus = null;
    }
  }

  function energyLink() {
    run.score += 50;
    run.link = Math.max(120, 420 - (run.level - 1) * 40);
    run.chain = 0;
    sfx.link();
    for (const guard of guards) {
      if (guard.state === "eyes") continue;
      guard.stun = run.link;
      if (guard.state === "out") guard.dir = [-guard.dir[0], -guard.dir[1]];
    }
  }

  function target(guard) {
    const chase = run.mode % 2 === 1;
    if (!chase) return guard.corner;
    const px = Math.round(me.x), py = Math.round(me.y);
    if (guard.name === "SENTRY") return [px, py];
    if (guard.name === "HUNTER") return [px + me.dir[0] * 4, py + me.dir[1] * 4];
    if (guard.name === "WARDEN") {
      const lead = guards[0], ax = px + me.dir[0] * 2, ay = py + me.dir[1] * 2;
      return [ax * 2 - Math.round(lead.x), ay * 2 - Math.round(lead.y)];
    }
    return Math.hypot(px - guard.x, py - guard.y) > 8 ? [px, py] : guard.corner;
  }

  function moveGuard(guard) {
    guard.guard = true;
    const pace = speeds();
    if (guard.state === "home") {
      guard.y = HOUSE.y + Math.sin(cab.tick * .12 + guard.x) * .2;
      if (--guard.wait <= 0) { guard.state = "leaving"; guard.x = HOUSE.x; guard.y = HOUSE.y; guard.dir = [0, -1]; }
      return;
    }
    if (guard.state === "leaving") {
      guard.x = HOUSE.x;
      guard.y -= pace.guard * .8;
      if (guard.y <= OUTSIDE.y) { guard.y = OUTSIDE.y; guard.state = "out"; guard.dir = [-1, 0]; }
      return;
    }
    if (guard.stun > 0) guard.stun -= 1;
    const goal = guard.state === "eyes" ? [OUTSIDE.x, OUTSIDE.y] : target(guard);
    const speed = guard.state === "eyes" ? pace.eyes : guard.stun > 0 ? pace.stunned
      : Math.round(guard.y) === 9 && (guard.x < 5 || guard.x > COLS - 6) ? pace.guard * .55 : pace.guard;
    step(guard, speed, (x, y) => {
      const choices = DIRS.filter(([dx, dy]) => !(dx === -guard.dir[0] && dy === -guard.dir[1]) && open(x + dx, y + dy) && cell(x + dx, y + dy) !== "-");
      if (!choices.length) return [-guard.dir[0], -guard.dir[1]];
      if (guard.stun > 0 && guard.state !== "eyes") return pick(choices);
      return choices.reduce((best, dir) => {
        const d = Math.hypot(x + dir[0] - goal[0], y + dir[1] - goal[1]);
        return d < best.d ? {dir, d} : best;
      }, {dir: choices[0], d: Infinity}).dir;
    });
    if (guard.state === "eyes" && Math.abs(guard.x - OUTSIDE.x) + Math.abs(guard.y - OUTSIDE.y) < .3) {
      // Back through the door to reboot the suit.
      guard.state = "home";
      guard.x = HOUSE.x;
      guard.y = HOUSE.y;
      guard.wait = 60;
      guard.stun = 0;
    }
  }

  function say(x, y, value, colour) {
    words.push({x: LEFT_X + (x + .5) * TILE, y: TOP_Y + (y + .5) * TILE, text: value, colour, life: 70});
  }

  function finish() {
    cab.over({score: run.score, level: run.level, rank: Kit.rank(run.score, .2, "mercenary")});
  }

  function update() {
    for (const word of words) { word.y -= .5; word.life -= 1; }
    words = words.filter((word) => word.life > 0);
    if (cab.state !== "play") return;
    if (run.banner && --run.banner.t <= 0) run.banner = null;
    if (run.dying > 0) {
      if (--run.dying === 0) {
        if (run.lives <= 0) return finish();
        placeEveryone();
      }
      return;
    }
    if (run.cleared > 0) {
      if (--run.cleared === 0) nextLevel();
      return;
    }
    if (run.link > 0) run.link -= 1;
    else if (--run.modeClock <= 0 && run.mode < MODES.length - 1) {
      run.mode += 1;
      run.modeClock = MODES[run.mode] * 60;
      for (const guard of guards) if (guard.state === "out") guard.dir = [-guard.dir[0], -guard.dir[1]];
    }
    if (run.bonus && --run.bonus.life <= 0) run.bonus = null;
    moveMe();
    guards.forEach(moveGuard);
    for (const guard of guards) {
      if (guard.state !== "out" || Math.abs(guard.x - me.x) + Math.abs(guard.y - me.y) > .7) continue;
      if (guard.stun > 0) {
        guard.state = "eyes";
        guard.stun = 0;
        run.chain += 1;
        run.zapped += 1;
        const points = 200 * 2 ** (run.chain - 1);
        run.score += points;
        say(guard.x, guard.y, String(points), guard.colour);
        sfx.zap();
      } else {
        run.lives -= 1;
        run.dying = 110;
        run.banner = {text: `CAUGHT BY ${guard.name}`, sub: run.lives > 0 ? "SUIT REBOOTING" : "", t: 100, bad: true};
        sfx.caught();
        return;
      }
    }
    if (run.link > 0 && run.link < 90 && cab.tick % 15 === 0) sfx.alarm();
    if (eaten >= total) {
      run.cleared = 150;
      const bonus = 1000 * run.level;
      run.score += bonus;
      run.banner = {text: "SETTLEMENT EMPTIED", sub: `EVERY PORT DOWNLOADED · +${bonus.toLocaleString()}`, t: 150, good: true};
      sfx.clear();
    }
  }

  // ---- Drawing. ----
  function drawMaze() {
    const flash = run.cleared > 0 && Math.floor(run.cleared / 12) % 2;
    const edge = flash ? "#ffffff" : colours.accent;
    ctx.fillStyle = "#070c12";
    ctx.fillRect(LEFT_X, TOP_Y, COLS * TILE, ROWS * TILE);
    // Deck plates under everything.
    ctx.strokeStyle = "rgba(255,255,255,.03)";
    ctx.lineWidth = 1;
    for (let x = 0; x <= COLS; x += 1) { ctx.beginPath(); ctx.moveTo(LEFT_X + x * TILE, TOP_Y); ctx.lineTo(LEFT_X + x * TILE, TOP_Y + ROWS * TILE); ctx.stroke(); }
    for (let y = 0; y <= ROWS; y += 1) { ctx.beginPath(); ctx.moveTo(LEFT_X, TOP_Y + y * TILE); ctx.lineTo(LEFT_X + COLS * TILE, TOP_Y + y * TILE); ctx.stroke(); }
    ctx.lineWidth = 2;
    ctx.strokeStyle = edge;
    glow(edge, 8);
    ctx.beginPath();
    for (let y = 0; y < ROWS; y += 1) {
      for (let x = 0; x < COLS; x += 1) {
        const c = grid[y][x];
        const px = LEFT_X + x * TILE, py = TOP_Y + y * TILE;
        if (c !== "#") continue;
        ctx.save();
        // Walls: a dark block, with a lit edge wherever it meets a corridor.
        if (cell(x, y - 1) !== "#" && y > 0) { ctx.moveTo(px, py + 3); ctx.lineTo(px + TILE, py + 3); }
        if (cell(x, y + 1) !== "#" && y < ROWS - 1) { ctx.moveTo(px, py + TILE - 3); ctx.lineTo(px + TILE, py + TILE - 3); }
        if (x > 0 && cell(x - 1, y) !== "#") { ctx.moveTo(px + 3, py); ctx.lineTo(px + 3, py + TILE); }
        if (x < COLS - 1 && cell(x + 1, y) !== "#") { ctx.moveTo(px + TILE - 3, py); ctx.lineTo(px + TILE - 3, py + TILE); }
        ctx.restore();
      }
    }
    ctx.stroke();
    ctx.shadowBlur = 0;
    for (let y = 0; y < ROWS; y += 1) {
      for (let x = 0; x < COLS; x += 1) {
        const c = grid[y][x];
        const cx = LEFT_X + (x + .5) * TILE, cy = TOP_Y + (y + .5) * TILE;
        if (c === "#") {
          ctx.fillStyle = "#0d1824";
          ctx.fillRect(cx - TILE / 2 + 4, cy - TILE / 2 + 4, TILE - 8, TILE - 8);
        } else if (c === ".") {
          ctx.fillStyle = colours.accent;
          ctx.fillRect(cx - 2, cy - 2, 4, 4);
        } else if (c === "o") {
          const pulse = 6 + Math.sin(cab.tick * .15) * 2;
          glow(colours.yellow, 16);
          ctx.fillStyle = colours.yellow;
          ctx.beginPath(); ctx.moveTo(cx, cy - pulse); ctx.lineTo(cx + pulse * .6, cy); ctx.lineTo(cx, cy + pulse); ctx.lineTo(cx - pulse * .6, cy); ctx.closePath(); ctx.fill();
          ctx.shadowBlur = 0;
        } else if (c === "-") {
          ctx.fillStyle = colours.red;
          ctx.fillRect(cx - TILE / 2, cy - 2, TILE, 4);
        }
      }
    }
    text("SECURITY", LEFT_X + (HOUSE.x + .5) * TILE, TOP_Y + (HOUSE.y + .5) * TILE + 20, 7, colours.dim);
  }

  function drawMe() {
    if (!me) return;
    const cx = LEFT_X + (me.x + .5) * TILE, cy = TOP_Y + (me.y + .5) * TILE;
    const angle = Math.atan2(me.dir[1], me.dir[0]);
    ctx.save();
    ctx.translate(cx, cy);
    if (run.dying) {
      const k = 1 - run.dying / 110;
      ctx.globalAlpha = 1 - k;
      ctx.scale(1 + k, 1 + k);
    }
    ctx.rotate(angle);
    // The commander from above: shoulders, the helmet, the visor ahead.
    ctx.fillStyle = "#2a3440";
    ctx.beginPath(); ctx.ellipse(-2, 0, 7, 11, 0, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = colours.green; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.beginPath(); ctx.arc(1, 0, 7, 0, Math.PI * 2);
    ctx.fillStyle = "#e8eef2"; ctx.fill();
    const open = Math.abs(Math.sin(me.mouth)) * .5 + .15;
    ctx.beginPath(); ctx.arc(1, 0, 6.5, -open, open); ctx.lineTo(1, 0); ctx.closePath();
    ctx.fillStyle = colours.green;
    glow(colours.green, 10);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.restore();
    ctx.globalAlpha = 1;
  }

  function drawGuard(guard) {
    const cx = LEFT_X + (guard.x + .5) * TILE, cy = TOP_Y + (guard.y + .5) * TILE;
    const stunned = guard.stun > 0 && guard.state !== "eyes";
    const ending = stunned && guard.stun < 90 && Math.floor(guard.stun / 8) % 2;
    ctx.save();
    ctx.translate(cx + (stunned ? Math.sin(cab.tick * .8) : 0), cy);
    if (guard.state !== "eyes") {
      const tone = stunned ? (ending ? "#ffffff" : "#3a5cff") : guard.colour;
      // Armoured shoulders and a helmet with a visor slit.
      ctx.beginPath(); ctx.roundRect(-10, -4, 20, 13, 4);
      ctx.fillStyle = stunned ? "#101a40" : "#1c1410"; ctx.fill();
      glow(tone, 10);
      ctx.strokeStyle = tone; ctx.lineWidth = 1.6; ctx.stroke();
      ctx.beginPath(); ctx.arc(0, -3, 7.5, 0, Math.PI * 2);
      ctx.fillStyle = stunned ? "#1a2a70" : "#2a2a30"; ctx.fill(); ctx.stroke();
      ctx.shadowBlur = 0;
      if (stunned) {
        ctx.strokeStyle = "#9fd8ff"; ctx.lineWidth = 1;
        ctx.beginPath();
        for (let i = 0; i < 4; i += 1) { const a = cab.tick * .3 + i * 1.6; ctx.moveTo(Math.cos(a) * 9, Math.sin(a) * 9 - 3); ctx.lineTo(Math.cos(a + .4) * 13, Math.sin(a + .4) * 13 - 3); }
        ctx.stroke();
      }
    }
    // The visor, which is all that's left of one heading home.
    const look = guard.dir;
    ctx.fillStyle = guard.state === "eyes" ? "#ffffff" : stunned ? "#9fd8ff" : "#ff3030";
    glow(ctx.fillStyle, 8);
    ctx.fillRect(-5 + look[0] * 2, -4 + look[1] * 2, 10, 3);
    ctx.shadowBlur = 0;
    ctx.restore();
  }

  function drawHud() {
    cab.scoreBar(run.score, "SETTLEMENT", run.level);
    if (cab.state === "title") return;
    const y = TOP_Y + ROWS * TILE + 26;
    for (let i = 0; i < Math.max(0, run.lives - 1); i += 1) {
      ctx.beginPath(); ctx.arc(30 + i * 22, y, 7, 0, Math.PI * 2); ctx.fillStyle = "#e8eef2"; ctx.fill();
    }
    text(`DATA ${eaten}/${total}`, W / 2, y + 4, 11, colours.accent);
    if (run.link > 0) {
      text("ENERGY LINK", W - 18, y - 4, 10, colours.yellow, "right");
      cab.draw.bar(W - 128, y + 2, 110, 4, run.link / 420, colours.yellow);
    } else text(run.mode % 2 ? "SECURITY HUNTING" : "SECURITY PATROLLING", W - 18, y + 4, 10, run.mode % 2 ? colours.red : colours.muted, "right");
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 6, 8, colours.dim);
  }

  function draw() {
    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, 0, W, H);
    drawMaze();
    if (run.bonus) {
      const cx = LEFT_X + (run.bonus.x + .5) * TILE, cy = TOP_Y + (run.bonus.y + .5) * TILE;
      glow(colours.yellow, 14);
      ctx.fillStyle = "#2a2410";
      ctx.fillRect(cx - 8, cy - 6, 16, 12);
      ctx.strokeStyle = colours.yellow; ctx.lineWidth = 1.5; ctx.strokeRect(cx - 8, cy - 6, 16, 12);
      ctx.shadowBlur = 0;
      ctx.fillStyle = colours.yellow;
      for (let i = -1; i <= 1; i += 1) ctx.fillRect(cx + i * 4 - 1, cy - 2, 2, 4);
    }
    if (cab.state !== "title") {
      guards.forEach(drawGuard);
      drawMe();
    }
    for (const word of words) {
      ctx.globalAlpha = clamp(word.life / 30, 0, 1);
      text(word.text, word.x, word.y, 11, word.colour);
    }
    ctx.globalAlpha = 1;
    drawHud();
    const banner = run.banner;
    if (banner && cab.state === "play") {
      ctx.globalAlpha = clamp(banner.t / 30, 0, 1);
      ctx.fillStyle = "rgba(0,0,0,.65)";
      ctx.fillRect(0, TOP_Y + 11 * TILE - 2, W, TILE * 2 + 4);
      text(banner.text, W / 2, TOP_Y + 11 * TILE + 24, 22, banner.bad ? colours.red : banner.good ? colours.green : colours.text, "center", 700, Kit.DISPLAY);
      if (banner.sub) text(banner.sub, W / 2, TOP_Y + 12 * TILE + 22, 10, colours.accent);
      ctx.globalAlpha = 1;
    }
    if (cab.state === "title") {
      cab.titleScreen({top: "SETTLEMENT", bottom: "RUN", tone: colours.green, y: 170,
        rows: [["DATA PORT", "10"], ["ENERGY LINK", "50"], ["OVERLOADED GUARD", "200 · 400 · 800 · 1,600"], ["DEFENCE PLANS", "BONUS"],
          ["SETTLEMENT EMPTIED", "1,000 × LEVEL"]],
        note: "SENTRY CHASES · HUNTER HEADS YOU OFF · WARDEN FLANKS · OFFICER KEEPS ITS DISTANCE",
        how: "ARROWS / WASD OR MOUSE TO RUN · THE AIRLOCK TUNNEL WRAPS ROUND"});
    } else if (cab.state === "over") {
      cab.overScreen({heading: "DETAINED", tone: colours.red, sub: "SECURITY REPORT", rankLabel: "MERCENARY RANK", rank: Kit.rank(run.score, .2, "mercenary"),
        lines: [["SCORE", run.score.toLocaleString()], ["SETTLEMENT", run.level], ["PORTS DOWNLOADED", run.ports], ["GUARDS OVERLOADED", run.zapped]]});
    }
  }

  function report() {
    return {score: run.score, level: run.level, lives: run.lives, eaten, total, link: run.link, x: me?.x ?? 0, y: me?.y ?? 0,
      guards: guards.map((guard) => guard.state)};
  }

  function debugOver() {
    run.score += 1234;
    run.lives = 1;
    run.lives -= 1;
    run.dying = 1;
  }

  function card() {
    startGame();
    for (let i = 0; i < 480; i += 1) {
      cab.tick += 1;
      // A quick run round the bottom-left, as if someone were playing.
      if (i === 0) me.want = [-1, 0];
      if (i === 120) me.want = [0, -1];
      if (i === 240) me.want = [1, 0];
      update();
      if (run.dying) { run.dying = 0; run.lives = 3; placeEveryone(); }
    }
    energyLink();
    run.link = 200;
    run.banner = null;
    run.score = Math.max(run.score, 3420);
  }

  window.settlementRun = {state: () => ({...report(), state: cab.state})};
})();
