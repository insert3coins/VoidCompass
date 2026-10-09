(() => {
  'use strict';

  /*
   * Journal watcher orb
   * -------------------
   * A HAL 9000-style eye: a brushed metal bezel round a black glass lens,
   * with an iris that glows out of the dark and a white-hot pupil. Here the
   * iris is a small spiral galaxy turning round a star, and the orb watches
   * the journal. Every event falls into the eye as a mote in its own colour.
   * Notable events play their own effect (heartbeat_events.py chooses which):
   * a jump streaks stars out of the pupil, a discovery scan rings out through
   * the bezel, combat turns the iris red and makes it flinch. Status.json
   * writes only run a small blip round the bezel.
   *
   * The orb keeps a mood as well as reacting. Each event leaves its colour in
   * the iris and fades out over several seconds (danger lingers longest), a
   * busy journal brightens the eye and spins the galaxy faster, a long quiet
   * spell lets it drowse, and the game's shutdown or main menu puts it to
   * sleep until the next session wakes it.
   *
   * One 30 fps clock draws it, slowed to 15 fps while the feed is quiet or
   * the eye sleeps. It stops while the page is hidden, and under reduced
   * motion each update paints one still frame with the current mood.
   *
   * The same orb wakes on the dashboard's boot screen, several times larger.
   * There its lines thicken more slowly than the orb grows and the iris gets
   * a denser galaxy, so it reads as a fine instrument, not a magnified icon.
   */

  const TAU = Math.PI * 2;
  const FRAME_MS = 1000 / 30;
  const QUIET_FRAME_MS = 1000 / 15;
  const MAX_MOTES = 40;
  // A burst (a jump writes a dozen events) still shows as a stream of motes,
  // but only the strongest events play full effects.
  const MOTES_PER_UPDATE = 14;
  const EFFECTS_PER_UPDATE = 2;
  const MAX_EFFECTS = 3;
  const DROWSY_AFTER_MS = 90000;
  const DROWSY_FULL_MS = 240000;
  // How long each tone stays in the iris after an event (time constant, ms).
  const TONE_MEMORY = {accent: 6000, muted: 7000, green: 8000, yellow: 8000, orange: 9000, red: 16000};
  const TONES = Object.keys(TONE_MEMORY);

  const clamp = (value, low = 0, high = 1) => Math.max(low, Math.min(high, value));
  const lerp = (from, to, t) => from + (to - from) * t;
  const easeOut = (t) => 1 - (1 - clamp(t)) ** 2;
  const easeIn = (t) => clamp(t) ** 2;
  // Smooth both ways (5.5.3.2): the waves start and settle gently.
  const smooth = (t) => { const x = clamp(t); return x * x * (3 - 2 * x); };
  const smoother = (t) => { const x = clamp(t); return x * x * x * (x * (x * 6 - 15) + 10); };
  // 0 at both ends of a 0..1 journey, 1 in the middle.
  const bump = (t) => Math.sin(Math.PI * clamp(t));
  const span = (p, from, to) => clamp((p - from) / (to - from));

  function random(seed) {
    let state = seed >>> 0;
    return () => {
      state = (state + 0x6D2B79F5) >>> 0;
      let t = state;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function rgb(value) {
    const match = /^#?([0-9a-f]{6})$/i.exec(String(value || '').trim());
    if (!match) return null;
    const number = parseInt(match[1], 16);
    return [(number >> 16) & 255, (number >> 8) & 255, number & 255];
  }

  const mix = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];

  function toHsl([r, g, b]) {
    r /= 255; g /= 255; b /= 255;
    const high = Math.max(r, g, b);
    const low = Math.min(r, g, b);
    const light = (high + low) / 2;
    if (high === low) return [0, 0, light];
    const range = high - low;
    const saturation = light > .5 ? range / (2 - high - low) : range / (high + low);
    const hue = high === r ? (g - b) / range + (g < b ? 6 : 0)
      : high === g ? (b - r) / range + 2 : (r - g) / range + 4;
    return [hue / 6, saturation, light];
  }

  function fromHsl([hue, saturation, light]) {
    if (!saturation) return [light * 255, light * 255, light * 255];
    const q = light < .5 ? light * (1 + saturation) : light + saturation - light * saturation;
    const p = 2 * light - q;
    const channel = (t) => {
      t = ((t % 1) + 1) % 1;
      if (t < 1 / 6) return p + (q - p) * 6 * t;
      if (t < 1 / 2) return q;
      if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
      return p;
    };
    return [channel(hue + 1 / 3) * 255, channel(hue) * 255, channel(hue - 1 / 3) * 255];
  }

  // Blend round the colour wheel, so cyan turning red or orange stays a
  // colour all the way instead of passing through grey.
  function mixHue(a, b, t) {
    const [h1, s1, l1] = toHsl(a);
    const [h2, s2, l2] = toHsl(b);
    let turn = (s1 < .05 ? 0 : s2 < .05 ? 0 : h2 - h1);
    if (turn > .5) turn -= 1;
    if (turn < -.5) turn += 1;
    const hue = s1 < .05 ? h2 : h1 + turn * t;
    return fromHsl([hue, lerp(s1, s2, t), lerp(l1, l2, t)]);
  }
  const paint = (color, alpha = 1) =>
    `rgba(${Math.round(color[0])},${Math.round(color[1])},${Math.round(color[2])},${clamp(alpha)})`;
  const hex = (color) => '#' + color.map((part) => Math.round(part).toString(16).padStart(2, '0')).join('');

  // The theme's own colours. Anything the snapshot leaves out comes from the
  // page's CSS tokens, so nothing here is a colour of its own.
  function themeColors(palette = {}) {
    const style = getComputedStyle(document.documentElement);
    const read = (name) => rgb(palette[name]) || rgb(style.getPropertyValue(`--${name}`)) || null;
    const colors = {};
    for (const name of ['bg', 'panel', 'border', 'text', 'muted', 'accent', 'orange', 'green', 'yellow', 'red']) {
      colors[name] = read(name);
    }
    colors.bg ||= colors.panel || [0, 0, 0];
    colors.text ||= colors.accent || [255, 255, 255];
    for (const name of ['panel', 'border', 'muted', 'accent', 'orange', 'green', 'yellow', 'red']) {
      colors[name] ||= colors.text;
    }
    return colors;
  }

  // The iris galaxy: two spiral arms and a thin halo, built once per detail
  // level. The large orb adds a central bulge and many more, fainter stars.
  function buildGalaxy(arms, halo, bulge, fine) {
    const next = random(9000);
    const stars = [];
    for (let index = 0; index < arms; index += 1) {
      const along = next() ** .85;
      stars.push({
        radius: .1 + .52 * along,
        angle: (index % 2) * Math.PI + along * 3.3 + (next() - .5) * .6 * (1 - along * .4),
        size: (.35 + next() * .7) * (fine ? .7 : 1),
        bright: (.35 + next() * .65) * (fine ? .8 : 1),
        twinkle: next() * TAU,
        along,
      });
    }
    for (let index = 0; index < halo; index += 1) {
      stars.push({
        radius: .16 + next() * .52, angle: next() * TAU, size: (.3 + next() * .4) * (fine ? .7 : 1),
        bright: .2 + next() * .35, twinkle: next() * TAU, along: 1,
      });
    }
    for (let index = 0; index < bulge; index += 1) {
      stars.push({
        radius: .04 + next() ** 2 * .16, angle: next() * TAU, size: .3 + next() * .35,
        bright: .45 + next() * .5, twinkle: next() * TAU, along: .1,
      });
    }
    return stars;
  }
  const GALAXY = buildGalaxy(112, 22, 0, false);
  let fineGalaxy = null;
  const galaxyFor = (R) => (R > 60 ? (fineGalaxy ||= buildGalaxy(760, 150, 140, true)) : GALAXY);

  // The iris's fibres (5.5.3.2): radial strands from the collarette out
  // toward the iris's edge, in three brightnesses, more on a larger eye.
  function buildFibres(count) {
    const next = random(7331);
    return Array.from({length: count}, (_, index) => ({
      angle: (index + next() * .7) / count * TAU,
      from: .16 + next() * .08,
      to: .36 + next() * .4,
      bucket: Math.min(2, Math.floor(next() * next() * 3.4)),
    }));
  }
  const FIBRES = {small: buildFibres(36), medium: buildFibres(80), large: buildFibres(260)};
  const fibresFor = (R) => (R > 60 ? FIBRES.large : R >= 30 ? FIBRES.medium : FIBRES.small);

  // Overlay sizes (up to 96 px) scale lines with the orb. Past that, lines
  // grow more slowly than the orb so a large eye keeps fine detail.
  const lineScale = (R) => (R <= 48 ? R / 27 : (48 / 27) * (R / 48) ** .45);

  /*
   * Effects. Each one lasts `ms`. `mods` bends the eye itself (flare
   * brightens the pupil, pupil and iris scale them, dim darkens the whole
   * eye, jx/jy shake it, spikes shows diffraction spikes). `inner` draws
   * inside the glass; `outer` draws on and past the bezel; `end` runs once
   * when it finishes. p runs 0..1 over the effect; fx.w is the event's
   * weight mapped to 0.55..1 and fx.r holds stable random numbers for its
   * layout.
   */
  const EFFECTS = {
    pulse: {
      ms: 800,
      mods: (p, m, fx) => { m.flare += .45 * fx.w * bump(p); m.iris += .06 * bump(p); },
    },
    wake: {
      // The eye opens from dark, the famous HAL wake, and the bezel lights round.
      ms: 2600,
      mods: (p, m) => { const e = easeOut(p); m.dim *= .12 + .88 * e; m.pupil *= .35 + .65 * e; },
      outer: (g, fx, p) => g.glowTrack(-Math.PI / 2, -Math.PI / 2 + TAU * smoother(span(p, 0, .8)),
        .885, 1.1, fx.color, .7 * (1 - smooth(span(p, .7, 1)))),
    },
    sleep: {
      ms: 2400,
      mods: (p, m) => { const e = easeOut(p); m.dim *= 1 - .68 * e; m.pupil *= 1 - .4 * e; },
      end: (orb) => { orb.asleep = true; },
    },
    warp: {
      // Hyperspace: stars stream out of the pupil past the glass.
      ms: 1500,
      // The galaxy also spins up for the jump; see advance().
      mods: (p, m, fx) => {
        m.flare += .9 * fx.w * bump(span(p, 0, .4));
        m.iris += .15 * bump(p);
      },
      inner: (g, fx, p) => {
        const alpha = bump(p) * .85 * fx.w;
        for (let index = 0; index < 22; index += 1) {
          const angle = fx.r[index] * TAU;
          const start = (.06 + .7 * easeIn(p) * (.6 + .4 * fx.r[index + 22])) * g.R;
          const length = (.05 + .3 * p) * g.R;
          g.ray(angle, start, start + length, mix(g.pal.text, fx.color, .4), alpha, .6 + .5 * fx.r[index + 44]);
        }
      },
    },
    charge: {
      // The drive charging: rings pull into the pupil as it gathers light.
      ms: 1700,
      mods: (p, m, fx) => { m.flare += .7 * fx.w * p * p; m.pupil *= 1 - .25 * bump(p); },
      inner: (g, fx, p) => {
        // Light gathers inward to the pupil in soft waves.
        for (let ring = 0; ring < 3; ring += 1) {
          const q = clamp(p * 1.35 - ring * .2);
          if (q <= 0 || q >= 1) continue;
          g.wave(lerp(.72, .08, smoother(q)), .05 - .03 * q, fx.color, bump(q) * .45 * fx.w);
        }
      },
    },
    cruise: {
      ms: 1300,
      inner: (g, fx, p) => {
        const alpha = bump(p) * .7 * fx.w;
        for (let index = 0; index < 8; index += 1) {
          const y = g.cy + (fx.r[index] - .5) * 1.4 * g.R;
          const travel = easeIn(clamp(p * 1.3 - fx.r[index + 8] * .3));
          const head = g.cx + g.R - 2.4 * g.R * travel;
          g.line(head, y, head + .35 * g.R, y, mix(g.pal.text, fx.color, .5), alpha, .7);
        }
      },
    },
    plot: {
      // A route drawn across the iris, one waypoint at a time.
      ms: 1600,
      inner: (g, fx, p) => {
        const drawn = clamp(p * 1.4);
        const alpha = fx.w * (1 - span(p, .75, 1));
        const point = (t) => {
          const u = 1 - t;
          return [
            g.cx + g.R * (u * u * -.55 + 2 * u * t * 0 + t * t * .55),
            g.cy + g.R * (u * u * .2 + 2 * u * t * -.55 + t * t * .1),
          ];
        };
        const ctx = g.ctx;
        ctx.setLineDash([2 * g.k, 2 * g.k]);
        ctx.beginPath();
        for (let step = 0; step <= 24; step += 1) {
          const t = drawn * step / 24;
          const [x, y] = point(t);
          if (step) ctx.lineTo(x, y); else ctx.moveTo(x, y);
        }
        ctx.strokeStyle = paint(fx.color, .8 * alpha);
        ctx.lineWidth = .8 * g.k;
        ctx.stroke();
        ctx.setLineDash([]);
        for (const t of [0, 1 / 3, 2 / 3, 1]) {
          if (drawn + .001 < t) continue;
          const [x, y] = point(t);
          g.dot(x, y, 1.1, mix(g.pal.text, fx.color, .3), alpha);
        }
      },
    },
    approach: {
      // A planet's limb rises into view at the foot of the lens.
      ms: 1800,
      inner: (g, fx, p) => g.horizon(1.75 - .55 * easeOut(p), fx.color, bump(p) * fx.w),
    },
    depart: {
      ms: 1800,
      inner: (g, fx, p) => g.horizon(1.2 + .55 * easeIn(p), fx.color, bump(p) * fx.w),
    },
    sweep: {
      // A scanner arm passes once round the iris and marks what it finds.
      ms: 1400,
      inner: (g, fx, p) => {
        const alpha = (1 - p * p) * fx.w;
        const start = fx.r[0] * TAU;
        const angle = start + p * TAU;
        for (let trail = 0; trail < 12; trail += 1) {
          g.ray(angle - trail * .05, .08 * g.R, .74 * g.R, fx.color, alpha * .8 * (1 - trail / 12), trail ? .6 : 1);
        }
        // The contact lights as the arm passes it, then fades behind it.
        const found = (.15 + .7 * fx.r[1]) * TAU;
        if (p * TAU >= found) {
          const [x, y] = g.polar(start + found, (.25 + .4 * fx.r[2]) * g.R);
          g.dot(x, y, 1.3, mix(g.pal.text, fx.color, .3), alpha * (1 - (p * TAU - found) / TAU));
        }
      },
    },
    honk: {
      // The discovery scanner: a wave out of the pupil and through the bezel.
      ms: 1700,
      mods: (p, m, fx) => { m.flare += .6 * fx.w * bump(span(p, 0, .33)); },
      outer: (g, fx, p) => {
        // A wave of light out of the pupil, through the glass, past the bezel.
        for (const delay of [0, .2]) {
          const q = span(p, delay, 1);
          if (q <= 0 || q >= 1) continue;
          g.wave(lerp(.08, .98, smoother(q)), .04 + .07 * q, fx.color, (1 - smooth(q)) * .55 * fx.w);
        }
      },
    },
    signal: {
      ms: 1600,
      inner: (g, fx, p) => {
        for (let index = 0; index < 5; index += 1) {
          const q = span(p, index * .12, index * .12 + .5);
          if (q <= 0) continue;
          const [x, y] = g.polar(fx.r[index] * TAU, (.2 + .45 * fx.r[index + 5]) * g.R);
          // Each contact blooms softly and fades.
          g.bloom(x, y, (.03 + .1 * smooth(q)) * g.R, fx.color, bump(q) * .5 * fx.w);
          g.dot(x, y, .8, mix(g.pal.text, fx.color, .4), bump(q) * fx.w);
        }
      },
    },
    spark: {
      // Something new: four-pointed sparkles across the iris.
      ms: 1400,
      inner: (g, fx, p) => {
        for (let index = 0; index < 3; index += 1) {
          const q = span(p, index * .15, index * .15 + .6);
          if (q <= 0) continue;
          const [x, y] = g.polar(fx.r[index] * TAU, (.15 + .4 * fx.r[index + 3]) * g.R);
          g.sparkle(x, y, .16 * g.R * bump(q) * (.7 + .6 * fx.w), mix(g.pal.text, fx.color, .35), bump(q));
        }
      },
    },
    complete: {
      // Every body found: the bezel fills round like a progress ring.
      ms: 1900,
      mods: (p, m, fx) => { m.flare += .5 * fx.w * bump(span(p, .55, 1)); },
      outer: (g, fx, p) => {
        const fade = 1 - smooth(span(p, .7, 1));
        g.glowTrack(-Math.PI / 2, -Math.PI / 2 + TAU * smoother(span(p, 0, .66)), .885, 1.3, fx.color, .85 * fade);
        if (p > .6) g.wave(.8, .05, fx.color, bump(span(p, .6, 1)) * .5 * fx.w);
      },
    },
    lock: {
      // Targeted, or targeting: brackets close on the pupil.
      ms: 1200,
      inner: (g, fx, p) => {
        const size = lerp(.5, .2, easeOut(clamp(p * 1.6))) * g.R;
        const arm = .08 * g.R;
        const blink = p < .8 ? (Math.floor(p * 10) % 2 ? .6 : 1) : (1 - p) / .2;
        const ctx = g.ctx;
        ctx.beginPath();
        for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
          const x = g.cx + sx * size;
          const y = g.cy + sy * size;
          ctx.moveTo(x - sx * arm, y);
          ctx.lineTo(x, y);
          ctx.lineTo(x, y - sy * arm);
        }
        ctx.strokeStyle = paint(fx.color, blink * fx.w);
        ctx.lineWidth = 1.1 * g.k;
        ctx.stroke();
      },
    },
    alarm: {
      // Under threat: the iris strobes and the eye flinches.
      ms: 1500,
      mods: (p, m, fx) => {
        const strobe = (.5 - .5 * Math.cos(p * TAU * 3)) * (1 - p);
        m.flare += .6 * strobe * fx.w;
        m.pupil *= 1 - .35 * bump(p);
        const shake = (1 - p) * .05;
        m.jx += (fx.r[Math.floor(p * 24) % 24] - .5) * shake;
        m.jy += (fx.r[(Math.floor(p * 24) + 7) % 24] - .5) * shake;
      },
      outer: (g, fx, p) => {
        // Three smooth pulses of light round the lip, fading.
        const pulse = (.5 - .5 * Math.cos(p * TAU * 3)) * (1 - smooth(p));
        g.wave(.86, .06, fx.color, pulse * .6 * fx.w);
      },
    },
    breach: {
      // Shields down or the canopy failing: cracks across the glass.
      ms: 1600,
      mods: (p, m, fx) => {
        m.flare += .5 * fx.w * bump(span(p, 0, .25));
        const shake = (1 - span(p, 0, .3)) * .04;
        m.jx += (fx.r[Math.floor(p * 24) % 24] - .5) * shake;
      },
      inner: (g, fx, p) => {
        const ctx = g.ctx;
        ctx.beginPath();
        for (let crack = 0; crack < 3; crack += 1) {
          let angle = fx.r[crack] * TAU;
          let [x, y] = g.polar(angle, .78 * g.R);
          ctx.moveTo(x, y);
          for (let step = 1; step <= 5; step += 1) {
            angle += (fx.r[crack * 5 + step + 3] - .5) * .9;
            [x, y] = g.polar(angle, (.78 - step * .11) * g.R);
            ctx.lineTo(x, y);
          }
        }
        ctx.strokeStyle = paint(mix(g.pal.text, fx.color, .3), (1 - p) * .8 * fx.w);
        ctx.lineWidth = .8 * g.k;
        ctx.stroke();
      },
      outer: (g, fx, p) => g.wave(.86, .05, fx.color, bump(span(p, 0, .5)) * .55 * fx.w),
    },
    die: {
      // A red flare, then the eye goes out until the next session wakes it.
      ms: 3000,
      mods: (p, m) => {
        m.flare += 1.2 * bump(span(p, 0, .2));
        const out = easeOut(span(p, .2, 1));
        m.dim *= 1 - .8 * out;
        m.pupil *= 1 - .6 * out;
      },
      outer: (g, fx, p) => g.wave(lerp(.95, .08, smoother(p)), .07 - .04 * p, fx.color, (1 - smooth(p)) * .6),
      end: (orb) => { orb.asleep = true; },
    },
    clear: {
      ms: 1500,
      mods: (p, m, fx) => { m.flare += .3 * fx.w * bump(p); },
      inner: (g, fx, p) => g.wave(lerp(.2, .82, smoother(p)), .04 + .05 * p, fx.color, bump(p) * .5 * fx.w),
    },
    strike: {
      ms: 1100,
      mods: (p, m, fx) => { m.flare += .5 * fx.w * bump(span(p, 0, .33)); },
      inner: (g, fx, p) => {
        const from = (.12 + .3 * easeOut(p)) * g.R;
        for (let index = 0; index < 8; index += 1) {
          g.ray(index / 8 * TAU + fx.r[0], from, from + .18 * g.R, fx.color, (1 - p) * fx.w, 1);
        }
      },
    },
    gather: {
      // Cargo, fuel, materials: motes spiral in and the pupil takes them.
      ms: 1700,
      mods: (p, m, fx) => { m.flare += .35 * fx.w * span(p, .6, 1); },
      inner: (g, fx, p) => {
        for (let index = 0; index < 12; index += 1) {
          const q = span(p, fx.r[index] * .35, fx.r[index] * .35 + .65);
          if (q <= 0 || q >= 1) continue;
          const [x, y] = g.polar(fx.r[index + 12] * TAU + q * 2.2, .76 * g.R * (1 - easeIn(q)));
          g.dot(x, y, 1 - .5 * q, fx.color, bump(q) * .9);
        }
      },
    },
    payout: {
      // Credits in, or anything leaving the hold: motes burst outward.
      ms: 1600,
      mods: (p, m, fx) => { m.flare += .5 * fx.w * bump(span(p, 0, .33)); },
      inner: (g, fx, p) => {
        for (let index = 0; index < 14; index += 1) {
          const q = span(p, fx.r[index] * .2, fx.r[index] * .2 + .8);
          if (q <= 0 || q >= 1) continue;
          const [x, y] = g.polar(fx.r[index + 14] * TAU, (.08 + .7 * easeOut(q)) * g.R);
          g.dot(x, y, 1.1 - .5 * q, mix(fx.color, g.pal.text, .2), (1 - q) * .9);
        }
      },
    },
    crack: {
      // An asteroid cracked open: a flash and fragments flung outward.
      ms: 1300,
      mods: (p, m, fx) => { m.flare += .9 * fx.w * bump(span(p, 0, .25)); },
      inner: (g, fx, p) => {
        const r = (.1 + .75 * easeOut(p)) * g.R;
        for (let index = 0; index < 9; index += 1) {
          const angle = fx.r[index] * TAU;
          g.ray(angle, r * (.8 + .2 * fx.r[index + 9]), r * (.8 + .2 * fx.r[index + 9]) + .06 * g.R,
            fx.color, (1 - p) * fx.w, 1.4);
        }
      },
    },
    dock: {
      // Docking and landing: guidance rings close in on the pupil.
      ms: 1700,
      inner: (g, fx, p) => {
        for (let ring = 0; ring < 3; ring += 1) {
          const q = clamp(p * 1.3 - ring * .15);
          if (q <= 0) continue;
          g.wave(lerp(.78, .12, smoother(q)), .045, fx.color, bump(q) * .45 * fx.w);
        }
      },
    },
    undock: {
      ms: 1700,
      inner: (g, fx, p) => {
        for (let ring = 0; ring < 3; ring += 1) {
          const q = clamp(p * 1.3 - ring * .15);
          if (q <= 0) continue;
          g.wave(lerp(.12, .78, smoother(q)), .045, fx.color, bump(q) * .45 * fx.w);
        }
      },
    },
    deny: {
      // Refused: the eye shakes its head.
      ms: 1000,
      mods: (p, m) => { m.jx += Math.sin(p * TAU * 3) * (1 - p) * .05; m.pupil *= 1 - .3 * bump(p); },
      inner: (g, fx, p) => {
        const size = .18 * g.R;
        g.line(g.cx - size, g.cy - size, g.cx + size, g.cy + size, fx.color, (1 - p) * fx.w, 1.4);
        g.line(g.cx - size, g.cy + size, g.cx + size, g.cy - size, fx.color, (1 - p) * fx.w, 1.4);
      },
    },
    speak: {
      // A message: the pupil glows and falls like a voice, as HAL's did.
      ms: 2000,
      mods: (p, m, fx) => {
        const voice = speech(p);
        m.flare += .75 * voice * fx.w;
        m.iris += .08 * voice;
      },
      inner: (g, fx, p) => {
        const voice = speech(p);
        // Its voice: soft waves of light rising out of the pupil and fading
        // into the glass (5.5.3.2).
        for (let ring = 0; ring < 3; ring += 1) {
          const q = (p * 4 + ring / 3) % 1;
          g.wave(.1 + .5 * smoother(q), .03 + .04 * q, fx.color, voice * Math.sin(Math.PI * q) * .28 * fx.w);
        }
      },
    },
    glint: {
      // Promotions, new ships and upgrades: diffraction spikes on the star.
      ms: 1500,
      mods: (p, m, fx) => {
        m.spikes = Math.max(m.spikes, bump(p) * fx.w);
        m.flare += .5 * bump(p) * fx.w;
      },
    },
  };

  function speech(p) {
    return (Math.abs(Math.sin(p * 29)) * .55 + Math.abs(Math.sin(p * 47 + 1.3)) * .45) * bump(p);
  }

  // Drawing helpers bound to one frame's geometry. R is the orb's radius;
  // sizes in R units scale with the orb, line widths in k units with its size.
  function geometry(ctx, R, cx, cy, pal) {
    const k = lineScale(R);
    const g = {
      ctx, R, k, cx, cy, pal,
      polar: (angle, radius) => [cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius],
      line(x1, y1, x2, y2, color, alpha, width = 1) {
        if (alpha <= 0) return;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.strokeStyle = paint(color, alpha);
        ctx.lineWidth = width * k;
        ctx.stroke();
      },
      ray(angle, from, to, color, alpha, width = 1) {
        const [x1, y1] = g.polar(angle, from);
        const [x2, y2] = g.polar(angle, to);
        g.line(x1, y1, x2, y2, color, alpha, width);
      },
      dot(x, y, size, color, alpha) {
        if (alpha <= 0) return;
        ctx.beginPath();
        ctx.arc(x, y, Math.max(.3, size * k), 0, TAU);
        ctx.fillStyle = paint(color, alpha);
        ctx.fill();
      },
      circle(x, y, radius, width, color, alpha) {
        if (alpha <= 0 || radius <= 0) return;
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, TAU);
        ctx.strokeStyle = paint(color, alpha);
        ctx.lineWidth = width * k;
        ctx.stroke();
      },
      ring: (radius, width, color, alpha) => g.circle(cx, cy, radius * R, width, color, alpha),
      // A soft wave of light (5.5.3.2): a glowing band that fades in and out
      // across its width, instead of a hard drawn circle.
      wave(radius, width, color, alpha, x = cx, y = cy) {
        if (alpha <= .004 || radius <= 0) return;
        const middle = radius * R;
        const half = Math.max(1.1 * k, width * R);
        const inner = Math.max(0, middle - half);
        const outer = middle + half;
        const band = ctx.createRadialGradient(x, y, inner, x, y, outer);
        band.addColorStop(0, paint(color, 0));
        band.addColorStop(.5, paint(color, clamp(alpha)));
        band.addColorStop(1, paint(color, 0));
        ctx.fillStyle = band;
        ctx.beginPath();
        ctx.arc(x, y, outer, 0, TAU);
        if (inner > 0) ctx.arc(x, y, inner, 0, TAU, true);
        ctx.fill();
      },
      // A soft bloom of light at a point.
      bloom(x, y, radius, color, alpha) {
        if (alpha <= .004 || radius <= 0) return;
        const light = ctx.createRadialGradient(x, y, 0, x, y, radius);
        light.addColorStop(0, paint(color, clamp(alpha)));
        light.addColorStop(1, paint(color, 0));
        ctx.fillStyle = light;
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, TAU);
        ctx.fill();
      },
      // A bezel track with a soft glow round it.
      glowTrack(from, to, radius, width, color, alpha) {
        if (to <= from || alpha <= 0) return;
        ctx.save();
        ctx.shadowColor = paint(color, clamp(alpha));
        ctx.shadowBlur = 5 * k;
        g.track(from, to, radius, width, color, alpha);
        ctx.restore();
      },
      arc(from, to, radius, width, color, alpha) {
        if (alpha <= 0) return;
        ctx.beginPath();
        ctx.arc(cx, cy, radius * R, from, to);
        ctx.strokeStyle = paint(color, alpha);
        ctx.lineWidth = width * k;
        ctx.stroke();
      },
      track(from, to, radius, width, color, alpha) {
        if (to <= from) return;
        ctx.lineCap = 'round';
        g.arc(from, to, radius, width, color, alpha);
        ctx.lineCap = 'butt';
      },
      sparkle(x, y, length, color, alpha) {
        if (alpha <= 0 || length <= 0) return;
        g.line(x - length, y, x + length, y, color, alpha, .8);
        g.line(x, y - length, x, y + length, color, alpha, .8);
        const short = length * .45;
        g.line(x - short, y - short, x + short, y + short, color, alpha * .6, .6);
        g.line(x - short, y + short, x + short, y - short, color, alpha * .6, .6);
      },
      horizon(offset, color, alpha) {
        if (alpha <= 0) return;
        const radius = 1.15 * R;
        ctx.beginPath();
        ctx.arc(cx, cy + offset * R, radius, 0, TAU);
        ctx.fillStyle = paint(color, .14 * alpha);
        ctx.fill();
        ctx.strokeStyle = paint(mix(color, pal.text, .3), .7 * alpha);
        ctx.lineWidth = 1.2 * k;
        ctx.stroke();
      },
    };
    return g;
  }

  class HeartbeatOrb {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.pal = null;
      this.eye = 'theme';
      this.reduced = false;
      this.crt = true;
      this.stalled = false;
      this.asleep = false;
      this.lastSeq = null;
      this.statusSeq = null;
      this.lastEvent = '';
      this.effects = [];
      this.motes = [];
      this.blips = [];
      this.blipAngle = -Math.PI / 2;
      this.heat = Object.fromEntries(TONES.map((tone) => [tone, 0]));
      this.arousal = 0;
      this.decayedAt = performance.now();
      this.lastEventAt = performance.now();
      this.lastSip = -Infinity;
      this.spin = 0;
      this.moon = 0;
      this.breath = 0;
      this.gaze = {x: 0, y: 0, tx: 0, ty: 0, until: 0};
      // Its aperture, glances, activity and moods between events (heartbeat-life.js).
      this.life = window.HeartbeatLife ? new window.HeartbeatLife() : null;
      this.pose = null;
      // The music it hears (5.5.3.2): smoothed toward what the player sends.
      this.musicTarget = {level: 0, bass: 0};
      this.musicLevel = 0;
      this.musicBass = 0;
      this.layers = new Map();
      this.palKey = '';
      this.seed = 1;
      this.size = 0;
      this.ratio = 1;
      this.frames = 0;
      this.suspended = false;
      this.running = false;
      this.raf = 0;
      this.lastFrame = 0;
      this.lastPaint = 0;
      this.loop = this.loop.bind(this);
      this.onVisibility = () => this.schedule();
      document.addEventListener('visibilitychange', this.onVisibility);
      if (window.ResizeObserver) {
        this.observer = new ResizeObserver(() => { this.resize(); this.draw(performance.now()); });
        this.observer.observe(canvas);
      }
      this.resize();
    }

    resize() {
      const size = Math.min(this.canvas.clientWidth, this.canvas.clientHeight);
      const shown = this.canvas.getBoundingClientRect().width;
      const zoom = this.canvas.clientWidth > 0 && shown > 0 ? shown / this.canvas.clientWidth : 1;
      this.ratio = clamp((window.devicePixelRatio || 1) * zoom, 1, 4);
      const backing = Math.max(1, Math.round(size * this.ratio));
      if (this.canvas.width !== backing || this.canvas.height !== backing) {
        this.canvas.width = backing;
        this.canvas.height = backing;
      }
      this.size = size;
    }

    update(input = {}) {
      const now = performance.now();
      this.decay(now);
      this.pal = themeColors(input.palette || {});
      this.palKey = JSON.stringify(this.pal);
      this.eye = input.eye === 'hal' ? 'hal' : 'theme';
      this.reduced = Boolean(input.reducedMotion);
      this.crt = input.crt !== false;
      const stalled = Boolean(input.stalled);
      if (stalled || this.reduced) this.clearMotion();
      if (this.life) {
        this.life.configure({liveliness: input.liveliness, idle: input.idle, reduced: this.reduced, state: input.state,
          overlays: input.overlays, personality: input.personality, memory: input.memory}, now);
        if (input.vitals) this.life.vitals(input.vitals);
      }
      this.stalled = stalled;

      const events = (Array.isArray(input.events) ? input.events : [])
        .filter((event) => event && Number.isFinite(Number(event.seq)))
        .sort((a, b) => Number(a.seq) - Number(b.seq));
      const newest = events.length ? Number(events[events.length - 1].seq) : 0;
      if (this.lastSeq === null) {
        // What was already in the journal is history, not news. The eye
        // just opens on it.
        this.lastSeq = newest;
        this.lastEvent = events.length ? String(events[events.length - 1].event || '') : '';
        if (!this.reduced && !this.stalled) this.play({effect: 'wake', tone: 'accent', weight: .8}, now);
      } else {
        // A restarted app counts from one again.
        if (newest < this.lastSeq) this.lastSeq = 0;
        const fresh = events.filter((event) => Number(event.seq) > this.lastSeq);
        if (fresh.length) {
          this.lastSeq = newest;
          this.observe(fresh, now);
        }
      }

      const status = Number(input.statusSeq);
      if (Number.isFinite(status)) {
        if (this.statusSeq !== null && status !== this.statusSeq) this.blip(now);
        this.statusSeq = status;
      }
      this.schedule();
    }

    observe(fresh, now) {
      this.lastEventAt = now;
      this.lastEvent = String(fresh[fresh.length - 1].event || '');
      for (const event of fresh) {
        this.feel(event);
        // A rare find earns a double take that ends in a pulse.
        const pulseAt = this.life?.notice(event, now);
        if (pulseAt && !this.reduced && !this.stalled) {
          this.play({effect: 'pulse', tone: event.tone || 'yellow', weight: .9}, pulseAt);
        }
      }
      const rousing = fresh.some((event) => !['sleep', 'die', 'tick'].includes(event.effect)
        && Number(event.weight) >= .2);
      const sleeping = fresh.some((event) => ['sleep', 'die'].includes(event.effect));
      if (this.reduced || this.stalled) {
        if (sleeping) this.asleep = true;
        else if (rousing) this.asleep = false;
        return;
      }
      if (this.asleep && rousing && !fresh.some((event) => event.effect === 'wake')) {
        this.play({effect: 'wake', tone: 'accent', weight: .6}, now);
      }
      fresh.slice(-MOTES_PER_UPDATE).forEach((event, index) => this.spawnMote(event, now + index * 70));
      fresh
        .filter((event) => event.effect !== 'tick' && Number(event.weight) >= .2)
        .sort((a, b) => Number(b.weight) - Number(a.weight))
        .slice(0, EFFECTS_PER_UPDATE)
        .forEach((event, index) => this.play(event, now + index * 180));
    }

    feel(event) {
      const tone = TONES.includes(event.tone) ? event.tone : 'muted';
      const weight = clamp(Number(event.weight) || 0);
      this.heat[tone] = Math.min(1.6, this.heat[tone] + weight * .9);
      this.arousal = clamp(this.arousal + weight * .35);
    }

    decay(now) {
      const elapsed = Math.max(0, now - this.decayedAt);
      this.decayedAt = now;
      for (const tone of TONES) this.heat[tone] *= Math.exp(-elapsed / TONE_MEMORY[tone]);
      this.arousal *= Math.exp(-elapsed / 12000);
    }

    // The Music player's levels (0..255 bands), or null when nothing plays.
    music(bands) {
      if (!Array.isArray(bands) || !bands.length || this.reduced) {
        this.musicTarget = {level: 0, bass: 0};
        return;
      }
      const values = bands.map((value) => clamp(Number(value) / 255));
      const low = values.slice(0, Math.max(1, Math.floor(values.length / 4)));
      this.musicTarget = {
        level: values.reduce((sum, value) => sum + value, 0) / values.length,
        bass: low.reduce((sum, value) => sum + value, 0) / low.length,
      };
    }

    // Composing a thought: the aperture closes in while it thinks (5.5.3.2).
    think(ms = 600) {
      if (this.reduced || this.stalled) return;
      this.life?.think(ms, performance.now());
    }

    // How it feels about what it's saying: the eye acts it out. (feel()
    // is the event's colour in the iris; this is a thought's mood.)
    showMood(mood) {
      if (this.reduced || this.stalled) return;
      this.life?.feel(mood, performance.now());
    }

    // The metal and glass that don't change frame to frame, painted once per
    // size, palette and scanline setting and reused (5.5.3.2).
    layer(name, paint) {
      const key = `${name}|${this.size}|${this.ratio}|${this.palKey}|${this.crt}`;
      let canvas = this.layers.get(key);
      if (canvas) return canvas;
      if (this.layers.size > 8) this.layers.clear();
      canvas = document.createElement('canvas');
      canvas.width = canvas.height = Math.max(1, Math.round(this.size * this.ratio));
      const ctx = canvas.getContext('2d');
      ctx.setTransform(this.ratio, 0, 0, this.ratio, 0, 0);
      const R = this.size / 2;
      paint(geometry(ctx, R, R, R, this.pal));
      this.layers.set(key, canvas);
      return canvas;
    }

    // The eye speaks a thought: its pupil rises and falls like a voice.
    speak(ms = 2000) {
      if (this.reduced || this.stalled) return;
      this.play({effect: 'speak', tone: 'accent', weight: .8}, performance.now(), Math.max(1200, Math.min(9000, ms)));
    }

    play(event, start, ms = null) {
      const spec = EFFECTS[event.effect];
      if (!spec) return;
      if (event.effect === 'wake') this.asleep = false;
      const next = random((this.seed += 7919));
      this.effects = this.effects.filter((effect) => effect.name !== event.effect);
      this.effects.push({
        name: event.effect, spec, start, ms: ms || spec.ms,
        tone: TONES.includes(event.tone) ? event.tone : 'accent',
        w: .55 + .45 * clamp(Number(event.weight) || 0),
        r: Array.from({length: 64}, next),
      });
      while (this.effects.length > MAX_EFFECTS) this.effects.shift();
    }

    spawnMote(event, start) {
      const next = random((this.seed += 104729));
      const angle = next() * TAU;
      this.motes.push({
        start, ms: 1100 + next() * 600, angle,
        twist: (next() < .5 ? -1 : 1) * (.6 + next() * .8),
        tone: TONES.includes(event.tone) ? event.tone : 'muted',
        size: .7 + .6 * clamp(Number(event.weight) || 0),
        dream: Boolean(event.dream),
      });
      if (this.motes.length > MAX_MOTES) this.motes.splice(0, this.motes.length - MAX_MOTES);
      // The eye glances toward what it just noticed (with the life module,
      // it looks where the event points instead).
      if (!this.life) {
        this.gaze.tx = Math.cos(angle) * .05;
        this.gaze.ty = Math.sin(angle) * .05;
        this.gaze.until = start + 2200;
      }
    }

    blip(now) {
      if (this.stalled || this.reduced) return;
      const last = this.blips[this.blips.length - 1];
      if (last && now - last.start < 350) return;
      this.blips.push({start: now, angle: this.blipAngle});
      this.blipAngle += TAU / 12;
      if (this.blips.length > 3) this.blips.shift();
    }

    clearMotion() {
      for (const effect of this.effects) effect.spec.end?.(this);
      this.effects = [];
      this.motes = [];
      this.blips = [];
    }

    color(tone) {
      if (!this.pal) return [0, 0, 0];
      if (tone === 'accent') return this.base();
      return this.pal[tone] || this.pal.accent;
    }

    base() {
      return this.eye === 'hal' ? this.pal.red : this.pal.accent;
    }

    // The iris colour: the resting eye, pulled toward the strongest tone the
    // recent events left behind. Averaging every tone turned a busy journal
    // grey, so only the leading one colours it, and danger leads early.
    tint() {
      let lead = null;
      for (const tone of TONES) {
        const weight = this.heat[tone] * (tone === 'red' ? 1.5 : 1);
        if (weight > .01 && (!lead || weight > lead.weight)) lead = {tone, weight};
      }
      if (!lead) return this.base();
      return mixHue(this.base(), this.color(lead.tone), clamp(this.heat[lead.tone] * 1.3));
    }

    // A host page that hides the orb (the boot screen once the deck is up)
    // stops its clock without discarding its state.
    setSuspended(suspended) {
      this.suspended = Boolean(suspended);
      this.schedule();
    }

    schedule() {
      const animate = !this.suspended && !this.reduced && !document.hidden && this.pal && this.size > 0;
      if (animate && !this.running) {
        this.running = true;
        this.lastFrame = performance.now();
        this.raf = requestAnimationFrame(this.loop);
      } else if (!animate && this.running) {
        cancelAnimationFrame(this.raf);
        this.running = false;
      }
      if (!animate && !this.suspended) this.draw(performance.now());
    }

    loop(now) {
      if (!this.running) return;
      this.raf = requestAnimationFrame(this.loop);
      const interval = this.stalled || this.asleep ? QUIET_FRAME_MS : FRAME_MS;
      if (now - this.lastPaint < interval - 2) return;
      this.lastPaint = now;
      this.advance(now);
      this.draw(now);
    }

    advance(now) {
      const elapsed = Math.min(100, Math.max(0, now - this.lastFrame));
      this.lastFrame = now;
      this.decay(now);
      const drowsy = this.drowsiness(now);
      this.life?.advance(now, {asleep: this.asleep, drowsy, stalled: this.stalled});
      if (!this.stalled) {
        let spin = (1 + this.arousal * 1.5) * Math.max(.4, this.pose?.spin ?? 1);
        for (const effect of this.effects) {
          const p = (now - effect.start) / effect.ms;
          if (p > 0 && p < 1 && effect.name === 'warp') spin += 6 * bump(p);
        }
        this.spin += elapsed / 1000 * .12 * spin * (1 - .5 * drowsy) * (this.asleep ? .2 : 1);
        this.moon += elapsed / 26000 * TAU;
      }
      this.breath += elapsed / (this.asleep || drowsy > .5 ? 8000 : 5200);
      // Music: quick to rise with the beat, slower to fall.
      const rise = (target, current) => current + (target - current) * Math.min(1, elapsed / (target > current ? 60 : 260));
      this.musicLevel = rise(this.musicTarget.level, this.musicLevel);
      this.musicBass = rise(this.musicTarget.bass, this.musicBass);
      if (this.musicLevel > .02 && !this.stalled) this.spin += elapsed / 1000 * .12 * this.musicLevel * 1.5;
      // With the life module the eye follows the newest event as it falls
      // in, so every journal line gets a look, however small.
      if (this.life && this.motes.length && !this.reduced && !this.asleep) {
        const mote = this.motes[this.motes.length - 1];
        const q = clamp((now - mote.start) / mote.ms);
        if (q > 0 && q < 1) {
          const radius = .76 * (1 - easeIn(q)) * .09;
          this.gaze.tx = Math.cos(mote.angle + mote.twist * q) * radius;
          this.gaze.ty = Math.sin(mote.angle + mote.twist * q) * radius;
          this.gaze.until = now + 200;
        }
      }
      const looking = now < this.gaze.until;
      const ease = Math.min(1, elapsed / 260);
      this.gaze.x += ((looking ? this.gaze.tx : 0) - this.gaze.x) * ease;
      this.gaze.y += ((looking ? this.gaze.ty : 0) - this.gaze.y) * ease;
      this.effects = this.effects.filter((effect) => {
        if (now < effect.start + effect.ms) return true;
        effect.spec.end?.(this);
        return false;
      });
      this.motes = this.motes.filter((mote) => {
        if (now < mote.start + mote.ms) return true;
        this.lastSip = now;
        return false;
      });
      this.blips = this.blips.filter((blip) => now < blip.start + 650);
      // Asleep, it dreams: faint motes of the session's notable moments
      // drift through the iris.
      const highlights = this.life?.highlights || [];
      if (this.asleep && highlights.length && !this.reduced && now >= (this.nextDream || 0)) {
        const tone = highlights[Math.floor(random((this.seed += 31))() * highlights.length)];
        this.spawnMote({tone, weight: .3, dream: true}, now);
        this.nextDream = now + 3000 + random((this.seed += 17))() * 3000;
      }
      this.frames += 1;
    }

    drowsiness(now) {
      return clamp((now - this.lastEventAt - DROWSY_AFTER_MS) / (DROWSY_FULL_MS - DROWSY_AFTER_MS));
    }

    draw(now) {
      const ctx = this.ctx;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.globalCompositeOperation = 'source-over';
      ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      if (!this.pal || this.size < 8) return;
      ctx.setTransform(this.ratio, 0, 0, this.ratio, 0, 0);

      const pose = this.life ? this.life.pose(now) : null;
      this.pose = pose;
      const mods = {flare: 0, pupil: pose?.pupil ?? 1, iris: pose?.iris ?? 1, dim: pose?.dim ?? 1,
        jx: 0, jy: 0, spikes: 0};
      const live = [];
      for (const effect of this.effects) {
        const p = (now - effect.start) / effect.ms;
        if (p < 0 || p > 1) continue;
        effect.color = this.color(effect.tone);
        effect.spec.mods?.(p, mods, effect);
        live.push([effect, p]);
      }
      // The music: the iris swells with the bass and the eye brightens.
      if (this.musicBass > .01 && !this.asleep) {
        mods.iris += .08 * this.musicBass;
        mods.flare += .3 * this.musicBass;
        mods.dim *= 1 + .12 * this.musicLevel;
      }
      const R = this.size / 2;
      const cx = R + mods.jx * R;
      const cy = R + mods.jy * R;
      const pal = this.pal;
      const g = geometry(ctx, R, cx, cy, pal);
      // Tension warms the iris toward red, as danger events do.
      let tint = pose?.red ? mixHue(this.tint(), pal.red, pose.red * .55) : this.tint();
      // An expression's own colour: pleased warms toward green, wary orange.
      if (pose?.tone && pose.toneAmount > .01 && pal[pose.tone]) tint = mixHue(tint, pal[pose.tone], pose.toneAmount);
      const drowsy = this.drowsiness(now);
      const breath = .5 + .5 * Math.sin(this.breath * TAU);
      const level = clamp((.8 + .2 * this.arousal) * (1 - .22 * drowsy) * (this.asleep ? .32 : 1) * mods.dim, .05, 1);
      const sip = Math.exp(-(now - this.lastSip) / 300) * .15;
      const flare = clamp(mods.flare + sip + (pose?.flare || 0) + .35 * (pose?.aperture || 0), 0, 1.6);
      g.tint = tint;
      g.level = level;

      this.drawBezel(g, tint, level);

      // Everything inside the lens.
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, .8 * R, 0, TAU);
      ctx.clip();
      const glass = ctx.createRadialGradient(cx, cy, 0, cx, cy, .8 * R);
      glass.addColorStop(0, paint(mix(pal.bg, tint, .12)));
      glass.addColorStop(1, paint(pal.bg));
      ctx.fillStyle = glass;
      ctx.fillRect(cx - R, cy - R, 2 * R, 2 * R);

      ctx.globalCompositeOperation = 'lighter';
      const gx = cx + (this.gaze.x + (pose?.dx ?? 0)) * R;
      const gy = cy + (this.gaze.y + (pose?.dy ?? 0)) * R;
      // The iris: HAL's glow, strongest at the pupil and fading into the glass.
      // The aperture tightens the iris as it thinks.
      const irisRadius = .66 * R * mods.iris * (.96 + .06 * breath) * (1 - .1 * (pose?.aperture || 0));
      const iris = ctx.createRadialGradient(gx, gy, 0, gx, gy, irisRadius);
      iris.addColorStop(0, paint(mix(tint, pal.text, .55), .95 * level));
      iris.addColorStop(.1, paint(tint, .9 * level));
      iris.addColorStop(.3, paint(tint, .5 * level));
      iris.addColorStop(.55, paint(mix(tint, pal.bg, .3), .18 * level));
      iris.addColorStop(.8, paint(tint, .05 * level));
      iris.addColorStop(1, paint(tint, 0));
      ctx.fillStyle = iris;
      ctx.beginPath();
      ctx.arc(gx, gy, irisRadius, 0, TAU);
      ctx.fill();
      this.drawFibres(g, gx, gy, irisRadius, tint, level);

      // Now and then the lens hunts for focus.
      if (pose?.blur > .05) ctx.filter = `blur(${(pose.blur * .012 * R).toFixed(2)}px)`;
      this.drawGalaxy(g, gx, gy, tint, level, now);
      ctx.filter = 'none';
      for (const [effect, p] of live) effect.spec.inner?.(g, effect, p);
      this.drawMotes(g, now);
      this.drawDiaphragm(g, gx, gy, irisRadius, tint, level, pose?.aperture || 0);
      ctx.globalCompositeOperation = 'lighter';
      this.drawCore(g, gx, gy, tint, level, breath, flare, mods);

      ctx.globalCompositeOperation = 'source-over';
      ctx.drawImage(this.layer('glass', (layer) => this.paintGlass(layer)), cx - R, cy - R, 2 * R, 2 * R);
      ctx.globalCompositeOperation = 'lighter';
      this.drawGhosts(g, gx, gy, tint, level);
      ctx.globalCompositeOperation = 'source-over';
      if (pose?.glint != null) this.drawGlint(g, pose.glint);
      if (pose) this.drawLids(g, pose);
      ctx.restore();

      ctx.globalCompositeOperation = 'lighter';
      for (const [effect, p] of live) effect.spec.outer?.(g, effect, p);
      for (const blip of this.blips) {
        const q = clamp((now - blip.start) / 650);
        const to = blip.angle + .5 * easeOut(q);
        g.glowTrack(blip.angle + .5 * easeOut(Math.max(0, q - .25)), to, .885, .9, mix(tint, pal.text, .3), (1 - smooth(q)) * .7);
        const [x, y] = g.polar(to, .885 * R);
        g.dot(x, y, 1, mix(tint, pal.text, .5), 1 - q);
      }
      ctx.globalCompositeOperation = 'source-over';
      if (this.stalled) {
        // A quiet feed lights one small lamp; it never puts the eye out.
        const [x, y] = g.polar(Math.PI / 4, .885 * R);
        g.dot(x, y, 1.9, pal.red, .45 + .45 * breath);
      }
    }

    drawBezel(g, tint, level) {
      const {ctx, R, cx, cy, pal} = g;
      ctx.drawImage(this.layer('bezel', (layer) => this.paintBezel(layer)), cx - R, cy - R, 2 * R, 2 * R);
      // The iris's light spills onto the inner lip of the bezel.
      ctx.globalCompositeOperation = 'lighter';
      const spill = ctx.createRadialGradient(cx, cy, .79 * R, cx, cy, .9 * R);
      spill.addColorStop(0, paint(tint, .15 * level));
      spill.addColorStop(.45, paint(tint, .04 * level));
      spill.addColorStop(1, paint(tint, 0));
      ctx.fillStyle = spill;
      ctx.beginPath();
      ctx.arc(cx, cy, .9 * R, 0, TAU);
      ctx.arc(cx, cy, .8 * R, 0, TAU, true);
      ctx.fill();
      ctx.globalCompositeOperation = 'source-over';
      // Instrument indexing round the lens, in the eye's own colour.
      const count = R >= 120 ? 96 : R >= 36 ? 48 : 24;
      for (let index = 0; index < count; index += 1) {
        const major = index % (count / 4) === 0;
        g.ray(index / count * TAU - Math.PI / 2, .85 * R, (major ? .935 : .9) * R,
          mix(tint, pal.bg, .2), (major ? .5 : .24) * (.5 + .5 * level), major ? .9 : .5);
      }
      // A small moon keeps its orbit round the bezel.
      const [x, y] = g.polar(this.moon - Math.PI / 2, .885 * R);
      ctx.globalCompositeOperation = 'lighter';
      g.dot(x, y, 2.4, tint, .18 * level);
      g.dot(x, y, 1, mix(tint, pal.text, .6), .9 * level);
      ctx.globalCompositeOperation = 'source-over';
    }

    // The bezel's metal, painted once (layer()): brushed aluminium lit from
    // the upper left like HAL's faceplate, a bevelled outer edge and an inner
    // lip falling away to the glass.
    paintBezel(g) {
      const {ctx, R, cx, cy, pal, k} = g;
      const outer = .97 * R;
      const inner = .8 * R;
      const band = () => {
        ctx.beginPath();
        ctx.arc(cx, cy, outer, 0, TAU);
        ctx.arc(cx, cy, inner, 0, TAU, true);
      };
      const metal = ctx.createRadialGradient(cx - .3 * R, cy - .35 * R, .1 * R, cx, cy, outer);
      metal.addColorStop(0, paint(mix(pal.text, pal.bg, .25)));
      metal.addColorStop(.6, paint(mix(pal.text, pal.bg, .55)));
      metal.addColorStop(.85, paint(mix(pal.border, pal.bg, .45)));
      metal.addColorStop(1, paint(pal.bg));
      band();
      ctx.fillStyle = metal;
      ctx.fill();
      // Brushing: fine concentric grain, light and dark.
      const grain = random(4242);
      const lines = Math.round(clamp(R * 1.6, 24, 360));
      const pitch = (outer - inner) / lines;
      ctx.lineWidth = Math.max(.3, pitch * .8);
      for (let index = 0; index < lines; index += 1) {
        const radius = inner + pitch * (index + grain() * .8);
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, TAU);
        ctx.strokeStyle = paint(grain() < .5 ? pal.text : pal.bg, .025 + .06 * grain());
        ctx.stroke();
      }
      if (ctx.createConicGradient) {
        // Anisotropic sheen: brushed metal throws light in long arcs.
        const sheen = ctx.createConicGradient(-Math.PI * .75, cx, cy);
        sheen.addColorStop(0, paint(pal.text, 0));
        sheen.addColorStop(.06, paint(pal.text, .42));
        sheen.addColorStop(.15, paint(pal.text, 0));
        sheen.addColorStop(.5, paint(pal.text, 0));
        sheen.addColorStop(.56, paint(pal.text, .18));
        sheen.addColorStop(.64, paint(pal.text, 0));
        sheen.addColorStop(1, paint(pal.text, 0));
        band();
        ctx.fillStyle = sheen;
        ctx.fill();
        // The bevels: the outer edge catches the light upper left; the
        // inner lip, facing the other way, catches it lower right.
        const bevel = (radius, width, lit) => {
          const edge = ctx.createConicGradient(lit - Math.PI, cx, cy);
          edge.addColorStop(0, paint(pal.bg, .6));
          edge.addColorStop(.3, paint(pal.text, .04));
          edge.addColorStop(.5, paint(pal.text, .5));
          edge.addColorStop(.7, paint(pal.text, .04));
          edge.addColorStop(1, paint(pal.bg, .6));
          ctx.beginPath();
          ctx.arc(cx, cy, radius * R, 0, TAU);
          ctx.strokeStyle = edge;
          ctx.lineWidth = width * k;
          ctx.stroke();
        };
        bevel(.955, 1.5, Math.PI * 1.25);
        bevel(.826, 2, Math.PI * .25);
      }
      g.ring(.97, .8, pal.bg, .9);
      g.ring(.8, 1.4, pal.bg, 1);
      g.ring(.812, .5, mix(pal.text, pal.bg, .35), .45);
    }

    // The glass, painted once (layer()): darker toward the rim, the faint
    // rings of the lens elements behind it, HAL's window reflections and the
    // scanlines.
    paintGlass(g) {
      const {ctx, R, cx, cy, pal} = g;
      const rim = ctx.createRadialGradient(cx, cy, .55 * R, cx, cy, .8 * R);
      rim.addColorStop(0, paint(pal.bg, 0));
      rim.addColorStop(1, paint(pal.bg, .75));
      ctx.fillStyle = rim;
      ctx.fillRect(cx - R, cy - R, 2 * R, 2 * R);
      if (R >= 20) {
        for (const [radius, alpha] of [[.34, .04], [.5, .035], [.66, .05], [.74, .03]]) {
          g.ring(radius, .6, pal.text, alpha);
        }
      }
      ctx.lineCap = 'round';
      g.arc(Math.PI * 1.08, Math.PI * 1.38, .64, .07 * R / g.k, pal.text, .16);
      g.arc(Math.PI * 1.12, Math.PI * 1.3, .52, .04 * R / g.k, pal.text, .08);
      g.arc(Math.PI * .12, Math.PI * .3, .66, .05 * R / g.k, pal.text, .07);
      ctx.lineCap = 'butt';
      const spot = ctx.createRadialGradient(cx - .34 * R, cy - .46 * R, 0, cx - .34 * R, cy - .46 * R, .09 * R);
      spot.addColorStop(0, paint(pal.text, .45));
      spot.addColorStop(1, paint(pal.text, 0));
      ctx.fillStyle = spot;
      ctx.fillRect(cx - R, cy - R, 2 * R, 2 * R);
      if (this.crt) {
        const step = Math.max(2, 2 * g.k);
        ctx.fillStyle = paint(pal.bg, .1);
        for (let y = cy - .8 * R; y < cy + .8 * R; y += step) ctx.fillRect(cx - R, y, 2 * R, step / 2);
      }
    }

    // The iris's texture: fine radial fibres round the pupil, turning slowly
    // with the galaxy, and the collarette where they start.
    drawFibres(g, gx, gy, irisRadius, tint, level) {
      const {ctx, R, k, pal} = g;
      const fibres = fibresFor(R);
      const turn = this.spin * .05;
      const color = mix(tint, pal.text, .15);
      for (let bucket = 0; bucket < 3; bucket += 1) {
        ctx.beginPath();
        for (const fibre of fibres) {
          if (fibre.bucket !== bucket) continue;
          const angle = fibre.angle + turn;
          const cos = Math.cos(angle);
          const sin = Math.sin(angle) * .95;
          ctx.moveTo(gx + cos * fibre.from * irisRadius, gy + sin * fibre.from * irisRadius);
          ctx.lineTo(gx + cos * fibre.to * irisRadius, gy + sin * fibre.to * irisRadius);
        }
        ctx.strokeStyle = paint(color, [.035, .065, .11][bucket] * level);
        ctx.lineWidth = .5 * k;
        ctx.stroke();
      }
      g.circle(gx, gy, .19 * irisRadius, .6, tint, .16 * level);
      g.circle(gx, gy, .93 * irisRadius, .5, tint, .07 * level);
    }

    // The aperture as a camera's diaphragm: seven blades closing in over the
    // iris while it thinks, their edges catching the light.
    drawDiaphragm(g, gx, gy, irisRadius, tint, level, closing) {
      const {ctx, R, pal} = g;
      if (closing < .02 || R < 20) return;
      const blades = 7;
      const outer = irisRadius * 1.06;
      const inner = irisRadius * (1 - .4 * closing);
      const turn = this.spin * .03 + closing * .7;
      const corner = (index, radius) => {
        const angle = turn + index / blades * TAU;
        return [gx + Math.cos(angle) * radius, gy + Math.sin(angle) * radius];
      };
      ctx.save();
      ctx.globalCompositeOperation = 'source-over';
      ctx.beginPath();
      ctx.arc(gx, gy, outer, 0, TAU);
      for (let index = blades; index >= 0; index -= 1) {
        const [x, y] = corner(index, inner);
        if (index === blades) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.fillStyle = paint(pal.bg, .6 * closing);
      ctx.fill('evenodd');
      ctx.globalCompositeOperation = 'lighter';
      const edge = mix(tint, pal.text, .3);
      for (let index = 0; index < blades; index += 1) {
        const [x1, y1] = corner(index, inner);
        const angle = turn + index / blades * TAU + .95;
        g.line(x1, y1, gx + Math.cos(angle) * outer * .98, gy + Math.sin(angle) * outer * .98, edge, .18 * closing * level, .5);
      }
      ctx.beginPath();
      for (let index = 0; index <= blades; index += 1) {
        const [x, y] = corner(index, inner);
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = paint(tint, .32 * closing * level);
      ctx.lineWidth = .6 * g.k;
      ctx.stroke();
      ctx.restore();
    }

    // Depth in the glass: two ghosts of the iris's light, mirrored through
    // the lens as real optics throw them, and the glow caught along the
    // glass's lower edge.
    drawGhosts(g, gx, gy, tint, level) {
      const {ctx, R, cx, cy, pal} = g;
      if (R < 20) return;
      const ox = cx - gx;
      const oy = cy - gy;
      const disc = ctx.createRadialGradient(cx + .36 * R + ox * .8, cy + .42 * R + oy * .8, 0,
        cx + .36 * R + ox * .8, cy + .42 * R + oy * .8, .06 * R);
      disc.addColorStop(0, paint(tint, .1 * level));
      disc.addColorStop(1, paint(tint, 0));
      ctx.fillStyle = disc;
      ctx.fillRect(cx - R, cy - R, 2 * R, 2 * R);
      g.circle(cx + .2 * R + ox * .4, cy + .24 * R + oy * .4, .11 * R, .6, tint, .06 * level);
      ctx.lineCap = 'round';
      g.arc(-Math.PI * .1, Math.PI * .55, .785, 1.3, mix(tint, pal.text, .2), .22 * level);
      ctx.lineCap = 'butt';
    }

    drawGalaxy(g, gx, gy, tint, level, now) {
      const {ctx, R, k, pal} = g;
      const twinkle = now / 900;
      for (const star of galaxyFor(R)) {
        // Inner stars turn faster, so the arms wind like a real spiral.
        const angle = star.angle + this.spin * (1.2 / (.35 + star.radius));
        const x = gx + Math.cos(angle) * star.radius * R;
        const y = gy + Math.sin(angle) * star.radius * R * .9;
        const alpha = star.bright * level * .75 * (.7 + .3 * Math.sin(twinkle + star.twinkle));
        ctx.fillStyle = paint(mix(pal.text, tint, .35 + .5 * star.along), alpha);
        ctx.beginPath();
        ctx.arc(x, y, Math.max(.25, star.size * k * .55), 0, TAU);
        ctx.fill();
      }
    }

    drawMotes(g, now) {
      const {R, pal} = g;
      for (const mote of this.motes) {
        const q = (now - mote.start) / mote.ms;
        if (q <= 0 || q >= 1) continue;
        const color = mix(this.color(mote.tone), pal.text, .25);
        const alpha = Math.min(1, q * 4) * (1 - q * .3) * (mote.dream ? .35 : 1);
        for (let trail = 2; trail >= 0; trail -= 1) {
          const t = Math.max(0, q - trail * .04);
          const [x, y] = g.polar(mote.angle + mote.twist * t, .76 * R * (1 - easeIn(t)));
          g.dot(x, y, mote.size * (1 - .5 * t) * (trail ? .7 : 1), color, alpha * (trail ? .35 / trail : 1));
        }
      }
    }

    drawCore(g, gx, gy, tint, level, breath, flare, mods) {
      const {ctx, R, pal} = g;
      const pupil = mods.pupil * (this.asleep ? .6 : 1);
      const core = (.075 + .025 * this.arousal + .02 * breath) * R * pupil;
      const halo = core * (3.2 + 2 * flare);
      const glow = ctx.createRadialGradient(gx, gy, 0, gx, gy, halo);
      glow.addColorStop(0, paint(mix(pal.text, tint, .25), .9 * level));
      glow.addColorStop(.35, paint(tint, .45 * level * (1 + flare)));
      glow.addColorStop(1, paint(tint, 0));
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(gx, gy, halo, 0, TAU);
      ctx.fill();
      // A wider bloom, and the faint horizontal streak a lens throws from a
      // bright point (stronger as it flares or speaks).
      const bloom = ctx.createRadialGradient(gx, gy, 0, gx, gy, halo * 2.2);
      bloom.addColorStop(0, paint(tint, .12 * level));
      bloom.addColorStop(1, paint(tint, 0));
      ctx.fillStyle = bloom;
      ctx.beginPath();
      ctx.arc(gx, gy, halo * 2.2, 0, TAU);
      ctx.fill();
      if (R >= 20) {
        const length = R * (.32 + .3 * Math.min(1, flare));
        ctx.save();
        ctx.translate(gx, gy);
        ctx.scale(1, .04 + .02 * Math.min(1, flare));
        const streak = ctx.createRadialGradient(0, 0, 0, 0, 0, length);
        streak.addColorStop(0, paint(mix(pal.text, tint, .3), (.1 + .3 * Math.min(1, flare)) * level));
        streak.addColorStop(1, paint(tint, 0));
        ctx.fillStyle = streak;
        ctx.beginPath();
        ctx.arc(0, 0, length, 0, TAU);
        ctx.fill();
        ctx.restore();
      }
      g.dot(gx, gy, core / g.k, mix(pal.text, tint, .15), Math.min(1, level * (1 + .5 * flare)));
      const spikes = mods.spikes;
      if (spikes > 0) {
        const length = R * (.12 + .45 * spikes);
        const turn = this.spin * .2;
        for (let arm = 0; arm < 4; arm += 1) {
          const angle = turn + arm * Math.PI / 2;
          g.line(gx - Math.cos(angle) * length, gy - Math.sin(angle) * length,
            gx + Math.cos(angle) * length, gy + Math.sin(angle) * length,
            mix(pal.text, tint, .3), .6 * spikes * level, .7);
        }
      }
    }

    // The lids: shadow falling over the lens, not a plate across it. They
    // hood the eye when it's tired or depressed, squint while scooping,
    // tilt for a side-eye, and lift from below in a smile.
    drawLids(g, pose) {
      const lid = clamp(pose.lid);
      const lowerLid = clamp(pose.lidLower ?? pose.lid);
      if (lid <= .01 && lowerLid <= .01) return;
      const {ctx, R, cx, cy, pal} = g;
      const reach = .8 * R;
      const feather = .1 * R;
      const tilt = (pose.tilt || 0) * reach * lid;
      // The edge curves with the eye, as an eyelid's does (a flat edge read
      // as a line drawn across the lens).
      const sag = (lid) => reach * (.2 + .45 * lid);
      if (lid > .01) {
        // Upper lid: dark at the top, softening toward its edge, which
        // comes down to the centre when shut.
        const top = cy - reach + lid * reach - sag(lid) * .5;
        const shade = ctx.createLinearGradient(0, cy - R, 0, top + feather);
        shade.addColorStop(0, paint(pal.bg, .97));
        shade.addColorStop(Math.max(0, Math.min(1, (top - (cy - R)) / (top + feather - (cy - R)))), paint(pal.bg, .88));
        shade.addColorStop(1, paint(pal.bg, 0));
        ctx.beginPath();
        ctx.moveTo(cx - R, cy - R);
        ctx.lineTo(cx + R, cy - R);
        ctx.lineTo(cx + R, top + tilt + feather);
        ctx.quadraticCurveTo(cx, top + sag(lid) + feather, cx - R, top - tilt + feather);
        ctx.closePath();
        ctx.fillStyle = shade;
        ctx.fill();
      }
      if (lowerLid > .01) {
        // Lower lid: it rises to meet it (more than the upper one in a smile).
        const bottom = cy + reach - lowerLid * reach + sag(lowerLid) * .5;
        const shade = ctx.createLinearGradient(0, cy + R, 0, bottom - feather);
        shade.addColorStop(0, paint(pal.bg, .97));
        shade.addColorStop(Math.max(0, Math.min(1, ((cy + R) - bottom) / ((cy + R) - (bottom - feather)))), paint(pal.bg, .88));
        shade.addColorStop(1, paint(pal.bg, 0));
        ctx.beginPath();
        ctx.moveTo(cx - R, cy + R);
        ctx.lineTo(cx + R, cy + R);
        ctx.lineTo(cx + R, bottom + tilt * .4 - feather);
        ctx.quadraticCurveTo(cx, bottom - sag(lowerLid) - feather, cx - R, bottom - tilt * .4 - feather);
        ctx.closePath();
        ctx.fillStyle = shade;
        ctx.fill();
      }
    }

    // Light sweeping across the glass, upper left to lower right.
    drawGlint(g, position) {
      const {ctx, R, cx, cy, pal} = g;
      const offset = (position * 2.4 - 1.2) * R;
      const band = ctx.createLinearGradient(cx + offset - .25 * R, cy - .25 * R, cx + offset + .25 * R, cy + .25 * R);
      band.addColorStop(0, paint(pal.text, 0));
      band.addColorStop(.5, paint(pal.text, .12 * Math.sin(Math.PI * position)));
      band.addColorStop(1, paint(pal.text, 0));
      ctx.fillStyle = band;
      ctx.fillRect(cx - R, cy - R, 2 * R, 2 * R);
    }

    // What the orb is doing, for tests and diagnostics.
    state() {
      return {
        running: this.running,
        effects: this.effects.map((effect) => effect.name),
        motes: this.motes.length,
        blips: this.blips.length,
        tint: this.pal ? hex(this.tint()) : '',
        base: this.pal ? hex(this.base()) : '',
        arousal: this.arousal,
        asleep: this.asleep,
        stalled: this.stalled,
        lastSeq: this.lastSeq,
        lastEvent: this.lastEvent,
        frames: this.frames,
        size: this.size,
        pose: this.pose ? {...this.pose} : null,
        music: {level: this.musicLevel, bass: this.musicBass},
        life: this.life ? this.life.state(performance.now()) : null,
      };
    }

    dispose() {
      this.running = false;
      cancelAnimationFrame(this.raf);
      document.removeEventListener('visibilitychange', this.onVisibility);
      this.observer?.disconnect();
    }
  }

  HeartbeatOrb.EFFECTS = Object.freeze(Object.keys(EFFECTS));
  window.HeartbeatOrb = HeartbeatOrb;
})();
