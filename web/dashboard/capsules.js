// Time capsules and On this day (5.5.3.7; the vault, and sharing, 5.5.4).
// Leave a note for a system, or for a station or body in it: it stays sealed
// until you next get there, then the Watcher (or a notice) hands it back.
// Share capsules with other commanders without any server: as a code to
// paste anywhere, or a .vccapsule file. What they send you stays unread until
// you arrive. On this day: where you were on this date in years gone by.

let lastKey = "";
let lastSettingsKey = "";
let here = "";
const chosen = new Set();

const WAIT_NAMES = {none: "Whenever I'm back", week: "Not before a week", month: "Not before a month",
  six_months: "Not before six months", year: "Not before a year", two_years: "Not before two years", date: "On a date…"};
const KIND_NAMES = {note: ["✉", "Note"], reminder: ["⏰", "Reminder"], warning: ["⚠", "Warning"], memory: ["★", "Memory"],
  greeting: ["✦", "Greeting"]};

function shell(root, ui) {
  root.classList.remove("loading-panel");
  const kinds = Object.entries(KIND_NAMES).map(([key, [icon, name]], index) =>
    `<label class="capsule-kind"><input type="radio" name="capsule-kind" value="${key}"${index ? "" : " checked"}><span><i>${icon}</i>${name}</span></label>`).join("");
  root.innerHTML = `<div class="capsules-page">
    <header class="capsule-vault" aria-label="The vault">
      <div class="capsule-vault-mark" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="capsule-vault-words"><h3>THE VAULT</h3><p id="capsule-vault-line"></p></div>
      <dl class="capsule-vault-figures" id="capsule-vault-figures"></dl>
    </header>
    <div class="capsule-side">
      <form class="capsule-form" id="capsule-form" autocomplete="off">
        <h3>SEAL A TIME CAPSULE</h3>
        <div class="capsule-kinds" role="radiogroup" aria-label="What kind of note">${kinds}</div>
        <label><span>For the system</span>
          <span class="capsule-system-row"><input id="capsule-system" maxlength="100" placeholder="The system you're in">
            <button type="button" data-capsule-here>HERE</button></span></label>
        <label><span>Open at <small>optional</small></span>
          <input id="capsule-target" maxlength="100" placeholder="Anywhere in the system, or a station or body: Jameson Memorial, A 1…"></label>
        <label><span>Your note <small id="capsule-count">0 / 280</small></span>
          <textarea id="capsule-note" maxlength="280" rows="4" placeholder="Something for when you come back: what's worth landing on, what you were chasing, who you were flying with…"></textarea></label>
        <div class="capsule-opens">
          <label><span>Opens</span>
            <select id="capsule-wait">${Object.entries(WAIT_NAMES).map(([key, name]) => `<option value="${key}">${name}</option>`).join("")}</select></label>
          <label id="capsule-date-row" hidden><span>Not before</span><input type="date" id="capsule-date"></label>
        </div>
        <div class="capsule-form-foot">
          <p>Sealed until you next get there: jump in, or dock or land where it's for. Sealed for later, it stays shut if you're back too soon.</p>
          <button type="submit" class="primary" id="capsule-seal">SEAL IT</button>
        </div>
      </form>
      <section class="capsule-receive" aria-label="Receive capsules">
        <h3>RECEIVE A CAPSULE</h3>
        <p class="capsule-hint">Another commander sent you a capsule? Paste their code below, or choose or drop the .vccapsule file they gave you. You'll see what's inside the pack first; once you receive it, each capsule waits, sealed, until you reach the place it was left for.</p>
        <div class="capsule-drop" id="capsule-drop">
          <textarea id="capsule-code" rows="3" placeholder="Paste a capsule code (VCCAP1-…), or a whole message with one in it"></textarea>
          <div class="capsule-receive-actions">
            <button type="button" data-capsule-preview>CHECK THE CODE</button>
            <label class="capsule-file"><input type="file" id="capsule-file" accept=".vccapsule,.json,application/json">CHOOSE A FILE</label>
            <small>or drop a .vccapsule file here</small>
          </div>
        </div>
        <div class="capsule-preview" id="capsule-preview" hidden></div>
      </section>
      <section class="capsule-today" aria-label="On this day"><h3 id="capsule-today-title">ON THIS DAY</h3><div id="capsule-days"></div></section>
      <details class="keepsake-settings" id="capsule-settings"><summary>TIME CAPSULE SETTINGS</summary><div id="capsule-settings-body"></div></details>
    </div>
    <div class="capsule-main">
    <div class="capsule-share" id="capsule-share" hidden></div>
    <section class="capsule-list" aria-label="Your sealed capsules">
      <header><h3 id="capsule-sealed-title">SEALED</h3>
        <div class="capsule-tools"><button type="button" data-capsule-all>SELECT ALL</button>
          <button type="button" data-capsule-share-chosen disabled>SHARE AS A CODE</button>
          <button type="button" data-capsule-export-chosen disabled>SAVE AS A FILE</button>
          <button type="button" data-capsule-folder>CAPSULE FOLDER</button></div></header>
      <ol id="capsule-sealed"></ol>
    </section>
    <section class="capsule-list received" aria-label="From other commanders"><header><h3 id="capsule-received-title">FROM OTHER COMMANDERS</h3></header><ol id="capsule-received"></ol></section>
    <section class="capsule-list opened" aria-label="Opened capsules"><header><h3 id="capsule-opened-title">OPENED</h3></header><ol id="capsule-opened"></ol></section>
    </div>
  </div>`;

  const send = (operation, extra = {}) => ui.command("workspace", {page: "capsules", operation, ...extra});
  root.addEventListener("change", async (event) => {
    if (event.target.id === "capsule-wait") {
      ui.byId("capsule-date-row").hidden = event.target.value !== "date";
      return;
    }
    const pick = event.target.closest("[data-capsule-choose]");
    if (pick) {
      if (pick.checked) chosen.add(pick.dataset.capsuleChoose); else chosen.delete(pick.dataset.capsuleChoose);
      updateTools(ui);
      return;
    }
    if (event.target.id === "capsule-file") {
      readFile(event.target.files?.[0], ui, send);
      event.target.value = "";
      return;
    }
    const field = event.target.closest("[data-capsule-setting]");
    if (!field) return;
    const value = field.type === "checkbox" ? field.checked : field.value;
    lastSettingsKey = "";
    if (!(await send("set", {key: field.dataset.capsuleSetting, value}))) ui.showToast("That setting wasn't saved");
  });
  const note = ui.byId("capsule-note");
  note.addEventListener("input", () => { ui.byId("capsule-count").textContent = `${note.value.length} / 280`; });
  ui.byId("capsule-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = note.value.trim();
    const system = ui.byId("capsule-system").value.trim() || here;
    const wait = ui.byId("capsule-wait").value;
    const opensOn = ui.byId("capsule-date").value;
    if (!text) return ui.showToast("Write something to seal");
    if (!system) return ui.showToast("Which system is it for?");
    if (wait === "date" && !opensOn) return ui.showToast("Choose the day it may open");
    const seal = ui.byId("capsule-seal");
    seal.disabled = true;
    try {
      const kind = root.querySelector('input[name="capsule-kind"]:checked')?.value || "note";
      const target = ui.byId("capsule-target").value.trim();
      if (await send("leave", {system, note: text, wait, kind, target, opens_on: opensOn})) {
        note.value = "";
        ui.byId("capsule-system").value = "";
        ui.byId("capsule-target").value = "";
        ui.byId("capsule-count").textContent = "0 / 280";
        ui.byId("capsule-wait").value = "none";
        ui.byId("capsule-date-row").hidden = true;
        ui.showToast(`Sealed for ${target ? `${target}, ` : ""}${system}`);
      } else {
        ui.showToast("That capsule wasn't sealed");
      }
    } finally {
      seal.disabled = false;
    }
  });
  // A file dropped anywhere on the receive panel.
  const drop = ui.byId("capsule-drop");
  drop.addEventListener("dragover", (event) => { event.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (event) => {
    event.preventDefault();
    drop.classList.remove("over");
    readFile(event.dataTransfer?.files?.[0], ui, send);
  });
  root.addEventListener("click", async (event) => {
    const target = event.target;
    if (target.closest("[data-capsule-here]")) {
      ui.byId("capsule-system").value = here;
      return;
    }
    if (target.closest("[data-capsule-preview]")) {
      const text = ui.byId("capsule-code").value.trim();
      if (!text) return ui.showToast("Paste a capsule code first");
      await send("preview", {text});
      return;
    }
    if (target.closest("[data-capsule-receive]")) {
      const text = ui.byId("capsule-code").value.trim() || pendingFile;
      if (await send("receive", {text})) {
        ui.byId("capsule-code").value = "";
        pendingFile = "";
      }
      return;
    }
    if (target.closest("[data-capsule-preview-close]")) {
      pendingFile = "";
      await send("clear_preview");
      return;
    }
    if (target.closest("[data-capsule-all]")) {
      const boxes = [...root.querySelectorAll("[data-capsule-choose]")];
      const all = boxes.length && boxes.every((box) => box.checked);
      boxes.forEach((box) => { box.checked = !all; if (!all) chosen.add(box.dataset.capsuleChoose); else chosen.delete(box.dataset.capsuleChoose); });
      updateTools(ui);
      return;
    }
    const shareOne = target.closest("[data-capsule-share]");
    if (shareOne || target.closest("[data-capsule-share-chosen]")) {
      const ids = shareOne ? [shareOne.dataset.capsuleShare] : [...chosen];
      if (await send("share", {ids})) ui.showToast("Capsule code copied: paste it to whoever it's for");
      return;
    }
    const exportOne = target.closest("[data-capsule-export]");
    if (exportOne || target.closest("[data-capsule-export-chosen]")) {
      const ids = exportOne ? [exportOne.dataset.capsuleExport] : [...chosen];
      if (await send("export", {ids})) ui.showToast("Saved in the capsule folder");
      return;
    }
    if (target.closest("[data-capsule-folder]")) {
      await send("open_folder");
      return;
    }
    if (target.closest("[data-capsule-copy]")) {
      if (await send("copy_share")) ui.showToast("Copied again");
      return;
    }
    if (target.closest("[data-capsule-share-close]")) {
      await send("clear_share");
      return;
    }
    const reseal = target.closest("[data-capsule-reseal]");
    if (reseal) {
      const wait = reseal.parentElement.querySelector("select")?.value || "month";
      if (await send("reseal", {id: reseal.dataset.capsuleReseal, wait})) ui.showToast("Sealed again");
      return;
    }
    const remove = target.closest("[data-capsule-remove]");
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
    chosen.delete(remove.dataset.capsuleRemove);
    if (!(await send("remove", {id: remove.dataset.capsuleRemove}))) {
      remove.disabled = false;
      ui.showToast("That capsule wasn't removed");
    }
  });
}

// A chosen file's text, checked first (a preview), received on RECEIVE.
let pendingFile = "";
function readFile(file, ui, send) {
  if (!file) return;
  if (file.size > 200000) {
    ui.showToast("That file is too big to be a capsule file");
    return;
  }
  const reader = new FileReader();
  reader.onload = async () => {
    pendingFile = String(reader.result || "");
    ui.byId("capsule-code").value = "";
    await send("preview", {text: pendingFile});
  };
  reader.readAsText(file);
}

function updateTools(ui) {
  const none = chosen.size === 0;
  const root = ui.byId("capsules-workspace");
  root.querySelector("[data-capsule-share-chosen]").disabled = none;
  root.querySelector("[data-capsule-export-chosen]").disabled = none;
  root.querySelector("[data-capsule-share-chosen]").textContent = none ? "SHARE AS A CODE" : `SHARE ${chosen.size} AS A CODE`;
  root.querySelector("[data-capsule-export-chosen]").textContent = none ? "SAVE AS A FILE" : `SAVE ${chosen.size} AS A FILE`;
}

function day(row, ui) {
  const cards = (row.postcards || []).map((card) =>
    `<img src="${ui.apiUrl(`/media/postcard-thumb/${encodeURIComponent(card.id)}.jpg`)}" alt="" title="${ui.escapeHtml(card.title)}" loading="lazy">`).join("");
  const moved = row.last && row.last !== row.first ? ` → ${ui.escapeHtml(row.last)}` : "";
  const flown = row.jumps ? ` · ${ui.numeric(row.jumps)} jump${row.jumps === 1 ? "" : "s"} · ${ui.numeric(row.distance)} ly` : "";
  return `<article class="capsule-day"><small>${ui.escapeHtml(String(row.ago || "").toUpperCase())} · ${ui.escapeHtml(row.date.slice(0, 4))}</small>
    <b>${ui.escapeHtml(row.first)}</b><span>${moved}${flown}</span>${cards ? `<div class="capsule-day-cards">${cards}</div>` : ""}</article>`;
}

const RESEAL = `<select aria-label="Seal again for"><option value="none">Next visit</option><option value="month">A month</option>
  <option value="six_months">Six months</option><option value="year" selected>A year</option></select>`;

function capsule(row, ui, mode) {
  const [icon, kindName] = KIND_NAMES[row.kind] || KIND_NAMES.note;
  const place = row.target ? `<em class="capsule-place">at ${ui.escapeHtml(row.target)}</em>` : "";
  const from = row.left_from && row.left_from.toLowerCase() !== row.system.toLowerCase() ? ` from ${ui.escapeHtml(row.left_from)}` : "";
  const sender = row.sender ? `CMDR ${ui.escapeHtml(row.sender)}` : "another commander";
  let meta;
  if (mode === "opened") meta = `Waited ${ui.escapeHtml(row.waited)} · left ${ui.escapeHtml(row.left_ago)} ago${row.shared ? ` by ${sender}` : from}`;
  else if (mode === "received") meta = `From ${sender} · left ${ui.escapeHtml(row.left_ago)} ago`;
  else meta = `Left ${ui.escapeHtml(row.left_ago)} ago${from}`;
  const waiting = row.opens_in ? `<span class="capsule-countdown" title="Not before ${ui.escapeHtml(row.opens_on || "")}">OPENS IN ${ui.escapeHtml(row.opens_in.toUpperCase())}</span>` : "";
  const note = row.hidden
    ? `<p class="capsule-note hidden-note">Sealed by ${sender}. You'll read it when you get there.</p>`
    : `<p class="capsule-note" tabindex="0" title="${mode === "sealed" ? "Sealed: hover to peek" : ""}">${ui.escapeHtml(row.note)}</p>`;
  const choose = mode === "sealed"
    ? `<label class="capsule-choose" title="Choose for sharing"><input type="checkbox" data-capsule-choose="${ui.escapeHtml(row.id)}"${chosen.has(row.id) ? " checked" : ""}></label>` : "";
  const actions = [
    mode === "sealed" ? `<button type="button" data-capsule-share="${ui.escapeHtml(row.id)}">SHARE</button><button type="button" data-capsule-export="${ui.escapeHtml(row.id)}">FILE</button>` : "",
    mode === "opened" && !row.shared ? `<span class="capsule-reseal">${RESEAL}<button type="button" data-capsule-reseal="${ui.escapeHtml(row.id)}">SEAL AGAIN</button></span>` : "",
    `<button type="button" data-capsule-remove="${ui.escapeHtml(row.id)}">REMOVE</button>`,
  ].join("");
  return `<li class="capsule ${mode} kind-${ui.escapeHtml(row.kind || "note")}">${choose}
    <div class="capsule-seal" aria-hidden="true" title="${kindName}">${icon}</div>
    <div class="capsule-head"><b>${ui.escapeHtml(row.system)}</b>${place}<small>${meta}</small>${waiting}</div>
    ${note}<div class="capsule-actions">${actions}</div></li>`;
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
  const key = JSON.stringify([settings, data.minimap, data.sender]);
  if (key === lastSettingsKey) return;
  lastSettingsKey = key;
  ui.byId("capsule-settings-body").innerHTML = `
    ${choice(ui, "capsule_delivery", "Hand capsules back", "Who gives you your note when you arrive.", settings.capsule_delivery,
      [["both", "The Watcher, or a notice if it's quiet"], ["notice", "A notice only"], ["watcher", "The Watcher only"]])}
    ${choice(ui, "capsule_notice_s", "Notice stays", "How long a capsule's notice stays on screen.", settings.capsule_notice_s,
      [[10, "10 seconds"], [25, "25 seconds"], [45, "45 seconds"], [60, "A minute"]])}
    ${toggle(ui, "capsule_open_on_login", "Open when I log in there", "Not only when you jump in: logging in at the system opens its capsules too.", settings.capsule_open_on_login)}
    ${toggle(ui, "capsule_blur_sealed", "Blur sealed notes", "Keep the surprise: sealed notes stay blurred here until you hover to peek.", settings.capsule_blur_sealed)}
    ${toggle(ui, "capsule_sign_shares", "Sign what I share", `Capsules you share say they're from you${data.sender ? ` (CMDR ${data.sender})` : ""}. Off, they arrive unsigned.`, settings.capsule_sign_shares)}
    ${toggle(ui, "capsule_hide_received", "Keep shared capsules unread", "A capsule another commander sends you can't be read here until you get to where it was left.", settings.capsule_hide_received)}
    ${toggle(ui, "on_this_day_watcher", "The Watcher remembers this day", "On your first jump of the day, it may tell you where you were on this date.", settings.on_this_day_watcher)}
    <p class="keepsake-hint">Sealed capsules ${data.minimap ? "show" : "can show"} as small hourglasses on the Galaxy Minimap (its Time capsules switch, in Overlay Studio).</p>`;
}

function renderVault(data, ui) {
  const vault = data.vault || {};
  const figure = (label, value) => `<div><dt>${label}</dt><dd>${ui.escapeHtml(String(value))}</dd></div>`;
  ui.byId("capsule-vault-figures").innerHTML = [
    figure("SEALED", vault.sealed ?? 0), figure("FROM OTHERS", vault.received ?? 0), figure("OPENED", vault.opened ?? 0),
    figure("OLDEST WAITING", vault.oldest || "—"), figure("LONGEST WAIT", vault.longest_wait || "—"),
  ].join("");
  const total = Number(vault.sealed || 0) + Number(vault.received || 0);
  ui.byId("capsule-vault-line").textContent = total
    ? `${total} capsule${total === 1 ? "" : "s"} out there in the dark, waiting for you to come back.`
    : "Nothing sealed yet. Leave a note for a place you'll return to, months or years from now.";
}

function renderShare(data, ui) {
  const box = ui.byId("capsule-share");
  const share = data.share || {};
  box.hidden = !(share.code || share.file || share.error);
  if (box.hidden) return;
  if (share.error) {
    box.innerHTML = `<p class="capsule-error">${ui.escapeHtml(share.error)}</p><button type="button" data-capsule-share-close>OK</button>`;
    return;
  }
  if (share.file) {
    box.innerHTML = `<div><h3>SAVED AS A FILE</h3><p>${ui.numeric(share.count)} capsule${share.count === 1 ? "" : "s"} in <b>${ui.escapeHtml(share.name)}</b>. Send the file to whoever it's for; they choose or drop it on their Time Capsules page.</p></div>
      <div class="capsule-share-actions"><button type="button" data-capsule-folder>OPEN THE FOLDER</button><button type="button" data-capsule-share-close>DONE</button></div>`;
    return;
  }
  box.innerHTML = `<div><h3>${share.count === 1 ? "A CAPSULE CODE" : `A PACK OF ${ui.numeric(share.count)} CAPSULES`}</h3>
      <p>${share.copied ? "Copied, with a line explaining it: paste it into Discord, in-game chat, anywhere." : "Copy it and pass it on: Discord, in-game chat, anywhere."}</p>
      <textarea readonly rows="2">${ui.escapeHtml(share.code)}</textarea></div>
    <div class="capsule-share-actions"><button type="button" class="primary" data-capsule-copy>COPY AGAIN</button><button type="button" data-capsule-share-close>DONE</button></div>`;
}

function renderPreview(data, ui) {
  const box = ui.byId("capsule-preview");
  const preview = data.preview || {};
  box.hidden = !Object.keys(preview).length;
  if (box.hidden) return;
  if (preview.problem) {
    box.innerHTML = `<p class="capsule-error">${ui.escapeHtml(preview.problem)}</p><button type="button" data-capsule-preview-close>OK</button>`;
    return;
  }
  if (preview.received !== undefined) {
    const skipped = preview.skipped ? ` ${ui.numeric(preview.skipped)} you already had.` : "";
    box.innerHTML = `<p><b>${preview.received ? `${ui.numeric(preview.received)} capsule${preview.received === 1 ? "" : "s"} received.` : "Nothing new."}</b>${skipped} They wait in FROM OTHER COMMANDERS below.</p><button type="button" data-capsule-preview-close>OK</button>`;
    return;
  }
  const from = preview.senders?.length ? `from CMDR ${preview.senders.map(ui.escapeHtml).join(", CMDR ")}` : "unsigned";
  const systems = (preview.systems || []).map(ui.escapeHtml).join(", ");
  const extras = [preview.targets ? `${ui.numeric(preview.targets)} wait for a station or body` : "",
    preview.waiting ? `${ui.numeric(preview.waiting)} can't open yet` : ""].filter(Boolean).join(" · ");
  box.innerHTML = `<p><b>${ui.numeric(preview.count)} capsule${preview.count === 1 ? "" : "s"}</b> ${from}, for ${systems}.${extras ? ` ${extras}.` : ""}</p>
    <div class="capsule-share-actions"><button type="button" class="primary" data-capsule-receive>RECEIVE</button><button type="button" data-capsule-preview-close>CANCEL</button></div>`;
}

export function renderCapsules(data = {}, ui) {
  const root = ui.byId("capsules-workspace");
  if (!root) return;
  if (!root.querySelector(".capsules-page")) shell(root, ui);
  here = data.here || "";
  ui.byId("capsule-system").placeholder = here ? `${here} (where you are)` : "A system's name";
  renderSettings(data, ui);
  renderVault(data, ui);
  renderShare(data, ui);
  renderPreview(data, ui);
  const sealed = data.sealed || [], opened = data.opened || [], received = data.received || [], days = data.on_this_day || [];
  const key = JSON.stringify([sealed, opened, received, days]);
  if (key === lastKey) return;
  lastKey = key;
  for (const id of [...chosen]) if (!sealed.some((row) => row.id === id)) chosen.delete(id);
  ui.byId("capsule-today-title").textContent = `ON THIS DAY · ${String(data.today || "").toUpperCase()}`;
  ui.byId("capsule-days").innerHTML = days.length ? days.map((row) => day(row, ui)).join("")
    : `<p class="capsule-empty">Nowhere on this date yet. Fly today, and next year it'll be here.</p>`;
  ui.byId("capsule-sealed-title").textContent = `SEALED · ${sealed.length}`;
  ui.byId("capsule-sealed").innerHTML = sealed.length ? sealed.map((row) => capsule(row, ui, "sealed")).join("")
    : `<li class="capsule-empty">No capsules waiting. Seal one above for a place you'll come back to.</li>`;
  ui.byId("capsule-received-title").textContent = `FROM OTHER COMMANDERS · ${received.length}`;
  ui.byId("capsule-received").innerHTML = received.length ? received.map((row) => capsule(row, ui, "received")).join("")
    : `<li class="capsule-empty">None yet. When a commander gives you a capsule code or file, receive it above.</li>`;
  ui.byId("capsule-opened-title").textContent = `OPENED · ${opened.length}`;
  ui.byId("capsule-opened").innerHTML = opened.length ? opened.map((row) => capsule(row, ui, "opened")).join("")
    : `<li class="capsule-empty">None opened yet.</li>`;
  updateTools(ui);
}
