(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const root = document.getElementById("heartbeat");
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
  const core = root.querySelector(".signal-pulse");
  const lids = root.querySelector(".eye-lids");
  const gaze = root.querySelector(".eye-gaze");
  const gazePoints = [[-3, -1], [3, 0], [0, -2], [-2, 1], [2, 1], [0, 0]];
  const waves = [...root.querySelectorAll(".event-wave")];
  const rays = root.querySelector(".event-rays");
  let pulseId = null;
  let activeAnimations = [];
  let beatTimer = 0;

  function stopBeat() {
    window.clearTimeout(beatTimer);
    beatTimer = 0;
    activeAnimations.forEach(animation => animation.cancel());
    activeAnimations = [];
    delete root.dataset.activity;
    gaze.style.removeProperty("--gaze-x");
    gaze.style.removeProperty("--gaze-y");
  }

  function reducedMotion() {
    return motionPreference.matches || root.classList.contains("reduced-motion");
  }

  function playBeat(model) {
    // Let the double beat finish during bursts; idle signal flow never restarts.
    root.dataset.activity = model.state_changed ? "change" : model.kind || "journal";
    if (beatTimer) return;
    if (reducedMotion()) {
      beatTimer = window.setTimeout(stopBeat, 650);
      return;
    }
    // Decorative glances respond to new activity; these are not bearings.
    const [x, y] = gazePoints[Math.abs(Math.trunc(model.pulse_id)) % gazePoints.length];
    gaze.style.setProperty("--gaze-x", `${x}px`);
    gaze.style.setProperty("--gaze-y", `${y}px`);
    if (model.kind === "journal" || model.state_changed) {
      activeAnimations.push(lids.animate([
        {transform: "scaleY(1)"},
        {transform: "scaleY(.06)", offset: .42},
        {transform: "scaleY(1)"},
      ], {duration: 240, easing: "ease-in-out"}));
    }
    activeAnimations.push(core.animate([
      {transform: "scale(1)", offset: 0},
      {transform: "scale(.97)", offset: .1},
      {transform: "scale(1.1)", offset: .24},
      {transform: "scale(1)", offset: .4},
      {transform: "scale(1.05)", offset: .57},
      {transform: "scale(1)", offset: 1},
    ], {duration: 900, easing: "ease-in-out"}));
    waves.forEach((wave, index) => activeAnimations.push(wave.animate([
      {transform: "scale(.8)", opacity: 0},
      {transform: "scale(1.1)", opacity: .75, offset: .2},
      {transform: "scale(2.5)", opacity: 0},
    ], {duration: 700, delay: index * 220, easing: "ease-out"})));
    activeAnimations.push(rays.animate([
      {transform: "scaleX(.25)", opacity: 0},
      {transform: "scaleX(1)", opacity: .8, offset: .25},
      {transform: "scaleX(1.2)", opacity: 0},
    ], {duration: 900, easing: "ease-out"}));
    beatTimer = window.setTimeout(stopBeat, 940);
  }

  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.heartbeat || {};
    const stalled = Boolean(model.stalled);
    root.classList.toggle("stalled", stalled);
    const label = stalled ? "Telemetry heartbeat stalled" : "Telemetry heartbeat active";
    root.setAttribute("aria-label", label);
    root.title = label;
    if (stalled || (reducedMotion() && activeAnimations.length)) stopBeat();
    const nextPulse = model.pulse_id;
    if (typeof nextPulse !== "number" || !Number.isFinite(nextPulse)) return;
    const changed = pulseId !== null && nextPulse !== pulseId;
    pulseId = nextPulse;
    if (!stalled && changed) playBeat(model);
  }

  motionPreference.addEventListener("change", () => {
    if (reducedMotion()) stopBeat();
  });
  window.addEventListener("pagehide", stopBeat);
  VoidCompassOverlay.startPolling({
    token: params.get("token") || "", overlay: params.get("overlay") || "heartbeat",
    render, contentHeight: 54, interval: 160,
  });
})();
