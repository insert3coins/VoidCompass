(() => {
  'use strict';

  /*
   * The Watcher's life
   * ------------------
   * heartbeat-orb.js paints the eye and plays an effect for each journal
   * event. This module is what it does in between (todo-watcher-life.md):
   *
   *   Idle life   blinks, slow breathing, small glances (saccades) and the
   *               odd refocus, so it never looks frozen.
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
  const BLINK_MS = 190;
  const SESSION_TIRED_MS = 3 * 3600 * 1000;
  const BREAK_MS = 15 * 60 * 1000;
  const BORED_AFTER_MS = 2 * 60 * 1000;
  const BORED_FULL_MS = 7 * 60 * 1000;

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
      this.blinkAt = now + this.between(2500, 6000);
      this.blinks = 0;
      this.double = false;
      this.yawnAt = 0;
      this.saccade = {x: 0, y: 0, at: now + this.between(1200, 3500), until: 0};
      this.look = null;     // one event's glance: {x, y, start, ms, kind}
      this.focus = 0;       // refocus blur, 0..1
      this.focusAt = now + this.between(20000, 45000);
      this.lastAdvance = now;
    }

    between(low, high) {
      return low + (high - low) * this.random();
    }

    configure({liveliness = 'standard', idle = true, reduced = false} = {}) {
      this.level = LIVELINESS[liveliness] || 1;
      this.idle = idle !== false;
      this.reduced = Boolean(reduced);
    }

    // Status.json: danger and heat set the tension; scooping makes it squint.
    vitals(vitals = {}) {
      this.dangerTarget = vitals.danger ? 1 : vitals.overheating ? .7 : vitals.low_fuel ? .45 : 0;
      this.scooping = Boolean(vitals.scooping);
    }

    // One journal event. Returns the time of a double take's closing pulse,
    // if the event earned one, so the orb can play it.
    notice(event = {}, now = performance.now()) {
      const weight = clamp(Number(event.weight) || 0);
      this.lastEventAt = now;
      if (weight >= .3 || event.rare) this.lastInteresting = now;
      if (event.effect === 'sleep' || event.effect === 'die') {
        // A break: the next session starts rested.
        this.sessionStart = now;
        this.excitement = 0;
      }
      if (event.rare) this.excitement = clamp(this.excitement + .35);
      else if (weight >= .8) this.excitement = clamp(this.excitement + .12);
      if (event.tone === 'red' && weight >= .4) this.tension = clamp(this.tension + .45);
      if (this.reduced) return null;
      const gaze = String(event.gaze || 'centre');
      if (event.rare) {
        // Double take: glance, back to centre, a longer look, then a pulse.
        const angle = this.random() * TAU;
        this.look = {x: Math.cos(angle), y: Math.sin(angle), start: now, ms: 1500, kind: 'double'};
        return now + 1250;
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
      const towards = this.dangerTarget > this.tension ? 1500 : 20000;
      this.tension += (this.dangerTarget - this.tension) * (1 - Math.exp(-elapsed / towards));
      if (now - this.lastEventAt > BREAK_MS) this.sessionStart = now;
      if (this.reduced || !this.idle || context.asleep || context.stalled) return;
      const fatigue = this.fatigue(now);
      const drowsy = clamp(Number(context.drowsy) || 0);
      if (now >= this.blinkAt + BLINK_MS) {
        this.blinks += 1;
        // Tired eyes blink less often but slower; tension blinks more.
        const pace = (1 + .8 * Math.max(fatigue, drowsy)) * (1 - .45 * this.tension) / Math.sqrt(this.level);
        const again = !this.double && this.random() < .15;
        this.double = again;
        this.blinkAt = now + (again ? 260 : this.between(4000, 12000) * pace);
      }
      if (now >= this.saccade.at && now >= this.saccade.until) {
        const reach = .045 * this.level * (1 + .6 * this.excitement + .5 * this.boredom(now));
        const angle = this.random() * TAU;
        const distance = reach * (.4 + .6 * this.random());
        this.saccade = {
          x: Math.cos(angle) * distance, y: Math.sin(angle) * distance * .8,
          at: now + this.between(1500, 5000) / (1 + this.excitement),
          until: now + this.between(300, 900),
        };
      }
      const bored = this.boredom(now);
      if (bored > .5 && !this.yawnAt && this.random() < elapsed / 40000) this.yawnAt = now;
      if (this.yawnAt && now - this.yawnAt > 2600) this.yawnAt = 0;
      if (now >= this.focusAt) this.focusAt = now + this.between(20000, 50000);
    }

    fatigue(now) {
      return clamp((now - this.sessionStart) / SESSION_TIRED_MS);
    }

    boredom(now) {
      return clamp((now - this.lastInteresting - BORED_AFTER_MS) / (BORED_FULL_MS - BORED_AFTER_MS));
    }

    blinkLid(now) {
      const t = (now - this.blinkAt) / BLINK_MS;
      if (t < 0 || t > 1) return 0;
      // Lids close quickly and open a little slower.
      return t < .38 ? smooth(t / .38) : 1 - smooth((t - .38) / .62);
    }

    lookOffset(now) {
      const look = this.look;
      if (!look) return [0, 0, 0];
      const t = (now - look.start) / look.ms;
      if (t < 0 || t >= 1) {
        if (t >= 1) this.look = null;
        return [0, 0, 0];
      }
      const reach = .07 * Math.sqrt(this.level);
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
    pose(now = performance.now()) {
      const fatigue = this.fatigue(now);
      const bored = this.boredom(now);
      const level = this.level;
      const [lx, ly, side] = this.lookOffset(now);
      let dx = lx;
      let dy = ly;
      let lid = 0;
      if (this.idle && !this.reduced) {
        if (now < this.saccade.until) {
          dx += this.saccade.x;
          dy += this.saccade.y;
        }
        lid = Math.max(lid, this.blinkLid(now));
        if (this.yawnAt) {
          const t = (now - this.yawnAt) / 2600;
          lid = Math.max(lid, .62 * Math.sin(Math.PI * clamp(t)));
        }
      }
      // Heavy lids when tired; a squint into the star while scooping; a
      // narrowed side-eye at danger.
      lid = Math.max(lid, .22 * fatigue * level, this.scooping ? .42 : 0, .32 * side);
      const focus = this.idle && !this.reduced
        ? Math.max(0, 1 - Math.abs(now - (this.focusAt - 600)) / 600) * .6 : 0;
      return {
        dx, dy,
        lid: clamp(lid),
        // The side-eye tilts the lids; everything else closes them level.
        tilt: side * .35,
        pupil: clamp(1 - .28 * this.tension + .16 * this.excitement * level, .6, 1.3),
        iris: 1 + .05 * this.excitement * level,
        dim: clamp(1 + .14 * this.excitement * level - .12 * fatigue - .08 * bored, .7, 1.2),
        spin: 1 + .9 * this.excitement * level - .3 * bored,
        red: clamp(this.tension * .7),
        blur: focus,
      };
    }

    state(now = performance.now()) {
      return {
        blinks: this.blinks, excitement: this.excitement, tension: this.tension,
        fatigue: this.fatigue(now), boredom: this.boredom(now),
        looking: Boolean(this.look), scooping: this.scooping,
      };
    }
  }

  window.HeartbeatLife = HeartbeatLife;
})();
