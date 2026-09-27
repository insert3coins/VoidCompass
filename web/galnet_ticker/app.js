(() => {
  "use strict";
  /*
   * Galnet ticker. The stories scroll right to left as one seamless loop:
   * the track holds enough copies of the sequence to cover the window, and a
   * Web Animation moves it by exactly one sequence before repeating. A change
   * of speed only changes the animation's playback rate, so the text never
   * jumps; a change of stories rebuilds the loop. Under reduced motion the
   * ticker holds one story still and steps to the next every few seconds.
   *
   * The bar is drawn as a CRT tube (styles.css draws the still screen at the
   * level Python resolves) and its signal glitches now and then: a burst is
   * a few quick frames of jitter, colour fringing, grain and torn bands of
   * text, then the picture settles. A new dispatch arrives as a burst of
   * interference. Reduced motion keeps the still screen and nothing else.
   */
  const params = new URLSearchParams(location.search);
  const root = document.getElementById("ticker");
  const windowNode = document.getElementById("ticker-window");
  const track = document.getElementById("ticker-track");
  const idle = document.getElementById("ticker-idle");
  const newTag = document.getElementById("ticker-new");
  const badgeName = document.getElementById("ticker-name");
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
  // The animation runs at this speed (px/s); playbackRate scales it.
  const BASE_SPEED = 75;
  const STILL_STEP_MS = 8000;
  const NAME = badgeName.textContent;
  const CRT_LEVELS = ["off", "subtle", "standard", "strong"];
  // Seconds between the signal's own glitches: a random wait in this range.
  const GLITCH_GAPS = {rare: [45, 95], occasional: [14, 32], frequent: [5, 11]};
  // What a glitch does at each strength: how many frames it lasts, how far
  // the picture jumps and leans (px and degrees at 100% text), how wide the
  // colour fringe opens, how many displaced bands and colour ghosts it
  // throws, the grain it adds, and whether it tears or scrambles the badge.
  const GLITCH_FORMS = {
    subtle: {frames: [3, 4], jitter: 2.5, skew: 0, split: 1.6, shifts: 0, ghosts: 0, noise: .05, tear: false, scramble: false},
    standard: {frames: [4, 6], jitter: 5, skew: 3, split: 3, shifts: 1, ghosts: 1, noise: .1, tear: true, scramble: false},
    strong: {frames: [6, 9], jitter: 9, skew: 7, split: 5, shifts: 2, ghosts: 2, noise: .18, tear: true, scramble: true},
  };
  const SCRAMBLE = "#%&$@/<>0123456789ΣΔΞΛ";
  const IDLE_TEXT = {
    off: "GALNET RELAY OFF · SWITCH IT ON IN SETTINGS",
    waiting: "AWAITING DISPATCHES",
    receiving: "RECEIVING DISPATCHES…",
    error: "GALNET UNAVAILABLE · CACHED NEWS WILL RETURN",
  };
  let animation = null;
  let contentKey = "";
  let stories = [];
  let options = {};
  let scale = 1;
  let reduced = false;
  let stillIndex = 0;
  let stillTimer = 0;
  let poller = null;
  let loopWidth = 0;
  let loopFrames = null;
  let loopTiming = null;
  let crtLevel = "off";
  let noiseColor = "";
  let rendered = false;
  let newsIds = null;
  let glitchKey = "";
  let glitchTimer = 0;
  let glitchStep = 0;
  let glitching = false;
  let glitchCount = 0;
  let powerTimer = 0;

  const random = (low, high) => low + Math.random() * (high - low);

  function storyNode(story) {
    const node = document.createElement("span");
    node.className = `ticker-story${story.new ? " new" : ""}`;
    const title = document.createElement("b");
    title.textContent = story.title;
    node.append(title);
    if (options.show_date && story.stamp) {
      const date = document.createElement("time");
      date.textContent = String(story.stamp).toUpperCase();
      node.append(date);
    }
    if (story.text) {
      const body = document.createElement("span");
      body.textContent = story.text;
      node.append(body);
    }
    return node;
  }

  function sequence(list) {
    const node = document.createElement("div");
    node.className = "ticker-sequence";
    for (const story of list) {
      node.append(storyNode(story));
      const separator = document.createElement("i");
      separator.className = "ticker-sep";
      separator.textContent = "◆";
      separator.setAttribute("aria-hidden", "true");
      node.append(separator);
    }
    return node;
  }

  function speedRate() {
    return (Number(options.px_per_second) || BASE_SPEED) * scale / BASE_SPEED;
  }

  function stopStill() {
    window.clearInterval(stillTimer);
    stillTimer = 0;
  }

  function showStill() {
    stopStill();
    if (!stories.length) return;
    stillIndex %= stories.length;
    track.replaceChildren(sequence([stories[stillIndex]]));
    if (stories.length > 1) {
      stillTimer = window.setInterval(() => {
        stillIndex = (stillIndex + 1) % stories.length;
        track.replaceChildren(sequence([stories[stillIndex]]));
      }, STILL_STEP_MS);
    }
  }

  function buildLoop() {
    // A glitch's bands copy the old loop, and the power-on's squeeze would
    // skew the measurements below; both give way to the new loop.
    clearGlitch();
    endPowerOn();
    loopWidth = windowNode.clientWidth;
    animation?.cancel();
    animation = null;
    loopFrames = null;
    stopStill();
    if (!stories.length) {
      track.replaceChildren();
      return;
    }
    if (reduced) {
      showStill();
      return;
    }
    const first = sequence(stories);
    track.replaceChildren(first);
    const width = first.getBoundingClientRect().width;
    const view = windowNode.getBoundingClientRect().width;
    if (!width || !view) return;
    // Enough copies that the window is always full while one scrolls out.
    const copies = Math.max(2, Math.ceil(view / width) + 1);
    for (let index = 1; index < copies; index += 1) track.append(first.cloneNode(true));
    loopFrames = [{transform: "translateX(0)"}, {transform: `translateX(${-width}px)`}];
    loopTiming = {duration: (width / BASE_SPEED) * 1000, iterations: Infinity, easing: "linear"};
    animation = track.animate(loopFrames, loopTiming);
    animation.playbackRate = speedRate();
  }

  // Grain for the tube, dotted in the theme's text colour so it belongs to
  // whichever theme is on; redrawn only when that colour changes.
  function paintNoise(color) {
    if (!color || color === noiseColor) return;
    noiseColor = color;
    const canvas = document.createElement("canvas");
    canvas.width = 160;
    canvas.height = 60;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.fillStyle = color;
    for (let index = 0; index < 1800; index += 1) {
      context.globalAlpha = Math.random() * .9;
      context.fillRect(Math.floor(Math.random() * 160), Math.floor(Math.random() * 60), 1, 1);
    }
    root.style.setProperty("--noise-image", `url("${canvas.toDataURL()}")`);
  }

  // The tube warming up: a bright line that opens into the picture.
  function powerOn() {
    endPowerOn();
    void root.offsetWidth;
    root.classList.add("power-on");
    powerTimer = window.setTimeout(endPowerOn, 900);
  }

  function endPowerOn() {
    window.clearTimeout(powerTimer);
    powerTimer = 0;
    root.classList.remove("power-on");
  }

  // Copies of the scrolling text, kept in step with it, for a glitch to
  // clip into bands and push sideways: "shift" bands cover the text beneath
  // them, "ghost" bands lay one gun's colour over it.
  function glitchBands(form) {
    if (!animation || !loopFrames) return [];
    const guns = ["red", "cyan", "red"].slice(0, form.ghosts).map((gun) => `ghost ${gun}`);
    return [...Array(form.shifts).fill("shift"), ...guns].map((kind) => {
      const band = document.createElement("div");
      band.className = `ticker-slice ${kind}`;
      band.setAttribute("aria-hidden", "true");
      const copy = track.cloneNode(true);
      copy.removeAttribute("id");
      copy.removeAttribute("aria-live");
      band.append(copy);
      windowNode.append(band);
      const motion = copy.animate(loopFrames, loopTiming);
      motion.currentTime = animation.currentTime;
      motion.playbackRate = animation.playbackRate;
      return band;
    });
  }

  function scramble(text, share) {
    return [...text].map((letter) => (
      Math.random() < share ? SCRAMBLE[Math.floor(Math.random() * SCRAMBLE.length)] : letter
    )).join("");
  }

  function glitchFrame(form, bands, first) {
    const jitter = form.jitter * scale;
    root.style.setProperty("--glitch-x", `${random(-jitter, jitter).toFixed(1)}px`);
    root.style.setProperty("--glitch-skew", `${random(-form.skew, form.skew).toFixed(1)}deg`);
    root.style.setProperty("--glitch-split", `${random(form.split * .4, form.split).toFixed(1)}px`);
    root.style.setProperty("--glitch-noise", random(form.noise * .5, form.noise).toFixed(3));
    root.style.setProperty("--tear-y", `${Math.round(random(8, 88))}%`);
    root.classList.toggle("tearing", form.tear && Math.random() < .6);
    root.classList.toggle("glitch-flash", first);
    for (const band of bands) {
      const top = random(0, 78);
      const height = random(12, band.classList.contains("ghost") ? 55 : 34);
      band.style.setProperty("--slice-top", `${top.toFixed(1)}%`);
      band.style.setProperty("--slice-bottom", `${Math.max(0, 100 - top - height).toFixed(1)}%`);
      band.style.setProperty("--slice-x", `${(random(-3, 3) * jitter).toFixed(1)}px`);
    }
    if (form.scramble) badgeName.textContent = scramble(NAME, random(.25, .7));
  }

  function clearGlitch() {
    window.clearTimeout(glitchStep);
    glitchStep = 0;
    glitching = false;
    root.classList.remove("glitching", "tearing", "glitch-flash");
    for (const name of ["--glitch-x", "--glitch-skew", "--glitch-split", "--glitch-noise", "--tear-y"]) {
      root.style.removeProperty(name);
    }
    for (const band of windowNode.querySelectorAll(".ticker-slice")) {
      band.getAnimations({subtree: true}).forEach((motion) => motion.cancel());
      band.remove();
    }
    badgeName.textContent = NAME;
    badgeName.style.removeProperty("width");
  }

  // One burst: a few frames 40-90 ms apart, then the picture settles. A new
  // dispatch hits at least as hard as Standard, runs longer and scrambles
  // the badge, whatever strength is chosen.
  function glitch(reason = "signal") {
    if (reduced || glitching) return false;
    let form = GLITCH_FORMS[options.glitch_strength] || GLITCH_FORMS.standard;
    if (reason === "news") {
      const base = form === GLITCH_FORMS.subtle ? GLITCH_FORMS.standard : form;
      form = {...base, frames: [base.frames[0] + 3, base.frames[1] + 4], scramble: true};
    }
    glitching = true;
    glitchCount += 1;
    root.classList.add("glitching");
    // Scrambled glyphs are not as wide as the name; hold its width so the
    // bar does not shuffle along behind it.
    if (form.scramble) badgeName.style.width = `${badgeName.getBoundingClientRect().width}px`;
    const bands = glitchBands(form);
    let frames = Math.round(random(...form.frames));
    const step = (first) => {
      if (frames <= 0) {
        clearGlitch();
        return;
      }
      frames -= 1;
      glitchFrame(form, bands, first);
      glitchStep = window.setTimeout(() => step(false), random(40, 90));
    };
    step(true);
    return true;
  }

  function scheduleGlitch() {
    window.clearTimeout(glitchTimer);
    glitchTimer = 0;
    const gap = GLITCH_GAPS[options.glitch];
    if (!gap || reduced) return;
    glitchTimer = window.setTimeout(() => {
      glitch();
      scheduleGlitch();
    }, random(...gap) * 1000);
  }

  function render(snapshot = {}) {
    const effects = snapshot.effects || {};
    const palette = VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, effects);
    paintNoise(palette?.text);
    const model = snapshot.ticker || {};
    const status = ["live", "waiting", "receiving", "off", "error"].includes(model.status) ? model.status : "waiting";
    const nextReduced = motionPreference.matches || Boolean(effects.reduced_motion);
    scale = Math.max(.75, Math.min(2, Number(effects.text_scale) || 1));
    options = model.options || {};
    stories = Array.isArray(model.stories) ? model.stories.filter((story) => story && story.title) : [];
    root.classList.remove("live", "waiting", "receiving", "off", "error");
    root.classList.add(status, ...(model.busy && status === "live" ? ["receiving"] : []));
    root.classList.toggle("still", nextReduced);
    // Python resolves the level (the ticker's own, or the shared CRT switch
    // and intensity); a snapshot without one only says on or off.
    crtLevel = CRT_LEVELS.includes(effects.crt_level) ? effects.crt_level : (effects.crt ? "subtle" : "off");
    root.dataset.crt = crtLevel;
    root.classList.toggle("crt-motion", crtLevel !== "off" && options.crt_motion !== false && !nextReduced);
    const showing = status === "live" && stories.length > 0;
    track.hidden = !showing;
    idle.hidden = showing;
    idle.textContent = IDLE_TEXT[status] || IDLE_TEXT.waiting;
    newTag.hidden = !stories.some((story) => story.new);
    const label = showing ? `Galnet: ${stories[0].title}` : `Galnet: ${idle.textContent}`;
    root.setAttribute("aria-label", label);
    // Dispatches flagged new that the bar has not seen before; the first
    // render only learns what is already there.
    const flagged = stories.filter((story) => story.new).map((story) => story.id || story.title);
    const arrived = newsIds ? flagged.filter((id) => !newsIds.has(id)) : [];
    newsIds = new Set([...(newsIds || []), ...flagged]);
    const key = JSON.stringify([stories, options.show_date, options.content, scale, nextReduced]);
    if (key !== contentKey) {
      contentKey = key;
      reduced = nextReduced;
      stillIndex = 0;
      buildLoop();
    } else if (animation) {
      // Speed alone changed: carry on from where the text is.
      animation.playbackRate = speedRate();
    }
    if (reduced) clearGlitch();
    const nextGlitchKey = `${options.glitch}|${reduced}`;
    if (nextGlitchKey !== glitchKey) {
      glitchKey = nextGlitchKey;
      scheduleGlitch();
    }
    if (!rendered) {
      rendered = true;
      if (root.classList.contains("crt-motion")) powerOn();
    } else if (arrived.length && showing && options.glitch_on_news !== false) {
      glitch("news");
    }
  }

  // A longer or shorter bar needs a different number of copies. Its layout
  // width, not its drawn one: the power-on's squeeze and a glitch's lean
  // change how wide the window looks, not how wide it is.
  if (window.ResizeObserver) {
    new ResizeObserver(() => {
      const width = windowNode.clientWidth;
      if (width && width !== loopWidth) buildLoop();
    }).observe(windowNode);
  }
  motionPreference.addEventListener("change", () => poller?.rerender());
  window.addEventListener("pagehide", () => {
    animation?.cancel();
    stopStill();
    clearGlitch();
    window.clearTimeout(glitchTimer);
  });
  window.galnetTicker = {
    state: () => ({
      stories: stories.length,
      scrolling: Boolean(animation && animation.playState === "running"),
      rate: animation?.playbackRate || 0,
      copies: track.querySelectorAll(".ticker-sequence").length,
      still: root.classList.contains("still"),
      idle: idle.hidden ? "" : idle.textContent,
      crt: crtLevel,
      crtMotion: root.classList.contains("crt-motion"),
      glitching,
      glitches: glitchCount,
      bands: windowNode.querySelectorAll(".ticker-slice").length,
      glitchScheduled: Boolean(glitchTimer),
    }),
    // Tests (and a curious commander in devtools) can set one off.
    glitch: (reason) => glitch(reason),
  };
  poller = VoidCompassOverlay.startPolling({
    token: params.get("token") || "", overlay: params.get("overlay") || "galnet-ticker",
    render, contentHeight: () => root.getBoundingClientRect().height || 34, interval: 250,
  });
})();
