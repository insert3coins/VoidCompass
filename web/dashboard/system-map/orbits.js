const LS_MM=299.792458, AU_LS=499.004783836, DEG=Math.PI/180;
// ------------------------------------------------------------ orbit math
export function solveKepler(M, e) {
  let E = e < 0.8 ? M : Math.PI;
  for (let k = 0; k < 30; k++) { const d = (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E)); E -= d; if (Math.abs(d) < 1e-13) break; }
  return E;
}
// position relative to parent, Mm, world frame
// Orbit convention, validated against in-game nav-panel distances (30 bodies, 2026-10-02, rms 0.5 ls):
//  - every body uses (-ascendingNode, -argOfPeriapsis) (planet longitudes checked against the in-game orrery);
//  - a body not orbiting body 0 is expressed in the frame of its parent:
//    a barycentre's perifocal frame, or a planet's perifocal frame tilted by its axial tilt (moons orbit the equator).
// Handedness (v0.49.3): the game's sky is the mirror image of the frame above. Seen from moon 9 a (10 Oct 2026), the star,
// planet 3 and moon 9 b sit on the opposite side of planet 9's rings than in the plain frame. Mirroring everything
// through the orbital plane (z -> -z) fixes this. A mirror keeps every distance, angle and eclipse time unchanged,
// so all earlier checks still hold. MZ gives a frame in mirrored coordinates: Mz F Mz.
const MZ = F => [[F[0][0], F[0][1], -F[0][2]], [F[1][0], F[1][1], -F[1][2]], [-F[2][0], -F[2][1], F[2][2]]];
const M3 = (A, B2) => A.map((r, i) => [0, 1, 2].map(j => r[0] * B2[0][j] + r[1] * B2[1][j] + r[2] * B2[2][j]));
const RZ = a => [[Math.cos(a), -Math.sin(a), 0], [Math.sin(a), Math.cos(a), 0], [0, 0, 1]];
const RX = a => [[1, 0, 0], [0, Math.cos(a), -Math.sin(a)], [0, Math.sin(a), Math.cos(a)]];
export function orbitFrames(byId, parentOf) {
  const done = new Set();
  const f = id => {
    const b = byId.get(id); if (!b || done.has(id)) return b ? b._Fraw : null; done.add(id);
    const p = parentOf.get(id), nested = p !== undefined && p !== 0;
    b._nested = nested; const pRaw = nested ? f(p) : null; b._pF = pRaw ? MZ(pRaw) : null;
    const sg = -1, i = (b.orbitalInclination || 0) * DEG, w = sg * (b.argOfPeriapsis || 0) * DEG, Om = sg * (b.ascendingNode || 0) * DEG;
    let F = M3(M3(RZ(Om), RX(i)), RZ(w));
    if (pRaw) F = M3(pRaw, F);
    // axial tilt sign, found by in-game tests (v0.38, v0.44): a body orbiting a barycentre that is not itself inside
    // another barycentre tilts one way (moon 2 a and moon 9 a eclipses), any other body the other way (rings of
    // planets 7 and 8, and planet 3 seen from moon 3 a, whose barycentre sits inside another barycentre)
    const pb = p !== undefined ? byId.get(p) : null, ppb = pb ? byId.get(parentOf.get(p)) : null;
    const ts = pb && pb.type === "Barycentre" && !(ppb && ppb.type === "Barycentre") ? 1 : -1;
    if (b.type !== "Barycentre") F = M3(F, RX(ts * (b.axialTilt || 0)));
    if (id === 0 || p === undefined) F = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    b._Fraw = F; b._F = MZ(F); return F;
  };
  for (const id of byId.keys()) f(id);
}
export function relPos(b, tMs, mOverride) {
  const a = (b.semiMajorAxis || 0) * AU_LS * LS_MM, e = Math.min(b.orbitalEccentricity || 0, 0.99), sg = -1;
  const i = (b.orbitalInclination || 0) * DEG, w = sg * (b.argOfPeriapsis || 0) * DEG, Om = sg * (b.ascendingNode || 0) * DEG;
  let M = mOverride;
  if (M === undefined) {
    const P = (b.orbitalPeriod || 1e9) * 86400000;
    M = (((b.meanAnomaly || 0) * DEG + 2 * Math.PI * (tMs - b._t0) / P) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);
  }
  const E = solveKepler(M, e);
  const nu = 2 * Math.atan2(Math.sqrt(1 + e) * Math.sin(E / 2), Math.sqrt(1 - e) * Math.cos(E / 2));
  const r = a * (1 - e * Math.cos(E)), u = w + nu;
  const x = r * (Math.cos(Om) * Math.cos(u) - Math.sin(Om) * Math.sin(u) * Math.cos(i)),
        y = r * (Math.sin(Om) * Math.cos(u) + Math.cos(Om) * Math.sin(u) * Math.cos(i)),
        z = -r * Math.sin(u) * Math.sin(i), F = b._pF;            // mirrored, see MZ
  return F ? { x: F[0][0] * x + F[0][1] * y + F[0][2] * z, y: F[1][0] * x + F[1][1] * y + F[1][2] * z, z: F[2][0] * x + F[2][1] * y + F[2][2] * z } : { x, y, z };
}
