// The Hatchling's looks (5.6.3), shared by its game page and its overlay:
// every species at every stage, its adult forms, and its face (happy,
// asleep, ill, frightened, hibernating). Drawn to a canvas in a 100-unit
// box around (x, y). The game page also passes where to look (the mouse)
// and a squash for hops and pats.
(() => {
  "use strict";

  const TONES = {
    larva: {light: "#2fd69a", dark: "#06261c", line: "#6bffc8", glow: "#9dffd2", eye: "#eafff6", iris: "#0e6b4b", vein: "#b6ffe0"},
    bot: {light: "#e9edf2", dark: "#4a5361", line: "#ffb35c", glow: "#ffd28a", eye: "#7fe8ff", iris: "#0c3a4a", vein: "#ffcf8f"},
    sample: {light: "#c7f06a", dark: "#203a10", line: "#dcff8a", glow: "#f0ffb0", eye: "#fffbe6", iris: "#3b4a12", vein: "#f6ffc8"},
  };
  // Adult forms change the colours a little.
  const FORM_TONES = {
    "larva:explored": {light: "#3fc8ff", line: "#8fe4ff", glow: "#c6f2ff"}, "larva:scarred": {light: "#2aa77a", line: "#ffa45c"},
    "larva:neglected": {light: "#6c8a80", dark: "#1a2420", line: "#93aba2", glow: "#b4c6bf"},
    "larva:rare": {light: "#b77bff", dark: "#1d0a3a", line: "#dcb8ff", glow: "#f0deff", vein: "#f6e8ff"},
    "bot:explored": {line: "#6fd6ff", glow: "#b8ecff"}, "bot:scarred": {light: "#b8b2a8", dark: "#3a362f", line: "#d8d0c4"},
    "bot:neglected": {light: "#b98a62", dark: "#3f2818", line: "#c0703a"}, "bot:rare": {light: "#ffe7a0", dark: "#7a5a10", line: "#ffd54a", glow: "#fff2b8"},
    "sample:explored": {light: "#ff8adf", dark: "#3a0f30", line: "#ffb8ec", glow: "#ffe0f6"}, "sample:scarred": {light: "#9a6a3a", dark: "#2a1608", line: "#ff9a4a"},
    "sample:neglected": {light: "#a89a64", dark: "#2a2616", line: "#bdb08a", glow: "#d8cfa8"},
    "sample:rare": {light: "#6affe6", dark: "#06322c", line: "#b0fff4", glow: "#e0fffb"},
  };

  function mix(a, b, k) {
    const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16);
    const ch = (shift) => Math.round(((pa >> shift) & 255) * (1 - k) + ((pb >> shift) & 255) * k);
    return `#${[16, 8, 0].map((shift) => ch(shift).toString(16).padStart(2, "0")).join("")}`;
  }

  function tones(pet) {
    const base = {...(TONES[pet.species] || TONES.larva), ...(FORM_TONES[`${pet.species}:${pet.form}`] || {})};
    if (pet.dormant) return {...base, light: "#7d93a8", dark: "#141c28", line: "#a9c3dc", glow: "#d6e8f8", vein: "#e4f0ff"};
    if (pet.sick) return {...base, light: mix(base.light, "#a9b84a", .45), glow: "#d6e27a"};
    return base;
  }

  function glowStroke(ctx, colour, width, blur) {
    ctx.strokeStyle = colour;
    ctx.lineWidth = width;
    ctx.shadowColor = colour;
    ctx.shadowBlur = blur;
    ctx.stroke();
    ctx.shadowBlur = 0;
  }

  function bodyFill(ctx, tone, r, cx = 0, cy = 0) {
    const grad = ctx.createRadialGradient(cx - r * .35, cy - r * .45, r * .08, cx, cy, r * 1.1);
    grad.addColorStop(0, mix(tone.light, "#ffffff", .25));
    grad.addColorStop(.45, tone.light);
    grad.addColorStop(1, tone.dark);
    return grad;
  }

  // ---- The face. ----
  const HAPPY = ["happy", "treat", "excited", "hatched", "grown", "revived", "cured", "clean", "petted", "play"];
  const AFRAID = ["scared", "distraught", "angry"];

  function face(ctx, pet, x, y, r, t, tone, look, lcd = false) {
    const reaction = pet.reaction || "";
    const mood = pet.mood_word || "";
    ctx.save();
    ctx.translate(x, y);
    const gap = r * 1.75;
    const blink = !pet.asleep && (Math.sin(t * 1.3 + 1) > .985 || Math.sin(t * .37) > .997);
    const [lx, ly] = look || [0, 0];
    const ink = lcd ? tone.eye : "#0b1712";
    const line = (width) => { ctx.lineWidth = width; ctx.lineCap = "round"; ctx.strokeStyle = ink; };
    const both = (draw) => [-gap, gap].forEach((dx) => { ctx.save(); ctx.translate(dx, 0); draw(); ctx.restore(); });

    if (pet.dormant) {
      both(() => { line(r * .3); ctx.beginPath(); ctx.moveTo(-r * .8, -r * .6); ctx.lineTo(r * .8, r * .6); ctx.moveTo(r * .8, -r * .6); ctx.lineTo(-r * .8, r * .6); ctx.stroke(); });
    } else if (pet.asleep || blink) {
      both(() => { line(r * .28); ctx.beginPath(); ctx.arc(0, -r * .1, r * .85, .15 * Math.PI, .85 * Math.PI); ctx.stroke(); });
    } else if (pet.sick) {
      both(() => {
        line(r * .22);
        ctx.beginPath();
        for (let a = 0; a < Math.PI * 4; a += .35) ctx.lineTo(Math.cos(a + t * 3) * a / 12 * r, Math.sin(a + t * 3) * a / 12 * r);
        ctx.stroke();
      });
    } else if (HAPPY.includes(reaction) || (mood === "HAPPY" && Math.sin(t * .5) > .3)) {
      both(() => { line(r * .32); ctx.beginPath(); ctx.arc(0, r * .45, r * .9, 1.12 * Math.PI, 1.88 * Math.PI); ctx.stroke(); });
    } else {
      // Big round eyes with pupils that follow you.
      const wide = AFRAID.includes(reaction) || reaction === "amazed" ? 1.18 : 1;
      const pupil = AFRAID.includes(reaction) ? .38 : .62;
      both(() => {
        ctx.beginPath();
        ctx.ellipse(0, 0, r * 1.05 * wide, r * 1.2 * wide, 0, 0, Math.PI * 2);
        ctx.fillStyle = lcd ? "rgba(127, 232, 255, .12)" : tone.eye;
        ctx.fill();
        const px = lx * r * .38, py = ly * r * .38;
        ctx.beginPath();
        ctx.arc(px, py, r * pupil, 0, Math.PI * 2);
        ctx.fillStyle = lcd ? tone.eye : tone.iris;
        if (lcd) { ctx.shadowColor = tone.eye; ctx.shadowBlur = r * 2; }
        ctx.fill();
        ctx.shadowBlur = 0;
        if (!lcd) {
          ctx.beginPath(); ctx.arc(px, py, r * pupil * .55, 0, Math.PI * 2); ctx.fillStyle = "#050a08"; ctx.fill();
        }
        ctx.fillStyle = "#ffffff";
        ctx.beginPath(); ctx.arc(px - r * .25, py - r * .32, r * .24, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(px + r * .22, py + r * .2, r * .1, 0, Math.PI * 2); ctx.fill();
      });
      if (reaction === "angry") {
        line(r * .3);
        ctx.beginPath(); ctx.moveTo(-gap - r, -r * 1.7); ctx.lineTo(-gap + r * .9, -r * 1.05); ctx.moveTo(gap + r, -r * 1.7); ctx.lineTo(gap - r * .9, -r * 1.05); ctx.stroke();
      }
    }
    // Cheeks when it's pleased.
    if (!lcd && !pet.dormant && (HAPPY.includes(reaction) || ["HAPPY", "CONTENT"].includes(mood))) {
      ctx.fillStyle = "rgba(255, 120, 150, .35)";
      for (const side of [-1, 1]) { ctx.beginPath(); ctx.ellipse(side * gap * 1.45, r * 1.4, r * .7, r * .4, 0, 0, Math.PI * 2); ctx.fill(); }
    }
    // The mouth.
    const sad = ["SAD", "MISERABLE"].includes(mood) || ["distraught", "bored", "grumpy"].includes(reaction);
    const glad = ["HAPPY", "CONTENT"].includes(mood) || HAPPY.includes(reaction);
    const inside = lcd ? tone.eye : "#3a0d14";
    const my = r * 2.1;
    line(r * .26);
    ctx.beginPath();
    if (pet.asleep || pet.dormant) { ctx.moveTo(-r * .45, my); ctx.quadraticCurveTo(0, my + r * .25, r * .45, my); ctx.stroke(); }
    else if (["eat", "treat"].includes(reaction)) {
      ctx.ellipse(0, my, r * .55, r * .5 * (1 + Math.abs(Math.sin(t * 10)) * .7), 0, 0, Math.PI * 2);
      ctx.fillStyle = inside; ctx.fill();
    } else if (AFRAID.includes(reaction) || reaction === "amazed") {
      ctx.ellipse(0, my + r * .1, r * .5, r * .65, 0, 0, Math.PI * 2);
      ctx.fillStyle = inside; ctx.fill();
    } else if (sad) { ctx.arc(0, my + r * .9, r * .95, 1.22 * Math.PI, 1.78 * Math.PI); ctx.stroke(); }
    else if (glad) {
      ctx.moveTo(-r, my - r * .3);
      ctx.quadraticCurveTo(0, my + r * 1.2, r, my - r * .3);
      ctx.closePath();
      ctx.fillStyle = lcd ? tone.eye : "#4a1220"; ctx.fill();
      if (!lcd) { ctx.beginPath(); ctx.ellipse(0, my + r * .35, r * .4, r * .2, 0, 0, Math.PI * 2); ctx.fillStyle = "#ff7a8a"; ctx.fill(); }
    } else { ctx.moveTo(-r * .55, my); ctx.quadraticCurveTo(0, my + r * .3, r * .55, my); ctx.stroke(); }
    ctx.restore();
  }

  // ---- The egg. ----
  function egg(ctx, pet, t, tone) {
    const soon = pet.hatch_minutes !== undefined && pet.hatch_minutes < 6;
    const wobble = soon ? Math.sin(t * 16) * .09 * (Math.sin(t * 1.7) > 0 ? 1 : .2) : Math.sin(t * 1.4) * .025;
    ctx.save();
    ctx.rotate(wobble);
    const shell = ctx.createRadialGradient(-8, -12, 3, 0, 4, 36);
    shell.addColorStop(0, mix(tone.light, "#ffffff", .5));
    shell.addColorStop(.5, tone.light);
    shell.addColorStop(1, tone.dark);
    ctx.beginPath();
    ctx.moveTo(0, -34);
    ctx.bezierCurveTo(22, -34, 28, 6, 26, 14);
    ctx.bezierCurveTo(24, 32, 10, 38, 0, 38);
    ctx.bezierCurveTo(-10, 38, -24, 32, -26, 14);
    ctx.bezierCurveTo(-28, 6, -22, -34, 0, -34);
    ctx.closePath();
    ctx.fillStyle = shell;
    ctx.shadowColor = tone.glow;
    ctx.shadowBlur = 24 + Math.sin(t * 2) * 8;
    ctx.fill();
    ctx.shadowBlur = 0;
    glowStroke(ctx, tone.line, 1.6, 6);
    ctx.save();
    ctx.clip();
    if (pet.species === "larva") {
      ctx.strokeStyle = tone.vein;
      ctx.globalAlpha = .55 + Math.sin(t * 2.4) * .25;
      ctx.lineWidth = 1.3;
      for (let i = 0; i < 6; i += 1) {
        const a = i / 6 * Math.PI * 2;
        ctx.beginPath(); ctx.moveTo(0, 6); ctx.quadraticCurveTo(Math.cos(a) * 16, 6 + Math.sin(a) * 6, Math.cos(a) * 30, 6 + Math.sin(a) * 26); ctx.stroke();
      }
      ctx.globalAlpha = 1;
    } else if (pet.species === "bot") {
      ctx.fillStyle = "rgba(0,0,0,.25)";
      ctx.fillRect(-30, 2, 60, 5);
      for (const x of [-14, 0, 14]) {
        ctx.beginPath(); ctx.arc(x, 4.5, 2, 0, Math.PI * 2);
        ctx.fillStyle = Math.floor(t * 3 + x) % 3 ? tone.glow : "#ff6b70"; ctx.fill();
      }
    } else {
      ctx.fillStyle = "rgba(255,255,255,.18)";
      ctx.fillRect(-14, -8, 28, 36);
      for (let i = 0; i < 6; i += 1) {
        ctx.beginPath();
        ctx.arc(-8 + (i * 7) % 18, 26 - ((t * 9 + i * 13) % 34), 1.6 + i % 2, 0, Math.PI * 2);
        ctx.fillStyle = tone.glow; ctx.fill();
      }
    }
    ctx.fillStyle = "rgba(255,255,255,.28)";
    ctx.beginPath(); ctx.ellipse(-10, -16, 5, 10, -.4, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
    // Cracks of light as it gets close.
    if (soon) {
      ctx.beginPath();
      ctx.moveTo(-18, -4); ctx.lineTo(-8, 2); ctx.lineTo(-2, -6); ctx.lineTo(6, 3); ctx.lineTo(14, -3); ctx.lineTo(20, 2);
      glowStroke(ctx, "#ffffff", 1.4, 14);
    }
    ctx.restore();
  }

  // ---- The species. ----
  function larva(ctx, pet, t, tone, look) {
    const grown = pet.stage === "adult" ? 1.2 : pet.stage === "juvenile" ? 1.03 : .84;
    const still = pet.asleep || pet.dormant;
    ctx.save();
    ctx.scale(grown, grown);
    // Tentacle legs, curling.
    const arms = pet.stage === "adult" ? 6 : pet.stage === "juvenile" ? 4 : 3;
    for (let i = 0; i < arms; i += 1) {
      const a = Math.PI * (.12 + .76 * i / Math.max(1, arms - 1));
      const sway = still ? 0 : Math.sin(t * 3 + i * 1.3) * 5;
      const ex = Math.cos(a) * 40 + sway, ey = Math.sin(a) * 34 + 8;
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * 18, Math.sin(a) * 14 + 6);
      ctx.quadraticCurveTo(Math.cos(a) * 34 - sway, Math.sin(a) * 18 + 10, ex, ey);
      ctx.lineCap = "round";
      ctx.strokeStyle = tone.dark;
      ctx.lineWidth = 7;
      ctx.stroke();
      glowStroke(ctx, tone.light, 3.4, 6);
      ctx.beginPath(); ctx.arc(ex, ey, 2.6, 0, Math.PI * 2); ctx.fillStyle = tone.glow; ctx.fill();
    }
    // The body: a soft hexagon.
    const r = 28;
    ctx.beginPath();
    for (let i = 0; i <= 6; i += 1) {
      const a = i / 6 * Math.PI * 2 - Math.PI / 2;
      const rr = r * (1 + (pet.dormant ? 0 : Math.sin(t * 2 + i) * .025));
      if (i === 0) ctx.moveTo(Math.cos(a) * rr, Math.sin(a) * rr);
      else ctx.quadraticCurveTo(Math.cos(a - Math.PI / 6) * rr * 1.12, Math.sin(a - Math.PI / 6) * rr * 1.12, Math.cos(a) * rr, Math.sin(a) * rr);
    }
    ctx.closePath();
    ctx.fillStyle = bodyFill(ctx, tone, r);
    ctx.shadowColor = tone.glow;
    ctx.shadowBlur = 18;
    ctx.fill();
    ctx.shadowBlur = 0;
    glowStroke(ctx, tone.line, 2, 10);
    // Glowing veins under the skin, pulsing.
    ctx.save();
    ctx.clip();
    ctx.globalAlpha = Math.max(.15, .4 + Math.sin(t * 2.6) * .25 + ((pet.needs?.mood ?? 60) / 100) * .35);
    ctx.strokeStyle = tone.vein;
    ctx.lineWidth = 1.2;
    for (let i = 0; i < 6; i += 1) {
      const a = i / 6 * Math.PI * 2 + .3;
      ctx.beginPath(); ctx.moveTo(0, 12);
      ctx.bezierCurveTo(Math.cos(a) * 10, 12 + Math.sin(a) * 8, Math.cos(a + .5) * 20, Math.sin(a + .5) * 20, Math.cos(a) * 30, Math.sin(a) * 30);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.restore();
    // The core, bright when it's happy.
    const happy = Math.max(.2, (pet.needs?.mood ?? 60) / 100);
    const core = ctx.createRadialGradient(0, 14, 0, 0, 14, 9);
    core.addColorStop(0, "#ffffff");
    core.addColorStop(.4, tone.glow);
    core.addColorStop(1, "rgba(0,0,0,0)");
    ctx.globalAlpha = .4 + happy * .6;
    ctx.beginPath(); ctx.arc(0, 14, 8 + Math.sin(t * 3) * 1.2, 0, Math.PI * 2); ctx.fillStyle = core; ctx.fill();
    ctx.globalAlpha = 1;
    // Its forms: a crown of petals, scars, a sensor; antennae otherwise.
    if (pet.form === "rare") {
      for (let i = 0; i < 5; i += 1) {
        const a = -Math.PI / 2 + (i - 2) * .38;
        ctx.save();
        ctx.translate(Math.cos(a) * 30, Math.sin(a) * 30);
        ctx.rotate(a + Math.PI / 2);
        ctx.beginPath(); ctx.ellipse(0, -6, 3.5, 9 + Math.sin(t * 2 + i) * 1.5, 0, 0, Math.PI * 2);
        ctx.fillStyle = tone.glow; ctx.shadowColor = tone.glow; ctx.shadowBlur = 14; ctx.fill(); ctx.shadowBlur = 0;
        ctx.restore();
      }
    } else {
      for (const side of [-1, 1]) {
        const twitch = still ? 0 : Math.sin(t * 4 + side) * 2;
        ctx.beginPath(); ctx.moveTo(side * 10, -24); ctx.quadraticCurveTo(side * 16, -36, side * 12 + twitch, -40);
        glowStroke(ctx, tone.line, 2, 6);
        ctx.beginPath(); ctx.arc(side * 12 + twitch, -40, 2.4, 0, Math.PI * 2); ctx.fillStyle = tone.glow; ctx.fill();
      }
    }
    if (pet.form === "scarred") {
      ctx.beginPath(); ctx.moveTo(12, -20); ctx.lineTo(18, -9); ctx.lineTo(13, -2); ctx.lineTo(19, 6);
      glowStroke(ctx, "#ff9a4a", 1.8, 10);
    }
    if (pet.form === "explored") {
      ctx.beginPath(); ctx.arc(-22, -8, 5, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(143, 228, 255, .35)"; ctx.fill(); glowStroke(ctx, tone.line, 1.2, 6);
    }
    face(ctx, pet, 0, -5, 4, t, tone, look);
    ctx.restore();
  }

  function bot(ctx, pet, t, tone, look) {
    const grown = pet.stage === "adult" ? 1.15 : pet.stage === "juvenile" ? 1 : .86;
    const off = pet.asleep || pet.dormant;
    ctx.save();
    ctx.scale(grown, grown);
    // The hover jet under it.
    if (!off && pet.stage !== "adult") {
      const jet = ctx.createRadialGradient(0, 32, 0, 0, 34, 18);
      jet.addColorStop(0, "rgba(255, 220, 160, .95)");
      jet.addColorStop(.4, "rgba(255, 150, 60, .5)");
      jet.addColorStop(1, "rgba(255, 120, 40, 0)");
      ctx.fillStyle = jet;
      ctx.beginPath(); ctx.ellipse(0, 34, 10, 14 + Math.sin(t * 20) * 3, 0, 0, Math.PI * 2); ctx.fill();
    }
    // Antenna and its light.
    ctx.beginPath(); ctx.moveTo(0, -26); ctx.quadraticCurveTo(4 + Math.sin(t * 2) * 3, -34, 0, -40);
    ctx.strokeStyle = "#9aa3ad"; ctx.lineWidth = 2; ctx.stroke();
    ctx.beginPath(); ctx.arc(0, -42, 3.6, 0, Math.PI * 2);
    ctx.fillStyle = off ? "#334" : Math.floor(t * 2) % 2 ? tone.glow : "#ff6b70";
    if (!off) { ctx.shadowColor = ctx.fillStyle; ctx.shadowBlur = 12; }
    ctx.fill();
    ctx.shadowBlur = 0;
    if (pet.form === "explored") {
      ctx.save(); ctx.translate(18, -30); ctx.rotate(Math.sin(t) * .4);
      ctx.beginPath(); ctx.arc(0, 0, 8, Math.PI * .85, Math.PI * 1.95); ctx.strokeStyle = tone.line; ctx.lineWidth = 2; ctx.stroke();
      ctx.restore();
    }
    // Arms when it's older, waving a little.
    if (pet.stage !== "hatchling") {
      for (const side of [-1, 1]) {
        const swing = off ? 0 : Math.sin(t * 3 + side) * .3;
        ctx.save();
        ctx.translate(side * 27, 0);
        ctx.rotate(side * (.4 + swing));
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(side * 12, 10);
        ctx.strokeStyle = "#7f8893"; ctx.lineWidth = 4; ctx.lineCap = "round"; ctx.stroke();
        ctx.beginPath(); ctx.arc(side * 13, 11, 3.5, 0, Math.PI * 2); ctx.fillStyle = tone.line; ctx.fill();
        ctx.restore();
      }
    }
    // The chassis: brushed metal with a shine.
    ctx.beginPath();
    ctx.roundRect(-27, -26, 54, 48, 14);
    const metal = ctx.createLinearGradient(0, -26, 0, 22);
    metal.addColorStop(0, mix(tone.light, "#ffffff", .3));
    metal.addColorStop(.5, tone.light);
    metal.addColorStop(1, tone.dark);
    ctx.fillStyle = metal;
    ctx.fill();
    glowStroke(ctx, tone.line, 1.6, 6);
    ctx.fillStyle = "rgba(255,255,255,.35)";
    ctx.beginPath(); ctx.roundRect(-22, -23, 44, 5, 3); ctx.fill();
    if (pet.form === "scarred" || pet.form === "neglected") {
      ctx.fillStyle = pet.form === "neglected" ? "#7a3f1e" : "#6b7178";
      ctx.beginPath(); ctx.roundRect(-22, 8, 13, 10, 2); ctx.fill();
      ctx.beginPath(); ctx.roundRect(11, 10, 10, 8, 2); ctx.fill();
      ctx.fillStyle = "#c8c8c8";
      for (const [x, y] of [[-20, 10], [-11, 10], [-20, 16], [-11, 16]]) ctx.fillRect(x, y, 1.4, 1.4);
    }
    if (pet.form === "rare") {
      ctx.strokeStyle = "#fff2b8"; ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.roundRect(-24, -23, 48, 42, 11); ctx.stroke();
    }
    // Treads when it's grown.
    if (pet.stage === "adult") {
      ctx.beginPath(); ctx.roundRect(-26, 22, 52, 11, 5);
      ctx.fillStyle = "#1a1d22"; ctx.fill();
      ctx.fillStyle = "#3a3f48";
      for (let i = 0; i < 6; i += 1) ctx.fillRect(-22 + ((i * 8 + (off ? 0 : t * 20)) % 44), 25, 4, 5);
    }
    // Its face, on a screen.
    ctx.beginPath(); ctx.roundRect(-20, -18, 40, 28, 8);
    const screen = ctx.createLinearGradient(0, -18, 0, 10);
    screen.addColorStop(0, "#0b1f2a");
    screen.addColorStop(1, "#030a10");
    ctx.fillStyle = screen; ctx.fill();
    ctx.strokeStyle = "rgba(127,232,255,.35)"; ctx.lineWidth = 1; ctx.stroke();
    if (!off) {
      ctx.save(); ctx.clip();
      ctx.fillStyle = "rgba(127,232,255,.06)";
      for (let y = -18; y < 10; y += 3) ctx.fillRect(-20, y, 40, 1);
      ctx.restore();
    }
    face(ctx, pet, 0, -8, 2.7, t, {...tone, eye: pet.sick ? "#d6e27a" : tone.eye}, look, true);
    ctx.restore();
  }

  function sample(ctx, pet, t, tone, look) {
    const grown = pet.stage === "adult" ? 1.18 : pet.stage === "juvenile" ? 1 : .82;
    const sway = pet.asleep || pet.dormant ? 0 : Math.sin(t * 1.6) * .06;
    const droop = pet.form === "neglected" || pet.mood_word === "MISERABLE" ? .28 : 0;
    ctx.save();
    ctx.scale(grown, grown);
    const kind = pet.kind || "bacterium";
    if (kind === "tubus") {
      for (const [x, h, phase] of [[-17, 30, 0], [0, 44, 1], [17, 26, 2], [-8, 20, 3], [9, 34, 4]]) {
        ctx.save();
        ctx.translate(x, 30);
        ctx.rotate(sway * (1 + phase * .3) + x * .008 + droop * Math.sign(x || 1));
        ctx.beginPath(); ctx.roundRect(-6, -h, 12, h, 6);
        const grad = ctx.createLinearGradient(-6, 0, 6, 0);
        grad.addColorStop(0, tone.dark); grad.addColorStop(.5, tone.light); grad.addColorStop(1, tone.dark);
        ctx.fillStyle = grad; ctx.fill();
        glowStroke(ctx, tone.line, 1.2, 6);
        ctx.beginPath(); ctx.ellipse(0, -h, 6.5, 3.4, 0, 0, Math.PI * 2);
        ctx.fillStyle = tone.glow; ctx.shadowColor = tone.glow; ctx.shadowBlur = 14 + Math.sin(t * 3 + phase) * 6; ctx.fill(); ctx.shadowBlur = 0;
        ctx.restore();
      }
      face(ctx, pet, 0, -2, 2.4, t, tone, look);
    } else if (kind === "fungoida") {
      ctx.beginPath(); ctx.moveTo(-9, 30); ctx.bezierCurveTo(-11, 10, -7, -2, -6, -4); ctx.lineTo(6, -4); ctx.bezierCurveTo(7, -2, 11, 10, 9, 30); ctx.closePath();
      const stem = ctx.createLinearGradient(-10, 0, 10, 0);
      stem.addColorStop(0, "#bfb79a"); stem.addColorStop(.5, "#fff8e0"); stem.addColorStop(1, "#a8a084");
      ctx.fillStyle = stem; ctx.fill();
      ctx.save();
      ctx.translate(0, -6);
      ctx.rotate(sway + droop);
      ctx.beginPath(); ctx.moveTo(-34, 4); ctx.bezierCurveTo(-34, -30, 34, -30, 34, 4); ctx.quadraticCurveTo(0, 12, -34, 4); ctx.closePath();
      ctx.fillStyle = bodyFill(ctx, tone, 32, 0, -10);
      ctx.shadowColor = tone.glow; ctx.shadowBlur = 16; ctx.fill(); ctx.shadowBlur = 0;
      glowStroke(ctx, tone.line, 1.6, 8);
      for (const [x, y, r] of [[-16, -10, 4], [4, -18, 5], [18, -6, 3.5], [-4, -4, 2.5], [24, -14, 2]]) {
        ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fillStyle = "rgba(255,255,240,.8)"; ctx.fill();
      }
      ctx.strokeStyle = "rgba(0,0,0,.25)"; ctx.lineWidth = 1;
      for (let x = -26; x <= 26; x += 6) { ctx.beginPath(); ctx.moveTo(x, 4); ctx.lineTo(x * .3, 9); ctx.stroke(); }
      ctx.restore();
      face(ctx, pet, 0, 12, 2.3, t, tone, look);
    } else {
      const cells = pet.stage === "adult" ? 7 : pet.stage === "juvenile" ? 5 : 3;
      for (let i = cells - 1; i >= 0; i -= 1) {
        const a = i / cells * Math.PI * 2 + t * .25;
        const ring = i === 0 ? 0 : 20;
        const cx = Math.cos(a) * ring, cy = Math.sin(a) * ring * .8 + droop * 10;
        const r = i === 0 ? 22 : 11 + Math.sin(t * 2 + i) * 1.3;
        // Cilia waving round each cell.
        ctx.strokeStyle = tone.line; ctx.lineWidth = 1; ctx.globalAlpha = .6;
        for (let k = 0; k < 14; k += 1) {
          const b = k / 14 * Math.PI * 2, wave = Math.sin(t * 5 + k) * .2;
          ctx.beginPath(); ctx.moveTo(cx + Math.cos(b) * r, cy + Math.sin(b) * r);
          ctx.lineTo(cx + Math.cos(b + wave) * (r + 4), cy + Math.sin(b + wave) * (r + 4)); ctx.stroke();
        }
        ctx.globalAlpha = 1;
        ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2);
        const cell = ctx.createRadialGradient(cx - r * .3, cy - r * .3, 1, cx, cy, r);
        cell.addColorStop(0, "rgba(255,255,255,.55)"); cell.addColorStop(.35, `${tone.light}cc`); cell.addColorStop(1, `${tone.dark}ee`);
        ctx.fillStyle = cell; ctx.shadowColor = tone.glow; ctx.shadowBlur = 10; ctx.fill(); ctx.shadowBlur = 0;
        glowStroke(ctx, tone.line, 1.2, 6);
        if (i > 0) { ctx.beginPath(); ctx.arc(cx + 2, cy + 2, r * .32, 0, Math.PI * 2); ctx.fillStyle = `${tone.dark}aa`; ctx.fill(); }
      }
      face(ctx, pet, 0, -2, 3.3, t, tone, look);
    }
    if (pet.form === "rare" || pet.form === "explored") {
      for (let i = 0; i < 7; i += 1) {
        const a = t * .7 + i * .9;
        ctx.beginPath(); ctx.arc(Math.cos(a) * 38, Math.sin(a * 1.3) * 28 - 6, 1.8, 0, Math.PI * 2);
        ctx.fillStyle = tone.glow; ctx.shadowColor = tone.glow; ctx.shadowBlur = 10; ctx.fill(); ctx.shadowBlur = 0;
      }
    }
    ctx.restore();
  }

  function heart(ctx, x, y, s, colour) {
    ctx.beginPath();
    ctx.moveTo(x, y + s * .35);
    ctx.bezierCurveTo(x - s, y - s * .4, x - s * .35, y - s * 1.1, x, y - s * .45);
    ctx.bezierCurveTo(x + s * .35, y - s * 1.1, x + s, y - s * .4, x, y + s * .35);
    ctx.fillStyle = colour;
    ctx.fill();
  }

  function sparkle(ctx, x, y, s, colour) {
    ctx.beginPath();
    ctx.moveTo(x, y - s * 1.6); ctx.lineTo(x + s * .4, y - s * .4); ctx.lineTo(x + s * 1.6, y); ctx.lineTo(x + s * .4, y + s * .4);
    ctx.lineTo(x, y + s * 1.6); ctx.lineTo(x - s * .4, y + s * .4); ctx.lineTo(x - s * 1.6, y); ctx.lineTo(x - s * .4, y - s * .4);
    ctx.closePath();
    ctx.fillStyle = "#ffffff"; ctx.shadowColor = colour; ctx.shadowBlur = 10; ctx.fill(); ctx.shadowBlur = 0;
  }

  function extras(ctx, pet, t, tone) {
    const reaction = pet.reaction || "";
    // eyesShut: only its eyes closed (a blink, a brace, a doze that draws its own z's).
    if (pet.asleep && !pet.dormant && !pet.eyesShut) {
      for (let i = 0; i < 3; i += 1) {
        const k = (t * .45 + i / 3) % 1;
        ctx.globalAlpha = Math.sin(k * Math.PI);
        ctx.font = `700 ${9 + k * 8}px Consolas, monospace`;
        ctx.fillStyle = tone.glow;
        ctx.fillText("z", 28 + k * 18 + Math.sin(k * 6) * 3, -30 - k * 30);
      }
      ctx.globalAlpha = 1;
    }
    if (pet.dormant) {
      ctx.strokeStyle = "#d6e8f8"; ctx.lineWidth = 1.2;
      for (const [x, y, s] of [[-38, -24, 6], [36, -32, 5], [34, 22, 4], [-30, 26, 3.5]]) {
        ctx.beginPath();
        for (let i = 0; i < 3; i += 1) {
          const a = i * Math.PI / 3 + t * .2;
          ctx.moveTo(x - Math.cos(a) * s, y - Math.sin(a) * s); ctx.lineTo(x + Math.cos(a) * s, y + Math.sin(a) * s);
        }
        ctx.stroke();
      }
    }
    if (["excited", "amazed", "hatched", "grown", "revived"].includes(reaction)) {
      for (let i = 0; i < 6; i += 1) {
        const a = t * 1.6 + i * Math.PI / 3;
        sparkle(ctx, Math.cos(a) * 46, Math.sin(a) * 36 - 4, 3 + Math.sin(t * 6 + i) * 1.5, tone.glow);
      }
    }
    if (["happy", "treat", "petted", "cured"].includes(reaction)) {
      for (let i = 0; i < 3; i += 1) {
        const k = (t * .6 + i / 3) % 1;
        ctx.globalAlpha = Math.sin(k * Math.PI);
        heart(ctx, -26 + i * 26 + Math.sin(k * 8 + i) * 4, -34 - k * 26, 5 + k * 2, "#ff6f9a");
      }
      ctx.globalAlpha = 1;
    }
    if (["scared", "distraught"].includes(reaction) && !pet.asleep) {
      const k = (t * 1.2) % 1;
      ctx.globalAlpha = 1 - k;
      ctx.beginPath();
      ctx.moveTo(30, -28 + k * 14);
      ctx.quadraticCurveTo(36, -18 + k * 14, 30, -14 + k * 14);
      ctx.quadraticCurveTo(24, -18 + k * 14, 30, -28 + k * 14);
      ctx.fillStyle = "#9fd8ff"; ctx.fill();
      ctx.globalAlpha = 1;
    }
    if (["angry", "grumpy"].includes(reaction)) {
      for (const side of [-1, 1]) {
        const k = (t + (side > 0 ? .5 : 0)) % 1;
        ctx.globalAlpha = 1 - k;
        ctx.beginPath(); ctx.arc(side * (22 + k * 10), -34 - k * 14, 4 + k * 5, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(230,230,240,.8)"; ctx.fill();
      }
      ctx.globalAlpha = 1;
    }
    if (pet.sick && !pet.dormant) {
      ctx.save();
      ctx.translate(-40, -26 + Math.sin(t * 3) * 2);
      ctx.fillStyle = "#d6e27a";
      ctx.fillRect(-1.5, -5, 3, 10); ctx.fillRect(-5, -1.5, 10, 3);
      ctx.restore();
    }
  }

  // Its mess on the floor: up to four little heaps.
  function mess(ctx, count, x, y, size, t = performance.now() / 1000) {
    const s = size / 100;
    for (let i = 0; i < count; i += 1) {
      const px = x + (i % 2 ? 1 : -1) * (42 + Math.floor(i / 2) * 16) * s;
      const py = y + 32 * s;
      const grad = ctx.createRadialGradient(px - 2 * s, py - 4 * s, 1, px, py, 9 * s);
      grad.addColorStop(0, "#9a7a4a"); grad.addColorStop(1, "#4a3418");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.ellipse(px, py, 8 * s, 4.5 * s, 0, 0, Math.PI * 2);
      ctx.ellipse(px + 1 * s, py - 4 * s, 5.5 * s, 3.4 * s, 0, 0, Math.PI * 2);
      ctx.ellipse(px + .5 * s, py - 7 * s, 3 * s, 2.2 * s, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "rgba(200, 220, 120, .5)";
      ctx.lineWidth = 1;
      const wave = t * 2.5 + i;
      for (const dx of [-3, 3]) {
        ctx.beginPath();
        ctx.moveTo(px + dx * s, py - 11 * s);
        ctx.bezierCurveTo(px + (dx + Math.sin(wave) * 2) * s, py - 15 * s, px + (dx - Math.sin(wave) * 2) * s, py - 18 * s, px + dx * s, py - 22 * s);
        ctx.stroke();
      }
    }
  }

  // look: where its eyes go (-1..1 each way); squash: 0 at rest, + squashed, - stretched.
  function draw(ctx, pet, {x = 50, y = 50, size = 100, t = performance.now() / 1000, look = null, squash = 0, aura = true, lift = 0} = {}) {
    if (!pet) return;
    const tone = tones(pet);
    const still = pet.asleep || pet.dormant;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(size / 100, size / 100);
    // A glow behind it, brighter when it's happy.
    if (aura) {
      const happy = pet.dormant ? .2 : Math.max(.25, (pet.needs?.mood ?? 60) / 100);
      const halo = ctx.createRadialGradient(0, 0, 4, 0, 0, 62);
      halo.addColorStop(0, `${tone.glow}${Math.round(happy * 90).toString(16).padStart(2, "0")}`);
      halo.addColorStop(1, `${tone.glow}00`);
      ctx.fillStyle = halo;
      ctx.beginPath(); ctx.arc(0, 0, 62, 0, Math.PI * 2); ctx.fill();
    }
    // Its shadow on the floor, smaller as it leaves the ground.
    const bob = still ? 0 : Math.sin(t * 2.2) * 2.2;
    const up = Math.max(0, lift);
    ctx.fillStyle = `rgba(0,0,0,${.35 - Math.min(.25, up / 120)})`;
    ctx.beginPath(); ctx.ellipse(0, 44, Math.max(10, 30 - bob - up * .3), 6, 0, 0, Math.PI * 2); ctx.fill();
    if (pet.reaction === "scared" && !pet.asleep) ctx.translate(Math.sin(t * 40) * 1.6, 0);
    ctx.translate(0, bob - up);
    // Breathing, and the squash of a hop or a pat (it keeps its feet on the floor).
    const breathe = still ? 1 + Math.sin(t * 1.2) * .015 : 1 + Math.sin(t * 2.2) * .025;
    const sx = (1 + squash * .22) * breathe, sy = (1 - squash * .22) / breathe;
    ctx.translate(0, 40);
    ctx.scale(sx, sy);
    ctx.translate(0, -40);
    if (pet.stage === "egg") egg(ctx, pet, t, tone);
    else if (pet.species === "bot") bot(ctx, pet, t, tone, look);
    else if (pet.species === "sample") sample(ctx, pet, t, tone, look);
    else larva(ctx, pet, t, tone, look);
    ctx.translate(0, 40);
    ctx.scale(1 / sx, 1 / sy);
    ctx.translate(0, -40);
    if (pet.stage !== "egg") extras(ctx, pet, t, tone);
    ctx.restore();
  }

  window.HatchlingArt = {draw, mess, tones, heart, sparkle};
})();
