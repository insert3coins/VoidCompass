(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "gravity";
  const root = document.getElementById("gravity");
  const node = (id) => document.getElementById(id);
  const finite = (value) => value !== null && value !== undefined && value !== ""
    && Number.isFinite(Number(value));
  // Python grades the world by its gravity over the commander's limit:
  // under 1.25x is a caution, under 1.75x a warning, beyond that critical.
  const TAGS = {warning: "CAUTION", high: "WARNING", critical: "WARNING"};
  let lastPhase = "";
  let flickerTimer = 0;

  function formatAltitude(metres) {
    const value = Math.max(0, Number(metres) || 0);
    if (value >= 100000) return `${Math.round(value / 1000)} KM`;
    return value >= 1000 ? `${(value / 1000).toFixed(1)} KM` : `${Math.round(value)} M`;
  }

  function place(element, fraction) {
    element.style.left = `${(Math.max(0, Math.min(1, fraction)) * 100).toFixed(2)}%`;
  }

  function render(snapshot = {}) {
    const effects = snapshot.effects || {};
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, effects);
    const data = snapshot.gravity || {};
    const severity = ["warning", "high", "critical"].includes(data.severity) ? data.severity : "warning";
    const phase = data.phase === "final" ? "final" : "approach";
    const g = finite(data.g) ? Number(data.g) : null;
    const limit = Math.max(.1, Number(data.threshold) || 3);
    root.dataset.severity = severity;
    root.dataset.phase = phase;

    node("tag").textContent = TAGS[severity];
    node("value").textContent = g === null ? "—" : `${g.toFixed(2)} G`;
    node("ratio").textContent = g === null ? "" : `${(g / limit).toFixed(2)}× LIMIT`;
    const shortName = String(data.body_short || "").trim();
    const identity = shortName
      ? [shortName, String(data.system || "").trim()].filter(Boolean).join(" · ")
      : String(data.body || "UNKNOWN BODY");
    node("body").textContent = identity.toUpperCase();
    node("body").title = String(data.body || "");

    // The gauge runs from zero to twice the limit, so the limit always sits
    // in the middle and the severity zones keep their places.
    const span = limit * 2;
    const marker = node("marker");
    marker.hidden = g === null;
    if (g !== null) place(marker, g / span);
    root.classList.toggle("off-scale", g !== null && g > span);
    const oneG = 1 / span;
    // 1 G is a useful landmark unless it would crowd the zero or the limit.
    const showOneG = oneG > .09 && oneG < .38;
    node("one-g").hidden = !showOneG;
    node("one-g-tick").hidden = !showOneG;
    place(node("one-g"), oneG);
    place(node("one-g-tick"), oneG);
    node("limit").textContent = `LIMIT ${limit.toFixed(1)} G`;
    node("max").textContent = `${span.toFixed(1)} G`;

    // Altitude and descent are live Status.json values; with none, only
    // the phase is shown.
    const parts = [phase === "final" ? "FINAL APPROACH" : "APPROACH"];
    if (finite(data.altitude_m)) parts.push(`ALT ${formatAltitude(data.altitude_m)}`);
    const descent = finite(data.descent_mps) ? Number(data.descent_mps) : 0;
    if (Math.abs(descent) > 1) {
      parts.push(`${descent > 0 ? "▼" : "▲"} ${Math.round(Math.abs(descent)).toLocaleString()} M/S`);
    }
    node("phase").textContent = parts.join(" · ");

    if (lastPhase && phase !== lastPhase && !root.classList.contains("reduced-motion")) {
      root.classList.remove("phase-change");
      void root.offsetWidth;
      root.classList.add("phase-change");
      window.clearTimeout(flickerTimer);
      flickerTimer = window.setTimeout(() => root.classList.remove("phase-change"), 600);
    }
    lastPhase = phase;
  }

  VoidCompassOverlay.startPolling({token, overlay, render, interval: 220});
})();
