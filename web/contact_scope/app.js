(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "contact-scope";
  const suffix = `token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
  const dom = Object.fromEntries([
    "scope", "counter", "system-name", "scope-state", "progress-fill",
    "progress-pulse", "contacts", "footer-state",
  ].map((id) => [id, document.getElementById(id)]));
  let lastRevision = -1;
  let readySent = false;
  let pollActive = false;
  let currentModel = {};

  const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }
  function applyTheme(theme = {}, effects = {}) {
    const mapping = {bg:"bg", panel:"panel", panel_raised:"raised", border:"border", border_soft:"soft", accent:"accent", orange:"orange", text:"text", muted:"muted", dim:"dim", green:"green", yellow:"yellow", red:"red"};
    for (const [key, css] of Object.entries(mapping)) {
      if (/^#[0-9a-f]{6}$/i.test(String(theme[key] || ""))) document.documentElement.style.setProperty(`--${css}`, theme[key]);
    }
    document.documentElement.style.setProperty("--scale", String(number(effects.text_scale, 1)));
    const opacity = Number(effects.opacity);
    document.body.style.opacity = String(Number.isFinite(opacity) ? Math.max(.4, Math.min(1, opacity)) : 1);
    dom.scope.classList.toggle("no-crt", !effects.crt);
    dom.scope.classList.toggle("reduced-motion", Boolean(effects.reduced_motion));
  }
  function remaining(expiresAt) {
    const seconds = Math.ceil(number(expiresAt) - Date.now() / 1000);
    if (!number(expiresAt)) return "";
    if (seconds <= 0) return "EXPIRED";
    const minutes = Math.floor(seconds / 60);
    const rest = seconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
  }
  function renderRows() {
    dom.contacts.replaceChildren();
    for (const row of (currentModel.contacts || [])) {
      const item = node("article", `contact ${row.tone || "muted"}`);
      const mark = node("i", "contact-mark");
      mark.appendChild(node("b")); item.appendChild(mark);
      const copy = node("div", "contact-copy");
      copy.appendChild(node("strong", "contact-name", row.name || "Unidentified signal"));
      const detail = node("span", "contact-detail");
      detail.appendChild(node("b", "contact-kind", row.kind || "SIGNAL"));
      if (row.faction) detail.appendChild(node("span", "contact-faction", row.faction));
      copy.appendChild(detail); item.appendChild(copy);
      const facts = node("div", "contact-facts");
      if (number(row.threat) > 0) facts.appendChild(node("b", "threat", `THREAT ${Math.round(number(row.threat))}`));
      const timer = remaining(row.expires_at);
      if (timer) facts.appendChild(node("span", timer === "EXPIRED" ? "expired" : "timer", timer));
      item.appendChild(facts); dom.contacts.appendChild(item);
    }
  }
  function render(snapshot = {}) {
    applyTheme(snapshot.theme || {}, snapshot.effects || {});
    currentModel = snapshot.contacts || {};
    const total = Math.max(number(currentModel.total), number(currentModel.resolved));
    const resolved = Math.min(total, number(currentModel.resolved));
    dom.scope.classList.toggle("empty", !total);
    dom.scope.classList.toggle("complete", Boolean(currentModel.complete));
    dom.counter.textContent = `${resolved} / ${total}`;
    dom["system-name"].textContent = String(currentModel.system || "SYSTEM").toUpperCase();
    dom["scope-state"].textContent = currentModel.complete ? "CONTACT SET RESOLVED" : "FSS CONTACT SCOPE";
    dom["progress-fill"].style.width = `${total ? Math.min(100, resolved / total * 100) : 0}%`;
    dom["footer-state"].textContent = currentModel.complete ? "RESOLUTION COMPLETE" : `${Math.max(0, total - resolved)} UNRESOLVED`;
    renderRows();
  }
  function contentHeight() {
    const rows = [...dom.contacts.children];
    const gap = Number.parseFloat(getComputedStyle(dom.contacts).rowGap) || 0;
    return Math.max(112, Math.ceil(86 + rows.reduce((sum, row) => sum + row.getBoundingClientRect().height, 0) + Math.max(0, rows.length - 1) * gap + 28));
  }
  async function refresh(revision) {
    const response = await fetch(`/api/snapshot?${suffix}`, {cache:"no-store"});
    if (!response.ok) return;
    render(await response.json());
    await new Promise((resolve) => requestAnimationFrame(resolve));
    lastRevision = revision;
    try {
      await fetch(`/api/rendered?${suffix}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({revision, content_height:contentHeight()})});
      if (!readySent) { readySent = true; await fetch(`/api/ready?${suffix}`, {method:"POST", body:"{}"}); }
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
    } catch (_) {} finally { pollActive = false; }
  }
  setInterval(() => { if ((currentModel.contacts || []).some((row) => number(row.expires_at))) renderRows(); }, 1000);
  poll(); setInterval(poll, 300);
})();
