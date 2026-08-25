(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "cargo";
  const suffix = `token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
  const root = document.getElementById("cargo");
  const byId = (id) => document.getElementById(id);
  const MAX_ROWS = 14;
  let revision = -1;
  let polling = false;
  let ready = false;

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  function set(id, value, fallback = "—") {
    const element = byId(id);
    if (element) element.textContent = value === null || value === undefined || value === "" ? fallback : String(value);
  }

  function number(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function tonnes(value) {
    return `${Math.max(0, Math.round(number(value))).toLocaleString()} T`;
  }

  function applyTheme(theme = {}, effects = {}) {
    const mapping = {
      bg:"bg", panel:"panel", panel_alt:"alt", panel_raised:"raised",
      border:"border", border_soft:"soft", accent:"accent", orange:"orange",
      text:"text", muted:"muted", dim:"dim", green:"green",
      yellow:"yellow", red:"red",
    };
    for (const [key, css] of Object.entries(mapping)) {
      const value = String(theme[key] || "");
      if (/^#[0-9a-f]{6}$/i.test(value)) document.documentElement.style.setProperty(`--${css}`, value);
    }
    const scale = Number(effects.text_scale);
    document.documentElement.style.setProperty("--scale", String(Number.isFinite(scale) ? Math.max(.75, Math.min(2, scale)) : 1));
    const opacity = Number(effects.opacity);
    document.body.style.opacity = String(Number.isFinite(opacity) ? Math.max(.4, Math.min(1, opacity)) : 1);
    root.classList.toggle("no-crt", !effects.crt);
    root.classList.toggle("reduced-motion", Boolean(effects.reduced_motion));
  }

  function renderCapacity(model) {
    const utilisation = model.utilisation === null || model.utilisation === undefined
      ? null : Math.max(0, Math.min(1, number(model.utilisation)));
    const count = 12;
    const active = utilisation === null ? 0 : Math.min(count, Math.ceil(utilisation * count));
    const tone = utilisation !== null && utilisation >= .95 ? "critical" : utilisation !== null && utilisation >= .8 ? "warning" : "nominal";
    root.dataset.load = tone;
    byId("capacity-segments").replaceChildren(...Array.from({length: count}, (_, index) => node("i", index < active ? `active ${tone}` : "")));
    set("capacity-percent", utilisation === null ? "CAPACITY UNKNOWN" : `${Math.round(utilisation * 100)}% USED`);
  }

  function renderFlags(model) {
    const flags = [];
    if (number(model.mission)) flags.push(["mission", `MISSION ${tonnes(model.mission)}`]);
    if (number(model.stolen)) flags.push(["stolen", `STOLEN ${tonnes(model.stolen)}`]);
    if (!flags.length) flags.push(["clear", "STANDARD CARGO"]);
    byId("cargo-flags").replaceChildren(...flags.map(([kind, label]) => node("span", kind, label)));
  }

  function manifestRow(row) {
    const stolen = number(row.stolen) > 0;
    const mission = number(row.mission) > 0;
    const item = node("article", stolen ? "stolen" : mission ? "mission" : "standard");
    const copy = node("div", "commodity-copy");
    copy.appendChild(node("strong", "", row.name || "Unknown commodity"));
    const tags = node("span", "commodity-tags");
    if (mission) tags.appendChild(node("i", "mission", `MISSION ${tonnes(row.mission)}`));
    if (stolen) tags.appendChild(node("i", "stolen", `STOLEN ${tonnes(row.stolen)}`));
    if (tags.childNodes.length) copy.appendChild(tags);
    item.appendChild(copy);
    const amount = node("div", "commodity-count");
    amount.appendChild(node("strong", "", number(row.count).toLocaleString()));
    amount.appendChild(node("small", "", "TONNES"));
    item.appendChild(amount);
    return item;
  }

  function renderManifest(model) {
    const rows = Array.isArray(model.rows) ? model.rows : [];
    const shown = rows.slice(0, MAX_ROWS);
    const overflow = rows.slice(MAX_ROWS);
    const host = byId("manifest");
    host.replaceChildren();
    if (!shown.length) {
      const empty = node("div", "empty-hold");
      empty.appendChild(node("i", "", "◇"));
      empty.appendChild(node("strong", "", "HOLD EMPTY"));
      empty.appendChild(node("span", "", "NO COMMODITY STACKS REPORTED"));
      host.appendChild(empty);
    } else {
      shown.forEach((row) => host.appendChild(manifestRow(row)));
    }
    if (overflow.length) {
      const hidden = overflow.reduce((sum, row) => sum + number(row.count), 0);
      host.appendChild(node("div", "overflow", `+ ${overflow.length} MORE STACKS · ${tonnes(hidden)}`));
    }
  }

  function render(snapshot = {}) {
    applyTheme(snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.cargo || {};
    const total = number(model.total);
    const capacity = number(model.capacity);
    const rows = Array.isArray(model.rows) ? model.rows : [];
    root.classList.toggle("empty", !rows.length);
    root.classList.toggle("has-stolen", number(model.stolen) > 0);
    root.classList.toggle("has-mission", number(model.mission) > 0);
    set("hold-state", rows.length ? "MANIFEST LIVE" : "HOLD EMPTY");
    set("hold-total", capacity ? `${total.toLocaleString()} / ${capacity.toLocaleString()} T` : tonnes(total));
    set("hold-detail", capacity ? `${Math.round((total / Math.max(1, capacity)) * 100)}% OF SHIP CAPACITY` : "CAPACITY UNKNOWN");
    set("hold-free", model.free === null || model.free === undefined ? "—" : number(model.free).toLocaleString());
    set("stack-count", `${rows.length} STACK${rows.length === 1 ? "" : "S"}`);
    set("manifest-summary", number(model.stolen) ? `STOLEN ${tonnes(model.stolen)}` : number(model.mission) ? `MISSION ${tonnes(model.mission)}` : `${rows.length} COMMODITY STACK${rows.length === 1 ? "" : "S"}`);
    renderCapacity(model);
    renderFlags(model);
    renderManifest(model);
  }

  function contentHeight() {
    return Math.max(170, Math.ceil(root.getBoundingClientRect().height + 2));
  }

  async function refresh(nextRevision) {
    const response = await fetch(`/api/snapshot?${suffix}`, {cache:"no-store"});
    if (!response.ok) return;
    render(await response.json());
    await new Promise((resolve) => requestAnimationFrame(resolve));
    revision = nextRevision;
    try {
      await fetch(`/api/rendered?${suffix}`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({revision:nextRevision, content_height:contentHeight()}),
      });
      if (!ready) {
        ready = true;
        await fetch(`/api/ready?${suffix}`, {method:"POST", body:"{}"});
      }
    } catch (_) {}
  }

  async function poll() {
    if (polling) return;
    polling = true;
    try {
      const response = await fetch(`/api/health?${suffix}`, {cache:"no-store"});
      if (response.ok) {
        const next = Number((await response.json()).revision);
        if (Number.isFinite(next) && next !== revision) await refresh(next);
      }
    } catch (_) {
    } finally {
      polling = false;
    }
  }

  poll();
  window.setInterval(poll, 260);
})();
