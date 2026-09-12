(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "planet-materials";
  const suffix = `token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
  const root = document.getElementById("panel");
  const byId = (id) => document.getElementById(id);
  let revision = -1, polling = false, ready = false;

  function node(tag, className = "", value = "") { const element = document.createElement(tag); if (className) element.className = className; if (value !== "") element.textContent = String(value); return element; }
  function set(id, value, fallback = "—") { const element = byId(id); if (element) element.textContent = value === null || value === undefined || value === "" ? fallback : String(value); }
  function number(value) { if (value === null || value === undefined || value === "") return null; const parsed = Number(value); return Number.isFinite(parsed) ? parsed : null; }
  function applyTheme(theme = {}, effects = {}) {
    const mapping = {bg:"bg",panel:"panel",panel_alt:"alt",panel_raised:"raised",border:"border",border_soft:"soft",accent:"accent",orange:"orange",text:"text",muted:"muted",dim:"dim",green:"green",yellow:"yellow",red:"red"};
    for (const [key, css] of Object.entries(mapping)) { const value = String(theme[key] || ""); if (/^#[0-9a-f]{6}$/i.test(value)) document.documentElement.style.setProperty(`--${css}`, value); }
    const scale = Number(effects.text_scale); document.documentElement.style.setProperty("--scale", String(Number.isFinite(scale) ? Math.max(.75, Math.min(2, scale)) : 1));
    const opacity = Number(effects.opacity); document.body.style.opacity = String(Number.isFinite(opacity) ? Math.max(.4, Math.min(1, opacity)) : 1);
    root.classList.toggle("no-crt", !effects.crt); root.classList.toggle("reduced-motion", Boolean(effects.reduced_motion));
  }
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
    if (site.density) meta.appendChild(node("b", "", String(site.density).toUpperCase()));
    meta.appendChild(node("small", "", distance(site.distance_m))); row.appendChild(meta);
    return row;
  }
  function render(snapshot = {}) {
    applyTheme(snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.planet_materials || {}, details = model.details || {};
    const materials = Array.isArray(model.materials) ? model.materials : [];
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
      ["VOLCANISM", details.volcanism || "None detected"],
      ["SURFACE", details.landable ? "LANDABLE" : "NOT LANDABLE"],
    ];
    factRows.forEach(([label, value]) => { const item = node("div"); item.appendChild(node("small", "", label)); item.appendChild(node("strong", "", value)); facts.appendChild(item); });
    set("material-count", `${materials.length} MATERIAL${materials.length === 1 ? "" : "S"}`);
    const materialHost = byId("materials"); materialHost.replaceChildren();
    const maximum = Math.max(1, ...materials.map((item) => number(item.percent) || 0));
    if (materials.length) materials.forEach((item) => materialHost.appendChild(materialRow(item, maximum)));
    else materialHost.appendChild(node("div", "empty", "NO SCAN.MATERIALS DATA FOR THIS BODY"));
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
  async function refresh(nextRevision) { const response = await fetch(`/api/snapshot?${suffix}`, {cache:"no-store"}); if (!response.ok) return; render(await response.json()); await new Promise((resolve) => requestAnimationFrame(resolve)); revision = nextRevision; try { await fetch(`/api/rendered?${suffix}`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision:nextRevision,content_height:contentHeight()})}); if (!ready) { ready = true; await fetch(`/api/ready?${suffix}`, {method:"POST",body:"{}"}); } } catch (_) {} }
  async function poll() { if (polling) return; polling = true; try { const response = await fetch(`/api/health?${suffix}`, {cache:"no-store"}); if (response.ok) { const next = Number((await response.json()).revision); if (Number.isFinite(next) && next !== revision) await refresh(next); } } catch (_) {} finally { polling = false; } }
  poll(); window.setInterval(poll, 260);
})();
