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
  // Survey Operations runs on one clock. The spotlight (when the Studio's
  // Spotlight rotation allows it) and every region that overflows its slot
  // advance together on a single beat, so the overlay never runs staggered
  // pagers that compete for the pilot's attention.
  const CYCLE_MS = 10000;
  // A journal event (fresh scan, DSS map, sample) holds the spotlight on the
  // affected world long enough to read before the rotation resumes.
  const HOLD_MS = 30000;
  // Most manifest rows and catalogue lines shown per text-scale tier before
  // paging on the shared clock. No body is ever hidden behind "+N more".
  const LIMITS = {
    normal: {manifest: 8, surface: 3, notable: 2, chips: 3, rows: 4},
    large: {manifest: 7, surface: 3, notable: 2, chips: 3, rows: 3},
    huge: {manifest: 6, surface: 2, notable: 2, chips: 3, rows: 3},
  };
  // Overlay height budget. When a busy system (or a sampling card) would
  // exceed it, the lowest-priority regions give up lines first — the quiet
  // catalogue before the biology manifest — and page instead of growing.
  const HEIGHT_BUDGET = {normal: 640, large: 680, huge: 700};
  const MANIFEST_MIN_ROWS = 3;
  const MANIFEST_FLOOR_ROWS = 2;
  const SHRINK_ORDER = ["other", "landable", "notable", "surface"];
  const collator = new Intl.Collator("en", {numeric: true, sensitivity: "base"});
  let cycle = null;
  let cycleTimer = 0;

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

  function count(value) {
    return Math.max(0, Math.round(safeNumber(value)));
  }

  function money(value) {
    const amount = safeNumber(value);
    if (amount <= 0) return "";
    // Trailing zeros are noise at a glance: 1.6M and 19M, not 1.60M/19.0M.
    const trim = (number, digits) => number.toFixed(digits).replace(/\.?0+$/, "");
    if (amount >= 1e9) return `${trim(amount / 1e9, 1)}B`;
    if (amount >= 1e7) return `${trim(amount / 1e6, 1)}M`;
    if (amount >= 1e6) return `${trim(amount / 1e6, 2)}M`;
    if (amount >= 1e3) return `${Math.round(amount / 1e3)}K`;
    return Math.round(amount).toLocaleString();
  }

  function moneyRange(low, high) {
    low = safeNumber(low); high = safeNumber(high);
    if (high <= 0) return "";
    const top = money(high);
    if (low <= 0 || low >= high) return top;
    const bottom = money(low);
    const unit = top.slice(-1);
    // Share a trailing unit: 4.29–21.7M scans faster than 4.29M–21.7M.
    return /[KMB]/.test(unit) && bottom.endsWith(unit)
      ? `${bottom.slice(0, -1)}–${top}` : `${bottom}–${top}`;
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

  // One-line rows and chips carry a short class; the spotlight keeps the full
  // journal label. Unscanned signal bodies stay explicitly unconfirmed.
  function shortClass(row) {
    const label = String(row.planet_class || "").trim().toLowerCase();
    if (!label) return "Unconfirmed";
    const sudarsky = label.match(/sudarsky class ([ivx]+)/);
    if (sudarsky) return `Class ${sudarsky[1].toUpperCase()} GG`;
    const rules = [
      [/earth[- ]?like/, "Earth-like"], [/ammonia world/, "Ammonia world"],
      [/water world/, "Water world"], [/water giant/, "Water giant"],
      [/gas giant.*water/, "Water-life GG"], [/gas giant.*ammonia/, "Ammonia-life GG"],
      [/helium/, "Helium GG"], [/gas giant/, "Gas giant"], [/rocky ice/, "Rocky ice"],
      [/icy/, "Icy"], [/high metal/, "High metal"], [/metal rich/, "Metal rich"],
      [/rocky/, "Rocky"],
    ];
    for (const [pattern, text] of rules) if (pattern.test(label)) return text;
    return classLabel(row);
  }

  function landableKnown(row) {
    return Object.prototype.hasOwnProperty.call(row, "landable_known")
      ? row.landable_known === true
      : Object.prototype.hasOwnProperty.call(row, "landable") && row.landable !== null;
  }

  function planetOrb(row, large = false) {
    const kind = planetKind(row.planet_class);
    const ringCount = count(row.ring_count);
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

  function retireEventClasses(elements) {
    for (const element of elements) {
      for (const className of [...element.classList]) {
        if (className.startsWith("event-")) element.classList.remove(className);
      }
    }
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
      // Pagers detach and reattach items as the clock turns. Retire one-shot
      // journal acknowledgements everywhere so a page turn never replays them.
      const detached = (cycle?.pagers || []).flatMap((pager) => pager.pages.flat());
      for (const item of [...dom.content.querySelectorAll("[class*='event-']"), ...detached]) {
        retireEventClasses([item, ...item.querySelectorAll("[class*='event-']")]);
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

  function signalPips(row, event = {}) {
    const rail = node("span", `bio-nodes${event.bioProgress ? " event-progress" : ""}`);
    for (const state of detailStates(row)) rail.appendChild(node("i", `bio-node ${state}`));
    return rail;
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
    // The symbol already says detected/analysed; spend width on the words
    // only where they add information: sample progress and predictions.
    const status = kind === "sample" && progress ? `${progress}/3`
      : kind === "predicted" || kind === "possible" ? String(detail.status || kind).toUpperCase() : "";
    if (status) facts.appendChild(node("span", "biological-status", status));
    const value = safeNumber(detail.value)
      ? money(detail.value)
      : moneyRange(detail.min_value, detail.max_value);
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

  // System rows carry only journal-confirmed biology; predictions belong to
  // the focused body view where the pilot can act on them.
  function systemDetails(row) {
    return orderedBiologicalDetails(row.bio_details || row.rows || [])
      .filter((detail) => ["detected", "sample", "complete"]
        .includes(String(detail.kind || "").toLowerCase()));
  }

  function surfaceBadges(row, event = {}) {
    const badges = node("span", "badges");
    const bio = count(row.bio_count);
    const done = count(row.complete);
    const geo = count(row.geo_count);
    const mining = count(row.mining_count);
    if (bio) badges.appendChild(node("b", `badge bio${event.bio ? " event-signal" : ""}`, `BIO ${done}/${bio}`));
    if (geo) badges.appendChild(node("b", `badge geo${event.geo ? " event-signal" : ""}`, `GEO ${geo}`));
    if (mining) badges.appendChild(node("b", `badge mining${event.mining ? " event-signal" : ""}`, `MINING ${mining}`));
    if (landableKnown(row)) {
      const landable = Boolean(row.landable);
      const badge = node("b", `badge ${landable ? "landable" : "non-landable"}`,
        landable ? "LAND" : "NO LAND");
      badge.title = landable ? "Landable surface" : "Not landable";
      badges.appendChild(badge);
    }
    const probes = count(row.dss_probes_used);
    const target = count(row.dss_efficiency_target);
    if (probes && target) {
      const efficient = row.dss_efficiency_met === true;
      const badge = node("b", `badge dss-result${efficient ? " efficient" : ""}${event.mapped ? " event-lock" : ""}`,
        `DSS ${efficient ? "✓ " : ""}${probes}/${target}`);
      badge.title = efficient ? "DSS efficiency target met" : "DSS mapping complete";
      badges.appendChild(badge);
    } else if (row.needs_dss) badges.appendChild(node("b", "badge dss", "DSS"));
    if (row.first_footfall) badges.appendChild(node("b", "badge footfall", "1ST FOOTFALL"));
    return badges;
  }

  // The spotlight is the one detailed card on screen: the focused body in
  // body mode, or the system world the single clock is currently showing.
  function spotlightCard(row, options = {}) {
    const system = options.system || "";
    const event = options.event || {};
    const bio = count(row.bio_count);
    const done = count(row.complete);
    const complete = Boolean(row.bio_complete || (bio && done >= bio));
    const surfaceOnly = !bio && Boolean(count(row.geo_count) || count(row.mining_count));
    const classes = [
      "target", "spotlight", options.focused ? "focus-target" : "",
      complete ? "complete" : "", surfaceOnly ? "surface-only" : "",
      !bio && !surfaceOnly ? "routine" : "",
      event.fresh ? "event-new-target" : "",
      event.completed ? "event-target-complete" : "",
      event.mapped ? "event-mapped" : "",
      event.value || event.notable ? "event-value" : "",
    ];
    const card = node("article", classes.filter(Boolean).join(" "));
    card.dataset.bodyKey = rowKey(row);
    const planet = node("div", "planet-cell");
    planet.appendChild(planetOrb(row, true));
    card.appendChild(planet);

    const head = node("div", "spot-head");
    const title = node("div", "spot-title");
    title.appendChild(node("strong", "target-name spot-name", designation(row, system)));
    if (options.kicker) title.appendChild(node("b", "spot-kicker", options.kicker));
    if (row.terraformable) title.appendChild(node("b", "environment-tag terraformable", "TF"));
    if (row.notable) title.appendChild(node("b", "environment-tag notable-tag", "◆ NOTABLE"));
    const value = moneyRange(row.min_value, row.max_value);
    if (value) {
      title.appendChild(node("b", `spot-value${event.value ? " event-value-badge" : ""}`, value));
    }
    head.appendChild(title);

    const environment = node("div", "target-environment");
    environment.appendChild(node("span", "target-class", classLabel(row)));
    const atmosphere = String(row.atmosphere_label || "").trim();
    if (atmosphere) environment.appendChild(node("span", "target-atmosphere", atmosphere));
    const gravity = Number(row.gravity_g);
    if (row.gravity_g != null && Number.isFinite(gravity) && gravity > 0) {
      environment.appendChild(node("span", "target-gravity", `${gravity.toFixed(2)} G`));
    }
    if (count(row.ring_count)) environment.appendChild(node("span", "target-rings", `RINGS ${count(row.ring_count)}`));
    head.appendChild(environment);
    head.appendChild(surfaceBadges(row, event));
    card.appendChild(head);

    const details = options.details || orderedBiologicalDetails(row.bio_details || row.rows || []);
    if (details.length) {
      const list = node("div", "target-detail biological-list");
      for (const detail of details) {
        list.appendChild(biologicalRow(detail, event.details?.get(detailKey(detail)) || {}));
      }
      card.appendChild(list);
    } else if (bio && !complete) {
      const pending = node("div", "target-detail pending");
      pending.appendChild(signalPips(row, event));
      pending.appendChild(node("span", "pending-copy", row.needs_dss
        ? "TYPES NOT IDENTIFIED · MAP TO REVEAL" : "TYPES NOT IDENTIFIED"));
      card.appendChild(pending);
    }
    return card;
  }

  // Manifest and catalogue rows share one grid: planet, designation, class,
  // a signal/value readout, and a right-aligned status column.
  function bodyRow(row, options = {}) {
    const system = options.system || "";
    const event = options.event || {};
    const kind = options.kind || "bio";
    const bio = count(row.bio_count);
    const complete = Boolean(bio && (row.bio_complete || count(row.complete) >= bio));
    const classes = [
      "body-row", `row-${kind}`, complete ? "complete" : "",
      row.recent_scan ? "recent" : "",
      String(row.planet_class || "").trim() ? "" : "unclassified",
      event.fresh ? "event-new-target" : "",
      event.completed ? "event-target-complete" : "",
      event.mapped ? "event-mapped" : "",
      event.value ? "event-value" : "",
    ];
    const element = node("div", classes.filter(Boolean).join(" "));
    element.dataset.bodyKey = rowKey(row);
    element.appendChild(planetOrb(row));
    const name = node("span", "row-name");
    name.appendChild(node("strong", "", designation(row, system)));
    if (row.recent_scan) name.appendChild(node("b", "row-tag new", "NEW"));
    element.appendChild(name);
    const identity = node("span", "row-class");
    identity.appendChild(node("span", "", shortClass(row)));
    if (row.terraformable) identity.appendChild(node("b", "row-tag tf", "TF"));
    if (row.notable && kind !== "notable") identity.appendChild(node("b", "row-tag notable", "◆"));
    element.appendChild(identity);

    const meta = node("span", "row-meta");
    const end = node("span", "row-end");
    if (kind === "bio") {
      meta.appendChild(signalPips(row, event));
      end.textContent = moneyRange(row.min_value, row.max_value) || "—";
    } else {
      if (kind === "surface") {
        const signals = [["GEO", count(row.geo_count)], ["MINING", count(row.mining_count)]]
          .filter(([, amount]) => amount).map(([label, amount]) => `${label} ${amount}`);
        meta.textContent = signals.join(" · ");
      } else if (kind === "notable") {
        const line = String(row.notable?.value_line || row.value_line || "").replace(/\s+/g, " ").trim();
        meta.textContent = line;
      } else {
        meta.textContent = String(row.atmosphere_label || "").trim();
      }
      // A notable body's value line already quotes its unclaimed DSS reward.
      const dssInLine = kind === "notable" && /\bDSS\b/.test(meta.textContent);
      if (Object.prototype.hasOwnProperty.call(row, "needs_dss") && !(row.needs_dss && dssInLine)) {
        end.textContent = row.needs_dss ? "DSS" : "✓";
        end.classList.add(row.needs_dss ? "dss-open" : "mapped");
      }
    }
    element.appendChild(meta);
    element.appendChild(end);
    const label = [row.name || designation(row, system), shortClass(row),
      bio ? `biology ${count(row.complete)} of ${bio}` : "", meta.textContent].filter(Boolean);
    element.setAttribute("aria-label", label.join(" · "));
    return element;
  }

  function bodyChip(row, system) {
    const mapped = Object.prototype.hasOwnProperty.call(row, "needs_dss") && !row.needs_dss;
    const chip = node("span", ["body-chip", row.recent_scan ? "recent" : "",
      mapped ? "mapped" : "dss-open", row.first_footfall ? "footfall" : ""].filter(Boolean).join(" "));
    chip.dataset.bodyKey = rowKey(row);
    chip.setAttribute("aria-label", `${row.name || designation(row, system)} · ${shortClass(row)} · ${mapped ? "MAPPED" : "DSS OPEN"}`);
    chip.appendChild(planetOrb(row));
    chip.appendChild(node("strong", "chip-name", designation(row, system)));
    chip.appendChild(node("span", "chip-class", shortClass(row)));
    // A folded catalogue mixes every tier into one line, so a chip carries
    // its own reason for being interesting.
    const signals = [["GEO", count(row.geo_count)], ["MINING", count(row.mining_count)]]
      .filter(([, amount]) => amount).map(([label, amount]) => `${label} ${amount}`);
    if (signals.length) chip.appendChild(node("b", "chip-flag signal", signals.join(" ")));
    if (row.notable || row.value_line) chip.appendChild(node("b", "chip-flag notable", "◆"));
    if (row.recent_scan) chip.appendChild(node("b", "chip-flag new", "NEW"));
    else if (row.first_footfall) chip.appendChild(node("b", "chip-flag footfall", "1ST"));
    else if (mapped) chip.appendChild(node("b", "chip-flag mapped", "✓"));
    return chip;
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

  function sectionHead(label, className = "") {
    const head = node("div", `section-head${className ? ` ${className}` : ""}`);
    head.appendChild(node("strong", "", label));
    head.appendChild(node("i", "section-rule"));
    const counter = node("span", "section-count");
    head.appendChild(counter);
    return {head, counter};
  }

  // Tier the system into what the pilot acts on: biology first, then bodies
  // with surface signals or mapping value, then the landable and quiet rest.
  function classifyRows(model) {
    const system = model.system || "";
    const groups = {biology: [], surface: [], notable: [], landable: [], other: []};
    for (const row of Array.isArray(model.rows) ? model.rows : []) {
      if (count(row.bio_count)) groups.biology.push(row);
      else if (count(row.geo_count) || count(row.mining_count)) groups.surface.push(row);
      else if (row.notable) groups.notable.push(row);
      else if (row.landable && landableKnown(row)) groups.landable.push(row);
      else groups.other.push(row);
    }
    groups.notable.push(...(model.notable_rows || []));
    const byDesignation = (left, right) => collator.compare(
      designation(left, system), designation(right, system),
    );
    // Rows keep their place as scans arrive (NEW marks the latest instead of
    // hoisting it); completed biology settles to the bottom of the manifest.
    groups.biology.sort((left, right) => Number(Boolean(left.bio_complete))
      - Number(Boolean(right.bio_complete)) || byDesignation(left, right));
    for (const key of ["surface", "notable", "landable", "other"]) groups[key].sort(byDesignation);
    return groups;
  }

  function samplingMatches(detail, species) {
    return [detail.name, detail.display_name]
      .map((value) => String(value || "").trim().toLowerCase())
      .some((name) => name && (name.includes(species) || species.includes(name)));
  }

  // The world being sampled: the one holding that species in progress, else
  // any world that lists it.
  function samplingWorld(rows, sampling) {
    const species = String(sampling?.species || "").trim().toLowerCase();
    if (!species) return null;
    const details = (row) => row.bio_details || [];
    return rows.find((row) => details(row).some((detail) =>
      String(detail.kind || "") === "sample" && samplingMatches(detail, species)))
      || rows.find((row) => details(row).some((detail) => samplingMatches(detail, species)))
      || null;
  }

  function eventWeight(event) {
    if (!event) return 0;
    let weight = 0;
    const raise = (value) => { weight = Math.max(weight, value); };
    if (event.completed) raise(6);
    if (event.bioProgress) raise(5);
    for (const detail of event.details?.values() || []) {
      raise(detail.complete || detail.progress ? 5 : detail.fresh ? 4 : 1);
    }
    if (event.mapped) raise(4);
    if (event.fresh || event.bio) raise(3);
    if (event.value || event.notable) raise(1);
    return weight;
  }

  function changedWorld(rows, motionRows) {
    let best = null;
    let bestWeight = 0;
    for (const row of rows) {
      const weight = eventWeight(motionRows.get(rowKey(row)))
        + (row.recent_scan ? 0.5 : 0);
      if (weight >= 1 && weight > bestWeight) {
        best = row;
        bestWeight = weight;
      }
    }
    return best;
  }

  function scaleTier() {
    return dom.root.classList.contains("scale-huge") ? "huge"
      : dom.root.classList.contains("scale-large") ? "large" : "normal";
  }

  function stopCycle() {
    if (cycleTimer) window.clearTimeout(cycleTimer);
    cycleTimer = 0;
    cycle = null;
  }

  // The Studio's Spotlight rotation choice: "auto" turns worlds only when the
  // system has more than the threshold, "always" whenever there are two or
  // more, and "off" keeps the spotlight on the latest journal activity.
  function spotlightRotates(options = {}, worlds = 0) {
    const mode = String(options.spotlight_rotation || "auto").toLowerCase();
    if (worlds < 2 || mode === "off") return false;
    if (mode === "always") return true;
    const threshold = Math.max(2, Math.min(40, Math.round(safeNumber(options.spotlight_threshold) || 8)));
    return worlds > threshold;
  }

  function spotlightTurns() {
    return Boolean(cycle && cycle.rotates && !cycle.locked && cycle.keys.length > 1);
  }

  // A manifest follows a turning spotlight; otherwise an overflowing
  // manifest pages on the clock by itself so every world still comes round.
  function manifestPagesAlone() {
    return Boolean(cycle?.manifest && !spotlightTurns() && cycle.manifest.pages > 1);
  }

  function rotating() {
    return Boolean(cycle && (spotlightTurns() || manifestPagesAlone()
      || cycle.pagers.some((pager) => pager.pages.length > 1)));
  }

  function schedule(delay) {
    if (cycleTimer) window.clearTimeout(cycleTimer);
    cycleTimer = 0;
    if (!rotating()) {
      cycle.periodStart = 0;
      cycle.nextAt = 0;
      return;
    }
    cycle.periodStart = Date.now();
    cycle.nextAt = cycle.periodStart + delay;
    cycleTimer = window.setTimeout(tick, delay);
  }

  function spotlightRow() {
    return cycle.biology.find((row) => rowKey(row) === cycle.spotKey) || cycle.biology[0];
  }

  // While sampling, the genetic-sequence card owns the species in hand; the
  // spotlight lists only the world's remaining biology.
  function spotlightDetails(row) {
    const details = systemDetails(row);
    if (!cycle?.locked || !cycle.samplingSpecies || rowKey(row) !== cycle.spotKey) return details;
    return details.filter((detail) => !samplingMatches(detail, cycle.samplingSpecies));
  }

  function pageDots(page, pages) {
    if (pages <= 1) return "";
    if (pages > 6) return `${page + 1}/${pages}`;
    return Array.from({length: pages}, (_, index) => (index === page ? "●" : "○")).join("");
  }

  function paintSpotlight(motionRows = new Map()) {
    const slot = cycle?.spotlight;
    if (!slot) return;
    const row = spotlightRow();
    const held = cycle.reason === "update" && Date.now() < cycle.holdUntil;
    const kicker = cycle.locked ? "SAMPLING" : row.recent_scan ? "LATEST SCAN"
      : held ? "UPDATED" : row.bio_complete ? "COMPLETE" : "";
    const card = spotlightCard(row, {
      system: cycle.systemName, event: motionRows.get(rowKey(row)) || {},
      kicker, details: spotlightDetails(row),
    });
    if (cycle.periodStart && spotlightTurns()) {
      // A hairline along the card's lower edge fills until the next turn. It
      // is phased from the shared clock, so a data repaint never resets it.
      const meter = node("i", `spot-meter${held || row.recent_scan ? " held" : ""}`);
      meter.setAttribute("aria-hidden", "true");
      meter.style.animationDuration = `${Math.max(1, cycle.nextAt - cycle.periodStart)}ms`;
      meter.style.animationDelay = `${-(Date.now() - cycle.periodStart)}ms`;
      card.appendChild(meter);
    }
    slot.replaceChildren(card);
  }

  function spotlightPage() {
    return Math.floor(Math.max(0, cycle.keys.indexOf(cycle.spotKey)) / cycle.manifest.limit);
  }

  function paintManifest(motionRows = new Map(), rebuild = false, requested = null) {
    const manifest = cycle?.manifest;
    if (!manifest) return;
    // A turning spotlight takes the manifest window with it: when the
    // highlight walks off the visible rows, the list turns on the same beat.
    const page = requested ?? (spotlightTurns() ? spotlightPage() : Math.max(0, manifest.page));
    if (rebuild || page !== manifest.page) {
      manifest.page = page;
      const start = page * manifest.limit;
      const rows = cycle.biology.slice(start, start + manifest.limit);
      manifest.list.replaceChildren(...rows.map((row) => bodyRow(row, {
        system: cycle.systemName, kind: "bio", event: motionRows.get(rowKey(row)) || {},
      })));
      const total = cycle.biology.length;
      manifest.counter.textContent = manifest.pages > 1
        ? `${start + 1}–${start + rows.length} OF ${total} WORLDS`
        : `${total} WORLDS`;
    }
    for (const element of manifest.list.children) {
      element.classList.toggle("spotlit", element.dataset.bodyKey === cycle.spotKey);
    }
  }

  function paintCounter(pager) {
    // A group that fits shows its bodies; the count earns its line only when
    // some of them are on another page.
    pager.counter.textContent = pager.pages.length > 1
      ? `${pager.total} ${pageDots(pager.page, pager.pages.length)}` : "";
    pager.counter.hidden = pager.pages.length <= 1;
  }

  function paintPager(pager) {
    pager.items.replaceChildren(...(pager.pages[pager.page] || []));
    paintCounter(pager);
  }

  function tick() {
    if (cycleTimer) window.clearTimeout(cycleTimer);
    cycleTimer = 0;
    if (!cycle) return;
    if (spotlightTurns()) {
      const index = cycle.keys.indexOf(cycle.spotKey);
      cycle.spotKey = cycle.keys[(index + 1) % cycle.keys.length];
      cycle.reason = "cycle";
      cycle.holdUntil = 0;
    } else if (manifestPagesAlone()) {
      cycle.manifest.page = (cycle.manifest.page + 1) % cycle.manifest.pages;
      paintManifest(new Map(), true, cycle.manifest.page);
    }
    for (const pager of cycle.pagers) {
      if (pager.pages.length > 1) pager.page = (pager.page + 1) % pager.pages.length;
    }
    schedule(CYCLE_MS);
    paintSpotlight();
    paintManifest();
    cycle.pagers.forEach(paintPager);
  }

  // Split rendered items into pages of whole visual lines. A row is one line;
  // chips wrap, so their lines are read back from the live layout.
  function linePages(container, items, maxLines) {
    container.replaceChildren(...items);
    const lines = [];
    let lineTop = null;
    for (const item of items) {
      const top = item.getBoundingClientRect().top;
      if (lineTop === null || Math.abs(top - lineTop) > 4) {
        lines.push([]);
        lineTop = top;
      }
      lines[lines.length - 1].push(item);
    }
    const pages = [];
    for (let index = 0; index < lines.length; index += maxLines) {
      pages.push(lines.slice(index, index + maxLines).flat());
    }
    return pages.length ? pages : [[]];
  }

  function buildLinePager(pager) {
    pager.items.style.minHeight = "";
    pager.pages = linePages(pager.items, pager.elements, pager.lines);
    pager.page = Math.min(pager.page, pager.pages.length - 1);
    // Reserve the first (fullest) page so turning never resizes the band.
    pager.items.replaceChildren(...pager.pages[0]);
    paintCounter(pager);
    pager.items.style.minHeight = `${Math.ceil(pager.items.getBoundingClientRect().height)}px`;
  }

  // Last resort before the biology manifest gives up rows: merge every
  // catalogue tier into one rotating chip line. Each chip keeps its own
  // signal/notable flag, and every body still comes round on the clock.
  function foldCatalogue() {
    const catalogue = cycle.catalogue;
    if (!catalogue || catalogue.folded || cycle.pagers.length < 2) return false;
    catalogue.folded = true;
    const group = node("div", "catalogue-group group-bodies layout-chips folded");
    group.dataset.group = "bodies";
    const head = node("div", "group-label");
    head.appendChild(node("strong", "", "BODIES"));
    const counter = node("span", "group-count");
    head.appendChild(counter);
    const items = node("div", "group-items");
    group.append(head, items);
    catalogue.section.replaceChildren(group);
    const identity = `folded|${catalogue.rows.map(rowKey).join("|")}`;
    const kept = catalogue.previous.find((pager) => pager.key === "bodies");
    const pager = {key: "bodies", items, counter, identity, total: catalogue.rows.length,
      elements: catalogue.rows.map((row) => bodyChip(row, cycle.systemName)),
      lines: 1, pages: [[]], page: kept?.identity === identity ? kept.page : 0};
    buildLinePager(pager);
    cycle.pagers = [pager];
    return true;
  }

  function buildManifest(motionRows = new Map()) {
    const manifest = cycle.manifest;
    manifest.pages = Math.ceil(cycle.biology.length / manifest.limit);
    // Reserve a full window of rows so a shorter last page keeps its size.
    manifest.list.style.minHeight = "";
    paintManifest(motionRows, true, 0);
    manifest.list.style.minHeight = `${Math.ceil(manifest.list.getBoundingClientRect().height)}px`;
  }

  function reserveSpotlight() {
    // Worlds differ in species count. Reserve the tallest so rotation never
    // resizes the overlay window or shifts the manifest beneath it. A locked
    // (sampling) spotlight does not rotate, so it reserves only itself.
    const slot = cycle.spotlight;
    const rows = cycle.locked ? [spotlightRow()] : cycle.biology;
    let tallest = 0;
    const measured = new Set();
    for (const row of rows) {
      const details = spotlightDetails(row);
      const landable = landableKnown(row) ? (row.landable ? "land" : "no-land") : "";
      const signature = [
        details.length, count(row.bio_count), count(row.complete), count(row.geo_count),
        count(row.mining_count), landable, count(row.dss_probes_used),
        count(row.dss_efficiency_target), row.dss_efficiency_met === true,
        Boolean(row.needs_dss), Boolean(row.first_footfall), Boolean(row.bio_complete),
      ].join("|");
      if (measured.has(signature)) continue;
      measured.add(signature);
      const card = spotlightCard(row, {system: cycle.systemName, kicker: "LATEST SCAN", details});
      slot.replaceChildren(card);
      tallest = Math.max(tallest, card.getBoundingClientRect().height);
    }
    slot.style.minHeight = `${Math.ceil(tallest)}px`;
  }

  // Give up height from the least important region first: catalogue lines
  // (quietest tier first), then a folded catalogue, then manifest rows.
  function fitBudget(budget) {
    const shrinkManifest = (floor) => {
      if (!cycle.manifest || cycle.manifest.limit <= Math.min(floor, cycle.biology.length)) return false;
      cycle.manifest.limit -= 1;
      buildManifest();
      return true;
    };
    for (let guard = 0; guard < 64 && renderedContentHeight() > budget; guard += 1) {
      const pager = SHRINK_ORDER.map((key) => cycle.pagers.find((item) => item.key === key))
        .find((item) => item && item.lines > 1);
      if (pager) {
        pager.lines -= 1;
        buildLinePager(pager);
      } else if (!foldCatalogue() && !shrinkManifest(MANIFEST_MIN_ROWS)
          && !shrinkManifest(MANIFEST_FLOOR_ROWS)) {
        break;
      }
    }
  }

  function renderSystem(model, motion, sample, options = {}) {
    const groups = classifyRows(model);
    const tier = scaleTier();
    const limits = LIMITS[tier];
    const systemName = model.system || "";
    const system = identityKey(systemName);
    const previous = cycle && cycle.system === system ? cycle : null;
    if (!previous && cycleTimer) {
      window.clearTimeout(cycleTimer);
      cycleTimer = 0;
    }
    const keys = groups.biology.map(rowKey);
    const sampleRow = model.sampling ? samplingWorld(groups.biology, model.sampling) : null;
    const changed = changedWorld(groups.biology, motion.rows);
    const now = Date.now();
    let spotKey = previous && keys.includes(previous.spotKey) ? previous.spotKey : null;
    let holdUntil = spotKey ? previous.holdUntil : 0;
    let reason = spotKey ? previous.reason : "";
    let jumped = false;
    if (sampleRow) {
      jumped = spotKey !== rowKey(sampleRow) || !previous?.locked;
      spotKey = rowKey(sampleRow);
      reason = "sampling";
      holdUntil = now + HOLD_MS;
    } else if (changed) {
      spotKey = rowKey(changed);
      reason = "update";
      holdUntil = now + HOLD_MS;
      jumped = true;
    } else if (!spotKey && keys.length) {
      const latest = groups.biology.find((row) => row.recent_scan);
      spotKey = rowKey(latest || groups.biology[0]);
      reason = latest ? "update" : "cycle";
      holdUntil = latest ? now + HOLD_MS : 0;
      jumped = true;
    }
    cycle = {
      system, systemName, biology: groups.biology, keys, spotKey, holdUntil, reason,
      locked: Boolean(sampleRow),
      samplingSpecies: sampleRow ? String(model.sampling.species || "").trim().toLowerCase() : "",
      rotates: spotlightRotates(options, keys.length),
      pagers: [], spotlight: null, manifest: null, catalogue: null,
      periodStart: previous?.periodStart || 0, nextAt: previous?.nextAt || 0,
    };

    if (sample) dom.content.appendChild(sample);
    if (groups.biology.length) {
      cycle.spotlight = node("section", "spotlight-slot");
      cycle.spotlight.setAttribute("aria-label", "Spotlight world");
      dom.content.appendChild(cycle.spotlight);
      reserveSpotlight();
    }
    // A lone biology world is fully described by the spotlight itself.
    if (groups.biology.length > 1) {
      const section = node("section", "manifest");
      section.setAttribute("aria-label", "Biology manifest");
      const {head, counter} = sectionHead("BIOLOGY", "tone-bio");
      const list = node("div", "manifest-rows");
      section.append(head, list);
      dom.content.appendChild(section);
      cycle.manifest = {list, counter, page: -1, pages: 1,
        limit: Math.max(1, limits.manifest),
        min: Math.min(MANIFEST_MIN_ROWS, groups.biology.length)};
      buildManifest(motion.rows);
    }

    const scopeAll = model.scope === "all";
    const specs = [
      ["surface", "SURFACE", groups.surface, "rows", limits.surface],
      ["notable", "NOTABLE", groups.notable, "rows", limits.notable],
      ["landable", "LANDABLE", groups.landable, scopeAll ? "rows" : "chips", scopeAll ? limits.rows : limits.chips],
      ["other", "OTHER", groups.other, scopeAll ? "rows" : "chips", scopeAll ? limits.rows : limits.chips],
    ].filter(([, , rows]) => rows.length);
    if (specs.length) {
      const catalogue = node("section", "catalogue");
      catalogue.setAttribute("aria-label", "System catalogue");
      dom.content.appendChild(catalogue);
      cycle.catalogue = {section: catalogue, folded: false, previous: previous?.pagers || [],
        rows: specs.flatMap(([, , rows]) => rows)};
      for (const [key, label, rows, layout, lines] of specs) {
        const group = node("div", `catalogue-group group-${key} layout-${layout}`);
        group.dataset.group = key;
        const head = node("div", "group-label");
        head.appendChild(node("strong", "", label));
        const counter = node("span", "group-count");
        head.appendChild(counter);
        const items = node("div", "group-items");
        group.append(head, items);
        catalogue.appendChild(group);
        const elements = rows.map((row) => layout === "chips"
          ? bodyChip(row, systemName)
          : bodyRow(row, {system: systemName, kind: key,
            event: motion.rows.get(rowKey(row)) || motion.notable.get(rowKey(row)) || {}}));
        const identity = `${layout}|${rows.map(rowKey).join("|")}`;
        const kept = previous?.pagers.find((pager) => pager.key === key);
        const pager = {key, items, counter, elements, identity, total: rows.length,
          lines: Math.max(1, lines), pages: [[]],
          page: kept?.identity === identity ? kept.page : 0};
        buildLinePager(pager);
        cycle.pagers.push(pager);
      }
    }
    fitBudget(HEIGHT_BUDGET[tier]);

    // Show the spotlit world's manifest page after a journal jump or while it
    // turns; otherwise a self-paging manifest keeps the page it was on.
    let manifestPage = null;
    if (cycle.manifest) {
      const kept = previous?.manifest?.limit === cycle.manifest.limit ? previous.manifest.page : 0;
      manifestPage = spotlightTurns() || jumped ? spotlightPage()
        : Math.min(Math.max(0, kept), cycle.manifest.pages - 1);
    }
    if (!rotating()) schedule(0);
    else if (jumped && spotlightTurns()) schedule(Math.max(CYCLE_MS, holdUntil - now));
    else if (jumped || !cycleTimer) schedule(CYCLE_MS);
    paintSpotlight(motion.rows);
    paintManifest(motion.rows, true, manifestPage);
    cycle.pagers.forEach(paintPager);
  }

  function renderBody(model, motion) {
    stopCycle();
    const rows = Array.isArray(model.rows) ? model.rows : [];
    const body = model.body || {};
    const samplingName = String((model.sampling || {}).species || "").trim().toLowerCase();
    // The genetic-sequence card already owns the species being sampled.
    const bodyDetails = rows.filter((detail) => !samplingName
      || !samplingMatches(detail, samplingName));
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
    dom.content.appendChild(spotlightCard(projected, {
      system: model.system, event: motion.body || {}, focused: true,
      kicker: "SURFACE FOCUS", details: orderedBiologicalDetails(bodyDetails),
    }));
  }

  window.VoidCompassSurveyAtlas = Object.freeze({
    // Advance the single clock now: spotlight, manifest window and any
    // overflowing catalogue group turn together.
    tick,
    getState: () => {
      if (!cycle) {
        return {spotlight: null, spotIndex: 0, bio: 0, manifestPage: 0, manifestPages: 0,
          locked: false, held: false, rotating: false, spotlightTurns: false, groups: {}};
      }
      const row = cycle.biology.length ? spotlightRow() : null;
      return {
        spotlight: row ? designation(row, cycle.systemName) : null,
        spotIndex: row ? cycle.keys.indexOf(rowKey(row)) + 1 : 0,
        bio: cycle.biology.length,
        manifestPage: cycle.manifest ? cycle.manifest.page + 1 : 0,
        manifestPages: cycle.manifest ? cycle.manifest.pages : 0,
        locked: cycle.locked,
        held: Date.now() < cycle.holdUntil,
        rotating: rotating(),
        spotlightTurns: spotlightTurns(),
        groups: Object.fromEntries(cycle.pagers.map((pager) => [pager.key, {
          total: pager.total, page: pager.page + 1, pages: pager.pages.length,
        }])),
      };
    },
  });

  function overview(model, motion = {}) {
    dom.overview.replaceChildren();
    const bodyMode = model.mode === "body";
    const body = model.body || {};
    const rows = Array.isArray(model.rows) ? model.rows : [];
    const sum = (key) => rows.reduce((total, row) => total + count(row[key]), 0);
    const bio = bodyMode ? count(body.bio_count) : sum("bio_count");
    const done = bodyMode ? count(body.organic_complete_count) : sum("complete");
    const geo = sum("geo_count");
    const mining = sum("mining_count");
    // Two independent lines so the long system name only shares its row with
    // the short counter, never with the counter's label.
    const context = node("div", "overview-line overview-context");
    const mode = node("span", "", bodyMode ? "BODY" : "SYSTEM");
    mode.id = "mode-label";
    context.appendChild(mode);
    const fss = model.total_known && count(model.total)
      ? `${count(model.scanned)}/${count(model.total)}` : "INTAKE";
    context.appendChild(node("i", "context-separator", "·"));
    context.appendChild(node("span", "context-fss", `FSS ${fss}`));
    context.appendChild(node("small", "overview-counter-label", "BIO ANALYSED"));
    dom.overview.appendChild(context);
    const heading = node("div", "overview-line overview-heading");
    const system = node("strong", "overview-primary", String(model.system || "UNKNOWN SYSTEM"));
    system.id = "system-name";
    heading.appendChild(system);
    heading.appendChild(node("strong", "overview-meta", `${done}/${bio}`));
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
    const low = bodyMode ? model.min_value : rows.reduce((total, row) => total + safeNumber(row.min_value), 0);
    const high = bodyMode ? model.max_value : rows.reduce((total, row) => total + safeNumber(row.max_value), 0);
    // Body mode's focus card already carries the surface signal badges.
    const items = bodyMode
      ? [["DSS", body.dss_complete ? "MAPPED" : "OPEN"]]
      : [["WORLDS", rows.filter((row) => count(row.bio_count)).length],
        ["GEO", geo], ...(mining ? [["MINING", mining]] : [])];
    for (const [label, value] of items) {
      const item = node("span", "overview-metric");
      item.appendChild(node("small", "", label));
      item.appendChild(node("b", "", value));
      metrics.appendChild(item);
    }
    const estimate = moneyRange(low, high);
    if (estimate) {
      const item = node("span", "overview-metric estimate");
      item.appendChild(node("small", "", "EST"));
      item.appendChild(node("b", "", estimate));
      metrics.appendChild(item);
    }
    dom.overview.appendChild(metrics);
  }

  function footer(model) {
    const left = [];
    let right = "";
    if (model.mode === "body") {
      left.push("SURFACE FIELD NOTES");
      const lifetime = model.dss_stats?.lifetime || {};
      const mapped = count(lifetime.mapped);
      if (mapped) right = `DSS EFF ${count(lifetime.efficient)}/${mapped}`;
    } else {
      const rows = Array.isArray(model.rows) ? model.rows : [];
      left.push(`MAPPED ${rows.filter((row) => !row.needs_dss).length}/${rows.length}`);
      const footfall = rows.filter((row) => row.first_footfall).length;
      if (footfall) left.push(`1ST FOOTFALL ${footfall}`);
      if (model.scope === "all") left.push("ALL BODIES");
      const session = model.dss_stats?.session || {};
      const mapped = count(session.mapped);
      if (mapped) right = `DSS EFF ${count(session.efficient)}/${mapped}`;
    }
    dom.footer.appendChild(node("span", "", left.join(" · ")));
    dom.footer.appendChild(node("span", "credits", right));
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
      stopCycle();
      dom.root.classList.add("empty");
      dom.overview.replaceChildren();
      applyMotionClass({enabled: false});
      return;
    }
    dom.root.classList.remove("empty");
    const sample = model.sampling ? sampleCard(model.sampling, motion.sampling || {}) : null;
    // Header and footer first: the system layout fits its height budget
    // against the complete stack.
    overview(model, motion);
    footer(model);
    if (bodyMode) {
      if (sample) dom.content.appendChild(sample);
      renderBody(model, motion);
    } else {
      renderSystem(model, motion, sample, snapshot.options || {});
    }
    applyMotionClass(motion);
  }

  function contentChildrenHeight(children) {
    const gap = Number.parseFloat(getComputedStyle(dom.content).rowGap) || 0;
    return children.reduce((total, child) => total + child.getBoundingClientRect().height, 0)
      + Math.max(0, children.length - 1) * gap;
  }

  function renderedContentHeight() {
    // Measure the stacked bands, not the viewport: the viewport grows with
    // the host window and would otherwise create a resize feedback loop.
    const style = getComputedStyle(dom.root);
    const frame = ["paddingTop", "paddingBottom", "borderTopWidth", "borderBottomWidth"]
      .reduce((total, key) => total + (Number.parseFloat(style[key]) || 0), 0);
    const gap = Number.parseFloat(style.rowGap) || 0;
    const bands = dom.overview.getBoundingClientRect().height
      + contentChildrenHeight([...dom.content.children])
      + dom.footer.getBoundingClientRect().height;
    return Math.max(150, Math.ceil(frame + bands + gap * 2 + 1));
  }

  VoidCompassOverlay.startPolling({
    token, overlay, render, contentHeight: renderedContentHeight, interval: 300,
  });
})();
