// The postcard album (5.5.3.7): every postcard saved as a picture, newest
// first. Click one to see it full size, copy it (to paste into Discord and
// the like) or show it in its folder. The pictures come from the deck's own
// server by id (/media/postcard/<id>), never by file path. A star keeps one
// as a favourite (favourites.js).

import {favouritesFilter, showFavouritesFilter, showViewerStar, starButton, toggleFavourite} from "./favourites.js";

let lastKey = "";
let favouritesOnly = false;
let shown = null;

function ago(seconds) {
  const age = Math.max(0, Date.now() / 1000 - Number(seconds || 0));
  if (age < 60) return "just now";
  if (age < 3600) return `${Math.round(age / 60)} min ago`;
  if (age < 86400) return `${Math.round(age / 3600)} h ago`;
  return new Date(Number(seconds) * 1000).toLocaleDateString([], {day: "numeric", month: "short", year: "numeric"});
}

function shell(root, ui) {
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="album-page">
    <header class="album-head"><div><b id="album-count"></b><small id="album-folder"></small></div>
      <div class="album-actions">${favouritesFilter("album-favs")}<button type="button" data-album="open_folder">OPEN POSTCARDS</button></div></header>
    <section class="album-settings" id="album-settings" aria-label="Postcard settings"></section>
    <ol class="album-grid" id="album-grid"></ol>
    <div class="album-viewer" id="album-viewer" hidden role="dialog" aria-modal="true" aria-label="Postcard">
      <figure><img id="album-full" alt=""><figcaption><b id="album-title"></b><small id="album-when"></small></figcaption></figure>
      <div class="album-actions">
        <button type="button" class="album-star-wide" id="album-star" data-album="favourite">☆ FAVOURITE</button>
        <button type="button" class="primary" data-album="copy">COPY</button>
        <button type="button" data-album="show">SHOW IN FOLDER</button>
        <button type="button" data-album="close">CLOSE</button>
      </div>
    </div>
  </div>`;
  // The settings: each change saves at once.
  root.addEventListener("change", async (event) => {
    const field = event.target.closest("[data-postcard-setting]");
    if (!field) return;
    const value = field.type === "checkbox" ? field.checked : field.value;
    if (!(await setting(ui, field.dataset.postcardSetting, value))) ui.showToast("That setting wasn't saved");
  });
  root.addEventListener("click", async (event) => {
    const style = event.target.closest("[data-postcard-style]");
    if (style) {
      await setting(ui, "postcard_style", style.dataset.postcardStyle);
      return;
    }
    if (event.target.closest("[data-postcard-browse]")) {
      const api = window.pywebview?.api;
      if (typeof api?.choose_folder !== "function") {
        ui.showToast("Choosing a folder works in the Void Compass window.");
        return;
      }
      const chosen = await api.choose_folder();
      if (chosen) await setting(ui, "postcards_path", String(chosen));
      return;
    }
    if (event.target.closest("[data-postcard-default]")) {
      await setting(ui, "postcards_path", "");
      return;
    }
    const star = event.target.closest("[data-star]");
    if (star) {
      const row = rows.find((item) => item.id === star.dataset.star);
      if (row) await toggleFavourite(row, "postcards", ui, () => drawAlbum(ui));
      return;
    }
    if (event.target.closest("[data-favs]")) {
      favouritesOnly = !favouritesOnly;
      drawAlbum(ui);
      return;
    }
    const card = event.target.closest("[data-postcard]");
    if (card) {
      open(card.dataset.postcard, ui);
      return;
    }
    const button = event.target.closest("[data-album]");
    if (!button) {
      if (event.target.id === "album-viewer") close(ui);
      return;
    }
    const operation = button.dataset.album;
    if (operation === "close") {
      close(ui);
      return;
    }
    if (operation === "favourite") {
      if (shown) await toggleFavourite(shown, "postcards", ui, () => drawAlbum(ui));
      return;
    }
    button.disabled = true;
    try {
      const done = await ui.command("workspace", {page: "postcards", operation, id: shown?.id || ""});
      if (operation === "copy") ui.showToast(done ? "Postcard copied: paste it anywhere" : "The postcard couldn't be copied");
    } finally {
      button.disabled = false;
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && shown) close(ui);
  });
}

let rows = [];

function open(id, ui) {
  const row = rows.find((item) => item.id === id);
  if (!row) return;
  shown = row;
  ui.byId("album-full").src = ui.apiUrl(`/media/postcard/${row.id}.png`);
  ui.byId("album-title").textContent = row.title;
  ui.byId("album-when").textContent = ago(row.at);
  showViewerStar(ui.byId("album-star"), row);
  ui.byId("album-viewer").hidden = false;
}

function close(ui) {
  shown = null;
  ui.byId("album-viewer").hidden = true;
  ui.byId("album-full").removeAttribute("src");
}

function setting(ui, key, value) {
  lastSettingsKey = "";
  return ui.command("workspace", {page: "postcards", operation: "set", key, value});
}

const STYLE_NAMES = {polaroid: "Polaroid", airmail: "Airmail", holo: "Holo", vintage: "Vintage"};
let lastSettingsKey = "";

function toggle(ui, key, label, detail, checked) {
  return `<label class="album-switch"><input type="checkbox" data-postcard-setting="${key}"${checked ? " checked" : ""}>
    <span><b>${ui.escapeHtml(label)}</b><small>${ui.escapeHtml(detail)}</small></span></label>`;
}

// Everything about postcards in one place (5.5.3.7): their design, with a
// live preview, and keeping them. Overlay Studio keeps only the overlay's own
// options (how long it stays, its size, its photo).
function renderSettings(data, ui) {
  const settings = data.settings || {};
  const panel = ui.byId("album-settings");
  const key = JSON.stringify([settings, data.preview]);
  const typing = panel.contains(document.activeElement) && document.activeElement.type === "text";
  if (key === lastSettingsKey || typing) return;
  lastSettingsKey = key;
  const current = settings.postcard_style || "polaroid";
  const styles = (data.styles || Object.keys(STYLE_NAMES)).map((style) =>
    `<button type="button" class="${style === current ? "active" : ""}" data-postcard-style="${ui.escapeHtml(style)}" aria-pressed="${style === current}">${ui.escapeHtml(STYLE_NAMES[style] || style)}</button>`).join("");
  panel.innerHTML = `
    <figure class="album-preview"><img src="${ui.apiUrl(`/media/postcard-preview/${encodeURIComponent(data.preview || "current")}.png`)}" alt="A postcard in this design">
      <figcaption>PREVIEW · THE OVERLAY AND SAVED POSTCARDS ALIKE</figcaption></figure>
    <div class="album-controls">
      <h3>DESIGN</h3>
      <div class="album-styles" role="group" aria-label="Style">${styles}</div>
      ${toggle(ui, "postcard_facts", "Journal facts", "What your scans say of the place: its kind, gravity, firsts, life, distance from Sol.", settings.postcard_facts)}
      ${toggle(ui, "postcard_note", "The Watcher's note", "A handwritten line from the Watcher, signed, while its thoughts are on.", settings.postcard_note)}
      ${toggle(ui, "postcard_doing", "What you were doing", "In supercruise, landed, docked, on foot…", settings.postcard_doing)}
      <label class="album-greeting"><span><b>Lettering</b><small>The words over the place's name.</small></span>
        <select data-postcard-setting="postcard_greeting">${[["greetings", "Greetings from…"], ["wish", "Wish you were here"], ["custom", "Your own words"], ["none", "None"]]
          .map(([value, name]) => `<option value="${value}"${value === (settings.postcard_greeting || "greetings") ? " selected" : ""}>${name}</option>`).join("")}</select></label>
      <label class="album-greeting-own"${settings.postcard_greeting === "custom" ? "" : " hidden"}><span><b>Your own words</b><small>Up to 40 letters, over the name in place of "Greetings from".</small></span>
        <input type="text" maxlength="40" data-postcard-setting="postcard_greeting_text" value="${ui.escapeHtml(settings.postcard_greeting_text || "")}" placeholder="Postcard from"></label>
      <h3>KEEPING</h3>
      ${toggle(ui, "screenshot_postcards", "Save postcards as pictures", "Each new screenshot's postcard as a PNG, kept in this album. Made even with the Postcards overlay off.", settings.screenshot_postcards)}
      <div class="album-folder"><span><b>Postcard folder</b><small>Empty is the postcards folder in Void Compass's own folder.</small></span>
        <span class="album-folder-row"><input type="text" aria-label="Postcard folder" data-postcard-setting="postcards_path" value="${ui.escapeHtml(settings.postcards_path || "")}" placeholder="${ui.escapeHtml(settings.default_folder || "postcards")}">
          <button type="button" data-postcard-browse>BROWSE</button><button type="button" data-postcard-default>DEFAULT</button></span></div>
      ${toggle(ui, "screenshot_captions", "Caption files", "A text file beside each new screenshot: its postcard in words.", settings.screenshot_captions)}
    </div>`;
}

export function renderPostcards(data = {}, ui) {
  const root = ui.byId("postcards-workspace");
  if (!root) return;
  if (!root.querySelector(".album-page")) shell(root, ui);
  rows = Array.isArray(data.rows) ? data.rows : [];
  renderSettings(data, ui);
  ui.byId("album-count").textContent = rows.length ? `${ui.numeric(rows.length)} POSTCARD${rows.length === 1 ? "" : "S"}` : "NO POSTCARDS YET";
  ui.byId("album-folder").textContent = data.folder || "";
  if (shown) shown = rows.find((row) => row.id === shown.id) || shown;
  drawAlbum(ui);
}

function drawAlbum(ui) {
  showFavouritesFilter(ui.byId("album-favs"), rows, favouritesOnly);
  showViewerStar(ui.byId("album-star"), shown);
  const list = favouritesOnly ? rows.filter((row) => row.favourite) : rows;
  const key = JSON.stringify([favouritesOnly, list.map((row) => [row.id, row.at, Boolean(row.favourite)])]);
  if (key === lastKey) return;
  lastKey = key;
  ui.byId("album-grid").innerHTML = list.length
    ? list.map((row) => `<li class="album-tile${row.favourite ? " favourite" : ""}">${starButton(row, ui)}<button type="button" data-postcard="${ui.escapeHtml(row.id)}" title="${ui.escapeHtml(row.title)}">
        <img src="${ui.apiUrl(`/media/postcard-thumb/${row.id}.jpg`)}" alt="" loading="lazy">
        <span><b>${ui.escapeHtml(row.title)}</b><small>${ui.escapeHtml(ago(row.at))}</small></span></button></li>`).join("")
    : `<li class="album-empty">${rows.length ? "No favourites yet: tap the ☆ on a postcard to keep it here." : "Take a screenshot in game (F10) and its postcard is kept here."}</li>`;
}
