(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "ground-target";
  const root = document.getElementById("ground");
  const node = (id) => document.getElementById(id);
  const finite = (value) => value !== null && value !== undefined && value !== ""
    && Number.isFinite(Number(value));
  const wrap360 = (value) => ((Number(value) % 360) + 360) % 360;
  const degrees = (value) => `${String(Math.round(wrap360(value)) % 360).padStart(3, "0")}°`;
  const coordinate = (value) => Number(value).toFixed(5);
  // Signed shortest turn from one angle to another, in [-180, 180).
  const shortest = (from, to) => ((to - from) % 360 + 540) % 360 - 180;

  // The heading tape shows 60° either side of the nose, as the SRV and suit
  // HUDs do. Its strip carries two spare turns of ticks so any heading has
  // marks on both sides and the strip can move continuously through north.
  const TAPE_SPAN = 120;
  const STRIP_FROM = -180;
  const STRIP_TO = 540;
  const CARDINALS = {0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S", 225: "SW", 270: "W", 315: "NW"};
  // These match the Python direction words: AHEAD within 12°, BEHIND past 168°.
  const AHEAD_DEG = 12;
  const BEHIND_DEG = 168;
  const NEAR_M = 150;
  const ARRIVED_M = 25;
  const MODES = {ship: "SHIP", srv: "SRV", foot: "ON FOOT", fighter: "FIGHTER", passenger: "PASSENGER"};

  let tapeHeading = null;
  let scopeAngle = null;
  let lastState = "";

  function buildTape() {
    const strip = node("tape-strip");
    const span = STRIP_TO - STRIP_FROM;
    strip.style.width = `${span / TAPE_SPAN * 100}%`;
    const ticks = document.createDocumentFragment();
    for (let degree = STRIP_FROM; degree <= STRIP_TO; degree += 5) {
      const tick = document.createElement("i");
      const value = wrap360(degree);
      tick.className = degree % 15 === 0 ? "tick major" : "tick";
      tick.style.left = `${(degree - STRIP_FROM) / span * 100}%`;
      if (degree % 15 === 0) {
        const label = document.createElement("span");
        label.textContent = CARDINALS[value] ?? String(value).padStart(3, "0");
        if (value in CARDINALS) tick.classList.add(value % 90 === 0 ? "cardinal" : "intercardinal");
        tick.appendChild(label);
      }
      ticks.appendChild(tick);
    }
    strip.replaceChildren(ticks);
  }

  // Follow the heading along the shortest turn. When the running value drifts
  // a full turn away it is folded back by exactly 360°, which shows identical
  // ticks, so that jump happens without a transition and cannot be seen.
  function placeTape(heading) {
    const strip = node("tape-strip");
    let instant = tapeHeading === null;
    tapeHeading = instant ? heading : tapeHeading + shortest(tapeHeading, heading);
    if (tapeHeading < -60 || tapeHeading >= 420) {
      tapeHeading = wrap360(tapeHeading);
      instant = true;
    }
    strip.classList.toggle("instant", instant);
    const fraction = (tapeHeading - STRIP_FROM) / (STRIP_TO - STRIP_FROM);
    strip.style.transform = `translateX(${(-fraction * 100).toFixed(4)}%)`;
  }

  function placeScope(delta) {
    const bearing = node("scope-bearing");
    const instant = scopeAngle === null;
    scopeAngle = instant ? delta : scopeAngle + shortest(scopeAngle, delta);
    bearing.classList.toggle("instant", instant);
    bearing.style.transform = `rotate(${scopeAngle.toFixed(2)}deg)`;
  }

  // Log scale from 10 km (left) to 10 m (right): each decade gets a third.
  function approachPosition(distance) {
    const metres = Math.max(10, Number(distance) || 0);
    return Math.max(0, Math.min(1, 1 - (Math.log10(metres) - 1) / 3));
  }

  function formatDuration(seconds) {
    const total = Math.max(0, Math.round(Number(seconds) || 0));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor(total % 3600 / 60);
    const secs = total % 60;
    const pad = (value) => String(value).padStart(2, "0");
    return hours ? `${hours}:${pad(minutes)}:${pad(secs)}` : `${pad(minutes)}:${pad(secs)}`;
  }

  // Closing speed is measured from real position changes by the bridge; with
  // no measurement the line stays empty rather than guessing an ETA.
  function closingText(data) {
    if (!finite(data.closing_mps)) return {text: "", tone: ""};
    const speed = Number(data.closing_mps);
    if (speed > 0.5) {
      const eta = finite(data.eta_s) ? ` · ETA ${formatDuration(data.eta_s)}` : "";
      return {text: `CLOSING ${Math.round(speed)} M/S${eta}`, tone: "closing"};
    }
    if (speed < -0.5) return {text: `OPENING ${Math.round(-speed)} M/S`, tone: "opening"};
    return {text: "HOLDING POSITION", tone: "holding"};
  }

  function formatAltitude(metres) {
    const value = Math.max(0, Number(metres) || 0);
    return value >= 1000 ? `${(value / 1000).toFixed(1)} KM` : `${Math.round(value)} M`;
  }

  function render(snapshot = {}) {
    const effects = snapshot.effects || {};
    VoidCompassOverlay.applyTheme(root, snapshot.theme, effects);
    const data = snapshot.navigation || {};
    const live = data.state === "OK" && data.active !== false;
    const distance = live && finite(data.distance_m) && Number(data.distance_m) >= 0
      ? Number(data.distance_m) : null;
    const bearing = live && finite(data.bearing) ? wrap360(data.bearing) : null;
    const heading = live && finite(data.heading) ? wrap360(data.heading) : null;
    const delta = live && finite(data.heading_delta) && heading !== null
      ? Math.max(-180, Math.min(180, Number(data.heading_delta))) : null;

    let state = "tracking";
    let stateLabel = "EN ROUTE";
    if (!live) {
      state = "pending";
      stateLabel = data.state === "WAIT_BODY" ? "AWAITING TARGET BODY"
        : data.state === "WAIT_POS" ? "AWAITING POSITION" : "FIX PENDING";
    } else if (distance === null) {
      state = "range-unavailable";
      stateLabel = "DISTANCE UNAVAILABLE";
    } else if (distance <= ARRIVED_M) {
      state = "at-fix";
      stateLabel = "ON TARGET";
    } else if (distance <= NEAR_M) {
      state = "near";
      stateLabel = "NEAR FIX";
    }
    root.dataset.state = state;
    if (state === "at-fix" && lastState && lastState !== "at-fix"
        && !root.classList.contains("reduced-motion")) {
      root.classList.remove("arrived");
      void root.offsetWidth;
      root.classList.add("arrived");
      window.setTimeout(() => root.classList.remove("arrived"), 1600);
    }
    lastState = state;
    root.classList.toggle("heading-unavailable", delta === null);

    const mode = MODES[data.mode] || "SHIP";
    node("mode").textContent = data.mode === "ship" && data.landed ? "SHIP · LANDED" : mode;
    const body = String(data.body || "").trim();
    node("body-name").textContent = String(data.body_short || body).toUpperCase();
    node("body-name").title = body;
    node("target-label").textContent = String(data.target_label || "TARGET FIX").toUpperCase();
    node("state-label").textContent = stateLabel;

    // Heading tape and the target on it.
    const tapeTarget = node("tape-target");
    const edge = node("tape-edge");
    node("heading").textContent = heading === null ? "HDG N/A" : degrees(heading);
    // Without a heading there is no nose to centre the tape on. Show the
    // caret alone, and re-enter at the next heading without sliding to it.
    node("tape-strip").hidden = heading === null;
    if (heading === null) tapeHeading = null;
    else placeTape(heading);
    if (delta === null) {
      tapeTarget.hidden = true;
      edge.hidden = true;
    } else if (Math.abs(delta) <= TAPE_SPAN / 2) {
      tapeTarget.hidden = false;
      edge.hidden = true;
      tapeTarget.style.left = `${50 + delta / TAPE_SPAN * 100}%`;
    } else {
      tapeTarget.hidden = true;
      edge.hidden = false;
      edge.dataset.side = delta < 0 ? "left" : "right";
      edge.textContent = delta < 0 ? `◀ ${Math.round(-delta)}°` : `${Math.round(delta)}° ▶`;
    }

    // Target compass: the dot sits where the target lies relative to the
    // nose, filled ahead of the beam and hollow behind it, as Elite's does.
    if (delta !== null) placeScope(delta);
    root.classList.toggle("target-behind", delta !== null && Math.abs(delta) > 90);

    node("distance").textContent = distance === null ? "—"
      : String(data.distance_label || `${Math.round(distance)} m`).toUpperCase();
    const closing = live && distance !== null && state !== "at-fix"
      ? closingText(data) : {text: "", tone: ""};
    node("closing").textContent = closing.text;
    node("closing").dataset.tone = closing.tone;

    const turn = node("turn-value");
    let turnTone = "wide";
    if (state === "at-fix") {
      turn.textContent = "ON TARGET";
      turnTone = "ahead";
    } else if (delta === null) {
      turn.textContent = live ? "HEADING N/A" : "STANDBY";
      turnTone = "none";
    } else if (Math.abs(delta) <= AHEAD_DEG) {
      turn.textContent = "AHEAD";
      turnTone = "ahead";
    } else if (Math.abs(delta) >= BEHIND_DEG) {
      turn.textContent = "TURN AROUND";
    } else {
      turn.textContent = `${delta < 0 ? "LEFT" : "RIGHT"} ${Math.round(Math.abs(delta))}°`;
      turnTone = Math.abs(delta) < 45 ? "near" : "wide";
    }
    turn.dataset.tone = turnTone;

    const approach = distance === null ? 0 : approachPosition(distance);
    node("approach-fill").style.transform = `scaleX(${approach.toFixed(4)})`;
    node("approach-marker").style.left = `${(approach * 100).toFixed(2)}%`;
    node("approach-marker").hidden = distance === null;

    node("target").textContent = finite(data.target_lat) && finite(data.target_lon)
      ? `${coordinate(data.target_lat)}, ${coordinate(data.target_lon)}` : "—";
    node("coordinates").textContent = live && finite(data.current_lat) && finite(data.current_lon)
      ? `${coordinate(data.current_lat)}, ${coordinate(data.current_lon)}` : "POSITION PENDING";
    const aux = node("aux");
    if (live && finite(data.altitude_m)) {
      aux.textContent = `ALT ${formatAltitude(data.altitude_m)}`;
    } else {
      aux.textContent = bearing === null ? "" : `BRG ${degrees(bearing)}`;
    }
  }

  function contentHeight() {
    // The panel has intrinsic height, not 100% viewport height: reporting it
    // cannot feed a previous host resize back as a new content measurement.
    return Math.max(1, Math.ceil(root.getBoundingClientRect().height));
  }

  buildTape();
  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 180});
})();
