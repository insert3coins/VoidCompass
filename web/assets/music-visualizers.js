/*
 * The music visualizers (5.6.2): one set for the Music page's player bar and
 * the music overlay, so a look is the same wherever you watch it. Void
 * Compass's own looks, and the six Pulse looks added in 5.6.2.
 *
 * A painter keeps what the moving looks remember between frames (falling
 * caps, the waterfall's trail, rings, stars, particles). draw() takes the
 * look's id and what's playing: 32 bands from low to high (0-255), the
 * waveform when there is one (0-255, 128 is silence), whether it's playing,
 * the colours, the time and the frame's length.
 *
 * Palettes are colour themes for the Neon skin and the player
 * bar: each names its three colours from low to high, and its peak.
 */
(function (global) {
  "use strict";

  const LOOKS = [
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
    {id: "vu", label: "VU", detail: "A VU meter that holds its peak", group: "PULSE"},
    {id: "radial", label: "RADIAL", detail: "The spectrum around a beating core", group: "PULSE"},
    {id: "particles", label: "PARTICLES", detail: "A burst of sparks on every beat", group: "PULSE"},
    {id: "tunnel", label: "TUNNEL", detail: "A warp tunnel, its rings bent by the music", group: "PULSE"},
    {id: "spiral", label: "SPIRAL", detail: "The spectrum, wound into a spiral", group: "PULSE"},
    {id: "sonar", label: "SONAR", detail: "A sonar pulse on every beat", group: "PULSE"},
    {id: "off", label: "OFF", detail: "No visualizer", group: ""},
  ];

  // The colour themes ("neon" first): panel and text colours for
  // the Neon skin, and the visualizer's low, mid and high, and its peak.
  const PALETTES = {
    neon: {label: "Neon", low: "#21e6c1", mid: "#7a5cff", high: "#ff4f9a", peak: "#ffb24d", panel: "#0d0820", line: "#2b2350", ink: "#eae6ff", dim: "#6f6d99"},
    amber: {label: "Amber Term", low: "#ffb000", mid: "#ff9020", high: "#ff7a00", peak: "#ffd75e", panel: "#160c00", line: "#4a2c05", ink: "#ffd9a0", dim: "#8a5a20"},
    blue: {label: "Blue Phosphor", low: "#3fb4ff", mid: "#5cc4ff", high: "#7ad4ff", peak: "#b8e8ff", panel: "#001428", line: "#0a3a6a", ink: "#cfeeff", dim: "#2f6a99"},
    c64: {label: "C64", low: "#8f9dff", mid: "#a58bff", high: "#c77dff", peak: "#ffe08a", panel: "#161040", line: "#2f2670", ink: "#dcdcff", dim: "#7a76b8"},
    crimson: {label: "Crimson", low: "#ff3355", mid: "#ff5a4a", high: "#ff7a5c", peak: "#ffb84d", panel: "#1e0810", line: "#5c1220", ink: "#ffd9e0", dim: "#8a5568"},
    deep: {label: "Deep Space", low: "#6a7aff", mid: "#8272ff", high: "#9a6aff", peak: "#6ae0ff", panel: "#08081a", line: "#1c1c48", ink: "#c8ccf5", dim: "#55558a"},
    gold: {label: "Gold Rush", low: "#ffcc33", mid: "#ffbb19", high: "#ffaa00", peak: "#fff0b0", panel: "#1a1000", line: "#5c3d0a", ink: "#ffedc2", dim: "#8a6a30"},
    green: {label: "Green Phosphor", low: "#33ff77", mid: "#6fff9a", high: "#9dffb0", peak: "#d6ff5e", panel: "#04140a", line: "#0e3a20", ink: "#bdf7cf", dim: "#3f7a54"},
    ice: {label: "Ice", low: "#6fe3ff", mid: "#8fd9ff", high: "#9fc8ff", peak: "#eaf6ff", panel: "#0a141f", line: "#1c3a55", ink: "#dbf0ff", dim: "#4f7a99"},
    miami: {label: "Miami", low: "#2de6c8", mid: "#ff6fc8", high: "#ff3fa4", peak: "#ffe14d", panel: "#150a28", line: "#3a1f5c", ink: "#ffe0f0", dim: "#7a5590"},
    steel: {label: "Steel", low: "#d8dee6", mid: "#c0c8d2", high: "#a8b2bd", peak: "#f2f5f8", panel: "#101215", line: "#33383e", ink: "#eef1f4", dim: "#6b727a"},
    sunset: {label: "Sunset", low: "#ff6b4a", mid: "#ff4f7a", high: "#ff2f92", peak: "#ffc857", panel: "#2a1030", line: "#5c2050", ink: "#ffe4d6", dim: "#9c6a8a"},
    toxic: {label: "Toxic", low: "#baff29", mid: "#9dff3a", high: "#6bff5e", peak: "#f2ff5e", panel: "#0e1804", line: "#2c4a08", ink: "#e6ffb8", dim: "#5c7a2e"},
    tron: {label: "Tron Grid", low: "#4de8ff", mid: "#6eedff", high: "#8ff2ff", peak: "#ffffff", panel: "#001824", line: "#0a5a7a", ink: "#d6f7ff", dim: "#2f7a99"},
    vaporwave: {label: "Vaporwave", low: "#7af3e0", mid: "#b3a1ff", high: "#ff9de2", peak: "#ffd9a8", panel: "#221542", line: "#41306b", ink: "#f4ecff", dim: "#8d84b8"},
  };

  // A palette as the colours the looks draw with; "theme" (or none) keeps
  // the theme's own, as given.
  function colours(palette, theme) {
    const p = PALETTES[palette];
    if (!p) return theme;
    return {accent: p.low, green: p.mid, orange: p.high, red: p.peak, yellow: p.peak, text: p.ink};
  }

  const BANDS = 32;
  const mean = (bands, from, to) => bands.slice(from, to).reduce((sum, level) => sum + level, 0) / Math.max(1, to - from) / 255;

  function painter() {
    let caps = new Array(BANDS).fill(0);
    let trail = null;
    let rings = [];
    let stars = [];
    let sparks = [];
    let pulses = [];
    let bassAverage = 0;
    let lastRing = 0;
    let pulseBass = 0;
    let vuLevel = 0;
    let vuPeak = 0;
    let phase = 0;
    // How bold the soft looks draw: 1 on the Music page, more over the game.
    let gain = 1;
    const alpha = (value) => Math.min(1, value * gain);

    function reset() {
      caps = new Array(BANDS).fill(0);
      trail = null;
      rings = [];
      stars = [];
      sparks = [];
      pulses = [];
      vuLevel = vuPeak = phase = 0;
    }

    function bars(ctx, width, height, bands, peaksToo) {
      const gap = 4, bar = (width - gap * (BANDS - 1)) / BANDS;
      bands.forEach((level, band) => {
        const tall = Math.max(2, level / 255 * height);
        ctx.globalAlpha = alpha(.12 + level / 255 * .2);
        ctx.fillRect(band * (bar + gap), height - tall, bar, tall);
        if (!peaksToo) return;
        // A cap sits on each bar's highest point and drifts back down.
        caps[band] = Math.max(tall, caps[band] - height * .012);
        ctx.globalAlpha = alpha(.55);
        ctx.fillRect(band * (bar + gap), height - caps[band] - 3, bar, 2);
      });
    }

    function mirror(ctx, width, height, bands) {
      const gap = 4, bar = (width - gap * (BANDS - 1)) / BANDS, middle = height / 2;
      bands.forEach((level, band) => {
        const half = Math.max(1, level / 255 * middle);
        ctx.globalAlpha = alpha(.12 + level / 255 * .22);
        ctx.fillRect(band * (bar + gap), middle - half, bar, half * 2);
      });
    }

    function wave(ctx, width, height, samples) {
      const count = samples ? samples.length : 2;
      ctx.globalAlpha = alpha(.55);
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.beginPath();
      for (let i = 0; i < count; i += 1) {
        const x = i / (count - 1) * width;
        const y = samples ? samples[i] / 255 * height : height / 2;
        if (i) ctx.lineTo(x, y);
        else ctx.moveTo(x, y);
      }
      ctx.stroke();
    }

    function horizon(ctx, width, height, bands) {
      const points = bands.map((level, band) => [band / (BANDS - 1) * width, height - Math.max(2, level / 255 * height * .9)]);
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
      ctx.globalAlpha = alpha(.16);
      ctx.fill();
      ctx.globalAlpha = alpha(.6);
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    function led(ctx, width, height, bands, theme) {
      const rows = 8, gap = 3;
      const cell = (width - gap * (BANDS - 1)) / BANDS, tall = (height - gap * (rows + 1)) / rows;
      bands.forEach((level, band) => {
        const lit = Math.round(level / 255 * rows);
        for (let row = 0; row < rows; row += 1) {
          ctx.fillStyle = row >= rows - 2 ? theme.orange : theme.accent;
          ctx.globalAlpha = row < lit ? alpha(.5) : .06;
          ctx.fillRect(band * (cell + gap), height - gap - (row + 1) * tall - row * gap, cell, tall);
        }
      });
    }

    function aurora(ctx, width, height, bands, theme, now) {
      [[mean(bands, 0, 8), theme.green], [mean(bands, 8, 20), theme.accent], [mean(bands, 20, BANDS), theme.orange]].forEach(([level, colour], k) => {
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
        ctx.globalAlpha = alpha(.14 + level * .3);
        ctx.fill();
      });
    }

    function waterfall(ctx, width, height, bands, theme, canvas) {
      if (!trail || trail.width !== canvas.width || trail.height !== canvas.height) {
        trail = global.document.createElement("canvas");
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
      bands.forEach((level, band) => {
        paper.globalAlpha = .04 + level / 255 * .86;
        paper.fillStyle = level > 190 ? theme.orange : theme.accent;
        paper.fillRect(trail.width - step, trail.height - (band + 1) * row, step, Math.ceil(row));
      });
      paper.globalAlpha = 1;
      ctx.globalAlpha = .8;
      ctx.drawImage(trail, 0, 0, width, height);
    }

    function shockwave(ctx, width, height, bands, theme, now) {
      const bass = mean(bands, 0, 5);
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
    function scanner(ctx, width, height, bands, theme, now) {
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
      bands.forEach((value, band) => {
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
    function witchspace(ctx, width, height, bands, theme, dt) {
      const loud = mean(bands, 0, BANDS);
      const bass = mean(bands, 0, 4);
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

    // -- the Pulse looks (5.6.2) ----------------------------------------------------
    // A VU meter: the loudness (from the waveform, or the bands without one),
    // quick to rise and slow to fall, its peak held a moment.
    function vu(ctx, width, height, bands, samples, theme, playing) {
      let loud;
      if (samples && samples.length) {
        let sum = 0;
        for (const value of samples) sum += ((value - 128) / 128) ** 2;
        loud = Math.min(1, Math.sqrt(sum / samples.length) * 2.3);
      } else {
        loud = Math.min(1, mean(bands, 0, BANDS) * 1.6);
      }
      const want = playing ? loud : 0;
      vuLevel += (want - vuLevel) * (want > vuLevel ? .5 : .08);
      vuPeak = Math.max(vuPeak - .007, vuLevel);
      const count = 24, gap = 3, cell = (width - gap * (count - 1)) / count;
      const lit = Math.round(vuLevel * count), peak = Math.min(count - 1, Math.round(vuPeak * count));
      for (let i = 0; i < count; i += 1) {
        const share = i / count;
        ctx.fillStyle = share < .62 ? theme.accent : share < .84 ? theme.yellow || theme.orange : theme.red;
        ctx.globalAlpha = i < lit ? .8 : .1;
        ctx.fillRect(i * (cell + gap), height * .28, cell, height * .44);
        if (i === peak && vuPeak > .02) {
          ctx.globalAlpha = 1;
          ctx.fillRect(i * (cell + gap), height * .18, cell, 2);
        }
      }
    }

    // The spectrum as spokes around a core that swells with the bass.
    function radial(ctx, width, height, bands, theme, playing) {
      const cx = width / 2, cy = height / 2, base = Math.min(height * .22, 18);
      const bass = mean(bands, 0, 3);
      const reach = Math.min(height * .3, width * .2);
      ctx.save();
      ctx.translate(cx, cy);
      ctx.lineWidth = 2;
      bands.forEach((value, band) => {
        const level = value / 255;
        const angle = band / BANDS * Math.PI * 2 - Math.PI / 2;
        const inner = base + bass * 4, outer = inner + 2 + level * reach;
        ctx.strokeStyle = band % 3 ? theme.accent : theme.orange;
        ctx.globalAlpha = playing ? .35 + level * .6 : .12;
        ctx.beginPath();
        ctx.moveTo(Math.cos(angle) * inner, Math.sin(angle) * inner);
        ctx.lineTo(Math.cos(angle) * outer, Math.sin(angle) * outer);
        ctx.stroke();
      });
      ctx.fillStyle = theme.yellow || theme.orange;
      ctx.globalAlpha = .2 + bass * .7;
      ctx.beginPath();
      ctx.arc(0, 0, 3 + bass * base * .6, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    // Sparks thrown from a glowing core on every beat, fading as they fly;
    // music with little bass still keeps a trickle going.
    function particles(ctx, width, height, bands, theme, playing, dt) {
      const bass = mean(bands, 0, 4), cx = width / 2, cy = height / 2;
      const energy = Math.max(bass, mean(bands, 0, BANDS) * .8);
      const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.min(width, height) * (.18 + energy * .3));
      core.addColorStop(0, theme.orange);
      core.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = core;
      ctx.globalAlpha = playing ? alpha(.18 + energy * .4) : .08;
      ctx.fillRect(0, 0, width, height);
      if (playing && energy > .05 && sparks.length < 120) {
        for (let i = 0; i < 1 + Math.floor(energy * 3); i += 1) {
          const angle = Math.random() * Math.PI * 2, speed = .3 + energy * 1.8 + Math.random() * .5;
          sparks.push({x: cx, y: cy, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed * .6, life: 1,
                       colour: Math.random() > .5 ? theme.accent : theme.orange});
        }
      }
      const step = Math.max(.5, dt / 16.7);
      sparks = sparks.filter((spark) => {
        spark.x += spark.vx * step;
        spark.y += spark.vy * step;
        spark.life -= .015 * step;
        if (spark.life <= 0 || spark.x < 0 || spark.x > width || spark.y < 0 || spark.y > height) return false;
        ctx.fillStyle = spark.colour;
        ctx.globalAlpha = spark.life;
        ctx.fillRect(spark.x - 1, spark.y - 1, 2, 2);
        return true;
      });
    }

    // Rings rushing out of the middle, each bent by its band.
    function tunnel(ctx, width, height, bands, theme, dt) {
      const bass = mean(bands, 0, 3);
      phase += (.01 + bass * .03) * Math.max(.5, dt / 16.7);
      const cx = width / 2, cy = height / 2, most = Math.hypot(cx, cy), count = 12;
      ctx.save();
      ctx.translate(cx, cy);
      for (let i = count; i >= 1; i -= 1) {
        const depth = (i / count + phase * .15) % 1, r = depth * most;
        const level = bands[i % BANDS] / 255;
        ctx.beginPath();
        for (let side = 0; side <= 24; side += 1) {
          const angle = side / 24 * Math.PI * 2 + phase * (i % 2 ? 1 : -1);
          const bend = 1 + level * .25 * Math.sin(angle * 3 + phase * 4);
          const x = Math.cos(angle) * r * bend, y = Math.sin(angle) * r * bend * .6;
          if (side) ctx.lineTo(x, y);
          else ctx.moveTo(x, y);
        }
        ctx.closePath();
        ctx.strokeStyle = i % 3 === 0 ? theme.orange : i % 2 === 0 ? theme.yellow || theme.orange : theme.accent;
        ctx.globalAlpha = Math.max(.05, (1 - depth) * (.35 + level * .65));
        ctx.lineWidth = 1 + level * 2;
        ctx.stroke();
      }
      ctx.restore();
    }

    // The spectrum wound into a spiral that slowly turns.
    function spiral(ctx, width, height, bands, theme, dt) {
      phase += .006 * Math.max(.5, dt / 16.7);
      const cx = width / 2, cy = height / 2, most = Math.min(width, height) / 2 - 4;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.lineWidth = 2;
      bands.forEach((value, band) => {
        const level = value / 255;
        const angle = band / BANDS * Math.PI * 2 * 2.4 + phase;
        const r = band / BANDS * most, length = 3 + level * most * .5;
        ctx.strokeStyle = level > .7 ? theme.yellow || theme.orange : level > .4 ? theme.orange : theme.accent;
        ctx.globalAlpha = .35 + level * .65;
        ctx.beginPath();
        ctx.moveTo(Math.cos(angle) * r * 1.8, Math.sin(angle) * r);
        ctx.lineTo(Math.cos(angle) * (r + length) * 1.8, Math.sin(angle) * (r + length));
        ctx.stroke();
      });
      ctx.restore();
    }

    // A sonar ping from the middle on every beat.
    function sonar(ctx, width, height, bands, theme, playing, dt) {
      const bass = playing ? mean(bands, 0, 3) : 0;
      const cx = width / 2, cy = height / 2, most = Math.hypot(cx, cy);
      if (bass > .35 && bass > pulseBass + .08 && pulses.length < 8) pulses.push({r: 4, life: 1, strength: bass});
      pulseBass = bass * .7 + pulseBass * .3;
      const step = Math.max(.5, dt / 16.7);
      ctx.save();
      ctx.translate(cx, cy);
      pulses = pulses.filter((pulse) => {
        pulse.r += (2.4 + pulse.strength * 2.5) * step;
        pulse.life -= .018 * step;
        if (pulse.life <= 0 || pulse.r > most) return false;
        ctx.strokeStyle = pulse.strength > .7 ? theme.yellow || theme.orange : theme.accent;
        ctx.globalAlpha = Math.max(0, pulse.life) * .8;
        ctx.lineWidth = 1.5 + pulse.strength * 2;
        ctx.beginPath();
        ctx.arc(0, 0, pulse.r, 0, Math.PI * 2);
        ctx.stroke();
        return true;
      });
      ctx.fillStyle = theme.orange;
      ctx.globalAlpha = .3 + bass * .6;
      ctx.beginPath();
      ctx.arc(0, 0, 4 + bass * 10, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    // One frame of a look. The canvas is cleared and scaled already.
    function draw(id, ctx, width, height, {bands = [], wave: samples = null, playing = true, theme, now = 0, dt = 16, canvas, bold = 1} = {}) {
      if (!width || !height || id === "off") return;
      gain = Math.max(1, Number(bold) || 1);
      const levels = bands.length >= BANDS ? bands : Array.from({length: BANDS}, (_, band) => Number(bands[band]) || 0);
      const fill = ctx.createLinearGradient(0, height, 0, 0);
      fill.addColorStop(0, theme.accent);
      fill.addColorStop(1, theme.orange);
      ctx.fillStyle = fill;
      ctx.strokeStyle = fill;
      ({
        bars: () => bars(ctx, width, height, levels, false),
        peaks: () => bars(ctx, width, height, levels, true),
        mirror: () => mirror(ctx, width, height, levels),
        led: () => led(ctx, width, height, levels, theme),
        wave: () => wave(ctx, width, height, playing ? samples : null),
        horizon: () => horizon(ctx, width, height, levels),
        aurora: () => aurora(ctx, width, height, levels, theme, now),
        waterfall: () => waterfall(ctx, width, height, levels, theme, canvas || ctx.canvas),
        shockwave: () => shockwave(ctx, width, height, levels, theme, now),
        scanner: () => scanner(ctx, width, height, levels, theme, now),
        witchspace: () => witchspace(ctx, width, height, levels, theme, dt),
        vu: () => vu(ctx, width, height, levels, samples, theme, playing),
        radial: () => radial(ctx, width, height, levels, theme, playing),
        particles: () => particles(ctx, width, height, levels, theme, playing, dt),
        tunnel: () => tunnel(ctx, width, height, levels, theme, dt),
        spiral: () => spiral(ctx, width, height, levels, theme, dt),
        sonar: () => sonar(ctx, width, height, levels, theme, playing, dt),
      }[id] || (() => bars(ctx, width, height, levels, false)))();
      ctx.globalAlpha = 1;
    }

    return {draw, reset};
  }

  global.VoidCompassVisualizers = Object.freeze({LOOKS, PALETTES, BANDS, colours, painter});
})(window);
