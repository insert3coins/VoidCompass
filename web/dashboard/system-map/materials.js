import * as THREE from "/galactic_map/vendor/three.module.min.js";
const MAX_STARS=4, MAX_OCC=12, LIN={value:1};
function atmColor(b) {
  const a = (b.atmosphereType || "") + " " + Object.keys(b.atmosphereComposition || {}).sort((x, y) => b.atmosphereComposition[y] - b.atmosphereComposition[x])[0];
  const c = /Sulphur/i.test(a) ? 0xffe36a : /Carbon dioxide/i.test(a) ? 0xffc38a : /Argon/i.test(a) ? 0xb9a2ff : /Nitrogen/i.test(a) ? 0x7fb2ff
    : /Methane/i.test(a) ? 0x7fe8ff : /Ammonia/i.test(a) ? 0xe8d27a : /Water/i.test(a) ? 0xcfe8ff : /Neon/i.test(a) ? 0xff8a9a
    : /Helium/i.test(a) ? 0xf0e8ff : /Oxygen/i.test(a) ? 0xa8d0ff : /Silicate/i.test(a) ? 0xffa060 : /Metallic/i.test(a) ? 0xb0c8d0 : 0x8fc8ff;
  const strength = /Thick|Hot thick/i.test(a) ? 1.0 : /Thin/i.test(a) ? 0.6 : 0.8;
  return [new THREE.Color(c), strength];
}
const PRESETS={low:{},medium:{}}; let QUALITY=PRESETS.medium;
// ------------------------------------------------------------ appearance
// the star's class letter. v0.77.1: a T Tauri star (class TTS) is a young sun-like star, not a T brown dwarf
function starLetter(b) { return /T Tauri/i.test(b.subType || "") || /^TTS/i.test(b.spectralClass || "") ? "K" : (b.spectralClass || b.subType || "M")[0].toUpperCase(); }
function starColor(b) {
  const s = (b.subType || "") + " " + (b.spectralClass || "");
  if (/Black Hole/i.test(s)) return 0x301048;
  if (/Neutron/i.test(s)) return 0xaff4ff;
  if (/White Dwarf/i.test(s)) return 0xdcefff;
  if (/Wolf-Rayet/i.test(s)) return 0xa4bcff;
  const c = starLetter(b);
  return { O: 0x9bbcff, B: 0xaac8ff, A: 0xe4ecff, F: 0xfff6e8, G: 0xfff1c8, K: 0xffcf92, M: 0xffa070, L: 0xe06040, T: 0xb04060, Y: 0x803050, C: 0xff6a40, S: 0xff9060 }[c] || 0xffd0a0;
}
const isGiant = b => /gas giant|Water giant|Helium/i.test(b.subType || "");
const hasAtm = b => b.type === "Planet" && !isGiant(b) && ((b.atmosphereType && !/^No atmosphere$/i.test(b.atmosphereType)) || (b.atmosphereComposition && Object.keys(b.atmosphereComposition).length));
// ---------------------------------------------- procedural surface textures
// v0.60: surfaces are baked on the graphics card. Spansh has no surface maps, so every pattern is generated from the
// body's own data and its id (the same body always looks the same). What is set by data and what is illustrative:
//  · gas giants: the game's 7-layer cloud model (EDGGG explainer, verified on 39 of 39 green gas giants). Each layer
//    gets the colour of its class and temperature band, so the mix of colours follows the data. Swirls are illustrative.
//  · rings: colour from the ring type (verified on in-game screenshots). Fine structure is illustrative.
//  · solid bodies: base colour from type, composition and temperature. Craters, patches and cracks are illustrative.
// Textures are equirectangular (same layout as THREE.SphereGeometry), albedo + object-space normal map, baked in strips
// over several frames, at a resolution that follows the body's size on screen, capped by the quality setting.
const PAL = [                                   // flat colours for the system map, charts and before a bake is ready
  [/Class I gas/i, [[196, 172, 140], [226, 210, 182], [120, 110, 170], [238, 224, 200]]],
  [/Class II gas/i, [[226, 226, 228], [206, 204, 200], [240, 238, 234], [190, 188, 184]]],
  [/Class III gas/i, [[64, 84, 160], [92, 112, 182], [44, 60, 130], [120, 140, 196]]],
  [/Class IV gas/i, [[112, 56, 52], [138, 72, 60], [90, 42, 44], [130, 120, 120]]],
  [/Class V gas/i, [[128, 116, 94], [182, 170, 144], [92, 82, 66], [200, 190, 166]]],
  [/water-based life/i, [[206, 186, 156], [166, 136, 102], [140, 110, 80], [226, 212, 186]]],
  [/ammonia-based life/i, [[194, 166, 122], [196, 126, 58], [142, 62, 44], [222, 204, 168]]],
  [/Water giant/i, [[82, 132, 176], [110, 152, 190], [60, 100, 150], [150, 186, 210]]],
  [/Helium/i, [[216, 210, 226], [196, 190, 214], [232, 228, 242], [180, 174, 200]]],
  [/gas giant/i, [[200, 176, 140], [224, 204, 170], [170, 140, 104], [236, 222, 196]]],
  [/Earth-like/i, [[54, 92, 140], [70, 110, 70], [222, 226, 230], [150, 130, 96]]],
  [/Water world/i, [[60, 92, 140], [90, 120, 160], [220, 226, 232], [40, 70, 120]]],
  [/Ammonia world/i, [[110, 100, 102], [132, 112, 100], [118, 98, 112], [160, 140, 116]]],
  [/Rocky ice/i, [[168, 176, 190], [120, 126, 138], [214, 220, 228], [96, 100, 110]]],
  [/Icy/i, [[222, 222, 220], [200, 200, 198], [240, 240, 238], [170, 172, 176]]],
  [/Metal rich/i, [[106, 100, 96], [78, 74, 70], [138, 130, 122], [60, 56, 54]]],
  [/High metal/i, [[150, 126, 96], [112, 92, 74], [178, 152, 112], [90, 74, 60]]],
  [/Rocky/i, [[150, 140, 128], [112, 104, 96], [176, 164, 146], [84, 78, 72]]],
];
const palette = b => {
  if (isGiant(b)) { const g = giantLook(b); if (g) return g.flat; }
  return (PAL.find(([re]) => re.test(b.subType || "")) || [0, PAL[PAL.length - 1][1]])[1];
};
// ---- the game's gas giant cloud ladder (as published by EDGGG, densitydemo.html; checked against 39 catalogue GGGs)
const GG_CRACK_I = [115, 250, 270, 370, 700, 900, 1400], GG_CRACK_O = [114, 210, 270, 370, 700, 900, 1400];
function giantLadder(b) {
  const st = b.subType || "", f = Math.fround, T = f(b.surfaceTemperature || 0), M = b.earthMasses, R = b.radius;
  if (!T || !M || !R) return null;
  const cls = /Class I gas/i.test(st) ? 1 : /Class II gas/i.test(st) ? 2 : /Class III gas/i.test(st) ? 3 : /Class IV gas/i.test(st) ? 4
    : /Class V gas/i.test(st) ? 5 : /water-based/i.test(st) ? 10 : /ammonia-based/i.test(st) ? 11 : /Water giant/i.test(st) ? 17 : 0;
  const ceil = T < 75 ? 100 : T < 330 ? 340 : T < 680 ? 700 : T < 900 ? 1200 : T < 1400 ? 1500 : 5000;
  const rho = M * 5.97219e24 / (4 / 3 * Math.PI * Math.pow(R * 1e3, 3));
  const top = Math.pow(rho / 1300 * T, 1.2) * (1 / 180) * (130000 / rho) + T;
  let step = (Math.min(ceil, top) - T) / 7;
  const clamp = { 2: [5, 20], 3: [30, 100], 4: [50, 100], 5: [250, 1000] }[cls];
  if (clamp) step = Math.max(clamp[0], Math.min(clamp[1], step));
  const bottom = Math.min(ceil, T), cracks = cls === 1 || cls === 11 ? GG_CRACK_I : GG_CRACK_O;
  const rungs = Array.from({ length: 7 }, (_, k) => f(step * k + bottom));
  return { cls, rungs, band: rungs.map(r => cracks.filter(c => r >= c).length), green: rungs.map(r => cracks.includes(r)) };
}
// Layer colours by class and temperature band (sRGB). Measured from in-game screenshots of 16 Oct 2026
// (Class I to V, water and ammonia life); bands not seen yet are interpolated and marked "guess".
const GG_COL = {
  1: [[[64, 60, 146], [94, 90, 170], [48, 46, 120]],                  // < 115 K: blue-violet (seen: VR-E 7, 8, 9)
      [[200, 184, 160], [168, 148, 124], [222, 212, 192]],             // 115–250 K: beige, tan, cream (seen: VR-E 1, 2, 6, UF-M c8-10 AB 11)
      [[232, 218, 194], [206, 186, 156]],                              // 250–270 K: light cream (seen: VU-M 3)
      [[196, 140, 92], [222, 196, 160]],                               // 270–370 K: guess
      [[160, 92, 66]]],                                                // hotter: guess
  2: [[[214, 220, 230]], [[232, 232, 234], [214, 214, 216]], [[214, 214, 216], [226, 218, 200]], [[214, 206, 192], [196, 192, 186]], [[190, 182, 172]]],
  3: [[[44, 56, 128]], [[44, 56, 128]], [[40, 52, 124], [62, 78, 150]], [[32, 42, 112], [56, 70, 140]], [[38, 50, 120], [66, 82, 152], [26, 34, 96]]],
  4: [[[120, 64, 52]], [[120, 64, 52]], [[120, 64, 52]], [[120, 64, 52]], [[124, 62, 52], [150, 84, 64]], [[112, 58, 50], [134, 80, 64]], [[98, 44, 42], [118, 60, 50], [86, 38, 38], [140, 94, 80]]],     // dark maroon, brown, a little rose-grey (seen: UF-M c8-5 1)
  5: [[[112, 100, 80]], [[112, 100, 80]], [[112, 100, 80]], [[112, 100, 80]], [[112, 100, 80]], [[112, 100, 80]], [[112, 100, 80]], [[112, 100, 80], [164, 152, 128], [80, 70, 56]]],
  10: [[[214, 200, 176]], [[214, 194, 164], [190, 170, 140]], [[170, 140, 104], [206, 186, 156]], [[146, 114, 82], [190, 166, 132]], [[130, 96, 70]]],
  11: [[[150, 144, 150]], [[196, 170, 128], [214, 192, 150], [176, 146, 104]], [[184, 124, 64], [214, 194, 158]], [[150, 92, 50], [176, 112, 58], [212, 192, 158]], [[130, 70, 44]]],
  17: [[[90, 130, 170], [120, 156, 186]], [[90, 130, 170]], [[90, 130, 170]], [[90, 130, 170]], [[90, 130, 170]]],
};
const GG_GREEN = [100, 178, 84];
function giantLook(b) {
  const L = giantLadder(b); if (!L) return null;
  const table = GG_COL[L.cls] || GG_COL[1], h = bodyHash(b);
  const cols = L.rungs.map((r, k) => {
    if (L.green[k]) return GG_GREEN;                         // a layer exactly on a band edge gets no colour: default green
    let set = table[Math.min(L.band[k], table.length - 1)];
    if (L.cls === 1 && L.band[k] === 0 && L.band.some(x => x > 0)) set = [[150, 146, 160], [128, 124, 136]];   // a few cold layers in a beige giant read as grey streaks (AB 11)
    return set[(k + (h >>> (k * 3))) % set.length];
  });
  const flat = [0, 2, 4, 6].map(i => cols[i]);
  return { ...L, cols, flat };
}
// colours measured from in-game screenshots (16 Oct 2026): [darker, lighter] sRGB of the lit disc centre.
// Used as the base colour of these bodies. Which icy bodies are red is not in the data, so only checked bodies get it.
const VERIFIED = {
  "col 285 sector vr-e b27-1 1 a": [[212, 198, 192], [236, 223, 217]],
  "col 285 sector vr-e b27-1 10": [[136, 128, 126], [181, 173, 169]],
  "col 285 sector vr-e b27-1 2 a": [[197, 182, 174], [223, 208, 200]],
  "col 285 sector vr-e b27-1 3 a": [[218, 203, 196], [239, 226, 220]],
  "col 285 sector vr-e b27-1 3 b": [[198, 183, 174], [222, 209, 201]],
  "col 285 sector vr-e b27-1 7 a": [[210, 195, 188], [232, 219, 212]],
  "col 285 sector vr-e b27-1 7 b": [[195, 182, 174], [221, 209, 202]],
  "col 285 sector vr-e b27-1 7 c": [[196, 179, 169], [226, 213, 205]],
  "col 285 sector vr-e b27-1 7 d": [[181, 161, 153], [227, 213, 207]],
  "col 285 sector vr-e b27-1 7 e": [[187, 171, 163], [221, 208, 200]],
  "col 285 sector vr-e b27-1 7 g": [[117, 83, 78], [152, 120, 113]],
  "col 285 sector vr-e b27-1 8 a": [[195, 179, 171], [225, 211, 204]],
  "col 285 sector vr-e b27-1 8 b": [[186, 170, 160], [222, 208, 200]],
  "col 285 sector vr-e b27-1 8 c": [[99, 85, 78], [139, 120, 111]],
  "col 285 sector vr-e b27-1 8 d": [[197, 182, 174], [223, 210, 203]],
  "col 285 sector vr-e b27-1 8 e": [[213, 198, 191], [235, 222, 216]],
  "col 285 sector vr-e b27-1 8 f": [[198, 184, 177], [222, 209, 202]],
  "col 285 sector vr-e b27-1 8 g": [[131, 102, 92], [155, 125, 113]],
  "col 285 sector vr-e b27-1 9 a": [[214, 199, 192], [236, 224, 217]],
  "col 285 sector vr-e b27-1 9 b": [[200, 185, 177], [224, 210, 203]],
  "col 285 sector vr-e b27-1 7 f": [[208, 192, 184], [235, 222, 216]],
  "col 285 sector vu-m c8-1 2 a": [[106, 88, 70], [130, 109, 88]],
  "col 285 sector vu-m c8-1 2 b": [[184, 160, 137], [210, 188, 167]],
  "col 285 sector vu-m c8-1 2 c": [[181, 158, 138], [210, 189, 169]],
  "col 285 sector vu-m c8-1 2 d": [[123, 94, 78], [151, 118, 99]],
  "col 285 sector vu-m c8-1 2 e": [[110, 90, 76], [135, 112, 96]],
  "col 285 sector vu-m c8-1 2 f": [[209, 192, 174], [235, 221, 205]],
  "col 285 sector vu-m c8-1 3 a": [[113, 97, 82], [154, 134, 115]],
  "col 285 sector vu-m c8-1 3 b a": [[228, 210, 190], [246, 233, 219]],
  "col 285 sector vu-m c8-1 3 b": [[157, 142, 122], [206, 190, 172]],
  "col 285 sector vu-m c8-1 3 c": [[137, 102, 88], [173, 135, 117]],
  "col 285 sector vu-m c8-1 3 d a": [[212, 197, 178], [235, 223, 207]],
  "col 285 sector vu-m c8-1 3 d": [[160, 141, 123], [203, 185, 167]],
  "col 285 sector vu-m c8-1 4 a": [[212, 192, 170], [234, 220, 203]],
  "col 285 sector vu-m c8-1 4 b": [[224, 207, 188], [245, 232, 217]],
  "col 285 sector vu-m c8-1 4 c": [[230, 213, 197], [248, 235, 221]]
};
const verifiedLook = b => VERIFIED[String(b.name || "").toLowerCase()] || null;
function bodyHash(b) { let h = 2166136261 >>> 0; const s = String(b.id64 || b.name || b.bodyId); for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619) >>> 0; return h >>> 0; }
const srgb2lin = c => c.map(v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });

// ---- the bake shader: hash noise, gradient noise, crater fields; one material for every body kind
const BAKE_GLSL = `
precision highp float; precision highp int;
// uLoop is always 10. Loops bounded by it stay loops: D3D unrolls constant ones, and that took ~24 s to compile.
uniform int uKind, uMode, uLoop; uniform uvec2 uSeed; uniform float uEps, uScale;
uniform vec3 uC[8]; uniform vec4 uP[6]; uniform vec3 uRung[7];
varying vec2 vUv;
uvec3 pcg3(uvec3 v) { v = v * 1664525u + 1013904223u; v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y; v ^= v >> 16u;
  v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y; return v; }
vec3 rnd3(ivec3 c, uint s) { return vec3(pcg3(uvec3(c + ivec3(1 << 20)) + uvec3(uSeed.x, uSeed.y, s)) & 0xFFFFu) / 65535.0; }   // offset: no negative → uint
float gnoise(vec3 p, uint s) {                         // gradient noise, quintic fade, about -1..1
  ivec3 i = ivec3(floor(p)); vec3 f = fract(p), u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  float n[8];
  for (int k = 0; k < min(8, uLoop); k++) { ivec3 o = ivec3(k & 1, (k >> 1) & 1, k >> 2); vec3 g = rnd3(i + o, s) * 2.0 - 1.0; n[k] = dot(g, f - vec3(o)); }
  return 1.6 * mix(mix(mix(n[0], n[1], u.x), mix(n[2], n[3], u.x), u.y), mix(mix(n[4], n[5], u.x), mix(n[6], n[7], u.x), u.y), u.z);
}
const mat3 ROT = mat3(0.00, 0.80, 0.60, -0.80, 0.36, -0.48, -0.60, -0.48, 0.64);
float fbm(vec3 p, int oct, uint s) { float a = 0.5, t = 0.0; for (int o = 0; o < min(oct, uLoop); o++) { t += a * gnoise(p, s + uint(o)); p = ROT * p * 2.03; a *= 0.5; } return t; }
float ridged(vec3 p, int oct, uint s) { float a = 0.5, t = 0.0; for (int o = 0; o < min(oct, uLoop); o++) { float n = 1.0 - abs(gnoise(p, s + uint(o))); t += a * n * n; p = ROT * p * 2.03; a *= 0.5; } return t; }
vec3 sph(vec2 uv) { float th = (1.0 - uv.y) * 3.14159265, ph = uv.x * 6.28318531; return vec3(-cos(ph) * sin(th), cos(th), sin(ph) * sin(th)); }
// craters on a sphere: jittered cells at several scales; returns height and a "fresh crater" brightness term
vec2 craters(vec3 d, float freq, float depth, float rays) {
  float h = 0.0, br = 0.0;
  for (int lv = 0; lv < min(4, uLoop); lv++) {
    float sc = freq * pow(2.3, float(lv)), dens = 0.9 - 0.12 * float(lv);
    vec3 p = d * sc; ivec3 c0 = ivec3(floor(p - 0.5));
    for (int k = 0; k < min(8, uLoop); k++) {
      ivec3 c = c0 + ivec3(k & 1, (k >> 1) & 1, k >> 2); vec3 r = rnd3(c, 900u + uint(lv));
      if (r.z > dens) continue;
      vec3 ctr = vec3(c) + 0.25 + 0.5 * r; float rad = 0.12 + 0.3 * pow(rnd3(c, 950u).x, 2.0);
      float u = length(p - ctr) / rad;
      if (u > 2.6) continue;
      float age = rnd3(c, 970u).y, dd = depth * rad / sc * 0.32;            // depth ~ 1/5 of the diameter
      h += (u < 1.0 ? (u * u - 1.0) * dd * 0.8 : 0.0) + dd * 0.35 * exp(-(u - 1.0) * (u - 1.0) / 0.03) * smoothstep(2.4, 1.0, u);
      if (u < 1.0 && rad > 0.3 && lv < 2) h += dd * 0.25 * exp(-u * u / 0.02);            // central peak in big craters
      br += (1.0 - age) * smoothstep(1.6, 0.9, u) * 0.35;                                    // young craters are brighter
      if (age < rays && lv < 2) { float a = atan(p.y - ctr.y, p.x - ctr.x) + (p.z - ctr.z);
        br += (1.0 - age / max(rays, 1e-3)) * smoothstep(5.0, 1.0, u) * pow(abs(sin(a * 11.0 + r.x * 30.0)), 18.0) * 0.45 * (0.5 + 0.5 * gnoise(p * 3.0, 975u)); }
    }
  }
  return vec2(h, br);
}
// ---- kinds: 0 gas giant · 1 solid (rocky, icy, metal, rocky ice, HMC) · 2 ocean world (ELW, water world) · 3 ammonia world
vec3 rotAx(vec3 v, vec3 k, float a) { return v * cos(a) + cross(k, v) * sin(a) + k * dot(k, v) * (1.0 - cos(a)); }
vec3 stormC(int i, out float sr) { vec3 r = rnd3(ivec3(i, 7, 3), 60u); float sl = (r.x - 0.5) * 1.6, slo = r.y * 6.2831853; sr = 0.025 + 0.07 * r.z * r.z;
  return vec3(-cos(slo) * cos(sl), sin(sl), sin(slo) * cos(sl)); }
vec3 giant(vec3 d) {
  // vortices first: they twist the coordinates, so bands curl around them
  vec3 dw = d;
  for (int i = 0; i < min(int(ceil(uP[1].x)), uLoop); i++) {
    float sr; vec3 c = stormC(i, sr); float dl = acos(clamp(dot(d, c), -1.0, 1.0)) / sr;
    if (dl < 3.0) dw = rotAx(dw, c, (rnd3(ivec3(i, 2, 2), 63u).x < 0.5 ? -1.0 : 1.0) * 1.4 * exp(-dl * dl * 1.2));
  }
  // shear zones: a large slow warp plus a finer one, so band edges wave and curl instead of fraying
  float lat = asin(clamp(dw.y, -1.0, 1.0)), Z = uP[0].z;
  float wa = fbm(vec3(dw.x, dw.y * 4.0, dw.z) * 1.8 * uP[0].x + 3.1, 5, 10u);
  float wb = fbm(vec3(dw.x * 6.0, dw.y * 30.0, dw.z * 6.0) + wa * 1.5, 4, 20u);
  float y = lat + 0.05 * uP[0].y * wa + 0.014 * uP[0].y * wb;
  float zones = 0.5 + 0.5 * (0.55 * sin(y * Z + 1.3) + 0.3 * sin(y * Z * 2.37 + 0.4) + 0.15 * sin(y * Z * 5.1 + 2.0));
  float along = fbm(vec3(dw.x * 2.5, y * Z * 0.6, dw.z * 2.5), 4, 30u) * 0.5 + 0.5;     // each band changes slowly along its length
  float raw = zones * 0.82 + along * 0.18;
  float blot = fbm(vec3(dw.x, dw.y * 1.6, dw.z) * 3.2 + wa, 6, 35u) * 0.5 + 0.5;           // life giants: blotches over weak bands
  raw = mix(raw, blot, uP[0].w);
  float pol = smoothstep(0.95, 1.3, abs(lat) + 0.1 * wa);                                    // poles: no bands, mottled
  raw = mix(raw, fbm(dw * 5.0 + wa, 6, 50u) * 0.5 + 0.45, pol);
  raw = clamp(raw * 1.15 - 0.07, 0.0, 1.0);
  float layer = 6.999 * pow(raw, 0.62);
  vec3 col = vec3(0.0); float wsum = 0.0;                                                   // soft blend of neighbouring layers: painted, not cut
  for (int k = 0; k < 7; k++) { float e = layer - float(k) - 0.5, wk = exp(-e * e * 2.6); col += uRung[k] * wk; wsum += wk; }
  col /= wsum;
  col *= 0.9 + 0.2 * mix(fbm(vec3(dw.x * 8.0, y * 90.0, dw.z * 8.0) + wa, 3, 80u) * 0.5 + 0.5, 0.5, pol);   // fine streaks along the flow
  col *= 0.95 + 0.1 * (fbm(dw * 30.0 + wa * 3.0, 3, 85u) * 0.5 + 0.5);                                       // small eddies
  for (int i = 0; i < min(int(ceil(uP[1].x)), uLoop); i++) {                                                                       // storm cores take a layer colour
    float sr; vec3 c = stormC(i, sr); vec3 e = d - c; e.y *= 1.7; float o = length(e) / (sr * 0.45);
    if (o > 1.2) continue;
    int pick = int(rnd3(ivec3(i, 4, 4), 62u).x * 6.99); vec3 sc = uRung[0];
    for (int k = 0; k < 7; k++) if (k == pick) sc = uRung[k];
    col = mix(col, sc * (0.92 + 0.12 * sin(o * 14.0)), smoothstep(1.0, 0.6, o) * 0.8);
  }
  return col;
}
float solidH(vec3 d) {
  float s = uScale, h = fbm(d * 1.6 * s, 6, 100u) * uP[0].x * 0.02 / s;                    // lowlands and highlands (relief ~1% of the radius)
  h += ridged(d * 3.2 * s + 4.0, 6, 120u) * uP[0].y * 0.012 / s;                            // mountains, ridges
  h += craters(d, 2.2 * s * (1.0 + uP[2].x), uP[0].z, uP[2].w).x;
  h -= uP[1].x * pow(max(ridged(d * 5.0 * s + 9.0, 4, 140u) - 0.6, 0.0), 2.0) * 0.02 / s;  // cracks (icy)
  return h;
}
vec4 solid(vec3 d) {                                       // rgb albedo, a = specular (none on solids)
  float s = uScale, h = solidH(d), m = fbm(d * 1.6 * s, 6, 100u);
  vec3 col = mix(uC[0], uC[1], smoothstep(-0.35, 0.45, m));                               // lowland → highland
  col = mix(col, uC[2], smoothstep(0.15, 0.5, fbm(d * 2.4 * s + 31.0, 5, 160u)) * uP[1].y);   // coloured patches
  float cr = uP[1].x * smoothstep(0.62, 0.9, ridged(d * 5.0 * s + 9.0, 4, 140u));
  col = mix(col, uC[3], cr);                                                               // crack lines
  vec2 c = craters(d, 2.2 * s * (1.0 + uP[2].x), uP[0].z, uP[2].w);
  col = mix(col, uC[4], clamp(c.y, 0.0, 1.0) * uP[2].z);                                  // fresh craters, rays
  col *= 0.88 + 0.24 * (fbm(d * 18.0 * s, 4, 180u) * 0.5 + 0.5);                          // grain
  float cap = smoothstep(uP[1].z - 0.06, uP[1].z + 0.04, abs(d.y) + 0.05 * fbm(d * 6.0, 4, 190u));
  col = mix(col, uC[5], cap * step(0.01, uP[1].w));                                       // polar frost
  return vec4(col, 0.0);
}
vec4 ocean(vec3 d) {
  float s = uScale, land = fbm(d * 1.4 * s, 8, 200u) + uP[0].x, hum = fbm(d * 2.0 * s + 5.0, 5, 210u);
  float lat = abs(d.y);
  vec3 sea = mix(uC[0], uC[1], smoothstep(-0.1, 0.12, land));                              // deep → shallow
  vec3 ground = mix(uC[2], uC[3], smoothstep(-0.2, 0.25, hum + lat * 0.6 - 0.2));          // green → dry
  ground = mix(ground, uC[4], smoothstep(0.25, 0.55, land) * 0.6);                          // mountains
  float isLand = smoothstep(0.0, 0.02, land) * step(0.5, uP[0].y);
  vec3 col = mix(sea, ground, isLand); float spec = 1.0 - isLand;
  float ice = smoothstep(uP[1].x - 0.05, uP[1].x + 0.05, lat + 0.12 * fbm(d * 4.0 + 3.0, 5, 220u));
  col = mix(col, uC[5], ice); spec *= 1.0 - ice;
  vec3 cq = d + 0.35 * vec3(fbm(d * 2.0, 4, 230u), fbm(d * 2.0 + 9.0, 4, 231u), fbm(d * 2.0 + 17.0, 4, 232u));
  float cl = smoothstep(uP[1].y, uP[1].y + 0.35, fbm(vec3(cq.x * 3.0, cq.y * 6.0, cq.z * 3.0), 7, 240u) * 0.5 + 0.5);
  col = mix(col, vec3(0.86), cl); spec *= 1.0 - cl;
  return vec4(col, spec);
}
vec4 ammonia(vec3 d) {                                     // seen: brown, grey and mauve mottled, tan patches
  float s = uScale, a = fbm(d * 2.2 * s, 7, 300u), b = fbm(d * 4.0 * s + 7.0, 6, 310u), m = fbm(d * 9.0 * s + 2.0, 5, 315u);
  vec3 col = mix(uC[0], uC[1], smoothstep(-0.25, 0.25, a + 0.25 * m));
  col = mix(col, uC[2], smoothstep(0.05, 0.4, b) * 0.75);
  col = mix(col, uC[3], smoothstep(0.2, 0.5, fbm(d * 3.0 * s + 3.0, 6, 320u) + 0.2 * m) * 0.85);
  return vec4(col * (0.88 + 0.24 * (fbm(d * 18.0, 4, 330u) * 0.5 + 0.5)), 0.0);
}
float heightAt(vec3 d) {
  if (uKind == 1) return solidH(d);
  if (uKind == 2) { float land = fbm(d * 1.4 * uScale, 8, 200u) + uP[0].x; return max(land, 0.0) * 0.6 * step(0.5, uP[0].y); }
  if (uKind == 3) return fbm(d * 1.5 * uScale, 7, 300u) * 0.15;
  return 0.0;
}
void main() {
  vec3 d = sph(vUv);
  if (uMode == 0) {
    vec4 c = uKind == 0 ? vec4(giant(d), 0.0) : uKind == 1 ? solid(d) : uKind == 2 ? ocean(d) : ammonia(d);
    gl_FragColor = vec4(pow(max(c.rgb, 0.0), vec3(1.0 / 2.2)), c.a);         // stored as sRGB-like 8 bit
  } else {                                                                     // object-space normal from the height field
    vec3 t1 = normalize(abs(d.y) < 0.99 ? cross(d, vec3(0.0, 1.0, 0.0)) : cross(d, vec3(1.0, 0.0, 0.0))), t2 = cross(d, t1);
    float h0 = heightAt(d), e = uEps;
    float hx = heightAt(normalize(d + t1 * e)), hy = heightAt(normalize(d + t2 * e));
    vec3 n = normalize(d - uP[3].x * ((hx - h0) / e * t1 + (hy - h0) / e * t2));
    float glow = uP[3].y * smoothstep(0.55, 0.9, ridged(d * 6.0 * uScale + 2.0, 5, 400u)) * smoothstep(0.004, -0.004, h0);
    gl_FragColor = vec4(n * 0.5 + 0.5, clamp(glow, 0.0, 1.0));               // a = glowing lava
  }
}`;
const BAKE = { mat: null, scene: null, cam: null, queue: [], live: new Set() };
function bakeInit() {
  if (BAKE.mat) return;
  BAKE.cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1); BAKE.scene = new THREE.Scene();
  BAKE.mat = new THREE.ShaderMaterial({
    uniforms: { uKind: { value: 0 }, uMode: { value: 0 }, uSeed: { value: new THREE.Vector2() }, uEps: { value: 0.002 }, uLoop: { value: 10 }, uScale: { value: 1 },
      uC: { value: Array.from({ length: 8 }, () => new THREE.Vector3()) }, uP: { value: Array.from({ length: 6 }, () => new THREE.Vector4()) },
      uRung: { value: Array.from({ length: 7 }, () => new THREE.Vector3()) } },
    vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
    fragmentShader: BAKE_GLSL, depthTest: false, depthWrite: false,
  });
  const q = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), BAKE.mat); q.frustumCulled = false; BAKE.scene.add(q);
  // The local baker compiles before its first queued slice. //                                  // v0.9: compiled in the background before the first surface
}
// what a body looks like: kind, colours and parameters for the bake shader
function surfaceRecipe(b) {
  const st = b.subType || "", h = bodyHash(b), r = i => ((Math.imul(h ^ (i * 0x9e3779b9), 2654435761) >>> 0) % 10007) / 10007;
  const T = b.surfaceTemperature || 0, Rkm = b.radius || 1000, comp = b.solidComposition || {}, ice = comp.Ice || 0, metal = comp.Metal || 0;
  const volc = b.volcanismType || "", C = [], P = Array.from({ length: 6 }, () => [0, 0, 0, 0]);
  const scale = Math.max(1, Math.min(5, Math.pow(Rkm / 500, 0.45)));
  const L = c => srgb2lin(c), mixc = (a, c, t) => a.map((v, i) => v + (c[i] - v) * t);
  if (isGiant(b)) {
    const g = giantLook(b), rung = g ? g.cols.map(L) : Array(7).fill(L((PAL.find(([re]) => re.test(st)) || [0, [[200, 180, 150]]])[1][0]));
    P[0] = [0.8 + r(1) * 0.8, 0.6 + r(2) * 0.9, 22 + r(3) * 20, g && g.cls === 10 ? 0.6 : 0]; P[1] = [3 + Math.floor(r(4) * 7), 0, 0, 0];
    if (g && g.band.every(x => x === g.band[0])) P[0][1] *= 0.8;          // one band only: a calmer planet
    return { kind: 0, rung, P, C: Array(8).fill([0, 0, 0]), scale: 1, normal: false, ls: 0 };
  }
  if (/Earth-like|Water world/i.test(st)) {
    const elw = /Earth-like/i.test(st), cold = Math.max(0, Math.min(1, (273 - T) / 45));
    const iceLat = elw ? 1.0 - 0.25 * cold - 0.05 : 1.1 - (0.35 + 0.65 * r(5)) * cold * 1.1;   // ice cover: colder → more, seeded
    C.push(L([10, 30, 66]), L([24, 66, 104]), L([58, 86, 44]), L([150, 128, 92]), L([110, 100, 92]), L([226, 232, 238]));
    P[0] = [elw ? -0.05 - r(6) * 0.08 : -1, elw ? 1 : 0, 0, 0]; P[1] = [Math.max(0.3, iceLat), (elw ? 0.47 : 0.56) + r(7) * 0.1, 0, 0];
    P[3] = [elw ? 0.03 : 0, 0, 0, 0];
    return { kind: 2, C, P, scale: 1, normal: elw, ls: 0.1 };
  }
  if (/Ammonia world/i.test(st)) {
    C.push(L([96, 80, 70]), L([124, 118, 120]), L([128, 96, 118]), L([180, 152, 108]));       // seen: brown, grey, mauve mottled with tan patches
    P[3] = [0.05, 0, 0, 0];
    return { kind: 3, C, P, scale: 1, normal: true, ls: 0.15 };
  }
  // solid bodies
  const icy = /Icy/i.test(st), rice = /Rocky ice/i.test(st), hmc = /High metal/i.test(st), mr = /Metal rich/i.test(st);
  let craterF = 0, lo, hi, patch = [0, 0, 0], crack = [0, 0, 0], fresh, cap = [235, 238, 242], craterD = 1, mount = 0.5, maria = 0.6, cracks = 0, patchAmt = 0, rays = 0;
  if (icy) {
    // Most icy bodies are white (19 of 22 at home). Which ones are red or dark is not in the data (refuted: temperature,
    // ruthenium, volcanism, atmosphere), so every icy body is white unless its colour was checked in the game (VERIFIED).
    lo = [214, 208, 202]; hi = [238, 234, 228];
    if (ice < 75) { lo = mixc(lo, [176, 170, 166], 0.35); hi = mixc(hi, [206, 202, 198], 0.3); }   // ~69% ice + 10% metal: greyer
    patch = [196, 190, 184]; patchAmt = r(12) < 0.3 ? 0.35 : 0;
    crack = [176, 168, 160]; cracks = 0.08 + r(15) * 0.15;
    fresh = [250, 250, 250]; craterD = 0.35; mount = 0.15; maria = 0.25; rays = r(16) < 0.25 ? 0.08 : 0; craterF = 1.6;
  } else if (rice) {
    lo = [120, 126, 138]; hi = [190, 198, 210]; fresh = [230, 236, 242]; crack = [90, 96, 108]; cracks = 0.3; craterD = 0.6; maria = 0.8;
  } else if (mr) {
    lo = [70, 68, 66]; hi = [120, 116, 110]; fresh = [170, 166, 160]; craterD = 1; mount = 0.8;
  } else if (hmc) {
    const v = r(20); [lo, hi] = v < 0.5 ? [[86, 80, 82], [150, 130, 100]] : [[96, 82, 70], [138, 118, 96]];
    if (hasAtm(b)) { lo = [150, 104, 64]; hi = [196, 148, 96]; patch = [86, 92, 108]; patchAmt = 0.6; }   // seen: ochre with blue-grey regions (UF-M c8-5 5)
    fresh = [190, 176, 150]; if (!hasAtm(b)) { patch = [120, 70, 50]; patchAmt = r(21) < 0.3 ? 0.4 : 0; }
  } else {                                                                     // rocky: grey to beige, brown and red-brown
    const looks = [[[104, 102, 100], [168, 164, 158]], [[150, 136, 118], [196, 182, 160]], [[110, 82, 66], [150, 112, 88]], [[96, 80, 68], [140, 120, 100]]];
    [lo, hi] = looks[Math.floor(r(22) * looks.length)]; fresh = [210, 206, 200]; rays = r(23) < 0.25 ? 0.07 : 0;
  }
  if (metal > 25 && !mr) { lo = mixc(lo, [80, 76, 72], 0.25); hi = mixc(hi, [120, 114, 108], 0.2); }
  const ver = verifiedLook(b);                                                // colour checked in the game: use it
  if (ver) { lo = ver[0]; hi = ver[1]; patchAmt = Math.min(patchAmt, 0.2); if (icy) patch = mixc(lo, [250, 250, 250], 0.5); }
  const capLat = (icy || T > 240) ? 2 : r(24) < 0.4 ? 0.82 + r(25) * 0.12 : 2;     // white polar caps on some cold rocky bodies
  const lava = /magma|lava/i.test(volc) && T > 500 ? Math.min(1, (T - 500) / 500) : 0;   // glowing only when hot
  C.push(L(lo), L(hi), L(patch), L(crack), L(fresh), L(cap));
  P[0] = [maria, mount, craterD * (hasAtm(b) && (b.surfacePressure || 0) > 0.1 ? 0.4 : 1), 0];
  P[1] = [cracks, patchAmt, capLat, capLat < 1.5 ? 1 : 0];
  P[2] = [craterF, 0, icy ? 0.18 : 0.4, rays];
  P[3] = [icy ? 0.8 : 1.0, lava, 0, 0];
  return { kind: 1, C, P, scale, normal: true, lava, ls: icy ? 0.3 : rice ? 0.4 : 0.6 };
}

function bakeUniforms(b, rec, res, pass) {
  const u = BAKE.mat.uniforms;
  u.uKind.value = rec.kind; u.uMode.value = pass; const h = bodyHash(b); u.uSeed.value.set(h & 0xffff, h >>> 16);
  u.uEps.value = 2 * Math.PI / res; u.uScale.value = rec.scale;
  for (let i = 0; i < 8; i++) { const c = (rec.C || [])[i] || [0, 0, 0]; u.uC.value[i].set(c[0], c[1], c[2]); }
  for (let i = 0; i < 6; i++) { const p = rec.P[i]; u.uP.value[i].set(p[0], p[1], p[2], p[3]); }
  for (let i = 0; i < 7; i++) { const c = (rec.rung || [])[i] || [0, 0, 0]; u.uRung.value[i].set(c[0], c[1], c[2]); }
}
// ------------------------------------------------------- star appearance
// Each stellar class gets its own look: limb darkening and boiling granulation
// for ordinary stars (larger cells on giants, spots on cool K/M and carbon stars),
// a hot featureless disc for white dwarfs, turbulent winds for Wolf-Rayet stars,
// cloud bands for brown dwarfs (L/T/Y), polar jet cones for neutron stars and
// gravitational lensing (screen-space, Einstein-ring mapping) for black holes.
const STAR_T = { value: 0 };
const STAR_ANIM = { on: false };          // v0.75.7: a star with moving flames is on screen, big enough to see them
const _corona = new Map();
function coronaTex(k) {                   // glow that starts at the disc's edge, so the surface stays visible
  if (_corona.has(k)) return _corona.get(k);
  const c = document.createElement("canvas"); c.width = c.height = 256; const g = c.getContext("2d");
  const e = Math.min(0.95, 2 / k), gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  gr.addColorStop(0, "rgba(255,255,255,0)"); gr.addColorStop(Math.max(0, e - 0.04), "rgba(255,255,255,0)");
  gr.addColorStop(e, "rgba(255,255,255,0.9)"); gr.addColorStop(Math.min(1, e + (1 - e) * 0.25), "rgba(255,255,255,0.35)"); gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 256, 256); const t = new THREE.CanvasTexture(c); _corona.set(k, t); return t;
}
function starKind(b) {
  const s = (b.subType || "") + " " + (b.spectralClass || ""), c = starLetter(b);
  const giant = /giant/i.test(b.subType || "") || /^(I|II|III)\b/.test(b.luminosity || "");
  if (/Black Hole/i.test(s)) return { kind: 3, halo: 0 };
  if (/Neutron/i.test(s)) return { kind: 2, halo: 3.2, scale: 0, spots: 0 };
  if (/White Dwarf/i.test(s) || c === "D") return { kind: 1, halo: 4.5, scale: 0, spots: 0 };
  if (/Wolf-Rayet/i.test(s) || c === "W") return { kind: 4, halo: 9, scale: 6, spots: 0 };
  if ("LTY".includes(c)) return { kind: 5, halo: 2.4, scale: 0, spots: 0 };
  if ("CS".includes(c) || /^MS/.test(b.spectralClass || "")) return { kind: 0, halo: 6, scale: giant ? 3 : 7, spots: 0.35 };
  return { kind: 0, halo: 6, scale: giant ? 3.5 : 9, spots: "KM".includes(c) ? 0.5 : 0 };
}
const STAR_NOISE = `
  float h3(vec3 p){ p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
  float n3(vec3 x){ vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(h3(i), h3(i + vec3(1,0,0)), f.x), mix(h3(i + vec3(0,1,0)), h3(i + vec3(1,1,0)), f.x), f.y),
               mix(mix(h3(i + vec3(0,0,1)), h3(i + vec3(1,0,1)), f.x), mix(h3(i + vec3(0,1,1)), h3(i + vec3(1,1,1)), f.x), f.y), f.z); }
  float fbm3(vec3 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 5; i++) { s += a * n3(p); p = p * 2.03 + 11.7; a *= 0.5; } return s; }
  float fbm3l(vec3 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 3; i++) { s += a * n3(p); p = p * 2.03 + 11.7; a *= 0.5; } return s * 1.143; }`;   // v0.75.7: 3 layers, for the flames
function starMaterial(b, color, K) {
  const m = new THREE.ShaderMaterial({
    defines: { STAR_LITE: QUALITY === PRESETS.low ? 1 : 0 },   // v0.71: Low draws a lighter star surface
    uniforms: { uCol: { value: color.clone() }, uTime: STAR_T, uKind: { value: K.kind }, uSeed: { value: (b.bodyId * 7.31) % 50 },
      uScale: { value: K.scale || 0 }, uSpots: { value: K.spots || 0 }, uLin: LIN, uWarm: { value: Math.max(0, Math.min(1, (5600 - (b.surfaceTemperature || 5600)) / 2400)) }, uBoost: { value: K.kind === 5 ? 1.3 : K.kind === 1 || K.kind === 2 ? 3 : 1.25 } },
    vertexShader: `
      #include <common>
      #include <logdepthbuf_pars_vertex>
      varying vec3 vP; varying vec3 vN; varying vec3 vW;
      void main() { vP = position; vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; vN = normalize(mat3(modelMatrix) * normal);
        gl_Position = projectionMatrix * viewMatrix * w;
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `
      #include <common>
      #include <logdepthbuf_pars_fragment>
      uniform vec3 uCol; uniform float uTime; uniform int uKind; uniform float uSeed; uniform float uScale; uniform float uSpots, uLin, uBoost, uWarm;
      varying vec3 vP; varying vec3 vN; varying vec3 vW;
      ${STAR_NOISE}
      void main() {
        #include <logdepthbuf_fragment>
        vec3 n = normalize(vN), v = normalize(cameraPosition - vW), u = normalize(vP);
        float mu = clamp(dot(n, v), 0.0, 1.0);
        vec3 p = u + uSeed, c;
        if (uKind == 5) {                         // brown dwarf: cloud bands, dim
          float w = fbm3(p * 3.0 + vec3(0.0, 0.0, uTime * 0.01));
          float band = sin((u.y + (w - 0.5) * 0.18) * 16.0) * 0.5 + 0.5;
          c = mix(uCol * 0.45, uCol * 1.1, band) * mix(0.45, 1.0, sqrt(mu));
        } else if (uKind == 1 || uKind == 2) {    // white dwarf / neutron star: tiny, hot, almost featureless
          c = uCol * (2.4 - 0.5 * (1.0 - mu));
        } else {
          // boiling surface: warped cells, bright hot patches, dark cool lanes (seen in game: orange disc, yellow-white patches)
          vec3 q = p * uScale * 1.1 + vec3(uTime * 0.012, uTime * 0.009, 0.0);
          #if STAR_LITE
          float g = fbm3(q * 1.3 + 3.1), f = 0.5;                                  /* v0.71 Low: one noise instead of five, still cells */
          #else
          vec3 wq = q + 1.6 * vec3(fbm3(q + 3.1), fbm3(q + 7.3), fbm3(q + 11.9)) + vec3(0.0, 0.0, uTime * 0.02);
          float g = fbm3(wq), f = fbm3(wq * 3.1 + vec3(uTime * 0.05));
          #endif
          float heat = clamp((g - 0.5) * 2.2 + 0.5 + (f - 0.5) * 0.6, 0.0, 1.0);
          vec3 mid = mix(uCol, vec3(1.0, 0.55, 0.16), uWarm), cool = mid * vec3(0.8, 0.45, 0.25), hot = mix(mid, vec3(1.0, 0.92, 0.6), 0.8);   // cool stars: game-like orange
          vec3 base = mix(mix(cool, mid, smoothstep(0.0, 0.5, heat)), hot, smoothstep(0.6, 0.92, heat));
          float limb = 1.0 - 0.55 * (1.0 - mu) - 0.2 * (1.0 - mu * mu);
          vec3 rim = mix(vec3(1.0, 0.45, 0.2), vec3(1.0), 0.25) * uCol;             // edges turn deeper and redder
          c = mix(rim * 0.8, base, smoothstep(0.0, 0.6, mu)) * limb * 1.15;
          if (uSpots > 0.0) c *= 1.0 - uSpots * smoothstep(0.62, 0.7, fbm3(u * 2.3 + uSeed * 3.0 + 17.0)) * 0.4;
          if (uKind == 4) c *= 0.75 + 0.6 * fbm3(p * 4.0 + vec3(uTime * 0.12));
        }
        c *= mix(1.0, uBoost, uLin);              // true scale: a star is far brighter than anything it lights (HDR, the tone curve rolls it to white)
        gl_FragColor = vec4(c, 1.0);


      }`,
  });
  return m;
}
function jetMaterial(color) {
  return new THREE.ShaderMaterial({
    uniforms: { uCol: { value: color.clone().lerp(new THREE.Color(0.75, 0.9, 1), 0.5) }, uTime: STAR_T },
    vertexShader: `
      #include <common>
      #include <logdepthbuf_pars_vertex>
      uniform float uLen; varying float vT; varying vec3 vP;
      void main() { vT = -position.y; vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `
      #include <common>
      #include <logdepthbuf_pars_fragment>
      uniform vec3 uCol; uniform float uTime; varying float vT; varying vec3 vP;
      ${STAR_NOISE}
      void main() {
        #include <logdepthbuf_fragment>
        float t = clamp(vT, 0.0, 1.0);
        float flick = 0.65 + 0.35 * n3(vec3(atan(vP.x, vP.z) * 3.0, t * 6.0 - uTime * 3.0, 0.0));
        float a = pow(1.0 - t, 1.6) * flick * 0.85;
        gl_FragColor = vec4(uCol * a * 2.0, a);

      }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  });
}
function addJets(tilt, r, color) {           // two cones along the spin axis, apex at the star
  const g = new THREE.ConeGeometry(1, 1, 48, 1, true); g.translate(0, -0.5, 0);   // apex at 0, base at y = -1
  const m = jetMaterial(color), out = [];
  for (const sgn of [1, -1]) { const j = new THREE.Mesh(g, m); j.scale.set(r * 1.4, r * 11, r * 1.4); j.rotation.x = sgn > 0 ? Math.PI : 0; j.renderOrder = 4; tilt.add(j); out.push(j); }
  return out;
}
const flatTex = (() => { const t = new THREE.DataTexture(new Uint8Array([255, 255, 255, 255]), 1, 1); t.needsUpdate = true; return t; })();
const glowTex = (() => {
  const c = document.createElement("canvas"); c.width = c.height = 128;
  const g = c.getContext("2d"), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(0.2, "rgba(255,255,255,.5)"); gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128); return new THREE.CanvasTexture(c);
})();


// prominences and flares: a camera-facing quad behind the star; flame tongues and loops rise from the limb (illustrative,
// seen in game around red dwarfs and other ordinary stars). The star's own disc hides the middle of the quad.
function promMaterial(color) {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, extensions: { derivatives: true },
    uniforms: { uCol: { value: color.clone() }, uTime: STAR_T, uSeed: { value: 0 }, uLin: LIN },
    vertexShader: `
      #include <common>
      #include <logdepthbuf_pars_vertex>
      varying vec2 vP; void main() { vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `
      #include <common>
      #include <logdepthbuf_pars_fragment>
      uniform vec3 uCol; uniform float uTime, uSeed, uLin; varying vec2 vP;
      ${STAR_NOISE}
      void main() {
        #include <logdepthbuf_fragment>
        float r = length(vP), a = atan(vP.y, vP.x), h = r - 1.0;
        if (h < -0.02 || r > 1.4) discard;
        float glow = exp(-max(h, 0.0) / 0.045) * 0.55 + exp(-max(h, 0.0) / 0.18) * 0.18;     // the thin bright layer at the edge
        vec2 pc = vec2(cos(a), sin(a)) * 3.0;
        // v0.75.7: lighter and calmer. Fewer noise layers, the fine noise only where a flame or an arch actually is,
        // slower motion, and line widths of at least ~1.5 pixels so the arches do not flicker from pixel to pixel
        float tongue = fbm3l(vec3(pc * 1.7 + uSeed, uTime * 0.05)), reach = 0.025 + 0.9 * pow(tongue, 3.0);
        float flame = 0.0;
        if (tongue > 0.5 && h < reach) flame = smoothstep(0.5, 0.68, tongue) * smoothstep(reach, 0.0, h) * smoothstep(0.3, 0.7, fbm3l(vec3(pc * 6.0, h * 18.0 - uTime * 0.25) + uSeed));
        float loops = 0.0, lw = max(0.02, fwidth(h) * 1.5);                            // a few arches standing on the limb
        for (int i = 0; i < 3; i++) {
          float c0 = fract(sin(uSeed * 3.7 + float(i) * 12.9) * 43758.5) * 6.2831853 + uTime * 0.004 * float(i + 1);
          float da = atan(sin(a - c0), cos(a - c0)), w = 0.18 + 0.1 * float(i);
          if (abs(da) > w) continue;
          float arch = (1.0 - (da * da) / (w * w)) * (0.14 + 0.05 * float(i)) * (0.85 + 0.15 * sin(uTime * 0.2 + float(i)));
          float d = abs(h - arch); if (d > lw) continue;
          loops += smoothstep(lw, 0.0, d) * (0.02 / lw) * (0.6 + 0.4 * fbm3l(vec3(da * 20.0, h * 30.0, uTime * 0.25)));
        }
        vec3 col = mix(uCol, vec3(1.0, 0.5, 0.15), 0.6);
        float I = glow + flame * 1.5 + loops * 1.3;
        I *= mix(0.6, 1.4, uLin) * smoothstep(-0.02, 0.0, h) * smoothstep(1.4, 1.15, r);
        gl_FragColor = vec4(col * I, 1.0);
      }`,
  });
}
// ------------------------------------------------------ lighting shaders
// Direct light from every star, analytic eclipses (fraction of the stellar
// disc covered by each nearby body, with penumbra) and ring shadows.
// v0.60: physically based shading in linear light. Surfaces get normal maps and a reflectance model per kind (the
// lunar-Lambert law for airless ground, limb darkening for gas giants, a sun glint on open water). Atmospheres are a
// shell that scatters starlight (Rayleigh + haze), so limbs glow, day sides haze over and thick ones hide the ground.
const LIGHT_GLSL = `
uniform vec4 uStars[${MAX_STARS}];   // xyz = position, w = radius
uniform vec3 uStarCol[${MAX_STARS}];
uniform int uNStars;
uniform vec4 uOcc[${MAX_OCC}];       // occluding spheres
uniform int uNOcc;
uniform float uEcl[${MAX_STARS}];    // fraction of each star's disc visible, computed in TRUE geometry
float angBetween(vec3 a, vec3 b) { return atan(length(cross(a, b)), dot(a, b)); }
float discCover(float aS, float aO, float sep) {
  if (sep >= aS + aO) return 0.0;
  float full = min(1.0, (aO * aO) / (aS * aS));
  if (sep <= abs(aO - aS)) return full;
  return full * clamp((aS + aO - sep) / (2.0 * min(aS, aO)), 0.0, 1.0);
}
float starVisibility(vec3 p, vec3 sp, float sr) {
  vec3 L = sp - p; float dL = length(L); vec3 l = L / dL;
  float aS = asin(min(sr / dL, 1.0)), vis = 1.0;
  for (int k = 0; k < ${MAX_OCC}; k++) {
    if (k >= uNOcc) break;
    vec3 o = uOcc[k].xyz - p; float dO = length(o);
    if (dO >= dL || dot(o, l) <= 0.0 || dO < uOcc[k].w * 1.0001) continue;
    float aO = asin(min(uOcc[k].w / dO, 1.0));
    vis *= 1.0 - discCover(aS, aO, angBetween(o, L));
  }
  return vis;
}`;
const lightUniforms = () => ({
  uStars: { value: Array.from({ length: MAX_STARS }, () => new THREE.Vector4()) },
  uStarCol: { value: Array.from({ length: MAX_STARS }, () => new THREE.Color()) }, uNStars: { value: 0 },
  uOcc: { value: Array.from({ length: MAX_OCC }, () => new THREE.Vector4()) }, uNOcc: { value: 0 }, uNight: { value: 0.003 },
  uEcl: { value: new Array(MAX_STARS).fill(1) },
});
// kinds: 0 gas giant · 1 solid ground · 2 ocean world · 3 ammonia world (set when the surface is baked)
function bodyMaterial(map) {
  return new THREE.ShaderMaterial({
    defines: { LITE: QUALITY === PRESETS.low ? 1 : 0 },             // v0.72: Low draws the ring shadow with one sample
    uniforms: { ...lightUniforms(), map: { value: map }, nmap: { value: map }, uHasN: { value: 0 }, uGlow: { value: 0 }, uKind: { value: 1 }, uLS: { value: 0.5 }, uDry: { value: 0 },
      uTint: { value: new THREE.Color(1, 1, 1) }, uLin: LIN, uRingTex: { value: map },
      uRing: { value: new THREE.Vector4() }, uRingN: { value: new THREE.Vector3(0, 1, 0) }, uRingC: { value: new THREE.Vector3() }, uAtm: { value: new THREE.Color(0, 0, 0) } },
    vertexShader: `
      #include <common>
      #include <logdepthbuf_pars_vertex>
      varying vec3 vW; varying vec3 vN; varying vec2 vUv; varying vec3 vM0; varying vec3 vM1; varying vec3 vM2;
      void main() {
        vUv = uv; vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; vN = normalize(mat3(modelMatrix) * normal);
        vM0 = normalize(modelMatrix[0].xyz); vM1 = normalize(modelMatrix[1].xyz); vM2 = normalize(modelMatrix[2].xyz);
        gl_Position = projectionMatrix * viewMatrix * w;
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `
      #include <common>
      #include <logdepthbuf_pars_fragment>
      ${LIGHT_GLSL}
      uniform sampler2D map, nmap, uRingTex; uniform vec3 uTint; uniform float uDry; uniform vec4 uRing; uniform vec3 uRingN; uniform vec3 uRingC; uniform float uNight;
      uniform float uHasN, uGlow, uKind, uLS, uLin; uniform vec3 uAtm;
      varying vec3 vW; varying vec3 vN; varying vec2 vUv; varying vec3 vM0; varying vec3 vM1; varying vec3 vM2;
      void main() {
        #include <logdepthbuf_fragment>
        vec4 tx = texture2D(map, vUv);
        vec3 alb = pow(tx.rgb, vec3(2.2)) * uTint; float water = tx.a * (1.0 - uDry);   // v0.71: dry ground never glints
        vec3 ng = normalize(vN), n = ng, v = normalize(cameraPosition - vW); float glow = 0.0;
        if (uHasN > 0.5) { vec4 nt = texture2D(nmap, vUv); vec3 no = nt.xyz * 2.0 - 1.0; n = normalize(vM0 * no.x + vM1 * no.y + vM2 * no.z); glow = nt.a * uGlow; }
        float ndv = max(dot(n, v), 0.0), ndvG = max(dot(ng, v), 0.0);
        vec3 lit = vec3(0.0), spec = vec3(0.0);
        for (int s = 0; s < ${MAX_STARS}; s++) {
          if (s >= uNStars) break;
          vec3 l = normalize(uStars[s].xyz - vW);
          float ndlG = dot(ng, l), ndl = dot(n, l), vis = 1.0;
          if (ndlG > -0.05) {
            vis = starVisibility(vW, uStars[s].xyz, uStars[s].w);
            if (uRing.w > 0.0) {                       // the rings' shadow, banded like the rings themselves
              float dn = dot(l, uRingN);
              if (abs(dn) > 1e-5) {
                float t = dot(uRingC - vW, uRingN) / dn;
                if (t > 0.0) { float r = length(vW + l * t - uRingC), u = (r - uRing.x) / (uRing.y - uRing.x);
                  if (u > 0.0 && u < 1.0) { float sh = 0.0;      // v0.63.5: averaged over ~6 % of the ring width, so fine ringlets don't alias into stripes
                    #if LITE
                    sh = texture2D(uRingTex, vec2(u, 0.5), 6.0).a * 9.0;
                    #else
                    for (int q = -4; q <= 4; q++) sh += texture2D(uRingTex, vec2(clamp(u + float(q) * 0.008, 0.0, 1.0), 0.5), 4.0).a;
                    #endif
                    vis *= 1.0 - sh / 9.0 * uRing.z; } }
              }
            }
          }
          float term = smoothstep(-0.02, 0.1, ndlG);    // the terminator follows the sphere; bumps never light the night side
          float d = max(ndl, 0.0);
          if (uKind < 0.5) d = max(ndlG, 0.0) * (0.72 + 0.28 * sqrt(ndvG));               // gas giant: soft limb darkening
          else d = mix(d, 2.0 * d / (d + ndv + 1e-3) * 0.5, uLS);                          // lunar-Lambert: flat, bright full disc
          vec3 Li = uStarCol[s] * vis * uEcl[s] * term;
          lit += Li * d;
          if (water > 0.01) {                             // sun glint on open water (GGX, Schlick Fresnel)
            vec3 hv = normalize(l + v); float nh = max(dot(ng, hv), 0.0), a2 = 0.012, dd = nh * nh * (a2 - 1.0) + 1.0;
            float F = 0.02 + 0.98 * pow(1.0 - max(dot(hv, v), 0.0), 5.0);
            spec += Li * water * (a2 / (3.14159 * dd * dd)) * F * max(ndlG, 0.0) * 0.25;
          }
        }
        vec3 col = alb * (lit + uNight) + spec + vec3(1.0, 0.36, 0.08) * glow * 1.6;
        gl_FragColor = vec4(col, 1.0);
      }`,
  });
}
// ---- atmosphere: a shell that scatters starlight. Rayleigh (blue) + haze (tinted by the dominant gas).
// Zenith optical depth from surface pressure; thick atmospheres veil the ground (seen in game: UF-M c8-10 AB 12,
// PF-M c8-3 1 and 2). Single scattering, 10 samples along the view ray, the planet's own shadow included.
function atmRecipe(b) {
  const st = b.subType || "", always = /Earth-like|Water world|Ammonia world/i.test(st);
  if (!hasAtm(b) && !always) return null;
  let P = b.surfacePressure; if (!(P > 0)) P = always ? 1 : 0.05;
  const [tint] = atmColor(b), lin = [tint.r, tint.g, tint.b];
  const tau = Math.min(40, 0.22 * Math.pow(P, 0.45)) * (/Ammonia world/i.test(st) ? 0.35 : 1);
  const haze = Math.min(0.92, 0.18 + 0.2 * Math.log10(1 + P)) * (/Earth-like/i.test(st) ? 0.5 : 1);
  const ray = [0.30, 0.55, 1.0].map(x => x * tau * (1 - haze));
  const hz = lin.map(x => (0.55 + 0.45 * x) * tau * haze);
  const hf = Math.max(0.012, Math.min(0.06, 0.012 + 0.01 * Math.log10(1 + P)));
  let alb = lin.map(x => 0.5 + 0.4 * x);                                    // what the cloud and haze deck reflects
  let cap = P > 1500 ? 0.97 : Math.min(0.68, 0.12 + 0.17 * Math.log10(1 + P));
  if (/Ammonia world/i.test(st)) cap = Math.min(cap, 0.35);                  // seen: AW at 644 atm still shows its mottled surface (PF-M c8-3 3)
  if (/Earth-like/i.test(st)) alb = [0.42, 0.6, 0.95];                     // thin air: a blue sky, as on Earth
  if (/Water world/i.test(st)) { cap = Math.min(cap, 0.55); alb = [0.6, 0.68, 0.8]; }   // seen: WW at 856 atm hazy blue-grey, cloud mass visible (PF-M c8-3 1)
  return { ray, hz, hf, alb, cap, si: /Ammonia world/i.test(st) ? 0.45 : 1, ms: Math.min(1, 0.12 * Math.log10(1 + P) + (always ? 0.1 : 0)), veil: P > 1500 };
}
function atmMaterial(rec) {
  return new THREE.ShaderMaterial({
    defines: { ATM_N: QUALITY === PRESETS.low ? 4 : 10 },            // v0.72: Low takes 4 steps through the air instead of 10
    transparent: true, depthWrite: false, side: THREE.FrontSide,
    blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor, blendEquation: THREE.AddEquation,
    uniforms: { ...lightUniforms(), uRatio: { value: 1 / (1 + rec.hf) }, uHk: { value: 4 }, uRay: { value: new THREE.Vector3(...rec.ray) }, uHz: { value: new THREE.Vector3(...rec.hz) },
      uI: { value: 0.35 * (rec.si || 1) }, uLin: LIN, uOn: { value: 1 }, uAlb: { value: new THREE.Vector3(...rec.alb) }, uCap: { value: rec.cap }, uMs: { value: rec.ms } },
    vertexShader: `
      #include <common>
      #include <logdepthbuf_pars_vertex>
      varying vec3 vW; varying vec3 vC; varying float vRa;
      void main() { vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; vC = modelMatrix[3].xyz; vRa = length(modelMatrix[0].xyz);
        gl_Position = projectionMatrix * viewMatrix * w;
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `
      #include <common>
      #include <logdepthbuf_pars_fragment>
      ${LIGHT_GLSL}
      uniform float uRatio, uHk, uI, uOn, uCap, uMs; uniform vec3 uRay, uHz, uAlb; varying vec3 vW; varying vec3 vC; varying float vRa;
      void main() {
        #include <logdepthbuf_fragment>
        vec3 c = vC; float Ra = vRa, R = Ra * uRatio, Hs = (Ra - R) / uHk;
        vec3 ro = cameraPosition, rd = normalize(vW - ro), oc = ro - c;
        float b = dot(oc, rd), disc = b * b - (dot(oc, oc) - Ra * Ra);
        if (disc <= 0.0 || uOn < 0.5) discard;
        float sq = sqrt(disc), t0 = max(-b - sq, 0.0), t1 = -b + sq;
        float dp = b * b - (dot(oc, oc) - R * R);
        if (dp > 0.0) { float tp = -b - sqrt(dp); if (tp > 0.0) t1 = min(t1, tp); }
        if (t1 <= t0) discard;
        const int N = ATM_N; float ds = (t1 - t0) / float(N);
        vec3 tau = vec3(0.0), sum = vec3(0.0);
        for (int i = 0; i < N; i++) {
          vec3 p = ro + rd * (t0 + (float(i) + 0.5) * ds), up = p - c; float rr = length(up); up /= rr;
          float rho = exp(-max(rr - R, 0.0) / Hs) / Hs;           // density normalised so the zenith column is 1
          vec3 dtau = (uRay + uHz) * rho * ds; tau += dtau * 0.5;
          for (int s = 0; s < ${MAX_STARS}; s++) {
            if (s >= uNStars) break;
            vec3 l = normalize(uStars[s].xyz - p); float mu = dot(up, l);
            float pr = dot(c - p, l), dist = length(c - p - l * pr);           // the planet's own shadow
            float lightOk = pr < 0.0 ? 1.0 : smoothstep(R * 0.985, R * 1.01, dist);
            vec3 tSun = (uRay + uHz) * exp(-max(rr - R, 0.0) / Hs) / max(mu + 0.12, 0.04) * 0.9;  // path to the star, Chapman-like
            float ct = dot(rd, l), g = 0.72, pR = 0.0597 * (1.0 + ct * ct), pM = 0.0796 * (1.0 - g * g) / pow(1.0 + g * g - 2.0 * g * ct, 1.5);
            sum += uStarCol[s] * uEcl[s] * lightOk * exp(-(tau + tSun)) * rho * ds * (uRay * pR + uHz * pM) * 12.566;
          }
          tau += dtau * 0.5;
        }
        vec3 T = exp(-tau);
        // multiple scattering, cheap form: an optically thick haze glows like a soft cloud deck lit from above
        vec3 n0 = normalize(ro + rd * t0 - c), ms = vec3(0.0);
        for (int s = 0; s < ${MAX_STARS}; s++) {
          if (s >= uNStars) break;
          vec3 l = normalize(uStars[s].xyz - c); float mu = dot(n0, l);
          ms += uStarCol[s] * uEcl[s] * smoothstep(-0.12, 0.25, mu) * (0.25 + 0.75 * max(mu, 0.0));
        }
        float a = min(1.0 - dot(T, vec3(0.3333)), uCap);
        gl_FragColor = vec4(sum * uI + ms * uAlb * uMs * a, a);
      }`,
  });
}
// ---- rings: one strip texture per planet (colour + density across all its rings); the type sets the colour
// (Rocky beige-brown, Icy white-blue, Metal Rich pale, Metallic grey; verified on in-game screenshots). Planet shadow
// and the unlit face are physical; the fine ringlets are illustrative.
const RING_COL = { Icy: [214, 222, 232], Rocky: [168, 138, 108], "Metal Rich": [214, 198, 186], Metallic: [176, 176, 180] };
function ringStrip(b) {
  const rings = (b.rings || []).slice().sort((x, y) => x.innerRadius - y.innerRadius);
  const rin = rings[0].innerRadius, rout = Math.max(...rings.map(r => r.outerRadius)), W = 2048;
  const data = new Uint8Array(W * 4), h = bodyHash(b);
  let rs = h || 1; const rnd = () => ((rs = (Math.imul(rs, 1664525) + 1013904223) >>> 0) / 4294967296);
  const waves = Array.from({ length: 24 }, () => [rnd() * 480 + 30, rnd() * 6.28, rnd() * 0.5]);
  const gaps = Array.from({ length: 3 + Math.floor(rnd() * 5) }, () => [rnd(), 0.002 + rnd() * 0.01]);
  for (let i = 0; i < W; i++) {
    const r = rin + (rout - rin) * (i + 0.5) / W, ring = rings.find(x => r >= x.innerRadius && r <= x.outerRadius);
    if (!ring) continue;
    const t = (r - ring.innerRadius) / (ring.outerRadius - ring.innerRadius), tg = i / W;
    let d = 0.58; for (const [f, p, a] of waves) d += a * (f > 400 ? 0.12 : 0.22) * Math.sin(tg * f + p);   // broad zones plus faint ringlets
    for (const [g, w] of gaps) if (Math.abs(tg - g) < w) d *= 0.15;
    d *= Math.min(1, t / 0.015) * Math.min(1, (1 - t) / 0.02);                  // soft inner and outer edges
    const type = Object.keys(RING_COL).find(k => k.toLowerCase() === String(ring.type).toLowerCase()) || "Rocky";
    const base = RING_COL[type], shade = 0.9 + 0.18 * (Math.sin(tg * 157 + 1.3) * 0.5 + 0.5) * (type === "Rocky" ? 1 : 0.6);
    data.set([Math.min(255, base[0] * shade), Math.min(255, base[1] * shade), Math.min(255, base[2] * shade), Math.max(0, Math.min(1, d)) * 255], i * 4);
  }
  const tex = new THREE.DataTexture(data, W, 1, THREE.RGBAFormat); tex.magFilter = THREE.LinearFilter; tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.generateMipmaps = true; tex.needsUpdate = true;
  return { tex, rin: rin / 1e6, rout: rout / 1e6 };
}
const RING_LIT = "0.62";
function ringMaterial(b, strip) {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, side: THREE.DoubleSide,
    uniforms: { ...lightUniforms(), uIn: { value: strip.rin }, uOut: { value: strip.rout }, uTex: { value: strip.tex }, uRN: { value: new THREE.Vector3(0, 1, 0) }, uLin: LIN, uSel: { value: 0 }, uA: { value: strip.rin }, uB: { value: strip.rout } },
    vertexShader: `
      #include <common>
      #include <logdepthbuf_pars_vertex>
      varying vec3 vW; varying float vR;
      void main() { vR = length(position.xy); vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w;
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `
      #include <common>
      #include <logdepthbuf_pars_fragment>
      ${LIGHT_GLSL}
      uniform float uIn, uOut, uNight, uLin, uSel, uA, uB; uniform vec3 uRN; uniform sampler2D uTex; varying vec3 vW; varying float vR;
      void main() {
        #include <logdepthbuf_fragment>
        float t = (vR - uIn) / (uOut - uIn);
        if (t < 0.0 || t > 1.0) discard;
        vec4 rt = texture2D(uTex, vec2(t, 0.5)); float dens = rt.a;
        if (dens < 0.004) discard;
        vec3 alb = pow(rt.rgb / 1.0, vec3(2.2)), v = normalize(cameraPosition - vW), lit = vec3(0.0);
        float camSide = dot(cameraPosition - vW, uRN);
        for (int s = 0; s < ${MAX_STARS}; s++) { if (s >= uNStars) break;
          vec3 l = normalize(uStars[s].xyz - vW); float ld = dot(l, uRN), ct = dot(-v, l);
          // Which face the star lights, blended across a narrow band: with the star in the ring plane
          // (no axial tilt or inclination) ld is ~0 and a hard sign test flips per pixel every frame.
          float sameFace = smoothstep(-0.015, 0.015, (camSide >= 0.0 ? 1.0 : -1.0) * ld);
          float vis = starVisibility(vW, uStars[s].xyz, uStars[s].w) * uEcl[s];
          // lit face: reflected light; unlit face: light that gets through the ring, stronger looking towards the star
          float fwd = 0.08 + 0.9 * pow(max(ct, 0.0), 6.0);
          float k = mix(0.2 * dens + (1.0 - dens) * fwd * 1.6, (0.45 + 0.55 * abs(ld)) * (1.0 + 0.6 * uLin), sameFace);   // unlit face: diffuse light that got through, plus forward scatter
          lit += uStarCol[s] * vis * k; }
        vec3 rc = alb * (lit * ${RING_LIT} + uNight); float ra = mix(dens * 0.92, min(1.0, dens * 1.35) * 0.96, uLin);   // true scale: dense rings are nearly opaque
        if (uSel > 0.0) {                                  // v0.64.2: hover = thin white edges; selected = pink edges and a soft pink tint
          float sel = step(0.75, uSel), px = fwidth(vR) * mix(1.6, 2.8, sel);
          float e = max(1.0 - smoothstep(0.0, px, vR - uA), 1.0 - smoothstep(0.0, px, uB - vR)) * step(uA, vR) * step(vR, uB);
          vec3 ec = mix(vec3(1.0), vec3(1.0, 0.42, 0.84), sel);
          rc = mix(rc, rc * vec3(1.15, 0.85, 1.1) + vec3(0.06, 0.0, 0.04), 0.6 * sel);
          rc = mix(rc, ec * max(1.0, max(rc.r, rc.g)), e); ra = max(ra, e);
        }
        gl_FragColor = vec4(rc, ra);
      }`,
  });
}


export {starColor,starKind,starMaterial,promMaterial,addJets,coronaTex,glowTex,flatTex,palette,bodyHash,bodyMaterial,atmRecipe,atmMaterial,ringStrip,ringMaterial,STAR_T};

export class SurfaceBaker {
  constructor(renderer) {
    this.renderer=renderer; this.queue=[]; this.targets=new Set(); this.disposed=false;
    bakeInit();
    this.ready=false;this.budget=65536;this.lastTick=0;
    // Warm the variant the bakes use (a render target: linear output), not the canvas one; otherwise
    // the first bake compiled it again, synchronously, freezing the deck.
    const warm=new THREE.WebGLRenderTarget(4,2,{depthBuffer:false}),previous=renderer.getRenderTarget();
    renderer.setRenderTarget(warm);
    const compiled=renderer.compileAsync(BAKE.scene,BAKE.cam);
    renderer.setRenderTarget(previous);
    compiled.catch(()=>{}).then(()=>{warm.dispose();this.ready=!this.disposed;});
  }
  request(body, material, resolution=512) {
    if((material.userData.bakedResolution||0)>=resolution)return;
    const pending=this.queue.find(job=>job.material===material);
    if(pending&&pending.resolution>=resolution)return;
    this.cancel(material);
    const create=()=>{
      const target=new THREE.WebGLRenderTarget(resolution,resolution/2,{depthBuffer:false,minFilter:THREE.LinearFilter});
      target.texture.wrapS=THREE.RepeatWrapping; this.targets.add(target); return target;
    };
    const recipe=surfaceRecipe(body);
    this.queue.push({body,material,resolution,recipe,albedo:create(),normal:recipe.normal?create():null,y:0,pass:0});
  }
  cancel(material) {
    this.queue=this.queue.filter(job=>{
      if(job.material!==material)return true;
      for(const target of [job.albedo,job.normal])if(target){target.dispose();this.targets.delete(target);} return false;
    });
    if(material.userData.baked){for(const target of material.userData.baked){target.dispose();this.targets.delete(target);} delete material.userData.baked;}
  }
  tick() {
    if(!this.ready||this.disposed||!this.queue.length)return;
    // A pixel budget per frame: it grows while frames stay smooth and backs off when they don't.
    const now=performance.now(),gap=this.lastTick?now-this.lastTick:16;this.lastTick=now;
    this.budget=gap>28?Math.max(8192,this.budget*.6):gap<20?Math.min(this.maxBudget||524288,this.budget*1.25):this.budget;
    const job=this.queue[0], rt=job.pass?job.normal:job.albedo;
    const rows=Math.max(8,Math.min(job.resolution/2-job.y,Math.floor(this.budget/job.resolution/8)*8));
    bakeUniforms(job.body,job.recipe,job.resolution,job.pass);
    const previous=this.renderer.getRenderTarget();
    rt.scissorTest=true;rt.scissor.set(0,job.y,job.resolution,rows);
    this.renderer.setRenderTarget(rt);this.renderer.render(BAKE.scene,BAKE.cam);this.renderer.setRenderTarget(previous);
    job.y+=rows;
    if(job.y<job.resolution/2)return;
    rt.scissorTest=false;
    if(!job.pass&&job.normal){job.pass=1;job.y=0;return;}
    const u=job.material.uniforms;
    u.map.value=job.albedo.texture;u.nmap.value=job.normal?.texture||flatTex;u.uHasN.value=job.normal?1:0;
    u.uTint.value.setRGB(1,1,1);u.uKind.value=job.recipe.kind;u.uLS.value=job.recipe.ls??.5;
    u.uDry.value=/Earth-like|Water world/i.test(job.body.subType||'')?0:1;
    job.material.userData.baked=[job.albedo,job.normal].filter(Boolean);
    job.material.userData.bakedResolution=job.resolution;
    this.queue.shift();
  }
  prioritize(material){const index=this.queue.findIndex(job=>job.material===material);if(index>0)this.queue.unshift(this.queue.splice(index,1)[0]);}
  dispose() { this.disposed=true;for(const target of this.targets)target.dispose();this.targets.clear();this.queue=[]; }
}
