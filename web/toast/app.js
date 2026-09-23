(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "toast";
  const root = document.getElementById("notifications");
  const severities = {
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

  function decorative(element) {
    element.setAttribute("aria-hidden", "true");
    return element;
  }

  function lifetime(item) {
    return `${Math.max(.2, number(item.expire_at) - Date.now() / 1000).toFixed(2)}s`;
  }

  function frame(card, item) {
    card.dataset.notificationId = String(item.id);
    card.style.setProperty("--life", lifetime(item));
    card.appendChild(decorative(node("div", "notification-edge")));
    card.appendChild(decorative(node("div", "notification-texture")));
    card.appendChild(decorative(node("div", "life-track")));
    return card;
  }

  function noticeCard(item) {
    const severity = severities[item.severity] ? item.severity : "info";
    const card = node("article", `notification notice ${severity}`);
    const mark = decorative(node("div", "notice-mark"));
    mark.appendChild(node("span", "", item.icon || severities[severity].symbol));
    card.appendChild(mark);

    const copy = node("div", "notice-copy");
    const header = node("div", "notice-header");
    header.appendChild(node("span", "notice-severity", severities[severity].label));
    header.appendChild(decorative(node("i", "notice-rule")));
    header.appendChild(node("span", "notice-source", "VOID COMPASS"));
    copy.appendChild(header);
    copy.appendChild(node("strong", "notice-title", item.title || "Notification"));
    if (item.message) copy.appendChild(node("span", "notice-message", item.message));
    card.appendChild(copy);
    card.appendChild(decorative(node("div", "notice-signal")));
    return frame(card, item);
  }

  function achievementCard(item) {
    const meta = item.meta || {};
    const card = node("article", "notification achievement");
    const mark = decorative(node("div", "achievement-mark"));
    mark.appendChild(node("span", "", item.icon || "★"));
    card.appendChild(mark);

    const copy = node("div", "achievement-copy");
    copy.appendChild(node("small", "achievement-kicker", "MILESTONE UNLOCKED"));
    copy.appendChild(node("strong", "achievement-title", item.title || "Achievement"));
    const supporting = item.message || meta.description || "Journal milestone verified";
    copy.appendChild(node("span", "achievement-message", supporting));
    const tier = meta.tier == null ? "" : String(meta.tier).trim();
    const tierLabel = tier ? ` · ${/^\d+$/.test(tier) ? `TIER ${tier}` : tier.toUpperCase()}` : "";
    copy.appendChild(node("span", "achievement-category",
      `${String(meta.category || "Exploration").toUpperCase()}${tierLabel}`));
    card.appendChild(copy);

    const score = node("div", "achievement-score");
    const points = Math.max(0, Math.round(number(meta.points)));
    score.appendChild(node("b", "", `+${points.toLocaleString()}`));
    score.appendChild(node("small", "", "POINTS"));
    card.appendChild(score);
    return frame(card, item);
  }

  function signature(item) {
    return JSON.stringify([
      item.kind, item.title, item.message, item.icon, item.severity,
      item.created_at, item.expire_at, item.meta,
    ]);
  }

  function render(snapshot = {}) {
    const effects = snapshot.effects || {};
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, effects);
    root.classList.toggle("reduced-motion", Boolean(effects.reduced_motion)
      || window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    root.classList.toggle("large-type", number(effects.text_scale, 1) >= 1.5);

    const existing = new Map([...root.children].map((card) => [card.dataset.notificationId, card]));
    const retained = new Set();
    for (const [index, item] of (snapshot.notifications || []).entries()) {
      const id = String(item.id);
      const nextSignature = signature(item);
      let card = existing.get(id);
      if (!card || card.dataset.signature !== nextSignature) {
        card = item.kind === "achievement" ? achievementCard(item) : noticeCard(item);
        card.dataset.signature = nextSignature;
      }
      if (root.children[index] !== card) root.insertBefore(card, root.children[index] || null);
      retained.add(card);
    }
    for (const card of [...root.children]) {
      if (!retained.has(card)) card.remove();
    }
  }

  VoidCompassOverlay.startPolling({token, overlay, render, interval: 220});
})();
