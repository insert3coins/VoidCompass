// Cockpit notifications and achievements (rewritten for 5.5.4). One page,
// two overlays: the notifications window shows notices, the achievements
// window (its own switch and place on screen) shows unlocks. Every size grows
// with the overlay text size and every line wraps, so nothing is cut off;
// the page fits itself to the window it really gets (overlayfix.md).
(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "toast";
  const root = document.getElementById("notifications");
  const SEVERITIES = {
    info: {label: "INFORMATION", symbol: "◇"},
    warn: {label: "CAUTION", symbol: "!"},
    fail: {label: "CRITICAL", symbol: "×"},
    success: {label: "CONFIRMED", symbol: "✓"},
  };

  const number = (value, fallback = 0) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  const decorative = (element) => {
    element.setAttribute("aria-hidden", "true");
    return element;
  };

  function finish(card, item) {
    card.dataset.notificationId = String(item.id);
    // Each card is its own shape for the Dark box fix (5.5.3.3.1).
    card.dataset.windowShape = "box";
    const left = Math.max(.2, number(item.expire_at) - Date.now() / 1000);
    card.style.setProperty("--life", `${left.toFixed(2)}s`);
    card.appendChild(decorative(node("i", "card-scan")));
    card.appendChild(decorative(node("i", "card-life")));
    return card;
  }

  function noticeCard(item) {
    const severity = SEVERITIES[item.severity] ? item.severity : "info";
    const card = node("article", `card notice ${severity}`);
    const mark = decorative(node("div", "notice-mark"));
    mark.appendChild(node("span", "", item.icon || SEVERITIES[severity].symbol));
    card.appendChild(mark);
    const copy = node("div", "card-copy");
    const head = node("div", "card-head");
    head.appendChild(node("b", "", SEVERITIES[severity].label));
    head.appendChild(decorative(node("i", "card-rule")));
    head.appendChild(node("small", "", "VOID COMPASS"));
    copy.appendChild(head);
    copy.appendChild(node("strong", "card-title", item.title || "Notification"));
    if (item.message) copy.appendChild(node("p", "card-message", item.message));
    card.appendChild(copy);
    return finish(card, item);
  }

  function achievementCard(item) {
    const meta = item.meta || {};
    const card = node("article", "card achievement");
    const head = node("div", "card-head achievement-head");
    head.appendChild(node("b", "", "ACHIEVEMENT UNLOCKED"));
    head.appendChild(decorative(node("i", "card-rule")));
    const tier = meta.tier == null ? "" : String(meta.tier).trim();
    const tierLabel = tier ? ` · ${/^\d+$/.test(tier) ? `TIER ${tier}` : tier.toUpperCase()}` : "";
    head.appendChild(node("small", "", `${String(meta.category || "Exploration").toUpperCase()}${tierLabel}`));
    card.appendChild(head);
    const badge = decorative(node("div", "achievement-badge"));
    badge.appendChild(node("span", "", item.icon || "★"));
    card.appendChild(badge);
    const copy = node("div", "card-copy");
    copy.appendChild(node("strong", "card-title", item.title || "Achievement"));
    copy.appendChild(node("p", "card-message", item.message || meta.description || "Journal milestone verified"));
    const points = Math.max(0, Math.round(number(meta.points)));
    if (points) copy.appendChild(node("span", "achievement-points", `+${points.toLocaleString()} POINTS`));
    card.appendChild(copy);
    return finish(card, item);
  }

  const signature = (item) => JSON.stringify([item.kind, item.title, item.message, item.icon, item.severity,
    item.created_at, item.expire_at, item.meta]);

  function render(snapshot = {}) {
    const effects = snapshot.effects || {};
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, effects);
    VoidCompassOverlay.fitToWindow(root, number(snapshot.design_width, overlay === "achievements" ? 420 : 400), effects);
    root.classList.toggle("reduced-motion", Boolean(effects.reduced_motion)
      || window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    const existing = new Map([...root.children].map((card) => [card.dataset.notificationId, card]));
    const kept = new Set();
    for (const [index, item] of (snapshot.notifications || []).entries()) {
      const next = signature(item);
      let card = existing.get(String(item.id));
      if (!card || card.dataset.signature !== next) {
        card = item.kind === "achievement" ? achievementCard(item) : noticeCard(item);
        card.dataset.signature = next;
      }
      if (root.children[index] !== card) root.insertBefore(card, root.children[index] || null);
      kept.add(card);
    }
    for (const card of [...root.children]) {
      if (!kept.has(card)) card.remove();
    }
  }

  // Every card's real height, in the app's units, so the window shows them all.
  const contentHeight = () => (root.children.length ? VoidCompassOverlay.designHeight(root, 0) : 0);

  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 220});
})();
