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
  // Hologram modes (Overlay Studio, 5.5.3). Full animates every frame.
  // Still, for low-end PCs, animates only while a state change re-projects
  // the hologram, then holds that state's settled still and draws nothing
  // until the next change. Off draws no hologram at all.
  const SCENE_MODES = new Set(['full', 'still', 'off']);
  // A still canvas has no next frame to restore it if WebView2 wipes it
  // (a graphics reset, memory reclaimed while hidden), so Still and reduced
  // motion repaint their one frame this often as a backstop.
  const STILL_REFRESH_MS = 5000;
  const REPROJECT_MS = 540;
  const CROSSFADE_MS = 380;
  const FOLD = .035;
  // Reduced motion paints one pose per state; this phase shows every scene
  // with its moving parts spread out rather than bunched at the origin.
  const STILL_PHASE = 1.37;
  // Deck scenes are composed for a deck this tall and scaled up uniformly
  // to the real one, so a taller deck enlarges a scene instead of
  // stretching it.
  const DECK_DESIGN_HEIGHT = 38;
  // A disc seen at the cockpit's viewing angle. Rings, dishes, orbits and
  // ripples keep this tilt at any deck width; stretching them to fill a
  // wide strip is what made scenes look squashed.
  const TILT = .3;

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

  // The models (station, carrier, ships, vehicles...) from models.js.
  const MODELS = window.NavigationModels;

  // Roll about z, then yaw about y, then pitch about x: a model is turned
  // on its own axes before the camera looks at it the same way.
  function rotor(yaw = 0, pitch = 0, roll = 0) {
    const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const cr = Math.cos(roll), sr = Math.sin(roll);
    return ([x, y, z]) => {
      const x1 = x * cr - y * sr, y1 = x * sr + y * cr;
      const x2 = x1 * cy + z * sy, z2 = z * cy - x1 * sy;
      return [x2, y1 * cp - z2 * sp, y1 * sp + z2 * cp];
    };
  }

  // A scene's camera: the deck point its origin lands on, pixels per unit,
  // the angle it looks from and, when `persp` is set, the distance whose
  // perspective it draws with (nearer things larger).
  function camera(x, y, unit, {yaw = 0, pitch = 0, persp = 0} = {}) {
    const look = rotor(yaw, pitch, 0);
    const scaleAt = (depth) => (persp ? persp / Math.max(persp * .12, persp - depth) : 1);
    return {
      x, y, unit, look, scaleAt,
      project(point) {
        const [vx, vy, vz] = look(point);
        const k = scaleAt(vz);
        return [x + vx * k * unit, y + vy * k * unit, vz, k];
      },
    };
  }

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
      // Scaled scenes thicken their lines by the square root of the scale
      // only, so a larger deck reads bolder without turning heavy.
      this.stroke = 1;
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
        ctx.lineWidth = (width * 3 + 1.2) * this.stroke;
        ctx.stroke();
      }
      ctx.globalAlpha = a;
      ctx.lineWidth = width * this.stroke;
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

    // Energise a fixed housing without moving it. Overlapping edge fades keep
    // the contour's seam smooth as the light runs round.
    traceEdges(points, cycle, color, alpha = .8) {
      for (let index = 0; index < points.length; index += 1) {
        const next = points[(index + 1) % points.length];
        const light = Math.pow(wave(cycle - index / points.length), 4);
        this.line(points[index][0], points[index][1], next[0], next[1], color, light * alpha, 1.6);
      }
    }

    // Blot out a disc: additive light can brighten but never darken, so a
    // black hole's hole is painted over what is behind it.
    occlude(x, y, r, color) {
      const ctx = this.ctx;
      ctx.save();
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = this.alpha;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x, y, Math.max(.2, r), 0, TAU);
      ctx.fill();
      ctx.restore();
    }

    // Pose and draw a model from models.js (a rock, the station, a ship):
    // solid facets, lit from the upper left, hiding whatever is behind them.
    // Solids paint normally rather than additively, so they occlude. `cam` is the scene's camera, `place` sets the model in it
    // ({x, y, z, yaw, pitch, roll, scale}). `lamps` colours the model's
    // named lamp faces and lights: {slot: colour} or {slot: [colour, level]};
    // false puts a lamp out. Returns a projector for points on the model,
    // so a scene can fly traffic into a slot or hang a beacon on a mast.
    solid(model, cam, place, color, alpha = 1, shadow = '#000', lamps = {}) {
      const a = clamp(alpha) * this.alpha;
      const spin = rotor(place.yaw, place.pitch, place.roll);
      const size = place.scale ?? 1, px = place.x || 0, py = place.y || 0, pz = place.z || 0;
      const toWorld = (point) => {
        const r = spin(point);
        return [r[0] * size + px, r[1] * size + py, r[2] * size + pz];
      };
      const at = (point) => cam.project(toWorld(point));
      if (a <= .004) return at;
      const view = model.v.map((vertex) => cam.look(toWorld(vertex)));
      const screen = view.map(([vx, vy, vz]) => {
        const k = cam.scaleAt(vz);
        return [cam.x + vx * k * cam.unit, cam.y + vy * k * cam.unit];
      });
      const lamp = (kind) => {
        const value = lamps[kind];
        if (value === false) return null;
        if (Array.isArray(value)) return value;
        return [value || color, .85];
      };
      const shown = [];
      for (const face of model.f) {
        const ids = face.i;
        let area = 0, depth = 0, nx = 0, ny = 0, nz = 0;
        for (let index = 0; index < ids.length; index += 1) {
          const p = screen[ids[index]], q = screen[ids[(index + 1) % ids.length]];
          area += p[0] * q[1] - q[0] * p[1];
          const u = view[ids[index]], w = view[ids[(index + 1) % ids.length]];
          nx += (u[1] - w[1]) * (u[2] + w[2]);
          ny += (u[2] - w[2]) * (u[0] + w[0]);
          nz += (u[0] - w[0]) * (u[1] + w[1]);
          depth += u[2];
        }
        // Screen winding says which way a face turns once perspective has
        // had its say; the view-space normal says how the light falls.
        if (area <= 0) continue;
        const light = clamp((-nx * .45 - ny * .65 + nz * .6) / (Math.hypot(nx, ny, nz) || 1));
        shown.push({face, depth: depth / ids.length, light});
      }
      shown.sort((left, right) => left.depth - right.depth);
      const ctx = this.ctx;
      ctx.save();
      ctx.globalCompositeOperation = 'source-over';
      ctx.lineWidth = .5 * this.stroke;
      ctx.lineJoin = 'round';
      for (const {face, light} of shown) {
        const ids = face.i;
        ctx.beginPath();
        ctx.moveTo(screen[ids[0]][0], screen[ids[0]][1]);
        for (let index = 1; index < ids.length; index += 1) ctx.lineTo(screen[ids[index]][0], screen[ids[index]][1]);
        ctx.closePath();
        ctx.globalAlpha = a;
        ctx.fillStyle = shadow;
        ctx.fill();
        let kind = face.k;
        let tone = null;
        if (kind !== 'hull' && kind !== 'trim' && kind !== 'dark') {
          tone = lamp(kind);
          if (!tone) kind = 'trim';
        }
        if (tone) {
          ctx.globalAlpha = a * clamp(tone[1]);
          ctx.fillStyle = tone[0];
          ctx.fill();
          ctx.globalAlpha = a * clamp(tone[1] + .1);
          ctx.strokeStyle = tone[0];
        } else if (kind === 'dark') {
          ctx.globalAlpha = a * .3;
          ctx.strokeStyle = color;
        } else {
          const trim = kind === 'trim';
          ctx.globalAlpha = a * ((trim ? .17 : .1) + light * (trim ? .52 : .47));
          ctx.fillStyle = color;
          ctx.fill();
          ctx.globalAlpha = a * ((trim ? .24 : .14) + light * .35);
          ctx.strokeStyle = color;
        }
        ctx.stroke();
      }
      ctx.restore();
      // Lights shine only from the side of the model facing the viewer.
      for (const point of model.lights || []) {
        const tone = lamp(point.k);
        if (!tone || tone[1] <= .01) continue;
        const facing = cam.look(spin(point.n))[2];
        if (facing <= 0) continue;
        const [sx, sy] = at(point.at);
        this.spark(sx, sy, .55, tone[0], null, a * tone[1] / this.alpha * clamp(facing * 2));
      }
      return at;
    }

    // A shaded world: lit from the key light's side with a night side
    // beyond the terminator, surface detail that turns with it, an
    // atmosphere rim and, if asked, rings. Decorative: no real body's
    // appearance is claimed.
    sphere(x, y, r, color, shadow, {spin = 0, tilt = .35, kind = 'rock', seed = 1, atmosphere = null,
      rings = null, grid = false, detail = 1, sheen = [-.45, -.5]} = {}) {
      const a = this.alpha;
      if (a <= .004 || r < .4) return;
      const ctx = this.ctx;
      const ct = Math.cos(tilt), stl = Math.sin(tilt);
      // A point on the unit sphere at (lat, lon), turned and tilted.
      const surface = (lat, lon) => {
        const cx = Math.cos(lat) * Math.sin(lon + spin), cy = -Math.sin(lat), cz = Math.cos(lat) * Math.cos(lon + spin);
        return [cx, cy * ct - cz * stl, cy * stl + cz * ct];
      };
      const litBy = ([px, py, pz]) => clamp(-px * .45 - py * .65 + pz * .6);
      const ringArc = (from, to) => {
        if (!rings) return;
        for (let band = 0; band < 3; band += 1) {
          const rx = r * lerp(rings.inner || 1.45, rings.outer || 2.2, band / 2), ry = rx * (rings.tilt || .22);
          this.arc(x, y, rx, ry, from, to, color, (rings.alpha || .5) * (1 - band * .22), 1.4 - band * .3);
        }
      };
      ringArc(Math.PI, TAU);
      ctx.save();
      ctx.globalCompositeOperation = 'source-over';
      ctx.beginPath();
      ctx.arc(x, y, r, 0, TAU);
      ctx.globalAlpha = a;
      ctx.fillStyle = shadow;
      ctx.fill();
      ctx.clip();
      // Where the light strikes, as a fraction of the radius from centre: a
      // world far bigger than the deck is lit on the cap that shows.
      const lx = x + r * sheen[0], ly = y + r * sheen[1];
      const body = ctx.createRadialGradient(lx, ly, r * .05, lx, ly, r * 1.55);
      body.addColorStop(0, color);
      body.addColorStop(1, 'transparent');
      ctx.globalAlpha = a * (kind === 'ice' ? .72 : .6);
      ctx.fillStyle = body;
      ctx.fillRect(x - r, y - r, r * 2, r * 2);
      ctx.lineWidth = Math.max(.5, r * .045) * this.stroke;
      ctx.strokeStyle = color;
      if (kind === 'gas') {
        // Cloud bands along the latitudes, and a storm that turns with them.
        for (let band = 0; band < 7; band += 1) {
          const lat = -1.1 + band * .37 + hash(seed + band) * .12;
          ctx.beginPath();
          let drawing = false;
          for (let step = 0; step <= 24; step += 1) {
            const [px, py, pz] = surface(lat, step * TAU / 24);
            if (pz < 0) {
              drawing = false;
              continue;
            }
            if (drawing) ctx.lineTo(x + px * r, y + py * r);
            else ctx.moveTo(x + px * r, y + py * r);
            drawing = true;
          }
          ctx.globalAlpha = a * (.16 + hash(seed + band * 3) * .22);
          ctx.lineWidth = r * (.06 + hash(seed + band * 5) * .1) * this.stroke;
          ctx.stroke();
        }
        ctx.lineWidth = Math.max(.5, r * .045) * this.stroke;
      }
      // Craters, storms or ice fields: surface marks that turn with it.
      const marks = kind === 'gas' ? 2 : Math.round((kind === 'ice' ? 9 : 16) * detail);
      for (let index = 0; index < marks; index += 1) {
        const lat = (hash(seed * 7 + index) - .5) * 2.6, lon = hash(seed * 13 + index) * TAU;
        const [px, py, pz] = surface(lat, lon);
        if (pz <= .08) continue;
        const size = (kind === 'gas' ? .16 : .05 + hash(seed * 3 + index) * .12) * r;
        ctx.beginPath();
        ctx.ellipse(x + px * r, y + py * r, Math.max(.3, size * pz), size, Math.atan2(py, px), 0, TAU);
        ctx.globalAlpha = a * (.18 + litBy([px, py, pz]) * .45) * pz;
        ctx.stroke();
      }
      if (grid) {
        // The hologram's lattice across the near hemisphere.
        ctx.lineWidth = .5 * this.stroke;
        for (let meridian = 0; meridian < 6; meridian += 1) {
          ctx.beginPath();
          let drawing = false;
          for (let step = 0; step <= 16; step += 1) {
            const [px, py, pz] = surface(-Math.PI / 2 + step * Math.PI / 16, meridian * TAU / 6);
            if (pz < 0) {
              drawing = false;
              continue;
            }
            if (drawing) ctx.lineTo(x + px * r, y + py * r);
            else ctx.moveTo(x + px * r, y + py * r);
            drawing = true;
          }
          ctx.globalAlpha = a * .16;
          ctx.stroke();
        }
      }
      // Night side: the terminator falls away from the light.
      const night = ctx.createRadialGradient(lx, ly, r * .75, lx, ly, r * 2.1);
      night.addColorStop(0, 'rgba(0, 0, 0, 0)');
      night.addColorStop(1, shadow);
      ctx.globalAlpha = a * .92;
      ctx.fillStyle = night;
      ctx.fillRect(x - r, y - r, r * 2, r * 2);
      ctx.restore();
      // The lit limb, and an atmosphere's glow beyond it.
      this.arc(x, y, r, r, Math.PI * .92, Math.PI * 1.62, color, .55, 1);
      if (atmosphere) {
        this.arc(x, y, r + 1.2, r + 1.2, Math.PI * .75, Math.PI * 1.85, atmosphere, .5, 1.6);
        this.arc(x, y, r + 2.6, r + 2.6, Math.PI * .9, Math.PI * 1.7, atmosphere, .18, 2);
      }
      ringArc(0, Math.PI);
    }

    // A star: a hot disc in its class colour with a white core, a surface
    // that boils, a corona that breathes and loops of plasma at the limb.
    sun(x, y, r, color, core, phase, {flares = true} = {}) {
      this.bloom(x, y, r * 3.2, color, .42);
      this.bloom(x, y, r * 1.7, color, .5);
      const ctx = this.ctx;
      ctx.save();
      ctx.globalCompositeOperation = 'source-over';
      const body = ctx.createRadialGradient(x - r * .2, y - r * .2, r * .1, x, y, r);
      body.addColorStop(0, core);
      body.addColorStop(.45, color);
      body.addColorStop(1, color);
      ctx.beginPath();
      ctx.arc(x, y, r, 0, TAU);
      ctx.globalAlpha = this.alpha * .95;
      ctx.fillStyle = body;
      ctx.fill();
      ctx.restore();
      for (let index = 0; index < 9; index += 1) {
        const angle = hash(index + 3) * TAU + phase * (.05 + hash(index) * .08);
        const reach = r * (.2 + hash(index + 9) * .6);
        this.bloom(x + Math.cos(angle) * reach, y + Math.sin(angle) * reach * .9, r * .28,
          core, .18 + .18 * wave(phase * .3 + index * .2));
      }
      for (let index = 0; index < 18; index += 1) {
        const angle = index * TAU / 18 + hash(index + 40) * .2;
        const length = r * (.25 + .45 * wave(phase * .22 + hash(index + 41)));
        this.line(x + Math.cos(angle) * r * 1.02, y + Math.sin(angle) * r * 1.02,
          x + Math.cos(angle) * (r + length), y + Math.sin(angle) * (r + length), color, .3, .9);
      }
      if (flares) {
        for (let index = 0; index < 2; index += 1) {
          const base = -1.9 + index * 1.3 + Math.sin(phase * .1 + index) * .15;
          const rise = r * (.35 + .25 * wave(phase * .18 + index * .5));
          const points = [];
          for (let step = 0; step <= 10; step += 1) {
            const u = step / 10, angle = base + (u - .5) * .5;
            const lift = Math.sin(u * Math.PI) * rise;
            points.push([x + Math.cos(angle) * (r + lift), y + Math.sin(angle) * (r + lift)]);
          }
          this.poly(points, color, .55, 1.2);
        }
      }
    }
  }

  // ---------------------------------------------------------------------
  // Shared fields: the wide backdrops that fill the deck around each
  // state's subject.
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

  // A confirmed neutron or white-dwarf supercharge charges the corridor
  // itself: a blue sheath inside its rails, blue-white streaks, and charge
  // rings rolling back from the heading round the corridor. The tier (from
  // the journal's boost value) shows as chevrons ahead of the marker; the
  // scene never invents a speed.
  function boostCharge(s, st, pal, vx) {
    const tier = boostTier(st.d);
    if (!tier) return;
    const cy = s.H / 2, blue = pal.accent;
    streaks(s, st, {x: vx, count: 4 + tier * 3, speed: .46, strength: .5, width: 1.1, color: blue});
    for (const side of [-1, 1]) {
      s.poly([[-4, cy + side * s.H * .42], [vx * .42, cy + side * s.H * .25],
        [vx * .78, cy + side * s.H * .09], [vx - 8, cy + side * 1.4]], blue, .55, 1.2);
    }
    const rings = 2 + tier;
    for (let index = 0; index < rings; index += 1) {
      const t = fract(st.p * .32 + index / rings), k = t * t;
      const r = lerp(2.5, s.H * .52, k);
      s.arc(lerp(vx - 6, -8, k), cy, r * .32, r, 0, TAU, blue, Math.sin(t * Math.PI) * .5, .8 + k * .8);
    }
    s.bloom(vx, cy, 12 + tier * 3, blue, .4 + .15 * wave(st.p * .6));
    for (let index = 0; index < tier; index += 1) {
      s.chevron(vx + 13 + index * 6, cy, 1, blue, .9 - index * .12, 3.2, 1.4);
    }
  }

  // ---------------------------------------------------------------------
  // Solid scenes. Each state stages its own subject (the station, the
  // carrier, a world, a star, a vehicle, the commander) as lit, occluding
  // solids like the asteroid field's rocks, with light and motion round
  // it. `s` is the painter, `st` the state (colour, dynamics, phase) and
  // `pal` the theme palette. Anything that reads as a quantity comes from
  // the journal or Status.json; the rest is decorative.
  // ---------------------------------------------------------------------

  // Low-poly ground seen through `cam`: a height field of lit facets drawn
  // far to near so ridges hide what lies behind them. `travel` slides the
  // ground under the viewer ([along x, along z], in ground units) on a
  // fixed lattice, so hills keep their shape as they pass. `flat` levels a
  // round clearing ({x, z, radius}) for a pad or a landing; `road` levels a
  // band across the view ({z, width}) for a vehicle driving along it. The
  // far rows rise into hills and fade in, so nothing pops over the horizon.
  function landscape(s, cam, st, pal, {x0 = -36, x1 = 36, z0 = -18, z1 = 3, cols = 18, rows = 8,
    travel = [0, 0], lift = 1, seed = 1, flat = null, road = null, alpha = 1, color = st.c, floor = 0} = {}) {
    const dx = (x1 - x0) / cols, dz = (z1 - z0) / rows;
    const baseX = Math.floor(travel[0] / dx), baseZ = Math.floor(travel[1] / dz);
    const sx = (travel[0] / dx - baseX) * dx, sz = (travel[1] / dz - baseZ) * dz;
    const grid = [];
    for (let j = 0; j <= rows; j += 1) {
      const row = [];
      const z = z0 + j * dz + sz, wz = z0 + (j - baseZ) * dz;
      for (let i = 0; i <= cols; i += 1) {
        const x = x0 + i * dx - sx, wx = x0 + (i + baseX) * dx;
        let h = .55 * Math.sin(wx * .55 + seed) + .7 * Math.sin(wz * .42 + wx * .18 + seed * 3)
          + .45 * Math.sin((wx - wz) * .31 + seed * 5) + .35 * hash(i + baseX * 7 + (j - baseZ) * 13) + .8;
        h = Math.max(0, h) * lift * (.5 + Math.pow(clamp(-z / Math.abs(z0)), 1.5) * 2.4);
        if (flat) h *= smooth((Math.hypot(x - flat.x, z - (flat.z || 0)) - flat.radius) / 3);
        if (road) h *= smooth((Math.abs(z - road.z) - road.width) / 3);
        const [vx, vy, vz] = cam.look([x, floor - h, z]), k = cam.scaleAt(vz);
        row.push([cam.x + vx * k * cam.unit, cam.y + vy * k * cam.unit, vx, vy, vz]);
      }
      grid.push(row);
    }
    const ctx = s.ctx, a = s.alpha * alpha;
    ctx.save();
    ctx.globalCompositeOperation = 'source-over';
    ctx.lineWidth = .45 * s.stroke;
    for (let j = 0; j < rows; j += 1) {
      // Fade the far rows in as they arrive over the horizon.
      const fog = smooth((j + 1 - sz / dz) / 2.2);
      if (fog <= .01) continue;
      for (let i = 0; i < cols; i += 1) {
        const p = grid[j][i], q = grid[j][i + 1], r = grid[j + 1][i + 1], u = grid[j + 1][i];
        // The slope of the facet, from its diagonals in view space, sets
        // its light the way a model's faces are lit.
        const ax = r[2] - p[2], ay = r[3] - p[3], az = r[4] - p[4];
        const bx = u[2] - q[2], by = u[3] - q[3], bz = u[4] - q[4];
        const nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx;
        const light = clamp((-nx * .45 - ny * .65 + nz * .6) / (Math.hypot(nx, ny, nz) || 1));
        ctx.beginPath();
        ctx.moveTo(p[0], p[1]);
        ctx.lineTo(q[0], q[1]);
        ctx.lineTo(r[0], r[1]);
        ctx.lineTo(u[0], u[1]);
        ctx.closePath();
        ctx.globalAlpha = a * fog;
        ctx.fillStyle = pal.bg;
        ctx.fill();
        ctx.globalAlpha = a * fog * (.03 + light * .2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.globalAlpha = a * fog * (.06 + light * .22);
        ctx.strokeStyle = color;
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  // Stars drifting deep in the background: three depths, the nearest fastest.
  function sky(s, st, alpha = 1, speed = 1) {
    dust(s, st, {count: 30, speed: .006 * speed, alpha: .45 * alpha});
    dust(s, st, {count: 12, speed: .016 * speed, alpha: .6 * alpha});
  }

  // A small craft's engine trail: fading dots behind it.
  function trail(s, from, to, color, alpha = .6, count = 7) {
    for (let index = 1; index <= count; index += 1) {
      const u = index / count;
      s.dot(lerp(from[0], to[0], u), lerp(from[1], to[1], u), .9 - u * .5, color, alpha * (1 - u));
    }
  }

  // ---------------------------------------------------------------------
  // Stars by kind. A star's colour comes from its class (the HUD's star
  // badge uses the same); its form from what it is: a sun, a white dwarf's
  // hard point, a neutron star's sweeping jets, a black hole's disc, a
  // Wolf-Rayet shedding shells, a T Tauri in its dust, a brown dwarf's
  // banded glow. `family` is starFamily() from app.js.
  // ---------------------------------------------------------------------

  function stellarBody(s, st, pal, x, y, r, {family = st.starFamily, tone = st.starTone, flares = true} = {}) {
    const color = tone || st.c, phase = st.p;
    if (family === 'neutron') neutronStar(s, pal, x, y, r, color, phase);
    else if (family === 'dwarf') whiteDwarf(s, pal, x, y, r, color, phase);
    else if (family === 'blackhole') blackHole(s, pal, x, y, r, color, phase);
    else if (family === 'wolf') wolfRayet(s, pal, x, y, r, color, phase, flares);
    else if (family === 'tauri') tTauri(s, pal, x, y, r, color, phase, flares);
    else if (family === 'l' || family === 't' || family === 'y') brownDwarf(s, pal, x, y, r, color, phase);
    else s.sun(x, y, r * ({o: 1.12, b: 1.08, m: .86}[family] || 1), color, pal.text, phase, {flares});
  }

  // A tilted ellipse as points, for loops that need their own angle.
  function loop(x, y, a, b, angle, steps = 28) {
    const ca = Math.cos(angle), sa = Math.sin(angle), points = [];
    for (let step = 0; step <= steps; step += 1) {
      const t = step * TAU / steps, u = Math.cos(t) * a, v = Math.sin(t) * b;
      points.push([x + u * ca - v * sa, y + u * sa + v * ca]);
    }
    return points;
  }

  // A neutron star: a tiny, fierce core, twin jets along its magnetic axis
  // sweeping round as it spins, field loops either side and a pulse ring
  // on each turn.
  function neutronStar(s, pal, x, y, r, color, phase) {
    const core = Math.max(1.2, r * .32), reach = r * 3.4;
    const axis = -1.15 + Math.sin(phase * .6) * .35;
    for (const side of [-1, 1]) {
      const ux = Math.cos(axis) * side, uy = Math.sin(axis) * side, nx = -uy, ny = ux;
      // An open cone: a hot core beam between two fading edges, which
      // reads as a jet at any size (a closed shape turns into a bar).
      const tip = [x + ux * reach, y + uy * reach], spread = Math.max(1.2, core * 1.4);
      s.line(x, y, tip[0], tip[1], pal.text, .55, Math.max(.8, core * .2));
      s.line(x, y, tip[0], tip[1], color, .5, Math.max(1.2, core * .45));
      for (const edge of [-1, 1]) {
        s.line(x + nx * edge * core * .4, y + ny * edge * core * .4, tip[0] + nx * edge * spread,
          tip[1] + ny * edge * spread, color, .22, .8);
      }
      for (let index = 0; index < 4; index += 1) {
        const t = fract(phase * 1.4 + index / 4);
        s.spark(x + ux * reach * t, y + uy * reach * t, .6, color, pal.text, ends(t) * .8);
      }
      s.poly(loop(x + nx * core * 1.9, y + ny * core * 1.9, core * 1.9, core * .9, axis), color, .35, .8);
    }
    const beat = fract(phase * 1.1), ring = core + beat * r * 1.3;
    s.arc(x, y, ring, ring, 0, TAU, color, (1 - beat) * .45, 1);
    s.bloom(x, y, r * 1.6, color, .45);
    s.bloom(x, y, core * 3.2, pal.text, .65);
    s.dot(x, y, core, pal.text, 1);
  }

  // A white dwarf: a small, intensely white point with a tight, hard corona.
  function whiteDwarf(s, pal, x, y, r, color, phase) {
    const core = Math.max(1.2, r * .3);
    s.bloom(x, y, r * 2.2, color, .42);
    s.bloom(x, y, core * 3.4, pal.text, .7);
    for (let index = 0; index < 12; index += 1) {
      const angle = index * TAU / 12 + phase * .02, length = core * (1 + .9 * wave(phase * .3 + index * .37));
      s.line(x + Math.cos(angle) * core * 1.15, y + Math.sin(angle) * core * 1.15,
        x + Math.cos(angle) * (core * 1.15 + length), y + Math.sin(angle) * (core * 1.15 + length), color, .55, .8);
    }
    s.arc(x, y, core * 1.55, core * 1.55, 0, TAU, color, .55, .9);
    s.dot(x, y, core, pal.text, 1);
  }

  // A black hole: no light of its own. A hot accretion disc turns round
  // it, the far side of the disc bent up over the top and under the
  // bottom by the hole's gravity, and a thin photon ring at its edge.
  function blackHole(s, pal, x, y, r, color, phase) {
    const hole = r * .5, tilt = .24;
    const disc = (from, to) => {
      for (let band = 0; band < 5; band += 1) {
        const rr = hole * (1.4 + band * .4);
        s.arc(x, y, rr, rr * tilt, from, to, band < 2 ? pal.text : color, .72 - band * .12, 1.7 - band * .22);
      }
      for (let clump = 0; clump < 10; clump += 1) {
        const rr = hole * (1.5 + (clump % 4) * .4), angle = fract(phase * (.2 - (clump % 4) * .03) + clump / 10) * TAU;
        const behind = Math.sin(angle) < 0;
        if ((from === Math.PI) !== behind) continue;
        s.dot(x + Math.cos(angle) * rr, y + Math.sin(angle) * rr * tilt, .6, pal.text, .7);
      }
    };
    s.bloom(x, y, r * 2.2, color, .22);
    disc(Math.PI, TAU);
    s.arc(x, y, hole * 1.3, hole * 1.3, Math.PI * 1.04, Math.PI * 1.96, color, .65, 1.8);
    s.arc(x, y, hole * 1.2, hole * 1.2, Math.PI * .1, Math.PI * .9, color, .35, 1.2);
    s.occlude(x, y, hole, pal.bg);
    s.arc(x, y, hole * 1.04, hole * 1.04, 0, TAU, pal.text, .7, .8);
    disc(0, Math.PI);
  }

  // A Wolf-Rayet star: hot and violent, throwing off shells of its own
  // atmosphere that expand and thin as they go.
  function wolfRayet(s, pal, x, y, r, color, phase, flares) {
    for (let shell = 0; shell < 3; shell += 1) {
      const t = fract(phase * .18 + shell / 3), rr = r * (1 + t * 2.4);
      for (let arc = 0; arc < 6; arc += 1) {
        const start = arc * TAU / 6 + shell + hash(arc + shell * 7) * .4;
        s.arc(x, y, rr, rr * .92, start, start + .7, color, (1 - t) * .5, 1.3 - t * .6);
      }
    }
    s.sun(x, y, r * .82, color, pal.text, phase * 1.8, {flares});
  }

  // A T Tauri star: young, half-hidden in the disc of dust it formed from,
  // with faint jets out of its poles.
  function tTauri(s, pal, x, y, r, color, phase, flares) {
    const dust = (from, to) => {
      for (let band = 0; band < 4; band += 1) {
        const rr = r * (1.35 + band * .42);
        s.arc(x, y, rr, rr * .2, from, to, color, .34 - band * .06, 2.2 - band * .35);
      }
      for (let grain = 0; grain < 14; grain += 1) {
        const rr = r * (1.4 + hash(grain + 60) * 1.3), angle = fract(phase * .05 * (1.6 - rr / r * .3) + hash(grain + 61)) * TAU;
        if ((from === Math.PI) !== (Math.sin(angle) < 0)) continue;
        s.dot(x + Math.cos(angle) * rr, y + Math.sin(angle) * rr * .2, .5, color, .6);
      }
    };
    dust(Math.PI, TAU);
    for (const side of [-1, 1]) s.line(x, y + side * r * .7, x + side * r * .15, y + side * r * 2.2, color, .25, .9);
    s.sun(x, y, r * .72, color, pal.text, phase, {flares});
    dust(0, Math.PI);
  }

  // A brown dwarf (classes L, T and Y): too small to shine like a star,
  // a dim, banded world glowing faintly in its own heat.
  function brownDwarf(s, pal, x, y, r, color, phase) {
    s.bloom(x, y, r * 1.9, color, .28);
    s.sphere(x, y, r * .82, color, pal.bg, {kind: 'gas', spin: phase * .05, seed: 23, sheen: [-.15, -.2]});
    s.bloom(x, y, r * .95, color, .22);
  }

  // ---------------------------------------------------------------------
  // Normal space.
  // ---------------------------------------------------------------------

  // Normal space: a ringed world low on the right with its moon, a
  // distant Coriolis catching the light, stars drifting past.
  function vista(s, st, pal, {alpha = 1, station = true} = {}) {
    const saved = s.alpha;
    s.alpha *= alpha;
    sky(s, st);
    const px = s.W * .82, py = s.H * 1.08, r = s.H * .78;
    const orbit = st.p * .045 + 2.2;
    const mx = px + Math.cos(orbit) * r * 1.55, my = py - r * .78 + Math.sin(orbit) * r * .2;
    const moon = () => s.sphere(mx, my, s.H * .09, st.c, pal.bg, {spin: st.p * .08, seed: 7, kind: 'ice'});
    if (Math.sin(orbit) < 0) moon();
    s.sphere(px, py, r, st.c, pal.bg, {spin: st.p * .025, tilt: .28, seed: 3, atmosphere: pal.accent, detail: 1.5});
    if (Math.sin(orbit) >= 0) moon();
    if (station) {
      const cam = camera(s.W * .55, s.H * .34, 3.1, {yaw: -.5, pitch: -.3});
      s.solid(MODELS.coriolis(), cam, {roll: st.p * .2}, st.c, .9, pal.bg, {slot: [pal.green, .6], window: [st.c, .4]});
    }
    s.alpha = saved;
  }

  function flight(s, st, pal) {
    vista(s, st, pal);
  }

  // Flight assist off: the nose swings free of the ship's line of travel,
  // which carries on straight ahead as a steady line of motion.
  function assistOff(s, st, pal) {
    vista(s, st, pal, {alpha: .45, station: false});
    const x = s.W * .44, y = s.H * .5;
    const cam = camera(x, y, 6, {yaw: 0, pitch: -.3, persp: 14});
    for (let index = 0; index < 7; index += 1) {
      const t = fract(st.p * .35 + index / 7);
      s.dot(x + 16 + t * s.W * .36, y + 1 + t * 2, .8, pal.accent, (1 - t) * .7);
    }
    s.ring(x + s.W * .42, y + 4, 3.5, 3.5, 4, pal.accent, .75, 1.2, Math.PI / 4);
    const at = s.solid(MODELS.ship(), cam, {yaw: .35 + Math.sin(st.p * .35) * 1.15, roll: Math.sin(st.p * .5) * .35},
      st.c, 1, pal.bg, {engine: [st.c, .7]});
    const [nx, ny] = at([3, 0, 0]), [cx, cy] = at([1.9, 0, 0]);
    s.line(cx, cy, nx, ny, pal.text, .5, .8);
  }

  // Silent running: the ship dark and cold, its heat signature drawn in
  // and held; nothing radiates.
  function silent(s, st, pal) {
    sky(s, st, .45, .5);
    const x = s.W * .58, y = s.H * .52;
    for (let index = 0; index < 4; index += 1) {
      const t = fract(st.p * .16 + index / 4), r = lerp(s.W * .34, 10, smooth(t));
      s.arc(x, y + 2, r, r * .3, 0, TAU, pal.accent, Math.sin(t * Math.PI) * .32, .9);
    }
    const cam = camera(x, y, 6.5, {yaw: -.35, pitch: -.3, persp: 14});
    s.solid(MODELS.ship(), cam, {yaw: Math.sin(st.p * .1) * .1}, st.c, .55, pal.bg, {engine: false});
    const seal = .35 + .4 * wave(st.p * .3);
    for (const side of [-1, 1]) s.brackets(x, y, 26, 13, pal.accent, seal * .7, 5, 1.1 + side * 0);
  }

  // A fighter weaving ahead of its mothership.
  function fighter(s, st, pal) {
    sky(s, st, .8, 1.6);
    const mother = camera(s.W * .78, s.H * .45, 7, {yaw: -.45, pitch: -.3, persp: 14});
    s.solid(MODELS.ship(), mother, {}, st.c, .5, pal.bg, {engine: [st.c, .5]});
    const fx = s.W * .38 + Math.sin(st.p * .45) * s.W * .08, fy = s.H * .52 + Math.sin(st.p * .7) * 4;
    const bank = Math.cos(st.p * .45) * .6;
    const cam = camera(fx, fy, 7.5, {yaw: -.5, pitch: -.3, persp: 12});
    trail(s, [fx - 12, fy], [fx - 44, fy - Math.sin(st.p * .7 - .5) * 5], pal.accent, .7);
    s.solid(MODELS.ship('fighter'), cam, {roll: bank, yaw: Math.sin(st.p * .7) * .2}, st.c, 1, pal.bg,
      {engine: [pal.accent, .9], window: [pal.accent, .6]});
  }

  // Multicrew: the ship with its crew standing on holo-pads either side,
  // linked to it.
  function multicrew(s, st, pal) {
    sky(s, st, .6);
    const x = s.W * .55, y = s.H * .52;
    const cam = camera(x, y, 6.5, {yaw: -.45, pitch: -.3, persp: 14});
    s.solid(MODELS.ship(), cam, {yaw: Math.sin(st.p * .12) * .15}, st.c, 1, pal.bg, {engine: [st.c, .6]});
    for (const [side, delay] of [[-1, 0], [1, .5]]) {
      const cx = x + side * s.W * .27, base = s.H * .86;
      s.arc(cx, base, 8, 2.2, 0, TAU, pal.accent, .5, 1);
      const person = camera(cx, base, 9, {yaw: side * .6, pitch: -.15});
      s.solid(MODELS.commander(0, {walking: false}), person, {scale: 1.05}, st.c, .9, pal.bg,
        {visor: [pal.accent, .8], lamp: false});
      const t = fract(st.p * .4 + delay);
      const from = [cx - side * 5, s.H * .45], to = [x - side * 14, y];
      s.line(...from, ...to, pal.accent, .22);
      s.spark(lerp(from[0], to[0], t), lerp(from[1], to[1], t), .9, pal.accent, pal.text, Math.sin(t * Math.PI) * .9);
    }
  }

  // Exploration: the discovery scanner's wave rolls out across the system
  // and each world lights as it passes. The worlds are decorative.
  function exploration(s, st, pal) {
    sky(s, st, .7);
    const x = s.W * .16, y = s.H * .56;
    const ping = fract(st.p * .12), reach = ping * s.W * 1.05;
    s.arc(x, y, reach, reach * .3, 0, TAU, st.c, (1 - ping) * .6, 1.4);
    s.arc(x, y, reach * .92, reach * .28, 0, TAU, st.c, (1 - ping) * .25, 1);
    const worlds = [[.42, .5, .16, 'rock'], [.6, .38, .09, 'ice'], [.76, .6, .26, 'gas'], [.92, .34, .07, 'rock']];
    worlds.forEach(([u, v, size, kind], index) => {
      const wx = s.W * u, wy = s.H * v, lit = clamp(1 - Math.abs(wx - x - reach) / 24);
      s.sphere(wx, wy, s.H * size, st.c, pal.bg, {spin: st.p * .05, seed: index + 2, kind, grid: lit > .1,
        rings: kind === 'gas' ? {tilt: .3, alpha: .35} : null});
      if (lit > .01) s.bloom(wx, wy, s.H * size * 2, st.c, lit * .5);
    });
    const cam = camera(x, y, 5, {yaw: -.3, pitch: -.3, persp: 14});
    s.solid(MODELS.ship(), cam, {}, st.c, 1, pal.bg, {engine: [st.c, .6]});
  }

  // ---------------------------------------------------------------------
  // The frame shift drive: supercruise, charging, witch-space, arrival.
  // ---------------------------------------------------------------------

  function cruise(s, st, pal) {
    const c = st.c, cy = s.H / 2, vx = s.W * .74, key = st.key;
    const sco = key === 'supercruise_overcharge', assist = key === 'supercruise_assist';
    const tint = sco ? pal.accent : c;
    // The destination waits at the vanishing point, ringed and turning.
    s.sphere(vx, cy, s.H * .2, c, pal.bg, {spin: st.p * .04, seed: 5, kind: 'gas', rings: {tilt: .26, alpha: .5}});
    // The frame shift bubble ripples outward round the heading.
    for (let index = 0; index < 4; index += 1) {
      const t = fract(st.p * (sco ? .5 : .22) + index / 4), k = t * t, r = lerp(s.H * .4, s.W * .95, k);
      s.arc(vx, cy, r, r * .4, 0, TAU, tint, Math.sin(t * Math.PI) * (sco ? .42 : .24), .8 + k);
    }
    streaks(s, st, {x: vx, count: sco ? 34 : 24, speed: sco ? .56 : .3, strength: sco ? .85 : .6,
      width: sco ? 1.2 : 1, color: tint});
    if (assist) {
      // Supercruise assist holds a lane onto the destination.
      for (const side of [-1, 1]) {
        s.poly([[-4, cy + side * s.H * .46], [vx * .5, cy + side * s.H * .2], [vx - 12, cy + side * 3]],
          pal.accent, .5, 1.1);
      }
      for (let index = 0; index < 5; index += 1) {
        const t = fract(st.p * .3 + index / 5), k = smooth(t);
        s.chevron(lerp(6, vx - 14, k), cy, 1, pal.accent, Math.sin(t * Math.PI) * .8, lerp(4, 2, k), 1.3);
      }
    }
    if (sco) {
      // Overcharge crackles along the bubble's edge.
      for (let bolt = 0; bolt < 3; bolt += 1) {
        const seedTick = Math.floor(st.p * 6 + bolt * 3.3);
        if (hash(seedTick) < .35) continue;
        const side = hash(seedTick + 1) > .5 ? 1 : -1, points = [];
        for (let step = 0; step <= 8; step += 1) {
          const u = step / 8;
          points.push([lerp(s.W * (.1 + hash(seedTick + 2) * .3), vx - 16, u),
            cy + side * (s.H * .42 * (1 - u) + 2) + (hash(seedTick * 7 + step) - .5) * 5]);
        }
        s.poly(points, pal.text, .6, .9);
      }
    }
    boostCharge(s, st, pal, vx);
  }

  // A passenger taxi carries the commander: the Apex shuttle in its lane.
  function taxi(s, st, pal) {
    const cy = s.H / 2;
    streaks(s, st, {x: s.W * .92, count: 16, speed: .22, strength: .4});
    const x = s.W * .5, y = cy + Math.sin(st.p * .3) * 1.2;
    const cam = camera(x, y, 7, {yaw: -.55, pitch: -.3, persp: 14});
    trail(s, [x - 14, y + 1], [x - 60, y + 3], st.c, .5, 9);
    s.solid(MODELS.ship('taxi'), cam, {roll: Math.sin(st.p * .25) * .06}, st.c, 1, pal.bg,
      {window: [pal.text, .7], engine: [pal.accent, .85]});
  }

  // The drive's containment ring: twelve segments round a core, seen three
  // quarters on. `lit(index)` lights each segment; `spin` turns the ring;
  // `arcs` throws charge from the segments into the core.
  function driveRing(s, st, pal, x, y, unit, {spin = 0, color = st.c, lit = () => .5, core = 1, tilt = .45,
    arcs = 0} = {}) {
    const cam = camera(x, y, unit, {yaw: tilt, pitch: -.3, persp: 12});
    const segment = MODELS.driveSegment();
    const order = [];
    for (let index = 0; index < 12; index += 1) {
      const angle = index * TAU / 12 + spin;
      const place = {y: Math.sin(angle) * 1.55, z: Math.cos(angle) * 1.55, pitch: -angle};
      order.push({index, place, depth: cam.look([0, place.y, place.z])[2]});
    }
    order.sort((left, right) => left.depth - right.depth);
    const draw = (list) => {
      for (const {index, place} of list) {
        const light = clamp(lit(index));
        s.solid(segment, cam, place, color, 1, pal.bg);
        const [sx, sy] = cam.project([0, place.y, place.z]);
        s.bloom(sx, sy, unit * 1.1, color, light * .6);
        s.dot(sx, sy, .9, pal.text, light * .85);
      }
    };
    draw(order.slice(0, 6));
    s.bloom(x, y, unit * 2.4 * core, color, .5 * core);
    s.spark(x, y, 1.6 * core, color, pal.text, .95 * core);
    for (let arc = 0; arc < arcs; arc += 1) {
      const tick = Math.floor(st.p * 7 + arc * 5.3);
      if (hash(tick) < .3) continue;
      const angle = hash(tick + 1) * TAU;
      const [ex, ey] = cam.project([0, Math.sin(angle) * 1.4, Math.cos(angle) * 1.4]);
      const points = [];
      for (let step = 0; step <= 6; step += 1) {
        const u = step / 6;
        points.push([lerp(ex, x, u) + (hash(tick * 3 + step) - .5) * 4 * Math.sin(u * Math.PI),
          lerp(ey, y, u) + (hash(tick * 5 + step) - .5) * 4 * Math.sin(u * Math.PI)]);
      }
      s.poly(points, pal.text, .7, .8);
    }
    draw(order.slice(6));
    return cam;
  }

  function charge(s, st, pal) {
    const c = st.c, cy = s.H / 2, hyper = st.key === 'hyper_charge';
    const fx = s.W * (hyper ? .5 : .6), spool = .52 + .48 * smooth(st.age / 2.3);
    const color = hyper ? pal.accent : c;
    // Space folds toward the drive: streams drawn into the ring.
    for (let index = 0; index < 22; index += 1) {
      const angle = index * TAU / 22 + st.p * .06, t = fract(st.p * (hyper ? .5 : .36) + hash(index + 3));
      const far = s.W * .55, near = 10;
      const r0 = lerp(far, near, smooth(t)), r1 = lerp(far, near, smooth(Math.min(1, t + .1)));
      s.line(fx + Math.cos(angle) * r0, cy + Math.sin(angle) * r0 * .42, fx + Math.cos(angle) * r1,
        cy + Math.sin(angle) * r1 * .42, color, ends(t, .2) * .6 * spool, 1);
    }
    driveRing(s, st, pal, fx, cy, hyper ? 9.5 : 8.6, {
      spin: st.p * (hyper ? 1.1 : .75) * spool, color, arcs: hyper ? 3 : 2,
      lit: (index) => .2 + .8 * Math.pow(wave(st.p * (hyper ? 1.1 : .8) - index / 12), 3) * spool,
      core: .6 + .4 * spool,
    });
    if (hyper) {
      // The destination star brightens ahead as the throat opens toward it.
      const sx = s.W * .9;
      for (let index = 0; index < 5; index += 1) {
        const t = fract(st.p * .4 + index / 5), r = lerp(5, 17, t);
        s.arc(lerp(fx + 26, sx - 6, t), cy, r * .35, r, 0, TAU, pal.accent, Math.sin(t * Math.PI) * .5 * spool, 1.1);
      }
      s.bloom(sx, cy, 14 + 6 * spool, pal.text, .3 + .3 * spool);
      s.spark(sx, cy, 2.2, pal.accent, pal.text, .6 + .4 * spool);
      s.line(sx - 18, cy, sx + 18, cy, pal.text, .25 * spool, .8);
    }
  }

  // Witch-space: rings of the tunnel stream out of the vanishing point in
  // true perspective, twisting, with gas filaments spiralling past.
  function witchSpace(s, st, pal, x, {speed = .3, color = st.c, gas = pal.accent, rings = 12, alpha = 1} = {}) {
    const cy = s.H / 2;
    for (let index = 0; index < rings; index += 1) {
      const t = fract(st.p * speed + index / rings), k = .07 / (1.07 - t);
      const radius = k * s.W * .75, points = [];
      for (let step = 0; step < 36; step += 1) {
        const angle = step * TAU / 36 + t * 2.4 + st.p * .08;
        const wobble = 1 + .06 * Math.sin(angle * 3 + index * 1.7 + st.p * .5);
        points.push([x + Math.cos(angle) * radius * wobble, cy + Math.sin(angle) * radius * wobble * .82]);
      }
      s.poly(points, index % 3 ? color : gas, smooth(t / .25) * (1 - smooth((t - .8) / .2)) * .45 * alpha,
        .5 + t * 1.2, true);
    }
    for (let strand = 0; strand < 8; strand += 1) {
      const points = [];
      for (let step = 0; step <= 22; step += 1) {
        const u = step / 22, k = .07 / (1.07 - u * .9);
        const angle = strand * TAU / 8 + u * 3.2 + st.p * .5;
        points.push([x + Math.cos(angle) * k * s.W * .6, cy + Math.sin(angle) * k * s.W * .45]);
      }
      s.poly(points, strand % 2 ? gas : color, .16 * alpha, 1.2);
    }
    s.bloom(x, cy, s.H * .8, gas, .2 * alpha);
    streaks(s, st, {x, count: 20, speed: speed * 1.3, strength: .6 * alpha, twist: .2, color});
  }

  function tunnel(s, st, pal) {
    const cy = s.H / 2, x = s.W * .68 + Math.sin(st.p * .15) * 5, opening = st.key === 'jumping';
    witchSpace(s, st, pal, x, {speed: opening ? .45 : .32});
    // The destination star waits at the tunnel's end; on the way out it
    // swells to fill the throat.
    const swell = opening ? smooth(st.age / 1.8) : 0;
    s.bloom(x, cy, 12 + swell * s.H * 1.4, pal.text, .35 + swell * .35);
    s.spark(x, cy, 1.6 + swell * 3, st.c, pal.text, .9);
    if (opening) s.line(0, cy, s.W, cy, pal.text, (1 - swell) * .6, 1 + swell * 2);
  }

  // Arrival: the star the jump landed at, huge and close in its own class
  // colour, the ship just out of witch-space and settling.
  function arrival(s, st, pal) {
    const settle = smooth(st.age / 2.2);
    streaks(s, st, {x: s.W * .82, count: 14, speed: .22 * (1 - settle * .8), strength: (1 - settle) * .6});
    stellarBody(s, st, pal, s.W * .86, s.H * .52, s.H * .6);
    const x = lerp(s.W * .18, s.W * .38, settle), y = s.H * .55;
    trail(s, [x - 10, y], [x - 50, y], st.c, .6 * (1 - settle * .6), 9);
    const cam = camera(x, y, 5.5, {yaw: -.4, pitch: -.3, persp: 14});
    s.solid(MODELS.ship(), cam, {}, st.c, 1, pal.bg, {engine: [st.c, .8]});
    const ring = clamp(st.age / 1.4);
    s.arc(x, y, 6 + ring * 40, 3 + ring * 16, 0, TAU, pal.text, (1 - ring) * .6, 1.3);
  }

  // Dropping out of supercruise at the destination: the drop flash, the
  // world ahead coming up to meet the ship, the streaks dying away.
  function localArrival(s, st, pal) {
    const settle = smooth(st.age / 2.2), cy = s.H / 2;
    sky(s, st, settle * .8);
    streaks(s, st, {x: s.W * .76, count: 16, speed: .2 * (1 - settle), strength: (1 - settle) * .6});
    s.sphere(s.W * .76, cy + 4, s.H * lerp(.3, .42, settle), st.c, pal.bg, {spin: st.p * .03, seed: 9,
      atmosphere: pal.accent, detail: 1.2});
    const x = s.W * .36, flash = clamp(st.age / 1.2);
    s.arc(x, cy, 4 + flash * 34, 2 + flash * 14, 0, TAU, pal.text, (1 - flash) * .7, 1.3);
    const cam = camera(x, cy, 5.5, {yaw: -.45, pitch: -.3, persp: 14});
    s.solid(MODELS.ship(), cam, {}, st.c, 1, pal.bg, {engine: [st.c, .7]});
    s.brackets(s.W * .76, cy + 4, s.H * .5 + (1 - settle) * 14, s.H * .48, st.c, .3 + .4 * settle);
  }

  // Escaping an interdiction: the tether snaps into pieces that tumble
  // away while the ship breaks for its destination.
  function evaded(s, st, pal) {
    const settle = smooth(st.age / 2.2), cy = s.H / 2;
    streaks(s, st, {x: s.W * .9, count: 18, speed: .3, strength: .5});
    const enemy = camera(s.W * .1, cy - 4, 5, {yaw: -.3, pitch: -.3, persp: 14});
    s.solid(MODELS.ship('interdictor'), enemy, {}, st.c, .4 + .3 * (1 - settle), pal.bg, {engine: [pal.red, .5]});
    for (let index = 0; index < 7; index += 1) {
      const u = (index + .5) / 7, drift = settle * (6 + hash(index) * 8);
      const x = lerp(s.W * .16, s.W * .5, u), y = cy + Math.sin(u * 9) * 3 + (hash(index + 4) - .5) * drift * 2;
      const angle = hash(index + 8) * settle * 3;
      s.line(x - Math.cos(angle) * 4, y - Math.sin(angle) * 4, x + Math.cos(angle) * 4, y + Math.sin(angle) * 4,
        pal.red, .7 * (1 - settle * .6), 1.2);
    }
    const x = s.W * lerp(.56, .66, settle);
    const cam = camera(x, cy, 6, {yaw: -.45, pitch: -.3, persp: 14});
    trail(s, [x - 12, cy], [x - 44, cy], pal.accent, .7, 8);
    s.solid(MODELS.ship(), cam, {roll: Math.sin(st.p * .6) * .2 * (1 - settle)}, st.c, 1, pal.bg,
      {engine: [pal.accent, .9]});
    s.ring(s.W * .86, cy, 7, 7, 16, pal.accent, .5 + .3 * wave(st.p * .4), 1.2);
  }

  // The drive cooling after a jump: the ring slows and its segments fade
  // from white heat to dark, the nearest the core last. Not a timer.
  function cooldown(s, st, pal) {
    const cy = s.H / 2, fx = s.W * .64, heat = 1 - smooth(st.age / 3.2);
    for (let index = 0; index < 9; index += 1) {
      const t = fract(st.p * .2 + index / 9), x = fx + (hash(index + 40) - .5) * s.W * .5;
      s.line(x, cy - 4 - t * 16, x + Math.sin(t * 6 + index) * 2, cy - 8 - t * 16, st.c,
        Math.sin(t * Math.PI) * (.12 + heat * .45));
    }
    driveRing(s, st, pal, fx, cy, 6.4, {
      spin: st.p * (.1 + .45 * heat),
      lit: (index) => heat * (.6 + .4 * hash(index)) + .12,
      core: .35 + .5 * heat,
    });
  }

  // FSD injection armed: synthesis feeds the drive's ring; the chevrons
  // show the boost the journal reports.
  function injection(s, st, pal) {
    const cy = s.H / 2, fx = s.W * .6;
    for (let index = 0; index < 3; index += 1) {
      const y = 6 + index * (s.H - 12) / 2;
      s.poly([[6, y], [fx * .5, y], [fx - 20, cy]], st.c, .28);
      const t = fract(st.p * .3 + index / 3);
      const x = lerp(6, fx - 20, t), yy = t < .55 ? y : lerp(y, cy, (t - .55) / .45);
      s.spark(x, yy, 1, st.c, pal.text, Math.sin(t * Math.PI) * .85);
    }
    driveRing(s, st, pal, fx, cy, 5.6, {spin: st.p * .4, lit: (index) => .35 + .5 * wave(st.p * .5 - index / 12)});
    const percent = st.d.fsdInjectionPercent;
    const level = percent >= 100 ? 3 : percent >= 50 ? 2 : 1;
    for (let index = 0; index < level; index += 1) s.chevron(fx + 26 + index * 8, cy, 1, pal.accent, .85, 4, 1.4);
  }

  // ---------------------------------------------------------------------
  // The fleet carrier.
  // ---------------------------------------------------------------------

  function carrierAt(s, st, pal, {x, y, unit, yaw = -.42, pitch = -.24, lamps = {}, alpha = 1, persp = 30,
    place = {}} = {}) {
    const cam = camera(x, y, unit, {yaw, pitch, persp});
    const blink = .2 + .8 * Math.pow(wave(st.p * .5), 6);
    return s.solid(MODELS.carrier(), cam, place, st.c, alpha, pal.bg,
      {engine: [st.c, .5], window: [st.c, .6], beacon: [pal.red, blink], ...lamps});
  }

  const padLamps = (level) => Object.fromEntries(Array.from({length: 8}, (_, index) => [`pad${index}`, level(index)]));

  function carrierScene(s, st, pal) {
    const key = st.key, cy = s.H / 2, x = s.W * .6, y = s.H * .64, unit = 6.4;
    if (key === 'carrier_transit') {
      // The carrier's own slow jump: the hull held steady in a wide tunnel.
      witchSpace(s, st, pal, s.W * .6, {speed: .16, rings: 8, alpha: .8});
      carrierAt(s, st, pal, {x, y: y + Math.sin(st.p * .3) * .6, unit,
        lamps: {engine: [pal.accent, .9], ...padLamps(() => [st.c, .2])}});
      return;
    }
    if (key === 'carrier_arrival') {
      const settle = smooth(st.age / 2.8);
      sky(s, st, settle);
      s.bloom(x, cy, s.H * (2.2 - settle * 1.4), pal.text, (1 - settle) * .7);
      for (let index = 0; index < 3; index += 1) {
        const t = clamp(st.age / 2.2 - index * .25), r = 20 + smooth(t) * s.W * .6;
        s.arc(x, cy, r, r * .3, 0, TAU, st.c, (1 - t) * .5, 1.2);
      }
      carrierAt(s, st, pal, {x: lerp(s.W * .42, x, settle), y, unit,
        lamps: {engine: [pal.accent, .9 - settle * .5], ...padLamps(() => [st.c, .4])}});
      return;
    }
    sky(s, st, .8, .4);
    if (key === 'carrier_preparing') {
      // Spooling for a jump: the drive bells brighten, pads light in turn
      // and charge rings run the hull's length. No countdown is implied.
      const at = carrierAt(s, st, pal, {x, y, unit, lamps: {
        engine: [pal.accent, .5 + .45 * wave(st.p * .8)],
        ...padLamps((index) => [st.c, .15 + .8 * Math.pow(wave(st.p * .35 - index / 8), 4)]),
      }});
      for (let index = 0; index < 3; index += 1) {
        const t = fract(st.p * .3 + index / 3);
        const [rx, ry] = at([lerp(6.5, -6.5, t), 0, 0]);
        s.arc(rx, ry, 5, 11, 0, TAU, pal.accent, Math.sin(t * Math.PI) * .5, 1.1);
      }
    } else if (key === 'carrier_lockdown') {
      // Locked down: pads red, drives cold, armoured shutters close over
      // the deck once and stay shut.
      const close = smooth(st.age / 2.5);
      const at = carrierAt(s, st, pal, {x, y, unit, lamps: {
        engine: [st.c, .12], beacon: [pal.red, .9], window: [pal.red, .5],
        ...padLamps(() => [pal.red, .35 + .3 * (1 - close)]),
      }});
      for (const side of [-1, 1]) {
        const [ax, ay] = at([-1.4, -1, side * lerp(2.6, .1, close)]), [bx, by] = at([4.6, -1, side * lerp(2.6, .1, close)]);
        s.line(ax, ay, bx, by, pal.red, .75, 1.6);
      }
    } else {
      // In the carrier's vicinity: a shuttle of traffic settles onto a pad
      // while the beacons turn over.
      const at = carrierAt(s, st, pal, {x, y, unit, lamps: padLamps((index) => [st.c, index === 5 ? .9 : .45])});
      const t = fract(st.p * .09);
      const [px, py] = at([2.25, -.74, .55]);
      const sx = lerp(-10, px, smooth(t)), sy = lerp(s.H * .2, py - 3, smooth(t)) - Math.sin(t * Math.PI) * 6;
      const cam = camera(sx, sy, 3.2, {yaw: -.4, pitch: -.3});
      trail(s, [sx - 6, sy - 1], [sx - 26, sy - 6], st.c, ends(t) * .6, 6);
      s.solid(MODELS.ship(), cam, {}, st.c, ends(t, .1), pal.bg, {engine: [st.c, .8]});
    }
  }

  // On foot on a carrier's flight deck: the hull under the commander's
  // boots, the command tower behind and the pads lit along the deck.
  function carrierDeck(s, st, pal) {
    sky(s, st, .7, .3);
    const at = carrierAt(s, st, pal, {x: s.W * .56, y: s.H * .98, unit: 11.5, yaw: -.3, pitch: -.42, persp: 24,
      lamps: padLamps((index) => [st.c, .25 + .35 * Math.pow(wave(st.p * .14 - index / 8), 4)])});
    const walk = fract(st.p * .04);
    const [fx, fy] = at([lerp(-.4, 4.4, walk), -.74, .15]);
    const person = camera(fx, fy, 7.5, {yaw: -.5, pitch: -.1});
    s.solid(MODELS.commander(st.p * 2.2), person, {}, st.c, ends(walk, .06), pal.bg,
      {visor: [pal.accent, .8], lamp: [pal.text, .7]});
  }

  // ---------------------------------------------------------------------
  // Scanners and maps.
  // ---------------------------------------------------------------------

  // The Full Spectrum Scanner: the signal band along the foot, filled as
  // far as the journal's scan progress, and the scanner's lens resolving a
  // world from its lattice as it focuses.
  function fss(s, st, pal) {
    const c = st.c, base = s.H - 5, x0 = 6, x1 = s.W * .56;
    sky(s, st, .7, .3);
    const peaks = [.08, .19, .31, .44, .57, .7, .83, .94], points = [];
    for (let index = 0; index <= 90; index += 1) {
      const u = index / 90;
      let amp = .5 + Math.sin(u * 61 + st.p * .7) * .3;
      peaks.forEach((at, n) => {
        amp += Math.exp(-(((u - at) / .018) ** 2)) * (4 + (n % 3) * 2.4 + wave(st.p * .26 + n * .37) * 2);
      });
      points.push([lerp(x0, x1, u), base - amp]);
    }
    const cut = Math.max(1, Math.round(clamp(st.d.scan) * 90));
    s.poly(points.slice(0, cut + 1), pal.accent, .9, 1.2);
    if (cut < 90) s.poly(points.slice(cut), c, .3, 1);
    s.line(x0, base + 1, x1, base + 1, c, .3);
    const needle = lerp(x0, x1, wave(st.p * .12));
    s.line(needle, 5, needle, base, pal.text, .3, .8);
    s.bloom(needle, base - 5, 6, pal.accent, .35);
    // The lens.
    const lx = s.W * .76, ly = s.H / 2, lr = s.H * .42, focus = .35 + .65 * clamp(st.d.scan);
    s.sphere(lx, ly, lr * .72, c, pal.bg, {spin: st.p * .06, seed: 11, grid: true, detail: focus,
      atmosphere: focus > .6 ? pal.accent : null});
    s.arc(lx, ly, lr, lr, 0, TAU, c, .55, 1.2);
    s.arc(lx, ly, lr * 1.12, lr * 1.12, 0, TAU, c, .2);
    const sweep = st.p * TAU * .18;
    s.arc(lx, ly, lr, lr, sweep, sweep + .8, pal.accent, .8, 1.6);
    for (let index = 0; index < 4; index += 1) {
      const angle = index * Math.PI / 2;
      s.line(lx + Math.cos(angle) * lr * .84, ly + Math.sin(angle) * lr * .84,
        lx + Math.cos(angle) * lr * 1.18, ly + Math.sin(angle) * lr * 1.18, c, .6, 1.1);
    }
    s.line(x1 + 3, ly, lx - lr * 1.2, ly, c, .22);
  }

  // A point on a turning world, as scene.sphere draws it.
  function onWorld(x, y, r, lat, lon, spin, tilt = .35) {
    const cx = Math.cos(lat) * Math.sin(lon + spin), cy = -Math.sin(lat), cz = Math.cos(lat) * Math.cos(lon + spin);
    const py = cy * Math.cos(tilt) - cz * Math.sin(tilt), pz = cy * Math.sin(tilt) + cz * Math.cos(tilt);
    return [x + cx * r, y + py * r, pz];
  }

  // The Detailed Surface Scanner: probes arc from the ship onto a turning
  // world and each impact leaves its mapped patch glowing on the surface.
  // Probe counts come from the journal's DSS label when it gives them.
  function dss(s, st, pal) {
    const c = st.c, cy = s.H / 2, gx = s.W * .7, r = s.H * .5, spin = st.p * .08;
    sky(s, st, .6, .3);
    s.sphere(gx, cy + 4, r, c, pal.bg, {spin, seed: 4, grid: true, detail: 1.3});
    const probes = /(\d+)\s*\/\s*(\d+)/.exec(st.label);
    const mapped = probes ? Math.min(12, Number(probes[1])) : 5;
    for (let index = 0; index < mapped; index += 1) {
      const lat = (hash(index + 30) - .5) * 1.6, lon = index * TAU / Math.max(1, mapped);
      const [px, py, pz] = onWorld(gx, cy + 4, r, lat, lon, spin);
      if (pz > .05) {
        s.bloom(px, py, r * .34 * pz, pal.accent, .8 * pz);
        s.arc(px, py, r * .16 * pz, r * .16, 0, TAU, pal.accent, .7 * pz, .9);
      }
    }
    const lx = s.W * .12, ly = s.H * .72;
    for (let index = 0; index < 3; index += 1) {
      const t = fract(st.p * .2 + index / 3);
      const [tx, ty, tz] = onWorld(gx, cy + 4, r, (index - 1) * .45, -.7 + index * .5, 0, 0);
      const x = lerp(lx, tx, t), y = lerp(ly, ty, t) - Math.sin(t * Math.PI) * (12 + index * 4);
      s.spark(x, y, 1.2, pal.accent, pal.text, Math.sin(t * Math.PI) * .9 + .1);
      if (t > .86 && tz > 0) {
        const splash = (t - .86) / .14;
        s.arc(tx, ty, 2 + splash * 7, 1 + splash * 3, 0, TAU, pal.accent, (1 - splash) * .7, 1.1);
      }
    }
    const cam = camera(lx, ly, 4.6, {yaw: -.4, pitch: -.3, persp: 14});
    s.solid(MODELS.ship(), cam, {}, c, 1, pal.bg, {engine: [c, .6]});
    if (probes) {
      const used = Math.min(16, Number(probes[1])), goal = Math.min(16, Number(probes[2]));
      for (let index = 0; index < Math.max(used, goal); index += 1) {
        const x = 8 + index * 7, lit = index < used;
        s.poly([[x, 6], [x + 2.5, 3], [x + 5, 6], [x + 2.5, 9]], index >= goal ? pal.yellow : c,
          lit ? .88 : .25, 1, true, lit ? .35 : 0);
      }
    }
  }

  // The galaxy: a few hundred stars on four spiral arms round a bright
  // bar, turning slowly on a tilted plane, with the commander's own spot
  // marked in the Orion Spur. Decorative, not a star chart.
  const GALAXY = Array.from({length: 320}, (_, index) => {
    const arm = index % 4, r = Math.pow(hash(index + 500), .85);
    const core = index < 70;
    const reach = core ? Math.pow(hash(index + 503), 1.6) * .24 : .12 + r * .88;
    const angle = core ? hash(index + 501) * TAU
      : arm * Math.PI / 2 + reach * 4.4 + (hash(index + 502) - .5) * .42 * (1 - r * .45);
    return [Math.cos(angle) * reach, (hash(index + 504) - .5) * (core ? .1 : .04), Math.sin(angle) * reach,
      .3 + hash(index + 505) * .7];
  });

  function galaxyMap(s, st, pal) {
    const c = st.c, gx = s.W * .58, gy = s.H * .5;
    const cam = camera(gx, gy, s.W * .3, {yaw: st.p * .05, pitch: -.9, persp: 5});
    s.bloom(gx, gy, s.H * .8, c, .4);
    // Dust lanes along each arm give the spiral its shape.
    for (let arm = 0; arm < 4; arm += 1) {
      const lane = [];
      for (let step = 0; step <= 24; step += 1) {
        const r = .12 + step / 24 * .88, angle = arm * Math.PI / 2 + r * 4.4;
        lane.push(cam.project([Math.cos(angle) * r, 0, Math.sin(angle) * r]));
      }
      s.poly(lane, c, arm % 2 ? .18 : .3, arm % 2 ? 1.4 : 2.2);
    }
    for (const [x, y, z, bright] of GALAXY) {
      const [sx, sy, depth] = cam.project([x, y, z]);
      s.dot(sx, sy, .4 + bright * .45, c, (.25 + bright * .6) * (.65 + depth * .35));
    }
    s.bloom(gx, gy, s.H * .3, pal.text, .45);
    const [hx, hy] = cam.project([.52, 0, -.36]);
    s.ring(hx, hy, 3.5 + wave(st.p * .5) * 2, 2.6, 4, pal.accent, .9, 1.2, Math.PI / 4);
    s.dot(hx, hy, 1, pal.text, .9);
  }

  // The system map, as the game lays it out: the star at the left and its
  // bodies in a row, moons hanging beneath, the cursor stepping along.
  function systemMap(s, st, pal) {
    const c = st.c, cy = s.H * .42;
    sky(s, st, .4, .2);
    stellarBody(s, st, pal, s.W * .08, cy, s.H * .2, {flares: false});
    const bodies = [[.25, .1, 'rock', 0], [.38, .13, 'ice', 1], [.55, .22, 'gas', 3], [.74, .17, 'gas', 2],
      [.9, .09, 'rock', 1]];
    s.line(s.W * .14, cy, s.W * .96, cy, c, .15);
    const pick = Math.floor(fract(st.p * .05) * bodies.length);
    bodies.forEach(([u, size, kind, moons], index) => {
      const x = s.W * u, r = s.H * size;
      s.sphere(x, cy, r, c, pal.bg, {spin: st.p * .06, seed: index + 20, kind,
        rings: index === 2 ? {tilt: .3, alpha: .4} : null});
      for (let moon = 0; moon < moons; moon += 1) {
        const my = cy + r + 5 + moon * 6;
        s.line(x, cy + r + 1, x, my - 2, c, .2, .7);
        s.sphere(x, my, 1.8, c, pal.bg, {seed: index * 5 + moon, kind: 'ice', detail: .3});
      }
      if (index === pick) s.brackets(x, cy, r + 5, r + 4, pal.accent, .85, 3, 1.1);
    });
  }

  // The orrery: worlds on their orbits round the star, in perspective.
  function orrery(s, st, pal) {
    const c = st.c, ox = s.W * .55, oy = s.H * .5;
    sky(s, st, .5, .2);
    const cam = camera(ox, oy, s.W * .1, {yaw: st.p * .02, pitch: -.42, persp: 14});
    const worlds = [];
    for (let index = 0; index < 5; index += 1) {
      const radius = .9 + index * .85, angle = st.p * .5 / (index + 1) + index * 1.9, ring = [];
      for (let step = 0; step <= 40; step += 1) {
        const a = step * TAU / 40;
        ring.push(cam.project([Math.cos(a) * radius, 0, Math.sin(a) * radius]));
      }
      s.poly(ring, c, .25, .8);
      worlds.push({at: cam.project([Math.cos(angle) * radius, 0, Math.sin(angle) * radius]), index});
    }
    worlds.sort((left, right) => left.at[2] - right.at[2]);
    const [sx, sy] = cam.project([0, 0, 0]);
    let starDrawn = false;
    for (const {at: [x, y, depth, k], index} of worlds) {
      if (!starDrawn && depth > 0) {
        stellarBody(s, st, pal, sx, sy, s.H * .13, {flares: false});
        starDrawn = true;
      }
      s.sphere(x, y, (1.8 + (index % 3) * 1.1) * k, c, pal.bg, {spin: st.p * .1, seed: index + 40,
        kind: index === 3 ? 'gas' : 'rock', detail: .4});
    }
    if (!starDrawn) stellarBody(s, st, pal, sx, sy, s.H * .13, {flares: false});
  }

  // Powerplay: two powers' spheres of influence over a bubble of systems,
  // their control systems ringed. Decorative, not real territory.
  const BUBBLE = Array.from({length: 90}, (_, index) => {
    const u = hash(index + 700) * TAU, v = Math.acos(2 * hash(index + 701) - 1), r = Math.cbrt(hash(index + 702));
    return [Math.sin(v) * Math.cos(u) * r * 1.6, Math.cos(v) * r * .7, Math.sin(v) * Math.sin(u) * r * 1.6];
  });

  function powerMap(s, st, pal) {
    const c = st.c, cam = camera(s.W * .56, s.H * .5, s.H * .55, {yaw: st.p * .06, pitch: -.4, persp: 6});
    const powers = [{centre: [-.7, 0, .2], color: c}, {centre: [.8, -.1, -.3], color: pal.accent}];
    for (const power of powers) {
      const [x, y, , k] = cam.project(power.centre);
      s.bloom(x, y, s.H * .6 * k, power.color, .35);
      s.arc(x, y, s.H * .5 * k, s.H * .5 * k, 0, TAU, power.color, .3, 1);
    }
    BUBBLE.forEach((point, index) => {
      const [x, y, depth] = cam.project(point);
      const owner = powers.find((power) => Math.hypot(...point.map((value, axis) => value - power.centre[axis])) < .75);
      s.dot(x, y, owner ? .9 : .6, owner ? owner.color : c, (owner ? .8 : .35) * (.6 + depth * .3));
      if (owner && index % 9 === 0) {
        s.ring(x, y, 2.6, 2.6, 6, owner.color, .5 + .35 * wave(st.p * .3 + index * .1), 1, Math.PI / 6);
        const [cx, cy] = cam.project(owner.centre);
        s.line(x, y, cx, cy, owner.color, .25, .7);
      }
    });
  }

  // The Codex: a specimen crystal turning in a scanning cradle while
  // entries orbit it.
  function codex(s, st, pal) {
    const c = st.c, x = s.W * .6, y = s.H * .5;
    sky(s, st, .5, .2);
    const cam = camera(x, y, 9, {yaw: st.p * .3, pitch: -.35, persp: 12});
    for (let ring = 0; ring < 2; ring += 1) {
      const radius = 2 + ring * .8, orbit = [];
      for (let step = 0; step <= 36; step += 1) {
        const angle = step * TAU / 36;
        orbit.push(cam.project([Math.cos(angle) * radius, ring ? -.4 : .5, Math.sin(angle) * radius]));
      }
      s.poly(orbit, c, .25, .8);
      for (let entry = 0; entry < 5; entry += 1) {
        const angle = entry * TAU / 5 - st.p * (.2 + ring * .1);
        const [ex, ey] = cam.project([Math.cos(angle) * radius, ring ? -.4 : .5, Math.sin(angle) * radius]);
        s.rect(ex - 1.5, ey - 1.1, 3, 2.2, ring ? pal.accent : c, .7, true);
      }
    }
    s.solid(MODELS.crystal(3), cam, {roll: Math.PI / 2, yaw: st.p * .2}, c, 1, pal.bg);
    const scan = y - 14 + wave(st.p * .25) * 28;
    s.line(x - 26, scan, x + 26, scan, pal.accent, .55, 1);
    s.bloom(x, scan, 10, pal.accent, .25);
  }

  // An unspecified map: a navigable grid in perspective and a cursor.
  function genericMap(s, st, pal) {
    const c = st.c, cam = camera(s.W * .55, s.H * .6, s.W * .07, {pitch: -.9, yaw: st.p * .03, persp: 10});
    for (let index = -5; index <= 5; index += 1) {
      s.line(...cam.project([index, 0, -5]).slice(0, 2), ...cam.project([index, 0, 5]).slice(0, 2), c, .22, .8);
      s.line(...cam.project([-5, 0, index]).slice(0, 2), ...cam.project([5, 0, index]).slice(0, 2), c, .22, .8);
    }
    const [x, y] = cam.project([Math.sin(st.p * .21) * 3.5, 0, Math.cos(st.p * .17) * 3]);
    s.poly([[x, y - 6], [x + 4, y], [x, y + 3], [x - 4, y]], pal.accent, .9, 1.2, true, .2);
    s.line(x, y - 6, x, y - 14, pal.accent, .5);
    s.brackets(x, y - 2, 9, 7, c, .45);
  }

  // Nebulae and Lagrange clouds: glowing gas and slow-tumbling crystals.
  function phenomena(s, st, pal) {
    const c = st.c, tones = [c, pal.accent, pal.green, pal.yellow];
    for (let index = 0; index < 9; index += 1) {
      const x = s.W * (.08 + hash(index + 70) * .86) + Math.sin(st.p * .05 + index) * 6;
      const y = s.H * (.2 + hash(index + 71) * .6);
      s.bloom(x, y, s.H * (.5 + hash(index + 72) * .5), tones[index % 4], .24 + .14 * wave(st.p * .1 + index * .3));
    }
    sky(s, st, .6, .3);
    for (let index = 0; index < 6; index += 1) {
      const x = s.W * (.16 + index * .14), y = s.H * (.3 + hash(index + 80) * .4);
      const cam = camera(x, y, 5.5 + hash(index + 81) * 3.5, {pitch: -.2, persp: 12});
      s.bloom(x, y, 10, tones[index % 4], .25);
      s.solid(MODELS.crystal(), cam, {yaw: st.p * (.1 + hash(index + 82) * .15) + index,
        roll: st.p * .07 + index * 1.3, pitch: index}, tones[index % 4], 1, pal.bg);
    }
  }

  // ---------------------------------------------------------------------
  // Targets: what the pilot has selected, held in closing brackets.
  // ---------------------------------------------------------------------

  function target(s, st, pal) {
    const c = st.c, key = st.key, x = s.W * .66, y = s.H * .5;
    sky(s, st, .6, .4);
    const locked = smooth(st.age / 1.2);
    const clear = key === 'target_clear', gone = clear ? smooth(st.age / 1.6) : 0;
    const spread = clear ? 18 + gone * 40 : 16 + (1 - locked) * 26;
    s.line(10, y, x - spread - 6, y, c, .18);
    for (let index = 0; index < 5; index += 1) {
      const t = fract(st.p * .14 + index / 5), px = lerp(10, x - spread - 6, t);
      s.line(px, y - 2.5, px, y + 2.5, c, Math.sin(t * Math.PI) * .45);
    }
    if (key === 'target_system') {
      // The targeted system's star, as the route knows it; a plain star in
      // the HUD's colour when its class is not known.
      stellarBody(s, st, pal, x, y, s.H * .17, {family: st.targetFamily, tone: st.targetTone, flares: false});
    } else if (key === 'target_body') {
      s.sphere(x, y, s.H * .3, c, pal.bg, {spin: st.p * .08, seed: 14, grid: true, atmosphere: pal.accent});
    } else if (key === 'target_signal') {
      for (let index = 0; index < 3; index += 1) {
        const t = fract(st.p * .3 + index / 3), r = 5 + t * 26;
        s.arc(x, y, r, r * .45, 0, TAU, pal.accent, (1 - t) * .5, 1);
      }
      const cam = camera(x, y, 6, {pitch: -.3, persp: 12});
      s.solid(MODELS.beacon(), cam, {yaw: st.p * .25}, c, 1, pal.bg, {beacon: [pal.accent, .5 + .5 * wave(st.p * .8)]});
    } else {
      // Cleared, the target drifts on unmarked and fades from the lock.
      const cam = camera(x + gone * 16, y, 5.4, {pitch: -.32, persp: 14});
      s.solid(MODELS.ship(), cam, {yaw: st.p * .35}, c, 1 - gone * .75, pal.bg, {engine: [c, .7]});
    }
    const bracket = clear ? .7 * (1 - gone) : .5 + .4 * locked;
    s.brackets(x, y, spread, s.H * .42, clear ? c : pal.accent, bracket, 5, 1.3);
    if (!clear) {
      const track = st.p * TAU * .4;
      s.arc(x, y, spread * .8, s.H * .38, track, track + .6, pal.accent, .6, 1.2);
    } else {
      s.line(x - 12, y + 9, x + 12, y - 9, c, .55 * (1 - gone * .5), 1.3);
    }
  }

  // ---------------------------------------------------------------------
  // Planets: approach, descent, the surface.
  // ---------------------------------------------------------------------

  // Orbital approach or departure: the world beneath, more of its curve
  // showing the higher the journal says the ship is, and the ship on its
  // glide path down to it or away.
  function orbital(s, st, pal) {
    const depart = st.key === 'orbital_departure', alt = st.d.altitude;
    const height = alt < 0 ? .55 : clamp(Math.log10(1 + alt) / 6.3);
    sky(s, st, .7, .3);
    const R = lerp(s.W * .95, s.W * .3, height), cx = s.W * .62, top = lerp(s.H * .46, s.H * .62, height);
    s.sphere(cx, top + R, R, st.c, pal.bg, {spin: st.p * .006 * (depart ? -1 : 1), tilt: .1, seed: 6,
      atmosphere: pal.accent, detail: 3, sheen: [-.25, -.88], grid: true});
    const path = depart
      ? [[s.W * .44, top - 3], [s.W * .6, top - 8], [s.W * .78, top * .5], [s.W * .96, 3]]
      : [[s.W * .96, 3], [s.W * .82, top * .45], [s.W * .66, top - 7], [s.W * .48, top - 3]];
    for (let index = 0; index < 3; index += 1) s.line(...path[index], ...path[index + 1], pal.accent, .4, .9);
    const t = fract(st.p * .12), leg = Math.min(2, Math.floor(t * 3)), f = t * 3 - leg;
    const x = lerp(path[leg][0], path[leg + 1][0], f), y = lerp(path[leg][1], path[leg + 1][1], f);
    const heading = Math.atan2(path[leg + 1][1] - path[leg][1], path[leg + 1][0] - path[leg][0]);
    const cam = camera(x, y, 4.2, {pitch: -.35});
    s.solid(MODELS.ship(), cam, {roll: heading, yaw: -.25}, st.c, ends(t, .08), pal.bg, {engine: [st.c, .8]});
  }

  // Glide: through the atmosphere, nose down over the terrain far below,
  // the air round the hull glowing with the heat of entry.
  function glide(s, st, pal) {
    const cam = camera(s.W * .5, s.H * .1, 6, {pitch: -.34, persp: 16});
    landscape(s, cam, st, pal, {z0: -26, z1: 4, rows: 7, lift: .9, floor: 6, travel: [0, st.p * 3],
      alpha: .8, seed: 2});
    for (let index = 0; index < 5; index += 1) {
      const t = fract(st.p * .12 + hash(index + 90));
      s.bloom(s.W * (1.1 - t * 1.2), s.H * (.2 + hash(index + 91) * .35), s.H * .5, pal.text, .08 * ends(t, .2));
    }
    const x = s.W * .6, y = s.H * .42;
    const shipCam = camera(x, y, 5.6, {yaw: -.5, pitch: -.1, persp: 14});
    const at = s.solid(MODELS.ship(), shipCam, {roll: .35}, st.c, 1, pal.bg, {engine: [st.c, .7]});
    const [nx, ny] = at([2.1, 0, 0]);
    s.bloom(nx, ny, 10 + wave(st.p * 2) * 3, pal.orange, .45);
    for (let index = 0; index < 8; index += 1) {
      const t = fract(st.p * .9 + index / 8), spread = (hash(index + 95) - .5) * 10;
      s.line(nx - t * 30, ny - t * 12 + spread * t, nx - t * 30 - 6, ny - t * 12 + spread * t - 2, pal.orange,
        (1 - t) * .6, 1);
    }
    gravityLoad(s, st, x);
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

  // Surface approach, hold and departure: low over the ground, the ship
  // descending toward it, hovering over its landing spot or climbing away.
  // The ground's pace follows the reported vertical speed only.
  function surface(s, st, pal) {
    const key = st.key, depart = key === 'surface_departure', hold = key === 'surface_hold';
    const pace = clamp(.6 + Math.abs(st.d.vertical) / 90, .4, 2.4);
    const climb = depart ? smooth(fract(st.p * .1)) : 0;
    const cam = camera(s.W * .5, s.H * (.1 - climb * .2), 6.5, {pitch: -.22, persp: 14});
    landscape(s, cam, st, pal, {z0: -22, z1: 5, rows: 7, lift: 1, floor: 5 + climb * 3,
      travel: [0, hold ? 0 : st.terrain * 1.2 * pace], flat: {x: 0, z: -1, radius: 2.5}, seed: 4});
    const x = s.W * .5, y = s.H * (hold ? .44 : depart ? .5 - climb * .25 : .38 + .08 * wave(st.p * .2));
    if (hold) {
      const [gx, gy] = cam.project([0, 5, -1]);
      for (let index = 0; index < 2; index += 1) {
        const t = fract(st.p * .3 + index / 2);
        s.arc(gx, gy, 6 + t * 16, 1.6 + t * 4, 0, TAU, pal.accent, (1 - t) * .7, 1.1);
      }
      s.arc(gx, gy, 9, 2.4, 0, TAU, pal.accent, .7, 1.2);
      s.line(x, y + 5, gx, gy - 2, pal.accent, .3, .8);
    }
    const shipCam = camera(x, y, 6, {yaw: -.6, pitch: -.35, persp: 14});
    const at = s.solid(MODELS.ship(), shipCam, {roll: depart ? -.2 : 0, yaw: Math.sin(st.p * .2) * .06}, st.c, 1,
      pal.bg, {engine: [st.c, .8]});
    const [bx, by] = at([-.3, .5, 0]);
    s.bloom(bx, by + 2, 7 + wave(st.p * 1.5) * 2, pal.accent, depart ? .55 : .4);
    gravityLoad(s, st, x);
  }

  // Landed: the ship down on its gear on a quiet surface, a moon hanging
  // over the horizon. The ground holds still; only the lights breathe.
  function landed(s, st, pal) {
    sky(s, st, .6, .2);
    s.sphere(s.W * .2, s.H * .26, s.H * .16, st.c, pal.bg, {seed: 13, kind: 'ice', spin: st.p * .02});
    const cam = camera(s.W * .55, s.H * .26, 6.5, {pitch: -.16, persp: 14});
    landscape(s, cam, st, pal, {z0: -22, z1: 5, rows: 7, lift: .9, floor: 4.2, flat: {x: .5, z: 0, radius: 3.5},
      seed: 8});
    const [gx, gy] = cam.project([.5, 4.2, 0]);
    const shipCam = camera(gx, gy - 7, 6.2, {yaw: -.55, pitch: -.3, persp: 14});
    s.arc(gx, gy - 1, 18, 3.4, 0, TAU, pal.bg, .8, 3);
    const at = s.solid(MODELS.ship(), shipCam, {}, st.c, 1, pal.bg, {engine: [st.c, .2]});
    for (const point of [[-.6, .3, -.9], [-.6, .3, .9], [1.2, .2, 0]]) {
      const [fx, fy] = at(point), [lx, ly] = at([point[0], .85, point[2]]);
      s.line(fx, fy, lx, ly, st.c, .75, 1.1);
    }
    for (let index = 0; index < 2; index += 1) {
      const [lx, ly] = at([-.9, 0, index ? 1.5 : -1.5]);
      s.spark(lx, ly, .6, index ? pal.green : pal.red, null, .3 + .7 * Math.pow(wave(st.p * .5 + index * .5), 4));
    }
  }

  // Planetary ports and settlements share a flat site on the ground.
  function site(s, st, pal, draw) {
    sky(s, st, .6, .2);
    const cam = camera(s.W * .55, s.H * .2, 6, {yaw: .2, pitch: -.22, persp: 14});
    landscape(s, cam, st, pal, {z0: -24, z1: 5, rows: 7, lift: 1, floor: 5, flat: {x: 0, z: -3, radius: 7},
      seed: 12, alpha: .9});
    draw(cam);
  }

  function port(s, st, pal) {
    if (st.key === 'surface_station') {
      site(s, st, pal, (cam) => {
        const [x, y] = cam.project([0, 5, -3]);
        const portCam = camera(x, y, 4.2, {yaw: .3 + st.p * .01, pitch: -.42, persp: 14});
        const at = s.solid(MODELS.surfacePort(), portCam, {}, st.c, 1, pal.bg,
          {window: [st.c, .6], beacon: [pal.red, .3 + .7 * Math.pow(wave(st.p * .5), 6)]});
        // Traffic settles onto the ring's pads.
        const t = fract(st.p * .1);
        const [px, py] = at([3.2, -.6, 0]);
        const sx = lerp(s.W * .95, px, smooth(t)), sy = lerp(-4, py - 3, smooth(t));
        s.solid(MODELS.ship(), camera(sx, sy, 2.6, {yaw: .5, pitch: -.3}), {yaw: Math.PI}, st.c, ends(t, .1), pal.bg,
          {engine: [st.c, .8]});
        s.bloom(sx, sy + 2, 5, pal.accent, ends(t, .1) * .4);
      });
      return;
    }
    // A settlement: habitats, domes, hangars and a mast, lights in windows.
    site(s, st, pal, (cam) => {
      const layout = [['block', -6, -3, 0], ['dome', -3.4, -1.2, 1], ['tower', -1, -4.5, 0], ['hangar', 1.6, -1, 0],
        ['block', 4, -3.2, 1], ['dome', 6.2, -.5, 0], ['block', 1.2, -6, 1]];
      layout.sort((left, right) => left[2] - right[2]);
      for (const [kind, x, z, seed] of layout) {
        const [bx, by] = cam.project([x, 5, z]);
        const buildingCam = camera(bx, by, 4.4 * cam.scaleAt(cam.look([x, 5, z])[2]), {yaw: .2, pitch: -.3});
        s.solid(MODELS.building(kind, seed), buildingCam, {yaw: kind === 'hangar' ? .6 : 0}, st.c, 1, pal.bg, {
          window: [st.c, .35 + .45 * Math.pow(wave(st.p * .3 + x * .2), 3)],
          beacon: [pal.red, .3 + .7 * Math.pow(wave(st.p * .6), 6)],
        });
      }
    });
  }

  // ---------------------------------------------------------------------
  // On the ground: surface vehicles and the commander on foot.
  // ---------------------------------------------------------------------

  function groundVehicleType(st) {
    for (const type of ['rhino', 'scorpion', 'nomad', 'scarab']) {
      if (st.key === type || st.key.endsWith(`_${type}`)) return type;
    }
    return ['rhino', 'scorpion', 'nomad', 'scarab'].includes(st.vehicleKey)
      ? st.vehicleKey : 'scarab';
  }

  // A vehicle on the ground at a deck point: the model, its wheels'
  // spokes turning with `roll` distance, and a hover glow for the Nomad.
  function groundVehicle(s, st, pal, x, y, unit, {type = groundVehicleType(st), roll = 0, yaw = -.62,
    bob = 0, lamps = {}} = {}) {
    const model = MODELS.vehicle(type), cam = camera(x, y, unit, {yaw, pitch: -.28, persp: 12});
    const place = {y: bob, pitch: 0};
    const at = s.solid(model, cam, place, st.c, 1, pal.bg, {window: [pal.accent, .75], hover: [pal.accent, .85],
      headlamp: [pal.text, .7], ...lamps});
    for (const wheel of model.wheels || []) {
      if (cam.look(wheel.at)[2] < 0) continue;
      const hub = [wheel.at[0], wheel.at[1] + bob, wheel.at[2] + Math.sign(wheel.at[2]) * .14];
      for (let spoke = 0; spoke < 3; spoke += 1) {
        const angle = roll / wheel.r + spoke * TAU / 3;
        const [ax, ay] = at([hub[0] + Math.cos(angle) * wheel.r * .75, hub[1] + Math.sin(angle) * wheel.r * .75, hub[2]]);
        const [bx, by] = at([hub[0] - Math.cos(angle) * wheel.r * .75, hub[1] - Math.sin(angle) * wheel.r * .75, hub[2]]);
        s.line(ax, ay, bx, by, st.c, .45, .7);
      }
    }
    if (type === 'nomad') {
      const [gx, gy] = at([0, .1, 0]);
      s.arc(gx, gy + 3, 18, 3, 0, TAU, pal.accent, .3 + .2 * wave(st.p * .6), 1);
      s.bloom(gx, gy + 2, 12, pal.accent, .25);
    }
    return at;
  }

  // The rover scenes: the vehicle three-quarters on, crossing ground that
  // streams past, dust thrown from its wheels. Handbrake stills it all;
  // turret view swings the gun; drive assist lays guide rails.
  function rover(s, st, pal) {
    const key = st.key, type = groundVehicleType(st), brake = key === 'srv_handbrake';
    const pace = {rhino: 2.4, scorpion: 3.4, nomad: 4.2, scarab: 3}[type] || 3;
    const travel = brake || key === 'srv_turret' ? 0 : st.p * pace;
    sky(s, st, .6, .2);
    const cam = camera(s.W * .5, s.H * .22, 6.2, {yaw: -.12, pitch: -.14, persp: 14});
    landscape(s, cam, st, pal, {z0: -22, z1: 5, rows: 7, lift: .9, floor: 5,
      travel: [travel, 0], road: {z: 0, width: 2.5}, seed: {rhino: 3, scorpion: 5, nomad: 7}[type] || 1, alpha: .9});
    const x = s.W * .5, y = s.H * .8;
    const bob = brake ? 0 : Math.sin(st.p * 2.2) * (type === 'rhino' ? .02 : .05);
    if (!brake && type !== 'nomad' && key !== 'srv_turret') {
      for (let index = 0; index < 6; index += 1) {
        const t = fract(st.p * .9 + index / 6);
        s.bloom(x - 12 - t * 34, y - 2 - t * 6, 3 + t * 6, st.c, (1 - t) * .22);
      }
    }
    if (key === 'srv_drive_assist') {
      for (const side of [-1, 1]) {
        s.poly([[x - s.W * .5, y + side * 5 + 2], [x - 10, y + side * 3 + 1], [x + s.W * .5, y + side * 3]],
          pal.accent, .45, 1.1);
      }
    }
    const at = groundVehicle(s, st, pal, x, y, 8.2, {type, roll: travel * 1.6, bob,
      lamps: brake ? {headlamp: [pal.red, .9]} : {}});
    if (key === 'srv_turret') {
      // The turret sweeps a stabilised arc; the reticle is not a target.
      const aim = Math.sin(st.p * .4) * .5;
      const [tx, ty] = at([0, -1, 0]), rx = tx + Math.cos(aim) * s.W * .3, ry = ty - 6 + Math.sin(aim) * 8;
      s.line(tx, ty, rx, ry, pal.accent, .6, 1.1);
      s.brackets(rx, ry, 6, 4, pal.accent, .8, 2.5, 1.1);
    }
    if (brake) {
      const latch = .3 + .6 * wave(st.p * .6);
      for (const side of [-1, 1]) s.brackets(x, y - 6, 24, 11, st.c, latch * (side > 0 ? 1 : 1), 4, 1.3);
    }
  }

  // Skimmer drones hunting the SRV across the ground.
  function srvThreat(s, st, pal) {
    sky(s, st, .5, .2);
    const cam = camera(s.W * .5, s.H * .22, 6.2, {yaw: -.12, pitch: -.14, persp: 14});
    landscape(s, cam, st, pal, {z0: -22, z1: 5, rows: 7, lift: .9, floor: 5,
      travel: [st.p * 2, 0], road: {z: 0, width: 2.5}, seed: 1, alpha: .9});
    const x = s.W * .3, y = s.H * .8;
    groundVehicle(s, st, pal, x, y, 7.5, {roll: st.p * 3});
    for (let index = 0; index < 3; index += 1) {
      const dx = s.W * (.62 + index * .13) + Math.sin(st.p * .6 + index * 2) * 8;
      const dy = s.H * (.42 + index * .08) + Math.sin(st.p * 1.1 + index) * 3;
      const drone = camera(dx, dy, 5, {pitch: -.4});
      s.solid(MODELS.skimmer(), drone, {yaw: st.p * .3 + index}, st.c, 1, pal.bg, {eye: [pal.red, .9]});
      if (fract(st.p * .5 + index / 3) < .12) s.line(dx - 3, dy, x + 6, y - 8, pal.red, .8, 1.1);
    }
  }

  // On foot: the commander walking the surface, helmet lamp lit.
  function onFoot(s, st, pal) {
    sky(s, st, .6, .2);
    const cam = camera(s.W * .5, s.H * .22, 6.2, {yaw: -.12, pitch: -.14, persp: 14});
    landscape(s, cam, st, pal, {z0: -22, z1: 5, rows: 7, lift: 1, floor: 5,
      travel: [st.p * 1.1, 0], road: {z: 0, width: 2.5}, seed: 6, alpha: .9});
    const x = s.W * .55, y = s.H * .93;
    const person = camera(x, y, 14, {yaw: -.55, pitch: -.12, persp: 12});
    const at = s.solid(MODELS.commander(st.p * 3.2), person, {}, st.c, 1, pal.bg,
      {visor: [pal.accent, .85], lamp: [pal.text, .9]});
    const [hx, hy] = at([.2, -1.76, 0]);
    s.poly([[hx, hy], [hx + 44, hy - 4], [hx + 44, hy + 12]], pal.text, .06, 0, true, .5);
  }

  // A craft changing hands: deploying or recovering a vehicle or fighter,
  // dismissing or recalling the ship, or passing control along a link.
  // Transfers run once and wait for the journal; they do not loop.
  function handoff(s, st, pal) {
    const key = st.key, cy = s.H / 2;
    const deploy = key.includes('deploy'), board = key.includes('board');
    const t = smooth(st.age / 2.4), progress = board ? 1 - t : t;
    if (key.endsWith('crew') || key.includes('switch')) {
      sky(s, st, .6, .3);
      const left = s.W * .3, right = s.W * .74;
      const ship = camera(left, cy, 6, {yaw: -.4, pitch: -.3, persp: 14});
      s.solid(MODELS.ship(), ship, {}, st.c, 1, pal.bg, {engine: [st.c, .6]});
      if (key.endsWith('crew')) {
        const person = camera(right, s.H * .92, 13, {yaw: -.6, pitch: -.1});
        s.solid(MODELS.commander(0, {walking: false}), person, {}, st.c, 1, pal.bg, {visor: [pal.accent, .8], lamp: false});
      } else if (key.endsWith('fighter')) {
        s.solid(MODELS.ship('fighter'), camera(right, cy, 6, {yaw: -.5, pitch: -.3}), {}, st.c, 1, pal.bg,
          {engine: [pal.accent, .8], window: [pal.accent, .6]});
      } else {
        groundVehicle(s, st, pal, right, s.H * .8, 7.5);
      }
      const link = (u) => cy + Math.sin(u * TAU * 3 - st.p * 2) * 3 * Math.sin(u * Math.PI);
      const points = [];
      for (let step = 0; step <= 30; step += 1) points.push([lerp(left + 16, right - 16, step / 30), link(step / 30)]);
      s.poly(points, pal.accent, .55, 1.1);
      const u = fract(st.p * .5);
      s.spark(lerp(left + 16, right - 16, u), link(u), 1.1, pal.accent, pal.text, Math.sin(u * Math.PI));
      return;
    }
    if (key.endsWith('fighter')) {
      // The fighter drops from the mothership's bay and away, or returns.
      sky(s, st, .7, .5);
      const mother = camera(s.W * .3, s.H * .38, 6.4, {yaw: -.45, pitch: -.3, persp: 14});
      const at = s.solid(MODELS.ship(), mother, {}, st.c, 1, pal.bg, {engine: [st.c, .6]});
      const [bx, by] = at([-.2, .45, 0]);
      const fx = lerp(bx, s.W * .85, progress), fy = lerp(by + 2, s.H * .6, Math.sqrt(progress));
      s.solid(MODELS.ship('fighter'), camera(fx, fy, 4.4, {yaw: -.5, pitch: -.3}), {}, st.c, .4 + .6 * clamp(progress * 4),
        pal.bg, {engine: [pal.accent, .9], window: [pal.accent, .6]});
      trail(s, [fx - 8, fy], [lerp(bx, fx, .4), lerp(by, fy, .4)], pal.accent, .5 * clamp(progress * 3), 6);
      return;
    }
    // Surface handoffs: the ship hangs over the ground and the SRV rides a
    // light column down (or up); a dismissed ship lifts off and leaves.
    sky(s, st, .6, .2);
    const cam = camera(s.W * .55, s.H * .24, 6, {pitch: -.16, persp: 14});
    landscape(s, cam, st, pal, {z0: -22, z1: 5, rows: 7, lift: .9, floor: 5, flat: {x: 0, z: 0, radius: 4},
      seed: 10, alpha: .85});
    const [gx, gy] = cam.project([0, 5, 0]);
    if (key.endsWith('ship')) {
      const rise = deploy ? progress : 1 - progress;
      const sx = gx + rise * s.W * .35, sy = gy - 6 - rise * s.H * .7;
      s.bloom(sx, sy + 4, 8, pal.accent, .5);
      s.solid(MODELS.ship(), camera(sx, sy, 6 - rise * 2, {yaw: -.55, pitch: -.3, persp: 14}), {roll: -rise * .4},
        st.c, 1 - rise * .5, pal.bg, {engine: [pal.accent, .9]});
      return;
    }
    const shipY = s.H * .2;
    s.solid(MODELS.ship(), camera(gx, shipY, 6.4, {yaw: -.55, pitch: -.35, persp: 14}), {}, st.c, 1, pal.bg,
      {engine: [st.c, .6]});
    s.poly([[gx - 5, shipY + 5], [gx + 5, shipY + 5], [gx + 11, gy], [gx - 11, gy]], pal.accent, .2, 0, true, .35);
    const vy = lerp(shipY + 8, gy - 1, progress);
    groundVehicle(s, st, pal, gx, vy, 5.5 + progress * 1.5, {roll: 0});
  }

  // ---------------------------------------------------------------------
  // Stations and docking.
  // ---------------------------------------------------------------------

  // The mail slot's traffic lights: green once cleared, amber while a
  // request waits or after a cancel, red when refused.
  function slotLamp(st, pal) {
    const key = st.key, p = st.p;
    if (key === 'docking_denied') return [pal.red, .4 + .55 * wave(p * .9)];
    if (key === 'docking_timeout') return [wave(p * .45) > .5 ? pal.red : pal.yellow, .85];
    if (key === 'docking_cancelled') return [pal.yellow, .45 + .35 * wave(p * .5)];
    if (key === 'docking_clearance') {
      return st.label.includes('CLEARED') ? [pal.green, .95] : [pal.yellow, .35 + .55 * wave(p * .8)];
    }
    return [pal.green, .6 + .3 * wave(p * .4)];
  }

  // The Coriolis, turning about its slot with the slot facing the lane.
  function coriolisAt(s, st, pal, x, y, unit) {
    const cam = camera(x, y, unit, {yaw: -.72, pitch: -.28, persp: 18});
    const roll = st.p * .16;
    const at = s.solid(MODELS.coriolis(), cam, {roll}, st.c, 1, pal.bg,
      {slot: slotLamp(st, pal), window: [st.c, .45]});
    return {cam, at};
  }

  // A craft on the slot's approach axis, `u` out from the slot (0 at the
  // slot), facing in or out.
  function onApproach(s, st, pal, station, u, {inbound = true, scale = .16, color = st.c, alpha = 1, offset = 0,
    model = MODELS.ship(), turnAway = 0} = {}) {
    const place = {x: offset, y: offset * .3, z: 1.1 + u * 4.2, yaw: inbound ? Math.PI / 2 : -Math.PI / 2,
      scale};
    place.yaw += turnAway;
    s.solid(model, station.cam, place, color, alpha, pal.bg, {engine: [inbound ? color : pal.accent, .8]});
    return station.cam.project([place.x, place.y, place.z]);
  }

  function station(s, st, pal) {
    const key = st.key, x = s.W * .8, y = s.H * .5;
    if (key === 'station') {
      stationInterior(s, st, pal);
      return;
    }
    sky(s, st, .7, .3);
    // The approach lane from the far left toward the slot: traffic that
    // is not the commander's comes and goes along it.
    const lane = key === 'station_vicinity' || key === 'docking_clearance' || key === 'docking_assist';
    if (lane) {
      for (let index = 0; index < 4; index += 1) {
        const t = fract(st.p * .07 + index / 4), lx = lerp(-6, s.W * .5, t), ly = lerp(s.H * .3, s.H * .46, t);
        s.solid(MODELS.ship(), camera(lx, ly, 1.7 + t * 1.2, {yaw: -.2, pitch: -.3}), {}, st.c,
          ends(t, .15) * .8, pal.bg, {engine: [st.c, .9]});
        trail(s, [lx - 4, ly - .3], [lx - 16, ly - 2], st.c, ends(t, .15) * .5, 5);
      }
    }
    const station = coriolisAt(s, st, pal, x, y, 10.8);
    if (key === 'station_vicinity') {
      const t = fract(st.p * .11);
      onApproach(s, st, pal, station, 1 - t, {alpha: ends(t, .12)});
      const out = fract(st.p * .11 + .5);
      onApproach(s, st, pal, station, out, {inbound: false, alpha: ends(out, .12), offset: .35});
      return;
    }
    if (key === 'docking_clearance' || key === 'docking_assist') {
      // The commander's own ship lines up on the slot. Assist lays the
      // docking computer's guide rails in.
      const t = fract(st.p * .08), u = lerp(1, .15, smooth(t));
      if (key === 'docking_assist') {
        const [ax, ay] = station.cam.project([0, 0, 1.1]), [bx, by] = station.cam.project([0, 0, 5.3]);
        for (const side of [-1, 1]) s.line(ax, ay + side * 2, bx, by + side * 8, pal.accent, .55, 1);
      }
      const [sx, sy] = onApproach(s, st, pal, station, u, {scale: .26, alpha: ends(t, .1)});
      s.brackets(sx, sy, 9, 6, pal.accent, .7 * ends(t, .1), 3, 1.1);
      return;
    }
    // Refused, cancelled or timed out: the ship turns away from the slot.
    const turn = smooth(clamp(st.age / 2)) * (key === 'docking_cancelled' ? Math.PI : 1.2);
    const u = .8 + (key === 'docking_timeout' ? Math.sin(st.p * .2) * .05 : 0);
    onApproach(s, st, pal, station, u, {scale: .26, turnAway: -turn, offset: key === 'docking_timeout' ? .5 : 0});
  }

  // Inside the station: down the length of the turning cylinder, city
  // blocks standing in from its walls and the docking wall far ahead.
  // Behind the pilot, on the left, the mail slot's frame holds still.
  function stationInterior(s, st, pal) {
    const c = st.c, cx = s.W * .68, cy = s.H * .5, roll = st.p * .08;
    const lx = s.W * .12;
    s.rect(lx - 18, cy - 5, 36, 10, c, .45);
    s.rect(lx - 14, cy - 2, 28, 4, pal.green, .5, true);
    for (const side of [-1, 1]) s.line(lx - 24, cy + side * 9, lx + 24, cy + side * 9, c, .3, 1);
    const cam = camera(cx, cy, 11, {persp: 4});
    // The cylinder's wall: rings receding and streets running its length.
    for (const z of [.6, -1.5, -3.8, -6.5, -11]) {
      const [, , , k] = cam.project([0, 0, z]);
      s.arc(cx, cy, 3 * k * 11, 3 * k * 11, 0, TAU, c, .12 + .12 * k, .8);
    }
    for (let street = 0; street < 12; street += 1) {
      const angle = street * TAU / 12 + roll;
      const [ax, ay] = cam.project([Math.cos(angle) * 3, Math.sin(angle) * 3, .6]);
      const [bx, by] = cam.project([Math.cos(angle) * 3, Math.sin(angle) * 3, -11]);
      s.line(ax, ay, bx, by, c, .14, .7);
    }
    // The docking wall: a lit disc of pads at the far end.
    const [, , , far] = cam.project([0, 0, -11]);
    s.bloom(cx, cy, 3 * far * 11 * 1.4, c, .35);
    for (let pad = 0; pad < 8; pad += 1) {
      const angle = pad * TAU / 8 + roll;
      s.dot(cx + Math.cos(angle) * 3 * far * 11 * .62, cy + Math.sin(angle) * 3 * far * 11 * .62, .8, pal.text,
        .5 + .4 * wave(st.p * .4 + pad / 8));
    }
    s.solid(MODELS.stationCity(), cam, {roll}, c, 1, pal.bg, {window: [c, .7]});
  }

  // Docked: the ship on its pad in the hangar, the lift lights chasing
  // round the walls. The pad and the ship hold still.
  function docked(s, st, pal) {
    const c = st.c, x = s.W * .6, y = s.H * .66;
    const cam = camera(x, y, 8.5, {yaw: -.35, pitch: -.52, persp: 14});
    for (let index = 0; index < 14; index += 1) {
      const angle = Math.PI * (.95 + index / 13 * 1.1);
      const [ax, ay] = cam.project([Math.cos(angle) * 3.3, -2.2, Math.sin(angle) * 2.6]);
      const [bx, by] = cam.project([Math.cos(angle) * 3.3, .15, Math.sin(angle) * 2.6]);
      s.line(ax, ay, bx, by, c, .1 + .45 * Math.pow(wave(st.p * .3 - index / 14), 4), 1);
    }
    s.solid(MODELS.hexPad(), cam, {scale: 2.3}, c, 1, pal.bg);
    const pad = [];
    for (let index = 0; index < 6; index += 1) {
      const angle = index * TAU / 6;
      pad.push(cam.project([Math.cos(angle) * 2.36, -.01, Math.sin(angle) * 2.36 * .86]).slice(0, 2));
    }
    s.traceEdges(pad, st.p * .4, pal.accent, .7);
    s.solid(MODELS.ship(), cam, {y: -.4, scale: .9, yaw: .25}, c, 1, pal.bg, {engine: [c, .15]});
  }

  // Module repairs: a sweep passes along the ship and the repair points
  // spark as it reaches them. Not a progress readout.
  function maintenance(s, st, pal) {
    const reboot = st.key === 'system_reboot', x = s.W * .58, y = s.H * .5;
    sky(s, st, .4, .2);
    const cam = camera(x, y, 9, {yaw: -.4, pitch: -.3, persp: 14});
    const sweep = fract(st.p * .16);
    s.solid(MODELS.ship(), cam, {}, st.c, reboot ? .35 + .65 * sweep : 1, pal.bg,
      {engine: reboot ? [st.c, sweep > .8 ? .8 : .05] : [st.c, .5]});
    const [ax, ay] = cam.project([lerp(-1.2, 2.2, sweep), -1, 0]), [bx, by] = cam.project([lerp(-1.2, 2.2, sweep), 1, 0]);
    s.line(ax, ay - 6, bx, by + 6, reboot ? st.c : pal.accent, .7, 1.2);
    s.bloom((ax + bx) / 2, (ay + by) / 2, 10, reboot ? st.c : pal.accent, .3);
    if (!reboot) {
      for (let index = 0; index < 5; index += 1) {
        const px = lerp(-1, 1.8, index / 4), [sx, sy] = cam.project([px, -.25, (hash(index) - .5) * 1.4]);
        const near = clamp(1 - Math.abs(px - lerp(-1.2, 2.2, sweep)) * 2.5);
        if (near > .05) {
          for (let spark = 0; spark < 3; spark += 1) {
            const angle = hash(index * 3 + spark + Math.floor(st.p * 8)) * TAU;
            s.line(sx, sy, sx + Math.cos(angle) * 4, sy + Math.sin(angle) * 4, pal.yellow, near * .8, .8);
          }
        }
      }
    } else {
      alarmChevrons(s, st, .43 + .43 * wave(st.p * .5));
    }
  }

  // ---------------------------------------------------------------------
  // Restrictions, contacts and danger.
  // ---------------------------------------------------------------------

  // Mass lock: space sags round a nearby mass in a well, and the ship at
  // its rim is held by rings that will not let the drive engage.
  function massLock(s, st, pal) {
    const c = st.c, cam = camera(s.W * .55, s.H * .42, s.W * .06, {yaw: st.p * .02, pitch: -.62, persp: 12});
    const sag = (x, z) => 2.2 / (1 + (x * x + z * z) * .35);
    for (let index = -6; index <= 6; index += 1) {
      const across = [], along = [];
      for (let step = -6; step <= 6; step += .5) {
        across.push(cam.project([step, sag(step, index), index]));
        along.push(cam.project([index, sag(index, step), step]));
      }
      s.poly(across, c, .22, .8);
      s.poly(along, c, .22, .8);
    }
    const [mx, my] = cam.project([0, 1.2, 0]);
    s.sphere(mx, my, s.H * .24, c, pal.bg, {spin: st.p * .05, seed: 15, grid: true});
    const [sx, sy] = cam.project([4.6, sag(4.6, 1.4) - .6, 1.4]);
    s.solid(MODELS.ship(), camera(sx, sy, 3.8, {yaw: -.9, pitch: -.3, persp: 14}), {}, c, 1, pal.bg, {engine: [c, .5]});
    for (let index = 0; index < 3; index += 1) {
      const t = fract(st.p * .3 + index / 3), r = lerp(20, 7, t);
      s.arc(sx, sy, r, r * .45, 0, TAU, pal.yellow || c, Math.sin(t * Math.PI) * .6, 1.1);
    }
  }

  // A signal source: a beacon amid tumbling cargo and wreckage, pulsing.
  // Dropping in, the streaks die as the field comes up; a threat signal
  // pulses red and shows the journal's threat level.
  function signal(s, st, pal) {
    const c = st.c, key = st.key, x = s.W * .64, y = s.H * .5;
    const threatened = key === 'signal_threat', drop = key === 'signal_drop';
    const settle = drop ? smooth(st.age / 2) : 1;
    sky(s, st, .6, .3);
    if (drop) streaks(s, st, {x, count: 18, speed: .3 * (1 - settle), strength: (1 - settle) * .7});
    const pulse = threatened ? pal.red : pal.accent;
    for (let index = 0; index < 3; index += 1) {
      const t = fract(st.p * .25 + index / 3), r = 6 + t * s.W * .3;
      s.arc(x, y, r, r * .32, 0, TAU, pulse, (1 - t) * .45 * settle, 1.1);
    }
    for (let index = 0; index < 6; index += 1) {
      const angle = index * TAU / 6 + st.p * .03, reach = s.W * (.12 + hash(index + 60) * .16);
      const dx = x + Math.cos(angle) * reach, dy = y + Math.sin(angle) * reach * .22;
      if (index % 2) {
        rockAt(s, pal, dx, dy, 3.2 + hash(index) * 2, c, st.p, .9 * settle, index + 2);
      } else {
        s.solid(MODELS.canister(), camera(dx, dy, 3.2, {pitch: -.3}), {yaw: st.p * .3 + index,
          roll: st.p * .2 + index}, c, settle, pal.bg, {window: [pulse, .6]});
      }
    }
    s.solid(MODELS.beacon(), camera(x, y, 5.6, {pitch: -.3, persp: 12}), {yaw: st.p * .2}, c, settle, pal.bg,
      {beacon: [pulse, .5 + .5 * wave(st.p * .8)], window: [pulse, .6]});
    if (threatened) {
      const level = clamp(Number(st.label.match(/\d+$/)?.[0] || 0), 0, 8);
      for (let index = 0; index < level; index += 1) {
        const px = 10 + index * 7;
        s.poly([[px - 2.2, s.H - 5], [px, s.H - 11], [px + 2.2, s.H - 5]], pal.red,
          .45 + .4 * wave(st.p * .5 - index * .1), 1.2, true, .25);
      }
      const orbit = st.p * .25;
      const [ex, ey] = [x + Math.cos(orbit) * s.W * .3, y + Math.sin(orbit) * 7];
      s.solid(MODELS.ship('interdictor'), camera(ex, ey, 3.6, {pitch: -.3}), {yaw: -orbit - Math.PI / 2}, pal.red,
        .8, pal.bg, {engine: [pal.red, .8]});
    }
  }

  function contact(s, st, pal) {
    const c = st.c, x = s.W * .6, y = s.H * .55;
    if (st.key === 'unknown_contact') {
      // Something not human: a Thargoid interceptor, petals turning round
      // its heart, and the interference it throws across the scanner.
      for (let index = 0; index < 5; index += 1) {
        const yy = 4 + index * (s.H - 8) / 4 + Math.sin(st.p * .7 + index) * 2;
        s.line(0, yy, s.W, yy + Math.sin(st.p * .4 + index * 2) * 3, pal.green, .08 + .1 * wave(st.p * .35 + index * .3), .8);
      }
      const cam = camera(x, s.H * .5, 8.4, {yaw: Math.sin(st.p * .1) * .5, pitch: -.35 + Math.sin(st.p * .07) * .15,
        persp: 12});
      s.bloom(x, s.H * .5, 20, pal.green, .25 + .15 * wave(st.p * .4));
      s.solid(MODELS.thargoid(), cam, {roll: st.p * .15}, c, 1, pal.bg, {core: [pal.green, .6 + .35 * wave(st.p * .5)]});
      return;
    }
    // A capital ship: a warship's long blade drifting past, running lights
    // blinking along its flank.
    sky(s, st, .7, .3);
    const cam = camera(x, y, 6.2, {yaw: -.35 + Math.sin(st.p * .05) * .08, pitch: -.22, persp: 30});
    s.solid(MODELS.capital(), cam, {}, c, 1, pal.bg, {engine: [pal.accent, .7],
      window: [c, .3 + .5 * Math.pow(wave(st.p * .3), 3)]});
    s.brackets(x, y - 4, s.W * .36, s.H * .44, c, .45, 6, 1.1);
  }

  // Combat: ships turning about each other, lasers crossing, shields
  // flaring where they land. Heavy combat adds more ships and explosions.
  // Decorative: the journal reports no contacts to plot.
  function threat(s, st, pal) {
    const c = st.c, key = st.key;
    if (key === 'srv_threat') {
      srvThreat(s, st, pal);
      return;
    }
    const heavy = key === 'heavy_combat', x = s.W * .56, y = s.H * .5;
    sky(s, st, .6, .6);
    const ships = heavy ? 4 : 2, placed = [];
    for (let index = 0; index < ships; index += 1) {
      const orbit = st.p * (.45 + index * .08) + index * TAU / ships;
      const reach = s.W * (.12 + (index % 2) * .09);
      placed.push({
        x: x + Math.cos(orbit) * reach, y: y + Math.sin(orbit * 2) * 5 + (index - ships / 2) * 2,
        depth: Math.sin(orbit), yaw: -orbit - Math.PI / 2, enemy: index % 2 === 1,
      });
    }
    placed.sort((left, right) => left.depth - right.depth);
    for (const ship of placed) {
      s.solid(MODELS.ship(ship.enemy ? 'interdictor' : 'wedge'), camera(ship.x, ship.y, 5 + ship.depth * 1.2,
        {pitch: -.35, persp: 14}), {yaw: ship.yaw, roll: Math.sin(st.p + ship.depth) * .4},
      ship.enemy ? pal.red : c, .85 + ship.depth * .15, pal.bg, {engine: [ship.enemy ? pal.red : c, .8]});
    }
    for (let index = 0; index < placed.length; index += 1) {
      const from = placed[index], to = placed[(index + 1) % placed.length];
      if (fract(st.p * 1.3 + index * .37) > .45) continue;
      s.line(from.x, from.y, to.x, to.y, from.enemy ? pal.red : pal.accent, .75, 1.1);
      s.arc(to.x, to.y, 8, 6, 0, TAU, pal.accent, .5, 1);
    }
    if (heavy) {
      const t = fract(st.p * .35), ex = x + (hash(Math.floor(st.p * .35)) - .5) * s.W * .5;
      s.bloom(ex, y, 4 + t * 18, pal.yellow, (1 - t) * .6);
      for (let index = 0; index < 6; index += 1) {
        const angle = index * TAU / 6 + hash(index);
        s.dot(ex + Math.cos(angle) * t * 16, y + Math.sin(angle) * t * 8, .8, pal.yellow, (1 - t) * .8);
      }
    }
    alarmChevrons(s, st, .3 + .4 * wave(st.p * .5));
  }

  // Interdiction: the interdictor behind, its tether writhing to the ship,
  // the escape vector ahead. Interdicted, the tether has won: the ship
  // tumbles out of supercruise.
  function interdiction(s, st, pal) {
    const lost = st.key === 'interdicted', cy = s.H / 2;
    streaks(s, st, {x: s.W * .92, count: lost ? 8 : 20, speed: lost ? .1 : .34, strength: lost ? .25 : .5});
    const ex = s.W * .14, ey = cy - 3;
    s.solid(MODELS.ship('interdictor'), camera(ex, ey, 5.5, {yaw: -.35, pitch: -.3, persp: 14}), {}, pal.red, 1,
      pal.bg, {engine: [pal.red, .8]});
    const x = s.W * .56 + (lost ? 0 : Math.sin(st.p * .6) * 10), y = cy + (lost ? 0 : Math.sin(st.p * .9) * 4);
    const points = [];
    for (let step = 0; step <= 24; step += 1) {
      const u = step / 24;
      points.push([lerp(ex + 12, x - 8, u), lerp(ey, y, u) + Math.sin(u * 12 - st.p * 4) * 3 * Math.sin(u * Math.PI)]);
    }
    s.poly(points, pal.red, lost ? .35 : .7, 1.3);
    s.solid(MODELS.ship(), camera(x, y, 6, {yaw: -.4, pitch: -.3, persp: 14}),
      {roll: lost ? st.p * 1.2 : Math.sin(st.p * .9) * .4, yaw: lost ? st.p * .8 : 0}, st.c, 1, pal.bg,
      {engine: [st.c, .8]});
    if (lost) {
      for (let index = 0; index < 6; index += 1) {
        const angle = hash(index + Math.floor(st.p * 5)) * TAU;
        s.line(x, y, x + Math.cos(angle) * 9, y + Math.sin(angle) * 5, pal.yellow, .6, .8);
      }
    } else {
      const vx = s.W * .86 + Math.sin(st.p * .4) * 8;
      s.ring(vx, cy, 8, 8, 16, pal.accent, .75, 1.4);
      s.chevron(vx, cy, 1, pal.accent, .8, 3, 1.3);
    }
  }

  // Heat critical: the ship glowing red-hot, heat shimmering off it.
  function heat(s, st, pal) {
    const x = s.W * .58, y = s.H * .52, alarm = .43 + .43 * wave(st.p * .5);
    for (let index = 0; index < 11; index += 1) {
      const points = [], x0 = x + (index - 5) * 9;
      for (let step = 0; step <= 10; step += 1) {
        const u = step / 10;
        points.push([x0 + Math.sin(u * 6 + st.p * 2 + index) * 2.5, s.H - 2 - u * (s.H - 4)]);
      }
      s.poly(points, pal.red, .14 + .18 * wave(st.p * .6 + index * .2), 1);
    }
    s.bloom(x, y, 26, pal.red, .35 + .25 * alarm);
    s.solid(MODELS.ship(), camera(x, y, 8, {yaw: -.45, pitch: -.3, persp: 14}), {yaw: Math.sin(st.p * .2) * .05},
      pal.red, 1, pal.bg, {engine: [pal.yellow, .9]});
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

  // The commander's suit in trouble, by what Status reports: oxygen, health,
  // cold or heat.
  function suit(s, st, pal) {
    const c = st.c, x = s.W * .6, label = st.label, alarm = .43 + .43 * wave(st.p * .5);
    if (label.includes('HEAT') && !label.includes('HEALTH')) {
      heat(s, st, pal);
      return;
    }
    const person = camera(x, s.H * 1.3, 20, {yaw: -.7, pitch: -.05});
    s.solid(MODELS.commander(0, {walking: false}), person, {}, c, 1, pal.bg,
      {visor: [label.includes('OXYGEN') ? pal.red : pal.accent, .5 + .4 * alarm], lamp: false});
    if (label.includes('OXYGEN')) {
      for (let index = 0; index < 8; index += 1) {
        const t = fract(st.p * .25 + hash(index + 5)), bx = x + 10 + (hash(index + 6) - .5) * 20;
        s.arc(bx + Math.sin(t * 6 + index) * 2, s.H * (1 - t), 1.2 + hash(index) * 1.4, 1.2 + hash(index) * 1.4,
          0, TAU, pal.accent, ends(t) * .6, .8);
      }
    } else if (label.includes('HEALTH')) {
      const points = [];
      for (let step = 0; step <= 80; step += 1) {
        const px = step / 80 * s.W * .42, beat = fract(step / 80 * 2 - st.p * .5);
        points.push([6 + px, beat < .08 ? s.H * .62 - Math.sin(beat / .08 * Math.PI) * s.H * .38
          : beat < .12 ? s.H * .62 + 4 : s.H * .62]);
      }
      s.poly(points, pal.red, alarm, 1.3);
    } else {
      for (let index = 0; index < 12; index += 1) {
        const t = fract(hash(index + 5) + st.p * .05), fx = s.W * (1 - t), fy = 5 + hash(index + 9) * (s.H - 10);
        const size = 1.8 + hash(index) * 1.6;
        for (let arm = 0; arm < 3; arm += 1) {
          const angle = arm * Math.PI / 3;
          s.line(fx - Math.cos(angle) * size, fy - Math.sin(angle) * size, fx + Math.cos(angle) * size,
            fy + Math.sin(angle) * size, pal.accent, alarm * .7 * ends(t), .8);
        }
      }
    }
    alarmChevrons(s, st, alarm);
  }

  // Jet cone damage: inside a neutron star's jet, the ship buffeted. Both
  // jets fire along the star's axis; the ship rides the nearer one.
  function jetCone(s, st, pal) {
    const sx = s.W * .68, sy = s.H * .5, alarm = .43 + .43 * wave(st.p * .5);
    const axis = -.32, reach = s.W * .5;
    for (const side of [-1, 1]) {
      const tipX = sx + Math.cos(axis) * reach * side, tipY = sy + Math.sin(axis) * reach * side;
      const normalX = -Math.sin(axis), normalY = Math.cos(axis);
      for (const width of [9, 5]) {
        s.poly([[sx, sy], [tipX + normalX * width, tipY + normalY * width], [tipX - normalX * width, tipY - normalY * width]],
          pal.accent, width === 9 ? .25 : .45, .9, true, width === 9 ? .08 : .12);
      }
      for (let index = 0; index < 4; index += 1) {
        const t = fract(st.p * .9 + index / 4);
        s.spark(lerp(sx, tipX, t), lerp(sy, tipY, t), .9, pal.accent, pal.text, ends(t) * .8);
      }
    }
    s.sun(sx, sy, s.H * .11, pal.accent, pal.text, st.p * 3, {flares: false});
    const shake = Math.floor(st.p * 9);
    const x = s.W * .34 + (hash(shake) - .5) * 3, y = sy - Math.sin(axis) * s.W * .34 + (hash(shake + 1) - .5) * 3;
    s.solid(MODELS.ship(), camera(x, y, 6, {yaw: -.4, pitch: -.3, persp: 14}), {roll: Math.sin(st.p * 2) * .3},
      st.c, 1, pal.bg, {engine: [st.c, .8]});
    for (let index = 0; index < 5; index += 1) {
      const angle = hash(index + shake) * TAU;
      s.line(x, y, x + Math.cos(angle) * 8, y + Math.sin(angle) * 5, pal.yellow, alarm * .7, .8);
    }
    alarmChevrons(s, st, alarm);
  }

  // ---------------------------------------------------------------------
  // Cockpit panels: angled holographic boards, as the cockpit hangs them.
  // ---------------------------------------------------------------------

  // A board in perspective; `mark(u, v)` maps a point on it (0..1 across,
  // 0..1 down) to the deck.
  function board(s, st, pal, {x, y, w, h, yaw = 0, pitch = 0}) {
    const cam = camera(x, y, 1, {yaw, pitch, persp: 220});
    const mark = (u, v) => cam.project([(u - .5) * w, (v - .5) * h, 0]).slice(0, 2);
    s.poly([mark(0, 0), mark(1, 0), mark(1, 1), mark(0, 1)], st.c, .45, 1, true, .06);
    s.poly([mark(.02, .08), mark(.02, .92)], st.c, .5, 1.4);
    return mark;
  }

  function panel(s, st, pal) {
    const c = st.c, key = st.key, p = st.p;
    sky(s, st, .4, .2);
    if (key === 'left_panel' || key === 'right_panel') {
      const left = key === 'left_panel';
      const mark = board(s, st, pal, {x: s.W * (left ? .38 : .72), y: s.H * .5, w: s.W * .5, h: s.H * .8,
        yaw: left ? .75 : -.75});
      const focus = Math.floor(fract(p * .07) * 5);
      for (let row = 0; row < 5; row += 1) {
        const v = .16 + row * .17, lit = row === focus;
        if (left) {
          s.poly([mark(.08, v), mark(.72, v), mark(.72, v + .11), mark(.08, v + .11)], c, lit ? .85 : .25, 1, true,
            lit ? .22 : 0);
          s.dot(...mark(.82, v + .05), 1.1, row % 2 ? pal.accent : c, .7);
        } else {
          const fill = .3 + .6 * hash(row + 7);
          s.poly([mark(.1, v + .02), mark(.1 + fill * .8, v + .02)], lit ? pal.accent : c, .75, 2.4);
          s.poly([mark(.1, v + .09), mark(.9, v + .09)], c, .15, .6);
        }
      }
      return;
    }
    if (key === 'comms_panel') {
      const mark = board(s, st, pal, {x: s.W * .55, y: s.H * .5, w: s.W * .62, h: s.H * .8, yaw: .25});
      for (let row = 0; row < 4; row += 1) {
        const v = .18 + row * .19, length = .3 + hash(row + 20) * .45;
        s.poly([mark(.08, v), mark(.08 + length, v)], row === 3 ? pal.accent : c,
          row === 3 ? .4 + .5 * wave(p * .6) : .35, 1.4);
      }
      for (let index = 0; index < 18; index += 1) {
        const u = .5 + index * .025, amp = .05 + .25 * wave(p * .4 - index * .12);
        s.poly([mark(u, .8 - amp), mark(u, .8 + amp)], pal.accent, .6, 1);
      }
      return;
    }
    if (key === 'role_panel') {
      const mark = board(s, st, pal, {x: s.W * .56, y: s.H * .55, w: s.W * .6, h: s.H * .75, pitch: -.6});
      for (let seat = 0; seat < 3; seat += 1) {
        const u = .22 + seat * .28, active = seat === Math.floor(fract(p * .08) * 3);
        const [hx, hy] = mark(u, .4);
        s.solid(MODELS.commander(0, {walking: false}), camera(hx, hy + 12, 7, {yaw: -.3}), {}, active ? pal.accent : c,
          active ? 1 : .6, pal.bg, {visor: [pal.accent, .6], lamp: false});
      }
      return;
    }
    // Station services: the menu's tiles lighting in turn.
    const mark = board(s, st, pal, {x: s.W * .56, y: s.H * .5, w: s.W * .66, h: s.H * .82, yaw: .2});
    for (let tile = 0; tile < 8; tile += 1) {
      const u = .08 + (tile % 4) * .23, v = tile < 4 ? .14 : .56;
      const lit = .2 + .7 * Math.pow(wave(p * .2 - tile / 8), 4);
      s.poly([mark(u, v), mark(u + .19, v), mark(u + .19, v + .32), mark(u, v + .32)], c, .3 + lit * .5, 1, true, lit * .25);
    }
  }

  // One tumbling rock at a deck point, `size` pixels to a unit: the
  // signal source's debris and the rocks round the ship's portrait.
  function rockAt(s, pal, x, y, size, color, phase, alpha, seed) {
    s.solid(MODELS.rock(seed), camera(x, y, size), {
      yaw: phase * (seed % 2 ? -.31 : .24) + seed * 2.1, pitch: phase * .17 + seed * .83,
    }, color, alpha, pal.bg);
  }

  // The asteroid field: inside a planet's ring. Rocks tumble past at every
  // depth, the nearer larger and quicker, over the ring's plane running
  // away to its bright far edge, with grit drifting through. Now and then
  // a facet catches the light, and a miner in the middle distance works a
  // rock with its laser while a prospector limpet flies out to it.
  // Decorative: the journal reports no rock, ship or position here.
  const FIELD = Array.from({length: 26}, (_, index) => ({
    seed: index,
    start: hash(index + 150),
    y: (hash(index + 204) - .5) * 4.2,
    z: lerp(-16, 2.4, Math.pow(hash(index + 60), .75)),
    size: .5 + Math.pow(hash(index + 29), 2) * 1.15,
  }));

  function asteroids(s, st, pal) {
    const c = st.c, unit = 6.2, travel = st.p * .6;
    const cam = camera(s.W * .5, s.H * .52, unit, {pitch: -.03, persp: 16});
    // Where something at this depth is on its lap: it wraps just beyond
    // the deck's edges, so nothing pops in or out in view.
    const along = (start, y, z, size) => {
      const k = cam.scaleAt(cam.look([0, y, z])[2]);
      const half = (s.W / 2 + 6) / (unit * k) + size * 1.6;
      return -half + fract(start - travel / (2 * half)) * 2 * half;
    };
    // The ring's plane, nearly edge on: its far edge a bright line, nearer
    // bands fainter as they come toward the viewer.
    for (const [z, alpha] of [[-600, .22], [-40, .08], [-14, .05]]) {
      const [, y] = cam.project([0, 0, z]);
      s.line(0, y, s.W, y, c, alpha, z < -100 ? 1.1 : .8);
    }
    for (let index = 0; index < 40; index += 1) {
      const y = (hash(index + 400) - .5) * 5, z = lerp(-18, 3, hash(index + 401));
      const [gx, gy, , k] = cam.project([along(hash(index + 402), y, z, 0), y, z]);
      s.dot(gx, gy, .3 + k * .35, c, .18 + .3 * hash(index + 403));
    }
    const items = FIELD.map((rock) => ({z: rock.z, draw() {
      const x = along(rock.start, rock.y, rock.z, rock.size);
      const fog = .45 + .55 * smooth((rock.z + 16) / 12);
      const at = s.solid(MODELS.rock(rock.seed), cam, {x, y: rock.y, z: rock.z, scale: rock.size,
        yaw: st.p * (rock.seed % 2 ? -.31 : .24) + rock.seed * 2.1, pitch: st.p * .17 + rock.seed * .83},
      c, fog, pal.bg);
      // A facet catching the light as the rock turns.
      const glint = fract(st.p * .31 + hash(rock.seed + 7));
      if (glint < .05) {
        const [gx, gy, , k] = at([-.35, -.4, .5]);
        s.spark(gx, gy, .5 + k * .3, pal.text, null, Math.sin(glint / .05 * Math.PI) * fog);
      }
    }}));
    items.push({z: -5.6, draw: () => miner(s, st, pal, cam, along)});
    items.sort((left, right) => left.z - right.z);
    for (const item of items) item.draw();
  }

  // A miner working a rock: its laser pulses onto the face and chips fly
  // off, while a prospector limpet arcs across and latches onto the rock.
  function miner(s, st, pal, cam, along) {
    const z = -5.6, x = along(.35, -.2, z, 4);
    const rockPlace = {x: x + 1.4, y: .5, z: z + .2, scale: 1.55, yaw: st.p * .05 + 1, pitch: .6};
    const ship = s.solid(MODELS.ship(), cam, {x: x - 1.6, y: -1.2, z: z - .3, scale: .42, yaw: -.25, roll: .15},
      st.c, .9, pal.bg, {engine: [st.c, .6]});
    const face = s.solid(MODELS.rock(5), cam, rockPlace, st.c, .95, pal.bg);
    const pulse = fract(st.p * .5);
    const [nx, ny] = ship([2.1, 0, 0]), [hx, hy] = face([-.7, -.25, .2]);
    if (pulse < .62) {
      s.line(nx, ny, hx, hy, pal.orange, .75, 1.1);
      s.bloom(hx, hy, 4, pal.orange, .6);
      for (let chip = 0; chip < 3; chip += 1) {
        const t = fract(pulse * 2.4 + chip / 3), angle = -2.4 + hash(chip + 9) * 1.4;
        s.dot(hx + Math.cos(angle) * t * 9, hy + Math.sin(angle) * t * 6 + t * t * 3, .6, pal.yellow, (1 - t) * .8);
      }
    }
    // The limpet: out along an arc to the next rock, then held there.
    const trip = fract(st.p * .09), flight = smooth(clamp(trip / .7));
    const [lx0, ly0] = ship([-.4, .4, 0]), [lx1, ly1] = face([.9, -.6, -.2]);
    const lx = lerp(lx0, lx1, flight), ly = lerp(ly0, ly1, flight) - Math.sin(flight * Math.PI) * 6;
    s.solid(MODELS.limpet(), camera(lx, ly, 1.8, {pitch: -.3}), {yaw: st.p * .6}, st.c, ends(trip, .06), pal.bg,
      {eye: [trip > .7 ? pal.green : pal.accent, .5 + .5 * wave(st.p * 2)]});
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
    signal_threat: signal, capital_contact: contact, unknown_contact: contact,
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
      const hyper = st.key === 'hyper_charge', pace = hyper ? .72 : .52;
      const spool = .52 + .48 * smooth(st.age / 2.3);
      for (let index = 0; index < 4; index += 1) {
        const t = fract(st.p * pace + index / 4), travel = smooth(t);
        const rx = lerp(b.W * .59, b.W * .24, travel);
        const ry = lerp(b.H * .5, b.H * .22, travel);
        const light = ends(t, .15) * spool * (hyper ? .52 : .36);
        b.arc(cx, cy, rx, ry, Math.PI * .18, Math.PI * .82, st.c, light, 1.1);
        b.arc(cx, cy, rx, ry, Math.PI * 1.18, Math.PI * 1.82, st.c, light, 1.1);
      }
      if (hyper) {
        b.bloom(cx, cy, b.W * .36, pal.accent, .16 * spool);
        b.arc(cx, cy, b.W * .25, b.H * .28, 0, TAU, pal.accent, .27 * spool, 1.1);
      }
    },
    tunnel(b, st, pal, cx, cy) {
      if (st.key === 'carrier_transit') {
        // A slow, squared wake surrounds the carrier projection, separate
        // from the commander's concentric ship-jump tunnel.
        for (let index = 0; index < 4; index += 1) {
          const t = fract(st.p * .19 + index / 4);
          const rx = b.W * lerp(.2, .72, smooth(t));
          const ry = b.H * lerp(.19, .64, smooth(t));
          const light = Math.sin(t * Math.PI) * .42;
          for (const side of [-1, 1]) {
            b.poly([[cx + side * rx, cy - ry * .5],
              [cx + side * rx * .7, cy - ry], [cx - side * rx * .25, cy - ry]],
              st.c, light, 1.15);
            b.poly([[cx + side * rx, cy + ry * .5],
              [cx + side * rx * .7, cy + ry], [cx - side * rx * .25, cy + ry]],
              st.c, light * .72, 1.1);
          }
        }
        return;
      }
      for (let index = 0; index < 6; index += 1) {
        const t = fract(st.p * .32 + index / 6), k = t * t;
        b.ring(cx, cy, 4 + k * b.W * .7, 3 + k * b.H * .7, 10, st.c, Math.sin(t * Math.PI) * .45, 1, st.p * .1 + index);
      }
    },
    flare(b, st, pal, cx, cy) {
      if (st.key === 'carrier_arrival') {
        const settle = smooth(st.age / 2.8);
        const spread = lerp(b.W * .56, b.W * .43, settle);
        b.brackets(cx, cy, spread, b.H * .44, st.c, .32 + .19 * settle, 9, 1.3);
        for (const side of [-1, 1]) {
          b.line(cx + side * b.W * .34, cy - b.H * .27,
            cx + side * b.W * .34, cy + b.H * .27, st.c, .28, 1.2);
          b.dot(cx + side * b.W * .4, cy + b.H * .28, 1.3,
            st.c, .3 + .48 * wave(st.p * .22 + (side + 1) / 4));
        }
        return;
      }
      const star = st.starTone || st.c;
      if (st.starFamily === 'blackhole') {
        // A black hole sheds no light: its disc rings the ship instead.
        for (let band = 0; band < 3; band += 1) {
          const rx = b.W * (.4 + band * .06);
          b.arc(cx, cy + b.H * .08, rx, rx * .2, 0, TAU, band ? star : pal.text, .5 - band * .12, 1.3 - band * .2);
        }
        return;
      }
      if (st.starFamily === 'neutron') {
        // A neutron star's jets sweep past behind the ship.
        const axis = -1.15 + Math.sin(st.p * .6) * .35;
        for (const side of [-1, 1]) {
          b.line(cx + b.W * .12, cy, cx + b.W * .12 + Math.cos(axis) * side * b.W * .6,
            cy + Math.sin(axis) * side * b.W * .6, star, .45, 1.4);
        }
      }
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
      if (st.key.startsWith('carrier_')) {
        // Broad deck rails and paired mooring beacons read as a capital
        // ship, rather than the station's revolving letterbox.
        const close = st.key === 'carrier_lockdown' ? smooth(st.age / 2.5) : 0;
        const railY = b.H * .69;
        b.poly([[cx - b.W * .48, railY], [cx - b.W * .3, railY - 6],
          [cx + b.W * .3, railY - 6], [cx + b.W * .48, railY]], st.c, .42, 1.2);
        for (const side of [-1, 1]) {
          const x = cx + side * lerp(b.W * .49, b.W * .38, close);
          b.poly([[x, cy - b.H * .38], [x - side * b.W * .12, cy - b.H * .24],
            [x - side * b.W * .12, cy + b.H * .25], [x, cy + b.H * .38]],
            st.c, .38 + close * .2, 1.15);
          const pulse = st.key === 'carrier_lockdown' ? .66
            : .2 + .5 * wave(st.p * .2 + (side + 1) / 4);
          b.dot(x, railY, 1.4, st.c, pulse);
        }
        if (st.key === 'carrier_preparing') {
          for (let index = 0; index < 4; index += 1) {
            const x = cx - b.W * .24 + index * b.W * .16;
            b.line(x, b.H * .82, x + b.W * .07, b.H * .82,
              st.c, .15 + .52 * Math.pow(wave(st.p * .28 - index / 4), 3), 1.4);
          }
        }
        return;
      }
      // The station has a smaller rotating octagonal aperture.
      b.ring(cx, cy, b.W * .46, b.H * .44, 8, st.c, .28, 1.1, Math.PI / 8 + st.p * .02);
      const facets = Array.from({length: 8}, (_, index) => {
        const angle = Math.PI / 8 + index * TAU / 8 + st.p * .02;
        return [cx + Math.cos(angle) * b.W * .46, cy + Math.sin(angle) * b.H * .44];
      });
      b.traceEdges(facets, st.p * .4, st.c, .6);
      if (st.key === 'station' || st.key === 'docked') {
        b.line(cx - b.W * .22, b.H * .78, cx + b.W * .22, b.H * .78, st.c, .48, 1.3);
        for (const side of [-1, 1]) {
          b.poly([[cx + side * b.W * .2, b.H * .69],
            [cx + side * b.W * .25, b.H * .77],
            [cx + side * b.W * .2, b.H * .84]], st.c, .5, 1.1);
        }
      }
    },
    ground(b, st, pal, cx, cy) {
      const type = groundVehicleType(st), hover = type === 'nomad';
      const brake = st.key === 'srv_handbrake', shift = brake ? 0 : st.p * (type === 'rhino' ? 8 : 12);
      if (hover) {
        b.arc(cx, b.H * .88, b.W * .43, b.H * .09, 0, TAU, st.c, .28, 1.1);
        for (let index = 0; index < 3; index += 1) {
          const t = brake ? index / 3 : fract(st.p * .28 + index / 3);
          b.arc(cx, b.H * .86, lerp(b.W * .18, b.W * .55, t),
            lerp(2, b.H * .13, t), 0, TAU, st.c, brake ? .12 : (1 - t) * .35, 1);
        }
        b.bloom(cx, b.H * .82, b.W * .3, pal.accent, .12);
        return;
      }
      const points = [];
      for (let x = -4; x <= b.W + 4; x += 6) {
        points.push([x, b.H * .86 - Math.sin((x + shift) * .07) * (type === 'rhino' ? 1.2 : 2.2)]);
      }
      b.poly(points, st.c, .45, 1);
      if (!brake) {
        const count = type === 'rhino' ? 3 : 5;
        for (let index = 0; index < count; index += 1) {
          const t = fract(st.p * (type === 'rhino' ? .3 : .5) + index / count);
          b.bloom(b.W * (.3 - t * .25), b.H * .84 - t * 5,
            3 + t * (type === 'rhino' ? 4 : 6), st.c, (1 - t) * .25);
        }
      }
      if (type === 'scorpion') {
        b.arc(cx, cy, b.W * .38, b.H * .3, Math.PI * 1.18 + st.p * .08,
          Math.PI * 1.82 + st.p * .08, st.c, .25, 1);
      }
    },
    foot(b, st, pal, cx, cy) {
      if (st.key === 'carrier_deck') {
        const y = b.H * .87;
        b.poly([[3, y + 4], [b.W * .25, y - 3], [b.W * .75, y - 3],
          [b.W - 3, y + 4]], st.c, .48, 1.1);
        for (let index = 0; index < 5; index += 1) {
          const x = lerp(b.W * .17, b.W * .83, index / 4);
          b.line(x, y - 3, x, y + 3, st.c,
            .2 + .38 * wave(st.p * .13 - index / 5), 1.1);
        }
        return;
      }
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
        rockAt(b, pal, x, y, 2.4 + hash(index + 92) * 2.2, st.c, st.p, ends(t) * .6, index + 3);
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
        const reach = r * s.W * 1.05;
        s.arc(0, y, reach, reach * .55, -Math.PI / 2, Math.PI / 2, c, fade * (1 - r * .6) * (.9 - index * .2), 1.6 - index * .3);
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
      const cx = s.W * .7, flare = event.kind === 'arrival_neutron', reach = 6 + p * s.H * 3;
      s.bloom(cx, y, 8 + p * s.H * 1.6, c, fade * .45);
      s.arc(cx, y, reach, reach * .5, 0, TAU, c, fade * .7, 1.5);
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
        const r = clamp(p * 1.2 - index * .1), reach = 8 + r * s.H * 3;
        s.arc(s.W * .6, y, reach, reach * .45, 0, TAU, c, fade * (1 - r), 1.4);
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
    constructor(canvas, role, designHeight = 0) {
      this.canvas = canvas;
      this.role = role;
      this.designHeight = designHeight;
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
      const scale = this.designHeight ? this.H / this.designHeight : 1;
      ctx.setTransform(this.ratio * scale, 0, 0, this.ratio * scale, 0, 0);
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.globalCompositeOperation = 'lighter';
      const painter = this.painter;
      painter.W = this.W / scale;
      painter.H = this.H / scale;
      painter.stroke = 1 / Math.sqrt(scale);
      painter.alpha = 1;
      painter.halo = 1;
      return true;
    }
  }

  class NavigationScene {
    constructor({deck = null, bay = null} = {}) {
      this.surfaces = [];
      if (deck?.getContext) this.surfaces.push(new Surface(deck, 'deck', DECK_DESIGN_HEIGHT));
      if (bay?.getContext) this.surfaces.push(new Surface(bay, 'bay'));
      this.state = null;
      this.previous = null;
      this.transition = null;
      this.palette = cssPalette();
      this.energy = 1;
      this.reduced = false;
      this.mode = 'full';
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
      this.stillTimer = 0;
      this.handleVisibility = () => {
        this.clock = performance.now();
        this.schedule();
        if (!document.hidden) this.repaint(true);
      };
      // A reset graphics context comes back blank: draw it again.
      this.handleRestored = () => this.repaint(true);
      this.surfaces.forEach((surface) => surface.canvas.addEventListener('contextrestored', this.handleRestored));
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
      const mode = SCENE_MODES.has(input.mode) ? input.mode : 'full';
      const modeChanged = mode !== this.mode;
      this.mode = mode;
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
          && next.d.landingGear !== current.d.landingGear && !this.reduced && this.mode === 'full') {
        this.gear = {down: next.d.landingGear, start: now};
      }
      if (!current) this.state = next;
      else if (next.identity !== current.identity) this.changeTo(next, now);
      else this.refresh(next);
      if (input.eventSequence != null && input.eventSequence !== this.eventSequence) {
        this.eventSequence = input.eventSequence;
        if (input.eventKind && !this.reduced && this.mode === 'full') {
          this.event = {kind: String(input.eventKind), tone: String(input.eventTone || ''), start: now};
        }
      }
      if (this.reduced || this.mode === 'off') {
        this.previous = null;
        this.transition = null;
      }
      if (this.reduced || this.mode !== 'full') {
        // Still and Off spend no frames on journal pulses or the gear.
        this.event = null;
        this.gear = null;
      }
      if (this.mode === 'still' && !this.transition) this.settle(this.state);
      this.schedule();
      this.repaint(rescaled || modeChanged);
    }

    // Still and reduced motion both show each state's settled pose.
    settled() {
      return this.reduced || this.mode === 'still';
    }

    settle(state) {
      if (!state) return;
      Object.assign(state, {p: STILL_PHASE, terrain: STILL_PHASE, age: 30});
      Object.assign(state.d, state.target);
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
        starFamily: String(input.starFamily || ''),
        targetTone: String(input.targetTone || ''),
        targetFamily: String(input.targetFamily || ''),
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
      if (this.reduced || !this.visible || this.mode === 'off') {
        this.state = next;
        this.previous = null;
        this.transition = null;
        return;
      }
      if (this.mode === 'still') {
        // Still re-projects between the two settled poses.
        this.settle(current);
        this.settle(next);
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
      state.starFamily = next.starFamily;
      state.targetTone = next.targetTone;
      state.targetFamily = next.targetFamily;
      state.halo = next.halo;
      state.level = next.level;
      for (const [field, value] of Object.entries(next.d)) {
        if (field in state.target) state.target[field] = value;
        else state.d[field] = value;
      }
      if (this.settled()) Object.assign(state.d, state.target);
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
      if (!dt || this.settled() || !this.visible || document.hidden) return;
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
      if (!this.state || !this.surfaces.length || !this.visible || this.reduced || document.hidden) return false;
      if (this.mode === 'off') return false;
      // Still runs only while a change re-projects the hologram.
      return this.mode === 'full' || Boolean(this.transition);
    }

    schedule() {
      if (this.active()) {
        if (!this.frameId) this.frameId = requestAnimationFrame(this.frameCallback);
      } else if (this.frameId) {
        cancelAnimationFrame(this.frameId);
        this.frameId = 0;
      }
      clearTimeout(this.stillTimer);
      this.stillTimer = 0;
      const still = (this.mode === 'still' || this.reduced) && this.mode !== 'off';
      if (still && this.state && this.visible && !document.hidden && !this.frameId) {
        this.stillTimer = setTimeout(() => {
          this.stillTimer = 0;
          this.repaint(true);
          this.schedule();
        }, STILL_REFRESH_MS);
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
      if (!this.active()) {
        // Still: the change has landed. Hold its settled pose, no more frames.
        this.repaint(true);
        this.schedule();
        return;
      }
      this.frameId = requestAnimationFrame(this.frameCallback);
    }

    // Keep the canvases truthful whenever the loop will not: reduced motion
    // gets a settled still, a hidden overlay is current the moment it shows,
    // and `force` covers a canvas the browser has just cleared.
    repaint(force = false) {
      if (!this.state || (this.running && !force)) return;
      if (this.mode === 'off') {
        for (const surface of this.surfaces) surface.begin();
        return;
      }
      if (!this.settled()) {
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
      clearTimeout(this.stillTimer);
    }
  }

  NavigationScene.sceneKey = sceneKey;
  NavigationScene.auraOf = auraOf;
  NavigationScene.hasScene = (key) => Boolean(DECK[key]) || key.startsWith('vehicle_');
  window.NavigationScene = NavigationScene;
})();
