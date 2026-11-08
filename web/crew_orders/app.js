(() => {
  "use strict";
  // Crew Orders (5.7.7): every order in the cockpit, the one waiting for your
  // answer first, then the campaign, then the rest, each in its officer's colour.
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "crew-orders";
  const dom = Object.fromEntries(["orders", "content", "orders-list"].map((id) => [id, document.getElementById(id)]));
  const OFFICERS = ["watcher", "aster", "axiom", "meridian", "lyra"];
  // The window's design size (html_orders_overlay): fit to it, report height in its units (overlayfix.md).
  const DESIGN_WIDTH = 360, MIN_HEIGHT = 90;

  const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
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

  function block(order, keys) {
    const officer = OFFICERS.includes(order.officer) ? order.officer : "watcher";
    const card = node("section", `order by-${officer}${order.state === "offer" ? " offer" : ""}`);
    const head = node("header", "notice");
    head.append(node("span", "notice-tag", String(order.tag || "ORDER")), node("strong", "orders-title", String(order.title || "").toUpperCase()));
    const from = node("div", "orders-from", `▸ ${String(order.officer_name || "").toUpperCase()}`);
    if (order.stage) from.appendChild(node("small", "", String(order.stage).toUpperCase()));
    const steps = node("div", "orders-steps");
    steps.append(...(order.steps || []).map((step) => {
      const row = node("div", `step${step.done ? " done" : ""}`);
      row.append(node("i", "", step.done ? "✓" : "○"), node("span", "", String(step.text || "")));
      if (!step.done) {
        const bar = node("em");
        bar.style.setProperty("--w", `${Math.round(Math.max(0, Math.min(1, number(step.fraction))) * 100)}%`);
        row.appendChild(bar);
      }
      return row;
    }));
    card.append(head, from, steps);
    if (order.line) card.appendChild(node("div", "orders-line", `“${order.line}”`));
    const figures = [];
    if (order.distance) figures.push(figure("TARGET", order.distance));
    if (order.state === "offer") {
      // The hotkeys answer the newest offer; the others are answered on the deck.
      if (order.keys && keys.accept) figures.push(figure("ACCEPT", keys.accept));
      if (order.keys && keys.decline) figures.push(figure("DECLINE", keys.decline));
      if (!order.keys || !keys.accept) figures.push(figure("ANSWER", "ON THE DECK"));
    } else if (order.progress != null) {
      figures.push(figure("PROGRESS", `${Math.round(number(order.progress) * 100)}%`));
    }
    if (figures.length) {
      const foot = node("footer", "orders-figures");
      foot.append(...figures);
      card.appendChild(foot);
    }
    return card;
  }

  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(dom.orders, snapshot.theme || {}, snapshot.effects || {});
    VoidCompassOverlay.fitToWindow(dom.orders, DESIGN_WIDTH, snapshot.effects || {});
    const model = snapshot.orders || null;
    const items = (model && model.items) || [];
    dom.orders.classList.toggle("empty", !items.length);
    const keys = {accept: (model && model.accept_key) || "", decline: (model && model.decline_key) || ""};
    dom["orders-list"].replaceChildren(...items.map((order) => block(order, keys)));
  }

  function contentHeight() {
    return VoidCompassOverlay.designHeight(dom.orders, MIN_HEIGHT);
  }

  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 250});
})();
