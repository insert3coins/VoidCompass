(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "toast";
  const root = document.getElementById("notifications");

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

  function severityIcon(severity) {
    return ({info: "◇", warn: "!", fail: "×", success: "✓"})[severity] || "◇";
  }

  function lifetime(item) {
    const remaining = Math.max(.2, number(item.expire_at) - (Date.now() / 1000));
    return `${remaining.toFixed(2)}s`;
  }

  function noticeCard(item) {
    const severity = ["info", "warn", "fail", "success"].includes(item.severity)
      ? item.severity : "info";
    const card = node("article", `notification notice ${severity}`);
    card.style.setProperty("--life", lifetime(item));
    const rail = node("div", "signal-rail");
    rail.appendChild(node("i"));
    card.appendChild(rail);
    const icon = node("div", "notice-icon");
    icon.appendChild(node("span", "", item.icon || severityIcon(severity)));
    card.appendChild(icon);
    const copy = node("div", "notice-copy");
    copy.appendChild(node("small", "notice-channel", severity === "fail" ? "COCKPIT ALERT" : "VOID COMPASS SIGNAL"));
    copy.appendChild(node("strong", "notice-title", item.title || "Notification"));
    if (item.message) copy.appendChild(node("span", "notice-message", item.message));
    card.appendChild(copy);
    card.appendChild(node("b", "notice-code", severity.toUpperCase()));
    card.appendChild(node("div", "life-rail"));
    card.appendChild(node("div", "scanlines"));
    return card;
  }

  function achievementCard(item) {
    const meta = item.meta || {};
    const card = node("article", "notification achievement");
    card.style.setProperty("--life", lifetime(item));
    card.appendChild(node("div", "achievement-sweep"));
    const sigil = node("div", "achievement-sigil", item.icon || "★");
    sigil.appendChild(node("i"));
    card.appendChild(sigil);
    const copy = node("div", "achievement-copy");
    copy.appendChild(node("small", "achievement-kicker", "COMMANDER MILESTONE UNLOCKED"));
    copy.appendChild(node("strong", "achievement-title", item.title || "Achievement"));
    const supporting = item.message || meta.description || "Journal milestone verified";
    copy.appendChild(node("span", "achievement-message", supporting));
    card.appendChild(copy);
    const score = node("div", "achievement-score");
    score.appendChild(node("b", "", `+${Math.max(0, Math.round(number(meta.points))).toLocaleString()}`));
    score.appendChild(node("small", "", "PTS"));
    card.appendChild(score);
    card.appendChild(node("div", "achievement-category", String(meta.category || "EXPLORATION").toUpperCase()));
    card.appendChild(node("div", "life-rail"));
    card.appendChild(node("div", "scanlines"));
    return card;
  }

  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
    const fragment = document.createDocumentFragment();
    for (const item of snapshot.notifications || []) {
      fragment.appendChild(item.kind === "achievement" ? achievementCard(item) : noticeCard(item));
    }
    root.replaceChildren(fragment);
  }

  VoidCompassOverlay.startPolling({token, overlay, render, interval: 220});
})();
