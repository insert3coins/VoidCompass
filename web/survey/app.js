(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "survey";
  const dom = {
    root: document.getElementById("survey"),
    overview: document.getElementById("overview"),
    content: document.getElementById("content"),
    footer: document.getElementById("footer"),
  };
  let previousMotionState = null;
  let motionClassTimer = 0;
  let atlas = null;
  let atlasCycleTimer = 0;
  let atlasTurnTimer = 0;
  let bioPinCycleTimer = 0;
  let routine = null;
  let routineCycleTimer = 0;
  const ATLAS_CYCLE_MS = 8000;
  const ATLAS_CONTENT_BUDGET = 520;
  const ATLAS_PAGE_CARD_LIMIT = 8;
  const BIO_PIN_LIMIT = 8;
  const BIO_PIN_CYCLE_MS = 10000;
  const ROUTINE_CYCLE_MS = 10000;
  const ROUTINE_LIMIT = 8;

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

  // These are class illustrations, not inferred images of individual bodies.
  // A signal-only body has no Scan/PlanetClass yet and remains unclassified.
  function planetKind(planetClass) {
    const label = String(planetClass || "").trim().toLowerCase();
    if (/earth[- ]?like/.test(label)) return "earthlike";
    if (/ammonia world/.test(label)) return "ammonia";
    if (/water world/.test(label)) return "water";
    if (/water giant|gas giant.*water/.test(label)) return "gas-water";
    if (/gas giant.*ammonia/.test(label)) return "gas-ammonia";
    if (/gas giant|helium rich giant/.test(label)) return "gas";
    if (/rocky ice/.test(label)) return "rocky-ice";
    if (/icy body/.test(label)) return "icy";
    if (/high metal content|metal rich/.test(label)) return "metal";
    if (/rocky body/.test(label)) return "rocky";
    return "unknown";
  }

  function designation(row, system = "") {
    if (row.designation) return String(row.designation);
    const name = String(row.name || "Unknown body");
    const prefix = `${system} `;
    return system && name.toLowerCase().startsWith(prefix.toLowerCase())
      ? name.slice(prefix.length) : name;
  }

  function classLabel(row) {
    return String(row.class_label || row.planet_class || "CLASS UNCONFIRMED")
      .replace(/ body$/i, "");
  }

  function planetOrb(row, large = false) {
    const kind = planetKind(row.planet_class);
    const ringCount = Math.max(0, Math.round(safeNumber(row.ring_count)));
    const orb = node("span", `planet-orb planet-${kind}${ringCount ? " has-rings" : ""}${large ? " large" : ""}`);
    orb.dataset.planetKind = kind;
    orb.setAttribute("aria-hidden", "true");
    orb.title = `${classLabel(row)} illustration${ringCount ? ` · ${ringCount} ring${ringCount === 1 ? "" : "s"}` : ""}`;
    orb.appendChild(node("i", "planet-ring"));
    orb.appendChild(node("i", "planet-sphere"));
    orb.appendChild(node("i", "planet-glint"));
    return orb;
  }

  function identityKey(value) {
    return String(value || "unknown").trim().toLowerCase();
  }

  function rowKey(row = {}) {
    return row.body_id == null
      ? identityKey(row.name || row.display_name)
      : `body:${row.body_id}`;
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
      recent: Boolean(row.recent_scan),
      scanStamp: String(row.scan_timestamp || ""),
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
      fresh: (current.recent && !previous.recent)
        || Boolean(current.scanStamp && current.scanStamp !== previous.scanStamp),
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
    motionClassTimer = window.setTimeout(() => {
      dom.root.classList.remove(...names);
      // Atlas cards are detached and reattached as pages turn. Retire
      // one-shot journal acknowledgements so paging never replays old events.
      const cards = atlas
        ? atlas.pages.flatMap((page) => page.map((entry) => entry.element))
        : [...dom.content.children];
      if (atlas?.sample) cards.push(atlas.sample);
      for (const card of cards) {
        for (const element of [card, ...card.querySelectorAll("[class*='event-']")]) {
          for (const className of [...element.classList]) {
            if (className.startsWith("event-")) element.classList.remove(className);
          }
        }
      }
    }, 1100);
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

  function targetCard(row, event = {}, system = "", focused = false) {
    const bio = Math.max(0, Math.round(safeNumber(row.bio_count)));
    const done = Math.max(0, Math.round(safeNumber(row.complete)));
    const geo = Math.max(0, Math.round(safeNumber(row.geo_count)));
    const mining = Math.max(0, Math.round(safeNumber(row.mining_count)));
    const complete = Boolean(row.bio_complete || (bio && done >= bio));
    const value = valueRange(row.min_value, row.max_value);
    const compactRoutine = row.priority === false && row.expanded !== true && !focused;
    const eventClasses = [
      event.fresh ? "event-new-target" : "",
      event.completed ? "event-target-complete" : "",
      event.mapped ? "event-mapped" : "",
      event.value || event.notable ? "event-value" : "",
    ].filter(Boolean).join(" ");
    const card = node("article", `target${focused ? " focus-target" : ""}${complete ? " complete" : ""}${!bio && (geo || mining) ? " surface-only" : ""}${row.priority === false ? " routine" : ""}${compactRoutine ? " compact" : ""}${eventClasses ? ` ${eventClasses}` : ""}`);
    const planet = node("div", "planet-cell");
    planet.appendChild(planetOrb(row, focused));
    card.appendChild(planet);
    const landableKnown = Object.prototype.hasOwnProperty.call(row, "landable_known")
      ? row.landable_known === true
      : Object.prototype.hasOwnProperty.call(row, "landable") && row.landable !== null;
    if (compactRoutine) {
      const summary = node("div", "routine-summary");
      const primary = node("div", "routine-primary");
      primary.appendChild(node("strong", "target-name", designation(row, system)));
      if (row.recent_scan) primary.appendChild(node("b", "target-kicker routine-latest", "LATEST SCAN"));
      summary.appendChild(primary);
      const facts = node("div", "routine-facts");
      facts.appendChild(node("span", "routine-class", classLabel(row)));
      const atmosphere = String(row.atmosphere_label || "").trim();
      if (atmosphere) {
        const detail = node("span", "routine-atmosphere", atmosphere);
        detail.title = atmosphere;
        facts.appendChild(detail);
      }
      if (safeNumber(row.ring_count) > 0) facts.appendChild(node("b", "routine-chip", `RINGS ${Math.round(safeNumber(row.ring_count))}`));
      if (landableKnown) facts.appendChild(node("b", "routine-chip", row.landable ? "LAND" : "NO LAND"));
      if (row.first_footfall) facts.appendChild(node("b", "routine-chip", "1ST FOOTFALL"));
      const probes = Math.max(0, Math.round(safeNumber(row.dss_probes_used)));
      const target = Math.max(0, Math.round(safeNumber(row.dss_efficiency_target)));
      if (probes && target) facts.appendChild(node("b", "routine-chip", `DSS ${probes}/${target}`));
      else facts.appendChild(node("b", "routine-chip", row.needs_dss ? "DSS OPEN" : "MAPPED"));
      summary.appendChild(facts);
      card.appendChild(summary);
      return card;
    }
    const head = node("div", "target-head");
    const identity = node("div", "target-identity");
    const eyebrow = node("div", "target-eyebrow");
    eyebrow.appendChild(node("span", "target-kicker", focused ? "SURFACE FOCUS" : row.recent_scan ? "LATEST SCAN" : (complete ? "SURVEY COMPLETE" : "SURVEY TARGET")));
    if (row.terraformable) eyebrow.appendChild(node("b", "environment-tag terraformable", "TERRAFORMABLE"));
    if (row.notable) eyebrow.appendChild(node("b", "environment-tag notable-tag", "◆ NOTABLE"));
    identity.appendChild(eyebrow);
    identity.appendChild(node("strong", "target-name", designation(row, system)));
    const environment = node("div", "target-environment");
    environment.appendChild(node("span", "target-class", classLabel(row)));
    const atmosphere = String(row.atmosphere_label || "").trim();
    if (atmosphere) {
      const atmos = node("span", "target-atmosphere", atmosphere);
      atmos.title = atmosphere;
      environment.appendChild(atmos);
    }
    if (safeNumber(row.ring_count) > 0) environment.appendChild(node("span", "target-rings", `RINGS ${Math.round(safeNumber(row.ring_count))}`));
    identity.appendChild(environment);
    head.appendChild(identity);
    const badges = node("span", "badges");
    if (bio) badges.appendChild(node("b", `badge bio${event.bio ? " event-signal" : ""}`, `BIO ${done}/${bio}`));
    if (geo) badges.appendChild(node("b", `badge geo${event.geo ? " event-signal" : ""}`, `GEO ${geo}`));
    if (mining) badges.appendChild(node("b", `badge mining${event.mining ? " event-signal" : ""}`, `MINING ${mining}`));
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
    if (row.first_footfall) badges.appendChild(node("b", "badge footfall", "1ST FOOTFALL"));
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
    if (detail.childNodes.length) card.appendChild(detail);
    if (value || row.notable || row.priority === false) {
      const foot = node("div", "target-foot");
      foot.appendChild(node("span", "target-foot-status", row.priority === false ? "CATALOGUED BODY" : complete ? "BIOLOGY COMPLETE" : bio ? "BIOLOGY IN PROGRESS" : "SURFACE SIGNALS"));
      if (value) foot.appendChild(node("span", `value${event.value ? " event-value-badge" : ""}`, `BIO BASE ${value}`));
      card.appendChild(foot);
    }
    return card;
  }

  function sampleCard(sampling, event = {}) {
    const progress = Math.max(1, Math.min(3, Math.round(safeNumber(sampling.progress) || 1)));
    const distanceKnown = sampling.min_distance_m != null
      && Number.isFinite(Number(sampling.min_distance_m));
    const spacing = Math.max(0, Math.round(safeNumber(sampling.colony_m)));
    const distance = distanceKnown ? Math.max(0, Math.round(safeNumber(sampling.min_distance_m))) : 0;
    const ready = progress < 3 && (sampling.clear === true
      || (distanceKnown && spacing > 0 && distance >= spacing));
    const analysisPending = progress === 3;
    const eventClasses = [
      event.fresh ? "event-sample-start" : "",
      event.progress ? "event-sample-step" : "",
      event.complete ? "event-sample-complete" : "",
    ].filter(Boolean).join(" ");
    const card = node("article", `sample-card${ready ? " ready" : ""}${analysisPending ? " analysis-pending" : ""}${eventClasses ? ` ${eventClasses}` : ""}`);
    const heading = node("div", "sample-heading");
    heading.appendChild(node("span", "sample-kicker", "EXOBIO · GENETIC SEQUENCE"));
    heading.appendChild(node("b", "sample-count", `${String(progress).padStart(2, "0")} / 03`));
    card.appendChild(heading);
    const species = node("strong", "sample-species", sampling.species || "Biological sample");
    species.title = sampling.species || "Biological sample";
    card.appendChild(species);
    const nodes = node("div", "sample-nodes");
    nodes.style.setProperty("--track-fill", `${(progress - 1) * 33.333}%`);
    for (let index = 1; index <= 3; index += 1) {
      const acknowledged = index === progress && (event.fresh || event.progress || event.complete);
      const step = node("div", `sample-step${index <= progress ? " captured" : ""}${index === progress ? " current" : ""}${index === progress + 1 ? " next" : ""}`);
      step.appendChild(node("i", `sample-node${index <= progress ? " done" : ""}${acknowledged ? " acknowledged" : ""}`, String(index).padStart(2, "0")));
      step.appendChild(node("span", "sample-step-label", index <= progress ? "CAPTURED" : index === progress + 1 ? (ready ? "READY" : "NEXT") : "PENDING"));
      nodes.appendChild(step);
    }
    card.appendChild(nodes);
    const clearance = node("div", "sample-clearance");
    let action = "DISTANCE UNAVAILABLE";
    let context = spacing ? `${spacing.toLocaleString()} M REQUIRED` : "COLONY SPACING UNKNOWN";
    if (analysisPending) {
      action = "SAMPLES SECURED";
      context = "AWAITING ANALYSIS";
    } else if (ready) {
      action = `READY FOR SAMPLE ${String(progress + 1).padStart(2, "0")}`;
      context = distanceKnown && spacing
        ? `${distance.toLocaleString()} / ${spacing.toLocaleString()} M SPACING`
        : "COLONY SPACING CLEAR";
    } else if (distanceKnown && spacing) {
      action = `${Math.max(0, spacing - distance).toLocaleString()} M TO SAMPLE ${String(progress + 1).padStart(2, "0")}`;
      context = `${distance.toLocaleString()} / ${spacing.toLocaleString()} M SPACING`;
    } else if (distanceKnown) {
      context = `${distance.toLocaleString()} M FROM NEAREST SAMPLE`;
    }
    clearance.appendChild(node("strong", "sample-action", action));
    clearance.appendChild(node("span", "sample-distance", context));
    card.appendChild(clearance);
    if (!analysisPending && distanceKnown && spacing) {
      const meter = node("div", "sample-range-meter");
      meter.setAttribute("aria-hidden", "true");
      const fill = node("i");
      fill.style.width = `${Math.min(100, (distance / spacing) * 100)}%`;
      meter.appendChild(fill);
      card.appendChild(meter);
    }
    return card;
  }

  function notableCard(row, event = {}, system = "") {
    const card = node("article", `notable-card${event.fresh ? " event-new-notable" : ""}${event.value ? " event-value" : ""}`);
    card.appendChild(planetOrb(row));
    const copy = node("div", "notable-copy");
    copy.appendChild(node("small", "", "◆ HIGH-VALUE BODY"));
    copy.appendChild(node("strong", "", designation(row, system)));
    copy.appendChild(node("span", "", classLabel(row)));
    card.appendChild(copy);
    card.appendChild(node("b", "notable-value", row.value_line || ""));
    return card;
  }

  function contentChildrenHeight(children) {
    const gap = Number.parseFloat(getComputedStyle(dom.content).rowGap) || 0;
    return children.reduce((total, child) => total + child.getBoundingClientRect().height, 0)
      + Math.max(0, children.length - 1) * gap;
  }

  function stopAtlasCycle() {
    if (atlasCycleTimer) window.clearInterval(atlasCycleTimer);
    if (atlasTurnTimer) window.clearTimeout(atlasTurnTimer);
    if (bioPinCycleTimer) window.clearInterval(bioPinCycleTimer);
    atlasCycleTimer = 0;
    atlasTurnTimer = 0;
    bioPinCycleTimer = 0;
    atlas = null;
    dom.root.classList.remove("paged", "page-turn");
  }

  function stopRoutineCycle() {
    if (routineCycleTimer) window.clearInterval(routineCycleTimer);
    routineCycleTimer = 0;
    routine = null;
  }

  function renderRoutineStrip(board, rows, index, system, limit) {
    const start = index * limit;
    const visible = rows.slice(start, start + limit);
    const heading = node("div", "routine-strip-heading");
    const compressed = dom.root.classList.contains("scale-huge")
      && dom.root.classList.contains("survey-congested");
    heading.appendChild(node("strong", "", compressed ? "OTHER" : "OTHER SCANNED PLANETS"));
    heading.appendChild(node("span", "", rows.length > limit
      ? compressed ? `${start + 1}–${start + visible.length}/${rows.length}`
        : `${start + 1}–${start + visible.length} / ${rows.length} · AUTO ${ROUTINE_CYCLE_MS / 1000}S`
      : `${rows.length} ${rows.length === 1 ? "WORLD" : "WORLDS"}`));
    const grid = node("div", "routine-strip-grid");
    for (const row of visible) {
      const pin = node("div", `routine-pin${row.recent_scan ? " recent" : ""}`);
      pin.dataset.bodyKey = rowKey(row);
      const className = classLabel(row);
      const mapping = row.needs_dss ? "DSS OPEN" : "MAPPED";
      pin.setAttribute("aria-label", `${row.name || designation(row, system)} · ${className} · ${mapping}`);
      pin.appendChild(planetOrb(row));
      const copy = node("div", "routine-pin-copy");
      copy.appendChild(node("strong", "routine-pin-name", designation(row, system)));
      copy.appendChild(node("span", "routine-pin-class", className));
      pin.appendChild(copy);
      pin.appendChild(node("b", "routine-pin-status", row.recent_scan ? "NEW" : row.needs_dss ? "DSS" : "MAP"));
      grid.appendChild(pin);
    }
    board.replaceChildren(heading, grid);
  }

  function nextRoutinePage() {
    if (!routine || routine.pages < 2) return;
    routine.page = (routine.page + 1) % routine.pages;
    renderRoutineStrip(routine.board, routine.rows, routine.page, routine.system, routine.limit);
  }

  function routineStrip(rows, system, samplingActive = false) {
    if (!rows.length) {
      stopRoutineCycle();
      return null;
    }
    const previous = routine;
    const limit = dom.root.classList.contains("scale-huge") ? (samplingActive ? 2 : 4)
      : dom.root.classList.contains("scale-large") ? (samplingActive ? 4 : 6) : ROUTINE_LIMIT;
    const identity = `${system}|${rows.map(rowKey).join("|")}`;
    const pages = Math.ceil(rows.length / limit);
    const page = previous?.identity === identity
      ? Math.min(previous.page, pages - 1) : 0;
    const board = node("section", "routine-strip");
    board.setAttribute("aria-label", "Other scanned planets");
    routine = {board, rows, system, limit, identity, pages, page};
    renderRoutineStrip(board, rows, page, system, limit);
    if (pages > 1 && !routineCycleTimer) {
      routineCycleTimer = window.setInterval(nextRoutinePage, ROUTINE_CYCLE_MS);
    } else if (pages <= 1 && routineCycleTimer) {
      window.clearInterval(routineCycleTimer);
      routineCycleTimer = 0;
    }
    return board;
  }

  function renderBioPins(board, rows, index, system, limit) {
    const start = index * limit;
    const visible = rows.slice(start, start + limit);
    const heading = node("div", "bio-pinboard-heading");
    const compressed = dom.root.classList.contains("scale-huge")
      && dom.root.classList.contains("survey-congested");
    heading.appendChild(node("strong", "", compressed ? "BIO PINS" : "PINNED BIOLOGY"));
    heading.appendChild(node("span", "", rows.length > limit
      ? compressed ? `${start + 1}–${start + visible.length}/${rows.length}`
        : `${start + 1}–${start + visible.length} / ${rows.length} · AUTO ${BIO_PIN_CYCLE_MS / 1000}S`
      : `${rows.length} SCANNED ${rows.length === 1 ? "WORLD" : "WORLDS"}`));
    const grid = node("div", "bio-pinboard-grid");
    for (const row of visible) {
      const total = Math.max(0, Math.round(safeNumber(row.bio_count)));
      const complete = Math.max(0, Math.round(safeNumber(row.complete)));
      const pin = node("div", `bio-pin${row.bio_complete ? " complete" : ""}${row.recent_scan ? " recent" : ""}`);
      pin.dataset.bodyKey = rowKey(row);
      pin.setAttribute("aria-label", `${row.name || designation(row, system)} · biology ${complete} of ${total}`);
      pin.appendChild(planetOrb(row));
      pin.appendChild(node("strong", "bio-pin-name", designation(row, system)));
      pin.appendChild(node("b", "bio-pin-count", `${complete}/${total}`));
      grid.appendChild(pin);
    }
    board.replaceChildren(heading, grid);
  }

  function nextBioPinPage() {
    if (!atlas?.pinboard || atlas.pinPages < 2) return;
    atlas.pinPage = (atlas.pinPage + 1) % atlas.pinPages;
    renderBioPins(atlas.pinboard, atlas.pinRows, atlas.pinPage,
      atlas.system, atlas.pinLimit);
  }

  function atlasBanner(page, pages, first, last, total) {
    const banner = node("div", "atlas-page-banner");
    banner.style.setProperty("--page-fill", `${(page / pages) * 100}%`);
    const compressed = dom.root.classList.contains("scale-huge")
      && dom.root.classList.contains("survey-congested");
    banner.appendChild(node("strong", "", `ATLAS PAGE ${page} / ${pages}`));
    banner.appendChild(node("span", "", compressed ? ` · ${first}–${last} OF ${total}`
      : ` · ${first}–${last} OF ${total} · AUTO ${ATLAS_CYCLE_MS / 1000}S`));
    return banner;
  }

  function showAtlasPage(animate = false) {
    if (!atlas || !atlas.pages.length) return;
    if (atlasTurnTimer) window.clearTimeout(atlasTurnTimer);
    atlasTurnTimer = 0;
    dom.root.classList.remove("page-turn");
    const current = atlas.pages[atlas.index];
    dom.content.replaceChildren();
    if (atlas.sample) dom.content.appendChild(atlas.sample);
    if (atlas.routineStrip) dom.content.appendChild(atlas.routineStrip);
    if (atlas.pinboard) dom.content.appendChild(atlas.pinboard);
    dom.content.appendChild(atlasBanner(
      atlas.index + 1, atlas.pages.length,
      current[0].index + 1, current[current.length - 1].index + 1, atlas.total,
    ));
    for (const entry of current) dom.content.appendChild(entry.element);
    if (animate) {
      dom.root.classList.add("page-turn");
      atlasTurnTimer = window.setTimeout(() => dom.root.classList.remove("page-turn"), 400);
    }
  }

  function nextAtlasPage() {
    if (!atlas || atlas.pages.length < 2) return;
    atlas.index = (atlas.index + 1) % atlas.pages.length;
    showAtlasPage(true);
  }

  function paginateSystemCards(cards, sample, routineBoard, pinRows, model, motion) {
    if (!cards.length) {
      stopAtlasCycle();
      return;
    }
    const fullHeight = contentChildrenHeight([...dom.content.children]);
    const pageBudget = dom.root.classList.contains("scale-huge") ? 450
      : dom.root.classList.contains("scale-large") ? 490
        : ATLAS_CONTENT_BUDGET;
    if (cards.length <= ATLAS_PAGE_CARD_LIMIT && fullHeight <= pageBudget) {
      stopAtlasCycle();
      return;
    }
    const previous = atlas;
    const gap = Number.parseFloat(getComputedStyle(dom.content).rowGap) || 0;
    const sampleHeight = sample ? sample.getBoundingClientRect().height : 0;
    const routineHeight = routineBoard ? routineBoard.getBoundingClientRect().height : 0;
    const sharedSpace = Boolean(sample && routineBoard);
    const pinLimit = dom.root.classList.contains("scale-huge") ? (sharedSpace ? 2 : 4)
      : dom.root.classList.contains("scale-large") ? (sharedSpace ? 4 : 6) : BIO_PIN_LIMIT;
    const pinIdentity = `${model.system}|${pinRows.map(rowKey).join("|")}`;
    const pinPages = Math.ceil(pinRows.length / pinLimit);
    const pinPage = pinRows.length && previous?.pinIdentity === pinIdentity
      ? Math.min(previous.pinPage, pinPages - 1) : 0;
    const pinboard = pinRows.length ? node("section", "bio-pinboard") : null;
    if (pinboard) {
      pinboard.setAttribute("aria-label", "Pinned scanned planets with biological signals");
      renderBioPins(pinboard, pinRows, pinPage, model.system, pinLimit);
      dom.content.insertBefore(pinboard, cards[0]?.element || null);
    }
    const pinHeight = pinboard ? pinboard.getBoundingClientRect().height : 0;
    const probe = atlasBanner(1, 1, 1, cards.length, cards.length);
    dom.content.appendChild(probe);
    const bannerHeight = probe.getBoundingClientRect().height;
    probe.remove();
    const pageHeight = (entries, cardHeight) => sampleHeight + routineHeight + pinHeight + bannerHeight + cardHeight
      + gap * (entries.length + (sample ? 1 : 0) + (routineBoard ? 1 : 0) + (pinboard ? 1 : 0));
    const pages = [];
    let current = [];
    let currentHeight = 0;
    for (const entry of cards) {
      entry.height = entry.element.getBoundingClientRect().height;
      if (current.length && (current.length >= ATLAS_PAGE_CARD_LIMIT
          || pageHeight([...current, entry], currentHeight + entry.height) > pageBudget)) {
        pages.push(current);
        current = [];
        currentHeight = 0;
      }
      current.push(entry);
      currentHeight += entry.height;
    }
    if (current.length) pages.push(current);
    const height = Math.max(...pages.map((page) => pageHeight(
      page, page.reduce((sum, entry) => sum + entry.height, 0),
    )));
    const identity = `${model.system}|${cards.map((entry) => entry.key).join("|")}`;
    let index = previous?.identity === identity
      ? Math.min(previous.index, pages.length - 1) : 0;
    const changed = new Set([...motion.rows.keys(), ...motion.notable.keys()]);
    if (changed.size) {
      const changedPage = pages.findIndex((page) => page.some((entry) => changed.has(entry.key)));
      if (changedPage >= 0) index = changedPage;
    }
    atlas = {pages, index, total: cards.length, sample, routineStrip: routineBoard, pinboard, pinRows,
      pinIdentity, pinPage, pinPages, pinLimit, system: model.system, identity,
      maxContentHeight: height};
    dom.root.classList.add("paged");
    showAtlasPage();
    if (!atlasCycleTimer) atlasCycleTimer = window.setInterval(nextAtlasPage, ATLAS_CYCLE_MS);
    if (pinPages > 1 && !bioPinCycleTimer) {
      bioPinCycleTimer = window.setInterval(nextBioPinPage, BIO_PIN_CYCLE_MS);
    } else if (pinPages <= 1 && bioPinCycleTimer) {
      window.clearInterval(bioPinCycleTimer);
      bioPinCycleTimer = 0;
    }
  }

  window.VoidCompassSurveyAtlas = Object.freeze({
    nextPage: nextAtlasPage,
    nextPinPage: nextBioPinPage,
    nextRoutinePage,
    getState: () => atlas
      ? {page: atlas.index + 1, pages: atlas.pages.length, total: atlas.total,
        pinned: atlas.pinRows.length, pinPage: atlas.pinPage + 1,
        pinPages: atlas.pinPages, routine: routine?.rows.length || 0,
        routinePage: routine ? routine.page + 1 : 0, routinePages: routine?.pages || 0}
      : {page: 0, pages: 0, total: 0, pinned: 0, pinPage: 0, pinPages: 0,
        routine: routine?.rows.length || 0, routinePage: routine ? routine.page + 1 : 0,
        routinePages: routine?.pages || 0},
  });

  function overview(model, motion = {}) {
    dom.overview.replaceChildren();
    const bodyMode = model.mode === "body";
    const body = model.body || {};
    const rows = Array.isArray(model.rows) ? model.rows : [];
    const visibleBodies = rows.length + (Array.isArray(model.notable_rows) ? model.notable_rows.length : 0);
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
    const heading = node("div", "overview-heading");
    const title = node("div", "overview-title");
    const context = node("div", "overview-context");
    const mode = node("span", "", bodyMode ? "BODY" : "SYSTEM");
    mode.id = "mode-label";
    const system = node("strong", "", String(model.system || "UNKNOWN SYSTEM"));
    system.id = "system-name";
    context.appendChild(mode);
    context.appendChild(node("i", "context-separator", "·"));
    context.appendChild(system);
    title.appendChild(context);
    title.appendChild(node("strong", "overview-primary", bodyMode ? designation(body, model.system) : `${visibleBodies} ${visibleBodies === 1 ? "BODY" : "BODIES"} IN VIEW`));
    heading.appendChild(title);
    const counter = node("div", "overview-counter");
    counter.appendChild(node("small", "", "BIO ANALYSED"));
    counter.appendChild(node("strong", "overview-meta", `${done}/${bio}`));
    heading.appendChild(counter);
    dom.overview.appendChild(heading);
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
    const metrics = node("div", "overview-metrics");
    const items = bodyMode
      ? [["BIO", bio], ["GEO", geo], ["MINING", mining], ["DSS", body.dss_complete ? "MAPPED" : "OPEN"]]
      : [["FSS", model.total_known && safeNumber(model.total) ? `${safeNumber(model.scanned)}/${safeNumber(model.total)}` : "INTAKE"], ["GEO", geo], ["MINING", mining], ["SCOPE", model.scope === "all" ? "EXPANDED" : "COMPACT"]];
    for (const [label, value] of items) {
      const item = node("span", "overview-metric");
      item.appendChild(node("small", "", label));
      item.appendChild(node("b", "", value));
      metrics.appendChild(item);
    }
    dom.overview.appendChild(metrics);
  }

  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(dom.root, snapshot.theme || {}, snapshot.effects || {});
    const textScale = safeNumber(snapshot.effects?.text_scale) || 1;
    dom.root.classList.toggle("scale-large", textScale > 1.35);
    dom.root.classList.toggle("scale-huge", textScale > 1.75);
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
    dom.content.replaceChildren(); dom.footer.replaceChildren();
    if (!model.mode) {
      stopAtlasCycle();
      stopRoutineCycle();
      dom.root.classList.remove("survey-congested");
      dom.root.classList.add("empty");
      dom.overview.replaceChildren();
      applyMotionClass({enabled: false});
      return;
    }
    dom.root.classList.remove("empty");
    overview(model, motion);
    const sample = model.sampling ? sampleCard(model.sampling, motion.sampling || {}) : null;
    if (sample) dom.content.appendChild(sample);
    const cards = [];
    const addCard = (element, key, row) => {
      cards.push({index: cards.length, element, key, row});
      dom.content.appendChild(element);
    };
    if (bodyMode) {
      stopAtlasCycle();
      stopRoutineCycle();
      dom.root.classList.remove("survey-congested");
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
      dom.content.appendChild(targetCard(projected, motion.body || {}, model.system, true));
    } else {
      const routineRows = rows.filter((row) => row.priority === false
        && String(row.planet_class || "").trim());
      dom.root.classList.toggle("survey-congested", Boolean(sample && routineRows.length
        && rows.some((row) => safeNumber(row.bio_count) > 0)));
      const board = routineStrip(routineRows, model.system, Boolean(sample));
      if (board) dom.content.appendChild(board);
      const detailedRows = rows.filter((row) => row.priority !== false || row.expanded === true
        || !String(row.planet_class || "").trim());
      const active = detailedRows.filter((row) => !row.bio_complete || row.recent_scan);
      const complete = detailedRows.filter((row) => row.bio_complete && !row.recent_scan);
      for (const row of active) addCard(targetCard(row, motion.rows.get(rowKey(row)) || {}, model.system), rowKey(row), row);
      if (complete.length) {
        const label = node("div", "group-label");
        label.appendChild(node("span", "", "COMPLETED BIOLOGY"));
        label.appendChild(node("span", "", `${complete.length} SURFACE${complete.length === 1 ? "" : "S"}`));
        dom.content.appendChild(label);
        for (const row of complete) addCard(targetCard(row, motion.rows.get(rowKey(row)) || {}, model.system), rowKey(row), row);
      }
    }
    for (const row of (model.notable_rows || [])) {
      const element = notableCard(row, motion.notable.get(rowKey(row)) || {}, model.system);
      if (bodyMode) dom.content.appendChild(element);
      else addCard(element, rowKey(row), row);
    }
    if (!bodyMode) {
      const bioPins = rows.filter((row) => safeNumber(row.bio_count) > 0
        && String(row.planet_class || "").trim());
      paginateSystemCards(cards, sample, routine?.board || null, bioPins, model, motion);
    }

    if (bodyMode) {
      dom.footer.appendChild(node("span", "", "SURFACE FIELD NOTES"));
      const lifetime = model.dss_stats?.lifetime || {};
      const mapped = Math.max(0, Math.round(safeNumber(lifetime.mapped)));
      const efficient = Math.max(0, Math.round(safeNumber(lifetime.efficient)));
      const receipt = mapped ? ` · DSS ${efficient}/${mapped}` : "";
      dom.footer.appendChild(node("span", "credits", `BIO BASE ${valueRange(model.min_value, model.max_value) || "—"}${receipt}`));
    } else {
      const complete = rows.filter((row) => row.bio_complete).length;
      const low = rows.reduce((sum, row) => sum + safeNumber(row.min_value), 0);
      const high = rows.reduce((sum, row) => sum + safeNumber(row.max_value), 0);
      const scope = model.scope === "all" ? "EXPANDED ATLAS" : "COMPACT ATLAS";
      const priority = rows.filter((row) => row.priority !== false).length;
      const routine = rows.length - priority;
      const mapped = rows.filter((row) => !row.needs_dss).length;
      const notableOnly = (model.notable_rows || []).length;
      const summary = `${scope} ${rows.length + notableOnly} · PRIORITY ${priority} · ROUTINE ${routine} · DONE ${complete} · MAPPED ${mapped}${notableOnly ? ` · NOTABLE ${notableOnly}` : ""}`;
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
    const contentHeight = atlas?.maxContentHeight
      ?? contentChildrenHeight([...dom.content.children]);
    // Measure children, not the viewport: the viewport itself grows with the
    // host window and would otherwise create a positive resize feedback loop.
    const style = getComputedStyle(dom.content);
    const top = Number.parseFloat(style.top) || 0;
    const bottom = Number.parseFloat(style.bottom) || 0;
    return Math.max(150, Math.ceil(top + contentHeight + bottom + 1));
  }

  VoidCompassOverlay.startPolling({
    token, overlay, render, contentHeight: renderedContentHeight, interval: 300,
  });
})();
