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
let lastThought = "";
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

// 5.6.1: laid out again now there's so much more of it. NOW is the eye and
// what's live (a question, how it feels, where it wants to go); STORY the
// four books and the echoes; YOU what it has gathered of you; SAID every
// word; then its settings and its voice.
const panel = (title, body, note = "", extra = "") =>
  `<section class="watcher-card ${extra}" aria-label="${title}"><header><span>${title}</span><b${note ? ` id="${note}"` : ""}></b></header>${body}</section>`;

function shell(root, ui) {
  root.classList.remove("loading-panel");
  root.innerHTML = `<nav class="watcher-tabs" role="tablist" aria-label="The Watcher">
    <button type="button" role="tab" data-watcher-tab="now">NOW<b id="watcher-now-badge"></b></button>
    <button type="button" role="tab" data-watcher-tab="story">STORY</button>
    <button type="button" role="tab" data-watcher-tab="you">YOU</button>
    <button type="button" role="tab" data-watcher-tab="said">SAID</button>
    <button type="button" role="tab" data-watcher-tab="settings">SETTINGS</button>
    <button type="button" role="tab" data-watcher-tab="voice">VOICE<b id="watcher-voice-badge"></b></button>
    <button type="button" role="tab" data-watcher-tab="mind">MIND<b id="watcher-mind-badge"></b></button>
    <button type="button" role="tab" data-watcher-tab="library">LIBRARY</button>
  </nav>
  <div class="watcher-page watcher-now" data-watcher-panel="now">
    <aside class="watcher-eye-panel" aria-label="The Watcher">
      <div class="watcher-optics-stage">
        <div class="watcher-stage-head"><span>THE WATCHER</span><small id="watcher-feed">JOURNAL LINK</small></div>
        <div class="watcher-eye"><canvas id="watcher-orb" aria-hidden="true"></canvas></div>
        <div class="watcher-stage-caption"><b id="watcher-flight-state"></b><span id="watcher-last-event"></span></div>
      </div>
      <blockquote class="watcher-latest" id="watcher-latest"><span></span><cite></cite></blockquote>
      <div class="watcher-actions">
        <button type="button" class="primary" data-ws-page="watcher" data-ws-op="poke" id="watcher-poke">POKE</button>
        <small id="watcher-hotkey"></small>
      </div>
      <dl class="watcher-character" id="watcher-character"></dl>
    </aside>
    <div class="watcher-now-main">
      <section class="watcher-ask" id="watcher-question" aria-live="polite"></section>
      <section class="watcher-card watcher-bond-panel" aria-label="You and the Watcher">
        <header><span>YOU AND THE WATCHER</span><b id="watcher-bond-name"></b></header>
        <div class="watcher-bond-meter" id="watcher-bond-meter" role="progressbar" aria-valuemin="0" aria-valuemax="100"><i></i></div>
        <p class="watcher-bond-next" id="watcher-bond-next"></p>
        <div class="watcher-feeling" id="watcher-feeling"></div>
      </section>
      <div class="watcher-pair">
        <section class="watcher-card watcher-now-story" aria-label="Its story, now">
          <header><span>ITS STORY</span><b id="watcher-now-count"></b></header>
          <div id="watcher-now-story"></div>
          <button type="button" class="watcher-go" data-watcher-go="story">READ THE STORY</button>
        </section>
        <section class="watcher-card watcher-wish" id="watcher-wish" aria-label="Where it wants to go"></section>
      </div>
      <section class="watcher-card" aria-label="Lately">
        <header><span>BEFORE THAT</span><b></b></header>
        <ol class="watcher-log watcher-lately" id="watcher-lately"></ol>
        <button type="button" class="watcher-go" data-watcher-go="said">EVERYTHING IT HAS SAID</button>
      </section>
    </div>
  </div>
  <div class="watcher-page watcher-story-page" data-watcher-panel="story" hidden>
    <section class="watcher-card watcher-lore-panel" aria-label="Its long story">
      <header><span>THE LONG STORY · WHAT IT REMEMBERS</span><b id="watcher-lore-count"></b></header>
      <div class="watcher-story">
        <nav class="watcher-chapters" id="watcher-lore" aria-label="Chapters"></nav>
        <article class="watcher-reader" id="watcher-reader" aria-live="polite"></article>
      </div>
      <p class="watcher-lore-next" id="watcher-lore-next"></p>
      <div class="watcher-books" id="watcher-books"></div>
    </section>
    <aside class="watcher-side">
      <section class="watcher-card watcher-road" id="watcher-road" aria-label="Its road"></section>
      ${panel("ECHOES", `<p class="watcher-note">Things out there that stir a memory of its own. Hover one to see how to find it.</p>
        <ul class="watcher-echoes" id="watcher-echoes"></ul>`, "watcher-echo-count")}
      ${panel("KEEP IT", `<p class="watcher-note">The story on your road, what it remembers, your answers and its dreams, saved as a book in the Wrapped folder.</p>
        <div class="watcher-buttons"><button type="button" data-watcher-code="book">SAVE AS A BOOK</button></div>`)}
    </aside>
  </div>
  <div class="watcher-page watcher-you" data-watcher-panel="you" hidden>
    <section class="watcher-card watcher-wide" aria-label="Together">
      <div class="watcher-two">
        <div><header><span>TOGETHER</span><b></b></header><div class="watcher-stats" id="watcher-stats"></div></div>
        <div><header><span>YOUR RECORDS</span><b>FROM YOUR JOURNALS</b></header><div class="watcher-stats" id="watcher-records"></div></div>
      </div>
    </section>
    ${namePanel()}
    ${panel("WHAT IT HAS WATCHED OF YOU", `<p class="watcher-note" id="watcher-knows-note"></p>
      <div class="watcher-stats" id="watcher-knows"></div>`, "watcher-knows-style", "watcher-wide watcher-knows-panel")}
    ${panel("WHAT IT REMEMBERS OF YOU", `<ol class="watcher-log watcher-short" id="watcher-memories"></ol>`, "watcher-memories-count")}
    ${panel("WHAT YOU TOLD IT", `<ol class="watcher-log watcher-short" id="watcher-answers"></ol>`, "watcher-answers-count")}
    ${panel("ITS DREAMS", `<ol class="watcher-log watcher-short" id="watcher-dreams"></ol>`, "watcher-dreams-count")}
    ${panel("WHAT IT TALKS ABOUT MOST", `<ol class="watcher-favourites" id="watcher-favourites"></ol>`)}
    ${panel("OTHER WATCHERS", `<p class="watcher-note">Share your Watcher's code (paste it in Discord or a message). A friend's code lets yours hear theirs.</p>
      <div class="watcher-meet"><textarea id="watcher-code" rows="2" placeholder="Paste a friend's VCWATCH1 code" spellcheck="false"></textarea>
        <div class="watcher-buttons"><button type="button" class="primary" data-watcher-code="meet">MEET IT</button>
        <button type="button" data-watcher-code="copy">COPY MY WATCHER'S CODE</button></div></div>
      <ol class="watcher-log watcher-short" id="watcher-met"></ol>`, "", "watcher-wide")}
  </div>
  <div class="watcher-page watcher-said" data-watcher-panel="said" hidden>
    <section class="watcher-card watcher-log-panel" aria-label="What it has said">
      <header><span>WHAT IT HAS SAID</span><b id="watcher-log-count"></b></header>
      <ol class="watcher-log" id="watcher-log"></ol>
    </section>
    <section class="watcher-reset-panel" aria-label="Reset the Watcher">
      <div class="watcher-reset-intro"><b>Start again</b><span>Make it forget you, and wake as it did the first time.</span>
        <button type="button" id="watcher-reset">RESET THE WATCHER</button></div>
      <div class="watcher-reset-confirm" id="watcher-reset-confirm" hidden role="alertdialog" aria-labelledby="watcher-reset-title">
        <b id="watcher-reset-title">ARE YOU SURE?</b>
        <p>It forgets <em>everything</em>: its whole story, all four books, every echo you found, all it has said, your
          answers, its dreams, the postcards it kept, your records with it, and every hour and session you've spent together. It will meet you
          again as a stranger. Your achievements stay. A copy of its old memory is kept beside the new one, just in case.</p>
        <div class="watcher-reset-actions">
          <button type="button" class="danger" id="watcher-reset-yes" disabled>YES, FORGET EVERYTHING</button>
          <button type="button" id="watcher-reset-no">KEEP IT</button>
        </div>
      </div>
    </section>
  </div>
  <div class="watcher-subpage" data-watcher-panel="settings" hidden>${settingsPanel()}</div>
  <div class="watcher-subpage" data-watcher-panel="voice" hidden>${voicePanel()}</div>
  <div class="watcher-page watcher-mindpage" data-watcher-panel="mind" hidden>${mindPanel()}</div>
  <div class="watcher-page watcher-librarypage" data-watcher-panel="library" hidden>${libraryPanel()}</div>`;
  tips(root);
  wireTabs(root);
  wireSettings(root, ui);
  wireVoice(root, ui);
  wireName(root, ui);
  wireMind(root, ui);
  wireLibrary(root, ui);
  // Answers, the code and the book, wherever they sit.
  root.addEventListener("click", async (event) => {
    const go = event.target.closest("[data-watcher-go]");
    if (go) {
      showTab(root, go.dataset.watcherGo);
      root.scrollIntoView({block: "start"});
      return;
    }
    const answer = event.target.closest("[data-watcher-answer]");
    if (answer) {
      answer.disabled = true;
      await ui.command("workspace", {page: "watcher", operation: "answer", answer: answer.dataset.watcherAnswer});
      return;
    }
    const action = event.target.closest("[data-watcher-code]")?.dataset.watcherCode;
    const box = ui.byId("watcher-code");
    if (action === "copy") {
      ui.showToast(await ui.command("workspace", {page: "watcher", operation: "copy_code"}) ? "Your Watcher's code is on the clipboard" : "It couldn't be copied");
    } else if (action === "meet") {
      const done = await ui.command("workspace", {page: "watcher", operation: "meet", code: box.value});
      ui.showToast(done ? "It met them" : "That isn't a Watcher's code");
      if (done) box.value = "";
    } else if (action === "book") {
      ui.showToast(await ui.command("workspace", {page: "watcher", operation: "save_book"}) ? "Saved in the Wrapped folder" : "It couldn't be saved");
    }
  });
  const canvas = root.querySelector("#watcher-orb");
  if (window.HeartbeatOrb && canvas) {
    orb?.dispose?.();
    orb = new window.HeartbeatOrb(canvas);
    window.watcherPageOrb = orb;
    lastThought = "";
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
  // Book One until its end; then both books (5.5.3.5); then all three (5.5.3.9);
  // Book Four counts only your road's chapters (5.6.1).
  const told = (book) => chapters.filter((chapter) => chapter.book === book).reduce((sum, chapter) => sum + chapter.total, 0);
  const total = lore.book_four ? (lore.book_two_total || 0) + told(3) + told(4)
    : lore.book_three ? (lore.book_two_total || 0) + told(3)
    : lore.afterword ? (lore.book_two_total || lore.total) : (lore.book_one_total || lore.total);
  ui.byId("watcher-lore-count").textContent = `${ui.numeric(lore.told)} OF ${ui.numeric(total)} TOLD`;
  let html = "";
  chapters.forEach((chapter, index) => {
    if (chapter.book === 2 && (index === 0 || chapters[index - 1].book !== 2)) {
      html += `<div class="watcher-book-head"><span>BOOK TWO</span><b>THE ANSWER</b><small>Each chapter waits for something to find, or for more time together.</small></div>`;
    }
    if (chapter.book === 3 && (index === 0 || chapters[index - 1].book !== 3)) {
      html += `<div class="watcher-book-head book-three"><span>BOOK THREE</span><b>WHAT WAS PUT THERE</b><small>It unfolds slowly: weeks between chapters, days between passages.</small></div>`;
    }
    if (chapter.book === 4 && (index === 0 || chapters[index - 1].book !== 4)) {
      const taken = lore.road === "shut" ? "Your road: the shutter drawn." : lore.road === "open" ? "Your road: the eye open." : "It waits for your answer about the shutter.";
      html += `<div class="watcher-book-head book-four"><span>BOOK FOUR</span><b>THE ROAD TAKEN</b><small>${taken}</small></div>`;
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
  let line = lore.road
    ? "That's all four books, on the road you chose. It still watches you. So it says."
    : lore.book_three
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
  // The NOW tab's glance at it: the chapter it's on, and what comes next.
  const current = chapters.filter((chapter) => chapter.begun).pop();
  ui.byId("watcher-now-count").textContent = ui.byId("watcher-lore-count").textContent;
  ui.byId("watcher-now-story").innerHTML = current
    ? `<p class="watcher-now-chapter"><span>${ui.escapeHtml(current.numeral)}</span><b>${ui.escapeHtml(current.title)}</b><em>${chapterStatus(current, ui)}</em></p>
      ${current.told.length ? `<p class="watcher-now-passage">${ui.escapeHtml(current.told[current.told.length - 1].text)}</p>` : ""}
      <p class="watcher-note">${ui.escapeHtml(line)}</p>`
    : `<p class="watcher-note">${ui.escapeHtml(line)}</p>`;
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
  const feed = data.heartbeat || {};
  const optics = feed.orb || {};
  orb?.update({
    palette: {}, eye: data.eye, reducedMotion: reduced, events: feed.events || [], frameRate: data.frame_rate,
    liveliness: optics.liveliness || "standard", idle: optics.idle !== false, personality: data.nature,
    memory: feed.memory || {sessions: data.sessions, bond: data.bond?.level},
    stalled: Boolean(feed.stalled), state: feed.state, statusSeq: feed.status_seq,
    vitals: feed.vitals, story: optics.story,
  });
  if (data.renderer_logging) orb?.watchRenderer((renderer, reason) => ui.command("watcher_renderer", {surface: "dashboard", renderer, ...(reason ? {reason} : {})}));

  const log = Array.isArray(data.log) ? data.log : [];
  const latest = log[0];
  const thoughtKey = latest ? `${latest.at}|${latest.text}` : "";
  if (thoughtKey !== lastThought) {
    if (latest && lastThought && latest.mood) orb?.showMood?.(latest.mood);
    lastThought = thoughtKey;
  }
  const feedLabel = ui.byId("watcher-feed");
  feedLabel.textContent = !data.enabled ? "OVERLAY OFF" : feed.status ? (feed.stalled ? "FEED QUIET" : "JOURNAL LIVE") : "JOURNAL LINK";
  feedLabel.dataset.live = String(Boolean(data.enabled && feed.status && !feed.stalled));
  ui.byId("watcher-flight-state").textContent = feed.state || feed.activity || "";
  const recentEvent = (feed.events || []).at(-1);
  const eventName = recentEvent?.event || recentEvent?.name || "";
  ui.byId("watcher-last-event").textContent = eventName.replace(/([a-z])([A-Z])/g, "$1 $2").toUpperCase();
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
  renderDeeper(data.deeper || {}, data.lore || {}, ui);
  renderKnows(data.habits || {}, ui);
  renderSettings(data.settings || {}, ui);
  renderVoice(data.voice || {}, ui);
  renderName(data.name || {}, ui);
  renderMind(data.mind || {}, ui);
  renderHear(data.listen || {}, data.mind || {}, ui);
  renderLibrary(data.library || {}, ui);

  // The newest hundred, however many it has said (5.5.3.5).
  ui.byId("watcher-log-count").textContent = Number(data.thoughts) > log.length
    ? `LATEST ${ui.numeric(log.length)} · ${ui.numeric(data.thoughts)} IN ALL`
    : `${ui.numeric(log.length)} IN ALL`;
  const key = JSON.stringify(log.slice(0, 3).map((row) => [row.at, row.text]).concat([log.length]));
  if (key !== lastLogKey) {
    lastLogKey = key;
    const line = (row) => `<li data-mood="${ui.escapeHtml(row.mood || "")}" data-kind="${ui.escapeHtml(row.kind || "")}"><time>${ui.escapeHtml(ago(row.at))}</time><p>${row.heading ? `<small>${ui.escapeHtml(row.heading)}</small>` : ""}${ui.escapeHtml(row.text)}</p>${row.mood ? `<b>${MOOD_LABELS[row.mood] || ""}</b>` : ""}</li>`;
    ui.byId("watcher-log").innerHTML = log.length ? log.map(line).join("")
      : `<li class="empty">Its thoughts will be kept here as it shares them.</li>`;
    ui.byId("watcher-lately").innerHTML = log.length > 1 ? log.slice(1, 6).map(line).join("")
      : `<li class="empty">Only that, so far.</li>`;
  }
}

// ---------------------------------------------------------------------------
// 5.6.1: what the deeper Watcher adds. Its question and how it feels about
// you (NOW), the road Book Four took (STORY), and what it keeps of you: its
// memories (faded where the shutter took them), your answers, its dreams,
// the other Watchers it has met (YOU).

const ROADS = {
  shut: ["ITS EYE CLOSED", "You chose the shutter. It keeps less of what it sees, and it says that's a mercy."],
  open: ["LOOKING BACK", "You chose to open the eye. Something out there looks at it, and it looks back."],
};
const drawn = new Map();

// Redrawn only when it changes, so a button under the pointer stays put.
function fill(ui, id, html) {
  const host = ui.byId(id);
  if (!host || drawn.get(id) === html) return;
  drawn.set(id, html);
  host.innerHTML = html;
}

function rows(ui, list, empty, body) {
  return list.length ? list.map((row) => `<li${row.faded ? ' class="faded"' : ""}><time>${ui.escapeHtml(ago(row.at))}</time><p>${body(row)}</p></li>`).join("")
    : `<li class="empty">${empty}</li>`;
}

function renderDeeper(deeper, lore, ui) {
  const esc = ui.escapeHtml;
  const question = deeper.question;
  ui.byId("watcher-now-badge").textContent = question ? " ●" : "";
  const keys = deeper.hotkeys || [];
  const asking = ui.byId("watcher-question");
  asking.classList.toggle("asking", Boolean(question));
  fill(ui, "watcher-question", question
    ? `<header><span>IT ASKS YOU</span><b>ANSWER HERE, OR WITH YOUR ANSWER KEYS IN GAME</b></header>
      <p class="watcher-question">${esc(question.text)}</p>
      <div class="watcher-answers">${question.answers.map((answer, index) => `<button type="button" class="watcher-answer" data-watcher-answer="${esc(answer.key)}">
        <b>${esc(answer.label)}</b>${keys[index] ? `<kbd>${esc(keys[index])}</kbd>` : ""}</button>`).join("")}</div>`
    : `<header><span>NOTHING ASKED</span><b></b></header>
      <p class="watcher-note">Now and then it asks you something, in the cockpit and here. It remembers what you say. Bind its answer keys in Settings › Hotkeys to answer without leaving the game.</p>`);

  const feeling = deeper.feeling || {};
  const trust = Math.max(0, Math.min(100, Number(feeling.trust_value) || 0));
  const road = ROADS[deeper.road];
  fill(ui, "watcher-feeling", `<div><span>TRUST</span><b>${esc(feeling.trust || "—")}</b><i class="watcher-gauge" style="--fill:${trust}%"></i></div>
    <div><span>MOOD LATELY</span><b>${esc(feeling.mood || "—")}</b><i class="watcher-gauge mood-${esc(feeling.mood || "")}" style="--fill:${Math.round(50 + 50 * Math.max(-1, Math.min(1, Number(feeling.mood_value) || 0)))}%"></i></div>
    <div><span>ITS ROAD</span><b>${road ? road[0].toLowerCase() : lore.book_four ? "still deciding" : "not yet"}</b><small>${lore.book_four ? "Book Four" : "after Book Three"}</small></div>`);

  const wish = deeper.pilgrimage;
  const wishState = wish ? (wish.reached ? ["TAKEN THERE", "done"] : wish.accepted ? ["YOU SAID YOU WOULD", "promised"] : ["NOT ANSWERED", ""]) : null;
  fill(ui, "watcher-wish", `<header><span>WHERE IT WANTS TO GO</span><b class="${wishState ? wishState[1] : ""}">${wishState ? wishState[0] : ""}</b></header>
    ${wish ? `<p class="watcher-wish-place">${esc(wish.words)}</p><p class="watcher-note">${esc(wish.how)}.</p>
      ${wish.reached ? "" : `<div class="watcher-buttons"><button type="button" data-page="mission">PLAN IT AS AN EXPEDITION</button></div>`}`
      : `<p class="watcher-note">Nowhere it has asked for, yet. Later in its story it may ask you to take it somewhere: a black hole, the core, the edge. An expedition can make it an objective.</p>`}`);

  fill(ui, "watcher-road", road
    ? `<header><span>ITS ROAD</span><b>${road[0]}</b></header><p class="watcher-note">${road[1]}</p>
      ${lore.other_road ? `<p class="watcher-note">There was another road. It doesn't talk about it.</p>` : ""}`
    : `<header><span>ITS ROAD</span><b>${lore.book_four ? "UNDECIDED" : ""}</b></header>
      <p class="watcher-note">${lore.book_four ? "Book Four waits for your answer about the shutter. It will ask you." : "After its third book, it will ask you something, and the story will go one of two ways."}</p>`);

  const memories = deeper.memories || [];
  const answers = deeper.answers || [];
  const dreams = deeper.dreams || [];
  const met = deeper.met || [];
  ui.byId("watcher-memories-count").textContent = memories.length ? `${ui.numeric(memories.length)} KEPT` : "";
  ui.byId("watcher-answers-count").textContent = answers.length ? `${ui.numeric(answers.length)} ASKED` : "";
  ui.byId("watcher-dreams-count").textContent = dreams.length ? `${ui.numeric(dreams.length)}` : "";
  fill(ui, "watcher-memories", rows(ui, memories, "Moments it keeps: first finds, ships lost, the commanders you flew with. Weeks later it brings them up.", (row) => esc(row.text)));
  fill(ui, "watcher-answers", rows(ui, answers, "Your answers, kept. It brings them back.",
    (row) => `<small>${esc(row.asked)}</small>${row.unanswered ? "<em>You didn't answer.</em>" : esc(row.answer)}`));
  fill(ui, "watcher-dreams", rows(ui, dreams, "When you log off, it dreams. They're written down here.", (row) => esc(row.text)));
  fill(ui, "watcher-met", met.length ? rows(ui, met, "", (row) => `<small>${esc(row.name || "A commander")}'s Watcher</small>${esc(row.nature || "")}${row.chapter ? `, at chapter ${esc(row.chapter)}` : ""}${row.road ? ` · ${row.road === "open" ? "looking back" : "eye closed"}` : ""}`) : "");
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

// The tabs before 5.6.1, to the ones that took their place.
const OLD_TABS = {overview: "now", together: "you"};
let watcherTab = "now";
try { watcherTab = window.localStorage.getItem("voidcompass.watcherTab") || "now"; } catch (_error) { /* private */ }

function showTab(root, tab) {
  tab = OLD_TABS[tab] || tab;
  watcherTab = ["now", "story", "you", "said", "settings", "voice", "mind", "library"].includes(tab) ? tab : "now";
  root.querySelectorAll("[data-watcher-panel]").forEach((panel) => { panel.hidden = panel.dataset.watcherPanel !== watcherTab; });
  root.querySelectorAll("[data-watcher-tab]").forEach((button) => {
    button.setAttribute("aria-selected", button.dataset.watcherTab === watcherTab ? "true" : "false");
  });
  try { window.localStorage.setItem("voidcompass.watcherTab", watcherTab); } catch (_error) { /* private */ }
  if (watcherTab === "mind") mindToNewest();
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

// Your name (5.7.1): the name the ship writes, what it calls you, and how
// it says it aloud. Kept in its memory of this commander.
function namePanel() {
  return `<section class="watcher-card watcher-wide watcher-name" aria-label="Your name">
    <header><span>YOUR NAME</span><b class="watcher-saved" id="watcher-name-saved"></b></header>
    <p class="watcher-note" id="watcher-name-note"></p>
    <div class="watcher-name-fields">
      <label class="studio-field"><span>It calls you<small>Commander every day; a name only for the moments that matter, once a session</small></span>
        <select id="watcher-name-call">${option("commander", "Commander")}${option("name", "Your name")}${option("nickname", "A name you choose")}</select></label>
      <label class="studio-field"><span>A name you choose<small>Used when it calls you by a name you choose</small></span>
        <input type="text" id="watcher-name-nickname" maxlength="24" spellcheck="false" autocomplete="off"></label>
      <label class="studio-field"><span>How it says your name<small>Write it the way it sounds. Empty, it works it out</small></span>
        <span class="watcher-name-say"><input type="text" id="watcher-name-spoken" maxlength="60" spellcheck="false" autocomplete="off">
          <button type="button" id="watcher-name-hear">HEAR IT</button></span></label>
    </div>
  </section>`;
}

function wireName(root, ui) {
  const send = async (operation, extra = {}) => ui.command("workspace", {page: "watcher", operation, ...extra});
  root.querySelector("#watcher-name-call").addEventListener("change", async (event) => {
    savedNote("watcher-name-saved", await send("name_call", {value: event.target.value}));
  });
  for (const [id, operation] of [["#watcher-name-nickname", "name_nickname"], ["#watcher-name-spoken", "name_spoken"]]) {
    root.querySelector(id).addEventListener("change", async (event) => {
      savedNote("watcher-name-saved", await send(operation, {value: event.target.value}));
    });
  }
  root.querySelector("#watcher-name-hear").addEventListener("click", async () => {
    const spoken = root.querySelector("#watcher-name-spoken");
    if (!(await send("name_hear", {value: spoken.value || spoken.placeholder}))) ui.showToast("The voice isn't ready");
  });
}

function renderName(name, ui) {
  const known = String(name.known || "");
  const call = ["commander", "name", "nickname"].includes(name.call) ? name.call : "commander";
  const nickname = String(name.nickname || "");
  const told = Array.isArray(name.told) ? name.told.length : 0;
  let note = "It hasn't read your name yet. It will the next time you load the game.";
  if (known) {
    note = `The ship writes ${known} every time you wake it.`;
    if (!name.call) note += told ? " It has noticed, and will ask you about it. Or choose here." : " Choose what it calls you here, or wait for it to ask.";
    else if (call === "name") note += " It may use it now and then, never more than once a session.";
    else if (call === "nickname") note += nickname ? ` It calls you ${nickname} now and then.` : " Write the name you'd like below.";
    else note += " It calls you Commander.";
  }
  ui.byId("watcher-name-note").textContent = note;
  const select = ui.byId("watcher-name-call");
  if (document.activeElement !== select) select.value = call;
  select.disabled = !known;
  const nick = ui.byId("watcher-name-nickname");
  if (document.activeElement !== nick) nick.value = nickname;
  const spoken = ui.byId("watcher-name-spoken");
  if (document.activeElement !== spoken) spoken.value = String(name.spoken || "");
  spoken.placeholder = String(name.spoken_auto || "");
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

// Its own mind (5.7.1, experimental): a small model on this PC (Qwen3.5, run
// by llama.cpp) puts its everyday thoughts in fresh words, thinks a little of
// its own, keeps a diary of your sessions and answers when you talk to it.
// Its rules decide what may be said; its story stays as written.
const MIND_STATES = {
  off: ["DORMANT", "It speaks its written lines. Wake it, and it finds its own words."],
  missing: ["NOT YET HERE", "Its mind isn't on this PC yet. Waking it downloads it first."],
  download: ["ARRIVING", "Its mind is downloading into the models folder beside Void Compass."],
  loading: ["WAKING", "Loading the model. A few seconds."],
  ready: ["AWAKE", "Everything it says comes from its own mind now. Its story stays as written."],
  thinking: ["THINKING", "Choosing its words."],
  error: ["IT WON'T WAKE", "The model couldn't load."],
};
const MIND_PROMPTS = ["Where are we?", "What did we do last time?", "How are you today?",
  "What do you make of this system?", "Tell me something you noticed."];
const MIND_STAGES = {starting: "Starting…", engine: "Downloading llama.cpp…", unpacking: "Unpacking llama.cpp…",
  model: "Downloading the model…", search: "Downloading its library search…", done: "Done", cancelled: "Cancelled",
  failed: "Failed"};
// What a line of what it has seen is about, for the timeline's marker.
const SEEN_KINDS = [[/^(jumped|rode the carrier)/i, "JUMP"], [/^docked/i, "DOCK"], [/^(landed|stepped|took the srv)/i, "LAND"],
  [/kinds of life|sampler|codex/i, "LIFE"], [/^(scanned|found every|mapped)/i, "SCAN"], [/^sold/i, "SALE"],
  [/destroyed|interdiction/i, "RISK"], [/^promoted/i, "RANK"], [/^(bought|switched to)/i, "SHIP"],
  [/mission/i, "TASK"], [/shut the game/i, "REST"]];

function mindCore() {
  const nodes = [0, 60, 120, 180, 240, 300].map((angle, index) => {
    const radius = index % 2 ? 62 : 78;
    const x = (100 + radius * Math.cos(angle * Math.PI / 180)).toFixed(1);
    const y = (100 + radius * Math.sin(angle * Math.PI / 180)).toFixed(1);
    return `<path class="mind-synapse" style="--i:${index}" d="M100 100 L${x} ${y}"></path><circle class="mind-node" style="--i:${index}" cx="${x}" cy="${y}" r="4"></circle>`;
  }).join("");
  return `<svg class="mind-core-art" viewBox="0 0 200 200" aria-hidden="true">
    <defs><radialGradient id="mind-iris" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="currentColor" stop-opacity=".95"></stop>
      <stop offset="45%" stop-color="currentColor" stop-opacity=".35"></stop>
      <stop offset="100%" stop-color="currentColor" stop-opacity="0"></stop></radialGradient></defs>
    <circle class="mind-ring mind-ring-outer" cx="100" cy="100" r="94"></circle>
    <circle class="mind-ring mind-ring-dash" cx="100" cy="100" r="86"></circle>
    <circle class="mind-ring mind-ring-mid" cx="100" cy="100" r="62"></circle>
    <g class="mind-web">${nodes}</g>
    <circle class="mind-ring mind-ring-inner" cx="100" cy="100" r="34"></circle>
    <circle class="mind-glow" cx="100" cy="100" r="30" fill="url(#mind-iris)"></circle>
    <circle class="mind-pupil" cx="100" cy="100" r="9"></circle>
  </svg>`;
}

function mindPanel() {
  const prompts = MIND_PROMPTS.map((text) => `<button type="button" class="mind-prompt" data-mind-prompt="${text}">${text}</button>`).join("");
  return `<section class="mind-hero" id="mind-hero" data-state="off" aria-label="Its own mind">
    <div class="mind-core">${mindCore()}<span class="mind-core-label" id="mind-core-label">DORMANT</span></div>
    <div class="mind-hero-text">
      <small class="mind-kicker">THE WATCHER · ITS OWN MIND <em>EXPERIMENTAL</em></small>
      <h2 id="mind-title">DORMANT</h2>
      <p id="mind-subtitle">It says only what was written for it.</p>
      <div class="mind-chips"><span id="mind-chip-model">QWEN3.5</span><span id="mind-chip-device">GRAPHICS CARD</span><span>ON THIS PC ONLY</span></div>
      <div class="watcher-voice-progress mind-progress" id="watcher-mind-progress" hidden><i></i><span></span></div>
      <p class="mind-error" id="watcher-mind-error" hidden></p>
      <div class="mind-hero-actions">
        <label class="mind-wake"><input type="checkbox" id="watcher-mind-on"><i></i><span id="watcher-mind-state">WAKE IT</span></label>
        <button type="button" class="mind-button" id="watcher-mind-download">DOWNLOAD · <b id="watcher-mind-size"></b> MB</button>
        <button type="button" class="mind-button" id="watcher-mind-cancel" hidden>CANCEL</button>
      </div>
    </div>
    <dl class="mind-readouts">
      <div><dt>IN ITS OWN WORDS</dt><dd id="mind-stat-written">0</dd></div>
      <div><dt>KEPT BACK</dt><dd id="mind-stat-kept">0</dd></div>
      <div><dt>LAST ANSWER</dt><dd id="mind-stat-speed">—</dd></div>
      <div><dt>DIARY ENTRIES</dt><dd id="mind-stat-diary">0</dd></div>
      <div><dt>THINGS SEEN</dt><dd id="mind-stat-seen">0</dd></div>
    </dl>
  </section>
  <div class="mind-main">
    <section class="mind-console" aria-label="Talk to it">
      <header><span>TALK TO IT</span><b id="watcher-talk-state"></b></header>
      <ol class="mind-transcript" id="watcher-talk-log"></ol>
      <div class="mind-typing" id="mind-typing" hidden><i></i><i></i><i></i><span>IT IS CHOOSING ITS WORDS</span></div>
      <div class="mind-prompts" id="mind-prompts">${prompts}</div>
      <div class="mind-say">
        <textarea id="watcher-talk-text" rows="2" maxlength="400" placeholder="Say something to the Watcher…" spellcheck="true"></textarea>
        <button type="button" class="mind-mic" id="watcher-talk-mic" data-stage="idle" title="Hold to talk" aria-label="Talk by voice" hidden><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"></rect><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"></path></svg></button>
        <button type="button" class="mind-send" id="watcher-talk-send">SAY IT</button>
      </div>
      <footer><p id="watcher-talk-note"></p><button type="button" class="mind-link" id="watcher-talk-forget">FORGET THIS TALK</button></footer>
    </section>
    <section class="mind-card mind-record" aria-label="Its record">
      <nav class="mind-record-tabs" role="tablist">
        <button type="button" role="tab" data-mind-record="said" aria-selected="true">WHAT IT SAID <b id="mind-said-count"></b></button>
        <button type="button" role="tab" data-mind-record="diary" aria-selected="false">ITS DIARY <b id="watcher-diary-count"></b></button>
        <button type="button" role="tab" data-mind-record="seen" aria-selected="false">WHAT IT SAW</button>
      </nav>
      <div class="mind-record-body" data-mind-record-panel="said">
        <p class="watcher-note">👍 a line it said in its own words and it becomes its tone for that moment; 👎 one and it steers clear of anything like it. Talk replies too.</p>
        <ol class="mind-said" id="watcher-said"></ol>
      </div>
      <div class="mind-record-body" data-mind-record-panel="diary" hidden>
        <ol class="mind-diary-list" id="watcher-diary"></ol>
        <p class="watcher-note" id="watcher-diary-note"></p>
      </div>
      <div class="mind-record-body" data-mind-record-panel="seen" hidden>
        <p class="watcher-note">From your journal, newest first: everything it may think about.</p>
        <ol class="mind-timeline" id="watcher-seen"></ol>
      </div>
    </section>
  </div>
  <div class="mind-lower">
  <section class="mind-card mind-settings" aria-label="Its settings">
    <header><span>HOW IT THINKS</span><b class="watcher-saved" id="watcher-mind-saved"></b></header>
      <div class="mind-fields">
        <label class="studio-field"><span>Model<small>Standard writes better; Light is half the size, for smaller graphics cards</small></span>
          <select id="watcher-mind-model"></select></label>
        <label class="studio-field"><span>Runs on<small>The graphics card is quickest; the CPU leaves the graphics card to the game</small></span>
          <select id="watcher-mind-device">${option("gpu", "Graphics card")}${option("cpu", "CPU only")}</select></label>
        <label class="studio-switch"><span><b>Its own words for everything</b><small>Awake, all it says comes from its mind, but its story and its questions. Off: its written lines, and only TALK TO IT uses the mind</small></span>
          <input type="checkbox" id="watcher-mind-reword"><i></i></label>
        <label class="studio-switch"><span><b>Its own thoughts</b><small>Now and then, something it noticed about your flying, at the pace of its Thoughts setting</small></span>
          <input type="checkbox" id="watcher-mind-own"><i></i></label>
        <label class="studio-switch"><span><b>Keeps a diary</b><small>A few lines about each session it watched, from what the journal says</small></span>
          <input type="checkbox" id="watcher-mind-diary"><i></i></label>
        <label class="studio-switch"><span><b>Free memory when idle</b><small>Unloads the model after ten quiet minutes; its next words take a few seconds longer</small></span>
          <input type="checkbox" id="watcher-mind-idle"><i></i></label>
      </div>
  </section>
  <section class="mind-card mind-hear" id="mind-hear" data-stage="off" aria-label="Talk by voice">
    <header><span>TALK BY VOICE</span><b class="watcher-saved" id="watcher-hear-saved"></b></header>
      <div class="mind-fields">
        <label class="studio-switch"><span><b>Talk to it by voice</b><small>Hold your talk key (or the microphone by SAY IT), speak, let go: it answers as if you'd typed it</small></span>
          <input type="checkbox" id="watcher-hear-on"><i></i></label>
        <div class="watcher-voice-progress mind-progress" id="watcher-hear-progress" hidden><i></i><span></span></div>
        <p class="mind-error" id="watcher-hear-error" hidden></p>
        <div class="mind-hear-actions">
          <button type="button" class="mind-button" id="watcher-hear-download">DOWNLOAD ITS HEARING · <b id="watcher-hear-size"></b> MB</button>
          <button type="button" class="mind-button" id="watcher-hear-cancel" hidden>CANCEL</button>
        </div>
        <label class="studio-field"><span>Microphone<small>Windows' default follows your Sound settings</small></span>
          <select id="watcher-hear-mic"></select></label>
        <label class="studio-field"><span>Talk key<small>Hold: it listens while the key is down. Tap: once to start, again to stop</small></span>
          <select id="watcher-hear-mode">${option("hold", "Hold to talk")}${option("tap", "Tap to start and stop")}</select></label>
        <div class="mind-hear-key"><span>THE KEY</span><kbd id="watcher-hear-key">NONE</kbd><small id="watcher-hear-key-note">Change it in Settings › Hotkeys</small></div>
      </div>
      <div class="mind-hear-test">
        <div class="mind-meter" id="watcher-hear-meter" aria-hidden="true"><i></i></div>
        <button type="button" class="mind-button" id="watcher-hear-test">TEST MIC</button>
        <button type="button" class="mind-button" id="watcher-hear-play" hidden>HEAR IT BACK</button>
      </div>
      <p class="watcher-note mind-hear-note" id="watcher-hear-note"></p>
      <p class="mind-notice" id="watcher-hear-notice"></p>
      <div class="mind-remove" id="watcher-hear-remove-row">
        <button type="button" class="mind-button" id="watcher-hear-remove">REMOVE ITS HEARING</button>
        <small>Deletes whisper.cpp and the speech model.</small>
      </div>
  </section>
  <section class="mind-card mind-voice" aria-label="Its voice">
    <header><span>ITS VOICE</span><b>YOURS TO SHAPE</b></header>
    <h3>YOU LIKED</h3><ol class="mind-votes" id="watcher-liked"></ol>
    <h3>IT STEERS CLEAR OF</h3><ol class="mind-votes" id="watcher-disliked"></ol>
  </section>
  <section class="mind-card mind-rules-card" aria-label="Its rules">
    <header><span>ITS RULES</span><b>ALWAYS</b></header>
      <div class="mind-rules">
        <ol>
          <li><b>It's told only what's true.</b> Your journal, its memory and its LIBRARY: what's built in, your sources and what you teach it, searched by meaning.</li>
          <li><b>Its story stays as written.</b> Its books, echoes, questions and warnings never come from the model.</li>
          <li><b>Every word is checked.</b> A made-up name or number, another language, talk of AI, or anything it never speaks of: never shown.</li>
          <li><b>It stays on this PC.</b> Nothing you say to it leaves your computer.</li>
        </ol>
        <p class="mind-notice" id="watcher-mind-notice"></p>
        <p class="watcher-note" id="watcher-mind-status"></p>
        <div class="mind-remove" id="watcher-mind-remove-row">
          <button type="button" class="mind-button" id="watcher-mind-remove">REMOVE THE MODEL FILES</button>
          <small>Deletes llama.cpp and the models. Waking it again downloads them again.</small>
        </div>
      </div>
  </section>
  </div>`;
}

let mindRemoveArmed = 0;
let hearRemoveArmed = 0;
// Talking by voice (5.7.1): the page's last word on it, and the meter's own quick loop.
let hearState = {};
let hearPoll = 0;
let hearAsking = false;
const HEAR_STAGES = {starting: "Starting…", engine: "Downloading whisper.cpp…", unpacking: "Unpacking whisper.cpp…",
  model: "Downloading the speech model…", done: "Done", cancelled: "Cancelled", failed: "Failed"};
const HEAR_ACTIVE = ["opening", "listening", "test"];
let mindTalkKey = "";
let mindVoiceKey = "";
let mindRecord = "said";
let mindDiaryKey = "";
let mindSeenKey = "";

// The talk opens at its newest words (drawn while the tab was hidden, it
// stayed wherever it was, half a reply showing above the prompts).
function mindToNewest() {
  const log = document.getElementById("watcher-talk-log");
  if (log) requestAnimationFrame(() => { log.scrollTop = log.scrollHeight; });
}
// What the vote buttons point at: lines by list and place (never text in markup).
const mindLines = {said: [], talk: [], liked: [], disliked: []};
function wireMind(root, ui) {
  const send = async (operation, extra = {}) => ui.command("workspace", {page: "watcher", operation, ...extra});
  // Its record: one of what it said, its diary and what it saw at a time.
  const record = root.querySelector(".mind-record");
  const showRecord = (name) => {
    mindRecord = ["said", "diary", "seen"].includes(name) ? name : "said";
    record.querySelectorAll("[data-mind-record]").forEach((tab) => tab.setAttribute("aria-selected", String(tab.dataset.mindRecord === mindRecord)));
    record.querySelectorAll("[data-mind-record-panel]").forEach((panel) => { panel.hidden = panel.dataset.mindRecordPanel !== mindRecord; });
    try { window.localStorage.setItem("voidcompass.watcher.mindRecord", mindRecord); } catch (_error) { /* private */ }
  };
  record.querySelector(".mind-record-tabs").addEventListener("click", (event) => {
    const tab = event.target.closest("[data-mind-record]");
    if (tab) showRecord(tab.dataset.mindRecord);
  });
  try { showRecord(window.localStorage.getItem("voidcompass.watcher.mindRecord") || "said"); } catch (_error) { showRecord("said"); }
  // 👍 / 👎 (5.7.1): pressed again, the vote is taken back.
  root.querySelector('[data-watcher-panel="mind"]')?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-mind-vote]");
    if (!button) return;
    const row = (mindLines[button.dataset.mindList] || [])[Number(button.dataset.mindIndex)];
    if (!row) return;
    const vote = button.getAttribute("aria-pressed") === "true" ? "clear" : button.dataset.mindVote;
    send("mind_rate", {text: row.text, topic: row.topic || "", vote});
  });
  root.querySelector("#watcher-mind-on").addEventListener("change", async (event) => {
    savedNote("watcher-mind-saved", await send("mind_toggle", {value: event.target.checked}));
  });
  root.querySelector("#watcher-mind-download").addEventListener("click", () => send("mind_download"));
  root.querySelector("#watcher-mind-cancel").addEventListener("click", () => send("mind_cancel"));
  for (const [id, key] of [["#watcher-mind-model", "watcher_llm_model"], ["#watcher-mind-device", "watcher_llm_device"]]) {
    root.querySelector(id).addEventListener("change", async (event) => {
      savedNote("watcher-mind-saved", await send("mind_settings", {values: {[key]: event.target.value}}));
    });
  }
  for (const [id, key] of [["#watcher-mind-reword", "watcher_llm_reword"], ["#watcher-mind-idle", "watcher_llm_free_idle"],
    ["#watcher-mind-own", "watcher_llm_own_thoughts"], ["#watcher-mind-diary", "watcher_llm_diary"]]) {
    root.querySelector(id).addEventListener("change", async (event) => {
      savedNote("watcher-mind-saved", await send("mind_settings", {values: {[key]: event.target.checked}}));
    });
  }
  const remove = root.querySelector("#watcher-mind-remove");
  remove.addEventListener("click", async () => {
    if (!mindRemoveArmed) {
      remove.textContent = "PRESS AGAIN TO REMOVE";
      mindRemoveArmed = window.setTimeout(() => { mindRemoveArmed = 0; remove.textContent = "REMOVE THE MODEL FILES"; }, 4000);
      return;
    }
    window.clearTimeout(mindRemoveArmed);
    mindRemoveArmed = 0;
    remove.textContent = "REMOVE THE MODEL FILES";
    ui.showToast((await send("mind_remove")) ? "The model files are removed" : "Some model files couldn't be removed");
  });
  const text = root.querySelector("#watcher-talk-text");
  const say = async (words) => {
    words = String(words || "").trim();
    if (!words) return;
    if (await send("mind_talk", {text: words})) {
      if (text.value.trim() === words) text.value = "";
    } else ui.showToast("It can't answer yet");
  };
  root.querySelector("#watcher-talk-send").addEventListener("click", () => say(text.value));
  text.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); say(text.value); }
  });
  root.querySelector("#mind-prompts").addEventListener("click", (event) => {
    const prompt = event.target.closest("[data-mind-prompt]");
    if (prompt && !prompt.disabled) say(prompt.dataset.mindPrompt);
  });
  root.querySelector("#watcher-talk-forget").addEventListener("click", () => send("mind_forget"));
  wireHear(root, ui, send);
}

// Talking by voice (5.7.1): the microphone button (held or tapped, as the
// talk key is), and the TALK BY VOICE card.
function wireHear(root, ui, send) {
  const mic = root.querySelector("#watcher-talk-mic");
  const start = () => { hearState = {...hearState, stage: "opening"}; drawHearLive(ui, {stage: "opening", level: 0}); send("listen_start"); hearLoop(ui); };
  const stop = () => { if (HEAR_ACTIVE.includes(hearState.stage)) send("listen_stop"); };
  let held = false;
  mic.addEventListener("pointerdown", (event) => {
    if (mic.disabled || hearState.mode === "tap" || event.button !== 0) return;
    held = true;
    mic.setPointerCapture?.(event.pointerId);
    start();
  });
  const release = () => { if (held) { held = false; stop(); } };
  for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) mic.addEventListener(name, release);
  mic.addEventListener("click", () => {
    if (mic.disabled || hearState.mode !== "tap") return;
    if (HEAR_ACTIVE.includes(hearState.stage)) stop(); else start();
  });
  mic.addEventListener("keydown", (event) => {
    if ((event.key !== " " && event.key !== "Enter") || event.repeat || hearState.mode === "tap" || mic.disabled) return;
    event.preventDefault();
    held = true;
    start();
  });
  mic.addEventListener("keyup", (event) => { if (event.key === " " || event.key === "Enter") release(); });
  window.addEventListener("blur", release);

  root.querySelector("#watcher-hear-on").addEventListener("change", async (event) => {
    savedNote("watcher-hear-saved", await send("listen_toggle", {value: event.target.checked}));
  });
  root.querySelector("#watcher-hear-download").addEventListener("click", () => send("listen_download"));
  root.querySelector("#watcher-hear-cancel").addEventListener("click", () => send("listen_cancel"));
  for (const [id, key] of [["#watcher-hear-mic", "watcher_listen_mic"], ["#watcher-hear-mode", "watcher_listen_mode"]]) {
    root.querySelector(id).addEventListener("change", async (event) => {
      savedNote("watcher-hear-saved", await send("listen_settings", {values: {[key]: event.target.value}}));
    });
  }
  root.querySelector("#watcher-hear-test").addEventListener("click", async () => {
    if (await send("listen_test")) {
      hearState = {...hearState, stage: "opening", testing: true};
      hearLoop(ui);
    }
  });
  root.querySelector("#watcher-hear-play").addEventListener("click", () => {
    const sound = new Audio(ui.apiUrl(`/api/data/listen-test?at=${Date.now()}`));
    sound.play().catch(() => ui.showToast("It couldn't be played"));
  });
  const remove = root.querySelector("#watcher-hear-remove");
  remove.addEventListener("click", async () => {
    if (!hearRemoveArmed) {
      remove.textContent = "PRESS AGAIN TO REMOVE";
      hearRemoveArmed = window.setTimeout(() => { hearRemoveArmed = 0; remove.textContent = "REMOVE ITS HEARING"; }, 4000);
      return;
    }
    window.clearTimeout(hearRemoveArmed);
    hearRemoveArmed = 0;
    remove.textContent = "REMOVE ITS HEARING";
    ui.showToast((await send("listen_remove")) ? "Its hearing is removed" : "Some of its files couldn't be removed");
  });
}

// The level meter's loop: one at a time, quick only while the microphone is open.
async function hearLoop(ui) {
  if (hearAsking) return;
  window.clearTimeout(hearPoll);
  hearAsking = true;
  let live = null;
  try {
    const response = await fetch(ui.apiUrl("/api/data/listen"), {cache: "no-store"});
    live = response.ok ? await response.json() : null;
  } catch (_error) {
    live = null;
  }
  hearAsking = false;
  if (live) drawHearLive(ui, live);
  const open = live && HEAR_ACTIVE.includes(live.stage);
  // Asked once more after the page's press reaches the app (opening takes a moment).
  if (open || (live && live.stage === "idle" && HEAR_ACTIVE.includes(hearState.stage) && !hearState.settled)) {
    if (!open) hearState = {...hearState, settled: true};
    hearPoll = window.setTimeout(() => hearLoop(ui), document.hidden ? 500 : 100);
  }
}

function drawHearLive(ui, live) {
  const level = Math.min(1, (Number(live.level) || 0) * 6);
  const open = HEAR_ACTIVE.includes(live.stage);
  const meter = ui.byId("watcher-hear-meter");
  if (meter) meter.style.setProperty("--level", open ? String(level) : "0");
  const mic = ui.byId("watcher-talk-mic");
  if (mic) {
    mic.dataset.stage = live.stage === "test" ? "idle" : live.stage || "idle";
    mic.style.setProperty("--level", live.stage === "listening" ? String(level) : "0");
  }
  const note = ui.byId("watcher-hear-note");
  if (note && open) note.textContent = live.stage === "opening" ? "Opening the microphone…"
    : live.stage === "test" ? `Testing… say something. ${Number(live.seconds || 0).toFixed(1)} s`
    : `Listening… ${Number(live.seconds || 0).toFixed(1)} s`;
}

function renderHear(listen, mind, ui) {
  const card = ui.byId("mind-hear");
  if (!card) return;
  hearState = {...listen, settled: false};
  const download = listen.download || {};
  const busy = ["starting", "engine", "unpacking", "model"].includes(download.stage);
  const ready = Boolean(listen.enabled && listen.installed);
  card.dataset.stage = listen.stage || "off";
  ui.byId("watcher-hear-on").checked = Boolean(listen.enabled);
  ui.byId("watcher-hear-size").textContent = ui.numeric(listen.download_mb);
  ui.byId("watcher-hear-download").hidden = Boolean(listen.installed) || busy || !listen.enabled;
  ui.byId("watcher-hear-cancel").hidden = !busy;
  const progress = ui.byId("watcher-hear-progress");
  progress.hidden = !busy;
  if (busy) {
    const share = Math.round(100 * (Number(download.done) || 0) / Math.max(1, Number(download.total) || 1));
    progress.style.setProperty("--done", `${share}%`);
    progress.querySelector("span").textContent = `${HEAR_STAGES[download.stage] || ""} ${share}%`;
  }
  const error = ui.byId("watcher-hear-error");
  error.hidden = download.stage !== "failed";
  error.textContent = download.stage === "failed" ? `The download failed: ${download.error}. Try again in a moment.` : "";

  const mics = Array.isArray(listen.mics) ? listen.mics : [];
  const select = ui.byId("watcher-hear-mic");
  const chosen = String(listen.mic || "");
  const names = chosen && !mics.includes(chosen) ? [...mics, chosen] : mics;
  const options = `<option value="">Windows' default</option>` + names.map((name) => `<option value="${ui.escapeHtml(name)}">`
    + `${ui.escapeHtml(name)}${mics.includes(name) ? "" : " · not connected"}</option>`).join("");
  if (select.dataset.options !== options) { select.innerHTML = options; select.dataset.options = options; }
  if (document.activeElement !== select) select.value = chosen;
  const mode = ui.byId("watcher-hear-mode");
  if (document.activeElement !== mode) mode.value = listen.mode === "tap" ? "tap" : "hold";
  ui.byId("watcher-hear-key").textContent = listen.hotkey || "NONE";
  ui.byId("watcher-hear-key-note").textContent = !listen.hotkey ? "No key yet: set one in Settings › Hotkeys"
    : listen.hotkeys_on === false ? "Hotkeys are off in Settings › Hotkeys" : "Change it in Settings › Hotkeys";
  for (const id of ["watcher-hear-mic", "watcher-hear-mode"]) ui.byId(id).disabled = !listen.enabled;
  const open = HEAR_ACTIVE.includes(listen.stage);
  const test = ui.byId("watcher-hear-test");
  test.disabled = !ready || open || listen.stage === "hearing";
  test.textContent = listen.testing && open ? "LISTENING…" : listen.testing && listen.stage === "hearing" ? "HEARING…" : "TEST MIC";
  ui.byId("watcher-hear-play").hidden = !listen.has_test || open;
  ui.byId("watcher-hear-remove-row").hidden = !listen.installed;
  ui.byId("watcher-hear-notice").textContent = listen.notice || "";
  if (!open) {
    ui.byId("watcher-hear-note").textContent = listen.stage === "hearing" ? "Working out what you said…"
      : listen.note || (!listen.enabled ? "Off. Switched on, its hearing downloads once (whisper.cpp and Whisper's small English model)."
        : !listen.installed ? "Its hearing isn't here yet." : listen.blocked || "Ready: hold your talk key and speak.");
  }

  // The button by SAY IT, there once its hearing is.
  const mic = ui.byId("watcher-talk-mic");
  mic.hidden = !ready;
  mic.disabled = !ready || Boolean(listen.blocked) || listen.stage === "hearing" || Boolean(mind.waiting);
  mic.title = listen.blocked || (listen.mode === "tap" ? "Click to talk, click again to stop" : "Hold to talk");
  // While the microphone is open the meter's loop draws it; redrawn here, it blinked to nothing.
  if (open) hearLoop(ui);
  else drawHearLive(ui, {stage: listen.stage, level: 0, seconds: 0});
  if (listen.stage === "hearing") ui.byId("watcher-talk-state").textContent = "HEARING YOU…";
}

function mindClock(seconds) {
  const at = Number(seconds);
  if (!at) return "";
  const when = new Date(at * 1000);
  const today = new Date().toDateString() === when.toDateString();
  return today ? when.toLocaleTimeString(undefined, {hour: "2-digit", minute: "2-digit"})
    : when.toLocaleDateString(undefined, {day: "numeric", month: "short"}).toUpperCase();
}

function renderMind(mind, ui) {
  const panel = ui.byId("watcher-workspace")?.querySelector('[data-watcher-panel="mind"]');
  if (!panel) return;
  const download = mind.download || {};
  const busy = ["starting", "engine", "unpacking", "model", "search"].includes(download.stage);
  const ready = mind.stage === "ready";
  const state = !mind.enabled ? (busy ? "download" : "off") : busy ? "download" : !mind.installed ? "missing"
    : mind.stage === "loading" ? "loading" : mind.stage === "error" ? "error" : mind.waiting ? "thinking" : ready ? "ready" : "loading";
  const [title, subtitle] = MIND_STATES[state];
  const hero = ui.byId("mind-hero");
  hero.dataset.state = state;
  ui.byId("mind-title").textContent = title;
  ui.byId("mind-core-label").textContent = title;
  ui.byId("mind-subtitle").textContent = state === "error" ? `${subtitle} ${mind.error || ""}`.trim() : subtitle;
  ui.byId("watcher-mind-badge").textContent = mind.enabled && ready ? " · AWAKE" : "";
  const models = Array.isArray(mind.models) ? mind.models : [];
  const chosen = models.find((row) => row.id === mind.model) || {};
  ui.byId("mind-chip-model").textContent = String(chosen.name || "Qwen3.5").toUpperCase();
  ui.byId("mind-chip-device").textContent = mind.device === "cpu" ? "CPU ONLY" : "GRAPHICS CARD";

  const wake = ui.byId("watcher-mind-on");
  wake.checked = Boolean(mind.enabled);
  ui.byId("watcher-mind-state").textContent = mind.enabled ? "AWAKE · LET IT REST" : "WAKE IT";
  ui.byId("watcher-mind-size").textContent = ui.numeric(mind.download_mb);
  ui.byId("watcher-mind-download").hidden = Boolean(mind.installed) || busy;
  ui.byId("watcher-mind-cancel").hidden = !busy;
  const progress = ui.byId("watcher-mind-progress");
  progress.hidden = !busy;
  if (busy) {
    const share = Math.round(100 * (Number(download.done) || 0) / Math.max(1, Number(download.total) || 1));
    progress.style.setProperty("--done", `${share}%`);
    progress.querySelector("span").textContent = `${MIND_STAGES[download.stage] || ""} ${share}%`;
  }
  const error = ui.byId("watcher-mind-error");
  error.hidden = download.stage !== "failed";
  error.textContent = download.stage === "failed" ? `The download failed: ${download.error}. Try again in a moment.` : "";

  const stats = mind.stats || {};
  const diary = Array.isArray(mind.diary) ? mind.diary : [];
  ui.byId("mind-stat-written").textContent = ui.numeric(stats.written || 0);
  ui.byId("mind-stat-kept").textContent = ui.numeric(stats.rejected || 0);
  ui.byId("mind-stat-speed").textContent = Number(stats.seconds) ? `${Number(stats.seconds).toFixed(1)} s` : "—";
  ui.byId("mind-stat-diary").textContent = ui.numeric(diary.length);
  ui.byId("mind-stat-seen").textContent = ui.numeric(mind.seen_count || 0);

  // The conversation, kept as it was unless something changed (no flicker,
  // and it stays scrolled to the newest words).
  const talk = Array.isArray(mind.talk) ? mind.talk : [];
  const liked = Array.isArray(mind.liked) ? mind.liked : [];
  const disliked = Array.isArray(mind.disliked) ? mind.disliked : [];
  const voteOf = (text) => liked.some((row) => row.text === text) ? "up" : disliked.some((row) => row.text === text) ? "down" : "";
  const votes = (list, index, vote) => `<span class="mind-vote-pair">`
    + `<button type="button" class="mind-vote" data-mind-vote="up" data-mind-list="${list}" data-mind-index="${index}" aria-pressed="${vote === "up"}" title="More like this" aria-label="More like this">👍</button>`
    + `<button type="button" class="mind-vote" data-mind-vote="down" data-mind-list="${list}" data-mind-index="${index}" aria-pressed="${vote === "down"}" title="Less like this" aria-label="Less like this">👎</button></span>`;
  mindLines.talk = talk.map((row) => ({text: row.it, topic: "talk"}));
  const key = JSON.stringify([talk, liked, disliked]);
  const log = ui.byId("watcher-talk-log");
  if (key !== mindTalkKey) {
    mindTalkKey = key;
    log.innerHTML = talk.length ? talk.map((row, index) => `<li class="mind-turn">
        <div class="mind-you"><small>YOU${row.voice ? " · SPOKEN" : ""} · ${ui.escapeHtml(mindClock(row.at))}</small><p>${ui.escapeHtml(row.you)}</p></div>
        ${row.it ? `<div class="mind-it"><small>THE WATCHER ${votes("talk", index, voteOf(row.it))}</small><p>${ui.escapeHtml(row.it)}</p></div>` : ""}</li>`).join("")
      : `<li class="mind-empty"><p>Nothing said yet. Ask it something: it knows where you are, what you've done lately and a little of the galaxy.</p></li>`;
    mindToNewest();
  }
  // Its voice: what it said in its own words, and your votes (redrawn only on change).
  const said = Array.isArray(mind.said) ? mind.said : [];
  const voiceKey = JSON.stringify([said, liked, disliked]);
  if (voiceKey !== mindVoiceKey) {
    mindVoiceKey = voiceKey;
    Object.assign(mindLines, {said, liked, disliked});
    ui.byId("mind-said-count").textContent = said.length ? ui.numeric(said.length) : "";
    const topicName = (topic) => String(topic || "").replace(/_/g, " ").toUpperCase();
    ui.byId("watcher-said").innerHTML = said.length ? said.map((row, index) => `<li>
        <small>${ui.escapeHtml(topicName(row.topic))} · ${ui.escapeHtml(mindClock(row.at))} ${votes("said", index, row.vote)}</small>
        <p>${ui.escapeHtml(row.text)}</p></li>`).join("")
      : `<li class="mind-empty"><p>Nothing in its own words yet. Wake it, and what it says turns up here.</p></li>`;
    const voted = (rows, list, empty) => rows.length ? rows.map((row, index) => `<li>
        <small>${ui.escapeHtml(topicName(row.topic))}</small><p>${ui.escapeHtml(row.text)}</p>
        <button type="button" class="lib-forget" data-mind-vote="clear" data-mind-list="${list}" data-mind-index="${index}" aria-pressed="true" title="Take this vote back" aria-label="Take this vote back">✕</button></li>`).join("")
      : `<li class="mind-empty"><p>${empty}</p></li>`;
    ui.byId("watcher-liked").innerHTML = voted(liked, "liked", "None yet: 👍 a line you liked.");
    ui.byId("watcher-disliked").innerHTML = voted(disliked, "disliked", "None yet: 👎 a line that missed.");
  }
  ui.byId("mind-typing").hidden = !mind.waiting;
  ui.byId("watcher-talk-state").textContent = mind.waiting ? "LISTENING…" : talk.length ? `${talk.length} EXCHANGED` : "";
  // Waking (just switched on, or another model): what you ask is answered once it's awake.
  const waking = Boolean(mind.enabled && mind.installed && mind.stage === "loading");
  const canTalk = Boolean(mind.enabled && (ready || waking) && mind.orb_on);
  ui.byId("watcher-talk-send").disabled = !canTalk || Boolean(mind.waiting);
  ui.byId("watcher-talk-text").disabled = !canTalk;
  panel.querySelectorAll("[data-mind-prompt]").forEach((button) => { button.disabled = !canTalk || Boolean(mind.waiting); });
  ui.byId("watcher-talk-note").textContent = !mind.orb_on
    ? "Its orb overlay is off: it answers beside the orb. Switch it on in Overlay Studio."
    : !mind.enabled ? "Wake it above, and it can answer you."
    : waking ? "It's waking. Ask now, and it answers as soon as it's awake."
    : !ready ? "It answers once it's awake."
    : "It won't speak of everything. Some things it keeps to itself.";

  // Redrawn only when they change: every refresh flickered them and dropped a text selection.
  const diaryKey = JSON.stringify(diary);
  if (diaryKey !== mindDiaryKey) {
    mindDiaryKey = diaryKey;
    ui.byId("watcher-diary").innerHTML = diary.map((row) => `<li><small>${ui.escapeHtml(mindClock(row.at))}</small>`
      + `<p>${ui.escapeHtml(row.text)}</p></li>`).join("");
  }
  ui.byId("watcher-diary-count").textContent = diary.length ? ui.numeric(diary.length) : "";
  ui.byId("watcher-diary-note").textContent = diary.length ? ""
    : mind.keeps_diary === false ? "Its diary is off (How it thinks, below)."
    : "Nothing yet. After a session with something in it, it writes a few lines the next time you fly together.";
  const seen = Array.isArray(mind.seen) ? mind.seen : [];
  const seenKey = JSON.stringify(seen);
  if (seenKey !== mindSeenKey) {
    mindSeenKey = seenKey;
    ui.byId("watcher-seen").innerHTML = seen.length ? seen.map((row) => {
      const kind = (SEEN_KINDS.find(([pattern]) => pattern.test(row.text)) || [null, "LOG"])[1];
      return `<li data-kind="${kind}"><b>${kind}</b><p>${ui.escapeHtml(row.text)}</p><small>${ui.escapeHtml(mindClock(row.at))}</small></li>`;
    }).join("") : `<li class="mind-empty"><p>Nothing yet: it learns as you fly.</p></li>`;
  }

  const model = ui.byId("watcher-mind-model");
  const options = models.map((row) => `<option value="${ui.escapeHtml(row.id)}">${ui.escapeHtml(row.name)} · ${ui.numeric(row.size_mb)} MB${row.installed ? " · downloaded" : ""}</option>`).join("");
  if (model.dataset.options !== options) { model.innerHTML = options; model.dataset.options = options; }
  if (document.activeElement !== model) model.value = mind.model || "standard";
  const device = ui.byId("watcher-mind-device");
  if (document.activeElement !== device) device.value = mind.device || "gpu";
  ui.byId("watcher-mind-reword").checked = mind.reword !== false;
  ui.byId("watcher-mind-idle").checked = Boolean(mind.free_idle);
  ui.byId("watcher-mind-own").checked = mind.own_thoughts !== false;
  ui.byId("watcher-mind-diary").checked = mind.keeps_diary !== false;
  ui.byId("watcher-mind-remove-row").hidden = !models.some((row) => row.installed);
  ui.byId("watcher-mind-notice").textContent = mind.notice || "";
  const reasons = Object.entries(stats.reasons || {}).sort((a, b) => b[1] - a[1]).slice(0, 3)
    .map(([reason, count]) => `${reason} (${count})`).join(", ");
  ui.byId("watcher-mind-status").textContent = reasons ? `Kept back this session for: ${reasons}.` : "";
}

// Its library (5.7.1): everything its own mind may draw on, yours to see. The
// galaxy as it knows it, what it knows of you, the notes it took from your
// talks, what you taught it, and how much of its story it may speak of.
function libraryPanel() {
  return `<section class="mind-hero lib-hero" data-state="ready" aria-label="Its library">
    <div class="lib-hero-text">
      <small class="mind-kicker">THE WATCHER · ITS LIBRARY</small>
      <h2>WHAT IT KNOWS</h2>
      <p>Everything its own mind may draw on when it talks to you or finds its own words. Nothing else: if it isn't here, or in your journal, it doesn't know it.</p>
    </div>
    <dl class="mind-readouts">
      <div><dt>OF THE GALAXY</dt><dd id="lib-stat-cards">0</dd></div>
      <div><dt>NOTES FROM YOUR TALKS</dt><dd id="lib-stat-notes">0</dd></div>
      <div><dt>TAUGHT BY YOU</dt><dd id="lib-stat-taught">0</dd></div>
      <div><dt>OF ITS STORY, TOLD</dt><dd id="lib-stat-story">0</dd></div>
    </dl>
  </section>
  <section class="mind-card lib-galaxy" aria-label="Search its library">
    <header><span>SEARCH ITS LIBRARY</span><b id="lib-galaxy-count"></b></header>
    <div class="lib-filter">
      <div class="lib-search-row">
        <input type="search" id="lib-search" placeholder="Ask it anything: who builds carriers? what fuel does a carrier burn? where is Colonia?" spellcheck="false" autocomplete="off">
        <b class="lib-search-mode" id="lib-search-mode"></b>
      </div>
      <p class="watcher-note" id="lib-search-note"></p>
      <div class="lib-subjects" id="lib-subjects"></div>
    </div>
    <div class="lib-cards" id="lib-cards"></div>
  </section>
  <section class="mind-card lib-sources" aria-label="Your sources">
    <header><span>YOUR SOURCES</span><b id="lib-sources-count"></b></header>
    <p class="watcher-note">Give it a page about Elite Dangerous to read, a wiki article or a guide, and it adds what it says to its library, on this PC. When you talk to it, it reads the best few cards for what you asked. It obeys each site's robots.txt, reads one page at a time, and never keeps anything that names what it doesn't speak of. Respect each site's terms.</p>
    <div class="lib-source-add">
      <input type="url" id="lib-source-url" placeholder="https://elite-dangerous.fandom.com/wiki/Fleet_Carrier" spellcheck="false" autocomplete="off">
      <label class="lib-source-follow"><input type="checkbox" id="lib-source-follow"> and the pages it links to, up to</label>
      <select id="lib-source-pages" aria-label="At most this many pages"></select>
      <button type="button" class="mind-send" id="lib-source-add">READ IT</button>
    </div>
    <p class="lib-teach-note" id="lib-source-note"></p>
    <div class="lib-source-progress" id="lib-source-progress" hidden>
      <div class="watcher-voice-progress"><i></i><span></span></div>
      <button type="button" class="mind-button" id="lib-source-cancel">CANCEL</button>
    </div>
    <ol class="lib-source-list" id="lib-sources"></ol>
  </section>
  <div class="lib-grid">
    <section class="mind-card lib-teach" aria-label="Teach it">
      <header><span>TEACH IT</span><b>YOURS TO WRITE</b></header>
      <p class="watcher-note">Tell it something it should know: where home is, your goals, your crew, your carrier's name. It uses what you write as true.</p>
      <div class="mind-say"><textarea id="lib-teach-text" rows="2" maxlength="200" placeholder="Our home is Jameson Memorial."></textarea>
        <button type="button" class="mind-send" id="lib-teach-add">TEACH IT</button></div>
      <p class="lib-teach-note" id="lib-teach-note"></p>
      <ol class="lib-notes" id="lib-taught"></ol>
    </section>
    <section class="mind-card lib-told" aria-label="What you've told it">
      <header><span>WHAT YOU'VE TOLD IT</span><b>FROM YOUR TALKS</b></header>
      <p class="watcher-note">After each talk it notes anything you said about yourself, in your own words. Delete any you'd rather it forgot.</p>
      <ol class="lib-notes" id="lib-notes"></ol>
    </section>
    <section class="mind-card lib-you" aria-label="What it knows of you">
      <header><span>WHAT IT KNOWS OF YOU</span><b>FROM YOUR JOURNAL</b></header>
      <blockquote class="lib-about" id="lib-about" hidden><p></p><cite></cite></blockquote>
      <ol class="lib-facts" id="lib-profile"></ol>
    </section>
    <section class="mind-card lib-story" aria-label="Its story, so far">
      <header><span>ITS STORY, SO FAR</span><b id="lib-story-count"></b></header>
      <p class="watcher-note" id="lib-story-note"></p>
      <ol class="lib-chapters" id="lib-chapters"></ol>
    </section>
  </div>
`;
}

let librarySubject = "";
let libraryKey = "";
let libraryGalaxy = [];
function wireLibrary(root, ui) {
  const send = async (operation, extra = {}) => ui.command("workspace", {page: "watcher", operation, ...extra});
  const text = root.querySelector("#lib-teach-text");
  const teach = async () => {
    const words = text.value.trim();
    if (!words) return;
    if (await send("mind_teach", {text: words})) text.value = "";
  };
  root.querySelector("#lib-teach-add").addEventListener("click", teach);
  text.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); teach(); }
  });
  root.querySelector("#lib-taught").addEventListener("click", (event) => {
    const button = event.target.closest("[data-lib-forget]");
    if (button) send("mind_unteach", {index: Number(button.dataset.libForget)});
  });
  root.querySelector("#lib-notes").addEventListener("click", (event) => {
    const button = event.target.closest("[data-lib-forget]");
    if (button) send("mind_forget_note", {index: Number(button.dataset.libForget)});
  });
  // Your sources (5.7.1): add, cancel, refresh, remove; searched as you type.
  const sourceUrl = root.querySelector("#lib-source-url");
  const addSource = async () => {
    const url = sourceUrl.value.trim();
    if (!url) return;
    const follow = root.querySelector("#lib-source-follow").checked;
    if (await send("library_add", {url, follow, pages: Number(root.querySelector("#lib-source-pages").value) || 1})) {
      sourceUrl.value = "";
    }
  };
  root.querySelector("#lib-source-add").addEventListener("click", addSource);
  sourceUrl.addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); addSource(); }
  });
  root.querySelector("#lib-source-cancel").addEventListener("click", () => send("library_cancel"));
  root.querySelector("#lib-sources").addEventListener("click", (event) => {
    const refresh = event.target.closest("[data-lib-source-refresh]");
    const remove = event.target.closest("[data-lib-source-remove]");
    if (refresh) send("library_refresh", {id: refresh.dataset.libSourceRefresh});
    if (remove) send("library_remove", {id: remove.dataset.libSourceRemove});
  });
  let searching = 0;
  root.querySelector("#lib-search").addEventListener("input", (event) => {
    renderGalaxy(ui);
    clearTimeout(searching);
    searching = setTimeout(() => send("library_search", {text: event.target.value.trim()}), 250);
  });
  root.querySelector("#lib-subjects").addEventListener("click", (event) => {
    const chip = event.target.closest("[data-lib-subject]");
    if (!chip) return;
    librarySubject = chip.dataset.libSubject;
    renderGalaxy(ui);
  });
}

const OWN_SOURCES = "YOUR SOURCES";
let librarySources = {query: "", results: [], cards: 0};
let librarySourcesKey = "";
let librarySourceListKey = "";
function renderGalaxy(ui) {
  const search = String(ui.byId("lib-search")?.value || "").trim().toLowerCase();
  const subjects = libraryGalaxy;
  const chips = [["", "ALL"], ...subjects.map((row) => [row.subject, row.subject])];
  if (librarySources.cards) chips.push([OWN_SOURCES, OWN_SOURCES]);
  ui.byId("lib-subjects").innerHTML = chips
    .map(([id, label]) => `<button type="button" class="lib-subject${id === librarySubject ? " active" : ""}" data-lib-subject="${ui.escapeHtml(id)}">${ui.escapeHtml(label)}</button>`).join("");
  const cards = [];
  for (const subject of subjects) {
    if (librarySubject && subject.subject !== librarySubject) continue;
    for (const card of subject.cards || []) {
      if (search && !`${card.title} ${card.text}`.toLowerCase().includes(search)) continue;
      cards.push(`<article class="lib-card"><small>${ui.escapeHtml(subject.subject)}</small><b>${ui.escapeHtml(card.title)}</b><p>${ui.escapeHtml(card.text)}</p></article>`);
    }
  }
  // Searching: once its answer for these words is back, its ranked cards (its
  // own and your sources', by meaning when it can) in place of the quick match.
  const answered = search && librarySources.query.toLowerCase().replace(/\s+/g, " ") === search.replace(/\s+/g, " ");
  if (answered) {
    cards.length = 0;
    for (const card of librarySources.results) {
      if (librarySubject === OWN_SOURCES && card.own) continue;
      if (librarySubject && librarySubject !== OWN_SOURCES && (card.own ? card.subject !== librarySubject : true)) continue;
      cards.push(`<article class="lib-card${card.own ? "" : " lib-card-source"}"><small>${ui.escapeHtml(card.own ? card.subject : card.host)}</small>`
        + `<b>${ui.escapeHtml(card.title)}</b><p>${ui.escapeHtml(card.text)}</p></article>`);
    }
  }
  const empty = librarySubject === OWN_SOURCES && !search
    ? `Search to see what it read from your sources: ${ui.numeric(librarySources.cards)} cards.`
    : search && !answered ? "Looking…" : "Nothing it knows matches that.";
  ui.byId("lib-cards").innerHTML = cards.length ? cards.join("") : `<p class="watcher-note">${empty}</p>`;
}

function renderSources(sources, ui) {
  const list = Array.isArray(sources.list) ? sources.list : [];
  ui.byId("lib-sources-count").textContent = list.length
    ? `${ui.numeric(list.length)} SOURCE${list.length === 1 ? "" : "S"} · ${ui.numeric(sources.cards || 0)} CARDS` : "";
  const pages = ui.byId("lib-source-pages");
  if (pages && !pages.options.length) {
    pages.innerHTML = (sources.pages || [1]).map((count) => `<option value="${count}"${count === 25 ? " selected" : ""}>${count} PAGE${count === 1 ? "" : "S"}</option>`).join("");
  }
  ui.byId("lib-source-note").textContent = sources.note || "";
  const state = sources.state || {};
  const progress = ui.byId("lib-source-progress");
  progress.hidden = !sources.running;
  if (sources.running) {
    const reading = list.find((row) => row.id === state.source) || {};
    progress.querySelector("i").style.width = `${Math.min(100, ((state.done || 0) / Math.max(1, state.total || 1)) * 100)}%`;
    progress.querySelector("span").textContent = `Reading ${reading.host || "the page"}… ${ui.numeric(state.done || 0)} of ${ui.numeric(state.total || 1)} pages`
      + (state.skipped ? `, ${ui.numeric(state.skipped)} skipped` : "");
  }
  ui.byId("lib-source-add").disabled = Boolean(sources.running);
  // Redrawn only when something changed: a redrawn button loses a click in progress.
  const key = JSON.stringify([list, sources.running]);
  if (key === librarySourceListKey) return;
  librarySourceListKey = key;
  ui.byId("lib-sources").innerHTML = list.length ? list.map((row) => {
    const when = row.fetched ? new Date(row.fetched * 1000).toLocaleDateString(undefined, {day: "numeric", month: "short"}) : "";
    const what = row.error ? `<em>${ui.escapeHtml(row.error)}</em>`
      : `${ui.numeric(row.pages || 0)} page${row.pages === 1 ? "" : "s"} · ${ui.numeric(row.cards || 0)} cards${when ? ` · read ${ui.escapeHtml(when)}` : ""}`;
    return `<li><div><b>${ui.escapeHtml(row.title || row.host)}</b><small>${ui.escapeHtml(row.host)}${row.follow ? ` · and its links, up to ${ui.numeric(row.pages_wanted)}` : ""}</small><p>${what}</p></div>`
      + `<button type="button" class="mind-button" data-lib-source-refresh="${ui.escapeHtml(row.id)}"${sources.running ? " disabled" : ""}>READ AGAIN</button>`
      + `<button type="button" class="lib-forget" data-lib-source-remove="${ui.escapeHtml(row.id)}" title="Remove this source and what it read" aria-label="Remove this source">✕</button></li>`;
  }).join("") : `<li class="mind-empty"><p>No sources yet. Its library is what's built in, and what you teach it.</p></li>`;
}

function renderLibrary(library, ui) {
  const panel = ui.byId("watcher-workspace")?.querySelector('[data-watcher-panel="library"]');
  if (!panel) return;
  const notes = Array.isArray(library.notes) ? library.notes : [];
  const taught = Array.isArray(library.taught) ? library.taught : [];
  const galaxy = Array.isArray(library.galaxy) ? library.galaxy : [];
  const sources = library.sources || {};
  const total = galaxy.reduce((sum, row) => sum + (row.cards || []).length, 0) + (sources.cards || 0);
  ui.byId("lib-stat-cards").textContent = ui.numeric(total);
  renderSources(sources, ui);
  ui.byId("lib-stat-notes").textContent = ui.numeric(notes.length);
  ui.byId("lib-stat-taught").textContent = ui.numeric(taught.length);
  ui.byId("lib-stat-story").textContent = ui.numeric(library.story_told || 0);
  const list = (rows, empty) => rows.length ? rows.map((row, index) => `<li><p>${ui.escapeHtml(row.text)}</p>`
    + `<button type="button" class="lib-forget" data-lib-forget="${index}" title="Forget this" aria-label="Forget this">✕</button></li>`).join("")
    : `<li class="mind-empty"><p>${empty}</p></li>`;
  ui.byId("lib-taught").innerHTML = list(taught, "Nothing yet.");
  ui.byId("lib-notes").innerHTML = list(notes, "Nothing yet. Talk to it on the MIND tab.");
  ui.byId("lib-teach-note").textContent = library.teach_note || "";
  // Its few sentences about you, condensed now and then from its notes and diary.
  const about = library.about || null;
  ui.byId("lib-about").hidden = !about;
  if (about) {
    ui.byId("lib-about").querySelector("p").textContent = about.text;
    ui.byId("lib-about").querySelector("cite").textContent = about.at
      ? `IN ITS OWN WORDS · ${new Date(about.at * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short" }).toUpperCase()}` : "IN ITS OWN WORDS";
  }
  const facts = [...(library.profile || []), ...(library.answers || [])];
  ui.byId("lib-profile").innerHTML = facts.length ? facts.map((line) => `<li>${ui.escapeHtml(line)}</li>`).join("")
    : `<li class="mind-empty"><p>Nothing yet: it learns as you fly.</p></li>`;
  const chapters = Array.isArray(library.chapters) ? library.chapters : [];
  ui.byId("lib-story-count").textContent = library.story_told ? `${ui.numeric(library.story_told)} PASSAGES` : "";
  ui.byId("lib-story-note").textContent = library.story_told
    ? "It may speak of the passages of its story it has already told you, in its own way. Never of what's still to come."
    : "It hasn't told you any of its story yet, so it won't speak of it.";
  ui.byId("lib-chapters").innerHTML = chapters.map((title) => `<li>${ui.escapeHtml(title)}</li>`).join("");
  const key = JSON.stringify(galaxy);
  const found = {query: String(sources.query || ""), results: Array.isArray(sources.results) ? sources.results : [], cards: sources.cards || 0};
  const foundKey = JSON.stringify(found);
  // How it searches: by meaning once its search model is here (and its cards read for it).
  const indexing = sources.indexing || {};
  ui.byId("lib-search-mode").textContent = sources.meaning ? "BY MEANING" : "BY WORDS";
  ui.byId("lib-search-mode").classList.toggle("on", Boolean(sources.meaning));
  ui.byId("lib-search-note").textContent = indexing.total
    ? `Reading ${ui.numeric(indexing.done)} of ${ui.numeric(indexing.total)} cards for their meaning…`
    : sources.meaning ? "" : "It matches words for now. With its mind awake, its small search model reads for meaning.";
  if (key !== libraryKey || foundKey !== librarySourcesKey) {
    libraryKey = key;
    librarySourcesKey = foundKey;
    libraryGalaxy = galaxy;
    librarySources = found;
    ui.byId("lib-galaxy-count").textContent = `${ui.numeric(total)} THINGS · ${ui.numeric(galaxy.length + (found.cards ? 1 : 0))} SUBJECTS`;
    renderGalaxy(ui);
  }
}
