(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "station";
  const byId = (id) => document.getElementById(id);
  const root = byId("station");

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
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
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

  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 260});
})();
