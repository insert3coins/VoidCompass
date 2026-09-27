(() => {
  'use strict';

  /*
   * Navigation models
   * -----------------
   * Low-poly solids for the navigation scenes: the Coriolis station, the
   * Drake-class fleet carrier, ships, surface vehicles, buildings and the
   * pieces they are built from. A model is vertices and faces in its own
   * units: x forward (a ship's nose), y down, z toward the viewer when it
   * is seen side on. scene.js poses, lights and draws it, the same way it
   * draws the asteroid field's rocks.
   *
   * Each face has a kind: 'hull' is lit by the key light; 'trim' is a
   * slightly brighter panel on a hull; 'dark' is a recess such as the
   * station's mail slot; anything else names a lamp the scene colours
   * (engines, windows, the slot's traffic lights, landing pads). Every
   * piece is built convex and its faces turned outward from its own
   * centre, so the painter can cull back faces without a winding table.
   * Models are built once and cached; only the commander on foot is posed
   * afresh each frame.
   */

  const TAU = Math.PI * 2;
  // The same stable scatter scene.js uses, so layouts never change.
  const hashOf = (value) => {
    const x = Math.sin(value * 91.731 + 17.17) * 43758.5453;
    return x - Math.floor(x);
  };

  const sub =(a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const centreOf = (points) => {
    const sum = [0, 0, 0];
    for (const point of points) for (let axis = 0; axis < 3; axis += 1) sum[axis] += point[axis];
    return sum.map((value) => value / points.length);
  };
  // Newell's normal: robust for any planar-ish polygon.
  function normalOf(points) {
    const n = [0, 0, 0];
    for (let index = 0; index < points.length; index += 1) {
      const a = points[index], b = points[(index + 1) % points.length];
      n[0] += (a[1] - b[1]) * (a[2] + b[2]);
      n[1] += (a[2] - b[2]) * (a[0] + b[0]);
      n[2] += (a[0] - b[0]) * (a[1] + b[1]);
    }
    return n;
  }

  // A convex piece: faces are index lists, turned to face away from centre.
  function piece(vertices, faces, kind = 'hull', centre = centreOf(vertices)) {
    return {
      v: vertices,
      f: faces.map((indices) => {
        const points = indices.map((index) => vertices[index]);
        const outward = dot(normalOf(points), sub(centreOf(points), centre)) >= 0;
        return {i: outward ? indices : [...indices].reverse(), k: kind};
      }),
      lights: [],
    };
  }

  // A flat plate (a lamp, a pad, a window) facing away from `centre`.
  function plate(points, kind, centre) {
    return piece(points, [points.map((_, index) => index)], kind, centre);
  }

  function merge(...parts) {
    const out = {v: [], f: [], lights: []};
    for (const part of parts) {
      if (!part) continue;
      const offset = out.v.length;
      out.v.push(...part.v);
      out.f.push(...part.f.map((face) => ({...face, i: face.i.map((index) => index + offset)})));
      out.lights.push(...(part.lights || []));
    }
    return out;
  }

  function mapPoints(mesh, fn) {
    return {
      v: mesh.v.map(fn),
      f: mesh.f,
      lights: (mesh.lights || []).map((light) => {
        const at = fn(light.at);
        const tip = fn(light.at.map((value, axis) => value + light.n[axis]));
        return {...light, at, n: sub(tip, at)};
      }),
    };
  }
  const move = (mesh, dx = 0, dy = 0, dz = 0) => mapPoints(mesh, ([x, y, z]) => [x + dx, y + dy, z + dz]);
  const stretch = (mesh, sx = 1, sy = sx, sz = sx) => mapPoints(mesh, ([x, y, z]) => [x * sx, y * sy, z * sz]);
  function turn(mesh, yaw = 0, pitch = 0, roll = 0) {
    const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const cr = Math.cos(roll), sr = Math.sin(roll);
    return mapPoints(mesh, ([x, y, z]) => {
      const x1 = x * cr - y * sr, y1 = x * sr + y * cr;
      const x2 = x1 * cy + z * sy, z2 = z * cy - x1 * sy;
      return [x2, y1 * cp - z2 * sp, y1 * sp + z2 * cp];
    });
  }

  function box(w, h, d, kind = 'hull') {
    const x = w / 2, y = h / 2, z = d / 2;
    const v = [[-x, -y, -z], [x, -y, -z], [x, y, -z], [-x, y, -z],
      [-x, -y, z], [x, -y, z], [x, y, z], [-x, y, z]];
    return piece(v, [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [3, 2, 6, 7], [0, 3, 7, 4], [1, 2, 6, 5]], kind);
  }
  // A box spanning two corners, which is how most hull parts are sized.
  const block = (x0, y0, z0, x1, y1, z1, kind) =>
    move(box(x1 - x0, y1 - y0, z1 - z0, kind), (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);

  // Join cross-sections (each [[y, z], ...] with the same count) along x.
  function loft(sections, kind = 'hull') {
    const n = sections[0].pts.length;
    const v = [];
    for (const section of sections) for (const [y, z] of section.pts) v.push([section.x, y, z]);
    const faces = [];
    for (let s = 0; s < sections.length - 1; s += 1) {
      for (let index = 0; index < n; index += 1) {
        const a = s * n + index, b = s * n + (index + 1) % n;
        faces.push([a, b, b + n, a + n]);
      }
    }
    faces.push([...Array(n).keys()]);
    faces.push([...Array(n).keys()].map((index) => (sections.length - 1) * n + index));
    return piece(v, faces, kind);
  }

  // A regular n-gon prism along x (wheels, engines, canisters).
  function cylinder(r, length, sides = 8, kind = 'hull', r2 = r) {
    const ring = (radius) => Array.from({length: sides}, (_, index) => {
      const angle = index * TAU / sides + Math.PI / sides;
      return [Math.sin(angle) * radius, Math.cos(angle) * radius];
    });
    return loft([{x: -length / 2, pts: ring(r)}, {x: length / 2, pts: ring(r2)}], kind);
  }

  // A low dome standing on y = 0 (settlement habitats).
  function dome(r, sides = 8, kind = 'hull') {
    const v = [], faces = [];
    const rings = [[r, 0], [r * .82, -r * .55], [r * .42, -r * .92]];
    for (const [radius, y] of rings) {
      for (let index = 0; index < sides; index += 1) {
        const angle = index * TAU / sides;
        v.push([Math.cos(angle) * radius, y, Math.sin(angle) * radius]);
      }
    }
    for (let ring = 0; ring < rings.length - 1; ring += 1) {
      for (let index = 0; index < sides; index += 1) {
        const a = ring * sides + index, b = ring * sides + (index + 1) % sides;
        faces.push([a, b, b + sides, a + sides]);
      }
    }
    faces.push([...Array(sides).keys()].map((index) => (rings.length - 1) * sides + index));
    faces.push([...Array(sides).keys()]);
    return piece(v, faces, kind, [0, -r * .35, 0]);
  }

  // Shrink one face toward its centre and lift it clear: a panel, window
  // or lamp that sits on the hull and faces the same way.
  function inset(mesh, faceIndex, scale, kind, lift = .012, sx = scale, sy = scale) {
    const face = mesh.f[faceIndex];
    const points = face.i.map((index) => mesh.v[index]);
    const centre = centreOf(points);
    const n = normalOf(points), length = Math.hypot(...n) || 1;
    const up = n.map((value) => value / length * lift);
    // Two in-plane axes so a lamp can be a strip rather than a square.
    const u = sub(points[1], points[0]), ul = Math.hypot(...u) || 1;
    const ux = u.map((value) => value / ul);
    const vx = [n[1] * ux[2] - n[2] * ux[1], n[2] * ux[0] - n[0] * ux[2], n[0] * ux[1] - n[1] * ux[0]]
      .map((value) => value / length);
    const shrunk = points.map((point) => {
      const d = sub(point, centre);
      const a = dot(d, ux) * sx, b = dot(d, vx) * sy;
      return [0, 1, 2].map((axis) => centre[axis] + ux[axis] * a + vx[axis] * b + up[axis]);
    });
    const behind = centre.map((value, axis) => value - n[axis]);
    return plate(shrunk, kind, behind);
  }

  const light = (at, n, kind = 'beacon') => ({at, n, k: kind});

  // ---------------------------------------------------------------------
  // The Coriolis station: a cuboctahedron turning about the axis through
  // its mail slot, the way every commander first sees one.
  // ---------------------------------------------------------------------
  function coriolis() {
    const v = [];
    for (const [a, b] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) v.push([a, b, 0], [a, 0, b], [0, a, b]);
    const faces = [];
    // Six squares, one round each axis direction.
    for (let axis = 0; axis < 3; axis += 1) {
      for (const sign of [-1, 1]) {
        const ids = v.map((point, index) => [point, index]).filter(([point]) => point[axis] === sign);
        const [p, q] = [0, 1, 2].filter((other) => other !== axis);
        ids.sort((left, right) => Math.atan2(left[0][q], left[0][p]) - Math.atan2(right[0][q], right[0][p]));
        faces.push(ids.map(([, index]) => index));
      }
    }
    // Eight triangles, one per octant.
    for (const sx of [-1, 1]) {
      for (const sy of [-1, 1]) {
        for (const sz of [-1, 1]) {
          faces.push([[sx, sy, 0], [sx, 0, sz], [0, sy, sz]].map((point) =>
            v.findIndex((vertex) => vertex.every((value, axis) => value === point[axis]))));
        }
      }
    }
    // Square the slot face to the station's own axes.
    let hull = turn(piece(v, faces), 0, 0, Math.PI / 4);
    const slotFace = hull.f.findIndex((face) => face.i.every((index) => Math.abs(hull.v[index][2] - 1) < 1e-6));
    const panels = hull.f.map((face, index) => {
      if (index === slotFace || face.i.length !== 4) return null;
      return inset(hull, index, .52, 'trim', .01);
    });
    // City lights across the triangular faces.
    const lights = hull.f.filter((face) => face.i.length === 3).map((face) => {
      const points = face.i.map((index) => hull.v[index]);
      return light(centreOf(points), normalOf(points), 'window');
    });
    const behind = [0, 0, 0];
    const slot = merge(
      plate([[-.54, -.16, 1.008], [.54, -.16, 1.008], [.54, .16, 1.008], [-.54, .16, 1.008]], 'trim', behind),
      plate([[-.46, -.085, 1.016], [.46, -.085, 1.016], [.46, .085, 1.016], [-.46, .085, 1.016]], 'dark', behind),
      plate([[-.46, -.14, 1.02], [.46, -.14, 1.02], [.46, -.108, 1.02], [-.46, -.108, 1.02]], 'slot', behind),
      plate([[-.46, .108, 1.02], [.46, .108, 1.02], [.46, .14, 1.02], [-.46, .14, 1.02]], 'slot', behind),
    );
    hull = merge(hull, ...panels, slot);
    hull.lights = lights;
    // Where traffic enters and leaves, in the station's own units.
    hull.slot = [0, 0, 1.02];
    return hull;
  }

  // The inside of the Coriolis: city blocks standing inward from the wall
  // of the turning cylinder (radius 3 about z, running away from the
  // viewer), windows lit on the faces that look across the axis.
  function stationCity() {
    const parts = [];
    for (let index = 0; index < 26; index += 1) {
      const angle = hashOf(index + 300) * TAU, z = -11 + hashOf(index + 301) * 11;
      const h = .35 + hashOf(index + 302) * 1.1, w = .45 + hashOf(index + 303) * .5, d = .6 + hashOf(index + 304) * .9;
      const building = turn(block(-w / 2, -h / 2, -d / 2, w / 2, h / 2, d / 2), 0, 0, angle - Math.PI / 2);
      const radius = 3 - h / 2;
      const placed = move(building, Math.cos(angle) * radius, Math.sin(angle) * radius, z);
      placed.lights = [light([Math.cos(angle) * (3 - h - .01), Math.sin(angle) * (3 - h - .01), z],
        [-Math.cos(angle), -Math.sin(angle), 0], 'window')];
      parts.push(placed);
    }
    return merge(...parts);
  }

  // ---------------------------------------------------------------------
  // The Drake-class fleet carrier: a long armoured hull, the tall command
  // tower with its wide bridge, landing pads along the deck ahead of it
  // and four drive bells astern.
  // ---------------------------------------------------------------------
  function carrier() {
    const hex = (h, w, lift = 0) => [[-h + lift, -w * .72], [-h + lift, w * .72], [lift, w],
      [h + lift, w * .72], [h + lift, -w * .72], [lift, -w]];
    const hull = loft([
      {x: -7, pts: hex(.72, 1.55)},
      {x: 3.4, pts: hex(.72, 1.55)},
      {x: 7, pts: hex(.4, .8, .12)},
    ]);
    const rear = hull.f.length - 2;
    const keel = block(-6.2, .55, -.8, 5, 1.05, .8);
    const tower = block(-3.4, -2.6, -.34, -2.2, -.7, .34);
    const bridge = block(-3.6, -3.25, -1.2, -1.8, -2.6, 1.2);
    const bridgeWindow = inset(bridge, 5, .8, 'window', .012, .9, .3);
    const mast = block(-2.95, -3.9, -.05, -2.85, -3.25, .05);
    // Eight pads, each its own lamp (pad0 nearest the tower) so a scene can
    // light them in turn.
    const pads = [];
    for (let index = 0; index < 4; index += 1) {
      const x = -.9 + index * 1.35;
      for (const side of [-1, 1]) {
        const z = side * .55;
        pads.push(plate([[x - .45, -.735, z - .38], [x + .45, -.735, z - .38], [x + .45, -.735, z + .38],
          [x - .45, -.735, z + .38]], `pad${pads.length}`, [x, 0, z]));
      }
    }
    const engines = [];
    for (const y of [-.28, .28]) {
      for (const z of [-.72, .72]) {
        engines.push(plate([[-7.02, y - .2, z - .3], [-7.02, y - .2, z + .3], [-7.02, y + .2, z + .3],
          [-7.02, y + .2, z - .3]], 'engine', [0, y, z]));
      }
    }
    const model = merge(hull, inset(hull, rear, .9, 'trim', .01), keel, tower, bridge, bridgeWindow, mast,
      ...pads, ...engines);
    model.lights = [
      light([-2.9, -3.92, 0], [0, -1, 0], 'beacon'),
      light([7.02, .12, 0], [1, 0, 0], 'beacon'),
      ...[-5.5, -3.5, -1.5, .5, 2.5].map((x) => light([x, 0, 1.56], [0, 0, 1], 'window')),
    ];
    return model;
  }

  // A capital warship: a long blade of a hull, a raised command block and
  // twin drive nacelles. Pointed where the carrier is blunt.
  function capital() {
    const diamond = (h, w) => [[-h, 0], [0, w], [h * .6, 0], [0, -w]];
    const hull = loft([
      {x: -8, pts: diamond(1.3, 1.5)},
      {x: 1, pts: diamond(1.1, 1.3)},
      {x: 8, pts: diamond(.12, .16)},
    ]);
    const command = block(-6.4, -2.2, -.45, -3.6, -1, .45);
    const deck = block(-6.9, -2.6, -.9, -4.4, -2.2, .9);
    const nacelles = [-1, 1].map((side) => move(cylinder(.45, 4.2, 6), -6.3, .2, side * 1.35));
    const glow = [-1, 1].map((side) => plate(
      Array.from({length: 6}, (_, index) => {
        const angle = index * TAU / 6 + Math.PI / 6;
        return [-8.42, .2 + Math.cos(angle) * .32, side * 1.35 + Math.sin(angle) * .32];
      }), 'engine', [0, .2, side * 1.35]));
    const model = merge(hull, command, deck, inset(deck, 5, .8, 'window', .012, .9, .35), ...nacelles, ...glow);
    model.lights = [-6, -3, 0, 3].map((x) => light([x, 0, 1.2], [0, 0, 1], 'window'));
    return model;
  }

  // Ships, nose to +x. The small ones read at a few pixels, so each is a
  // clear silhouette: the everyday wedge, a fighter with its canopy, the
  // boxy Apex taxi and a heavier, aggressive interdictor.
  function ship(kind = 'wedge') {
    if (kind === 'taxi') {
      const hull = loft([
        {x: -1.4, pts: [[-.45, -.6], [-.45, .6], [.45, .6], [.45, -.6]]},
        {x: .9, pts: [[-.5, -.65], [-.5, .65], [.45, .65], [.45, -.65]]},
        {x: 1.7, pts: [[-.18, -.45], [-.18, .45], [.35, .45], [.35, -.45]]},
      ]);
      const windows = [2, 3, 4, 5].map((face) => inset(hull, face, .7, 'window', .012, .8, .25));
      const engine = inset(hull, hull.f.length - 2, .7, 'engine');
      const fins = [-1, 1].map((side) => block(-1.4, -.2, side * .6, -.6, .1, side * 1.05));
      return merge(hull, ...windows, engine, ...fins);
    }
    // A flattened hexagon: the cross-section of a combat hull, `w` either
    // side of the keel line and `h` above it.
    const section = (x, w, h) => ({x, pts: [[0, -w], [-h, -w * .5], [-h, w * .5], [0, w], [h * .6, w * .5],
      [h * .6, -w * .5]]});
    // Nose to stern: a narrow prow widening to swept wing tips, then the
    // drive face. The everyday hull is Cobra-like; the interdictor longer
    // and meaner; the fighter a small dart.
    const plan = {
      wedge: [[1.9, .32, .12], [.3, 1.2, .42], [-.75, 1.9, .42], [-1.15, 1.3, .38]],
      fighter: [[1.5, .18, .1], [.2, .7, .36], [-.8, 1.15, .3], [-1, .62, .28]],
      interdictor: [[2.6, .16, .1], [.6, .9, .46], [-.9, 1.55, .5], [-1.3, 1.1, .45]],
    }[kind] || [[1.9, .32, .12], [.3, 1.2, .42], [-.75, 1.9, .42], [-1.15, 1.3, .38]];
    const hull = loft(plan.map(([x, w, h]) => section(x, w, h)));
    const parts = [hull, inset(hull, hull.f.length - 1, .6, 'engine', .02, .72, .5),
      inset(hull, 1, .5, 'window', .015, .55, .7)];
    if (kind === 'interdictor') {
      parts.push(...[-1, 1].map((side) => block(-1.2, -.08, side * 1.1, .3, .08, side * 2.1)));
    }
    return merge(...parts);
  }

  // A Thargoid interceptor: eight petals round a glowing heart, facing the
  // viewer, each petal cupped forward.
  function thargoid() {
    const parts = [];
    for (let index = 0; index < 8; index += 1) {
      const angle = index * TAU / 8;
      const at = (r, spread, z) => [Math.cos(angle + spread) * r, Math.sin(angle + spread) * r, z];
      const petal = [at(.6, -.2, .1), at(1.5, -.24, .45), at(2.35, -.05, .78), at(2.35, .05, .78),
        at(1.5, .24, .45), at(.6, .2, .1)];
      const back = petal.map(([x, y, z]) => [x * .96, y * .96, z - .18]);
      const v = [...petal, ...back];
      const faces = [[0, 1, 2, 3, 4, 5], [6, 7, 8, 9, 10, 11]];
      for (let edge = 0; edge < 6; edge += 1) faces.push([edge, (edge + 1) % 6, (edge + 1) % 6 + 6, edge + 6]);
      parts.push(piece(v, faces));
    }
    const core = cylinder(.62, .5, 8);
    const heart = turn(core, Math.PI / 2, 0, 0);
    parts.push(heart, inset(heart, heart.f.length - 1, .6, 'core', .02));
    return merge(...parts);
  }

  // ---------------------------------------------------------------------
  // Surface vehicles, nose to +x, wheels on y = 0. Each lists its wheels
  // so the scene can spin their spokes.
  // ---------------------------------------------------------------------
  function vehicle(type) {
    const wheels = [];
    const wheel = (x, z, r, width) => {
      wheels.push({at: [x, -r, z], r});
      return move(turn(cylinder(r, width, 8), Math.PI / 2, 0, 0), x, -r, z);
    };
    const parts = [];
    if (type === 'nomad') {
      // A hover skimmer: a low wedge on four glowing lift pads.
      const hull = loft([
        {x: -1.7, pts: [[-.62, -.7], [-.62, .7], [-.28, .95], [-.28, -.95]]},
        {x: .9, pts: [[-.72, -.75], [-.72, .75], [-.3, 1], [-.3, -1]]},
        {x: 1.9, pts: [[-.48, -.35], [-.48, .35], [-.3, .5], [-.3, -.5]]},
      ]);
      parts.push(move(hull, 0, -.15, 0), block(-.6, -1.12, -.45, .6, -.87, .45));
      parts.push(inset(parts[1], 1, .7, 'window', .012, .8, .5));
      for (const x of [-1.1, 1]) {
        for (const z of [-.7, .7]) {
          parts.push(plate([[x - .3, -.44, z - .22], [x + .3, -.44, z - .22], [x + .3, -.44, z + .22],
            [x - .3, -.44, z + .22]], 'hover', [x, -1, z]));
        }
      }
    } else if (type === 'rhino') {
      // A heavy hauler: tall cab, cargo box, four axles.
      parts.push(block(-1.9, -1.05, -.85, 1.2, -.35, .85));
      const cab = block(.6, -1.55, -.7, 1.75, -.55, .7);
      parts.push(cab, inset(cab, 5, .75, 'window', .012, .85, .5));
      parts.push(block(-1.8, -1.55, -.72, .4, -1.05, .72, 'trim'));
      for (const x of [-1.45, -.55, .35, 1.25]) for (const z of [-.95, .95]) parts.push(wheel(x, z, .36, .26));
    } else if (type === 'scorpion') {
      // Low and long, four big wheels, a heavy twin-cannon turret.
      const body = loft([
        {x: -1.8, pts: [[-.62, -.72], [-.62, .72], [-.3, .82], [-.3, -.82]]},
        {x: 1.2, pts: [[-.66, -.72], [-.66, .72], [-.3, .82], [-.3, -.82]]},
        {x: 2, pts: [[-.46, -.4], [-.46, .4], [-.3, .52], [-.3, -.52]]},
      ]);
      parts.push(body);
      const turret = block(-.9, -1.05, -.42, .2, -.66, .42);
      parts.push(turret, inset(turret, 5, .6, 'window', .012, .8, .45));
      for (const z of [-.18, .18]) parts.push(block(.2, -.95, z - .06, 1.75, -.83, z + .06));
      for (const x of [-1.2, 1.15]) for (const z of [-.98, .98]) parts.push(wheel(x, z, .44, .3));
    } else {
      // The Scarab: six-wheeled explorer, a forward cab and a small turret.
      const body = loft([
        {x: -1.6, pts: [[-.8, -.72], [-.8, .72], [-.38, .8], [-.38, -.8]]},
        {x: 1.1, pts: [[-.8, -.72], [-.8, .72], [-.38, .8], [-.38, -.8]]},
        {x: 1.7, pts: [[-.62, -.5], [-.62, .5], [-.4, .6], [-.4, -.6]]},
      ]);
      const cab = block(.35, -1.2, -.58, 1.3, -.78, .58);
      parts.push(body, cab, inset(cab, 5, .75, 'window', .012, .85, .55));
      parts.push(block(-1.05, -1.02, -.26, -.45, -.8, .26), block(-.45, -.98, -.05, .5, -.9, .05));
      for (const x of [-1.15, 0, 1.15]) for (const z of [-.92, .92]) parts.push(wheel(x, z, .34, .24));
    }
    const model = merge(...parts);
    model.wheels = wheels;
    model.lights = [light([1.8, -.55, .45], [1, 0, 0], 'headlamp'), light([1.8, -.55, -.45], [1, 0, 0], 'headlamp')];
    return model;
  }

  // A skimmer drone: a squat disc with a red eye, hunting over the ground.
  function skimmer() {
    const body = cylinder(.6, .3, 8, 'hull', .38);
    const disc = turn(body, 0, 0, Math.PI / 2);
    return merge(disc, inset(disc, disc.f.length - 2, .5, 'eye', .02));
  }

  // ---------------------------------------------------------------------
  // Ports, pads and buildings.
  // ---------------------------------------------------------------------
  function hexPad(r = 1, kind = 'trim') {
    const top = Array.from({length: 6}, (_, index) => {
      const angle = index * TAU / 6;
      return [Math.cos(angle) * r, 0, Math.sin(angle) * r * .86];
    });
    const v = [...top, ...top.map(([x, , z]) => [x, .12, z])];
    const faces = [[0, 1, 2, 3, 4, 5], [6, 7, 8, 9, 10, 11]];
    for (let edge = 0; edge < 6; edge += 1) faces.push([edge, (edge + 1) % 6, (edge + 1) % 6 + 6, edge + 6]);
    return piece(v, faces, kind);
  }

  function settlementBuilding(kind, seed) {
    if (kind === 'dome') return merge(dome(.9 + seed * .3), move(block(-.2, -.4, .7, .2, 0, 1.1, 'window'), 0, 0, 0));
    if (kind === 'tower') {
      const tower = loft([
        {x: 0, pts: [[-.3, -.3], [-.3, .3], [.3, .3], [.3, -.3]]},
        {x: 2.2 + seed, pts: [[-.18, -.18], [-.18, .18], [.18, .18], [.18, -.18]]},
      ]);
      const upright = turn(tower, 0, 0, -Math.PI / 2);
      const model = merge(upright, block(-.4, -2.5 - seed, -.4, .4, -2.2 - seed, .4, 'trim'));
      model.lights = [light([0, -2.65 - seed, 0], [0, -1, 0], 'beacon')];
      return model;
    }
    if (kind === 'hangar') {
      const hangar = loft([
        {x: -1.1, pts: [[0, -.8], [-.55, -.5], [-.7, 0], [-.55, .5], [0, .8]]},
        {x: 1.1, pts: [[0, -.8], [-.55, -.5], [-.7, 0], [-.55, .5], [0, .8]]},
      ]);
      return merge(hangar, inset(hangar, hangar.f.length - 1, .6, 'window', .012, .7, .5));
    }
    const w = 1 + seed * .6;
    const hab = block(-w / 2, -1.1 - seed * .5, -.5, w / 2, 0, .5);
    return merge(hab, inset(hab, 1, .8, 'window', .012, .85, .18));
  }

  // A planetary starport: a broad ring on the ground round a central tower.
  function surfacePort() {
    const parts = [];
    for (let index = 0; index < 10; index += 1) {
      const angle = index * TAU / 10;
      const segment = turn(block(-.55, -.55, -1.1, .55, 0, 1.1), -angle, 0, 0);
      parts.push(move(segment, Math.cos(angle) * 3.2, 0, Math.sin(angle) * 3.2));
    }
    const tower = turn(loft([
      {x: 0, pts: [[-.5, -.5], [-.5, .5], [.5, .5], [.5, -.5]]},
      {x: 3.4, pts: [[-.28, -.28], [-.28, .28], [.28, .28], [.28, -.28]]},
    ]), 0, 0, -Math.PI / 2);
    const top = block(-.9, -3.9, -.9, .9, -3.3, .9);
    parts.push(tower, top, inset(top, 5, .8, 'window', .012, .9, .35));
    const model = merge(...parts);
    model.lights = [light([0, -4, 0], [0, -1, 0], 'beacon')];
    return model;
  }

  // ---------------------------------------------------------------------
  // Drives, beacons and debris.
  // ---------------------------------------------------------------------
  // One segment of the frame shift drive's containment ring; the scene
  // lights segments one at a time.
  function driveSegment() {
    return block(-.18, -.5, -.3, .18, .5, .3);
  }

  function beacon() {
    const body = box(.7, .7, .7);
    const panels = [-1, 1].map((side) => block(-.08, -.42, side * .5, .08, .42, side * 1.9, 'trim'));
    const mast = block(-.04, -1.4, -.04, .04, -.35, .04);
    const model = merge(body, inset(body, 1, .6, 'window'), ...panels, mast);
    model.lights = [light([0, -1.45, 0], [0, -1, 0], 'beacon')];
    return model;
  }

  function canister() {
    const can = cylinder(.36, 1.1, 6);
    return merge(can, inset(can, can.f.length - 1, .55, 'window'), inset(can, 1, .5, 'trim', .01, .9, .3));
  }

  // A rock: an icosahedron with each vertex pushed in or out a little and
  // the whole squashed a touch, so none of the twelve looks like another
  // and each keeps its silhouette as it tumbles. The shapes are the ones
  // the asteroid field has always drawn.
  const ROCK_SHAPES = 12;
  function rock(seed) {
    const t = (1 + Math.sqrt(5)) / 2;
    const base = [[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
      [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t], [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]];
    const faces = [[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
      [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
      [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
      [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]];
    const squash = .7 + hashOf(seed + 41) * .25;
    const v = base.map((vertex, index) => {
      const radius = (.78 + hashOf(seed * 17 + index) * .26) / Math.hypot(...vertex);
      return vertex.map((n, axis) => n * radius * (axis === 1 ? squash : 1));
    });
    return piece(v, faces, 'hull', [0, 0, 0]);
  }

  // A prospector limpet: a small hexagonal drone with a lit eye.
  function limpet() {
    const body = turn(cylinder(.5, .34, 6), Math.PI / 2, 0, 0);
    return merge(body, inset(body, body.f.length - 1, .45, 'eye', .02));
  }

  // A long crystal shard (Lagrange clouds, the Codex's specimen).
  function crystal(length = 2.4) {
    const v = [[length / 2, 0, 0], [-length / 2, 0, 0], [0, -.42, 0], [0, 0, .36], [0, .42, 0], [0, 0, -.36]];
    return piece(v, [[0, 2, 3], [0, 3, 4], [0, 4, 5], [0, 5, 2], [1, 3, 2], [1, 4, 3], [1, 5, 4], [1, 2, 5]]);
  }

  // A neutron star's jet: a long, narrow cone.
  function cone(length, radius, sides = 8) {
    return cylinder(radius, length, sides, 'jet', .02);
  }

  // ---------------------------------------------------------------------
  // The commander on foot, posed each frame: boxes hinged at the hips,
  // knees, shoulders and elbows, walking toward +x.
  // ---------------------------------------------------------------------
  function commander(stride, {walking = true, reach = 0} = {}) {
    const parts = [];
    const limb = (length, width, [px, py, pz], angle, knee = 0) => {
      const upper = move(turn(block(-width / 2, 0, -width / 2, width / 2, length, width / 2), 0, 0, angle),
        px, py, pz);
      const endX = px - Math.sin(angle) * length, endY = py + Math.cos(angle) * length;
      const lower = move(turn(block(-width / 2 * .9, 0, -width / 2 * .9, width / 2 * .9, length, width / 2 * .9),
        0, 0, angle + knee), endX, endY, pz);
      parts.push(upper, lower);
    };
    const swing = walking ? Math.sin(stride) : 0, lift = walking ? Math.cos(stride) : 0;
    const bob = walking ? Math.abs(Math.cos(stride)) * .04 : 0;
    const hip = -.92 - bob;
    for (const side of [-1, 1]) {
      const phase = side * swing;
      limb(.46, .17, [0, hip, side * .13], phase * .5, Math.max(0, -side * lift) * -.7);
    }
    const torso = block(-.16, hip - .66, -.26, .16, hip, .26);
    const pack = block(-.36, hip - .62, -.2, -.16, hip - .14, .2, 'trim');
    const head = block(-.15, hip - .98, -.14, .15, hip - .7, .14);
    parts.push(torso, pack, head, inset(head, 5, .78, 'visor', .012, .75, .5));
    for (const side of [-1, 1]) {
      limb(.34, .12, [0, hip - .6, side * .33], -side * swing * .45 + reach, -.35 - reach * .4);
    }
    const model = merge(...parts);
    model.lights = [light([.16, hip - .84, 0], [1, 0, 0], 'lamp')];
    return model;
  }

  const cache = new Map();
  const cached = (name, build) => {
    if (!cache.has(name)) cache.set(name, build());
    return cache.get(name);
  };

  window.NavigationModels = {
    merge, move, stretch, turn, box, block, loft, cylinder, dome, inset, plate,
    coriolis: () => cached('coriolis', coriolis),
    stationCity: () => cached('station-city', stationCity),
    carrier: () => cached('carrier', carrier),
    capital: () => cached('capital', capital),
    ship: (kind = 'wedge') => cached(`ship-${kind}`, () => ship(kind)),
    thargoid: () => cached('thargoid', thargoid),
    vehicle: (type = 'scarab') => cached(`vehicle-${type}`, () => vehicle(type)),
    skimmer: () => cached('skimmer', skimmer),
    hexPad: () => cached('hex-pad', () => hexPad()),
    building: (kind, seed = 0) => cached(`building-${kind}-${seed}`, () => settlementBuilding(kind, seed)),
    surfacePort: () => cached('surface-port', surfacePort),
    driveSegment: () => cached('drive-segment', driveSegment),
    beacon: () => cached('beacon', beacon),
    canister: () => cached('canister', canister),
    rock: (seed = 0) => cached(`rock-${seed % ROCK_SHAPES}`, () => rock(seed % ROCK_SHAPES)),
    limpet: () => cached('limpet', limpet),
    crystal: (length = 2.4) => cached(`crystal-${length}`, () => crystal(length)),
    cone: (length, radius) => cached(`cone-${length}-${radius}`, () => cone(length, radius)),
    commander,
  };
})();
