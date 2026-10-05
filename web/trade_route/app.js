(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "trade-route";
  const dom = Object.fromEntries(["route", "content", "route-tag", "route-title", "route-place", "route-warnings", "route-figures"]
    .map((id) => [id, document.getElementById(id)]));

  const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const credits = (value) => {
    const v = number(value), abs = Math.abs(v);
    return abs >= 1e9 ? `${(v / 1e9).toFixed(2)}B` : abs >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : abs >= 1e3 ? `${(v / 1e3).toFixed(0)}K` : `${Math.round(v)}`;
  };
  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }
  function figure(label, value) {
    const span = node("span");
    span.append(node("b", "", `${label} `), String(value));
    return span;
  }

  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(dom.route, snapshot.theme || {}, snapshot.effects || {});
    const step = snapshot.route || null;
    dom.route.classList.toggle("empty", !step);
    if (!step) return;
    dom.route.classList.toggle("done", Boolean(step.done));
    dom.route.classList.toggle("sell", step.phase === "sell");
    dom.route.classList.toggle("here", Boolean(step.here));
    if (step.done) {
      dom["route-tag"].textContent = "DONE";
      dom["route-title"].textContent = "ROUTE COMPLETE";
      dom["route-place"].replaceChildren(node("span", "", `${credits(step.profit)} CR PROFIT`));
      dom["route-warnings"].replaceChildren();
      dom["route-figures"].replaceChildren(figure("HOPS", step.hops));
      return;
    }
    dom["route-tag"].textContent = step.phase === "sell" ? "SELL" : "BUY";
    dom["route-title"].textContent = String(step.action || "").toUpperCase();
    const place = node("span", "", `${step.here ? "▸ HERE · " : "▸ "}${String(step.station || "").toUpperCase()}`);
    place.appendChild(node("small", "", `${String(step.system || "").toUpperCase()}${step.phase === "sell" && step.distance ? ` · ${number(step.distance).toFixed(1)} LY` : ""}`));
    dom["route-place"].replaceChildren(place);
    dom["route-warnings"].replaceChildren(...(step.warnings || []).map((text) => node("span", "", `▲ ${String(text).toUpperCase()}`)));
    dom["route-figures"].replaceChildren(figure("HOP", `${step.hop}/${step.hops}`), figure("PLANNED", `${credits(step.expected)} CR`),
      figure("MADE", `${credits(step.profit)} CR`));
  }

  function contentHeight() {
    return Math.ceil(dom.content.getBoundingClientRect().height + 2);
  }

  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 250});
})();
