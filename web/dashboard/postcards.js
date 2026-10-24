// The Postcards page (5.5.3.7, rebuilt 5.5.4, again 5.6.3): the album, the
// studio where the look for new postcards is designed, and keeping them.
// Pictures come from the deck's own server by id (/media/postcard/<id>),
// never by path. A star keeps one as a favourite (favourites.js). EDIT opens
// the editor (postcard-editor.js), which draws the card in the page and
// saves exactly what it shows; the slideshow is postcard-show.js.

import {favouritesFilter, showFavouritesFilter, showViewerStar, starButton, toggleFavourite} from "./favourites.js";
import {editorOpen, openEditor} from "./postcard-editor.js";
import {showOpen, startShow} from "./postcard-show.js";

const TABS = [["album", "ALBUM"], ["studio", "STUDIO"], ["keeping", "KEEPING"]];
const FILTERS = [["all", "ALL"], ["editable", "EDITABLE"], ["older", "OLDER"]];
const SORTS = [["newest", "Newest first"], ["oldest", "Oldest first"], ["az", "Place A–Z"]];
const GROUPS = [["month", "By month"], ["day", "By day"], ["region", "By region"], ["system", "By system"], ["none", "All together"]];
const BASE_NAMES = {polaroid: "Polaroid", airmail: "Airmail", holo: "Holo", vintage: "Vintage"};
// What each look's paper, ink and lettering look like, for its swatch.
const BASE_SWATCH = {
  polaroid: ["#eef0e6", "#070b10", "var(--orange)"], airmail: ["#f6eedb", "#1f2a44", "#c8323c"],
  holo: ["var(--panel)", "var(--text)", "var(--accent)"], vintage: ["#e9dab6", "#3b2a1a", "#b4532a"],
};
const FONT_NAMES = {"": "As the look", hud: "Cockpit capitals", serif: "Serif", hand: "Handwriting"};
const FILTER_NAMES = {none: "As the look", sepia: "Sepia", mono: "Black & white", vivid: "Vivid", cool: "Cool"};
// Your text sizes (5.5.4): the lettering, the note, the details.
const TEXT_PARTS = [["lettering", "Lettering", "The place's name and the words over it"],
  ["note", "Note", "The handwriting and its signature"], ["details", "Details", "Facts, where, the date and the time"]];
const TEXT_SIZES = [85, 100, 115, 130, 150];
const sizeOptions = (chosen) => TEXT_SIZES.map((size) => `<option value="${size}"${Number(chosen || 100) === size ? " selected" : ""}>${size}%</option>`).join("");
const MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"];

const view = {tab: "album", filter: "all", favourites: false, find: "", sort: "newest", group: "month", month: ""};
try {
  view.tab = sessionStorage.getItem("vc-postcards-tab") || "album";
  view.group = localStorage.getItem("voidcompass.postcards.group") || "month";
} catch { /* the album, by month, then */ }
let rows = [];
let data = {};
let shown = null;
let editorWanted = "";
let openedNext = "";
let themeBackground = "";
let lastAlbumKey = "";
let lastStudioKey = "";
let lastKeepingKey = "";
let previewTurn = 0;
let drafting = false;
const timers = {};

function later(name, wait, task) {
  window.clearTimeout(timers[name]);
  timers[name] = window.setTimeout(task, wait);
}

function ago(seconds) {
  const age = Math.max(0, Date.now() / 1000 - Number(seconds || 0));
  if (age < 60) return "just now";
  if (age < 3600) return `${Math.round(age / 60)} min ago`;
  if (age < 86400) return `${Math.round(age / 3600)} h ago`;
  return eliteDate(seconds);
}

// The game's calendar: our year plus 1286.
function eliteDate(seconds) {
  const day = new Date(Number(seconds) * 1000);
  return `${day.getDate()} ${MONTHS[day.getMonth()].slice(0, 3)} ${day.getFullYear() + 1286}`;
}

function monthOf(seconds) {
  const day = new Date(Number(seconds) * 1000);
  return `${MONTHS[day.getMonth()]} ${day.getFullYear() + 1286}`;
}

// A slight, steady tilt for each card on the table.
function tilt(id) {
  let hash = 0;
  for (const char of String(id)) hash = (hash * 31 + char.charCodeAt(0)) | 0;
  return Math.abs(hash) % 5;
}

// The viewer belongs to the window, not the page (5.5.3.9): it keeps its own
// clicks, and shuts if you change page.
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

let ui = null;

function shell(root) {
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="pc-page">
    <header class="pc-head">
      <dl class="pc-stats" id="pc-stats"></dl>
      <nav class="pc-tabs" role="tablist" aria-label="Postcards">${TABS.map(([id, label]) =>
        `<button type="button" role="tab" id="pc-tab-${id}" data-pc-tab="${id}" aria-controls="pc-panel-${id}">${label}</button>`).join("")}</nav>
    </header>

    <section class="pc-panel" id="pc-panel-album" data-pc-panel="album" role="tabpanel" aria-labelledby="pc-tab-album">
      <div class="pc-toolbar">
        <input type="search" id="pc-find" placeholder="Find a place" aria-label="Find a place" autocomplete="off">
        <div class="pc-filter" role="group" aria-label="Show">${FILTERS.map(([id, label]) =>
          `<button type="button" data-pc-filter="${id}">${label}</button>`).join("")}</div>
        ${favouritesFilter("album-favs")}
        <select id="pc-sort" aria-label="Order">${SORTS.map(([id, label]) => `<option value="${id}">${label}</option>`).join("")}</select>
        <select id="pc-group" aria-label="Group">${GROUPS.map(([id, label]) => `<option value="${id}"${id === view.group ? " selected" : ""}>${label}</option>`).join("")}</select>
        <button type="button" class="primary" data-pc-show>▶ SLIDESHOW</button>
        <button type="button" data-album="open_folder">OPEN FOLDER</button>
      </div>
      <div class="pc-hero" id="pc-hero" hidden></div>
      <div class="pc-timeline" id="pc-timeline" hidden></div>
      <div class="pc-restore" id="pc-restore" hidden></div>
      <div class="pc-album" id="pc-album"></div>
    </section>

    <section class="pc-panel pc-studio" id="pc-panel-studio" data-pc-panel="studio" role="tabpanel" aria-labelledby="pc-tab-studio" hidden>
      <figure class="pc-preview">
        <div class="pc-table"><img id="pc-preview-img" alt="A postcard in this design"></div>
        <figcaption><b id="pc-preview-state">LIVE PREVIEW</b><span>The overlay and saved postcards alike.</span>
          <button type="button" id="pc-draft-reset" data-pc-reset hidden>UNDO CHANGES</button></figcaption>
      </figure>
      <div class="pc-controls" id="pc-controls"></div>
    </section>

    <section class="pc-panel" id="pc-panel-keeping" data-pc-panel="keeping" role="tabpanel" aria-labelledby="pc-tab-keeping" hidden>
      <div class="pc-keeping" id="pc-keeping"></div>
    </section>

    <div class="pc-viewer" id="pc-viewer" hidden role="dialog" aria-modal="true" aria-label="Postcard">
      <div class="pc-stage">
        <button type="button" class="pc-step" data-pc-step="-1" aria-label="Previous postcard">‹</button>
        <figure><img id="pc-full" alt=""></figure>
        <button type="button" class="pc-step" data-pc-step="1" aria-label="Next postcard">›</button>
      </div>
      <aside class="pc-side">
        <header><small id="pc-when"></small><h3 id="pc-title"></h3><span class="pc-badges" id="pc-badges"></span></header>
        <div class="pc-side-actions" id="pc-actions">
          <button type="button" class="album-star-wide" id="album-star" data-album="favourite">☆ FAVOURITE</button>
          <button type="button" class="primary" data-album="copy">COPY</button>
          <button type="button" data-album="show">SHOW IN FOLDER</button>
          <button type="button" class="primary pc-edit-button" id="pc-edit" data-pc-edit>✎ EDIT IN THE EDITOR</button>
          <button type="button" data-pc-show-here>▶ SLIDESHOW FROM HERE</button>
          <button type="button" id="pc-restore-one" data-pc-restore-one hidden>MAKE EDITABLE</button>
          <button type="button" class="danger-action" id="pc-delete" data-pc-delete>DELETE</button>
          <button type="button" data-album="close">CLOSE</button>
        </div>
        <dl class="pc-side-facts" id="pc-side-facts"></dl>
        <p class="pc-side-note" id="pc-side-note"></p>
      </aside>
    </div>
  </div>`;

  const onClick = async (event) => {
    const tab = event.target.closest("[data-pc-tab]");
    if (tab) return showTab(tab.dataset.pcTab);
    const filter = event.target.closest("[data-pc-filter]");
    if (filter) {
      view.filter = filter.dataset.pcFilter;
      return drawAlbum(true);
    }
    if (event.target.closest("[data-favs]")) {
      view.favourites = !view.favourites;
      return drawAlbum(true);
    }
    const star = event.target.closest("[data-star]");
    if (star) {
      const row = rows.find((item) => item.id === star.dataset.star);
      if (row) await toggleFavourite(row, "postcards", ui, () => drawAlbum(true));
      return undefined;
    }
    const card = event.target.closest("[data-postcard]");
    if (card) return open(card.dataset.postcard);
    const step = event.target.closest("[data-pc-step]");
    if (step) return stepBy(Number(step.dataset.pcStep));
    if (event.target.closest("[data-pc-restore-all]")) {
      return ui.showToast((await send("restore")) ? "Looking for their screenshots…" : "There's nothing to restore");
    }
    if (event.target.closest("[data-pc-restore-one]")) {
      if (shown && await send("restore", {id: shown.id})) ui.showToast("Looking for its screenshot…");
      return undefined;
    }
    if (event.target.closest("[data-pc-edit]")) return editCard(shown?.id);
    const heroEdit = event.target.closest("[data-pc-hero-edit]");
    if (heroEdit) return editCard(heroEdit.dataset.pcHeroEdit);
    if (event.target.closest("[data-pc-show]")) return slideshow(0);
    if (event.target.closest("[data-pc-show-here]")) {
      const list = listed();
      const at = Math.max(0, list.findIndex((row) => row.id === shown?.id));
      close();
      return slideshow(at);
    }
    const month = event.target.closest("[data-pc-month]");
    if (month) {
      view.month = view.month === month.dataset.pcMonth ? "" : month.dataset.pcMonth;
      return drawAlbum(true);
    }
    const remove = event.target.closest("[data-pc-delete]");
    if (remove && shown) {
      if (!remove.dataset.armed) {
        remove.dataset.armed = "1";
        remove.textContent = "SURE? TO THE RECYCLE BIN";
        return setTimeout(() => { if (remove.isConnected) { delete remove.dataset.armed; remove.textContent = "DELETE"; } }, 4000);
      }
      delete remove.dataset.armed;
      remove.textContent = "DELETE";
      const gone = shown;
      if (!(await send("delete", {id: gone.id}))) return ui.showToast("The postcard couldn't be deleted");
      rows = rows.filter((row) => row.id !== gone.id);
      close();
      drawStats();
      drawAlbum(true);
      return ui.showToast(`${gone.title} moved to the Recycle Bin`);
    }
    if (event.target.closest("[data-pc-reset]")) return resetDraft();
    if (event.target.closest("[data-theme-save]")) return saveTheme();
    if (event.target.closest("[data-theme-new]")) return newTheme();
    const forget = event.target.closest("[data-theme-delete]");
    if (forget) {
      if (!forget.dataset.armed) {
        forget.dataset.armed = "1";
        forget.textContent = "SURE?";
        return setTimeout(() => { if (forget.isConnected) { delete forget.dataset.armed; forget.textContent = "DELETE THEME"; } }, 3000);
      }
      await send("delete_theme", {name: forget.dataset.themeDelete});
      return resetDraft();
    }
    const style = event.target.closest("[data-postcard-style]");
    if (style) {
      window.clearTimeout(timers.draft);
      if (drafting) await send("draft_clear");
      drafting = false;
      lastStudioKey = "";
      return setting("postcard_style", style.dataset.postcardStyle);
    }
    if (event.target.closest("[data-postcard-browse]")) {
      const api = window.pywebview?.api;
      if (typeof api?.choose_folder !== "function") return ui.showToast("Choosing a folder works in the Void Compass window.");
      const chosen = await api.choose_folder();
      if (chosen) await setting("postcards_path", String(chosen));
      return undefined;
    }
    if (event.target.closest("[data-postcard-default]")) return setting("postcards_path", "");
    const button = event.target.closest("[data-album]");
    if (!button) {
      if (event.target.id === "pc-viewer") close();
      return undefined;
    }
    const operation = button.dataset.album;
    if (operation === "close") return close();
    if (operation === "favourite") {
      if (shown) await toggleFavourite(shown, "postcards", ui, () => drawAlbum(true));
      return undefined;
    }
    button.disabled = true;
    try {
      const done = await send(operation, {id: shown?.id || ""});
      if (operation === "copy") ui.showToast(done ? "Postcard copied: paste it anywhere" : "The postcard couldn't be copied");
    } finally {
      button.disabled = false;
    }
    return undefined;
  };
  root.addEventListener("click", onClick);
  lift(root, "pc-viewer", onClick, () => close());

  root.addEventListener("input", (event) => {
    if (event.target.id === "pc-find") {
      view.find = event.target.value.trim().toLowerCase();
      return drawAlbum(true);
    }
    const field = event.target.closest('input[type="text"][data-postcard-setting]');
    if (field) return saveText(field, 700);
    if (event.target.closest("#pc-theme")) {
      if (event.target.name === "angle") event.target.closest("label").querySelector("[data-angle-out]").textContent = `${event.target.value}°`;
      return later("draft", 280, sendDraft);
    }
    return undefined;
  });
  root.addEventListener("change", async (event) => {
    if (event.target.id === "pc-sort") {
      view.sort = event.target.value;
      return drawAlbum(true);
    }
    if (event.target.id === "pc-group") {
      view.group = event.target.value;
      try { localStorage.setItem("voidcompass.postcards.group", view.group); } catch { /* not kept */ }
      return drawAlbum(true);
    }
    if (event.target.name === "bg_file") return readBackground(event.target);
    if (event.target.closest("#pc-theme")) return later("draft", 0, sendDraft);
    const field = event.target.closest("[data-postcard-setting]");
    if (!field) return undefined;
    if (field.type === "text") return saveText(field, 0);
    const key = field.dataset.postcardSetting;
    if (key === "postcard_note_mode") root.querySelectorAll(".pc-note-own").forEach((box) => { box.hidden = field.value !== "own"; });
    if (key === "postcard_greeting") {
      const own = root.querySelector(".pc-greeting-own");
      if (own) {
        own.hidden = field.value !== "custom";
        if (!own.hidden) own.querySelector("input")?.focus();
      }
    }
    if (!(await setting(key, field.type === "checkbox" ? field.checked : field.value))) ui.showToast("That setting wasn't saved");
    return undefined;
  });
  document.addEventListener("keydown", (event) => {
    if (!shown || ui.byId("pc-viewer")?.hidden || editorOpen() || showOpen()) return;
    if (event.key === "Escape") close();
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "");
    if (!typing && (event.key === "ArrowLeft" || event.key === "ArrowRight")) stepBy(event.key === "ArrowLeft" ? -1 : 1);
  });
}

const send = (operation, extra = {}) => ui.command("workspace", {page: "postcards", operation, ...extra});

function setting(key, value) {
  lastStudioKey = "";
  lastKeepingKey = "";
  return send("set", {key, value});
}

function showTab(tab) {
  if (view.tab === "studio" && tab !== "studio" && drafting) resetDraft();
  view.tab = TABS.some(([id]) => id === tab) ? tab : "album";
  try { sessionStorage.setItem("vc-postcards-tab", view.tab); } catch { /* not kept */ }
  for (const [id] of TABS) {
    const button = ui.byId(`pc-tab-${id}`);
    button.setAttribute("aria-selected", String(id === view.tab));
    button.classList.toggle("active", id === view.tab);
    ui.byId(`pc-panel-${id}`).hidden = id !== view.tab;
  }
}

// -- The album ---------------------------------------------------------------
function listed() {
  let list = rows.filter((row) => (view.filter === "editable" ? row.editable : view.filter === "older" ? !row.editable : true));
  if (view.favourites) list = list.filter((row) => row.favourite);
  if (view.find) list = list.filter((row) => [row.title, row.system, row.region, row.note].some((text) => String(text || "").toLowerCase().includes(view.find)));
  if (view.month) list = list.filter((row) => monthOf(row.taken || row.at) === view.month);
  const taken = (row) => Number(row.taken || row.at || 0);
  if (view.sort === "oldest") list = [...list].sort((a, b) => taken(a) - taken(b));
  else if (view.sort === "az") list = [...list].sort((a, b) => a.title.localeCompare(b.title));
  else list = [...list].sort((a, b) => taken(b) - taken(a));
  return list;
}

function drawAlbum(force = false) {
  showFavouritesFilter(ui.byId("album-favs"), rows, view.favourites);
  showViewerStar(ui.byId("album-star"), shown);
  for (const button of ui.byId("postcards-workspace").querySelectorAll("[data-pc-filter]")) {
    button.setAttribute("aria-pressed", String(button.dataset.pcFilter === view.filter));
  }
  const list = listed();
  const key = JSON.stringify([view, list.map((row) => [row.id, row.at, row.favourite, row.editable, row.designed])]);
  if (key === lastAlbumKey && !force) return;
  lastAlbumKey = key;
  drawHero();
  drawTimeline();
  const esc = ui.escapeHtml;
  const tile = (row) => `<li class="pc-tile pc-tilt-${tilt(row.id)}${row.favourite ? " favourite" : ""}">${starButton(row, ui)}
    <button type="button" data-postcard="${esc(row.id)}" title="${esc(row.title)}">
      <img src="${ui.apiUrl(`/media/postcard-thumb/${row.id}.jpg?v=${encodeURIComponent(row.at)}`)}" alt="" loading="lazy">
      <span><b>${esc(row.title)}</b><small>${esc([eliteDate(row.taken || row.at), row.region].filter(Boolean).join(" · "))}${row.editable ? "" : " · OLDER"}</small></span>
      ${row.designed ? `<i class="pc-made" title="Made in the editor">✎</i>` : ""}</button></li>`;
  if (!list.length) {
    ui.byId("pc-album").innerHTML = `<p class="album-empty">${!rows.length ? "Take a screenshot in game (F10) and its postcard is kept here. Saving them is on the KEEPING tab. Or make one from any screenshot on the Screenshots page."
      : view.favourites ? "No favourites yet: tap the ☆ on a postcard to keep it here." : "No postcard matches."}</p>`;
    return;
  }
  const groupOf = (row) => {
    if (view.sort === "az") return row.title.slice(0, 1).toUpperCase();
    if (view.group === "day") return eliteDate(row.taken || row.at);
    if (view.group === "region") return (row.region || "Somewhere unknown").toUpperCase();
    if (view.group === "system") return String(row.system || row.title).toUpperCase();
    if (view.group === "none") return "";
    return monthOf(row.taken || row.at);
  };
  const groups = [];
  const byName = new Map();
  for (const row of list) {
    const name = groupOf(row);
    // Regions and systems gather wherever they come in the list; days and months follow it.
    let group = ["region", "system"].includes(view.group) && view.sort !== "az" ? byName.get(name) : groups.at(-1)?.name === name ? groups.at(-1) : null;
    if (!group) { group = {name, rows: []}; groups.push(group); byName.set(name, group); }
    group.rows.push(row);
  }
  ui.byId("pc-album").innerHTML = groups.map((group) => {
    const places = [...new Set(group.rows.map((row) => row.title))];
    const sub = view.group === "day" || view.group === "month" ? places.slice(0, 4).join(" · ") + (places.length > 4 ? ` · +${places.length - 4}` : "") : "";
    return `<section class="pc-month">${group.name ? `<h4>${esc(group.name)}<span>${group.rows.length}</span>${sub ? `<small>${esc(sub)}</small>` : ""}</h4>` : ""}
      <ol class="pc-grid">${group.rows.map(tile).join("")}</ol></section>`;
  }).join("");
}

// The one to look at today: on this day in an earlier year, or a favourite, or the newest.
function heroRow() {
  if (!rows.length) return null;
  const today = new Date();
  const same = rows.filter((row) => {
    const day = new Date(Number(row.taken || row.at) * 1000);
    return day.getDate() === today.getDate() && day.getMonth() === today.getMonth() && day.getFullYear() < today.getFullYear();
  });
  if (same.length) return {row: same[0], why: `ON THIS DAY · ${today.getFullYear() - new Date(Number(same[0].taken || same[0].at) * 1000).getFullYear()} YEAR${same.length === 1 ? "" : "S"} AGO`};
  const starred = rows.filter((row) => row.favourite);
  const pool = starred.length ? starred : rows;
  // The same one all day, a different one tomorrow.
  const pick = pool[Math.floor(Date.now() / 86400000) % pool.length];
  return {row: pick, why: starred.length ? "FROM YOUR FAVOURITES" : "FROM THE ALBUM"};
}

function drawHero() {
  const panel = ui.byId("pc-hero");
  const chosen = view.find || view.month || view.favourites ? null : heroRow();
  panel.hidden = !chosen;
  if (!chosen) return;
  const {row, why} = chosen;
  const esc = ui.escapeHtml;
  panel.innerHTML = `<button type="button" class="pc-hero-card" data-postcard="${esc(row.id)}">
      <img src="${ui.apiUrl(`/media/postcard-thumb/${row.id}.jpg?v=${encodeURIComponent(row.at)}`)}" alt=""></button>
    <div class="pc-hero-words"><small>${why}</small><h3>${esc(row.title)}</h3>
      <span>${esc([row.system && row.system !== row.title ? row.system : "", row.region, eliteDate(row.taken || row.at)].filter(Boolean).join(" · "))}</span>
      ${row.note ? `<blockquote>“${esc(row.note)}”</blockquote>` : ""}
      <div class="pc-hero-actions"><button type="button" class="primary" data-postcard="${esc(row.id)}">OPEN</button>
        ${row.editable ? `<button type="button" data-pc-hero-edit="${esc(row.id)}">✎ EDIT</button>` : ""}
        <button type="button" data-pc-show>▶ SLIDESHOW</button></div></div>`;
}

// A strip of months with how many were sent in each; click one to see only it.
function drawTimeline() {
  const panel = ui.byId("pc-timeline");
  const months = new Map();
  for (const row of rows) {
    const name = monthOf(row.taken || row.at);
    months.set(name, (months.get(name) || 0) + 1);
  }
  panel.hidden = months.size < 2;
  if (months.size < 2) return;
  const most = Math.max(...months.values());
  const entries = [...months.entries()].reverse();
  panel.innerHTML = `<small>TIMELINE</small><ol>${entries.map(([name, count]) =>
    `<li><button type="button" class="${view.month === name ? "active" : ""}" data-pc-month="${ui.escapeHtml(name)}" title="${count} postcard${count === 1 ? "" : "s"}">
      <i style="height:${Math.round(10 + 34 * count / most)}px"></i><span>${ui.escapeHtml(name.slice(0, 3))}</span><b>${count}</b></button></li>`).join("")}</ol>
    ${view.month ? `<button type="button" class="pc-timeline-all" data-pc-month="${ui.escapeHtml(view.month)}">SHOW EVERY MONTH</button>` : ""}`;
}

function slideshow(start) {
  const list = listed();
  if (!list.length) return ui.showToast("No postcards to show");
  return startShow({ui, rows: list, start, eliteDate});
}

function drawStats() {
  const places = new Set(rows.map((row) => row.title.toLowerCase())).size;
  const times = rows.map((row) => Number(row.taken || row.at || 0)).filter(Boolean);
  const stat = (label, value) => `<div><dt>${label}</dt><dd>${value}</dd></div>`;
  ui.byId("pc-stats").innerHTML = [
    stat("POSTCARDS", ui.numeric(rows.length)),
    stat("PLACES", ui.numeric(places)),
    stat("FAVOURITES", ui.numeric(rows.filter((row) => row.favourite).length)),
    stat("FIRST", times.length ? eliteDate(Math.min(...times)) : "—"),
    stat("LATEST", times.length ? eliteDate(Math.max(...times)) : "—"),
  ].join("");
}

function drawRestore() {
  const panel = ui.byId("pc-restore");
  const older = rows.filter((row) => !row.editable && /^postcard - /i.test(row.file || "")).length;
  const missing = rows.filter((row) => row.needs_picture).length;
  const state = data.restore || {};
  if (state.running) {
    panel.hidden = false;
    panel.innerHTML = `<b>MAKING OLDER POSTCARDS EDITABLE</b><span>${ui.numeric(state.done || 0)} of ${ui.numeric(state.total || 0)} · ${ui.numeric(state.pictures || 0)} screenshots found so far</span>
      <i class="pc-progress"><i style="width:${Math.round(100 * (state.done || 0) / Math.max(1, state.total || 1))}%"></i></i>`;
    return;
  }
  panel.hidden = !older && !missing;
  if (!older && !missing) return;
  const last = state.total ? `<small>Last time: ${ui.numeric(state.done)} done, ${ui.numeric(state.pictures)} with their screenshot.</small>` : "";
  panel.innerHTML = older ? `<div><b>${ui.numeric(older)} OLDER POSTCARD${older === 1 ? "" : "S"}</b>
      <span>Saved before postcards could be edited. Void Compass can find each one's screenshot and journal entry so you can give it new words, a new look or its postmark.</span>${last}</div>
    <button type="button" class="primary" data-pc-restore-all>MAKE THEM EDITABLE</button>`
    : `<div><b>${ui.numeric(missing)} POSTCARD${missing === 1 ? "" : "S"} WITHOUT THEIR SCREENSHOT</b>
      <span>Made editable, but their screenshot wasn't found then. Void Compass can look again; your words and look stay as they are.</span>${last}</div>
    <button type="button" class="primary" data-pc-restore-all>FIND THEIR SCREENSHOTS</button>`;
}

// -- The viewer and the editor --------------------------------------------------
function open(id) {
  const row = rows.find((item) => item.id === id);
  if (!row) return;
  shown = row;
  ui.byId("pc-full").src = ui.apiUrl(`/media/postcard/${row.id}.png?v=${encodeURIComponent(row.at)}`);
  drawSide();
  ui.byId("pc-viewer").hidden = false;
}

function drawSide() {
  const row = shown;
  if (!row) return;
  ui.byId("pc-title").textContent = row.title;
  const when = row.taken || row.at;
  const recent = Date.now() / 1000 - Number(when) < 86400;
  ui.byId("pc-when").textContent = recent ? `${eliteDate(when)} · ${ago(when)}` : eliteDate(when);
  ui.byId("pc-badges").innerHTML = row.editable ? "<em>EDITABLE</em>" : "<em class=\"older\">OLDER</em>";
  ui.byId("pc-edit").hidden = !row.editable;
  ui.byId("pc-restore-one").hidden = row.editable && !row.needs_picture;
  ui.byId("pc-restore-one").textContent = row.needs_picture ? "FIND ITS SCREENSHOT" : "MAKE EDITABLE";
  ui.byId("pc-side-note").textContent = row.needs_picture
    ? "Its screenshot wasn't found when it was made editable. FIND ITS SCREENSHOT looks again, or pick a picture for it in the editor."
    : row.editable ? "" : "Saved before postcards could be edited. MAKE EDITABLE finds its screenshot and journal entry.";
  const fact = (label, value) => (value ? `<dt>${label}</dt><dd>${ui.escapeHtml(value)}</dd>` : "");
  ui.byId("pc-side-facts").innerHTML = fact("SYSTEM", row.system && row.system !== row.title ? row.system : "") + fact("REGION", row.region)
    + fact("NOTE", row.note) + fact("MADE", row.designed ? "In the editor" : "");
  showViewerStar(ui.byId("album-star"), row);
  const list = listed();
  const index = list.findIndex((item) => item.id === row.id);
  for (const button of ui.byId("pc-viewer").querySelectorAll("[data-pc-step]")) {
    const target = index + Number(button.dataset.pcStep);
    button.disabled = index < 0 || target < 0 || target >= list.length;
  }
}

function stepBy(step) {
  if (!shown || editorOpen()) return;
  const list = listed();
  const next = list[list.findIndex((item) => item.id === shown.id) + step];
  if (next) open(next.id);
}

function close() {
  shown = null;
  ui.byId("pc-viewer").hidden = true;
  ui.byId("pc-full").removeAttribute("src");
}

// -- The editor (5.6.3) ------------------------------------------------------------
// EDIT asks the deck for the card (its words, its looks, its saved design);
// the editor opens once that arrives.
async function editCard(id) {
  if (!id) return;
  editorWanted = id;
  if (!(await send("edit", {id}))) {
    editorWanted = "";
    ui.showToast("That postcard can't be edited yet: MAKE EDITABLE first");
  }
}

function renderEditor() {
  const editing = data.editing || {};
  if (!editing.id || editing.id !== editorWanted || editorOpen()) return;
  editorWanted = "";
  const id = editing.id;
  openEditor({
    ui, id, info: editing.info || {title: editing.title}, design: editing.design, looks: editing.looks, themes: data.themes || {},
    shots: editing.shots || [], photoUrl: editing.photo ? ui.apiUrl(`/media/postcard-photo/${id}.jpg?v=${Date.now()}`) : "",
    onSaved: (savedId, asNew) => {
      lastAlbumKey = "";
      if (shown) {
        const target = asNew ? savedId : shown.id;
        ui.byId("pc-full").src = ui.apiUrl(`/media/postcard/${target}.png?v=${Date.now()}`);
      }
    },
    onClose: () => send("edit_close"),
  });
}

// A screenshot made into a postcard on its page: straight into the editor.
function openNext() {
  const next = data.open_next || "";
  if (!next || next === openedNext) return;
  openedNext = next;
  send("opened");
  editCard(next);
}

// -- The studio ----------------------------------------------------------------
// One preview loading at a time (5.5.5): asked for again meanwhile, only the
// newest is fetched once it's in. Each one is a render on the deck's side.
function loadPreview(img, src) {
  if (!img || img.getAttribute("src") === src) return;
  if (img.dataset.loading === "1") {
    img.dataset.next = src;
    return;
  }
  img.dataset.loading = "1";
  img.dataset.next = "";
  const done = () => {
    img.dataset.loading = "";
    const next = img.dataset.next;
    img.dataset.next = "";
    if (next && next !== img.getAttribute("src")) loadPreview(img, next);
  };
  img.addEventListener("load", done, {once: true});
  img.addEventListener("error", done, {once: true});
  img.src = src;
}

function previewSrc() {
  return ui.apiUrl(drafting ? `/media/postcard-preview/draft-${previewTurn}.png`
    : `/media/postcard-preview/${encodeURIComponent(data.preview || "current")}.png`);
}

function showPreview() {
  loadPreview(ui.byId("pc-preview-img"), previewSrc());
  ui.byId("pc-preview-state").textContent = drafting ? "PREVIEW · THEME NOT SAVED YET" : "LIVE PREVIEW";
  ui.byId("pc-draft-reset").hidden = !drafting;
}

function themeParams() {
  const form = ui.byId("pc-theme");
  const value = (name) => form.querySelector(`[name="${name}"]`);
  const colour = (key) => (value(`use_${key}`).checked ? value(key).value : "");
  return {base: value("base").value, paper: colour("paper"), ink: colour("ink"), greet: colour("greet"),
    font: value("font").value, filter: value("filter").value, angle: value("angle").value,
    background: value("background").value, bg_colour: value("bg_colour").value, bg_image: value("bg_image")?.value || ""};
}

async function sendDraft() {
  if (!ui.byId("pc-theme")) return;
  if (!(await send("draft", {theme: themeParams()}))) return;
  drafting = true;
  previewTurn += 1;
  showPreview();
}

async function resetDraft() {
  window.clearTimeout(timers.draft);
  if (drafting) await send("draft_clear");
  drafting = false;
  themeBackground = "";
  lastStudioKey = "";
  if (ui) drawStudio();
}

function newTheme() {
  const form = ui.byId("pc-theme");
  if (!form) return;
  form.querySelector('[name="name"]').value = "";
  form.querySelector('[name="name"]').focus();
  ui.showToast("Name it, change what you like, then SAVE THEME");
}

function readBackground(input) {
  const file = input.files?.[0];
  if (!file) return;
  if (file.size > 6 * 1024 * 1024) return ui.showToast("That picture is too big (6 MB at most)");
  const reader = new FileReader();
  reader.onload = () => {
    themeBackground = String(reader.result || "");
    input.form.querySelector('[name="background"]').value = "image";
    ui.showToast("Picture ready: SAVE THEME to see it on the card");
  };
  reader.readAsDataURL(file);
}

async function saveTheme() {
  const form = ui.byId("pc-theme");
  const name = form.querySelector('[name="name"]').value.trim();
  if (!name) return ui.showToast("Give your theme a name");
  const params = themeParams();
  const done = await send("save_theme", {name, params, background_data: params.background === "image" ? themeBackground : ""});
  ui.showToast(done ? `Theme "${name}" saved and in use` : "That theme wasn't saved");
  if (done) await resetDraft();
  return done;
}

const swatch = (paper, ink, greet) => `<i class="pc-swatch"><i style="background:${paper}"></i><i style="background:${ink}"></i><i style="background:${greet}"></i></i>`;

function switchRow(key, label, detail, checked) {
  return `<label class="pc-switch"><input type="checkbox" data-postcard-setting="${key}"${checked ? " checked" : ""}>
    <i></i><span><b>${ui.escapeHtml(label)}</b><small>${ui.escapeHtml(detail)}</small></span></label>`;
}

function textRow(key, label, detail, value, limit, placeholder, extraClass = "", hidden = false) {
  return `<label class="pc-row ${extraClass}"${hidden ? " hidden" : ""}><span><b>${label}</b><small>${detail}</small></span>
    <span class="pc-own"><input type="text" maxlength="${limit}" data-postcard-setting="${key}" value="${ui.escapeHtml(value || "")}" placeholder="${ui.escapeHtml(placeholder)}"><em class="pc-saved" data-saved="${key}" aria-live="polite"></em></span></label>`;
}

function drawStudio() {
  const settings = data.settings || {};
  const panel = ui.byId("pc-controls");
  const key = JSON.stringify([settings, data.themes, data.preview]);
  const typing = panel.contains(document.activeElement) && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
  showPreview();
  if (key === lastStudioKey || typing || drafting) return;
  lastStudioKey = key;
  const esc = ui.escapeHtml;
  const current = settings.postcard_style || "polaroid";
  const themes = data.themes || {};
  const looks = [
    ...(data.styles || Object.keys(BASE_NAMES)).map((style) => [style, BASE_NAMES[style] || style, BASE_SWATCH[style] || BASE_SWATCH.polaroid, "LOOK"]),
    ...Object.entries(themes).map(([name, theme]) => {
      const base = BASE_SWATCH[theme.base] || BASE_SWATCH.polaroid;
      return [`theme:${name}`, name, [theme.paper || base[0], theme.ink || base[1], theme.greet || base[2]], `ON ${String(theme.base || "polaroid").toUpperCase()}`];
    }),
  ].map(([style, label, colours, kind]) => `<button type="button" class="pc-look${style === current ? " active" : ""}" data-postcard-style="${esc(style)}" aria-pressed="${style === current}">
      ${swatch(...colours)}<span><b>${esc(label)}</b><small>${esc(kind)}</small></span></button>`).join("");
  const mode = settings.postcard_note_mode || "watcher";
  const greeting = settings.postcard_greeting || "greetings";
  const option = (value, name, chosen) => `<option value="${value}"${value === chosen ? " selected" : ""}>${name}</option>`;
  const name = current.startsWith("theme:") ? current.slice(6) : "";
  const theme = themes[name] || {};
  const select = (field, names, value) => `<select name="${field}">${Object.entries(names).map(([id, label]) => option(id, label, value || "")).join("")}</select>`;
  const colour = (field, label, fallback) => `<label class="pc-colour"><span><input type="checkbox" name="use_${field}"${theme[field] ? " checked" : ""}>${label}</span>
    <input type="color" name="${field}" value="${esc(theme[field] || fallback)}"></label>`;
  panel.innerHTML = `
    <section class="pc-block"><h4>LOOK</h4><div class="pc-looks" role="group" aria-label="Look">${looks}</div></section>
    <section class="pc-block"><h4>THE WORDS</h4>
      <label class="pc-row"><span><b>Lettering</b><small>The words over the place's name.</small></span>
        <select data-postcard-setting="postcard_greeting">${[["greetings", "Greetings from…"], ["wish", "Wish you were here"], ["custom", "Your own words"], ["none", "None"]].map(([id, label]) => option(id, label, greeting)).join("")}</select></label>
      ${textRow("postcard_greeting_text", "Your lettering", "Up to 40 letters, over the name.", settings.postcard_greeting_text, 40, "Postcard from", "pc-greeting-own", greeting !== "custom")}
      <label class="pc-row"><span><b>The note</b><small>The handwritten line on the paper.</small></span>
        <select data-postcard-setting="postcard_note_mode">${[["watcher", "The Watcher's"], ["own", "Your own words"], ["none", "None"]].map(([id, label]) => option(id, label, mode)).join("")}</select></label>
      ${textRow("postcard_note_text", "Your words", "Up to 160 letters, on every postcard from now on.", settings.postcard_note_text, 160, "Wish you were here. The view is better than the fuel.", "pc-note-own", mode !== "own")}
      ${textRow("postcard_signature", "Signed", "Empty signs it CMDR and your name.", settings.postcard_signature, 40, "CMDR …", "pc-note-own", mode !== "own")}
      <div class="pc-switches">
        ${switchRow("postcard_postmark", "Postmark", "The system, the date and the time, stamped on the paper.", settings.postcard_postmark !== false)}
        ${switchRow("postcard_facts", "Journal facts", "What your scans say of the place: its kind, gravity, firsts, life, distance from Sol.", settings.postcard_facts)}
        ${switchRow("postcard_doing", "What you were doing", "In supercruise, landed, docked, on foot…", settings.postcard_doing)}
      </div>
      <div class="pc-sizes" role="group" aria-label="Text sizes">${TEXT_PARTS.map(([part, label, detail]) =>
        `<label><span><b>${label} size</b><small>${detail}</small></span><select data-postcard-setting="postcard_size_${part}">${sizeOptions(settings[`postcard_size_${part}`])}</select></label>`).join("")}</div></section>
    <section class="pc-block"><header><h4>${name ? `YOUR THEME · ${esc(name)}` : "YOUR OWN THEME"}</h4>
        ${name ? `<button type="button" data-theme-new>NEW THEME</button>` : ""}</header>
      <p class="pc-hint">Every change shows in the preview at once. SAVE THEME keeps it and uses it for the overlay and every postcard saved from now on.</p>
      <form class="pc-theme" id="pc-theme" autocomplete="off" onsubmit="return false">
        <label><span>Name</span><input name="name" maxlength="30" value="${esc(name)}" placeholder="My postcard"></label>
        <label><span>Built on</span>${select("base", BASE_NAMES, theme.base || (BASE_NAMES[current] ? current : "polaroid"))}</label>
        ${colour("paper", "Paper", "#f3ead2")}${colour("ink", "Ink", "#1c2333")}${colour("greet", "Lettering", "#ff7a18")}
        <label><span>Lettering font</span>${select("font", FONT_NAMES, theme.font)}</label>
        <label><span>Photo</span>${select("filter", FILTER_NAMES, theme.filter || "none")}</label>
        <label><span>Angle <small data-angle-out>${theme.angle ?? -1.2}°</small></span><input type="range" name="angle" min="-12" max="12" step="0.5" value="${theme.angle ?? -1.2}"></label>
        <label><span>Behind the card</span>${select("background", {none: "Nothing (see-through)", colour: "A colour", image: "A picture of mine"}, theme.background || "none")}</label>
        <label class="pc-colour"><span>Background colour</span><input type="color" name="bg_colour" value="${esc(theme.bg_colour || "#1b2433")}"></label>
        <label><span>Background picture ${theme.bg_image ? "<small>(one is set)</small>" : ""}</span><input type="file" name="bg_file" accept="image/png,image/jpeg,image/webp"></label>
        <input type="hidden" name="bg_image" value="${esc(theme.bg_image || "")}">
        <div class="pc-theme-actions"><button type="button" class="primary" data-theme-save>SAVE THEME</button>
          ${name ? `<button type="button" data-theme-delete="${esc(name)}">DELETE THEME</button>` : ""}</div>
      </form></section>`;
}

// -- Keeping -------------------------------------------------------------------
function drawKeeping() {
  const settings = data.settings || {};
  const panel = ui.byId("pc-keeping");
  const key = JSON.stringify([settings, data.folder, rows.length]);
  if (key === lastKeepingKey || (panel.contains(document.activeElement) && document.activeElement.type === "text")) return;
  lastKeepingKey = key;
  panel.innerHTML = `
    <section class="pc-block"><h4>SAVING</h4>
      <div class="pc-switches">
        ${switchRow("screenshot_postcards", "Save postcards as pictures", "Each new screenshot's postcard as a PNG, kept in this album. Made even with the Postcards overlay off.", settings.screenshot_postcards)}
        ${switchRow("screenshot_captions", "Caption files", "A text file beside each new screenshot: its postcard in words.", settings.screenshot_captions)}
      </div></section>
    <section class="pc-block"><h4>THE FOLDER</h4>
      <div class="pc-folder"><span><b>Postcard folder</b><small>Empty is the postcards folder in Void Compass's own folder.</small></span>
        <span class="pc-folder-row"><input type="text" aria-label="Postcard folder" data-postcard-setting="postcards_path" value="${ui.escapeHtml(settings.postcards_path || "")}" placeholder="${ui.escapeHtml(settings.default_folder || "postcards")}"><em class="pc-saved" data-saved="postcards_path" aria-live="polite"></em>
          <button type="button" data-postcard-browse>BROWSE</button><button type="button" data-postcard-default>DEFAULT</button><button type="button" data-album="open_folder">OPEN</button></span></div>
      <p class="pc-hint">${ui.numeric(rows.length)} postcard${rows.length === 1 ? "" : "s"} in ${ui.escapeHtml(data.folder || "the folder")}. Each one saved from 5.5.4 on keeps its words and photo in a hidden .cards folder beside it, so it can be edited later.</p></section>
    <section class="pc-block"><h4>THE OVERLAY</h4>
      <p class="pc-hint">How long a postcard stays on screen, its size and whether it shows the photo are the Postcards overlay's own options, in Overlay Studio.</p>
      <div><button type="button" data-page="overlay-studio">OVERLAY STUDIO</button></div></section>`;
}

const typed = {};

// A text box's words, saved once you pause (or at once, on Enter).
function saveText(field, wait) {
  const key = field.dataset.postcardSetting;
  const entry = typed[key] || (typed[key] = {saved: null});
  const note = field.parentElement.querySelector(`[data-saved="${key}"]`);
  const say = (text, tone = "") => { if (note) { note.textContent = text; note.dataset.tone = tone; } };
  if (field.value === entry.saved) return;
  say("Saving…");
  later(`text-${key}`, wait, async () => {
    const value = field.value;
    const done = await send("set", {key, value});
    if (done) entry.saved = value;
    say(done ? "Saved ✓" : "Not saved", done ? "ok" : "bad");
  });
}

export function renderPostcards(next = {}, deck) {
  ui = deck;
  const root = ui.byId("postcards-workspace");
  if (!root) return;
  if (!root.querySelector(".pc-page")) {
    shell(root);
    showTab(view.tab);
  }
  data = next;
  rows = Array.isArray(next.rows) ? next.rows : [];
  if (shown) shown = rows.find((row) => row.id === shown.id) || shown;
  drawStats();
  drawRestore();
  drawAlbum();
  drawStudio();
  drawKeeping();
  renderEditor();
  openNext();
  if (shown) drawSide();
}
