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
    "title", "artist", "details", "elapsed", "total", "resume", "next", "neon-live", "neon-look", "neon-format"]
    .map((id) => [id, document.getElementById(id)]));
  // Five skins since 5.5.17, Neon again in 5.6.2 and Orb in 5.6.3; the cockpit
  // draws its bars as lit blocks, the orb as rays round its ring.
  const SKINS = ["deck", "cockpit", "glass", "vinyl", "minimal", "neon", "orb"];
  // The looks are shared with the Music page (5.6.2); this page keeps its own
  // skin-tuned bars, mirror and wave, and draws the rest with the shared painter.
  const SHARED = window.VoidCompassVisualizers || null;
  const OWN_LOOKS = ["bars", "mirror", "wave"];
  const painter = SHARED ? SHARED.painter() : null;
  const NEON_VARS = ["low", "mid", "high", "peak", "panel", "line", "ink", "dim"];
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
  let wave = [];
  let lastDraw = 0;
  let lookNow = "";

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

  // Neon's colours (a palette, or the theme's) and its labels.
  function renderNeon(state, track) {
    const colours = SHARED?.PALETTES?.[options.palette];
    for (const name of NEON_VARS) {
      if (colours?.[name]) root.style.setProperty(`--neon-${name}`, colours[name]);
      else root.style.removeProperty(`--neon-${name}`);
    }
    nodes["neon-live"].textContent = {playing: "LIVE", paused: "PAUSED", blocked: "WAITING", idle: "STANDBY"}[state];
    const look = SHARED?.LOOKS?.find((item) => item.id === (options.visualizer || "bars"));
    nodes["neon-look"].textContent = look ? look.label : String(options.visualizer || "").toUpperCase();
    nodes["neon-format"].textContent = [track?.format, track?.year].filter(Boolean).join(" · ").toUpperCase();
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
    renderNeon(state, track);
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
        wave = data.playing && Array.isArray(data.wave) ? data.wave.map((value) => Number(value) || 128) : [];
      } catch (_error) {
        target.fill(0);
        wave = [];
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

  // The shared looks' colours: the Neon skin's palette, else the skin's own
  // tone in the chosen scheme (theme, warm or spectrum).
  function lookColours() {
    const base = {accent: tone("accent"), orange: tone("orange"), red: tone("red"), green: tone("green"), text: tone("text"), yellow: tone("yellow")};
    if (skinNow() === "neon") return SHARED.colours(options.palette, base);
    if (options.colour === "warm") return {...base, accent: tone("red"), green: tone("orange"), orange: tone("yellow")};
    if (options.colour === "spectrum") return {...base, accent: "hsl(190, 95%, 62%)", green: "hsl(275, 95%, 62%)", orange: "hsl(355, 95%, 62%)"};
    return {...base, accent: tone(SKIN_TONES[skinNow()] || "accent")};
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
    if (skinNow() === "orb" && !strip) return drawOrb(ctx, height, style);
    const now = performance.now();
    const dt = Math.min(50, now - (lastDraw || now));
    lastDraw = now;
    if (painter && (skinNow() === "neon" || !OWN_LOOKS.includes(style))) {
      if (style !== lookNow) {
        lookNow = style;
        painter.reset();
      }
      painter.draw(style, ctx, width, height, {bands: shown.map((value) => value * 255), wave: wave.length ? wave : null,
        playing: playing(), theme: lookColours(), now, dt, canvas, bold: 2.6});
      return;
    }
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

  // The orb skin (5.5.3.3): every look drawn round the ring of the cover; the
  // classic bars are rays standing out from it.
  // Note: plain colours only. A CSS colour function in a canvas gradient
  // throws in the app's WebView2 and stops the drawing altogether.
  const orb = {look: "", last: 0, avg: 0, beat: 0, ping: 0, sweep: 0, phase: 0, vu: [0, 0], hist: [], rings: [], streaks: [], dots: []};
  const TAU = Math.PI * 2;

  function drawOrb(ctx, height, style) {
    const cover = root.querySelector(".cover").getBoundingClientRect();
    const box = canvas.getBoundingClientRect();
    const cx = cover.left + cover.width / 2 - box.left, cy = cover.top + cover.height / 2 - box.top;
    const scale = Number(getComputedStyle(root).getPropertyValue("--scale")) || 1;
    const inner = cover.width / 2 + 8 * scale;
    // Kept inside the skin's rounded edge, which hugs the ring.
    const reach = Math.min(cx, cy, height - cy) - inner - 7 * scale;
    if (reach <= 2) return;
    const now = performance.now();
    const dt = Math.min(50, now - (orb.last || now)) / 1000;
    orb.last = now;
    if (orb.look !== style) Object.assign(orb, {look: style, hist: [], rings: [], streaks: [], dots: [], vu: [0, 0]});

    const live = playing();
    const energy = shown.reduce((sum, value) => sum + value, 0) / BANDS;
    const bass = (shown[0] + shown[1] + shown[2] + shown[3]) / 4;
    const beat = live && bass > .2 && bass > orb.avg * 1.2 && now - orb.beat > 240;
    orb.avg += (bass - orb.avg) * Math.min(1, dt * 4);
    if (beat) orb.beat = now;

    const spectrum = options.colour === "spectrum";
    const lead = paint(ctx, height, 0);
    const colour = (band) => spectrum ? paint(ctx, height, band) : lead;
    const tones = lookColours();
    const thin = Math.max(1.5, cover.width / 50);
    const at = (angle, r) => [cx + Math.cos(angle) * r, cy + Math.sin(angle) * r];
    // Bass at the top, the treble meeting at the bottom, the same on both sides.
    const side = (band, s) => -Math.PI / 2 + s * (band + .5) / BANDS * Math.PI;
    const bandAt = (i, count) => Math.min(BANDS - 1, Math.floor((i <= count / 2 ? i : count - i) / (count / 2) * BANDS));
    const ray = (angle, from, to) => {
      ctx.beginPath();
      ctx.moveTo(...at(angle, from));
      ctx.lineTo(...at(angle, to));
      ctx.stroke();
    };
    const dot = (point, r) => {
      ctx.beginPath();
      ctx.arc(point[0], point[1], Math.max(.5, r), 0, TAU);
      ctx.fill();
    };
    const circle = (r) => {
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, TAU);
      ctx.stroke();
    };
    // A closed curve round the ring, its radius set band by band.
    const loop = (radius, count = 64) => {
      const points = Array.from({length: count}, (_, i) => at(-Math.PI / 2 + i / count * TAU, radius(shown[bandAt(i, count)], i / count * TAU)));
      ctx.beginPath();
      points.forEach((point, i) => {
        const next = points[(i + 1) % count];
        const mid = [(point[0] + next[0]) / 2, (point[1] + next[1]) / 2];
        if (!i) ctx.moveTo(...mid);
        else ctx.quadraticCurveTo(point[0], point[1], mid[0], mid[1]);
      });
      ctx.quadraticCurveTo(points[0][0], points[0][1], ...[(points[0][0] + points[1][0]) / 2, (points[0][1] + points[1][1]) / 2]);
      ctx.closePath();
    };

    // Only the band between the cover and the edge: nothing over the art, nothing spilling out.
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, inner + reach + 2 * scale, 0, TAU);
    ctx.arc(cx, cy, inner - 1, 0, TAU, true);
    ctx.clip("evenodd");
    ctx.lineCap = "round";
    ctx.lineWidth = thin;
    ctx.strokeStyle = lead;
    ctx.fillStyle = lead;

    switch (style) {
      case "mirror":
        // Four ways round: bass at the sides, treble top and bottom.
        for (let band = 0; band < BANDS / 2; band += 1) {
          const value = Math.max(shown[band * 2], shown[band * 2 + 1]);
          ctx.strokeStyle = colour(band * 2);
          ctx.globalAlpha = .25 + value * .6;
          for (const base of [0, Math.PI]) for (const s of [1, -1]) ray(base + s * (band + .5) / (BANDS / 2) * Math.PI / 2, inner, inner + Math.max(1, value * reach));
        }
        break;
      case "led": {
        const step = thin * 2.2, count = Math.max(3, Math.floor(reach / step));
        ctx.lineCap = "butt";
        ctx.lineWidth = thin * 1.5;
        shown.forEach((value, band) => {
          const lit = Math.round(value * count);
          for (let k = 0; k < lit; k += 1) {
            ctx.strokeStyle = k >= count * .8 ? tones.red : k >= count * .55 ? tones.orange : colour(band);
            ctx.globalAlpha = .55 + k / count * .4;
            for (const s of [1, -1]) ray(side(band, s), inner + k * step, inner + k * step + step * .55);
          }
        });
        break;
      }
      case "wave":
        loop((value) => inner + 1 + value * reach * .92);
        ctx.globalAlpha = .16;
        ctx.fill();
        ctx.globalAlpha = .9;
        ctx.stroke();
        break;
      case "horizon":
        ctx.shadowColor = tones.accent;
        ctx.shadowBlur = thin * 5;
        ctx.fillStyle = tones.accent;
        loop((value) => inner + value * reach * .85);
        ctx.globalAlpha = .38;
        ctx.fill();
        ctx.strokeStyle = tones.text;
        ctx.lineWidth = thin * .7;
        ctx.globalAlpha = .7;
        ctx.stroke();
        break;
      case "aurora":
        ctx.globalCompositeOperation = "lighter";
        [tones.accent, tones.green, tones.orange].forEach((tint, layer) => {
          ctx.fillStyle = tint;
          loop((value, angle) => inner + value * reach * (.45 + layer * .2) + Math.sin(angle * (3 + layer) + now / (900 - layer * 180)) * reach * .08 * (.4 + energy), 48);
          ctx.globalAlpha = .2;
          ctx.fill();
        });
        break;
      case "waterfall": {
        // The last few moments as rings, the newest at the cover.
        const step = thin * 1.6, rows = Math.max(3, Math.floor(reach / step));
        if (!orb.hist.length || now - orb.hist[0].at > 70) orb.hist.unshift({at: now, values: shown.slice()});
        orb.hist.length = Math.min(orb.hist.length, rows);
        ctx.lineCap = "butt";
        ctx.lineWidth = step * .8;
        orb.hist.forEach(({values}, row) => {
          values.forEach((value, band) => {
            if (value < .05) return;
            ctx.strokeStyle = value > .7 ? tones.orange : value > .4 ? tones.accent : tones.green;
            ctx.globalAlpha = value * (1 - row / rows);
            for (const s of [1, -1]) {
              const angle = side(band, s);
              ctx.beginPath();
              ctx.arc(cx, cy, inner + row * step + step / 2, angle - Math.PI / BANDS * .42, angle + Math.PI / BANDS * .42);
              ctx.stroke();
            }
          });
        });
        break;
      }
      case "shockwave":
        if (beat) orb.rings.push({r: inner, life: 1, width: thin * (1.5 + bass * 3)});
        shown.forEach((value, band) => {
          ctx.strokeStyle = colour(band);
          ctx.globalAlpha = .12 + value * .25;
          for (const s of [1, -1]) ray(side(band, s), inner, inner + value * reach * .5);
        });
        ctx.strokeStyle = tones.orange;
        orb.rings = orb.rings.filter((ring) => {
          ring.r += dt * reach * 1.7;
          ring.life -= dt * 1.5;
          if (ring.life <= 0 || ring.r > inner + reach) return false;
          ctx.globalAlpha = ring.life;
          ctx.lineWidth = ring.width * ring.life;
          circle(ring.r);
          return true;
        });
        break;
      case "scanner": {
        orb.sweep = (orb.sweep + dt * (live ? 2.4 : .6)) % TAU;
        ctx.strokeStyle = tones.green;
        ctx.lineWidth = thin * .5;
        ctx.globalAlpha = .18;
        circle(inner + reach * .5);
        circle(inner + reach - 1);
        for (let i = 0; i < 18; i += 1) {
          ctx.globalAlpha = (1 - i / 18) * (i ? .22 : .9);
          ctx.lineWidth = i ? thin * 1.4 : thin * .8;
          ray(orb.sweep - i * .06, inner, inner + reach);
        }
        ctx.fillStyle = tones.green;
        shown.forEach((value, band) => {
          for (const s of [1, -1]) {
            const angle = side(band, s);
            const behind = ((orb.sweep - angle) % TAU + TAU) % TAU;
            if (behind > 2.2 || value < .08) continue;
            ctx.globalAlpha = value * (1 - behind / 2.2);
            dot(at(angle, inner + value * reach * .92), thin * (.6 + value));
          }
        });
        break;
      }
      case "witchspace":
        if (live) {
          for (let n = Math.floor(energy * 5 + Math.random() * 1.5); n > 0; n -= 1) {
            orb.streaks.push({angle: Math.random() * TAU, r: inner, speed: reach * (1.2 + energy * 4 + Math.random() * 1.5), tint: Math.random() < .3 ? tones.text : tones.accent});
          }
        }
        orb.streaks = orb.streaks.filter((streak) => {
          streak.r += streak.speed * dt;
          const gone = (streak.r - inner) / reach;
          if (gone >= 1) return false;
          ctx.strokeStyle = streak.tint;
          ctx.globalAlpha = 1 - gone;
          ctx.lineWidth = thin * (.4 + gone * .8);
          ray(streak.angle, Math.max(inner, streak.r - streak.speed * .07), streak.r);
          return true;
        });
        ctx.strokeStyle = tones.accent;
        ctx.globalAlpha = .25 + bass * .5;
        ctx.lineWidth = thin * .8;
        circle(inner + 1);
        break;
      case "vu": {
        // Two arc meters: the low half of the music up the left, the high up the right.
        const levels = [shown.slice(0, BANDS / 2), shown.slice(BANDS / 2)].map((half) => Math.min(1, Math.max(...half) * 1.05));
        orb.vu = orb.vu.map((held, i) => levels[i] > held ? levels[i] : Math.max(levels[i], held - dt * .9));
        const ticks = 16, r = inner + reach * .45;
        ctx.lineCap = "butt";
        ctx.lineWidth = reach * .55;
        [-1, 1].forEach((s, meter) => {
          for (let k = 0; k < ticks; k += 1) {
            const from = Math.PI / 2 - s * (k / ticks) * Math.PI, to = Math.PI / 2 - s * ((k + .72) / ticks) * Math.PI;
            const lit = k < Math.round(orb.vu[meter] * ticks);
            ctx.strokeStyle = k >= ticks * .8 ? tones.red : k >= ticks * .6 ? tones.orange : tones.green;
            ctx.globalAlpha = lit ? .9 : .1;
            ctx.beginPath();
            ctx.arc(cx, cy, r, Math.min(from, to), Math.max(from, to));
            ctx.stroke();
          }
        });
        break;
      }
      case "radial": {
        const spin = now / 5000;
        ctx.lineWidth = thin * .6;
        for (let i = 0; i < 96; i += 1) {
          const band = bandAt(i, 96), value = shown[band];
          ctx.strokeStyle = colour(band);
          ctx.globalAlpha = .3 + value * .7;
          ray(-Math.PI / 2 + i / 96 * TAU + spin, inner + value * reach * .18, inner + Math.max(1, value * reach));
        }
        ctx.globalAlpha = .35;
        circle(inner);
        break;
      }
      case "particles":
        if (!orb.dots.length) orb.dots = Array.from({length: 48}, (_, i) => ({band: i % BANDS, angle: i / 48 * TAU, wobble: Math.random() * TAU}));
        orb.dots.forEach((spark) => {
          const value = shown[spark.band];
          spark.angle += dt * (.25 + value * 1.6) * (spark.band % 2 ? 1 : -1);
          spark.wobble += dt * 3;
          const r = inner + 2 + value * reach * .9 + Math.sin(spark.wobble) * thin;
          ctx.fillStyle = colour(spark.band);
          ctx.globalAlpha = .25 + value * .75;
          dot(at(spark.angle, r), thin * (.5 + value * 1.3));
          ctx.globalAlpha *= .35;
          dot(at(spark.angle - (spark.band % 2 ? .12 : -.12), r), thin * .5);
        });
        break;
      case "tunnel": {
        // Rings rushing out of the cover, faster when it's loud.
        orb.phase = (orb.phase + dt * (live ? .35 + energy * 1.5 : .1)) % 1;
        const count = 7;
        for (let k = 0; k < count; k += 1) {
          const f = (k + orb.phase) / count, r = inner + f * f * reach;
          ctx.strokeStyle = k % 2 ? tones.accent : tones.green;
          ctx.globalAlpha = (1 - f) * (.35 + energy * .65);
          ctx.lineWidth = thin * (.4 + f * 1.6);
          loop((value) => r + value * reach * .18 * f, 48);
          ctx.stroke();
        }
        break;
      }
      case "spiral":
        for (const arm of [0, 1]) {
          const points = shown.map((value, band) => at(-Math.PI / 2 + arm * Math.PI + band / BANDS * Math.PI * 1.7 + now / 2600, inner + 2 + band / (BANDS - 1) * (reach - 4)));
          ctx.strokeStyle = lead;
          ctx.globalAlpha = .22;
          ctx.lineWidth = thin * .5;
          ctx.beginPath();
          points.forEach((point, i) => i ? ctx.lineTo(...point) : ctx.moveTo(...point));
          ctx.stroke();
          points.forEach((point, band) => {
            ctx.fillStyle = colour(band);
            ctx.globalAlpha = .3 + shown[band] * .7;
            dot(point, thin * (.35 + shown[band] * 1.6));
          });
        }
        break;
      case "sonar":
        if (live && (beat || now - orb.ping > 1500)) {
          orb.ping = now;
          orb.rings.push({r: inner, life: 1, width: thin * .8});
        }
        ctx.strokeStyle = tones.green;
        ctx.lineWidth = thin * .4;
        ctx.globalAlpha = .15;
        ray(0, inner, inner + reach);
        ray(Math.PI, inner, inner + reach);
        ray(-Math.PI / 2, inner, inner + reach);
        ray(Math.PI / 2, inner, inner + reach);
        orb.rings = orb.rings.filter((ring) => {
          ring.r += dt * reach * .8;
          ring.life = 1 - (ring.r - inner) / reach;
          if (ring.life <= 0) return false;
          ctx.strokeStyle = tones.green;
          ctx.globalAlpha = ring.life * .8;
          ctx.lineWidth = ring.width;
          circle(ring.r);
          // Contacts light up as the ping reaches them.
          ctx.fillStyle = tones.green;
          shown.forEach((value, band) => {
            const r = inner + value * reach * .92;
            const near = 1 - Math.abs(ring.r - r) / (reach * .25);
            if (near <= 0 || value < .1) return;
            ctx.globalAlpha = near * ring.life;
            for (const s of [1, -1]) dot(at(side(band, s), r), thin * (.6 + value * .8));
          });
          return true;
        });
        break;
      default:
        shown.forEach((value, band) => {
          ctx.strokeStyle = colour(band);
          ctx.fillStyle = colour(band);
          for (const s of [1, -1]) {
            ctx.globalAlpha = .25 + value * .6;
            ray(side(band, s), inner, inner + Math.max(1, value * reach));
            if (style === "peaks") {
              ctx.globalAlpha = .85;
              dot(at(side(band, s), inner + Math.max(2, peaks[band] * reach) + thin * 1.5), thin * .65);
            }
          }
        });
    }
    ctx.restore();
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
    // The moving looks (stars, rings, sparks) keep going while it plays.
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
      palette: options.palette || "", shared: Boolean(painter), wave: wave.length,
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
