import {createAsterDisplay} from "./aster-3d.js";
import {companionColours} from "./companion-colours.js";

const views = new Map();
function dispose(source) {
  const view = views.get(source);
  if (!view) return;
  view.display?.destroy(); view.canvas.remove(); view.error?.remove(); views.delete(source);
  source.style.opacity = "";
}
function update(source, model = {}, live = {}, options = {}) {
  if (!source) return;
  for (const canvas of views.keys()) if (!canvas.isConnected) dispose(canvas);
  const active = model.orb?.identity === "aster";
  let view = views.get(source);
  if (!active) {
    if (view) { view.display?.setVisible(false); view.canvas.hidden = true; view.canvas.style.display = "none"; if (view.error) { view.error.hidden = true; view.error.style.display = "none"; } }
    source.style.opacity = model.orb?.identity && model.orb.identity !== "watcher" ? "0" : "";
    return;
  }
  if (!view) {
    const canvas = document.createElement("canvas");
    canvas.className = "aster-instrument";
    canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
    canvas.setAttribute("aria-hidden", "true");
    source.parentElement.style.position = "relative";
    source.insertAdjacentElement("afterend", canvas);
    try { view = {canvas, display: createAsterDisplay(canvas)}; }
    catch (error) {
      canvas.remove();
      const message = document.createElement("span");
      message.className = "aster-renderer-error";
      message.style.cssText = "position:absolute;inset:15%;display:grid;place-items:center;text-align:center;font:11px/1.5 Consolas,monospace;color:var(--text,#d8e6ee)";
      message.textContent = "Aster display unavailable. Check WebGL / hardware acceleration.";
      source.insertAdjacentElement("afterend", message);
      views.set(source, {canvas, display: null, error: message});
      source.style.opacity = "0";
      source.setAttribute("aria-label", "Aster's Three.js display could not start");
      window.dispatchEvent(new CustomEvent("aster-renderer-error", {detail: String(error)}));
      return;
    }
    views.set(source, view);
  }
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
  const theme = options.palette?.accent || getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
  const colours = companionColours("aster",accent,theme);
  view.display.setColour(colours.primary,colours.secondary);
  view.display.setReducedMotion(Boolean(options.reducedMotion) || window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  view.display.setMotion(model.orb?.motion !== false);
  view.display.setFrameRate(model.orb?.frame_rate);
  view.display.setActivity(model.orb?.liveliness);
}
window.AsterCompanion = {update, dispose, inspect: source => views.get(source)?.display?.inspect() || null};
window.dispatchEvent(new Event("aster-three-ready"));
window.addEventListener("pagehide", () => { for (const source of views.keys()) dispose(source); });
