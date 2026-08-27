(() => {
  "use strict";

  /*
   * Navigation State Spine
   * ----------------------
   * One continuous instrument owns the complete upper rail.  Each flight
   * state contributes a single visual signature; journal events are a short,
   * bounded response laid over it.  Nothing persists between frames, which
   * keeps transitions clean and prevents old state geometry leaking through.
   */

  const TAU = Math.PI * 2;
  const FRAME_MS = 1000 / 30;
  const clamp = (value, low = 0, high = 1) => Math.max(low, Math.min(high, value));
  const smooth = (value) => {
    const t = clamp(value);
    return t * t * (3 - 2 * t);
  };
  const wave = (value) => .5 - .5 * Math.cos(value * TAU);
  const triangle = (value) => 1 - Math.abs(((value % 1) + 1) % 1 * 2 - 1);
  const hash = (value) => {
    const x = Math.sin(value * 91.731 + 17.17) * 43758.5453;
    return x - Math.floor(x);
  };

  const PLANETARY = new Set([
    "orbital_approach", "glide", "surface_approach", "surface_hold",
    "surface_departure", "orbital_departure",
  ]);
  const ROUTE_EVENTS = new Set(["route_set", "route_clear", "route_target", "route_divert"]);
  const SCAN_EVENTS = new Set([
    "honk", "fss_progress", "fss_signal", "body_scan", "signals",
    "survey_complete", "mapping_complete", "bio_sample", "codex",
    "valuable_discovery", "first_discovery", "footfall_candidate", "data_sale",
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
      this.running = true;
      this.resizeObserver = new ResizeObserver(() => this.resize());
      this.resizeObserver.observe(canvas);
      this.resize();
      requestAnimationFrame((time) => this.frame(time));
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
        startedAt: performance.now(),
      };
    }

    normaliseDynamics(raw = {}) {
      const source = raw && typeof raw === "object" ? raw : {};
      const number = (value, fallback, low, high) => {
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
        neutronBoost: Boolean(source.neutron_boost),
        neutronBoostValue: number(source.neutron_boost_value, 0, 0, 10),
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
      }
      this.ratio = ratio;
    }

    update(next = {}) {
      const now = performance.now();
      const incoming = this.makeState(next);
      if (this.receivedModel
          && incoming.dynamics.landingGear !== this.state.dynamics.landingGear) {
        this.gearPulseStarted = now;
        this.gearPulseDown = incoming.dynamics.landingGear;
      }
      if (!this.receivedModel) {
        this.state = incoming;
        this.stateStarted = now;
        this.receivedModel = true;
      } else if (incoming.motion !== this.state.motion || incoming.label !== this.state.label
          || incoming.vehicleKey !== this.state.vehicleKey
          || this.boostTier(incoming) !== this.boostTier(this.state)) {
        this.previous = {...this.state};
        this.state = incoming;
        this.stateStarted = now;
        this.transitionStarted = now;
        this.transitionDuration = this.transitionMs(this.previous, incoming);
      } else {
        incoming.startedAt = this.state.startedAt;
        this.state = incoming;
      }
      this.reduced = Boolean(next.reduced);
      if (next.eventSequence != null && next.eventSequence !== this.eventSequence) {
        this.eventSequence = next.eventSequence;
        this.eventKind = String(next.eventKind || "");
        this.eventStarted = now;
      }
      this.draw(now);
    }

    key(state) {
      const motion = String(state?.motion || "flight");
      const label = String(state?.label || "FLIGHT").toUpperCase();
      if (motion === "scanner") return label === "DSS" ? "dss" : "fss";
      if (motion === "map") return ({
        "GALAXY MAP": "galaxy_map", "SYSTEM MAP": "system_map",
        "POWER MAP": "power_map", ORRERY: "orrery", CODEX: "codex",
      })[label] || "map";
      if (motion === "surface_vehicle") {
        if (label === "NOMAD" || state?.vehicleKey === "nomad") return "nomad";
        if (state?.vehicleKey === "scorpion") return "scorpion";
        return "srv";
      }
      if (motion === "fsd_charge") return label === "HYPER CHARGE" ? "hyper_charge" : "fsd_charge";
      if (motion === "jump") return label === "JUMPING" ? "jumping" : "hyperspace";
      if (motion === "arrival" && label === "INTERDICTION EVADED") return "interdiction_evaded";
      if (motion === "fsd_lock") {
        if (label === "MASS LOCK") return "mass_lock";
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
              : label.includes("SRV") || label.includes("SCARAB") || state?.vehicleKey === "scarab" ? "srv"
              : label.includes("CREW") ? "crew" : "ship";
        return `${motion}_${vehicle}`;
      }
      if (motion === "flight" && label === "MULTICREW") return "multicrew";
      if (motion === "flight" && label === "EXPLORATION") return "exploration";
      if (motion === "docked" && label === "STATION") return "station";
      return motion;
    }

    family(state) {
      const key = this.key(state);
      if (["fsd_charge", "hyper_charge", "hyperspace", "jumping", "arrival",
        "interdiction_evaded", "fsd_cooldown", "supercruise_overcharge",
        "supercruise_assist", "local_arrival"].includes(key)) return "fsd";
      if (PLANETARY.has(key) || ["landed", "srv", "scorpion", "nomad", "on_foot",
        "srv_handbrake", "srv_turret", "srv_drive_assist"].includes(key)) return "surface";
      if (["fss", "dss", "map", "galaxy_map", "system_map", "power_map",
        "orrery", "codex", "exploration", "phenomena"].includes(key)) return "scope";
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
        local_arrival: 1.42,
        carrier_transit: 1.08, carrier_arrival: 1.34,
        fss: 1.52, dss: 1.82, map: 2.1, galaxy_map: 2.35,
        system_map: 1.86, power_map: 1.7, orrery: 2.5, codex: 1.9,
        phenomena: 2.6, docking_assist: 1.34, settlement_area: 1.95,
        srv_threat: .72, capital_contact: 1.48, unknown_contact: 1.72,
        heavy_combat: .56,
        left_panel: 1.62, right_panel: 1.62, comms_panel: 1.34,
        role_panel: 1.78, station_services: 2.05,
        orbital_approach: 1.68, glide: .82, surface_approach: 1.38,
        surface_hold: 2.25, surface_departure: 1.28, orbital_departure: 1.55,
        landed: 2.4, on_foot: 1.32, srv: 1.18, scorpion: .9, nomad: 1.05,
        srv_handbrake: 1.8, srv_turret: 1.2, srv_drive_assist: 1.35,
        asteroid_field: 2.2, mass_lock: 1.12, signal_lock: 1.55,
        signal_drop: .92, signal_threat: .76, combat: .64,
        interdiction: .5, interdicted: .43, docked: 2.3, station: 2.1,
        heat_critical: .58, suit_hazard: .72, jet_cone_damage: .46,
        docking_clearance: 1.42, docking_denied: .68,
        maintenance: 1.7, system_reboot: .92,
      })[key] || 1.45;
    }

    phase(state, now) {
      if (this.reduced) return .18;
      const seconds = Math.max(0, now - (state.startedAt || this.stateStarted)) / 1000;
      return (seconds * state.energy / this.period(state)) % 1;
    }

    geometry() {
      const width = Math.max(1, this.canvas.clientWidth);
      const height = Math.max(1, this.canvas.clientHeight);
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
        // The response bay keeps a tiny central discontinuity so directional
        // packets still read as data crossing an instrument, not a progress bar.
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
      const y = g.y;
      this.path([[g.left, y + 9], [g.centerLeft - 12, y + 9], [g.centerLeft, y + 3]], color, .26, 1);
      this.path([[g.centerRight, y - 5], [g.centerRight + 10, y], [g.right, y]], color, .32, 1);
      this.line(g.left, y - 9, g.left + 13, y - 9, color, .38);
      this.line(g.right - 13, y - 9, g.right, y - 9, color, .38);
      this.line(g.left, y - 9, g.left, y + 9, color, .5);
      this.line(g.right, y - 9, g.right, y + 9, color, .5);
      this.line(g.centerLeft - 5, y + 9, g.centerLeft, y + 4, color, .38);
      this.line(g.centerRight, y - 5, g.centerRight + 5, y, color, .38);
      this.line(g.centerRight + 12, y + 10, g.right - 8, y + 10, color, .18);
    }

    drawIdentity(g, state, p, alpha) {
      const c = state.color, y = g.y;
      const key = this.key(state), family = this.family(state);
      const start = g.left + 7, end = g.centerLeft - 8;
      const span = Math.max(18, end - start);
      const point = (progress) => start + ((progress % 1 + 1) % 1) * span;
      const quiet = alpha * .42;

      // A steady registration rail seats the photographic vehicle. Motion is
      // confined to its edges and wake so the image remains readable.
      this.line(start, y + 10, end, y + 10, c, quiet, 1);
      this.line(start, y - 10, start + 10, y - 10, c, quiet * .7, 1);

      if (key === "arrival" || key === "interdiction_evaded") {
        // The identity bay resolves the ship after witch-space: speed bars
        // collapse into a steady acquisition bracket instead of continuing
        // the generic FSD wake used by charge and hyperspace.
        const lockX = end - 12;
        for (let band = 0; band < 4; band += 1) {
          const progress = (p + band / 4) % 1;
          const fade = Math.sin(progress * Math.PI);
          const x = start + Math.max(4, lockX - 2 - start) * smooth(progress);
          const length = 3 + (1 - progress) * 8;
          this.line(x, y - 7 + band * 4, Math.min(lockX - 2, x + length), y - 7 + band * 4,
            c, alpha * fade * (.34 + band * .09), band === 2 ? 1.5 : 1);
        }
        const lockPulse = .42 + .5 * wave(p);
        this.path([[lockX - 7, y - 9], [lockX - 10, y - 9], [lockX - 10, y - 4]],
          c, alpha * lockPulse, 1.2);
        this.path([[lockX + 7, y + 9], [lockX + 10, y + 9], [lockX + 10, y + 4]],
          c, alpha * lockPulse, 1.2);
        this.glowDot(lockX, y, 1 + .7 * wave(p * 2), c, alpha * .86);
      } else if (key === "fsd_cooldown") {
        // Post-jump thermal buses bleed away from the ship in alternating
        // banks.  This is deliberately the inverse of charge compression.
        const cx = start + span * .55;
        for (let bank = 0; bank < 5; bank += 1) {
          const progress = (p + bank / 5) % 1;
          const fade = Math.sin(progress * Math.PI);
          const distance = 4 + smooth(progress) * span * .42;
          const height = 2.5 + (1 - progress) * 5;
          for (const side of [-1, 1]) {
            const x = cx + side * distance;
            this.line(x, y - height, x, y + height, c,
              alpha * fade * (.34 + (1 - progress) * .35), 1.15);
            this.line(x, y + height, x + side * 4, y + height + 2, c,
              alpha * fade * .34, 1);
          }
        }
        const reset = 5 + wave(p) * 2;
        this.angularRing(cx, y, reset, reset * .58, 6, c,
          alpha * (.38 + .26 * wave(p * 2)), 1.1, Math.PI / 6);
        this.dot(cx, y, 1, c, alpha * .72);
      } else if (family === "fsd") {
        const speed = key === "supercruise_overcharge" || key === "hyperspace" ? 1.7 : 1;
        for (let i = 0; i < 4; i += 1) {
          const x = point(1 - (p * speed + i * .23));
          const length = 5 + i * 2 + (key === "hyperspace" ? 5 : 0);
          this.line(Math.max(start, x - length), y - 6 + i * 4, x, y - 6 + i * 4,
            c, alpha * (.28 + i * .1), i === 2 ? 1.5 : 1);
        }
        const gate = 3 + wave(p) * 7;
        this.line(end - gate, y - 9, end - gate, y + 9, c, alpha * .62, 1.3);
      } else if (key === "phenomena") {
        const cx = start + span * .52;
        for (let strand = 0; strand < 3; strand += 1) {
          const points = [];
          for (let step = 0; step <= 18; step += 1) {
            const travel = step / 18;
            const x = start + travel * span;
            const envelope = Math.sin(travel * Math.PI);
            const py = y + Math.sin((travel * 1.5 + p + strand / 3) * TAU)
              * (2 + strand) * envelope;
            points.push([x, py]);
          }
          this.path(points, c, alpha * (.18 + strand * .09), 1);
        }
        for (let contact = 0; contact < 4; contact += 1) {
          const angle = p * TAU * (contact % 2 ? -1 : 1) + contact * 1.47;
          const radius = 5 + contact * 4;
          const x = cx + Math.cos(angle) * radius;
          const py = y + Math.sin(angle) * radius * .38;
          this.arc(x, py, 1.8 + contact * .35, 1 + contact * .2,
            0, TAU, c, alpha * (.35 + .4 * wave(p + contact * .19)), 1);
        }
      } else if (family === "interface") {
        if (key === "left_panel" || key === "right_panel") {
          const fromLeft = key === "left_panel";
          const anchor = fromLeft ? start : end;
          const direction = fromLeft ? 1 : -1;
          for (let row = 0; row < 4; row += 1) {
            const rowY = y - 8 + row * 5;
            const width = span * (.36 + hash(row + 811) * .35);
            this.line(anchor, rowY, anchor + direction * width, rowY,
              c, alpha * (.24 + row * .08), row === 1 ? 1.35 : 1);
            const packet = (p + row / 4) % 1;
            const x = anchor + direction * width * packet;
            this.dot(x, rowY, .8, c,
              alpha * Math.sin(packet * Math.PI) * .76);
          }
          const gate = anchor + direction * span * (.18 + .68 * wave(p * .5));
          this.line(gate, y - 10, gate, y + 10, c, alpha * .58, 1.2);
          this.chevron(gate - direction * 3, y, direction, c, alpha * .68, 2.4);
        } else if (key === "comms_panel") {
          const points = [];
          for (let step = 0; step <= 28; step += 1) {
            const travel = step / 28;
            const x = start + travel * span;
            const py = y + Math.sin((travel * 3 - p * 2) * TAU)
              * (1.2 + 3.8 * Math.sin(travel * Math.PI));
            points.push([x, py]);
          }
          this.path(points, c, alpha * .5, 1.1);
          for (let packet = 0; packet < 3; packet += 1) {
            const progress = (p + packet / 3) % 1;
            const x = start + progress * span;
            this.rect(x - 2.5, y - 9 + packet * 7, 5, 2.5,
              c, alpha * Math.sin(progress * Math.PI) * .55, true);
          }
        } else if (key === "role_panel") {
          const reveal = wave(p * .5);
          for (let slot = 0; slot < 4; slot += 1) {
            const x = start + span * (slot + .5) / 4;
            const height = 5 + (slot % 2) * 3;
            this.rect(x - 4, y + 9 - height * reveal, 8, height * reveal,
              c, alpha * (.28 + slot * .09));
            this.dot(x, y + 6 - height * reveal, .8, c,
              alpha * (.4 + .35 * wave(p + slot / 4)));
          }
          this.line(start + 3, y + 10, end - 3, y + 10, c, alpha * .5, 1.2);
        } else {
          for (let cell = 0; cell < 6; cell += 1) {
            const column = cell % 3, row = Math.floor(cell / 3);
            const x = start + span * (.18 + column * .31);
            const py = y - 7 + row * 10;
            const active = cell === Math.floor(p * 6) % 6;
            this.rect(x - 5, py - 3, 10, 6, c,
              alpha * (active ? .72 : .25), active);
          }
        }
      } else if (key === "galaxy_map") {
        // Galactic navigation resolves as a sparse star lattice behind the
        // ship identity.  The travelling fix follows a plotted vector rather
        // than reusing the scanner sweep shared by FSS/DSS.
        const cx = start + span * .52;
        const contacts = [];
        for (let index = 0; index < 8; index += 1) {
          const x = start + 3 + hash(index + 307) * (span - 6);
          const py = y + (hash(index + 349) - .5) * 16;
          contacts.push([x, py]);
          const signal = .2 + .62 * wave(p + hash(index + 383));
          this.dot(x, py, index % 3 === 0 ? 1.15 : .65, c, alpha * signal);
        }
        for (const [from, to] of [[0, 3], [3, 6], [1, 5], [5, 7]]) {
          this.line(contacts[from][0], contacts[from][1], contacts[to][0], contacts[to][1],
            c, alpha * .18, 1);
        }
        this.arc(cx, y, span * .31, 7.5, 0, TAU, c, alpha * .24, 1);
        const fixAngle = p * TAU;
        const fixX = cx + Math.cos(fixAngle) * span * .31;
        const fixY = y + Math.sin(fixAngle) * 7.5;
        this.line(cx, y, fixX, fixY, c, alpha * .34, 1);
        this.glowDot(fixX, fixY, 1.25, c, alpha * .84);
        const routeY = y + 8;
        this.line(start + 4, routeY, end - 4, routeY, c, alpha * .3, 1.1);
        const routeProgress = (p + .08) % 1;
        const routeFade = Math.sin(routeProgress * Math.PI);
        const routeX = start + 4 + (span - 8) * routeProgress;
        this.chevron(routeX, routeY, 1, c, alpha * routeFade * .76, 2.3);
      } else if (key === "system_map") {
        // System Map keeps the identity bay body-relative: a central stellar
        // fix, three orbital tracks and a resolved body bracket.
        const cx = start + span * .47;
        this.glowDot(cx, y, 1.5 + .55 * wave(p * 2), c, alpha * .86);
        const radii = [span * .14, span * .25, span * .37];
        radii.forEach((radius, index) => {
          this.arc(cx, y, radius, 3.2 + index * 1.9, 0, TAU, c,
            alpha * (.18 + index * .06), 1);
          const direction = index % 2 ? -1 : 1;
          const angle = p * TAU * direction + index * 1.71;
          const bodyX = cx + Math.cos(angle) * radius;
          const bodyY = y + Math.sin(angle) * (3.2 + index * 1.9);
          this.dot(bodyX, bodyY, index === 2 ? 1.2 : .75, c, alpha * .72);
          if (index === 2) {
            const lock = 3.2 + wave(p) * 1.2;
            this.path([[bodyX - lock, bodyY - 2], [bodyX - lock, bodyY - lock],
              [bodyX - 1, bodyY - lock]], c, alpha * .62, 1);
            this.path([[bodyX + lock, bodyY + 2], [bodyX + lock, bodyY + lock],
              [bodyX + 1, bodyY + lock]], c, alpha * .62, 1);
          }
        });
        const bearing = p * TAU;
        this.line(cx, y, cx + Math.cos(bearing) * span * .42,
          y + Math.sin(bearing) * 9, c, alpha * .28, 1);
      } else if (family === "scope") {
        const x = point(p);
        this.line(x, y - 10, x, y + 10, c, alpha * .68, 1.2);
        for (let i = 0; i < 4; i += 1) {
          const cx = start + span * (.18 + i * .21);
          const cy = y + (hash(i + 211) - .5) * 12;
          this.dot(cx, cy, i === Math.floor(p * 4) ? 1.5 : .75, c,
            alpha * (i === Math.floor(p * 4) ? .82 : .34));
        }
      } else if (key === "srv" || key === "scorpion") {
        const armoured = key === "scorpion";
        const terrain = [];
        for (let i = 0; i <= 14; i += 1) {
          const progress = i / 14;
          terrain.push([
            start + span * progress,
            y + 7 + Math.sin((progress * 2 + p) * TAU) * (armoured ? 1.4 : 2.1),
          ]);
        }
        this.path(terrain, c, alpha * .48, 1.1);
        for (const progress of [.26, .5, .74]) {
          const x = start + span * progress;
          const angle = (p + progress) * TAU * (armoured ? 1.3 : 1.8);
          this.arc(x, y + 3, 2.7, 2.7, 0, TAU, c, alpha * .56, 1.1);
          this.dot(x + Math.cos(angle) * 1.7, y + 3 + Math.sin(angle) * 1.7,
            .65, c, alpha * .8);
        }
        const sweepX = start + span * p;
        this.line(sweepX, y - 8, sweepX, y + 8, c,
          alpha * (armoured ? .22 : .48) * Math.sin(p * Math.PI), 1.2);
      } else if (key === "nomad") {
        const hover = wave(p) * 1.5;
        this.line(start, y + 8, end, y + 8, c, alpha * .34, 1);
        this.path([[start + span * .28, y + 1 - hover], [start + span * .43, y - 4 - hover],
          [start + span * .68, y - 3 - hover], [start + span * .79, y + 1 - hover]],
        c, alpha * .7, 1.2);
        for (const progress of [.38, .63]) {
          const x = start + span * progress;
          const length = 3 + 5 * wave(p + progress);
          this.line(x, y + 1 - hover, x, y + length, c, alpha * .5, 1.2);
        }
        this.chevron(point((p * .72 + .1) % 1), y - 7, 1, c, alpha * .58, 2.4);
      } else if (key === "fighter") {
        const lockX = start + span * (.58 + Math.sin(p * TAU) * .08);
        const lockY = y + Math.cos(p * TAU) * 2.5;
        this.arc(lockX, lockY, 7, 5, -.7, .7, c, alpha * .55, 1.1);
        this.arc(lockX, lockY, 7, 5, Math.PI - .7, Math.PI + .7, c, alpha * .55, 1.1);
        for (let i = 0; i < 3; i += 1) {
          const x = point((p * 1.8 + i / 3) % 1);
          this.line(Math.max(start, x - 8), y - 6 + i * 5, x, y - 6 + i * 5,
            c, alpha * (.38 + i * .13), 1.2);
        }
      } else if (family === "surface") {
        const departing = key.includes("departure");
        const orbital = key.startsWith("orbital_");
        const glide = key === "glide";
        const hold = key === "surface_hold" || key === "landed";
        const direction = departing ? -1 : 1;
        const horizon = y + 6;
        this.arc(start + span * .52, horizon + 7, span * .55, 9,
          Math.PI * 1.08, Math.PI * 1.92, c, alpha * .48, 1.15);
        if (orbital) {
          this.arc(start + span * .52, y + 1, span * .38, 8, 0, TAU,
            c, alpha * .28, 1);
          const angle = (departing ? p : 1 - p) * TAU;
          const contactX = start + span * .52 + Math.cos(angle) * span * .38;
          const contactY = y + 1 + Math.sin(angle) * 8;
          this.glowDot(contactX, contactY, 1.2, c, alpha * .82);
        } else if (glide) {
          this.line(start + 4, y - 9, end - 7, horizon, c, alpha * .42, 1.2);
          this.line(start + 17, y - 9, end - 1, horizon - 2, c, alpha * .3, 1);
          for (let gate = 0; gate < 3; gate += 1) {
            const progress = (p * 1.7 + gate / 3) % 1;
            const x = start + span * progress;
            const py = y - 8 + progress * 14;
            this.path([[x - 3, py - 2], [x, py], [x + 3, py - 2]],
              c, alpha * Math.sin(progress * Math.PI) * .68, 1.2);
          }
        } else if (hold) {
          const lock = 5 + wave(p) * 2;
          this.line(start + span * .28, horizon - 1, end - span * .28, horizon - 1,
            c, alpha * .64, 1.3);
          this.path([[start + span * .52 - lock, y - 4], [start + span * .52 - lock, y + 2],
            [start + span * .52 - 2, y + 2]], c, alpha * .55, 1.1);
          this.path([[start + span * .52 + lock, y - 4], [start + span * .52 + lock, y + 2],
            [start + span * .52 + 2, y + 2]], c, alpha * .55, 1.1);
        } else {
          for (let rung = 0; rung < 4; rung += 1) {
            const progress = (p + rung / 4) % 1;
            const travel = departing ? 1 - progress : progress;
            const py = y - 8 + travel * 14;
            const half = 2 + travel * 5;
            this.line(start + span * .52 - half, py, start + span * .52 + half, py,
              c, alpha * Math.sin(progress * Math.PI) * .58, 1);
          }
          const markerX = point(direction > 0 ? p : 1 - p);
          this.chevron(markerX, horizon - 2, direction, c, alpha * .68, 2.5);
        }
      } else if (family === "hazard") {
        const pulse = .38 + .62 * wave(p * (key === "interdiction" ? 2 : 1));
        this.path([[start + 7, y - 9], [start, y], [start + 7, y + 9]], c, alpha * pulse, 1.5);
        this.path([[end - 7, y - 9], [end, y], [end - 7, y + 9]], c, alpha * pulse, 1.5);
        for (let i = 0; i <= 12; i += 1) {
          const x = start + span * i / 12;
          const py = y + Math.sin((i / 12 * 3 - p * 2) * TAU) * 2.5;
          if (i) {
            const prevX = start + span * (i - 1) / 12;
            const prevY = y + Math.sin(((i - 1) / 12 * 3 - p * 2) * TAU) * 2.5;
            this.line(prevX, prevY, x, py, c, alpha * .42);
          }
        }
      } else if (family === "vehicle") {
        const x = point(p);
        this.trackStroke(p, .08, {
          ...g, left: start, right: end, center: (start + end) / 2,
          centerLeft: (start + end) / 2 - 2, centerRight: (start + end) / 2 + 2,
        }, y + 7, c, alpha * .5);
        this.line(x, y - 7, x, y + 7, c, alpha * .55);
      } else if (family === "carrier") {
        for (let i = 0; i < 5; i += 1) {
          const x = start + span * (i + .5) / 5;
          const active = ((Math.floor(p * 5) + 5) % 5) === i;
          this.rect(x - 5, y + 5, 8, 3, c, alpha * (active ? .72 : .25), active);
        }
        this.line(start + 4, y - 6, end - 4, y - 6, c, alpha * .34, 2);
      } else if (family === "station") {
        const spread = 12 + wave(p) * 2;
        const cx = (start + end) / 2;
        this.path([[cx - spread, y - 8], [cx - spread, y + 7], [cx - spread + 5, y + 7]], c, alpha * .52, 1.2);
        this.path([[cx + spread, y - 8], [cx + spread, y + 7], [cx + spread - 5, y + 7]], c, alpha * .52, 1.2);
      } else {
        const packets = key === "fighter" ? 3 : key === "multicrew" ? 2 : 1;
        for (let i = 0; i < packets; i += 1) {
          const progress = (p * .64 + i / packets) % 1;
          const x = point(progress);
          this.line(Math.max(start, x - 8), y + 7 - i * 3, x, y + 7 - i * 3,
            c, alpha * (.38 + .22 * wave(progress)), 1.2);
          this.dot(x, y + 7 - i * 3, 1, c, alpha * .7);
        }
      }
    }

    drawFlight(g, state, p, alpha, key) {
      const c = state.color, y = g.y;
      const fighter = key === "fighter";
      const crew = key === "multicrew";
      const route = state.dynamics.routeActive;
      const amplitude = fighter ? 6 : 3.2;
      const points = [];
      for (let i = 0; i <= 42; i += 1) {
        const progress = i / 42;
        const point = this.trackPoint(progress, g);
        points.push([point.x, y + Math.sin((progress * 2 + p) * TAU) * amplitude * (fighter ? .48 : .24), point.wing]);
      }
      let segment = [];
      for (const [x, py, wing] of points) {
        if (segment.length && segment[segment.length - 1][2] !== wing) {
          this.path(segment.map(([sx, sy]) => [sx, sy]), c, alpha * .38);
          segment = [];
        }
        segment.push([x, py, wing]);
      }
      this.path(segment.map(([x, py]) => [x, py]), c, alpha * .38);
      const packets = fighter ? 3 : crew ? 2 : 1;
      for (let i = 0; i < packets; i += 1) {
        const progress = (p + i / packets) % 1;
        this.trackStroke(progress, fighter ? .09 : .055, g, y, c, alpha * .9, fighter ? 1.7 : 1.3);
      }
      for (const progress of [.14, .38, .62, .86]) {
        const point = this.trackPoint(progress, g);
        this.chevron(point.x, y, 1, c,
          alpha * ((route ? .34 : .2) + .18 * wave(p + progress)), 2.6);
      }
      if (crew) {
        [-1, 1].forEach((side) => {
          const cx = side < 0 ? (g.left + g.centerLeft) / 2 : (g.centerRight + g.right) / 2;
          this.dot(cx - 5, y, 1.2, c, alpha * .72);
          this.dot(cx + 5, y, 1.2, c, alpha * .72);
          this.line(cx - 4, y, cx + 4, y, c, alpha * .48);
        });
      }
    }

    drawExploration(g, state, p, alpha) {
      const c = state.color, y = g.y;
      const span = Math.max(24, g.right - g.left);
      const cx = (g.left + g.right) / 2;

      // Long-range discovery scope. Every moving contact fades fully at its
      // wrap point, and every oscillator completes an integer cycle, making
      // frame 1 meet frame 0 without the old visible snap-back.
      this.line(g.left + 2, y, g.right - 2, y, c, alpha * .2, 1);
      this.line(g.left + 4, y - 10, cx, y - 2, c, alpha * .22, 1);
      this.line(g.left + 4, y + 10, cx, y + 2, c, alpha * .22, 1);
      this.line(g.right - 4, y - 10, cx, y - 2, c, alpha * .22, 1);
      this.line(g.right - 4, y + 10, cx, y + 2, c, alpha * .22, 1);

      // Four expanding range gates provide forward depth. A sine envelope
      // hides each gate exactly as it returns from the far edge.
      for (let gate = 0; gate < 4; gate += 1) {
        const progress = (p + gate / 4) % 1;
        const fade = Math.sin(progress * Math.PI);
        const x = g.left + 4 + (span - 8) * progress;
        const halfHeight = 2.5 + progress * 8;
        this.path([
          [x - 2.5, y - halfHeight], [x, y - halfHeight - 1.5],
          [x + 2.5, y - halfHeight],
        ], c, alpha * fade * .42, 1);
        this.path([
          [x - 2.5, y + halfHeight], [x, y + halfHeight + 1.5],
          [x + 2.5, y + halfHeight],
        ], c, alpha * fade * .42, 1);
      }

      // Deterministic stellar contacts sit in the scope instead of sparkling
      // randomly. Their phase-offset pulses and constellation traces make the
      // field resolve progressively through the full discovery cycle.
      const contacts = [];
      for (let index = 0; index < 9; index += 1) {
        const x = g.left + 8 + hash(index + 41) * (span - 16);
        const py = y + (hash(index + 79) - .5) * 16;
        const signal = .2 + .72 * wave(p + hash(index + 113));
        contacts.push([x, py, signal]);
        this.dot(x, py, index % 4 === 0 ? 1.35 : .78, c, alpha * signal);
        if (index % 4 === 0) {
          this.arc(x, py, 3.2, 2.2, 0, TAU, c, alpha * signal * .36, 1);
        }
      }
      for (const [from, to, phase] of [[0, 3, .03], [3, 6, .31], [6, 8, .58], [2, 5, .79]]) {
        const resolve = Math.pow(wave(p + phase), 2);
        this.line(contacts[from][0], contacts[from][1], contacts[to][0], contacts[to][1],
          c, alpha * resolve * .2, 1);
      }

      // The central discovery reticle makes one complete revolution while a
      // smooth sinusoidal sensor beam searches the field and returns without
      // changing direction abruptly at the loop boundary.
      this.angularRing(cx, y, 10.5, 7, 6, c,
        alpha * (.34 + .28 * wave(p)), 1.1, p * TAU);
      this.dot(cx, y, 1.1, c, alpha * (.58 + .34 * wave(p * 2)));
      const sweepX = cx + Math.sin(p * TAU) * span * .39;
      const sweepFade = .3 + .55 * Math.abs(Math.cos(p * TAU));
      this.line(sweepX, y - 10, sweepX, y + 10, c, alpha * sweepFade, 1.15);
      this.line(sweepX - 5, y, sweepX + 5, y, c, alpha * sweepFade * .65, 1);
    }

    drawSupercruise(g, state, p, alpha, overcharge = false) {
      const c = state.color, y = g.y;
      const cx = (g.left + g.right) / 2;
      const span = Math.max(28, g.right - g.left);
      const boostTier = this.boostTier(state);
      const boostValue = state.dynamics.neutronBoostValue;
      const neutron = boostTier > 0 && !overcharge;
      const energy = overcharge ? 1.65 : neutron ? 1.12 + boostTier * .08 : 1;

      // A forward flight corridor: stable horizon/vanishing point plus
      // expanding angular gates. It reads as supercruise rather than a
      // generic progress rail, and every gate fades before its loop wraps.
      this.line(g.left + 2, y - 11, cx, y - 2, c, alpha * .32, 1);
      this.line(g.left + 2, y + 11, cx, y + 2, c, alpha * .32, 1);
      this.line(g.right - 2, y - 11, cx, y - 2, c, alpha * .32, 1);
      this.line(g.right - 2, y + 11, cx, y + 2, c, alpha * .32, 1);
      this.line(cx - 8, y, cx + 8, y, c, alpha * (.42 + .24 * wave(p)), 1.4);
      this.glowDot(cx, y, overcharge ? 1.9 : 1.3, c, alpha * .88);
      for (let gate = 0; gate < 4; gate += 1) {
        const progress = (p * energy + gate / 4) % 1;
        const scale = .13 + Math.pow(progress, 1.28) * .87;
        const fade = Math.sin(progress * Math.PI);
        this.angularRing(
          cx, y, span * .46 * scale, 11.5 * scale, 6, c,
          alpha * fade * (overcharge ? .72 : .48),
          overcharge && gate === 0 ? 1.6 : 1,
          Math.PI / 6,
        );
      }

      // Sparse star streaks carry the speed. Seeded lanes are deterministic,
      // so they remain smooth instead of sparkling randomly between frames.
      const streaks = overcharge ? 14 : 10;
      for (let index = 0; index < streaks; index += 1) {
        const progress = (p * energy + hash(index + 31)) % 1;
        const eased = Math.pow(progress, 1.7);
        const side = hash(index + 67) < .5 ? -1 : 1;
        const radial = (.18 + hash(index + 93) * .82) * eased;
        const x = cx + side * span * .47 * radial;
        const py = y + (hash(index + 121) - .5) * 20 * eased;
        const length = (2 + eased * (overcharge ? 12 : 8)) * side;
        const fade = Math.sin(progress * Math.PI);
        this.line(x - length, py, x, py, c,
          alpha * fade * (overcharge ? .78 : .52), 1 + eased * .8);
      }

      if (overcharge) {
        // SCO gets a contained plasma shear, distinct from normal cruise.
        for (let band = 0; band < 2; band += 1) {
          const points = [];
          for (let step = 0; step <= 30; step += 1) {
            const progress = step / 30;
            const x = g.left + progress * span;
            const py = y + Math.sin((progress * 3.5 - p * 4 + band * .5) * TAU)
              * (2.1 + band * 1.6);
            points.push([x, py]);
          }
          this.path(points, c, alpha * (band ? .28 : .54), band ? 1 : 1.5);
        }
      } else if (neutron) {
        // Jet-cone charge changes the normal supercruise corridor itself. The
        // actual journal BoostValue selects the number and speed of locked
        // field coils, so enhanced boosts remain visibly stronger than the
        // ordinary neutron charge without inventing a fixed multiplier.
        const coils = boostTier === 3 ? 6 : boostTier === 2 ? 4 : 3;
        const phaseSpeed = 1.2 + boostTier * .28;
        for (let coil = 0; coil < coils; coil += 1) {
          const phase = (p * phaseSpeed + coil / coils) % 1;
          const x = g.left + 7 + phase * (span - 14);
          const envelope = Math.sin(phase * Math.PI);
          const radius = 3.2 + envelope * (4 + boostTier * 1.2);
          this.angularRing(x, y, radius, radius * .58, boostTier === 3 ? 8 : 6,
            c, alpha * envelope * (.34 + boostTier * .11),
            boostTier === 3 ? 1.5 : 1.15, p * TAU + coil);
        }
        for (const side of [-1, 1]) {
          const points = [];
          for (let step = 0; step <= 28; step += 1) {
            const progress = step / 28;
            const x = cx + side * progress * span * .47;
            const cone = progress * (4.2 + boostTier * 1.8);
            const py = y + Math.sin((progress * (2 + boostTier) - p * phaseSpeed) * TAU)
              * cone;
            points.push([x, py]);
          }
          this.path(points, c, alpha * (.23 + boostTier * .1), boostTier === 3 ? 1.45 : 1.05);
        }
        this.angularRing(cx, y, 11 + boostTier * 2.5, 6 + boostTier,
          6 + boostTier * 2, c, alpha * (.42 + .25 * wave(p * phaseSpeed)),
          1.2 + boostTier * .18, -p * TAU * phaseSpeed);
        if (boostValue > 0) {
          const markers = Math.max(1, Math.min(6, Math.round(boostValue)));
          for (let index = 0; index < markers; index += 1) {
            const angle = index / markers * TAU - p * TAU * .45;
            this.dot(cx + Math.cos(angle) * (7 + boostTier * 2),
              y + Math.sin(angle) * (3 + boostTier), .7, c, alpha * .78);
          }
        }
      }
    }

    drawCharge(g, state, p, alpha, hyper = false) {
      const c = state.color, y = g.y;
      const cx = (g.left + g.right) / 2;
      const half = Math.max(18, (g.right - g.left) / 2);
      const boosted = hyper || state.dynamics.neutronBoost;

      // Drive capacitor banks step toward a single compression focus.
      for (let bank = 0; bank < 7; bank += 1) {
        const progress = (p + bank / 7) % 1;
        const inward = smooth(progress);
        const distance = half * (1 - inward) * .92;
        const height = 3 + inward * 8.5;
        const fade = Math.sin(progress * Math.PI);
        for (const side of [-1, 1]) {
          const x = cx + side * distance;
          this.path([
            [x - side * 4, y - height], [x, y - height],
            [x + side * 2.5, y], [x, y + height], [x - side * 4, y + height],
          ], c, alpha * fade * .72, inward > .72 ? 1.7 : 1.1);
        }
      }

      // Contracting drive reticles give FSD CHARGE a mechanical spool-up.
      for (let ring = 0; ring < 3; ring += 1) {
        const phase = (p + ring / 3) % 1;
        const contraction = 1 - smooth(phase) * .78;
        const fade = Math.sin(phase * Math.PI);
        this.angularRing(cx, y, half * .62 * contraction + 4, 10 * contraction + 2,
          boosted ? 8 : 6, c, alpha * fade * (boosted ? .62 : .42),
          boosted ? 1.5 : 1, p * TAU * (ring % 2 ? -1 : 1));
      }
      this.glowDot(cx, y, 1.5 + 1.4 * wave(p), c, alpha);
      this.line(cx - 12, y, cx + 12, y, c, alpha * (.36 + .34 * wave(p)), 1.2);

      if (boosted) {
        // Hypercharge / neutron boost adds phase-locked coils rather than
        // merely running the normal charge animation faster.
        for (let coil = 0; coil < 2; coil += 1) {
          const points = [];
          for (let step = 0; step <= 34; step += 1) {
            const progress = step / 34;
            const x = g.left + progress * (g.right - g.left);
            const envelope = Math.sin(progress * Math.PI);
            const py = y + Math.sin((progress * 2.5 - p * 2 + coil * .5) * TAU)
              * 6.2 * envelope;
            points.push([x, py]);
          }
          this.path(points, c, alpha * (coil ? .36 : .68), coil ? 1 : 1.5);
        }
      } else {
        for (let packet = 0; packet < 3; packet += 1) {
          const progress = (p + packet / 3) % 1;
          const side = packet % 2 ? -1 : 1;
          const x = cx + side * half * (1 - smooth(progress));
          this.line(x - side * 7, y, x, y, c,
            alpha * Math.sin(progress * Math.PI) * .82, 1.7);
        }
      }
    }

    drawJump(g, state, p, alpha, jumping = false) {
      const c = state.color, y = g.y;
      const cx = (g.left + g.right) / 2;
      const span = Math.max(28, g.right - g.left);
      const speed = jumping ? 1.42 : 1.08;

      // Witch-space is a radial tunnel, intentionally unlike the orderly
      // supercruise corridor. Streaks accelerate away from a turbulent core.
      const count = jumping ? 15 : 20;
      for (let index = 0; index < count; index += 1) {
        const progress = (p * speed + hash(index + 41)) % 1;
        const travel = Math.pow(progress, 1.55);
        const angle = hash(index + 79) * TAU + Math.sin(p * TAU + index) * .08;
        const radiusX = span * .49 * travel;
        const radiusY = 11.5 * travel;
        const x = cx + Math.cos(angle) * radiusX;
        const py = y + Math.sin(angle) * radiusY;
        const prior = Math.max(0, travel - (.06 + travel * .12));
        const tailX = cx + Math.cos(angle) * span * .49 * prior;
        const tailY = y + Math.sin(angle) * 11.5 * prior;
        const fade = Math.sin(progress * Math.PI);
        this.line(tailX, tailY, x, py, c, alpha * fade * (.4 + travel * .6),
          1 + travel * 1.2);
      }
      for (let ring = 0; ring < 3; ring += 1) {
        const phase = (p * speed + ring / 3) % 1;
        const expansion = Math.pow(phase, .72);
        const fade = Math.sin(phase * Math.PI);
        this.angularRing(cx, y, 4 + span * .45 * expansion, 2 + 10 * expansion,
          8, c, alpha * fade * .55, ring === 0 ? 1.6 : 1,
          p * TAU * (ring % 2 ? -.22 : .18));
      }
      const core = .45 + .55 * wave(p * 2);
      this.glowDot(cx, y, 1.4 + core * 1.7, c, alpha * core);
      this.line(cx - 8, y, cx + 8, y, c, alpha * .55, 1.3);
      if (jumping) {
        const shock = wave(p);
        this.angularRing(cx, y, 8 + shock * span * .38, 3 + shock * 8,
          6, c, alpha * (1 - shock) * .8, 1.8, Math.PI / 6);
      }
    }

    drawArrival(g, state, p, alpha) {
      const c = state.color, y = g.y;
      const cx = (g.left + g.right) / 2;
      const half = Math.max(16, (g.right - g.left) / 2);

      // Arrival reverses the witch-space tunnel. Angular apertures contract
      // into the navigation lock while deceleration packets bleed away at the
      // centre, so the loop remains seamless during the bounded arrival state.
      for (let ring = 0; ring < 4; ring += 1) {
        const progress = (p + ring / 4) % 1;
        const contraction = 1 - smooth(progress);
        const fade = Math.sin(progress * Math.PI);
        this.angularRing(cx, y, 5 + half * .86 * contraction, 2.5 + 8.5 * contraction,
          6, c, alpha * fade * (.42 + ring * .05), ring === 0 ? 1.5 : 1,
          Math.PI / 6);
      }
      for (let packet = 0; packet < 4; packet += 1) {
        const progress = (p + packet / 4) % 1;
        const inward = smooth(progress);
        const fade = Math.sin(progress * Math.PI);
        const side = packet % 2 ? -1 : 1;
        const x = cx + side * half * (1 - inward);
        this.line(x + side * (4 + 5 * (1 - inward)), y - 6 + packet * 4,
          x, y - 6 + packet * 4, c, alpha * fade * .72, 1.3);
      }
      const lock = 9 + wave(p) * 2.5;
      this.path([[cx - lock - 5, y - 8], [cx - lock, y - 8], [cx - lock, y - 3]],
        c, alpha * .68, 1.25);
      this.path([[cx + lock + 5, y + 8], [cx + lock, y + 8], [cx + lock, y + 3]],
        c, alpha * .68, 1.25);
      this.line(cx - 6, y, cx + 6, y, c, alpha * (.45 + .35 * wave(p)), 1.3);
      this.glowDot(cx, y, 1.3 + .9 * wave(p * 2), c, alpha * .92);
    }

    drawCooldown(g, state, p, alpha) {
      const c = state.color, y = g.y;
      const cx = g.center;
      const span = Math.max(24, g.right - g.left);

      // Cooling is the mechanical inverse of FSD charge: hot packets travel
      // away from the drive core through paired radiator buses, fading before
      // they wrap.  A slowly resolving hexagonal lock represents drive reset.
      this.line(g.left + 4, y, cx - 7, y, c, alpha * .28, 1.1);
      this.line(cx + 7, y, g.right - 4, y, c, alpha * .28, 1.1);
      for (let fin = 0; fin < 6; fin += 1) {
        const progress = (p + fin / 6) % 1;
        const fade = Math.sin(progress * Math.PI);
        const distance = 7 + smooth(progress) * span * .43;
        const heat = 1 - progress;
        const height = 2.5 + heat * 8;
        for (const side of [-1, 1]) {
          const x = cx + side * distance;
          this.line(x, y - height, x, y + height, c,
            alpha * fade * (.38 + heat * .42), 1 + heat * .45);
          this.line(x, y - height, x + side * (3 + heat * 4), y - height - 2,
            c, alpha * fade * .34, 1);
          this.line(x, y + height, x + side * (3 + heat * 4), y + height + 2,
            c, alpha * fade * .34, 1);
        }
      }
      for (let ring = 0; ring < 3; ring += 1) {
        const phase = (p + ring / 3) % 1;
        const contraction = 1 - smooth(phase);
        const fade = Math.sin(phase * Math.PI);
        this.angularRing(cx, y, 5 + contraction * 14, 2.8 + contraction * 6,
          6, c, alpha * fade * .4, 1.1, Math.PI / 6);
      }
      const ready = .4 + .45 * wave(p * 2);
      this.path([[cx - 8, y - 6], [cx - 4, y - 9], [cx + 4, y - 9],
        [cx + 8, y - 6]], c, alpha * ready, 1.15);
      this.path([[cx - 8, y + 6], [cx - 4, y + 9], [cx + 4, y + 9],
        [cx + 8, y + 6]], c, alpha * ready, 1.15);
      this.glowDot(cx, y, 1.2, c, alpha * (.45 + .35 * wave(p)));
    }

    splitPath(points, color, alpha = 1, width = 1) {
      let segment = [];
      for (const point of points) {
        if (segment.length && segment[segment.length - 1][2] !== point[2]) {
          this.path(segment.map(([x, y]) => [x, y]), color, alpha, width);
          segment = [];
        }
        segment.push(point);
      }
      this.path(segment.map(([x, y]) => [x, y]), color, alpha, width);
    }

    drawScanner(g, state, p, alpha, dss = false) {
      const c = state.color, y = g.y;
      const progress = dss ? (p * .72) % 1 : p;
      const cursor = this.trackPoint(progress, g);
      this.line(cursor.x, y - 11, cursor.x, y + 11, c, alpha * .92, 1.6);
      this.trackStroke(progress, .09, g, y, c, alpha * .72);
      for (let i = 0; i < 10; i += 1) {
        const point = this.trackPoint((i + .5) / 10, g);
        const value = .2 + hash(i + 113) * .8;
        if (dss) {
          this.arc(point.x, y, 2 + value * 4, 1.4 + value * 2.2, 0, TAU, c,
            alpha * (.2 + .45 * wave(p + i * .07)));
        } else {
          this.line(point.x, y - value * 8, point.x, y + value * 8, c,
            alpha * (.25 + value * .42));
        }
      }
      if (state.dynamics.analysisMode) {
        this.line(g.left, y + 11, g.centerLeft - 4, y + 11, c, alpha * .5, 1.5);
        this.line(g.centerRight + 4, y + 11, g.right, y + 11, c, alpha * .5, 1.5);
      }
    }

    drawMap(g, state, p, alpha, key) {
      const c = state.color, y = g.y;
      const centers = [(g.left + g.centerLeft) / 2, (g.centerRight + g.right) / 2];
      if (key === "galaxy_map" || key === "map") {
        const cx = g.center;
        const span = Math.max(24, g.right - g.left);

        // A flattened galactic projection with a plotted navigation solution.
        // Seeded contacts keep it quiet and deterministic; every moving phase
        // completes an integer revolution so the animation has no wrap jerk.
        for (let ring = 0; ring < 3; ring += 1) {
          this.arc(cx, y, span * (.15 + ring * .13), 3.5 + ring * 3.2,
            0, TAU, c, alpha * (.16 + ring * .055), 1,
          );
        }
        for (let arm = 0; arm < 3; arm += 1) {
          const points = [];
          for (let step = 0; step <= 18; step += 1) {
            const travel = step / 18;
            const radius = 2 + travel * span * .43;
            const angle = travel * 4.6 + p * TAU + arm * TAU / 3;
            points.push([
              cx + Math.cos(angle) * radius,
              y + Math.sin(angle) * radius * .2,
            ]);
          }
          this.path(points, c, alpha * .32, 1);
        }
        for (let index = 0; index < 11; index += 1) {
          const starX = g.left + 5 + hash(index + 421) * (span - 10);
          const starY = y + (hash(index + 463) - .5) * 19;
          const signal = .18 + .55 * wave(p + hash(index + 491));
          this.dot(starX, starY, index % 4 === 0 ? 1.05 : .58, c, alpha * signal);
        }

        const route = [
          [g.left + 7, y + 7], [g.left + span * .29, y + 2],
          [g.left + span * .54, y - 6], [g.left + span * .78, y - 1],
          [g.right - 7, y - 8],
        ];
        this.path(route, c, alpha * .42, 1.15);
        route.forEach(([x, py], index) => {
          this.angularRing(x, py, index === route.length - 1 ? 3.4 : 2.2,
            index === route.length - 1 ? 2.4 : 1.55, 4, c,
            alpha * (index === route.length - 1 ? .76 : .4), 1, Math.PI / 4);
        });
        const legFloat = p * (route.length - 1);
        const leg = Math.min(route.length - 2, Math.floor(legFloat));
        const local = legFloat - leg;
        const packetX = route[leg][0] + (route[leg + 1][0] - route[leg][0]) * local;
        const packetY = route[leg][1] + (route[leg + 1][1] - route[leg][1]) * local;
        const packetFade = Math.sin(p * Math.PI);
        this.glowDot(packetX, packetY, 1.35, c,
          alpha * (.38 + .5 * packetFade));
        const aperture = 7 + wave(p) * 2;
        this.path([[cx - aperture - 4, y - 10], [cx - aperture, y - 10],
          [cx - aperture, y - 6]], c, alpha * .5, 1.1);
        this.path([[cx + aperture + 4, y + 10], [cx + aperture, y + 10],
          [cx + aperture, y + 6]], c, alpha * .5, 1.1);
        return;
      }
      if (key === "system_map") {
        const cx = g.center;
        const span = Math.max(24, g.right - g.left);
        const orbitRadii = [span * .105, span * .2, span * .31, span * .42];

        // One navigable star system: the primary remains fixed, orbiting
        // contacts move at distinct integer periods, and the outer target is
        // acquired by a restrained body-selection bracket.
        this.glowDot(cx, y, 2.1 + .65 * wave(p * 2), c, alpha * .92);
        this.arc(cx, y, 4.5, 3, 0, TAU, c, alpha * .45, 1.2);
        orbitRadii.forEach((radius, index) => {
          const ry = 3.1 + index * 2.25;
          this.arc(cx, y, radius, ry, 0, TAU, c,
            alpha * (.2 + index * .045), 1);
          const direction = index % 2 ? -1 : 1;
          const revolutions = index < 2 ? 2 : 1;
          const angle = p * TAU * revolutions * direction + index * 1.37;
          const bodyX = cx + Math.cos(angle) * radius;
          const bodyY = y + Math.sin(angle) * ry;
          this.dot(bodyX, bodyY, index === 3 ? 1.45 : .8 + index * .08,
            c, alpha * (.58 + .2 * wave(p + index * .17)));
          if (index === 3) {
            const lock = 4 + wave(p) * 1.5;
            this.path([[bodyX - lock - 2, bodyY - lock], [bodyX - lock, bodyY - lock],
              [bodyX - lock, bodyY - 2]], c, alpha * .72, 1.2);
            this.path([[bodyX + lock + 2, bodyY + lock], [bodyX + lock, bodyY + lock],
              [bodyX + lock, bodyY + 2]], c, alpha * .72, 1.2);
          }
        });
        const scanAngle = p * TAU;
        this.line(cx, y, cx + Math.cos(scanAngle) * span * .45,
          y + Math.sin(scanAngle) * 10.5, c, alpha * .27, 1);
        for (const side of [-1, 1]) {
          const edgeX = cx + side * span * .47;
          this.line(edgeX, y - 8, edgeX, y + 8, c,
            alpha * (.28 + .25 * wave(p + (side > 0 ? .5 : 0))), 1.15);
        }
        return;
      }
      if (key === "codex") {
        centers.forEach((cx, side) => {
          for (let row = -1; row <= 1; row += 1) {
            const width = 18 + ((row + side + 3) % 3) * 7;
            this.line(cx - width, y + row * 5, cx + width, y + row * 5, c,
              alpha * (row === Math.floor(p * 3) - 1 ? .78 : .3));
          }
          this.line(cx - 31, y - 10, cx - 31, y + 10, c, alpha * .48);
        });
        return;
      }
      centers.forEach((cx, side) => {
        if (key === "power_map") {
          const nodes = [[-26, 5], [-12, -7], [5, 1], [22, -8], [29, 7]];
          this.path(nodes.map(([x, py]) => [cx + x, y + py]), c, alpha * .42);
          nodes.forEach(([x, py], i) => this.dot(cx + x, y + py, i === Math.floor(p * nodes.length) ? 2 : 1.2, c, alpha * .72));
        } else {
          const orbits = key === "orrery" ? [7, 14, 23, 31] : [9, 20, 30];
          orbits.forEach((radius, i) => {
            this.arc(cx, y, radius, radius * .34, 0, TAU, c, alpha * (.22 + i * .07));
            const angle = (p * (i % 2 ? -1 : 1) + i * .23) * TAU;
            this.dot(cx + Math.cos(angle) * radius, y + Math.sin(angle) * radius * .34,
              i === 0 ? 1.5 : 1, c, alpha * .75);
          });
        }
      });
    }

    drawPlanet(g, state, p, alpha, key) {
      const c = state.color, y = g.y, d = state.dynamics;
      const departing = key.includes("departure");
      const hold = key === "surface_hold";
      const landed = key === "landed";
      const orbital = key.startsWith("orbital_");
      const glide = key === "glide";
      const vertical = clamp(Math.abs(d.vertical) / 160);
      const gravity = clamp(d.gravity / 4);
      const knownAltitude = d.altitude >= 0;
      const altitude = knownAltitude ? clamp(Math.log10(d.altitude + 1) / 6) : .45;
      const proximity = 1 - altitude;
      const horizonY = y + (departing ? 5 : hold || landed ? 6 : 3) + gravity * 1.4;
      const leftMid = (g.left + g.centerLeft) / 2;
      const rightMid = (g.centerRight + g.right) / 2;
      [leftMid, rightMid].forEach((cx) => {
        const bayWidth = Math.max(15, g.centerLeft - g.left);
        const planetWidth = Math.min(62, bayWidth * (.34 + proximity * .2));
        this.arc(cx, horizonY + 10, planetWidth, 10 + gravity * 2,
          Math.PI * 1.08, Math.PI * 1.92, c, alpha * .56, 1.2);
      });
      if (hold || landed) {
        this.line(g.left + 7, horizonY, g.centerLeft - 7, horizonY, c, alpha * .55, 1.3);
        this.line(g.centerRight + 7, horizonY, g.right - 7, horizonY, c, alpha * .55, 1.3);
        for (const cx of [leftMid, rightMid]) {
          this.line(cx - 8, horizonY, cx - 4, horizonY - 5, c, alpha * .62);
          this.line(cx + 8, horizonY, cx + 4, horizonY - 5, c, alpha * .62);
        }
        for (const cx of [leftMid, rightMid]) {
          const pulse = 4 + wave(p) * 2;
          this.path([[cx - pulse, y - 6], [cx - pulse, y], [cx - 2, y]],
            c, alpha * .5, 1.1);
          this.path([[cx + pulse, y - 6], [cx + pulse, y], [cx + 2, y]],
            c, alpha * .5, 1.1);
          if (landed) this.rect(cx - 5, horizonY - 2, 10, 2, c, alpha * .65, true);
        }
      } else if (orbital) {
        // Orbital phases use a curved flight solution and a body-relative
        // contact. Approach converges toward the forward tangent; departure
        // carries the contact away while the planet arc recedes.
        [leftMid, rightMid].forEach((cx, side) => {
          const bayWidth = Math.max(16, g.centerLeft - g.left);
          this.arc(cx, y + 1, bayWidth * .34, 8, 0, TAU, c, alpha * .3, 1);
          const travel = departing ? p : 1 - p;
          const angle = (side ? Math.PI : 0) + travel * TAU;
          const contactX = cx + Math.cos(angle) * bayWidth * .34;
          const contactY = y + 1 + Math.sin(angle) * 8;
          this.glowDot(contactX, contactY, 1.25, c,
            alpha * (.5 + .42 * wave(p + side * .17)));
          this.line(cx - 6, horizonY - 1, cx + 6, horizonY - 1,
            c, alpha * (.28 + .25 * proximity), 1.1);
        });
      } else if (glide) {
        // Glide is a steep, high-energy descent corridor rather than the
        // horizontal travel packets used by supercruise and normal flight.
        [leftMid, rightMid].forEach((cx) => {
          const bayHalf = Math.max(10, (g.centerLeft - g.left) * .42);
          this.line(cx - bayHalf, y - 10, cx - 5, horizonY, c, alpha * .5, 1.2);
          this.line(cx + bayHalf, y - 10, cx + 5, horizonY, c, alpha * .5, 1.2);
          for (let gate = 0; gate < 4; gate += 1) {
            const progress = (p * (1.65 + vertical) + gate / 4) % 1;
            const py = y - 9 + progress * 15;
            const halfWidth = bayHalf * (1 - progress * .68);
            const fade = Math.sin(progress * Math.PI);
            this.line(cx - halfWidth, py, cx - 3, py, c, alpha * fade * .58, 1);
            this.line(cx + 3, py, cx + halfWidth, py, c, alpha * fade * .58, 1);
          }
          const markerY = y - 5 + wave(p) * 6;
          this.path([[cx - 4, markerY - 2], [cx, markerY + 2], [cx + 4, markerY - 2]],
            c, alpha * .8, 1.4);
        });
      } else {
        // Low-altitude approach/departure gets an animated radar altimeter.
        // Direction is vertical and journal-derived velocity changes its rate.
        [leftMid, rightMid].forEach((cx) => {
          const bayHalf = Math.max(10, (g.centerLeft - g.left) * .4);
          this.line(cx - bayHalf, y - 9, cx - 5, horizonY, c, alpha * .36, 1);
          this.line(cx + bayHalf, y - 9, cx + 5, horizonY, c, alpha * .36, 1);
          for (let rung = 0; rung < 5; rung += 1) {
            const progress = (p * (.78 + vertical) + rung / 5) % 1;
            const travel = departing ? 1 - progress : progress;
            const py = y - 9 + travel * 15;
            const halfWidth = 2.5 + travel * (bayHalf - 4);
            this.line(cx - halfWidth, py, cx - 1.5, py, c,
              alpha * Math.sin(progress * Math.PI) * .52, 1);
            this.line(cx + 1.5, py, cx + halfWidth, py, c,
              alpha * Math.sin(progress * Math.PI) * .52, 1);
          }
          const markerY = departing ? y - 5 - wave(p) * 3 : y - 5 + wave(p) * 5;
          this.path(departing
            ? [[cx - 4, markerY + 2], [cx, markerY - 2], [cx + 4, markerY + 2]]
            : [[cx - 4, markerY - 2], [cx, markerY + 2], [cx + 4, markerY - 2]],
          c, alpha * .78, 1.35);
        });
      }
      if (d.landingGear) {
        this.line(g.centerLeft - 10, y + 10, g.centerLeft - 4, y + 5, c, alpha * .75, 1.4);
        this.line(g.centerRight + 10, y + 10, g.centerRight + 4, y + 5, c, alpha * .75, 1.4);
      }
    }

    drawSRV(g, state, p, alpha, armoured = false) {
      const c = state.color, y = g.y, d = state.dynamics;
      const gravityLoad = clamp(d.gravity / 4);
      const analysis = d.analysisMode && !armoured;
      for (const [start, end, direction] of [
        [g.left + 4, g.centerLeft - 5, 1], [g.centerRight + 5, g.right - 4, -1],
      ]) {
        const width = end - start;
        const terrain = [];
        for (let i = 0; i <= 28; i += 1) {
          const progress = i / 28;
          const ripple = Math.sin((progress * 2 + p) * TAU) * 1.4
            + Math.sin((progress * 5 - p * 1.4) * TAU) * .65;
          terrain.push([start + width * progress, y + 8 + ripple]);
        }
        this.path(terrain, c, alpha * .46, 1.1);

        const cx = (start + end) / 2;
        const suspension = Math.sin(p * TAU * 2) * (armoured ? .35 : .65) + gravityLoad;
        const chassisY = y + 1 + suspension;
        const half = armoured ? 13 : 11;
        this.path([
          [cx - half, chassisY + 2], [cx - half + 3, chassisY - 4],
          [cx + half - 4, chassisY - 4], [cx + half, chassisY + 2],
        ], c, alpha * .82, armoured ? 1.6 : 1.3);
        this.line(cx - half + 3, chassisY + 3, cx + half - 3, chassisY + 3,
          c, alpha * .55, 1.1);

        const wheelAngle = p * TAU * (armoured ? 1.45 : 2.1) * direction;
        for (const offset of [-half + 3, 0, half - 3]) {
          const wx = cx + offset;
          const wy = chassisY + 6;
          this.arc(wx, wy, armoured ? 3.1 : 2.7, armoured ? 3.1 : 2.7,
            0, TAU, c, alpha * .7, 1.15);
          this.line(wx, wy, wx + Math.cos(wheelAngle + offset) * 2,
            wy + Math.sin(wheelAngle + offset) * 2, c, alpha * .64, 1);
        }

        if (armoured) {
          const turretDirection = direction * (4 + wave(p) * 4);
          this.rect(cx - 4, chassisY - 8, 8, 3.5, c, alpha * .7);
          this.line(cx, chassisY - 7, cx + turretDirection, chassisY - 9,
            c, alpha * .8, 1.5);
          for (let i = 0; i < 3; i += 1) {
            const packet = (p * 1.25 + i / 3) % 1;
            const x = direction > 0 ? start + width * packet : end - width * packet;
            this.chevron(x, y - 10, direction, c,
              alpha * Math.sin(packet * Math.PI) * .48, 2.2);
          }
        } else {
          this.line(cx, chassisY - 4, cx, chassisY - 10, c, alpha * .72, 1.2);
          this.dot(cx, chassisY - 11, 1.2, c, alpha * (.58 + .3 * wave(p * 1.5)));
          if (analysis) {
            const sweep = (p + (direction < 0 ? .5 : 0)) % 1;
            const x = start + width * sweep;
            this.line(x, y - 11, x, y + 9, c,
              alpha * Math.sin(sweep * Math.PI) * .72, 1.25);
          }
        }
      }
    }

    drawNomad(g, state, p, alpha) {
      const c = state.color, y = g.y, d = state.dynamics;
      const vertical = clamp(Math.abs(d.vertical) / 80);
      for (const [start, end, direction] of [
        [g.left + 3, g.centerLeft - 5, 1], [g.centerRight + 5, g.right - 3, -1],
      ]) {
        const width = end - start;
        const cx = (start + end) / 2;
        const hover = 1.2 + wave(p) * (1.3 + vertical * 1.8);
        this.line(start + 2, y + 10, end - 2, y + 10, c, alpha * .3, 1);
        for (let i = 0; i < 5; i += 1) {
          const progress = (p * .72 + i / 5) % 1;
          const x = start + width * progress;
          const height = 1 + Math.sin(progress * Math.PI) * 4;
          this.line(x, y + 10, x + direction * height, y + 8 - height,
            c, alpha * Math.sin(progress * Math.PI) * .38, 1);
        }

        const craftY = y - hover;
        this.path([
          [cx - 14, craftY + 2], [cx - 9, craftY - 4], [cx - 2, craftY - 6],
          [cx + 10, craftY - 3], [cx + 15, craftY + 2], [cx + 7, craftY + 4],
          [cx - 8, craftY + 4], [cx - 14, craftY + 2],
        ], c, alpha * .86, 1.35, true, .04);
        for (const offset of [-8, 0, 8]) {
          const plume = 3 + wave(p + offset * .07) * (4 + vertical * 4);
          this.line(cx + offset, craftY + 4, cx + offset - direction * .8,
            craftY + 4 + plume, c, alpha * .5, 1.3);
        }

        this.path([[start + 3, y - 10], [cx, y - 4], [end - 3, y - 10]],
          c, alpha * .28, 1);
        const nav = (p * .58 + .12) % 1;
        const navX = direction > 0 ? start + width * nav : end - width * nav;
        this.chevron(navX, y - 9, direction, c,
          alpha * (.35 + .45 * wave(nav)), 2.6);
      }
    }

    drawFighter(g, state, p, alpha) {
      const c = state.color, y = g.y;
      for (const [start, end, direction] of [
        [g.left + 3, g.centerLeft - 5, 1], [g.centerRight + 5, g.right - 3, -1],
      ]) {
        const width = end - start;
        const cx = (start + end) / 2;
        const lockX = cx + Math.sin(p * TAU) * width * .07;
        const lockY = y + Math.cos(p * TAU * 2) * 2.5;

        this.line(start, y - 11, cx, lockY - 3, c, alpha * .3, 1);
        this.line(start, y + 11, cx, lockY + 3, c, alpha * .3, 1);
        this.line(end, y - 11, cx, lockY - 3, c, alpha * .3, 1);
        this.line(end, y + 11, cx, lockY + 3, c, alpha * .3, 1);
        this.arc(lockX, lockY, 8, 6, -.72, .72, c, alpha * .66, 1.2);
        this.arc(lockX, lockY, 8, 6, Math.PI - .72, Math.PI + .72,
          c, alpha * .66, 1.2);
        this.dot(lockX, lockY, .9, c, alpha * (.55 + .35 * wave(p * 2)));

        const bank = Math.sin(p * TAU) * 3.2;
        this.path([
          [cx + direction * 9, y + bank], [cx - direction * 6, y - 4 - bank * .25],
          [cx - direction * 2, y + bank], [cx - direction * 6, y + 4 - bank * .25],
          [cx + direction * 9, y + bank],
        ], c, alpha * .9, 1.4);
        for (let i = 0; i < 4; i += 1) {
          const progress = (p * 1.75 + i / 4) % 1;
          const x = direction > 0 ? start + width * progress : end - width * progress;
          const fade = Math.sin(progress * Math.PI);
          this.line(x - direction * (3 + progress * 7), y - 8 + i * 5, x,
            y - 8 + i * 5, c, alpha * fade * .62, 1 + progress * .5);
        }
      }
    }

    drawOnFoot(g, state, p, alpha) {
      const c = state.color, y = g.y;
      for (let i = 0; i < 7; i += 1) {
        const progress = (p + i / 7) % 1;
        const point = this.trackPoint(progress, g, y + (i % 2 ? 4 : -4));
        this.arc(point.x, point.y, 2.2, 1.1, 0, TAU, c,
          alpha * (.2 + .72 * (1 - progress)), 1.1);
      }
      this.trackStroke(p * .72, .035, g, y, c, alpha * .45);
    }

    drawDocked(g, state, p, alpha, station = false) {
      const c = state.color, y = g.y;
      const pulse = .45 + .45 * wave(p);
      [[g.left + 5, g.centerLeft - 7], [g.centerRight + 7, g.right - 5]].forEach(([start, end], side) => {
        const cx = (start + end) / 2;
        const spread = station ? 24 : 18;
        this.path([[cx - spread, y - 9], [cx - spread, y + 9], [cx - spread + 7, y + 9]], c, alpha * .55, 1.2);
        this.path([[cx + spread, y - 9], [cx + spread, y + 9], [cx + spread - 7, y + 9]], c, alpha * .55, 1.2);
        this.line(cx - spread + 4, y, cx + spread - 4, y, c, alpha * .32);
        this.rect(cx - 5, y - 3, 10, 6, c, alpha * pulse);
        if (station) this.arc(cx, y, 31, 10, 0, TAU, c, alpha * .22);
      });
    }

    drawHandoff(g, state, p, alpha, key) {
      const c = state.color, y = g.y;
      const deploy = key.startsWith("vehicle_deploy");
      const board = key.startsWith("vehicle_board");
      const travel = board ? 1 - p : p;
      const vehicle = key.endsWith("fighter") ? "fighter"
        : key.endsWith("nomad") ? "nomad"
          : key.endsWith("scorpion") ? "scorpion"
          : key.endsWith("crew") ? "crew"
            : "ground";
      for (const edge of [g.centerLeft, g.centerRight]) {
        this.line(edge, y - 10, edge, y + 10, c, alpha * .58);
      }
      const point = this.trackPoint(travel, g);
      if (vehicle === "fighter") this.ship(point.x, y, c, alpha, .72, deploy ? 1 : -1);
      else if (vehicle === "nomad") {
        const direction = deploy ? 1 : -1;
        this.path([
          [point.x + 7 * direction, y], [point.x - 4 * direction, y - 4],
          [point.x - 7 * direction, y + 1], [point.x - 3 * direction, y + 4],
          [point.x + 7 * direction, y],
        ], c, alpha, 1.25);
        this.line(point.x - 2, y + 4, point.x - 2, y + 9,
          c, alpha * .55, 1.2);
        this.line(point.x + 2, y + 3, point.x + 2, y + 8,
          c, alpha * .55, 1.2);
      }
      else if (vehicle === "scorpion") {
        this.rect(point.x - 5, y - 3, 10, 6, c, alpha);
        this.rect(point.x - 3, y - 6, 6, 2.5, c, alpha * .78);
        this.line(point.x, y - 5, point.x + (deploy ? 6 : -6), y - 7,
          c, alpha * .82, 1.3);
        this.dot(point.x - 3, y + 5, 1.4, c, alpha);
        this.dot(point.x + 3, y + 5, 1.4, c, alpha);
      }
      else if (vehicle === "crew") {
        this.dot(point.x - 3, y, 1.4, c, alpha);
        this.dot(point.x + 3, y, 1.4, c, alpha);
        this.line(point.x - 2, y, point.x + 2, y, c, alpha);
      } else {
        this.rect(point.x - 4, y - 2.5, 8, 5, c, alpha);
        this.dot(point.x - 2.5, y + 4, 1.2, c, alpha);
        this.dot(point.x + 2.5, y + 4, 1.2, c, alpha);
      }
      this.trackStroke(travel, .09, g, y, c, alpha * .56);
    }

    drawHazard(g, state, p, alpha, key) {
      const c = state.color, y = g.y;
      if (key === "asteroid_field") {
        for (let i = 0; i < 12; i += 1) {
          const progress = (hash(i + 8) + p * (.08 + hash(i + 31) * .12)) % 1;
          const point = this.trackPoint(progress, g, y + (hash(i + 51) - .5) * 17);
          const radius = 1.7 + hash(i + 71) * 2.8;
          const sides = 5 + (i % 3), points = [];
          for (let n = 0; n < sides; n += 1) {
            const angle = n / sides * TAU + p * (i % 2 ? -1 : 1);
            points.push([point.x + Math.cos(angle) * radius, point.y + Math.sin(angle) * radius]);
          }
          this.path(points, c, alpha * (.28 + hash(i) * .46), 1, true);
        }
        return;
      }
      const danger = ["combat", "interdiction", "interdicted", "signal_threat"].includes(key);
      const bite = (danger ? 7 : 4) + wave(p) * (danger ? 5 : 3);
      for (const side of [-1, 1]) {
        const inner = side < 0 ? g.centerLeft : g.centerRight;
        const outer = side < 0 ? g.left : g.right;
        const direction = side < 0 ? 1 : -1;
        this.path([
          [outer, y - 8], [outer + direction * bite, y], [outer, y + 8],
        ], c, alpha * .72, danger ? 1.8 : 1.2);
        this.path([
          [inner - direction * 6, y - 10], [inner, y - 5], [inner, y + 5], [inner - direction * 6, y + 10],
        ], c, alpha * (.55 + .35 * wave(p)), danger ? 1.8 : 1.2);
      }
      const points = [];
      for (let i = 0; i <= 40; i += 1) {
        const progress = i / 40;
        const point = this.trackPoint(progress, g);
        const frequency = key === "interdiction" || key === "interdicted" ? 7 : 3;
        const amplitude = danger ? 6 : 3;
        points.push([point.x, y + Math.sin((progress * frequency - p * 3) * TAU) * amplitude, point.wing]);
      }
      this.splitPath(points, c, alpha * .58, danger ? 1.5 : 1);
    }

    drawMusicState(g, state, p, alpha, key) {
      const c = state.color, y = g.y;
      const cx = g.center;
      const span = Math.max(24, g.right - g.left);

      if (key === "phenomena") {
        // Organic structures and fog-cloud life use slow, phase-locked sensor
        // tendrils with cellular contacts instead of an ordinary FSS sweep.
        for (let strand = 0; strand < 4; strand += 1) {
          const points = [];
          for (let step = 0; step <= 36; step += 1) {
            const travel = step / 36;
            const x = g.left + travel * span;
            const envelope = Math.sin(travel * Math.PI);
            const py = y + Math.sin((travel * (1.25 + strand * .25)
              + p * (strand % 2 ? -1 : 1) + strand / 4) * TAU)
              * (2.2 + strand * .8) * envelope;
            points.push([x, py]);
          }
          this.path(points, c, alpha * (.15 + strand * .075), 1);
        }
        for (let cell = 0; cell < 6; cell += 1) {
          const orbit = 8 + cell * span * .045;
          const angle = p * TAU * (cell % 2 ? -1 : 1) + hash(cell + 631) * TAU;
          const x = cx + Math.cos(angle) * orbit;
          const py = y + Math.sin(angle) * orbit * .23;
          const pulse = .3 + .6 * wave(p + cell * .13);
          this.arc(x, py, 2 + hash(cell + 653) * 2.5,
            1.2 + hash(cell + 677) * 1.5, 0, TAU, c, alpha * pulse, 1);
          if (cell % 2 === 0) this.dot(x, py, .65, c, alpha * pulse);
        }
        this.arc(cx, y, 11 + 2 * wave(p), 5 + wave(p), 0, TAU,
          c, alpha * .34, 1.15);
        return;
      }

      if (key === "srv_threat") {
        const horizon = y + 8;
        this.line(g.left + 2, horizon, g.right - 2, horizon, c, alpha * .42, 1.2);
        for (let ridge = 0; ridge <= 24; ridge += 1) {
          if (!ridge) continue;
          const previous = (ridge - 1) / 24;
          const travel = ridge / 24;
          this.line(g.left + previous * span,
            horizon + Math.sin((previous * 3 + p) * TAU) * 1.2,
            g.left + travel * span,
            horizon + Math.sin((travel * 3 + p) * TAU) * 1.2,
            c, alpha * .26, 1);
        }
        const targetX = cx + Math.sin(p * TAU) * span * .27;
        const targetY = y - 1 + Math.cos(p * TAU * 2) * 2.5;
        const lock = 7 + wave(p * 2) * 3;
        this.arc(targetX, targetY, lock, lock * .58, -.72, .72,
          c, alpha * .78, 1.5);
        this.arc(targetX, targetY, lock, lock * .58, Math.PI - .72,
          Math.PI + .72, c, alpha * .78, 1.5);
        this.dot(targetX, targetY, 1.1, c, alpha * .88);
        for (let packet = 0; packet < 4; packet += 1) {
          const progress = (p * 1.5 + packet / 4) % 1;
          const x = g.left + progress * span;
          this.chevron(x, y - 9 + packet * 5, packet % 2 ? -1 : 1,
            c, alpha * Math.sin(progress * Math.PI) * .62, 2.6);
        }
        return;
      }

      if (key === "capital_contact") {
        // A broad, slow contact that occupies the sensor field rather than
        // borrowing the twitchier dogfight waveform.
        const half = Math.min(span * .38, 47);
        this.path([
          [cx - half, y], [cx - half * .72, y - 6], [cx + half * .54, y - 8],
          [cx + half, y - 2], [cx + half * .82, y + 5],
          [cx - half * .6, y + 7], [cx - half, y],
        ], c, alpha * .62, 1.35, true, .035);
        for (let segment = 0; segment < 6; segment += 1) {
          const x = cx - half * .55 + segment * half * .22;
          this.line(x, y - 5, x + 5, y + 5, c,
            alpha * (.2 + .35 * wave(p + segment / 6)), 1);
        }
        const sweep = cx - half + (half * 2) * wave(p * .5);
        this.line(sweep, y - 11, sweep, y + 11, c, alpha * .58, 1.25);
        const bracket = half + 4 + wave(p) * 3;
        this.path([[cx - bracket, y - 11], [cx - bracket + 7, y - 11],
          [cx - bracket + 7, y - 7]], c, alpha * .7, 1.4);
        this.path([[cx + bracket, y + 11], [cx + bracket - 7, y + 11],
          [cx + bracket - 7, y + 7]], c, alpha * .7, 1.4);
        return;
      }

      if (key === "unknown_contact") {
        for (let echo = 0; echo < 4; echo += 1) {
          const phase = (p + echo / 4) % 1;
          const fade = Math.sin(phase * Math.PI);
          const radius = 5 + smooth(phase) * span * .38;
          this.angularRing(cx, y, radius, 2.5 + radius * .18,
            5 + echo % 3, c, alpha * fade * .48, 1.1,
            p * TAU * (echo % 2 ? -.5 : .5));
        }
        for (let contact = 0; contact < 5; contact += 1) {
          const x = g.left + 8 + hash(contact + 709) * (span - 16);
          const py = y + (hash(contact + 733) - .5) * 17;
          const pulse = Math.pow(wave(p + hash(contact + 761)), 2);
          this.path([[x, py - 2.8], [x + 2.5, py + 2], [x - 2.5, py + 2]],
            c, alpha * pulse * .7, 1, true);
        }
        this.line(cx - 5, y, cx + 5, y, c, alpha * (.28 + .48 * wave(p * 2)), 1.2);
        return;
      }

      if (key === "heavy_combat") {
        for (let lane = 0; lane < 4; lane += 1) {
          const direction = lane % 2 ? -1 : 1;
          const progress = (p * 1.75 + lane / 4) % 1;
          const x = direction > 0
            ? g.left + progress * span : g.right - progress * span;
          const py = y - 8 + lane * 5.2;
          this.line(x - direction * (5 + progress * 8), py, x, py,
            c, alpha * Math.sin(progress * Math.PI) * .8, 1.5);
          this.chevron(x, py, direction, c,
            alpha * Math.sin(progress * Math.PI) * .72, 2.8);
        }
        for (const side of [-1, 1]) {
          const contactX = cx + side * span * (.19 + .04 * Math.sin(p * TAU));
          const contactY = y + side * Math.cos(p * TAU * 2) * 3;
          this.arc(contactX, contactY, 8, 5, -.7, .7, c, alpha * .68, 1.4);
          this.arc(contactX, contactY, 8, 5, Math.PI - .7, Math.PI + .7,
            c, alpha * .68, 1.4);
        }
        this.path([[cx - 4, y - 10], [cx, y - 5], [cx + 4, y - 10]],
          c, alpha * (.48 + .42 * wave(p * 3)), 1.5);
        this.path([[cx - 4, y + 10], [cx, y + 5], [cx + 4, y + 10]],
          c, alpha * (.48 + .42 * wave(p * 3)), 1.5);
        return;
      }

      if (key === "docking_assist") {
        for (let gate = 0; gate < 5; gate += 1) {
          const progress = (p + gate / 5) % 1;
          const fade = Math.sin(progress * Math.PI);
          const x = g.left + 5 + progress * (span - 10);
          const halfHeight = 10 - progress * 6;
          this.path([[x - 3, y - halfHeight], [x, y - halfHeight - 2],
            [x + 3, y - halfHeight]], c, alpha * fade * .5, 1.1);
          this.path([[x - 3, y + halfHeight], [x, y + halfHeight + 2],
            [x + 3, y + halfHeight]], c, alpha * fade * .5, 1.1);
        }
        const padWidth = 13 + wave(p) * 2;
        this.path([[cx - padWidth, y + 7], [cx - padWidth + 4, y + 2],
          [cx + padWidth - 4, y + 2], [cx + padWidth, y + 7]],
        c, alpha * .72, 1.4);
        this.line(cx - 5, y + 5, cx + 5, y + 5, c, alpha * .7, 1.3);
        this.glowDot(cx, y + 5, 1.1, c, alpha * (.55 + .35 * wave(p * 2)));
        return;
      }

      if (key === "settlement_area") {
        const horizon = y + 6;
        this.line(g.left + 2, horizon, g.right - 2, horizon, c, alpha * .44, 1.2);
        const buildings = [
          [-.34, 8, 7], [-.18, 13, 10], [.02, 9, 6], [.2, 16, 11], [.37, 7, 5],
        ];
        buildings.forEach(([offset, width, height], index) => {
          const x = cx + offset * span - width / 2;
          this.rect(x, horizon - height, width, height, c,
            alpha * (.28 + .18 * wave(p + index * .14)));
          this.dot(x + width * .5, horizon - height - 2, .7, c,
            alpha * (.32 + .45 * wave(p + index * .19)));
        });
        for (let lane = 0; lane < 4; lane += 1) {
          const progress = (p + lane / 4) % 1;
          const x = g.left + 4 + progress * (span - 8);
          this.line(x, horizon + 1, cx, y + 1, c,
            alpha * Math.sin(progress * Math.PI) * .22, 1);
        }
        const scanX = cx + Math.sin(p * TAU) * span * .43;
        this.line(scanX, y - 11, scanX, horizon + 2, c, alpha * .52, 1.15);
        return;
      }

      if (key === "local_arrival") {
        for (let bracket = 0; bracket < 4; bracket += 1) {
          const progress = (p + bracket / 4) % 1;
          const fade = Math.sin(progress * Math.PI);
          const distance = span * .44 * (1 - smooth(progress));
          const height = 3 + (1 - progress) * 7;
          for (const side of [-1, 1]) {
            const x = cx + side * distance;
            this.line(x, y - height, x, y + height, c,
              alpha * fade * .62, 1.25);
          }
        }
        const destination = cx + span * .18;
        this.angularRing(destination, y, 7 + wave(p) * 2, 5 + wave(p),
          6, c, alpha * .66, 1.3, Math.PI / 6);
        this.glowDot(destination, y, 1.3, c, alpha * .88);
        for (let packet = 0; packet < 3; packet += 1) {
          const progress = (p + packet / 3) % 1;
          const x = g.left + 5 + progress * (destination - g.left - 7);
          this.line(x - 6, y - 6 + packet * 6, x, y - 6 + packet * 6,
            c, alpha * Math.sin(progress * Math.PI) * .62, 1.3);
        }
      }
    }

    drawPanelState(g, state, p, alpha, key) {
      const c = state.color, y = g.y;
      const cx = g.center;
      const span = Math.max(24, g.right - g.left);

      if (key === "left_panel" || key === "right_panel") {
        const fromLeft = key === "left_panel";
        const edge = fromLeft ? g.left + 3 : g.right - 3;
        const inner = fromLeft ? g.right - 5 : g.left + 5;
        const direction = fromLeft ? 1 : -1;
        const panelEdge = edge + direction * span * (.22 + .06 * wave(p));

        // Direction is literal: External/left focus resolves from port, while
        // Internal/right focus resolves from starboard.
        this.path(fromLeft
          ? [[edge, y - 11], [panelEdge, y - 8], [panelEdge, y + 8], [edge, y + 11]]
          : [[edge, y - 11], [panelEdge, y - 8], [panelEdge, y + 8], [edge, y + 11]],
        c, alpha * .62, 1.35);
        for (let row = 0; row < 5; row += 1) {
          const rowY = y - 9 + row * 4.5;
          const width = span * (.31 + hash(row + (fromLeft ? 853 : 877)) * .42);
          this.line(edge, rowY, edge + direction * width, rowY,
            c, alpha * (.2 + row * .07), row === 2 ? 1.4 : 1);
          const progress = (p + row / 5) % 1;
          const x = edge + direction * width * progress;
          this.line(x - direction * 4, rowY, x, rowY, c,
            alpha * Math.sin(progress * Math.PI) * .76, 1.5);
        }
        const cursor = edge + direction * span * (.12 + .75 * wave(p * .5));
        this.line(cursor, y - 11, cursor, y + 11, c, alpha * .54, 1.15);
        this.chevron(cursor - direction * 3, y, direction, c, alpha * .78, 2.7);
        this.line(panelEdge, y, inner, y, c, alpha * .18, 1);
        return;
      }

      if (key === "comms_panel") {
        const channels = [-6, 0, 6];
        channels.forEach((channelY, channel) => {
          const points = [];
          for (let step = 0; step <= 38; step += 1) {
            const travel = step / 38;
            const envelope = Math.sin(travel * Math.PI);
            const x = g.left + travel * span;
            const py = y + channelY
              + Math.sin((travel * (2 + channel) - p * (1 + channel * .25)) * TAU)
              * envelope * (1.2 + channel * .5);
            points.push([x, py]);
          }
          this.path(points, c, alpha * (.2 + channel * .12), channel === 1 ? 1.35 : 1);
        });
        for (let message = 0; message < 4; message += 1) {
          const progress = (p + message / 4) % 1;
          const fade = Math.sin(progress * Math.PI);
          const x = g.left + 5 + progress * (span - 10);
          const py = y - 9 + message * 6;
          this.rect(x - 3, py - 1.5, 6, 3, c, alpha * fade * .58, true);
          this.line(x - 7, py, x - 3, py, c, alpha * fade * .42, 1);
        }
        this.path([[cx - 7, y - 10], [cx, y - 7], [cx + 7, y - 10]],
          c, alpha * (.32 + .32 * wave(p * 2)), 1.15);
        return;
      }

      if (key === "role_panel") {
        const floor = y + 10;
        this.line(g.left + 3, floor, g.right - 3, floor, c, alpha * .5, 1.25);
        for (let slot = 0; slot < 5; slot += 1) {
          const x = g.left + span * (slot + .5) / 5;
          const reveal = .25 + .75 * wave(p * .5 + slot * .08);
          const height = (6 + (slot % 2) * 4) * reveal;
          this.path([[x - 6, floor], [x - 5, floor - height],
            [x + 5, floor - height], [x + 6, floor]],
          c, alpha * (.28 + slot * .075), 1.1, false,
          slot === Math.floor(p * 5) % 5 ? .08 : 0);
          const active = slot === Math.floor(p * 5) % 5;
          this.dot(x, floor - height - 2, active ? 1.45 : .7, c,
            alpha * (active ? .82 : .35));
        }
        const selector = g.left + span * ((Math.floor(p * 5) + .5) / 5);
        this.path([[selector - 4, y - 10], [selector, y - 6],
          [selector + 4, y - 10]], c, alpha * .72, 1.35);
        return;
      }

      // Station Services uses an orderly menu matrix with a single moving
      // focus cell. It stays visually separate from Docking Assist's corridor.
      const columns = 4, rows = 2;
      const cellWidth = Math.min(18, span / columns - 4);
      const activeFloat = p * columns * rows;
      const active = Math.floor(activeFloat) % (columns * rows);
      for (let cell = 0; cell < columns * rows; cell += 1) {
        const column = cell % columns, row = Math.floor(cell / columns);
        const x = g.left + span * (column + .5) / columns;
        const py = y - 6 + row * 12;
        const selected = cell === active;
        this.rect(x - cellWidth / 2, py - 4, cellWidth, 8, c,
          alpha * (selected ? .8 : .28), selected);
        this.line(x - cellWidth * .3, py, x + cellWidth * .3, py,
          c, alpha * (selected ? .72 : .2), 1);
      }
      const sweep = g.left + (activeFloat % 1) * span;
      this.line(sweep, y - 11, sweep, y + 11, c,
        alpha * Math.sin((activeFloat % 1) * Math.PI) * .36, 1);
    }

    drawCarrier(g, state, p, alpha, arrival = false) {
      const c = state.color, y = g.y;
      if (arrival) {
        this.drawArrival(g, state, p, alpha);
      }
      const travel = arrival ? .5 : p;
      const point = this.trackPoint(travel, g);
      const points = [
        [point.x - 9, y - 2], [point.x - 5, y - 6], [point.x + 7, y - 4],
        [point.x + 10, y], [point.x + 7, y + 4], [point.x - 5, y + 6],
      ];
      this.path(points, c, alpha * .9, 1.4, true, .12);
      if (!arrival) this.trackStroke(travel, .16, g, y, c, alpha * .72, 2);
      for (const progress of [.16, .34, .66, .84]) {
        const gate = this.trackPoint(progress, g);
        const height = 5 + 4 * wave(p + progress);
        this.line(gate.x, y - height, gate.x, y + height, c, alpha * .34);
      }
    }

    drawCruiseAssist(g, state, p, alpha) {
      const c = state.color, y = g.y;
      const cx = (g.left + g.right) / 2;
      const span = Math.max(28, g.right - g.left);
      // Supercruise Assist is a closed guidance solution: paired rails feed a
      // stable acquisition gate instead of Supercruise's expanding tunnel.
      this.line(g.left + 2, y - 9, cx - 8, y - 2, c, alpha * .42, 1);
      this.line(g.left + 2, y + 9, cx - 8, y + 2, c, alpha * .42, 1);
      this.line(g.right - 2, y - 9, cx + 8, y - 2, c, alpha * .42, 1);
      this.line(g.right - 2, y + 9, cx + 8, y + 2, c, alpha * .42, 1);
      for (let guide = 0; guide < 4; guide += 1) {
        const progress = (p + guide / 4) % 1;
        const fade = Math.sin(progress * Math.PI);
        const distance = (1 - smooth(progress)) * span * .43;
        for (const side of [-1, 1]) {
          const x = cx + side * distance;
          this.chevron(x, y, -side, c, alpha * fade * .72, 3.2);
        }
      }
      const lock = 7 + 2 * wave(p * 2);
      this.path([[cx - lock, y - 7], [cx - lock, y - 2], [cx - 3, y - 2]],
        c, alpha * .8, 1.3);
      this.path([[cx + lock, y + 7], [cx + lock, y + 2], [cx + 3, y + 2]],
        c, alpha * .8, 1.3);
      this.glowDot(cx, y, 1.2, c, alpha * (.68 + .3 * wave(p)));
    }

    drawControlMode(g, state, p, alpha, key) {
      const c = state.color, y = g.y;
      const cx = (g.left + g.right) / 2;
      const span = Math.max(24, g.right - g.left);
      if (key === "silent_running") {
        // Suppressed emissions: a damped signature repeatedly collapses into
        // the centre while the outer hull remains deliberately dark.
        const envelope = .24 + .76 * wave(p);
        const points = [];
        for (let step = 0; step <= 24; step += 1) {
          const progress = step / 24;
          const x = g.left + progress * span;
          const falloff = Math.sin(progress * Math.PI);
          points.push([x, y + Math.sin((progress * 3 + p) * TAU) * 2.2 * falloff * envelope]);
        }
        this.path(points, c, alpha * (.18 + envelope * .32), 1);
        this.angularRing(cx, y, 5 + 5 * (1 - envelope), 3 + 2 * (1 - envelope),
          6, c, alpha * (.25 + envelope * .35), 1, Math.PI / 6);
        this.line(g.left + 2, y - 10, g.left + span * .24, y - 10, c, alpha * .22, 1);
        this.line(g.right - span * .24, y + 10, g.right - 2, y + 10, c, alpha * .22, 1);
        return;
      }
      // Flight Assist Off permits lateral drift. Two inertial vectors slide
      // out of phase while the centre datum remains fixed.
      const drift = Math.sin(p * TAU) * span * .18;
      this.line(g.left + 3, y, g.right - 3, y, c, alpha * .2, 1);
      this.path([[cx - 5 + drift, y - 9], [cx + drift, y], [cx - 5 + drift, y + 9]],
        c, alpha * .78, 1.4);
      this.path([[cx + 5 - drift, y - 9], [cx - drift, y], [cx + 5 - drift, y + 9]],
        c, alpha * .46, 1.1);
      for (const side of [-1, 1]) {
        const x = cx + side * (span * .24 + drift * .45);
        this.line(x, y - 6, x + side * 7, y - 2, c, alpha * .48, 1.1);
        this.line(x, y + 6, x + side * 7, y + 2, c, alpha * .48, 1.1);
      }
    }

    drawSurfaceControl(g, state, p, alpha, key) {
      const c = state.color, y = g.y;
      const cx = (g.left + g.right) / 2;
      const span = Math.max(24, g.right - g.left);
      if (key === "srv_handbrake") {
        const clampWidth = 9 + 3 * wave(p);
        this.line(g.left + 4, y + 7, g.right - 4, y + 7, c, alpha * .34, 1.2);
        this.path([[cx - clampWidth - 6, y - 8], [cx - clampWidth, y - 3],
          [cx - clampWidth, y + 6], [cx - 3, y + 6]], c, alpha * .78, 1.5);
        this.path([[cx + clampWidth + 6, y - 8], [cx + clampWidth, y - 3],
          [cx + clampWidth, y + 6], [cx + 3, y + 6]], c, alpha * .78, 1.5);
        this.line(cx - 4, y, cx + 4, y, c, alpha * .56, 1.4);
        return;
      }
      if (key === "srv_turret") {
        const angle = p * TAU;
        this.arc(cx, y, span * .28, 9, Math.PI * 1.08, Math.PI * 1.92,
          c, alpha * .38, 1.1);
        this.line(cx, y, cx + Math.cos(angle) * span * .35,
          y + Math.sin(angle) * 9, c, alpha * .82, 1.4);
        this.angularRing(cx, y, 7, 5, 8, c, alpha * .62, 1.2, -angle * .5);
        this.glowDot(cx + Math.cos(angle) * span * .35,
          y + Math.sin(angle) * 9, 1.1, c, alpha * .84);
        return;
      }
      // Drive Assist owns a ground guidance lane with a bounded correction
      // packet rather than the ordinary SRV suspension motion.
      for (const offset of [-6, 6]) {
        this.line(g.left + 3, y + offset, g.right - 3, y + offset,
          c, alpha * .3, 1);
      }
      const point = this.trackPoint(p, g);
      this.path([[point.x - 5, y - 4], [point.x, y], [point.x - 5, y + 4]],
        c, alpha * .86, 1.4);
      for (const marker of [.2, .5, .8]) {
        const x = g.left + span * marker;
        this.line(x, y - 3, x, y + 3, c,
          alpha * (.28 + .28 * wave(p + marker)), 1);
      }
    }

    drawDockingState(g, state, p, alpha, denied = false) {
      const c = state.color, y = g.y;
      const cx = (g.left + g.right) / 2;
      const span = Math.max(24, g.right - g.left);
      if (denied) {
        const slam = 7 + wave(p * 2) * span * .19;
        this.line(cx - slam, y - 11, cx - slam, y + 11, c, alpha * .9, 1.8);
        this.line(cx + slam, y - 11, cx + slam, y + 11, c, alpha * .9, 1.8);
        this.path([[cx - 7, y - 6], [cx + 7, y + 6]], c, alpha * .72, 1.6);
        this.path([[cx + 7, y - 6], [cx - 7, y + 6]], c, alpha * .72, 1.6);
        return;
      }
      const travel = smooth(p);
      for (let gate = 0; gate < 4; gate += 1) {
        const progress = (travel + gate / 4) % 1;
        const fade = Math.sin(progress * Math.PI);
        const half = 4 + progress * span * .37;
        const height = 3 + progress * 8;
        this.path([[cx - half, y - height], [cx - half, y + height],
          [cx - half + 4, y + height]], c, alpha * fade * .62, 1.2);
        this.path([[cx + half, y - height], [cx + half, y + height],
          [cx + half - 4, y + height]], c, alpha * fade * .62, 1.2);
      }
      this.line(cx - 8, y, cx + 8, y, c, alpha * .7, 1.4);
      this.glowDot(cx, y, 1.2, c, alpha * (.62 + .34 * wave(p * 2)));
    }

    drawEmergency(g, state, p, alpha, key) {
      const c = state.color, y = g.y;
      const cx = (g.left + g.right) / 2;
      const span = Math.max(24, g.right - g.left);
      if (key === "heat_critical") {
        for (let band = 0; band < 5; band += 1) {
          const progress = (p + band / 5) % 1;
          const fade = Math.sin(progress * Math.PI);
          const x = g.left + 4 + progress * (span - 8);
          const rise = 3 + progress * 7;
          this.path([[x - 3, y + rise], [x, y - rise], [x + 3, y + rise]],
            c, alpha * fade * .7, band % 2 ? 1 : 1.4);
        }
        this.line(g.left + 2, y + 10, g.right - 2, y + 10,
          c, alpha * (.38 + .5 * wave(p * 2)), 1.8);
        return;
      }
      if (key === "jet_cone_damage") {
        for (let bolt = 0; bolt < 3; bolt += 1) {
          const offset = (bolt - 1) * 7;
          const jitter = (wave(p * 3 + bolt * .21) - .5) * 4;
          this.path([[g.left + 3, y + offset], [cx - 8, y - offset * .4 + jitter],
            [cx + 1, y + offset * .5 - jitter], [g.right - 3, y - offset]],
          c, alpha * (.35 + .2 * bolt), bolt === 1 ? 1.7 : 1.1);
        }
        this.angularRing(cx, y, 8 + 4 * wave(p * 2), 5 + 2 * wave(p * 2),
          6, c, alpha * .72, 1.3, p * TAU);
        return;
      }
      // Suit hazards use a life-support trace, visually separate from ship
      // heat and damage geometry.
      const points = [];
      for (let step = 0; step <= 24; step += 1) {
        const progress = step / 24;
        let pulse = 0;
        const local = (progress - p + 1) % 1;
        if (local > .42 && local < .48) pulse = -7 * Math.sin((local - .42) / .06 * Math.PI);
        if (local >= .48 && local < .56) pulse = 10 * Math.sin((local - .48) / .08 * Math.PI);
        points.push([g.left + progress * span, y + pulse]);
      }
      this.path(points, c, alpha * .78, 1.4);
      this.rect(g.right - 16, y - 9, 11, 18, c, alpha * .45, false);
      this.rect(g.right - 14, y + 3, 7, 4 + 3 * wave(p), c, alpha * .72, true);
    }

    drawMaintenance(g, state, p, alpha, reboot = false) {
      const c = state.color, y = g.y;
      const cx = (g.left + g.right) / 2;
      if (reboot) {
        const stage = Math.floor(p * 6);
        this.angularRing(cx, y, 9, 6, 6, c, alpha * .54, 1.2, Math.PI / 6);
        for (let index = 0; index < 6; index += 1) {
          const angle = index * TAU / 6;
          const active = index <= stage;
          this.line(cx + Math.cos(angle) * 11, y + Math.sin(angle) * 7,
            cx + Math.cos(angle) * 19, y + Math.sin(angle) * 11,
            c, alpha * (active ? .9 : .18), active ? 1.6 : 1);
        }
        this.glowDot(cx, y, 1 + 1.2 * wave(p * 2), c, alpha * .82);
        return;
      }
      const columns = 6;
      for (let index = 0; index < columns; index += 1) {
        const x = g.left + 4 + index * (g.right - g.left - 8) / columns;
        const active = index === Math.floor(p * columns) % columns;
        this.rect(x, y - 6, 7, 12, c, alpha * (active ? .78 : .24), active);
      }
      const sweep = g.left + 3 + p * (g.right - g.left - 6);
      this.line(sweep, y - 10, sweep, y + 10, c, alpha * .7, 1.3);
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
    }

    drawState(g, state, p, alpha) {
      if (alpha <= .002) return;
      const key = this.key(state);
      if (key === "flight" || key === "multicrew") {
        this.drawFlight(g, state, p, alpha, key); return;
      }
      if (key === "fighter") { this.drawFighter(g, state, p, alpha); return; }
      if (key === "exploration") { this.drawExploration(g, state, p, alpha); return; }
      if (key === "supercruise") { this.drawSupercruise(g, state, p, alpha); return; }
      if (key === "supercruise_overcharge") { this.drawSupercruise(g, state, p, alpha, true); return; }
      if (key === "supercruise_assist") { this.drawCruiseAssist(g, state, p, alpha); return; }
      if (key === "flight_assist_off" || key === "silent_running") {
        this.drawControlMode(g, state, p, alpha, key); return;
      }
      if (key === "fsd_charge" || key === "hyper_charge") {
        this.drawCharge(g, state, p, alpha, key === "hyper_charge"); return;
      }
      if (key === "hyperspace" || key === "jumping") {
        this.drawJump(g, state, p, alpha, key === "jumping"); return;
      }
      if (key === "arrival" || key === "interdiction_evaded") {
        this.drawArrival(g, state, p, alpha); return;
      }
      if (key === "fsd_cooldown") { this.drawCooldown(g, state, p, alpha); return; }
      if (key === "fss" || key === "dss") {
        this.drawScanner(g, state, p, alpha, key === "dss"); return;
      }
      if (["map", "galaxy_map", "system_map", "power_map", "orrery", "codex"].includes(key)) {
        this.drawMap(g, state, p, alpha, key); return;
      }
      if (PLANETARY.has(key) || key === "landed") {
        this.drawPlanet(g, state, p, alpha, key); return;
      }
      if (key === "srv" || key === "scorpion") {
        this.drawSRV(g, state, p, alpha, key === "scorpion"); return;
      }
      if (key === "nomad") { this.drawNomad(g, state, p, alpha); return; }
      if (["srv_handbrake", "srv_turret", "srv_drive_assist"].includes(key)) {
        this.drawSurfaceControl(g, state, p, alpha, key); return;
      }
      if (key === "on_foot") { this.drawOnFoot(g, state, p, alpha); return; }
      if (key === "docked" || key === "station") {
        this.drawDocked(g, state, p, alpha, key === "station"); return;
      }
      if (["phenomena", "srv_threat", "capital_contact", "unknown_contact",
        "heavy_combat", "docking_assist", "settlement_area",
        "local_arrival"].includes(key)) {
        this.drawMusicState(g, state, p, alpha, key); return;
      }
      if (["left_panel", "right_panel", "comms_panel", "role_panel",
        "station_services"].includes(key)) {
        this.drawPanelState(g, state, p, alpha, key); return;
      }
      if (key.startsWith("vehicle_")) { this.drawHandoff(g, state, p, alpha, key); return; }
      if (["mass_lock", "signal_lock", "signal_drop", "signal_threat", "combat",
        "interdiction", "interdicted", "asteroid_field"].includes(key)) {
        this.drawHazard(g, state, p, alpha, key); return;
      }
      if (key === "carrier_transit" || key === "carrier_arrival") {
        this.drawCarrier(g, state, p, alpha, key === "carrier_arrival"); return;
      }
      if (key === "docking_clearance" || key === "docking_denied") {
        this.drawDockingState(g, state, p, alpha, key === "docking_denied"); return;
      }
      if (["heat_critical", "suit_hazard", "jet_cone_damage"].includes(key)) {
        this.drawEmergency(g, state, p, alpha, key); return;
      }
      if (key === "maintenance" || key === "system_reboot") {
        this.drawMaintenance(g, state, p, alpha, key === "system_reboot"); return;
      }
      this.drawFlight(g, state, p, alpha, "flight");
    }

    eventColor(kind, fallback) {
      if (WARNING_EVENTS.has(kind) || kind === "dock_denied") return this.themeColor("orange", "#ff7a18");
      if (["survey_complete", "mapping_complete", "bio_sample", "data_sale", "touchdown",
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
      const value = getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
      return /^#[0-9a-f]{6}$/i.test(value) ? value : fallback;
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
      const c = p < .5 ? from.color : to.color;
      const left = g.centerLeft - (1 - Math.abs(p * 2 - 1)) * 13;
      const right = g.centerRight + (1 - Math.abs(p * 2 - 1)) * 13;
      this.line(left, g.y - 10, left, g.y + 10, c, .72 * Math.sin(p * Math.PI), 1.5);
      this.line(right, g.y - 10, right, g.y + 10, c, .72 * Math.sin(p * Math.PI), 1.5);
      this.trackStroke(p, .12, g, g.y, c, .82 * Math.sin(p * Math.PI), 1.8);
    }

    draw(now) {
      this.resize();
      const ctx = this.ctx, ratio = this.ratio || 1;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.clearRect(0, 0, this.canvas.clientWidth, this.canvas.clientHeight);
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      const g = this.geometry();
      const response = this.responseGeometry(g);
      this.chassis(g, this.state.color);
      if (!this.reduced && this.previous && this.transitionStarted) {
        const progress = clamp((now - this.transitionStarted) / this.transitionDuration);
        const mix = smooth(progress);
        this.drawIdentity(g, this.previous, this.phase(this.previous, now), 1 - mix);
        this.drawIdentity(g, this.state, this.phase(this.state, now), mix);
        this.drawState(response, this.previous, this.phase(this.previous, now), 1 - mix);
        this.drawState(response, this.state, this.phase(this.state, now), mix);
        this.drawTransition(response, progress, this.previous, this.state);
        if (progress >= 1) this.previous = null;
      } else {
        const phase = this.phase(this.state, now);
        this.drawIdentity(g, this.state, phase, 1);
        this.drawState(response, this.state, phase, 1);
      }
      this.drawStatusModifiers(response, this.state, this.phase(this.state, now), 1);
      if (!this.reduced) {
        this.drawEvent(response, now);
        this.drawGearPulse(response, now);
      }
    }

    frame(now) {
      if (!this.running) return;
      const interval = this.reduced ? 180 : FRAME_MS;
      if (now - this.lastFrame >= interval) {
        this.lastFrame = now;
        this.draw(now);
      }
      requestAnimationFrame((time) => this.frame(time));
    }
  }

  window.NavigationIndicator = NavigationIndicator;
})();
