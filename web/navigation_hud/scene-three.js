// Native WebGL scenes for the journal-driven Navigation HUD. Every scene is a
// hologram in the state's colour, the way the cockpit draws its own: shaded
// translucent solids, bright edges and a scan band sweeping through them.
// Only measured values read as quantities (probes used, threat level, FSD
// injection, scan progress, altitude, shields, boost); the rest is motion.
import * as THREE from '../galactic_map/vendor/three.module.min.js';

const TAU = Math.PI * 2;
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const fract = (x) => x - Math.floor(x);
const wave = (x) => .5 + .5 * Math.sin(x * TAU);
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
// Fades in and out across one pass of 0..1.
const ends = (t) => Math.sin(Math.PI * clamp(t)) ** 2;
const hash = n => { const x = Math.sin(n * 91.731 + 17.17) * 43758.5453; return x - Math.floor(x); };
const seedOf = text => [...text].reduce((a, c) => (Math.imul(a, 31) + c.charCodeAt(0)) >>> 0, 7);
const color = (value, fallback = '#ff8a32') => new THREE.Color(/^#[\da-f]{6}$/i.test(value || '') ? value : fallback);
const WHITE = new THREE.Color(1, 1, 1);

// The frame each scene composes for: a wide strip about 22 units across and
// 4.6 high at its focus. The camera backs off until both fit the deck.
const SHOT = {at: [0, 0, 0], from: [.34, .3, 1], width: 22, height: 4.6, fov: 24};

const HOLO_VERTEX = `
varying vec3 vNormal;
varying vec3 vView;
varying float vHeight;
#ifdef USE_COLOR
varying vec3 vTint;
#endif
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vec4 view = viewMatrix * world;
  vNormal = normalize(normalMatrix * normal);
  vView = -view.xyz;
  vHeight = world.y;
  #ifdef USE_COLOR
  vTint = color;
  #endif
  gl_Position = projectionMatrix * view;
}`;

const HOLO_FRAGMENT = `
uniform vec3 uColor;
uniform vec3 uHot;
uniform float uOpacity;
uniform float uFill;
uniform float uRim;
uniform float uLamp;
uniform float uPower;
uniform float uShade;
uniform float uSweep;
varying vec3 vNormal;
varying vec3 vView;
varying float vHeight;
#ifdef USE_COLOR
varying vec3 vTint;
#endif
void main() {
  vec3 normal = normalize(vNormal);
  float facing = abs(dot(normal, normalize(vView)));
  float rim = pow(1.0 - facing, uPower);
  float light = mix(1.0, 0.38 + 0.62 * max(dot(normal, vec3(-0.42, 0.72, 0.55)), 0.0), uShade);
  float fill = uFill * light;
  #ifdef USE_COLOR
  fill *= vTint.r;
  #endif
  float band = exp(-pow((vHeight - uSweep) * 2.6, 2.0)) * 0.42;
  vec3 tone = uColor * (fill + rim * uRim + band * (0.35 + uFill)) + uHot * uLamp;
  float alpha = uOpacity * clamp(0.16 + fill * 0.95 + rim * uRim + band * 0.4 + uLamp, 0.0, 1.0);
  gl_FragColor = vec4(tone, alpha);
  #include <colorspace_fragment>
}`;

// How each kind of surface takes the projection: fill is the shaded body,
// rim the glow along its silhouette, lamp a hot emitter.
const ROLES = {
  hull: {fill: .3, rim: .85},
  alloy: {fill: .42, rim: .85},
  navy: {fill: .24, rim: .85},
  ochre: {fill: .4, rim: .85},
  dark: {fill: .1, rim: .5},
  tyre: {fill: .08, rim: .45},
  glass: {fill: .05, rim: 1.3, lamp: .1},
  trim: {fill: .58, rim: .9},
  lamp: {fill: .25, rim: .4, lamp: .95},
  band: {fill: .65, rim: .6, lamp: .3},
  planet: {fill: .26, rim: 1.4, power: 3.6},
  shell: {fill: .012, rim: .95, power: 2.6},
  ground: {fill: .06, rim: .2},
  panel: {fill: .05, rim: .25},
  star: {fill: .6, rim: .35, lamp: .62, power: 1.6, shade: 0},
};
// The older scene vocabulary: a colour named where a role belongs.
const LEGACY = {cyan: ['lamp', 'accent'], red: ['lamp', 'red'], green: ['lamp', 'green'], orange: ['trim', 'state'],
  white: ['lamp', 'white'], gold: ['lamp', 'gold']};

function faceRole(kind, muted) {
  if (kind === 'trim' && muted) return ['hull', 'state'];
  if (['hull', 'alloy', 'navy', 'ochre', 'dark', 'tyre', 'glass', 'trim'].includes(kind)) return [kind, 'state'];
  if (/^pad\d$/.test(kind)) return [kind, 'state'];
  if (kind === 'hub') return ['trim', 'state'];
  if (/red|stop|port/.test(kind)) return ['lamp', 'red'];
  if (/green|go/.test(kind)) return ['lamp', 'green'];
  return ['lamp', 'state'];
}

function glowTexture() {
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 64;
  const ctx = canvas.getContext('2d'), light = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  light.addColorStop(0, '#fff'); light.addColorStop(.12, '#fff'); light.addColorStop(.35, '#ffffff80'); light.addColorStop(1, '#ffffff00');
  ctx.fillStyle = light; ctx.fillRect(0, 0, 64, 64);
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; return texture;
}

function merged(parts) {
  const positions = [];
  for (const part of parts) { for (const value of part.attributes.position.array) positions.push(value); part.dispose(); }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3)); geometry.computeVertexNormals();
  return geometry;
}

class Stage {
  constructor(state, palette, texture) {
    this.root = new THREE.Group(); this.flat = new THREE.Group();
    this.state = state; this.palette = palette; this.texture = texture;
    this.animations = []; this.materials = []; this.geometries = []; this.holos = new Map();
    this.sweep = {value: 0}; this.opacity = 1; this.hero = null; this.shot = {...SHOT};
    this.seed = seedOf(state.key + state.label);
  }
  tone(tint = 'state') {
    const p = this.palette;
    if (tint === 'state') return color(this.state.c, p.hud || p.orange);
    if (String(tint).startsWith('#')) return color(tint);
    return color({accent: p.accent, red: p.red, green: p.green, gold: p.yellow, white: p.text, orange: p.orange,
      hud: p.hud || p.orange}[tint], p.hud || p.orange);
  }
  track(material, alpha) {
    material.userData.alpha = alpha; this.materials.push(material); return material;
  }
  holo(role = 'hull', tint = 'state', alpha = 1, {dim = 1, side = THREE.FrontSide, vertexColors = false} = {}) {
    const key = `${role}|${tint}|${alpha}|${dim}|${side}|${vertexColors}`;
    if (this.holos.has(key)) return this.holos.get(key);
    const preset = ROLES[role] || (role.startsWith('pad') ? ROLES.lamp : ROLES.hull);
    const base = this.tone(tint), ghost = role === 'shell';
    const material = new THREE.ShaderMaterial({
      uniforms: {
        uColor: {value: base}, uHot: {value: base.clone().lerp(WHITE, .55)}, uOpacity: {value: alpha},
        uFill: {value: preset.fill * dim}, uRim: {value: preset.rim}, uLamp: {value: preset.lamp || 0}, uPower: {value: preset.power || 2}, uShade: {value: preset.shade ?? 1},
        uSweep: this.sweep,
      },
      vertexShader: HOLO_VERTEX, fragmentShader: HOLO_FRAGMENT, transparent: true, side, vertexColors,
      depthWrite: !ghost, blending: ghost ? THREE.AdditiveBlending : THREE.NormalBlending,
      polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 2,
    });
    material.userData.holo = true;
    this.holos.set(key, this.track(material, alpha)); return material;
  }
  ink(tint = 'state', opacity = .5, fog = true) {
    return this.track(new THREE.LineBasicMaterial({color: this.tone(tint), transparent: true, opacity,
      blending: THREE.AdditiveBlending, depthWrite: false, fog}), opacity);
  }
  mesh(geometry, role = 'hull', position = [0, 0, 0], scale = [1, 1, 1], opacity = 1, parent = this.root, options = {}) {
    const [kind, tint] = LEGACY[role] || [role, options.tint || 'state'];
    this.geometries.push(geometry);
    const mesh = new THREE.Mesh(geometry, this.holo(kind, tint, opacity, options));
    mesh.position.set(...position); mesh.scale.set(...scale); parent.add(mesh); return mesh;
  }
  outline(mesh, tint = 'state', opacity = .5, threshold = 30) {
    const edges = new THREE.EdgesGeometry(mesh.geometry, threshold); this.geometries.push(edges);
    const lines = new THREE.LineSegments(edges, this.ink(tint, opacity)); mesh.add(lines); return lines;
  }
  line(points, tint = 'state', opacity = .5, parent = this.root, segments = false) {
    const geometry = new THREE.BufferGeometry().setFromPoints(points.map(p => new THREE.Vector3(...p)));
    this.geometries.push(geometry);
    const material = this.ink(tint, opacity);
    const line = segments ? new THREE.LineSegments(geometry, material) : new THREE.Line(geometry, material);
    parent.add(line); return line;
  }
  // A live polyline whose points an animation rewrites every frame.
  strip(count, tint = 'state', opacity = .5, parent = this.root) {
    const line = this.line(Array.from({length: count}, () => [0, 0, 0]), tint, opacity, parent);
    line.frustumCulled = false; return line;
  }
  circle(radius, position = [0, 0, 0], tint = 'state', opacity = .5, {tilt = -Math.PI / 2, arc = TAU, segments = 96,
    dashed = false, parent = this.root} = {}) {
    const points = [];
    for (let i = 0; i <= segments; i++) { const a = i * arc / segments; points.push([Math.cos(a) * radius, Math.sin(a) * radius, 0]); }
    const line = this.line(points, tint, opacity, parent, dashed);
    line.position.set(...position); line.rotation.x = tilt; return line;
  }
  ring(radius, position = [0, 0, 0], kind = 'orange', tilt = -Math.PI / 2, opacity = .6, arc = TAU, parent = this.root) {
    const tint = kind === 'orange' ? 'state' : kind;
    const ring = this.mesh(new THREE.TorusGeometry(radius, Math.max(.012, radius * .012), 4, 72, arc), 'band',
      position, [1, 1, 1], opacity, parent, {tint});
    ring.rotation.x = tilt; return ring;
  }
  glow(position, size, kind = 'cyan', opacity = .55, parent = this.root) {
    const tint = kind === 'cyan' ? 'accent' : kind === 'orange' ? 'state' : kind;
    const material = this.track(new THREE.SpriteMaterial({map: this.texture, color: this.tone(tint), transparent: true,
      opacity, blending: THREE.AdditiveBlending, depthWrite: false, fog: false}), opacity);
    const sprite = new THREE.Sprite(material); sprite.position.set(...position); sprite.scale.setScalar(size); parent.add(sprite); return sprite;
  }
  points(positions, {tint = 'state', size = .08, opacity = .7, colors = null, parent = this.root, fog = true} = {}) {
    const geometry = new THREE.BufferGeometry();
    const position = new THREE.BufferAttribute(positions instanceof Float32Array ? positions : new Float32Array(positions), 3);
    position.setUsage(THREE.DynamicDrawUsage); geometry.setAttribute('position', position);
    if (colors) geometry.setAttribute('color', new THREE.BufferAttribute(colors, colors.length / position.count));
    this.geometries.push(geometry);
    const material = this.track(new THREE.PointsMaterial({color: colors ? WHITE : this.tone(tint), vertexColors: Boolean(colors),
      size, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false, fog}), opacity);
    const cloud = new THREE.Points(geometry, material); cloud.frustumCulled = false; parent.add(cloud); return cloud;
  }
  model(name, position = [0, 0, 0], size = 4, options = {}) {
    const M = window.NavigationModels;
    const source = name === 'ship' ? window.ShipModels?.get(options.type) || M.ship(options.type) : name === 'vehicle' ? M.vehicle(options.type || 'scarab')
      : name === 'building' ? M.building(options.type || 'block', options.seed || 0) : name === 'rock' ? M.rock(options.seed || 0)
        : M[name]?.();
    if (!source) throw new Error(`Missing navigation model: ${name}`);
    // y up, and a bank about the length built into the shape, so a scene's own
    // rotations still apply on top of it.
    const cb = Math.cos(options.bank || 0), sb = Math.sin(options.bank || 0);
    const place = ([x, y, z]) => [x, -y * cb - z * sb, -y * sb + z * cb];
    const bounds = new THREE.Box3().setFromPoints(source.v.map(v => new THREE.Vector3(...place(v))));
    const dimensions = bounds.getSize(new THREE.Vector3()), centre = bounds.getCenter(new THREE.Vector3());
    const unit = size / Math.max(dimensions.x, dimensions.y, dimensions.z, .01);
    const group = new THREE.Group(); group.scale.setScalar(unit);
    const tint = options.tint || 'state', roles = new Map();
    const materialFor = (kind) => {
      let [role, colour] = faceRole(kind, options.muted);
      if (options.lamps?.[kind]) colour = options.lamps[kind];
      else if (colour === 'state') colour = tint;
      const key = `${role}|${colour}`;
      if (!roles.has(key)) roles.set(key, this.holo(role, colour, options.alpha ?? 1, {dim: options.dim ?? 1}));
      return roles.get(key);
    };
    const ink = this.ink(options.ink || tint, options.edge ?? .55);
    const part = (faces, origin, parent) => {
      const positions = [], byMaterial = new Map();
      for (const face of faces) {
        const material = materialFor(face.k);
        if (!byMaterial.has(material)) byMaterial.set(material, []);
        const vertices = byMaterial.get(material);
        for (let i = 1; i < face.i.length - 1; i++) for (const index of [face.i[0], face.i[i + 1], face.i[i]]) {
          const v = place(source.v[index]); vertices.push(v[0] - origin.x, v[1] - origin.y, v[2] - origin.z);
        }
      }
      const geometry = new THREE.BufferGeometry(), materials = [];
      for (const [material, vertices] of byMaterial) {
        geometry.addGroup(positions.length / 3, vertices.length / 3, materials.length); materials.push(material);
        for (const value of vertices) positions.push(value);
      }
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3)); geometry.computeVertexNormals();
      this.geometries.push(geometry); parent.add(new THREE.Mesh(geometry, materials));
      const edges = new THREE.EdgesGeometry(geometry, 30); this.geometries.push(edges); parent.add(new THREE.LineSegments(edges, ink));
    };
    part(source.f.filter(face => face.wheel == null), centre, group);
    const nativeWheels = [];
    for (const [index, wheel] of (source.wheels || []).entries()) {
      const faces = source.f.filter(face => face.wheel === index);
      if (!faces.length) continue;
      const pivot = new THREE.Vector3(...place(wheel.at)), hub = new THREE.Group();
      hub.position.copy(pivot).sub(centre); part(faces, pivot, hub); group.add(hub); nativeWheels.push(hub);
    }
    group.position.set(...position); group.rotation.set(options.pitch || 0, options.yaw ?? -.3, options.roll || 0);
    Object.assign(group.userData, {modelCentre: centre, wheels: source.wheels || [], nativeWheels, unit, size, materials: roles, type: options.type || name,
      height: dimensions.y * unit, tail: bounds.min.x - centre.x, nose: bounds.max.x - centre.x});
    this.root.add(group); return group;
  }
  // Pads and lamps a scene lights in turn, by face kind.
  lamp(model, kind) {
    for (const [key, material] of model.userData.materials) if (key.startsWith(`${kind}|`)) return material;
    return null;
  }
  stars({streak = false, speed = 1, count = streak ? 70 : 80} = {}) {
    const vertices = streak ? count * 2 : count;
    const positions = new Float32Array(vertices * 3), colors = new Float32Array(vertices * 4);
    const cloud = streak ? null : this.points(positions, {colors, size: .06, opacity: .75, fog: false});
    let field = cloud;
    if (streak) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3).setUsage(THREE.DynamicDrawUsage));
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 4).setUsage(THREE.DynamicDrawUsage));
      this.geometries.push(geometry);
      const material = this.track(new THREE.LineBasicMaterial({vertexColors: true, transparent: true, opacity: .7,
        blending: THREE.AdditiveBlending, depthWrite: false, fog: false}), .7);
      field = new THREE.LineSegments(geometry, material); field.frustumCulled = false; this.root.add(field);
    }
    const tone = this.tone(streak ? 'accent' : 'white');
    const position = field.geometry.attributes.position, tint = field.geometry.attributes.color;
    this.animations.push(st => {
      for (let i = 0; i < count; i++) {
        const rate = (streak ? .07 * speed : .012 * speed) * (.7 + hash(i + 55) * .6);
        const travel = fract(hash(i + 17) + st.p * rate), fade = ends(travel) * (.35 + hash(i + 3) * .65);
        const x = 18 - travel * 36, y = (hash(i + 32) - .5) * 12, z = -6 - hash(i + 23) * 22;
        positions.set([x, y, z], i * (streak ? 6 : 3));
        colors.set([tone.r, tone.g, tone.b, fade], i * (streak ? 8 : 4));
        if (streak) {
          const length = (1 + hash(i) * 1.6) * speed;
          positions.set([x + length, y, z], i * 6 + 3); colors.set([tone.r, tone.g, tone.b, 0], i * 8 + 4);
        }
      }
      position.needsUpdate = tint.needsUpdate = true;
    });
    return field;
  }
  planet(position = [0, 0, 0], radius = 2.1, kind = 'rock', {atmosphere = true, spin = .05, latitudes = true} = {}) {
    const globe = new THREE.Group(); globe.position.set(...position); this.root.add(globe);
    const geometry = new THREE.IcosahedronGeometry(radius, 4), vertices = geometry.attributes.position, shades = [];
    const seed = hash(radius * 7 + position[0]) * 10, roughness = kind === 'ice' ? .5 : 1;
    for (let i = 0; i < vertices.count; i++) {
      const x = vertices.getX(i) / radius, y = vertices.getY(i) / radius, z = vertices.getZ(i) / radius;
      const relief = Math.sin(x * 7 + Math.sin(z * 5 + seed)) * Math.cos(y * 6 + seed) * .5 + Math.sin(x * 15 - y * 11 + z * 9) * .22;
      const n = 1 + relief * .018 * roughness;
      vertices.setXYZ(i, x * radius * n, y * radius * n, z * radius * n);
      const shade = .45 + .45 * (relief * roughness + .5); shades.push(shade, shade, shade);
    }
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(shades, 3)); geometry.computeVertexNormals();
    const sphere = this.mesh(geometry, 'planet', [0, 0, 0], [1, 1, 1], 1, globe, {vertexColors: true});
    if (latitudes) {
      for (const latitude of [-.55, 0, .55]) {
        const r = Math.sqrt(1 - latitude * latitude) * radius * 1.01;
        this.circle(r, [0, latitude * radius * 1.01, 0], 'state', .3, {parent: sphere, segments: 64});
      }
      const meridian = this.circle(radius * 1.01, [0, 0, 0], 'state', .22, {parent: sphere, tilt: 0, segments: 64});
      meridian.rotation.y = .6;
    }
    if (atmosphere) this.mesh(new THREE.SphereGeometry(radius * 1.06, 40, 24), 'shell', [0, 0, 0], [1, 1, 1], .7, globe,
      {tint: kind === 'ice' ? 'accent' : 'state'});
    globe.userData.sphere = sphere;
    this.animations.push(st => { sphere.rotation.y = st.p * spin; });
    return globe;
  }
  star(position = [0, 0, 0], radius = 1.2, family = this.state.starFamily, tone = this.state.starTone) {
    const familyName = String(family || '').toLowerCase();
    const black = familyName === 'blackhole', neutron = familyName === 'neutron', dwarf = familyName === 'dwarf';
    const size = black ? radius * .6 : neutron ? radius * .23 : dwarf ? radius * .4 : radius;
    let star;
    if (black) {
      const geometry = new THREE.SphereGeometry(size, 32, 24); this.geometries.push(geometry);
      star = new THREE.Mesh(geometry, this.track(new THREE.MeshBasicMaterial({color: 0x000000, transparent: true, fog: false}), 1));
      star.position.set(...position); this.root.add(star);
    } else {
      const geometry = new THREE.IcosahedronGeometry(size, 3), shades = [], surface = geometry.attributes.position;
      for (let i = 0; i < surface.count; i++) {
        const x = surface.getX(i) / size, y = surface.getY(i) / size, z = surface.getZ(i) / size;
        const cell = .72 + .28 * (Math.sin(x * 11 + Math.sin(z * 9)) * Math.cos(y * 10 + Math.sin(x * 7)) * .5 + .5);
        shades.push(cell, cell, cell);
      }
      geometry.setAttribute('color', new THREE.Float32BufferAttribute(shades, 3));
      const brown = ['l', 't', 'y'].includes(familyName);
      const tint = brown ? '#8e351b' : /^#[\da-f]{6}$/i.test(tone || '') ? tone : neutron ? '#c0eaff' : '#ffb44b';
      star = this.mesh(geometry, 'star', position, [1, 1, 1], 1, this.root, {tint, vertexColors: true});
      this.animations.push(st => { star.rotation.y = st.p * .04; });
    }
    if (black) {
      const disc = this.ring(radius, position, 'gold', -.8, .9); disc.scale.set(1.4, 1, 1);
      const outer = this.ring(radius * 1.22, position, 'cyan', -.8, .22); outer.scale.set(1.4, 1, 1);
      this.glow(position, radius * 2.6, 'gold', .25);
      this.animations.push(st => { disc.rotation.z = st.p * .4; outer.rotation.z = -st.p * .25; });
    } else {
      this.glow(position, radius * (neutron ? 1.2 : 1.9), 'white', .55);
      const corona = this.glow(position, radius * (neutron ? 2.3 : 4), neutron || dwarf ? 'cyan' : 'gold', .5);
      this.animations.push(st => corona.scale.setScalar(radius * (neutron ? 2.3 : 4) * (1 + Math.sin(st.p * 1.7) * .04)));
      if (neutron || dwarf) {
        for (const side of [-1, 1]) {
          const jet = this.mesh(new THREE.ConeGeometry(radius * .65, radius * 4, 20, 1, true), 'shell',
            [position[0], position[1] + side * radius * 2, position[2]], [1, 1, 1], 1, this.root, {tint: 'accent'});
          jet.rotation.z = side > 0 ? Math.PI : 0;
          this.line([[position[0], position[1] - radius * 4, position[2]], [position[0], position[1] + radius * 4, position[2]]], 'white', .8);
          this.animations.push(st => { jet.rotation.y = st.p * .6; });
        }
      } else if (familyName === 'wolf' || familyName === 'tauri') {
        for (let i = 0; i < 3; i++) {
          const shell = this.circle(radius * (1.4 + i * .35), position, familyName === 'wolf' ? 'accent' : 'gold', .35, {tilt: -.65 + i * .1});
          this.animations.push(st => { shell.rotation.z = st.p * (.1 + i * .05); });
        }
      } else if (['l', 't', 'y'].includes(familyName)) {
        this.circle(radius * 1.05, position, 'red', .45, {tilt: .3});
      }
    }
    return star;
  }
  terrain(seed = 1, {y = -2, clearing = 3.4, relief = 1, depth = 26, width = 50} = {}) {
    const cols = 42, rows = 15;
    const geometry = new THREE.PlaneGeometry(width, depth, cols, rows); geometry.rotateX(-Math.PI / 2);
    const height = (x, z) => {
      const side = smooth(clearing, clearing + 7, Math.abs(x)), back = clamp((-z - 4) / 12);
      const n = Math.sin(x * .45 + seed) * Math.cos(z * .6 + seed * .3) * .5 + Math.sin(x * 1.1 - z * .8 + seed * 2) * .25 + .45;
      return (side * 1.1 + back * 2.2) * n * relief;
    };
    const points = geometry.attributes.position;
    for (let i = 0; i < points.count; i++) points.setY(i, height(points.getX(i), points.getZ(i) - 6));
    geometry.computeVertexNormals();
    const ground = this.mesh(geometry, 'ground', [0, y, -6], [1, 1, 1], 1, this.root, {side: THREE.DoubleSide});
    const segments = [], at = (r, c) => [points.getX(r * (cols + 1) + c), points.getY(r * (cols + 1) + c) + .01, points.getZ(r * (cols + 1) + c)];
    for (let r = 0; r <= rows; r++) for (let c = 0; c < cols; c++) segments.push(at(r, c), at(r, c + 1));
    for (let c = 0; c <= cols; c += 2) for (let r = 0; r < rows; r++) segments.push(at(r, c), at(r + 1, c));
    this.line(segments, 'state', .3, ground, true);
    this.ground = (x, z) => y + height(x, z);
    return ground;
  }
  person(position = [0, 0, 0], walking = true, hazard = false) {
    const body = new THREE.Group(); body.position.set(...position); this.root.add(body);
    body.userData.role = 'commander';
    const chest = this.mesh(new THREE.CapsuleGeometry(.29, .4, 4, 12), 'hull', [0, 1.48, 0], [1, 1, .73], 1, body);
    this.mesh(new THREE.BoxGeometry(.43, .36, .09), 'alloy', [0, 1.61, .245], [1, 1, 1], 1, body);
    this.mesh(new THREE.BoxGeometry(.29, .055, .025), 'cyan', [0, 1.7, .3], [1, 1, 1], .65, body);
    this.mesh(new THREE.BoxGeometry(.49, .19, .35), 'dark', [0, 1.02, 0], [1, 1, 1], 1, body);
    this.mesh(new THREE.BoxGeometry(.4, .56, .24), 'alloy', [0, 1.51, -.32], [1, 1, 1], 1, body);
    for (const side of [-1, 1]) this.mesh(new THREE.CapsuleGeometry(.065, .28, 3, 8), 'dark', [side * .17, 1.48, -.47], [1, 1, 1], 1, body);
    const head = new THREE.Group(); head.position.set(0, 2.12, 0); body.add(head);
    this.mesh(new THREE.SphereGeometry(.275, 16, 12), 'alloy', [0, 0, 0], [1, 1.06, .96], 1, head);
    this.mesh(new THREE.SphereGeometry(.282, 16, 8, 0, Math.PI, .86, 1.1), 'glass', [0, 0, .008], [1, 1, 1], 1, head);
    this.line([[-.19, .11, .2], [0, .14, .277], [.19, .11, .2]], 'accent', .6, head);
    this.mesh(new THREE.CylinderGeometry(.18, .2, .08, 12), 'dark', [0, 1.9, 0], [1, 1, 1], 1, body);
    const legs = [], arms = [];
    for (const side of [-1, 1]) {
      const leg = new THREE.Group(), shin = new THREE.Group(); leg.position.set(side * .18, .96, 0); body.add(leg);
      this.mesh(new THREE.CapsuleGeometry(.11, .25, 3, 10), 'hull', [0, -.23, 0], [1, 1, 1], 1, leg);
      shin.position.y = -.45; leg.add(shin);
      this.mesh(new THREE.CapsuleGeometry(.095, .23, 3, 10), 'alloy', [0, -.22, 0], [1, 1, 1], 1, shin);
      this.mesh(new THREE.BoxGeometry(.22, .14, .36), 'dark', [0, -.43, .08], [1, 1, 1], 1, shin);
      legs.push({leg, shin, side});
      const arm = new THREE.Group(), forearm = new THREE.Group(); arm.position.set(side * .38, 1.8, 0); body.add(arm);
      this.mesh(new THREE.SphereGeometry(.15, 10, 8), 'alloy', [side * .025, 0, 0], [1, 1, .9], 1, arm);
      this.mesh(new THREE.CapsuleGeometry(.09, .24, 3, 10), 'hull', [0, -.22, 0], [1, 1, 1], 1, arm);
      forearm.position.y = -.42; arm.add(forearm);
      this.mesh(new THREE.CapsuleGeometry(.08, .2, 3, 10), 'alloy', [0, -.18, 0], [1, 1, 1], 1, forearm);
      this.mesh(new THREE.SphereGeometry(.085, 8, 6), 'dark', [0, -.37, 0], [1, 1, 1], 1, forearm);
      arms.push({arm, forearm, side});
    }
    const tool = new THREE.Group(); tool.position.set(0, -.36, .12); arms[1].forearm.add(tool);
    this.mesh(new THREE.BoxGeometry(.12, .17, .25), 'dark', [0, 0, .07], [1, 1, 1], 1, tool);
    this.mesh(new THREE.CylinderGeometry(.065, .075, .1, 10), 'cyan', [0, 0, .25], [1, 1, 1], .7, tool).rotation.x = Math.PI / 2;
    body.userData.tool = tool; body.userData.joints = {head, legs, arms};
    this.animations.push(st => {
      const phase = st.p * 3.1, pace = walking ? .25 : 0;
      for (const {leg, shin, side} of legs) { const stride = Math.sin(phase + (side < 0 ? Math.PI : 0)); leg.rotation.x = stride * pace; shin.rotation.x = Math.max(0, -stride) * pace * 1.3; }
      for (const {arm, forearm, side} of arms) { arm.rotation.x = side > 0 ? (hazard ? -.55 : -.32) : Math.sin(phase) * pace * .6; forearm.rotation.x = side > 0 ? -.8 : -.12; arm.rotation.z = side * (.06 + Math.sin(st.p * .8) * .015); }
      head.rotation.y = Math.sin(st.p * .38) * .16; head.rotation.x = hazard ? .12 : Math.sin(st.p * .51) * .035;
      chest.scale.y = 1 + Math.sin(st.p * (hazard ? 3.6 : 1.9)) * (hazard ? .025 : .008);
      body.position.y = position[1] + (walking ? (1 - Math.cos(phase * 2)) * .018 : 0);
    });
    return body;
  }
  // Flat marks in the deck's own pixels, for readouts that must stay legible
  // whatever the camera does: probe pips, threat level, alarm chevrons.
  mark(points, tint = 'state', opacity = .85) {
    const shape = new THREE.Shape(points.map(([x, y]) => new THREE.Vector2(x, y)));
    const geometry = new THREE.ShapeGeometry(shape); this.geometries.push(geometry);
    const material = this.track(new THREE.MeshBasicMaterial({color: this.tone(tint), transparent: true, opacity,
      depthTest: false, depthWrite: false, fog: false}), opacity);
    const mesh = new THREE.Mesh(geometry, material); this.flat.add(mesh); return mesh;
  }
  update(state, alpha = 1, fold = 1, view = {W: 0, H: 0}) {
    this.state = state; this.opacity = alpha * state.level * (state.halo ?? 1);
    this.root.scale.y = this.flat.scale.y = Math.max(.015, fold);
    this.sweep.value = -3.4 + fract(state.p * .13) * 7.4;
    for (const material of this.materials) {
      const value = material.userData.alpha * this.opacity;
      if (material.userData.holo) material.uniforms.uOpacity.value = value; else material.opacity = value;
    }
    for (const animate of this.animations) animate(state, view);
  }
  dispose() { this.geometries.forEach(g => g.dispose()); this.materials.forEach(m => m.dispose()); }
}

const CRUISE = new Set(['supercruise', 'supercruise_overcharge', 'supercruise_assist', 'taxi']);
const CHARGE = new Set(['fsd_charge', 'hyper_charge', 'fsd_injection']);
const TUNNEL = new Set(['hyperspace', 'jumping', 'carrier_transit']);
const APPROACH = new Set(['station_vicinity', 'docking_clearance', 'docking_denied', 'docking_cancelled', 'docking_timeout', 'docking_assist']);
const CARRIER = new Set(['carrier_vicinity', 'carrier_preparing', 'carrier_lockdown', 'carrier_arrival', 'carrier_deck']);
const MAPS = new Set(['map', 'galaxy_map', 'system_map', 'power_map', 'orrery', 'codex']);
const DESCENT = new Set(['orbital_approach', 'orbital_departure', 'glide', 'surface_approach', 'surface_hold', 'surface_departure']);
const PADS = new Set(['landed', 'surface_station', 'settlement_area']);
const VEHICLES = new Set(['srv', 'scarab', 'scorpion', 'rhino', 'nomad', 'srv_handbrake', 'srv_turret', 'srv_drive_assist', 'srv_threat']);
const FIGHTS = new Set(['combat', 'heavy_combat', 'interdiction', 'interdicted', 'signal_threat']);
const PANELS = new Set(['left_panel', 'right_panel', 'comms_panel', 'role_panel', 'station_services']);
const LOCKS = new Set(['mass_lock', 'signal_lock', 'signal_drop', 'capital_contact', 'unknown_contact', 'phenomena']);

// ---------------------------------------------------------------------------
// Shared pieces.
// ---------------------------------------------------------------------------

// The commander's own ship: the one they fly, unless the scene names another
// (a fighter, the taxi). It banks toward the camera so its plan reads, as
// the portraits show it; a ship sitting on a pad passes bank 0.
function hero(s, position, size, options = {}) {
  const ship = s.model('ship', position, size, {yaw: -.24, bank: .42, ...options, type: options.type || s.state.shipKey || undefined});
  s.hero = ship; return ship;
}

// The drive plume behind a ship, sized in world units whatever the model's scale.
function wake(s, ship, strength = 1, tint = 'state') {
  const unit = ship.userData.unit, tail = [ship.userData.tail * 1.02, 0, 0];
  const plume = s.glow(tail, 1, tint, .55, ship), core = s.glow(tail, 1, 'white', .45, ship);
  s.animations.push(st => {
    const flicker = 1 + Math.sin(st.p * 11.3) * .07 + Math.sin(st.p * 7.1) * .05;
    plume.scale.set(2.8 * strength * flicker / unit, .9 * strength / unit, 1);
    core.scale.set(1 * strength * flicker / unit, .3 * strength / unit, 1);
  });
  return plume;
}

function brackets(s, centre, w, h, tint = 'state', opacity = .8, parent = s.root) {
  const [x, y, z] = centre, a = Math.min(w, h) * .28, group = new THREE.Group(); parent.add(group);
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) {
    s.line([[x + sx * w / 2, y + sy * (h / 2 - a), z], [x + sx * w / 2, y + sy * h / 2, z], [x + sx * (w / 2 - a), y + sy * h / 2, z]], tint, opacity, group);
  }
  return group;
}

// A landing pad as its markings: a faint hexagon with its rim and spokes lit.
function padMarks(s, at, r = 2.4) {
  const pad = new THREE.Group(); pad.position.set(...at); s.root.add(pad);
  s.mesh(new THREE.CircleGeometry(r, 6), 'ground', [0, 0, 0], [1, 1, 1], 1, pad, {side: THREE.DoubleSide}).rotation.x = -Math.PI / 2;
  s.circle(r, [0, .02, 0], 'state', .9, {segments: 6, parent: pad});
  s.circle(r * .7, [0, .02, 0], 'state', .45, {segments: 6, parent: pad});
  const spokes = [];
  for (let i = 0; i < 6; i++) { const a = i * TAU / 6; spokes.push([Math.cos(a) * r * .7, .02, Math.sin(a) * r * .7], [Math.cos(a) * r, .02, Math.sin(a) * r]); }
  s.line(spokes, 'state', .5, pad, true);
  return pad;
}

const standOn = (model, groundY) => { model.position.y = groundY + model.userData.height / 2; return model; };

// A jagged arc of light, re-struck a few times a second.
function lightning(s, from, to, tint = 'accent', opacity = .85, jitter = .35, seed = 0) {
  const bolt = s.strip(12, tint, opacity), vertices = bolt.geometry.attributes.position;
  s.animations.push(st => {
    const strike = Math.floor(st.p * 7 + seed * 3);
    const live = hash(strike * 1.3 + seed) > .15;
    bolt.visible = live;
    for (let i = 0; i < 12; i++) {
      const t = i / 11, kick = i === 0 || i === 11 ? 0 : (hash(strike + i * 7 + seed) - .5) * jitter * 2;
      vertices.setXYZ(i, lerp(from[0], to[0], t) + kick * .3, lerp(from[1], to[1], t) + kick, lerp(from[2], to[2], t) + kick * .6);
    }
    vertices.needsUpdate = true;
  });
  return bolt;
}

// Alarm chevrons pointing in from both edges of the deck, top and bottom.
function chevrons(s, level = () => 1) {
  const marks = [];
  for (const side of [-1, 1]) for (const row of [-1, 1]) for (let i = 0; i < 3; i++) {
    const d = -side;
    const mark = s.mark([[-2.4 * d, 5.2], [2.8 * d, 0], [-2.4 * d, -5.2], [-.4 * d, 0]], 'state', .85);
    marks.push({mark, side, row, i});
  }
  s.animations.push((st, view) => {
    const alarm = level(st) * (.45 + .45 * wave(st.p * .5));
    for (const {mark, side, row, i} of marks) {
      mark.position.set(side * (view.W / 2 - 12 - i * 8), row * (view.H / 2 - 10), 0);
      mark.material.opacity = alarm * (1 - i * .2) * s.opacity;
    }
  });
}

// Small diamonds (probes) or triangles (threat) along a corner of the deck.
function pips(s, count, {lit = count, warn = Infinity, corner = 'top', shape = 'diamond', tint = 'state', pulse = false} = {}) {
  const marks = [];
  for (let i = 0; i < count; i++) {
    const points = shape === 'triangle' ? [[-3.6, -3], [0, 3.6], [3.6, -3]] : [[0, 4], [3.4, 0], [0, -4], [-3.4, 0]];
    const on = i < lit, mark = s.mark(points, i >= warn ? 'gold' : tint, on ? .9 : .22);
    if (!on) { mark.scale.setScalar(.75); }
    marks.push({mark, i, on});
  }
  s.animations.push((st, view) => {
    for (const {mark, i, on} of marks) {
      mark.position.set(-view.W / 2 + 13 + i * 10, (corner === 'top' ? 1 : -1) * (view.H / 2 - 10), 0);
      if (pulse && on) mark.material.opacity = (.45 + .45 * wave(st.p * .5 - i * .1)) * s.opacity;
    }
  });
}

// Shield bubble, heat, hardpoints, low fuel, night vision and neutron boost,
// from Status flags, wherever the commander's own ship is.
function systems(s) {
  const anchor = new THREE.Group(); s.root.add(anchor);
  const size = s.hero ? s.hero.userData.size * .85 : 3;
  const shield = s.mesh(new THREE.SphereGeometry(1, 28, 16), 'shell', [0, 0, 0], [size * .62, size * .3, size * .42], 1, anchor, {tint: 'accent'});
  const broken = s.mesh(new THREE.SphereGeometry(1, 14, 8), 'shell', [0, 0, 0], [size * .62, size * .3, size * .42], 1, anchor, {tint: 'red'});
  s.outline(broken, 'red', .35, 1);
  const heat = s.glow([0, 0, 0], size * 1.4, 'red', .32, anchor);
  const fuel = s.glow([0, size * .3, 0], .55, 'gold', .8, anchor);
  const hardpoints = new THREE.Group(); anchor.add(hardpoints);
  for (const side of [-1, 1]) s.line([[size * .45, side * .45, 0], [size * .62, 0, 0], [size * .45, -side * .05, 0]], 'red', .8, hardpoints);
  const vision = s.circle(size * .6, [0, -size * .18, 0], 'green', .45);
  anchor.add(vision);
  const boost = new THREE.Group(); anchor.add(boost);
  const tier = s.state.d.neutronBoostValue >= 5.5 ? 3 : s.state.d.neutronBoostValue >= 3.5 ? 2 : 1;
  for (let i = 0; i < tier; i++) s.circle(size * (.7 + i * .09), [0, 0, 0], 'accent', .6, {tilt: .3 + i * .45, arc: TAU * .7, parent: boost});
  s.animations.push(st => {
    if (s.hero) anchor.position.copy(s.hero.position);
    const d = st.d, own = d.inMainShip;
    shield.visible = own && d.shieldsKnown && d.shieldsUp;
    broken.visible = own && d.shieldsKnown && !d.shieldsUp && Math.sin(st.p * 9) > -.2;
    heat.visible = d.overheating; heat.material.opacity = (.22 + .18 * wave(st.p * .7)) * s.opacity;
    fuel.visible = own && d.lowFuel; fuel.material.opacity = (.4 + .5 * wave(st.p * .6)) * s.opacity;
    hardpoints.visible = own && d.hardpoints; vision.visible = d.nightVision;
    boost.visible = d.neutronBoost; boost.rotation.y = st.p * .15; boost.rotation.z = st.p * .1;
  });
}

// ---------------------------------------------------------------------------
// Normal space, supercruise, the frame shift drive and witchspace.
// ---------------------------------------------------------------------------

function flight(s, key) {
  const fighter = key === 'fighter', silent = key === 'silent_running', drifting = key === 'flight_assist_off';
  s.stars();
  const ship = hero(s, fighter ? [-2.2, .2, .9] : [-4.4, 0, .9], fighter ? 2.8 : 4.4, {type: fighter ? 'fighter' : undefined,
    dim: silent ? .45 : 1, edge: silent ? .3 : .55});
  if (!silent) wake(s, ship, fighter ? .75 : 1.05);
  if (fighter) {
    const mother = s.model('ship', [6.8, .8, -5], 5.6, {yaw: -.55}); wake(s, mother, 1);
    const link = s.strip(2, 'accent', .4), at = link.geometry.attributes.position;
    s.animations.push(st => {
      ship.rotation.x = Math.sin(st.p * 1.3) * .5; ship.position.y = .2 + Math.sin(st.p * .9) * .35;
      at.setXYZ(0, ship.position.x, ship.position.y, ship.position.z); at.setXYZ(1, 6.8, .8, -5); at.needsUpdate = true;
      link.material.opacity = (.15 + .3 * wave(st.p * .8)) * s.opacity;
    });
    return;
  }
  s.planet([8.4, -1.5, -7.5], 3.3, 'rock');
  const station = s.model('coriolis', [3, .9, -10], 1.5, {pitch: .3, yaw: .5});
  s.circle(4.2, [8.4, -1.5, -7.5], 'state', .22, {tilt: -1.25});
  s.animations.push(st => { station.rotation.z = st.p * .12; });
  if (silent) {
    const seal = s.mesh(new THREE.SphereGeometry(1, 24, 12), 'shell', [-4.4, 0, .9], [2.6, .8, 1.5], .6, s.root, {tint: 'accent'});
    s.outline(seal, 'accent', .12, 1);
    s.animations.push(st => { ship.rotation.y = -.24 + Math.sin(st.p * .13) * .04; seal.rotation.y = st.p * .05; });
  } else if (drifting) {
    // Flight assist off: the nose wanders off the line of travel and the
    // thrusters fire in short bursts to catch it.
    const travel = s.line([[-4.4, 0, .9], [2, 0, .9]], 'accent', .5);
    const puffs = [[1.6, .3], [1.6, -.3], [-1.4, .3], [-1.4, -.3]].map(([x, y]) => s.glow([x, y, 0], .5, 'white', .7, ship));
    s.animations.push(st => {
      ship.rotation.y = -.24 + Math.sin(st.p * .35) * .55; ship.rotation.z = Math.sin(st.p * .27) * .3;
      ship.position.y = Math.sin(st.p * .6) * .3; travel.position.y = ship.position.y;
      puffs.forEach((puff, i) => { puff.material.opacity = (fract(st.p * .9 + i * .37) < .12 ? .8 : 0) * s.opacity; puff.scale.setScalar(.45 / ship.userData.unit); });
    });
  } else {
    s.animations.push(st => { ship.rotation.y = -.24 + Math.sin(st.p * .13) * .05; ship.rotation.x = Math.sin(st.p * .21) * .06; ship.position.y = Math.sin(st.p * .3) * .12; });
  }
}

function cruise(s, key) {
  const boost = key === 'supercruise_overcharge', assist = key === 'supercruise_assist';
  s.stars({streak: true, speed: boost ? 2.3 : 1});
  const at = [-4.2, -.15, .9];
  const ship = hero(s, at, 4.2, {type: key === 'taxi' ? 'taxi' : undefined, yaw: -.16});
  wake(s, ship, boost ? 1.9 : 1.25, boost ? 'accent' : 'state');
  // The frame shift bubble round the hull.
  const bubble = s.mesh(new THREE.SphereGeometry(1, 32, 16), 'shell', at, [3.1, 1.05, 1.6], boost ? .9 : .5, s.root,
    {tint: boost ? 'accent' : 'state'});
  for (let side of [-1, 1]) for (let layer = 0; layer < 3; layer++) {
    const wakeLine = s.line(Array.from({length: 40}, (_, i) => [-13 + i * .17, 0, 0]), boost ? 'accent' : layer ? 'state' : 'white', layer ? .22 : .4);
    const vertices = wakeLine.geometry.attributes.position;
    s.animations.push(st => {
      for (let i = 0; i < vertices.count; i++) {
        const x = -13 + i * .17, spread = 1 - i / (vertices.count - 1);
        vertices.setXYZ(i, x, at[1] + side * (.3 + layer * .2 + spread * .7) + Math.sin(x * .9 - st.p * (boost ? 4 : 1.6) + layer) * spread * (boost ? .25 : .12), at[2] - layer * .5);
      }
      vertices.needsUpdate = true;
    });
  }
  const target = [8.8, .7, -7];
  s.star(target, 1.05, s.state.targetFamily, s.state.targetTone);
  if (boost) {
    for (let i = 0; i < 7; i++) {
      const a = i * TAU / 7, b = a + 1.3;
      lightning(s, [at[0] + Math.cos(a) * 3, at[1] + Math.sin(a) * 1, at[2]], [at[0] + Math.cos(b) * 3.1, at[1] + Math.sin(b) * 1.05, at[2] + .3], 'accent', .9, .3, i);
    }
    s.glow([at[0] - 2.5, at[1], at[2]], 3.5, 'accent', .3);
  }
  if (assist || key === 'taxi') {
    const path = [];
    for (let i = 0; i <= 30; i++) { const t = i / 30; path.push([lerp(at[0] + 2.2, target[0] - 1.4, t), lerp(at[1], target[1], t) + Math.sin(t * Math.PI) * .6, lerp(at[2], target[2], t)]); }
    s.line(path, 'accent', .55, s.root, true);
    const lock = brackets(s, target, 3.3, 3.3, 'accent', .85);
    s.animations.push(st => { lock.scale.setScalar(1 + Math.sin(st.p * 1.2) * .04); });
  }
  s.animations.push(st => {
    ship.rotation.z = Math.sin(st.p * .47) * .02 + (boost ? Math.sin(st.p * 2.3) * .03 : 0);
    ship.rotation.y = -.16 + Math.sin(st.p * .19) * .025;
    bubble.scale.set(3.1 + Math.sin(st.p * 1.1) * .06, 1.05, 1.6); bubble.rotation.x = st.p * .2;
  });
}

function charge(s, key) {
  const hyper = key === 'hyper_charge', inject = key === 'fsd_injection';
  s.stars();
  const ship = hero(s, [-2.6, 0, .4], 4.8, {yaw: -.2});
  wake(s, ship, hyper ? 1.2 : .9, hyper ? 'accent' : 'state');
  const coil = new THREE.Group(); coil.position.set(-2.6, 0, .4); s.root.add(coil);
  const rings = [];
  for (let i = 0; i < 7; i++) {
    const holder = new THREE.Group(); holder.rotation.y = Math.PI / 2; coil.add(holder);
    const ring = s.ring(1.25 + i * .13, [0, 0, 0], hyper ? 'cyan' : 'orange', 0, .5, TAU * .76, holder);
    rings.push({holder, ring, i});
  }
  // Energy drawn into the drive along a tightening helix.
  const count = 46, flow = new Float32Array(count * 3);
  const swirl = s.points(flow, {tint: hyper ? 'accent' : 'state', size: .13, opacity: .9});
  const core = s.glow([-4.6, 0, .4], 1.6, hyper ? 'cyan' : 'orange', .7);
  s.animations.push(st => {
    for (const {holder, ring, i} of rings) {
      ring.rotation.z = st.p * (hyper ? 1.5 : .8) + i * .9;
      holder.position.x = Math.sin(st.p * .9 + i * .4) * .25 + i * .55 - 1.8;
      holder.rotation.x = Math.sin(st.p * .6 + i) * .25;
    }
    for (let i = 0; i < count; i++) {
      const t = fract(st.p * .35 + hash(i)), a = i * 2.4 + t * 6 + st.p * .8, r = (1 - t) * (2.2 + hash(i + 9) * 1.8);
      flow.set([-4.6 + Math.cos(a) * r * .8 + (1 - t) * 1.4, Math.sin(a) * r * .5, .4 + Math.cos(a * .7 + i) * r * .5], i * 3);
    }
    swirl.geometry.attributes.position.needsUpdate = true;
    core.scale.setScalar(1.3 + wave(st.p * .9) * .9);
  });
  if (hyper) {
    // The witchspace aperture forming ahead of the nose.
    const vortex = new Float32Array(150 * 3), spiral = s.points(vortex, {tint: 'accent', size: .1, opacity: .85});
    const lip = s.ring(1.8, [7.6, 0, -1], 'cyan', 0, .7); lip.rotation.y = -.5;
    s.glow([7.6, 0, -1], 2.6, 'white', .35);
    s.star([7.6, 0, -1.4], .35, s.state.targetFamily, s.state.targetTone);
    s.animations.push(st => {
      for (let i = 0; i < 150; i++) {
        const arm = i % 3, t = fract(hash(i) + st.p * .15), a = arm * TAU / 3 + t * 7 - st.p * 1.2, r = .2 + t * 2.1;
        vortex.set([7.6 + Math.sin(a) * r * .45, Math.cos(a) * r, -1 + Math.sin(a) * r * .8], i * 3);
      }
      spiral.geometry.attributes.position.needsUpdate = true;
      lip.rotation.z = st.p * .5; lip.scale.setScalar(.9 + wave(st.p * .4) * .2);
    });
  }
  if (inject) {
    const crystal = s.model('crystal', [6.6, 0, 0], 2.6, {yaw: 0, lamps: {hull: 'accent'}});
    for (let i = 0; i < 3; i++) {
      const stream = s.strip(16, 'accent', .6), v = stream.geometry.attributes.position;
      s.animations.push(st => {
        for (let j = 0; j < 16; j++) { const t = j / 15; v.setXYZ(j, lerp(5.4, -1.6, t), (i - 1) * .55 * (1 - t) + Math.sin(t * 9 - st.p * 4 + i) * .08, lerp(0, .4, t)); }
        v.needsUpdate = true;
      });
    }
    s.animations.push(st => { crystal.rotation.y = st.p * .6; crystal.rotation.x = st.p * .2; });
    const percent = s.state.d.fsdInjectionPercent, level = percent >= 100 ? 3 : percent >= 50 ? 2 : 1;
    for (let i = 0; i < level; i++) {
      const mark = s.mark([[-2.4, 5.2], [2.8, 0], [-2.4, -5.2], [-.4, 0]], 'accent', .9);
      s.animations.push((st, view) => mark.position.set(view.W * .06 + i * 9, view.H * .06, 0));
    }
  }
}

function tunnel(s, key) {
  const carrier = key === 'carrier_transit', jumping = key === 'jumping';
  s.shot = {at: [6, 0, 0], from: [-.62, .2, .76], width: 18, height: 5.4, fov: 30};
  const rings = [];
  for (let i = 0; i < 16; i++) {
    const ring = s.circle(2.3 + (i % 3) * .2, [0, 0, 0], i % 4 ? 'state' : 'accent', .6, {tilt: 0, arc: TAU * (.55 + hash(i) * .4)});
    ring.rotation.y = Math.PI / 2; rings.push(ring);
  }
  const threads = [];
  for (let i = 0; i < 10; i++) threads.push(s.strip(24, i % 2 ? 'state' : 'accent', .35));
  const sparks = new Float32Array(60 * 3), field = s.points(sparks, {tint: 'white', size: .07, opacity: .8});
  s.glow([22, 0, 0], 7, 'white', .5);
  const end = s.star([24, 0, 0], .8, s.state.targetFamily, s.state.targetTone);
  end.visible = !carrier;
  const vessel = carrier ? s.model('carrier', [1, -.3, 0], 6, {yaw: 0}) : hero(s, [1, -.25, 0], 2.6, {yaw: 0});
  if (!carrier) wake(s, vessel, 1.2, 'accent');
  const flash = s.glow([20, 0, 0], 2, 'white', .9);
  const speed = jumping ? .26 : .14;
  s.animations.push(st => {
    rings.forEach((ring, i) => {
      const travel = fract(i / rings.length + st.p * speed);
      ring.position.x = 26 - travel * 32; ring.rotation.x = st.p * .3 + i * .7;
      ring.material.opacity = .6 * ends(travel) * s.opacity;
    });
    threads.forEach((thread, i) => {
      const v = thread.geometry.attributes.position;
      for (let j = 0; j < 24; j++) {
        const x = -6 + j * 1.3, a = i * TAU / 10 + st.p * .5 + x * .08, r = 2.6 + Math.sin(x * .3 + st.p) * .15;
        v.setXYZ(j, x, Math.cos(a) * r, Math.sin(a) * r);
      }
      v.needsUpdate = true;
    });
    for (let i = 0; i < 60; i++) {
      const t = fract(hash(i) + st.p * speed * 1.6), a = hash(i + 7) * TAU, r = .6 + hash(i + 3) * 1.8;
      sparks.set([26 - t * 32, Math.cos(a) * r, Math.sin(a) * r], i * 3);
    }
    field.geometry.attributes.position.needsUpdate = true;
    vessel.position.y = -.25 + Math.sin(st.p) * .12; vessel.rotation.x = Math.sin(st.p * .7) * .08;
    const burst = jumping ? smooth(0, 1.2, st.age) : 0;
    flash.scale.setScalar(2 + burst * 9); flash.material.opacity = (jumping ? .2 + .6 * burst : .25 + .2 * wave(st.p * .5)) * s.opacity;
  });
}

function arrival(s, key) {
  s.stars();
  const local = key !== 'arrival', radius = local ? 1 : 2.6;
  const star = s.star(local ? [9.2, 1.4, -10] : [6, 0, -3], radius);
  const rays = [];
  for (let i = 0; i < 14; i++) rays.push(s.strip(2, 'gold', .45));
  const ship = hero(s, [-4.6, -.3, 1.1], 3.6, {yaw: -.2});
  wake(s, ship, 1);
  if (key === 'arrival') {
    // The witchspace exit closing behind the ship.
    const aperture = s.ring(1.6, [-7, -.3, 1.1], 'cyan', 0, .8); aperture.rotation.y = Math.PI / 2;
    const burst = s.glow([-7, -.3, 1.1], 3, 'white', .7);
    s.animations.push(st => {
      const close = smooth(0, 2.2, st.age), shown = 1 - close;
      aperture.scale.setScalar(.15 + shown * .85 + Math.sin(st.p * 3) * .03 * shown); aperture.visible = shown > .02;
      burst.scale.setScalar(1 + shown * 4); burst.material.opacity = .7 * shown * s.opacity;
    });
  } else if (key === 'local_arrival') {
    const station = s.model('coriolis', [4.6, 0, -1.6], 3.6, {yaw: .45, pitch: .2});
    brackets(s, [4.6, 0, -1.6], 4.4, 4.2, 'state', .8);
    s.animations.push(st => { station.rotation.z = st.p * .1; });
  } else {
    // Interdiction evaded: the tether snapped, the escape vector open ahead.
    const escape = s.ring(1.5, [2.2, -.3, 1.1], 'green', 0, .75, TAU * .8); escape.rotation.y = Math.PI / 2;
    for (let i = 0; i < 6; i++) {
      const piece = s.line([[0, 0, 0], [.5, .15, 0]], 'red', .7);
      s.animations.push(st => { const t = fract(st.p * .25 + i / 6); piece.position.set(-6.5 - t * 4, -.3 + (hash(i) - .5) * 1.5 - t * .3, 1); piece.rotation.z = st.p * (1 + i * .2); piece.material.opacity = .7 * (1 - t) * s.opacity; });
    }
    s.animations.push(st => { escape.rotation.x = st.p * .6; });
  }
  s.animations.push(st => {
    rays.forEach((ray, i) => {
      const v = ray.geometry.attributes.position, a = i * TAU / 14 + st.p * .03, length = 1.12 + wave(st.p * .3 + hash(i)) * .6;
      const [sx, sy, sz] = star.position.toArray();
      v.setXYZ(0, sx + Math.cos(a) * radius * 1.04, sy + Math.sin(a) * radius * 1.04, sz); v.setXYZ(1, sx + Math.cos(a) * radius * length, sy + Math.sin(a) * radius * length, sz);
      v.needsUpdate = true;
    });
    ship.rotation.y = -.2 + Math.sin(st.p * .2) * .06;
  });
}

function cooldown(s) {
  // The drive core venting its heat; it follows the journal's recovery
  // state, never a timed percentage.
  s.stars();
  const drive = new THREE.Group(); s.root.add(drive); drive.rotation.set(.12, -.1, -.08);
  const body = s.mesh(new THREE.CylinderGeometry(.64, .64, 6.4, 16), 'dark', [0, 0, 0], [1, 1, 1], 1, drive); body.rotation.z = Math.PI / 2;
  const fins = [];
  for (let i = 0; i < 9; i++) {
    const x = -2.8 + i * .7;
    const collar = s.mesh(new THREE.CylinderGeometry(.94, .94, .24, 10), 'hull', [x, 0, 0], [1, 1, 1], 1, drive); collar.rotation.z = Math.PI / 2;
    s.outline(collar, 'state', .4);
    for (let j = 0; j < 4; j++) {
      const a = j * TAU / 4 + Math.PI / 4, y = Math.cos(a), z = Math.sin(a);
      const fin = s.mesh(new THREE.BoxGeometry(.36, .12, .55), 'trim', [x, y * .94, z * .94], [1, 1, 1], 1, drive); fin.rotation.x = a;
      fins.push({fin, y, z, i});
    }
  }
  const heat = s.glow([0, 0, 0], 5, 'orange', .3, drive);
  const vents = [];
  for (const side of [-1, 1]) for (let i = 0; i < 14; i++) vents.push({glow: s.glow([0, 0, 0], .4, 'cyan', .3), side, i});
  for (const side of [-1, 1]) {
    s.line([[-4.4, side * 1.6, 0], [-4.9, side * 1.6, 0], [-4.9, side * .8, 0]], 'state', .75);
    s.line([[4.4, side * 1.6, 0], [4.9, side * 1.6, 0], [4.9, side * .8, 0]], 'state', .75);
  }
  for (let i = 0; i < 3; i++) s.circle(1.4 + i * .25, [-3.6 - i * .3, 0, 0], 'state', .25 - i * .06, {tilt: 0}).rotation.y = Math.PI / 2;
  s.animations.push(st => {
    for (const {fin, y, z, i} of fins) { const breath = .5 + .5 * Math.sin(st.p * 1.8 - i * .32); fin.position.y = y * (.98 + breath * .15); fin.position.z = z * (.98 + breath * .15); }
    for (const {glow, side, i} of vents) {
      const travel = fract(st.p * .38 + hash(i + side * 20)), x = -2.6 + (i % 8) * .74;
      glow.position.set(x + travel * .3, side * (1.1 + travel * 1.6), (hash(i + 8) - .5) * 1.2);
      glow.scale.setScalar(.25 + travel * .6); glow.material.opacity = ends(travel) * .3 * s.opacity;
    }
    heat.material.opacity = (.2 + .12 * wave(st.p * .4)) * s.opacity;
    drive.rotation.y = -.1 + Math.sin(st.p * .18) * .12;
  });
}

// ---------------------------------------------------------------------------
// Planets: approach, glide, the surface, pads and settlements.
// ---------------------------------------------------------------------------

function altitudeY(st, low = -.6, high = 1.7) {
  return st.d.altitude >= 0 ? clamp(Math.log10(st.d.altitude + 1) / 2 - .8, low, high) : .1 + Math.sin(st.p * .3) * .15;
}

function descent(s, key) {
  if (key.startsWith('orbital')) {
    s.stars();
    const world = s.planet([1.5, -17.2, -7], 15, 'rock', {spin: .01});
    s.circle(16.6, [1.5, -17.2, -7], 'accent', .35, {tilt: -Math.PI / 2 + .05, dashed: true, segments: 220});
    const leaving = key === 'orbital_departure';
    const ship = hero(s, [-4, 1, 1], 3.4, {pitch: 0, roll: leaving ? .12 : -.12, yaw: -.2});
    wake(s, ship, leaving ? 1.3 : .8);
    const path = s.line(Array.from({length: 30}, (_, i) => { const t = i / 29; return [lerp(-11, 9, t), 1.9 - t * t * 3.2, 1]; }), 'state', .35, s.root, true);
    s.animations.push(st => {
      const y = altitudeY(st, -.4, 1.6);
      ship.position.set(leaving ? -2 + Math.sin(st.p * .2) : -4 + Math.sin(st.p * .2), y, 1);
      ship.rotation.z = leaving ? .14 + Math.sin(st.p * .3) * .03 : -.12 + Math.sin(st.p * .3) * .03;
      path.position.y = y - 1;
      world.rotation.x = st.p * .004;
    });
    return;
  }
  s.terrain(s.seed % 12, {y: -2.1});
  s.planet([8.5, 3.4, -16], 1.3, 'ice', {latitudes: false});
  const glide = key === 'glide', hold = key === 'surface_hold', leaving = key === 'surface_departure';
  const ship = hero(s, [0, 0, .4], 4, {pitch: 0, yaw: -.22});
  if (!hold) wake(s, ship, leaving ? 1.3 : .7);
  const thrusters = [-1, 1].map(side => s.glow([0, -.3, side * .5], .8, 'white', .5, ship));
  if (glide) {
    // Glide: the hull glows where the atmosphere meets it, the ground streams past.
    const flare = s.glow([2.3, 0, .4], 1.4, 'gold', .6);
    for (let i = 0; i < 8; i++) {
      const streak = s.line([[0, 0, 0], [1.6, 0, 0]], 'state', .5);
      s.animations.push(st => { const t = fract(st.p * .5 + i / 8); streak.position.set(12 - t * 26, -1.6 + hash(i) * .5, -1 - hash(i + 3) * 6); streak.material.opacity = ends(t) * .5 * s.opacity; });
    }
    for (const side of [-1, 1]) s.line([[-10, -1.9, side * 2.5], [9, -1.9, side * .3]], 'accent', .35);
    s.animations.push(st => { flare.position.set(ship.position.x + 2.2, ship.position.y - .25, .4); flare.material.opacity = (.35 + .3 * wave(st.p * 1.3)) * s.opacity; });
  }
  const pad = key === 'surface_approach' ? s.circle(1.3, [1, -2.05, .6], 'accent', .8, {dashed: true, segments: 40}) : null;
  const drop = s.strip(2, 'accent', .4);
  s.animations.push(st => {
    const y = glide ? altitudeY(st, -.2, 1.1) : hold ? -.2 + Math.sin(st.p * .8) * .08 : altitudeY(st, -.9, .9);
    ship.position.y = y;
    ship.rotation.z = glide ? -.18 : leaving ? .1 : Math.sin(st.p * .4) * .03;
    for (const glow of thrusters) { glow.visible = !glide; glow.scale.setScalar((.7 + wave(st.p * 2) * .3) / ship.userData.unit); }
    const v = drop.geometry.attributes.position;
    v.setXYZ(0, ship.position.x, y - .3, .4); v.setXYZ(1, ship.position.x, -2, .4); v.needsUpdate = true;
    drop.visible = !glide;
    if (pad) pad.rotation.z = st.p * .4;
  });
}

function pads(s, key) {
  s.terrain(s.seed % 9, {y: -2});
  s.planet([-8.5, 3.2, -15], 1.1, 'ice', {latitudes: false});
  s.shot = {...SHOT, at: [0, -.8, 0]};
  if (key === 'landed') {
    padMarks(s, [0, -1.96, .3], 2.6);
    const ship = hero(s, [0, -1.2, .3], 3.3, {yaw: -.3, bank: 0});
    for (const x of [-1.1, 1.1]) for (const z of [-.4, .9]) s.line([[x, -1.5, z], [x * 1.1, -1.95, z]], 'state', .8);
    const lights = [];
    for (let i = 0; i < 12; i++) { const a = i * TAU / 12; lights.push(s.glow([Math.cos(a) * 2.7, -1.9, .3 + Math.sin(a) * 2.2], .35, 'cyan', .7)); }
    s.animations.push(st => {
      lights.forEach((light, i) => { light.material.opacity = (.25 + .6 * wave(st.p * .5 - i / 12)) * s.opacity; });
      ship.position.y = -1.15 + Math.sin(st.p * .4) * .01;
    });
  } else if (key === 'surface_station') {
    const port = standOn(s.model('surfacePort', [1.5, 0, -2.5], 7, {yaw: .2}), -2);
    const ship = hero(s, [-5, .2, 1], 3, {yaw: -.1}); wake(s, ship, .8);
    const traffic = s.model('ship', [5.5, .6, -4], 1.8, {yaw: .9});
    s.glow([1.5, -1.2, -2], 3, 'cyan', .2);
    s.animations.push(st => { port.rotation.y = .2 + st.p * .01; traffic.position.y = .6 + Math.sin(st.p * .4) * .4; ship.position.x = -5 + Math.sin(st.p * .2) * 1.2; });
  } else {
    const kinds = ['hangar', 'tower', 'dome', 'block', 'dome', 'hangar', 'tower', 'block'];
    kinds.forEach((type, i) => {
      const x = (i - 3.5) * 2.4, z = -2.2 - hash(i) * 2.4;
      const building = s.model('building', [x, 0, z], 1.4 + hash(i) * .9, {type, seed: i, yaw: hash(i + 3) * .6});
      building.position.y = -1.98 + building.userData.height / 2;
    });
    const ship = hero(s, [1.6, .6, 1.4], 3, {yaw: -.3});
    const perimeter = s.circle(9.5, [0, -1.95, -2.6], 'state', .3, {dashed: true, segments: 120});
    const beam = s.strip(2, 'accent', .4);
    s.animations.push(st => {
      ship.position.y = .4 + Math.sin(st.p * .5) * .2;
      const v = beam.geometry.attributes.position; v.setXYZ(0, 1.6, ship.position.y - .3, 1.4); v.setXYZ(1, 1.6, -1.95, 1.4); v.needsUpdate = true;
      perimeter.rotation.z = st.p * .02;
    });
  }
}

// ---------------------------------------------------------------------------
// Stations and carriers: inside, docked, and the approach.
// ---------------------------------------------------------------------------

// The station's interior from inside its turning drum: the far wall built
// up with blocks and lit windows, sliding past as the station spins.
function drum(s, {city = true} = {}) {
  const radius = 14, wall = new THREE.Group(); wall.position.set(0, 0, 6); s.root.add(wall);
  const blocks = [], place = new THREE.Matrix4(), turn = new THREE.Matrix4();
  for (let i = 0; city && i < 64; i++) {
    const a = (hash(i + 11) - .5) * 1.1, x = (hash(i + 12) - .5) * 46, h = .12 + hash(i + 13) ** 3 * .5, r = radius - h / 2;
    const block = new THREE.BoxGeometry(.9 + hash(i + 14) * 2.2, h, .7 + hash(i + 15) * 1.6).toNonIndexed();
    block.applyMatrix4(place.makeTranslation(x, r * Math.sin(a), -r * Math.cos(a)).multiply(turn.makeRotationX(a + Math.PI / 2)));
    blocks.push(block);
  }
  if (city) s.outline(s.mesh(merged(blocks), 'hull', [0, 0, 0], [1, 1, 1], .7, wall, {dim: .5}), 'state', .35);
  const skin = s.mesh(new THREE.CylinderGeometry(radius, radius, 52, 72, 1, true, Math.PI - .85, 1.7), 'ground', [0, 0, 0], [1, 1, 1], 1.6, wall, {side: THREE.DoubleSide});
  skin.rotation.z = Math.PI / 2;
  const lanes = [];
  for (let i = -14; i <= 14; i++) { const a = i * .055; lanes.push([-26, radius * Math.sin(a), -radius * Math.cos(a)], [26, radius * Math.sin(a), -radius * Math.cos(a)]); }
  s.line(lanes, 'state', .12, wall, true);
  for (let x = -24; x <= 24; x += 6) s.circle(radius, [x, 0, 0], 'state', .22, {tilt: 0, arc: 1.8, segments: 30, parent: wall}).rotation.set(0, Math.PI / 2, -.9);
  const windows = new Float32Array(180 * 3);
  for (let i = 0; i < 180; i++) { const a = (hash(i + 40) - .5) * 1.6, r = radius - .05 - hash(i + 41) * 2.2; windows.set([(hash(i + 42) - .5) * 48, r * Math.sin(a), -r * Math.cos(a)], i * 3); }
  const lights = s.points(windows, {tint: 'white', size: .1, opacity: .7, parent: wall});
  s.animations.push(st => { wall.rotation.x = st.p * .015; lights.material.opacity = (.5 + .25 * wave(st.p * .2)) * s.opacity; });
  return wall;
}

function docked(s, key) {
  const place = s.state.d.dockPlace;
  if (key === 'station') {
    // Flying inside the station: in through the slot, along to the pad.
    s.shot = {...SHOT, from: [.2, .26, 1]};
    drum(s);
    padMarks(s, [5.5, -1.9, .5], 1.9);
    const ship = hero(s, [-8, 0, .8], 2.8, {yaw: -.1}); wake(s, ship, .9);
    const lights = [];
    for (let i = 0; i < 6; i++) lights.push(s.glow([5.5 + Math.cos(i * TAU / 6) * 1.9, -1.85, .5 + Math.sin(i * TAU / 6) * 1.5], .3, 'cyan', .7));
    s.animations.push(st => {
      const t = fract(st.p * .06);
      ship.position.set(lerp(-10, 5.5, smooth(0, 1, t)), lerp(.2, -1.3, smooth(.55, 1, t)), .6);
      ship.rotation.y = lerp(-.1, -.5, smooth(.6, 1, t));
      lights.forEach((light, i) => { light.material.opacity = (.3 + .5 * wave(st.p * .5 - i / 6)) * s.opacity; });
    });
    return;
  }
  if (place === 'carrier') {
    s.stars();
    const fleet = s.model('carrier', [0, -.6, -1.5], 15, {yaw: .12});
    const ship = hero(s, [deckX(fleet, .45), deckY(fleet) + .45, -1.2], 2.4, {yaw: .5, bank: 0});
    s.animations.push(st => { fleet.position.y = -.6 + Math.sin(st.p * .2) * .04; ship.position.y = deckY(fleet) + .45; });
    return;
  }
  if (place === 'surface') {
    s.terrain(5, {y: -2});
    s.shot = {...SHOT, at: [0, -.6, 0]};
    standOn(s.model('surfacePort', [-2.5, 0, -3], 8, {yaw: .1}), -2);
    padMarks(s, [3.4, -1.96, -.6], 2);
    hero(s, [3.4, -1.25, -.6], 3, {yaw: .4, bank: 0});
    return;
  }
  if (place === 'outpost') {
    s.stars();
    s.planet([8, -.5, -9], 2.8, 'rock');
    const kinds = ['hangar', 'tower', 'hangar'];
    kinds.forEach((type, i) => s.model('building', [-7 + i * 3.4, -.6 + (type === 'tower' ? .5 : 0), -2], 3, {type, seed: i, yaw: .2}));
    s.shot = {...SHOT, at: [0, -.5, 0]};
    s.line([[-9, -1.3, -1.6], [3, -1.3, -1.6]], 'state', .6);
    padMarks(s, [1.6, -1.35, .9], 2);
    hero(s, [1.6, -.75, .9], 2.8, {yaw: .4, bank: 0});
    return;
  }
  drum(s, {city: false});
  s.shot = {...SHOT, at: [0, -.6, 0]};
  // The bay: floor, back wall and its frame, beams overhead.
  s.mesh(new THREE.BoxGeometry(12, .1, 7), 'ground', [0, -2.02, -.2]);
  const floor = [];
  for (let i = -6; i <= 6; i++) floor.push([i, -1.96, -3.7], [i, -1.96, 3.3]);
  for (let j = 0; j <= 7; j++) floor.push([-6, -1.96, -3.7 + j], [6, -1.96, -3.7 + j]);
  s.line(floor, 'state', .16, s.root, true);
  for (const side of [-1, 1]) {
    s.outline(s.mesh(new THREE.BoxGeometry(.3, 4.4, .3), 'alloy', [side * 6, .1, -3.7]));
    s.outline(s.mesh(new THREE.BoxGeometry(.25, .25, 7), 'alloy', [side * 6, 2.2, -.2]));
    s.mesh(new THREE.PlaneGeometry(7, 4.2), 'panel', [side * 6, .1, -.2], [1, 1, 1], 1, s.root, {side: THREE.DoubleSide}).rotation.y = Math.PI / 2;
  }
  s.line([[-6, 2.3, -3.7], [6, 2.3, -3.7]], 'state', .6);
  padMarks(s, [0, -1.94, .3], 2.5);
  hero(s, [0, -1.2, .3], 3.4, {yaw: .45, bank: 0});
  const lights = [];
  for (let i = 0; i < 10; i++) lights.push(s.glow([Math.cos(i * TAU / 10) * 2.6, -1.9, .3 + Math.sin(i * TAU / 10) * 2.1], .3, 'cyan', .7));
  s.animations.push(st => {
    lights.forEach((light, i) => { light.material.opacity = (.25 + .5 * wave(st.p * .4 - i / 10)) * s.opacity; });
  });
}

function approach(s, key) {
  s.stars();
  const denied = key === 'docking_denied', lapsed = key === 'docking_cancelled' || key === 'docking_timeout';
  const cleared = /clearance|assist/.test(key), turning = denied || lapsed;
  const signal = denied || key === 'docking_timeout' ? 'red' : cleared ? 'green' : 'state';
  const station = s.model('coriolis', [6.8, 0, -3.6], 4.8, {yaw: -.8, lamps: {slot: signal}});
  const mouth = [6.8 - 1.2, 0, -3.6 + 1.2];
  const slot = s.glow(mouth, 1.5, signal === 'state' ? 'orange' : signal, .7);
  s.circle(6.4, [6.8, 0, -3.6], denied ? 'red' : 'state', .3, {tilt: -Math.PI / 2 + .2, dashed: true, segments: 140});
  // Traffic queues in from the left for the slot.
  for (let i = 0; i < 4; i++) {
    const ship = s.model('ship', [-12, 0, 0], 1.5 + hash(i) * .5, {type: i === 2 ? 'taxi' : undefined, yaw: -.1});
    wake(s, ship, .5);
    s.animations.push(st => {
      const t = fract(st.p * .07 + i / 4);
      ship.position.set(lerp(-12, mouth[0], t), (hash(i + 5) - .5) * 1.4 * (1 - t), lerp(-1.5 - hash(i + 1) * 2, mouth[2], t));
      ship.scale.setScalar(ship.userData.unit * smooth(0, .08, t) * (1 - smooth(.9, 1, t)));
    });
  }
  const ship = hero(s, [-2.2, -.45, 1.2], 2.9, {yaw: -.12});
  wake(s, ship, .8);
  if (cleared || lapsed) {
    const corridor = [], lane = key === 'docking_assist' ? 'accent' : key === 'docking_timeout' ? 'red' : lapsed ? 'state' : 'green';
    for (let i = 0; i < 6; i++) {
      const u = (i + 1) / 7, ring = s.circle(.75 - i * .06, [lerp(-.4, mouth[0], u), lerp(-.45, 0, u), lerp(1.2, mouth[2], u)], lane, .75, {tilt: 0});
      ring.rotation.y = Math.PI / 2; corridor.push(ring);
    }
    if (key === 'docking_assist') brackets(s, [-2.2, -.45, 1.2], 3.6, 1.8, 'accent', .85);
    s.animations.push(st => corridor.forEach((ring, i) => {
      const level = key === 'docking_cancelled' ? .12 + .08 * wave(st.p * .3) : key === 'docking_timeout' ? (Math.sin(st.p * 3) > 0 ? .7 : .12) : .25 + .6 * wave(st.p * .6 - i / 6);
      ring.material.opacity = level * s.opacity;
    }));
  }
  if (denied) {
    const barrier = new THREE.Group(); barrier.position.set(...mouth); barrier.rotation.y = -.8; s.root.add(barrier);
    for (let i = -3; i <= 3; i++) s.line([[i * .25 - .5, -.9, 0], [i * .25 + .5, .9, 0]], 'red', .7, barrier);
    s.line([[-.9, -.9, .1], [.9, .9, .1]], 'red', .95, barrier); s.line([[-.9, .9, .1], [.9, -.9, .1]], 'red', .95, barrier);
    s.animations.push(st => { barrier.scale.setScalar(.92 + wave(st.p * .8) * .1); });
  }
  if (turning) s.animations.push(st => { ship.rotation.y = -.12 - smooth(0, 1, Math.sin(st.p * .3) * .5 + .5) * .5; });
  s.animations.push(st => {
    station.rotation.z = st.p * .08;
    slot.material.opacity = (.35 + .4 * wave(st.p * .5)) * s.opacity;
    if (!turning) ship.position.x = -2.2 + Math.sin(st.p * .25) * .8;
  });
}

// The carrier's flight deck in world units (its pads sit at model y -0.73).
const deckY = (fleet) => fleet.position.y + (.73 - fleet.userData.modelCentre.y) * fleet.userData.unit;
const deckX = (fleet, x) => fleet.position.x + (x - fleet.userData.modelCentre.x) * fleet.userData.unit;

function carrier(s, key) {
  s.stars();
  const lockdown = key === 'carrier_lockdown', deck = key === 'carrier_deck';
  if (deck) s.shot = {...SHOT, at: [0, .4, 0], width: 13, height: 3.6, from: [.3, .5, 1]};
  const fleet = s.model('carrier', [0, -.4, -1.5], deck ? 15 : 13, {yaw: .1, lamps: lockdown ? {window: 'red'} : {}});
  const pads = Array.from({length: 8}, (_, i) => s.lamp(fleet, `pad${i}`));
  if (deck) {
    s.shot = {...SHOT, at: [deckX(fleet, .45), deckY(fleet) + .3, -1.2], width: 13, height: 3.4, from: [.3, .5, 1]};
    hero(s, [deckX(fleet, .45), deckY(fleet) + .4, -1.2], 2.2, {yaw: .5, bank: 0});
  }
  if (key === 'carrier_vicinity') {
    const ship = hero(s, [-9, .8, 2], 2.2, {yaw: -.1}); wake(s, ship, .6);
    s.animations.push(st => { const t = fract(st.p * .05); ship.position.set(lerp(-11, deckX(fleet, .45), t), lerp(1.2, deckY(fleet) + .6, t), lerp(2, -1.2, t)); });
  }
  if (key === 'carrier_preparing' || key === 'carrier_arrival') {
    // The jump drive spooling at the stern, or the flash it arrives from.
    const stern = new THREE.Group(); stern.position.set(-7.5, -.4, -1.5); s.root.add(stern);
    const spool = [0, 1, 2].map(i => { const r = s.ring(1.8 + i * .4, [0, 0, 0], 'cyan', 0, .6, TAU * .7, stern); r.rotation.y = Math.PI / 2; return r; });
    const flare = s.glow([-7.5, -.4, -1.5], 4, 'cyan', .45);
    s.animations.push(st => {
      spool.forEach((ring, i) => { ring.rotation.x = st.p * (.8 + i * .4) * (i % 2 ? -1 : 1); });
      if (key === 'carrier_arrival') {
        const emerge = smooth(0, 2.6, st.age);
        flare.scale.setScalar(4 + (1 - emerge) * 10); flare.material.opacity = (.3 + .6 * (1 - emerge)) * s.opacity;
        fleet.position.x = lerp(-6, 0, emerge); stern.visible = emerge < .98;
      } else flare.material.opacity = (.25 + .35 * wave(st.p * .5)) * s.opacity;
    });
  }
  if (lockdown) {
    for (let i = 0; i < 4; i++) {
      const beacon = s.glow([-5 + i * 3.3, .9, -1], .8, 'red', .8);
      s.animations.push(st => { beacon.material.opacity = (Math.sin(st.p * 4 + i * 1.6) > .3 ? .9 : .1) * s.opacity; });
    }
    for (let i = 0; i < 2; i++) {
      const ship = s.model('ship', [0, 0, 0], 1.4, {yaw: Math.PI * .9}); wake(s, ship, .4);
      s.animations.push(st => { const t = fract(st.p * .08 + i / 2); ship.position.set(lerp(1, -12, t), .9 + t * .6, -.5 + i); });
    }
  }
  s.animations.push(st => {
    pads.forEach((pad, i) => { if (pad) pad.uniforms.uLamp.value = lockdown ? .2 : .25 + .75 * wave(st.p * .3 - i / 8); });
    fleet.rotation.y = .1 + Math.sin(st.p * .08) * .03;
  });
}

// ---------------------------------------------------------------------------
// Maps, scanners and targets.
// ---------------------------------------------------------------------------

function galaxy(s, key) {
  const power = key === 'power_map', count = 900;
  const positions = new Float32Array(count * 3), colors = new Float32Array(count * 3);
  const tone = s.tone(power ? 'accent' : 'state'), core = s.tone('gold');
  for (let i = 0; i < count; i++) {
    const inner = i < 180, arm = i % 4, r = Math.pow(hash(i + 500), .8);
    const reach = inner ? Math.pow(hash(i + 503), 1.7) * 2.2 : 1.2 + r * 8.6;
    const angle = inner ? hash(i + 501) * TAU : arm * Math.PI / 2 + reach * .52 + (hash(i + 502) - .5) * .5 * (1 - r * .4);
    positions.set([Math.cos(angle) * reach, (hash(i + 504) - .5) * (inner ? .5 : .18), Math.sin(angle) * reach], i * 3);
    const mix = tone.clone().lerp(core, inner ? .7 : (1 - r) * .4), bright = .35 + hash(i + 505) * .65;
    colors.set([mix.r * bright, mix.g * bright, mix.b * bright], i * 3);
  }
  const disc = new THREE.Group(); disc.rotation.set(.12, 0, -.05); s.root.add(disc);
  s.points(positions, {colors, size: .2, opacity: .95, parent: disc});
  for (let arm = 0; arm < 4; arm++) {
    const spine = [];
    for (let j = 0; j <= 70; j++) { const reach = 1.2 + j / 70 * 8.6, angle = arm * Math.PI / 2 + reach * .52; spine.push([Math.cos(angle) * reach, 0, Math.sin(angle) * reach]); }
    s.line(spine, power ? 'accent' : 'state', .4, disc);
  }
  s.glow([0, 0, 0], 3.2, 'gold', .4, disc); s.glow([0, 0, 0], 1.2, 'white', .5, disc);
  s.circle(9.8, [0, 0, 0], 'state', .18, {parent: disc, segments: 140});
  s.circle(5.2, [0, 0, 0], 'state', .12, {parent: disc, segments: 100, dashed: true});
  s.shot = {...SHOT, from: [.04, .5, 1], width: 21, height: 4.6};
  // You are here: the Orion Spur, marked, not charted.
  const here = new THREE.Group(); here.position.set(Math.cos(2.1) * 6.1, 0, Math.sin(2.1) * 6.1); disc.add(here);
  s.circle(.35, [0, 0, 0], 'accent', .95, {parent: here, segments: 24});
  s.line([[0, 0, 0], [0, 1.4, 0]], 'accent', .7, here);
  if (power) {
    for (let i = 0; i < 7; i++) {
      const a = hash(i + 40) * TAU, r = 1.5 + hash(i + 41) * 7;
      const bubble = s.circle(.5 + hash(i + 42) * .7, [Math.cos(a) * r, .05, Math.sin(a) * r], i % 2 ? 'red' : 'accent', .75, {parent: disc, segments: 32});
      s.animations.push(st => bubble.scale.setScalar(1 + wave(st.p * .3 + i * .2) * .25));
    }
  }
  s.animations.push(st => { disc.rotation.y = st.p * (key === 'map' ? .04 : .02); here.children[1].material.opacity = (.4 + .5 * wave(st.p * .6)) * s.opacity; });
}

function systemMap(s) {
  // The system map's own layout: the star, then each body along one line,
  // moons hanging beneath, a selection bracket stepping between them.
  s.shot = {...SHOT, from: [.08, .14, 1]};
  s.star([-8.6, 0, 0], 1.25);
  s.line([[-7, 0, 0], [10.5, 0, 0]], 'state', .35);
  const bodies = [[-5.2, .32], [-2.3, .5], [1.2, .85], [5, .62], [8.4, .4]];
  const globes = bodies.map(([x, r], i) => {
    const globe = s.planet([x, 0, 0], r, i % 2 ? 'ice' : 'rock', {latitudes: i === 2});
    if (i === 2) s.circle(r * 1.8, [x, 0, 0], 'state', .6, {tilt: -1.3});
    const moons = Math.floor(hash(i + 70) * 3) + (i === 2 ? 2 : 0);
    if (moons) s.line([[x, -r - .15, 0], [x, -r - .2 - moons * .5, 0]], 'state', .3);
    for (let m = 0; m < moons; m++) s.planet([x, -r - .55 - m * .5, 0], .13 + hash(i * 3 + m) * .07, 'rock', {atmosphere: false, latitudes: false});
    return globe;
  });
  const pick = brackets(s, [0, 0, 0], 1.4, 1.4, 'accent', .9);
  s.animations.push(st => {
    const step = Math.floor(st.p * .25) % bodies.length, [x, r] = bodies[step];
    pick.position.set(x, 0, .1); pick.scale.setScalar(r * 1.9 + Math.sin(st.p * 2) * .05);
  });
  return globes;
}

function orrery(s) {
  s.shot = {...SHOT, from: [.18, .62, 1]};
  s.star([0, 0, 0], .95);
  for (let i = 0; i < 5; i++) {
    const r = 2.1 + i * 1.9;
    s.circle(r, [0, 0, 0], i % 2 ? 'accent' : 'state', .35, {segments: 140});
    const world = s.planet([r, 0, 0], .24 + (i % 3) * .14, i % 2 ? 'ice' : 'rock', {latitudes: false});
    const trail = s.circle(r, [0, 0, 0], 'state', .7, {arc: .5, segments: 16});
    s.animations.push(st => {
      const a = i * 1.7 + st.p * (.16 - i * .022);
      world.position.set(Math.cos(a) * r, 0, -Math.sin(a) * r); trail.rotation.z = a - .5;
    });
  }
}

function codex(s) {
  s.stars();
  const relic = s.model('thargoid', [0, 0, -.5], 3.4, {yaw: 0, pitch: -.5, lamps: {core: 'accent'}});
  for (let i = 0; i < 3; i++) {
    const ring = s.circle(2 + i * .35, [0, 0, -.5], i ? 'state' : 'accent', .45, {tilt: -1.1 + i * .35, arc: TAU * .82});
    s.animations.push(st => { ring.rotation.z = st.p * (.2 + i * .1) * (i % 2 ? -1 : 1); });
  }
  for (let i = 0; i < 5; i++) {
    const row = s.line([[-10, 1.4 - i * .62, 0], [-10 + 3 + hash(i) * 2.6, 1.4 - i * .62, 0]], 'state', .7);
    s.animations.push(st => { row.scale.x = .3 + .7 * smooth(0, 1, fract(st.p * .2 - i * .12) * 3); });
  }
  const signal = s.strip(60, 'accent', .8), v = signal.geometry.attributes.position;
  s.animations.push(st => {
    for (let i = 0; i < 60; i++) { const x = 4 + i * .11; v.setXYZ(i, x, Math.sin(x * 3 - st.p * 2) * Math.sin(i * .21 + st.p) * .9, 0); }
    v.needsUpdate = true;
    relic.rotation.z = st.p * .25;
  });
}

function phenomena(s) {
  s.stars();
  const cloud = new Float32Array(260 * 3);
  for (let i = 0; i < 260; i++) cloud.set([(hash(i) - .5) * 22, (hash(i + 1) - .5) * 4.4, -1 - hash(i + 2) * 7], i * 3);
  const mist = s.points(cloud, {tint: 'accent', size: .12, opacity: .5});
  for (let i = 0; i < 9; i++) {
    const crystal = s.model('crystal', [(i - 4) * 2.3, Math.sin(i * 1.7) * .9, -hash(i) * 3], 1 + hash(i) * 1.1,
      {yaw: hash(i + 5) * TAU, pitch: hash(i + 6), lamps: {hull: i % 3 ? 'state' : 'accent'}});
    s.animations.push(st => { crystal.rotation.y = st.p * (.1 + hash(i) * .1) + i; crystal.position.y = Math.sin(i * 1.7) * .9 + Math.sin(st.p * .3 + i) * .12; });
  }
  s.animations.push(st => { mist.rotation.y = Math.sin(st.p * .05) * .05; mist.position.x = Math.sin(st.p * .07) * .6; });
}

function fss(s) {
  // The Full Spectrum Scanner: signal peaks along the band, resolved as far
  // as the journal's scan progress, the next body brought into focus.
  s.shot = {...SHOT, from: [.1, .14, 1]};
  const scan = clamp(s.state.d.scan), left = -10.4, right = 1.6;
  const peaks = (x) => { let h = 0; for (let j = 0; j < 6; j++) h += Math.exp(-(((x - (left + 1.4 + j * 1.9)) / (.18 + j * .03)) ** 2)) * (1.7 - hash(j) * .8); return h; };
  const done = [], open = [];
  for (let i = 0; i <= 150; i++) { const x = left + i * (right - left) / 150, point = [x, -1.6 + peaks(x), 0]; (x - left) / (right - left) <= scan ? done.push(point) : open.push(point); }
  if (done.length > 1) s.line(done, 'state', .95);
  if (open.length > 1) s.line(open, 'state', .25);
  for (let j = 0; j < 4; j++) s.line([[left, -1.6 + j * .75, -.1], [right, -1.6 + j * .75, -.1]], 'accent', .12);
  s.line([[left, -1.75, 0], [lerp(left, right, scan), -1.75, 0]], 'accent', .9);
  const cursor = s.line([[0, -1.7, .1], [0, 1.7, .1]], 'accent', .9);
  const band = s.mesh(new THREE.PlaneGeometry(.5, 3.4), 'panel', [0, 0, -.05], [1, 1, 1], 1, s.root, {tint: 'accent', side: THREE.DoubleSide});
  const world = s.planet([6.6, 0, -.6], 1.9, 'ice');
  const focus = s.circle(2.6 - scan * .4, [6.6, 0, -.6], 'accent', .85, {tilt: 0, segments: 72});
  for (const a of [0, Math.PI / 2, Math.PI, Math.PI * 1.5]) s.line([[6.6 + Math.cos(a) * 2.9, Math.sin(a) * 2.9, -.6], [6.6 + Math.cos(a) * 2.4, Math.sin(a) * 2.4, -.6]], 'accent', .8);
  s.animations.push(st => {
    const x = lerp(left, right, .5 + Math.sin(st.p * .42) * .45);
    cursor.position.x = x; band.position.x = x;
    focus.rotation.z = st.p * .3; world.rotation.y = st.p * .05;
  });
}

function dss(s) {
  // The Detailed Surface Scanner: probes arc onto a turning world and each
  // mapped patch glows. Counts come from the journal's DSS label.
  s.stars();
  const probes = /(\d+)\s*\/\s*(\d+)/.exec(s.state.label);
  const used = probes ? Math.min(16, Number(probes[1])) : 0, goal = probes ? Math.min(16, Number(probes[2])) : 0;
  const world = s.planet([5, 0, -1], 2.5, 'rock', {spin: .08});
  const sphere = world.userData.sphere;
  for (let i = 0; i < (probes ? used : 4); i++) {
    const lat = (hash(i + 30) - .5) * 1.8, lon = i * TAU / Math.max(1, probes ? used : 4);
    const at = new THREE.Vector3(Math.cos(lat) * Math.cos(lon), Math.sin(lat), Math.cos(lat) * Math.sin(lon)).multiplyScalar(2.52);
    const patch = s.circle(.32, [0, 0, 0], 'accent', .85, {parent: sphere, segments: 24});
    patch.position.copy(at); patch.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), at.clone().normalize());
    s.glow(at.toArray(), .9, 'cyan', .5, sphere);
  }
  const ship = hero(s, [-7.2, -.5, 1.2], 3, {yaw: -.1});
  wake(s, ship, .5);
  const flights = [0, 1, 2].map(i => ({probe: s.mesh(new THREE.OctahedronGeometry(.11), 'white'), trail: s.strip(10, 'accent', .5), i}));
  s.animations.push(st => {
    for (const {probe, trail, i} of flights) {
      const t = fract(st.p * .2 + i / 3), target = [5 - 2.2 + i * .3, (i - 1) * .9, .2];
      const point = (u) => [lerp(-5.8, target[0], u), lerp(-.4, target[1], u) + Math.sin(u * Math.PI) * (1.2 + i * .4), lerp(1.2, target[2], u)];
      probe.position.set(...point(t)); probe.rotation.y = st.p * 3;
      const v = trail.geometry.attributes.position;
      for (let j = 0; j < 10; j++) v.setXYZ(j, ...point(Math.max(0, t - j * .025)));
      v.needsUpdate = true; trail.material.opacity = .5 * ends(t) * s.opacity; probe.visible = t < .97;
    }
  });
  if (probes) pips(s, Math.max(used, goal), {lit: used, warn: goal});
}

function exploration(s) {
  s.stars();
  const world = s.planet([4.4, 0, -2.2], 2.4, 'rock');
  s.planet([8.8, .9, -7], .7, 'ice', {latitudes: false});
  s.circle(4.4, [4.4, 0, -2.2], 'state', .25, {tilt: -1.3});
  const ship = hero(s, [-5.6, -.4, 1.3], 3.4, {yaw: -.2}); wake(s, ship, .8);
  const sweep = s.mesh(new THREE.PlaneGeometry(.06, 5.4), 'lamp', [4.4, 0, -2.2], [1, 1, 1], .8, s.root, {tint: 'accent', side: THREE.DoubleSide});
  const finds = [];
  for (let i = 0; i < 9; i++) {
    const a = hash(i + 9) * TAU, y = (hash(i + 16) - .5) * 3.6, r = Math.sqrt(Math.max(0, 2.5 ** 2 - y * y));
    finds.push(s.glow([Math.cos(a) * r, y, Math.sin(a) * r], .45, 'gold', .8, world.userData.sphere));
  }
  s.line([[-3.4, -.3, 1.1], [1.8, -.1, -1.4]], 'accent', .35, s.root, false);
  s.animations.push(st => {
    sweep.position.x = 4.4 + Math.sin(st.p * .32) * 2.4;
    finds.forEach((find, i) => { find.material.opacity = (.3 + .6 * wave(st.p * .3 + hash(i))) * s.opacity; });
  });
}

function target(s, key) {
  s.stars();
  const at = [3, 0, -.4];
  // Data rows down the left, as the target panel lays them out.
  for (let i = 0; i < 4; i++) s.line([[-10, 1.2 - i * .7, 0], [-10 + 2.2 + hash(i + 2) * 2.4, 1.2 - i * .7, 0]], 'state', .55);
  s.line([[-5, 0, 0], [at[0] - 2.6, 0, at[2]]], 'state', .3, s.root, false);
  const lock = brackets(s, at, 5.2, 4, key === 'target_clear' ? 'state' : 'accent', key === 'target_clear' ? .35 : .9);
  const reticle = s.circle(1.9, at, 'accent', .6, {tilt: 0, arc: TAU * .7, segments: 60});
  if (key === 'target_system') s.star(at, 1.3, s.state.targetFamily, s.state.targetTone);
  else if (key === 'target_body') { s.planet(at, 1.6, 'ice'); s.circle(2.3, at, 'state', .5, {tilt: -1.2}); }
  else if (key === 'target_signal') {
    const beacon = s.model('beacon', at, 2.6, {yaw: .4});
    for (let i = 0; i < 2; i++) { const pulse = s.circle(1, at, 'accent', .6, {tilt: -1.2}); s.animations.push(st => { const t = fract(st.p * .4 + i / 2); pulse.scale.setScalar(.5 + t * 2.4); pulse.material.opacity = .6 * (1 - t) * s.opacity; }); }
    s.animations.push(st => { beacon.rotation.y = st.p * .3; });
  } else if (key === 'target_lock') {
    const ship = s.model('ship', at, 4.2, {type: 'interdictor', yaw: .6});
    s.animations.push(st => { ship.rotation.y = .6 + st.p * .25; });
  }
  s.animations.push(st => {
    reticle.rotation.z = st.p * (key === 'target_clear' ? .1 : .6);
    lock.scale.setScalar(key === 'target_clear' ? 1 + smooth(0, 1.6, st.age) * .3 : 1 + Math.sin(st.p * 1.4) * .03);
    if (key === 'target_clear') lock.children.forEach(line => { line.material.opacity = .4 * (1 - smooth(0, 2, st.age) * .6) * s.opacity; });
  });
}

// ---------------------------------------------------------------------------
// Rings, signals, contacts and fights.
// ---------------------------------------------------------------------------

function asteroids(s) {
  s.stars();
  const rocks = [];
  for (let i = 0; i < 22; i++) {
    const depth = hash(i + 60), size = .5 + hash(i) * 1.1 + depth * .9;
    const rock = s.model('rock', [0, 0, 0], size, {seed: i % 12, yaw: hash(i + 2) * TAU, edge: .7});
    rocks.push({rock, i, unit: rock.userData.unit, span: 34 + depth * 24, y: (hash(i + 9) - .5) * 3.2 - depth * 1.6, z: -1 - depth * 9});
  }
  s.line([[-16, -1.4, -6], [16, -1, -6]], 'gold', .2);
  const dust = new Float32Array(120 * 3);
  for (let i = 0; i < 120; i++) dust.set([(hash(i) - .5) * 30, (hash(i + 1) - .5) * .9 - 1.2, -2 - hash(i + 2) * 8], i * 3);
  const ring = s.points(dust, {tint: 'gold', size: .07, opacity: .55});
  const ship = hero(s, [-5.2, -.3, 1.4], 3.2, {yaw: -.15});
  const laser = s.strip(2, 'gold', .9), target = new THREE.Vector3(.6, -.3, -.2);
  const hit = s.glow(target.toArray(), 1.1, 'gold', .8);
  const chunk = s.model('rock', target.toArray(), 1.4, {seed: 3, edge: .8});
  const limpet = s.model('limpet', [0, 0, 1.4], .5);
  const sparks = [];
  for (let i = 0; i < 6; i++) sparks.push(s.glow(target.toArray(), .18, 'white', .8));
  s.animations.push(st => {
    for (const {rock, i, unit, span, y, z} of rocks) {
      const u = fract(hash(i + 5) - st.p * 2 / span);
      rock.position.set((u - .5) * span, y + Math.sin(st.p * .2 + i) * .1, z);
      rock.scale.setScalar(unit * smooth(0, .05, u) * (1 - smooth(.95, 1, u)));
      rock.rotation.x = st.p * .03 + i; rock.rotation.y = st.p * .05 + i * .7;
    }
    ring.position.x = -fract(st.p * .01) * 3;
    chunk.rotation.x = st.p * .05; chunk.rotation.y = st.p * .08;
    const firing = fract(st.p * .18) < .7;
    const v = laser.geometry.attributes.position;
    v.setXYZ(0, -3.5, -.35, 1.45); v.setXYZ(1, target.x, target.y, target.z); v.needsUpdate = true;
    laser.visible = hit.visible = firing;
    hit.scale.setScalar(.8 + Math.sin(st.p * 13) * .25);
    sparks.forEach((spark, i) => {
      const t = fract(st.p * .9 + i / 6), a = hash(i + Math.floor(st.p * .9)) * TAU;
      spark.position.set(target.x + Math.cos(a) * t * 1.3, target.y + Math.sin(a) * t * .9, target.z + .4);
      spark.visible = firing; spark.material.opacity = (1 - t) * .8 * s.opacity;
    });
    limpet.position.set(-1.5 + Math.sin(st.p * .6) * 2.2, .9 + Math.cos(st.p * .6) * .4, 1);
    limpet.rotation.z = st.p;
    ship.rotation.y = -.15 + Math.sin(st.p * .15) * .04;
  });
}

function lock(s, key) {
  s.stars();
  if (key === 'unknown_contact') {
    // Something not human: interference across the whole scanner.
    for (let i = 0; i < 7; i++) {
      const line = s.strip(48, 'green', .3), v = line.geometry.attributes.position;
      s.animations.push(st => { for (let j = 0; j < 48; j++) { const x = -12 + j * .5; v.setXYZ(j, x, -2 + i * .66 + Math.sin(x * .7 + st.p * (1 + i * .2) + i) * .18, -1); } v.needsUpdate = true; line.material.opacity = (.1 + .25 * wave(st.p * .35 + i * .3)) * s.opacity; });
    }
    const alien = s.model('thargoid', [1.5, 0, -.3], 4.6, {yaw: 0, pitch: -.4, lamps: {core: 'green'}});
    const heart = s.glow([1.5, 0, 0], 3, 'green', .45);
    s.animations.push(st => { alien.rotation.z = st.p * .12; alien.rotation.x = -.4 + Math.sin(st.p * .07) * .15; heart.material.opacity = (.3 + .25 * wave(st.p * .5)) * s.opacity; });
    return;
  }
  if (key === 'capital_contact') {
    const capital = s.model('capital', [2, .2, -2.2], 14, {yaw: -.12});
    brackets(s, [2, .2, -2.2], 15, 4.2, 'state', .6);
    const ship = hero(s, [-6.5, -1.1, 2], 1.8, {yaw: -.2}); wake(s, ship, .5);
    const lights = s.lamp(capital, 'window');
    s.animations.push(st => { capital.position.x = 2 + Math.sin(st.p * .05) * .8; if (lights) lights.uniforms.uLamp.value = .3 + .7 * wave(st.p * .3) ** 3; });
    return;
  }
  if (key === 'phenomena') return phenomena(s);
  const drop = key === 'signal_drop', mass = key === 'mass_lock';
  const centre = mass ? [6.4, 0, -3] : [3.2, 0, -.6];
  if (mass) {
    const station = s.model('coriolis', centre, 5.2, {yaw: .9, pitch: .2});
    s.animations.push(st => { station.rotation.x = st.p * .05; });
  } else {
    const beacon = s.model('beacon', centre, 2.8, {yaw: .3});
    for (let i = 0; i < 7; i++) {
      const piece = i % 2 ? s.model('rock', [0, 0, 0], .5 + hash(i) * .5, {seed: i}) : s.model('canister', [0, 0, 0], .6, {yaw: i});
      s.animations.push(st => { const a = i * TAU / 7 + st.p * .04, r = 2.6 + hash(i + 3) * 3.4; piece.position.set(centre[0] + Math.cos(a) * r, Math.sin(a * 2) * .5, centre[2] + Math.sin(a) * r * .6); piece.rotation.set(st.p * .3 + i, st.p * .2, 0); });
    }
    for (let i = 0; i < 3; i++) {
      const pulse = s.circle(1, centre, 'accent', .5, {tilt: -1.25});
      s.animations.push(st => { const t = fract(st.p * .25 + i / 3); pulse.scale.setScalar(1 + t * 7); pulse.material.opacity = .45 * (1 - t) * (drop ? smooth(0, 2, st.age) : 1) * s.opacity; });
    }
    s.animations.push(st => { beacon.rotation.y = .3 + st.p * .2; });
  }
  const ship = hero(s, [-5.4, -.3, 1.2], 3.6, {yaw: -.2});
  wake(s, ship, drop ? .6 : .9);
  if (mass) {
    const field = s.mesh(new THREE.SphereGeometry(1, 24, 12), 'shell', [-5.4, -.3, 1.2], [2.6, 1.1, 1.6], 1, s.root, {tint: 'red'});
    s.outline(field, 'red', .3, 1);
    s.line([[-3, -.2, 1], [centre[0] - 2.8, 0, centre[2]]], 'red', .45, s.root, false);
    s.animations.push(st => { field.rotation.y = st.p * .2; field.scale.set(2.6 + Math.sin(st.p * 1.4) * .08, 1.1, 1.6); });
  }
  if (drop) {
    for (let i = 0; i < 16; i++) {
      const streak = s.line([[0, 0, 0], [2.4, 0, 0]], 'accent', .5);
      s.animations.push(st => { const fade = 1 - smooth(0, 2.2, st.age), t = fract(st.p * .7 + hash(i)); streak.position.set(12 - t * 26, (hash(i + 4) - .5) * 4, -2 - hash(i + 2) * 5); streak.material.opacity = .5 * fade * ends(t) * s.opacity; });
    }
  }
  s.animations.push(st => { ship.rotation.y = -.2 + Math.sin(st.p * .2) * .06; });
}

function fight(s, key) {
  if (key !== 'interdiction' && key !== 'interdicted') s.stars();
  if (key === 'interdiction' || key === 'interdicted') {
    // The interdictor behind, its tether writhing to the ship, the escape
    // vector ahead. Interdicted, the tether has won and the ship tumbles.
    const lost = key === 'interdicted';
    s.stars({streak: true, speed: lost ? .3 : 1.2});
    const hunter = s.model('ship', [-7.6, .2, .4], 3.6, {type: 'interdictor', tint: 'red', yaw: -.2});
    wake(s, hunter, 1, 'red');
    const ship = hero(s, [.5, 0, .8], 3.6, {yaw: -.2}); wake(s, ship, lost ? .3 : 1.1);
    const tether = s.strip(40, 'red', .8), v = tether.geometry.attributes.position;
    const escape = s.ring(1.2, [6.2, 0, .5], lost ? 'red' : 'cyan', 0, .8, TAU * .8); escape.rotation.y = Math.PI / 2;
    const sparks = [];
    if (lost) for (let i = 0; i < 8; i++) sparks.push(s.glow([0, 0, 0], .25, 'gold', .9));
    s.animations.push(st => {
      if (lost) { ship.rotation.set(st.p * .9, -.2 + st.p * .5, st.p * 1.3); }
      else { ship.position.set(.5 + Math.sin(st.p * .6) * .9, Math.sin(st.p * .9) * .45, .8); ship.rotation.z = Math.sin(st.p * .9) * .35; }
      for (let i = 0; i < 40; i++) {
        const u = i / 39, slack = lost ? .6 : 1;
        v.setXYZ(i, lerp(-5.8, ship.position.x - 1.6, u), lerp(.2, ship.position.y, u) + Math.sin(u * 13 - st.p * 5) * .35 * Math.sin(u * Math.PI) * slack, lerp(.4, .8, u));
      }
      v.needsUpdate = true; tether.material.opacity = (lost ? .35 : .85) * s.opacity;
      escape.rotation.x = st.p * .8; escape.visible = !lost || Math.sin(st.p * 6) > 0;
      sparks.forEach((spark, i) => { const t = fract(st.p * 1.2 + i / 8), a = hash(i + Math.floor(st.p * 1.2)) * TAU; spark.position.set(ship.position.x + Math.cos(a) * t * 2, ship.position.y + Math.sin(a) * t * 1.2, 1); spark.material.opacity = (1 - t) * .9 * s.opacity; });
    });
    chevrons(s);
    return;
  }
  if (key === 'signal_threat') {
    const centre = [2.6, 0, -.8];
    const beacon = s.model('beacon', centre, 2.6, {yaw: .3, tint: 'red'});
    for (let i = 0; i < 3; i++) {
      const pulse = s.circle(1, centre, 'red', .6, {tilt: -1.25});
      s.animations.push(st => { const t = fract(st.p * .25 + i / 3); pulse.scale.setScalar(1 + t * 7); pulse.material.opacity = .55 * (1 - t) * s.opacity; });
    }
    const pirates = [0, 1].map(i => { const p = s.model('ship', [0, 0, 0], 2.3, {type: 'interdictor', tint: 'red'}); wake(s, p, .6, 'red'); return p; });
    const ship = hero(s, [-6.2, -.4, 1.2], 3.2, {yaw: -.2}); wake(s, ship, .8);
    s.animations.push(st => {
      beacon.rotation.y = st.p * .2;
      pirates.forEach((pirate, i) => { const a = st.p * .22 + i * Math.PI; pirate.position.set(centre[0] + Math.cos(a) * 5.2, .5 + Math.sin(a * 2) * .3, centre[2] + Math.sin(a) * 2.2); pirate.rotation.y = -a - Math.PI / 2; });
    });
    const level = clamp(Number(s.state.label.match(/\d+$/)?.[0] || 0), 0, 8);
    if (level) pips(s, level, {corner: 'bottom', shape: 'triangle', tint: 'red', pulse: true});
    return;
  }
  // Combat: ships turning about each other, lasers crossing, shields
  // flaring where they land. Decorative: the journal reports no contacts.
  const heavy = key === 'heavy_combat';
  if (heavy) {
    const capital = s.model('capital', [5.5, 1, -8], 13, {yaw: -.3, tint: 'red', dim: .6});
    s.animations.push(st => { capital.position.x = 5.5 + Math.sin(st.p * .04) * .6; });
  }
  const ship = hero(s, [-3.2, 0, 1], 3.6, {yaw: -.2}); wake(s, ship, 1);
  const enemies = Array.from({length: heavy ? 3 : 2}, (_, i) => {
    const enemy = s.model('ship', [0, 0, 0], 2.9, {type: 'interdictor', tint: 'red'}); wake(s, enemy, .8, 'red'); return enemy;
  });
  const beams = enemies.map(() => s.strip(2, 'red', .85));
  const answer = s.strip(2, 'accent', .85);
  const flash = s.glow([0, 0, 0], 1.6, 'cyan', .8);
  const blasts = heavy ? [0, 1].map(() => s.glow([0, 0, 0], 1, 'gold', .8)) : [];
  s.animations.push(st => {
    enemies.forEach((enemy, i) => {
      const a = st.p * (.4 + i * .07) + i * TAU / enemies.length;
      enemy.position.set(3 + Math.cos(a) * 4, Math.sin(a * 2) * .7 + (i - 1) * .3, -.8 + Math.sin(a) * 2.2);
      enemy.rotation.set(0, -a - Math.PI / 2, Math.sin(a) * .5);
      const v = beams[i].geometry.attributes.position, on = fract(st.p * 1.3 + i * .37) < .4;
      v.setXYZ(0, enemy.position.x, enemy.position.y, enemy.position.z); v.setXYZ(1, ship.position.x + .4, ship.position.y, ship.position.z); v.needsUpdate = true;
      beams[i].visible = on;
    });
    const target = enemies[Math.floor(st.p * .3) % enemies.length].position, firing = fract(st.p * 1.1) < .45;
    const v = answer.geometry.attributes.position; v.setXYZ(0, ship.position.x + 1.6, ship.position.y, ship.position.z); v.setXYZ(1, target.x, target.y, target.z); v.needsUpdate = true;
    answer.visible = firing; flash.position.copy(target); flash.visible = firing;
    ship.rotation.z = Math.sin(st.p) * .25; ship.position.y = Math.sin(st.p * .7) * .3;
    blasts.forEach((blast, i) => { const t = fract(st.p * .35 + i * .5), cycle = Math.floor(st.p * .35 + i * .5); blast.position.set((hash(cycle + i) - .3) * 14, (hash(cycle + 7) - .5) * 2.4, -3); blast.scale.setScalar(.6 + t * 3.4); blast.material.opacity = (1 - t) * .75 * s.opacity; });
  });
  chevrons(s);
}

function emergency(s, key) {
  s.stars();
  if (key === 'jet_cone_damage') {
    // Inside a neutron star's jet, the ship buffeted along the cone.
    const at = [5.5, 0, -2.5], axis = new THREE.Group(); axis.position.set(...at); axis.rotation.z = -1.69; s.root.add(axis);
    s.star(at, .45, '', '#c0eaff');
    for (const side of [-1, 1]) {
      const cone = s.mesh(new THREE.ConeGeometry(1.6, 13, 24, 1, true), 'shell', [0, side * 6.5, 0], [1, 1, 1], 1.2, axis, {tint: 'accent'});
      cone.rotation.z = side > 0 ? Math.PI : 0;
      s.outline(cone, 'accent', .2, 1);
    }
    const flow = new Float32Array(80 * 3), field = s.points(flow, {tint: 'white', size: .1, opacity: .8, parent: axis});
    const ship = hero(s, [-3.6, 1.15, -1.4], 3.4, {yaw: -.3});
    const sparks = [];
    for (let i = 0; i < 6; i++) sparks.push(s.glow([0, 0, 0], .25, 'gold', .9));
    s.animations.push(st => {
      for (let i = 0; i < 80; i++) { const t = fract(hash(i) + st.p * .6), side = i % 2 ? 1 : -1, a = hash(i + 5) * TAU, r = t * 1.5 * hash(i + 9); flow.set([Math.cos(a) * r, side * t * 13, Math.sin(a) * r], i * 3); }
      field.geometry.attributes.position.needsUpdate = true;
      const shake = Math.floor(st.p * 9);
      ship.position.set(-3.6 + (hash(shake) - .5) * .25, 1.15 + (hash(shake + 1) - .5) * .25, -1.4); ship.rotation.z = Math.sin(st.p * 2) * .3;
      sparks.forEach((spark, i) => { const t = fract(st.p * 1.4 + i / 6), a = hash(i + Math.floor(st.p * 1.4)) * TAU; spark.position.set(ship.position.x + Math.cos(a) * t * 1.6, ship.position.y + Math.sin(a) * t, .6); spark.material.opacity = (1 - t) * .9 * s.opacity; });
      axis.rotation.y = st.p * .05;
    });
    chevrons(s);
    return;
  }
  const ship = hero(s, [0, 0, .4], 4.8, {yaw: -.3, tint: key === 'heat_critical' ? 'red' : 'state'});
  if (key === 'heat_critical') {
    // Heat critical: the hull red-hot, heat shimmering off it.
    wake(s, ship, 1, 'gold');
    s.glow([0, 0, .4], 6, 'red', .35);
    for (let i = 0; i < 15; i++) {
      const shimmer = s.strip(12, 'red', .3), v = shimmer.geometry.attributes.position;
      s.animations.push(st => { const x0 = (i - 7) * 1.25; for (let j = 0; j < 12; j++) { const u = j / 11; v.setXYZ(j, x0 + Math.sin(u * 6 + st.p * 2 + i) * .22, -2.3 + u * 4.6, -1.2); } v.needsUpdate = true; shimmer.material.opacity = (.12 + .22 * wave(st.p * .6 + i * .2)) * s.opacity; });
    }
    s.animations.push(st => { ship.rotation.y = -.3 + Math.sin(st.p * .2) * .05; });
    chevrons(s);
    return;
  }
  if (key === 'system_reboot') {
    // The ship goes dark and comes back a piece at a time, its ring relighting.
    const segments = [];
    for (let i = 0; i < 16; i++) {
      const arc = new THREE.Mesh(new THREE.TorusGeometry(2.7, .06, 4, 6, TAU / 16 - .07), s.track(new THREE.MeshBasicMaterial({color: s.tone('accent'), transparent: true, opacity: .8}), .8));
      s.geometries.push(arc.geometry); arc.position.set(0, 0, .4); arc.rotation.z = Math.PI / 2 - (i + 1) * TAU / 16 + .035; s.root.add(arc); segments.push(arc);
    }
    const hull = [...ship.userData.materials.values()];
    const base = hull.map(m => m.uniforms.uFill.value), lit = s.tone('accent'), dark = s.tone('red');
    s.animations.push(st => {
      const boot = fract(st.p * .12);
      const power = boot < .15 ? (hash(Math.floor(st.p * 20)) > .5 ? .2 : .5) : .3 + .7 * smooth(.15, .65, boot);
      hull.forEach((m, i) => { m.uniforms.uFill.value = base[i] * power; });
      segments.forEach((arc, i) => { const on = i / 16 < boot; arc.material.color.copy(on ? lit : dark); arc.material.opacity = (on ? .85 : .25) * s.opacity; });
    });
    chevrons(s, st => 1 - fract(st.p * .12));
    return;
  }
  // Repair (AFMU): a scan frame working along the hull, sparks where it is.
  wake(s, ship, .5);
  const frame = s.line([[0, -1.4, -1.2], [0, 1.4, -1.2], [0, 1.4, 1.6], [0, -1.4, 1.6], [0, -1.4, -1.2]], 'accent', .8);
  const sparks = [];
  for (let i = 0; i < 6; i++) sparks.push(s.glow([0, 0, 0], .2, 'gold', .9));
  for (let i = 0; i < 3; i++) s.line([[-10, 1.1 - i * .55, 0], [-7.4 + hash(i) * 1.6, 1.1 - i * .55, 0]], 'state', .5);
  s.animations.push(st => {
    const along = Math.sin(st.p * .5) * 2.2;
    frame.position.x = along;
    sparks.forEach((spark, i) => { const t = fract(st.p * 1.6 + i / 6), a = hash(i + Math.floor(st.p * 1.6)) * TAU; spark.position.set(along + Math.cos(a) * t * .6, Math.sin(a) * t * .6, .9); spark.material.opacity = (1 - t) * .9 * s.opacity; });
  });
}

// ---------------------------------------------------------------------------
// The surface: vehicles and the commander on foot.
// ---------------------------------------------------------------------------

function ground(s, key) {
  s.shot = {...SHOT, at: [0, -.75, 0]};
  s.terrain(s.seed % 8, {y: -1.95});
  const type = ['scorpion', 'rhino', 'nomad', 'scarab'].includes(key) ? key : ['scorpion', 'rhino', 'nomad', 'scarab'].includes(s.state.vehicleKey) ? s.state.vehicleKey : 'scarab';
  const rover = s.model('vehicle', [0, 0, .4], type === 'nomad' ? 5 : 4.7, {type, yaw: -.38});
  const restingY = -1.88 + rover.userData.height / 2;
  rover.position.y = restingY;
  const parked = key === 'srv_handbrake' || key === 'srv_turret';
  for (const wheel of rover.userData.nativeWheels) s.animations.push(st => { wheel.rotation.z = parked ? 0 : -st.p * 2.2; });
  s.planet([8.8, 3.3, -16], 1.3, 'ice', {latitudes: false});
  // Dust kicked up behind, the ground streaming past.
  if (!parked) {
    const count = 40, dust = new Float32Array(count * 3), cloud = s.points(dust, {tint: 'state', size: .12, opacity: .55});
    s.animations.push(st => {
      for (let i = 0; i < count; i++) { const t = fract(hash(i) + st.p * .5); dust.set([-2.4 - t * 6, -1.75 + t * (.4 + hash(i + 1) * .6), .4 + (hash(i + 2) - .5) * 2.4 + t * .5], i * 3); }
      cloud.geometry.attributes.position.needsUpdate = true;
    });
    for (let i = 0; i < 7; i++) {
      const tick = s.line([[0, 0, -.6], [0, 0, .6]], 'state', .5);
      s.animations.push(st => { const t = fract(st.p * .25 + i / 7); tick.position.set(10 - t * 20, -1.93, 2.4); tick.material.opacity = ends(t) * .5 * s.opacity; });
    }
  }
  if (type === 'rhino') { s.model('beacon', [-5.4, -1.2, -1.8], 1.2, {yaw: .3}); s.model('canister', [-4.2, -1.65, -1.2], .6); s.circle(2.2, [-5.4, -1.92, -1.8], 'state', .5, {dashed: true, segments: 48}); }
  if (type === 'nomad') { const hover = s.glow([0, -1.75, .4], 3, 'cyan', .25); s.animations.push(st => { hover.material.opacity = (.15 + .15 * wave(st.p)) * s.opacity; }); }
  if (key === 'srv_handbrake') for (const side of [-1, 1]) s.line([[side * 3, -1.6, .4], [side * 3, -.2, .4], [side * 3.5, -.2, .4]], 'red', .85);
  if (key === 'srv_drive_assist') for (const side of [-1, 1]) s.line([[-11, -1.9, .4 + side * 1.9], [11, -1.9, .4 + side * 1.9]], 'accent', .65);
  if (key === 'srv_turret') {
    const aim = s.strip(2, 'red', .75), mark = s.circle(.5, [0, 0, 0], 'red', .8, {tilt: 0, segments: 24});
    s.animations.push(st => { const a = Math.sin(st.p * .5) * .5, end = [Math.cos(a) * 7, .2, -Math.sin(a) * 4]; const v = aim.geometry.attributes.position; v.setXYZ(0, .4, .5, .4); v.setXYZ(1, ...end); v.needsUpdate = true; mark.position.set(...end); mark.rotation.z = st.p; });
  }
  if (key === 'srv_threat') {
    for (let i = 0; i < 3; i++) {
      const drone = s.model('skimmer', [3 + i * 2.2, 1 + i * .2, -1], 1.1, {tint: 'red'});
      const shot = s.strip(2, 'red', .7);
      s.animations.push(st => {
        drone.position.y = 1 + i * .2 + Math.sin(st.p + i) * .15; drone.rotation.y = st.p * .5;
        const v = shot.geometry.attributes.position; v.setXYZ(0, drone.position.x, drone.position.y, -1); v.setXYZ(1, 0, -.6, .4); v.needsUpdate = true;
        shot.visible = fract(st.p * 1.2 + i * .33) < .35;
      });
    }
    chevrons(s);
  }
  s.animations.push(st => { rover.position.y = restingY + (parked ? 0 : Math.sin(st.p * 3) * (type === 'nomad' ? .045 : .025)); });
}

function foot(s, key) {
  const hazard = key === 'suit_hazard', place = s.state.d.footPlace, interior = place !== 'planet';
  s.shot = {...SHOT, at: [0, -.2, 0], width: 17, height: 4.3, from: [.3, .26, 1]};
  if (interior) {
    s.mesh(new THREE.BoxGeometry(30, .12, 16), 'ground', [0, -1.9, -3]);
    for (const x of [-5, 5]) s.line([[x, -1.82, 4], [x, -1.82, -8]], 'accent', .4);
    for (let i = -6; i <= 6; i++) s.line([[i * 2, -1.83, 3], [i * 2, -1.83, -8]], 'state', .12);
  } else s.terrain(s.seed % 8, {y: -1.95, clearing: 4});
  const person = s.person([-1.1, -1.84, .5], !hazard && place === 'planet', hazard);
  person.scale.setScalar(1.38); person.rotation.y = .28;
  if (place === 'planet') {
    for (let i = 0; i < 3; i++) s.model('rock', [-5.2 + i * 4.4, -1.55, -2.4 - hash(i) * 2], .5 + hash(i) * .65, {seed: i + 3});
    s.model('ship', [-8, -.6, -6.5], 3.6, {yaw: .5, dim: .7});
    const sample = new THREE.Group(); sample.position.set(2.2, -1.82, 1); s.root.add(sample);
    for (let i = 0; i < 5; i++) {
      const x = (i - 2) * .19, height = .45 + hash(i + 8) * .45;
      s.mesh(new THREE.CylinderGeometry(.045, .085, height, 7), 'hull', [x, height / 2, Math.sin(i) * .15], [1, 1, 1], 1, sample);
      s.mesh(new THREE.IcosahedronGeometry(.12, 1), 'green', [x, height, Math.sin(i) * .15], [1, .7, 1], .8, sample);
    }
    s.circle(.9, [2.2, -1.8, 1], 'accent', .5, {dashed: true, segments: 32});
    if (!hazard) {
      const beam = s.strip(2, 'accent', .4), start = new THREE.Vector3();
      s.animations.push(st => {
        person.updateWorldMatrix(true, true); person.userData.tool.getWorldPosition(start); s.root.worldToLocal(start);
        const v = beam.geometry.attributes.position; v.setXYZ(0, start.x, start.y, start.z); v.setXYZ(1, 2.2 + Math.sin(st.p * .7) * .22, -1.2, 1);
        v.needsUpdate = true; beam.material.opacity = (.2 + Math.sin(st.p * .8) ** 2 * .35) * s.opacity;
      });
    }
  }
  if (place === 'concourse') {
    for (const x of [-5, 0, 5]) {
      s.outline(s.mesh(new THREE.BoxGeometry(.16, 3.3, .18), 'alloy', [x, -.25, -4]));
      s.mesh(new THREE.BoxGeometry(4.65, 2.7, .03), 'panel', [x + 2.5, -.15, -4.1], [1, 1, 1], 1, s.root, {tint: 'accent'});
    }
    s.line([[-6, 1.4, -4], [8, 1.4, -4]], 'state', .5);
    s.outline(s.mesh(new THREE.BoxGeometry(.7, 1.15, .4), 'hull', [2.7, -1.3, .1]));
    s.mesh(new THREE.BoxGeometry(.58, .4, .04), 'cyan', [2.7, -.9, .33], [1, 1, 1], .4);
    for (let i = 0; i < 2; i++) {
      const pedestrian = s.model('commander', [i * 5 - 2, -.98, -2.2 - i * .6], 1.65, {yaw: i ? -.4 : .8});
      s.animations.push(st => { pedestrian.position.x = i * 4 - 2 + Math.sin(st.p * .16 + i * 2) * 2; pedestrian.position.y = -.98 + Math.sin(st.p * 2 + i) * .02; });
    }
    const traffic = s.model('ship', [1, .4, -9], 1.7, {yaw: .2});
    s.animations.push(st => { traffic.position.x = Math.sin(st.p * .1) * 5; });
  } else if (place === 'hangar') {
    s.model('hexPad', [3, -1.7, -1.7], 5.5, {muted: true}); s.model('ship', [3, -.9, -1.7], 4.3, {yaw: .7});
    for (const x of [-6, 7]) s.outline(s.mesh(new THREE.BoxGeometry(.25, 5, .4), 'alloy', [x, .5, -4]));
    s.line([[-6, 3, -4], [7, 3, -4]], 'state', .65);
    for (let i = 0; i < 2; i++) s.outline(s.mesh(new THREE.BoxGeometry(.6, .55, .65), 'alloy', [-3.3 + i * .7, -1.55, -.8]));
    const drone = s.model('skimmer', [2, .5, -.3], .55);
    s.glow([3, -1.55, -1.7], 1.9, 'cyan', .16);
    s.animations.push(st => { drone.position.set(2 + Math.sin(st.p * .4), .5 + Math.cos(st.p * .6) * .2, -.3 + Math.cos(st.p * .4) * .6); });
  } else if (place === 'carrier') {
    s.model('carrier', [0, -.3, -8], 11.5);
    for (const x of [-5, 5]) { s.line([[x, -1.8, 3], [x, -.55, 3], [x, -.55, -4]], 'state', .45); s.outline(s.mesh(new THREE.BoxGeometry(.12, 3.2, .18), 'alloy', [x, -.2, -4])); }
    const tender = s.model('ship', [4, .5, -5], 1.3, {yaw: .8});
    s.animations.push(st => { tender.position.x = 4 + Math.sin(st.p * .15) * 1.8; tender.position.y = .5 + Math.sin(st.p * .18) * .1; });
  }
  if (hazard) {
    const cold = s.state.label.includes('COLD');
    for (const side of [-1, 1]) s.line([[-1.1 + side * .7, 1.3, .7], [-1.1 + side * .9, 1.3, .7], [-1.1 + side * .9, -1.7, .7], [-1.1 + side * .7, -1.7, .7]], cold ? 'accent' : 'red', .7);
    s.animations.push(st => { person.rotation.z = Math.sin(st.p) * .025; });
    if (s.state.label.includes('OXYGEN')) {
      for (let i = 0; i < 3; i++) {
        const breath = s.glow([-1, .6, 1], .2, 'cyan', .2);
        s.animations.push(st => { const q = fract(st.p * .35 + i / 3); breath.position.set(-1 + q * .6, .9 + q * .3, 1); breath.scale.setScalar(.15 + q * .3); breath.material.opacity = ends(q) * .3 * s.opacity; });
      }
    } else if (s.state.label.includes('HEALTH')) s.line([[.8, -.1, .8], [1.4, -.1, .8], [1.7, .5, .8], [2, -.5, .8], [2.3, -.1, .8], [3, -.1, .8]], 'red', .8);
    else s.glow([-1, .2, 0], 2.4, cold ? 'cyan' : 'red', .16);
    chevrons(s);
  }
}

// Ship to vehicle and back: the deploy, the recovery, the crew link.
function handoff(s, key) {
  s.shot = {...SHOT, at: [0, -.6, 0]};
  s.terrain(4, {y: -1.95});
  const mother = hero(s, [-3, .6, -1.5], 5.4, {yaw: -.2});
  const type = key.includes('fighter') ? 'fighter' : key.includes('nomad') ? 'nomad' : key.includes('scorpion') ? 'scorpion' : key.includes('rhino') ? 'rhino' : 'scarab';
  const crew = key.includes('crew') || key === 'multicrew';
  const child = crew ? s.person([3, -1.84, 1], true) : type === 'fighter' || key.endsWith('_ship')
    ? s.model('ship', [3, -.9, 1], 2.4, {type: type === 'fighter' ? 'fighter' : undefined})
    : s.model('vehicle', [3, -1.3, 1], 2.6, {type});
  const recover = /recovery|board|return/.test(key);
  const beam = s.strip(2, 'accent', .6);
  s.circle(1.4, [3, -1.92, 1], 'accent', .5, {dashed: true, segments: 32});
  s.animations.push(st => {
    const t = fract(st.p * .18), u = recover ? 1 - t : t;
    child.position.x = lerp(-1.5, 4.5, u);
    if (key.includes('deploy') && type === 'fighter') child.position.y = -.9 + Math.sin(u * Math.PI) * 1.2;
    for (const wheel of child.userData.nativeWheels || []) wheel.rotation.z = st.p * (recover ? 1.6 : -1.6);
    const v = beam.geometry.attributes.position; v.setXYZ(0, -3, .1, -1.5); v.setXYZ(1, child.position.x, child.position.y + .4, child.position.z); v.needsUpdate = true;
    beam.material.opacity = (.2 + .4 * wave(st.p)) * s.opacity;
    mother.position.y = .6 + Math.sin(st.p * .3) * .1;
  });
}

function panels(s, key) {
  // Cockpit panels as holo screens: one ahead, two angled either side.
  const centre = new THREE.Group(); s.root.add(centre);
  const layout = [[-6.6, .55], [0, 0], [6.6, -.55]];
  layout.forEach(([x, turn], i) => {
    const panel = s.mesh(new THREE.PlaneGeometry(5.4, 3.6), 'panel', [x, 0, -Math.abs(x) * .12], [1, 1, 1], 1, s.root, {tint: 'accent', side: THREE.DoubleSide});
    panel.rotation.y = turn; s.outline(panel, 'state', .75, 1);
    for (let j = 0; j < 4; j++) {
      const row = s.line([[-2.3, 1.1 - j * .6, .02], [-2.3 + 1.6 + hash(i * 4 + j) * 2.4, 1.1 - j * .6, .02]], 'state', i === 1 ? .35 : .6, panel);
      row.visible = i !== 1;
    }
    if (i === 0 || i === 2) {
      const pick = s.mesh(new THREE.PlaneGeometry(4.8, .42), 'lamp', [0, 1.1, .01], [1, 1, 1], .3, panel, {tint: 'state', side: THREE.DoubleSide});
      s.animations.push(st => { pick.position.y = 1.1 - (Math.floor(st.p * .5 + i) % 4) * .6; });
    }
  });
  if (key === 'left_panel') {
    const rows = s.line(Array.from({length: 12}, (_, j) => [[-2.2, 1.4 - j * .25, .1], [1.8, 1.4 - j * .25, .1]]).flat(), 'state', .5, centre, true);
    s.animations.push(st => { rows.position.y = -fract(st.p * .12) * .25; });
  } else if (key === 'right_panel') {
    const ship = s.model('ship', [0, .1, .3], 3.4, {yaw: .5});
    s.animations.push(st => { ship.rotation.y = .5 + st.p * .3; });
  } else if (key === 'comms_panel') {
    const signal = s.strip(60, 'accent', .9), v = signal.geometry.attributes.position;
    s.animations.push(st => { for (let i = 0; i < 60; i++) { const x = -2.4 + i * .08; v.setXYZ(i, x, Math.sin(i * .7 - st.p * 3) * Math.sin(i * .11 + st.p) * .8, .2); } v.needsUpdate = true; });
  } else if (key === 'role_panel') {
    const crew = s.person([0, -1.5, .4], false); crew.scale.setScalar(.95);
  } else {
    const station = s.model('coriolis', [0, 0, .3], 2.6, {yaw: .5});
    s.animations.push(st => { station.rotation.y = .5 + st.p * .25; station.rotation.x = st.p * .1; });
  }
}

function buildStage(state, palette, texture) {
  const s = new Stage(state, palette, texture), key = state.key;
  if (TUNNEL.has(key)) tunnel(s, key);
  else if (CRUISE.has(key)) cruise(s, key);
  else if (key === 'fsd_cooldown') cooldown(s);
  else if (CHARGE.has(key)) charge(s, key);
  else if (key === 'arrival' || key === 'local_arrival' || key === 'interdiction_evaded') arrival(s, key);
  else if (key === 'docked' || key === 'station') docked(s, key);
  else if (APPROACH.has(key)) approach(s, key);
  else if (CARRIER.has(key)) carrier(s, key);
  else if (key === 'galaxy_map' || key === 'power_map' || key === 'map') galaxy(s, key);
  else if (key === 'system_map') systemMap(s);
  else if (key === 'orrery') orrery(s);
  else if (key === 'codex') codex(s);
  else if (key === 'fss') fss(s);
  else if (key === 'dss') dss(s);
  else if (key === 'exploration') exploration(s);
  else if (key.startsWith('target_')) target(s, key);
  else if (DESCENT.has(key)) descent(s, key);
  else if (PADS.has(key)) pads(s, key);
  else if (VEHICLES.has(key)) ground(s, key);
  else if (key === 'on_foot' || key === 'suit_hazard') foot(s, key);
  else if (key.startsWith('vehicle_') || key === 'multicrew') handoff(s, key);
  else if (key === 'asteroid_field') asteroids(s);
  else if (LOCKS.has(key)) lock(s, key);
  else if (FIGHTS.has(key)) fight(s, key);
  else if (['heat_critical', 'jet_cone_damage', 'system_reboot', 'maintenance'].includes(key)) emergency(s, key);
  else if (PANELS.has(key)) panels(s, key);
  else if (['flight', 'fighter', 'silent_running', 'flight_assist_off'].includes(key)) flight(s, key);
  else throw new Error(`No Three.js navigation scene for ${key}`);
  systems(s);
  return s;
}

export class ThreeSurface {
  constructor(canvas, role) {
    this.canvas = canvas; this.role = role; this.W = 0; this.H = 0; this.ratio = 1; this.dpr = 1;
    this.cache = new Map(); this.failed = false; this.error = ''; this.events = [];
    try {
      this.renderer = new THREE.WebGLRenderer({canvas, alpha: true, antialias: true, premultipliedAlpha: true, preserveDrawingBuffer: true, powerPreference: 'low-power'});
      this.renderer.setPixelRatio(1); this.renderer.setClearColor(0, 0); this.renderer.outputColorSpace = THREE.SRGBColorSpace;
      this.renderer.toneMapping = THREE.NoToneMapping;
      this.scene = new THREE.Scene(); this.scene.fog = new THREE.Fog(0x000000, 12, 32);
      this.camera = new THREE.PerspectiveCamera(24, 1, .1, 200);
      this.flatScene = new THREE.Scene(); this.flatCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, -10, 10);
      this.texture = glowTexture(); this.canvas.dataset.renderer = 'three';
      canvas.addEventListener('webglcontextlost', event => { event.preventDefault(); this.failed = true; this.canvas.dataset.renderer = 'lost'; this.error = 'WebGL context lost'; this.showError(); });
      canvas.addEventListener('webglcontextrestored', () => { this.failed = false; this.error = ''; this.canvas.dataset.renderer = 'three'; this.showError(); canvas.dispatchEvent(new Event('contextrestored')); });
    } catch (error) { this.failed = true; this.error = String(error.message || error); this.canvas.dataset.renderer = 'failed'; this.showError(); }
    this.resize();
  }
  showError() {
    if (this.role !== 'deck') return;
    let notice = this.canvas.parentElement.querySelector('.scene-render-error');
    if (!notice) { notice = document.createElement('span'); notice.className = 'scene-render-error'; notice.setAttribute('role', 'status'); this.canvas.parentElement.append(notice); }
    notice.textContent = this.failed ? '3D SCENE UNAVAILABLE' : ''; notice.hidden = !this.failed;
    if (this.failed) console.warn('Navigation HUD Three.js scene unavailable:', this.error);
  }
  resize() {
    this.W = this.canvas.clientWidth; this.H = this.canvas.clientHeight; this.dpr = window.devicePixelRatio || 1;
    const shown = this.canvas.getBoundingClientRect().width, zoom = this.W > 0 && shown > 0 ? shown / this.W : 1; this.ratio = clamp(this.dpr * zoom, 1, 3);
    if (this.renderer) {
      this.renderer.setSize(Math.max(1, Math.round(this.W * this.ratio)), Math.max(1, Math.round(this.H * this.ratio)), false);
      this.camera.aspect = this.W / Math.max(1, this.H); this.camera.updateProjectionMatrix();
      Object.assign(this.flatCamera, {left: -this.W / 2, right: this.W / 2, top: this.H / 2, bottom: -this.H / 2}); this.flatCamera.updateProjectionMatrix();
    }
  }
  begin() { if (this.renderer && !this.failed) this.renderer.clear(); return this.W > 1 && this.H > 1 && !this.failed; }
  get(state, palette) {
    const key = state.identity + '|' + state.starFamily + '|' + state.targetFamily + '|' + JSON.stringify(palette);
    if (this.cache.has(key)) { const stage = this.cache.get(key); this.cache.delete(key); this.cache.set(key, stage); return stage; }
    const stage = buildStage(state, palette, this.texture); this.scene.add(stage.root); this.flatScene.add(stage.flat); this.cache.set(key, stage);
    while (this.cache.size > 4) { const [old, entry] = this.cache.entries().next().value; this.scene.remove(entry.root); this.flatScene.remove(entry.flat); entry.dispose(); this.cache.delete(old); }
    return stage;
  }
  // Back the camera off along the shot's direction until its frame fits the deck.
  frame(shot) {
    const half = THREE.MathUtils.degToRad(shot.fov / 2), aspect = this.W / Math.max(1, this.H);
    const distance = Math.max(shot.height / 2 / Math.tan(half), shot.width / 2 / (Math.tan(half) * aspect));
    const at = new THREE.Vector3(...shot.at), from = new THREE.Vector3(...shot.from).normalize();
    this.camera.fov = shot.fov; this.camera.aspect = aspect; this.camera.updateProjectionMatrix();
    this.camera.position.copy(at).addScaledVector(from, distance); this.camera.lookAt(at);
    this.scene.fog.near = distance * 1.05; this.scene.fog.far = distance * 2.7;
  }
  render(layers, palette, overlays = {}) {
    if (!this.begin()) return;
    try {
      for (const stage of this.cache.values()) stage.root.visible = stage.flat.visible = false;
      if (this.role === 'bay') { this.renderBay(layers.at(-1)?.state, palette, overlays); return; }
      const view = {W: this.W, H: this.H};
      const staged = layers.map(layer => ({...layer, stage: this.get(layer.state, palette)}));
      this.frame(staged.at(-1)?.stage.shot || SHOT);
      for (const {state, alpha, fold, stage} of staged) { stage.root.visible = stage.flat.visible = true; stage.update(state, alpha, fold, view); }
      this.renderEvent(layers.at(-1)?.state, palette, overlays);
      this.renderer.render(this.scene, this.camera);
      if (staged.some(({stage}) => stage.flat.children.length)) {
        this.renderer.autoClear = false; this.renderer.render(this.flatScene, this.flatCamera); this.renderer.autoClear = true;
      }
    } catch (error) { this.failed = true; this.error = String(error.message || error); this.canvas.dataset.renderer = 'failed'; this.showError(); }
  }
  renderEvent(state, palette, {event, now} = {}) {
    if (!state) return;
    if (!event) { if (this.eventStage) this.eventStage.root.visible = false; return; }
    const id = event.kind + ':' + event.start;
    if (this.eventId !== id) {
      if (this.eventStage) { this.scene.remove(this.eventStage.root); this.eventStage.dispose(); }
      const tone = event.tone === 'muted' ? 'orange' : event.tone;
      const s = new Stage({...state, c: palette[tone] || state.c}, palette, this.texture);
      this.eventStage = s; this.eventId = id; this.scene.add(s.root);
      const warning = /warning|interdict|damage|denied/.test(event.kind);
      s.ring(.8, [0, 0, 2], warning ? 'red' : 'cyan', -.45, .65, TAU * (warning ? .72 : .94));
      for (let i = 0; i < 8; i++) s.glow([0, 0, 0], .24, warning ? 'red' : 'white', .7);
    }
    // The event's own phase is supplied independently of the state clock.
    const stage = this.eventStage, t = clamp((now - event.start) / 2200);
    const ring = stage.root.children[0]; ring.scale.setScalar(1 + t * 4); ring.rotation.z = t * 1.6;
    for (let i = 1; i < stage.root.children.length; i++) { const a = (i - 1) * TAU / 8 + t * .5, r = .5 + t * 5; stage.root.children[i].position.set(Math.cos(a) * r, Math.sin(a) * r * .38, 2); }
    stage.root.visible = true; stage.update(state, Math.sin(t * Math.PI));
  }
  renderBay(state, palette, {gear} = {}) {
    if (!state) return;
    const d = state.d;
    const enabled = d.inMainShip && (d.shieldsKnown || d.fuelScooping || d.cargoScoop || d.hardpoints || d.overheating || Boolean(gear));
    if (!enabled) return;
    const key = JSON.stringify([d.shieldsKnown, d.shieldsUp, d.fuelScooping, d.cargoScoop, d.hardpoints, d.overheating, Boolean(gear), gear?.down, state.c, palette]);
    if (!this.bay || this.bayKey !== key) {
      if (this.bay) { this.scene.remove(this.bay.root); this.bay.dispose(); }
      this.bay = new Stage(state, palette, this.texture); this.bayKey = key; this.scene.add(this.bay.root);
      if (d.shieldsKnown) for (let i = 0; i < 3; i++) this.bay.ring(2.2 + i * .22, [0, 0, 0], d.shieldsUp ? 'cyan' : 'red', -.25, .3, TAU * .75);
      if (d.fuelScooping) this.bay.ring(2.8, [0, -1, 0], 'gold', -.4, .6, TAU * .6);
      if (d.hardpoints) for (const side of [-1, 1]) this.bay.line([[side * 2.5, -1, 0], [side * 3, 0, 0], [side * 2.5, 1, 0]], 'red', .7);
      if (d.cargoScoop) this.bay.line([[-1, -1.5, 0], [0, -2.5, 0], [1, -1.5, 0]], 'orange', .7);
      if (d.overheating) this.bay.glow([0, 0, -1], 6, 'red', .25);
      if (gear) for (const side of [-1, 1]) this.bay.line([[side * 1.4, -.5, 0], [side * 1.8, -1.8, 0], [side * 2.4, -1.8, 0]], 'orange', .75);
    }
    this.bay.root.visible = true; this.bay.update(state);
    this.scene.fog.near = 100; this.scene.fog.far = 200;
    this.camera.fov = 26; this.camera.aspect = this.W / Math.max(1, this.H); this.camera.updateProjectionMatrix();
    this.camera.position.set(0, 0, 14); this.camera.lookAt(0, 0, 0); this.renderer.render(this.scene, this.camera);
  }
  pixels() {
    const gl = this.renderer?.getContext(); if (!gl || this.failed) return new Uint8Array(this.canvas.width * this.canvas.height * 4);
    const pixels = new Uint8Array(this.canvas.width * this.canvas.height * 4); gl.readPixels(0, 0, this.canvas.width, this.canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels); return pixels;
  }
  dispose() { for (const stage of this.cache.values()) stage.dispose(); this.bay?.dispose(); this.eventStage?.dispose(); this.texture?.dispose(); this.renderer?.dispose(); }
}
