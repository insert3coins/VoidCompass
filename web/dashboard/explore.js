/** Explore & Survey: one live system model and three task views.
 *
 *   01 SYSTEM     survey board, next target and the live orrery
 *   02 ROUTE      Elite NavRoute, saved waypoints and Spansh neutron plots
 *   03 PROSPECTS  Return Later, Exploration Scout and personal Codex gaps
 *
 * Each view fills the window and scrolls its own lists, so no control sits
 * below the fold. The survey board is fed by the live snapshot, so every
 * discovered body is listed the moment its record arrives; the workspace
 * survey queue then adds priority order and the commander's PIN/DONE/SKIP
 * choices. Board and orrery share one selection.
 */

const VIEWS = [
  {id: "system", index: "01", label: "System survey", idle: "AWAITING SYSTEM"},
  {id: "route", index: "02", label: "Route & waypoints", idle: "NO ROUTE"},
  {id: "prospects", index: "03", label: "Prospects", idle: "NOTHING PENDING"},
];
const VIEW_IDS = VIEWS.map((view) => view.id);
const FILTERS = [["all", "ALL"], ["todo", "TO DO"], ["bio", "BIOLOGY"], ["done", "DONE"]];
const FILTER_IDS = FILTERS.map(([id]) => id);
// The schematic strip pictures the first bodies only. The board below always
// lists every body, and the strip says how many it has not pictured.
const STRIP_LIMIT = 18;
const STATUS = {
  targeted: ["⌖", "ELITE TARGET"], pinned: ["◆", "PINNED"], pending: ["●", "TO DO"],
  awaiting: ["○", "AWAITING DETAILED SCAN"], listed: ["·", "SURVEY RECORD"],
  skipped: ["–", "SKIPPED"], complete: ["✓", "COMPLETE"], known: ["◌", "KNOWN ARCHIVE"],
};
const RANK = {targeted: 0, pinned: 1, pending: 2, awaiting: 3, listed: 3, skipped: 4, complete: 5, known: 6};

let prefs = {profile: null, view: "system", filter: "all"};
let selection = null;
let boardFingerprint = "";
let boardSystem = "";
let boardObserver = null;
let boardCounts = {all: 0, todo: 0, bio: 0, done: 0};
let liveTargetId = "";
let surveyState = null;
let workspaceData = null;

const lower = (value) => String(value ?? "").trim().toLowerCase();

function designation(name, system) {
  const full = String(name || "UNKNOWN BODY");
  const prefix = `${system} `;
  return system && full.toLowerCase().startsWith(prefix.toLowerCase()) ? full.slice(prefix.length) : full;
}

function loadPrefs(ui) {
  const profile = ui.profileKey();
  if (prefs.profile === profile) return prefs;
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(`voidcompass.explore.view.${profile}`) || "{}") || {};
  } catch (_error) {
    saved = {};
  }
  prefs = {
    profile,
    view: VIEW_IDS.includes(saved.view) ? saved.view : "system",
    filter: FILTER_IDS.includes(saved.filter) ? saved.filter : "all",
  };
  return prefs;
}

function savePrefs() {
  try {
    localStorage.setItem(`voidcompass.explore.view.${prefs.profile}`,
      JSON.stringify({view: prefs.view, filter: prefs.filter}));
  } catch (_error) { /* The remembered view is a convenience only. */ }
}

function pending(title, detail) {
  return `<div class="explore-pending"><i aria-hidden="true"></i><b>${title}</b><span>${detail}</span></div>`;
}

function skeletonMarkup() {
  const tabs = VIEWS.map((view) => `<button type="button" role="tab" id="explore-tab-${view.id}" data-explore-view="${view.id}" aria-controls="explore-view-${view.id}" aria-selected="false" tabindex="-1"><i>${view.index}</i><span>${view.label}<small id="explore-tab-${view.id}-meta">${view.idle}</small></span></button>`).join("");
  const filters = FILTERS.map(([id, label]) => `<button type="button" data-explore-filter="${id}" aria-pressed="false">${label}<b data-filter-count="${id}">0</b></button>`).join("");
  return `<nav class="explore-views" role="tablist" aria-label="Explore and survey views">${tabs}
      <div class="explore-readouts"><span><small>DATA ABOARD</small><b id="intel-value">0 CR</b></span><span><small>REGION</small><b id="explore-region">UNKNOWN</b></span></div>
    </nav>
    <section class="explore-view" role="tabpanel" id="explore-view-system" data-explore-panel="system" aria-labelledby="explore-tab-system">
      <header class="explore-band">
        <div class="explore-star" aria-hidden="true"><i></i></div>
        <div class="explore-identity"><small><b id="workboard-badge">LIVE</b><span id="workboard-class">PRIMARY STAR · CLASS UNKNOWN</span></small><strong id="workboard-system">NO SYSTEM DATA</strong></div>
        <div class="explore-progress">
          <div class="explore-fss"><small>FSS</small><b id="workboard-count">0 / ? BODIES</b><i aria-hidden="true"><em id="explore-fss-fill"></em></i><span id="workboard-percent">—</span></div>
          <div><small>BIOLOGY</small><b id="explore-bio">0 / 0</b></div>
          <div><small>GEOLOGY</small><b id="explore-geo">0</b></div>
        </div>
        <div id="workboard-orbits" class="workboard-orbits" aria-label="System body schematic"></div>
      </header>
      <div class="explore-system-grid">
        <section class="explore-board" aria-labelledby="explore-board-title">
          <header class="explore-board-head"><div><small>SURVEY BOARD</small><h3 id="explore-board-title">Bodies by priority</h3></div><div class="explore-filters" role="group" aria-label="Filter the survey board">${filters}</div></header>
          <div id="body-workboard" class="explore-board-list" role="list" aria-label="Surveyed system bodies" tabindex="-1"></div>
          <p class="explore-board-empty" hidden>No bodies match this filter.</p>
          <footer class="explore-board-foot"><span>Priority, actions and values come from the survey queue; journal completion cannot be reopened.</span><button type="button" id="explore-survey-reset" data-ws-page="explore" data-ws-op="survey_reset" disabled>RESET COMMANDER CHOICES</button></footer>
        </section>
        <section class="explore-instrument" id="explore-orrery" aria-label="Live system orrery">${pending("LINKING LIVE ORRERY", "The system architecture appears once the survey workspace is ready.")}</section>
      </div>
    </section>
    <section class="explore-view" role="tabpanel" id="explore-view-route" data-explore-panel="route" aria-labelledby="explore-tab-route" hidden>
      <header class="explore-expedition" aria-label="Expedition pulse">
        <div><small>EXPEDITION <b id="expedition-badge">NO MISSION</b></small><strong id="expedition-name">NO ACTIVE EXPEDITION</strong><span id="expedition-detail">Create or resume a named expedition in Mission Control.</span></div>
        <div class="explore-expedition-track"><i aria-hidden="true"><em id="expedition-progress"></em></i><span id="expedition-progress-label">0 / 0</span></div>
        <button type="button" data-command="open" data-target="mission">OPEN MISSION CONTROL</button>
      </header>
      <div id="explore-route" class="explore-columns explore-route-grid">${pending("LINKING ROUTE RECORDS", "Elite NavRoute, saved waypoints and neutron plots load with the survey workspace.")}</div>
    </section>
    <section class="explore-view" role="tabpanel" id="explore-view-prospects" data-explore-panel="prospects" aria-labelledby="explore-tab-prospects" hidden>
      <div id="explore-prospects" class="explore-columns explore-prospect-grid">${pending("LINKING PROSPECT RECORDS", "Return Later, Exploration Scout and Codex gaps load with the survey workspace.")}</div>
    </section>`;
}

function bind(root, ui) {
  if (root.dataset.exploreBound) return;
  root.dataset.exploreBound = "true";
  root.addEventListener("click", (event) => {
    const tab = event.target.closest("[data-explore-view]");
    if (tab && root.contains(tab)) {
      setExploreView(tab.dataset.exploreView, ui);
      return;
    }
    const filter = event.target.closest("[data-explore-filter]");
    if (filter) {
      loadPrefs(ui).filter = FILTER_IDS.includes(filter.dataset.exploreFilter) ? filter.dataset.exploreFilter : "all";
      savePrefs();
      applyFilter(root);
      return;
    }
    const select = event.target.closest("[data-explore-select]");
    if (select) {
      const row = select.closest(".body-row");
      selectBody(ui, {bodyId: row?.dataset.bodyId || select.dataset.bodyId || "", name: row?.dataset.bodyName || select.dataset.bodyName || ""});
    }
  });
  root.addEventListener("keydown", (event) => {
    const tab = event.target.closest("[data-explore-view]");
    if (!tab || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const index = VIEW_IDS.indexOf(tab.dataset.exploreView);
    const next = event.key === "Home" ? 0 : event.key === "End" ? VIEW_IDS.length - 1
      : (index + (event.key === "ArrowRight" ? 1 : -1) + VIEW_IDS.length) % VIEW_IDS.length;
    setExploreView(VIEW_IDS[next], ui);
    root.querySelector(`[data-explore-view="${VIEW_IDS[next]}"]`)?.focus();
  });
  // The orrery announces canvas picks so the board follows without a loop.
  root.addEventListener("orrery-select", (event) => {
    selection = {system: surveyState?.system || "", bodyId: String(event.detail?.id ?? ""), name: ""};
    markSelection(root, {scroll: true});
  });
}

/** Build the view skeleton once (and again if an error panel replaced it). */
function ensureSkeleton(ui) {
  const root = ui.byId("explore-workspace");
  if (!root) return {root: null, created: false};
  bind(root, ui);
  if (root.querySelector(":scope > .explore-views")) return {root, created: false};
  root.classList.remove("loading-panel");
  root.innerHTML = skeletonMarkup();
  boardFingerprint = "";
  boardObserver?.disconnect();
  boardObserver = null;
  applyView(root, ui);
  return {root, created: true};
}

function applyView(root, ui) {
  const view = loadPrefs(ui).view;
  for (const tab of root.querySelectorAll("[data-explore-view]")) {
    const active = tab.dataset.exploreView === view;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  }
  for (const panel of root.querySelectorAll("[data-explore-panel]")) {
    panel.hidden = panel.dataset.explorePanel !== view;
  }
  root.dataset.view = view;
  applyFilter(root);
}

export function setExploreView(view, ui) {
  if (!VIEW_IDS.includes(view)) return;
  loadPrefs(ui).view = view;
  savePrefs();
  const {root} = ensureSkeleton(ui);
  if (root) applyView(root, ui);
}

function applyFilter(root) {
  const filter = prefs.filter;
  const list = root.querySelector("#body-workboard");
  if (!list) return;
  list.dataset.filter = filter;
  for (const button of root.querySelectorAll("[data-explore-filter]")) {
    const active = button.dataset.exploreFilter === filter;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  }
  for (const [id] of FILTERS) {
    const node = root.querySelector(`[data-filter-count="${id}"]`);
    if (node) node.textContent = String(boardCounts[id] || 0);
  }
  const empty = root.querySelector(".explore-board-empty");
  if (empty) empty.hidden = !boardCounts.all || Boolean(boardCounts[filter]);
}

function matchesSelection(row) {
  if (!selection || lower(selection.system) !== lower(boardSystem)) return false;
  if (selection.bodyId && selection.bodyId !== "0" && row.dataset.bodyId === selection.bodyId) return true;
  return Boolean(selection.name) && lower(row.dataset.bodyName) === lower(selection.name);
}

function markSelection(root, {focus = false, scroll = false} = {}) {
  const list = root?.querySelector("#body-workboard");
  if (!list) return;
  let selected = null;
  for (const row of list.querySelectorAll(".body-row[data-body-name]")) {
    const active = matchesSelection(row);
    row.classList.toggle("selected", active);
    if (active) {
      row.setAttribute("aria-current", "true");
      selected = row;
    } else {
      row.removeAttribute("aria-current");
    }
  }
  if (focus) (selected || list).focus({preventScroll: true});
  if (selected && (focus || scroll)) {
    const rowBox = selected.getBoundingClientRect();
    const listBox = list.getBoundingClientRect();
    list.scrollTop += rowBox.top - listBox.top - (list.clientHeight - rowBox.height) / 2;
  }
}

function selectBody(ui, target, options = {}) {
  selection = {system: surveyState?.system || "", bodyId: String(target.bodyId || ""), name: String(target.name || "")};
  const {root} = ensureSkeleton(ui);
  markSelection(root, options);
  const orreryBody = orreryBodyFor(selection);
  if (orreryBody) {
    ui.selectOrreryBody(String(orreryBody.id));
  } else {
    const detail = ui.byId("orrery-detail");
    const row = root?.querySelector("#body-workboard .body-row.selected");
    if (detail && row) detail.innerHTML = fallbackDetail(row, ui);
  }
}

/** Entry from the Dashboard's Current System list. */
export function openExploreBody(button, ui) {
  selection = {
    system: button.closest("#survey-body-list")?.dataset.system || "",
    bodyId: button.dataset.bodyId || "",
    name: button.dataset.bodyName || "",
  };
  loadPrefs(ui).view = "system";
  savePrefs();
  ui.showPage("explore");
  const {root} = ensureSkeleton(ui);
  if (!root) return;
  applyView(root, ui);
  selectBody(ui, selection, {focus: true});
}

export function resetExploreProfile() {
  selection = null;
  boardFingerprint = "";
  boardSystem = "";
  liveTargetId = "";
  surveyState = null;
  workspaceData = null;
  prefs = {profile: null, view: "system", filter: "all"};
}

function sameSystem(left, right) {
  return Boolean(left) && lower(left) === lower(right);
}

function currentQueue() {
  const cartography = workspaceData?.cartography || {};
  return sameSystem(cartography.system, surveyState?.system) ? cartography.queue || null : null;
}

function orreryBodyFor(target) {
  const cartography = workspaceData?.cartography || {};
  if (!target || !sameSystem(cartography.system, surveyState?.system || cartography.system)) return null;
  const bodies = (cartography.orrery?.bodies || []).filter((body) => !body.hidden);
  return bodies.find((body) => target.bodyId && target.bodyId !== "0" && String(body.id) === target.bodyId)
    || bodies.find((body) => target.name && lower(body.name) === lower(target.name)) || null;
}

function planetOrb(planetClass, ringCount, ui) {
  const kind = ui.planetKind(planetClass);
  return `<span class="bridge-planet-orb bridge-planet-${kind}${ringCount ? " has-rings" : ""}" aria-hidden="true"><i class="bridge-planet-ring"></i><i class="bridge-planet-sphere"></i><i class="bridge-planet-glint"></i></span>`;
}

function boardModel(ui) {
  const system = surveyState?.system || "";
  const bodies = Array.isArray(surveyState?.survey?.bodies) ? surveyState.survey.bodies : [];
  const queue = currentQueue();
  const byKey = new Map((queue?.rows || []).map((row) => [String(row.key), row]));
  const nextKey = queue?.next ? String(queue.next.key) : "";
  const resources = sameSystem(workspaceData?.cartography?.system, system) ? workspaceData.cartography.resources?.bodies || [] : [];
  const rare = new Map(resources.map((row) => [String(row.body_id ?? lower(row.body)), ui.number(row.rare_count)]));
  const rows = bodies.map((body, order) => {
    const bodyId = body.body_id === null || body.body_id === undefined ? "" : String(body.body_id);
    const queued = byKey.get(`body:${bodyId}`) || byKey.get(`name:${lower(body.name)}`) || null;
    let status = "listed";
    if (queued) status = queued.targeted ? "targeted" : queued.status in RANK ? queued.status : "pending";
    else if (body.archived) status = "known";
    else if (queue && (body.signal_only || !body.planet_class)) status = "awaiting";
    const state = ["targeted", "pinned", "pending", "awaiting"].includes(status) ? "todo"
      : ["complete", "skipped"].includes(status) ? "done" : "known";
    return {
      body, queued, status, state, order, bodyId,
      next: Boolean(queued && nextKey && String(queued.key) === nextKey),
      rare: rare.get(bodyId) || rare.get(lower(body.name)) || 0,
    };
  });
  // Priority first (the survey queue's order), then the journal's body order.
  rows.sort((left, right) => RANK[left.status] - RANK[right.status]
    || ui.number(right.queued?.score) - ui.number(left.queued?.score)
    || ui.number(left.body.body_id, 9999) - ui.number(right.body.body_id, 9999)
    || left.order - right.order);
  return {system, rows, queue};
}

function surveyActions(row, system, escapeHtml) {
  const queued = row.queued;
  if (!queued) return "";
  const key = escapeHtml(queued.key);
  const owner = escapeHtml(system);
  const journalDone = queued.status === "complete" && !queued.manual_complete;
  return `<span class="body-actions"><button type="button" data-ws-page="explore" data-ws-op="survey_pin" data-body-key="${key}" data-system="${owner}">${queued.pinned ? "UNPIN" : "PIN"}</button><button type="button" data-ws-page="explore" data-ws-op="survey_complete" data-body-key="${key}" data-system="${owner}" ${journalDone ? 'disabled title="Completed by Elite journal; only commander choices can be reopened"' : ""}>${queued.status === "complete" ? queued.manual_complete ? "REOPEN" : "JOURNAL ✓" : "DONE"}</button><button type="button" data-ws-page="explore" data-ws-op="survey_skip" data-body-key="${key}" data-system="${owner}">${queued.status === "skipped" ? "RESTORE" : "SKIP"}</button></span>`;
}

function boardRowMarkup(row, system, ui) {
  const {escapeHtml, number, numeric, formatCredits} = ui;
  const {body, queued, status} = row;
  const name = String(body.name || "UNKNOWN BODY");
  const planetClass = String(body.planet_class || body.type || "");
  const bio = Math.max(0, number(body.bio_count));
  const geo = Math.max(0, number(body.geo_count));
  const [glyph, statusLabel] = STATUS[status];
  const tags = [
    row.next ? `<em class="tag next">NEXT</em>` : "",
    status === "targeted" ? `<em class="tag target">ELITE TARGET</em>` : "",
    body.latest_scan ? `<em class="tag latest">LATEST SCAN</em>` : "",
  ].join("");
  const chips = [
    bio ? `<b class="chip bio">BIO ${bio}</b>` : "",
    geo ? `<b class="chip geo">GEO ${geo}</b>` : "",
    body.terraformable ? `<b class="chip tf">TF</b>` : "",
    row.rare ? `<b class="chip rare">RARE ${row.rare}</b>` : "",
    !bio && !geo && body.mapped ? `<b class="chip mapped">MAPPED</b>` : "",
    body.archived ? `<b class="chip known">KNOWN</b>` : "",
  ].join("");
  const detail = queued
    ? [planetClass || queued.class, queued.distance_ls ? `${numeric(queued.distance_ls, 0)} LS` : "", `${queued.action} — ${queued.reason}`]
    : [planetClass || "CLASS UNCONFIRMED", status === "awaiting" ? "Awaiting detailed scan" : status === "known" ? "Known archive record" : body.detail || "Survey record"];
  const value = queued && number(queued.value) ? formatCredits(queued.value) : "";
  const classes = ["body-row", `status-${status}`, body.priority ? "priority" : "", body.mapped ? "mapped" : "", row.next ? "next" : ""].filter(Boolean).join(" ");
  return `<div class="${classes}" role="listitem" tabindex="-1" data-body-id="${escapeHtml(row.bodyId)}" data-body-name="${escapeHtml(name)}" data-state="${row.state}" data-bio="${bio ? 1 : 0}">
    <i class="body-status" title="${statusLabel}">${glyph}</i>
    ${planetOrb(planetClass, number(body.ring_count), ui)}
    <button type="button" class="body-select" data-explore-select aria-label="Show ${escapeHtml(name)} in the orrery · ${statusLabel}">
      <span class="body-line"><strong>${escapeHtml(designation(name, system))}</strong>${tags}<span class="body-chips">${chips}</span>${value ? `<b class="body-value">${escapeHtml(value)}</b>` : ""}</span>
      <small>${escapeHtml(detail.filter(Boolean).join(" · "))}</small>
    </button>
    ${surveyActions(row, system, escapeHtml)}
  </div>`;
}

function renderBoard(root, ui) {
  const list = root.querySelector("#body-workboard");
  if (!list) return;
  const {system, rows, queue} = boardModel(ui);
  if (selection && !sameSystem(selection.system, system)) selection = null;
  const survey = surveyState?.survey || {};
  const fingerprint = JSON.stringify([system, rows.map((row) => [row.body, row.queued, row.status, row.next, row.rare]),
    survey.archive_loading, survey.total_known, survey.scanned]);
  const reset = root.querySelector("#explore-survey-reset");
  if (reset) {
    reset.disabled = !queue;
    reset.dataset.system = system;
  }
  if (fingerprint === boardFingerprint) return;
  boardFingerprint = fingerprint;
  const previousSystem = boardSystem;
  const scrollTop = list.scrollTop;
  const hadFocus = list.contains(document.activeElement);
  boardSystem = system;
  boardCounts = {
    all: rows.length,
    todo: rows.filter((row) => row.state === "todo").length,
    bio: rows.filter((row) => ui.number(row.body.bio_count) > 0).length,
    done: rows.filter((row) => row.state === "done").length,
  };
  boardObserver?.disconnect();
  if (!rows.length) {
    const knownRecord = Boolean(survey.total_known && ui.number(survey.scanned) >= ui.number(survey.total));
    const title = survey.archive_loading ? "RECOVERING KNOWN SYSTEM" : knownRecord ? "KNOWN SYSTEM RECORD" : "AWAITING FSS / DSS DATA";
    const detail = survey.archive_loading
      ? "Requesting historical body architecture while retained scan progress remains authoritative."
      : knownRecord ? "Survey completion is retained; detailed body records were not captured by this profile."
        : "Bodies appear here as the journal reports them, ranked by what to survey next.";
    list.innerHTML = `<div class="body-row empty"><div><strong>${title}</strong><span>${detail}</span></div></div>`;
  } else {
    list.innerHTML = rows.map((row) => boardRowMarkup(row, system, ui)).join("");
  }
  // Only the worlds scrolled into view animate, as on the Dashboard list.
  if ("IntersectionObserver" in window) {
    boardObserver = new IntersectionObserver((entries) => {
      for (const entry of entries) entry.target.classList.toggle("in-view", entry.isIntersecting);
    }, {root: list, rootMargin: "20px"});
    for (const row of list.querySelectorAll(".body-row")) boardObserver.observe(row);
  } else {
    for (const row of list.querySelectorAll(".body-row")) row.classList.add("in-view");
  }
  list.scrollTop = previousSystem === system ? scrollTop : 0;
  applyFilter(root);
  markSelection(root, {focus: hadFocus});
}

function renderBand(root, ui) {
  const {number, text, percentWidth} = ui;
  const survey = surveyState?.survey || {};
  const completion = number(survey.percent);
  const star = String(survey.star_class || "").trim();
  root.querySelector(".explore-star")?.setAttribute("data-star-class", star.charAt(0).toUpperCase());
  text("workboard-badge", survey.complete ? "COMPLETE" : survey.archive_bodies ? "KNOWN" : "LIVE");
  text("workboard-system", surveyState?.system, "NO SYSTEM DATA");
  text("workboard-class", star ? `PRIMARY · ${star}` : "PRIMARY STAR · CLASS UNKNOWN");
  text("workboard-percent", survey.total_known ? `${Math.round(completion)}%` : "—");
  text("workboard-count", `${number(survey.scanned)} / ${survey.total_known ? number(survey.total) : "?"} BODIES`);
  percentWidth("explore-fss-fill", survey.total_known ? completion : 0);
  text("explore-bio", `${number(survey.bio_complete)} / ${number(survey.bio_signals)}`);
  text("explore-geo", String(number(survey.geo_signals)));
}

function renderStrip(root) {
  const orbits = root.querySelector("#workboard-orbits");
  if (!orbits) return;
  const bodies = Array.isArray(surveyState?.survey?.bodies) ? surveyState.survey.bodies : [];
  const markers = bodies.slice(0, STRIP_LIMIT).map((row, index) => {
    const marker = document.createElement("i");
    marker.className = [
      "workboard-body-marker", row.priority ? "priority" : "", row.mapped ? "mapped" : "",
      Number(row.bio_count) ? "bio" : "", Number(row.geo_count) ? "geo" : "", row.landable === true ? "landable" : "",
    ].filter(Boolean).join(" ");
    marker.style.setProperty("--body-index", String(index));
    marker.title = `${row.name || "Unknown body"} · ${row.detail || "Survey record"}`;
    const label = document.createElement("b");
    label.textContent = row.body_id > 0 ? String(row.body_id) : String(index + 1);
    marker.appendChild(label);
    return marker;
  });
  const hidden = Math.max(0, bodies.length - markers.length);
  if (hidden) {
    const more = document.createElement("span");
    more.className = "workboard-more";
    more.textContent = `+${hidden} MORE`;
    markers.push(more);
  }
  orbits.replaceChildren(...markers);
  orbits.setAttribute("aria-label", hidden
    ? `System body schematic: ${markers.length - 1} of ${bodies.length} bodies pictured; ${hidden} more in the survey board`
    : `System body schematic: ${bodies.length} bodies pictured`);
  orbits.classList.toggle("empty", bodies.length === 0);
}

function setMeta(ui, view, value) {
  ui.text(`explore-tab-${view}-meta`, value, VIEWS.find((row) => row.id === view)?.idle || "—");
}

function renderSystemMeta(ui) {
  const survey = surveyState?.survey || {};
  const {number} = ui;
  const fss = `${number(survey.scanned)}/${survey.total_known ? number(survey.total) : "?"} FSS`;
  setMeta(ui, "system", surveyState?.system ? `${fss} · ${boardCounts.todo} TO DO` : "");
}

/** Snapshot-driven half: identity band, schematic strip and survey board. */
export function renderExploreSystem(state, ui) {
  surveyState = {
    system: String(state.flight?.system || ""),
    survey: state.survey || {},
  };
  loadPrefs(ui);
  const {root, created} = ensureSkeleton(ui);
  if (!root) return;
  renderBand(root, ui);
  renderStrip(root);
  renderBoard(root, ui);
  renderSystemMeta(ui);
  if (created && workspaceData) renderWorkspaceParts(root, ui);
}

function fallbackDetail(row, ui) {
  const {escapeHtml} = ui;
  const name = row.dataset.bodyName || "UNKNOWN BODY";
  const note = row.querySelector(".body-select small")?.textContent || "";
  return `<div class="orrery-body-title"><i class="planet"></i><div><small>NOT YET IN THE ORRERY</small><h3>${escapeHtml(name)}</h3><span>${escapeHtml(note)}</span></div><b>—</b></div><div class="orrery-flags"><em>DETAILED SCAN REQUIRED FOR ORBITAL ELEMENTS</em></div>`;
}

function renderInstrument(root, ui) {
  const slot = root.querySelector("#explore-orrery");
  if (!slot) return;
  const {escapeHtml, numeric} = ui;
  const cartography = workspaceData?.cartography || {};
  const orrery = cartography.orrery || {};
  const bodies = (orrery.bodies || []).filter((body) => !body.hidden);
  const target = orrery.target || cartography.target || {};
  const targetId = target.resolved && target.id !== null && target.id !== undefined ? String(target.id) : "";
  // A fresh Elite target lock takes the selection, as it always has.
  if (targetId && targetId !== liveTargetId) {
    selection = {system: cartography.system || surveyState?.system || "", bodyId: targetId, name: ""};
  }
  liveTargetId = targetId;
  // With no explicit pick, open on the recommended next body rather than the
  // arrival star; a picked body the orrery cannot draw gets a text readout.
  const explicit = orreryBodyFor(selection);
  const next = lower(cartography.queue?.next?.body);
  const selected = explicit || bodies.find((body) => next && lower(body.name) === next)
    || bodies.find((body) => body.kind === "planet") || bodies[0] || null;
  ui.setOrrerySelection(selected ? String(selected.id) : "");
  const lock = target.resolved
    ? `<div class="cartography-target-lock"><i>⌖</i><span><small>ELITE NAVIGATION TARGET</small><b>${escapeHtml(target.name || "TARGETED BODY")}</b></span><em>BODY ${escapeHtml(target.body_id ?? "—")} · LOCKED</em></div>`
    : "";
  slot.innerHTML = `<header class="explore-instrument-head"><div><small>LIVE SYSTEM ORRERY</small><b>${numeric(orrery.stars)} STARS · ${numeric(orrery.planets)} PLANETS · ${numeric(orrery.mapped)} MAPPED</b></div><span>${escapeHtml(orrery.mode || "JOURNAL ARCHITECTURE")}</span></header>${lock}${ui.orreryCanvas(orrery)}<div id="orrery-detail" class="orrery-detail">${ui.orreryDetail(selected)}</div>`;
  ui.mountSystemOrrery(orrery);
  markSelection(root);
  if (!explicit && selection) {
    const row = root.querySelector("#body-workboard .body-row.selected");
    const detail = ui.byId("orrery-detail");
    if (row && detail) detail.innerHTML = fallbackDetail(row, ui);
  }
}

function routeMarkup(data, ui) {
  const {escapeHtml, numeric} = ui;
  const route = Array.isArray(data.nav_route) ? data.nav_route : [];
  const waypoints = Array.isArray(data.waypoints) ? data.waypoints : [];
  const plotter = data.plotter || {};
  const plotted = plotter.result || {};
  const plottedRows = Array.isArray(plotted.waypoints) ? plotted.waypoints : [];
  const remaining = waypoints.filter((row) => !row.visited).length;
  const navRows = route.map((row) => `<div class="route-system${row.current ? " current" : row.passed ? " passed" : ""}"><i>${row.passed ? "✓" : row.current ? "◆" : "·"}</i><span><b>${escapeHtml(row.system)}</b><small>${escapeHtml(row.star_class || "STAR CLASS UNKNOWN")} · ${row.distance === null || row.distance === undefined ? "LEG UNKNOWN" : `${numeric(row.distance, 1)} LY`}</small></span></div>`).join("");
  const waypointRows = waypoints.map((row) => `<div class="waypoint-row${row.visited ? " visited" : ""}">
    <button type="button" data-ws-page="explore" data-ws-op="mark_waypoint" data-index="${row.index}" data-visited="${!row.visited}" aria-label="${row.visited ? "Mark not visited" : "Mark visited"}">${row.visited ? "✓" : "○"}</button>
    <span><b>${String(row.index + 1).padStart(2, "0")} · ${escapeHtml(row.name)}</b><small>${escapeHtml(row.note || (row.coords_known ? "COORDINATES RESOLVED" : "COORDINATES AWAITING VISIT"))}${row.distance === null || row.distance === undefined ? "" : ` · ${numeric(row.distance, 1)} LY`}</small></span>
    <div><button type="button" data-ws-page="explore" data-ws-op="copy_waypoint" data-index="${row.index}">COPY</button><button type="button" data-ws-page="explore" data-ws-op="edit_waypoint" data-index="${row.index}" data-name="${escapeHtml(row.name)}" data-note="${escapeHtml(row.note || "")}">EDIT</button><button type="button" data-ws-page="explore" data-ws-op="move_waypoint" data-index="${row.index}" data-offset="-1" aria-label="Move earlier">↑</button><button type="button" data-ws-page="explore" data-ws-op="move_waypoint" data-index="${row.index}" data-offset="1" aria-label="Move later">↓</button><button type="button" class="danger-action" data-ws-page="explore" data-ws-op="delete_waypoint" data-index="${row.index}" aria-label="Delete waypoint">×</button></div>
  </div>`).join("");
  const plotRows = plottedRows.map((row, index) => `<div class="neutron-row"><i>${String(index + 1).padStart(2, "0")}</i><span><b>${escapeHtml(row.system)}</b><small>${row.distance_jumped === null || row.distance_jumped === undefined ? "LEG —" : `${numeric(row.distance_jumped, 1)} LY`} · ${row.distance_left === null || row.distance_left === undefined ? "REMAINING —" : `${numeric(row.distance_left, 1)} LY LEFT`}</small></span><em class="${row.neutron ? "neutron" : ""}">${row.neutron ? "NEUTRON" : "STANDARD"}</em></div>`).join("");
  const multiplier = ui.number(plotter.multiplier, 4);
  const working = plotter.status === "working";
  return `<section class="explore-card nav-route-card" aria-labelledby="explore-nav-title">
      <header><div><small>ELITE NAVROUTE</small><h3 id="explore-nav-title">Live route</h3></div><b>${numeric(route.length)} STOPS</b></header>
      <p class="explore-card-lead">${data.destination ? `NAV TARGET · ${escapeHtml(data.destination)}` : "No local nav target"}</p>
      <div class="explore-card-body" data-scroll-key="nav">${navRows || `<p class="workspace-empty">Plot a route in Elite to populate the live NavRoute.</p>`}</div>
    </section>
    <section class="explore-card waypoint-card" aria-labelledby="explore-waypoint-title">
      <header><div><small>PROFILE ROUTE</small><h3 id="explore-waypoint-title">Saved waypoints</h3></div><b>${numeric(waypoints.length - remaining)}/${numeric(waypoints.length)} COMPLETE</b></header>
      <div class="route-add-form"><input id="waypoint-name" placeholder="SYSTEM NAME" aria-label="Waypoint system name"><input id="waypoint-note" placeholder="OPTIONAL NOTE" aria-label="Waypoint note"><button type="button" class="primary" data-ws-page="explore" data-ws-op="add_waypoint">ADD</button></div>
      <div class="waypoint-next"><span><small>NEXT WAYPOINT</small><b>${escapeHtml(data.next_waypoint || "ROUTE COMPLETE / EMPTY")}</b></span><button type="button" data-ws-page="explore" data-ws-op="copy_next" ${data.next_waypoint ? "" : "disabled"}>COPY NEXT</button><button type="button" data-ws-page="explore" data-ws-op="set_auto_copy" data-enabled="${!data.auto_copy}" aria-pressed="${Boolean(data.auto_copy)}">AUTO COPY ${data.auto_copy ? "ON" : "OFF"}</button></div>
      <div class="explore-card-body" data-scroll-key="waypoints">${waypointRows || `<p class="workspace-empty">No saved waypoints. Add a destination above or import a neutron plot.</p>`}</div>
      <footer><button type="button" class="danger-action" data-ws-page="explore" data-ws-op="clear_waypoints" ${waypoints.length ? "" : "disabled"}>CLEAR ROUTE</button></footer>
    </section>
    <section class="explore-card neutron-card" aria-labelledby="explore-neutron-title">
      <header><div><small>SPANSH</small><h3 id="explore-neutron-title">Neutron plotter</h3></div><b>${plotted.total_jumps ? `${numeric(plotted.total_jumps)} JUMPS` : "MANUAL ROUTE"}</b></header>
      <div class="neutron-form"><label class="wide">FROM<input id="neutron-from" value="${escapeHtml(plotter.from || data.current || "")}"></label><label class="wide">DESTINATION<input id="neutron-to" value="${escapeHtml(plotter.to || "")}"></label><label>SHIP RANGE<input id="neutron-range" type="number" min="1" step="0.1" value="${ui.number(plotter.range, 30)}"></label><label>EFFICIENCY<input id="neutron-efficiency" type="number" min="1" max="100" value="${ui.number(plotter.efficiency, 60)}"></label><label>BOOST<select id="neutron-multiplier"><option value="4" ${multiplier === 4 ? "selected" : ""}>NEUTRON 4×</option><option value="6" ${multiplier === 6 ? "selected" : ""}>OVERCHARGE 6×</option></select></label><button type="button" class="primary" data-ws-page="explore" data-ws-op="neutron_plot" ${working ? "disabled" : ""}>${working ? "PLOTTING…" : "PLOT ROUTE"}</button></div>
      <p class="workspace-status ${escapeHtml(plotter.status || "ready")}">${escapeHtml(plotter.detail || "Ready.")}</p>
      <div class="explore-card-body" data-scroll-key="neutron">${plotRows || `<p class="workspace-empty">Plot a route to inspect its manual waypoints here.</p>`}</div>
      <footer><button type="button" data-ws-page="explore" data-ws-op="neutron_copy" ${plottedRows.length ? "" : "disabled"}>COPY LIST</button><button type="button" data-ws-page="explore" data-ws-op="neutron_import" ${plottedRows.length ? "" : "disabled"}>IMPORT TO WAYPOINTS</button><button type="button" data-ws-page="explore" data-ws-op="neutron_clear" ${plottedRows.length ? "" : "disabled"}>CLEAR</button></footer>
    </section>`;
}

function prospectsMarkup(data, ui) {
  const {credits, escapeHtml, number, numeric} = ui;
  const returnLater = data.return_later || {};
  const entries = Array.isArray(returnLater.entries) ? returnLater.entries : [];
  const returnRows = entries.map((row) => {
    const id = escapeHtml(row.id || "");
    const reasons = (Array.isArray(row.reasons) ? row.reasons : []).map((reason) => `<li>${escapeHtml(reason)}</li>`).join("");
    const visited = row.last_visited ? `LAST VISIT ${escapeHtml(String(row.last_visited).replace("T", " ").slice(0, 16))}` : "VISIT TIME UNAVAILABLE";
    return `<article class="return-later-entry${row.current ? " current" : ""}">
      <div class="return-later-entry-main"><small>${row.current ? "CURRENT SYSTEM · " : ""}${visited} · ${escapeHtml(String(row.source || "journal").toUpperCase())}</small><h4>${escapeHtml(row.system || "UNKNOWN SYSTEM")}</h4><strong>${row.body ? escapeHtml(row.body) : "SYSTEM SURVEY"}</strong><ul>${reasons || "<li>Unfinished survey work recorded in the Journal</li>"}</ul></div>
      <div class="return-later-actions"><button type="button" data-ws-page="explore" data-ws-op="return_later_copy" data-return-later-id="${id}">COPY</button><button type="button" data-ws-page="explore" data-ws-op="return_later_waypoint" data-return-later-id="${id}">ADD TO ROUTE</button><button type="button" class="danger-action" data-ws-page="explore" data-ws-op="return_later_dismiss" data-return-later-id="${id}">DISMISS</button></div>
    </article>`;
  }).join("");
  const scout = data.scout || {};
  const audit = scout.audit || {};
  const codex = scout.codex || {};
  const modes = Object.entries(scout.modes || {}).map(([key, label]) => `<option value="${escapeHtml(key)}" ${scout.mode === key ? "selected" : ""}>${escapeHtml(label)}</option>`).join("");
  const codexRows = (codex.candidates || []).map((row) => `<div class="scout-codex-row"><i></i><span><b>${escapeHtml(row.name)}</b><small>${escapeHtml([row.category, row.subcategory].filter(Boolean).join(" · ") || "PERSONAL CODEX GAP")}</small></span></div>`).join("");
  const results = Array.isArray(scout.results) ? scout.results : [];
  const prospectRows = results.map((row, index) => {
    const distance = row.distance === null || row.distance === undefined
      ? (row.route_index ? `ROUTE STOP ${numeric(row.route_index)}${row.jumps ? ` · ${numeric(row.jumps)} JUMPS` : ""}` : "DISTANCE NOT RETURNED")
      : `${numeric(row.distance, 1)} LY FROM REFERENCE`;
    const arrival = row.arrival_ls === null || row.arrival_ls === undefined ? "" : ` · ${numeric(row.arrival_ls, 0)} LS ARRIVAL`;
    const evidence = (row.reasons || []).map((reason) => `<li>${escapeHtml(reason)}</li>`).join("");
    const freshness = `${escapeHtml(row.confidence || "CATALOGUE MATCH")} · ${row.updated_at ? `UPDATED ${escapeHtml(String(row.updated_at).replace("T", " ").slice(0, 16))}` : escapeHtml(row.source || "COMMUNITY CATALOGUE")}`;
    return `<article class="scout-prospect">
      <header><span><small>${escapeHtml(distance)}${arrival}</small><h4>${escapeHtml(row.system || "UNKNOWN SYSTEM")}</h4><b>${escapeHtml(row.body || row.body_type || "SYSTEM PROSPECT")}</b></span><em>${row.mapping_value ? credits(row.mapping_value) : row.signal_count ? `${numeric(row.signal_count)} SIGNAL${number(row.signal_count) === 1 ? "" : "S"}` : "KNOWN TARGET"}</em></header>
      <ul>${evidence || "<li>Known catalogue match</li>"}</ul><footer><small>${freshness}</small><div><button type="button" data-ws-page="explore" data-ws-op="scout_copy" data-result-index="${index}">COPY</button><button type="button" data-ws-page="explore" data-ws-op="scout_add_waypoint" data-result-index="${index}">ADD TO ROUTE</button><button type="button" data-ws-page="explore" data-ws-op="scout_add_objective" data-result-index="${index}">ADD OBJECTIVE</button><button type="button" data-page="map">ATLAS</button><button type="button" data-ws-page="explore" data-ws-op="scout_open" data-result-index="${index}">OPEN SPANSH</button></div></footer>
    </article>`;
  }).join("");
  const auditHeadline = audit.complete ? "SURVEY COMPLETE" : audit.scan_known ? `${numeric(audit.pending)} TARGETS PENDING` : "FSS TOTAL AWAITING CONFIRMATION";
  const working = scout.status === "working";
  return `<div class="explore-stack">
      <section class="return-later-board explore-card" aria-label="Return Later exploration board">
        <header><div><small>EXPEDITION CONTINUITY · PROFILE-LOCAL</small><h3>Return later</h3></div><b>${numeric(entries.length)} OPEN</b></header>
        <p class="explore-card-lead">Unfinished survey work kept when you leave a system. New journal evidence updates it when you return.</p>
        <div class="return-later-entries" data-scroll-key="return">${returnRows || `<p class="workspace-empty">No unfinished return targets recorded yet. Journal-backed gaps appear here after departure.</p>`}</div>
      </section>
      <section class="explore-card codex-card" aria-labelledby="explore-codex-title">
        <header><div><small>PERSONAL CODEX · ${escapeHtml(codex.region || "REGION UNKNOWN")}</small><h3 id="explore-codex-title">Codex gaps</h3></div><b>${numeric(codex.personal_gap_count)} GAPS</b></header>
        <p class="explore-card-lead">${numeric(codex.personal_entries_here)} of ${numeric(codex.personal_entries_total)} recorded here · ${numeric(codex.personal_coverage_percent, 1)}% coverage</p>
        <div class="explore-card-body" data-scroll-key="codex">${codexRows || `<p class="workspace-empty">Retained Codex history has no regional comparison yet.</p>`}</div>
        <p class="explore-card-note">${escapeHtml(codex.availability_note || "Personal history only; no spawn is inferred.")}</p>
      </section>
    </div>
    <section class="exploration-scout explore-card" aria-labelledby="explore-scout-title">
      <header><div><small>EXPLORATION INTELLIGENCE · JOURNAL + COMMUNITY EVIDENCE</small><h3 id="explore-scout-title">EXPLORATION SCOUT</h3></div><b>${escapeHtml(codex.region || "REGION UNKNOWN")}</b></header>
      <div class="scout-audit"><span><small>CURRENT SYSTEM AUDIT</small><b>${auditHeadline}</b></span><p>${audit.scan_known ? `${numeric(audit.scanned)} / ${numeric(audit.total)} bodies resolved · ` : ""}${numeric(audit.known_bodies)} known · ${numeric(audit.mapped_bodies)} mapped · ${numeric(audit.bio_targets)} bio · ${numeric(audit.geo_targets)} geo${audit.next ? ` · next ${escapeHtml(audit.next)}` : ""} <em>${escapeHtml(audit.source || "ELITE JOURNAL")}</em></p></div>
      <div class="scout-search-form">
        <label class="wide">REFERENCE SYSTEM<input id="scout-reference" value="${escapeHtml(scout.reference || data.current || "")}" placeholder="SYSTEM NAME"></label>
        <label class="wide">PROSPECT TYPE<select id="scout-mode">${modes}</select></label>
        <label>RADIUS<input id="scout-radius" type="number" min="1" max="10000" value="${number(scout.radius, 500)}"><small>LY / route radius</small></label>
        <label>MIN SIGNALS<input id="scout-signals" type="number" min="1" max="100" value="${number(scout.min_signals, 1)}"><small>Signal searches</small></label>
        <label>MIN VALUE<input id="scout-min-value" type="number" min="1" step="100000" value="${number(scout.min_value, 500000)}"><small>Value search CR</small></label>
        <label>SHIP RANGE<input id="scout-range" type="number" min="1" max="500" step="0.1" value="${number(scout.jump_range, 30)}"><small>Value route</small></label>
        <label>LIMIT<input id="scout-limit" type="number" min="1" max="100" value="${number(scout.max_results, 20)}"><small>Results</small></label>
        <button type="button" class="primary" data-ws-page="explore" data-ws-op="scout_search" ${working ? "disabled" : ""}>${working ? "SEARCHING…" : "FIND PROSPECTS"}</button>
      </div>
      <p class="workspace-status ${escapeHtml(scout.status || "ready")}">${escapeHtml(scout.detail || "Ready.")}${scout.source ? ` · SOURCE ${escapeHtml(scout.source)}` : ""}${scout.searched_at ? ` · ${escapeHtml(String(scout.searched_at).replace("T", " "))}` : ""}</p>
      ${scout.evidence_note ? `<p class="scout-provenance">${escapeHtml(scout.evidence_note)} · ${numeric(scout.catalogue_count)} catalogue matches reported.</p>` : ""}
      <div class="scout-results" data-scroll-key="scout">${prospectRows || `<p class="workspace-empty">No prospect result set. Search from the current system or enter another reference.</p>`}</div>
      <footer><button type="button" data-ws-page="explore" data-ws-op="scout_clear" ${results.length ? "" : "disabled"}>CLEAR RESULTS</button></footer>
    </section>`;
}

/** Replace a slot's markup while keeping every list at its scroll position. */
function replaceKeepingScroll(slot, markup) {
  const positions = new Map([...slot.querySelectorAll("[data-scroll-key]")].map((node) => [node.dataset.scrollKey, node.scrollTop]));
  slot.innerHTML = markup;
  for (const node of slot.querySelectorAll("[data-scroll-key]")) {
    if (positions.has(node.dataset.scrollKey)) node.scrollTop = positions.get(node.dataset.scrollKey);
  }
}

function renderWorkspaceParts(root, ui) {
  const data = workspaceData || {};
  const {number} = ui;
  renderInstrument(root, ui);
  renderBoard(root, ui);
  renderSystemMeta(ui);
  const route = root.querySelector("#explore-route");
  if (route) replaceKeepingScroll(route, routeMarkup(data, ui));
  const prospects = root.querySelector("#explore-prospects");
  if (prospects) replaceKeepingScroll(prospects, prospectsMarkup(data, ui));
  const stops = Array.isArray(data.nav_route) ? data.nav_route.length : 0;
  const saved = (data.waypoints || []).filter((row) => !row.visited).length;
  setMeta(ui, "route", stops || saved ? `${stops} STOP${stops === 1 ? "" : "S"} · ${saved} WAYPOINT${saved === 1 ? "" : "S"} LEFT` : "");
  const returns = number(data.return_later?.entries?.length);
  const scouted = number(data.scout?.results?.length);
  setMeta(ui, "prospects", returns || scouted ? `${returns} RETURN LATER · ${scouted} SCOUTED` : "");
}

/** Workspace-driven half: orrery, queue enrichment, route and prospects. */
export function renderExploreWorkspace(data, ui) {
  workspaceData = data || {};
  loadPrefs(ui);
  const {root, created} = ensureSkeleton(ui);
  if (!root) return;
  // A workspace-only render (no snapshot yet) still needs a system context.
  if (!surveyState) surveyState = {system: String(workspaceData.current || ""), survey: {}};
  // A rebuilt skeleton (after an error panel) needs the last snapshot's band.
  if (created) {
    renderBand(root, ui);
    renderStrip(root);
  }
  renderWorkspaceParts(root, ui);
}
