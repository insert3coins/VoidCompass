/** Explore & Survey (5.7.8, rebuilt on ED-Outrider's views):
 *
 *   OVERVIEW   Nearby and the system you're viewing, two tables side by side
 *   SYSTEM     one system's body table full width, or the survey board (QUEUE)
 *   SEARCH     condition search and find by name
 *   FIRSTS     unsold firsts, the firsts watch, Left behind, your records
 *   CHECKLIST  species by region, geology, My Samples, your Codex gaps
 *   SYSTEM MAP the live 3D System Map (system-map.js), 5.6.9
 *   ARCHIVE    the Exploration Archive (5.5.4) and the Journal Log
 *
 * 5.6.1: the page in the newer pages' style. The route (NavRoute, waypoints and
 * the neutron plotter) lives on the Expeditions page now; a slim next-waypoint
 * line stays in the hero. The board ranks like the Survey overlay and the Nav
 * HUD (biology still to do, then geology and mining, then value), with a sort
 * switch, and a picked body opens its details in place.
 *
 * Each view fills the window and scrolls its own lists, so no control sits
 * below the fold. The survey board is fed by the live snapshot, so every
 * discovered body is listed the moment its record arrives; the workspace
 * survey queue then adds priority order and the commander's PIN/DONE/SKIP
 * choices. Board and System Map share one selection.
 */

import {renderOverview, resetOverview} from "./explore-overview.js";
import {renderSystemTable, setSystemMode, systemModes} from "./explore-system.js";
import {renderSearch} from "./explore-search.js";
import {renderFirsts} from "./explore-firsts.js";
import {renderChecklist} from "./explore-checklist.js";
import {renderJournalLog} from "./explore-log.js";

const VIEWS = [
  {id: "overview", label: "OVERVIEW", idle: ""},
  {id: "system", label: "SYSTEM", idle: ""},
  {id: "search", label: "SEARCH", idle: ""},
  {id: "firsts", label: "FIRSTS", idle: ""},
  {id: "checklist", label: "CHECKLIST", idle: ""},
  {id: "map", label: "SYSTEM MAP", idle: ""},
  // 5.5.4: the Exploration Archive, merged in; 5.7.8: with the Journal Log.
  {id: "archive", label: "ARCHIVE", idle: ""},
];
const VIEW_IDS = VIEWS.map((view) => view.id);
const FILTERS = [["all", "ALL"], ["todo", "TO DO"], ["bio", "BIOLOGY"], ["done", "DONE"]];
const FILTER_IDS = FILTERS.map(([id]) => id);
// How the board ranks the bodies still to survey (5.6.1). BIO FIRST is the
// Survey overlay's and the Nav HUD's order.
const SORTS = [["bio", "BIO FIRST"], ["value", "VALUE"], ["distance", "DISTANCE"]];
const SORT_IDS = SORTS.map(([id]) => id);
const STATUS = {
  targeted: ["⌖", "ELITE TARGET"], pinned: ["◆", "PINNED"], pending: ["●", "TO DO"],
  awaiting: ["○", "AWAITING DETAILED SCAN"], listed: ["·", "SURVEY RECORD"],
  skipped: ["–", "SKIPPED"], complete: ["✓", "COMPLETE"], known: ["◌", "KNOWN ARCHIVE"],
};
const RANK = {targeted: 0, pinned: 1, pending: 2, awaiting: 3, listed: 3, skipped: 4, complete: 5, known: 6};

let prefs = {profile: null, view: "overview", filter: "all", sort: "bio"};
// SYSTEM shows the system you're in, or one opened from another tab.
let systemViewing = null;
let archiveMode = "archive";
let directive = null;
let uiRef = null;
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
    // PROSPECTS was split up in 5.7.8, and PLOT ROUTE is the Route page of its own.
    view: VIEW_IDS.includes(saved.view) ? saved.view : "overview",
    filter: FILTER_IDS.includes(saved.filter) ? saved.filter : "all",
    sort: SORT_IDS.includes(saved.sort) ? saved.sort : "bio",
  };
  return prefs;
}

function savePrefs() {
  try {
    localStorage.setItem(`voidcompass.explore.view.${prefs.profile}`,
      JSON.stringify({view: prefs.view, filter: prefs.filter, sort: prefs.sort}));
  } catch (_error) { /* The remembered view is a convenience only. */ }
}

function pending(title, detail) {
  return `<div class="explore-pending"><i aria-hidden="true"></i><b>${title}</b><span>${detail}</span></div>`;
}

function skeletonMarkup() {
  const tabs = VIEWS.map((view) => `<button type="button" role="tab" id="explore-tab-${view.id}" data-explore-view="${view.id}" aria-controls="explore-view-${view.id}" aria-selected="false" tabindex="-1">${view.label}<small id="explore-tab-${view.id}-meta"></small></button>`).join("");
  const filters = FILTERS.map(([id, label]) => `<button type="button" data-explore-filter="${id}" aria-pressed="false">${label}<b data-filter-count="${id}">0</b></button>`).join("");
  const sorts = SORTS.map(([id, label]) => `<button type="button" data-explore-sort="${id}" aria-pressed="false">${label}</button>`).join("");
  // The system's survey heads every tab (5.7.8 redesign): the survey, what it's
  // worth and what's new here, and the Directive under it. Its name, region and
  // next jump live in the deck's top bar, on every page.
  return `<section class="explore-hero" aria-label="This system">
      <div class="explore-hero-figures">
        <div class="xh-group xh-survey"><small class="xh-label">SURVEY</small>
          <div class="explore-fss"><small>FSS</small><b id="workboard-count">0 / ? BODIES</b><i aria-hidden="true"><em id="explore-fss-fill"></em></i><span id="workboard-percent">—</span></div>
          <div><small>BIOLOGY</small><b id="explore-bio">0 / 0</b></div>
          <div><small>GEOLOGY</small><b id="explore-geo">0</b></div>
        </div>
        <div class="xh-group xh-value"><small class="xh-label">WORTH</small>
          <div><small>CARTOGRAPHY</small><b id="intel-carto">0 CR</b></div>
          <div class="readout-bio"><small id="intel-bio-label">EXOBIOLOGY</small><b id="intel-bio">0 CR</b></div>
        </div>
        <div class="xh-group xh-finds"><small class="xh-label">FINDS</small>
          <div title="Bodies here with biology you've never logged in your Codex, or not in this region"><small>CODEX TARGETS</small><b id="explore-codex">0</b></div>
          <div title="Landable bodies nobody has walked on yet"><small>FIRST FOOTFALL</small><b id="explore-footfall">0</b></div>
          <div class="explore-traffic"><small>EDSM TRAFFIC</small><b id="explore-traffic">—</b></div>
        </div>
      </div>
      <p class="explore-directive" id="explore-directive" title="The Mission Directive: what to do next"><small>DIRECTIVE</small><b id="explore-directive-title">—</b><span id="explore-directive-detail"></span></p>
      <a class="explore-expedition" id="explore-expedition" data-page="mission" href="#" hidden><small>EXPEDITION <b id="expedition-badge">ACTIVE</b></small><strong id="expedition-name"></strong><span id="expedition-detail"></span><i aria-hidden="true"><em id="expedition-progress"></em></i><span id="expedition-progress-label">0 / 0</span></a>
    </section>
    <nav class="co-tabs explore-views" role="tablist" aria-label="Explore and survey views">${tabs}</nav>
    <section class="explore-view explore-overview-view" role="tabpanel" id="explore-view-overview" data-explore-panel="overview" aria-labelledby="explore-tab-overview"></section>
    <section class="explore-view explore-system-view" role="tabpanel" id="explore-view-system" data-explore-panel="system" aria-labelledby="explore-tab-system" hidden>
      <div class="explore-system-bar"><span class="xn-modes" role="group" aria-label="Table or survey queue"><button type="button" data-system-mode="table">TABLE</button><button type="button" data-system-mode="queue">QUEUE</button></span>
        <span id="explore-system-viewing"></span><div id="explore-audit-slot" class="explore-audit"></div></div>
      <div class="explore-system-table" data-system-table></div>
      <div class="explore-system-queue" data-system-queue hidden>
      <div class="explore-system-grid">
        <section class="explore-board" aria-labelledby="explore-board-title">
          <header class="explore-board-head"><div><small>SURVEY BOARD</small><h3 id="explore-board-title">Bodies by priority</h3></div>
            <div class="explore-filters" role="group" aria-label="Filter the survey board">${filters}</div>
            <div class="explore-filters explore-sorts" role="group" aria-label="Sort the survey board">${sorts}</div></header>
          <div id="body-workboard" class="explore-board-list" role="list" aria-label="Surveyed system bodies" tabindex="-1"></div>
          <p class="explore-board-empty" hidden>No bodies match this filter.</p>
          <footer class="explore-board-foot"><span>Click a body for its details. Pinned and targeted bodies stay at the top; then the sort you chose.</span><button type="button" id="explore-survey-reset" data-ws-page="explore" data-ws-op="survey_reset" disabled>RESET COMMANDER CHOICES</button></footer>
        </section>
      </div>
      </div>
    </section>
    <section class="explore-view explore-search-view" role="tabpanel" id="explore-view-search" data-explore-panel="search" aria-labelledby="explore-tab-search" hidden>
      <div id="explore-search"></div>
    </section>
    <section class="explore-view explore-firsts-view" role="tabpanel" id="explore-view-firsts" data-explore-panel="firsts" aria-labelledby="explore-tab-firsts" hidden></section>
    <section class="explore-view explore-checklist-view" role="tabpanel" id="explore-view-checklist" data-explore-panel="checklist" aria-labelledby="explore-tab-checklist" hidden></section>
    <section class="explore-view explore-map-view" role="tabpanel" id="explore-view-map" data-explore-panel="map" aria-labelledby="explore-tab-map" hidden>
      <section id="system-map-workspace" aria-label="Live system map"></section>
    </section>
    <section class="explore-view explore-archive" role="tabpanel" id="explore-view-archive" data-explore-panel="archive" aria-labelledby="explore-tab-archive" hidden>
      <div class="explore-archive-bar"><span class="xn-modes" role="group"><button type="button" data-archive-mode="archive">ARCHIVE</button><button type="button" data-archive-mode="log">JOURNAL LOG</button></span></div>
      <div id="analytics-workspace" class="workspace-shell">${pending("OPENING THE ARCHIVE", "Retained flight sessions, scan evidence and region stamps load with the survey workspace.")}</div>
      <div id="explore-journal-log" hidden></div>
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
    const systemMode = event.target.closest("[data-system-mode]");
    if (systemMode) {
      setSystemMode(ui.profileKey(), systemMode.dataset.systemMode);
      renderActive(root, ui);
      return;
    }
    const archive = event.target.closest("[data-archive-mode]");
    if (archive) {
      archiveMode = archive.dataset.archiveMode;
      renderActive(root, ui);
      return;
    }
    if (event.target.closest("[data-system-back]")) {
      systemViewing = null;
      renderActive(root, ui);
      return;
    }
    const sort = event.target.closest("[data-explore-sort]");
    if (sort) {
      loadPrefs(ui).sort = SORT_IDS.includes(sort.dataset.exploreSort) ? sort.dataset.exploreSort : "bio";
      savePrefs();
      boardFingerprint = "";
      renderBoard(root, ui);
      return;
    }
    const filter = event.target.closest("[data-explore-filter]");
    if (filter) {
      loadPrefs(ui).filter = FILTER_IDS.includes(filter.dataset.exploreFilter) ? filter.dataset.exploreFilter : "all";
      savePrefs();
      applyFilter(root);
      return;
    }
    // 5.6.1: a body kept as one of the expedition's places, or added to its route.
    const keep = event.target.closest("[data-explore-keep]");
    if (keep) {
      ui.command?.("workspace", {page: "mission", operation: "add_place", system: keep.dataset.system, body: keep.dataset.body,
        title: keep.dataset.body, kind: "planet", route: keep.dataset.exploreKeep === "route"})
        .then((done) => ui.showToast?.(done ? `${keep.dataset.body}: ${keep.dataset.exploreKeep === "route" ? "added to the expedition's route" : "kept as a place"}`
          : "Start an expedition first, on the Expeditions page"));
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
}

/** Build the view skeleton once (and again if an error panel replaced it). */
function ensureSkeleton(ui) {
  const root = ui.byId("explore-workspace");
  if (!root) return {root: null, created: false};
  bind(root, ui);
  if (root.querySelector(":scope > .explore-views")) {
    if (root.dataset.profile !== prefs.profile) {
      root.dataset.profile = prefs.profile;
      applyView(root, ui);
    }
    return {root, created: false};
  }
  root.classList.remove("loading-panel");
  root.innerHTML = skeletonMarkup();
  root.dataset.profile = prefs.profile;
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
  ui.onViewChange?.(view);
  root.dataset.view = view;
  applyFilter(root);
  renderActive(root, ui);
}

/** The page modules' ui: the deck's, plus moving between tabs. */
function moduleUi(ui) {
  return {
    ...ui,
    setView: (view) => setExploreView(view, ui),
    openSystem: (name, id64 = "") => {
      systemViewing = {name, id64};
      setSystemMode(ui.profileKey(), "table");
      setExploreView("system", ui);
    },
  };
}

// Reopening a tab keeps its history; refresh it at most once a minute.
const slowTicks = new Map();
function slowKey(view) {
  const now = Date.now();
  const key = `${prefs.profile}:${view}`;
  if (now - (slowTicks.get(key) || 0) > 60000) slowTicks.set(key, now);
  return `${key}:${slowTicks.get(key)}`;
}

/** Draw the tab that's showing (the others wait until they're opened). */
function renderActive(root, ui) {
  if (!root || !surveyState) return;
  // Nothing is asked of Spansh until the page is showing.
  if (!root.closest(".page")?.classList.contains("active")) return;
  const view = prefs.view;
  const mui = moduleUi(ui);
  const survey = surveyState.survey || {};
  const rev = `${workspaceData?.survey?.rev ?? 0}:${ui.number(survey.scanned)}:${ui.number(survey.bio_complete)}:${(survey.bodies || []).length}:${surveyState.system}`;
  if (view === "overview") {
    renderOverview(root.querySelector("[data-explore-panel=overview]"), mui, rev, surveyState.system);
  } else if (view === "system") {
    const mode = systemModes(ui.profileKey());
    for (const button of root.querySelectorAll("[data-system-mode]")) button.setAttribute("aria-pressed", String(button.dataset.systemMode === mode));
    const table = root.querySelector("[data-system-table]");
    const queue = root.querySelector("[data-system-queue]");
    if (table) table.hidden = mode !== "table";
    if (queue) queue.hidden = mode !== "queue";
    if (mode === "queue") renderBoard(root, ui);
    const viewing = systemViewing && systemViewing.name && lower(systemViewing.name) !== lower(surveyState.system) ? systemViewing : null;
    const label = root.querySelector("#explore-system-viewing");
    if (label) label.innerHTML = viewing ? `VIEWING <b>${ui.escapeHtml(viewing.name)}</b> <button type="button" data-system-back>BACK TO ${ui.escapeHtml(surveyState.system || "HERE")}</button>` : "";
    if (mode === "table") renderSystemTable(table, mui, rev, viewing?.name || surveyState.system, viewing?.id64 || "");
  } else if (view === "search") {
    renderSearch(root.querySelector("#explore-search"), mui, `${workspaceData?.survey?.rev ?? 0}`);
    } else if (view === "firsts") {
    renderFirsts(root.querySelector("[data-explore-panel=firsts]"), mui, `${slowKey("firsts")}:${workspaceData?.survey?.rev ?? 0}`);
  } else if (view === "checklist") {
    renderChecklist(root.querySelector("[data-explore-panel=checklist]"), mui, `${slowKey("checklist")}:${surveyState.system}`, codexMarkup(workspaceData || {}, ui));
  } else if (view === "archive") {
    for (const button of root.querySelectorAll("[data-archive-mode]")) button.setAttribute("aria-pressed", String(button.dataset.archiveMode === archiveMode));
    const archive = root.querySelector("#analytics-workspace");
    const log = root.querySelector("#explore-journal-log");
    if (archive) archive.hidden = archiveMode === "log";
    if (log) log.hidden = archiveMode !== "log";
    if (archiveMode === "log") renderJournalLog(log, mui);
    else if (workspaceData?.archive) ui.renderArchive?.(workspaceData.archive);
  }
}

function renderDirective(root) {
  const title = root.querySelector("#explore-directive-title");
  const detail = root.querySelector("#explore-directive-detail");
  if (title) title.textContent = directive?.title || "—";
  if (detail) detail.textContent = directive?.detail || "";
}

export function exploreView() {
  return prefs.view || "system";
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
  for (const button of root.querySelectorAll("[data-explore-sort]")) {
    const active = button.dataset.exploreSort === prefs.sort;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  }
}

function matchesSelection(row) {
  if (!selection || lower(selection.system) !== lower(boardSystem)) return false;
  if (selection.bodyId && selection.bodyId !== "0" && row.dataset.bodyId === selection.bodyId) return true;
  return Boolean(selection.name) && lower(row.dataset.bodyName) === lower(selection.name);
}

function markSelection(root, {focus = false, scroll = false} = {}) {
  const list = root?.querySelector("#body-workboard");
  if (!list || prefs.view !== "system" || systemModes(prefs.profile) !== "queue"
      || !root.closest(".page")?.classList.contains("active")) return;
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
  const previousMore = list.querySelector(".body-more");
  if (selected && uiRef) {
    const more = previousMore || document.createElement("div");
    const body = orreryBodyFor({bodyId: selected.dataset.bodyId, name: selected.dataset.bodyName});
    let markup = body ? uiRef.orreryDetail(body) : fallbackDetail(selected, uiRef);
    const name = selected.dataset.bodyName || "";
    if (name && boardSystem) {
      const esc = uiRef.escapeHtml;
      markup += `<div class="body-more-actions"><button type="button" data-system-map-body="${esc(body?.id ?? selected.dataset.bodyId ?? '')}" data-system="${esc(boardSystem)}" data-body="${esc(name)}">SYSTEM MAP ↗</button><button type="button" data-explore-keep="place" data-system="${esc(boardSystem)}" data-body="${esc(name)}">+ EXPEDITION PLACE</button>
        <button type="button" data-explore-keep="route" data-system="${esc(boardSystem)}" data-body="${esc(name)}">+ EXPEDITION ROUTE</button></div>`;
    }
    if (more._markup !== markup) {
      more.className = "body-more";
      more._markup = markup;
      more.innerHTML = markup;
    }
    if (selected.nextElementSibling !== more) selected.after(more);
  } else previousMore?.remove();
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
  systemViewing = null;
  setSystemMode(ui.profileKey(), "queue");
  ui.showPage("explore");
  const {root} = ensureSkeleton(ui);
  if (!root) return;
  applyView(root, ui);
  selectBody(ui, selection, {focus: true});
}

export function resetExploreProfile() {
  resetOverview();
  systemViewing = null;
  selection = null;
  boardFingerprint = "";
  boardSystem = "";
  liveTargetId = "";
  surveyState = null;
  workspaceData = null;
  prefs = {profile: null, view: "overview", filter: "all", sort: "bio"};
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
  // Targeted and pinned stay on top, finished work at the bottom; the bodies
  // still to survey go in the order chosen (5.6.1). BIO FIRST is the Survey
  // overlay's: biology still to do, then geology and mining, then value.
  const group = (status) => (status === "targeted" ? 0 : status === "pinned" ? 1 : ["pending", "awaiting", "listed"].includes(status) ? 2 : RANK[status]);
  const value = (row) => ui.number(row.queued?.value);
  const distance = (row) => (row.queued?.distance_ls === null || row.queued?.distance_ls === undefined ? Infinity : ui.number(row.queued.distance_ls));
  const work = (row) => {
    const body = row.body;
    if (ui.number(body.bio_count) > ui.number(body.bio_done)) return 0;
    return ui.number(body.geo_count) || ui.number(body.mining_count) || body.rhino?.hint ? 1 : 2;
  };
  const order = {
    bio: (left, right) => work(left) - work(right) || value(right) - value(left),
    value: (left, right) => value(right) - value(left),
    distance: (left, right) => distance(left) - distance(right),
  }[prefs.sort] || ((left, right) => value(right) - value(left));
  rows.sort((left, right) => group(left.status) - group(right.status)
    || order(left, right)
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

// What a body's ground tends to hold, for a chip's tooltip.
function rhinoTitle(rhino) {
  const rows = (rhino?.materials || []).map((row) => `${row.material} ${Math.round(Number(row.pct) || 0)}%`);
  return rows.length ? `Rhino ground: ${rows.join(", ")} of mining sites on ground like this` : "Mining sites found";
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
    // The Rhino: mining sites found, and what the ground tends to hold (5.5.17).
    number(body.mining_count) || body.rhino?.hint
      ? `<b class="chip rhino" title="${escapeHtml(rhinoTitle(body.rhino))}">${number(body.mining_count) ? `MINE ${number(body.mining_count)}` : "RHINO"}${body.rhino?.hint ? ` · ${escapeHtml(body.rhino.hint.toUpperCase())}` : ""}</b>` : "",
    row.rare ? `<b class="chip rare">RARE ${row.rare}</b>` : "",
    !bio && !geo && body.mapped ? `<b class="chip mapped">MAPPED</b>` : "",
    body.footfall ? `<b class="chip footfall" title="Nobody has walked on it yet: the first footfall is yours">FOOTFALL</b>` : "",
    bio && number(body.bio_done) >= bio ? `<b class="chip done">BIO DONE</b>` : "",
    body.archived ? `<b class="chip known">KNOWN</b>` : "",
    ...[["guardian", "GUARDIAN"], ["thargoid", "THARGOID"], ["human", "HUMAN"], ["other", "OTHER"]]
      .filter(([kind]) => number((body.sites || {})[kind]))
      .map(([kind, label]) => `<b class="chip site ${kind}">${label} ${number(body.sites[kind])}</b>`),
    CODEX_FLAGS[body.codex] ? `<b class="chip codex ${body.codex}" title="${CODEX_FLAGS[body.codex][2]}">${CODEX_FLAGS[body.codex][0]} ${CODEX_FLAGS[body.codex][1]}</b>` : "",
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
      ${discoveryText(body) ? `<small class="body-discovery${body.was_discovered === false && !body.discovered_by ? " first" : ""}">${escapeHtml(discoveryText(body))}</small>` : ""}
    </button>
    ${surveyActions(row, system, escapeHtml)}
  </div>`;
}

function renderBoard(root, ui) {
  const list = root.querySelector("#body-workboard");
  if (!list || prefs.view !== "system" || systemModes(prefs.profile) !== "queue"
      || !root.closest(".page")?.classList.contains("active")) return;
  const {system, rows, queue} = boardModel(ui);
  if (selection && !sameSystem(selection.system, system)) selection = null;
  const survey = surveyState?.survey || {};
  const fingerprint = JSON.stringify([system, prefs.sort, rows.map((row) => [row.body, row.queued, row.status, row.next, row.rare]),
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
  text("workboard-percent", survey.total_known ? `${Math.round(completion)}%` : "—");
  text("workboard-count", `${number(survey.scanned)} / ${survey.total_known ? number(survey.total) : "?"} BODIES`);
  percentWidth("explore-fss-fill", survey.total_known ? completion : 0);
  text("explore-bio", `${number(survey.bio_complete)} / ${number(survey.bio_signals)}`);
  text("explore-geo", String(number(survey.geo_signals)));
  // EDSM's visitors, as Jump Info shows them, and who discovered the system.
  const traffic = surveyState?.traffic || {};
  const visits = ["day", "week", "total"].map((key) => number(traffic[key]));
  const trafficText = traffic.resolved || visits.some(Boolean)
    ? `24H ${visits[0].toLocaleString()} · WK ${visits[1].toLocaleString()} · EVER ${visits[2].toLocaleString()}`
    : "—";
  text("explore-traffic", trafficText);
  const bodies = Array.isArray(survey.bodies) ? survey.bodies : [];
  text("explore-codex", String(bodies.filter((body) => CODEX_FLAGS[body.codex]).length));
  text("explore-footfall", String(bodies.filter((body) => body.footfall).length));
  const trafficCell = root.querySelector(".explore-traffic");
  if (trafficCell) {
    trafficCell.title = traffic.discovered_by
      ? `System discovered by ${traffic.discovered_by}${traffic.discovered_at ? ` · ${String(traffic.discovered_at).slice(0, 10)}` : ""}`
      : "Commanders EDSM has logged in this system";
  }
}

// Who found a body: EDSM's name for its discoverer, else the game's own
// word (nobody had, so the discovery is yours to sell).
function discoveryText(body) {
  if (body.discovered_by) {
    const date = String(body.discovered_at || "").slice(0, 10);
    return `DISCOVERED BY ${String(body.discovered_by).toUpperCase()}${date ? ` · ${date}` : ""}`;
  }
  if (body.was_discovered === false) return "UNDISCOVERED · FIRST DISCOVERY YOURS";
  if (body.was_discovered === true) return "DISCOVERED · NOT ON EDSM";
  return "";
}

const CODEX_FLAGS = {
  new: ["⚑", "NEW TO CODEX", "Biology here you have never logged in your Codex"],
  region: ["⚐", "NEW IN REGION", "Biology here you have not logged in this galactic region"],
};

function setMeta(ui, view, value) {
  ui.text(`explore-tab-${view}-meta`, value, "");
}

function renderSystemMeta(ui) {
  const survey = surveyState?.survey || {};
  const {number} = ui;
  const todo = currentQueue()?.pending ?? Math.max(0, number(survey.total) - number(survey.scanned));
  setMeta(ui, "system", surveyState?.system ? `${todo} TO DO` : "");
}

/** Snapshot-driven half: identity band, schematic strip and survey board. */
export function renderExploreSystem(state, ui) {
  surveyState = {
    system: String(state.flight?.system || ""),
    survey: state.survey || {},
    traffic: state.traffic || {},
  };
  directive = state.decision || null;
  loadPrefs(ui);
  const {root, created} = ensureSkeleton(ui);
  if (!root) return;
  uiRef = ui;
  renderDirective(root);
  renderBand(root, ui);
  renderBoard(root, ui);
  renderSystemMeta(ui);
  if (created && workspaceData) renderWorkspaceParts(root, ui);
  renderActive(root, ui);
}

function fallbackDetail(row, ui) {
  const {escapeHtml} = ui;
  const name = row.dataset.bodyName || "UNKNOWN BODY";
  const note = row.querySelector(".body-select small")?.textContent || "";
  return `<div class="orrery-body-title"><i class="planet"></i><div><small>NOT YET IN THE ORRERY</small><h3>${escapeHtml(name)}</h3><span>${escapeHtml(note)}</span></div><b>—</b></div><div class="orrery-flags"><em>DETAILED SCAN REQUIRED FOR ORBITAL ELEMENTS</em></div>`;
}

function followTarget(root) {
  const cartography = workspaceData?.cartography || {};
  const target = cartography.orrery?.target || cartography.target || {};
  const targetId = target.resolved && target.id !== null && target.id !== undefined ? String(target.id) : "";
  if (targetId && targetId !== liveTargetId) {
    selection = {system: cartography.system || surveyState?.system || "", bodyId: targetId, name: ""};
  }
  liveTargetId = targetId;
  markSelection(root);
}

/** The waypoint route, NavRoute and the plotted route (Explore & Survey's
 * Route page, 5.7.8): drawn on the Expeditions page since 5.6.1 (expeditions.js). */
export function routeMarkup(data, ui) {
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
  const plotRows = plottedRows.map((row, index) => `<div class="neutron-row"><i>${String(index + 1).padStart(2, "0")}</i><span><b>${escapeHtml(row.system)}</b><small>${row.jumps ? `${numeric(row.jumps)} JUMP${row.jumps === 1 ? "" : "S"}` : ""}${row.refuel ? " · REFUEL" : ""}</small></span><em class="${row.neutron ? "neutron" : ""}">${row.neutron ? "NEUTRON" : "STANDARD"}</em></div>`).join("");
  return `<section class="explore-card nav-route-card" aria-labelledby="explore-nav-title">
      <header><div><small>ELITE NAVROUTE</small><h3 id="explore-nav-title">Live route</h3></div><b>${numeric(route.length)} STOPS</b></header>
      <p class="explore-card-lead">${data.destination ? `NAV TARGET · ${escapeHtml(data.destination)}` : "No local nav target"}</p>
      <div class="explore-card-body" data-scroll-key="nav">${navRows || `<p class="workspace-empty">Plot a route in Elite to populate the live NavRoute.</p>`}</div>
    </section>
    <section class="explore-card waypoint-card" aria-labelledby="explore-waypoint-title">
      <header><div><small>PROFILE ROUTE</small><h3 id="explore-waypoint-title">Saved waypoints</h3></div><b>${numeric(waypoints.length - remaining)}/${numeric(waypoints.length)} COMPLETE</b></header>
      <div class="route-add-form"><input id="waypoint-name" placeholder="SYSTEM NAME" aria-label="Waypoint system name"><input id="waypoint-note" placeholder="OPTIONAL NOTE" aria-label="Waypoint note"><button type="button" class="primary" data-ws-page="explore" data-ws-op="add_waypoint">ADD</button></div>
      <div class="waypoint-next"><span><small>NEXT WAYPOINT</small><b>${escapeHtml(data.next_waypoint || "ROUTE COMPLETE / EMPTY")}</b></span><button type="button" data-ws-page="explore" data-ws-op="copy_next" ${data.next_waypoint ? "" : "disabled"}>COPY NEXT</button><button type="button" data-ws-page="explore" data-ws-op="set_auto_copy" data-enabled="${!data.auto_copy}" aria-pressed="${Boolean(data.auto_copy)}" title="As you arrive in a system, the next waypoint goes on the clipboard">AUTO-COPY ON ARRIVAL ${data.auto_copy ? "ON" : "OFF"}</button></div>
      <div class="explore-card-body" data-scroll-key="waypoints">${waypointRows || `<p class="workspace-empty">No saved waypoints. Add a destination above, or plot a route.</p>`}</div>
      <footer><button type="button" class="danger-action" data-ws-page="explore" data-ws-op="clear_waypoints" ${waypoints.length ? "" : "disabled"}>CLEAR ROUTE</button></footer>
    </section>
    <section class="explore-card neutron-card" aria-labelledby="explore-neutron-title">
      <header><div><small>THE ROUTE PAGE</small><h3 id="explore-neutron-title">Plotted route</h3></div><b>${plotted.total_jumps ? `${numeric(plotted.total_jumps)} JUMPS` : "NONE"}</b></header>
      <p class="workspace-status ${escapeHtml(plotter.status || "ready")}">${escapeHtml(plotted.label ? `${plotted.label}: ${plotted.from} to ${plotted.to}${plotted.followed ? " · your waypoint route" : ""}` : plotter.detail || "Neutron, exact, road to riches and the rest, on one plotter. A plotted route becomes your waypoint route.")}</p>
      <div class="explore-card-body" data-scroll-key="neutron">${plotRows || `<p class="workspace-empty">No route plotted. Plot one on Explore & Survey, or plot a leg above.</p>`}</div>
      <footer><button type="button" class="primary" data-page="route">OPEN ROUTE</button></footer>
    </section>`;
}

function codexMarkup(data, ui) {
  const {escapeHtml, numeric} = ui;
  const codex = data.scout?.codex || {};
  const codexRows = (codex.candidates || []).map((row) => `<div class="scout-codex-row"><i></i><span><b>${escapeHtml(row.name)}</b><small>${escapeHtml([row.category, row.subcategory].filter(Boolean).join(" · ") || "PERSONAL CODEX GAP")}</small></span></div>`).join("");
  return `<section class="explore-card codex-card" aria-labelledby="explore-codex-title">
        <header><div><small>PERSONAL CODEX · ${escapeHtml(codex.region || "REGION UNKNOWN")}</small><h3 id="explore-codex-title">Codex gaps</h3></div><b>${numeric(codex.personal_gap_count)} GAPS</b></header>
        <p class="explore-card-lead">${numeric(codex.personal_entries_here)} of ${numeric(codex.personal_entries_total)} recorded here · ${numeric(codex.personal_coverage_percent, 1)}% coverage</p>
        <div class="explore-card-body" data-scroll-key="codex">${codexRows || `<p class="workspace-empty">Retained Codex history has no regional comparison yet.</p>`}</div>
        <p class="explore-card-note">${escapeHtml(codex.availability_note || "Personal history only; no spawn is inferred.")}</p>
      </section>`;
}

function auditMarkup(data, ui) {
  const {escapeHtml, numeric} = ui;
  const audit = data.scout?.audit || {};
  const headline = audit.complete ? "SURVEY COMPLETE" : audit.scan_known ? `${numeric(audit.pending)} TARGETS PENDING` : "FSS TOTAL AWAITING CONFIRMATION";
  return `<span><small>AUDIT</small><b>${headline}</b></span><p>${audit.scan_known ? `${numeric(audit.scanned)} / ${numeric(audit.total)} bodies resolved · ` : ""}${numeric(audit.known_bodies)} known · ${numeric(audit.mapped_bodies)} mapped · ${numeric(audit.bio_targets)} bio · ${numeric(audit.geo_targets)} geo${audit.next ? ` · next ${escapeHtml(audit.next)}` : ""}</p>`;
}

/** Replace a slot's markup while keeping every list at its scroll position.
 * The same markup again leaves it alone: redrawn every refresh, its buttons
 * blinked and a button under the pointer lost its hover (5.5.5). */
const drawnMarkup = new WeakMap();
function replaceKeepingScroll(slot, markup) {
  if (drawnMarkup.get(slot) === markup && slot.childElementCount) return;
  drawnMarkup.set(slot, markup);
  const positions = new Map([...slot.querySelectorAll("[data-scroll-key]")].map((node) => [node.dataset.scrollKey, node.scrollTop]));
  slot.innerHTML = markup;
  for (const node of slot.querySelectorAll("[data-scroll-key]")) {
    if (positions.has(node.dataset.scrollKey)) node.scrollTop = positions.get(node.dataset.scrollKey);
  }
}

function renderWorkspaceParts(root, ui) {
  const data = workspaceData || {};
  const {number} = ui;
  followTarget(root);
  renderBoard(root, ui);
  renderSystemMeta(ui);
  const audit = root.querySelector("#explore-audit-slot");
  if (audit) replaceKeepingScroll(audit, auditMarkup(data, ui));
  setMeta(ui, "firsts", number(data.return_later?.entries?.length) ? `${number(data.return_later.entries.length)} LEFT` : "");
  renderActive(root, ui);
}

/** Workspace-driven half: orrery, queue enrichment, route and prospects. */
export function renderExploreWorkspace(data, ui) {
  workspaceData = data || {};
  loadPrefs(ui);
  const {root, created} = ensureSkeleton(ui);
  if (!root) return;
  // A workspace-only render (no snapshot yet) still needs a system context.
  if (!surveyState) surveyState = {system: String(workspaceData.current || ""), survey: {}};
  uiRef = ui;
  // A rebuilt skeleton (after an error panel) needs the last snapshot's band.
  if (created) renderBand(root, ui);
  renderWorkspaceParts(root, ui);
}
