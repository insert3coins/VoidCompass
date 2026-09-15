(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "planet-materials";
  const root = document.getElementById("panel");
  const byId = (id) => document.getElementById(id);

  function node(tag, className = "", value = "") { const element = document.createElement(tag); if (className) element.className = className; if (value !== "") element.textContent = String(value); return element; }
  function set(id, value, fallback = "—") { const element = byId(id); if (element) element.textContent = value === null || value === undefined || value === "" ? fallback : String(value); }
  function number(value) { if (value === null || value === undefined || value === "") return null; const parsed = Number(value); return Number.isFinite(parsed) ? parsed : null; }
  function distance(value) { const metres = number(value); if (metres === null) return "DISTANCE —"; if (metres >= 1000) return `${(metres / 1000).toFixed(metres >= 100000 ? 0 : 1)} KM`; return `${Math.round(metres)} M`; }
  function materialRow(item, maximum) {
    const row = node("article", item.rare ? "rare" : "");
    row.appendChild(node("strong", "", item.name || "Unknown"));
    const rail = node("i", "rail"), fill = node("b");
    fill.style.setProperty("--fill", `${Math.max(1, Math.min(100, (number(item.percent) || 0) * 100 / Math.max(1, maximum)))}%`);
    rail.appendChild(fill); row.appendChild(rail);
    row.appendChild(node("span", "", `${(number(item.percent) || 0).toFixed(2)}%`));
    return row;
  }
  function siteRow(site, targetId) {
    const active = targetId !== null && targetId !== undefined && String(targetId) === String(site.id);
    const row = node("article", active ? "target-site" : "");
    const copy = node("div"); copy.appendChild(node("strong", "", site.name || "Surface site"));
    const materials = Array.isArray(site.materials) ? site.materials.slice(0, 4).join(" · ") : "";
    copy.appendChild(node("span", "", materials || "No field materials logged")); row.appendChild(copy);
    const meta = node("div", "site-meta");
    if (site.tons_left) meta.appendChild(node("b", "", String(site.tons_left).toUpperCase()));
    else if (site.amount || site.density) meta.appendChild(node("b", "", [site.amount,site.density].filter(Boolean).join(" · ").toUpperCase()));
    meta.appendChild(node("small", "", distance(site.distance_m))); row.appendChild(meta);
    return row;
  }
  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.planet_materials || {}, details = model.details || {};
    const materials = Array.isArray(model.materials) ? model.materials : [];
    const bestMaterials = Array.isArray(model.best_materials) ? model.best_materials : [];
    const sites = Array.isArray(model.sites) ? model.sites.slice(0, 4) : [];
    const position = model.position || null, target = model.target || {};
    root.classList.toggle("rhino", Boolean(model.rhino_active));
    set("mode", model.rhino_active ? "RHINO FIELD OPS" : model.on_planet ? "SURFACE FIX" : "ORBITAL INTEL");
    set("system", String(model.system || "SYSTEM UNKNOWN").toUpperCase());
    set("body", model.short_body || model.body, "NO BODY LOCK");
    set("body-class", details.class || "Awaiting planetary data");
    set("mining-count", Math.max(0, Math.round(number(details.mining_locations) || 0)));
    const facts = byId("facts"); facts.replaceChildren();
    const factRows = [
      ["GRAVITY", number(details.gravity) === null ? "—" : `${number(details.gravity).toFixed(2)} G`],
      ["GROUND", details.ground || "Unclassified"],
      ["SAMPLE", details.ground_sample ? `${details.ground_sample} LOCATIONS` : "UNMEASURED"],
      ["SURFACE", details.landable ? "LANDABLE" : "NOT LANDABLE"],
    ];
    factRows.forEach(([label, value]) => { const item = node("div"); item.appendChild(node("small", "", label)); item.appendChild(node("strong", "", value)); facts.appendChild(item); });
    set("material-count", `${materials.length} MATERIAL${materials.length === 1 ? "" : "S"}`);
    const materialHost = byId("materials"); materialHost.replaceChildren();
    const maximum = Math.max(1, ...materials.map((item) => number(item.percent) || 0));
    if (materials.length) materials.forEach((item) => materialHost.appendChild(materialRow(item, maximum)));
    else materialHost.appendChild(node("div", "empty", "NO SCAN.MATERIALS DATA FOR THIS BODY"));
    const valueHost = byId("best-materials"); valueHost.replaceChildren();
    const bestMaximum = Math.max(1, ...bestMaterials.map((item) => number(item.percent) || 0));
    if (bestMaterials.length) bestMaterials.forEach((item) => {
      const row = materialRow(item, bestMaximum);
      row.querySelector("span").textContent = `${(number(item.percent)||0).toFixed(1)}% · ${Math.round(number(item.median)||0).toLocaleString()} CR`;
      valueHost.appendChild(row);
    });
    else valueHost.appendChild(node("div", "empty", "NO MATCHING RHINO GROUND DATA"));
    set("site-count", `${Math.max(0, Math.round(number(model.site_count) || 0))} SITE${Number(model.site_count) === 1 ? "" : "S"}`);
    const siteHost = byId("site-list"); siteHost.replaceChildren();
    if (sites.length) sites.forEach((site) => siteHost.appendChild(siteRow(site, target.site_id)));
    else siteHost.appendChild(node("div", "empty", "NO SAVED SITES ON THIS BODY"));
    if (position) {
      const heading = number(position.heading);
      set("position", `${number(position.latitude).toFixed(4)}° / ${number(position.longitude).toFixed(4)}°${heading === null ? "" : ` · HDG ${String(Math.round(heading)).padStart(3, "0")}°`}`);
    } else set("position", "NO SURFACE FIX");
    set("target", target.active ? `COMPASS · ${target.label || "SURFACE SITE"}` : "NO COMPASS TARGET");
  }
  function contentHeight() { return Math.max(190, Math.ceil(root.getBoundingClientRect().height + 2)); }
  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 260});
})();
