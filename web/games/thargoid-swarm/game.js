// Thargoid Swarm (5.6.3): the Games page's first cabinet. A swarm comes in
// formation and peels off to dive; every third wave an Interceptor comes,
// its hearts its health. The loop, sound, input and deck messages are the
// shared kit's (web/games/kit).
(() => {
  "use strict";

  const W = 540, H = 720;
  const {pad, clamp, chance} = Kit;

  const colours = {bg: "#05080c", panel: "#0d141c", accent: "#00d1ff", orange: "#ff8a3d", text: "#dcebf3",
    muted: "#91a8b7", dim: "#607584", green: "#54e39a", yellow: "#f5c76d", red: "#ff6b70"};
  const HULL = "#0b1512";
  const CAUSTIC = "#8dffb8";
  const ENEMY = {
    thargon: {w: 22, h: 20, hp: 1, score: 50, dive: 100, colour: "#4ee5b0", label: "THARGON"},
    scout: {w: 26, h: 24, hp: 1, score: 80, dive: 160, colour: "#b48cff", label: "SCOUT"},
    orthrus: {w: 30, h: 28, hp: 2, score: 150, dive: 400, colour: "#ff7a3d", label: "ORTHRUS"},
  };
  const ROWS = [["orthrus", 4], ["scout", 8], ["scout", 8], ["thargon", 10], ["thargon", 10]];
  // Interceptors in the order they came, with their hearts.
  const BOSSES = [["CYCLOPS", 4], ["BASILISK", 5], ["MEDUSA", 6], ["HYDRA", 8]];
  const WEAPONS = ["", "PULSE LASER", "TWIN PULSE", "FRAG SPREAD"];
  const DROPS = {
    weapon: {glyph: "W", colour: () => colours.orange},
    shield: {glyph: "S", colour: () => colours.accent},
    life: {glyph: "+", colour: () => colours.green},
  };

  const cab = Kit.cabinet({width: W, height: H, colours, start: startGame, update, draw, report, end: debugOver, card});
  const {ctx} = cab;
  const {poly, glow, text} = cab.draw;
  const pointer = cab.input.pointer;
  const game = {score: 0, wave: 0, lives: 3, shots: 0, hits: 0, bosses: 0,
    lost: false, banner: null, shift: 0, clearing: 0, quake: 0};
  let player = null;
  let shots = [], bolts = [], enemies = [], drops = [], sparks = [], words = [];
  let boss = null;
  const sway = {x: 0, dir: 1, speed: .6};
  let diveClock = 0;
  const stars = Array.from({length: 120}, () => ({x: Math.random() * W, y: Math.random() * H, z: .25 + Math.random() * 1.75, tint: Math.random()}));

  const rank = (score) => Kit.rank(score);

  // ---- Sound. ----
  const sound = (() => {
    const {tone, hiss} = cab.sound;
    return {
      shoot(level) { tone("square", 1150 + level * 140, 360, .07, .14); },
      pop() { hiss(.18, .4, 2600); tone("triangle", 320, 60, .14, .2); },
      clank() { tone("square", 190, 90, .07, .22); },
      dive() { tone("sine", 980, 240, .5, .1); },
      drop() { [523, 659, 784, 1047].forEach((f, i) => tone("square", f, f, .08, .12, i * .065)); },
      warn() {
        for (let i = 0; i < 3; i += 1) {
          tone("sawtooth", 440, 440, .22, .14, i * .5);
          tone("sawtooth", 311, 311, .22, .14, i * .5 + .25);
        }
      },
      heart() { hiss(.45, .6, 3200); tone("sawtooth", 640, 70, .55, .22); },
      boom() { hiss(.9, .8, 1400); tone("sawtooth", 150, 28, .8, .3); },
      clear() { [392, 523, 659, 784, 1047].forEach((f, i) => tone("triangle", f, f * 1.01, .15, .2, i * .085)); },
      hit() { hiss(.7, .8, 1000); tone("sawtooth", 520, 40, .75, .3); },
    };
  })();

  // ---- Waves. ----
  function newPlayer() {
    return {x: W / 2, y: H - 64, cooldown: 0, guard: 120, weapon: 1, shield: 0, tilt: 0};
  }

  function startGame() {
    pointer.active = false;
    Object.assign(game, {score: 0, wave: 0, lives: 3, shots: 0, hits: 0, bosses: 0,
      clearing: 0, banner: null, quake: 0});
    player = newPlayer();
    shots = []; bolts = []; drops = []; sparks = []; words = [];
    nextWave();
  }

  function nextWave() {
    game.wave += 1;
    game.lost = false;
    game.shift = 80;
    enemies = [];
    bolts = [];
    boss = null;
    sway.x = 0;
    if (game.wave % 3 === 0) spawnBoss();
    else {
      formation();
      game.banner = {text: `WAVE ${pad(game.wave)}`, sub: game.wave === 1 ? "THE SWARM IS HERE" : "MORE OF THEM", t: 150};
    }
  }

  function formation() {
    const gap = 42, rowGap = 36, top = 104;
    ROWS.forEach(([kind, count], row) => {
      const left = W / 2 - (count - 1) * gap / 2;
      for (let index = 0; index < count; index += 1) {
        const fromLeft = (index < count / 2) === (row % 2 === 0);
        enemies.push({
          kind, hp: ENEMY[kind].hp, slotX: left + index * gap, slotY: top + row * rowGap,
          x: fromLeft ? -40 : W + 40, y: 150 + row * 18, sx: 0, sy: 0, fromLeft,
          state: "wait", delay: 70 + row * 16 + (fromLeft ? index : count - 1 - index) * 5,
          t: 0, flash: 0, angle: 0, phase: Math.random() * Math.PI * 2,
        });
      }
    });
    sway.speed = Math.min(.45 + game.wave * .1, 1.5);
    diveClock = 200;
  }

  function spawnBoss() {
    const tier = game.wave / 3;
    const [name, hearts] = BOSSES[Math.min(BOSSES.length - 1, tier - 1)];
    const mark = tier > BOSSES.length ? ` MK ${tier - BOSSES.length + 1}` : "";
    const per = 9 + tier * 3;
    boss = {name: `${name}${mark}`, hearts, per, hp: hearts * per, max: hearts * per, tier,
      x: W / 2, y: -110, home: 168, state: "enter", t: 0, flash: 0, cool: 120, minions: 240, spin: 0, burst: 0};
    sound.warn();
    game.banner = {text: "WARNING", sub: `THARGOID INTERCEPTOR · ${boss.name}`, t: 200, alarm: true};
  }

  function slot(enemy) {
    return [enemy.slotX + sway.x, enemy.slotY + Math.sin(cab.tick * .05 + enemy.slotX * .02) * 3];
  }

  function launch(enemy, lead = null, offset = 0) {
    enemy.state = "dive";
    enemy.t = 0;
    enemy.side = enemy.x < W / 2 ? -1 : 1;
    enemy.sx = enemy.x;
    enemy.sy = enemy.y;
    enemy.lead = lead;
    enemy.offset = offset;
    enemy.fired = 0;
    enemy.anchor = enemy.x;
    enemy.amp = 40 + Math.random() * 70;
    enemy.freq = .028 + Math.random() * .025;
  }

  function dive() {
    const waiting = enemies.filter((enemy) => enemy.state === "form");
    if (!waiting.length) return;
    const pick = waiting[Math.floor(Math.random() * waiting.length)];
    launch(pick);
    sound.dive();
    // An Orthrus takes its two nearest Scouts with it.
    if (pick.kind === "orthrus") {
      waiting.filter((enemy) => enemy.kind === "scout" && enemy !== pick)
        .sort((a, b) => Math.abs(a.slotX - pick.slotX) + a.slotY - (Math.abs(b.slotX - pick.slotX) + b.slotY))
        .slice(0, 2)
        .forEach((escort, index) => launch(escort, pick, index ? 26 : -26));
    }
  }

  function fireBolt(x, y, angle, speed) {
    bolts.push({x, y, vx: Math.sin(angle) * speed, vy: Math.cos(angle) * speed, r: 4});
  }

  function aimAt(x, y) {
    return Math.atan2(player.x - x, player.y - y);
  }

  function boltSpeed() {
    return Math.min(3.4 + game.wave * .16, 6);
  }

  // ---- The player. ----
  function fire() {
    if (player.cooldown > 0) return;
    const level = player.weapon;
    const pattern = level === 1 ? [[0, 0]] : level === 2 ? [[-8, 0], [8, 0]] : [[-8, 0], [8, 0], [-12, -2.3], [12, 2.3]];
    for (const [dx, vx] of pattern) shots.push({x: player.x + dx, y: player.y - 16, vx, vy: -11.5});
    game.shots += pattern.length;
    player.cooldown = level === 1 ? 13 : 11;
    sound.shoot(level);
  }

  function hurtPlayer() {
    if (player.guard > 0 || cab.state !== "play") return;
    if (player.shield > 0) {
      player.shield = 0;
      player.guard = 50;
      burst(player.x, player.y, [colours.accent, "#ffffff"], 18, 3);
      say(player.x, player.y - 30, "SHIELDS DOWN", colours.accent);
      sound.clank();
      return;
    }
    game.lives -= 1;
    game.lost = true;
    game.quake = 18;
    burst(player.x, player.y, [colours.accent, colours.orange, "#ffffff", colours.yellow], 46, 5);
    sound.hit();
    if (game.lives <= 0) return gameOver();
    player.weapon = Math.max(1, player.weapon - 1);
    player.x = W / 2;
    player.guard = 160;
    player.shield = 0;
    bolts = [];
    say(W / 2, H / 2 + 40, "REBUY", colours.text);
  }

  function gameOver() {
    cab.over({score: game.score, wave: game.wave, accuracy: accuracy(), rank: rank(game.score)});
  }

  function accuracy() {
    return game.shots ? Math.round(game.hits / game.shots * 100) : 0;
  }

  // ---- Effects. ----
  function burst(x, y, palette, count = 20, speed = 4) {
    for (let index = 0; index < count; index += 1) {
      const angle = Math.random() * Math.PI * 2, velocity = .6 + Math.random() * speed;
      sparks.push({x, y, vx: Math.cos(angle) * velocity, vy: Math.sin(angle) * velocity, life: 24 + Math.random() * 26,
        max: 50, size: 1.5 + Math.random() * 3, colour: palette[Math.floor(Math.random() * palette.length)]});
    }
  }

  function say(x, y, text, colour = colours.yellow) {
    words.push({x, y, text, colour, life: 60});
  }

  function addScore(points, x, y, colour) {
    game.score += points;
    if (x !== undefined) say(x, y, String(points), colour);
  }

  function maybeDrop(x, y, sure = false) {
    if (!sure && !chance(.09)) return;
    const roll = Math.random();
    const type = sure ? (player.weapon < 3 ? "weapon" : "life") : roll < .55 ? "weapon" : roll < .86 ? "shield" : "life";
    drops.push({x, y, type, spin: 0});
  }

  function collect(drop) {
    sound.drop();
    if (drop.type === "weapon") {
      if (player.weapon < 3) {
        player.weapon += 1;
        say(drop.x, drop.y - 20, WEAPONS[player.weapon], colours.orange);
      } else addScore(500, drop.x, drop.y - 20, colours.orange);
    } else if (drop.type === "shield") {
      player.shield = 15 * 60;
      say(drop.x, drop.y - 20, "SHIELD CELL", colours.accent);
    } else {
      game.lives = Math.min(6, game.lives + 1);
      say(drop.x, drop.y - 20, "REBUY +1", colours.green);
    }
  }

  function kill(enemy) {
    const spec = ENEMY[enemy.kind];
    const points = enemy.state === "form" ? spec.score : spec.dive;
    addScore(points, enemy.x, enemy.y, enemy.state === "form" ? colours.text : colours.yellow);
    burst(enemy.x, enemy.y, [spec.colour, CAUSTIC, "#ffffff"], 22, 3.8);
    sound.pop();
    maybeDrop(enemy.x, enemy.y, false);
    enemy.dead = true;
  }

  // ---- One step. ----
  function update() {
    if (game.shift > 0) game.shift -= 1;
    for (const star of stars) {
      star.y += star.z * (game.shift > 0 ? 2 + game.shift * .3 : .55);
      if (star.y > H) { star.y -= H; star.x = Math.random() * W; }
    }
    updateEffects();
    if (cab.state !== "play") return;

    if (game.banner && --game.banner.t <= 0) game.banner = null;
    if (game.quake > 0) game.quake -= 1;
    movePlayer();
    moveShots();
    if (boss) updateBoss();
    updateSwarm();
    moveBolts();
    moveDrops();
    enemies = enemies.filter((enemy) => !enemy.dead);

    if (cab.state === "play" && !boss && !enemies.length) {
      if (!game.clearing) {
        game.clearing = 100;
        const bonus = 300 * game.wave;
        addScore(bonus);
        sound.clear();
        game.banner = {text: `WAVE ${pad(game.wave)} CLEAR`, sub: `BONUS ${bonus.toLocaleString()}${game.lost ? "" : " · FLAWLESS +1,000"}`, t: 100};
        if (!game.lost) addScore(1000);
      } else if (--game.clearing <= 0) {
        game.clearing = 0;
        nextWave();
      }
    }
  }

  function updateEffects() {
    for (const spark of sparks) {
      spark.x += spark.vx;
      spark.y += spark.vy;
      spark.vx *= .96;
      spark.vy *= .96;
      spark.life -= 1;
    }
    sparks = sparks.filter((spark) => spark.life > 0);
    for (const word of words) {
      word.y -= .6;
      word.life -= 1;
    }
    words = words.filter((word) => word.life > 0);
  }

  function movePlayer() {
    const left = cab.input.held(...Kit.LEFT);
    const right = cab.input.held(...Kit.RIGHT);
    let dx = (right ? 5.4 : 0) - (left ? 5.4 : 0);
    if (dx) pointer.active = false;
    else if (pointer.active) dx = clamp(pointer.x - player.x, -7, 7);
    player.x = clamp(player.x + dx, 22, W - 22);
    player.tilt += (clamp(dx / 6, -1, 1) - player.tilt) * .2;
    if (player.cooldown > 0) player.cooldown -= 1;
    if (player.guard > 0) player.guard -= 1;
    if (player.shield > 0) player.shield -= 1;
    if (cab.input.held("Space", ...Kit.UP) || pointer.down) fire();
  }

  function moveShots() {
    for (const shot of shots) {
      shot.x += shot.vx;
      shot.y += shot.vy;
      if (boss && boss.state === "fight" && Math.abs(shot.x - boss.x) < 48 && Math.abs(shot.y - boss.y) < 42) {
        shot.dead = true;
        game.hits += 1;
        hitBoss();
        continue;
      }
      for (const enemy of enemies) {
        if (enemy.dead || enemy.state === "wait") continue;
        const spec = ENEMY[enemy.kind];
        if (Math.abs(shot.x - enemy.x) < spec.w / 2 + 3 && Math.abs(shot.y - enemy.y) < spec.h / 2 + 7) {
          shot.dead = true;
          game.hits += 1;
          enemy.hp -= 1;
          enemy.flash = 8;
          if (enemy.hp <= 0) kill(enemy);
          else { sound.clank(); burst(shot.x, shot.y, [spec.colour], 6, 2); }
          break;
        }
      }
    }
    shots = shots.filter((shot) => !shot.dead && shot.y > -20 && shot.x > -20 && shot.x < W + 20);
  }

  function updateSwarm() {
    sway.x += sway.dir * sway.speed;
    if (Math.abs(sway.x) > 44) { sway.x = clamp(sway.x, -44, 44); sway.dir *= -1; }
    const settled = enemies.length && enemies.every((enemy) => enemy.state !== "wait" && enemy.state !== "enter");
    const diving = enemies.filter((enemy) => enemy.state === "dive" || enemy.state === "return").length;
    const most = Math.min(2 + Math.floor(game.wave / 2), 6);
    if (settled && !boss && --diveClock <= 0) {
      if (diving < most) dive();
      const few = enemies.length <= 8;
      diveClock = Math.max(34, 112 - game.wave * 9) * (few ? .5 : 1) * (.7 + Math.random() * .6);
    }
    // The formation's own fire, from whoever is at the front.
    if (settled && chance(Math.min(.0035 * game.wave, .018))) {
      const front = enemies.filter((enemy) => enemy.state === "form");
      const shooter = front[Math.floor(Math.random() * front.length)];
      if (shooter) fireBolt(shooter.x, shooter.y + 10, aimAt(shooter.x, shooter.y) * .35, boltSpeed() * .85);
    }
    for (const enemy of enemies) {
      if (enemy.flash > 0) enemy.flash -= 1;
      if (enemy.state === "wait") {
        if (--enemy.delay <= 0) { enemy.state = "enter"; enemy.sx = enemy.x; enemy.sy = enemy.y; enemy.t = 0; }
        continue;
      }
      if (enemy.state === "enter") {
        enemy.t = Math.min(1, enemy.t + 1 / 90);
        const [ex, ey] = slot(enemy);
        const cx = enemy.fromLeft ? W * .78 : W * .22, cy = 470;
        const t = enemy.t, u = 1 - t;
        const x = u * u * enemy.sx + 2 * u * t * cx + t * t * ex;
        const y = u * u * enemy.sy + 2 * u * t * cy + t * t * ey;
        enemy.angle = Math.atan2(x - enemy.x, y - enemy.y);
        enemy.x = x;
        enemy.y = y;
        if (enemy.t >= 1) { enemy.state = "form"; enemy.angle = 0; }
      } else if (enemy.state === "form") {
        [enemy.x, enemy.y] = slot(enemy);
        enemy.angle *= .8;
      } else if (enemy.state === "dive") {
        diveStep(enemy);
      } else if (enemy.state === "return") {
        const [ex, ey] = slot(enemy);
        enemy.x += (ex - enemy.x) * .06;
        enemy.y += (ey - enemy.y) * .06;
        enemy.angle *= .9;
        if (Math.hypot(ex - enemy.x, ey - enemy.y) < 2) enemy.state = "form";
      }
      if (enemy.state === "dive" && player.guard <= 0 && Math.abs(enemy.x - player.x) < 18 && Math.abs(enemy.y - player.y) < 16) {
        kill(enemy);
        hurtPlayer();
      }
    }
  }

  function diveStep(enemy) {
    enemy.t += 1;
    const lead = enemy.lead && !enemy.lead.dead && enemy.lead.state === "dive" ? enemy.lead : null;
    let x, y;
    if (lead) {
      x = lead.x + enemy.offset;
      y = lead.y + 18;
    } else if (enemy.t < 40) {
      // Peel off: a half loop up and out of the line.
      const a = enemy.t / 40 * Math.PI;
      x = enemy.sx - enemy.side * 28 * (1 - Math.cos(a));
      y = enemy.sy - 28 * Math.sin(a);
      enemy.anchor = x;
    } else {
      enemy.anchor += clamp(player.x - enemy.anchor, -1.3, 1.3);
      x = enemy.anchor + Math.sin((enemy.t - 40) * enemy.freq) * enemy.amp;
      y = enemy.y + Math.min(2.6 + game.wave * .14, 4.8);
      const most = game.wave > 3 ? 2 : 1;
      if (y > 150 && y < H - 230 && enemy.fired < most && chance(.025)) {
        enemy.fired += 1;
        fireBolt(x, y + 10, aimAt(x, y), boltSpeed());
      }
    }
    const angle = Math.atan2(x - enemy.x, y - enemy.y);
    enemy.angle += (angle - enemy.angle) * .25;
    enemy.x = x;
    enemy.y = y;
    if (enemy.y > H + 30) {
      if (enemy.minion) { enemy.dead = true; return; }
      // Out the bottom and back in at the top, to its place.
      enemy.state = "return";
      enemy.lead = null;
      enemy.y = -30;
      enemy.x = slot(enemy)[0];
    }
  }

  function updateBoss() {
    boss.t += 1;
    boss.spin += .008 + (heartsLeft() <= boss.hearts / 2 ? .01 : 0);
    if (boss.flash > 0) boss.flash -= 1;
    if (boss.state === "enter") {
      boss.y += (boss.home - boss.y) * .025;
      if (Math.abs(boss.home - boss.y) < 1.5) { boss.state = "fight"; boss.t = 0; }
      return;
    }
    const angry = heartsLeft() <= boss.hearts / 2;
    boss.x = W / 2 + Math.sin(boss.t * .012 * (angry ? 1.6 : 1)) * 170;
    boss.y = boss.home + Math.sin(boss.t * .023) * 26;
    if (boss.burst > 0 && boss.t % 9 === 0) {
      boss.burst -= 1;
      fireBolt(boss.x, boss.y + 34, aimAt(boss.x, boss.y + 34), boltSpeed() * 1.1);
    }
    if (--boss.cool <= 0) {
      const roll = Math.random();
      if (angry && roll < .3) {
        const count = 12 + boss.tier * 2;
        for (let index = 0; index < count; index += 1) fireBolt(boss.x, boss.y, index / count * Math.PI * 2 + boss.spin, boltSpeed() * .75);
      } else if (roll < .65) {
        const count = 5 + Math.min(boss.tier, 3);
        for (let index = 0; index < count; index += 1) fireBolt(boss.x, boss.y + 30, (index - (count - 1) / 2) * .17, boltSpeed() * .9);
      } else {
        boss.burst = 3 + Math.min(boss.tier, 3);
      }
      boss.cool = Math.max(42, 104 - boss.tier * 8) * (angry ? .72 : 1);
    }
    if (--boss.minions <= 0) {
      boss.minions = Math.max(150, 270 - boss.tier * 20);
      for (const side of [-1, 1]) {
        const minion = {kind: "thargon", hp: 1, slotX: boss.x, slotY: boss.y, x: boss.x + side * 30, y: boss.y + 20,
          state: "form", flash: 0, angle: 0, minion: true};
        launch(minion);
        minion.t = 40;
        minion.anchor = minion.x;
        enemies.push(minion);
      }
      sound.dive();
    }
    if (player.guard <= 0 && Math.abs(player.x - boss.x) < 44 && Math.abs(player.y - boss.y) < 40) hurtPlayer();
  }

  function heartsLeft() {
    return boss ? Math.ceil(boss.hp / boss.per) : 0;
  }

  function hitBoss() {
    const before = heartsLeft();
    boss.hp -= 1;
    boss.flash = 6;
    if (boss.hp <= 0) {
      const points = 2500 * boss.tier;
      addScore(points, boss.x, boss.y - 50, colours.yellow);
      game.bosses += 1;
      game.quake = 30;
      for (let index = 0; index < 6; index += 1) {
        burst(boss.x + (Math.random() - .5) * 90, boss.y + (Math.random() - .5) * 70, [CAUSTIC, colours.orange, "#ffffff", "#4ee5b0"], 34, 6);
      }
      sound.boom();
      maybeDrop(boss.x, boss.y, true);
      say(boss.x, boss.y + 30, `${boss.name} DOWN`, CAUSTIC);
      enemies.forEach((enemy) => { if (enemy.minion) kill(enemy); });
      boss = null;
      return;
    }
    if (heartsLeft() < before) {
      sound.heart();
      game.quake = 10;
      const a = boss.spin + (heartsLeft()) * Math.PI * 2 / boss.hearts;
      burst(boss.x + Math.sin(a) * 34, boss.y + Math.cos(a) * 34, [colours.orange, CAUSTIC, "#ffffff"], 30, 5);
      say(boss.x, boss.y - 60, "HEART DESTROYED", colours.orange);
      addScore(250 * boss.tier);
    } else if (boss.t % 3 === 0) sound.clank();
  }

  function moveBolts() {
    for (const bolt of bolts) {
      bolt.x += bolt.vx;
      bolt.y += bolt.vy;
      if (player.guard <= 0 && Math.abs(bolt.x - player.x) < 11 && Math.abs(bolt.y - player.y) < 10) {
        bolt.dead = true;
        hurtPlayer();
      }
    }
    bolts = bolts.filter((bolt) => !bolt.dead && bolt.y < H + 20 && bolt.y > -40 && bolt.x > -20 && bolt.x < W + 20);
  }

  function moveDrops() {
    for (const drop of drops) {
      drop.y += 1.7;
      drop.spin += .06;
      if (Math.abs(drop.x - player.x) < 20 && Math.abs(drop.y - player.y) < 20) {
        drop.dead = true;
        collect(drop);
      }
    }
    drops = drops.filter((drop) => !drop.dead && drop.y < H + 20);
  }

  // ---- Drawing. ----
  const DISPLAY = Kit.DISPLAY;

  function drawStars() {
    for (const star of stars) {
      const tone = star.tint < .7 ? "#ffffff" : star.tint < .85 ? colours.accent : star.tint < .95 ? "#ffd2a1" : "#b48cff";
      ctx.globalAlpha = .25 + star.z * .35;
      ctx.fillStyle = tone;
      if (game.shift > 0) {
        const length = star.z * game.shift * .35;
        ctx.fillRect(star.x, star.y - length, star.z > 1.3 ? 2 : 1, length);
      } else {
        const size = star.z > 1.4 ? 2 : 1;
        ctx.fillRect(star.x, star.y, size, size);
      }
    }
    ctx.globalAlpha = 1;
  }

  function drawCobra(x, y, tilt, small = 1) {
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(small * (1 - Math.abs(tilt) * .12), small);
    // A Cobra Mk III from above-behind: the wide flat wedge.
    poly([[0, -15], [9, -7], [19, 5], [13, 10], [-13, 10], [-19, 5], [-9, -7]]);
    ctx.fillStyle = colours.panel;
    ctx.fill();
    glow(colours.accent, 10);
    ctx.strokeStyle = colours.accent;
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.shadowBlur = 0;
    poly([[0, -9], [5, -2], [0, 2], [-5, -2]]);
    ctx.fillStyle = colours.accent;
    ctx.globalAlpha = .55;
    ctx.fill();
    ctx.globalAlpha = 1;
    if (small === 1) {
      const flame = 5 + Math.random() * 5;
      ctx.fillStyle = colours.orange;
      glow(colours.orange, 12);
      for (const side of [-7, 7]) ctx.fillRect(side - 2, 10, 4, flame);
      ctx.shadowBlur = 0;
    }
    ctx.restore();
  }

  function drawPlayer() {
    if (!player || cab.state === "over") return;
    if (player.guard > 0 && Math.floor(player.guard / 5) % 2) return;
    drawCobra(player.x, player.y, player.tilt);
    if (player.shield > 0 && (player.shield > 120 || Math.floor(player.shield / 6) % 2)) {
      ctx.beginPath();
      ctx.ellipse(player.x, player.y - 2, 28, 24, 0, 0, Math.PI * 2);
      glow(colours.accent, 14);
      ctx.strokeStyle = colours.accent;
      ctx.globalAlpha = .55 + Math.sin(cab.tick * .2) * .2;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.shadowBlur = 0;
    }
  }

  function drawEnemy(enemy) {
    if (enemy.state === "wait") return;
    const spec = ENEMY[enemy.kind];
    const flap = 1 + Math.sin(cab.tick * .18 + (enemy.phase || 0)) * .08;
    const colour = enemy.flash ? "#ffffff" : spec.colour;
    ctx.save();
    ctx.translate(enemy.x, enemy.y);
    ctx.rotate(-enemy.angle);
    ctx.scale(flap, 1);
    ctx.fillStyle = HULL;
    ctx.strokeStyle = colour;
    ctx.lineWidth = 1.5;
    glow(colour, 8);
    if (enemy.kind === "thargon") {
      const points = [];
      for (let i = 0; i < 6; i += 1) points.push([Math.sin(i / 6 * Math.PI * 2) * 9, Math.cos(i / 6 * Math.PI * 2) * 8]);
      poly(points);
      ctx.fill();
      ctx.stroke();
      for (const a of [0, 2.09, 4.19]) {
        ctx.beginPath();
        ctx.moveTo(Math.sin(a) * 9, Math.cos(a) * 8);
        ctx.lineTo(Math.sin(a) * 13, Math.cos(a) * 12);
        ctx.stroke();
      }
    } else if (enemy.kind === "scout") {
      poly([[0, 13], [8, 1], [13, -10], [5, -5], [0, -12], [-5, -5], [-13, -10], [-8, 1]]);
      ctx.fill();
      ctx.stroke();
    } else {
      const points = [];
      for (let i = 0; i < 8; i += 1) {
        const r = i % 2 ? 9 : 15;
        points.push([Math.sin(i / 8 * Math.PI * 2) * r, Math.cos(i / 8 * Math.PI * 2) * r * .9]);
      }
      poly(points);
      ctx.fill();
      ctx.stroke();
    }
    // The glowing heart of every one of them.
    const hurt = enemy.kind === "orthrus" && enemy.hp === 1;
    ctx.beginPath();
    ctx.arc(0, 0, enemy.kind === "orthrus" ? 4.5 : 3, 0, Math.PI * 2);
    ctx.fillStyle = hurt && cab.tick % 8 < 4 ? colours.red : CAUSTIC;
    glow(ctx.fillStyle, 10);
    ctx.fill();
    ctx.restore();
    ctx.shadowBlur = 0;
  }

  function drawBoss() {
    if (!boss) return;
    const left = heartsLeft();
    ctx.save();
    ctx.translate(boss.x, boss.y);
    const lit = boss.flash ? "#ffffff" : "#4ee5b0";
    for (let i = 0; i < boss.hearts; i += 1) {
      const a = boss.spin + i * Math.PI * 2 / boss.hearts;
      ctx.save();
      ctx.rotate(-a);
      ctx.beginPath();
      ctx.ellipse(0, 34, 15, 30, 0, 0, Math.PI * 2);
      ctx.fillStyle = HULL;
      ctx.fill();
      glow(lit, 10);
      ctx.strokeStyle = lit;
      ctx.lineWidth = 1.6;
      ctx.stroke();
      // Hearts are lost in order, the last first.
      const alive = i < left;
      ctx.beginPath();
      ctx.arc(0, 40, alive ? 6 : 4, 0, Math.PI * 2);
      ctx.fillStyle = alive ? (boss.flash ? "#ffffff" : colours.orange) : "#2a1a12";
      glow(alive ? colours.orange : "transparent", alive ? 16 : 0);
      ctx.fill();
      ctx.restore();
    }
    ctx.beginPath();
    ctx.arc(0, 0, 18, 0, Math.PI * 2);
    ctx.fillStyle = HULL;
    ctx.fill();
    glow(CAUSTIC, 18);
    ctx.strokeStyle = CAUSTIC;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, 0, 7 + Math.sin(cab.tick * .15) * 1.5, 0, Math.PI * 2);
    ctx.fillStyle = CAUSTIC;
    ctx.fill();
    ctx.restore();
    ctx.shadowBlur = 0;

    // Its hearts as its health.
    const width = 300, x = (W - width) / 2, y = 74, gap = 4;
    const cell = (width - gap * (boss.hearts - 1)) / boss.hearts;
    text(boss.name, W / 2, y - 6, 11, CAUSTIC);
    for (let i = 0; i < boss.hearts; i += 1) {
      const fill = clamp((boss.hp - i * boss.per) / boss.per, 0, 1);
      ctx.fillStyle = "#1a2a22";
      ctx.fillRect(x + i * (cell + gap), y, cell, 6);
      ctx.fillStyle = colours.orange;
      ctx.fillRect(x + i * (cell + gap), y, cell * fill, 6);
    }
  }

  function drawShots() {
    ctx.fillStyle = colours.accent;
    glow(colours.accent, 8);
    for (const shot of shots) {
      ctx.save();
      ctx.translate(shot.x, shot.y);
      ctx.rotate(Math.atan2(shot.vx, -shot.vy));
      ctx.fillRect(-1.5, -7, 3, 14);
      ctx.restore();
    }
    glow(CAUSTIC, 10);
    for (const bolt of bolts) {
      ctx.beginPath();
      ctx.arc(bolt.x, bolt.y, bolt.r, 0, Math.PI * 2);
      ctx.fillStyle = CAUSTIC;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(bolt.x, bolt.y, bolt.r * .45, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff";
      ctx.fill();
    }
    ctx.shadowBlur = 0;
  }

  function drawDrops() {
    for (const drop of drops) {
      const spec = DROPS[drop.type];
      const colour = spec.colour();
      ctx.save();
      ctx.translate(drop.x, drop.y);
      ctx.rotate(drop.spin);
      poly([[0, -12], [12, 0], [0, 12], [-12, 0]]);
      ctx.fillStyle = HULL;
      ctx.fill();
      glow(colour, 12);
      ctx.strokeStyle = colour;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.restore();
      ctx.shadowBlur = 0;
      text(spec.glyph, drop.x, drop.y + 5, 13, colour);
    }
  }

  function drawEffects() {
    for (const spark of sparks) {
      ctx.globalAlpha = clamp(spark.life / spark.max, 0, 1);
      ctx.fillStyle = spark.colour;
      ctx.fillRect(spark.x - spark.size / 2, spark.y - spark.size / 2, spark.size, spark.size);
    }
    ctx.globalAlpha = 1;
    for (const word of words) {
      ctx.globalAlpha = clamp(word.life / 30, 0, 1);
      text(word.text, word.x, word.y, 12, word.colour);
    }
    ctx.globalAlpha = 1;
  }

  function drawHud() {
    text("SCORE", 18, 22, 10, colours.dim, "left");
    text(pad(game.score, 6), 18, 42, 18, colours.text, "left");
    text("BEST", W / 2, 22, 10, colours.dim);
    text(pad(Math.max(cab.best, game.score), 6), W / 2, 42, 18, colours.accent);
    text("WAVE", W - 18, 22, 10, colours.dim, "right");
    text(pad(game.wave), W - 18, 42, 18, colours.text, "right");
    if (cab.state === "title") return;
    for (let i = 0; i < Math.max(0, game.lives - 1); i += 1) drawCobra(24 + i * 26, H - 18, 0, .55);
    text(WEAPONS[player?.weapon || 1], W - 18, H - 22, 10, colours.orange, "right");
    if (player?.shield > 0) {
      ctx.fillStyle = colours.dim;
      ctx.fillRect(W - 118, H - 14, 100, 3);
      ctx.fillStyle = colours.accent;
      ctx.fillRect(W - 118, H - 14, 100 * player.shield / (15 * 60), 3);
    }
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 14, 9, colours.dim);
  }

  function drawBanner() {
    const banner = game.banner;
    if (!banner || cab.state !== "play") return;
    const fade = clamp(banner.t / 30, 0, 1);
    ctx.globalAlpha = fade;
    if (banner.alarm && Math.floor(banner.t / 15) % 2) {
      ctx.fillStyle = "rgba(255, 60, 60, .08)";
      ctx.fillRect(0, 0, W, H);
    }
    text(banner.text, W / 2, H / 2 - 10, 34, banner.alarm ? colours.red : colours.text, "center", 700, DISPLAY);
    if (banner.sub) text(banner.sub, W / 2, H / 2 + 18, 12, banner.alarm ? colours.orange : colours.accent);
    ctx.globalAlpha = 1;
  }

  function drawTitle() {
    ctx.fillStyle = "rgba(0, 0, 0, .45)";
    ctx.fillRect(0, 0, W, H);
    glow(CAUSTIC, 24);
    text("THARGOID", W / 2, 150, 54, CAUSTIC, "center", 700, DISPLAY);
    text("SWARM", W / 2, 204, 54, colours.text, "center", 700, DISPLAY);
    ctx.shadowBlur = 0;
    text("A VOID COMPASS ARCADE CABINET", W / 2, 234, 11, colours.accent);
    text("— SCORE ADVANCE TABLE —", W / 2, 300, 12, colours.muted);
    const rows = [["thargon", "50", "100"], ["scout", "80", "160"], ["orthrus", "150", "400"]];
    rows.forEach(([kind, still, diving], index) => {
      const y = 342 + index * 46;
      drawEnemy({kind, state: "form", x: W / 2 - 120, y, angle: 0, flash: 0, hp: 2, phase: index});
      text(ENEMY[kind].label, W / 2 - 88, y + 4, 12, ENEMY[kind].colour, "left");
      text(`${still} · ${diving} DIVING`, W / 2 + 150, y + 4, 12, colours.text, "right");
    });
    text("INTERCEPTOR EVERY THIRD WAVE · BREAK ITS HEARTS", W / 2, 498, 11, colours.orange);
    if (Math.floor(cab.tick / 30) % 2) text("PRESS SPACE OR CLICK TO LAUNCH", W / 2, 570, 15, colours.text);
    text("← → OR MOUSE TO FLY · SPACE OR CLICK TO FIRE · P PAUSE · M SOUND", W / 2, 610, 10, colours.dim);
  }

  function drawOver() {
    ctx.fillStyle = "rgba(0, 0, 0, .62)";
    ctx.fillRect(0, 0, W, H);
    text("SHIP DESTROYED", W / 2, 170, 40, colours.red, "center", 700, DISPLAY);
    text("COMBAT DEBRIEF", W / 2, 206, 12, colours.accent);
    const lines = [["SCORE", game.score.toLocaleString()], ["WAVE REACHED", pad(game.wave)],
      ["INTERCEPTORS DOWNED", String(game.bosses)], ["SHOTS FIRED", game.shots.toLocaleString()], ["ACCURACY", `${accuracy()}%`]];
    lines.forEach(([label, value], index) => {
      const y = 262 + index * 32;
      text(label, W / 2 - 150, y, 13, colours.muted, "left");
      text(value, W / 2 + 150, y, 15, colours.text, "right");
    });
    text("COMBAT RANK", W / 2, 448, 11, colours.dim);
    glow(CAUSTIC, 16);
    text(rank(game.score), W / 2, 482, 28, CAUSTIC, "center", 700, DISPLAY);
    ctx.shadowBlur = 0;
    if (cab.newBest) text("NEW BEST SCORE", W / 2, 520, 13, colours.yellow);
    if (cab.tick - cab.overAt > 60 && Math.floor(cab.tick / 30) % 2) text("PRESS SPACE OR CLICK TO FLY AGAIN", W / 2, 590, 14, colours.text);
  }

  function draw() {
    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, 0, W, H);
    if (game.quake > 0) ctx.translate((Math.random() - .5) * game.quake * .5, (Math.random() - .5) * game.quake * .5);
    drawStars();
    if (cab.state !== "title") {
      drawBoss();
      enemies.forEach(drawEnemy);
      drawShots();
      drawDrops();
      drawPlayer();
    }
    drawEffects();
    ctx.setTransform(cab.scale, 0, 0, cab.scale, 0, 0);
    drawHud();
    drawBanner();
    if (cab.state === "title") drawTitle();
    else if (cab.state === "over") drawOver();
  }

  function report() {
    return {score: game.score, wave: game.wave, lives: game.lives, enemies: enemies.length,
      boss: boss ? {name: boss.name, hp: boss.hp, hearts: heartsLeft()} : null, weapon: player?.weapon || 0};
  }

  function debugOver() {
    game.score += 1234;
    game.lives = 1;
    player.guard = 0;
    player.shield = 0;
    hurtPlayer();
  }

  // The card picture: wave two, mid-fight.
  function card() {
    startGame();
    cab.state = "play";
    game.wave = 1;
    nextWave();
    for (let i = 0; i < 560; i += 1) {
      cab.tick += 1;
      player.guard = 9;
      update();
      if (i > 500 && i % 14 === 0) fire();
    }
    player.guard = 0;
    game.banner = null;
  }

  window.thargoidSwarm = {state: () => ({...report(), state: cab.state, muted: cab.sound.muted}),
    // For tests: jump to a wave, or end the run.
    _wave(wave) { if (cab.state !== "play") cab.start(); game.wave = wave - 1; nextWave(); },
    _over() { window.cabinet.end(); }};
})();
