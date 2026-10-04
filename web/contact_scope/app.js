(() => {
  "use strict";
  // Deep Space Contacts (5.5.2.3): draws the model the journal-driven
  // ContactLedger builds (src/voidcompass/exploration/contact_scope.py).
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "contact-scope";
  const dom = Object.fromEntries([
    "scope", "content", "scope-tag", "system-name", "scope-count", "resolution", "resolution-text",
    "resolution-aside", "resolution-fill", "groups", "rows", "more", "carriers", "carriers-count", "carriers-names",
  ].map((id) => [id, document.getElementById(id)]));
  let previousSystem = "";
  let previousKeys = new Set();

  const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  function remaining(expiresAt) {
    const expiry = number(expiresAt);
    if (!expiry) return null;
    const seconds = Math.ceil(expiry - Date.now() / 1000);
    if (seconds <= 0) return {text: "", seconds: 0};
    return {text: `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`, seconds};
  }

  function tickTimers() {
    for (const timer of dom.rows.querySelectorAll("[data-expires]")) {
      const left = remaining(timer.dataset.expires);
      const row = timer.closest(".row");
      if (!left || left.seconds <= 0) {
        // Gone from the game: gone from here, before the next snapshot.
        if (row) row.hidden = true;
        continue;
      }
      timer.textContent = left.text;
      timer.classList.toggle("urgent", left.seconds <= 120);
    }
  }

  function contactRow(row, fresh) {
    const item = node("div", `row kind-${row.kind}${fresh ? " fresh" : ""}`);
    item.appendChild(node("i", "mark"));
    const name = node("span", "name", row.name || row.label);
    if (number(row.count) > 1) name.appendChild(node("small", "count", `×${number(row.count)}`));
    if (row.faction) name.appendChild(node("small", "", row.faction));
    item.appendChild(name);
    const side = node("span", "side");
    if (number(row.threat) > 0) side.appendChild(node("b", "threat", `THREAT ${number(row.threat)}`));
    const left = remaining(row.expires_at);
    if (left) {
      const timer = node("span", "timer", left.text);
      timer.dataset.expires = String(number(row.expires_at));
      side.appendChild(timer);
    }
    side.appendChild(node("span", "", String(row.kind === "uss" ? "USS" : row.label || "").toUpperCase()));
    item.appendChild(side);
    return item;
  }

  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(dom.scope, snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.contacts || null;
    dom.scope.classList.toggle("empty", !model);
    dom.scope.classList.toggle("reduced-motion", Boolean((snapshot.effects || {}).reduced_motion));
    if (!model) return;
    const system = String(model.system || "").toUpperCase();
    const rows = Array.isArray(model.rows) ? model.rows : [];
    const threat = number(model.threat);
    const honked = Boolean(model.honked);
    const expected = number(model.expected);
    const named = number(model.named);
    const unresolved = number(model.unresolved);

    dom.scope.classList.toggle("threat", threat > 0);
    dom.scope.classList.toggle("resolved", honked && expected > 0 && unresolved === 0 && threat === 0);
    dom["scope-tag"].textContent = threat > 0 ? `THREAT ${threat}` : "FSS";
    dom["system-name"].textContent = system || "UNKNOWN SYSTEM";
    dom["scope-count"].textContent = `${honked ? expected : named} SIGNAL${(honked ? expected : named) === 1 ? "" : "S"}`;

    dom.resolution.classList.toggle("unhonked", !honked);
    if (!honked) {
      dom["resolution-text"].textContent = `${named} HEARD · HONK FOR THE FULL COUNT`;
      dom["resolution-aside"].textContent = "";
    } else if (!expected) {
      dom["resolution-text"].textContent = "NO SIGNALS IN THIS SYSTEM";
      dom["resolution-aside"].textContent = "";
    } else {
      dom["resolution-text"].textContent = !unresolved
        ? "EVERY SIGNAL NAMED"
        : model.bodies_done
          ? `BODIES DONE · ${unresolved} SIGNAL${unresolved === 1 ? "" : "S"}: TUNE TO THEM IN THE FSS`
          : `${named} NAMED · ${unresolved} TO RESOLVE IN THE FSS`;
      dom["resolution-aside"].textContent = `${Math.min(named, expected)} / ${expected}`;
    }
    dom["resolution-fill"].style.width = `${expected ? Math.min(100, named / expected * 100) : 0}%`;

    dom.groups.replaceChildren(...(model.groups || []).map((group) => {
      const chip = node("span", `group kind-${group.kind}`);
      chip.appendChild(node("b", "", group.count));
      chip.append(String(group.name || ""));
      return chip;
    }));

    const sameSystem = system === previousSystem;
    const keys = new Set(rows.map((row) => row.key));
    dom.rows.replaceChildren(...rows.map((row) => contactRow(row, sameSystem && !previousKeys.has(row.key))));
    dom.more.hidden = !number(model.more);
    dom.more.textContent = number(model.more) ? `+ ${number(model.more)} MORE` : "";

    const carriers = model.carriers;
    dom.carriers.hidden = !carriers;
    if (carriers) {
      dom["carriers-count"].textContent = `${carriers.count} CARRIER${carriers.count === 1 ? "" : "S"}`;
      dom["carriers-names"].textContent = (carriers.names || []).join(" · ") + (number(carriers.more) ? ` · +${number(carriers.more)}` : "");
    }
    tickTimers();
    previousSystem = system;
    previousKeys = keys;
  }

  function contentHeight() {
    return Math.ceil(dom.content.getBoundingClientRect().height + 2);
  }

  window.setInterval(tickTimers, 1000);
  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 300});
})();
