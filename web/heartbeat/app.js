(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const root = document.getElementById("heartbeat");
  const canvas = document.getElementById("orb");
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
  const orb = new window.HeartbeatOrb(canvas);
  window.heartbeatOrb = orb;
  let poller = null;

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
    });
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
