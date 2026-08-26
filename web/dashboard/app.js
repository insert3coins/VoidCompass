const query = new URLSearchParams(window.location.search);
const token = query.get("token") || "";
let revision = -1;
let model = {};
let currentPage = "overview";
let profileKey = "default";
let feedFilter = "ALL";
let toastTimer = 0;
let feedFingerprint = "";
let galnetFingerprint = "";
let galnetRenderKey = "";
let galnetTickerIndex = 0;
let galnetTickerId = "";
let galnetSelectedId = "";
let galnetRotationTimer = 0;
let galnetRotationSettingsKey = "";
let onboardingSession = -1;
let atlasRequested = false;
let lastClientError = "";
let bootActive = true;
let bootHideTimer = 0;
let dashboardRenderQueued = false;
let themeFingerprint = "";
let pageRequestId = 0;
let studioSelectedId = "";
let studioView = "layout";
let studioDragging = null;
let studioFingerprint = "";
let studioMoveSentAt = 0;
let studioMoveSequence = 0;
let studioDragFrame = 0;
let studioPendingPosition = null;
let studioFilter = "all";
let studioSearch = "";
let workspaceFingerprints = {};
let missionSelectedId = "";
let hotkeyCaptureAction = "";
let orrerySelectedBodyId = "";
let orreryLiveTargetBodyId = "";
let analyticsView = "trends";
let replaySelectedSessionIndex = 0;
let replayTimer = 0;
let deckLayoutDraft = null;
let deckLayoutFingerprint = "";
let atlasLayerRequest = "";
let decisionTagsFingerprint = "";
let routeHorizonFingerprint = "";
let sessionHighlightsFingerprint = "";
let codexCandidatesFingerprint = "";
let pageLayoutEditing = "";
let pageLayoutOriginal = null;
let pageLayoutDrag = null;
let pageLayoutDragArmed = null;
let pageLayoutDrop = null;
const pageLayoutDefaults = {};

const HOTKEY_MODIFIER_KEYS = new Set([
  "Alt", "AltGraph", "Control", "Meta", "OS", "Shift",
]);
const HOTKEY_CODE_NAMES = {
  Space: "Space", ArrowLeft: "Left", ArrowRight: "Right",
  ArrowUp: "Up", ArrowDown: "Down", PageUp: "PageUp",
  PageDown: "PageDown", Enter: "Enter", NumpadEnter: "Enter",
  Delete: "Delete", Insert: "Insert", Home: "Home", End: "End",
  Backspace: "Backspace", Tab: "Tab", Escape: "Escape",
};

const STRUCTURAL_BUTTON_SELECTOR = [
  ".nav-item", "[data-feed-filter]", ".studio-overlay-card",
  ".studio-index-row", ".mission-row", ".workspace-tabs button",
  "[data-analytics-view]", "[data-studio-view]",
  ".galnet-headline-row", "#status-galnet",
].join(",");

function decorateCockpitButtons(root = document) {
  const buttons = [];
  if (root instanceof HTMLButtonElement) buttons.push(root);
  if (root?.querySelectorAll) buttons.push(...root.querySelectorAll("button"));
  for (const button of buttons) {
    if (button.matches(STRUCTURAL_BUTTON_SELECTOR)) continue;
    button.classList.add("cockpit-button");
    button.classList.toggle("cockpit-primary", button.matches(
      ".primary, .commission-action, #settings-save-html, #save-deck-layout, [data-page-layout-save]",
    ));
    button.classList.toggle("cockpit-danger", button.matches(
      ".danger-action, .row-delete, #studio-delete-preset, #annotation-delete",
    ));
    button.classList.toggle("cockpit-ghost", button.matches(".ghost, .quiet-action"));
  }
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
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return true;
  } catch (error) {
    showToast(`Command unavailable: ${error.message}`);
    return false;
  }
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
  "#overview-modules", ".intel-grid", ".record-metrics", ".records-grid",
  ".tool-grid", ".settings-grid", ".about-grid",
  ".workspace-shell > .workspace-grid", ".workspace-shell > .settings-workspace-grid",
  ".workspace-shell > .stellar-grid", ".workspace-shell > .mission-layout",
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
    "article, aside, main, section.telemetry-strip, section.workspace-card, .tool-card",
  ));
  const used = new Set();
  candidates.forEach((panel, index) => {
    if (!panel.dataset.layoutPanel) {
      const heading = panel.querySelector(":scope > header span")?.textContent
        ?.split("·", 1)[0]?.trim();
      const identity = panel.dataset.deckModule
        || heading
        || panel.querySelector(":scope > h3")?.textContent
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
      panel.draggable = true;
      const handle = document.createElement("div");
      handle.className = "panel-layout-handle";
      handle.innerHTML = `<span title="Drag this panel">⠿</span><button type="button" data-panel-move="up" ${index === 0 ? "disabled" : ""} aria-label="Move panel earlier">↑</button><button type="button" data-panel-move="down" ${index === panels.length - 1 ? "disabled" : ""} aria-label="Move panel later">↓</button>`;
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
      controls.querySelector('[data-panel-move="up"]').disabled = index === 0;
      controls.querySelector('[data-panel-move="down"]').disabled = index === panels.length - 1;
    });
  }
}

function removePanelLayoutHandles(pageName) {
  const page = document.querySelector(`[data-page-name="${CSS.escape(pageName)}"]`);
  page?.querySelectorAll(":scope .panel-layout-handle").forEach((node) => node.remove());
  page?.querySelectorAll(":scope .layout-panel").forEach((panel) => {
    panel.classList.remove(
      "layout-panel", "layout-dragging", "layout-drop-before", "layout-drop-after",
    );
    panel.removeAttribute("draggable");
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
  toolbar.innerHTML = `<div><small>PROFILE-AWARE PANEL LAYOUT</small><strong>${escapeHtml(page.querySelector(":scope > .page-title h2")?.textContent || pageName)}</strong><span>Drag panels or use the arrow controls. Lists and controls remain intact.</span></div><div><button type="button" data-page-layout-cancel>CANCEL</button><button type="button" data-page-layout-reset>RESET DEFAULT</button><button type="button" class="primary" data-page-layout-save>SAVE TO THIS PROFILE</button></div>`;
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
  pageLayoutDragArmed = null;
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
  pageLayoutDragArmed = null;
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
  pageLayoutDragArmed = null;
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
  const select = byId("theme-select");
  const names = Array.isArray(theme.available) ? theme.available : [];
  const optionsKey = names.join("\u0000");
  if (select.dataset.options !== optionsKey) {
    select.replaceChildren(...names.map((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      return option;
    }));
    select.dataset.options = optionsKey;
  }
  select.value = theme.name || "Void Cyan";
  const nextFingerprint = JSON.stringify({name: theme.name || "", palette: theme.palette || {}, names});
  if (nextFingerprint !== themeFingerprint) {
    themeFingerprint = nextFingerprint;
    const swatches = byId("theme-swatches");
    swatches.replaceChildren(...["accent", "orange", "green", "yellow", "red", "text"].map((key) => {
      const item = document.createElement("i");
      item.style.background = theme.palette?.[key] || "transparent";
      return item;
    }));
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
    bootRoot.hidden = false;
    window.clearTimeout(bootHideTimer);
    bootHideTimer = 0;
    document.body.classList.remove("ready");
    byId("app").setAttribute("aria-hidden", "true");
    renderCommissioning(onboarding);
    return;
  }

  text("boot-status", boot.status, "INITIALISING FLIGHT COMPUTER");
  text("boot-detail", boot.detail, "Preparing local state");
  percentWidth("boot-progress", number(boot.progress) * 100);
  const progress = number(boot.progress);
  const stages = [
    ["boot-profile", progress >= .18],
    ["boot-survey", progress >= .64],
    ["boot-journal", progress >= .76],
    ["boot-cockpit", progress >= .90],
  ];
  for (const [id, ready] of stages) {
    text(id, ready ? "READY" : "WAIT");
    byId(id).classList.toggle("ready", ready);
    const stage = document.querySelector(`[data-boot-stage="${id.replace("boot-", "")}"]`);
    if (stage) stage.classList.toggle("ready", ready);
  }
  if (!boot.active) {
    document.body.classList.add("ready");
    byId("app").setAttribute("aria-hidden", "false");
    if (!bootHideTimer) {
      bootHideTimer = window.setTimeout(() => {
        bootHideTimer = 0;
        if (!model.boot?.active && !model.onboarding?.active) bootRoot.hidden = true;
      }, 720);
    }
  } else {
    bootRoot.hidden = false;
    window.clearTimeout(bootHideTimer);
    bootHideTimer = 0;
    document.body.classList.remove("ready");
    byId("app").setAttribute("aria-hidden", "true");
  }
}

function renderCommissioning(onboarding) {
  const session = number(onboarding.session, 0);
  if (session !== onboardingSession) {
    onboardingSession = session;
    byId("onboarding-journal").value = onboarding.journal_path || "";
    byId("onboarding-adaptive").checked = Boolean(onboarding.adaptive_command_enabled);
    byId("onboarding-overlays").checked = Boolean(onboarding.overlay_enabled);
    byId("onboarding-passthrough").checked = Boolean(onboarding.overlay_mouse_passthrough);
  }
  text("onboarding-error", onboarding.error, "");
  const submitting = Boolean(onboarding.submitting);
  for (const control of byId("onboarding-form").querySelectorAll("input,button")) control.disabled = submitting;
  text("onboarding-submit", submitting ? "COMMISSIONING…" : "COMMISSION VOID COMPASS");
}

function renderHeader(state) {
  const flight = state.flight || {};
  const survey = state.survey || {};
  const route = state.route || {};
  const session = state.session || {};
  const traffic = state.traffic || {};
  text("header-system", flight.system, "---");
  text("header-context", flight.context, "WAITING FOR LIVE JOURNAL");
  text("header-survey", `${number(survey.scanned)} / ${survey.total_known ? number(survey.total) : "?"}`);
  text("header-route", route.summary, "INACTIVE");
  text("header-session", session.elapsed, "00:00:00");
  text("header-traffic", `${number(traffic.day)} / ${number(traffic.week)} / ${number(traffic.total)}`);
  text("header-commander", state.profile?.commander, "UNKNOWN");
  text("header-ship", `${flight.ship || "SHIP"} // ${flight.state || "FLIGHT"}`.toUpperCase());
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
  text("decision-confidence", decision.confidence || "JOURNAL-BACKED");
  text("decision-title", decision.title || "HOLD FOR EXPLORATION TELEMETRY");
  text("decision-detail", decision.detail || "No unresolved journal-backed objective is currently known.");
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

function renderFlightLog(state) {
  const enabled = Boolean(state.ui?.flight_log_mode);
  document.body.classList.toggle("flight-log-mode", enabled);
  byId("flight-log-shell")?.setAttribute("aria-hidden", String(!enabled));
  if (!enabled) return;
  const flight = state.flight || {};
  const survey = state.survey || {};
  const route = state.route || {};
  const data = state.data || {};
  text("flightlog-identity", `${state.profile?.commander || "UNKNOWN COMMANDER"} · ${flight.ship || "SHIP"} · ${state.session?.elapsed || "00:00:00"}`);
  text("flightlog-system", flight.system, "NO SYSTEM DATA");
  text("flightlog-state", flight.context, "WAITING FOR LIVE JOURNAL");
  text("flightlog-survey-badge", survey.complete ? "COMPLETE" : survey.total_known ? "IN PROGRESS" : "AWAITING");
  text("flightlog-survey", `${numeric(survey.scanned)} / ${survey.total_known ? numeric(survey.total) : "?"}`);
  text("flightlog-survey-detail", `${numeric(survey.bio_signals)} BIO · ${numeric(survey.geo_signals)} GEO · ${numeric(survey.valuable_count)} VALUABLE`);
  percentWidth("flightlog-progress", survey.percent);
  text("flightlog-route", route.next || "NO ACTIVE ROUTE");
  text("flightlog-route-detail", route.summary || route.text || "PLOT IN ELITE OR WAYPOINTS");
  text("flightlog-value", credits(data.unsold_total));
  text("flightlog-value-detail", `${credits(data.unsold_exploration)} CARTOGRAPHY · ${credits(data.unsold_bio)} BIOLOGY`);
  const events = (state.events || []).slice(0, 40);
  text("flightlog-event-count", `${events.length} EVENTS`);
  byId("flightlog-event-list").innerHTML = events.map((row) => `<div class="flightlog-event ${escapeHtml(String(row.severity || "info").toLowerCase())}"><time>${escapeHtml(row.time || "--:--:--")}</time><b>${escapeHtml(row.tag || "INFO")}</b><span>${escapeHtml(row.message || "")}</span></div>`).join("") || `<p class="workspace-empty">The curated exploration record is waiting for live journal activity.</p>`;
}

function renderSurvey(state) {
  const survey = state.survey || {};
  const intel = state.intelligence || {};
  const completion = number(survey.percent);
  text("survey-system", state.flight?.system, "NO SYSTEM DATA");
  text("survey-star", survey.star_class ? `STAR CLASS ${survey.star_class}` : "STAR CLASS —");
  text("survey-count", `${number(survey.scanned)} / ${survey.total_known ? number(survey.total) : "?"}`);
  text("survey-bio", `${number(survey.bio_signals)} SIGNALS`);
  text("survey-valuable", `${number(survey.valuable_count)} BODIES`);
  text("survey-region", intel.region, "UNKNOWN");
  text("survey-percent", survey.total_known ? `${Math.round(completion)}%` : "UNKNOWN");
  percentWidth("survey-progress", completion);
  const badge = byId("survey-badge");
  const badgeText = survey.complete ? "COMPLETE" : survey.undiscovered ? "NEW SYSTEM" : survey.total_known ? "IN PROGRESS" : "AWAITING";
  badge.textContent = badgeText;
  badge.style.color = survey.complete ? "var(--green)" : survey.undiscovered ? "var(--yellow)" : "var(--dim)";
  text("workboard-badge", survey.complete ? "COMPLETE" : "LIVE");
  text("workboard-system", state.flight?.system, "NO SYSTEM DATA");
  text("workboard-class", survey.star_class ? `PRIMARY · ${survey.star_class}` : "PRIMARY STAR · CLASS UNKNOWN");
  text("workboard-percent", survey.total_known ? `${Math.round(completion)}%` : "—");
  text("workboard-count", `${number(survey.scanned)} / ${survey.total_known ? number(survey.total) : "?"} BODIES`);

  const rows = Array.isArray(survey.notables) ? survey.notables : [];
  const notable = byId("survey-notables");
  if (!rows.length) {
    notable.className = "notable-list empty";
    notable.textContent = survey.total_known ? "No priority bodies or surface signals recorded yet." : "Awaiting scan telemetry.";
  } else {
    notable.className = "notable-list";
    notable.replaceChildren(...rows.slice(0, 4).map((item) => {
      const span = document.createElement("span");
      span.textContent = String(item);
      return span;
    }));
  }

  const bodies = Array.isArray(survey.bodies) ? survey.bodies : [];
  const workboard = byId("body-workboard");
  const orbits = byId("workboard-orbits");
  orbits.replaceChildren(...bodies.slice(0, 18).map((row, index) => {
    const marker = document.createElement("i");
    marker.className = [
      "workboard-body-marker",
      row.priority ? "priority" : "",
      row.mapped ? "mapped" : "",
      number(row.bio_count) ? "bio" : "",
      number(row.geo_count) ? "geo" : "",
      row.landable === true ? "landable" : "",
    ].filter(Boolean).join(" ");
    marker.style.setProperty("--body-index", String(index));
    marker.title = `${row.name || "Unknown body"} · ${row.detail || "Survey record"}`;
    const label = document.createElement("b");
    label.textContent = row.body_id > 0 ? String(row.body_id) : String(index + 1);
    marker.appendChild(label);
    return marker;
  }));
  orbits.classList.toggle("empty", bodies.length === 0);
  if (!bodies.length) {
    const empty = document.createElement("div");
    empty.className = "body-row empty";
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = "AWAITING FSS / DSS DATA";
    const detail = document.createElement("span");
    detail.textContent = "Priority bodies will appear as the system survey develops.";
    copy.append(title, detail);
    empty.append(copy);
    workboard.replaceChildren(empty);
  } else {
    workboard.replaceChildren(...bodies.slice(0, 18).map((row, index) => {
      const item = document.createElement("div");
      item.className = `body-row${row.priority ? " priority" : ""}${row.mapped ? " mapped" : ""}`;
      const indexNode = document.createElement("i");
      indexNode.textContent = row.body_id > 0 ? String(row.body_id).padStart(2, "0") : String(index + 1).padStart(2, "0");
      const copy = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = row.name || "UNKNOWN BODY";
      const detail = document.createElement("span");
      detail.textContent = row.detail || row.type || "SURVEY RECORD";
      copy.append(name, detail);
      const badgeNode = document.createElement("b");
      badgeNode.textContent = row.badge || "SCAN";
      item.append(indexNode, copy, badgeNode);
      return item;
    }));
  }
}

function renderRoute(state) {
  const route = state.route || {};
  text("route-badge", route.mode === "none" ? "NO ROUTE" : route.mode === "game" ? "GAME ROUTE" : "WAYPOINT PLAN");
  text("route-source", route.source, "NAVIGATION");
  text("route-next", route.next, "NO ACTIVE ROUTE");
  text("route-final", route.final ? `FINAL // ${route.final}` : "Plot a route in Elite or Mission Control.");
  text("route-progress-label", route.text, "INACTIVE");
  text("route-distance", route.distance_text, "— LY");
  text("route-remaining", `${number(route.remaining)} ${number(route.remaining) === 1 ? "JUMP" : "JUMPS"} LEFT`);
  percentWidth("route-progress", route.percent);
  byId("copy-next").disabled = !route.next;
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
  const data = state.data || {};
  const sources = state.sources || {};
  text("metric-fuel", flight.fuel_percent === null || flight.fuel_percent === undefined ? "—" : `${Math.round(number(flight.fuel_percent))}%`);
  text("metric-fuel-detail", flight.fuel_detail, "AWAITING LOADOUT");
  text("metric-data", formatCredits(data.unsold_total));
  text("metric-data-detail", data.unsold_bio ? `${formatCredits(data.unsold_bio)} BIOLOGICAL` : "EXPLORATION LEDGER");
  text("metric-distance", `${number(session.distance_ly).toLocaleString(undefined, {maximumFractionDigits: 1})} LY`);
  text("metric-jumps", `${number(session.jumps)} JUMPS`);
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
  const corePanels = [
    document.querySelector(".overview-modules > .decision-card"),
    document.querySelector(".overview-modules > .survey-card"),
    document.querySelector(".overview-modules > .telemetry-strip"),
  ];
  if (pageLayoutOwnsOrder) {
    corePanels.forEach((node) => { if (node) node.style.order = ""; });
  } else {
    const routeIndex = Math.max(0, order.indexOf("route"));
    if (corePanels[0]) corePanels[0].style.order = "0";
    if (corePanels[1]) corePanels[1].style.order = "1";
    if (corePanels[2]) corePanels[2].style.order = String(3 + routeIndex * 2);
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

function renderGalnetReader(state = model) {
  const articles = galnetArticles(state);
  if (!articles.some((row) => row.id === galnetSelectedId)) {
    galnetSelectedId = articles[Math.min(galnetTickerIndex, Math.max(0, articles.length - 1))]?.id || "";
  }
  const selected = articles.find((row) => row.id === galnetSelectedId) || articles[0];
  byId("galnet-headlines").replaceChildren(...articles.map((row) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `galnet-headline-row${row.id === selected?.id ? " active" : ""}`;
    button.dataset.galnetSelect = row.id || "";
    const stamp = document.createElement("small"); stamp.textContent = row.stamp || "GALNET";
    const title = document.createElement("strong"); title.textContent = row.title || "UNTITLED DISPATCH";
    button.append(stamp, title);
    return button;
  }));
  text("galnet-reader-status", state.galnet?.detail || "Galnet relay");
  text("galnet-article-stamp", selected?.stamp || "NO DISPATCH SELECTED");
  text("galnet-article-title", selected?.title || "GALNET RELAY");
  text("galnet-article-body", selected?.body || "No Galnet dispatch is available yet.");
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
  text("intel-value", formatCredits(data.unsold_total));
  setFactList("intel-facts", [
    ["Current region", intel.region || "UNKNOWN"],
    ["First discoveries", String(number(intel.first_discoveries))],
    ["First footfalls", String(number(intel.first_footfalls))],
    ["Bio completion", `${number(survey.bio_complete)} / ${number(survey.bio_signals)}`],
    ["Geological signals", String(number(survey.geo_signals))],
  ]);
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
  text("expedition-detail", active ? expedition.detail : "Create or resume a named expedition in Mission Control.");
  const total = number(expedition.total);
  const complete = number(expedition.complete);
  percentWidth("expedition-progress", total ? (complete / total) * 100 : 0);
  text("expedition-progress-label", `${complete} / ${total}`);
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
  return model.overlay_studio || {desktop: {}, overlays: [], presets: [], options: {}};
}

function studioOverlay(id) {
  return (studioData().overlays || []).find((row) => row.id === id) || null;
}

function selectStudioOverlay(id) {
  const selected = studioOverlay(id);
  if (!selected) return;
  studioSelectedId = id;
  document.querySelectorAll(".studio-overlay-card, .studio-index-row").forEach((node) => {
    node.classList.toggle("selected", node.dataset.overlayId === id);
  });
  text("studio-selected-state", selected.state, "READY");
  text("studio-selected-short", selected.short_label, "SURFACE");
  text("studio-selected-name", selected.label, "Overlay");
  text("studio-selected-metrics", `${selected.x}, ${selected.y}  //  ${selected.width} × ${selected.height} PX`);
  text("studio-selected-position", `X ${selected.x} · Y ${selected.y}`);
  text("studio-selected-size", `${selected.width} × ${selected.height} PX`);
  text("studio-selected-renderer", selected.html_ready ? "HTML READY" : selected.enabled ? "LINKING" : "STANDBY");
  text("studio-selected-visibility", selected.shown ? "ON SCREEN" : selected.enabled ? "READY" : "DISABLED");
  const toggle = byId("studio-toggle-selected");
  toggle.textContent = selected.enabled ? "DISABLE" : "ENABLE";
  toggle.classList.toggle("enabled", selected.enabled);
}

function applyStudioFilters() {
  const queryText = studioSearch.trim().toLocaleLowerCase();
  const matches = (row) => {
    if (!row) return false;
    const stateMatch = studioFilter === "all" || (studioFilter === "enabled" && row.enabled) || (studioFilter === "disabled" && !row.enabled) || (studioFilter === "visible" && row.shown);
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

function setStudioView(name) {
  studioView = name === "options" ? "options" : "layout";
  document.querySelectorAll("[data-studio-view]").forEach((node) => node.classList.toggle("active", node.dataset.studioView === studioView));
  byId("studio-layout-view").classList.toggle("active", studioView === "layout");
  byId("studio-options-view").classList.toggle("active", studioView === "options");
}

function updateStudioOptionControls(options, groundTarget = {}) {
  document.querySelectorAll("[data-overlay-option]").forEach((input) => {
    if (document.activeElement !== input) input.checked = Boolean(options[input.dataset.overlayOption]);
  });
  const fields = {
    "studio-text-scale": options.overlay_text_scale_percent,
    "studio-overlay-opacity": options.overlay_opacity_percent,
    "studio-prospector-timeout": options.prospector_hud_timeout_s,
    "studio-gravity-timeout": options.gravity_warning_hud_timeout_s,
    "studio-station-timeout": options.station_info_timeout_s,
    "studio-gravity-threshold": options.gravity_warning_threshold_g,
    "studio-crt-intensity": options.hud_crt_intensity,
  };
  for (const [id, value] of Object.entries(fields)) {
    const field = byId(id);
    if (field && document.activeElement !== field) field.value = value ?? "";
  }
  const opacityField = byId("studio-overlay-opacity");
  const opacityValue = document.activeElement === opacityField
    ? opacityField.value : options.overlay_opacity_percent;
  text("studio-overlay-opacity-value", `${Math.max(40, Math.min(100, Math.round(number(opacityValue, 100))))}%`);
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
  const groundOverlay = studioOverlay("ground_popup");
  const overlayEnabled = Boolean(groundOverlay?.enabled);
  const state = groundTarget.navigation_ready ? "COMPASS LIVE" : groundTarget.active ? "TARGET ARMED" : "TARGET OFF";
  text("studio-ground-target-state", state);
  text("studio-ground-target-detail", groundTarget.active
    ? `${Number(groundTarget.lat).toFixed(6)}, ${Number(groundTarget.lon).toFixed(6)}`
    : "NO COORDINATES SET");
  text("studio-ground-visibility", !overlayEnabled
    ? "OVERLAY DISABLED"
    : groundTarget.navigation_ready ? "LIVE PLANET GUIDANCE" : "HIDDEN UNTIL PLANET APPROACH");
  const readout = document.querySelector(".studio-ground-readout");
  readout?.classList.toggle("live", Boolean(groundTarget.navigation_ready && overlayEnabled));
  readout?.classList.toggle("armed", Boolean(groundTarget.active && !groundTarget.navigation_ready && overlayEnabled));
  const current = byId("studio-ground-current");
  if (current) current.disabled = !Boolean(groundTarget.current_available);
  const clear = byId("studio-ground-clear");
  if (clear) clear.disabled = !Boolean(groundTarget.active);
  const toggle = byId("studio-ground-overlay-toggle");
  if (toggle) toggle.textContent = `OVERLAY ${overlayEnabled ? "ON" : "OFF"}`;
}

function renderOverlayStudio(state) {
  const studio = state.overlay_studio || {};
  const desktop = studio.desktop || {};
  const overlays = Array.isArray(studio.overlays) ? studio.overlays : [];
  const desktopWidth = Math.max(1, number(desktop.width, 1920));
  const desktopHeight = Math.max(1, number(desktop.height, 1080));
  const left = number(desktop.left);
  const top = number(desktop.top);
  const primary = desktop.primary || {left: 0, top: 0, width: desktopWidth, height: desktopHeight};
  if (!studioSelectedId || !overlays.some((row) => row.id === studioSelectedId)) {
    studioSelectedId = overlays.find((row) => row.enabled)?.id || overlays[0]?.id || "";
  }

  const fingerprint = JSON.stringify({desktop, overlays});
  if (!studioDragging && fingerprint !== studioFingerprint) {
    studioFingerprint = fingerprint;
    const desktopNode = byId("studio-desktop");
    desktopNode.style.aspectRatio = `${desktopWidth} / ${desktopHeight}`;
    const primaryNode = byId("studio-primary-monitor");
    primaryNode.style.left = `${(number(primary.left) - left) * 100 / desktopWidth}%`;
    primaryNode.style.top = `${(number(primary.top) - top) * 100 / desktopHeight}%`;
    primaryNode.style.width = `${number(primary.width, desktopWidth) * 100 / desktopWidth}%`;
    primaryNode.style.height = `${number(primary.height, desktopHeight) * 100 / desktopHeight}%`;

    const cards = overlays.map((row) => {
      const node = document.createElement("button");
      node.type = "button";
      node.className = `studio-overlay-card${row.enabled ? " enabled" : " disabled"}${row.shown ? " shown" : ""}`;
      node.dataset.overlayId = row.id;
      node.style.left = `${(row.x - left) * 100 / desktopWidth}%`;
      node.style.top = `${(row.y - top) * 100 / desktopHeight}%`;
      node.style.width = `${Math.max(1.2, row.width * 100 / desktopWidth)}%`;
      node.style.height = `${Math.max(1.8, row.height * 100 / desktopHeight)}%`;
      node.innerHTML = `<span>${escapeHtml(row.short_label)}</span><small>${escapeHtml(row.state)}</small>`;
      return node;
    });
    byId("studio-overlay-cards").replaceChildren(...cards);

    const index = overlays.map((row) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `studio-index-row${row.enabled ? " enabled" : ""}${row.shown ? " shown" : ""}`;
      button.dataset.overlayId = row.id;
      button.innerHTML = `<i></i><span><b>${escapeHtml(row.label)}</b><small>X ${row.x} · Y ${row.y} · ${row.width} × ${row.height}</small></span><em>${escapeHtml(row.state)}</em>`;
      return button;
    });
    byId("studio-overlay-index").replaceChildren(...index);

    const modules = overlays.map((row) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = row.enabled ? "enabled" : "";
      button.dataset.overlayToggle = row.id;
      button.textContent = `${row.short_label}  //  ${row.enabled ? "ON" : "OFF"}`;
      return button;
    });
    byId("studio-module-grid").replaceChildren(...modules);
    applyStudioFilters();
  }

  const enabled = overlays.filter((row) => row.enabled).length;
  const shown = overlays.filter((row) => row.shown).length;
  const htmlReady = overlays.filter((row) => row.html_ready).length;
  text("studio-enabled-count", `${enabled} ENABLED`);
  text("studio-total-count", overlays.length);
  text("studio-enabled-total", enabled);
  text("studio-live-count", shown);
  text("studio-html-count", htmlReady);
  text("studio-desktop-label", `${desktopWidth} × ${desktopHeight} // ${overlays.length} SURFACES`);
  const presetSelect = byId("studio-preset-select");
  const previousPreset = presetSelect.value;
  const presetNames = Array.isArray(studio.presets) ? studio.presets : [];
  const presetKey = presetNames.join("\u0000");
  if (presetSelect.dataset.presets !== presetKey) {
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = presetNames.length ? "SELECT SAVED LAYOUT" : "NO SAVED LAYOUTS";
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

function orreryLayout(bodies = []) {
  if (!bodies.length) return {nodes: [], orbits: []};
  const nodes = [];
  const orbits = [];
  const byId = new Map(bodies.map((row) => [String(row.id), row]));
  const positions = new Map();
  const stars = bodies.filter((row) => row.kind === "star");
  const primaryStars = stars.length ? stars : bodies.slice(0, 1);
  primaryStars.forEach((row, index) => {
    const angle = primaryStars.length === 1 ? 0 : index * Math.PI * 2 / primaryStars.length;
    const radius = primaryStars.length === 1 ? 0 : 36;
    positions.set(String(row.id), {x: 360 + Math.cos(angle) * radius, y: 250 + Math.sin(angle) * radius});
  });
  const rootPlanets = bodies.filter((row) => row.kind !== "star" && (!row.parent_id || byId.get(String(row.parent_id))?.kind === "star"));
  rootPlanets.sort((a, b) => number(a.semi_major_axis, number(a.distance_ls)) - number(b.semi_major_axis, number(b.distance_ls)) || number(a.body_id) - number(b.body_id));
  const radialStep = Math.min(33, 184 / Math.max(1, rootPlanets.length));
  rootPlanets.forEach((row, index) => {
    const radius = 54 + radialStep * index;
    const eccentricity = clamp(number(row.eccentricity), 0, .82);
    const rx = radius * (1 + eccentricity * .22);
    const ry = radius * (.62 - eccentricity * .12);
    const angle = ((number(row.body_id, index + 1) * 137.508) % 360) * Math.PI / 180;
    const x = 360 + Math.cos(angle) * rx;
    const y = 250 + Math.sin(angle) * ry;
    positions.set(String(row.id), {x, y});
    orbits.push({cx: 360, cy: 250, rx, ry, id: row.id});
  });
  const pending = bodies.filter((row) => !positions.has(String(row.id)));
  for (let pass = 0; pass < 4 && pending.length; pass += 1) {
    for (let index = pending.length - 1; index >= 0; index -= 1) {
      const row = pending[index];
      const parent = positions.get(String(row.parent_id));
      if (!parent) continue;
      const siblings = bodies.filter((item) => String(item.parent_id) === String(row.parent_id));
      const siblingIndex = Math.max(0, siblings.findIndex((item) => String(item.id) === String(row.id)));
      const radius = 14 + siblingIndex * 6;
      const angle = ((number(row.body_id, siblingIndex + 1) * 111.25) % 360) * Math.PI / 180;
      positions.set(String(row.id), {x: parent.x + Math.cos(angle) * radius, y: parent.y + Math.sin(angle) * radius});
      orbits.push({cx: parent.x, cy: parent.y, rx: radius, ry: radius * .7, id: row.id, moon: true});
      pending.splice(index, 1);
    }
  }
  for (const row of bodies) {
    const point = positions.get(String(row.id)) || {x: 360, y: 250};
    nodes.push({...row, ...point});
  }
  return {nodes, orbits};
}

function orrerySvg(orrery = {}) {
  const bodies = orrery.bodies || [];
  if (!bodies.length) return `<div class="orrery-empty"><i></i><b>AWAITING SYSTEM SCANS</b><span>Honk or begin FSS to assemble the live architecture.</span></div>`;
  const layout = orreryLayout(bodies);
  const orbits = layout.orbits.map((row) => `<ellipse cx="${row.cx}" cy="${row.cy}" rx="${row.rx}" ry="${row.ry}" class="${row.moon ? "moon-orbit" : "planet-orbit"}"/>`).join("");
  const nodes = layout.nodes.map((row) => {
    const classes = [row.kind, row.bio ? "bio" : "", row.geo ? "geo" : "", row.terraformable ? "terraformable" : "", row.mapped ? "mapped" : "", row.targeted ? "targeted" : ""].filter(Boolean).join(" ");
    const radius = row.kind === "star" ? 10 : row.rings ? 6 : 4.5;
    const targetReticle = row.targeted ? `<g class="orrery-target-reticle" transform="translate(${row.x} ${row.y})"><circle r="${radius + 12}"/><path d="M-${radius + 19} 0H-${radius + 9}M${radius + 9} 0H${radius + 19}M0 -${radius + 19}V-${radius + 9}M0 ${radius + 9}V${radius + 19}"/></g>` : "";
    return `<g class="orrery-node ${classes}" data-orrery-body="${escapeHtml(row.id)}" tabindex="0" role="button">${targetReticle}<circle cx="${row.x}" cy="${row.y}" r="${radius}"/>${row.rings ? `<ellipse cx="${row.x}" cy="${row.y}" rx="${radius + 5}" ry="${radius + 1.5}"/>` : ""}<title>${escapeHtml(row.name)} · ${escapeHtml(row.class)}${row.targeted ? " · ELITE TARGET" : ""}</title></g>`;
  }).join("");
  return `<svg class="orrery-chart" viewBox="0 0 720 500" role="img" aria-label="Schematic system architecture"><defs><radialGradient id="orrery-star"><stop offset="0" stop-color="#fff"/><stop offset=".3" stop-color="var(--orange)"/><stop offset="1" stop-color="transparent"/></radialGradient></defs><path class="orrery-axis" d="M360 18V482M18 250H702"/>${orbits}<g class="orrery-sweep"><path d="M360 250L688 250"/></g>${nodes}<text x="20" y="28">${escapeHtml(orrery.mode || "JOURNAL ARCHITECTURE")}</text></svg>`;
}

function orreryDetail(body) {
  if (!body) return `<p class="workspace-empty">Select a body in the system architecture.</p>`;
  const period = body.orbital_period ? `${numeric(body.orbital_period / 86400, 2)} DAYS` : "UNREPORTED";
  return `<div class="orrery-body-title"><i class="${escapeHtml(body.kind)}"></i><div><small>BODY ${escapeHtml(body.body_id ?? "—")}</small><h3>${escapeHtml(body.name)}</h3><span>${escapeHtml(body.class)}</span></div><b>${credits(body.value)}</b></div><div class="orrery-facts"><span>ORBIT <b>${period}</b></span><span>DISTANCE <b>${body.distance_ls === null ? "—" : `${numeric(body.distance_ls, 1)} LS`}</b></span><span>GRAVITY <b>${body.gravity_g === null ? "—" : `${numeric(body.gravity_g, 2)} G`}</b></span><span>ATMOSPHERE <b>${escapeHtml(body.atmosphere || "AIRLESS")}</b></span><span>BIOLOGY <b>${numeric(body.bio_complete)} / ${numeric(body.bio)}</b></span><span>GEOLOGY <b>${numeric(body.geo)}</b></span></div><div class="orrery-flags">${(body.flags || []).map((flag) => `<em>${escapeHtml(flag)}</em>`).join("") || "<em>STANDARD SURVEY RECORD</em>"}</div>`;
}

function stellarCartographyMarkup(cartography = {}) {
  const orrery = cartography.orrery || {};
  const queue = cartography.queue || {};
  const bodies = orrery.bodies || [];
  const liveTarget = orrery.target || cartography.target || {};
  const targetId = liveTarget.resolved && liveTarget.id !== null && liveTarget.id !== undefined ? String(liveTarget.id) : "";
  if (targetId && targetId !== orreryLiveTargetBodyId) {
    orreryLiveTargetBodyId = targetId;
    orrerySelectedBodyId = targetId;
  } else if (!targetId) {
    orreryLiveTargetBodyId = "";
  }
  if (!orrerySelectedBodyId || !bodies.some((row) => String(row.id) === String(orrerySelectedBodyId))) orrerySelectedBodyId = String(bodies[0]?.id || "");
  const selected = bodies.find((row) => String(row.id) === String(orrerySelectedBodyId));
  const queueRows = (queue.rows || []).map((row) => `<div class="survey-queue-row ${escapeHtml(row.status)}${row.targeted ? " targeted" : ""}"><i>${row.targeted ? "⌖" : row.status === "complete" ? "✓" : row.status === "skipped" ? "–" : row.pinned ? "◆" : String(number(row.score)).padStart(2, "0")}</i><span><b>${escapeHtml(row.body)}${row.targeted ? " <strong>ELITE TARGET</strong>" : ""}</b><small>${escapeHtml(row.action)} · ${escapeHtml(row.reason)}</small><em>${row.distance_ls ? `${numeric(row.distance_ls, 0)} LS · ` : ""}${credits(row.value)}</em></span><div><button data-ws-page="explore" data-ws-op="survey_pin" data-body-key="${escapeHtml(row.key)}" data-system="${escapeHtml(cartography.system || "")}">${row.pinned ? "UNPIN" : "PIN"}</button><button data-ws-page="explore" data-ws-op="survey_complete" data-body-key="${escapeHtml(row.key)}" data-system="${escapeHtml(cartography.system || "")}">${row.status === "complete" && row.manual_complete ? "REOPEN" : "DONE"}</button><button data-ws-page="explore" data-ws-op="survey_skip" data-body-key="${escapeHtml(row.key)}" data-system="${escapeHtml(cartography.system || "")}">${row.status === "skipped" ? "RESTORE" : "SKIP"}</button></div></div>`);
  return `<section class="stellar-cartography">
    <header><div><small>STELLAR CARTOGRAPHY // LIVE SYSTEM MODEL</small><h3>${escapeHtml(cartography.system || "AWAITING SYSTEM")}</h3><span>${numeric(orrery.stars)} STARS · ${numeric(orrery.planets)} PLANETS · ${numeric(orrery.mapped)} MAPPED</span></div><div><b>${numeric(queue.pending)} ACTIVE</b><span>${numeric(queue.complete)} COMPLETE · ${numeric(queue.skipped)} SKIPPED</span></div></header>
    ${liveTarget.resolved ? `<div class="cartography-target-lock"><i>⌖</i><span><small>ELITE NAVIGATION TARGET</small><b>${escapeHtml(liveTarget.name || "TARGETED BODY")}</b></span><em>BODY ${escapeHtml(liveTarget.body_id ?? "—")} · LOCKED IN ORRERY & SURVEY QUEUE</em></div>` : ""}
    <div class="stellar-grid">
      ${workspaceCard("LIVE SYSTEM ORRERY", `${orrerySvg(orrery)}<div id="orrery-detail" class="orrery-detail">${orreryDetail(selected)}</div>`, `${numeric((orrery.bodies || []).length)} BODIES`, "orrery-card")}
      ${workspaceCard("EXPLORATION SURVEY QUEUE", `${queue.next ? `<div class="survey-next"><small>NEXT RECOMMENDATION</small><b>${escapeHtml(queue.next.body)}</b><span>${escapeHtml(queue.next.action)} · ${escapeHtml(queue.next.reason)}</span></div>` : ""}${workspaceRows(queueRows, "FSS body records will create a prioritised survey queue.")}<div class="workspace-actions"><button data-ws-page="explore" data-ws-op="survey_reset" data-system="${escapeHtml(cartography.system || "")}">RESET COMMANDER CHOICES</button></div>`, `${numeric(queue.pending)} PENDING`, "survey-queue-card")}
    </div>
  </section>`;
}

function renderExploreWorkspace(data) {
  const root = byId("explore-workspace");
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
  root.classList.remove("loading-panel");
  root.innerHTML = `${workspaceMetrics([
    {label: "Current system", value: data.current || "—", detail: data.destination ? `NAV TARGET · ${data.destination}` : "NO LOCAL NAV TARGET"},
    {label: "Elite route", value: `${numeric((data.nav_route || []).length)} STOPS`, detail: (data.nav_route || []).length ? "LIVE NAVROUTE.JSON" : "NO ROUTE PLOTTED IN GAME"},
    {label: "Saved waypoints", value: numeric((data.waypoints || []).length), detail: data.next_waypoint ? `NEXT · ${data.next_waypoint}` : "ROUTE COMPLETE / EMPTY"},
    {label: "Survey queue", value: `${numeric(data.cartography?.queue?.pending)} ACTIVE`, detail: data.cartography?.queue?.next ? `NEXT · ${data.cartography.queue.next.body}` : "SYSTEM WORK COMPLETE"},
  ])}${stellarCartographyMarkup(data.cartography || {})}<section class="workspace-grid route-workspace-grid">
    ${workspaceCard("ELITE NAV ROUTE", workspaceRows(navRows, "Plot a route in Elite to populate the live NavRoute."), `${(data.nav_route || []).length} STOPS`)}
    ${workspaceCard("PROFILE WAYPOINT ROUTE", `${workspaceRows(waypointRows, "No saved waypoints. Add a destination below or import a plotted route.")}<div class="route-add-form"><input id="waypoint-name" placeholder="SYSTEM NAME"><input id="waypoint-note" placeholder="OPTIONAL NOTE"><button data-ws-page="explore" data-ws-op="add_waypoint">ADD</button></div><div class="workspace-actions wrap"><button data-ws-page="explore" data-ws-op="copy_next">COPY NEXT</button><button data-ws-page="explore" data-ws-op="set_auto_copy" data-enabled="${!data.auto_copy}">AUTO COPY ${data.auto_copy ? "ON" : "OFF"}</button><button class="danger-action" data-ws-page="explore" data-ws-op="clear_waypoints">CLEAR ROUTE</button></div>`, `${(data.waypoints || []).filter((row) => row.visited).length}/${(data.waypoints || []).length} COMPLETE`)}
    ${workspaceCard("SPANSH NEUTRON PLOTTER", `<div class="neutron-form"><label>FROM<input id="neutron-from" value="${escapeHtml(data.plotter?.from || data.current || "")}"></label><label>DESTINATION<input id="neutron-to" value="${escapeHtml(data.plotter?.to || "")}"></label><label>SHIP RANGE<input id="neutron-range" type="number" min="1" step="0.1" value="${number(data.plotter?.range, 30)}"></label><label>EFFICIENCY<input id="neutron-efficiency" type="number" min="1" max="100" value="${number(data.plotter?.efficiency, 60)}"></label><label>BOOST<select id="neutron-multiplier"><option value="4" ${number(data.plotter?.multiplier, 4) === 4 ? "selected" : ""}>NEUTRON 4×</option><option value="6" ${number(data.plotter?.multiplier, 4) === 6 ? "selected" : ""}>OVERCHARGE 6×</option></select></label><button class="primary" data-ws-page="explore" data-ws-op="neutron_plot" ${data.plotter?.status === "working" ? "disabled" : ""}>${data.plotter?.status === "working" ? "PLOTTING…" : "PLOT ROUTE"}</button></div><p class="workspace-status ${escapeHtml(data.plotter?.status || "ready")}">${escapeHtml(data.plotter?.detail || "Ready.")}</p>${plottedRows}<div class="workspace-actions wrap"><button data-ws-page="explore" data-ws-op="neutron_copy" ${plotted.waypoints?.length ? "" : "disabled"}>COPY LIST</button><button data-ws-page="explore" data-ws-op="neutron_import" ${plotted.waypoints?.length ? "" : "disabled"}>IMPORT TO WAYPOINTS</button><button data-ws-page="explore" data-ws-op="neutron_clear" ${plotted.waypoints?.length ? "" : "disabled"}>CLEAR RESULT</button></div>`, plotted.total_jumps ? `${numeric(plotted.total_jumps)} JUMPS` : "MANUAL ROUTE", "neutron-plotter-card")}
  </section>`;
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
  root.classList.remove("loading-panel");
  root.innerHTML = `
    <section class="workspace-hero"><div><small>ACTIVE COMMANDER // ${escapeHtml(data.key)}</small><h3>${escapeHtml(data.name)}</h3><span>${escapeHtml(data.fid || "FID awaiting journal")} · ${escapeHtml(ship.name || ship.type || "No active ship")}</span></div><div><button data-ws-page="profile" data-ws-op="open_folder">OPEN PROFILE FOLDER</button><button data-ws-page="profile" data-ws-op="backup_picker">BACKUP</button><button data-ws-page="profile" data-ws-op="restore_picker">RESTORE</button></div></section>
    ${workspaceMetrics([
      {label: "Credits", value: credits(data.balance), detail: data.session_credit_delta === null ? "LIVE BALANCE" : `${data.session_credit_delta >= 0 ? "+" : ""}${credits(data.session_credit_delta)} THIS SESSION`},
      {label: "Active vessel", value: ship.name || ship.type || "—", detail: `${ship.type || "SHIP"} · ${ship.ident || "NO IDENT"}`},
      {label: "Achievements", value: `${numeric(achievements.unlocked)} / ${numeric(achievements.total)}`, detail: `${numeric(achievements.points)} POINTS`},
      {label: "Captain's Log", value: `${numeric(log.sessions)} FLIGHTS`, detail: `${numeric(log.distance, 1)} LY · ${numeric(log.jumps)} JUMPS`},
    ])}
    <section class="workspace-grid two">
      ${workspaceCard("CAREER RANKS", workspaceRows(rankRows, "Awaiting Rank and Progress journal events."), `${rankRows.length} TRACKED`)}
      ${workspaceCard("SUPERPOWER REPUTATION", workspaceRows(repRows, "Awaiting Reputation journal data."))}
      ${workspaceCard("CAREER RECORDS", `<div class="fact-list spacious">${careerRows.join("") || "<p class='workspace-empty'>Elite will provide lifetime statistics through its Statistics event.</p>"}</div>`)}
      ${workspaceCard("ACTIVE SHIP & LOADOUT", `<div class="profile-ship-grid"><div><span>TYPE</span><b>${escapeHtml(ship.type || "—")}</b></div><div><span>IDENT</span><b>${escapeHtml(ship.ident || "—")}</b></div><div><span>CARGO</span><b>${numeric(ship.cargo)} T</b></div><div><span>JUMP RANGE</span><b>${numeric(ship.jump_range, 2)} LY</b></div><div><span>REBUY</span><b>${credits(ship.rebuy)}</b></div><div><span>HULL</span><b>${ship.hull === null || ship.hull === undefined ? "—" : `${numeric(Number(ship.hull) * 100, 1)}%`}</b></div></div><div class="workspace-actions"><button data-ws-page="profile" data-ws-op="open_edsy" ${data.loadout_ready ? "" : "disabled"}>OPEN IN EDSY</button><button data-ws-page="profile" data-ws-op="copy_slef" ${data.loadout_ready ? "" : "disabled"}>COPY SLEF</button></div>`, data.loadout_ready ? "EXPORT READY" : "AWAITING LOADOUT")}
      ${workspaceCard(`STORED FLEET · ${(data.fleet || []).length}`, fleet)}
      ${workspaceCard("FLEET CARRIER", `<div class="fact-list spacious"><div><span>CARRIER</span><b>${escapeHtml(data.carrier?.name || "NO OWNED CARRIER DATA")}</b></div><div><span>CALLSIGN</span><b>${escapeHtml(data.carrier?.callsign || "—")}</b></div><div><span>LOCATION</span><b>${escapeHtml(data.carrier?.system || "—")}</b></div><div><span>TRITIUM</span><b>${numeric(data.carrier?.fuel)} T</b></div></div><div class="workspace-actions"><button data-page="carrier">OPEN CARRIER COMMAND</button></div>`)}
      ${workspaceCard(`MISSION RESPONSIBILITIES · ${(data.missions || []).length}`, missions)}
      ${workspaceCard("PROFILE CUSTODY", `<div class="fact-list spacious"><div><span>PROFILE KEY</span><b>${escapeHtml(data.key)}</b></div><div><span>PROFILE FOLDER</span><b class="path-value">${escapeHtml(data.folder)}</b></div><div><span>EDSM UPLOAD</span><b>${data.integrations?.edsm ? "ON" : "OFF"}</b></div><div><span>EDDN MARKET</span><b>${data.integrations?.eddn ? "ON" : "OFF"}</b></div><div><span>CARRIER DISCORD</span><b>${data.integrations?.discord ? "CONFIGURED" : "OFF"}</b></div></div>`)}
    </section>`;
}

function analyticsBars(rows, key, colour = "accent") {
  const recent = [...rows].reverse().slice(-40);
  const max = Math.max(1, ...recent.map((row) => number(row[key])));
  return `<div class="analytics-bars">${recent.map((row) => `<i class="${colour}" style="height:${Math.max(3, number(row[key]) * 100 / max)}%" title="${escapeHtml(row.started || "Session")} · ${numeric(row[key], key === "distance" ? 1 : 0)}"></i>`).join("") || "<span>NO SESSION SERIES</span>"}</div>`;
}

function renderAnalyticsWorkspace(data) {
  const root = byId("analytics-workspace");
  const rows = data.sessions || [];
  const totals = rows.reduce((sum, row) => ({jumps: sum.jumps + number(row.jumps), distance: sum.distance + number(row.distance), fss: sum.fss + number(row.fss), dss: sum.dss + number(row.dss), bio: sum.bio + number(row.bio)}), {jumps: 0, distance: 0, fss: 0, dss: 0, bio: 0});
  const science = data.science || {};
  const passport = data.passport || {};
  const distribution = (items, colour = "accent") => {
    const maximum = Math.max(1, ...(items || []).map((row) => number(row.count)));
    return `<div class="science-distribution">${(items || []).map((row) => `<div><span>${escapeHtml(row.label)}</span><i><em class="${colour}" style="width:${number(row.count) * 100 / maximum}%"></em></i><b>${numeric(row.count)}</b></div>`).join("") || `<p class="workspace-empty">More retained scan evidence is required.</p>`}</div>`;
  };
  const species = workspaceTable([
    {label: "Species", render: (row) => `<b>${escapeHtml(row.name)}</b><small>${escapeHtml(row.genus)}</small>`},
    {label: "Analyses", key: "analyses"}, {label: "Worlds", key: "worlds"}, {label: "Systems", key: "systems"},
    {label: "Base value", render: (row) => credits(row.value)},
  ], science.species || [], "Analysed organic species will form the ecology index.");
  const regionCards = (passport.rows || []).map((row) => `<article class="region-passport-card${row.visited ? " visited" : ""}"><header><i>${String(row.id).padStart(2, "0")}</i><b>${row.visited ? "VISITED" : "UNSTAMPED"}</b></header><h4>${escapeHtml(row.name)}</h4><p>${row.visited ? `${numeric(row.systems)} systems · ${numeric(row.distance, 1)} LY` : "No commander visit retained"}</p><div><span>FSS <b>${numeric(row.fss)}</b></span><span>DSS <b>${numeric(row.dss)}</b></span><span>BIO <b>${numeric(row.biology)}</b></span><span>CODEX <b>${numeric(row.codex)}</b></span></div><footer>${escapeHtml(row.last_system || "REGION AWAITS EXPLORATION")}</footer></article>`).join("");
  root.classList.remove("loading-panel");
  root.innerHTML = `<nav class="workspace-tabs analytics-tabs"><button data-analytics-view="trends">FLIGHT TRENDS</button><button data-analytics-view="science">EXPLORER SCIENCE LAB</button><button data-analytics-view="passport">GALACTIC REGION PASSPORT</button></nav>
  <section data-analytics-panel="trends">${workspaceMetrics([
    {label: "Current duration", value: data.current?.elapsed || "00:00:00", detail: `${numeric(data.current?.systems)} SYSTEMS`},
    {label: "Current travel", value: `${numeric(data.current?.distance, 1)} LY`, detail: `${numeric(data.current?.jumps)} JUMPS`},
    {label: "Retained sessions", value: numeric(rows.length), detail: `${numeric(totals.distance, 1)} LY TOTAL`},
    {label: "Survey operations", value: numeric(totals.fss + totals.dss + totals.bio), detail: `${numeric(totals.fss)} FSS · ${numeric(totals.dss)} DSS · ${numeric(totals.bio)} BIO`},
  ])}<section class="workspace-grid two">
    ${workspaceCard("DISTANCE BY FLIGHT", analyticsBars(rows, "distance"), "RECENT 40")}
    ${workspaceCard("SURVEY ACTIVITY", analyticsBars(rows, "fss", "orange"), "FSS SERIES")}
    ${workspaceCard("FLIGHT SESSION HISTORY", workspaceTable([
      {label: "Started", render: (row) => escapeHtml(String(row.started || "—").replace("T", " ").slice(0, 16))},
      {label: "Route", render: (row) => `${escapeHtml(row.start_system)}<small>→ ${escapeHtml(row.end_system)}</small>`},
      {label: "Jumps", key: "jumps"}, {label: "Distance", render: (row) => `${numeric(row.distance, 1)} LY`},
      {label: "FSS", key: "fss"}, {label: "DSS", key: "dss"}, {label: "Bio", key: "bio"},
    ], rows, "No Captain's Log sessions have been retained yet."), `${rows.length} SESSIONS`, "flight-history-card")}
  </section></section>
  <section data-analytics-panel="science">${workspaceMetrics([
    {label: "Indexed systems", value: numeric(science.systems), detail: `${numeric(science.bodies)} PLANETARY BODIES`},
    {label: "Biological worlds", value: numeric(science.biological_bodies), detail: `${numeric(science.species_total)} SPECIES`},
    {label: "Organic analyses", value: numeric(science.analyses), detail: "JOURNAL-CONFIRMED RECORDS"},
    {label: "Notable worlds", value: numeric(science.valuable), detail: `${numeric(science.terraformable)} TERRAFORMABLE`},
  ])}<section class="workspace-grid two science-grid">${workspaceCard("ORGANIC ECOLOGY INDEX", species, `${numeric(science.species_total)} SPECIES`, "science-index-card")}${workspaceCard("BIOLOGY BY ATMOSPHERE", distribution(science.atmospheres), `${numeric(science.biological_bodies)} WORLDS`)}${workspaceCard("BIOLOGY BY GRAVITY", distribution(science.gravity, "orange"))}${workspaceCard("WORLD CLASS MIX", distribution(science.body_classes))}${workspaceCard("STELLAR CLASS MIX", distribution(science.star_classes, "orange"))}</section></section>
  <section data-analytics-panel="passport">${workspaceMetrics([
    {label: "Regions stamped", value: `${numeric(passport.visited)} / ${numeric(passport.total)}`, detail: `${numeric(passport.percent, 1)}% OF GALACTIC REGIONS`},
    {label: "Systems indexed", value: numeric(passport.systems), detail: "REGION-ASSIGNED VISITS"},
    {label: "Regional travel", value: `${numeric(passport.distance, 1)} LY`, detail: "RETAINED JUMP DISTANCE"},
    {label: "Biology", value: numeric(passport.biology), detail: "ANALYSES BY REGION"},
  ])}<div class="passport-actions"><span>Each stamp is profile-local and derived from retained journal coordinates.</span><button data-page="map">OPEN GALACTIC ATLAS</button></div><section class="region-passport-grid">${regionCards}</section></section>`;
  document.querySelectorAll("[data-analytics-view]").forEach((button) => button.classList.toggle("active", button.dataset.analyticsView === analyticsView));
  document.querySelectorAll("[data-analytics-panel]").forEach((panel) => { panel.hidden = panel.dataset.analyticsPanel !== analyticsView; });
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

function renderChronicleWorkspace(data) {
  const root = byId("chronicle-workspace");
  const sessions = data.sessions || [];
  if (replayTimer) { clearInterval(replayTimer); replayTimer = 0; }
  const cards = sessions.map((session) => {
    const highlights = (session.highlights || []).map((row) => `<div class="chronicle-event"><b>${escapeHtml(row.kind)}</b><p><strong>${escapeHtml(row.title)}</strong><span>${escapeHtml(row.detail)}</span></p><time>${escapeHtml(String(row.timestamp || "").replace("T", " ").slice(0, 16))}</time></div>`);
    return workspaceCard(`${String(session.started || "UNKNOWN SESSION").replace("T", " ").slice(0, 16)}`, `<div class="chronicle-summary"><strong>${escapeHtml(session.start_system)} → ${escapeHtml(session.end_system)}</strong><span>${numeric(session.jumps)} jumps · ${numeric(session.distance, 1)} ly · ${numeric(session.fss)} FSS · ${numeric(session.dss)} DSS · ${numeric(session.bio)} bio</span></div>${workspaceRows(highlights, "No notable highlights were retained for this flight.")}`, session.ended ? "COMPLETE" : "ACTIVE");
  });
  root.classList.remove("loading-panel");
  root.innerHTML = `${workspaceMetrics([
    {label: "Flights", value: numeric(sessions.length), detail: "PROFILE CHRONICLE"},
    {label: "Distance", value: `${numeric(sessions.reduce((sum, row) => sum + number(row.distance), 0), 1)} LY`, detail: "RETAINED TRAVEL"},
    {label: "FSS surveys", value: numeric(sessions.reduce((sum, row) => sum + number(row.fss), 0)), detail: "SYSTEM COMPLETIONS"},
    {label: "Bio analyses", value: numeric(sessions.reduce((sum, row) => sum + number(row.bio), 0)), detail: "GENETIC SAMPLES"},
  ])}${workspaceCard("EXPEDITION REPLAY", replayMarkup(data.replay || {}), `${numeric(data.replay?.points?.length)} ROUTE POINTS`, "replay-card")}<section class="chronicle-list">${cards.join("") || `<p class="workspace-empty">Captain's Log will populate as journal sessions are completed.</p>`}</section>`;
}

function renderMissionWorkspace(data) {
  const root = byId("mission-workspace");
  const expeditions = data.expeditions || [];
  if (!missionSelectedId || !expeditions.some((row) => row.id === missionSelectedId)) missionSelectedId = data.active_id || expeditions[0]?.id || "";
  const selected = expeditions.find((row) => row.id === missionSelectedId);
  const list = expeditions.map((row) => `<button class="mission-row${row.id === missionSelectedId ? " active" : ""}" data-mission-select="${escapeHtml(row.id)}"><i></i><span><b>${escapeHtml(row.name)}</b><small>${escapeHtml(row.destination || row.description || "Open-ended expedition")}</small></span><em>${escapeHtml(row.status)}</em></button>`).join("");
  let detail = `<p class="workspace-empty">Create a named expedition to begin a journal-backed mission.</p>`;
  if (selected) {
    const objectives = (selected.objectives || []).map((row) => `<div class="objective-row${row.complete ? " complete" : ""}"><button data-ws-page="mission" data-ws-op="toggle_objective" data-expedition-id="${escapeHtml(selected.id)}" data-objective-id="${escapeHtml(row.id)}">${row.complete ? "✓" : "○"}</button><p><strong>${escapeHtml(row.title)}</strong><span>${escapeHtml(row.detail || row.kind || "Manual expedition objective")}</span></p><button class="row-delete" data-ws-page="mission" data-ws-op="remove_objective" data-expedition-id="${escapeHtml(selected.id)}" data-objective-id="${escapeHtml(row.id)}">×</button></div>`);
    detail = `${workspaceMetrics([
      {label: "Jumps", value: numeric(selected.stats?.jumps), detail: `${numeric(selected.stats?.systems)} SYSTEMS`},
      {label: "Distance", value: `${numeric(selected.stats?.distance, 1)} LY`, detail: "EXPEDITION TRAVEL"},
      {label: "Survey", value: numeric(number(selected.stats?.fss) + number(selected.stats?.dss)), detail: `${numeric(selected.stats?.fss)} FSS · ${numeric(selected.stats?.dss)} DSS`},
      {label: "Discoveries", value: numeric(number(selected.stats?.bio) + number(selected.stats?.codex)), detail: `${numeric(selected.stats?.bio)} BIO · ${numeric(selected.stats?.codex)} CODEX`},
    ])}<section class="workspace-hero compact"><div><small>${escapeHtml(selected.status)} // ${escapeHtml(selected.started)}</small><h3>${escapeHtml(selected.name)}</h3><span>${escapeHtml(selected.description || "No expedition description")}</span></div><div><button data-ws-page="mission" data-ws-op="status" data-status="active" data-expedition-id="${escapeHtml(selected.id)}">RESUME</button><button data-ws-page="mission" data-ws-op="status" data-status="paused" data-expedition-id="${escapeHtml(selected.id)}">PAUSE</button><button data-ws-page="mission" data-ws-op="status" data-status="completed" data-expedition-id="${escapeHtml(selected.id)}">COMPLETE</button><button class="danger-action" data-ws-page="mission" data-ws-op="delete" data-expedition-id="${escapeHtml(selected.id)}">DELETE</button></div></section>${workspaceCard("OBJECTIVES", `${workspaceRows(objectives, "No objectives yet.")}<div class="workspace-actions"><button data-ws-page="mission" data-ws-op="add_objective" data-expedition-id="${escapeHtml(selected.id)}">ADD OBJECTIVE</button></div>`, `${objectives.filter((_, index) => selected.objectives[index]?.complete).length}/${objectives.length}`)}`;
  }
  root.classList.remove("loading-panel");
  root.innerHTML = `<section class="mission-layout"><aside class="card mission-list"><header><span>EXPEDITIONS</span><b>${expeditions.length}</b></header><div>${list || `<p class="workspace-empty">NO EXPEDITIONS</p>`}</div></aside><div class="mission-detail">${detail}</div></section>`;
}

function trailSvg(points = []) {
  if (!points.length) return `<div class="trail-empty">TRAIL BEGINS AFTER TOUCHDOWN</div>`;
  const extent = Math.max(75, ...points.flatMap((row) => [Math.abs(number(row.east)), Math.abs(number(row.north))])) * 1.15;
  const project = (row) => `${150 + number(row.east) * 130 / extent},${150 - number(row.north) * 130 / extent}`;
  const circles = points.filter((row) => row.kind === "sample" || row.kind === "ship").map((row) => `<circle cx="${project(row).split(",")[0]}" cy="${project(row).split(",")[1]}" r="${row.kind === "ship" ? 5 : 3}" class="${escapeHtml(row.kind)}"><title>${escapeHtml(row.label || row.kind)}</title></circle>`).join("");
  return `<svg class="trail-chart" viewBox="0 0 300 300" role="img"><path class="trail-grid" d="M150 5V295M5 150H295M75 5V295M225 5V295M5 75H295M5 225H295"/><polyline points="${points.map(project).join(" ")}"/>${circles}<circle cx="${project(points.at(-1)).split(",")[0]}" cy="${project(points.at(-1)).split(",")[1]}" r="4" class="current"/></svg>`;
}

function fieldMapSvg(field = {}, trail = {}) {
  const pins = field.pins || [];
  if (!pins.length) return trailSvg(trail.points || []);
  const colony = Math.max(0, number(field.sampling?.colony_m));
  const extent = Math.max(100, colony * 1.1, ...pins.flatMap((row) => [Math.abs(number(row.east)), Math.abs(number(row.north))])) * 1.15;
  const project = (row) => ({x: 180 + number(row.east) * 158 / extent, y: 180 - number(row.north) * 158 / extent});
  const activeGroup = field.sampling?.sample_group || "";
  const rings = colony ? pins.filter((row) => row.kind === "organic_sample" && (!activeGroup || row.metadata?.sample_group === activeGroup)).map((row) => {
    const point = project(row);
    return `<circle class="sample-clearance" cx="${point.x}" cy="${point.y}" r="${colony * 158 / extent}"><title>${numeric(colony)} m colony distance</title></circle>`;
  }).join("") : "";
  const markers = pins.map((row) => {
    const point = project(row);
    const kind = row.kind === "organic_sample" ? "sample" : row.kind === "landing" ? "ship" : row.kind === "codex" ? "codex" : "waypoint";
    return `<g class="field-pin ${kind}${row.manual ? " manual" : ""}" transform="translate(${point.x} ${point.y})"><circle r="${kind === "ship" ? 6 : kind === "waypoint" ? 5 : 4}"/><title>${escapeHtml(row.label || kind)}${row.distance === null ? "" : ` · ${numeric(row.distance)} m @ ${numeric(row.bearing)}°`}</title></g>`;
  }).join("");
  return `<svg class="trail-chart field-map-chart" viewBox="0 0 360 360" role="img" aria-label="Planetary field map"><path class="trail-grid" d="M180 5V355M5 180H355M90 5V355M270 5V355M5 90H355M5 270H355"/><circle class="field-range" cx="180" cy="180" r="158"/>${rings}${markers}<g class="field-current" transform="translate(180 180) rotate(${number(field.heading)})"><path d="M0 -9L6 7L0 4L-6 7Z"/></g><text x="12" y="20">LOCAL TANGENT PLANE · ±${numeric(extent)} M</text></svg>`;
}

function renderGroundWorkspace(data) {
  const root = byId("ground-workspace");
  const target = data.target || {};
  const trail = data.trail || {};
  const field = data.field_map || {};
  const eliteTarget = data.elite_target || {};
  const pins = (field.pins || []).map((row) => `<div class="field-pin-row"><i class="${escapeHtml(row.kind)}"></i><span><b>${escapeHtml(row.label || row.kind)}</b><small>${row.distance === null ? escapeHtml(row.source || "FIELD RECORD") : `${numeric(row.distance)} M · ${numeric(row.bearing)}°`}</small></span>${row.manual ? `<button data-ws-page="ground" data-ws-op="remove_pin" data-pin-id="${escapeHtml(row.id)}">×</button>` : ""}</div>`);
  const completed = (field.completed || []).map((row) => `<em>${escapeHtml(row.variant || row.species || row.genus)}${row.count > 1 ? ` ×${numeric(row.count)}` : ""}</em>`).join("");
  root.classList.remove("loading-panel");
  const eliteTargetStrip = eliteTarget.name ? `<div class="ground-elite-target${eliteTarget.is_current_body ? " current" : ""}"><i>⌖</i><span><small>ELITE NAVIGATION TARGET</small><b>${escapeHtml(eliteTarget.name)}</b></span><em>${eliteTarget.is_current_body ? "TARGET BODY REACHED · FIELD TELEMETRY LINKED" : "BODY SELECTED · APPROACH OR LAND FOR SURFACE TELEMETRY"}</em></div>` : "";
  root.innerHTML = `${workspaceMetrics([
    {label: "Surface state", value: data.on_planet ? "ON SURFACE" : "ORBITAL", detail: data.body || data.system || "NO BODY"},
    {label: "Current position", value: data.position?.lat === null ? "AWAITING STATUS" : `${numeric(data.position.lat, 5)}, ${numeric(data.position.lon, 5)}`, detail: data.position?.heading === null ? "HEADING UNKNOWN" : `HEADING ${numeric(data.position.heading)}°`},
    {label: "Target bearing", value: target.bearing === null ? "—" : `${numeric(target.bearing)}°`, detail: target.direction || target.state || "TARGET OFF"},
    {label: "Target distance", value: target.distance === null ? "—" : `${numeric(target.distance)} M`, detail: target.active ? "LIVE GUIDANCE" : "NO ACTIVE TARGET"},
  ])}${eliteTargetStrip}<section class="workspace-grid ground-grid">
    ${workspaceCard("SURFACE TARGET", `<div class="coordinate-form"><label>LATITUDE<input id="ground-lat" type="number" min="-90" max="90" step="0.000001" value="${target.lat ?? ""}"></label><label>LONGITUDE<input id="ground-lon" type="number" min="-180" max="180" step="0.000001" value="${target.lon ?? ""}"></label></div><div class="workspace-actions wrap"><button data-ws-page="ground" data-ws-op="set">SET TARGET</button><button data-ws-page="ground" data-ws-op="set_current">USE CURRENT</button><button data-ws-page="ground" data-ws-op="return_ship">RETURN TO SHIP</button><button data-ws-page="ground" data-ws-op="clear">CLEAR</button><button data-ws-page="ground" data-ws-op="toggle_popup">POPUP ${target.popup ? "ON" : "OFF"}</button></div>`)}
    ${workspaceCard("PLANETARY FIELD MAP", `${fieldMapSvg(field, trail)}<div class="field-map-summary"><div><small>${escapeHtml(field.body || data.body || "NO ACTIVE BODY")}</small><b>${numeric(field.signals)} BIO SIGNALS</b><span>${escapeHtml((field.genuses || []).join(" · ") || "GENUS IDENTIFICATION AWAITING DSS")}</span></div><div class="field-completed">${completed || "<em>NO COMPLETED ANALYSES ON THIS MAP</em>"}</div></div><div class="field-marker-form"><input id="field-marker-label" placeholder="FIELD MARKER NOTE"><button data-ws-page="ground" data-ws-op="add_pin">ADD AT CURRENT POSITION</button></div>${workspaceRows(pins, "Landings, samples, Codex entries and field markers will appear here.")}<div class="trail-readout"><span>TRAVELLED <b>${numeric(trail.travelled)} M</b></span><span>SHIP <b>${trail.return_distance === null ? "—" : `${numeric(trail.return_distance)} M @ ${numeric(trail.return_bearing)}°`}</b></span><span>SAMPLE <b>${field.sampling?.progress ? `${numeric(field.sampling.progress)} / 3 · ${numeric(field.sampling.colony_m)} M` : "INACTIVE"}</b></span><button data-ws-page="ground" data-ws-op="clear_trail">CLEAR TRAIL</button></div>`, `${(field.pins || []).length} FIELD RECORDS`)}
  </section>`;
}

function renderMiningWorkspace(data) {
  const root = byId("mining-workspace");
  const session = data.session || {};
  const materials = workspaceTable([
    {label: "Material", key: "name"}, {label: "Sightings", key: "sightings"},
    {label: "Best", render: (row) => `${numeric(row.best, 2)}%`}, {label: "Average", render: (row) => `${numeric(row.average, 2)}%`},
  ], session.materials || [], "Prospector results will appear here during a mining run.");
  const yields = workspaceTable([
    {label: "Commodity", key: "name"}, {label: "Refined", render: (row) => `${numeric(row.count)} T`},
    {label: "Cargo delta", render: (row) => `${numeric(row.cargo_delta)} T`}, {label: "Sold", render: (row) => `${numeric(row.sold)} T`},
  ], session.yield || [], "No refined commodities in this run.");
  root.classList.remove("loading-panel");
  root.innerHTML = `${workspaceMetrics([
    {label: "Run state", value: data.active ? "ACTIVE" : "STANDBY", detail: duration(session.duration)},
    {label: "Prospected", value: numeric(session.prospected), detail: `${numeric(session.cracked)} CORES CRACKED`},
    {label: "Refined yield", value: `${numeric(session.refined_t)} T`, detail: session.tons_per_hour === null ? "RATE AWAITING DATA" : `${numeric(session.tons_per_hour, 1)} T / HR`},
    {label: "Attributed return", value: credits(session.revenue), detail: `NET ${credits(session.net)}`},
  ])}<section class="workspace-grid two">${workspaceCard("PROSPECTOR QUALITY", materials)}${workspaceCard("REFINERY & CARGO YIELD", yields)}${workspaceCard("LIMPET ECONOMY", `<div class="fact-list spacious"><div><span>PROSPECTORS</span><b>${numeric(session.limpets?.prospectors_used)}</b></div><div><span>COLLECTORS</span><b>${numeric(session.limpets?.collectors_launched)}</b></div><div><span>ESTIMATED USED</span><b>${numeric(session.limpets?.estimated_used)}</b></div><div><span>REMAINING</span><b>${numeric(session.limpets?.remaining)}</b></div><div><span>CASH COST</span><b>${credits(session.limpets?.cash_net_cost_cr)}</b></div></div>`)}${workspaceCard("RECENT MINING RUNS", workspaceTable([{label: "System", key: "system"}, {label: "Prospected", key: "prospected"}, {label: "Refined", render: (row) => `${numeric(row.refined)} T`}, {label: "Revenue", render: (row) => credits(row.revenue)}], data.history || [], "No completed mining history yet."), `${(data.history || []).length} RETAINED`)}</section>`;
}

function renderEngineeringWorkspace(data) {
  const root = byId("engineering-workspace");
  const wishlist = data.wishlist || {};
  const pinRows = (data.pins || []).map((row) => `<div class="engineering-pin"><div><b>${escapeHtml(row.name)}</b><span>G${numeric(row.current_grade)} → G${numeric(row.grade)} · QTY ${numeric(row.quantity)}</span></div><em class="${row.craftable ? "ready" : "missing"}">${row.craftable ? "READY" : "MISSING"}</em><button data-ws-page="engineering" data-ws-op="unpin" data-name="${escapeHtml(row.name)}">×</button></div>`);
  const odysseyGoals = (data.odyssey?.goals || []).map((row) => `<div class="engineering-pin"><div><b>${escapeHtml(row.name)}</b><span>ODYSSEY WORKSHOP · QTY ${numeric(row.quantity)}</span></div><em class="missing">GOAL</em><button data-ws-page="engineering" data-ws-op="odyssey_unpin" data-name="${escapeHtml(row.name)}">×</button></div>`);
  const priorities = workspaceTable([
    {label: "Material", render: (row) => `<b>${escapeHtml(row.name || row.symbol)}</b><small>${escapeHtml(row.category || row.family || "")}</small>`},
    {label: "Have", render: (row) => numeric(row.have ?? row.count)}, {label: "Need", render: (row) => numeric(row.need)},
    {label: "Missing", render: (row) => `<b class="warn-text">${numeric(row.deficit)}</b>`},
  ], wishlist.materials || data.priorities || [], "Pin a blueprint to build a shared material wishlist.");
  const engineers = workspaceTable([{label: "Engineer", key: "name"}, {label: "Rank", key: "rank"}, {label: "Progress", key: "progress"}, {label: "System", key: "system"}], data.engineers || [], "EngineerProgress will populate access records.");
  const inventory = workspaceTable([{label: "Material", render: (row) => `<b>${escapeHtml(row.name)}</b><small>${escapeHtml(row.category)} · G${numeric(row.grade)}</small>`}, {label: "Stock", render: (row) => numeric(row.count)}, {label: "Capacity", render: (row) => numeric(row.capacity)}], data.inventory || [], "Materials and Backpack journal events will populate inventory.");
  root.classList.remove("loading-panel");
  root.innerHTML = `${workspaceMetrics([
    {label: "Pinned upgrades", value: numeric(wishlist.pins), detail: `${numeric(wishlist.required)} REQUIRED UNITS`},
    {label: "Material deficit", value: numeric(wishlist.missing), detail: wishlist.complete ? "ALL GOALS READY" : "COLLECTION REQUIRED"},
    {label: "Odyssey goals", value: numeric(data.odyssey?.goals?.length), detail: `${numeric(data.odyssey?.missing)} MISSING UNITS`},
    {label: "Inventory types", value: numeric(data.inventory?.length), detail: data.last_updated || "AWAITING MATERIALS"},
  ])}<section class="engineering-add card"><header><span>ADD ENGINEERING GOAL</span></header><div><select id="engineering-blueprint">${(data.catalogue || []).map((row) => `<option value="${escapeHtml(row.name)}" data-grade="${number(row.grade, 5)}">${escapeHtml(row.name)} · G${numeric(row.grade)}</option>`).join("")}</select><label>TARGET GRADE<input id="engineering-grade" type="number" min="1" max="5" value="5"></label><label>CURRENT GRADE<input id="engineering-current-grade" type="number" min="0" max="4" value="0"></label><label>QUANTITY<input id="engineering-quantity" type="number" min="1" max="99" value="1"></label><button data-ws-page="engineering" data-ws-op="pin">PIN GOAL</button></div></section><section class="workspace-grid two">${workspaceCard("PINNED BLUEPRINTS", workspaceRows(pinRows, "No engineering goals pinned."), `${pinRows.length} GOALS`)}${workspaceCard("COLLECTION PLAN", priorities, `${numeric(wishlist.missing)} MISSING`)}${workspaceCard("FSD INJECTION SYNTHESIS", `<div class="profile-ship-grid"><div><span>BASIC +25%</span><b>${numeric(data.synthesis?.basic)}</b></div><div><span>STANDARD +50%</span><b>${numeric(data.synthesis?.standard)}</b></div><div><span>PREMIUM +100%</span><b>${numeric(data.synthesis?.premium)}</b></div></div>`)}${workspaceCard("ENGINEER ACCESS", engineers, `${(data.engineers || []).length} KNOWN`)}${workspaceCard("ODYSSEY WORKSHOP", `<div class="odyssey-add"><select id="odyssey-blueprint">${(data.odyssey_catalogue || []).map((name) => `<option>${escapeHtml(name)}</option>`).join("")}</select><input id="odyssey-quantity" type="number" min="1" max="99" value="1"><button data-ws-page="engineering" data-ws-op="odyssey_pin">ADD GOAL</button></div>${workspaceRows(odysseyGoals, "No Odyssey suit or weapon goals pinned.")}${workspaceTable([{label: "Material", key: "name"}, {label: "Have", key: "have"}, {label: "Need", key: "need"}, {label: "Missing", key: "deficit"}], data.odyssey?.materials || [], "Add an Odyssey goal to calculate its shopping list.")}`, `${numeric(data.odyssey?.missing)} MISSING`)}${workspaceCard("MATERIAL INVENTORY", inventory, `${numeric((data.inventory || []).length)} TYPES`)}</section>`;
}

function renderCarrierWorkspace(data) {
  const root = byId("carrier-workspace");
  const carrier = data.carrier || {};
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
  root.classList.remove("loading-panel");
  root.innerHTML = `${workspaceMetrics([
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

function renderAchievementsWorkspace(data) {
  const root = byId("achievements-workspace");
  const rows = (data.achievements || []).map((row) => {
    const progress = row.unlocked ? 100 : row.target ? clamp(number(row.current) * 100 / number(row.target)) : 0;
    return `<article class="achievement-tile${row.unlocked ? " unlocked" : ""}" data-achievement-category="${escapeHtml(row.category)}"><header><span>${escapeHtml(row.category || "MILESTONE")}</span><b>${numeric(row.points)} PTS</b></header><h3>${escapeHtml(row.title)}</h3><p>${escapeHtml(row.description || "Journal-driven commander milestone.")}</p><div class="achievement-progress"><i style="width:${progress}%"></i><span>${row.unlocked ? "UNLOCKED" : row.target ? `${numeric(row.current)} / ${numeric(row.target)}` : "LOCKED"}</span></div><footer><button data-ws-page="achievements" data-ws-op="manual_unlock" data-achievement-id="${escapeHtml(row.id)}" ${row.unlocked ? "disabled" : ""}>UNLOCK</button><button class="danger-action" data-ws-page="achievements" data-ws-op="reset" data-achievement-id="${escapeHtml(row.id)}" ${row.unlocked || number(row.current) ? "" : "disabled"}>RESET</button></footer></article>`;
  });
  root.classList.remove("loading-panel");
  root.innerHTML = `${workspaceMetrics([{label: "Unlocked", value: `${numeric(data.unlocked)} / ${numeric(data.total)}`, detail: `${data.total ? numeric(number(data.unlocked) * 100 / number(data.total), 1) : "0.0"}% COMPLETE`}, {label: "Achievement points", value: numeric(data.points), detail: "PROFILE TOTAL"}, {label: "Categories", value: numeric((data.categories || []).length), detail: "EXPLORATION-FOCUSED"}, {label: "Tracking", value: data.enabled ? "ACTIVE" : "PAUSED", detail: data.notifications_enabled ? "UNLOCK SIGNALS ON" : "UNLOCK SIGNALS OFF"}])}<div class="workspace-actions achievement-controls"><button data-ws-page="achievements" data-ws-op="set_enabled" data-enabled="${!data.enabled}">${data.enabled ? "PAUSE TRACKING" : "ENABLE TRACKING"}</button><button data-ws-page="achievements" data-ws-op="set_notifications" data-enabled="${!data.notifications_enabled}">${data.notifications_enabled ? "MUTE UNLOCK SIGNALS" : "ENABLE UNLOCK SIGNALS"}</button><input id="achievement-filter" placeholder="FILTER MILESTONES"></div><section id="achievement-grid" class="achievement-grid">${rows.join("") || `<p class="workspace-empty">Achievement catalogue unavailable.</p>`}</section>`;
}

function renderLedgerWorkspace(data) {
  const root = byId("ledger-workspace");
  const rows = data.rows || [];
  root.classList.remove("loading-panel");
  root.innerHTML = `${workspaceMetrics([{label: "Valuable bodies", value: numeric(rows.length), detail: "PROFILE INDEX"}, {label: "Retained estimate", value: credits(data.total), detail: "CURRENT SCAN EVIDENCE"}, {label: "Mapped", value: numeric(rows.filter((row) => row.mapped).length), detail: "DSS COMPLETE"}, {label: "Terraformable", value: numeric(rows.filter((row) => (row.flags || []).includes("Terraformable")).length), detail: "HIGH VALUE"}])}<section class="card ledger-card"><header><span>VALUABLE WORLD INDEX</span><input id="ledger-filter" placeholder="FILTER SYSTEM, BODY OR CLASS"></header><div id="ledger-table">${workspaceTable([{label: "System", key: "system"}, {label: "Body", key: "body"}, {label: "Class", key: "class"}, {label: "Value", render: (row) => `<b>${credits(row.value)}</b>`}, {label: "Mapped", render: (row) => row.mapped ? "YES" : "NO"}, {label: "Flags", render: (row) => escapeHtml((row.flags || []).join(" · "))}], rows, "No valuable bodies are indexed for this profile yet.")}</div></section>`;
  root.dataset.rows = JSON.stringify(rows);
}

function settingToggle(id, label, detail, checked) {
  return `<label class="settings-toggle"><span><b>${escapeHtml(label)}</b><small>${escapeHtml(detail)}</small></span><input id="${id}" type="checkbox" ${checked ? "checked" : ""}><i></i></label>`;
}

function settingInput(id, label, value, type = "text") {
  return `<label class="settings-input"><span>${escapeHtml(label)}</span><input id="${id}" type="${type}" value="${escapeHtml(value ?? "")}" autocomplete="off"></label>`;
}

function renderSettingsWorkspace(data) {
  const root = byId("settings-workspace");
  const value = data.values || {};
  const galnet = data.galnet || {};
  const hotkeys = (data.hotkeys || []).map((row) => `<div class="hotkey-row"><span><b>${escapeHtml(row.label)}</b><small>${escapeHtml(row.action)}</small></span><input data-hotkey-action="${escapeHtml(row.action)}" value="${escapeHtml(row.value || "")}" placeholder="UNBOUND"><button data-hotkey-record="${escapeHtml(row.action)}">RECORD</button><button data-hotkey-clear="${escapeHtml(row.action)}">CLEAR</button></div>`).join("");
  const health = data.health || {};
  const editor = data.theme_editor || {};
  const themeColors = (editor.keys || []).map((key) => `<label><span>${escapeHtml(key.replaceAll("_", " "))}</span><input type="color" data-theme-color="${escapeHtml(key)}" value="${escapeHtml(editor.palette?.[key] || "#000000")}"></label>`).join("");
  root.classList.remove("loading-panel");
  root.innerHTML = `<section class="settings-workspace-grid">
    ${workspaceCard("CORE PATHS & ACCESSIBILITY", `${settingInput("setting-journal", "Journal folder", value.journal_path)}${settingInput("setting-screenshots", "Screenshot folder", value.screenshots_path)}${settingToggle("setting-screenshots-enabled", "Convert BMP screenshots to PNG", "Watch the configured screenshot folder.", value.screenshots_enabled)}<label class="settings-input"><span>Application scale</span><select id="setting-ui-scale">${[90,100,110,125,140].map((item) => `<option ${number(value.ui_scale_percent,100) === item ? "selected" : ""}>${item}</option>`).join("")}</select></label><label class="settings-input"><span>Navigation animation</span><select id="setting-motion-intensity">${["Calm","Standard","Energetic"].map((item) => `<option ${String(value.hud_animation_intensity || "Standard") === item ? "selected" : ""}>${item}</option>`).join("")}</select></label>${settingToggle("setting-reduced-motion", "Reduced motion", "Gentler activity pulses and transitions.", value.reduced_motion_enabled)}`)}
    ${workspaceCard("GLOBAL HOTKEYS", `${settingToggle("setting-hotkeys-enabled", "Enable system-wide hotkeys", "Shortcuts remain profile-aware and work while Elite has focus.", value.overlay_hotkeys_enabled)}<div class="hotkey-status" id="hotkey-status">Click RECORD, then press the complete shortcut.</div><div class="hotkey-list">${hotkeys}</div><div class="workspace-actions"><button id="hotkey-defaults">RESTORE DEFAULTS</button></div>`, `${(data.hotkeys || []).filter((row) => row.value).length} ACTIVE`)}
    ${workspaceCard("THEME WORKSHOP", `<div class="theme-editor-head"><label>CUSTOM THEME NAME<input id="custom-theme-name" value="${escapeHtml((editor.custom || []).includes(editor.name) ? editor.name : `${editor.name || "Void"} Custom`)}"></label><label>EXISTING CUSTOM THEME<select id="custom-theme-existing"><option value="">SELECT TO DELETE</option>${(editor.custom || []).map((name) => `<option>${escapeHtml(name)}</option>`).join("")}</select></label></div><details><summary>EDIT COMPLETE PALETTE</summary><div class="theme-colour-grid">${themeColors}</div></details><div class="workspace-actions wrap"><button data-ws-page="settings" data-ws-op="save_theme">SAVE & APPLY CUSTOM THEME</button><button class="danger-action" data-ws-page="settings" data-ws-op="delete_theme">DELETE SELECTED CUSTOM THEME</button></div>`, `${(editor.custom || []).length} CUSTOM`)}
    ${workspaceCard("EDSM & EDDN", `${settingInput("setting-edsm-name", "EDSM commander name", value.edsm_cmdr_name)}${settingInput("setting-edsm-key", "EDSM API key", value.edsm_api_key, "password")}${settingToggle("setting-edsm-upload", "Upload exploration events to EDSM", "Uses the active commander's credentials.", value.edsm_upload_enabled)}${settingToggle("setting-eddn-upload", "Upload visited markets to EDDN", "Community market publishing remains independent from Trade UI.", value.eddn_market_upload_enabled)}<p class="settings-note">${numeric(data.eddn?.uploads)} EDDN uploads this run${data.eddn?.last_error ? ` · LAST ERROR ${escapeHtml(data.eddn.last_error)}` : ""}</p><div class="workspace-actions"><button data-ws-page="settings" data-ws-op="test_edsm">TEST EDSM CREDENTIALS</button></div>`)}
    ${workspaceCard("GALNET RELAY", `${settingToggle("setting-galnet-enabled", "Enable Galnet relay", "Show the bottom-bar news ticker and permit background feed refreshes.", value.galnet_enabled)}${settingToggle("setting-galnet-rotate", "Rotate headlines automatically", "Hold the current dispatch when disabled; the archive remains available.", value.galnet_auto_rotate_enabled)}<label class="settings-input"><span>Headline rotation cadence</span><select id="setting-galnet-rotation">${[4,7,10,15,30,60].map((item) => `<option value="${item}" ${number(value.galnet_rotation_seconds,7) === item ? "selected" : ""}>${item} seconds</option>`).join("")}</select></label><label class="settings-input"><span>Feed refresh cadence</span><select id="setting-galnet-refresh">${[5,15,30,60,120,240].map((item) => `<option value="${item}" ${number(value.galnet_refresh_minutes,30) === item ? "selected" : ""}>${item < 60 ? `${item} minutes` : `${item / 60} hour${item === 60 ? "" : "s"}`}</option>`).join("")}</select></label><p class="settings-note">${escapeHtml(galnet.detail || "Galnet relay standing by.")} · ${numeric((galnet.articles || []).length)} cached dispatches</p><div class="workspace-actions wrap"><button id="galnet-settings-refresh">REFRESH NOW</button><button id="galnet-settings-clear" class="danger-action">CLEAR CACHE</button></div>`, galnet.busy ? "RECEIVING" : String(galnet.status || "STANDBY").toUpperCase())}
    ${workspaceCard("CARRIER INTEGRATION", `${settingInput("setting-discord", "Discord webhook URL", value.carrier_discord_webhook_url, "password")}<p class="settings-note">One webhook handles personal and Squadron Carrier status, jump and expedition updates.</p><div class="workspace-actions"><button data-ws-page="settings" data-ws-op="test_discord">SEND TEST PREVIEW</button><button data-page="carrier">OPEN CARRIER COMMAND</button></div>`)}
    ${workspaceCard("DIAGNOSTICS & RECOVERY", `<div class="health-readout"><b>${escapeHtml(health.level || "NOMINAL")}</b><span>UI queue ${numeric(health.ui?.pending || health.ui_pending)} · max lag ${numeric(health.ui?.max_lag_ms || health.ui_max_lag_ms)} ms · disk queue ${numeric(health.persistence?.pending || health.writes_pending)}</span></div>${settingToggle("setting-runtime-trace", "Runtime performance trace", "Retain startup and UI timing evidence.", value.runtime_trace_enabled)}${settingToggle("setting-crash-report", "Crash and UI-freeze reporter", "Rotate current and previous diagnostic logs.", value.crash_reporting_enabled)}${settingToggle("setting-safe-mode", "Safe unclean-shutdown recovery", "Restore the last graceful profile checkpoint first.", value.recovery_safe_mode_enabled)}${settingToggle("setting-auto-backups", "Automatic profile safety snapshots", "Keep up to five snapshots before upgrades and cache rebuilds. Manual backup and restore rollback remain available.", value.automatic_profile_backups_enabled)}${settingToggle("setting-cache-edsm", "Upload history during cache rebuild", "Optional EDSM backfill while reconstructing profile history.", value.edsm_backfill_on_cache_rebuild)}<div class="workspace-actions wrap"><button data-ws-page="settings" data-ws-op="rebuild_cache">REBUILD CACHE</button><button data-ws-page="settings" data-ws-op="support_bundle">CREATE SUPPORT BUNDLE</button><button data-command="open_logs">OPEN LOGS</button><button data-ws-page="settings" data-ws-op="run_setup">RUN SETUP</button></div>`)}
  </section><p id="settings-test-status" class="workspace-status ${escapeHtml(data.tools?.status || "ready")}">${escapeHtml(data.tools?.detail || "Integration tests have not run this session.")}</p><footer class="settings-savebar"><span>All settings belong to the active commander profile.</span><button id="settings-save-html">SAVE SETTINGS</button></footer>`;
}

function renderWorkspace(state) {
  const workspace = state.workspace || {};
  const page = workspace.page || "";
  if (page !== currentPage || !workspace.ready) return;
  if (pageLayoutEditing === page) return;
  const fingerprintData = page === "analytics"
    ? {...(workspace.data || {}), current: {...(workspace.data?.current || {}), elapsed: ""}}
    : (workspace.data || {});
  const fingerprint = JSON.stringify(fingerprintData);
  if (page === "settings" && workspaceFingerprints[page]) {
    const status = byId("settings-test-status");
    if (status) {
      status.className = `workspace-status ${workspace.data?.tools?.status || "ready"}`;
      status.textContent = workspace.data?.tools?.detail || "Integration tests have not run this session.";
    }
    return;
  }
  if (workspaceFingerprints[page] === fingerprint) return;
  const root = byId(`${page}-workspace`);
  const focused = document.activeElement;
  if (root?.contains(focused) && focused?.matches("input, textarea, select, [contenteditable='true']")) return;
  workspaceFingerprints[page] = fingerprint;
  const renderers = {
    explore: renderExploreWorkspace,
    profile: renderProfileWorkspace, analytics: renderAnalyticsWorkspace,
    chronicle: renderChronicleWorkspace, mission: renderMissionWorkspace,
    ground: renderGroundWorkspace, mining: renderMiningWorkspace,
    engineering: renderEngineeringWorkspace, carrier: renderCarrierWorkspace,
    recon: renderReconWorkspace, achievements: renderAchievementsWorkspace,
    ledger: renderLedgerWorkspace, settings: renderSettingsWorkspace,
  };
  renderers[page]?.(workspace.data || {});
  preparePageLayout(page);
}

function renderDashboard(state) {
  const nextProfileKey = model.profile?.key || "default";
  if (nextProfileKey !== profileKey) {
    cancelPageLayout();
    profileKey = nextProfileKey;
    Object.keys(pageLayoutDefaults).forEach((page) => delete pageLayoutDefaults[page]);
    workspaceFingerprints = {};
    missionSelectedId = "";
    orrerySelectedBodyId = "";
    orreryLiveTargetBodyId = "";
    analyticsView = "trends";
    replaySelectedSessionIndex = 0;
    deckLayoutDraft = null;
    deckLayoutFingerprint = "";
    decisionTagsFingerprint = "";
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
  text("rail-version", `v${model.app?.version || "5.4.1.4"} // WEBVIEW2`);
  text("boot-version", `v${model.app?.version || "5.4.1.4"} // SECURE LOOPBACK // WEBVIEW2`);
  text("about-version", `Version ${model.app?.version || "5.4.1.4"} // HTML Command Deck`);
  text("overview-subtitle", model.profile?.profile_label || "Journal-backed field intelligence");
  if (currentPage === "map" && !model.boot?.active) ensureAtlas();
}

function queueDashboardRender() {
  if (dashboardRenderQueued) return;
  dashboardRenderQueued = true;
  // Give WebView2 two compositor turns to paint the dismissed boot curtain
  // before hydrating the complete dashboard. This keeps journal catch-up and
  // overlay creation from being visually mistaken for a frozen handoff.
  window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
    dashboardRenderQueued = false;
    if (!model.boot?.active && !model.onboarding?.active) renderDashboard(model);
  }));
}

function renderState(state) {
  model = state || {};
  applyTheme(model.theme || {});
  document.body.classList.toggle("reduced-motion", Boolean(model.ui?.reduced_motion));
  const nextBootActive = Boolean(model.boot?.active || model.onboarding?.active);
  const leavingBoot = bootActive && !nextBootActive;
  bootActive = nextBootActive;
  // Boot ownership is deliberately independent. While it is visible, do not
  // build hidden dashboard lists or start optional renderers underneath it.
  renderBoot(model);
  if (nextBootActive) return;
  if (leavingBoot) {
    queueDashboardRender();
    return;
  }
  renderDashboard(model);
}

function setConnection(online) {
  const node = byId("connection-light").parentElement;
  node.classList.toggle("online", online);
  text("connection-state", online ? "LIVE" : "RECONNECTING");
}

async function syncSnapshot() {
  const state = await getJson("/api/snapshot");
  renderState(state);
  setConnection(true);
}

async function eventLoop() {
  while (true) {
    try {
      const event = await getJson(`/api/events?since=${revision}&wait=12`);
      if (event.closing) return;
      if (number(event.revision, -1) !== revision) {
        revision = number(event.revision, -1);
        await syncSnapshot();
      }
    } catch (_error) {
      reportClientError(_error, "event-loop");
      setConnection(false);
      await new Promise((resolve) => window.setTimeout(resolve, 700));
    }
  }
}

function showPage(name) {
  const page = document.querySelector(`[data-page-name="${CSS.escape(name)}"]`);
  if (!page) return;
  if (pageLayoutEditing && pageLayoutEditing !== name) cancelPageLayout();
  if (name === "settings" && currentPage !== "settings") workspaceFingerprints.settings = "";
  currentPage = name;
  localStorage.setItem(`voidcompass.dashboard.page.${profileKey}`, name);
  document.querySelectorAll(".page").forEach((node) => node.classList.toggle("active", node === page));
  document.querySelectorAll(".nav-item[data-page]").forEach((node) => node.classList.toggle("active", node.dataset.page === name));
  document.querySelector(".pages").classList.toggle("atlas-active", name === "map");
  if (name !== "map") {
    document.body.classList.remove("atlas-focus");
    text("atlas-focus-toggle", "FOCUS MAP");
  }
  document.querySelector(".pages").scrollTo({top: 0, behavior: "instant"});
  command("page_changed", {page: name});
  if (name === "map" && !model.boot?.active) ensureAtlas();
  if (name === "map") syncAtlasViewport();
  if (name === "map") window.setTimeout(syncAtlasLayerRequest, 160);
  if (name === "overlay-studio") renderOverlayStudio(model);
  preparePageLayout(name);
}

function studioPointerPosition(event, drag) {
  const desktopNode = byId("studio-desktop");
  const rect = desktopNode.getBoundingClientRect();
  const desktop = studioData().desktop || {};
  const width = Math.max(1, number(desktop.width, 1920));
  const height = Math.max(1, number(desktop.height, 1080));
  const row = studioOverlay(drag.id);
  if (!row || rect.width <= 0 || rect.height <= 0) return null;
  const x = Math.round(drag.startX + (event.clientX - drag.clientX) * width / rect.width);
  const y = Math.round(drag.startY + (event.clientY - drag.clientY) * height / rect.height);
  const left = number(desktop.left);
  const top = number(desktop.top);
  return {
    x: Math.max(left, Math.min(x, left + width - row.width)),
    y: Math.max(top, Math.min(y, top + height - row.height)),
    left, top, width, height,
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
    activeCard.style.left = `${(active.x - active.left) * 100 / active.width}%`;
    activeCard.style.top = `${(active.y - active.top) * 100 / active.height}%`;
    text("studio-pointer-position", `X ${active.x}  //  Y ${active.y}`);
    const row = studioOverlay(studioDragging.id);
    text("studio-selected-metrics", `${active.x}, ${active.y}  //  ${row.width} × ${row.height} PX`);
    text("studio-selected-position", `X ${active.x} · Y ${active.y}`);
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
  card.style.left = `${(position.x - position.left) * 100 / position.width}%`;
  card.style.top = `${(position.y - position.top) * 100 / position.height}%`;
  command("overlay_studio", {operation: "move", overlay_id: drag.id, x: position.x, y: position.y, commit: true, sequence: ++studioMoveSequence})
    .finally(() => {
      const row = studioOverlay(drag.id);
      if (row) { row.x = position.x; row.y = position.y; }
      studioDragging = null;
      studioFingerprint = "";
      renderOverlayStudio(model);
    });
}

async function nudgeStudioOverlay(vector) {
  const row = studioOverlay(studioSelectedId);
  if (!row) return false;
  const [dx, dy] = String(vector || "0,0").split(",").map((value) => number(value));
  const desktop = studioData().desktop || {};
  const left = number(desktop.left);
  const top = number(desktop.top);
  const width = Math.max(1, number(desktop.width, 1920));
  const height = Math.max(1, number(desktop.height, 1080));
  const x = Math.max(left, Math.min(row.x + dx, left + width - row.width));
  const y = Math.max(top, Math.min(row.y + dy, top + height - row.height));
  return command("overlay_studio", {operation: "move", overlay_id: row.id, x, y, commit: true, sequence: ++studioMoveSequence});
}

document.addEventListener("click", async (event) => {
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
    document.querySelectorAll("[data-analytics-view]").forEach((button) => button.classList.toggle("active", button === analyticsTab));
    document.querySelectorAll("[data-analytics-panel]").forEach((panel) => { panel.hidden = panel.dataset.analyticsPanel !== analyticsView; });
    return;
  }
  const orreryNode = event.target.closest("[data-orrery-body]");
  if (orreryNode) {
    orrerySelectedBodyId = orreryNode.dataset.orreryBody;
    const bodies = model.workspace?.page === "explore" ? model.workspace.data?.cartography?.orrery?.bodies || [] : [];
    byId("orrery-detail").innerHTML = orreryDetail(bodies.find((row) => String(row.id) === String(orrerySelectedBodyId)));
    document.querySelectorAll("[data-orrery-body]").forEach((node) => node.classList.toggle("selected", node === orreryNode));
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
  const studioTab = event.target.closest("[data-studio-view]");
  if (studioTab) {
    setStudioView(studioTab.dataset.studioView);
    return;
  }
  const studioOverlayButton = event.target.closest(".studio-overlay-card, .studio-index-row");
  if (studioOverlayButton) {
    selectStudioOverlay(studioOverlayButton.dataset.overlayId);
    return;
  }
  const studioNudge = event.target.closest("[data-studio-nudge]");
  if (studioNudge) {
    await nudgeStudioOverlay(studioNudge.dataset.studioNudge);
    return;
  }
  if (event.target.closest("#studio-ground-overlay-toggle")) {
    const accepted = await command("overlay_studio", {operation: "toggle", overlay_id: "ground_popup"});
    showToast(accepted ? "Planet Waypoint overlay updated" : "Planet Waypoint overlay could not be changed");
    return;
  }
  const pageButton = event.target.closest("[data-page]");
  if (pageButton) {
    showPage(pageButton.dataset.page);
    return;
  }
  if (event.target.closest("#explore-complete")) {
    byId("explore-workspace")?.scrollIntoView({behavior: "smooth", block: "start"});
    return;
  }
  const missionSelect = event.target.closest("[data-mission-select]");
  if (missionSelect) {
    missionSelectedId = missionSelect.dataset.missionSelect;
    workspaceFingerprints.mission = "";
    renderWorkspace(model);
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
    text("hotkey-status", "Binding cleared. Save Settings to apply.");
    return;
  }
  if (event.target.closest("[data-settings-focus]")) {
    byId("settings-workspace")?.scrollIntoView({behavior: "smooth", block: "start"});
    return;
  }
  if (event.target.closest("#hotkey-defaults")) {
    for (const row of model.workspace?.data?.hotkeys || []) {
      const input = document.querySelector(`[data-hotkey-action="${CSS.escape(row.action)}"]`);
      if (input) input.value = row.default || "";
    }
    text("hotkey-status", "Default bindings restored. Save Settings to apply.");
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
  if (event.target.closest("#settings-save-html")) {
    const values = {
      journal_path: byId("setting-journal")?.value.trim() || "",
      screenshots_path: byId("setting-screenshots")?.value.trim() || "",
      screenshots_enabled: Boolean(byId("setting-screenshots-enabled")?.checked),
      ui_scale_percent: number(byId("setting-ui-scale")?.value, 100),
      reduced_motion_enabled: Boolean(byId("setting-reduced-motion")?.checked),
      hud_animation_intensity: byId("setting-motion-intensity")?.value || "Standard",
      overlay_hotkeys_enabled: Boolean(byId("setting-hotkeys-enabled")?.checked),
      edsm_cmdr_name: byId("setting-edsm-name")?.value.trim() || "",
      edsm_api_key: byId("setting-edsm-key")?.value.trim() || "",
      edsm_upload_enabled: Boolean(byId("setting-edsm-upload")?.checked),
      eddn_market_upload_enabled: Boolean(byId("setting-eddn-upload")?.checked),
      carrier_discord_webhook_url: byId("setting-discord")?.value.trim() || "",
      runtime_trace_enabled: Boolean(byId("setting-runtime-trace")?.checked),
      crash_reporting_enabled: Boolean(byId("setting-crash-report")?.checked),
      recovery_safe_mode_enabled: Boolean(byId("setting-safe-mode")?.checked),
      automatic_profile_backups_enabled: Boolean(byId("setting-auto-backups")?.checked),
      edsm_backfill_on_cache_rebuild: Boolean(byId("setting-cache-edsm")?.checked),
      galnet_enabled: Boolean(byId("setting-galnet-enabled")?.checked),
      galnet_auto_rotate_enabled: Boolean(byId("setting-galnet-rotate")?.checked),
      galnet_rotation_seconds: number(byId("setting-galnet-rotation")?.value, 7),
      galnet_refresh_minutes: number(byId("setting-galnet-refresh")?.value, 30),
    };
    const hotkeys = Object.fromEntries([...document.querySelectorAll("[data-hotkey-action]")].map((input) => [input.dataset.hotkeyAction, input.value.trim()]));
    const accepted = await command("workspace", {page: "settings", operation: "save", values, hotkeys});
    showToast(accepted ? "Commander settings saved" : "Settings could not be saved; check hotkey bindings");
    return;
  }
  if (event.target.closest("#mission-new")) {
    const name = window.prompt("Expedition name:", "Deep-space expedition");
    if (!name?.trim()) return;
    const destination = window.prompt("Destination system or region (optional):", "") || "";
    if (await command("workspace", {page: "mission", operation: "create", name: name.trim(), destination, start_system: model.flight?.system || ""})) showToast("Expedition created");
    return;
  }
  const workspaceButton = event.target.closest("[data-ws-page]");
  if (workspaceButton) {
    if (workspaceButton.disabled) return;
    const page = workspaceButton.dataset.wsPage;
    const operation = workspaceButton.dataset.wsOp;
    const payload = {page, operation};
    for (const [datasetKey, payloadKey] of [["expeditionId", "expedition_id"], ["objectiveId", "objective_id"], ["achievementId", "achievement_id"], ["bodyKey", "body_key"], ["pinId", "pin_id"], ["sessionIndex", "session_index"], ["system", "system"], ["name", "name"]]) {
      if (workspaceButton.dataset[datasetKey] !== undefined) payload[payloadKey] = workspaceButton.dataset[datasetKey];
    }
    if (workspaceButton.dataset.status !== undefined) payload.status = workspaceButton.dataset.status;
    if (workspaceButton.dataset.index !== undefined) payload.index = number(workspaceButton.dataset.index, -1);
    if (workspaceButton.dataset.offset !== undefined) payload.offset = number(workspaceButton.dataset.offset);
    if (workspaceButton.dataset.resultIndex !== undefined) payload.result_index = number(workspaceButton.dataset.resultIndex, -1);
    if (workspaceButton.dataset.visited !== undefined) payload.visited = workspaceButton.dataset.visited === "true";
    if (workspaceButton.dataset.enabled !== undefined) payload.enabled = workspaceButton.dataset.enabled === "true";
    if (["delete", "remove_objective", "delete_stop", "clear_route", "delete_candidate", "reset", "delete_waypoint", "clear_waypoints", "delete_theme"].includes(operation)) {
      if (!window.confirm("Confirm this profile-local change?")) return;
      payload.confirmed = true;
    }
    if (operation === "backup_picker" || operation === "restore_picker") {
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
    } else if (page === "mission" && operation === "add_objective") {
      const target = window.prompt("Objective:", "Survey target") || "";
      if (!target.trim()) return;
      Object.assign(payload, {kind: "manual", target: target.trim(), system: model.flight?.system || "", count: 1});
    } else if (page === "ground" && operation === "set") {
      const prefix = workspaceButton.dataset.groundSource === "studio" ? "studio-ground" : "ground";
      payload.lat = byId(`${prefix}-lat`)?.value;
      payload.lon = byId(`${prefix}-lon`)?.value;
    } else if (page === "ground" && operation === "add_pin") {
      payload.label = byId("field-marker-label")?.value.trim() || "Field marker";
    } else if (page === "engineering" && operation === "pin") {
      payload.name = byId("engineering-blueprint")?.value || "";
      payload.grade = byId("engineering-grade")?.value;
      payload.current_grade = byId("engineering-current-grade")?.value;
      payload.quantity = byId("engineering-quantity")?.value;
    } else if (page === "engineering" && operation === "odyssey_pin") {
      payload.name = byId("odyssey-blueprint")?.value || "";
      payload.quantity = byId("odyssey-quantity")?.value;
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
    } else if (page === "settings" && operation === "test_discord") {
      payload.url = byId("setting-discord")?.value.trim() || "";
      if (!payload.url) return;
    } else if (page === "settings" && operation === "rebuild_cache") {
      if (!window.confirm("Rebuild the active profile's journal cache now?")) return;
      payload.upload_edsm = Boolean(byId("setting-cache-edsm")?.checked);
    }
    workspaceButton.disabled = true;
    const accepted = await command("workspace", payload);
    workspaceButton.disabled = false;
    showToast(accepted ? "Command applied" : "That action is not available from current journal state");
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
  if (accepted && action !== "copy_next") showToast("Command handed to the flight computer");
});

document.addEventListener("input", (event) => {
  if (event.target.id === "replay-slider") {
    updateReplayCursor(event.target.value);
  } else if (event.target.id === "achievement-filter") {
    const query = event.target.value.trim().toLocaleLowerCase();
    document.querySelectorAll("#achievement-grid .achievement-tile").forEach((tile) => {
      tile.hidden = Boolean(query && !tile.textContent.toLocaleLowerCase().includes(query));
    });
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

document.addEventListener("change", async (event) => {
  if (event.target.dataset.deckVisible && deckLayoutDraft) {
    const id = event.target.dataset.deckVisible;
    const hidden = new Set(deckLayoutDraft.hidden);
    if (event.target.checked) hidden.delete(id); else hidden.add(id);
    deckLayoutDraft.hidden = [...hidden];
  } else if (event.target.id === "replay-session") {
    replaySelectedSessionIndex = Math.max(0, number(event.target.value));
    renderChronicleWorkspace(model.workspace?.data || {});
  }
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

byId("status-galnet").addEventListener("click", openGalnetReader);
byId("galnet-close").addEventListener("click", () => { byId("galnet-reader").hidden = true; });
byId("galnet-reader").addEventListener("click", (event) => {
  if (event.target === byId("galnet-reader")) byId("galnet-reader").hidden = true;
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

byId("studio-toggle-selected").addEventListener("click", async () => {
  if (!studioSelectedId) return;
  if (await command("overlay_studio", {operation: "toggle", overlay_id: studioSelectedId})) showToast("Overlay module updated");
});
byId("studio-snap-selected").addEventListener("click", async () => {
  if (!studioSelectedId) return;
  if (await command("overlay_studio", {operation: "snap", overlay_id: studioSelectedId})) showToast("Overlay snapped to the nearest edge");
});
byId("studio-reset-selected").addEventListener("click", async () => {
  if (!studioSelectedId || !window.confirm("Reset this overlay to its default screen position?")) return;
  if (await command("overlay_studio", {operation: "reset", overlay_id: studioSelectedId})) showToast("Overlay position reset");
});

byId("studio-module-grid").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-overlay-toggle]");
  if (!button) return;
  selectStudioOverlay(button.dataset.overlayToggle);
  await command("overlay_studio", {operation: "toggle", overlay_id: button.dataset.overlayToggle});
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
    await command("overlay_studio", {operation: "toggle_option", key: input.dataset.overlayOption});
  });
});

byId("studio-save-settings").addEventListener("click", async () => {
  const accepted = await command("overlay_studio", {
    operation: "save_settings",
    overlay_text_scale_percent: byId("studio-text-scale").value,
    overlay_opacity_percent: byId("studio-overlay-opacity").value,
    prospector_hud_timeout_s: byId("studio-prospector-timeout").value,
    gravity_warning_hud_timeout_s: byId("studio-gravity-timeout").value,
    station_info_timeout_s: byId("studio-station-timeout").value,
    gravity_warning_threshold_g: byId("studio-gravity-threshold").value,
    hud_crt_intensity: byId("studio-crt-intensity").value,
  });
  if (accepted) showToast("Overlay settings saved for this commander");
});

byId("studio-overlay-opacity").addEventListener("input", (event) => {
  text("studio-overlay-opacity-value", `${Math.max(40, Math.min(100, Math.round(number(event.target.value, 100))))}%`);
});

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

byId("theme-select").addEventListener("change", async (event) => {
  if (await command("set_theme", {name: event.target.value})) showToast(`Theme changed to ${event.target.value}`);
});

byId("onboarding-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = byId("onboarding-submit");
  submit.disabled = true;
  submit.textContent = "COMMISSIONING…";
  const accepted = await command("onboarding_submit", {
    journal_path: byId("onboarding-journal").value.trim(),
    adaptive_command_enabled: byId("onboarding-adaptive").checked,
    overlay_enabled: byId("onboarding-overlays").checked,
    overlay_mouse_passthrough: byId("onboarding-passthrough").checked,
  });
  if (!accepted) {
    submit.disabled = false;
    submit.textContent = "COMMISSION VOID COMPASS";
  }
});

byId("onboarding-browse").addEventListener("click", async () => {
  const browse = byId("onboarding-browse");
  browse.disabled = true;
  try {
    const api = window.pywebview?.api;
    if (!api?.choose_journal_folder) throw new Error("Native folder picker is not ready");
    const selected = await api.choose_journal_folder();
    if (selected) byId("onboarding-journal").value = String(selected);
  } catch (error) {
    showToast(error.message || "Folder picker unavailable");
  } finally {
    browse.disabled = false;
  }
});

byId("onboarding-exit").addEventListener("click", async () => {
  await command("onboarding_cancel");
});

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
    const key = hotkeyFinalKey(event);
    if (!modifiers.length || !key) {
      text("hotkey-status", "Use Ctrl, Alt, Shift or Win plus a letter, number, F-key or navigation key.");
      return;
    }
    const chord = [...modifiers, key].join("+");
    const input = document.querySelector(`[data-hotkey-action="${CSS.escape(hotkeyCaptureAction)}"]`);
    if (input) input.value = chord;
    await finishHotkeyCapture(`Captured ${chord}. Save Settings to activate it.`);
    return;
  }
  if (event.key === "Escape" && !byId("galnet-reader").hidden) {
    event.preventDefault();
    byId("galnet-reader").hidden = true;
    byId("status-galnet").focus();
    return;
  }
  if (event.key === "Escape" && document.body.classList.contains("atlas-focus")) {
    document.body.classList.remove("atlas-focus");
    text("atlas-focus-toggle", "FOCUS MAP");
    syncAtlasViewport();
  }
}, true);

document.addEventListener("pointerdown", (event) => {
  if (!pageLayoutEditing) return;
  const grip = event.target.closest(".panel-layout-handle > span");
  pageLayoutDragArmed = grip?.closest("[data-layout-panel]") || null;
});

document.addEventListener("pointerup", () => { pageLayoutDragArmed = null; });

document.addEventListener("dragstart", (event) => {
  if (!pageLayoutEditing) return;
  const panel = event.target.closest?.("[data-layout-panel]");
  if (!panel || panel !== pageLayoutDragArmed) {
    event.preventDefault();
    return;
  }
  pageLayoutDrag = panel;
  panel.classList.add("layout-dragging");
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", panel.dataset.layoutPanel || "panel");
});

document.addEventListener("dragover", (event) => {
  if (!pageLayoutDrag) return;
  const scroller = document.querySelector(".pages");
  const scrollRect = scroller?.getBoundingClientRect();
  if (scroller && scrollRect) {
    const edge = 58;
    if (event.clientY < scrollRect.top + edge) scroller.scrollTop -= 18;
    else if (event.clientY > scrollRect.bottom - edge) scroller.scrollTop += 18;
  }
  const target = event.target.closest?.("[data-layout-panel]");
  if (!target || target === pageLayoutDrag || target.parentElement !== pageLayoutDrag.parentElement) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
  const rect = target.getBoundingClientRect();
  const sourceRect = pageLayoutDrag.getBoundingClientRect();
  const sameVisualRow = Math.abs(sourceRect.top - rect.top) < Math.min(sourceRect.height, rect.height) * .35;
  const after = sameVisualRow
    ? event.clientX >= rect.left + rect.width / 2
    : event.clientY >= rect.top + rect.height / 2;
  if (pageLayoutDrop?.target === target && pageLayoutDrop.after === after) return;
  document.querySelectorAll(".layout-drop-before,.layout-drop-after").forEach((panel) => {
    panel.classList.remove("layout-drop-before", "layout-drop-after");
  });
  pageLayoutDrop = {target, after};
  target.classList.add(after ? "layout-drop-after" : "layout-drop-before");
});

document.addEventListener("dragleave", (event) => {
  const target = event.target.closest?.("[data-layout-panel]");
  if (!target || target.contains(event.relatedTarget)) return;
  if (pageLayoutDrop?.target === target) {
    target.classList.remove("layout-drop-before", "layout-drop-after");
    pageLayoutDrop = null;
  }
});

document.addEventListener("drop", (event) => {
  if (!pageLayoutDrag || !pageLayoutDrop) return;
  event.preventDefault();
  const {target, after} = pageLayoutDrop;
  if (target !== pageLayoutDrag && target.parentElement === pageLayoutDrag.parentElement) {
    target.parentElement.insertBefore(pageLayoutDrag, after ? target.nextSibling : target);
    refreshPanelLayoutHandles(pageLayoutEditing);
  }
});

document.addEventListener("dragend", () => {
  if (pageLayoutDrag) pageLayoutDrag.classList.remove("layout-dragging");
  document.querySelectorAll(".layout-drop-before,.layout-drop-after").forEach((panel) => {
    panel.classList.remove("layout-drop-before", "layout-drop-after");
  });
  pageLayoutDrag = null;
  pageLayoutDragArmed = null;
  pageLayoutDrop = null;
});

window.addEventListener("error", (event) => {
  reportClientError(event.error || event.message, "window-error");
});

window.addEventListener("unhandledrejection", (event) => {
  reportClientError(event.reason, "unhandled-rejection");
});

window.setInterval(() => text("footer-clock", new Date().toLocaleTimeString([], {hour12: false})), 500);
decorateCockpitButtons();
cockpitButtonObserver.observe(document.body, {childList: true, subtree: true});
showPage("overview");
eventLoop();
