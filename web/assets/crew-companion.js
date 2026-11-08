import {createCrewDisplay} from "./crew-3d.js";
import {companionColours} from "./companion-colours.js";

// 5.7.7: a display per companion for each source, so a crewmate stepping in
// while they speak (a guest) doesn't rebuild the one on watch. A guest's
// display unused for a while is let go.
const pools = new Map();
const views = {get: (source) => { const pool = pools.get(source); return pool?.byId.get(pool.current) || null; }, keys: () => pools.keys()};
const IDLE_MS = 90000;
function release(view) { view.display?.destroy(); view.canvas.remove(); view.error?.remove(); }
function dispose(source) {
  const pool = pools.get(source);
  if (!pool) return;
  for (const view of pool.byId.values()) release(view);
  pools.delete(source);
  source.style.opacity = "";
}
function hide(view) {
  view.display?.setVisible(false); view.canvas.hidden = true; view.canvas.style.display = "none";
  if (view.error) { view.error.hidden = true; view.error.style.display = "none"; }
}
function update(source, model = {}, live = {}, options = {}) {
  if (!source) return;
  for (const canvas of [...pools.keys()]) if (!canvas.isConnected) dispose(canvas);
  const identity = model.orb?.identity;
  const active = ["axiom", "meridian", "lyra"].includes(identity);
  let pool = pools.get(source);
  if (!pool) { pool = {byId: new Map(), current: null}; pools.set(source, pool); }
  const now = performance.now();
  for (const [id, other] of [...pool.byId]) {
    if (id === identity) continue;
    hide(other);
    if (now - (other.used || 0) > IDLE_MS) { release(other); pool.byId.delete(id); }
  }
  pool.current = active ? identity : null;
  let view = active ? pool.byId.get(identity) : null;
  if (!active) {
    source.style.opacity = identity && identity !== "watcher" ? "0" : "";
    return;
  }
  if (!view) {
    const canvas = document.createElement("canvas");
    canvas.className = "crew-instrument";
    canvas.dataset.identity = identity;
    canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
    canvas.setAttribute("aria-hidden", "true");
    source.parentElement.style.position = "relative";
    source.insertAdjacentElement("afterend", canvas);
    try { view = {canvas, identity, display: createCrewDisplay(canvas, identity)}; }
    catch (error) {
      canvas.remove();
      const message = document.createElement("span");
      message.className = "crew-renderer-error";
      message.style.cssText = "position:absolute;inset:15%;display:grid;place-items:center;text-align:center;font:11px/1.5 Consolas,monospace;color:var(--text,#d8e6ee)";
      message.textContent = `${{axiom:"Axiom",meridian:"Meridian",lyra:"Lyra"}[identity]} display unavailable. Check WebGL / hardware acceleration.`;
      source.insertAdjacentElement("afterend", message);
      pool.byId.set(identity, {canvas, identity, display: null, error: message, used: now});
      source.style.opacity = "0";
      source.setAttribute("aria-label", `${identity} display could not start`);
      window.dispatchEvent(new CustomEvent("crew-renderer-error", {detail: String(error)}));
      return;
    }
    pool.byId.set(identity, view);
  }
  view.used = now;
  if (!view.display) { source.style.opacity = "0"; if (view.error) { view.error.hidden = false; view.error.style.display = "grid"; } return; }
  source.style.opacity = "0"; view.canvas.hidden = false; view.canvas.style.display = "block";
  const visible = options.visible !== false && source.getClientRects().length > 0;
  view.display.setVisible(visible);
  const speech = live.speech;
  const hearing = live.hearing;
  const working = live.working ?? model.orb?.working;
  const vitals = model.vitals || {};
  const state = vitals.danger || vitals.overheating || vitals.low_fuel ? "alert"
    : hearing && ["listening", "opening", "test"].includes(hearing.stage) ? "listening"
    : hearing && ["hearing", "working", "transcribing"].includes(hearing.stage) ? "working"
    : speech ? "speaking" : working ? "working" : vitals.fsd_charging ? "charging" : "idle";
  view.canvas.dataset.state = state;
  view.display.setContext(model);
  view.display.setFocus(model.orb?.focus_movement);
  view.display.setState(state, speech?.level ?? hearing?.level ?? 0, speech ? speech.level ?? 0 : null);
  const accent = model.orb?.accent;
  // The deck panel has its own decorative accent; Theme means the app's
  // selected theme, just as it does in the floating overlay.
  const theme = options.palette?.accent || getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
  const colours = companionColours(identity,accent,theme);
  view.display.setColour(colours.primary,colours.secondary);
  view.display.setReducedMotion(Boolean(options.reducedMotion) || window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  view.display.setMotion(model.orb?.motion !== false);
  view.display.setFrameRate(model.orb?.frame_rate);
  view.display.setActivity(model.orb?.liveliness);
}
window.CrewCompanion = {update, dispose, inspect: source => views.get(source)?.display?.inspect() || null};
window.dispatchEvent(new Event("crew-three-ready"));
window.addEventListener("pagehide", () => { for (const source of [...pools.keys()]) dispose(source); });
