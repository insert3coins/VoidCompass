(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "hatchling";
  const dom = Object.fromEntries(["hatchling", "pet", "roam", "name", "title", "mood", "wants", "needs", "line"]
    .map((id) => [id, document.getElementById(id)]));
  // From html_hatchling_overlay.py: the width and least height the window is sized from.
  const DESIGN_WIDTH = 250, MIN_HEIGHT = 110;
  const NEEDS = [["hunger", ""], ["mood", "MOOD"], ["clean", "CLEAN"], ["health", "HEALTH"], ["energy", "SLEEP"]];
  let model = null;
  let needsKey = "";
  let life = null, lastFrame = 0;
  // The overlay's text size (its own in Overlay Studio, else all overlays'): its words follow it.
  let textScale = 1;

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  function render(snapshot = {}) {
    const root = dom.hatchling;
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
    // Pet only has no panel to fit: its window is its strip, at its own size.
    if (snapshot.hatchling?.options?.look === "pet") { root.style.zoom = ""; delete root.dataset.fitWidth; }
    else VoidCompassOverlay.fitToWindow(root, DESIGN_WIDTH, snapshot.effects || {});
    model = snapshot.hatchling || null;
    textScale = Math.max(.75, Math.min(2, Number(snapshot.effects?.text_scale) || 1));
    root.classList.toggle("empty", !model);
    // Pet only (5.6.4): no panel, just the pet on a see-through strip.
    root.classList.toggle("pet-mode", model?.options?.look === "pet");
    if (!model) return;
    root.classList.toggle("low", Boolean(model.wants) || model.sick || model.dormant);
    dom.name.textContent = model.name.toUpperCase();
    const stageTitle = model.stage_name?.toUpperCase() || (model.stage !== "adult" ? model.stage.toUpperCase() : "");
    dom.title.textContent = model.stage === "egg" ? "EGG" : `${model.title}${stageTitle && stageTitle !== model.title ? ` · ${stageTitle}` : ""}`;
    dom.mood.textContent = model.stage === "egg" && model.hatch_minutes > 0 ? `HATCHES IN ${model.hatch_minutes} MIN` : model.mood_word;
    dom.wants.hidden = !model.wants;
    dom.wants.textContent = model.wants ? `WANTS ${model.wants}` : "";
    const key = JSON.stringify([model.needs, model.food_label, model.stage]);
    if (key !== needsKey) {
      needsKey = key;
      dom.needs.hidden = model.stage === "egg";
      dom.needs.replaceChildren(...NEEDS.map(([need, label]) => {
        const value = Math.max(0, Math.min(100, Number(model.needs?.[need]) || 0));
        const row = node("div", `need${value < 25 ? " low" : value < 50 ? " mid" : ""}`);
        const track = node("span", "track"), bar = node("i");
        bar.style.setProperty("--fill", `${value}%`);
        track.append(bar);
        row.append(node("small", "", label || model.food_label), track);
        return row;
      }));
    }
    dom.line.hidden = !model.line;
    dom.line.textContent = model.line || "";
  }

  // Its chirps in the overlay (Overlay Studio › Sounds), pitched by what it is.
  let audio = null;
  function voice(kind) {
    // Chatter is text-only; optional habitat sounds can still accompany actions.
    if (kind === "babble") return;
    if (!model?.options?.sounds) return;
    try {
      audio = audio || new AudioContext();
      if (audio.state === "suspended") audio.resume();
    } catch {
      return;
    }
    const species = model.species || "larva";
    const wave = species === "bot" ? "square" : species === "sample" ? "sine" : "triangle";
    const base = species === "bot" ? 880 : species === "sample" ? 420 : 560;
    const tone = (from, to, length, volume = .05, delay = 0) => {
      const at = audio.currentTime + delay, osc = audio.createOscillator(), gain = audio.createGain();
      osc.type = wave;
      osc.frequency.setValueAtTime(base * from, at);
      osc.frequency.exponentialRampToValueAtTime(base * to, at + length);
      gain.gain.setValueAtTime(volume, at);
      gain.gain.exponentialRampToValueAtTime(.0001, at + length);
      osc.connect(gain).connect(audio.destination);
      osc.start(at);
      osc.stop(at + length + .02);
    };
    ({
      chirp() { tone(1, 1.3, .06); tone(1.2, 1.5, .06, .05, .08); },
      cheer() { [1, 1.25, 1.5, 2].forEach((step, i) => tone(step, step, .08, .05, i * .07)); },
      boing() { tone(.5, 1, .08, .04); },
      eek() { tone(2, 2.6, .09, .04); },
      yawn() { tone(.9, .5, .55, .035); },
      snore() { tone(.17, .13, .6, .03); },
      beep() { tone(1.4, 1.4, .04, .04); tone(1.7, 1.7, .04, .04, .07); },
      hum() { tone(.36, .38, .8, .03); },
    })[kind]?.();
  }

  // Needs are live values, not a sample label. A bot's food is called POWER.
  function needWarning(pet) {
    const want = pet.wants;
    if (!want) return "";
    const mapping = {
      POWER: ["hunger", 35, "LOW POWER"],
      FOOD: ["hunger", 35, ["NUTRIENTS", "NOURISHMENT"].includes(pet.food_label) ? `LOW ${pet.food_label}` : "LOW FOOD"],
      "A CLEAN HOLD": ["clean", 35, "NEEDS CLEANING"], PLAY: ["mood", 35, "NEEDS PLAY"],
      SLEEP: ["energy", 20, "NEEDS SLEEP"],
    }[want];
    if (!mapping) return want; // Illness and hibernation have their own warnings.
    const [need, limit, label] = mapping, raw = pet.needs?.[need];
    if (raw == null || raw === "" || !Number.isFinite(Number(raw))) return label;
    const value = Math.max(0, Math.min(100, Number(raw)));
    // A new needs snapshot can arrive before its older wants field is refreshed.
    return value < limit ? `${label} · ${Math.floor(value)}%` : "";
  }

  // A quiet, borderless status beside the pet; speech is drawn separately.
  function wantsBubble(ctx, x, y, size, ratio) {
    const word = needWarning(model);
    if (!word) return;
    const tone = getComputedStyle(dom.hatchling).getPropertyValue("--yellow").trim() || "#ffd166";
    const font = Math.max(9 * ratio, size * .1) * textScale;
    ctx.save();
    ctx.font = `700 ${font}px Bahnschrift, "Segoe UI", sans-serif`;
    const wide = Math.min(ctx.canvas.width - 4, ctx.measureText(word).width), high = font * 1.8;
    const bx = Math.max(wide / 2 + 2, Math.min(ctx.canvas.width - wide / 2 - 2, x - size * .42)), by = Math.max(high / 2 + 2, y - size * .62);
    ctx.fillStyle = tone;
    ctx.shadowColor = "#000";
    ctx.shadowBlur = 4 * ratio;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(word, bx, by, Math.max(1, ctx.canvas.width - 4));
    ctx.restore();
  }

  // Its five needs as small bars beside it (Pet only, Needs: Always).
  function needBars(ctx, x, y, size, ratio) {
    const bars = ["hunger", "mood", "clean", "health", "energy"].map((need) => Math.max(0, Math.min(100, Number(model.needs?.[need]) || 0)));
    const bw = Math.max(2, size * .035), gap = bw * .8, tall = size * .3, left = x + size * .42, foot = y + size * .44;
    bars.forEach((value, i) => {
      const bx = left + i * (bw + gap);
      ctx.fillStyle = "rgba(255, 255, 255, .12)";
      ctx.fillRect(bx, foot - tall, bw, tall);
      ctx.fillStyle = value < 25 ? "#ff6075" : value < 50 ? "#ffd166" : "#4ee59b";
      ctx.fillRect(bx, foot - tall * value / 100, bw, tall * value / 100);
    });
  }

  // While your music plays it hears the levels (as the music overlay does), and dances to them.
  // Note: one loop only. It stays "listening" through each request, or every
  // frame while a request was out started another loop (a request storm that
  // slowed the overlay server, and every overlay with it).
  let listening = false;
  async function listen() {
    while (model?.music && life) {
      try {
        const response = await fetch(`/api/live?token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`, {cache: "no-store"});
        const data = response.ok ? await response.json() : (await response.arrayBuffer(), {});
        life.hear(data.bands || [], Boolean(data.playing));
      } catch {
        life.hear([], false);
      }
      await new Promise((resume) => window.setTimeout(resume, 120));
    }
    listening = false;
  }

  // The pet moves on its own between snapshots.
  function animate() {
    const pet = model?.options?.look === "pet";
    const canvas = pet ? dom.roam : dom.pet;
    const ratio = window.devicePixelRatio || 1;
    const box = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(box.width * ratio)), height = Math.max(1, Math.round(box.height * ratio));
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const now = performance.now();
    const dt = Math.min(.25, (now - (lastFrame || now)) / 1000);
    lastFrame = now;
    if (model) {
      // Feet on the bottom edge, room above for its bubbles and what it plays with.
      const size = pet ? height / 2.8 : height * .8, x = width / 2, y = height - size * (pet ? .5 : .47);
      const options = model.options || {};
      const fit = {size, range: Math.max(0, width / 2 - size * .5), top: y, ink: 9.5 * ratio, speech: options.speech !== false, text: textScale};
      if (!life) life = window.HatchlingLife.create({...fit, onSound: voice, sync: true});
      else life.resize(fit);
      life.step(dt, model);
      if (model.music && !listening) { listening = true; listen(); }
      window.HatchlingArt.mess(ctx, model.mess || 0, x, y, size);
      life.back(ctx, model, x, y);
      life.drawPet(ctx, model, {x, y, size, t: Date.now() / 1000, aura: options.glow !== false, shadow: false});
      life.front(ctx, model, x, y);
      if (pet && options.needs !== "never") wantsBubble(ctx, x + life.x, y - life.lift, size, ratio);
      if (pet && options.needs === "always" && model.stage !== "egg") needBars(ctx, x + life.x, y - life.lift, size, ratio);
    }
    requestAnimationFrame(animate);
  }

  function contentHeight() {
    return VoidCompassOverlay.designHeight(dom.hatchling, MIN_HEIGHT);
  }

  window.hatchlingOverlay = {state: () => ({pet: Boolean(model), look: model?.options?.look || "panel", life: life?.state() || null}), play: (name) => life?.play(name, model), acts: () => life?.acts || []};
  requestAnimationFrame(animate);
  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 250});
})();
