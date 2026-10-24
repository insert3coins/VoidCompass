// The postcard slideshow (5.6.3): your postcards dealt one by one onto a desk,
// full screen, each landing at its own angle over the last. Arrows step,
// Space pauses, S shuffles, Esc leaves.

const DESKS = {
  wood: "linear-gradient(135deg, #2a180e, #5a3820 45%, #2a180e)",
  space: "radial-gradient(ellipse at 30% 25%, #1d1650, #04050c 70%)",
  hangar: "linear-gradient(180deg, #1b1f24, #0c0e11)",
};

let show = null;

export function showOpen() {
  return Boolean(show);
}

export function startShow({ui, rows, start = 0, eliteDate}) {
  stopShow();
  if (!rows.length) return;
  const root = document.createElement("div");
  root.className = "pc-show";
  root.innerHTML = `<div class="pc-show-desk" id="pc-show-desk"></div>
    <div class="pc-show-caption" id="pc-show-caption"></div>
    <nav class="pc-show-bar">
      <button type="button" data-show="prev" title="Previous (←)">‹</button>
      <button type="button" data-show="play" id="pc-show-play" title="Pause (Space)">❚❚</button>
      <button type="button" data-show="next" title="Next (→)">›</button>
      <button type="button" data-show="shuffle" id="pc-show-shuffle" title="Shuffle (S)">SHUFFLE</button>
      <select id="pc-show-speed" aria-label="Speed"><option value="4000">FAST</option><option value="6500" selected>STEADY</option><option value="10000">SLOW</option></select>
      <select id="pc-show-desk-pick" aria-label="Desk"><option value="wood">DESK</option><option value="space">DEEP SPACE</option><option value="hangar">HANGAR</option></select>
      <span class="pc-show-count" id="pc-show-count"></span>
      <button type="button" data-show="close" title="Leave (Esc)">✕</button>
    </nav>
    <div class="pc-show-progress"><i id="pc-show-progress"></i></div>`;
  document.body.append(root);
  show = {ui, rows: [...rows], order: rows.map((_, index) => index), at: start, root, playing: true, timer: 0, wait: 6500, shuffled: false,
    eliteDate, dealt: []};
  try {
    const desk = localStorage.getItem("voidcompass.postcards.desk");
    if (desk && DESKS[desk]) root.querySelector("#pc-show-desk-pick").value = desk;
  } catch { /* the wooden desk, then */ }
  paintDesk();
  root.addEventListener("click", onClick);
  root.addEventListener("change", onChange);
  document.addEventListener("keydown", onKey, true);
  root.requestFullscreen?.().catch(() => {});
  deal();
}

export function stopShow() {
  if (!show) return;
  window.clearTimeout(show.timer);
  document.removeEventListener("keydown", onKey, true);
  if (document.fullscreenElement === show.root) document.exitFullscreen?.().catch(() => {});
  show.root.remove();
  show = null;
}

function paintDesk() {
  const pick = show.root.querySelector("#pc-show-desk-pick").value;
  show.root.querySelector("#pc-show-desk").style.background = DESKS[pick] || DESKS.wood;
  try { localStorage.setItem("voidcompass.postcards.desk", pick); } catch { /* not kept */ }
}

function current() {
  return show.rows[show.order[show.at]];
}

// One card dealt onto the desk; the last few stay under it, then fade.
function deal() {
  if (!show) return;
  const row = current();
  const desk = show.root.querySelector("#pc-show-desk");
  const card = document.createElement("img");
  card.className = "pc-show-card";
  card.alt = row.title;
  card.src = show.ui.apiUrl(`/media/postcard/${row.id}.png?v=${encodeURIComponent(row.at)}`);
  const seed = [...row.id].reduce((sum, char) => (sum * 31 + char.charCodeAt(0)) | 0, 7);
  const turn = ((Math.abs(seed) % 13) - 6) * .9;
  const dx = ((Math.abs(seed >> 3) % 9) - 4) * 1.2, dy = ((Math.abs(seed >> 6) % 7) - 3) * 1.2;
  card.style.setProperty("--turn", `${turn}deg`);
  card.style.setProperty("--dx", `${dx}vw`);
  card.style.setProperty("--dy", `${dy}vh`);
  card.style.setProperty("--from", `${(seed % 2 ? 1 : -1) * 60}vw`);
  desk.append(card);
  show.dealt.push(card);
  while (show.dealt.length > 4) show.dealt.shift().remove();
  show.dealt.forEach((item, index) => item.classList.toggle("under", index < show.dealt.length - 1));
  const when = row.taken || row.at;
  show.root.querySelector("#pc-show-caption").innerHTML = `<b>${show.ui.escapeHtml(row.title)}</b>
    <span>${show.ui.escapeHtml([row.region, show.eliteDate(when)].filter(Boolean).join(" · "))}</span>
    ${row.note ? `<em>“${show.ui.escapeHtml(row.note)}”</em>` : ""}`;
  show.root.querySelector("#pc-show-count").textContent = `${show.at + 1} / ${show.rows.length}`;
  restartClock();
}

function restartClock() {
  window.clearTimeout(show.timer);
  const bar = show.root.querySelector("#pc-show-progress");
  bar.style.transition = "none";
  bar.style.width = "0%";
  if (!show.playing) return;
  void bar.offsetWidth;
  bar.style.transition = `width ${show.wait}ms linear`;
  bar.style.width = "100%";
  show.timer = window.setTimeout(() => step(1), show.wait);
}

function step(by) {
  if (!show) return;
  show.at = (show.at + by + show.rows.length) % show.rows.length;
  deal();
}

function setPlaying(on) {
  show.playing = on;
  show.root.querySelector("#pc-show-play").textContent = on ? "❚❚" : "▶";
  restartClock();
}

function shuffle() {
  const now = show.order[show.at];
  show.shuffled = !show.shuffled;
  show.order = show.rows.map((_, index) => index);
  if (show.shuffled) {
    for (let i = show.order.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [show.order[i], show.order[j]] = [show.order[j], show.order[i]];
    }
  }
  show.at = Math.max(0, show.order.indexOf(now));
  show.root.querySelector("#pc-show-shuffle").classList.toggle("active", show.shuffled);
  show.root.querySelector("#pc-show-count").textContent = `${show.at + 1} / ${show.rows.length}`;
}

function onClick(event) {
  const button = event.target.closest("[data-show]");
  if (!button) return;
  const what = button.dataset.show;
  if (what === "close") stopShow();
  else if (what === "prev") step(-1);
  else if (what === "next") step(1);
  else if (what === "play") setPlaying(!show.playing);
  else if (what === "shuffle") shuffle();
}

function onChange(event) {
  if (event.target.id === "pc-show-speed") { show.wait = Number(event.target.value) || 6500; restartClock(); }
  if (event.target.id === "pc-show-desk-pick") paintDesk();
}

function onKey(event) {
  if (!show) return;
  const keys = {ArrowLeft: () => step(-1), ArrowRight: () => step(1), " ": () => setPlaying(!show.playing), Escape: stopShow, s: shuffle, S: shuffle};
  const act = keys[event.key];
  if (!act) return;
  event.preventDefault();
  event.stopPropagation();
  act();
}

window.voidcompassPostcardShow = {state: () => (show ? {at: show.at, count: show.rows.length, playing: show.playing, shuffled: show.shuffled} : null)};
