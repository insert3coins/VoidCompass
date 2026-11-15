// Settings › Appearance: the theme picker and the Theme Workshop (5.8.2).
// The picker groups the themes (skins, palettes, yours). The workshop opens
// under it from a button, or EDIT on one of yours, and the whole deck shows
// the draft as you change it, until you save it or close the workshop.

const GROUPS = [
  ["BACKGROUNDS", [["bg", "Background", "Behind everything"], ["panel", "Panels", "Cards and panels"],
    ["panel_alt", "Panels, alternate", "Every other row, tabs"], ["panel_raised", "Raised panels", "Buttons and raised parts"],
    ["header", "Top bar", "The bar across the top"], ["input", "Text boxes", "Inputs and lists"],
    ["inset", "Wells", "Sunk areas inside panels"], ["selection", "Selection", "Picked rows and highlights"]]],
  ["LINES", [["border", "Borders", "Panel edges"], ["border_soft", "Soft borders", "Dividers inside panels"]]],
  ["TEXT", [["text", "Text", "Most of what you read"], ["muted", "Muted text", "Second-line text"], ["dim", "Dim labels", "Small labels and hints"]]],
  ["ACCENTS", [["accent", "Accent", "Headings and active things"], ["orange", "Highlight", "The second accent"]]],
  ["STATUS", [["green", "Good", "Online, done, safe"], ["yellow", "Caution", "Warnings"], ["red", "Danger", "Alerts and errors"]]],
];
const KEYS = GROUPS.flatMap(([, rows]) => rows.map(([key]) => key));
const HEX = /^#[0-9a-f]{6}$/i;

let open = false;
let justOpened = false;
let draft = null;          // {name, previous, base, skin, palette}
let original = "";         // the draft as it opened, to tell what's changed
let confirm = {what: "", until: 0};
let pending = {name: "", until: 0};   // saved: keep showing it until the deck has it
let last = {};             // the settings data last drawn

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[char]));

function editor(data) {
  return data?.theme_editor || {};
}

// -- colour sums ------------------------------------------------------------------
function rgb(hex) {
  return [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16));
}

function blend(a, b, t) {
  const [x, y] = [rgb(a), rgb(b)];
  return `#${x.map((value, index) => Math.round(value + (y[index] - value) * t).toString(16).padStart(2, "0")).join("")}`;
}

function luminance(hex) {
  const [r, g, b] = rgb(hex).map((value) => {
    const c = value / 255;
    return c <= .03928 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4;
  });
  return .2126 * r + .7152 * g + .0722 * b;
}

function contrast(a, b) {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
  return (x + .05) / (y + .05);
}

// The shades between the background and the text, and the selection tint,
// worked out from those two and the accent (as the built-in themes are).
function blended(palette) {
  const {bg, text, accent} = palette;
  return {...palette, panel: blend(bg, text, .035), panel_alt: blend(bg, text, .065), panel_raised: blend(bg, text, .10),
    header: blend(bg, text, .018), input: blend(bg, text, .028), inset: blend(bg, text, .032),
    border: blend(bg, text, .22), border_soft: blend(bg, text, .13), selection: blend(bg, accent, .20),
    muted: blend(bg, text, .62), dim: blend(bg, text, .42)};
}

const CHECKS = [
  ["Text on panels", "text", "panel", 7, 4.5],
  ["Muted text on panels", "muted", "panel", 4.5, 3],
  ["Dim labels on the background", "dim", "bg", 3, 2.2],
  ["Accent on panels", "accent", "panel", 4.5, 3],
];

function checks(palette) {
  return CHECKS.map(([label, front, back, good, fair]) => {
    const ratio = contrast(palette[front], palette[back]);
    const grade = ratio >= good ? "good" : ratio >= fair ? "fair" : "low";
    return `<li class="tw-check ${grade}"><span>${label}</span><b>${ratio.toFixed(1)} : 1</b><em>${grade === "good" ? "EASY TO READ" : grade === "fair" ? "READABLE" : "HARD TO READ"}</em></li>`;
  }).join("");
}

// -- what the deck wears ------------------------------------------------------------
// The draft while the workshop is open (and the saved theme until the deck has it).
export function workshopTheme(theme = {}) {
  const arrived = draft && theme.name === pending.name && KEYS.every((key) => String(theme.palette?.[key] || "").toLowerCase() === draft.palette[key]);
  const waiting = pending.name && Date.now() < pending.until && !arrived;
  if (!(open || waiting) || !draft) return theme;
  return {...theme, palette: {...(theme.palette || {}), ...draft.palette}, skin: draft.skin || ""};
}

export function themeWorkshopOpen() {
  return open;
}

function dirty() {
  return Boolean(draft) && JSON.stringify(draft) !== original;
}

function paletteOf(data, name) {
  const box = editor(data);
  const palette = {...(box.palettes?.[name] || box.palette || {})};
  for (const key of KEYS) palette[key] = String(palette[key] || "#000000").toLowerCase();
  return palette;
}

function startFrom(data, name, editing) {
  const box = editor(data);
  const custom = (box.custom || []).includes(name);
  draft = {name: editing || custom ? name : `${name} Custom`, previous: editing || custom ? name : "", base: name,
    skin: box.skins?.[name] || "", palette: paletteOf(data, name)};
  original = JSON.stringify(draft);
  open = true;
  justOpened = true;
  confirm = {what: "", until: 0};
  pending = {name: "", until: 0};
}

// Another theme's colours and skin, keeping the name (UNDO goes back to how it opened).
function rebase(data, name) {
  Object.assign(draft, {base: name, skin: editor(data).skins?.[name] || "", palette: paletteOf(data, name)});
}

// -- drawing ------------------------------------------------------------------------
function card(theme, box) {
  const swatch = theme.swatch || {};
  const style = ["bg", "panel", "border", "accent", "orange", "green", "yellow", "red", "text"]
    .filter((key) => HEX.test(swatch[key] || "")).map((key) => `--t-${key}:${swatch[key]}`).join(";");
  const active = theme.name === box.name;
  const base = open && draft?.base === theme.name;
  const tag = active ? "ACTIVE" : base ? "WORKSHOP BASE" : theme.skin ? `SKIN · ${theme.custom ? "YOURS" : "FONTS AND SHAPES"}` : theme.custom ? "YOURS" : "PALETTE";
  const button = `<button type="button" class="theme-option${active ? " active" : ""}${base ? " base" : ""}" data-theme-name="${esc(theme.name)}" style="${esc(style)}" aria-pressed="${active}" title="${open ? "Start the workshop's theme from this one" : "Use this theme"}"><span class="theme-preview" aria-hidden="true"><i></i><i></i><i></i><i></i></span><b>${esc(theme.name)}</b><small>${tag}</small></button>`;
  return theme.custom ? `<div class="theme-own">${button}<button type="button" class="theme-edit" data-tw-op="edit" data-name="${esc(theme.name)}" title="Change it in the workshop">EDIT</button></div>` : button;
}

function picker(data) {
  const box = editor(data);
  const themes = data.themes || [];
  const sets = [
    ["SKINS", "Their own fonts, corners and panel styling, on the deck and every overlay.", themes.filter((theme) => theme.skin && !theme.custom)],
    ["PALETTES", "Colours only, on the deck's own lettering.", themes.filter((theme) => !theme.skin && !theme.custom)],
    ["YOURS", "Made in the workshop. EDIT one to change it.", themes.filter((theme) => theme.custom)],
  ].filter(([, , rows]) => rows.length);
  const launch = open
    ? `<p class="tw-launch-note"><b>WORKSHOP OPEN</b> Click any theme to start from it.</p>`
    : `<button type="button" class="tw-launch-button" data-tw-op="open"><b>THEME WORKSHOP</b><span>${(box.custom || []).includes(box.name) ? `Edit ${esc(box.name)}` : `Make your own from ${esc(box.name || "this theme")}`}: colours, and any skin's fonts and shapes</span></button>`;
  return `<div class="tw-launch">${launch}</div>` + sets.map(([title, note, rows]) => `<section class="theme-set"><header><b>${title}</b><span>${note}</span><em>${rows.length}</em></header><div class="theme-options">${rows.map((theme) => card(theme, box)).join("")}</div></section>`).join("");
}

function colourRow([key, label, note]) {
  const value = draft.palette[key] || "#000000";
  return `<div class="tw-colour" data-tw-row="${key}"><input type="color" data-tw-color="${key}" value="${esc(value)}" aria-label="${esc(label)}"><span><b>${esc(label)}</b><small>${esc(note)}</small></span><input type="text" class="tw-hex" data-tw-hex="${key}" value="${esc(value)}" maxlength="7" spellcheck="false" aria-label="${esc(label)} hex"></div>`;
}

function workshop(data) {
  if (!open || !draft) return "";
  const box = editor(data);
  const builtin = new Set((data.themes || []).filter((theme) => !theme.custom).map((theme) => theme.name));
  const taken = builtin.has(draft.name.trim());
  const editing = draft.previous && (box.custom || []).includes(draft.previous);
  const now = Date.now();
  const armed = (what) => confirm.what === what && now < confirm.until;
  const bases = (data.themes || []).map((theme) => `<option value="${esc(theme.name)}"${theme.name === draft.base ? " selected" : ""}>${esc(theme.name)}${theme.custom ? " (yours)" : ""}</option>`).join("");
  const skins = [["", "None: the deck's own lettering"], ...(box.skin_choices || []).map(([id, name]) => [id, `${name}'s fonts and shapes`])]
    .map(([id, label]) => `<option value="${esc(id)}"${id === (draft.skin || "") ? " selected" : ""}>${esc(label)}</option>`).join("");
  const anim = justOpened ? " tw-anim" : "";
  justOpened = false;
  return `<section class="tw-panel${anim}" id="theme-workshop" aria-label="Theme workshop">
    <header class="tw-head">
      <span><b>THEME WORKSHOP</b><em>${editing ? `EDITING ${esc(draft.previous)}` : "NEW THEME"}</em></span>
      <span class="tw-preview-flag${dirty() ? " on" : ""}" id="tw-flag">${dirty() ? "PREVIEWING ON THE DECK · NOT SAVED" : "THE WHOLE DECK SHOWS YOUR CHANGES AS YOU MAKE THEM"}</span>
      <button type="button" class="tw-close${armed("close") ? " armed" : ""}" data-tw-op="close" title="Close the workshop">${armed("close") ? "DISCARD CHANGES?" : "CLOSE ✕"}</button>
    </header>
    <div class="tw-body">
      <div class="tw-setup">
        <label class="tw-field"><span>NAME</span><input data-tw-field="name" value="${esc(draft.name)}" maxlength="60" spellcheck="false"></label>
        <p class="tw-warn" id="tw-name-warn"${taken ? "" : " hidden"}>That's a built-in theme's name: give yours another.</p>
        <label class="tw-field"><span>START FROM<small>Its colours and skin, replacing yours</small></span><select data-tw-field="base">${bases}</select></label>
        <label class="tw-field"><span>SKIN<small>Fonts, corners and panel styling</small></span><select data-tw-field="skin">${skins}</select></label>
        <div class="tw-quick">
          <span>QUICK START<small>Pick these three, then blend the panels, lines and text shades from them.</small></span>
          <div>${[["bg", "Background"], ["text", "Text"], ["accent", "Accent"]].map(([key, label]) => `<label><input type="color" data-tw-color="${key}" value="${esc(draft.palette[key])}"><small>${label}</small></label>`).join("")}</div>
          <button type="button" data-tw-op="blend">BLEND THE REST</button>
        </div>
        <ul class="tw-checks" id="tw-checks" aria-label="How readable it is">${checks(draft.palette)}</ul>
      </div>
      <div class="tw-colours">${GROUPS.map(([title, rows]) => `<section><h5>${title}</h5>${rows.map(colourRow).join("")}</section>`).join("")}</div>
    </div>
    <footer class="tw-foot">
      <button type="button" class="primary" data-tw-op="save"${taken || !draft.name.trim() ? " disabled" : ""}>${editing && draft.name.trim() !== draft.previous ? "SAVE, RENAMED, & APPLY" : "SAVE & APPLY"}</button>
      <button type="button" data-tw-op="undo"${dirty() ? "" : " disabled"}>UNDO CHANGES</button>
      ${editing ? `<button type="button" class="danger-action${armed("delete") ? " armed" : ""}" data-tw-op="delete">${armed("delete") ? `DELETE ${esc(draft.previous)}?` : "DELETE THIS THEME"}</button>` : ""}
    </footer>
  </section>`;
}

// The THEME group's content: the picker, and the workshop when it's open.
export function themeSettings(data) {
  last = data || {};
  return `<div id="theme-settings">${picker(last)}${workshop(last)}</div>`;
}

function redraw(ui) {
  const host = document.getElementById("theme-settings");
  if (host) host.innerHTML = picker(last) + workshop(last);
  ui?.refreshTheme?.();
}

// Small changes without redrawing the panel (focus and colour pickers stay put).
function touch(ui) {
  const flag = document.getElementById("tw-flag");
  if (flag) {
    flag.classList.toggle("on", dirty());
    flag.textContent = dirty() ? "PREVIEWING ON THE DECK · NOT SAVED" : "THE WHOLE DECK SHOWS YOUR CHANGES AS YOU MAKE THEM";
  }
  const list = document.getElementById("tw-checks");
  if (list) list.innerHTML = checks(draft.palette);
  const undo = document.querySelector('#theme-workshop [data-tw-op="undo"]');
  if (undo) undo.disabled = !dirty();
  ui?.refreshTheme?.();
}

function setColour(key, value) {
  draft.palette[key] = value.toLowerCase();
  document.querySelectorAll(`#theme-workshop [data-tw-color="${key}"]`).forEach((input) => { if (input.value !== value) input.value = value; });
  const hex = document.querySelector(`#theme-workshop [data-tw-hex="${key}"]`);
  if (hex && hex !== document.activeElement) hex.value = value.toLowerCase();
}

// -- events -------------------------------------------------------------------------
export function handleThemeWorkshopClick(event, ui) {
  const control = event.target.closest?.("[data-tw-op]");
  const themeCard = !control && open ? event.target.closest?.("#theme-settings [data-theme-name]") : null;
  if (themeCard) {
    // While the workshop's open, a theme card is where to start from.
    rebase(last, themeCard.dataset.themeName);
    redraw(ui);
    return true;
  }
  if (!control || !control.closest("#theme-settings")) return false;
  const op = control.dataset.twOp;
  const box = editor(last);
  if (op === "open") {
    startFrom(last, box.name || "Void Cyan");
  } else if (op === "edit") {
    startFrom(last, control.dataset.name, true);
  } else if (op === "close") {
    if (dirty() && !(confirm.what === "close" && Date.now() < confirm.until)) {
      confirm = {what: "close", until: Date.now() + 4000};
    } else {
      open = false;
      draft = null;
    }
  } else if (op === "undo") {
    draft = JSON.parse(original);
  } else if (op === "blend") {
    for (const [key, value] of Object.entries(blended(draft.palette))) draft.palette[key] = value;
  } else if (op === "save") {
    save(ui);
    return true;
  } else if (op === "delete") {
    if (!(confirm.what === "delete" && Date.now() < confirm.until)) {
      confirm = {what: "delete", until: Date.now() + 4000};
    } else {
      remove(ui);
      return true;
    }
  }
  redraw(ui);
  return true;
}

async function save(ui) {
  const name = draft.name.trim();
  if (!name) return;
  const accepted = await ui.command("workspace", {page: "settings", operation: "save_theme", name, previous: draft.previous,
    colors: Object.fromEntries(KEYS.map((key) => [key, draft.palette[key]])), skin: draft.skin || ""});
  if (accepted) {
    pending = {name, until: Date.now() + 4000};
    open = false;
    ui.showToast?.(`${name} saved and applied`);
  } else {
    ui.showToast?.("The theme wasn't saved");
  }
  redraw(ui);
}

async function remove(ui) {
  const name = draft.previous;
  const accepted = await ui.command("workspace", {page: "settings", operation: "delete_theme", name, confirmed: true});
  if (accepted) {
    open = false;
    draft = null;
    ui.showToast?.(`${name} deleted`);
  }
  confirm = {what: "", until: 0};
  redraw(ui);
}

export function handleThemeWorkshopInput(event, ui) {
  const target = event.target;
  if (!open || !draft || !target.closest?.("#theme-workshop")) return false;
  if (target.dataset.twColor) {
    setColour(target.dataset.twColor, target.value);
  } else if (target.dataset.twHex) {
    let value = target.value.trim();
    if (value && !value.startsWith("#")) value = `#${value}`;
    target.classList.toggle("bad", !HEX.test(value));
    if (!HEX.test(value)) return true;
    setColour(target.dataset.twHex, value);
  } else if (target.dataset.twField === "name") {
    draft.name = target.value;
    const taken = (last.themes || []).some((theme) => !theme.custom && theme.name === draft.name.trim());
    const warn = document.getElementById("tw-name-warn");
    if (warn) warn.hidden = !taken;
    const save = document.querySelector('#theme-workshop [data-tw-op="save"]');
    if (save) save.disabled = taken || !draft.name.trim();
  } else if (target.dataset.twField === "base") {
    rebase(last, target.value);
    redraw(ui);
    return true;
  } else if (target.dataset.twField === "skin") {
    draft.skin = target.value;
  } else {
    return false;
  }
  touch(ui);
  return true;
}
