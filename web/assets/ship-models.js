(() => {
  'use strict';

  /*
   * Ship models
   * -----------
   * Every ship in the catalogue as a low-poly solid for the holograms, built
   * from the feel of its portrait (assets/images/ships): the plan shape, the
   * height of the hull, its pods, outriggers, wings and fins, the canopy and
   * the drives. Models use the navigation scenes' format: vertices and faces
   * in their own units, nose to +x, y down, z toward the viewer side on.
   * Faces carry a kind ('hull', 'trim', 'dark', 'glass', 'window', 'engine')
   * the scene turns into its own materials. Keys are the ship catalogue's
   * (VoidCompassShipCatalog), so the ship the HUD names is the ship it draws.
   */

  const TAU = Math.PI * 2;
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const centreOf = (points) => {
    const sum = [0, 0, 0];
    for (const point of points) for (let axis = 0; axis < 3; axis += 1) sum[axis] += point[axis];
    return sum.map((value) => value / points.length);
  };
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

  // A convex piece, its faces turned away from its own centre.
  function piece(vertices, faces, kind = 'hull') {
    const centre = centreOf(vertices);
    return {v: vertices, f: faces.map((indices) => {
      const points = indices.map((index) => vertices[index]);
      const outward = dot(normalOf(points), sub(centreOf(points), centre)) >= 0;
      return {i: outward ? indices : [...indices].reverse(), k: kind};
    })};
  }
  function merge(...parts) {
    const out = {v: [], f: []};
    for (const part of parts.flat(Infinity)) {
      if (!part) continue;
      const offset = out.v.length;
      out.v.push(...part.v);
      out.f.push(...part.f.map((face) => ({...face, i: face.i.map((index) => index + offset)})));
    }
    return out;
  }
  const move = (mesh, dx = 0, dy = 0, dz = 0) => ({...mesh, v: mesh.v.map(([x, y, z]) => [x + dx, y + dy, z + dz])});
  // Roll about the ship's length: a wing's dihedral, a pod's cant.
  const roll = (mesh, angle) => {
    const c = Math.cos(angle), s = Math.sin(angle);
    return {...mesh, v: mesh.v.map(([x, y, z]) => [x, y * c - z * s, y * s + z * c])};
  };
  const both = (build) => [build(1), build(-1)];

  // Join cross-sections ({x, pts: [[y, z], ...]}, same count) nose to tail.
  function loft(sections, kind = 'hull') {
    const n = sections[0].pts.length, v = [], faces = [];
    for (const section of sections) for (const [y, z] of section.pts) v.push([section.x, y, z]);
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
  // A hull section: `w` either side, `up` above the keel line, `down` below,
  // the top and bottom flats `t` of the width.
  const S = (x, w, up, down = up * .6, t = .5) => ({x, pts: [[0, -w], [-up, -w * t], [-up, w * t], [0, w],
    [down, w * t], [down, -w * t]]});
  // A rounded section for liners and freighters.
  const R = (x, w, up, down = up, power = .55) => ({x, pts: Array.from({length: 10}, (_, k) => {
    const a = k * TAU / 10 + Math.PI / 10, c = Math.cos(a), s = Math.sin(a);
    return [(s < 0 ? -up : down) * Math.abs(s) ** power, w * Math.sign(c) * Math.abs(c) ** power];
  })});

  // Shrink a face toward its centre and lift it clear: a lamp or panel.
  function inset(mesh, faceIndex, scale, kind, lift = .015, sx = scale, sy = scale) {
    const face = mesh.f[faceIndex], points = face.i.map((index) => mesh.v[index]);
    const centre = centreOf(points), n = normalOf(points), length = Math.hypot(...n) || 1;
    const up = n.map((value) => value / length * lift);
    const u = sub(points[1], points[0]), ul = Math.hypot(...u) || 1, ux = u.map((value) => value / ul);
    const vx = [n[1] * ux[2] - n[2] * ux[1], n[2] * ux[0] - n[0] * ux[2], n[0] * ux[1] - n[1] * ux[0]].map((value) => value / length);
    const shrunk = points.map((point) => {
      const d = sub(point, centre), a = dot(d, ux) * sx, b = dot(d, vx) * sy;
      return [0, 1, 2].map((axis) => centre[axis] + ux[axis] * a + vx[axis] * b + up[axis]);
    });
    const behind = centre.map((value, axis) => value - n[axis] / length);
    const plate = piece([...shrunk, behind], [shrunk.map((_, index) => index)], kind);
    return {v: shrunk, f: plate.f};
  }
  // The drive glow across a hull's tail.
  const drives = (hull, sx = .7, sy = .5) => inset(hull, hull.f.length - 1, .7, 'engine', .02, sx, sy);

  // A pod along x (nacelle, engine, gun) from x0 to x1, its drive at x0.
  function pod(x0, x1, r, y, z, {sides = 8, kind = 'hull', taper = 1, drive = true} = {}) {
    const ring = (radius) => Array.from({length: sides}, (_, index) => {
      const angle = index * TAU / sides + Math.PI / sides;
      return [Math.sin(angle) * radius, Math.cos(angle) * radius];
    });
    const body = move(loft([{x: x1, pts: ring(r * taper)}, {x: x0, pts: ring(r)}], kind), 0, y, z);
    return drive ? [body, drives(body, .75, .75)] : [body];
  }
  // A flat wing: a convex plan [[x, z], ...] at height y, `t` thick.
  function slab(plan, y = 0, t = .06, kind = 'hull') {
    const v = [...plan.map(([x, z]) => [x, y - t / 2, z]), ...plan.map(([x, z]) => [x, y + t / 2, z])], n = plan.length;
    const faces = [[...Array(n).keys()], [...Array(n).keys()].map((index) => index + n)];
    for (let index = 0; index < n; index += 1) faces.push([index, (index + 1) % n, (index + 1) % n + n, index + n]);
    return piece(v, faces, kind);
  }
  // An upright fin: a convex profile [[x, y], ...] at z, `t` thick.
  function fin(profile, z = 0, t = .05, kind = 'hull') {
    const v = [...profile.map(([x, y]) => [x, y, z - t / 2]), ...profile.map(([x, y]) => [x, y, z + t / 2])], n = profile.length;
    const faces = [[...Array(n).keys()], [...Array(n).keys()].map((index) => index + n)];
    for (let index = 0; index < n; index += 1) faces.push([index, (index + 1) % n, (index + 1) % n + n, index + n]);
    return piece(v, faces, kind);
  }
  // A box spanning two corners.
  function block(x0, y0, z0, x1, y1, z1, kind = 'hull') {
    const v = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]];
    return piece(v, [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [3, 2, 6, 7], [0, 3, 7, 4], [1, 2, 6, 5]], kind);
  }
  // A canopy sitting on the hull at height y (negative is up), nose to x1.
  function canopy(x0, x1, w, h, y, kind = 'glass') {
    const s = (x, k, hk) => ({x, pts: [[y, -w * k], [y - h * hk, -w * k * .45], [y - h * hk, w * k * .45], [y, w * k]]});
    return loft([s(x1, .25, .15), s(x1 - (x1 - x0) * .45, 1, 1), s(x0, .8, .55)], kind);
  }

  // ---------------------------------------------------------------------
  // The ships, by catalogue key. Lengths run about four units, nose +x.
  // ---------------------------------------------------------------------
  const SHIPS = {
    sidewinder() {
      const hull = loft([S(1.5, .8, .32, .25, .7), S(-.3, 1.55, .55, .3, .8), S(-1.3, 1.45, .5, .28, .8)]);
      return merge(hull, drives(hull, .85, .4), canopy(-.2, .9, .3, .2, -.42), block(-1.2, -.66, -.5, -.3, -.5, -.1, 'trim'));
    },
    eaglemkii() {
      const hull = loft([S(2.1, .1, .07), S(.7, .38, .32, .25), S(-1.1, .42, .32, .28), S(-1.6, .3, .26, .22)]);
      const wings = both((side) => roll(slab([[.3, side * .35], [-1.35, side * .4], [-1.75, side * 1.75], [-.75, side * 1.7]], 0, .07), side * .3));
      return merge(hull, drives(hull), canopy(.2, 1.4, .22, .2, -.28), wings, fin([[-.8, -.3], [-1.6, -.3], [-1.45, -.95]], 0));
    },
    hauler() {
      const hull = loft([S(1.9, .18, .12, .1), S(.1, .85, .48, .3), S(-1.4, 1.05, .52, .3, .6)]);
      const domes = [-.2, -.85].flatMap((x) => both((side) => pod(x - .22, x + .22, .2, -.55, side * .35, {sides: 6, drive: false})));
      return merge(hull, drives(hull, .8, .45), canopy(.6, 1.6, .2, .15, -.24), domes, both((side) => fin([[-.7, -.4], [-1.4, -.4], [-1.35, -.95]], side * .8)));
    },
    adder() {
      const hull = loft([S(2, .14, .1), R(.8, .75, .55, .35), R(-.7, 1.05, .6, .35), S(-1.5, .8, .45, .3, .6)]);
      return merge(hull, drives(hull), canopy(.3, 1.4, .25, .18, -.5), fin([[-.4, -.5], [-1.4, -.45], [-1.2, -1.25]], 0),
        both((side) => slab([[-.3, side * .9], [-1.4, side * .85], [-1.5, side * 1.35], [-.8, side * 1.3]], .15, .06, 'trim')));
    },
    vipermkiii() {
      const hull = loft([S(2.1, .22, .14, .1), S(.4, .85, .42, .22), S(-1.6, 1.35, .48, .25, .7)]);
      const deck = loft([S(1, .15, .1, 0), S(-.4, .5, .28, 0), S(-1.6, .6, .3, 0)], 'trim');
      return merge(hull, drives(hull, .8, .45), move(deck, 0, -.42, 0), canopy(.2, 1.1, .2, .16, -.5),
        both((side) => pod(-1.65, -.4, .22, -.05, side * 1.15, {sides: 6})));
    },
    vipermkiv() {
      const hull = loft([S(2.1, .25, .16, .12), S(.3, .95, .48, .26), S(-1.7, 1.25, .52, .28, .7)]);
      const deck = loft([S(.9, .15, .1, 0), S(-.5, .55, .3, 0), S(-1.7, .65, .32, 0)], 'trim');
      return merge(hull, drives(hull, .8, .45), move(deck, 0, -.48, 0), canopy(.1, 1, .2, .16, -.55),
        both((side) => pod(-1.8, .2, .3, -.02, side * 1.3, {sides: 6, taper: .7})));
    },
    cobramkiii() {
      const hull = loft([S(1.6, .35, .14, .1), S(.2, 1.6, .4, .25, .45), S(-.9, 2.3, .4, .2, .4), S(-1.1, 1.5, .34, .2, .55)]);
      return merge(hull, drives(hull, .75, .45), canopy(-.2, .9, .3, .2, -.38),
        both((side) => block(-.95, -.45, side * .5, -.25, -.36, side * 1.05, 'trim')));
    },
    cobramkiv() {
      const hull = loft([S(1.7, .4, .2, .14), S(.1, 1.45, .6, .35, .55), S(-1, 2, .6, .32, .5), S(-1.35, 1.3, .5, .3, .6)]);
      return merge(hull, drives(hull, .75, .5), canopy(-.2, .95, .32, .22, -.56),
        both((side) => block(-1.2, -.66, side * .6, -.4, -.54, side * 1.2, 'trim')));
    },
    cobramkv() {
      const hull = loft([S(2.1, .28, .12, .1), S(.4, .9, .42, .24), S(-1.6, 1.1, .52, .28, .6), S(-2, .9, .48, .28, .6)]);
      return merge(hull, drives(hull, .8, .5), canopy(.2, 1.2, .25, .18, -.42),
        both((side) => slab([[.6, side * .8], [-1.9, side * 1], [-2, side * 1.45], [-.6, side * 1.4]], .05, .14, 'trim')));
    },
    aspexplorer() {
      const hull = loft([S(1.8, .45, .25, .2), S(.5, 1, .48, .35), S(-1.3, 1.15, .45, .3)]);
      const wings = both((side) => slab([[-.1, side * .9], [-1.4, side * 1.05], [-1.7, side * 2.2], [-.7, side * 2.3]], .05, .1));
      return merge(hull, drives(hull, .8, .5), canopy(.6, 1.75, .42, .3, -.3), wings,
        both((side) => slab([[-.7, side * 2.25], [-1.6, side * 2.15], [-1.5, side * 2.35], [-.75, side * 2.4]], .05, .14, 'trim')));
    },
    aspscout() {
      const hull = loft([S(1.6, .45, .25, .2), S(.3, 1.05, .5, .35), S(-1.2, 1.15, .45, .3)]);
      return merge(hull, drives(hull, .8, .5), canopy(.4, 1.55, .4, .28, -.3),
        both((side) => slab([[-.2, side * .95], [-1.2, side * 1.05], [-1.45, side * 1.85], [-.6, side * 1.9]], .05, .1)));
    },
    diamondbackscout() {
      const hull = loft([S(1.6, .5, .4, .3, .6), S(.2, .9, .6, .4, .6), S(-1.2, .85, .55, .4, .6)]);
      return merge(hull, drives(hull, .8, .5), canopy(.6, 1.65, .45, .32, -.4),
        both((side) => pod(-1.4, .2, .35, .1, side * 1.2, {sides: 6})),
        both((side) => slab([[.2, side * .8], [-1, side * .8], [-1.1, side * 1.25], [-.1, side * 1.25]], .05, .12, 'trim')));
    },
    diamondbackexplorer() {
      const hull = loft([S(2, .5, .4, .3, .6), S(.5, .85, .6, .4, .6), S(-1.6, .9, .58, .42, .6)]);
      return merge(hull, drives(hull, .8, .5), canopy(1, 2, .45, .32, -.38),
        both((side) => pod(-1.8, .8, .32, .05, side * 1.2, {sides: 6})),
        both((side) => slab([[.6, side * .82], [-1.5, side * .85], [-1.6, side * 1.3], [.3, side * 1.3]], .05, .1, 'trim')),
        fin([[-.4, -.55], [-1.5, -.55], [-1.3, -1.05]], 0));
    },
    vulture() {
      const hull = loft([S(1.6, .32, .32, .25), S(.2, .6, .52, .4), S(-1.3, .55, .45, .35)]);
      const arms = both((side) => roll(slab([[1.1, side * .95], [-1.5, side * .95], [-1.6, side * 1.35], [.9, side * 1.35]], .05, .5), side * -.3));
      return merge(hull, drives(hull), canopy(.6, 1.6, .3, .25, -.3), arms,
        both((side) => pod(-1.6, -.9, .2, .1, side * 1.15, {sides: 6})));
    },
    ferdelance() {
      const hull = loft([S(2.3, .1, .08, .06), S(.4, .8, .5, .3, .4), S(-1.6, 1.4, .6, .35, .45), S(-1.85, .9, .5, .3, .55)]);
      return merge(hull, drives(hull, .8, .45), canopy(.2, 1.3, .28, .22, -.48),
        fin([[.2, -.48], [-1.6, -.58], [-1.4, -1.15]], 0), both((side) => slab([[-.6, side * 1], [-1.8, side * 1.3], [-1.85, side * 1.55]], .1, .06, 'trim')));
    },
    python() {
      const hull = loft([S(2, .3, .2, .14), S(.3, 1.35, .6, .35, .55), S(-1.6, 1.7, .62, .4, .6), S(-1.9, 1.25, .5, .35, .6)]);
      return merge(hull, drives(hull, .8, .5), canopy(.6, 1.7, .3, .2, -.32),
        both((side) => block(-1.5, -.74, side * .4, -.3, -.6, side * 1.1, 'trim')));
    },
    pythonmkii() {
      const hull = loft([S(2.3, .14, .1, .08), S(.5, .9, .45, .28), S(-1.6, 1.35, .48, .3, .55), S(-1.9, 1, .42, .28)]);
      return merge(hull, drives(hull, .8, .45), canopy(.4, 1.5, .26, .2, -.42),
        both((side) => slab([[.2, side * .85], [-1.3, side * 1.3], [-1.5, side * 1.9], [-.6, side * 1.85]], .1, .06)),
        fin([[-.3, -.45], [-1.6, -.5], [-1.4, -.95]], 0));
    },
    anaconda() {
      const hull = loft([S(2.4, .14, .1, .08), S(.6, .7, .4, .35), S(-1.2, 1, .55, .4), S(-2.1, .9, .7, .45)]);
      return merge(hull, drives(hull, .8, .55), block(-2.05, -1.05, -.35, -1.2, -.6, .35), canopy(-1.9, -1.2, .3, .2, -1.05),
        both((side) => fin([[-1.4, -.4], [-2.1, -.5], [-2.15, -1.1]], side * .55)),
        both((side) => slab([[.3, side * .65], [-1.6, side * .95], [-1.9, side * 1.35], [-1, side * 1.2]], .2, .06, 'trim')));
    },
    anacondamkii() {
      const hull = loft([S(2.4, .35, .2, .15, .7), S(1.5, .7, .36, .3, .8), S(-2, .8, .42, .35, .85), S(-2.3, .7, .38, .32, .8)]);
      const decks = [block(1.2, -.62, -.4, -1.6, -.4, .4, 'trim'), block(.2, -.8, -.25, -1.3, -.6, .25)];
      return merge(hull, drives(hull, .8, .55), decks, canopy(1.2, 1.9, .28, .14, -.38),
        both((side) => fin([[-1.3, .3], [-2.2, .3], [-2.3, .85]], side * .6)),
        both((side) => block(-2.2, .05, side * .78, .8, .3, side * 1.05, 'trim')));
    },
    federaldropship() {
      const hull = loft([S(2.1, .25, .2, .16), S(.6, .6, .52, .42), S(-1.6, .65, .55, .45)]);
      return merge(hull, drives(hull), canopy(.8, 1.9, .26, .2, -.32),
        both((side) => roll(slab([[0, side * .55], [-1.3, side * .6], [-1.95, side * 1.75], [-1.2, side * 1.75]], .1, .08), side * .4)),
        fin([[-.6, -.5], [-1.6, -.52], [-1.55, -1.25]], 0), both((side) => fin([[-1, .4], [-1.6, .4], [-1.65, .95]], side * .4)));
    },
    federalassaultship() {
      const hull = loft([S(2.2, .2, .16, .12), S(.6, .6, .46, .36), S(-1.6, .75, .5, .4)]);
      return merge(hull, drives(hull), canopy(.8, 1.9, .24, .18, -.28),
        both((side) => slab([[-.4, side * .6], [-1.5, side * .7], [-1.9, side * 1.9], [-1.4, side * 1.95]], .05, .08)),
        fin([[-.8, -.45], [-1.6, -.48], [-1.5, -1.05]], 0));
    },
    federalgunship() {
      const hull = loft([S(2.1, .28, .22, .18), S(.6, .7, .55, .45), S(-1.6, .8, .58, .48)]);
      return merge(hull, drives(hull), canopy(.8, 1.85, .28, .2, -.36),
        both((side) => pod(-1.4, .8, .22, .3, side * 1.05, {sides: 6})),
        both((side) => roll(slab([[-.2, side * .7], [-1.3, side * .75], [-1.9, side * 1.8], [-1.2, side * 1.8]], .1, .08), side * .35)),
        fin([[-.6, -.55], [-1.6, -.58], [-1.5, -1.2]], 0));
    },
    federalcorvette() {
      const hull = loft([S(2.5, .14, .1, .08), S(.8, .7, .42, .32), S(-1.6, 1.1, .52, .4, .55), S(-2.2, 1, .55, .42, .6)]);
      return merge(hull, drives(hull, .8, .55), canopy(.9, 2, .24, .16, -.32),
        both((side) => slab([[.6, side * .7], [-2.1, side * 1.05], [-2.2, side * 1.5], [-.2, side * 1.2]], .05, .1, 'trim')),
        fin([[-.8, -.5], [-2.1, -.55], [-2, -1.05]], 0));
    },
    imperialcourier() {
      const hull = loft([S(2.3, .1, .1, .08), S(.6, .42, .3, .25), S(-1.4, .48, .32, .26)]);
      return merge(hull, drives(hull), canopy(.6, 1.8, .22, .18, -.28),
        both((side) => pod(-1.7, .5, .2, .05, side * 1.45, {sides: 8, taper: .6})),
        both((side) => slab([[.1, side * .4], [-1, side * .42], [-1.4, side * 1.4], [-.2, side * 1.4]], .05, .06)));
    },
    imperialeagle() {
      const hull = loft([S(2.1, .1, .1, .08), S(.5, .42, .32, .25), S(-1.2, .48, .32, .26)]);
      return merge(hull, drives(hull), canopy(.5, 1.6, .22, .18, -.3),
        both((side) => pod(-1.6, -.1, .18, .2, side * 1.35, {sides: 8, taper: .7})),
        both((side) => slab([[-.1, side * .4], [-.9, side * .42], [-1.2, side * 1.3], [-.4, side * 1.3]], .1, .06)));
    },
    imperialclipper() {
      const hull = loft([S(2.2, .14, .14, .1), S(.6, .5, .38, .3), S(-1.6, .55, .4, .32)]);
      return merge(hull, drives(hull), canopy(.7, 1.8, .24, .18, -.34),
        both((side) => pod(-2, -.5, .3, .1, side * 2.1, {sides: 8, taper: .7})),
        both((side) => slab([[-.2, side * .45], [-1.2, side * .5], [-1.8, side * 2], [-.9, side * 2]], .05, .08)));
    },
    imperialcutter() {
      const hull = loft([S(2.5, .14, .14, .1), S(.6, .65, .45, .35), S(-1.8, .75, .5, .38)]);
      return merge(hull, drives(hull), canopy(.8, 2, .26, .2, -.4),
        both((side) => pod(-1.9, -.2, .32, .05, side * 1.8, {sides: 8, taper: .7})),
        both((side) => slab([[-.2, side * .6], [-1.4, side * .7], [-1.8, side * 1.75], [-.6, side * 1.75]], .05, .08)),
        fin([[-.9, -.45], [-1.8, -.5], [-1.7, -.9]], 0));
    },
    keelback() {
      const hull = loft([R(1.6, .6, .5, .4, .5), R(-.3, 1.15, .7, .5, .5), R(-1.6, 1.05, .62, .45, .5)]);
      return merge(hull, drives(hull, .75, .55), canopy(.9, 1.7, .35, .2, -.42),
        both((side) => block(-1.2, -.75, side * .3, .2, -.6, side * .9, 'trim')));
    },
    type6transporter() {
      const hull = loft([R(1.7, .5, .4, .4, .45), R(.6, 1, .62, .55, .45), R(-1.7, .95, .62, .5, .45)]);
      return merge(hull, drives(hull, .7, .55), canopy(1.1, 1.85, .3, .18, -.36), block(-1.3, -.72, -.4, .3, -.6, .4, 'trim'));
    },
    type7transporter() {
      const hull = loft([R(2, .45, .38, .35, .45), R(1.2, .9, .58, .52, .45), R(-2, .9, .58, .52, .45)]);
      const ribs = [-1.6, -.9, -.2, .5].map((x) => block(x - .2, -.72, -.75, x + .2, -.55, .75, 'trim'));
      return merge(hull, drives(hull, .7, .55), ribs, canopy(1.5, 2.05, .26, .15, -.34));
    },
    type8transporter() {
      const hull = loft([R(1.8, .5, .4, .38, .45), R(.8, .8, .55, .5, .45), R(-1.6, .85, .55, .5, .45)]);
      return merge(hull, drives(hull, .7, .55), canopy(1.2, 1.95, .28, .16, -.36),
        both((side) => pod(-1.9, -.2, .32, .1, side * 1.2, {sides: 8})),
        both((side) => block(-1.4, -.1, side * .8, -.6, .1, side * 1, 'trim')));
    },
    type9heavy() {
      const hull = loft([S(1.9, .8, .5, .4, .7), S(.5, 1.6, .8, .6, .8), S(-1.8, 1.6, .78, .58, .85)]);
      return merge(hull, drives(hull, .8, .55), canopy(1.2, 2, .4, .2, -.5),
        both((side) => block(-1.6, -.92, side * .5, .2, -.75, side * 1.3, 'trim')));
    },
    type10defender() {
      const hull = loft([S(1.9, .8, .5, .4, .7), S(.5, 1.6, .8, .6, .8), S(-1.8, 1.6, .78, .58, .85)]);
      return merge(hull, drives(hull, .8, .55), canopy(1.2, 2, .4, .2, -.5),
        both((side) => pod(-.8, 1.6, .22, -.75, side * .9, {sides: 6, drive: false})),
        both((side) => fin([[-.6, -.7], [-1.7, -.75], [-1.6, -1.35]], side * 1.2)));
    },
    type11prospector() {
      const hull = loft([S(1.5, .4, .35, .3), S(-.3, .62, .48, .42), S(-1.6, .6, .45, .4)]);
      return merge(hull, drives(hull), canopy(.6, 1.5, .25, .18, -.36),
        both((side) => block(-1, -.08, side * .55, .7, .08, side * 1.35, 'trim')),
        both((side) => pod(.2, 1.9, .26, 0, side * 1.45, {sides: 8, drive: false})),
        both((side) => pod(-1.9, -.9, .3, .1, side * 1.1, {sides: 8})));
    },
    belugaliner() {
      const hull = loft([R(2.4, .3, .3, .3, .7), R(1.6, .8, .72, .6, .6), R(-.4, .72, .62, .52, .6), R(-2, .35, .36, .3, .6)]);
      return merge(hull, drives(hull, .7, .65), canopy(1.4, 2.35, .45, .2, -.66, 'window'),
        both((side) => slab([[1.2, side * .75], [.2, side * .7], [-.2, side * 1.6], [.4, side * 1.6]], .1, .06)),
        both((side) => roll(fin([[-1.2, -.3], [-2, -.3], [-2.1, -1.1], [-1.75, -1.1]], 0), side * .5)));
    },
    dolphin() {
      const hull = loft([R(2, .32, .32, .3, .7), R(1, .72, .62, .52, .6), R(-1.6, .55, .48, .42, .6)]);
      return merge(hull, drives(hull, .7, .65), canopy(.8, 1.95, .42, .2, -.56, 'window'),
        both((side) => slab([[-.4, side * .5], [-1.4, side * .5], [-1.7, side * 1.25], [-1, side * 1.25]], .1, .06)),
        fin([[-.7, -.4], [-1.55, -.42], [-1.65, -.95]], 0));
    },
    orca() {
      const hull = loft([R(2.3, .22, .22, .2, .7), R(1, .62, .52, .42, .6), R(-1.8, .55, .5, .4, .6)]);
      return merge(hull, drives(hull, .7, .65), canopy(.6, 2.2, .4, .16, -.46, 'window'),
        fin([[-.6, -.45], [-1.8, -.48], [-1.9, -1.2]], 0), fin([[-1, .38], [-1.8, .4], [-1.95, .95]], 0),
        both((side) => slab([[.4, side * .55], [-.6, side * .55], [-.9, side * 1.15], [-.2, side * 1.1]], .1, .05)));
    },
    mamba() {
      const hull = loft([S(2.2, .12, .1, .08), S(.4, .5, .34, .2), S(-1.8, .7, .4, .25)]);
      return merge(hull, drives(hull), canopy(-.2, .8, .22, .18, -.32),
        both((side) => pod(-1.9, 2.4, .18, .05, side * .95, {sides: 6, taper: .3})),
        both((side) => slab([[1, side * .4], [-1.6, side * .65], [-1.7, side * .95], [.9, side * .95]], .05, .06, 'trim')));
    },
    kraitmkii() {
      const hull = loft([S(1.8, .3, .2, .14), S(.2, 1.55, .45, .3, .55), S(-1.6, 1.75, .5, .3, .6)]);
      return merge(hull, drives(hull, .8, .45), canopy(.4, 1.6, .3, .22, -.32),
        both((side) => pod(-.4, 1.9, .14, .05, side * 1.2, {sides: 6, drive: false})),
        both((side) => block(-1.4, -.6, side * .3, -.2, -.45, side * 1.1, 'trim')));
    },
    kraitphantom() {
      const hull = loft([S(1.8, .3, .16, .12), S(.2, 1.6, .36, .25, .5), S(-1.6, 1.85, .4, .25, .55)]);
      return merge(hull, drives(hull, .8, .4), canopy(.4, 1.6, .3, .18, -.26),
        both((side) => pod(-.2, 2, .1, .05, side * 1.25, {sides: 6, drive: false})),
        both((side) => slab([[-1.2, side * 1.6], [-2.1, side * 1.9], [-2.2, side * 2.2], [-1.2, side * 1.9]], .05, .05, 'trim')));
    },
    alliancechieftain() {
      const hull = loft([S(2, .2, .2, .16), S(.5, .6, .5, .4), S(-1.4, .62, .46, .38)]);
      return merge(hull, drives(hull), canopy(.8, 1.8, .26, .2, -.32),
        both((side) => [-1, 1].map((up) => pod(-1.7, -.3, .26, up * .65, side * 1.3, {sides: 6}))),
        both((side) => [-1, 1].map((up) => block(-1.3, up * .65 - .06, side * .5, -.7, up * .65 + .06, side * 1.2, 'trim'))));
    },
    alliancechallenger() {
      const hull = loft([S(2, .26, .24, .2), S(.5, .72, .58, .46), S(-1.4, .74, .55, .45)]);
      return merge(hull, drives(hull), canopy(.8, 1.8, .3, .22, -.4),
        both((side) => [-1, 1].map((up) => pod(-1.7, -.2, .3, up * .7, side * 1.35, {sides: 6}))),
        both((side) => [-1, 1].map((up) => block(-1.3, up * .7 - .07, side * .6, -.6, up * .7 + .07, side * 1.25, 'trim'))));
    },
    alliancecrusader() {
      const hull = loft([S(2, .26, .26, .2), S(.5, .75, .62, .46), S(-1.4, .78, .6, .46)]);
      return merge(hull, drives(hull), canopy(.6, 1.8, .38, .3, -.44),
        both((side) => [-1, 1].map((up) => pod(-1.7, -.4, .28, up * .7, side * 1.35, {sides: 6}))),
        both((side) => [-1, 1].map((up) => block(-1.3, up * .7 - .07, side * .6, -.7, up * .7 + .07, side * 1.25, 'trim'))),
        both((side) => fin([[.4, -.4], [-.8, -.5], [-.6, -.95]], side * .4)));
    },
    corsair() {
      const hull = loft([S(2.2, .12, .12, .1), S(.6, .45, .34, .26), S(-1.4, .5, .34, .28)]);
      return merge(hull, drives(hull), canopy(.6, 1.7, .22, .18, -.3),
        both((side) => slab([[-1.1, side * .45], [-.4, side * .45], [1.3, side * 1.75], [1.1, side * 1.95]], .05, .07)),
        both((side) => pod(-1.4, .1, .14, .05, side * .9, {sides: 6, taper: .5})));
    },
    mandalay() {
      const hull = loft([S(2.3, .1, .08, .06), S(.6, .4, .28, .22), S(-1.6, .45, .3, .24)]);
      return merge(hull, drives(hull), canopy(.7, 1.9, .2, .16, -.26),
        both((side) => slab([[.4, side * .4], [-.6, side * .42], [-1.6, side * 1.9], [-1.2, side * 1.95]], .05, .06)),
        pod(-1.8, -.4, .2, -.42, 0, {sides: 6}), fin([[-.9, -.5], [-1.6, -.5], [-1.7, -.95]], 0));
    },
    lynxhighliner() {
      const hull = loft([R(2.1, .45, .45, .4, .6), R(1.5, .7, .62, .5, .5), R(-2.1, .7, .62, .5, .5)]);
      const windows = [-.2, .2].map((y) => both((side) => block(-1.8, y - .05, side * .72, 1.4, y + .05, side * .74, 'window')));
      return merge(hull, drives(hull, .7, .6), windows, canopy(1.5, 2.1, .36, .16, -.5), block(-1.6, -.78, -.35, .8, -.6, .35, 'trim'));
    },
    pantherclippermkii() {
      const hull = loft([R(1.8, .8, .6, .55, .55), R(.6, 1.15, .8, .7, .5), R(-1.5, 1.1, .78, .68, .5)]);
      return merge(hull, drives(hull, .7, .55), canopy(1.3, 1.95, .5, .2, -.5),
        both((side) => [-1, 1].map((up) => pod(-1.9, -.4, .32, up * .55, side * 1.5, {sides: 8}))),
        both((side) => block(-1.4, -.08, side * 1, -.9, .08, side * 1.25, 'trim')));
    },
    caspianexplorer() {
      const hull = loft([S(1.8, .7, .26, .18, .55), S(.8, 1.6, .38, .26, .65), S(-.4, 1.45, .36, .26, .65), S(-1.6, .75, .5, .5, .7)]);
      return merge(hull, drives(hull, .7, .6), canopy(.9, 1.75, .45, .18, -.34),
        [-1, 0, 1].map((k) => pod(-2.2, -1, .26, .25 + Math.abs(k) * -.15, k * .55, {sides: 8})));
    },
    kestrelmkii() {
      const hull = loft([S(1.8, .1, .08, .06), S(.5, .32, .26, .2), S(-1.3, .38, .26, .2)]);
      return merge(hull, drives(hull), canopy(.3, 1.3, .18, .16, -.24),
        both((side) => slab([[-.1, side * .32], [-.9, side * .36], [-1.3, side * 1.7], [-.2, side * 1.5]], .05, .05)),
        both((side) => fin([[-.8, -.2], [-1.3, -.22], [-1.4, -.65]], side * .3)));
    },
    taipan() {
      const hull = loft([S(1.6, .1, .08, .06), S(.4, .3, .26, .2), S(-1.2, .34, .24, .2)]);
      return merge(hull, drives(hull), canopy(.2, 1.1, .18, .16, -.24),
        both((side) => slab([[.1, side * .3], [-.9, side * .32], [-1.2, side * 1.3], [-.8, side * 1.3]], .05, .05)),
        both((side) => roll(fin([[-.6, -.2], [-1.2, -.22], [-1.25, -.75]], side * .25), side * .3)));
    },
  };
  const ALIASES = {fighter: 'taipan'};

  const normalise = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  const cache = new Map();
  function get(key) {
    const name = ALIASES[normalise(key)] || normalise(key);
    if (!SHIPS[name]) return null;
    if (!cache.has(name)) cache.set(name, SHIPS[name]());
    return cache.get(name);
  }

  window.ShipModels = Object.freeze({
    keys: Object.freeze(Object.keys(SHIPS)),
    has: (key) => Boolean(SHIPS[ALIASES[normalise(key)] || normalise(key)]),
    get,
  });
})();
