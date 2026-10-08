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

  // A thought types out a letter at a time, as the eye speaks it.
  function showThought(thought, reduced, eye) {
    const style = (thought && thought.style) || {};
    document.body.classList.toggle("thought-backdrop", style.backdrop !== false);
    document.body.dataset.thoughtColour = style.colour === "accent" ? "accent" : style.colour === "eye" ? (eye === "hal" ? "red" : "accent") : "bright";
    document.body.dataset.thoughtSize = ["small", "large"].includes(style.size) ? style.size : "standard";
    if (!thought || !thought.text) {
      thoughtId = null;
      clearInterval(typing);
      thoughtBox.hidden = true;
      document.body.classList.remove("thought-left");
      return;
    }
    document.body.classList.toggle("thought-left", thought.side === "left");
    if (thought.id === thoughtId) return;
    thoughtId = thought.id;
    clearInterval(typing);
    thoughtBox.hidden = false;
    thoughtBox.classList.remove("done");
    const text = String(thought.text);
    orb.speak?.(text.length * 32);
    if (reduced) {
      thoughtText.textContent = text;
      thoughtBox.classList.add("done");
      return;
    }
    let shown = 0;
    thoughtText.textContent = "";
    typing = setInterval(() => {
      shown += 1;
      thoughtText.textContent = text.slice(0, shown);
      if (shown >= text.length) {
        clearInterval(typing);
        thoughtBox.classList.add("done");
      }
    }, 32);
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

  motionPreference.addEventListener("change", () => poller?.rerender());
  window.addEventListener("pagehide", () => orb.dispose());
  poller = VoidCompassOverlay.startPolling({
    token: params.get("token") || "", overlay: params.get("overlay") || "heartbeat",
    render, contentHeight: () => orb.size || 54, interval: 160,
  });
})();
