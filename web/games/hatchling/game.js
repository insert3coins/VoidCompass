// Hatchling (5.6.3): the pocket pet's own screen. The pet lives in the deck
// (core/hatchling.py), in real time; this page only shows it and asks for
// things: feed it, play with it, vent the hold, give it medicine, lights,
// a pat. What it is, the deck sends as "live"; what we do goes back as
// "action". Everything you see happen here is the page's own show.
(() => {
  "use strict";

  const W = 600, H = 675;
  const {clamp, between, pick, lerp} = Kit;
  const colours = {bg: "#03060a", panel: "#0b1513", border: "#1f3a33", accent: "#4ee5b0", orange: "#ff8a3d", text: "#e6f4f0",
    muted: "#91a8b7", dim: "#5d736d", green: "#54e39a", yellow: "#f5c76d", red: "#ff6b70"};
  const SPECIES = ["larva", "bot", "sample"];
  const KINDS = ["bacterium", "tubus", "fungoida"];
  const NAMES = {larva: "THARGOID LARVA", bot: "REMLOK BOT", sample: "EXOBIOLOGY SAMPLE"};
  const HUE = {larva: "#4ee5b0", bot: "#ffb35c", sample: "#c7f06a"};
  const NEEDS = [["hunger", null], ["mood", "MOOD"], ["clean", "CLEAN"], ["health", "HEALTH"], ["energy", "SLEEP"]];
  const STAGE_ENDS = {egg: [0, .5, "HATCHLING"], hatchling: [.5, 24, "JUVENILE"], juvenile: [24, 72, "ADULT"]};
  const POD = {x: 300, y: 232, rx: 262, ry: 150};
  const FLOOR = 318;
  const PET = {x: 300, y: 262, size: 196};
  // The minigames play inside the pod.
  const HABITAT = {x: 70, y: 106, w: 460, h: 236};

  const cab = Kit.cabinet({width: W, height: H, colours, state0: "play", pausable: false, start() {}, update, draw,
    onLive, key, card, report, onLevels: (data) => life.hear(data.bands, data.playing)});
  const {ctx} = cab;
  const {text, glow} = cab.draw;
  const pointer = cab.input.pointer;

  let view = null;
  let screen = "choose";
  let pending = 0;
  let buttons = [];
  let notice = {text: "", until: 0, seen: 0};
  const choice = {species: "larva", kind: "bacterium", name: "", suggest: 0};
  let mini = null;
  let fx = [], floaters = [], flying = [];
  const body = {dark: 0, petCool: 0};
  const seen = {x: 0, y: 0, at: -999};
  // What it gets up to on its own, shared with the overlay.
  const life = HatchlingLife.create({size: PET.size, range: 115, top: PET.y - (POD.y - POD.ry) - 4, onSound: (kind, words) => voice(kind, words)});
  let snapFlash = 0;
  let welcomed = 0;
  let resetAsked = -999;
  let lastStage = "", hatchFx = 0, nebula = null, nebulaFor = "";
  const stars = [0, 1, 2].map((layer) => Array.from({length: 60 - layer * 15}, () => ({x: between(0, W), y: between(0, H), s: .4 + layer * .5, a: between(.3, 1)})));
  let shooting = null;

  const pet = () => view?.pet || null;
  const now = () => Date.now() / 1000;
  const hue = () => HUE[pet()?.species || choice.species];
  const sfx = {
    blip() { cab.sound.tone("square", 880, 660, .05, .1); },
    yum() { [523, 659, 784].forEach((f, i) => cab.sound.tone("triangle", f, f * 1.02, .09, .16, i * .07)); },
    purr() { for (let i = 0; i < 4; i += 1) cab.sound.tone("triangle", 140 + (i % 2) * 18, 130, .12, .12, i * .1); },
    whoosh() { cab.sound.hiss(.7, .5, 3200); },
    chime() { [784, 988, 1175, 1568].forEach((f, i) => cab.sound.tone("sine", f, f, .3, .1, i * .09)); },
    win() { [523, 659, 784, 1047].forEach((f, i) => cab.sound.tone("square", f, f, .1, .12, i * .08)); },
    lose() { cab.sound.tone("sawtooth", 330, 140, .4, .12); },
    hatch() { cab.sound.hiss(.4, .5, 4000); [392, 523, 659, 784, 1047, 1319].forEach((f, i) => cab.sound.tone("triangle", f, f, .22, .16, .2 + i * .09)); },
  };

  // Its own little noises, pitched by what it is: a larva hums, a bot beeps, a sample whispers.
  function voice(kind, words = "") {
    const species = pet()?.species || "larva";
    const wave = species === "bot" ? "square" : species === "sample" ? "sine" : "triangle";
    const base = species === "bot" ? 880 : species === "sample" ? 420 : 560;
    const tone = (from, to, length, volume = .07, delay = 0) => cab.sound.tone(wave, base * from, base * to, length, volume, delay);
    ({
      chirp() { tone(1, 1.3, .06); tone(1.2, 1.5, .06, .07, .08); },
      cheer() { [1, 1.25, 1.5, 2].forEach((step, i) => tone(step, step, .08, .07, i * .07)); },
      boing() { tone(.5, 1, .08, .05); },
      crash() { cab.sound.hiss(.25, .35, 1800); tone(.3, .2, .25, .06); },
      eek() { tone(2, 2.6, .09, .06); },
      grumble() { cab.sound.tone("sawtooth", 150, 110, .3, .05); },
      sneeze() { tone(1.4, 1.6, .05, .05); cab.sound.hiss(.2, .3, 3000); },
      snore() { cab.sound.tone("triangle", 95, 70, .6, .04); },
      yawn() { tone(.9, .5, .55, .05); },
      hum() { cab.sound.tone("triangle", 200, 210, .8, .04); },
      beep() { tone(1.4, 1.4, .04, .05); tone(1.7, 1.7, .04, .05, .07); },
      babble() {
        const syllables = Math.min(9, Math.max(2, Math.round(words.replace(/[^a-z]/gi, "").length / 3)));
        for (let i = 0; i < syllables; i += 1) { const pitch = 1 + Math.random() * .5; tone(pitch, pitch * 1.06, .05, .045, i * .085); }
      },
    })[kind]?.();
  }

  // SNAP: the pod, sent to the deck to become a postcard.
  function snap() {
    const [sx, sy, sw, sh] = [POD.x - POD.rx - 8, POD.y - POD.ry - 8, POD.rx * 2 + 16, POD.ry * 2 + 16];
    const out = document.createElement("canvas");
    out.width = sw * 2;
    out.height = sh * 2;
    out.getContext("2d").drawImage(cab.canvas, sx * cab.scale, sy * cab.scale, sw * cab.scale, sh * cab.scale, 0, 0, out.width, out.height);
    cab.tell("snap", {png: out.toDataURL("image/png").split(",")[1] || ""});
    snapFlash = 18;
    cab.sound.tone("square", 1800, 1800, .03, .08);
    cab.sound.hiss(.12, .25, 5000);
  }

  function ask(action, value = {}) {
    if (action !== "pet") pending = cab.tick;
    cab.tell("action", {action, value});
  }

  function onLive(live) {
    view = live;
    pending = 0;
    const p = pet();
    const was = screen;
    if (!p) screen = "choose";
    else if (screen === "choose") screen = "home";
    if (p?.dormant && screen !== "home") screen = "home";
    // The last screen's buttons are gone with it (a click can come before the next draw).
    if (screen !== was) buttons = [];
    // The moment it hatches.
    if (p && lastStage === "egg" && p.stage !== "egg") startHatch();
    if (p && !lastStage && p.stage === "egg" && cab.tick > 30) burst(PET.x, PET.y, hue(), 40, 4);
    lastStage = p?.stage || "";
    const fresh = live?.notice;
    if (fresh?.text && fresh.at > notice.seen) notice = {text: fresh.text, until: cab.tick + 300, seen: fresh.at};
  }

  function startHatch() {
    hatchFx = 170;
    sfx.hatch();
    for (let i = 0; i < 26; i += 1) {
      const a = between(0, Math.PI * 2), v = between(2, 6);
      fx.push({kind: "shell", x: PET.x, y: PET.y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 2, spin: between(-.3, .3), angle: 0, life: 90, size: between(4, 9)});
    }
    burst(PET.x, PET.y, "#ffffff", 50, 6);
  }

  // ---- Keys: numbers for the buttons, letters for a name. ----
  function key(code, event) {
    if (screen === "choose" && event) {
      if (code === "Backspace") { choice.name = choice.name.slice(0, -1); return true; }
      if (event.key && event.key.length === 1 && /[\w '\-.]/.test(event.key) && choice.name.length < 16) {
        choice.name += event.key;
        return true;
      }
      if (code === "Enter") { hatch(); return true; }
      if (code === "ArrowLeft" || code === "ArrowRight") {
        const index = SPECIES.indexOf(choice.species) + (code === "ArrowLeft" ? -1 : 1);
        choice.species = SPECIES[(index + SPECIES.length) % SPECIES.length];
        sfx.blip();
        return true;
      }
    }
    if (code === "Escape" || code === "Backspace") {
      if (["feed", "games"].includes(screen)) { screen = "home"; return true; }
      if (mini) { mini = null; return true; }
      return true;
    }
    const digit = /^Digit([1-9])$/.exec(code);
    if (digit) {
      const button = buttons.find((item) => item.key === digit[1]);
      if (button && !button.off) { sfx.blip(); button.act(); }
      return true;
    }
    return false;
  }

  function hatch() {
    const names = view?.species?.[choice.species]?.names || ["Pip"];
    const name = choice.name.trim() || names[choice.suggest % names.length];
    ask("hatch", {species: choice.species, name, kind: choice.species === "sample" ? choice.kind : ""});
  }

  // ---- The show: particles, words that float up, things that fly to it. ----
  function burst(x, y, colour, count = 20, speed = 3) {
    for (let i = 0; i < count; i += 1) {
      const a = between(0, Math.PI * 2), v = between(.5, speed);
      fx.push({kind: "spark", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: between(25, 55), colour, size: between(1.5, 3.5)});
    }
  }

  function float(words, colour, x = PET.x, y = PET.y - 90) {
    floaters.push({text: words, colour, x: x + between(-20, 20), y, life: 80});
  }

  function hearts(count = 5) {
    for (let i = 0; i < count; i += 1) fx.push({kind: "heart", x: PET.x + between(-50, 50), y: PET.y - between(30, 70), vx: between(-.4, .4), vy: between(-1.6, -.8), life: between(50, 80), size: between(6, 10)});
  }

  function rings(colour) {
    for (let i = 0; i < 3; i += 1) fx.push({kind: "ring", x: PET.x, y: PET.y, r: 10 + i * 18, life: 60 + i * 8, colour});
  }

  function sendFood(item, from) {
    flying.push({item, x: from.x, y: from.y, sx: from.x, sy: from.y, t: 0});
  }

  function hop(height = 22) {
    life.hop(height);
  }

  // ---- One step. ----
  function update() {
    const p = pet();
    if (cab.input.clicked()) {
      const hit = buttons.find((button) => !button.off && pointer.x >= button.x && pointer.x <= button.x + button.w
        && pointer.y >= button.y && pointer.y <= button.y + button.h);
      if (hit) { sfx.blip(); hit.act(); }
      else if (mini) mini.click(pointer.x, pointer.y);
      else if (p && screen === "home" && Math.hypot(pointer.x - PET.x - life.x, pointer.y - (PET.y - life.lift)) < 80) pat(p);
    }
    if (mini) mini.step();
    if (pending && cab.tick - pending > 240) pending = 0;
    if (body.petCool > 0) body.petCool -= 1;

    // Its life on its own, with eyes that follow you while you're about.
    life.step(1 / 60, p, {busy: Boolean(mini) || screen !== "home" || Boolean(flying.length)});
    if (pointer.x !== seen.x || pointer.y !== seen.y) Object.assign(seen, {x: pointer.x, y: pointer.y, at: cab.tick});
    if (pointer.active && pointer.y < FLOOR + 40 && cab.tick - seen.at < 90) {
      life.lookAt([clamp((pointer.x - PET.x - life.x) / 180, -1, 1), clamp((pointer.y - PET.y) / 180, -1, 1)]);
    }
    body.dark = lerp(body.dark, p?.asleep && !p.dormant ? 1 : 0, .04);

    for (const item of flying) {
      item.t += 1 / 36;
      const k = clamp(item.t, 0, 1);
      item.x = lerp(item.sx, PET.x + life.x, k);
      item.y = lerp(item.sy, PET.y - 20, k) - Math.sin(k * Math.PI) * 120;
      if (item.t >= 1) {
        item.done = true;
        life.kick(.6);
        sfx.yum();
        burst(PET.x, PET.y - 10, "#ffd8a0", 14, 2.5);
      }
    }
    flying = flying.filter((item) => !item.done);
    for (const item of fx) {
      item.life -= 1;
      if (item.kind === "ring") { item.r += 2.2; continue; }
      item.x += item.vx;
      item.y += item.vy;
      if (item.kind === "shell") { item.vy += .12; item.angle += item.spin; }
      else if (item.kind === "spark") { item.vx *= .95; item.vy *= .95; }
      else if (item.kind === "wind") { item.vx *= 1.04; item.y += Math.sin(item.life * .2) * .8; }
    }
    fx = fx.filter((item) => item.life > 0);
    for (const item of floaters) { item.y -= .7; item.life -= 1; }
    floaters = floaters.filter((item) => item.life > 0);
    if (hatchFx > 0) hatchFx -= 1;
    if (snapFlash > 0) snapFlash -= 1;
    for (const layer of stars) for (const star of layer) { star.x -= star.s * .12; if (star.x < 0) star.x += W; }
    if (!shooting && Math.random() < .002) shooting = {x: between(100, W), y: between(0, 160), life: 40};
    if (shooting && --shooting.life <= 0) shooting = null;
    // The species' own motes drift in the pod.
    if (p && !p.dormant && Math.random() < .25) {
      const kind = p.species === "bot" ? "ember" : p.species === "sample" ? "spore" : "mote";
      fx.push({kind, x: POD.x + between(-200, 200), y: FLOOR + between(-10, 10), vx: between(-.2, .2), vy: between(-.9, -.3), life: between(90, 160), size: between(1, 2.6)});
    }
  }

  function pat(p) {
    if (p.stage === "egg" || p.dormant) { life.kick(.3); return; }
    if (p.asleep) { float("SHH… ASLEEP", colours.muted); return; }
    life.kick(.9);
    hearts(6);
    sfx.purr();
    if (body.petCool <= 0) { body.petCool = 90 * 60; ask("pet"); }
  }

  // ---- The minigames: a short play, then the result goes to the deck. ----
  function finish(game, won) {
    (won ? sfx.win : sfx.lose)();
    mini.done = {won, at: cab.tick};
    if (won) { hearts(8); burst(PET.x, PET.y - 30, colours.yellow, 40, 5); }
    ask("play", {game, won});
  }

  function limpetGame() {
    const box = HABITAT;
    const limpet = {x: box.x + box.w / 2, y: box.y + box.h / 2, vx: 2.4, vy: 1.6, caught: 0, flash: 0, trail: []};
    return {
      name: "CATCH THE LIMPET", left: 12 * 60, limpet,
      step() {
        if (this.done) { if (cab.tick - this.done.at > 110) mini = null; return; }
        this.left -= 1;
        const speed = 1 + limpet.caught * .45;
        limpet.x += limpet.vx * speed;
        limpet.y += limpet.vy * speed;
        if (limpet.x < box.x + 20 || limpet.x > box.x + box.w - 20) limpet.vx *= -1;
        if (limpet.y < box.y + 20 || limpet.y > box.y + box.h - 20) limpet.vy *= -1;
        if (Math.random() < .02) { limpet.vx += between(-1, 1); limpet.vy += between(-1, 1); }
        const length = Math.hypot(limpet.vx, limpet.vy) || 1;
        limpet.vx = limpet.vx / length * 2.8;
        limpet.vy = limpet.vy / length * 2.8;
        limpet.trail = [[limpet.x, limpet.y], ...limpet.trail].slice(0, 12);
        if (limpet.flash > 0) limpet.flash -= 1;
        life.lookAt([clamp((limpet.x - HABITAT.x - 64) / 180, -1, 1), clamp((limpet.y - FLOOR + 40) / 180, -1, 1)]);
        if (this.left <= 0) finish("limpet", false);
      },
      click(x, y) {
        if (this.done) return;
        if (Math.hypot(x - limpet.x, y - limpet.y) < 28) {
          limpet.caught += 1;
          limpet.flash = 12;
          sfx.yum();
          burst(limpet.x, limpet.y, colours.orange, 20, 3);
          float(`${limpet.caught} / 3`, colours.orange, limpet.x, limpet.y - 20);
          limpet.x = between(box.x + 40, box.x + box.w - 40);
          limpet.y = between(box.y + 40, box.y + box.h - 40);
          hop(16);
          if (limpet.caught >= 3) finish("limpet", true);
        }
      },
      draw() {
        limpet.trail.forEach(([x, y], index) => {
          ctx.globalAlpha = (1 - index / 12) * .5;
          ctx.fillStyle = colours.orange;
          ctx.beginPath(); ctx.arc(x, y, 5 - index * .3, 0, Math.PI * 2); ctx.fill();
        });
        ctx.globalAlpha = 1;
        ctx.save();
        ctx.translate(limpet.x, limpet.y);
        ctx.rotate(cab.tick * .1);
        ctx.strokeStyle = limpet.flash ? "#ffffff" : colours.orange;
        ctx.lineWidth = 2.4;
        ctx.shadowColor = colours.orange;
        ctx.shadowBlur = 14;
        ctx.beginPath();
        for (let i = 0; i < 4; i += 1) {
          const a = i * Math.PI / 2;
          ctx.moveTo(Math.cos(a) * 7, Math.sin(a) * 7);
          ctx.lineTo(Math.cos(a) * 17, Math.sin(a) * 17);
        }
        ctx.stroke();
        ctx.beginPath(); ctx.arc(0, 0, 8, 0, Math.PI * 2);
        ctx.fillStyle = "#3a2410"; ctx.fill(); ctx.stroke();
        ctx.restore();
        ctx.shadowBlur = 0;
        text(`CAUGHT ${limpet.caught} / 3`, box.x + 14, box.y + 22, 13, colours.text, "left");
        text(`${Math.ceil(this.left / 60)} S`, box.x + box.w - 14, box.y + 22, 13, colours.yellow, "right");
      },
    };
  }

  function thargonGame() {
    const box = HABITAT;
    const spots = [box.x + box.w * .2, box.x + box.w * .5, box.x + box.w * .8];
    const rocks = [0, 1, 2].map((slot) => ({slot, x: spots[slot]}));
    const hidden = rocks[Math.floor(Math.random() * 3)];
    const y = box.y + box.h * .45;
    return {
      name: "WHERE DID THE THARGON GO?", phase: "show", t: 0, swaps: 0, swap: null, picked: null,
      step() {
        if (this.done) { if (cab.tick - this.done.at > 120) mini = null; return; }
        this.t += 1;
        if (this.phase === "show" && this.t > 80) { this.phase = "shuffle"; this.t = 0; sfx.whoosh(); }
        if (this.phase === "shuffle") {
          if (!this.swap) {
            const a = Math.floor(Math.random() * 3);
            const b = (a + 1 + Math.floor(Math.random() * 2)) % 3;
            this.swap = {a: rocks.find((rock) => rock.slot === a), b: rocks.find((rock) => rock.slot === b), t: 0, length: Math.max(14, 30 - this.swaps * 2)};
          }
          const swap = this.swap;
          swap.t += 1;
          const k = clamp(swap.t / swap.length, 0, 1);
          swap.a.x = lerp(spots[swap.a.slot], spots[swap.b.slot], k);
          swap.b.x = lerp(spots[swap.b.slot], spots[swap.a.slot], k);
          swap.lift = Math.sin(k * Math.PI);
          if (k >= 1) {
            [swap.a.slot, swap.b.slot] = [swap.b.slot, swap.a.slot];
            this.swap = null;
            this.swaps += 1;
            if (this.swaps >= 7) this.phase = "pick";
          }
        }
      },
      click(x) {
        if (this.phase !== "pick" || this.done) return;
        const rock = rocks.reduce((best, item) => (Math.abs(item.x - x) < Math.abs(best.x - x) ? item : best));
        if (Math.abs(rock.x - x) > 70) return;
        this.picked = rock;
        this.phase = "reveal";
        finish("thargon", rock === hidden);
      },
      draw() {
        const lift = this.phase === "show" ? Math.max(0, 40 - this.t) * 1.4 + (this.t < 30 ? 50 : 0) : this.phase === "reveal" ? 56 : 0;
        for (const rock of rocks) {
          const up = rock === hidden || rock === this.picked ? lift : 0;
          const hop = this.swap && (rock === this.swap.a || rock === this.swap.b) ? this.swap.lift * (rock === this.swap.a ? 26 : -10) : 0;
          if (rock === hidden && up > 6) {
            ctx.save();
            ctx.translate(rock.x, y + 10);
            ctx.strokeStyle = colours.accent; ctx.lineWidth = 2; ctx.shadowColor = colours.accent; ctx.shadowBlur = 14;
            ctx.beginPath();
            for (let i = 0; i < 6; i += 1) ctx.lineTo(Math.sin(i / 6 * Math.PI * 2) * 14, Math.cos(i / 6 * Math.PI * 2) * 12);
            ctx.closePath(); ctx.stroke();
            ctx.beginPath(); ctx.arc(0, 0, 4, 0, Math.PI * 2); ctx.fillStyle = "#9dffd2"; ctx.fill();
            ctx.restore(); ctx.shadowBlur = 0;
          }
          ctx.save();
          ctx.translate(rock.x, y - up - hop);
          ctx.beginPath();
          for (let i = 0; i < 10; i += 1) {
            const a = i / 10 * Math.PI * 2, r = 40 + Math.sin(i * 2.3 + rock.slot) * 7;
            ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r * .78);
          }
          ctx.closePath();
          const stone = ctx.createRadialGradient(-12, -14, 4, 0, 0, 46);
          stone.addColorStop(0, "#6a5a4a"); stone.addColorStop(1, "#1a1410");
          ctx.fillStyle = stone; ctx.fill();
          ctx.strokeStyle = "rgba(255,220,180,.35)"; ctx.lineWidth = 1.4; ctx.stroke();
          ctx.restore();
        }
        const words = {show: "WATCH THE THARGON", shuffle: "KEEP YOUR EYE ON IT", pick: "WHICH ROCK? CLICK IT", reveal: ""}[this.phase];
        text(words, POD.x, box.y + 22, 15, colours.text);
      },
    };
  }

  // ---- Drawing. ----
  function makeNebula(species) {
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const n = canvas.getContext("2d");
    n.fillStyle = "#020408";
    n.fillRect(0, 0, W, H);
    const tint = {larva: ["#0a4a3a", "#1a2a6a", "#0a3050"], bot: ["#4a2a0a", "#2a1a4a", "#3a1010"], sample: ["#2a4a0a", "#0a3a3a", "#3a2a5a"]}[species];
    for (let i = 0; i < 9; i += 1) {
      const x = between(-50, W + 50), y = between(-50, H * .7), r = between(120, 300);
      const cloud = n.createRadialGradient(x, y, 0, x, y, r);
      cloud.addColorStop(0, `${pick(tint)}cc`);
      cloud.addColorStop(1, "rgba(0,0,0,0)");
      n.globalCompositeOperation = "lighter";
      n.fillStyle = cloud;
      n.fillRect(0, 0, W, H);
    }
    n.globalCompositeOperation = "source-over";
    // A planet far off, lit from one side.
    const px = W * .95, py = 330, pr = 80;
    const planet = n.createRadialGradient(px - pr * .5, py - pr * .4, pr * .1, px, py, pr);
    planet.addColorStop(0, "#5a6a8a"); planet.addColorStop(.6, "#1a2236"); planet.addColorStop(1, "#05070c");
    n.fillStyle = planet;
    n.beginPath(); n.arc(px, py, pr, 0, Math.PI * 2); n.fill();
    n.strokeStyle = "rgba(160, 200, 255, .35)"; n.lineWidth = 2;
    n.beginPath(); n.arc(px, py, pr, Math.PI * .8, Math.PI * 1.5); n.stroke();
    return canvas;
  }

  function drawSpace() {
    const species = pet()?.species || choice.species;
    if (nebulaFor !== species) { nebula = makeNebula(species); nebulaFor = species; }
    ctx.drawImage(nebula, 0, 0, W, H);
    stars.forEach((layer, index) => {
      ctx.fillStyle = "#ffffff";
      for (const star of layer) {
        ctx.globalAlpha = star.a * (.4 + index * .25) * (.8 + Math.sin(cab.tick * .05 + star.x) * .2);
        ctx.fillRect(star.x, star.y, star.s + .6, star.s + .6);
      }
    });
    ctx.globalAlpha = 1;
    if (shooting) {
      const k = 1 - shooting.life / 40;
      const x = shooting.x - k * 160, y = shooting.y + k * 60;
      const trail = ctx.createLinearGradient(x, y, x + 50, y - 18);
      trail.addColorStop(0, "rgba(255,255,255,.9)"); trail.addColorStop(1, "rgba(255,255,255,0)");
      ctx.strokeStyle = trail; ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 50, y - 18); ctx.stroke();
    }
  }

  function podPath() {
    ctx.beginPath();
    ctx.ellipse(POD.x, POD.y, POD.rx, POD.ry, 0, 0, Math.PI * 2);
  }

  function drawPod(p) {
    const tint = hue();
    const mood = p ? (p.needs?.mood ?? 60) / 100 : .6;
    ctx.save();
    podPath();
    ctx.clip();
    // Glass, darker at the edges.
    const glass = ctx.createRadialGradient(POD.x, POD.y - 40, 20, POD.x, POD.y, POD.rx);
    glass.addColorStop(0, "rgba(20, 40, 50, .35)");
    glass.addColorStop(1, "rgba(0, 0, 0, .75)");
    ctx.fillStyle = glass;
    ctx.fillRect(0, 0, W, H);
    // A beam of light from above, the colour of its mood.
    const beam = ctx.createLinearGradient(0, POD.y - POD.ry, 0, FLOOR + 20);
    beam.addColorStop(0, `${tint}${Math.round(40 + mood * 60).toString(16)}`);
    beam.addColorStop(1, `${tint}00`);
    ctx.fillStyle = beam;
    ctx.beginPath();
    ctx.moveTo(POD.x - 50, POD.y - POD.ry);
    ctx.lineTo(POD.x + 50, POD.y - POD.ry);
    ctx.lineTo(POD.x + 170, FLOOR + 30);
    ctx.lineTo(POD.x - 170, FLOOR + 30);
    ctx.closePath();
    ctx.fill();
    // The holo floor: a disc, its grid and a turning ring.
    ctx.save();
    ctx.translate(POD.x, FLOOR);
    ctx.scale(1, .18);
    const floor = ctx.createRadialGradient(0, 0, 10, 0, 0, 190);
    floor.addColorStop(0, `${tint}55`); floor.addColorStop(1, `${tint}00`);
    ctx.fillStyle = floor;
    ctx.beginPath(); ctx.arc(0, 0, 190, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = `${tint}55`; ctx.lineWidth = 2;
    for (const r of [60, 110, 160]) { ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.stroke(); }
    ctx.setLineDash([18, 14]);
    ctx.lineDashOffset = -cab.tick * .8;
    ctx.strokeStyle = `${tint}aa`; ctx.lineWidth = 4;
    ctx.beginPath(); ctx.arc(0, 0, 135, 0, Math.PI * 2); ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();
    // Motes drifting up through it.
    for (const item of fx) {
      if (!["mote", "ember", "spore"].includes(item.kind)) continue;
      ctx.globalAlpha = clamp(item.life / 60, 0, 1) * .8;
      ctx.fillStyle = item.kind === "ember" ? "#ffb35c" : item.kind === "spore" ? "#e2ff9a" : "#9dffd2";
      ctx.beginPath(); ctx.arc(item.x, item.y, item.size, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  function drawPodGlass() {
    // Lights out: the pod goes dark and blue.
    if (body.dark > .02) {
      ctx.save();
      podPath();
      ctx.clip();
      ctx.fillStyle = `rgba(2, 6, 20, ${body.dark * .62})`;
      ctx.fillRect(0, 0, W, H);
      ctx.restore();
    }
    // The rim and a shine across the glass.
    podPath();
    const rim = ctx.createLinearGradient(0, POD.y - POD.ry, 0, POD.y + POD.ry);
    rim.addColorStop(0, "rgba(220, 255, 250, .55)");
    rim.addColorStop(.5, `${hue()}55`);
    rim.addColorStop(1, "rgba(220, 255, 250, .25)");
    ctx.strokeStyle = rim;
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.save();
    podPath();
    ctx.clip();
    ctx.strokeStyle = "rgba(255,255,255,.12)";
    ctx.lineWidth = 18;
    ctx.beginPath(); ctx.ellipse(POD.x - 40, POD.y - 20, POD.rx - 30, POD.ry - 24, 0, Math.PI * 1.05, Math.PI * 1.45); ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,.07)";
    ctx.lineWidth = 6;
    ctx.beginPath(); ctx.ellipse(POD.x + 30, POD.y + 10, POD.rx - 26, POD.ry - 20, 0, Math.PI * 1.6, Math.PI * 1.8); ctx.stroke();
    ctx.restore();
    // Clamps where the pod meets the ship.
    for (const side of [-1, 1]) {
      ctx.fillStyle = "#0c1418";
      ctx.strokeStyle = `${hue()}88`;
      ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.roundRect(POD.x + side * POD.rx - (side > 0 ? 12 : 0), POD.y - 24, 12, 48, 3); ctx.fill(); ctx.stroke();
      ctx.fillStyle = Math.floor(cab.tick / 40) % 2 ? hue() : "#203030";
      ctx.fillRect(POD.x + side * (POD.rx - 6) - 2, POD.y - 4, 4, 8);
    }
  }

  function drawFx() {
    for (const item of fx) {
      const alpha = clamp(item.life / 30, 0, 1);
      if (item.kind === "spark") {
        ctx.globalAlpha = alpha;
        ctx.fillStyle = item.colour;
        ctx.beginPath(); ctx.arc(item.x, item.y, item.size, 0, Math.PI * 2); ctx.fill();
      } else if (item.kind === "heart") {
        ctx.globalAlpha = alpha;
        window.HatchlingArt.heart(ctx, item.x, item.y, item.size, "#ff6f9a");
      } else if (item.kind === "ring") {
        ctx.globalAlpha = alpha * .8;
        ctx.strokeStyle = item.colour;
        ctx.lineWidth = 3;
        ctx.beginPath(); ctx.ellipse(item.x, item.y, item.r, item.r * .7, 0, 0, Math.PI * 2); ctx.stroke();
      } else if (item.kind === "shell") {
        ctx.globalAlpha = alpha;
        ctx.save();
        ctx.translate(item.x, item.y);
        ctx.rotate(item.angle);
        ctx.fillStyle = mixShell();
        ctx.beginPath(); ctx.moveTo(-item.size, -item.size * .4); ctx.lineTo(item.size * .8, -item.size * .7); ctx.lineTo(item.size * .4, item.size * .6); ctx.closePath(); ctx.fill();
        ctx.restore();
      } else if (item.kind === "wind") {
        ctx.globalAlpha = alpha * .6;
        ctx.strokeStyle = "#cfeaff";
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(item.x, item.y); ctx.quadraticCurveTo(item.x + 20, item.y - 6, item.x + 40, item.y); ctx.stroke();
      } else if (item.kind === "cross") {
        ctx.globalAlpha = alpha;
        ctx.fillStyle = "#7dff9a";
        ctx.fillRect(item.x - 2, item.y - 6, 4, 12);
        ctx.fillRect(item.x - 6, item.y - 2, 12, 4);
      }
    }
    ctx.globalAlpha = 1;
    for (const item of flying) {
      ctx.save();
      ctx.translate(item.x, item.y);
      ctx.rotate(item.t * 8);
      icon(foodIcon(item.item), 0, 0, 16, colours.yellow);
      ctx.restore();
    }
    for (const item of floaters) {
      ctx.globalAlpha = clamp(item.life / 30, 0, 1);
      glow(item.colour, 10);
      text(item.text, item.x, item.y, 14, item.colour, "center", 700, Kit.DISPLAY);
      ctx.shadowBlur = 0;
    }
    ctx.globalAlpha = 1;
  }

  function mixShell() {
    return {larva: "#9dffd2", bot: "#e9edf2", sample: "#e2ff9a"}[pet()?.species || "larva"];
  }

  function drawHatchFx() {
    if (hatchFx <= 0) return;
    const k = hatchFx / 170;
    ctx.save();
    ctx.translate(PET.x, PET.y);
    ctx.rotate(cab.tick * .01);
    for (let i = 0; i < 12; i += 1) {
      ctx.rotate(Math.PI / 6);
      const ray = ctx.createLinearGradient(0, 0, 0, -300);
      ray.addColorStop(0, `rgba(255,255,255,${.5 * k})`);
      ray.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = ray;
      ctx.beginPath(); ctx.moveTo(-8, 0); ctx.lineTo(8, 0); ctx.lineTo(30, -300); ctx.lineTo(-30, -300); ctx.closePath(); ctx.fill();
    }
    ctx.restore();
    if (hatchFx > 150) { ctx.fillStyle = `rgba(255,255,255,${(hatchFx - 150) / 20})`; ctx.fillRect(0, 0, W, H); }
    ctx.globalAlpha = Math.min(1, k * 2);
    glow(hue(), 24);
    text("IT HATCHED!", W / 2, 150, 40, "#ffffff", "center", 700, Kit.DISPLAY);
    ctx.shadowBlur = 0;
    ctx.globalAlpha = 1;
  }

  // Little drawn icons for the gauges and buttons.
  function foodIcon(item) {
    return ({hydrogenfuel: "power", powergenerators: "power", robotics: "gear", powerconverter: "power", microcontrollers: "chip",
      basicmedicines: "health", advancedmedicines: "health", agronomictreatment: "health", coffee: "cup", tea: "cup", lavianbrandy: "cup"})[item] || "food";
  }

  function icon(name, x, y, s, colour) {
    ctx.save();
    ctx.translate(x, y);
    ctx.strokeStyle = colour;
    ctx.fillStyle = colour;
    ctx.lineWidth = Math.max(1.4, s * .12);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    const r = s / 2;
    ctx.beginPath();
    if (name === "food") {
      ctx.arc(0, r * .1, r * .8, 0, Math.PI); ctx.closePath(); ctx.fill();
      ctx.beginPath(); ctx.moveTo(-r * .4, -r * .3); ctx.quadraticCurveTo(-r * .1, -r * .7, -r * .4, -r * 1); ctx.moveTo(r * .2, -r * .3); ctx.quadraticCurveTo(r * .5, -r * .7, r * .2, -r * 1); ctx.stroke();
    } else if (name === "power") {
      ctx.moveTo(r * .2, -r); ctx.lineTo(-r * .5, r * .1); ctx.lineTo(0, r * .1); ctx.lineTo(-r * .2, r); ctx.lineTo(r * .5, -r * .1); ctx.lineTo(0, -r * .1); ctx.closePath(); ctx.fill();
    } else if (name === "leaf") {
      ctx.moveTo(-r * .8, r * .8); ctx.quadraticCurveTo(-r * .8, -r * .8, r * .8, -r * .8); ctx.quadraticCurveTo(r * .8, r * .8, -r * .8, r * .8); ctx.fill();
    } else if (name === "mood") {
      window.HatchlingArt.heart(ctx, 0, r * .2, r * .9, colour);
    } else if (name === "clean") {
      ctx.moveTo(0, -r); ctx.quadraticCurveTo(r * .9, r * .1, 0, r * .9); ctx.quadraticCurveTo(-r * .9, r * .1, 0, -r); ctx.fill();
    } else if (name === "health") {
      ctx.fillRect(-r * .25, -r * .8, r * .5, r * 1.6); ctx.fillRect(-r * .8, -r * .25, r * 1.6, r * .5);
    } else if (name === "sleep") {
      ctx.arc(0, 0, r * .8, 0, Math.PI * 2); ctx.fill();
      ctx.globalCompositeOperation = "destination-out";
      ctx.beginPath(); ctx.arc(r * .4, -r * .3, r * .7, 0, Math.PI * 2); ctx.fill();
      ctx.globalCompositeOperation = "source-over";
    } else if (name === "play") {
      for (let i = 0; i < 5; i += 1) {
        const a = -Math.PI / 2 + i * Math.PI * 2 / 5, b = a + Math.PI / 5;
        ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r); ctx.lineTo(Math.cos(b) * r * .45, Math.sin(b) * r * .45);
      }
      ctx.closePath(); ctx.fill();
    } else if (name === "vent") {
      for (const dy of [-r * .5, 0, r * .5]) { ctx.moveTo(-r, dy); ctx.quadraticCurveTo(0, dy - r * .4, r * .6, dy); ctx.quadraticCurveTo(r, dy + r * .2, r * .7, dy + r * .35); }
      ctx.stroke();
    } else if (name === "lights") {
      ctx.arc(0, -r * .2, r * .6, Math.PI * .8, Math.PI * 2.2); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(-r * .3, r * .5); ctx.lineTo(r * .3, r * .5); ctx.moveTo(-r * .25, r * .8); ctx.lineTo(r * .25, r * .8); ctx.stroke();
    } else if (name === "cup") {
      ctx.moveTo(-r * .6, -r * .3); ctx.lineTo(-r * .5, r * .7); ctx.lineTo(r * .4, r * .7); ctx.lineTo(r * .5, -r * .3); ctx.closePath(); ctx.fill();
      ctx.beginPath(); ctx.arc(r * .65, r * .15, r * .28, -Math.PI / 2, Math.PI / 2); ctx.stroke();
    } else if (name === "gear" || name === "chip") {
      ctx.fillRect(-r * .55, -r * .55, r * 1.1, r * 1.1);
      for (let i = -1; i <= 1; i += 1) { ctx.fillRect(-r, i * r * .35 - 1, r * .3, 2); ctx.fillRect(r * .7, i * r * .35 - 1, r * .3, 2); }
    }
    ctx.restore();
  }

  function hungerIcon(p) {
    return p?.species === "bot" ? "power" : p?.species === "sample" ? "leaf" : "food";
  }

  function gauges(p) {
    const y = 420, r = 27;
    NEEDS.forEach(([need, label], index) => {
      const x = 70 + index * 115;
      const value = p.stage === "egg" ? 0 : clamp(Number(p.needs?.[need]) || 0, 0, 100);
      const tone = p.stage === "egg" ? colours.dim : value < 25 ? colours.red : value < 50 ? colours.yellow : colours.green;
      const pulse = value < 25 && p.stage !== "egg" ? .5 + Math.sin(cab.tick * .15) * .5 : 0;
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(4, 10, 12, .75)"; ctx.fill();
      ctx.strokeStyle = "rgba(255,255,255,.08)"; ctx.lineWidth = 6; ctx.stroke();
      ctx.beginPath(); ctx.arc(x, y, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * value / 100);
      ctx.strokeStyle = tone; ctx.lineWidth = 6; ctx.lineCap = "round";
      ctx.shadowColor = tone; ctx.shadowBlur = 8 + pulse * 14;
      ctx.stroke();
      ctx.shadowBlur = 0;
      ctx.lineCap = "butt";
      icon(need === "hunger" ? hungerIcon(p) : need === "energy" ? "sleep" : need, x, y - 4, 16, tone);
      text(p.stage === "egg" ? "—" : String(Math.round(value)), x, y + 15, 10, colours.text);
      text(label || p.food_label, x, y + r + 16, 9, colours.muted);
    });
  }

  function button(x, y, w, h, label, act, {key: hotkey = "", off = false, tone = hue(), small = "", glyph = ""} = {}) {
    const hover = !off && pointer.active && pointer.x >= x && pointer.x <= x + w && pointer.y >= y && pointer.y <= y + h;
    const cut = 10;
    ctx.beginPath();
    ctx.moveTo(x + cut, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + h - cut); ctx.lineTo(x + w - cut, y + h); ctx.lineTo(x, y + h); ctx.lineTo(x, y + cut);
    ctx.closePath();
    const fill = ctx.createLinearGradient(0, y, 0, y + h);
    fill.addColorStop(0, hover ? `${tone}40` : "rgba(12, 24, 26, .85)");
    fill.addColorStop(1, hover ? `${tone}18` : "rgba(4, 10, 12, .85)");
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.strokeStyle = off ? "rgba(255,255,255,.12)" : tone;
    ctx.lineWidth = hover ? 2 : 1.2;
    if (hover) { ctx.shadowColor = tone; ctx.shadowBlur = 14; }
    ctx.stroke();
    ctx.shadowBlur = 0;
    const lift = hover ? -1 : 0;
    if (glyph) {
      icon(glyph, x + w / 2, y + 16 + lift, 16, off ? colours.dim : tone);
      text(label, x + w / 2, y + h - (small ? 18 : 10) + lift, 12, off ? colours.dim : colours.text);
    } else text(label, x + w / 2, y + h / 2 + (small ? -1 : 5) + lift, 13, off ? colours.dim : colours.text);
    if (small) text(small, x + w / 2, y + h - 6, 8, off ? colours.dim : colours.muted);
    if (hotkey) text(hotkey, x + 12, y + 13, 8, colours.dim, "left");
    buttons.push({x, y, w, h, act, key: hotkey, off});
  }

  function petForArt(p) {
    const fresh = now() - (p.reaction_at || 0) < 90;
    return {...p, reaction: fresh ? p.reaction : ""};
  }

  function drawHeader(p) {
    ctx.fillStyle = "rgba(2, 6, 8, .55)";
    ctx.fillRect(0, 0, W, 72);
    ctx.fillStyle = hue();
    ctx.fillRect(0, 71, W, 1);
    glow(hue(), 16);
    text(p.name.toUpperCase(), 22, 38, 28, "#ffffff", "left", 700, Kit.DISPLAY);
    ctx.shadowBlur = 0;
    const title = p.stage === "egg" ? `${p.species_name.toUpperCase()} · EGG`
      : `${(p.form_name || p.kind_name || p.species_name).toUpperCase()} · ${p.stage.toUpperCase()} · ${ageText(p.age_hours)}`;
    text(title, 22, 58, 10, colours.muted, "left");
    // The mood, as a chip.
    const word = p.stage === "egg" && p.hatch_minutes > 0 ? `HATCHES IN ${p.hatch_minutes} MIN` : p.mood_word;
    const tone = p.dormant ? "#9fc4e8" : p.sick || p.wants ? colours.yellow : hue();
    ctx.font = `700 15px ${Kit.DISPLAY}`;
    const width = ctx.measureText(word).width + 26;
    ctx.beginPath(); ctx.roundRect(W - 22 - width, 18, width, 26, 13);
    ctx.fillStyle = `${tone}26`; ctx.fill();
    ctx.strokeStyle = tone; ctx.lineWidth = 1.2; ctx.stroke();
    text(word, W - 22 - width / 2, 36, 15, tone, "center", 700, Kit.DISPLAY);
    if (p.wants) text(`WANTS ${p.wants}`, W - 22, 60, 10, colours.yellow, "right");
    // How far to the next stage.
    const span = STAGE_ENDS[p.stage];
    if (span) {
      const share = clamp((p.age_hours - span[0]) / (span[1] - span[0]), 0, 1);
      ctx.fillStyle = "rgba(255,255,255,.06)";
      ctx.fillRect(0, 72, W, 3);
      ctx.fillStyle = hue();
      ctx.fillRect(0, 72, W * share, 3);
      text(`${Math.round(share * 100)}% TO ${span[2]}`, W - 22, 88, 8, colours.dim, "right");
    }
    const outfit = (p.outfits || []).find((item) => item.id === p.outfit);
    const about = [p.trip ? `ON ${String(p.trip.name).toUpperCase()}` : "", p.badges?.length ? `✦ ${p.badges.length}` : "",
      p.trait ? p.trait.toUpperCase() : "", outfit ? `IN ITS ${outfit.label.toUpperCase()}` : "",
      p.favourite_food ? `LOVES ${p.favourite_food.toUpperCase()}` : "",
      p.tricks?.length ? `TRICKS: ${p.tricks.join(", ").toUpperCase()}` : "", p.toys?.length ? `${p.toys.length} TOY${p.toys.length > 1 ? "S" : ""}` : ""]
      .filter(Boolean).join(" · ");
    if (about && p.stage !== "egg") text(about, 22, 88, 8, colours.muted, "left");
  }

  function drawHome(p) {
    drawHeader(p);
    drawPod(p);
    const art = petForArt(p);
    if (!mini) {
      window.HatchlingArt.mess(ctx, p.mess || 0, PET.x, FLOOR - 48, 200, cab.tick / 60);
      ctx.save(); podPath(); ctx.clip();
      life.back(ctx, art, PET.x, PET.y);
      life.drawPet(ctx, art, {x: PET.x, y: PET.y, size: PET.size, t: cab.tick / 60, threeOnly: true});
      life.front(ctx, art, PET.x, PET.y);
      ctx.restore();
    } else {
      life.drawPet(ctx, art, {x: HABITAT.x + 64, y: FLOOR - 40, size: 90, t: cab.tick / 60, threeOnly: true});
      ctx.save();
      podPath();
      ctx.clip();
      mini.draw();
      ctx.restore();
      if (mini.done) {
        ctx.save(); podPath(); ctx.clip();
        ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.fillRect(0, 0, W, H);
        ctx.restore();
        glow(mini.done.won ? colours.green : colours.orange, 18);
        text(mini.done.won ? "WELL PLAYED!" : "SO CLOSE", POD.x, POD.y - 4, 34, mini.done.won ? colours.green : colours.orange, "center", 700, Kit.DISPLAY);
        ctx.shadowBlur = 0;
        text(mini.done.won ? `${p.name.toUpperCase()} LOVED THAT` : `${p.name.toUpperCase()} HAD FUN ANYWAY`, POD.x, POD.y + 22, 12, colours.text);
      }
    }
    drawPodGlass();
    if (p.asleep && !p.dormant) text("LIGHTS OFF · SLEEPING", POD.x, POD.y - POD.ry + 24, 10, "#8fb4ff");
    if (p.dormant) {
      ctx.save(); podPath(); ctx.clip();
      const frost = ctx.createRadialGradient(POD.x, POD.y, 40, POD.x, POD.y, POD.rx);
      frost.addColorStop(0, "rgba(160, 200, 240, .05)"); frost.addColorStop(1, "rgba(200, 230, 255, .4)");
      ctx.fillStyle = frost; ctx.fillRect(0, 0, W, H);
      ctx.restore();
      glow("#b8d4ec", 16);
      text("HIBERNATING", POD.x, POD.y - POD.ry + 44, 28, "#e4f0ff", "center", 700, Kit.DISPLAY);
      ctx.shadowBlur = 0;
      text(`${Math.max(0, p.dormant_hours_left / 24).toFixed(1)} DAYS TO BRING IT BACK`, POD.x, POD.y - POD.ry + 64, 11, "#9fc4e8");
    }
    drawHatchFx();
    if (snapFlash > 0) {
      ctx.save(); podPath(); ctx.clip();
      ctx.fillStyle = `rgba(255, 255, 255, ${snapFlash / 18 * .7})`;
      ctx.fillRect(0, 0, W, H);
      ctx.restore();
      if (snapFlash > 6) text("POSTCARD TAKEN", POD.x, POD.y, 16, "#ffffff", "center", 700, Kit.DISPLAY);
    }
    gauges(p);

    buttons = [];
    const y = 486, bw = (W - 44 - 4 * 8) / 5, busy = Boolean(pending) || Boolean(mini);
    if (p.dormant) {
      button(22, y, W - 44, 52, "REVIVE", () => { rings("#b8d4ec"); ask("revive"); }, {key: "1", off: busy, tone: "#9fc4e8", small: `NEEDS ${p.medicine.toUpperCase()}`});
    } else {
      const off = p.stage === "egg" || busy;
      const awake = off || p.asleep;
      button(22, y, bw, 56, "FEED", () => { screen = "feed"; }, {key: "1", off: awake, glyph: hungerIcon(p)});
      button(22 + (bw + 8), y, bw, 56, "PLAY", () => { screen = "games"; }, {key: "2", off: awake, glyph: "play"});
      button(22 + (bw + 8) * 2, y, bw, 56, "VENT", vent, {key: "3", off: awake, glyph: "vent"});
      button(22 + (bw + 8) * 3, y, bw, 56, "MEDICINE", medicine, {key: "4", off: awake, glyph: "health", tone: p.sick ? colours.yellow : hue()});
      button(22 + (bw + 8) * 4, y, bw, 56, p.asleep ? "WAKE" : "LIGHTS", lights, {key: "5", off, glyph: p.asleep ? "lights" : "sleep"});
    }
    drawLog(p);
    if (p.welcome && welcomed !== p.welcome.at && !mini) drawWelcome(p);
  }

  function drawWelcome(p) {
    const lines = p.welcome.lines || [];
    const w = 380, h = 64 + lines.length * 19, x = (W - w) / 2, y = POD.y - h / 2 + 10;
    ctx.fillStyle = "rgba(4, 12, 14, .92)";
    ctx.beginPath(); ctx.roundRect(x, y, w, h, 10); ctx.fill();
    ctx.strokeStyle = hue(); ctx.lineWidth = 1.2; ctx.stroke();
    glow(hue(), 12);
    text("WELCOME BACK", W / 2, y + 26, 18, hue(), "center", 700, Kit.DISPLAY);
    ctx.shadowBlur = 0;
    lines.forEach((line, index) => text(line, W / 2, y + 50 + index * 19, 12, colours.text, "center", 600, '"Segoe UI", sans-serif'));
    // Its own button, drawn last so it's the one under your click.
    button(W / 2 - 70, y + h - 8, 140, 26, "GLAD TO BE BACK", () => {
      welcomed = p.welcome.at;
      hearts(6);
      ask("welcomed");
    }, {key: "8"});
  }

  function vent() {
    ask("vent");
    sfx.whoosh();
    for (let i = 0; i < 40; i += 1) fx.push({kind: "wind", x: POD.x + between(-160, 160), y: FLOOR - between(0, 160), vx: -between(2, 5), vy: 0, life: between(30, 60)});
  }

  function medicine() {
    ask("medicine");
    rings("#7dff9a");
    for (let i = 0; i < 8; i += 1) fx.push({kind: "cross", x: PET.x + between(-60, 60), y: PET.y - between(0, 40), vx: 0, vy: -between(.6, 1.4), life: 70});
  }

  function lights() {
    ask("lights");
    sfx.chime();
  }

  function drawLog(p) {
    const top = 556;
    ctx.fillStyle = "rgba(2, 8, 10, .7)";
    ctx.beginPath(); ctx.roundRect(22, top, W - 44, H - top - 12, 6); ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,.08)"; ctx.lineWidth = 1; ctx.stroke();
    text("SHIP'S LOG", 36, top + 18, 9, hue(), "left");
    if (pending) text("TRANSMITTING…", 120, top + 18, 9, colours.accent, "left");
    // Start again: a second press within a few seconds lets it go (it's remembered).
    const sure = cab.tick - resetAsked < 240;
    button(W - 104 - 128 - 96, top + 4, 88, 22, sure ? "SURE?" : "RESET", () => {
      if (!sure) { resetAsked = cab.tick; return; }
      resetAsked = -999;
      ask("release");
    }, {key: "9", off: Boolean(pending) || Boolean(mini), tone: sure ? colours.red : colours.muted});
    if (p.stage !== "egg") {
      button(W - 104, top + 4, 76, 22, "SNAP", snap, {key: "6", off: Boolean(mini) || snapFlash > 0});
      // What it wears: each press tries the next one it has earned, then none.
      const earned = (p.outfits || []).filter((item) => item.earned);
      const worn = earned.find((item) => item.id === p.outfit);
      button(W - 104 - 128, top + 4, 120, 22, worn ? worn.label.toUpperCase() : "WEAR", () => {
        const ids = ["", ...earned.map((item) => item.id)];
        ask("wear", {outfit: ids[(ids.indexOf(p.outfit || "") + 1) % ids.length]});
      }, {key: "7", off: !earned.length || Boolean(pending)});
    }
    let row = 0;
    if (notice.text && cab.tick < notice.until) {
      text(notice.text, 36, top + 40, 12, colours.yellow, "left", 600, '"Segoe UI", sans-serif');
      row += 1;
    }
    for (const entry of p.log || []) {
      if (row >= 4) break;
      const y = top + 40 + row * 21;
      const tone = entry.tone === "good" ? colours.green : entry.tone === "bad" ? colours.orange : colours.muted;
      ctx.fillStyle = tone;
      ctx.beginPath(); ctx.arc(40, y - 4, 3, 0, Math.PI * 2); ctx.fill();
      text(entry.text, 52, y, 12, entry.tone === "bad" ? colours.orange : colours.text, "left", 600, '"Segoe UI", sans-serif');
      text(since(entry.at), W - 36, y, 9, colours.dim, "right");
      row += 1;
    }
  }

  function overlayPanel(title, sub) {
    ctx.fillStyle = "rgba(0, 4, 6, .78)";
    ctx.fillRect(0, 0, W, H);
    glow(hue(), 18);
    text(title, W / 2, 112, 30, "#ffffff", "center", 700, Kit.DISPLAY);
    ctx.shadowBlur = 0;
    if (sub) text(sub, W / 2, 134, 10, colours.muted);
  }

  function drawFeed(p) {
    overlayPanel("THE LARDER", "BUY FOOD AT A MARKET AND IT LANDS HERE");
    buttons = [];
    const rows = (p.larder || []).slice(0, 8);
    rows.forEach((item, index) => {
      const y = 158 + index * 52;
      const tone = item.kind === "medicine" ? colours.yellow : item.kind === "treat" ? colours.orange : hue();
      button(60, y, W - 120, 44, `${item.name.toUpperCase()}  ×${item.count}`, () => {
        screen = "home";
        sendFood(item.id, {x: 22 + 50, y: 500});
        ask("feed", {item: item.id});
        float(item.kind === "treat" ? "+MOOD" : item.kind === "medicine" ? "+HEALTH" : `+${p.food_label}`, tone);
      }, {key: String(index + 1), tone, small: item.kind.toUpperCase()});
      icon(foodIcon(item.id), 84, y + 22, 18, tone);
    });
    if (!rows.length) {
      wrap(`The larder is empty. The ship's stores bring ${p.species === "bot" ? "Hydrogen Fuel" : p.species === "sample" ? "Algae" : "Food Cartridges"} in ${Math.ceil(p.stores_hours)} h, or buy something it eats at a market.`,
        W / 2, 200, 420, 13, colours.muted, 18, 4, "center");
    }
    button(W / 2 - 80, H - 80, 160, 42, "BACK", () => { screen = "home"; });
  }

  function drawGames() {
    overlayPanel("PLAY", "A GAME MAKES IT HAPPIER, AND HUNGRIER");
    buttons = [];
    button(90, 200, W - 180, 70, "CATCH THE LIMPET", () => { mini = limpetGame(); screen = "home"; }, {key: "1", small: "THREE CATCHES IN TWELVE SECONDS"});
    button(90, 290, W - 180, 70, "WHERE DID THE THARGON GO?", () => { mini = thargonGame(); screen = "home"; }, {key: "2", small: "WATCH THE ROCKS"});
    button(W / 2 - 80, H - 80, 160, 42, "BACK", () => { screen = "home"; });
  }

  function wrap(value, x, y, width, size, colour, lineHeight = size * 1.35, most = 4, align = "left") {
    ctx.font = `600 ${size}px "Segoe UI", sans-serif`;
    let line = "", row = 0;
    for (const word of String(value || "").split(/\s+/)) {
      const next = line ? `${line} ${word}` : word;
      if (ctx.measureText(next).width > width && line) {
        text(line, x, y + row * lineHeight, size, colour, align, 600, '"Segoe UI", sans-serif');
        line = word;
        row += 1;
        if (row >= most) return row;
      } else line = next;
    }
    if (line) text(line, x, y + row * lineHeight, size, colour, align, 600, '"Segoe UI", sans-serif');
    return row + 1;
  }

  function pedestal(x, y, tone, picked) {
    // A light up from the plinth.
    const beam = ctx.createLinearGradient(0, y - 200, 0, y);
    beam.addColorStop(0, `${tone}00`);
    beam.addColorStop(1, `${tone}${picked ? "70" : "30"}`);
    ctx.fillStyle = beam;
    ctx.beginPath(); ctx.moveTo(x - 30, y - 200); ctx.lineTo(x + 30, y - 200); ctx.lineTo(x + 60, y); ctx.lineTo(x - 60, y); ctx.closePath(); ctx.fill();
    const side = ctx.createLinearGradient(x - 64, 0, x + 64, 0);
    side.addColorStop(0, "#0a1214"); side.addColorStop(.5, "#1d2c30"); side.addColorStop(1, "#0a1214");
    ctx.fillStyle = side;
    ctx.fillRect(x - 64, y, 128, 22);
    ctx.beginPath(); ctx.ellipse(x, y + 22, 64, 12, 0, 0, Math.PI); ctx.fill();
    ctx.beginPath(); ctx.ellipse(x, y, 64, 12, 0, 0, Math.PI * 2);
    ctx.fillStyle = "#16242a"; ctx.fill();
    ctx.strokeStyle = tone; ctx.lineWidth = picked ? 2 : 1;
    if (picked) { ctx.shadowColor = tone; ctx.shadowBlur = 16; }
    ctx.stroke();
    ctx.shadowBlur = 0;
    if (picked) {
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(1, .19);
      ctx.setLineDash([14, 10]);
      ctx.lineDashOffset = -cab.tick;
      ctx.strokeStyle = tone; ctx.lineWidth = 6;
      ctx.beginPath(); ctx.arc(0, 0, 80, 0, Math.PI * 2); ctx.stroke();
      ctx.restore();
      ctx.setLineDash([]);
    }
  }

  function drawChoose() {
    glow(colours.accent, 28);
    text("HATCHLING", W / 2, 66, 50, "#ffffff", "center", 700, Kit.DISPLAY);
    ctx.shadowBlur = 0;
    text("A POCKET PET FOR YOUR COCKPIT · CHOOSE AN EGG", W / 2, 90, 11, colours.accent);
    buttons = [];
    SPECIES.forEach((species, index) => {
      const x = 110 + index * 190, y = 300, picked = choice.species === species, tone = HUE[species];
      pedestal(x, y, tone, picked);
      const size = picked ? 150 : 118;
      const egg = {species, stage: "egg", kind: choice.kind, hatch_minutes: picked ? 3 : 30, needs: {mood: picked ? 90 : 50}};
      const art = {x, y: y - 70 + Math.sin(cab.tick / 30 + index) * 6, size, t: cab.tick / 60, aura: picked};
      window.Hatchling3D?.draw(ctx, egg, art);
      text(NAMES[species], x, y + 54, 12, picked ? "#ffffff" : colours.muted);
      buttons.push({x: x - 80, y: y - 160, w: 160, h: 230, act: () => { if (choice.species !== species) { choice.species = species; sfx.blip(); } }});
    });
    const spec = view?.species?.[choice.species];
    if (spec) wrap(spec.blurb, W / 2, 392, 520, 13, colours.text, 18, 3, "center");
    if (choice.species === "sample") {
      KINDS.forEach((kind, index) => {
        button(104 + index * 134, 432, 124, 30, kind.toUpperCase(), () => { choice.kind = kind; }, {tone: choice.kind === kind ? colours.green : "#2a4040"});
      });
    }
    const names = spec?.names || ["Pip"];
    const name = choice.name || names[choice.suggest % names.length];
    ctx.beginPath(); ctx.roundRect(W / 2 - 150, 478, 300, 44, 8);
    ctx.fillStyle = "rgba(4, 12, 14, .85)"; ctx.fill();
    ctx.strokeStyle = `${hue()}88`; ctx.lineWidth = 1.2; ctx.stroke();
    text("NAME", W / 2 - 138, 492, 8, colours.dim, "left");
    text(`${name.toUpperCase()}${Math.floor(cab.tick / 30) % 2 ? "_" : " "}`, W / 2, 514, 22, choice.name ? "#ffffff" : colours.muted, "center", 700, Kit.DISPLAY);
    button(W / 2 + 160, 486, 92, 28, "ANOTHER", () => { choice.suggest += 1; choice.name = ""; });
    const pulse = .5 + Math.sin(cab.tick * .08) * .5;
    ctx.shadowColor = colours.green; ctx.shadowBlur = 10 + pulse * 14;
    button(W / 2 - 120, 540, 240, 54, "HATCH IT", hatch, {off: Boolean(pending) || !view, tone: colours.green, small: view ? "IT LIVES IN REAL TIME" : "OPEN IN VOID COMPASS"});
    ctx.shadowBlur = 0;
    const memorial = view?.memorial || [];
    const collection = view?.collection || [];
    if (memorial.length) text(`REMEMBERED: ${memorial.slice(-4).map((item) => String(item.name || "").toUpperCase()).join(" · ")}`, W / 2, 616, 10, colours.muted);
    if (collection.length) text(`GROWN UP: ${collection.length} FORM${collection.length === 1 ? "" : "S"} · ${collection.slice(-3).map((item) => item.label.toUpperCase()).join(" · ")}`, W / 2, 634, 10, colours.accent);
    text("← → CHOOSE · TYPE A NAME · ENTER HATCH · M SOUND · C SCREEN", W / 2, H - 14, 9, colours.dim);
  }

  function ageText(hours) {
    const value = Number(hours) || 0;
    return value >= 48 ? `${Math.floor(value / 24)} DAYS OLD` : value >= 1 ? `${Math.floor(value)} H OLD` : "NEWBORN";
  }

  function since(at) {
    const seconds = Math.max(0, now() - (Number(at) || 0));
    if (seconds < 60) return "NOW";
    if (seconds < 3600) return `${Math.floor(seconds / 60)} MIN`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} H`;
    return `${Math.floor(seconds / 86400)} D`;
  }

  function draw() {
    // The Three.js module is deferred. During its load, keep the scene clear of
    // the retired 2D pet so the game never visibly swaps art styles at startup.
    if (!window.Hatchling3D) {
      drawSpace();
      return;
    }
    drawSpace();
    const p = pet();
    if (!p || screen === "choose") {
      drawChoose();
      drawFx();
      return;
    }
    drawHome(p);
    drawFx();
    if (screen === "feed") drawFeed(p);
    else if (screen === "games") drawGames();
    if (cab.sound.muted) text("SOUND OFF", W / 2, H - 2, 8, colours.dim);
  }

  // The card picture: a happy juvenile larva.
  function card() {
    const at = now();
    lastStage = "juvenile";
    onLive({pet: {name: "Glim", species: "larva", species_name: "Thargoid larva", kind: "", kind_name: "", stage: "juvenile",
      form: "", form_name: "", age_hours: 41, needs: {hunger: 74, mood: 91, clean: 62, health: 96, energy: 58}, food_label: "HUNGER",
      asleep: false, sick: false, dormant: false, mood_word: "HAPPY", wants: "", mess: 1, larder: [], medicine: "Basic Medicines",
      stores_hours: 6, reaction: "excited", reaction_at: at,
      log: [{at: at - 30, text: "Thargoid signals. Glim is glowing and humming.", tone: "good"},
        {at: at - 900, text: "Coffee into the larder (4).", tone: "good"},
        {at: at - 2400, text: "Glim had the Fish.", tone: "good"},
        {at: at - 7200, text: "Shields down! Glim hid under the console.", tone: "bad"}]}});
    for (let i = 0; i < 160; i += 1) { cab.tick += 1; update(); }
    hearts(4);
    life.setLook([.5, -.2]);
  }

  function report() {
    return {screen, pet: Boolean(pet()), name: pet()?.name || "", mini: mini?.name || "", pending: Boolean(pending), hearts: fx.filter((item) => item.kind === "heart").length,
      life: life.state()};
  }

  window.hatchling = {state: () => ({...report(), state: cab.state}), play: (name) => life.play(name, pet()), acts: () => life.acts};
})();
