(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "survey";
  const suffix = `token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
  const dom = {
    root: document.getElementById("survey"),
    system: document.getElementById("system-name"),
    overview: document.getElementById("overview"),
    content: document.getElementById("content"),
    footer: document.getElementById("footer"),
  };
  let lastRevision = -1;
  let pollActive = false;
  let readySent = false;

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  function safeNumber(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function credits(value) {
    const amount = safeNumber(value);
    if (!amount) return "";
    if (amount >= 1e6) return `${(amount / 1e6).toFixed(2)} M`;
    if (amount >= 1e3) return `${Math.round(amount / 1e3)} K`;
    return Math.round(amount).toLocaleString();
  }

  function valueRange(low, high) {
    low = safeNumber(low); high = safeNumber(high);
    if (!high) return "";
    return low === high ? credits(low) : `${credits(low)}–${credits(high)}`;
  }

  function applyTheme(theme = {}, effects = {}) {
    const mapping = {
      bg: "bg", panel: "panel", panel_raised: "raised", border: "border",
      border_soft: "soft", accent: "accent", orange: "orange", text: "text",
      muted: "muted", dim: "dim", green: "green", yellow: "yellow", red: "red",
    };
    for (const [key, css] of Object.entries(mapping)) {
      if (/^#[0-9a-f]{6}$/i.test(String(theme[key] || ""))) {
        document.documentElement.style.setProperty(`--${css}`, theme[key]);
      }
    }
    document.documentElement.style.setProperty("--scale", String(safeNumber(effects.text_scale) || 1));
    dom.root.classList.toggle("no-crt", !effects.crt);
    dom.root.classList.toggle("reduced-motion", Boolean(effects.reduced_motion));
  }

  function detailStates(row) {
    const total = Math.max(0, Math.round(safeNumber(row.bio_count)));
    const details = Array.isArray(row.bio_details) ? row.bio_details : [];
    const completed = Math.max(
      Math.round(safeNumber(row.complete)),
      details.filter((item) => item.kind === "complete").length,
    );
    const sampled = details.filter((item) => item.kind === "sample").length;
    const detected = details.filter((item) => item.kind === "detected").length;
    return [
      ...Array(completed).fill("complete"),
      ...Array(sampled).fill("sample"),
      ...Array(detected).fill("detected"),
      ...Array(Math.max(0, total - completed - sampled - detected)).fill("unresolved"),
    ].slice(0, total);
  }

  function appendNodes(parent, row) {
    const states = detailStates(row);
    if (!states.length) return;
    const rail = node("span", "bio-nodes");
    for (const state of states) rail.appendChild(node("i", `bio-node ${state}`));
    parent.appendChild(rail);
  }

  function appendDetails(parent, details, limit = 3) {
    for (const detail of (details || []).slice(0, limit)) {
      const kind = String(detail.kind || "");
      const symbol = {complete: "✓", sample: "●", detected: "○"}[kind] || "·";
      const progress = kind === "sample" && safeNumber(detail.progress)
        ? ` ${Math.min(3, safeNumber(detail.progress))}/3` : "";
      parent.appendChild(node(
        "span", `detail-token ${kind}`,
        `${symbol} ${detail.display_name || detail.name || "Organic"}${progress}`,
      ));
    }
  }

  function targetCard(row, bodyMode = false) {
    const bio = Math.max(0, Math.round(safeNumber(row.bio_count)));
    const done = Math.max(0, Math.round(safeNumber(row.complete)));
    const geo = Math.max(0, Math.round(safeNumber(row.geo_count)));
    const complete = Boolean(row.bio_complete || (bio && done >= bio));
    const value = valueRange(row.min_value, row.max_value);
    const card = node("article", `target${complete ? " complete" : ""}${!bio && geo ? " geo-only" : ""}`);
    const head = node("div", "target-head");
    head.appendChild(node("span", "target-name", row.display_name || row.name || "Unknown body"));
    const badges = node("span", "badges");
    if (bio) badges.appendChild(node("b", "badge bio", `BIO ${done}/${bio}`));
    if (geo) badges.appendChild(node("b", "badge geo", `GEO ${geo}`));
    if (row.needs_dss) badges.appendChild(node("b", "badge dss", "DSS"));
    if (complete && value) badges.appendChild(node("b", "badge", `BASE ${value}`));
    head.appendChild(badges); card.appendChild(head);

    const detail = node("div", "target-detail");
    if (!complete) {
      appendNodes(detail, row);
      appendDetails(detail, row.bio_details || row.rows || [], bodyMode ? 3 : 2);
    }
    if (row.notable) detail.appendChild(node("span", "notable", "◆ NOTABLE"));
    if (value && !complete) detail.appendChild(node("span", "value", `EST ${value}`));
    if (detail.childNodes.length) card.appendChild(detail);
    return card;
  }

  function sampleCard(sampling) {
    const progress = Math.max(1, Math.min(3, Math.round(safeNumber(sampling.progress) || 1)));
    const card = node("article", "sample-card");
    const nodes = node("div", "sample-nodes");
    for (let index = 1; index <= 3; index += 1) {
      nodes.appendChild(node("i", `sample-node${index <= progress ? " done" : ""}`, index));
    }
    card.appendChild(nodes);
    const copy = node("div", "sample-copy");
    copy.appendChild(node("strong", "sample-species", sampling.species || "Biological sample"));
    const status = node("div", "sample-status");
    status.appendChild(node("span", "", `SAMPLE ${progress}/3`));
    let range = "SEEK NEXT COLONY";
    if (sampling.clear) range = "CLEAR FOR NEXT";
    else if (sampling.min_distance_m != null && sampling.colony_m) {
      range = `${Math.round(safeNumber(sampling.min_distance_m)).toLocaleString()}/${Math.round(safeNumber(sampling.colony_m)).toLocaleString()} M`;
    }
    status.appendChild(node("span", sampling.clear ? "clear" : "", range));
    copy.appendChild(status); card.appendChild(copy);
    return card;
  }

  function notableCard(row) {
    const card = node("article", "notable-card");
    card.appendChild(node("strong", "", `${row.icons || "◆"} ${row.display_name || row.name || "Notable body"}`));
    const line = node("span");
    line.appendChild(node("i", "", "SURVEY VALUE"));
    line.appendChild(node("b", "", row.value_line || ""));
    card.appendChild(line);
    return card;
  }

  function overview(model) {
    dom.overview.replaceChildren();
    const bodyMode = model.mode === "body";
    const body = model.body || {};
    const rows = Array.isArray(model.rows) ? model.rows : [];
    const bio = bodyMode
      ? safeNumber(body.bio_count)
      : rows.reduce((sum, row) => sum + safeNumber(row.bio_count), 0);
    const done = bodyMode
      ? safeNumber(body.organic_complete_count)
      : rows.reduce((sum, row) => sum + safeNumber(row.complete), 0);
    const geo = bodyMode
      ? safeNumber(body.geo_count)
      : rows.reduce((sum, row) => sum + safeNumber(row.geo_count), 0);
    const line = node("div", "overview-line");
    line.appendChild(node(
      "strong", "overview-primary",
      bodyMode ? (model.body_display || body.name || "SURFACE TARGET") : `BIO SIGNALS ${bio} · ANALYSED ${done} · GEO ${geo}`,
    ));
    const scan = bodyMode
      ? `BIO ${done}/${bio}${geo ? ` · GEO ${geo}` : ""}`
      : model.total_known && safeNumber(model.total)
        ? `FSS ${safeNumber(model.scanned)}/${safeNumber(model.total)}`
        : "FSS INTAKE";
    line.appendChild(node("span", "overview-meta", scan));
    dom.overview.appendChild(line);
    const rail = node("div", "overview-rail");
    const fill = node("i");
    fill.style.setProperty("--fill", `${bio ? Math.min(100, (done / bio) * 100) : 0}%`);
    rail.appendChild(fill); dom.overview.appendChild(rail);
  }

  function render(snapshot = {}) {
    applyTheme(snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.survey || {};
    const bodyMode = model.mode === "body";
    dom.root.classList.toggle("body", bodyMode);
    dom.root.classList.toggle("system", !bodyMode);
    dom.system.textContent = String(model.system || "SYSTEM").toUpperCase();
    dom.content.replaceChildren(); dom.footer.replaceChildren();
    if (!model.mode) {
      dom.overview.replaceChildren(node("div", "overview-primary", "AWAITING SURVEY DATA"));
      return;
    }
    overview(model);
    if (model.sampling) dom.content.appendChild(sampleCard(model.sampling));
    const rows = Array.isArray(model.rows) ? model.rows : [];
    if (bodyMode) {
      const body = model.body || {};
      const samplingName = String((model.sampling || {}).species || "").toLowerCase();
      const bodyDetails = rows.filter((detail) => {
        if (!samplingName) return true;
        const names = [detail.name, detail.display_name]
          .map((value) => String(value || "").toLowerCase())
          .filter(Boolean);
        return !names.some((name) => name.includes(samplingName) || samplingName.includes(name));
      });
      const projected = {
        ...body,
        display_name: model.body_display || body.name,
        complete: body.organic_complete_count,
        bio_details: bodyDetails,
        min_value: model.min_value,
        max_value: model.max_value,
        notable: model.notable,
      };
      if (rows.length || safeNumber(body.geo_count) || model.notable) {
        dom.content.appendChild(targetCard(projected, true));
      }
    } else {
      const active = rows.filter((row) => !row.bio_complete);
      const complete = rows.filter((row) => row.bio_complete);
      for (const row of active) dom.content.appendChild(targetCard(row));
      if (complete.length) {
        const label = node("div", "group-label");
        label.appendChild(node("span", "", "COMPLETED BIOLOGY"));
        label.appendChild(node("span", "", `${complete.length} SURFACE${complete.length === 1 ? "" : "S"}`));
        dom.content.appendChild(label);
        for (const row of complete) dom.content.appendChild(targetCard(row));
      }
    }
    for (const row of (model.notable_rows || [])) dom.content.appendChild(notableCard(row));

    if (bodyMode) {
      dom.footer.appendChild(node("span", "", "BIOLOGICAL SURFACE WORKBOARD"));
      dom.footer.appendChild(node("span", "credits", `BIO BASE ${valueRange(model.min_value, model.max_value) || "-"}`));
    } else {
      const complete = rows.filter((row) => row.bio_complete).length;
      const low = rows.reduce((sum, row) => sum + safeNumber(row.min_value), 0);
      const high = rows.reduce((sum, row) => sum + safeNumber(row.max_value), 0);
      dom.footer.appendChild(node("span", "", `TARGETS ${rows.length} · OPEN ${rows.length - complete} · COMPLETE ${complete}`));
      dom.footer.appendChild(node("span", "credits", valueRange(low, high) ? `BIO BASE ${valueRange(low, high)}` : ""));
    }
  }

  async function refresh(revision) {
    const response = await fetch(`/api/snapshot?${suffix}`, {cache: "no-store"});
    if (!response.ok) return;
    render(await response.json());
    lastRevision = revision;
    try {
      await fetch(`/api/rendered?${suffix}`, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({revision}),
      });
      if (!readySent) {
        readySent = true;
        await fetch(`/api/ready?${suffix}`, {method: "POST", body: "{}"});
      }
    } catch (_) {}
  }

  async function poll() {
    if (pollActive) return;
    pollActive = true;
    try {
      const response = await fetch(`/api/health?${suffix}`, {cache: "no-store"});
      if (response.ok) {
        const revision = Number((await response.json()).revision);
        if (Number.isFinite(revision) && revision !== lastRevision) await refresh(revision);
      }
    } catch (_) {
    } finally {
      pollActive = false;
    }
  }

  poll();
  window.setInterval(poll, 300);
})();
