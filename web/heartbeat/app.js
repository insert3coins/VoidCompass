(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "heartbeat";
  const root = document.getElementById("heartbeat");
  let pulseId = -1;

  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(
      root, snapshot.theme || {}, snapshot.effects || {},
      {scaleMin: .85, scaleMax: 1.25},
    );
    const model = snapshot.heartbeat || {};
    const stalled = Boolean(model.stalled);
    root.classList.toggle("stalled", stalled);
    root.classList.toggle("journal", model.kind === "journal");
    root.classList.toggle("status", model.kind === "status");
    root.classList.toggle("state-change", Boolean(model.state_changed));
    root.setAttribute("aria-label", stalled ? "Telemetry heartbeat stalled" : "Telemetry heartbeat active");
    root.title = stalled ? "Telemetry heartbeat stalled" : "Telemetry heartbeat active";
    const nextPulse = Number(model.pulse_id);
    if (!stalled && Number.isFinite(nextPulse) && nextPulse !== pulseId) {
      pulseId = nextPulse;
      root.classList.remove("beat");
      void root.offsetWidth;
      root.classList.add("beat");
    }
  }

  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight: 54, interval: 160});
})();
