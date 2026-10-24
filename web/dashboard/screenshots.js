// The screenshot album (5.5.3.7): the screenshot folder, newest first,
// grouped by day. Filter by system, click one to see it full size (the arrow
// keys step through them), copy it (to paste into Discord and the like) or
// show it in its folder. A caption file beside a picture is shown with it.
// The pictures come from the deck's own server by id (/media/shot/<id>),
// never by file path. A star keeps one as a favourite (favourites.js).

import {favouritesFilter, showFavouritesFilter, showViewerStar, starButton, toggleFavourite} from "./favourites.js";

let rows = [];
let favouritesOnly = false;
let shownId = "";
let filter = "";
let lastKey = "";

function when(seconds) {
  return new Date(Number(seconds || 0) * 1000);
}

function dayLabel(seconds) {
  const date = when(seconds);
  const today = new Date();
  const yesterday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return "TODAY";
  if (date.toDateString() === yesterday.toDateString()) return "YESTERDAY";
  return date.toLocaleDateString([], {weekday: "short", day: "numeric", month: "short", year: "numeric"}).toUpperCase();
}

function time(seconds) {
  return when(seconds).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
}

function visible() {
  const words = filter.trim().toLowerCase();
  return rows.filter((row) => (!favouritesOnly || row.favourite)
    && (!words || `${row.title} ${row.system} ${row.caption}`.toLowerCase().includes(words)));
}

function redraw(ui) {
  lastKey = "";
  drawGrid(ui);
  showFavouritesFilter(ui.byId("shots-favs"), rows, favouritesOnly);
  showViewerStar(ui.byId("shots-star"), rows.find((row) => row.id === shownId));
}

// The full-size viewer belongs to the window, not the page (5.5.3.9): inside
// the page it opened at the page's top, out of sight when you'd scrolled
// down the gallery. It keeps its own clicks, and shuts if you change page.
function lift(root, id, onClick, onLeave) {
  document.querySelectorAll(`#${id}`).forEach((stale) => {
    if (!root.contains(stale)) stale.remove();
  });
  const viewer = root.querySelector(`#${id}`);
  if (!viewer) return;
  document.body.append(viewer);
  viewer.addEventListener("click", onClick);
  document.addEventListener("click", (event) => {
    if (!viewer.hidden && event.target.closest?.(".nav-item, [data-page]") && !viewer.contains(event.target)) onLeave();
  }, true);
}

function shell(root, ui) {
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="album-page shots-page">
    <header class="album-head"><div><b id="shots-count"></b><small id="shots-folder"></small></div>
      <div class="album-actions">
        ${favouritesFilter("shots-favs")}
        <input type="search" id="shots-filter" class="shots-filter" placeholder="Filter by system…" aria-label="Filter screenshots by system">
        <button type="button" data-shots="open_folder">OPEN SCREENSHOTS</button>
      </div></header>
    <p class="album-note" id="shots-note" hidden></p>
    <ol class="album-grid shots-grid" id="shots-grid"></ol>
    <div class="album-viewer shots-viewer" id="shots-viewer" hidden role="dialog" aria-modal="true" aria-label="Screenshot">
      <figure><img id="shots-full" alt=""><figcaption><b id="shots-title"></b><small id="shots-when"></small></figcaption>
        <p class="shots-caption" id="shots-caption" hidden></p></figure>
      <div class="album-actions">
        <button type="button" data-shots="prev" aria-label="Newer screenshot">◀</button>
        <button type="button" class="album-star-wide" id="shots-star" data-shots="favourite">☆ FAVOURITE</button>
        <button type="button" class="primary" data-shots="postcard">✎ MAKE A POSTCARD</button>
        <button type="button" data-shots="copy">COPY</button>
        <button type="button" data-shots="show">SHOW IN FOLDER</button>
        <button type="button" data-shots="close">CLOSE</button>
        <button type="button" data-shots="next" aria-label="Older screenshot">▶</button>
      </div>
    </div>
  </div>`;
  ui.byId("shots-filter").addEventListener("input", (event) => {
    filter = event.target.value;
    lastKey = "";
    drawGrid(ui);
  });
  const onClick = async (event) => {
    const star = event.target.closest("[data-star]");
    if (star) {
      const row = rows.find((item) => item.id === star.dataset.star);
      if (row) await toggleFavourite(row, "screenshots", ui, () => redraw(ui));
      return;
    }
    if (event.target.closest("[data-favs]")) {
      favouritesOnly = !favouritesOnly;
      redraw(ui);
      return;
    }
    const tile = event.target.closest("[data-shot]");
    if (tile) {
      open(tile.dataset.shot, ui);
      return;
    }
    const button = event.target.closest("[data-shots]");
    if (!button) {
      if (event.target.id === "shots-viewer") close(ui);
      return;
    }
    const operation = button.dataset.shots;
    if (operation === "close") return close(ui);
    if (operation === "prev" || operation === "next") return step(operation === "next" ? 1 : -1, ui);
    if (operation === "favourite") {
      const row = rows.find((item) => item.id === shownId);
      if (row) await toggleFavourite(row, "screenshots", ui, () => redraw(ui));
      return;
    }
    if (operation === "postcard") {
      // Made on the deck's side, then it opens in the Postcards page's editor.
      button.disabled = true;
      const done = await ui.command("workspace", {page: "screenshots", operation, id: shownId});
      button.disabled = false;
      if (!done) return ui.showToast("That screenshot couldn't be made into a postcard");
      close(ui);
      ui.showToast("Postcard made: opening the editor…");
      document.querySelector('.nav-item[data-page="postcards"]')?.click();
      return;
    }
    button.disabled = true;
    try {
      const done = await ui.command("workspace", {page: "screenshots", operation, id: shownId});
      if (operation === "copy") ui.showToast(done ? "Screenshot copied: paste it anywhere" : "The screenshot couldn't be copied");
    } finally {
      button.disabled = false;
    }
  };
  root.addEventListener("click", onClick);
  lift(root, "shots-viewer", onClick, () => close(ui));
  document.addEventListener("keydown", (event) => {
    if (!shownId) return;
    if (event.key === "Escape") close(ui);
    else if (event.key === "ArrowRight") step(1, ui);
    else if (event.key === "ArrowLeft") step(-1, ui);
  });
}

// Through what the filter shows, newest to oldest.
function step(direction, ui) {
  const list = visible();
  const at = list.findIndex((row) => row.id === shownId);
  const next = list[at + direction];
  if (next) open(next.id, ui);
}

function open(id, ui) {
  const row = rows.find((item) => item.id === id);
  if (!row) return;
  shownId = id;
  ui.byId("shots-full").src = ui.apiUrl(`/media/shot/${row.id}`);
  ui.byId("shots-title").textContent = row.title;
  ui.byId("shots-when").textContent = `${dayLabel(row.at)} · ${time(row.at)} · ${row.kind}${row.high_res ? " · HIGH RES" : ""}`;
  const caption = ui.byId("shots-caption");
  caption.textContent = row.caption || "";
  caption.hidden = !row.caption;
  showViewerStar(ui.byId("shots-star"), row);
  ui.byId("shots-viewer").hidden = false;
}

function close(ui) {
  shownId = "";
  ui.byId("shots-viewer").hidden = true;
  ui.byId("shots-full").removeAttribute("src");
}

function drawGrid(ui) {
  const list = visible();
  const key = JSON.stringify([filter, favouritesOnly, list.map((row) => [row.id, row.at, Boolean(row.caption), Boolean(row.favourite)])]);
  if (key === lastKey) return;
  lastKey = key;
  let day = "";
  const items = [];
  for (const row of list) {
    const label = dayLabel(row.at);
    if (label !== day) {
      day = label;
      items.push(`<li class="shots-day">${ui.escapeHtml(label)}</li>`);
    }
    const tags = [row.kind === "BMP" ? "BMP" : "", row.high_res ? "HIGH RES" : "", row.caption ? "CAPTION" : ""].filter(Boolean)
      .map((tag) => `<em>${tag}</em>`).join("");
    items.push(`<li class="album-tile${row.favourite ? " favourite" : ""}">${starButton(row, ui)}<button type="button" data-shot="${ui.escapeHtml(row.id)}" title="${ui.escapeHtml(row.title)}">
        <img src="${ui.apiUrl(`/media/shot-thumb/${row.id}.jpg`)}" alt="" loading="lazy">
        <span><b>${ui.escapeHtml(row.title)}</b><small>${ui.escapeHtml(time(row.at))}${tags ? ` <i>${tags}</i>` : ""}</small></span></button></li>`);
  }
  ui.byId("shots-grid").innerHTML = items.length ? items.join("")
    : `<li class="album-empty">${!rows.length ? "Take a screenshot in game (F10) and it shows up here."
      : favouritesOnly && !filter.trim() ? "No favourites yet: tap the ☆ on a screenshot to keep it here." : "No screenshot matches that."}</li>`;
}

export function renderScreenshots(data = {}, ui) {
  const root = ui.byId("screenshots-workspace");
  if (!root) return;
  if (!root.querySelector(".shots-page")) shell(root, ui);
  rows = Array.isArray(data.rows) ? data.rows : [];
  const total = Number(data.total || rows.length);
  ui.byId("shots-count").textContent = !rows.length ? "NO SCREENSHOTS YET"
    : total > rows.length ? `NEWEST ${ui.numeric(rows.length)} OF ${ui.numeric(total)} SCREENSHOTS`
      : `${ui.numeric(rows.length)} SCREENSHOT${rows.length === 1 ? "" : "S"}`;
  ui.byId("shots-folder").textContent = data.folder || "";
  const note = ui.byId("shots-note");
  note.hidden = data.found !== false;
  note.textContent = "That folder isn't there. Choose where Elite saves its screenshots in Settings › Screenshots.";
  drawGrid(ui);
  showFavouritesFilter(ui.byId("shots-favs"), rows, favouritesOnly);
  showViewerStar(ui.byId("shots-star"), rows.find((row) => row.id === shownId));
}
