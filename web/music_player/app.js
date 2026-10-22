(() => {
  "use strict";
  /*
   * Music player overlay. It shows the music and never plays it: the Music
   * page in the command deck is the player. The snapshot carries the track,
   * its tags and cover, what plays next, where it was when last reported and
   * the Overlay Studio options; the position runs on from that report.
   *
   * The visualizer reads live levels from the overlay server (/api/live)
   * about fifteen times a second while music plays, and eases toward each
   * reading every frame, so it moves smoothly in between.
   */
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlayId = params.get("overlay") || "music-player";
  const root = document.getElementById("player");
  const canvas = document.getElementById("visualizer");
  const nodes = Object.fromEntries(["cover", "backdrop", "state", "playlist", "scene", "shuffle", "repeat", "repeat-one",
    "title", "artist", "details", "elapsed", "total", "resume", "next"].map((id) => [id, document.getElementById(id)]));
  // Five skins since 5.5.17; the cockpit draws its bars as lit blocks.
  const SKINS = ["deck", "cockpit", "glass", "vinyl", "minimal"];
  const SKIN_TONES = {cockpit: "orange", vinyl: "yellow"};
  const SCENES = {docked: "DOCKED", space: "IN SPACE", deep: "DEEP SPACE", surface: "ON A SURFACE", combat: "COMBAT"};
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
  const BANDS = 32;
  const LIVE_MS = 66;

  let model = {};
  let options = {};
  let reduced = false;
  let trackId = "";
  let titleKey = "";
  let nextKey = "";
  const target = new Array(BANDS).fill(0);
  const shown = new Array(BANDS).fill(0);
  const peaks = new Array(BANDS).fill(0);
  let frame = 0;
  let livePoll = 0;
  let changedTimer = 0;
  let palette = {};
  let poller = null;

  const playing = () => model.state === "playing";
  const clock = (seconds) => {
    const whole = Math.max(0, Math.floor(Number(seconds) || 0));
    const hours = Math.floor(whole / 3600), minutes = Math.floor(whole % 3600 / 60), rest = whole % 60;
    return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`
      : `${minutes}:${String(rest).padStart(2, "0")}`;
  };
  const skinNow = () => SKINS.includes(options.skin) ? options.skin : "deck";

  // Where the track is now: the last report, run on while it plays.
  function position() {
    const total = Number(model.track?.duration) || 0;
    let at = Number(model.position) || 0;
    if (playing() && model.reported_at) at += Math.max(0, (Date.now() - model.reported_at) / 1000);
    return total ? Math.min(at, total) : at;
  }

  function renderProgress() {
    const total = Number(model.track?.duration) || 0;
    const at = position();
    nodes.elapsed.textContent = clock(at);
    nodes.total.textContent = clock(total);
    root.style.setProperty("--progress", total ? Math.min(1, at / total).toFixed(4) : "0");
  }

  // A title too long for its window scrolls to its end and back.
  function fitTitle() {
    const title = nodes.title;
    title.classList.remove("scrolling");
    const overflow = title.scrollWidth - title.parentElement.clientWidth;
    if (overflow > 4 && !reduced) {
      title.style.setProperty("--marquee-shift", `${-overflow}px`);
      title.style.setProperty("--marquee-time", `${Math.max(6, overflow / 22 + 4)}s`);
      title.classList.add("scrolling");
    }
  }

  function renderTrack(track) {
    nodes.title.textContent = track?.title || "Nothing playing";
    // The strip is one line: its artist rides in the title's window, so the
    // whole "title — artist" scrolls when it doesn't fit.
    if (options.layout === "strip" && track?.artist) {
      const by = document.createElement("span");
      by.className = "by";
      by.textContent = `  —  ${track.artist}`;
      nodes.title.append(by);
    }
    nodes.artist.textContent = track ? track.artist || "Unknown artist" : "Play something on the Music page";
    nodes.details.replaceChildren();
    if (!track || options.show_details === false) return;
    // A long mix says so, and while it waits, where it carries on from.
    const resume = Number(model.resume_at) || 0;
    if (model.long_mix) {
      const badge = document.createElement("b");
      badge.textContent = model.state !== "playing" && resume ? `CARRIES ON FROM ${clock(resume)}` : "LONG MIX";
      nodes.details.append(badge, document.createTextNode("  ·  "));
    }
    nodes.details.append([track.album, track.year, track.format].filter(Boolean).join("  ·  "));
    if (!nodes.details.lastChild.textContent && nodes.details.childNodes.length > 1) nodes.details.childNodes[1].remove();
  }

  function renderNext() {
    const list = options.show_next === false || options.layout === "strip" ? []
      : (model.upcoming || (model.next ? [model.next] : [])).slice(0, Number(options.next_count) || 1);
    const key = JSON.stringify(list);
    if (key === nextKey) return;
    nextKey = key;
    nodes.next.hidden = !list.length;
    nodes.next.replaceChildren(...list.map((item, place) => {
      const row = document.createElement("li");
      row.classList.toggle("queued", Boolean(item.queued));
      const tag = document.createElement("span");
      tag.textContent = item.queued ? "QUEUED" : place ? "THEN" : "NEXT";
      const name = document.createElement("b");
      name.textContent = item.title || "Untitled";
      if (item.artist) {
        const by = document.createElement("i");
        by.textContent = `  —  ${item.artist}`;
        name.append(by);
      }
      row.append(tag, name);
      return row;
    }));
  }

  function render(snapshot = {}) {
    const effects = snapshot.effects || {};
    palette = VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, effects);
    model = snapshot.music || {};
    options = model.options || {};
    reduced = motionPreference.matches || Boolean(effects.reduced_motion);
    const track = model.track || null;
    const state = ["playing", "paused", "blocked", "idle"].includes(model.state) ? model.state : "idle";
    root.classList.remove("playing", "paused", "blocked", "idle");
    root.classList.add(state);
    root.classList.toggle("strip", options.layout === "strip");
    const skin = skinNow();
    for (const name of SKINS) root.classList.toggle(`skin-${name}`, name === skin);
    root.classList.toggle("no-art", options.show_art === false);
    root.classList.toggle("visualizer-off", reduced || options.visualizer === "off");
    nodes.state.textContent = {playing: "NOW PLAYING", paused: "PAUSED", blocked: "WAITING", idle: "STANDBY"}[state];
    nodes.playlist.textContent = model.playlist ? String(model.playlist).toUpperCase() : "";
    nodes.scene.hidden = !SCENES[model.scene];
    nodes.scene.textContent = SCENES[model.scene] || "";
    // SVG has no .hidden property, only the attribute.
    nodes.shuffle.toggleAttribute("hidden", !model.shuffle);
    nodes.repeat.toggleAttribute("hidden", !["all", "one"].includes(model.repeat));
    nodes["repeat-one"].hidden = model.repeat !== "one";
    renderTrack(track);
    if (nodes.cover.dataset.src !== (model.art || "")) {
      nodes.cover.dataset.src = model.art || "";
      for (const image of [nodes.cover, nodes.backdrop]) {
        image.hidden = !model.art;
        if (model.art) image.src = model.art;
        else image.removeAttribute("src");
      }
    }
    renderNext();
    const total = Number(track?.duration) || 0;
    const resume = Number(model.resume_at) || 0;
    nodes.resume.hidden = !(model.long_mix && resume && total && state !== "playing");
    if (!nodes.resume.hidden) root.style.setProperty("--resume", Math.min(1, resume / total).toFixed(4));
    // A new track arrives.
    if (track?.id !== trackId) {
      const first = trackId === "";
      trackId = track?.id || "";
      if (!first && trackId && !reduced) {
        root.classList.remove("changed");
        void root.offsetWidth;
        root.classList.add("changed");
        window.clearTimeout(changedTimer);
        changedTimer = window.setTimeout(() => root.classList.remove("changed"), 800);
      }
    }
    const fitKey = JSON.stringify([track?.title, track?.artist, options.layout, skin, effects.text_scale]);
    if (fitKey !== titleKey) {
      titleKey = fitKey;
      // Measured now and again once laid out: an overlay hidden while the
      // music was paused gets no animation frames until it shows again.
      fitTitle();
      window.requestAnimationFrame(fitTitle);
    }
    root.setAttribute("aria-label", track ? `Now playing: ${track.title}${track.artist ? ` by ${track.artist}` : ""}` : "Music: nothing playing");
    renderProgress();
    live();
    run();
  }

  // --- The visualizer --------------------------------------------------------
  function live() {
    window.clearTimeout(livePoll);
    livePoll = 0;
    if (!playing() || root.classList.contains("visualizer-off")) {
      target.fill(0);
      return;
    }
    const ask = async () => {
      try {
        const response = await fetch(`/api/live?token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlayId)}`,
          {cache: "no-store"});
        const data = response.ok ? await response.json() : (await response.arrayBuffer(), {});
        const bands = Array.isArray(data.bands) ? data.bands : [];
        for (let band = 0; band < BANDS; band += 1) target[band] = data.playing ? (Number(bands[band]) || 0) / 255 : 0;
      } catch (_error) {
        target.fill(0);
      }
      if (playing() && !root.classList.contains("visualizer-off")) livePoll = window.setTimeout(ask, LIVE_MS);
    };
    ask();
  }

  // A theme colour: the snapshot's, or the page's own before one arrives.
  const tone = (name) => palette[name] || getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();

  function paint(ctx, height, band) {
    const scheme = options.colour || "theme";
    if (scheme === "spectrum") return `hsl(${190 + band / BANDS * 170}, 95%, 62%)`;
    if (skinNow() === "glass" && scheme === "theme") return "rgba(255, 255, 255, .85)";
    const gradient = ctx.createLinearGradient(0, height, 0, 0);
    const lead = tone(SKIN_TONES[skinNow()] || "accent");
    const stops = scheme === "warm" ? [tone("red"), tone("orange"), tone("yellow")] : [lead, lead, tone("orange")];
    stops.forEach((stop, place) => gradient.addColorStop(place / (stops.length - 1), stop));
    return gradient;
  }

  function draw() {
    const width = canvas.clientWidth, height = canvas.clientHeight;
    if (!width || !height) return;
    const ratio = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const strip = options.layout === "strip";
    const style = options.visualizer || "bars";
    const count = strip ? BANDS / 2 : BANDS;
    const values = strip ? Array.from({length: count}, (_, band) => Math.max(shown[band * 2], shown[band * 2 + 1])) : shown;
    const spectrum = options.colour === "spectrum";
    const shared = spectrum ? null : paint(ctx, height, 0);
    if (style === "wave") return drawWave(ctx, width, height, values, shared || paint(ctx, height, count / 2));
    if (style === "bars" && skinNow() === "cockpit" && !strip) return drawBlocks(ctx, width, height, values, shared);
    const gap = strip || skinNow() === "vinyl" ? 2 : 3;
    const bar = (width - gap * (count - 1)) / count;
    const mirror = style === "mirror";
    const round = skinNow() === "glass";
    values.forEach((value, band) => {
      const x = band * (bar + gap);
      const tall = Math.max(1.5, value * (mirror ? height / 2 : height));
      ctx.fillStyle = shared || paint(ctx, height, band * (BANDS / count));
      ctx.globalAlpha = .35 + value * .5;
      const top = mirror ? height / 2 - tall : height - tall;
      fillBar(ctx, x, top, bar, mirror ? tall * 2 : tall, round);
      if (!mirror) {
        // A cap that falls slowly after each peak.
        const peak = strip ? Math.max(peaks[band * 2], peaks[band * 2 + 1]) : peaks[band];
        ctx.globalAlpha = .75;
        ctx.fillRect(x, height - Math.max(2, peak * height) - 2, bar, 1.5);
      }
    });
    ctx.globalAlpha = 1;
  }

  function fillBar(ctx, x, y, w, h, round) {
    if (!round || typeof ctx.roundRect !== "function") return ctx.fillRect(x, y, w, h);
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, Math.min(w / 2, 3));
    ctx.fill();
  }

  function drawWave(ctx, width, height, values, colour) {
    const count = values.length;
    const points = values.map((value, band) => [band / (count - 1) * width, height - Math.max(1, value * height * .92)]);
    ctx.beginPath();
    ctx.moveTo(0, height);
    points.forEach(([x, y], band) => {
      if (!band) ctx.lineTo(x, y);
      else {
        const [px, py] = points[band - 1];
        ctx.quadraticCurveTo(px, py, (px + x) / 2, (py + y) / 2);
      }
    });
    ctx.lineTo(width, points[count - 1][1]);
    ctx.lineTo(width, height);
    ctx.closePath();
    ctx.globalAlpha = .22;
    ctx.fillStyle = colour;
    ctx.fill();
    ctx.globalAlpha = .85;
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = colour;
    ctx.stroke();
    ctx.globalAlpha = 1;
  }

  // The cockpit's meters: stacked blocks lit from the bottom, the top two orange-red.
  function drawBlocks(ctx, width, height, values, shared) {
    const count = values.length, gap = 3, rows = Math.max(3, Math.round(height / 5));
    const cell = (width - gap * (count - 1)) / count, cellH = height / rows;
    values.forEach((value, band) => {
      const lit = Math.round(value * rows);
      for (let row = 0; row < rows; row += 1) {
        ctx.fillStyle = row >= rows - 1 ? tone("red") : shared || paint(ctx, height, band);
        ctx.globalAlpha = row < lit ? .45 + .45 * (row / rows) : .07;
        ctx.fillRect(band * (cell + gap), height - (row + 1) * cellH + 1, cell, cellH - 2);
      }
    });
    ctx.globalAlpha = 1;
  }

  function step() {
    frame = 0;
    let moving = false;
    for (let band = 0; band < BANDS; band += 1) {
      // Rise quickly, fall gently: bars read as music, not noise.
      const want = target[band];
      shown[band] += (want - shown[band]) * (want > shown[band] ? .55 : .16);
      peaks[band] = Math.max(shown[band], peaks[band] - .012);
      if (shown[band] > .004 || peaks[band] > .004) moving = true;
    }
    renderProgress();
    if (!root.classList.contains("visualizer-off")) draw();
    if (playing() || moving) frame = window.requestAnimationFrame(step);
  }

  function run() {
    if (!frame) frame = window.requestAnimationFrame(step);
  }

  new ResizeObserver(() => {
    fitTitle();
    run();
  }).observe(root);
  motionPreference.addEventListener("change", () => poller?.rerender());
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) fitTitle();
  });
  window.addEventListener("pagehide", () => {
    window.clearTimeout(livePoll);
    window.cancelAnimationFrame(frame);
  });
  window.musicPlayerOverlay = {
    state: () => ({state: model.state || "idle", track: model.track?.title || "", layout: options.layout || "card",
      skin: skinNow(), visualizer: root.classList.contains("visualizer-off") ? "off" : (options.visualizer || "bars"),
      polling: Boolean(livePoll), level: shown.reduce((sum, value) => sum + value, 0) / BANDS,
      elapsed: nodes.elapsed.textContent, scene: nodes.scene.hidden ? "" : nodes.scene.textContent,
      next: [...nodes.next.querySelectorAll("li b")].map((item) => item.textContent),
      details: nodes.details.textContent, scrolling: nodes.title.classList.contains("scrolling")}),
  };
  poller = VoidCompassOverlay.startPolling({
    token, overlay: overlayId, render,
    contentHeight: () => root.getBoundingClientRect().height || 156, interval: 250,
  });
})();
