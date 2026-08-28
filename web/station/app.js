(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "station";
  const suffix = `token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
  const byId = (id) => document.getElementById(id);
  const root = byId("station");
  let revision = -1;
  let polling = false;
  let ready = false;

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  function set(id, value, fallback = "—") {
    const element = byId(id);
    if (element) element.textContent = value === null || value === undefined || value === "" ? fallback : String(value);
  }

  function applyTheme(theme = {}, effects = {}) {
    const mapping = {
      bg: "bg", panel: "panel", panel_alt: "alt", panel_raised: "raised",
      border: "border", border_soft: "soft", accent: "accent",
      orange: "orange", text: "text", muted: "muted", dim: "dim",
      green: "green", yellow: "yellow", red: "red",
    };
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

  function availabilityChip(service) {
    const online = Boolean(service?.available);
    const chip = node("span", `service-chip ${online ? "online" : "offline"}`);
    chip.appendChild(node("i", "", online ? "●" : "○"));
    chip.appendChild(node("b", "", service?.label || "UNKNOWN"));
    return chip;
  }

  function renderServices(id, rows) {
    const host = byId(id);
    host.replaceChildren(...rows.map(availabilityChip));
  }

  function renderMetrics(model, coreOnline, explorerOnline) {
    const values = [
      ["ARRIVAL", model.distance || "LOCAL"],
      ["PAD GRID", model.pads || "NOT REPORTED"],
      ["FLIGHT", `${coreOnline}/4 ONLINE`],
      ["EXPLORER", `${explorerOnline}/4 ONLINE`],
    ];
    byId("metrics").replaceChildren(...values.map(([label, value]) => {
      const metric = node("article");
      metric.appendChild(node("small", "", label));
      metric.appendChild(node("strong", "", value));
      return metric;
    }));
  }

  function renderData(rows) {
    const host = byId("data-rows");
    host.replaceChildren();
    if (!rows.length) {
      host.appendChild(node("p", "data-empty", "NO UNSOLD EXPLORATION OR BIOLOGY DATA REPORTED"));
      set("data-count", "NONE REPORTED");
      return;
    }
    const readyCount = rows.filter((row) => row.available).length;
    set("data-count", `${readyCount}/${rows.length} SALE READY`);
    for (const entry of rows) {
      const row = node("article", entry.available ? "ready" : "unavailable");
      const copy = node("div");
      copy.appendChild(node("strong", "", entry.label || "EXPLORATION DATA"));
      copy.appendChild(node("span", "", entry.available ? `${entry.service || "SERVICE"} ONLINE` : `${entry.service || "SERVICE"} UNAVAILABLE`));
      row.appendChild(copy);
      row.appendChild(node("b", "", entry.value || "—"));
      host.appendChild(row);
    }
  }

  function renderLocal(model) {
    const facts = [];
    if (model.economies) facts.push(["ECONOMY", model.economies]);
    if (model.authority) facts.push(["AUTHORITY", model.authority]);
    const host = byId("local-facts");
    host.replaceChildren(...(facts.length ? facts : [["DOSSIER", "NO ECONOMY OR AUTHORITY DETAILS REPORTED"]]).map(([label, value]) => {
      const row = node("div");
      row.appendChild(node("small", "", label));
      row.appendChild(node("span", "", value));
      return row;
    }));
    const specialists = Array.isArray(model.special_services) ? model.special_services : [];
    set("special-count", specialists.length ? `${specialists.length} SPECIALIST${specialists.length === 1 ? "" : "S"}` : "PORT DOSSIER");
    byId("specialists").replaceChildren(...specialists.map((label) => node("span", "", label)));
  }

  function render(snapshot = {}) {
    applyTheme(snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.station || {};
    const core = Array.isArray(model.core_services) ? model.core_services : [];
    const explorer = Array.isArray(model.exploration_services) ? model.exploration_services : [];
    const coreOnline = core.filter((row) => row.available).length;
    const explorerOnline = explorer.filter((row) => row.available).length;
    root.classList.toggle("carrier", Boolean(model.is_personal_carrier));
    set("badge", model.badge || "DOCKED");
    set("station-type", model.type || "STATION");
    set("station-name", String(model.station || "UNKNOWN STATION").toUpperCase());
    set("station-location", String(model.system || "UNKNOWN SYSTEM").toUpperCase());
    set("link-state", model.is_personal_carrier ? "CARRIER" : "LINKED");
    set("core-count", `${coreOnline}/${core.length || 4}`);
    set("explorer-count", `${explorerOnline}/${explorer.length || 4}`);
    renderMetrics(model, coreOnline, explorerOnline);
    renderServices("core-services", core);
    renderServices("explorer-services", explorer);
    renderData(Array.isArray(model.data_rows) ? model.data_rows : []);
    renderLocal(model);
    set("footer-summary", `${coreOnline + explorerOnline}/${core.length + explorer.length || 8} SERVICES ONLINE`);
  }

  function contentHeight() {
    return Math.max(330, Math.ceil(root.getBoundingClientRect().height + 2));
  }

  async function refresh(nextRevision) {
    const response = await fetch(`/api/snapshot?${suffix}`, {cache: "no-store"});
    if (!response.ok) return;
    render(await response.json());
    await new Promise((resolve) => requestAnimationFrame(resolve));
    revision = nextRevision;
    try {
      await fetch(`/api/rendered?${suffix}`, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({revision: nextRevision, content_height: contentHeight()}),
      });
      if (!ready) {
        ready = true;
        await fetch(`/api/ready?${suffix}`, {method: "POST", body: "{}"});
      }
    } catch (_) {}
  }

  async function poll() {
    if (polling) return;
    polling = true;
    try {
      const response = await fetch(`/api/health?${suffix}`, {cache: "no-store"});
      if (response.ok) {
        const next = Number((await response.json()).revision);
        if (Number.isFinite(next) && next !== revision) await refresh(next);
      }
    } catch (_) {
    } finally {
      polling = false;
    }
  }

  poll();
  window.setInterval(poll, 260);
})();
