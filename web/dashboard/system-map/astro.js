// Positions here are in the orbit frame (orbits.js), in megametres; the scene converts for display.
import {relPos} from "./orbits.js";

const DEG = Math.PI / 180, LS_MM = 299.792458, DAY_MS = 86400000;
const n3 = (v) => { const l = Math.hypot(v[0], v[1], v[2]) || 1; return [v[0] / l, v[1] / l, v[2] / l]; };
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const gap = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
// Share of a star's disc an occluder covers (angular radii aS, aO; separation sep).
export function discCover(aS, aO, sep) {
  if (sep >= aS + aO) return 0;
  if (sep <= Math.abs(aS - aO)) return Math.min(1, aO * aO / (aS * aS));
  const s = aS * aS, o = aO * aO, d = sep * sep;
  return (s * Math.acos(Math.max(-1, Math.min(1, (d + s - o) / (2 * sep * aS))))
    + o * Math.acos(Math.max(-1, Math.min(1, (d + o - s) / (2 * sep * aO))))
    - .5 * Math.sqrt(Math.max(0, (-sep + aS + aO) * (sep + aS - aO) * (sep - aS + aO) * (sep + aS + aO)))) / (Math.PI * s);
}
export const radiusMm = (b) => b.type === "Star" ? (b.solarRadius > 0 ? b.solarRadius * 695.7 : 0) : (b.radius > 0 ? b.radius / 1000 : 0);
// A rough supercruise time for a distance in light seconds: a power law through typical
// in-game times (100 ls about a minute, 10,000 ls about six). No slowdowns, no gravity wells.
export const cruiseSeconds = (ls) => ls > 0 ? 8.8 * Math.pow(ls, .41) : 0;

export class SystemModel {
  constructor(byId, parentOf) {
    this.byId = byId; this.parentOf = parentOf;
    this.bodies = [...byId.values()].filter((b) => b.type !== "Barycentre");
    this.stars = this.bodies.filter((b) => b.type === "Star");
    this.main = this.bodies.find((b) => b.mainStar) || this.bodies.find((b) => b.type === "Star" && !(b.distanceToArrival > 0))
      || byId.get(0) || this.stars[0] || null;
  }
  // Where every body with a measured orbit is at time t (approximate placements excluded).
  worldAt(t, only = null) {
    const W = new Map(), visiting = new Set();
    const get = (id) => {
      if (W.has(id)) return W.get(id);
      const b = this.byId.get(id); if (!b || visiting.has(id)) return null; visiting.add(id);
      let w = null; const parent = this.parentOf.get(id);
      if (id === 0 || (parent === undefined && b.bodyId === 0)) w = {x: 0, y: 0, z: 0};
      else if (b._resolved && parent !== undefined) { const p = get(parent); if (p) { const r = relPos(b, t); w = {x: p.x + r.x, y: p.y + r.y, z: p.z + r.z}; } }
      visiting.delete(id); W.set(id, w); return w;
    };
    for (const id of only || this.byId.keys()) get(id);
    return W;
  }
  starOf(b, W) {
    const pb = W.get(b.bodyId); if (!pb) return null; let best = null, bd = Infinity;
    for (const s of this.stars) { const p = W.get(s.bodyId); if (!p || !(radiusMm(s) > 0)) continue; const d = gap(p, pb); if (d < bd) { bd = d; best = s; } }
    return best;
  }
  // Starlight reaching a body: the share of the star's disc not covered, and by whom.
  light(b, star, W) {
    const pb = W.get(b.bodyId), ps = W.get(star.bodyId); if (!pb || !ps) return null;
    const L = {x: ps.x - pb.x, y: ps.y - pb.y, z: ps.z - pb.z}, dL = Math.hypot(L.x, L.y, L.z), aS = Math.asin(Math.min(radiusMm(star) / dL, 1));
    let vis = 1, by = null, best = 0, bSep = 0, bAO = 0;
    for (const o of this.bodies) {
      if (o === b || o === star || !(radiusMm(o) > 0)) continue;
      const po = W.get(o.bodyId); if (!po) continue;
      const v = {x: po.x - pb.x, y: po.y - pb.y, z: po.z - pb.z}, dO = Math.hypot(v.x, v.y, v.z), dp = v.x * L.x + v.y * L.y + v.z * L.z;
      if (dO >= dL || dp <= 0) continue;
      const aO = Math.asin(Math.min(radiusMm(o) / dO, 1));
      const sep = Math.atan2(Math.hypot(v.y * L.z - v.z * L.y, v.z * L.x - v.x * L.z, v.x * L.y - v.y * L.x), dp);
      const c = discCover(aS, aO, sep);
      if (c > best) { best = c; by = o; bSep = sep; bAO = aO; }
      vis *= 1 - c;
    }
    return {vis, by, aS, aO: bAO, sep: bSep};
  }
  // The eclipses coming up, seen from a body: sampled, then cut into events at their deepest.
  eclipses(bodyId, t0) {
    const b = this.byId.get(bodyId); if (!b || b.type === "Star" || !b._resolved) return {reason: "orbit"};
    const W0 = this.worldAt(t0), star = this.starOf(b, W0); if (!star) return {reason: "star"};
    const P = b.orbitalPeriod || 1, span = Math.min(Math.max(P * 2, 2), 45), N = Math.round(Math.min(1500, Math.max(400, span * 24 * 3)));
    const events = []; let start = -1, deepest = null;
    for (let i = 0; i < N; i++) {
      const t = t0 + i / (N - 1) * span * DAY_MS, w = this.light(b, star, this.worldAt(t)); if (!w) continue;
      const shaded = w.vis < .995;
      if (shaded && start < 0) { start = t; deepest = {...w, t}; }
      if (shaded && w.vis < deepest.vis) deepest = {...w, t};
      if (start >= 0 && (!shaded || i === N - 1)) { events.push({...deepest, start, end: t, hours: (t - start) / 3600000}); start = -1; }
    }
    return {star, span, events: events.slice(0, 6)};
  }
  distanceLs(aId, bId, t) {
    const W = this.worldAt(t), a = W.get(aId), b = W.get(bId);
    return a && b ? gap(a, b) / LS_MM : null;
  }
  // Which body was at the reported distance from the arrival star when the station was reported.
  placeByDistance(distanceLs, at) {
    if (!(distanceLs > 0) || !at || !this.main) return null;
    const W = this.worldAt(at), m = W.get(this.main.bodyId); if (!m) return null;
    const ranked = this.bodies.filter((o) => o !== this.main && W.get(o.bodyId))
      .map((o) => ({o, e: Math.abs(gap(W.get(o.bodyId), m) / LS_MM - distanceLs)})).sort((x, y) => x.e - y.e);
    if (!ranked.length || ranked[0].e > Math.max(2, distanceLs * .002)) return null;
    return {body: ranked[0].o, alt: ranked[1] && ranked[1].e - ranked[0].e < 1 ? ranked[1].o : null};
  }
  // Day and night at a spot on a tidally locked body. Free-spinning bodies have no rotation phase in
  // the data, so they get no times. Longitude: 0° faces the parent, east by the right-hand rule
  // (an assumption, not yet checked in the game).
  locked(b) { return Boolean(b && b.type !== "Star" && b.rotationalPeriodTidallyLocked && b._resolved && b._F && this.parentOf.get(b.bodyId) !== undefined); }
  up(b, lat, lon, W) {
    const F = b._F, P = n3([F[0][2], F[1][2], F[2][2]]), pb = W.get(b.bodyId), pp = W.get(this.parentOf.get(b.bodyId));
    if (!pb || !pp) return null;
    let e1 = [pp.x - pb.x, pp.y - pb.y, pp.z - pb.z]; const k = dot(e1, P); e1 = n3([e1[0] - k * P[0], e1[1] - k * P[1], e1[2] - k * P[2]]);
    const e2 = cross(P, e1), la = lat * DEG, lo = lon * DEG;
    return [0, 1, 2].map((i) => Math.cos(la) * (Math.cos(lo) * e1[i] + Math.sin(lo) * e2[i]) + Math.sin(la) * P[i]);
  }
  sunAt(b, lat, lon, t) {
    const W = this.worldAt(t, [b.bodyId, this.parentOf.get(b.bodyId), ...this.stars.map((s) => s.bodyId)]), star = this.starOf(b, W), up = this.up(b, lat, lon, W); if (!star || !up) return null;
    const pb = W.get(b.bodyId), ps = W.get(star.bodyId), d = n3([ps.x - pb.x, ps.y - pb.y, ps.z - pb.z]);
    const half = Math.asin(Math.min(1, radiusMm(star) / gap(ps, pb))) / DEG, alt = Math.asin(Math.max(-1, Math.min(1, dot(up, d)))) / DEG;
    return {alt, half, up: alt > -half, star};
  }
  dayLength(b) {
    const parent = this.byId.get(this.parentOf.get(b.bodyId)), P1 = Math.abs(b.orbitalPeriod || b.rotationalPeriod || 0);
    let P2 = 0;
    for (let p = parent; p; p = this.byId.get(this.parentOf.get(p.bodyId))) { if (p.type === "Star") break; if (p.orbitalPeriod > P1 * 1.01) { P2 = p.orbitalPeriod; break; } }
    if (!P1) return 0;
    return !P2 || parent?.type === "Star" ? P1 : 1 / Math.abs(1 / P1 - 1 / P2);
  }
  nextHorizon(b, lat, lon, t0, span, rising) {
    const N = 480, step = span / N; let prev = this.sunAt(b, lat, lon, t0); if (!prev) return null;
    for (let i = 1; i <= N; i++) {
      const t = t0 + i * step, cur = this.sunAt(b, lat, lon, t); if (!cur) return null;
      const a = prev.alt + prev.half, c = cur.alt + cur.half;
      if (rising ? a <= 0 && c > 0 : a > 0 && c <= 0) {
        let lo = t - step, hi = t;
        for (let k = 0; k < 22; k++) { const m = (lo + hi) / 2, s = this.sunAt(b, lat, lon, m), v = s.alt + s.half; if ((v > 0) === rising) hi = m; else lo = m; }
        return hi;
      }
      prev = cur;
    }
    return null;
  }
  dayNight(bodyId, lat, lon, t0) {
    const b = this.byId.get(bodyId);
    if (!this.locked(b)) return {reason: "spin"};
    const now = this.sunAt(b, lat, lon, t0); if (!now) return {reason: "orbit"};
    const toStar = this.byId.get(this.parentOf.get(bodyId))?.type === "Star", day = this.dayLength(b), span = toStar ? 0 : day * DAY_MS * 1.05;
    return {now, day, toStar, rise: span ? this.nextHorizon(b, lat, lon, t0, span, true) : null,
      set: span ? this.nextHorizon(b, lat, lon, t0, span, false) : null};
  }
}
