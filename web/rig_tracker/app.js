(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "rig-tracker";
  const byId = (id) => document.getElementById(id);
  const root = byId("rigs");
  const NS = "http://www.w3.org/2000/svg";

  const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const distance = (metres) => {
    const m = number(metres);
    return m >= 1000 ? `${(m / 1000).toFixed(m >= 10000 ? 0 : 1)}km` : `${Math.round(m)}m`;
  };
  const age = (at) => {
    const minutes = Math.max(0, Math.floor((Date.now() / 1000 - number(at)) / 60));
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return hours < 48 ? `${hours}h ${minutes % 60}m ago` : `${Math.floor(hours / 24)}d ago`;
  };

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  // A dial: a ring with a needle pointing the way the rig lies (up is
  // straight ahead), or a filled ring when you're at it.
  function dial(rig) {
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 40 40");
    svg.setAttribute("aria-hidden", "true");
    const ring = document.createElementNS(NS, "circle");
    ring.setAttribute("cx", "20"); ring.setAttribute("cy", "20"); ring.setAttribute("r", "15");
    ring.setAttribute("class", "ring");
    svg.appendChild(ring);
    if (!rig.tracked) return svg;
    if (rig.here) {
      const dot = document.createElementNS(NS, "circle");
      dot.setAttribute("cx", "20"); dot.setAttribute("cy", "20"); dot.setAttribute("r", "6");
      dot.setAttribute("class", "here-dot");
      svg.appendChild(dot);
      return svg;
    }
    const needle = document.createElementNS(NS, "path");
    needle.setAttribute("d", "M20 7.5 L23.6 15.5 L20 13.8 L16.4 15.5 Z M20 20 L20 13.8");
    needle.setAttribute("class", "needle");
    needle.setAttribute("transform", `rotate(${number(rig.relative)} 20 20)`);
    const hub = document.createElementNS(NS, "circle");
    hub.setAttribute("cx", "20"); hub.setAttribute("cy", "20"); hub.setAttribute("r", "2.6");
    hub.setAttribute("class", "hub");
    svg.append(needle, hub);
    return svg;
  }

  // A hold: how full it is, never what's in it (that's the Cargo overlay).
  function hold(row) {
    const used = number(row.used), capacity = Math.max(0, number(row.capacity));
    const share = capacity ? Math.min(1, used / capacity) : 0;
    const full = !row.partial && share >= 1, nearly = !row.partial && share >= 0.9;
    const item = node("li", `hold${full ? " full" : nearly ? " nearly" : ""}${row.partial ? " partial" : ""}`);
    const bar = node("span", "bar");
    const fill = node("i");
    fill.style.setProperty("--fill", share.toFixed(3));
    bar.appendChild(fill);
    item.append(node("span", "hold-name", String(row.name || "")), bar,
      node("b", "hold-used", `${row.partial ? "+" : ""}${used} / ${capacity} t`),
      node("small", "hold-free", row.partial ? "THIS TRIP" : full ? "FULL" : `${number(row.free)} FREE`));
    return item;
  }

  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
    VoidCompassOverlay.fitToWindow(root, 420, snapshot.effects || {});
    const model = snapshot.rigs || null;
    root.classList.toggle("empty", !model);
    if (!model) return;
    byId("rigs-body").textContent = String(model.body || "").toUpperCase();
    byId("rigs-count").textContent = `${number(model.tracked)} OUT`;
    byId("rigs-dials").replaceChildren(...(model.slots || []).map((rig) => {
      const item = node("li", `dial${rig.tracked ? "" : " idle"}${rig.next ? " nearest" : ""}${rig.here ? " at" : ""}`);
      item.append(node("span", "slot", `#${rig.slot}`), dial(rig),
        node("b", "distance", rig.tracked ? (rig.here ? "HERE" : distance(rig.distance_m)) : "--"),
        node("small", "age", rig.tracked ? age(rig.at) : ""));
      return item;
    }));
    const order = (model.order || []).map((slot) => `#${slot}`);
    byId("rigs-order").textContent = order.length > 1 ? `COLLECT ▸ ${order.join(" → ")}` : "";
    byId("rigs-order").hidden = order.length < 2;
    const holds = (model.holds || []).filter((row) => number(row.capacity) > 0);
    byId("rigs-holds").replaceChildren(...holds.map(hold));
    byId("rigs-holds").hidden = !holds.length;
    byId("rigs-hint").textContent = String(model.hint || "");
    byId("rigs-hint").hidden = !model.hint;
  }

  function contentHeight() {
    return VoidCompassOverlay.designHeight(root, 130);
  }

  const poller = VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 250});
  // Each rig's time down keeps counting while you stand still.
  setInterval(() => poller?.rerender?.(), 20000);
})();
