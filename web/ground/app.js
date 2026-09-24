(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "ground-target";
  const root = document.getElementById("ground");
  const node = id => document.getElementById(id);
  const finite = value => value !== null && value !== undefined && value !== ""
    && Number.isFinite(Number(value));
  const degrees = value => `${Math.round(((Number(value) % 360) + 360) % 360) % 360}`.padStart(3, "0") + "°";
  const coordinate = value => Number(value).toFixed(5);

  function render(snapshot = {}) {
    const effects = snapshot.effects || {};
    VoidCompassOverlay.applyTheme(root, snapshot.theme, effects);
    root.classList.toggle("large-type", Number(effects.text_scale) >= 1.45);

    const data = snapshot.navigation || {};
    const live = data.state === "OK" && data.active !== false;
    const distance = live && finite(data.distance_m) && Number(data.distance_m) >= 0
      ? Number(data.distance_m) : null;
    const bearing = live && finite(data.bearing) ? Number(data.bearing) : null;
    const heading = live && finite(data.heading) ? Number(data.heading) : null;
    const delta = live && finite(data.heading_delta) && heading !== null
      ? Math.max(-180, Math.min(180, Number(data.heading_delta))) : null;

    let state = "tracking";
    let stateLabel = "EN ROUTE";
    if (!live) {
      state = "pending";
      stateLabel = data.state === "WAIT_BODY" ? "AWAITING TARGET BODY"
        : data.state === "WAIT_POS" ? "AWAITING POSITION" : "FIX PENDING";
    } else if (distance !== null && distance <= 25) {
      state = "at-fix";
      stateLabel = "WITHIN 25 M";
    } else if (distance !== null && distance <= 150) {
      state = "near";
      stateLabel = "NEAR FIX";
    } else if (distance === null) {
      state = "range-unavailable";
      stateLabel = "DISTANCE UNAVAILABLE";
    }
    root.dataset.state = state;
    root.classList.toggle("heading-unavailable", delta === null);

    node("body-name").textContent = String(data.target_label || data.body || "SURFACE FIX").toUpperCase();
    node("distance").textContent = distance === null ? "—" : String(data.distance_label || `${Math.round(distance)} m`);
    node("state-label").textContent = stateLabel;
    node("direction").textContent = !live ? "GUIDANCE STANDBY"
      : delta === null ? "BEARING ONLY · HEADING N/A"
        : Math.abs(delta) <= 12 ? "TARGET STRAIGHT AHEAD"
          : delta < 0 ? "TARGET TO PORT" : "TARGET TO STARBOARD";

    const turn = delta === null ? "HEADING N/A"
      : Math.abs(delta) <= 12 ? "AHEAD"
        : `${delta < 0 ? "LEFT" : "RIGHT"} ${Math.abs(delta).toFixed(0)}°`;
    node("turn-value").textContent = turn;
    root.style.setProperty("--needle-angle", `${delta === null ? 0 : delta}deg`);
    root.style.setProperty("--turn-position", `${delta === null ? 50 : 50 + delta / 180 * 50}%`);

    node("target").textContent = finite(data.target_lat) && finite(data.target_lon)
      ? `${coordinate(data.target_lat)}, ${coordinate(data.target_lon)}` : "—";
    node("coordinates").textContent = live && finite(data.current_lat) && finite(data.current_lon)
      ? `${coordinate(data.current_lat)}, ${coordinate(data.current_lon)}` : "POSITION PENDING";
    node("bearing").textContent = `${heading === null ? "—" : degrees(heading)} / ${bearing === null ? "—" : degrees(bearing)}`;
  }

  function contentHeight() {
    // The panel has intrinsic height, not 100% viewport height: reporting it
    // cannot feed a previous host resize back as a new content measurement.
    return Math.max(208, Math.ceil(root.getBoundingClientRect().height));
  }

  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 180});
})();
