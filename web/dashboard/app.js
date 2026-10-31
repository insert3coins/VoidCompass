import {renderPowerplayWorkspace as renderPowerplayOperationsWorkspace} from "./powerplay.js";
import {
  openExploreBody, renderExploreSystem, renderExploreWorkspace, resetExploreProfile, setExploreView, exploreView,
} from "./explore.js";
import {renderExplorationArchive} from "./archive.js";
import {createMusicDeck} from "./music.js";
import {installSetup, renderSetup} from "./setup.js";
import {applyTextSize} from "./text-size.js";
import {
  handleColonisationChange, handleColonisationClick, handleColonisationSubmit, renderColonisation, resetColonisation,
} from "./colonisation.js";
import {handleBgsChange, handleBgsClick, handleBgsSubmit, renderBgs} from "./bgs.js";
import {handleTradingClick, handleTradingInput, handleTradingSubmit, renderTrading, resetTrading} from "./trading.js";
import {handleMiningClick, handleMiningInput, handleMiningSubmit, renderMining, resetMining} from "./mining.js";
import {handleExpeditionsChange, handleExpeditionsClick, handleExpeditionsInput, handleExpeditionsSubmit, renderExpeditions, resetExpeditions} from "./expeditions.js";
import {handlePlanetaryChange, handlePlanetaryClick, handlePlanetaryInput, handlePlanetarySubmit, renderPlanetary, resetPlanetary, setPlanetaryView} from "./planetary.js";
import {renderWatcher} from "./watcher.js";
import {renderPostcards} from "./postcards.js";
import {renderScreenshots} from "./screenshots.js";
import {renderCapsules} from "./capsules.js";
import {renderTools} from "./tools.js";
import {renderConstellation} from "./constellation.js";
import {renderGames} from "./games.js";
import {renderHatchling, setHatchlingActive} from "./hatchling.js";
import {renderFlightLogs} from "./flightlog.js";
import {renderWrapped} from "./wrapped.js";
import {renderAbout} from "./about.js";
import {installSystemMap,renderSystemMap,setSystemMapActive,resetSystemMap,openSystemMap,systemMapState} from "./system-map.js";

const query = new URLSearchParams(window.location.search);
const token = query.get("token") || "";
let revision = -1;
let model = {};
// The music player runs behind every page once the deck is up (music.js).
let musicDeck = null;
let currentPage = "overview";
let profileKey = "default";
let feedFilter = "ALL";
let flightLogFilter = "ALL";
let flightLogSearch = "";
let flightLogEventsFingerprint = "";
let toastTimer = 0;
let feedFingerprint = "";
let galnetFingerprint = "";
let galnetRenderKey = "";
let galnetTickerIndex = 0;
let galnetTickerId = "";
let galnetSelectedId = "";
let galnetRotationTimer = 0;
let galnetRotationSettingsKey = "";
let atlasRequested = false;
let lastClientError = "";
let bootActive = true;
let bootHideTimer = 0;
let bootReleaseStarted = false;
let bootRecoveryPending = false;
let bootPresentedRequested = false;
let bootHandoffRequested = false;
// Keep the finished deck visible long enough to see the lens and a field note.
const BOOT_READY_HOLD_MS = 5000;
let bootReadyAt = 0;
let bootHoldComplete = false;
let bootHoldTimer = 0;
let lastBootStage = "";
let bootStageTransitionTimer = 0;
let themeFingerprint = "";
let pageRequestId = 0;
let studioSelectedId = "";
let studioMonitorId = "";
let studioDragging = null;
let studioFingerprint = "";
let studioMoveSentAt = 0;
let studioMoveSequence = 0;
let studioOpacitySequence = 0;
let studioOpacityTimer = 0;
let studioOpacityLastSentAt = 0;
let studioOpacityLastSentValue = null;
let studioOpacityPending = null;
let studioOpacityPendingAt = 0;
let studioDragFrame = 0;
let studioPendingPosition = null;
let studioFilter = "all";
let studioSearch = "";
let workspaceFingerprints = {};
let workspaceSyncTimer = 0;
let workspaceSyncTicket = 0;
let groundTargetRefreshTimer = 0;
const achievementUi = {category: "all", status: "all", search: "", sort: "progress", visible: 24};
let hotkeyCaptureAction = "";
let analyticsView = "trends";
let replaySelectedSessionIndex = 0;
let replayTimer = 0;
let deckLayoutDraft = null;
let deckLayoutFingerprint = "";
let atlasLayerRequest = "";
let decisionTagsFingerprint = "";
let preflightFingerprint = "";
let preflightSignalFingerprint = "";
let preflightExpanded = false;
let surveyBodiesFingerprint = "";
let surveyBodyObserver = null;
let routeHorizonFingerprint = "";
let sessionHighlightsFingerprint = "";
let codexCandidatesFingerprint = "";
let pageLayoutEditing = "";
let pageLayoutOriginal = null;
let pageLayoutDrag = null;
let pageLayoutDrop = null;
const pageLayoutDefaults = {};

const PAGE_SUITES = [
  {parent: "explore", label: "EXPLORATION COMMAND", pages: [
    // Expeditions has its own place on the rail since 5.6.1.
    ["explore", "SYSTEM SURVEY"],
    ["recon", "SCOUT & RECON"], ["ledger", "VALUE LEDGER"], ["chronicle", "CAPTAIN'S LOG"],
  ]},
  {parent: "profile", label: "COMMANDER RECORD", pages: [
    ["profile", "COMMANDER"], ["records", "FLIGHT RECORD"],
    ["achievements", "ACHIEVEMENTS"],
  ]},
];
const PAGE_SUITE_BY_PAGE = new Map();
for (const suite of PAGE_SUITES) {
  for (const [page] of suite.pages) PAGE_SUITE_BY_PAGE.set(page, suite);
}
// Ground & Exobio is the Planetary page's ON THE GROUND tab since 5.5.12.
const LEGACY_PAGE_REDIRECTS = {operations: "overview", ground: "planet-materials", "system-map": "explore"};

const HOTKEY_MODIFIER_KEYS = new Set([
  "Alt", "AltGraph", "Control", "Meta", "OS", "Shift",
]);
// The keyboard's media keys: the only keys a shortcut may use on their own.
const HOTKEY_MEDIA_KEYS = {
  MediaPlayPause: "MediaPlayPause", MediaTrackNext: "MediaNext",
  MediaTrackPrevious: "MediaPrevious", MediaStop: "MediaStop",
};
const HOTKEY_CODE_NAMES = {
  Space: "Space", ArrowLeft: "Left", ArrowRight: "Right",
  ArrowUp: "Up", ArrowDown: "Down", PageUp: "PageUp",
  PageDown: "PageDown", Enter: "Enter", NumpadEnter: "Enter",
  Delete: "Delete", Insert: "Insert", Home: "Home", End: "End",
  Backspace: "Backspace", Tab: "Tab", Escape: "Escape",
};

const STRUCTURAL_BUTTON_SELECTOR = [
  ".nav-item", "[data-feed-filter]", ".overlay-quick button", "#overlay-all-toggle", "#overlay-quick-more", ".studio-overlay-card", ".studio-monitor", "[data-setup-go]", ".studio-text-link",
  ".studio-index-select", ".mission-row", ".workspace-tabs button", ".watcher-chapter", ".album-grid button", ".sky-gallery button", ".flightlog-nights button",
  ".suite-tabs button", "[data-analytics-view]",
  ".galnet-headline-row", "#status-galnet",
  ".survey-body-row", ".explore-views button", "[data-explore-filter]", ".body-select",
  ".settings-tab", ".theme-option", ".settings-group-link", ".settings-clear-search", ".settings-studio-link",
  ".music-button", ".music-mode", ".music-playlist", ".music-smart", ".music-list-play", ".music-track-head button", ".music-upnext li button", ".music-viz-menu button",
  "[data-follow-fold]",
  ".pp-tabs button", ".pp-task-main", ".pp-power", "[data-pp-filter]",
  ".co-tabs button", ".co-actions button", ".pl-mini", ".pl-chip",
  ".bgs-star", ".bgs-link", ".bgs-row-main", ".bgs-card", ".bgs-ranges button",
  ".tr-ranges button", ".tr-station-row", ".tools-filter button", ".tools-segments button",
  ".pc-tabs button", ".pc-filter button", ".pc-look", ".pc-grid button", ".pc-step",
  ".sky-views button", ".sky-stars button", ".sky-saved ol button",
  ".wrapped-years button", ".wrapped-index button", ".wrapped-start", ".game-card",
  ".pe button", ".pc-show button", ".pc-hero-card", ".pc-timeline li button",
].join(",");

function decorateCockpitButtons(root = document) {
  const buttons = [];
  if (root instanceof HTMLButtonElement) buttons.push(root);
  if (root?.querySelectorAll) buttons.push(...root.querySelectorAll("button"));
  let fresh = false;
  for (const button of buttons) {
    if (button.matches(STRUCTURAL_BUTTON_SELECTOR)) continue;
    // Note: a panel redrawn and then measured (its scroll kept) lays its new
    // buttons out before this runs, so they faded from the plain look into
    // this one on every redraw: the "blinking" (5.5.5). New ones skip it.
    if (!button.classList.contains("cockpit-button")) {
      button.classList.add("cockpit-fresh");
      fresh = true;
    }
    button.classList.add("cockpit-button");
    button.classList.toggle("cockpit-primary", button.matches(
      ".primary, .commission-action, #save-deck-layout, [data-page-layout-save]",
    ));
    button.classList.toggle("cockpit-danger", button.matches(
      ".danger-action, .row-delete, #studio-delete-preset, #annotation-delete",
    ));
    button.classList.toggle("cockpit-ghost", button.matches(".ghost, .quiet-action"));
  }
  if (fresh) settleFreshButtons();
}

// Two frames on, they may animate as usual (hover and the like); a timer too,
// as a minimised window runs no frames.
let freshButtonsPending = false;
function settleFreshButtons() {
  if (freshButtonsPending) return;
  freshButtonsPending = true;
  const settle = () => {
    if (!freshButtonsPending) return;
    freshButtonsPending = false;
    document.querySelectorAll("button.cockpit-fresh").forEach((button) => button.classList.remove("cockpit-fresh"));
  };
  requestAnimationFrame(() => requestAnimationFrame(settle));
  setTimeout(settle, 250);
}

const cockpitButtonObserver = new MutationObserver((records) => {
  for (const record of records) {
    for (const node of record.addedNodes) {
      if (node.nodeType === Node.ELEMENT_NODE) decorateCockpitButtons(node);
    }
  }
});

function hotkeyFinalKey(event) {
  const code = String(event.code || "");
  if (/^Key[A-Z]$/.test(code)) return code.slice(3);
  if (/^Digit[0-9]$/.test(code)) return code.slice(5);
  if (/^F(?:[1-9]|1[0-9]|2[0-4])$/.test(code)) return code;
  if (HOTKEY_CODE_NAMES[code]) return HOTKEY_CODE_NAMES[code];
  const names = {
    " ": "Space", ArrowLeft: "Left", ArrowRight: "Right",
    ArrowUp: "Up", ArrowDown: "Down", PageUp: "PageUp",
    PageDown: "PageDown", Escape: "Escape", Enter: "Enter",
    Delete: "Delete", Insert: "Insert", Home: "Home", End: "End",
    Backspace: "Backspace", Tab: "Tab",
  };
  const key = names[event.key] || String(event.key || "");
  if (/^[A-Za-z0-9]$/.test(key)) return key.toUpperCase();
  if (/^F(?:[1-9]|1[0-9]|2[0-4])$/.test(key)) return key.toUpperCase();
  return "";
}

async function finishHotkeyCapture(message) {
  hotkeyCaptureAction = "";
  document.querySelectorAll(".hotkey-row.recording").forEach((row) => row.classList.remove("recording"));
  text("hotkey-status", message);
  await command("workspace", {page: "settings", operation: "capture_end"});
}

const byId = (id) => document.getElementById(id);
const text = (id, value, fallback = "—") => {
  const node = byId(id);
  if (node) node.textContent = value === null || value === undefined || value === "" ? fallback : String(value);
};
const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const clamp = (value, low = 0, high = 100) => Math.max(low, Math.min(high, number(value)));
const percentWidth = (id, value) => {
  const node = byId(id);
  if (node) node.style.width = `${clamp(value)}%`;
};
const apiUrl = (path) => `${path}${path.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`;
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[char]));
const credits = (value) => Number.isFinite(Number(value)) ? `${Math.round(Number(value)).toLocaleString()} CR` : "—";
const numeric = (value, digits = 0) => Number.isFinite(Number(value)) ? Number(value).toLocaleString(undefined, {minimumFractionDigits: digits, maximumFractionDigits: digits}) : "—";
// What the page modules draw and talk with.
// A rounded −0 (an empty hold, a zero resistance) reads as 0.
const WORKSHOP_UI = {
  byId, escapeHtml, credits, showToast, command, apiUrl: (path) => apiUrl(path),
  numeric: (value, digits = 0) => numeric(value, digits).replace(/^-(?=0(?:[.,]0+)?$)/, ""),
  workspaceCard: (...args) => workspaceCard(...args), workspaceTable: (...args) => workspaceTable(...args),
};
const duration = (seconds) => {
  const total = Math.max(0, Math.round(number(seconds)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor(total % 3600 / 60);
  const secs = total % 60;
  return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}` : `${minutes}:${String(secs).padStart(2, "0")}`;
};

async function getJson(path) {
  const response = await fetch(apiUrl(path), {cache: "no-store"});
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function command(action, payload = {}) {
  try {
    const response = await fetch(apiUrl("/api/command"), {
      method: "POST",
      cache: "no-store",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action, ...payload}),
    });
    // Read to the end: an unread reply holds native buffers until GC.
    await response.arrayBuffer().catch(() => null);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return true;
  } catch (error) {
    showToast(`Command unavailable: ${error.message}`);
    return false;
  }
}

function postBootMilestone(action) {
  fetch(apiUrl("/api/command"), {
    method: "POST",
    cache: "no-store",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({action}),
  }).then(async (response) => {
    await response.arrayBuffer().catch(() => null);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
  }).catch(() => window.setTimeout(() => postBootMilestone(action), 1000));
}

// A minimized WebView2 stops requestAnimationFrame outright (timers still run,
// throttled to about once a second). Waiting on frames alone held the whole
// Python startup, overlays included, until the window was restored. A hidden
// window has no frame to present, so the timer releases the milestone instead.
const BOOT_PAINT_FALLBACK_MS = 800;

function afterBootPaint(callback) {
  let settled = false;
  const settle = () => {
    if (settled) return;
    settled = true;
    window.clearTimeout(fallback);
    window.setTimeout(callback, 0);
  };
  const fallback = window.setTimeout(settle, BOOT_PAINT_FALLBACK_MS);
  requestAnimationFrame(() => requestAnimationFrame(settle));
}

function acknowledgeBootPresented() {
  if (bootPresentedRequested) return;
  bootPresentedRequested = true;
  afterBootPaint(() => {
    if (!byId("boot").hidden) postBootMilestone("boot_presented");
  });
}

function acknowledgeBootHandoff() {
  if (bootHandoffRequested) return;
  bootHandoffRequested = true;
  afterBootPaint(() => {
    if (byId("boot").hidden && document.body.classList.contains("ready")) {
      postBootMilestone("boot_handoff_complete");
    }
  });
}

function reportClientError(error, source = "runtime") {
  const message = String(error?.stack || error?.message || error || "unknown dashboard error").slice(0, 2000);
  const fingerprint = `${source}:${message}`;
  if (fingerprint === lastClientError) return;
  lastClientError = fingerprint;
  command("client_error", {source, message});
}

function showToast(message) {
  const toast = byId("toast");
  toast.textContent = String(message || "");
  toast.classList.add("show");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("show"), 2800);
}

const PAGE_LAYOUT_CONTAINER_SELECTOR = [
  "#overview-modules", ".record-metrics", ".records-grid",
  ".tool-grid", ".about-grid",
  ".workspace-shell .workspace-metrics", ".workspace-shell .workspace-grid",
  ".workspace-shell .mission-layout", ".workspace-shell .chronicle-list",
  ".workspace-shell .region-passport-grid", ".workspace-shell .achievement-grid",
  ".workspace-shell .mining-command-grid",
].join(",");

function layoutSlug(value, fallback = "panel") {
  const slug = String(value || "").toLocaleLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80);
  return slug || fallback;
}

function pageLayoutContainers(pageName) {
  const page = document.querySelector(`[data-page-name="${CSS.escape(pageName)}"]`);
  if (!page) return [];
  const containers = [...page.querySelectorAll(PAGE_LAYOUT_CONTAINER_SELECTOR)]
    .filter((node) => node.closest(".page") === page);
  const used = new Set();
  containers.forEach((container, index) => {
    if (!container.dataset.layoutContainer) {
      const specific = [...container.classList].filter((name) => ![
        "workspace-grid", "two", "card", "core-module",
      ].includes(name)).join("-");
      let key = layoutSlug(container.id || specific || `container-${index + 1}`, `container-${index + 1}`);
      let suffix = 2;
      while (used.has(key)) key = `${layoutSlug(container.id || specific || "container")}-${suffix++}`;
      container.dataset.layoutContainer = key;
    }
    used.add(container.dataset.layoutContainer);
  });
  return containers.filter((container) => layoutPanels(container).length > 1);
}

function layoutPanels(container) {
  const candidates = [...container.children].filter((node) => node.matches(
    "article, aside, main, .card, .mission-detail, section.telemetry-strip, section.workspace-card, .tool-card",
  ));
  const used = new Set();
  candidates.forEach((panel, index) => {
    if (!panel.dataset.layoutPanel) {
      const heading = panel.querySelector(":scope > header span")?.textContent
        ?.split("·", 1)[0]?.trim();
      const identity = panel.dataset.deckModule
        || heading
        || panel.querySelector(":scope > h3")?.textContent
        || panel.querySelector(":scope > h4")?.textContent
        || panel.querySelector(":scope > small")?.textContent
        || [...panel.classList].find((name) => name !== "card" && name !== "workspace-card")
        || `panel-${index + 1}`;
      let key = layoutSlug(identity, `panel-${index + 1}`);
      let suffix = 2;
      while (used.has(key)) key = `${layoutSlug(identity)}-${suffix++}`;
      panel.dataset.layoutPanel = key;
    }
    used.add(panel.dataset.layoutPanel);
  });
  return candidates;
}

function pageLayoutPanelTitle(panel, fallback = "Dashboard panel") {
  return String(
    panel.querySelector(":scope > header span")?.textContent?.split("·", 1)[0]
    || panel.querySelector(":scope > h3, :scope > h4")?.textContent
    || panel.querySelector(":scope > small")?.textContent
    || panel.dataset.deckModule
    || panel.dataset.layoutPanel
    || fallback
  ).trim();
}

function capturePageLayout(pageName) {
  return Object.fromEntries(pageLayoutContainers(pageName).map((container) => [
    container.dataset.layoutContainer,
    layoutPanels(container).map((panel) => panel.dataset.layoutPanel),
  ]));
}

function applyPageLayout(pageName, layout) {
  if (!layout || typeof layout !== "object") return;
  for (const container of pageLayoutContainers(pageName)) {
    const saved = layout[container.dataset.layoutContainer];
    if (!Array.isArray(saved)) continue;
    const panels = layoutPanels(container);
    const indexed = new Map(panels.map((panel) => [panel.dataset.layoutPanel, panel]));
    const ordered = saved.map((key) => indexed.get(key)).filter(Boolean);
    ordered.push(...panels.filter((panel) => !ordered.includes(panel)));
    const current = panels.map((panel) => panel.dataset.layoutPanel).join("\u0000");
    const desired = ordered.map((panel) => panel.dataset.layoutPanel).join("\u0000");
    if (pageName === "overview") panels.forEach((panel) => { panel.style.order = ""; });
    if (current !== desired) container.append(...ordered);
  }
}

function ensurePageLayoutControl(pageName) {
  if (["map", "overlay-studio"].includes(pageName)) return;
  const containers = pageLayoutContainers(pageName);
  if (!containers.length) return;
  const page = document.querySelector(`[data-page-name="${CSS.escape(pageName)}"]`);
  const header = page?.querySelector(":scope > .page-title, :scope > .about-hero");
  if (!header || header.querySelector("[data-page-layout-open]")) return;
  let actions = header.querySelector(":scope > .title-actions");
  if (!actions) {
    actions = document.createElement("div");
    actions.className = "title-actions";
    header.appendChild(actions);
  }
  const button = document.createElement("button");
  button.className = "ghost";
  button.dataset.pageLayoutOpen = pageName;
  button.textContent = "ARRANGE PANELS";
  actions.prepend(button);
  decorateCockpitButtons(button);
}

function preparePageLayout(pageName) {
  const containers = pageLayoutContainers(pageName);
  if (!containers.length) return;
  if (!pageLayoutDefaults[pageName]) pageLayoutDefaults[pageName] = capturePageLayout(pageName);
  if (pageLayoutEditing !== pageName) applyPageLayout(pageName, model.page_layouts?.[pageName]);
  ensurePageLayoutControl(pageName);
}

function normalisePageVisualOrder(pageName) {
  for (const container of pageLayoutContainers(pageName)) {
    const panels = layoutPanels(container);
    const originalIndex = new Map(panels.map((panel, index) => [panel, index]));
    const ordered = [...panels].sort((left, right) => {
      const leftOrder = Number.parseFloat(getComputedStyle(left).order);
      const rightOrder = Number.parseFloat(getComputedStyle(right).order);
      const a = Number.isFinite(leftOrder) ? leftOrder : 0;
      const b = Number.isFinite(rightOrder) ? rightOrder : 0;
      return a - b || originalIndex.get(left) - originalIndex.get(right);
    });
    container.append(...ordered);
    panels.forEach((panel) => { panel.style.order = ""; });
  }
}

function addPanelLayoutHandles(pageName) {
  for (const container of pageLayoutContainers(pageName)) {
    const panels = layoutPanels(container);
    panels.forEach((panel, index) => {
      panel.classList.add("layout-panel");
      const handle = document.createElement("div");
      handle.className = "panel-layout-handle";
      const title = pageLayoutPanelTitle(panel, `Panel ${index + 1}`);
      handle.innerHTML = `<span class="panel-layout-grip" title="Drag ${escapeHtml(title)}" role="button" aria-label="Drag ${escapeHtml(title)}">⠿</span><div><small>PANEL ${String(index + 1).padStart(2, "0")} / ${String(panels.length).padStart(2, "0")}</small><strong>${escapeHtml(title)}</strong></div><button type="button" data-panel-move="up" ${index === 0 ? "disabled" : ""} aria-label="Move panel earlier">↑</button><button type="button" data-panel-move="down" ${index === panels.length - 1 ? "disabled" : ""} aria-label="Move panel later">↓</button>`;
      panel.appendChild(handle);
    });
  }
}

function refreshPanelLayoutHandles(pageName) {
  for (const container of pageLayoutContainers(pageName)) {
    const panels = layoutPanels(container);
    panels.forEach((panel, index) => {
      const controls = panel.querySelector(":scope > .panel-layout-handle");
      if (!controls) return;
      const position = controls.querySelector(":scope > div > small");
      if (position) position.textContent = `PANEL ${String(index + 1).padStart(2, "0")} / ${String(panels.length).padStart(2, "0")}`;
      controls.querySelector('[data-panel-move="up"]').disabled = index === 0;
      controls.querySelector('[data-panel-move="down"]').disabled = index === panels.length - 1;
    });
  }
}

function clearPageLayoutPointer() {
  const drag = pageLayoutDrag;
  if (drag?.panel) drag.panel.classList.remove("layout-dragging");
  if (drag?.ghost) drag.ghost.remove();
  document.body.classList.remove("layout-pointer-dragging");
  document.querySelectorAll(".layout-drop-before,.layout-drop-after").forEach((panel) => {
    panel.classList.remove("layout-drop-before", "layout-drop-after");
  });
  pageLayoutDrag = null;
  pageLayoutDrop = null;
}

function removePanelLayoutHandles(pageName) {
  clearPageLayoutPointer();
  const page = document.querySelector(`[data-page-name="${CSS.escape(pageName)}"]`);
  page?.querySelectorAll(":scope .panel-layout-handle").forEach((node) => node.remove());
  page?.querySelectorAll(":scope .layout-panel").forEach((panel) => {
    panel.classList.remove(
      "layout-panel", "layout-dragging", "layout-drop-before", "layout-drop-after",
    );
  });
  page?.querySelector(":scope > .page-layout-toolbar")?.remove();
  page?.classList.remove("layout-editing");
  pageLayoutDrop = null;
}

function beginPageLayout(pageName) {
  if (pageLayoutEditing) cancelPageLayout();
  normalisePageVisualOrder(pageName);
  pageLayoutEditing = pageName;
  pageLayoutOriginal = capturePageLayout(pageName);
  const page = document.querySelector(`[data-page-name="${CSS.escape(pageName)}"]`);
  page.classList.add("layout-editing");
  const toolbar = document.createElement("section");
  toolbar.className = "page-layout-toolbar";
  toolbar.innerHTML = `<div><small>PROFILE-AWARE PANEL LAYOUT</small><strong>${escapeHtml(page.querySelector(":scope > .page-title h2")?.textContent || pageName)}</strong><span>Cards are compact while arranging, so every panel is easy to place. Drag a tile or use its arrow controls.</span></div><div><button type="button" data-page-layout-cancel>CANCEL</button><button type="button" data-page-layout-reset>RESET DEFAULT</button><button type="button" class="primary" data-page-layout-save>SAVE TO THIS PROFILE</button></div>`;
  page.querySelector(":scope > .page-title, :scope > .about-hero")?.insertAdjacentElement("afterend", toolbar);
  addPanelLayoutHandles(pageName);
  decorateCockpitButtons(toolbar);
  toolbar.scrollIntoView({block: "nearest", behavior: "smooth"});
}

function cancelPageLayout() {
  if (!pageLayoutEditing) return;
  const pageName = pageLayoutEditing;
  removePanelLayoutHandles(pageName);
  if (pageLayoutOriginal) applyPageLayout(pageName, pageLayoutOriginal);
  pageLayoutEditing = "";
  pageLayoutOriginal = null;
  pageLayoutDrag = null;
  pageLayoutDrop = null;
}

async function savePageLayout() {
  if (!pageLayoutEditing) return;
  const pageName = pageLayoutEditing;
  const containers = capturePageLayout(pageName);
  const accepted = await command("save_page_layout", {page: pageName, containers});
  if (!accepted) {
    showToast("Panel layout could not be saved");
    return;
  }
  model.page_layouts ||= {};
  model.page_layouts[pageName] = containers;
  removePanelLayoutHandles(pageName);
  pageLayoutEditing = "";
  pageLayoutOriginal = null;
  pageLayoutDrag = null;
  pageLayoutDrop = null;
  showToast("Panel layout saved to this commander profile");
}

async function resetPageLayout() {
  if (!pageLayoutEditing) return;
  const pageName = pageLayoutEditing;
  const accepted = await command("reset_page_layout", {page: pageName});
  if (!accepted) return;
  removePanelLayoutHandles(pageName);
  model.page_layouts ||= {};
  delete model.page_layouts[pageName];
  applyPageLayout(pageName, pageLayoutDefaults[pageName] || {});
  pageLayoutEditing = "";
  pageLayoutOriginal = null;
  pageLayoutDrag = null;
  pageLayoutDrop = null;
  showToast("Default panel order restored for this profile");
}

function applyTheme(theme = {}) {
  const keys = ["bg", "panel", "panel_alt", "panel_raised", "header", "input", "inset", "border", "border_soft", "selection", "accent", "orange", "text", "muted", "dim", "green", "yellow", "red"];
  for (const key of keys) {
    const value = theme.palette?.[key];
    if (typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value)) {
      document.documentElement.style.setProperty(`--${key.replaceAll("_", "-")}`, value);
    }
  }
  const names = Array.isArray(theme.available) ? theme.available : [];
  const nextFingerprint = JSON.stringify({name: theme.name || "", palette: theme.palette || {}, names});
  if (nextFingerprint !== themeFingerprint) {
    themeFingerprint = nextFingerprint;
  }
}

function renderBoot(state) {
  const boot = state.boot || {};
  const onboarding = state.onboarding || {};
  const commissioning = Boolean(onboarding.active);
  const bootRoot = byId("boot");
  bootRoot.classList.toggle("commissioning-active", commissioning);
  byId("boot-loader").hidden = commissioning;
  byId("commissioning").hidden = !commissioning;
  if (commissioning) {
    window.clearTimeout(bootHoldTimer);
    bootHoldTimer = 0;
    bootReadyAt = 0;
    bootHoldComplete = false;
    bootRoot.hidden = false;
    window.clearTimeout(bootHideTimer);
    bootHideTimer = 0;
    document.body.classList.remove("ready");
    byId("app").setAttribute("aria-hidden", "true");
    renderCommissioning(onboarding);
    announceBoot({commissioning: true});
    return;
  }

  text("boot-status", boot.status, "INITIALISING FLIGHT COMPUTER");
  text("boot-detail", boot.detail, "Preparing local state");
  const progress = Math.max(0, Math.min(1, number(boot.progress)));
  const progressPercent = Math.round(progress * 100);
  percentWidth("boot-progress", progressPercent);
  text("boot-progress-percent", `${String(progressPercent).padStart(2, "0")}%`);
  byId("boot-track").setAttribute("aria-valuenow", String(progressPercent));
  const stages = bootStages().map((stage) => ({...stage, ready: progress >= stage.threshold}));
  const activeIndex = stages.findIndex((stage) => !stage.ready);
  const activeStage = activeIndex >= 0 ? stages[activeIndex] : {
    key: "handoff", label: "LIVE HANDOFF",
  };
  const loader = byId("boot-loader");
  loader.style.setProperty("--boot-progress", String(progressPercent));
  loader.dataset.bootStage = activeStage.key;
  text("boot-stage-code", activeIndex >= 0
    ? String(activeIndex + 1).padStart(2, "0") : "05");
  text("boot-stage-label", activeStage.label);
  text("boot-stage-footer", `${activeStage.label} // ${progressPercent}%`);
  if (lastBootStage && activeStage.key !== lastBootStage) {
    loader.classList.remove("stage-changing");
    void loader.offsetWidth;
    loader.classList.add("stage-changing");
    window.clearTimeout(bootStageTransitionTimer);
    bootStageTransitionTimer = window.setTimeout(() => {
      loader.classList.remove("stage-changing");
      bootStageTransitionTimer = 0;
    }, 720);
  }
  lastBootStage = activeStage.key;
  for (const [index, stage] of stages.entries()) {
    const reported = boot.systems?.[stage.key];
    const systemState = reported || (stage.ready ? "ready" : index === activeIndex ? "working" : "waiting");
    const active = systemState === "working";
    stage.node.dataset.state = systemState;
    stage.node.classList.toggle("ready", systemState === "ready");
    stage.node.classList.toggle("active", active);
    const badge = stage.node.querySelector(":scope > b");
    if (badge) badge.textContent = ({ready: "READY", working: "ACTIVE", waiting: "WAIT", background: "BACKGROUND", cached: "CACHED", off: "OFF"})[systemState] || "WAIT";
  }
  const announcement = {
    active: Boolean(boot.active),
    status: String(boot.status || ""),
    detail: String(boot.detail || ""),
    progress,
    events: number(boot.events),
    eventsKnown: Number.isFinite(boot.events),
    commander: String(state.profile?.commander || boot.commander || ""),
    system: String(state.flight?.system || ""),
    ship: String(state.flight?.ship || ""),
    journalState: boot.systems?.journal || (boot.status === "JOURNAL LINK OFFLINE" ? "cached" : boot.journal_live ? "ready" : "working"),
    overlaysReady: number(boot.overlays_ready),
    overlaysTotal: number(boot.overlays_total),
    eye: boot.eye === "hal" ? "hal" : "theme",
    update: state.update || {},
    stage: activeStage.key,
    version: String(state.app?.version || ""),
  };
  if (!boot.active) {
    if (!bootReadyAt && !bootHoldComplete) bootReadyAt = performance.now();
    const remaining = bootHoldComplete ? 0 : BOOT_READY_HOLD_MS - (performance.now() - bootReadyAt);
    if (remaining > 0) {
      bootRoot.hidden = false;
      document.body.classList.remove("ready");
      byId("app").setAttribute("aria-hidden", "true");
      text("boot-status", "FLIGHT DECK READY");
      text("boot-detail", "Stand by for live handoff");
      // The boot scene counts down to this moment and jumps into the deck.
      announceBoot({...announcement, handoffAt: performance.now() + remaining});
      if (!bootHoldTimer) {
        bootHoldTimer = window.setTimeout(() => {
          bootHoldTimer = 0;
          renderBoot(model);
        }, Math.ceil(remaining));
      }
      return;
    }
    bootReadyAt = 0;
    bootHoldComplete = true;
    announceBoot({...announcement, handoffAt: performance.now()});
    document.body.classList.add("ready");
    byId("app").setAttribute("aria-hidden", "false");
    if (!bootRoot.hidden && !bootHideTimer) {
      bootHideTimer = window.setTimeout(() => {
        bootHideTimer = 0;
        if (!model.boot?.active && !model.onboarding?.active) {
          bootRoot.hidden = true;
          acknowledgeBootHandoff();
        }
      }, 720);
    }
    if (bootRoot.hidden) acknowledgeBootHandoff();
  } else {
    window.clearTimeout(bootHoldTimer);
    bootHoldTimer = 0;
    bootReadyAt = 0;
    bootHoldComplete = false;
    bootRoot.hidden = false;
    window.clearTimeout(bootHideTimer);
    bootHideTimer = 0;
    document.body.classList.remove("ready");
    byId("app").setAttribute("aria-hidden", "true");
    acknowledgeBootPresented();
    announceBoot(announcement);
  }
}

// The startup systems and the progress each one completes at live in the
// boot markup, so the progress ring's markers and this code agree.
function bootStages() {
  return [...document.querySelectorAll(".boot-sequence > [data-boot-stage]")].map((node) => ({
    node,
    key: node.dataset.bootStage,
    label: node.dataset.bootLabel || node.dataset.bootStage.toUpperCase(),
    threshold: number(node.dataset.bootThreshold),
  }));
}

// boot-scene.js draws the watcher, sky, log and countdown from these.
function announceBoot(detail) {
  window.dispatchEvent(new CustomEvent("voidcompass:boot", {detail}));
}

// First commissioning lives in setup.js.
const SETUP_UI = {command: (...args) => command(...args), showToast: (...args) => showToast(...args), applyTheme: (...args) => applyTheme(...args)};
function renderCommissioning(onboarding) {
  renderSetup(onboarding, SETUP_UI);
}

function renderHeader(state) {
  const flight = state.flight || {};
  const survey = state.survey || {};
  const route = state.route || {};
  const session = state.session || {};
  const traffic = state.traffic || {};
  const source = String(state.sources?.overall || "CACHED").toUpperCase();
  text("header-system", flight.system, "---");
  text("header-context", flight.context, "WAITING FOR LIVE JOURNAL");
  text("header-survey", `${number(survey.scanned)} / ${survey.total_known ? number(survey.total) : "?"}`);
  text("header-route", route.summary, "INACTIVE");
  text("header-session", session.elapsed, "00:00:00");
  text("header-traffic", `${number(traffic.day)} / ${number(traffic.week)} / ${number(traffic.total)}`);
  text("header-commander", state.profile?.commander, "UNKNOWN");
  text("header-ship", `${flight.ship || "SHIP"} // ${flight.state || "FLIGHT"}`.toUpperCase());
  renderOverlaySwitchboard(state.overlay_studio || {});
  text("overview-link-state", `JOURNAL ${source}`);
  byId("overview-link-state").dataset.source = source.toLowerCase();
}

// The header switchboard: one switch per overlay (its Overlay Studio on/off)
// and ALL, the show/hide-all curtain, reachable from every page.
let overlayQuickFingerprint = "";
function renderOverlaySwitchboard(studio = {}) {
  const host = byId("overlay-quick");
  if (!host) return;
  const overlays = Array.isArray(studio.overlays) ? studio.overlays : [];
  const allHidden = Boolean((studio.options || {}).all_hidden);
  const board = host.closest(".overlay-switchboard");
  board.hidden = !overlays.length;
  board.classList.toggle("all-hidden", allHidden);
  const all = byId("overlay-all-toggle");
  all.setAttribute("aria-pressed", String(allHidden));
  all.title = allHidden ? "Overlays are hidden: show them again" : "Hide every overlay for now (each keeps its own setting)";
  text("overlay-all-state", allHidden ? "HIDDEN" : "SHOWN");
  text("overlay-quick-count", `${overlays.filter((row) => row.enabled).length} / ${overlays.length} ON`);
  const fingerprint = JSON.stringify(overlays.map((row) => [row.id, row.short_label, row.label, Boolean(row.enabled)]));
  if (fingerprint === overlayQuickFingerprint) return;
  overlayQuickFingerprint = fingerprint;
  host.replaceChildren(...overlays.map((row) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.overlayQuick = row.id;
    button.className = row.enabled ? "on" : "";
    button.setAttribute("aria-pressed", String(Boolean(row.enabled)));
    button.title = `${row.label}: ${row.enabled ? "on. Click to turn it off" : "off. Click to turn it on"}`;
    button.append(document.createElement("i"));
    const label = document.createElement("span");
    label.textContent = row.short_label || row.label;
    button.append(label);
    return button;
  }));
}

function renderAdaptive(state) {
  const adaptive = state.adaptive || {};
  // Activity awareness now stays automatic and quietly drives contextual
  // emphasis; the retired manual mode strip no longer consumes dashboard space.
  document.body.dataset.activity = adaptive.mode || "general";
}

function renderDecision(state) {
  const decision = state.decision || {};
  text("decision-doctrine", decision.doctrine_label || "BALANCED");
  document.querySelector(".decision-card")?.classList.toggle("warn", String(decision.severity || "").toUpperCase() === "WARN");
  text("decision-confidence", decision.confidence || "JOURNAL-BACKED");
  text("decision-title", decision.title || "HOLD FOR EXPLORATION TELEMETRY");
  text("decision-detail", decision.detail || "No unresolved journal-backed objective is currently known.");
  text("decision-context", state.flight?.system, "UNKNOWN SYSTEM");
  const tags = Array.isArray(decision.tags) ? decision.tags : [];
  const tagsFingerprint = tags.join("\u0000");
  if (tagsFingerprint !== decisionTagsFingerprint) {
    decisionTagsFingerprint = tagsFingerprint;
    byId("decision-tags").replaceChildren(...tags.map((value) => {
      const tag = document.createElement("span");
      tag.textContent = value;
      return tag;
    }));
  }
  const primary = decision.primary || {};
  text("decision-primary", primary.label || "OPEN SYSTEM SURVEY");
  byId("decision-primary").disabled = !primary.command;
}

function renderPreflight(state) {
  const preflight = state.preflight || {};
  const checks = Array.isArray(preflight.checks) ? preflight.checks : [];
  const attention = checks.filter((row) => ["warn", "fail"].includes(String(row.status || "").toLowerCase()));
  const visible = preflightExpanded ? checks : attention;
  const signal = byId("preflight-signal");
  signal.setAttribute("aria-label", `${checks.length} departure checks; ${attention.length} need attention`);
  const signalFingerprint = JSON.stringify(checks.map((row) => [row.id, row.label, row.status, row.value]));
  if (signalFingerprint !== preflightSignalFingerprint) {
    preflightSignalFingerprint = signalFingerprint;
    signal.replaceChildren(...checks.map((row) => {
      const light = document.createElement("i");
      light.className = String(row.status || "warn").toLowerCase();
      light.title = `${row.label || "Check"}: ${row.value || "—"}`;
      return light;
    }));
  }
  const badge = byId("preflight-status");
  text("preflight-status", preflight.status || "CHECK");
  if (badge) badge.dataset.state = String(preflight.status || "check").toLowerCase();
  text("preflight-summary", preflight.summary || "Checking departure systems.");
  const toggle = byId("preflight-toggle");
  toggle.disabled = checks.length === 0;
  toggle.setAttribute("aria-expanded", String(preflightExpanded));
  toggle.textContent = preflightExpanded ? "HIDE CHECKS" : `SHOW ALL ${checks.length} CHECKS`;
  const list = byId("preflight-checks");
  list.hidden = visible.length === 0;
  const fingerprint = JSON.stringify([preflightExpanded, visible.map((row) => [row.id, row.status, row.label, row.value, row.detail])]);
  if (fingerprint === preflightFingerprint) return;
  preflightFingerprint = fingerprint;
  list.replaceChildren(...visible.map((row) => {
    const node = document.createElement("div");
    node.className = `preflight-check ${String(row.status || "warn").toLowerCase()}`;
    const light = document.createElement("i");
    const copy = document.createElement("span");
    const label = document.createElement("small");
    const value = document.createElement("b");
    const detail = document.createElement("em");
    label.textContent = row.label || "CHECK";
    value.textContent = row.value || "—";
    detail.textContent = row.detail || "";
    copy.append(label, value, detail);
    node.append(light, copy);
    return node;
  }));
}

function renderFlightLog(state) {
  const enabled = Boolean(state.ui?.flight_log_mode);
  document.body.classList.toggle("flight-log-mode", enabled);
  byId("flight-log-shell")?.setAttribute("aria-hidden", String(!enabled));
  if (!enabled) return;
  const flight = state.flight || {};
  const survey = state.survey || {};
  const route = state.route || {};
  const data = state.data || {};
  const session = state.session || {};
  const source = String(state.sources?.overall || "CACHED").toUpperCase();
  const sourceNode = byId("flightlog-source");
  sourceNode.dataset.source = ["LIVE", "RECENT", "CACHED"].includes(source) ? source.toLowerCase() : "cached";
  text("flightlog-source", `LOCAL LINK ${sourceNode.dataset.source.toUpperCase()}`);
  text("flightlog-evidence", source === "LIVE" ? "Journal or status linked · recent curated events"
    : source === "RECENT" ? "Game link quiet · recent curated events"
    : "Cached field state · waiting for game activity");
  text("flightlog-commander", state.profile?.commander, "UNKNOWN COMMANDER");
  text("flightlog-ship", flight.ship, "SHIP UNKNOWN");
  text("flightlog-session-time", session.elapsed, "00:00:00");
  text("flightlog-system", flight.system, "NO SYSTEM DATA");
  text("flightlog-state", flight.context, "WAITING FOR LIVE JOURNAL");
  text("flightlog-directive", state.decision?.title, "AWAITING JOURNAL-BACKED OBJECTIVE");
  text("flightlog-directive-detail", state.decision?.detail, "The field directive will appear when exploration evidence is available.");
  text("flightlog-directive-confidence", state.decision?.confidence, "FIELD INTELLIGENCE");
  renderFlightLogDirective(state);
  const knownTotal = Boolean(survey.total_known);
  const progress = knownTotal ? Math.max(0, Math.min(100, number(survey.percent))) : 0;
  const gauge = byId("flightlog-survey-gauge");
  gauge.dataset.known = String(knownTotal);
  gauge.setAttribute("role", knownTotal ? "progressbar" : "img");
  gauge.setAttribute("role", knownTotal ? "progressbar" : "img");
  gauge.style.setProperty("--flightlog-survey-angle", `${progress * 3.6}deg`);
  gauge.setAttribute("aria-label", knownTotal
    ? `System survey ${Math.round(progress)} percent complete`
    : "System survey total not yet confirmed");
  if (knownTotal) gauge.setAttribute("aria-valuenow", String(Math.round(progress)));
  else gauge.removeAttribute("aria-valuenow");
  text("flightlog-survey-percent", knownTotal ? `${Math.round(progress)}%` : "—");
  text("flightlog-survey-badge", knownTotal && survey.complete ? "SYSTEM COMPLETE" : knownTotal ? "SURVEY ACTIVE" : "TOTAL UNKNOWN");
  text("flightlog-survey", `${numeric(survey.scanned)} / ${survey.total_known ? numeric(survey.total) : "?"}`);
  text("flightlog-survey-detail", `${numeric(survey.bio_signals)} BIO · ${numeric(survey.geo_signals)} GEO · ${numeric(survey.valuable_count)} VALUABLE`);
  const work = survey.completion || {};
  const surveyWork = [
    ["FSS UNKNOWN", knownTotal ? numeric(work.unknown_bodies) : "?"],
    ["DSS LEFT", numeric(Math.max(0, number(work.dss_targets) - number(work.dss_complete)))],
    ["BIO LEFT", numeric(Math.max(0, number(work.bio_total) - number(work.bio_complete)))],
  ];
  for (const [index, [label, value]] of surveyWork.entries()) {
    text(`flightlog-work-label-${index}`, label);
    text(`flightlog-work-value-${index}`, value);
  }
  text("flightlog-route", route.next || "NO ACTIVE ROUTE");
  text("flightlog-route-detail", route.summary || route.text || "PLOT IN ELITE OR WAYPOINTS");
  text("flightlog-route-source", route.next ? route.source : "NO PLOTTED LEG");
  text("flightlog-route-final", route.final || "—");
  text("flightlog-route-distance", route.distance_text || "—");
  text("flightlog-value", credits(data.unsold_total));
  text("flightlog-value-detail", `${credits(data.unsold_exploration)} CARTOGRAPHY · ${credits(data.unsold_bio)} BIOLOGY`);
  text("flightlog-jumps", numeric(session.jumps));
  text("flightlog-distance", `${number(session.distance_ly).toLocaleString(undefined, {maximumFractionDigits: 1})} LY`);
  text("flightlog-flown", session.flown || session.elapsed || "—");
  text("flightlog-earned", credits(session.earned));
  text("flightlog-firsts", numeric(session.first_discoveries));
  text("flightlog-rare", numeric(session.rare_worlds));
  const priorities = Array.isArray(state.priorities) ? state.priorities.slice(0, 4) : [];
  const priorityList = byId("flightlog-priorities");
  const priorityKey = JSON.stringify(priorities.map((row) => [row.title, row.detail, row.severity]));
  if (priorityList.dataset.renderKey !== priorityKey) {
    priorityList.dataset.renderKey = priorityKey;
    priorityList.replaceChildren(...(priorities.length ? priorities.map((row, index) => {
      const item = document.createElement("li");
      const ordinal = document.createElement("b");
      const copy = document.createElement("div");
      const title = document.createElement("strong");
      const detail = document.createElement("span");
      ordinal.textContent = String(index + 1).padStart(2, "0");
      title.textContent = row.title || "Field objective";
      detail.textContent = row.detail || "Current field objective.";
      copy.append(title, detail);
      item.append(ordinal, copy);
      return item;
    }) : [Object.assign(document.createElement("li"), {className: "flightlog-priorities-empty", textContent: "No additional field priorities are pending."})]));
  }
  renderFlightLogEvents(state);
}

// The Focused Log's directive: the same tags and action as the Mission
// Directive, a warning tone for fuel, and the Watcher's latest thought.
function renderFlightLogDirective(state) {
  const decision = state.decision || {};
  const panel = document.querySelector(".flightlog-directive");
  panel?.classList.toggle("warn", String(decision.severity || "").toUpperCase() === "WARN");
  const tags = Array.isArray(decision.tags) ? decision.tags : [];
  const host = byId("flightlog-directive-tags");
  const key = tags.join(" ");
  if (host.dataset.renderKey !== key) {
    host.dataset.renderKey = key;
    host.replaceChildren(...tags.map((value) => Object.assign(document.createElement("span"), {textContent: value})));
  }
  const primary = decision.primary || {};
  const button = byId("flightlog-directive-primary");
  button.hidden = !primary.command;
  button.textContent = primary.label || "OPEN";
  const watcher = state.watcher || {};
  const quote = byId("flightlog-watcher");
  quote.hidden = !watcher.text;
  if (watcher.text) {
    text("flightlog-watcher-text", watcher.text);
    const minutes = Math.max(0, Math.round((Date.now() / 1000 - number(watcher.at)) / 60));
    text("flightlog-watcher-when", minutes < 1 ? "JUST NOW" : minutes < 60 ? `${minutes} MIN AGO` : `${Math.round(minutes / 60)} H AGO`);
  }
}

function renderFlightLogEvents(state, resetScroll = false) {
  const recent = (Array.isArray(state.events) ? state.events : []).slice(0, 40);
  const query = flightLogSearch.trim().toLocaleLowerCase();
  const filtered = recent.filter((row) =>
    (flightLogFilter === "ALL" || eventGroup(row.tag, row.severity) === flightLogFilter)
    && (!query || `${row.time || ""} ${row.tag || ""} ${row.message || ""}`.toLocaleLowerCase().includes(query)));
  text("flightlog-event-count", `${filtered.length} SHOWN / ${recent.length} RECENT`);
  text("flightlog-event-limit", (state.events || []).length > 40
    ? `Showing the latest 40 of ${(state.events || []).length} curated events.`
    : "Recent curated events only · not a permanent flight archive.");
  for (const button of document.querySelectorAll("[data-flightlog-filter]")) {
    const active = button.dataset.flightlogFilter === flightLogFilter;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  }
  const fingerprint = JSON.stringify([flightLogFilter, query, filtered.map((row) => [row.ts, row.time, row.tag, row.severity, row.message])]);
  if (fingerprint === flightLogEventsFingerprint) return;
  flightLogEventsFingerprint = fingerprint;
  const list = byId("flightlog-event-list");
  const scrollTop = list.scrollTop;
  const rows = filtered.map((row) => {
    const item = document.createElement("article");
    const severity = String(row.severity || "info").toLowerCase();
    item.className = `flightlog-event ${["info", "warn", "fail", "error"].includes(severity) ? severity : "info"}`;
    const timeNode = document.createElement("time");
    timeNode.textContent = row.time || "--:--:--";
    const tag = document.createElement("b");
    tag.textContent = row.tag || "INFO";
    const message = document.createElement("p");
    message.textContent = row.message || "";
    item.append(timeNode, tag, message);
    return item;
  });
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "flightlog-empty";
    empty.textContent = recent.length
      ? "No recent events match this filter. Change the category or search."
      : "Waiting for curated exploration events from the local journal.";
    rows.push(empty);
  }
  list.replaceChildren(...rows);
  list.scrollTop = resetScroll ? 0 : scrollTop;
}

function surveyPlanetKind(planetClass) {
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

function renderSurveyBodies(survey, system) {
  const bodies = Array.isArray(survey.bodies) ? survey.bodies : [];
  const fingerprint = JSON.stringify([system, bodies]);
  if (fingerprint === surveyBodiesFingerprint) return;
  surveyBodiesFingerprint = fingerprint;
  const list = byId("survey-body-list");
  surveyBodyObserver?.disconnect();
  const previousSystem = list.dataset.system || "";
  const previousLatest = list.dataset.latest || "";
  const scrollTop = list.scrollTop;
  const latest = bodies.find((row) => row.latest_scan);
  const latestKey = latest ? String(latest.body_id ?? latest.name ?? "") : "";
  const ordered = latest ? [latest, ...bodies.filter((row) => row !== latest)] : bodies;
  text("survey-body-total", `${bodies.length} ${bodies.length === 1 ? "BODY RECORD" : "BODY RECORDS"}`);
  list.dataset.system = system;
  list.dataset.latest = latestKey;
  list.classList.toggle("empty", bodies.length === 0);
  if (!bodies.length) {
    surveyBodyObserver = null;
    list.textContent = survey.archive_loading ? "Recovering known-system body records…"
      : number(survey.scanned) ? "Scan progress retained; detailed body records are unavailable for this profile."
      : "Planets and moons appear here as their journal records arrive.";
    return;
  }
  list.replaceChildren(...ordered.map((body) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = ["survey-body-row", body.latest_scan ? "latest" : "", body.priority ? "priority" : "", body.archived ? "archived" : ""].filter(Boolean).join(" ");
    row.dataset.bodyId = String(body.body_id ?? "");
    const fullName = String(body.name || "UNKNOWN BODY");
    row.dataset.bodyName = fullName;
    row.setAttribute("aria-label", `Open ${fullName} in the Survey Board`);
    const name = system && fullName.toLowerCase().startsWith(`${system} `.toLowerCase())
      ? fullName.slice(system.length + 1) : fullName;
    const planetClass = String(body.planet_class || body.type || "");
    const ringCount = Math.max(0, number(body.ring_count));
    const kind = surveyPlanetKind(planetClass);
    row.title = [fullName, planetClass || "Class unconfirmed", body.detail || ""].filter(Boolean).join(" · ");
    const orb = document.createElement("span");
    orb.className = `bridge-planet-orb bridge-planet-${kind}${ringCount ? " has-rings" : ""}`;
    orb.setAttribute("aria-hidden", "true");
    for (const part of ["ring", "sphere", "glint"]) {
      const layer = document.createElement("i");
      layer.className = `bridge-planet-${part}`;
      orb.appendChild(layer);
    }
    const copy = document.createElement("span");
    copy.className = "survey-body-copy";
    const title = document.createElement("b");
    title.textContent = name;
    const detail = document.createElement("small");
    detail.textContent = `${body.archived ? "KNOWN ARCHIVE · " : ""}${planetClass || "CLASS UNCONFIRMED"}`;
    copy.append(title, detail);
    const flags = document.createElement("span");
    flags.className = "survey-body-flags";
    const status = [];
    if (body.latest_scan) status.push(["latest", "LATEST"]);
    if (number(body.bio_count)) status.push(["bio", `BIO ${number(body.bio_count)}`]);
    if (number(body.geo_count)) status.push(["geo", `GEO ${number(body.geo_count)}`]);
    if (body.terraformable) status.push(["terraformable", "TF"]);
    if (!status.length && body.mapped) status.push(["mapped", "MAPPED"]);
    if (!status.length && body.landable) status.push(["landable", "LANDABLE"]);
    if (!status.length && body.archived) status.push(["archive", "ARCHIVE"]);
    if (!status.length) status.push(["scan", planetClass ? "SCAN" : "SIGNAL"]);
    for (const [className, label] of status) {
      const badge = document.createElement("em");
      badge.className = className;
      badge.textContent = label;
      flags.appendChild(badge);
    }
    row.append(orb, copy, flags);
    return row;
  }));
  if ("IntersectionObserver" in window) {
    surveyBodyObserver = new IntersectionObserver((entries) => {
      for (const entry of entries) entry.target.classList.toggle("in-view", entry.isIntersecting);
    }, {root: list, rootMargin: "10px"});
    for (const row of list.querySelectorAll(".survey-body-row")) surveyBodyObserver.observe(row);
  } else {
    for (const row of list.querySelectorAll(".survey-body-row")) row.classList.add("in-view");
  }
  list.scrollTop = previousSystem !== system || previousLatest !== latestKey ? 0 : scrollTop;
}

function renderSurvey(state) {
  const survey = state.survey || {};
  const intel = state.intelligence || {};
  const completion = number(survey.percent);
  const surveyCard = document.querySelector(".overview-modules > .survey-card");
  surveyCard.dataset.surveyState = survey.complete ? "complete" : survey.total_known ? "active" : "awaiting";
  surveyCard.dataset.starClass = String(survey.star_class || "").trim().charAt(0).toUpperCase();
  const orbital = byId("survey-orbital");
  orbital.style.setProperty("--survey-angle", `${Math.max(0, Math.min(100, completion)) * 3.6}deg`);
  orbital.setAttribute("aria-valuetext", survey.total_known ? `${Math.round(completion)}% of bodies scanned` : "System body total unknown");
  if (survey.total_known) orbital.setAttribute("aria-valuenow", String(Math.round(completion)));
  else orbital.removeAttribute("aria-valuenow");
  text("survey-system", state.flight?.system, "NO SYSTEM DATA");
  text("survey-star", survey.star_class ? `STAR CLASS ${survey.star_class}` : "STAR CLASS —");
  text("survey-count", `${number(survey.scanned)} / ${survey.total_known ? number(survey.total) : "?"}`);
  text("survey-bio", `${number(survey.bio_signals)} SIGNALS`);
  text("survey-valuable", `${number(survey.valuable_count)} BODIES`);
  text("survey-region", intel.region, "UNKNOWN");
  text("survey-percent", survey.total_known ? `${Math.round(completion)}%` : "UNKNOWN");
  percentWidth("survey-progress", completion);
  renderSurveyBodies(survey, String(state.flight?.system || ""));
  const badge = byId("survey-badge");
  const badgeText = survey.complete ? "COMPLETE" : survey.undiscovered ? "NEW SYSTEM" : survey.total_known ? "IN PROGRESS" : "AWAITING";
  badge.textContent = badgeText;
  badge.style.color = survey.complete ? "var(--green)" : survey.undiscovered ? "var(--yellow)" : "var(--dim)";

  const rows = Array.isArray(survey.notables) ? survey.notables : [];
  const notable = byId("survey-notables");
  const shown = rows.slice(0, 4);
  const overflow = Math.max(0, number(survey.notable_total, rows.length) - shown.length);
  const overflowNode = byId("survey-overflow");
  overflowNode.hidden = overflow === 0;
  overflowNode.textContent = overflow ? `+${overflow} MORE PRIORITY ${overflow === 1 ? "BODY" : "BODIES"}` : "";
  if (!rows.length) {
    notable.className = "notable-list empty";
    notable.textContent = survey.total_known ? "No priority bodies or surface signals recorded yet." : "Awaiting scan telemetry.";
  } else {
    notable.className = "notable-list";
    notable.replaceChildren(...shown.map((item) => {
      const span = document.createElement("span");
      span.textContent = String(item);
      return span;
    }));
  }

  // The Explore survey board, band and schematic are fed by this snapshot.
  renderExploreSystem(state, EXPLORE_WORKSPACE_UI);
}

function renderRoute(state) {
  const route = state.route || {};
  document.querySelector(".overview-modules > .route-card").classList.toggle("has-route", Boolean(route.next));
  text("route-badge", route.mode === "none" ? "NO ROUTE" : route.mode === "game" ? "GAME ROUTE" : "WAYPOINT PLAN");
  text("route-source", route.source, "NAVIGATION");
  text("route-next", route.next, "NO ACTIVE ROUTE");
  text("route-final", route.final ? `FINAL // ${route.final}` : "Plot a route in Elite or on the Expeditions page.");
  text("route-progress-label", route.text, "INACTIVE");
  text("route-distance", route.distance_text, "— LY");
  text("route-remaining", `${number(route.remaining)} ${number(route.remaining) === 1 ? "JUMP" : "JUMPS"} LEFT`);
  percentWidth("route-progress", route.percent);
  byId("copy-next").disabled = !route.next;
  const autoCopy = byId("auto-copy");
  if (autoCopy) {
    autoCopy.textContent = `AUTO-COPY NEXT WAYPOINT ON ARRIVAL · ${route.auto_copy ? "ON" : "OFF"}`;
    autoCopy.setAttribute("aria-pressed", String(Boolean(route.auto_copy)));
    autoCopy.dataset.enabled = String(!route.auto_copy);
    autoCopy.classList.toggle("on", Boolean(route.auto_copy));
  }
  const horizon = route.horizon || {};
  const rows = Array.isArray(horizon.jumps) ? horizon.jumps : [];
  const parent = byId("route-horizon");
  const horizonFingerprint = JSON.stringify({summary: horizon.summary || "", rows});
  if (horizonFingerprint === routeHorizonFingerprint) return;
  routeHorizonFingerprint = horizonFingerprint;
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.textContent = horizon.summary || "No plotted jump horizon.";
    parent.replaceChildren(empty);
  } else {
    parent.replaceChildren(...rows.map((row) => {
      const item = document.createElement("div");
      item.className = `${row.hazard ? "hazard" : ""} ${row.region_crossing ? "crossing" : ""}`.trim();
      const index = document.createElement("i");
      index.textContent = row.index || "·";
      const system = document.createElement("span");
      system.textContent = row.system || "UNKNOWN SYSTEM";
      const detail = document.createElement("small");
      detail.textContent = `${row.distance_ly === null || row.distance_ly === undefined ? "—" : `${number(row.distance_ly).toFixed(1)} LY`} · ${row.star_class || "?"}`;
      const status = document.createElement("b");
      status.textContent = row.hazard || (row.scoopable === true ? "SCOOP" : row.scoopable === false ? "DRY" : "UNKNOWN");
      item.append(index, system, detail, status);
      item.title = row.region_crossing ? `Region crossing: ${row.region || "unknown"}` : row.region || "";
      return item;
    }));
  }
}

function formatCredits(value) {
  const credits = Math.max(0, number(value));
  if (credits >= 1e9) return `${(credits / 1e9).toFixed(1)}B CR`;
  if (credits >= 1e6) return `${(credits / 1e6).toFixed(1)}M CR`;
  if (credits >= 1e3) return `${Math.round(credits / 1e3)}K CR`;
  return `${Math.round(credits).toLocaleString()} CR`;
}

function renderMetrics(state) {
  const flight = state.flight || {};
  const session = state.session || {};
  const survey = state.survey || {};
  const data = state.data || {};
  const sources = state.sources || {};
  // Out in an SRV, its own tank (5.5.12): the ship's reads as empty there.
  const vehicleFuel = flight.vehicle_fuel;
  if (vehicleFuel) {
    const known = vehicleFuel.percent !== null && vehicleFuel.percent !== undefined;
    text("metric-fuel", known ? `${Math.round(number(vehicleFuel.percent))}%`
      : vehicleFuel.tonnes === null || vehicleFuel.tonnes === undefined ? "—" : `${number(vehicleFuel.tonnes).toFixed(2)} T`);
    text("metric-fuel-detail", `${vehicleFuel.name || "SRV"} TANK${known ? "" : " · SIZE BEING LEARNT"}`);
  } else {
    text("metric-fuel", flight.fuel_percent === null || flight.fuel_percent === undefined ? "—" : `${Math.round(number(flight.fuel_percent))}%`);
    text("metric-fuel-detail", flight.fuel_detail, "AWAITING LOADOUT");
  }
  text("metric-data", formatCredits(data.unsold_total));
  text("metric-data-detail", data.unsold_bio ? `${formatCredits(data.unsold_bio)} BIOLOGICAL` : "EXPLORATION LEDGER");
  const completion = survey.completion || {};
  const fss = Math.max(0, number(completion.unknown_bodies));
  const dss = Math.max(0, number(completion.dss_targets) - number(completion.dss_complete));
  const bio = Math.max(0, number(completion.bio_total) - number(completion.bio_complete));
  const outstanding = fss + dss + bio;
  const surveyKnown = Boolean(survey.total_known || number(survey.scanned));
  text("metric-work", !surveyKnown ? "AWAITING SURVEY" : outstanding ? `${outstanding} OPEN ${outstanding === 1 ? "TASK" : "TASKS"}` : survey.complete ? "CLEAR" : "FSS UNCONFIRMED");
  text("metric-work-detail", !surveyKnown ? "FSS / DSS / BIO UNKNOWN" : `FSS ${survey.total_known ? fss : "?"} · DSS ${dss} · BIO ${bio}`);
  text("metric-health", sources.overall, "CACHED");
  text("metric-health-detail", sources.detail, "WAITING FOR GAME");
  text("record-jumps", number(session.jumps));
  text("record-distance", `${number(session.distance_ly).toLocaleString(undefined, {maximumFractionDigits: 1})} LY`);
  text("record-systems", number(session.systems));
  text("record-bio", number(state.survey?.bio_complete));
}

function renderSessionPulse(state) {
  const session = state.session || {};
  text("pulse-jumps", numeric(session.jumps));
  text("pulse-distance", `${numeric(session.distance_ly, 1)} LY`);
  text("pulse-surveys", `${numeric(session.fss_surveys)} / ${numeric(session.dss_maps)}`);
  text("pulse-discoveries", `${numeric(session.bio_analyses)} / ${numeric(session.codex)}`);
  text("pulse-flown", session.flown || session.elapsed || "—");
  text("pulse-earned", formatCredits(session.earned));
  text("pulse-firsts", numeric(session.first_discoveries));
  text("pulse-rare", numeric(session.rare_worlds));
  text("session-pulse-summary", session.summary || "The current exploration session is waiting for journal activity.");
  const rows = Array.isArray(session.highlights) ? session.highlights : [];
  const highlightsFingerprint = JSON.stringify(rows.slice(0, 3));
  if (highlightsFingerprint !== sessionHighlightsFingerprint) {
    sessionHighlightsFingerprint = highlightsFingerprint;
    byId("session-highlights").replaceChildren(...rows.slice(0, 3).map((row) => {
      const item = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = row.title || row.kind || "SESSION EVENT";
      const detail = document.createElement("span");
      detail.textContent = row.detail || row.kind || "Journal highlight";
      item.append(title, detail);
      return item;
    }));
  }
  text("session-pulse-badge", number(session.jumps) || number(session.fss_surveys) ? "LIVE SESSION" : "STANDING BY");
}

function renderCodexHunt(state) {
  const hunt = state.codex_hunt || {};
  text("codex-region", hunt.region || "UNKNOWN REGION");
  text("codex-coverage", `${Math.round(number(hunt.personal_coverage_percent))}%`);
  text("codex-coverage-detail", `${numeric(hunt.personal_entries_here)} OF ${numeric(hunt.personal_entries_total)} PERSONAL ENTRIES`);
  percentWidth("codex-coverage-bar", hunt.personal_coverage_percent);
  text("codex-note", hunt.availability_note || "Personal coverage comparison; local availability is not inferred.");
  const rows = Array.isArray(hunt.candidates) ? hunt.candidates : [];
  const candidatesFingerprint = JSON.stringify({rows: rows.slice(0, 3), total: hunt.personal_entries_total || 0});
  if (candidatesFingerprint !== codexCandidatesFingerprint) {
    codexCandidatesFingerprint = candidatesFingerprint;
    const candidateNodes = rows.slice(0, 3).map((row) => {
    const item = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = row.name || "CODEX ENTRY";
    const category = document.createElement("span");
    category.textContent = row.category || "UNCLASSIFIED";
    item.append(name, category);
    return item;
    });
    if (!candidateNodes.length) {
      const empty = document.createElement("p");
      empty.className = "codex-empty";
      empty.textContent = hunt.personal_entries_total ? "No personal cross-region gaps are visible in the retained Codex ledger." : "Codex discoveries will build this personal regional comparison.";
      candidateNodes.push(empty);
    }
    byId("codex-candidates").replaceChildren(...candidateNodes);
  }
  byId("codex-add-objective").disabled = !hunt.active_expedition_id || !hunt.target_category;
  byId("codex-add-objective").title = hunt.active_expedition_id ? `Add ${hunt.target_category || "Codex"} to ${hunt.active_expedition_name || "the active expedition"}` : "Start or resume an expedition first";
}

function renderDeckLayout(state) {
  const layout = state.dashboard_layout || {};
  const order = Array.isArray(layout.module_order) ? layout.module_order : [];
  const hidden = new Set(Array.isArray(layout.hidden_modules) ? layout.hidden_modules : []);
  const overviewLayout = model.page_layouts?.overview;
  const pageLayoutOwnsOrder = pageLayoutEditing === "overview"
    || Boolean(overviewLayout && typeof overviewLayout === "object" && Object.keys(overviewLayout).length);
  document.querySelectorAll("[data-deck-module]").forEach((node) => {
    const index = order.indexOf(node.dataset.deckModule);
    node.style.order = pageLayoutOwnsOrder ? "" : String(2 + (index < 0 ? order.length : index) * 2);
    node.hidden = hidden.has(node.dataset.deckModule);
  });
  byId("overview-modules").classList.toggle("route-hidden", hidden.has("route"));
  const corePanels = [
    document.querySelector(".overview-modules > .decision-card"),
    document.querySelector(".overview-modules > .preflight-card"),
    document.querySelector(".overview-modules > .survey-card"),
    document.querySelector(".overview-modules > .telemetry-strip"),
  ];
  if (pageLayoutOwnsOrder) {
    corePanels.forEach((node) => { if (node) node.style.order = ""; });
  } else {
    const routeIndex = Math.max(0, order.indexOf("route"));
    if (corePanels[0]) corePanels[0].style.order = "0";
    if (corePanels[1]) corePanels[1].style.order = "1";
    if (corePanels[2]) corePanels[2].style.order = "2";
    if (corePanels[3]) corePanels[3].style.order = String(4 + routeIndex * 2);
  }

  const panel = byId("deck-customiser");
  if (!panel.hidden && deckLayoutDraft) return;
  deckLayoutDraft = {order: [...order], hidden: [...hidden]};
  const fingerprint = JSON.stringify({available: layout.available_modules || [], order, hidden: [...hidden], doctrines: layout.doctrines || [], doctrine: layout.doctrine});
  if (fingerprint === deckLayoutFingerprint) return;
  deckLayoutFingerprint = fingerprint;
  const doctrine = byId("exploration-doctrine");
  doctrine.replaceChildren(...(layout.doctrines || []).map((row) => {
    const option = document.createElement("option");
    option.value = row.id;
    option.textContent = row.label;
    return option;
  }));
  doctrine.value = layout.doctrine || "balanced";
  renderDeckModuleControls(layout.available_modules || []);
}

function renderDeckModuleControls(available = []) {
  if (!deckLayoutDraft) return;
  const labels = Object.fromEntries(available.map((row) => [row.id, row.label]));
  byId("deck-module-controls").replaceChildren(...deckLayoutDraft.order.map((id) => {
    const row = document.createElement("div");
    row.className = "deck-module-row";
    row.dataset.moduleId = id;
    const visible = document.createElement("input");
    visible.type = "checkbox";
    visible.checked = !deckLayoutDraft.hidden.includes(id);
    visible.dataset.deckVisible = id;
    const label = document.createElement("label");
    label.textContent = labels[id] || id;
    row.append(visible, label);
    return row;
  }));
}

function renderPriorities(state) {
  const priorities = Array.isArray(state.priorities) && state.priorities.length ? state.priorities.slice(0, 4) : [{title: "No urgent objective", detail: "Continue surveying or follow the current route."}];
  const list = byId("priority-list");
  list.replaceChildren(...priorities.map((row, index) => {
    const item = document.createElement("div");
    const rank = document.createElement("b");
    rank.textContent = String(index + 1).padStart(2, "0");
    const copy = document.createElement("p");
    const title = document.createElement("strong");
    title.textContent = row.title || "Exploration task";
    const detail = document.createElement("span");
    detail.textContent = row.detail || "Journal-backed field objective.";
    copy.append(title, detail);
    item.append(rank, copy);
    return item;
  }));
  text("priority-badge", priorities.some((row) => row.severity === "WARN") ? "ATTENTION" : "NOMINAL");
}

function eventGroup(tag, severity) {
  const key = String(tag || "INFO").toUpperCase();
  if (["SCAN", "DSS", "BIO", "MILESTONE", "VALUABLE"].includes(key)) return "DISCOVERY";
  if (["JUMP", "ROUTE", "SYSTEM", "NAV"].includes(key)) return "NAVIGATION";
  if (["ALERT", "WARN", "FAIL"].includes(key) || ["WARN", "FAIL", "ERROR"].includes(String(severity || "").toUpperCase())) return "ALERTS";
  return "OPERATIONS";
}

function createEventRow(row) {
  const item = document.createElement("div");
  const group = eventGroup(row.tag, row.severity);
  item.className = `event-row ${String(row.severity || "").toLowerCase()} ${group.toLowerCase()}`;
  const timeNode = document.createElement("time");
  timeNode.textContent = row.time || "--:--:--";
  const tag = document.createElement("b");
  tag.textContent = row.tag || "INFO";
  const message = document.createElement("p");
  message.textContent = row.message || "";
  item.append(timeNode, tag, message);
  return item;
}

function renderEvents(state) {
  const all = Array.isArray(state.events) ? state.events : [];
  const filtered = feedFilter === "ALL" ? all : all.filter((row) => eventGroup(row.tag, row.severity) === feedFilter);
  const fingerprint = `${feedFilter}:${filtered.map((row) => `${row.ts}:${row.tag}:${row.message}`).join("|")}`;
  if (fingerprint !== feedFingerprint) {
    feedFingerprint = fingerprint;
    byId("event-feed").replaceChildren(...filtered.slice(0, 45).map(createEventRow));
  }
  byId("record-feed").replaceChildren(...all.slice(0, 80).map(createEventRow));
}

function galnetArticles(state = model) {
  return Array.isArray(state.galnet?.articles) ? state.galnet.articles : [];
}

function galnetTimestamp(value, fallback = "UNKNOWN") {
  if (!value) return fallback;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value).toUpperCase();
  return `${parsed.toLocaleString(undefined, {
    timeZone: "UTC", day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).toUpperCase()} UTC`;
}

function renderGalnetReader(state = model) {
  const articles = galnetArticles(state);
  if (!articles.some((row) => row.id === galnetSelectedId)) {
    galnetSelectedId = articles[Math.min(galnetTickerIndex, Math.max(0, articles.length - 1))]?.id || "";
  }
  const selected = articles.find((row) => row.id === galnetSelectedId) || articles[0];
  const selectedIndex = articles.findIndex((row) => row.id === selected?.id);
  const selectedOrdinal = selectedIndex >= 0 ? selectedIndex + 1 : 0;
  const archive = byId("galnet-headlines");
  const archiveKey = `${galnetSelectedId}:${articles.map((row) => `${row.id}:${row.stamp}:${row.title}`).join("|")}`;
  if (archive.dataset.renderKey !== archiveKey) {
    archive.dataset.renderKey = archiveKey;
    archive.replaceChildren(...articles.map((row, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `galnet-headline-row${row.id === selected?.id ? " active" : ""}`;
      button.dataset.galnetSelect = row.id || "";
      if (row.id === selected?.id) button.setAttribute("aria-current", "true");
      const indexNode = document.createElement("span");
      indexNode.className = "galnet-headline-index";
      indexNode.textContent = String(index + 1).padStart(2, "0");
      const copy = document.createElement("span");
      copy.className = "galnet-headline-copy";
      const stamp = document.createElement("small"); stamp.textContent = row.stamp || "GALNET";
      const title = document.createElement("strong"); title.textContent = row.title || "UNTITLED DISPATCH";
      copy.append(stamp, title);
      const chevron = document.createElement("i");
      chevron.className = "galnet-headline-chevron";
      chevron.setAttribute("aria-hidden", "true");
      button.append(indexNode, copy, chevron);
      return button;
    }));
  }
  const feed = state.galnet || {};
  const relayState = feed.busy ? "refreshing" : String(feed.status || "waiting").toLowerCase();
  byId("galnet-reader-shell").dataset.relayState = relayState;
  text("galnet-reader-status", feed.detail || "Galnet relay");
  text("galnet-reader-count", String(articles.length).padStart(2, "0"));
  text("galnet-archive-count", `${String(articles.length).padStart(2, "0")} RECORDS`);
  text("galnet-reader-updated", galnetTimestamp(feed.updated_at, "NOT SYNCED"));
  text("galnet-reader-source", feed.source || "FRONTIER GALNET");
  text("galnet-article-stamp", selected?.stamp || "NO DISPATCH SELECTED");
  text("galnet-article-title", selected?.title || "GALNET RELAY");
  text("galnet-article-number", `DISPATCH ${String(selectedOrdinal).padStart(2, "0")}`);
  text("galnet-article-published", galnetTimestamp(selected?.published, selected?.stamp || "UNKNOWN"));
  text("galnet-article-integrity", relayState === "live" ? "VERIFIED LIVE" : relayState === "cached" ? "CACHED COPY" : relayState === "refreshing" ? "RECEIVING" : relayState === "error" ? "SIGNAL ERROR" : "LOCAL COPY");
  text("galnet-article-position", `${String(selectedOrdinal).padStart(2, "0")} // ${String(articles.length).padStart(2, "0")}`);
  text("galnet-reader-link", relayState === "live" ? "RELAY LINK ESTABLISHED" : relayState === "cached" ? "LOCAL ARCHIVE LINK" : relayState === "refreshing" ? "RECEIVING TRANSMISSIONS" : relayState === "error" ? "RELAY LINK DEGRADED" : "RELAY STANDING BY");
  const articleBody = byId("galnet-article-body");
  const articleChanged = articleBody.dataset.articleId !== (selected?.id || "");
  if (articleChanged) {
    articleBody.dataset.articleId = selected?.id || "";
    text("galnet-article-body", selected?.body || "No Galnet dispatch is available yet.");
    articleBody.scrollTop = 0;
  }
  byId("galnet-previous").disabled = selectedIndex <= 0;
  byId("galnet-next").disabled = selectedIndex < 0 || selectedIndex >= articles.length - 1;
}

function renderGalnet(state, force = false) {
  const feed = state.galnet || {};
  const articles = galnetArticles(state);
  const fingerprint = JSON.stringify({status: feed.status, busy: feed.busy, articles: articles.map((row) => [row.id, row.title, row.stamp])});
  if (fingerprint !== galnetFingerprint) {
    galnetFingerprint = fingerprint;
    const retainedIndex = articles.findIndex((row) => row.id === galnetTickerId);
    galnetTickerIndex = retainedIndex >= 0 ? retainedIndex : 0;
  }
  if (galnetTickerIndex >= articles.length) galnetTickerIndex = 0;
  const row = articles[galnetTickerIndex];
  galnetTickerId = row?.id || "";
  const status = feed.busy ? "refreshing" : (feed.status || "waiting");
  const renderKey = `${fingerprint}:${galnetTickerIndex}`;
  if (force || renderKey !== galnetRenderKey) {
    galnetRenderKey = renderKey;
    text("footer-galnet-title", row?.title || "AWAITING DISPATCHES");
  }
  const ticker = byId("status-galnet");
  const enabled = feed.enabled !== false;
  ticker.hidden = !enabled;
  if (!enabled && !byId("galnet-reader").hidden) byId("galnet-reader").hidden = true;
  ticker.className = `status-galnet ${status}`;
  ticker.title = row ? `${row.stamp || "GALNET"} · ${row.title || ""}` : (feed.detail || "Galnet relay");
  text("footer-galnet-state", status === "refreshing" ? "RX" : (articles.length ? `${galnetTickerIndex + 1}/${articles.length}` : status.toUpperCase()));
  configureGalnetRotation(feed, articles);
  if (enabled && !byId("galnet-reader").hidden) renderGalnetReader(state);
}

function configureGalnetRotation(feed, articles) {
  const enabled = feed.enabled !== false && feed.auto_rotate !== false && articles.length > 1;
  const seconds = Math.max(4, Math.min(60, Math.round(number(feed.rotation_seconds, 7))));
  const key = `${enabled}:${seconds}:${articles.length}`;
  if (key === galnetRotationSettingsKey) return;
  galnetRotationSettingsKey = key;
  if (galnetRotationTimer) window.clearTimeout(galnetRotationTimer);
  galnetRotationTimer = 0;
  if (!enabled) return;
  const rotate = () => {
    if (!document.hidden && byId("galnet-reader").hidden) {
      const current = galnetArticles();
      if (current.length > 1) {
        galnetTickerIndex = (galnetTickerIndex + 1) % current.length;
        renderGalnet(model, true);
      }
    }
    galnetRotationTimer = window.setTimeout(rotate, seconds * 1000);
  };
  galnetRotationTimer = window.setTimeout(rotate, seconds * 1000);
}

function setFactList(id, rows) {
  const parent = byId(id);
  if (!parent) return;
  parent.replaceChildren(...rows.map(([label, value]) => {
    const row = document.createElement("div");
    const left = document.createElement("span");
    left.textContent = label;
    const right = document.createElement("b");
    right.textContent = value;
    row.append(left, right);
    return row;
  }));
}

function renderIntelligence(state) {
  const survey = state.survey || {};
  const intel = state.intelligence || {};
  const data = state.data || {};
  // Explore's readouts: the data aboard, cartography and exobiology apart
  // (what each sells for), and the region. Biology and geology progress sit
  // in the Explore survey band.
  text("intel-carto", formatCredits(data.unsold_exploration));
  text("intel-bio", formatCredits(data.unsold_bio));
  const samples = number(data.unsold_bio_samples);
  text("intel-bio-label", samples ? `EXOBIOLOGY · ${samples} SAMPLE${samples === 1 ? "" : "S"}` : "EXOBIOLOGY");
  const bioReadout = document.getElementById("intel-bio");
  if (bioReadout) {
    bioReadout.title = number(data.unsold_bio_bonus)
      ? `Unsold exobiology: ${formatCredits(data.unsold_bio)}, including ${formatCredits(data.unsold_bio_bonus)} first-footfall bonus (5x)`
      : `Unsold exobiology: ${formatCredits(data.unsold_bio)}`;
  }
  text("explore-region", intel.region, "UNKNOWN");
  setFactList("record-facts", [
    ["Current system", state.flight?.system || "UNKNOWN"],
    ["Survey completion", survey.total_known ? `${Math.round(number(survey.percent))}%` : "UNKNOWN"],
    ["Valuable bodies", String(number(survey.valuable_count))],
    ["Unsold exploration", formatCredits(data.unsold_exploration)],
    ["Unsold biology", formatCredits(data.unsold_bio)],
    ["Galactic region", intel.region || "UNKNOWN"],
  ]);
  text("footer-region", `REGION ${(intel.region || "UNKNOWN").toUpperCase()}`);
}

function renderExpedition(state) {
  const expedition = state.expedition || {};
  const active = Boolean(expedition.active);
  text("expedition-badge", active ? String(expedition.status || "ACTIVE").toUpperCase() : "NO MISSION");
  text("expedition-name", active ? expedition.name : "NO ACTIVE EXPEDITION");
  text("expedition-detail", active ? expedition.detail : "Plan one on the Expeditions page.");
  const total = number(expedition.total);
  const complete = number(expedition.complete);
  percentWidth("expedition-progress", total ? (complete / total) * 100 : 0);
  text("expedition-progress-label", `${complete} / ${total}`);
  // Explore & Survey's link to it shows only while one is on (5.6.1).
  const banner = byId("explore-expedition");
  if (banner) banner.hidden = !active;
}

function renderSources(state) {
  const sources = state.sources || {};
  const mapping = [["journal", "journal-state"], ["status", "status-state"], ["navigation", "nav-state"]];
  for (const [key, id] of mapping) text(id, String(sources[key] || "cached").toUpperCase());
  for (const key of ["journal", "status", "nav"]) {
    const sourceKey = key === "nav" ? "navigation" : key;
    byId(`${key}-light`)?.classList.toggle("live", sources[sourceKey] === "live");
  }
  text("ui-state", sources.ui === "warn" ? "RECOVERED" : "LIVE");
  // EDSM and Inara (5.5.4).
  for (const key of ["edsm", "inara"]) {
    const row = (sources.services || {})[key] || {};
    text(`${key}-state`, row.label || "OFF");
    const light = byId(`${key}-light`);
    light?.classList.toggle("live", row.state === "live");
    light?.classList.toggle("warn", row.state === "warn");
    light?.classList.toggle("recent", row.state === "recent");
    light?.classList.toggle("off", !row.state || row.state === "off");
  }
  byId("ui-light")?.classList.toggle("live", sources.ui !== "warn");
  byId("ui-light")?.classList.toggle("warn", sources.ui === "warn");
  const heartbeat = sources.heartbeat || {};
  const uiHeartbeat = byId("ui-heartbeat");
  const pulseId = String(heartbeat.pulse_id ?? "");
  if (pulseId && uiHeartbeat?.dataset.pulse !== pulseId) {
    uiHeartbeat.dataset.pulse = pulseId;
    uiHeartbeat.classList.remove("beat");
    void uiHeartbeat.offsetWidth;
    uiHeartbeat.classList.add("beat");
    uiHeartbeat.title = `${heartbeat.activity || "TELEMETRY"} · ${heartbeat.state || "FLIGHT"}`;
  }
}

function renderAtlas(state) {
  const atlas = state.atlas || {};
  const frame = byId("atlas-frame");
  const shell = byId("atlas-frame-shell");
  if (!frame || !shell) return;
  // The WebGL atlas is deliberately lazy. Loading it behind the boot curtain
  // or an inactive page competes with the command-deck handoff for GPU time.
  if (currentPage !== "map" || state.boot?.active) return;
  const url = typeof atlas.url === "string" ? atlas.url : "";
  if (url && frame.dataset.url !== url) {
    shell.classList.remove("ready");
    frame.dataset.url = url;
    frame.src = url;
    text("atlas-status", "Live map linked to this commander profile");
  } else if (!url) {
    text("atlas-status", atlasRequested ? "Starting the private atlas renderer…" : "Atlas renderer is ready on demand");
  }
}

function syncAtlasViewport() {
  const frame = byId("atlas-frame");
  if (!frame?.contentWindow) return;
  let targetOrigin = "*";
  try {
    const origin = new URL(model.atlas?.url || frame.dataset.url).origin;
    if (origin && origin !== "null") targetOrigin = origin;
  } catch (_error) {}
  const notify = () => {
    try { frame.contentWindow?.postMessage({type: "voidcompass-atlas-viewport"}, targetOrigin); } catch (_error) {}
  };
  // Focus mode changes several grid rows and columns at once. Two animation
  // frames let Chromium commit that layout before the atlas measures itself;
  // the short follow-up also covers slower WebView2 window resizes.
  requestAnimationFrame(() => requestAnimationFrame(notify));
  window.setTimeout(notify, 120);
}

function syncAtlasLayerRequest() {
  if (!atlasLayerRequest) return;
  const frame = byId("atlas-frame");
  if (!frame?.contentWindow || !byId("atlas-frame-shell")?.classList.contains("ready")) return;
  let targetOrigin = "*";
  try {
    const origin = new URL(model.atlas?.url || frame.dataset.url).origin;
    if (origin && origin !== "null") targetOrigin = origin;
  } catch (_error) {}
  try {
    frame.contentWindow.postMessage({type: "voidcompass-atlas-focus-layer", layer: atlasLayerRequest}, targetOrigin);
    atlasLayerRequest = "";
  } catch (_error) {}
}

function studioData() {
  return model.overlay_studio || {desktop: {}, monitors: [], overlays: [], presets: [], options: {}};
}

function studioOverlay(id) {
  return (studioData().overlays || []).find((row) => row.id === id) || null;
}

// Displays in the overlays' own screen coordinates. The Studio shows one at a
// time; without a monitor list the whole virtual desktop is one display.
function studioMonitors() {
  const studio = studioData();
  if (Array.isArray(studio.monitors) && studio.monitors.length) return studio.monitors;
  const desktop = studio.desktop || {};
  return [{
    id: "display-1", number: 1, label: "DISPLAY 1", primary: true,
    left: number(desktop.left), top: number(desktop.top),
    width: Math.max(1, number(desktop.width, 1920)), height: Math.max(1, number(desktop.height, 1080)),
  }];
}

function studioMonitor(id = studioMonitorId) {
  const monitors = studioMonitors();
  return monitors.find((monitor) => monitor.id === id)
    || monitors.find((monitor) => monitor.primary) || monitors[0];
}

function studioMonitorOf(row) {
  return studioMonitors().find((monitor) => monitor.id === row?.monitor) || studioMonitor();
}

function studioIntersects(row, monitor) {
  return row.x < monitor.left + monitor.width && row.x + row.width > monitor.left
    && row.y < monitor.top + monitor.height && row.y + row.height > monitor.top;
}

function studioDisplayTag(id) {
  const monitor = studioMonitors().find((item) => item.id === id);
  return monitor ? `D${monitor.number}` : "";
}

function placeStudioCard(node, row, monitor) {
  node.style.left = `${(row.x - monitor.left) * 100 / monitor.width}%`;
  node.style.top = `${(row.y - monitor.top) * 100 / monitor.height}%`;
  node.style.width = `${Math.max(2.5, row.width * 100 / monitor.width)}%`;
  node.style.height = `${Math.max(3.5, row.height * 100 / monitor.height)}%`;
  // Every surface stays named: a short card (the Galnet ticker's bar) puts its
  // name and size in one row, and one too small for its name (the heartbeat
  // orb) hangs the name beside it, on the left when it sits near the right.
  // New cards are placed before they are attached, so measure the stage itself.
  const stage = byId("studio-overlay-cards");
  if (stage?.clientWidth && stage.clientHeight) {
    const width = stage.clientWidth * parseFloat(node.style.width) / 100;
    const height = stage.clientHeight * parseFloat(node.style.height) / 100;
    node.classList.toggle("slim", height < 30);
    node.classList.toggle("tiny", width < 70);
    node.classList.toggle("label-left", (row.x - monitor.left + row.width) / monitor.width > .85);
  }
}

// Where the Watcher's words go beside the orb (5.5.3.5): a quiet outline on
// the stage, from the side and room the app works out for its monitor. The
// orb's card stays the orb's size, however long the thought on screen.
function studioThoughtZone(row, monitor) {
  const zone = row.thought;
  if (!zone || !(Number(zone.width) > 0)) return null;
  const node = document.createElement("div");
  node.className = "studio-thought-zone";
  node.dataset.side = zone.side === "left" ? "left" : "right";
  node.setAttribute("aria-hidden", "true");
  node.style.left = `${(number(zone.x) - monitor.left) * 100 / monitor.width}%`;
  node.style.top = `${(number(zone.y) - monitor.top) * 100 / monitor.height}%`;
  node.style.width = `${number(zone.width) * 100 / monitor.width}%`;
  node.style.height = `${number(zone.height) * 100 / monitor.height}%`;
  node.innerHTML = `<span>${escapeHtml(row.short_label)}</span>`;
  return node;
}

function renderStudioMoveDisplay(row, monitor) {
  const host = byId("studio-move-display");
  if (!host) return;
  const others = studioMonitors().filter((item) => item.id !== monitor?.id);
  host.replaceChildren(...others.map((target) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.studioMoveDisplay = target.id;
    button.textContent = `MOVE TO ${target.label}`;
    return button;
  }));
  host.hidden = !row || !others.length;
}

function selectStudioOverlay(id, follow = false) {
  const selected = studioOverlay(id);
  if (!selected) return;
  studioSelectedId = id;
  // Choosing a surface from the roster brings its display onto the stage.
  if (follow && selected.monitor && selected.monitor !== studioMonitorId) {
    studioMonitorId = selected.monitor;
    studioFingerprint = "";
    renderOverlayStudio(model);
    return;
  }
  document.querySelectorAll(".studio-overlay-card, .studio-index-row").forEach((node) => {
    node.classList.toggle("selected", node.dataset.overlayId === id);
  });
  const monitor = studioMonitorOf(selected);
  text("studio-selected-state", selected.state, "READY");
  text("studio-selected-short", selected.short_label, "SURFACE");
  text("studio-selected-name", selected.label, "Overlay");
  text("studio-selected-position", `X ${selected.x - monitor.left} · Y ${selected.y - monitor.top}`);
  text("studio-selected-size", `${selected.width} × ${selected.height}`);
  text("studio-selected-display", monitor.label);
  text("studio-selected-renderer", selected.html_ready ? "HTML READY" : selected.enabled ? "LINKING" : "STANDBY");
  text("studio-selected-visibility", selected.shown ? "On screen now"
    : selected.enabled ? "Shows when it has something to report" : "Off for this commander");
  // A focused switch keeps the click just made while its save is in flight,
  // but only for the overlay it was clicked for: choosing another overlay
  // (the stage cards don't take focus) always shows that overlay's own state.
  const fill = (input, value) => {
    if (!input) return;
    if (document.activeElement !== input || input.dataset.overlayId !== id) input.checked = value;
    input.dataset.overlayId = id;
  };
  fill(byId("studio-selected-enabled"), Boolean(selected.enabled));
  // Per overlay; the All overlays switch turns map hiding on or off for all.
  const mapsOn = Boolean((studioData().options || {}).overlay_hide_on_maps ?? true);
  const mapHide = byId("studio-selected-maphide");
  fill(mapHide, selected.hide_on_maps !== false);
  if (mapHide) mapHide.disabled = !mapsOn;
  text("studio-selected-maphide-note", !mapsOn ? "Off for every overlay (All overlays)"
    : selected.hide_on_maps !== false ? "Hides on the Galaxy Map, System Map and Orrery" : "Stays on screen on the maps");
  // The same for the menus (5.7.1), which are off for all until switched on.
  const menusOn = Boolean((studioData().options || {}).overlay_hide_in_menus);
  const menuHide = byId("studio-selected-menuhide");
  fill(menuHide, selected.hide_in_menus !== false);
  if (menuHide) menuHide.disabled = !menusOn;
  text("studio-selected-menuhide-note", !menusOn ? "Off for every overlay (All overlays)"
    : selected.hide_in_menus !== false ? "Hides on ship panels, station services and menus" : "Stays on screen in the menus");
  // Its own opacity (5.5.3.3), or the one set for all overlays.
  const ownOpacity = byId("studio-selected-opacity");
  if (ownOpacity && document.activeElement !== ownOpacity) ownOpacity.value = String(Number(selected.own_opacity) || 0);
  text("studio-selected-opacity-note", Number(selected.own_opacity) ? "Its own, whatever OPACITY is set to" : "Same as all overlays (OPACITY)");
  // Its own text size (5.5.4), or the one set for all overlays. The Watcher's
  // words have theirs on the Watcher page.
  const ownText = byId("studio-selected-text");
  const watcher = id === "heartbeat_hud";
  byId("studio-own-text").hidden = watcher;
  if (ownText && document.activeElement !== ownText) ownText.value = String(Number(selected.own_text) || 0);
  text("studio-selected-text-note", Number(selected.own_text) ? "Its own, whatever TEXT SIZE is set to" : "Same as all overlays (Settings › Appearance)");
  // The inspector shows only this surface's own settings.
  let own = false;
  document.querySelectorAll("[data-studio-settings]").forEach((node) => {
    const match = node.dataset.studioSettings === id;
    node.hidden = !match;
    own ||= match;
  });
  const none = document.querySelector('[data-studio-settings="none"]');
  if (none) none.hidden = own;
  renderStudioMoveDisplay(selected, monitor);
}

function applyStudioFilters() {
  const queryText = studioSearch.trim().toLocaleLowerCase();
  const matches = (row) => {
    if (!row) return false;
    const stateMatch = studioFilter === "all" || (studioFilter === "enabled" && row.enabled)
      || (studioFilter === "disabled" && !row.enabled) || (studioFilter === "visible" && row.shown)
      || (studioFilter === "display" && studioIntersects(row, studioMonitor()));
    const textMatch = !queryText || `${row.label} ${row.short_label} ${row.id}`.toLocaleLowerCase().includes(queryText);
    return stateMatch && textMatch;
  };
  document.querySelectorAll(".studio-index-row").forEach((node) => {
    node.hidden = !matches(studioOverlay(node.dataset.overlayId));
  });
  document.querySelectorAll(".studio-overlay-card").forEach((node) => {
    node.classList.toggle("filtered-out", !matches(studioOverlay(node.dataset.overlayId)));
  });
}

function syncStudioOpacity(value) {
  const percent = Math.max(40, Math.min(100, Math.round(number(value, 100))));
  byId("studio-desktop-viewport")?.style.setProperty("--studio-global-opacity", String(percent / 100));
  const input = byId("studio-global-fade");
  if (input) input.value = percent;
  text("studio-global-fade-value", `${percent}%`);
  return percent;
}

function sendStudioOpacity(value) {
  if (studioOpacityTimer) clearTimeout(studioOpacityTimer);
  studioOpacityTimer = 0;
  const percent = Math.max(40, Math.min(100, Math.round(number(value, 100))));
  if (percent === studioOpacityLastSentValue) return;
  studioOpacityLastSentValue = percent;
  studioOpacityLastSentAt = Date.now();
  const sequence = ++studioOpacitySequence;
  command("overlay_studio", {operation: "set_opacity", value: percent, sequence}).then((accepted) => {
    if (accepted || sequence !== studioOpacitySequence) return;
    studioOpacityLastSentValue = null;
    studioOpacityPending = null;
    syncStudioOpacity(studioData().options?.overlay_opacity_percent);
  });
}

function queueStudioOpacity(value, flush = false) {
  const percent = syncStudioOpacity(value);
  studioOpacityPending = percent;
  studioOpacityPendingAt = Date.now();
  if (studioOpacityTimer) clearTimeout(studioOpacityTimer);
  const delay = flush ? 0 : Math.max(0, 120 - (Date.now() - studioOpacityLastSentAt));
  if (!delay) sendStudioOpacity(percent);
  else studioOpacityTimer = setTimeout(() => sendStudioOpacity(percent), delay);
}

function updateStudioOptionControls(options, groundTarget = {}) {
  document.querySelectorAll("[data-overlay-option]").forEach((input) => {
    if (document.activeElement !== input) input.checked = Boolean(options[input.dataset.overlayOption]);
  });
  document.querySelectorAll("[data-studio-setting]").forEach((field) => {
    if (document.activeElement !== field) field.value = options[field.dataset.studioSetting] ?? "";
  });
  const layoutMode = byId("studio-layout-mode");
  if (layoutMode) layoutMode.checked = Boolean(options.layout_mode);
  const savedOpacity = Math.max(40, Math.min(100, Math.round(number(options.overlay_opacity_percent, 100))));
  if (studioOpacityPending === savedOpacity || Date.now() - studioOpacityPendingAt > 3000) {
    studioOpacityPending = null;
  }
  const fade = byId("studio-global-fade");
  syncStudioOpacity(document.activeElement === fade ? fade.value : studioOpacityPending ?? savedOpacity);
  const stationTimeout = byId("studio-station-timeout");
  if (stationTimeout) stationTimeout.disabled = !Boolean(options.station_info_auto_hide_enabled);
  const targetFields = {
    "studio-ground-lat": groundTarget.active ? groundTarget.lat : null,
    "studio-ground-lon": groundTarget.active ? groundTarget.lon : null,
  };
  for (const [id, value] of Object.entries(targetFields)) {
    const field = byId(id);
    if (field && document.activeElement !== field) {
      field.value = value === null || value === undefined ? "" : Number(value).toFixed(6);
    }
  }
  const overlayEnabled = Boolean(studioOverlay("ground_popup")?.enabled);
  text("studio-ground-target-state", groundTarget.navigation_ready ? "COMPASS LIVE"
    : groundTarget.active ? "TARGET ARMED" : "TARGET OFF");
  text("studio-ground-target-detail", groundTarget.active
    ? `${Number(groundTarget.lat).toFixed(6)}, ${Number(groundTarget.lon).toFixed(6)}`
    : "NO COORDINATES SET");
  text("studio-ground-visibility", !overlayEnabled ? "OVERLAY OFF"
    : groundTarget.navigation_ready ? "LIVE PLANET GUIDANCE" : "HIDDEN UNTIL APPROACH");
  const readout = document.querySelector(".studio-ground-readout");
  readout?.classList.toggle("live", Boolean(groundTarget.navigation_ready && overlayEnabled));
  readout?.classList.toggle("armed", Boolean(groundTarget.active && !groundTarget.navigation_ready && overlayEnabled));
  const current = byId("studio-ground-current");
  if (current) current.disabled = !Boolean(groundTarget.current_available);
  const clear = byId("studio-ground-clear");
  if (clear) clear.disabled = !Boolean(groundTarget.active);
}

// A small map of the desktop's displays, in their real arrangement; each
// display is a tab that brings it onto the stage.
function renderStudioMonitors(monitors, overlays) {
  const host = byId("studio-monitors");
  const left = Math.min(...monitors.map((item) => item.left));
  const top = Math.min(...monitors.map((item) => item.top));
  const width = Math.max(1, Math.max(...monitors.map((item) => item.left + item.width)) - left);
  const height = Math.max(1, Math.max(...monitors.map((item) => item.top + item.height)) - top);
  host.style.setProperty("--studio-map-aspect", `${width} / ${height}`);
  host.hidden = monitors.length < 2;
  host.replaceChildren(...monitors.map((monitor) => {
    const button = document.createElement("button");
    const active = monitor.id === studioMonitorId;
    const count = overlays.filter((row) => row.enabled && row.monitor === monitor.id).length;
    button.type = "button";
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", active ? "true" : "false");
    button.dataset.studioDisplay = monitor.id;
    button.className = `studio-monitor${active ? " active" : ""}${monitor.primary ? " main-display" : ""}`;
    button.style.left = `${(monitor.left - left) * 100 / width}%`;
    button.style.top = `${(monitor.top - top) * 100 / height}%`;
    button.style.width = `${monitor.width * 100 / width}%`;
    button.style.height = `${monitor.height * 100 / height}%`;
    button.title = `${monitor.label} · ${monitor.width} × ${monitor.height}${monitor.primary ? " · primary" : ""} · ${count} on`;
    button.innerHTML = `<b>${monitor.number}</b><small>${count}</small>`;
    return button;
  }));
}

function showStudioDisplay(id) {
  if (!studioMonitors().some((monitor) => monitor.id === id) || id === studioMonitorId) return;
  studioMonitorId = id;
  // Keep a selection the stage can show.
  const selected = studioOverlay(studioSelectedId);
  if (!selected || !studioIntersects(selected, studioMonitor())) {
    const onDisplay = (studioData().overlays || []).filter((row) => studioIntersects(row, studioMonitor()));
    studioSelectedId = (onDisplay.find((row) => row.enabled) || onDisplay[0] || selected || {}).id || "";
  }
  studioFingerprint = "";
  renderOverlayStudio(model);
}

function renderOverlayStudio(state) {
  const studio = state.overlay_studio || {};
  const overlays = Array.isArray(studio.overlays) ? studio.overlays : [];
  const monitors = studioMonitors();
  if (!studioSelectedId || !overlays.some((row) => row.id === studioSelectedId)) {
    studioSelectedId = overlays.find((row) => row.enabled)?.id || overlays[0]?.id || "";
  }
  if (!monitors.some((monitor) => monitor.id === studioMonitorId)) {
    studioMonitorId = studioOverlay(studioSelectedId)?.monitor || studioMonitor("").id;
  }
  const monitor = studioMonitor();

  const fingerprint = JSON.stringify({monitors, overlays, display: studioMonitorId});
  if (!studioDragging && fingerprint !== studioFingerprint) {
    studioFingerprint = fingerprint;
    renderStudioMonitors(monitors, overlays);
    const stage = byId("studio-desktop");
    stage.style.setProperty("--studio-aspect", `${monitor.width} / ${monitor.height}`);
    stage.style.setProperty("--studio-aspect-number", String(monitor.width / monitor.height));
    const cards = overlays.filter((row) => studioIntersects(row, monitor)).flatMap((row) => {
      const node = document.createElement("button");
      node.type = "button";
      node.className = `studio-overlay-card${row.enabled ? " enabled" : " disabled"}${row.shown ? " shown" : ""}`;
      node.dataset.overlayId = row.id;
      node.title = `${row.label}: drag to place`;
      placeStudioCard(node, row, monitor);
      node.innerHTML = `<span>${escapeHtml(row.short_label)}</span><small>${row.width} × ${row.height}</small>`;
      // The orb's words have their outline, which carries its name too (at a
      // screen edge a name hung beside the orb fell off the stage).
      const zone = studioThoughtZone(row, monitor);
      node.classList.toggle("zoned", Boolean(zone));
      return zone ? [zone, node] : [node];
    });
    byId("studio-overlay-cards").replaceChildren(...cards);

    const several = monitors.length > 1;
    // The list beside the stage, in alphabetical order.
    const byName = [...overlays].sort((a, b) => String(a.label || "").localeCompare(String(b.label || ""), undefined, {sensitivity: "base"}));
    const index = byName.map((row) => {
      const item = document.createElement("div");
      item.className = `studio-index-row${row.enabled ? " enabled" : ""}${row.shown ? " shown" : ""}`;
      item.dataset.overlayId = row.id;
      const status = row.in_hud ? "IN THE NAV HUD" : row.shown ? "ON SCREEN" : row.enabled ? "READY" : "OFF";
      item.innerHTML = `<button type="button" class="studio-index-select"><i></i><span><b>${escapeHtml(row.label)}</b><small>${several ? `${studioDisplayTag(row.monitor)} · ` : ""}${status}</small></span></button>`
        + `<label class="studio-row-switch" title="Enable or disable ${escapeHtml(row.label)}"><input type="checkbox" data-overlay-enable="${escapeHtml(row.id)}"${row.enabled ? " checked" : ""} aria-label="Enable ${escapeHtml(row.label)}"><i></i></label>`;
      return item;
    });
    byId("studio-overlay-index").replaceChildren(...index);
  }

  const enabled = overlays.filter((row) => row.enabled).length;
  const shown = overlays.filter((row) => row.shown).length;
  text("studio-enabled-count", `${enabled} OF ${overlays.length} ON`);
  text("studio-roster-summary", `${shown} ON SCREEN · ${overlays.filter((row) => row.html_ready).length} LINKED`);
  text("studio-desktop-label", `${monitor.label} · ${monitor.width} × ${monitor.height}${monitor.primary ? " · PRIMARY" : ""}`);
  const presetSelect = byId("studio-preset-select");
  const previousPreset = presetSelect.value;
  const presetNames = Array.isArray(studio.presets) ? studio.presets : [];
  const presetKey = presetNames.join("\u0000");
  if (presetSelect.dataset.presets !== presetKey) {
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = presetNames.length ? "SAVED LAYOUTS" : "NO SAVED LAYOUTS";
    presetSelect.replaceChildren(empty, ...presetNames.map((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      return option;
    }));
    presetSelect.dataset.presets = presetKey;
    if (presetNames.includes(previousPreset)) presetSelect.value = previousPreset;
  }
  updateStudioOptionControls(studio.options || {}, studio.ground_target || {});
  if (studioSelectedId) selectStudioOverlay(studioSelectedId);
  applyStudioFilters();
}

async function ensureAtlas() {
  const url = model.atlas?.url;
  if (url) {
    renderAtlas(model);
    return true;
  }
  if (atlasRequested) return false;
  atlasRequested = true;
  text("atlas-status", "Starting the private atlas renderer…");
  const accepted = await command("open", {target: "map"});
  if (!accepted) {
    atlasRequested = false;
    text("atlas-status", "Galactic Atlas could not be started");
  }
  return accepted;
}

function workspaceMetrics(items = []) {
  return `<section class="workspace-metrics">${items.map((item) => `
    <article><small>${escapeHtml(item.label)}</small><strong>${escapeHtml(item.value ?? "—")}</strong><span>${escapeHtml(item.detail || "")}</span></article>
  `).join("")}</section>`;
}

function workspaceCard(title, body, badge = "", extraClass = "") {
  return `<article class="card workspace-card${extraClass ? ` ${escapeHtml(extraClass)}` : ""}"><header><span>${escapeHtml(title)}</span>${badge ? `<b>${escapeHtml(badge)}</b>` : ""}</header>${body}</article>`;
}

function workspaceRows(rows = [], empty = "No journal-backed records are available yet.") {
  if (!rows.length) return `<p class="workspace-empty">${escapeHtml(empty)}</p>`;
  return `<div class="workspace-rows">${rows.join("")}</div>`;
}

function workspaceTable(columns, rows, empty = "No records available.") {
  if (!rows.length) return `<p class="workspace-empty">${escapeHtml(empty)}</p>`;
  return `<div class="workspace-table-wrap"><table class="workspace-table"><thead><tr>${columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map((column) => `<td>${column.render ? column.render(row) : escapeHtml(row[column.key] ?? "—")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

// The value breakdown, the discovery record and the body's scan facts
// (after EDDiscovery's scan panel, 5.5.3.1).
function orreryValueBlock(body) {
  const values = body.values || {};
  const table = (body.facts || {}).value_table || {};
  const parts = [];
  if (body.kind !== "star" && number(values.scan)) {
    parts.push(`SCAN <b>${credits(values.scan)}</b>`);
    if (number(values.mapped)) parts.push(`MAPPED <b>${credits(values.mapped)}</b>`);
    if (number(values.mapped_plain) && number(values.mapped_plain) !== number(values.mapped)) {
      parts.push(`WITHOUT EFFICIENCY <b>${credits(values.mapped_plain)}</b>`);
    }
  }
  // What it would pay in each case (EDDiscovery's value table).
  const cases = [
    ["NO BONUS", table.base], ["IF FIRST DISCOVERED", table.first_discovered], ["IF MAPPED", table.mapped],
    ["IF FIRST MAPPED", table.first_mapped], ["IF FIRST TO BOTH", table.first_discovered_mapped],
  ].filter(([, value]) => number(value));
  const record = [];
  if (body.was_discovered === true) record.push("ALREADY DISCOVERED");
  // Stars cannot be mapped.
  if (body.kind !== "star" && body.was_mapped === true) record.push("ALREADY MAPPED");
  else if (body.kind !== "star" && body.was_mapped === false) record.push(body.mapped ? "FIRST MAPPED" : "NEVER MAPPED");
  if (body.was_footfalled === true) record.push("ALREADY FOOTFALLED");
  const dss = (body.facts || {}).dss;
  if (dss) record.push(`DSS ${dss.probes}/${dss.target} ${dss.efficient ? "· EFFICIENT" : "· OVER TARGET"}`);
  const scanType = (body.facts || {}).scan_type;
  if (scanType) record.push(`SCAN: ${String(scanType).replace(/([a-z])([A-Z])/g, "$1 $2").toUpperCase()}`);
  return (parts.length ? `<div class="orrery-values">${parts.map((part) => `<span>${part}</span>`).join("")}</div>` : "")
    + (cases.length > 1 ? `<div class="orrery-group"><small>VALUE IN EACH CASE</small><div class="orrery-values cases">${cases.map(([label, value]) => `<span>${label} <b>${credits(value)}</b></span>`).join("")}</div></div>` : "")
    + (record.length ? `<div class="orrery-flags record">${record.map((flag) => `<em>${escapeHtml(flag)}</em>`).join("")}</div>` : "");
}

// Every fact the scan gives, grouped (after EDDiscovery's scan panel).
function orreryFactsBlock(body) {
  const facts = body.facts || {};
  const star = body.kind === "star";
  const group = (title, rows) => {
    const cells = rows.filter(([, value]) => value !== null && value !== undefined && value !== "")
      .map(([label, value]) => `<span>${label} <b>${escapeHtml(String(value))}</b></span>`);
    return cells.length ? `<div class="orrery-group"><small>${title}</small><div class="orrery-facts more">${cells.join("")}</div></div>` : "";
  };
  const chips = (title, rows, tone = "") => rows.length
    ? `<div class="orrery-flags composition${tone ? ` ${tone}` : ""}"><small>${title}</small>${rows.map((text) => `<em>${escapeHtml(text)}</em>`).join("")}</div>` : "";
  const deg = (value, places = 1) => value == null ? null : `${numeric(value, places)}°`;
  const sma = body.semi_major_axis;
  const smaText = !sma ? null : sma < 0.01 * 149597870700
    ? `${numeric(sma / 1000, 0)} KM` : `${numeric(sma / 149597870700, 3)} AU`;
  const physical = group(star ? "STAR" : "BODY", [
    ["CLASS", facts.classification || null],
    ["TEMPERATURE", body.temperature_k == null ? null : `${numeric(body.temperature_k, 0)} K`],
    ["PRESSURE", !(facts.pressure_atm > 0) ? null : `${numeric(facts.pressure_atm, facts.pressure_atm < .1 ? 3 : 2)} ATM`],
    ["RADIUS", facts.radius_sr != null ? `${numeric(facts.radius_sr, 3)} SR` : facts.radius_km == null ? null : `${numeric(facts.radius_km, 0)} KM`],
    ["MASS", facts.earth_masses != null ? `${numeric(facts.earth_masses, 4)} EM` : facts.solar_masses != null ? `${numeric(facts.solar_masses, 3)} SM` : null],
    ["AGE", facts.age_my == null ? null : `${numeric(facts.age_my, 0)} MY`],
    ["ABS MAGNITUDE", facts.absolute_magnitude == null ? null : numeric(facts.absolute_magnitude, 2)],
    ["VOLCANISM", facts.volcanism || null],
    ["RESERVES", facts.reserve || null],
  ]);
  const orbit = group("ORBIT", [
    ["ORBITS", facts.orbits || null],
    ["SEMI-MAJOR AXIS", smaText],
    ["ECCENTRICITY", body.eccentricity == null ? null : numeric(body.eccentricity, 4)],
    ["INCLINATION", deg(facts.inclination_deg, 2)],
    ["PERIAPSIS", deg(facts.periapsis_deg, 2)],
    ["ASCENDING NODE", deg(facts.ascending_node_deg, 2)],
    ["MEAN ANOMALY", deg(facts.mean_anomaly_deg, 2)],
    ["ROTATION", facts.tidal_lock ? "TIDALLY LOCKED" : body.rotation_period ? `${numeric(Math.abs(body.rotation_period) / 86400, 3)} DAYS${body.rotation_period < 0 ? " (RETROGRADE)" : ""}` : null],
    ["AXIAL TILT", deg(facts.axial_tilt_deg, 2)],
  ]);
  const zones = facts.zones || {};
  const range = (pair) => Array.isArray(pair) ? `${numeric(pair[0], 0)}–${numeric(pair[1], 0)} LS` : null;
  const zoneBlock = star && Object.keys(zones).length ? group("CIRCUMSTELLAR ZONES", [
    ["HABITABLE", range(zones.habitable)], ["EARTH-LIKE", range(zones.earth_like)],
    ["WATER WORLDS", range(zones.water_world)], ["AMMONIA WORLDS", range(zones.ammonia_world)],
    ["METAL-RICH", range(zones.metal_rich)], ["ICY FROM", zones.icy_from == null ? null : `${numeric(zones.icy_from, 0)} LS`],
  ]) : "";
  const atmosphere = (facts.atmosphere_composition || []).map((row) => `${row.name} ${numeric(row.percent, 1)}%`);
  const composition = Object.entries(facts.composition || {}).map(([name, percent]) => `${name} ${numeric(percent, 1)}%`);
  const rings = (facts.rings || []).map((ring) => [
    `${ring.class || "Ring"} ${ring.belt ? "belt" : "ring"}`,
    ring.inner_km && ring.outer_km ? `${numeric(ring.inner_km, 0)}–${numeric(ring.outer_km, 0)} KM` : ring.width_km ? `${numeric(ring.width_km, 0)} KM WIDE` : "",
    ring.mass_mt ? `${numeric(ring.mass_mt, 0)} MT` : "",
  ].filter(Boolean).join(" · "));
  const organics = (facts.organics || []).map((row) => `${row.name} · ${String(row.state).toUpperCase()}`);
  return physical + orbit + zoneBlock
    + chips("ATMOSPHERE", atmosphere) + chips("MAKE-UP", composition) + chips("RINGS", rings)
    + chips("GENERA", facts.genera || [], "life") + chips("ORGANICS", organics, "life") + chips("CODEX", facts.codex || [], "life")
    + chips("NOTES", facts.notes || [], "notes");
}

function orreryDetail(body) {
  if (!body) return `<p class="workspace-empty">Select a body in the system architecture.</p>`;
  const period = body.orbital_period ? `${numeric(body.orbital_period / 86400, 2)} DAYS` : "UNREPORTED";
  const position = body.orbit?.resolved ? "LIVE KEPLER POSITION" : body.source === "edsm" ? "EDSM ORBIT · POSITION APPROXIMATE" : "SCHEMATIC POSITION";
  const flags = [...(body.flags || []), position, body.rings ? `${numeric(body.rings)} RING${number(body.rings) === 1 ? "" : "S"}` : ""].filter(Boolean);
  const materials = (body.materials || []).slice(0, 8).map((row) => `<em>${escapeHtml(row.name)} ${numeric(row.percent, 1)}%</em>`).join("");
  return `<div class="orrery-body-title"><i class="${escapeHtml(body.kind)}"></i><div><small>BODY ${escapeHtml(body.body_id ?? "—")} · ${body.is_moon ? "MOON" : escapeHtml(String(body.kind || "BODY").toUpperCase())}</small><h3>${escapeHtml(body.name)}</h3><span>${escapeHtml(body.class)}</span></div><b>${credits(body.value)}</b></div><div class="orrery-facts"><span>ORBIT <b>${period}</b></span><span>DISTANCE <b>${body.distance_ls === null ? "—" : `${numeric(Math.abs(body.distance_ls), 1)} LS`}</b></span>${body.kind === "star" ? "" : `<span>GRAVITY <b>${body.gravity_g === null ? "—" : `${numeric(body.gravity_g, 2)} G`}</b></span><span>ATMOSPHERE <b>${escapeHtml(body.atmosphere || "AIRLESS")}</b></span><span>BIOLOGY <b>${numeric(body.bio_complete)} / ${numeric(body.bio)}</b></span><span>GEOLOGY <b>${numeric(body.geo)}</b></span><span>MINING SITES <b>${numeric(body.mining)}</b></span>`}</div><div class="orrery-flags">${flags.map((flag) => `<em>${escapeHtml(flag)}</em>`).join("") || "<em>STANDARD SURVEY RECORD</em>"}</div>${materials ? `<div class="orrery-flags resource-composition">${materials}</div>` : ""}${orreryValueBlock(body)}${orreryFactsBlock(body)}`;
}

// The Planetary page lives in planetary.js (5.5.12).
const PLANETARY_UI = {
  byId, escapeHtml, showToast, command,
  syncSnapshot: () => syncSnapshot(),
  forgetFingerprint: (page) => { delete workspaceFingerprints[page]; },
};

const EXPLORE_WORKSPACE_UI = Object.freeze({
  byId, credits, escapeHtml, formatCredits, number, numeric,
  orreryDetail, percentWidth, showPage, text,
  planetKind: surveyPlanetKind,
  profileKey: () => profileKey,
  command, showToast,
  onViewChange: () => syncSystemMap(),
});

// The System Map is Explore & Survey's SYSTEM MAP tab (5.6.9): it draws only
// on that tab, and warms up while Explore is open so the tab opens ready.
function syncSystemMap() {
  setSystemMapActive(currentPage === "explore" && exploreView() === "map", currentPage === "explore");
}

function renderProfileWorkspace(data) {
  const root = byId("profile-workspace");
  const ship = data.ship || {};
  const achievements = data.achievements || {};
  const log = data.log || {};
  const rankRows = (data.ranks || []).map((row) => `<div class="progress-row"><div><b>${escapeHtml(row.category)}</b><span>${escapeHtml(row.rank)}</span></div><i><em style="width:${clamp(row.progress)}%"></em></i><strong>${row.progress === null || row.progress === undefined ? "—" : `${numeric(row.progress)}%`}</strong></div>`);
  const repRows = (data.reputation || []).map((row) => `<div class="progress-row"><div><b>${escapeHtml(row.name)}</b><span>SUPERPOWER STANDING</span></div><i><em class="orange" style="width:${clamp(row.value)}%"></em></i><strong>${numeric(row.value)}%</strong></div>`);
  const careerRows = (data.career || []).map((row) => `<div><span>${escapeHtml(row.label)}</span><b>${row.credits ? credits(row.value) : `${numeric(row.value)}${escapeHtml(row.suffix || "")}`}</b></div>`);
  const fleet = workspaceTable([
    {label: "Vessel", render: (row) => `<b>${escapeHtml(row.name)}</b><small>${escapeHtml(row.type)}</small>`},
    {label: "Location", key: "system"},
    {label: "State", render: (row) => row.in_transit ? "IN TRANSIT" : row.hot ? "HOT" : "STORED"},
    {label: "Transfer", render: (row) => row.transfer_cr ? credits(row.transfer_cr) : "—"},
  ], data.fleet || [], "Open a shipyard in Elite to synchronise stored vessels.");
  const missions = workspaceTable([
    {label: "Mission", render: (row) => `<b>${escapeHtml(row.name)}</b><small>${escapeHtml(row.kind)}</small>`},
    {label: "Destination", key: "destination"},
    {label: "Expiry", key: "expiry"},
    {label: "Reward", render: (row) => credits(row.reward)},
  ], data.missions || [], "No active mission responsibilities.");
  const surfaceVehicles = workspaceTable([
    {label: "Vehicle", render: (row) => `<b>${escapeHtml(row.name)}</b><small>${escapeHtml(row.symbol || "JOURNAL VEHICLE")}</small>`},
    {label: "ID", render: (row) => row.id ?? "—"},
    {label: "Loadout", key: "loadout"},
    {label: "Launches", key: "launches"},
    {label: "Restocks", key: "restocks"},
    {label: "Last state", render: (row) => row.destroyed ? "DESTROYED" : escapeHtml(row.last_event || "OBSERVED")},
  ], data.surface_vehicles || [], "Launch, dock or restock an SRV to establish the observed vehicle ledger.");
  // Odyssey on foot (5.5.2.8): suit, loadout, weapons, what's carried, and
  // the on-foot and exobiology record, all from the journal.
  const foot = data.on_foot || {};
  const kit = foot.loadout;
  const figure = (row) => row.unit === "cr" ? credits(row.value)
    : row.unit === "m" ? `${numeric(row.value / 1000, 1)} KM` : numeric(row.value);
  const factRows = (rows) => (rows || []).map((row) => `<div><span>${escapeHtml(row.label)}</span><b>${figure(row)}</b></div>`).join("");
  const chips = (labels) => (labels || []).map((label) => `<span class="onfoot-chip">${escapeHtml(label)}</span>`).join("");
  const kitCard = kit ? `<div class="onfoot-body"><div class="onfoot-suit"><div><span>SUIT</span><b>${escapeHtml(kit.suit)}${kit.grade ? ` <em>G${numeric(kit.grade)}</em>` : ""}</b></div>
      <div><span>LOADOUT</span><b>${escapeHtml(kit.loadout || "—")}</b></div></div>
    <div class="onfoot-chips">${chips(kit.suit_mods) || "<small>No suit modifications</small>"}</div>
    ${workspaceTable([
      {label: "Slot", key: "slot"},
      {label: "Weapon", render: (row) => `<b>${escapeHtml(row.name)}</b>`},
      {label: "Grade", render: (row) => row.grade ? `G${numeric(row.grade)}` : "—"},
      {label: "Modifications", render: (row) => chips(row.mods) || "—"},
    ], kit.weapons || [], "No weapons in this loadout.")}</div>`
    : "<p class='workspace-empty'>Your suit and loadout show here after the game logs them (at login, or when you change loadout).</p>";
  const inventory = (store, empty) => {
    const parts = [["items", "ITEMS"], ["components", "COMPONENTS"], ["consumables", "CONSUMABLES"], ["data", "DATA"]]
      .filter(([key]) => (store?.[key] || []).length)
      .map(([key, label]) => `<div class="onfoot-store"><h5>${label}</h5>${(store[key] || []).slice(0, 14).map((row) => `<div><span>${escapeHtml(row.name)}</span><b>${numeric(row.count)}</b></div>`).join("")}${(store[key] || []).length > 14 ? `<small>+${numeric(store[key].length - 14)} more</small>` : ""}</div>`);
    return parts.length ? `<div class="onfoot-body"><div class="onfoot-stores">${parts.join("")}</div></div>` : `<p class='workspace-empty'>${empty}</p>`;
  };
  root.classList.remove("loading-panel");
  root.innerHTML = `
    <section class="workspace-hero"><div><small>ACTIVE COMMANDER // ${escapeHtml(data.key)}</small><h3>${escapeHtml(data.name)}</h3><span>${escapeHtml(data.fid || "FID awaiting journal")} · ${escapeHtml(ship.name || ship.type || "No active ship")}</span></div><div><button data-ws-page="profile" data-ws-op="open_folder">OPEN PROFILE FOLDER</button><button data-ws-page="profile" data-ws-op="backup_picker">BACKUP</button><button data-ws-page="profile" data-ws-op="restore_picker">RESTORE</button></div></section>
    ${workspaceMetrics([
      {label: "Credits", value: credits(data.balance), detail: data.session_credit_delta === null ? "LIVE BALANCE" : `${data.session_credit_delta >= 0 ? "+" : ""}${credits(data.session_credit_delta)} THIS SESSION`},
      {label: "Active vessel", value: ship.name || ship.type || "—", detail: `${ship.type || "SHIP"} · ${ship.ident || "NO IDENT"}`},
      {label: "Achievements", value: `${numeric(achievements.unlocked)} / ${numeric(achievements.total)}`, detail: `${numeric(achievements.points)} POINTS`},
      {label: "Captain's Log", value: `${numeric(log.sessions)} FLIGHTS`, detail: `${numeric(log.distance, 1)} LY · ${numeric(log.jumps)} JUMPS`},
    ])}
    <section class="workspace-grid two profile-workspace-grid">
      ${workspaceCard("CAREER RANKS", workspaceRows(rankRows, "Awaiting Rank and Progress journal events."), `${rankRows.length} TRACKED`)}
      ${workspaceCard("SUPERPOWER REPUTATION", workspaceRows(repRows, "Awaiting Reputation journal data."))}
      ${workspaceCard("CAREER RECORDS", `<div class="fact-list spacious">${careerRows.join("") || "<p class='workspace-empty'>Elite will provide lifetime statistics through its Statistics event.</p>"}</div>`)}
      ${workspaceCard("ON FOOT · SUIT & LOADOUT", kitCard, kit?.ts ? `LOGGED ${escapeHtml(String(kit.ts).slice(0, 16).replace("T", " "))}` : "ODYSSEY")}
      ${workspaceCard("ON-FOOT RECORD", `<div class="fact-list spacious">${factRows(foot.record) || "<p class='workspace-empty'>Elite sends on-foot figures in its Statistics event at login.</p>"}</div>`)}
      ${workspaceCard("EXOBIOLOGY CAREER", `<div class="fact-list spacious">${factRows(foot.exobiology) || "<p class='workspace-empty'>Elite sends exobiology figures in its Statistics event at login.</p>"}</div>`)}
      ${workspaceCard("BACKPACK", inventory(foot.backpack, "Your backpack is empty, or the game hasn't logged it yet."), "ON YOU")}
      ${workspaceCard("SHIP LOCKER", inventory(foot.locker, "The ship locker shows here once the game writes it (open your locker, or log in)."), "STORED")}
      ${workspaceCard("ACTIVE SHIP & LOADOUT", `<div class="profile-ship-grid"><div><span>TYPE</span><b>${escapeHtml(ship.type || "—")}</b></div><div><span>IDENT</span><b>${escapeHtml(ship.ident || "—")}</b></div><div><span>CARGO</span><b>${numeric(ship.cargo)} T</b></div><div><span>JUMP RANGE</span><b>${numeric(ship.jump_range, 2)} LY</b></div><div><span>REBUY</span><b>${credits(ship.rebuy)}</b></div><div><span>HULL</span><b>${ship.hull === null || ship.hull === undefined ? "—" : `${numeric(Number(ship.hull) * 100, 1)}%`}</b></div></div><div class="workspace-actions"><button data-ws-page="profile" data-ws-op="open_edsy" ${data.loadout_ready ? "" : "disabled"}>OPEN IN EDSY</button><button data-ws-page="profile" data-ws-op="copy_slef" ${data.loadout_ready ? "" : "disabled"}>COPY SLEF</button></div>`, data.loadout_ready ? "EXPORT READY" : "AWAITING LOADOUT")}
      ${workspaceCard(`STORED FLEET · ${(data.fleet || []).length}`, fleet)}
      ${workspaceCard(`OBSERVED SURFACE VEHICLES · ${(data.surface_vehicles || []).length}`, surfaceVehicles, "JOURNAL OBSERVATIONS")}
      ${workspaceCard("FLEET CARRIER", `<div class="fact-list spacious"><div><span>CARRIER</span><b>${escapeHtml(data.carrier?.name || "NO OWNED CARRIER DATA")}</b></div><div><span>CALLSIGN</span><b>${escapeHtml(data.carrier?.callsign || "—")}</b></div><div><span>LOCATION</span><b>${escapeHtml(data.carrier?.system || "—")}</b></div><div><span>TRITIUM</span><b>${numeric(data.carrier?.fuel)} T</b></div></div><div class="workspace-actions"><button data-page="carrier">OPEN CARRIER COMMAND</button></div>`)}
      ${workspaceCard(`MISSION RESPONSIBILITIES · ${(data.missions || []).length}`, missions)}
      ${workspaceCard("PROFILE CUSTODY", `<div class="fact-list spacious"><div><span>PROFILE KEY</span><b>${escapeHtml(data.key)}</b></div><div><span>PROFILE FOLDER</span><b class="path-value">${escapeHtml(data.folder)}</b></div><div><span>GAME MODE</span><b>${escapeHtml(data.session?.game_mode || "UNKNOWN")}</b></div><div><span>REPAIR DRONE RECORDS</span><b>${numeric(data.session?.repair_drone_events)}</b></div><div><span>EDSM UPLOAD</span><b>${data.integrations?.edsm ? "ON" : "OFF"}</b></div><div><span>EDDN MARKET</span><b>${data.integrations?.eddn ? "ON" : "OFF"}</b></div><div><span>CARRIER DISCORD</span><b>${data.integrations?.discord ? "CONFIGURED" : "OFF"}</b></div></div>`)}
    </section>`;
}

function renderArchiveWorkspace(data) {
  renderExplorationArchive(data, {byId, credits, escapeHtml, number, numeric, workspaceTable, analyticsView, profileKey});
}

// The archive inside Explore & Survey (5.5.4): drawn again only when it changed.
let lastArchiveKey = "";
function renderExploreArchive(archive) {
  const key = JSON.stringify({...archive, current: {...(archive.current || {}), elapsed: ""}, profileKey});
  if (key === lastArchiveKey && byId("analytics-workspace")?.childElementCount) return;
  lastArchiveKey = key;
  renderArchiveWorkspace(archive);
}

function replayGeometry(replay = {}, sessionIndex = 0) {
  const points = replay.points || [];
  const session = (replay.sessions || [])[sessionIndex] || {};
  let start = Number.isInteger(session.point_start) ? session.point_start : 0;
  let end = Number.isInteger(session.point_end) ? session.point_end : Math.max(0, points.length - 1);
  start = Math.max(0, Math.min(start, Math.max(0, points.length - 1)));
  end = Math.max(start, Math.min(end, Math.max(0, points.length - 1)));
  const scoped = points.slice(start, end + 1);
  if (!scoped.length) return {start: 0, end: 0, points: [], projected: [], path: ""};
  const xs = scoped.map((row) => number(row.pos?.[0]));
  const zs = scoped.map((row) => number(row.pos?.[2]));
  const minX = Math.min(...xs), maxX = Math.max(...xs), minZ = Math.min(...zs), maxZ = Math.max(...zs);
  const span = Math.max(1, maxX - minX, maxZ - minZ);
  const projected = scoped.map((row, index) => ({
    ...row, globalIndex: start + index,
    x: 54 + (number(row.pos?.[0]) - minX) * 792 / span,
    y: 382 - (number(row.pos?.[2]) - minZ) * 330 / span,
  }));
  return {start, end, points: scoped, projected, path: projected.map((row, index) => `${index ? "L" : "M"}${row.x.toFixed(1)} ${row.y.toFixed(1)}`).join(" ")};
}

function replayMarkup(replay = {}) {
  const sessions = replay.sessions || [];
  if (replaySelectedSessionIndex >= sessions.length) replaySelectedSessionIndex = 0;
  const geometry = replayGeometry(replay, replaySelectedSessionIndex);
  const first = geometry.projected[0];
  const photos = (replay.photos || []).map((photo) => {
    const match = [...geometry.projected].reverse().find((row) => row.system === photo.system && row.epoch <= photo.epoch) || geometry.projected.find((row) => row.system === photo.system);
    return match ? `<circle class="replay-photo" cx="${match.x}" cy="${match.y}" r="4"><title>${escapeHtml(photo.body || photo.system)} · ${escapeHtml(String(photo.timestamp || "").replace("T", " ").slice(0, 16))}</title></circle>` : "";
  }).join("");
  const discoveries = geometry.projected.filter((row) => row.discoveries || row.codex || row.fss_complete).map((row) => `<circle class="replay-discovery" cx="${row.x}" cy="${row.y}" r="3"><title>${escapeHtml(row.system)} · ${row.discoveries ? `${row.discoveries} discoveries` : row.codex ? `${row.codex} Codex` : "FSS complete"}</title></circle>`).join("");
  const options = sessions.map((row, index) => `<option value="${index}" ${index === replaySelectedSessionIndex ? "selected" : ""}>${escapeHtml(String(row.started || "UNKNOWN FLIGHT").replace("T", " ").slice(0, 16))} · ${escapeHtml(row.start_system || "—")} → ${escapeHtml(row.end_system || "—")}</option>`).join("");
  return `<div class="replay-toolbar"><label>FLIGHT<select id="replay-session">${options}</select></label><div><button id="replay-play" ${geometry.points.length > 1 ? "" : "disabled"}>PLAY REPLAY</button><button data-ws-page="chronicle" data-ws-op="export_replay" data-session-index="${replaySelectedSessionIndex}" ${geometry.points.length ? "" : "disabled"}>EXPORT INTERACTIVE HTML</button></div></div><svg class="replay-chart" viewBox="0 0 900 430" role="img" aria-label="Expedition journey replay"><path class="replay-grid" d="M450 22V408M22 215H878M225 22V408M675 22V408M22 108H878M22 322H878"/><path class="replay-route" d="${geometry.path}"/>${discoveries}${photos}${first ? `<g id="replay-ship" transform="translate(${first.x} ${first.y})"><path d="M0 -9L7 8L0 5L-7 8Z"/></g>` : ""}<text x="24" y="32">${geometry.points.length ? `${geometry.points.length} RETAINED SYSTEMS` : "NO COORDINATED ROUTE IN THIS SESSION"}</text></svg><div class="replay-controls"><input id="replay-slider" type="range" min="${geometry.start}" max="${geometry.end}" value="${geometry.start}" ${geometry.points.length ? "" : "disabled"}><span id="replay-readout">${first ? `01 / ${String(geometry.points.length).padStart(2, "0")} · ${escapeHtml(first.system)}` : "AWAITING ROUTE EVIDENCE"}</span><div><i class="discovery"></i> DISCOVERY <i class="photo"></i> PHOTO</div></div>`;
}

function updateReplayCursor(globalIndex) {
  const replay = model.workspace?.page === "chronicle" ? model.workspace.data?.replay || {} : {};
  const geometry = replayGeometry(replay, replaySelectedSessionIndex);
  const localIndex = Math.max(0, Math.min(geometry.projected.length - 1, number(globalIndex) - geometry.start));
  const row = geometry.projected[localIndex];
  const ship = byId("replay-ship");
  if (!row || !ship) return;
  ship.setAttribute("transform", `translate(${row.x} ${row.y})`);
  text("replay-readout", `${String(localIndex + 1).padStart(2, "0")} / ${String(geometry.projected.length).padStart(2, "0")} · ${row.system} · ${numeric(row.jump_dist, 1)} LY`);
}

// The Captain's Log's long lists, folded until wanted (5.5.3.8); each stays
// open or shut as left, though the page is drawn again as the game goes on.
const chronicleFolds = {photos: false, discoveries: false};
document.addEventListener("toggle", (event) => {
  const fold = event.target.closest?.("[data-chronicle-fold]");
  if (fold) chronicleFolds[fold.dataset.chronicleFold] = fold.open;
}, true);

function chronicleFold(key, title, body) {
  return `<details class="chronicle-fold" data-chronicle-fold="${key}"${chronicleFolds[key] ? " open" : ""}><summary>${escapeHtml(title)}</summary>${body}</details>`;
}

function renderChronicleWorkspace(data) {
  const root = byId("chronicle-workspace");
  const sessions = data.sessions || [];
  if (replayTimer) { clearInterval(replayTimer); replayTimer = 0; }
  // Each session's own log is in the flight logs above (5.5.3.8): one list
  // of nights, each opening to its full log, instead of every card at once.
  const photos = [...(data.replay?.photos || [])].reverse().slice(0, 24);
  const photoRows = photos.map((photo) => {
    const location = [photo.system, photo.body].filter(Boolean).join(" · ") || "Location unavailable";
    const coordinates = photo.latitude === null || photo.latitude === undefined
      ? "" : ` · ${numeric(photo.latitude, 4)}°, ${numeric(photo.longitude, 4)}°`;
    const context = photo.nearby_label
      ? `${photo.nearby_label}${photo.nearby_detail ? ` · ${photo.nearby_detail}` : ""}`
      : "No nearby notable journal event retained";
    const filename = String(photo.filename || "Screenshot").split(/[\\/]/).pop();
    return `<div class="photo-chronicle-row"><i></i><p><strong>${escapeHtml(location)}</strong><span>${escapeHtml(context)}</span><small>${escapeHtml(filename)}${escapeHtml(coordinates)}</small></p><time>${escapeHtml(String(photo.timestamp || "").replace("T", " ").slice(0, 16))}</time></div>`;
  });
  // Field discoveries are each flight's own now, in its flight log (5.5.3.8).
  root.classList.remove("loading-panel");
  root.innerHTML = `${workspaceMetrics([
    {label: "Flights", value: numeric(sessions.length), detail: "PROFILE CHRONICLE"},
    {label: "Distance", value: `${numeric(sessions.reduce((sum, row) => sum + number(row.distance), 0), 1)} LY`, detail: "RETAINED TRAVEL"},
    {label: "FSS surveys", value: numeric(sessions.reduce((sum, row) => sum + number(row.fss), 0)), detail: "SYSTEM COMPLETIONS"},
    {label: "Bio analyses", value: numeric(sessions.reduce((sum, row) => sum + number(row.bio), 0)), detail: "GENETIC SAMPLES"},
  ])}<section class="workspace-grid chronicle-feature-grid">${workspaceCard("EXPEDITION REPLAY", replayMarkup(data.replay || {}), `${numeric(data.replay?.points?.length)} ROUTE POINTS`, "replay-card")}</section>${chronicleFold("photos", `SCREENSHOT CHRONICLE · ${photos.length} RECENT`, workspaceCard("SCREENSHOT CHRONICLE", `${workspaceRows(photoRows, "Screenshots will be associated with their system, body and nearby journal event.")}<div class="workspace-actions"><button data-command="open_screenshots">OPEN SCREENSHOT FOLDER</button></div>`, `${photos.length} RECENT PHOTOS`, "photo-chronicle-card"))}${sessions.length ? "" : `<p class="workspace-empty">Captain's Log will populate as journal sessions are completed.</p>`}`;
}



// The Mining page lives in mining.js (5.5.12).
function renderMiningWorkspace(data) {
  renderMining(data, WORKSHOP_UI);
}

function installPageSuites() {
  for (const suite of PAGE_SUITES) {
    for (const [pageName, pageLabel] of suite.pages) {
      const page = document.querySelector(`[data-page-name="${CSS.escape(pageName)}"]`);
      const header = page?.querySelector(":scope > .page-title, :scope > .studio-title");
      if (!page || !header || page.querySelector(":scope > .suite-tabs")) continue;
      const tabs = document.createElement("nav");
      tabs.className = "suite-tabs";
      tabs.setAttribute("aria-label", suite.label);
      tabs.innerHTML = `<span>${escapeHtml(suite.label)}</span>${suite.pages.map(([target, label]) => `<button type="button" data-page="${escapeHtml(target)}">${escapeHtml(label)}</button>`).join("")}`;
      header.insertAdjacentElement("afterend", tabs);
    }
  }
}

function navigationPage(pageName) {
  return PAGE_SUITE_BY_PAGE.get(pageName)?.parent || pageName;
}

// Settings › Diagnostics: the result of the last check, live.
function renderSettingsUpdate(update = {}) {
  const state = byId("settings-update-state");
  if (!state) return;
  const box = byId("settings-update");
  const current = update.current_version || model.app?.version || "";
  const when = (seconds) => seconds ? new Date(seconds * 1000).toLocaleString([], {dateStyle: "medium", timeStyle: "short"}) : "";
  let tone = "idle";
  let label = "NOT CHECKED";
  let detail = "Void Compass checks GitHub once when it starts.";
  if (update.checking) {
    tone = "busy"; label = "CHECKING…"; detail = "Asking GitHub for the latest release.";
  } else if (update.error && Number(update.failed_at || 0) >= Number(update.checked_at || 0)) {
    tone = "bad"; label = "CHECK FAILED"; detail = `${update.error}. Try again in a moment.`;
  } else if (update.available) {
    tone = "new"; label = `v${update.latest_version} AVAILABLE`;
    detail = `You have v${current}. Checked ${when(update.checked_at) || "this session"}.`;
  } else if (update.checked) {
    tone = "good"; label = "UP TO DATE"; detail = `v${current} is the latest release. Checked ${when(update.checked_at) || "this session"}.`;
  }
  box.dataset.tone = tone;
  state.textContent = label;
  text("settings-update-detail", detail);
  const check = document.querySelector("#settings-workspace [data-update-check]");
  if (check) {
    check.disabled = Boolean(update.checking);
    check.textContent = update.checking ? "CHECKING…" : "CHECK FOR UPDATES";
  }
  const view = byId("settings-update-view");
  if (view) view.hidden = !update.available;
}

function forgetUpdateDismissal() {
  try {
    Object.keys(sessionStorage).filter((key) => key.startsWith("voidcompass.update.dismissed.")).forEach((key) => sessionStorage.removeItem(key));
  } catch (_error) { /* storage can be unavailable */ }
}

// Asking again means the answer should show, even if it was dismissed.
document.addEventListener("click", (event) => {
  if (event.target.closest("[data-update-check]")) forgetUpdateDismissal();
  if (event.target.closest("[data-update-view]")) {
    forgetUpdateDismissal();
    renderUpdateNotice(model.update || {});
  }
});

function renderUpdateNotice(update = {}) {
  renderSettingsUpdate(update);
  const dialog = byId("release-update");
  if (!dialog) return;
  const latest = String(update.latest_version || "").trim();
  const dismissalKey = latest ? `voidcompass.update.dismissed.${latest}` : "";
  const dismissed = dismissalKey && sessionStorage.getItem(dismissalKey) === "1";
  if (!update.available || !latest || dismissed) {
    dialog.hidden = true;
    return;
  }
  dialog.dataset.version = latest;
  text("release-update-current", `INSTALLED v${update.current_version || model.app?.version || "—"}`);
  text("release-update-title", `VOID COMPASS v${latest} IS AVAILABLE`);
  text("release-update-summary", update.title || "A newer Void Compass release is ready on GitHub.");
  text("release-update-notes", update.notes || "Open the GitHub release page for downloads and the complete change log.");
  renderUpdateInstaller(update.installer || {});
  dialog.hidden = false;
}

// In-app update (5.5.2.5): INSTALL UPDATE downloads and checks the release,
// then RESTART TO UPDATE closes the app so the new version swaps itself in.
function renderUpdateInstaller(installer) {
  const install = byId("release-update-install");
  const open = byId("release-update-open");
  const progress = byId("release-update-progress");
  const state = installer.state || "idle";
  const mb = (bytes) => `${(Number(bytes || 0) / 1048576).toFixed(1)} MB`;
  install.hidden = !installer.can_install;
  open.classList.toggle("primary", !installer.can_install);
  install.disabled = state === "downloading" || state === "verifying";
  install.dataset.action = state === "ready" ? "restart_to_update" : "install_update";
  install.textContent = {downloading: "DOWNLOADING…", verifying: "CHECKING…", ready: "RESTART TO UPDATE", failed: "TRY AGAIN"}[state] || "INSTALL UPDATE";
  progress.hidden = !installer.can_install || state === "idle";
  progress.classList.toggle("failed", state === "failed");
  const total = Number(installer.total || 0);
  const share = state === "ready" || state === "verifying" ? 1 : (total ? Math.min(1, Number(installer.received || 0) / total) : 0);
  byId("release-update-bar").style.width = `${Math.round(share * 100)}%`;
  text("release-update-status", {
    downloading: `DOWNLOADING ${mb(installer.received)}${total ? ` OF ${mb(total)}` : ""}`,
    verifying: "CHECKING THE DOWNLOAD AGAINST THE RELEASE CHECKSUMS",
    ready: "READY · VOID COMPASS WILL CLOSE, UPDATE ITSELF AND OPEN AGAIN. YOUR SETTINGS AND PROFILES ARE KEPT.",
    failed: `UPDATE FAILED: ${installer.error || "unknown error"}. NOTHING WAS CHANGED; YOU CAN STILL DOWNLOAD IT FROM GITHUB.`,
  }[state] || "");
}

function dismissUpdateNotice() {
  const dialog = byId("release-update");
  const version = String(dialog?.dataset.version || "");
  if (version) sessionStorage.setItem(`voidcompass.update.dismissed.${version}`, "1");
  if (dialog) dialog.hidden = true;
}

// The BGS tab lives in bgs.js.
function renderBgsWorkspace(data) {
  renderBgs(data, WORKSHOP_UI);
}

// The Trading tab lives in trading.js.
function renderTradingWorkspace(data) {
  renderTrading(data, WORKSHOP_UI);
}

// The Colonisation tab lives in colonisation.js.
function renderColonisationWorkspace(data) {
  renderColonisation(data, WORKSHOP_UI);
}

function renderPowerplayWorkspace(data) {
  renderPowerplayOperationsWorkspace(data, {
    byId, escapeHtml, workspaceMetrics, workspaceCard, workspaceTable, numeric, credits,
  });
}

function renderCarrierWorkspace(data) {
  const root = byId("carrier-workspace");
  const carrier = data.carrier || {};
  const carriers = data.carriers || [];
  const expedition = data.expedition || {};
  const route = expedition.route || [];
  const tools = data.tools || {};
  const discord = data.discord || {};
  const discordEvents = (discord.events || []).map((row) => `<span class="${row.enabled ? "enabled" : "disabled"}">${row.enabled ? "◆" : "◇"} ${escapeHtml(row.label)}</span>`).join("");
  const routeRows = route.map((row) => `<div class="carrier-stop${row.visited ? " visited" : ""}"><button data-ws-page="carrier" data-ws-op="mark" data-index="${row.index}" data-visited="${!row.visited}">${row.visited ? "✓" : "○"}</button><span><b>${String(row.index + 1).padStart(2, "0")} · ${escapeHtml(row.system)}</b><small>${row.distance === null ? "DISTANCE UNKNOWN" : `${numeric(row.distance, 1)} LY`} · ${row.fuel === null ? "FUEL UNKNOWN" : `${numeric(row.fuel)} T`} ${row.tank_after === null ? "" : `· TANK ${numeric(row.tank_after)} T`}${row.restock ? ` · REFILL ${numeric(row.restock)} T` : ""}</small></span><div><button data-ws-page="carrier" data-ws-op="move_stop" data-index="${row.index}" data-offset="-1">↑</button><button data-ws-page="carrier" data-ws-op="move_stop" data-index="${row.index}" data-offset="1">↓</button><button class="danger-action" data-ws-page="carrier" data-ws-op="delete_stop" data-index="${row.index}">×</button></div></div>`);
  const destinations = (expedition.requested || []).length ? expedition.requested : route.map((row) => row.system);
  const tritiumRows = workspaceTable([
    {label: "System", render: (row) => `<b>${escapeHtml(row.system)}</b><small>${escapeHtml(row.body)}</small>`},
    {label: "Signals", render: (row) => numeric(row.hotspots)},
    {label: "Ring", key: "ring_type"},
    {label: "Distance", render: (row) => row.distance === null ? "—" : `${numeric(row.distance, 1)} LY`},
    {label: "Arrival", render: (row) => row.arrival === null ? "—" : `${numeric(row.arrival)} LS`},
    {label: "Reserve", key: "reserve"},
    {label: "Actions", render: (row) => `<div class="table-actions"><button data-ws-page="carrier" data-ws-op="tritium_copy" data-result-index="${row.index}">COPY</button><button data-ws-page="carrier" data-ws-op="tritium_add" data-result-index="${row.index}">ADD</button><button data-ws-page="carrier" data-ws-op="tritium_open" data-result-index="${row.index}">VIEW</button></div>`},
  ], (tools.tritium_results || []).map((row, index) => ({...row, index})), "Search from a system to find known community-reported Tritium ring signals.");
  root.dataset.carrierId = carrier.id === null || carrier.id === undefined ? "" : String(carrier.id);
  const carrierSwitcher = carriers.length ? `<section class="carrier-switcher">${carriers.map((row) => `
    <button class="${row.active ? "active" : ""}" data-ws-page="carrier" data-ws-op="select_carrier" data-carrier-id="${escapeHtml(row.id)}">
      <span>${escapeHtml(row.kind || row.type || "CARRIER")}</span>
      <b>${escapeHtml(row.name || row.callsign || "UNKNOWN CARRIER")}</b>
      <small>${escapeHtml(row.callsign || "—")} · ${escapeHtml(row.system || "LOCATION UNKNOWN")} · ${escapeHtml(String(row.status || "idle").toUpperCase())}</small>
    </button>`).join("")}</section>${carrierRemoveRow(carriers.find((row) => row.active), data.remove_armed)}` : `<p class="workspace-empty carrier-empty">No personal or Squadron Carrier record has reached this profile yet.</p>`;
  root.classList.remove("loading-panel");
  root.innerHTML = `${carrierSwitcher}${workspaceMetrics([
    {label: "Carrier", value: carrier.name || "NO CARRIER DATA", detail: carrier.callsign || carrier.type || "JOURNAL AWAITING"},
    {label: "Location", value: carrier.system || "—", detail: carrier.status || "IDLE"},
    {label: "Tritium", value: `${numeric(carrier.fuel)} / ${numeric(carrier.fuel_capacity)} T`, detail: `${numeric(carrier.jump_range)} LY RANGE`},
    {label: "Cargo capacity", value: `${numeric(carrier.space_cargo)} T`, detail: `${numeric(carrier.space_free)} T FREE`},
  ])}<section class="workspace-grid carrier-grid">
    ${workspaceCard("CARRIER STATUS", `<div class="fact-list spacious"><div><span>DESTINATION</span><b>${escapeHtml(carrier.destination || "NO JUMP PLOTTED")}</b></div><div><span>DEPARTURE</span><b>${escapeHtml(carrier.departure || "—")}</b></div><div><span>DOCKING ACCESS</span><b>${escapeHtml(carrier.access || "—")}</b></div><div><span>BALANCE</span><b>${credits(carrier.balance)}</b></div><div><span>RESERVE</span><b>${credits(carrier.reserve)}</b></div><div><span>SQUADRON</span><b>${escapeHtml(carrier.squadron || "PERSONAL / UNKNOWN")}</b></div></div>`)}
    ${workspaceCard("FUEL READINESS", `<div class="fact-list spacious"><div><span>AVAILABLE</span><b>${numeric(data.readiness?.available_t)} T</b></div><div><span>ROUTE REQUIRED</span><b>${numeric(data.readiness?.tritium_required_t)} T</b></div><div><span>RESERVE</span><b>${numeric(data.readiness?.reserve_t)} T</b></div><div><span>DEFICIT</span><b class="${number(data.readiness?.deficit_t) > 0 ? "warn-text" : "ok-text"}">${numeric(data.readiness?.deficit_t)} T</b></div><div><span>INVENTORY SOURCE</span><b>${escapeHtml(data.inventory_source || "JOURNAL EVIDENCE")}</b></div></div>`)}
    ${workspaceCard("CARRIER EXPEDITION NAVIGATOR", `<div class="carrier-plan-form"><label>ROUTE NAME<input id="carrier-route-name" value="${escapeHtml(expedition.name || "Carrier expedition")}"></label><label>RESERVE TRITIUM<input id="carrier-route-reserve" type="number" min="0" max="25000" value="${number(expedition.reserve, 200)}"></label><label class="carrier-destinations">DESTINATIONS · ONE SYSTEM PER LINE<textarea id="carrier-route-systems">${escapeHtml(destinations.join("\n"))}</textarea></label></div><div class="workspace-actions wrap"><button class="primary" data-ws-page="carrier" data-ws-op="plot_route" ${tools.route_status === "working" ? "disabled" : ""}>${tools.route_status === "working" ? "PLOTTING…" : "PLOT WITH SPANSH"}</button><button data-ws-page="carrier" data-ws-op="save_route">SAVE MANUAL ROUTE</button><button data-ws-page="carrier" data-ws-op="update_route_details">SAVE DETAILS</button><button data-ws-page="carrier" data-ws-op="open_spansh_result" ${expedition.result_url ? "" : "disabled"}>OPEN RESULT</button><button class="danger-action" data-ws-page="carrier" data-ws-op="clear_route">DELETE ROUTE</button></div><div class="carrier-import"><input id="carrier-spansh-reference" placeholder="COMPLETED SPANSH RESULT URL OR UUID"><button data-ws-page="carrier" data-ws-op="import_route" ${tools.route_status === "working" ? "disabled" : ""}>IMPORT RESULT</button></div><p class="workspace-status ${escapeHtml(tools.route_status || "ready")}">${escapeHtml(tools.route_detail || "Carrier route service ready.")}</p>${workspaceRows(routeRows, "No Carrier expedition route saved.")}<div class="carrier-route-edit"><input id="carrier-add-system" placeholder="ADD ONE SYSTEM"><button data-ws-page="carrier" data-ws-op="add_stop">ADD STOP</button><button data-ws-page="carrier" data-ws-op="copy_next">COPY NEXT</button></div>`, `${route.filter((row) => row.visited).length}/${route.length} COMPLETE`, "carrier-expedition-card")}
    ${workspaceCard("DISCORD OPERATIONS", `<div class="carrier-discord-state ${discord.configured ? "configured" : "offline"}"><i></i><span><b>${discord.configured ? "WEBHOOK CONFIGURED" : "WEBHOOK NOT CONFIGURED"}</b><small>${escapeHtml(discord.carrier_kind || "PERSONAL FLEET CARRIER")} · PROFILE-AWARE</small></span></div><div class="carrier-discord-events">${discordEvents || "<span class='disabled'>◇ AUTOMATIC EVENTS UNAVAILABLE</span>"}</div><div class="carrier-discord-form"><label>PLANNED DESTINATION<input id="carrier-discord-destination" value="${escapeHtml(discord.destination_note || "")}" placeholder="OPTIONAL DESTINATION SHOWN IN STATUS POSTS"></label><label>LOCAL DEPARTURE TIME<input id="carrier-discord-departure" placeholder="18:30 OR 26/05 18:30"></label><label class="carrier-discord-note">OPERATOR NOTE<textarea id="carrier-discord-note" placeholder="OPTIONAL EXPEDITION OR CARRIER STATUS NOTE">${escapeHtml(discord.operator_note || "")}</textarea></label></div><p class="workspace-status ${escapeHtml(discord.status || "ready")}">${escapeHtml(discord.detail || "Carrier Discord operations ready.")}</p><div class="workspace-actions wrap"><button data-ws-page="carrier" data-ws-op="save_discord_details">SAVE POST DETAILS</button><button class="primary" data-ws-page="carrier" data-ws-op="discord_status" ${discord.configured ? "" : "disabled"}>POST CARRIER STATUS</button><button data-page="settings">CONFIGURE WEBHOOK</button></div>`, discord.configured ? "CONNECTED" : "SETUP REQUIRED")}
    ${workspaceCard("TRITIUM HOTSPOT FINDER", `<div class="tritium-search-form"><label>SEARCH FROM<input id="tritium-reference" value="${escapeHtml(carrier.system || "")}"></label><label>RANGE LY<input id="tritium-range" type="number" min="1" value="300"></label><button data-ws-page="carrier" data-ws-op="tritium_search" ${tools.tritium_status === "working" ? "disabled" : ""}>${tools.tritium_status === "working" ? "SEARCHING…" : "SEARCH SPANSH"}</button></div><p class="workspace-status ${escapeHtml(tools.tritium_status || "ready")}">${escapeHtml(tools.tritium_detail || "Search known community ring signals.")}</p>${tritiumRows}`, `${numeric((tools.tritium_results || []).length)} RESULTS`)}
    ${workspaceCard("CARGO EVIDENCE", workspaceTable([{label: "Commodity", key: "name"}, {label: "Quantity", render: (row) => `${numeric(row.count)} T`}, {label: "Symbol", key: "symbol"}], data.inventory || [], "No Carrier manifest baseline has been observed."), `${(data.inventory || []).length} COMMODITIES`)}
    ${workspaceCard("INSTALLED SERVICES", workspaceTable([{label: "Service", key: "role"}, {label: "Crew", key: "name"}, {label: "State", render: (row) => row.enabled ? "ACTIVE" : row.active ? "SUSPENDED" : "INACTIVE"}], data.services || [], "CarrierStats has not supplied service records."))}
    ${workspaceCard("TRADE ORDERS", workspaceTable([{label: "Commodity", key: "name"}, {label: "Side", key: "side"}, {label: "Quantity", key: "quantity"}, {label: "Price", render: (row) => credits(row.price_cr)}], data.orders || [], "No active Carrier trade orders."))}
    ${workspaceCard("JUMP HISTORY", workspaceTable([{label: "System", key: "system"}, {label: "When", key: "timestamp"}, {label: "Fuel", render: (row) => row.fuel === null ? "—" : `${numeric(row.fuel)} T`}], [...(data.jump_history || [])].reverse(), "Carrier jumps will be retained here."))}
  </section>`;
}

function renderReconWorkspace(data) {
  const root = byId("recon-workspace");
  const report = data.report || {};
  const gaps = (report.gaps || []).map((row) => `<div class="recon-gap"><i></i><span>${escapeHtml(typeof row === "string" ? row : row.detail || row.title || row.kind || JSON.stringify(row))}</span></div>`);
  const candidates = workspaceTable([{label: "System", key: "system"}, {label: "Score", render: (row) => `${numeric(row.score)}/100`}, {label: "Grade", key: "grade"}, {label: "Saved", key: "saved"}, {label: "", render: (row) => `<button class="row-delete" data-ws-page="recon" data-ws-op="delete_candidate" data-system="${escapeHtml(row.system)}">×</button>`}], data.candidates || [], "No recon candidates saved.");
  root.classList.remove("loading-panel");
  root.innerHTML = `${workspaceMetrics([
    {label: "Current system", value: report.system || "UNKNOWN", detail: "RECON TARGET"},
    {label: "Readiness", value: `${numeric(report.score)} / 100`, detail: String(report.grade || "UNKNOWN").toUpperCase()},
    {label: "Survey gaps", value: numeric((report.gaps || []).length), detail: "REMAINING CHECKS"},
    {label: "Retained candidates", value: numeric((data.candidates || []).length), detail: `${numeric((data.revisits || []).length)} REVISITS`},
  ])}<section class="workspace-grid two">${workspaceCard("CURRENT ASSESSMENT", `<div class="recon-score"><strong>${numeric(report.score)}</strong><span>/100<br>${escapeHtml(String(report.grade || "unknown").toUpperCase())}</span></div>${workspaceRows(gaps, "This system has no identified survey gaps.")}<div class="workspace-actions"><button data-ws-page="recon" data-ws-op="copy_report">COPY DOSSIER</button><button data-ws-page="recon" data-ws-op="save">SAVE CANDIDATE</button></div>`)}${workspaceCard("SAVED CANDIDATES", candidates)}${workspaceCard("REVISIT QUEUE", workspaceTable([{label: "System", key: "system"}, {label: "Reason", render: (row) => escapeHtml(row.reason || row.detail || row.grade || "Missed opportunity")}, {label: "", render: (row) => `<button data-ws-page="recon" data-ws-op="dismiss_revisit" data-system="${escapeHtml(row.system)}">DISMISS</button>`}], data.revisits || [], "No unresolved revisit opportunities."))}${workspaceCard("EXPLORATION MILESTONES", workspaceTable([{label: "When", key: "timestamp"}, {label: "Milestone", render: (row) => escapeHtml(row.title || row.kind || row.detail || "Milestone")}, {label: "System", key: "system"}], data.milestones || [], "Milestones will appear as the exploration record grows."))}</section>`;
}

function achievementPercent(row) {
  return row.unlocked ? 100 : number(row.target) > 0
    ? clamp(number(row.current) * 100 / number(row.target)) : 0;
}

function achievementState(row) {
  if (row.unlocked) return "earned";
  return number(row.current) > 0 && number(row.target) > 0 ? "active" : "locked";
}

function achievementDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString(undefined, {
    timeZone: "UTC", day: "numeric", month: "short", year: "numeric",
  }).toUpperCase();
}

function achievementTile(row) {
  const state = achievementState(row);
  const percent = achievementPercent(row);
  const hasTarget = number(row.target) > 0;
  const current = Math.max(0, number(row.current));
  const target = Math.max(0, number(row.target));
  const progressText = row.unlocked ? "COMPLETE" : hasTarget
    ? `${numeric(Math.min(current, target))} / ${numeric(target)}` : "DISCOVERY MILESTONE";
  const earnedDate = achievementDate(row.unlocked_at);
  const symbol = String(row.category || "M").trim().slice(0, 2).toUpperCase();
  return `<article class="achievement-tile ${state}">
    <div class="achievement-tile-head"><span class="achievement-category-mark" aria-hidden="true">${escapeHtml(symbol)}</span><span class="achievement-tile-category">${escapeHtml(row.category || "Milestone")}</span><b>${numeric(row.points)} <small>PTS</small></b></div>
    <div class="achievement-tile-body"><span class="achievement-state"><i aria-hidden="true"></i>${state === "earned" ? "EARNED" : state === "active" ? "IN PROGRESS" : "UNDISCOVERED"}</span><h3>${escapeHtml(row.title || "Untitled milestone")}</h3><p>${escapeHtml(row.description || "Journal-driven commander milestone.")}</p></div>
    <div class="achievement-progress"><div><span>${progressText}</span><b>${hasTarget || row.unlocked ? `${numeric(percent)}%` : ""}</b></div><i role="progressbar" aria-label="${escapeHtml(row.title || "Milestone")} progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(percent)}"><em style="width:${percent}%"></em></i></div>
    <footer><span>${state === "earned" ? `UNLOCKED${earnedDate ? ` · ${earnedDate}` : ""}` : state === "active" ? "JOURNAL PROGRESS" : "AWAITING JOURNAL EVENT"}</span><div>${row.unlocked ? "" : `<button type="button" data-ws-page="achievements" data-ws-op="manual_unlock" data-achievement-id="${escapeHtml(row.id)}">MARK EARNED</button>`}<button type="button" class="danger-action" data-ws-page="achievements" data-ws-op="reset" data-achievement-id="${escapeHtml(row.id)}" ${row.unlocked || current > 0 ? "" : "disabled"}>RESET</button></div></footer>
  </article>`;
}

function renderAchievementCatalogue(data) {
  const rows = Array.isArray(data.achievements) ? data.achievements : [];
  const categories = new Map();
  rows.forEach((row) => {
    const category = String(row.category || "Milestone");
    categories.set(category, (categories.get(category) || 0) + 1);
  });
  if (achievementUi.category !== "all" && !categories.has(achievementUi.category)) achievementUi.category = "all";
  const categoryOptions = [...categories].sort(([a], [b]) => a.localeCompare(b));
  byId("achievement-categories").innerHTML = [["all", rows.length], ...categoryOptions].map(([name, count]) => `<button type="button" data-achievement-category="${escapeHtml(name)}" aria-pressed="${achievementUi.category === name}">${name === "all" ? "ALL FIELDS" : escapeHtml(name)} <b>${numeric(count)}</b></button>`).join("");
  const search = achievementUi.search.trim().toLocaleLowerCase();
  const scoped = rows.filter((row) => (achievementUi.category === "all" || String(row.category || "Milestone") === achievementUi.category)
    && (!search || [row.title, row.description, row.category].some((value) => String(value || "").toLocaleLowerCase().includes(search))));
  const counts = {all: scoped.length, earned: 0, active: 0, locked: 0};
  scoped.forEach((row) => { counts[achievementState(row)] += 1; });
  byId("achievement-states").innerHTML = [["all", "ALL"], ["active", "IN PROGRESS"], ["earned", "EARNED"], ["locked", "UNDISCOVERED"]].map(([state, label]) => `<button type="button" data-achievement-state="${state}" aria-pressed="${achievementUi.status === state}">${label} <b>${numeric(counts[state])}</b></button>`).join("");
  const filtered = scoped.filter((row) => achievementUi.status === "all" || achievementState(row) === achievementUi.status);
  const originalOrder = new Map(rows.map((row, index) => [row.id, index]));
  filtered.sort((a, b) => {
    if (achievementUi.sort === "points") return number(b.points) - number(a.points) || (originalOrder.get(a.id) || 0) - (originalOrder.get(b.id) || 0);
    if (achievementUi.sort === "recent") return String(b.unlocked_at || "").localeCompare(String(a.unlocked_at || "")) || (originalOrder.get(a.id) || 0) - (originalOrder.get(b.id) || 0);
    if (achievementUi.sort === "progress") {
      const rank = {active: 0, earned: 1, locked: 2};
      const difference = rank[achievementState(a)] - rank[achievementState(b)];
      if (difference) return difference;
      if (achievementState(a) === "active") return achievementPercent(b) - achievementPercent(a) || number(b.current) - number(a.current);
      if (a.unlocked && b.unlocked) return String(b.unlocked_at || "").localeCompare(String(a.unlocked_at || ""));
    }
    return (originalOrder.get(a.id) || 0) - (originalOrder.get(b.id) || 0);
  });
  const visible = filtered.slice(0, achievementUi.visible);
  byId("achievement-results").textContent = `${numeric(filtered.length ? visible.length : 0)} OF ${numeric(filtered.length)} MILESTONES`;
  byId("achievement-grid").innerHTML = visible.map(achievementTile).join("") || `<div class="achievement-empty"><span aria-hidden="true">◇</span><b>${rows.length ? "NO MILESTONES MATCH" : "CATALOGUE UNAVAILABLE"}</b><p>${rows.length ? "Try another field, status or search term." : "The milestone catalogue could not be loaded for this profile."}</p></div>`;
  const more = byId("achievement-more");
  more.hidden = visible.length >= filtered.length;
  more.textContent = `SHOW MORE · ${numeric(filtered.length - visible.length)} REMAINING`;
}

function renderAchievementsWorkspace(data) {
  const root = byId("achievements-workspace");
  const rows = Array.isArray(data.achievements) ? data.achievements : [];
  const total = Math.max(0, number(data.total));
  const unlocked = Math.max(0, Math.min(total, number(data.unlocked)));
  const percent = total ? clamp(unlocked * 100 / total) : 0;
  const active = rows.filter((row) => achievementState(row) === "active")
    .sort((a, b) => achievementPercent(b) - achievementPercent(a) || number(a.target) - number(b.target))[0];
  const latest = rows.filter((row) => row.unlocked)
    .sort((a, b) => String(b.unlocked_at || "").localeCompare(String(a.unlocked_at || "")))[0];
  const activePercent = active ? achievementPercent(active) : 0;
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="achievement-dashboard">
    <section class="achievement-overview" aria-label="Commander achievement record">
      <div class="achievement-overview-head"><span>VOID COMPASS <i>／</i> COMMANDER RECORD</span><b class="${data.enabled ? "" : "paused"}">${data.enabled ? "TRACKING ACTIVE" : "TRACKING PAUSED"}</b></div>
      <div class="achievement-overview-main"><div class="achievement-dial" style="--achievement-complete:${percent}%" role="img" aria-label="${numeric(percent, 1)} percent of milestones earned"><div><strong>${numeric(percent, 1)}<small>%</small></strong><span>COMPLETE</span></div></div><div class="achievement-overview-copy"><span class="achievement-kicker">FIELD HONOURS</span><h3>Your journey, recorded.</h3><p>Every discovery, expedition and hard won first adds to this commander record.</p><div class="achievement-overview-count"><strong>${numeric(unlocked)}</strong><span>OF ${numeric(total)}<br>MILESTONES EARNED</span></div></div></div>
      <div class="achievement-overview-stats"><div><span>ACHIEVEMENT POINTS</span><strong>${numeric(data.points)}</strong></div><div><span>IN PROGRESS</span><strong>${numeric(rows.filter((row) => achievementState(row) === "active").length)}</strong></div><div><span>FIELDS OF DISCOVERY</span><strong>${numeric((data.categories || []).length)}</strong></div></div>
    </section>
    <div class="achievement-side"><section class="achievement-spotlight"><span class="achievement-kicker">NEXT ON THE HORIZON</span><div class="achievement-spotlight-emblem" aria-hidden="true">✦</div><h3>${escapeHtml(active?.title || "The next milestone awaits")}</h3><p>${escapeHtml(active?.description || "Keep exploring. Your journal will chart the way to the next unlock.")}</p><div class="achievement-spotlight-progress"><span>${active ? `${numeric(Math.max(0, number(active.current)))} / ${numeric(Math.max(0, number(active.target)))}` : "NO ACTIVE MILESTONE"}</span><b>${active ? `${numeric(activePercent)}%` : ""}</b></div><i class="achievement-spotlight-bar"><em style="width:${activePercent}%"></em></i></section>
      <section class="achievement-latest"><span class="achievement-kicker">LATEST UNLOCK</span><strong>${escapeHtml(latest?.title || "Your story starts here")}</strong><small>${latest ? `${escapeHtml(latest.category || "MILESTONE")} · ${numeric(latest.points)} PTS${achievementDate(latest.unlocked_at) ? ` · ${achievementDate(latest.unlocked_at)}` : ""}` : "Earn a milestone to begin your record."}</small></section></div>
    <section class="achievement-preferences" aria-label="Achievement settings"><div><span>RECORD SIGNALS</span><small>Profile settings for progress tracking and unlock notices.</small></div><div class="achievement-preference"><span><i class="${data.enabled ? "on" : ""}"></i>TRACKING ${data.enabled ? "ON" : "OFF"}</span><button type="button" data-ws-page="achievements" data-ws-op="set_enabled" data-enabled="${!data.enabled}">${data.enabled ? "PAUSE" : "RESUME"}</button></div><div class="achievement-preference"><span><i class="${data.notifications_enabled ? "on" : ""}"></i>UNLOCK NOTICES ${data.notifications_enabled ? "ON" : "OFF"}</span><button type="button" data-ws-page="achievements" data-ws-op="set_notifications" data-enabled="${!data.notifications_enabled}">${data.notifications_enabled ? "MUTE" : "ENABLE"}</button></div></section>
    <section class="achievement-archive" aria-label="Achievement catalogue"><div class="achievement-archive-head"><div><span class="achievement-kicker">THE ARCHIVE</span><h3>Milestone catalogue</h3><p>Follow the milestones still ahead, or revisit what you have earned.</p></div><span id="achievement-results" role="status" aria-live="polite"></span></div>
      <div class="achievement-catalogue-controls"><label for="achievement-filter">FIND A MILESTONE<input id="achievement-filter" type="search" autocomplete="off" placeholder="Search title, field or description" value="${escapeHtml(achievementUi.search)}"></label><label for="achievement-sort">ORDER BY<select id="achievement-sort"><option value="progress" ${achievementUi.sort === "progress" ? "selected" : ""}>Closest progress</option><option value="catalogue" ${achievementUi.sort === "catalogue" ? "selected" : ""}>Catalogue order</option><option value="recent" ${achievementUi.sort === "recent" ? "selected" : ""}>Recently earned</option><option value="points" ${achievementUi.sort === "points" ? "selected" : ""}>Highest points</option></select></label></div>
      <div id="achievement-categories" class="achievement-categories" role="group" aria-label="Filter by field"></div><div id="achievement-states" class="achievement-states" role="group" aria-label="Filter by status"></div><div id="achievement-grid" class="achievement-grid"></div><button id="achievement-more" type="button" class="achievement-more"></button>
    </section>
  </div>`;
  renderAchievementCatalogue(data);
}

function renderLedgerWorkspace(data) {
  const root = byId("ledger-workspace");
  const rows = data.rows || [];
  root.classList.remove("loading-panel");
  root.innerHTML = `${workspaceMetrics([{label: "Valuable bodies", value: numeric(rows.length), detail: "PROFILE INDEX"}, {label: "Retained estimate", value: credits(data.total), detail: "CURRENT SCAN EVIDENCE"}, {label: "Mapped", value: numeric(rows.filter((row) => row.mapped).length), detail: "DSS COMPLETE"}, {label: "Terraformable", value: numeric(rows.filter((row) => (row.flags || []).includes("Terraformable")).length), detail: "HIGH VALUE"}])}<section class="card ledger-card"><header><span>VALUABLE WORLD INDEX</span><input id="ledger-filter" placeholder="FILTER SYSTEM, BODY OR CLASS"></header><div id="ledger-table">${workspaceTable([{label: "System", key: "system"}, {label: "Body", key: "body"}, {label: "Class", key: "class"}, {label: "Value", render: (row) => `<b>${credits(row.value)}</b>`}, {label: "Mapped", render: (row) => row.mapped ? "YES" : "NO"}, {label: "Flags", render: (row) => escapeHtml((row.flags || []).join(" · "))}], rows, "No valuable bodies are indexed for this profile yet.")}</div></section>`;
  root.dataset.rows = JSON.stringify(rows);
}

// ------------------------------------------------------------- settings --
// Settings save one control at a time as it changes, as Overlay Studio does;
// there is no Save button. One section shows at a time, chosen from the rail,
// and the find box searches every setting in every section. The command
// channel answers before Python applies a save, so each save carries an id
// and the next snapshot's last_save says whether it was kept.
const SETTINGS_SECTIONS = [
  {id: "journal", title: "Journal & files", heading: "Journal & files", category: "FLIGHT RECORDS", detail: "Connect your flight journals and screenshots. Every discovery begins with a good record."},
  {id: "appearance", title: "Appearance", heading: "Make yourself at home", category: "PRESENTATION", detail: "Choose your palette, find a comfortable text size and make the deck your own."},
  {id: "flight", title: "Flight & exploration", heading: "Flight & exploration", category: "FIELD PREFERENCES", detail: "Tune the helpers that travel with you, from fuel warnings to your next expedition."},
  {id: "hotkeys", title: "Hotkeys", heading: "A shortcut to your cockpit", category: "COMMAND INPUT", detail: "Keep your hands on the controls. These shortcuts work while Elite Dangerous has focus."},
  {id: "galnet", title: "Galnet", heading: "A signal from the Bubble", category: "NEWS RELAY", detail: "Choose how often the news arrives and how headlines move through your deck."},
  {id: "integrations", title: "Integrations", heading: "Connections you choose", category: "EXTERNAL SERVICES", detail: "Manage community services, sharing and your local API. Each connection has its own controls."},
  {id: "diagnostics", title: "Diagnostics & recovery", heading: "Keep the compass steady", category: "SYSTEM CARE", detail: "Check the runtime, collect a useful report and look after this commander's local history."},
  {id: "updates", title: "Updates", heading: "Ready for the next leg", category: "RELEASE CHANNEL", detail: "Your installed version, the latest check and a clear path to the next release."},
];
let settingsSection = "journal";
let settingsSaveSequence = 0;
const settingsPendingSaves = new Map();
let settingsWorkshopOpen = false;

const settingSearchText = (...parts) => escapeHtml(parts.filter(Boolean).join(" ").toLocaleLowerCase());

// Native schematics stay sharp when the deck's text or window scale changes.
function settingsIcon(id) {
  const paths = {
    journal: '<path d="M6 3h10l3 3v15H6zM15 3v5h4M9 12h7M9 16h5"/>',
    appearance: '<path d="M3 6h18M3 12h18M3 18h18"/><path d="M7 3v6M16 9v6M10 15v6" stroke-width="3"/>',
    flight: '<path d="m12 2 9 18-9-4-9 4zM12 2v14"/>',
    hotkeys: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M5 9h2m3 0h2m3 0h2M5 13h2m3 0h2m3 0h4M7 16h10"/>',
    galnet: '<path d="M12 5v15M7 20h10M8 8a6 6 0 0 0 0 8m8-8a6 6 0 0 1 0 8M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14"/><circle cx="12" cy="10" r="2"/>',
    integrations: '<rect x="8" y="8" width="8" height="8"/><path d="M12 2v6M12 16v6M2 12h6M16 12h6M5 5l3 3m8 8 3 3M5 19l3-3m8-8 3-3"/>',
    diagnostics: '<path d="M2 12h5l3-8 4 16 3-8h5"/>',
    updates: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  };
  return `<svg class="settings-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[id] || paths.journal}</svg>`;
}

const SETTINGS_GROUP_NOTES = {
  JOURNAL: "The source of your flight history.", SCREENSHOTS: "Bring your captures into the journey.",
  THEME: "A different atmosphere, applied as soon as you choose it.", DISPLAY: "Comfortable reading, at your preferred scale.",
  FLIGHT: "Small helps for the next jump.", EXPEDITIONS: "Choose what matters on the long route.",
  HOME: "A familiar point to measure the distance from.", "COMMAND DECK": "How the dashboard follows your flight.",
  ACHIEVEMENTS: "Milestones earned along the way.", SHORTCUTS: "Record a combination, clear it, or return to the defaults.",
  RELAY: "A connection to Frontier's Galnet feed.", "NEWS BAR": "Set the pace of your headlines.",
  EDSM: "Your exploration record in the community atlas.", INARA: "Your commander, ships and activity on Inara.",
  "RAVEN COLONIAL": "Keep your colonisation team in the loop.", BGS: "Online reference data for the background simulation.",
  TRADING: "Market and route searches when you ask for them.", EDDN: "Contribute the markets you visit to the network.",
  "LOCAL API": "Connect your own tools and devices.", DISCORD: "Carrier and expedition updates for your channel.",
  DIAGNOSTICS: "Useful evidence when something needs attention.", RECOVERY: "Checkpoints and backups for this commander.",
  "JOURNAL CACHE": "Rebuild the local exploration archive from your journals.",
};

function settingFlag() {
  return `<em class="setting-flag" aria-live="polite"></em>`;
}

function settingSwitch({key = "", id = "", label, detail = "", checked, attrs = ""}) {
  const target = key ? ` data-setting="${escapeHtml(key)}"` : "";
  return `<label class="setting-row switch" data-search="${settingSearchText(label, detail, key)}"><span class="setting-copy"><b>${escapeHtml(label)}</b>${detail ? `<small>${escapeHtml(detail)}</small>` : ""}</span><span class="setting-control"><input type="checkbox"${id ? ` id="${escapeHtml(id)}"` : ""}${target} ${checked ? "checked" : ""}${attrs}><i class="setting-switch" aria-hidden="true"></i></span>${settingFlag()}</label>`;
}

function settingSelect({key, label, detail = "", value, options, type = "text"}) {
  const choices = options.map(([option, text]) => `<option value="${escapeHtml(option)}" ${String(option) === String(value) ? "selected" : ""}>${escapeHtml(text)}</option>`).join("");
  return `<label class="setting-row" data-search="${settingSearchText(label, detail, key, options.map((item) => item[1]).join(" "))}"><span class="setting-copy"><b>${escapeHtml(label)}</b>${detail ? `<small>${escapeHtml(detail)}</small>` : ""}</span><span class="setting-control"><select data-setting="${escapeHtml(key)}" data-setting-type="${escapeHtml(type)}">${choices}</select></span>${settingFlag()}</label>`;
}

function settingText({key, id = "", label, detail = "", value, secret = false, browse = false, status = null, placeholder = ""}) {
  const chip = status ? `<span class="setting-status ${escapeHtml(status.tone)}">${escapeHtml(status.text)}</span>` : "";
  const tools = [
    browse ? `<button type="button" data-settings-browse="${escapeHtml(key)}">BROWSE</button>` : "",
    secret ? `<button type="button" data-settings-reveal aria-pressed="false">SHOW</button>` : "",
  ].join("");
  const fieldId = id || `setting-${key}`;
  return `<div class="setting-row wide" data-search="${settingSearchText(label, detail, key)}"><label class="setting-copy" for="${escapeHtml(fieldId)}"><b>${escapeHtml(label)}</b>${detail ? `<small>${escapeHtml(detail)}</small>` : ""}</label>${chip}<span class="setting-control"><input id="${escapeHtml(fieldId)}" type="${secret ? "password" : "text"}" data-setting="${escapeHtml(key)}" value="${escapeHtml(value ?? "")}" placeholder="${escapeHtml(placeholder)}" autocomplete="off" spellcheck="false">${tools}</span>${settingFlag()}</div>`;
}

function settingActions(buttons, search = "") {
  return `<div class="setting-row actions" data-search="${settingSearchText(search)}">${buttons}</div>`;
}

function settingNote(textValue, id = "") {
  return `<p class="setting-note"${id ? ` id="${escapeHtml(id)}"` : ""}>${escapeHtml(textValue)}</p>`;
}

function settingGroup(title, body) {
  const note = SETTINGS_GROUP_NOTES[title.toUpperCase()];
  return `<div class="settings-group" data-settings-group="${layoutSlug(title)}"><header class="settings-group-head"><h4>${escapeHtml(title)}</h4>${note ? `<p>${escapeHtml(note)}</p>` : ""}</header>${body}</div>`;
}

function settingsSummaries(data) {
  const value = data.values || {};
  const journal = data.paths?.journal || {};
  const galnet = data.galnet || {};
  const bound = (data.hotkeys || []).filter((row) => row.value).length;
  return {
    journal: journal.exists ? `JOURNAL LINKED · ${numeric(journal.logs)} LOGS` : "JOURNAL FOLDER NOT FOUND",
    appearance: String(data.theme_editor?.name || "Void Cyan").toUpperCase(),
    flight: `LOW FUEL AT ${Math.round(number(value.low_fuel_threshold_pct, .25) * 100)}%`,
    hotkeys: value.overlay_hotkeys_enabled ? `${numeric(bound)} BOUND` : "HOTKEYS OFF",
    galnet: value.galnet_enabled ? `${String(galnet.status || "standby").toUpperCase()} · ${numeric((galnet.articles || []).length)} DISPATCHES` : "RELAY OFF",
    integrations: [value.edsm_upload_enabled ? "EDSM ON" : "EDSM OFF", value.inara_upload_enabled ? "INARA ON" : "INARA OFF", value.eddn_market_upload_enabled ? "EDDN ON" : "EDDN OFF", value.api_enabled ? "API ON" : "API OFF"].join(" · "),
    diagnostics: String(data.health?.level || "NOMINAL").toUpperCase(),
    updates: "NEW RELEASES FROM GITHUB",
  };
}

function settingsSectionBody(id, data) {
  const value = data.values || {};
  const paths = data.paths || {};
  const galnet = data.galnet || {};
  const health = data.health || {};
  const editor = data.theme_editor || {};
  if (id === "journal") {
    const journal = paths.journal || {};
    const journalStatus = journal.exists
      ? {tone: "good", text: `${numeric(journal.logs)} JOURNALS${journal.latest ? ` · LATEST ${journal.latest.replace(/^Journal\./, "").replace(/\.log$/, "")}` : ""}`}
      : {tone: "bad", text: "FOLDER NOT FOUND"};
    const shotsStatus = paths.screenshots?.exists ? {tone: "good", text: "FOLDER FOUND"} : {tone: "bad", text: "FOLDER NOT FOUND"};
    return settingGroup("JOURNAL", `${settingText({key: "journal_path", id: "setting-journal", label: "Journal folder", detail: "The folder holding Frontier's Journal.*.log files. Void Compass only ever reads it. A new folder is watched straight away, from the end of its newest journal.", value: value.journal_path, browse: true, status: journalStatus})}`)
      + settingGroup("SCREENSHOTS", `${settingText({key: "screenshots_path", id: "setting-screenshots", label: "Screenshot folder", detail: "Where Elite saves its BMP screenshots.", value: value.screenshots_path, browse: true, status: shotsStatus})}${settingSwitch({key: "screenshots_enabled", label: "Convert screenshots to PNG", detail: "Watch the screenshot folder and convert each new BMP.", checked: value.screenshots_enabled})}<p class="setting-note">How postcards look, keeping them as pictures, their folder and caption files: the Postcards page.</p>${settingActions(`<button type="button" data-command="open_screenshots">OPEN SCREENSHOTS</button><button type="button" data-command="open_postcards">OPEN POSTCARDS</button><button type="button" data-page="screenshots">SCREENSHOTS</button><button type="button" data-page="postcards">POSTCARDS</button>`, "open screenshots postcards album caption style gallery")}`);
  }
  if (id === "appearance") {
    const cards = (data.themes || []).map((theme) => {
      const swatch = theme.swatch || {};
      const style = ["bg", "panel", "border", "accent", "orange", "green", "yellow", "red", "text"]
        .filter((key) => /^#[0-9a-f]{6}$/i.test(swatch[key] || "")).map((key) => `--t-${key}:${swatch[key]}`).join(";");
      const active = theme.name === editor.name;
      return `<button type="button" class="theme-option${active ? " active" : ""}" data-theme-name="${escapeHtml(theme.name)}" style="${escapeHtml(style)}" aria-pressed="${active}"><span class="theme-preview" aria-hidden="true"><i></i><i></i><i></i><i></i></span><b>${escapeHtml(theme.name)}</b><small>${active ? "ACTIVE" : theme.custom ? "CUSTOM" : "BUILT IN"}</small></button>`;
    }).join("");
    const colors = (editor.keys || []).map((key) => `<label><span>${escapeHtml(key.replaceAll("_", " "))}</span><input type="color" data-theme-color="${escapeHtml(key)}" value="${escapeHtml(editor.palette?.[key] || "#000000")}"></label>`).join("");
    return settingGroup("THEME", `<div class="theme-options" data-search="${settingSearchText("theme palette colour color", (data.themes || []).map((theme) => theme.name).join(" "))}">${cards}</div>`)
      + settingGroup("DISPLAY", `${settingSelect({key: "ui_text_scale_percent", label: "Text size", detail: "Makes all the deck's text bigger, keeping the layout as it is.", value: number(value.ui_text_scale_percent, 100), options: [[100, "Standard"], [110, "110%"], [120, "120%"], [135, "135%"], [150, "150%"]], type: "number"})}${settingSelect({key: "ui_text_min_px", label: "Smallest text", detail: "Raises the small labels to at least this size and leaves the headings alone. The easiest fix if the fine print is hard to read.", value: number(value.ui_text_min_px, 0), options: [[0, "As designed"], [10, "10 px"], [11, "11 px"], [12, "12 px"], [13, "13 px"], [14, "14 px"]], type: "number"})}${settingSelect({key: "overlay_text_scale_percent", label: "Overlay text size", detail: "Text on every cockpit overlay. Overlays grow to fit it; one overlay can have its own size in Overlay Studio.", value: number(value.overlay_text_scale_percent, 100), options: [75, 90, 100, 110, 125, 140, 160, 180, 200].map((item) => [item, item === 100 ? "Standard" : `${item}%`]), type: "number"})}${settingSelect({key: "ui_scale_percent", label: "Command deck scale", detail: "Zooms everything in this window, text, panels and maps, as Ctrl+ does in a browser. Less fits on screen.", value: number(value.ui_scale_percent, 100), options: [90, 100, 110, 125, 140, 160].map((item) => [item, `${item}%`]), type: "number"})}${settingSwitch({key: "reduced_motion_enabled", label: "Reduced motion", detail: "Still frames instead of animation on the deck and every overlay.", checked: value.reduced_motion_enabled})}`)
      + `<details class="settings-group theme-workshop"${settingsWorkshopOpen ? " open" : ""} data-search="${settingSearchText("theme workshop custom palette colours colors")}"><summary><span class="theme-workshop-label"><h4>THEME WORKSHOP</h4><small>Build a palette of your own.</small></span><span>${numeric((editor.custom || []).length)} CUSTOM</span></summary><div class="theme-workshop-body"><div class="theme-workshop-head"><label>NAME<input id="custom-theme-name" value="${escapeHtml((editor.custom || []).includes(editor.name) ? editor.name : `${editor.name || "Void"} Custom`)}"></label><label>DELETE A CUSTOM THEME<select id="custom-theme-existing"><option value="">CHOOSE ONE</option>${(editor.custom || []).map((name) => `<option>${escapeHtml(name)}</option>`).join("")}</select></label></div><p class="setting-note">Starts from the active theme. Change any colour, then save it as your own.</p><div class="theme-colour-grid">${colors}</div><div class="setting-row actions"><button type="button" data-ws-page="settings" data-ws-op="save_theme">SAVE & APPLY</button><button type="button" class="danger-action" data-ws-page="settings" data-ws-op="delete_theme">DELETE SELECTED</button></div></div></details>`;
  }
  if (id === "flight") {
    return settingGroup("FLIGHT", `${settingSelect({key: "low_fuel_threshold_pct", label: "Low fuel warning", detail: "Warn when the main tank falls below this.", value: String(number(value.low_fuel_threshold_pct, .25)), options: [.1, .15, .2, .25, .3, .4, .5].map((item) => [String(item), `${Math.round(item * 100)}%`]), type: "number"})}${settingSwitch({key: "auto_copy_waypoint", label: "Auto-copy the next waypoint", detail: "As you arrive in a system, your next saved waypoint goes on the clipboard, ready to paste into the galaxy map. Also on the Command Deck, under COPY NEXT DESTINATION.", checked: value.auto_copy_waypoint})}`)
      + settingGroup("EXPEDITIONS", settingSelect({key: "expedition_risk_cr", label: "Data at risk", detail: "On an expedition, a nudge (and a word from the Watcher) each time the unsold data aboard passes another step of this.", value: String(number(value.expedition_risk_cr, 100000000)), options: [["0", "Off"], ["25000000", "25 M CR"], ["50000000", "50 M CR"], ["100000000", "100 M CR"], ["250000000", "250 M CR"], ["500000000", "500 M CR"], ["1000000000", "1 BN CR"]]})
        + settingSwitch({key: "expedition_gec_enabled", label: "Points of interest near the route", detail: "Sights from EDAstro's Galactic Exploration Catalog near your expedition's route, on its PLACES tab. Fetched from edastro.com at most once a day; off means nothing is fetched.", checked: value.expedition_gec_enabled !== false})
        + settingSelect({key: "expedition_poi_range_ly", label: "How far off the route", detail: "Points of interest this close to the line of your route are shown.", value: number(value.expedition_poi_range_ly, 150), options: [[50, "50 ly"], [100, "100 ly"], [150, "150 ly"], [250, "250 ly"], [500, "500 ly"], [1000, "1,000 ly"]], type: "number"}))
      + settingGroup("HOME", `${settingText({key: "home_system", id: "setting-home", label: "Home system", detail: "Distances \"from home\" start here: the Watcher's remarks and the Galaxy Minimap. Leave it empty for Sol.", value: value.home_system, placeholder: "Sol", status: homeStatus(data.home)})}`)
      + settingGroup("COMMAND DECK", `${settingSwitch({key: "adaptive_command_enabled", label: "Adaptive command deck", detail: "The dashboard follows what you are doing: exploring, mining, on foot, docked.", checked: value.adaptive_command_enabled})}`)
      + settingGroup("ACHIEVEMENTS", `${settingSwitch({key: "achievements_enabled", label: "Track achievements", detail: "Unlock achievements from your journal as you play.", checked: value.achievements_enabled})}${settingNote("Unlocks pop up in the cockpit's Achievements overlay: switch it on or off, and place it, in Overlay Studio.")}`);
  }
  if (id === "hotkeys") {
    const rows = (data.hotkeys || []).map((row) => `<div class="setting-row hotkey-row" data-search="${settingSearchText(row.label, row.action, row.value, "hotkey shortcut")}"><span class="setting-copy"><b>${escapeHtml(row.label)}</b><small>${escapeHtml(row.default ? `Default ${row.default}` : "No default")}</small></span><span class="setting-control"><input data-hotkey-action="${escapeHtml(row.action)}" data-saved="${escapeHtml(row.value || "")}" value="${escapeHtml(row.value || "")}" placeholder="UNBOUND" readonly aria-label="${escapeHtml(row.label)} shortcut"><button type="button" data-hotkey-record="${escapeHtml(row.action)}" aria-label="Record ${escapeHtml(row.label)} shortcut">RECORD</button><button type="button" data-hotkey-clear="${escapeHtml(row.action)}" aria-label="Clear ${escapeHtml(row.label)} shortcut">CLEAR</button></span>${settingFlag()}</div>`).join("");
    return settingGroup("SHORTCUTS", `${settingSwitch({key: "overlay_hotkeys_enabled", label: "System-wide hotkeys", detail: "Shortcuts work while Elite has focus.", checked: value.overlay_hotkeys_enabled})}<p class="hotkey-status" id="hotkey-status">Press RECORD, then the whole shortcut. It saves as soon as you press it.</p>${rows}${settingActions(`<button type="button" id="hotkey-defaults">RESTORE DEFAULTS</button>`, "restore default hotkeys")}`);
  }
  if (id === "galnet") {
    const updated = galnet.updated_at ? ` · UPDATED ${String(galnet.updated_at).toUpperCase()}` : "";
    return settingGroup("RELAY", `${settingSwitch({key: "galnet_enabled", label: "Galnet relay", detail: "Fetch Frontier's Galnet feed for the news bar, the archive and the cockpit's Galnet Ticker.", checked: value.galnet_enabled})}${settingSelect({key: "galnet_refresh_minutes", label: "Check for news every", value: number(value.galnet_refresh_minutes, 30), options: [5, 15, 30, 60, 120, 240].map((item) => [item, item < 60 ? `${item} minutes` : `${item / 60} hour${item === 60 ? "" : "s"}`]), type: "number"})}<p class="setting-note" id="settings-galnet-status">${escapeHtml(galnet.detail || "Galnet relay standing by.")} · ${numeric((galnet.articles || []).length)} dispatches cached${escapeHtml(updated)}</p>${settingActions(`<button type="button" id="galnet-settings-refresh">REFRESH NOW</button><button type="button" id="galnet-settings-clear" class="danger-action">CLEAR CACHE</button>`, "refresh galnet clear cache")}`)
      + settingGroup("NEWS BAR", `${settingSwitch({key: "galnet_auto_rotate_enabled", label: "Rotate headlines", detail: "Step through the dispatches in the deck's news bar.", checked: value.galnet_auto_rotate_enabled})}${settingSelect({key: "galnet_rotation_seconds", label: "Next headline every", value: number(value.galnet_rotation_seconds, 7), options: [4, 7, 10, 15, 30, 60].map((item) => [item, `${item} seconds`]), type: "number"})}`)
;
  }
  if (id === "integrations") {
    return settingGroup("EDSM", `${settingText({key: "edsm_cmdr_name", id: "setting-edsm-name", label: "Commander name on EDSM", value: value.edsm_cmdr_name})}${settingText({key: "edsm_api_key", id: "setting-edsm-key", label: "EDSM API key", detail: "From your EDSM account settings.", value: value.edsm_api_key, secret: true})}${settingSwitch({key: "edsm_upload_enabled", label: "Send exploration to EDSM", detail: "Upload journal events with this commander's key.", checked: value.edsm_upload_enabled})}${settingActions(`<button type="button" data-ws-page="settings" data-ws-op="test_edsm">TEST EDSM</button>`, "test edsm credentials")}`)
      + settingGroup("INARA", `${settingText({key: "inara_cmdr_name", id: "setting-inara-name", label: "Commander name on Inara", detail: "Only used until the journal names your commander: Inara asks for the in-game name.", value: value.inara_cmdr_name, placeholder: data.profile?.name || ""})}${settingText({key: "inara_api_key", id: "setting-inara-key", label: "Inara API key", detail: "Your personal key, from inara.cz › Settings › API key.", value: value.inara_api_key, secret: true, status: inaraStatus(data.inara)})}${settingSwitch({key: "inara_upload_enabled", label: "Sync with Inara", detail: "Keep your Inara profile up to date as you play: credits, ranks, reputation, ships and loadouts, materials, cargo, missions, and your flight and combat logs. Sent in batches as you dock and jump, never more than once a minute.", checked: value.inara_upload_enabled})}${settingActions(`<button type="button" data-ws-page="settings" data-ws-op="test_inara">TEST INARA</button><button type="button" data-command="open" data-target="inara">INARA</button>`, "test inara key profile sync")}`)
      + settingGroup("RAVEN COLONIAL", `${settingText({key: "raven_api_key", id: "setting-raven-key", label: "Raven Colonial API key", detail: "From your account at ravencolonial.com/user. Colonisation shares your projects with it.", value: value.raven_api_key, secret: true})}${settingSwitch({key: "raven_sync_enabled", label: "Sync colonisation", detail: "Send deliveries, depot updates and fleet carrier cargo to Raven Colonial as they happen, under this commander.", checked: value.raven_sync_enabled})}${settingSwitch({key: "raven_share_ship_cargo", label: "Share your ship's cargo", detail: "Let your project's team see what you are carrying.", checked: value.raven_share_ship_cargo})}${settingActions(`<button type="button" data-ws-page="settings" data-ws-op="test_raven">CHECK KEY</button><button type="button" data-page="colonisation">COLONISATION</button>`, "test raven colonial key colonisation")}`)
      + settingGroup("BGS", `${settingSwitch({key: "bgs_online_enabled", label: "BGS online", detail: "Ask the EDCD tick service when the galaxy tick happened, and let the BGS tab look systems up on EDSM. Your own journal record works without it.", checked: value.bgs_online_enabled})}${settingActions(`<button type="button" data-page="bgs">BGS</button>`, "bgs tick edsm factions background simulation")}`)
      + settingGroup("Trading", `${settingSwitch({key: "trading_online_enabled", label: "Trading searches (Spansh)", detail: "Let the Trading tab ask Spansh for trade routes, prices and station markets, only when you search. Your own trading record works without it.", checked: value.trading_online_enabled})}${settingActions(`<button type="button" data-page="trading">TRADING</button>`, "trading trade routes spansh market prices commodities profit")}`)
      + settingGroup("EDDN", `${settingSwitch({key: "eddn_market_upload_enabled", label: "Share markets on EDDN", detail: "Publish the markets you visit to the community network.", checked: value.eddn_market_upload_enabled})}${settingNote(`${numeric(data.eddn?.uploads)} uploads this session${data.eddn?.last_error ? ` · last error: ${data.eddn.last_error}` : ""}`)}`)
      + settingGroup("LOCAL API", `${settingSwitch({key: "api_enabled", label: "Local API", detail: "Let your own tools read Void Compass and drive it: scripts, Stream Deck buttons, OBS scenes and widgets, Discord bots. No key needed: it answers this PC only, and web pages only when they're files on this PC (OBS browser sources too).", checked: value.api_enabled})}${settingText({key: "api_port", id: "setting-api-port", label: "Port", detail: "Where it listens, 1024 to 65535. Keep 7380 unless another program uses it.", value: String(value.api_port ?? 7380), status: apiStatus(data.api, value)})}${settingSwitch({key: "api_allow_control", label: "Allow control", detail: "Let tools change things: overlays, deck pages, the theme, the Watcher's thoughts and voice, music. Off, the API only reads.", checked: value.api_allow_control !== false})}${settingSwitch({key: "api_allow_lan", label: "Allow other devices", detail: "Answer other computers, tablets and phones on your network, not only this PC. There's no key, so anyone on the network can use it: only on a network you trust.", checked: value.api_allow_lan})}${settingActions(`<button type="button" data-ws-page="settings" data-ws-op="api_open_docs">API DOCS</button>`, "local api port docs stream deck obs scripts bot")}`)
      + settingGroup("DISCORD", `${settingText({key: "carrier_discord_webhook_url", id: "setting-discord", label: "Carrier webhook", detail: "One webhook for your personal and Squadron Carrier: status, jumps and expedition updates.", value: value.carrier_discord_webhook_url, secret: true})}${settingActions(`<button type="button" data-ws-page="settings" data-ws-op="test_discord">SEND TEST</button><button type="button" data-page="carrier">CARRIER COMMAND</button>`, "test discord carrier")}`)
;
  }
  if (id === "updates") {
    const version = escapeHtml(model.app?.version || "");
    return `<div class="update-page" data-search="${settingSearchText("check for updates update version new release download install github")}">
      <section class="update-card settings-update" id="settings-update" aria-live="polite">
        <div class="update-mark" aria-hidden="true"><i></i></div>
        <div class="update-words">
          <small>VOID COMPASS</small>
          <h4>You have <span id="update-current">v${version}</span></h4>
          <b id="settings-update-state">NOT CHECKED</b>
          <p id="settings-update-detail">Void Compass checks GitHub once when it starts.</p>
        </div>
        <div class="update-actions">
          <button type="button" class="primary" data-command="check_updates" data-update-check>CHECK FOR UPDATES</button>
          <button type="button" id="settings-update-view" data-update-view hidden>SEE THE UPDATE</button>
          <button type="button" data-command="open" data-target="releases">ALL RELEASES</button>
        </div>
      </section>
      <section class="update-how">
        <h4>HOW UPDATES WORK</h4>
        <ol>
          <li><b>It asks GitHub</b><span>once as Void Compass starts, or whenever you press CHECK FOR UPDATES.</span></li>
          <li><b>You choose</b><span>nothing downloads until you say so.</span></li>
          <li><b>It checks every byte</b><span>the download must match the checksum published with the release, or it's thrown away.</span></li>
          <li><b>It only replaces its own files</b><span>your settings, profiles, music, postcards, capsules and the Watcher's voice are never touched.</span></li>
        </ol>
      </section>
    </div>`;
  }
  const rebuildPanel = `<div id="settings-cache-rebuild" class="cache-rebuild-state ready" role="status" aria-live="polite"><header><span><b id="settings-cache-phase">READY</b><small id="settings-cache-detail">No cache rebuild has run for this profile this session.</small></span><strong id="settings-cache-percent">0%</strong></header><div id="settings-cache-meter" class="cache-rebuild-meter" role="progressbar" aria-label="Cache rebuild progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i id="settings-cache-bar"></i></div><footer><span id="settings-cache-meta">WAITING TO START</span><span id="settings-cache-elapsed"></span></footer></div>`;
  return `<div class="settings-health" id="settings-health"><b id="settings-health-level">${escapeHtml(health.level || "NOMINAL")}</b><span id="settings-health-detail">${escapeHtml(settingsHealthDetail(health))}</span></div>`
    + settingGroup("DIAGNOSTICS", `${settingSwitch({key: "runtime_trace_enabled", label: "Performance trace", detail: "Keep startup and UI timing in the logs folder.", checked: value.runtime_trace_enabled})}${settingSwitch({key: "crash_reporting_enabled", label: "Crash and freeze reports", detail: "Keep the current and previous reports in the logs folder.", checked: value.crash_reporting_enabled})}${settingActions(`<button type="button" data-command="open_logs">OPEN LOGS</button><button type="button" data-ws-page="settings" data-ws-op="support_bundle">CREATE SUPPORT BUNDLE</button>`, "open logs support bundle")}`)
    + settingGroup("RECOVERY", `${settingSwitch({key: "recovery_safe_mode_enabled", label: "Safe recovery after a crash", detail: "Start from the last clean profile checkpoint after an unclean shutdown.", checked: value.recovery_safe_mode_enabled})}${settingSwitch({key: "automatic_profile_backups_enabled", label: "Automatic profile snapshots", detail: "Keep up to five, taken before upgrades and cache rebuilds.", checked: value.automatic_profile_backups_enabled})}${settingActions(`<button type="button" data-ws-page="settings" data-ws-op="run_setup">RUN FIRST-TIME SETUP</button>`, "run setup onboarding")}`)
    + settingGroup("JOURNAL CACHE", `${settingNote("Rebuilds this profile's exploration history from every journal. Progress shows here and in the live feed.")}${rebuildPanel}${settingSwitch({key: "edsm_backfill_on_cache_rebuild", id: "setting-cache-edsm", label: "Send history to EDSM while rebuilding", detail: "Backfill EDSM from the journals being read.", checked: value.edsm_backfill_on_cache_rebuild})}${settingActions(`<button type="button" id="settings-cache-rebuild-button" data-ws-page="settings" data-ws-op="rebuild_cache">REBUILD CACHE</button>`, "rebuild journal cache")}`);
}

// Removing a carrier you no longer have (5.5.4): asked twice. Decommissioned
// ones go by themselves once scrapped; leaving a squadron drops its carrier.
function carrierRemoveRow(row, armed) {
  if (!row || row.id === null || row.id === undefined) return "";
  const pressed = armed !== null && armed !== undefined && String(armed) === String(row.id);
  const scrap = Number(row.decommission_at) > 0
    ? ` Decommissioning: it goes from this list once it's scrapped, ${new Date(Number(row.decommission_at) * 1000).toLocaleDateString([], {day: "numeric", month: "short"})}.` : "";
  return `<div class="carrier-remove"><small>${escapeHtml(`No longer yours? Remove ${row.name || row.callsign || "this carrier"} from Void Compass.${scrap}`)}</small>
    <button type="button" class="danger-action" data-ws-page="carrier" data-ws-op="remove_carrier" data-carrier-id="${escapeHtml(row.id)}">${pressed ? "PRESS AGAIN TO REMOVE" : "REMOVE CARRIER"}</button></div>`;
}

// Inara (5.5.4): how this session's sync is going.
// The local API (5.5.7): where it listens, or why it doesn't.
function apiStatus(api = {}, value = {}) {
  if (api.running) return {tone: "good", text: `LISTENING · ${String(api.url || "").replace("http://", "").toUpperCase()}${api.lan ? " · NETWORK" : ""}`};
  if (api.error && value.api_enabled) return {tone: "bad", text: String(api.error).toUpperCase()};
  return {tone: "", text: "OFF"};
}

function inaraStatus(inara = {}) {
  if (inara.status === "rejected") return {tone: "bad", text: "KEY REJECTED"};
  if (inara.status === "error") return {tone: "bad", text: "UNREACHABLE · RETRYING"};
  if (inara.status === "paused") return {tone: "", text: "NOT THE LIVE GAME"};
  if (Number(inara.sent) > 0) return {tone: "good", text: `${numeric(inara.sent)} SENT${Number(inara.pending) ? ` · ${numeric(inara.pending)} WAITING` : ""}`};
  return null;
}

// Your home system (5.5.4): the one in use, or how its lookup went.
function homeStatus(home = {}) {
  if (home.status === "looking") return {tone: "", text: "LOOKING UP…"};
  if (home.status === "unknown") return {tone: "bad", text: "NOT FOUND · USING SOL"};
  if (home.custom) return {tone: "good", text: `HOME · ${String(home.name || "").toUpperCase()}`};
  return {tone: "good", text: "HOME · SOL"};
}

function settingsHealthDetail(health = {}) {
  return (`UI queue ${numeric(health.ui?.pending ?? health.ui_pending)} · max lag ${numeric(health.ui?.max_lag_ms ?? health.ui_max_lag_ms)} ms · disk queue ${numeric(health.persistence?.pending ?? health.writes_pending)}`);
}

function renderSettingsWorkspace(data) {
  const root = byId("settings-workspace");
  const scroller = root.closest(".pages");
  const scrollTop = scroller?.scrollTop || 0;
  const summaries = settingsSummaries(data);
  const profile = data.profile || {};
  if (!SETTINGS_SECTIONS.some((section) => section.id === settingsSection)) settingsSection = "journal";
  root.classList.remove("loading-panel");
  const panels = SETTINGS_SECTIONS.map((section, index) => {
    const body = document.createElement("template");
    body.innerHTML = settingsSectionBody(section.id, data);
    const groups = [...body.content.querySelectorAll(".settings-group")];
    const links = groups.map((group) => {
      const heading = group.querySelector("h4");
      const name = heading?.textContent || "";
      group.id = `settings-${section.id}-${group.dataset.settingsGroup || layoutSlug(name)}`;
      if (heading) {
        heading.id = `${group.id}-heading`;
        heading.tabIndex = -1;
        group.setAttribute("aria-labelledby", heading.id);
      }
      return `<button type="button" class="settings-group-link" data-settings-jump="${group.id}">${escapeHtml(name)}</button>`;
    }).join("");
    return `<section class="settings-section" data-settings-panel="${section.id}" aria-labelledby="settings-heading-${section.id}">
      <header class="settings-section-head"><div><p>${String(index + 1).padStart(2, "0")} / ${section.category}</p><h3 id="settings-heading-${section.id}">${escapeHtml(section.heading)}</h3><span class="settings-section-detail">${escapeHtml(section.detail)}</span><small class="settings-section-summary">${escapeHtml(summaries[section.id] || "")}</small></div><div class="settings-section-emblem">${settingsIcon(section.id)}</div></header>
      ${groups.length > 1 ? `<nav class="settings-group-nav" aria-label="Jump within ${escapeHtml(section.title)}"><span>JUMP TO</span>${links}</nav>` : ""}
      <div class="settings-section-body">${body.innerHTML}</div></section>`;
  }).join("");
  const html = `<div class="settings-shell">
    <aside class="settings-rail">
      <header class="settings-commander"><span class="settings-profile-mark" aria-hidden="true">${settingsIcon("flight")}</span><div><small>COMMANDER PREFERENCES</small><b>CMDR ${escapeHtml(profile.name || "Unknown Commander")}</b><span>${escapeHtml(profile.fid ? `FID ${profile.fid}` : "No Frontier ID yet")}</span></div></header>
      <nav class="settings-rail-links" aria-label="Settings sections">${SETTINGS_SECTIONS.map((section) => `<button type="button" class="settings-tab" data-settings-section="${section.id}">${settingsIcon(section.id)}<span><b>${escapeHtml(section.title)}</b><small>${escapeHtml(summaries[section.id] || "")}</small></span><em class="settings-tab-count"></em></button>`).join("")}</nav>
      <footer class="settings-rail-footer"><small>Looking for overlay windows &amp; effects?</small><button type="button" class="settings-studio-link" data-page="overlay-studio">OPEN OVERLAY STUDIO <span aria-hidden="true">↗</span></button></footer>
    </aside>
    <div class="settings-panels">${panels}<div class="settings-no-match" hidden><h3>No settings found.</h3><p>Try a shorter word, a feature name, or clear the search to browse.</p><button type="button" class="settings-clear-search" data-settings-clear>CLEAR SEARCH</button></div></div>
  </div>`;
  // Note: patched in place after the first draw, so a save doesn't flash the
  // whole page or take the caret out of the field you're typing in.
  const shell = root.querySelector(".settings-shell");
  if (shell) {
    const fresh = document.createElement("template");
    fresh.innerHTML = html;
    morphNode(shell, fresh.content.firstElementChild);
  } else {
    root.innerHTML = html;
  }
  applySettingsView();
  renderSettingsUpdate(model.update || {});
  updateSettingsLive(data);
  showSettingsTestResult(data.tools || {});
  if (scroller) scroller.scrollTop = scrollTop;
}

// Brings an element in line with a freshly built copy, touching only what
// differs. Inputs being typed in keep their value; a row's save flash keeps
// its class.
const MORPH_KEEP_CLASSES = ["saving", "saved", "rejected"];
function morphNode(current, next) {
  if (current.nodeType !== next.nodeType || current.nodeName !== next.nodeName) {
    current.replaceWith(next.cloneNode(true));
    return;
  }
  if (current.nodeType === Node.TEXT_NODE || current.nodeType === Node.COMMENT_NODE) {
    if (current.nodeValue !== next.nodeValue) current.nodeValue = next.nodeValue;
    return;
  }
  if (current.nodeType !== Node.ELEMENT_NODE) return;
  for (const {name} of [...current.attributes]) {
    if (!next.hasAttribute(name) && name !== "class") current.removeAttribute(name);
  }
  for (const {name, value} of [...next.attributes]) {
    if (name === "class") {
      const keep = MORPH_KEEP_CLASSES.filter((cls) => current.classList.contains(cls));
      const wanted = [value, ...keep].join(" ").trim();
      if (current.getAttribute("class") !== wanted) current.setAttribute("class", wanted);
    } else if (current.getAttribute(name) !== value) {
      current.setAttribute(name, value);
    }
  }
  if (!next.hasAttribute("class") && current.hasAttribute("class")) {
    const keep = MORPH_KEEP_CLASSES.filter((cls) => current.classList.contains(cls));
    if (keep.length) current.setAttribute("class", keep.join(" ")); else current.removeAttribute("class");
  }
  const editing = current === document.activeElement;
  if (current instanceof HTMLInputElement) {
    if (current.type === "checkbox" || current.type === "radio") current.checked = next.hasAttribute("checked");
    else if (!editing && current.value !== (next.getAttribute("value") ?? "")) current.value = next.getAttribute("value") ?? "";
  }
  if (current instanceof HTMLTextAreaElement) {
    if (!editing && current.value !== next.value) current.value = next.value;
    return;
  }
  if (current instanceof HTMLSelectElement) {
    morphChildren(current, next);
    const chosen = [...next.options].find((option) => option.hasAttribute("selected"));
    if (!editing && chosen && current.value !== chosen.value) current.value = chosen.value;
    return;
  }
  morphChildren(current, next);
}

function morphChildren(current, next) {
  const fresh = [...next.childNodes];
  let index = 0;
  for (; index < fresh.length; index += 1) {
    const existing = current.childNodes[index];
    if (!existing) current.appendChild(fresh[index].cloneNode(true));
    else morphNode(existing, fresh[index]);
  }
  while (current.childNodes.length > fresh.length) current.lastChild.remove();
}

// An integration test's answer, right beside the button that ran it.
function showSettingsTestResult(tool = {}) {
  const op = String(tool.op || "");
  document.querySelectorAll(".setting-test-result").forEach((chip) => {
    if (chip.dataset.op !== op) chip.remove();
  });
  if (!op || !tool.status) return;
  const button = document.querySelector(`#settings-workspace [data-ws-op="${CSS.escape(op)}"]`);
  const row = button?.closest(".setting-row");
  if (!row) return;
  let chip = row.querySelector(".setting-test-result");
  if (!chip) {
    chip = document.createElement("span");
    chip.className = "setting-test-result";
    chip.setAttribute("role", "status");
    row.appendChild(chip);
  }
  const state = tool.status === "working" ? "working" : tool.status === "failed" ? "failed" : "ready";
  chip.dataset.op = op;
  chip.className = `setting-test-result ${state}`;
  chip.textContent = `${state === "working" ? "…" : state === "failed" ? "✗" : "✓"} ${tool.detail || ""}`;
}

// Shows the chosen section, or every row that matches the find box.
function applySettingsView() {
  const root = byId("settings-workspace");
  const shell = root?.querySelector(".settings-shell");
  if (!shell) return;
  const query = String(byId("settings-search")?.value || "").trim().toLocaleLowerCase();
  const words = query.split(/\s+/).filter(Boolean);
  shell.classList.toggle("searching", Boolean(words.length));
  let matches = 0;
  let matchingSections = 0;
  for (const panel of shell.querySelectorAll("[data-settings-panel]")) {
    const id = panel.dataset.settingsPanel;
    let panelMatches = 0;
    for (const row of panel.querySelectorAll("[data-search]")) {
      const hit = !words.length || words.every((word) => row.dataset.search.includes(word));
      row.hidden = !hit;
      if (hit) panelMatches += 1;
    }
    for (const group of panel.querySelectorAll(".settings-group")) {
      const rows = group.matches("[data-search]") ? [group] : [...group.querySelectorAll("[data-search]")];
      group.hidden = words.length > 0 && rows.every((row) => row.hidden);
    }
    const jumps = panel.querySelector(".settings-group-nav");
    if (jumps) jumps.hidden = words.length > 0;
    const health = panel.querySelector(".settings-health");
    if (health) health.hidden = words.length > 0;
    panel.hidden = words.length ? !panelMatches : id !== settingsSection;
    matches += panelMatches;
    if (panelMatches) matchingSections += 1;
    const tab = shell.querySelector(`[data-settings-section="${id}"]`);
    if (tab) {
      tab.classList.toggle("active", !words.length && id === settingsSection);
      tab.classList.toggle("empty", words.length > 0 && !panelMatches);
      tab.querySelector(".settings-tab-count").textContent = words.length ? String(panelMatches) : "";
      tab.setAttribute("aria-current", !words.length && id === settingsSection ? "page" : "false");
    }
  }
  shell.querySelector(".settings-no-match").hidden = !words.length || matches > 0;
  document.querySelector(".settings-toolbar [data-settings-clear]").hidden = !words.length;
  text("settings-search-summary", words.length
    ? `${matches} match${matches === 1 ? "" : "es"} across ${matchingSections} section${matchingSections === 1 ? "" : "s"}`
    : `Search across all ${SETTINGS_SECTIONS.length} sections`);
}

function settingsSaveState(state, detail = "") {
  const badge = byId("settings-save-state");
  if (!badge) return;
  badge.className = `settings-save-state ${state}`;
  badge.textContent = {
    saving: "SAVING…", saved: "ALL CHANGES SAVED", failed: detail ? `NOT SAVED · ${detail}` : "NOT SAVED",
  }[state] || "ALL CHANGES SAVED";
}

function flagSettingRow(row, state) {
  const flag = row?.querySelector(":scope > .setting-flag");
  if (!row || !flag) return;
  row.classList.remove("saving", "saved", "rejected");
  void row.offsetWidth;
  row.classList.add(state);
  flag.textContent = {saving: "SAVING", saved: "SAVED", rejected: "NOT SAVED"}[state] || "";
}

async function saveSettings(values, rows = [], extra = {}) {
  const id = ++settingsSaveSequence;
  settingsPendingSaves.set(id, {rows, revert: extra.revert, started: Date.now()});
  rows.forEach((row) => flagSettingRow(row, "saving"));
  settingsSaveState("saving");
  const accepted = await command("workspace", {page: "settings", operation: "save", save_id: id, values, ...(extra.hotkeys ? {hotkeys: extra.hotkeys} : {})});
  if (!accepted) settleSettingsSave(id, false, "the command deck could not reach Void Compass");
  // Should no snapshot confirm it, a save the channel accepted stands.
  window.setTimeout(() => { if (settingsPendingSaves.has(id)) settleSettingsSave(id, true); }, 4000);
  return accepted;
}

function settleSettingsSave(id, ok, detail = "") {
  const pending = settingsPendingSaves.get(id);
  if (!pending) return;
  settingsPendingSaves.delete(id);
  pending.rows.forEach((row) => flagSettingRow(row, ok ? "saved" : "rejected"));
  if (!ok) pending.revert?.();
  settingsSaveState(ok ? (settingsPendingSaves.size ? "saving" : "saved") : "failed", ok ? "" : detail);
}

function settleSettingsSaves(data = {}) {
  const result = data.last_save || {};
  const id = number(result.id);
  if (!id) return;
  // Saves up to this one have been applied in order; this one may have failed.
  for (const pendingId of [...settingsPendingSaves.keys()]) {
    if (pendingId < id) settleSettingsSave(pendingId, true);
    else if (pendingId === id) settleSettingsSave(pendingId, Boolean(result.ok), String(result.detail || ""));
  }
}

function settingValue(input) {
  if (input.type === "checkbox") return input.checked;
  if (input.dataset.settingType === "number") return number(input.value);
  return input.value.trim();
}

async function saveSettingsHotkeys(rows, message) {
  const inputs = [...document.querySelectorAll("[data-hotkey-action]")];
  const hotkeys = Object.fromEntries(inputs.map((input) => [input.dataset.hotkeyAction, input.value.trim()]));
  // The same shortcut on two actions is refused by Python; say why here.
  const owners = new Map();
  for (const input of inputs) {
    const chord = input.value.trim().toLocaleLowerCase();
    if (!chord) continue;
    if (owners.has(chord)) {
      text("hotkey-status", `${input.value.trim()} is already used by ${owners.get(chord)}. Choose another shortcut.`);
      inputs.forEach((item) => { item.value = item.dataset.saved || ""; });
      rows.forEach((row) => flagSettingRow(row, "rejected"));
      return false;
    }
    owners.set(chord, input.closest(".setting-row")?.querySelector(".setting-copy b")?.textContent || "another action");
  }
  const revert = () => {
    inputs.forEach((item) => { item.value = item.dataset.saved || ""; });
    text("hotkey-status", "That shortcut could not be used; the previous bindings are kept.");
  };
  const accepted = await saveSettings({}, rows, {hotkeys, revert});
  if (accepted) {
    inputs.forEach((item) => { item.dataset.saved = item.value; });
    if (message) text("hotkey-status", message);
  }
  return accepted;
}

// A re-render must not wipe what the commander is doing: an input with
// focus, a hotkey being recorded, unsaved theme colours or saves in flight.
function settingsCanRerender() {
  const root = byId("settings-workspace");
  if (!root) return false;
  if (hotkeyCaptureAction || settingsPendingSaves.size) return false;
  if (root.querySelector(".theme-workshop[data-dirty]")) return false;
  const focused = document.activeElement;
  return !(focused && root.contains(focused) && focused.matches("input, select, textarea, button"));
}

// What the page shows, without the live numbers updateSettingsLive handles.
function settingsFingerprint(data = {}) {
  return JSON.stringify({
    values: data.values, hotkeys: data.hotkeys, themes: data.themes,
    profile: data.profile, paths: data.paths, editor: [data.theme_editor?.name, data.theme_editor?.custom],
    galnet: [data.galnet?.status, data.galnet?.detail, (data.galnet?.articles || []).length, data.galnet?.updated_at],
    eddn: data.eddn,
  });
}

function cacheRebuildMeta(state = {}) {
  const parts = [];
  const processed = Math.max(0, number(state.processed));
  const total = Math.max(0, number(state.total));
  const systems = Math.max(0, number(state.systems));
  if (total) parts.push(`${numeric(Math.min(processed, total))} / ${numeric(total)} JOURNAL FILES`);
  if (systems) parts.push(`${numeric(systems)} SYSTEMS`);
  return parts.join(" · ") || (state.running ? "COUNTING JOURNAL FILES" : "WAITING TO START");
}

function updateSettingsLive(data = {}) {
  const state = data.cache_rebuild || {};
  const running = Boolean(state.running);
  const status = ["working", "failed", "warning", "ready"].includes(state.status) ? state.status : "ready";
  const percent = clamp(state.percent);
  const panel = byId("settings-cache-rebuild");
  if (panel) panel.className = `cache-rebuild-state ${status}`;
  text("settings-cache-phase", state.phase || (running ? "Preparing" : "Ready"));
  text("settings-cache-detail", state.detail || "No cache rebuild has run for this profile this session.");
  text("settings-cache-percent", `${numeric(percent)}%`);
  text("settings-cache-meta", cacheRebuildMeta(state));
  text("settings-cache-elapsed", number(state.elapsed_seconds) > 0 ? `${numeric(state.elapsed_seconds, 1)}S ELAPSED` : "");
  const meter = byId("settings-cache-meter");
  if (meter) meter.setAttribute("aria-valuenow", String(percent));
  const bar = byId("settings-cache-bar");
  if (bar) bar.style.width = `${percent}%`;
  const button = byId("settings-cache-rebuild-button");
  if (button) {
    button.disabled = running;
    button.textContent = running ? "REBUILDING CACHE…" : "REBUILD CACHE";
    button.classList.toggle("busy", running);
    if (running) button.setAttribute("aria-busy", "true");
    else button.removeAttribute("aria-busy");
  }
  if (data.health) {
    text("settings-health-level", data.health.level || "NOMINAL");
    text("settings-health-detail", settingsHealthDetail(data.health));
  }
}

let heldControl = null;
let deferredWorkspace = null;
document.addEventListener("pointerdown", (event) => {
  heldControl = event.target.closest?.("button, select, a, [role='button'], label") || null;
}, true);
function releaseHeldControl() {
  heldControl = null;
  const waiting = deferredWorkspace;
  deferredWorkspace = null;
  // After the click this release makes has been handled.
  if (waiting) setTimeout(() => renderWorkspace(model.workspace?.page === waiting.workspace?.page ? model : waiting), 0);
}
document.addEventListener("pointerup", releaseHeldControl, true);
document.addEventListener("pointercancel", releaseHeldControl, true);
window.addEventListener("blur", releaseHeldControl);

function renderWorkspace(state) {
  const workspace = state.workspace || {};
  const page = workspace.page || "";
  if (page !== currentPage || !workspace.ready) {
    if (page === currentPage && workspace.error) {
      const root = byId(`${page}-workspace`);
      if (root) {
        root.classList.remove("loading-panel");
        root.innerHTML = `<div class="workspace-empty"><b>COMMANDER RECORD LINK INTERRUPTED</b><span>${escapeHtml(workspace.error)}</span><button type="button" data-page="${escapeHtml(page)}">RETRY PANEL</button></div>`;
      }
    }
    return;
  }
  workspaceSyncTicket += 1;
  if (workspaceSyncTimer) window.clearTimeout(workspaceSyncTimer);
  workspaceSyncTimer = 0;
  if (pageLayoutEditing === page) return;
  // The archive's session clock ticks every second, and its science read
  // reports its age in tenths: neither alone may redraw Explore. Redrawn
  // every refresh, its orrery was rebuilt and the page wouldn't scroll.
  const archive = workspace.data?.archive;
  const fingerprintData = page === "explore" && archive
    ? {...workspace.data, archive: {...archive, current: {...(archive.current || {}), elapsed: ""},
      science_status: {...(archive.science_status || {}), age_seconds: null}}}
    : (workspace.data || {});
  const fingerprint = page === "settings" ? settingsFingerprint(workspace.data) : JSON.stringify(fingerprintData);
  if (page === "settings" && workspaceFingerprints[page]) {
    updateSettingsLive(workspace.data || {});
    settleSettingsSaves(workspace.data || {});
    showSettingsTestResult(workspace.data?.tools || {});
    if (fingerprint === workspaceFingerprints[page] || !settingsCanRerender()) return;
    workspaceFingerprints[page] = fingerprint;
    renderSettingsWorkspace(workspace.data || {});
    return;
  }
  if (page === "explore" && workspace.data?.archive) {
    const elapsed = byId("analytics-workspace")?.querySelector(".archive-current > strong");
    if (elapsed) elapsed.textContent = String(workspace.data.archive.current?.elapsed || "00:00:00");
  }
  if (workspaceFingerprints[page] === fingerprint) return;
  const root = byId(`${page}-workspace`);
  const focused = document.activeElement;
  const profileChanged = (page === "planet-materials" && root?.dataset.profileKey !== workspace.data?.profile_key)
    || (page === "explore" && byId("analytics-workspace")?.dataset.profileKey !== profileKey);
  if (!profileChanged && root?.contains(focused) && focused?.matches("input, textarea, select, [contenteditable='true']") && !focused?.matches("[data-refresh-on-change]")) return;
  // A button held down mustn't be redrawn before it's let go: the press and
  // the release would land on two different buttons and the click is lost
  // (5.5.5). The redraw waits for the release.
  if (root && heldControl && root.contains(heldControl)) {
    deferredWorkspace = state;
    return;
  }
  workspaceFingerprints[page] = fingerprint;
  const renderers = {
    "system-map": renderSystemMap,
    "planet-materials": (data) => renderPlanetary(data, PLANETARY_UI),
    explore: (data) => {
      renderExploreWorkspace(data, EXPLORE_WORKSPACE_UI);
      if (data.archive) renderExploreArchive(data.archive);
    },
    profile: renderProfileWorkspace,
    chronicle: (data) => {
      renderChronicleWorkspace(data);
      renderFlightLogs(data.flight_logs || {}, WORKSHOP_UI, data.sessions || []);
    },
    // 5.6.1: Mission Control is the Expeditions page (expeditions.js).
    mission: (data) => renderExpeditions(data, WORKSHOP_UI),
    mining: renderMiningWorkspace,
    powerplay: renderPowerplayWorkspace,
    carrier: renderCarrierWorkspace,
    recon: renderReconWorkspace, achievements: renderAchievementsWorkspace,
    ledger: renderLedgerWorkspace, settings: renderSettingsWorkspace,
    colonisation: renderColonisationWorkspace,
    bgs: renderBgsWorkspace,
    trading: renderTradingWorkspace,
    watcher: (data) => renderWatcher(data, WORKSHOP_UI),
    postcards: (data) => renderPostcards(data, WORKSHOP_UI),
    screenshots: (data) => renderScreenshots(data, WORKSHOP_UI),
    capsules: (data) => renderCapsules(data, WORKSHOP_UI),
    tools: (data) => renderTools(data, WORKSHOP_UI),
    constellation: (data) => renderConstellation(data, WORKSHOP_UI),
    games: (data) => renderGames(data, WORKSHOP_UI),
    hatchling: (data) => renderHatchling(data, WORKSHOP_UI),
    wrapped: (data) => renderWrapped(data, WORKSHOP_UI),
  };
  renderers[page]?.(workspace.data || {});
  preparePageLayout(page);
}

function renderDashboard(state) {
  const nextProfileKey = model.profile?.key || "default";
  if (nextProfileKey !== profileKey) {
    cancelPageLayout();
    resetSystemMap();
    profileKey = nextProfileKey;
    Object.keys(pageLayoutDefaults).forEach((page) => delete pageLayoutDefaults[page]);
    workspaceFingerprints = {};
    resetColonisation();
    resetTrading();
    resetMining();
    resetExpeditions();
    resetPlanetary();
    analyticsView = "trends";
    replaySelectedSessionIndex = 0;
    deckLayoutDraft = null;
    deckLayoutFingerprint = "";
    decisionTagsFingerprint = "";
    flightLogFilter = "ALL";
    flightLogSearch = "";
    flightLogEventsFingerprint = "";
    const flightLogSearchInput = byId("flightlog-search");
    if (flightLogSearchInput) flightLogSearchInput.value = "";
    preflightFingerprint = "";
    preflightSignalFingerprint = "";
    preflightExpanded = false;
    surveyBodiesFingerprint = "";
    resetExploreProfile();
    routeHorizonFingerprint = "";
    sessionHighlightsFingerprint = "";
    codexCandidatesFingerprint = "";
    galnetRenderKey = "";
    galnetTickerIndex = 0;
    galnetTickerId = "";
    galnetSelectedId = "";
    galnetRotationSettingsKey = "";
    if (galnetRotationTimer) window.clearTimeout(galnetRotationTimer);
    galnetRotationTimer = 0;
    byId("galnet-reader").hidden = true;
    if (replayTimer) { clearInterval(replayTimer); replayTimer = 0; }
    atlasRequested = false;
    const atlasFrame = byId("atlas-frame");
    if (atlasFrame) {
      atlasFrame.removeAttribute("src");
      atlasFrame.dataset.url = "";
    }
    byId("atlas-frame-shell")?.classList.remove("ready");
    const savedPage = localStorage.getItem(`voidcompass.dashboard.page.${profileKey}`) || "overview";
    showPage(document.querySelector(`[data-page-name="${CSS.escape(savedPage)}"]`) ? savedPage : "overview");
  }
  renderHeader(model);
  renderAdaptive(model);
  renderDecision(model);
  renderPreflight(model);
  renderFlightLog(model);
  renderSurvey(model);
  renderRoute(model);
  renderMetrics(model);
  renderSessionPulse(model);
  renderCodexHunt(model);
  renderDeckLayout(model);
  renderPriorities(model);
  renderEvents(model);
  renderGalnet(model);
  renderIntelligence(model);
  renderExpedition(model);
  renderSources(model);
  renderUpdateNotice(model.update || {});
  renderWorkspace(model);
  preparePageLayout(currentPage);
  // The Studio has a richer DOM than the briefing pages. Hydrate it only
  // while visible so routine journal publications stay inexpensive.
  if (currentPage === "overlay-studio") renderOverlayStudio(model);
  const requestedPage = model.ui?.page_request || {};
  const requestedId = number(requestedPage.id, 0);
  if (requestedId > pageRequestId && document.querySelector(`[data-page-name="${CSS.escape(requestedPage.page || "")}"]`)) {
    pageRequestId = requestedId;
    showPage(requestedPage.page);
  }
  renderAtlas(model);
  if (model.system_map) renderSystemMap(model.system_map);
  const appVersion = model.app?.version || "DEV";
  text("rail-version", `v${appVersion} // WEBVIEW2`);
  text("boot-version", `v${appVersion}`);
  renderAbout(model);
  text("overview-subtitle", model.profile?.profile_label || "Journal-backed field intelligence");
  if (currentPage === "map" && !model.boot?.active) ensureAtlas();
}

function renderState(state) {
  const incoming = state || {};
  // A response fetched before Python stopped booting may arrive after a newer
  // inactive snapshot. Reject it and let syncSnapshot fetch the current one.
  if (bootReleaseStarted && incoming.boot?.active && !incoming.onboarding?.active) return false;
  if (incoming.onboarding?.active) {
    bootReleaseStarted = false;
  } else if (!incoming.boot?.active) {
    bootReleaseStarted = true;
  }
  model = incoming;
  if (model.watcher_renderer_logging) {
    window.bootScene?.watchRenderer?.((renderer, reason) => command("watcher_renderer", {surface: "boot", renderer, ...(reason ? {reason} : {})}));
  }
  applyTheme(model.theme || {});
  applyTextSize(model.ui?.text_scale_percent, model.ui?.text_min_px);
  document.body.classList.toggle("reduced-motion", Boolean(model.ui?.reduced_motion));
  const nextBootActive = Boolean(model.boot?.active || model.onboarding?.active);
  const leavingBoot = bootActive && !nextBootActive;
  bootActive = nextBootActive;
  // Keep startup work out of the active boot phase; the final five-second
  // handoff hold below is the safe window to hydrate the deck behind it.
  renderBoot(model);
  if (nextBootActive) return true;
  if (!musicDeck) {
    musicDeck = createMusicDeck({apiUrl, showToast, byId, escapeHtml, duration});
    musicDeck.showPage(currentPage === "music");
  }
  musicDeck.update(model);
  if (leavingBoot) {
    // The boot curtain remains visible for five seconds. Hydrate the deck
    // behind it now so the first revealed frame is already complete.
    renderDashboard(model);
    return true;
  }
  renderDashboard(model);
  return true;
}

function setConnection(online) {
  const node = byId("connection-light").parentElement;
  node.classList.toggle("online", online);
  text("connection-state", online ? "LIVE" : "RECONNECTING");
}

async function syncSnapshot() {
  for (let attempt = 0; attempt < 3; attempt++) {
    const state = await getJson("/api/snapshot");
    if (renderState(state) !== false) {
      lastClientError = "";
      setConnection(true);
      return;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 120));
  }
  throw new Error("Stale boot snapshot persisted after handoff");
}

window.addEventListener("voidcompass:boot-recover", async () => {
  if (bootRecoveryPending || model.onboarding?.active
      || (document.body.classList.contains("ready") && byId("boot").hidden)) return;
  bootRecoveryPending = true;
  try {
    await syncSnapshot();
  } catch (error) {
    reportClientError(error, "boot-recover");
  } finally {
    bootRecoveryPending = false;
  }
});

// Ground targets are profile data as well as overlay state. The command is
// accepted by the loopback server before its coalesced snapshot publication
// runs, so give that publication one compositor turn and then pull the
// authoritative state. This keeps the coordinate fields, Studio readout,
// workspace and cockpit compass in step after a manual edit.
function queueGroundTargetRefresh() {
  if (groundTargetRefreshTimer) window.clearTimeout(groundTargetRefreshTimer);
  groundTargetRefreshTimer = window.setTimeout(async () => {
    groundTargetRefreshTimer = 0;
    try {
      await syncSnapshot();
    } catch (error) {
      reportClientError(error, "ground-target-refresh");
    }
  }, 90);
}

async function eventLoop() {
  while (true) {
    try {
      const event = await getJson(`/api/events?since=${revision}&wait=12`);
      if (event.closing) return;
      const nextRevision = number(event.revision, -1);
      if (nextRevision !== revision) {
        // Commit the revision only after its snapshot has fetched and rendered.
        // Otherwise one transient WebView2/loopback failure leaves the page
        // waiting forever because the failed revision appears consumed.
        await syncSnapshot();
        revision = nextRevision;
      }
    } catch (_error) {
      reportClientError(_error, "event-loop");
      setConnection(false);
      await new Promise((resolve) => window.setTimeout(resolve, 700));
    }
  }
}

function showPage(name) {
  if (name === "ground") setPlanetaryView("ground");
  if (name === "system-map") setExploreView("map", EXPLORE_WORKSPACE_UI);
  name = LEGACY_PAGE_REDIRECTS[name] || name;
  const page = document.querySelector(`[data-page-name="${CSS.escape(name)}"]`);
  if (!page) return;
  if (pageLayoutEditing && pageLayoutEditing !== name) cancelPageLayout();
  if (name === "settings" && currentPage !== "settings") workspaceFingerprints.settings = "";
  currentPage = name;
  setHatchlingActive(name === "hatchling");
  syncSystemMap();
  localStorage.setItem(`voidcompass.dashboard.page.${profileKey}`, name);
  document.querySelectorAll(".page").forEach((node) => node.classList.toggle("active", node === page));
  const navPage = navigationPage(name);
  document.querySelectorAll(".nav-item[data-page]").forEach((node) => {
    const active = node.dataset.page === navPage;
    node.classList.toggle("active", active);
    if (active) node.setAttribute("aria-current", "page");
    else node.removeAttribute("aria-current");
  });
  document.querySelectorAll(".suite-tabs [data-page]").forEach((node) => node.classList.toggle("active", node.dataset.page === name));
  document.querySelector(".pages").classList.toggle("atlas-active", name === "map");
  if (name !== "map") {
    document.body.classList.remove("atlas-focus");
    text("atlas-focus-toggle", "FOCUS MAP");
  }
  document.querySelector(".pages").scrollTo({top: 0, behavior: "instant"});
  requestPageChange(name);
  if (name === "map" && !model.boot?.active) ensureAtlas();
  if (name === "map") syncAtlasViewport();
  if (name === "map") window.setTimeout(syncAtlasLayerRequest, 160);
  if (name === "overlay-studio") renderOverlayStudio(model);
  musicDeck?.showPage(name === "music");
  preparePageLayout(name);
}

function requestPageChange(name) {
  const ticket = ++workspaceSyncTicket;
  if (workspaceSyncTimer) window.clearTimeout(workspaceSyncTimer);
  workspaceSyncTimer = 0;
  command("page_changed", {page: name});
  if (!byId(`${name}-workspace`)) return;
  let attempt = 0;
  const retry = () => {
    if (ticket !== workspaceSyncTicket || currentPage !== name) return;
    const workspace = model.workspace || {};
    if (workspace.page === name && workspace.ready) return;
    attempt += 1;
    command("page_changed", {page: name});
    if (attempt < 5) {
      workspaceSyncTimer = window.setTimeout(retry, 350 + attempt * 300);
    }
  };
  workspaceSyncTimer = window.setTimeout(retry, 450);
}

// Drags happen on one display: the pointer maps onto that display's pixels
// and the surface stays inside it. MOVE TO DISPLAY crosses between screens.
function studioPointerPosition(event, drag) {
  const rect = byId("studio-desktop").getBoundingClientRect();
  const monitor = studioMonitor();
  const row = studioOverlay(drag.id);
  if (!row || !monitor || rect.width <= 0 || rect.height <= 0) return null;
  const x = Math.round(drag.startX + (event.clientX - drag.clientX) * monitor.width / rect.width);
  const y = Math.round(drag.startY + (event.clientY - drag.clientY) * monitor.height / rect.height);
  return {
    x: Math.max(monitor.left, Math.min(x, monitor.left + monitor.width - row.width)),
    y: Math.max(monitor.top, Math.min(y, monitor.top + monitor.height - row.height)),
    monitor,
  };
}

function beginStudioDrag(event, card) {
  const row = studioOverlay(card.dataset.overlayId);
  if (!row || event.button !== 0) return;
  selectStudioOverlay(row.id);
  studioDragging = {
    id: row.id, pointerId: event.pointerId,
    clientX: event.clientX, clientY: event.clientY,
    startX: row.x, startY: row.y,
  };
  card.setPointerCapture(event.pointerId);
  card.classList.add("dragging");
  event.preventDefault();
}

function moveStudioDrag(event, card) {
  if (!studioDragging || studioDragging.ending || studioDragging.pointerId !== event.pointerId || studioDragging.id !== card.dataset.overlayId) return;
  const position = studioPointerPosition(event, studioDragging);
  if (!position) return;
  studioPendingPosition = {card, position};
  if (!studioDragFrame) studioDragFrame = requestAnimationFrame(() => {
    studioDragFrame = 0;
    const pending = studioPendingPosition;
    studioPendingPosition = null;
    if (!pending || !studioDragging) return;
    const {card: activeCard, position: active} = pending;
    const row = studioOverlay(studioDragging.id);
    placeStudioCard(activeCard, {...row, x: active.x, y: active.y}, active.monitor);
    const local = `X ${active.x - active.monitor.left} · Y ${active.y - active.monitor.top}`;
    text("studio-pointer-position", `${active.monitor.label} · ${local}`);
    text("studio-selected-position", local);
  });
  const now = performance.now();
  if (now - studioMoveSentAt >= 50) {
    studioMoveSentAt = now;
    command("overlay_studio", {operation: "move", overlay_id: studioDragging.id, x: position.x, y: position.y, commit: false, sequence: ++studioMoveSequence});
  }
}

function endStudioDrag(event, card) {
  if (!studioDragging || studioDragging.pointerId !== event.pointerId || studioDragging.id !== card.dataset.overlayId) return;
  const drag = studioDragging;
  const position = studioPointerPosition(event, drag);
  studioDragging.ending = true;
  card.classList.remove("dragging");
  try { card.releasePointerCapture(event.pointerId); } catch (_error) { /* already released */ }
  if (!position) {
    studioDragging = null;
    return;
  }
  const row = studioOverlay(drag.id);
  placeStudioCard(card, {...row, x: position.x, y: position.y}, position.monitor);
  command("overlay_studio", {operation: "move", overlay_id: drag.id, x: position.x, y: position.y, commit: true, sequence: ++studioMoveSequence})
    .finally(() => {
      const current = studioOverlay(drag.id);
      if (current) Object.assign(current, {x: position.x, y: position.y, monitor: position.monitor.id});
      studioDragging = null;
      studioFingerprint = "";
      renderOverlayStudio(model);
    });
}

async function nudgeStudioOverlay(vector) {
  const row = studioOverlay(studioSelectedId);
  if (!row) return false;
  const [dx, dy] = String(vector || "0,0").split(",").map((value) => number(value));
  const monitor = studioMonitorOf(row);
  const x = Math.max(monitor.left, Math.min(row.x + dx, monitor.left + monitor.width - row.width));
  const y = Math.max(monitor.top, Math.min(row.y + dy, monitor.top + monitor.height - row.height));
  return command("overlay_studio", {operation: "move", overlay_id: row.id, x, y, commit: true, sequence: ++studioMoveSequence});
}

// Keep the surface's place on its screen when it moves to another display.
async function moveStudioToDisplay(targetId) {
  const row = studioOverlay(studioSelectedId);
  const target = studioMonitors().find((monitor) => monitor.id === targetId);
  if (!row || !target) return false;
  const source = studioMonitorOf(row);
  const x = target.left + Math.max(0, Math.min(row.x - source.left, target.width - row.width));
  const y = target.top + Math.max(0, Math.min(row.y - source.top, target.height - row.height));
  const accepted = await command("overlay_studio", {operation: "move", overlay_id: row.id, x, y, commit: true, sequence: ++studioMoveSequence});
  if (accepted) {
    Object.assign(row, {x, y, monitor: target.id});
    studioMonitorId = target.id;
    studioFingerprint = "";
    renderOverlayStudio(model);
  }
  return accepted;
}

async function toggleStudioOverlay(id, wanted) {
  const row = studioOverlay(id);
  if (!row || Boolean(row.enabled) === Boolean(wanted)) return true;
  const accepted = await command("overlay_studio", {operation: "toggle", overlay_id: id});
  if (accepted) showToast(`${row.label} ${wanted ? "enabled" : "disabled"}`);
  return accepted;
}

document.addEventListener("click", async (event) => {
  const flightLogFilterButton = event.target.closest("[data-flightlog-filter]");
  if (flightLogFilterButton) {
    flightLogFilter = flightLogFilterButton.dataset.flightlogFilter || "ALL";
    flightLogEventsFingerprint = "";
    renderFlightLogEvents(model, true);
    return;
  }
  const layoutOpen = event.target.closest("[data-page-layout-open]");
  if (layoutOpen) {
    beginPageLayout(layoutOpen.dataset.pageLayoutOpen);
    return;
  }
  if (event.target.closest("[data-page-layout-cancel]")) {
    cancelPageLayout();
    return;
  }
  if (event.target.closest("[data-page-layout-reset]")) {
    await resetPageLayout();
    return;
  }
  if (event.target.closest("[data-page-layout-save]")) {
    await savePageLayout();
    return;
  }
  const panelMove = event.target.closest("[data-panel-move]");
  if (panelMove && pageLayoutEditing) {
    const panel = panelMove.closest("[data-layout-panel]");
    const panels = panel ? layoutPanels(panel.parentElement) : [];
    const index = panels.indexOf(panel);
    const targetIndex = index + (panelMove.dataset.panelMove === "up" ? -1 : 1);
    if (index >= 0 && targetIndex >= 0 && targetIndex < panels.length) {
      if (targetIndex < index) panel.parentElement.insertBefore(panel, panels[targetIndex]);
      else panel.parentElement.insertBefore(panel, panels[targetIndex].nextSibling);
      refreshPanelLayoutHandles(pageLayoutEditing);
    }
    return;
  }
  const analyticsTab = event.target.closest("[data-analytics-view]");
  if (analyticsTab) {
    analyticsView = analyticsTab.dataset.analyticsView || "trends";
    document.querySelectorAll("[data-analytics-view]").forEach((button) => {
      const active = button === analyticsTab;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    document.querySelectorAll("[data-analytics-panel]").forEach((panel) => { panel.hidden = panel.dataset.analyticsPanel !== analyticsView; });
    return;
  }
  if (event.target.closest("#replay-play")) {
    const slider = byId("replay-slider");
    if (!slider || slider.disabled) return;
    if (replayTimer) {
      clearInterval(replayTimer); replayTimer = 0;
      event.target.textContent = "PLAY REPLAY";
    } else {
      event.target.textContent = "PAUSE";
      replayTimer = window.setInterval(() => {
        const maximum = number(slider.max);
        slider.value = number(slider.value) >= maximum ? number(slider.min) : number(slider.value) + 1;
        updateReplayCursor(slider.value);
      }, 360);
    }
    return;
  }
  const studioDisplay = event.target.closest("[data-studio-display]");
  if (studioDisplay) {
    showStudioDisplay(studioDisplay.dataset.studioDisplay);
    return;
  }
  const studioMoveDisplay = event.target.closest("[data-studio-move-display]");
  if (studioMoveDisplay) {
    const target = studioMonitors().find((monitor) => monitor.id === studioMoveDisplay.dataset.studioMoveDisplay);
    if (await moveStudioToDisplay(studioMoveDisplay.dataset.studioMoveDisplay)) showToast(`Moved to ${target?.label || "the other display"}`);
    return;
  }
  if (handleColonisationClick(event, WORKSHOP_UI, () => renderColonisationWorkspace(model.workspace?.data || {}))) return;
  if (handleBgsClick(event, WORKSHOP_UI)) return;
  if (handleTradingClick(event, WORKSHOP_UI)) return;
  if (handleMiningClick(event, WORKSHOP_UI)) return;
  if (handleExpeditionsClick(event, WORKSHOP_UI)) return;
  if (handlePlanetaryClick(event, PLANETARY_UI)) return;
  const studioCard = event.target.closest(".studio-overlay-card");
  if (studioCard) {
    selectStudioOverlay(studioCard.dataset.overlayId);
    return;
  }
  // A row's switch toggles the surface in its change handler; the rest of the
  // row selects it and brings its display onto the stage.
  const studioRow = event.target.closest(".studio-index-row");
  if (studioRow && !event.target.closest(".studio-row-switch")) {
    selectStudioOverlay(studioRow.dataset.overlayId, true);
    return;
  }
  const studioNudge = event.target.closest("[data-studio-nudge]");
  if (studioNudge) {
    await nudgeStudioOverlay(studioNudge.dataset.studioNudge);
    return;
  }
  const surveyBodyButton = event.target.closest("#survey-body-list .survey-body-row");
  if (surveyBodyButton) {
    openExploreBody(surveyBodyButton, EXPLORE_WORKSPACE_UI);
    return;
  }
  const systemMapButton = event.target.closest("[data-system-map-body]");
  if (systemMapButton) {
    event.preventDefault();
    openSystemMap({system: systemMapButton.dataset.system || model.survey?.system || "", bodyId: systemMapButton.dataset.systemMapBody, name: systemMapButton.dataset.body || ""});
    return;
  }
  const pageButton = event.target.closest("[data-page]");
  if (pageButton) {
    // Links into Explore may name the view they belong to.
    if (pageButton.dataset.page === "explore" && pageButton.dataset.exploreView) {
      setExploreView(pageButton.dataset.exploreView, EXPLORE_WORKSPACE_UI);
    }
    // Links into Settings may name the section to open.
    if (pageButton.dataset.page === "settings" && pageButton.dataset.settingsSection) {
      settingsSection = pageButton.dataset.settingsSection;
    }
    // Links into Overlay Studio may name the overlay to select there.
    if (pageButton.dataset.page === "overlay-studio" && pageButton.dataset.studioSelect) {
      studioSelectedId = pageButton.dataset.studioSelect;
      studioFingerprint = "";
    }
    showPage(pageButton.dataset.page);
    return;
  }
  if (event.target.closest("[data-settings-clear]")) {
    byId("settings-search").value = "";
    applySettingsView();
    byId("settings-search").focus();
    return;
  }
  const settingsJump = event.target.closest("[data-settings-jump]");
  if (settingsJump) {
    const group = byId(settingsJump.dataset.settingsJump);
    if (group?.matches("details")) group.open = true;
    group?.querySelector("h4")?.focus({preventScroll: true});
    group?.scrollIntoView({block: "start", behavior: model.ui?.reduced_motion || window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth"});
    return;
  }
  const settingsTab = event.target.closest("[data-settings-section]");
  if (settingsTab) {
    settingsSection = settingsTab.dataset.settingsSection;
    const search = byId("settings-search");
    if (search) search.value = "";
    applySettingsView();
    settingsTab.closest(".pages")?.scrollTo({top: 0, behavior: "instant"});
    return;
  }
  const themeOption = event.target.closest("[data-theme-name]");
  if (themeOption) {
    const name = themeOption.dataset.themeName;
    if (themeOption.classList.contains("active")) return;
    if (await command("set_theme", {name})) {
      document.querySelectorAll(".theme-option").forEach((node) => {
        const active = node === themeOption;
        node.classList.toggle("active", active);
        node.setAttribute("aria-pressed", String(active));
      });
      showToast(`Theme changed to ${name}`);
    }
    return;
  }
  const browseFolder = event.target.closest("[data-settings-browse]");
  if (browseFolder) {
    const input = browseFolder.closest(".setting-row")?.querySelector("input[data-setting]");
    browseFolder.disabled = true;
    try {
      const api = window.pywebview?.api;
      if (!api?.choose_folder) throw new Error("Folder picker unavailable");
      const selected = await api.choose_folder();
      if (selected && input) {
        input.value = String(selected);
        input.dispatchEvent(new Event("change", {bubbles: true}));
      }
    } catch (error) {
      showToast(error.message || "Folder picker unavailable");
    } finally {
      browseFolder.disabled = false;
    }
    return;
  }
  const revealSecret = event.target.closest("[data-settings-reveal]");
  if (revealSecret) {
    const input = revealSecret.closest(".setting-control")?.querySelector("input");
    if (input) {
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      revealSecret.textContent = showing ? "SHOW" : "HIDE";
      revealSecret.setAttribute("aria-pressed", String(!showing));
    }
    return;
  }
  const achievementCategory = event.target.closest("[data-achievement-category]");
  const achievementStatus = event.target.closest("[data-achievement-state]");
  if (achievementCategory || achievementStatus) {
    if (achievementCategory) achievementUi.category = achievementCategory.dataset.achievementCategory;
    if (achievementStatus) achievementUi.status = achievementStatus.dataset.achievementState;
    achievementUi.visible = 24;
    renderAchievementCatalogue(model.workspace?.data || {});
    const attribute = achievementCategory ? "achievementCategory" : "achievementState";
    const selected = achievementCategory ? achievementUi.category : achievementUi.status;
    [...document.querySelectorAll("#achievement-categories button, #achievement-states button")]
      .find((button) => button.dataset[attribute] === selected)?.focus({preventScroll: true});
    return;
  }
  if (event.target.closest("#achievement-more")) {
    achievementUi.visible += 24;
    renderAchievementCatalogue(model.workspace?.data || {});
    return;
  }
  const recordHotkey = event.target.closest("[data-hotkey-record]");
  if (recordHotkey) {
    if (hotkeyCaptureAction) await finishHotkeyCapture("Starting a new capture…");
    hotkeyCaptureAction = recordHotkey.dataset.hotkeyRecord;
    const accepted = await command("workspace", {page: "settings", operation: "capture_begin"});
    if (!accepted) {
      hotkeyCaptureAction = "";
      text("hotkey-status", "Recorder could not suspend the active shortcuts.");
      return;
    }
    text("hotkey-status", "PRESS THE COMPLETE SHORTCUT · ESC CANCELS");
    recordHotkey.closest(".hotkey-row")?.classList.add("recording");
    recordHotkey.focus({preventScroll: true});
    return;
  }
  const clearHotkey = event.target.closest("[data-hotkey-clear]");
  if (clearHotkey) {
    const input = document.querySelector(`[data-hotkey-action="${CSS.escape(clearHotkey.dataset.hotkeyClear)}"]`);
    if (input) input.value = "";
    await saveSettingsHotkeys([clearHotkey.closest(".setting-row")], "Shortcut cleared.");
    return;
  }
  if (event.target.closest("#hotkey-defaults")) {
    for (const row of model.workspace?.data?.hotkeys || []) {
      const input = document.querySelector(`[data-hotkey-action="${CSS.escape(row.action)}"]`);
      if (input) input.value = row.default || "";
    }
    await saveSettingsHotkeys([...document.querySelectorAll(".hotkey-row")], "Default shortcuts restored.");
    return;
  }
  const galnetSettingsRefresh = event.target.closest("#galnet-settings-refresh");
  if (galnetSettingsRefresh) {
    await refreshGalnet(galnetSettingsRefresh);
    return;
  }
  if (event.target.closest("#galnet-settings-clear")) {
    if (!window.confirm("Clear locally cached Galnet dispatches?")) return;
    const accepted = await command("clear_galnet_cache");
    showToast(accepted ? "Galnet cache cleared" : "Galnet is busy; try again after the current refresh");
    return;
  }
  const workspaceButton = event.target.closest("[data-ws-page]");
  if (workspaceButton) {
    event.preventDefault();
    if (workspaceButton.disabled) return;
    const page = workspaceButton.dataset.wsPage;
    const operation = workspaceButton.dataset.wsOp;
    const payload = {page, operation};
    for (const [datasetKey, payloadKey] of [["expeditionId", "expedition_id"], ["objectiveId", "objective_id"], ["achievementId", "achievement_id"], ["bodyKey", "body_key"], ["pinId", "pin_id"], ["planId", "plan_id"], ["bookmarkId", "bookmark_id"], ["sessionIndex", "session_index"], ["carrierId", "carrier_id"], ["shipId", "ship_id"], ["returnLaterId", "id"], ["slot", "slot"], ["system", "system"], ["name", "name"], ["dossier", "dossier"]]) {
      if (workspaceButton.dataset[datasetKey] !== undefined) payload[payloadKey] = workspaceButton.dataset[datasetKey];
    }
    if (page === "carrier" && payload.carrier_id === undefined) {
      payload.carrier_id = byId("carrier-workspace")?.dataset.carrierId || null;
    }
    if (workspaceButton.dataset.status !== undefined) payload.status = workspaceButton.dataset.status;
    if (workspaceButton.dataset.index !== undefined) payload.index = number(workspaceButton.dataset.index, -1);
    if (workspaceButton.dataset.offset !== undefined) payload.offset = number(workspaceButton.dataset.offset);
    if (workspaceButton.dataset.resultIndex !== undefined) payload.result_index = number(workspaceButton.dataset.resultIndex, -1);
    if (workspaceButton.dataset.visited !== undefined) payload.visited = workspaceButton.dataset.visited === "true";
    if (workspaceButton.dataset.enabled !== undefined) payload.enabled = workspaceButton.dataset.enabled === "true";
    if (["delete", "remove_objective", "delete_objective", "delete_stop", "clear_route", "delete_candidate", "reset", "delete_waypoint", "clear_waypoints", "delete_theme", "delete_bookmark", "delete_build", "clear_slot"].includes(operation)) {
      if (!window.confirm("Confirm this profile-local change?")) return;
      payload.confirmed = true;
    }
    if (page === "chronicle" && operation === "export_replay") {
      payload.path = await window.pywebview?.api?.choose_replay_file?.();
      if (!payload.path) return;
    } else if (operation === "backup_picker" || operation === "restore_picker") {
      try {
        const selected = await window.pywebview?.api?.choose_folder?.();
        if (!selected) return;
        payload.operation = operation === "backup_picker" ? "backup" : "restore";
        payload.path = String(selected);
        if (payload.operation === "restore") {
          if (!window.confirm("Restore this backup on the next VoidCompass start? The current profile will be preserved as a rollback snapshot.")) return;
          payload.confirmed = true;
        }
      } catch (error) {
        showToast(error.message || "Native folder picker unavailable");
        return;
      }
    } else if (page === "explore" && operation === "add_waypoint") {
      payload.name = byId("waypoint-name")?.value.trim() || "";
      payload.note = byId("waypoint-note")?.value.trim() || "";
      if (!payload.name) return;
    } else if (page === "explore" && operation === "edit_waypoint") {
      const name = window.prompt("Waypoint system:", workspaceButton.dataset.name || "") || "";
      if (!name.trim()) return;
      const note = window.prompt("Waypoint note (optional):", workspaceButton.dataset.note || "");
      if (note === null) return;
      payload.name = name.trim();
      payload.note = note.trim();
    } else if (page === "explore" && operation === "neutron_plot") {
      Object.assign(payload, {
        from: byId("neutron-from")?.value.trim() || "",
        to: byId("neutron-to")?.value.trim() || "",
        range: byId("neutron-range")?.value,
        efficiency: byId("neutron-efficiency")?.value,
        multiplier: byId("neutron-multiplier")?.value,
      });
      if (!payload.from || !payload.to || number(payload.range) <= 0) return;
    } else if (page === "explore" && operation === "scout_search") {
      Object.assign(payload, {
        reference: byId("scout-reference")?.value.trim() || "",
        mode: byId("scout-mode")?.value || "biology",
        radius: byId("scout-radius")?.value,
        min_signals: byId("scout-signals")?.value,
        min_value: byId("scout-min-value")?.value,
        jump_range: byId("scout-range")?.value,
        max_results: byId("scout-limit")?.value,
      });
      if (!payload.reference || number(payload.radius) <= 0 || number(payload.max_results) <= 0 || number(payload.jump_range) <= 0) {
        showToast("Enter a reference system and positive search values"); return;
      }
    } else if (page === "ground" && operation === "set") {
      const prefix = {
        studio: "studio-ground",
      }[workspaceButton.dataset.groundSource] || "ground";
      payload.lat = byId(`${prefix}-lat`)?.value?.trim() || "";
      payload.lon = byId(`${prefix}-lon`)?.value?.trim() || "";
      const latitude = Number(payload.lat);
      const longitude = Number(payload.lon);
      if (!payload.lat || !payload.lon
          || !Number.isFinite(latitude) || !Number.isFinite(longitude)
          || latitude < -90 || latitude > 90
          || longitude < -180 || longitude > 180) {
        showToast("Enter a latitude from −90 to 90 and longitude from −180 to 180");
        return;
      }
    } else if (page === "ground" && operation === "add_pin") {
      payload.label = byId("field-marker-label")?.value.trim() || "Field marker";
    } else if (page === "powerplay" && operation === "add_objective") {
      Object.assign(payload, {
        title: byId("powerplay-objective-title")?.value.trim() || "",
        kind: byId("powerplay-objective-kind")?.value || "general",
        system: byId("powerplay-objective-system")?.value.trim() || "",
        commodity: byId("powerplay-objective-commodity")?.value.trim() || "",
        target: byId("powerplay-objective-target")?.value,
        notes: byId("powerplay-objective-notes")?.value.trim() || "",
      });
      if (!payload.title || number(payload.target) < 1) return;
    } else if (page === "carrier" && ["plot_route", "save_route", "update_route_details"].includes(operation)) {
      payload.name = byId("carrier-route-name")?.value.trim() || "Carrier expedition";
      payload.reserve = byId("carrier-route-reserve")?.value;
      payload.systems = (byId("carrier-route-systems")?.value || "").split(/\r?\n/).map((row) => row.trim()).filter(Boolean);
      if (operation === "plot_route" && !payload.systems.length) return;
    } else if (page === "carrier" && operation === "import_route") {
      payload.reference = byId("carrier-spansh-reference")?.value.trim() || "";
      payload.name = byId("carrier-route-name")?.value.trim() || "Carrier expedition";
      payload.reserve = byId("carrier-route-reserve")?.value;
      if (!payload.reference) return;
    } else if (page === "carrier" && operation === "tritium_search") {
      payload.reference = byId("tritium-reference")?.value.trim() || "";
      payload.range = byId("tritium-range")?.value;
      if (!payload.reference || number(payload.range) <= 0) return;
    } else if (page === "carrier" && operation === "add_stop") {
      payload.system = byId("carrier-add-system")?.value.trim() || "";
      if (!payload.system) return;
    } else if (page === "carrier" && ["save_discord_details", "discord_status"].includes(operation)) {
      payload.destination = byId("carrier-discord-destination")?.value.trim() || "";
      payload.note = byId("carrier-discord-note")?.value.trim() || "";
      payload.departure = byId("carrier-discord-departure")?.value.trim() || "";
    } else if (page === "settings" && operation === "save_theme") {
      payload.name = byId("custom-theme-name")?.value.trim() || "";
      payload.colors = Object.fromEntries([...document.querySelectorAll("[data-theme-color]")].map((input) => [input.dataset.themeColor, input.value]));
      if (!payload.name) return;
    } else if (page === "settings" && operation === "delete_theme") {
      payload.name = byId("custom-theme-existing")?.value || "";
      if (!payload.name) return;
    } else if (page === "settings" && operation === "test_edsm") {
      payload.commander = byId("setting-edsm-name")?.value.trim() || "";
      payload.api_key = byId("setting-edsm-key")?.value.trim() || "";
      if (!payload.commander || !payload.api_key) return;
    } else if (page === "settings" && operation === "test_raven") {
      payload.api_key = byId("setting-raven-key")?.value.trim() || "";
      if (!payload.api_key) return;
    } else if (page === "settings" && operation === "test_discord") {
      payload.url = byId("setting-discord")?.value.trim() || "";
      if (!payload.url) return;
    } else if (page === "settings" && operation === "rebuild_cache") {
      if (!window.confirm("Rebuild the active profile's journal cache now?")) return;
      payload.upload_edsm = Boolean(byId("setting-cache-edsm")?.checked);
      updateSettingsLive({cache_rebuild: {
        running: true, status: "working", phase: "Preparing", percent: 0,
        detail: "Preparing the active profile before scanning journal history.",
      }});
    }
    const cacheRebuildCommand = page === "settings" && operation === "rebuild_cache";
    workspaceButton.disabled = true;
    const accepted = await command("workspace", payload);
    if (!cacheRebuildCommand) workspaceButton.disabled = false;
    if (cacheRebuildCommand) {
      if (!accepted) updateSettingsLive(model.workspace?.data || {});
      showToast(accepted ? "Cache rebuild started — progress is shown in Diagnostics" : "A cache rebuild is already running");
    } else {
      const groundTargetCommand = page === "ground" && ["set", "set_current", "return_ship", "clear", "toggle_popup"].includes(operation);
      showToast(accepted
        ? groundTargetCommand ? "Compass target saved and overlay refreshed" : "Command applied"
        : "That action is not available from current journal state");
      if (accepted && groundTargetCommand) {
        workspaceFingerprints.ground = "";
        workspaceFingerprints["planet-materials"] = "";
        queueGroundTargetRefresh();
      }
    }
    return;
  }
  const filterButton = event.target.closest("[data-feed-filter]");
  if (filterButton) {
    feedFilter = filterButton.dataset.feedFilter || "ALL";
    document.querySelectorAll("[data-feed-filter]").forEach((node) => node.classList.toggle("active", node === filterButton));
    feedFingerprint = "";
    renderEvents(model);
    return;
  }
  const button = event.target.closest("[data-command]");
  if (!button || button.disabled) return;
  const action = button.dataset.command;
  if (action === "rebuild_cache" && !window.confirm("Rebuild the profile's journal cache now?")) return;
  button.classList.add("busy");
  button.setAttribute("aria-busy", "true");
  const payload = button.dataset.target ? {target: button.dataset.target} : {};
  if (button.dataset.enabled !== undefined) payload.enabled = button.dataset.enabled === "true";
  const accepted = await command(action, payload);
  button.classList.remove("busy");
  button.removeAttribute("aria-busy");
  // A copy reports in the Event Feed: whether it reached the clipboard.
  if (accepted && !["copy_next", "set_auto_copy"].includes(action)) showToast("Command handed to the flight computer");
});

document.addEventListener("input", (event) => {
  if (event.target.id === "flightlog-search") {
    flightLogSearch = event.target.value;
    flightLogEventsFingerprint = "";
    renderFlightLogEvents(model, true);
  } else if (event.target.id === "replay-slider") {
    updateReplayCursor(event.target.value);
  } else if (event.target.id === "achievement-filter") {
    achievementUi.search = event.target.value;
    achievementUi.visible = 24;
    renderAchievementCatalogue(model.workspace?.data || {});
  } else if (event.target.id === "ledger-filter") {
    const query = event.target.value.trim().toLocaleLowerCase();
    const rows = model.workspace?.page === "ledger" ? model.workspace.data?.rows || [] : [];
    const filtered = rows.filter((row) => !query || Object.values(row).flat().join(" ").toLocaleLowerCase().includes(query));
    byId("ledger-table").innerHTML = workspaceTable([
      {label: "System", key: "system"}, {label: "Body", key: "body"}, {label: "Class", key: "class"},
      {label: "Value", render: (row) => `<b>${credits(row.value)}</b>`},
      {label: "Mapped", render: (row) => row.mapped ? "YES" : "NO"},
      {label: "Flags", render: (row) => escapeHtml((row.flags || []).join(" · "))},
    ], filtered, "No valuable bodies match that filter.");
  }
});

// Settings save as they change. Overlays are Overlay Studio's alone.
document.addEventListener("change", (event) => {
  if (handleExpeditionsChange(event, WORKSHOP_UI)) return;
  handlePlanetaryChange(event, PLANETARY_UI);
});

document.addEventListener("change", async (event) => {
  const target = event.target;
  if (!target.closest?.("#settings-workspace")) return;
  if (target.matches("[data-setting]")) {
    const row = target.closest(".setting-row");
    // What to put back if Python refuses this save.
    const previous = target.type === "checkbox" ? !target.checked
      : target.tagName === "SELECT" ? ([...target.options].find((option) => option.defaultSelected)?.value ?? target.value)
        : target.defaultValue;
    const revert = () => {
      if (target.type === "checkbox") target.checked = previous;
      else target.value = previous;
    };
    const accepted = await saveSettings({[target.dataset.setting]: settingValue(target)}, [row], {revert});
    if (accepted && target.tagName === "SELECT") [...target.options].forEach((option) => { option.defaultSelected = option.selected; });
    else if (accepted && target.type !== "checkbox") target.defaultValue = target.value;
  } else if (target.matches("[data-theme-color], #custom-theme-name")) {
    target.closest(".theme-workshop")?.setAttribute("data-dirty", "");
  }
});

document.addEventListener("input", (event) => {
  if (event.target.id === "settings-search") applySettingsView();
  else if (!handleMiningInput(event, WORKSHOP_UI) && !handleExpeditionsInput(event) && !handlePlanetaryInput(event, PLANETARY_UI)) handleTradingInput(event, WORKSHOP_UI);
});

document.addEventListener("toggle", (event) => {
  if (event.target.matches?.(".theme-workshop")) settingsWorkshopOpen = event.target.open;
}, true);

// Saving or deleting a custom theme settles the workshop's edits.
document.addEventListener("click", (event) => {
  if (event.target.closest('[data-ws-page="settings"][data-ws-op="save_theme"], [data-ws-page="settings"][data-ws-op="delete_theme"]')) {
    event.target.closest(".theme-workshop")?.removeAttribute("data-dirty");
  }
}, true);

document.addEventListener("change", async (event) => {
  if (event.target.id === "achievement-sort") {
    achievementUi.sort = event.target.value;
    achievementUi.visible = 24;
    renderAchievementCatalogue(model.workspace?.data || {});
  } else if (event.target.dataset.deckVisible && deckLayoutDraft) {
    const id = event.target.dataset.deckVisible;
    const hidden = new Set(deckLayoutDraft.hidden);
    if (event.target.checked) hidden.delete(id); else hidden.add(id);
    deckLayoutDraft.hidden = [...hidden];
  } else if (event.target.id === "replay-session") {
    replaySelectedSessionIndex = Math.max(0, number(event.target.value));
    renderChronicleWorkspace(model.workspace?.data || {});
  } else if (!handleColonisationChange(event, WORKSHOP_UI, model.workspace?.data)) {
    handleBgsChange(event, WORKSHOP_UI);
  }
});

document.addEventListener("submit", (event) => {
  if (handleColonisationSubmit(event, WORKSHOP_UI)) return;
  if (handleTradingSubmit(event, WORKSHOP_UI)) return;
  if (handleMiningSubmit(event, WORKSHOP_UI)) return;
  if (handleExpeditionsSubmit(event, WORKSHOP_UI)) return;
  if (handlePlanetarySubmit(event, PLANETARY_UI)) return;
  handleBgsSubmit(event, WORKSHOP_UI);
});

byId("customise-deck").addEventListener("click", () => {
  const layout = model.dashboard_layout || {};
  deckLayoutDraft = {
    order: [...(layout.module_order || [])],
    hidden: [...(layout.hidden_modules || [])],
  };
  byId("exploration-doctrine").value = layout.doctrine || "balanced";
  renderDeckModuleControls(layout.available_modules || []);
  byId("deck-customiser").hidden = false;
  byId("deck-customiser").scrollIntoView({block: "nearest", behavior: "smooth"});
});

byId("preflight-toggle").addEventListener("click", () => {
  preflightExpanded = !preflightExpanded;
  renderPreflight(model);
});

byId("close-deck-customiser").addEventListener("click", () => {
  byId("deck-customiser").hidden = true;
  deckLayoutDraft = null;
  renderDeckLayout(model);
});

byId("save-deck-layout").addEventListener("click", async () => {
  if (!deckLayoutDraft) return;
  const doctrine = byId("exploration-doctrine").value || "balanced";
  const layoutSaved = await command("save_dashboard_layout", {module_order: deckLayoutDraft.order, hidden_modules: deckLayoutDraft.hidden});
  const doctrineSaved = layoutSaved && await command("set_exploration_doctrine", {doctrine});
  if (layoutSaved && doctrineSaved) {
    byId("deck-customiser").hidden = true;
    deckLayoutDraft = null;
    showToast("Explorer deck saved to this commander profile");
  }
});

function openGalnetReader() {
  const articles = galnetArticles();
  if (!articles.length) return showToast(model.galnet?.detail || "No Galnet dispatches are available");
  galnetSelectedId = articles[galnetTickerIndex]?.id || articles[0].id;
  renderGalnetReader();
  byId("galnet-reader").hidden = false;
  byId("galnet-close").focus();
}

function closeGalnetReader() {
  byId("galnet-reader").hidden = true;
  byId("status-galnet").focus();
}

function moveGalnetSelection(offset) {
  const articles = galnetArticles();
  if (!articles.length) return;
  const current = Math.max(0, articles.findIndex((row) => row.id === galnetSelectedId));
  const next = Math.max(0, Math.min(articles.length - 1, current + offset));
  if (next === current) return;
  galnetSelectedId = articles[next].id || "";
  renderGalnetReader();
  byId("galnet-headlines").querySelector(".galnet-headline-row.active")?.scrollIntoView({block: "nearest"});
}

byId("status-galnet").addEventListener("click", openGalnetReader);
byId("galnet-close").addEventListener("click", closeGalnetReader);
byId("galnet-previous").addEventListener("click", () => moveGalnetSelection(-1));
byId("galnet-next").addEventListener("click", () => moveGalnetSelection(1));
byId("galnet-reader").addEventListener("click", (event) => {
  if (event.target === byId("galnet-reader")) return closeGalnetReader();
  const headline = event.target.closest?.("[data-galnet-select]");
  if (!headline) return;
  galnetSelectedId = headline.dataset.galnetSelect || "";
  renderGalnetReader();
});

async function refreshGalnet(button) {
  button.disabled = true;
  const accepted = await command("refresh_galnet");
  button.disabled = false;
  if (accepted) showToast("Galnet refresh requested");
}
byId("galnet-reader-refresh").addEventListener("click", () => refreshGalnet(byId("galnet-reader-refresh")));

byId("flightlog-directive-primary").addEventListener("click", () => byId("decision-primary").click());
byId("decision-primary").addEventListener("click", async () => {
  const primary = model.decision?.primary || {};
  if (!primary.command) return;
  const payload = primary.target ? {target: primary.target} : {};
  const accepted = await command(primary.command, payload);
  if (accepted && primary.command === "open_codex_atlas") {
    atlasLayerRequest = "Codex";
    showPage("map");
  }
});

byId("codex-open-atlas").addEventListener("click", async () => {
  atlasLayerRequest = "Codex";
  const accepted = await command("open_codex_atlas");
  if (accepted) showPage("map");
});

byId("codex-add-objective").addEventListener("click", async () => {
  const target = model.codex_hunt?.target_category || "";
  if (!target) return;
  const accepted = await command("add_codex_objective", {target});
  showToast(accepted ? `${target} added to the active expedition` : "An active expedition is required");
});

byId("studio-overlay-cards").addEventListener("pointerdown", (event) => {
  const card = event.target.closest(".studio-overlay-card");
  if (card) beginStudioDrag(event, card);
});
byId("studio-overlay-cards").addEventListener("pointermove", (event) => {
  const card = event.target.closest(".studio-overlay-card");
  if (card) moveStudioDrag(event, card);
});
byId("studio-overlay-cards").addEventListener("pointerup", (event) => {
  const card = event.target.closest(".studio-overlay-card");
  if (card) endStudioDrag(event, card);
});
byId("studio-overlay-cards").addEventListener("pointercancel", (event) => {
  const card = event.target.closest(".studio-overlay-card");
  if (card) endStudioDrag(event, card);
});

byId("studio-selected-opacity").addEventListener("change", async (event) => {
  const wanted = event.target.value;
  if (!studioSelectedId || !(await command("overlay_studio", {operation: "own_opacity", overlay_id: studioSelectedId, value: Number(wanted)}))) {
    event.target.value = "0";
  }
});
byId("studio-selected-text").addEventListener("change", async (event) => {
  const wanted = event.target.value;
  if (!studioSelectedId || !(await command("overlay_studio", {operation: "own_text", overlay_id: studioSelectedId, value: Number(wanted)}))) {
    event.target.value = "0";
  }
});
byId("studio-selected-maphide").addEventListener("change", async (event) => {
  const wanted = event.target.checked;
  if (!studioSelectedId || !(await command("overlay_studio", {operation: "map_hiding", overlay_id: studioSelectedId, hide: wanted}))) {
    event.target.checked = !wanted;
  }
});
byId("studio-selected-menuhide").addEventListener("change", async (event) => {
  const wanted = event.target.checked;
  if (!studioSelectedId || !(await command("overlay_studio", {operation: "menu_hiding", overlay_id: studioSelectedId, hide: wanted}))) {
    event.target.checked = !wanted;
  }
});
byId("studio-selected-enabled").addEventListener("change", async (event) => {
  const wanted = event.target.checked;
  if (!studioSelectedId || !(await toggleStudioOverlay(studioSelectedId, wanted))) event.target.checked = !wanted;
});
byId("overlay-quick")?.addEventListener("click", async (event) => {
  const chip = event.target.closest("[data-overlay-quick]");
  if (!chip || chip.disabled) return;
  const wanted = chip.getAttribute("aria-pressed") !== "true";
  chip.disabled = true;
  try {
    if (await toggleStudioOverlay(chip.dataset.overlayQuick, wanted)) {
      chip.classList.toggle("on", wanted);
      chip.setAttribute("aria-pressed", String(wanted));
    }
  } finally {
    chip.disabled = false;
  }
});
function setOverlayQuickOpen(open) {
  const board = byId("overlay-quick")?.closest(".overlay-switchboard");
  if (!board) return;
  board.classList.toggle("open", open);
  byId("overlay-quick-more")?.setAttribute("aria-expanded", String(open));
}
byId("overlay-quick-more")?.addEventListener("click", () => {
  setOverlayQuickOpen(byId("overlay-quick-more").getAttribute("aria-expanded") !== "true");
});
// The dropdown closes on a click elsewhere or Escape, as menus do.
document.addEventListener("pointerdown", (event) => {
  if (!event.target.closest?.(".overlay-switchboard")) setOverlayQuickOpen(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setOverlayQuickOpen(false);
  if (event.key === "Escape" && event.target.id === "settings-search") {
    event.target.value = "";
    applySettingsView();
  }
});
byId("overlay-all-toggle")?.addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const hide = button.getAttribute("aria-pressed") !== "true";
  if (await command("overlay_studio", {operation: "hide_all"})) {
    button.setAttribute("aria-pressed", String(hide));
    button.closest(".overlay-switchboard")?.classList.toggle("all-hidden", hide);
    text("overlay-all-state", hide ? "HIDDEN" : "SHOWN");
  }
});
byId("studio-overlay-index").addEventListener("change", async (event) => {
  const input = event.target.closest("[data-overlay-enable]");
  if (!input) return;
  const wanted = input.checked;
  if (!(await toggleStudioOverlay(input.dataset.overlayEnable, wanted))) input.checked = !wanted;
});
byId("studio-snap-selected").addEventListener("click", async () => {
  if (!studioSelectedId) return;
  if (await command("overlay_studio", {operation: "snap", overlay_id: studioSelectedId})) showToast("Snapped to the nearest edge");
});
byId("studio-reset-selected").addEventListener("click", async () => {
  if (!studioSelectedId || !window.confirm("Reset this overlay to its default screen position?")) return;
  if (await command("overlay_studio", {operation: "reset", overlay_id: studioSelectedId})) showToast("Overlay position reset");
});
// Arrow keys nudge the selected surface 1 px, or 10 px with Shift.
byId("studio-desktop").addEventListener("keydown", async (event) => {
  const step = event.shiftKey ? 10 : 1;
  const vector = {ArrowUp: [0, -step], ArrowDown: [0, step], ArrowLeft: [-step, 0], ArrowRight: [step, 0]}[event.key];
  if (!vector || !studioSelectedId) return;
  event.preventDefault();
  await nudgeStudioOverlay(vector.join(","));
});

byId("studio-search").addEventListener("input", (event) => {
  studioSearch = event.target.value || "";
  applyStudioFilters();
});
byId("studio-filter").addEventListener("change", (event) => {
  studioFilter = event.target.value || "all";
  applyStudioFilters();
});

document.querySelectorAll("[data-overlay-option]").forEach((input) => {
  input.addEventListener("change", async () => {
    const requested = Boolean(input.checked);
    if (input.dataset.overlayOption === "station_info_auto_hide_enabled") {
      const timeout = byId("studio-station-timeout");
      if (timeout) timeout.disabled = !requested;
    }
    const accepted = await command("overlay_studio", {
      operation: "toggle_option", key: input.dataset.overlayOption, value: requested,
    });
    if (!accepted) input.checked = !requested;
  });
});

// Each setting saves on its own as it changes; nothing waits on an Apply.
document.querySelectorAll("[data-studio-setting]").forEach((field) => {
  field.addEventListener("change", async () => {
    const accepted = await command("overlay_studio", {
      operation: "save_settings", [field.dataset.studioSetting]: field.value,
    });
    const flag = field.closest(".studio-field");
    if (!flag) return;
    flag.classList.remove("saved", "rejected");
    void flag.offsetWidth;
    flag.classList.add(accepted ? "saved" : "rejected");
  });
});

byId("studio-layout-mode")?.addEventListener("change", (event) => {
  command("overlay_studio", {operation: "layout_mode", enabled: event.target.checked});
});

byId("studio-global-fade").addEventListener("input", (event) => queueStudioOpacity(event.target.value));
byId("studio-global-fade").addEventListener("change", (event) => queueStudioOpacity(event.target.value, true));

byId("studio-save-preset").addEventListener("click", async () => {
  const name = window.prompt("Name this overlay layout preset:", "");
  if (!name?.trim()) return;
  const exists = (studioData().presets || []).includes(name.trim());
  if (exists && !window.confirm(`Replace the existing '${name.trim()}' layout?`)) return;
  if (await command("overlay_studio", {operation: "save_preset", name: name.trim()})) showToast(`Saved ${name.trim()}`);
});
byId("studio-apply-preset").addEventListener("click", async () => {
  const name = byId("studio-preset-select").value;
  if (!name) return showToast("Choose a saved layout first");
  if (await command("overlay_studio", {operation: "apply_preset", name})) showToast(`Applied ${name}`);
});
byId("studio-delete-preset").addEventListener("click", async () => {
  const name = byId("studio-preset-select").value;
  if (!name || !window.confirm(`Delete the '${name}' layout preset?`)) return;
  if (await command("overlay_studio", {operation: "delete_preset", name})) showToast(`Deleted ${name}`);
});

installSetup(SETUP_UI);

byId("atlas-frame").addEventListener("load", () => {
  text("atlas-status", "Initialising map scene and commander layers…");
});

window.addEventListener("message", (event) => {
  const frame = byId("atlas-frame");
  const atlasUrl = model.atlas?.url;
  if (!atlasUrl || event.source !== frame.contentWindow) return;
  let expectedOrigin = "";
  try { expectedOrigin = new URL(atlasUrl).origin; } catch (_error) { return; }
  if (event.origin !== expectedOrigin || event.data?.type !== "voidcompass-atlas-ready") return;
  byId("atlas-frame-shell").classList.add("ready");
  text("atlas-status", "Live map linked to this commander profile");
  syncAtlasLayerRequest();
});

byId("atlas-focus-toggle").addEventListener("click", () => {
  const focused = document.body.classList.toggle("atlas-focus");
  text("atlas-focus-toggle", focused ? "DOCK MAP" : "FOCUS MAP");
  syncAtlasViewport();
});

window.addEventListener("keydown", async (event) => {
  if (hotkeyCaptureAction) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    if (event.repeat) return;
    if (event.key === "Escape" && !event.ctrlKey && !event.altKey && !event.shiftKey && !event.metaKey) {
      await finishHotkeyCapture("Capture cancelled.");
      return;
    }
    if (HOTKEY_MODIFIER_KEYS.has(event.key) || /^(?:Control|Alt|Shift|Meta)(?:Left|Right)$/.test(event.code || "")) {
      text("hotkey-status", "KEEP HOLDING THE MODIFIER · PRESS THE FINAL KEY");
      return;
    }
    const modifiers = [];
    if (event.ctrlKey) modifiers.push("Ctrl");
    if (event.altKey) modifiers.push("Alt");
    if (event.shiftKey) modifiers.push("Shift");
    if (event.metaKey) modifiers.push("Win");
    const media = HOTKEY_MEDIA_KEYS[event.key] || HOTKEY_MEDIA_KEYS[event.code] || "";
    const key = media || hotkeyFinalKey(event);
    if ((!modifiers.length && !media) || !key) {
      text("hotkey-status", "Use Ctrl, Alt, Shift or Win plus a letter, number, F-key or navigation key, or a media key on its own.");
      return;
    }
    const chord = [...modifiers, key].join("+");
    const input = document.querySelector(`[data-hotkey-action="${CSS.escape(hotkeyCaptureAction)}"]`);
    if (input) input.value = chord;
    await finishHotkeyCapture(`Captured ${chord}.`);
    if (input) await saveSettingsHotkeys([input.closest(".setting-row")], `${chord} saved.`);
    return;
  }
  if (event.key === "Escape" && !byId("galnet-reader").hidden) {
    event.preventDefault();
    closeGalnetReader();
    return;
  }
  if (event.key === "Escape" && document.body.classList.contains("atlas-focus")) {
    document.body.classList.remove("atlas-focus");
    text("atlas-focus-toggle", "FOCUS MAP");
    syncAtlasViewport();
  }
}, true);

function movePageLayoutGhost(drag, clientX, clientY) {
  if (!drag.ghost) {
    drag.ghost = document.createElement("div");
    drag.ghost.className = "panel-layout-ghost";
    drag.ghost.innerHTML = `<small>REPOSITION PANEL</small><strong>${escapeHtml(pageLayoutPanelTitle(drag.panel))}</strong>`;
    document.body.appendChild(drag.ghost);
  }
  drag.ghost.style.transform = `translate3d(${Math.round(clientX + 16)}px,${Math.round(clientY + 14)}px,0)`;
}

function pageLayoutDropAt(drag, clientX, clientY) {
  const panels = layoutPanels(drag.container).filter((panel) => panel !== drag.panel);
  if (!panels.length) return null;
  const hit = document.elementFromPoint(clientX, clientY)?.closest?.("[data-layout-panel]");
  let target = hit && hit !== drag.panel && hit.parentElement === drag.container ? hit : null;
  if (!target) {
    target = panels.reduce((nearest, panel) => {
      const rect = panel.getBoundingClientRect();
      const dx = clientX - (rect.left + rect.width / 2);
      const dy = clientY - (rect.top + rect.height / 2);
      const distance = dx * dx + dy * dy;
      return !nearest || distance < nearest.distance ? {panel, distance} : nearest;
    }, null)?.panel || null;
  }
  if (!target) return null;
  const rect = target.getBoundingClientRect();
  const withinRow = clientY >= rect.top && clientY <= rect.bottom;
  const after = withinRow
    ? clientX >= rect.left + rect.width / 2
    : clientY >= rect.top + rect.height / 2;
  return {target, after};
}

function updatePageLayoutDrop(drag, clientX, clientY) {
  const scroller = document.querySelector(".pages");
  const scrollRect = scroller?.getBoundingClientRect();
  if (scroller && scrollRect) {
    const edge = 58;
    if (clientY < scrollRect.top + edge) scroller.scrollTop -= 18;
    else if (clientY > scrollRect.bottom - edge) scroller.scrollTop += 18;
  }
  const nextDrop = pageLayoutDropAt(drag, clientX, clientY);
  if (!nextDrop) return;
  const {target, after} = nextDrop;
  if (pageLayoutDrop?.target === target && pageLayoutDrop.after === after) return;
  document.querySelectorAll(".layout-drop-before,.layout-drop-after").forEach((panel) => {
    panel.classList.remove("layout-drop-before", "layout-drop-after");
  });
  pageLayoutDrop = {target, after};
  target.classList.add(after ? "layout-drop-after" : "layout-drop-before");
}

document.addEventListener("pointerdown", (event) => {
  if (!pageLayoutEditing || (event.button !== undefined && event.button !== 0)) return;
  const grip = event.target.closest?.(".panel-layout-grip");
  const panel = grip?.closest("[data-layout-panel]");
  if (!panel?.parentElement) return;
  event.preventDefault();
  pageLayoutDrag = {
    panel,
    container: panel.parentElement,
    grip,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    active: false,
    ghost: null,
  };
  try { grip.setPointerCapture(event.pointerId); } catch (_error) { /* WebView capture is best effort. */ }
});

document.addEventListener("pointermove", (event) => {
  const drag = pageLayoutDrag;
  if (!drag || drag.pointerId !== event.pointerId) return;
  event.preventDefault();
  if (!drag.active) {
    if (Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) < 4) return;
    drag.active = true;
    drag.panel.classList.add("layout-dragging");
    document.body.classList.add("layout-pointer-dragging");
  }
  movePageLayoutGhost(drag, event.clientX, event.clientY);
  updatePageLayoutDrop(drag, event.clientX, event.clientY);
});

function finishPageLayoutDrag(event, commit) {
  const drag = pageLayoutDrag;
  if (!drag || (event?.pointerId !== undefined && drag.pointerId !== event.pointerId)) return;
  if (commit && drag.active && pageLayoutDrop) {
    const {target, after} = pageLayoutDrop;
    if (target !== drag.panel && target.parentElement === drag.container) {
      drag.container.insertBefore(drag.panel, after ? target.nextSibling : target);
    }
  }
  try { drag.grip?.releasePointerCapture(drag.pointerId); } catch (_error) { /* Already released. */ }
  clearPageLayoutPointer();
  if (commit && drag.active) refreshPanelLayoutHandles(pageLayoutEditing);
}

document.addEventListener("pointerup", (event) => finishPageLayoutDrag(event, true));
document.addEventListener("pointercancel", (event) => finishPageLayoutDrag(event, false));

window.addEventListener("error", (event) => {
  reportClientError(event.error || event.message, "window-error");
});

window.addEventListener("unhandledrejection", (event) => {
  reportClientError(event.reason, "unhandled-rejection");
});

window.setInterval(() => text("footer-clock", new Date().toLocaleTimeString([], {hour12: false})), 500);
byId("release-update-later").addEventListener("click", dismissUpdateNotice);
byId("release-update-open").addEventListener("click", async () => {
  if (await command("open", {target: "release_update"})) dismissUpdateNotice();
});
byId("release-update-install").addEventListener("click", (event) => {
  const action = event.currentTarget.dataset.action || "install_update";
  event.currentTarget.disabled = true;
  command(action, {});
});
installPageSuites();
decorateCockpitButtons();
cockpitButtonObserver.observe(document.body, {childList: true, subtree: true});
showPage("overview");
// page-start.js watches for this: a page that never sets it is reported.
window.__voidcompassDeckStarted = true;
eventLoop();

installSystemMap({showPage});
