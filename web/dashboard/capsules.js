// Time capsules and On this day (5.5.3.7). Leave a note for a system: it
// stays sealed until you next jump in there, then the Watcher (or a notice)
// hands it back. On this day: where you were on this date in years gone by,
// with the postcards you took that day.

let lastKey = "";
let lastSettingsKey = "";
let here = "";

const WAIT_NAMES = {none: "Whenever I'm back", week: "Not before a week", month: "Not before a month", year: "Not before a year"};

function shell(root, ui) {
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="capsules-page">
    <div class="capsules-top">
      <form class="capsule-form" id="capsule-form" autocomplete="off">
        <h3>LEAVE A TIME CAPSULE</h3>
        <label><span>For the system</span>
          <span class="capsule-system-row"><input id="capsule-system" maxlength="100" placeholder="The system you're in">
            <button type="button" data-capsule-here>HERE</button></span></label>
        <label><span>Your note <small id="capsule-count">0 / 280</small></span>
          <textarea id="capsule-note" maxlength="280" rows="4" placeholder="Something for when you come back: what's worth landing on, what you were chasing, who you were flying with…"></textarea></label>
        <label><span>Opens</span>
          <select id="capsule-wait">${Object.entries(WAIT_NAMES).map(([key, name]) => `<option value="${key}">${name}</option>`).join("")}</select></label>
        <div class="capsule-form-foot">
          <p>Sealed until you next jump into that system: next week, or years from now. Sealed for later, it stays shut if you're back too soon.</p>
          <button type="submit" class="primary" id="capsule-seal">SEAL IT</button>
        </div>
      </form>
      <section class="capsule-today" aria-label="On this day"><h3 id="capsule-today-title">ON THIS DAY</h3><div id="capsule-days"></div></section>
    </div>
    <section class="capsule-list" aria-label="Sealed capsules"><h3 id="capsule-sealed-title">SEALED</h3><ol id="capsule-sealed"></ol></section>
    <section class="capsule-list opened" aria-label="Opened capsules"><h3 id="capsule-opened-title">OPENED</h3><ol id="capsule-opened"></ol></section>
    <details class="keepsake-settings" id="capsule-settings"><summary>TIME CAPSULE SETTINGS</summary><div id="capsule-settings-body"></div></details>
  </div>`;
  root.addEventListener("change", async (event) => {
    const field = event.target.closest("[data-capsule-setting]");
    if (!field) return;
    const value = field.type === "checkbox" ? field.checked : field.value;
    lastSettingsKey = "";
    if (!(await ui.command("workspace", {page: "capsules", operation: "set", key: field.dataset.capsuleSetting, value}))) {
      ui.showToast("That setting wasn't saved");
    }
  });
  const note = ui.byId("capsule-note");
  note.addEventListener("input", () => {
    ui.byId("capsule-count").textContent = `${note.value.length} / 280`;
  });
  ui.byId("capsule-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = note.value.trim();
    const system = ui.byId("capsule-system").value.trim() || here;
    if (!text) {
      ui.showToast("Write something to seal");
      return;
    }
    if (!system) {
      ui.showToast("Which system is it for?");
      return;
    }
    const seal = ui.byId("capsule-seal");
    seal.disabled = true;
    try {
      const wait = ui.byId("capsule-wait").value;
      if (await ui.command("workspace", {page: "capsules", operation: "leave", system, note: text, wait})) {
        note.value = "";
        ui.byId("capsule-system").value = "";
        ui.byId("capsule-count").textContent = "0 / 280";
        ui.byId("capsule-wait").value = "none";
        ui.showToast(`Sealed for ${system}`);
      } else {
        ui.showToast("That capsule wasn't sealed");
      }
    } finally {
      seal.disabled = false;
    }
  });
  root.addEventListener("click", async (event) => {
    if (event.target.closest("[data-capsule-here]")) {
      ui.byId("capsule-system").value = here;
      return;
    }
    const remove = event.target.closest("[data-capsule-remove]");
    if (!remove) return;
    // Two steps, in place: REMOVE, then SURE?
    if (!remove.dataset.armed) {
      remove.dataset.armed = "1";
      remove.textContent = "SURE?";
      setTimeout(() => {
        if (remove.isConnected) {
          delete remove.dataset.armed;
          remove.textContent = "REMOVE";
        }
      }, 3000);
      return;
    }
    remove.disabled = true;
    if (!(await ui.command("workspace", {page: "capsules", operation: "remove", id: remove.dataset.capsuleRemove}))) {
      remove.disabled = false;
      ui.showToast("That capsule wasn't removed");
    }
  });
}

function day(row, ui) {
  const cards = (row.postcards || []).map((card) =>
    `<img src="${ui.apiUrl(`/media/postcard-thumb/${encodeURIComponent(card.id)}.jpg`)}" alt="" title="${ui.escapeHtml(card.title)}" loading="lazy">`).join("");
  const moved = row.last && row.last !== row.first ? ` → ${ui.escapeHtml(row.last)}` : "";
  const flown = row.jumps ? ` · ${ui.numeric(row.jumps)} jump${row.jumps === 1 ? "" : "s"} · ${ui.numeric(row.distance)} ly` : "";
  return `<article class="capsule-day"><small>${ui.escapeHtml(String(row.ago || "").toUpperCase())} · ${ui.escapeHtml(row.date.slice(0, 4))}</small>
    <b>${ui.escapeHtml(row.first)}</b><span>${moved}${flown}</span>${cards ? `<div class="capsule-day-cards">${cards}</div>` : ""}</article>`;
}

function capsule(row, ui, opened) {
  const from = row.left_from && row.left_from.toLowerCase() !== row.system.toLowerCase() ? ` from ${ui.escapeHtml(row.left_from)}` : "";
  const meta = opened ? `Waited ${ui.escapeHtml(row.waited)} · left ${ui.escapeHtml(row.left_ago)} ago${from}`
    : `Left ${ui.escapeHtml(row.left_ago)} ago${from}${row.opens_in ? ` · <em>opens in ${ui.escapeHtml(row.opens_in)}</em>` : ""}`;
  return `<li class="capsule${opened ? " opened" : ""}"><div><b>${ui.escapeHtml(row.system)}</b><small>${meta}</small></div>
    <p class="capsule-note" tabindex="0" title="${opened ? "" : "Sealed: hover to peek"}">${ui.escapeHtml(row.note)}</p>
    <button type="button" data-capsule-remove="${ui.escapeHtml(row.id)}">REMOVE</button></li>`;
}

function choice(ui, key, label, detail, value, options) {
  return `<label class="keepsake-field"><span><b>${ui.escapeHtml(label)}</b><small>${ui.escapeHtml(detail)}</small></span>
    <select data-capsule-setting="${key}">${options.map(([option, name]) => `<option value="${option}"${String(option) === String(value) ? " selected" : ""}>${ui.escapeHtml(name)}</option>`).join("")}</select></label>`;
}

function toggle(ui, key, label, detail, checked) {
  return `<label class="keepsake-switch"><input type="checkbox" data-capsule-setting="${key}"${checked ? " checked" : ""}>
    <span><b>${ui.escapeHtml(label)}</b><small>${ui.escapeHtml(detail)}</small></span></label>`;
}

function renderSettings(data, ui) {
  const settings = data.settings || {};
  ui.byId("capsules-workspace").querySelector(".capsules-page").classList.toggle("unblurred", settings.capsule_blur_sealed === false);
  const key = JSON.stringify([settings, data.minimap]);
  if (key === lastSettingsKey) return;
  lastSettingsKey = key;
  ui.byId("capsule-settings-body").innerHTML = `
    ${choice(ui, "capsule_delivery", "Hand capsules back", "Who gives you your note when you arrive.", settings.capsule_delivery,
      [["both", "The Watcher, or a notice if it's quiet"], ["notice", "A notice only"], ["watcher", "The Watcher only"]])}
    ${choice(ui, "capsule_notice_s", "Notice stays", "How long a capsule's notice stays on screen.", settings.capsule_notice_s,
      [[10, "10 seconds"], [25, "25 seconds"], [45, "45 seconds"], [60, "A minute"]])}
    ${toggle(ui, "capsule_open_on_login", "Open when I log in there", "Not only when you jump in: logging in at the system opens its capsules too.", settings.capsule_open_on_login)}
    ${toggle(ui, "capsule_blur_sealed", "Blur sealed notes", "Keep the surprise: sealed notes stay blurred here until you hover to peek.", settings.capsule_blur_sealed)}
    ${toggle(ui, "on_this_day_watcher", "The Watcher remembers this day", "On your first jump of the day, it may tell you where you were on this date.", settings.on_this_day_watcher)}
    <p class="keepsake-hint">Sealed capsules ${data.minimap ? "show" : "can show"} as small hourglasses on the Galaxy Minimap (its Time capsules switch, in Overlay Studio).</p>`;
}

export function renderCapsules(data = {}, ui) {
  const root = ui.byId("capsules-workspace");
  if (!root) return;
  if (!root.querySelector(".capsules-page")) shell(root, ui);
  here = data.here || "";
  ui.byId("capsule-system").placeholder = here ? `${here} (where you are)` : "A system's name";
  renderSettings(data, ui);
  const sealed = data.sealed || [], opened = data.opened || [], days = data.on_this_day || [];
  const key = JSON.stringify([sealed, opened, days]);
  if (key === lastKey) return;
  lastKey = key;
  ui.byId("capsule-today-title").textContent = `ON THIS DAY · ${String(data.today || "").toUpperCase()}`;
  ui.byId("capsule-days").innerHTML = days.length ? days.map((row) => day(row, ui)).join("")
    : `<p class="capsule-empty">Nowhere on this date yet. Fly today, and next year it'll be here.</p>`;
  ui.byId("capsule-sealed-title").textContent = `SEALED · ${sealed.length}`;
  ui.byId("capsule-sealed").innerHTML = sealed.length ? sealed.map((row) => capsule(row, ui, false)).join("")
    : `<li class="capsule-empty">No capsules waiting. Leave one above for a place you'll come back to.</li>`;
  ui.byId("capsule-opened-title").textContent = `OPENED · ${opened.length}`;
  ui.byId("capsule-opened").innerHTML = opened.length ? opened.map((row) => capsule(row, ui, true)).join("")
    : `<li class="capsule-empty">None opened yet.</li>`;
}
