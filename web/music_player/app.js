(() => {
  "use strict";
  /*
   * Music player overlay. It shows the music and never plays it: the Music
   * page in the command deck is the player. The snapshot carries the track,
   * its tags and cover, where it was when last reported and the Overlay
   * Studio options; the position runs on from that report between reports.
   *
   * The visualizer reads live levels from the overlay server (/api/live)
   * about fifteen times a second while music plays, and eases its bars
   * toward each reading every frame, so it moves smoothly in between.
   */
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlayId = params.get("overlay") || "music-player";
  const root = document.getElementById("player");
  const canvas = document.getElementById("visualizer");
  const nodes = Object.fromEntries(["cover", "state", "playlist", "modes", "title", "artist", "details",
    "elapsed", "total", "fill", "head", "next", "next-title"].map((id) => [id, document.getElementById(id)]));
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
  const BANDS = 32;
  const LIVE_MS = 66;

  let model = {};
  let options = {};
  let reduced = false;
  let trackId = "";
  let titleKey = "";
  let target = new Array(BANDS).fill(0);
  let shown = new Array(BANDS).fill(0);
  let peaks = new Array(BANDS).fill(0);
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
    const share = total ? `${Math.min(100, at / total * 100)}%` : "0%";
    nodes.fill.style.width = share;
    nodes.head.style.left = share;
  }

  // A title too long for its window scrolls to its end and back.
  function fitTitle() {
    const title = nodes.title;
    title.classList.remove("scrolling");
    const room = title.parentElement.clientWidth;
    const overflow = title.scrollWidth - room;
    if (overflow > 4 && !reduced) {
      title.style.setProperty("--marquee-shift", `${-overflow}px`);
      title.style.setProperty("--marquee-time", `${Math.max(6, overflow / 22 + 4)}s`);
      title.classList.add("scrolling");
    }
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
    root.classList.toggle("no-art", options.show_art === false);
    const visualizer = reduced ? "off" : (options.visualizer || "bars");
    root.classList.toggle("visualizer-off", visualizer === "off");
    nodes.state.textContent = {playing: "NOW PLAYING", paused: "PAUSED", blocked: "WAITING", idle: "STANDBY"}[state];
    nodes.playlist.textContent = model.playlist ? String(model.playlist).toUpperCase() : "";
    nodes.modes.textContent = [model.shuffle ? "SHUFFLE" : "", {one: "REPEAT ONE", off: "", all: "REPEAT"}[model.repeat] || ""]
      .filter(Boolean).join(" · ");
    const nextKey = JSON.stringify([track?.title, track?.artist, track?.album, options.layout, effects.text_scale]);
    // The strip is one line: its artist rides in the title's window, so the
    // whole "title — artist" scrolls when it doesn't fit, rather than the
    // artist being cut off beside a scrolling title.
    const artist = track ? track.artist || "Unknown artist" : "Play something on the Music page";
    nodes.title.textContent = track?.title || "Nothing playing";
    if (options.layout === "strip" && track?.artist) {
      const by = document.createElement("span");
      by.className = "by";
      by.textContent = `  —  ${track.artist}`;
      nodes.title.append(by);
    }
    nodes.artist.textContent = artist;
    nodes.details.textContent = track && options.show_details !== false
      ? [track.album, track.year, track.format].filter(Boolean).join("  ·  ") : "";
    if (nodes.cover.dataset.src !== (model.art || "")) {
      nodes.cover.dataset.src = model.art || "";
      nodes.cover.hidden = !model.art;
      if (model.art) nodes.cover.src = model.art;
      else nodes.cover.removeAttribute("src");
    }
    const following = options.show_next !== false && options.layout !== "strip" ? model.next : null;
    nodes.next.hidden = !following;
    nodes["next-title"].textContent = following
      ? [following.title, following.artist].filter(Boolean).join("  —  ") : "";
    // A new track slides in.
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
    if (nextKey !== titleKey) {
      titleKey = nextKey;
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
        const data = response.ok ? await response.json() : {};
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

  function colourAt(band, ctx, height) {
    const scheme = options.colour || "theme";
    if (scheme === "spectrum") return `hsl(${190 + band / BANDS * 170}, 95%, 62%)`;
    const gradient = ctx.createLinearGradient(0, height, 0, 0);
    // Theme tokens as applyTheme resolved them (the page's own when unset).
    const stops = scheme === "warm" ? [tone("red"), tone("orange"), tone("yellow")]
      : [tone("accent"), tone("accent"), tone("orange")];
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
    const shared = options.colour === "spectrum" ? null : colourAt(0, ctx, height);
    ctx.globalCompositeOperation = "lighter";
    if (style === "wave") {
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
      ctx.globalAlpha = .16;
      ctx.fillStyle = shared || colourAt(count / 2, ctx, height);
      ctx.fill();
      ctx.globalAlpha = .7;
      ctx.lineWidth = 1.4;
      ctx.strokeStyle = shared || colourAt(count / 2, ctx, height);
      ctx.shadowColor = tone("accent");
      ctx.shadowBlur = 8;
      ctx.stroke();
      ctx.shadowBlur = 0;
      return;
    }
    const gap = strip ? 2 : 3, bar = (width - gap * (count - 1)) / count;
    const mirror = style === "mirror";
    values.forEach((value, band) => {
      const x = band * (bar + gap);
      const tall = Math.max(1, value * (mirror ? height / 2 : height) * .95);
      ctx.fillStyle = shared || colourAt(band * (BANDS / count), ctx, height);
      // Behind the progress and up-next lines: bright enough to dance,
      // never so bright it drowns the text.
      ctx.globalAlpha = .16 + value * .34;
      if (mirror) {
        ctx.fillRect(x, height / 2 - tall, bar, tall);
        ctx.globalAlpha *= .55;
        ctx.fillRect(x, height / 2, bar, tall * .8);
      } else {
        ctx.fillRect(x, height - tall, bar, tall);
        // A cap that falls slowly after each peak.
        const peak = strip ? Math.max(peaks[band * 2], peaks[band * 2 + 1]) : peaks[band];
        ctx.globalAlpha = .5;
        ctx.fillRect(x, height - Math.max(2, peak * height * .95) - 2, bar, 1.5);
      }
    });
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
      visualizer: root.classList.contains("visualizer-off") ? "off" : (options.visualizer || "bars"),
      polling: Boolean(livePoll), level: shown.reduce((sum, value) => sum + value, 0) / BANDS,
      elapsed: nodes.elapsed.textContent, next: nodes.next.hidden ? "" : nodes["next-title"].textContent,
      scrolling: nodes.title.classList.contains("scrolling")}),
  };
  poller = VoidCompassOverlay.startPolling({
    token, overlay: overlayId, render,
    contentHeight: () => root.getBoundingClientRect().height || 136, interval: 250,
  });
})();
