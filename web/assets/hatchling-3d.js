// The Hatchling's shared Three.js renderer (5.6.7). The life simulation and
// its canvas effects stay shared; this replaces only the creature itself.
import * as THREE from "../galactic_map/vendor/three.module.min.js";

const SIZE = 384;
const SPHERE = new THREE.SphereGeometry(1, 32, 24);
const PLANE = new THREE.PlaneGeometry(2.8, 1.35);
let GLOW_TEXTURE = null;

function colour(hex) {
  return new THREE.Color(hex || "#ffffff");
}

function material(hex, options = {}) {
  return new THREE.MeshPhysicalMaterial({
    color: colour(hex), roughness: .34, metalness: .08, clearcoat: .72,
    clearcoatRoughness: .24, ...options,
  });
}

function ball(parent, hex, position, scale, options = {}) {
  const mesh = new THREE.Mesh(SPHERE, material(hex, options));
  mesh.position.set(...position);
  mesh.scale.set(...scale);
  parent.add(mesh);
  return mesh;
}

function skinTexture(tone, style) {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = tone.light;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  let seed = [...`${tone.light}:${tone.dark}:${style}`].reduce((value, char) => (value * 33 + char.charCodeAt(0)) >>> 0, 5381);
  const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  for (let i = 0; i < (style === "chitin" ? 0 : 190); i += 1) {
    const x = random() * 256, y = random() * 128, radius = 1.5 + random() * 8;
    ctx.globalAlpha = style === "tech" ? .06 + random() * .08 : .08 + random() * .15;
    ctx.fillStyle = random() > .48 ? tone.dark : tone.glow;
    ctx.beginPath();
    ctx.ellipse(x, y, radius * (1 + random()), radius * (.45 + random() * .8), random() * Math.PI, 0, Math.PI * 2);
    ctx.fill();
  }
  // Fine surface wear gives the close-up model something to catch the light.
  // It is seeded per material, so the pattern stays still between frames.
  for (let i = 0; i < 2400; i += 1) {
    ctx.globalAlpha = .025 + random() * .085;
    ctx.fillStyle = i % 3 ? tone.dark : "#ffffff";
    const x = random() * 256, y = random() * 128;
    ctx.fillRect(x, y, style === "tech" ? 1 + random() * 3 : 1, .5 + random());
  }
  ctx.globalAlpha = 1;
  if (style === "tech") {
    ctx.globalAlpha = .28;
    ctx.strokeStyle = tone.dark;
    ctx.lineWidth = 2;
    for (let y = 12; y < 128; y += 20) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(256, y); ctx.stroke();
    }
    ctx.strokeStyle = tone.line;
    ctx.lineWidth = 1.2;
    for (let i = 0; i < 18; i += 1) {
      const x = random() * 256, y = random() * 128, width = 8 + random() * 28;
      ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + width * .35, y); ctx.lineTo(x + width * .55, y + (random() - .5) * 12); ctx.lineTo(x + width, y + (random() - .5) * 12); ctx.stroke();
    }
    ctx.globalAlpha = .8;
    for (let i = 0; i < 24; i += 1) {
      ctx.fillStyle = i % 2 ? tone.line : tone.glow;
      ctx.beginPath(); ctx.arc(random() * 256, random() * 128, 1.2 + random() * 1.2, 0, Math.PI * 2); ctx.fill();
    }
  } else if (style === "cell") {
    ctx.globalAlpha = .26;
    ctx.strokeStyle = tone.vein;
    ctx.lineWidth = 1.2;
    for (let i = 0; i < 38; i += 1) {
      const x = random() * 256, y = random() * 128, radius = 3 + random() * 9;
      ctx.beginPath(); ctx.ellipse(x, y, radius * 1.25, radius, random() * Math.PI, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.globalAlpha = .35;
    for (let i = 0; i < 18; i += 1) {
      ctx.fillStyle = tone.glow;
      ctx.beginPath(); ctx.arc(random() * 256, random() * 128, 2 + random() * 4, 0, Math.PI * 2); ctx.fill();
    }
  } else if (style === "chitin") {
    ctx.lineCap = "round";
    for (let i=0;i<140;i++) {
      const x=random()*256,y=random()*128,length=6+random()*22;
      ctx.strokeStyle=i%3?tone.dark:tone.vein;ctx.globalAlpha=i%3?.5:.14;ctx.lineWidth=.35+random()*.7;
      ctx.beginPath();ctx.moveTo(x,y);ctx.bezierCurveTo(x+3,y-length*.3,x-4,y-length*.7,x+random()*7,y-length);ctx.stroke();
    }
  } else {
    ctx.globalAlpha = .22;
    ctx.strokeStyle = tone.vein;
    ctx.lineCap = "round";
    ctx.lineWidth = 2;
    for (let i = 0; i < 13; i += 1) {
      const x = random() * 256, y = random() * 128, bend = (random() - .5) * 60;
      ctx.beginPath(); ctx.moveTo(x, y);
      ctx.bezierCurveTo(x + bend, y - 22, x - bend, y + 22, x + (random() - .5) * 50, y + (random() - .5) * 38);
      ctx.stroke();
    }
  }
  ctx.globalAlpha = 1;
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.anisotropy = 4;
  return texture;
}

function texturedBall(parent, tone, style, position, scale, options = {}) {
  const map = skinTexture(tone, style);
  const mesh = new THREE.Mesh(SPHERE, material("#ffffff", {map, bumpMap: map, bumpScale: style === "tech" ? .025 : .045, ...options}));
  mesh.position.set(...position);
  mesh.scale.set(...scale);
  parent.add(mesh);
  return mesh;
}

function glowTexture() {
  if (GLOW_TEXTURE) return GLOW_TEXTURE;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext("2d");
  const gradient = ctx.createRadialGradient(64, 64, 1, 64, 64, 63);
  gradient.addColorStop(0, "rgba(255,255,255,.78)");
  gradient.addColorStop(.18, "rgba(255,255,255,.42)");
  gradient.addColorStop(.52, "rgba(255,255,255,.12)");
  gradient.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 128, 128);
  GLOW_TEXTURE = new THREE.CanvasTexture(canvas);
  GLOW_TEXTURE.colorSpace = THREE.SRGBColorSpace;
  return GLOW_TEXTURE;
}

function glowSprite(parent, position, scale, hex, opacity = .7) {
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({map: glowTexture(), color: hex, transparent: true, opacity,
    blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false}));
  sprite.position.set(...position);
  sprite.scale.set(...scale);
  parent.add(sprite);
  return sprite;
}

function tube(parent, points, hex, radius = .018, options = {}) {
  const curve = new THREE.CatmullRomCurve3(points.map((point) => new THREE.Vector3(...point)));
  const mesh = new THREE.Mesh(new THREE.TubeGeometry(curve, Math.max(12, points.length * 5), radius, 8, false),
    material(hex, options));
  parent.add(mesh);
  return mesh;
}

function rod(parent, start, end, hex, radius = .025, options = {}) {
  const a = new THREE.Vector3(...start), b = new THREE.Vector3(...end), delta = b.clone().sub(a);
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius * .72, radius, delta.length(), 12), material(hex, options));
  mesh.position.copy(a).add(b).multiplyScalar(.5);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), delta.normalize());
  parent.add(mesh);
  return mesh;
}

// Small, bevelled armour plates read as actual fitted parts under the lights,
// instead of linework painted on a sphere. Coordinates are local to the model.
function panel(parent, points, hex, options = {}) {
  const shape = new THREE.Shape();
  points.forEach(([x, y], index) => index ? shape.lineTo(x, y) : shape.moveTo(x, y));
  shape.closePath();
  const mesh = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, {
    depth: options.depth ?? .035, bevelEnabled: true, bevelThickness: .012,
    bevelSize: .014, bevelSegments: 2, curveSegments: 3,
  }), material(hex, {metalness: options.metalness ?? .65, roughness: options.roughness ?? .36,
    emissive: options.emissive || "#000000", emissiveIntensity: options.emissiveIntensity ?? 0}));
  mesh.position.set(...(options.position || [0, 0, 0]));
  mesh.rotation.set(...(options.rotation || [0, 0, 0]));
  parent.add(mesh);
  return mesh;
}

function fastener(parent, x, y, z, tone = "#8b9ba5", size = .028) {
  const bolt = new THREE.Mesh(new THREE.CylinderGeometry(size, size, .012, 8),
    material(tone, {metalness: .82, roughness: .36}));
  bolt.rotation.x = Math.PI / 2;
  bolt.position.set(x, y, z);
  parent.add(bolt);
  rod(parent, [x - size * .45, y, z + .009], [x + size * .45, y, z + .009], "#263039", .004,
    {metalness: .7, roughness: .45});
}

function shellRib(parent, y, width, depth, tone, strength = .35) {
  tube(parent, [[-width, y - .06, depth - .18], [-width * .67, y + .015, depth - .03],
    [0, y + .065, depth], [width * .67, y + .015, depth - .03], [width, y - .06, depth - .18]],
  tone, .012, {roughness: .45, metalness: .12, emissive: tone, emissiveIntensity: strength});
}

function sparkField(parent, tone, species) {
  const group = new THREE.Group();
  parent.add(group);
  const count = species === "sample" ? 13 : species === "bot" ? 9 : 11;
  const sparks = [];
  for (let i = 0; i < count; i += 1) {
    const size = .038 + (i % 3) * .014;
    const mesh = new THREE.Mesh(new THREE.OctahedronGeometry(size, 0), material(i % 3 ? tone.glow : tone.line, {
      emissive: tone.glow, emissiveIntensity: 2.1, metalness: .35, roughness: .2,
    }));
    group.add(mesh);
    const glow = i % 3 === 0 ? glowSprite(group, [0, 0, 0], [size * 4.8, size * 4.8, 1], tone.glow, .52) : null;
    sparks.push({mesh, glow, angle: i * Math.PI * 2 / count, radius: .83 + (i % 3) * .09, size});
  }
  return sparks;
}

function dispose(group) {
  group.traverse((object) => {
    if (object.geometry && object.geometry !== SPHERE && object.geometry !== PLANE) object.geometry.dispose();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.filter(Boolean).forEach((entry) => {
      new Set([entry.map, entry.bumpMap, entry.normalMap, entry.roughnessMap].filter(Boolean))
        .forEach((texture) => { if (texture !== GLOW_TEXTURE) texture.dispose(); });
      entry.dispose();
    });
  });
}

function eyes(parent, tone, {bot = false, small = false} = {}) {
  const parts = [];
  const gap = small ? .25 : .29;
  for (const side of [-1, 1]) {
    const eye = new THREE.Group();
    eye.position.set(side * gap, .15, bot ? .59 : .62);
    parent.add(eye);
    if (!bot) ball(eye, tone.dark, [0, 0, .015], [.135, .15, .07], {roughness: .3, clearcoat: .7});
    const iris = ball(eye, bot ? tone.iris : tone.line, [0, -.005, .085], [bot ? .115 : .085, bot ? .105 : .092, .055], {
      emissive: tone.iris, emissiveIntensity: .18, roughness: .23,
    });
    const pupil = ball(eye, bot ? tone.glow : "#071315", [0, 0, .13], [.043, .055, .03], {
      emissive: bot ? tone.glow : "#000000", emissiveIntensity: bot ? .8 : 0, roughness: .12,
    });
    ball(eye, "#ffffff", [-.027, .038, .16], [.014, .014, .009], {roughness: .08, emissive: "#ffffff", emissiveIntensity: .1});
    parts.push({eye, iris, pupil});
  }
  return parts;
}

function face(parent, pet, tone, {bot = false, small = false} = {}) {
  if (bot) {
    ball(parent, "#15232b", [0, .13, .51], [.57, .33, .14], {
      color: colour("#15232b"), emissive: tone.iris, emissiveIntensity: .13, roughness: .2, metalness: .55,
    });
    tube(parent, [[-.47, .15, .59], [-.25, .39, .57], [.25, .39, .57], [.47, .15, .59]], tone.line, .014,
      {emissive: tone.line, emissiveIntensity: .7, metalness: .35});
  }
  const parts = eyes(parent, tone, {bot, small});
  if (pet.dormant) {
    for (const part of parts) {
      part.eye.children.forEach((child) => { child.visible = false; });
      tube(part.eye, [[-.105, -.095, .19], [.105, .095, .19]], tone.line, .014, {emissive: tone.glow, emissiveIntensity: .72});
      tube(part.eye, [[-.105, .095, .19], [.105, -.095, .19]], tone.line, .014, {emissive: tone.glow, emissiveIntensity: .72});
    }
  }
  const mouthY = bot ? -.12 : -.22;
  const happy = ["HAPPY", "EXCITED"].includes(pet.mood_word) || ["happy", "treat", "excited", "hatched", "grown", "revived", "cured", "clean", "petted", "play"].includes(pet.reaction);
  const mouthPoints = happy
    ? [[-.13, mouthY + .035, .68], [-.07, mouthY - .005, .7], [0, mouthY - .015, .705], [.07, mouthY - .005, .7], [.13, mouthY + .035, .68]]
    : [[-.12, mouthY, .69], [0, mouthY - .015, .71], [.12, mouthY, .69]];
  tube(parent, mouthPoints, bot ? tone.glow : tone.iris, .018, {emissive: tone.glow, emissiveIntensity: .42});
  return parts;
}

function makeEgg(root, pet, tone) {
  const shell = new THREE.Group();
  shell.position.y = -.2;
  root.add(shell);
  texturedBall(shell, tone, pet.species === "bot" ? "tech" : "organic", [0, 0, 0], [.68, .9, .52], {
    roughness: .23, metalness: pet.species === "bot" ? .42 : .12, clearcoat: 1, emissive: tone.dark, emissiveIntensity: .28,
  });
  // The three eggs have distinct construction: a field capsule, a living
  // carapace, and the translucent membrane around an exobiology sample.
  if (pet.species === "bot") {
    for (const side of [-1, 1]) {
      panel(shell, [[0, 0], [side * .18, .12], [side * .21, .48], [side * .08, .57], [0, .45]], tone.dark,
        {position: [side * .32, -.2, .39], rotation: [0, side * .24, 0], metalness: .84});
      for (const y of [-.12, .13, .36]) fastener(shell, side * .4, y, .47, tone.line, .018);
    }
    for (let i = 0; i < 5; i += 1) {
      rod(shell, [-.26 + i * .13, -.56, .41], [-.26 + i * .13, -.47, .46], tone.line, .011,
        {metalness: .8, emissive: tone.glow, emissiveIntensity: .22});
    }
  } else {
    for (const [y, width, depth] of [[.62, .29, .4], [.38, .5, .49], [-.18, .57, .5], [-.46, .43, .4]]) {
      shellRib(shell, y, width, depth, pet.species === "sample" ? tone.vein : tone.dark, .18);
    }
    for (const side of [-1, 1]) {
      for (let i = 0; i < 4; i += 1) {
        const y = -.37 + i * .23, x = side * (.39 + .07 * Math.cos(y * 3));
        ball(shell, tone.line, [x, y, .42], [.025, .034, .015], {emissive: tone.glow, emissiveIntensity: .35, roughness: .36});
      }
    }
  }
  if (pet.species === "thargoid") {
    // The shell hints at the radial form it will unfurl after hatching.
    for (let i = 0; i < 8; i += 1) {
      const ray = new THREE.Group();
      ray.rotation.z = i * Math.PI * 2 / 8;
      ray.position.set(.05, .06, .45);
      shell.add(ray);
      tube(ray, [[0, .12, 0], [.06, .29, .04], [.035, .48, .02], [0, .59, -.02]], tone.line, .013,
        {emissive: tone.glow, emissiveIntensity: .42, roughness: .36});
      ball(ray, tone.glow, [.035, .35, .045], [.022, .035, .012], {emissive: tone.glow, emissiveIntensity: 1.05});
    }
  }
  // Keep the egg's shell clean: a torus around its base read as a halo/ring
  // around the pet, which doesn't belong on any Hatchling.
  tube(shell, [[-.17, .81, .31], [-.11, .64, .46], [-.22, .49, .48], [-.08, .33, .51], [-.15, .15, .51]], tone.glow, .022,
    {emissive: tone.glow, emissiveIntensity: 1.25});
  tube(shell, [[-.2, .5, .48], [-.39, .43, .42], [-.47, .28, .36]], tone.line, .012,
    {emissive: tone.line, emissiveIntensity: .9});
  tube(shell, [[-.08, .34, .51], [.13, .27, .51], [.19, .09, .49]], tone.line, .012,
    {emissive: tone.line, emissiveIntensity: .8});
  const core = ball(shell, tone.glow, [.16, .39, .5], [.055, .055, .035], {emissive: tone.glow, emissiveIntensity: 2.1});
  const coreGlow = glowSprite(shell, [.16, .39, .47], [.42, .42, 1], tone.glow, .74);
  return {body: shell, eyes: [], appendages: [], core, coreGlow};
}

function formMarks(parent, pet, tone) {
  const details = new THREE.Group();
  parent.add(details);
  if (pet.form === "rare") {
    for (let i = -2; i <= 2; i += 1) {
      const spike = new THREE.Mesh(new THREE.ConeGeometry(.075, .25 + (2 - Math.abs(i)) * .035, 5), material(tone.glow, {
        emissive: tone.glow, emissiveIntensity: 1.15, metalness: .18, roughness: .18,
      }));
      spike.position.set(i * .15, .75 - Math.abs(i) * .025, .28);
      spike.rotation.z = i * -.12;
      details.add(spike);
    }
  } else if (pet.form === "scarred") {
    ball(details, "#4a2522", [.5, -.12, .55], [.12, .22, .08], {roughness: .72, metalness: .2});
    tube(details, [[.39, .28, .57], [.48, .12, .64], [.4, -.02, .63], [.54, -.2, .53]], "#ff9a4a", .018,
      {emissive: "#ff7b43", emissiveIntensity: .75, roughness: .27});
  } else if (pet.form === "explored") {
    const sensor = new THREE.Mesh(new THREE.TorusGeometry(.115, .018, 8, 24), material(tone.line, {
      emissive: tone.glow, emissiveIntensity: .75, metalness: .42,
    }));
    sensor.position.set(-.52, -.24, .48);
    details.add(sensor);
    ball(details, tone.glow, [-.52, -.24, .49], [.035, .035, .025], {emissive: tone.glow, emissiveIntensity: 1.4});
  }
  return details;
}

function makeLarva(root, pet, tone) {
  const body = new THREE.Group();
  root.add(body);
  const grown = pet.stage === "adult" ? 1.12 : pet.stage === "juvenile" ? 1.02 : .86;
  body.scale.setScalar(grown);
  const tail = new THREE.Group();
  tail.position.set(0, -.65, -.17);
  body.add(tail);
  ball(tail, tone.dark, [0, -.29, 0], [.39, .48, .28], {roughness: .5, metalness: .08});
  texturedBall(tail, tone, "organic", [0, -.29, .11], [.34, .44, .22],
    {roughness: .42, metalness: .04, emissive: tone.dark, emissiveIntensity: .08});
  for (let i = 0; i < 3; i += 1) {
    const y = -.22 - i * .12;
    shellRib(tail, y, .28 - i * .035, .31 - i * .025, tone.dark, .12);
  }
  ball(body, tone.dark, [0, -.25, -.06], [.76, .78, .5], {roughness: .48, metalness: .06});
  texturedBall(body, tone, "organic", [0, -.11, .2], [.72, .72, .48],
    {emissive: tone.dark, emissiveIntensity: .1, roughness: .45, clearcoat: .38});
  // Layered carapace plates frame its eyes and give the larva a sharp silhouette.
  for (const side of [-1, 1]) {
    ball(body, tone.dark, [side * .56, -.18, .2], [.27, .43, .24], {roughness: .36, metalness: .14});
    panel(body, [[side * .43,.46], [side * .63,.31], [side * .7,.02],
      [side * .62,-.28], [side * .48,-.32], [side * .5,-.04], [side * .47,.22]], tone.dark,
      {position: [0, 0, .36], metalness: .15, roughness: .52});
    ball(body, tone.dark, [side * .43, .37, .33], [.28, .18, .14], {roughness: .42, metalness: .1});
    tube(body, [[side * .18, .43, .55], [side * .37, .5, .48], [side * .58, .4, .35]], tone.vein, .013,
      {roughness: .42, emissive: tone.glow, emissiveIntensity: .27});
    // Overlapping chitin along the flank, with luminous respiratory pores.
    for (let i = 0; i < 3; i += 1) {
      const y = .24 - i * .23;
      ball(body, i % 2 ? tone.dark : tone.vein, [side * (.58 + i * .012), y, .29], [.15, .11, .09],
        {roughness: .52, metalness: .08, emissive: tone.dark, emissiveIntensity: .16});
      ball(body, tone.glow, [side * (.61 + i * .012), y, .37], [.021, .021, .015],
        {roughness: .3, emissive: tone.glow, emissiveIntensity: .75});
    }
    const crest = new THREE.Mesh(new THREE.ConeGeometry(.11, .38, 6), material(tone.line, {
      emissive: tone.glow, emissiveIntensity: .52, metalness: .25, roughness: .26,
    }));
    crest.position.set(side * .43, .54, .15);
    crest.rotation.z = side * -.42;
    body.add(crest);
  }
  for (let i = 0; i < 3; i += 1) {
    const y = .67 - i * .13;
    tube(body, [[-.56, y - .07, .34], [-.34, y + .035, .54], [0, y + .09, .63], [.34, y + .035, .54], [.56, y - .07, .34]],
      i % 2 ? tone.line : tone.vein, .021, {emissive: i % 2 ? tone.line : tone.glow, emissiveIntensity: .72, roughness: .3});
  }
  for (let i = 0; i < 4; i += 1) {
    const y = -.28 - i * .105;
    shellRib(body, y, .36 - i * .025, .64 - i * .025, tone.dark, .12);
  }
  const feelers = [];
  for (const side of [-1, 1]) {
    for (let i = 0; i < 3; i += 1) {
      const y = .12 - i * .22;
      tube(body, [[0, -.42, .61], [side * .22, y, .59], [side * (.4 + i * .025), y + .1, .48], [side * .57, y - .02, .33]],
        tone.vein, .009, {emissive: tone.glow, emissiveIntensity: .58, transparent: true, opacity: .78});
      ball(body, tone.glow, [side * .57, y - .02, .35], [.025, .025, .025], {emissive: tone.glow, emissiveIntensity: 1.7});
    }
  }
  const core = ball(body, tone.vein, [0, -.48, .57], [.18, .18, .09], {transparent: true, opacity: .9,
    emissive: tone.glow, emissiveIntensity: 1.8, roughness: .12});
  const coreGlow = glowSprite(body, [0, -.48, .69], [.72, .72, 1], tone.glow, .72);
  for (const side of [-1, 1]) {
    const feeler = new THREE.Group();
    feeler.position.set(side * .31, .49, .22);
    body.add(feeler);
    tube(feeler, [[0, 0, 0], [side * .1, .18, .04], [side * .22, .36, .02], [side * .31, .46, .02]], tone.vein, .025,
      {emissive: tone.line, emissiveIntensity: .65});
    ball(feeler, tone.glow, [side * .31, .46, .02], [.055, .055, .055], {emissive: tone.glow, emissiveIntensity: 1.3});
    feelers.push(feeler);
  }
  const legs = [];
  const pairs = pet.stage === "adult" ? 3 : 2;
  for (const side of [-1, 1]) {
    for (let i = 0; i < pairs; i += 1) {
      const y = -.34 - i * .17;
      const reach = i === 2 ? .39 : .48;
      const limb = new THREE.Group();
      limb.position.set(side * .49, y, .12);
      body.add(limb);
      tube(limb, [[0, 0, 0], [side * .22, -.08, .03], [side * .32, -reach * .58, .08], [side * .2, -reach, .1]], tone.light, .04,
        {emissive: tone.dark, emissiveIntensity: .18});
      ball(limb, tone.dark, [side * .22, -.08, .03], [.064, .06, .055], {roughness: .45, metalness: .08});
      ball(limb, tone.line, [side * .2, -reach, .1], [.07, .06, .07], {emissive: tone.glow, emissiveIntensity: .65});
      legs.push(limb);
    }
  }
  const eyeParts = face(body, pet, tone);
  return {body, eyes: eyeParts, appendages: [...legs, ...feelers, tail], core, coreGlow};
}

function makeBot(root, pet, tone) {
  const body = new THREE.Group();
  root.add(body);
  const grown = pet.stage === "adult" ? 1.13 : pet.stage === "juvenile" ? 1.03 : .88;
  body.scale.setScalar(grown);
  ball(body, tone.dark, [0, -.15, -.04], [.78, .78, .51], {metalness: .72, roughness: .34});
  texturedBall(body, tone, "tech", [0, -.1, .12], [.7, .72, .52], {metalness: .64, roughness: .26, clearcoat: .95});
  // A service chassis, with fitted armour and recessed vents. The face and
  // expression remain visible in front of the panels.
  panel(body, [[-.3, .5], [-.22, .66], [0, .72], [.22, .66], [.3, .5], [.22, .43], [-.22, .43]], tone.dark,
    {position: [0, 0, .44], metalness: .83, roughness: .3});
  panel(body, [[-.18, .52], [-.12, .6], [.12, .6], [.18, .52], [.12, .49], [-.12, .49]], tone.line,
    {position: [0, 0, .49], metalness: .76, roughness: .38});
  for (const side of [-1, 1]) {
    panel(body, [[0, .26], [side * .13, .2], [side * .16, -.18], [side * .07, -.3], [0, -.25]], tone.dark,
      {position: [side * .47, -.13, .43], rotation: [0, side * .18, 0], metalness: .84});
    fastener(body, side * .48, -.35, .53, tone.line, .023);
    fastener(body, side * .46, .32, .48, tone.line, .019);
    for (let i = 0; i < 4; i += 1) {
      rod(body, [side * (.21 + i * .055), -.68, .34], [side * (.21 + i * .055), -.59, .43], "#17262c", .012,
        {metalness: .55, roughness: .5});
    }
  }
  ball(body, tone.line, [0, -.49, .39], [.28, .2, .16], {metalness: .76, roughness: .24, emissive: tone.dark, emissiveIntensity: .3});
  const badge = new THREE.Mesh(new THREE.TorusGeometry(.115, .025, 8, 28), material(tone.line, {
    emissive: tone.glow, emissiveIntensity: .72, metalness: .68, roughness: .2,
  }));
  badge.position.set(0, -.48, .545);
  body.add(badge);
  ball(body, tone.glow, [0, -.48, .55], [.05, .05, .035], {emissive: tone.glow, emissiveIntensity: 1.7});
  // Little panel seams and fasteners make the chassis read as a field robot.
  for (const side of [-1, 1]) {
    tube(body, [[side * .44, -.28, .52], [side * .51, -.12, .51], [side * .52, .12, .47]], tone.dark, .018,
      {metalness: .72, roughness: .32});
    ball(body, tone.line, [side * .55, -.3, .47], [.027, .027, .027], {emissive: tone.glow, emissiveIntensity: .7});
  }
  const arms = [];
  for (const side of [-1, 1]) {
    ball(body, tone.dark, [side * .66, .02, .08], [.2, .32, .38], {metalness: .76, roughness: .3});
    ball(body, tone.line, [side * .71, .02, .4], [.055, .12, .035], {emissive: tone.line, emissiveIntensity: .65, metalness: .35});
    if (pet.stage !== "hatchling") {
      const arm = new THREE.Group();
      arm.position.set(side * .61, -.08, .22);
      body.add(arm);
      rod(arm, [0, 0, 0], [side * .2, -.15, .04], tone.light, .045, {metalness: .82, roughness: .24});
      ball(arm, tone.dark, [side * .21, -.17, .06], [.095, .085, .09], {metalness: .8, roughness: .26});
      fastener(arm, side * .21, -.17, .15, tone.line, .023);
      tube(arm, [[side * .22, -.17, .07], [side * .3, -.24, .1], [side * .33, -.31, .11]], tone.line, .018,
        {emissive: tone.glow, emissiveIntensity: .65, metalness: .6});
      arms.push(arm);
    }
    for (let i = 0; i < 3; i += 1) {
      rod(body, [side * (.4 + i * .1), -.55, .35], [side * (.42 + i * .1), -.67, .37], tone.dark, .018,
        {metalness: .8, roughness: .3});
    }
  }
  // A tiny beacon and crown fins give the bot a pilot's helmet silhouette.
  rod(body, [0, .58, .12], [0, .86, .12], tone.line, .024, {emissive: tone.line, emissiveIntensity: .45, metalness: .7});
  ball(body, tone.glow, [0, .88, .12], [.075, .075, .075], {emissive: tone.glow, emissiveIntensity: 1.5});
  for (const side of [-1, 1]) {
    tube(body, [[side * .25, .48, .08], [side * .43, .72, -.01], [side * .58, .59, -.05]], tone.line, .035,
      {metalness: .78, emissive: tone.line, emissiveIntensity: .3});
  }
  const thruster = new THREE.Mesh(new THREE.ConeGeometry(.14, .42, 12), new THREE.MeshBasicMaterial({
    color: "#ffae58", transparent: true, opacity: .72, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false,
  }));
  thruster.position.set(0, -.83, .14);
  thruster.rotation.x = Math.PI;
  body.add(thruster);
  const thrusterGlow = glowSprite(body, [0, -.9, .17], [.52, .68, 1], "#ff9b42", .54);
  const thrusting = pet.stage !== "adult" && !pet.asleep && !pet.dormant;
  thruster.visible = thrusterGlow.visible = thrusting;
  const eyeParts = face(body, pet, tone, {bot: true});
  return {body, eyes: eyeParts, appendages: arms, thruster, thrusterGlow};
}

function makeSample(root, pet, tone) {
  const body = new THREE.Group();
  root.add(body);
  const kind = pet.kind || pet.sample_kind || "bacterium";
  const grown = pet.stage === "adult" ? 1.12 : pet.stage === "juvenile" ? 1.02 : .86;
  body.scale.setScalar(grown);
  const fronds = [];
  if (kind === "tubus") {
    // The familiar tubus fan, now with translucent, living fronds.
    ball(body, tone.dark, [0, -.61, -.02], [.29, .43, .28], {roughness: .5});
    for (let i = -2; i <= 2; i += 1) {
      const x = i * .22;
      const height = .86 - Math.abs(i) * .12;
      const frond = new THREE.Group();
      frond.position.set(x * .5, -.4, .03);
      body.add(frond);
      tube(frond, [[-x * .5, -.22, .02], [0, .12, .04], [x * .35, .48, .01], [x * .5, height * .65 + .4, -.03]], tone.light, .075,
        {emissive: tone.dark, emissiveIntensity: .28, roughness: .28, transparent: true, opacity: .92});
      const cup = new THREE.Mesh(new THREE.LatheGeometry([
        new THREE.Vector2(.07, -.2), new THREE.Vector2(.11, -.08), new THREE.Vector2(.16, .08),
        new THREE.Vector2(.24, .22), new THREE.Vector2(.2, .22), new THREE.Vector2(.13, .08),
        new THREE.Vector2(.07, -.08), new THREE.Vector2(.05, -.2),
      ], 24), material("#ffffff", {map: skinTexture(tone, "cell"), side: THREE.DoubleSide,
        emissive: tone.dark, emissiveIntensity: .22, roughness: .35, clearcoat: .7}));
      cup.position.set(x * .5, height * .65 + .4, -.03);
      cup.rotation.z = -i * .08;
      frond.add(cup);
      ball(frond, tone.glow, [x * .5, height * .65 + .51, .025], [.038, .045, .035],
        {emissive: tone.glow, emissiveIntensity: .9});
      for (let line = -1; line <= 1; line += 1) {
        tube(frond, [[line * .035, -.1, .09], [x * .25 + line * .025, .2, .12], [x * .45 + line * .02, height * .55 + .35, .08]],
          tone.vein, .008, {emissive: tone.glow, emissiveIntensity: .32});
      }
      fronds.push(frond);
    }
  } else if (kind === "fungoida") {
    const cap = new THREE.Mesh(new THREE.SphereGeometry(.82, 32, 20, 0, Math.PI * 2, 0, Math.PI / 2),
      material("#ffffff", {map: skinTexture(tone, "cell"), roughness: .26, clearcoat: .9, bumpScale: .035}));
    cap.position.set(0, .02, -.02);
    cap.scale.set(1, .9, .64);
    body.add(cap);
    texturedBall(body, {...tone, light: "#e5dfc1", dark: "#77765a", line: tone.line}, "cell",
      [0, -.47, .05], [.25, .47, .3], {roughness: .32, clearcoat: .5});
    const gills = new THREE.Mesh(new THREE.TorusGeometry(.49, .012, 6, 48), material(tone.vein, {
      emissive: tone.glow, emissiveIntensity: .25, transparent: true, opacity: .55,
    }));
    gills.position.set(0, .005, .04);
    gills.rotation.x = Math.PI / 2;
    body.add(gills);
    // Radial gills under the cap are visible when the little specimen leans.
    for (let i = 0; i < 12; i += 1) {
      const angle = Math.PI * 2 * i / 12;
      rod(body, [Math.cos(angle) * .16, -.015, Math.sin(angle) * .1],
        [Math.cos(angle) * .61, -.025, Math.sin(angle) * .37], tone.vein, .009,
        {roughness: .52, emissive: tone.glow, emissiveIntensity: .2});
    }
    for (let i = 0; i < 5; i += 1) {
      const angle = i * Math.PI * 2 / 5;
      const x = Math.cos(angle) * .63, y = -.13 + Math.sin(angle) * .34;
      ball(body, i % 2 ? tone.line : tone.light, [x, y, .15], [.19, .2, .17],
        {emissive: tone.glow, emissiveIntensity: .45, roughness: .25});
      ball(body, tone.glow, [x * 1.12, y + .02, .3], [.035, .035, .03], {emissive: tone.glow, emissiveIntensity: 1.35});
      if (i % 2 === 0) {
        const stem = new THREE.Group();
        stem.position.set(x * .72, y + .12, .12);
        body.add(stem);
        tube(stem, [[0, 0, 0], [x * .1, .16, .02], [x * .14, .29, .02]], tone.line, .014,
          {emissive: tone.glow, emissiveIntensity: .45});
        ball(stem, tone.glow, [x * .14, .3, .02], [.045, .045, .045], {emissive: tone.glow, emissiveIntensity: 1.5});
        fronds.push(stem);
      }
    }
  } else {
    ball(body, tone.dark, [0, -.26, -.02], [.87, .51, .44], {roughness: .38});
    texturedBall(body, tone, "cell", [0, -.19, .16], [.83, .46, .42], {emissive: tone.dark, emissiveIntensity: .18, roughness: .25});
    const membrane = new THREE.Mesh(new THREE.TorusGeometry(.64, .018, 8, 48), material(tone.line, {
      emissive: tone.glow, emissiveIntensity: .58, transparent: true, opacity: .72, roughness: .2,
    }));
    membrane.position.set(0, -.18, .38);
    membrane.scale.set(1.2, .72, 1);
    body.add(membrane);
    ball(body, tone.vein, [0, -.2, .57], [.19, .19, .075], {emissive: tone.glow, emissiveIntensity: 1.05,
      transparent: true, opacity: .8, roughness: .18});
    glowSprite(body, [0, -.2, .67], [.8, .65, 1], tone.glow, .42);
    for (let i = 0; i < 10; i += 1) {
      const angle = i * Math.PI * 2 / 10;
      const x = Math.cos(angle) * .68, y = -.2 + Math.sin(angle) * .4;
      const tip = [x * 1.34, y + Math.sin(angle) * .12, .04];
      tube(body, [[x, y, .2], [x * 1.14, y + Math.sin(angle) * .08, .16], tip], tone.line, .014,
        {emissive: tone.glow, emissiveIntensity: .55});
      ball(body, tone.glow, tip, [.035, .035, .035], {emissive: tone.glow, emissiveIntensity: 1.1});
    }
    for (let i = 0; i < 8; i += 1) {
      const angle = i * Math.PI / 4, x = Math.cos(angle) * .48, y = -.2 + Math.sin(angle) * .24;
      ball(body, tone.vein, [x, y, .48], [.07, .05, .025],
        {roughness: .32, emissive: tone.glow, emissiveIntensity: .28});
    }
  }
  const eyeParts = face(body, pet, tone, {small: kind !== "tubus"});
  return {body, eyes: eyeParts, appendages: fronds};
}

// A shipboard foundling inspired by the Scout, Thargon and Orthrus forms.
// Each blade is a real, jointed 3D part rather than a rotating sprite; the
// life simulation can pose it along with the pet and its activity props.
function makeThargoid(root, pet, tone) {
  const body = new THREE.Group();
  root.add(body);
  const adult = pet.stage === "adult", juvenile = pet.stage === "juvenile";
  // The Orthrus's hanging claws need room to flex inside the shared camera.
  const grown = adult ? .94 : juvenile ? 1.0 : .92;
  body.scale.setScalar(grown);
  body.userData.restY = adult ? .16 : 0;

  const chitin = material(tone.dark, {metalness: .54, roughness: .37, clearcoat: .68,
    emissive: tone.dark, emissiveIntensity: .1, side: THREE.DoubleSide});
  const shellTone = {...tone, light: colour(tone.dark).lerp(colour(tone.vein), .24).getStyle()};
  const carapaceTexture = skinTexture(shellTone, "chitin");
  const edge = material("#ffffff", {map: carapaceTexture, bumpMap: carapaceTexture, bumpScale: .055,
    metalness: .62, roughness: .35, clearcoat: .84,
    emissive: tone.dark, emissiveIntensity: .16, side: THREE.DoubleSide});
  const vein = material(tone.line, {metalness: .36, roughness: .25, emissive: tone.glow, emissiveIntensity: .62});
  const count = adult ? 8 : juvenile ? 10 : 8;
  const width = adult ? .18 : juvenile ? .18 : .23;
  const length = adult ? 1.61 : juvenile ? 1.28 : 1.2;
  const tip = adult ? .49 : juvenile ? .08 : .13;

  // Curved, bevelled carapace with a thinner inset ridge. The adult's tip
  // sweeps round into a claw, while the middle form grows sharper spines.
  const shape = new THREE.Shape();
  shape.moveTo(-.11, .18);
  shape.bezierCurveTo(-width * 1.24, .41, -width * 1.1, .72, -width * .72, length * .78);
  shape.bezierCurveTo(-width * .24, length * .96, tip - .07, length * 1.03, tip, length);
  shape.bezierCurveTo(tip + .035, length * .88, width * 1.22, .78, width * 1.12, .55);
  shape.bezierCurveTo(width * .83, .37, .13, .25, .11, .18);
  shape.closePath();
  const bladeGeometry = new THREE.ExtrudeGeometry(shape, {depth: .065, bevelEnabled: true,
    bevelThickness: .018, bevelSize: .018, bevelSegments: 3, curveSegments: 10});
  const vertices = bladeGeometry.attributes.position;
  for (let i=0;i<vertices.count;i++) {
    const x=vertices.getX(i), y=vertices.getY(i);
    vertices.setZ(i,vertices.getZ(i)+Math.sin(Math.PI*y/length)*(.1*Math.cos(x/width)+.012*Math.sin(y*29)));
  }
  bladeGeometry.computeVertexNormals();
  const ridgeGeometry = bladeGeometry.clone();
  ridgeGeometry.scale(.63,.81,.7); ridgeGeometry.translate(0,.12,.075);
  const insetGeometry = new THREE.SphereGeometry(1, 12, 8);
  const appendages = [];
  for (let i = 0; i < count; i += 1) {
    // The mature form hangs its long claws beneath the central body; its
    // short upper fins give it a distinctly different silhouette.
    const adultAngles = [-1.9, -2.35, -2.85, 2.85, 2.35, 1.9, -.52, .52];
    const angle = adult ? adultAngles[i] : i * Math.PI * 2 / count;
    const anchor = new THREE.Group();
    anchor.rotation.z = angle;
    anchor.rotation.y = (i % 2 ? -.10 : .10);
    if (adult && i >= 6) anchor.scale.set(.78, .68, .85);
    body.add(anchor);
    const joint = new THREE.Group();
    joint.position.set(0, .05, -.05 - (i % 2) * .035);
    joint.userData.thargoidPetal = i;
    anchor.add(joint);
    appendages.push(joint);
    const plate = new THREE.Mesh(bladeGeometry, chitin);
    joint.add(plate);
    const spine = new THREE.Mesh(ridgeGeometry, edge);
    joint.add(spine);
    tube(joint, [[0, .23, .14], [.035, .46, .16], [-.015, .74, .13],
      [tip * .48, length * .85, .08], [tip, length * .97, .03]], tone.line, .012,
      {metalness: .45, roughness: .32, emissive: tone.glow, emissiveIntensity: .7});
    for (const side of [-1, 1]) {
      // Irregular branching ridges catch the light across the armour.
      tube(joint, [[side * .035, .32, .14], [side * width * .68, .44, .13],
        [side * width * .56, .61, .13], [side * width * .3, .74, .12]],
      i % 2 ? tone.vein : tone.line, .008,
      {metalness: .36, roughness: .42, emissive: tone.glow, emissiveIntensity: .34});
    }
    // Raised ribs and luminous pores give depth without tiny unreadable text.
    for (let rib = 0; rib < 3; rib += 1) {
      const y = .4 + rib * .19;
      const strip = new THREE.Mesh(new THREE.BoxGeometry(width * 1.25, .018, .022), edge);
      strip.position.set(.005 + rib * .012, y, .15 - rib * .005);
      strip.rotation.z = -.13 - rib * .04;
      joint.add(strip);
      const pore = new THREE.Mesh(insetGeometry, vein);
      pore.position.set(.055, y + .07, .162 - rib * .01);
      pore.scale.set(.025, .04, .013);
      joint.add(pore);
    }
    if (juvenile) {
      for (const [y, scale] of [[.59, .8], [.8, 1], [1.0, .65]]) {
        const thorn = new THREE.Mesh(new THREE.ConeGeometry(.055 * scale, .25 * scale, 5), edge);
        thorn.position.set(-width * .74, y, .02);
        thorn.rotation.z = .68;
        joint.add(thorn);
      }
    }
    if (adult) {
      // Recurved hanging feelers make the Orthrus stage more than a recolour.
      tube(joint, [[-.08, .35, -.03], [-.22, .58, -.02], [-.31, .86, -.06],
        [-.26, 1.08, -.08], [-.14, 1.18, -.1]], tone.light, .027,
      {metalness: .45, roughness: .35, emissive: tone.dark, emissiveIntensity: .18});
      tube(joint, [[-.10, .44, .01], [-.22, .65, .01], [-.28, .87, -.03], [-.25, 1.04, -.05]], tone.glow, .009,
        {emissive: tone.glow, emissiveIntensity: .85});
    }
  }

  // Overlapping central plates and a single illuminated sensor suggest a
  // living alien eye without imposing a human cartoon face on the design.
  ball(body, tone.dark, [0, 0, .16], [.43, .43, .32], {metalness: .4, roughness: .38});
  for (let i = 0; i < 8; i += 1) {
    const angle = i * Math.PI * 2 / 8;
    const plate = new THREE.Mesh(insetGeometry, i % 2 ? chitin : edge);
    plate.position.set(Math.sin(angle) * .32, Math.cos(angle) * .32, .38);
    plate.scale.set(.105, .22, .07);
    plate.rotation.z = -angle;
    body.add(plate);
    const marker = new THREE.Mesh(insetGeometry, vein);
    marker.position.set(Math.sin(angle) * .29, Math.cos(angle) * .29, .46);
    marker.scale.set(.025, .04, .018);
    body.add(marker);
  }
  const eye = new THREE.Group();
  eye.position.set(0, 0, .43);
  body.add(eye);
  ball(eye, tone.dark, [0, 0, 0], [.22, .22, .09], {metalness: .55, roughness: .25});
  const iris = ball(eye, tone.glow, [0, 0, .08], [.16, .16, .065],
    {emissive: tone.glow, emissiveIntensity: 1.25, roughness: .2});
  const pupil = ball(eye, tone.dark, [0, 0, .145], [.09, .09, .025],
    {emissive: tone.dark, emissiveIntensity: .2, roughness: .12});
  for(let i=0;i<12;i++){const a=i*Math.PI/6;rod(eye,[Math.sin(a)*.1,Math.cos(a)*.1,.146],[Math.sin(a)*.153,Math.cos(a)*.153,.13],tone.dark,.006,{roughness:.4,metalness:.45});}
  ball(eye, "#ffffff", [-.045, .052, .17], [.026, .026, .014],
    {emissive: tone.glow, emissiveIntensity: .5, roughness: .2});
  const coreGlow = glowSprite(eye, [0, 0, .15], [.62, .62, 1], tone.glow, .45);
  return {body, eyes: [{eye, iris, pupil}], appendages, core: iris, coreGlow};
}

// Fitted surface detail shares the creature's articulated body.
function refineModel(model, pet, tone) {
  const body=model.body, organic=pet.species!=='bot';
  if(pet.stage==='egg') {
    for(let side of [-1,1])for(let i=0;i<3;i++) {
      const y=-.4+i*.32;
      panel(body,[[0,0],[side*.16,.12],[side*.18,.3],[side*.05,.27]],organic?tone.dark:'#85929a',
        {position:[side*.37,y,.37],rotation:[0,side*.3,0],metalness:organic?.22:.8,roughness:.5,depth:.025});
    }
  } else if(pet.species==='larva') {
    for(const side of [-1,1])for(let i=0;i<4;i++) {
      const y=.32-i*.25;
      const plate=panel(body,[[0,0],[side*.17,.06],[side*.29,-.07],[side*.19,-.23],[side*.025,-.16]],i%2?tone.dark:'#234738',
        {position:[side*.54,y,.59],rotation:[0,side*.25,side*.08],metalness:.28,roughness:.44,depth:.055});
      tube(plate,[[side*.05,-.05,.075],[side*.14,-.07,.09],[side*.22,-.1,.07]],tone.glow,.008,{emissive:tone.glow,emissiveIntensity:.5});
    }
    for(const side of [-1,1])for(let i=0;i<3;i++) {
      const y=-.24-i*.14;
      panel(body,[[side*.08,y],[side*.33,y+.05],[side*.4,y-.025],[side*.29,y-.11],[side*.06,y-.09]],'#24483b',{position:[0,0,.62-i*.015],metalness:.22,roughness:.5,depth:.04});
    }
    for(let i=0;i<5;i++) {
      const thorn=new THREE.Mesh(new THREE.ConeGeometry(.046,.18-i*.015,5),material(tone.dark,{roughness:.46,metalness:.25}));
      thorn.position.set((i-2)*.13,.69+(.1-Math.abs(i-2)*.03),.22);thorn.rotation.z=(i-2)*-.18;body.add(thorn);
    }
  } else if(pet.species==='bot') {
    for(const side of [-1,1]) {
      panel(body,[[0,.24],[side*.18,.19],[side*.28,-.08],[side*.18,-.32],[0,-.3]],'#9ba6ab',
        {position:[side*.62,.03,.17],rotation:[0,side*.4,0],roughness:.5,metalness:.8,depth:.09});
      for(let i=0;i<4;i++) {
        panel(body,[[0,0],[side*.12,.025],[side*.13,-.04],[0,-.055]],'#15232c',
          {position:[side*.72,.18-i*.09,.38],metalness:.65,depth:.012});
      }
      tube(body,[[side*.61,-.32,.3],[side*.8,-.41,.27],[side*.7,-.59,.22]],'#e4ac51',.019,{metalness:.8,roughness:.45});
      fastener(body,side*.74,.3,.28,'#d4dedf',.028);
    }
    for(const side of [-1,1]) {
      panel(body,[[side*.14,-.21],[side*.38,-.17],[side*.43,-.35],[side*.3,-.53],[side*.16,-.48]],'#536570',{position:[0,0,.61],metalness:.8,roughness:.5,depth:.05});
      for(let i=0;i<3;i++)rod(body,[side*(.21+i*.055),-.28,.69],[side*(.22+i*.055),-.39,.69],'#1d2e36',.009,{metalness:.8,roughness:.4});
      fastener(body,side*.32,-.43,.69,'#aabcc4',.018);
    }
    panel(body,[[-.28,0],[-.2,-.12],[.2,-.12],[.28,0]],'#1c2931',{position:[0,-.59,.42],depth:.03});
    for(let i=-2;i<=2;i++)rod(body,[i*.07,-.63,.47],[i*.07,-.68,.47],'#d6a95a',.009,{metalness:.8,roughness:.5});
  } else if(pet.species==='sample') {
    const kind=pet.kind||pet.sample_kind||'bacterium';
    if(kind==='fungoida') {
      for(let i=0;i<16;i++) {
        const a=i*Math.PI/8;
        tube(body,[[Math.cos(a)*.18,.7,Math.sin(a)*.11],[Math.cos(a)*.49,.59,Math.sin(a)*.31],
          [Math.cos(a)*.77,.24,Math.sin(a)*.49],[Math.cos(a)*.83,.015,Math.sin(a)*.54]],
          i%2?tone.vein:tone.dark,.012,{emissive:tone.glow,emissiveIntensity:i%2?.18:0,roughness:.6});
      }
      for(let i=0;i<12;i++) {const a=i*Math.PI/6;ball(body,tone.glow,[Math.cos(a)*.7,.09+Math.sin(a)*.04,Math.sin(a)*.45],[.022,.025,.02],{emissive:tone.glow,emissiveIntensity:.7});}
    } else if(kind==='tubus') {
      for(const [i,frond] of model.appendages.entries()) {
        const x=(i-2)*.22, h=.86-Math.abs(i-2)*.12, top=h*.65+.4;
        const rim=new THREE.Mesh(new THREE.TorusGeometry(.226,.012,6,36),material(tone.vein,{roughness:.48,emissive:tone.glow,emissiveIntensity:.22}));
        rim.rotation.x=Math.PI/2;rim.position.set(x*.5,top+.22,-.03);frond.add(rim);
        for(let j=0;j<6;j++){const a=j*Math.PI/3;tube(frond,[[x*.5+Math.cos(a)*.08,top-.15,-.03+Math.sin(a)*.08],[x*.5+Math.cos(a)*.14,top+.07,-.03+Math.sin(a)*.14],[x*.5+Math.cos(a)*.23,top+.2,-.03+Math.sin(a)*.23]],tone.dark,.009,{roughness:.5});}
      }
    } else {
      for(let i=0;i<14;i++) {
        const a=i*Math.PI*2/14, x=Math.cos(a)*.67,y=-.2+Math.sin(a)*.32;
        const organelle=ball(body,i%3?tone.dark:tone.vein,[x,y,.43],[.056,.09,.05],{emissive:tone.glow,emissiveIntensity:.18,roughness:.44});organelle.rotation.z=-a;
        tube(body,[[x*.8,y,.46],[x*1.1,y+.03,.49],[x*1.22,y-.05,.38]],tone.vein,.006,{roughness:.5,emissive:tone.glow,emissiveIntensity:.22});
      }
    }
  }
}

function makeOutfit(parent, pet, tone) {
  const root=new THREE.Group();parent.add(root);
  const radial=pet.species==='thargoid', tubus=pet.species==='sample'&&(pet.kind||pet.sample_kind)==='tubus';
  const fungus=pet.species==='sample'&&(pet.kind||pet.sample_kind)==='fungoida';
  const bacterium=pet.species==='sample'&&!tubus&&!fungus;
  const neck=radial?-.31:-.35, width=radial?.38:tubus||fungus?.25:.49;
  const top=tubus?1.30:fungus?.89:bacterium?.44:radial?.52:.74;
  if((tubus||fungus)&&['scarf','bowtie','charm'].includes(pet.outfit))root.position.z=-.3;
  const cloth=(mesh)=>{mesh.material.metalness=0;mesh.material.roughness=.88;mesh.material.clearcoat=0;mesh.material.sheen=.7;return mesh;};
  let tail=null, pendant=null;
  if(pet.outfit==='visor') {
    const y=radial?0:.15, radius=radial?.35:.64, centreZ=radial?.27:.16;
    const pane=new THREE.Mesh(new THREE.CylinderGeometry(radius,radius,.24,32,1,true,-.82,1.64),material('#6cd8e7',{transparent:true,opacity:.22,roughness:.12,metalness:.25,clearcoat:1,side:THREE.DoubleSide,depthWrite:false}));
    pane.position.set(0,y,centreZ);root.add(pane);
    for(const dy of [-.13,.13])tube(root,Array.from({length:9},(_,i)=>{const a=-.82+i*.205;return[Math.sin(a)*radius,y+dy,centreZ+Math.cos(a)*radius];}),'#a4b6be',.014,{metalness:.85,roughness:.3});
    for(const side of [-1,1]){ball(root,'#1c2c34',[side*radius*.75,y,centreZ+radius*.68],[.055,.14,.055],{metalness:.8,roughness:.35});ball(root,tone.glow,[side*radius*.75,y+.025,centreZ+radius*.73],[.014,.025,.009],{emissive:tone.glow,emissiveIntensity:.9});}
  } else if(pet.outfit==='helmet') {
    const shell=new THREE.Mesh(new THREE.SphereGeometry(.56,32,16,0,Math.PI*2,0,Math.PI/2),material('#c58e35',{metalness:.6,roughness:.46,clearcoat:.25}));
    shell.position.set(0,top-.12,.08);shell.scale.z=.8;root.add(shell);
    const brim=new THREE.Mesh(new THREE.TorusGeometry(.57,.035,8,40),material('#4c4130',{metalness:.6,roughness:.55}));brim.rotation.x=Math.PI/2;brim.scale.y=.8;brim.position.set(0,top-.12,.08);root.add(brim);
    ball(root,'#202b32',[0,top+.06,.51],[.14,.14,.08],{metalness:.8,roughness:.4});
    ball(root,'#fff4d1',[0,top+.06,.58],[.1,.1,.035],{emissive:'#fff0bf',emissiveIntensity:pet.asleep?.2:1.1,roughness:.18});
    for(const side of [-1,1]){tube(root,[[side*.43,top-.11,.39],[side*.49,top+.08,.3],[side*.3,top+.3,.27]],'#e6c67d',.022,{roughness:.55,metalness:.3});fastener(root,side*.42,top-.07,.42,'#a7afb2',.019);}
  } else if(pet.outfit==='scarf'||pet.outfit==='bowtie') {
    tube(root,[[-width,neck,.45],[-width*.5,neck-.025,.65],[0,neck-.04,.73],[width*.5,neck-.025,.65],[width,neck,.45]],'#7c2830',.045,{roughness:.93,clearcoat:0,metalness:0});
    if(pet.outfit==='scarf') {
      tail=new THREE.Group();tail.position.set(width*.65,neck-.01,.64);root.add(tail);
      cloth(panel(tail,[[0,0],[.16,-.025],[.22,-.42],[.1,-.47],[.035,-.39]],'#ba4b40',{depth:.02,metalness:0,roughness:.9}));
      for(let i=0;i<4;i++)rod(tail,[.07+i*.035,-.41,.045],[.065+i*.035,-.49,.04],'#d9ab72',.006,{roughness:1,metalness:0});
      tube(tail,[[.05,-.03,.045],[.1,-.17,.055],[.12,-.36,.046]],'#7b3033',.008,{roughness:1,metalness:0});
    } else {
      for(const side of [-1,1])cloth(panel(root,[[side*.035,neck],[side*.26,neck+.11],[side*.28,neck-.12]],'#b94b40',{position:[0,0,.74],rotation:[0,side*.18,0],depth:.035,metalness:0,roughness:.8}));
      ball(root,'#77303a',[0,neck,.8],[.07,.08,.055],{roughness:.88,metalness:0,clearcoat:0});
    }
  } else if(pet.outfit==='charm') {
    tube(root,[[-width*.6,neck+.07,.48],[0,neck-.07,.74],[width*.6,neck+.07,.48]],'#b9a77a',.012,{metalness:.8,roughness:.45});
    pendant=new THREE.Group();pendant.position.set(0,neck-.07,.76);root.add(pendant);
    const stone=panel(pendant,[[0,-.04],[.12,-.17],[0,-.33],[-.12,-.17]],'#354e5f',{depth:.05,metalness:.55,roughness:.55});
    tube(stone,[[0,-.08,.09],[.065,-.17,.09],[0,-.27,.09],[-.065,-.17,.09],[0,-.08,.09]],'#66e7fb',.007,{emissive:'#4bc8fa',emissiveIntensity:1.2,roughness:.3});
    rod(stone,[0,-.11,.095],[0,-.23,.095],'#b9f7ff',.009,{emissive:'#67dfff',emissiveIntensity:.9});
  }
  root.name=`outfit:${pet.outfit||'none'}`;
  return {root,tail,pendant};
}

function stationHull() {
  // A cuboctahedron: eight triangular and six square faces, like the
  // familiar rotating station silhouette, rather than a featureless cube.
  const v = [0,1,1, 0,1,-1, 0,-1,1, 0,-1,-1, 1,0,1, 1,0,-1,
    -1,0,1, -1,0,-1, 1,1,0, 1,-1,0, -1,1,0, -1,-1,0];
  const faces = [0,4,8, 0,10,6, 1,8,5, 1,7,10, 2,9,4, 2,6,11, 3,5,9, 3,11,7,
    0,8,1, 0,1,10, 2,3,9, 2,11,3, 4,9,5, 4,5,8,
    6,10,7, 6,7,11, 0,6,2, 0,2,4, 1,5,3, 1,3,7];
  return new THREE.PolyhedronGeometry(v, faces, .78, 0);
}

function toyModel(parent, kind, tone) {
  const group = new THREE.Group();
  parent.add(group);
  if (kind === "relic") {
    const crystal = new THREE.Mesh(new THREE.OctahedronGeometry(.72, 1), material("#4a9bc4", {
      emissive: "#348fff", emissiveIntensity: .8, metalness: .4, roughness: .18, clearcoat: 1,
    }));
    crystal.scale.set(.62, 1.2, .65);
    crystal.rotation.z = .18;
    group.add(crystal);
    for (let i = 0; i < 3; i += 1) {
      const collar = new THREE.Mesh(new THREE.TorusGeometry(.31 + i * .045, .023, 6, 6), material("#5b797f", {
        metalness: .75, roughness: .36, emissive: "#51d5e0", emissiveIntensity: .28,
      }));
      collar.position.y = -.3 + i * .25;
      collar.rotation.set(Math.PI / 2, i * .32, .18);
      group.add(collar);
    }
    tube(group, [[-.23, -.45, .3], [-.15, -.2, .4], [0, .06, .47], [.09, .37, .3]], "#b4edff", .012,
      {emissive: "#73e7ff", emissiveIntensity: 1.1});
    ball(group, "#bdedff", [0, 0, .49], [.16, .16, .12], {emissive: "#6bd7ff", emissiveIntensity: 1.5});
  } else if (kind === "sensor") {
    const petals = [];
    for (let i = 0; i < 5; i += 1) {
      const petal = new THREE.Group();
      petal.rotation.z = i * Math.PI * 2 / 5;
      group.add(petal);
      ball(petal, "#182622", [0, .43, 0], [.18, .39, .12], {metalness: .54, roughness: .28});
      ball(petal, "#416746", [0, .55, .08], [.08, .21, .08], {emissive: tone.glow, emissiveIntensity: .2});
      panel(petal, [[-.1,.29], [-.16,.58], [0,.86], [.16,.58], [.1,.29]], "#314b39",
        {position: [0, 0, .11], metalness: .46, roughness: .55});
      tube(petal, [[0, .3, .17], [0, .52, .2], [0, .74, .16]], "#8dd286", .012,
        {emissive: "#5ec674", emissiveIntensity: .5});
      petals.push(petal);
    }
    const core = ball(group, "#54e39a", [0, 0, .19], [.2, .2, .16], {emissive: "#54e39a", emissiveIntensity: 1.7});
    glowSprite(group, [0, 0, .25], [.8, .8, 1], "#54e39a", .65);
    group.userData.petals = petals;
    group.userData.core = core;
  } else if (kind === "fragment") {
    const amber = material("#e6a73d", {emissive: "#ff9c35", emissiveIntensity: .45, metalness: .3, roughness: .23, clearcoat: 1});
    for (const [position, scale, rotation] of [
      [[0, 0, 0], [.42, .78, .38], .18], [[-.31, -.1, -.05], [.25, .48, .27], -.42], [[.27, -.12, .03], [.23, .39, .25], .34],
    ]) {
      const shard = new THREE.Mesh(new THREE.ConeGeometry(.52, 1.2, 5), amber);
      shard.position.set(...position); shard.scale.set(...scale); shard.rotation.z = rotation; group.add(shard);
    }
    const matrix = new THREE.Mesh(new THREE.DodecahedronGeometry(.45, 1), material("#575247", {roughness: .92, metalness: .12}));
    matrix.scale.set(1.2, .42, .8); matrix.position.y = -.27; group.add(matrix);
  } else if (kind === "beacon") {
    const base = new THREE.Mesh(new THREE.CylinderGeometry(.52, .65, .3, 8), material("#394855", {metalness: .75, roughness: .29}));
    base.position.y = -.39; group.add(base);
    const foot = new THREE.Mesh(new THREE.CylinderGeometry(.62, .67, .08, 8), material("#172631", {metalness: .8, roughness: .4}));
    foot.position.y = -.57; group.add(foot);
    for (const side of [-1, 1]) {
      rod(group, [side * .42, -.34, .02], [side * .12, .35, .02], "#667985", .035, {metalness: .8});
      fastener(group, side * .38, -.38, .4, "#c8d2d2", .028);
    }
    rod(group, [0, -.3, 0], [0, .48, 0], "#a7b5c1", .07, {metalness: .82, roughness: .22});
    const lamp = ball(group, "#ffd166", [0, .57, .02], [.2, .2, .2], {emissive: "#ffb52e", emissiveIntensity: 1.8});
    glowSprite(group, [0, .61, .02], [.9, .9, 1], "#ffd166", .64);
    group.userData.lamp = lamp;
  } else if (kind === "station" || kind === "model") {
    const body = new THREE.Mesh(stationHull(), material("#80909a", {metalness: .72, roughness: .43}));
    group.add(body);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(body.geometry, 25), new THREE.LineBasicMaterial({color: "#d2dde0", transparent: true, opacity: .42}));
    group.add(edges);
    panel(group, [[-.3,-.2],[.3,-.2],[.3,.2],[-.3,.2]], "#24343e", {position: [0, 0, .56], depth: .025});
    panel(group, [[-.22,-.09],[.22,-.09],[.22,.09],[-.22,.09]], "#070e12", {position: [0, 0, .61], depth: .015});
    for (const side of [-1, 1]) {
      for (let i = 0; i < 3; i += 1) {
        ball(group, i % 2 ? "#d6e7ef" : "#ffab50", [side * .27, -.12 + i * .12, .635], [.014, .014, .01],
          {emissive: i % 2 ? "#a6deff" : "#ff994b", emissiveIntensity: 1.2});
      }
    }
  } else {
    const stone = new THREE.Mesh(new THREE.DodecahedronGeometry(.72, 0), material(kind === "pebble" ? "#77848d" : "#596b6d", {
      roughness: .82, metalness: .08,
    }));
    stone.scale.set(1.15, .72, .9); group.add(stone);
    for (let i = 0; i < 3; i += 1) ball(group, tone.glow, [(-.28 + i * .28), .18 + (i % 2) * .08, .43], [.07, .055, .035], {emissive: tone.glow, emissiveIntensity: .3});
  }
  return group;
}

function limpetModel(parent, tone) {
  const group = new THREE.Group();
  parent.add(group);
  const shell = new THREE.Mesh(new THREE.CylinderGeometry(.42, .55, .3, 8), material("#b8c6d3", {metalness: .78, roughness: .22, clearcoat: 1}));
  group.add(shell);
  ball(group, "#283942", [0, 0, .13], [.48, .39, .3], {metalness: .7, roughness: .24});
  const aperture = new THREE.Mesh(new THREE.TorusGeometry(.22, .035, 8, 24), material("#8f9da3", {metalness: .85, roughness: .3}));
  aperture.position.z = .38; group.add(aperture);
  for (const side of [-1, 1]) {
    fastener(group, side * .32, -.16, .33, "#ced9d9", .025);
    fastener(group, side * .32, .16, .33, "#ced9d9", .025);
  }
  const lamp = ball(group, "#ff8a3d", [0, 0, .39], [.16, .16, .12], {emissive: "#ff8a3d", emissiveIntensity: 2});
  glowSprite(group, [0, 0, .43], [.72, .72, 1], "#ff8a3d", .72);
  const fins = [];
  for (let i = 0; i < 4; i += 1) {
    const fin = new THREE.Group();
    fin.rotation.z = i * Math.PI / 2 + Math.PI / 4;
    group.add(fin);
    rod(fin, [0, .22, 0], [0, .68, 0], "#7a8b99", .045, {metalness: .8, roughness: .25});
    panel(fin, [[-.1,.38],[-.18,.64],[0,.79],[.18,.64],[.1,.38]], "#6d7c85",
      {position: [0, 0, -.015], metalness: .8, roughness: .38});
    const tip = ball(fin, i % 2 ? "#ffb35c" : "#c9d2db", [0, .7, .01], [.11, .14, .07], {
      emissive: i % 2 ? "#ff8a3d" : "#6d8797", emissiveIntensity: .5,
    });
    fins.push({fin, tip});
  }
  group.userData.lamp = lamp;
  group.userData.fins = fins;
  return group;
}

function canisterModel(parent, colourHex = "#c7a441") {
  const group = new THREE.Group();
  parent.add(group);
  const body = new THREE.Mesh(new THREE.CylinderGeometry(.62, .62, 1.15, 12), material(colourHex, {metalness: .64, roughness: .28}));
  group.add(body);
  const stripe = new THREE.Mesh(new THREE.CylinderGeometry(.635, .635, .2, 12), material("#302a20", {metalness: .38, roughness: .35}));
  group.add(stripe);
  for (let i = 0; i < 8; i += 1) {
    const angle = i * Math.PI / 4;
    rod(group, [Math.cos(angle) * .6, -.46, Math.sin(angle) * .6], [Math.cos(angle) * .6, .46, Math.sin(angle) * .6],
      "#695830", .025, {metalness: .7, roughness: .4});
  }
  const lip = new THREE.Mesh(new THREE.TorusGeometry(.58, .05, 6, 16), material("#f0d58a", {metalness: .72, roughness: .2}));
  lip.rotation.x = Math.PI / 2;
  lip.position.y = .5; group.add(lip);
  const base = new THREE.Mesh(new THREE.CylinderGeometry(.66, .66, .1, 12), material("#514b3e", {metalness: .75, roughness: .35}));
  base.position.y = -.57; group.add(base);
  return group;
}

function starModel(parent, tone, scale = .11) {
  const group = new THREE.Group();
  parent.add(group);
  const star = new THREE.Mesh(new THREE.OctahedronGeometry(1, 0), material("#ffffff", {
    emissive: tone.glow, emissiveIntensity: 1.6, metalness: .18, roughness: .2,
  }));
  star.scale.setScalar(scale);
  group.add(star);
  const glow = glowSprite(group, [0, 0, -.02], [scale * 5.4, scale * 5.4, 1], tone.glow, .62);
  return {group, star, glow};
}

function orbModel(parent, tone) {
  const group = new THREE.Group();
  parent.add(group);
  const orb = ball(group, tone.glow, [0, 0, 0], [.15, .15, .15], {emissive: tone.glow, emissiveIntensity: 1.8, roughness: .18});
  const inner = ball(group, "#ffffff", [-.04, .045, .12], [.045, .045, .035], {emissive: "#ffffff", emissiveIntensity: .6});
  const glow = glowSprite(group, [0, 0, -.04], [.9, .9, 1], tone.glow, .68);
  const orbit = new THREE.Mesh(new THREE.TorusGeometry(.23, .008, 6, 32), material(tone.line, {
    emissive: tone.glow, emissiveIntensity: .8, transparent: true, opacity: .72, metalness: .4,
  }));
  orbit.rotation.set(.35, .2, .1);
  group.add(orbit);
  ball(group, tone.line, [.22, 0, 0], [.025, .025, .025], {emissive: tone.glow, emissiveIntensity: 1.3});
  return {group, orb, inner, glow};
}

function propKey(toys, activity, tone) {
  const name = activity?.name || "";
  const special = ["keepy", "tower", "tag", "chase", "stars", "stargaze", "holo"].includes(name)
    || (name === "trick" && activity?.trick === "juggle") ? name : "";
  return JSON.stringify([toys.map((toy) => toy.kind), special, activity?.toy?.kind || "", activity?.trick || "",
    activity?.stars?.points?.length || 0, tone.glow, tone.line]);
}

function buildProps(view, toys, activity, tone) {
  if (view.props) {
    view.scene.remove(view.props);
    dispose(view.props);
  }
  const root = new THREE.Group();
  view.scene.add(root);
  const state = {root, toys: [], activity: null};
  for (const toy of toys) {
    state.toys.push({kind: toy.kind, group: toyModel(root, toy.kind, tone)});
  }
  const name = activity?.name;
  if (name === "keepy") state.activity = {kind: name, model: limpetModel(root, tone)};
  else if (name === "tower") {
    state.activity = {kind: name, cans: Array.from({length: 8}, (_, i) => ({model: canisterModel(root), index: i})),
      drop: canisterModel(root, "#d8aa39")};
  } else if (name === "tag") state.activity = {kind: name, model: toyModel(root, "sensor", tone)};
  else if (name === "chase" || name === "stargaze" || name === "holo") state.activity = {kind: name, model: orbModel(root, tone)};
  else if (name === "stars") {
    const count = Math.min(9, activity?.stars?.points?.length || 0);
    const stars = Array.from({length: count}, () => starModel(root, tone, .075));
    const links = Array.from({length: Math.max(0, count - 1)}, () => {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute([0, 0, 0, 0, 0, 0], 3));
      const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({color: tone.glow, transparent: true, opacity: .58, depthWrite: false}));
      root.add(line);
      return line;
    });
    state.activity = {kind: name, stars, links};
  } else if (name === "trick" && activity?.trick === "juggle") {
    state.activity = {kind: "juggle", balls: ["#ff8a3d", "#54e39a", "#7fe8ff"].map((hex) => {
      const model = new THREE.Group(); root.add(model);
      ball(model, hex, [0, 0, 0], [.075, .075, .075], {emissive: hex, emissiveIntensity: .34, roughness: .22});
      return model;
    })};
  }
  view.props = root;
  view.propState = state;
  return state;
}

function positionProps(state, toys, activity, size, t, tone) {
  if (!state) return;
  const xScale = 3.4 / (size * 1.4), yScale = 3.4 / (size * 1.4);
  const toWorld = (x, y, z = .15) => new THREE.Vector3(x * xScale, -(y + size * .08) * yScale, z);
  const floorY = 44 * size / 100;
  state.toys.forEach((entry, index) => {
    const toy = toys[index];
    if (!toy) { entry.group.visible = false; return; }
    entry.group.visible = true;
    const playing = activity?.name === "toy" && activity.toy?.kind === toy.kind;
    entry.group.position.copy(toWorld(toy.x, toy.y ?? floorY, playing ? .62 : .17));
    entry.group.scale.setScalar(playing ? .31 : .23);
    entry.group.rotation.y = Math.sin(t * .65 + index) * .13;
    entry.group.rotation.z = playing ? Math.sin(t * 5) * .16 : Math.sin(t * .8 + index * 1.7) * .035;
  });
  const prop = state.activity;
  if (!prop) return;
  if (prop.kind === "keepy" && activity?.ball) {
    prop.model.position.copy(toWorld(activity.ball.x, activity.ball.y, .78));
    prop.model.scale.setScalar(.42);
    prop.model.rotation.z = activity.ball.spin || 0;
    prop.model.userData.fins?.forEach(({fin}, i) => { fin.rotation.x = Math.sin(t * 13 + i) * .14; });
  } else if (prop.kind === "tower" && activity?.tower) {
    const tower = activity.tower;
    prop.cans.forEach(({model, index}) => {
      model.visible = index < tower.cans;
      model.position.copy(toWorld(tower.x, floorY - (index + .5) * 13 * size / 100, .2));
      model.rotation.z = tower.lean || 0;
      model.scale.set(.15, .15, .15);
    });
    prop.drop.visible = Boolean(tower.drop);
    if (tower.drop) prop.drop.position.copy(toWorld(tower.x, tower.drop.y, .23));
    prop.drop.scale.set(.15, .15, .15);
  } else if (prop.kind === "tag" && activity?.thargon) {
    prop.model.position.copy(toWorld(activity.thargon.x, activity.thargon.y, .78));
    prop.model.scale.setScalar(.32);
    prop.model.rotation.z = activity.thargon.spin || t * 2;
  } else if (prop.kind === "chase" && activity?.mote) {
    prop.model.group.position.copy(toWorld(activity.mote.x, activity.mote.y, .35));
    const pulse = .88 + (Math.sin(t * 9) + 1) * .1;
    prop.model.group.scale.setScalar(pulse);
  } else if (prop.kind === "stargaze" && activity?.star) {
    prop.model.group.position.copy(toWorld(activity.star.x, activity.star.y, .25));
    prop.model.group.rotation.z = t * .7;
  } else if (prop.kind === "holo" && activity?.orb) {
    prop.model.group.position.copy(toWorld(activity.orb.x, activity.orb.y, .36));
    prop.model.group.rotation.y = t * .8;
    prop.model.group.scale.setScalar(.92 + (Math.sin(t * 3.6) + 1) * .08);
  } else if (prop.kind === "stars" && activity?.stars) {
    const points = activity.stars.points || [];
    prop.stars.forEach((entry, index) => {
      const point = points[index];
      entry.group.visible = Boolean(point);
      if (!point) return;
      entry.group.position.copy(toWorld(point.x, point.y, .2));
      entry.star.material.emissiveIntensity = index < activity.stars.lit ? 1.9 : .35;
      entry.glow.material.opacity = index < activity.stars.lit ? .7 : .14;
      entry.group.scale.setScalar(activity.stars.fade ?? 1);
    });
    prop.links.forEach((line, index) => {
      const first = points[index], second = points[index + 1];
      const visible = first && second && index < activity.stars.lit - 1;
      line.visible = Boolean(visible);
      if (!visible) return;
      const values = line.geometry.attributes.position.array;
      values.set([...toWorld(first.x, first.y, .18).toArray(), ...toWorld(second.x, second.y, .18).toArray()]);
      line.geometry.attributes.position.needsUpdate = true;
      line.material.opacity = .58 * (activity.stars.fade ?? 1);
    });
  } else if (prop.kind === "juggle") {
    prop.balls.forEach((ballModel, index) => {
      const phase = t * 2.8 + index * Math.PI * 2 / 3;
      ballModel.position.copy(toWorld(Math.sin(phase) * size * .17, -size * (.43 + Math.max(0, Math.cos(phase)) * .21), .42));
      ballModel.rotation.set(phase, phase * .7, phase * .4);
    });
  }
  if (prop.model?.userData?.petals) prop.model.userData.petals.forEach((petal, i) => { petal.rotation.x = Math.sin(t * 2 + i) * .05; });
  if (prop.model?.userData?.lamp) prop.model.userData.lamp.material.emissiveIntensity = 1.1 + (Math.sin(t * 7) + 1) * .65;
}

function shadowTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext("2d");
  const gradient = ctx.createRadialGradient(64, 64, 4, 64, 64, 61);
  gradient.addColorStop(0, "rgba(1, 5, 8, .56)");
  gradient.addColorStop(.55, "rgba(1, 5, 8, .24)");
  gradient.addColorStop(1, "rgba(1, 5, 8, 0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 128, 128);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function createView(canvas) {
  const renderer = new THREE.WebGLRenderer({canvas, alpha: true, antialias: true, powerPreference: "low-power", stencil: false});
  renderer.setPixelRatio(1);
  renderer.setSize(SIZE, SIZE, false);
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.02;
  const scene = new THREE.Scene();
  // The transparent image is composited into a wider-than-tall rectangle.
  // Match the camera to that rectangle so circular details stay circular.
  const halfWidth = 1.7 * 1.64 / 1.4;
  // Extra room above the model keeps high toys and effects in the viewport.
  // The bottom and world-to-pixel scale remain unchanged.
  const camera = new THREE.OrthographicCamera(-halfWidth, halfWidth, 2.35, -1.7, .1, 30);
  camera.position.set(0, 0, 8);
  camera.lookAt(0, 0, 0);
  scene.add(new THREE.HemisphereLight(0xb7d8e0, 0x0e1722, .95));
  const key = new THREE.DirectionalLight(0xffe5c2, 2.8);
  key.position.set(-3, 4, 5);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0x65c8ff, .8);
  fill.position.set(3, 1, 3);
  scene.add(fill);
  const rim = new THREE.DirectionalLight(0x9dffd2, 2.0);
  rim.position.set(0, 2, -4);
  scene.add(rim);
  const shadow = new THREE.Mesh(PLANE, new THREE.MeshBasicMaterial({map: shadowTexture(), transparent: true, depthWrite: false}));
  shadow.position.set(0, -1.12, -.25);
  scene.add(shadow);
  const aura = glowSprite(scene, [0, -.12, -1.05], [2.8, 2.7, 1], "#73eaff", .42);
  aura.renderOrder = 0;
  const root = new THREE.Group();
  scene.add(root);
  return {renderer, scene, camera, root, aura, shadow, renderSize: SIZE, models: new Map(), model: null, props: null, propKey: "", propState: null};
}

export class HatchlingRenderer3D {
  constructor() {
    this.views = new WeakMap();
    this.failedCanvases = new WeakSet();
  }

  draw(ctx, pet, {x, y, size, t = 0, look = [0, 0], squash = 0, lift = 0, aura = true, shadow = true, act = "", dance = "", activity = null, toys = [], resolution = 0} = {}) {
    if (!ctx?.canvas || !pet || !Number.isFinite(size) || size <= 0) return false;
    const host = ctx.canvas;
    if (this.failedCanvases.has(host)) return false;
    let view = this.views.get(host);
    try {
      if (!view) {
        view = createView(document.createElement("canvas"));
        this.views.set(host, view);
      }
      // Large deck habitats need more pixels; tiny overlay pets keep the
      // cheaper backing size. Quantising avoids resizing on every frame.
      const transform = ctx.getTransform?.();
      const density = Math.max(1, Math.abs(transform?.a || 1), Math.abs(transform?.d || 1));
      const renderSize = THREE.MathUtils.clamp(Math.max(resolution, Math.ceil(size * 1.64 * density / 64) * 64), SIZE, resolution ? 1536 : 640);
      if (renderSize !== view.renderSize) {
        view.renderer.setSize(renderSize, renderSize, false);
        view.renderSize = renderSize;
      }
      const tone = window.HatchlingArt?.tones?.(pet) || {light: "#4ee5b0", dark: "#06261c", line: "#6bffc8", glow: "#9dffd2", eye: "#eafff6", iris: "#0e6b4b", vein: "#b6ffe0"};
      const key = JSON.stringify([pet.species, pet.kind, pet.sample_kind, pet.stage, pet.form, pet.outfit, pet.sick, pet.dormant,
        pet.asleep || pet.eyesShut, pet.reaction, pet.mood_word, tone.light, tone.dark, tone.line, tone.glow, tone.eye, tone.iris, tone.vein]);
      let entry = view.models.get(key);
      if (!entry) {
        const group = new THREE.Group();
        view.root.add(group);
        const model = pet.stage === "egg" ? makeEgg(group, pet, tone)
          : pet.species === "bot" ? makeBot(group, pet, tone)
            : pet.species === "thargoid" ? makeThargoid(group, pet, tone)
            : pet.species === "sample" ? makeSample(group, pet, tone) : makeLarva(group, pet, tone);
        refineModel(model, pet, tone);
        if (pet.form) model.details = formMarks(model.body, pet, tone);
        model.outfit = pet.stage === "egg" ? null : makeOutfit(model.body, pet, tone);
        model.sparks = sparkField(group, tone, pet.species);
        entry = {group, model};
        view.models.set(key, entry);
      } else {
        // The game shows three eggs side by side. Keep recent models ready so
        // each frame changes visibility instead of rebuilding their geometry.
        view.models.delete(key);
        view.models.set(key, entry);
      }
      for (const [modelKey, modelEntry] of view.models) modelEntry.group.visible = modelKey === key;
      while (view.models.size > 8) {
        const [oldestKey, oldest] = view.models.entries().next().value;
        view.models.delete(oldestKey);
        view.root.remove(oldest.group);
        dispose(oldest.group);
      }
      view.model = entry.model;
      view.shadow.visible = Boolean(shadow);
      const nextPropKey = propKey(toys, activity, tone);
      if (view.propKey !== nextPropKey) {
        view.propState = buildProps(view, toys, activity, tone);
        view.propKey = nextPropKey;
      }
      positionProps(view.propState, toys, activity, size, t, tone);
      const still = pet.asleep || pet.dormant;
      const action = activity?.name || act;
      const patting = action === "pat" && !still;
      const patPhase = Math.min(1, Math.max(0, Number(activity?.t) || 0) / 1.8);
      const patGesture = patting ? Math.sin(patPhase * Math.PI) : 0;
      const breathing = still ? 1 + Math.sin(t * 1.2) * .012 : 1 + Math.sin(t * 2.2) * .023;
      const stretch = action === "stretch" ? Math.sin(Math.min(1, (activity?.t || 0) / .7) * Math.PI) * .13 : 0;
      const crouch = action === "groom" ? .035 : action === "toy" || action === "keepy" || action === "tag" ? -.025 : 0;
      const spring = patting ? 0 : squash;
      const scaleX = (1 + spring * .22) * breathing * (1 - stretch * .18);
      const scaleY = (1 - spring * .22 + stretch + crouch) / breathing;
      if (!view.model.body.userData.baseScaleX) {
        view.model.body.userData.baseScaleX = view.model.body.scale.x / scaleX;
        view.model.body.userData.baseScaleY = view.model.body.scale.y / scaleY;
      }
      view.model.body.scale.x = view.model.body.userData.baseScaleX * scaleX;
      view.model.body.scale.y = view.model.body.userData.baseScaleY * scaleY;
      view.model.body.position.y = (view.model.body.userData.restY || 0) + (lift / size) * 1.45 + (still ? 0 : Math.sin(t * 2.2) * .025);
      const dancing = action === "dance";
      const grooving = activity?.style || dance;
      const dancePhase = (activity?.t || 0) * Math.PI * 2 / THREE.MathUtils.clamp(Number(activity?.period) || .5, .25, 1.5);
      const beat = Math.sin(dancePhase);
      const slowBeat = Math.sin(dancePhase / 2);
      const robotStep = beat >= 0 ? 1 : -1;
      view.model.body.position.x = action === "groom" ? Math.sin((activity?.t || 0) * 5) * .025 : 0;
      view.model.body.rotation.z = still ? 0 : action === "stretch" ? Math.sin(t * 3) * .025
        : action === "groom" ? Math.sin((activity?.t || 0) * 5) * .035
          : Math.sin(t * (dancing ? 6.5 : 1.4)) * (dancing ? .095 : .014);
      view.model.body.rotation.x = dancing ? Math.sin(t * 5.1 + (grooving === "spin" ? 1.4 : 0)) * .055
        : action === "yawn" || action === "doze" ? -.035 : action === "stretch" ? -.045 : 0;
      view.model.body.rotation.y = still ? 0 : THREE.MathUtils.clamp(Number(look?.[0] || 0), -1, 1) * .12 + Math.sin(t * .7) * .025;
      if (patting) {
        // Lean into the touch and nod, keeping the creature's shape intact.
        view.model.body.rotation.x -= patGesture * .19;
        view.model.body.rotation.z += patGesture * .10;
        view.model.body.position.y += patGesture * .045;
      }
      if (dancing && !still) {
        // These are articulated 3D poses; the life simulation also supplies
        // the larger hops and movement around the habitat.
        if (grooving === "sway") {
          view.model.body.rotation.z = slowBeat * .16;
          view.model.body.rotation.y += slowBeat * .08;
        } else if (grooving === "headbang") {
          view.model.body.rotation.x = -.16 - beat * .16;
          view.model.body.rotation.z = slowBeat * .055;
        } else if (grooving === "robot") {
          view.model.body.rotation.z = robotStep * .11;
          view.model.body.rotation.y += robotStep * .13;
        } else if (grooving === "shuffle") {
          view.model.body.position.x = slowBeat * .07;
          view.model.body.rotation.z = slowBeat * .12;
          view.model.body.rotation.y += slowBeat * .12;
        } else {
          view.model.body.rotation.z = slowBeat * .11;
          view.model.body.rotation.x = beat * .06;
        }
      }
      if (view.model.core) {
        const pulse = 1 + Math.sin(t * 3.2) * (still ? .035 : .09);
        if (!view.model.core.userData.baseScale) view.model.core.userData.baseScale = view.model.core.scale.clone();
        view.model.core.scale.copy(view.model.core.userData.baseScale).multiplyScalar(pulse);
        view.model.core.material.emissiveIntensity = .42 + (Math.sin(t * 3.2) + 1) * .17;
      }
      if (view.model.coreGlow) view.model.coreGlow.material.opacity = .26 + (Math.sin(t * 3.2) + 1) * .10;
      if (view.model.thruster) {
        const thrusting = !still && pet.stage !== "adult";
        view.model.thruster.visible = view.model.thrusterGlow.visible = thrusting;
        view.model.thruster.scale.y = .82 + (Math.sin(t * 19) + 1) * .18;
        view.model.thruster.material.opacity = .46 + (Math.sin(t * 19) + 1) * .14;
      }
      view.aura.visible = Boolean(aura);
      view.aura.material.color.set(tone.glow);
      view.aura.material.opacity = aura ? (pet.dormant ? .2 : .34 + Math.max(0, Number(pet.needs?.mood ?? 60)) / 100 * .23) : 0;
      for (const spark of view.model.sparks) {
        const angle = spark.angle + t * (dancing ? 1.1 : .32);
        const px = Math.cos(angle) * spark.radius, py = Math.sin(angle * 1.3) * .73 - .12, pz = .2 + Math.sin(angle) * .12;
        spark.mesh.position.set(px, py, pz);
        spark.mesh.rotation.set(t * .8 + spark.angle, t * .65, t * .45 + spark.angle);
        spark.mesh.scale.setScalar(.6 + (Math.sin(t * (dancing ? 5 : 2) + spark.angle) + 1) * (dancing ? .43 : .25));
        if (spark.glow) {
          spark.glow.visible = Boolean(aura);
          spark.glow.position.set(px, py, pz - .015);
          spark.glow.material.opacity = .24 + (Math.sin(t * 2.4 + spark.angle) + 1) * .16;
        }
      }
      const blink = pet.asleep || pet.eyesShut || (pet.reaction !== "scared" && (Math.sin(t * 1.3 + 1) > .985 || Math.sin(t * .37) > .997));
      for (const part of view.model.eyes) {
        part.eye.scale.y = blink ? .16 : 1;
        part.iris.position.x = THREE.MathUtils.clamp(Number(look?.[0] || 0) * .035, -.035, .035);
        part.iris.position.y = -.005 + THREE.MathUtils.clamp(-Number(look?.[1] || 0) * .035, -.035, .035);
        part.pupil.position.x = part.iris.position.x;
        part.pupil.position.y = part.iris.position.y + .005;
      }
      for (const [index, appendage] of view.model.appendages.entries()) {
        const side = appendage.position.x < 0 ? -1 : 1;
        const idle = Math.sin(t * (still ? .5 : dancing ? 5.4 : 2.4) + index * 1.7);
        appendage.rotation.z = action === "stretch" ? side * (.25 + stretch * 2.2) + idle * .035
          : action === "groom" && index === 0 ? -.42 + idle * .08
            : action === "wave" && index === 0 ? Math.sin(t * 7) * .34
              : idle * (still ? .018 : dancing ? .2 : .07);
        if (dancing && !still) {
          if (grooving === "robot") appendage.rotation.z = side * robotStep * .28;
          else if (grooving === "shuffle") appendage.rotation.z = side * Math.sin(dancePhase + index * Math.PI / 2) * .28;
          else if (grooving === "headbang") appendage.rotation.z = side * (.12 + beat * .16);
          else appendage.rotation.z = side * slowBeat * .18 + idle * .06;
        }
        if (appendage.userData.thargoidPetal !== undefined) {
          // Each radial segment flexes at its own root in 3D, including when
          // the foundling sways or dances to the music.
          const phase = t * (still ? .45 : dancing ? 4.2 : 1.6) + index * .77;
          const amount = still ? .018 : dancing ? .16 : .07;
          appendage.rotation.x = Math.sin(phase) * amount;
          appendage.rotation.y = Math.cos(phase * .8) * amount * .6;
          appendage.rotation.z = Math.sin(phase + .4) * amount * .7;
          if (action === "unfurl" && !still) {
            const opening = Math.sin(Math.min(1, (activity?.t || 0) / 2.5) * Math.PI);
            appendage.rotation.x += opening * .34;
            appendage.rotation.y += opening * Math.sin(index * 1.3) * .12;
            appendage.rotation.z += opening * .1;
          }
          if (patting) {
            // The foundling's radial petals have their own 3D joints.
            appendage.rotation.x += patGesture * (.18 + .035 * Math.sin(index));
            appendage.rotation.y += patGesture * Math.sin(index * 1.3) * .07;
          }
        } else if (patting) {
          appendage.rotation.z += side * patGesture * .22;
        }
      }
      if (view.model.outfit?.tail) view.model.outfit.tail.rotation.z = Math.sin(t*1.7)*.09 + Math.sin(t*.7)*.025;
      if (view.model.outfit?.pendant) view.model.outfit.pendant.rotation.z = Math.sin(t*1.25)*.12;
      view.renderer.render(view.scene, view.camera);
      ctx.drawImage(view.renderer.domElement, x - size * .82, y - size * (1.4 * 4.05 / 3.4 - .62),
        size * 1.64, size * (1.4 * 4.05 / 3.4));
      return true;
    } catch (error) {
      this.failedCanvases.add(host);
      console.warn("Hatchling's 3D renderer unavailable; keeping the canvas artwork.", error);
      if (view) {
        try { view.renderer.dispose(); } catch { /* The page may already be closing. */ }
      }
      return false;
    }
  }
}

// Classic scripts use the same one renderer in the game and transparent HUD.
window.Hatchling3D = new HatchlingRenderer3D();
