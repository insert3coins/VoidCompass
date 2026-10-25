// Games (5.6.3): a card per game, each played here in the deck. A game is
// its own page under /games/<id>/, framed and sandboxed; it talks to the
// deck only by postMessage (ready, over, mute, crt, action) and the deck
// answers with the theme, the commander's best, the sound and CRT switches,
// how you want to play it (mouse and keys, keys only or mouse only),
// and what the journal knows for it ("live": the Hatchling, Touchdown's
// gravity), sent again whenever that changes.

let games = [];
let playing = "";       // the game open in the player, or ""
let frame = null;
let lastCardsKey = "";
let lastRunsKey = "";
let lastLiveKey = "";
let cardSize = [1200, 1350];
let ui = null;
let watching = false;

const INPUT_MODES = [["both", "MOUSE & KEYS"], ["keys", "KEYS ONLY"], ["mouse", "MOUSE ONLY"]];
const THEME_TOKENS = ["bg", "panel", "border", "accent", "orange", "text", "muted", "dim", "green", "yellow", "red"];

function stored(key, fallback = "") {
  try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; }
}

function store(key, value) {
  try { localStorage.setItem(key, value); } catch { /* the sound comes back on next time */ }
}

function theme() {
  const style = getComputedStyle(document.documentElement);
  return Object.fromEntries(THEME_TOKENS.map((name) => [name, style.getPropertyValue(`--${name}`).trim()]));
}

function score(value) {
  return Math.max(0, Math.round(Number(value) || 0)).toLocaleString();
}

function when(seconds) {
  if (!seconds) return "";
  const date = new Date(seconds * 1000);
  return date.toLocaleDateString(undefined, {day: "numeric", month: "short"}).toUpperCase();
}

function game(id) {
  return games.find((item) => item.id === id) || null;
}

function cardArt(item) {
  const esc = ui.escapeHtml;
  if (item.card) {
    return `<img src="${esc(item.card)}" alt="" loading="lazy" decoding="async">`;
  }
  // No picture yet: a drawn stand-in that says where one goes.
  return `<div class="game-art-blank" aria-hidden="true">
    <span class="game-art-grid"></span>
    <strong>${esc(item.title)}</strong>
    <small>CARD ART · assets/gamecards/${esc(item.card_name)} · ${cardSize[0]} × ${cardSize[1]}</small>
  </div>`;
}

function stage(item, run) {
  return run?.wave ? ` · ${ui.escapeHtml(item.stage || "WAVE")} ${run.wave}` : "";
}

// The pet's card shows the pet, not a score.
function petBadge(item) {
  const pet = item.live?.pet;
  if (!pet) return `<b>—</b><small>NO EGG CHOSEN YET</small>`;
  const esc = ui.escapeHtml;
  return `<b>${esc(pet.name.toUpperCase())}</b><small>${esc(pet.mood_word)}${pet.wants ? ` · WANTS ${esc(pet.wants)}` : ""}</small>`;
}

function card(item) {
  const esc = ui.escapeHtml;
  const best = item.id === "hatchling" ? petBadge(item)
    : item.best ? `<b>${score(item.best.score)}</b><small>BEST${stage(item, item.best)}</small>` : `<b>—</b><small>NOT PLAYED YET</small>`;
  const accent = item.accent ? ` style="--game-tone:${esc(item.accent)}"` : "";
  return `<button type="button" class="game-card" data-game-open="${esc(item.id)}"${accent} aria-label="Play ${esc(item.title)}">
    <div class="game-art">${cardArt(item)}<i class="game-play">PLAY</i></div>
    <div class="game-card-body">
      <header><h3>${esc(item.title)}</h3>${item.genre ? `<span>${esc(item.genre)}</span>` : ""}</header>
      <p>${esc(item.tagline || item.description)}</p>
      <footer><div class="game-best">${best}</div><small>${item.played ? `${item.played} RUN${item.played === 1 ? "" : "S"}` : esc(item.players)}</small></footer>
    </div>
  </button>`;
}

function shell(root) {
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="games-page">
    <div class="games-library"><div class="games-grid" id="games-grid"></div></div>
    <div class="games-player" id="games-player" hidden>
      <header class="games-bar">
        <button type="button" data-game-back>◂ ALL GAMES</button>
        <div><small id="games-genre"></small><strong id="games-title"></strong></div>
        <button type="button" data-game-restart>RESTART</button>
        <button type="button" data-game-full>FULL SCREEN</button>
      </header>
      <div class="games-stage" id="games-stage"></div>
      <aside class="games-side">
        <section><small>ABOUT</small><p id="games-about"></p></section>
        <section><small>CONTROLS</small>
          <div class="games-input" id="games-input" role="group" aria-label="Play with">${INPUT_MODES.map(([id, label]) =>
            `<button type="button" data-game-input="${id}">${label}</button>`).join("")}</div>
          <dl id="games-controls"></dl></section>
        <section><small>YOUR BEST RUNS</small><ol id="games-runs"></ol></section>
      </aside>
    </div>
  </div>`;
  root.addEventListener("click", (event) => {
    const open = event.target.closest("[data-game-open]");
    if (open) return openGame(open.dataset.gameOpen);
    if (event.target.closest("[data-game-back]")) return closeGame();
    if (event.target.closest("[data-game-restart]")) return openGame(playing);
    const input = event.target.closest("[data-game-input]");
    if (input) return setInput(input.dataset.gameInput);
    if (event.target.closest("[data-game-full]")) {
      const player = ui.byId("games-player");
      if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
      else player?.requestFullscreen?.().catch(() => ui.showToast?.("Full screen isn't available here"));
    }
  });
}

function renderCards() {
  const grid = ui.byId("games-grid");
  if (!grid) return;
  const key = JSON.stringify([games.map((item) => [item.id, item.title, item.tagline, item.card, item.best?.score, item.played, item.accent,
    item.id === "hatchling" ? [item.live?.pet?.name, item.live?.pet?.mood_word, item.live?.pet?.wants] : null]), cardSize]);
  if (key === lastCardsKey) return;
  lastCardsKey = key;
  grid.innerHTML = games.length
    ? games.map(card).join("")
    : `<div class="games-empty"><strong>NO GAMES FOUND</strong><span>Games live in web/games, one folder each with a game.json.</span></div>`;
}

function renderRuns() {
  const item = game(playing);
  const list = ui.byId("games-runs");
  if (!item || !list) return;
  const key = JSON.stringify([item.id, item.runs]);
  if (key === lastRunsKey) return;
  lastRunsKey = key;
  const esc = ui.escapeHtml;
  list.innerHTML = (item.runs || []).slice(0, 5).map((run) => `<li><b>${score(run.score)}</b>
    <span>${stage(item, run).replace(" · ", "")}${run.rank ? `${run.wave ? " · " : ""}${esc(run.rank)}` : ""}</span><small>${when(run.at)}</small></li>`).join("")
    || `<li class="games-none">${item.id === "hatchling" ? "It keeps no scores: it keeps you company." : "Your first run goes here."}</li>`;
}

function hello() {
  const item = game(playing);
  if (!frame?.contentWindow || !item) return;
  const crt = stored(`voidcompass.games.${item.id}.crt`);
  lastLiveKey = JSON.stringify(item.live ?? null);
  frame.contentWindow.postMessage({source: "voidcompass-deck", type: "hello", theme: theme(),
    best: item.best?.score || 0, muted: stored(`voidcompass.games.${item.id}.muted`) === "1",
    ...(crt ? {crt: crt === "1"} : {}), input: inputMode(item), live: item.live ?? null}, "*");
}

function inputMode(item) {
  const mode = stored(`voidcompass.games.${item.id}.input`, "both");
  return item.input_modes === false ? "both" : INPUT_MODES.some(([id]) => id === mode) ? mode : "both";
}

function showInput(item) {
  const box = ui.byId("games-input");
  if (!box) return;
  box.hidden = item.input_modes === false;
  const mode = inputMode(item);
  for (const button of box.querySelectorAll("[data-game-input]")) button.setAttribute("aria-pressed", String(button.dataset.gameInput === mode));
}

// The Hatchling hears the deck's music (5.6.4), a few times a second.
let hearing = 0;
function hearMusic() {
  window.clearInterval(hearing);
  hearing = 0;
  if (playing !== "hatchling") return;
  hearing = window.setInterval(() => {
    if (playing !== "hatchling" || !frame) { window.clearInterval(hearing); hearing = 0; return; }
    const heard = window.voidcompassMusicLevels?.();
    if (heard?.playing) frame.contentWindow?.postMessage({source: "voidcompass-deck", type: "levels", bands: heard.bands, playing: true}, "*");
  }, 100);
}

function setInput(mode) {
  const item = game(playing);
  if (!item) return;
  store(`voidcompass.games.${item.id}.input`, mode);
  showInput(item);
  frame?.contentWindow?.postMessage({source: "voidcompass-deck", type: "input", mode: inputMode(item)}, "*");
  frame?.focus();
}

function sendLive() {
  const item = game(playing);
  if (!frame?.contentWindow || !item) return;
  const key = JSON.stringify(item.live ?? null);
  if (key === lastLiveKey) return;
  lastLiveKey = key;
  frame.contentWindow.postMessage({source: "voidcompass-deck", type: "live", live: item.live ?? null}, "*");
}

function tell(type) {
  frame?.contentWindow?.postMessage({source: "voidcompass-deck", type}, "*");
}

function openGame(id) {
  const item = game(id);
  const stage = ui.byId("games-stage");
  if (!item || !stage) return;
  playing = item.id;
  lastRunsKey = "";
  lastLiveKey = "";
  ui.byId("games-player").hidden = false;
  document.querySelector(".games-library").hidden = true;
  ui.byId("games-title").textContent = item.title;
  ui.byId("games-genre").textContent = item.genre.toUpperCase();
  ui.byId("games-about").textContent = item.description || item.tagline;
  showInput(item);
  hearMusic();
  ui.byId("games-controls").innerHTML = item.controls.map(([keys, action]) =>
    `<dt>${ui.escapeHtml(keys)}</dt><dd>${ui.escapeHtml(action)}</dd>`).join("");
  ui.byId("games-player").style.setProperty("--game-tone", item.accent || "var(--accent)");
  renderRuns();
  // A fresh frame each time: RESTART is a clean cabinet.
  frame?.remove();
  frame = document.createElement("iframe");
  frame.className = "games-frame";
  frame.title = item.title;
  frame.setAttribute("sandbox", "allow-scripts");
  frame.setAttribute("allow", "autoplay");
  frame.src = item.entry;
  stage.replaceChildren(frame);
  frame.addEventListener("load", () => frame?.focus());
}

function closeGame() {
  if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
  frame?.remove();
  frame = null;
  playing = "";
  const player = ui.byId("games-player");
  if (player) player.hidden = true;
  const library = document.querySelector(".games-library");
  if (library) library.hidden = false;
}

async function received(event) {
  if (!frame || event.source !== frame.contentWindow) return;
  const data = event.data || {};
  if (data.source !== "voidcompass-game") return;
  const item = game(playing);
  if (!item) return;
  if (data.type === "ready") hello();
  else if (data.type === "mute") store(`voidcompass.games.${item.id}.muted`, data.muted ? "1" : "0");
  else if (data.type === "crt") store(`voidcompass.games.${item.id}.crt`, data.on ? "1" : "0");
  else if (data.type === "action") {
    // "act", not "action": the deck's command already uses that key for its own name.
    await ui.command("workspace", {page: "games", operation: "action", game: item.id,
      act: String(data.action || "").slice(0, 20), value: data.value && typeof data.value === "object" ? data.value : {}});
  } else if (data.type === "snap" && item.id === "hatchling" && typeof data.png === "string" && data.png.length < 20_000_000) {
    // The Hatchling's SNAP (5.6.4): its pod, saved as a postcard.
    try {
      const response = await fetch(ui.apiUrl("/api/postcard-save"), {
        method: "POST", cache: "no-store", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({mode: "snap", png: data.png}),
      });
      const reply = await response.json().catch(() => ({}));
      if (!response.ok || !reply.ok) throw new Error(reply.error || `HTTP ${response.status}`);
      ui.showToast?.("Postcard saved: it's on the Postcards page");
    } catch (error) {
      ui.showToast?.(`The postcard wasn't saved: ${error.message}`);
    }
  } else if (data.type === "over") {
    await ui.command("workspace", {page: "games", operation: "score", game: item.id,
      score: data.score, wave: data.wave ?? data.level, accuracy: data.accuracy, rank: data.rank});
  }
}

function watch() {
  if (watching) return;
  watching = true;
  window.addEventListener("message", received);
  // Leaving the page pauses the game (it keeps its place).
  const page = document.querySelector('[data-page-name="games"]');
  if (page) {
    new MutationObserver(() => { if (!page.classList.contains("active")) tell("pause"); })
      .observe(page, {attributes: true, attributeFilter: ["class"]});
  }
  document.addEventListener("visibilitychange", () => { if (document.hidden) tell("pause"); });
}

export function renderGames(data = {}, deckUi) {
  ui = deckUi;
  const root = ui.byId("games-workspace");
  if (!root) return;
  if (!root.querySelector(".games-page")) shell(root);
  watch();
  games = Array.isArray(data.games) ? data.games : [];
  if (Array.isArray(data.card_size) && data.card_size.length === 2) cardSize = data.card_size;
  renderCards();
  if (playing && !game(playing)) closeGame();
  else if (playing) { renderRuns(); sendLive(); }
}

window.voidcompassGames = {state: () => ({games: games.map((item) => item.id), playing, framed: Boolean(frame)})};
