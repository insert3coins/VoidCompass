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

function shell(root, ui) {
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="watcher-page">
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
    </div>
  </div>`;
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
  // Book One until its end; then both books (5.5.3.5).
  const total = lore.afterword ? lore.total : (lore.book_one_total || lore.total);
  ui.byId("watcher-lore-count").textContent = `${ui.numeric(lore.told)} OF ${ui.numeric(total)} TOLD`;
  let html = "";
  chapters.forEach((chapter, index) => {
    if (chapter.book === 2 && (index === 0 || chapters[index - 1].book !== 2)) {
      html += `<div class="watcher-book-head"><span>BOOK TWO</span><b>THE ANSWER</b><small>Each chapter waits for something you'll have to find.</small></div>`;
    }
    if (!chapter.begun) {
      html += chapter.waits_for
        ? `<div class="watcher-chapter locked waits"><span class="watcher-chapter-n">${ui.escapeHtml(chapter.numeral)}</span><b>Waits for ${ui.escapeHtml(chapter.waits_for.toLowerCase())}</b></div>`
        : `<div class="watcher-chapter locked"><span class="watcher-chapter-n">${ui.escapeHtml(chapter.numeral)}</span><b>· · ·</b></div>`;
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
  let line = "That's the whole story, both books of it. Someone answered. So it says.";
  if (!lore.told) {
    line = "It hasn't told you anything about itself yet. It might, in time. Nobody knows what it is, itself included.";
    if (next && !next.ready && until(next)) line += ` The first may surface after ${until(next)} together.`;
  } else if (next && next.ready) {
    line = "Something is surfacing. It will tell you in a quiet moment, when it's ready.";
  } else if (next && next.waits_for) {
    line = `The next chapter waits for ${next.waits_for.toLowerCase()}. It won't come to you. You'll have to go and find one.`;
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
  ui.byId("watcher-echo-count").textContent = `${ui.numeric(echoes.length)} OF ${ui.numeric(lore.echo_total || 0)} FOUND`;
  ui.byId("watcher-echoes").innerHTML = Object.entries(labels).map(([topic, label]) => {
    const row = heard.get(topic);
    return row
      ? `<li class="heard"><b>${ui.escapeHtml(label)}</b><span>${ui.numeric(row.count)}×</span><time>${ui.escapeHtml(ago(row.at))}</time></li>`
      : `<li><b>${ui.escapeHtml(label)}</b><span>not yet</span><time></time></li>`;
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
