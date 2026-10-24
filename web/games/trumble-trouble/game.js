// Trumble Trouble (5.6.3): Elite's own secret. Furry Trumbles breed in the
// hold, faster the more food they find. Catch them, then vent them out of
// the airlock, or keep them until the ship docks and sell them to a buyer.
// When the hold is full of fur, the run is over.
(() => {
  "use strict";

  const W = 600, H = 675;
  const HOLD = {x: 30, y: 96, w: 540, h: 470};
  const FULL = 70, CAGE = 5;
  const {clamp, between, chance, pick} = Kit;
  const colours = {bg: "#07070a", panel: "#12121a", accent: "#00d1ff", orange: "#ff8a3d", text: "#ece8f2",
    muted: "#a59fb3", dim: "#6c6679", green: "#54e39a", yellow: "#f5c76d", red: "#ff6b70"};
  const FURS = ["#f3c6a5", "#e9e1d0", "#c9a27a", "#f7b2c4", "#d8c8f0", "#b8d8a8"];

  const cab = Kit.cabinet({width: W, height: H, colours, start: startGame, update, draw, report, end: debugOver, card, key});
  const {ctx} = cab;
  const {text, glow} = cab.draw;
  const pointer = cab.input.pointer;

  const run = {score: 0, clock: 0, caught: 0, vented: 0, sold: 0, banner: null, dock: 0, dockedFor: 0, station: ""};
  let trumbles = [], crates = [], cage = [], puffs = [], hand = {x: W / 2, y: HOLD.y + HOLD.h / 2};
  const STATIONS = ["OKAFOR PORT", "VANCE RING", "LINDQVIST HUB", "HALDANE GATEWAY", "MOREAU ORBITAL"];

  const sfx = {
    purr() { cab.sound.tone("triangle", between(150, 190), between(120, 150), .25, .05); },
    pop() { cab.sound.tone("sine", 600, 900, .08, .1); },
    catch() { cab.sound.tone("square", 880, 1320, .07, .1); },
    vent() { cab.sound.hiss(.8, .6, 3000); },
    sell() { [523, 659, 784, 1047].forEach((f, i) => cab.sound.tone("triangle", f, f, .1, .14, i * .07)); },
    dock() { [392, 494, 587].forEach((f, i) => cab.sound.tone("square", f, f, .12, .1, i * .12)); },
    full() { cab.sound.tone("sawtooth", 300, 80, 1, .2); },
  };

  function key(code) {
    if (cab.state !== "play") return false;
    if (code === "KeyV") { vent(); return true; }
    if (code === "KeyS") { sell(); return true; }
    if (code === "Space" || code === "Enter") { grabAt(hand.x, hand.y); return true; }
    return false;
  }

  function startGame() {
    Object.assign(run, {score: 0, clock: 0, caught: 0, vented: 0, sold: 0, banner: null, dock: 40 * 60, dockedFor: 0, station: ""});
    trumbles = [];
    cage = [];
    puffs = [];
    crates = Array.from({length: 8}, (_, i) => ({x: HOLD.x + 50 + (i % 4) * 140, y: HOLD.y + 80 + Math.floor(i / 4) * 290, food: 100}));
    for (let i = 0; i < 2; i += 1) trumbles.push(newTrumble(HOLD.x + between(100, HOLD.w - 100), HOLD.y + between(100, HOLD.h - 100)));
    pointer.active = false;
    run.banner = {text: "A PAIR OF TRUMBLES", sub: "THEY SEEMED SO HARMLESS AT THE MARKET", t: 160};
  }

  function newTrumble(x, y) {
    return {x, y, vx: between(-.4, .4), vy: between(-.4, .4), r: 11, grow: 0, fed: between(200, 400), fur: pick(FURS), wobble: between(0, 6), blink: between(0, 300)};
  }

  function grabAt(x, y) {
    if (cage.length >= CAGE) { run.banner = {text: "THE CAGE IS FULL", sub: "V TO VENT · S TO SELL WHEN DOCKED", t: 60, small: true}; return; }
    const target = trumbles.filter((item) => Math.hypot(item.x - x, item.y - y) < item.r + 14)
      .sort((a, b) => Math.hypot(a.x - x, a.y - y) - Math.hypot(b.x - x, b.y - y))[0];
    if (!target) return;
    target.gone = true;
    cage.push(target.fur);
    run.caught += 1;
    run.score += 10;
    sfx.catch();
    puff(target.x, target.y, target.fur);
  }

  function vent() {
    if (!cage.length) return;
    const count = cage.length;
    run.score += count * 25;
    run.vented += count;
    for (const fur of cage) puff(HOLD.x - 10, HOLD.y + HOLD.h / 2 + between(-40, 40), fur, -3);
    cage = [];
    sfx.vent();
    run.banner = {text: `${count} VENTED`, sub: `+${count * 25}`, t: 70, small: true};
  }

  function sell() {
    if (!cage.length) return;
    if (run.dockedFor <= 0) { run.banner = {text: "NOT DOCKED", sub: "THE BUYER WAITS AT THE NEXT STATION", t: 60, small: true}; return; }
    const count = cage.length;
    const price = 60 + Math.floor(run.clock / 60) * 10;
    run.score += count * price;
    run.sold += count;
    cage = [];
    sfx.sell();
    run.banner = {text: `SOLD ${count} AT ${price} CR`, sub: `+${(count * price).toLocaleString()}`, t: 80, small: true, good: true};
  }

  function puff(x, y, fur, push = 0) {
    for (let i = 0; i < 12; i += 1) {
      const a = between(0, Math.PI * 2), v = between(.5, 2.2);
      puffs.push({x, y, vx: Math.cos(a) * v + push, vy: Math.sin(a) * v, life: between(20, 40), colour: fur});
    }
  }

  function finish() {
    sfx.full();
    cab.over({score: run.score, wave: Math.floor(run.clock / 60) + 1, rank: Kit.rank(run.score, .15, "trade")});
  }

  function update() {
    for (const item of puffs) { item.x += item.vx; item.y += item.vy; item.vx *= .95; item.vy *= .95; item.life -= 1; }
    puffs = puffs.filter((item) => item.life > 0);
    for (const item of trumbles) {
      item.wobble += .06;
      item.blink = (item.blink + 1) % 320;
    }
    if (cab.state !== "play") return;
    const dt = 1 / 60;
    run.clock += dt;
    if (run.banner && --run.banner.t <= 0) run.banner = null;

    // The hand: the mouse, or the arrow keys.
    const mx = (cab.input.held(...Kit.RIGHT) ? 1 : 0) - (cab.input.held(...Kit.LEFT) ? 1 : 0);
    const my = (cab.input.held("ArrowDown") ? 1 : 0) - (cab.input.held("ArrowUp", "KeyW") ? 1 : 0);
    if (mx || my) { pointer.active = false; hand.x += mx * 6; hand.y += my * 6; }
    else if (pointer.active) { hand.x = pointer.x; hand.y = pointer.y; }
    hand.x = clamp(hand.x, HOLD.x, HOLD.x + HOLD.w);
    hand.y = clamp(hand.y, HOLD.y, HOLD.y + HOLD.h);
    if (cab.input.clicked()) grabAt(pointer.x, pointer.y);

    // Docking: a buyer on the pad for a while.
    if (run.dockedFor > 0) {
      if (--run.dockedFor === 0) { run.dock = between(30, 45) * 60; run.banner = {text: "UNDOCKED", sub: "BACK INTO THE BLACK", t: 70, small: true}; }
    } else if (--run.dock <= 0) {
      run.dockedFor = 11 * 60;
      run.station = pick(STATIONS);
      sfx.dock();
      run.banner = {text: `DOCKED AT ${run.station}`, sub: "A TRUMBLE BUYER IS ON THE PAD · S TO SELL", t: 150, good: true};
    }

    // They wander, eat and breed.
    const pace = 1 + run.clock / 90;
    const born = [];
    for (const item of trumbles) {
      if (chance(.02)) { item.vx = between(-.6, .6); item.vy = between(-.6, .6); }
      const crate = crates.filter((c) => c.food > 0).sort((a, b) => Math.hypot(a.x - item.x, a.y - item.y) - Math.hypot(b.x - item.x, b.y - item.y))[0];
      if (crate && item.fed < 120) {
        const d = Math.hypot(crate.x - item.x, crate.y - item.y) || 1;
        item.vx += (crate.x - item.x) / d * .03;
        item.vy += (crate.y - item.y) / d * .03;
        if (d < 30) { crate.food -= .08; item.fed += 3; }
      }
      item.vx = clamp(item.vx, -.9, .9);
      item.vy = clamp(item.vy, -.9, .9);
      item.x = clamp(item.x + item.vx, HOLD.x + item.r, HOLD.x + HOLD.w - item.r);
      item.y = clamp(item.y + item.vy, HOLD.y + item.r, HOLD.y + HOLD.h - item.r);
      item.fed -= .25;
      item.grow += pace * (item.fed > 0 ? 1 : .25);
      if (item.grow > 520) {
        item.grow = between(0, 120);
        const baby = newTrumble(item.x + between(-10, 10), item.y + between(-10, 10));
        baby.fur = chance(.7) ? item.fur : pick(FURS);
        baby.r = 7;
        born.push(baby);
        if (chance(.3)) sfx.pop();
      }
      if (item.r < 11) item.r += .01;
    }
    trumbles = trumbles.filter((item) => !item.gone).concat(born);
    if (chance(.01 * Math.min(4, trumbles.length / 8))) sfx.purr();
    // A fresh crate turns up now and then (the ship's cargo, sadly).
    if (chance(.0015)) {
      const empty = crates.find((c) => c.food <= 0);
      if (empty) empty.food = 100;
    }
    if (trumbles.length >= FULL) return finish();
    if (!trumbles.length) {
      run.score += 500;
      for (let i = 0; i < 2 + Math.floor(run.clock / 60); i += 1) trumbles.push(newTrumble(HOLD.x + between(80, HOLD.w - 80), HOLD.y + between(80, HOLD.h - 80)));
      run.banner = {text: "HOLD CLEAR · +500", sub: "WAIT. WHERE DID THOSE COME FROM?", t: 120, good: true};
    }
  }

  // ---- Drawing. ----
  function drawTrumble(item) {
    const breathe = 1 + Math.sin(item.wobble) * .05;
    const r = item.r * breathe;
    ctx.save();
    ctx.translate(item.x, item.y);
    ctx.fillStyle = item.fur;
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.fill();
    // Fur: little strokes round the edge.
    ctx.strokeStyle = item.fur;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    for (let i = 0; i < 18; i += 1) {
      const a = i / 18 * Math.PI * 2 + item.wobble * .1;
      ctx.moveTo(Math.cos(a) * r * .8, Math.sin(a) * r * .8);
      ctx.lineTo(Math.cos(a) * (r + 3), Math.sin(a) * (r + 3));
    }
    ctx.stroke();
    ctx.fillStyle = "#1a1420";
    if (item.blink > 6) {
      ctx.beginPath(); ctx.arc(-r * .35, -r * .15, r * .14, 0, Math.PI * 2); ctx.arc(r * .35, -r * .15, r * .14, 0, Math.PI * 2); ctx.fill();
    } else {
      ctx.fillRect(-r * .5, -r * .17, r * .3, 1.2); ctx.fillRect(r * .2, -r * .17, r * .3, 1.2);
    }
    ctx.restore();
  }

  function draw() {
    ctx.fillStyle = colours.bg;
    ctx.fillRect(0, 0, W, H);
    // The hold: deck plates, the airlock on the left, the hatch on the right.
    ctx.fillStyle = "#11121a";
    ctx.fillRect(HOLD.x, HOLD.y, HOLD.w, HOLD.h);
    ctx.strokeStyle = "#1e2030";
    ctx.lineWidth = 1;
    for (let x = HOLD.x; x <= HOLD.x + HOLD.w; x += 45) { ctx.beginPath(); ctx.moveTo(x, HOLD.y); ctx.lineTo(x, HOLD.y + HOLD.h); ctx.stroke(); }
    for (let y = HOLD.y; y <= HOLD.y + HOLD.h; y += 47) { ctx.beginPath(); ctx.moveTo(HOLD.x, y); ctx.lineTo(HOLD.x + HOLD.w, y); ctx.stroke(); }
    ctx.strokeStyle = colours.dim;
    ctx.lineWidth = 2;
    ctx.strokeRect(HOLD.x, HOLD.y, HOLD.w, HOLD.h);
    ctx.fillStyle = colours.red;
    ctx.fillRect(HOLD.x - 8, HOLD.y + HOLD.h / 2 - 50, 6, 100);
    text("AIRLOCK", HOLD.x - 12, HOLD.y + HOLD.h / 2 + 66, 8, colours.red, "left");
    const docked = run.dockedFor > 0;
    ctx.fillStyle = docked ? colours.green : "#2a2a30";
    ctx.fillRect(HOLD.x + HOLD.w + 2, HOLD.y + HOLD.h / 2 - 50, 6, 100);
    text(docked ? "BUYER" : "HATCH", HOLD.x + HOLD.w + 8, HOLD.y + HOLD.h / 2 + 66, 8, docked ? colours.green : colours.dim, "right");
    for (const crate of crates) {
      ctx.fillStyle = crate.food > 0 ? "#2a2416" : "#18181c";
      ctx.fillRect(crate.x - 22, crate.y - 16, 44, 32);
      ctx.strokeStyle = crate.food > 0 ? colours.yellow : colours.dim;
      ctx.strokeRect(crate.x - 22, crate.y - 16, 44, 32);
      text(crate.food > 0 ? "FOOD" : "EMPTY", crate.x, crate.y + 3, 8, crate.food > 0 ? colours.yellow : colours.dim);
      if (crate.food > 0) cab.draw.bar(crate.x - 18, crate.y + 8, 36, 3, crate.food / 100, colours.yellow);
    }
    trumbles.forEach(drawTrumble);
    for (const item of puffs) {
      ctx.globalAlpha = clamp(item.life / 25, 0, 1);
      ctx.fillStyle = item.colour;
      ctx.fillRect(item.x - 1.5, item.y - 1.5, 3, 3);
    }
    ctx.globalAlpha = 1;
    if (cab.state === "play") {
      ctx.strokeStyle = cage.length >= CAGE ? colours.red : colours.accent;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(hand.x, hand.y, 16, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath(); ctx.moveTo(hand.x - 6, hand.y); ctx.lineTo(hand.x + 6, hand.y); ctx.moveTo(hand.x, hand.y - 6); ctx.lineTo(hand.x, hand.y + 6); ctx.stroke();
    }

    cab.scoreBar(run.score, "", 0);
    if (cab.state !== "title") {
      const minutes = Math.floor(run.clock / 60), seconds = Math.floor(run.clock % 60);
      text(`${minutes}:${String(seconds).padStart(2, "0")}`, W - 18, 42, 18, colours.text, "right");
      text("TIME", W - 18, 22, 10, colours.dim, "right");
      const y = HOLD.y + HOLD.h + 26;
      text(`HOLD ${trumbles.length}/${FULL} TRUMBLES`, 30, y, 11, trumbles.length > FULL * .75 ? colours.red : colours.text, "left");
      cab.draw.bar(30, y + 8, 220, 8, trumbles.length / FULL, trumbles.length > FULL * .75 ? colours.red : colours.orange);
      text("CAGE", W - 30, y, 11, colours.muted, "right");
      for (let i = 0; i < CAGE; i += 1) {
        ctx.beginPath();
        ctx.arc(W - 40 - i * 22, y + 16, 8, 0, Math.PI * 2);
        ctx.fillStyle = cage[CAGE - 1 - i] ? cage[CAGE - 1 - i] : "#1c1c24";
        ctx.fill();
      }
      text(docked ? `DOCKED AT ${run.station} · S SELLS · V VENTS` : "CLICK TO CATCH · V VENTS · S SELLS WHEN DOCKED", W / 2, y + 48, 10, docked ? colours.green : colours.dim);
      if (docked) cab.draw.bar(W / 2 - 100, y + 56, 200, 3, run.dockedFor / (11 * 60), colours.green);
    }
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 6, 8, colours.dim);
    const banner = run.banner;
    if (banner && cab.state === "play") {
      ctx.globalAlpha = clamp(banner.t / 30, 0, 1);
      text(banner.text, W / 2, HOLD.y - 26, banner.small ? 16 : 22, banner.good ? colours.green : colours.text, "center", 700, Kit.DISPLAY);
      if (banner.sub) text(banner.sub, W / 2, HOLD.y - 8, 10, colours.accent);
      ctx.globalAlpha = 1;
    }
    if (cab.state === "title") {
      cab.titleScreen({top: "TRUMBLE", bottom: "TROUBLE", tone: "#f7b2c4", y: 160,
        rows: [["CATCH ONE", "10"], ["VENT IT", "25"], ["SELL IT WHEN DOCKED", "60 AND RISING"], ["CLEAR THE HOLD", "500"]],
        note: "THEY BREED FASTER THE MORE FOOD THEY FIND",
        how: "CLICK OR SPACE TO CATCH · V VENT · S SELL · ARROWS MOVE THE HAND"});
    } else if (cab.state === "over") {
      cab.overScreen({heading: "THE HOLD IS FULL OF FUR", tone: "#f7b2c4", sub: "THE SHIP IS NOW MOSTLY TRUMBLES", rankLabel: "TRADE RANK", rank: Kit.rank(run.score, .15, "trade"),
        lines: [["SCORE", run.score.toLocaleString()], ["HELD OUT FOR", `${Math.floor(run.clock / 60)}:${String(Math.floor(run.clock % 60)).padStart(2, "0")}`],
          ["CAUGHT", run.caught], ["VENTED", run.vented], ["SOLD", run.sold]]});
    }
  }

  function report() {
    return {score: run.score, trumbles: trumbles.length, cage: cage.length, docked: run.dockedFor > 0, clock: run.clock};
  }

  function debugOver() {
    run.score += 1234;
    while (trumbles.length < FULL) trumbles.push(newTrumble(HOLD.x + between(20, HOLD.w - 20), HOLD.y + between(20, HOLD.h - 20)));
  }

  function card() {
    startGame();
    for (let i = 0; i < 26; i += 1) trumbles.push(newTrumble(HOLD.x + between(30, HOLD.w - 30), HOLD.y + between(30, HOLD.h - 30)));
    for (const item of trumbles) item.r = between(8, 12);
    cage = [FURS[0], FURS[3], FURS[4]];
    run.score = 1840;
    run.clock = 134;
    run.dockedFor = 7 * 60;
    run.station = "OKAFOR PORT";
    crates[1].food = 0;
    crates[6].food = 30;
    hand = {x: 330, y: 300};
    run.banner = null;
  }

  window.trumbleTrouble = {state: () => ({...report(), state: cab.state})};
})();
