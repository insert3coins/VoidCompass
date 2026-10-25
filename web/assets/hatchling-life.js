// The Hatchling's life on its own (5.6.4), shared by its game page and its
// overlay: it wanders, dozes, sulks at a messy hold, chases motes and plays
// little games by itself (keepy-uppy with a limpet, a canister tower, tag
// with a Thargon, joining up stars), picked by how it feels. All of it is
// show; the deck keeps the real pet.
//
// It also acts out what you're doing (the deck's cue: a jump, docking, a
// fight, a first discovery), plays with the toys it found on your trips,
// shows off its tricks, dances to your music, dreams of where you've been,
// and keeps your local hours. Its personality tilts what it picks.
//
// On a planet it hops by the world's gravity and feels its cold or heat; it
// rides the SRV's bumps, waits at the glass while you're on foot, greets
// you back, turns to the Watcher when it speaks, and wears what it earned.
//
// Positions are in pixels from the pet's home spot (its centre); size is the
// pet's drawn size, range how far it may wander each way, top the room above
// its centre.
(() => {
  "use strict";
  const TAU = Math.PI * 2;
  const DT = 1 / 60;
  const rand = (a, b) => a + Math.random() * (b - a);
  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  const lerp = (a, b, k) => a + (b - a) * k;
  const need = (pet, key) => Number(pet.needs?.[key] ?? 60);
  const pick = (list) => list[Math.floor(Math.random() * list.length)];
  // Where its eyes are, in its 100-unit box: [y, eye size] (for the sunglasses).
  const EYES = {larva: [-5, 4], bot: [-8, 2.7], bacterium: [-2, 3.3], tubus: [-2, 2.4], fungoida: [12, 2.3]};
  // The top of its head and its neck, for what it wears: [head, neck].
  const BODY = {larva: [-38, 13], bot: [-31, 17], bacterium: [-30, 15], tubus: [-25, 12], fungoida: [-30, 22]};
  // A cue from the deck, and what it does about it.
  const CUE_ACTS = {jump: "brace", arrive: "dizzy", dock: "peek", undock: "byebye", touchdown: "landed", liftoff: "liftoff",
    cruise: "whee", drop: "whoa", danger: "hide", discovery: "cheer", heat: "hot", lowfuel: "fuel", scoop: "cool",
    srv: "bumpy", srvback: "aboard", leave: "miss", welcome: "welcome",
    victory: "cheer", mission: "cheer", sad: "sulk", party: "party", newship: "inspect", paid: "coins", upgrade: "cheer",
    repaired: "relief", phew: "relief", boost: "whee", pose: "pose", naughty: "gasp", rude: "huff", fighter: "byebye",
    allfound: "cheer", mapped: "cheer", settlement: "peek", tripdone: "party"};
  // What it shouts when it cheers, by what happened.
  const CHEERS = {victory: ["GOT 'EM!", "TAKE THAT!"], mission: ["WE DID IT!", "JOB DONE!"], upgrade: ["UPGRADES!", "SHINY!"],
    allfound: ["ALL OF THEM!", "EVERY ONE!"], mapped: ["MAPPED!", "PERFECT!"]};
  // On the ground: the places where a world's gravity and heat count.
  const SURFACE = ["landed", "srv", "away"];
  const CAN = 13;
  const THREE_PROP_ACTS = new Set(["toy", "keepy", "tower", "tag", "chase", "stars", "stargaze", "trick", "holo"]);

  // ink: the smallest lettering in pixels (the overlay passes its pixel ratio in);
  // text: the overlay's text size, which every word it draws follows.
  // onSound(kind): a chirp, a cheer, a snore… for a page that has sound.
  // speech: false keeps its words and dreams to itself (the overlay's switch).
  function create({size = 100, range = 100, top = 100, ink = 9, onSound = null, speech = true, text = 1} = {}) {
    const me = {x: 0, squash: 0, vel: 0, lift: 0, hop: null, look: [0, 0], goal: [0, 0], held: 0, tilt: 0, shake: 0, spin: 0, flair: 0,
      face: "", shut: false, act: null, rest: 3, last: "", spare: 0, bits: [], words: [], eggWobble: 0, eggNext: 4,
      clock: 0, cueSeen: null, shades: 0, toyAt: {}, dream: {next: 4, life: 0, text: ""}, greeted: false, snore: 0,
      heavy: 1, bump: 1, heardAt: null, place: "space", chatSeen: null, chat: null,
      danced: -999, bobbed: 0, ear: {energy: 0, bass: 0, treble: 0, avg: 0, heard: -9, lastBeat: -9, beats: 0, gaps: [], period: .5, feel: {energy: 0, bass: 0, treble: 0}}};
    let u = size / 100;
    const ceiling = () => -Math.min(top - 6, 90 * u);
    const floor = () => 44 * u;

    function hop(height, frames = 40) {
      if (!me.hop) me.hop = {t: 0, n: Math.round(frames * Math.sqrt(me.heavy)), h: height * me.heavy};
    }

    function gaze(goal) {
      if (me.held <= 0) me.goal = goal;
    }

    function sound(kind, words = "") {
      try { onSound?.(kind, words); } catch { /* a page without sound */ }
    }

    function say(text) {
      me.words.push({text, x: me.x + rand(-6, 6) * u, y: Math.max(ceiling() + 10 * u, -56 * u), life: 1.8});
    }

    function bit(kind, x, y, extra = {}) {
      me.bits.push({kind, x, y, vx: 0, vy: 0, g: 0, life: 1, max: 1, size: 3 * u, spin: 0, angle: 0, ...extra});
    }

    function a0() {
      for (let i = 0; i < 10; i += 1) {
        bit("dust", me.x + rand(-26, 26) * u, floor() - 2 * u, {vx: rand(-30, 30) * u, vy: -rand(5, 25) * u, life: .8, max: .8});
      }
    }

    function sparkles(x, y, count = 8) {
      for (let i = 0; i < count; i += 1) {
        const a = rand(0, TAU), v = rand(20, 60) * u;
        bit("spark", x, y, {vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: rand(.5, 1), max: 1, size: rand(1.5, 3) * u});
      }
    }

    // A few steps along the floor, a little hop to each.
    function walkTo(target, speed = 55) {
      target = clamp(target, -range, range);
      const gap = target - me.x, step = speed * u * DT;
      if (Math.abs(gap) <= step) { me.x = target; return true; }
      me.x += Math.sign(gap) * step;
      hop(5 * u, 18);
      gaze([Math.sign(gap) * .9, .1]);
      return false;
    }

    function spot() {
      if (range < 4) return 0;
      for (let tries = 0; tries < 6; tries += 1) {
        const x = rand(-range, range);
        if (Math.abs(x - me.x) > range * .35) return x;
      }
      return -me.x;
    }

    const ACTS = {
      wander: {
        weight: () => 3,
        start(a) { a.to = spot(); },
        step(a) { return !walkTo(a.to) && a.t < 8; },
      },
      look: {
        weight: () => 2,
        start(a) { a.next = 0; a.end = rand(2.5, 4.5); },
        step(a) {
          if (a.t >= a.next) { gaze([rand(-1, 1), rand(-.6, .4)]); a.next = a.t + rand(.8, 1.6); }
          return a.t < a.end;
        },
      },
      bounce: {
        weight: (p) => need(p, "mood") > 65 ? 2 : 0,
        start(a) { a.n = 0; me.face = "happy"; },
        step(a) {
          gaze([0, -.3]);
          if (me.hop) return true;
          if (a.n >= 3) { sparkles(me.x, -20 * u, 6); return false; }
          hop(18 * u, 30);
          a.n += 1;
          return true;
        },
      },
      stretch: {
        weight: (p) => need(p, "energy") > 42 ? .75 : 0,
        start() { me.face = "happy"; gaze([0, -.7]); },
        step(a) {
          me.tilt = Math.sin(Math.min(1, a.t / .7) * Math.PI / 2) * .12 * (a.t < 1.3 ? 1 : Math.max(0, 2.8 - a.t) / 1.5);
          if (a.t > 1.2 && !a.sparkled) { a.sparkled = true; sparkles(me.x, -42 * u, 4); }
          return a.t < 2.8;
        },
      },
      groom: {
        weight: (p) => !p.sick && need(p, "clean") < 85 ? .65 : .25,
        start(a) { a.side = Math.random() < .5 ? -1 : 1; me.face = "happy"; },
        step(a) {
          gaze([a.side * .75, -.55]);
          me.shut = a.t % .8 > .6;
          if (a.t > 1.25 && !a.sparkled) { a.sparkled = true; sparkles(me.x, -27 * u, 5); }
          return a.t < 2.2;
        },
        end() { me.shut = false; },
      },
      holo: {
        weight: (p) => need(p, "mood") > 35 ? .45 + Math.min(1, p.traits?.curious || 0) * .5 : 0,
        start(a) {
          a.orb = {x: me.x + rand(-42, 42) * u, y: ceiling() + 22 * u};
          a.orbY = a.orb.y;
          say(pick(["WHAT'S THAT?", "A LITTLE STAR", "BOOP?"]));
        },
        step(a) {
          a.orb.x += Math.sin(a.t * 1.7) * 22 * u * DT;
          a.orb.y = a.orbY + Math.sin(a.t * 3) * 5 * u;
          gaze([clamp((a.orb.x - me.x) / (50 * u), -1, 1), -1]);
          if (a.t > 1.8 && !a.booped) {
            if (Math.abs(a.orb.x - me.x) > 16 * u) walkTo(a.orb.x, 70);
            else {
              a.booped = true;
              a.done = true;
              hop(12 * u, 22);
              me.face = "excited";
              sparkles(a.orb.x, a.orb.y, 7);
            }
          }
          return a.t < 3.5;
        },
      },
      yawn: {
        weight: (p) => need(p, "energy") < 45 ? 3 : .3,
        start() {
          const hour = new Date().getHours();
          say(hour >= 5 && hour < 10 && !me.greeted ? "GOOD MORNING" : "YAWN");
          sound("yawn");
        },
        step(a) {
          if (a.t < 1.1) { me.vel -= .018; gaze([0, -.5]); }
          me.shut = a.t > .4 && a.t < 1.6;
          return a.t < 2.2;
        },
      },
      doze: {
        weight: (p) => need(p, "energy") < 30 ? 3 : (p.traits?.lazy || 0) >= 1 || night() ? .8 : 0,
        start(a) { a.end = rand(6, 10); },
        step(a) {
          me.shut = true;
          me.vel += Math.sin(a.t * 2) * .004;
          if (a.t % 2.2 < DT) { sound("snore"); bit("z", me.x + 16 * u, -40 * u, {vx: 10 * u, vy: -16 * u, life: 1.6, max: 1.6}); }
          if (a.t < a.end) return true;
          me.shut = false;
          me.vel += .8;
          say("!");
          return false;
        },
      },
      rumble: {
        weight: (p) => need(p, "hunger") < 35 ? 3 : 0,
        start(a) { a.bowl = clamp(me.x + (me.x > 0 ? -40 : 40) * u, -range - 20 * u, range + 20 * u); say("GRUMBLE"); },
        step(a) {
          me.shake = Math.sin(a.t * 55) * 1.4 * u * (a.t % 1 < .5 ? 1 : 0);
          gaze([Math.sign(a.bowl - me.x) * .8, .7]);
          if (a.t % .5 < DT) bit("line", me.x + rand(-14, 14) * u, 14 * u, {life: .5, max: .5});
          if (a.t < 3) return true;
          me.shake = 0;
          return false;
        },
        back(ctx, a, ox, oy, tone) {
          // An empty dish.
          const x = ox + a.bowl, y = oy + floor() - 3 * u;
          ctx.fillStyle = "#2a3540";
          ctx.beginPath();
          ctx.ellipse(x, y, 13 * u, 4 * u, 0, 0, Math.PI);
          ctx.fill();
          ctx.strokeStyle = tone.line;
          ctx.globalAlpha = .6;
          ctx.lineWidth = Math.max(1, u);
          ctx.beginPath();
          ctx.ellipse(x, y, 13 * u, 3 * u, 0, 0, TAU);
          ctx.stroke();
          ctx.globalAlpha = 1;
        },
      },
      sulk: {
        weight: (p) => (p.mess > 0 || need(p, "clean") < 35) ? 2 : 0,
        step(a) {
          gaze([.2, .8]);
          if (a.t % .12 < DT) bit("drop", me.x + rand(-12, 12) * u, -62 * u, {vy: 70 * u, life: .35, max: .35});
          return a.t < 3.5;
        },
        front(ctx, a, ox, oy) {
          // A little raincloud over its head.
          const x = ox + me.x, y = oy - 66 * u - me.lift;
          ctx.fillStyle = "#6d7a88";
          ctx.globalAlpha = Math.min(1, a.t * 3, (3.5 - a.t) * 3);
          for (const [dx, dy, r] of [[-9, 2, 7], [0, -3, 9], [10, 2, 7]]) {
            ctx.beginPath();
            ctx.arc(x + dx * u, y + dy * u, r * u, 0, TAU);
            ctx.fill();
          }
          ctx.globalAlpha = 1;
        },
      },
      sneeze: {
        weight: (p) => p.sick ? 4 : 0,
        step(a) {
          if (a.t < .9) { me.vel -= .025; gaze([0, -.6]); return true; }
          if (!a.done) {
            a.done = true;
            me.vel += 1.4;
            say("ACHOO!");
            sound("sneeze");
            const way = me.look[0] >= 0 ? 1 : -1;
            for (let i = 0; i < 10; i += 1) {
              bit("drop", me.x + way * 10 * u, -8 * u, {vx: way * rand(40, 110) * u, vy: rand(-40, 10) * u, g: 160 * u, life: .7, max: .7});
            }
          }
          return a.t < 1.6;
        },
      },
      stargaze: {
        weight: () => 1,
        start(a) { a.star = {x: me.x - 70 * u, y: ceiling() + 8 * u}; },
        step(a) {
          a.star.x += 60 * u * DT;
          gaze([clamp((a.star.x - me.x) / (60 * u), -1, 1), -1]);
          if (a.t > 2.6 && !a.done) { a.done = true; me.face = "happy"; sparkles(a.star.x, a.star.y, 6); }
          return a.t < 4;
        },
        front(ctx, a, ox, oy, tone) {
          if (a.done) return;
          const x = ox + a.star.x, y = oy + a.star.y;
          ctx.strokeStyle = tone.glow;
          ctx.lineWidth = Math.max(1, u);
          ctx.globalAlpha = .7;
          ctx.beginPath();
          ctx.lineWidth = Math.max(1, 1.6 * u);
          ctx.moveTo(x - 36 * u, y + 7 * u);
          ctx.lineTo(x, y);
          ctx.stroke();
          ctx.globalAlpha = 1;
          ctx.fillStyle = "#ffffff";
          ctx.shadowColor = tone.glow;
          ctx.shadowBlur = 10 * u;
          ctx.beginPath();
          ctx.arc(x, y, 2.6 * u, 0, TAU);
          ctx.fill();
          ctx.shadowBlur = 0;
        },
      },
      chase: {
        weight: (p) => need(p, "energy") > 35 ? 2 : 0,
        start(a) { a.mote = {x: me.x + rand(-40, 40) * u, y: -30 * u, vx: 0, vy: 0}; a.catchAt = rand(2, 5); },
        step(a) {
          const m = a.mote;
          m.vx = (m.vx + rand(-500, 500) * u * DT) * .96;
          m.vy = (m.vy + rand(-500, 500) * u * DT) * .96;
          m.x = clamp(m.x + m.vx * DT, -range - 25 * u, range + 25 * u);
          m.y = clamp(m.y + m.vy * DT, ceiling() + 10 * u, 22 * u);
          if (Math.abs(m.x - me.x) > 14 * u) walkTo(m.x, 70);
          gaze([clamp((m.x - me.x) / (50 * u), -1, 1), clamp(m.y / (50 * u), -1, 1)]);
          if (Math.abs(m.x - me.x) < 14 * u && m.y > -26 * u && !me.hop) {
            hop(22 * u, 34);
            if (a.t > a.catchAt) { sparkles(m.x, m.y, 10); say("GOT IT!"); me.face = "happy"; return false; }
          }
          return a.t < 8;
        },
        front(ctx, a, ox, oy, tone) {
          const m = a.mote;
          ctx.fillStyle = tone.glow;
          ctx.shadowColor = tone.glow;
          ctx.shadowBlur = 8 * u;
          ctx.beginPath();
          ctx.arc(ox + m.x, oy + m.y, 3.6 * u * (1 + Math.sin(a.t * 12) * .2), 0, TAU);
          ctx.fill();
          ctx.shadowBlur = 0;
        },
      },
      wave: {
        weight: () => 1,
        start() { me.face = "happy"; sound("chirp"); bit("heart", me.x, -46 * u, {vy: -26 * u, life: 1.2, max: 1.2, size: 5 * u}); },
        step(a) { gaze([0, .15]); me.held = 0; return a.t < 2.2; },
      },
      hum: {
        weight: (p) => p.species === "larva" ? 1.5 : 0,
        step(a) {
          if (a.t % .55 < DT) bit("ring", me.x, -me.lift, {life: 1, max: 1, size: 20 * u});
          if (a.t < DT) sound("hum");
          me.vel += Math.sin(a.t * 30) * .01;
          return a.t < 3;
        },
      },
      scan: {
        weight: (p) => p.species === "bot" ? 1.5 : 0,
        step(a) {
          a.sweep = Math.sin(a.t * 1.8);
          if (a.t % .9 < DT) sound("beep");
          gaze([a.sweep, .6]);
          return a.t < 3.5;
        },
        front(ctx, a, ox, oy, tone) {
          const ex = ox + me.x, ey = oy - 6 * u - me.lift;
          const hit = ex + a.sweep * 60 * u, fy = oy + floor();
          ctx.fillStyle = tone.line;
          ctx.globalAlpha = .18;
          ctx.beginPath();
          ctx.moveTo(ex, ey);
          ctx.lineTo(hit - 12 * u, fy);
          ctx.lineTo(hit + 12 * u, fy);
          ctx.closePath();
          ctx.fill();
          ctx.globalAlpha = .8;
          ctx.fillRect(hit - 12 * u, fy - 1, 24 * u, Math.max(1, u));
          ctx.globalAlpha = 1;
        },
      },
      sway: {
        weight: (p) => p.species === "sample" ? 1.5 : 0,
        step(a) {
          me.tilt = Math.sin(a.t * 2.4) * .14 * Math.min(1, a.t, 4 - a.t);
          if (a.t % .3 < DT) bit("spore", me.x + rand(-20, 20) * u, -20 * u, {vx: rand(-8, 8) * u, vy: -rand(14, 30) * u, life: 1.6, max: 1.6});
          return a.t < 4;
        },
      },

      dance: {
        // Your music is playing: it dances, and how depends on what it hears
        // (the levels the music visualizers use): bounces to a heavy beat,
        // headbangs to loud and bright, shuffles, or sways to something slow.
        // A set now and then, not all the time: a rest after each, more when it's happy, less when lazy.
        weight: (p) => !p.music || me.clock - me.danced < 45 ? 0
          : 2.5 * (need(p, "mood") > 70 ? 1.4 : 1) * ((p.traits?.lazy || 0) >= 1 ? .6 : 1),
        start(a) { me.face = "happy"; a.style = ""; a.pick = 0; a.step = 1; a.length = rand(12, 16); },
        step(a, p) {
          const ear = me.ear, live = me.clock - ear.heard < 1.5;
          if (a.t >= a.pick || (a.style === "groove" && live)) {
            a.pick = a.t + 6;
            const was = a.style;
            const feel = ear.feel;
            a.style = !live ? "groove" : feel.energy < .18 ? "sway"
              : feel.energy > .55 && feel.treble > .3 ? (p.species === "bot" ? "robot" : "headbang")
                : feel.bass > .45 ? "bounce" : "shuffle";
            if (was && was !== a.style && Math.random() < .5) sparkles(me.x, -30 * u, 5);
          }
          // On the beat it hears, else on a steady half-second.
          const period = live ? ear.period : .5;
          const beat = live ? ear.beats : Math.floor(a.t / period);
          const onBeat = beat !== a.beat;
          a.beat = beat;
          const notes = () => bit("note", me.x + rand(-22, 22) * u, -42 * u, {vx: rand(-10, 10) * u, vy: -28 * u, life: 1.3, max: 1.3});
          me.shut = a.style === "sway";
          if (a.style === "sway") {
            me.tilt = Math.sin(me.clock * TAU / (period * 2)) * .14;
            gaze([Math.sin(me.clock * TAU / (period * 4)) * .5, -.1]);
            if (onBeat && beat % 4 === 0) notes();
          } else if (a.style === "headbang") {
            if (onBeat) { me.vel += .6 + ear.bass * .4; gaze([rand(-.3, .3), .8]); if (beat % 2) notes(); }
            else if (me.vel < 0) gaze([0, -.4]);
            me.shake = ear.energy > .7 ? Math.sin(me.clock * 60) * .8 * u : 0;
          } else if (a.style === "robot") {
            if (onBeat) { a.step = -a.step; me.tilt = .15 * a.step; gaze([a.step * .9, 0]); if (beat % 2) notes(); }
          } else if (a.style === "shuffle") {
            if (onBeat) { a.step = -a.step; hop(5 * u, 14); if (beat % 3 === 0) notes(); }
            walkTo(a.step * 16 * u + (a.home ?? (a.home = me.x)), 140);
            gaze([a.step * .6, -.1]);
          } else {
            if (onBeat) { hop((a.style === "bounce" ? 6 + ear.bass * 10 : 7) * u, a.style === "bounce" ? 18 : 20); if (beat % 2) notes(); }
            me.tilt = Math.sin(me.clock * TAU / (period * 2)) * .1;
            gaze([Math.sin(me.clock * Math.PI) * .6, -.2]);
          }
          // The music swells: a little jump and a wiggle, now and then (not a spin).
          if (live && a.t > 2 && ear.energy > .5 && ear.energy > ear.feel.energy + .15 && a.t - (a.flourished ?? -9) > 8) {
            a.flourished = a.t;
            a.wiggle = 1;
            hop(16 * u, 30);
            sparkles(me.x, -30 * u, 6);
          }
          if (a.wiggle > 0) {
            a.wiggle = Math.max(0, a.wiggle - DT / .8);
            me.flair = Math.sin((1 - a.wiggle) * TAU * 1.5) * .18 * a.wiggle;
          } else me.flair = 0;
          return p.music && a.t < a.length;
        },
        end() { me.shut = false; me.shake = 0; me.tilt = 0; me.flair = 0; me.danced = me.clock; },
      },
      toy: {
        // One of the toys it found on your trips.
        weight: (p) => (p.toys || []).length ? 2 : 0,
        start(a, p) {
          a.toy = pick(p.toys || []) || {kind: "pebble", label: "a pebble"};
          a.x = toyX(p, a.toy.kind);
          a.vx = 0;
          a.pushes = 0;
          a.wait = 0;
          a.end = Infinity;
        },
        step(a, p) {
          const edge = range + 25 * u;
          a.x = clamp(a.x + a.vx * DT, -edge, edge);
          a.vx *= .94;
          if (a.wait > 0) a.wait -= DT;
          if (a.t >= a.end) return false;
          if (a.pushes >= 3) { gaze([clamp((a.x - me.x) / (40 * u), -1, 1), .5]); return true; }
          const side = me.x <= a.x ? -1 : 1;
          if (!walkTo(a.x + side * 18 * u, 60) || a.wait > 0) return a.t < 14;
          const away = -side, kind = a.toy.kind;
          if (kind === "sensor" && p.species !== "larva") {
            me.face = "scared"; me.vel += .8; hop(14 * u, 26); say("EEK!"); sound("eek");
            a.pushes = 3; a.end = a.t + 1.6;
          } else if (kind === "relic" && p.species === "larva") {
            me.face = "angry"; a.vx = away * 170 * u; say("HMPH"); sound("grumble");
            a.pushes = 3; a.end = a.t + 1.6;
          } else {
            a.vx = away * rand(50, 90) * u;
            a.pushes += 1;
            a.wait = .7;
            hop(6 * u, 18);
            if (a.pushes === 1 && Math.random() < .5) say(a.toy.label.toUpperCase());
            if (a.pushes >= 3) { a.end = a.t + 1.4; me.face = "happy"; sound("chirp"); }
          }
          return true;
        },
        end(a) { me.toyAt[a.toy.kind] = a.x; },
      },
      trick: {
        // Showing off what you taught it.
        weight: (p) => (p.tricks || []).length ? 1.4 : 0,
        start(a, p) { a.trick = pick(p.tricks || []) || "spin"; me.face = "happy"; say(`${a.trick.toUpperCase()}!`); sound("cheer"); },
        step(a) {
          const k = a.t;
          if (a.trick === "spin") me.spin = Math.min(1, k / .9) * TAU;
          else if (a.trick === "flip") {
            if (!a.hopped) { a.hopped = true; hop(42 * u, 54); }
            me.spin = -Math.min(1, k / .9) * TAU;
          } else if (a.trick === "wave") {
            gaze([0, .1]);
            if (k % .45 < DT) { me.vel += .3; bit("heart", me.x + rand(-10, 10) * u, -46 * u, {vy: -26 * u, life: 1, max: 1, size: 4 * u}); }
          } else if (a.trick === "bow") me.tilt = Math.sin(Math.min(1, k / 1.4) * Math.PI) * .42;
          else if (a.trick === "juggle") gaze([Math.sin(k * 6) * .5, -1]);
          if (k < (a.trick === "juggle" ? 3.2 : 1.6)) return true;
          me.spin = 0;
          sparkles(me.x, -30 * u, 8);
          return false;
        },
        front(ctx, a, ox, oy) {
          if (a.trick !== "juggle") return;
          ["#ff8a3d", "#54e39a", "#7fe8ff"].forEach((colour, i) => {
            const phase = a.t * 1.6 + i / 3;
            ctx.fillStyle = colour;
            ctx.beginPath();
            ctx.arc(ox + me.x + Math.cos(phase * TAU) * 14 * u, oy - 58 * u - me.lift - Math.abs(Math.sin(phase * TAU)) * 20 * u, 3 * u, 0, TAU);
            ctx.fill();
          });
        },
      },

      // ---- On a world, in the SRV, and while you're on foot. ----
      shiver: {
        weight: (p) => SURFACE.includes(p.place) && p.world && p.world.temp > 0 && p.world.temp < 180 ? 3 : 0,
        start() { say(pick(["BRRR…", "SO COLD", "BRR"])); },
        step(a) {
          me.shake = Math.sin(a.t * 80) * .9 * u;
          if (a.t % .3 < DT) bit("frost", me.x + rand(-24, 24) * u, -rand(10, 40) * u, {vy: 8 * u, life: .9, max: .9});
          if (a.t < 3) return true;
          me.shake = 0;
          return false;
        },
      },
      bumpy: {
        weight: () => 0,
        start() { me.face = "excited"; say(pick(["BUMPY!", "WHEE, THE SRV", "HOLD ON TIGHT"])); sound("cheer"); },
        step(a) { if (a.t % .4 < DT) hop(10 * u, 18); return a.t < 2; },
      },
      aboard: {
        weight: () => 0,
        start() { say(pick(["HOME SWEET SHIP", "BACK ABOARD"])); hop(12 * u, 24); },
        step(a) { return a.t < 1.6; },
      },
      miss: {
        // You're out on foot: it waits at the glass.
        weight: (p) => p.place === "away" ? 6 : 0,
        start() { if (Math.random() < .5) say(pick(["WHERE'D YOU GO?", "COME BACK SOON", "…"])); },
        step(a) {
          walkTo(0, 45);
          gaze([Math.sin(a.t * .7) * .3, .35]);
          if (a.t % 2.5 < DT) me.vel -= .12;
          return a.t < 6;
        },
      },
      welcome: {
        weight: () => 0,
        start() { me.face = "excited"; say(pick(["YOU'RE BACK!", "MISSED YOU!", "THERE YOU ARE!"])); sound("cheer"); },
        step(a) {
          gaze([0, .2]);
          if (a.t % .45 < DT && a.t < 2) {
            hop(16 * u, 24);
            bit("heart", me.x + rand(-14, 14) * u, -46 * u, {vy: -28 * u, life: 1.2, max: 1.2, size: 5 * u});
          }
          return a.t < 3;
        },
      },
      listen: {
        // The Watcher said something: it turns to look.
        weight: () => 0,
        start(a, p) { a.side = p.watcher?.side || [0, -1]; me.vel += .25; },
        step(a) {
          gaze([a.side[0] * .95, a.side[1] * .8 || -.4]);
          return a.t < 3.5;
        },
      },
      company: {
        // The weary Watcher spoke: it goes and sits quietly near it.
        weight: () => 0,
        start(a, p) { a.side = p.watcher?.side || [0, -1]; },
        step(a) {
          if (!walkTo(a.side[0] * range * .8, 40)) return a.t < 8;
          gaze([a.side[0] * .8, a.side[1] * .6 || -.3]);
          me.vel += (.12 - me.squash) * .05;
          return a.t < 8;
        },
      },

      party: {
        // A promotion: confetti.
        weight: () => 0,
        start(a, p) { me.face = "excited"; say(p?.cue?.kind === "tripdone" ? "WE MADE IT!" : "PROMOTED!"); sound("cheer"); },
        step(a) {
          if (a.t % .12 < DT && a.t < 2) {
            bit("confetti", me.x + rand(-60, 60) * u, ceiling() + 4 * u, {vx: rand(-15, 15) * u, vy: rand(20, 50) * u, life: 2, max: 2,
              spin: rand(-8, 8), size: rand(2, 3.4) * u, colour: pick(["#ff6b9a", "#ffd166", "#54e39a", "#7fe8ff", "#c49bff"])});
          }
          if (a.t % .5 < DT && a.t < 2.5) hop(14 * u, 26);
          return a.t < 3.2;
        },
      },
      inspect: {
        // A different ship: it has a good look round.
        weight: () => 0,
        start(a) { say("NEW SHIP!"); a.stops = [-range * .8, range * .8, 0]; },
        step(a) {
          if (!a.stops.length) return a.t < 6;
          if (walkTo(a.stops[0], 60)) {
            gaze([Math.sign(a.stops[0] || 1) * .9, rand(-.5, .3)]);
            a.wait = (a.wait || 0) + DT;
            if (a.wait > .9) { a.stops.shift(); a.wait = 0; }
          }
          return a.t < 9;
        },
      },
      coins: {
        // Paid: credits rain down.
        weight: () => 0,
        start() { me.face = "happy"; say(pick(["CREDITS!", "KA-CHING!"])); sound("chirp"); },
        step(a) {
          if (a.t % .09 < DT && a.t < 1.4) {
            bit("coin", me.x + rand(-40, 40) * u, ceiling() + 4 * u, {vy: rand(60, 110) * u, g: 140 * u, life: 1.6, max: 1.6,
              floor: floor() - 2 * u, spin: rand(4, 9)});
          }
          gaze([0, -.6]);
          return a.t < 2.6;
        },
      },
      relief: {
        weight: () => 0,
        start() { say(pick(["PHEW", "THAT WAS CLOSE"])); },
        step(a) { if (a.t < .5) me.vel += .05; gaze([0, .4]); return a.t < 1.8; },
      },
      pose: {
        // A screenshot: it strikes a pose.
        weight: () => 0,
        start() { me.face = "happy"; say(pick(["CHEESE!", "MY GOOD SIDE", "SNAP!"])); },
        step(a) {
          me.tilt = .16 * Math.sin(Math.min(1, a.t / .4) * Math.PI / 2) * (a.t < 1.6 ? 1 : Math.max(0, 2.2 - a.t) / .6);
          gaze([0, 0]);
          if (a.t > .4 && !a.flash) { a.flash = true; sparkles(me.x, -20 * u, 10); }
          return a.t < 2.2;
        },
      },
      gasp: {
        weight: () => 0,
        start() { me.face = "scared"; say(pick(["OOH!", "NAUGHTY!", "I SAW THAT"])); sound("eek"); me.vel -= .3; },
        step(a) { gaze([0, .2]); return a.t < 1.8; },
      },
      huff: {
        weight: () => 0,
        start() { me.face = "angry"; say(pick(["RUDE!", "HMPH", "LET US IN!"])); sound("grumble"); },
        step(a) { if (a.t % .35 < DT && a.t < 1) me.vel += .25; return a.t < 1.8; },
      },

      // ---- What you're doing, acted out (the deck's cue). ----
      brace: {
        weight: () => 0,
        start() { say("HOLD ON!"); sound("eek"); },
        step(a) {
          me.vel += (.45 - me.squash) * .15;
          me.shake = a.t > .6 ? Math.sin(a.t * 70) * 1.4 * u : 0;
          me.shut = a.t > .9 && a.t < 3.4;
          gaze([0, 0]);
          if (a.t < 4) return true;
          me.shake = 0;
          return false;
        },
        back(ctx, a, ox, oy, tone) {
          // Witch-space streaming past the pod.
          if (a.t < .7) return;
          ctx.strokeStyle = tone.glow;
          ctx.lineWidth = Math.max(1, u * .8);
          for (let i = 0; i < 24; i += 1) {
            const angle = i / 24 * TAU + i * 1.7, k = (me.clock * 1.4 + i * .37) % 1;
            const r1 = 20 * u + k * 110 * u, r2 = r1 + (10 + k * 30) * u;
            ctx.globalAlpha = k * .5;
            ctx.beginPath();
            ctx.moveTo(ox + me.x + Math.cos(angle) * r1, oy + Math.sin(angle) * r1 * .6);
            ctx.lineTo(ox + me.x + Math.cos(angle) * r2, oy + Math.sin(angle) * r2 * .6);
            ctx.stroke();
          }
          ctx.globalAlpha = 1;
        },
      },
      dizzy: {
        weight: () => 0,
        start() { if (Math.random() < .6) say(pick(["WHERE ARE WE?", "WOOZY…", "NEW STAR!"])); },
        step(a) {
          me.tilt = Math.sin(a.t * 9) * .1 * Math.max(0, 1 - a.t / 3);
          gaze([Math.sin(a.t * 5) * .8, Math.cos(a.t * 5) * .4]);
          return a.t < 3;
        },
        front(ctx, a, ox, oy, tone) {
          for (let i = 0; i < 3; i += 1) {
            const angle = a.t * 5 + i / 3 * TAU;
            ctx.globalAlpha = Math.max(0, 1 - a.t / 3);
            window.HatchlingArt.sparkle(ctx, ox + me.x + Math.cos(angle) * 22 * u, oy - 52 * u - me.lift + Math.sin(angle) * 5 * u, 3 * u, tone.glow);
          }
          ctx.globalAlpha = 1;
        },
      },
      peek: {
        weight: () => 0,
        start() { me.face = "happy"; say(pick(["A STATION!", "OOH, LIGHTS", "WE'RE IN!"])); sound("chirp"); },
        step(a) { gaze([0, .3]); if (a.t < .4) me.vel -= .03; return a.t < 2.6; },
      },
      byebye: {
        weight: () => 0,
        start() { say("BYE!"); },
        step(a) {
          gaze([.8, -.2]);
          if (a.t % .5 < DT) hop(6 * u, 18);
          return a.t < 2;
        },
      },
      landed: {
        weight: () => 0,
        start() { me.face = "happy"; say("TOUCHDOWN!"); sound("cheer"); a0(); },
        step(a) {
          if (a.t % .45 < DT && a.t < 1) hop(12 * u, 24);
          return a.t < 2;
        },
      },
      liftoff: {
        weight: () => 0,
        start() { say("UP WE GO!"); hop(28 * u, 40); },
        step(a) { gaze([0, -1]); return a.t < 1.6; },
      },
      whee: {
        weight: () => 0,
        start() { me.face = "excited"; say("WHEEE!"); sound("cheer"); },
        step(a) { me.tilt = -.16 * Math.sin(Math.min(1, a.t / 2.4) * Math.PI); gaze([-.6, -.4]); return a.t < 2.4; },
      },
      whoa: {
        weight: () => 0,
        start() { say("WHOA"); },
        step(a) {
          me.shake = a.t < .6 ? Math.sin(a.t * 60) * 1.2 * u : 0;
          if (a.t < .3) me.vel += .04;
          return a.t < 1.4;
        },
      },
      hide: {
        weight: () => 0,
        start(a, p) {
          a.brave = (p.traits?.brave || 0) >= 1;
          if (a.brave) { me.face = "angry"; say("BRING IT ON!"); sound("grumble"); }
          else { me.face = "scared"; say("EEK!"); sound("eek"); a.to = me.x >= 0 ? range : -range; }
        },
        step(a) {
          if (a.brave) {
            if (a.t % .5 < DT) hop(10 * u, 20);
            gaze([0, 0]);
          } else {
            walkTo(a.to, 110);
            me.shake = Math.sin(a.t * 50) * 1 * u;
            gaze([-Math.sign(a.to) * .8, .6]);
          }
          if (a.t < 5) return true;
          me.shake = 0;
          return false;
        },
      },
      cheer: {
        weight: () => 0,
        start(a, p) { me.face = "excited"; say(pick(CHEERS[p?.cue?.kind] || ["FIRST!", "NEW!", "OOOH!", "WE FOUND IT!"])); sound("cheer"); hop(30 * u, 40); },
        step(a) {
          if (a.t > .3 && !a.done) { a.done = true; sparkles(me.x, -40 * u, 14); }
          return a.t < 2;
        },
      },
      hot: {
        weight: (p) => SURFACE.includes(p.place) && p.world && p.world.temp > 500 ? 3 : 0,
        start() { say("TOO HOT!"); },
        step(a) {
          if (a.t % .2 < DT) bit("drop", me.x + rand(-16, 16) * u, -24 * u, {vx: rand(-20, 20) * u, vy: -rand(10, 30) * u, g: 120 * u, life: .7, max: .7});
          gaze([0, -.8]);
          me.vel += Math.sin(a.t * 20) * .01;
          return a.t < 3;
        },
      },
      fuel: {
        weight: () => 0,
        start() { say("FUEL…?"); sound("grumble"); },
        step(a) { gaze([.6, .6]); return a.t < 3.2; },
        front(ctx, a, ox, oy) {
          // A little fuel gauge, blinking red.
          const x = ox + me.x + 26 * u, y = oy - 30 * u;
          ctx.fillStyle = "#1a2229";
          ctx.fillRect(x - 3 * u, y - 10 * u, 6 * u, 20 * u);
          ctx.fillStyle = Math.floor(a.t * 4) % 2 ? "#ff6b70" : "#5a2025";
          ctx.fillRect(x - 2 * u, y + 5 * u, 4 * u, 4 * u);
        },
      },
      cool: {
        weight: () => 0,
        start() { me.shades = 25; me.face = "happy"; say("SHADES ON"); },
        step(a) { gaze([.4, -.9]); return a.t < 2.4; },
      },

      // ---- The games it plays by itself. ----
      keepy: {
        weight: (p) => need(p, "energy") > 35 && need(p, "mood") > 25 && !p.sick ? 1.6 : 0,
        start(a, p) {
          const room = Math.max(12, (-ceiling() / u) - 52);
          a.kick = () => -Math.sqrt(2 * 520 * room) * rand(.8, .95) * u;
          a.ball = {x: me.x, y: ceiling() + 6 * u, vx: 0, vy: 0, spin: 0};
          a.hits = 0;
          a.goal = Math.round(rand(4, 8 + need(p, "energy") / 12));
          say("KEEPY-UPPY");
        },
        step(a) {
          const b = a.ball;
          b.vy += 520 * u * DT;
          b.x = clamp(b.x + b.vx * DT, -range - 10 * u, range + 10 * u);
          b.y += b.vy * DT;
          b.spin += b.vx * DT * .1;
          if (!a.dropped) {
            if (Math.abs(b.x - me.x) > 4 * u) walkTo(b.x, 95);
            gaze([clamp((b.x - me.x) / (40 * u), -1, 1), -1]);
            const head = -44 * u - me.lift;
            if (b.vy > 0 && b.y >= head - 4 * u) {
              if (a.hits < a.goal && Math.abs(b.x - me.x) < 16 * u) {
                a.hits += 1;
                b.vy = a.kick();
                b.vx = rand(-28, 28) * u - Math.sign(b.x) * (Math.abs(b.x) > range * .6 ? 20 * u : 0);
                me.vel += .45;
                sound("boing");
                me.face = a.hits > 3 ? "excited" : "happy";
                me.words.push({text: String(a.hits), x: b.x, y: head - 10 * u, life: .6, small: true});
              } else a.dropped = a.t;
            }
            return true;
          }
          if (b.y >= floor() - 3 * u) { b.y = floor() - 3 * u; b.vy *= -.4; b.vx *= .7; }
          gaze([clamp((b.x - me.x) / (40 * u), -1, 1), .7]);
          if (a.t - a.dropped > 1.3) {
            say(a.hits >= 10 ? `${a.hits} IN A ROW!` : `${a.hits} KEEPY-UPS`);
            me.face = a.hits >= 6 ? "happy" : "";
            return false;
          }
          return true;
        },
        front(ctx, a, ox, oy, tone) {
          // A limpet: a little drone with an orange light.
          const b = a.ball, x = ox + b.x, y = oy + b.y;
          ctx.save();
          ctx.translate(x, y);
          ctx.rotate(b.spin);
          ctx.fillStyle = "#c9d2db";
          ctx.beginPath();
          for (let i = 0; i < 6; i += 1) ctx.lineTo(Math.cos(i / 6 * TAU) * 7 * u, Math.sin(i / 6 * TAU) * 7 * u);
          ctx.closePath();
          ctx.fill();
          ctx.fillStyle = "#ff8a3d";
          ctx.shadowColor = "#ff8a3d";
          ctx.shadowBlur = 6 * u;
          ctx.beginPath();
          ctx.arc(0, 0, 2.4 * u, 0, TAU);
          ctx.fill();
          ctx.restore();
        },
      },
      tower: {
        weight: (p) => need(p, "energy") > 30 && !p.sick ? 1.3 : 0,
        start(a) {
          a.side = me.x > 0 ? -1 : 1;
          a.at = clamp(me.x + a.side * 62 * u, -range - 30 * u, range + 30 * u);
          a.cans = 0;
          a.goal = Math.min(Math.round(rand(3, 7)), Math.floor((floor() - ceiling()) / (CAN * u)) - 2);
          a.next = .6;
          a.drop = null;
          a.lean = 0;
          say("STACKING");
        },
        step(a) {
          gaze([a.side * .8, -(.1 + a.cans * .12)]);
          if (a.fell) {
            if (a.t - a.fell > .6) me.face = "happy";
            return a.t - a.fell < 1.8;
          }
          if (a.cans >= a.goal) {
            a.wobble = (a.wobble || 0) + DT;
            a.lean = Math.sin(a.wobble * 9) * a.wobble * .06;
            if (a.wobble < 1.4) return true;
            a.fell = a.t;
            sound("crash");
            me.face = "scared";
            me.vel += 1;
            say(`TOWER OF ${a.cans}!`);
            for (let k = 0; k < a.cans; k += 1) {
              bit("can", a.at, floor() - (k + .5) * CAN * u, {vx: (a.side * rand(10, 70) + rand(-30, 30)) * u, vy: -rand(20, 90) * u, g: 300 * u,
                life: 1.6, max: 1.6, spin: rand(-6, 6), floor: floor() - 4 * u});
            }
            a.cans = 0;
            return true;
          }
          if (!a.drop && a.t >= a.next) a.drop = {y: ceiling(), vy: 0};
          if (a.drop) {
            a.drop.vy += 400 * u * DT;
            a.drop.y += a.drop.vy * DT;
            const rest = floor() - (a.cans + 1) * CAN * u;
            if (a.drop.y >= rest) {
              a.cans += 1;
              a.drop = null;
              a.next = a.t + .7;
              hop(8 * u, 22);
              me.face = "happy";
            }
          }
          return a.t < 14;
        },
        back(ctx, a, ox, oy) {
          const base = oy + floor();
          ctx.save();
          ctx.translate(ox + a.at, base);
          ctx.rotate(a.lean);
          for (let k = 0; k < a.cans; k += 1) can(ctx, 0, -(k + .5) * CAN * u, 0);
          ctx.restore();
          if (a.drop) can(ctx, ox + a.at, oy + a.drop.y + 5 * u, 0);
        },
      },
      tag: {
        weight: (p) => need(p, "energy") > 40 && !p.sick ? 1.3 : 0,
        start(a) {
          const side = me.x > 0 ? -1 : 1;
          a.th = {x: clamp(me.x + side * 60 * u, -range - 20 * u, range + 20 * u), y: 18 * u, vx: 0};
          a.catchAt = rand(3.5, 7);
          say("TAG!");
        },
        step(a) {
          const th = a.th, gap = th.x - me.x, edge = range + 20 * u;
          if (a.away) {
            th.y -= 160 * u * DT;
            th.x += th.vx * DT;
            gaze([clamp(gap / (40 * u), -1, 1), -1]);
            return th.y > ceiling() - 30 * u;
          }
          if (Math.abs(gap) < 34 * u) th.vx += Math.sign(gap || 1) * 900 * u * DT;
          th.vx *= .9;
          th.x += th.vx * DT;
          if (Math.abs(th.x) > edge) { th.x = Math.sign(th.x) * edge; th.vx = -th.vx * 1.6; }
          th.y = 16 * u + Math.sin(a.t * 6) * 6 * u;
          walkTo(th.x, 78);
          gaze([clamp(gap / (40 * u), -1, 1), .4]);
          if (a.t > a.catchAt && Math.abs(gap) < 18 * u) {
            hop(16 * u, 26);
            sound("cheer");
            sparkles(th.x, th.y, 10);
            say("GOT YOU!");
            me.face = "excited";
            return false;
          }
          if (a.t > 10) { a.away = true; say("IT GOT AWAY"); }
          return true;
        },
        front(ctx, a, ox, oy) {
          // A tiny Thargon: a dark petal ring with a green core.
          const x = ox + a.th.x, y = oy + a.th.y;
          ctx.save();
          ctx.translate(x, y);
          ctx.rotate(a.t * 3);
          ctx.fillStyle = "#1f2a26";
          for (let i = 0; i < 5; i += 1) {
            ctx.rotate(TAU / 5);
            ctx.beginPath();
            ctx.ellipse(0, -6 * u, 3 * u, 5 * u, 0, 0, TAU);
            ctx.fill();
          }
          ctx.fillStyle = "#54e39a";
          ctx.shadowColor = "#54e39a";
          ctx.shadowBlur = 6 * u;
          ctx.beginPath();
          ctx.arc(0, 0, 3 * u, 0, TAU);
          ctx.fill();
          ctx.restore();
        },
      },
      stars: {
        weight: (p) => need(p, "mood") > 30 ? 1 : 0,
        start(a) {
          const count = Math.round(rand(5, 7)), wide = Math.min(range * 2 + 40 * u, 110 * u);
          const high = ceiling() + 8 * u, low = Math.min(-56 * u, high + 30 * u);
          a.points = Array.from({length: count}, (_, i) => ({
            x: clamp(me.x + (i / (count - 1) - .5) * wide, -range - 30 * u, range + 30 * u), y: rand(high, low)}));
          a.lit = 0;
          a.next = .5;
        },
        step(a) {
          if (a.lit < a.points.length) {
            const point = a.points[a.lit];
            gaze([clamp((point.x - me.x) / (50 * u), -1, 1), -1]);
            if (a.t >= a.next) {
              sparkles(point.x, point.y, 4);
              a.lit += 1;
              a.next = a.t + .55;
              if (a.lit === a.points.length) { a.done = a.t; me.face = "happy"; say("A NEW CONSTELLATION"); }
            }
            return true;
          }
          return a.t - a.done < 2;
        },
        back(ctx, a, ox, oy, tone) {
          const fade = a.done ? clamp(1 - (a.t - a.done) / 2, 0, 1) : 1;
          ctx.strokeStyle = tone.glow;
          ctx.lineWidth = Math.max(1, u * .8);
          ctx.globalAlpha = .5 * fade;
          ctx.beginPath();
          a.points.slice(0, a.lit).forEach((point, i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, ox + point.x, oy + point.y));
          ctx.stroke();
          ctx.fillStyle = "#ffffff";
          a.points.forEach((point, i) => {
            ctx.globalAlpha = (i < a.lit ? 1 : .25) * fade;
            ctx.beginPath();
            ctx.arc(ox + point.x, oy + point.y, (i < a.lit ? 2.4 : 1.2) * u, 0, TAU);
            ctx.fill();
          });
          ctx.globalAlpha = 1;
        },
      },
    };

    function can(ctx, x, y, angle) {
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(angle);
      ctx.fillStyle = "#c9a227";
      ctx.fillRect(-8 * u, -6 * u, 16 * u, 12 * u);
      ctx.fillStyle = "#3a3324";
      ctx.fillRect(-8 * u, -1.3 * u, 16 * u, 2.6 * u);
      ctx.fillStyle = "rgba(255, 255, 255, .25)";
      ctx.fillRect(-8 * u, -6 * u, 16 * u, 1.6 * u);
      ctx.restore();
    }

    function night() {
      const hour = new Date().getHours();
      return hour >= 23 || hour < 6;
    }

    function bias(name, pet) {
      const traits = pet.traits || {};
      let k = 1;
      if (night()) k *= {doze: 4, yawn: 2.5, keepy: .4, tag: .4, bounce: .5, dance: .6}[name] ?? 1;
      const lean = (trait, acts, by) => { if (acts.includes(name)) k *= 1 + Math.min(2, traits[trait] || 0) * by; };
      lean("curious", ["stargaze", "chase", "toy", "holo", "look"], .6);
      lean("lazy", ["doze", "yawn"], 1);
      lean("brave", ["tag", "keepy"], .5);
      lean("greedy", ["rumble"], .8);
      lean("clingy", ["wave", "trick"], .8);
      // A long supercruise bores it into its games.
      if (pet.place === "supercruise" && ["keepy", "tower", "tag"].includes(name)) k *= 2;
      return k;
    }

    function choose(pet) {
      const hour = new Date().getHours();
      if (!me.greeted) {
        me.greeted = true;
        if (hour >= 5 && hour < 10) return "yawn";
      }
      const away = pet.place === "away";
      const options = Object.entries(ACTS).map(([name, act]) => [name, name === me.last ? 0 : act.weight(pet) * bias(name, pet)])
        .filter(([name, weight]) => weight > 0 && (!away || ["miss", "look", "doze", "yawn", "shiver", "hot"].includes(name)));
      let roll = Math.random() * options.reduce((sum, [, weight]) => sum + weight, 0);
      for (const [name, weight] of options) if ((roll -= weight) <= 0) return name;
      return "look";
    }

    // Asleep, it dreams of where you've been today.
    function dreaming(pet) {
      const dream = me.dream;
      if (dream.life > 0) { dream.life -= DT; return; }
      dream.next -= DT;
      if (dream.next > 0) return;
      dream.next = rand(8, 14);
      const places = pet.dreams || [];
      dream.text = places.length ? `${pick(places).toUpperCase()}…` : pick(["STARS…", "THE BLACK…", "HOME…"]);
      dream.life = 5;
      dream.max = 5;
    }

    // Where a toy rests on the floor of its pod.
    function toyX(pet, kind) {
      if (me.toyAt[kind] != null) return me.toyAt[kind];
      const toys = pet.toys || [], index = Math.max(0, toys.findIndex((toy) => toy.kind === kind));
      const spread = range + 18 * u;
      return toys.length < 2 ? spread * .7 : -spread + index * (spread * 2) / (toys.length - 1);
    }

    function drawToy(ctx, kind, x, y, t, tone) {
      ctx.save();
      ctx.translate(x, y);
      if (kind === "relic") {
        ctx.fillStyle = "#2a4a6e";
        ctx.shadowColor = "#6fc8ff";
        ctx.shadowBlur = 8 * u;
        ctx.beginPath();
        ctx.moveTo(0, -12 * u); ctx.lineTo(8 * u, 0); ctx.lineTo(-8 * u, 0); ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = "#9fe0ff";
        ctx.lineWidth = Math.max(1, u);
        ctx.beginPath();
        ctx.arc(0, -4.5 * u, 2.4 * u, 0, TAU);
        ctx.stroke();
      } else if (kind === "sensor") {
        ctx.fillStyle = "#1f2a26";
        for (let i = 0; i < 6; i += 1) {
          ctx.save(); ctx.translate(0, -6 * u); ctx.rotate(i / 6 * TAU);
          ctx.beginPath(); ctx.ellipse(0, -4 * u, 2 * u, 3.6 * u, 0, 0, TAU); ctx.fill();
          ctx.restore();
        }
        ctx.fillStyle = "#54e39a";
        ctx.shadowColor = "#54e39a";
        ctx.shadowBlur = (4 + Math.sin(t * 3) * 3) * u;
        ctx.beginPath(); ctx.arc(0, -6 * u, 2.4 * u, 0, TAU); ctx.fill();
      } else if (kind === "fragment") {
        ctx.fillStyle = "#e0a63c";
        ctx.shadowColor = "#ffd28a";
        ctx.shadowBlur = 5 * u;
        ctx.beginPath();
        [[-6, 0], [-4, -8], [1, -11], [6, -6], [5, 0]].forEach(([px, py], i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, px * u, py * u));
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = "rgba(255, 255, 255, .4)";
        ctx.fillRect(-2 * u, -8 * u, 2 * u, 3 * u);
      } else if (kind === "pebble") {
        ctx.fillStyle = "#7a8188";
        ctx.beginPath(); ctx.ellipse(0, -4 * u, 7 * u, 4.4 * u, 0, 0, TAU); ctx.fill();
        ctx.fillStyle = "#7fd66a";
        for (const [px, py] of [[-3, -6], [1, -7], [3, -5]]) { ctx.beginPath(); ctx.arc(px * u, py * u, 1.1 * u, 0, TAU); ctx.fill(); }
      } else if (kind === "beacon") {
        ctx.fillStyle = "#4a5361";
        ctx.fillRect(-1.2 * u, -12 * u, 2.4 * u, 12 * u);
        ctx.fillRect(-5 * u, -1.5 * u, 10 * u, 1.5 * u);
        ctx.fillStyle = Math.floor(t * 2) % 2 ? "#ffd166" : "#6b5a2a";
        ctx.shadowColor = "#ffd166";
        ctx.shadowBlur = Math.floor(t * 2) % 2 ? 8 * u : 0;
        ctx.beginPath(); ctx.arc(0, -13 * u, 2.2 * u, 0, TAU); ctx.fill();
      } else {
        // A model station: a little Coriolis, turning.
        ctx.translate(0, -7 * u);
        ctx.rotate(t * .5);
        ctx.fillStyle = "#b8c2cc";
        ctx.fillRect(-6 * u, -6 * u, 12 * u, 12 * u);
        ctx.fillStyle = "#1a2229";
        ctx.fillRect(-3 * u, -1 * u, 6 * u, 2 * u);
        ctx.strokeStyle = tone.line;
        ctx.lineWidth = Math.max(1, u * .6);
        ctx.strokeRect(-6 * u, -6 * u, 12 * u, 12 * u);
      }
      ctx.restore();
    }

    // What it wears (5.6.4), placed from its eyes.
    function outfit(ctx, pet, px, middle, drawn, rendered3d = false) {
      const [ey, er] = EYES[pet.species === "sample" ? pet.kind || "bacterium" : pet.species] || EYES.larva;
      const grown = pet.species === "sample" ? (pet.stage === "adult" ? 1.18 : pet.stage === "juvenile" ? 1 : .82) : 1;
      const k = drawn / 100 * grown, eyes = rendered3d ? middle - drawn * .14 : middle + ey * k, gap = er * 1.75 * k, w = gap * 2 + er * 3 * k;
      const [headY, neckY] = BODY[pet.species === "sample" ? pet.kind || "bacterium" : pet.species] || BODY.larva;
      const head = middle + headY * k, neck = middle + neckY * k;
      ctx.save();
      if (pet.outfit === "visor") {
        ctx.fillStyle = "rgba(90, 220, 255, .55)";
        ctx.strokeStyle = "#bff3ff";
        ctx.lineWidth = Math.max(1, k * .9);
        ctx.shadowColor = "#5ad8ff";
        ctx.shadowBlur = 6 * k;
        ctx.beginPath();
        ctx.roundRect(px - w / 2, eyes - er * 1.3 * k, w, er * 2.6 * k, er * k);
        ctx.fill();
        ctx.stroke();
      } else if (pet.outfit === "helmet") {
        const top = head;
        ctx.fillStyle = "#f0b93a";
        ctx.beginPath();
        ctx.ellipse(px, top + 6 * k, w * .62, 9 * k, 0, Math.PI, 0);
        ctx.fill();
        ctx.fillStyle = "#c98e1d";
        ctx.fillRect(px - w * .7, top + 5 * k, w * 1.4, 2.4 * k);
        ctx.fillStyle = "#fff6c8";
        ctx.shadowColor = "#fff6c8";
        ctx.shadowBlur = 8 * k;
        ctx.beginPath();
        ctx.arc(px, top, 2.6 * k, 0, Math.PI * 2);
        ctx.fill();
      } else if (pet.outfit === "charm") {
        const y = neck + 5 * k;
        ctx.strokeStyle = "#9fe0ff";
        ctx.lineWidth = Math.max(1, k * .6);
        ctx.beginPath();
        ctx.moveTo(px - 6 * k, y - 6 * k); ctx.lineTo(px, y - 2 * k); ctx.lineTo(px + 6 * k, y - 6 * k);
        ctx.stroke();
        ctx.fillStyle = "#3d7fb8";
        ctx.shadowColor = "#6fc8ff";
        ctx.shadowBlur = 8 * k;
        ctx.beginPath();
        ctx.moveTo(px, y - 2 * k); ctx.lineTo(px + 4 * k, y + 5 * k); ctx.lineTo(px - 4 * k, y + 5 * k);
        ctx.closePath();
        ctx.fill();
      } else if (pet.outfit === "scarf") {
        const y = neck - 2 * k;
        ctx.fillStyle = "#e0484f";
        ctx.beginPath();
        ctx.roundRect(px - w * .55, y, w * 1.1, 4.5 * k, 2 * k);
        ctx.fill();
        ctx.fillStyle = "#b8323a";
        ctx.save();
        ctx.translate(px + w * .32, y + 3 * k);
        ctx.rotate(.3 + Math.sin(me.clock * 3) * .12);
        ctx.fillRect(0, 0, 4 * k, 12 * k);
        ctx.restore();
      } else if (pet.outfit === "bowtie") {
        const y = neck;
        ctx.fillStyle = "#e0484f";
        for (const side of [-1, 1]) {
          ctx.beginPath();
          ctx.moveTo(px, y); ctx.lineTo(px + side * 7 * k, y - 4 * k); ctx.lineTo(px + side * 7 * k, y + 4 * k);
          ctx.closePath();
          ctx.fill();
        }
        ctx.fillStyle = "#8a1f25";
        ctx.beginPath();
        ctx.arc(px, y, 1.8 * k, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }

    function begin(name, pet) {
      me.act = {name, t: 0};
      me.last = name;
      me.face = "";
      ACTS[name].start?.(me.act, pet);
    }

    function settle() {
      if (me.act) ACTS[me.act.name].end?.(me.act);
      me.spin = 0;
      me.flair = 0;
      me.act = null;
      me.face = "";
      me.shut = false;
      me.shake = 0;
    }

    function physics() {
      me.vel += -me.squash * .22 - me.vel * .16;
      me.squash += me.vel;
      if (me.hop) {
        me.hop.t += 1;
        const k = me.hop.t / me.hop.n;
        me.lift = Math.sin(Math.min(1, k) * Math.PI) * me.hop.h;
        if (me.hop.t === 1) me.vel -= .35;
        if (k >= 1) { me.hop = null; me.lift = 0; me.vel += .5; }
      }
      if (me.held > 0) me.held -= DT;
      if (me.shades > 0) me.shades -= DT;
      me.clock += DT;
      me.look = [lerp(me.look[0], me.goal[0], .12), lerp(me.look[1], me.goal[1], .12)];
      for (const b of me.bits) {
        b.vy += b.g * DT;
        b.x += b.vx * DT;
        b.y += b.vy * DT;
        b.angle += b.spin * DT;
        if (b.floor && b.y > b.floor) { b.y = b.floor; b.vy *= -.3; b.vx *= .6; b.spin *= .5; }
        b.life -= DT;
      }
      me.bits = me.bits.filter((b) => b.life > 0);
      for (const word of me.words) { word.y -= 18 * u * DT; word.life -= DT; }
      me.words = me.words.filter((word) => word.life > 0);
    }

    function tick(pet, busy) {
      physics();
      const surface = Boolean(pet?.world) && SURFACE.includes(pet?.place);
      me.heavy = surface ? clamp(1 / Math.sqrt(Math.max(.05, Number(pet.world.gravity) || 1)), .55, 1.8) : 1;
      me.place = pet?.place || "space";
      if (me.place === "srv" && !busy && !pet.asleep) {
        me.bump -= DT;
        if (me.bump <= 0) { me.bump = rand(.5, 1.4); me.vel += rand(.2, .5); me.shake = rand(-1, 1) * u; }
        else if (me.bump < .3) me.shake *= .8;
      }
      // Its few words from the deck (5.6.4): a bubble, and a babble of chirps.
      const chat = pet?.chat;
      if (chat && chat.at !== me.chatSeen) {
        me.chatSeen = chat.at;
        if (Date.now() / 1000 - chat.at < 8 && !pet.asleep && !pet.dormant) {
          me.chat = {text: chat.text, life: 4.5, max: 4.5};
          sound("babble", chat.text);
        }
      }
      if (me.chat && (me.chat.life -= DT) <= 0) me.chat = null;
      const heard = pet?.watcher;
      if (heard && heard.at !== me.heardAt) {
        // Fresh words wait until it's free (not mid-cue or dancing); stale ones are let go.
        if (Date.now() / 1000 - heard.at >= 12 || busy || pet.asleep || pet.dormant || pet.stage === "egg") me.heardAt = heard.at;
        else if (!Object.values(CUE_ACTS).includes(me.act?.name) && me.act?.name !== "dance") {
          me.heardAt = heard.at;
          settle();
          begin(heard.weary ? "company" : "listen", pet);
        }
      }
      const cue = pet?.cue;
      if (cue && cue.at !== me.cueSeen) {
        me.cueSeen = cue.at;
        const act = CUE_ACTS[cue.kind];
        if (act && Date.now() / 1000 - cue.at < 25 && !busy && !pet.asleep && !pet.dormant && pet.stage !== "egg") {
          settle();
          begin(act, pet);
        }
      }
      // Your music starting gets it up and dancing (unless it's busy acting out a cue).
      const music = Boolean(pet?.music);
      if (!music) me.music = false;
      else if (!me.music && !busy && !pet.asleep && !pet.dormant && pet.stage !== "egg"
               && !Object.values(CUE_ACTS).includes(me.act?.name)) {
        me.music = true;
        settle();
        begin("dance", pet);
      }
      // Between sets it keeps the beat: a small bob on each one it hears. A big
      // swell after a quiet while can still pull it back into a dance.
      const ear = me.ear;
      if (music && me.clock - ear.heard < 1.5 && !busy && !pet.asleep && !pet.dormant && pet.stage !== "egg" && me.act?.name !== "dance") {
        if (ear.beats !== me.bobbed) { me.bobbed = ear.beats; me.vel += .1 + ear.bass * .1; }
        if (me.clock - me.danced > 90 && ear.energy > .55 && ear.energy > ear.feel.energy + .2
            && !Object.values(CUE_ACTS).includes(me.act?.name)) {
          settle();
          begin("dance", pet);
        }
      }
      if (pet?.asleep && !pet.dormant) dreaming(pet);
      if (busy || !pet || pet.dormant || pet.asleep) {
        if (me.act) settle();
        if (busy) me.x = lerp(me.x, 0, .08);
        me.tilt = lerp(me.tilt, 0, .1);
        return;
      }
      me.dream.life = 0;
      if (pet.stage === "egg") {
        // An egg only rocks, and more often near hatching.
        if (me.act) settle();
        me.eggNext -= DT;
        if (me.eggNext <= 0) { me.eggWobble = 1; me.eggNext = pet.hatch_minutes > 0 && pet.hatch_minutes < 5 ? rand(1, 2.5) : rand(4, 9); }
        me.eggWobble = Math.max(0, me.eggWobble - DT * 1.2);
        me.tilt = Math.sin(me.eggWobble * 22) * .12 * me.eggWobble;
        return;
      }
      if (!me.act) {
        me.tilt = lerp(me.tilt, 0, .1);
        me.rest -= DT;
        if (me.rest <= 0) begin(choose(pet), pet);
        return;
      }
      me.act.t += DT;
      if (ACTS[me.act.name].step(me.act, pet) === false) {
        settle();
        me.rest = rand(2, 5);
      }
    }

    return {
      // dt in seconds; busy while the page has the pet doing something else.
      step(dt, pet, {busy = false} = {}) {
        me.spare = Math.min(me.spare + dt, .25);
        while (me.spare >= DT) { me.spare -= DT; tick(pet, busy); }
      },
      resize(next) {
        if (next.size) { size = next.size; u = size / 100; }
        if (next.range != null) range = next.range;
        if (next.top != null) top = next.top;
        if (next.ink) ink = next.ink;
        if (next.text) text = next.text;
        if (next.speech != null) speech = next.speech;
        me.x = clamp(me.x, -range, range);
      },
      // What the music sounds like right now (32 bands, 0-255), a few times a second.
      hear(bands, playing = true) {
        const ear = me.ear;
        if (!Array.isArray(bands) || !bands.length || !playing) { ear.energy = ear.bass = ear.treble = 0; return; }
        const mean = (from, to) => bands.slice(from, to).reduce((sum, value) => sum + (Number(value) || 0), 0) / Math.max(1, to - from) / 255;
        ear.energy = mean(0, bands.length);
        ear.bass = mean(0, 4);
        ear.treble = mean(Math.floor(bands.length * .6), bands.length);
        // The feel of the music, smoothed over a few seconds (it picks the dance);
        // after a silence it starts from what it hears now.
        const fresh = me.clock - ear.heard > 1.5;
        for (const key of ["energy", "bass", "treble"]) ear.feel[key] = fresh ? ear[key] : ear.feel[key] + (ear[key] - ear.feel[key]) * .1;
        ear.heard = me.clock;
        // A beat: the bass jumping above its recent level.
        if (ear.bass > .22 && ear.bass > ear.avg * 1.22 && me.clock - ear.lastBeat > .26) {
          const gap = me.clock - ear.lastBeat;
          if (gap < 1.2) ear.gaps = [...ear.gaps, gap].slice(-8);
          ear.lastBeat = me.clock;
          ear.beats += 1;
          const sorted = [...ear.gaps].sort((x, y) => x - y);
          if (sorted.length >= 3) ear.period = clamp(sorted[Math.floor(sorted.length / 2)], .3, 1);
        }
        ear.avg += (ear.bass - ear.avg) * .3;
      },
      hop(height, frames) { hop(height, frames); },
      kick(amount) { me.vel += amount; },
      // Where the page wants it to look (the mouse, a minigame), for a moment.
      lookAt(goal, seconds = .4) { me.goal = goal; me.held = seconds; },
      setLook(goal) { me.goal = goal; me.look = goal; me.held = 1; },
      play(name, pet) { if (ACTS[name] && pet) { settle(); begin(name, pet); } },
      acts: Object.keys(ACTS),
      get x() { return me.x; },
      get lift() { return me.lift; },
      get act() { return me.act?.name || ""; },
      state: () => ({act: me.act?.name || "", x: Math.round(me.x), bits: me.bits.length, shades: me.shades > 0, heavy: me.heavy,
        chat: me.chat ? me.chat.text : "", text, dance: me.act?.name === "dance" ? me.act.style : "",
        dream: me.dream.life > 0 ? me.dream.text : ""}),

      // The pet itself, where it is now and how it looks.
      drawPet(ctx, pet, {x, y, size: drawn = size, t, aura = true, threeOnly = false} = {}) {
        if (!pet) return;
        const shown = me.shut && !pet.asleep ? {...pet, asleep: true, eyesShut: true} : me.face && !pet.reaction ? {...pet, reaction: me.face} : pet;
        const px = x + me.x + me.shake, feet = y + 44 * drawn / 100, middle = y - me.lift;
        ctx.save();
        if (me.tilt || me.flair) { ctx.translate(px, feet); ctx.rotate(me.tilt + me.flair); ctx.translate(-px, -feet); }
        if (me.spin) { ctx.translate(px, middle); ctx.rotate(me.spin); ctx.translate(-px, -middle); }
        const current = me.act || {};
        const relative = (value) => Number(value || 0) - me.x - me.shake;
        const activity = {name: current.name || "idle", t: current.t || 0, style: current.style || "", trick: current.trick || ""};
        if (current.ball) activity.ball = {...current.ball, x: relative(current.ball.x)};
        if (current.toy) activity.toy = {kind: current.toy.kind, x: relative(current.x ?? toyX(pet, current.toy.kind)), vx: current.vx || 0, pushes: current.pushes || 0};
        if (current.tower) activity.tower = current.tower;
        if (current.name === "tower") activity.tower = {x: relative(current.at), cans: current.cans || 0, lean: current.lean || 0,
          drop: current.drop ? {y: current.drop.y + 5 * u} : null, fallen: Boolean(current.fell)};
        if (current.th) activity.thargon = {x: relative(current.th.x), y: current.th.y, spin: current.t * 3, fleeing: Boolean(current.away)};
        if (current.mote) activity.mote = {x: relative(current.mote.x), y: current.mote.y};
        if (current.points) activity.stars = {points: current.points.map((point) => ({x: relative(point.x), y: point.y})), lit: current.lit || 0,
          fade: current.done ? clamp(1 - (current.t - current.done) / 2, 0, 1) : 1};
        if (current.star) activity.star = {x: relative(current.star.x), y: current.star.y};
        if (current.orb) activity.orb = {x: relative(current.orb.x), y: current.orb.y};
        const toys = pet.stage === "egg" ? [] : (pet.toys || []).map((toy) => ({kind: toy.kind,
          x: relative(current.name === "toy" && current.toy?.kind === toy.kind ? current.x : toyX(pet, toy.kind)), y: 44 * drawn / 100}));
        const rendered3d = window.Hatchling3D?.draw(ctx, shown, {
          x: px, y, size: drawn, t, look: me.look, squash: me.squash, lift: me.lift, aura,
          act: me.act?.name || "", dance: me.act?.style || "",
          activity, toys,
        });
        if (!rendered3d && !threeOnly) window.HatchlingArt.draw(ctx, shown, {x: px, y, size: drawn, t, look: me.look, squash: me.squash, lift: me.lift, aura});
        if (pet.outfit && pet.stage !== "egg") outfit(ctx, pet, px, middle, drawn, rendered3d);
        if (me.shades > 0 && !pet.asleep && pet.stage !== "egg") {
          // Sunglasses, while it scoops fuel from a star.
          const [ey, er] = EYES[pet.species === "sample" ? pet.kind || "bacterium" : pet.species] || EYES.larva;
          const k = drawn / 100, grown = pet.species === "sample" ? (pet.stage === "adult" ? 1.18 : pet.stage === "juvenile" ? 1 : .82) : 1;
          const gap = er * 1.75 * k * grown, lens = er * 1.25 * k * grown;
          const cy = rendered3d ? middle - drawn * .14 : middle + ey * k * grown;
          ctx.globalAlpha = Math.min(1, me.shades);
          ctx.fillStyle = "#0b0f14";
          ctx.strokeStyle = "#0b0f14";
          ctx.lineWidth = Math.max(1, lens * .35);
          for (const dx of [-gap, gap]) { ctx.beginPath(); ctx.ellipse(px + dx, cy, lens * 1.25, lens, 0, 0, TAU); ctx.fill(); }
          ctx.beginPath(); ctx.moveTo(px - gap + lens, cy); ctx.lineTo(px + gap - lens, cy); ctx.stroke();
          ctx.fillStyle = "rgba(255, 255, 255, .45)";
          for (const dx of [-gap, gap]) ctx.fillRect(px + dx - lens * .7, cy - lens * .6, lens * .5, lens * .3);
          ctx.globalAlpha = 1;
        }
        ctx.restore();
      },
      // What it's playing with, behind it and in front of it.
      back(ctx, pet, ox, oy) {
        if (!pet) return;
        const tone = window.HatchlingArt.tones(pet);
        if (pet.place === "supercruise" && !pet.dormant) {
          // Stars streaming past in supercruise.
          ctx.strokeStyle = tone.glow;
          ctx.lineWidth = Math.max(1, u * .7);
          const wide = range + 70 * u;
          for (let i = 0; i < 14; i += 1) {
            const k = (me.clock * (.25 + (i % 4) * .08) + i * .618) % 1;
            const x = ox + wide - k * wide * 2, y = oy + ceiling() + ((i * 37) % 100) / 100 * (floor() - ceiling() - 10 * u);
            ctx.globalAlpha = .12 + (i % 3) * .06;
            ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + (8 + (i % 5) * 4) * u, y); ctx.stroke();
          }
          ctx.globalAlpha = 1;
        } else if (pet.place === "srv" && !pet.dormant) {
          // The ground running under the SRV.
          ctx.strokeStyle = tone.line;
          ctx.lineWidth = Math.max(1, u);
          const wide = range + 70 * u;
          for (let i = 0; i < 9; i += 1) {
            const k = (me.clock * .6 + i / 9) % 1, x = ox + wide - k * wide * 2;
            ctx.globalAlpha = .25;
            ctx.beginPath(); ctx.moveTo(x, oy + floor() + 2 * u); ctx.lineTo(x + 10 * u, oy + floor() + 2 * u); ctx.stroke();
          }
          ctx.globalAlpha = 1;
        } else if (pet.place === "docked" && !pet.dormant) {
          // The station's lights, through the glass.
          ctx.fillStyle = tone.glow;
          for (let i = 0; i < 5; i += 1) {
            ctx.globalAlpha = .05 + .03 * Math.sin(me.clock * 1.5 + i);
            ctx.fillRect(ox + (-2 + i) * 34 * u - 3 * u, oy + ceiling(), 6 * u, floor() - ceiling());
          }
          ctx.globalAlpha = 1;
        }
        if (pet.stage !== "egg") {
          if (!window.Hatchling3D) {
            const playing = me.act?.name === "toy" ? me.act.toy.kind : "";
            for (const toy of pet.toys || []) {
              const x = playing === toy.kind ? me.act.x : toyX(pet, toy.kind);
              drawToy(ctx, toy.kind, ox + x, oy + floor(), me.clock, tone);
            }
          }
        }
        if (me.act && (!window.Hatchling3D || !THREE_PROP_ACTS.has(me.act.name))) ACTS[me.act.name].back?.(ctx, me.act, ox, oy, tone);
      },
      front(ctx, pet, ox, oy) {
        if (!pet) return;
        const tone = window.HatchlingArt.tones(pet);
        if (me.act && (!window.Hatchling3D || !THREE_PROP_ACTS.has(me.act.name))) ACTS[me.act.name].front?.(ctx, me.act, ox, oy, tone);
        for (const b of me.bits) {
          const k = b.life / b.max, x = ox + b.x, y = oy + b.y;
          ctx.globalAlpha = clamp(k * 1.5, 0, 1);
          if (b.kind === "spark") window.HatchlingArt.sparkle(ctx, x, y, b.size * (.5 + k), tone.glow);
          else if (b.kind === "heart") window.HatchlingArt.heart(ctx, x, y, b.size, "#ff6b9a");
          else if (b.kind === "can") can(ctx, x, y, b.angle);
          else if (b.kind === "note" || b.kind === "z") {
            ctx.fillStyle = tone.glow;
            ctx.font = `700 ${Math.max(ink, 9 * u) * text}px Bahnschrift, "Segoe UI", sans-serif`;
            ctx.textAlign = "center";
            ctx.fillText(b.kind === "note" ? "♪" : "z", x, y);
          } else if (b.kind === "confetti") {
            ctx.save();
            ctx.translate(x, y);
            ctx.rotate(b.angle);
            ctx.fillStyle = b.colour;
            ctx.fillRect(-b.size / 2, -b.size / 4, b.size, b.size / 2);
            ctx.restore();
          } else if (b.kind === "coin") {
            ctx.fillStyle = "#ffd166";
            ctx.strokeStyle = "#b8862a";
            ctx.lineWidth = Math.max(1, u * .5);
            ctx.beginPath();
            ctx.ellipse(x, y, 3 * u * Math.abs(Math.cos(b.angle)) + .5, 3 * u, 0, 0, TAU);
            ctx.fill();
            ctx.stroke();
          } else if (b.kind === "frost") {
            window.HatchlingArt.sparkle(ctx, x, y, 2 * u, "#cfe8ff");
          } else if (b.kind === "dust") {
            ctx.fillStyle = "#9aa6b0";
            ctx.beginPath();
            ctx.arc(x, y, 1.6 * u * (2 - k), 0, TAU);
            ctx.fill();
          }
          else if (b.kind === "ring") {
            ctx.strokeStyle = tone.line;
            ctx.lineWidth = Math.max(1, u);
            ctx.globalAlpha = k * .7;
            ctx.beginPath();
            ctx.arc(x, y, b.size + (1 - k) * 40 * u, 0, TAU);
            ctx.stroke();
          } else if (b.kind === "line") {
            ctx.strokeStyle = tone.line;
            ctx.lineWidth = Math.max(1, u * .9);
            ctx.beginPath();
            ctx.arc(x, y, 5 * u, -.6, .6);
            ctx.stroke();
          } else {
            ctx.fillStyle = b.kind === "drop" ? "#8fc8ff" : tone.vein;
            ctx.beginPath();
            ctx.arc(x, y, (b.kind === "spore" ? 1.4 : 1.2) * u + .5, 0, TAU);
            ctx.fill();
          }
        }
        ctx.globalAlpha = 1;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        if (speech && me.dream.life > 0 && pet.asleep && !pet.dormant) {
          // A dream, in a thought bubble.
          const fade = clamp(Math.min(me.dream.life, me.dream.max - me.dream.life), 0, 1);
          const size = Math.max(ink * .9, 6.5 * u) * text;
          ctx.font = `700 ${size}px Bahnschrift, "Segoe UI", sans-serif`;
          const wide = ctx.measureText(me.dream.text).width + size * 1.6;
          const bx = clamp(ox + me.x + 30 * u, ox - range - 40 * u + wide / 2, ox + range + 40 * u - wide / 2);
          const by = oy + Math.max(ceiling() + size, -54 * u);
          ctx.globalAlpha = fade * .85;
          ctx.fillStyle = "#0d1820";
          ctx.strokeStyle = tone.line;
          ctx.lineWidth = Math.max(1, u * .6);
          ctx.beginPath();
          ctx.ellipse(bx, by, wide / 2, size * 1.1, 0, 0, TAU);
          ctx.fill();
          ctx.stroke();
          for (const [dx, dy, r] of [[-wide * .3, size * 1.6, size * .3], [-wide * .38, size * 2.3, size * .18]]) {
            ctx.beginPath(); ctx.arc(bx + dx, by + dy, r, 0, TAU); ctx.fill(); ctx.stroke();
          }
          ctx.globalAlpha = fade;
          ctx.fillStyle = tone.glow;
          ctx.fillText(me.dream.text, bx, by);
          ctx.globalAlpha = 1;
        }
        if (speech && me.chat && !pet.asleep) {
          // Its own words, in a bubble with a tail (not the Watcher's panel).
          const fade = clamp(Math.min(me.chat.life * 2, (me.chat.max - me.chat.life) * 4), 0, 1);
          const size = Math.max(ink * .95, 7 * u) * text;
          ctx.font = `600 ${size}px "Segoe UI", sans-serif`;
          const wide = ctx.measureText(me.chat.text).width + size * 1.4, high = size * 1.9;
          const edge = range + 40 * u;
          const bx = clamp(ox + me.x, ox - edge + wide / 2, ox + edge - wide / 2);
          const by = oy + Math.max(ceiling() + high / 2 + 2, -62 * u - me.lift);
          ctx.globalAlpha = fade;
          ctx.fillStyle = "rgba(246, 250, 252, .95)";
          ctx.beginPath();
          ctx.roundRect(bx - wide / 2, by - high / 2, wide, high, high / 2);
          ctx.fill();
          ctx.beginPath();
          ctx.moveTo(ox + me.x - 3 * u, by + high / 2 - 1);
          ctx.lineTo(ox + me.x + 3 * u, by + high / 2 - 1);
          ctx.lineTo(ox + me.x, by + high / 2 + 5 * u);
          ctx.fill();
          ctx.fillStyle = "#14202a";
          ctx.fillText(me.chat.text, bx, by + 1);
          ctx.globalAlpha = 1;
        }
        for (const word of speech ? me.words : []) {
          ctx.globalAlpha = clamp(word.life * 2, 0, 1);
          ctx.font = `700 ${Math.max(word.small ? ink * .85 : ink, (word.small ? 6 : 7.5) * u) * text}px Bahnschrift, "Segoe UI", sans-serif`;
          ctx.fillStyle = tone.glow;
          ctx.shadowColor = "#000000";
          ctx.shadowBlur = 4;
          ctx.fillText(word.text, ox + clamp(word.x, -range - 10 * u, range + 10 * u), oy + word.y);
        }
        ctx.shadowBlur = 0;
        ctx.globalAlpha = 1;
      },
    };
  }

  window.HatchlingLife = {create};
})();
