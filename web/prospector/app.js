(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "prospector";
  const root = document.getElementById("prospector");
  const byId = (id) => document.getElementById(id);

  function node(tag, className = "", text = "") { const element = document.createElement(tag); if (className) element.className = className; if (text !== "") element.textContent = String(text); return element; }
  function set(id, value, fallback = "—") { const element = byId(id); if (element) element.textContent = value === null || value === undefined || value === "" ? fallback : String(value); }
  function number(value, fallback = 0) { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : fallback; }
  function tone(value) { const allowed = new Set(["green","yellow","red","orange","accent","dim","muted","text"]); const result = String(value || "text").toLowerCase(); return allowed.has(result) ? result : "text"; }

  function materialRow(item, maximum, coreName) {
    const isCore = Boolean(coreName && String(item.name || "").toLowerCase() === String(coreName).toLowerCase());
    const row = node("article", isCore ? "core-material" : "");
    row.appendChild(node("strong", "", item.name || "Unknown"));
    const rail = node("i", "material-rail"); const fill = node("b"); fill.style.setProperty("--fill", `${Math.max(1, Math.min(100, number(item.proportion) * 100 / Math.max(1, maximum)))}%`); rail.appendChild(fill); row.appendChild(rail);
    row.appendChild(node("span", "", `${number(item.proportion).toFixed(1)}%`));
    return row;
  }

  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.prospector || {};
    const materials = Array.isArray(model.materials) ? model.materials.slice(0, 10) : [];
    const refined = Array.isArray(model.refined) ? model.refined : [];
    const remaining = model.remaining === null || model.remaining === undefined ? null : Math.max(0, Math.min(100, number(model.remaining)));
    const core = String(model.core_material || "");
    root.classList.toggle("has-core", Boolean(core)); root.dataset.contentTone = tone(model.content_tone);
    set("content-badge", core ? "CORE DETECTED" : `${model.content_label || "UNKNOWN"} CONTENT`);
    set("mining-type", model.mining_type, "Asteroid");
    set("remaining-text", remaining === null ? "REMAINING UNKNOWN" : `${remaining.toFixed(1)}% OF DEPOSIT REMAINS`);
    set("remaining-value", remaining === null ? "—" : `${remaining.toFixed(1)}%`);
    byId("rock-glyph").style.setProperty("--remaining", `${remaining === null ? 0 : remaining}%`);
    byId("core").hidden = !core; set("core-material", core, "UNKNOWN");
    set("material-count", `${materials.length} SIGNAL${materials.length === 1 ? "" : "S"}`);
    const maximum = Math.max(1, ...materials.map((item) => number(item.proportion)));
    const materialHost = byId("materials"); materialHost.replaceChildren();
    if (materials.length) materials.forEach((item) => materialHost.appendChild(materialRow(item, maximum, core)));
    else materialHost.appendChild(node("div", "empty", "NO EXTRACTABLE MATERIALS REPORTED"));
    set("refined-total", number(model.refined_total) > 0 ? `${Math.round(number(model.refined_total))} T REFINED` : "AWAITING EVENTS");
    const refinedHost = byId("refined"); refinedHost.replaceChildren();
    if (refined.length) refined.forEach((item) => { const chip = node("span"); chip.appendChild(node("b", "", `${Math.round(number(item.tonnes))} T`)); chip.appendChild(node("i", "", item.name || "Unknown")); refinedHost.appendChild(chip); });
    else refinedHost.appendChild(node("span", "empty-refined", "Refinery events for this asteroid will appear here"));
    set("analysis-state", core ? "MOTHERLODE LOCK" : materials.length ? "COMPOSITION LOCK" : "PROSPECTOR LOCK");
  }

  function contentHeight() { return Math.max(180, Math.ceil(root.getBoundingClientRect().height + 2)); }
  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 260});
})();
