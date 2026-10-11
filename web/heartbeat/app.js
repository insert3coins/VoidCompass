(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const root = document.getElementById("heartbeat");
  const canvas = document.getElementById("orb");
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
  const orb = new window.HeartbeatOrb(canvas);
  window.heartbeatOrb = orb;
  let poller = null;
  const thoughtBox = document.getElementById("thought");
  const thoughtFrame = thoughtBox.querySelector(".thought-box");
  const thoughtHead = thoughtBox.querySelector(".thought-head");
  const thoughtText = thoughtBox.querySelector(".thought-words");
  let thoughtId = null;
  let typing = 0;

  // How each nature types (5.5.3.5): ms per character (base plus a random
  // spread), the pause after a full stop and after a comma, how often it
  // hesitates between words and for how long, the extra moment before it
  // starts, how often it mistypes the start of a word and fixes it, whether
  // it keeps its own second thoughts ("[[typed|final]]"; Stoic never has
  // any), and Curious hurrying through the words that caught its eye.
  const STANDARD_TYPING = {base: 26, spread: 26, stop: 300, comma: 130, hesitate: .04, pause: 160, think: 0, typos: 0, corrects: true, eager: 1};
  const NATURE_TYPING = {
    weary: {...STANDARD_TYPING, base: 40, spread: 32, stop: 520, comma: 220, hesitate: .08, pause: 280, think: 300},
    stoic: {...STANDARD_TYPING, base: 30, spread: 8, stop: 320, comma: 140, hesitate: 0, pause: 0, corrects: false},
    nervous: {...STANDARD_TYPING, base: 18, spread: 22, stop: 230, comma: 90, hesitate: .07, pause: 140, think: -120, typos: .06},
    curious: {...STANDARD_TYPING, base: 24, spread: 24, hesitate: .03, eager: .55},
  };
  // A beat before bad news: the eye has already seen it.
  const MOOD_BEAT = {wary: 450, downcast: 250};
  // A slip of the finger: the key beside the one it meant.
  const KEY_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"];
  function neighbour(ch, roll) {
    const lower = ch.toLowerCase();
    const row = KEY_ROWS.find((keys) => keys.includes(lower));
    if (!row) return "";
    const at = row.indexOf(lower);
    const other = row[at + (roll < .5 && at > 0 ? -1 : at < row.length - 1 ? 1 : -1)];
    return ch === lower ? other : other.toUpperCase();
  }

  // A script's words: "[[typed|final]]" resolved, and the words it noticed
  // ("⟦Hatchooe⟧", from the journal) flagged. [{ch, noticed}] per character.
  function splitNoticed(text) {
    const out = [];
    for (const part of String(text).split(/(⟦[^⟧]*⟧)/)) {
      const noticed = part.startsWith("⟦") && part.endsWith("⟧");
      for (const ch of noticed ? part.slice(1, -1) : part) out.push({ch, noticed});
    }
    return out;
  }
  const finalWords = (script) => splitNoticed(String(script).replace(/\[\[([^|\]]*)\|([^\]]*)\]\]/g, "$2"));

  // How a thought is typed (5.5.3.2): unevenly, a pause after a comma and
  // a longer one after a full stop, and "[[typed|final]]" typed, stopped,
  // deleted and corrected; since 5.5.3.5 in its nature's own way. Returns
  // [{parts, ms}] frames (the words so far) and the total time.
  function typingPlan(script, nature) {
    const feel = NATURE_TYPING[nature] || STANDARD_TYPING;
    const frames = [];
    const shown = [];
    let total = 0;
    let seed = 0;
    for (const ch of String(script)) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
    const next = () => ((seed = (seed * 1103515245 + 12345) >>> 0) / 4294967296);
    const push = (ms) => { frames.push({parts: shown.slice(), ms}); total += ms; };
    const typeOne = (ch, noticed) => {
      const last = shown.length ? shown[shown.length - 1].ch : "";
      const wordStart = !last || last === " ";
      if (wordStart && feel.typos && /[a-z]/i.test(ch) && next() < feel.typos) {
        const slip = neighbour(ch, next());
        if (slip) {
          shown.push({ch: slip, noticed});
          push(feel.base + next() * feel.spread);
          frames[frames.length - 1].ms += 160 + next() * 120;  // it sees it
          shown.pop();
          push(60);
        }
      }
      let ms = (feel.base + next() * feel.spread) * (noticed ? feel.eager : 1);
      if (last && ".!?".includes(last) && ch === " ") ms += feel.stop * (1 + next() * .7);
      else if (last && ",;:".includes(last) && ch === " ") ms += feel.comma * (1 + next() * .7);
      else if (last === " " && next() < feel.hesitate) ms += feel.pause;  // a small hesitation
      shown.push({ch, noticed});
      push(ms);
    };
    const type = (text) => { for (const {ch, noticed} of splitNoticed(text)) typeOne(ch, noticed); };
    for (const part of String(script).split(/(\[\[[^|\]]*\|[^\]]*\]\])/)) {
      const fix = /^\[\[([^|\]]*)\|([^\]]*)\]\]$/.exec(part);
      if (!fix) { type(part); continue; }
      if (!feel.corrects) { type(fix[2]); continue; }
      const before = shown.length;
      type(fix[1]);
      frames[frames.length - 1].ms += 380;  // it stops, and thinks better of it
      while (shown.length > before) {
        shown.pop();
        push(45);
      }
      frames[frames.length - 1].ms += 200;
      type(fix[2]);
    }
    return {frames, total};
  }

  window.heartbeatTyping = {typingPlan, finalWords};

  // The words on the page: plain text, and what it noticed in the accent.
  function paint(parts) {
    const nodes = [];
    let run = "";
    let noticed = false;
    const flush = () => {
      if (!run) return;
      if (noticed) {
        const mark = document.createElement("em");
        mark.className = "noticed";
        mark.textContent = run;
        nodes.push(mark);
      } else {
        nodes.push(document.createTextNode(run));
      }
      run = "";
    };
    for (const part of parts) {
      if (part.noticed !== noticed) { flush(); noticed = part.noticed; }
      run += part.ch;
    }
    flush();
    thoughtText.replaceChildren(...nodes);
  }

  // The line above a thought (5.5.3.5): what kind it is, from the mind (a
  // memory and where it sits in the story, an echo and what stirred it), or
  // for an everyday remark simply the Watcher.
  function headingFor(thought) {
    return thought.heading ? String(thought.heading) : "THE WATCHER";
  }

  // A thought: a moment's thought first (the aperture tightens), then it
  // types out as the eye speaks it, the eye showing how it feels about it.
  function showThought(thought, reduced, eye, nature) {
    const style = (thought && thought.style) || {};
    document.body.classList.toggle("thought-backdrop", style.backdrop !== false);
    document.body.dataset.thoughtColour = style.colour === "accent" ? "accent" : style.colour === "eye" ? (eye === "hal" ? "red" : "accent") : "bright";
    document.body.dataset.thoughtSize = ["small", "large"].includes(style.size) ? style.size : "standard";
    if (!thought || !thought.text) {
      thoughtId = null;
      clearTimeout(typing);
      thoughtBox.hidden = true;
      document.body.classList.remove("thought-left");
      document.documentElement.style.removeProperty("--orb-top");
      return;
    }
    document.body.classList.toggle("thought-left", thought.side === "left");
    // Near a screen edge the window grows away from it, so the orb isn't
    // always in the middle: the bridge says where its top is.
    document.documentElement.style.setProperty("--orb-top", `${Math.max(0, Number(thought.orb_top) || 0)}px`);
    thoughtHead.hidden = style.heading === false;
    if (thought.id === thoughtId) return;
    thoughtId = thought.id;
    clearTimeout(typing);
    thoughtBox.hidden = false;
    thoughtBox.classList.remove("done");
    thoughtFrame.dataset.kind = String(thought.kind || "");
    thoughtHead.textContent = headingFor(thought);
    const script = String(thought.script || thought.text);
    const words = finalWords(script);
    if (reduced) {
      paint(words);
      thoughtBox.classList.add("done");
      return;
    }
    const {frames, total} = typingPlan(script, nature);
    const feel = NATURE_TYPING[nature] || STANDARD_TYPING;
    const pause = Math.max(200, 420 + Math.floor(Math.random() * 480) + feel.think + (MOOD_BEAT[thought.mood] || 0));
    orb.showMood?.(thought.mood);
    orb.think?.(pause);
    thoughtText.textContent = "";
    let index = 0;
    const step = () => {
      const frame = frames[index];
      if (!frame) {
        paint(words);
        thoughtBox.classList.add("done");
        return;
      }
      paint(frame.parts);
      index += 1;
      typing = setTimeout(step, frame.ms);
    };
    typing = setTimeout(() => {
      orb.speak?.(total);
      step();
    }, pause);
  }

  function render(snapshot = {}) {
    const effects = snapshot.effects || {};
    const palette = VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, effects);
    const model = snapshot.heartbeat || {};
    const stalled = Boolean(model.stalled);
    // The orb at its own size while a thought shows, when a long one makes
    // the window taller than the orb; otherwise it simply fills the window.
    const orbSize = Number((model.orb || {}).size) || 0;
    if (model.thought && orbSize > 0) document.documentElement.style.setProperty("--orb-size", `${orbSize}px`);
    else document.documentElement.style.removeProperty("--orb-size");
    root.classList.toggle("stalled", stalled);
    orb.update({
      palette,
      eye: (model.orb || {}).eye,
      crt: effects.crt !== false,
      reducedMotion: motionPreference.matches || Boolean(effects.reduced_motion),
      stalled,
      events: model.events,
      statusSeq: model.status_seq,
      // Overlay Studio's Liveliness and Idle motions, and Status.json's
      // danger, heat, fuel and scooping for the Watcher's mood.
      liveliness: (model.orb || {}).liveliness,
      idle: (model.orb || {}).idle !== false,
      vitals: model.vitals,
      // What the commander is doing (the HUD's state), for how it watches.
      state: model.state,
      // Where the other overlays are, its nature, and its memory of you.
      overlays: model.overlays,
      personality: model.personality,
      memory: model.memory,
    });
    showThought(model.thought, motionPreference.matches || Boolean(effects.reduced_motion), (model.orb || {}).eye,
      model.personality);
    const label = stalled ? "Journal watcher: feed quiet"
      : orb.lastEvent ? `Journal watcher: ${orb.lastEvent}` : "Journal watcher";
    root.setAttribute("aria-label", label);
    root.title = label;
  }

  // The Music player's live levels (5.5.3.2): the eye moves with the music.
  // Asked often while something plays, once a second otherwise.
  let livePoll = 0;
  async function listen() {
    let playing = false;
    try {
      const response = await fetch(`/api/live?token=${encodeURIComponent(params.get("token") || "")}&overlay=${encodeURIComponent(params.get("overlay") || "heartbeat")}`,
        {cache: "no-store"});
      const live = response.ok ? await response.json() : {};
      playing = Boolean(live.playing) && Array.isArray(live.bands) && live.bands.length > 0;
      orb.music?.(playing ? live.bands : null);
    } catch (_error) {
      orb.music?.(null);
    }
    livePoll = window.setTimeout(listen, playing && !document.hidden ? 120 : 1000);
  }
  listen();

  motionPreference.addEventListener("change", () => poller?.rerender());
  window.addEventListener("pagehide", () => { window.clearTimeout(livePoll); orb.dispose(); });
  poller = VoidCompassOverlay.startPolling({
    token: params.get("token") || "", overlay: params.get("overlay") || "heartbeat",
    render, contentHeight: () => orb.size || 54, interval: 160,
  });
})();
