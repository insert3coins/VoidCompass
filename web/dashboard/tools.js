// Tools (5.5.4): everything you switch often, in one place. Each switch is
// the same setting as on its own page; this only gathers them.

let lastKey = "";
// The overlay filter is the pilot's, kept across refreshes.
const view = {filter: "all", find: ""};

const PAGES = [
  ["explore", "✦", "Explore & Survey"], ["planet-materials", "◇", "Planet sites"], ["ground", "⬡", "Ground & exobio"],
  ["map", "◉", "Galactic Atlas"], ["mining", "◆", "Mining"], ["carrier", "◈", "Carrier"], ["trading", "⇄", "Trading"],
  ["watcher", "◉", "The Watcher"], ["music", "♪", "Music"], ["postcards", "✉", "Postcards"],
  ["screenshots", "▣", "Screenshots"], ["capsules", "⧗", "Time Capsules"], ["constellation", "✧", "Constellation"],
];
const THOUGHTS = [["off", "Off"], ["rare", "Rare"], ["occasional", "Occasional"], ["chatty", "Chatty"]];
const SERVICE_HOMES = new Set(["integrations", "galnet"]);
const SERVICE_OF = {edsm_upload_enabled: "edsm", inara_upload_enabled: "inara"};

function shell(root, ui) {
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="tools-page">
    <section class="tools-strip" aria-label="Right now">
      <div class="tools-readout tools-here"><small>LOCATION</small><b id="tools-here">Waiting for the game</b>
        <button type="button" data-tool="copy-system" title="Copy the system name">COPY</button></div>
      <div class="tools-readout"><small>OVERLAYS</small><b id="tools-live-count">—</b></div>
      <div class="tools-readout"><small>THE WATCHER</small><b id="tools-watcher-state">—</b></div>
      <div class="tools-readout"><small>MUSIC</small><b id="tools-music-state">—</b></div>
      <div class="tools-readout"><small>COMPASS</small><b id="tools-compass-readout">—</b></div>
    </section>

    <div class="tools-main">
      <section class="tools-card tools-overlays" aria-labelledby="tools-overlays-title">
        <header><h3 id="tools-overlays-title">OVERLAYS</h3>
          <div class="tools-filter" role="group" aria-label="Show overlays">
            <button type="button" data-tools-filter="all">ALL</button><button type="button" data-tools-filter="on">LIVE</button><button type="button" data-tools-filter="off">OFF</button></div>
          <input type="search" id="tools-find" placeholder="Find an overlay" aria-label="Find an overlay" autocomplete="off">
          <button type="button" data-page="overlay-studio">PLACE THEM</button></header>
        <div class="tools-groups" id="tools-overlays"></div>
        <p class="tools-note tools-none" id="tools-overlays-none" hidden>No overlay matches.</p>
      </section>
      <section class="tools-card tools-switches" aria-labelledby="tools-switches-title">
        <header><h3 id="tools-switches-title">SWITCHES</h3><button type="button" data-page="settings">SETTINGS</button></header>
        <div class="tools-groups" id="tools-switches"></div>
      </section>
    </div>

    <aside class="tools-side">
      <section class="tools-card tools-watcher"><header><h3>THE WATCHER</h3><button type="button" data-page="watcher">ITS PAGE</button></header>
        <div id="tools-watcher"></div></section>
      <section class="tools-card tools-music"><header><h3>MUSIC</h3><button type="button" data-page="music">ITS PAGE</button></header>
        <div class="tools-now" id="tools-now"></div>
        <div class="tools-transport"><button type="button" data-tool="music" data-action="previous" aria-label="Previous track">⏮</button>
          <button type="button" class="primary" data-tool="music" data-action="toggle" id="tools-play">PLAY</button>
          <button type="button" data-tool="music" data-action="next" aria-label="Next track">⏭</button></div></section>
      <section class="tools-card tools-compass-card"><header><h3>COMPASS</h3><button type="button" data-page="planet-materials">PLANET SITES</button></header>
        <div class="tools-compass"><label>LATITUDE<input id="tools-lat" type="number" step="0.000001" min="-90" max="90" placeholder="32.328"></label>
          <label>LONGITUDE<input id="tools-lon" type="number" step="0.000001" min="-180" max="180" placeholder="108.838"></label></div>
        <div class="tools-buttons"><button type="button" class="primary" data-tool="compass-set">SEND</button>
          <button type="button" data-tool="compass-current" id="tools-compass-current">USE CURRENT</button><button type="button" data-tool="compass-clear">CLEAR</button></div>
        <p class="tools-note" id="tools-compass-state"></p></section>
      <section class="tools-card tools-actions"><header><h3>QUICK ACTIONS</h3></header>
        <div class="tools-action-list">
          <button type="button" data-tool="open-journal"><i>▤</i>Journal folder</button>
          <button type="button" data-command="open_screenshots"><i>▣</i>Screenshot folder</button>
          <button type="button" data-tool="open-capsules"><i>⧗</i>Capsule folder</button>
          <button type="button" data-command="check_updates" data-update-check><i>⟳</i>Check for updates</button>
        </div></section>
    </aside>

    <nav class="tools-jump" aria-label="Go to a page"><h3>JUMP TO</h3>
      <div>${PAGES.map(([page, glyph, name]) => `<button type="button" data-page="${page}"><i>${glyph}</i><span>${name}</span></button>`).join("")}</div></nav>
  </div>`;

  const send = (operation, extra = {}) => ui.command("workspace", {page: "tools", operation, ...extra});
  root.addEventListener("change", async (event) => {
    const tile = event.target.closest(".tools-switch");
    tile?.classList.toggle("on", event.target.checked);
    const overlay = event.target.closest("[data-tool-overlay]");
    if (overlay) {
      if (!(await send("overlay", {id: overlay.dataset.toolOverlay}))) ui.showToast("That overlay didn't change");
      return;
    }
    const setting = event.target.closest("[data-tool-setting]");
    if (setting) {
      if (!(await send("setting", {key: setting.dataset.toolSetting, value: setting.checked}))) ui.showToast("That setting wasn't saved");
      return;
    }
    if (event.target.id === "tools-voice") await send("voice", {value: event.target.checked});
  });
  root.addEventListener("input", (event) => {
    if (event.target.id !== "tools-find") return;
    view.find = event.target.value.trim().toLowerCase();
    applyFilter(ui);
  });
  root.addEventListener("click", async (event) => {
    const filter = event.target.closest("[data-tools-filter]");
    if (filter) {
      view.filter = filter.dataset.toolsFilter;
      applyFilter(ui);
      return undefined;
    }
    const button = event.target.closest("[data-tool]");
    if (!button) return undefined;
    const tool = button.dataset.tool;
    if (tool === "music") return send("music", {action: button.dataset.action});
    if (tool === "poke") return send("poke");
    if (tool === "thoughts") {
      for (const other of button.parentElement.children) other.setAttribute("aria-checked", String(other === button));
      return send("thoughts", {value: button.dataset.value});
    }
    if (tool === "copy-system") return ui.showToast((await send("copy_system")) ? "System name copied" : "No system yet");
    if (tool === "open-journal") return send("open_journal");
    if (tool === "open-capsules") return send("open_capsules");
    if (tool === "compass-set") {
      const lat = ui.byId("tools-lat").value, lon = ui.byId("tools-lon").value;
      if (lat === "" || lon === "") return ui.showToast("Enter a latitude and longitude");
      return ui.showToast((await ui.command("workspace", {page: "ground", operation: "set", lat, lon})) ? "Compass armed" : "Those coordinates weren't accepted");
    }
    if (tool === "compass-current") return ui.command("workspace", {page: "ground", operation: "set_current"});
    if (tool === "compass-clear") return ui.command("workspace", {page: "ground", operation: "clear"});
    return undefined;
  });
}

const toggle = (attrs, label, detail, checked, chip = "") => `<label class="tools-switch${checked ? " on" : ""}" data-name="${label.toLowerCase()}"><input type="checkbox" ${attrs}${checked ? " checked" : ""}>
  <i></i><span><b>${label}</b>${detail ? `<small>${detail}</small>` : ""}</span>${chip}</label>`;

// Hides what the filter leaves out, and any group left empty.
function applyFilter(ui) {
  const root = ui.byId("tools-overlays");
  if (!root) return;
  let shown = 0;
  for (const group of root.querySelectorAll(".tools-group")) {
    let left = 0;
    for (const tile of group.querySelectorAll(".tools-switch")) {
      const on = tile.classList.contains("on");
      const hide = (view.filter === "on" && !on) || (view.filter === "off" && on) || (view.find && !tile.dataset.name.includes(view.find));
      tile.hidden = hide;
      if (!hide) left += 1;
    }
    group.hidden = !left;
    shown += left;
  }
  ui.byId("tools-overlays-none").hidden = shown > 0;
  for (const button of ui.byId("tools-workspace").querySelectorAll("[data-tools-filter]")) {
    button.setAttribute("aria-pressed", String(button.dataset.toolsFilter === view.filter));
  }
}

function group(label, tiles, count = "") {
  return `<div class="tools-group"><h4>${label}${count ? `<span>${count}</span>` : ""}</h4><div class="tools-grid">${tiles}</div></div>`;
}

export function renderTools(data = {}, ui) {
  const root = ui.byId("tools-workspace");
  if (!root) return;
  if (!root.querySelector(".tools-page")) shell(root, ui);
  const key = JSON.stringify(data);
  if (key === lastKey) return;
  lastKey = key;
  const esc = ui.escapeHtml;

  const overlays = data.overlays || [];
  const live = overlays.filter((row) => row.enabled).length;
  ui.byId("tools-overlays").innerHTML = (data.groups || [{id: "other", label: "Overlays"}]).map((row) => {
    const members = overlays.filter((overlay) => (overlay.group || "other") === row.id);
    if (!members.length) return "";
    const on = members.filter((overlay) => overlay.enabled).length;
    return group(esc(row.label), members.map((overlay) =>
      toggle(`data-tool-overlay="${esc(overlay.id)}"`, esc(overlay.label), "", overlay.enabled)).join(""), `${on} / ${members.length}`);
  }).join("");
  applyFilter(ui);
  ui.byId("tools-live-count").textContent = `${live} of ${overlays.length} live`;

  const services = data.services || {};
  const switchTile = (row) => {
    const state = services[SERVICE_OF[row.key]];
    const chip = state && row.on ? `<em class="tools-chip ${esc(state.state)}">${esc(state.label)}</em>` : "";
    return toggle(`data-tool-setting="${esc(row.key)}"`, esc(row.label), esc(row.detail), row.on, chip);
  };
  const switches = data.switches || [];
  ui.byId("tools-switches").innerHTML =
    group("Connected services", switches.filter((row) => SERVICE_HOMES.has(row.home)).map(switchTile).join(""))
    + group("Behaviour", switches.filter((row) => !SERVICE_HOMES.has(row.home)).map(switchTile).join(""));

  const watcher = data.watcher || {};
  const thoughts = THOUGHTS.map(([value, name]) => `<button type="button" role="radio" data-tool="thoughts" data-value="${value}" aria-checked="${value === watcher.thoughts}">${name}</button>`).join("");
  ui.byId("tools-watcher").innerHTML = `
    <div class="tools-orb-row"><div class="tools-orb${watcher.voice ? " speaking" : ""}${watcher.orb ? "" : " asleep"}" aria-hidden="true"><i></i></div>
      <p>${watcher.orb ? (watcher.voice ? "Watching, and speaking." : "Watching, in silence.") : "Its orb is switched off. Turn on Journal Heartbeat to see it."}</p></div>
    ${toggle('id="tools-voice"', "Its voice", watcher.installed ? "Thoughts spoken aloud." : "Switching it on downloads the voice first.", watcher.voice)}
    <div class="tools-field"><span><b>Thoughts</b><small>How often it says something.</small></span>
      <div class="tools-segments" role="radiogroup" aria-label="How often it says something">${thoughts}</div></div>
    <button type="button" class="tools-poke" data-tool="poke" ${watcher.orb ? "" : "disabled"}>POKE IT</button>`;
  const thoughtName = (THOUGHTS.find(([value]) => value === watcher.thoughts) || [])[1] || "—";
  ui.byId("tools-watcher-state").textContent = `${watcher.voice ? "Voice on" : "Voice off"} · ${thoughtName}`;

  const music = data.music || {};
  const playing = music.state === "playing";
  ui.byId("tools-now").innerHTML = music.state && music.state !== "idle"
    ? `<small>${playing ? "NOW PLAYING" : "PAUSED"}</small><b>${esc(music.title || "Untitled")}</b>${music.artist ? `<span>${esc(music.artist)}</span>` : ""}`
    : `<small>NOTHING QUEUED</small><span>Pick a playlist on the Music page.</span>`;
  ui.byId("tools-now").classList.toggle("playing", playing);
  ui.byId("tools-play").textContent = playing ? "PAUSE" : "PLAY";
  ui.byId("tools-music-state").textContent = music.state && music.state !== "idle"
    ? `${playing ? "▶" : "❚❚"} ${music.title || "Untitled"}` : "Silent";

  const target = data.target || {};
  const armed = target.active
    ? `${target.label ? `${target.label} · ` : ""}${Number(target.lat).toFixed(4)}, ${Number(target.lon).toFixed(4)}` : "";
  ui.byId("tools-compass-state").textContent = armed ? `Armed: ${armed}` : "No compass target.";
  ui.byId("tools-compass-readout").textContent = armed || "No target";
  ui.byId("tools-compass-current").disabled = !data.on_planet;
  ui.byId("tools-compass-current").title = data.on_planet ? "Point the compass at where you are now" : "Only on or near a planet";
  // A body is named after its system; only the part after it is new.
  const body = data.body && data.body !== data.system ? data.body.replace(data.system, "").trim() || data.body : "";
  ui.byId("tools-here").textContent = data.system ? `${data.system}${body ? ` · ${body}` : ""}` : "Waiting for the game";
}
