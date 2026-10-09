(() => {
  'use strict';

  /*
   * The Watcher's life
   * ------------------
   * heartbeat-orb.js paints the eye and plays an effect for each journal
   * event. This module is what it does in between (todo-watcher-life.md):
   *
   *   Idle life   the aperture tightening as it thinks, light sweeping across
   *               the glass, slow breathing, small glances (saccades) and the
   *               odd refocus, so it never looks frozen. (No blinking: a lens
   *               does not blink; 5.5.3.1.)
   *   Activity    what the commander is doing sets how it watches: relaxed
   *               when docked, looking ahead in supercruise, sweeping in the
   *               FSS, looking down on a surface, wary in danger.
   *   Attention   it looks the way each event points (heartbeat_events.py
   *               gives a gaze), takes a double take at rare finds, gives
   *               danger a side-eye and squints into a star while scooping.
   *   Mood        fatigue over a long session, excitement from streaks of
   *               finds, tension from danger, boredom when nothing new
   *               happens. Each blends into the same few numbers the orb
   *               already draws with.
   *
   * It is all rules and timers on a seeded clock (no AI, nothing measured),
   * so a test can pin any pose. The orb asks for pose(now) every frame.
   */

  const TAU = Math.PI * 2;
  const clamp = (value, low = 0, high = 1) => Math.max(low, Math.min(high, value));
  const smooth = (t) => t * t * (3 - 2 * t);

  // How strongly each liveliness setting moves the eye and colours its mood.
  const LIVELINESS = {calm: .55, standard: 1, alive: 1.6};
  const GAZES = {
    centre: [0, 0], up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0],
    side: [1, -.15], sweep: [0, 0],
  };
  const APERTURE_MS = 900;
  const GLINT_MS = 1400;
  // What the commander is doing, from the HUD's state label.
  const ACTIVITIES = [
    ['wary', /INTERDICT|SILENT RUNNING|TARGET LOCK|DOCK DENIED|COMBAT|DANGER|UNDER ATTACK/],
    ['scanning', /\bFSS\b|\bDSS\b|PHENOMENA|ORRERY|CODEX|SYSTEM MAP|GALAXY MAP|\bMAP\b|EXPLORATION/],
    ['down', /GLIDE|SURFACE|ORBITAL APPROACH|\bSRV\b|SCARAB|SCORPION|RHINO|NOMAD|ON ?FOOT|SETTLEMENT|TURRET|DRIVE ASSIST|LANDING/],
    ['ahead', /SUPERCRUISE|SC ASSIST|SCO|HYPER|JUMP|FSD|TAXI|CARRIER TRANSIT|ARRIVAL/],
    ['relaxed', /DOCKED|LANDED|HANDBRAKE|AFMU|CARRIER DECK|SURFACE STATION/],
  ];
  // How each activity holds the eye: where it rests, how far and how often
  // it glances, and how heavy the lids sit.
  const STANCES = {
    idle: {x: 0, y: 0, reach: 1, pace: 1, lower: 0},
    relaxed: {x: 0, y: .01, reach: .6, pace: 1.8, lower: .12, upper: .08},
    ahead: {x: 0, y: -.025, reach: .7, pace: 1.3},
    scanning: {x: 0, y: 0, reach: 1.3, pace: .7, sweep: true},
    down: {x: 0, y: .035, reach: .8, pace: 1},
    wary: {x: 0, y: 0, reach: 1.4, pace: .5, upper: .18, lower: .1},
  };

  function activityFor(state) {
    const label = String(state || '').toUpperCase();
    if (!label) return 'idle';
    for (const [name, pattern] of ACTIVITIES) if (pattern.test(label)) return name;
    return 'idle';
  }
  const SESSION_TIRED_MS = 3 * 3600 * 1000;
  const BREAK_MS = 15 * 60 * 1000;
  const BORED_AFTER_MS = 2 * 60 * 1000;
  const BORED_FULL_MS = 7 * 60 * 1000;
  // After this long with nothing new, the next event startles it more.
  const QUIET_STARTLE_MS = 60 * 1000;
  // Repeats of one event fade from memory over a few minutes.
  const HABIT_MEMORY_MS = 3 * 60 * 1000;

  /*
   * Expressions (5.5.3.1): what the eye feels about one event, held for a
   * few seconds over its mood. upper/lower close the lids, wide opens them,
   * pupil and iris scale the eye, tone tints the iris; dart quickens the
   * glances, still stops them, reading scans lines left to right.
   */
  const EXPRESSIONS = {
    startled: {ms: 1500, wide: .9, pupil: -.45, iris: .08, bright: .35, flare: 1.1, then: 'wary'},
    wary: {ms: 4500, upper: .3, lower: .18, pupil: -.18, dart: 1.6, tone: 'orange', toneAmount: .18},
    curious: {ms: 2600, wide: .3, pupil: .28, iris: .04, bright: .15, flare: .45},
    pleased: {ms: 3200, upper: .1, lower: .45, pupil: .18, tone: 'green', toneAmount: .35, bright: .12, flare: .35},
    focused: {ms: 3600, upper: .2, lower: .1, pupil: -.1, still: 1},
    reading: {ms: 2600, upper: .12, lower: .06, reading: 1},
    // Saying something gloomy (5.5.3.2): the lids fall, the eye dims and drops.
    downcast: {ms: 4200, upper: .34, lower: .04, pupil: -.12, bright: -.14, down: .04},
  };
  // A thought's mood (watcher_mind.MOODS) and the expression it plays.
  const MOOD_EXPRESSIONS = {pleased: 'pleased', wary: 'wary', curious: 'curious', downcast: 'downcast'};
  // Its nature (Overlay Studio): how strongly each feeling takes it.
  const NATURES = {
    stoic: {all: .6, excitement: .6},
    curious: {curious: 1.5, pleased: 1.15, startled: .85},
    nervous: {startled: 1.6, wary: 1.6, curious: .8, tension: 1.8},
    // Depressed (the default): heavy lids, a low gaze, a dim slow eye,
    // frequent sighs, and very little impresses it.
    weary: {all: .55, excitement: .3, pleased: .3, curious: .55, startled: .7, downcast: 1.8, lids: .3, lower: .08,
      dim: .8, spin: .55, look: .03, sighs: 3},
  };
  const GRIEF_MS = 10 * 60 * 1000;
  const ALARMS = new Set(['alarm', 'breach', 'strike']);
  const PLEASURES = new Set(['payout', 'complete', 'clear', 'glint', 'dock']);
  const FOCUS = new Set(['warp', 'charge', 'approach', 'lock']);
  const CURIOSITY = new Set(['spark', 'signal', 'sweep', 'honk']);

  // Which expression an event earns, if any.
  function expressionFor(event, weight) {
    const effect = String(event.effect || '');
    // A death is not a startle: grief takes it (see notice()).
    if (effect === 'die' || effect === 'sleep') return null;
    if (event.rare) return 'curious';
    if (ALARMS.has(effect) || (event.tone === 'red' && weight >= .6)) return 'startled';
    if (PLEASURES.has(effect)) return 'pleased';
    if (FOCUS.has(effect)) return 'focused';
    if (effect === 'speak' && weight >= .5) return 'reading';
    if (event.family === 'scan' || CURIOSITY.has(effect)) return 'curious';
    return null;
  }

  // mulberry32: a small seeded generator, so tests can fix the pose.
  function rng(seed) {
    let state = seed >>> 0;
    return () => {
      state = (state + 0x6D2B79F5) >>> 0;
      let t = state;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  class HeartbeatLife {
    constructor(seed = 0x5eed, now = performance.now()) {
      this.random = rng(seed);
      this.level = 1;
      this.idle = true;
      this.reduced = false;
      this.sessionStart = now;
      this.lastInteresting = now;
      this.lastEventAt = now;
      this.excitement = 0;
      this.tension = 0;
      this.dangerTarget = 0;
      this.scooping = false;
      this.apertureAt = now + this.between(2500, 6000);
      this.pulses = 0;
      this.glintAt = now + this.between(6000, 14000);
      this.sighAt = 0;
      this.activity = 'idle';
      this.saccade = {x: 0, y: 0, at: now + this.between(1200, 3500), until: 0};
      this.look = null;     // one event's glance: {x, y, start, ms, kind}
      this.focus = 0;       // refocus blur, 0..1
      this.focusAt = now + this.between(20000, 45000);
      this.lastAdvance = now;
      this.expression = null; // {name, start, ms, strength}
      this.habits = new Map(); // event name -> {count, at}
      this.overlays = {};      // overlay attr -> [dx, dy] on screen
      this.nature = 'curious'; // neutral; the app sends the commander's nature (depressed by default)
      this.charging = 0;       // anticipation of a jump, eased 0..1
      this.fsdCharging = false;
      this.glide = false;
      this.fuel = null;
      this.worryAt = now + 6000;
      this.griefUntil = 0;
      this.homecoming = false;
      this.highlights = [];    // tones of the session's notable moments, for its dreams
    }

    // How used to this event it is: 1 for something new, falling towards
    // .3 for the tenth of the same in a row. Forgotten over a few minutes.
    habituation(name, now) {
      const key = String(name || '');
      const habit = this.habits.get(key);
      const count = habit ? habit.count * Math.exp(-(now - habit.at) / HABIT_MEMORY_MS) : 0;
      this.habits.set(key, {count: count + 1, at: now});
      if (this.habits.size > 120) this.habits.delete(this.habits.keys().next().value);
      return Math.max(.3, 1 / (1 + .45 * count));
    }

    express(name, now, strength) {
      const spec = EXPRESSIONS[name];
      if (!spec || strength <= .05) return;
      const current = this.expressionPose(now);
      // A stronger feeling replaces a weaker one; a weaker one waits its turn.
      if (current && current.strength > strength && this.expression.name !== name) return;
      this.expression = {name, start: now, ms: spec.ms, strength: clamp(strength, 0, 1.4)};
    }

    // The current expression's weight this moment (attack, hold, release).
    expressionPose(now) {
      const expression = this.expression;
      if (!expression) return null;
      const t = (now - expression.start) / expression.ms;
      if (t >= 1) {
        const follow = EXPRESSIONS[expression.name].then;
        this.expression = null;
        if (follow) this.express(follow, expression.start + expression.ms, expression.strength * .8);
        return this.expression ? this.expressionPose(now) : null;
      }
      if (t < 0) return null;
      const envelope = t < .12 ? smooth(t / .12) : t < .7 ? 1 : 1 - smooth((t - .7) / .3);
      return {name: expression.name, t, strength: envelope * expression.strength, spec: EXPRESSIONS[expression.name]};
    }

    // Saying a thought: the eye shows how it feels about it.
    feel(mood, now = performance.now()) {
      const name = MOOD_EXPRESSIONS[String(mood || '')];
      if (!name || this.reduced) return;
      this.express(name, now, .85 * this.natureOf(name));
      // A gloomy thought comes with a sigh.
      if (name === 'downcast' && (!this.sighAt || now - this.sighAt > 2600)) this.sighAt = now;
    }

    // Composing a thought: the aperture tightens and holds until it speaks.
    think(ms, now = performance.now()) {
      if (this.reduced) return;
      this.thinkStart = now;
      this.thinkUntil = now + Math.max(200, Number(ms) || 600);
    }

    thinking(now) {
      if (!this.thinkUntil || now < this.thinkStart) return 0;
      if (now < this.thinkUntil) return .85 * smooth(clamp((now - this.thinkStart) / 260));
      return .85 * (1 - smooth(clamp((now - this.thinkUntil) / 450)));
    }

    between(low, high) {
      return low + (high - low) * this.random();
    }

    configure({liveliness = 'standard', idle = true, reduced = false, state = null,
      overlays = null, personality = null, memory = null} = {}, now = performance.now()) {
      this.level = LIVELINESS[liveliness] || 1;
      this.idle = idle !== false;
      this.reduced = Boolean(reduced);
      if (state !== null && state !== undefined) this.activity = activityFor(state);
      if (overlays && typeof overlays === 'object') this.overlays = overlays;
      if (personality && NATURES[personality]) this.nature = personality;
      if (memory && !this.homecoming) {
        this.homecoming = true;
        // It remembers you: a long absence, a slow look around on waking;
        // a recent death, a subdued eye for a while.
        if (Number(memory.away_hours) > 48 && !this.reduced) {
          this.look = {x: 1, y: 0, start: now + 1200, ms: 3200, kind: 'sweep'};
          this.excitement = clamp(this.excitement + .25);
        }
        if (memory.recent_death) this.griefUntil = now + GRIEF_MS / 2;
      }
    }

    natureOf(feeling) {
      const nature = NATURES[this.nature] || {};
      return (nature.all ?? 1) * (nature[feeling] ?? 1);
    }

    stance() {
      return STANCES[this.activity] || STANCES.idle;
    }

    // Status.json: danger and heat set the tension; scooping makes it squint.
    vitals(vitals = {}) {
      this.dangerTarget = vitals.danger ? 1 : vitals.overheating ? .7 : vitals.low_fuel ? .45 : 0;
      this.scooping = Boolean(vitals.scooping);
      // It anticipates: the drive charging before the jump, a glide down.
      this.fsdCharging = Boolean(vitals.fsd_charging);
      this.glide = Boolean(vitals.glide);
      const fuel = Number(vitals.fuel_percent);
      this.fuel = vitals.fuel_percent == null || !Number.isFinite(fuel) ? null : fuel;
    }

    worry() {
      // Fuel under a quarter, not scooping: it keeps glancing at the gauge.
      if (this.fuel == null || this.scooping || this.fuel >= 25) return 0;
      return clamp(1 - this.fuel / 25);
    }

    // One journal event. Returns the time of a double take's closing pulse,
    // if the event earned one, so the orb can play it.
    notice(event = {}, now = performance.now()) {
      const weight = clamp(Number(event.weight) || 0);
      const quiet = now - this.lastEventAt > QUIET_STARTLE_MS;
      this.lastEventAt = now;
      // What it feels: scaled by how used to it the eye is, and stronger
      // after a long quiet.
      const feeling = expressionFor(event, weight);
      if (feeling && !this.reduced) {
        const strength = (event.rare ? 1.2 : .45 + .6 * weight)
          * this.habituation(event.event || event.effect, now) * (quiet ? 1.35 : 1) * this.natureOf(feeling);
        this.express(feeling, now, strength);
      }
      if (event.effect === 'die') this.griefUntil = now + GRIEF_MS;
      if (event.rare || weight >= .7) {
        // A moment worth dreaming about later.
        this.highlights.push(String(event.tone || 'accent'));
        if (this.highlights.length > 40) this.highlights.shift();
      }
      if (weight >= .3 || event.rare) this.lastInteresting = now;
      if (event.effect === 'sleep' || event.effect === 'die') {
        // A break: the next session starts rested.
        this.sessionStart = now;
        this.excitement = 0;
      }
      const keen = NATURES[this.nature]?.excitement ?? 1;
      if (event.rare) this.excitement = clamp(this.excitement + .35 * keen);
      else if (weight >= .8) this.excitement = clamp(this.excitement + .12 * keen);
      if (event.tone === 'red' && weight >= .4) this.tension = clamp(this.tension + .45 * (NATURES[this.nature]?.tension ?? 1));
      if (this.reduced) return null;
      const gaze = String(event.gaze || 'centre');
      if (event.rare) {
        // Double take: glance, back to centre, a longer look, then a pulse.
        const angle = this.random() * TAU;
        this.look = {x: Math.cos(angle), y: Math.sin(angle), start: now, ms: 1500, kind: 'double'};
        return now + 1250;
      }
      // It looks at the overlay the event concerns, where it sits on screen.
      const toward = this.overlays[event.overlay];
      if (Array.isArray(toward) && weight >= .1) {
        this.look = {x: toward[0], y: toward[1], start: now, ms: 1300, kind: 'overlay'};
        return null;
      }
      if (weight < .2 || gaze === 'centre') return null;
      const [x, y] = GAZES[gaze] || GAZES.centre;
      const kind = gaze === 'sweep' ? 'sweep' : gaze === 'side' ? 'side' : 'look';
      this.look = {x, y, start: now, ms: kind === 'side' ? 2200 : kind === 'sweep' ? 1400 : 1300, kind};
      return null;
    }

    advance(now, context = {}) {
      const elapsed = clamp(now - this.lastAdvance, 0, 1000);
      this.lastAdvance = now;
      // Moods ease rather than jump; excitement lasts minutes, tension follows
      // the danger flags and lets go with relief.
      this.excitement *= Math.exp(-elapsed / 240000);
      const towards = this.dangerTarget > this.tension ? 1500 / (NATURES[this.nature]?.tension ?? 1) : 20000;
      this.charging += ((this.fsdCharging ? 1 : 0) - this.charging) * (1 - Math.exp(-elapsed / 500));
      this.tension += (this.dangerTarget - this.tension) * (1 - Math.exp(-elapsed / towards));
      if (now - this.lastEventAt > BREAK_MS) this.sessionStart = now;
      if (this.reduced || !this.idle || context.asleep || context.stalled) return;
      const fatigue = this.fatigue(now);
      const drowsy = clamp(Number(context.drowsy) || 0);
      const stance = this.stance();
      const worry = this.worry();
      if (worry > 0 && now >= this.worryAt && !this.look) {
        this.look = {x: 0, y: 1, start: now, ms: 1100, kind: 'look'};
        this.worryAt = now + this.between(5000, 9000) / (.5 + worry);
      }
      if (now >= this.apertureAt + APERTURE_MS) {
        this.pulses += 1;
        // The aperture works: tightening as it thinks. Slower when tired,
        // quicker when tense.
        const pace = (1 + .8 * Math.max(fatigue, drowsy)) * (1 - .45 * this.tension) / Math.sqrt(this.level);
        this.apertureAt = now + this.between(5000, 12000) * pace;
      }
      if (now >= this.glintAt + GLINT_MS) this.glintAt = now + this.between(9000, 22000);
      if (stance.sweep && (!this.look || this.look.kind !== 'sweep') && this.random() < elapsed / 7000) {
        // Scanning: it sweeps the field now and then by itself.
        this.look = {x: 1, y: 0, start: now, ms: 1800, kind: 'sweep'};
      }
      const feeling = this.expressionPose(now);
      const dart = feeling ? (feeling.spec.dart || 0) * feeling.strength : 0;
      if (now >= this.saccade.at && now >= this.saccade.until) {
        const reach = .045 * this.level * stance.reach * (1 + .6 * this.excitement + .5 * this.boredom(now) + .4 * dart);
        const angle = this.random() * TAU;
        const distance = reach * (.4 + .6 * this.random());
        this.saccade = {
          x: Math.cos(angle) * distance, y: Math.sin(angle) * distance * .8,
          at: now + this.between(1500, 5000) * stance.pace / (1 + this.excitement + dart),
          until: now + this.between(300, 900),
        };
      }
      const bored = this.boredom(now);
      // Bored, it sighs: the eye dims and the galaxy slows for a moment.
      const sighs = NATURES[this.nature]?.sighs || 1;
      if ((bored > .5 || sighs > 1) && !this.sighAt && this.random() < elapsed * sighs / 40000) this.sighAt = now;
      if (this.sighAt && now - this.sighAt > 2600) this.sighAt = 0;
      if (now >= this.focusAt) this.focusAt = now + this.between(20000, 50000);
    }

    fatigue(now) {
      return clamp((now - this.sessionStart) / SESSION_TIRED_MS);
    }

    boredom(now) {
      return clamp((now - this.lastInteresting - BORED_AFTER_MS) / (BORED_FULL_MS - BORED_AFTER_MS));
    }

    // The aperture's squeeze, 0..1 (quick in, slow out).
    aperture(now) {
      const t = (now - this.apertureAt) / APERTURE_MS;
      if (t < 0 || t > 1) return 0;
      return t < .25 ? smooth(t / .25) : 1 - smooth((t - .25) / .75);
    }

    // Light across the glass: where the sweep is (0..1), or null.
    glint(now) {
      const t = (now - this.glintAt) / GLINT_MS;
      return t >= 0 && t <= 1 ? smooth(t) : null;
    }

    lookOffset(now) {
      const look = this.look;
      if (!look) return [0, 0, 0];
      const t = (now - look.start) / look.ms;
      if (t < 0 || t >= 1) {
        if (t >= 1) this.look = null;
        return [0, 0, 0];
      }
      const reach = (look.kind === 'overlay' ? .1 : .07) * Math.sqrt(this.level);
      if (look.kind === 'sweep') {
        const swing = Math.sin(t * TAU) * (1 - t);
        return [swing * reach, 0, 0];
      }
      if (look.kind === 'double') {
        // Glance (0-.2), back (.2-.4), the second, longer look (.45-.85).
        const first = t < .2 ? smooth(t / .2) : t < .4 ? 1 - smooth((t - .2) / .2) : 0;
        const second = t < .45 ? 0 : t < .6 ? smooth((t - .45) / .15) : t < .85 ? 1 : 1 - smooth((t - .85) / .15);
        const amount = Math.max(first * .7, second);
        return [look.x * reach * amount, look.y * reach * amount, 0];
      }
      const hold = t < .18 ? smooth(t / .18) : t < .7 ? 1 : 1 - smooth((t - .7) / .3);
      return [look.x * reach * hold, look.y * reach * hold, look.kind === 'side' ? hold : 0];
    }

    // Everything the orb needs this frame. Neutral when idle life is off,
    // apart from what events and the mood ask for.
    // The local time: drowsier deep in the night.
    nightfall() {
      const hour = new Date().getHours();
      return hour < 5 ? .5 : hour >= 23 ? .3 : 0;
    }

    grief(now) {
      return now < this.griefUntil ? clamp((this.griefUntil - now) / GRIEF_MS * 1.5) : 0;
    }

    pose(now = performance.now()) {
      const fatigue = Math.max(this.fatigue(now), this.nightfall());
      const grief = this.grief(now);
      const charge = this.charging;
      const bored = this.boredom(now);
      const level = this.level;
      const [lx, ly, side] = this.lookOffset(now);
      const feeling = this.reduced ? null : this.expressionPose(now);
      const spec = feeling?.spec || {};
      const strength = feeling?.strength || 0;
      // Gliding down to a surface, it looks down whatever the HUD says.
      const stance = this.glide ? STANCES.down : this.stance();
      // Where the activity rests the eye: ahead, down, centre.
      let dx = lx + stance.x * level;
      // A depressed eye rests low.
      let dy = ly + stance.y * level - .02 * charge + (NATURES[this.nature]?.look || 0);
      // Composing a thought tightens it, idle motions or not.
      let aperture = this.reduced ? 0 : this.thinking(now);
      let glint = null;
      let sigh = 0;
      if (this.idle && !this.reduced) {
        // A focused eye holds its gaze; any other glances about.
        if (now < this.saccade.until && !(spec.still && strength > .4)) {
          dx += this.saccade.x;
          dy += this.saccade.y;
        }
        aperture = Math.max(aperture, this.aperture(now));
        glint = this.glint(now);
        if (this.sighAt) sigh = Math.sin(Math.PI * clamp((now - this.sighAt) / 2600));
      }
      // A sigh with a gloomy thought shows even with idle motions off.
      if (!sigh && this.sighAt && !this.reduced) sigh = Math.sin(Math.PI * clamp((now - this.sighAt) / 2600));
      // A downcast eye drops its gaze.
      dy += (spec.down || 0) * strength;
      if (spec.reading && strength > .05) {
        // Reading a message: three lines, left to right, a quick return each.
        const line = clamp(feeling.t * 3, 0, 2.999);
        const across = line % 1;
        dx += (across < .85 ? -1 + 2 * (across / .85) : 1 - 2 * ((across - .85) / .15)) * .05 * strength;
        dy += (-.03 + Math.floor(line) * .03) * strength;
      }
      // Heavy lids when tired; a squint into the star while scooping; a
      // narrowed side-eye at danger; and whatever the eye feels. A wide eye
      // (startled, curious) opens them.
      const wide = (spec.wide || 0) * strength;
      // (The scooping squint holds whatever it feels: the star is bright.)
      const squint = this.scooping ? .42 : 0;
      const droop = NATURES[this.nature]?.lids || 0;
      const upper = Math.max(squint, Math.max(.22 * fatigue * level, .32 * side, (spec.upper || 0) * strength, stance.upper || 0, .15 * grief, this.glide ? .12 : 0, droop) * (1 - wide - .5 * charge));
      const lower = Math.max(squint, Math.max(.12 * fatigue * level, .16 * side, (spec.lower || 0) * strength, stance.lower || 0, .1 * grief, NATURES[this.nature]?.lower || 0) * (1 - wide - .5 * charge));
      const lid = upper;
      const focus = this.idle && !this.reduced
        ? Math.max(0, 1 - Math.abs(now - (this.focusAt - 600)) / 600) * .6 : 0;
      return {
        dx, dy,
        lid: clamp(lid),
        lidLower: clamp(lower),
        aperture,
        glint,
        activity: this.activity,
        // The side-eye tilts the lids; everything else closes them level.
        tilt: side * .35,
        pupil: clamp(1 - .28 * Math.max(this.tension, .5 * this.worry()) + .16 * this.excitement * level + (spec.pupil || 0) * strength + .28 * charge - .1 * grief, .45, 1.5),
        iris: 1 + .05 * this.excitement * level + (spec.iris || 0) * strength,
        expression: feeling ? feeling.name : '',
        // The pupil's flash: a startle flares it, curiosity and pleasure glow.
        flare: (spec.flare || 0) * strength,
        tone: spec.tone || '',
        toneAmount: (spec.toneAmount || 0) * strength,
        dim: clamp((NATURES[this.nature]?.dim ?? 1) + .14 * this.excitement * level - .12 * fatigue - .08 * bored - .15 * sigh - .22 * grief + .12 * charge + (spec.bright || 0) * strength, .55, 1.45),
        spin: (NATURES[this.nature]?.spin ?? 1) + .9 * this.excitement * level - .3 * bored - .5 * sigh - .45 * grief + 1.6 * charge,
        red: clamp(this.tension * .7),
        blur: focus,
      };
    }

    state(now = performance.now()) {
      return {
        pulses: this.pulses, activity: this.activity, excitement: this.excitement, tension: this.tension,
        nature: this.nature, charging: this.charging, worry: this.worry(), grief: this.grief(now),
        dreams: this.highlights.length,
        fatigue: this.fatigue(now), boredom: this.boredom(now),
        looking: Boolean(this.look), scooping: this.scooping,
        expression: this.expressionPose(now)?.name || '',
      };
    }
  }

  window.HeartbeatLife = HeartbeatLife;
})();
