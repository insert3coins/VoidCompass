(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "powerplay";
  const suffix = `token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
  const root = document.getElementById("panel");
  const byId = (id) => document.getElementById(id);
  let revision = -1, polling = false, ready = false;
  const set = (id, value, fallback = "—") => { const node = byId(id); if (node) node.textContent = value === null || value === undefined || value === "" ? fallback : String(value); };
  const count = (value) => Number.isFinite(Number(value)) ? Math.max(0, Math.round(Number(value))).toLocaleString() : "—";
  function applyTheme(theme = {}, effects = {}) {
    const mapping = {bg:"bg",panel:"panel",panel_alt:"alt",panel_raised:"raised",border:"border",border_soft:"soft",accent:"accent",orange:"orange",text:"text",muted:"muted",dim:"dim",green:"green",yellow:"yellow",red:"red"};
    for (const [key, css] of Object.entries(mapping)) { const value = String(theme[key] || ""); if (/^#[0-9a-f]{6}$/i.test(value)) document.documentElement.style.setProperty(`--${css}`, value); }
    const scale = Number(effects.text_scale); document.documentElement.style.setProperty("--scale", String(Number.isFinite(scale) ? Math.max(.75, Math.min(2, scale)) : 1));
    const opacity = Number(effects.opacity); document.body.style.opacity = String(Number.isFinite(opacity) ? Math.max(.4, Math.min(1, opacity)) : 1);
    root.classList.toggle("no-crt", !effects.crt); root.classList.toggle("reduced-motion", Boolean(effects.reduced_motion));
  }
  function cycleRemaining(value) {
    const end = Date.parse(value || "");
    if (!Number.isFinite(end)) return "CYCLE TIMER —";
    const seconds = Math.max(0, Math.floor((end - Date.now()) / 1000));
    const days = Math.floor(seconds / 86400), hours = Math.floor(seconds % 86400 / 3600);
    return `CYCLE · ${days}D ${hours}H`;
  }
  function render(snapshot = {}) {
    applyTheme(snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.powerplay || {}, objective = model.objective || {};
    root.classList.toggle("unpledged", !model.pledged);
    set("rank", model.rank === null || model.rank === undefined ? "RANK —" : `RANK ${count(model.rank)}`);
    set("power", String(model.power || "NO ACTIVE PLEDGE").toUpperCase());
    set("merits", model.merits === null || model.merits === undefined ? "MERITS —" : `${count(model.merits)} MERITS`);
    set("cycle-merits", count(model.cycle_merits)); set("collected", `${count(model.cargo_collected)} UNITS`); set("delivered", `${count(model.cargo_delivered)} UNITS`);
    set("system", String(model.system || "SYSTEM UNKNOWN").toUpperCase());
    set("system-state", String(model.system_state || "NO POWERPLAY STATE").toUpperCase());
    set("controller", model.controlling_power ? `CONTROL · ${String(model.controlling_power).toUpperCase()}` : "CONTROL UNKNOWN");
    root.classList.toggle("has-objective", Boolean(objective.title));
    set("objective-title", objective.title || "NO ASSIGNMENT SELECTED");
    set("objective-detail", [objective.kind, objective.commodity, objective.system].filter(Boolean).join(" · ").toUpperCase() || "CREATE ONE IN POWERPLAY OPERATIONS");
    set("objective-progress", objective.title ? `${count(objective.current)} / ${count(objective.target)}` : "—");
    set("cycle-end", cycleRemaining(model.cycle_ends));
  }
  function contentHeight() { return Math.max(180, Math.ceil(root.getBoundingClientRect().height + 2)); }
  async function refresh(nextRevision) { const response = await fetch(`/api/snapshot?${suffix}`, {cache:"no-store"}); if (!response.ok) return; render(await response.json()); await new Promise((resolve) => requestAnimationFrame(resolve)); revision = nextRevision; try { await fetch(`/api/rendered?${suffix}`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision:nextRevision,content_height:contentHeight()})}); if (!ready) { ready = true; await fetch(`/api/ready?${suffix}`, {method:"POST",body:"{}"}); } } catch (_) {} }
  async function poll() { if (polling) return; polling = true; try { const response = await fetch(`/api/health?${suffix}`, {cache:"no-store"}); if (response.ok) { const next = Number((await response.json()).revision); if (Number.isFinite(next) && next !== revision) await refresh(next); } } catch (_) {} finally { polling = false; } }
  poll(); window.setInterval(poll, 300);
})();
