/** Explore & Survey workspace renderer. */

export function renderExploreWorkspace(data, ui) {
  const {
    byId, credits, escapeHtml, mountSystemOrrery, number, numeric,
    stellarCartographyMarkup, workspaceCard, workspaceMetrics, workspaceRows,
    workspaceTable,
  } = ui;
  const root = byId("explore-workspace");
  const returnLaterScroll = root.querySelector(".return-later-entries")?.scrollTop || 0;
  const navRows = (data.nav_route || []).map((row) => `<div class="route-system${row.current ? " current" : row.passed ? " passed" : ""}"><i>${row.passed ? "✓" : row.current ? "◆" : "·"}</i><span><b>${escapeHtml(row.system)}</b><small>${escapeHtml(row.star_class || "STAR CLASS UNKNOWN")} · ${row.distance === null ? "LEG UNKNOWN" : `${numeric(row.distance, 1)} LY`}</small></span></div>`);
  const waypointRows = (data.waypoints || []).map((row) => `<div class="waypoint-row${row.visited ? " visited" : ""}">
    <button data-ws-page="explore" data-ws-op="mark_waypoint" data-index="${row.index}" data-visited="${!row.visited}">${row.visited ? "✓" : "○"}</button>
    <span><b>${String(row.index + 1).padStart(2, "0")} · ${escapeHtml(row.name)}</b><small>${escapeHtml(row.note || (row.coords_known ? "COORDINATES RESOLVED" : "COORDINATES AWAITING VISIT"))}${row.distance === null ? "" : ` · ${numeric(row.distance, 1)} LY`}</small></span>
    <div><button data-ws-page="explore" data-ws-op="copy_waypoint" data-index="${row.index}">COPY</button><button data-ws-page="explore" data-ws-op="edit_waypoint" data-index="${row.index}" data-name="${escapeHtml(row.name)}" data-note="${escapeHtml(row.note || "")}">EDIT</button><button data-ws-page="explore" data-ws-op="move_waypoint" data-index="${row.index}" data-offset="-1">↑</button><button data-ws-page="explore" data-ws-op="move_waypoint" data-index="${row.index}" data-offset="1">↓</button><button class="danger-action" data-ws-page="explore" data-ws-op="delete_waypoint" data-index="${row.index}">×</button></div>
  </div>`);
  const plotted = data.plotter?.result || {};
  const plottedRows = workspaceTable([
    {label: "#", render: (row) => numeric(row.index)},
    {label: "System", render: (row) => `<b>${escapeHtml(row.system)}</b>`},
    {label: "Leg", render: (row) => row.distance_jumped === null || row.distance_jumped === undefined ? "—" : `${numeric(row.distance_jumped, 1)} LY`},
    {label: "Remaining", render: (row) => row.distance_left === null || row.distance_left === undefined ? "—" : `${numeric(row.distance_left, 1)} LY`},
    {label: "Boost", render: (row) => row.neutron ? "NEUTRON" : "STANDARD"},
  ], (plotted.waypoints || []).map((row, index) => ({index: index + 1, ...row})), "Plot a route to inspect its manual waypoints here.");
  const scout = data.scout || {};
  const audit = scout.audit || {};
  const codex = scout.codex || {};
  const modeOptions = Object.entries(scout.modes || {}).map(([key, label]) => `<option value="${escapeHtml(key)}" ${scout.mode === key ? "selected" : ""}>${escapeHtml(label)}</option>`).join("");
  const codexRows = (codex.candidates || []).map((row) => `<div class="scout-codex-row"><i></i><span><b>${escapeHtml(row.name)}</b><small>${escapeHtml([row.category, row.subcategory].filter(Boolean).join(" · ") || "PERSONAL CODEX GAP")}</small></span></div>`);
  const prospectRows = (scout.results || []).map((row, index) => {
    const distance = row.distance === null || row.distance === undefined
      ? (row.route_index ? `ROUTE STOP ${numeric(row.route_index)}${row.jumps ? ` · ${numeric(row.jumps)} JUMPS` : ""}` : "DISTANCE NOT RETURNED")
      : `${numeric(row.distance, 1)} LY FROM REFERENCE`;
    const arrival = row.arrival_ls === null || row.arrival_ls === undefined ? "" : ` · ${numeric(row.arrival_ls, 0)} LS ARRIVAL`;
    const evidence = (row.reasons || []).map((reason) => `<li>${escapeHtml(reason)}</li>`).join("");
    const freshness = `${escapeHtml(row.confidence || "CATALOGUE MATCH")} · ${row.updated_at ? `UPDATED ${escapeHtml(String(row.updated_at).replace("T", " ").slice(0, 16))}` : escapeHtml(row.source || "COMMUNITY CATALOGUE")}`;
    return `<article class="scout-prospect">
      <header><span><small>${escapeHtml(distance)}${arrival}</small><h4>${escapeHtml(row.system || "UNKNOWN SYSTEM")}</h4><b>${escapeHtml(row.body || row.body_type || "SYSTEM PROSPECT")}</b></span><em>${row.mapping_value ? credits(row.mapping_value) : row.signal_count ? `${numeric(row.signal_count)} SIGNAL${number(row.signal_count) === 1 ? "" : "S"}` : "KNOWN TARGET"}</em></header>
      <ul>${evidence || "<li>Known catalogue match</li>"}</ul><footer><small>${freshness}</small><div><button data-ws-page="explore" data-ws-op="scout_copy" data-result-index="${index}">COPY</button><button data-ws-page="explore" data-ws-op="scout_add_waypoint" data-result-index="${index}">ADD TO ROUTE</button><button data-ws-page="explore" data-ws-op="scout_add_objective" data-result-index="${index}">ADD OBJECTIVE</button><button data-page="map">ATLAS</button><button data-ws-page="explore" data-ws-op="scout_open" data-result-index="${index}">OPEN SPANSH</button></div></footer>
    </article>`;
  });
  const scoutMarkup = `<section class="exploration-scout">
    <header class="scout-heading"><div><small>EXPLORATION INTELLIGENCE // JOURNAL + COMMUNITY EVIDENCE</small><h3>EXPLORATION SCOUT</h3><p>Audit the current system, find known nearby prospects, then promote useful targets into your route or active expedition.</p></div><span>${escapeHtml(codex.region || "REGION UNKNOWN")}</span></header>
    <div class="scout-audit-grid">
      <article><small>CURRENT SYSTEM AUDIT</small><b>${audit.complete ? "SURVEY COMPLETE" : audit.scan_known ? `${numeric(audit.pending)} TARGETS PENDING` : "FSS TOTAL AWAITING CONFIRMATION"}</b><span>${audit.scan_known ? `${numeric(audit.scanned)} / ${numeric(audit.total)} bodies resolved · ` : ""}${numeric(audit.known_bodies)} known records · ${numeric(audit.mapped_bodies)} mapped · ${numeric(audit.bio_targets)} bio · ${numeric(audit.geo_targets)} geo${audit.next ? ` · next ${escapeHtml(audit.next)}` : ""}</span><em>${escapeHtml(audit.source || "ELITE JOURNAL")}</em></article>
      <article><small>PERSONAL CODEX HORIZON</small><b>${numeric(codex.personal_gap_count)} REGIONAL GAPS</b><span>${numeric(codex.personal_entries_here)} of ${numeric(codex.personal_entries_total)} personally recorded here · ${numeric(codex.personal_coverage_percent, 1)}% coverage</span><em>${escapeHtml(codex.availability_note || "Personal history only; no spawn is inferred.")}</em></article>
    </div>
    <div class="scout-search-form">
      <label>REFERENCE SYSTEM<input id="scout-reference" value="${escapeHtml(scout.reference || data.current || "")}" placeholder="SYSTEM NAME"></label>
      <label>PROSPECT TYPE<select id="scout-mode">${modeOptions}</select></label>
      <label>SEARCH RADIUS<input id="scout-radius" type="number" min="1" max="10000" value="${number(scout.radius, 500)}"><small>LY / route radius</small></label>
      <label>MIN SIGNALS<input id="scout-signals" type="number" min="1" max="100" value="${number(scout.min_signals, 1)}"><small>Signal searches</small></label>
      <label>MIN VALUE<input id="scout-min-value" type="number" min="1" step="100000" value="${number(scout.min_value, 500000)}"><small>Value search CR</small></label>
      <label>SHIP RANGE<input id="scout-range" type="number" min="1" max="500" step="0.1" value="${number(scout.jump_range, 30)}"><small>Value route</small></label>
      <label>RESULT LIMIT<input id="scout-limit" type="number" min="1" max="100" value="${number(scout.max_results, 20)}"></label>
      <button class="primary" data-ws-page="explore" data-ws-op="scout_search" ${scout.status === "working" ? "disabled" : ""}>${scout.status === "working" ? "SEARCHING…" : "FIND PROSPECTS"}</button>
    </div>
    <p class="workspace-status ${escapeHtml(scout.status || "ready")}">${escapeHtml(scout.detail || "Ready.")}${scout.source ? ` · SOURCE ${escapeHtml(scout.source)}` : ""}${scout.searched_at ? ` · ${escapeHtml(String(scout.searched_at).replace("T", " "))}` : ""}</p>
    ${scout.evidence_note ? `<p class="scout-provenance">${escapeHtml(scout.evidence_note)} · ${numeric(scout.catalogue_count)} catalogue matches reported.</p>` : ""}
    <div class="scout-content"><div class="scout-results">${prospectRows.join("") || `<p class="workspace-empty">No prospect result set. Search from the current system or enter another reference.</p>`}</div><aside><header>PERSONAL CODEX GAPS</header>${workspaceRows(codexRows, "Retained Codex history has no regional comparison yet.")}<p>${escapeHtml(codex.availability_note || "")}</p></aside></div>
    <div class="workspace-actions wrap"><button data-ws-page="explore" data-ws-op="scout_clear" ${(scout.results || []).length ? "" : "disabled"}>CLEAR RESULTS</button></div>
  </section>`;
  const returnLater = data.return_later || {};
  const returnLaterEntries = Array.isArray(returnLater.entries) ? returnLater.entries : [];
  const returnLaterRows = returnLaterEntries.map((row) => {
    const system = escapeHtml(row.system || "UNKNOWN SYSTEM");
    const body = row.body ? escapeHtml(row.body) : "SYSTEM SURVEY";
    const reasons = (Array.isArray(row.reasons) ? row.reasons : []).map((reason) => `<li>${escapeHtml(reason)}</li>`).join("");
    const visited = row.last_visited ? `LAST VISIT ${escapeHtml(String(row.last_visited).replace("T", " ").slice(0, 16))}` : "VISIT TIME UNAVAILABLE";
    const id = escapeHtml(row.id || "");
    return `<article class="return-later-entry${row.current ? " current" : ""}">
      <div class="return-later-entry-main"><small>${row.current ? "CURRENT SYSTEM · " : ""}${visited} · ${escapeHtml(String(row.source || "journal").toUpperCase())}</small><h4>${system}</h4><strong>${body}</strong><ul>${reasons || "<li>Unfinished survey work recorded in the Journal</li>"}</ul></div>
      <div class="return-later-actions"><button type="button" data-ws-page="explore" data-ws-op="return_later_copy" data-return-later-id="${id}">COPY SYSTEM</button><button type="button" data-ws-page="explore" data-ws-op="return_later_waypoint" data-return-later-id="${id}">ADD TO ROUTE</button><button type="button" class="danger-action" data-ws-page="explore" data-ws-op="return_later_dismiss" data-return-later-id="${id}">DISMISS</button></div>
    </article>`;
  }).join("");
  const returnLaterMarkup = `<section class="return-later-board" aria-label="Return Later exploration board">
    <header><div><small>EXPEDITION CONTINUITY // PROFILE-LOCAL</small><h3>RETURN LATER</h3><p>Unfinished survey targets retained when you leave a system. New Journal evidence updates this board when you return.</p></div><b>${numeric(returnLaterEntries.length)} OPEN</b></header>
    <div class="return-later-entries">${returnLaterRows || `<p class="workspace-empty">No unfinished return targets recorded yet. Continue surveying; journal-backed gaps will appear here after departure.</p>`}</div>
  </section>`;
  root.classList.remove("loading-panel");
  root.innerHTML = `${workspaceMetrics([
    {label: "Current system", value: data.current || "—", detail: data.destination ? `NAV TARGET · ${data.destination}` : "NO LOCAL NAV TARGET"},
    {label: "Elite route", value: `${numeric((data.nav_route || []).length)} STOPS`, detail: (data.nav_route || []).length ? "LIVE NAVROUTE.JSON" : "NO ROUTE PLOTTED IN GAME"},
    {label: "Saved waypoints", value: numeric((data.waypoints || []).length), detail: data.next_waypoint ? `NEXT · ${data.next_waypoint}` : "ROUTE COMPLETE / EMPTY"},
    {label: "Survey queue", value: `${numeric(data.cartography?.queue?.pending)} ACTIVE`, detail: data.cartography?.queue?.next ? `NEXT · ${data.cartography.queue.next.body}` : "SYSTEM WORK COMPLETE"},
  ])}${returnLaterMarkup}${scoutMarkup}${stellarCartographyMarkup(data.cartography || {})}<section class="workspace-grid route-workspace-grid">
    ${workspaceCard("ELITE NAV ROUTE", workspaceRows(navRows, "Plot a route in Elite to populate the live NavRoute."), `${(data.nav_route || []).length} STOPS`)}
    ${workspaceCard("PROFILE WAYPOINT ROUTE", `${workspaceRows(waypointRows, "No saved waypoints. Add a destination below or import a plotted route.")}<div class="route-add-form"><input id="waypoint-name" placeholder="SYSTEM NAME"><input id="waypoint-note" placeholder="OPTIONAL NOTE"><button data-ws-page="explore" data-ws-op="add_waypoint">ADD</button></div><div class="workspace-actions wrap"><button data-ws-page="explore" data-ws-op="copy_next">COPY NEXT</button><button data-ws-page="explore" data-ws-op="set_auto_copy" data-enabled="${!data.auto_copy}">AUTO COPY ${data.auto_copy ? "ON" : "OFF"}</button><button class="danger-action" data-ws-page="explore" data-ws-op="clear_waypoints">CLEAR ROUTE</button></div>`, `${(data.waypoints || []).filter((row) => row.visited).length}/${(data.waypoints || []).length} COMPLETE`)}
    ${workspaceCard("SPANSH NEUTRON PLOTTER", `<div class="neutron-form"><label>FROM<input id="neutron-from" value="${escapeHtml(data.plotter?.from || data.current || "")}"></label><label>DESTINATION<input id="neutron-to" value="${escapeHtml(data.plotter?.to || "")}"></label><label>SHIP RANGE<input id="neutron-range" type="number" min="1" step="0.1" value="${number(data.plotter?.range, 30)}"></label><label>EFFICIENCY<input id="neutron-efficiency" type="number" min="1" max="100" value="${number(data.plotter?.efficiency, 60)}"></label><label>BOOST<select id="neutron-multiplier"><option value="4" ${number(data.plotter?.multiplier, 4) === 4 ? "selected" : ""}>NEUTRON 4×</option><option value="6" ${number(data.plotter?.multiplier, 4) === 6 ? "selected" : ""}>OVERCHARGE 6×</option></select></label><button class="primary" data-ws-page="explore" data-ws-op="neutron_plot" ${data.plotter?.status === "working" ? "disabled" : ""}>${data.plotter?.status === "working" ? "PLOTTING…" : "PLOT ROUTE"}</button></div><p class="workspace-status ${escapeHtml(data.plotter?.status || "ready")}">${escapeHtml(data.plotter?.detail || "Ready.")}</p>${plottedRows}<div class="workspace-actions wrap"><button data-ws-page="explore" data-ws-op="neutron_copy" ${plotted.waypoints?.length ? "" : "disabled"}>COPY LIST</button><button data-ws-page="explore" data-ws-op="neutron_import" ${plotted.waypoints?.length ? "" : "disabled"}>IMPORT TO WAYPOINTS</button><button data-ws-page="explore" data-ws-op="neutron_clear" ${plotted.waypoints?.length ? "" : "disabled"}>CLEAR RESULT</button></div>`, plotted.total_jumps ? `${numeric(plotted.total_jumps)} JUMPS` : "MANUAL ROUTE", "neutron-plotter-card")}
  </section>`;
  const returnLaterList = root.querySelector(".return-later-entries");
  if (returnLaterList) returnLaterList.scrollTop = returnLaterScroll;
  mountSystemOrrery(data.cartography?.orrery || {});
}
