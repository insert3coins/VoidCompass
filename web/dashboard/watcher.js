import "../assets/companion-caption.js";
import {renderCompanionChrome, COMPANIONS, renderCompanionDisplay} from "./companion-ui.js";
import {companionColours} from "../assets/companion-colours.js";
import {renderOrders} from "./orders.js";
// The Watcher's page (5.5.3.2): its eye, live; everything it has said; what
// it remembers of the commander (records, places, the bond grown over
// sessions together); and a poke.
//
// The page is built once and then updated in place, so the orb's canvas
// (and its life) survives every refresh. While the page is hidden the canvas
// has no size and the orb stops drawing.

const COMPANION_ICONS = {watcher: "◉", aster: "⬡", axiom: "◌", meridian: "◇", lyra: "✧"};
const NATURES = {weary: "Depressed", curious: "Curious", stoic: "Stoic", nervous: "Nervous", officer: "Officer on watch"};
const FREQUENCIES = {off: "Off", rare: "Rare", occasional: "Occasional", chatty: "Chatty"};
const MOOD_LABELS = {pleased: "PLEASED", wary: "WARY", curious: "CURIOUS", downcast: "DOWNCAST"};

let orb = null;
let activeCompanion = "watcher";
let companionModel = {}, companionLive = {}, companionPoll = 0, companionAsking = false;
let activeGeneration = 0, captionNature = "stoic", latestLog = null, panelCaption = null, captionTarget = null;
let companionLiveReceived = 0;

function panelText(ui) {
  const quote = ui.byId("watcher-latest");
  const target = quote?.querySelector(".companion-caption-text");
  if (!target) return;
  if (target !== captionTarget) {
    panelCaption?.destroy(); captionTarget = target;
    panelCaption = window.CompanionCaption.createPresenter({
      paint: parts => window.CompanionCaption.paintParts(target, parts),
      onDone: done => quote.classList.toggle("done", done),
      onThink: pause => orb?.think?.(pause),
      onStart: (duration, voiced) => { if (!voiced) orb?.speak?.(duration); },
    });
  }
  const liveThought = companionLive.thought, modelThought = companionModel.thought;
  const stale = liveThought?.scope && modelThought?.scope && liveThought.scope !== modelThought.scope;
  const current = (stale ? null : liveThought) || modelThought;
  const preview = Boolean(COMPANIONS[activeCompanion]?.overlay_only);
  const thought = current || {id: `log:${activeCompanion}:${latestLog?.at || "empty"}`, text: latestLog?.text || (preview ? "Lyra’s overlay is ready to preview. Her voice, dialogue and story are still to come. Appearance and animation are in Overlay Studio." : "It hasn't said anything yet. Give it a moment.")};
  const body = quote.querySelector(".companion-caption");
  const fullText = window.CompanionCaption.finalWords(thought.script || thought.text || "").map(part => part.ch).join("");
  if (body.dataset.fullText !== fullText) body.dataset.fullText = fullText;
  panelCaption.setVisible(target.getClientRects().length > 0 && !document.hidden);
  const changed = panelCaption.show(thought, {
    scope: `${activeCompanion}:${activeGeneration}`, nature: captionNature,
    reduced: document.body.classList.contains("reduced-motion") || window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    instant: !current,
  });
  panelCaption.live(companionLive.speech, companionLiveReceived);
  const name = (COMPANIONS[activeCompanion]?.name || "The Watcher").toUpperCase();
  quote.querySelector("cite").textContent = current ? `${name} · ${current.heading || "ON WATCH"}` : latestLog ? `${name} · ${ago(latestLog.at).toUpperCase()}` : name;
  return changed;
}

function asterSignal(ui) {
  const label = ui.byId("aster-signal");
  if (!label) return;
  const state = ui.byId("watcher-orb")?.parentElement.querySelector(".aster-instrument:not([hidden]), .crew-instrument:not([hidden])")?.dataset.state || "idle";
  const text = {idle:"ON WATCH",listening:"LISTENING",working:"ASSESSING",speaking:"REPLYING",alert:"ATTENTION",charging:"DRIVE CHARGING"}[state] || "ON WATCH";
  if (label.textContent !== text) label.textContent = text;
  if (label.dataset.state !== state) label.dataset.state = state;
}

async function companionLiveLoop(ui) {
  if (companionAsking) return;
  clearTimeout(companionPoll); companionPoll = 0;
  const canvas = ui.byId("watcher-orb");
  if (!canvas?.isConnected) return;
  const requestedIdentity = activeCompanion, requestedGeneration = activeGeneration;
  const visible = canvas.getClientRects().length > 0 && !document.hidden;
  if (visible) {
    companionAsking = true;
    try {
      const path = ui.apiUrl ? ui.apiUrl("/api/data/companion-live") : `/api/data/companion-live?token=${encodeURIComponent(new URLSearchParams(location.search).get("token") || "")}`;
      const response = await fetch(path, {cache: "no-store"});
      if (response.ok) {
        const live = await response.json();
        if (requestedIdentity === activeCompanion && requestedGeneration === activeGeneration
            && (!live.identity || live.identity === activeCompanion)
            && (live.generation == null || live.generation === activeGeneration)) {
          companionLive = live;
          companionLiveReceived = performance.now();
        }
      }
      else { await response.arrayBuffer(); companionLive = {}; }
    } catch (_error) { companionLive = {}; }
    finally { companionAsking = false; }
  }
  window.AsterCompanion?.update(canvas, companionModel, companionLive, {visible, reducedMotion: document.body.classList.contains("reduced-motion")});
  window.CrewCompanion?.update(canvas, companionModel, companionLive, {visible, reducedMotion: document.body.classList.contains("reduced-motion")});
  asterSignal(ui);
  orb?.voice?.(companionLive.speech ? Number(companionLive.speech.level) || 0 : null);
  panelText(ui);
  companionPoll = setTimeout(() => companionLiveLoop(ui), visible && (companionLive.speech || companionLive.hearing || panelCaption?.busy()) ? 100 : 700);
}
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
  // 5.7.4: a compact switcher (A–Z), then BRIDGE (the display beside the
  // conversation), STORY, YOU, LOG and SETUP (its thoughts and its voice).
  const crew = Object.entries(COMPANIONS).sort(([, a], [, b]) => a.name.replace(/^The\s+/i, "").localeCompare(b.name.replace(/^The\s+/i, "")));
  root.innerHTML = `<header class="companion-bar" aria-label="Choose your companion">
    <div class="companion-switch" role="group" aria-label="Your companion">${crew.map(([id, row]) => `<button type="button" data-companion="${id}" aria-pressed="${id === activeCompanion}" title="${row.description}"><i aria-hidden="true">${COMPANION_ICONS[id] || "◉"}</i><span><b>${row.name}</b><small>${row.role}</small></span></button>`).join("")}</div>
    <div class="companion-bar-side">
      <label id="aster-humour-row" hidden><span id="companion-humour-label">Officer’s commentary</span><select id="aster-humour"><option value="dry">Dry wit</option><option value="off">Restrained</option></select></label>
      <p role="status" id="companion-choice-status"></p>
    </div>
  </header><nav class="watcher-tabs" role="tablist" aria-label="Companion">
    <button type="button" role="tab" data-watcher-tab="now">BRIDGE<b id="watcher-now-badge"></b></button>
    <button type="button" role="tab" data-watcher-tab="orders">ORDERS<b id="watcher-orders-badge"></b></button>
    <button type="button" role="tab" data-watcher-tab="story">STORY</button>
    <button type="button" role="tab" data-watcher-tab="you">YOU</button>
    <button type="button" role="tab" data-watcher-tab="said">LOG</button>
    <button type="button" role="tab" data-watcher-tab="settings">SETUP<b id="watcher-voice-badge"></b></button>
  </nav>
  <div class="watcher-page watcher-now watcher-bridge" data-watcher-panel="now">
    <aside class="watcher-eye-panel" aria-label="The Watcher">
      <div class="watcher-optics-stage">
        <div class="watcher-stage-head"><span>THE WATCHER</span><small id="watcher-feed">JOURNAL LINK</small></div>
        <div class="aster-officer-mark"><span>FIELD COMPANION</span><b>MANIFEST OFFICER</b></div>
        <div class="watcher-eye"><canvas id="watcher-orb" aria-hidden="true"></canvas></div>
        <div class="aster-signal-line"><i aria-hidden="true"></i><b id="aster-signal">ON WATCH</b><span>ASTER</span></div>
        <div class="watcher-stage-caption"><b id="watcher-flight-state"></b><span id="watcher-last-event"></span></div>
      </div>
      <blockquote class="watcher-latest" id="watcher-latest"><span class="companion-caption"><span class="companion-caption-text"></span></span><cite></cite></blockquote>
      <div class="watcher-actions">
        <button type="button" class="primary" data-ws-page="watcher" data-ws-op="poke" id="watcher-poke">POKE</button>
        <small id="watcher-hotkey"></small>
      </div>
      <dl class="watcher-character" id="watcher-character"></dl>
    </aside>
    <div class="watcher-bridge-main">
      <section class="watcher-ask" id="watcher-question" aria-live="polite"></section>
      ${talkPanel()}
    </div>
    <aside class="watcher-bridge-side">
      <section class="watcher-card watcher-now-story" aria-label="Its story, now">
        <header><span>ITS STORY</span><b id="watcher-now-count"></b></header>
        <div id="watcher-now-story"></div>
        <button type="button" class="watcher-go" data-watcher-go="story">READ THE STORY</button>
      </section>
      <section class="watcher-card watcher-bond-panel" aria-label="You and the Watcher">
        <header><span>YOU AND THE WATCHER</span><b id="watcher-bond-name"></b></header>
        <div class="watcher-bond-meter" id="watcher-bond-meter" role="progressbar" aria-valuemin="0" aria-valuemax="100"><i></i></div>
        <p class="watcher-bond-next" id="watcher-bond-next"></p>
        <div class="watcher-feeling" id="watcher-feeling"></div>
      </section>
      <section class="watcher-card watcher-wish" id="watcher-wish" aria-label="Where it wants to go"></section>
      <section class="watcher-card watcher-recent" aria-label="Lately">
        <header><span>RECENT THOUGHTS</span><b></b></header>
        <ol class="watcher-log watcher-lately" id="watcher-lately"></ol>
        <button type="button" class="watcher-go" data-watcher-go="said">THE FULL LOG</button>
      </section>
    </aside>
  </div>
  <div class="watcher-page watcher-orders-page" data-watcher-panel="orders" hidden>
    <div id="orders-workspace" class="workspace-shell loading-panel">Opening the order book…</div>
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
    <section class="watcher-card watcher-crew" aria-label="The crew">
      <header><span>THE CREW · COMING ABOARD</span><b id="watcher-crew-count"></b></header>
      <p class="watcher-note">How each of your companions came aboard, and how they found each other. Each tells its own part in quiet moments; a passage about a crewmate waits until you've flown with that crewmate too.</p>
      <div class="watcher-crew-grid" id="watcher-crew"></div>
      <div class="watcher-crew-story" id="watcher-crew-story"></div>
    </section>
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
    ${panel("OTHER COMMANDERS' COMPANIONS", `<p class="watcher-note">Share your companion's code (paste it in Discord or a message). A friend's code, from any companion, lets yours meet theirs.</p>
      <div class="watcher-meet"><textarea id="watcher-code" rows="2" placeholder="Paste a friend's VCWATCH1 code" spellcheck="false"></textarea>
        <div class="watcher-buttons"><button type="button" class="primary" data-watcher-code="meet">MEET IT</button>
        <button type="button" data-watcher-code="copy">COPY MY COMPANION'S CODE</button></div></div>
      <ol class="watcher-log watcher-short" id="watcher-met"></ol>`, "", "watcher-wide")}
  </div>
  <div class="watcher-page watcher-said" data-watcher-panel="said" hidden>
    <section class="watcher-card watcher-log-panel" aria-label="What it has said">
      <header><span>WHAT IT HAS SAID</span><b id="watcher-log-count"></b></header>
      <ol class="watcher-log" id="watcher-log"></ol>
    </section>
  </div>
  <div class="watcher-subpage watcher-setup" data-watcher-panel="settings" hidden>
    <div class="watcher-setup-col">${settingsPanel()}</div>
    <div class="watcher-setup-col">${voicePanel()}</div>
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
  </div>`;
  talkKey = "";
  tips(root);
  wireTabs(root);
  wireSettings(root, ui);
  wireVoice(root, ui);
  wireName(root, ui);
  wireTalk(root, ui);
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
      ui.showToast(await ui.command("workspace", {page: "watcher", operation: "copy_code"}) ? "Your companion's code is on the clipboard" : "It couldn't be copied");
    } else if (action === "meet") {
      const done = await ui.command("workspace", {page: "watcher", operation: "meet", code: box.value});
      ui.showToast(done ? "It met them" : "That isn't a companion's code");
      if (done) box.value = "";
    } else if (action === "book") {
      ui.showToast(await ui.command("workspace", {page: "watcher", operation: "save_book"}) ? "Saved in the Wrapped folder" : "It couldn't be saved");
    }
  });
  const canvas = root.querySelector("#watcher-orb");
  root.querySelectorAll("button[data-companion]").forEach((button) => button.addEventListener("click", async () => {
    ui.byId("companion-choice-status").textContent = "Switching companion…";
    if (!(await ui.command("workspace", {page: "watcher", operation: "companion_identity", value: button.dataset.companion}))) ui.showToast("Finish or cancel any voice download before changing companion.");
  }));
  root.querySelector("#aster-humour").addEventListener("change", (event) => ui.command("workspace", {page: "watcher", operation: "companion_humour", value: event.target.value}));
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
    ui.showToast(done ? `${COMPANIONS[activeCompanion].name} has been reset. Its previous memory is backed up.` : "The companion could not be reset");
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
  if (lore.pending) {
    ui.byId("watcher-lore-count").textContent = "PENDING";
    ui.byId("watcher-lore").replaceChildren();
    ui.byId("watcher-reader").innerHTML = `<h3>${ui.escapeHtml(lore.title)}</h3><p>The voice, welcome messages and display are ready to try. Original lore, stories and a personal introduction will be added later.</p>`;
    ui.byId("watcher-lore-next").textContent = "Try a greeting in TALK, or TEST THE VOICE on the VOICE tab.";
    ui.byId("watcher-books").replaceChildren();
    return;
  }
  if (["aster", "axiom", "meridian", "lyra"].includes(lore.identity)) { renderCrewLore(lore, ui); return; }
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

// Aster, Axiom and Meridian (5.7.4): one renderer for the shared story
// engine. Unopened chapters say how they open; echoes say what stirs them.
function renderCrewLore(lore, ui) {
  const echoes = Array.isArray(lore.echoes) ? lore.echoes : [];
  const key = JSON.stringify([lore.identity, lore.told, lore.next, echoes.map((row) => [row.topic, row.count])]);
  if (lastLoreKey === key) return;
  lastLoreKey = key;
  loreChapters = lore.chapters || [];
  ui.byId("watcher-lore-count").textContent = `${ui.numeric(lore.told)} OF ${ui.numeric(lore.total)} TOLD`;
  ui.byId("watcher-now-count").textContent = ui.byId("watcher-lore-count").textContent;
  ui.byId("watcher-lore").innerHTML = loreChapters.map((chapter, index) => {
    if (chapter.begun) return `<button type="button" class="watcher-chapter${chapter.complete ? " complete" : " telling"}" data-chapter="${index}"><span class="watcher-chapter-n">${ui.escapeHtml(chapter.numeral)}</span><b>${ui.escapeHtml(chapter.title)}</b><em>${chapterStatus(chapter, ui)}</em></button>`;
    const unlock = chapter.unlock || [];
    const tip = unlock.length ? ` data-tip="${ui.escapeHtml(`Chapter ${chapter.numeral}|${unlock.join("|")}`)}" tabindex="0" title="${ui.escapeHtml(unlock.join(". "))}"` : "";
    return chapter.waits_for
      ? `<div class="watcher-chapter locked waits"${tip}><span class="watcher-chapter-n">${ui.escapeHtml(chapter.numeral)}</span><b>Waits for ${ui.escapeHtml(chapter.waits_for)}</b></div>`
      : `<div class="watcher-chapter locked"${tip}><span class="watcher-chapter-n">${ui.escapeHtml(chapter.numeral)}</span><b>· · ·</b></div>`;
  }).join("");
  renderReader(ui);
  if (!lore.told) ui.byId("watcher-reader").innerHTML = `<p class="watcher-reader-empty">${ui.escapeHtml(lore.empty_note || "")}</p>`;
  const next = lore.next;
  const span = (hours) => { const value = Number(hours || 0); return value >= 1.5 ? `${Math.ceil(value)} hours` : `${Math.max(1, Math.ceil(value * 60))} minutes`; };
  let note = lore.complete_note || "";
  if (!lore.complete && next) {
    if (next.ready) note = "The next passage is ready for a quiet moment together.";
    else if (next.waits_for) note = `The next chapter waits for ${next.waits_for}. ${next.how || ""} Or keep flying together: it opens anyway after about ${span(next.grace)} more.`;
    else if (Number(next.days) > 0) note = `The next chapter opens in about ${Math.ceil(next.days)} day${Math.ceil(next.days) === 1 ? "" : "s"}${Number(next.hours) > 0 ? `, after ${span(next.hours)} more together` : ""}.`;
    else note = `More opens after about ${span(next.hours)} of active service together.`;
  }
  ui.byId("watcher-lore-next").textContent = note;
  const current = loreChapters.filter((chapter) => chapter.begun).at(-1);
  ui.byId("watcher-now-story").innerHTML = `${current ? `<p class="watcher-now-chapter"><span>${ui.escapeHtml(current.numeral)}</span><b>${ui.escapeHtml(current.title)}</b><em>${chapterStatus(current, ui)}</em></p><p class="watcher-now-passage">${ui.escapeHtml(current.told.at(-1)?.text || "")}</p>` : ""}<p class="watcher-note">${ui.escapeHtml(note)}</p>`;
  const books = Array.isArray(lore.books) ? lore.books : [];
  ui.byId("watcher-books").innerHTML = books.map((book) => `<details class="watcher-book">
      <summary><span>READ THE WHOLE STORY</span><b>${ui.escapeHtml(String(book.title).toUpperCase())}</b></summary>
      <article>${book.chapters.map((chapter) => `<h4><span>${ui.escapeHtml(chapter.numeral)}</span>${ui.escapeHtml(chapter.title)}</h4>
        ${String(chapter.account).split("\n\n").map((para) => `<p>${ui.escapeHtml(para)}</p>`).join("")}`).join("")}</article>
    </details>`).join("");
  const heard = new Map(echoes.map((row) => [row.topic, row]));
  const labels = lore.echo_labels || {};
  const how = lore.echo_how || {};
  ui.byId("watcher-echo-count").textContent = `${ui.numeric(echoes.length)} OF ${ui.numeric(lore.echo_total || 0)} FOUND`;
  ui.byId("watcher-echoes").innerHTML = Object.entries(labels).map(([topic, label]) => {
    const row = heard.get(topic);
    const tip = how[topic] ? ` data-tip="${ui.escapeHtml(`${label}|${row ? "Found. " : ""}${how[topic]}`)}" tabindex="0" title="${ui.escapeHtml(how[topic])}"` : "";
    return row
      ? `<li class="heard"${tip}><b>${ui.escapeHtml(label)}</b><span>${ui.numeric(row.count)}×</span><time>${row.at ? ui.escapeHtml(ago(row.at)) : ""}</time></li>`
      : `<li${tip}><b>${ui.escapeHtml(label)}</b><span>not yet</span><time></time></li>`;
  }).join("");
}

// The crew (5.7.4): all four accounts, each from its own memory, whoever is on watch.
function renderCrew(crew, ui) {
  const esc = ui.escapeHtml;
  const arcs = Array.isArray(crew.arcs) ? crew.arcs : [];
  const count = ui.byId("watcher-crew-count");
  if (count) count.textContent = crew.total ? `${ui.numeric(crew.told)} OF ${ui.numeric(crew.total)} TOLD · ${ui.numeric(crew.flown || 0)} OF 4 FLOWN WITH` : "";
  // 5.7.6: the crew's own story, told together once every account is in.
  const night = crew.ensemble || {};
  const nightBox = ui.byId("watcher-crew-story");
  if (nightBox) nightBox.innerHTML = !night.scenes ? "" : `<header><b>${ui.escapeHtml(night.title || "")}</b><em>${night.unlocked
      ? `${ui.numeric(night.told)} / ${ui.numeric(night.total)}` : "When every account is told"}</em></header>
    <ol>${night.scenes.map((scene) => scene.heard
      ? `<li class="heard"><details><summary>${ui.escapeHtml(scene.title)}</summary>${scene.lines.map((line) =>
          `<p><b>${ui.escapeHtml(line.speaker)}</b> ${ui.escapeHtml(line.text)}</p>`).join("")}</details></li>`
      : `<li><span>· · ·</span></li>`).join("")}</ol>`;
  fill(ui, "watcher-crew", arcs.map((arc) => `<article class="watcher-crew-arc${arc.identity === activeCompanion ? " on-watch" : ""}" data-crew="${esc(arc.identity)}">
      <header><i aria-hidden="true">${COMPANION_ICONS[arc.identity] || "◉"}</i><span><b>${esc(arc.name)}</b><small>${esc(arc.role || "")}${arc.identity === activeCompanion ? " · ON WATCH" : arc.flown ? "" : " · NOT YET FLOWN WITH"}</small></span><em>${ui.numeric(arc.told)} / ${ui.numeric(arc.total)}</em></header>
      <ol>${(arc.passages || []).map((row) => row.heard
        ? `<li class="heard"><details><summary>${esc(row.title)}${row.about ? `<small>${esc(row.about)}</small>` : ""}</summary><p>${esc(row.text)}</p></details></li>`
        : `<li${row.waits_for ? ` data-tip="${esc(`${arc.name}|${row.waits_for}, then wait for a quiet moment with ${arc.name} on watch.`)}" tabindex="0"` : ""}><span>· · ·</span>${row.waits_for ? `<small>${esc(row.waits_for)}</small>` : ""}</li>`).join("")}</ol>
    </article>`).join(""));
}

function stat(ui, label, value, detail = "") {
  return `<div><span>${ui.escapeHtml(label)}</span><strong>${ui.escapeHtml(value)}</strong>${detail ? `<small>${ui.escapeHtml(detail)}</small>` : ""}</div>`;
}

export function renderWatcher(data = {}, ui) {
  const root = ui.byId("watcher-workspace");
  if (!root) return;
  if (!root.querySelector(".watcher-page")) shell(root, ui);
  const identity = data.identity || "watcher";
  if (identity !== activeCompanion || (data.companion_generation || 0) !== activeGeneration) { companionLive = {}; panelCaption?.clear(); lastLoreKey = ""; lastLogKey = ""; lastThought = ""; chosenChapter = null; }
  activeCompanion = identity;
  // 5.7.7: the crew's orders, in their own tab; its badge counts the ones waiting for an answer.
  renderOrders(data.orders || {enabled: false}, ui);
  const waiting = (data.orders?.offered || []).filter((row) => !row.later).length;
  const badge = ui.byId("watcher-orders-badge");
  if (badge) badge.textContent = waiting ? String(waiting) : "";
  activeGeneration = data.companion_generation || 0;
  renderCompanionChrome(data);
  root.dataset.companion = identity;
  root.dataset.overlayOnly = String(Boolean(COMPANIONS[identity]?.overlay_only));
  if (COMPANIONS[identity]?.overlay_only && watcherTab === "you") showTab(root,"now");
  const selectedName = data.companion_name || (COMPANIONS[identity]?.name || "The Watcher");
  root.dataset.storyPending = String(Boolean(data.lore?.pending));
  root.querySelector(".aster-officer-mark b").textContent = (COMPANIONS[identity]?.role || "Companion").toUpperCase();
  root.querySelector(".aster-signal-line > span").textContent = selectedName.toUpperCase();
  root.querySelectorAll("button[data-companion]").forEach((button) => { button.setAttribute("aria-pressed", String(button.dataset.companion === identity)); button.disabled = ["starting", "engine", "unpacking", "model"].includes(data.voice?.download?.stage); });
  ui.byId("companion-choice-status").textContent = `${selectedName} is on watch.`;
  // Each persona's own commentary choice (5.7.4).
  const humour = data.settings?.companion_humour;
  ui.byId("aster-humour-row").hidden = identity === "watcher" || !humour;
  if (humour) {
    ui.byId("companion-humour-label").textContent = humour.label;
    const select = ui.byId("aster-humour");
    const options = (humour.choices || []).map(([value, label]) => `<option value="${ui.escapeHtml(value)}">${ui.escapeHtml(label)}</option>`).join("");
    if (select.dataset.options !== options) { select.innerHTML = options; select.dataset.options = options; }
    if (document.activeElement !== select) select.value = humour.value || "dry";
  }
  root.querySelector('.watcher-stage-head > span').textContent = selectedName.toUpperCase();
  root.querySelector('.watcher-lore-panel > header > span').textContent = data.lore?.pending ? `${selectedName.toUpperCase()} · STORY PENDING` : identity !== "watcher" ? String(data.lore?.title || selectedName).toUpperCase() : "THE LONG STORY · WHAT IT REMEMBERS";
  root.querySelector('[data-watcher-setting="heartbeat_personality"]')?.closest("label")?.toggleAttribute("hidden", identity !== "watcher");
  // 5.7.6: the rota's duties show while the rota is on.
  root.querySelectorAll('[data-watcher-setting^="crew_rota_"]').forEach((select) =>
    select.closest("label")?.toggleAttribute("hidden", !data.settings?.crew_rota));
  root.querySelector(".watcher-eye-panel").setAttribute("aria-label", selectedName);
  root.querySelector(".watcher-bond-panel > header > span").textContent = `YOU AND ${selectedName.toUpperCase()}`;
  root.querySelector(".watcher-bond-panel").setAttribute("aria-label", `You and ${selectedName}`);
  ui.byId("watcher-reset").textContent = `RESET ${selectedName.toUpperCase()}`;
  const bookNote = root.querySelector('[data-watcher-code="book"]')?.closest(".watcher-card")?.querySelector("p");
  if (bookNote) bookNote.textContent = identity !== "watcher" ? `Keep ${selectedName}’s heard story passages and service memories as a book in the Wrapped folder.` : "Keep the story, memories, answers and dreams as a book in the Wrapped folder.";
  const resetText = root.querySelector("#watcher-reset-confirm > p");
  if (resetText) resetText.textContent = data.lore?.pending ? `${selectedName} forgets its conversation and session memory for this commander. Its previous memory is backed up first.` : identity !== "watcher" ? `${selectedName} forgets its own story, conversation and service memory for this commander. Its previous memory is backed up first. Other companions’ memories and your game records remain separate.` : "The Watcher forgets its story, echoes, conversation and memory of this commander. Its previous memory is backed up first. Your game records and achievements remain.";
  root.querySelectorAll('[data-watcher-code]').forEach((button) => { button.closest(".watcher-card")?.toggleAttribute("hidden", Boolean(data.lore?.pending)); });

  const reduced = document.body.classList.contains("reduced-motion");
  const feed = data.heartbeat || {};
  const optics = feed.orb || {};
  const panelColours = companionColours(identity,optics.accent,getComputedStyle(document.documentElement).getPropertyValue("--accent").trim());
  if (identity !== "watcher") root.querySelector(".watcher-eye-panel").style.setProperty("--accent",panelColours.primary);
  else root.querySelector(".watcher-eye-panel").style.removeProperty("--accent");
  companionModel = {...feed, orb: {...optics, identity, frame_rate: data.frame_rate}};
  orb?.setSuspended?.(identity !== "watcher");
  window.AsterCompanion?.update(ui.byId("watcher-orb"), companionModel, companionLive, {reducedMotion: reduced});
  window.CrewCompanion?.update(ui.byId("watcher-orb"), companionModel, companionLive, {reducedMotion: reduced});
  asterSignal(ui);
  orb?.update({
    palette: {}, eye: data.eye, reducedMotion: reduced, events: feed.events || [], frameRate: data.frame_rate,
    focusMovement: optics.focus_movement, liveliness: optics.liveliness || "standard", idle: optics.idle !== false, personality: data.nature,
    memory: feed.memory || {sessions: data.sessions, bond: data.bond?.level},
    stalled: Boolean(feed.stalled), state: feed.state, statusSeq: feed.status_seq,
    vitals: feed.vitals, story: optics.story,
  });
  if (data.renderer_logging) orb?.watchRenderer((renderer, reason) => ui.command("watcher_renderer", {surface: "dashboard", renderer, ...(reason ? {reason} : {})}));

  const log = Array.isArray(data.log) ? data.log : [];
  const latest = log[0];
  latestLog = latest;
  captionNature = feed.personality || data.nature || "stoic";
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
  const captionChanged = panelText(ui);
  if ((!companionPoll || captionChanged) && !companionAsking) { clearTimeout(companionPoll); companionPoll = 0; companionLiveLoop(ui); }
  ui.byId("watcher-hotkey").textContent = data.hotkey ? `or ${data.hotkey} in game` : "Bind a key in Settings › Hotkeys to poke it in game";
  ui.byId("watcher-poke").disabled = !data.enabled || Boolean(COMPANIONS[identity]?.overlay_only);
  ui.byId("watcher-poke").textContent = identity !== "watcher" ? `CALL ${selectedName.toUpperCase()}` : "POKE";
  if (identity !== "watcher") ui.byId("watcher-hotkey").textContent = data.hotkey ? `or ${data.hotkey} in game` : "Set a companion key in Settings › Hotkeys";
  ui.byId("watcher-character").innerHTML = [
    identity !== "watcher" ? ["ROLE", COMPANIONS[identity]?.role || "Companion"] : ["NATURE", NATURES[data.nature] || data.nature || "—"],
    ["THOUGHTS", FREQUENCIES[data.frequency] || data.frequency || "—"],
    [identity !== "watcher" ? "DISPLAY" : "EYE", identity === "axiom" ? "Particle field" : identity === "lyra" ? "3D robot" : identity === "meridian" ? "Holographic portrait" : identity === "aster" ? "Luminous halo" : data.eye === "hal" ? "HAL red" : "Theme"],
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
  renderCrew(data.crew || {}, ui);
  renderDeeper(data.deeper || {}, data.lore || {}, ui);
  renderKnows(data.habits || {}, ui);
  renderSettings(data.settings || {}, ui);
  renderVoice(data.voice || {}, ui);
  renderName(data.name || {}, ui);
  renderTalk(data.talk || {}, ui);
  renderHear(data.listen || {}, data.talk || {}, ui);

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
    ? `<header><span>${activeCompanion !== "watcher" ? `${String(COMPANIONS[activeCompanion]?.name || "").toUpperCase()} ASKS` : "IT ASKS YOU"}</span><b>ANSWER HERE, OR WITH YOUR ANSWER KEYS IN GAME</b></header>
      <p class="watcher-question">${esc(question.text)}</p>
      <div class="watcher-answers">${question.answers.map((answer, index) => `<button type="button" class="watcher-answer" data-watcher-answer="${esc(answer.key)}">
        <b>${esc(answer.label)}</b>${keys[index] ? `<kbd>${esc(keys[index])}</kbd>` : ""}</button>`).join("")}</div>`
    : `<header><span>NOTHING ASKED</span><b></b></header>
      <p class="watcher-note">Now and then it asks you something, in the cockpit and here. It remembers what you say. Bind its answer keys in Settings › Hotkeys to answer without leaving the game.</p>`);

  const feeling = deeper.feeling || {};
  const trust = Math.max(0, Math.min(100, Number(feeling.trust_value) || 0));
  const road = ROADS[deeper.road];
  // 5.7.4: Aster, Axiom and Meridian read you in their own terms.
  const [trustLabel, moodLabel] = feeling.labels || ["TRUST", "MOOD LATELY"];
  const moodTone = feeling.mood_value <= -.4 ? "low" : feeling.mood_value >= .4 ? "bright" : feeling.mood || "";
  const third = feeling.story
    ? `<div><span>STORY</span><b>${esc(feeling.story.title)}</b><small>${esc(feeling.story.note)}</small></div>`
    : `<div><span>ITS ROAD</span><b>${road ? road[0].toLowerCase() : lore.book_four ? "still deciding" : "not yet"}</b><small>${lore.book_four ? "Book Four" : "after Book Three"}</small></div>`;
  fill(ui, "watcher-feeling", `<div><span>${esc(trustLabel)}</span><b>${esc(feeling.trust || "—")}</b><i class="watcher-gauge" style="--fill:${trust}%"></i></div>
    <div><span>${esc(moodLabel)}</span><b>${esc(feeling.mood || "—")}</b><i class="watcher-gauge mood-${esc(moodTone)}" style="--fill:${Math.round(50 + 50 * Math.max(-1, Math.min(1, Number(feeling.mood_value) || 0)))}%"></i></div>
    ${third}`);

  const wish = deeper.pilgrimage;
  const wishState = wish ? (wish.reached ? ["TAKEN THERE", "done"] : wish.accepted ? ["YOU SAID YOU WOULD", "promised"] : wish.asked ? ["ASKED", "promised"] : ["NOT ANSWERED", ""]) : null;
  fill(ui, "watcher-wish", `<header><span>WHERE IT WANTS TO GO</span><b class="${wishState ? wishState[1] : ""}">${wishState ? wishState[0] : ""}</b></header>
    ${wish ? `<p class="watcher-wish-place">${esc(wish.words)}</p><p class="watcher-note">${esc(wish.how)}.</p>
      ${wish.reached ? "" : `<div class="watcher-buttons"><button type="button" data-page="mission">PLAN IT AS AN EXPEDITION</button></div>`}`
      : `<p class="watcher-note">${activeCompanion === "watcher" ? "Nowhere it has asked for, yet. Later in its story it may ask you to take it somewhere: a black hole, the core, the edge." : "Nowhere it has asked for, yet. Later in its story it may ask to be taken somewhere that matters to it."} An expedition can make it an objective.</p>`}`);

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
  const dreamsHead = ui.byId("watcher-dreams")?.closest(".watcher-card")?.querySelector("header > span");
  if (dreamsHead) dreamsHead.textContent = deeper.notes_title || "ITS DREAMS";
  fill(ui, "watcher-memories", rows(ui, memories, "Moments it keeps: first finds, ships lost, the commanders you flew with. Weeks later it brings them up.", (row) => esc(row.text)));
  fill(ui, "watcher-answers", rows(ui, answers, "Your answers, kept. It brings them back.",
    (row) => `<small>${esc(row.asked)}</small>${row.unanswered ? "<em>You didn't answer.</em>" : esc(row.answer)}`));
  fill(ui, "watcher-dreams", rows(ui, dreams, deeper.notes_title ? "When you log off, it writes a short note about the watch. They're kept here." : "When you log off, it dreams. They're written down here.", (row) => esc(row.text)));
  fill(ui, "watcher-met", met.length ? rows(ui, met, "", (row) => `<small>${esc(row.name || "A commander")}'s ${esc((COMPANIONS[row.companion || "watcher"]?.name || "The Watcher").replace(/^The /, ""))}</small>${esc(COMPANIONS[row.nature] ? COMPANIONS[row.nature].role : row.nature || "")}${row.chapter ? `, at chapter ${esc(row.chapter)}` : ""}${row.road ? ` · ${row.road === "open" ? "looking back" : "eye closed"}` : ""}`) : "");
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
const OLD_TABS = {overview: "now", together: "you", mind: "now", library: "now", talk: "now", voice: "settings"};
let watcherTab = "now";
try { watcherTab = window.localStorage.getItem("voidcompass.watcherTab") || "now"; } catch (_error) { /* private */ }

function showTab(root, tab) {
  tab = OLD_TABS[tab] || tab;
  watcherTab = ["now", "orders", "story", "you", "said", "settings"].includes(tab) ? tab : "now";
  root.querySelectorAll("[data-watcher-panel]").forEach((panel) => { panel.hidden = panel.dataset.watcherPanel !== watcherTab; });
  root.querySelectorAll("[data-watcher-tab]").forEach((button) => {
    button.setAttribute("aria-selected", button.dataset.watcherTab === watcherTab ? "true" : "false");
  });
  try { window.localStorage.setItem("voidcompass.watcherTab", watcherTab); } catch (_error) { /* private */ }
  if (watcherTab === "now") talkToNewest();
}

// 5.7.7: other pages can open a tab here (Settings' CREW ORDERS button, an old Orders link).
export function openWatcherTab(tab) {
  watcherTab = tab;
  try { window.localStorage.setItem("voidcompass.watcherTab", tab); } catch (_error) { /* private */ }
  const root = document.getElementById("watcher-workspace");
  if (root?.querySelector(".watcher-tabs")) showTab(root, tab);
}

function wireTabs(root) {
  root.querySelector(".watcher-tabs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-watcher-tab]");
    if (button) showTab(root, button.dataset.watcherTab);
  });
  showTab(root, watcherTab);
}

const option = (value, label) => `<option value="${value}">${label}</option>`;
// 5.7.6: the watch rota's duties, and who can take each.
const ROTA_DUTIES = [["docked", "Docked"], ["scanning", "Scanning (FSS or DSS)"], ["surface", "On a planet's surface"],
  ["route", "On a plotted route"], ["deep", "Deep space"], ["flight", "Ordinary flight"]];
const ROTA_DEEP = [250, 500, 1000, 2000, 5000, 10000].map((ly) => [String(ly), `${ly.toLocaleString("en-GB")} ly`]);
const ROTA_CREW = [["watcher", "The Watcher"], ["aster", "Aster"], ["axiom", "Axiom"], ["meridian", "Meridian"], ["lyra", "Lyra"], ["keep", "Whoever's on watch"]];
// 5.7.7: crew banter, the crew talking to each other: how often, how many, and when.
const BANTER_GROUPS = [
  ["flight", "In flight", "Fuel, a full scoop, long jump runs, heat, a narrow escape, launch, distance records, black holes and neutron stars."],
  ["exploring", "Exploring", "First discoveries, worlds worth mapping, the Codex, samples, landings, footfalls and data sold."],
  ["port", "In port", "Docking, trade and mining."],
  ["crew", "Crew moments", "A crew order done, a ship lost, a long session."],
  ["quiet", "Quiet stretches", "When nothing has been said for a while."]];
function banterPanel() {
  return `<div class="watcher-banter">
    ${field("crew_banter", "Crew banter", "The crew talking to each other, each in their own voice. Only companions whose voice is on take part: the one on watch, and crewmates you've flown with.",
      [["off", "Off"], ["sometimes", "Now and then"], ["often", "Often"]])}
    <p class="watcher-rota-status" id="watcher-banter-status" hidden><span></span></p>
    ${field("crew_banter_gap", "At most one every", "However often, never closer than this", [["10", "10 minutes"], ["20", "20 minutes"], ["30", "30 minutes"], ["60", "Hour"]])}
    ${field("crew_banter_size", "Who joins", "Just two of them, or a third when there's one to hand", [["two", "Two"], ["three", "Up to three"]])}
    ${field("crew_banter_length", "Length", "Short is a line and its answer; Full lets the whole exchange play out", [["short", "Short"], ["full", "Full"]])}
    ${BANTER_GROUPS.map(([group, title, note]) => toggle(`crew_banter_${group}`, title, note)).join("")}
  </div>`;
}
const field = (key, title, note, options) => `<label class="studio-field"><span>${title}${note ? `<small>${note}</small>` : ""}</span>
  <select data-watcher-setting="${key}">${options.map(([value, label]) => option(value, label)).join("")}</select></label>`;
const toggle = (key, title, note) => `<label class="studio-switch"><span><b>${title}</b><small>${note}</small></span>
  <input type="checkbox" data-watcher-switch="${key}"><i></i></label>`;

function settingsPanel() {
  return `<section class="watcher-settings" aria-label="Its display">
    <header><span>ITS DISPLAY</span><b class="watcher-saved" id="watcher-display-saved"></b></header>
    <p class="watcher-note">How it looks on screen. Colour is each companion's own; the rest is shared by the whole crew. Its size is in Overlay Studio.</p>
    ${field("companion_accent", "Accent", "At rest; danger still uses a warning colour", [])}
    ${field("companion_focus", "Focus movement", "How it focuses on and follows activity", [["off", "Fixed focus"], ["tracking", "Tracking"], ["expressive", "Expressive"]])}
    ${field("companion_liveliness", "Animation intensity", "", [["calm", "Calm"], ["standard", "Standard"], ["alive", "Lively"]])}
    ${field("heartbeat_frame_rate", "Frame rate", "Lower is lighter on an older PC", [["0", "Same as all overlays"], ["60", "Full · 60"], ["30", "Standard · 30"], ["24", "Gentle · 24"], ["15", "Light · 15"]])}
    <label class="studio-switch"><span><b>Idle animation</b><small data-companion-motion-note></small></span>
      <input type="checkbox" data-watcher-switch="companion_motion"><i></i></label>
  </section>
  <section class="watcher-settings" aria-label="Its thoughts">
    <header><span>ITS THOUGHTS</span><b class="watcher-saved" id="watcher-settings-saved"></b></header>
    <p class="watcher-note">What it says beside its display, and how.</p>
    ${field("heartbeat_thoughts", "Thoughts", "Rare speaks of what matters; Chatty also remarks on everyday play",
      [["off", "Off"], ["rare", "Rare"], ["occasional", "Occasional"], ["chatty", "Chatty"]])}
    ${field("heartbeat_personality", "Nature", "How it takes what happens",
      [["weary", "Depressed"], ["curious", "Curious"], ["stoic", "Stoic"], ["nervous", "Nervous"]])}
    ${toggle("heartbeat_thought_backdrop", "Thought backdrop", "A dark panel behind its words, easier to read over the game.")}
    ${toggle("heartbeat_thought_heading", "Thought heading", "A line above its words: a memory and its chapter, an echo, or simply its name.")}
    ${toggle("crew_rota", "Watch rota", "The crew changes the watch with what you're doing: within seconds of docking, under a minute for the rest. Choose who takes each duty below. Choosing a companion yourself holds it for five minutes.")}
    <p class="watcher-rota-status" id="watcher-rota-status" hidden><span></span><button type="button" data-watcher-rota-release hidden>LET THE ROTA DECIDE</button></p>
    ${ROTA_DUTIES.map(([duty, title]) => field(`crew_rota_${duty}`, title, "", ROTA_CREW)
      + (duty === "deep" ? field("crew_rota_deep_ly", "Deep space starts", "How far from home", ROTA_DEEP) : "")).join("")}
    ${banterPanel()}
    ${field("heartbeat_thought_side", "Thought side", "Auto goes toward the middle of the screen; either side swaps if its words won't fit there",
      [["auto", "Auto"], ["left", "Left of the display"], ["right", "Right of the display"]])}
    ${field("heartbeat_text_scale_percent", "Text size", "Its words only; the display keeps its size",
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

// 5.7.7: the rota's state under its switch. The deck sends when a change is
// due; the countdown runs here, so the page itself never redraws for a clock.
let rotaStatus = null;
let rotaTimer = 0;
function rotaText() {
  const line = document.getElementById("watcher-rota-status");
  if (!line) return;
  const status = rotaStatus;
  line.hidden = !status;
  if (!status) return;
  const left = status.until ? Math.max(0, Math.round(status.until - Date.now() / 1000)) : null;
  const when = left == null ? "" : left >= 120 ? ` in ${Math.ceil(left / 60)} min` : ` in ${left} s`;
  let text = status.text || "";
  if (status.state === "holding" && status.until) {
    const until = new Date(status.until * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
    text = `${text} until ${until}`;
  } else if (status.state === "gap") {
    text = `${text}${left ? `: next change allowed${when}` : ""}`;
  } else if (status.state === "waiting") {
    text = `${text}${left ? when : ""}`;
  }
  line.querySelector("span").textContent = text;
  line.querySelector("[data-watcher-rota-release]").hidden = status.state !== "holding";
}

function wireSettings(root, ui) {
  const panel = root.querySelector('[data-watcher-panel="settings"]');
  panel.addEventListener("click", async (event) => {
    if (!event.target.closest("[data-watcher-rota-release]")) return;
    await ui.command("workspace", {page: "watcher", operation: "rota_release"});
  });
  panel.addEventListener("change", async (event) => {
    const select = event.target.closest("[data-watcher-setting]");
    const box = event.target.closest("[data-watcher-switch]");
    if (!select && !box) return;
    const values = select ? {[select.dataset.watcherSetting]: select.value} : {[box.dataset.watcherSwitch]: box.checked};
    const saved = event.target.closest(".watcher-settings")?.querySelector(".watcher-saved")?.id || "watcher-settings-saved";
    savedNote(saved, await ui.command("workspace", {page: "watcher", operation: "settings", values}));
  });
}

function renderSettings(settings, ui) {
  const panel = ui.byId("watcher-workspace")?.querySelector('[data-watcher-panel="settings"]');
  if (!panel) return;
  renderCompanionDisplay(panel, settings);
  panel.querySelectorAll("[data-watcher-setting]").forEach((select) => {
    const value = settings[select.dataset.watcherSetting];
    if (value !== undefined && document.activeElement !== select) select.value = String(value);
  });
  panel.querySelectorAll("[data-watcher-switch]").forEach((box) => {
    const value = settings[box.dataset.watcherSwitch];
    if (value !== undefined) box.checked = Boolean(value);
  });
  // 5.7.7: crew banter's details show while it's on, with who can talk now.
  const banterOn = (settings.crew_banter || "sometimes") !== "off";
  panel.querySelectorAll('[data-watcher-setting^="crew_banter_"], [data-watcher-switch^="crew_banter_"]').forEach((control) =>
    control.closest("label")?.toggleAttribute("hidden", !banterOn));
  const banterStatus = document.getElementById("watcher-banter-status");
  if (banterStatus) {
    banterStatus.hidden = !settings.banter_status;
    banterStatus.querySelector("span").textContent = settings.banter_status || "";
  }
  rotaStatus = settings.rota_status || null;
  rotaText();
  if (rotaStatus && !rotaTimer) rotaTimer = window.setInterval(rotaText, 1000);
  if (!rotaStatus && rotaTimer) { window.clearInterval(rotaTimer); rotaTimer = 0; }
}

function voicePanel() {
  return `<section class="watcher-voice" aria-label="Its voice">
    <header><span>ITS VOICE</span><b class="watcher-saved" id="watcher-voice-saved"></b></header>
    <label class="studio-switch watcher-voice-switch"><span><b>Voice</b><small id="watcher-voice-state">Its thoughts, spoken aloud as they appear beside its display.</small></span>
      <input type="checkbox" id="watcher-voice-on"><i></i></label>
    <div class="watcher-voice-get" id="watcher-voice-get">
      <p>Its voice isn't on this PC yet. Switching it on downloads the voice engine (Piper) and the <span id="watcher-voice-model-name">HAL 9000 voice</span> model,
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
      <label class="studio-field"><span>It calls you<small id="watcher-name-policy">Choose your preferred form of address</small></span>
        <select id="watcher-name-call">${option("commander", "Commander")}${option("name", "Your name")}${option("nickname", "A name you choose")}</select></label>
      <label class="studio-field"><span>A name you choose<small>Used when it calls you by a name you choose</small></span>
        <input type="text" id="watcher-name-nickname" maxlength="24" spellcheck="false" autocomplete="off"></label>
      <label class="studio-field"><span>How it says your name<small>Write it the way it sounds. Empty, it works it out</small></span>
        <span class="watcher-name-say"><input type="text" id="watcher-name-spoken" maxlength="60" spellcheck="false" autocomplete="off">
          <button type="button" id="watcher-name-hear">HEAR IT</button></span></label>
    </div>
    <details id="watcher-name-story" hidden>
      <summary id="watcher-name-story-title"></summary>
      <ol class="watcher-lore" id="watcher-name-passages"></ol>
    </details>
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
  const officer = activeCompanion !== "watcher";
  ui.byId("watcher-name-policy").textContent = officer
    ? "Uses your chosen name or nickname in replies and reports; choose Commander to keep the title"
    : "Commander every day; a name only for the moments that matter, once a session";
  const known = String(name.known || "");
  const call = ["commander", "name", "nickname"].includes(name.call) ? name.call : "commander";
  const nickname = String(name.nickname || "");
  const told = Array.isArray(name.told) ? name.told.length : 0;
  let note = "It hasn't read your name yet. It will the next time you load the game.";
  if (known) {
    note = activeCompanion === "aster" ? `Aster has read ${known} in the crew register.` : activeCompanion === "axiom" ? `Axiom has read ${known} in the journal and filed it carefully.` : activeCompanion === "meridian" ? `Meridian has read ${known} in the ship’s log.` : activeCompanion === "lyra" ? `Lyra has read ${known} in the ship’s registry.` : `The ship writes ${known} every time you wake it.`;
    if (!name.call) note += told ? " It has noticed, and will ask you about it. Or choose here." : " Choose what it calls you here, or wait for it to ask.";
    else if (call === "name") note += officer ? " Your name is its regular form of address." : " It may use it now and then, never more than once a session.";
    else if (call === "nickname") note += nickname
      ? officer ? ` It uses ${nickname} as your regular form of address.` : ` It calls you ${nickname} now and then.`
      : " Write the name you'd like below.";
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
  const story = name.story;
  const passages = Array.isArray(story?.told) ? story.told : [];
  const reader = ui.byId("watcher-name-story");
  reader.hidden = !passages.length;
  if (passages.length) {
    ui.byId("watcher-name-story-title").textContent = `${story.title} · ${passages.length} OF ${name.steps || 3}`;
    fill(ui, "watcher-name-passages", passages.map(row => `<li><p>${ui.escapeHtml(row.text)}</p></li>`).join(""));
  }
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
  model: "Downloading the voice model…", done: "Done", cancelled: "Cancelled", failed: "Failed"};

function renderVoice(voice, ui) {
  if (ui.byId("watcher-voice-model-name")) ui.byId("watcher-voice-model-name").textContent = voice.model_name || "HAL 9000 voice";
  const panel = ui.byId("watcher-workspace")?.querySelector('.watcher-voice');
  if (!panel) return;
  const pending = voice.available === false || Boolean(COMPANIONS[activeCompanion]?.overlay_only);
  panel.querySelectorAll("input,select,button").forEach(control => { control.disabled = pending; });
  if (pending) {
    ui.byId("watcher-voice-model-name").textContent = "Voice pending";
    ui.byId("watcher-voice-on").checked = false;
    ui.byId("watcher-voice-state").textContent = "Voice pending. Lyra is an overlay-only preview for now.";
    ui.byId("watcher-voice-badge").textContent = " · PREVIEW";
    ui.byId("watcher-voice-get").hidden = true;
    ui.byId("watcher-voice-ready").hidden = true;
    ui.byId("watcher-voice-orb").textContent = "Choose Lyra’s colours, size, focus and animation in Overlay Studio. No voice download is available yet.";
    return;
  }
  const download = voice.download || {};
  const busy = ["starting", "engine", "unpacking", "model"].includes(download.stage);
  ui.byId("watcher-voice-badge").textContent = voice.enabled && voice.installed ? " · VOICE ON" : "";
  ui.byId("watcher-voice-on").checked = Boolean(voice.enabled);
  ui.byId("watcher-voice-state").textContent = voice.enabled && voice.installed
    ? (voice.speaking ? "Speaking now." : "On. Its thoughts are spoken aloud as they appear beside its display.")
    : voice.enabled ? "On, once the voice has downloaded." : "Off. Its thoughts appear beside its display, silently.";
  ui.byId("watcher-voice-get").hidden = Boolean(voice.installed);
  ui.byId("watcher-voice-ready").hidden = !voice.installed;
  for (const id of ["watcher-voice-size", "watcher-voice-size-2"]) ui.byId(id).textContent = ui.numeric(voice.size_mb);
  ui.byId("watcher-voice-rights").textContent = voice.rights || "";
  const progress = ui.byId("watcher-voice-progress");
  progress.hidden = !busy;
  if (busy) {
    const share = Math.round(100 * (Number(download.done) || 0) / Math.max(1, Number(download.total) || 1));
    progress.style.setProperty("--done", `${share}%`);
    progress.querySelector("span").textContent = `${(download.stage === "model" ? `Downloading the ${voice.model_name || (activeCompanion !== "watcher" ? `${COMPANIONS[activeCompanion]?.name || "companion"} voice` : "HAL 9000 voice")}…` : DOWNLOAD_STAGES[download.stage]) || ""} ${share}%`;
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
    : "The companion overlay is off. Its thoughts, spoken or not, need it on in Overlay Studio. TEST THE VOICE works either way.";

  const findingPanel = ui.byId("watcher-finding-stage")?.closest("section");
  if (findingPanel) findingPanel.hidden = voice.identity !== "watcher";
  if (["aster", "axiom", "meridian", "lyra"].includes(voice.identity)) {
    const name = COMPANIONS[voice.identity].name;
    ui.byId("watcher-voice-orb").textContent = voice.orb_on ? `${name} speaks complete reports from the start. Its story unfolds separately over active service. Set up your microphone and recognition in Settings › Voice.` : `Enable the companion overlay in Overlay Studio to receive ${name}’s replies. TEST THE VOICE works here either way.`;
  }
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

const TALK_PROMPTS = ["Open the galaxy map", "Open the system map", "Open the left panel", "Gear down",
  "Balance power", "Where are we?", "What's in the cargo hold?"];
let talkKey = "";
let hearState = {};
let hearPoll = 0;
let hearAsking = false;
const HEAR_ACTIVE = ["opening", "listening", "test"];

function talkPanel() {
  const prompts = TALK_PROMPTS.map((text) => `<button type="button" class="talk-prompt" data-talk-prompt="${text}">${text}</button>`).join("");
  return `<section class="talk-console" aria-label="Talk to it">
    <header><span id="watcher-talk-title">TALK</span><b id="watcher-talk-state"></b><button type="button" class="talk-link" id="watcher-talk-forget">CLEAR</button></header>
    <ol class="talk-transcript" id="watcher-talk-log" aria-live="polite"></ol>
    <div class="talk-prompts" id="talk-prompts" aria-label="Example commands">${prompts}</div>
    <div class="talk-say">
      <textarea id="watcher-talk-text" rows="1" maxlength="400" placeholder="Ask something, or give a command…" aria-label="A command or question for your companion" spellcheck="true"></textarea>
      <button type="button" class="talk-mic" id="watcher-talk-mic" data-stage="idle" title="Hold to talk" aria-label="Talk by voice" hidden><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"></rect><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"></path></svg></button>
      <button type="button" class="talk-send" id="watcher-talk-send" aria-label="Send">SEND</button>
    </div>
    <footer><p class="watcher-note">Work the ship, show an overlay, change the music, or ask about your ship, cargo, route and system.</p><p class="talk-setup" id="watcher-talk-note"></p></footer>
  </section>`;
}

function talkToNewest() {
  const log = document.getElementById("watcher-talk-log");
  if (log) requestAnimationFrame(() => { log.scrollTop = log.scrollHeight; });
}

function wireTalk(root, ui) {
  const send = async (operation, extra = {}) => ui.command("workspace", {page: "watcher", operation, ...extra});
  const text = root.querySelector("#watcher-talk-text");
  const say = async (words) => {
    words = String(words || "").trim();
    if (!words) return;
    if (await send("talk", {text: words})) {
      if (text.value.trim() === words) text.value = "";
    } else ui.showToast("It can't answer yet");
  };
  root.querySelector("#watcher-talk-send").addEventListener("click", () => say(text.value));
  text.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); say(text.value); }
  });
  root.querySelector("#talk-prompts").addEventListener("click", (event) => {
    const prompt = event.target.closest("[data-talk-prompt]");
    if (prompt && !prompt.disabled) say(prompt.dataset.talkPrompt);
  });
  root.querySelector("#watcher-talk-forget").addEventListener("click", () => send("talk_forget"));
  wireHear(root, ui, send);
}

// Talking by voice (5.7.1): the microphone button by SAY IT, held or tapped
// as the talk key is. Its settings are in Settings › Voice (5.7.3).
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
  const mic = ui.byId("watcher-talk-mic");
  if (mic) {
    mic.dataset.stage = live.stage === "test" ? "idle" : live.stage || "idle";
    mic.style.setProperty("--level", live.stage === "listening" ? String(level) : "0");
  }
}

function renderHear(listen, talk, ui) {
  const mic = ui.byId("watcher-talk-mic");
  if (!mic) return;
  hearState = {...listen, settled: false};
  const ready = Boolean(listen.enabled && listen.installed);
  // The button by SAY IT, there once its hearing is.
  mic.hidden = !ready;
  mic.disabled = !ready || !talk.orb_on || Boolean(listen.blocked) || listen.stage === "hearing";
  mic.title = listen.blocked || (listen.mode === "tap" ? "Click to talk, click again to stop" : "Hold to talk");
  // While the microphone is open the meter's loop draws it; redrawn here, it blinked to nothing.
  if (HEAR_ACTIVE.includes(listen.stage)) hearLoop(ui);
  else drawHearLive(ui, {stage: listen.stage, level: 0, seconds: 0});
  if (listen.stage === "hearing") ui.byId("watcher-talk-state").textContent = "HEARING YOU…";
}

function talkClock(seconds) {
  const at = Number(seconds);
  if (!at) return "";
  const when = new Date(at * 1000);
  const today = new Date().toDateString() === when.toDateString();
  return today ? when.toLocaleTimeString(undefined, {hour: "2-digit", minute: "2-digit"})
    : when.toLocaleDateString(undefined, {day: "numeric", month: "short"}).toUpperCase();
}

function renderTalk(data, ui) {
  const panel = ui.byId("watcher-workspace")?.querySelector(".talk-console");
  if (!panel) return;
  const talk = Array.isArray(data.talk) ? data.talk : [];
  const name = COMPANIONS[activeCompanion]?.name || "The Watcher";
  const preview = Boolean(COMPANIONS[activeCompanion]?.overlay_only);
  const key = JSON.stringify([activeCompanion, talk]);
  if (key !== talkKey) {
    talkKey = key;
    const icon = COMPANION_ICONS[activeCompanion] || "◉";
    // 5.7.4: a crewmate asked by name answers under its own name, off watch.
    const replier = (row) => row.who && row.who !== activeCompanion && COMPANIONS[row.who]
      ? [COMPANION_ICONS[row.who] || "◉", `${COMPANIONS[row.who].name} · OFF WATCH`, " off-watch"] : [icon, name, ""];
    ui.byId("watcher-talk-log").innerHTML = talk.length ? talk.map((row) => { const [mark, who, extra] = replier(row); return `<li class="talk-turn">
      <div class="talk-you"><small>YOU${row.voice ? " · SPOKEN" : ""} · ${ui.escapeHtml(talkClock(row.at))}</small><p>${ui.escapeHtml(row.you)}</p></div>
      ${row.it ? `<div class="talk-it${extra}"><i aria-hidden="true">${mark}</i><div><small>${ui.escapeHtml(who.toUpperCase())}</small><p>${ui.escapeHtml(row.it)}</p></div></div>` : ""}</li>`; }).join("")
      : `<li class="talk-empty"><p>${preview ? "Overlay preview. Lyra’s dialogue and voice are pending." : `Say hello to ${ui.escapeHtml(name)}, try a command below, or ask about your ship, cargo, route or current system.`}</p></li>`;
    talkToNewest();
  }
  const canTalk = Boolean(data.orb_on) && !preview;
  ui.byId("watcher-talk-title").textContent = `TALK TO ${name.toUpperCase()}`;
  ui.byId("watcher-talk-state").textContent = talk.length ? `${talk.length} EXCHANGED` : "";
  ui.byId("watcher-talk-forget").hidden = !talk.length;
  ui.byId("watcher-talk-send").disabled = !canTalk;
  ui.byId("watcher-talk-text").disabled = !canTalk;
  ui.byId("watcher-talk-text").placeholder = `Ask ${name}, or give a command…`;
  if (preview) ui.byId("watcher-talk-text").placeholder = "Dialogue and voice are pending for Lyra.";
  panel.querySelectorAll("[data-talk-prompt]").forEach((button) => { button.disabled = !canTalk; });
  ui.byId("watcher-talk-note").innerHTML = preview ? "Lyra’s dialogue and voice are pending. Her display controls are in <b>Overlay Studio</b>." : canTalk
    ? "Microphone, talk key, keyboard bindings and sequences: <b>SETTINGS › VOICE</b>."
    : "The companion overlay is off: it answers beside its display. Switch it on in <b>Overlay Studio</b>.";
}

window.addEventListener("pagehide", () => { clearTimeout(companionPoll); panelCaption?.destroy(); });
