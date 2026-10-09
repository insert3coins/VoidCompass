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
  const thoughtText = thoughtBox.querySelector("span");
  let thoughtId = null;
  let typing = 0;

  // How a thought is typed (5.5.3.2): unevenly, a pause after a comma and
  // a longer one after a full stop, and "[[typed|final]]" typed, stopped,
  // deleted and corrected. Returns [{text, ms}] frames and the total time.
  function typingPlan(script) {
    const frames = [];
    let shown = "";
    let total = 0;
    let seed = 0;
    for (const ch of script) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
    const next = () => ((seed = (seed * 1103515245 + 12345) >>> 0) / 4294967296);
    const push = (text, ms) => { frames.push({text, ms}); total += ms; };
    const type = (text) => {
      for (const ch of text) {
        const last = shown.slice(-1);
        let ms = 26 + next() * 26;
        if (".!?".includes(last) && ch === " ") ms += 300 + next() * 220;
        else if (",;:".includes(last) && ch === " ") ms += 130 + next() * 90;
        else if (last === " " && next() < .04) ms += 160;  // a small hesitation
        shown += ch;
        push(shown, ms);
      }
    };
    for (const part of String(script).split(/(\[\[[^|\]]*\|[^\]]*\]\])/)) {
      const fix = /^\[\[([^|\]]*)\|([^\]]*)\]\]$/.exec(part);
      if (!fix) { type(part); continue; }
      type(fix[1]);
      frames[frames.length - 1].ms += 380;  // it stops, and thinks better of it
      for (let index = 0; index < fix[1].length; index += 1) {
        shown = shown.slice(0, -1);
        push(shown, 45);
      }
      frames[frames.length - 1].ms += 200;
      type(fix[2]);
    }
    return {frames, total};
  }

  // A thought: a moment's thought first (the aperture tightens), then it
  // types out as the eye speaks it, the eye showing how it feels about it.
  function showThought(thought, reduced, eye) {
    const style = (thought && thought.style) || {};
    document.body.classList.toggle("thought-backdrop", style.backdrop !== false);
    document.body.dataset.thoughtColour = style.colour === "accent" ? "accent" : style.colour === "eye" ? (eye === "hal" ? "red" : "accent") : "bright";
    document.body.dataset.thoughtSize = ["small", "large"].includes(style.size) ? style.size : "standard";
    if (!thought || !thought.text) {
      thoughtId = null;
      clearTimeout(typing);
      thoughtBox.hidden = true;
      document.body.classList.remove("thought-left");
      return;
    }
    document.body.classList.toggle("thought-left", thought.side === "left");
    if (thought.id === thoughtId) return;
    thoughtId = thought.id;
    clearTimeout(typing);
    thoughtBox.hidden = false;
    thoughtBox.classList.remove("done");
    const text = String(thought.text);
    if (reduced) {
      thoughtText.textContent = text;
      thoughtBox.classList.add("done");
      return;
    }
    const {frames, total} = typingPlan(String(thought.script || text));
    const pause = 420 + Math.floor(Math.random() * 480);
    orb.showMood?.(thought.mood);
    orb.think?.(pause);
    thoughtText.textContent = "";
    let index = 0;
    const step = () => {
      const frame = frames[index];
      if (!frame) {
        thoughtText.textContent = text;
        thoughtBox.classList.add("done");
        return;
      }
      thoughtText.textContent = frame.text;
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
    showThought(model.thought, motionPreference.matches || Boolean(effects.reduced_motion), (model.orb || {}).eye);
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
