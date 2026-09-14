(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "powerplay";
  const root = document.getElementById("panel");
  const byId = (id) => document.getElementById(id);
  const set = (id, value, fallback = "—") => { const node = byId(id); if (node) node.textContent = value === null || value === undefined || value === "" ? fallback : String(value); };
  const count = (value) => Number.isFinite(Number(value)) ? Math.max(0, Math.round(Number(value))).toLocaleString() : "—";
  function cycleRemaining(value) {
    const end = Date.parse(value || "");
    if (!Number.isFinite(end)) return "CYCLE TIMER —";
    const seconds = Math.max(0, Math.floor((end - Date.now()) / 1000));
    const days = Math.floor(seconds / 86400), hours = Math.floor(seconds % 86400 / 3600);
    return `CYCLE · ${days}D ${hours}H`;
  }
  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
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
  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 300});
})();
