// Settings › Helm (5.8.6): Elite's controls and
// Void Compass's own shortcuts, in one place.
//   BINDS      every control of a binds file, by section; click a slot to change it
//   PRESETS    which binds file each section reads (StartPreset), and editable copies
//   CREW KEYS  the keys the crew's ship commands press, and ASSIGN MISSING KEYS
//   SHORTCUTS  Void Compass's own shortcuts (they were Settings › Hotkeys)
//   BACKUPS    every backup, BACK UP NOW, RESTORE, and the game installs found
// Edits wait on screen until APPLY, which checks, backs up and writes. Its status
// comes from /api/data/helm-status while it's on screen (Settings redraws
// round it: its host is data-morph-keep); a file's big table comes from
// /api/data/helm-file when its revision changes.

const TABS = [["binds", "BINDS"], ["devices", "DEVICES"], ["presets", "PRESETS"], ["crew", "CREW KEYS"], ["shortcuts", "SHORTCUTS"], ["backups", "BACKUPS"]];
const SECTIONS = [["general", "General"], ["ship", "Ship"], ["srv", "SRV"], ["onfoot", "On foot"]];
const SECTION_LABEL = Object.fromEntries([...SECTIONS, ["other", "Other"]]);
const MODIFIER_CODES = {ControlLeft: "Key_LeftControl", ControlRight: "Key_RightControl", ShiftLeft: "Key_LeftShift",
  ShiftRight: "Key_RightShift", AltLeft: "Key_LeftAlt", AltRight: "Key_RightAlt"};
const NAMED_CODES = {Space: "Key_Space", Enter: "Key_Enter", Tab: "Key_Tab", Escape: "Key_Escape", Backspace: "Key_Backspace",
  ArrowUp: "Key_UpArrow", ArrowDown: "Key_DownArrow", ArrowLeft: "Key_LeftArrow", ArrowRight: "Key_RightArrow",
  Insert: "Key_Insert", Delete: "Key_Delete", Home: "Key_Home", End: "Key_End", PageUp: "Key_PageUp", PageDown: "Key_PageDown",
  Minus: "Key_Minus", Equal: "Key_Equals", BracketLeft: "Key_LeftBracket", BracketRight: "Key_RightBracket",
  Backslash: "Key_BackSlash", Semicolon: "Key_SemiColon", Quote: "Key_Apostrophe", Comma: "Key_Comma", Period: "Key_Period",
  Slash: "Key_Slash", Backquote: "Key_Grave", CapsLock: "Key_CapsLock", NumLock: "Key_NumLock", ScrollLock: "Key_ScrollLock",
  Pause: "Key_Pause", ContextMenu: "Key_Apps", MetaLeft: "Key_LeftWin", MetaRight: "Key_RightWin",
  NumpadAdd: "Key_Numpad_Add", NumpadSubtract: "Key_Numpad_Subtract", NumpadMultiply: "Key_Numpad_Multiply",
  NumpadDivide: "Key_Numpad_Divide", NumpadDecimal: "Key_Numpad_Decimal", NumpadEnter: "Key_NumpadEnter",
  IntlBackslash: "Key_OEM102"};
const KEY_WORDS = {LeftControl: "Left Ctrl", RightControl: "Right Ctrl", LeftShift: "Left Shift", RightShift: "Right Shift",
  LeftAlt: "Left Alt", RightAlt: "Right Alt", LeftArrow: "←", RightArrow: "→", UpArrow: "↑", DownArrow: "↓", SemiColon: ";",
  Apostrophe: "'", Comma: ",", Period: ".", Slash: "/", BackSlash: "\\", Minus: "-", Equals: "=", LeftBracket: "[",
  RightBracket: "]", Grave: "`", Hash: "#", PageUp: "Page Up", PageDown: "Page Down", CapsLock: "Caps Lock",
  NumLock: "Num Lock", ScrollLock: "Scroll Lock", Escape: "Esc", Apps: "Menu", LeftWin: "Left Win", RightWin: "Right Win"};
const CREW_STATES = {ready: "READY", odd: "CAN'T PRESS", device: "PAD/STICK ONLY", missing: "NO KEY", absent: "NOT IN FILE"};

let last = {};
let ui = null;
let bound = null;
let tab = "binds";
let section = "all";
let query = "";
let crewOnly = false;
let fileName = "";
let file = null;          // the table of fileName
let fileKey = "";         // name|revision it was fetched for
let fileLoading = "";
let dialog = null;        // {kind, ...}
let copyForm = null;      // the editable copy form on PRESETS / CREW KEYS
let offered = "";         // the unnamed controllers the naming dialog last opened for by itself
let reconcilePicks = {};  // whose each differing device item is, before it's kept
let testing = null;       // DEVICES' button tester: {ident, pad, labels}
let live = null;          // its last readout
let liveTimer = 0;
const PAD_KEYS = ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "Back", "Start", "LS", "RS", "Up", "Down", "Left", "Right"];
let holder = null;        // {key, holder_label, reserved} for the dialog's candidate

const esc = (value) => (ui ? ui.escapeHtml(value) : String(value ?? ""));
const n = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
const whole = (value) => Math.round(n(value)).toLocaleString("en-GB");
const fold = (value) => String(value || "").toLowerCase();

let pollTimer = 0;
let polling = false;

// Settings draws Helm's host and calls this after each of its redraws.
export function mountHelm(workshopUi) {
  ui = workshopUi;
  const root = ui.byId("helm-workspace");
  if (!root) return;
  if (bound !== root) {
    bound = root;
    root.innerHTML = `<div class="bf-main"><p class="bf-empty">Reading your controls…</p></div>`;
    listen(root);
    if (last.revision !== undefined) render(last);
  }
  if (!pollTimer && !polling) refresh();
}

function listen(node) {
  node.addEventListener("click", onClick);
  node.addEventListener("change", onChange);
  node.addEventListener("input", onInput);
  node.addEventListener("keydown", onKeyDown, true);
  node.addEventListener("keyup", onKeyUp, true);
}

// The dialogs sit on <body>: inside Settings, "fixed" would be fixed to its panel, not the screen.
function dialogHost() {
  let host = document.getElementById("helm-dialogs");
  if (!host) {
    host = document.createElement("div");
    host.id = "helm-dialogs";
    document.body.appendChild(host);
    listen(host);
  }
  return host;
}

// A dialog open: Settings mustn't redraw round it.
export function helmBusy() {
  return Boolean(dialog);
}

// Asked while on screen: quickly while a controller press is awaited, else every 1.5 s.
async function refresh() {
  window.clearTimeout(pollTimer);
  pollTimer = 0;
  const root = ui?.byId("helm-workspace");
  if (!root || !root.isConnected) return;
  if (root.offsetParent === null || document.hidden) {
    if (dialog && root.offsetParent === null) closeDialog();   // left Helm: its dialog goes too
    pollTimer = window.setTimeout(refresh, 1500);
    return;
  }
  polling = true;
  try {
    const response = await fetch(ui.apiUrl("/api/data/helm-status"), {cache: "no-store"});
    if (response.ok) render(await response.json());
  } catch {
    /* tried again shortly */
  } finally {
    polling = false;
  }
  const listening = last.capture?.status === "listening";
  pollTimer = window.setTimeout(refresh, listening ? 300 : 1500);
}

function render(data) {
  last = data || {};
  chooseFile();
  ensureFile();
  offerNaming();
  draw();
  drawDialog();
}

// Settings › Voice's "ASSIGN IN HELM" opens CREW KEYS.
document.addEventListener("click", (event) => {
  const link = event.target.closest?.("[data-helm-tab]");
  if (link) tab = link.dataset.helmTab;
}, true);

function chooseFile() {
  const files = last.files || [];
  if (fileName && (files.includes(fileName) || (last.factories || []).includes(fileName))) return;
  // The file the ship reads, else the first of yours, else the ship's built-in one.
  const ship = (last.sections || []).find((row) => row.section === "ship") || {};
  fileName = (ship.kind === "user" && ship.file) || files[0] || (ship.kind === "factory" ? ship.preset : "") || "";
}

function ensureFile() {
  if (!fileName || !ui) return;
  const key = `${fileName}|${last.revision}`;
  if (fileKey === key || fileLoading === key) return;
  fileLoading = key;
  fetch(ui.apiUrl(`/api/data/helm-file?name=${encodeURIComponent(fileName)}`), {cache: "no-store"})
    .then((response) => response.json())
    .then((data) => { if (fileLoading === key) { file = data; fileKey = key; fileLoading = ""; draw(true); drawDialog(); } })
    .catch(() => { fileLoading = ""; });
}

async function op(operation, extra = {}) {
  if (!ui) return false;
  try {
    const response = await fetch(ui.apiUrl("/api/command"), {
      method: "POST", cache: "no-store", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action: "workspace", page: "helm", operation, ...extra}),
    });
    const reply = await response.json().catch(() => ({}));
    refresh();
    return Boolean(reply.accepted);
  } catch {
    return false;
  }
}

// -- names ------------------------------------------------------------------------
function keyName(key) {
  const text = String(key || "");
  if (!text.startsWith("Key_")) return text;
  const rest = text.slice(4);
  if (rest.startsWith("Numpad_")) return `Num ${{Add: "+", Subtract: "-", Multiply: "*", Divide: "/", Decimal: "."}[rest.slice(7)] || rest.slice(7)}`;
  return KEY_WORDS[rest] || rest;
}

function inputName(device, key) {
  if (device === "Keyboard") return keyName(key);
  const mouse = (file?.inputs?.mouse || []).find(([token]) => token === key);
  if (device === "Mouse") return mouse ? mouse[1] : key;
  const pad = (file?.inputs?.pad || []).find(([, token]) => token === key);
  if (pad) return `Pad ${pad[0]}`;
  const dev = (file?.devices || {})[device] || device;
  const joy = /^(Pos_|Neg_)?Joy_(.+)$/i.exec(key || "");
  if (!joy) return `${dev} ${key}`;
  if (/^\d+$/.test(joy[2])) return `${dev} ${joy[2]}`;
  const hat = /^POV(\d)(Up|Down|Left|Right)$/i.exec(joy[2]);
  if (hat) return `${dev} hat ${{up: "↑", down: "↓", left: "←", right: "→"}[hat[2].toLowerCase()]}`;
  return `${dev} ${joy[2].replace(/Axis$/i, "").toUpperCase()} axis${joy[1] === "Pos_" ? "+" : joy[1] === "Neg_" ? "−" : ""}`;
}

function chordName(device, key, modifiers = []) {
  return [...modifiers.map(([d, k]) => inputName(d, k)), inputName(device, key)].join(" + ");
}

// -- drawing ----------------------------------------------------------------------
function draw(force = false) {
  const root = ui?.byId("helm-workspace");
  const main = root?.querySelector(".bf-main");
  if (!main) return;
  if (tab === "shortcuts" && ui.shortcutsBusy?.()) return;
  const focused = document.activeElement;
  if (!force && main.contains(focused) && focused.matches("input:not([type=checkbox]), select, textarea")) return;
  const markup = `${bar()}<nav class="bf-tabs" role="tablist">${TABS.map(([key, label]) => `<button type="button" class="bf-tab${tab === key ? " on" : ""}" data-bf="tab" data-tab="${key}" role="tab" aria-selected="${tab === key}">${label}${tabCount(key)}</button>`).join("")}</nav><div class="bf-body bf-body-${tab}">${body()}</div>`;
  if (main.dataset.markup === markup) return;
  const caret = focused?.dataset?.bfSearch ? focused.selectionStart : null;
  main.dataset.markup = markup;
  main.innerHTML = markup;
  if (caret !== null) {
    const input = main.querySelector("[data-bf-search]");
    if (input) { input.focus(); try { input.setSelectionRange(caret, caret); } catch { /* search */ } }
  }
  if (tab === "shortcuts") {
    ui.applyHotkeyFilter?.();
    ui.startControllerLive?.();
  }
  if (testing) {
    if (!(last.devices?.rows || []).some((row) => row.connected && row.ident === testing.ident)) stopTest();
    else applyLive();
  }
}

function tabCount(key) {
  if (key === "crew") {
    const missing = (last.crew || []).filter((row) => row.state !== "ready").length;
    return missing ? ` <b class="warn">${whole(missing)}</b>` : "";
  }
  if (key === "binds" && file && !file.error) {
    const count = (file.conflicts || []).filter((row) => !row.shadow).length + (file.reserved || []).length;
    return count ? ` <b class="warn">${whole(count)}</b>` : "";
  }
  if (key === "backups") return ` <b>${whole((last.backups || []).length)}</b>`;
  if (key === "devices" && last.devices?.unnamed) return ` <b class="warn">${whole(last.devices.unnamed)}</b>`;
  return "";
}

function bar() {
  const pending = last.pending || [];
  const note = last.notice;
  const check = last.check;
  let html = "";
  if (!last.folder_found) {
    html += `<div class="bf-banner warn"><b>ELITE'S BINDINGS FOLDER WASN'T FOUND</b><span>${esc(last.folder || "%LOCALAPPDATA%\\Frontier Developments\\Elite Dangerous\\Options\\Bindings")}: the game makes it once you've played through the start. Helm can't edit or back up anything until then.</span></div>`;
  } else if (!last.set_up) {
    html += `<div class="bf-banner"><b>SET UP HELM</b><span>It backs up every control file first (that backup is kept for good), then keeps a working copy of them in Void Compass's folder. Nothing in the game's files changes until you press APPLY.</span><button type="button" class="primary" data-bf="setup">SET UP</button></div>`;
  }
  if ((check?.reconcile || []).length) html += reconcileBanner(check.reconcile);
  const unnamed = last.devices?.unnamed || 0;
  if (unnamed && last.set_up && !(check?.reconcile || []).length) {
    html += `<div class="bf-banner"><b>${whole(unnamed)} CONTROLLER${unnamed === 1 ? " HAS" : "S HAVE"} NO NAME YET</b><span>A name lets the game keep your bindings when a firmware update changes the controller's ids, and labels its buttons. Bindings made on it so far move to the name.</span><button type="button" class="primary" data-bf="name-open">NAME ${unnamed === 1 ? "IT" : "THEM"}</button></div>`;
  }
  if (check?.changed) html += checkBanner(check);
  html += `<div class="bf-bar${pending.length ? " pending" : ""}"><span class="bf-bar-state">${pending.length
    ? `<b>${whole(pending.length)} FILE${pending.length === 1 ? "" : "S"} WITH EDITS</b><small>${pending.map(esc).join(" · ")}</small>`
    : `<b>NO EDITS WAITING</b><small>${last.set_up ? "The game's files match Helm's working copy." : "Edits wait here until APPLY."}</small>`}</span>`
    + `<span class="bf-bar-actions"><button type="button" class="ghost" data-bf="discard"${pending.length ? "" : " disabled"}>DISCARD</button><button type="button" class="primary" data-bf="apply-ask"${pending.length && last.folder_found ? "" : " disabled"}>APPLY</button></span></div>`;
  if (note?.text) html += `<p class="bf-notice ${esc(note.severity || "info")}">${esc(note.text)}</p>`;
  return html;
}

function checkBanner(check) {
  const rows = (check.files || []).map((row) => {
    let what = row.state === "new" ? "in the game's folder only" : row.state === "gone" ? "gone from the game's folder" : "changed";
    if (row.preset) what = `lines changed: game has ${(row.game || []).map(esc).join(" / ")}`;
    const detail = row.detail || {};
    const parts = [detail.changed && `${detail.changed} changed`, detail.added && `${detail.added} new`, detail.removed && `${detail.removed} gone`].filter(Boolean);
    const labels = (detail.labels || []).length ? `<small>${detail.labels.map(esc).join(" · ")}</small>` : "";
    const reset = row.reset ? `<em>It now matches the game's own ${esc(row.reset)}: a game update probably reset it. KEEP MINE puts yours back.</em>` : "";
    return `<li><b>${esc(row.file)}</b><span>${esc(what)}${parts.length ? ` (${parts.join(", ")})` : ""}</span>${labels}${reset}</li>`;
  }).join("");
  const merges = (check.files || []).filter((row) => row.state === "changed")
    .map((row) => `<button type="button" data-bf="merge-open" data-file="${esc(row.file)}">MERGE ${esc(row.file)}…</button>`).join("");
  const installs = (check.installs || []).map((row) => `<li><b>${esc(row.install)}: device files</b><span>${row.items.length} item${row.items.length === 1 ? "" : "s"} differ: ${row.items.slice(0, 6).map((item) => esc(item.name)).join(" · ")}</span>${row.reset ? "<em>They look reset to the game's own (a game update, probably): KEEP MINE puts yours back.</em>" : ""}<span class="bf-actions"><button type="button" data-bf="merge-install-open" data-install="${esc(row.install)}">MERGE…</button><button type="button" data-bf="take_games" data-install="${esc(row.install)}" data-confirm="Make ${esc(row.install)}'s device files (and the game's binds files) Helm's working copy?">TAKE ${esc(row.install.toUpperCase())}'S</button></span></li>`).join("");
  const reset = (check.files || []).some((row) => row.reset) || (check.installs || []).some((row) => row.reset);
  return `<div class="bf-banner warn bf-check"><b>YOUR CONTROL FILES CHANGED OUTSIDE HELM</b><span>In the game's Options › Controls, or a game update. Both sides are backed up before either is replaced.</span><ul>${rows}${installs}</ul><div class="bf-actions"><button type="button" class="primary" data-bf="keep_mine">KEEP MINE</button><button type="button" data-bf="take_games"${reset ? ` data-confirm="It looks like a game update reset your files. Take them anyway?"` : ""}>TAKE THE GAME'S</button>${merges}<button type="button" class="ghost" data-bf="check">CHECK AGAIN</button></div></div>`;
}

function reconcileBanner(items) {
  const installs = [...new Set(items.flatMap((item) => Object.keys(item.values)))];
  const rows = items.map((item) => `<li><b>${esc(item.kind === "labels" ? `${item.name} (button labels)` : item.name)}</b><span class="bf-picks">${installs.map((install) => `<label class="bf-check"><input type="radio" name="rc-${esc(item.item)}" data-bf="reconcile-pick" data-item="${esc(item.item)}" value="${esc(install)}"${(reconcilePicks[item.item] || installs[0]) === install ? " checked" : ""}> ${esc(install)}: ${esc(item.values[install])}</label>`).join("")}</span></li>`).join("");
  return `<div class="bf-banner warn bf-check"><b>YOUR GAME INSTALLS HAVE DIFFERENT DEVICE FILES</b><span>The game reads one set of binds files for every install, but each install has its own device names. An install missing a name your bindings use falls back to the default controls, so they must agree. Pick whose each one is; every install gets the result (backed up first).</span><ul>${rows}</ul><div class="bf-actions"><button type="button" class="primary" data-bf="reconcile">KEEP THESE</button>${installs.map((install) => `<button type="button" data-bf="reconcile-all" data-install="${esc(install)}">KEEP ALL OF ${esc(install.toUpperCase())}'S</button>`).join("")}</div></div>`;
}

function body() {
  if (tab === "devices") return devicesBody();
  if (tab === "presets") return presetsBody();
  if (tab === "crew") return crewBody();
  if (tab === "shortcuts") return `<div class="bf-shortcuts" data-settings-host>${ui.shortcuts ? ui.shortcuts(last.shortcuts || {}) : ""}</div>`;
  if (tab === "backups") return backupsBody();
  return bindsBody();
}

// -- BINDS --------------------------------------------------------------------------
function fileOptions() {
  const mine = (last.files || []).map((name) => `<option value="${esc(name)}"${name === fileName ? " selected" : ""}>${esc(name)}</option>`).join("");
  const built = (last.factories || []).map((name) => `<option value="${esc(name)}"${name === fileName ? " selected" : ""}>${esc(name)} (built in)</option>`).join("");
  return `${mine ? `<optgroup label="Yours">${mine}</optgroup>` : ""}${built ? `<optgroup label="The game's (view only)">${built}</optgroup>` : ""}`;
}

function bindsBody() {
  const head = `<div class="bf-toolbar"><label class="bf-field">FILE<select data-bf="file">${fileOptions()}</select></label><div class="bf-chips" role="group">${[["all", "ALL"], ...SECTIONS.map(([key, label]) => [key, label.toUpperCase()]), ["anomalies", "PROBLEMS"], ["toggles", "TOGGLES"], ["sensitivity", "SENSITIVITY"]].map(([key, label]) => `<button type="button" class="bf-chip${section === key ? " on" : ""}" data-bf="section" data-section="${key}">${label}${key === "anomalies" ? anomalyCount() : ""}</button>`).join("")}</div><label class="bf-search"><input type="search" data-bf-search placeholder="Find a control or key…" value="${esc(query)}"></label><label class="bf-check"><input type="checkbox" data-bf="crew-only"${crewOnly ? " checked" : ""}> Crew's only</label></div>`;
  if (!fileName) return head + `<p class="bf-empty">No binds file yet: pick a preset on PRESETS, or make an editable copy of one of the game's.</p>`;
  if (!file || fileKey.split("|")[0] !== fileName) return head + `<p class="bf-empty">Reading ${esc(fileName)}…</p>`;
  if (file.error) return head + `<p class="bf-empty">${esc(file.error)}</p>`;
  const using = (file.sections_using || []).map((key) => SECTION_LABEL[key]).join(", ");
  const info = file.editable
    ? `<p class="bf-info">${using ? `The game reads this file for <b>${esc(using)}</b>.` : "No section reads this file now (PRESETS chooses)."} Click a slot to change it.${file.azerty ? " An AZERTY file: number-row keys go by their own names here." : ""}</p>`
    : `<p class="bf-info warn">One of the game's own presets: it can't be changed. <button type="button" data-bf="copy-open" data-factory="${esc(fileName)}">MAKE AN EDITABLE COPY</button></p>`;
  if (section === "anomalies") return head + info + anomalies();
  if (section === "toggles") return head + info + togglesView();
  if (section === "sensitivity") return head + info + sensitivityView();
  return head + info + grid();
}

// -- TOGGLES and SENSITIVITY ------------------------------------------------------------
function grouped(rows, render) {
  let html = "", heading = "";
  for (const row of rows) {
    const title = `${SECTION_LABEL[row.section] || ""}${row.group ? ` · ${row.group}` : ""}`;
    if (title !== heading) { heading = title; html += `<div class="bf-group">${esc(title.toUpperCase())}</div>`; }
    html += render(row);
  }
  return html;
}

function togglesView() {
  const rows = (file.toggles || []).filter((row) => !query || fold(`${row.name} ${row.group} ${row.tag}`).includes(fold(query)));
  if (!rows.length) return `<p class="bf-empty">No yes/no settings ${query ? "match" : "in this file"}.</p>`;
  return `<div class="bf-grid bf-settings">${grouped(rows, (row) => `<div class="bf-setting"><span class="bf-name"><b>${esc(row.name)}</b><small>${esc(row.tag)}</small></span><span class="bf-onoff">${["ON", "OFF"].map((word) => `<button type="button" class="bf-chip${(word === "ON") === row.on ? " on" : ""}" data-bf="toggle" data-tag="${esc(row.tag)}" data-value="${word === "ON" ? 1 : 0}"${file.editable && row.editable ? "" : " disabled"}>${word}</button>`).join("")}</span></div>`)}</div>`;
}

function sensitivityView() {
  const editable = file.editable;
  const numbers = (file.numbers || []).map((row) => {
    const range = row.range;
    const slider = range ? `<input type="range" min="${range[0]}" max="${range[1]}" step="${range[2]}" value="${esc(row.value)}" data-bf="number-slide" data-tag="${esc(row.tag)}"${editable && row.editable ? "" : " disabled"}>` : "";
    return `<div class="bf-setting"><span class="bf-name"><b>${esc(row.name)}</b><small>${esc(row.group)}</small></span><span class="bf-number">${slider}<input class="bf-number-box" value="${esc(row.value)}" data-bf="number" data-tag="${esc(row.tag)}"${editable && row.editable ? "" : " disabled"}></span></div>`;
  }).join("");
  const throttles = (file.throttles || []).map((row) => `<div class="bf-setting"><span class="bf-name"><b>${esc(row.name)}</b><small>Throttle range</small></span><span class="bf-onoff">${[["full", "FULL RANGE"], ["forward", "FORWARD ONLY"]].map(([key, word]) => `<button type="button" class="bf-chip${row.reading === key ? " on" : ""}" data-bf="throttle" data-axis="${esc(row.axis)}" data-forward="${key === "forward" ? 1 : 0}"${editable && row.editable ? "" : " disabled"}>${word}</button>`).join("")}</span></div>`).join("");
  const zones = (file.deadzones || []).map((row) => `<div class="bf-setting"><span class="bf-name"><b>${esc(row.name)}</b><small>${esc(row.label)}</small></span><span class="bf-number"><input type="range" min="0" max="1" step="0.01" value="${row.deadzone}" data-bf="zone" data-tag="${esc(row.tag)}"${editable && row.editable ? "" : " disabled"}><b class="bf-zone">${n(row.deadzone).toFixed(2)}</b></span></div>`).join("");
  return `<section class="bf-card"><h4>MOUSE AND CAMERA</h4><p class="bf-dim">Sensitivities, curves and dead zones as the game's own sliders set them (a number past their stops is kept as you have it). Changes wait for APPLY.</p><div class="bf-settings">${numbers || "<p class='bf-empty'>None in this file.</p>"}</div></section>`
    + (throttles ? `<section class="bf-card"><h4>THROTTLE RANGE</h4><div class="bf-settings">${throttles}</div></section>` : "")
    + `<section class="bf-card"><h4>AXIS DEAD ZONES</h4><p class="bf-dim">Every axis you've bound. Invert and the axis itself are in BINDS (click the axis).</p><div class="bf-settings">${zones || "<p class='bf-empty'>No axes bound in this file.</p>"}</div></section>`;
}

// -- DEVICES ----------------------------------------------------------------------------
function devicesBody() {
  const view = last.devices;
  if (!last.set_up) return `<p class="bf-empty">Set Helm up first (the banner above).</p>`;
  if (!view) return `<p class="bf-empty">Reading your controllers…</p>`;
  const rows = view.rows || [];
  const table = rows.length ? `<div class="bf-devices">${rows.map((row) => `<div class="bf-device${row.connected ? "" : " away"}"><span class="bf-name"><b>${esc(row.name || "No name yet")}</b><small>${esc(row.reported || "not connected")}${row.pad ? "" : ` · ${esc(row.ident)}`}${row.builtin ? " · the game's own name" : ""}</small></span><span class="bf-dim">${row.connected ? "CONNECTED" : "NOT CONNECTED"}</span><span class="bf-dim">${row.pad ? "Buttons shown with the game's own pad icons" : `${whole(row.labels)} labels`} · ${whole(row.refs)} binding${row.refs === 1 ? "" : "s"}${row.by_id ? ` (${whole(row.by_id)} by its id)` : ""}</span><span class="bf-actions">${row.connected ? `<button type="button" class="${testing?.ident === row.ident ? "primary" : "ghost"}" data-bf="test" data-ident="${esc(row.ident)}" data-name="${esc(row.name || "")}" data-pad="${row.pad ? 1 : 0}" data-buttons="${row.buttons || 0}" data-hats="${row.hats || 0}">${testing?.ident === row.ident ? "STOP TEST" : "TEST"}</button>` : ""}${row.pad ? `<span class="bf-dim">NO NAME NEEDED</span>` : row.name ? `<button type="button" data-bf="device-open" data-name="${esc(row.name)}">EDIT</button>` : `<button type="button" class="primary" data-bf="name-open" data-ident="${esc(row.ident)}">NAME</button>`}</span></div>${testing?.ident === row.ident ? testPanel(row) : ""}`).join("")}</div>` : `<p class="bf-empty">No controller is connected, and none has a name of yours. Plug one in or switch it on: it shows here within a few seconds.</p>`;
  return `<section class="bf-card"><h4>YOUR CONTROLLERS</h4><p class="bf-dim">Each controller is known to the game by a name (DeviceMappings.xml), with its buttons' labels beside it. A controller with no name is bound by its USB ids, and a firmware update that changes them loses every binding; with a name, it costs one edit here. Every install gets the same names when you APPLY. Xbox-style pads need no name: the game knows every one as GamePad.</p><div class="bf-actions"><button type="button" data-bf="name-open"${view.unnamed ? "" : " disabled"}>NAME EVERY NEW CONTROLLER</button></div></section>${table}`;
}

function anomalyCount() {
  if (!file || file.error) return "";
  const count = (file.conflicts || []).length + (file.reserved || []).length + (file.invalid || []).length;
  return count ? ` <b>${whole(count)}</b>` : "";
}

function conflictMap() {
  const map = new Map();
  for (const row of file.conflicts || []) {
    for (const [action, position, other] of [[row.a, row.position_a, row.b], [row.b, row.position_b, row.a]]) {
      const key = `${action}|${position}`;
      const list = map.get(key) || [];
      list.push({...row, other});
      map.set(key, list);
    }
  }
  for (const row of file.reserved || []) {
    const key = `${row.action}|${row.position}`;
    const list = map.get(key) || [];
    list.push({reserved: true, text: `${row.reason}: ${row.fix}`});
    map.set(key, list);
  }
  return map;
}

function matches(row) {
  if (section !== "all" && row.section !== section) return false;
  if (crewOnly && !(file.crew || []).includes(row.tag)) return false;
  if (!query) return true;
  const text = fold(`${row.group} ${row.name} ${row.tag} ${(row.slots || []).map((slot) => slot?.label || "").join(" ")} ${row.axis?.label || ""}`);
  return fold(query).split(/\s+/).every((word) => text.includes(word));
}

function grid() {
  const rows = (file.rows || []).filter(matches);
  if (!rows.length) return `<p class="bf-empty">No control matches.</p>`;
  const clashes = conflictMap();
  const crew = new Set(file.crew || []);
  let html = `<div class="bf-grid" role="table"><div class="bf-row bf-head" role="row"><span>CONTROL</span><span>PRIMARY</span><span>SECONDARY</span></div>`;
  let heading = "";
  for (const row of rows) {
    const title = `${SECTION_LABEL[row.section] || "Other"}${row.group ? ` · ${row.group}` : ""}`;
    if (title !== heading) {
      heading = title;
      html += `<div class="bf-group" role="row">${esc(title.toUpperCase())}</div>`;
    }
    const name = `<span class="bf-name"><b>${esc(row.name)}</b>${crew.has(row.tag) ? `<em class="bf-crew-tag" title="The crew's ship commands press this">CREW</em>` : ""}<small>${esc(row.tag)}</small></span>`;
    if (row.kind === "axis") {
      const axis = row.axis || {};
      const extra = [axis.inverted && "inverted", axis.deadzone && `dead zone ${n(axis.deadzone).toFixed(2)}`].filter(Boolean).join(" · ");
      html += `<div class="bf-row bf-axis" role="row">${name}<button type="button" class="bf-slot bf-slot-wide${axis.bound ? "" : " empty"}" data-bf="axis" data-tag="${esc(row.tag)}"${file.editable && axis.editable ? "" : " disabled"}><b>${esc(axis.label || "—")}</b>${extra ? `<small>${esc(extra)}</small>` : ""}<i>AXIS</i></button></div>`;
      continue;
    }
    const cells = (row.slots || []).map((slot, index) => {
      const position = index ? "Secondary" : "Primary";
      if (!slot) return `<span class="bf-slot none">—</span>`;
      const found = clashes.get(`${row.tag}|${position}`) || [];
      const level = found.some((item) => item.blocking || item.reserved) ? " bad" : found.some((item) => !item.shadow) ? " clash" : found.length ? " shadow" : "";
      const tip = found.map((item) => item.text).join("\n");
      return `<button type="button" class="bf-slot${slot.assigned ? "" : " empty"}${level}" data-bf="slot" data-tag="${esc(row.tag)}" data-position="${position}"${file.editable ? "" : " disabled"}${tip ? ` title="${esc(tip)}"` : ""}><b>${esc(slot.label || "—")}</b>${slot.hold ? "<i>HOLD</i>" : ""}${found.length ? `<i class="bf-flag">${found.some((item) => item.reserved) ? "RESERVED" : found.some((item) => !item.shadow) ? "CLASH" : "SHADOW"}</i>` : ""}</button>`;
    }).join("");
    html += `<div class="bf-row" role="row">${name}${cells}</div>`;
  }
  return html + `</div>`;
}

function controlName(tag) {
  const row = (file?.rows || []).find((item) => item.tag === tag);
  return row ? `${SECTION_LABEL[row.section] || ""} › ${row.group ? `${row.group} › ` : ""}${row.name}` : tag;
}

function anomalies() {
  const conflicts = file.conflicts || [];
  const hard = conflicts.filter((row) => !row.shadow);
  const shadows = conflicts.filter((row) => row.shadow);
  const list = (rows, render) => rows.length ? `<ul class="bf-list">${rows.map(render).join("")}</ul>` : `<p class="bf-empty">None.</p>`;
  const jump = (tag, position) => file.editable ? ` data-bf="slot" data-tag="${esc(tag)}" data-position="${esc(position)}"` : "";
  return `<section class="bf-card"><h4>RESERVED KEYS <b>${whole((file.reserved || []).length)}</b></h4><p class="bf-dim">Keys the system or the game menu take first: Alt+F4 closes the game, and anything on the Game Menu's key opens the menu.</p>${list(file.reserved || [], (row) => `<li><button type="button" class="bf-link"${jump(row.action, row.position)}>${esc(controlName(row.action))}</button><span>${esc(row.chord.map(keyName).join(" + "))}: ${esc(row.reason)}</span><small>Fix: ${esc(row.fix)}.</small></li>`)}</section>`
    + `<section class="bf-card"><h4>CLASHES <b>${whole(hard.length)}</b></h4><p class="bf-dim">Two controls live at the same time on one input: pressing it does both. BLOCKING ones stop the crew's menu and map moves.</p>${list(hard, (row) => `<li class="${row.blocking ? "bad" : ""}"><button type="button" class="bf-link"${jump(row.a, row.position_a)}>${esc(controlName(row.a))}</button><button type="button" class="bf-link"${jump(row.b, row.position_b)}>${esc(controlName(row.b))}</button><span>${row.blocking ? "<b>BLOCKING</b> " : ""}${esc(row.text)}</span></li>`)}</section>`
    + `<section class="bf-card"><h4>MODIFIER SHADOWS <b>${whole(shadows.length)}</b></h4><p class="bf-dim">A combination whose modifier is bound on its own too: the bare one fires first as you press the combination.</p>${list(shadows, (row) => `<li><button type="button" class="bf-link"${jump(row.a, row.position_a)}>${esc(controlName(row.a))}</button><button type="button" class="bf-link"${jump(row.b, row.position_b)}>${esc(controlName(row.b))}</button><span>${esc(row.text)}</span></li>`)}</section>`
    + ((file.invalid || []).length ? `<section class="bf-card"><h4>KEYS THIS LAYOUT CAN'T NAME <b>${whole(file.invalid.length)}</b></h4><p class="bf-dim">An AZERTY file names the number row by its own characters, so these keys can't be told apart in game.</p>${list(file.invalid, (row) => `<li><button type="button" class="bf-link"${jump(row.action, row.position)}>${esc(controlName(row.action))}</button><span>${esc(keyName(row.key))}</span></li>`)}</section>` : "")
    + ((file.twins || []).length ? `<section class="bf-card"><h4>SHIP AND SRV ON DIFFERENT KEYS <b>${whole(file.twins.length)}</b></h4><p class="bf-dim">Not a problem: many commanders like the same key in both. Just so you know.</p>${list(file.twins, (row) => `<li><span>${esc(controlName(row.ship))}</span><span>${esc(controlName(row.srv))}</span></li>`)}</section>` : "");
}

// -- PRESETS ------------------------------------------------------------------------
function presetNames() {
  const mine = [...new Set((last.files || []).map((name) => name.replace(/\.\d+\.\d+\.binds$/i, "")))];
  return {mine, built: last.factories || []};
}

function presetsBody() {
  const rows = last.sections || [];
  const {mine, built} = presetNames();
  const options = (current) => `${mine.length ? `<optgroup label="Yours">${mine.map((name) => `<option${name === current ? " selected" : ""}>${esc(name)}</option>`).join("")}</optgroup>` : ""}<optgroup label="The game's">${built.map((name) => `<option${name === current ? " selected" : ""}>${esc(name)}</option>`).join("")}</optgroup>${current && ![...mine, ...built].includes(current) ? `<option selected>${esc(current)}</option>` : ""}`;
  const lines = rows.length ? rows : SECTIONS.map(([key]) => ({section: key, preset: "", kind: "missing", file: ""}));
  const differ = new Set(lines.map((row) => row.preset)).size > 1;
  const table = lines.map((row) => `<div class="bf-preset"><span>${esc(SECTION_LABEL[row.section])}</span><select data-bf="preset" data-section="${row.section}">${options(row.preset)}</select><small class="${row.kind === "missing" ? "bad" : ""}">${row.kind === "user" ? `Your file: ${esc(row.file)}` : row.kind === "factory" ? "Built in: view only (make a copy to edit)" : "No file found for this preset"}</small></div>`).join("");
  return `<section class="bf-card"><h4>WHICH FILE EACH SECTION READS</h4><p class="bf-dim">Elite reads one binds file for each of its four sections (StartPreset.4.start). Usually all four are the same.${differ ? " <b>Yours differ</b>: that's allowed, but each section's controls come from its own file." : ""}</p>${table}<div class="bf-actions"><label class="bf-field">SET ALL TO<select data-bf="preset-all"><option value="">Choose…</option>${[...mine, ...built].map((name) => `<option>${esc(name)}</option>`).join("")}</select></label></div></section>${copyCard()}`;
}

function copyCard(defaults = {}) {
  const form = copyForm || {factory: defaults.factory || (last.factories || [])[0] || "", name: defaults.name || "", sections: defaults.sections || SECTIONS.map(([key]) => key)};
  return `<section class="bf-card bf-copy"><h4>MAKE AN EDITABLE COPY OF ONE OF THE GAME'S PRESETS</h4><p class="bf-dim">The game's own presets can't be changed. A copy under your own name can, and keeps every binding the preset has. The sections you tick switch to it (APPLY writes both).</p><div class="bf-copy-form"><label class="bf-field">START FROM<select data-bf="copy-factory">${(last.factories || []).map((name) => `<option${name === form.factory ? " selected" : ""}>${esc(name)}</option>`).join("")}</select></label><label class="bf-field">NAME<input data-bf="copy-name" maxlength="40" placeholder="My ${esc(form.factory || "controls")}" value="${esc(form.name)}"></label><span class="bf-copy-sections">${SECTIONS.map(([key, label]) => `<label class="bf-check"><input type="checkbox" data-bf="copy-section" value="${key}"${form.sections.includes(key) ? " checked" : ""}> ${label}</label>`).join("")}</span><button type="button" class="primary" data-bf="copy"${(last.factories || []).length ? "" : " disabled"}>MAKE THE COPY</button></div>${(last.factories || []).length ? "" : `<p class="bf-dim warn">The game's install wasn't found, so its presets can't be read. Set Elite's game folder on SHORTCUTS › Elite's bindings.</p>`}</section>`;
}

// -- CREW KEYS ----------------------------------------------------------------------
function crewBody() {
  const rows = last.crew || [];
  const counts = rows.reduce((acc, row) => { acc[row.state] = (acc[row.state] || 0) + 1; return acc; }, {});
  const missing = rows.filter((row) => row.state === "missing" || row.state === "device");
  const factory = [...new Set(missing.filter((row) => row.kind === "factory").map((row) => row.preset))];
  const report = last.notice?.report || {};
  const assigned = Array.isArray(report.assigned) ? report.assigned : [];
  const skipped = Array.isArray(report.skipped) ? report.skipped : [];
  const tiles = [["ready", "READY"], ["device", "PAD/STICK ONLY"], ["missing", "NO KEY"], ["odd", "CAN'T PRESS"]]
    .map(([key, label]) => `<div class="bf-tile ${key}"><span>${label}</span><b>${whole(counts[key] || 0)}</b></div>`).join("");
  const factoryNote = factory.length ? `<p class="bf-info warn">${factory.map(esc).join(", ")} ${factory.length === 1 ? "is" : "are"} the game's own preset, which can't be changed: make an editable copy (below) and its controls get keys too. <button type="button" data-bf="copy-open" data-factory="${esc(factory[0])}" data-crew="1">MAKE A COPY OF ${esc(factory[0].toUpperCase())}</button></p>` : "";
  const reportHtml = assigned.length || skipped.length ? `<section class="bf-card"><h4>LAST ASSIGN</h4>${assigned.length ? `<ul class="bf-list">${assigned.map((row) => `<li><span>${esc(row.label)}</span><b>${esc(row.chord)}</b><small>${esc(row.file)}</small></li>`).join("")}</ul>` : ""}${skipped.length ? `<p class="bf-dim">Left alone:</p><ul class="bf-list">${skipped.map((row) => `<li><span>${esc(row.label)}</span><small>${esc(row.why)}</small></li>`).join("")}</ul>` : ""}</section>` : "";
  const table = rows.length ? `<div class="bf-crew">${rows.map((row) => `<div class="bf-crew-row ${row.state}"><span class="bf-name"><b>${esc(row.name)}</b><small>${esc(SECTION_LABEL[row.section] || "")} · ${esc(row.preset || "no preset")}${row.kind === "factory" ? " (built in)" : ""}</small></span><span class="bf-crew-key">${row.key ? `<b>${esc(row.key)}</b>` : row.device ? `<small>${esc(row.device)}</small>` : "—"}</span><em>${CREW_STATES[row.state] || row.state}</em><small class="bf-says">“${(row.says || []).map(esc).join("”, “")}”</small></div>`).join("")}</div>` : `<p class="bf-empty">The crew's ship commands are switched off, so no keys are needed.</p>`;
  return `<section class="bf-card"><h4>THE KEYS YOUR CREW PRESSES</h4><p class="bf-dim">Your crew works the ship with Elite's own keyboard keys (it can't press pad or stick buttons). ASSIGN MISSING KEYS gives each control with none a free, safe key: only empty slots are filled, nothing you bound is touched, and you check them before APPLY.</p><div class="bf-tiles">${tiles}</div><div class="bf-actions"><button type="button" class="primary" data-bf="crew_assign"${missing.length ? "" : " disabled"}>ASSIGN MISSING KEYS</button><button type="button" class="ghost" data-page="settings" data-settings-section="voice">VOICE COMMANDS</button></div>${factoryNote}</section>${reportHtml}${table}${factory.length ? copyCard({factory: factory[0], sections: (last.sections || []).filter((row) => row.preset === factory[0]).map((row) => row.section)}) : ""}`;
}

// -- BACKUPS ------------------------------------------------------------------------
function when(seconds) {
  const date = new Date(n(seconds) * 1000);
  return date.toLocaleString("en-GB", {day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit"});
}

function backupsBody() {
  const rows = last.backups || [];
  const retention = last.retention || {};
  const list = rows.length ? `<div class="bf-backups">${rows.map((row) => `<div class="bf-backup ${esc(row.kind)}"><span><b>${esc(when(row.created))}</b><small>${esc(row.label)}${row.note ? ` · ${esc(row.note)}` : ""}</small></span><span class="bf-dim">${whole(row.files)} file${row.files === 1 ? "" : "s"} · ${whole(row.size / 1024)} KB</span><span class="bf-actions">${row.working ? "" : `<button type="button" data-bf="restore-ask" data-id="${esc(row.id)}">RESTORE</button>`}${row.kind === "user" ? `<button type="button" class="ghost danger" data-bf="delete-backup" data-id="${esc(row.id)}">DELETE</button>` : ""}</span></div>`).join("")}</div>` : `<p class="bf-empty">No backups yet. The first start each day makes one by itself.</p>`;
  const installs = (last.installs || []).map((row) => `<li><b>${esc(row.label)}</b><small>${esc(row.path)}</small><em class="${row.reachable ? "" : "bad"}">${row.reachable ? "FOUND" : "MISSING"}</em></li>`).join("");
  return `<section class="bf-card"><h4>BACKUPS</h4><p class="bf-dim">Every backup is a zip of all your control files: the bindings folder and each install's device files. One is made the first time Void Compass starts each day, before every write, and when you ask. Restoring backs up what's there first.</p><div class="bf-actions"><button type="button" class="primary" data-bf="backup_now"${last.folder_found ? "" : " disabled"}>BACK UP NOW</button><button type="button" class="ghost" data-bf="open" data-which="backups">OPEN THE FOLDER</button><label class="bf-field">KEEP DAILY ONES FOR<select data-bf="retention-days">${(retention.choices || [30, 60, 90, 180]).map((days) => `<option value="${days}"${days === retention.daily_days ? " selected" : ""}>${days} days</option>`).join("")}</select></label><label class="bf-field">KEEP THE LAST<select data-bf="retention-keep">${[10, 25, 50, 100, 250, 500, 1000].map((count) => `<option value="${count}"${count === retention.before_keep ? " selected" : ""}>${count} before-change ones</option>`).join("")}</select></label></div><p class="bf-dim">Yours (BACK UP NOW) and the first-setup one are kept until you delete them.</p></section>${list}<section class="bf-card"><h4>WHERE THE FILES ARE</h4><ul class="bf-list"><li><b>Bindings folder</b><small>${esc(last.folder || "not found")}</small><button type="button" class="ghost" data-bf="open" data-which="bindings"${last.folder_found ? "" : " disabled"}>OPEN</button></li>${installs || `<li><b>No game install found</b><small>Set Elite's game folder on SHORTCUTS › Elite's bindings.</small></li>`}</ul></section>`;
}

// -- DEVICES' button tester ------------------------------------------------------------
function testPanel(row) {
  const keys = testing.pad
    ? PAD_KEYS.map((key) => `<span class="bf-key" data-live="p-${key}">${esc(key)}</span>`).join("")
    : Array.from({length: Math.min(Math.max(testing.buttons, 0), 32)}, (_v, i) => i + 1)
      .map((n) => `<span class="bf-key" data-live="b-${n}" title="Joy_${n}">${esc(testing.labels[`Joy_${n}`] || `Button ${n}`)}</span>`).join("");
  const hat = testing.pad || !testing.hats ? "" : `<div class="bf-hat">${["Up", "Left", "Right", "Down"].map((dir) => `<span class="bf-key" data-live="h-${dir}">${{Up: "↑", Down: "↓", Left: "←", Right: "→"}[dir]}</span>`).join("")}</div>`;
  return `<div class="bf-tester" data-test-panel><p class="bf-dim">Press anything on ${esc(row.name || row.reported)}: it lights up here.${testing.pad ? "" : " Windows reports up to 32 buttons and one hat per controller."}</p><div class="bf-keys">${keys || "<span class='bf-dim'>It reports no buttons.</span>"}</div>${hat}<div class="bf-axes" data-live-axes></div></div>`;
}

function startTest(d) {
  testing = {ident: d.ident, pad: d.pad === "1", buttons: Number(d.buttons) || 32, hats: Number(d.hats) || 0, labels: {}};
  live = null;
  if (d.name && !testing.pad) {
    fetch(ui.apiUrl(`/api/data/helm-device?name=${encodeURIComponent(d.name)}`), {cache: "no-store"}).then((r) => r.json()).then((data) => {
      if (testing?.ident !== d.ident || !data.inputs) return;
      testing.labels = Object.fromEntries(data.inputs.map((input) => [input.token, input.label || input.default]));
      draw(true);
      applyLive();
    }).catch(() => {});
  }
  draw(true);
  pollLive();
}

function stopTest() {
  testing = null;
  live = null;
  window.clearTimeout(liveTimer);
  liveTimer = 0;
}

async function pollLive() {
  window.clearTimeout(liveTimer);
  liveTimer = 0;
  const root = ui?.byId("helm-workspace");
  if (!testing || tab !== "devices" || !root?.isConnected) return;
  if (root.offsetParent !== null && !document.hidden) {
    try {
      const response = await fetch(ui.apiUrl("/api/data/helm-live"), {cache: "no-store"});
      if (response.ok) live = await response.json();
    } catch {
      /* next time */
    }
    applyLive();
  }
  if (testing) liveTimer = window.setTimeout(pollLive, 80);
}

function applyLive() {
  const panel = ui?.byId("helm-workspace")?.querySelector("[data-test-panel]");
  if (!panel || !testing) return;
  let down = new Set(), axes = {};
  if (testing.pad) {
    const slot = Number(String(testing.ident).replace(/\D/g, "")) - 1;
    const pad = (live?.pads || []).find((row) => row.slot === slot);
    down = new Set((pad?.down || []).map((key) => `p-${key}`));
    axes = pad?.axes || {};
  } else {
    const stick = (live?.joysticks || []).find((row) => row.ident === testing.ident);
    down = new Set([...(stick?.down || []).map((n) => `b-${n}`), ...(stick?.hats || []).map((dir) => `h-${dir}`)]);
    axes = stick?.axes || {};
  }
  panel.querySelectorAll("[data-live]").forEach((key) => key.classList.toggle("on", down.has(key.dataset.live)));
  const bars = panel.querySelector("[data-live-axes]");
  if (bars) {
    const triggers = new Set(["LT", "RT"]);
    bars.innerHTML = Object.entries(axes).map(([name, value]) => {
      const v = Number(value) || 0;
      const left = triggers.has(name) ? 0 : Math.min(50, 50 + v * 50);
      const width = triggers.has(name) ? v * 100 : Math.abs(v) * 50;
      return `<span class="bf-axis"><b>${esc(name)}</b><i><em style="left:${left}%;width:${width}%"></em></i><small>${v.toFixed(2)}</small></span>`;
    }).join("");
  }
}

// -- dialogs ------------------------------------------------------------------------
function rowOf(tag) {
  return (file?.rows || []).find((row) => row.tag === tag);
}

function openSlot(tag, position) {
  const row = rowOf(tag);
  if (!row || !file?.editable) return;
  const slot = (row.slots || [])[position === "Secondary" ? 1 : 0] || {};
  dialog = {kind: "slot", tag, position, source: slot.device === "Keyboard" || !slot.assigned ? "keyboard" : slot.device === "Mouse" ? "mouse" : "controller",
    device: slot.assigned ? slot.device : "", key: slot.assigned ? slot.key : "", modifiers: slot.assigned ? slot.modifiers || [] : [],
    hold: Boolean(slot.hold), capturing: false, held: [], token: "", focus: true};
  holder = null;
  drawDialog();
  checkHolder();
}

function openAxis(tag) {
  const row = rowOf(tag);
  if (!row || !file?.editable) return;
  const axis = row.axis || {};
  dialog = {kind: "axis", tag, device: axis.bound ? axis.device : "", key: axis.bound ? axis.key : "", inverted: Boolean(axis.inverted), deadzone: n(axis.deadzone)};
  drawDialog();
}

function closeDialog() {
  if (dialog?.kind === "slot" && dialog.token) op("capture_cancel");
  dialog = null;
  holder = null;
  drawDialog();
}

function drawDialog() {
  const host = ui ? dialogHost() : null;
  if (!host) return;
  if (!dialog) {
    if (host.innerHTML) host.innerHTML = "";
    return;
  }
  // A controller press arrives with the page's next refresh.
  const capture = last.capture || {};
  if (dialog.kind === "slot" && dialog.token && capture.token === dialog.token && capture.status !== "listening" && !dialog.captured) {
    dialog.captured = true;
    if (capture.status === "done") {
      Object.assign(dialog, {device: capture.device, key: capture.key, modifiers: capture.modifiers || []});
      checkHolder();
    }
  }
  const markup = dialog.kind === "slot" ? slotDialog(capture) : dialog.kind === "axis" ? axisDialog()
    : dialog.kind === "name" ? nameDialog() : dialog.kind === "device" ? deviceDialog()
      : dialog.kind === "merge" ? mergeDialog() : confirmDialog();
  if (host.dataset.markup === markup) return;
  // Typing in it: the refresh waits (what's typed is kept in the dialog's state).
  const typing = document.activeElement;
  if (host.dataset.markup && host.contains(typing) && typing.matches("input:not([type=radio]):not([type=checkbox]):not([type=range]), select")) return;
  const focusedCapture = document.activeElement?.matches?.("[data-bf-capture]");
  host.dataset.markup = markup;
  host.innerHTML = markup;
  // Ready to take a key as it opens (or switches to KEYBOARD), and while it's taking one.
  if (focusedCapture || (dialog.focus && dialog.source === "keyboard")) host.querySelector("[data-bf-capture]")?.focus();
  dialog.focus = false;
}

function slotDialog(capture) {
  const row = rowOf(dialog.tag) || {};
  const sources = [["keyboard", "KEYBOARD"], ["mouse", "MOUSE"], ["controller", "CONTROLLER"]];
  const listening = dialog.token && capture.token === dialog.token && capture.status === "listening";
  let pick = "";
  if (dialog.source === "keyboard") {
    const keys = (file.inputs?.keys || []).map((key) => `<option value="${esc(key)}"${dialog.device === "Keyboard" && dialog.key === key ? " selected" : ""}>${esc(keyName(key))}</option>`).join("");
    pick = `<div class="bf-capture${dialog.capturing ? " live" : ""}" tabindex="0" data-bf-capture>${dialog.held.length ? esc(dialog.held.map(keyName).join(" + ")) + " + …" : "Click here, then press the key (hold Ctrl, Shift or Alt with it for a combination)"}</div><label class="bf-field">OR PICK A KEY<select data-bf="pick-key"><option value="">…</option>${keys}</select></label>`;
  } else if (dialog.source === "mouse") {
    pick = `<div class="bf-picks">${(file.inputs?.mouse || []).map(([token, label]) => `<button type="button" class="bf-pick${dialog.device === "Mouse" && dialog.key === token ? " on" : ""}" data-bf="pick-mouse" data-key="${esc(token)}">${esc(label)}</button>`).join("")}</div><p class="bf-dim">Mouse buttons are picked, not pressed: a click here would only click the page.</p>`;
  } else {
    pick = `<div class="bf-actions"><button type="button" class="primary" data-bf="listen">${listening ? "PRESS A BUTTON OR HAT…" : "LISTEN"}</button>${listening ? `<button type="button" class="ghost" data-bf="listen-cancel">STOP</button>` : ""}</div><p class="bf-dim">${capture.token === dialog.token && capture.status === "none" ? "Nothing was pressed. LISTEN and try again." : "LISTEN, then press a pad, stick or HOTAS button, or a hat. Hold one button and press another for a combination."}</p><div class="bf-picks">${(file.inputs?.pad || []).map(([name, token]) => `<button type="button" class="bf-pick${dialog.device === "GamePad" && dialog.key === token ? " on" : ""}" data-bf="pick-pad" data-key="${esc(token)}">Pad ${esc(name)}</button>`).join("")}</div>`;
  }
  const chosen = dialog.key ? chordName(dialog.device, dialog.key, dialog.modifiers) : "";
  const blocked = holder && holder.key === candidateKey() && (holder.holder || holder.reserved);
  const warning = !blocked ? "" : holder.reserved ? `<p class="bf-warn">That ${esc(holder.reserved)}.</p>` : `<p class="bf-warn">${esc(holder.holder_label)} already uses that, live at the same time. Free it there first, or pick another.</p>`;
  return `<div class="bf-dialog" role="dialog" aria-modal="true" aria-label="Change a binding"><div class="bf-dialog-box"><header><small>${esc(SECTION_LABEL[row.section] || "")}${row.group ? ` › ${esc(row.group)}` : ""} · ${dialog.position.toUpperCase()}</small><h3>${esc(row.name || dialog.tag)}</h3></header><div class="bf-chips" role="tablist">${sources.map(([key, label]) => `<button type="button" class="bf-chip${dialog.source === key ? " on" : ""}" data-bf="source" data-source="${key}">${label}</button>`).join("")}</div>${pick}<div class="bf-chosen"><span>NEW</span><b>${esc(chosen || "nothing yet")}</b>${dialog.modifiers.length ? `<button type="button" class="ghost" data-bf="drop-mods">NO MODIFIERS</button>` : ""}</div><label class="bf-check"><input type="checkbox" data-bf="hold"${dialog.hold ? " checked" : ""}> Press and hold (fires on a long press, not a tap)</label>${warning}<footer><button type="button" class="ghost" data-bf="dialog-close">CANCEL</button><button type="button" class="ghost danger" data-bf="slot-clear">CLEAR THIS SLOT</button><button type="button" class="primary" data-bf="slot-save"${dialog.key && !blocked ? "" : " disabled"}>SET</button></footer></div></div>`;
}

function axisDialog() {
  const row = rowOf(dialog.tag) || {};
  const devices = Object.entries(file.devices || {}).filter(([name]) => !["Keyboard", "Mouse", "GamePad"].includes(name));
  const axes = file.inputs?.axes || [];
  const pad = dialog.device === "GamePad";
  const current = dialog.key ? inputName(dialog.device, dialog.key) : "nothing";
  return `<div class="bf-dialog" role="dialog" aria-modal="true" aria-label="Change an axis"><div class="bf-dialog-box"><header><small>${esc(SECTION_LABEL[row.section] || "")}${row.group ? ` › ${esc(row.group)}` : ""} · AXIS</small><h3>${esc(row.name || dialog.tag)}</h3></header><p class="bf-dim">Now: <b>${esc(current)}</b>${pad ? " (a pad stick: invert and dead zone can change)" : ""}</p>${pad ? "" : `<div class="bf-copy-form"><label class="bf-field">CONTROLLER<select data-bf="axis-device"><option value="">None (unbound)</option>${devices.map(([name, label]) => `<option value="${esc(name)}"${name === dialog.device ? " selected" : ""}>${esc(label === name ? name : `${label} (${name})`)}</option>`).join("")}${dialog.device && !devices.some(([name]) => name === dialog.device) ? `<option value="${esc(dialog.device)}" selected>${esc(dialog.device)}</option>` : ""}</select></label><label class="bf-field">AXIS<select data-bf="axis-key">${axes.map((axis) => `<option value="Joy_${axis}"${dialog.key === `Joy_${axis}` ? " selected" : ""}>${axis.replace(/Axis$/, "")}</option>`).join("")}</select></label></div>`}<label class="bf-check"><input type="checkbox" data-bf="axis-inverted"${dialog.inverted ? " checked" : ""}> Inverted</label><label class="bf-field bf-range">DEAD ZONE <b>${n(dialog.deadzone).toFixed(2)}</b><input type="range" min="0" max="1" step="0.01" value="${n(dialog.deadzone)}" data-bf="axis-deadzone"></label><footer><button type="button" class="ghost" data-bf="dialog-close">CANCEL</button><button type="button" class="ghost danger" data-bf="axis-clear"${pad ? " disabled" : ""}>UNBIND</button><button type="button" class="primary" data-bf="axis-save">SET</button></footer></div></div>`;
}

function nameDialog() {
  const rows = (last.devices?.rows || []).filter((row) => row.connected && !row.name && (!dialog.ident || row.ident === dialog.ident));
  if (!rows.length) return `<div class="bf-dialog" role="dialog" aria-modal="true"><div class="bf-dialog-box"><header><small>NAME</small><h3>Every connected controller has a name</h3></header><footer><button type="button" class="ghost" data-bf="dialog-close">CLOSE</button></footer></div></div>`;
  const fields = rows.map((row) => `<div class="bf-name-row"><span class="bf-name"><b>${esc(row.reported)}</b><small>${esc(row.ident)} · ${whole(row.buttons)} buttons${row.hats ? `, ${whole(row.hats)} hat` : ""}${row.axes ? `, ${whole(row.axes)} axes` : ""}${row.by_id ? ` · ${whole(row.by_id)} binding${row.by_id === 1 ? "" : "s"} move to the name` : ""}</small></span><input data-bf="name-field" data-ident="${esc(row.ident)}" maxlength="50" value="${esc(dialog.names?.[row.ident] ?? row.suggest)}"></div>`).join("");
  return `<div class="bf-dialog" role="dialog" aria-modal="true" aria-label="Name your controllers"><div class="bf-dialog-box"><header><small>DEVICES</small><h3>${rows.length === 1 ? "A controller needs a name" : `${rows.length} controllers need a name`}</h3></header><p class="bf-dim">The name goes in each install's DeviceMappings.xml (at the top, so it's the one the game uses), with a labels file: Button 1, Button 2… (rename them later in its editor). Letters, digits, - and _; 3 to 50, starting with a letter. Nothing is written until APPLY.</p>${fields}<footer><button type="button" class="ghost" data-bf="dialog-close">CANCEL</button><button type="button" class="primary" data-bf="name-save">NAME ${rows.length === 1 ? "IT" : "THEM"}</button></footer></div></div>`;
}

function deviceDialog() {
  const device = dialog.data;
  if (!device) return `<div class="bf-dialog" role="dialog" aria-modal="true"><div class="bf-dialog-box"><p class="bf-empty">Reading ${esc(dialog.name)}…</p></div></div>`;
  if (device.error) return `<div class="bf-dialog" role="dialog" aria-modal="true"><div class="bf-dialog-box"><p class="bf-empty">${esc(device.error)}</p><footer><button type="button" class="ghost" data-bf="dialog-close">CLOSE</button></footer></div></div>`;
  const groups = [["BUTTONS", (t) => /^Joy_\d+$/.test(t)], ["HATS", (t) => /^Joy_POV/.test(t)], ["AXES", (t) => /Axis$/.test(t)], ["OTHER", () => true]];
  const used = new Set();
  const grids = groups.map(([title, test]) => {
    const inputs = device.inputs.filter((row) => !used.has(row.token) && test(row.token));
    inputs.forEach((row) => used.add(row.token));
    return inputs.length ? `<h4>${title}</h4><div class="bf-labels">${inputs.map((row) => `<label class="bf-field">${esc(row.token.replace(/^Joy_/, ""))}<input data-bf="label" data-token="${esc(row.token)}" maxlength="40" placeholder="${esc(row.default)}" value="${esc(dialog.labels?.[row.token] ?? row.label)}"></label>`).join("")}</div>` : "";
  }).join("");
  const retarget = !device.builtin && !device.connected && device.candidates.length
    ? `<label class="bf-field">IT'S THIS CONTROLLER NOW<select data-bf="retarget-pick"><option value="">…</option>${device.candidates.map((row) => `<option value="${esc(row.ident)}">${esc(row.reported)} (${esc(row.ident)})</option>`).join("")}</select></label><p class="bf-dim">A firmware update or a new USB port can change a controller's ids. Pick it here and its ${whole(device.refs)} binding${device.refs === 1 ? "" : "s"} keep working.</p>` : "";
  return `<div class="bf-dialog" role="dialog" aria-modal="true" aria-label="Edit a controller"><div class="bf-dialog-box bf-wide"><header><small>DEVICE · ${esc(device.ids.slice(0, 2).join(", "))}${device.ids.length > 2 ? " …" : ""} · ${device.connected ? `CONNECTED (${esc(device.reported)})` : "NOT CONNECTED"}</small><h3>${esc(device.name)}</h3></header>${device.builtin ? `<p class="bf-dim">One of the game's own names: its button labels can change here, its name can't.</p>` : `<label class="bf-field">NAME<input data-bf="device-rename" maxlength="50" value="${esc(dialog.rename ?? device.name)}"></label><p class="bf-dim">Renaming moves its ${whole(device.refs)} binding${device.refs === 1 ? "" : "s"} and its labels with it.</p>`}${retarget}${grids}<footer><button type="button" class="ghost" data-bf="dialog-close">CANCEL</button>${device.builtin ? "" : `<button type="button" class="ghost danger" data-bf="device-clear" data-confirm="Take ${esc(device.name)}'s name away? Its bindings go back to its USB ids.">REMOVE NAME</button>`}<button type="button" class="ghost" data-bf="device-reset">RESET LABELS</button><button type="button" class="primary" data-bf="device-save">SAVE</button></footer></div></div>`;
}

function mergeDialog() {
  const rows = dialog.rows;
  if (!rows) return `<div class="bf-dialog" role="dialog" aria-modal="true"><div class="bf-dialog-box"><p class="bf-empty">Comparing…</p></div></div>`;
  const list = rows.length ? rows.map((row) => `<div class="bf-merge-row"><span class="bf-name"><b>${esc(row.label)}</b></span>${["mine", "game"].map((side) => `<label class="bf-check bf-merge-side${(dialog.picks[row.key] || "mine") === side ? " on" : ""}"><input type="radio" name="mg-${esc(row.key)}" data-bf="merge-pick" data-key="${esc(row.key)}" value="${side}"${(dialog.picks[row.key] || "mine") === side ? " checked" : ""}> <small>${side === "mine" ? "YOURS" : dialog.install ? esc(dialog.install.toUpperCase()) : "THE GAME'S"}</small> ${esc(row[side])}</label>`).join("")}</div>`).join("") : `<p class="bf-empty">Nothing differs any more.</p>`;
  return `<div class="bf-dialog" role="dialog" aria-modal="true" aria-label="Merge"><div class="bf-dialog-box bf-wide"><header><small>MERGE · ${rows.length} DIFFERENCE${rows.length === 1 ? "" : "S"}</small><h3>${esc(dialog.title)}</h3></header><p class="bf-dim">Pick each line's side. The result goes to both Helm's working copy and the game's files (both are backed up first).</p><div class="bf-actions"><button type="button" class="ghost" data-bf="merge-all" data-side="mine">ALL YOURS</button><button type="button" class="ghost" data-bf="merge-all" data-side="game">ALL ${dialog.install ? esc(dialog.install.toUpperCase()) + "'S" : "THE GAME'S"}</button></div><div class="bf-merge">${list}</div><footer><button type="button" class="ghost" data-bf="dialog-close">CANCEL</button><button type="button" class="primary" data-bf="merge-save"${rows.length ? "" : " disabled"}>MERGE</button></footer></div></div>`;
}

function openMerge(fileName_, install) {
  dialog = {kind: "merge", file: fileName_, install, title: install ? `${install}'s device files` : fileName_, rows: null, picks: {}};
  drawDialog();
  if (install) {
    const row = (last.check?.installs || []).find((item) => item.install === install);
    dialog.rows = (row?.items || []).map((item) => ({key: item.item, label: item.kind === "labels" ? `${item.name} (button labels)` : item.name,
      mine: item.values.mine, game: item.values.game}));
    drawDialog();
    return;
  }
  fetch(ui.apiUrl(`/api/data/helm-diff?name=${encodeURIComponent(fileName_)}`), {cache: "no-store"}).then((r) => r.json()).then((data) => {
    if (dialog?.kind !== "merge") return;
    dialog.rows = (data.rows || []).map((row) => ({key: row.tag, label: row.label, mine: row.mine, game: row.game}));
    drawDialog();
  }).catch(() => {});
}

function openDevice(name) {
  dialog = {kind: "device", name, data: null, labels: {}, rename: undefined};
  drawDialog();
  fetch(ui.apiUrl(`/api/data/helm-device?name=${encodeURIComponent(name)}`), {cache: "no-store"}).then((r) => r.json()).then((data) => {
    if (dialog?.kind !== "device") return;
    dialog.data = data;
    drawDialog();
  }).catch(() => {});
}

// The controllers with no name, offered by themselves once (and again when another is plugged in).
function offerNaming() {
  const idents = (last.devices?.rows || []).filter((row) => row.connected && !row.name).map((row) => row.ident).sort().join(",");
  if (!idents || dialog || !last.set_up || (last.check?.reconcile || []).length) {
    if (!idents) offered = "";
    return;
  }
  if (idents === offered || idents.split(",").every((ident) => offered.split(",").includes(ident))) return;
  offered = idents;
  dialog = {kind: "name", names: {}};
}

function confirmDialog() {
  const running = last.game_running ? `<p class="bf-warn">Elite is running. Close its Options › Controls screen first; the game reads its controls again when that screen opens.</p>` : "";
  if (dialog.kind === "apply") {
    return `<div class="bf-dialog" role="dialog" aria-modal="true" aria-label="Apply"><div class="bf-dialog-box"><header><small>APPLY</small><h3>Write your edits to the game's files?</h3></header><p>${(last.pending || []).map(esc).join(" · ")}</p><p class="bf-dim">Everything is backed up first. ${esc(last.close_controls || "")}</p>${running}<footer><button type="button" class="ghost" data-bf="dialog-close">CANCEL</button><button type="button" class="primary" data-bf="apply">APPLY</button></footer></div></div>`;
  }
  if (dialog.kind === "restore") {
    const row = (last.backups || []).find((item) => item.id === dialog.id) || {};
    return `<div class="bf-dialog" role="dialog" aria-modal="true" aria-label="Restore"><div class="bf-dialog-box"><header><small>RESTORE</small><h3>Put back the backup of ${esc(when(row.created))}?</h3></header><p class="bf-dim">The whole backup goes back: your binds and preset files, and each install's device files it holds. What's there now is backed up first, and it becomes Helm's working copy.${(last.pending || []).length ? " Your edits on screen are discarded." : ""}</p>${running}<footer><button type="button" class="ghost" data-bf="dialog-close">CANCEL</button><button type="button" class="primary" data-bf="restore" data-id="${esc(dialog.id)}">RESTORE</button></footer></div></div>`;
  }
  return "";
}

// -- the dialog's candidate ---------------------------------------------------------
function candidateKey() {
  return dialog ? `${dialog.device}|${dialog.key}|${dialog.modifiers.map((m) => m.join(":")).join(",")}|${dialog.hold}` : "";
}

function checkHolder() {
  if (!dialog || dialog.kind !== "slot" || !dialog.key || !ui) return;
  const key = candidateKey();
  const mods = dialog.modifiers.map(([d, k]) => `${d}|${k}`).join(",");
  const url = `/api/data/helm-holder?file=${encodeURIComponent(fileName)}&action=${encodeURIComponent(dialog.tag)}&device=${encodeURIComponent(dialog.device)}&key=${encodeURIComponent(dialog.key)}&mods=${encodeURIComponent(mods)}&hold=${dialog.hold ? 1 : 0}`;
  fetch(ui.apiUrl(url), {cache: "no-store"}).then((response) => response.json()).then((answer) => {
    if (candidateKey() !== key) return;
    holder = {...answer, key};
    drawDialog();
  }).catch(() => {});
}

// -- events -------------------------------------------------------------------------
function confirmed(control) {
  return !control.dataset.confirm || window.confirm(control.dataset.confirm);
}

async function onClick(event) {
  if (event.target.classList?.contains("bf-dialog")) { closeDialog(); return; }
  const control = event.target.closest("[data-bf]");
  if (!control || control.disabled || control.tagName === "SELECT" || control.tagName === "INPUT") return;
  const d = control.dataset;
  switch (d.bf) {
    case "tab": tab = d.tab; if (tab !== "devices") stopTest(); draw(true); return;
    case "section": section = d.section; draw(true); return;
    case "slot": openSlot(d.tag, d.position); return;
    case "axis": openAxis(d.tag); return;
    case "dialog-close": closeDialog(); return;
    case "source": Object.assign(dialog, {source: d.source, capturing: false, held: [], focus: true}); drawDialog(); return;
    case "pick-mouse": Object.assign(dialog, {device: "Mouse", key: d.key, modifiers: []}); drawDialog(); checkHolder(); return;
    case "pick-pad": Object.assign(dialog, {device: "GamePad", key: d.key, modifiers: []}); drawDialog(); checkHolder(); return;
    case "drop-mods": dialog.modifiers = []; drawDialog(); checkHolder(); return;
    case "listen":
      dialog.token = `bf${Date.now()}`;
      dialog.captured = false;
      await op("capture", {token: dialog.token});
      return;
    case "listen-cancel": await op("capture_cancel"); dialog.token = ""; drawDialog(); return;
    case "slot-save": {
      const done = await op("assign", {file: fileName, tag: dialog.tag, position: dialog.position, device: dialog.device, key: dialog.key, modifiers: dialog.modifiers, hold: dialog.hold});
      if (done) closeDialog();
      return;
    }
    case "slot-clear": if (await op("clear", {file: fileName, tag: dialog.tag, position: dialog.position})) closeDialog(); return;
    case "axis-save": if (await op("axis", {file: fileName, tag: dialog.tag, device: dialog.device, key: dialog.key, inverted: dialog.inverted, deadzone: dialog.deadzone})) closeDialog(); return;
    case "axis-clear": if (await op("axis", {file: fileName, tag: dialog.tag, device: "", key: "", inverted: dialog.inverted, deadzone: dialog.deadzone})) closeDialog(); return;
    case "apply-ask": dialog = {kind: "apply"}; drawDialog(); return;
    case "toggle": await op("setting", {file: fileName, tag: d.tag, value: d.value}); return;
    case "throttle": await op("throttle", {file: fileName, axis: d.axis, forward: d.forward === "1"}); return;
    case "name-open": dialog = {kind: "name", ident: d.ident || "", names: {}}; drawDialog(); return;
    case "test": if (testing?.ident === d.ident) { stopTest(); draw(true); } else startTest(d); return;
    case "name-save": {
      const devices = [...control.closest(".bf-dialog-box").querySelectorAll("[data-bf='name-field']")].map((input) => ({ident: input.dataset.ident, name: input.value.trim()}));
      if (await op("name_devices", {devices})) closeDialog();
      return;
    }
    case "device-open": openDevice(d.name); return;
    case "device-save": {
      const box = control.closest(".bf-dialog-box");
      const labels = Object.fromEntries([...box.querySelectorAll("[data-bf='label']")].map((input) => [input.dataset.token, input.value.trim()]));
      const rename = box.querySelector("[data-bf='device-rename']")?.value.trim();
      const target = box.querySelector("[data-bf='retarget-pick']")?.value;
      let name = dialog.data.name;
      let done = await op("device_labels", {name, labels});
      if (done && target) done = await op("retarget_device", {name, ident: target});
      if (done && rename && rename !== name) done = await op("rename_device", {name, new: rename});
      if (done) closeDialog();
      return;
    }
    case "device-reset": if (await op("reset_labels", {name: dialog.data.name})) openDevice(dialog.data.name); return;
    case "device-clear": if (confirmed(control) && await op("clear_device", {name: dialog.data.name})) closeDialog(); return;
    case "merge-open": openMerge(d.file, ""); return;
    case "merge-install-open": openMerge("", d.install); return;
    case "merge-all": for (const row of dialog.rows || []) dialog.picks[row.key] = d.side; drawDialog(); return;
    case "merge-save": {
      const picks = Object.fromEntries(Object.entries(dialog.picks).filter(([, side]) => side === "game"));
      const done = dialog.install ? await op("merge_install", {install: dialog.install, picks}) : await op("merge_file", {file: dialog.file, picks});
      if (done) closeDialog();
      return;
    }
    case "reconcile": {
      const items = last.check?.reconcile || [];
      const first = Object.keys(items[0]?.values || {})[0];
      const picks = Object.fromEntries(items.map((item) => [item.item, reconcilePicks[item.item] || first]));
      if (await op("adopt_devices", {picks, base: first})) reconcilePicks = {};
      return;
    }
    case "reconcile-all": if (await op("adopt_devices", {base: d.install, picks: Object.fromEntries((last.check?.reconcile || []).map((item) => [item.item, d.install]))})) reconcilePicks = {}; return;
    case "apply": closeDialog(); await op("apply"); return;
    case "restore-ask": dialog = {kind: "restore", id: d.id}; drawDialog(); return;
    case "restore": closeDialog(); await op("restore", {id: d.id}); return;
    case "delete-backup": if (window.confirm("Delete this backup of yours?")) await op("delete_backup", {id: d.id}); return;
    case "open": await op("open_folder", {which: d.which}); return;
    case "copy-open":
      copyForm = {factory: d.factory, name: "", sections: (last.sections || []).filter((row) => row.preset === d.factory).map((row) => row.section)};
      if (!copyForm.sections.length) copyForm.sections = SECTIONS.map(([key]) => key);
      if (!d.crew) tab = "presets";
      draw(true);
      ui.byId("helm-workspace")?.querySelector("[data-bf='copy-name']")?.focus();
      return;
    case "copy": {
      const form = control.closest(".bf-copy");
      const factory = form.querySelector("[data-bf='copy-factory']").value;
      const name = form.querySelector("[data-bf='copy-name']").value.trim() || `My ${factory}`;
      const sections = [...form.querySelectorAll("[data-bf='copy-section']:checked")].map((box) => box.value);
      if (await op("copy_factory", {factory, name, sections})) { copyForm = null; fileName = ""; }
      return;
    }
    default:
      if (["setup", "discard", "keep_mine", "take_games", "check", "backup_now", "crew_assign"].includes(d.bf) && confirmed(control)) await op(d.bf, d.install ? {install: d.install} : {});
  }
}

async function onChange(event) {
  const target = event.target;
  const d = target.dataset || {};
  if (d.bf === "file") { fileName = target.value; file = null; fileKey = ""; ensureFile(); draw(true); return; }
  if (d.bf === "crew-only") { crewOnly = target.checked; draw(true); return; }
  if (d.bf === "number" || d.bf === "number-slide") { await op("setting", {file: fileName, tag: d.tag, value: target.value}); return; }
  if (d.bf === "zone") {
    const row = (file?.deadzones || []).find((item) => item.tag === d.tag);
    if (row) await op("axis", {file: fileName, tag: row.tag, device: row.device, key: row.key, inverted: row.inverted, deadzone: Number(target.value)});
    return;
  }
  if (d.bf === "reconcile-pick") { reconcilePicks[d.item] = target.value; return; }
  if (d.bf === "merge-pick" && dialog?.kind === "merge") { dialog.picks[d.key] = target.value; drawDialog(); return; }
  if (d.bf === "retarget-pick" || d.bf === "device-rename" || d.bf === "label" || d.bf === "name-field") return;
  if (d.bf === "preset") {
    const lines = (last.sections || []).map((row) => row.preset);
    const index = SECTIONS.findIndex(([key]) => key === d.section);
    if (index >= 0) { lines[index] = target.value; await op("presets", {lines}); }
    return;
  }
  if (d.bf === "preset-all" && target.value) { await op("presets", {lines: SECTIONS.map(() => target.value)}); return; }
  if (d.bf === "retention-days" || d.bf === "retention-keep") {
    const main = target.closest(".bf-card");
    await op("retention", {daily_days: Number(main.querySelector("[data-bf='retention-days']").value), before_keep: Number(main.querySelector("[data-bf='retention-keep']").value)});
    return;
  }
  if (d.bf === "copy-factory" || d.bf === "copy-section") {
    const form = target.closest(".bf-copy");
    copyForm = {factory: form.querySelector("[data-bf='copy-factory']").value, name: form.querySelector("[data-bf='copy-name']").value,
      sections: [...form.querySelectorAll("[data-bf='copy-section']:checked")].map((box) => box.value)};
    return;
  }
  if (!dialog) return;
  if (d.bf === "hold") { dialog.hold = target.checked; drawDialog(); checkHolder(); return; }
  if (d.bf === "pick-key" && target.value) { Object.assign(dialog, {device: "Keyboard", key: target.value, modifiers: []}); drawDialog(); checkHolder(); return; }
  if (d.bf === "axis-device") { dialog.device = target.value; if (!dialog.key || !/^Joy_/.test(dialog.key)) dialog.key = "Joy_XAxis"; if (!target.value) dialog.key = ""; drawDialog(); return; }
  if (d.bf === "axis-key") { dialog.key = target.value; return; }
  if (d.bf === "axis-inverted") { dialog.inverted = target.checked; return; }
}

function onInput(event) {
  const target = event.target;
  // Typed into a dialog: kept, so a refresh redrawing it doesn't lose it.
  if (dialog?.kind === "device") {
    if (target.dataset?.bf === "label") dialog.labels[target.dataset.token] = target.value;
    if (target.dataset?.bf === "device-rename") dialog.rename = target.value;
  }
  if (dialog?.kind === "name" && target.dataset?.bf === "name-field") dialog.names[target.dataset.ident] = target.value;
  if (target.dataset?.bf === "zone") {
    const label = target.parentElement?.querySelector(".bf-zone");
    if (label) label.textContent = Number(target.value).toFixed(2);
  }
  if (target.matches("[data-bf-search]")) { query = target.value; draw(true); return; }
  if (target.dataset?.bf === "axis-deadzone" && dialog) {
    dialog.deadzone = Number(target.value);
    const label = target.closest(".bf-range")?.querySelector("b");
    if (label) label.textContent = dialog.deadzone.toFixed(2);
  }
  if (target.dataset?.bf === "copy-name") copyForm = {...(copyForm || {}), name: target.value,
    factory: target.closest(".bf-copy")?.querySelector("[data-bf='copy-factory']")?.value || "",
    sections: [...(target.closest(".bf-copy")?.querySelectorAll("[data-bf='copy-section']:checked") || [])].map((box) => box.value)};
}

function codeToKey(code) {
  if (MODIFIER_CODES[code]) return MODIFIER_CODES[code];
  if (/^Key[A-Z]$/.test(code)) return `Key_${code.slice(3)}`;
  if (/^Digit\d$/.test(code)) return `Key_${code.slice(5)}`;
  if (/^F([1-9]|1[0-2])$/.test(code)) return `Key_${code}`;
  if (/^Numpad\d$/.test(code)) return `Key_Numpad_${code.slice(6)}`;
  return NAMED_CODES[code] || "";
}

// Keyboard capture: modifiers held, then the key; let go of a lone modifier and it's the key.
function onKeyDown(event) {
  // Esc closes the dialog, even while taking a key (Escape itself is in the list to pick).
  if (event.key === "Escape" && dialog) { event.preventDefault(); event.stopPropagation(); closeDialog(); return; }
  if (!dialog || dialog.kind !== "slot" || !event.target.matches?.("[data-bf-capture]")) return;
  event.preventDefault();
  event.stopPropagation();
  const key = codeToKey(event.code);
  if (!key) return;
  dialog.capturing = true;
  if (Object.values(MODIFIER_CODES).includes(key)) {
    if (!dialog.held.includes(key)) dialog.held.push(key);
    drawDialog();
    return;
  }
  Object.assign(dialog, {device: "Keyboard", key, modifiers: dialog.held.slice(0, 3).map((mod) => ["Keyboard", mod]), held: [], capturing: false});
  drawDialog();
  checkHolder();
}

function onKeyUp(event) {
  if (!dialog || dialog.kind !== "slot" || !event.target.matches?.("[data-bf-capture]")) return;
  event.preventDefault();
  event.stopPropagation();
  const key = codeToKey(event.code);
  if (dialog.held.length && dialog.held[dialog.held.length - 1] === key) {
    // A modifier pressed and let go on its own: that key, bare.
    const rest = dialog.held.slice(0, -1);
    Object.assign(dialog, {device: "Keyboard", key, modifiers: rest.map((mod) => ["Keyboard", mod]), held: [], capturing: false});
    drawDialog();
    checkHolder();
  }
}
