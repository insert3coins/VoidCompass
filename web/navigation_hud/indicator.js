(() => {
  "use strict";

  /*
   * Navigation Holographic Instruments
   * ----------------------------------
   * Ship identity on the left, a dedicated state instrument on the right.
   * Decorative geometry suggests Elite's cockpit instruments, never invented
   * telemetry or a simulated readiness countdown. Journal state selection,
   * the continuous clock and interruptible dissolves remain independent of
   * these drawings. Fixed-size scenes are clipped away from the centre label.
   */

  const TAU = Math.PI * 2;
  const FRAME_MS = 1000 / 30;
  const fract = (value) => ((value % 1) + 1) % 1;
  const clamp = (value, low = 0, high = 1) => Math.max(low, Math.min(high, value));
  const smooth = (value) => {
    const t = clamp(value);
    return t * t * (3 - 2 * t);
  };
  const wave = (value) => .5 - .5 * Math.cos(value * TAU);
  const hash = (value) => {
    const x = Math.sin(value * 91.731 + 17.17) * 43758.5453;
    return x - Math.floor(x);
  };

  // Stable low-poly geology, built once rather than changing silhouettes on
  // every frame. Shared vertices keep the shaded facets joined as rocks tumble.
  const ASTEROIDS = (() => {
    const t = (1 + Math.sqrt(5)) / 2;
    const vertices = [[-1,t,0],[1,t,0],[-1,-t,0],[1,-t,0],
      [0,-1,t],[0,1,t],[0,-1,-t],[0,1,-t],[t,0,-1],[t,0,1],[-t,0,-1],[-t,0,1]];
    const faces = [[0,11,5],[0,5,1],[0,1,7],[0,7,10],[0,10,11],
      [1,5,9],[5,11,4],[11,10,2],[10,7,6],[7,1,8],
      [3,9,4],[3,4,2],[3,2,6],[3,6,8],[3,8,9],
      [4,9,5],[2,4,11],[6,2,10],[8,6,7],[9,8,1]];
    return Array.from({length: 12}, (_, seed) => {
      const shape = vertices.map((v, i) => {
        const r = (.78 + hash(seed * 17 + i) * .26) / Math.hypot(...v);
        return v.map((n, axis) => n * r * (axis === 1 ? .7 + hash(seed + 41) * .25 : 1));
      });
      return {vertices: shape, faces};
    });
  })();

  const PLANETARY = new Set([
    "orbital_approach", "glide", "surface_approach", "surface_hold",
    "surface_departure", "orbital_departure",
  ]);
  const ROUTE_EVENTS = new Set(["route_set", "route_clear", "route_target", "route_divert"]);
  const TARGET_EVENTS = new Set(["target_lock", "target_body", "target_signal", "target_system", "target_clear"]);
  const SCAN_EVENTS = new Set([
    "honk", "fss_progress", "fss_signal", "body_scan", "signals",
    "survey_complete", "mapping_complete", "bio_sample", "codex",
    "valuable_discovery", "first_discovery", "footfall_candidate", "data_sale",
    "dss_efficiency", "dss_complete",
  ]);
  const RESOURCE_EVENTS = new Set([
    "prospector_scan", "prospector_rich", "prospector_core", "mining_refined",
  ]);
  const DOCK_EVENTS = new Set(["dock", "dock_request", "dock_denied", "undock"]);
  const SURFACE_EVENTS = new Set(["body_approach", "planet_clear", "touchdown", "liftoff"]);
  const MAINTENANCE_EVENTS = new Set(["maintenance", "system_reboot"]);
  const WARNING_EVENTS = new Set([
    "warning", "interdiction", "signal_drop", "fighter_destroyed", "srv_destroyed",
    "jet_cone_damage",
  ]);

  class NavigationIndicator {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d", {alpha: true, desynchronized: true});
      this.state = this.makeState({});
      this.previous = null;
      this.receivedModel = false;
      this.stateStarted = performance.now();
      this.transitionStarted = 0;
      this.transitionDuration = 540;
      this.eventStarted = 0;
      this.eventSequence = null;
      this.eventKind = "";
      this.gearPulseStarted = 0;
      this.gearPulseDown = false;
      this.reduced = false;
      this.lastFrame = 0;
      this.clockTime = performance.now();
      this.visible = true;
      this.transitionImage = null;
      this.themeColors = {};
      this.frameCallback = (time) => this.frame(time);
      this.running = true;
      this.resizeObserver = new ResizeObserver(() => this.resize());
      this.resizeObserver.observe(canvas);
      this.resize();
      requestAnimationFrame(this.frameCallback);
    }

    makeState(next) {
      return {
        motion: String(next.motion || "flight"),
        label: String(next.label || "FLIGHT").toUpperCase(),
        vehicleKey: String(next.vehicleKey || "").toLowerCase(),
        color: /^#[0-9a-f]{6}$/i.test(String(next.color || ""))
          ? String(next.color) : "#607584",
        energy: clamp(Number(next.energy || 1), .55, 1.6),
        dynamics: this.normaliseDynamics(next.dynamics),
        cycles: 0,
        terrainCycles: 0,
        age: 0,
        startedAt: performance.now(),
      };
    }

    normaliseDynamics(raw = {}) {
      const source = raw && typeof raw === "object" ? raw : {};
      const number = (value, fallback, low, high) => {
        if (value == null || value === "") return fallback;
        const parsed = Number(value);
        return Number.isFinite(parsed) ? clamp(parsed, low, high) : fallback;
      };
      return {
        gravity: number(source.gravity_g, 0, 0, 20),
        altitude: number(source.altitude_m, -1, -1, 100000000),
        vertical: number(source.vertical_mps, 0, -5000, 5000),
        scan: number(source.scan_percent, 0, 0, 1),
        route: number(source.route_progress, 0, 0, 1),
        landingGear: Boolean(source.landing_gear),
        cargoScoop: Boolean(source.cargo_scoop),
        analysisMode: Boolean(source.analysis_mode),
        hardpoints: Boolean(source.hardpoints_deployed),
        shieldsKnown: Boolean(source.shields_known),
        shieldsUp: Boolean(source.shields_up),
        nightVision: Boolean(source.night_vision),
        inMainShip: Boolean(source.in_main_ship),
        lowFuel: Boolean(source.low_fuel),
        fuelScooping: Boolean(source.fuel_scooping),
        neutronBoost: Boolean(source.neutron_boost),
        neutronBoostValue: number(source.neutron_boost_value, 0, 0, 10),
        fsdInjection: Boolean(source.fsd_injection),
        fsdInjectionPercent: number(source.fsd_injection_percent, 0, 0, 100),
        routeActive: Boolean(source.route_active),
      };
    }

    boostTier(state) {
      if (!state?.dynamics?.neutronBoost) return 0;
      const value = Number(state.dynamics.neutronBoostValue) || 0;
      if (value >= 5.5) return 3;
      if (value >= 3.5) return 2;
      return 1;
    }

    resize() {
      const ratio = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
      const width = Math.max(1, Math.round(this.canvas.clientWidth * ratio));
      const height = Math.max(1, Math.round(this.canvas.clientHeight * ratio));
      if (this.canvas.width !== width || this.canvas.height !== height) {
        this.canvas.width = width;
        this.canvas.height = height;
        this.transitionImage = null;
      }
      this.ratio = ratio;
      this.width = this.canvas.clientWidth;
      this.height = this.canvas.clientHeight;
    }

    update(next = {}) {
      const now = performance.now();
      this.advanceClock(now);
      const incoming = this.makeState(next);
      this.visible = next.visible !== false;
      this.themeColors = {};
      if (this.receivedModel
          && incoming.dynamics.landingGear !== this.state.dynamics.landingGear) {
        this.gearPulseStarted = now;
        this.gearPulseDown = incoming.dynamics.landingGear;
      }
      if (!this.receivedModel) {
        this.state = incoming;
        this.targetDynamics = {...incoming.dynamics};
        this.targetEnergy = incoming.energy;
        this.stateStarted = now;
        this.receivedModel = true;
      } else if (incoming.motion !== this.state.motion || incoming.label !== this.state.label
          || incoming.vehicleKey !== this.state.vehicleKey
          || this.boostTier(incoming) !== this.boostTier(this.state)) {
        // If another event interrupts a dissolve, continue from exactly what
        // was on screen instead of jumping back to either underlying state.
        this.transitionImage = null;
        if (this.previous && typeof document !== "undefined") {
          const image = document.createElement("canvas");
          image.width = this.canvas.width;
          image.height = this.canvas.height;
          image.getContext("2d").drawImage(this.canvas, 0, 0);
          this.transitionImage = image;
        }
        this.previous = {...this.state};
        incoming.cycles = this.state.cycles;
        incoming.terrainCycles = this.state.terrainCycles;
        this.targetDynamics = {...incoming.dynamics};
        this.targetEnergy = incoming.energy;
        incoming.energy = this.state.energy;
        // Altitude/vertical interpolation only shares a physical frame within
        // a planetary sequence, never across a new body/vehicle identity.
        if (PLANETARY.has(this.key(incoming)) && PLANETARY.has(this.key(this.state))) {
          for (const field of ["altitude", "vertical", "gravity"]) {
            incoming.dynamics[field] = this.state.dynamics[field];
          }
        }
        this.state = incoming;
        this.stateStarted = now;
        this.transitionStarted = now;
        this.transitionDuration = this.transitionMs(this.previous, incoming);
      } else {
        this.targetDynamics = incoming.dynamics;
        this.targetEnergy = incoming.energy;
        this.state.color = incoming.color;
        for (const [field, value] of Object.entries(incoming.dynamics)) {
          if (!["altitude", "vertical", "gravity"].includes(field)) this.state.dynamics[field] = value;
        }
      }
      this.reduced = Boolean(next.reduced);
      if (this.reduced) {
        this.previous = null;
        this.transitionImage = null;
        this.state.dynamics = {...this.targetDynamics};
        this.state.energy = this.targetEnergy;
      }
      if (next.eventSequence != null && next.eventSequence !== this.eventSequence) {
        this.eventSequence = next.eventSequence;
        this.eventKind = String(next.eventKind || "");
        this.eventStarted = now;
      }
      // The animation clock owns all drawing. Incoming telemetry must not
      // insert extra, unevenly spaced frames between requestAnimationFrames.
    }

    advanceClock(now) {
      const dt = clamp((now - this.clockTime) / 1000, 0, .1);
      this.clockTime = now;
      if (this.reduced || !this.visible || document.hidden) return;
      const blend = 1 - Math.exp(-dt / .3);
      const current = this.state;
      current.energy += ((this.targetEnergy ?? current.energy) - current.energy) * blend;
      for (const field of ["altitude", "vertical", "gravity"]) {
        const target = this.targetDynamics?.[field] ?? current.dynamics[field];
        const old = current.dynamics[field];
        current.dynamics[field] = field === "altitude" && (old < 0 || target < 0)
          ? target : old + (target - old) * blend;
      }
      for (const state of [current, this.previous]) {
        if (!state) continue;
        state.age += dt;
        const key = this.key(state);
        // Decorative spool-up settles at a steady running intensity. It is
        // never a charge countdown or a prediction of FSD readiness.
        const spool = ["fsd_charge", "hyper_charge"].includes(key)
          ? .65 + .45 * smooth(state.age / 2.4) : 1;
        const rate = state.energy * spool / this.period(state);
        state.cycles += dt * rate;
        state.terrainCycles += dt * rate * (.65 + clamp(Math.abs(state.dynamics.vertical) / 160));
      }
    }

    key(state) {
      const motion = String(state?.motion || "flight");
      const label = String(state?.label || "FLIGHT").toUpperCase();
      if (motion === "scanner") return label.startsWith("DSS") ? "dss" : "fss";
      if (motion === "map") return ({
        "GALAXY MAP": "galaxy_map", "SYSTEM MAP": "system_map",
        "POWER MAP": "power_map", ORRERY: "orrery", CODEX: "codex",
      })[label] || "map";
      if (motion === "surface_vehicle") {
        if (label === "NOMAD" || state?.vehicleKey === "nomad") return "nomad";
        if (state?.vehicleKey === "scorpion") return "scorpion";
        if (label === "RHINO" || state?.vehicleKey === "rhino") return "rhino";
        return "srv";
      }
      if (motion === "fsd_charge") return label === "HYPER CHARGE" ? "hyper_charge" : "fsd_charge";
      if (motion === "jump") return label === "JUMPING" ? "jumping" : "hyperspace";
      if (motion === "arrival" && label === "INTERDICTION EVADED") return "interdiction_evaded";
      if (motion === "fsd_lock") {
        if (label === "MASS LOCK") return "mass_lock";
        if (label.startsWith("FSD INJECTION")) return "fsd_injection";
        if (label === "SIGNAL DROP") return "signal_drop";
        return label.startsWith("SIGNAL THREAT") ? "signal_threat" : "signal_lock";
      }
      if (motion === "combat") {
        if (label === "INTERDICTED") return "interdicted";
        if (label === "INTERDICTION") return "interdiction";
        return "combat";
      }
      if (motion.startsWith("vehicle_")) {
        const vehicle = label.includes("NOMAD") || state?.vehicleKey === "nomad" ? "nomad"
          : label.includes("FIGHTER") || state?.vehicleKey === "fighter" ? "fighter"
            : label.includes("SCORPION") || state?.vehicleKey === "scorpion" ? "scorpion"
              : label.includes("RHINO") || state?.vehicleKey === "rhino" ? "rhino"
              : label.includes("SRV") || label.includes("SCARAB") || state?.vehicleKey === "scarab" ? "srv"
              : label.includes("CREW") ? "crew" : "ship";
        return `${motion}_${vehicle}`;
      }
      if (motion === "flight" && label === "MULTICREW") return "multicrew";
      if (motion === "flight" && label === "EXPLORATION") return "exploration";
      if (motion === "docked" && label === "STATION") return "station";
      if (motion === "station" && label === "CARRIER VICINITY") return "carrier_vicinity";
      return motion;
    }

    family(state) {
      const key = this.key(state);
      if (["supercruise", "fsd_charge", "hyper_charge", "hyperspace", "jumping", "arrival",
        "interdiction_evaded", "fsd_cooldown", "supercruise_overcharge",
        "supercruise_assist", "local_arrival", "fsd_injection"].includes(key)) return "fsd";
      if (PLANETARY.has(key) || ["surface_station", "landed", "srv", "scorpion", "rhino", "nomad", "on_foot",
        "srv_handbrake", "srv_turret", "srv_drive_assist"].includes(key)) return "surface";
      if (["fss", "dss", "map", "galaxy_map", "system_map", "power_map",
        "orrery", "codex", "exploration", "phenomena", "target_lock"].includes(key)) return "scope";
      if (["mass_lock", "signal_lock", "signal_drop", "signal_threat", "combat",
        "interdiction", "interdicted", "asteroid_field", "srv_threat",
        "capital_contact", "unknown_contact", "heavy_combat", "heat_critical",
        "suit_hazard", "jet_cone_damage", "docking_denied"].includes(key)) return "hazard";
      if (key.startsWith("vehicle_") || ["fighter", "multicrew"].includes(key)) return "vehicle";
      if (key.startsWith("carrier_")) return "carrier";
      if (["docked", "station", "docking_assist", "docking_clearance",
        "maintenance", "system_reboot"].includes(key)) return "station";
      if (key === "settlement_area") return "surface";
      if (["left_panel", "right_panel", "comms_panel", "role_panel",
        "station_services"].includes(key)) return "interface";
      return "flight";
    }

    transitionMs(previous, next) {
      const from = this.family(previous), to = this.family(next);
      if (from === to) return from === "fsd" ? 430 : 390;
      if (from === "fsd" || to === "fsd") return 650;
      if (from === "hazard" || to === "hazard") return 470;
      if (from === "surface" || to === "surface") return 560;
      return 510;
    }

    period(state) {
      const key = this.key(state);
      return ({
        flight: 1.9, fighter: .82, multicrew: 1.5, exploration: 2.25,
        supercruise: .94, supercruise_overcharge: .48,
        supercruise_assist: 1.28, flight_assist_off: .84, silent_running: 2.2,
        fsd_charge: .86, hyper_charge: .64, hyperspace: .58, jumping: .72,
        arrival: 1.15, interdiction_evaded: 1.05, fsd_cooldown: 1.55,
        local_arrival: 1.42, fsd_injection: 1.9, target_lock: 2.2, carrier_vicinity: 2.3,
        carrier_transit: 1.08, carrier_arrival: 1.34, carrier_deck: 2.4,
        fss: 1.52, dss: 1.82, map: 2.1, galaxy_map: 2.35,
        system_map: 1.86, power_map: 1.7, orrery: 2.5, codex: 1.9,
        phenomena: 2.6, docking_assist: 1.34, settlement_area: 1.95,
        srv_threat: .72, capital_contact: 1.48, unknown_contact: 1.72,
        heavy_combat: .56,
        left_panel: 1.62, right_panel: 1.62, comms_panel: 1.34,
        role_panel: 1.78, station_services: 2.05,
        orbital_approach: 1.68, glide: .82, surface_approach: 1.38,
        surface_hold: 2.25, surface_departure: 1.28, orbital_departure: 1.55,
        landed: 2.4, on_foot: 1.32, srv: 1.18, scorpion: .9, rhino: 1.04, nomad: 1.05,
        srv_handbrake: 1.8, srv_turret: 1.2, srv_drive_assist: 1.35,
        asteroid_field: 5.2, mass_lock: 1.12, signal_lock: 1.55,
        signal_drop: .92, signal_threat: .76, combat: .64,
        interdiction: .5, interdicted: .43, docked: 2.3, station: 2.1,
        surface_station: 1.72,
        heat_critical: .58, suit_hazard: .72, jet_cone_damage: .46,
        docking_clearance: 1.42, docking_denied: .68,
        maintenance: 1.7, system_reboot: .92,
      })[key] || 1.45;
    }

    phase(state, now) {
      if (this.reduced) return .18;
      // Keep fractional-speed oscillators continuous across the base cycle.
      // Only moving packets wrap their individual positions, under a fade.
      return state.cycles;
    }

    geometry() {
      const width = Math.max(1, this.width);
      const height = Math.max(1, this.height);
      const center = width / 2;
      const aperture = Math.min(188, Math.max(142, width * .38));
      return {
        width, height, center, y: height / 2 + .5,
        top: 3.5, bottom: height - 4,
        left: 5, right: width - 5,
        centerLeft: center - aperture / 2,
        centerRight: center + aperture / 2,
      };
    }

    responseGeometry(g) {
      const left = g.centerRight + 7;
      const right = g.right - 1;
      const center = (left + right) / 2;
      return {
        width: g.width, height: g.height, center, y: g.y,
        top: g.top, bottom: g.bottom, left, right,
        // Only the short event accent uses this tiny break; sustained scenes
        // now own one complete response bay rather than two miniature halves.
        centerLeft: center - 2.5, centerRight: center + 2.5,
      };
    }

    // Convert a 0..1 journey into the visible rail, skipping the label aperture.
    trackPoint(progress, g, y = g.y) {
      const p = ((progress % 1) + 1) % 1;
      const leftLength = g.centerLeft - g.left;
      const rightLength = g.right - g.centerRight;
      const distance = p * (leftLength + rightLength);
      return {
        x: distance <= leftLength
          ? g.left + distance
          : g.centerRight + distance - leftLength,
        y,
        wing: distance <= leftLength ? 0 : 1,
      };
    }

    withAlpha(alpha, draw) {
      if (alpha <= .002) return;
      const ctx = this.ctx;
      ctx.save();
      ctx.globalAlpha *= clamp(alpha);
      draw();
      ctx.restore();
    }

    line(x1, y1, x2, y2, color, alpha = 1, width = 1) {
      this.withAlpha(alpha, () => {
        const ctx = this.ctx;
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
        ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
      });
    }

    path(points, color, alpha = 1, width = 1, close = false, fillAlpha = 0) {
      if (!points.length) return;
      this.withAlpha(alpha, () => {
        const ctx = this.ctx;
        ctx.beginPath(); ctx.moveTo(points[0][0], points[0][1]);
        points.slice(1).forEach(([x, y]) => ctx.lineTo(x, y));
        if (close) ctx.closePath();
        if (fillAlpha > 0) {
          ctx.save(); ctx.globalAlpha *= fillAlpha; ctx.fillStyle = color; ctx.fill(); ctx.restore();
        }
        ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
      });
    }

    dot(x, y, radius, color, alpha = 1) {
      this.withAlpha(alpha, () => {
        const ctx = this.ctx;
        ctx.beginPath(); ctx.arc(x, y, Math.max(.2, radius), 0, TAU);
        ctx.fillStyle = color; ctx.fill();
      });
    }

    arc(x, y, rx, ry, start, end, color, alpha = 1, width = 1) {
      this.withAlpha(alpha, () => {
        const ctx = this.ctx;
        ctx.beginPath(); ctx.ellipse(x, y, Math.max(.2, rx), Math.max(.2, ry), 0, start, end);
        ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
      });
    }

    angularRing(x, y, rx, ry, segments, color, alpha = 1, width = 1, rotation = 0) {
      const points = [];
      for (let index = 0; index < segments; index += 1) {
        const angle = rotation + index * TAU / segments;
        points.push([x + Math.cos(angle) * rx, y + Math.sin(angle) * ry]);
      }
      this.path(points, color, alpha, width, true);
    }

    rect(x, y, width, height, color, alpha = 1, fill = false) {
      this.withAlpha(alpha, () => {
        const ctx = this.ctx;
        ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 1;
        if (fill) ctx.fillRect(x, y, width, height);
        else ctx.strokeRect(x, y, width, height);
      });
    }

    glowDot(x, y, radius, color, alpha = 1) {
      this.withAlpha(alpha, () => {
        const ctx = this.ctx;
        ctx.shadowColor = color; ctx.shadowBlur = 6;
        ctx.beginPath(); ctx.arc(x, y, radius, 0, TAU);
        ctx.fillStyle = color; ctx.fill();
      });
    }

    trackStroke(progress, trail, g, y, color, alpha = 1, width = 1.5) {
      const samples = 13;
      let previous = null;
      for (let index = 0; index <= samples; index += 1) {
        const local = progress - trail + trail * index / samples;
        const point = this.trackPoint(local, g, y);
        if (previous && previous.wing === point.wing) {
          const strength = alpha * (.16 + .84 * index / samples);
          this.line(previous.x, previous.y, point.x, point.y, color, strength, width);
        }
        previous = point;
      }
      const head = this.trackPoint(progress, g, y);
      this.glowDot(head.x, head.y, 1.25, color, alpha);
    }

    chevron(x, y, direction, color, alpha = 1, size = 4) {
      this.path([
        [x - direction * size, y - size], [x, y], [x - direction * size, y + size],
      ], color, alpha, 1.2);
    }

    ship(x, y, color, alpha = 1, scale = 1, direction = 1) {
      const s = scale * direction;
      this.path([
        [x + 6 * s, y], [x - 4 * s, y - 3.5], [x - 1.5 * s, y],
        [x - 4 * s, y + 3.5], [x + 6 * s, y],
      ], color, alpha, 1.2);
    }

    chassis(g, color) {
      // Quiet mounting notches, not another horizontal line through the scene.
      for (const [x, direction] of [[g.left, 1], [g.right, -1]]) {
        this.path([[x + direction * 8, g.top + 1], [x, g.top + 1],
          [x, g.top + 6]], color, .35);
        this.path([[x, g.bottom - 5], [x, g.bottom],
          [x + direction * 8, g.bottom]], color, .24);
      }
    }

    drawIdentity(g, state, p, alpha) {
      if (alpha <= .002) return;
      const c = state.color, key = this.key(state), family = this.family(state);
      const x = g.left + 6, end = g.centerLeft - 7, span = end - x;
      const y = g.y, top = g.top + 2, bottom = g.bottom - 2;
      // Leave the actual ship art unobscured. These are propulsion/sensor/
      // support signatures at its perimeter, not a second copy of the right bay.
      this.withAlpha(alpha, () => {
        if (family === "fsd") {
          const charge = key.includes("charge") && key !== "supercruise_overcharge";
          const cooling = key === "fsd_cooldown";
          const arriving = ["arrival", "local_arrival", "interdiction_evaded"].includes(key);
          const envelope = arriving ? 1 - smooth(state.age / 2) : 1;
          for (let i = 0; i < 5; i++) {
            const t = fract(p * .6 + i / 5), fade = Math.sin(t * Math.PI);
            const at = x + (charge ? t : 1 - t) * span;
            const flare = cooling ? 3 + t * 4 : 2;
            for (const side of [-1, 1]) {
              this.path([[at - 6, y + side * (10 + flare)], [at, y + side * 10],
                [at + 4, y + side * 10]], c, fade * .5 * envelope, 1.2);
            }
          }
          if (arriving) this.brackets(x + span / 2, y, span * .47, 14, c, .6);
          const boost = this.boostTier(state);
          for (let i = 0; i < boost; i++) {
            this.line(end - i * 5, top, end - 2 - i * 5, top + 4, c, .8, 1.5);
          }
        } else if (PLANETARY.has(key)) {
          const depart = key.includes("departure"), hold = key === "surface_hold";
          for (let i = 0; i < 4; i++) {
            const t = hold ? i / 4 : fract(state.terrainCycles * .4 + i / 4);
            const yy = top + (depart ? 1 - t : t) * (bottom - top);
            const fade = hold ? .4 : Math.sin(t * Math.PI) * .7;
            this.line(x, yy, x + (i % 2 ? 4 : 7), yy, c, fade);
            this.line(end - (i % 2 ? 4 : 7), yy, end, yy, c, fade);
          }
          if (hold) this.arc(x + span / 2, bottom - 1, span * .4, 2, 0, TAU, c, .42);
        } else if (family === "scope" || family === "interface") {
          const frequency = key === "fss" ? 2 : key === "dss" ? .65 : 1;
          for (let i = 0; i < 11; i++) {
            const xx = x + i * span / 10;
            const strength = .2 + .6 * Math.pow(wave(p * .4 * frequency - i / 11), 3);
            this.line(xx, bottom, xx, bottom - (key === "fss" ? 2 + hash(i) * 3 : 2), c, strength);
          }
          this.brackets(x + span / 2, y, span * .48, 13, c, .32);
        } else if (key.startsWith("vehicle_")) {
          const board = key.includes("board"), t = smooth(state.age / 1.8);
          for (const side of [-1, 1]) {
            const at = x + span / 2 + side * span * (board ? .47 - t * .08 : .39 + t * .08);
            this.path([[at - side * 5, top], [at, top], [at, bottom],
              [at - side * 5, bottom]], c, .65);
          }
        } else if (family === "surface") {
          const parked = ["landed", "srv_handbrake", "surface_station"].includes(key);
          const hover = key === "nomad" || state.vehicleKey === "nomad";
          for (let i = 0; i < (hover ? 3 : 6); i++) {
            const xx = x + (i + .5) * span / (hover ? 3 : 6);
            const lift = parked ? 0 : wave(p * .45 + i * .2) * 2;
            this.path([[xx - 4, bottom - 1 - lift], [xx, bottom + 1],
              [xx + 4, bottom - 1 - lift]], c, .5);
          }
        } else if (family === "carrier" || family === "station") {
          const transit = key === "carrier_transit";
          for (let i = 0; i < 6; i++) {
            const xx = x + i * span / 5;
            this.rect(xx - 2, bottom - 2, 4, 2, c, .3 + .4 * wave(p * .35 - i / 6), true);
          }
          if (!transit) this.brackets(x + span / 2, y, span * .48, 13, c, .45);
        } else if (key === "asteroid_field") {
          // Passing fragments frame the ship without covering its portrait.
          // Use the same drift direction as the field, with no looping reticle.
          for (let i = 0; i < 10; i++) {
            const t = fract(hash(i + 121) + p * (.035 + hash(i + 88) * .025));
            const xx = x + (1 - t) * span;
            const yy = i % 2 ? bottom - 1 : top + 1;
            const fade = smooth(t * 7) * smooth((1 - t) * 7);
            const size = .8 + hash(i + 76) * 1.5;
            this.path([[xx - size, yy], [xx, yy - size * .6],
              [xx + size, yy + .3], [xx, yy + size * .6]], c, fade * .6, .8, true, .12);
          }
        } else if (family === "hazard") {
          for (const side of [-1, 1]) {
            const xx = side < 0 ? x + 3 : end - 3;
            this.path([[xx, top + 2], [xx + side * 3, y], [xx, bottom - 2]], c,
              .35 + .35 * wave(p * .5), 1.2);
          }
        } else {
          this.arc(x + span / 2, bottom - 1, span * .43, 3, .05, Math.PI - .05, c, .45);
          const t = p * .35;
          this.dot(x + span / 2 + Math.sin(t) * span * .36,
            bottom - 1 + Math.cos(t) * 2, 1.1, c, .65);
        }
      });
    }

    // All response instruments use a 120 x 36 design space. Clip once so
    // perspective particles never escape into the centre label or HUD frame.
    instrument(g, alpha, render) {
      this.withAlpha(alpha, () => {
        const ctx = this.ctx;
        ctx.beginPath(); ctx.rect(g.left, g.top, g.right - g.left, g.bottom - g.top); ctx.clip();
        ctx.translate(g.left, g.top);
        ctx.scale((g.right - g.left) / 120, (g.bottom - g.top) / 36);
        render();
      });
    }

    brackets(x, y, w, h, c, alpha = .7) {
      for (const sx of [-1, 1]) for (const sy of [-1, 1]) {
        this.path([[x + sx * (w - 5), y + sy * h], [x + sx * w, y + sy * h],
          [x + sx * w, y + sy * (h - 4)]], c, alpha, 1.1);
      }
    }

    traceEdges(points, cycle, c, alpha = .8) {
      // Energise a fixed housing without moving a parked ship or repeating
      // its arrival. Overlapping edge fades keep the contour's seam smooth.
      for (let i = 0; i < points.length; i++) {
        const next = points[(i + 1) % points.length];
        const light = Math.pow(wave(cycle - i / points.length), 4);
        this.line(points[i][0], points[i][1], next[0], next[1], c, light * alpha, 1.7);
      }
    }

    globe(x, y, r, c, p = 0, alpha = .7) {
      this.arc(x, y, r, r, 0, TAU, c, alpha, 1.2);
      this.arc(x, y, r, r * .31, 0, TAU, c, alpha * .4);
      this.arc(x, y, r * .7, r * .7, 0, TAU, c, alpha * .17);
      for (let i = 0; i < 3; i++) {
        const angle = p * .32 + i * Math.PI / 3;
        this.arc(x, y, Math.max(.2, Math.abs(Math.cos(angle)) * r), r, 0, TAU,
          c, alpha * (.23 + .2 * Math.abs(Math.sin(angle))));
      }
    }

    asteroid(x, y, size, c, p, alpha, seed) {
      const mesh = ASTEROIDS[seed % ASTEROIDS.length];
      const yaw = p * (seed % 2 ? -.31 : .24) + seed * 2.1;
      const pitch = p * .17 + seed * .83;
      const cy = Math.cos(yaw), sy = Math.sin(yaw);
      const cx = Math.cos(pitch), sx = Math.sin(pitch);
      const points = mesh.vertices.map(([vx, vy, vz]) => {
        const xx = vx * cy + vz * sy, zz = vz * cy - vx * sy;
        return [xx, vy * cx - zz * sx, vy * sx + zz * cx];
      });
      const ctx = this.ctx;
      const shadow = this.themeColor("bg", "#081018");
      this.withAlpha(alpha, () => {
        const opacity = ctx.globalAlpha;
        for (const [a, b, d] of mesh.faces) {
          const v = points[a], w = points[b], u = points[d];
          const ax = w[0]-v[0], ay = w[1]-v[1], az = w[2]-v[2];
          const bx = u[0]-v[0], by = u[1]-v[1], bz = u[2]-v[2];
          const nx = ay*bz-az*by, ny = az*bx-ax*bz, nz = ax*by-ay*bx;
          if (nz <= 0) continue;
          // Fixed upper-left light reveals solid facets rather than a wire cage.
          const light = clamp((-nx*.45 - ny*.65 + nz*.6) / Math.hypot(nx, ny, nz));
          ctx.beginPath();
          ctx.moveTo(x + v[0]*size, y + v[1]*size);
          ctx.lineTo(x + w[0]*size, y + w[1]*size);
          ctx.lineTo(x + u[0]*size, y + u[1]*size);
          ctx.closePath();
          ctx.globalAlpha = opacity;
          ctx.fillStyle = shadow;
          ctx.fill();
          ctx.globalAlpha = opacity * (.1 + light * .47);
          ctx.fillStyle = c;
          ctx.fill();
          ctx.globalAlpha = opacity * (.14 + light * .35);
          ctx.strokeStyle = c;
          ctx.lineWidth = .45;
          ctx.lineJoin = "round";
          ctx.stroke();
        }
      });
    }

    drawAsteroidField(state, p) {
      const c = state.color;
      // Decorative parallax, not a claim about real asteroid positions/speed.
      // Every crossing fades outside the scene; rotations use unwrapped time.
      for (let i = 0; i < 26; i++) {
        const t = fract(hash(i + 150) + p * .017);
        const x = (1 - t) * 132 - 6;
        const y = 18 + (hash(i + 204) - .5) * 23 + (x - 60) * .085;
        this.dot(x, y, .25 + hash(i + 98) * .4, c,
          .16 * smooth(t * 12) * smooth((1 - t) * 12));
      }
      // Far -> near: small slow silhouettes behind larger, brighter boulders.
      for (let layer = 0; layer < 3; layer++) {
        const count = [7, 5, 3][layer];
        for (let i = 0; i < count; i++) {
          const seed = layer * 7 + i;
          const t = fract(i / count + hash(seed + 60) * .11 + p * [.022,.037,.057][layer]);
          const x = 148 * (1 - t) - 14;
          const y = 7 + hash(seed + 33) * 22 + Math.sin(p * .22 + seed) * 1.3;
          const size = [2.4, 5.1, 8.5][layer] + hash(seed + 29) * [1.7, 2.5, 3][layer];
          const fade = smooth(t * 9) * smooth((1 - t) * 9);
          this.asteroid(x, y, size, c, p, fade * [.35,.7,.95][layer], seed);
        }
      }
    }

    spaceLanes(p, c, {cx = 62, cy = 18, count = 14, speed = .32, twist = 0, strength = .65} = {}) {
      for (let i = 0; i < count; i++) {
        const t = fract(p * speed + hash(i + 23)), fade = Math.sin(t * Math.PI);
        const angle = hash(i + 51) * TAU + twist * Math.sin(p * .3 + i);
        const depth = t * t, tail = Math.max(0, t - .10 - t * .12) ** 2;
        const dx = Math.cos(angle) * 80, dy = Math.sin(angle) * 27;
        this.line(cx + dx * tail, cy + dy * tail, cx + dx * depth, cy + dy * depth,
          c, strength * fade, .7 + t * .8);
      }
    }

    drawDrive(state, p, key) {
      const c = state.color, tier = this.boostTier(state);
      if (key === "fsd_injection") {
        // Synthesis feeds the drive core. This is an armed-buff signature,
        // never a simulated recipe progress meter or an automatic jump.
        this.angularRing(67, 18, 13, 11, 6, c, .7, 1.2, Math.PI / 6);
        this.angularRing(67, 18, 6, 5, 6, c, .45, 1, Math.PI / 6);
        for (let i = 0; i < 3; i++) {
          const yy = 7 + i * 11;
          this.path([[10, yy], [29, yy], [46, 18], [52, 18]], c, .3);
          const t = fract(p * .3 + i / 3);
          this.dot(12 + t * 38, yy + (18 - yy) * t, 1.2, c, Math.sin(t * Math.PI) * .8);
        }
        const level = state.dynamics.fsdInjectionPercent >= 100 ? 3
          : state.dynamics.fsdInjectionPercent >= 50 ? 2 : 1;
        for (let i = 0; i < level; i++) this.chevron(91 + i * 8, 18, 1, c, .65, 4);
        return;
      }
      if (["supercruise", "supercruise_overcharge", "supercruise_assist"].includes(key)) {
        const sco = key === "supercruise_overcharge", assist = key === "supercruise_assist";
        // Supercruise: a bowed space-time wake, not a rotating radar or bars.
        const cx = 67, cy = 18;
        this.spaceLanes(p, c, {cx, cy, count: sco ? 22 : 13, speed: sco ? .45 : .28, strength: .7});
        for (let i = 0; i < (sco ? 5 : 3); i++) {
          const t = fract(p * (sco ? .4 : .24) + i / (sco ? 5 : 3));
          const fade = Math.sin(t * Math.PI), points = [];
          for (let j = 0; j <= 16; j++) {
            const u = j / 16 * 2 - 1;
            points.push([cx - 7 - t * 54 + (1 - u * u) * (sco ? 14 : 9), cy + u * (4 + t * 19)]);
          }
          this.path(points, c, fade * .55, sco ? 1.35 : 1);
        }
        this.path([[62, 18], [69, 15], [75, 18], [69, 21], [62, 18]], c, .85, 1.2, false, .2);
        if (assist) {
          this.brackets(70, 18, 13, 9, c, .72);
          this.line(84, 18, 109, 18, c, .3);
          this.dot(110, 18, 1.7, c, .7);
        }
        if (sco) for (const side of [-1, 1]) {
          const points = [];
          for (let j = 0; j <= 20; j++) {
            const x = j * 5;
            points.push([x, 18 + side * (10 + Math.sin(j * .72 - p * 2) * 2)]);
          }
          this.path(points, c, .35, 1.2);
        }
        // Confirmed boosts add symmetric jet-cone threads, not fake speed data.
        for (let i = 0; i < tier; i++) for (const side of [-1, 1]) {
          const points = [];
          for (let j = 0; j <= 16; j++) {
            const t = j / 16;
            points.push([12 + t * 62, 18 + side * (2 + i * 2 + (1 - t) * 5)
              + Math.sin(t * 12 - p * 1.7 + i) * (1 - t) * 1.6]);
          }
          this.path(points, c, .38, 1);
        }
        return;
      }
      if (key === "fsd_charge" || key === "hyper_charge") {
        const hyper = key === "hyper_charge", settle = .65 + .35 * smooth(state.age / 2.4);
        // Coils feed inward; inter-system charge opens a faceted destination
        // aperture, whereas local FSD charge winds an elongated solenoid.
        for (let i = 0; i < 7; i++) {
          const x = 16 + i * 14, strength = .2 + .5 * wave(p * .65 - Math.abs(i - 3) * .2);
          this.arc(x, 18, hyper ? 3 : 4.5, 5 + Math.abs(i - 3) * 2, -.8, .8, c, strength);
          this.arc(x, 18, hyper ? 3 : 4.5, 5 + Math.abs(i - 3) * 2, Math.PI - .8, Math.PI + .8, c, strength);
        }
        for (const side of [-1, 1]) for (let strand = 0; strand < 2; strand++) {
          const points = [];
          for (let j = 0; j <= 24; j++) {
            const t = j / 24, amp = Math.sin(t * Math.PI) * (hyper ? 8 : 5);
            points.push([60 + side * (4 + t * 50), 18 + Math.sin(t * 11 - p * 2 + strand * Math.PI) * amp]);
          }
          this.path(points, c, .3 + strand * .25, 1.1);
        }
        if (hyper) {
          this.angularRing(60, 18, 12, 12, 6, c, .6, 1.15, Math.PI / 6);
          this.angularRing(60, 18, 6 + wave(p * .4) * 2, 7, 6, c, .85, 1.2, Math.PI / 6);
        } else {
          this.arc(60, 18, 11, 7, 0, TAU, c, .7);
          this.line(43, 18, 77, 18, c, .38 + .3 * settle, 1.8);
        }
        this.glowDot(60, 18, 1.6 + wave(p * .6) * .7, c, .8);
        return;
      }
      if (key === "hyperspace" || key === "jumping") {
        const opening = key === "jumping", cx = 63 + Math.sin(p * .17) * 5, cy = 18;
        this.spaceLanes(p, c, {cx, cy, count: 22, speed: .34, twist: .15, strength: .75});
        for (let i = 0; i < 5; i++) {
          const t = fract(p * .26 + i / 5), fade = Math.sin(t * Math.PI);
          const points = [];
          for (let j = 0; j < 10; j++) {
            const angle = j * TAU / 10 + Math.sin(p * .12) * .12;
            const distortion = opening ? 1 : 1 + .16 * Math.sin(angle * 3 + p * .45 + i);
            points.push([cx + Math.cos(angle) * (4 + t * t * 75) * distortion,
              cy + Math.sin(angle) * (2 + t * t * 24) * distortion]);
          }
          this.path(points, c, fade * .5, 1, true);
        }
        if (opening) {
          const t = smooth(state.age / 1.8);
          this.line(5, 18, 115, 18, c, (1 - t) * .6, 1 + t * 2);
        }
        return;
      }
      if (["arrival", "interdiction_evaded", "local_arrival"].includes(key)) {
        const t = smooth(state.age / 2.2), local = key === "local_arrival";
        this.spaceLanes(p, c, {count: 12, speed: .2, strength: (1 - t) * .8});
        if (local) {
          this.arc(65, 19, 24, 9, 0, TAU, c, .35);
          this.ship(65, 19, c, .9, 1.3);
          const bearing = p * TAU * .32;
          this.arc(65, 19, 24, 9, bearing, bearing + .8, c, .8, 1.5);
        } else {
          this.arc(66, 18, 10, 10, 0, TAU, c, .78, 1.5);
          for (let i = 0; i < 14; i++) {
            const a = i * TAU / 14;
            const r = 12 + wave(p * .24 + i / 14) * 2;
            this.line(66 + Math.cos(a) * 11, 18 + Math.sin(a) * 11,
              66 + Math.cos(a) * r, 18 + Math.sin(a) * r, c, .4);
          }
          this.arc(66, 18, 7, 10, -.9, 1.2, c, .25);
        }
        this.brackets(66, 18, 19 + (1 - t) * 34, 14, c, .35 + .4 * t);
        for (let i = 0; i < 4; i++) this.line(12 + i * 7, 31, 16 + i * 7, 31, c, .2 + .25 * t);
        return;
      }
      if (key === "fsd_cooldown") {
        const cooling = .35 + .65 * (1 - smooth(state.age / 3));
        this.angularRing(60, 18, 13, 12, 6, c, .6, 1.2, Math.PI / 6);
        this.angularRing(60, 18, 7, 6, 6, c, .3, 1, Math.PI / 6);
        for (const side of [-1, 1]) for (let i = 0; i < 5; i++) {
          const x = 60 + side * (22 + i * 8), heat = .2 + cooling * wave(p * .25 - i * .1) * .5;
          this.path([[x, 8 + i], [x + side * 3, 12 + i], [x + side * 3, 24 - i],
            [x, 28 - i]], c, heat, 1.4);
        }
        for (let i = 0; i < 3; i++) {
          const t = fract(p * .25 + i / 3), fade = Math.sin(t * Math.PI) * cooling;
          for (const side of [-1, 1]) this.line(60 + side * (17 + t * 32), 18,
            60 + side * (21 + t * 32), 18, c, fade * .55);
        }
      }
    }

    drawSurveyInstrument(state, p, key) {
      const c = state.color;
      if (key === "fss") {
        // FSS tuning spectrum with discrete signal peaks and a focus lens.
        const peaks = [.16, .33, .61, .82], points = [];
        for (let i = 0; i <= 70; i++) {
          const u = i / 70;
          const amp = peaks.reduce((sum, at, n) => sum + Math.exp(-(((u - at) / .027) ** 2))
            * (7 + n * 1.6 + wave(p * .3 + n) * 2), 0);
          points.push([5 + u * 110, 26 - amp]);
        }
        this.path(points, c, .78, 1.2);
        this.line(5, 29, 115, 29, c, .25);
        for (let i = 0; i < 18; i++) this.line(5 + i * 6.4, 30, 5 + i * 6.4, i % 3 ? 32 : 34, c, .32);
        const x = 16 + wave(p * .12) * 88;
        this.brackets(x, 15, 7, 11, c, .8);
        this.line(x, 4, x, 27, c, .24);
      } else if (key === "dss") {
        this.globe(68, 18, 14, c, p, .75);
        for (let i = 0; i < 3; i++) {
          const t = fract(p * .18 + i / 3), fade = Math.sin(t * Math.PI);
          const path = [];
          for (let j = 0; j <= 18; j++) {
            const u = j / 18;
            path.push([14 + u * 48, 27 - u * 14 - Math.sin(u * Math.PI) * (9 + i * 3)]);
          }
          this.path(path, c, .15);
          this.glowDot(14 + t * 48, 27 - t * 14 - Math.sin(t * Math.PI) * (9 + i * 3), 1.3, c, fade * .8);
          this.arc(69 + i * 3, 17 + i * 2, 2 + t * 6, 1 + t * 3, 0, TAU, c, fade * .32);
        }
        this.ship(14, 27, c, .8, .8);
      } else if (key === "galaxy_map" || key === "power_map") {
        const power = key === "power_map";
        for (let arm = 0; arm < 4; arm++) {
          const points = [];
          for (let i = 0; i <= 22; i++) {
            const r = 2 + i * 2.25, a = arm * Math.PI / 2 + i * .16 + .35;
            points.push([60 + Math.cos(a) * r, 18 + Math.sin(a) * r * .28]);
          }
          this.path(points, c, power ? .2 : .42);
          for (let i = 4; i < points.length; i += 4) {
            const [x, y] = points[i];
            this.dot(x, y, power ? 1.6 : 1, c, .3 + .5 * wave(p * .15 - i * .04 - arm * .2));
            if (power) this.angularRing(x, y, 6, 3, 6, c, .3);
          }
        }
        this.glowDot(60, 18, 2.1, c, .85);
        this.line(8, 32, 112, 32, c, .16);
      } else if (["map", "system_map", "orrery"].includes(key)) {
        const flat = key !== "orrery";
        this.glowDot(flat ? 14 : 55, 18, 2.8, c, .85);
        for (let i = 0; i < 4; i++) {
          if (flat) {
            const x = 38 + i * 23;
            this.line(i ? x - 23 : 18, 18, x - 4, 18, c, .22);
            this.globe(x, 18, 3 + i % 2, c, p * .4, .65);
            this.arc(x, 18, 7, 10, -Math.PI / 2, -Math.PI / 2 + TAU * .7, c, .2);
            this.dot(x + Math.cos(p * .32 + i) * 7, 18 + Math.sin(p * .32 + i) * 10, .9, c, .6);
          } else {
            const rx = 15 + i * 12, ry = 4 + i * 3, a = p * .28 / (i + 1) + i * 1.4;
            this.arc(55, 18, rx, ry, 0, TAU, c, .3);
            this.dot(55 + Math.cos(a) * rx, 18 + Math.sin(a) * ry, 1.8, c, .8);
          }
        }
      } else if (key === "codex") {
        this.path([[18, 6], [50, 9], [60, 13], [70, 9], [102, 6], [102, 29],
          [71, 28], [60, 32], [49, 28], [18, 29]], c, .6, 1, true, .06);
        this.line(60, 13, 60, 30, c, .4);
        for (let i = 0; i < 4; i++) for (const side of [-1, 1]) {
          this.line(60 + side * 14, 13 + i * 4, 60 + side * (34 - i % 2 * 7), 11 + i * 4,
            c, .22 + .4 * wave(p * .18 - i * .12));
        }
      } else if (key === "phenomena") {
        for (let i = 0; i < 3; i++) {
          const points = [];
          for (let j = 0; j <= 32; j++) {
            const t = j / 32 * TAU;
            points.push([60 + Math.cos(t) * (24 + i * 8),
              18 + Math.sin(t * 2 + p * .35 + i) * (5 + i * 3)]);
          }
          this.path(points, c, .3 + i * .15);
        }
        this.brackets(60, 18, 49, 15, c, .28);
      } else {
        // Exploration: a tilted holographic scanner dish, with soft echoes.
        this.arc(61, 22, 46, 10, 0, TAU, c, .48);
        this.arc(61, 22, 29, 6.3, 0, TAU, c, .23);
        this.line(15, 22, 107, 22, c, .18);
        const a = p * .38;
        this.path([[61, 22], [61 + Math.cos(a) * 46, 22 + Math.sin(a) * 10],
          [61 + Math.cos(a + .38) * 46, 22 + Math.sin(a + .38) * 10]], c, .4, 1, true, .12);
        for (let i = 0; i < 5; i++) {
          const x = 28 + hash(i + 2) * 63, y = 17 + hash(i + 8) * 9;
          this.line(x, y, x, y - 5 - hash(i) * 5, c, .3);
          this.dot(x, y - 5 - hash(i) * 5, 1.2, c, .3 + .4 * wave(p * .2 - i * .14));
        }
      }
    }

    drawSurfaceFlight(state, p, key) {
      const c = state.color, d = state.dynamics;
      const depart = key.includes("departure"), orbital = key.startsWith("orbital");
      if (orbital) {
        // Tangential orbital path; departure opens away from the planet limb.
        const altitude = d.altitude < 0 ? .5 : clamp(Math.log10(1 + d.altitude) / 7);
        const r = 39 - altitude * 8, cy = 49;
        this.globe(61, cy, r, c, p * .5, .65);
        this.arc(61, cy, r + 11, r + 11, Math.PI * 1.15, Math.PI * 1.85, c, .32);
        const points = depart ? [[34, 24], [52, 16], [73, 8], [103, 4]]
          : [[15, 5], [38, 9], [60, 16], [81, 27]];
        this.path(points, c, .65, 1.2);
        const t = fract(p * .15), fade = Math.sin(t * Math.PI), i = Math.min(2, Math.floor(t * 3));
        const f = t * 3 - i;
        this.glowDot(points[i][0] + (points[i + 1][0] - points[i][0]) * f,
          points[i][1] + (points[i + 1][1] - points[i][1]) * f, 1.4, c, fade * .9);
        return;
      }
      const hold = key === "surface_hold", landed = key === "landed", glide = key === "glide";
      const horizon = hold ? 16 : landed ? 11 : glide ? 8 : 12;
      // Projected terrain, not made-up terrain telemetry. Direction is a
      // state signature; density/pressure respond to available altitude/gravity.
      for (let i = -3; i <= 3; i++) this.line(60 + i * 6, horizon, 60 + i * 25, 35, c, .18);
      for (let i = 0; i < 5; i++) {
        const t = hold || landed ? (i + .6) / 5 : fract(state.terrainCycles * .16 + i / 5);
        const depth = (depart ? 1 - t : t) ** 2;
        const yy = horizon + depth * (35 - horizon);
        this.line(5, yy, 115, yy, c, (hold || landed ? .27 : Math.sin(t * Math.PI) * .38));
      }
      this.path([[4, horizon + 1], [23, horizon - 1], [38, horizon + 2],
        [62, horizon], [79, horizon - 2], [101, horizon + 1], [116, horizon]], c, .55);
      if (landed) {
        this.path([[37, 26], [48, 20], [76, 20], [87, 26], [76, 32], [48, 32]], c, .7, 1.2, true, .07);
        this.ship(62, 25, c, .85, 1.35);
        for (const x of [45, 79]) this.line(x, 27, x, 31, c, .8, 1.5);
        this.traceEdges([[37, 26], [48, 20], [76, 20], [87, 26], [76, 32], [48, 32]], p * .5, c);
      } else if (hold) {
        this.brackets(61, 17, 19, 8, c, .65);
        this.line(49, 17, 57, 17, c, .8); this.line(65, 17, 73, 17, c, .8);
        this.dot(61, 17, 1.4, c, .75);
        this.arc(61, 28, 16, 3, 0, TAU, c, .3);
        const stabilizer = p * TAU * .5;
        for (const offset of [0, Math.PI]) this.arc(61, 28, 16, 3,
          stabilizer + offset, stabilizer + offset + .9, c, .8, 1.6);
      } else if (glide) {
        for (let i = 0; i < 4; i++) {
          const t = fract(p * .18 + i / 4), fade = Math.sin(t * Math.PI);
          const w = 9 + t * t * 48, h = 2 + t * t * 15;
          this.path([[61 - w, 18 + h], [61 - w * .7, 18 - h],
            [61 + w * .7, 18 - h], [61 + w, 18 + h]], c, fade * .68, 1.1);
        }
        this.path([[48, 18], [57, 18], [61, 21], [65, 18], [74, 18]], c, .85, 1.4);
      } else {
        // Descent ladder and outward ascent vector have different silhouettes.
        const direction = depart ? -1 : 1;
        this.path([[48, 16], [57, 16], [61, 19], [65, 16], [74, 16]], c, .8, 1.2);
        for (let i = 0; i < 3; i++) {
          const t = fract(state.terrainCycles * .18 + i / 3), yy = 18 + direction * (2 + t * 12);
          this.path([[56, yy - direction * 2], [61, yy], [66, yy - direction * 2]],
            c, Math.sin(t * Math.PI) * .72, 1.1);
        }
      }
      if (d.gravity > 1.5) {
        const load = clamp((d.gravity - 1.5) / 3);
        for (const side of [-1, 1]) this.line(61 + side * (43 - load * 5), 10,
          61 + side * (43 - load * 5), 29, c, .3 + .3 * load, 1.6);
      }
    }

    drawVehicleInstrument(state, p, key) {
      const c = state.color;
      const type = key === "srv" ? "scarab" : ["rhino", "scorpion", "nomad"].includes(key) ? key
        : state.vehicleKey || "scarab";
      if (key === "on_foot") {
        // Suit's projected boot tracks / visor range fan, not another ship.
        this.arc(60, 31, 38, 22, Math.PI, TAU, c, .3);
        for (let i = 0; i < 4; i++) {
          const t = fract(p * .18 + i / 4), fade = Math.sin(t * Math.PI);
          const x = i % 2 ? 67 : 53, y = 31 - t * 26;
          this.path([[x - 2, y - 3], [x + 2, y - 3], [x + 3, y + 1],
            [x + 2, y + 4], [x - 2, y + 4]], c, fade * .75, 1, true, .18);
        }
        this.brackets(60, 18, 43, 14, c, .3);
        return;
      }
      if (key === "srv_turret") {
        this.arc(60, 27, 29, 18, Math.PI, TAU, c, .4);
        const a = -Math.PI / 2 + Math.sin(p * .4) * .45;
        this.path([[49, 30], [53, 24], [67, 24], [71, 30]], c, .7);
        this.line(60, 25, 60 + Math.cos(a) * 22, 25 + Math.sin(a) * 22, c, .85, 2);
        this.brackets(60 + Math.cos(a) * 22, 25 + Math.sin(a) * 22, 7, 4, c, .6);
        for (let i = 0; i < 9; i++) this.line(24 + i * 9, 33, 24 + i * 9, i % 2 ? 31 : 29, c, .3);
        return;
      }
      const brake = key === "srv_handbrake", assist = key === "srv_drive_assist";
      if (type === "nomad") {
        this.path([[32, 18], [41, 11], [79, 11], [88, 18], [78, 23], [42, 23]], c, .78, 1.2, true, .08);
        this.path([[43, 11], [52, 6], [69, 6], [78, 11]], c, .5);
        for (const x of [40, 80]) {
          this.arc(x, 22, 8, 2.5, 0, TAU, c, .65);
          for (let i = 0; i < 3; i++) {
            const t = fract(p * .3 + i / 3);
            this.arc(x, brake ? 29 : 25 + t * 8, brake ? 9 : 5 + t * 7, 1.7, 0, TAU, c,
              brake ? .16 : Math.sin(t * Math.PI) * .5);
          }
        }
      } else {
        // Suspension telemetry motif: Rhino's load-bearing chassis, Scarab's
        // articulated axles and Scorpion's protected turret are recognisable.
        const heavy = type === "rhino", armed = type === "scorpion";
        const wheels = heavy ? 4 : armed ? 2 : 3;
        const width = heavy ? 62 : armed ? 48 : 54;
        const x0 = 60 - width / 2, bob = brake ? 0 : Math.sin(p * .8) * .6;
        this.path([[x0, 17 + bob], [x0 + 9, 11 + bob], [x0 + width - 11, 11 + bob],
          [x0 + width, 17 + bob], [x0 + width - 5, 23], [x0 + 5, 23]], c, .78, 1.2, true, .06);
        if (heavy) {
          this.path([[44, 10], [44, 6], [72, 6], [80, 10]], c, .65);
          for (let i = 0; i < 4; i++) this.line(47 + i * 7, 8, 47 + i * 7, 17, c, .25);
        } else if (armed) {
          this.path([[50, 11], [52, 6], [64, 6], [69, 11]], c, .65);
          this.line(61, 7, 83, 7, c, .8, 1.8);
        } else this.path([[49, 11], [51, 6], [60, 4], [65, 11]], c, .6);
        for (let i = 0; i < wheels; i++) {
          const x = x0 + 5 + i * (width - 10) / (wheels - 1);
          const y = 26 + (brake ? 0 : Math.sin(p * .8 + i * 1.4) * .8);
          this.path([[x - 3, 20], [x + 2, 23], [x, y]], c, .4);
          this.arc(x, y, 4, 4, 0, TAU, c, .75, 1.15);
          if (!brake) this.line(x - 2, y + Math.sin(p * .8 + i) * 2,
            x + 2, y - Math.sin(p * .8 + i) * 2, c, .35);
        }
      }
      this.line(20, 33, 101, 33, c, .25);
      if (brake) {
        this.brackets(60, 20, 43, 12, c, .72);
        this.path([[10, 14], [6, 18], [10, 22]], c, .6);
        this.path([[110, 14], [114, 18], [110, 22]], c, .6);
        // Latched brake calipers breathe; wheels and chassis remain still.
        const latch = .2 + .65 * wave(p * .6);
        for (const x of [17, 103]) this.path([[x - 3, 10], [x, 13], [x, 27],
          [x - 3, 30]], c, latch, 1.8);
      } else if (assist) {
        for (const side of [-1, 1]) this.path([[60 + side * 47, 31], [60 + side * 40, 20],
          [60 + side * 40, 6]], c, .55);
      } else {
        for (let i = 0; i < 5; i++) {
          const t = fract(p * .16 + i / 5);
          this.line(18 + t * 83, 33, 21 + t * 83, 33, c, Math.sin(t * Math.PI) * .4, 1.5);
        }
      }
    }

    drawDockInstrument(state, p, key) {
      const c = state.color;
      const denied = key === "docking_denied", docking = key === "docking_assist" || key === "docking_clearance";
      if (["station", "docking_assist", "docking_clearance", "docking_denied"].includes(key)) {
        // Coriolis-style octagonal station frame and illuminated letterbox.
        this.angularRing(72, 18, 25, 16, 8, c, .65, 1.1, Math.PI / 8);
        this.angularRing(72, 18, 19, 12, 8, c, .26, 1, Math.PI / 8);
        this.rect(60, 14, 24, 8, c, .8);
        for (let i = 0; i < 5; i++) this.line(62 + i * 5, 15, 62 + i * 5, 17, c,
          .2 + .65 * Math.pow(wave(p * .5 - i / 5), 3), 1.4);
        if (denied) {
          const caution = .28 + .6 * wave(p * .26);
          this.line(64, 12, 80, 24, c, caution, 1.8); this.line(64, 24, 80, 12, c, caution, 1.8);
        } else if (docking) {
          for (let i = 0; i < 3; i++) {
            const t = fract(p * .2 + i / 3), x = 7 + t * 47;
            this.chevron(x, 18, 1, c, Math.sin(t * Math.PI) * .8, 3);
          }
          if (key === "docking_clearance") this.brackets(72, 18, 15, 7, c, .6);
        } else {
          // The old 88-second arc was mostly clipped and looked frozen.
          // A lit facet circuit stays inside the visible station silhouette.
          const facets = Array.from({length: 8}, (_, i) => {
            const a = Math.PI / 8 + i * TAU / 8;
            return [72 + Math.cos(a) * 25, 18 + Math.sin(a) * 16];
          });
          this.traceEdges(facets, p * .5, c, .88);
        }
      } else if (key === "surface_station" || key === "settlement_area") {
        this.path([[6, 31], [18, 29], [103, 29], [115, 31]], c, .3);
        for (let i = 0; i < 5; i++) {
          const x = 19 + i * 18, h = [8, 15, 20, 11, 7][i];
          this.path([[x, 29], [x, 29 - h], [x + 6, 26 - h], [x + 13, 29 - h], [x + 13, 29]], c, .6);
          this.line(x + 6, 26 - h, x + 6, 28, c, .22);
          this.dot(x + 6, 24 - h, 1, c, .3 + .5 * wave(p * .2 + i * .2));
          this.line(x + 2, 28, x + 11, 28, c,
            .12 + .65 * Math.pow(wave(p * .5 - i / 5), 3), 1.6);
        }
        if (key === "surface_station") this.arc(62, 29, 25, 5, 0, Math.PI, c, .6);
      } else {
        // Docked: pad clamps stay latched; no endless docking manoeuvre.
        this.path([[25, 24], [44, 8], [83, 8], [102, 24], [83, 32], [44, 32]], c, .65, 1.1, true, .06);
        this.path([[38, 24], [49, 14], [78, 14], [88, 24], [78, 28], [49, 28]], c, .32, 1, true);
        this.ship(63, 21, c, .85, 1.7);
        for (const x of [38, 88]) this.path([[x - 3, 23], [x, 20], [x + 3, 23]], c, .75, 1.6);
        this.traceEdges([[38, 24], [49, 14], [78, 14], [88, 24], [78, 28], [49, 28]], p * .55, c);
        for (let i = 0; i < 4; i++) this.rect(47 + i * 10, 32, 4, 1.4, c, .3 + .5 * wave(p * .55 + i / 4), true);
      }
    }

    drawCarrierInstrument(state, p, key) {
      const c = state.color, transit = key === "carrier_transit", arrival = key === "carrier_arrival";
      if (transit) {
        // Broad hyperspace wake around the capital-sized hull, not ship FSD.
        for (let i = 0; i < 4; i++) {
          const t = fract(p * .23 + i / 4);
          this.angularRing(62, 19, 19 + t * 46, 3 + t * 18, 8, c, Math.sin(t * Math.PI) * .4, 1.2);
        }
      } else if (arrival) {
        this.spaceLanes(p, c, {count: 10, speed: .2, strength: 1 - smooth(state.age / 2)});
        this.brackets(60, 18, 50, 14, c, .4);
      } else {
        this.path([[16, 29], [32, 10], [97, 10], [108, 29]], c, .24);
        this.line(6, 32, 115, 32, c, .22);
      }
      this.path([[14, 21], [26, 17], [42, 17], [45, 13], [91, 13], [105, 18],
        [105, 24], [32, 24]], c, .75, 1.2, true, .08);
      this.path([[71, 13], [73, 6], [80, 6], [85, 13]], c, .65);
      this.line(77, 6, 77, 3, c, .65);
      for (let i = 0; i < 6; i++) {
        this.path([[40 + i * 9, 18], [43 + i * 9, 16], [47 + i * 9, 18]], c, .35);
        const light = .18 + .7 * Math.pow(wave(p * .5 - i / 6), 3);
        this.line(40 + i * 9, 25, 46 + i * 9, 25, c, light, 1.5);
      }
    }

    drawHandoffInstrument(state, p, key) {
      const c = state.color, board = key.includes("board");
      const t = smooth(state.age / 2), progress = board ? 1 - t : t;
      const foot = key.endsWith("crew"), flyer = key.endsWith("fighter") || key.endsWith("ship");
      // An airlock / ramp transfer runs once, then waits for journal confirmation.
      this.path([[14, 30], [14, 6], [43, 6], [49, 12], [49, 30]], c, .58);
      const door = board ? (1 - t) * 13 : t * 13;
      this.line(47, 9, 47, 19 - door * .6, c, .6, 1.5);
      this.line(47, 21 + door * .6, 47, 30, c, .6, 1.5);
      this.path([[49, 29], [76, flyer ? 24 : 32], [112, flyer ? 24 : 32]], c, .4);
      const x = 29 + progress * 65, y = flyer ? 19 : 22;
      if (foot) {
        this.dot(x, y - 5, 2, c, .8);
        this.path([[x, y - 2], [x, y + 3], [x - 3, y + 7]], c, .75);
        this.line(x, y + 3, x + 3, y + 7, c, .75);
      } else if (flyer) this.ship(x, y, c, .9, 1.5, board ? -1 : 1);
      else {
        const size = key.endsWith("rhino") ? 11 : 8;
        this.path([[x - size, y], [x - size + 3, y - 5], [x + size - 3, y - 5], [x + size, y]], c, .8);
        for (const side of [-1, 1]) this.arc(x + side * (size - 3), y + 2, 2.7, 2.7, 0, TAU, c, .7);
        if (key.endsWith("nomad")) this.arc(x, y + 6, size, 1.5, 0, TAU, c, .5);
      }
      this.brackets(board ? 29 : 96, 20, 13, 11, c, .2 + .45 * t);
      // The transfer itself is one-shot; the airlock's confirmation circuit
      // stays alive while waiting for the journal's final vehicle state.
      for (let i = 0; i < 4; i++) this.line(16 + i * 7, 4, 20 + i * 7, 4, c,
        .14 + .65 * Math.pow(wave(p * .5 - i / 4), 3), 1.6);
    }

    drawContactInstrument(state, p, key) {
      const c = state.color;
      if (key === "target_lock") {
        const locked = smooth(state.age / 1.2);
        this.arc(61, 18, 10, 10, 0, TAU, c, .4);
        this.brackets(61, 18, 16 + (1 - locked) * 23, 13, c, .78);
        this.line(61, 3, 61, 7, c, .5); this.line(61, 29, 61, 33, c, .5);
        this.line(30, 18, 47, 18, c, .4); this.line(75, 18, 92, 18, c, .4);
        this.dot(61, 18, 1.3, c, .8);
        const track = p * TAU * .45;
        for (const offset of [0, Math.PI]) this.arc(61, 18, 10, 10,
          track + offset, track + offset + .65, c, .75, 1.5);
      } else if (key === "signal_lock" || key === "signal_drop") {
        const drop = key === "signal_drop";
        this.dot(70, 18, 2, c, .8);
        for (let i = 0; i < 4; i++) {
          const t = fract(p * .2 + i / 4), r = 5 + (drop ? 1 - t : t) * 20;
          this.arc(70, 18, r, r * .62, -.9, .9, c, Math.sin(t * Math.PI) * .55);
          this.arc(70, 18, r, r * .62, Math.PI - .9, Math.PI + .9, c, Math.sin(t * Math.PI) * .55);
        }
        if (drop) {
          this.path([[9, 8], [25, 8], [39, 18], [52, 18]], c, .65);
          this.chevron(49, 18, 1, c, .8, 3);
        } else this.brackets(70, 18, 31, 15, c, .3);
      } else if (key === "asteroid_field") {
        this.drawAsteroidField(state, p);
      } else if (key === "mass_lock") {
        this.angularRing(60, 18, 14, 11, 6, c, .55, 1.2);
        this.ship(60, 18, c, .8, 1.1);
        for (const side of [-1, 1]) {
          this.path([[60 + side * 33, 6], [60 + side * 24, 6], [60 + side * 19, 18],
            [60 + side * 24, 30], [60 + side * 33, 30]], c, .7, 1.6);
          for (let i = 0; i < 3; i++) this.line(60 + side * (33 + i * 7), 13,
            60 + side * (30 + i * 7), 23, c, .25 + .2 * wave(p * .3 - i / 3));
        }
      } else if (key === "interdiction" || key === "interdicted") {
        const lost = key === "interdicted", x = 62 + Math.sin(p * .5) * (lost ? 22 : 12);
        for (let i = 0; i < 4; i++) {
          const t = fract(p * .17 + i / 4);
          this.arc(60, 18, 8 + t * 58, 4 + t * 17, 0, TAU, c, Math.sin(t * Math.PI) * .25);
        }
        this.brackets(x, 18 + Math.cos(p * .5) * 5, 10, 8, c, .8);
        this.path([[46, 18], [56, 18], [60, 21], [64, 18], [74, 18]], c, .85, 1.4);
        if (lost) { this.line(10, 5, 25, 30, c, .6); this.line(110, 5, 95, 30, c, .6); }
      } else if (key === "capital_contact") {
        this.drawCarrierInstrument(state, p, "carrier_deck");
        this.brackets(60, 18, 54, 15, c, .65);
      } else {
        const combat = ["combat", "heavy_combat", "srv_threat"].includes(key);
        const threat = combat || key === "signal_threat", drop = key === "signal_drop";
        this.arc(60, 22, 45, 10, 0, TAU, c, .3);
        this.arc(60, 22, 22, 5, 0, TAU, c, .2);
        const x = 62 + Math.sin(p * .18) * (combat ? 18 : 2), y = 14 + Math.cos(p * .2) * 2;
        this.line(x, 23, x, y, c, .4);
        if (key === "unknown_contact") {
          this.angularRing(x, y, 5, 5, 6, c, .6);
          this.arc(x, y, 10, 8, p * .5, p * .5 + Math.PI, c, .4);
        } else {
          this.path([[x, y - 4], [x + 4, y + 3], [x - 4, y + 3]], c, .8, 1.1, true, .13);
          this.brackets(x, y, 10 + (drop ? 4 * wave(p * .2) : 0), 8, c, .6);
        }
        if (threat) for (let i = 0; i < (key === "heavy_combat" ? 4 : 2); i++) {
          const t = fract(p * .2 + i / 4), fade = Math.sin(t * Math.PI);
          this.line(11 + t * 24, 30 - t * 9, 16 + t * 24, 28 - t * 9, c, fade * .65, 1.3);
        }
      }
    }

    drawCockpitInstrument(state, p, key) {
      const c = state.color;
      if (["left_panel", "right_panel", "role_panel", "station_services", "comms_panel"].includes(key)) {
        if (key === "comms_panel") {
          this.path([[15, 10], [30, 10], [30, 22], [21, 22], [16, 27], [16, 22], [12, 22], [12, 10]], c, .6);
          for (let i = 0; i < 21; i++) {
            const amp = 2 + 10 * wave(p * .25 - i * .12) * Math.sin(i / 20 * Math.PI);
            this.line(39 + i * 3.5, 18 - amp, 39 + i * 3.5, 18 + amp, c, .4 + .25 * wave(p * .2 - i * .1));
          }
        } else if (key === "role_panel") {
          for (let i = 0; i < 3; i++) {
            const x = 30 + i * 30;
            this.dot(x, 12, 3.2, c, .7);
            this.path([[x - 7, 26], [x - 6, 20], [x, 17], [x + 6, 20], [x + 7, 26]], c, .55);
          }
          this.brackets(60, 18, 13, 13, c, .25 + .6 * wave(p * .5));
          for (const side of [-1, 1]) {
            const t = fract(p * .4 + (side < 0 ? 0 : .5));
            this.line(60 + side * (13 + t * 9), 31, 60 + side * (17 + t * 9), 31,
              c, Math.sin(t * Math.PI) * .75, 1.5);
          }
        } else if (key === "station_services") {
          for (let i = 0; i < 4; i++) {
            const x = 25 + i * 24;
            this.angularRing(x, 18, 8, 8, 6, c, .35 + .3 * wave(p * .16 - i / 4), 1.1, Math.PI / 6);
            this.line(x - 3, 18, x + 3, 18, c, .6);
            if (i % 2) this.line(x, 15, x, 21, c, .6);
          }
        } else {
          const left = key === "left_panel";
          this.path(left ? [[18, 7], [100, 3], [100, 32], [18, 27]]
            : [[20, 3], [102, 7], [102, 27], [20, 32]], c, .55, 1, true, .04);
          if (left) {
            for (let i = 0; i < 4; i++) {
              const x = 29 + i * 18, y = 17 + Math.sin(i * 1.7) * 6;
              this.angularRing(x, y, 2.5, 2.5, 4, c, .75);
              if (i < 3) this.line(x + 3, y, x + 15, 17 + Math.sin((i + 1) * 1.7) * 6, c, .3);
              this.arc(x, y, 5.5, 5.5, 0, TAU, c,
                .7 * Math.pow(wave(p * .45 - i / 4), 4), 1.3);
            }
          } else {
            for (let i = 0; i < 4; i++) {
              this.rect(31, 9 + i * 5, 5, 2, c, .4, true);
              this.line(41, 10 + i * 5, 82 - i * 4, 10 + i * 5, c, .28 + .3 * wave(p * .2 - i * .2));
            }
          }
        }
        return;
      }
      if (key === "maintenance" || key === "system_reboot") {
        const reboot = key === "system_reboot";
        for (let i = 0; i < 6; i++) {
          const x = 15 + i * 18, activity = .25 + .45 * wave(p * .2 - i / 6);
          this.rect(x - 5, 12, 10, 12, c, activity);
          this.line(x + 5, 18, x + 13, 18, c, .25);
          if (reboot) {
            this.line(x - 2, 18, x + 2, 18, c, activity, 1.7);
          } else {
            this.line(x, 15, x, 21, c, activity, 1.5); this.line(x - 3, 18, x + 3, 18, c, activity, 1.5);
          }
        }
        if (reboot) {
          const t = fract(p * .18), x = 5 + t * 110;
          this.line(x, 6, x, 30, c, Math.sin(t * Math.PI) * .6);
        }
        return;
      }
      if (["heat_critical", "suit_hazard", "jet_cone_damage"].includes(key)) {
        if (key === "jet_cone_damage") {
          for (let i = 0; i < 4; i++) {
            const points = [];
            for (let j = 0; j <= 24; j++) points.push([6 + j * 4.5,
              18 + (i - 1.5) * 5 + Math.sin(j * .45 - p + i) * 4]);
            this.path(points, c, .25 + i * .13);
          }
          this.brackets(60, 18, 13, 11, c, .8);
        } else if (key === "suit_hazard") {
          this.path([[48, 29], [43, 22], [43, 12], [49, 5], [69, 5], [76, 12], [76, 22], [71, 29]], c, .72);
          this.path([[47, 14], [71, 14], [70, 21], [48, 21]], c, .5, 1, true, .08);
          for (const x of [33, 85]) this.path([[x, 10], [x, 22], [x + 2, 26]], c, .4 + .3 * wave(p * .3), 1.5);
        } else {
          this.path([[47, 30], [47, 9], [51, 4], [69, 4], [73, 9], [73, 30]], c, .65);
          for (let i = 0; i < 6; i++) this.line(51, 28 - i * 3.5, 69, 28 - i * 3.5, c, .3 + .5 * wave(p * .25 - i * .1), 1.8);
          for (const side of [-1, 1]) {
            const pts = [];
            for (let j = 0; j <= 12; j++) pts.push([60 + side * (26 + Math.sin(j * .5 - p * .6) * 2), 30 - j * 2]);
            this.path(pts, c, .45);
          }
        }
        return;
      }
      const faOff = key === "flight_assist_off", silent = key === "silent_running";
      const fighter = key === "fighter", crew = key === "multicrew";
      // Flight: holographic attitude gimbal. FA-off shows a detached inertia
      // vector; silent running shutters the thermal shell around the ship.
      this.arc(60, 20, 30, 10, 0, TAU, c, .42);
      this.arc(60, 20, 12, 15, 0, TAU, c, .28);
      this.path(fighter ? [[41, 24], [54, 20], [60, 11], [66, 20], [79, 24], [60, 22]]
        : [[47, 23], [60, 12], [73, 23], [60, 20]], c, .8, 1.15, true, .1);
      if (faOff) {
        const x = 60 + Math.sin(p * .35) * 43, y = 20 + Math.cos(p * .35) * 11;
        this.line(60, 20, x, y, c, .4); this.brackets(x, y, 4, 3, c, .75);
      } else if (silent) {
        const seal = .25 + .55 * wave(p * .55);
        for (const side of [-1, 1]) this.path([[60 + side * 25, 5], [60 + side * 19, 10],
          [60 + side * 19, 28], [60 + side * 25, 32]], c, seal, 1.6);
        this.line(44, 32, 76, 32, c, .25 + .35 * wave(p * .55));
      } else if (crew) {
        for (const side of [-1, 1]) {
          this.angularRing(60 + side * 45, 18, 6, 6, 6, c, .6);
          this.line(60 + side * 31, 20, 60 + side * 39, 18, c, .35);
          this.angularRing(60 + side * 45, 18, 8, 8, 6, c,
            .2 + .55 * wave(p * .5 + (side < 0 ? 0 : .5)), 1.3);
        }
      } else {
        const a = p * TAU * (fighter ? .18 : .25);
        this.arc(60, 20, 30, 10, a - .65, a, c, .65, 1.3);
        this.dot(60 + Math.cos(a) * 30, 20 + Math.sin(a) * 10, 1.4, c, .8);
        if (fighter) this.brackets(60, 19, 45, 13, c, .55);
      }
    }

    drawStatusModifiers(g, state, p, alpha) {
      const d = state.dynamics || {};
      const c = state.color;
      const orange = this.themeColor("orange", "#ff7a18");
      const green = this.themeColor("green", "#4ee59b");
      if (d.inMainShip && d.hardpoints) {
        this.chevron(g.left + 8, g.y - 9, -1, orange, alpha * .72, 2.4);
        this.chevron(g.right - 8, g.y - 9, 1, orange, alpha * .72, 2.4);
      }
      if (d.inMainShip && d.cargoScoop) {
        const spread = 6 + 2 * wave(p);
        this.path([[g.center - spread, g.y + 7], [g.center, g.y + 11],
          [g.center + spread, g.y + 7]], c, alpha * .52, 1.1);
      }
      if (d.inMainShip && d.shieldsKnown && !d.shieldsUp) {
        this.arc(g.right - 8, g.y, 5, 7, Math.PI * .6, Math.PI * 1.35,
          orange, alpha * .62, 1.2);
        this.arc(g.right - 8, g.y, 5, 7, Math.PI * 1.55, Math.PI * 2.25,
          orange, alpha * .62, 1.2);
      }
      if (d.nightVision) {
        const scan = g.left + ((p + .2) % 1) * Math.max(1, g.right - g.left);
        this.line(scan, g.y - 10, scan, g.y + 10, green, alpha * .28, 1);
      }
      if (d.analysisMode) {
        this.path([[g.left + 2, g.y - 6], [g.left + 2, g.y - 10], [g.left + 7, g.y - 10]],
          c, alpha * .42, 1);
        this.path([[g.right - 2, g.y + 6], [g.right - 2, g.y + 10], [g.right - 7, g.y + 10]],
          c, alpha * .42, 1);
      }
      if (d.inMainShip && d.lowFuel) {
        const flash = .35 + .45 * wave(p * 2);
        this.path([[g.left + 3, g.y + 10], [g.left + 7, g.y + 5],
          [g.left + 11, g.y + 10]], orange, alpha * flash, 1.2);
      }
      if (d.inMainShip && d.fsdInjection) {
        const tier = d.fsdInjectionPercent >= 100 ? 3 : d.fsdInjectionPercent >= 50 ? 2 : 1;
        const breathe = .35 + .35 * wave(p);
        for (const side of [-1, 1]) {
          const origin = side < 0 ? g.centerLeft - 7 : g.centerRight + 7;
          for (let index = 0; index < tier; index += 1) {
            const x = origin + side * index * 5;
            this.line(x, g.y - 9, x + side * 3, g.y - 6,
              c, alpha * breathe, 1.15);
          }
        }
      }
    }

    drawFuelPulse(g, state, p, alpha) {
      const d = state.dynamics || {};
      if (!d.inMainShip || !d.fuelScooping) return;
      const green = this.themeColor("green", "#4ee59b");
      const beat = wave(p);
      const baseAlpha = alpha * (.08 + beat * .08);

      // Fuel intake breathes along the chassis rails without adding another
      // label or competing with the live FUEL readout below the instrument.
      this.line(g.left + 5, g.bottom - 1, g.centerLeft - 5, g.bottom - 1,
        green, baseAlpha, 1.15);
      this.line(g.centerRight + 5, g.bottom - 1, g.right - 5, g.bottom - 1,
        green, baseAlpha, 1.15);

      if (this.reduced) return;
      for (const offset of [0, .5]) {
        const local = (p + offset) % 1;
        const envelope = Math.sin(local * Math.PI);
        const leftX = g.left + 7 + local * Math.max(1, g.centerLeft - g.left - 14);
        const rightX = g.right - 7 - local * Math.max(1, g.right - g.centerRight - 14);
        const packetAlpha = alpha * envelope * .34;
        this.line(Math.max(g.left + 5, leftX - 7), g.bottom - 1,
          leftX, g.bottom - 1, green, packetAlpha * .62, 1.2);
        this.line(Math.min(g.right - 5, rightX + 7), g.bottom - 1,
          rightX, g.bottom - 1, green, packetAlpha * .62, 1.2);
        this.glowDot(leftX, g.bottom - 1, .65 + beat * .35, green, packetAlpha);
        this.glowDot(rightX, g.bottom - 1, .65 + beat * .35, green, packetAlpha);
      }
    }

    drawState(g, state, p, alpha) {
      if (alpha <= .002) return;
      const key = this.key(state);
      this.instrument(g, alpha, () => {
        if (["supercruise", "supercruise_overcharge", "supercruise_assist", "fsd_charge",
          "hyper_charge", "hyperspace", "jumping", "arrival", "interdiction_evaded",
          "local_arrival", "fsd_cooldown", "fsd_injection"].includes(key)) {
          this.drawDrive(state, p, key);
        } else if (["fss", "dss", "map", "galaxy_map", "system_map", "orrery",
          "power_map", "codex", "exploration", "phenomena"].includes(key)) {
          this.drawSurveyInstrument(state, p, key);
        } else if (PLANETARY.has(key) || key === "landed") {
          this.drawSurfaceFlight(state, p, key);
        } else if (["srv", "scorpion", "rhino", "nomad", "srv_handbrake",
          "srv_turret", "srv_drive_assist", "on_foot"].includes(key)) {
          this.drawVehicleInstrument(state, p, key);
        } else if (["docked", "station", "surface_station", "settlement_area",
          "docking_clearance", "docking_denied", "docking_assist"].includes(key)) {
          this.drawDockInstrument(state, p, key);
        } else if (key.startsWith("carrier_")) {
          this.drawCarrierInstrument(state, p, key);
        } else if (key.startsWith("vehicle_")) {
          this.drawHandoffInstrument(state, p, key);
        } else if (["asteroid_field", "mass_lock", "signal_lock", "signal_drop",
          "signal_threat", "combat", "heavy_combat", "srv_threat", "unknown_contact",
          "capital_contact", "interdiction", "interdicted", "target_lock"].includes(key)) {
          this.drawContactInstrument(state, p, key);
        } else {
          this.drawCockpitInstrument(state, p, key);
        }
      });
    }

    eventColor(kind, fallback) {
      if (WARNING_EVENTS.has(kind) || kind === "dock_denied") return this.themeColor("orange", "#ff7a18");
      if (["survey_complete", "mapping_complete", "dss_efficiency", "bio_sample", "data_sale", "touchdown",
        "mining_refined", "interdiction_clear"].includes(kind)) return this.themeColor("green", "#4ee59b");
      if (RESOURCE_EVENTS.has(kind) || kind === "signals" || kind === "codex") return this.themeColor("yellow", "#ffd166");
      return fallback;
    }

    drawGearPulse(g, now) {
      if (!this.gearPulseStarted) return;
      const elapsed = (now - this.gearPulseStarted) / 1000;
      if (elapsed < 0 || elapsed > 1.08) {
        this.gearPulseStarted = 0;
        return;
      }
      const travel = smooth(clamp(elapsed / .58));
      const deployment = this.gearPulseDown ? travel : 1 - travel;
      const fadeIn = smooth(clamp(elapsed / .14));
      const fadeOut = 1 - smooth(clamp((elapsed - .64) / .44));
      const alpha = fadeIn * fadeOut;
      const c = this.gearPulseDown
        ? this.themeColor("green", "#4ee59b")
        : this.themeColor("accent", "#00d1ff");
      const cx = g.center, y = g.y;
      const spread = 4 + deployment * Math.min(15, (g.right - g.left) * .17);
      const footY = y - 1 + deployment * 9;

      // Two mechanical struts deploy/retract around a restrained acquisition
      // pulse. It is intentionally short: useful confirmation without
      // becoming another persistent flight-state animation.
      for (const side of [-1, 1]) {
        const rootX = cx + side * 4;
        const footX = cx + side * spread;
        this.line(rootX, y - 6, footX, footY, c, alpha * .9, 1.5);
        this.line(footX - side * 3.5, footY, footX + side * 2, footY,
          c, alpha * (.42 + deployment * .48), 1.35);
        this.dot(footX, footY, 1, c, alpha * .82);
      }
      const pulse = clamp(elapsed / .78);
      this.angularRing(cx, y, 6 + pulse * Math.min(27, (g.right - g.left) * .28),
        2.5 + pulse * 7, 6, c, alpha * (1 - pulse) * .72, 1.2, Math.PI / 6);
      this.line(cx - 5, y, cx + 5, y, c, alpha * .6, 1.2);
    }

    themeColor(name, fallback) {
      if (typeof document === "undefined" || typeof getComputedStyle !== "function") return fallback;
      if (!this.themeColors[name]) {
        const value = getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
        this.themeColors[name] = /^#[0-9a-f]{6}$/i.test(value) ? value : fallback;
      }
      return this.themeColors[name];
    }

    drawEvent(g, now) {
      if (!this.eventStarted || !this.eventKind) return;
      const elapsed = (now - this.eventStarted) / 1000;
      if (elapsed < 0 || elapsed > 1.15) return;
      const p = smooth(elapsed / 1.15);
      const fade = 1 - smooth(clamp((elapsed - .62) / .53));
      const c = this.eventColor(this.eventKind, this.state.color);
      const y = g.y;
      if (ROUTE_EVENTS.has(this.eventKind)) {
        this.trackStroke(p, .16, g, y - 7, c, fade, 1.8);
        for (const progress of [.16, .38, .62, .84]) {
          const point = this.trackPoint(progress, g, y - 7);
          this.dot(point.x, point.y, 1.1, c, fade * .62);
        }
      } else if (TARGET_EVENTS.has(this.eventKind)) {
        const clearing = this.eventKind === "target_clear";
        const spread = clearing ? 7 + p * 30 : 35 - p * 28;
        for (const side of [-1, 1]) {
          const x = g.center + side * spread;
          this.path([[x + side * 5, y - 7], [x, y - 7], [x, y - 2]],
            c, fade * .9, 1.35);
          this.path([[x + side * 5, y + 7], [x, y + 7], [x, y + 2]],
            c, fade * .9, 1.35);
        }
        if (!clearing) this.glowDot(g.center, y, 1.2 + wave(p) * 1.1, c, fade * .85);
      } else if (this.eventKind === "dss_efficiency" || this.eventKind === "dss_complete") {
        const rings = this.eventKind === "dss_efficiency" ? 3 : 2;
        for (let index = 0; index < rings; index += 1) {
          const radius = 5 + ((p + index / rings) % 1) * 27;
          this.arc(g.center, y, radius, radius * .34, 0, TAU,
            c, fade * (.65 - index * .13), 1.25);
        }
        this.line(g.center - 5, y, g.center + 5, y, c, fade * .85, 1.3);
      } else if (this.eventKind === "fsd_injection") {
        for (const side of [-1, 1]) {
          for (let index = 0; index < 3; index += 1) {
            const x = g.center + side * (8 + index * 8 + p * 3);
            this.chevron(x, y, -side, c, fade * (.85 - index * .16), 1.5);
          }
        }
      } else if (SCAN_EVENTS.has(this.eventKind)) {
        const sweep = this.trackPoint(p, g);
        this.line(sweep.x, y - 12, sweep.x, y + 12, c, fade * .92, 1.8);
        for (let i = 0; i < 3; i += 1) {
          const radius = 4 + (p + i * .14) * 17;
          this.arc(sweep.x, y, radius, radius * .34, 0, TAU, c, fade * (.55 - i * .12));
        }
      } else if (RESOURCE_EVENTS.has(this.eventKind)) {
        const point = this.trackPoint(p, g);
        this.path([
          [point.x - 5, y], [point.x - 2, y - 5], [point.x + 4, y - 3],
          [point.x + 6, y + 2], [point.x, y + 6], [point.x - 5, y],
        ], c, fade, 1.4);
        this.trackStroke(p, .1, g, y, c, fade * .72);
      } else if (DOCK_EVENTS.has(this.eventKind)) {
        const opening = this.eventKind === "undock" ? p : 1 - p;
        const spread = 7 + opening * 27;
        this.line(g.center - spread, y - 10, g.center - spread, y + 10, c, fade, 1.5);
        this.line(g.center + spread, y - 10, g.center + spread, y + 10, c, fade, 1.5);
      } else if (SURFACE_EVENTS.has(this.eventKind)) {
        const outbound = this.eventKind === "liftoff" || this.eventKind === "planet_clear";
        const travel = outbound ? p : 1 - p;
        const spread = 5 + travel * Math.max(10, (g.right - g.left) * .34);
        this.arc(g.center, y + 10, Math.max(15, (g.right - g.left) * .38), 10,
          Math.PI * 1.08, Math.PI * 1.92, c, fade * .58, 1.2);
        this.path([[g.center - spread - 5, y - 8], [g.center - spread, y - 8],
          [g.center - spread, y - 2]], c, fade * .88, 1.5);
        this.path([[g.center + spread + 5, y + 8], [g.center + spread, y + 8],
          [g.center + spread, y + 2]], c, fade * .88, 1.5);
        const markerY = outbound ? y + 5 - p * 12 : y - 7 + p * 12;
        this.path(outbound
          ? [[g.center - 4, markerY + 2], [g.center, markerY - 2], [g.center + 4, markerY + 2]]
          : [[g.center - 4, markerY - 2], [g.center, markerY + 2], [g.center + 4, markerY - 2]],
        c, fade, 1.5);
      } else if (MAINTENANCE_EVENTS.has(this.eventKind)) {
        const columns = 5;
        for (let index = 0; index < columns; index += 1) {
          const x = g.left + 3 + index * Math.max(8, (g.right - g.left - 8) / columns);
          const active = index <= Math.floor(p * columns);
          this.rect(x, y - 5, 6, 10, c, fade * (active ? .72 : .2), active);
        }
      } else if (WARNING_EVENTS.has(this.eventKind)) {
        const flash = .35 + .65 * wave(elapsed * 3.2);
        this.line(g.left, g.top, g.centerLeft, g.top, c, fade * flash, 2);
        this.line(g.centerRight, g.top, g.right, g.top, c, fade * flash, 2);
        this.line(g.left, g.bottom, g.centerLeft, g.bottom, c, fade * flash, 2);
        this.line(g.centerRight, g.bottom, g.right, g.bottom, c, fade * flash, 2);
      } else {
        this.trackStroke(p, .18, g, y, c, fade, 2);
      }
    }

    drawTransition(g, progress, from, to) {
      const p = smooth(progress);
      const fade = Math.sin(p * Math.PI);
      const fsd = this.family(from) === "fsd" && this.family(to) === "fsd";
      // Couple both bays along their lower edge without crossing the label.
      const span = g.right - g.left;
      const x = g.left + p * span;
      this.line(Math.max(g.left, x - 18), g.bottom - 1, x, g.bottom - 1,
        to.color, fade * (fsd ? .52 : .32), 1.2);
    }

    draw(now) {
      const ctx = this.ctx, ratio = this.ratio || 1;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.clearRect(0, 0, this.width, this.height);
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      const g = this.geometry();
      const response = this.responseGeometry(g);
      this.chassis(g, this.state.color);
      if (!this.reduced && this.previous && this.transitionStarted) {
        const progress = clamp((now - this.transitionStarted) / this.transitionDuration);
        const mix = smooth(progress);
        if (this.transitionImage) {
          ctx.save();
          ctx.globalAlpha = 1 - mix;
          ctx.drawImage(this.transitionImage, 0, 0, this.width, this.height);
          ctx.restore();
        } else {
          this.drawIdentity(g, this.previous, this.phase(this.previous, now), 1 - mix);
          this.drawState(response, this.previous, this.phase(this.previous, now), 1 - mix);
        }
        this.drawIdentity(g, this.state, this.phase(this.state, now), mix);
        this.drawState(response, this.state, this.phase(this.state, now), mix);
        this.drawTransition(g, progress, this.previous, this.state);
        if (progress >= 1) {
          this.previous = null;
          this.transitionImage = null;
        }
      } else {
        const phase = this.phase(this.state, now);
        this.drawIdentity(g, this.state, phase, 1);
        this.drawState(response, this.state, phase, 1);
      }
      const livePhase = this.phase(this.state, now);
      this.drawFuelPulse(g, this.state, livePhase, 1);
      this.drawStatusModifiers(response, this.state, livePhase, 1);
      if (!this.reduced) {
        this.drawEvent(response, now);
        this.drawGearPulse(response, now);
      }
    }

    frame(now) {
      if (!this.running) return;
      this.advanceClock(now);
      const interval = this.reduced ? 180 : FRAME_MS;
      const elapsed = now - this.lastFrame;
      if (elapsed >= interval - .1 && this.visible && !document.hidden) {
        // Preserve the remainder to avoid irregular 20 FPS on 60 Hz displays.
        this.lastFrame += Math.floor((elapsed + .1) / interval) * interval;
        this.draw(now);
      }
      requestAnimationFrame(this.frameCallback);
    }
  }

  window.NavigationIndicator = NavigationIndicator;
})();
