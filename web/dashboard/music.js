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
// the <audio> element to the speakers. The copy is taken before the
// element's volume, so the same capture also measures each track's own
// loudness for levelling.

const BANDS = 32;
const LEVELS_MS = 66;
const STATUS_MS = 1000;
// Loudness is in LUFS, the scale streaming services and broadcasters use.
// Tracks are mastered anywhere from about -6 LUFS (loud modern masters) to
// -20 (older and classical), so one slider position is too loud for some and
// too quiet for others, and a straight 0-1 slider crowds everything useful
// into its bottom few steps. Levelling plays every track at LEVEL_TARGET at
// full volume, and the slider is an even taper in decibels below that.
const LEVEL_TARGET = -20;
// A track not measured yet is taken to be as loud as a typical modern master,
// so at full volume it starts about 11 dB down, as it does with levelling off.
const LEVEL_ASSUMED = -9;
// A quiet track is raised by at most this much (the player can't go above
// full scale in any case).
const LEVEL_MAX_BOOST_DB = 12;
// The slider covers this many dB, from full volume down to its first step.
const VOLUME_RANGE_DB = 40;
// A track with no loudness tag is measured as it first plays: 100 ms samples
// of the captured copy. After TRUST samples the estimate steers the level, at
// no more than SLEW dB a second and never beyond SWING dB of the assumption,
// so a quiet intro can't make the chorus blast. KEEP samples make a
// measurement worth remembering; the next play starts at the right level.
const METER_MS = 100;
const METER_TRUST = 80;
const METER_KEEP = 300;
const LEVEL_SLEW_DB_S = 1;
const FIRST_LISTEN_SWING_DB = 6;
const ICON_PATHS = {play: "M8 5v14l11-7z", pause: "M6 5h4v14H6zM14 5h4v14h-4z"};
const REPEAT_NEXT = {off: "all", all: "one", one: "off"};
const REPEAT_LABEL = {off: "OFF", all: "ALL", one: "ONE"};
// The player's live state, kept in session storage: it survives this page
// reloading (WebView2 losing its renderer, say) but not the app closing. A
// page that finds it playing moments ago carries on instead of resuming
// paused as a fresh start does.
const LIVE_KEY = "voidcompass.music.live";
// Music that flies with you (5.5.3.8): the scenes the game can be in, how
// long a calm change waits before the music follows (combat doesn't), and
// how far hyperspace ducks it.
const SCENES = [["docked", "Docked"], ["space", "Space"], ["deep", "Deep space"], ["surface", "Surface"], ["combat", "Combat"]];
const SCENE_SETTLE_MS = 4000;
const DUCK_TO = .3;
const LIVE_RESUME_MS = 15000;
// Long mixes carry on where they were left (5.5.17), as the library keeps it.
const RESUME_MIN_S = 20 * 60;
const RESUME_END_S = 120;
const RESUME_MIN_IN_S = 30;
const UP_NEXT_SHOWN = 3;
// Lists made from your library and your listening, never saved as files.
const SMART = [["smart:added", "Recently added"], ["smart:most", "Most played"], ["smart:never", "Never played"],
  ["smart:long", "Long mixes"]];
const RECENT_VIEW = "recent";
const FOLLOW_VIEW = "follow";
const FOLLOW_OPEN_KEY = "voidcompass.music.follow-open";
// The player bar's visualizer looks (5.5.17), kept per viewer.
const VISUALIZER_KEY = "voidcompass.music.visualizer";
const VISUALIZERS = [
  {id: "bars", label: "BARS", detail: "Spectrum bars", group: "CLASSIC"},
  {id: "peaks", label: "PEAKS", detail: "Bars with falling peaks", group: "CLASSIC"},
  {id: "mirror", label: "MIRROR", detail: "The spectrum, mirrored", group: "CLASSIC"},
  {id: "led", label: "LED", detail: "A dot-matrix level meter", group: "CLASSIC"},
  {id: "wave", label: "WAVE", detail: "The waveform itself", group: "FLOWING"},
  {id: "horizon", label: "HORIZON", detail: "A smooth spectrum skyline", group: "FLOWING"},
  {id: "aurora", label: "AURORA", detail: "Ribbons of light: bass, mids and treble", group: "FLOWING"},
  {id: "waterfall", label: "WATERFALL", detail: "The spectrum scrolling past", group: "FLOWING"},
  {id: "shockwave", label: "SHOCKWAVE", detail: "A ring for every beat", group: "FLOWING"},
  {id: "scanner", label: "SCANNER", detail: "Your ship's scanner, a contact for every band", group: "ELITE"},
  {id: "witchspace", label: "WITCHSPACE", detail: "The jump tunnel, faster as it gets louder", group: "ELITE"},
  {id: "off", label: "OFF", detail: "No visualizer", group: ""},
];
const SORT_VALUE = {
  title: (row) => row.track.title.toLowerCase(),
  artist: (row) => (row.track.artist || "").toLowerCase(),
  played: (row) => row.plays,
  added: (row) => row.track.added || 0,
  time: (row) => row.track.duration || 0,
};

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
  let normalise = true;
  // The current track's level offset in dB, eased toward wantedLevel().
  let levelDb = LEVEL_TARGET - LEVEL_ASSUMED;
  let meterTimer = 0;
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
  // Following the game: its settings, the scene now, the music's two
  // extra gains (a fade between playlists, a duck for hyperspace), and where
  // each playlist was left so it picks up there.
  let follow = {on: false, playlists: {}, fade_s: 2, duck: true};
  let scene = "";
  let jumping = false;
  let fadeMix = 1;
  let duckMix = 1;
  let duckTarget = 1;
  const ramps = {};
  let switching = false;
  let followKey = "";
  let sceneTimer = 0;
  let followRendered = "";
  const leftAt = {};
  // 5.5.17: the queue (this session only), the list's selection and sort,
  // your listening from the diary, and where each long mix was left.
  let queue = [];
  let fromQueue = false;
  let selected = new Set();
  let anchor = -1;
  let sortKey = "order";
  let sortDown = false;
  let stats = {revision: -1, plays: {}, recent: [], listening: {}};
  let resume = {};
  const touched = new Set();
  let smartCache = {key: "", lists: {}};
  let dragging_rows = null;
  const drawn = {};
  let followOpen = null;
  try {
    const kept = window.localStorage.getItem(FOLLOW_OPEN_KEY);
    if (kept !== null) followOpen = kept === "1";
  } catch (_error) { /* opens as the setting suggests */ }
  let visualizer = "bars";
  try {
    const kept = window.localStorage.getItem(VISUALIZER_KEY);
    if (VISUALIZERS.some((look) => look.id === kept)) visualizer = kept;
  } catch (_error) { /* bars, as ever */ }
  // What the moving looks remember between frames.
  let caps = new Array(BANDS).fill(0);
  let trail = null;
  let rings = [];
  let stars = [];
  let bassAverage = 0;
  let lastRing = 0;
  let lastDraw = 0;

  // --- The analyser, on a captured copy of the sound ------------------------
  let context = null;
  let analyser = null;
  let capture = null;
  let source = null;
  let boundTrack = null;
  let bins = null;
  let samples = null;
  let edges = null;
  let meterNodes = null;

  function listen() {
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context || typeof audio.captureStream !== "function") return;
    if (!context) {
      context = new Context();
      analyser = context.createAnalyser();
      analyser.fftSize = 2048;
      analyser.smoothingTimeConstant = .7;
      bins = new Uint8Array(analyser.frequencyBinCount);
      samples = new Uint8Array(analyser.fftSize);
      // Bands spaced the way the ear hears pitch: 40 Hz to 16 kHz.
      const nyquist = context.sampleRate / 2;
      edges = Array.from({length: BANDS + 1}, (_, band) =>
        Math.min(bins.length - 1, Math.round(40 * Math.pow(400, band / BANDS) / nyquist * bins.length)));
      meterNodes = buildMeter(context);
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
        source.connect(meterNodes.input);
        boundTrack = track;
        meter.skip = 3;
      }
    } catch (_error) {
      // Nothing loaded to capture yet; the next 'playing' tries again.
    }
  }

  // BS.1770 loudness as closely as Web Audio allows: K-weighting (a high
  // shelf, then a high pass) on both channels, their powers summed. A mono
  // file is spread to both sides first, as the speakers play it.
  function buildMeter(audioContext) {
    const input = audioContext.createGain();
    input.channelCount = 2;
    input.channelCountMode = "explicit";
    input.channelInterpretation = "speakers";
    const shelf = audioContext.createBiquadFilter();
    shelf.type = "highshelf";
    shelf.frequency.value = 1681.97;
    shelf.gain.value = 4;
    const pass = audioContext.createBiquadFilter();
    pass.type = "highpass";
    pass.frequency.value = 38.13;
    pass.Q.value = .5;
    const split = audioContext.createChannelSplitter(2);
    input.connect(shelf).connect(pass).connect(split);
    const sides = [0, 1].map((channel) => {
      const side = audioContext.createAnalyser();
      side.fftSize = 4096;
      split.connect(side, channel);
      return side;
    });
    return {input, sides, data: new Float32Array(4096)};
  }

  // What the meter has heard of the current track. It waits for the track to
  // be playing, then lets the analyser's buffer (the previous track's last
  // 85 ms) pass before counting: one stray block of a loud track would read a
  // quiet one 3 dB too loud.
  const meter = {track: "", blocks: [], firstListen: false, kept: false, skip: Infinity};

  function resetMeter(id) {
    keepMeasurement();
    meter.track = id;
    meter.blocks = [];
    meter.kept = false;
    meter.skip = Infinity;
    meter.firstListen = Boolean(id) && !Number.isFinite(trackOf(id)?.loudness);
  }

  function sampleMeter() {
    if (!meterNodes || !currentId || audio.paused || audio.seeking || meter.track !== currentId) return;
    if (meter.skip > 0) {
      meter.skip -= 1;
      return;
    }
    let power = 0;
    for (const side of meterNodes.sides) {
      side.getFloatTimeDomainData(meterNodes.data);
      let sum = 0;
      for (const value of meterNodes.data) sum += value * value;
      power += sum / meterNodes.data.length;
    }
    meter.blocks.push(power);
    if (meter.blocks.length === METER_KEEP) keepMeasurement();
  }

  // Integrated loudness of the blocks heard: silence (below -70 LUFS) and
  // the quiet passages (10 LU under the rest) don't count, as in BS.1770.
  const SILENCE_POWER = 10 ** ((-70 + 0.691) / 10);
  function measuredLoudness() {
    const audible = meter.blocks.filter((power) => power > SILENCE_POWER);
    if (!audible.length) return null;
    const mean = (rows) => rows.reduce((sum, value) => sum + value, 0) / rows.length;
    const floor = mean(audible) / 10;
    const counted = audible.filter((power) => power > floor);
    return -0.691 + 10 * Math.log10(mean(counted.length ? counted : audible));
  }

  function keepMeasurement() {
    if (!meter.track || meter.blocks.length < METER_KEEP || trackOf(meter.track)?.loudness_source === "tag") return;
    const lufs = measuredLoudness();
    if (lufs == null) return;
    meter.kept = true;
    music("set_loudness", {track_id: meter.track, lufs: Math.round(lufs * 100) / 100});
  }

  // The level offset the current track should play at, in dB.
  function wantedLevel() {
    if (!normalise) return LEVEL_TARGET - LEVEL_ASSUMED;
    const known = trackOf(currentId)?.loudness;
    if (!meter.firstListen && Number.isFinite(known)) return Math.min(LEVEL_MAX_BOOST_DB, LEVEL_TARGET - known);
    const heard = meter.blocks.length >= METER_TRUST ? measuredLoudness() : null;
    if (heard == null) return LEVEL_TARGET - LEVEL_ASSUMED;
    const bounded = Math.max(LEVEL_ASSUMED - FIRST_LISTEN_SWING_DB, Math.min(LEVEL_ASSUMED + FIRST_LISTEN_SWING_DB, heard));
    return LEVEL_TARGET - bounded;
  }

  function applyVolume() {
    const taper = -VOLUME_RANGE_DB * (1 - volume / 100);
    const base = volume > 0 ? Math.min(1, 10 ** ((taper + levelDb) / 20)) : 0;
    audio.volume = Math.max(0, Math.min(1, base * fadeMix * duckMix));
  }

  // --- Following the game (5.5.3.8) -----------------------------------------------
  // Ease one of the extra gains to a level over a time; resolves when there.
  function ramp(kind, target, ms) {
    window.clearInterval(ramps[kind]);
    return new Promise((resolve) => {
      const from = kind === "fade" ? fadeMix : duckMix;
      const started = performance.now();
      const step = () => {
        const done = Math.min(1, (performance.now() - started) / Math.max(1, ms));
        const level = from + (target - from) * done;
        if (kind === "fade") fadeMix = level; else duckMix = level;
        applyVolume();
        if (done >= 1) {
          window.clearInterval(ramps[kind]);
          resolve();
        }
      };
      ramps[kind] = window.setInterval(step, 30);
      step();
    });
  }

  // The playlist for the scene the game is in, faded across, picking up
  // where that playlist was left. Only while music is playing: it never
  // starts by itself.
  async function switchTo(target, song = "") {
    const tracks = playable(target);
    if (!tracks.includes(song)) song = "";
    if (switching || !tracks.length || (target === playlistId && (!song || song === currentId))) return;
    switching = true;
    const fadeMs = Number(follow.fade_s || 2) * 1000;
    try {
      await ramp("fade", 0, fadeMs);
      if (playlistId && currentId) leftAt[playlistId] = {track: currentId, at: audio.currentTime};
      playlistId = target;
      const back = leftAt[target];
      if (song) {
        // The scene's own song, from the top; the playlist carries on after.
        arrange(song);
        load(song, {play: true, at: 0});
      } else if (back && tracks.includes(back.track)) {
        arrange(back.track);
        load(back.track, {play: true, at: back.at});
      } else {
        arrange(shuffle ? tracks[Math.floor(Math.random() * tracks.length)] : tracks[0]);
        load(order[index], {play: true});
      }
      renderLibrary();
      await ramp("fade", 1, fadeMs);
    } finally {
      fadeMix = 1;
      applyVolume();
      switching = false;
    }
  }

  function followGame() {
    // Hyperspace: down while the jump lasts, back up after.
    const wanted = follow.on && follow.duck && jumping ? DUCK_TO : 1;
    if (wanted !== duckTarget) {
      // A new ease replaces one still under way.
      duckTarget = wanted;
      ramp("duck", wanted, 700);
    }
    const target = follow.on && scene ? String(follow.playlists?.[scene] || "") : "";
    const song = target ? String(follow.tracks?.[scene] || "") : "";
    const key = `${follow.on}|${scene}|${target}|${song}`;
    if (key === followKey) return;
    followKey = key;
    window.clearTimeout(sceneTimer);
    if (!target || !playlistOf(target) || audio.paused) return;
    if (target === playlistId && (!song || song === currentId)) return;
    // A calm change waits a moment (a station's mass lock flickers); combat
    // doesn't wait.
    sceneTimer = window.setTimeout(() => {
      if (!audio.paused) switchTo(target, song);
    }, scene === "combat" ? 0 : SCENE_SETTLE_MS);
  }

  function renderFollow() {
    const panel = byId("music-follow");
    if (!panel) return;
    const names = library.playlists.map((list) => [list.id, list.name]);
    // A scene's song choices: its playlist's tracks.
    const songs = (id) => {
      const list = follow.playlists?.[id] || "";
      if (!list || !playlistOf(list)) return "";
      const chosen = follow.tracks?.[id] || "";
      return `<select data-follow="track:${id}" aria-label="${escapeHtml(id)} song">${option("", "Where it left off", chosen)}${playable(list)
        .map((track) => option(track, trackOf(track)?.title || "Track", chosen)).join("")}</select>`;
    };
    const open = viewId === FOLLOW_VIEW || (followOpen ?? follow.on);
    const state = byId("music-follow-state");
    if (state) {
      const now = SCENES.find(([id]) => id === scene);
      state.textContent = follow.on ? `On${now ? ` · ${now[1].toLowerCase()} now` : ""}` : "Off: a playlist per scene";
    }
    const key = JSON.stringify([follow, names, scene, library.revision, open]);
    if (key === followRendered) return;
    followRendered = key;
    panel.classList.toggle("collapsed", !open);
    const option = (value, label, chosen) => `<option value="${escapeHtml(value)}"${value === chosen ? " selected" : ""}>${escapeHtml(label)}</option>`;
    const now = SCENES.find(([id]) => id === scene);
    panel.innerHTML = `<header><button type="button" data-follow-fold aria-expanded="${open}"><span>FOLLOW THE GAME</span><i aria-hidden="true"></i></button><b class="${follow.on ? "on" : ""}">${follow.on ? (now ? `NOW: ${now[1].toUpperCase()}` : "WAITING FOR THE GAME") : "OFF"}</b></header>
      <label class="music-follow-switch"><input type="checkbox" data-follow="music_follow_game"${follow.on ? " checked" : ""}>
        <span><b>Change the music with the game</b><small>A playlist for each scene, faded across as you go. Only while music is playing; scenes left on "Keep playing" don't change it.</small></span></label>
      <div class="music-follow-scenes">${SCENES.map(([id, label]) => `<label class="${id === scene ? "now" : ""}"><span>${label}</span>
        <select data-follow="${id}">${option("", "Keep playing", follow.playlists?.[id] || "")}${names.map(([value, name]) => option(value, name, follow.playlists?.[id] || "")).join("")}</select>${songs(id)}</label>`).join("")}</div>
      <div class="music-follow-more">
        <label><span>Fade</span><select data-follow="music_follow_fade_s">${[1, 2, 4, 6].map((seconds) => option(String(seconds), `${seconds} s`, String(follow.fade_s))).join("")}</select></label>
        <label class="music-follow-switch"><input type="checkbox" data-follow="music_jump_duck"${follow.duck ? " checked" : ""}><span><b>Quieter in hyperspace</b></span></label>
      </div>`;
  }

  // --- Long mixes resume (5.5.17) ----------------------------------------------
  const longTrack = (id) => (trackOf(id)?.duration || 0) >= RESUME_MIN_S;

  function noteResume(id, at) {
    if (!id || !longTrack(id)) return;
    const length = id === currentId && Number.isFinite(audio.duration) ? audio.duration : trackOf(id).duration;
    const keep = at >= RESUME_MIN_IN_S && at <= length - RESUME_END_S;
    touched.add(id);
    if (keep) resume[id] = Math.round(at * 10) / 10;
    else delete resume[id];
    music("set_resume", {track_id: id, position: keep ? at : 0, duration: length});
  }

  function setVolume(value) {
    volume = Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
    applyVolume();
  }

  // A new track or a change of mode takes its level at once; a measurement
  // arriving mid-track eases in.
  function settleLevel(instant = false) {
    const wanted = wantedLevel();
    const step = LEVEL_SLEW_DB_S * METER_MS / 1000;
    levelDb = instant ? wanted : levelDb + Math.max(-step, Math.min(step, wanted - levelDb));
    applyVolume();
  }

  function levelDescription() {
    if (!normalise) return "Levelling off: tracks play as they were mastered, 11 dB down at full volume.";
    const track = trackOf(currentId);
    if (!track) return "Levelling on: every track plays equally loud.";
    const known = Number.isFinite(track.loudness) ? `${track.loudness.toFixed(1)} LUFS` : "";
    const source = meter.firstListen ? "measuring on this first play"
      : track.loudness_source === "tag" ? `${known}, from its ReplayGain tag`
        : known ? `${known}, measured` : "not measured yet";
    return `Levelling on: every track plays equally loud. This track: ${source}.`;
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
  // Every reply is read to its end. An unread fetch reply keeps its native
  // buffers until the garbage collector happens by, which on this small heap
  // is rarely: at fifteen level reports a second that held about 40 MB more
  // each minute, and WebView2 dropped the page after about 18 minutes.
  function post(payload, keepalive = false) {
    return fetch(apiUrl("/api/command"), {
      method: "POST", cache: "no-store", keepalive,
      headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
    }).then((response) => response.arrayBuffer()).catch(() => {});
  }
  const music = (operation, payload = {}) => post({action: "music", operation, ...payload});

  function upNext() {
    if (queue.length) return queue[0];
    if (!order.length || index < 0) return "";
    if (repeat === "one") return currentId;
    if (index + 1 < order.length) return order[index + 1];
    return repeat === "all" ? order[0] : "";
  }

  // What plays after this one: the queue first, then the playlist on.
  function upcoming(count = UP_NEXT_SHOWN) {
    const out = queue.slice(0, count).map((id) => ({id, queued: true}));
    if (!order.length || index < 0 || repeat === "one") return out;
    let at = index;
    while (out.length < count) {
      at += 1;
      if (at >= order.length) {
        if (repeat !== "all") break;
        at = 0;
      }
      if (at === index) break;
      out.push({id: order[at], queued: false});
    }
    return out;
  }

  function status() {
    return {
      track_id: currentId, next_id: upNext(), playlist_id: playlistId, upcoming: upcoming(3),
      scene: follow.on && scene && follow.playlists?.[scene] === playlistId ? scene : "",
      position: resumeAt ?? audio.currentTime ?? 0,
      duration: Number.isFinite(audio.duration) ? audio.duration : (trackOf(currentId)?.duration || 0),
      playing: !audio.paused, blocked, volume, shuffle, repeat, normalise, reported_at: Date.now(),
    };
  }

  function report() {
    window.clearTimeout(reportTimer);
    reportTimer = window.setTimeout(() => {
      const now = status();
      music("status", now);
      try {
        window.sessionStorage.setItem(LIVE_KEY, JSON.stringify({
          track: now.track_id, playlist: now.playlist_id, position: now.position, playing: now.playing, at: Date.now(),
        }));
      } catch (_error) { /* storage may be unavailable; a reload then resumes paused */ }
    }, 60);
  }

  function liveBeforeReload() {
    try {
      const live = JSON.parse(window.sessionStorage.getItem(LIVE_KEY) || "null");
      if (live?.playing && Date.now() - Number(live.at) < LIVE_RESUME_MS
          && playlistOf(live.playlist) && playable(live.playlist).includes(live.track)) return live;
    } catch (_error) { /* nothing usable */ }
    return null;
  }

  function startTimers() {
    window.clearInterval(statusTimer);
    window.clearInterval(levelsTimer);
    statusTimer = window.setInterval(report, STATUS_MS);
    window.clearInterval(meterTimer);
    meterTimer = window.setInterval(() => {
      sampleMeter();
      settleLevel();
    }, METER_MS);
    levelsTimer = overlayOn
      ? window.setInterval(() => post({action: "music_levels", bands: levels(), playing: true}), LEVELS_MS) : 0;
  }

  function stopTimers() {
    window.clearInterval(statusTimer);
    window.clearInterval(levelsTimer);
    window.clearInterval(meterTimer);
    statusTimer = levelsTimer = meterTimer = 0;
    if (overlayOn) post({action: "music_levels", bands: new Array(BANDS).fill(0), playing: false});
  }

  // --- The library -----------------------------------------------------------------
  const trackOf = (id) => library.tracks[id] || null;
  const playsOf = (id) => stats.plays?.[id]?.[0] || 0;

  function smartLists() {
    const key = `${library.revision}|${stats.revision}`;
    if (smartCache.key === key) return smartCache.lists;
    const ids = Object.keys(library.tracks);
    const lastPlayed = (id) => stats.plays?.[id]?.[1] || 0;
    const lists = {
      "smart:added": ids.filter((id) => trackOf(id).added).sort((a, b) => trackOf(b).added - trackOf(a).added).slice(0, 50),
      "smart:most": ids.filter((id) => playsOf(id)).sort((a, b) => playsOf(b) - playsOf(a) || lastPlayed(b) - lastPlayed(a)).slice(0, 50),
      "smart:never": ids.filter((id) => !playsOf(id)),
      "smart:long": ids.filter((id) => (trackOf(id).duration || 0) >= 3600).sort((a, b) => trackOf(b).duration - trackOf(a).duration),
    };
    smartCache = {key, lists};
    return lists;
  }

  function playlistOf(id) {
    if (String(id).startsWith("smart:")) {
      const entry = SMART.find(([key]) => key === id);
      return entry ? {id, name: entry[1], tracks: smartLists()[id] || [], smart: true} : null;
    }
    return library.playlists.find((item) => item.id === id) || null;
  }
  const playable = (id) => (playlistOf(id)?.tracks || []).filter((key) => library.tracks[key]);
  const isView = (id) => id === RECENT_VIEW || id === FOLLOW_VIEW || Boolean(playlistOf(id));

  async function fetchLibrary() {
    if (fetching) return;
    fetching = true;
    try {
      const response = await fetch(apiUrl("/api/music/library"), {cache: "no-store"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      library = await response.json();
      // The page's own notes win over the copy just fetched.
      const kept = {};
      for (const id of touched) if (resume[id]) kept[id] = resume[id];
      resume = {...Object.fromEntries(Object.entries(library.resume || {}).filter(([id]) => !touched.has(id))), ...kept};
    } catch (_error) {
      fetching = false;
      window.setTimeout(fetchLibrary, 1500);
      return;
    }
    fetching = false;
    if (!restored && saved) restore(saved);
    if (!isView(viewId)) viewId = library.playlists[0]?.id || "";
    selected.clear();
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
    normalise = settings.normalise !== false;
    setVolume(settings.volume ?? 80);
    shuffle = Boolean(settings.shuffle);
    repeat = REPEAT_NEXT[settings.repeat] ? settings.repeat : "all";
    playlistId = playlistOf(settings.playlist_id) ? settings.playlist_id : "";
    viewId = playlistId || library.playlists[0]?.id || "";
    // Back where the commander left off, paused: it never starts by surprise,
    // unless this page is reloading mid-song, when the music carries on.
    const live = liveBeforeReload();
    if (live) {
      playlistId = live.playlist;
      viewId = playlistId;
      arrange(live.track);
      load(live.track, {play: true, at: Number(live.position || 0) + (Date.now() - Number(live.at)) / 1000});
    } else if (playlistId && playable(playlistId).includes(settings.track_id)) {
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

  function load(id, {play: start = true, at = null} = {}) {
    if (!trackOf(id)) return;
    if (currentId && currentId !== id && audio.getAttribute("src")) noteResume(currentId, audio.currentTime);
    if (at == null) at = longTrack(id) && resume[id] ? resume[id] : 0;
    currentId = id;
    resumeAt = at > 0 ? at : null;
    resetMeter(id);
    settleLevel(true);
    audio.src = apiUrl(`/media/music/${id}`);
    audio.load();
    describeToWindows();
    renderNow();
    markCurrent();
    if (start) play();
    else report();
  }

  async function play() {
    if (!currentId && queue.length) {
      fromQueue = true;
      load(queue.shift());
      return;
    }
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
    resetMeter("");
    currentId = "";
    order = [];
    index = -1;
    renderNow();
    report();
  }

  function skip(forward, automatic = false) {
    if (forward && queue.length && !(automatic && repeat === "one")) {
      fromQueue = true;
      failures = 0;
      return load(queue.shift());
    }
    if (!order.length) return play();
    if (!forward && audio.currentTime > 3) {
      // Back goes to the start of the track first, as players do.
      audio.currentTime = 0;
      noteResume(currentId, 0);
      return undefined;
    }
    if (fromQueue) {
      // A queued track played between playlist tracks: carry on from there.
      fromQueue = false;
      if (!forward) return load(order[index]);
    }
    if (automatic && repeat === "one") {
      keepMeasurement();
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

  // The Flight Recorder (5.5.10): a past session's music, in the order it played.
  function playQueue(ids) {
    const tracks = (Array.isArray(ids) ? ids : []).filter((id) => trackOf(id));
    if (!tracks.length) return;
    order = tracks;
    index = 0;
    failures = 0;
    fromQueue = false;
    load(order[0]);
  }

  function playFromList(id, position, at = null) {
    fromQueue = false;
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
    load(id, {at});
  }

  // Straight in: plays now, and the playlist carries on after it.
  function playNow(id) {
    if (!trackOf(id)) return;
    queue.unshift(id);
    skip(true);
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
    meter.skip = Math.min(meter.skip, 3);
    startTimers();
    renderNow();
    report();
    if (pageShown && !frame) frame = window.requestAnimationFrame(drawVisualizer);
  });
  audio.addEventListener("pause", () => {
    // Not mid-load: a new track's pause would forget its own place.
    if (!audio.ended && resumeAt == null && audio.currentTime > 0) noteResume(currentId, audio.currentTime);
    stopTimers();
    renderNow();
    report();
  });
  audio.addEventListener("ended", () => {
    noteResume(currentId, 0);
    skip(true, true);
  });
  audio.addEventListener("timeupdate", renderTime);
  audio.addEventListener("error", () => {
    if (!currentId || !audio.getAttribute("src")) return;
    failures += 1;
    showToast(`Could not play ${trackOf(currentId)?.title || "that track"}: the file may have moved.`);
    if (failures < Math.max(1, order.length)) window.setTimeout(() => skip(true, true), 700);
    else stopTimers();
  });
  window.addEventListener("pagehide", () => {
    post({action: "music", operation: "status", ...status()}, true);
    if (meter.track && meter.blocks.length >= METER_KEEP && !meter.kept) {
      const lufs = measuredLoudness();
      if (lufs != null) post({action: "music", operation: "set_loudness", track_id: meter.track, lufs}, true);
    }
  });

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
    const levelButton = byId("music-level");
    if (levelButton) {
      levelButton.setAttribute("aria-pressed", String(normalise));
      levelButton.title = levelDescription();
    }
    const slider = byId("music-volume");
    if (document.activeElement !== slider) slider.value = String(volume);
    slider.style.setProperty("--fill", `${volume}%`);
    byId("music-volume-value").textContent = String(volume);
    byId("music-blocked").hidden = !blocked;
    // The player bar along the bottom (5.5.17) repeats the essentials.
    const barTitle = byId("music-bar-title");
    if (barTitle) {
      barTitle.textContent = track?.title || "Nothing playing";
      byId("music-bar-artist").textContent = track ? track.artist || "Unknown artist" : "";
      const small = byId("music-bar-cover");
      if (small.dataset.src !== src) {
        small.dataset.src = src;
        small.hidden = !src;
        if (src) small.src = src;
        else small.removeAttribute("src");
      }
    }
    const listPlay = byId("music-list-play");
    if (listPlay) {
      const live = viewId === playlistId && playing;
      listPlay.querySelector("path")?.setAttribute("d", ICON_PATHS[live ? "pause" : "play"]);
      listPlay.setAttribute("aria-label", live ? "Pause" : "Play this list");
    }
    renderTime();
    renderUpNext();
  }

  // Assign markup only when it changed: a redraw under the pointer loses clicks.
  function paint(node, html) {
    if (!node || drawn[node.id] === html) return false;
    drawn[node.id] = html;
    node.innerHTML = html;
    return true;
  }

  const artOf = (id) => (trackOf(id)?.art ? `<img src="${apiUrl(`/media/art/${id}.jpg`)}" alt="" loading="lazy">` : "<i>♪</i>");

  function renderUpNext() {
    const strip = byId("music-upnext");
    if (!strip) return;
    const next = currentId || queue.length ? upcoming() : [];
    strip.hidden = !next.length;
    paint(strip, next.length ? `<span class="music-upnext-label">UP NEXT</span><ol>${next.map(({id, queued}, spot) => `
      <li class="${queued ? "queued" : ""}" data-upnext="${escapeHtml(id)}" title="Double-click to play it now">${artOf(id)}
        <span><b>${escapeHtml(trackOf(id)?.title || "Track")}</b><small>${queued ? "QUEUED · " : ""}${escapeHtml(trackOf(id)?.artist || "")}</small></span>
        ${queued ? `<button type="button" data-unqueue="${spot}" aria-label="Take it out of the queue" title="Take it out of the queue">✕</button>` : ""}</li>`).join("")}</ol>
      ${queue.length ? `<button type="button" class="music-clear-queue" data-clear-queue>CLEAR QUEUE (${queue.length})</button>` : ""}` : "");
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
    // Where a long mix was left, while it waits to carry on.
    const mark = byId("music-resume-mark");
    const spot = resume[currentId];
    if (mark) {
      mark.hidden = !(spot && total && audio.paused);
      if (!mark.hidden) {
        mark.style.setProperty("--at", `${spot / total * 100}%`);
        mark.title = `Left off at ${duration(spot)}`;
      }
    }
  }

  function markCurrent() {
    page?.querySelectorAll(".music-row").forEach((row) => {
      row.classList.toggle("current", row.dataset.track === currentId && viewId === playlistId);
    });
    page?.querySelectorAll(".music-playlist, .music-smart").forEach((button) => {
      button.classList.toggle("live", button.dataset.playlist === playlistId && Boolean(currentId));
    });
  }

  function ago(seconds) {
    const gone = Math.max(0, Date.now() / 1000 - Number(seconds || 0));
    if (gone < 90) return "just now";
    if (gone < 3600) return `${Math.round(gone / 60)} min ago`;
    if (gone < 86400) return `${Math.round(gone / 3600)} h ago`;
    if (gone < 86400 * 14) return `${Math.round(gone / 86400)} d ago`;
    if (gone < 86400 * 60) return `${Math.round(gone / 604800)} wk ago`;
    return `${Math.round(gone / 2592000)} mo ago`;
  }

  function addedLabel(seconds) {
    if (!seconds) return "";
    const day = new Date(seconds * 1000);
    const options = {day: "numeric", month: "short"};
    if (day.getFullYear() !== new Date().getFullYear()) options.year = "numeric";
    return day.toLocaleDateString(undefined, options);
  }

  const hours = (seconds) => (seconds >= 36000 ? `${Math.round(seconds / 3600)} h`
    : seconds >= 3600 ? `${(seconds / 3600).toFixed(1)} h` : `${Math.round(seconds / 60)} min`);

  function renderLibrary() {
    if (!page) return;
    renderPlaylists();
    renderListening();
    const view = playlistOf(viewId);
    const recent = viewId === RECENT_VIEW;
    const following = viewId === FOLLOW_VIEW;
    const real = Boolean(view && !view.smart);
    for (const menu of ["music-add-menu", "music-more-menu"]) {
      const node = byId(menu);
      if (node) node.hidden = !real;
    }
    byId("music-find").hidden = recent || following;
    renderHero(view, recent, following);
    page.classList.toggle("music-following", following);
    if (following) {
      byId("music-follow").hidden = false;
      followRendered = "";
      renderFollow();
      return;
    }
    byId("music-follow").hidden = true;
    if (recent) return renderRecent();
    byId("music-list-name").textContent = view?.name || "No playlist";
    const rows = viewRows(view);
    const total = rows.all.reduce((sum, row) => sum + (row.track.duration || 0), 0);
    byId("music-list-meta").textContent = view
      ? `${rows.all.length} track${rows.all.length === 1 ? "" : "s"} · ${duration(total)}${view.smart ? " · made from your library" : ""}${library.tagging ? ` · reading tags (${library.tagging} left)` : ""}`
      : "";
    renderHead(Boolean(view));
    renderSelection(view);
    const list = byId("music-tracks");
    if (!view) {
      paint(list, `<div class="music-empty"><b>Your music stays where it is.</b><span>Make a playlist, then add music files or whole folders from anywhere on this PC, or import an M3U. Void Compass remembers where each file lives and plays it from there.</span></div>`);
      return;
    }
    if (!rows.all.length) {
      paint(list, view.smart
        ? `<div class="music-empty"><b>Nothing here yet.</b><span>${escapeHtml(SMART_HINT[view.id] || "")}</span></div>`
        : `<div class="music-empty"><b>An empty playlist.</b><span>Add music files or a whole folder with ＋ ADD above.</span></div>`);
      return;
    }
    // Drag to reorder works on the playlist's own order, all of it in view.
    const draggable = real && sortKey === "order" && !find.trim();
    paint(list, rows.shown.map((row) => rowMarkup(row, draggable)).join("")
      || `<div class="music-empty"><b>Nothing here matches “${escapeHtml(find)}”.</b></div>`);
  }

  const SMART_HINT = {
    "smart:added": "Music you add to any playlist shows here, newest first.",
    "smart:most": "The tracks you play most, once you've played a few.",
    "smart:never": "Everything you've played at least once. Nice.",
    "smart:long": "Tracks an hour or longer show here.",
  };

  function viewRows(view) {
    const all = (view?.tracks || []).map((id, position) => ({id, position, track: trackOf(id), plays: playsOf(id)}))
      .filter((row) => row.track);
    const needle = find.trim().toLowerCase();
    let shown = needle ? all.filter(({track}) =>
      `${track.title} ${track.artist} ${track.album} ${track.genre}`.toLowerCase().includes(needle)) : all;
    const value = SORT_VALUE[sortKey];
    if (value) {
      shown = [...shown].sort((a, b) => {
        const [x, y] = [value(a), value(b)];
        return (x < y ? -1 : x > y ? 1 : 0) * (sortDown ? -1 : 1) || a.position - b.position;
      });
    }
    return {all, shown};
  }

  function rowMarkup({id, position, track, plays}, draggable) {
    const last = stats.plays?.[id]?.[1];
    const spot = resume[id];
    const details = [track.artist || "Unknown artist", track.album, track.year].filter(Boolean).map(escapeHtml).join(" · ");
    const classes = [track.missing && "missing", id === currentId && viewId === playlistId && "current",
      selected.has(position) && "selected"].filter(Boolean).join(" ");
    const action = track.missing
      ? `<button type="button" data-locate title="Find where this file is now">LOCATE</button>`
      : spot ? `<button type="button" data-from-start title="Play it from the beginning">FROM START</button>` : "";
    return `<div class="music-row ${classes}" role="listitem" tabindex="0" draggable="${draggable}"
        data-track="${escapeHtml(id)}" data-position="${position}" title="Double-click to play">
        <span class="music-number">${position + 1}</span>
        <span class="music-eq" aria-hidden="true"><i></i><i></i><i></i></span>
        <span class="music-name">${artOf(id)}<span><b>${escapeHtml(track.title)}</b><small>${details}${track.missing ? " · FILE NOT FOUND" : ""}</small></span></span>
        <span class="music-played">${plays ? `${plays}×<small>${ago(last)}</small>` : "<small>never</small>"}</span>
        <span class="music-added">${addedLabel(track.added)}</span>
        <span class="music-time">${track.duration ? duration(track.duration) : "—"}${spot ? `<small title="Where you left off">AT ${duration(spot)}</small>` : ""}</span>
        <span class="music-row-extra">${action}</span>
      </div>`;
  }

  // The open list's header: its cover (or a mosaic of four), what it is, its name.
  function renderHero(view, recent, following) {
    const art = byId("music-hero-art");
    if (!art) return;
    const ids = (view?.tracks || []).filter((id) => trackOf(id)?.art);
    const pictures = ids.slice(0, ids.length >= 4 ? 4 : 1);
    paint(art, pictures.length ? pictures.map((id) => `<img src="${apiUrl(`/media/art/${id}.jpg`)}" alt="">`).join("")
      : `<i>${following ? "◈" : recent ? "↺" : "♪"}</i>`);
    art.classList.toggle("mosaic", pictures.length === 4);
    byId("music-hero-kicker").textContent = following ? "IN THE COCKPIT" : recent ? "YOUR LISTENING" : view?.smart ? "MADE FOR YOU" : view ? "PLAYLIST" : "MUSIC";
    if (following) {
      byId("music-list-name").textContent = "Follow the game";
      byId("music-list-meta").textContent = "A playlist for each scene, faded across as you fly";
    }
    const play = byId("music-list-play");
    if (play) play.hidden = following || recent || !(view?.tracks || []).some((id) => trackOf(id));
  }

  function renderHead(shown) {
    const head = byId("music-track-head");
    if (!head) return;
    const sort = (key, label) => {
      const on = sortKey === key;
      return `<button type="button" data-sort="${key}" class="${on ? "on" : ""}" aria-pressed="${on}">${label}${on && key !== "order" ? (sortDown ? " ↓" : " ↑") : ""}</button>`;
    };
    head.hidden = !shown;
    paint(head, `<span>${sort("order", "#")}</span><span></span><span>${sort("title", "TITLE")}<i>·</i>${sort("artist", "ARTIST")}</span>`
      + `<span>${sort("played", "PLAYED")}</span><span>${sort("added", "ADDED")}</span><span>${sort("time", "LENGTH")}</span><span></span>`);
  }

  function selectedIds(view) {
    return [...selected].sort((a, b) => a - b).map((position) => view?.tracks[position]).filter((id) => trackOf(id));
  }

  function renderSelection(view) {
    const bar = byId("music-selection");
    if (!bar) return;
    const count = view ? selectedIds(view).length : 0;
    bar.hidden = !count;
    if (!count) return paint(bar, "");
    const others = library.playlists.filter((item) => item.id !== view.id);
    const options = (label) => `<option value="">${label}</option>${others.map((item) =>
      `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("")}`;
    paint(bar, `<b>${count} SELECTED</b>
      <button type="button" data-sel="next">PLAY NEXT</button>
      <button type="button" data-sel="queue">ADD TO QUEUE</button>
      ${others.length ? `<select data-sel="copy" aria-label="Add to another playlist">${options("ADD TO PLAYLIST…")}</select>` : ""}
      ${!view.smart && others.length ? `<select data-sel="move" aria-label="Move to another playlist">${options("MOVE TO…")}</select>` : ""}
      ${!view.smart ? `<button type="button" data-sel="remove" class="danger-action">REMOVE</button>` : ""}
      <button type="button" data-sel="clear" class="music-sel-clear">CLEAR</button>`);
  }

  function markSelection() {
    page?.querySelectorAll("#music-tracks .music-row").forEach((row) => {
      row.classList.toggle("selected", selected.has(Number(row.dataset.position)));
    });
    renderSelection(playlistOf(viewId));
  }

  function renderPlaylists() {
    const lists = library.playlists;
    byId("music-playlist-count").textContent = String(lists.length);
    const cover = (ids) => {
      const art = ids.filter((id) => trackOf(id)?.art).slice(0, 4);
      if (art.length >= 4) return `<span class="music-list-art mosaic">${art.map((id) => `<img src="${apiUrl(`/media/art/${id}.jpg`)}" alt="" loading="lazy">`).join("")}</span>`;
      return `<span class="music-list-art">${art.length ? `<img src="${apiUrl(`/media/art/${art[0]}.jpg`)}" alt="" loading="lazy">` : "<i>♪</i>"}</span>`;
    };
    const entry = (item, extra = "") => {
      const ids = item.tracks.filter((id) => trackOf(id));
      const total = ids.reduce((sum, id) => sum + (trackOf(id).duration || 0), 0);
      return `<button type="button" class="${extra}${item.id === viewId ? " selected" : ""}${item.id === playlistId && currentId ? " live" : ""}" data-playlist="${escapeHtml(item.id)}">`
        + `${cover(ids)}<span class="music-list-text"><span>${escapeHtml(item.name)}</span><small>${ids.length} track${ids.length === 1 ? "" : "s"}${total ? ` · ${duration(total)}` : ""}</small></span></button>`;
    };
    paint(byId("music-playlists"), lists.length ? lists.map((item) => entry(item, "music-playlist")).join("")
      : `<p class="music-note">No playlists yet. Name one above, or import an M3U playlist from another player.</p>`);
    const smart = SMART.map(([id]) => playlistOf(id)).filter(Boolean);
    paint(byId("music-smart"), smart.map((item) => entry(item, "music-smart")).join("")
      + `<button type="button" class="music-smart music-recent${viewId === RECENT_VIEW ? " selected" : ""}" data-playlist="${RECENT_VIEW}">`
      + `<span class="music-list-art"><i>↺</i></span><span class="music-list-text"><span>Recently played</span><small>your last ${stats.recent?.length || 0} and where you were</small></span></button>`);
  }

  function renderListening() {
    const line = byId("music-listening");
    if (!line) return;
    const heard = stats.listening || {};
    const top = heard.top;
    paint(line, heard.all_s ? `<span>LISTENING</span><b>${hours(heard.week_s || 0)}</b> this week · <b>${hours(heard.all_s)}</b> in all`
      + (top?.title ? `<small>Most played: ${escapeHtml(top.title)} (${top.count}×)</small>` : "") : "");
  }

  function renderRecent() {
    byId("music-list-name").textContent = "Recently played";
    byId("music-list-meta").textContent = "Your last tracks, newest first, and the system you were in";
    renderSelection(null);
    const head = byId("music-track-head");
    head.hidden = false;
    paint(head, `<span></span><span></span><span>TRACK</span><span>WHEN</span><span class="music-where-head">WHERE</span><span></span><span></span>`);
    const rows = stats.recent || [];
    paint(byId("music-tracks"), rows.length ? rows.map((play) => {
      const track = trackOf(play.track_id);
      return `<div class="music-row music-recent-row${track ? "" : " missing"}" role="listitem" tabindex="0" data-track="${escapeHtml(play.track_id)}"
        title="${track ? "Double-click to play it now" : "No longer in your library"}">
        <span class="music-number"></span><span class="music-eq" aria-hidden="true"><i></i><i></i><i></i></span>
        <span class="music-name">${artOf(play.track_id)}<span><b>${escapeHtml(track?.title || play.title || "Track")}</b><small>${escapeHtml(track?.artist || play.artist || "")}</small></span></span>
        <span class="music-played"><small>${ago(play.at)}</small></span>
        <span class="music-where">${play.system ? escapeHtml(play.system) : "<small>—</small>"}</span>
        <span></span><span></span>
      </div>`;
    }).join("") : `<div class="music-empty"><b>Nothing played yet.</b><span>Each track you play is noted here, with the system you were in.</span></div>`);
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
    const now = performance.now();
    const dt = Math.min(50, now - (lastDraw || now));
    lastDraw = now;
    if (visualizer === "off") return;
    const style = getComputedStyle(document.documentElement);
    const token = (name, fallback) => style.getPropertyValue(name).trim() || fallback;
    const theme = {accent: token("--accent", "#00d1ff"), orange: token("--orange", "#ff7a18"),
      red: token("--red", "#ff6b70"), green: token("--green", "#54e39a"), text: token("--text", "#dce8ef")};
    const fill = ctx.createLinearGradient(0, height, 0, 0);
    fill.addColorStop(0, theme.accent);
    fill.addColorStop(1, theme.orange);
    ctx.fillStyle = fill;
    ctx.strokeStyle = fill;
    const draw = {bars: drawBars, peaks: drawBars, mirror: drawMirror, led: drawLed, wave: drawWave,
      horizon: drawHorizon, aurora: drawAurora, waterfall: drawWaterfall, shockwave: drawShockwave,
      scanner: drawScanner, witchspace: drawWitchspace}[visualizer];
    draw(ctx, width, height, {theme, now, dt, canvas});
    ctx.globalAlpha = 1;
    if (!audio.paused) frame = window.requestAnimationFrame(drawVisualizer);
  }

  function drawBars(ctx, width, height) {
    const gap = 4, bar = (width - gap * (BANDS - 1)) / BANDS;
    levels().forEach((level, band) => {
      const tall = Math.max(2, level / 255 * height);
      ctx.globalAlpha = .12 + level / 255 * .2;
      ctx.fillRect(band * (bar + gap), height - tall, bar, tall);
      if (visualizer !== "peaks") return;
      // A cap sits on each bar's highest point and drifts back down.
      caps[band] = Math.max(tall, caps[band] - height * .012);
      ctx.globalAlpha = .55;
      ctx.fillRect(band * (bar + gap), height - caps[band] - 3, bar, 2);
    });
  }

  function drawMirror(ctx, width, height) {
    const gap = 4, bar = (width - gap * (BANDS - 1)) / BANDS, middle = height / 2;
    levels().forEach((level, band) => {
      const half = Math.max(1, level / 255 * middle);
      ctx.globalAlpha = .12 + level / 255 * .22;
      ctx.fillRect(band * (bar + gap), middle - half, bar, half * 2);
    });
  }

  function drawWave(ctx, width, height) {
    const quiet = !analyser || audio.paused;
    if (!quiet) analyser.getByteTimeDomainData(samples);
    const count = quiet ? 2 : samples.length;
    ctx.globalAlpha = .55;
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.beginPath();
    for (let i = 0; i < count; i += 1) {
      const x = i / (count - 1) * width;
      const y = quiet ? height / 2 : samples[i] / 255 * height;
      if (i) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    }
    ctx.stroke();
  }

  function drawHorizon(ctx, width, height) {
    const points = levels().map((level, band) => [band / (BANDS - 1) * width, height - Math.max(2, level / 255 * height * .9)]);
    ctx.beginPath();
    ctx.moveTo(0, height);
    ctx.lineTo(...points[0]);
    // Through the midpoints, so the skyline is a curve rather than steps.
    for (let i = 1; i < points.length; i += 1) {
      const [x0, y0] = points[i - 1], [x1, y1] = points[i];
      ctx.quadraticCurveTo(x0, y0, (x0 + x1) / 2, (y0 + y1) / 2);
    }
    ctx.lineTo(...points[points.length - 1]);
    ctx.lineTo(width, height);
    ctx.closePath();
    ctx.globalAlpha = .16;
    ctx.fill();
    ctx.globalAlpha = .6;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  function drawLed(ctx, width, height, {theme}) {
    const rows = 8, gap = 3;
    const cell = (width - gap * (BANDS - 1)) / BANDS, tall = (height - gap * (rows + 1)) / rows;
    levels().forEach((level, band) => {
      const lit = Math.round(level / 255 * rows);
      for (let row = 0; row < rows; row += 1) {
        ctx.fillStyle = row >= rows - 2 ? theme.orange : theme.accent;
        ctx.globalAlpha = row < lit ? .5 : .06;
        ctx.fillRect(band * (cell + gap), height - gap - (row + 1) * tall - row * gap, cell, tall);
      }
    });
  }

  function drawAurora(ctx, width, height, {theme, now}) {
    const bands = levels();
    const mean = (from, to) => bands.slice(from, to).reduce((sum, level) => sum + level, 0) / (to - from) / 255;
    [[mean(0, 8), theme.green], [mean(8, 20), theme.accent], [mean(20, BANDS), theme.orange]].forEach(([level, colour], k) => {
      const swing = (.12 + level * .88) * height * .34;
      const thick = 4 + level * height * .3;
      const middle = height * (.42 + k * .08);
      const at = (x) => middle + Math.sin(x / width * Math.PI * (2.4 + k * 1.3) + now * .0005 * (1 + k * .45) + k * 2.1)
        * swing * (.65 + .35 * Math.sin(x / width * Math.PI * 3 + now * .0003));
      ctx.beginPath();
      for (let x = 0; x <= width; x += 8) ctx.lineTo(x, at(x));
      for (let x = Math.floor(width / 8) * 8; x >= 0; x -= 8) ctx.lineTo(x, at(x) + thick);
      ctx.closePath();
      ctx.fillStyle = colour;
      ctx.globalAlpha = .14 + level * .3;
      ctx.fill();
    });
  }

  function drawWaterfall(ctx, width, height, {theme, canvas}) {
    if (!trail || trail.width !== canvas.width || trail.height !== canvas.height) {
      trail = document.createElement("canvas");
      trail.width = canvas.width;
      trail.height = canvas.height;
    }
    const paper = trail.getContext("2d");
    const step = Math.max(1, Math.round(canvas.width / width * 3));
    // Slide what's there to the left; the newest moment comes in on the right.
    paper.globalCompositeOperation = "copy";
    paper.drawImage(trail, -step, 0);
    paper.globalCompositeOperation = "source-over";
    const row = trail.height / BANDS;
    levels().forEach((level, band) => {
      paper.globalAlpha = .04 + level / 255 * .86;
      paper.fillStyle = level > 190 ? theme.orange : theme.accent;
      paper.fillRect(trail.width - step, trail.height - (band + 1) * row, step, Math.ceil(row));
    });
    paper.globalAlpha = 1;
    ctx.globalAlpha = .8;
    ctx.drawImage(trail, 0, 0, width, height);
  }

  function drawShockwave(ctx, width, height, {theme, now}) {
    const bands = levels();
    const bass = bands.slice(0, 5).reduce((sum, level) => sum + level, 0) / 5 / 255;
    bassAverage += (bass - bassAverage) * .05;
    if (bass > .45 && bass > bassAverage * 1.15 && now - lastRing > 140 && rings.length < 30) {
      rings.push({x: width * (.12 + Math.random() * .76), born: now, power: bass});
      lastRing = now;
    }
    // A quiet skyline underneath, so the rings have somewhere to come from.
    ctx.globalAlpha = .1;
    ctx.beginPath();
    ctx.moveTo(0, height);
    bands.forEach((level, band) => ctx.lineTo(band / (BANDS - 1) * width, height - Math.max(2, level / 255 * height * .5)));
    ctx.lineTo(width, height);
    ctx.fill();
    ctx.strokeStyle = theme.accent;
    rings = rings.filter((ring) => {
      const age = (now - ring.born) / 1400;
      if (age >= 1) return false;
      ctx.globalAlpha = (1 - age) * .6 * ring.power;
      ctx.lineWidth = .5 + 2.5 * (1 - age);
      ctx.beginPath();
      ctx.arc(ring.x, height / 2, age * height * (1.2 + ring.power * 2.2), 0, Math.PI * 2);
      ctx.stroke();
      return true;
    });
  }

  // The ship's scanner: the disc, its range rings and the forward lines, with
  // each band a contact on a stalk. Above the plane is solid, below is hollow,
  // and the loudest show red, like a hostile.
  function drawScanner(ctx, width, height, {theme, now}) {
    // Spread across the whole bar, like the other looks, rather than a disc behind the controls.
    const cx = width / 2, cy = height * .6, ry = height * .32, rx = width * .46;
    ctx.strokeStyle = theme.orange;
    ctx.lineWidth = 1;
    for (const [size, alpha] of [[1, .4], [.66, .2], [.33, .2]]) {
      ctx.globalAlpha = alpha;
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx * size, ry * size, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.globalAlpha = .2;
    ctx.beginPath();
    for (const side of [-1, 1]) {
      const angle = -Math.PI / 2 + side * .55;
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(angle) * rx, cy + Math.sin(angle) * ry);
    }
    ctx.stroke();
    ctx.globalAlpha = .7;
    ctx.fillStyle = theme.orange;
    ctx.beginPath();
    ctx.moveTo(cx, cy - 4);
    ctx.lineTo(cx - 3.5, cy + 3);
    ctx.lineTo(cx + 3.5, cy + 3);
    ctx.closePath();
    ctx.fill();
    levels().forEach((value, band) => {
      const level = value / 255;
      if (level < .04) return;
      const angle = band * 2.39996 + now * .00004;
      const reach = .25 + .7 * ((band * .618034) % 1);
      const x = cx + Math.cos(angle) * rx * reach, y = cy + Math.sin(angle) * ry * reach;
      const above = band % 3 !== 0;
      const top = y - level * height * (above ? .55 : -.25);
      const colour = level > .78 ? theme.red : theme.orange;
      const size = 3 + level * 3;
      ctx.strokeStyle = colour;
      ctx.fillStyle = colour;
      ctx.globalAlpha = .3 + level * .6;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x, top);
      ctx.stroke();
      if (above) ctx.fillRect(x - size / 2, top - size / 2, size, size);
      else ctx.strokeRect(x - size / 2, top - size / 2, size, size);
      ctx.globalAlpha *= .5;
      ctx.beginPath();
      ctx.ellipse(x, y, 2, 1, 0, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  // Witchspace: streaks rushing out of the tunnel, the bass lighting the star ahead.
  function drawWitchspace(ctx, width, height, {theme, dt}) {
    const bands = levels();
    const loud = bands.reduce((sum, level) => sum + level, 0) / BANDS / 255;
    const bass = bands.slice(0, 4).reduce((sum, level) => sum + level, 0) / 4 / 255;
    const cx = width / 2, cy = height / 2;
    const star = (near = Math.random()) => ({angle: Math.random() * Math.PI * 2, depth: .01 + near * .9});
    if (!stars.length) stars = Array.from({length: 160}, () => star());
    const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, height * (.5 + bass * 1.4));
    glow.addColorStop(0, theme.text);
    glow.addColorStop(.25, theme.accent);
    glow.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.globalAlpha = .08 + bass * .3;
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, width, height);
    const speed = (.00006 + loud * .0009) * dt;
    ctx.lineCap = "round";
    for (const point of stars) {
      point.depth += speed * (.3 + point.depth * 3);
      if (point.depth > 1.15) {
        Object.assign(point, star(Math.random() * .06));
        continue;
      }
      const tail = point.depth * (1 - .06 - loud * .3);
      const x = (d) => cx + Math.cos(point.angle) * d * cx;
      const y = (d) => cy + Math.sin(point.angle) * d * cy * 1.6;
      ctx.strokeStyle = point.depth > .7 && loud > .5 ? theme.text : theme.accent;
      ctx.globalAlpha = Math.min(1, point.depth * 1.4) * (.3 + loud * .6);
      ctx.lineWidth = .6 + point.depth * 1.6;
      ctx.beginPath();
      ctx.moveTo(x(tail), y(tail));
      ctx.lineTo(x(point.depth), y(point.depth));
      ctx.stroke();
    }
  }

  function pickVisualizer(id) {
    visualizer = id;
    caps = new Array(BANDS).fill(0);
    trail = null;
    rings = [];
    stars = [];
    try {
      window.localStorage.setItem(VISUALIZER_KEY, visualizer);
    } catch (_error) { /* this visit only */ }
    renderVisualizerButton();
    if (!frame) frame = window.requestAnimationFrame(drawVisualizer);
  }

  function renderVisualizerButton() {
    const button = byId("music-viz");
    if (!button) return;
    const look = VISUALIZERS.find((item) => item.id === visualizer);
    button.querySelector("span").textContent = look.label;
    button.title = `Visualizer: ${look.detail.toLowerCase()}`;
    button.dataset.on = String(visualizer !== "off");
    const list = byId("music-viz-list");
    if (!list) return;
    let group = null;
    list.innerHTML = VISUALIZERS.map((item) => {
      const heading = item.group && item.group !== group ? `<h4>${item.group}</h4>` : "";
      group = item.group;
      return `${heading}<button type="button" role="menuitemradio" aria-checked="${item.id === visualizer}" data-viz="${item.id}"><b>${item.label}</b><small>${escapeHtml(item.detail)}</small></button>`;
    }).join("");
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

  byId("music-follow")?.addEventListener("click", (event) => {
    if (!event.target.closest("[data-follow-fold]")) return;
    followOpen = !(followOpen ?? follow.on);
    try {
      window.localStorage.setItem(FOLLOW_OPEN_KEY, followOpen ? "1" : "0");
    } catch (_error) { /* remembered for this visit only */ }
    followRendered = "";
    renderFollow();
  });
  byId("music-follow")?.addEventListener("change", (event) => {
    const field = event.target.closest("[data-follow]");
    if (!field) return;
    const value = field.type === "checkbox" ? field.checked : field.value;
    followRendered = "";
    music("follow_set", {key: field.dataset.follow, value});
  });
  page?.addEventListener("pointerdown", () => {
    if (context?.state === "suspended") context.resume().catch(() => {});
  });
  byId("music-play")?.addEventListener("click", () => {
    blocked = false;
    toggle();
  });
  byId("music-previous")?.addEventListener("click", () => skip(false));
  byId("music-next")?.addEventListener("click", () => skip(true));
  // The big play button: this list from the top (or shuffled), or pause it.
  byId("music-list-play")?.addEventListener("click", () => {
    if (viewId === playlistId && currentId) return toggle();
    const tracks = playable(viewId);
    if (!tracks.length) return undefined;
    const first = shuffle ? tracks[Math.floor(Math.random() * tracks.length)] : tracks[0];
    return playFromList(first, tracks.indexOf(first));
  });
  byId("music-shuffle")?.addEventListener("click", () => {
    shuffle = !shuffle;
    if (playlistId && currentId && !fromQueue) arrange(currentId);
    renderNow();
    report();
  });
  byId("music-repeat")?.addEventListener("click", () => {
    repeat = REPEAT_NEXT[repeat];
    renderNow();
    report();
  });
  byId("music-upnext")?.addEventListener("click", (event) => {
    const out = event.target.closest("[data-unqueue]");
    if (out) {
      queue.splice(Number(out.dataset.unqueue), 1);
    } else if (event.target.closest("[data-clear-queue]")) {
      queue = [];
    } else {
      return;
    }
    renderUpNext();
    report();
  });
  byId("music-upnext")?.addEventListener("dblclick", (event) => {
    const item = event.target.closest("[data-upnext]");
    if (!item || event.target.closest("button")) return;
    const at = queue.indexOf(item.dataset.upnext);
    if (at >= 0) queue.splice(at, 1);
    playNow(item.dataset.upnext);
  });
  byId("music-viz-list")?.addEventListener("click", (event) => {
    const choice = event.target.closest("[data-viz]");
    if (choice) pickVisualizer(choice.dataset.viz);
  });
  renderVisualizerButton();
  byId("music-level")?.addEventListener("click", () => {
    normalise = !normalise;
    settleLevel(true);
    renderNow();
    report();
  });
  byId("music-volume")?.addEventListener("input", (event) => {
    setVolume(Math.round(Number(event.target.value)));
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
    selected.clear();
    renderLibrary();
  });
  byId("music-import")?.addEventListener("click", async () => {
    const choose = nativePicker("choose_playlist_file");
    const path = choose ? await choose() : "";
    if (path) music("import_m3u", {path});
  });
  // The ＋ ADD and ⋯ menus close once used, or with a click elsewhere.
  const closeMenus = (except = null) => page?.querySelectorAll(".music-menu[open]").forEach((menu) => {
    if (menu !== except) menu.removeAttribute("open");
  });
  document.addEventListener("click", (event) => {
    if (!pageShown) return;
    const menu = event.target.closest?.(".music-menu");
    closeMenus(menu);
    if (menu && event.target.closest(".music-menu > div button")) menu.removeAttribute("open");
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
      selected.clear();
      anchor = -1;
      renderLibrary();
      return;
    }
    const sorter = event.target.closest("[data-sort]");
    if (sorter) {
      const key = sorter.dataset.sort;
      if (key === sortKey && key !== "order") sortDown = !sortDown;
      else {
        sortKey = key;
        // Numbers read best biggest first; words from A.
        sortDown = ["played", "added", "time"].includes(key);
      }
      renderLibrary();
      return;
    }
    const action = event.target.closest("[data-sel]");
    if (action && action.tagName === "BUTTON") return selectionAction(action.dataset.sel);
    const row = event.target.closest("#music-tracks .music-row");
    if (!row || row.classList.contains("music-recent-row")) return;
    const position = Number(row.dataset.position);
    if (event.target.closest("[data-locate]")) return locate(row.dataset.track);
    if (event.target.closest("[data-from-start]")) {
      noteResume(row.dataset.track, 0);
      return playFromList(row.dataset.track, position, 0);
    }
    // Click selects; Ctrl adds or takes one away; Shift takes the run between.
    const shown = [...page.querySelectorAll("#music-tracks .music-row")].map((node) => Number(node.dataset.position));
    if (event.shiftKey && anchor >= 0 && shown.includes(anchor)) {
      const [from, to] = [shown.indexOf(anchor), shown.indexOf(position)].sort((a, b) => a - b);
      if (!event.ctrlKey) selected.clear();
      shown.slice(from, to + 1).forEach((spot) => selected.add(spot));
    } else if (event.ctrlKey || event.metaKey) {
      if (selected.has(position)) selected.delete(position);
      else selected.add(position);
      anchor = position;
    } else {
      selected = new Set([position]);
      anchor = position;
    }
    markSelection();
  });
  page?.addEventListener("change", (event) => {
    const field = event.target.closest("select[data-sel]");
    if (field && field.value) selectionAction(field.dataset.sel, field.value);
  });
  page?.addEventListener("dblclick", (event) => {
    const row = event.target.closest("#music-tracks .music-row");
    if (!row || event.target.closest("button")) return;
    if (row.classList.contains("music-recent-row")) return playNow(row.dataset.track);
    playFromList(row.dataset.track, Number(row.dataset.position));
  });
  page?.addEventListener("keydown", (event) => {
    const row = event.target.closest?.("#music-tracks .music-row");
    if (!row || event.key !== "Enter") return;
    if (row.classList.contains("music-recent-row")) playNow(row.dataset.track);
    else playFromList(row.dataset.track, Number(row.dataset.position));
  });

  function selectionAction(kind, target = "") {
    const view = playlistOf(viewId);
    const ids = selectedIds(view);
    const positions = [...selected].sort((a, b) => a - b);
    if (kind === "clear" || !ids.length) {
      selected.clear();
      return markSelection();
    }
    if (kind === "next") queue.unshift(...ids);
    else if (kind === "queue") queue.push(...ids);
    else if (kind === "copy" && target) music("add_tracks", {playlist_id: target, track_ids: ids});
    else if (kind === "move" && target && !view.smart) {
      music("add_tracks", {playlist_id: target, track_ids: ids})
        .then(() => music("remove_tracks", {playlist_id: viewId, positions}));
    } else if (kind === "remove" && !view.smart) music("remove_tracks", {playlist_id: viewId, positions});
    if (kind === "next" || kind === "queue") {
      showToast(`${ids.length} track${ids.length === 1 ? "" : "s"} ${kind === "next" ? "play next" : "added to the queue"}.`);
      renderUpNext();
      report();
    }
    selected.clear();
    markSelection();
  }

  async function locate(id) {
    const choose = nativePicker("choose_music_files");
    const paths = choose ? await choose() : [];
    if (paths?.length) music("relink", {track_id: id, path: paths[0]});
  }

  // Drag rows to reorder (the selection moves together).
  const trackList = byId("music-tracks");
  const clearDrop = () => trackList?.querySelectorAll(".drop-before, .drop-after")
    .forEach((node) => node.classList.remove("drop-before", "drop-after"));
  trackList?.addEventListener("dragstart", (event) => {
    const row = event.target.closest(".music-row[draggable='true']");
    if (!row) return;
    const position = Number(row.dataset.position);
    if (!selected.has(position)) {
      selected = new Set([position]);
      anchor = position;
      markSelection();
    }
    dragging_rows = [...selected].sort((a, b) => a - b);
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", "music-rows");
    row.classList.add("dragging");
  });
  trackList?.addEventListener("dragover", (event) => {
    const row = event.target.closest(".music-row");
    if (!dragging_rows || !row) return;
    event.preventDefault();
    const box = row.getBoundingClientRect();
    const after = event.clientY > box.top + box.height / 2;
    clearDrop();
    row.classList.add(after ? "drop-after" : "drop-before");
  });
  trackList?.addEventListener("drop", (event) => {
    const row = event.target.closest(".music-row");
    if (!dragging_rows || !row) return;
    event.preventDefault();
    const to = Number(row.dataset.position) + (row.classList.contains("drop-after") ? 1 : 0);
    music("move_tracks", {playlist_id: viewId, positions: dragging_rows, to});
    selected.clear();
    clearDrop();
  });
  trackList?.addEventListener("dragend", () => {
    dragging_rows = null;
    clearDrop();
    trackList.querySelectorAll(".dragging").forEach((node) => node.classList.remove("dragging"));
  });

  // Keys while the Music page is open, outside text boxes: Space plays and
  // pauses, arrows seek (Shift skips), Delete removes the selection, Ctrl+F
  // finds, Ctrl+A selects all, Escape lets go.
  document.addEventListener("keydown", (event) => {
    if (!pageShown) return;
    const typing = event.target.closest?.("input:not([type='range']), textarea, select, [contenteditable]");
    if (event.ctrlKey && event.key.toLowerCase() === "f") {
      const box = byId("music-find");
      if (box && !box.hidden) {
        event.preventDefault();
        box.focus();
        box.select();
      }
      return;
    }
    if (typing) return;
    if (event.code === "Space" && !event.repeat && !event.target.closest?.("button, input")) {
      event.preventDefault();
      toggle();
    } else if ((event.key === "ArrowLeft" || event.key === "ArrowRight") && !event.target.closest?.("input")) {
      event.preventDefault();
      const forward = event.key === "ArrowRight";
      if (event.shiftKey) skip(forward);
      else if (Number.isFinite(audio.duration)) {
        audio.currentTime = Math.max(0, Math.min(audio.duration - 1, audio.currentTime + (forward ? 10 : -10)));
        report();
      }
    } else if (event.key === "Delete" && selected.size) {
      const view = playlistOf(viewId);
      if (view && !view.smart) selectionAction("remove");
    } else if (event.ctrlKey && event.key.toLowerCase() === "a" && viewId !== RECENT_VIEW) {
      event.preventDefault();
      page.querySelectorAll("#music-tracks .music-row").forEach((row) => selected.add(Number(row.dataset.position)));
      markSelection();
    } else if (event.key === "Escape") {
      closeMenus();
      if (selected.size) {
        selected.clear();
        markSelection();
      }
    }
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
      ({toggle, next: () => skip(true), previous: () => skip(false), pause, queue: () => playQueue(state.remote.tracks)})[state.remote.op]?.();
    }
    if (numbers.focus > seen.focus && state.focus.playlist_id) {
      viewId = state.focus.playlist_id;
      renderLibrary();
    }
    if (numbers.notice > seen.notice && state.notice.text) showToast(state.notice.text);
    seen = numbers;
    const working = byId("music-working");
    if (working) working.hidden = !state.working;
    const listening = state.stats;
    if (listening && (listening.revision !== stats.revision || listening.recent?.[0]?.system !== stats.recent?.[0]?.system)) {
      stats = listening;
      renderLibrary();
    }
    follow = state.follow || follow;
    scene = String(state.scene || "");
    jumping = Boolean(state.jumping);
    renderFollow();
    followGame();
  }

  // Until the saved settings arrive the player is already at a sane level,
  // never the element's full-scale default.
  applyVolume();

  window.voidcompassMusic = {
    state: () => ({currentId, playlistId, viewId, order: [...order], index, playing: !audio.paused, shuffle,
      repeat, volume, blocked, src: audio.getAttribute("src") || "", revision: library.revision,
      normalise, levelDb, gain: audio.volume, measured: measuredLoudness(), samples: meter.blocks.length,
      firstListen: meter.firstListen, scene, jumping, fadeMix, duckMix, switching,
      queue: [...queue], fromQueue, selected: [...selected].sort((a, b) => a - b), sortKey, resume: {...resume}}),
    audio,
  };

  return {update, showPage};
}
