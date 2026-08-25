(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "carrier";
  const suffix = `token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
  const root = document.getElementById("carrier");
  const byId = (id) => document.getElementById(id);
  let revision = -1;
  let polling = false;
  let ready = false;

  function set(id, value, fallback = "—") {
    const element = byId(id);
    if (element) element.textContent = value === null || value === undefined || value === "" ? fallback : String(value);
  }

  function number(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function tone(value, fallback = "muted") {
    const allowed = new Set(["accent", "orange", "green", "yellow", "red", "muted", "text", "dim"]);
    const result = String(value || fallback).toLowerCase();
    return allowed.has(result) ? result : fallback;
  }

  function applyTheme(theme = {}, effects = {}) {
    const mapping = {bg:"bg",panel:"panel",panel_alt:"alt",panel_raised:"raised",border:"border",border_soft:"soft",accent:"accent",orange:"orange",text:"text",muted:"muted",dim:"dim",green:"green",yellow:"yellow",red:"red"};
    for (const [key, css] of Object.entries(mapping)) {
      const value = String(theme[key] || "");
      if (/^#[0-9a-f]{6}$/i.test(value)) document.documentElement.style.setProperty(`--${css}`, value);
    }
    const scale = Number(effects.text_scale);
    document.documentElement.style.setProperty("--scale", String(Number.isFinite(scale) ? Math.max(.75, Math.min(2, scale)) : 1));
    const opacity = Number(effects.opacity);
    document.body.style.opacity = String(Number.isFinite(opacity) ? Math.max(.4, Math.min(1, opacity)) : 1);
    root.classList.toggle("no-crt", !effects.crt);
    root.classList.toggle("reduced-motion", Boolean(effects.reduced_motion));
  }

  function render(snapshot = {}) {
    applyTheme(snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.carrier || {};
    const state = String(model.status || "idle").toLowerCase();
    root.dataset.state = state;
    root.dataset.badgeTone = tone(model.badge_tone);
    root.dataset.movementTone = tone(model.movement_tone);
    root.dataset.fuelTone = tone(model.fuel_tone);
    set("carrier-type", model.carrier_type, "FLEET CARRIER");
    set("status-badge", model.badge, "READY");
    set("carrier-name", model.name, "Fleet Carrier");
    set("carrier-callsign", `[${model.callsign || "---"}]`);
    set("carrier-location", model.location, "Location unknown");
    set("movement-label", model.movement_label, "NEXT JUMP");
    set("movement-value", model.movement_value, "READY TO PLOT JUMP");
    set("movement-detail", model.movement_detail, "");

    const routeTotal = Math.max(0, Math.round(number(model.route_total)));
    const routeDone = Math.max(0, Math.min(routeTotal, Math.round(number(model.route_done))));
    byId("route").hidden = routeTotal < 1;
    set("route-name", model.route_name, "EXPEDITION ROUTE");
    set("route-progress", `${routeDone}/${routeTotal} COMPLETE`);
    set("route-remaining", number(model.remaining_fuel) > 0 ? `${number(model.remaining_fuel).toLocaleString()} T REMAINING` : "ROUTE FUEL CLEAR");
    set("route-state", model.route_complete ? "ROUTE COMPLETE" : "IN PROGRESS");
    const routeRatio = routeTotal ? routeDone / routeTotal : 0;
    byId("route-fill").style.setProperty("--progress", `${Math.round(routeRatio * 100)}%`);
    byId("route-marker").style.setProperty("--progress", `${Math.round(routeRatio * 100)}%`);

    const fuel = model.fuel === null || model.fuel === undefined ? null : Math.max(0, number(model.fuel));
    const capacity = Math.max(0, number(model.fuel_capacity));
    const fuelRatio = model.fuel_ratio === null || model.fuel_ratio === undefined ? 0 : Math.max(0, Math.min(1, number(model.fuel_ratio)));
    set("fuel-value", fuel === null ? "UNKNOWN" : `${model.fuel_estimated ? "~" : ""}${Math.round(fuel).toLocaleString()} / ${Math.round(capacity).toLocaleString()} T`);
    byId("fuel-fill").style.setProperty("--fuel", `${Math.round(fuelRatio * 100)}%`);
    const range = model.range === null || model.range === undefined ? null : number(model.range);
    set("jump-range", range === null ? "—" : `${model.range_is_max ? "MAX " : ""}${range.toFixed(1)} LY`);
    set("cargo-value", model.cargo === null || model.cargo === undefined ? "—" : `${Math.round(number(model.cargo)).toLocaleString()} T`);
    set("free-value", model.free === null || model.free === undefined ? "—" : `${Math.round(number(model.free)).toLocaleString()} T`);
    set("orders-value", Math.max(0, Math.round(number(model.orders))).toLocaleString());
    set("footer-state", state === "jumping" ? "JUMP SEQUENCE ACTIVE" : state.startsWith("cooldown") ? "DRIVE RECOVERY" : model.route_complete ? "EXPEDITION COMPLETE" : "COMMAND READY");
  }

  function contentHeight() { return Math.max(214, Math.ceil(root.getBoundingClientRect().height + 2)); }

  async function refresh(nextRevision) {
    const response = await fetch(`/api/snapshot?${suffix}`, {cache:"no-store"});
    if (!response.ok) return;
    render(await response.json());
    await new Promise((resolve) => requestAnimationFrame(resolve));
    revision = nextRevision;
    try {
      await fetch(`/api/rendered?${suffix}`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision:nextRevision,content_height:contentHeight()})});
      if (!ready) { ready = true; await fetch(`/api/ready?${suffix}`, {method:"POST",body:"{}"}); }
    } catch (_) {}
  }

  async function poll() {
    if (polling) return;
    polling = true;
    try {
      const response = await fetch(`/api/health?${suffix}`, {cache:"no-store"});
      if (response.ok) {
        const next = Number((await response.json()).revision);
        if (Number.isFinite(next) && next !== revision) await refresh(next);
      }
    } catch (_) {} finally { polling = false; }
  }
  poll(); window.setInterval(poll, 260);
})();
