// The Flight Recorder (5.5.10): any past session played again on the
// Atlas. Python gives the tape (exploration/flight_recorder.py): every
// arrival, every moment and every track on one clock; this plays it at any
// speed, draws the trail as it goes, pops the moments up where they
// happened, and can play the session's music again.

const SPEEDS = [[60, '1 MIN / S'], [300, '5 MIN / S'], [900, '15 MIN / S'], [3600, '1 HOUR / S']];
const JUMP_S = 15;          // a jump's last seconds: the ship crossing the gap
const POP_MS = 4200;        // how long a moment stays on the map
const MOMENTS = {
  first: ['⚑', 'First discovery'], footfall: ['⬩', 'First footfall'], rare: ['✦', 'Rare world'], valuable: ['◆', 'Valuable world'],
  codex: ['⬡', 'Codex'], bio: ['❦', 'Organics'], survey: ['◎', 'Survey'], sale: ['¤', 'Sale'], loss: ['✖', 'Ship lost'],
  photo: ['▣', 'Picture'], postcard: ['✉', 'Postcard'], material: ['◇', 'Material'], data: ['≋', 'Data'], note: ['✎', 'Note'],
  debrief: ['■', 'Session end'], find: ['•', 'Find'],
};

export function createRecorder(env) {
  const $ = env.$;
  const escape = env.escape;
  const state = {tape: null, clock: 0, playing: false, speed: 300, skipQuiet: true, music: false, follow: true,
    last: 0, popped: new Map(), sessions: null, loading: false, lastFollow: 0, musicQueued: false, seenRequest: 0};

  const clockText = (seconds) => {
    const total = Math.max(0, Math.round(seconds));
    const h = Math.floor(total / 3600), m = Math.floor(total % 3600 / 60), s = total % 60;
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };
  const wallTime = (seconds) => {
    if (!state.tape) return '';
    const at = new Date((state.tape.start_epoch + seconds) * 1000);
    return at.toLocaleTimeString(undefined, {hour: '2-digit', minute: '2-digit'});
  };

  // -- the sessions to choose from ---------------------------------------------------------
  async function listSessions(force = false) {
    if (state.sessions && !force) return renderSessions();
    $('recorder-sessions').innerHTML = '<p class="hint">Reading your Captain\'s log…</p>';
    try {
      const response = await fetch(env.api('/api/recorder'), {cache: 'no-store'});
      const answer = await response.json();
      state.sessions = Array.isArray(answer.sessions) ? answer.sessions : [];
    } catch (_error) {
      state.sessions = [];
    }
    renderSessions();
  }

  function renderSessions() {
    const rows = state.sessions || [];
    $('recorder-sessions').innerHTML = rows.length ? rows.map((row) => `<button type="button" class="row-button${state.tape?.id === row.id ? ' active' : ''}" data-recorder-open="${escape(row.id)}">
        <i>▶</i><span><b>${escape(row.date)} · ${escape(row.time)}${row.open ? ' · NOW' : ''}</b>
        <small>${escape(row.start_system === row.end_system ? row.start_system : `${row.start_system} → ${row.end_system}`)}</small>
        <small>${escape(row.flown)} · ${env.number(row.jumps)} JUMPS${row.firsts ? ` · ${env.number(row.firsts)} FIRSTS` : ''}${row.moments ? ` · ${env.number(row.moments)} MOMENTS` : ''}</small></span></button>`).join('')
      : '<p class="hint">Sessions you fly are kept in the Captain\'s log; each one can be played again here.</p>';
  }

  // -- loading a tape -------------------------------------------------------------------------
  async function open(id) {
    if (!id || state.loading) return false;
    state.loading = true;
    $('recorder-status').textContent = 'LOADING THE TAPE…';
    let tape = null;
    try {
      const response = await fetch(env.api(`/api/recorder?id=${encodeURIComponent(id)}`), {cache: 'no-store'});
      if (response.ok) tape = await response.json();
      else await response.arrayBuffer().catch(() => null);
    } catch (_error) {
      tape = null;
    }
    state.loading = false;
    $('recorder-status').textContent = '';
    if (!tape?.arrivals?.length) {
      $('recorder-status').textContent = 'THAT SESSION HAS NO JOURNEY TO PLAY';
      return false;
    }
    stopMusic();
    state.tape = tape;
    state.clock = 0;
    state.playing = false;
    state.popped = new Map();
    state.musicQueued = false;
    const rows = tape.arrivals.map((row) => ({system: row.system, pos: row.pos, star_class: row.star, jump_dist: row.jump,
      timestamp: new Date((tape.start_epoch + row.t) * 1000).toISOString()}));
    env.onTape(rows, tape);
    document.body.classList.add('recording');
    $('recorder').hidden = false;
    $('recorder-title').textContent = `${tape.date} · ${tape.elite_date}`;
    $('recorder-sub').textContent = `${tape.began} · ${tape.ship || 'Your ship'} · ${env.number(tape.figures?.jumps)} jumps · ${env.number(tape.figures?.distance)} ly`;
    $('recorder-music').disabled = !(tape.music || []).length;
    $('recorder-music').title = (tape.music || []).length ? 'Play the music you were listening to, in the order it played'
      : 'No music was playing in this session (the music diary began in 5.5.10)';
    renderTimeline();
    renderSessions();
    seek(0);
    env.frame(tape.arrivals.map((row) => row.pos));
    return true;
  }

  function close() {
    if (!state.tape) return;
    stopMusic();
    state.tape = null;
    state.playing = false;
    $('recorder').hidden = true;
    document.body.classList.remove('recording');
    env.onTape(null, null);
    renderSessions();
  }

  // -- the clock --------------------------------------------------------------------------------
  function arrivalAt(clock) {
    const rows = state.tape.arrivals;
    let low = 0, high = rows.length - 1;
    while (low < high) {
      const mid = (low + high + 1) >> 1;
      if (rows[mid].t <= clock) low = mid;
      else high = mid - 1;
    }
    return low;
  }

  // Where the ship is, as the share of the trail the Atlas's replay draws.
  function valueAt(clock) {
    const rows = state.tape.arrivals;
    if (rows.length < 2) return 0;
    const index = arrivalAt(clock);
    let frac = 0;
    if (index + 1 < rows.length) {
      const next = rows[index + 1].t;
      frac = Math.max(0, Math.min(1, (clock - (next - JUMP_S)) / JUMP_S));
    }
    return Math.min(.9999, (index + frac) / (rows.length - 1));
  }

  function seek(clock, jumped = true) {
    const tape = state.tape;
    if (!tape) return;
    const before = state.clock;
    state.clock = Math.max(0, Math.min(tape.length, clock));
    // Moments crossed while playing pop up on the map; a scrub doesn't.
    if (!jumped) {
      for (const moment of tape.moments) {
        if (moment.t > before && moment.t <= state.clock) state.popped.set(moment, performance.now());
      }
    }
    env.setProgress(valueAt(state.clock));
    renderNow();
  }

  function tick(now) {
    if (!state.tape || !state.playing) {
      state.last = now;
      return false;
    }
    const dt = Math.max(0, Math.min(250, now - state.last)) / 1000;
    state.last = now;
    let next = state.clock + dt * state.speed;
    if (state.skipQuiet) {
      for (const [from, to] of state.tape.quiet || []) {
        if (next > from && next < to) next = to;
      }
    }
    if (next >= state.tape.length) {
      next = state.tape.length;
      state.playing = false;
      stopMusic();
      renderControls();
    }
    seek(next, false);
    if (state.follow && now - state.lastFollow > 1200) {
      state.lastFollow = now;
      const at = state.tape.arrivals[arrivalAt(state.clock)];
      if (at) env.follow(at.pos);
    }
    return true;
  }

  function toggle() {
    if (!state.tape) return false;
    if (state.clock >= state.tape.length - .5) seek(0);
    state.playing = !state.playing;
    state.last = performance.now();
    if (state.playing && state.music) startMusic();
    if (!state.playing) stopMusic();
    renderControls();
    return true;
  }

  // -- the music of the night -----------------------------------------------------------------------
  function startMusic() {
    const tracks = (state.tape?.music || []);
    if (!tracks.length || state.musicQueued) return;
    // The track playing now, then everything after it.
    let from = 0;
    tracks.forEach((track, index) => { if (track.t <= state.clock) from = index; });
    state.musicQueued = true;
    env.command({action: 'recorder_music', op: 'queue', tracks: tracks.slice(from).map((track) => track.track_id)});
  }

  function stopMusic() {
    if (!state.musicQueued) return;
    state.musicQueued = false;
    env.command({action: 'recorder_music', op: 'pause'});
  }

  // -- drawing ---------------------------------------------------------------------------------------
  function renderTimeline() {
    const tape = state.tape;
    const length = Math.max(1, tape.length);
    const pct = (t) => `${Math.max(0, Math.min(100, t / length * 100)).toFixed(3)}%`;
    const quiet = (tape.quiet || []).map(([a, b]) => `<i class="quiet" style="left:${pct(a)};width:calc(${pct(b)} - ${pct(a)})"></i>`).join('');
    const jumps = tape.arrivals.slice(1).map((row) => `<i class="jump" style="left:${pct(row.t)}"></i>`).join('');
    const moments = tape.moments.map((row) => `<i class="mark ${escape(row.kind)}" style="left:${pct(row.t)}" title="${escape(`${wallTime(row.t)} · ${row.title}`)}"></i>`).join('');
    const music = (tape.music || []).map((row) => `<i class="tune" style="left:${pct(row.t)}" title="${escape(`♪ ${row.title}${row.artist ? ` · ${row.artist}` : ''}`)}"></i>`).join('');
    $('recorder-track').innerHTML = `${quiet}${jumps}${music}${moments}<b id="recorder-head"></b>`;
    $('recorder-start').textContent = tape.began;
    $('recorder-end').textContent = wallTime(tape.length);
  }

  function renderControls() {
    const play = $('recorder-play');
    const name = state.playing ? 'pause' : 'play';
    if (play.dataset.state !== name) {
      play.dataset.state = name;
      play.querySelector('path').setAttribute('d', state.playing ? 'M6 5h4v14H6zM14 5h4v14h-4z' : 'M8 5v14l11-7z');
      play.title = state.playing ? 'Pause (Space)' : 'Play (Space)';
    }
    $('recorder-music').setAttribute('aria-pressed', String(state.music));
    $('recorder-quiet').setAttribute('aria-pressed', String(state.skipQuiet));
    $('recorder-follow').setAttribute('aria-pressed', String(state.follow));
  }

  function renderNow() {
    const tape = state.tape;
    if (!tape) return;
    const index = arrivalAt(state.clock);
    const here = tape.arrivals[index];
    const length = Math.max(1, tape.length);
    const head = $('recorder-head');
    if (head) head.style.left = `${(state.clock / length * 100).toFixed(3)}%`;
    $('recorder-scrub').value = String(Math.round(state.clock / length * 1000));
    $('recorder-clock').textContent = `${wallTime(state.clock)} · ${clockText(state.clock)} IN`;
    $('recorder-here').textContent = here?.system || '—';
    const seen = tape.moments.filter((moment) => moment.t <= state.clock);
    const tally = (kind) => seen.filter((moment) => moment.kind === kind).length;
    const counts = [[index, 'JUMPS'], [tally('first'), 'FIRSTS'], [tally('codex'), 'CODEX'], [tally('bio'), 'ORGANICS'], [tally('postcard') + tally('photo'), 'PICTURES']];
    $('recorder-tally').innerHTML = counts.filter(([value], at) => at === 0 || value).map(([value, label]) => `<span><b>${env.number(value)}</b>${label}</span>`).join('');
    const tracks = (tape.music || []).filter((track) => track.t <= state.clock + 1);
    const tune = tracks.at(-1);
    $('recorder-tune').hidden = !tune;
    if (tune) $('recorder-tune').textContent = `♪ ${tune.title}${tune.artist ? ` · ${tune.artist}` : ''}`;
    // The feed: the latest moments, newest on top; the Watcher at the end.
    const feed = seen.slice(-5).reverse().map((moment) => {
      const [glyph, label] = MOMENTS[moment.kind] || MOMENTS.find;
      const value = moment.value ? ` · ${env.number(moment.value)} CR` : '';
      return `<li class="${escape(moment.kind)}"><i>${glyph}</i><span><small>${escape(wallTime(moment.t))} · ${escape(label.toUpperCase())}${value}</small><b>${escape(moment.title)}</b>${moment.detail ? `<em>${escape(moment.detail)}</em>` : ''}</span></li>`;
    });
    if (state.clock >= tape.length - .5 && tape.words) {
      feed.unshift(`<li class="words"><i>◉</i><span><small>THE WATCHER</small><b>${escape(tape.words)}</b></span></li>`);
    }
    const html = feed.join('');
    const list = $('recorder-feed');
    if (list.dataset.html !== html) {
      list.dataset.html = html;
      list.innerHTML = html;
    }
  }

  // Moments just crossed, as labels where they happened.
  function labels(now) {
    if (!state.tape) return [];
    const out = [];
    for (const [moment, at] of state.popped) {
      if (now - at > POP_MS) {
        state.popped.delete(moment);
        continue;
      }
      const where = state.tape.arrivals[moment.at];
      if (!where) continue;
      const [glyph] = MOMENTS[moment.kind] || MOMENTS.find;
      out.push({key: `moment-${moment.t}-${moment.title}`, cls: `moment ${moment.kind}`, pos: where.pos, dy: 26 + out.length * 22,
        html: `${glyph} ${escape(moment.title)}`, rank: 115 - out.length});
    }
    return out.slice(0, 4);
  }

  function request(value) {
    // WATCH AGAIN on the deck: open that session (only a fresh request).
    if (!value?.seq || value.seq === state.seenRequest) return;
    state.seenRequest = value.seq;
    if (Date.now() / 1000 - Number(value.at || 0) > 60) return;
    env.showTab('recorder');
    listSessions(true).then(() => open(value.id)).then((done) => { if (done) toggle(); });
  }

  // -- wiring ------------------------------------------------------------------------------------------
  function bind() {
    $('recorder-sessions').addEventListener('click', (event) => {
      const button = event.target.closest('[data-recorder-open]');
      if (button) open(button.dataset.recorderOpen);
    });
    $('recorder-refresh').addEventListener('click', () => listSessions(true));
    $('recorder-play').addEventListener('click', toggle);
    $('recorder-close').addEventListener('click', close);
    $('recorder-scrub').addEventListener('input', (event) => {
      if (!state.tape) return;
      stopMusic();
      seek(Number(event.target.value) / 1000 * state.tape.length);
      env.redraw();
    });
    $('recorder-speed').innerHTML = SPEEDS.map(([value, label]) => `<option value="${value}"${value === state.speed ? ' selected' : ''}>${label}</option>`).join('');
    $('recorder-speed').addEventListener('change', (event) => { state.speed = Number(event.target.value) || 300; });
    $('recorder-quiet').addEventListener('click', () => { state.skipQuiet = !state.skipQuiet; renderControls(); });
    $('recorder-follow').addEventListener('click', () => { state.follow = !state.follow; renderControls(); });
    $('recorder-music').addEventListener('click', () => {
      state.music = !state.music;
      if (state.music && state.playing) startMusic();
      if (!state.music) stopMusic();
      renderControls();
    });
    $('recorder-step-back').addEventListener('click', () => step(-1));
    $('recorder-step-on').addEventListener('click', () => step(1));
    renderControls();
  }

  // To the moment before or after this one.
  function step(direction) {
    if (!state.tape) return;
    const times = state.tape.moments.map((moment) => moment.t);
    const target = direction > 0 ? times.find((t) => t > state.clock + .5) : [...times].reverse().find((t) => t < state.clock - .5);
    seek(target ?? (direction > 0 ? state.tape.length : 0));
    const moment = state.tape.moments.find((row) => row.t === target);
    if (moment) state.popped.set(moment, performance.now());
    env.redraw();
  }

  bind();
  return {
    listSessions, open, close, tick, toggle, labels, request,
    get active() { return Boolean(state.tape); },
    get playing() { return state.playing; },
    state: () => ({active: Boolean(state.tape), id: state.tape?.id || '', clock: state.clock, playing: state.playing,
      speed: state.speed, moments: state.tape?.moments?.length || 0}),
  };
}
