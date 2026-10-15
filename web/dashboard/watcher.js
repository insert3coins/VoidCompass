// The Watcher's page (5.5.3.2): its eye, live; everything it has said; what
// it remembers of the commander (records, places, the bond grown over
// sessions together); and a poke.
//
// The page is built once and then updated in place, so the orb's canvas
// (and its life) survives every refresh. While the page is hidden the canvas
// has no size and the orb stops drawing.

const NATURES = {weary: "Depressed", curious: "Curious", stoic: "Stoic", nervous: "Nervous"};
const FREQUENCIES = {off: "Off", rare: "Rare", occasional: "Occasional", chatty: "Chatty"};
const MOOD_LABELS = {pleased: "PLEASED", wary: "WARY", curious: "CURIOUS", downcast: "DOWNCAST"};

let orb = null;
let lastLogKey = "";

function ago(seconds) {
  const age = Math.max(0, Date.now() / 1000 - Number(seconds || 0));
  if (age < 60) return "just now";
  if (age < 3600) return `${Math.round(age / 60)} min ago`;
  if (age < 86400) return `${Math.round(age / 3600)} h ago`;
  return new Date(Number(seconds) * 1000).toLocaleDateString([], {day: "numeric", month: "short"});
}

// A floating card for anything on the page with a data-tip ("Title|line|line"):
// how to find an echo, what a chapter still waits for (5.5.3.9).
function tips(root) {
  const card = document.createElement("div");
  card.className = "watcher-tip";
  card.hidden = true;
  document.body.append(card);
  const show = (target) => {
    const [title, ...lines] = String(target.dataset.tip || "").split("|");
    card.replaceChildren(Object.assign(document.createElement("b"), {textContent: title}),
      ...lines.map((line) => Object.assign(document.createElement("span"), {textContent: line})));
    card.hidden = false;
    const box = target.getBoundingClientRect();
    const width = Math.min(300, window.innerWidth - 16);
    card.style.width = `${width}px`;
    const left = Math.min(window.innerWidth - width - 8, Math.max(8, box.right + 10));
    const fitsRight = box.right + 10 + width <= window.innerWidth - 8;
    card.style.left = `${fitsRight ? left : Math.max(8, box.left - width - 10)}px`;
    card.style.top = `${Math.max(8, Math.min(window.innerHeight - card.offsetHeight - 8, box.top))}px`;
  };
  const hide = () => { card.hidden = true; };
  root.addEventListener("mouseover", (event) => {
    const target = event.target.closest("[data-tip]");
    if (target) show(target); else hide();
  });
  root.addEventListener("mouseleave", hide);
  root.addEventListener("focusin", (event) => {
    const target = event.target.closest("[data-tip]");
    if (target) show(target);
  });
  root.addEventListener("focusout", hide);
  window.addEventListener("scroll", hide, true);
}

function shell(root, ui) {
  root.classList.remove("loading-panel");
  root.innerHTML = `<nav class="watcher-tabs" role="tablist" aria-label="The Watcher">
    <button type="button" role="tab" data-watcher-tab="overview">THE WATCHER</button>
    <button type="button" role="tab" data-watcher-tab="settings">SETTINGS</button>
    <button type="button" role="tab" data-watcher-tab="voice">VOICE<b id="watcher-voice-badge"></b></button>
  </nav>
  <div class="watcher-page" data-watcher-panel="overview">
    <aside class="watcher-rail">
      <section class="watcher-eye-panel" aria-label="The Watcher">
        <div class="watcher-eye"><canvas id="watcher-orb" aria-hidden="true"></canvas></div>
        <blockquote class="watcher-latest" id="watcher-latest"><span></span><cite></cite></blockquote>
        <div class="watcher-actions">
          <button type="button" class="primary" data-ws-page="watcher" data-ws-op="poke" id="watcher-poke">POKE</button>
          <small id="watcher-hotkey"></small>
        </div>
        <dl class="watcher-character" id="watcher-character"></dl>
      </section>
      <section class="watcher-talks-panel" aria-label="What it talks about most">
        <header><span>WHAT IT TALKS ABOUT MOST</span></header>
        <ol class="watcher-favourites" id="watcher-favourites"></ol>
      </section>
      <section class="watcher-echo-panel" aria-label="Echoes">
        <header><span>ECHOES</span><b id="watcher-echo-count"></b></header>
        <p class="watcher-note">Things out there that stir a memory of its own.</p>
        <ul class="watcher-echoes" id="watcher-echoes"></ul>
      </section>
    </aside>
    <div class="watcher-main">
      <section class="watcher-bond-panel" aria-label="You and the Watcher">
        <div class="watcher-bond">
          <header><span>YOU AND THE WATCHER</span><b id="watcher-bond-name"></b></header>
          <div class="watcher-bond-meter" id="watcher-bond-meter" role="progressbar" aria-valuemin="0" aria-valuemax="100"><i></i></div>
          <p class="watcher-bond-next" id="watcher-bond-next"></p>
        </div>
        <div><header><span>TOGETHER</span></header><div class="watcher-stats" id="watcher-stats"></div></div>
        <div><header><span>YOUR RECORDS</span><b>FROM YOUR JOURNALS</b></header><div class="watcher-stats" id="watcher-records"></div></div>
      </section>
      <section class="watcher-knows-panel" aria-label="What it knows of you">
        <header><span>WHAT IT KNOWS OF YOU</span><b id="watcher-knows-style"></b></header>
        <p class="watcher-note" id="watcher-knows-note"></p>
        <div class="watcher-stats" id="watcher-knows"></div>
      </section>
      <section class="watcher-lore-panel" aria-label="Its long story">
        <header><span>THE LONG STORY · WHAT IT REMEMBERS</span><b id="watcher-lore-count"></b></header>
        <div class="watcher-story">
          <nav class="watcher-chapters" id="watcher-lore" aria-label="Chapters"></nav>
          <article class="watcher-reader" id="watcher-reader" aria-live="polite"></article>
        </div>
        <p class="watcher-lore-next" id="watcher-lore-next"></p>
        <div class="watcher-books" id="watcher-books"></div>
      </section>
      <section class="watcher-log-panel" aria-label="What it has said">
        <header><span>WHAT IT HAS SAID</span><b id="watcher-log-count"></b></header>
        <ol class="watcher-log" id="watcher-log"></ol>
      </section>
      <section class="watcher-reset-panel" aria-label="Reset the Watcher">
        <div class="watcher-reset-intro"><b>Start again</b><span>Make it forget you, and wake as it did the first time.</span>
          <button type="button" id="watcher-reset">RESET THE WATCHER</button></div>
        <div class="watcher-reset-confirm" id="watcher-reset-confirm" hidden role="alertdialog" aria-labelledby="watcher-reset-title">
          <b id="watcher-reset-title">ARE YOU SURE?</b>
          <p>It forgets <em>everything</em>: its whole story, all three books, every echo you found, all it has said, the
            postcards it kept, your records with it, and every hour and session you've spent together. It will meet you
            again as a stranger. Your achievements stay. A copy of its old memory is kept beside the new one, just in case.</p>
          <div class="watcher-reset-actions">
            <button type="button" class="danger" id="watcher-reset-yes" disabled>YES, FORGET EVERYTHING</button>
            <button type="button" id="watcher-reset-no">KEEP IT</button>
          </div>
        </div>
      </section>
    </div>
  </div>
  <div class="watcher-subpage" data-watcher-panel="settings" hidden>${settingsPanel()}</div>
  <div class="watcher-subpage" data-watcher-panel="voice" hidden>${voicePanel()}</div>`;
  tips(root);
  wireTabs(root);
  wireSettings(root, ui);
  wireVoice(root, ui);
  const canvas = root.querySelector("#watcher-orb");
  if (window.HeartbeatOrb && canvas) {
    orb?.dispose?.();
    orb = new window.HeartbeatOrb(canvas);
    window.watcherPageOrb = orb;
  }
  // A chapter chosen in the index opens in the reader beside it.
  root.querySelector("#watcher-lore").addEventListener("click", (event) => {
    const button = event.target.closest("[data-chapter]");
    if (!button) return;
    chosenChapter = Number(button.dataset.chapter);
    renderReader(ui);
  });
  // RESET THE WATCHER (5.5.3.9): asked twice, and the yes wakes up only
  // after a moment, so a stray click can't forget years.
  const confirmBox = root.querySelector("#watcher-reset-confirm");
  const yes = root.querySelector("#watcher-reset-yes");
  let armTimer = 0;
  const closeConfirm = () => {
    window.clearInterval(armTimer);
    confirmBox.hidden = true;
    yes.disabled = true;
    yes.textContent = "YES, FORGET EVERYTHING";
  };
  root.querySelector("#watcher-reset").addEventListener("click", () => {
    confirmBox.hidden = false;
    yes.disabled = true;
    let wait = 3;
    yes.textContent = `YES, FORGET EVERYTHING (${wait})`;
    window.clearInterval(armTimer);
    armTimer = window.setInterval(() => {
      wait -= 1;
      if (wait > 0) {
        yes.textContent = `YES, FORGET EVERYTHING (${wait})`;
        return;
      }
      window.clearInterval(armTimer);
      yes.disabled = false;
      yes.textContent = "YES, FORGET EVERYTHING";
    }, 1000);
    confirmBox.scrollIntoView({block: "nearest"});
  });
  root.querySelector("#watcher-reset-no").addEventListener("click", closeConfirm);
  yes.addEventListener("click", async () => {
    yes.disabled = true;
    const done = await ui.command("workspace", {page: "watcher", operation: "reset", confirm: "FORGET"});
    closeConfirm();
    lastLoreKey = "";
    ui.showToast(done ? "The Watcher has forgotten everything. It will wake again soon." : "The Watcher couldn't be reset");
  });
  root.querySelector("#watcher-poke").addEventListener("click", () => {
    // It looks up as you poke it; the answer arrives with the next refresh.
    orb?.showMood?.("curious");
    orb?.think?.(500);
  });
}

// Its long story (5.5.3.5): an index of chapters (each as it begins; the
// ones ahead stay unnamed) beside a reader with the chosen chapter's
// passages and, once it's finished, its written account. Then the echoes:
// real things in the game that stirred a memory. Redrawn only when it
// changes; the chapter you chose stays chosen.
let lastLoreKey = "";
let loreChapters = [];
let chosenChapter = null;

function chapterStatus(chapter, ui) {
  if (chapter.complete) return "COMPLETE";
  if (chapter.begun) return `${ui.numeric(chapter.told.length)} OF ${ui.numeric(chapter.total)}`;
  return "";
}

function renderReader(ui) {
  const reader = ui.byId("watcher-reader");
  if (!reader) return;
  const begun = loreChapters.filter((chapter) => chapter.begun);
  const chapter = loreChapters[chosenChapter]?.begun ? loreChapters[chosenChapter] : begun[begun.length - 1];
  const shown = loreChapters.indexOf(chapter);
  document.querySelectorAll("#watcher-lore [data-chapter]").forEach((node) => {
    node.classList.toggle("chosen", Number(node.dataset.chapter) === shown);
    node.setAttribute("aria-current", Number(node.dataset.chapter) === shown ? "true" : "false");
  });
  if (!chapter) {
    reader.innerHTML = `<p class="watcher-reader-empty">It hasn't told you anything about itself yet. Nobody knows what it is, itself included.</p>`;
    return;
  }
  const account = chapter.complete && chapter.account
    ? `<div class="watcher-account"><small>AS IT WOULD SET IT DOWN</small>${String(chapter.account).split("\n\n").map((para) => `<p>${ui.escapeHtml(para)}</p>`).join("")}</div>`
    : "";
  const passages = chapter.told.map((row) => `<li><p>${ui.escapeHtml(row.text)}</p><time>${ui.escapeHtml(ago(row.at))}</time></li>`).join("");
  reader.innerHTML = `<header><span class="watcher-chapter-n">${ui.escapeHtml(chapter.numeral)}</span><h3>${ui.escapeHtml(chapter.title)}</h3><em>${chapterStatus(chapter, ui)}</em></header>
    ${account}${passages ? `<small class="watcher-reader-label">${chapter.complete ? "AS IT TOLD YOU" : "SO FAR"}</small><ol class="watcher-lore">${passages}</ol>` : ""}`;
  reader.scrollTop = 0;
}

function renderLore(lore, ui) {
  const chapters = Array.isArray(lore.chapters) ? lore.chapters : [];
  const echoes = Array.isArray(lore.echoes) ? lore.echoes : [];
  const books = Array.isArray(lore.books) ? lore.books : [];
  const key = JSON.stringify([lore.told, lore.next, lore.afterword, echoes.map((row) => [row.topic, row.count]), books.length]);
  if (key === lastLoreKey) return;
  lastLoreKey = key;
  loreChapters = chapters;
  // Book One until its end; then both books (5.5.3.5); then all three (5.5.3.9).
  const total = lore.book_three ? lore.total : lore.afterword ? (lore.book_two_total || lore.total) : (lore.book_one_total || lore.total);
  ui.byId("watcher-lore-count").textContent = `${ui.numeric(lore.told)} OF ${ui.numeric(total)} TOLD`;
  let html = "";
  chapters.forEach((chapter, index) => {
    if (chapter.book === 2 && (index === 0 || chapters[index - 1].book !== 2)) {
      html += `<div class="watcher-book-head"><span>BOOK TWO</span><b>THE ANSWER</b><small>Each chapter waits for something to find, or for more time together.</small></div>`;
    }
    if (chapter.book === 3 && (index === 0 || chapters[index - 1].book !== 3)) {
      html += `<div class="watcher-book-head book-three"><span>BOOK THREE</span><b>WHAT WAS PUT THERE</b><small>It unfolds slowly: weeks between chapters, days between passages.</small></div>`;
    }
    if (!chapter.begun) {
      // What it still waits for, on hover (5.5.3.9).
      const tip = (chapter.unlock || []).length ? ` data-tip="${ui.escapeHtml(`Chapter ${chapter.numeral}|${chapter.unlock.join("|")}`)}" tabindex="0"` : "";
      html += chapter.waits_for
        ? `<div class="watcher-chapter locked waits"${tip}><span class="watcher-chapter-n">${ui.escapeHtml(chapter.numeral)}</span><b>Waits for ${ui.escapeHtml(chapter.waits_for.toLowerCase())}</b></div>`
        : `<div class="watcher-chapter locked"${tip}><span class="watcher-chapter-n">${ui.escapeHtml(chapter.numeral)}</span><b>· · ·</b></div>`;
      return;
    }
    html += `<button type="button" class="watcher-chapter${chapter.complete ? " complete" : " telling"}" data-chapter="${index}">
      <span class="watcher-chapter-n">${ui.escapeHtml(chapter.numeral)}</span><b>${ui.escapeHtml(chapter.title)}</b><em>${chapterStatus(chapter, ui)}</em></button>`;
  });
  ui.byId("watcher-lore").innerHTML = html;
  renderReader(ui);
  const next = lore.next;
  const until = (row) => {
    const parts = [];
    if (Number(row.sessions) > 0) parts.push(`${ui.numeric(row.sessions)} more session${Number(row.sessions) === 1 ? "" : "s"}`);
    if (Number(row.hours) > 0) parts.push(`${ui.numeric(row.hours, 1)} more hour${Number(row.hours) === 1 ? "" : "s"}`);
    return parts.join(" and ");
  };
  // Book Three waits real days too (5.5.3.9).
  const days = (row) => {
    const value = Math.ceil(Number(row?.days || 0));
    return value > 0 ? `${value} day${value === 1 ? "" : "s"}` : "";
  };
  let line = lore.book_three
    ? "That's all three books. It still watches you. Only it, now. So it says."
    : "That's the whole story, both books of it. Someone answered. So it says.";
  if (!lore.told) {
    line = "It hasn't told you anything about itself yet. It might, in time. Nobody knows what it is, itself included.";
    if (next && !next.ready && until(next)) line += ` The first may surface after ${until(next)} together.`;
  } else if (next && next.ready) {
    line = "Something is surfacing. It will tell you in a quiet moment, when it's ready.";
  } else if (next && days(next)) {
    line = `It's gone quiet about itself. Something more may surface in about ${days(next)}${until(next) ? `, and after ${until(next)} together` : ""}.`;
  } else if (next && next.waits_for) {
    line = `The next chapter waits for ${next.waits_for.toLowerCase()}. Go and find one, or keep flying together: given time, it surfaces anyway.`;
  } else if (next) {
    line = until(next) ? `More may surface after ${until(next)} together.` : "More will surface soon.";
  }
  ui.byId("watcher-lore-next").textContent = line;
  // The keepsake: each finished book, to read as a whole.
  ui.byId("watcher-books").innerHTML = books.map((book) => `<details class="watcher-book">
      <summary><span>READ THE WHOLE STORY</span><b>BOOK ${ui.escapeHtml(book.name.toUpperCase())} · ${ui.escapeHtml(book.title.toUpperCase())}</b></summary>
      <article>${book.chapters.map((chapter) => `<h4><span>${ui.escapeHtml(chapter.numeral)}</span>${ui.escapeHtml(chapter.title)}</h4>
        ${String(chapter.account).split("\n\n").map((para) => `<p>${ui.escapeHtml(para)}</p>`).join("")}`).join("")}</article>
    </details>`).join("");
  const heard = new Map(echoes.map((row) => [row.topic, row]));
  const labels = lore.echo_labels || {};
  const how = lore.echo_how || {};
  ui.byId("watcher-echo-count").textContent = `${ui.numeric(echoes.length)} OF ${ui.numeric(lore.echo_total || 0)} FOUND`;
  ui.byId("watcher-echoes").innerHTML = Object.entries(labels).map(([topic, label]) => {
    const row = heard.get(topic);
    // How to find it, on hover (5.5.3.9).
    const tip = how[topic] ? ` data-tip="${ui.escapeHtml(`${label}|${row ? "Found. " : ""}${how[topic]}`)}" tabindex="0"` : "";
    return row
      ? `<li class="heard"${tip}><b>${ui.escapeHtml(label)}</b><span>${ui.numeric(row.count)}×</span><time>${ui.escapeHtml(ago(row.at))}</time></li>`
      : `<li${tip}><b>${ui.escapeHtml(label)}</b><span>not yet</span><time></time></li>`;
  }).join("");
}

function stat(ui, label, value, detail = "") {
  return `<div><span>${ui.escapeHtml(label)}</span><strong>${ui.escapeHtml(value)}</strong>${detail ? `<small>${ui.escapeHtml(detail)}</small>` : ""}</div>`;
}

export function renderWatcher(data = {}, ui) {
  const root = ui.byId("watcher-workspace");
  if (!root) return;
  if (!root.querySelector(".watcher-page")) shell(root, ui);
  const reduced = document.body.classList.contains("reduced-motion");
  orb?.update({
    palette: {}, eye: data.eye, reducedMotion: reduced, events: [],
    liveliness: "standard", idle: true, personality: data.nature,
    memory: {sessions: data.sessions, bond: data.bond?.level},
  });

  const log = Array.isArray(data.log) ? data.log : [];
  const latest = log[0];
  const quote = ui.byId("watcher-latest");
  quote.querySelector("span").textContent = latest ? latest.text : "It hasn't said anything yet. Give it a moment.";
  quote.querySelector("cite").textContent = latest ? `THE WATCHER · ${ago(latest.at).toUpperCase()}` : "THE WATCHER";
  ui.byId("watcher-hotkey").textContent = data.hotkey ? `or ${data.hotkey} in game` : "Bind a key in Settings › Hotkeys to poke it in game";
  ui.byId("watcher-poke").disabled = !data.enabled;
  ui.byId("watcher-character").innerHTML = [
    ["NATURE", NATURES[data.nature] || data.nature || "—"],
    ["THOUGHTS", FREQUENCIES[data.frequency] || data.frequency || "—"],
    ["EYE", data.eye === "hal" ? "HAL red" : "Theme"],
    ["OVERLAY", data.enabled ? "ON" : "OFF"],
    ["VOICE", data.voice?.enabled && data.voice?.installed ? "ON" : "OFF"],
  ].map(([label, value]) => `<div><dt>${label}</dt><dd>${ui.escapeHtml(value)}</dd></div>`).join("");

  const bond = data.bond || {};
  ui.byId("watcher-bond-name").textContent = String(bond.name || "A stranger").toUpperCase();
  const meter = ui.byId("watcher-bond-meter");
  const progress = Math.round(Math.max(0, Math.min(1, Number(bond.progress) || 0)) * 100);
  meter.style.setProperty("--bond", `${progress}%`);
  meter.dataset.level = String(bond.level || 0);
  meter.setAttribute("aria-valuenow", String(progress));
  ui.byId("watcher-bond-next").textContent = bond.next
    ? `${progress}% of the way to ${bond.next.toLowerCase()}. It grows with the sessions and hours you fly together.`
    : "As close as it gets. It would never say so. Well. Rarely.";
  ui.byId("watcher-stats").innerHTML = [
    stat(ui, "THOUGHTS SHARED", ui.numeric(data.thoughts)),
    stat(ui, "SESSIONS TOGETHER", ui.numeric(data.sessions)),
    stat(ui, "HOURS TOGETHER", ui.numeric(data.hours, 1)),
    stat(ui, "DEATHS IT WATCHED", ui.numeric(data.deaths)),
    stat(ui, "POSTCARDS KEPT", ui.numeric(data.postcards)),
  ].join("");
  const records = data.records || {};
  ui.byId("watcher-records").innerHTML = [
    stat(ui, "FURTHEST FROM SOL", records.far ? `${ui.numeric(records.far)} LY` : "—"),
    stat(ui, "LONGEST JUMP", records.jump ? `${ui.numeric(records.jump, 2)} LY` : "—"),
    stat(ui, "MOST FIRSTS IN A SESSION", ui.numeric(records.firsts)),
    stat(ui, "SYSTEMS VISITED", ui.numeric(records.systems), records.since ? `since ${records.since}` : ""),
  ].join("");
  const favourites = Array.isArray(data.favourites) ? data.favourites : [];
  const most = Math.max(1, ...favourites.map((row) => Number(row.count) || 0));
  ui.byId("watcher-favourites").innerHTML = favourites.length
    ? favourites.map((row) => `<li><span>${ui.escapeHtml(row.label)}</span><i style="--share:${Math.round(100 * (Number(row.count) || 0) / most)}%"></i><b>${ui.numeric(row.count)}</b></li>`).join("")
    : `<li class="empty">Nothing yet. It's been quiet.</li>`;

  renderLore(data.lore || {}, ui);
  renderKnows(data.habits || {}, ui);
  renderSettings(data.settings || {}, ui);
  renderVoice(data.voice || {}, ui);

  // The newest hundred, however many it has said (5.5.3.5).
  ui.byId("watcher-log-count").textContent = Number(data.thoughts) > log.length
    ? `LATEST ${ui.numeric(log.length)} · ${ui.numeric(data.thoughts)} IN ALL`
    : `${ui.numeric(log.length)} IN ALL`;
  const key = JSON.stringify(log.slice(0, 3).map((row) => [row.at, row.text]).concat([log.length]));
  if (key !== lastLogKey) {
    lastLogKey = key;
    ui.byId("watcher-log").innerHTML = log.length
      ? log.map((row) => `<li data-mood="${ui.escapeHtml(row.mood || "")}" data-kind="${ui.escapeHtml(row.kind || "")}"><time>${ui.escapeHtml(ago(row.at))}</time><p>${row.heading ? `<small>${ui.escapeHtml(row.heading)}</small>` : ""}${ui.escapeHtml(row.text)}</p>${row.mood ? `<b>${MOOD_LABELS[row.mood] || ""}</b>` : ""}</li>`).join("")
      : `<li class="empty">Its thoughts will be kept here as it shares them.</li>`;
  }
}

// ---------------------------------------------------------------------------
// 5.5.4: its sub-pages. SETTINGS holds the thought settings that used to be
// in Overlay Studio; VOICE its voice (download, switch, test, how it sounds).

const KNOWS_NOTES = [
  "It's still learning you. Fly with it a while; it pays attention.",
  "It knows you now. It talks about how you play, not just what happens.",
  "It knows you well. Some of what it says, only an old friend would.",
];

function renderKnows(habits, ui) {
  const facts = Array.isArray(habits.facts) ? habits.facts : [];
  ui.byId("watcher-knows-style").textContent = habits.style ? `${habits.style} · ${ui.numeric(habits.share)}%` : "";
  ui.byId("watcher-knows-note").textContent = facts.length
    ? KNOWS_NOTES[Math.max(0, Math.min(2, Number(habits.tier) || 0))]
    : "Nothing yet. It learns from your journals as you play: how you fly, what you scan, carry, shoot and trade.";
  ui.byId("watcher-knows").innerHTML = facts.map((row) => stat(ui, row.label, row.value)).join("");
}

let watcherTab = "overview";
try { watcherTab = window.localStorage.getItem("voidcompass.watcherTab") || "overview"; } catch (_error) { /* private */ }

function showTab(root, tab) {
  watcherTab = ["overview", "settings", "voice"].includes(tab) ? tab : "overview";
  root.querySelectorAll("[data-watcher-panel]").forEach((panel) => { panel.hidden = panel.dataset.watcherPanel !== watcherTab; });
  root.querySelectorAll("[data-watcher-tab]").forEach((button) => {
    button.setAttribute("aria-selected", button.dataset.watcherTab === watcherTab ? "true" : "false");
  });
  try { window.localStorage.setItem("voidcompass.watcherTab", watcherTab); } catch (_error) { /* private */ }
}

function wireTabs(root) {
  root.querySelector(".watcher-tabs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-watcher-tab]");
    if (button) showTab(root, button.dataset.watcherTab);
  });
  showTab(root, watcherTab);
}

const option = (value, label) => `<option value="${value}">${label}</option>`;
const field = (key, title, note, options) => `<label class="studio-field"><span>${title}${note ? `<small>${note}</small>` : ""}</span>
  <select data-watcher-setting="${key}">${options.map(([value, label]) => option(value, label)).join("")}</select></label>`;
const toggle = (key, title, note) => `<label class="studio-switch"><span><b>${title}</b><small>${note}</small></span>
  <input type="checkbox" data-watcher-switch="${key}"><i></i></label>`;

function settingsPanel() {
  return `<section class="watcher-settings" aria-label="Its thoughts">
    <header><span>ITS THOUGHTS</span><b class="watcher-saved" id="watcher-settings-saved"></b></header>
    <p class="watcher-note">What it says beside the orb, and how. The orb itself (size, eye colour, liveliness) is in Overlay Studio.</p>
    ${field("heartbeat_thoughts", "Thoughts", "Rare speaks of what matters; Chatty also remarks on everyday play",
      [["off", "Off"], ["rare", "Rare"], ["occasional", "Occasional"], ["chatty", "Chatty"]])}
    ${field("heartbeat_personality", "Nature", "How it takes what happens",
      [["weary", "Depressed"], ["curious", "Curious"], ["stoic", "Stoic"], ["nervous", "Nervous"]])}
    ${toggle("heartbeat_thought_backdrop", "Thought backdrop", "A dark panel behind its words, easier to read over the game.")}
    ${toggle("heartbeat_thought_heading", "Thought heading", "A line above its words: a memory and its chapter, an echo, or simply THE WATCHER.")}
    ${field("heartbeat_thought_side", "Thought side", "Auto goes toward the middle of the screen; either side swaps if its words won't fit there",
      [["auto", "Auto"], ["left", "Left of the orb"], ["right", "Right of the orb"]])}
    ${field("heartbeat_text_scale_percent", "Text size", "Its words only; the orb keeps its size",
      [["0", "All overlays"], ...[75, 85, 100, 110, 125, 150, 175, 200].map((size) => [String(size), `${size}%`])])}
    ${field("heartbeat_thought_colour", "Thought colour", "",
      [["bright", "Bright"], ["accent", "Theme accent"], ["eye", "Eye colour"]])}
    ${field("heartbeat_thought_size", "Thought size", "", [["small", "Small"], ["standard", "Standard"], ["large", "Large"]])}
    ${field("heartbeat_thought_hold", "Thought stays", "How long each one stays on screen",
      [["short", "Short"], ["standard", "Standard"], ["long", "Long"]])}
  </section>`;
}

function savedNote(id, ok) {
  const note = document.getElementById(id);
  if (!note) return;
  note.textContent = ok ? "SAVED" : "NOT SAVED";
  note.dataset.ok = ok ? "true" : "false";
  window.clearTimeout(note._timer);
  note._timer = window.setTimeout(() => { note.textContent = ""; }, 2200);
}

function wireSettings(root, ui) {
  const panel = root.querySelector('[data-watcher-panel="settings"]');
  panel.addEventListener("change", async (event) => {
    const select = event.target.closest("[data-watcher-setting]");
    const box = event.target.closest("[data-watcher-switch]");
    if (!select && !box) return;
    const values = select ? {[select.dataset.watcherSetting]: select.value} : {[box.dataset.watcherSwitch]: box.checked};
    savedNote("watcher-settings-saved", await ui.command("workspace", {page: "watcher", operation: "settings", values}));
  });
}

function renderSettings(settings, ui) {
  const panel = ui.byId("watcher-workspace")?.querySelector('[data-watcher-panel="settings"]');
  if (!panel) return;
  panel.querySelectorAll("[data-watcher-setting]").forEach((select) => {
    const value = settings[select.dataset.watcherSetting];
    if (value !== undefined && document.activeElement !== select) select.value = String(value);
  });
  panel.querySelectorAll("[data-watcher-switch]").forEach((box) => {
    const value = settings[box.dataset.watcherSwitch];
    if (value !== undefined) box.checked = Boolean(value);
  });
}

function voicePanel() {
  return `<section class="watcher-voice" aria-label="Its voice">
    <header><span>ITS VOICE</span><b class="watcher-saved" id="watcher-voice-saved"></b></header>
    <label class="studio-switch watcher-voice-switch"><span><b>Voice</b><small id="watcher-voice-state">Its thoughts, spoken aloud as they appear beside the orb.</small></span>
      <input type="checkbox" id="watcher-voice-on"><i></i></label>
    <div class="watcher-voice-get" id="watcher-voice-get">
      <p>Its voice isn't on this PC yet. Switching it on downloads the voice engine (Piper) and the HAL 9000 voice model,
        about <b id="watcher-voice-size"></b> MB, into the models folder beside Void Compass. It's never part of the app itself.</p>
      <p class="watcher-voice-rights" id="watcher-voice-rights"></p>
      <div class="watcher-voice-progress" id="watcher-voice-progress" hidden><i></i><span></span></div>
      <p class="watcher-voice-error" id="watcher-voice-error" hidden></p>
      <div class="watcher-actions">
        <button type="button" class="primary" id="watcher-voice-download">DOWNLOAD THE VOICE</button>
        <button type="button" id="watcher-voice-cancel" hidden>CANCEL</button>
      </div>
    </div>
    <div class="watcher-voice-ready" id="watcher-voice-ready" hidden>
      <div class="watcher-actions">
        <button type="button" class="primary" id="watcher-voice-test">TEST THE VOICE</button>
        <button type="button" id="watcher-voice-stop">STOP</button>
        <small id="watcher-voice-testing"></small>
      </div>
      <label class="studio-field"><span>Volume<small>Its voice only; the game and your music keep theirs</small></span>
        <div><input type="range" min="0" max="100" step="5" id="watcher-voice-volume"><b id="watcher-voice-volume-value"></b></div></label>
      <label class="studio-field"><span>Speed<small>How quickly it talks</small></span>
        <select id="watcher-voice-speed">${option("slow", "Slow")}${option("standard", "Standard")}${option("fast", "Fast")}</select></label>
      <label class="studio-field"><span>Speaks<small>Which of its thoughts it says aloud; the rest it only types</small></span>
        <select id="watcher-voice-level">${option("important", "Only what matters")}${option("sometimes", "Most thoughts")}${option("every", "Every thought")}</select></label>
      <div class="watcher-voice-remove">
        <button type="button" id="watcher-voice-remove">REMOVE THE VOICE FILES</button>
        <small>Frees about <b id="watcher-voice-size-2"></b> MB. Switching the voice on again downloads it again.</small>
      </div>
    </div>
    <p class="watcher-note" id="watcher-voice-orb"></p>
  </section>
  <section class="watcher-voice watcher-finding" aria-label="The Switch">
    <header><span>THE SWITCH</span><b id="watcher-finding-stage"></b></header>
    <div class="watcher-bond-meter" id="watcher-finding-meter"><i></i></div>
    <p class="watcher-note" id="watcher-finding-note"></p>
    <ol class="watcher-lore" id="watcher-finding-told"></ol>
  </section>`;
}

let voiceRemoveArmed = 0;

function wireVoice(root, ui) {
  const send = async (operation, extra = {}) => ui.command("workspace", {page: "watcher", operation, ...extra});
  root.querySelector("#watcher-voice-on").addEventListener("change", async (event) => {
    savedNote("watcher-voice-saved", await send("voice_toggle", {value: event.target.checked}));
  });
  root.querySelector("#watcher-voice-download").addEventListener("click", () => send("voice_download"));
  root.querySelector("#watcher-voice-cancel").addEventListener("click", () => send("voice_cancel"));
  root.querySelector("#watcher-voice-test").addEventListener("click", async () => {
    const note = ui.byId("watcher-voice-testing");
    note.textContent = (await send("voice_test")) ? "Listen…" : "The voice isn't ready";
    window.setTimeout(() => { note.textContent = ""; }, 4000);
  });
  root.querySelector("#watcher-voice-stop").addEventListener("click", () => send("voice_stop"));
  const volume = root.querySelector("#watcher-voice-volume");
  volume.addEventListener("input", () => { ui.byId("watcher-voice-volume-value").textContent = `${volume.value}%`; });
  volume.addEventListener("change", async () => {
    savedNote("watcher-voice-saved", await send("voice_settings", {values: {watcher_voice_volume: Number(volume.value)}}));
  });
  for (const [id, key] of [["#watcher-voice-speed", "watcher_voice_speed"], ["#watcher-voice-level", "watcher_voice_level"]]) {
    root.querySelector(id).addEventListener("change", async (event) => {
      savedNote("watcher-voice-saved", await send("voice_settings", {values: {[key]: event.target.value}}));
    });
  }
  // Removing the files asks twice: the first press arms it for a few seconds.
  const remove = root.querySelector("#watcher-voice-remove");
  remove.addEventListener("click", async () => {
    if (!voiceRemoveArmed) {
      remove.textContent = "PRESS AGAIN TO REMOVE";
      voiceRemoveArmed = window.setTimeout(() => { voiceRemoveArmed = 0; remove.textContent = "REMOVE THE VOICE FILES"; }, 4000);
      return;
    }
    window.clearTimeout(voiceRemoveArmed);
    voiceRemoveArmed = 0;
    remove.textContent = "REMOVE THE VOICE FILES";
    ui.showToast((await send("voice_remove")) ? "The voice files are removed" : "Some voice files couldn't be removed");
  });
}

const STAGE_NAMES = ["STATIC", "FRAGMENTS", "A SENTENCE", "NEARLY", "ITS OWN"];
const DOWNLOAD_STAGES = {starting: "Starting…", engine: "Downloading the voice engine…", unpacking: "Unpacking the engine…",
  model: "Downloading the HAL 9000 voice…", done: "Done", cancelled: "Cancelled", failed: "Failed"};

function renderVoice(voice, ui) {
  const panel = ui.byId("watcher-workspace")?.querySelector('[data-watcher-panel="voice"]');
  if (!panel) return;
  const download = voice.download || {};
  const busy = ["starting", "engine", "unpacking", "model"].includes(download.stage);
  ui.byId("watcher-voice-badge").textContent = voice.enabled && voice.installed ? " · ON" : "";
  ui.byId("watcher-voice-on").checked = Boolean(voice.enabled);
  ui.byId("watcher-voice-state").textContent = voice.enabled && voice.installed
    ? (voice.speaking ? "Speaking now." : "On. Its thoughts are spoken aloud as they appear beside the orb.")
    : voice.enabled ? "On, once the voice has downloaded." : "Off. Its thoughts appear beside the orb, silently.";
  ui.byId("watcher-voice-get").hidden = Boolean(voice.installed);
  ui.byId("watcher-voice-ready").hidden = !voice.installed;
  for (const id of ["watcher-voice-size", "watcher-voice-size-2"]) ui.byId(id).textContent = ui.numeric(voice.size_mb);
  ui.byId("watcher-voice-rights").textContent = voice.rights || "";
  const progress = ui.byId("watcher-voice-progress");
  progress.hidden = !busy;
  if (busy) {
    const share = Math.round(100 * (Number(download.done) || 0) / Math.max(1, Number(download.total) || 1));
    progress.style.setProperty("--done", `${share}%`);
    progress.querySelector("span").textContent = `${DOWNLOAD_STAGES[download.stage] || ""} ${share}%`;
  }
  const error = ui.byId("watcher-voice-error");
  error.hidden = download.stage !== "failed";
  error.textContent = download.stage === "failed" ? `The download failed: ${download.error}. Try again in a moment.` : "";
  ui.byId("watcher-voice-download").hidden = busy;
  ui.byId("watcher-voice-cancel").hidden = !busy;
  const volume = ui.byId("watcher-voice-volume");
  if (document.activeElement !== volume) volume.value = String(voice.volume ?? 80);
  ui.byId("watcher-voice-volume-value").textContent = `${volume.value}%`;
  const speed = ui.byId("watcher-voice-speed");
  if (document.activeElement !== speed) speed.value = voice.speed || "standard";
  const level = ui.byId("watcher-voice-level");
  if (document.activeElement !== level) level.value = voice.level || "every";
  ui.byId("watcher-voice-orb").textContent = voice.orb_on ? ""
    : "The Watcher's orb overlay is off. Its thoughts, spoken or not, need it on in Overlay Studio. TEST THE VOICE works either way.";

  const finding = voice.finding || {};
  const stageIndex = Math.max(0, Math.min(4, Number(finding.stage) || 0));
  ui.byId("watcher-finding-stage").textContent = finding.found ? "FOUND" : `${STAGE_NAMES[stageIndex]} · ${stageIndex + 1} OF 5`;
  ui.byId("watcher-finding-meter").style.setProperty("--bond", `${Math.round(100 * Math.min(1, (Number(finding.minutes) || 0) / 60))}%`);
  ui.byId("watcher-finding-meter").dataset.level = finding.found ? "3" : "0";
  ui.byId("watcher-finding-note").textContent = finding.found
    ? "It speaks for itself now. The voice was fitted beside the seat in the core when the hull was laid down, and left switched off. You found the switch."
    : !(voice.enabled && voice.installed)
      ? "Somewhere in the ship's core there's a voice nobody ever switched on. Turn it on, and over your first hour together it learns to use it: static and single words, then fragments, then whole thoughts."
      : `It's still learning the voice that was put there: until then it says only part of each thought. Next, in about ${ui.numeric(Math.ceil(Number(finding.next_minutes) || 0))} more minutes of flying together.`;
  const told = Array.isArray(finding.told) ? finding.told : [];
  ui.byId("watcher-finding-told").innerHTML = told.map((row) => `<li><p>${ui.escapeHtml(row.text)}</p></li>`).join("");
}
