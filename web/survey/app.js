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
  let previousMotionState = null;
  let motionClassTimer = 0;

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

  function identityKey(value) {
    return String(value || "unknown").trim().toLowerCase();
  }

  function rowKey(row = {}) {
    return identityKey(row.name || row.display_name);
  }

  function detailKey(detail = {}) {
    return identityKey(detail.name || detail.display_name);
  }

  function detailState(detail = {}) {
    return {
      kind: String(detail.kind || "detected"),
      progress: Math.max(0, Math.round(safeNumber(detail.progress))),
      value: Math.max(safeNumber(detail.value), safeNumber(detail.max_value)),
    };
  }

  function detailStateMap(details = []) {
    return new Map((details || []).map((detail) => [detailKey(detail), detailState(detail)]));
  }

  function rowState(row = {}) {
    const details = row.bio_details || row.rows || [];
    return {
      bio: Math.max(0, Math.round(safeNumber(row.bio_count))),
      geo: Math.max(0, Math.round(safeNumber(row.geo_count))),
      mining: Math.max(0, Math.round(safeNumber(row.mining_count))),
      complete: Math.max(0, Math.round(safeNumber(row.complete || row.organic_complete_count))),
      bioComplete: Boolean(row.bio_complete),
      needsDss: Boolean(row.needs_dss),
      probes: Math.max(0, Math.round(safeNumber(row.dss_probes_used))),
      notable: Boolean(row.notable),
      value: Math.max(safeNumber(row.max_value), safeNumber(row.min_value)),
      details: detailStateMap(details),
    };
  }

  function captureMotionState(model = {}) {
    const rows = Array.isArray(model.rows) ? model.rows : [];
    const body = model.body || {};
    const sampling = model.sampling || null;
    return {
      system: identityKey(model.system),
      mode: String(model.mode || ""),
      scanned: Math.max(0, Math.round(safeNumber(model.scanned))),
      total: Math.max(0, Math.round(safeNumber(model.total))),
      rows: new Map(rows.map((row) => [rowKey(row), rowState(row)])),
      bodyKey: rowKey({...body, display_name: model.body_display || body.name}),
      body: rowState({
        ...body,
        complete: body.organic_complete_count,
        bio_complete: safeNumber(body.bio_count) > 0
          && safeNumber(body.organic_complete_count) >= safeNumber(body.bio_count),
        bio_details: rows,
        min_value: model.min_value,
        max_value: model.max_value,
        notable: model.notable,
      }),
      notable: new Map((model.notable_rows || []).map((row) => [
        rowKey(row), Math.max(safeNumber(row.value), safeNumber(row.max_value)),
      ])),
      sampling: sampling ? {
        key: identityKey(sampling.species),
        progress: Math.max(1, Math.min(3, Math.round(safeNumber(sampling.progress) || 1))),
        clear: Boolean(sampling.clear),
      } : null,
    };
  }

  function compareDetails(current, previous = new Map()) {
    const events = new Map();
    for (const [key, detail] of current.entries()) {
      const old = previous.get(key);
      if (!old) {
        events.set(key, {fresh: true, progress: detail.progress > 0, complete: detail.kind === "complete"});
        continue;
      }
      const progressed = detail.progress > old.progress || (old.kind !== "sample" && detail.kind === "sample");
      const completed = old.kind !== "complete" && detail.kind === "complete";
      if (progressed || completed || detail.value > old.value) {
        events.set(key, {progress: progressed, complete: completed, value: detail.value > old.value});
      }
    }
    return events;
  }

  function compareRow(current, previous) {
    if (!previous) {
      return {fresh: true, bio: current.bio > 0, geo: current.geo > 0,
        mining: current.mining > 0,
        value: current.value > 0, notable: current.notable, details: new Map()};
    }
    return {
      fresh: false,
      bio: current.bio > previous.bio,
      geo: current.geo > previous.geo,
      mining: current.mining > previous.mining,
      value: current.value > previous.value,
      notable: current.notable && !previous.notable,
      mapped: (previous.needsDss && !current.needsDss) || current.probes > previous.probes,
      bioProgress: current.complete > previous.complete,
      completed: current.bioComplete && !previous.bioComplete,
      details: compareDetails(current.details, previous.details),
    };
  }

  function motionContext(model = {}) {
    const current = captureMotionState(model);
    const previous = previousMotionState;
    previousMotionState = current;
    if (!previous) return {enabled: false, rows: new Map(), notable: new Map()};

    const sameSystem = current.system === previous.system;
    const sameMode = sameSystem && current.mode === previous.mode;
    const rowEvents = new Map();
    if (sameMode && current.mode === "system") {
      for (const [key, row] of current.rows.entries()) {
        const event = compareRow(row, previous.rows.get(key));
        if (Object.values(event).some((value) => value === true) || event.details.size) {
          rowEvents.set(key, event);
        }
      }
    }

    let bodyEvent = null;
    if (sameMode && current.mode === "body" && current.bodyKey === previous.bodyKey) {
      bodyEvent = compareRow(current.body, previous.body);
    }

    const notableEvents = new Map();
    if (sameMode) {
      for (const [key, value] of current.notable.entries()) {
        const old = previous.notable.get(key);
        if (old == null || value > old) notableEvents.set(key, {fresh: old == null, value: value > (old || 0)});
      }
    }

    let sampling = null;
    if (current.sampling) {
      const old = previous.sampling;
      const sampleEvent = {
        fresh: !old || old.key !== current.sampling.key,
        progress: Boolean(old && old.key === current.sampling.key
          && current.sampling.progress > old.progress),
        complete: Boolean(old && old.key === current.sampling.key
          && current.sampling.progress >= 3 && old.progress < 3),
      };
      if (Object.values(sampleEvent).some(Boolean)) sampling = sampleEvent;
    }

    const currentBio = current.mode === "body"
      ? current.body.complete
      : [...current.rows.values()].reduce((sum, row) => sum + row.complete, 0);
    const currentBioTotal = current.mode === "body"
      ? current.body.bio
      : [...current.rows.values()].reduce((sum, row) => sum + row.bio, 0);
    const previousBio = previous.mode === "body"
      ? previous.body.complete
      : [...previous.rows.values()].reduce((sum, row) => sum + row.complete, 0);
    const previousBioTotal = previous.mode === "body"
      ? previous.body.bio
      : [...previous.rows.values()].reduce((sum, row) => sum + row.bio, 0);
    const fill = currentBioTotal ? Math.min(100, (currentBio / currentBioTotal) * 100) : 0;
    const fromFill = previousBioTotal ? Math.min(100, (previousBio / previousBioTotal) * 100) : fill;

    return {
      enabled: true,
      rows: rowEvents,
      body: bodyEvent,
      notable: notableEvents,
      sampling,
      systemChanged: current.system !== previous.system,
      focusEntered: sameSystem && previous.mode !== "body" && current.mode === "body",
      focusLeft: sameSystem && previous.mode === "body" && current.mode !== "body",
      scanAdvanced: sameSystem && current.scanned > previous.scanned,
      scanCompleted: sameSystem && current.total > 0
        && current.scanned >= current.total
        && (previous.total <= 0 || previous.scanned < previous.total),
      bioAdvanced: sameMode && fill > fromFill,
      fromFill,
    };
  }

  function applyMotionClass(motion) {
    const names = [
      "event-active", "event-system", "event-focus-in", "event-focus-out",
      "event-scan-complete",
    ];
    dom.root.classList.remove(...names);
    if (!motion.enabled) return;
    // Restart only the short acknowledgement layer; ordinary revisions do not
    // receive a class and therefore never produce ambient redraw flicker.
    void dom.root.offsetWidth;
    const activity = motion.rows.size || motion.notable.size || motion.sampling
      || motion.scanAdvanced || motion.scanCompleted || motion.bioAdvanced;
    if (activity) dom.root.classList.add("event-active");
    if (motion.systemChanged) dom.root.classList.add("event-system");
    if (motion.focusEntered) dom.root.classList.add("event-focus-in");
    if (motion.focusLeft) dom.root.classList.add("event-focus-out");
    if (motion.scanCompleted) dom.root.classList.add("event-scan-complete");
    window.clearTimeout(motionClassTimer);
    motionClassTimer = window.setTimeout(() => dom.root.classList.remove(...names), 1100);
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
    const opacity = Number(effects.opacity);
    document.body.style.opacity = String(Number.isFinite(opacity) ? Math.max(.4, Math.min(1, opacity)) : 1);
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

  function appendNodes(parent, row, event = {}) {
    const states = detailStates(row);
    if (!states.length) return;
    const rail = node("span", `bio-nodes${event.bioProgress ? " event-progress" : ""}`);
    for (const state of states) rail.appendChild(node("i", `bio-node ${state}`));
    parent.appendChild(rail);
  }

  function biologicalRow(detail, event = {}) {
    const kind = String(detail.kind || "detected");
    const eventClasses = [
      event.fresh ? "event-new-detail" : "",
      event.progress ? "event-sample-progress" : "",
      event.complete ? "event-bio-complete" : "",
      event.value ? "event-value" : "",
    ].filter(Boolean).join(" ");
    const row = node("div", `biological-row ${kind}${eventClasses ? ` ${eventClasses}` : ""}`);
    const identity = node("span", "biological-identity");
    const symbol = {complete: "✓", sample: "●", detected: "○", predicted: "?", possible: "·"}[kind] || "·";
    identity.appendChild(node("i", "biological-symbol", symbol));
    identity.appendChild(node(
      "strong", "biological-name",
      detail.display_name || detail.name || "Organic",
    ));
    row.appendChild(identity);

    const facts = node("span", "biological-facts");
    const progress = Math.max(0, Math.min(3, Math.round(safeNumber(detail.progress))));
    const status = kind === "sample" && progress
      ? `${progress}/3`
      : String(detail.status || kind).toUpperCase();
    facts.appendChild(node("span", "biological-status", status));
    const value = safeNumber(detail.value)
      ? credits(detail.value)
      : valueRange(detail.min_value, detail.max_value);
    if (value) facts.appendChild(node("b", "biological-value", value));
    row.appendChild(facts);
    return row;
  }

  function orderedBiologicalDetails(details) {
    const priority = {sample: 0, detected: 1, predicted: 2, possible: 3, complete: 4};
    return [...(details || [])].sort((left, right) => {
      const leftRank = priority[String(left.kind || "detected")] ?? 2;
      const rightRank = priority[String(right.kind || "detected")] ?? 2;
      return leftRank - rightRank || String(left.display_name || left.name || "")
        .localeCompare(String(right.display_name || right.name || ""));
    });
  }

  function targetCard(row, event = {}) {
    const bio = Math.max(0, Math.round(safeNumber(row.bio_count)));
    const done = Math.max(0, Math.round(safeNumber(row.complete)));
    const geo = Math.max(0, Math.round(safeNumber(row.geo_count)));
    const mining = Math.max(0, Math.round(safeNumber(row.mining_count)));
    const complete = Boolean(row.bio_complete || (bio && done >= bio));
    const value = valueRange(row.min_value, row.max_value);
    const eventClasses = [
      event.fresh ? "event-new-target" : "",
      event.completed ? "event-target-complete" : "",
      event.mapped ? "event-mapped" : "",
      event.value || event.notable ? "event-value" : "",
    ].filter(Boolean).join(" ");
    const card = node("article", `target${complete ? " complete" : ""}${!bio && (geo || mining) ? " surface-only" : ""}${row.priority === false ? " routine" : ""}${eventClasses ? ` ${eventClasses}` : ""}`);
    const head = node("div", "target-head");
    head.appendChild(node("span", "target-name", row.display_name || row.name || "Unknown body"));
    const badges = node("span", "badges");
    if (bio) badges.appendChild(node("b", `badge bio${event.bio ? " event-signal" : ""}`, `BIO ${done}/${bio}`));
    if (geo) badges.appendChild(node("b", `badge geo${event.geo ? " event-signal" : ""}`, `GEO ${geo}`));
    if (mining) badges.appendChild(node("b", `badge mining${event.mining ? " event-signal" : ""}`, `MINING ${mining}`));
    const landableKnown = Object.prototype.hasOwnProperty.call(row, "landable_known")
      ? row.landable_known === true
      : Object.prototype.hasOwnProperty.call(row, "landable") && row.landable !== null;
    if (landableKnown) {
      const landable = Boolean(row.landable);
      const badge = node(
        "b", `badge ${landable ? "landable" : "non-landable"}`,
        landable ? "LAND" : "NO LAND",
      );
      badge.title = landable ? "Landable surface" : "Not landable";
      badges.appendChild(badge);
    }
    const probes = Math.max(0, Math.round(safeNumber(row.dss_probes_used)));
    const target = Math.max(0, Math.round(safeNumber(row.dss_efficiency_target)));
    if (probes && target) {
      const efficient = row.dss_efficiency_met === true;
      const badge = node("b", `badge dss-result${efficient ? " efficient" : ""}${event.mapped ? " event-lock" : ""}`,
        `DSS ${efficient ? "✓ " : ""}${probes}/${target}`);
      badge.title = efficient ? "DSS efficiency target met" : "DSS mapping complete";
      badges.appendChild(badge);
    } else if (row.needs_dss) badges.appendChild(node("b", "badge dss", "DSS"));
    if (row.priority === false) badges.appendChild(node("b", "badge routine", "BODY"));
    if (complete && value) badges.appendChild(node("b", `badge${event.value ? " event-value-badge" : ""}`, `BASE ${value}`));
    head.appendChild(badges); card.appendChild(head);

    const biological = orderedBiologicalDetails(row.bio_details || row.rows || []);
    const detail = node("div", `target-detail${biological.length ? " biological-list" : ""}`);
    if (!complete) {
      if (biological.length) {
        for (const entry of biological) {
          detail.appendChild(biologicalRow(entry, event.details?.get(detailKey(entry)) || {}));
        }
      } else {
        appendNodes(detail, row, event);
      }
    }
    if (row.notable) detail.appendChild(node("span", "notable", "◆ NOTABLE"));
    if (value && !complete) detail.appendChild(node("span", "value", `EST ${value}`));
    if (detail.childNodes.length) card.appendChild(detail);
    return card;
  }

  function sampleCard(sampling, event = {}) {
    const progress = Math.max(1, Math.min(3, Math.round(safeNumber(sampling.progress) || 1)));
    const eventClasses = [
      event.fresh ? "event-sample-start" : "",
      event.progress ? "event-sample-step" : "",
      event.complete ? "event-sample-complete" : "",
    ].filter(Boolean).join(" ");
    const card = node("article", `sample-card${eventClasses ? ` ${eventClasses}` : ""}`);
    const nodes = node("div", "sample-nodes");
    for (let index = 1; index <= 3; index += 1) {
      const acknowledged = index === progress && (event.fresh || event.progress || event.complete);
      nodes.appendChild(node("i", `sample-node${index <= progress ? " done" : ""}${acknowledged ? " acknowledged" : ""}`, index));
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

  function notableCard(row, event = {}) {
    const card = node("article", `notable-card${event.fresh ? " event-new-notable" : ""}${event.value ? " event-value" : ""}`);
    card.appendChild(node("strong", "", `${row.icons || "◆"} ${row.display_name || row.name || "Notable body"}`));
    const line = node("span");
    line.appendChild(node("i", "", "SURVEY VALUE"));
    line.appendChild(node("b", "", row.value_line || ""));
    card.appendChild(line);
    return card;
  }

  function overview(model, motion = {}) {
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
    const mining = bodyMode
      ? safeNumber(body.mining_count)
      : rows.reduce((sum, row) => sum + safeNumber(row.mining_count), 0);
    const line = node("div", "overview-line");
    line.appendChild(node(
      "strong", "overview-primary",
      bodyMode ? (model.body_display || body.name || "SURFACE TARGET") : `BIO SIGNALS ${bio} · ANALYSED ${done} · GEO ${geo} · MINING ${mining}`,
    ));
    const scan = bodyMode
      ? `BIO ${done}/${bio}${geo ? ` · GEO ${geo}` : ""}${mining ? ` · MINING ${mining}` : ""}`
      : model.total_known && safeNumber(model.total)
        ? `FSS ${safeNumber(model.scanned)}/${safeNumber(model.total)}`
        : "FSS INTAKE";
    line.appendChild(node("span", "overview-meta", scan));
    dom.overview.appendChild(line);
    const rail = node("div", "overview-rail");
    const fill = node("i");
    const fillPercent = bio ? Math.min(100, (done / bio) * 100) : 0;
    fill.style.setProperty("--fill", `${fillPercent}%`);
    fill.style.setProperty("--from-fill", `${Number.isFinite(motion.fromFill) ? motion.fromFill : fillPercent}%`);
    rail.style.setProperty("--fill", `${fillPercent}%`);
    if (motion.bioAdvanced) fill.classList.add("event-progress");
    rail.appendChild(fill);
    rail.appendChild(node("b", "rail-sweep"));
    rail.appendChild(node("em", "rail-beacon"));
    dom.overview.appendChild(rail);
  }

  function render(snapshot = {}) {
    applyTheme(snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.survey || {};
    const motion = motionContext(model);
    const bodyMode = model.mode === "body";
    const rows = Array.isArray(model.rows) ? model.rows : [];
    const total = Math.max(0, safeNumber(model.total));
    const scanned = Math.max(0, safeNumber(model.scanned));
    const body = model.body || {};
    const openBiology = bodyMode
      ? safeNumber(body.bio_count) > safeNumber(body.organic_complete_count)
      : rows.some((row) => safeNumber(row.bio_count) > safeNumber(row.complete));
    dom.root.classList.toggle("body", bodyMode);
    dom.root.classList.toggle("system", !bodyMode);
    dom.root.classList.toggle("scan-active", Boolean(
      !bodyMode && model.total_known && total > 0 && scanned < total
    ));
    dom.root.classList.toggle("sampling-active", Boolean(model.sampling));
    dom.root.classList.toggle("signal-open", Boolean(openBiology || model.sampling));
    dom.root.classList.toggle("survey-locked", Boolean(
      !bodyMode && model.total_known && total > 0 && scanned >= total
    ));
    dom.system.textContent = String(model.system || "SYSTEM").toUpperCase();
    dom.content.replaceChildren(); dom.footer.replaceChildren();
    if (!model.mode) {
      dom.root.classList.add("empty");
      dom.overview.replaceChildren();
      applyMotionClass({enabled: false});
      return;
    }
    dom.root.classList.remove("empty");
    overview(model, motion);
    if (model.sampling) dom.content.appendChild(sampleCard(model.sampling, motion.sampling || {}));
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
        landable_known: Object.prototype.hasOwnProperty.call(body, "landable")
          && body.landable !== null,
      };
      if (rows.length || safeNumber(body.geo_count) || safeNumber(body.mining_count) || model.notable) {
        dom.content.appendChild(targetCard(projected, motion.body || {}));
      }
    } else {
      const active = rows.filter((row) => !row.bio_complete);
      const complete = rows.filter((row) => row.bio_complete);
      for (const row of active) dom.content.appendChild(targetCard(row, motion.rows.get(rowKey(row)) || {}));
      if (complete.length) {
        const label = node("div", "group-label");
        label.appendChild(node("span", "", "COMPLETED BIOLOGY"));
        label.appendChild(node("span", "", `${complete.length} SURFACE${complete.length === 1 ? "" : "S"}`));
        dom.content.appendChild(label);
        for (const row of complete) dom.content.appendChild(targetCard(row, motion.rows.get(rowKey(row)) || {}));
      }
    }
    for (const row of (model.notable_rows || [])) {
      dom.content.appendChild(notableCard(row, motion.notable.get(rowKey(row)) || {}));
    }

    if (bodyMode) {
      dom.footer.appendChild(node("span", "", "BIOLOGICAL SURFACE WORKBOARD"));
      const lifetime = model.dss_stats?.lifetime || {};
      const mapped = Math.max(0, Math.round(safeNumber(lifetime.mapped)));
      const efficient = Math.max(0, Math.round(safeNumber(lifetime.efficient)));
      const receipt = mapped ? ` · DSS ${efficient}/${mapped}` : "";
      dom.footer.appendChild(node("span", "credits", `BIO BASE ${valueRange(model.min_value, model.max_value) || "-"}${receipt}`));
    } else {
      const complete = rows.filter((row) => row.bio_complete).length;
      const low = rows.reduce((sum, row) => sum + safeNumber(row.min_value), 0);
      const high = rows.reduce((sum, row) => sum + safeNumber(row.max_value), 0);
      const scope = model.scope === "all" ? "ALL BODIES" : "PRIORITY TARGETS";
      const priority = rows.filter((row) => row.priority !== false).length;
      const mapped = rows.filter((row) => !row.needs_dss).length;
      const summary = model.scope === "all"
        ? `${scope} ${rows.length} · PRIORITY ${priority} · MAPPED ${mapped}`
        : `${scope} ${rows.length} · OPEN ${rows.length - complete} · COMPLETE ${complete}`;
      dom.footer.appendChild(node("span", "", summary));
      const session = model.dss_stats?.session || {};
      const mappedSession = Math.max(0, Math.round(safeNumber(session.mapped)));
      const efficientSession = Math.max(0, Math.round(safeNumber(session.efficient)));
      const dssReceipt = mappedSession ? `DSS EFF ${efficientSession}/${mappedSession}` : "";
      const bioReceipt = valueRange(low, high) ? `BIO BASE ${valueRange(low, high)}` : "";
      dom.footer.appendChild(node("span", "credits", [dssReceipt, bioReceipt].filter(Boolean).join(" · ")));
    }
    applyMotionClass(motion);
  }

  function renderedContentHeight() {
    const children = [...dom.content.children];
    const gap = Number.parseFloat(getComputedStyle(dom.content).rowGap) || 0;
    const contentHeight = children.reduce(
      (total, child) => total + child.getBoundingClientRect().height,
      0,
    ) + Math.max(0, children.length - 1) * gap;
    // Content begins at 67px. Reserve the footer's 24px lower band plus an
    // eight-pixel compositor-safe margin. Measure children directly rather
    // than content.scrollHeight: the content viewport itself expands with the
    // window and would otherwise create a positive resize feedback loop.
    return Math.max(90, Math.ceil(67 + contentHeight + 32));
  }

  async function refresh(revision) {
    const response = await fetch(`/api/snapshot?${suffix}`, {cache: "no-store"});
    if (!response.ok) return;
    render(await response.json());
    await new Promise((resolve) => requestAnimationFrame(resolve));
    const contentHeight = renderedContentHeight();
    lastRevision = revision;
    try {
      await fetch(`/api/rendered?${suffix}`, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({revision, content_height: contentHeight}),
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
