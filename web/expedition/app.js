(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "expedition";
  const dom = Object.fromEntries(["expedition", "name", "share", "bar", "distance", "next-kind", "next-name", "next-where", "compass", "needle",
    "target-distance", "target-detail", "fly-to", "figures", "warnings"].map((id) => [id, document.getElementById(id)]));
  // From html_expedition_overlay.py: the width and least height the window is sized from.
  const DESIGN_WIDTH = 380, MIN_HEIGHT = 120;

  const number = (value, fallback = 0) => Number.isFinite(Number(value)) && value !== null ? Number(value) : fallback;
  const known = (value) => value !== null && value !== undefined && Number.isFinite(Number(value));
  const whole = (value) => Math.round(number(value)).toLocaleString("en-GB");
  const credits = (value) => {
    const v = number(value);
    return v >= 1e9 ? `${(v / 1e9).toFixed(2)} BN CR` : v >= 1e6 ? `${(v / 1e6).toFixed(1)} M CR` : `${whole(v)} CR`;
  };
  const metres = (value) => number(value) >= 1000
    ? `${(number(value) / 1000).toLocaleString("en-GB", {minimumFractionDigits: 1, maximumFractionDigits: 1})} KM` : `${whole(value)} M`;
  const upper = (value) => String(value || "").toUpperCase();

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  function figure(label, value, tone = "") {
    const box = node("div", `figure${tone ? ` ${tone}` : ""}`);
    box.append(node("small", "", label), node("b", "", value));
    return box;
  }

  function render(snapshot = {}) {
    const root = dom.expedition;
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
    VoidCompassOverlay.fitToWindow(root, DESIGN_WIDTH, snapshot.effects || {});
    const model = snapshot.expedition || null;
    root.classList.toggle("empty", !model);
    if (!model) return;
    root.classList.toggle("over", Boolean(model.risk_over));
    dom.name.textContent = upper(model.name);
    const share = known(model.share) ? Math.max(0, Math.min(1, number(model.share))) : null;
    dom.share.textContent = share === null ? "" : `${Math.round(share * 100)}%`;
    dom.bar.style.setProperty("--share", `${share === null ? 0 : (share * 100).toFixed(1)}%`);
    dom.distance.textContent = [known(model.to_go_ly) && number(model.to_go_ly) > 0 ? `${whole(model.to_go_ly)} LY TO GO` : "",
      known(model.done_ly) && number(model.done_ly) > 0 ? `${whole(model.done_ly)} LY FLOWN` : ""].filter(Boolean).join(" · ") || "PLACE THE LEGS TO MEASURE IT";

    const next = model.next;
    dom["next-kind"].textContent = next ? `NEXT STOP · ${next.kind}` : "EVERY LEG REACHED";
    dom["next-name"].textContent = next ? upper(next.name) : "HOME AND DRY";
    dom["next-where"].textContent = next ? upper(next.where) : "";
    dom["next-where"].hidden = !(next && next.where);

    // On the next stop's planet: which way to it. In its system: which body.
    const surface = model.surface || {};
    const target = surface.target;
    dom.compass.hidden = !target;
    if (target) {
      dom.needle.style.setProperty("--turn", `${number(target.turn)}deg`);
      dom.needle.classList.toggle("unknown", !known(target.turn));
      dom["target-distance"].textContent = target.arrived ? "HERE" : metres(target.distance_m);
      dom["target-detail"].textContent = [`BEARING ${String(Math.round(number(target.bearing)) % 360).padStart(3, "0")}°`,
        known(surface.altitude_m) && number(surface.altitude_m) > 0 ? `ALT ${metres(surface.altitude_m)}` : ""].filter(Boolean).join(" · ");
    }
    const flyTo = !target && surface.here && surface.body && !surface.on_body;
    dom["fly-to"].hidden = !flyTo;
    if (flyTo) {
      dom["fly-to"].textContent = `FLY TO ${upper(surface.body)}${known(surface.lat) ? ` · LAND AT ${number(surface.lat).toFixed(4)}, ${number(surface.lon).toFixed(4)}` : ""}`;
    }

    dom.figures.replaceChildren(
      figure("DATA AT RISK", model.risk ? credits(model.risk) : "—", model.risk_over ? "red" : "yellow"),
      figure("STREAK", `${whole(model.streak)} JUMPS`),
      figure("ETA", known(model.eta_hours) ? `${whole(model.eta_hours)} H` : "—"),
      figure("HULL", known(model.hull) ? `${Math.round(number(model.hull))}%` : "—"));
    const warnings = [
      ...(model.fuel_runs || []).map((run) => node("span", "warn", `NO STAR TO SCOOP: ${run.jumps} NEUTRON JUMPS FROM ${upper(run.from)}`)),
      ...((model.low || []).length ? [node("span", "warn", `RUNNING LOW · ${model.low.map(upper).join(" · ")}`)] : []),
      ...(model.ironman ? [node("span", "danger", "IRONMAN · ONE LIFE")] : []),
    ];
    dom.warnings.replaceChildren(...warnings);
    dom.warnings.hidden = !warnings.length;
  }

  function contentHeight() {
    return VoidCompassOverlay.designHeight(dom.expedition, MIN_HEIGHT);
  }

  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 250});
})();
