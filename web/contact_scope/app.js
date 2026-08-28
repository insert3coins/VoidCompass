(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "contact-scope";
  const suffix = `token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
  const dom = Object.fromEntries([
    "scope", "counter", "system-name", "scope-state", "resolution-label",
    "threat-summary", "progress-fill", "progress-pulse", "radar-blips",
    "contact-summary", "contacts", "footer-state",
  ].map((id) => [id, document.getElementById(id)]));
  let lastRevision = -1;
  let readySent = false;
  let pollActive = false;
  let previousSystem = "";
  let previousResolved = -1;
  let previousComplete = false;
  let previousRows = new Map();
  let activityTimer = 0;

  const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  function keyOf(row = {}) {
    return String(row.key || row.name || "unidentified").trim().toLowerCase();
  }

  function kindClass(value) {
    const key = String(value || "signal").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
    return key || "signal";
  }

  function hash(value) {
    let result = 2166136261;
    for (const char of String(value || "")) {
      result ^= char.charCodeAt(0);
      result = Math.imul(result, 16777619);
    }
    return result >>> 0;
  }

  function applyTheme(theme = {}, effects = {}) {
    const mapping = {
      bg:"bg", panel:"panel", panel_raised:"raised", border:"border",
      border_soft:"soft", accent:"accent", orange:"orange", text:"text",
      muted:"muted", dim:"dim", green:"green", yellow:"yellow", red:"red",
    };
    for (const [key, css] of Object.entries(mapping)) {
      if (/^#[0-9a-f]{6}$/i.test(String(theme[key] || ""))) {
        document.documentElement.style.setProperty(`--${css}`, theme[key]);
      }
    }
    document.documentElement.style.setProperty("--scale", String(number(effects.text_scale, 1)));
    const opacity = Number(effects.opacity);
    document.body.style.opacity = String(Number.isFinite(opacity) ? Math.max(.4, Math.min(1, opacity)) : 1);
    dom.scope.classList.toggle("no-crt", !effects.crt);
    dom.scope.classList.toggle("reduced-motion", Boolean(effects.reduced_motion));
  }

  function remaining(expiresAt) {
    const expiry = number(expiresAt);
    if (!expiry) return {text:"", seconds:null, state:"stable"};
    const seconds = Math.ceil(expiry - Date.now() / 1000);
    if (seconds <= 0) return {text:"EXPIRED", seconds:0, state:"expired"};
    const minutes = Math.floor(seconds / 60);
    const rest = seconds % 60;
    return {
      text:`${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`,
      seconds,
      state:seconds <= 300 ? "urgent" : seconds <= 900 ? "aging" : "stable",
    };
  }

  function updateTimers() {
    for (const timer of dom.contacts.querySelectorAll("[data-expires]")) {
      const state = remaining(timer.dataset.expires);
      timer.textContent = state.text;
      timer.className = `timer ${state.state}`;
      const contact = timer.closest(".contact");
      if (contact) {
        contact.classList.toggle("expired", state.state === "expired");
        contact.classList.toggle("expiring", state.state === "urgent");
      }
    }
  }

  function blip(row, index, isNew) {
    const key = keyOf(row);
    const seed = hash(key);
    const angle = ((seed % 360) / 180) * Math.PI;
    const radius = 17 + ((seed >>> 9) % 20);
    const x = 50 + Math.cos(angle) * radius;
    const y = 50 + Math.sin(angle) * radius * .72;
    const tone = String(row.tone || "muted");
    const threat = Math.max(0, Math.round(number(row.threat)));
    const item = node("i", `radar-blip ${tone}${threat ? " hostile" : ""}${isNew ? " acquired" : ""}`);
    item.style.setProperty("--x", `${x.toFixed(2)}%`);
    item.style.setProperty("--y", `${y.toFixed(2)}%`);
    item.style.setProperty("--delay", `${-((seed % 2200) / 1000).toFixed(2)}s`);
    item.style.setProperty("--size", `${threat ? 5.5 : 4 + (index % 2)}px`);
    item.appendChild(node("b"));
    return item;
  }

  function contactRow(row, event = {}) {
    const tone = String(row.tone || "muted");
    const threat = Math.max(0, Math.round(number(row.threat)));
    const expiry = remaining(row.expires_at);
    const classes = [
      "contact", tone, `kind-${kindClass(row.kind)}`,
      threat ? "has-threat" : "",
      event.fresh ? "acquired" : "",
      event.threat ? "threat-changed" : "",
      expiry.state === "expired" ? "expired" : "",
      expiry.state === "urgent" ? "expiring" : "",
    ].filter(Boolean).join(" ");
    const item = node("article", classes);
    item.dataset.key = keyOf(row);

    const mark = node("i", "contact-mark");
    mark.appendChild(node("i", "mark-ring"));
    mark.appendChild(node("b", "mark-core"));
    mark.appendChild(node("em", "mark-vector"));
    item.appendChild(mark);

    const copy = node("div", "contact-copy");
    copy.appendChild(node("strong", "contact-name", row.name || "Unidentified signal"));
    const detail = node("span", "contact-detail");
    detail.appendChild(node("b", "contact-kind", row.kind || "SIGNAL"));
    if (row.faction) detail.appendChild(node("span", "contact-faction", row.faction));
    copy.appendChild(detail);
    const trace = node("i", "signal-trace");
    trace.appendChild(node("b"));
    copy.appendChild(trace);
    item.appendChild(copy);

    const facts = node("div", "contact-facts");
    if (threat) facts.appendChild(node("b", "threat", `THREAT ${threat}`));
    else facts.appendChild(node("b", "classification", row.is_station ? "FIXED" : "CONTACT"));
    if (expiry.text) {
      const timer = node("span", `timer ${expiry.state}`, expiry.text);
      timer.dataset.expires = String(number(row.expires_at));
      facts.appendChild(timer);
    }
    item.appendChild(facts);
    return item;
  }

  function activityClass(name) {
    const names = ["event-resolution", "event-threat", "event-complete", "event-system"];
    dom.scope.classList.remove(...names);
    if (name) {
      void dom.scope.offsetWidth;
      dom.scope.classList.add(name);
    }
    window.clearTimeout(activityTimer);
    activityTimer = window.setTimeout(() => dom.scope.classList.remove(...names), 1150);
  }

  function render(snapshot = {}) {
    applyTheme(snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.contacts || {};
    const rows = Array.isArray(model.contacts) ? model.contacts : [];
    const total = Math.max(number(model.total), number(model.resolved));
    const resolved = Math.min(total, number(model.resolved));
    const system = String(model.system || "SYSTEM").toUpperCase();
    const complete = Boolean(model.complete);
    const firstRender = previousResolved < 0;
    const sameSystem = previousSystem === system;
    const currentRows = new Map(rows.map((row) => [keyOf(row), row]));
    const rowEvents = new Map();
    let threatChanged = false;
    if (!firstRender && sameSystem) {
      for (const [key, row] of currentRows.entries()) {
        const previous = previousRows.get(key);
        const event = {
          fresh: !previous,
          threat: Boolean(previous && number(row.threat) !== number(previous.threat)),
        };
        if (event.fresh || event.threat) rowEvents.set(key, event);
        threatChanged = threatChanged || event.threat
          || Boolean(event.fresh && number(row.threat));
      }
    }

    const maxThreat = rows.reduce((highest, row) => Math.max(highest, number(row.threat)), 0);
    const timed = rows.filter((row) => number(row.expires_at) > 0).length;
    const unresolved = Math.max(0, total - resolved);
    const percentage = total ? Math.min(100, resolved / total * 100) : 0;
    dom.scope.classList.toggle("empty", !total);
    dom.scope.classList.toggle("complete", complete);
    dom.scope.dataset.threat = maxThreat > 0 ? "hostile" : "clear";
    dom.counter.textContent = `${resolved} / ${total}`;
    dom["system-name"].textContent = system;
    dom["scope-state"].textContent = complete ? "CONTACT SET RESOLVED" : "PASSIVE FSS ACQUISITION";
    dom["resolution-label"].textContent = complete ? "SCOPE RESOLVED" : `${Math.round(percentage)}% RESOLVED`;
    dom["threat-summary"].textContent = maxThreat > 0 ? `MAX THREAT ${Math.round(maxThreat)}` : "FIELD CLEAR";
    dom["progress-fill"].style.width = `${percentage}%`;
    dom["progress-pulse"].style.left = `${Math.max(0, Math.min(100, percentage))}%`;
    dom["contact-summary"].textContent = `${rows.length} CONTACT${rows.length === 1 ? "" : "S"}`;
    dom["footer-state"].textContent = complete
      ? `RESOLUTION COMPLETE${timed ? ` · ${timed} TIMED` : ""}`
      : `${unresolved} UNRESOLVED${timed ? ` · ${timed} TIMED` : ""}`;

    dom.contacts.replaceChildren(...rows.map((row) => contactRow(row, rowEvents.get(keyOf(row)) || {})));
    dom["radar-blips"].replaceChildren(...rows.map((row, index) => (
      blip(row, index, Boolean(rowEvents.get(keyOf(row))?.fresh))
    )));
    updateTimers();

    if (!firstRender) {
      if (!sameSystem) activityClass("event-system");
      else if (complete && !previousComplete) activityClass("event-complete");
      else if (threatChanged) activityClass("event-threat");
      else if (resolved !== previousResolved) activityClass("event-resolution");
      else activityClass("");
    }
    previousSystem = system;
    previousResolved = resolved;
    previousComplete = complete;
    previousRows = currentRows;
  }

  function contentHeight() {
    const rows = [...dom.contacts.children];
    const gap = Number.parseFloat(getComputedStyle(dom.contacts).rowGap) || 0;
    const rowHeight = rows.reduce((sum, row) => sum + row.getBoundingClientRect().height, 0);
    return Math.max(212, Math.ceil(157 + rowHeight + Math.max(0, rows.length - 1) * gap + 29));
  }

  async function refresh(revision) {
    const response = await fetch(`/api/snapshot?${suffix}`, {cache:"no-store"});
    if (!response.ok) return;
    render(await response.json());
    await new Promise((resolve) => requestAnimationFrame(resolve));
    lastRevision = revision;
    try {
      await fetch(`/api/rendered?${suffix}`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({revision, content_height:contentHeight()}),
      });
      if (!readySent) {
        readySent = true;
        await fetch(`/api/ready?${suffix}`, {method:"POST", body:"{}"});
      }
    } catch (_) {}
  }

  async function poll() {
    if (pollActive) return;
    pollActive = true;
    try {
      const response = await fetch(`/api/health?${suffix}`, {cache:"no-store"});
      if (response.ok) {
        const revision = Number((await response.json()).revision);
        if (Number.isFinite(revision) && revision !== lastRevision) await refresh(revision);
      }
    } catch (_) {
    } finally {
      pollActive = false;
    }
  }

  window.setInterval(updateTimers, 1000);
  poll();
  window.setInterval(poll, 300);
})();
