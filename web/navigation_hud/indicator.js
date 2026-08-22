(() => {
  "use strict";

  const TAU = Math.PI * 2;
  const clamp = (value, low = 0, high = 1) => Math.max(low, Math.min(high, value));
  const wave = (progress) => .5 - .5 * Math.cos(progress * TAU);
  const smoothstep = (value) => {
    const t = clamp(value);
    return t * t * (3 - 2 * t);
  };
  const easeOut = (value) => 1 - Math.pow(1 - clamp(value), 3);
  const windowPulse = (value, start, end) => {
    if (value <= start || value >= end) return 0;
    const local = (value - start) / Math.max(.001, end - start);
    return Math.sin(local * Math.PI);
  };
  const PLANETARY_MOTIONS = new Set([
    "orbital_approach", "glide", "surface_approach", "surface_hold",
    "surface_departure", "orbital_departure",
  ]);
  const HANDOFF_MOTIONS = new Set(["vehicle_deploy", "vehicle_board", "vehicle_switch"]);
  const FSD_MOTIONS = new Set([
    "fsd_charge", "jump", "arrival", "fsd_cooldown", "supercruise_overcharge",
  ]);
  const RESOURCE_EVENTS = new Set([
    "prospector_scan", "prospector_rich", "prospector_core", "mining_refined",
  ]);
  const SCOPE_EVENTS = new Set([
    "honk", "fss_progress", "fss_signal", "body_scan", "signals",
    "valuable_discovery", "first_discovery", "footfall_candidate", "codex",
  ]);
  const ROUTE_EVENTS = new Set(["route_set", "route_clear", "route_target", "route_divert"]);
  const DOCKING_EVENTS = new Set(["dock", "dock_request", "dock_denied", "undock"]);

  class NavigationIndicator {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d", {alpha: true, desynchronized: true});
      this.state = {motion: "flight", label: "FLIGHT", color: "#607584", energy: 1, dynamics: {}};
      this.receivedModel = false;
      this.previous = null;
      this.stateStarted = performance.now();
      this.transitionStarted = 0;
      this.transitionDuration = 620;
      this.eventStarted = 0;
      this.eventSequence = null;
      this.reduced = false;
      this.lastFrame = 0;
      this.running = true;
      this.resizeObserver = new ResizeObserver(() => this.resize());
      this.resizeObserver.observe(canvas);
      this.resize();
      requestAnimationFrame((time) => this.frame(time));
    }

    resize() {
      const ratio = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
      const width = Math.max(1, Math.round(this.canvas.clientWidth * ratio));
      const height = Math.max(1, Math.round(this.canvas.clientHeight * ratio));
      if (this.canvas.width !== width || this.canvas.height !== height) {
        this.canvas.width = width; this.canvas.height = height;
      }
      this.ratio = ratio;
    }

    update(next = {}) {
      const now = performance.now();
      const incoming = {
        motion: String(next.motion || "flight"),
        label: String(next.label || "FLIGHT").toUpperCase(),
        color: /^#[0-9a-f]{6}$/i.test(String(next.color || "")) ? next.color : "#607584",
        energy: clamp(Number(next.energy || 1), .55, 1.6),
        dynamics: this.normaliseDynamics(next.dynamics),
      };
      if (!this.receivedModel) {
        incoming.startedAt = now;
        this.state = incoming;
        this.stateStarted = now;
        this.receivedModel = true;
      } else if (incoming.motion !== this.state.motion || incoming.label !== this.state.label) {
        this.previous = {...this.state, phaseAtChange: this.phase(this.state, now)};
        incoming.startedAt = now;
        this.state = incoming;
        this.stateStarted = now;
        this.transitionStarted = now;
        this.transitionDuration = this.transitionMs(this.previous, incoming);
      } else {
        incoming.startedAt = this.state.startedAt || this.stateStarted;
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

    family(state) {
      const key = this.animationKey(state);
      if (["fsd_charge", "hyper_charge", "hyperspace", "jumping", "arrival", "fsd_cooldown", "interdiction_evaded", "supercruise_overcharge"].includes(key)) return "fsd";
      if (PLANETARY_MOTIONS.has(key) || ["landed", "srv", "nomad", "on_foot"].includes(key)) return "surface";
      if (["fss", "dss", "galaxy_map", "system_map", "power_map", "orrery", "codex", "map", "exploration"].includes(key)) return "scope";
      if (["mass_lock", "signal_lock", "signal_drop", "signal_threat", "combat", "interdiction", "interdicted", "asteroid_field"].includes(key)) return "hazard";
      if (key.startsWith("vehicle_") || key === "multicrew" || key === "fighter") return "vehicle";
      if (key.startsWith("carrier_")) return "carrier";
      if (["docked", "station"].includes(key)) return "station";
      return "flight";
    }

    transitionMs(previous, next) {
      const from = this.family(previous), to = this.family(next);
      if (from === to) return from === "fsd" ? 460 : 420;
      if (from === "fsd" || to === "fsd") return 720;
      if (from === "surface" || to === "surface") return 610;
      if (from === "hazard" || to === "hazard") return 520;
      return 560;
    }

    choreography(state, now) {
      const key = this.animationKey(state);
      const family = this.family(state);
      const age = Math.max(0, now - (state.startedAt || this.stateStarted)) / 1000;
      const p = this.phase(state, now);
      const introSeconds = ({
        fsd: .46, hazard: .32, surface: .52, scope: .48,
        vehicle: .42, carrier: .58, station: .46,
      })[family] || .38;
      const intro = smoothstep(age / introSeconds);
      const eventAge = this.eventStarted ? Math.max(0, now - this.eventStarted) / 1000 : 99;
      const event = eventAge < .95 ? 1 - smoothstep(eventAge / .95) : 0;
      const dynamics = state.dynamics || {};
      const gravity = clamp(Number(dynamics.gravity || 0) / 3.5);
      const vertical = clamp(Math.abs(Number(dynamics.vertical || 0)) / 120);
      const dataEnergy = Math.max(
        gravity * (family === "surface" ? .7 : .15),
        vertical * (family === "surface" ? .8 : .1),
        dynamics.analysisMode && family === "scope" ? .32 : 0,
        dynamics.neutronBoost && family === "fsd" ? .5 : 0,
      );
      return {
        key, family, age, p, intro,
        attack: (1 - intro) * (family === "hazard" || family === "fsd" ? 1 : .72),
        acquire: windowPulse(p, 0, .28),
        sustain: smoothstep(clamp((p - .12) / .42)) * (1 - smoothstep(clamp((p - .78) / .22))),
        resolve: windowPulse(p, .66, 1),
        beat: wave(p),
        subBeat: wave((p * 2 + .17) % 1),
        activity: clamp(Math.max(event, dataEnergy)),
        gravity, vertical,
        scan: clamp(Number(dynamics.scan || 0)),
        route: clamp(Number(dynamics.route || 0)),
        landingGear: Boolean(dynamics.landingGear),
        neutronBoost: Boolean(dynamics.neutronBoost),
        routeActive: Boolean(dynamics.routeActive),
      };
    }

    animationKey(state) {
      const motion = String(state?.motion || "flight");
      const label = String(state?.label || "FLIGHT").toUpperCase();
      if (motion === "scanner") return label === "DSS" ? "dss" : "fss";
      if (motion === "map") return ({
        "GALAXY MAP": "galaxy_map", "SYSTEM MAP": "system_map",
        "POWER MAP": "power_map", ORRERY: "orrery", CODEX: "codex",
      })[label] || "map";
      if (motion === "surface_vehicle") return label === "NOMAD" ? "nomad" : "srv";
      if (motion === "fsd_charge") return label === "HYPER CHARGE" ? "hyper_charge" : "fsd_charge";
      if (motion === "jump") return label === "JUMPING" ? "jumping" : "hyperspace";
      if (motion === "arrival" && label === "INTERDICTION EVADED") return "interdiction_evaded";
      if (motion === "fsd_lock") {
        if (label === "MASS LOCK") return "mass_lock";
        if (label === "SIGNAL DROP") return "signal_drop";
        return label.startsWith("SIGNAL THREAT") ? "signal_threat" : "signal_lock";
      }
      if (motion === "combat") return label === "COMBAT" ? "combat"
        : label === "INTERDICTED" ? "interdicted" : "interdiction";
      if (HANDOFF_MOTIONS.has(motion)) {
        const vehicle = label.includes("NOMAD") ? "nomad"
          : label.includes("FIGHTER") ? "fighter"
            : label.includes("SRV") ? "srv"
              : label.includes("CREW") || label.includes("MULTICREW") ? "crew"
                : "ship";
        return `${motion}_${vehicle}`;
      }
      if (motion === "flight" && label === "MULTICREW") return "multicrew";
      if (motion === "flight" && label === "EXPLORATION") return "exploration";
      if (motion === "docked" && label === "STATION") return "station";
      return motion;
    }

    period(state) {
      const key = this.animationKey(state);
      return ({
        flight: 1.72, fighter: .88, supercruise: .94, supercruise_overcharge: .52,
        fsd_charge: .82, hyper_charge: .64, hyperspace: .58, jumping: .69,
        arrival: 1.16, interdiction_evaded: .96, fsd_cooldown: 1.42,
        carrier_transit: .98, carrier_arrival: 1.34,
        fss: 1.52, dss: 1.84, galaxy_map: 2.2, system_map: 1.78,
        power_map: 1.56, orrery: 2.46, codex: 1.68, map: 1.94,
        asteroid_field: 2.08, mass_lock: 1.14, signal_lock: 1.38,
        signal_drop: .86, signal_threat: .72, combat: .84,
        interdiction: .66, interdicted: .78,
        srv: 1.26, nomad: 1.06, on_foot: 1.42, multicrew: 1.62,
        exploration: 1.88, docked: 1.72, station: 1.44, landed: 1.86,
        orbital_approach: 1.52, glide: .96, surface_approach: 1.36,
        surface_hold: 1.92, surface_departure: 1.18, orbital_departure: 1.04,
        vehicle_deploy_srv: 1.12, vehicle_deploy_nomad: .94,
        vehicle_deploy_fighter: .82, vehicle_board_srv: 1.2,
        vehicle_board_nomad: 1.04, vehicle_board_fighter: .92,
        vehicle_deploy_ship: 1.18, vehicle_board_ship: 1.24,
        vehicle_switch_srv: 1.12, vehicle_switch_nomad: 1.02,
        vehicle_switch_fighter: .86, vehicle_switch_ship: 1.16,
        vehicle_switch_crew: 1.38, vehicle_deploy_crew: 1.3,
        vehicle_board_crew: 1.34,
      })[key] || 1.55;
    }

    phase(state, now) {
      const elapsed = Math.max(0, now - (state.startedAt || this.stateStarted)) / 1000;
      return (elapsed * (state.energy || 1) / this.period(state)) % 1;
    }

    geometry() {
      const width = this.canvas.clientWidth;
      const height = this.canvas.clientHeight;
      const center = width / 2;
      const aperture = Math.max(130, width * .43);
      return {
        width, height, y: height / 2 + 1, top: 3, bottom: height - 4,
        left: 3, leftEnd: center - aperture / 2 - 8,
        rightStart: center + aperture / 2 + 8, right: width - 3,
        leftCenter: 3 + (center - aperture / 2 - 11) * .42,
        rightCenter: center + aperture / 2 + 8 + (width - center - aperture / 2 - 11) * .58,
      };
    }

    withAlpha(alpha, callback) {
      const ctx = this.ctx;
      ctx.save();
      ctx.globalAlpha *= clamp(alpha);
      ctx.globalCompositeOperation = "lighter";
      callback(ctx);
      ctx.restore();
    }

    line(x1, y1, x2, y2, color, alpha = 1, width = 1) {
      const ctx = this.ctx;
      ctx.save(); ctx.globalAlpha *= alpha; ctx.strokeStyle = color;
      if (alpha >= .72 && width >= 2) { ctx.shadowColor = color; ctx.shadowBlur = 4; }
      ctx.lineWidth = width; ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.restore();
    }

    path(points, color, alpha = 1, width = 1, close = false) {
      if (points.length < 2) return;
      const ctx = this.ctx;
      ctx.save(); ctx.globalAlpha *= alpha; ctx.strokeStyle = color; ctx.lineWidth = width;
      ctx.beginPath(); ctx.moveTo(points[0][0], points[0][1]);
      for (const point of points.slice(1)) ctx.lineTo(point[0], point[1]);
      if (close) ctx.closePath(); ctx.stroke(); ctx.restore();
    }

    dot(x, y, radius, color, alpha = 1, fill = true) {
      const ctx = this.ctx;
      ctx.save(); ctx.globalAlpha *= alpha; ctx.beginPath(); ctx.arc(x, y, radius, 0, TAU);
      if (alpha >= .7) { ctx.shadowColor = color; ctx.shadowBlur = 4; }
      if (fill) { ctx.fillStyle = color; ctx.fill(); } else { ctx.strokeStyle = color; ctx.stroke(); }
      ctx.restore();
    }

    arc(x, y, rx, ry, start, end, color, alpha = 1, width = 1) {
      const ctx = this.ctx;
      ctx.save(); ctx.globalAlpha *= alpha; ctx.strokeStyle = color; ctx.lineWidth = width;
      ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, start, end); ctx.stroke(); ctx.restore();
    }

    polygon(points, color, alpha = 1, fill = false, width = 1) {
      if (!points.length) return;
      const ctx = this.ctx;
      ctx.save(); ctx.globalAlpha *= alpha; ctx.beginPath(); ctx.moveTo(...points[0]);
      for (const point of points.slice(1)) ctx.lineTo(...point);
      ctx.closePath();
      if (fill) { ctx.fillStyle = color; ctx.fill(); }
      ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke(); ctx.restore();
    }

    chassis(g, color) {
      const y = g.y;
      this.line(g.left, y, g.leftEnd, y, color, .25);
      this.line(g.rightStart, y, g.right, y, color, .25);
      for (const [x, side] of [[g.left, 1], [g.right, -1]]) {
        this.line(x, g.top + 4, x, g.bottom - 3, color, .3);
        this.line(x, g.top + 4, x + side * 7, g.top + 4, color, .3);
        this.line(x, g.bottom - 3, x + side * 4, g.bottom - 3, color, .22);
      }
      for (const [x, side] of [[g.leftEnd, -1], [g.rightStart, 1]]) {
        this.line(x, y - 4, x, y + 4, color, .35);
        this.line(x, y - 4, x + side * 5, y, color, .28);
      }
    }

    wings(g) {
      return [[g.left + 6, g.leftEnd - 5], [g.rightStart + 5, g.right - 6]];
    }

    clipWing(g, side, callback) {
      const [x1, x2] = side === "left" ? this.wings(g)[0] : this.wings(g)[1];
      const ctx = this.ctx;
      ctx.save();
      ctx.beginPath();
      ctx.rect(x1 - 4, 0, Math.max(1, x2 - x1 + 8), g.height);
      ctx.clip();
      callback();
      ctx.restore();
    }

    shipGlyph(x, y, color, alpha = 1, scale = 1, fighter = false) {
      const points = fighter ? [
        [x + 8 * scale, y], [x - 7 * scale, y - 6 * scale],
        [x - 3 * scale, y], [x - 7 * scale, y + 6 * scale],
      ] : [
        [x + 8 * scale, y], [x - 6 * scale, y - 5 * scale],
        [x - 2 * scale, y], [x - 6 * scale, y + 5 * scale],
      ];
      this.polygon(points, color, alpha, false, 1.4);
    }

    carrierGlyph(x, y, color, alpha = 1, scale = 1) {
      this.polygon([
        [x - 14 * scale, y - 3 * scale], [x + 8 * scale, y - 3 * scale],
        [x + 14 * scale, y], [x + 8 * scale, y + 3 * scale],
        [x - 14 * scale, y + 3 * scale], [x - 10 * scale, y],
      ], color, alpha, false, 1.4);
      this.line(x - 7 * scale, y, x + 7 * scale, y, color, alpha * .55);
    }

    drawLeftIdentity(g, state, p, alpha) {
      const c = state.color, y = g.y;
      const [x1, x2] = this.wings(g)[0];
      const span = Math.max(1, x2 - x1);
      const cx = g.leftCenter;
      const motion = state.motion;
      const label = state.label;
      const key = this.animationKey(state);
      const pulse = wave(p);
      this.withAlpha(alpha, () => {
        // The left wing is the state identity bay: a recognisable animated
        // sigil plus a quiet bearing rail. The right wing owns live response.
        this.line(x1, y, x2, y, c, .16);
        this.line(x1 + 2, y - 9, x1 + 2, y + 9, c, .24);

        if (motion === "docked") {
          if (key === "station") {
            const rotation = p * TAU;
            this.arc(cx, y, 22, 10, rotation, rotation + Math.PI * 1.45, c, .68, 2);
            this.arc(cx, y, 13, 6, -rotation * .7, -rotation * .7 + Math.PI, c, .34);
            this.polygon([[cx - 5, y - 5], [cx + 5, y - 5], [cx + 8, y], [cx + 5, y + 5], [cx - 5, y + 5], [cx - 8, y]], c, .9);
            this.dot(cx + Math.cos(rotation) * 22, y + Math.sin(rotation) * 10, 1.7, c, .95);
            return;
          }
          const clampWidth = 12 + pulse * 4;
          this.shipGlyph(cx, y, c, .88, .72);
          this.polygon([
            [cx - 25, y - 10], [cx + 25, y - 10],
            [cx + 19, y + 10], [cx - 19, y + 10],
          ], c, .32);
          for (const side of [-1, 1]) {
            this.line(cx + side * clampWidth, y - 7, cx + side * (clampWidth - 5), y - 7, c, .9, 2);
            this.line(cx + side * clampWidth, y + 7, cx + side * (clampWidth - 5), y + 7, c, .9, 2);
          }
          return;
        }

        if (motion === "landed") {
          this.line(cx - 25, y + 9, cx + 25, y + 9, c, .45, 2);
          this.shipGlyph(cx, y - 2, c, .9, .78);
          [-12, 0, 12].forEach((offset, index) => this.dot(
            cx + offset, y + 9, 1.2 + (index === Math.floor(p * 3) % 3 ? 1 : 0), c,
            index === Math.floor(p * 3) % 3 ? .95 : .32,
          ));
          return;
        }

        if (motion === "carrier_transit" || motion === "carrier_arrival") {
          this.carrierGlyph(cx, y, c, .92, .72);
          const fold = motion === "carrier_arrival" ? 10 + (1 - p) * 18 : 17 + pulse * 8;
          for (const side of [-1, 1]) {
            this.line(cx + side * fold, y - 10, cx + side * fold, y + 10, c, .78, 2);
            this.line(cx + side * (fold + 5), y - 6, cx + side * (fold + 5), y + 6, c, .28);
          }
          if (motion === "carrier_arrival") {
            this.arc(cx, y, 9 + p * 16, 4 + p * 6, 0, TAU, c, 1 - p, 2);
          }
          return;
        }

        if (motion === "asteroid_field") {
          for (let index = 0; index < 6; index += 1) {
            const local = (p + index / 6) % 1;
            const px = x1 + 6 + (span - 12) * local;
            const py = y + Math.sin(index * 2.1 + p * TAU) * 8;
            const radius = 1.5 + index % 3;
            this.polygon([
              [px, py - radius], [px + radius, py],
              [px, py + radius], [px - radius, py],
            ], c, index < 2 ? .9 : .38);
          }
          this.arc(cx, y, 15, 9, p * TAU, p * TAU + Math.PI * 1.25, c, .62, 2);
          return;
        }

        if (motion === "supercruise" && label !== "TAXI") {
          const shipX = Math.min(x2 - 16, cx + 8);
          const wakeEnd = shipX - 13;
          this.line(x1 + 4, y, wakeEnd, y, c, .16);
          for (let index = 0; index < 4; index += 1) {
            const local = (p + index / 4) % 1;
            const depth = easeOut(local);
            const px = x1 + 6 + (wakeEnd - x1 - 8) * depth;
            const half = 9 - depth * 5;
            const glow = Math.sin(local * Math.PI) * (.34 + depth * .56);
            this.path([[px - 5, y - half], [px + 1, y], [px - 5, y + half]], c, glow, depth > .65 ? 2 : 1);
          }
          this.shipGlyph(shipX, y, c, .98, .76);
          const halo = 10 + pulse * 3;
          this.arc(shipX - 1, y, halo, 7, Math.PI * .62, Math.PI * 1.38, c, .45 + pulse * .24, 2);
          this.arc(shipX - 1, y, halo + 5, 10, Math.PI * .72, Math.PI * 1.28, c, .22);
          const solutionX = x2 - 4;
          this.line(shipX + 8, y, solutionX, y, c, .35 + pulse * .2);
          this.polygon([
            [solutionX - 4, y - 4], [solutionX, y],
            [solutionX - 4, y + 4], [solutionX - 8, y],
          ], c, .62 + pulse * .28, false, 2);
          return;
        }

        if (motion === "combat" || motion === "fsd_lock") {
          const rotation = p * TAU;
          const radius = 10 + pulse * 5;
          if (key === "interdiction") {
            for (const side of [-1, 1]) {
              const points = [];
              for (let index = 0; index <= 8; index += 1) {
                const amount = index / 8;
                points.push([x1 + 5 + (span - 10) * amount, y + side * Math.sin(amount * Math.PI + p * TAU) * (9 - amount * 5)]);
              }
              this.path(points, c, .82, 2);
            }
            this.polygon([[cx, y - 8], [cx + 8, y], [cx, y + 8], [cx - 8, y]], c, .9, false, 2);
            return;
          }
          if (key === "interdicted") {
            const lock = 5 + (1 - pulse) * 15;
            this.shipGlyph(cx, y, c, .92, .64);
            for (const side of [-1, 1]) {
              this.line(cx + side * lock, y - 10, cx + side * lock, y + 10, c, .92, 2);
              this.line(cx + side * lock, y - 10, cx + side * (lock - 7), y - 10, c, .62);
              this.line(cx + side * lock, y + 10, cx + side * (lock - 7), y + 10, c, .62);
            }
            this.path([[x1 + 3, y - 7], [x1 + 11, y], [x1 + 3, y + 7]], c, .72 + pulse * .2, 2);
            return;
          }
          if (key === "signal_drop" || key === "signal_threat" || key === "signal_lock") {
            const severity = key === "signal_threat" ? 1.0 : key === "signal_drop" ? .72 : .48;
            const target = cx + Math.sin(p * TAU) * 6;
            this.polygon([[target, y - 7], [target + 7, y], [target, y + 7], [target - 7, y]], c, .7 + severity * .2, false, 2);
            for (let index = 0; index < 3; index += 1) {
              const local = (p + index / 3) % 1;
              this.arc(target, y, 5 + local * 20, 3 + local * 8, 0, TAU, c, (1 - local) * severity);
            }
            if (key === "signal_threat") {
              this.path([[x1 + 4, y], [x1 + 14, y - 7], [x1 + 22, y + 7], [x1 + 31, y]], c, .9, 2);
            }
            return;
          }
          this.arc(cx, y, radius, radius * .68, rotation, rotation + 1.8, c, .9, 2);
          this.arc(cx, y, radius, radius * .68, rotation + Math.PI, rotation + Math.PI + 1.8, c, .9, 2);
          this.dot(cx, y, 1.8, c, .95);
          const lock = motion === "fsd_lock" ? 6 + (1 - pulse) * 10 : 17;
          for (const side of [-1, 1]) {
            this.line(cx + side * lock, y - 8, cx + side * lock, y + 8, c, .75, 2);
            this.line(cx + side * lock, y - 8, cx + side * (lock - 5), y - 8, c, .5);
            this.line(cx + side * lock, y + 8, cx + side * (lock - 5), y + 8, c, .5);
          }
          return;
        }

        if (FSD_MOTIONS.has(motion)) {
          if (key === "interdiction_evaded") {
            this.shipGlyph(cx + 4, y, c, .94, .72);
            for (let index = 0; index < 4; index += 1) {
              const local = (p + index / 4) % 1;
              const x = x1 + 5 + (cx - x1 - 13) * local;
              this.path([[x - 7, y - 7], [x, y], [x - 7, y + 7]], c, (1 - local) * .8, local < .24 ? 2 : 1);
            }
          } else if (motion === "arrival" || motion === "fsd_cooldown") {
            for (let index = 0; index < 3; index += 1) {
              const local = (p + index / 3) % 1;
              const radius = 4 + local * 17;
              this.arc(cx, y, radius, radius * .52, 0, TAU, c, 1 - local, local > .68 ? 2 : 1);
            }
            this.shipGlyph(cx, y, c, .82, .62);
          } else {
            for (let index = 0; index < 4; index += 1) {
              const local = (p + index / 4) % 1;
              const px = x1 + 8 + (cx - x1 - 15) * local;
              this.line(Math.max(x1 + 4, px - 10 - local * 8), y + [-7, -2, 3, 8][index], px, y + [-7, -2, 3, 8][index], c, .35 + local * .58, local > .72 ? 2 : 1);
            }
            const squeeze = 8 + pulse * 9;
            for (const side of [-1, 1]) {
              const bx = cx + side * squeeze;
              this.path([[bx + side * 5, y - 8], [bx, y], [bx + side * 5, y + 8]], c, .88, 2);
            }
            if (motion === "supercruise_overcharge") {
              this.path([[cx - 23, y], [cx - 15, y - 7], [cx - 7, y + 6], [cx, y]], c, .95, 2);
            } else if (key === "hyper_charge") {
              this.arc(cx, y, 15 + pulse * 8, 8 + pulse * 3, 0, TAU, c, .6, 2);
              this.dot(cx, y, 2 + pulse * 1.6, c, .98);
            } else if (key === "hyperspace") {
              const ring = 7 + pulse * 9;
              this.arc(cx, y, ring, ring * .52, 0, TAU, c, .8, 2);
              this.line(cx - 28, y, cx + 28, y, c, .32);
            }
          }
          return;
        }

        if (motion === "scanner" || motion === "map" || motion === "exploration") {
          if (key === "dss") {
            this.arc(cx, y, 10, 10, 0, TAU, c, .6, 2);
            this.arc(cx, y, 18, 8, p * TAU, p * TAU + Math.PI * 1.25, c, .42);
            for (let index = 0; index < 3; index += 1) {
              const angle = p * TAU + index * TAU / 3;
              const probeX = cx + Math.cos(angle) * 18;
              const probeY = y + Math.sin(angle) * 8;
              this.dot(probeX, probeY, 1.5, c, .95);
              this.line(probeX, probeY, cx + Math.cos(angle) * 8, y + Math.sin(angle) * 8, c, .3);
            }
          } else if (key === "fss") {
            const samples = [];
            for (let index = 0; index <= 22; index += 1) {
              const amount = index / 22;
              const envelope = Math.sin(amount * Math.PI);
              samples.push([x1 + 5 + (span - 10) * amount, y + Math.sin(index * 1.55 + p * TAU) * envelope * 8]);
            }
            this.path(samples, c, .68, 1.5);
            const sweep = x1 + 5 + (span - 10) * p;
            this.line(sweep, y - 10, sweep, y + 10, c, .92, 2);
            this.arc(cx, y, 23, 10, -Math.PI * .82, -Math.PI * .18, c, .34);
          } else if (key === "galaxy_map") {
            const nodes = [];
            for (let index = 0; index < 7; index += 1) {
              const angle = index * 2.22 + p * TAU * .18;
              const radius = 3 + index * 3;
              nodes.push([cx + Math.cos(angle) * radius, y + Math.sin(angle) * radius * .42]);
            }
            this.path(nodes, c, .34);
            nodes.forEach(([px, py], index) => this.dot(px, py, index === Math.floor(p * 7) ? 2 : 1, c, index === Math.floor(p * 7) ? .98 : .42));
            this.arc(cx, y, 25, 10, p * TAU * .25, p * TAU * .25 + Math.PI * 1.35, c, .28);
          } else if (key === "system_map") {
            this.dot(cx, y, 2.5, c, .98);
            [8, 15, 23].forEach((radius, index) => {
              this.arc(cx, y, radius, radius * .38, 0, TAU, c, .28 + index * .08);
              const angle = p * TAU * (index % 2 ? -1 : 1) + index * 1.9;
              this.dot(cx + Math.cos(angle) * radius, y + Math.sin(angle) * radius * .38, 1.2 + index * .25, c, .9);
            });
          } else if (key === "orrery") {
            for (let index = 0; index < 3; index += 1) {
              const radius = 8 + index * 7;
              const tilt = (index - 1) * .24;
              this.arc(cx, y, radius, radius * (.28 + index * .08), tilt, tilt + TAU, c, .3 + index * .1);
              const angle = p * TAU * (1 + index * .33) + index * 2.1;
              this.dot(cx + Math.cos(angle) * radius, y + Math.sin(angle + tilt) * radius * (.28 + index * .08), 1.3, c, .92);
            }
            this.dot(cx, y, 2.2, c, .98);
          } else if (key === "power_map") {
            for (let index = 0; index < 5; index += 1) {
              const px = cx + (index - 2) * 10;
              const py = y + (index % 2 ? 5 : -1);
              const size = index === Math.floor(p * 5) ? 5.5 : 4;
              this.polygon(Array.from({length: 6}, (_, point) => [
                px + Math.cos(point * TAU / 6) * size,
                py + Math.sin(point * TAU / 6) * size,
              ]), c, index === Math.floor(p * 5) ? .95 : .34, false, index === Math.floor(p * 5) ? 2 : 1);
            }
          } else if (key === "codex") {
            const reveal = Math.floor(p * 5);
            this.polygon([[cx - 20, y - 10], [cx + 17, y - 10], [cx + 22, y - 5], [cx + 22, y + 10], [cx - 20, y + 10]], c, .42);
            for (let index = 0; index < 5; index += 1) {
              const width = [24, 31, 18, 28, 21][index];
              this.line(cx - 14, y - 7 + index * 3.5, cx - 14 + width, y - 7 + index * 3.5, c, index === reveal ? .98 : .3, index === reveal ? 2 : 1);
            }
          } else if (motion === "map") {
            const nodes = [[x1 + 12, y + 5], [x1 + 34, y - 7], [cx + 4, y + 4], [x2 - 12, y - 4]];
            this.path(nodes, c, .42);
            nodes.forEach(([px, py], index) => this.dot(
              px, py, index === Math.floor(p * nodes.length) % nodes.length ? 2.2 : 1.1,
              c, index === Math.floor(p * nodes.length) % nodes.length ? .98 : .4,
            ));
          } else {
            this.arc(cx, y, 22, 10, 0, TAU, c, .42);
            const angle = (-.75 + wave(p) * 1.5) * Math.PI;
            this.line(cx, y, cx + Math.cos(angle) * 22, y + Math.sin(angle) * 10, c, .9, 2);
            [[-.55, -.35], [.15, .5], [.62, -.18]].forEach(([ox, oy], index) => {
              const active = ((p + index * .23) % 1) < .18;
              this.dot(cx + ox * 22, y + oy * 10, active ? 2.1 : 1.1, c, active ? .98 : .35);
            });
          }
          return;
        }

        if (PLANETARY_MOTIONS.has(motion)) {
          const departing = motion.includes("departure");
          const local = departing ? 1 - p : p;
          const horizonY = y + 8;
          this.arc(cx, horizonY + 3, 27, 10, Math.PI, TAU, c, .38);
          if (motion === "orbital_approach") {
            const angle = Math.PI * (1.12 + p * .72);
            const shipX = cx + Math.cos(angle) * 25;
            const shipY = horizonY + 3 + Math.sin(angle) * 10;
            this.shipGlyph(shipX, shipY, c, .94, .5);
            this.arc(cx, horizonY + 3, 31, 14, Math.PI * 1.03, Math.PI * 1.88, c, .45, 2);
          } else if (motion === "glide") {
            const descent = y - 9 + p * 13;
            this.shipGlyph(cx + 8, descent, c, .95, .66);
            for (let index = 0; index < 4; index += 1) {
              const x = x1 + 6 + index * 14;
              this.line(x, y - 10 + index * 3, x + 16, y - 5 + index * 3, c, .28 + index * .15, index === 3 ? 2 : 1);
            }
            this.line(cx - 28, y + Math.sin(p * TAU) * 1.5, cx + 28, y + Math.sin(p * TAU) * 1.5, c, .7, 2);
          } else if (motion === "surface_hold") {
            this.shipGlyph(cx, y - 3, c, .9, .68);
            const bracket = 9 + pulse * 5;
            for (const side of [-1, 1]) {
              this.line(cx + side * bracket, y - 9, cx + side * bracket, y + 7, c, .78, 2);
              this.line(cx + side * bracket, y + 7, cx + side * 5, y + 7, c, .45);
            }
            this.dot(cx, y + 9, 1.3 + pulse, c, .9);
          } else if (motion === "orbital_departure") {
            const angle = Math.PI * (1.88 - p * .7);
            const shipX = cx + Math.cos(angle) * 27;
            const shipY = horizonY + 3 + Math.sin(angle) * 10;
            this.shipGlyph(shipX, shipY, c, .94, .5);
            this.arc(cx, horizonY + 3, 31, 14, Math.PI * 1.03, Math.PI * 1.88, c, .45, 2);
            this.path([[cx + 10, y - 8], [cx + 17, y], [cx + 10, y + 8]], c, .75, 2);
          } else {
            this.shipGlyph(cx, y - 4 + local * 8, c, .92, .68);
            const markerY = y - 9 + local * 18;
            for (const side of [-1, 1]) this.line(cx + side * 18, markerY, cx + side * 8, markerY, c, .8, 2);
            if (motion === "surface_departure") {
              for (let index = 0; index < 3; index += 1) {
                const trail = (p + index / 3) % 1;
                this.line(cx - 21 - trail * 16, y + [-6, 0, 6][index], cx - 12 - trail * 8, y + [-6, 0, 6][index], c, (1 - trail) * .72);
              }
            }
          }
          return;
        }

        if (motion === "surface_vehicle" || motion === "on_foot" || HANDOFF_MOTIONS.has(motion)) {
          this.line(x1 + 5, y + 8, x2 - 5, y + 8, c, .34);
          if (motion === "on_foot") {
            for (let index = 0; index < 6; index += 1) {
              const local = (p + index / 6) % 1;
              this.arc(x1 + 8 + (span - 16) * local, y + (index % 2 ? -3 : 3), 3, 1.4, 0, TAU, c, index < 2 ? .9 : .28);
            }
          } else {
            const reverse = motion === "vehicle_board";
            const amount = HANDOFF_MOTIONS.has(motion) ? (reverse ? 1 - pulse : pulse) : .52;
            const vehicleX = x1 + 12 + (span - 24) * amount;
            if (key === "nomad" || key.includes("_nomad")) {
              this.polygon([
                [vehicleX - 11, y + 2], [vehicleX - 6, y - 5],
                [vehicleX + 8, y - 5], [vehicleX + 12, y + 1], [vehicleX, y + 5],
              ], c, .92);
              for (const side of [-1, 1]) this.line(vehicleX + side * 7, y + 6, vehicleX + side * 12, y + 8 + pulse * 2, c, .72, 2);
            } else if (key.includes("_fighter")) {
              this.shipGlyph(vehicleX, y, c, .95, .78, true);
              this.line(vehicleX - 15, y + 8, vehicleX + 15, y + 8, c, .36);
            } else if (key.includes("_ship")) {
              this.shipGlyph(vehicleX, y, c, .95, .74);
              const bay = 13 + pulse * 5;
              for (const side of [-1, 1]) this.line(vehicleX + side * bay, y - 8, vehicleX + side * bay, y + 8, c, .5, 2);
            } else {
              this.polygon([
                [vehicleX - 10, y + 3], [vehicleX - 7, y - 5],
                [vehicleX + 7, y - 5], [vehicleX + 10, y + 3],
              ], c, .9);
              this.dot(vehicleX - 6, y + 6, 2, c, .9, false);
              this.dot(vehicleX + 6, y + 6, 2, c, .9, false);
            }
            if (key.includes("_crew")) {
              this.arc(vehicleX, y, 15, 9, p * TAU, p * TAU + Math.PI * 1.3, c, .55, 2);
            }
          }
          return;
        }

        if (label === "MULTICREW") {
          const nodes = [[cx - 13, y + 6], [cx, y - 8], [cx + 13, y + 6]];
          this.path([...nodes, nodes[0]], c, .42);
          nodes.forEach(([px, py], index) => this.dot(px, py, index === Math.floor(p * 3) % 3 ? 2.3 : 1.2, c, index === Math.floor(p * 3) % 3 ? .98 : .38));
          return;
        }

        if (label === "TAXI") {
          const route = [[x1 + 8, y + 4], [x1 + 33, y - 5], [cx + 8, y + 3], [x2 - 8, y - 3]];
          this.path(route, c, .4);
          const leg = Math.min(route.length - 1, Math.floor(p * route.length));
          route.forEach(([px, py], index) => this.dot(px, py, index === leg ? 2.2 : 1.1, c, index === leg ? .95 : .32));
          return;
        }

        // Normal flight/fighter identity: one ship, a rotating bearing arc and
        // an independent heading solution—not a mirrored velocity field.
        this.shipGlyph(cx, y, c, .94, label === "FIGHTER" ? .92 : .78, motion === "fighter");
        const angle = p * TAU;
        this.arc(cx, y, 18, 10, angle, angle + Math.PI * 1.35, c, .42);
        this.dot(cx + Math.cos(angle) * 18, y + Math.sin(angle) * 10, 1.4, c, .92);
        const solution = x1 + 6 + (cx - x1 - 18) * pulse;
        this.line(x1 + 5, y - 7, solution, y - 7, c, .45);
        this.line(solution, y - 10, solution, y - 4, c, .82, 2);
      });
    }

    drawDepthField(g, state, cue, alpha) {
      if (this.reduced) return;
      const c = state.color, y = g.y;
      this.withAlpha(alpha * (.62 + cue.activity * .38), () => {
        for (const [side, [x1, x2]] of [["left", this.wings(g)[0]], ["right", this.wings(g)[1]]]) {
          const span = Math.max(1, x2 - x1);
          if (cue.family === "fsd" || cue.family === "carrier") {
            const count = cue.family === "carrier" ? 3 : 4;
            for (let index = 0; index < count; index += 1) {
              const local = (cue.p * (cue.neutronBoost ? 2.7 : 1.6) + index / count + (side === "right" ? .13 : 0)) % 1;
              const accelerated = local * local;
              const x = x1 + span * accelerated;
              const py = y + [-9, -4, 4, 9][index % 4] * (1 - accelerated * .45);
              this.line(Math.max(x1, x - 3 - accelerated * 12), py, x, py, c, .09 + local * .12, 1);
            }
          } else if (cue.family === "scope") {
            for (let index = 0; index < 4; index += 1) {
              const amount = (index + .5) / 4;
              const x = x1 + span * amount;
              const active = Math.abs(((cue.p + index * .17) % 1) - .5) < .1;
              this.dot(x, y + [-8, 5, -3, 8][index], active ? 1.1 : .7, c, active ? .2 : .08);
            }
          } else if (cue.family === "surface") {
            const drift = cue.vertical * (side === "right" ? 1 : -1);
            for (let index = 0; index < 5; index += 1) {
              const local = (cue.p * (.42 + drift) + index / 5) % 1;
              const x = x1 + span * local;
              this.line(x, y + 8 - local * 3, x + 3 + local * 4, y + 8 - local * 3, c, .08 + local * .12);
            }
          } else if (cue.family === "hazard") {
            const shear = Math.sin(cue.p * TAU * 2) * (1.5 + cue.activity * 2.5);
            this.line(x1, y - 8 + shear, x2, y - 8 - shear, c, .09 + cue.activity * .1);
            this.line(x1, y + 8 - shear, x2, y + 8 + shear, c, .09 + cue.activity * .1);
          } else if (cue.family === "vehicle") {
            for (let index = 0; index < 5; index += 1) {
              const local = (cue.p + index / 5) % 1;
              const x = x1 + span * local;
              this.line(x, y + 9, x + 3, y + 9, c, .08 + (1 - local) * .1);
            }
          } else {
            for (let index = 0; index < 3; index += 1) {
              const local = (cue.p * .45 + index / 3) % 1;
              const x = x1 + span * local;
              this.line(x, y - 2, x, y + 2, c, .08 + cue.activity * .08);
            }
          }
        }
      });
    }

    drawEntryChoreography(g, state, cue, alpha) {
      if (this.reduced || cue.intro >= .999) return;
      const c = state.color, y = g.y;
      const remaining = 1 - cue.intro;
      this.withAlpha(alpha * remaining, () => {
        if (cue.family === "fsd" || cue.family === "carrier") {
          const squeeze = 4 + remaining * 30;
          this.line(g.leftEnd - squeeze, y - 11, g.leftEnd - squeeze, y + 11, c, .85, 2);
          this.line(g.rightStart + squeeze, y - 11, g.rightStart + squeeze, y + 11, c, .85, 2);
          for (const side of [-1, 1]) {
            const inner = side < 0 ? g.leftEnd : g.rightStart;
            const outer = inner + side * squeeze;
            this.line(outer, y, inner, y, c, .5, 2);
          }
        } else if (cue.family === "scope") {
          const left = g.left + (g.leftEnd - g.left) * cue.intro;
          const right = g.right - (g.right - g.rightStart) * cue.intro;
          this.line(left, y - 11, left, y + 11, c, .8, 2);
          this.line(right, y - 11, right, y + 11, c, .8, 2);
        } else if (cue.family === "surface") {
          const horizon = y + 10 - cue.intro * 7;
          this.line(g.left + 5, horizon, g.leftEnd - 4, horizon, c, .72, 2);
          this.line(g.rightStart + 4, horizon, g.right - 5, horizon, c, .72, 2);
          for (const x of [g.leftCenter, g.rightCenter]) this.line(x, horizon - 6 * remaining, x, horizon + 6 * remaining, c, .5);
        } else if (cue.family === "hazard") {
          const lock = 5 + remaining * 27;
          for (const cx of [g.leftCenter, g.rightCenter]) {
            for (const side of [-1, 1]) this.line(cx + side * lock, y - 10, cx + side * lock, y + 10, c, .9, 2);
          }
        } else if (cue.family === "vehicle") {
          const gate = 3 + remaining * 13;
          this.line(g.leftCenter - gate, y - 9, g.leftCenter - gate, y + 9, c, .72, 2);
          this.line(g.rightCenter + gate, y - 9, g.rightCenter + gate, y + 9, c, .72, 2);
        } else {
          const leftX = g.left + (g.leftEnd - g.left) * cue.intro;
          const rightX = g.right - (g.right - g.rightStart) * cue.intro;
          this.line(g.left, y, leftX, y, c, .72, 2);
          this.line(rightX, y, g.right, y, c, .72, 2);
          this.dot(leftX, y, 1.5, c, .9);
          this.dot(rightX, y, 1.5, c, .9);
        }
      });
    }

    drawActivityCouplers(g, state, cue, alpha) {
      if (this.reduced || cue.activity < .04) return;
      const c = state.color, y = g.y;
      const lift = cue.activity * (3 + cue.subBeat * 4);
      this.withAlpha(alpha * cue.activity, () => {
        this.line(g.leftEnd, y - 3 - lift, g.leftEnd, y + 3 + lift, c, .52 + cue.activity * .3, 2);
        this.line(g.rightStart, y - 3 - lift, g.rightStart, y + 3 + lift, c, .52 + cue.activity * .3, 2);
        if (cue.gravity > .4 && cue.family === "surface") {
          this.line(g.leftCenter - 10, y + 10, g.leftCenter + 10, y + 10, c, .35 + cue.gravity * .4, 2);
          this.line(g.rightCenter - 10, y + 10, g.rightCenter + 10, y + 10, c, .35 + cue.gravity * .4, 2);
        }
      });
    }

    drawStageSignature(g, state, cue, alpha) {
      if (this.reduced) return;
      const c = state.color, y = g.y;
      const [x1, x2] = this.wings(g)[1];
      const span = Math.max(1, x2 - x1), cx = (x1 + x2) / 2;
      this.withAlpha(alpha, () => {
        if (cue.family === "fsd") {
          if (cue.acquire > .01) {
            for (let index = 0; index < 3; index += 1) {
              const lane = [-7, 0, 7][index];
              const x = x1 + span * (.12 + cue.acquire * .42);
              this.line(x1 + 4, y + lane, x, y + lane * (1 - cue.acquire), c, cue.acquire * .32);
              this.dot(x, y + lane * (1 - cue.acquire), 1, c, cue.acquire * .58);
            }
          }
          if (cue.sustain > .01) {
            const aperture = 4 + cue.subBeat * 5;
            this.arc(cx, y, 14 + aperture, 5 + aperture * .35, 0, TAU, c, cue.sustain * .2);
          }
          if (cue.resolve > .01) this.arc(x2 - 12, y, 4 + cue.resolve * 11, 2 + cue.resolve * 4, 0, TAU, c, cue.resolve * .4, 2);
        } else if (cue.family === "scope") {
          const sweep = x1 + span * smoothstep(clamp(cue.p / .3));
          if (cue.acquire > .01) this.line(sweep, y - 10, sweep, y + 10, c, cue.acquire * .45, 2);
          if (cue.sustain > .01) {
            [0.23, .51, .79].forEach((amount, index) => this.dot(
              x1 + span * amount, y + [-6, 5, -2][index],
              1 + cue.subBeat, c, cue.sustain * .28,
            ));
          }
          if (cue.resolve > .01) {
            this.polygon([[x2 - 12, y - 4], [x2 - 8, y], [x2 - 12, y + 4], [x2 - 16, y]], c, cue.resolve * .48, false, 2);
          }
        } else if (cue.family === "surface") {
          if (cue.acquire > .01) {
            const marker = y - 9 + cue.acquire * 17;
            this.line(cx - 13, marker, cx - 4, marker, c, cue.acquire * .4, 2);
            this.line(cx + 4, marker, cx + 13, marker, c, cue.acquire * .4, 2);
          }
          if (cue.sustain > .01) {
            const compression = 1 + cue.gravity * 3;
            this.line(x1 + 4, y + 9, x2 - 4, y + 9, c, cue.sustain * (.16 + cue.gravity * .16), compression > 2 ? 2 : 1);
          }
          if (cue.resolve > .01) {
            const direction = cue.key.includes("departure") ? -1 : 1;
            const py = y + direction * (8 - cue.resolve * 15);
            this.path([[cx - 5, py - direction * 4], [cx, py], [cx + 5, py - direction * 4]], c, cue.resolve * .42, 2);
          }
        } else if (cue.family === "hazard") {
          const lock = 22 - cue.acquire * 14;
          if (cue.acquire > .01) {
            for (const side of [-1, 1]) this.line(cx + side * lock, y - 9, cx + side * lock, y + 9, c, cue.acquire * .46, 2);
          }
          if (cue.sustain > .01) {
            const shear = Math.sin(cue.p * TAU * 2) * 4;
            this.line(x1 + 5, y - shear, x2 - 5, y + shear, c, cue.sustain * .18);
          }
          if (cue.resolve > .01) this.arc(cx, y, 4 + cue.resolve * 18, 2 + cue.resolve * 7, 0, TAU, c, cue.resolve * .38, 2);
        } else if (cue.family === "vehicle") {
          const travel = cue.acquire > .01 ? cue.acquire : cue.resolve;
          if (travel > .01) {
            const x = x1 + 7 + (span - 14) * travel;
            this.line(Math.max(x1, x - 10), y, x, y, c, travel * .35, 2);
            this.dot(x, y, 1.2, c, travel * .56);
          }
          if (cue.sustain > .01) {
            for (const side of [-1, 1]) this.line(cx + side * (7 + cue.subBeat * 5), y - 7, cx + side * (7 + cue.subBeat * 5), y + 7, c, cue.sustain * .22);
          }
        } else if (cue.family === "carrier") {
          const fold = 7 + cue.acquire * 21;
          for (const side of [-1, 1]) this.line(cx + side * fold, y - 10, cx + side * fold, y + 10, c, cue.acquire * .42, 2);
          if (cue.resolve > .01) this.arc(cx, y, 5 + cue.resolve * 23, 2 + cue.resolve * 7, 0, TAU, c, cue.resolve * .35, 2);
        } else if (cue.routeActive && cue.sustain > .01) {
          const solution = x1 + span * (.2 + cue.route * .6);
          this.line(solution, y - 7, solution, y + 7, c, cue.sustain * .2);
          this.dot(solution, y, 1, c, cue.sustain * .4);
        }
      });
    }

    drawTransitionBridge(g, previous, next, progress) {
      if (this.reduced) return;
      const t = smoothstep(progress);
      const fromFamily = this.family(previous), toFamily = this.family(next);
      const c1 = previous.color, c2 = next.color, y = g.y;
      if (fromFamily === "fsd" || toFamily === "fsd" || fromFamily === "carrier" || toFamily === "carrier") {
        const aperture = 3 + Math.sin(t * Math.PI) * 20;
        this.line(g.leftEnd - aperture, y - 11, g.leftEnd - aperture, y + 11, c1, (1 - t) * .8, 2);
        this.line(g.rightStart + aperture, y - 11, g.rightStart + aperture, y + 11, c2, t * .8, 2);
        const packet = g.left + (g.right - g.left) * easeOut(t);
        this.line(Math.max(g.left, packet - 18), y, packet, y, t < .5 ? c1 : c2, .85, 2);
        this.dot(packet, y, 1.8, t < .5 ? c1 : c2, .95);
      } else if (fromFamily === "surface" || toFamily === "surface") {
        const bend = Math.sin(t * Math.PI) * 5;
        this.path([[g.left + 5, y + 8], [g.leftCenter, y + 3 - bend], [g.leftEnd - 4, y + 7]], c1, (1 - t) * .7, 2);
        this.path([[g.rightStart + 4, y + 7], [g.rightCenter, y + 3 + bend], [g.right - 5, y + 8]], c2, t * .7, 2);
      } else if (fromFamily === "scope" || toFamily === "scope") {
        const sweep = g.left + (g.right - g.left) * t;
        this.line(sweep, y - 12, sweep, y + 12, t < .5 ? c1 : c2, .85, 2);
        for (let index = 1; index <= 3; index += 1) this.line(sweep - index * 5, y - 9, sweep - index * 5, y + 9, t < .5 ? c1 : c2, .22 / index);
      } else if (fromFamily === "hazard" || toFamily === "hazard") {
        const shear = Math.sin(t * Math.PI) * 9;
        this.line(g.left + 5, y - shear, g.leftEnd - 4, y + shear, c1, (1 - t) * .75, 2);
        this.line(g.rightStart + 4, y + shear, g.right - 5, y - shear, c2, t * .75, 2);
      } else {
        const packet = g.left + (g.right - g.left) * t;
        this.line(Math.max(g.left, packet - 14), y, packet, y, t < .5 ? c1 : c2, .72, 2);
        this.dot(packet, y, 1.5, t < .5 ? c1 : c2, .9);
      }
    }

    drawLayer(g, state, phase, alpha, cue) {
      const previousCue = this.activeCue;
      this.activeCue = cue;
      this.drawDepthField(g, state, cue, alpha);
      this.drawLeftIdentity(g, state, phase, alpha);
      this.clipWing(g, "right", () => this.drawScene(g, state, phase, alpha));
      this.drawStageSignature(g, state, cue, alpha);
      this.drawEntryChoreography(g, state, cue, alpha);
      this.drawActivityCouplers(g, state, cue, alpha);
      this.activeCue = previousCue;
    }

    drawFlight(g, state, p, alpha, fighter = false) {
      const c = state.color, y = g.y;
      const cue = this.activeCue || {};
      this.withAlpha(alpha, () => {
        const x1 = g.rightStart + 8, x2 = g.right - 8, span = x2 - x1;
        if (fighter) {
          const tx = x1 + span * .7, size = 7 + wave(p) * 3;
          for (const side of [-1, 1]) {
            this.line(tx + side * size, y - 8, tx + side * size, y + 8, c, .8, 2);
            this.line(tx + side * size, y - 8, tx + side * (size - 5), y - 8, c, .55);
            this.line(tx + side * size, y + 8, tx + side * (size - 5), y + 8, c, .55);
          }
          for (let index = 0; index < 3; index += 1) {
            const local = (p + index / 3) % 1, x = x1 + (tx - x1) * local;
            this.line(Math.max(x1, x - 12), y + [-6, 0, 6][index], x, y + [-6, 0, 6][index], c, .7);
          }
        } else {
          this.line(x1, y, x2, y, c, .28);
          for (const offset of [-9, -5, 5, 9]) this.line(x1 + span * .25, y + offset, x1 + span * .35, y + offset, c, .25);
          const vx = x1 + span * (.5 + Math.sin(p * TAU) * .18);
          for (let trail = 3; trail >= 1; trail -= 1) {
            const oldPhase = (p - trail * (.025 + (cue.activity || 0) * .012) + 1) % 1;
            const oldX = x1 + span * (.5 + Math.sin(oldPhase * TAU) * .18);
            this.path([[oldX - 4, y - 3], [oldX, y], [oldX - 4, y + 3]], c, .08 + (4 - trail) * .045, 1);
          }
          this.path([[vx - 5, y - 4], [vx, y], [vx - 5, y + 4]], c, .9, 2);
          if (cue.routeActive) {
            const solution = x1 + span * (.22 + (cue.route || 0) * .56);
            this.line(solution, y - 8, solution, y + 8, c, .22 + (cue.activity || 0) * .16);
          }
        }
      });
    }

    drawSupercruise(g, state, p, alpha, overcharge = false) {
      const c = state.color, y = g.y, pulse = wave(p);
      this.withAlpha(alpha, () => {
        if (!overcharge) {
          const [x1, x2] = this.wings(g)[1];
          const span = Math.max(1, x2 - x1);
          const focusX = x2 - 7;

          // A perspective frame-shift corridor: fixed guide rails establish
          // depth while silent gates collapse towards the navigation focus.
          this.line(x1 + 2, y - 10, focusX, y - 2, c, .24);
          this.line(x1 + 2, y + 10, focusX, y + 2, c, .24);
          this.line(x1 + 2, y, focusX, y, c, .13);
          for (let index = 0; index < 5; index += 1) {
            const local = (p + index / 5) % 1;
            const depth = easeOut(local);
            const x = x1 + 4 + (focusX - x1 - 5) * depth;
            const half = 10 - depth * 7.5;
            const shoulder = 5 - depth * 3;
            const gateAlpha = Math.sin(local * Math.PI) * (.28 + depth * .62);
            this.line(x, y - half, x, y + half, c, gateAlpha, depth > .72 ? 2 : 1);
            this.line(x - shoulder, y - half, x + shoulder, y - half, c, gateAlpha * .62);
            this.line(x - shoulder, y + half, x + shoulder, y + half, c, gateAlpha * .62);
          }

          // The velocity solution bends within the corridor and carries three
          // fading after-images, so its wrap point is never visible.
          const spline = [];
          for (let index = 0; index <= 20; index += 1) {
            const amount = index / 20;
            const x = x1 + 4 + (focusX - x1 - 4) * amount;
            const amplitude = (1 - amount) * 3.6;
            const py = y + Math.sin((amount * 1.25 - p * 1.7) * TAU) * amplitude;
            spline.push([x, py]);
          }
          this.path(spline, c, .34, 1);
          for (let trail = 3; trail >= 0; trail -= 1) {
            const local = (p - trail * .035 + 1) % 1;
            const depth = easeOut(local);
            const x = x1 + 4 + (focusX - x1 - 4) * depth;
            const amplitude = (1 - depth) * 3.6;
            const py = y + Math.sin((depth * 1.25 - p * 1.7) * TAU) * amplitude;
            const trailAlpha = Math.sin(local * Math.PI) * (trail === 0 ? .95 : .08 + (3 - trail) * .08);
            this.dot(x, py, trail === 0 ? 1.8 : 1.1, c, trailAlpha);
            if (trail === 0) this.line(Math.max(x1 + 3, x - 8), py, x, py, c, trailAlpha * .72, 2);
          }

          const focusPulse = 1 + pulse * 2;
          this.dot(focusX, y, focusPulse, c, .72 + pulse * .2, false);
          this.line(focusX - 5, y - 6, focusX, y - 2, c, .46 + pulse * .24);
          this.line(focusX - 5, y + 6, focusX, y + 2, c, .46 + pulse * .24);
          return;
        }

        for (const [wingIndex, [x1, x2]] of [[1, this.wings(g)[1]]]) {
          const span = x2 - x1;
          for (const lane of [-8, 0, 8]) this.line(x1, y + lane, x2, y + lane * .25, c, .2);
          const count = overcharge ? 10 : 7;
          for (let index = 0; index < count; index += 1) {
            const local = (p + index / count + wingIndex * .09) % 1;
            const fast = local * local, x = x1 + span * fast;
            const lane = [-8, 0, 8][index % 3], py = y + lane * (1 - fast * .72);
            const length = 5 + fast * (overcharge ? 34 : 25);
            this.line(Math.max(x1, x - length), py, x, py, c, local > .7 ? .95 : .48, local > .75 ? 2 : 1);
          }
          const front = x1 + span * p, edge = Math.sin(p * Math.PI);
          this.line(front, y - edge * 10, front, y + edge * 10, c, .35 + edge * .5, overcharge ? 2 : 1);
        }
        if (overcharge) {
          const jag = [[g.leftEnd - 34, y], [g.leftEnd - 25, y - 7], [g.leftEnd - 17, y + 6], [g.leftEnd - 8, y]];
          this.path(jag.map(([x, py]) => [g.width - x, 2 * y - py]), c, .9, 2);
        }
      });
    }

    drawTaxi(g, state, p, alpha) {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const [wingIndex, [x1, x2]] of [[1, this.wings(g)[1]]]) {
          const span = x2 - x1;
          const offsets = wingIndex ? [5, -5, 3, -3] : [-4, 5, -2, 4];
          const points = offsets.map((offset, index) => [x1 + span * index / 3, y + offset]);
          this.path(points, c, .35);
          const active = Math.min(3, Math.floor(p * 4));
          points.forEach(([x, py], index) => this.dot(
            x, py, index === active ? 2.2 : 1.1, c, index === active ? 1 : .35,
          ));
        }
      });
    }

    drawMulticrew(g, state, p, alpha) {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const [x1, x2] of [this.wings(g)[1]]) {
          const center = (x1 + x2) / 2;
          this.arc(center, y, 18, 10, .45, Math.PI - .45, c, .48);
          this.arc(center, y, 18, 10, Math.PI + .45, TAU - .45, c, .48);
          this.line(center - 13, y, center + 13, y, c, .28);
          [-9, 0, 9].forEach((offset, index) => {
            const local = (p + index / 3) % 1;
            this.dot(center + offset, y, local < .34 ? 2.2 : 1.2, c, local < .34 ? 1 : .38);
          });
        }
      });
    }

    drawFsd(g, state, p, alpha, variant) {
      const c = state.color, y = g.y;
      const cue = this.activeCue || {};
      this.withAlpha(alpha, () => {
        if (variant === "charge" || variant === "hyper_charge") {
          for (const [x1, x2, reverse] of [[g.rightStart + 6, g.right - 6, true]]) {
            const span = x2 - x1;
            const count = variant === "hyper_charge" ? 8 : 6;
            for (let index = 0; index < count; index += 1) {
              const local = (p + index / count) % 1;
              const x = reverse ? x2 - span * local : x1 + span * local;
              const lane = [-7, 0, 7][index % 3];
              this.line(x - (reverse ? -11 : 11), y + lane, x, y + lane, c, .65, local > .75 ? 2 : 1);
              this.dot(x, y + lane, 1.2, c, .9);
            }
          }
          const squeeze = 4 + wave(p) * 9;
          this.line(g.rightStart + squeeze, y - 10, g.rightStart + squeeze, y + 10, c, .9, 2);
          if (variant === "hyper_charge") {
            this.arc(g.rightCenter, y, 9 + wave(p) * 14, 5 + wave(p) * 4, 0, TAU, c, .72, 2);
            this.path([[g.rightStart + 8, y], [g.rightStart + 18, y - 8], [g.rightStart + 28, y + 7], [g.rightStart + 39, y]], c, .92, 2);
            if (cue.neutronBoost) {
              const flare = 12 + cue.subBeat * 10;
              this.arc(g.rightCenter, y, flare, flare * .42, p * TAU, p * TAU + Math.PI * 1.55, c, .72, 2);
              this.line(g.rightStart + 5, y - 10, g.right - 7, y + 7, c, .32 + cue.subBeat * .25, 2);
            }
          }
        } else if (variant === "hyperspace" || variant === "jumping") {
          for (const [wingIndex, [x1, x2]] of [[1, this.wings(g)[1]]]) {
            const span = x2 - x1;
            const count = variant === "hyperspace" ? 11 : 7;
            for (let index = 0; index < count; index += 1) {
              const local = (p + index / count + wingIndex * .13) % 1;
              const x = x1 + span * local, lane = [-10, -5, 0, 5, 10][index % 5];
              const length = variant === "hyperspace" ? 10 + local * 31 : 5 + local * 18;
              this.line(Math.max(x1, x - length), y + lane, x, y + lane, c, .4 + local * .55, local > .7 ? 2 : 1);
            }
          }
          const aperture = 2 + wave(p) * 11;
          this.line(g.rightStart + aperture, g.top + 1, g.rightStart + aperture, g.bottom, c, .9, 2);
          if (variant === "jumping") {
            for (let index = 0; index < 3; index += 1) {
              const x = g.rightStart + 19 + index * 21;
              this.path([[x - 6, y - 7], [x, y], [x - 6, y + 7]], c, index === Math.floor(p * 3) ? .95 : .28, index === Math.floor(p * 3) ? 2 : 1);
            }
          }
        } else if (variant === "arrival" || variant === "interdiction_evaded") {
          for (const [side, start, end] of [[1, g.rightStart + 4, g.right - 5]]) {
            const x = start + (end - start) * p;
            this.arc(x, y, 5 + p * 8, 5 + p * 5, 0, TAU, c, 1 - p, 2);
            this.line(start, y, x, y, c, .55, 2);
          }
          if (variant === "interdiction_evaded") {
            const x1 = g.rightStart + 7, x2 = g.right - 7;
            this.path([[x1, y + 7], [x1 + (x2 - x1) * .38, y - 7], [x2, y]], c, .78, 2);
            this.shipGlyph(x1 + (x2 - x1) * p, y + Math.sin(p * Math.PI) * -7, c, .95, .52);
          }
        } else {
          for (const cx of [g.rightCenter]) {
            for (let index = 0; index < 3; index += 1) {
              const local = (p + index / 3) % 1, radius = 4 + local * 13;
              this.arc(cx, y, radius, radius * .55, 0, TAU, c, 1 - local, 1);
            }
          }
        }
      });
    }

    drawScanner(g, state, p, alpha, map = false) {
      const c = state.color, y = g.y;
      const cue = this.activeCue || {};
      this.withAlpha(alpha, () => {
        for (const [wingIndex, [x1, x2]] of [[1, this.wings(g)[1]]]) {
          const span = x2 - x1;
          if (map) {
            const offsets = wingIndex ? [-4, 6, -2, 8, 1] : [5, -6, 2, -8, 0];
            const points = offsets.map((offset, index) => [x1 + span * index / 4, y + offset]);
            this.path(points, c, .35);
            const active = Math.min(4, Math.floor(p * 5));
            points.forEach(([x, py], index) => this.dot(x, py, index === active ? 2 : 1, c, index === active ? 1 : .35));
          } else if (state.label === "DSS") {
            const cx = (x1 + x2) / 2;
            for (let index = 0; index < 3; index += 1) {
              const local = (p + index / 3) % 1;
              const radius = 4 + local * Math.min(24, span * .25);
              this.arc(cx, y, radius, radius * .48, 0, TAU, c, (1 - local) * (.82 + (cue.activity || 0) * .18), local > .65 ? 2 : 1);
            }
            const beamPhase = cue.scan > 0 ? (p * .72 + cue.scan * .28) % 1 : p;
            const beam = x1 + span * wave(beamPhase);
            this.line(beam, y - 11, beam, y + 11, c, .75, 2);
            this.dot(cx, y, 2, c, .95);
          } else {
            const sweepPhase = cue.scan > 0 ? (p * .74 + cue.scan * .26) % 1 : p;
            const sweepTravel = wave(sweepPhase);
            const sweep = x1 + span * sweepTravel;
            this.line(sweep, y - 11, sweep, y + 11, c, .9, 2);
            const contacts = [.12, .31, .54, .78, .91];
            contacts.forEach((amount, index) => {
              const delta = Math.abs(amount - sweepTravel), py = y + [-7, 4, -2, 8, -5][index];
              this.dot(x1 + span * amount, py, delta < .08 ? 2 : 1, c, delta < .08 ? 1 : .35);
            });
            this.arc((x1 + x2) / 2, y, span * .23, 11, sweepTravel * TAU, sweepTravel * TAU + 1.1, c, .65);
          }
        }
      });
    }

    drawMapState(g, state, p, alpha, variant) {
      const c = state.color, y = g.y;
      const [x1, x2] = this.wings(g)[1];
      const span = x2 - x1, cx = (x1 + x2) / 2;
      this.withAlpha(alpha, () => {
        if (variant === "galaxy_map") {
          const nodes = [];
          for (let index = 0; index < 9; index += 1) {
            const amount = index / 8;
            const angle = amount * Math.PI * 3.2 + p * TAU * .22;
            const radius = 3 + amount * Math.min(31, span * .32);
            nodes.push([cx + Math.cos(angle) * radius, y + Math.sin(angle) * radius * .32]);
          }
          this.path(nodes, c, .5, 1.3);
          const index = Math.min(nodes.length - 1, Math.floor(p * nodes.length));
          nodes.forEach(([px, py], node) => this.dot(px, py, node === index ? 2 : .8, c, node === index ? 1 : .32));
          const route = [[x1 + 6, y + 7], [cx - 7, y - 6], [cx + 15, y + 4], [x2 - 5, y - 5]];
          this.path(route, c, .3);
          const leg = Math.min(2, Math.floor(p * 3));
          const local = p * 3 - leg;
          this.dot(
            route[leg][0] + (route[leg + 1][0] - route[leg][0]) * local,
            route[leg][1] + (route[leg + 1][1] - route[leg][1]) * local,
            1.5, c, Math.sin(p * Math.PI) * .9,
          );
        } else if (variant === "system_map") {
          this.dot(cx - 10, y, 2.8, c, .98);
          [11, 21, 32].forEach((radius, index) => {
            this.arc(cx - 10, y, radius, 4 + index * 2.5, 0, TAU, c, .25 + index * .08);
            const angle = p * TAU * (1 + index * .28) + index * 1.7;
            const px = cx - 10 + Math.cos(angle) * radius;
            const py = y + Math.sin(angle) * (4 + index * 2.5);
            this.dot(px, py, 1.1 + index * .25, c, .88);
            if (index === 2) this.arc(px, py, 4, 2, 0, TAU, c, .46);
          });
        } else if (variant === "orrery") {
          for (let index = 0; index < 4; index += 1) {
            const radius = 10 + index * 8;
            const tilt = -.35 + index * .22;
            this.arc(cx, y, radius, radius * .25, tilt, tilt + TAU, c, .24 + index * .08);
            const angle = p * TAU * (1 + index * .17) + index * 1.4;
            this.dot(cx + Math.cos(angle) * radius, y + Math.sin(angle + tilt) * radius * .25, 1 + index * .22, c, .88);
          }
          this.line(cx, y - 11, cx, y + 11, c, .28);
        } else if (variant === "power_map") {
          const active = Math.floor(p * 7);
          for (let index = 0; index < 7; index += 1) {
            const column = index % 4, row = Math.floor(index / 4);
            const px = cx - 25 + column * 17 + (row ? 8 : 0);
            const py = y - 5 + row * 11;
            const size = index === active ? 6 : 5;
            this.polygon(Array.from({length: 6}, (_, point) => [
              px + Math.cos(point * TAU / 6) * size,
              py + Math.sin(point * TAU / 6) * size,
            ]), c, index === active ? .98 : .28, index === active, index === active ? 2 : 1);
          }
          const border = x1 + span * wave(p);
          this.line(border, y - 10, border, y + 10, c, .48, 2);
        } else if (variant === "codex") {
          const pageX = x1 + span * .28, pageRight = x2 - 7;
          this.polygon([[pageX, y - 10], [pageRight - 5, y - 10], [pageRight, y - 5], [pageRight, y + 10], [pageX, y + 10]], c, .42);
          const active = Math.floor(p * 6);
          for (let index = 0; index < 6; index += 1) {
            const py = y - 7.5 + index * 3;
            const width = [29, 47, 36, 51, 23, 42][index];
            this.line(pageX + 6, py, Math.min(pageRight - 5, pageX + 6 + width), py, c, index === active ? .98 : .25, index === active ? 2 : 1);
          }
          const scan = pageX + (pageRight - pageX) * wave(p);
          this.line(scan, y - 10, scan, y + 10, c, .45);
        } else {
          const rows = [-8, 0, 8];
          rows.forEach((py, index) => this.line(x1 + index * 4, y + py, x2 - (2 - index) * 4, y + py, c, .2));
          for (let index = 0; index < 6; index += 1) {
            const px = x1 + span * index / 5;
            this.line(px, y - 10, px, y + 10, c, .16);
          }
          const vector = x1 + span * wave(p);
          this.path([[Math.max(x1, vector - 9), y - 7], [vector, y], [Math.max(x1, vector - 9), y + 7]], c, .9, 2);
        }
      });
    }

    drawHold(g, state, p, alpha) {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const [x1, x2] of [this.wings(g)[1]]) {
          const span = x2 - x1, center = (x1 + x2) / 2;
          this.line(x1, y + 7, x2, y + 7, c, .42, 2);
          this.line(center - 17, y - 4, center + 17, y - 4, c, .75, 2);
          for (const x of [center - 17, center, center + 17]) {
            this.line(x, y - 4, x, y + 7, c, .35 + wave(p) * .35);
          }
          const pulse = 3 + wave(p) * 5;
          this.line(center - pulse, y + 10, center + pulse, y + 10, c, .85, 2);
        }
      });
    }

    drawStation(g, state, p, alpha, landed = false) {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const cx of [g.rightCenter]) {
          if (state.label === "STATION") {
            const angle = p * TAU;
            this.arc(cx, y, 25, 10, angle, angle + Math.PI * 1.5, c, .72, 2);
            this.arc(cx, y, 15, 6, -angle * .6, -angle * .6 + Math.PI * 1.2, c, .38);
            this.polygon([[cx - 6, y - 5], [cx + 6, y - 5], [cx + 9, y], [cx + 6, y + 5], [cx - 6, y + 5], [cx - 9, y]], c, .85);
            this.dot(cx + Math.cos(angle) * 25, y + Math.sin(angle) * 10, 1.5, c, .95);
          } else if (landed) {
            this.line(cx - 23, y + 9, cx + 23, y + 9, c, .35);
            this.line(cx - 12, y - 5, cx + 12, y - 5, c, .75, 2);
            for (const x of [cx - 12, cx, cx + 12]) {
              this.line(x, y - 5, x, y + 9, c, .55);
              this.dot(x, y + 9, 1.3 + wave(p) * .4, c, .85);
            }
          } else {
            const clamp = 10 + (1 - wave(p)) * 7;
            this.polygon([[cx - 28, y - 10], [cx + 28, y - 10], [cx + 20, y + 10], [cx - 20, y + 10]], c, .3);
            this.polygon([[cx - 8, y - 5], [cx + 8, y - 5], [cx + 8, y + 5], [cx - 8, y + 5]], c, .8);
            for (const side of [-1, 1]) {
              this.line(cx + side * clamp, y - 8, cx + side * (clamp - 5), y - 8, c, .8, 2);
              this.line(cx + side * clamp, y + 8, cx + side * (clamp - 5), y + 8, c, .8, 2);
            }
          }
        }
      });
    }

    drawSurface(g, state, p, alpha, variant) {
      const c = state.color, y = g.y, departing = variant.includes("departure");
      const cue = this.activeCue || {};
      this.withAlpha(alpha, () => {
        for (const [x1, x2] of [this.wings(g)[1]]) {
          const span = x2 - x1;
          if (variant === "orbital_approach") {
            this.arc(x2 + 5, y + 10, span * .58, 18, Math.PI, Math.PI * 1.55, c, .46, 2);
            const marker = x1 + span * p;
            this.shipGlyph(marker, y - 6 + p * 9, c, .94, .5);
            for (let index = 0; index < 5; index += 1) {
              const x = x1 + 6 + index * span / 5;
              this.line(x, y + 7 - index, x + 7, y + 7 - index, c, index === Math.floor(p * 5) ? .95 : .25, index === Math.floor(p * 5) ? 2 : 1);
            }
          } else if (variant === "glide") {
            const horizon = y - 5 + p * (7 + (cue.vertical || 0) * 2);
            this.line(x1, horizon, x2, horizon, c, .72, 2);
            this.line(x1, y + 10, x1 + span * .48, horizon, c, .42);
            this.line(x2, y + 10, x1 + span * .52, horizon, c, .42);
            for (let index = 0; index < 5; index += 1) {
              const depth = (p + index / 5) % 1;
              const half = 4 + depth * span * .46;
              const py = horizon + depth * (y + 10 - horizon);
              this.line(Math.max(x1, x1 + span / 2 - half), py, Math.min(x2, x1 + span / 2 + half), py, c, (1 - depth) * .65);
            }
          } else if (variant === "orbital_departure") {
            this.arc(x1 - 5, y + 10, span * .58, 18, Math.PI * 1.45, TAU, c, .46, 2);
            const marker = x1 + span * p;
            this.shipGlyph(marker, y + 4 - p * 11, c, .94, .5);
            for (let index = 0; index < 3; index += 1) {
              const local = (p + index / 3) % 1;
              this.arc(x1 + span * .3, y + 7, 5 + local * 25, 2 + local * 6, Math.PI, TAU, c, (1 - local) * .7);
            }
          } else {
            this.line(x1, y + 10, x2, y + 3, c, .32);
            const local = departing ? 1 - p : p;
            const active = Math.min(7, Math.floor(local * 8));
            for (let index = 0; index < 8; index += 1) {
              const x = x1 + span * (index + .5) / 8, distance = Math.abs(index - active);
              const height = 3 + (index % 3) * 2 + (cue.gravity || 0) * 2;
              this.line(x, y - height, x, y + height, c, distance === 0 ? 1 : distance === 1 ? .6 : .22, distance === 0 || (cue.gravity || 0) > .7 ? 2 : 1);
            }
            if (variant === "surface_departure") {
              const shipX = x1 + span * (.24 + p * .68);
              this.shipGlyph(shipX, y + 5 - p * 12, c, .92, .48);
              this.line(Math.max(x1, shipX - 20), y + 8, shipX - 7, y + 2, c, .45, 2);
            } else {
              const targetX = x1 + span * (.18 + p * .64);
              this.line(targetX, y - 10, targetX, y + 9, c, .8, 2);
              this.dot(targetX, y + 3, 1.5, c, .95);
              if (cue.landingGear) {
                this.line(targetX - 8, y + 8, targetX - 3, y + 5, c, .72, 2);
                this.line(targetX + 8, y + 8, targetX + 3, y + 5, c, .72, 2);
              }
            }
          }
        }
      });
    }

    drawVehicle(g, state, p, alpha, foot = false) {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const [wingIndex, [x1, x2]] of [[1, this.wings(g)[1]]]) {
          const span = x2 - x1;
          if (foot) {
            for (let index = 0; index < 7; index += 1) {
              const local = (p + index / 7) % 1, x = x1 + span * local;
              const py = y + (index % 2 ? -4 : 4);
              this.arc(x, py, 3, 1.5, 0, TAU, c, index < 2 ? .9 : .28, 1);
            }
          } else if (this.animationKey(state) === "nomad") {
            const terrain = [];
            for (let index = 0; index <= 16; index += 1) {
              const amount = index / 16, x = x1 + span * amount;
              terrain.push([x, y + 8 + Math.sin((amount + p) * TAU) * 1.2]);
            }
            this.path(terrain, c, .25);
            const vehicleX = x1 + span * .56;
            this.polygon([[vehicleX - 12, y + 1], [vehicleX - 7, y - 6], [vehicleX + 8, y - 6], [vehicleX + 13, y + 1], [vehicleX, y + 5]], c, .9);
            for (const side of [-1, 1]) {
              this.line(vehicleX + side * 7, y + 6, vehicleX + side * (12 + wave(p) * 3), y + 9, c, .78, 2);
              this.line(vehicleX + side * 15, y + 9, vehicleX + side * 22, y + 9, c, .22 + wave(p) * .3);
            }
            const scan = x1 + span * p;
            this.line(scan, y - 9, scan, y + 8, c, .4);
          } else {
            const terrain = [];
            for (let index = 0; index <= 16; index += 1) {
              const amount = index / 16, x = x1 + span * amount;
              terrain.push([x, y + 7 + Math.sin((amount + p) * TAU * 2) * 2]);
            }
            this.path(terrain, c, .28);
            const vehicleX = x1 + span * (wingIndex ? .62 : .38);
            this.polygon([[vehicleX - 9, y + 2], [vehicleX - 7, y - 5], [vehicleX + 7, y - 5], [vehicleX + 10, y + 2]], c, .85);
            this.dot(vehicleX - 6, y + 5, 2, c, .9, false);
            this.dot(vehicleX + 6, y + 5, 2, c, .9, false);
          }
        }
      });
    }

    drawHandoff(g, state, p, alpha, variant) {
      const c = state.color, y = g.y, reverse = variant === "vehicle_board";
      const key = this.animationKey(state);
      this.withAlpha(alpha, () => {
        for (const [x1, x2] of [this.wings(g)[1]]) {
          const amount = reverse ? 1 - wave(p) : wave(p);
          const x = x1 + (x2 - x1) * amount;
          this.line(x1, y + 7, x2, y + 7, c, .28);
          if (key.includes("_fighter")) {
            this.shipGlyph(x, y, c, .95, .7, true);
          } else if (key.includes("_nomad")) {
            this.polygon([[x - 9, y + 1], [x - 5, y - 5], [x + 6, y - 5], [x + 10, y + 1], [x, y + 4]], c, .92);
            this.line(x - 9, y + 7, x - 4, y + 4, c, .72, 2);
            this.line(x + 9, y + 7, x + 4, y + 4, c, .72, 2);
          } else if (key.includes("_crew")) {
            const nodes = [[x - 7, y + 5], [x, y - 6], [x + 7, y + 5]];
            this.path([...nodes, nodes[0]], c, .7);
            nodes.forEach(([px, py], index) => this.dot(px, py, index === Math.floor(p * 3) ? 2 : 1.2, c, index === Math.floor(p * 3) ? .98 : .45));
          } else if (key.includes("_ship")) {
            this.shipGlyph(x, y, c, .95, .68);
          } else {
            this.polygon([[x - 6, y - 4], [x + 6, y - 4], [x + 6, y + 3], [x - 6, y + 3]], c, .9);
            this.dot(x - 4, y + 5, 1.4, c, .8); this.dot(x + 4, y + 5, 1.4, c, .8);
          }
          if (variant === "vehicle_switch") {
            const other = x1 + (x2 - x1) * (1 - amount);
            this.polygon([[other, y - 6], [other + 5, y], [other, y + 6], [other - 5, y]], c, .6);
          } else {
            const bayX = reverse ? x1 + 7 : x2 - 7;
            const gate = 4 + wave(p) * 4;
            this.line(bayX, y - gate, bayX, y + gate, c, .88, 2);
            this.line(bayX - 5, y - gate, bayX + 5, y - gate, c, .42);
            this.line(bayX - 5, y + gate, bayX + 5, y + gate, c, .42);
          }
        }
      });
    }

    drawHazard(g, state, p, alpha, variant = "mass") {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const [wingIndex, [x1, x2]] of [[1, this.wings(g)[1]]]) {
          const span = x2 - x1;
          if (variant === "asteroid") {
            for (let index = 0; index < 8; index += 1) {
              const local = (p + index / 8 + wingIndex * .17) % 1;
              const x = x1 + span * local, py = y + Math.sin(index * 2.2 + p * TAU) * 9;
              const r = 1.5 + index % 3;
              this.polygon([[x, py - r], [x + r, py], [x, py + r], [x - r, py]], c, index < 2 ? .9 : .35);
            }
          } else if (variant === "combat") {
            const cx = x1 + span * .68, rotation = p * Math.PI;
            this.arc(cx, y, 13, 10, .3 + rotation, 2.2 + rotation, c, .9, 2);
            this.arc(cx, y, 13, 10, Math.PI + .3 + rotation, Math.PI + 2.2 + rotation, c, .9, 2);
            for (const side of [-1, 1]) {
              const points = [];
              for (let index = 0; index <= 8; index += 1) {
                const amount = index / 8, x = x1 + (cx - x1) * amount;
                points.push([x, y + side * (1 - amount) * 8 * Math.sin(p * TAU + amount * Math.PI)]);
              }
              this.path(points, c, .62, 2);
            }
            this.dot(cx, y, 1.8, c, 1);
          } else if (variant === "interdiction") {
            const cx = x1 + span * .72;
            for (let index = 0; index < 4; index += 1) {
              const local = (p + index / 4) % 1;
              const rx = 5 + local * 25, ry = 3 + local * 8;
              this.arc(cx, y, rx, ry, p * TAU + local, p * TAU + local + Math.PI * 1.45, c, (1 - local) * .9, local < .3 ? 2 : 1);
            }
            const shear = Math.sin(p * TAU) * 7;
            this.line(x1 + 4, y - shear, cx - 7, y + shear * .35, c, .72, 2);
            this.line(x1 + 4, y + shear, cx - 7, y - shear * .35, c, .72, 2);
            this.polygon([[cx, y - 6], [cx + 6, y], [cx, y + 6], [cx - 6, y]], c, .95, false, 2);
          } else if (variant === "interdicted") {
            const cx = x1 + span * .66;
            const lock = 6 + (1 - wave(p)) * 19;
            this.shipGlyph(cx, y, c, .94, .56);
            for (const side of [-1, 1]) {
              this.line(cx + side * lock, y - 10, cx + side * lock, y + 10, c, .92, 2);
              this.line(cx + side * lock, y - 10, cx + side * (lock - 8), y - 10, c, .52);
              this.line(cx + side * lock, y + 10, cx + side * (lock - 8), y + 10, c, .52);
            }
            for (let index = 0; index < 3; index += 1) {
              const local = (p + index / 3) % 1;
              this.line(x1 + 4 + span * .34 * local, y + [-7, 0, 7][index], x1 + 10 + span * .34 * local, y + [-7, 0, 7][index], c, (1 - local) * .75);
            }
          } else if (["signal_lock", "signal_drop", "signal_threat"].includes(variant)) {
            const target = x1 + span * .76, samples = [];
            for (let index = 0; index <= 14; index += 1) {
              const amount = index / 14, x = x1 + span * amount;
              const envelope = 1 - Math.abs(amount - .72);
              const gain = variant === "signal_threat" ? 9 : variant === "signal_drop" ? 5 : 6;
              samples.push([x, y + Math.sin(index * (variant === "signal_threat" ? 2.35 : 1.7) + p * TAU) * gain * envelope]);
            }
            this.path(samples, c, .7, 1);
            const size = 5 + wave(p) * (variant === "signal_threat" ? 5 : 3);
            this.polygon([[target, y - size], [target + size, y], [target, y + size], [target - size, y]], c, .95, false, 2);
            if (variant === "signal_drop") {
              const vector = x1 + span * p;
              this.path([[Math.max(x1, vector - 8), y - 6], [vector, y], [Math.max(x1, vector - 8), y + 6]], c, .85, 2);
            } else if (variant === "signal_threat") {
              for (const side of [-1, 1]) {
                this.line(target + side * 14, y - 10, target + side * 14, y + 10, c, .68 + wave(p) * .25, 2);
              }
            }
          } else {
            const cx = (x1 + x2) / 2, radius = 7 + wave(p) * 7;
            this.dot(cx, y, 2.5, c, .9);
            this.arc(cx, y, radius, radius * .62, .2, Math.PI - .2, c, .75, 2);
            this.arc(cx, y, radius, radius * .62, Math.PI + .2, TAU - .2, c, .75, 2);
            this.line(cx - 18, y + 10, cx + 18, y - 10, c, .7, 2);
          }
        }
      });
    }

    drawCarrier(g, state, p, alpha, arrival = false) {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const [x1, x2] of [this.wings(g)[1]]) {
          const span = x2 - x1;
          for (const lane of [-7, 0, 7]) this.line(x1, y + lane, x2, y + lane, c, .2);
          for (let index = 0; index < 6; index += 1) {
            const local = (p + index / 6) % 1;
            const amount = arrival ? 1 - local : local;
            const x = x1 + span * amount, lane = [-7, 0, 7][index % 3];
            this.line(Math.max(x1, x - 19), y + lane, x, y + lane, c, .7, 2);
          }
          for (let index = 0; index < 2; index += 1) {
            const local = (p + index * .5) % 1;
            const amount = arrival ? 1 - local : local;
            const fold = x1 + span * amount;
            this.polygon([[fold, y - 11], [fold + 6, y], [fold, y + 11], [fold - 6, y]], c, Math.sin(local * Math.PI) * .85, false, 2);
          }
        }
      });
    }

    drawExploration(g, state, p, alpha) {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const [x1, x2] of [this.wings(g)[1]]) {
          const sweepPhase = wave(p);
          const span = x2 - x1, sweep = x1 + span * sweepPhase;
          this.line(sweep, y - 10, sweep, y + 10, c, .85, 2);
          [.16, .39, .63, .84].forEach((amount, index) => {
            const x = x1 + span * amount, py = y + [-6, 4, -2, 7][index];
            const active = Math.abs(amount - sweepPhase) < .09;
            this.dot(x, py, active ? 2 : 1, c, active ? 1 : .3);
            if (active) this.arc(x, py, 5 + wave(p) * 4, 5 + wave(p) * 4, 0, TAU, c, .55);
          });
        }
      });
    }

    drawScene(g, state, phase, alpha) {
      const motion = state.motion;
      const key = this.animationKey(state);
      if (motion === "supercruise") {
        return state.label === "TAXI"
          ? this.drawTaxi(g, state, phase, alpha)
          : this.drawSupercruise(g, state, phase, alpha);
      }
      if (motion === "supercruise_overcharge") return this.drawSupercruise(g, state, phase, alpha, true);
      if (motion === "fsd_charge") return this.drawFsd(g, state, phase, alpha, key);
      if (motion === "jump") return this.drawFsd(g, state, phase, alpha, key);
      if (motion === "arrival" || motion === "carrier_arrival") {
        return motion === "carrier_arrival"
          ? this.drawCarrier(g, state, phase, alpha, true)
          : this.drawFsd(g, state, phase, alpha, key);
      }
      if (motion === "fsd_cooldown") return this.drawFsd(g, state, phase, alpha, "cooldown");
      if (motion === "scanner") return this.drawScanner(g, state, phase, alpha);
      if (motion === "map") return this.drawMapState(g, state, phase, alpha, key);
      if (["orbital_approach", "glide", "surface_approach", "surface_hold", "surface_departure", "orbital_departure"].includes(motion)) {
        if (motion === "surface_hold") return this.drawHold(g, state, phase, alpha);
        return this.drawSurface(g, state, phase, alpha, motion);
      }
      if (motion === "docked") return this.drawStation(g, state, phase, alpha);
      if (motion === "landed") return this.drawStation(g, state, phase, alpha, true);
      if (motion === "surface_vehicle") return this.drawVehicle(g, state, phase, alpha);
      if (motion === "on_foot") return this.drawVehicle(g, state, phase, alpha, true);
      if (["vehicle_deploy", "vehicle_board", "vehicle_switch"].includes(motion)) return this.drawHandoff(g, state, phase, alpha, motion);
      if (motion === "fsd_lock") return this.drawHazard(g, state, phase, alpha, key);
      if (motion === "combat") return this.drawHazard(g, state, phase, alpha, key);
      if (motion === "asteroid_field") return this.drawHazard(g, state, phase, alpha, "asteroid");
      if (motion === "carrier_transit") return this.drawCarrier(g, state, phase, alpha);
      if (motion === "fighter") return this.drawFlight(g, state, phase, alpha, true);
      if (motion === "exploration") return this.drawExploration(g, state, phase, alpha);
      if (motion === "flight" && state.label === "MULTICREW") return this.drawMulticrew(g, state, phase, alpha);
      return this.drawFlight(g, state, phase, alpha);
    }

    eventResponse(g, now) {
      const elapsed = (now - this.eventStarted) / 900;
      if (!this.eventStarted || elapsed < 0 || elapsed > 1) return;
      const c = this.state.color, y = g.y;
      const ease = elapsed * elapsed * (3 - 2 * elapsed);
      if (["hazard", "signal"].includes(this.eventKind)) {
        const shear = Math.sin(elapsed * Math.PI) * 7;
        this.line(g.left + 8, y - shear, g.leftEnd - 5, y + shear, c, .75, 2);
        const radius = 4 + Math.sin(elapsed * Math.PI) * 12;
        this.arc(g.rightCenter, y, radius, radius * .58, 0, TAU, c, .85 * (1 - elapsed), 2);
        this.line(g.rightCenter - radius - 5, y, g.rightCenter + radius + 5, y, c, .48 * (1 - elapsed));
      } else if (RESOURCE_EVENTS.has(this.eventKind)) {
        const cx = g.rightCenter, rx = 13, ry = 8;
        this.polygon([
          [cx - rx, y - 1], [cx - 8, y - ry], [cx + 1, y - 6],
          [cx + rx, y - 1], [cx + 8, y + ry], [cx - 5, y + 6],
        ], c, .45 + (1 - elapsed) * .4);
        if (this.eventKind === "mining_refined") {
          const target = g.right - 13;
          this.polygon([[target - 7, y - 6], [target + 7, y - 6], [target + 7, y + 6], [target - 7, y + 6]], c, .82);
          for (let index = 0; index < 4; index += 1) {
            const local = clamp(ease * 1.2 - index * .08);
            const px = cx + 6 + (target - cx - 14) * local;
            const py = y + (index - 1.5) * 4 * (1 - local);
            this.dot(px, py, 1.4, c, .9 - elapsed * .4);
          }
        } else {
          const sweep = cx - rx + rx * 2 * ease;
          this.line(sweep, y - ry, sweep, y + ry, c, .95, 2);
          if (this.eventKind === "prospector_core") {
            this.path([[cx - 5, y - 6], [cx - 1, y - 1], [cx - 4, y + 1], [cx + 3, y + 7]], c, .95, 2);
          }
        }
      } else if (SCOPE_EVENTS.has(this.eventKind)) {
        const cx = g.rightCenter;
        for (let index = 0; index < 3; index += 1) {
          const local = clamp(elapsed * 1.3 - index * .16);
          const radius = 4 + local * 28;
          this.arc(cx, y, radius, radius * .38, 0, TAU, c, (1 - local) * .85, index === 0 ? 2 : 1);
        }
        const sweep = g.rightStart + 8 + (g.right - g.rightStart - 16) * ease;
        this.line(sweep, y - 9, sweep, y + 9, c, .75 * (1 - elapsed), 2);
      } else if (ROUTE_EVENTS.has(this.eventKind)) {
        const x1 = g.rightStart + 7, x2 = g.right - 7;
        const route = [[x1, y + 4], [x1 + (x2 - x1) * .32, y - 5], [x1 + (x2 - x1) * .65, y + 3], [x2, y - 3]];
        this.path(route, c, .45);
        const segment = ease * (route.length - 1);
        const index = Math.min(route.length - 2, Math.floor(segment));
        const local = segment - index;
        const px = route[index][0] + (route[index + 1][0] - route[index][0]) * local;
        const py = route[index][1] + (route[index + 1][1] - route[index][1]) * local;
        this.shipGlyph(px, py, c, 1 - elapsed * .35, .55);
        route.forEach(([x, pointY]) => this.dot(x, pointY, 1, c, .38));
      } else if (DOCKING_EVENTS.has(this.eventKind)) {
        const cx = g.rightCenter;
        const outward = this.eventKind === "undock";
        const travel = outward ? ease : 1 - ease;
        const spread = 7 + travel * 29;
        for (const side of [-1, 1]) {
          const bx = cx + side * spread;
          this.line(bx, y - 10, bx, y + 10, c, .9, 2);
          this.line(bx, y - 10, bx - side * 7, y - 10, c, .55);
          this.line(bx, y + 10, bx - side * 7, y + 10, c, .55);
        }
        this.shipGlyph(cx, y, c, .82, .62);
      } else {
        // A journal pulse is handed from the identity bay to the response bay
        // instead of being duplicated on both sides at the same instant.
        if (elapsed < .46) {
          const local = clamp(ease / .46);
          const x = g.left + 6 + (g.leftEnd - g.left - 10) * local;
          this.line(Math.max(g.left + 4, x - 11 - local * 6), y, x, y, c, .95, 2);
          this.dot(x, y, 1.4 + local * .5, c, .95);
        } else if (elapsed < .56) {
          const local = Math.sin(((elapsed - .46) / .10) * Math.PI);
          this.line(g.leftEnd, y - 3 - local * 5, g.leftEnd, y + 3 + local * 5, c, .85, 2);
          this.line(g.rightStart, y - 3 - local * 5, g.rightStart, y + 3 + local * 5, c, .85, 2);
        } else {
          const local = clamp((ease - .56) / .44);
          const x = g.rightStart + 5 + (g.right - g.rightStart - 11) * local;
          this.line(Math.max(g.rightStart + 4, x - 12 - local * 8), y, x, y, c, 1 - elapsed, 2);
          this.dot(x, y, 1.8 - local * .4, c, 1 - elapsed);
        }
      }
    }

    draw(now) {
      this.resize();
      const ctx = this.ctx, ratio = this.ratio || 1;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.clearRect(0, 0, this.canvas.clientWidth, this.canvas.clientHeight);
      const g = this.geometry();
      const currentPhase = this.reduced ? .18 : this.phase(this.state, now);
      const currentCue = this.choreography(this.state, now);
      if (!this.reduced && this.previous && this.transitionStarted) {
        const transition = clamp((now - this.transitionStarted) / this.transitionDuration);
        const previousPhase = this.phase(this.previous, now);
        const previousCue = this.choreography(this.previous, now);
        const fadeOut = smoothstep(transition / .78);
        const fadeIn = smoothstep((transition - .12) / .78);
        this.withAlpha(1 - smoothstep(transition), () => this.chassis(g, this.previous.color));
        this.withAlpha(smoothstep(transition), () => this.chassis(g, this.state.color));
        this.drawLayer(g, this.previous, previousPhase, 1 - fadeOut, previousCue);
        this.drawLayer(g, this.state, currentPhase, fadeIn, currentCue);
        this.drawTransitionBridge(g, this.previous, this.state, transition);
        if (transition >= 1) this.previous = null;
      } else {
        this.chassis(g, this.state.color);
        this.drawLayer(g, this.state, currentPhase, 1, currentCue);
      }
      if (!this.reduced) this.eventResponse(g, now);
    }

    frame(now) {
      if (!this.running) return;
      if (now - this.lastFrame >= (this.reduced ? 180 : 32)) {
        this.lastFrame = now; this.draw(now);
      }
      requestAnimationFrame((time) => this.frame(time));
    }
  }

  window.NavigationIndicator = NavigationIndicator;
})();
