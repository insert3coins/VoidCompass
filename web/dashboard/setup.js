/* First commissioning: the setup a new commander meets before the deck.

   Four steps on the boot galaxy: what Void Compass is, linking the journal
   folder (checked live by the backend: journals found, the span they cover,
   the commander, ship and last system), the cockpit (overlays, mouse
   passthrough, the adaptive deck and a theme previewed as you pick it), and
   a summary before COMMISSION. Steps are page state only; the backend sees
   onboarding_probe, onboarding_submit and onboarding_cancel. */

const STEPS = ["welcome", "journal", "cockpit", "launch"];
const STATUS = {
  ok: ["LINKED", "ok"],
  empty: ["NO JOURNALS YET", "warn"],
  missing: ["NOT FOUND", "bad"],
  invalid: ["CAN'T READ", "bad"],
};

const state = {step: "welcome", session: -1, theme: "", themes: {}, probedPath: null, timer: 0, sending: false};
let ui = null;
let eye = null, eyeKey = "";
const motion = window.matchMedia("(prefers-reduced-motion: reduce)");

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[char]));

function linkedProbe(onboarding = state.lastOnboarding || {}) {
  const result = onboarding.probe;
  const path = $("onboarding-journal").value.trim();
  return !onboarding.probing && result?.status === "ok"
    && (path ? path === result.path : result.auto === true) ? result : null;
}

function syncIdentity() {
  const result = linkedProbe();
  $("setup-profile-name").textContent = result?.commander ? `CMDR ${result.commander}` : "Your next chapter.";
  $("setup-profile-detail").textContent = result ? `${Number(result.journals).toLocaleString()} journals to reconnect with.` : "Four small steps to your own cockpit.";
}

function syncEye() {
  const shown = state.step === "welcome" && !$("commissioning").hidden && !document.hidden;
  if (!shown) {
    eye?.dispose(); eye = null; eyeKey = "";
    return;
  }
  if (!eye && window.HeartbeatOrb) eye = new window.HeartbeatOrb($("setup-orb"));
  const reduced = motion.matches || document.body.classList.contains("reduced-motion");
  const key = JSON.stringify([state.theme, reduced]);
  if (eye && key !== eyeKey) {
    eyeKey = key;
    eye.update({palette: state.themes[state.theme] || {}, eye: "hal", crt: false,
      reducedMotion: reduced, events: [], statusSeq: 0, liveliness: .35, idle: true, frameRate: 30});
  }
}

export function setupPresentationState() {
  return {step: state.step, watcher: eye?.state() || null};
}

function dateText(iso) {
  const date = iso ? new Date(`${iso}T00:00:00Z`) : null;
  return date && !Number.isNaN(date.getTime())
    ? date.toLocaleDateString(undefined, {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"}) : "—";
}

function showStep(step) {
  state.step = STEPS.includes(step) ? step : "welcome";
  const index = STEPS.indexOf(state.step);
  document.querySelectorAll("#commissioning [data-step]").forEach((node) => { node.hidden = node.dataset.step !== state.step; });
  document.querySelectorAll("#commissioning [data-setup-go]").forEach((node) => {
    const at = STEPS.indexOf(node.dataset.setupGo);
    node.classList.toggle("current", at === index);
    node.classList.toggle("done", at < index);
    if (at === index) node.setAttribute("aria-current", "step");
    else node.removeAttribute("aria-current");
  });
  $("setup-back").hidden = index === 0;
  $("setup-next").hidden = index === STEPS.length - 1;
  $("onboarding-submit").hidden = index !== STEPS.length - 1;
  $("setup-progress").textContent = `STEP ${index + 1} OF ${STEPS.length}`;
  $("setup-next").textContent = {welcome: "LINK MY JOURNALS", journal: "SET UP THE COCKPIT", cockpit: "REVIEW MY SETUP"}[state.step] || "NEXT";
  if (state.step === "launch") renderSummary();
  // Focus moves to the step's heading so the keyboard starts there.
  document.querySelector(`#commissioning [data-step="${state.step}"] h2`)?.focus({preventScroll: true});
  const panel = document.querySelector(`#commissioning [data-step="${state.step}"]`);
  if (panel) panel.scrollTop = 0;
  syncEye();
}

function probe(path) {
  state.probedPath = path;
  ui?.command("onboarding_probe", {journal_path: path});
  renderProbe({probing: true});
}

function queueProbe() {
  renderProbe(state.lastOnboarding || {});
  syncIdentity();
  window.clearTimeout(state.timer);
  state.timer = window.setTimeout(() => {
    const path = $("onboarding-journal").value.trim();
    if (path !== state.probedPath) probe(path);
  }, 450);
}

function renderProbe(onboarding) {
  const card = $("setup-probe");
  const result = onboarding.probe;
  if (onboarding.probing || !result) {
    card.className = "setup-probe checking";
    const html = `<header><i></i><b>CHECKING THE FOLDER…</b></header><p>Looking for Elite Dangerous journals and your latest commander record.</p>`;
    if (card.innerHTML !== html) card.innerHTML = html;
    return;
  }
  // The folder Elite uses is filled in when the commander has not typed one.
  const field = $("onboarding-journal");
  if (result.auto && result.path && !field.value.trim() && document.activeElement !== field) {
    field.value = result.path;
    state.probedPath = result.path;
  }
  const path = field.value.trim();
  if (path ? path !== result.path : result.auto !== true) {
    card.className = "setup-probe warn";
    const html = `<header><i></i><b>FOLDER CHANGED</b></header><p>This folder has not been checked yet. Choose CHECK, or wait for the automatic check.</p>`;
    if (card.innerHTML !== html) card.innerHTML = html;
    return;
  }
  const [label, tone] = STATUS[result.status] || STATUS.invalid;
  const ok = result.status === "ok";
  const facts = ok ? [
    ["JOURNALS", Number(result.journals).toLocaleString()],
    ["COVERING", `${dateText(result.first)} → ${dateText(result.latest)}`],
    ["COMMANDER", result.commander ? `CMDR ${result.commander}` : "—"],
    ["SHIP", [result.ship, result.ship_name].filter(Boolean).join(" · ") || "—"],
    ["LAST SYSTEM", result.system || "—"],
    ["LIVE STATUS", result.live_status ? "STATUS.JSON PRESENT" : "STARTS WITH THE GAME"],
  ] : [];
  card.className = `setup-probe ${tone}`;
  const html = `<header><i></i><b>${label}</b>${result.auto && result.path ? "<em>FOUND AUTOMATICALLY</em>" : ""}</header>
    <p>${esc(result.message)}</p>
    ${facts.length ? `<dl>${facts.map(([name, value]) => `<div><dt>${name}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>` : ""}`;
  if (card.innerHTML !== html) card.innerHTML = html;
}

function renderThemes() {
  const names = Object.keys(state.themes);
  $("setup-themes").innerHTML = names.map((name) => {
    const palette = state.themes[name] || {};
    return `<label class="setup-theme" style="--sw-bg:${esc(palette.bg)};--sw-panel:${esc(palette.panel)};--sw-accent:${esc(palette.accent)};--sw-orange:${esc(palette.orange)};--sw-text:${esc(palette.text)}">
      <input type="radio" name="setup-theme" value="${esc(name)}" ${name === state.theme ? "checked" : ""}>
      <span class="setup-swatch" aria-hidden="true"><i></i><i></i><i></i></span><b>${esc(name)}</b></label>`;
  }).join("");
}

function previewTheme() {
  const palette = state.themes[state.theme];
  if (palette && ui) ui.applyTheme({name: state.theme, palette});
  syncEye();
}

function renderSummary() {
  const result = state.lastOnboarding?.probe || {};
  const path = $("onboarding-journal").value.trim() || (result.auto ? result.path : "") || "";
  const linked = Boolean(linkedProbe());
  const on = (id) => $(id).checked;
  const rows = [
    ["JOURNAL FOLDER", path || "Not set: Void Compass will look in the usual place", linked ? "ok" : "warn"],
    ["COMMANDER", linked && result.commander ? `CMDR ${result.commander} · ${Number(result.journals).toLocaleString()} journals to read` : "Detected from the journal when you fly", linked ? "ok" : ""],
    ["COCKPIT OVERLAYS", on("onboarding-overlays") ? "On: Navigation, Survey Operations and the field HUDs" : "Off: switch them on any time in Overlay Studio", ""],
    ["MOUSE PASSTHROUGH", on("onboarding-passthrough") ? "On: clicks go through the overlays to the game" : "Off: overlays catch the mouse", ""],
    ["ADAPTIVE DECK", on("onboarding-adaptive") ? "On: the deck follows what you are doing" : "Off: the deck stays as you arrange it", ""],
    ["THEME", state.theme || "Void Cyan", ""],
  ];
  const html = rows.map(([name, value, tone], index) => `<div class="${tone}"><dt>${name}</dt><dd><span>${esc(value)}</span>${index === 1 ? "" : `<button type="button" class="setup-summary-edit" data-setup-go="${index === 0 ? "journal" : "cockpit"}" aria-label="Edit ${esc(name.toLowerCase())}">EDIT</button>`}</dd></div>`).join("");
  if ($("setup-summary").innerHTML !== html) $("setup-summary").innerHTML = html;
  $("setup-launch-intro").textContent = linked && result.commander
    ? `Ready, CMDR ${result.commander}. Take one last look at your choices.`
    : "Take one last look at your choices. You can connect your flight journals when they are available.";
}

function submitting(on) {
  for (const control of $("onboarding-form").querySelectorAll("input,button")) control.disabled = on;
  $("onboarding-submit").textContent = on ? "COMMISSIONING…" : "COMMISSION VOID COMPASS";
}

export function renderSetup(onboarding, helpers) {
  ui = helpers;
  state.lastOnboarding = onboarding;
  const session = Number(onboarding.session) || 0;
  if (session !== state.session) {
    state.session = session;
    state.sending = false;
    window.clearTimeout(state.timer);
    state.theme = onboarding.theme || "";
    state.themes = onboarding.themes || {};
    state.probedPath = onboarding.journal_path || "";
    $("onboarding-journal").value = onboarding.journal_path || "";
    $("onboarding-adaptive").checked = Boolean(onboarding.adaptive_command_enabled);
    $("onboarding-overlays").checked = Boolean(onboarding.overlay_enabled);
    $("onboarding-passthrough").checked = Boolean(onboarding.overlay_mouse_passthrough);
    renderThemes();
    showStep("welcome");
  }
  previewTheme();
  renderProbe(onboarding);
  syncIdentity();
  if (state.step === "launch") renderSummary();
  $("onboarding-error").textContent = onboarding.error || "";
  if (onboarding.error && state.step !== "journal") showStep("journal");
  if (onboarding.error) state.sending = false;
  submitting(Boolean(onboarding.submitting || state.sending));
}

export function installSetup(helpers) {
  ui = helpers;
  const form = $("onboarding-form");
  const move = (offset) => showStep(STEPS[Math.max(0, Math.min(STEPS.length - 1, STEPS.indexOf(state.step) + offset))]);
  $("setup-next").addEventListener("click", () => move(1));
  $("setup-back").addEventListener("click", () => move(-1));
  form.addEventListener("click", (event) => {
    const go = event.target.closest("[data-setup-go]");
    if (go) showStep(go.dataset.setupGo);
  });
  $("onboarding-journal").addEventListener("input", queueProbe);
  $("setup-check").addEventListener("click", () => probe($("onboarding-journal").value.trim()));
  $("onboarding-browse").addEventListener("click", async () => {
    const browse = $("onboarding-browse");
    browse.disabled = true;
    try {
      const api = window.pywebview?.api;
      if (!api?.choose_journal_folder) throw new Error("The folder picker is not ready yet");
      const selected = await api.choose_journal_folder();
      if (selected) {
        $("onboarding-journal").value = String(selected);
        probe(String(selected));
      }
    } catch (error) {
      ui.showToast(error.message || "Folder picker unavailable");
    } finally {
      browse.disabled = false;
    }
  });
  form.addEventListener("change", (event) => {
    if (event.target.name === "setup-theme") {
      state.theme = event.target.value;
      previewTheme();
    }
  });
  // Enter moves on through the steps; only the last one commissions.
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.sending || state.lastOnboarding?.submitting) return;
    if (state.step !== "launch") {
      if (event.target === form && document.activeElement?.id === "onboarding-journal") probe($("onboarding-journal").value.trim());
      else move(1);
      return;
    }
    state.sending = true;
    submitting(true);
    const result = state.lastOnboarding?.probe || {};
    const accepted = await ui.command("onboarding_submit", {
      journal_path: $("onboarding-journal").value.trim() || (linkedProbe() ? result.path : ""),
      adaptive_command_enabled: $("onboarding-adaptive").checked,
      overlay_enabled: $("onboarding-overlays").checked,
      overlay_mouse_passthrough: $("onboarding-passthrough").checked,
      ui_theme_name: state.theme,
    });
    if (!accepted) {
      state.sending = false;
      submitting(false);
    }
  });
  $("onboarding-exit").addEventListener("click", () => { window.clearTimeout(state.timer); ui.command("onboarding_cancel"); });
  document.addEventListener("visibilitychange", syncEye);
  window.addEventListener("voidcompass:boot", syncEye);
  window.addEventListener("heartbeat-three-ready", syncEye);
  motion.addEventListener("change", syncEye);
  window.addEventListener("pagehide", () => { eye?.dispose(); window.clearTimeout(state.timer); });
}
