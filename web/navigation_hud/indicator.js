(() => {
  "use strict";

  const TAU = Math.PI * 2;
  const clamp = (value, low = 0, high = 1) => Math.max(low, Math.min(high, value));
  const wave = (progress) => .5 - .5 * Math.cos(progress * TAU);

  class NavigationIndicator {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d", {alpha: true, desynchronized: true});
      this.state = {motion: "flight", label: "FLIGHT", color: "#607584", energy: 1};
      this.receivedModel = false;
      this.previous = null;
      this.stateStarted = performance.now();
      this.transitionStarted = 0;
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
      };
      if (!this.receivedModel) {
        this.state = incoming;
        this.stateStarted = now;
        this.receivedModel = true;
      } else if (incoming.motion !== this.state.motion || incoming.label !== this.state.label) {
        this.previous = {...this.state, phaseAtChange: this.phase(this.state, now)};
        this.state = incoming;
        this.stateStarted = now;
        this.transitionStarted = now;
      } else {
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

    period(motion) {
      return ({
        supercruise_overcharge: .55, fsd_charge: .78, jump: .62,
        arrival: 1.18, carrier_transit: 1.1, carrier_arrival: 1.25,
        scanner: 1.65, map: 1.9, asteroid_field: 2.2,
        surface_vehicle: 1.3, on_foot: 1.45, combat: .92,
        planetary: 1.35,
      })[motion] || 1.65;
    }

    phase(state, now) {
      const elapsed = Math.max(0, now - this.stateStarted) / 1000;
      return (elapsed * (state.energy || 1) / this.period(state.motion)) % 1;
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

    drawFlight(g, state, p, alpha, fighter = false) {
      const c = state.color, y = g.y, cx = g.leftCenter;
      this.withAlpha(alpha, () => {
        const scale = 1 + wave(p) * (fighter ? .12 : .05);
        this.polygon([
          [cx + 9 * scale, y], [cx - 7 * scale, y - (fighter ? 7 : 5)],
          [cx - 2 * scale, y], [cx - 7 * scale, y + (fighter ? 7 : 5)],
        ], c, .9);
        const angle = (fighter ? p * TAU : Math.sin(p * TAU) * .5);
        this.arc(cx, y, 15, 10, angle, angle + Math.PI * 1.25, c, .35);
        this.dot(cx + Math.cos(p * TAU) * 15, y + Math.sin(p * TAU) * 9, 1.4, c, .9);
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
          this.path([[vx - 5, y - 4], [vx, y], [vx - 5, y + 4]], c, .9, 2);
        }
      });
    }

    drawSupercruise(g, state, p, alpha, overcharge = false) {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const [wingIndex, [x1, x2]] of this.wings(g).entries()) {
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
          this.path(jag, c, .9, 2);
          this.path(jag.map(([x, py]) => [g.width - x, 2 * y - py]), c, .9, 2);
        }
      });
    }

    drawTaxi(g, state, p, alpha) {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const [wingIndex, [x1, x2]] of this.wings(g).entries()) {
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
        for (const [x1, x2] of this.wings(g)) {
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
      this.withAlpha(alpha, () => {
        if (variant === "charge") {
          for (const [x1, x2, reverse] of [[g.left + 6, g.leftEnd - 6, false], [g.rightStart + 6, g.right - 6, true]]) {
            const span = x2 - x1;
            for (let index = 0; index < 6; index += 1) {
              const local = (p + index / 6) % 1;
              const x = reverse ? x2 - span * local : x1 + span * local;
              const lane = [-7, 0, 7][index % 3];
              this.line(x - (reverse ? -11 : 11), y + lane, x, y + lane, c, .65, local > .75 ? 2 : 1);
              this.dot(x, y + lane, 1.2, c, .9);
            }
          }
          const squeeze = 4 + wave(p) * 9;
          this.line(g.leftEnd - squeeze, y - 10, g.leftEnd - squeeze, y + 10, c, .9, 2);
          this.line(g.rightStart + squeeze, y - 10, g.rightStart + squeeze, y + 10, c, .9, 2);
        } else if (variant === "jump") {
          for (const [wingIndex, [x1, x2]] of this.wings(g).entries()) {
            const span = x2 - x1;
            for (let index = 0; index < 9; index += 1) {
              const local = (p + index / 9 + wingIndex * .13) % 1;
              const x = x1 + span * local, lane = [-10, -5, 0, 5, 10][index % 5];
              this.line(Math.max(x1, x - 8 - local * 25), y + lane, x, y + lane, c, .4 + local * .55, local > .7 ? 2 : 1);
            }
          }
          const aperture = 2 + wave(p) * 11;
          this.line(g.leftEnd - aperture, g.top + 1, g.leftEnd - aperture, g.bottom, c, .9, 2);
          this.line(g.rightStart + aperture, g.top + 1, g.rightStart + aperture, g.bottom, c, .9, 2);
        } else if (variant === "arrival") {
          for (const [side, start, end] of [[-1, g.leftEnd - 4, g.left + 5], [1, g.rightStart + 4, g.right - 5]]) {
            const x = start + (end - start) * p;
            this.arc(x, y, 5 + p * 8, 5 + p * 5, 0, TAU, c, 1 - p, 2);
            this.line(start, y, x, y, c, .55, 2);
          }
        } else {
          for (const cx of [g.leftCenter, g.rightCenter]) {
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
      this.withAlpha(alpha, () => {
        for (const [wingIndex, [x1, x2]] of this.wings(g).entries()) {
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
              this.arc(cx, y, radius, radius * .48, 0, TAU, c, 1 - local, local > .65 ? 2 : 1);
            }
            const beam = x1 + span * wave(p);
            this.line(beam, y - 11, beam, y + 11, c, .75, 2);
            this.dot(cx, y, 2, c, .95);
          } else {
            const sweep = x1 + span * p;
            this.line(sweep, y - 11, sweep, y + 11, c, .9, 2);
            const contacts = [.12, .31, .54, .78, .91];
            contacts.forEach((amount, index) => {
              const delta = Math.abs(amount - p), py = y + [-7, 4, -2, 8, -5][index];
              this.dot(x1 + span * amount, py, delta < .08 ? 2 : 1, c, delta < .08 ? 1 : .35);
            });
            this.arc((x1 + x2) / 2, y, span * .23, 11, p * TAU, p * TAU + 1.1, c, .65);
          }
        }
      });
    }

    drawHold(g, state, p, alpha) {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const [x1, x2] of this.wings(g)) {
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
        for (const cx of [g.leftCenter, g.rightCenter]) {
          if (landed) {
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
      this.withAlpha(alpha, () => {
        for (const [x1, x2] of this.wings(g)) {
          const span = x2 - x1;
          this.line(x1, y + 10, x2, y + 3, c, .3);
          const local = departing ? 1 - p : p;
          const active = Math.min(7, Math.floor(local * 8));
          for (let index = 0; index < 8; index += 1) {
            const x = x1 + span * (index + .5) / 8, distance = Math.abs(index - active);
            const height = 3 + (index % 3) * 2;
            this.line(x, y - height, x, y + height, c, distance === 0 ? 1 : distance === 1 ? .6 : .22, distance === 0 ? 2 : 1);
          }
          if (variant === "glide") {
            const horizon = y + Math.sin(p * TAU) * 2;
            this.line(x1, horizon, x2, horizon, c, .7, 2);
            this.line(x1 + span * .5, y - 11, x1 + span * .5, y + 11, c, .5);
          }
        }
      });
    }

    drawVehicle(g, state, p, alpha, foot = false) {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const [wingIndex, [x1, x2]] of this.wings(g).entries()) {
          const span = x2 - x1;
          if (foot) {
            for (let index = 0; index < 7; index += 1) {
              const local = (p + index / 7) % 1, x = x1 + span * local;
              const py = y + (index % 2 ? -4 : 4);
              this.arc(x, py, 3, 1.5, 0, TAU, c, index < 2 ? .9 : .28, 1);
            }
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
      this.withAlpha(alpha, () => {
        for (const [x1, x2] of this.wings(g)) {
          const amount = reverse ? 1 - wave(p) : wave(p);
          const x = x1 + (x2 - x1) * amount;
          this.line(x1, y + 7, x2, y + 7, c, .28);
          this.polygon([[x - 6, y - 4], [x + 6, y - 4], [x + 6, y + 3], [x - 6, y + 3]], c, .9);
          this.dot(x - 4, y + 5, 1.4, c, .8); this.dot(x + 4, y + 5, 1.4, c, .8);
          if (variant === "vehicle_switch") {
            const other = x1 + (x2 - x1) * (1 - amount);
            this.polygon([[other, y - 6], [other + 5, y], [other, y + 6], [other - 5, y]], c, .6);
          }
        }
      });
    }

    drawHazard(g, state, p, alpha, variant = "mass") {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const [wingIndex, [x1, x2]] of this.wings(g).entries()) {
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
          } else if (variant === "signal") {
            const target = x1 + span * .76, samples = [];
            for (let index = 0; index <= 14; index += 1) {
              const amount = index / 14, x = x1 + span * amount;
              const envelope = 1 - Math.abs(amount - .72);
              samples.push([x, y + Math.sin(index * 1.7 + p * TAU) * 6 * envelope]);
            }
            this.path(samples, c, .7, 1);
            const size = 5 + wave(p) * 3;
            this.polygon([[target, y - size], [target + size, y], [target, y + size], [target - size, y]], c, .95, false, 2);
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
        for (const [x1, x2] of this.wings(g)) {
          const span = x2 - x1;
          for (const lane of [-7, 0, 7]) this.line(x1, y + lane, x2, y + lane, c, .2);
          for (let index = 0; index < 6; index += 1) {
            const local = (p + index / 6) % 1;
            const amount = arrival ? 1 - local : local;
            const x = x1 + span * amount, lane = [-7, 0, 7][index % 3];
            this.line(Math.max(x1, x - 19), y + lane, x, y + lane, c, .7, 2);
          }
          const fold = x1 + span * (arrival ? 1 - p : p);
          this.polygon([[fold, y - 11], [fold + 6, y], [fold, y + 11], [fold - 6, y]], c, .85, false, 2);
        }
      });
    }

    drawExploration(g, state, p, alpha) {
      const c = state.color, y = g.y;
      this.withAlpha(alpha, () => {
        for (const [x1, x2] of this.wings(g)) {
          const span = x2 - x1, sweep = x1 + span * p;
          this.line(sweep, y - 10, sweep, y + 10, c, .85, 2);
          [.16, .39, .63, .84].forEach((amount, index) => {
            const x = x1 + span * amount, py = y + [-6, 4, -2, 7][index];
            const active = Math.abs(amount - p) < .09;
            this.dot(x, py, active ? 2 : 1, c, active ? 1 : .3);
            if (active) this.arc(x, py, 5 + wave(p) * 4, 5 + wave(p) * 4, 0, TAU, c, .55);
          });
        }
      });
    }

    drawScene(g, state, phase, alpha) {
      const motion = state.motion;
      if (motion === "supercruise") {
        return state.label === "TAXI"
          ? this.drawTaxi(g, state, phase, alpha)
          : this.drawSupercruise(g, state, phase, alpha);
      }
      if (motion === "supercruise_overcharge") return this.drawSupercruise(g, state, phase, alpha, true);
      if (motion === "fsd_charge") return this.drawFsd(g, state, phase, alpha, "charge");
      if (motion === "jump") return this.drawFsd(g, state, phase, alpha, "jump");
      if (motion === "arrival" || motion === "carrier_arrival") {
        return motion === "carrier_arrival"
          ? this.drawCarrier(g, state, phase, alpha, true)
          : this.drawFsd(g, state, phase, alpha, "arrival");
      }
      if (motion === "fsd_cooldown") return this.drawFsd(g, state, phase, alpha, "cooldown");
      if (motion === "scanner") return this.drawScanner(g, state, phase, alpha);
      if (motion === "map") return this.drawScanner(g, state, phase, alpha, true);
      if (["orbital_approach", "glide", "surface_approach", "surface_hold", "surface_departure", "orbital_departure"].includes(motion)) {
        if (motion === "surface_hold") return this.drawHold(g, state, phase, alpha);
        return this.drawSurface(g, state, phase, alpha, motion);
      }
      if (motion === "docked") return this.drawStation(g, state, phase, alpha);
      if (motion === "landed") return this.drawStation(g, state, phase, alpha, true);
      if (motion === "surface_vehicle") return this.drawVehicle(g, state, phase, alpha);
      if (motion === "on_foot") return this.drawVehicle(g, state, phase, alpha, true);
      if (["vehicle_deploy", "vehicle_board", "vehicle_switch"].includes(motion)) return this.drawHandoff(g, state, phase, alpha, motion);
      if (motion === "fsd_lock") return this.drawHazard(
        g, state, phase, alpha, state.label === "MASS LOCK" ? "mass" : "signal",
      );
      if (motion === "combat") return this.drawHazard(g, state, phase, alpha, "combat");
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
        this.line(g.rightStart + 5, y + shear, g.right - 8, y - shear, c, .75, 2);
      } else {
        const leftX = g.left + (g.leftEnd - g.left) * ease;
        const rightX = g.rightStart + (g.right - g.rightStart) * ease;
        this.line(Math.max(g.left, leftX - 13), y, leftX, y, c, 1 - elapsed, 2);
        this.line(Math.max(g.rightStart, rightX - 13), y, rightX, y, c, 1 - elapsed, 2);
        this.dot(leftX, y, 1.6, c, 1 - elapsed);
        this.dot(rightX, y, 1.6, c, 1 - elapsed);
      }
    }

    draw(now) {
      this.resize();
      const ctx = this.ctx, ratio = this.ratio || 1;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.clearRect(0, 0, this.canvas.clientWidth, this.canvas.clientHeight);
      const g = this.geometry();
      this.chassis(g, this.state.color);
      const currentPhase = this.reduced ? .18 : this.phase(this.state, now);
      if (!this.reduced && this.previous && this.transitionStarted) {
        const transition = clamp((now - this.transitionStarted) / 520);
        const previousPhase = (this.previous.phaseAtChange + (now - this.transitionStarted) / 1700) % 1;
        this.drawScene(g, this.previous, previousPhase, 1 - transition);
        this.drawScene(g, this.state, currentPhase, transition);
        if (transition >= 1) this.previous = null;
      } else {
        this.drawScene(g, this.state, currentPhase, 1);
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
