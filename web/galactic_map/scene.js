// What the atlas draws, in WebGL: the galaxy and its 42 regions on one
// shader plane, the commander's travels as a line that fades with age, the
// plotted route, every visited system, intel markers and the "you are here"
// beacon. Everything is in Elite light years (see toScene in camera.js);
// colours come from the commander's theme.
import * as THREE from './vendor/three.module.min.js';
import {toScene} from './camera.js';

const MARKER_SHAPES = {circle: 0, diamond: 1, square: 2, triangle: 3, star: 4, hexagon: 5, ring: 6, cross: 7, target: 8};

const color = (value, fallback = '#ffffff') => new THREE.Color(value || fallback);

// --- The galaxy plane ---------------------------------------------------------
const GALAXY_VERTEX = `
varying vec2 vElite;
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vElite = vec2(world.x, -world.z);
  gl_Position = projectionMatrix * viewMatrix * world;
}`;

const GALAXY_FRAGMENT = `
uniform sampler2D uIds;
uniform sampler2D uGlow;
uniform sampler2D uVisited;
uniform vec2 uOrigin;
uniform float uExtent;
uniform vec2 uCentre;
uniform float uHover;
uniform float uSelected;
uniform float uCurrent;
uniform float uRegions;
uniform float uGrid;
uniform float uGlowOn;
uniform vec3 uBg, uText, uAccent, uOrange, uGreen, uBorder;
varying vec2 vElite;

float regionAt(vec2 uv) {
  if (uv.x < 0.0 || uv.y < 0.0 || uv.x >= 1.0 || uv.y >= 1.0) return 0.0;
  return floor(texture2D(uIds, uv).r * 255.0 + 0.5);
}
float hash12(vec2 p) { vec3 q = fract(vec3(p.xyx) * 0.1031); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }
vec2 hash22(vec2 p) { vec3 q = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973)); q += dot(q, q.yzx + 33.33); return fract((q.xx + q.yz) * q.zy); }

// One star per cell of \`cell\` light years, drawn a pixel or so wide at any
// zoom, and hidden once cells shrink below a few pixels (it would only shimmer).
float stars(vec2 p, float cell, float lyPx, float seed) {
  vec2 c = floor(p / cell);
  vec2 star = (c + 0.15 + 0.7 * hash22(c + seed)) * cell;
  float pick = hash12(c + seed * 1.7);
  float d = length(p - star) / lyPx;
  float lit = smoothstep(1.5, 0.0, d) * step(0.45, pick) * (0.35 + 0.65 * pick);
  return lit * smoothstep(3.0, 9.0, cell / lyPx);
}

float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), f.x), mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), f.x), f.y);
}
float fbm(vec2 p) {
  float value = 0.0, amplitude = 0.5;
  for (int i = 0; i < 4; i++) { value += amplitude * noise(p); p = p * 2.03 + 17.1; amplitude *= 0.5; }
  return value;
}

float gridAt(vec2 p, float spacing, float lyPx) {
  vec2 g = abs(fract(p / spacing - 0.5) - 0.5) * spacing / lyPx;
  return 1.0 - smoothstep(0.0, 1.1, min(g.x, g.y));
}

void main() {
  vec2 uv = (vElite - uOrigin) / uExtent;
  vec2 duv = fwidth(uv);
  float lyPx = max(fwidth(vElite).x, fwidth(vElite).y);
  float id = regionAt(uv);

  // The galaxy: an exponential disc with a bulge at Sagittarius A*, lit
  // along the regions Universal Cartographics calls arms and streams.
  float r = length(vElite - uCentre);
  float disc = exp(-r / 16000.0) * (1.0 - smoothstep(42000.0, 56000.0, r));
  float bulge = exp(-(r * r) / (2.0 * 3300.0 * 3300.0));
  float structure = texture2D(uGlow, clamp(uv, 0.0, 1.0)).r;
  // Dust: slow noise across a few thousand light years breaks the arms up.
  float dust = fbm(vElite / 2400.0);
  float light = disc * mix(0.05, 1.15, pow(structure, 2.4)) * mix(0.5, 1.3, dust) + bulge * 1.35;
  vec3 starlight = mix(mix(uAccent, uText, 0.55), mix(uOrange, uText, 0.2), clamp(bulge * 1.5 + exp(-r / 5600.0) * 0.55, 0.0, 1.0));
  vec3 colour = uBg + starlight * pow(light, 0.8) * 0.5 * uGlowOn;
  float field = stars(vElite, 380.0, lyPx, 1.0) * (0.15 + 2.2 * disc * structure)
              + stars(vElite, 2600.0, lyPx, 7.0) * (0.35 + 1.6 * disc)
              + stars(vElite, 45.0, lyPx, 3.0) * disc * structure * 1.4;
  colour += mix(uText, starlight, 0.35) * field * 0.8 * uGlowOn;

  // Regions: those the commander has flown through glow faintly; the one
  // they are in, the one under the cursor and the selected one more so.
  if (uRegions > 0.5 && id > 0.5) {
    float visited = texture2D(uVisited, vec2((id + 0.5) / 64.0, 0.5)).r;
    colour += uAccent * visited * 0.035;
    colour += uGreen * (abs(id - uCurrent) < 0.5 ? 0.05 : 0.0);
    colour += uAccent * (abs(id - uHover) < 0.5 ? 0.06 : 0.0);
    colour += uAccent * (abs(id - uSelected) < 0.5 ? 0.09 : 0.0);
  }

  // Borders straight from the raster: a pixel is on a border when a
  // neighbouring pixel lies in another region.
  if (uRegions > 0.5) {
    float edges = 0.0;
    float strong = 0.0;
    for (int i = 0; i < 4; i++) {
      vec2 offset = i == 0 ? vec2(duv.x, 0.0) : i == 1 ? vec2(-duv.x, 0.0) : i == 2 ? vec2(0.0, duv.y) : vec2(0.0, -duv.y);
      float other = regionAt(uv + offset);
      if (abs(other - id) > 0.5) {
        edges += 0.25;
        float mine = max(id, other);
        if (abs(id - uHover) < 0.5 || abs(other - uHover) < 0.5 || abs(id - uSelected) < 0.5 || abs(other - uSelected) < 0.5) strong = 1.0;
      }
    }
    float line = min(1.0, edges * 2.0);
    colour = mix(colour, mix(uBorder, uAccent, 0.3 + strong * 0.6), line * (0.45 + strong * 0.5));
  }

  // The galactic grid in light years: lines every power of ten, fading in
  // and out as the view zooms so there are always a few across the screen.
  if (uGrid > 0.5) {
    float level = log(lyPx * 70.0) / log(10.0);
    float base = pow(10.0, floor(level));
    float fine = gridAt(vElite, base, lyPx) * (1.0 - fract(level));
    float coarse = gridAt(vElite, base * 10.0, lyPx);
    colour = mix(colour, uBorder, max(fine * 0.35, coarse * 0.6) * 0.5);
  }
  gl_FragColor = vec4(colour, 1.0);
}`;

// --- Wide lines ---------------------------------------------------------------
// WebGL draws plain lines one pixel wide, so each segment is a quad widened
// in screen space.
const LINE_VERTEX = `
attribute vec3 aA;
attribute vec3 aB;
attribute vec2 aT;
attribute vec2 aD;
uniform vec2 uResolution;
uniform float uWidth;
varying float vT;
varying float vD;
varying float vSide;
void main() {
  vec4 a = projectionMatrix * modelViewMatrix * vec4(aA, 1.0);
  vec4 b = projectionMatrix * modelViewMatrix * vec4(aB, 1.0);
  a.w = max(a.w, 0.0001);
  b.w = max(b.w, 0.0001);
  vec2 sa = a.xy / a.w * uResolution * 0.5;
  vec2 sb = b.xy / b.w * uResolution * 0.5;
  vec2 along = sb - sa;
  vec2 dir = length(along) > 0.0001 ? normalize(along) : vec2(1.0, 0.0);
  vec2 normal = vec2(-dir.y, dir.x);
  vec4 p = mix(a, b, position.x);
  vec2 offset = normal * position.y * uWidth * 0.5 + dir * (position.x * 2.0 - 1.0) * uWidth * 0.35;
  p.xy += offset / uResolution * 2.0 * p.w;
  gl_Position = p;
  vT = mix(aT.x, aT.y, position.x);
  vD = mix(aD.x, aD.y, position.x);
  vSide = position.y;
}`;

const LINE_FRAGMENT = `
uniform vec3 uOld;
uniform vec3 uNew;
uniform float uOpacity;
uniform float uCut;
uniform float uDash;
uniform float uPhase;
uniform float uSoft;
varying float vT;
varying float vD;
varying float vSide;
void main() {
  if (vT > uCut) discard;
  float across = abs(vSide);
  float body = uSoft > 0.5 ? pow(1.0 - across, 2.2) : 1.0 - smoothstep(0.5, 1.0, across);
  float dash = uDash > 0.0 ? step(0.42, fract(vD / uDash - uPhase)) : 1.0;
  float age = mix(0.35, 1.0, smoothstep(0.0, 1.0, vT));
  vec3 colour = mix(uOld, uNew, smoothstep(0.0, 1.0, vT));
  gl_FragColor = vec4(colour, uOpacity * body * dash * age);
}`;

function lineMesh(options) {
  const geometry = new THREE.InstancedBufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute([0, -1, 0, 0, 1, 0, 1, -1, 0, 1, 1, 0], 3));
  geometry.setIndex([0, 2, 1, 2, 3, 1]);
  geometry.instanceCount = 0;
  const material = new THREE.ShaderMaterial({
    vertexShader: LINE_VERTEX, fragmentShader: LINE_FRAGMENT, transparent: true, depthWrite: false, depthTest: false,
    blending: options.additive ? THREE.AdditiveBlending : THREE.NormalBlending,
    uniforms: {
      uResolution: {value: new THREE.Vector2(1, 1)}, uWidth: {value: options.width},
      uOld: {value: new THREE.Color()}, uNew: {value: new THREE.Color()}, uOpacity: {value: options.opacity},
      uCut: {value: 2}, uDash: {value: 0}, uPhase: {value: 0}, uSoft: {value: options.soft ? 1 : 0},
    },
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  mesh.renderOrder = options.order || 1;
  return mesh;
}

function setLinePoints(mesh, points, depth) {
  const count = Math.max(0, points.length - 1);
  const a = new Float32Array(count * 3), b = new Float32Array(count * 3);
  const t = new Float32Array(count * 2), d = new Float32Array(count * 2);
  let travelled = 0;
  for (let index = 0; index < count; index += 1) {
    const from = toScene(...points[index].pos, depth), to = toScene(...points[index + 1].pos, depth);
    a.set([from.x, from.y, from.z], index * 3);
    b.set([to.x, to.y, to.z], index * 3);
    const span = Math.hypot(points[index + 1].pos[0] - points[index].pos[0], points[index + 1].pos[2] - points[index].pos[2]);
    t.set([index / Math.max(1, count), (index + 1) / Math.max(1, count)], index * 2);
    d.set([travelled, travelled + span], index * 2);
    travelled += span;
  }
  const geometry = mesh.geometry;
  geometry.setAttribute('aA', new THREE.InstancedBufferAttribute(a, 3));
  geometry.setAttribute('aB', new THREE.InstancedBufferAttribute(b, 3));
  geometry.setAttribute('aT', new THREE.InstancedBufferAttribute(t, 2));
  geometry.setAttribute('aD', new THREE.InstancedBufferAttribute(d, 2));
  geometry.instanceCount = count;
}

// --- Points: systems, markers, beacons ---------------------------------------------
const POINT_VERTEX = `
attribute vec3 aColor;
attribute float aShape;
attribute float aSize;
attribute float aState;
attribute float aT;
uniform float uScale;
uniform float uTime;
uniform float uCut;
varying vec3 vColor;
varying float vShape;
varying float vState;
varying float vSize;
void main() {
  vColor = aColor;
  vShape = aShape;
  vState = aState;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  // Not reached yet in a replay: put it outside the clip volume.
  if (aT > uCut) gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
  gl_PointSize = aSize * uScale * (1.0 + aState * 0.35);
  vSize = gl_PointSize;
}`;

const POINT_FRAGMENT = `
uniform float uOpacity;
uniform float uTime;
uniform vec3 uOutline;
varying vec3 vColor;
varying float vShape;
varying float vState;
varying float vSize;
float polygon(vec2 p, float sides, float radius) {
  float a = atan(p.x, p.y) + 3.14159265;
  float r = 6.2831853 / sides;
  return cos(floor(0.5 + a / r) * r - a) * length(p) - radius;
}
float star(vec2 p) {
  float a = atan(p.x, p.y);
  float k = 0.5 + 0.5 * cos(a * 5.0);
  return length(p) - mix(0.42, 0.9, k * k);
}
void main() {
  vec2 p = gl_PointCoord * 2.0 - 1.0;
  p.y = -p.y;
  float d;
  int shape = int(vShape + 0.5);
  if (shape == 0) d = length(p) - 0.72;
  else if (shape == 1) d = (abs(p.x) + abs(p.y)) - 0.86;
  else if (shape == 2) d = max(abs(p.x), abs(p.y)) - 0.62;
  else if (shape == 3) d = polygon(p + vec2(0.0, 0.12), 3.0, 0.42);
  else if (shape == 4) d = star(p);
  else if (shape == 5) d = polygon(p, 6.0, 0.64);
  else if (shape == 6) d = abs(length(p) - 0.6) - 0.16;
  else if (shape == 7) d = min(max(abs(p.x) - 0.2, abs(p.y) - 0.82), max(abs(p.y) - 0.2, abs(p.x) - 0.82));
  else {
    float pulse = fract(uTime * 0.45);
    float ring = abs(length(p) - (0.3 + pulse * 0.65)) - 0.05;
    float core = length(p) - 0.26;
    float edge = abs(length(p) - 0.5) - 0.045;
    float a1 = 1.0 - smoothstep(0.0, 0.06, core);
    float a2 = (1.0 - smoothstep(0.0, 0.06, ring)) * (1.0 - pulse);
    float a3 = (1.0 - smoothstep(0.0, 0.05, edge)) * 0.8;
    float alpha = max(a1, max(a2, a3));
    if (alpha < 0.01) discard;
    gl_FragColor = vec4(mix(vColor, vec3(1.0), a1 * 0.5), alpha * uOpacity);
    return;
  }
  float px = 2.0 / max(1.0, vSize);
  float fill = 1.0 - smoothstep(-px, px, d);
  float outline = 1.0 - smoothstep(-px, px, d - 0.16);
  if (outline < 0.01) discard;
  vec3 colour = mix(uOutline, vColor, fill);
  colour = mix(colour, vec3(1.0), vState * 0.3 * fill);
  gl_FragColor = vec4(colour, outline * uOpacity);
}`;

function pointCloud(order) {
  const geometry = new THREE.BufferGeometry();
  const material = new THREE.ShaderMaterial({
    vertexShader: POINT_VERTEX, fragmentShader: POINT_FRAGMENT, transparent: true, depthWrite: false, depthTest: false,
    uniforms: {uScale: {value: 1}, uOpacity: {value: 1}, uTime: {value: 0}, uCut: {value: 2}, uOutline: {value: new THREE.Color()}},
  });
  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  points.renderOrder = order;
  return points;
}

function setPoints(points, rows, depth) {
  const count = rows.length;
  const position = new Float32Array(count * 3), colours = new Float32Array(count * 3);
  const shape = new Float32Array(count), size = new Float32Array(count), state = new Float32Array(count), when = new Float32Array(count);
  rows.forEach((row, index) => {
    const at = toScene(...row.pos, depth);
    position.set([at.x, at.y, at.z], index * 3);
    colours.set([row.color.r, row.color.g, row.color.b], index * 3);
    shape[index] = row.shape;
    size[index] = row.size;
    state[index] = row.state || 0;
    when[index] = row.t ?? -1;
  });
  const geometry = points.geometry;
  geometry.setAttribute('position', new THREE.BufferAttribute(position, 3));
  geometry.setAttribute('aColor', new THREE.BufferAttribute(colours, 3));
  geometry.setAttribute('aShape', new THREE.BufferAttribute(shape, 1));
  geometry.setAttribute('aSize', new THREE.BufferAttribute(size, 1));
  geometry.setAttribute('aState', new THREE.BufferAttribute(state, 1));
  geometry.setAttribute('aT', new THREE.BufferAttribute(when, 1));
  geometry.computeBoundingSphere();
}

export function createScene(container) {
  let camera = null;
  const renderer = new THREE.WebGLRenderer({antialias: true, powerPreference: 'high-performance'});
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  container.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const theme = {};
  let depth = 4;
  let regions = null;

  // The galaxy plane: four times the region raster, so its edge (where the
  // grid and stars stop) is never on screen even fully zoomed out.
  const galaxyMaterial = new THREE.ShaderMaterial({
    vertexShader: GALAXY_VERTEX, fragmentShader: GALAXY_FRAGMENT, depthWrite: false, depthTest: false,
    uniforms: {
      uIds: {value: null}, uGlow: {value: null}, uVisited: {value: null},
      uOrigin: {value: new THREE.Vector2()}, uExtent: {value: 1}, uCentre: {value: new THREE.Vector2(25, 25900)},
      uHover: {value: 0}, uSelected: {value: 0}, uCurrent: {value: 0},
      uRegions: {value: 1}, uGrid: {value: 1}, uGlowOn: {value: 1},
      uBg: {value: new THREE.Color()}, uText: {value: new THREE.Color()}, uAccent: {value: new THREE.Color()},
      uOrange: {value: new THREE.Color()}, uGreen: {value: new THREE.Color()}, uBorder: {value: new THREE.Color()},
    },
  });
  const galaxy = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), galaxyMaterial);
  galaxy.rotation.x = -Math.PI / 2;
  galaxy.renderOrder = -10;
  galaxy.frustumCulled = false;
  scene.add(galaxy);
  const visited = new THREE.DataTexture(new Uint8Array(64), 64, 1, THREE.RedFormat);
  visited.needsUpdate = true;
  galaxyMaterial.uniforms.uVisited.value = visited;

  const sectors = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({vertexColors: true, transparent: true, opacity: .7, depthTest: false}));
  sectors.renderOrder = 0;
  sectors.frustumCulled = false;
  const travelGlow = lineMesh({width: 9, opacity: .22, additive: true, soft: true, order: 1});
  const travel = lineMesh({width: 2.2, opacity: .95, order: 2});
  const retrace = lineMesh({width: 2, opacity: .9, order: 2});
  const planned = lineMesh({width: 2.6, opacity: 1, order: 3});
  const stalk = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineDashedMaterial({dashSize: 1, gapSize: 1, transparent: true, opacity: .6, depthTest: false}));
  stalk.frustumCulled = false;
  const systems = pointCloud(4);
  const markers = pointCloud(5);
  const beacons = pointCloud(6);
  scene.add(sectors, travelGlow, travel, retrace, planned, stalk, systems, markers, beacons);

  const lines = [travelGlow, travel, retrace, planned];
  let lastRoute = [], lastPlanned = [], lastRetrace = [];
  let pixelRatio = 1;
  let systemRows = [], markerRows = [], beaconRows = [];

  function setTheme(values) {
    Object.assign(theme, values);
    const u = galaxyMaterial.uniforms;
    u.uBg.value = color(values.bg, '#070b10');
    u.uText.value = color(values.text, '#dcebf3');
    u.uAccent.value = color(values.accent, '#00d1ff');
    u.uOrange.value = color(values.orange, '#ff8a3d');
    u.uGreen.value = color(values.green, '#54e39a');
    u.uBorder.value = color(values.border, '#243746');
    renderer.setClearColor(u.uBg.value);
    const muted = color(values.muted, '#91a8b7');
    travel.material.uniforms.uOld.value = muted.clone().lerp(u.uBg.value, .35);
    travel.material.uniforms.uNew.value = u.uAccent.value.clone();
    travelGlow.material.uniforms.uOld.value = u.uAccent.value.clone().multiplyScalar(.35);
    travelGlow.material.uniforms.uNew.value = u.uAccent.value.clone();
    retrace.material.uniforms.uOld.value = u.uGreen.value.clone();
    retrace.material.uniforms.uNew.value = u.uGreen.value.clone();
    planned.material.uniforms.uOld.value = u.uOrange.value.clone();
    planned.material.uniforms.uNew.value = u.uOrange.value.clone();
    stalk.material.color = u.uAccent.value.clone();
    for (const cloud of [systems, markers, beacons]) cloud.material.uniforms.uOutline.value = u.uBg.value.clone();
  }

  function setRegions(value) {
    regions = value;
    const ids = new THREE.DataTexture(value.ids, value.size, value.size, THREE.RedFormat);
    ids.magFilter = ids.minFilter = THREE.NearestFilter;
    ids.needsUpdate = true;
    const glow = new THREE.DataTexture(value.glow.data, value.glow.size, value.glow.size, THREE.RedFormat);
    glow.magFilter = glow.minFilter = THREE.LinearFilter;
    glow.needsUpdate = true;
    const u = galaxyMaterial.uniforms;
    u.uIds.value = ids;
    u.uGlow.value = glow;
    u.uOrigin.value.set(value.x0, value.z0);
    u.uExtent.value = value.extent;
    u.uCentre.value.set(value.centre[0], value.centre[2]);
    const span = value.extent * 4;
    galaxy.scale.set(span, span, 1);
    galaxy.position.copy(toScene(value.x0 + value.extent / 2, 0, value.z0 + value.extent / 2));
  }

  function setVisitedRegions(ids) {
    visited.image.data.fill(0);
    for (const id of ids) if (id > 0 && id < 64) visited.image.data[id] = 255;
    visited.needsUpdate = true;
  }

  function setRoute(route) {
    lastRoute = route;
    setLinePoints(travel, route, depth);
    setLinePoints(travelGlow, route, depth);
  }
  function setRetrace(route) {
    lastRetrace = route;
    setLinePoints(retrace, route, depth);
  }
  function setPlanned(route) {
    lastPlanned = route;
    setLinePoints(planned, route, depth);
  }
  function setSystems(rows) {
    systemRows = rows;
    setPoints(systems, rows, depth);
  }
  function setMarkers(rows) {
    markerRows = rows;
    setPoints(markers, rows, depth);
  }
  function setBeacons(rows, current) {
    beaconRows = rows;
    setPoints(beacons, rows, depth);
    if (current) {
      const top = toScene(...current, depth), ground = toScene(current[0], 0, current[2]);
      stalk.geometry.setFromPoints([top, ground]);
      stalk.computeLineDistances();
      stalk.visible = Math.abs(current[1] * depth) > 1;
    } else {
      stalk.visible = false;
    }
  }
  function setSectors(cells) {
    const vertices = [], colours = [];
    for (const cell of cells) {
      const half = cell.size / 2, [x, , z] = cell.pos;
      const corners = [[x - half, z - half], [x + half, z - half], [x + half, z + half], [x - half, z + half]];
      corners.forEach((corner, index) => {
        const next = corners[(index + 1) % 4];
        for (const [cx, cz] of [corner, next]) {
          const at = toScene(cx, 0, cz);
          vertices.push(at.x, at.y, at.z);
          colours.push(cell.color.r, cell.color.g, cell.color.b);
        }
      });
    }
    sectors.geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    sectors.geometry.setAttribute('color', new THREE.Float32BufferAttribute(colours, 3));
  }

  function setDepth(value) {
    depth = value;
    setRoute(lastRoute);
    setRetrace(lastRetrace);
    setPlanned(lastPlanned);
    setSystems(systemRows);
    setMarkers(markerRows);
    const current = beaconRows.find((row) => row.current);
    setBeacons(beaconRows, current?.pos);
  }

  function setVisibility(layers) {
    galaxyMaterial.uniforms.uRegions.value = layers.Regions ? 1 : 0;
    travel.visible = travelGlow.visible = systems.visible = Boolean(layers.Travel);
    retrace.visible = Boolean(layers.Return);
    planned.visible = Boolean(layers.Planned);
    sectors.visible = Boolean(layers.Sectors);
  }

  function resize(width, height) {
    renderer.setSize(width, height, false);
    renderer.domElement.style.width = `${width}px`;
    renderer.domElement.style.height = `${height}px`;
    const ratio = renderer.getPixelRatio();
    for (const mesh of lines) mesh.material.uniforms.uResolution.value.set(width * ratio, height * ratio);
    pixelRatio = ratio;
    for (const cloud of [systems, markers, beacons]) cloud.material.uniforms.uScale.value = ratio;
  }

  // Screen position of an Elite coordinate; null when behind the camera.
  const scratch = new THREE.Vector3();
  function project(pos, width, height) {
    scratch.copy(toScene(pos[0], pos[1] || 0, pos[2], depth)).project(camera);
    if (scratch.z > 1 || scratch.z < -1) return null;
    return {x: (scratch.x + 1) / 2 * width, y: (1 - scratch.y) / 2 * height};
  }

  function render(time, {lyPerPixel, replay = 2, motion = true, systemAlpha = 1}) {
    const seconds = time / 1000;
    for (const cloud of [systems, markers, beacons]) cloud.material.uniforms.uTime.value = motion ? seconds : .35;
    systems.material.uniforms.uOpacity.value = systemAlpha;
    systems.material.uniforms.uCut.value = replay;
    markers.material.uniforms.uCut.value = replay;
    // Markers ease down to about half size as the view widens to the galaxy.
    markers.material.uniforms.uScale.value = pixelRatio * Math.min(1.1, Math.max(.55, 1.3 - .25 * Math.log10(Math.max(1, lyPerPixel))));
    travel.material.uniforms.uCut.value = replay;
    travelGlow.material.uniforms.uCut.value = replay;
    const dash = lyPerPixel * 14;
    planned.material.uniforms.uDash.value = dash;
    planned.material.uniforms.uPhase.value = motion ? seconds * .6 : 0;
    stalk.material.dashSize = stalk.material.gapSize = Math.max(.5, lyPerPixel * 4);
    renderer.render(scene, camera);
  }

  return {
    renderer, useCamera(value) { camera = value; }, setTheme, setRegions, setVisitedRegions, setRoute, setRetrace, setPlanned, setSystems,
    setMarkers, setBeacons, setSectors, setDepth, setVisibility, resize, project, render,
    setRegionState(values) {
      const u = galaxyMaterial.uniforms;
      if ('hover' in values) u.uHover.value = values.hover || 0;
      if ('selected' in values) u.uSelected.value = values.selected || 0;
      if ('current' in values) u.uCurrent.value = values.current || 0;
    },
    setBackdrop({grid, glow}) {
      galaxyMaterial.uniforms.uGrid.value = grid ? 1 : 0;
      galaxyMaterial.uniforms.uGlowOn.value = glow ? 1 : 0;
    },
    get depth() { return depth; },
    get regions() { return regions; },
  };
}

export {MARKER_SHAPES};
