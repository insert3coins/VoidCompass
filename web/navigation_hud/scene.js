(() => {
  'use strict';

  /*
   * Navigation scene
   * ----------------
   * Every navigation state projects its own animated hologram: a scene in the
   * deck beside the ship, and an aura in the ship's hologram bay. The geometry
   * evokes the cockpit instrument for that state and never invents telemetry.
   * Anything that reads as a quantity (altitude, scan progress, probes used,
   * threat level, boost tier, shields) is drawn from the journal or
   * Status.json; everything else is decorative motion.
   *
   * One 30 fps clock draws both surfaces. It stops while the overlay is
   * hidden or the page is in the background, and under reduced motion each
   * change paints a single still frame instead. A state change re-projects
   * the hologram: the outgoing scene folds to a bright line and the new one
   * opens from it. Related states (supercruise to assist, say) cross-fade.
   */

  const TAU = Math.PI * 2;
  const FRAME_MS = 1000 / 30;
  const REPROJECT_MS = 540;
  const CROSSFADE_MS = 380;
  const FOLD = .035;
  // Reduced motion paints one pose per state; this phase shows every scene
  // with its moving parts spread out rather than bunched at the origin.
  const STILL_PHASE = 1.37;

  const fract = (value) => ((value % 1) + 1) % 1;
  const clamp = (value, low = 0, high = 1) => Math.max(low, Math.min(high, value));
  const lerp = (from, to, t) => from + (to - from) * t;
  const smooth = (value) => {
    const t = clamp(value);
    return t * t * (3 - 2 * t);
  };
  const wave = (value) => .5 - .5 * Math.cos(value * TAU);
  const hash = (value) => {
    const x = Math.sin(value * 91.731 + 17.17) * 43758.5453;
    return x - Math.floor(x);
  };
  // Fade a 0..1 journey in and out at both ends of its travel.
  const ends = (t, edge = .12) => smooth(t / edge) * smooth((1 - t) / edge);

  // Stable low-poly geology, built once rather than changing silhouettes on
  // every frame. Shared vertices keep the shaded facets joined as rocks tumble.
  const ASTEROIDS = (() => {
    const t = (1 + Math.sqrt(5)) / 2;
    const vertices = [[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
      [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t], [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]];
    const faces = [[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
      [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
      [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
      [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]];
    return Array.from({length: 12}, (_, seed) => {
      const shape = vertices.map((vertex, index) => {
        const radius = (.78 + hash(seed * 17 + index) * .26) / Math.hypot(...vertex);
        return vertex.map((n, axis) => n * radius * (axis === 1 ? .7 + hash(seed + 41) * .25 : 1));
      });
      return {vertices: shape, faces};
    });
  })();

  // ---------------------------------------------------------------------
  // State keys. Python publishes a motion family and a label; the scene
  // needs the finer distinction between, say, a system map and an orrery.
  // ---------------------------------------------------------------------

  const PLANETARY = new Set([
    'orbital_approach', 'glide', 'surface_approach', 'surface_hold',
    'surface_departure', 'orbital_departure',
  ]);

  function sceneKey(motionValue, labelValue, vehicleValue) {
    const motion = String(motionValue || 'flight');
    const label = String(labelValue || 'FLIGHT').toUpperCase();
    const vehicle = String(vehicleValue || '').toLowerCase();
    if (motion === 'scanner') return label.startsWith('DSS') ? 'dss' : 'fss';
    if (motion === 'supercruise' && label === 'TAXI') return 'taxi';
    if (motion === 'map') {
      return ({
        'GALAXY MAP': 'galaxy_map', 'SYSTEM MAP': 'system_map',
        'POWER MAP': 'power_map', ORRERY: 'orrery', CODEX: 'codex',
      })[label] || 'map';
    }
    if (motion === 'surface_vehicle') {
      for (const name of ['nomad', 'scorpion', 'rhino']) {
        if (label === name.toUpperCase() || vehicle === name) return name;
      }
      return label === 'SCARAB' || vehicle === 'scarab' ? 'scarab' : 'srv';
    }
    if (motion === 'fsd_charge') return label === 'HYPER CHARGE' ? 'hyper_charge' : 'fsd_charge';
    if (motion === 'jump') return label === 'JUMPING' ? 'jumping' : 'hyperspace';
    if (motion === 'arrival' && label === 'INTERDICTION EVADED') return 'interdiction_evaded';
    if (motion === 'fsd_lock') {
      if (label === 'MASS LOCK') return 'mass_lock';
      if (label.startsWith('FSD INJECTION')) return 'fsd_injection';
      if (label === 'SIGNAL DROP') return 'signal_drop';
      return label.startsWith('SIGNAL THREAT') ? 'signal_threat' : 'signal_lock';
    }
    if (motion === 'combat') {
      if (label === 'INTERDICTED') return 'interdicted';
      return label === 'INTERDICTION' ? 'interdiction' : 'combat';
    }
    if (motion === 'target_lock') {
      return ({
        'SYSTEM TARGET': 'target_system', 'BODY TARGET': 'target_body',
        'SIGNAL TARGET': 'target_signal', 'TARGET CLEARED': 'target_clear',
      })[label] || 'target_lock';
    }
    if (motion === 'docking_denied') {
      if (label === 'DOCK CANCELLED') return 'docking_cancelled';
      return label === 'DOCK TIMEOUT' ? 'docking_timeout' : 'docking_denied';
    }
    if (motion.startsWith('vehicle_')) {
      const kind = label.includes('NOMAD') || vehicle === 'nomad' ? 'nomad'
        : label.includes('FIGHTER') || vehicle === 'fighter' ? 'fighter'
          : label.includes('SCORPION') || vehicle === 'scorpion' ? 'scorpion'
            : label.includes('RHINO') || vehicle === 'rhino' ? 'rhino'
              : label.includes('SRV') || label.includes('SCARAB') || vehicle === 'scarab' ? 'srv'
                : label.includes('CREW') ? 'crew' : 'ship';
      return `${motion}_${kind}`;
    }
    if (motion === 'flight' && label === 'MULTICREW') return 'multicrew';
    if (motion === 'docked' && label === 'STATION') return 'station';
    if (motion === 'station') return label === 'CARRIER VICINITY' ? 'carrier_vicinity' : 'station_vicinity';
    return motion;
  }

  // The bay aura groups related states. Moving between states that share an
  // aura cross-fades; anything else re-projects the whole hologram.
  const AURA_GROUPS = {
    cruise: ['supercruise', 'supercruise_overcharge', 'supercruise_assist', 'taxi',
      'local_arrival', 'interdiction_evaded'],
    charge: ['fsd_charge', 'hyper_charge', 'fsd_injection'],
    tunnel: ['hyperspace', 'jumping', 'carrier_transit'],
    flare: ['arrival', 'carrier_arrival'],
    cool: ['fsd_cooldown'],
    descent: [...PLANETARY],
    pad: ['landed', 'surface_station', 'settlement_area'],
    dock: ['docked', 'station', 'station_vicinity', 'docking_clearance', 'docking_denied',
      'docking_cancelled', 'docking_timeout', 'docking_assist', 'maintenance',
      'carrier_vicinity', 'carrier_preparing', 'carrier_lockdown'],
    ground: ['srv', 'scarab', 'scorpion', 'rhino', 'nomad', 'srv_handbrake', 'srv_turret',
      'srv_drive_assist'],
    foot: ['on_foot', 'carrier_deck'],
    sensor: ['fss', 'dss', 'map', 'galaxy_map', 'system_map', 'power_map', 'orrery', 'codex',
      'phenomena', 'exploration', 'target_lock', 'target_system', 'target_body',
      'target_signal', 'target_clear'],
    rocks: ['asteroid_field'],
    lock: ['mass_lock', 'signal_lock', 'signal_drop', 'capital_contact', 'unknown_contact'],
    alarm: ['combat', 'heavy_combat', 'srv_threat', 'interdiction', 'interdicted',
      'signal_threat', 'heat_critical', 'suit_hazard', 'jet_cone_damage', 'system_reboot'],
    panel: ['left_panel', 'right_panel', 'comms_panel', 'role_panel', 'station_services'],
  };
  const AURA_OF = new Map(Object.entries(AURA_GROUPS)
    .flatMap(([aura, keys]) => keys.map((key) => [key, aura])));
  const auraOf = (key) => (key.startsWith('vehicle_') ? 'handoff' : AURA_OF.get(key) || 'idle');

  // Seconds per animation cycle, per state. Faster states read as urgent.
  const PERIODS = {
    flight: 1.9, fighter: .82, multicrew: 1.5, exploration: 2.25,
    supercruise: .94, taxi: 1.56, supercruise_overcharge: .48,
    supercruise_assist: 1.28, flight_assist_off: .84, silent_running: 2.2,
    fsd_charge: .86, hyper_charge: .64, hyperspace: .58, jumping: .72,
    arrival: 1.15, interdiction_evaded: 1.05, fsd_cooldown: 1.55,
    local_arrival: 1.42, fsd_injection: 1.9, target_lock: 2.2,
    target_system: 1.9, target_body: 1.7, target_signal: 1.42, target_clear: 1.8,
    carrier_vicinity: 2.3, station_vicinity: 2.1, carrier_preparing: 1.6,
    carrier_lockdown: 1.4, carrier_transit: 1.08, carrier_arrival: 1.34, carrier_deck: 2.4,
    fss: 1.52, dss: 1.82, map: 2.1, galaxy_map: 2.35,
    system_map: 1.86, power_map: 1.7, orrery: 2.5, codex: 1.9,
    phenomena: 2.6, docking_assist: 1.34, settlement_area: 1.95,
    srv_threat: .72, capital_contact: 1.48, unknown_contact: 1.72, heavy_combat: .56,
    left_panel: 1.62, right_panel: 1.62, comms_panel: 1.34,
    role_panel: 1.78, station_services: 2.05,
    orbital_approach: 1.68, glide: .82, surface_approach: 1.38,
    surface_hold: 2.25, surface_departure: 1.28, orbital_departure: 1.55,
    landed: 2.4, on_foot: 1.32, srv: 1.18, scarab: 1.18,
    scorpion: .9, rhino: 1.04, nomad: 1.05,
    srv_handbrake: 1.8, srv_turret: 1.2, srv_drive_assist: 1.35,
    asteroid_field: 5.2, mass_lock: 1.12, signal_lock: 1.55,
    signal_drop: .92, signal_threat: .76, combat: .64,
    interdiction: .5, interdicted: .43, docked: 2.3, station: 2.1,
    surface_station: 1.72,
    heat_critical: .58, suit_hazard: .72, jet_cone_damage: .46,
    docking_clearance: 1.42, docking_denied: .68,
    docking_cancelled: 1.1, docking_timeout: .8,
    maintenance: 1.7, system_reboot: .92,
  };
  const periodOf = (key) => PERIODS[key] || (key.startsWith('vehicle_') ? 1.3 : 1.45);

  function dynamicsOf(raw) {
    const source = raw && typeof raw === 'object' ? raw : {};
    const number = (value, fallback, low, high) => {
      if (value == null || value === '') return fallback;
      const parsed = Number(value);
      return Number.isFinite(parsed) ? clamp(parsed, low, high) : fallback;
    };
    return {
      gravity: number(source.gravity_g, 0, 0, 20),
      altitude: number(source.altitude_m, -1, -1, 100000000),
      vertical: number(source.vertical_mps, 0, -5000, 5000),
      scan: number(source.scan_percent, 0, 0, 1),
      landingGear: Boolean(source.landing_gear),
      cargoScoop: Boolean(source.cargo_scoop),
      hardpoints: Boolean(source.hardpoints_deployed),
      shieldsKnown: Boolean(source.shields_known),
      shieldsUp: Boolean(source.shields_up),
      nightVision: Boolean(source.night_vision),
      inMainShip: Boolean(source.in_main_ship),
      lowFuel: Boolean(source.low_fuel),
      fuelScooping: Boolean(source.fuel_scooping),
      overheating: Boolean(source.overheating),
      silentRunning: Boolean(source.silent_running),
      neutronBoost: Boolean(source.neutron_boost),
      neutronBoostValue: number(source.neutron_boost_value, 0, 0, 10),
      fsdInjection: Boolean(source.fsd_injection),
      fsdInjectionPercent: number(source.fsd_injection_percent, 0, 0, 100),
    };
  }

  // Frontier reports the boost multiplier; three tiers keep the jet-cone
  // threads readable without pretending to plot the exact value.
  function boostTier(dynamics) {
    if (!dynamics?.neutronBoost) return 0;
    const value = Number(dynamics.neutronBoostValue) || 0;
    return value >= 5.5 ? 3 : value >= 3.5 ? 2 : 1;
  }

  // Theme tokens as the page resolved them; app.js passes the live values.
  const TOKENS = ['hud', 'orange', 'accent', 'green', 'yellow', 'red', 'text', 'muted', 'dim', 'bg', 'inset'];
  function cssPalette() {
    const style = getComputedStyle(document.documentElement);
    const palette = {};
    for (const name of TOKENS) palette[name] = style.getPropertyValue(`--${name}`).trim();
    palette.hud = palette.hud || palette.orange;
    palette.state = palette.hud;
    return palette;
  }

  // ---------------------------------------------------------------------
  // Painter: holographic strokes. Every line is laid twice, a faint wide
  // halo under a crisp core, and the surfaces composite additively so
  // crossing light brightens the way a projection does.
  // ---------------------------------------------------------------------

  class Painter {
    constructor(ctx) {
      this.ctx = ctx;
      this.W = 1;
      this.H = 1;
      this.alpha = 1;
      this.halo = 1;
    }

    finish(color, alpha = 1, width = 1, fill = 0) {
      const ctx = this.ctx;
      const a = clamp(alpha) * this.alpha;
      if (a <= .004) return;
      ctx.strokeStyle = color;
      if (fill > 0) {
        ctx.fillStyle = color;
        ctx.globalAlpha = a * fill;
        ctx.fill();
      }
      if (this.halo > .01 && width > .3) {
        ctx.globalAlpha = a * .15 * this.halo;
        ctx.lineWidth = width * 3 + 1.2;
        ctx.stroke();
      }
      ctx.globalAlpha = a;
      ctx.lineWidth = width;
      ctx.stroke();
    }

    line(x1, y1, x2, y2, color, alpha = 1, width = 1) {
      const ctx = this.ctx;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      this.finish(color, alpha, width);
    }

    poly(points, color, alpha = 1, width = 1, close = false, fill = 0) {
      if (!points.length) return;
      const ctx = this.ctx;
      ctx.beginPath();
      ctx.moveTo(points[0][0], points[0][1]);
      for (let index = 1; index < points.length; index += 1) ctx.lineTo(points[index][0], points[index][1]);
      if (close) ctx.closePath();
      this.finish(color, alpha, width, fill);
    }

    arc(x, y, rx, ry, start, end, color, alpha = 1, width = 1) {
      const ctx = this.ctx;
      ctx.beginPath();
      ctx.ellipse(x, y, Math.max(.2, rx), Math.max(.2, ry), 0, start, end);
      this.finish(color, alpha, width);
    }

    ring(x, y, rx, ry, segments, color, alpha = 1, width = 1, rotation = 0, fill = 0) {
      const ctx = this.ctx;
      ctx.beginPath();
      for (let index = 0; index < segments; index += 1) {
        const angle = rotation + index * TAU / segments;
        const px = x + Math.cos(angle) * rx;
        const py = y + Math.sin(angle) * ry;
        if (index) ctx.lineTo(px, py);
        else ctx.moveTo(px, py);
      }
      ctx.closePath();
      this.finish(color, alpha, width, fill);
    }

    rect(x, y, width, height, color, alpha = 1, fill = false) {
      const ctx = this.ctx;
      ctx.beginPath();
      ctx.rect(x, y, width, height);
      if (fill) {
        const a = clamp(alpha) * this.alpha;
        if (a <= .004) return;
        ctx.fillStyle = color;
        ctx.globalAlpha = a;
        ctx.fill();
      } else {
        this.finish(color, alpha, 1);
      }
    }

    dot(x, y, radius, color, alpha = 1) {
      const a = clamp(alpha) * this.alpha;
      if (a <= .004) return;
      const ctx = this.ctx;
      ctx.beginPath();
      ctx.arc(x, y, Math.max(.2, radius), 0, TAU);
      ctx.fillStyle = color;
      ctx.globalAlpha = a;
      ctx.fill();
    }

    // Soft light. Additive compositing makes the transparent rim add nothing.
    bloom(x, y, radius, color, alpha = 1) {
      const a = clamp(alpha) * this.alpha * Math.max(.35, this.halo);
      if (a <= .004 || radius <= .5) return;
      const ctx = this.ctx;
      const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
      gradient.addColorStop(0, color);
      gradient.addColorStop(1, 'transparent');
      ctx.fillStyle = gradient;
      ctx.globalAlpha = a;
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, TAU);
      ctx.fill();
    }

    // A glowing point with a hot centre.
    spark(x, y, radius, color, core, alpha = 1) {
      this.bloom(x, y, radius * 3.4, color, alpha * .6);
      this.dot(x, y, radius, core || color, alpha);
    }

    brackets(x, y, w, h, color, alpha = .7, length = 5, width = 1.1) {
      for (const sx of [-1, 1]) {
        for (const sy of [-1, 1]) {
          this.poly([[x + sx * (w - length), y + sy * h], [x + sx * w, y + sy * h],
            [x + sx * w, y + sy * (h - length * .8)]], color, alpha, width);
        }
      }
    }

    chevron(x, y, direction, color, alpha = 1, size = 4, width = 1.2) {
      this.poly([[x - direction * size, y - size], [x, y], [x - direction * size, y + size]],
        color, alpha, width);
    }

    ship(x, y, color, alpha = 1, scale = 1, direction = 1) {
      const s = scale * direction;
      this.poly([[x + 6 * s, y], [x - 4 * s, y - 3.5 * scale], [x - 1.5 * s, y],
        [x - 4 * s, y + 3.5 * scale], [x + 6 * s, y]], color, alpha, 1.2, false, .12);
    }

    globe(x, y, r, color, phase = 0, alpha = .7) {
      this.arc(x, y, r, r, 0, TAU, color, alpha, 1.2);
      this.arc(x, y, r, r * .31, 0, TAU, color, alpha * .4);
      this.arc(x, y, r * .7, r * .7, 0, TAU, color, alpha * .17);
      for (let index = 0; index < 3; index += 1) {
        const angle = phase * .32 + index * Math.PI / 3;
        this.arc(x, y, Math.max(.2, Math.abs(Math.cos(angle)) * r), r, 0, TAU,
          color, alpha * (.23 + .2 * Math.abs(Math.sin(angle))));
      }
    }

    // Energise a fixed housing without moving it. Overlapping edge fades keep
    // the contour's seam smooth as the light runs round.
    traceEdges(points, cycle, color, alpha = .8) {
      for (let index = 0; index < points.length; index += 1) {
        const next = points[(index + 1) % points.length];
        const light = Math.pow(wave(cycle - index / points.length), 4);
        this.line(points[index][0], points[index][1], next[0], next[1], color, light * alpha, 1.6);
      }
    }

    // Shaded facets need real occlusion, so rocks paint normally rather than
    // additively; the shadow fill hides whatever tumbles behind them.
    asteroid(x, y, size, color, phase, alpha, seed, shadow) {
      const a = clamp(alpha) * this.alpha;
      if (a <= .004) return;
      const mesh = ASTEROIDS[seed % ASTEROIDS.length];
      const yaw = phase * (seed % 2 ? -.31 : .24) + seed * 2.1;
      const pitch = phase * .17 + seed * .83;
      const cy = Math.cos(yaw), sy = Math.sin(yaw);
      const cx = Math.cos(pitch), sx = Math.sin(pitch);
      const points = mesh.vertices.map(([vx, vy, vz]) => {
        const xx = vx * cy + vz * sy;
        const zz = vz * cy - vx * sy;
        return [xx, vy * cx - zz * sx, vy * sx + zz * cx];
      });
      const ctx = this.ctx;
      ctx.save();
      ctx.globalCompositeOperation = 'source-over';
      ctx.lineWidth = .45;
      ctx.lineJoin = 'round';
      for (const [first, second, third] of mesh.faces) {
        const v = points[first], w = points[second], u = points[third];
        const ax = w[0] - v[0], ay = w[1] - v[1], az = w[2] - v[2];
        const bx = u[0] - v[0], by = u[1] - v[1], bz = u[2] - v[2];
        const nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx;
        if (nz <= 0) continue;
        // A fixed upper-left light reveals solid facets, not a wire cage.
        const light = clamp((-nx * .45 - ny * .65 + nz * .6) / Math.hypot(nx, ny, nz));
        ctx.beginPath();
        ctx.moveTo(x + v[0] * size, y + v[1] * size);
        ctx.lineTo(x + w[0] * size, y + w[1] * size);
        ctx.lineTo(x + u[0] * size, y + u[1] * size);
        ctx.closePath();
        ctx.globalAlpha = a;
        ctx.fillStyle = shadow;
        ctx.fill();
        ctx.globalAlpha = a * (.1 + light * .47);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.globalAlpha = a * (.14 + light * .35);
        ctx.strokeStyle = color;
        ctx.stroke();
      }
      ctx.restore();
    }

    // Draw a legacy instrument designed in a 120 x 36 space, centred on
    // (cx, cy) at the given height. Proportions, and so circles, are kept.
    glyph(cx, cy, height, draw) {
      const ctx = this.ctx;
      const scale = height / 36;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.scale(scale, scale);
      ctx.translate(-60, -18);
      draw();
      ctx.restore();
    }
  }

  // ---------------------------------------------------------------------
  // Shared fields: the wide backdrops that fill the deck around each
  // state's focal instrument.
  // ---------------------------------------------------------------------

  // Distant dust drifting past. Decorative only: never a positional plot.
  function dust(s, st, {count = 24, speed = .02, alpha = .35, direction = -1, color = st.c} = {}) {
    for (let index = 0; index < count; index += 1) {
      const t = fract(hash(index + 3) + st.p * speed * (.55 + hash(index + 7) * .9));
      const x = (direction < 0 ? 1 - t : t) * (s.W + 10) - 5;
      const y = 2 + hash(index + 11) * (s.H - 4);
      s.dot(x, y, .35 + hash(index + 19) * .6, color,
        alpha * (.3 + .7 * hash(index + 23)) * ends(t, .08));
    }
  }

  // Normal-space backdrop: two depths of dust, the nearer faster and longer.
  // Decorative only: the journal reports no speed or heading to draw.
  function starfield(s, st, alpha = 1) {
    dust(s, st, {count: 26, speed: .012, alpha: .45 * alpha});
    for (let index = 0; index < 7; index += 1) {
      const t = fract(hash(index + 61) + st.p * .05 * (.6 + hash(index + 62) * .8));
      const x = (1 - t) * (s.W + 20) - 10, y = 3 + hash(index + 63) * (s.H - 6);
      s.line(x, y, x + 3 + hash(index + 64) * 5, y, st.c, .5 * alpha * ends(t, .1), .9);
    }
  }

  // Perspective streaks radiating from a vanishing point.
  function streaks(s, st, {x, y = s.H / 2, count = 18, speed = .3, strength = .55, width = 1,
    twist = 0, color = st.c, spread = 1} = {}) {
    const rx = Math.max(x, s.W - x) * 1.1;
    const ry = s.H * .8 * spread;
    for (let index = 0; index < count; index += 1) {
      const t = fract(st.p * speed * (.75 + hash(index + 31) * .5) + hash(index + 23));
      const angle = hash(index + 51) * TAU + twist * Math.sin(st.p * .3 + index);
      const dx = Math.cos(angle), dy = Math.sin(angle);
      const far = t * t;
      const near = Math.max(0, t - .1 - t * .14) ** 2;
      s.line(x + dx * rx * near, y + dy * ry * near, x + dx * rx * far, y + dy * ry * far,
        color, strength * Math.sin(t * Math.PI), width * (.55 + t * .9));
    }
  }

  // Ground plane: rays converge on the horizon while rows roll toward the
  // viewer, or away on departure. Pace follows the real descent rate only.
  function terrain(s, st, {horizon = s.H * .36, x = s.W * .62, speed = 1, alpha = .3,
    depart = false, still = false, rows = 6, color = st.c} = {}) {
    for (let index = -9; index <= 9; index += 1) {
      s.line(x + index * 5, horizon, x + index * s.W * .085, s.H + 2, color, alpha * .5, .8);
    }
    for (let index = 0; index < rows; index += 1) {
      const t = still ? (index + .55) / rows : fract(st.terrain * .16 * speed + index / rows);
      const depth = (depart ? 1 - t : t) ** 2;
      const y = horizon + depth * (s.H - horizon);
      s.line(0, y, s.W, y, color, (still ? .62 : Math.sin(t * Math.PI)) * alpha, .9);
    }
    const ridge = [];
    for (let px = -6; px <= s.W + 6; px += 9) {
      ridge.push([px, horizon - 1 - (Math.max(0, Math.sin(px * .021 + 1.3)) * 3.4
        + Math.sin(px * .083 + .4) * 1.1 + 1.2)]);
    }
    s.poly(ridge, color, .5, 1);
  }

  // Elite's scanner disc: flattened range rings, a sweep and the ship at its
  // centre. It never plots contacts, because the journal does not report them.
  function radar(s, st, x, {sweep = .16, alpha = 1, color = st.c} = {}) {
    const y = s.H / 2 + 2;
    const rx = Math.min(s.W * .21, 86);
    const ry = s.H * .34;
    s.arc(x, y, rx, ry, 0, TAU, color, .5 * alpha, 1.1);
    s.arc(x, y, rx * .64, ry * .64, 0, TAU, color, .26 * alpha);
    s.arc(x, y, rx * .3, ry * .3, 0, TAU, color, .2 * alpha);
    s.line(x - rx, y, x + rx, y, color, .16 * alpha);
    s.line(x, y - ry, x, y + ry, color, .12 * alpha);
    if (sweep) {
      const angle = st.p * TAU * sweep;
      for (let trail = 0; trail < 6; trail += 1) {
        s.arc(x, y, rx, ry, angle - (trail + 1) * .14, angle - trail * .14, color,
          .75 * alpha * (1 - trail / 6), 1.5);
      }
      s.line(x, y, x + Math.cos(angle) * rx, y + Math.sin(angle) * ry, color, .32 * alpha);
    }
    s.poly([[x - 7, y + 4], [x, y - 5], [x + 7, y + 4], [x, y + 1]], color, .9 * alpha, 1.3, true, .16);
    return {x, y, rx, ry};
  }

  // Horizon wings either side of the scanner, as the cockpit frames it.
  function attitude(s, st, x, alpha = 1) {
    const y = s.H / 2;
    const rx = Math.min(s.W * .21, 86);
    for (const side of [-1, 1]) {
      const reach = Math.min(46, side < 0 ? x - rx - 10 : s.W - x - rx - 10);
      s.poly([[x + side * (rx + reach), y], [x + side * (rx + 10), y], [x + side * (rx + 5), y - 5]],
        st.c, .45 * alpha, 1.1);
      s.line(x + side * (rx + 12), y + 6, x + side * (rx + reach * .6), y + 6, st.c, .24 * alpha);
      s.line(x + side * (rx + 12), y - 7, x + side * (rx + reach * .4), y - 7, st.c, .16 * alpha);
    }
  }

  // Confirmed neutron and white-dwarf boosts add jet-cone threads to the
  // drive scenes; the tier shows, never an invented speed.
  function boostThreads(s, st, pal, x) {
    const tier = boostTier(st.d);
    for (let index = 0; index < tier; index += 1) {
      for (const side of [-1, 1]) {
        const points = [];
        for (let step = 0; step <= 24; step += 1) {
          const t = step / 24;
          points.push([lerp(4, x - 6, t), s.H / 2 + side * (2 + index * 2.2 + (1 - t) * (6 + index * 3))
            + Math.sin(t * 14 - st.p * 1.9 + index) * (1 - t) * 1.8]);
        }
        s.poly(points, pal.accent, .42, 1);
      }
    }
  }

  // ---------------------------------------------------------------------
  // Legacy focal instruments, drawn in their original 120 x 36 space and
  // placed by Painter.glyph. The wide fields around them are new.
  // ---------------------------------------------------------------------

  function carrierGlyph(s, st, variant = st.key) {
    const c = st.c, p = st.p;
    if (variant === 'carrier_transit') {
      for (const side of [-1, 1]) {
        s.poly([[62 + side * 15, 5], [62 + side * 39, 3], [62 + side * 54, 9]], c, .58, 1.5);
      }
    } else if (variant === 'carrier_arrival') {
      s.brackets(60, 18, 50, 14, c, .4);
      s.arc(62, 19, 53, 17, Math.PI * .15, Math.PI * .85, c, .48, 1.4);
    } else {
      s.poly([[16, 29], [32, 10], [97, 10], [108, 29]], c, .24);
      s.line(6, 32, 115, 32, c, .22);
    }
    if (variant === 'carrier_lockdown') {
      const close = smooth(Math.min(st.age / 3, 1));
      s.line(18, 4 + close * 10, 108, 4 + close * 10, c, .65);
      s.brackets(62, 19, 48 - close * 5, 16, c, .7);
      for (const side of [-1, 1]) {
        s.poly([[62 + side * 50, 3], [62 + side * 34, 9], [62 + side * 34, 28], [62 + side * 50, 33]], c, .64, 1.6);
      }
    } else if (variant === 'carrier_preparing') {
      for (let index = 0; index < 4; index += 1) {
        s.line(30 + index * 20, 8, 40 + index * 20, 8, c, .2 + .65 * wave(p * .35 - index / 4), 1.6);
      }
      for (const side of [-1, 1]) s.chevron(62 + side * 47, 18, -side, c, .65, 4);
    } else if (variant === 'carrier_deck' || variant === 'carrier_vicinity') {
      const deck = variant === 'carrier_deck';
      s.poly([[11, 31], [34, deck ? 27 : 24], [87, deck ? 27 : 24], [111, 31]], c, .58, 1.35);
      for (const x of [22, 99]) s.line(x, 24, x, 32, c, .6, 1.3);
      if (deck) s.brackets(63, 22, 27, 10, c, .47);
      else s.arc(63, 20, 44, 13, Math.PI * 1.1, Math.PI * 1.9, c, .44, 1.3);
    }
    s.poly([[14, 21], [26, 17], [42, 17], [45, 13], [91, 13], [105, 18], [105, 24], [32, 24]],
      c, .75, 1.2, true, .08);
    s.poly([[71, 13], [73, 6], [80, 6], [85, 13]], c, .65);
    s.line(77, 6, 77, 3, c, .65);
    for (let index = 0; index < 6; index += 1) {
      s.poly([[40 + index * 9, 18], [43 + index * 9, 16], [47 + index * 9, 18]], c, .35);
      const light = .18 + .7 * Math.pow(wave(p * .5 - index / 6), 3);
      s.line(40 + index * 9, 25, 46 + index * 9, 25, c, light, 1.5);
    }
  }

  function targetGlyph(s, st) {
    const c = st.c, p = st.p, key = st.key;
    if (key === 'target_clear') {
      for (const side of [-1, 1]) {
        s.poly([[60 + side * 14, 6], [60 + side * 38, 6], [60 + side * 46, 13]], c, .63, 1.4);
        s.poly([[60 + side * 14, 30], [60 + side * 38, 30], [60 + side * 46, 23]], c, .63, 1.4);
      }
      s.arc(60, 18, 10, 10, -.8, .8, c, .48, 1.3);
      s.arc(60, 18, 10, 10, Math.PI - .8, Math.PI + .8, c, .48, 1.3);
      s.line(44, 27, 76, 9, c, .62, 1.5);
      return;
    }
    const locked = smooth(st.age / 1.2);
    s.arc(60, 18, 10, 10, 0, TAU, c, .4);
    s.brackets(60, 18, 16 + (1 - locked) * 23, 13, c, .8);
    s.line(60, 3, 60, 7, c, .5);
    s.line(60, 29, 60, 33, c, .5);
    s.line(29, 18, 46, 18, c, .4);
    s.line(74, 18, 91, 18, c, .4);
    if (key === 'target_system') {
      s.ring(60, 18, 8, 8, 8, c, .65, 1.1, Math.PI / 8);
      s.spark(60, 18, 1.7, c, null, .84);
      for (const x of [21, 99]) s.poly([[x - 4, 18], [x, 14], [x + 4, 18], [x, 22]], c, .49, 1.1, true);
    } else if (key === 'target_body') {
      s.globe(60, 18, 7, c, p * .28, .76);
      s.arc(60, 18, 16, 7, Math.PI * .12, Math.PI * .88, c, .48, 1.2);
    } else if (key === 'target_signal') {
      s.dot(60, 18, 1.5, c, .8);
      for (const side of [-1, 1]) {
        for (let index = 0; index < 2; index += 1) {
          s.arc(60, 18, 14 + index * 9, 8 + index * 5, side < 0 ? Math.PI - .75 : -.75,
            side < 0 ? Math.PI + .75 : .75, c, .38 + .24 * wave(p * .3 - index * .25), 1.2);
        }
      }
    } else {
      s.dot(60, 18, 1.3, c, .8);
    }
    const track = p * TAU * .45;
    for (const offset of [0, Math.PI]) s.arc(60, 18, 10, 10, track + offset, track + offset + .65, c, .75, 1.5);
  }

  function threatGlyph(s, st) {
    const c = st.c, p = st.p, key = st.key;
    const heavy = key === 'heavy_combat', ground = key === 'srv_threat';
    const lock = .37 + .48 * wave(p * (heavy ? .82 : .57));
    // Threat geometry is an alarm frame, never a fabricated target count.
    s.ring(60, 18, heavy ? 28 : 24, 14, 8, c, heavy ? .69 : .51, heavy ? 1.5 : 1.2, Math.PI / 8);
    s.ring(60, 18, 14, 9, 8, c, .25 + lock * .35, 1.15, Math.PI / 8);
    s.poly([[60, 8], [69, 18], [60, 28], [51, 18]], c, .8, 1.5, true, .07);
    for (const side of [-1, 1]) {
      s.poly([[60 + side * 35, 4], [60 + side * 47, 4], [60 + side * 47, 12]], c, lock, 1.6);
      s.poly([[60 + side * 35, 32], [60 + side * 47, 32], [60 + side * 47, 24]], c, lock, 1.6);
      s.line(60 + side * 18, 18, 60 + side * 42, 18, c, .23 + lock * .36, 1.3);
    }
    if (ground) {
      s.poly([[10, 33], [30, 29], [48, 31], [60, 29], [77, 31], [94, 29], [111, 33]], c, .61, 1.2);
      for (const x of [24, 96]) s.line(x, 28, x, 34, c, .7, 1.2);
    } else if (heavy) {
      s.line(60, 1, 60, 6, c, lock, 1.8);
      s.line(60, 30, 60, 35, c, lock, 1.8);
      for (const side of [-1, 1]) s.chevron(60 + side * 52, 18, -side, c, lock, 4);
    }
  }

  function contactGlyph(s, st) {
    const c = st.c, p = st.p, key = st.key;
    const threat = key === 'signal_threat', drop = key === 'signal_drop';
    s.arc(60, 22, 45, 10, 0, TAU, c, .3);
    s.arc(60, 22, 22, 5, 0, TAU, c, .2);
    const x = 62 + Math.sin(p * .18) * 2, y = 14 + Math.cos(p * .2) * 2;
    s.line(x, 23, x, y, c, .4);
    if (key === 'unknown_contact') {
      s.ring(x, y, 5, 5, 6, c, .6);
      s.arc(x, y, 10, 8, p * .5, p * .5 + Math.PI, c, .4);
    } else {
      s.poly([[x, y - 4], [x + 4, y + 3], [x - 4, y + 3]], c, .8, 1.1, true, .13);
      s.brackets(x, y, 10 + (drop ? 4 * wave(p * .2) : 0), 8, c, .6);
    }
    if (threat) {
      // The USS threat level comes from the journal label, SIGNAL THREAT n.
      const level = clamp(Number(st.label.match(/\d+$/)?.[0] || 0), 0, 8);
      for (let index = 0; index < level; index += 1) {
        const px = 34 + index * 7;
        s.poly([[px - 2, 31], [px, 25], [px + 2, 31]], c, .42 + .35 * wave(p * .47 - index * .11), 1.2);
      }
    }
  }

  function panelGlyph(s, st) {
    const c = st.c, p = st.p, key = st.key;
    s.poly([[6, 5], [114, 5], [114, 31], [6, 31]], c, .2, 1, true, .015);
    if (key === 'comms_panel') {
      s.poly([[15, 10], [30, 10], [30, 22], [21, 22], [16, 27], [16, 22], [12, 22], [12, 10]], c, .6);
      for (let index = 0; index < 21; index += 1) {
        const amp = 2 + 10 * wave(p * .25 - index * .12) * Math.sin(index / 20 * Math.PI);
        s.line(39 + index * 3.5, 18 - amp, 39 + index * 3.5, 18 + amp, c, .4 + .25 * wave(p * .2 - index * .1));
      }
      for (let index = 0; index < 3; index += 1) s.dot(104 + index * 4, 9, 1.1, c, .31 + .39 * wave(p * .38 - index * .18));
    } else if (key === 'role_panel') {
      for (let index = 0; index < 3; index += 1) {
        const x = 30 + index * 30;
        s.dot(x, 12, 3.2, c, .7);
        s.poly([[x - 7, 26], [x - 6, 20], [x, 17], [x + 6, 20], [x + 7, 26]], c, .55);
      }
      s.brackets(60, 18, 13, 13, c, .25 + .6 * wave(p * .5));
      s.poly([[30, 12], [60, 6], [90, 12]], c, .39);
    } else if (key === 'station_services') {
      for (let index = 0; index < 4; index += 1) {
        const x = 25 + index * 24;
        s.ring(x, 18, 8, 8, 6, c, .35 + .3 * wave(p * .16 - index / 4), 1.1, Math.PI / 6);
        s.line(x - 3, 18, x + 3, 18, c, .6);
        if (index % 2) s.line(x, 15, x, 21, c, .6);
      }
      s.poly([[11, 30], [11, 8], [18, 8]], c, .58, 1.3);
      s.poly([[109, 30], [109, 8], [102, 8]], c, .58, 1.3);
    } else {
      const left = key === 'left_panel';
      s.poly(left ? [[18, 7], [100, 3], [100, 32], [18, 27]] : [[20, 3], [102, 7], [102, 27], [20, 32]],
        c, .55, 1, true, .04);
      if (left) {
        for (let index = 0; index < 4; index += 1) {
          const x = 29 + index * 18, y = 17 + Math.sin(index * 1.7) * 6;
          s.ring(x, y, 2.5, 2.5, 4, c, .75);
          if (index < 3) s.line(x + 3, y, x + 15, 17 + Math.sin((index + 1) * 1.7) * 6, c, .3);
          s.arc(x, y, 5.5, 5.5, 0, TAU, c, .7 * Math.pow(wave(p * .45 - index / 4), 4), 1.3);
        }
        s.poly([[8, 7], [15, 7], [15, 30], [8, 30]], c, .52, 1.3, true, .06);
      } else {
        for (let index = 0; index < 4; index += 1) {
          s.rect(31, 9 + index * 5, 5, 2, c, .4, true);
          s.line(41, 10 + index * 5, 82 - index * 4, 10 + index * 5, c, .28 + .3 * wave(p * .2 - index * .2));
        }
        s.poly([[105, 7], [112, 7], [112, 30], [105, 30]], c, .52, 1.3, true, .06);
      }
    }
  }

  function stationGlyph(s, st) {
    const c = st.c, p = st.p, key = st.key;
    const denied = ['docking_denied', 'docking_cancelled', 'docking_timeout'].includes(key);
    // Station approach is a gate. Clearance locks its letterbox and denial
    // visibly seals it; no pad location is implied.
    s.ring(60, 18, 27, 16, 8, c, .69, 1.2, Math.PI / 8);
    s.ring(60, 18, 18, 11, 8, c, .28, 1, Math.PI / 8);
    s.poly([[47, 14], [73, 14], [73, 22], [47, 22]], c, denied ? .44 : .81, 1.25, true, .05);
    for (let index = 0; index < 5; index += 1) {
      s.line(50 + index * 5, 15, 50 + index * 5, 17, c, .2 + .65 * Math.pow(wave(p * .5 - index / 5), 3), 1.4);
    }
    if (key === 'docking_cancelled') {
      for (const side of [-1, 1]) {
        s.poly([[60 + side * 8, 7], [60 + side * 19, 3], [60 + side * 31, 3]], c, .68, 1.5);
        s.poly([[60 + side * 8, 29], [60 + side * 19, 33], [60 + side * 31, 33]], c, .68, 1.5);
      }
    } else if (key === 'docking_timeout') {
      s.arc(60, 18, 32, 17, -2.6, -.3, c, .7, 1.6);
      s.arc(60, 18, 32, 17, .4, 2.3, c, .7, 1.6);
      s.line(60, 18, 60, 8, c, .8, 1.5);
      s.line(60, 18, 69, 20, c, .8, 1.5);
    } else if (denied) {
      const caution = .41 + .51 * wave(p * .38);
      s.line(46, 9, 74, 27, c, caution, 2);
      s.line(46, 27, 74, 9, c, caution, 2);
    } else if (key === 'docking_clearance') {
      const confirmed = st.label.includes('CLEARED');
      s.brackets(60, 18, 18, 9, c, confirmed ? .86 : .46);
      for (const side of [-1, 1]) s.line(60 + side * 32, 9, 60 + side * 32, 27, c, confirmed ? .65 : .28, 1.4);
    } else if (key === 'station_vicinity' || key === 'docking_assist') {
      s.brackets(60, 18, 35, 16, c, .52);
    } else {
      // A lit facet circuit runs round the station silhouette.
      const facets = Array.from({length: 8}, (_, index) => {
        const angle = Math.PI / 8 + index * TAU / 8;
        return [60 + Math.cos(angle) * 25, 18 + Math.sin(angle) * 16];
      });
      s.traceEdges(facets, p * .5, c, .88);
    }
  }

  function dockedGlyph(s, st) {
    const c = st.c, p = st.p;
    // Docked: pad clamps stay latched; no endless docking manoeuvre.
    s.poly([[25, 24], [44, 8], [83, 8], [102, 24], [83, 32], [44, 32]], c, .65, 1.1, true, .06);
    const pad = [[38, 24], [49, 14], [78, 14], [88, 24], [78, 28], [49, 28]];
    s.poly(pad, c, .32, 1, true);
    s.ship(63, 21, c, .85, 1.7);
    for (const x of [38, 88]) s.poly([[x - 3, 23], [x, 20], [x + 3, 23]], c, .75, 1.6);
    s.traceEdges(pad, p * .55, c);
    for (let index = 0; index < 4; index += 1) s.rect(47 + index * 10, 32, 4, 1.4, c, .3 + .5 * wave(p * .55 + index / 4), true);
  }

  function suitGlyph(s, st) {
    const c = st.c, p = st.p, label = st.label;
    const alarm = .43 + .43 * wave(p * .5);
    s.poly([[45, 30], [40, 23], [40, 12], [47, 4], [73, 4], [80, 12], [80, 23], [75, 30]], c, .78, 1.25);
    s.poly([[44, 14], [76, 14], [73, 23], [47, 23]], c, .55, 1, true, .06);
    if (label.startsWith('EXTREME')) {
      // Status distinguishes an extreme environment from a suit caution.
      for (const side of [-1, 1]) {
        const x = 60 + side * 28;
        s.poly([[x, 5], [x + side * 5, 10], [x, 15], [x + side * 5, 20], [x, 29]], c, alarm, 1.6);
      }
    }
  }

  function vehicleGlyph(s, st) {
    const c = st.c, p = st.p, key = st.key;
    const type = key === 'srv' ? 'scarab' : ['rhino', 'scorpion', 'nomad'].includes(key) ? key
      : ['rhino', 'scorpion', 'nomad', 'scarab'].includes(st.vehicleKey) ? st.vehicleKey : 'scarab';
    const brake = key === 'srv_handbrake';
    if (type === 'nomad') {
      s.poly([[32, 18], [41, 11], [79, 11], [88, 18], [78, 23], [42, 23]], c, .78, 1.2, true, .08);
      s.poly([[43, 11], [52, 6], [69, 6], [78, 11]], c, .5);
      for (const x of [40, 80]) {
        s.arc(x, 22, 8, 2.5, 0, TAU, c, .65);
        for (let index = 0; index < 3; index += 1) {
          const t = fract(p * .3 + index / 3);
          s.arc(x, brake ? 29 : 25 + t * 8, brake ? 9 : 5 + t * 7, 1.7, 0, TAU, c,
            brake ? .16 : Math.sin(t * Math.PI) * .5);
        }
      }
      return;
    }
    // Suspension motif: Rhino's load-bearing chassis, Scarab's articulated
    // axles and Scorpion's protected turret stay recognisable.
    const heavy = type === 'rhino', armed = type === 'scorpion';
    const wheels = heavy ? 4 : armed ? 2 : 3;
    const width = heavy ? 62 : armed ? 48 : 54;
    const x0 = 60 - width / 2, bob = brake ? 0 : Math.sin(p * .8) * .6;
    s.poly([[x0, 17 + bob], [x0 + 9, 11 + bob], [x0 + width - 11, 11 + bob], [x0 + width, 17 + bob],
      [x0 + width - 5, 23], [x0 + 5, 23]], c, .78, 1.2, true, .06);
    if (heavy) {
      s.poly([[44, 10], [44, 6], [72, 6], [80, 10]], c, .65);
      for (let index = 0; index < 4; index += 1) s.line(47 + index * 7, 8, 47 + index * 7, 17, c, .25);
    } else if (armed) {
      s.poly([[50, 11], [52, 6], [64, 6], [69, 11]], c, .65);
      s.line(61, 7, 83, 7, c, .8, 1.8);
    } else {
      s.poly([[49, 11], [51, 6], [60, 4], [65, 11]], c, .6);
    }
    for (let index = 0; index < wheels; index += 1) {
      const x = x0 + 5 + index * (width - 10) / (wheels - 1);
      const y = 26 + (brake ? 0 : Math.sin(p * .8 + index * 1.4) * .8);
      s.poly([[x - 3, 20], [x + 2, 23], [x, y]], c, .4);
      s.arc(x, y, 4, 4, 0, TAU, c, .75, 1.15);
      if (!brake) s.line(x - 2, y + Math.sin(p * .8 + index) * 2, x + 2, y - Math.sin(p * .8 + index) * 2, c, .35);
    }
  }

  // ---------------------------------------------------------------------
  // Deck scenes, one per state. Each fills the deck; `s` is the painter,
  // `st` the state (colour, dynamics, phase), `pal` the theme palette.
  // ---------------------------------------------------------------------

  function cruise(s, st, pal) {
    const c = st.c, cy = s.H / 2, vx = s.W * .76, key = st.key;
    const sco = key === 'supercruise_overcharge', assist = key === 'supercruise_assist';
    streaks(s, st, {x: vx, count: sco ? 30 : 20, speed: sco ? .5 : .28, strength: sco ? .72 : .5,
      width: sco ? 1.15 : 1});
    // A compression corridor converging on the heading marker ahead.
    for (const side of [-1, 1]) {
      s.poly([[-4, cy + side * s.H * .52], [vx * .42, cy + side * s.H * .32],
        [vx * .78, cy + side * s.H * .13], [vx - 7, cy + side * 2]], c, .36, 1.1);
      for (let index = 0; index < 5; index += 1) {
        const t = fract(st.p * (sco ? .46 : .28) + index / 5), k = t * t;
        const x = lerp(vx - 8, -12, k), y = cy + side * lerp(2, s.H * .52, k);
        const length = 3 + k * 12;
        s.line(x + length, y - side * k * 1.4, x - length, y + side * k * 1.4, c,
          Math.sin(t * Math.PI) * (sco ? .9 : .62), sco ? 1.6 : 1.2);
      }
    }
    s.poly([[vx - 7, cy], [vx, cy - 5], [vx + 7, cy], [vx, cy + 5]], c, .86, 1.3, true, .16);
    s.line(vx + 10, cy, s.W + 2, cy, c, .22);
    if (assist) {
      // Supercruise assist holds a clean guide lane onto the destination.
      for (const side of [-1, 1]) {
        s.poly([[8, cy + side * 1.5], [vx * .55, cy + side * 1.5], [vx * .7, cy + side * 5],
          [vx - 13, cy + side * 5]], pal.accent, .5, 1);
      }
      s.brackets(vx, cy, 15, 9, pal.accent, .78);
      s.spark(vx + 28, cy, 1.3, pal.accent, pal.text, .35 + .5 * wave(st.p * .5));
    }
    if (sco) {
      // Overcharge fractures the outer rails and runs hot down the axis.
      for (const side of [-1, 1]) {
        const points = [];
        for (let step = 0; step <= 30; step += 1) {
          const x = step * s.W / 30;
          points.push([x, cy + side * (s.H * .34 + Math.sin(step * .9 - st.p * 2.4) * 2.6 * (x / s.W))]);
        }
        s.poly(points, c, .42, 1.3);
      }
      for (let index = 0; index < 4; index += 1) {
        const t = fract(st.p * .7 + index / 4), k = t * t;
        s.line(lerp(vx - 10, 0, k), cy, lerp(vx - 10, 0, Math.max(0, k - .12)), cy, pal.text,
          Math.sin(t * Math.PI) * .7, 1.3);
      }
    }
    boostThreads(s, st, pal, vx);
  }

  function taxi(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .6;
    // A passenger shuttle in a paired lane: not the commander's own drive.
    streaks(s, st, {x: s.W * .8, count: 12, speed: .2, strength: .32});
    for (const side of [-1, 1]) {
      s.poly([[-4, cy + side * 15], [s.W * .3, cy + side * 11], [s.W * .55, cy + side * 7],
        [s.W + 4, cy + side * 7]], c, .45, 1.1);
      for (let index = 0; index < 5; index += 1) {
        const t = fract(st.p * .16 + index / 5), x = lerp(-10, s.W, t);
        const y = cy + side * lerp(13, 7, t);
        s.line(x - 7, y, x, y, c, Math.sin(t * Math.PI) * .6, 1.4);
      }
    }
    s.glyph(fx, cy, s.H * .92, () => {
      s.poly([[42, 18], [50, 13], [70, 13], [77, 18], [70, 23], [50, 23]], c, .8, 1.3, true, .1);
      s.poly([[53, 13], [55, 10], [67, 10], [70, 13]], c, .53);
      s.line(49, 18, 73, 18, c, .34);
      s.brackets(60, 18, 26, 12, c, .44);
    });
  }

  function charge(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .7, hyper = st.key === 'hyper_charge';
    // Decorative spool-up settles at a steady running intensity. It is never
    // a charge countdown or a prediction of when the jump will happen.
    const spool = .55 + .45 * smooth(st.age / 2.4);
    const step = 12;
    for (const side of [-1, 1]) {
      const reach = side < 0 ? fx - 18 : s.W - fx - 14;
      const count = Math.max(0, Math.floor(reach / step));
      for (let index = 0; index < count; index += 1) {
        const x = fx + side * (18 + index * step);
        // Brightness waves travel inward, feeding the core.
        const pulse = wave(st.p * (hyper ? 1.1 : .85) + index * .085);
        const edge = ends(1 - index / Math.max(1, count), .2);
        const h = (hyper ? 13 : 10) * (.45 + .55 * pulse) * spool * (1 - index / (count + 3) * .5);
        s.line(x, cy - h, x, cy + h, c, (.14 + .62 * pulse) * edge, 1.25);
        if (pulse > .82) s.dot(x, cy - h - 1.5, .9, pal.text, (pulse - .82) * 4 * edge);
      }
    }
    for (const side of [-1, 1]) {
      const points = [];
      for (let stepIndex = 0; stepIndex <= 40; stepIndex += 1) {
        const x = stepIndex / 40 * s.W, distance = Math.abs(x - fx) / s.W;
        points.push([x, cy + side * (3 + (1 - distance) * (hyper ? 12 : 9) * spool
          * (.7 + .3 * Math.sin(st.p * 3 + stepIndex * .6)))]);
      }
      s.poly(points, c, .16, .9);
    }
    for (let index = 0; index < 6; index += 1) {
      const side = index % 2 ? 1 : -1, t = fract(st.p * (hyper ? .5 : .36) + index / 6);
      const x = fx + side * lerp(side < 0 ? fx - 10 : s.W - fx, 12, t);
      s.spark(x, cy, 1.1, c, pal.text, Math.sin(t * Math.PI) * .85);
    }
    // Arcs jump between the vanes a few times a second.
    const flicker = Math.floor(st.p * 6);
    for (let index = 0; index < 2; index += 1) {
      const seed = flicker * 7 + index * 13;
      if (hash(seed) < .45) continue;
      const side = hash(seed + 1) < .5 ? -1 : 1;
      const x0 = fx + side * (22 + hash(seed + 2) * s.W * .28);
      const points = [];
      for (let stepIndex = 0; stepIndex <= 5; stepIndex += 1) {
        points.push([x0 + stepIndex * 5 * side, cy + (hash(seed + stepIndex + 4) - .5) * s.H * .6]);
      }
      s.poly(points, pal.text, .45 * spool, .8);
    }
    if (hyper) {
      s.ring(fx, cy, 16, 14, 6, c, .5, 1.15, Math.PI / 6);
      s.ring(fx, cy, 10 + wave(st.p * .44) * 1.6, 9, 6, c, .9, 1.35, Math.PI / 6 + st.p * .075);
    } else {
      s.poly([[fx - 14, cy], [fx - 7, cy - 7], [fx + 7, cy - 7], [fx + 14, cy], [fx + 7, cy + 7],
        [fx - 7, cy + 7]], c, .75, 1.25, true, .07);
      s.arc(fx, cy, 11, 7, st.p * .3, st.p * .3 + 2.3, c, .38 + .37 * spool, 1.8);
    }
    s.bloom(fx, cy, 16, c, .3 + .25 * spool);
    s.spark(fx, cy, 2 + wave(st.p * .55) * .8, c, pal.text, .95);
  }

  function tunnel(s, st, pal) {
    const c = st.c, cy = s.H / 2, opening = st.key === 'jumping';
    const vx = s.W * .72 + Math.sin(st.p * .17) * 6;
    // Witch-space: rings stream out of the vanishing point and twist.
    for (let index = 0; index < 8; index += 1) {
      const t = fract(st.p * .3 + index / 8), k = t * t;
      const points = [];
      for (let step = 0; step < 16; step += 1) {
        const angle = step * TAU / 16 + Math.sin(st.p * .12) * .12;
        const warp = opening ? 1 : 1 + .14 * Math.sin(angle * 3 + st.p * .45 + index);
        points.push([vx + Math.cos(angle) * (5 + k * s.W * .85) * warp,
          cy + Math.sin(angle) * (2 + k * s.H * 1.05) * warp]);
      }
      s.poly(points, c, Math.sin(t * Math.PI) * .5, .9 + t * .7, true);
    }
    for (let filament = 0; filament < 5; filament += 1) {
      const points = [];
      for (let step = 0; step <= 22; step += 1) {
        const r = step / 22, angle = filament * TAU / 5 + r * 2.6 + st.p * .22;
        points.push([vx + Math.cos(angle) * r * r * s.W * .8, cy + Math.sin(angle) * r * r * s.H * .95]);
      }
      s.poly(points, c, .2, .9);
    }
    streaks(s, st, {x: vx, count: 24, speed: .4, strength: .62, twist: .15});
    if (opening) {
      // The threshold splits once; the journal, not this animation, decides
      // when the ship has actually arrived.
      const t = smooth(st.age / 1.8);
      s.line(0, cy, s.W, cy, pal.text, (1 - t) * .7, 1 + t * 2);
      for (const side of [-1, 1]) {
        s.poly([[vx + side * (5 + t * 8), 4], [vx + side * (14 + t * 22), cy],
          [vx + side * (5 + t * 8), s.H - 4]], c, .78, 1.5);
      }
    } else {
      s.ring(vx, cy, 10, 8, 10, c, .8, 1.2, st.p * .08);
      s.arc(vx, cy, 5, 4, 0, TAU, c, .35);
    }
    s.bloom(vx, cy, 18, c, .4);
    s.spark(vx, cy, 1.8, c, pal.text, .9);
  }

  function arrival(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .7, settle = smooth(st.age / 2.2);
    // The arrival star glows in its own class colour, as the journal reports it.
    const star = st.starTone || c;
    streaks(s, st, {x: fx, count: 16, speed: .24 * (1 - settle * .7), strength: (1 - settle) * .7});
    s.bloom(fx, cy, 24 + wave(st.p * .2) * 3, star, .5);
    for (let index = 0; index < 16; index += 1) {
      const angle = index * TAU / 16 + st.p * .02;
      const inner = 8, outer = 10 + wave(st.p * .24 + index / 16) * 3.5;
      s.line(fx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner * .8,
        fx + Math.cos(angle) * outer, cy + Math.sin(angle) * outer * .8, star, .45);
    }
    s.dot(fx, cy, 5.5, star, .9);
    s.dot(fx - 1.4, cy - 1.4, 2.2, pal.text, .85);
    s.brackets(fx, cy, 17 + (1 - settle) * 40, 13, c, .35 + .4 * settle);
    const ring = clamp(st.age / 1.6);
    s.arc(fx, cy, 8 + ring * s.W * .55, 4 + ring * s.H * .7, 0, TAU, c, (1 - ring) * .6, 1.2);
    for (let index = 0; index < 6; index += 1) {
      s.line(10 + index * 8, s.H - 4, 14 + index * 8, s.H - 4, c, .2 + .3 * settle);
    }
  }

  function carrierScene(s, st, pal) {
    const c = st.c, cy = s.H / 2, key = st.key, fx = s.W * .6;
    if (key === 'carrier_transit') {
      // A broad hyperspace wake round a capital hull, not the ship's own FSD.
      for (let index = 0; index < 6; index += 1) {
        const t = fract(st.p * .23 + index / 6);
        s.ring(fx, cy + 1, 19 + t * s.W * .6, 3 + t * s.H * .7, 8, c, Math.sin(t * Math.PI) * .38, 1.2);
      }
    } else if (key === 'carrier_arrival') {
      streaks(s, st, {x: fx, count: 12, speed: .2, strength: (1 - smooth(st.age / 2)) * .8});
    } else {
      dust(s, st, {count: 16, speed: .01, alpha: .28});
    }
    s.glyph(fx, cy, s.H * .96, () => carrierGlyph(s, st));
  }

  function fss(s, st, pal) {
    const c = st.c, cy = s.H / 2, base = s.H - 8, x0 = 6, x1 = s.W * .62;
    const peaks = [.08, .19, .31, .44, .57, .7, .83, .94];
    const points = [];
    for (let index = 0; index <= 96; index += 1) {
      const u = index / 96;
      let amp = .6 + Math.sin(u * 61 + st.p * .7) * .35;
      peaks.forEach((at, n) => {
        amp += Math.exp(-(((u - at) / .018) ** 2)) * (5 + (n % 3) * 2.4 + wave(st.p * .26 + n * .37) * 2.2);
      });
      points.push([lerp(x0, x1, u), base - amp]);
    }
    // The resolved share of the band follows the journal's FSS progress.
    const cut = Math.max(1, Math.round(clamp(st.d.scan) * 96));
    s.poly(points.slice(0, cut + 1), c, .92, 1.3);
    if (cut < 96) s.poly(points.slice(cut), c, .28, 1);
    s.line(x0, base + 1, x1, base + 1, c, .3);
    for (let index = 0; index <= 24; index += 1) {
      const x = lerp(x0, x1, index / 24);
      s.line(x, base + 2, x, base + (index % 4 ? 3.5 : 5.5), c, .3);
    }
    const needle = lerp(x0, x1, wave(st.p * .12));
    s.line(needle, 3, needle, base, pal.text, .35, 1);
    s.bloom(needle, base - 6, 7, c, .35);
    const ax = s.W * .8;
    s.line(x1 + 4, cy, ax - 19, cy, c, .3);
    s.ring(ax, cy, 17, 15, 8, c, .48, 1.1, Math.PI / 8);
    s.arc(ax, cy, 9, 8, 0, TAU, c, .3);
    const focus = st.p * TAU * .2;
    s.arc(ax, cy, 17, 15, focus, focus + .96, c, .9, 1.6);
    s.poly([[ax - 3.5, cy], [ax, cy - 3.5], [ax + 3.5, cy], [ax, cy + 3.5]], c, .8, 1.2, true, .2);
    for (const side of [-1, 1]) s.line(ax + side * 21, cy, ax + side * 26, cy, c, .5);
  }

  function dss(s, st, pal) {
    const c = st.c, cy = s.H / 2, gx = s.W * .72, r = s.H * .42;
    s.globe(gx, cy, r, c, st.p, .72);
    s.arc(gx, cy, r * 1.35, r * .5, Math.PI * .96, Math.PI * 2.04, c, .45);
    const lx = s.W * .1, ly = s.H - 6, target = gx - r * .3;
    for (let index = 0; index < 3; index += 1) {
      const t = fract(st.p * .16 + index / 3), lift = 8 + index * 3, landing = cy - 2 + index * 2;
      const path = [];
      for (let step = 0; step <= 18; step += 1) {
        const u = step / 18;
        path.push([lerp(lx, target, u), lerp(ly, landing, u) - Math.sin(u * Math.PI) * lift]);
      }
      s.poly(path, c, .18);
      s.spark(lerp(lx, target, t), lerp(ly, landing, t) - Math.sin(t * Math.PI) * lift, 1.2, c,
        pal.text, Math.sin(t * Math.PI) * .9);
      if (t > .85) {
        const splash = (t - .85) / .15;
        s.arc(target + index * 3, landing, 2 + splash * 6, 1 + splash * 2.6, 0, TAU, c, (1 - splash) * .5);
      }
    }
    s.poly([[lx - 7, ly], [lx, ly - 4], [lx + 7, ly - 1], [lx, ly + 3]], c, .85, 1.1, true, .13);
    // Probes used against the efficiency target, both straight from the
    // journal's DSS EFFICIENT/COMPLETE label. Nothing is counted here.
    const probes = /(\d+)\s*\/\s*(\d+)/.exec(st.label);
    if (probes) {
      const used = Math.min(16, Number(probes[1])), goal = Math.min(16, Number(probes[2]));
      for (let index = 0; index < Math.max(used, goal); index += 1) {
        const x = lx + 14 + index * 7, lit = index < used;
        s.poly([[x, 6], [x + 2.5, 3], [x + 5, 6], [x + 2.5, 9]], index >= goal ? pal.yellow : c,
          lit ? .88 : .25, 1, true, lit ? .35 : 0);
      }
    }
    const bx = s.W * .91;
    if (st.label.startsWith('DSS EFFICIENT')) {
      s.ring(bx, cy, 10, 9, 6, pal.green, .8, 1.25, Math.PI / 6);
      s.poly([[bx - 5, cy], [bx - 1, cy + 4], [bx + 6, cy - 5]], pal.green, .95, 1.8);
    } else if (st.label.startsWith('DSS COMPLETE')) {
      s.ring(bx, cy, 10, 9, 8, c, .8, 1.3, Math.PI / 8);
      s.spark(bx, cy, 1.8, c, pal.text, .85);
    }
  }

  function galaxyMap(s, st, pal) {
    const c = st.c, gx = s.W * .6, gy = s.H / 2, spin = st.p * .05;
    for (let arm = 0; arm < 4; arm += 1) {
      const points = [];
      for (let index = 0; index <= 30; index += 1) {
        const r = 3 + index * (s.W * .3) / 30, angle = arm * Math.PI / 2 + index * .15 + .35 + spin;
        points.push([gx + Math.cos(angle) * r, gy + Math.sin(angle) * r * .24]);
      }
      s.poly(points, c, .4);
      for (let index = 3; index < points.length; index += 3) {
        s.dot(points[index][0], points[index][1], .9 + hash(index + arm * 7) * .6, c,
          .3 + .5 * wave(st.p * .15 - index * .04 - arm * .2));
      }
    }
    s.bloom(gx, gy, 16, c, .5);
    s.spark(gx, gy, 2.2, c, pal.text, .85);
    s.line(8, s.H - 4, s.W - 8, s.H - 4, c, .14);
  }

  function systemMap(s, st, pal) {
    const c = st.c, cy = s.H / 2, sx = s.W * .1, star = st.starTone || c;
    s.bloom(sx, cy, 15, star, .55);
    s.dot(sx, cy, 4, star, .92);
    // Local orbits and bodies laid out from the star: decorative, not a plot.
    const span = s.W * .82 / 5;
    for (let index = 0; index < 5; index += 1) {
      const x = sx + (index + 1) * span, radius = 7 + (index % 2) * 2.5;
      s.line(index ? x - span + radius + 2 : sx + 7, cy, x - radius - 2, cy, c, .22);
      s.globe(x, cy, 3 + (index % 2), c, st.p * .4, .66);
      s.arc(x, cy, radius, radius * .73, st.p * .16 + index, st.p * .16 + index + Math.PI * 1.2, c, .35);
      s.dot(x + Math.cos(st.p * .3 + index) * radius, cy + Math.sin(st.p * .3 + index) * radius * .73, .9, c, .66);
    }
  }

  function orrery(s, st, pal) {
    const c = st.c, ox = s.W * .52, oy = s.H / 2, star = st.starTone || c;
    s.bloom(ox, oy, 13, star, .5);
    s.dot(ox, oy, 3.3, star, .9);
    for (let index = 0; index < 5; index += 1) {
      const rx = 20 + index * s.W * .085, ry = Math.min(s.H * .47, 4 + index * 3.2);
      const angle = st.p * .28 / (index + 1) + index * 1.4;
      s.arc(ox, oy, rx, ry, 0, TAU, c, .3);
      s.dot(ox + Math.cos(angle) * rx, oy + Math.sin(angle) * ry, 1.8, c, .8);
    }
  }

  function powerMap(s, st, pal) {
    const c = st.c;
    // Powerplay territory is a linked influence lattice, unlike the galaxy
    // map's spiral. The cells are decorative, not a map of real territory.
    const columns = 6, cells = [];
    for (let row = 0; row < 2; row += 1) {
      for (let column = 0; column < columns; column += 1) {
        cells.push([s.W * (.08 + column * .84 / (columns - 1)) + (row ? 6 : 0),
          s.H * (row ? .74 : .26) + (hash(column + row * 9) - .5) * 4]);
      }
    }
    for (let column = 0; column < columns; column += 1) {
      s.line(...cells[column], ...cells[column + columns], c, .2);
      if (column < columns - 1) {
        s.line(...cells[column], ...cells[column + 1], c, .3);
        s.line(...cells[column + columns], ...cells[column + columns + 1], c, .3);
      }
    }
    const active = new Set([1, 2, 7, 8, 9]);
    cells.forEach(([x, y], index) => {
      const lit = active.has(index);
      s.ring(x, y, lit ? 8 : 5, lit ? 6 : 4, 6, c, lit ? .65 : .35, 1.1, Math.PI / 6);
      if (lit) s.dot(x, y, 1.3, c, .62 + .25 * wave(st.p * .22 - index * .1));
    });
    s.poly([cells[1], cells[2], cells[9], cells[8], cells[7]], c, .6, 1.4, true, .08);
  }

  function codex(s, st, pal) {
    const c = st.c, cx = s.W * .56, cy = s.H / 2;
    const w = Math.min(s.W * .3, 110), h = s.H * .42;
    s.poly([[cx - w, cy - h], [cx - 10, cy - h + 3], [cx, cy - h + 7], [cx + 10, cy - h + 3], [cx + w, cy - h],
      [cx + w, cy + h], [cx + 11, cy + h - 1], [cx, cy + h + 3], [cx - 11, cy + h - 1], [cx - w, cy + h]],
    c, .6, 1, true, .06);
    s.line(cx, cy - h + 7, cx, cy + h + 2, c, .4);
    for (let index = 0; index < 4; index += 1) {
      for (const side of [-1, 1]) {
        s.line(cx + side * 14, cy - h + 7 + index * 5, cx + side * (w - 8 - (index % 2) * 14), cy - h + 5 + index * 5,
          c, .22 + .4 * wave(st.p * .18 - index * .12));
      }
    }
    dust(s, st, {count: 14, speed: .008, alpha: .25});
  }

  function genericMap(s, st, pal) {
    const c = st.c, cy = s.H / 2;
    // An unspecified map: a navigable grid, not an invented star system.
    s.poly([[s.W * .08, 4], [s.W * .88, 4], [s.W * .95, 12], [s.W * .88, s.H - 4], [s.W * .08, s.H - 4],
      [s.W * .03, cy]], c, .45, 1.1, true, .03);
    for (let index = 0; index < 8; index += 1) {
      const x = s.W * (.14 + index * .1);
      s.line(x, 6, x - 5, s.H - 6, c, .2);
    }
    for (const y of [s.H * .33, cy, s.H * .72]) s.line(s.W * .05, y, s.W * .93, y, c, .18);
    const x = s.W * .5 + Math.sin(st.p * .21) * s.W * .25, y = cy + Math.cos(st.p * .17) * s.H * .2;
    s.poly([[x, y - 5], [x + 5, y], [x, y + 5], [x - 5, y]], c, .85, 1.3, true, .1);
    s.brackets(x, y, 13, 10, c, .42);
  }

  function target(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .66;
    dust(s, st, {count: 16, speed: .012, alpha: .26});
    // A range ladder closes toward the selected target.
    s.line(10, cy, fx - 36, cy, c, .18);
    for (let index = 0; index < 6; index += 1) {
      const t = fract(st.p * .12 + index / 6), x = lerp(10, fx - 36, t);
      s.line(x, cy - 3, x, cy + 3, c, Math.sin(t * Math.PI) * .5);
    }
    s.glyph(fx, cy, s.H * .96, () => targetGlyph(s, st));
  }

  function phenomena(s, st, pal) {
    const c = st.c, cy = s.H / 2;
    for (let ribbon = 0; ribbon < 4; ribbon += 1) {
      const points = [];
      for (let step = 0; step <= 48; step += 1) {
        const u = step / 48;
        points.push([u * s.W, cy + Math.sin(u * TAU * (1.2 + ribbon * .35) + st.p * (.3 + ribbon * .08) + ribbon)
          * (4 + ribbon * 3) * Math.sin(u * Math.PI)]);
      }
      s.poly(points, ribbon % 2 ? pal.accent : c, .2 + ribbon * .09, 1 + ribbon * .15);
    }
    dust(s, st, {count: 30, speed: .01, alpha: .35});
    for (let index = 0; index < 5; index += 1) {
      const x = s.W * (.15 + hash(index + 70) * .7), y = cy + (hash(index + 71) - .5) * s.H * .6;
      s.bloom(x, y, 7 + wave(st.p * .2 + index * .3) * 4, c, .2);
    }
    s.brackets(s.W * .5, cy, s.W * .46, s.H / 2 - 3, c, .25);
  }

  function exploration(s, st, pal) {
    const c = st.c, x = s.W * .62, y = s.H * .6, rx = s.W * .3, ry = s.H * .28;
    dust(s, st, {count: 18, speed: .015, alpha: .3});
    // A tilted holographic scanner dish, with soft echoes.
    s.arc(x, y, rx, ry, 0, TAU, c, .48);
    s.arc(x, y, rx * .62, ry * .62, 0, TAU, c, .23);
    s.line(x - rx - 10, y, x + rx + 10, y, c, .18);
    const angle = st.p * .38;
    s.poly([[x, y], [x + Math.cos(angle) * rx, y + Math.sin(angle) * ry],
      [x + Math.cos(angle + .38) * rx, y + Math.sin(angle + .38) * ry]], c, .4, 1, true, .12);
    for (let index = 0; index < 7; index += 1) {
      const px = x - rx * .8 + hash(index + 2) * rx * 1.6, py = y - 2 + hash(index + 8) * ry * .8;
      const h = 5 + hash(index) * 7;
      s.line(px, py, px, py - h, c, .3);
      s.dot(px, py - h, 1.2, c, .3 + .4 * wave(st.p * .2 - index * .14));
    }
  }

  function orbital(s, st, pal) {
    const c = st.c, depart = st.key === 'orbital_departure', alt = st.d.altitude;
    // The planet below. Higher orbits show more of its curve; altitude only
    // changes the view when the journal reports it.
    const height = alt < 0 ? .55 : clamp(Math.log10(1 + alt) / 6.3);
    const R = lerp(s.W * .9, s.W * .36, height), top = lerp(s.H * .3, s.H * .48, height);
    const cx = s.W * .6, centre = top + R;
    s.dot(cx, centre, R, c, .09);
    s.arc(cx, centre, R + 1.5, R + 1.5, Math.PI, TAU, c, .28, 3.2);
    s.arc(cx, centre, R, R, Math.PI, TAU, c, .8, 1.2);
    s.arc(cx, centre, R + 7, R + 7, Math.PI * 1.1, Math.PI * 1.9, c, .12 + .1 * wave(st.p * .23), 1);
    for (const inset of [6, 14, 26]) s.arc(cx, centre, R - inset, R - inset, Math.PI * 1.02, Math.PI * 1.98, c, .12);
    // Surface features turn beneath the ship: short craters along the limb.
    for (let index = 0; index < 14; index += 1) {
      const angle = Math.PI + fract(index / 14 + hash(index + 12) * .04 + st.p * .012 * (depart ? -1 : 1)) * Math.PI;
      const facing = Math.sin(angle - Math.PI);
      const depth = 5 + hash(index + 13) * 10;
      const x = cx + Math.cos(angle) * (R - depth), y = centre + Math.sin(angle) * (R - depth);
      s.arc(x, y, 2 + hash(index + 14) * 3, (1 + hash(index + 15)) * facing, 0, TAU, c, .3 * facing);
    }
    // Approach and departure keep to the right half, clear of the readout.
    const path = depart
      ? [[s.W * .5, top - 1], [s.W * .64, top - 5], [s.W * .8, top * .45], [s.W * .97, 2]]
      : [[s.W * .98, 2], [s.W * .88, top * .5 + 1], [s.W * .74, top - 4], [s.W * .6, top - 1.5]];
    s.poly(path, c, .62, 1.15);
    const t = fract(st.p * .15), leg = Math.min(2, Math.floor(t * 3)), f = t * 3 - leg;
    s.spark(lerp(path[leg][0], path[leg + 1][0], f), lerp(path[leg][1], path[leg + 1][1], f), 1.3, c, pal.text,
      Math.sin(t * Math.PI) * .9);
    if (depart) {
      for (let index = 0; index < 3; index += 1) {
        const u = .3 + index * .25;
        s.chevron(lerp(path[2][0], path[3][0], u), lerp(path[2][1], path[3][1], u) + 3, 1, c,
          .42 + .25 * wave(st.p * .3 - index * .2), 2.4);
      }
    } else {
      s.brackets(path[3][0], path[3][1], 11, 5, c, .65);
    }
  }

  function glide(s, st, pal) {
    const c = st.c, horizon = s.H * .3, fx = s.W * .62, cy = s.H / 2;
    terrain(s, st, {horizon, speed: 2.2, alpha: .34, x: fx});
    // Friction glow over the nose while gliding through atmosphere.
    for (let index = 0; index < 8; index += 1) {
      const t = fract(st.p * .5 + hash(index + 60)), y = 3 + hash(index + 61) * (horizon - 4);
      s.line(s.W * (1 - t), y, s.W * (1 - t) + 10 + t * 18, y, pal.hud, Math.sin(t * Math.PI) * .45, 1);
    }
    for (const side of [-1, 1]) {
      s.poly([[fx + side * 48, 3], [fx + side * 32, 11], [fx + side * 19, s.H - 10]], c, .47, 1.3);
    }
    for (let index = 0; index < 4; index += 1) {
      const t = fract(st.p * .18 + index / 4), w = 9 + t * t * 48, h = 2 + t * t * s.H * .42;
      s.poly([[fx - w, cy + h], [fx - w * .7, cy - h], [fx + w * .7, cy - h], [fx + w, cy + h]],
        c, Math.sin(t * Math.PI) * .6, 1.1);
    }
    s.poly([[fx - 13, cy], [fx - 4, cy], [fx, cy + 3], [fx + 4, cy], [fx + 13, cy]], c, .85, 1.4);
    gravityLoad(s, st, fx);
  }

  function surface(s, st, pal) {
    const c = st.c, key = st.key, fx = s.W * .62, cy = s.H / 2;
    const depart = key === 'surface_departure', hold = key === 'surface_hold';
    // Descent pace answers to the real vertical speed; nothing is estimated.
    const pace = clamp(.6 + Math.abs(st.d.vertical) / 90, .4, 2.4);
    terrain(s, st, {horizon: hold ? s.H * .42 : s.H * .34, speed: pace, still: hold, depart, alpha: .32, x: fx});
    if (hold) {
      for (const side of [-1, 1]) {
        s.poly([[fx + side * 30, 5], [fx + side * 24, 9], [fx + side * 24, s.H - 12], [fx + side * 30, s.H - 8]],
          c, .31 + .19 * wave(st.p * .27), 1.2);
      }
      s.brackets(fx, cy - 1, 19, 8, c, .65);
      s.line(fx - 12, cy - 1, fx - 4, cy - 1, c, .8);
      s.line(fx + 4, cy - 1, fx + 12, cy - 1, c, .8);
      s.dot(fx, cy - 1, 1.4, c, .75);
      s.arc(fx, s.H - 7, 16, 3, 0, TAU, c, .3);
      const stabiliser = st.p * TAU * .5;
      for (const offset of [0, Math.PI]) s.arc(fx, s.H - 7, 16, 3, stabiliser + offset, stabiliser + offset + .9, c, .8, 1.6);
    } else {
      // Descent ladder and ascent vector have different silhouettes.
      const direction = depart ? -1 : 1;
      for (const side of [-1, 1]) {
        s.poly(depart
          ? [[fx + side * 11, s.H - 9], [fx + side * 30, cy - 5], [fx + side * 46, 5]]
          : [[fx + side * 46, 5], [fx + side * 30, cy - 3], [fx + side * 11, s.H - 9]], c, .51, 1.3);
      }
      s.poly([[fx - 13, cy - 2], [fx - 4, cy - 2], [fx, cy + 1], [fx + 4, cy - 2], [fx + 13, cy - 2]], c, .8, 1.2);
      for (let index = 0; index < 3; index += 1) {
        const t = fract(st.terrain * .18 + index / 3), y = cy + direction * (2 + t * (s.H * .34));
        s.poly([[fx - 5, y - direction * 2], [fx, y], [fx + 5, y - direction * 2]], c, Math.sin(t * Math.PI) * .72, 1.1);
      }
    }
    gravityLoad(s, st, fx);
  }

  // Heavy gravity presses bars in from the sides, from the reported value.
  function gravityLoad(s, st, fx) {
    if (st.d.gravity <= 1.5) return;
    const load = clamp((st.d.gravity - 1.5) / 3);
    for (const side of [-1, 1]) {
      const x = fx + side * (58 - load * 6);
      s.line(x, 6, x, s.H - 6, st.c, .3 + .3 * load, 1.6);
      s.line(x + side * 3, 9, x + side * 3, s.H - 9, st.c, .15 + .2 * load, 1.2);
    }
  }

  function landed(s, st, pal) {
    const c = st.c, fx = s.W * .62, y = s.H * .62;
    terrain(s, st, {horizon: s.H * .3, still: true, alpha: .24, x: fx});
    // Pad shoes are latched; only the edge lights breathe while landed.
    s.poly([[fx - 34, s.H - 1], [fx - 24, y + 3], [fx + 24, y + 3], [fx + 34, s.H - 1]], c, .45, 1.4);
    const pad = [[fx - 25, y], [fx - 14, y - 6], [fx + 14, y - 6], [fx + 25, y], [fx + 14, y + 6], [fx - 14, y + 6]];
    s.poly(pad, c, .72, 1.2, true, .08);
    s.traceEdges(pad, st.p * .5, c);
    s.ship(fx, y - 1, c, .85, 1.35);
    for (const x of [fx - 17, fx + 17]) s.line(x, y + 1, x, y + 5, c, .8, 1.5);
    for (let index = 0; index < 10; index += 1) {
      const x = 10 + index * (s.W - 20) / 9;
      s.dot(x, s.H - 3, 1, c, .18 + .62 * Math.pow(wave(st.p * .45 - index / 10), 3));
    }
  }

  // One settlement structure: domes, masts, blocks and hangars, so the
  // skyline reads as a base rather than a row of identical towers.
  function structure(s, st, kind, x, w, h, base, index) {
    const c = st.c;
    if (kind === 0) {
      s.arc(x + w / 2, base, w / 2, Math.min(h, w * .7), Math.PI, TAU, c, .6, 1.1);
      s.line(x + w * .2, base - 1, x + w * .8, base - 1, c, .25);
    } else if (kind === 1) {
      s.poly([[x + w * .3, base], [x + w * .4, base - h], [x + w * .6, base - h], [x + w * .7, base]], c, .55);
      s.line(x + w / 2, base - h, x + w / 2, base - h - 5, c, .5);
      s.spark(x + w / 2, base - h - 6, .9, c, null, .3 + .6 * wave(st.p * .25 + index * .3));
    } else if (kind === 2) {
      s.poly([[x, base], [x, base - h * .55], [x + w, base - h * .55], [x + w, base]], c, .55, 1, false, .05);
      for (let row = 1; row < 3; row += 1) s.line(x + 2, base - h * .55 * row / 3, x + w - 2, base - h * .55 * row / 3, c, .18);
    } else {
      s.poly([[x - 2, base], [x + w * .25, base - h * .45], [x + w * .75, base - h * .45], [x + w + 2, base]], c, .55);
      s.line(x + w * .3, base - 2, x + w * .7, base - 2, c, .12 + .6 * Math.pow(wave(st.p * .5 - index * .2), 3), 1.5);
    }
  }

  function port(s, st, pal) {
    const c = st.c, base = s.H - 6, fx = s.W * .62, station = st.key === 'surface_station';
    s.line(0, base + 2, s.W, base + 2, c, .3);
    const count = Math.max(7, Math.round(s.W / 30));
    for (let index = 0; index < count; index += 1) {
      const x = 6 + index * (s.W - 12) / count, w = 12 + hash(index + 3) * 9;
      if (station && Math.abs(x + w / 2 - fx) < 38) continue;
      const h = 8 + hash(index + 5) * s.H * .5;
      structure(s, st, Math.floor(hash(index + 7) * 4), x, w, h, base, index);
    }
    // Perimeter lights chase along the base.
    for (let index = 0; index < 16; index += 1) {
      const x = 4 + index * (s.W - 8) / 15;
      s.dot(x, base + 2, .9, c, .15 + .6 * Math.pow(wave(st.p * .4 - index / 16), 4));
    }
    if (station) {
      s.arc(fx, base, 25, 5, Math.PI, TAU, c, .6);
      s.poly([[fx - 20, base + 2], [fx - 20, base - 7], [fx - 13, base - 10], [fx + 13, base - 10],
        [fx + 20, base - 7], [fx + 20, base + 2]], c, .67, 1.25);
      for (const x of [fx - 16, fx + 16]) s.line(x, base - 8, x, base, c, .55, 1.1);
    } else {
      for (const x of [9, s.W - 9]) s.poly([[x - 3, base], [x - 3, base - 10], [x, base - 15], [x + 3, base - 10], [x + 3, base]], c, .54, 1.2);
    }
  }

  function asteroids(s, st, pal) {
    const c = st.c;
    // Decorative parallax, not a claim about real asteroid positions. Every
    // crossing fades outside the scene; rotations use unwrapped time.
    for (let index = 0; index < 40; index += 1) {
      const t = fract(hash(index + 150) + st.p * .017);
      const x = (1 - t) * (s.W + 12) - 6;
      const y = s.H / 2 + (hash(index + 204) - .5) * s.H * .7 + (x - s.W / 2) * .03;
      s.dot(x, y, .25 + hash(index + 98) * .4, c, .16 * ends(t, .08));
    }
    const counts = [11, 8, 4], scale = s.H / 36;
    for (let layer = 0; layer < 3; layer += 1) {
      for (let index = 0; index < counts[layer]; index += 1) {
        const seed = layer * 11 + index;
        const t = fract(index / counts[layer] + hash(seed + 60) * .11 + st.p * [.022, .037, .057][layer]);
        const x = (s.W + 40) * (1 - t) - 20;
        const y = s.H * .2 + hash(seed + 33) * s.H * .6 + Math.sin(st.p * .22 + seed) * 1.3;
        const size = [2.4, 5.1, 8.5][layer] * scale + hash(seed + 29) * [1.7, 2.5, 3][layer];
        s.asteroid(x, y, size, c, st.p, ends(t, .1) * [.35, .7, .95][layer], seed, pal.bg);
      }
    }
  }

  function massLock(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .62;
    // Space bends round a nearby mass: ripples compress onto the lock.
    for (let index = 0; index < 7; index += 1) {
      const t = fract(st.p * .25 + index / 7), r = lerp(s.W * .55, 16, t);
      s.arc(fx, cy, r, Math.min(s.H * .48, r * .35), 0, TAU, c, Math.sin(t * Math.PI) * .28);
    }
    s.ring(fx, cy, 14, 11, 6, c, .6, 1.2);
    s.ship(fx, cy, c, .82, 1.1);
    for (const side of [-1, 1]) {
      s.poly([[fx + side * 33, 6], [fx + side * 24, 6], [fx + side * 19, cy], [fx + side * 24, s.H - 6],
        [fx + side * 33, s.H - 6]], c, .72, 1.6);
      for (let index = 0; index < 3; index += 1) {
        s.line(fx + side * (36 + index * 7), 13, fx + side * (33 + index * 7), s.H - 13, c,
          .25 + .2 * wave(st.p * .3 - index / 3));
      }
    }
  }

  function signal(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .66, drop = st.key === 'signal_drop';
    dust(s, st, {count: 14, speed: .012, alpha: .24});
    s.dot(fx, cy, 2, c, .8);
    s.bloom(fx, cy, 10, c, .3);
    for (let index = 0; index < 6; index += 1) {
      const t = fract(st.p * .2 + index / 6), r = 5 + (drop ? 1 - t : t) * s.W * .3;
      for (const [start, end] of [[-.9, .9], [Math.PI - .9, Math.PI + .9]]) {
        s.arc(fx, cy, r, Math.min(s.H * .48, r * .5), start, end, c, Math.sin(t * Math.PI) * .5);
      }
    }
    if (drop) {
      s.poly([[8, 7], [s.W * .2, 7], [s.W * .32, cy], [fx - 14, cy]], c, .65);
      s.chevron(fx - 16, cy, 1, c, .8, 3);
    } else {
      s.brackets(fx, cy, 31, 15, c, .3);
    }
  }

  function contact(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .62, key = st.key;
    if (key === 'unknown_contact') {
      // Something unexplained: slow interference bands, not a plotted contact.
      for (let index = 0; index < 5; index += 1) {
        const y = 4 + index * (s.H - 8) / 4 + Math.sin(st.p * .7 + index) * 2;
        s.line(0, y, s.W, y + Math.sin(st.p * .4 + index * 2) * 3, c, .1 + .12 * wave(st.p * .35 + index * .3), .8);
      }
    } else {
      dust(s, st, {count: 16, speed: .014, alpha: .26});
    }
    if (key === 'capital_contact') {
      s.glyph(fx, cy, s.H * .96, () => carrierGlyph(s, st, 'carrier_deck'));
      s.brackets(fx, cy, s.H * 1.5, s.H / 2 - 2, c, .65);
    } else {
      s.glyph(fx, cy, s.H * .96, () => contactGlyph(s, st));
    }
  }

  function threat(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .62;
    // A wide sweep round the alarm frame; it never plots a contact.
    const rx = s.W * .34, ry = s.H * .44, angle = st.p * TAU * .22;
    s.arc(fx, cy + 1, rx, ry, 0, TAU, c, .2);
    for (let trail = 0; trail < 6; trail += 1) {
      s.arc(fx, cy + 1, rx, ry, angle - (trail + 1) * .12, angle - trail * .12, c, .6 * (1 - trail / 6), 1.4);
    }
    s.glyph(fx, cy, s.H * .96, () => threatGlyph(s, st));
  }

  function interdiction(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .6, lost = st.key === 'interdicted';
    // The capture field closes in, the escape vector wanders, the tether pulls.
    for (let index = 0; index < 6; index += 1) {
      const t = fract(st.p * .17 + index / 6);
      s.arc(fx, cy, lerp(s.W * .6, 8, t), lerp(s.H * .8, 4, t), 0, TAU, c, Math.sin(t * Math.PI) * .3);
    }
    const tether = [];
    for (let step = 0; step <= 20; step += 1) {
      const u = step / 20;
      tether.push([lerp(4, fx - 16, u), cy + Math.sin(u * 9 - st.p * 3) * 3 * (1 - u)]);
    }
    s.poly(tether, c, .55, 1.2);
    const x = fx + Math.sin(st.p * .5) * (lost ? 40 : 22), y = cy + Math.cos(st.p * .5) * 5;
    s.brackets(x, y, 10, 8, c, .85);
    s.poly([[fx - 14, cy], [fx - 4, cy], [fx, cy + 3], [fx + 4, cy], [fx + 14, cy]], c, .85, 1.4);
    if (lost) {
      s.line(s.W * .06, 4, s.W * .12, s.H - 4, c, .6);
      s.line(s.W * .94, 4, s.W * .88, s.H - 4, c, .6);
    }
  }

  function heat(s, st, pal) {
    const c = st.c, fx = s.W * .62;
    const alarm = .43 + .43 * wave(st.p * .5);
    // Heat shimmer rises across the deck while the radiators glow.
    for (let index = 0; index < 9; index += 1) {
      const points = [], x0 = (index + .5) * s.W / 9;
      for (let step = 0; step <= 10; step += 1) {
        const u = step / 10;
        points.push([x0 + Math.sin(u * 6 + st.p * 2 + index) * 3, s.H - 2 - u * (s.H - 4)]);
      }
      s.poly(points, c, .16 + .2 * wave(st.p * .6 + index * .2), 1);
    }
    s.poly([[fx - 13, s.H - 4], [fx - 13, 7], [fx - 9, 3], [fx + 9, 3], [fx + 13, 7], [fx + 13, s.H - 4]], c, .7);
    for (let index = 0; index < 6; index += 1) {
      const y = s.H - 7 - index * (s.H - 12) / 6;
      s.line(fx - 9, y, fx + 9, y, c, .3 + .5 * wave(st.p * .25 - index * .1), 1.8);
    }
    alarmChevrons(s, st, alarm);
  }

  function alarmChevrons(s, st, alarm) {
    for (const side of [-1, 1]) {
      for (let index = 0; index < 3; index += 1) {
        const x = side < 0 ? 8 + index * 6 : s.W - 8 - index * 6;
        s.poly([[x, 3], [x - side * 3, 6], [x, 9]], st.c, alarm * (1 - index * .17), 1.4);
        s.poly([[x, s.H - 3], [x - side * 3, s.H - 6], [x, s.H - 9]], st.c, alarm * (1 - index * .17), 1.4);
      }
    }
  }

  function suit(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .62, label = st.label;
    const alarm = .43 + .43 * wave(st.p * .5);
    if (label.includes('OXYGEN')) {
      // Breath rings pulse outward from the visor.
      for (let index = 0; index < 5; index += 1) {
        const t = fract(st.p * .2 + index / 5);
        s.arc(fx, cy + 1, 4 + t * s.W * .3, 2 + t * s.H * .42, Math.PI * .08, Math.PI * .92, c, Math.sin(t * Math.PI) * .6, 1.2);
        s.arc(fx, cy + 1, 4 + t * s.W * .3, 2 + t * s.H * .42, Math.PI * 1.08, Math.PI * 1.92, c, Math.sin(t * Math.PI) * .4, 1.2);
      }
    } else if (label.includes('HEALTH')) {
      // A heart trace runs the width of the deck.
      const points = [];
      for (let step = 0; step <= 80; step += 1) {
        const x = step / 80 * s.W, beat = fract(x / s.W * 3 - st.p * .5);
        const y = beat < .08 ? cy - Math.sin(beat / .08 * Math.PI) * s.H * .38 : beat < .12 ? cy + 4 : cy;
        points.push([x, y]);
      }
      s.poly(points, c, alarm, 1.4);
    } else if (label.includes('COLD')) {
      for (let index = 0; index < 9; index += 1) {
        const t = fract(hash(index + 5) + st.p * .05), x = s.W * (1 - t), y = 5 + hash(index + 9) * (s.H - 10);
        const size = 2.5 + hash(index) * 2;
        s.line(x - size, y, x + size, y, c, alarm * .8 * ends(t));
        s.line(x, y - size, x, y + size, c, alarm * .8 * ends(t));
        s.line(x - size * .7, y - size * .7, x + size * .7, y + size * .7, c, alarm * .5 * ends(t));
      }
    } else {
      heat(s, st, pal);
      return;
    }
    s.glyph(fx, cy, s.H * .96, () => suitGlyph(s, st));
    alarmChevrons(s, st, alarm);
  }

  function jetCone(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .62;
    // Turbulent streams from the star's jet buffet the hull.
    for (let index = 0; index < 5; index += 1) {
      const points = [];
      for (let step = 0; step <= 40; step += 1) {
        const x = step / 40 * s.W;
        points.push([x, cy + (index - 2) * 5 + Math.sin(step * .45 - st.p + index) * 4]);
      }
      s.poly(points, c, .22 + index * .1, 1);
    }
    s.ring(fx, cy, 14, 12, 6, c, .8, 1.55, Math.PI / 6);
    s.poly([[fx - 7, cy], [fx - 2, cy - 5], [fx + 5, cy + 2], [fx + 8, cy - 2]], c, .84, 1.6);
    alarmChevrons(s, st, .43 + .43 * wave(st.p * .5));
  }

  function station(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .7, key = st.key;
    const denied = ['docking_denied', 'docking_cancelled', 'docking_timeout'].includes(key);
    if (!denied) {
      // Approach chevrons lead in toward the letterbox.
      for (let index = 0; index < 6; index += 1) {
        const t = fract(st.p * .2 + index / 6), x = lerp(8, fx - 40, t);
        s.chevron(x, cy, 1, c, Math.sin(t * Math.PI) * .72, 3.2);
      }
      s.line(8, cy, fx - 36, cy, c, .14);
    } else {
      // Refused: the approach lane breaks off and turns away.
      s.poly([[8, cy], [fx * .45, cy], [fx * .6, cy - 8], [fx * .7, cy - 8]], c, .45, 1.3);
      s.chevron(12, cy, -1, c, .8, 3);
    }
    if (key === 'docking_assist') {
      for (const side of [-1, 1]) s.poly([[8, cy + side * 9], [fx * .55, cy + side * 9], [fx - 34, cy + side * 3]], pal.accent, .45);
    }
    // Station traffic lights blink round the structure.
    for (let index = 0; index < 5; index += 1) {
      const angle = index * TAU / 5 + st.p * .05;
      s.dot(fx + Math.cos(angle) * 34, cy + Math.sin(angle) * 18, .9, c, .2 + .6 * wave(st.p * .3 + index * .2));
    }
    s.glyph(fx, cy, s.H * .96, () => stationGlyph(s, st));
  }

  function docked(s, st, pal) {
    const c = st.c, cy = s.H / 2;
    // Hangar lights chase along the deck while the pad holds the ship.
    for (let index = 0; index < 14; index += 1) {
      const x = 8 + index * (s.W - 16) / 13;
      s.line(x, 3, x + 5, 3, c, .12 + .5 * Math.pow(wave(st.p * .45 - index / 14), 3), 1.2);
      s.line(x, s.H - 3, x + 5, s.H - 3, c, .12 + .5 * Math.pow(wave(st.p * .45 - index / 14 + .5), 3), 1.2);
    }
    s.glyph(s.W * .6, cy, s.H * .96, () => dockedGlyph(s, st));
  }

  function maintenance(s, st, pal) {
    const c = st.c, cy = s.H / 2, reboot = st.key === 'system_reboot', k = s.H / 36;
    // Module bays along the deck. A repair sweep services each in turn; a
    // reboot brings them back one by one. Neither is a progress readout.
    const count = Math.max(6, Math.floor((s.W - 24) / 24)), step = (s.W - 24) / count;
    const sweep = fract(st.p * .18), mx = s.W * .5;
    for (let index = 0; index < count; index += 1) {
      const x = 12 + (index + .5) * step, u = (index + .5) / count;
      if (Math.abs(x - mx) < 22) continue;
      const activity = reboot ? (u < sweep ? .78 : .16) : .25 + .45 * wave(st.p * .2 - index / count);
      s.rect(x - 6, cy - 7, 12, 14, c, activity);
      if (reboot) {
        s.line(x - 3, cy, x + 3, cy, c, activity, 1.7);
      } else {
        s.line(x, cy - 3.5, x, cy + 3.5, c, activity, 1.5);
        s.line(x - 3.5, cy, x + 3.5, cy, c, activity, 1.5);
      }
    }
    const sx = lerp(6, s.W - 6, sweep);
    s.line(sx, 3, sx, s.H - 3, c, Math.sin(sweep * Math.PI) * .6);
    if (reboot) {
      s.poly([[mx - 8 * k, cy - 14 * k], [mx + 6 * k, cy - 14 * k], [mx + 1 * k, cy - 5 * k], [mx + 10 * k, cy - 5 * k],
        [mx - 6 * k, cy + 13 * k], [mx - 1 * k, cy + 2 * k], [mx - 10 * k, cy + 2 * k]], c, .85, 1.45, true, .1);
      alarmChevrons(s, st, .43 + .43 * wave(st.p * .5));
    } else {
      s.ring(mx, cy, 13, 12, 6, c, .55, 1.2, Math.PI / 6);
      s.line(mx, cy - 6, mx, cy + 6, c, .75, 1.5);
      s.line(mx - 6, cy, mx + 6, cy, c, .75, 1.5);
    }
  }

  function rover(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .62, key = st.key;
    const brake = key === 'srv_handbrake', assist = key === 'srv_drive_assist';
    // Parallax ridges roll past while the chassis rides its suspension.
    // Folded sines give peaks rather than waves, so the ground reads as rock.
    const ridge = (u, seed) => Math.abs(Math.sin(u * .019 + seed)) * 5
      + Math.abs(Math.sin(u * .053 + seed * 2)) * 2.4 + Math.sin(u * .13 + seed) * .7;
    const near = brake ? 0 : st.p * 16;
    for (let layer = 0; layer < 2; layer += 1) {
      const points = [], shift = layer ? near : near / 2;
      for (let x = -10; x <= s.W + 10; x += 6) {
        const u = x + shift;
        points.push([x, layer ? s.H * .86 - ridge(u * 1.8, 4) * .45 : s.H * .6 - ridge(u, 1) * 1.15]);
      }
      s.poly(points, c, layer ? .5 : .24, layer ? 1.1 : .9);
    }
    // Loose rocks pass at the ground's own pace.
    const span = s.W + 30;
    for (let index = 0; index < 6; index += 1) {
      const x = fract((hash(index + 80) * span - near) / span) * span - 15;
      const size = 1.4 + hash(index + 81) * 2.2, y = s.H * .86 + 1 + hash(index + 82) * 3;
      s.poly([[x - size, y], [x - size * .4, y - size * .9], [x + size * .6, y - size * .7], [x + size, y]],
        c, .45, .9, true, .15);
    }
    if (!brake) {
      for (let index = 0; index < 8; index += 1) {
        const x = fract((index / 8 * span - near * 1.3) / span) * span - 15;
        s.line(x, s.H - 2, x + 4, s.H - 2, c, .4 * ends(clamp((x + 15) / span), .15), 1.4);
      }
    }
    if (key === 'srv_turret') {
      // Turret view: the gun arc sweeps above the chassis.
      const angle = -Math.PI / 2 + Math.sin(st.p * .4) * .6;
      s.arc(fx, s.H - 4, s.W * .2, s.H * .8, Math.PI, TAU, c, .35);
      s.line(fx, s.H - 6, fx + Math.cos(angle) * s.W * .18, s.H - 6 + Math.sin(angle) * s.H * .7, c, .85, 1.8);
      s.brackets(fx + Math.cos(angle) * s.W * .18, s.H - 6 + Math.sin(angle) * s.H * .7, 7, 4, c, .6);
    }
    if (assist) {
      for (const side of [-1, 1]) s.poly([[fx + side * 70, s.H - 2], [fx + side * 50, cy], [fx + side * 50, 4]], pal.accent, .5);
    }
    if (brake) {
      // Latched calipers breathe; the wheels and chassis stay still.
      const latch = .2 + .65 * wave(st.p * .6);
      for (const side of [-1, 1]) {
        const x = fx + side * 56;
        s.poly([[x - side * 3, 8], [x, 11], [x, s.H - 11], [x - side * 3, s.H - 8]], c, latch, 1.8);
      }
    }
    if (key !== 'srv_turret') s.glyph(fx, cy, s.H * .96, () => vehicleGlyph(s, st));
  }

  function onFoot(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .62;
    // Footfalls cross the ground ahead of the visor frame.
    s.arc(fx, s.H + s.H * .5, s.W * .5, s.H * .9, Math.PI, TAU, c, .3);
    for (let index = 0; index < 6; index += 1) {
      const t = fract(st.p * .18 + index / 6), x = lerp(8, s.W - 8, t);
      const y = s.H - 6 - (index % 2) * 4;
      s.poly([[x - 2, y - 2], [x + 2, y - 2], [x + 3, y + 1], [x - 2, y + 2]], c, ends(t) * .6, 1, true, .2);
    }
    s.glyph(fx, cy, s.H * .96, () => {
      s.poly([[28, 9], [42, 4], [78, 4], [92, 9], [85, 28], [35, 28]], c, .55, 1.25, true, .04);
      s.poly([[38, 13], [48, 10], [72, 10], [82, 13], [77, 22], [43, 22]], c, .45, 1.1, true, .07);
      s.line(48, 16, 72, 16, c, .43);
      s.brackets(60, 18, 43, 14, c, .3);
      const scan = fract(st.p * .25);
      s.line(40 + scan * 40, 11, 40 + scan * 40, 21, c, Math.sin(scan * Math.PI) * .6);
    });
  }

  function carrierDeck(s, st, pal) {
    dust(s, st, {count: 14, speed: .008, alpha: .24});
    s.glyph(s.W * .6, s.H / 2, s.H * .96, () => carrierGlyph(s, st, 'carrier_deck'));
  }

  // The craft changing hands in a handoff, drawn at deck scale.
  function craft(s, st, x, y, direction = 1) {
    const c = st.c, key = st.key, k = s.H / 36 * 1.25;
    if (key.endsWith('crew')) {
      s.dot(x, y - 5 * k, 2 * k, c, .85);
      s.poly([[x, y - 2 * k], [x, y + 3 * k], [x - 3 * k, y + 7 * k]], c, .8);
      s.line(x, y + 3 * k, x + 3 * k, y + 7 * k, c, .8);
    } else if (key.endsWith('fighter') || key.endsWith('ship')) {
      s.ship(x, y, c, .9, (key.endsWith('fighter') ? 1.25 : 1.5) * k, direction);
      if (!key.endsWith('fighter')) s.arc(x, y, 13 * k, 7 * k, 0, TAU, c, .31, 1.1);
    } else {
      const size = (key.endsWith('rhino') ? 11 : 8) * k;
      s.poly([[x - size, y], [x - size + 3 * k, y - 5 * k], [x + size - 3 * k, y - 5 * k], [x + size, y]], c, .85);
      for (const side of [-1, 1]) s.arc(x + side * (size - 3 * k), y + 2 * k, 2.7 * k, 2.7 * k, 0, TAU, c, .7);
      if (key.endsWith('nomad')) s.arc(x, y + 6 * k, size, 1.5 * k, 0, TAU, c, .5);
    }
  }

  function handoff(s, st, pal) {
    const c = st.c, cy = s.H / 2, key = st.key;
    if (key.includes('switch')) {
      // Control passes along a link between two stations, not down a ramp.
      const left = s.W * .3, right = s.W * .74;
      for (const [x, side] of [[left, -1], [right, 1]]) {
        s.ring(x, cy, 15, 13, 6, c, .63, 1.25, Math.PI / 6);
        s.brackets(x, cy, 11, 9, c, .54);
        craft(s, st, x, cy + (key.endsWith('crew') ? 1 : 0), -side);
      }
      const link = (u) => cy + Math.sin(u * TAU * 3 - st.p * 2) * 4 * Math.sin(u * Math.PI);
      const points = [];
      for (let step = 0; step <= 30; step += 1) points.push([lerp(left + 17, right - 17, step / 30), link(step / 30)]);
      s.poly(points, c, .6, 1.3);
      const t = fract(st.p * .5);
      s.spark(lerp(left + 17, right - 17, t), link(t), 1.2, c, pal.text, Math.sin(t * Math.PI));
      return;
    }
    // A bay transfer runs once, then waits for the journal to confirm the
    // final vehicle state; the door and the craft do not loop.
    const board = key.includes('board'), t = smooth(st.age / 2), progress = board ? 1 - t : t;
    const flyer = key.endsWith('fighter') || key.endsWith('ship');
    const doorX = s.W * .24, y = flyer ? cy - 1 : s.H - 10;
    s.poly([[s.W * .03, s.H - 3], [s.W * .03, 4], [doorX - 6, 4], [doorX, 10], [doorX, s.H - 3]], c, .58, 1.1, false, .04);
    const opening = (board ? 1 - t : t) * s.H * .3;
    s.line(doorX, 11, doorX, cy - opening, c, .75, 1.5);
    s.line(doorX, cy + opening, doorX, s.H - 4, c, .75, 1.5);
    if (flyer) {
      s.line(doorX + 3, y, s.W - 8, y, c, .22);
    } else {
      s.poly([[doorX, s.H - 5], [doorX + 18, s.H - 3], [s.W - 6, s.H - 3]], c, .35);
    }
    const x = lerp(s.W * .13, s.W * .8, progress);
    craft(s, st, x, y, board ? -1 : 1);
    s.brackets(board ? s.W * .13 : s.W * .8, y, 14, 10, c, .2 + .45 * t);
    for (let index = 0; index < 4; index += 1) {
      s.line(s.W * .05 + index * 7, 2.5, s.W * .05 + index * 7 + 4, 2.5, c,
        .14 + .65 * Math.pow(wave(st.p * .5 - index / 4), 3), 1.6);
    }
  }

  function panel(s, st, pal) {
    const c = st.c, focus = Math.floor(fract(st.p * .06) * 5);
    // The panel's tab strip, the focus stepping along it, and a scroll bar.
    for (let index = 0; index < 5; index += 1) {
      const x = 8 + index * 17, lit = index === focus;
      s.poly([[x, 11], [x + 3, 5], [x + 14, 5], [x + 14, 11]], c, lit ? .85 : .3, 1, true, lit ? .22 : 0);
    }
    for (let row = 0; row < 3; row += 1) {
      s.line(8, 16 + row * 6, 90, 16 + row * 6, c, row === focus % 3 ? .5 : .14, 1.1);
    }
    const thumb = lerp(6, s.H - 14, wave(st.p * .08));
    s.line(s.W - 9, 5, s.W - 9, s.H - 5, c, .2);
    s.line(s.W - 9, thumb, s.W - 9, thumb + 8, c, .75, 2);
    s.glyph(s.W * .6, s.H / 2, s.H * .96, () => panelGlyph(s, st));
  }

  function flight(s, st, pal) {
    starfield(s, st);
    const scope = radar(s, st, s.W * .64);
    attitude(s, st, scope.x);
  }

  function assistOff(s, st, pal) {
    starfield(s, st);
    const scope = radar(s, st, s.W * .66, {sweep: .2});
    // The velocity vector drifts free of the nose: flight assist is off.
    const vx = scope.x + Math.sin(st.p * .38) * scope.rx * .9;
    const vy = scope.y + Math.cos(st.p * .31) * scope.ry * .8;
    s.poly([[scope.x, scope.y], [lerp(scope.x, vx, .45), vy], [vx, vy]], st.c, .5, 1.1);
    s.ring(vx, vy, 4.5, 4.5, 4, st.c, .9, 1.3, Math.PI / 4);
    attitude(s, st, scope.x, .7);
  }

  function silent(s, st, pal) {
    // Heat signature sealed: the scanner dims behind closing shutters.
    dust(s, st, {count: 14, speed: .012, alpha: .2});
    const scope = radar(s, st, s.W * .66, {sweep: .08, alpha: .45});
    const seal = .42 + .46 * wave(st.p * .42);
    for (const side of [-1, 1]) {
      const x = scope.x + side * (scope.rx + 6);
      s.poly([[x + side * 14, 3], [x, 9], [x, s.H - 9], [x + side * 14, s.H - 3]], st.c, seal, 1.8);
      s.poly([[x - side * 4, 11], [x - side * 10, 15], [x - side * 10, s.H - 15], [x - side * 4, s.H - 11]],
        st.c, seal * .6, 1.2);
    }
  }

  function fighter(s, st, pal) {
    starfield(s, st);
    const scope = radar(s, st, s.W * .66, {sweep: .22});
    s.brackets(scope.x, scope.y - 2, scope.rx + 16, s.H / 2 - 4, st.c, .54);
    for (const side of [-1, 1]) {
      s.chevron(scope.x + side * (scope.rx + 26), scope.y - 2, -side, st.c, .4 + .35 * wave(st.p * .6), 3.2);
    }
  }

  function multicrew(s, st, pal) {
    dust(s, st, {count: 18, speed: .02, alpha: .3});
    const scope = radar(s, st, s.W * .5, {sweep: .12, alpha: .7});
    for (const side of [-1, 1]) {
      const x = scope.x + side * (scope.rx + 30);
      s.ring(x, scope.y, 7, 8, 6, st.c, .7, 1.2);
      s.ring(x, scope.y, 10, 11, 6, st.c, .19 + .55 * wave(st.p * .42 + (side < 0 ? 0 : .5)), 1.3);
      // Crew links pass between the seats.
      const t = fract(st.p * .4 + (side < 0 ? 0 : .5));
      s.line(scope.x + side * 12, scope.y, x - side * 12, scope.y, st.c, .25);
      s.spark(lerp(scope.x + side * 12, x - side * 12, t), scope.y, 1, st.c, pal.text, Math.sin(t * Math.PI) * .85);
    }
  }

  function localArrival(s, st, pal) {
    const c = st.c, cy = s.H / 2 + 1, fx = s.W * .64, settle = smooth(st.age / 2.2);
    streaks(s, st, {x: fx, count: 12, speed: .2, strength: (1 - settle) * .6});
    const rx = s.W * .2, ry = s.H * .32;
    s.arc(fx, cy, rx, ry, 0, TAU, c, .35);
    const bearing = st.p * TAU * .32;
    s.arc(fx, cy, rx, ry, bearing, bearing + .8, c, .8, 1.5);
    s.ship(fx, cy, c, .9, 1.3);
    s.brackets(fx, cy, 22 + (1 - settle) * 30, 13, c, .35 + .4 * settle);
  }

  function evaded(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .5, settle = smooth(st.age / 2.2);
    // Two capture rails peel away from a stable ship.
    s.ship(fx, cy, c, .9, 1.3);
    for (const side of [-1, 1]) {
      s.poly([[8, cy + side * 3], [fx * .6, cy + side * 5], [fx + 20, cy + side * 9],
        [s.W - 6, cy + side * (s.H / 2 - 2)]], c, .58, 1.3);
      for (let index = 0; index < 4; index += 1) {
        const v = fract(st.p * .16 + index / 4);
        s.chevron(lerp(10, s.W - 10, v), cy + side * lerp(3, s.H / 2 - 3, v), 1, c, Math.sin(v * Math.PI) * .7, 2.6);
      }
    }
    s.brackets(fx, cy, 14 + (1 - settle) * 20, 9, c, .76);
  }

  function cooldown(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .7;
    // Radiator fins either side of the drive core shed their heat, the ones
    // nearest the core last. The fade is decorative, not a cooldown timer.
    const heat = 1 - smooth(st.age / 3.2);
    for (const side of [-1, 1]) {
      const count = Math.floor((side < 0 ? fx - 24 : s.W - fx - 16) / 8);
      for (let index = 0; index < count; index += 1) {
        const x = fx + side * (20 + index * 8), reach = index / Math.max(1, count);
        const warmth = clamp(heat * 1.4 - reach * .9);
        const h = 7 + (1 - reach) * 4;
        s.line(x, cy - h, x, cy + h, c, (.14 + .6 * warmth) * ends(1 - reach, .15), 1.4);
        if (warmth > .3) s.bloom(x, cy, 6, c, (warmth - .3) * .5);
      }
    }
    for (let index = 0; index < 8; index += 1) {
      const t = fract(st.p * .22 + index / 8), x = fx + (hash(index + 40) - .5) * s.W * .7;
      const warmth = clamp(heat * 1.4 - Math.abs(x - fx) / (s.W * .5));
      s.line(x, cy - 8 - t * (cy - 6), x + Math.sin(t * 6 + index) * 2, cy - 12 - t * (cy - 6), c,
        Math.sin(t * Math.PI) * (.1 + warmth * .5));
    }
    s.ring(fx, cy, 13, 12, 6, c, .65, 1.2, Math.PI / 6);
    s.ring(fx, cy, 7, 6, 6, c, .35 + .3 * heat, 1, Math.PI / 6);
    s.bloom(fx, cy, 14, c, .15 + .35 * heat);
  }

  function injection(s, st, pal) {
    const c = st.c, cy = s.H / 2, fx = s.W * .6;
    // Synthesis feeds the drive core: an armed buff, never a recipe meter.
    s.ring(fx, cy, 13, 11, 6, c, .72, 1.2, Math.PI / 6);
    s.ring(fx, cy, 6, 5, 6, c, .45, 1, Math.PI / 6);
    s.bloom(fx, cy, 14, c, .35);
    for (let index = 0; index < 3; index += 1) {
      const y = 5 + index * (s.H - 10) / 2;
      s.poly([[6, y], [fx * .55, y], [fx - 22, cy], [fx - 14, cy]], c, .3);
      const t = fract(st.p * .3 + index / 3);
      const x = lerp(6, fx - 14, t), yy = t < .6 ? y : lerp(y, cy, (t - .6) / .4);
      s.spark(x, yy, 1.1, c, pal.text, Math.sin(t * Math.PI) * .85);
    }
    const percent = st.d.fsdInjectionPercent;
    const level = percent >= 100 ? 3 : percent >= 50 ? 2 : 1;
    for (let index = 0; index < level; index += 1) s.chevron(fx + 26 + index * 9, cy, 1, pal.accent, .75, 4);
    s.line(fx + 30 + level * 9, cy, s.W, cy, c, .2);
  }

  const DECK = {
    flight, flight_assist_off: assistOff, silent_running: silent, fighter, multicrew, exploration,
    supercruise: cruise, supercruise_overcharge: cruise, supercruise_assist: cruise, taxi,
    fsd_charge: charge, hyper_charge: charge, hyperspace: tunnel, jumping: tunnel,
    arrival, local_arrival: localArrival, interdiction_evaded: evaded,
    fsd_cooldown: cooldown, fsd_injection: injection,
    carrier_preparing: carrierScene, carrier_lockdown: carrierScene, carrier_transit: carrierScene,
    carrier_arrival: carrierScene, carrier_vicinity: carrierScene, carrier_deck: carrierDeck,
    fss, dss, map: genericMap, galaxy_map: galaxyMap, system_map: systemMap, power_map: powerMap,
    orrery, codex, phenomena,
    target_lock: target, target_system: target, target_body: target, target_signal: target, target_clear: target,
    orbital_approach: orbital, orbital_departure: orbital, glide,
    surface_approach: surface, surface_hold: surface, surface_departure: surface,
    landed, surface_station: port, settlement_area: port,
    asteroid_field: asteroids, mass_lock: massLock, signal_lock: signal, signal_drop: signal,
    capital_contact: contact, unknown_contact: contact, signal_threat: contact,
    combat: threat, heavy_combat: threat, srv_threat: threat,
    interdiction, interdicted: interdiction,
    heat_critical: heat, suit_hazard: suit, jet_cone_damage: jetCone, system_reboot: maintenance,
    docked, station, station_vicinity: station, docking_clearance: station, docking_denied: station,
    docking_cancelled: station, docking_timeout: station, docking_assist: station, maintenance,
    srv: rover, scarab: rover, scorpion: rover, rhino: rover, nomad: rover,
    srv_handbrake: rover, srv_turret: rover, srv_drive_assist: rover, on_foot: onFoot,
    left_panel: panel, right_panel: panel, comms_panel: panel, role_panel: panel, station_services: panel,
  };
  const deckScene = (key) => DECK[key] || (key.startsWith('vehicle_') ? handoff : flight);

  // Graticule ticks frame the deck as an instrument, whatever it shows.
  function graticule(s, st) {
    for (let x = 12; x < s.W - 6; x += 12) {
      const major = Math.round(x / 12) % 4 === 0;
      s.line(x, 1, x, major ? 4 : 2.5, st.c, major ? .2 : .11, .8);
      s.line(x, s.H - 1, x, s.H - (major ? 4 : 2.5), st.c, major ? .2 : .11, .8);
    }
  }

  function paintDeck(s, st, pal) {
    graticule(s, st);
    deckScene(st.key)(s, st, pal);
  }

  // ---------------------------------------------------------------------
  // Bay aura: what the ship's hologram stands in. The portrait covers most
  // of the bay, so these read round its silhouette. The ship art faces its
  // nose down and to the right, so the world streams up and to the left.
  // ---------------------------------------------------------------------

  const NOSE = [.86, .5];

  const AURAS = {
    idle(b, st, pal, cx, cy) {
      const y = b.H * .74, rx = b.W * .42, ry = b.H * .12, angle = st.p * TAU * .12;
      b.arc(cx, y, rx, ry, 0, TAU, st.c, .22);
      b.arc(cx, y, rx, ry, angle - .7, angle, st.c, .5, 1.2);
    },
    cruise(b, st, pal, cx, cy) {
      const fast = st.key === 'supercruise_overcharge' ? 1.8 : 1;
      for (let index = 0; index < 12; index += 1) {
        const t = fract(st.p * .55 * fast * (.7 + hash(index + 3) * .6) + hash(index + 5));
        const offset = (hash(index + 9) - .5) * b.H * 1.3, along = lerp(-b.W * .75, b.W * .75, t);
        const x = cx - NOSE[0] * along + NOSE[1] * offset;
        const y = cy - NOSE[1] * along - NOSE[0] * offset;
        const length = 6 + hash(index + 11) * 10;
        b.line(x, y, x + NOSE[0] * length, y + NOSE[1] * length, st.c, Math.sin(t * Math.PI) * .42, 1);
      }
    },
    charge(b, st, pal, cx, cy) {
      const spool = .55 + .45 * smooth(st.age / 2.4);
      for (let index = 0; index < 4; index += 1) {
        const t = fract(st.p * .5 + index / 4);
        b.arc(cx, cy, lerp(b.W * .6, 6, t), lerp(b.H * .55, 4, t), 0, TAU, st.c, Math.sin(t * Math.PI) * .38 * spool, 1.1);
      }
      const flicker = Math.floor(st.p * 7);
      for (let index = 0; index < 2; index += 1) {
        const seed = flicker * 5 + index * 17;
        if (hash(seed) < .4) continue;
        const angle = hash(seed + 1) * TAU, r = b.W * .36;
        const points = [];
        for (let step = 0; step <= 4; step += 1) {
          const a = angle + (step - 2) * .12;
          points.push([cx + Math.cos(a) * (r + (hash(seed + step) - .5) * 6), cy + Math.sin(a) * (r * .55 + (hash(seed + step + 9) - .5) * 5)]);
        }
        b.poly(points, pal.text, .55, .8);
      }
    },
    tunnel(b, st, pal, cx, cy) {
      for (let index = 0; index < 6; index += 1) {
        const t = fract(st.p * .32 + index / 6), k = t * t;
        b.ring(cx, cy, 4 + k * b.W * .7, 3 + k * b.H * .7, 10, st.c, Math.sin(t * Math.PI) * .45, 1, st.p * .1 + index);
      }
    },
    flare(b, st, pal, cx, cy) {
      const star = st.starTone || st.c;
      b.bloom(cx + b.W * .12, cy - b.H * .05, b.W * .5, star, .32);
      for (let index = 0; index < 10; index += 1) {
        const angle = index * TAU / 10 + st.p * .03, r = b.W * (.34 + wave(st.p * .2 + index / 10) * .1);
        b.line(cx + Math.cos(angle) * b.W * .26, cy + Math.sin(angle) * b.H * .3, cx + Math.cos(angle) * r,
          cy + Math.sin(angle) * r * .6, star, .28);
      }
    },
    cool(b, st, pal, cx, cy) {
      const cooling = .35 + .65 * (1 - smooth(st.age / 3));
      for (let index = 0; index < 7; index += 1) {
        const t = fract(st.p * .25 + index / 7), x = b.W * (.12 + hash(index + 4) * .76);
        b.line(x, b.H - 6 - t * b.H * .8, x + Math.sin(t * 5 + index) * 2, b.H - 10 - t * b.H * .8, st.c, Math.sin(t * Math.PI) * cooling * .5);
      }
    },
    descent(b, st, pal, cx, cy) {
      // The ground plane under the hologram, closer as altitude falls.
      const alt = st.d.altitude;
      const near = alt < 0 ? .5 : 1 - clamp(Math.log10(1 + alt) / 5);
      const horizon = lerp(b.H * .92, b.H * .62, near);
      const depart = st.key.includes('departure');
      for (let index = -5; index <= 5; index += 1) b.line(cx + index * 4, horizon, cx + index * b.W * .14, b.H + 1, st.c, .18);
      for (let index = 0; index < 4; index += 1) {
        const t = fract(st.terrain * .2 + index / 4), depth = (depart ? 1 - t : t) ** 2;
        b.line(0, lerp(horizon, b.H, depth), b.W, lerp(horizon, b.H, depth), st.c, Math.sin(t * Math.PI) * .3);
      }
    },
    pad(b, st, pal, cx, cy) {
      const y = b.H * .8;
      const pad = [[cx - b.W * .4, y], [cx - b.W * .24, y - 5], [cx + b.W * .24, y - 5], [cx + b.W * .4, y],
        [cx + b.W * .24, y + 5], [cx - b.W * .24, y + 5]];
      b.poly(pad, st.c, .45, 1, true, .05);
      b.traceEdges(pad, st.p * .5, st.c, .7);
    },
    dock(b, st, pal, cx, cy) {
      b.ring(cx, cy, b.W * .46, b.H * .44, 8, st.c, .28, 1.1, Math.PI / 8 + st.p * .02);
      const facets = Array.from({length: 8}, (_, index) => {
        const angle = Math.PI / 8 + index * TAU / 8 + st.p * .02;
        return [cx + Math.cos(angle) * b.W * .46, cy + Math.sin(angle) * b.H * .44];
      });
      b.traceEdges(facets, st.p * .4, st.c, .6);
    },
    ground(b, st, pal, cx, cy) {
      const brake = st.key === 'srv_handbrake', shift = brake ? 0 : st.p * 12;
      const points = [];
      for (let x = -4; x <= b.W + 4; x += 6) points.push([x, b.H * .86 - Math.sin((x + shift) * .07) * 2.2]);
      b.poly(points, st.c, .45, 1);
      if (!brake) {
        for (let index = 0; index < 5; index += 1) {
          const t = fract(st.p * .5 + index / 5);
          b.bloom(b.W * (.3 - t * .25), b.H * .84 - t * 5, 3 + t * 6, st.c, (1 - t) * .25);
        }
      }
    },
    foot(b, st, pal, cx, cy) {
      for (let index = 0; index < 3; index += 1) {
        const t = fract(st.p * .3 + index / 3);
        b.arc(cx, b.H * .9, 6 + t * b.W * .4, 1.5 + t * 5, 0, TAU, st.c, (1 - t) * .45);
      }
    },
    sensor(b, st, pal, cx, cy) {
      for (let index = 0; index < 4; index += 1) {
        const t = fract(st.p * .3 + index / 4);
        b.arc(cx, cy, 6 + t * b.W * .55, 4 + t * b.H * .5, 0, TAU, st.c, Math.sin(t * Math.PI) * .35);
      }
    },
    rocks(b, st, pal, cx, cy) {
      for (let index = 0; index < 5; index += 1) {
        const t = fract(index / 5 + st.p * .035 + hash(index + 90) * .1);
        const x = (b.W + 20) * (1 - t) - 10, y = b.H * (.15 + hash(index + 91) * .7);
        b.asteroid(x, y, 2.4 + hash(index + 92) * 2.2, st.c, st.p, ends(t) * .6, index + 3, pal.bg);
      }
    },
    lock(b, st, pal, cx, cy) {
      // A lattice bubble: the ship's frame shift held by a nearby mass.
      for (let index = 0; index < 10; index += 1) {
        const angle = index * TAU / 10 + st.p * .04;
        const x = cx + Math.cos(angle) * b.W * .42, y = cy + Math.sin(angle) * b.H * .42;
        b.ring(x, y, 4, 3.5, 6, st.c, .25 + .3 * wave(st.p * .3 + index / 10), .9, Math.PI / 6);
      }
    },
    alarm(b, st, pal, cx, cy) {
      const flash = .3 + .55 * wave(st.p * .5);
      b.brackets(cx, cy, b.W * .46, b.H * .44, st.c, flash, 9, 1.4);
      b.arc(cx, cy, b.W * .38, b.H * .34, 0, TAU, st.c, flash * .4);
    },
    handoff(b, st, pal, cx, cy) {
      const t = fract(st.p * .5);
      b.line(cx, b.H - 4, cx, 4, st.c, .18);
      b.spark(cx, lerp(b.H - 4, 4, t), 1.2, st.c, pal.text, Math.sin(t * Math.PI) * .8);
    },
    panel(b, st, pal, cx, cy) {
      const x = lerp(4, b.W - 4, wave(st.p * .15));
      b.line(x, 4, x, b.H - 6, st.c, .25);
    },
  };

  function paintBay(b, st, pal) {
    const cx = b.W / 2, cy = b.H * .46, baseY = b.H - 4;
    // The projection plinth the hologram stands on.
    b.bloom(cx, baseY, b.W * .42, st.c, .2);
    b.arc(cx, baseY, b.W * .36, 3, 0, TAU, st.c, .45, 1);
    b.arc(cx, baseY, b.W * .2, 1.6, 0, TAU, st.c, .3, 1);
    (AURAS[st.aura] || AURAS.idle)(b, st, pal, cx, cy);
  }

  // Ship systems read round the portrait, from Status.json flags only.
  function bayOverlays(b, st, pal, clockSeconds) {
    const d = st.d, cx = b.W / 2, cy = b.H * .46;
    const ownShip = d.inMainShip && !['ground', 'foot', 'handoff'].includes(st.aura);
    if (ownShip && d.shieldsKnown) {
      // Shield rings, as the cockpit's ship hologram draws them. Down, they
      // break up and flicker red.
      const segments = 18, rx = b.W * .47, ry = b.H * .2, y = b.H * .62;
      for (let index = 0; index < segments; index += 1) {
        const start = index * TAU / segments, end = start + TAU / segments * .7;
        const on = d.shieldsUp
          ? .22 + .38 * Math.pow(wave(st.p * .3 - index / segments), 3)
          : (hash(index + Math.floor(clockSeconds * 8) * 3) > .55 ? .6 : .06);
        b.arc(cx, y, rx, ry, start, end, d.shieldsUp ? pal.accent : pal.red, on, 1.2);
      }
    }
    if (ownShip && d.fuelScooping) {
      // Stellar plasma streams into the scoop at the nose.
      const tx = cx + b.W * .24, ty = cy + b.H * .18;
      for (let index = 0; index < 9; index += 1) {
        const t = fract(st.p * .7 + index / 9);
        const sx = b.W + 4, sy = b.H * (.25 + hash(index + 4) * .7);
        b.spark(lerp(sx, tx, t), lerp(sy, ty, t * t), .8, pal.green, pal.text, Math.sin(t * Math.PI) * .75);
      }
      b.bloom(tx, ty, 9, pal.green, .35 + .2 * wave(st.p * .8));
    }
    if (ownShip && d.cargoScoop) {
      const y = b.H * .74;
      b.poly([[cx - 10, b.H - 2], [cx - 3, y], [cx + 3, y], [cx + 10, b.H - 2]], st.c, .35 + .2 * wave(st.p), 1);
    }
    if (d.overheating) {
      // Heat haze rises off the hull.
      for (let index = 0; index < 8; index += 1) {
        const t = fract(st.p * .45 + index / 8), x = b.W * (.2 + hash(index + 30) * .6);
        b.line(x, cy + 8 - t * b.H * .5, x + Math.sin(t * 7 + index) * 2.5, cy + 4 - t * b.H * .5, pal.red,
          Math.sin(t * Math.PI) * .5, 1);
      }
    }
    if (ownShip && d.hardpoints) {
      const nx = cx + b.W * .34, ny = cy + b.H * .26;
      b.chevron(nx, ny, 1, pal.hud, .75, 2.6);
      b.chevron(nx + 5, ny + 3, 1, pal.hud, .5, 2.6);
    }
  }

  // Deck overlays for pilot-selected systems that change what is on screen.
  function deckOverlays(s, st, pal) {
    const d = st.d;
    if (d.inMainShip && d.hardpoints) {
      for (const side of [-1, 1]) s.chevron(side < 0 ? 9 : s.W - 9, s.H / 2, side, pal.hud, .55, 3);
    }
    if (d.nightVision) {
      const x = fract(st.p * .5 + .2) * s.W;
      s.line(x, 2, x, s.H - 2, pal.green, .3);
    }
    if (d.inMainShip && d.lowFuel) {
      const flash = .35 + .45 * wave(st.p * 2);
      s.poly([[s.W - 16, s.H - 5], [s.W - 12, s.H - 11], [s.W - 8, s.H - 5]], pal.red, flash, 1.2, true, .2);
    }
  }

  // ---------------------------------------------------------------------
  // One-shot journal event accents over the deck.
  // ---------------------------------------------------------------------

  const EVENT_GROUP = new Map(Object.entries({
    route: ['route_set', 'route_clear', 'route_target', 'route_divert'],
    scan: ['fss_progress', 'fss_signal', 'body_scan', 'signals', 'survey_complete', 'mapping_complete',
      'bio_sample', 'codex', 'valuable_discovery', 'first_discovery', 'footfall_candidate', 'data_sale'],
    honk: ['honk'],
    dss: ['dss_efficiency', 'dss_complete'],
    resource: ['prospector_scan', 'prospector_rich', 'prospector_core', 'mining_refined'],
    dock: ['dock', 'dock_request', 'dock_denied', 'undock'],
    surface: ['body_approach', 'planet_clear', 'touchdown', 'liftoff'],
    maintenance: ['maintenance', 'system_reboot'],
    warning: ['warning', 'interdiction', 'jet_cone_damage'],
    arrival: ['arrival', 'arrival_valuable', 'arrival_neutron', 'arrival_white_dwarf', 'carrier_arrival'],
    drive: ['jump_charge', 'supercruise_enter', 'supercruise_exit', 'supercruise_drop', 'signal_drop'],
    vehicle: ['vehicle_deploy', 'vehicle_board', 'vehicle_switch'],
    release: ['interdiction_clear'],
    wake: ['wake'],
  }).flatMap(([group, kinds]) => kinds.map((kind) => [kind, group])));
  const EVENT_SECONDS = {honk: 1.5, arrival: 1.6, warning: 1.4, wake: 1.4};

  function eventColour(event, pal, fallback) {
    const tone = event.tone === 'muted' ? 'dim' : event.tone;
    return pal[tone] || fallback;
  }

  function drawEvent(s, event, t, c, pal) {
    // Accents launch at once and settle, so the cue lands with the event.
    const p = 1 - (1 - t) ** 2, fade = 1 - smooth((t - .55) / .45), y = s.H / 2;
    const left = 4, right = s.W - 4, at = (u) => lerp(left, right, u);
    const group = EVENT_GROUP.get(event.kind) || 'other';
    if (group === 'honk') {
      // The discovery scanner's pulse sweeps out through the system.
      for (let index = 0; index < 3; index += 1) {
        const r = clamp(p * 1.15 - index * .12);
        if (r <= 0) continue;
        s.arc(0, y, r * s.W * 1.05, r * s.H * 1.3, -Math.PI / 2, Math.PI / 2, c, fade * (1 - r * .6) * (.9 - index * .2), 1.6 - index * .3);
      }
    } else if (group === 'route') {
      const head = at(p);
      s.line(Math.max(left, head - s.W * .18), y - 7, head, y - 7, c, fade, 1.8);
      s.spark(head, y - 7, 1.3, c, pal.text, fade);
      for (const u of [.16, .38, .62, .84]) s.dot(at(u), y - 7, 1.1, c, fade * (u < p ? .8 : .3));
    } else if (group === 'dss') {
      const rings = event.kind === 'dss_efficiency' ? 3 : 2;
      for (let index = 0; index < rings; index += 1) {
        const radius = 5 + ((p + index / rings) % 1) * 27;
        s.arc(s.W * .72, y, radius, radius * .34, 0, TAU, c, fade * (.65 - index * .13), 1.25);
      }
    } else if (group === 'scan') {
      const x = at(p);
      s.line(x, 2, x, s.H - 2, c, fade * .92, 1.8);
      for (let index = 0; index < 3; index += 1) {
        const radius = 4 + (p + index * .14) * 17;
        s.arc(x, y, radius, radius * .34, 0, TAU, c, fade * (.55 - index * .12));
      }
    } else if (group === 'resource') {
      const x = at(p);
      s.poly([[x - 5, y], [x - 2, y - 5], [x + 4, y - 3], [x + 6, y + 2], [x, y + 6], [x - 5, y]], c, fade, 1.4);
      s.line(Math.max(left, x - s.W * .12), y, x - 6, y, c, fade * .6, 1.4);
    } else if (group === 'dock') {
      const opening = event.kind === 'undock' ? p : 1 - p, spread = 7 + opening * s.W * .3;
      for (const side of [-1, 1]) s.line(s.W * .62 + side * spread, 3, s.W * .62 + side * spread, s.H - 3, c, fade, 1.5);
    } else if (group === 'surface') {
      const outbound = event.kind === 'liftoff' || event.kind === 'planet_clear';
      const travel = outbound ? p : 1 - p, spread = 5 + travel * s.W * .3, cx = s.W * .62;
      s.arc(cx, y + 12, s.W * .34, 10, Math.PI * 1.08, Math.PI * 1.92, c, fade * .58, 1.2);
      s.poly([[cx - spread - 5, y - 8], [cx - spread, y - 8], [cx - spread, y - 2]], c, fade * .88, 1.5);
      s.poly([[cx + spread + 5, y + 8], [cx + spread, y + 8], [cx + spread, y + 2]], c, fade * .88, 1.5);
      const my = outbound ? y + 5 - p * 12 : y - 7 + p * 12, dir = outbound ? -1 : 1;
      s.poly([[cx - 4, my - dir * 2], [cx, my + dir * 2], [cx + 4, my - dir * 2]], c, fade, 1.5);
    } else if (group === 'maintenance') {
      const columns = 8;
      for (let index = 0; index < columns; index += 1) {
        const x = left + index * (right - left) / columns;
        const active = index <= Math.floor(p * columns);
        s.rect(x + 2, y - 5, (right - left) / columns - 4, 10, c, fade * (active ? .5 : .15), active);
      }
    } else if (group === 'warning') {
      const flash = .35 + .65 * wave(t * 4);
      for (const yy of [1, s.H - 1]) s.line(0, yy, s.W, yy, c, fade * flash, 2);
      for (const xx of [1, s.W - 1]) s.line(xx, 0, xx, s.H, c, fade * flash, 2);
    } else if (group === 'arrival') {
      const cx = s.W * .7, flare = event.kind === 'arrival_neutron';
      s.bloom(cx, y, 8 + p * s.W * .3, c, fade * .45);
      s.arc(cx, y, 6 + p * s.W * .5, 3 + p * s.H * .6, 0, TAU, c, fade * .7, 1.5);
      if (flare) {
        // Neutron stars fire twin jets along their axis.
        s.line(cx - p * s.W * .5, y + p * 10, cx + p * s.W * .5, y - p * 10, pal.text, fade * .7, 1.4);
      }
    } else if (group === 'drive') {
      const entering = event.kind === 'supercruise_enter' || event.kind === 'jump_charge';
      for (let index = 0; index < 5; index += 1) {
        const u = clamp(p * 1.2 - index * .05), x = entering ? at(1 - u) : at(u);
        s.line(x, y - 9 + index * 4.5, x + (entering ? 18 : -18), y - 9 + index * 4.5, c, fade * .7, 1.3);
      }
    } else if (group === 'vehicle') {
      const cx = s.W * .56;
      s.brackets(cx, y, 12 + (1 - p) * 30, 12, c, fade, 6, 1.4);
    } else if (group === 'release') {
      for (let index = 0; index < 3; index += 1) {
        const r = clamp(p * 1.2 - index * .1);
        s.arc(s.W * .6, y, 8 + r * s.W * .6, 4 + r * s.H * .8, 0, TAU, c, fade * (1 - r), 1.4);
      }
    } else if (group === 'wake') {
      const x = at(p);
      s.line(x, 1, x, s.H - 1, c, fade, 1.4);
      s.line(left, y, x, y, c, fade * .4, 1);
    } else {
      const head = at(p);
      s.line(Math.max(left, head - s.W * .2), y, head, y, c, fade, 2);
    }
  }

  // Landing gear deploys or retracts as a short strut pulse under the ship.
  function drawGear(b, gear, elapsed, pal) {
    const travel = smooth(clamp(elapsed / .58));
    const deployment = gear.down ? travel : 1 - travel;
    const alpha = smooth(clamp(elapsed / .14)) * (1 - smooth(clamp((elapsed - .64) / .44)));
    const c = gear.down ? pal.green : pal.accent;
    const cx = b.W / 2, y = b.H * .7;
    const spread = 5 + deployment * b.W * .16, footY = y - 1 + deployment * 8;
    for (const side of [-1, 1]) {
      const footX = cx + side * spread;
      b.line(cx + side * 4, y - 5, footX, footY, c, alpha * .9, 1.5);
      b.line(footX - side * 3.5, footY, footX + side * 2, footY, c, alpha * (.42 + deployment * .48), 1.35);
      b.dot(footX, footY, 1, c, alpha * .82);
    }
    const pulse = clamp(elapsed / .78);
    b.ring(cx, y, 6 + pulse * b.W * .3, 2.5 + pulse * 7, 6, c, alpha * (1 - pulse) * .72, 1.2, Math.PI / 6);
  }

  function seam(s, st, pal, strength) {
    if (strength <= .01) return;
    s.alpha = 1;
    s.halo = 1;
    s.line(0, s.H / 2, s.W, s.H / 2, st.c, strength * .8, 1.2);
    s.line(s.W * .18, s.H / 2, s.W * .82, s.H / 2, pal.text, strength * .45, .8);
  }

  // ---------------------------------------------------------------------
  // Surfaces and the scene clock.
  // ---------------------------------------------------------------------

  class Surface {
    constructor(canvas, role) {
      this.canvas = canvas;
      this.role = role;
      this.ctx = canvas.getContext('2d');
      this.painter = new Painter(this.ctx);
      this.W = 0;
      this.H = 0;
      this.ratio = 1;
      this.resize();
    }

    resize() {
      const width = this.canvas.clientWidth;
      const height = this.canvas.clientHeight;
      // The overlay text size zooms the page; size the backing store for the
      // pixels actually shown so strokes stay crisp at any scale.
      const shown = this.canvas.getBoundingClientRect().width;
      const zoom = width > 0 && shown > 0 ? shown / width : 1;
      this.dpr = window.devicePixelRatio || 1;
      const ratio = clamp(this.dpr * zoom, 1, 4);
      const backingWidth = Math.max(1, Math.round(width * ratio));
      const backingHeight = Math.max(1, Math.round(height * ratio));
      if (this.canvas.width !== backingWidth || this.canvas.height !== backingHeight) {
        this.canvas.width = backingWidth;
        this.canvas.height = backingHeight;
      }
      this.W = width;
      this.H = height;
      this.ratio = ratio;
    }

    begin() {
      const ctx = this.ctx;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = 1;
      ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      if (this.W < 2 || this.H < 2) return false;
      ctx.setTransform(this.ratio, 0, 0, this.ratio, 0, 0);
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.globalCompositeOperation = 'lighter';
      const painter = this.painter;
      painter.W = this.W;
      painter.H = this.H;
      painter.alpha = 1;
      painter.halo = 1;
      return true;
    }
  }

  class NavigationScene {
    constructor({deck = null, bay = null} = {}) {
      this.surfaces = [];
      if (deck?.getContext) this.surfaces.push(new Surface(deck, 'deck'));
      if (bay?.getContext) this.surfaces.push(new Surface(bay, 'bay'));
      this.state = null;
      this.previous = null;
      this.transition = null;
      this.palette = cssPalette();
      this.energy = 1;
      this.reduced = false;
      this.visible = true;
      this.textScale = 0;
      this.clock = performance.now();
      this.lastFrame = 0;
      this.event = null;
      this.eventSequence = null;
      this.gear = null;
      this.frameId = 0;
      this.frames = 0;
      this.frameCallback = (now) => this.frame(now);
      this.handleVisibility = () => {
        this.clock = performance.now();
        this.schedule();
      };
      document.addEventListener('visibilitychange', this.handleVisibility);
      if (typeof ResizeObserver === 'function') {
        // Resizing clears a canvas. Observers run before the browser paints,
        // so repainting here means a resize (a ship name appearing under the
        // portrait, say) never flashes an empty frame.
        this.observer = new ResizeObserver(() => {
          this.surfaces.forEach((surface) => surface.resize());
          this.repaint(true);
        });
        this.surfaces.forEach((surface) => this.observer.observe(surface.canvas));
      }
    }

    get key() {
      return this.state?.key || '';
    }

    get running() {
      return Boolean(this.frameId);
    }

    update(input = {}) {
      const now = performance.now();
      this.advance(now);
      this.palette = {...cssPalette(), ...(input.palette || {})};
      this.energy = clamp(Number(input.energy) || 1, .55, 1.6);
      this.reduced = Boolean(input.reduced);
      this.visible = input.visible !== false;
      // The text size zooms the page without resizing the canvases' CSS
      // boxes, so ResizeObserver never hears of it; re-measure on change.
      const textScale = Number(input.textScale) || 1;
      const rescaled = textScale !== this.textScale;
      if (rescaled) {
        this.textScale = textScale;
        this.surfaces.forEach((surface) => surface.resize());
      }
      const next = this.makeState(input);
      const current = this.state;
      if (current && next.d.inMainShip && current.d.inMainShip
          && next.d.landingGear !== current.d.landingGear && !this.reduced) {
        this.gear = {down: next.d.landingGear, start: now};
      }
      if (!current) this.state = next;
      else if (next.identity !== current.identity) this.changeTo(next, now);
      else this.refresh(next);
      if (input.eventSequence != null && input.eventSequence !== this.eventSequence) {
        this.eventSequence = input.eventSequence;
        if (input.eventKind && !this.reduced) {
          this.event = {kind: String(input.eventKind), tone: String(input.eventTone || ''), start: now};
        }
      }
      if (this.reduced) {
        this.previous = null;
        this.transition = null;
        this.event = null;
        this.gear = null;
      }
      this.schedule();
      this.repaint(rescaled);
    }

    makeState(input) {
      const label = String(input.label || 'FLIGHT').toUpperCase();
      const vehicleKey = String(input.vehicleKey || '').toLowerCase();
      const key = sceneKey(input.motion, label, vehicleKey);
      const d = dynamicsOf(input.dynamics);
      const palette = {...this.palette, ...(input.palette || {})};
      return {
        key,
        label,
        vehicleKey,
        aura: auraOf(key),
        identity: `${key}|${label}|${vehicleKey}|${boostTier(d)}`,
        c: palette.state || palette.hud,
        d,
        target: {altitude: d.altitude, vertical: d.vertical, gravity: d.gravity},
        starTone: String(input.starTone || ''),
        // Silent running seals the ship's emissions; its hologram dims too.
        halo: d.silentRunning ? .35 : 1,
        level: input.quiet ? .8 : 1,
        p: 0,
        terrain: 0,
        age: 0,
      };
    }

    changeTo(next, now) {
      const current = this.state;
      next.p = current.p;
      next.terrain = current.terrain;
      // Planetary phases share one physical frame, so altitude and descent
      // keep easing from where they were rather than jumping.
      if (PLANETARY.has(next.key) && PLANETARY.has(current.key)) {
        for (const field of ['altitude', 'vertical', 'gravity']) next.d[field] = current.d[field];
      }
      if (this.reduced || !this.visible) {
        this.state = next;
        this.previous = null;
        this.transition = null;
        return;
      }
      // An interrupted change continues from exactly what is on screen.
      let from = current, fromScale = 1;
      if (this.transition && this.previous) {
        const k = this.progress(now);
        if (this.transition.crossfade) {
          from = k < .5 ? this.previous : current;
        } else if (k < .5) {
          from = this.previous;
          fromScale = this.foldScale(k);
        } else {
          fromScale = this.openScale(k);
        }
      }
      const crossfade = from.aura === next.aura;
      this.previous = from;
      this.state = next;
      this.transition = {start: now, duration: crossfade ? CROSSFADE_MS : REPROJECT_MS, crossfade, fromScale};
    }

    refresh(next) {
      const state = this.state;
      state.c = next.c;
      state.starTone = next.starTone;
      state.halo = next.halo;
      state.level = next.level;
      for (const [field, value] of Object.entries(next.d)) {
        if (field in state.target) state.target[field] = value;
        else state.d[field] = value;
      }
      if (this.reduced) Object.assign(state.d, state.target);
    }

    progress(now) {
      return this.transition ? clamp((now - this.transition.start) / this.transition.duration) : 1;
    }

    foldScale(k) {
      return lerp(this.transition.fromScale, FOLD, smooth(k * 2));
    }

    openScale(k) {
      return lerp(FOLD, 1, smooth((k - .5) * 2));
    }

    advance(now) {
      const dt = clamp((now - this.clock) / 1000, 0, .1);
      this.clock = now;
      if (!dt || this.reduced || !this.visible || document.hidden) return;
      const blend = 1 - Math.exp(-dt / .3);
      for (const state of [this.state, this.previous]) {
        if (!state) continue;
        state.age += dt;
        for (const field of ['altitude', 'vertical', 'gravity']) {
          const target = state.target[field], old = state.d[field];
          state.d[field] = field === 'altitude' && (old < 0 || target < 0) ? target : old + (target - old) * blend;
        }
        const rate = this.energy / periodOf(state.key);
        state.p += dt * rate;
        state.terrain += dt * rate * (.65 + clamp(Math.abs(state.d.vertical) / 160));
      }
    }

    active() {
      return Boolean(this.state) && this.surfaces.length > 0 && this.visible && !this.reduced && !document.hidden;
    }

    schedule() {
      if (this.active()) {
        if (!this.frameId) this.frameId = requestAnimationFrame(this.frameCallback);
      } else if (this.frameId) {
        cancelAnimationFrame(this.frameId);
        this.frameId = 0;
      }
    }

    frame(now) {
      this.frameId = 0;
      if (!this.active()) return;
      // Moving to a monitor with another scale factor changes no CSS size.
      const rescaled = this.surfaces.some((surface) => surface.dpr !== (window.devicePixelRatio || 1));
      if (rescaled) this.surfaces.forEach((surface) => surface.resize());
      this.advance(now);
      const elapsed = now - this.lastFrame;
      if (elapsed >= FRAME_MS - .1 || rescaled) {
        // Keep the remainder so 60 Hz displays get an even 30 fps.
        this.lastFrame += Math.floor((elapsed + .1) / FRAME_MS) * FRAME_MS;
        this.draw(now);
      }
      this.frameId = requestAnimationFrame(this.frameCallback);
    }

    // Keep the canvases truthful whenever the loop will not: reduced motion
    // gets a settled still, a hidden overlay is current the moment it shows,
    // and `force` covers a canvas the browser has just cleared.
    repaint(force = false) {
      if (!this.state || (this.running && !force)) return;
      if (!this.reduced) {
        this.draw(performance.now());
        return;
      }
      const state = this.state;
      const saved = {p: state.p, terrain: state.terrain, age: state.age};
      Object.assign(state, {p: STILL_PHASE, terrain: STILL_PHASE, age: 30});
      Object.assign(state.d, state.target);
      this.draw(performance.now());
      Object.assign(state, saved);
    }

    draw(now) {
      const state = this.state;
      if (!state) return;
      const k = this.progress(now);
      if (this.transition && k >= 1) {
        this.transition = null;
        this.previous = null;
      }
      const clockSeconds = now / 1000;
      for (const surface of this.surfaces) {
        if (!surface.begin()) continue;
        const painter = surface.painter;
        const paint = surface.role === 'deck' ? paintDeck : paintBay;
        const transition = this.transition;
        if (transition && this.previous) {
          if (transition.crossfade) {
            const mix = smooth(k);
            this.layer(surface, paint, this.previous, 1, 1 - mix);
            this.layer(surface, paint, state, 1, mix);
          } else if (k < .5) {
            this.layer(surface, paint, this.previous, this.foldScale(k), 1 - smooth(k * 2) * .35);
          } else {
            this.layer(surface, paint, state, this.openScale(k), .65 + .35 * smooth((k - .5) * 2));
          }
          if (!transition.crossfade) seam(painter, state, this.palette, 1 - Math.abs(k - .5) * 2);
        } else {
          this.layer(surface, paint, state, 1, 1);
        }
        painter.alpha = 1;
        painter.halo = state.halo;
        if (surface.role === 'deck') {
          deckOverlays(painter, state, this.palette);
          if (this.event) {
            const group = EVENT_GROUP.get(this.event.kind) || 'other';
            const seconds = EVENT_SECONDS[group] || 1.2;
            const t = (now - this.event.start) / 1000 / seconds;
            if (t >= 0 && t <= 1) drawEvent(painter, this.event, t, eventColour(this.event, this.palette, state.c), this.palette);
            else if (t > 1) this.event = null;
          }
        } else {
          bayOverlays(painter, state, this.palette, clockSeconds);
          if (this.gear) {
            const elapsed = (now - this.gear.start) / 1000;
            if (elapsed >= 0 && elapsed <= 1.08) drawGear(painter, this.gear, elapsed, this.palette);
            else if (elapsed > 1.08) this.gear = null;
          }
        }
      }
      this.frames += 1;
    }

    layer(surface, paint, state, scale, alpha) {
      const painter = surface.painter, ctx = painter.ctx;
      ctx.save();
      if (scale < .999) {
        ctx.translate(0, painter.H / 2);
        ctx.scale(1, Math.max(.001, scale));
        ctx.translate(0, -painter.H / 2);
      }
      painter.alpha = alpha * state.level;
      painter.halo = state.halo;
      paint(painter, state, this.palette);
      ctx.restore();
    }

    dispose() {
      if (this.frameId) cancelAnimationFrame(this.frameId);
      this.frameId = 0;
      this.observer?.disconnect();
      document.removeEventListener('visibilitychange', this.handleVisibility);
    }
  }

  NavigationScene.sceneKey = sceneKey;
  NavigationScene.auraOf = auraOf;
  NavigationScene.hasScene = (key) => Boolean(DECK[key]) || key.startsWith('vehicle_');
  window.NavigationScene = NavigationScene;
})();
