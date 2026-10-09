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
    <section class="watcher-eye-panel" aria-label="The Watcher">
      <div class="watcher-eye"><canvas id="watcher-orb" aria-hidden="true"></canvas></div>
      <blockquote class="watcher-latest" id="watcher-latest"><span></span><cite></cite></blockquote>
      <div class="watcher-actions">
        <button type="button" class="primary" data-ws-page="watcher" data-ws-op="poke" id="watcher-poke">POKE</button>
        <small id="watcher-hotkey"></small>
      </div>
      <dl class="watcher-character" id="watcher-character"></dl>
    </section>
    <section class="watcher-bond-panel" aria-label="You and the Watcher">
      <header><span>YOU AND THE WATCHER</span><b id="watcher-bond-name"></b></header>
      <div class="watcher-bond-meter" id="watcher-bond-meter" role="progressbar" aria-valuemin="0" aria-valuemax="100"><i></i></div>
      <p class="watcher-bond-next" id="watcher-bond-next"></p>
      <div class="watcher-stats" id="watcher-stats"></div>
      <header><span>YOUR RECORDS</span><b>FROM YOUR JOURNALS</b></header>
      <div class="watcher-stats" id="watcher-records"></div>
      <header><span>WHAT IT TALKS ABOUT MOST</span></header>
      <ol class="watcher-favourites" id="watcher-favourites"></ol>
    </section>
    <section class="watcher-log-panel" aria-label="What it has said">
      <header><span>WHAT IT HAS SAID</span><b id="watcher-log-count"></b></header>
      <ol class="watcher-log" id="watcher-log"></ol>
    </section>
  </div>`;
  const canvas = root.querySelector("#watcher-orb");
  if (window.HeartbeatOrb && canvas) {
    orb?.dispose?.();
    orb = new window.HeartbeatOrb(canvas);
    window.watcherPageOrb = orb;
  }
  root.querySelector("#watcher-poke").addEventListener("click", () => {
    // It looks up as you poke it; the answer arrives with the next refresh.
    orb?.showMood?.("curious");
    orb?.think?.(500);
  });
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

  ui.byId("watcher-log-count").textContent = `${ui.numeric(log.length)} SHOWN · ${ui.numeric(data.thoughts)} IN ALL`;
  const key = JSON.stringify(log.slice(0, 3).map((row) => [row.at, row.text]).concat([log.length]));
  if (key !== lastLogKey) {
    lastLogKey = key;
    ui.byId("watcher-log").innerHTML = log.length
      ? log.map((row) => `<li data-mood="${ui.escapeHtml(row.mood || "")}"><time>${ui.escapeHtml(ago(row.at))}</time><p>${ui.escapeHtml(row.text)}</p>${row.mood ? `<b>${MOOD_LABELS[row.mood] || ""}</b>` : ""}</li>`).join("")
      : `<li class="empty">Its thoughts will be kept here as it shares them.</li>`;
  }
}
