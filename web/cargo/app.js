(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "cargo";
  const suffix = `token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
  const root = document.getElementById("cargo");
  const byId = (id) => document.getElementById(id);
  const MAX_ROWS = 14;
  const CAPACITY_CELLS = 16;
  let revision = -1;
  let polling = false;
  let ready = false;
  let previousModel = null;
  let eventSequence = 0;
  let settleTimer = null;

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  function set(id, value, fallback = "—") {
    const element = byId(id);
    if (element) {
      element.textContent = value === null || value === undefined || value === ""
        ? fallback : String(value);
    }
  }

  function number(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function tonnes(value, signed = false) {
    const amount = Math.round(number(value));
    const sign = signed && amount > 0 ? "+" : "";
    return `${sign}${amount.toLocaleString()} T`;
  }

  function cargoKey(row) {
    return String(row?.name || "unknown").trim().toLowerCase();
  }

  function applyTheme(theme = {}, effects = {}) {
    const mapping = {
      bg: "bg", panel: "panel", panel_alt: "alt", panel_raised: "raised",
      border: "border", border_soft: "soft", accent: "accent", orange: "orange",
      text: "text", muted: "muted", dim: "dim", green: "green",
      yellow: "yellow", red: "red",
    };
    for (const [key, css] of Object.entries(mapping)) {
      const value = String(theme[key] || "");
      if (/^#[0-9a-f]{6}$/i.test(value)) {
        document.documentElement.style.setProperty(`--${css}`, value);
      }
    }
    const scale = Number(effects.text_scale);
    document.documentElement.style.setProperty(
      "--scale", String(Number.isFinite(scale) ? Math.max(.75, Math.min(2, scale)) : 1),
    );
    const opacity = Number(effects.opacity);
    document.body.style.opacity = String(
      Number.isFinite(opacity) ? Math.max(.4, Math.min(1, opacity)) : 1,
    );
    root.classList.toggle("no-crt", !effects.crt);
    root.classList.toggle("reduced-motion", Boolean(effects.reduced_motion));
  }

  function loadTone(utilisation) {
    if (utilisation === null) return "unknown";
    if (utilisation >= .95) return "critical";
    if (utilisation >= .8) return "warning";
    return "nominal";
  }

  function renderCapacity(model) {
    const utilisation = model.utilisation === null || model.utilisation === undefined
      ? null : Math.max(0, Math.min(1, number(model.utilisation)));
    const active = utilisation === null
      ? 0 : Math.min(CAPACITY_CELLS, Math.ceil(utilisation * CAPACITY_CELLS));
    const tone = loadTone(utilisation);
    root.dataset.load = tone;
    root.style.setProperty("--utilisation", String(utilisation || 0));
    root.style.setProperty("--load-angle", `${Math.round((utilisation || 0) * 360)}deg`);
    const cells = Array.from({length: CAPACITY_CELLS}, (_, index) => {
      const cell = node("i", index < active ? `active ${tone}` : "");
      cell.style.setProperty("--cell", String(index));
      return cell;
    });
    byId("capacity-segments").replaceChildren(...cells);
    const percent = utilisation === null ? null : Math.round(utilisation * 100);
    set("capacity-percent", percent === null ? "CAPACITY UNKNOWN" : `${percent}% OCCUPIED`);
    set("hold-percent", percent === null ? "—" : `${percent}%`);
  }

  function renderFlags(model, delta) {
    const flags = [];
    if (delta > 0) flags.push(["intake", `INTAKE ${tonnes(delta, true)}`]);
    if (delta < 0) flags.push(["release", `RELEASE ${tonnes(Math.abs(delta))}`]);
    if (number(model.mission)) flags.push(["mission", `MISSION ${tonnes(model.mission)}`]);
    if (number(model.stolen)) flags.push(["stolen", `STOLEN ${tonnes(model.stolen)}`]);
    if (!flags.length) flags.push(["clear", model.total ? "HOLD STABLE" : "HOLD CLEAR"]);
    byId("cargo-flags").replaceChildren(
      ...flags.map(([kind, label]) => node("span", kind, label)),
    );
  }

  function orderedRows(rows) {
    return [...rows].sort((left, right) => {
      const leftRank = number(left.stolen) ? 0 : number(left.mission) ? 1 : 2;
      const rightRank = number(right.stolen) ? 0 : number(right.mission) ? 1 : 2;
      return leftRank - rightRank
        || number(right.count) - number(left.count)
        || String(left.name || "").localeCompare(String(right.name || ""));
    });
  }

  function manifestRow(row, previousCount, total) {
    const count = Math.max(0, number(row.count));
    const stolen = number(row.stolen) > 0;
    const mission = number(row.mission) > 0;
    const changed = previousCount !== null && count !== previousCount;
    const added = previousCount === null;
    const direction = changed ? (count > previousCount ? "increased" : "decreased") : "";
    const item = node("article", [
      stolen ? "stolen" : mission ? "mission" : "standard",
      added ? "acquired" : "", changed ? "adjusted" : "", direction,
    ].filter(Boolean).join(" "));
    item.dataset.key = cargoKey(row);

    const copy = node("div", "commodity-copy");
    copy.appendChild(node("strong", "", row.name || "Unknown commodity"));
    const tags = node("span", "commodity-tags");
    if (mission) tags.appendChild(node("i", "mission", `MISSION ${tonnes(row.mission)}`));
    if (stolen) tags.appendChild(node("i", "stolen", `STOLEN ${tonnes(row.stolen)}`));
    if (!tags.childNodes.length) tags.appendChild(node("i", "standard", "STANDARD HOLD"));
    copy.appendChild(tags);

    const allocation = node("span", "commodity-allocation");
    const fill = node("i");
    fill.style.setProperty("--share", `${total ? Math.max(2, count / total * 100) : 0}%`);
    allocation.appendChild(fill);
    copy.appendChild(allocation);
    item.appendChild(copy);

    const amount = node("div", "commodity-count");
    const countLine = node("span", "count-line");
    countLine.appendChild(node("strong", "", count.toLocaleString()));
    if (changed) {
      const delta = count - previousCount;
      countLine.appendChild(node("em", direction, `${delta > 0 ? "+" : ""}${delta}`));
    } else if (added && previousModel) {
      countLine.appendChild(node("em", "increased", `+${count}`));
    }
    amount.appendChild(countLine);
    amount.appendChild(node("small", "", "TONNES"));
    item.appendChild(amount);
    return item;
  }

  function renderManifest(model) {
    const rows = orderedRows(Array.isArray(model.rows) ? model.rows : []);
    const shown = rows.slice(0, MAX_ROWS);
    const overflow = rows.slice(MAX_ROWS);
    const previousCounts = new Map(
      (previousModel?.rows || []).map((row) => [cargoKey(row), number(row.count)]),
    );
    const host = byId("manifest");
    host.replaceChildren();
    if (!shown.length) {
      const empty = node("div", "empty-hold");
      empty.appendChild(node("i", "", "◇"));
      empty.appendChild(node("strong", "", "HOLD CLEAR"));
      empty.appendChild(node("span", "", "NO COMMODITY STACKS REPORTED"));
      host.appendChild(empty);
    } else {
      shown.forEach((row) => {
        const key = cargoKey(row);
        host.appendChild(manifestRow(
          row, previousCounts.has(key) ? previousCounts.get(key) : null,
          Math.max(1, number(model.total)),
        ));
      });
    }
    if (overflow.length) {
      const hidden = overflow.reduce((sum, row) => sum + number(row.count), 0);
      host.appendChild(node(
        "div", "overflow", `+ ${overflow.length} MORE STACKS · ${tonnes(hidden)}`,
      ));
    }
  }

  function acknowledgeCargoChange(delta, hasRows) {
    eventSequence += 1;
    const sequence = eventSequence;
    window.clearTimeout(settleTimer);
    root.classList.remove("cargo-event", "intake-event", "release-event");
    if (delta) {
      root.classList.add("cargo-event", delta > 0 ? "intake-event" : "release-event");
      set("hold-state", delta > 0
        ? `CARGO INTAKE ${tonnes(delta, true)}`
        : `CARGO RELEASE ${tonnes(Math.abs(delta))}`);
      settleTimer = window.setTimeout(() => {
        if (sequence !== eventSequence) return;
        root.classList.remove("cargo-event", "intake-event", "release-event");
        set("hold-state", hasRows ? "MANIFEST LIVE" : "HOLD CLEAR");
      }, 1650);
    } else {
      set("hold-state", hasRows ? "MANIFEST LIVE" : "HOLD CLEAR");
    }
  }

  function render(snapshot = {}) {
    applyTheme(snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.cargo || {};
    const total = Math.max(0, number(model.total));
    const capacity = Math.max(0, number(model.capacity));
    const rows = Array.isArray(model.rows) ? model.rows : [];
    const oldTotal = previousModel ? number(previousModel.total) : total;
    const delta = total - oldTotal;
    root.classList.toggle("empty", !rows.length);
    root.classList.toggle("has-cargo", rows.length > 0);
    root.classList.toggle("has-stolen", number(model.stolen) > 0);
    root.classList.toggle("has-mission", number(model.mission) > 0);
    acknowledgeCargoChange(delta, rows.length > 0);

    set("hold-total", capacity
      ? `${total.toLocaleString()} / ${capacity.toLocaleString()} T`
      : tonnes(total));
    set("hold-detail", capacity
      ? `${rows.length} STACK${rows.length === 1 ? "" : "S"} · ${Math.round(total / Math.max(1, capacity) * 100)}% LOAD`
      : `${rows.length} STACK${rows.length === 1 ? "" : "S"} · CAPACITY UNKNOWN`);
    set("hold-free", model.free === null || model.free === undefined
      ? "—" : number(model.free).toLocaleString());
    set("stack-count", `${rows.length} STACK${rows.length === 1 ? "" : "S"}`);
    const manifestSummary = number(model.stolen)
      ? `STOLEN ${tonnes(model.stolen)}`
      : number(model.mission)
        ? `MISSION ${tonnes(model.mission)}`
        : rows.length
          ? `${rows.length} COMMODITY STACK${rows.length === 1 ? "" : "S"}`
          : "HOLD CLEAR";
    set("manifest-summary", manifestSummary);
    renderCapacity(model);
    renderFlags(model, delta);
    renderManifest(model);
    previousModel = JSON.parse(JSON.stringify(model));
  }

  function contentHeight() {
    return Math.max(190, Math.ceil(root.scrollHeight + 2));
  }

  async function refresh(nextRevision) {
    const response = await fetch(`/api/snapshot?${suffix}`, {cache: "no-store"});
    if (!response.ok) return;
    render(await response.json());
    await new Promise((resolve) => requestAnimationFrame(resolve));
    revision = nextRevision;
    try {
      await fetch(`/api/rendered?${suffix}`, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({revision: nextRevision, content_height: contentHeight()}),
      });
      if (!ready) {
        ready = true;
        await fetch(`/api/ready?${suffix}`, {method: "POST", body: "{}"});
      }
    } catch (_) {}
  }

  async function poll() {
    if (polling) return;
    polling = true;
    try {
      const response = await fetch(`/api/health?${suffix}`, {cache: "no-store"});
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
