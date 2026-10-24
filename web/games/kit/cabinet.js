// The cabinet every game sits in: fits the screen, runs the game at a fixed
// 60 steps a second whatever the monitor's refresh, pauses when the deck asks
// or the window loses focus, and talks to the deck only by postMessage.
//
// A game hands over its hooks: start, update and draw, and optionally
// onLive (what the deck knows from the journal), onPause, onResume, key,
// card (a scene for the card picture) and end (a finished run, for tests).
(() => {
  "use strict";
  const Kit = window.Kit = window.Kit || {};
  const STEP = 1000 / 60;

  Kit.cabinet = function cabinet(options) {
    const W = options.width, H = options.height;
    const canvas = document.getElementById("screen");
    const ctx = canvas.getContext("2d");
    const shell = canvas.closest(".cabinet") || document.body;
    const cab = {
      W, H, canvas, ctx, state: options.state0 || "title", tick: 0, best: 0, overAt: 0, newBest: false, scale: 1,
      colours: options.colours, crt: Boolean(options.crt), live: null,
    };
    cab.input = Kit.input(canvas, W, H);
    cab.sound = Kit.sound(options.volume ?? .2);
    cab.draw = Kit.draw(ctx);

    function tell(type, extra = {}) {
      try { window.parent.postMessage({source: "voidcompass-game", type, ...extra}, "*"); } catch { /* played on its own */ }
    }

    function start() {
      cab.sound.ready();
      cab.state = "play";
      cab.newBest = false;
      options.start();
    }

    function pause() {
      if (cab.state !== "play" || options.pausable === false) return;
      cab.state = "pause";
      cab.input.release();
      options.onPause?.();
    }

    function resume() {
      if (cab.state !== "pause") return;
      cab.state = "play";
      options.onResume?.();
    }

    function press() {
      cab.sound.ready();
      if (cab.state === "title") start();
      else if (cab.state === "pause") resume();
      else if (cab.state === "over" && cab.tick - cab.overAt > 60) start();
    }

    function over(result) {
      cab.state = "over";
      cab.overAt = cab.tick;
      cab.newBest = result.score > cab.best;
      cab.best = Math.max(cab.best, result.score);
      cab.input.release();
      options.onPause?.();
      tell("over", result);
    }

    function setMute(on, quiet = false) {
      cab.sound.mute(on);
      if (!quiet) tell("mute", {muted: cab.sound.muted});
    }

    function setCrt(on, quiet = false) {
      cab.crt = Boolean(on);
      shell.classList.toggle("crt", cab.crt);
      if (!quiet) tell("crt", {on: cab.crt});
    }

    function setLive(live) {
      cab.live = live && typeof live === "object" ? live : null;
      options.onLive?.(cab.live);
    }

    // A game's own keys come first (a name being typed takes M and C too).
    cab.input.on("key", (code, event) => {
      if (options.key?.(code, event) === true) return true;
      if (code === "KeyM") { setMute(!cab.sound.muted); return true; }
      if (code === "KeyC") { setCrt(!cab.crt); return true; }
      if (code === "KeyP" || code === "Escape") {
        if (cab.state === "play") pause();
        else resume();
        return true;
      }
      if ((code === "Space" || code === "Enter") && cab.state !== "play") { press(); return true; }
      return false;
    });
    cab.input.on("down", () => {
      if (cab.state === "play") return false;
      press();
      return true;
    });

    window.addEventListener("blur", pause);
    document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
    window.addEventListener("message", (event) => {
      const data = event.data || {};
      if (event.source !== window.parent || data.source !== "voidcompass-deck") return;
      if (data.type === "pause") pause();
      if (data.type === "live") setLive(data.live);
      if (data.type === "input") cab.input.setMode(data.mode);
      if (data.type === "hello") {
        for (const [name, value] of Object.entries(data.theme || {})) {
          if (name in cab.colours && /^#[0-9a-f]{3,8}$|^rgb/i.test(String(value))) cab.colours[name] = value;
        }
        cab.best = Math.max(cab.best, Math.round(Number(data.best) || 0));
        setMute(Boolean(data.muted), true);
        if (typeof data.crt === "boolean") setCrt(data.crt, true);
        if ("live" in data) setLive(data.live);
        if (data.input) cab.input.setMode(data.input);
        fit();
      }
    });

    function fit() {
      const ratio = window.devicePixelRatio || 1;
      const size = Math.min(window.innerWidth / W, window.innerHeight / H);
      canvas.style.width = `${Math.floor(W * size)}px`;
      canvas.style.height = `${Math.floor(H * size)}px`;
      canvas.width = Math.max(1, Math.round(W * size * ratio));
      canvas.height = Math.max(1, Math.round(H * size * ratio));
      cab.scale = size * ratio;
      shell.style.setProperty("--screen-w", canvas.style.width);
      shell.style.setProperty("--screen-h", canvas.style.height);
      document.body.style.background = cab.colours.bg;
    }
    window.addEventListener("resize", fit);

    function drawPause() {
      const {text, shade} = cab.draw;
      shade("#000000", .55, W, H);
      text("PAUSED", W / 2, H / 2 - 6, 40, cab.colours.text, "center", 700, Kit.DISPLAY);
      text("PRESS P, SPACE OR CLICK TO CARRY ON", W / 2, H / 2 + 26, 12, cab.colours.accent);
    }

    // The usual title and debrief screens, for games that don't draw their own.
    function titleScreen({top, bottom, tone, tagline = "A VOID COMPASS ARCADE CABINET", rows = [], note = "", how = "", y = 160}) {
      const {text, shade, glow} = cab.draw;
      const c = cab.colours;
      shade("#000000", .45, W, H);
      glow(tone, 24);
      text(top, W / 2, y, 52, tone, "center", 700, Kit.DISPLAY);
      if (bottom) text(bottom, W / 2, y + 54, 52, c.text, "center", 700, Kit.DISPLAY);
      ctx.shadowBlur = 0;
      const after = y + (bottom ? 84 : 32);
      text(tagline, W / 2, after, 11, c.accent);
      rows.forEach(([label, value], index) => {
        const ry = after + 62 + index * 30;
        text(label, W / 2 - 170, ry, 12, c.muted, "left");
        text(value, W / 2 + 170, ry, 12, c.text, "right");
      });
      const base = after + 62 + rows.length * 30 + 20;
      if (note) text(note, W / 2, base, 11, c.orange);
      if (Math.floor(cab.tick / 30) % 2) text("PRESS SPACE OR CLICK TO LAUNCH", W / 2, H - 110, 15, c.text);
      if (how) text(how, W / 2, H - 70, 10, c.dim);
      text("P PAUSE · M SOUND · C SCREEN", W / 2, H - 50, 9, c.dim);
    }

    function overScreen({heading, tone, sub = "DEBRIEF", lines = [], rank = "", rankLabel = "COMBAT RANK"}) {
      const {text, shade, glow} = cab.draw;
      const c = cab.colours;
      shade("#000000", .62, W, H);
      const top = Math.max(120, H / 2 - 180 - lines.length * 8);
      text(heading, W / 2, top, 38, tone, "center", 700, Kit.DISPLAY);
      text(sub, W / 2, top + 34, 12, c.accent);
      lines.forEach(([label, value], index) => {
        const y = top + 86 + index * 30;
        text(label, W / 2 - 160, y, 13, c.muted, "left");
        text(String(value), W / 2 + 160, y, 15, c.text, "right");
      });
      const after = top + 86 + lines.length * 30 + 20;
      if (rank) {
        text(rankLabel, W / 2, after, 11, c.dim);
        glow(tone, 16);
        text(rank, W / 2, after + 34, 28, tone, "center", 700, Kit.DISPLAY);
        ctx.shadowBlur = 0;
      }
      if (cab.newBest) text("NEW BEST SCORE", W / 2, after + 72, 13, c.yellow);
      if (cab.tick - cab.overAt > 60 && Math.floor(cab.tick / 30) % 2) text("PRESS SPACE OR CLICK TO FLY AGAIN", W / 2, Math.min(H - 60, after + 130), 14, c.text);
    }

    // Score, best and the stage along the top.
    function scoreBar(score, stageLabel, stage) {
      const {text} = cab.draw;
      const c = cab.colours;
      text("SCORE", 18, 22, 10, c.dim, "left");
      text(Kit.pad(score, 6), 18, 42, 18, c.text, "left");
      text("BEST", W / 2, 22, 10, c.dim);
      text(Kit.pad(Math.max(cab.best, score), 6), W / 2, 42, 18, c.accent);
      if (stageLabel) {
        text(stageLabel, W - 18, 22, 10, c.dim, "right");
        text(Kit.pad(stage), W - 18, 42, 18, c.text, "right");
      }
    }

    let last = performance.now(), spare = 0;
    function frame(now) {
      spare = Math.min(spare + now - last, 250);
      last = now;
      while (spare >= STEP) {
        cab.tick += 1;
        options.update();
        spare -= STEP;
      }
      ctx.setTransform(cab.scale, 0, 0, cab.scale, 0, 0);
      options.draw();
      ctx.setTransform(cab.scale, 0, 0, cab.scale, 0, 0);
      if (cab.state === "pause") drawPause();
      requestAnimationFrame(frame);
    }

    Object.assign(cab, {tell, start, pause, resume, press, over, setCrt, setLive, titleScreen, overScreen, scoreBar});
    setCrt(cab.crt, true);
    fit();
    requestAnimationFrame(frame);
    queueMicrotask(() => tell("ready"));

    // For tests and the card-picture tool.
    window.cabinet = {
      state: () => ({state: cab.state, tick: cab.tick, best: cab.best, muted: cab.sound.muted, crt: cab.crt, input: cab.input.mode,
        pointer: cab.input.pointer.active, ...(options.report?.() || {})}),
      start() { if (cab.state !== "play") start(); },
      end() { if (cab.state !== "play") start(); options.end(); },
      card() { if (!options.card) return start(); cab.state = "play"; options.card(); },
      live: setLive,
    };
    return cab;
  };
})();
