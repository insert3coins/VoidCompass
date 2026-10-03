(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "colony-needs";
  const dom = Object.fromEntries([
    "needs", "content", "needs-tag", "needs-title", "needs-sub", "needs-projects", "needs-warnings",
    "needs-complete", "needs-table", "needs-rows", "needs-footer", "head-fc", "head-ship",
  ].map((id) => [id, document.getElementById(id)]));

  const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const count = (value) => number(value).toLocaleString("en-GB");
  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  function needRow(row, columns) {
    const item = node("div", `need-row ${row.state || ""}${row.almost ? " almost" : ""}`);
    item.dataset.id = String(row.id || "");
    const mark = row.state === "pending" ? ["pending", "►"] : row.check === "ship" ? ["ship", "✓"] : row.check === "fc" ? ["fc", "✓"] : null;
    if (mark) item.appendChild(node("i", `mark ${mark[0]}`, mark[1]));
    const name = node("span", "name");
    if (row.assigned) name.appendChild(node("i", `pin ${row.assigned}`, row.assigned === "me" ? "◆" : "⊘"));
    name.append(String(row.name || row.id || ""));
    if (row.warn) name.appendChild(node("span", "warn", " ▲"));
    if (row.almost) name.append(" ⚑");
    item.appendChild(name);
    item.appendChild(node("span", "num need", row.state === "pending" ? "…" : count(row.need)));
    if (columns.inline) {
      // One HAVE column: the ship's count, else the carriers' (dimmer).
      const ship = number(row.ship);
      const fc = number(row.fc);
      const tone = ship ? "" : `fc-inline ${fc >= number(row.need) ? "covered" : fc ? "short" : "none"}`;
      item.appendChild(node("span", `num ship ${tone}`, row.state === "pending" ? "…" : ship ? count(ship) : fc ? count(fc) : ""));
      return item;
    }
    if (columns.fc) {
      let text = count(row.fc);
      let tone = number(row.fc) >= number(row.need) ? "covered" : number(row.fc) ? "short" : "none";
      if (columns.fc_delta) {
        const delta = number(row.fc_delta);
        text = `${delta > 0 ? "+" : ""}${count(delta)}`;
        tone = delta >= 0 ? "covered" : "short";
      }
      item.appendChild(node("span", `num fc ${tone}`, row.state === "pending" ? "…" : text));
    }
    if (columns.ship) item.appendChild(node("span", "num ship", number(row.ship) ? count(row.ship) : ""));
    return item;
  }

  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(dom.needs, snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.needs || null;
    dom.needs.classList.toggle("empty", !model);
    if (!model) return;
    dom.needs.classList.toggle("at-site", Boolean(model.at_site));
    dom.needs.classList.toggle("complete", Boolean(model.complete));
    dom["needs-tag"].textContent = model.complete ? "DONE" : model.at_site ? "SITE" : "BUILD";
    dom["needs-title"].textContent = String(model.header || "CONSTRUCTION").toUpperCase();
    dom["needs-complete"].hidden = !model.complete;
    dom["needs-table"].hidden = Boolean(model.complete);
    dom["needs-footer"].hidden = Boolean(model.complete);
    dom["needs-sub"].hidden = !model.subheader;
    dom["needs-sub"].textContent = model.subheader ? `▸ ${String(model.subheader).toUpperCase()}` : "";
    const projects = Array.isArray(model.projects) ? model.projects : [];
    dom["needs-projects"].hidden = !projects.length;
    dom["needs-projects"].replaceChildren(...projects.map((name) => node("li", "", name)));
    dom["needs-warnings"].replaceChildren(...(model.warnings || []).map((text) => node("span", "", `▲ ${String(text).toUpperCase()}`)));
    if (model.complete) return;

    const columns = model.columns || {};
    dom["needs-table"].classList.toggle("no-fc", !columns.fc || Boolean(columns.inline));
    dom["needs-table"].classList.toggle("no-ship", !columns.ship);
    dom["head-fc"].textContent = columns.fc_delta ? "FC Δ" : `${number(columns.fc_count)} FC`;
    dom["head-ship"].textContent = columns.fc && !columns.inline ? "SHIP" : "HAVE";
    const rows = [];
    for (const group of model.groups || []) {
      if (group.name) {
        const label = node("div", `need-group${group.collapsed ? " covered" : ""}`, String(group.name).toUpperCase());
        if (group.collapsed) label.append(" ✓");
        rows.push(label);
      }
      for (const row of group.rows || []) rows.push(needRow(row, columns));
    }
    dom["needs-rows"].replaceChildren(...rows);

    const footer = [];
    const remaining = node("span", "", `▸ ${count(model.remaining)} REMAINING`);
    if (model.trips !== null && model.trips !== undefined) remaining.append(`  ▸ ${count(model.trips)} TRIPS IN THIS SHIP`);
    footer.push(remaining);
    if (model.carriers) {
      const carriers = node("span", "carriers", `▸ ${number(model.carriers.count)} FC: ${count(model.carriers.deficit)} DEFICIT`);
      if (model.carriers.trips !== null && model.carriers.trips !== undefined) carriers.append(`  ▸ ${count(model.carriers.trips)} TRIPS`);
      carriers.appendChild(node("small", "", (model.carriers.names || []).join("   ")));
      footer.push(carriers);
    }
    if (model.pending) footer.push(node("span", "updating", "▸ UPDATING…"));
    if (model.pinned) footer.push(node("span", "legend", "◆ ASSIGNED TO YOU   ⊘ ASSIGNED TO OTHERS"));
    dom["needs-footer"].replaceChildren(...footer);
  }

  function contentHeight() {
    return Math.ceil(dom.content.getBoundingClientRect().height + 2);
  }

  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 250});
})();
