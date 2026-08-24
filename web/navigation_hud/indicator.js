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
  const WARNING_EVENTS = new Set([
    "warning", "interdiction", "signal_drop", "fighter_destroyed", "srv_destroyed",
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
        analysisMode: Boolean(source.analysis_mode),
        neutronBoost: Boolean(source.neutron_boost),
        routeActive: Boolean(source.route_active),
      };
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
      if (!this.receivedModel) {
        this.state = incoming;
        this.stateStarted = now;
        this.receivedModel = true;
      } else if (incoming.motion !== this.state.motion || incoming.label !== this.state.label
          || incoming.vehicleKey !== this.state.vehicleKey) {
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
        "interdiction_evaded", "fsd_cooldown", "supercruise_overcharge"].includes(key)) return "fsd";
      if (PLANETARY.has(key) || ["landed", "srv", "scorpion", "nomad", "on_foot"].includes(key)) return "surface";
      if (["fss", "dss", "map", "galaxy_map", "system_map", "power_map",
        "orrery", "codex", "exploration"].includes(key)) return "scope";
      if (["mass_lock", "signal_lock", "signal_drop", "signal_threat", "combat",
        "interdiction", "interdicted", "asteroid_field"].includes(key)) return "hazard";
      if (key.startsWith("vehicle_") || ["fighter", "multicrew"].includes(key)) return "vehicle";
      if (key.startsWith("carrier_")) return "carrier";
      if (["docked", "station"].includes(key)) return "station";
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
        fsd_charge: .86, hyper_charge: .64, hyperspace: .58, jumping: .72,
        arrival: 1.15, interdiction_evaded: 1.05, fsd_cooldown: 1.55,
        carrier_transit: 1.08, carrier_arrival: 1.34,
        fss: 1.52, dss: 1.82, map: 2.1, galaxy_map: 2.35,
        system_map: 1.86, power_map: 1.7, orrery: 2.5, codex: 1.9,
        orbital_approach: 1.68, glide: .82, surface_approach: 1.38,
        surface_hold: 2.25, surface_departure: 1.28, orbital_departure: 1.55,
        landed: 2.4, on_foot: 1.32, srv: 1.18, scorpion: .9, nomad: 1.05,
        asteroid_field: 2.2, mass_lock: 1.12, signal_lock: 1.55,
        signal_drop: .92, signal_threat: .76, combat: .64,
        interdiction: .5, interdicted: .43, docked: 2.3, station: 2.1,
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

      if (family === "fsd") {
        const speed = key === "supercruise_overcharge" || key === "hyperspace" ? 1.7 : 1;
        for (let i = 0; i < 4; i += 1) {
          const x = point(1 - (p * speed + i * .23));
          const length = 5 + i * 2 + (key === "hyperspace" ? 5 : 0);
          this.line(Math.max(start, x - length), y - 6 + i * 4, x, y - 6 + i * 4,
            c, alpha * (.28 + i * .1), i === 2 ? 1.5 : 1);
        }
        const gate = 3 + wave(p) * 7;
        this.line(end - gate, y - 9, end - gate, y + 9, c, alpha * .62, 1.3);
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
        const departure = key.includes("departure");
        const motion = key === "surface_hold" || key === "landed" ? 0 : (departure ? -1 : 1);
        this.path([[start, y + 6], [start + span * .28, y + 3],
          [start + span * .62, y + 7], [end, y + 4]], c, alpha * .48, 1.2);
        if (motion) {
          const x = point(motion > 0 ? p : 1 - p);
          this.chevron(x, y + 5, motion, c, alpha * .68, 2.5);
        } else {
          this.line(start + span * .36, y + 1, start + span * .64, y + 1, c,
            alpha * (.35 + .25 * wave(p)));
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
      const energy = overcharge ? 1.65 : 1;

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

    drawArrival(g, state, p, alpha, cooldown = false) {
      const c = state.color, y = g.y;
      if (cooldown) {
        for (let i = 0; i < 9; i += 1) {
          const progress = (i + .5) / 9;
          const point = this.trackPoint(progress, g);
          const heat = (1 - progress) * (.35 + .5 * wave(p + i * .08));
          this.line(point.x, y - heat * 9, point.x, y + heat * 9, c, alpha * (.25 + heat * .55));
        }
        this.trackStroke(p * .42, .04, g, y, c, alpha * .45);
        return;
      }
      const expansion = smooth(p);
      const leftX = g.centerLeft - expansion * (g.centerLeft - g.left);
      const rightX = g.centerRight + expansion * (g.right - g.centerRight);
      const fade = 1 - expansion;
      this.line(leftX, y - 9 * fade, leftX, y + 9 * fade, c, alpha * (.3 + fade * .7), 1.7);
      this.line(rightX, y - 9 * fade, rightX, y + 9 * fade, c, alpha * (.3 + fade * .7), 1.7);
      this.path([[g.left, y + 5], [leftX, y], [g.centerLeft, y - 5]], c, alpha * .38);
      this.path([[g.centerRight, y - 5], [rightX, y], [g.right, y + 5]], c, alpha * .38);
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
        if (key === "galaxy_map" || key === "map") {
          for (let arm = 0; arm < 3; arm += 1) {
            const points = [];
            for (let i = 0; i < 12; i += 1) {
              const radius = 1.5 + i * 2.2;
              const angle = i * .48 + p * TAU * (side ? -1 : 1) + arm * TAU / 3;
              points.push([cx + Math.cos(angle) * radius, y + Math.sin(angle) * radius * .38]);
            }
            this.path(points, c, alpha * .35);
          }
          this.glowDot(cx, y, 1.6, c, alpha * .85);
        } else if (key === "power_map") {
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
      const direction = departing ? -1 : 1;
      const vertical = clamp(Math.abs(d.vertical) / 160);
      const gravity = clamp(d.gravity / 4);
      const horizonY = y + (departing ? 4 : hold || landed ? 5 : 2) + gravity * 2;
      const leftMid = (g.left + g.centerLeft) / 2;
      const rightMid = (g.centerRight + g.right) / 2;
      [leftMid, rightMid].forEach((cx) => {
        this.arc(cx, horizonY + 10, Math.min(62, (g.centerLeft - g.left) * .46), 12,
          Math.PI * 1.08, Math.PI * 1.92, c, alpha * .58, 1.2);
      });
      if (hold || landed) {
        this.line(g.left + 7, horizonY, g.centerLeft - 7, horizonY, c, alpha * .55, 1.3);
        this.line(g.centerRight + 7, horizonY, g.right - 7, horizonY, c, alpha * .55, 1.3);
        for (const cx of [leftMid, rightMid]) {
          this.line(cx - 8, horizonY, cx - 4, horizonY - 5, c, alpha * .62);
          this.line(cx + 8, horizonY, cx + 4, horizonY - 5, c, alpha * .62);
        }
      } else {
        const speed = key === "glide" ? 1.9 : .78 + vertical;
        for (let i = 0; i < 5; i += 1) {
          const progress = (p * speed + i / 5) % 1;
          const travel = direction > 0 ? progress : 1 - progress;
          const point = this.trackPoint(travel, g);
          const size = 2 + (direction > 0 ? progress : 1 - progress) * 5;
          this.chevron(point.x, y - 1, direction, c, alpha * (.25 + .55 * wave(progress)), size);
        }
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
      if (key === "fsd_charge" || key === "hyper_charge") {
        this.drawCharge(g, state, p, alpha, key === "hyper_charge"); return;
      }
      if (key === "hyperspace" || key === "jumping") {
        this.drawJump(g, state, p, alpha, key === "jumping"); return;
      }
      if (key === "arrival" || key === "interdiction_evaded") {
        this.drawArrival(g, state, p, alpha); return;
      }
      if (key === "fsd_cooldown") { this.drawArrival(g, state, p, alpha, true); return; }
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
      if (key === "on_foot") { this.drawOnFoot(g, state, p, alpha); return; }
      if (key === "docked" || key === "station") {
        this.drawDocked(g, state, p, alpha, key === "station"); return;
      }
      if (key.startsWith("vehicle_")) { this.drawHandoff(g, state, p, alpha, key); return; }
      if (["mass_lock", "signal_lock", "signal_drop", "signal_threat", "combat",
        "interdiction", "interdicted", "asteroid_field"].includes(key)) {
        this.drawHazard(g, state, p, alpha, key); return;
      }
      if (key === "carrier_transit" || key === "carrier_arrival") {
        this.drawCarrier(g, state, p, alpha, key === "carrier_arrival"); return;
      }
      this.drawFlight(g, state, p, alpha, "flight");
    }

    eventColor(kind, fallback) {
      if (WARNING_EVENTS.has(kind) || kind === "dock_denied") return this.themeColor("orange", "#ff7a18");
      if (["survey_complete", "mapping_complete", "bio_sample", "data_sale",
        "mining_refined", "interdiction_clear"].includes(kind)) return this.themeColor("green", "#4ee59b");
      if (RESOURCE_EVENTS.has(kind) || kind === "signals" || kind === "codex") return this.themeColor("yellow", "#ffd166");
      return fallback;
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
      if (!this.reduced) this.drawEvent(response, now);
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
