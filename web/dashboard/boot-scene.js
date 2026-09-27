/*
 * Boot scene: the watcher wakes
 * -----------------------------
 * The flight computer starts under the same HAL-style eye that watches the
 * journal in the heartbeat overlay (web/assets/heartbeat-orb.js). It sits in
 * the core of a galaxy seen edge-on, and the window drifts slowly toward it.
 *
 * Everything that reads as progress is real. The ring and the four systems
 * follow the backend's boot progress, each status the backend reports is
 * written to the flight computer log with its time, and the orb takes in the
 * journal events as they are actually restored, one mote per batch. The
 * orb's other reactions, the sky and the distant jump flashes are
 * decoration.
 *
 * When the deck is ready the backend holds the boot screen for five seconds.
 * That hold becomes an FSD countdown, and the screen jumps into the deck:
 * the drifting stars stretch into hyperspace streaks from the eye as the
 * boot screen fades. app.js (renderBoot) owns the timing and the handoff;
 * this module only listens to its `voidcompass:boot` announcements.
 *
 * Nothing animates under reduced motion; the sky is painted once and the
 * orb paints still frames. Everything stops once the deck is up.
 */
import {BOOT_FACTS} from './boot-facts.js';

const TAU = Math.PI * 2;
const FRAME_MS = 1000 / 30;
const FACT_INTERVAL_MS = 6500;
const RELEASE_INTERVAL_MS = 8000;
const LOG_LINES = 6;
// The five-second hold counts down from 4, as the ship's FSD does.
const COUNTDOWN_FROM_MS = 4000;
// The streaks start just before the deck appears and carry through its fade.
const JUMP_LEAD_MS = 650;
const CRUISE_SPEED = .016;
const JUMP_SPEED = 2.6;

// The backend's boot statuses and how the watcher reacts to each. Any other
// status still gets a plain pulse.
const STATUS_REACTIONS = {
  'INITIALISING FLIGHT COMPUTER': ['accent', 'pulse', .5],
  'FIRST COMMISSIONING': ['accent', 'pulse', .5],
  'PROFILE VAULT COMMISSIONED': ['green', 'clear', .7],
  'BUILDING DASHBOARD CORE': ['accent', 'charge', .7],
  'RESTORING JOURNAL HISTORY': ['orange', 'gather', .7],
  'INDEXING PAST JOURNALS': ['yellow', 'sweep', .6],
  'HISTORICAL INDEX READY': ['green', 'complete', .75],
  'RESTORING RECENT JOURNAL': ['orange', 'gather', .55],
  'LIVE JOURNAL TAIL REACHED': ['accent', 'honk', .85],
  'JOURNAL LINK OFFLINE': ['muted', 'deny', .6],
  'LIVE STATE READY': ['green', 'clear', .7],
  'VOID COMPASS LIVE': ['green', 'glint', .9],
};

const $ = (id) => document.getElementById(id);
const boot = $('boot');
const loader = $('boot-loader');
const body = document.body;
const motion = matchMedia('(prefers-reduced-motion: reduce)');
const reduced = () => motion.matches || body.classList.contains('reduced-motion');
// On screen, including the fade into the deck.
const presented = () => !boot.hidden && !loader.hidden && !document.hidden;
// Still starting up, before the deck takes over.
const starting = () => presented() && !body.classList.contains('ready');

const clamp = (value, low = 0, high = 1) => Math.max(low, Math.min(high, value));
const lerp = (from, to, t) => from + (to - from) * t;

function random(seed) {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function rgb(value) {
  const match = /^#?([0-9a-f]{6})$/i.exec(String(value || '').trim());
  if (!match) return null;
  const number = parseInt(match[1], 16);
  return [(number >> 16) & 255, (number >> 8) & 255, number & 255];
}

const mix = (a, b, t) => a.map((part, index) => lerp(part, b[index], t));
const paint = (color, alpha = 1) =>
  `rgba(${Math.round(color[0])},${Math.round(color[1])},${Math.round(color[2])},${clamp(alpha)})`;

// The dashboard theme's colours; the sky has none of its own.
function themeColors() {
  const style = getComputedStyle(document.documentElement);
  const read = (name) => rgb(style.getPropertyValue(`--${name}`));
  const colors = {};
  for (const name of ['bg', 'text', 'muted', 'accent', 'orange', 'yellow', 'green', 'red']) colors[name] = read(name);
  colors.bg ||= [0, 0, 0];
  colors.text ||= [255, 255, 255];
  for (const name of ['muted', 'accent', 'orange', 'yellow', 'green', 'red']) colors[name] ||= colors.text;
  return colors;
}

function formatClock(ms) {
  const seconds = Math.max(0, ms) / 1000;
  const minutes = Math.floor(seconds / 60);
  return `T+${String(minutes).padStart(2, '0')}:${(seconds % 60).toFixed(1).padStart(4, '0')}`;
}

/*
 * The sky. A still layer (the galaxy, painted once per size or theme) and a
 * drift layer: nearby stars in perspective, flying slowly toward the eye,
 * which is the vanishing point. The jump is the same flight, much faster.
 */
class Sky {
  constructor(still, drift) {
    this.still = still;
    this.drift = drift;
    this.stillContext = still.getContext('2d');
    this.driftContext = drift.getContext('2d');
    this.width = 0;
    this.height = 0;
    this.ratio = 1;
    this.vanish = [.3, .5];
    this.colors = null;
    this.paletteKey = '';
    this.next = random(4242);
    this.stars = Array.from({length: 240}, () => this.spawn(true));
    this.flashes = [];
    this.nextFlashAt = 0;
    this.warp = 0;
    this.jumping = false;
    this.running = false;
    this.raf = 0;
    this.last = 0;
    this.draws = 0;
    this.loop = this.loop.bind(this);
  }

  spawn(anywhere = false) {
    const next = this.next;
    return {
      x: (next() * 2 - 1) * 1.6,
      y: (next() * 2 - 1) * 1.1,
      z: anywhere ? .08 + next() * .92 : .85 + next() * .15,
      size: .45 + next() ** 3 * 1.5,
      bright: .35 + next() * .65,
      tint: next(),
    };
  }

  resize(vanish) {
    const box = boot.getBoundingClientRect();
    const width = Math.max(1, Math.round(box.width));
    const height = Math.max(1, Math.round(box.height));
    const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
    this.vanish = vanish;
    const colors = themeColors();
    const paletteKey = JSON.stringify(colors);
    const changed = width !== this.width || height !== this.height || ratio !== this.ratio
      || paletteKey !== this.paletteKey || vanish.join() !== this.vanishKey;
    this.width = width;
    this.height = height;
    this.ratio = ratio;
    this.colors = colors;
    this.paletteKey = paletteKey;
    this.vanishKey = vanish.join();
    for (const canvas of [this.still, this.drift]) {
      const w = Math.round(width * ratio);
      const h = Math.round(height * ratio);
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
    }
    if (changed) this.paintStill();
    this.paintDrift(0);
  }

  // A soft elliptical glow along the galaxy's plane.
  glow(ctx, x, y, rx, ry, color, alpha) {
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(1, ry / rx);
    const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, rx);
    gradient.addColorStop(0, paint(color, alpha));
    gradient.addColorStop(.45, paint(color, alpha * .45));
    gradient.addColorStop(1, paint(color, 0));
    ctx.fillStyle = gradient;
    ctx.fillRect(-rx, -rx, rx * 2, rx * 2);
    ctx.restore();
  }

  paintStill() {
    const ctx = this.stillContext;
    const {width: W, height: H, colors: c} = this;
    ctx.setTransform(this.ratio, 0, 0, this.ratio, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const next = random(1291);
    const diagonal = Math.hypot(W, H);
    const cx = this.vanish[0] * W;
    const cy = this.vanish[1] * H;
    const gauss = () => (next() + next() + next() + next() - 2) * 1.2;

    // Distant nebulae, very faint, in the theme's own colours.
    this.glow(ctx, W * .82, H * .16, diagonal * .34, diagonal * .22, c.accent, .07);
    this.glow(ctx, W * .08, H * .9, diagonal * .3, diagonal * .18, c.orange, .05);
    this.glow(ctx, W * .66, H * .98, diagonal * .24, diagonal * .12, c.red, .035);

    // The galaxy edge-on, rising left to right through the eye.
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(-.34);
    const band = mix(c.text, c.accent, .35);
    for (let index = 0; index < 18; index += 1) {
      const t = (index / 17 - .5) * diagonal * 1.15;
      const r = diagonal * (.08 + .05 * next());
      this.glow(ctx, t, (next() - .5) * diagonal * .02, r * 1.7, r * .38, band, .045 + .03 * next());
    }
    // Its core, warm, sits right behind the eye.
    this.glow(ctx, 0, 0, diagonal * .24, diagonal * .085, mix(c.orange, c.yellow, .5), .13);
    this.glow(ctx, 0, 0, diagonal * .1, diagonal * .045, mix(c.yellow, c.text, .5), .12);
    const count = Math.round(clamp(W * H / 330, 1800, 7000));
    for (let index = 0; index < count; index += 1) {
      const t = (next() - .5) * diagonal * 1.2;
      const spread = diagonal * .045 * (1 + 1.5 * Math.abs(t) / diagonal) * (1 + .9 * Math.exp(-((t / (diagonal * .12)) ** 2)));
      const y = gauss() * spread;
      const roll = next();
      const color = roll < .07 ? c.accent : roll < .11 ? c.orange : roll < .13 ? c.yellow : c.text;
      const radius = .25 + next() ** 4 * .9;
      ctx.fillStyle = paint(color, .12 + next() * .55);
      if (radius < .6) ctx.fillRect(t, y, radius * 1.6, radius * 1.6);
      else {
        ctx.beginPath();
        ctx.arc(t, y, radius, 0, TAU);
        ctx.fill();
      }
    }
    // Dust lanes break the band just below its centre line.
    for (let index = 0; index < 11; index += 1) {
      const t = (next() - .5) * diagonal * 1.05;
      const rx = diagonal * (.05 + .07 * next());
      this.glow(ctx, t, diagonal * (.004 + .012 * next()), rx, rx * (.1 + .06 * next()), c.bg, .5 + .2 * next());
    }
    ctx.restore();

    // The field beyond the band, with a few bright stars and their spikes.
    const field = Math.round(clamp(W * H / 1600, 400, 1500));
    for (let index = 0; index < field; index += 1) {
      const x = next() * W;
      const y = next() * H;
      const radius = .25 + next() ** 5 * 1.1;
      ctx.fillStyle = paint(next() < .06 ? c.accent : c.text, .1 + next() * .5);
      ctx.fillRect(x, y, radius * 1.6, radius * 1.6);
    }
    for (let index = 0; index < 9; index += 1) {
      const x = next() * W;
      const y = next() * H;
      const color = next() < .3 ? mix(c.text, c.accent, .5) : c.text;
      const length = 3 + next() * 4;
      this.glow(ctx, x, y, length * 1.6, length * 1.6, color, .16);
      // Spikes fade from the star, as a lens renders them.
      for (const [dx, dy] of [[1, 0], [0, 1]]) {
        const spike = ctx.createLinearGradient(x - dx * length, y - dy * length, x + dx * length, y + dy * length);
        spike.addColorStop(0, paint(color, 0));
        spike.addColorStop(.5, paint(color, .5));
        spike.addColorStop(1, paint(color, 0));
        ctx.fillStyle = spike;
        ctx.fillRect(x - dx * length - dy * .3, y - dy * length - dx * .3, dx * length * 2 + dy * .6, dy * length * 2 + dx * .6);
      }
      ctx.fillStyle = paint(color, .9);
      ctx.beginPath();
      ctx.arc(x, y, .9, 0, TAU);
      ctx.fill();
    }

    // The edges fall away so the eye and the deck's type carry the frame.
    const vignette = ctx.createRadialGradient(W * .45, H * .5, Math.min(W, H) * .35, W * .45, H * .5, diagonal * .62);
    vignette.addColorStop(0, paint(c.bg, 0));
    vignette.addColorStop(1, paint(c.bg, .72));
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, W, H);
  }

  // Where a star at (x, y, z) lands on screen, looking at the eye.
  project(star, z) {
    const focal = Math.max(this.width, this.height) * .18;
    return [this.vanish[0] * this.width + star.x / z * focal, this.vanish[1] * this.height + star.y / z * focal];
  }

  paintDrift(elapsed) {
    const ctx = this.driftContext;
    const {width: W, height: H, colors: c} = this;
    ctx.setTransform(this.ratio, 0, 0, this.ratio, 0, 0);
    ctx.clearRect(0, 0, W, H);
    if (!c) return;
    const speed = lerp(CRUISE_SPEED, JUMP_SPEED, this.warp ** 2);
    const seconds = elapsed / 1000;
    ctx.lineCap = 'round';
    for (let index = 0; index < this.stars.length; index += 1) {
      let star = this.stars[index];
      star.z -= speed * seconds;
      let [x, y] = this.project(star, Math.max(.02, star.z));
      if (star.z <= .02 || x < -40 || x > W + 40 || y < -40 || y > H + 40) {
        star = this.stars[index] = this.spawn(false);
        [x, y] = this.project(star, star.z);
      }
      const alpha = clamp((1 - star.z) * 1.6) * star.bright * (1 - .35 * this.warp);
      const color = star.tint < .12 ? mix(c.text, c.accent, .6) : star.tint < .16 ? mix(c.text, c.orange, .5) : c.text;
      const size = star.size * (1.25 - star.z * .8);
      if (this.warp > .04) {
        const trail = Math.min(star.z + speed * (.05 + .5 * this.warp), 1.2);
        const [tx, ty] = this.project(star, trail);
        ctx.strokeStyle = paint(mix(color, c.accent, .35 * this.warp), alpha);
        ctx.lineWidth = Math.max(.6, size);
        ctx.beginPath();
        ctx.moveTo(tx, ty);
        ctx.lineTo(x, y);
        ctx.stroke();
      } else {
        ctx.fillStyle = paint(color, alpha);
        ctx.beginPath();
        ctx.arc(x, y, size, 0, TAU);
        ctx.fill();
      }
    }
    // Now and then a ship jumps out somewhere far off.
    for (const flash of this.flashes) {
      const q = (this.clock - flash.start) / 900;
      if (q < 0 || q > 1) continue;
      const alpha = Math.sin(Math.PI * q) * .8;
      const length = 3 + 16 * q;
      const color = mix(c.text, c.accent, .5);
      ctx.fillStyle = paint(color, alpha);
      ctx.fillRect(flash.x - length, flash.y - .5, length * 2, 1);
      ctx.fillRect(flash.x - .5, flash.y - length * .45, 1, length * .9);
      this.glow(ctx, flash.x, flash.y, 7, 7, color, alpha * .6);
    }
    this.draws += 1;
  }

  loop(now) {
    if (!this.running) return;
    this.raf = requestAnimationFrame(this.loop);
    if (this.last && now - this.last < FRAME_MS - 2) return;
    const elapsed = this.last ? Math.min(100, now - this.last) : 0;
    this.last = now;
    this.clock = now;
    this.warp += ((this.jumping ? 1 : 0) - this.warp) * Math.min(1, elapsed / 700);
    if (!this.jumping && now >= this.nextFlashAt) {
      if (this.nextFlashAt) {
        this.flashes = this.flashes.filter((flash) => now - flash.start < 900);
        this.flashes.push({start: now, x: this.next() * this.width, y: this.next() * this.height});
      }
      this.nextFlashAt = now + 4000 + this.next() * 5000;
    }
    this.paintDrift(elapsed);
  }

  start() {
    if (this.running) return;
    this.running = true;
    this.last = 0;
    this.raf = requestAnimationFrame(this.loop);
  }

  stop() {
    this.running = false;
    cancelAnimationFrame(this.raf);
  }

  jump(on) {
    this.jumping = Boolean(on);
    if (!on) this.warp = 0;
  }
}

const sky = new Sky($('boot-sky'), $('boot-drift'));
const orbCanvas = $('boot-orb');
const orb = window.HeartbeatOrb ? new window.HeartbeatOrb(orbCanvas) : null;
let orbSeq = 0;
const orbEvents = [];

function tellOrb(event, tone, effect, weight) {
  orbEvents.push({seq: ++orbSeq, event, tone, effect, weight});
  if (orbEvents.length > 24) orbEvents.shift();
}

function feedOrb() {
  orb?.update({
    palette: {}, eye: 'theme', crt: false, reducedMotion: reduced(),
    stalled: false, events: orbEvents, statusSeq: 0,
  });
}

// The eye opens as the page does.
feedOrb();

// Stage markers round the progress ring, from the same markup renderBoot reads.
const ringStages = $('boot-ring-stages');
const stageItems = [...document.querySelectorAll('.boot-sequence > [data-boot-stage]')];
const SVG = 'http://www.w3.org/2000/svg';
const markers = stageItems.map((item) => {
  const angle = Number(item.dataset.bootThreshold || 0) * TAU - Math.PI / 2;
  const group = document.createElementNS(SVG, 'g');
  group.dataset.ringStage = item.dataset.bootStage;
  const mark = document.createElementNS(SVG, 'rect');
  mark.setAttribute('x', String(200 + Math.cos(angle) * 194 - 3.5));
  mark.setAttribute('y', String(200 + Math.sin(angle) * 194 - 3.5));
  mark.setAttribute('width', '7');
  mark.setAttribute('height', '7');
  mark.setAttribute('transform', `rotate(45 ${200 + Math.cos(angle) * 194} ${200 + Math.sin(angle) * 194})`);
  const label = document.createElementNS(SVG, 'text');
  const lx = 200 + Math.cos(angle) * 216;
  const ly = 200 + Math.sin(angle) * 216;
  label.setAttribute('x', String(lx));
  label.setAttribute('y', String(ly + 3));
  label.setAttribute('text-anchor', Math.cos(angle) > .25 ? 'start' : Math.cos(angle) < -.25 ? 'end' : 'middle');
  label.textContent = (item.dataset.bootLabel || item.dataset.bootStage).split(' ')[0];
  group.append(mark, label);
  ringStages.append(group);
  return {item, group};
});

function syncMarkers() {
  for (const {item, group} of markers) {
    group.classList.toggle('ready', item.classList.contains('ready'));
    group.classList.toggle('active', item.classList.contains('active'));
  }
}

// Flight computer log: every status the backend reports, with its time.
const logList = $('boot-log');
const clock = $('boot-clock');
const log = [];

function logStatus(status, detail) {
  if (!status) return;
  const last = log[log.length - 1];
  if (last && last.status === status) {
    last.detail = detail;
  } else {
    log.push({at: performance.now(), status, detail});
    if (log.length > 40) log.shift();
  }
  const rows = log.slice(-LOG_LINES).map((entry, index, shown) => {
    const row = document.createElement('li');
    row.classList.toggle('current', index === shown.length - 1);
    const time = document.createElement('time');
    time.textContent = formatClock(entry.at);
    const title = document.createElement('b');
    title.textContent = entry.status;
    const note = document.createElement('span');
    note.textContent = entry.detail || '';
    row.append(time, title, note);
    return row;
  });
  logList.replaceChildren(...rows);
}
logStatus($('boot-status').textContent.trim(), $('boot-detail').textContent.trim());

// Field notes, spoken by the watcher.
const fact = $('boot-fact');
const transmission = document.querySelector('.boot-transmission');
let deck = [];
let lastFactId = '';
let voiceTimer = 0;

function nextFact() {
  if (!starting() || !BOOT_FACTS.length) return;
  if (!deck.length) {
    deck = [...BOOT_FACTS];
    for (let i = deck.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [deck[i], deck[j]] = [deck[j], deck[i]];
    }
    if (deck.length > 1 && deck.at(-1).id === lastFactId) [deck[0], deck[deck.length - 1]] = [deck.at(-1), deck[0]];
  }
  const note = deck.pop();
  fact.textContent = note.text;
  fact.dataset.factId = note.id;
  lastFactId = note.id;
  transmission.classList.remove('speaking');
  void transmission.offsetWidth;
  transmission.classList.add('speaking');
  clearTimeout(voiceTimer);
  voiceTimer = setTimeout(() => transmission.classList.remove('speaking'), 1800);
  tellOrb('FIELD NOTE', 'accent', 'speak', .5);
  feedOrb();
}

// What is new in this release, one change at a time.
const release = {notes: [], index: 0, key: ''};

function showRelease(announcement) {
  const info = announcement.release;
  const version = announcement.version || info?.version || '';
  const notes = Array.isArray(info?.notes) ? info.notes.filter(Boolean) : [];
  const key = JSON.stringify([version, info?.title, notes]);
  if (key === release.key) return;
  release.key = key;
  release.notes = notes;
  release.index = 0;
  const line = $('boot-release-line');
  if (info?.title) {
    line.textContent = [`V${version}`, info.title, info.date].filter(Boolean).join(' // ').toUpperCase();
  } else if (version) {
    line.textContent = `V${version} // LOCAL-FIRST EXPLORATION COMPANION`;
  }
  $('boot-release').hidden = !notes.length;
  $('boot-release-version').textContent = version ? `V${version}` : 'THIS RELEASE';
  paintReleaseNote();
}

function paintReleaseNote() {
  if (!release.notes.length) return;
  const note = $('boot-release-note');
  note.textContent = release.notes[release.index % release.notes.length];
  $('boot-release-page').textContent = `${release.index % release.notes.length + 1} / ${release.notes.length}`;
  const card = $('boot-release');
  card.classList.remove('turning');
  void card.offsetWidth;
  card.classList.add('turning');
}

function nextReleaseNote() {
  if (!starting() || release.notes.length < 2) return;
  release.index += 1;
  paintReleaseNote();
}

// The handoff countdown and jump.
const operation = document.querySelector('.boot-operation');
const countdown = $('boot-countdown');
let handoffAt = 0;
let lastCount = 0;
let jumped = false;

function tickCountdown() {
  if (!handoffAt) return;
  const remaining = handoffAt - performance.now();
  const counting = remaining <= COUNTDOWN_FROM_MS;
  countdown.hidden = !counting;
  operation.classList.toggle('counting', counting);
  if (!counting) return;
  const count = Math.max(0, Math.ceil(remaining / 1000));
  if (count !== lastCount) {
    lastCount = count;
    countdown.querySelector('b').textContent = count ? String(count) : 'JUMP';
    countdown.classList.remove('tick');
    void countdown.offsetWidth;
    countdown.classList.add('tick');
    if (count) {
      tellOrb('FSD CHARGE', 'accent', 'charge', .8);
      feedOrb();
    }
  }
  if (!jumped && remaining <= JUMP_LEAD_MS) {
    jumped = true;
    logStatus('FRAME SHIFT ENGAGED', 'Handing over to the command deck');
    if (!reduced()) {
      boot.classList.add('jumping');
      sky.jump(true);
      tellOrb('JUMP', 'accent', 'warp', 1);
      feedOrb();
    }
  }
}

function resetHandoff() {
  handoffAt = 0;
  lastCount = 0;
  jumped = false;
  countdown.hidden = true;
  operation.classList.remove('counting');
  boot.classList.remove('jumping');
  sky.jump(false);
}

// Timers and clocks run only while the boot screen is starting up.
let factTimer = 0;
let releaseTimer = 0;
let clockTimer = 0;
let lastEvents = 0;
let lastStatus = '';
let lastDetail = '';

function vanishingPoint() {
  const box = boot.getBoundingClientRect();
  const eye = orbCanvas.getBoundingClientRect();
  if (!box.width || !box.height || !eye.width) return [.3, .45];
  const point = [
    clamp((eye.left + eye.width / 2 - box.left) / box.width),
    clamp((eye.top + eye.height / 2 - box.top) / box.height),
  ];
  boot.style.setProperty('--vanish-x', `${(point[0] * 100).toFixed(2)}%`);
  boot.style.setProperty('--vanish-y', `${(point[1] * 100).toFixed(2)}%`);
  return point;
}

function sync() {
  const on = presented();
  const animate = on && !reduced();
  orb?.setSuspended(!on);
  // Carries a changed reduced-motion preference to the watcher.
  if (on) feedOrb();
  // First-run commissioning shares the boot screen: its form sits on the
  // same galaxy, held still.
  if (!boot.hidden && !document.hidden) sky.resize(vanishingPoint());
  if (animate) sky.start();
  else sky.stop();
  if (starting()) {
    if (!factTimer) {
      if (!fact.textContent) nextFact();
      factTimer = setInterval(nextFact, FACT_INTERVAL_MS);
    }
    releaseTimer ||= setInterval(nextReleaseNote, RELEASE_INTERVAL_MS);
    clockTimer ||= setInterval(() => {
      clock.textContent = formatClock(performance.now());
      tickCountdown();
    }, 100);
  } else {
    clearInterval(factTimer);
    clearInterval(releaseTimer);
    clearTimeout(voiceTimer);
    factTimer = releaseTimer = 0;
    transmission.classList.remove('speaking');
    // The countdown keeps ticking through the fade so the jump completes.
    if (!on) {
      clearInterval(clockTimer);
      clockTimer = 0;
    }
  }
}

window.addEventListener('voidcompass:boot', (event) => {
  const announcement = event.detail || {};
  if (announcement.commissioning) {
    resetHandoff();
    sync();
    return;
  }
  syncMarkers();
  showRelease(announcement);
  const events = Number(announcement.events) || 0;
  const status = announcement.handoffAt ? 'FLIGHT DECK READY' : announcement.status;
  const detail = announcement.handoffAt ? 'Stand by for live handoff' : announcement.detail;
  if (status && status !== lastStatus) {
    const [tone, effect, weight] = announcement.handoffAt
      ? ['green', 'complete', .8]
      : STATUS_REACTIONS[status] || ['accent', 'pulse', .4];
    tellOrb(status, tone, effect, weight);
  }
  if (events > lastEvents) {
    // One mote per slice of the restored journal: the eye takes it in.
    const motes = clamp(Math.ceil(Math.sqrt(events - lastEvents)), 1, 14);
    for (let index = 0; index < motes; index += 1) tellOrb('JOURNAL', 'orange', 'tick', .12);
    $('boot-events').textContent = `${events.toLocaleString()} events restored`;
  }
  if (status !== lastStatus || events !== lastEvents) feedOrb();
  if (status !== lastStatus || detail !== lastDetail) logStatus(status, detail);
  lastEvents = Math.max(lastEvents, events);
  lastStatus = status;
  lastDetail = detail;
  if (announcement.handoffAt) {
    handoffAt = announcement.handoffAt;
    tickCountdown();
  } else if (announcement.active && handoffAt) {
    resetHandoff();
  }
  sync();
});

const observer = new MutationObserver(sync);
for (const node of [boot, loader, body]) observer.observe(node, {attributes: true, attributeFilter: ['hidden', 'class']});
const resize = new ResizeObserver(() => { if (presented()) sky.resize(vanishingPoint()); });
resize.observe(boot);
document.addEventListener('visibilitychange', sync);
motion.addEventListener('change', sync);
window.addEventListener('pagehide', () => {
  sky.stop();
  orb?.dispose();
  clearInterval(factTimer);
  clearInterval(releaseTimer);
  clearInterval(clockTimer);
  clearTimeout(voiceTimer);
  observer.disconnect();
  resize.disconnect();
  document.removeEventListener('visibilitychange', sync);
  motion.removeEventListener('change', sync);
}, {once: true});
sync();

// What the boot scene is doing, for tests and diagnostics.
window.bootScene = Object.freeze({
  state: () => ({
    running: sky.running,
    draws: sky.draws,
    warp: sky.warp,
    jumped,
    counting: !countdown.hidden,
    count: countdown.querySelector('b').textContent,
    log: log.map((entry) => entry.status),
    orb: orb?.state() || null,
    factInterval: FACT_INTERVAL_MS,
  }),
});
