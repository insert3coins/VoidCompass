(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "planet-materials";
  const root = document.getElementById("panel");
  const byId = (id) => document.getElementById(id);
  const SITE_PAGE_MS = 5000;
  const siteState = {scope: "", page: 0, pages: 1, pageSize: 2, rows: [], pinned: null, total: 0, timer: null};

  function node(tag, className = "", value = "") { const element = document.createElement(tag); if (className) element.className = className; if (value !== "") element.textContent = String(value); return element; }
  function set(id, value, fallback = "—") { const element = byId(id); if (element) element.textContent = value === null || value === undefined || value === "" ? fallback : String(value); }
  function number(value) { if (value === null || value === undefined || value === "") return null; const parsed = Number(value); return Number.isFinite(parsed) ? parsed : null; }
  function distance(value) { const metres = number(value); if (metres === null) return "DISTANCE —"; if (metres >= 1000) return `${(metres / 1000).toFixed(metres >= 100000 ? 0 : 1)} KM`; return `${Math.round(metres)} M`; }
  function materialRow(item, maximum) {
    const row = node("article", item.rare ? "rare" : "");
    row.appendChild(node("strong", "", item.name || "Unknown"));
    const rail = node("i", "rail"), fill = node("b");
    fill.style.setProperty("--fill", `${Math.max(1, Math.min(100, (number(item.percent) || 0) * 100 / Math.max(1, maximum)))}%`);
    rail.appendChild(fill);
    row.appendChild(node("span", "", `${(number(item.percent) || 0).toFixed(2)}%`));
    row.appendChild(rail);
    return row;
  }
  function estimateRow(item) {
    const row = node("article", "estimate");
    row.appendChild(node("strong", "", item.name || "Unknown"));
    row.appendChild(node("span", "", `${(number(item.percent) || 0).toFixed(1)}% · ${Math.round(number(item.median) || 0).toLocaleString()} CR`));
    return row;
  }
  function siteRow(site, targetId) {
    const active = targetId !== null && targetId !== undefined && String(targetId) === String(site.id);
    const row = node("article", active ? "target-site" : "");
    row.dataset.siteId = String(site.id);
    const copy = node("div"); copy.appendChild(node("strong", "", site.name || "Surface site"));
    const logged = Array.isArray(site.materials) ? site.materials : [];
    const materials = `${logged.slice(0, 3).join(" · ")}${logged.length > 3 ? ` · +${logged.length - 3}` : ""}`;
    copy.appendChild(node("span", "", materials || "No field materials logged")); row.appendChild(copy);
    const meta = node("div", "site-meta");
    if (site.tons_left) meta.appendChild(node("b", "", String(site.tons_left).toUpperCase()));
    else if (site.amount || site.density) meta.appendChild(node("b", "", [site.amount,site.density].filter(Boolean).join(" · ").toUpperCase()));
    meta.appendChild(node("small", "", distance(site.distance_m))); row.appendChild(meta);
    return row;
  }
  function renderSitePage() {
    const host = byId("site-list"); host.replaceChildren();
    if (siteState.pinned) host.appendChild(siteRow(siteState.pinned, siteState.pinned.id));
    const first = siteState.page * siteState.pageSize;
    siteState.rows.slice(first, first + siteState.pageSize).forEach((site) => host.appendChild(siteRow(site, null)));
    if (!siteState.total) host.appendChild(node("div", "empty", "NO SAVED SITES ON THIS BODY"));
    set("site-count", `${siteState.total} SITE${siteState.total === 1 ? "" : "S"}${siteState.pages > 1 ? ` · PAGE ${siteState.page + 1}/${siteState.pages}` : ""}`);
  }
  function nextSitePage() {
    if (siteState.pages < 2) return;
    siteState.page = (siteState.page + 1) % siteState.pages;
    renderSitePage();
  }
  function renderSites(sites, target, model, textScale) {
    const targetId = target.active && target.site_id !== null && target.site_id !== undefined ? String(target.site_id) : null;
    const pinned = targetId === null ? null : sites.find((site) => String(site.id) === targetId) || null;
    const rows = pinned ? sites.filter((site) => site !== pinned) : sites;
    const pageSize = textScale >= 1.6 ? 1 : 2;
    const scope = `${model.system || ""}|${model.body || ""}|${targetId || ""}|${pageSize}|${sites.map((site) => String(site.id)).sort().join(",")}`;
    if (scope !== siteState.scope) { siteState.scope = scope; siteState.page = 0; }
    siteState.rows = rows;
    siteState.pinned = pinned;
    siteState.pageSize = pageSize;
    siteState.pages = Math.max(1, Math.ceil(rows.length / pageSize));
    siteState.page = Math.min(siteState.page, siteState.pages - 1);
    siteState.total = sites.length;
    renderSitePage();
    if (siteState.pages > 1 && !siteState.timer) siteState.timer = window.setInterval(nextSitePage, SITE_PAGE_MS);
    else if (siteState.pages === 1 && siteState.timer) { window.clearInterval(siteState.timer); siteState.timer = null; }
  }
  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.planet_materials || {}, details = model.details || {};
    const materials = Array.isArray(model.materials) ? model.materials : [];
    const bestMaterials = Array.isArray(model.best_materials) ? model.best_materials : [];
    const sites = Array.isArray(model.sites) ? model.sites : [];
    const position = model.position || null, target = model.target || {};
    const textScale = Math.max(.75, Math.min(2, number((snapshot.effects || {}).text_scale) || 1));
    root.classList.toggle("rhino", Boolean(model.rhino_active));
    root.classList.toggle("large-type", textScale >= 1.6);
    set("mode", model.rhino_active ? "RHINO FIELD OPS" : model.on_planet ? "SURFACE FIX" : "ORBITAL INTEL");
    set("system", String(model.system || "SYSTEM UNKNOWN").toUpperCase());
    set("body", model.short_body || model.body, "NO BODY LOCK");
    set("body-class", `${details.class || "Awaiting planetary data"}${details.landable ? " · LANDABLE" : ""}`);
    set("mining-count", Math.max(0, Math.round(number(details.mining_locations) || 0)));
    const facts = byId("facts"); facts.replaceChildren();
    const factRows = [
      ["GRAVITY", number(details.gravity) === null ? "—" : `${number(details.gravity).toFixed(2)} G`],
      ["TEMPERATURE", number(details.temperature) === null ? "—" : `${Math.round(number(details.temperature))} K`],
      ["VOLCANISM", details.volcanism || "None detected"],
      [`GROUND${details.ground_sample ? ` · ${details.ground_sample} LOC` : ""}`, details.ground || "Unclassified"],
    ];
    factRows.forEach(([label, value]) => { const item = node("div"); item.appendChild(node("small", "", label)); item.appendChild(node("strong", "", value)); facts.appendChild(item); });
    set("material-count", `${materials.length} MATERIAL${materials.length === 1 ? "" : "S"}`);
    const materialHost = byId("materials"); materialHost.replaceChildren();
    const maximum = Math.max(1, ...materials.map((item) => number(item.percent) || 0));
    if (materials.length) materials.forEach((item) => materialHost.appendChild(materialRow(item, maximum)));
    else materialHost.appendChild(node("div", "empty", "NO SCAN.MATERIALS DATA FOR THIS BODY"));
    const valueHost = byId("best-materials"); valueHost.replaceChildren();
    if (bestMaterials.length) bestMaterials.forEach((item) => valueHost.appendChild(estimateRow(item)));
    else valueHost.appendChild(node("div", "empty", "NO MATCHING RHINO GROUND DATA"));
    renderSites(sites, target, model, textScale);
    if (position) {
      const heading = number(position.heading);
      set("position", `${number(position.latitude).toFixed(4)}° / ${number(position.longitude).toFixed(4)}°${heading === null ? "" : ` · HDG ${String(Math.round(heading)).padStart(3, "0")}°`}`);
    } else set("position", "NO SURFACE FIX");
    set("target", target.active ? `COMPASS · ${target.label || "SURFACE SITE"}` : "NO COMPASS TARGET");
  }
  function contentHeight() { return Math.max(190, Math.ceil(root.getBoundingClientRect().height + 2)); }
  window.VoidCompassPlanetMaterials = Object.freeze({render, nextSitePage, getState: () => ({page: siteState.page, pages: siteState.pages, total: siteState.total, pinnedId: siteState.pinned?.id ?? null})});
  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 260});
})();
