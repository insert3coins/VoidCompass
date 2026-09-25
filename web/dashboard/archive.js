// Exploration Archive: profile-local, journal-backed flight and scan evidence.
// The flight payload is the newest retained window (at most 120 sessions), not
// a career total. Keep the wording here honest when visualising aggregates.

const rowsOf = (value) => Array.isArray(value) ? value.filter((row) => row && typeof row === "object") : [];
const positive = (value, number) => Math.max(0, number(value));
const percent = (part, whole) => whole > 0 ? Math.max(0, Math.min(100, part * 100 / whole)) : 0;
let flightQuery = "";
let flightProfileKey = null;

function flightDate(value, escapeHtml) {
  const stamp = String(value || "").replace("T", " ").replace(/Z$/, "").slice(0, 16);
  return escapeHtml(stamp || "DATE UNKNOWN");
}

function archiveMetric(label, value, detail, escapeHtml) {
  return `<div class="archive-metric"><span>${escapeHtml(label)}</span><strong>${value}</strong><small>${detail}</small></div>`;
}

function archiveTrend(rows, key, label, unit, ui) {
  const {escapeHtml, number, numeric} = ui;
  const recent = rows.slice(0, 40).reverse();
  const maximum = Math.max(0, ...recent.map((row) => positive(row[key], number)));
  const bars = maximum > 0
    ? recent.map((row, index) => {
      const amount = positive(row[key], number);
      const height = amount > 0 ? Math.max(2, amount * 100 / maximum) : 0;
      const tooltip = `${String(row.started || "Flight").replace("T", " ").slice(0, 16)} · ${numeric(amount, key === "distance" ? 1 : 0)} ${unit}`;
      return `<i style="--archive-bar:${height.toFixed(2)}%" title="${escapeHtml(tooltip)}" aria-hidden="true"><em>${index + 1}</em></i>`;
    }).join("")
    : `<p class="archive-chart-empty">${recent.length ? "NO RECORDED ACTIVITY IN THIS SERIES" : "FLIGHTS WILL APPEAR AFTER JOURNAL SESSIONS ARE RETAINED"}</p>`;
  return `<article class="archive-chart-card"><header><span>${escapeHtml(label)}</span><b>${recent.length} RECENT FLIGHTS</b></header>
    <div class="archive-chart" role="img" aria-label="${escapeHtml(`${label}: ${recent.length} recent retained flights; exact values are listed in the flight ledger below`)}">${bars}</div>
    <footer><span>${recent.length ? flightDate(recent[0].started, escapeHtml) : "EARLIEST"}</span><span>${recent.length ? flightDate(recent.at(-1).started, escapeHtml) : "LATEST"}</span></footer></article>`;
}

function flightLedger(rows, ui) {
  const {escapeHtml, numeric, number} = ui;
  if (!rows.length) return `<p class="archive-empty">No Captain's Log sessions have been retained yet. A flight record appears after journal activity is saved.</p>`;
  return `<div class="archive-flight-scroll" role="region" aria-label="Recent retained flight ledger" tabindex="0">
    <table class="archive-flight-table"><thead><tr><th scope="col">Flight / route</th><th scope="col">Jumps</th><th scope="col">Distance</th><th scope="col">FSS</th><th scope="col">DSS</th><th scope="col">Bio</th><th scope="col">Codex</th></tr></thead><tbody>
    ${rows.map((row) => `<tr><th scope="row"><time>${flightDate(row.started, escapeHtml)}</time><strong>${escapeHtml(row.start_system || "UNKNOWN ORIGIN")} <span>→</span> ${escapeHtml(row.end_system || row.start_system || "UNKNOWN DESTINATION")}</strong>${row.ended ? "" : `<small>END NOT RECORDED</small>`}</th><td>${numeric(row.jumps)}</td><td>${numeric(row.distance, 1)} <small>LY</small></td><td>${numeric(row.fss)}</td><td>${numeric(row.dss)}</td><td>${numeric(row.bio)}</td><td>${numeric(row.codex)}</td></tr>`).join("")}
    </tbody></table></div>`;
}

function distribution(items, title, note, ui) {
  const {escapeHtml, numeric, number} = ui;
  const rows = rowsOf(items);
  const maximum = Math.max(0, ...rows.map((row) => positive(row.count, number)));
  return `<article class="archive-distribution"><header><h4>${escapeHtml(title)}</h4><small>${escapeHtml(note)}</small></header>
    ${rows.length && maximum > 0 ? `<ol>${rows.map((row) => {
      const count = positive(row.count, number);
      return `<li><span title="${escapeHtml(row.label || "UNKNOWN")}">${escapeHtml(row.label || "UNKNOWN")}</span><i><em style="width:${percent(count, maximum).toFixed(2)}%"></em></i><b>${numeric(count)}</b></li>`;
    }).join("")}</ol>` : `<p class="archive-empty">More retained scan evidence is required.</p>`}</article>`;
}

function speciesIndex(items, ui) {
  const {escapeHtml, numeric, credits} = ui;
  const rows = rowsOf(items);
  if (!rows.length) return `<p class="archive-empty">Analysed organic species will appear here after journal-confirmed fieldwork.</p>`;
  return `<div class="archive-species-scroll" role="region" aria-label="Analysed organic species index" tabindex="0"><table class="archive-species-table">
    <thead><tr><th scope="col">Species / genus</th><th scope="col">Analyses</th><th scope="col">Worlds</th><th scope="col">Systems</th><th scope="col">Listed base value</th></tr></thead><tbody>
    ${rows.map((row) => `<tr><th scope="row"><strong>${escapeHtml(row.name || "UNKNOWN ORGANIC")}</strong><small>${escapeHtml(row.genus || "GENUS UNCONFIRMED")}</small></th><td>${numeric(row.analyses)}</td><td>${numeric(row.worlds)}</td><td>${numeric(row.systems)}</td><td>${credits(row.value)}</td></tr>`).join("")}
    </tbody></table></div>`;
}

function regionCard(row, ui) {
  const {escapeHtml, numeric} = ui;
  const visited = Boolean(row.visited);
  const id = Number.isFinite(Number(row.id)) ? String(row.id).padStart(2, "0") : "--";
  const stamp = visited ? "STAMPED" : "UNSTAMPED";
  return `<article class="archive-region${visited ? " visited" : ""}">
    <header><span class="archive-region-number">${escapeHtml(id)}</span><b>${stamp}</b></header>
    <h4>${escapeHtml(row.name || "UNKNOWN REGION")}</h4>
    ${visited ? `<p>${numeric(row.systems)} systems · ${numeric(row.distance, 1)} LY retained travel</p>
      <dl><div><dt>FSS</dt><dd>${numeric(row.fss)}</dd></div><div><dt>DSS</dt><dd>${numeric(row.dss)}</dd></div><div><dt>BIO</dt><dd>${numeric(row.biology)}</dd></div><div><dt>CODEX</dt><dd>${numeric(row.codex)}</dd></div></dl>
      <footer><small>LAST RECORDED SYSTEM</small><strong title="${escapeHtml(row.last_system || "NOT RECORDED")}">${escapeHtml(row.last_system || "NOT RECORDED")}</strong>${row.last_visit ? `<time>${flightDate(row.last_visit, escapeHtml)}</time>` : ""}</footer>`
      : `<p>No visit retained from this commander's journal coordinates.</p><footer><small>AWAITING JOURNAL EVIDENCE</small></footer>`}
  </article>`;
}

/** Render the Exploration Archive into the existing analytics workspace. */
export function renderExplorationArchive(data, ui) {
  const {byId, escapeHtml, numeric, number} = ui;
  const root = byId("analytics-workspace");
  if (!root) return;
  root.dataset.profileKey = String(ui.profileKey ?? "");
  if (ui.profileKey !== undefined && ui.profileKey !== flightProfileKey) {
    flightQuery = "";
    flightProfileKey = ui.profileKey;
  }
  const rows = rowsOf(data.sessions);
  const science = data.science || {};
  const passport = data.passport || {};
  const regions = rowsOf(passport.rows);
  const visitedRegions = regions.filter((row) => row.visited);
  const unvisitedRegions = regions.filter((row) => !row.visited);
  const totals = rows.reduce((sum, row) => {
    for (const key of ["jumps", "distance", "fss", "dss", "bio", "codex"]) sum[key] += positive(row[key], number);
    return sum;
  }, {jumps: 0, distance: 0, fss: 0, dss: 0, bio: 0, codex: 0});
  const current = data.current || {};
  const activeView = ["trends", "science", "passport"].includes(ui.analyticsView) ? ui.analyticsView : "trends";
  const rawScienceState = data.science_status?.state;
  const scienceState = ["ready", "stale", "loading", "unavailable"].includes(rawScienceState) ? rawScienceState : "ready";
  const scienceAvailable = scienceState === "ready" || scienceState === "stale";
  const scienceStatus = scienceState === "ready" ? "" : `<div class="archive-status ${scienceState}"><strong>${scienceState === "stale" ? "CACHED INDEX" : scienceState === "loading" ? "INDEX LOADING" : "INDEX UNAVAILABLE"}</strong><span>${scienceState === "stale" ? "Showing the last same-profile science and region index while a fresh scan read is pending." : scienceState === "loading" ? "Waiting for the local scan database. Counts are withheld until the first index is ready." : "The local scan database could not be read. Science and region counts are withheld for now."}</span></div>`;
  const deferred = `<div class="archive-deferred">${scienceState === "loading" ? "The local scan index is still loading. Flight records remain available in the meantime." : "Science and region evidence is temporarily unavailable. Flight records remain available in the meantime."}</div>`;
  const focusedSearch = document.activeElement?.id === "archive-flight-search" && root.contains(document.activeElement);
  const searchSelection = focusedSearch ? [document.activeElement.selectionStart, document.activeElement.selectionEnd] : null;
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="archive-shell">
    <header class="archive-masthead"><div class="archive-masthead-copy"><small>FIELD SYSTEMS <i></i> PROFILE-LOCAL RECORDS / 06</small><h2>Exploration <span>Archive</span></h2><p>Trace the flights you have flown, examine the worlds you have surveyed, and follow the regions your journal can place you in.</p></div><div class="archive-masthead-actions"><button type="button" data-page="chronicle">OPEN CAPTAIN'S LOG <span aria-hidden="true">↗</span></button><button type="button" data-page="map">GALACTIC ATLAS <span aria-hidden="true">↗</span></button></div></header>
    <div class="archive-index-strip" aria-label="Archive index"><span><b>${numeric(rows.length)}</b> RECENT FLIGHTS</span><span><b>${scienceAvailable ? numeric(science.bodies) : "—"}</b> SCANNED BODIES</span><span><b>${scienceAvailable ? `${numeric(passport.visited)} / ${numeric(passport.total)}` : "—"}</b> REGIONS STAMPED</span><small>LOCAL JOURNAL / STORED SCAN EVIDENCE</small></div>
    <nav class="archive-tabs" role="tablist" aria-label="Exploration Archive sections"><button type="button" role="tab" id="archive-tab-trends" data-analytics-view="trends" aria-controls="archive-trends" aria-selected="${activeView === "trends"}" class="${activeView === "trends" ? "active" : ""}"><i>01</i><span>Flight record<small>Retained sorties and survey tempo</small></span></button><button type="button" role="tab" id="archive-tab-science" data-analytics-view="science" aria-controls="archive-science" aria-selected="${activeView === "science"}" class="${activeView === "science" ? "active" : ""}"><i>02</i><span>Science index<small>Worlds, atmospheres and ecology</small></span></button><button type="button" role="tab" id="archive-tab-passport" data-analytics-view="passport" aria-controls="archive-passport" aria-selected="${activeView === "passport"}" class="${activeView === "passport" ? "active" : ""}"><i>03</i><span>Region passport<small>Coordinate-backed visit stamps</small></span></button></nav>
    <section class="archive-panel" role="tabpanel" id="archive-trends" data-analytics-panel="trends" aria-labelledby="archive-tab-trends" ${activeView === "trends" ? "" : "hidden"}>
      <header class="archive-section-head"><div><small>01 / FLIGHT RECORD</small><h3>Where the journey went</h3><p>A recent retained sample of up to 120 Captain's Log flights. These figures are not lifetime career totals.</p></div><span>${numeric(rows.length)} FLIGHTS IN VIEW</span></header>
      <div class="archive-flight-layout"><article class="archive-current"><div class="archive-current-top"><span>CURRENT SORTIE</span><i aria-hidden="true"></i></div><strong>${escapeHtml(current.elapsed || "00:00:00")}</strong><small>CURRENT SESSION ELAPSED</small><div class="archive-current-readouts"><span><b>${numeric(current.distance, 1)}</b> LY TRAVELLED</span><span><b>${numeric(current.jumps)}</b> JUMPS</span><span><b>${numeric(current.systems)}</b> SYSTEMS</span></div></article>
        <div class="archive-trend-pair">${archiveTrend(rows, "distance", "Distance by flight", "LY", ui)}${archiveTrend(rows, "fss", "FSS by flight", "FSS surveys", ui)}</div></div>
      <div class="archive-metrics">${archiveMetric("DISTANCE IN SAMPLE", `${numeric(totals.distance, 1)} <em>LY</em>`, `${numeric(totals.jumps)} JUMPS`, escapeHtml)}${archiveMetric("FSS SURVEYS", numeric(totals.fss), "RETAINED FLIGHTS", escapeHtml)}${archiveMetric("DSS MAPS", numeric(totals.dss), "RETAINED FLIGHTS", escapeHtml)}${archiveMetric("BIO ANALYSES", numeric(totals.bio), `${numeric(totals.codex)} CODEX RECORDS`, escapeHtml)}</div>
      <section class="archive-ledger"><header><div><small>FLIGHT MANIFEST</small><h4>Session ledger</h4></div><label class="archive-ledger-search"><span>SEARCH RECENT FLIGHTS</span><input id="archive-flight-search" type="search" placeholder="System, date, record…" value="${escapeHtml(flightQuery)}" ${rows.length ? "" : "disabled"}></label></header><div class="archive-ledger-count" id="archive-ledger-count" role="status" aria-live="polite">${numeric(rows.length)} OF ${numeric(rows.length)} FLIGHTS SHOWN · NEWEST FIRST</div>${flightLedger(rows, ui)}<p id="archive-search-empty" class="archive-empty" hidden>No retained flights match this search.</p></section>
    </section>
    <section class="archive-panel" role="tabpanel" id="archive-science" data-analytics-panel="science" aria-labelledby="archive-tab-science" ${activeView === "science" ? "" : "hidden"}>
      <header class="archive-section-head"><div><small>02 / SCIENCE INDEX</small><h3>What the scans reveal</h3><p>Profile-local correlations from stored body scans. Biological analyses are journal-confirmed; listed species base values are not earnings.</p></div><span>${scienceAvailable ? `${numeric(science.systems)} INDEXED SYSTEMS` : "INDEX PENDING"}</span></header>
      ${scienceStatus}
      ${scienceAvailable ? `
      <div class="archive-metrics">${archiveMetric("SCANNED BODIES", numeric(science.bodies), `${numeric(science.systems)} INDEXED SYSTEMS`, escapeHtml)}${archiveMetric("BIOLOGICAL WORLDS", numeric(science.biological_bodies), `${numeric(science.species_total)} SPECIES`, escapeHtml)}${archiveMetric("ORGANIC ANALYSES", numeric(science.analyses), "JOURNAL-CONFIRMED", escapeHtml)}${archiveMetric("NOTABLE WORLDS", numeric(science.valuable), `${numeric(science.terraformable)} TERRAFORMABLE`, escapeHtml)}</div>
      <div class="archive-science-layout"><section class="archive-species"><header><div><small>FIELD ECOLOGY</small><h4>Organic species index</h4></div><span>${numeric(science.species_total)} SPECIES / UP TO 80 SHOWN</span></header>${speciesIndex(science.species, ui)}</section><div class="archive-science-side">${distribution(science.atmospheres, "Biology by atmosphere", "BIOLOGICAL WORLDS", ui)}${distribution(science.gravity, "Biology by gravity", "BIOLOGICAL WORLDS", ui)}</div></div>
      <div class="archive-world-mix">${distribution(science.body_classes, "World class mix", "SCANNED PLANETARY BODIES", ui)}${distribution(science.star_classes, "Stellar class mix", "SCANNED STARS", ui)}</div>` : deferred}
    </section>
    <section class="archive-panel" role="tabpanel" id="archive-passport" data-analytics-panel="passport" aria-labelledby="archive-tab-passport" ${activeView === "passport" ? "" : "hidden"}>
      <header class="archive-section-head"><div><small>03 / REGION PASSPORT</small><h3>The galaxy, stamped</h3><p>A stamp means this profile has a retained journal-coordinate visit in that region. Unstamped is not proof it has never been visited.</p></div><span>${scienceAvailable ? `${numeric(passport.visited)} / ${numeric(passport.total)} REGIONS` : "INDEX PENDING"}</span></header>
      ${scienceStatus}
      ${scienceAvailable ? `
      <div class="archive-passport-summary"><div class="archive-passport-progress"><span>REGION COVERAGE <b>${numeric(passport.percent, 1)}%</b></span><i><em style="width:${percent(positive(passport.visited, number), positive(passport.total, number)).toFixed(2)}%"></em></i><small>PROFILE-LOCAL JOURNAL EVIDENCE</small></div>${archiveMetric("SYSTEMS INDEXED", numeric(passport.systems), "REGION-ASSIGNED VISITS", escapeHtml)}${archiveMetric("TRAVEL RETAINED", `${numeric(passport.distance, 1)} <em>LY</em>`, "COORDINATED JUMPS", escapeHtml)}${archiveMetric("BIO ANALYSES", numeric(passport.biology), "ASSIGNED BY REGION", escapeHtml)}</div>
      <div class="archive-passport-note"><span>Open the atlas to place these records in galactic context.</span><button type="button" data-page="map">OPEN GALACTIC ATLAS <span aria-hidden="true">↗</span></button></div>
      <div class="archive-regions" role="region" aria-label="Galactic region passport" tabindex="0">${[...visitedRegions, ...unvisitedRegions].map((row) => regionCard(row, ui)).join("") || `<p class="archive-empty">Region coordinates have not been retained yet.</p>`}</div>` : deferred}
    </section>
    <footer class="archive-custody"><i aria-hidden="true"></i><span>ARCHIVE CUSTODY // LOCAL PROFILE</span><small>Only retained journal, scan and coordinate evidence is shown. Missing records remain unknown.</small></footer>
  </div>`;
  const search = root.querySelector("#archive-flight-search");
  const tableRows = [...root.querySelectorAll(".archive-flight-table tbody tr")];
  const count = root.querySelector("#archive-ledger-count");
  const noMatch = root.querySelector("#archive-search-empty");
  const filterFlights = () => {
    const query = flightQuery.trim().toLocaleLowerCase();
    let shown = 0;
    for (const row of tableRows) {
      row.hidden = Boolean(query) && !row.textContent.toLocaleLowerCase().includes(query);
      if (!row.hidden) shown += 1;
    }
    count.textContent = `${numeric(shown)} OF ${numeric(tableRows.length)} FLIGHTS SHOWN · NEWEST FIRST`;
    noMatch.hidden = !query || shown > 0 || !tableRows.length;
  };
  search.addEventListener("input", () => {
    flightQuery = search.value;
    filterFlights();
  });
  filterFlights();
  if (focusedSearch && !search.disabled) {
    search.focus({preventScroll: true});
    if (searchSelection.every(Number.isInteger)) search.setSelectionRange(...searchSelection);
  }
}
