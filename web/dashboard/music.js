// Music: the player that runs behind every page of the command deck, and
// the Music page's playlists.
//
// The deck is the player. Each track streams from the local dashboard
// server by id (/media/music/<id>): files play from wherever they are and
// are never copied. Python keeps the library and remembers the player for
// the commander; this page reports what it is doing about once a second
// (so the music overlay can show it and it resumes next time), carries out
// hotkeys that arrive in the snapshot and, while the overlay is on, sends
// the visualizer's levels about fifteen times a second.
//
// The analyser listens to a captured copy of the sound (captureStream), so
// it can never be what silences playback: sound always goes straight from
// the <audio> element to the speakers.

const BANDS = 32;
const LEVELS_MS = 66;
const STATUS_MS = 1000;
const ICON_PATHS = {play: "M8 5v14l11-7z", pause: "M6 5h4v14H6zM14 5h4v14h-4z"};
const REPEAT_NEXT = {off: "all", all: "one", one: "off"};
const REPEAT_LABEL = {off: "OFF", all: "ALL", one: "ONE"};

export function createMusicDeck({apiUrl, showToast, byId, escapeHtml, duration}) {
  const audio = new Audio();
  audio.preload = "auto";
  const page = document.querySelector('[data-page-name="music"]');

  let library = {revision: -1, playlists: [], tracks: {}, tagging: 0};
  let wantedRevision = -1;
  let fetching = false;
  let saved = null;
  let restored = false;
  let playlistId = "";
  let viewId = "";
  let order = [];
  let index = -1;
  let currentId = "";
  let shuffle = false;
  let repeat = "all";
  let volume = 80;
  let blocked = false;
  let failures = 0;
  let resumeAt = null;
  let seen = null;
  let overlayOn = false;
  let pageShown = false;
  let find = "";
  let dragging = false;
  let statusTimer = 0;
  let levelsTimer = 0;
  let reportTimer = 0;
  let frame = 0;

  // --- The analyser, on a captured copy of the sound ------------------------
  let context = null;
  let analyser = null;
  let capture = null;
  let source = null;
  let boundTrack = null;
  let bins = null;
  let edges = null;

  function listen() {
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context || typeof audio.captureStream !== "function") return;
    if (!context) {
      context = new Context();
      analyser = context.createAnalyser();
      analyser.fftSize = 2048;
      analyser.smoothingTimeConstant = .7;
      bins = new Uint8Array(analyser.frequencyBinCount);
      // Bands spaced the way the ear hears pitch: 40 Hz to 16 kHz.
      const nyquist = context.sampleRate / 2;
      edges = Array.from({length: BANDS + 1}, (_, band) =>
        Math.min(bins.length - 1, Math.round(40 * Math.pow(400, band / BANDS) / nyquist * bins.length)));
    }
    if (context.state === "suspended") context.resume().catch(() => {});
    try {
      if (!capture) {
        capture = audio.captureStream();
        // Each new source gives the capture a new track; follow it.
        capture.addEventListener("addtrack", listen);
      }
      const live = capture.getAudioTracks().filter((track) => track.readyState === "live");
      const track = live[live.length - 1];
      if (track && track !== boundTrack) {
        source?.disconnect();
        source = context.createMediaStreamSource(new MediaStream([track]));
        source.connect(analyser);
        boundTrack = track;
      }
    } catch (_error) {
      // Nothing loaded to capture yet; the next 'playing' tries again.
    }
  }

  function levels() {
    if (!analyser || audio.paused) return new Array(BANDS).fill(0);
    analyser.getByteFrequencyData(bins);
    return edges.slice(0, BANDS).map((start, band) => {
      let peak = 0;
      for (let bin = start; bin < Math.max(start + 1, edges[band + 1]); bin += 1) peak = Math.max(peak, bins[bin]);
      return peak;
    });
  }

  // --- Talking to Python --------------------------------------------------------
  // Quiet: status and levels are routine, and a missed one is soon replaced.
  function post(payload, keepalive = false) {
    return fetch(apiUrl("/api/command"), {
      method: "POST", cache: "no-store", keepalive,
      headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
    }).catch(() => {});
  }
  const music = (operation, payload = {}) => post({action: "music", operation, ...payload});

  function upNext() {
    if (!order.length || index < 0) return "";
    if (repeat === "one") return currentId;
    if (index + 1 < order.length) return order[index + 1];
    return repeat === "all" ? order[0] : "";
  }

  function status() {
    return {
      track_id: currentId, next_id: upNext(), playlist_id: playlistId,
      position: resumeAt ?? audio.currentTime ?? 0,
      duration: Number.isFinite(audio.duration) ? audio.duration : (trackOf(currentId)?.duration || 0),
      playing: !audio.paused, blocked, volume, shuffle, repeat, reported_at: Date.now(),
    };
  }

  function report() {
    window.clearTimeout(reportTimer);
    reportTimer = window.setTimeout(() => music("status", status()), 60);
  }

  function startTimers() {
    window.clearInterval(statusTimer);
    window.clearInterval(levelsTimer);
    statusTimer = window.setInterval(report, STATUS_MS);
    levelsTimer = overlayOn
      ? window.setInterval(() => post({action: "music_levels", bands: levels(), playing: true}), LEVELS_MS) : 0;
  }

  function stopTimers() {
    window.clearInterval(statusTimer);
    window.clearInterval(levelsTimer);
    statusTimer = levelsTimer = 0;
    if (overlayOn) post({action: "music_levels", bands: new Array(BANDS).fill(0), playing: false});
  }

  // --- The library -----------------------------------------------------------------
  const trackOf = (id) => library.tracks[id] || null;
  const playlistOf = (id) => library.playlists.find((item) => item.id === id) || null;
  const playable = (id) => (playlistOf(id)?.tracks || []).filter((key) => library.tracks[key]);

  async function fetchLibrary() {
    if (fetching) return;
    fetching = true;
    try {
      const response = await fetch(apiUrl("/api/music/library"), {cache: "no-store"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      library = await response.json();
    } catch (_error) {
      fetching = false;
      window.setTimeout(fetchLibrary, 1500);
      return;
    }
    fetching = false;
    if (!restored && saved) restore(saved);
    if (!playlistOf(viewId)) viewId = library.playlists[0]?.id || "";
    if (playlistId && !playlistOf(playlistId)) {
      stop();
      playlistId = "";
    } else if (playlistId && currentId) {
      // A playlist edited while it plays carries on from the same track.
      arrange(currentId, true);
    }
    renderLibrary();
    renderNow();
    // The library moved on again while that request was out.
    if (library.revision < wantedRevision) fetchLibrary();
  }

  function restore(settings) {
    restored = true;
    volume = Math.max(0, Math.min(100, Number(settings.volume ?? 80)));
    shuffle = Boolean(settings.shuffle);
    repeat = REPEAT_NEXT[settings.repeat] ? settings.repeat : "all";
    audio.volume = volume / 100;
    playlistId = playlistOf(settings.playlist_id) ? settings.playlist_id : "";
    viewId = playlistId || library.playlists[0]?.id || "";
    // Back where the commander left off, paused: it never starts by surprise.
    if (playlistId && playable(playlistId).includes(settings.track_id)) {
      arrange(settings.track_id);
      load(settings.track_id, {play: false, at: Number(settings.position) || 0});
    }
  }

  // --- Playing ----------------------------------------------------------------------
  function shuffled(tracks, first) {
    const rest = tracks.filter((key) => key !== first);
    for (let spot = rest.length - 1; spot > 0; spot -= 1) {
      const pick = Math.floor(Math.random() * (spot + 1));
      [rest[spot], rest[pick]] = [rest[pick], rest[spot]];
    }
    return first ? [first, ...rest] : rest;
  }

  // The play order: the playlist's own, or shuffled with this track first.
  // Keeping an existing shuffle (after an edit) keeps what was already heard.
  function arrange(startId, keep = false) {
    const tracks = playable(playlistId);
    if (shuffle && keep && order.length) {
      order = [...order.filter((key) => tracks.includes(key)), ...tracks.filter((key) => !order.includes(key))];
    } else {
      order = shuffle ? shuffled(tracks, startId) : tracks;
    }
    index = startId ? order.indexOf(startId) : (order.length ? 0 : -1);
  }

  function load(id, {play: start = true, at = 0} = {}) {
    if (!trackOf(id)) return;
    currentId = id;
    resumeAt = at > 0 ? at : null;
    audio.src = apiUrl(`/media/music/${id}`);
    audio.load();
    describeToWindows();
    renderNow();
    markCurrent();
    if (start) play();
    else report();
  }

  async function play() {
    if (!currentId) {
      playlistId = playlistId || viewId;
      const tracks = playable(playlistId);
      if (!tracks.length) return;
      arrange(shuffle ? tracks[Math.floor(Math.random() * tracks.length)] : tracks[0]);
      load(order[index]);
      return;
    }
    try {
      listen();
      await audio.play();
      blocked = false;
    } catch (error) {
      // WebView2 may want one click in its window before sound can start by
      // itself (from a hotkey, say): say so rather than failing silently.
      if (error?.name === "NotAllowedError") blocked = true;
    }
    renderNow();
    report();
  }

  const pause = () => audio.pause();
  const toggle = () => (audio.paused ? play() : pause());

  function stop() {
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
    currentId = "";
    order = [];
    index = -1;
    renderNow();
    report();
  }

  function skip(forward, automatic = false) {
    if (!order.length) return play();
    if (!forward && audio.currentTime > 3) {
      // Back goes to the start of the track first, as players do.
      audio.currentTime = 0;
      return undefined;
    }
    if (automatic && repeat === "one") {
      audio.currentTime = 0;
      return play();
    }
    let next = index + (forward ? 1 : -1);
    if (next >= order.length) {
      if (automatic && repeat === "off") {
        // The end of the playlist: stop at its start, ready to go again.
        index = 0;
        return load(order[0], {play: false});
      }
      if (shuffle) order = shuffled(order, "");
      next = 0;
    } else if (next < 0) {
      next = order.length - 1;
    }
    index = next;
    return load(order[index]);
  }

  function playFromList(id, position) {
    playlistId = viewId;
    const tracks = playable(playlistId);
    if (shuffle) {
      order = shuffled(tracks, id);
      index = 0;
    } else {
      order = tracks;
      index = order[position] === id ? position : order.indexOf(id);
    }
    failures = 0;
    load(id);
  }

  audio.addEventListener("loadedmetadata", () => {
    if (resumeAt != null && Number.isFinite(audio.duration)) {
      audio.currentTime = Math.min(resumeAt, Math.max(0, audio.duration - 1));
    }
    resumeAt = null;
    const known = trackOf(currentId);
    if (known && Number.isFinite(audio.duration) && Math.abs((known.duration || 0) - audio.duration) > .5) {
      // The tags guessed the length; playing measured it.
      known.duration = audio.duration;
      music("set_duration", {track_id: currentId, duration: audio.duration});
    }
    renderNow();
  });
  audio.addEventListener("playing", () => {
    failures = 0;
    listen();
    startTimers();
    renderNow();
    report();
    if (pageShown && !frame) frame = window.requestAnimationFrame(drawVisualizer);
  });
  audio.addEventListener("pause", () => {
    stopTimers();
    renderNow();
    report();
  });
  audio.addEventListener("ended", () => skip(true, true));
  audio.addEventListener("timeupdate", renderTime);
  audio.addEventListener("error", () => {
    if (!currentId || !audio.getAttribute("src")) return;
    failures += 1;
    showToast(`Could not play ${trackOf(currentId)?.title || "that track"}: the file may have moved.`);
    if (failures < Math.max(1, order.length)) window.setTimeout(() => skip(true, true), 700);
    else stopTimers();
  });
  window.addEventListener("pagehide", () => post({action: "music", operation: "status", ...status()}, true));

  // What is playing, for Windows' own media controls and the keyboard's
  // media keys, where the WebView offers them. The app's hotkeys work either way.
  function describeToWindows() {
    const session = navigator.mediaSession;
    const track = trackOf(currentId);
    if (!session || !track || typeof window.MediaMetadata !== "function") return;
    session.metadata = new window.MediaMetadata({
      title: track.title, artist: track.artist, album: track.album,
      artwork: track.art ? [{src: apiUrl(`/media/art/${currentId}.jpg`), sizes: "360x360", type: "image/jpeg"}] : [],
    });
  }
  if (navigator.mediaSession) {
    for (const [name, handler] of Object.entries({
      play, pause, nexttrack: () => skip(true), previoustrack: () => skip(false),
    })) {
      try {
        navigator.mediaSession.setActionHandler(name, handler);
      } catch (_error) {
        // Not every action is offered everywhere.
      }
    }
  }

  // --- Drawing the page -----------------------------------------------------------
  function renderNow() {
    const deck = byId("music-deck");
    if (!deck) return;
    const track = trackOf(currentId);
    const playing = !audio.paused;
    deck.classList.toggle("playing", playing);
    deck.classList.toggle("idle", !track);
    byId("music-title").textContent = track?.title || "Nothing playing";
    byId("music-artist").textContent = track ? track.artist || "Unknown artist"
      : "Choose a playlist below and double-click a track.";
    byId("music-details").textContent = track
      ? [track.album, track.year, track.genre, track.format].filter(Boolean).join("  ·  ") : "";
    byId("music-state").textContent = blocked ? "WAITING FOR A CLICK" : playing ? "NOW PLAYING" : track ? "PAUSED" : "STANDBY";
    byId("music-source").textContent = playlistOf(playlistId)?.name.toUpperCase() || "NO PLAYLIST";
    const cover = byId("music-cover");
    const src = track?.art ? apiUrl(`/media/art/${currentId}.jpg`) : "";
    if (cover.dataset.src !== src) {
      cover.dataset.src = src;
      cover.hidden = !src;
      if (src) cover.src = src;
      else cover.removeAttribute("src");
    }
    const button = byId("music-play");
    button.querySelector("path")?.setAttribute("d", ICON_PATHS[playing ? "pause" : "play"]);
    button.setAttribute("aria-label", playing ? "Pause" : "Play");
    button.title = playing ? "Pause" : "Play";
    byId("music-shuffle").setAttribute("aria-pressed", String(shuffle));
    const repeatButton = byId("music-repeat");
    repeatButton.setAttribute("aria-pressed", String(repeat !== "off"));
    repeatButton.querySelector("span").textContent = REPEAT_LABEL[repeat];
    repeatButton.title = `Repeat: ${REPEAT_LABEL[repeat].toLowerCase()}`;
    const slider = byId("music-volume");
    if (document.activeElement !== slider) slider.value = String(volume);
    slider.style.setProperty("--fill", `${volume}%`);
    byId("music-volume-value").textContent = String(volume);
    byId("music-blocked").hidden = !blocked;
    renderTime();
  }

  function renderTime() {
    const elapsed = byId("music-elapsed");
    if (!elapsed || dragging) return;
    const total = Number.isFinite(audio.duration) ? audio.duration : (trackOf(currentId)?.duration || 0);
    const at = resumeAt ?? audio.currentTime ?? 0;
    elapsed.textContent = duration(at);
    byId("music-total").textContent = duration(total);
    const seek = byId("music-seek");
    seek.value = String(total ? Math.round(at / total * 1000) : 0);
    seek.style.setProperty("--fill", `${total ? at / total * 100 : 0}%`);
  }

  function markCurrent() {
    page?.querySelectorAll(".music-row").forEach((row) => {
      row.classList.toggle("current", row.dataset.track === currentId && viewId === playlistId);
    });
    page?.querySelectorAll(".music-playlist").forEach((button) => {
      button.classList.toggle("live", button.dataset.playlist === playlistId && Boolean(currentId));
    });
  }

  function renderLibrary() {
    if (!page) return;
    const lists = library.playlists;
    byId("music-playlist-count").textContent = String(lists.length);
    byId("music-playlists").innerHTML = lists.length ? lists.map((item) => {
      const count = item.tracks.length;
      return `<button type="button" class="music-playlist${item.id === viewId ? " selected" : ""}" data-playlist="${escapeHtml(item.id)}">`
        + `<span>${escapeHtml(item.name)}</span><small>${count} track${count === 1 ? "" : "s"}</small></button>`;
    }).join("") : `<p class="music-note">No playlists yet. Name one above, or import an M3U playlist from another player.</p>`;
    const view = playlistOf(viewId);
    page.querySelectorAll("[data-music-list]").forEach((button) => { button.disabled = !view; });
    byId("music-list-name").textContent = view?.name || "No playlist";
    const rows = (view?.tracks || []).map((id, position) => ({id, position, track: trackOf(id)})).filter((row) => row.track);
    const total = rows.reduce((sum, row) => sum + (row.track.duration || 0), 0);
    byId("music-list-meta").textContent = view
      ? `${rows.length} track${rows.length === 1 ? "" : "s"} · ${duration(total)}${library.tagging ? ` · reading tags (${library.tagging} left)` : ""}`
      : "";
    const list = byId("music-tracks");
    if (!view) {
      list.innerHTML = `<div class="music-empty"><b>Your music stays where it is.</b><span>Make a playlist, then add music files or whole folders from anywhere on this PC, or import an M3U. Void Compass remembers where each file lives and plays it from there.</span></div>`;
      return;
    }
    if (!rows.length) {
      list.innerHTML = `<div class="music-empty"><b>An empty playlist.</b><span>Add files or a folder with ＋ FILES and ＋ FOLDER above.</span></div>`;
      return;
    }
    const needle = find.trim().toLowerCase();
    const shown = needle ? rows.filter(({track}) =>
      `${track.title} ${track.artist} ${track.album} ${track.genre}`.toLowerCase().includes(needle)) : rows;
    list.innerHTML = shown.map(({id, position, track}) => `
      <div class="music-row${track.missing ? " missing" : ""}${id === currentId && viewId === playlistId ? " current" : ""}" role="listitem" tabindex="0"
        data-track="${escapeHtml(id)}" data-position="${position}" title="Double-click to play">
        <span class="music-number">${position + 1}</span>
        <span class="music-eq" aria-hidden="true"><i></i><i></i><i></i></span>
        <span class="music-name">${track.art ? `<img src="${apiUrl(`/media/art/${id}.jpg`)}" alt="" loading="lazy">` : "<i>♪</i>"}<span><b>${escapeHtml(track.title)}</b><small>${escapeHtml(track.artist || "Unknown artist")}${track.missing ? " · FILE NOT FOUND" : ""}</small></span></span>
        <span class="music-album">${escapeHtml(track.album)}${track.year ? `<small>${escapeHtml(track.year)}</small>` : ""}</span>
        <span class="music-time">${track.duration ? duration(track.duration) : "—"}</span>
        <span class="music-row-actions">
          <button type="button" data-move="-1" aria-label="Move up" title="Move up"${position === 0 ? " disabled" : ""}>▲</button>
          <button type="button" data-move="1" aria-label="Move down" title="Move down"${position === rows.length - 1 ? " disabled" : ""}>▼</button>
          <button type="button" data-remove aria-label="Remove from the playlist" title="Remove from the playlist">✕</button>
        </span>
      </div>`).join("") || `<div class="music-empty"><b>Nothing here matches “${escapeHtml(find)}”.</b></div>`;
  }

  // The deck's visualizer, drawn while the Music page is on screen.
  function drawVisualizer() {
    frame = 0;
    const canvas = byId("music-visualizer");
    if (!pageShown || !canvas || !canvas.clientWidth) return;
    const width = canvas.clientWidth, height = canvas.clientHeight, ratio = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const style = getComputedStyle(document.documentElement);
    const accent = style.getPropertyValue("--accent").trim();
    const orange = style.getPropertyValue("--orange").trim();
    const gap = 4, bar = (width - gap * (BANDS - 1)) / BANDS;
    const fill = ctx.createLinearGradient(0, height, 0, 0);
    fill.addColorStop(0, accent);
    fill.addColorStop(1, orange);
    ctx.fillStyle = fill;
    levels().forEach((level, band) => {
      const tall = Math.max(2, level / 255 * height);
      ctx.globalAlpha = .12 + level / 255 * .2;
      ctx.fillRect(band * (bar + gap), height - tall, bar, tall);
    });
    if (!audio.paused) frame = window.requestAnimationFrame(drawVisualizer);
  }

  function showPage(active) {
    pageShown = active;
    if (!active) return;
    music("recheck");
    renderLibrary();
    renderNow();
    if (!frame) frame = window.requestAnimationFrame(drawVisualizer);
  }

  // --- The page's controls -----------------------------------------------------------
  function nativePicker(name) {
    const api = window.pywebview?.api;
    if (typeof api?.[name] !== "function") {
      showToast("Choosing files works in the Void Compass window.");
      return null;
    }
    return api[name].bind(api);
  }

  page?.addEventListener("pointerdown", () => {
    if (context?.state === "suspended") context.resume().catch(() => {});
  });
  byId("music-play")?.addEventListener("click", () => {
    blocked = false;
    toggle();
  });
  byId("music-previous")?.addEventListener("click", () => skip(false));
  byId("music-next")?.addEventListener("click", () => skip(true));
  byId("music-shuffle")?.addEventListener("click", () => {
    shuffle = !shuffle;
    if (playlistId && currentId) arrange(currentId);
    renderNow();
    report();
  });
  byId("music-repeat")?.addEventListener("click", () => {
    repeat = REPEAT_NEXT[repeat];
    renderNow();
    report();
  });
  byId("music-volume")?.addEventListener("input", (event) => {
    volume = Math.round(Number(event.target.value));
    audio.volume = volume / 100;
    event.target.style.setProperty("--fill", `${volume}%`);
    byId("music-volume-value").textContent = String(volume);
  });
  byId("music-volume")?.addEventListener("change", report);
  byId("music-seek")?.addEventListener("input", (event) => {
    dragging = true;
    const total = Number.isFinite(audio.duration) ? audio.duration : 0;
    byId("music-elapsed").textContent = duration(total * Number(event.target.value) / 1000);
    event.target.style.setProperty("--fill", `${Number(event.target.value) / 10}%`);
  });
  byId("music-seek")?.addEventListener("change", (event) => {
    dragging = false;
    const total = Number.isFinite(audio.duration) ? audio.duration : 0;
    if (total) audio.currentTime = total * Number(event.target.value) / 1000;
    report();
  });
  byId("music-create")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = byId("music-create-name");
    music("create_playlist", {name: input.value.trim() || "New playlist"});
    input.value = "";
  });
  byId("music-find")?.addEventListener("input", (event) => {
    find = event.target.value;
    renderLibrary();
  });
  byId("music-import")?.addEventListener("click", async () => {
    const choose = nativePicker("choose_playlist_file");
    const path = choose ? await choose() : "";
    if (path) music("import_m3u", {path});
  });
  byId("music-add-files")?.addEventListener("click", async () => {
    const choose = nativePicker("choose_music_files");
    const paths = choose ? await choose() : [];
    if (paths?.length) music("add_paths", {playlist_id: viewId, paths});
  });
  byId("music-add-folder")?.addEventListener("click", async () => {
    const choose = nativePicker("choose_folder");
    const path = choose ? await choose() : "";
    if (path) music("add_paths", {playlist_id: viewId, paths: [path]});
  });
  byId("music-export")?.addEventListener("click", async () => {
    const choose = nativePicker("choose_playlist_export");
    const path = choose ? await choose(playlistOf(viewId)?.name || "Playlist") : "";
    if (path) music("export_m3u", {playlist_id: viewId, path});
  });
  byId("music-rename")?.addEventListener("click", () => {
    const view = playlistOf(viewId);
    const name = view ? window.prompt("Rename this playlist:", view.name) : "";
    if (name?.trim()) music("rename_playlist", {playlist_id: viewId, name: name.trim()});
  });
  byId("music-delete")?.addEventListener("click", () => {
    const view = playlistOf(viewId);
    if (!view || !window.confirm(`Delete the playlist "${view.name}"? Your music files are not touched.`)) return;
    if (view.id === playlistId) {
      stop();
      playlistId = "";
    }
    music("delete_playlist", {playlist_id: view.id});
  });
  page?.addEventListener("click", (event) => {
    const list = event.target.closest("[data-playlist]");
    if (list) {
      viewId = list.dataset.playlist;
      find = "";
      byId("music-find").value = "";
      renderLibrary();
      return;
    }
    const row = event.target.closest(".music-row");
    if (!row) return;
    const position = Number(row.dataset.position);
    if (event.target.closest("[data-remove]")) {
      music("remove_tracks", {playlist_id: viewId, positions: [position]});
    } else if (event.target.closest("[data-move]")) {
      music("move_track", {playlist_id: viewId, from: position,
        to: position + Number(event.target.closest("[data-move]").dataset.move)});
    }
  });
  page?.addEventListener("dblclick", (event) => {
    const row = event.target.closest(".music-row");
    if (row && !event.target.closest(".music-row-actions")) playFromList(row.dataset.track, Number(row.dataset.position));
  });
  page?.addEventListener("keydown", (event) => {
    const row = event.target.closest?.(".music-row");
    if (row && event.key === "Enter") playFromList(row.dataset.track, Number(row.dataset.position));
  });
  // Space plays and pauses while the Music page is open, outside text boxes.
  document.addEventListener("keydown", (event) => {
    if (!pageShown || event.code !== "Space" || event.repeat) return;
    if (event.target.closest?.("input, textarea, select, button, [contenteditable]")) return;
    event.preventDefault();
    toggle();
  });

  // --- The snapshot ------------------------------------------------------------------
  function update(model) {
    const state = model?.music;
    if (!state) return;
    const overlayWas = overlayOn;
    overlayOn = Boolean(state.overlay);
    if (overlayOn !== overlayWas && !audio.paused) startTimers();
    if (!saved) saved = state.settings || {};
    wantedRevision = Number(state.library_revision);
    if (wantedRevision > library.revision) fetchLibrary();
    // Remote actions and messages arrive numbered. Those from before this
    // page loaded are not replayed.
    const numbers = {remote: Number(state.remote?.seq) || 0, focus: Number(state.focus?.seq) || 0,
      notice: Number(state.notice?.seq) || 0};
    if (!seen) seen = numbers;
    if (numbers.remote > seen.remote) {
      ({toggle, next: () => skip(true), previous: () => skip(false)})[state.remote.op]?.();
    }
    if (numbers.focus > seen.focus && state.focus.playlist_id) {
      viewId = state.focus.playlist_id;
      renderLibrary();
    }
    if (numbers.notice > seen.notice && state.notice.text) showToast(state.notice.text);
    seen = numbers;
    const working = byId("music-working");
    if (working) working.hidden = !state.working;
  }

  window.voidcompassMusic = {
    state: () => ({currentId, playlistId, viewId, order: [...order], index, playing: !audio.paused, shuffle,
      repeat, volume, blocked, src: audio.getAttribute("src") || "", revision: library.revision}),
    audio,
  };

  return {update, showPage};
}
