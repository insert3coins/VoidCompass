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
  for (let i = 0; i < 190; i += 1) {
    const x = random() * 256, y = random() * 128, radius = 1.5 + random() * 8;
    ctx.globalAlpha = style === "tech" ? .06 + random() * .08 : .08 + random() * .15;
    ctx.fillStyle = random() > .48 ? tone.dark : tone.glow;
    ctx.beginPath();
    ctx.ellipse(x, y, radius * (1 + random()), radius * (.45 + random() * .8), random() * Math.PI, 0, Math.PI * 2);
    ctx.fill();
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
  } else {
    ctx.globalAlpha = .3;
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
    if (!bot) ball(eye, tone.eye, [0, 0, .015], [.16, .195, .07], {roughness: .2, clearcoat: 1});
    const iris = ball(eye, tone.iris, [0, -.005, .085], [bot ? .115 : .1, bot ? .105 : .11, .055], {
      emissive: tone.iris, emissiveIntensity: .12, roughness: .2,
    });
    const pupil = ball(eye, bot ? tone.glow : "#071315", [0, 0, .13], [.052, .065, .03], {
      emissive: bot ? tone.glow : "#000000", emissiveIntensity: bot ? .8 : 0, roughness: .12,
    });
    ball(eye, "#ffffff", [-.027, .038, .16], [.025, .025, .014], {roughness: .08, emissive: "#ffffff", emissiveIntensity: .25});
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
  ball(body, tone.dark, [0, -.25, -.06], [.76, .78, .5], {roughness: .48, metalness: .06});
  texturedBall(body, tone, "organic", [0, -.11, .2], [.72, .72, .48], {emissive: tone.dark, emissiveIntensity: .16, roughness: .28});
  // Layered carapace plates frame its eyes and give the larva a sharp silhouette.
  for (const side of [-1, 1]) {
    ball(body, tone.dark, [side * .56, -.18, .2], [.27, .43, .24], {roughness: .36, metalness: .14});
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
      ball(limb, tone.line, [side * .2, -reach, .1], [.07, .06, .07], {emissive: tone.glow, emissiveIntensity: .65});
      legs.push(limb);
    }
  }
  const eyeParts = face(body, pet, tone);
  return {body, eyes: eyeParts, appendages: legs, core, coreGlow};
}

function makeBot(root, pet, tone) {
  const body = new THREE.Group();
  root.add(body);
  const grown = pet.stage === "adult" ? 1.13 : pet.stage === "juvenile" ? 1.03 : .88;
  body.scale.setScalar(grown);
  ball(body, tone.dark, [0, -.15, -.04], [.78, .78, .51], {metalness: .72, roughness: .34});
  texturedBall(body, tone, "tech", [0, -.1, .12], [.7, .72, .52], {metalness: .64, roughness: .26, clearcoat: .95});
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
      texturedBall(frond, tone, "cell", [x * .5, height * .65 + .4, -.03], [.2, .22, .18], {
        emissive: tone.dark, emissiveIntensity: .28, roughness: .24, clearcoat: 1,
      });
      ball(frond, tone.line, [x * .5, height * .77 + .4, .09], [.055, .055, .04], {emissive: tone.glow, emissiveIntensity: 1.25});
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
  }
  const eyeParts = face(body, pet, tone, {small: kind !== "tubus"});
  return {body, eyes: eyeParts, appendages: fronds};
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
    ball(group, "#bdedff", [0, 0, .49], [.16, .16, .12], {emissive: "#6bd7ff", emissiveIntensity: 1.5});
  } else if (kind === "sensor") {
    const petals = [];
    for (let i = 0; i < 5; i += 1) {
      const petal = new THREE.Group();
      petal.rotation.z = i * Math.PI * 2 / 5;
      group.add(petal);
      ball(petal, "#182622", [0, .43, 0], [.18, .39, .12], {metalness: .54, roughness: .28});
      ball(petal, "#416746", [0, .55, .08], [.08, .21, .08], {emissive: tone.glow, emissiveIntensity: .2});
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
  } else if (kind === "beacon") {
    const base = new THREE.Mesh(new THREE.CylinderGeometry(.52, .65, .3, 8), material("#394855", {metalness: .75, roughness: .29}));
    base.position.y = -.39; group.add(base);
    rod(group, [0, -.3, 0], [0, .48, 0], "#a7b5c1", .07, {metalness: .82, roughness: .22});
    const lamp = ball(group, "#ffd166", [0, .57, .02], [.2, .2, .2], {emissive: "#ffb52e", emissiveIntensity: 1.8});
    glowSprite(group, [0, .61, .02], [.9, .9, 1], "#ffd166", .64);
    group.userData.lamp = lamp;
  } else if (kind === "station" || kind === "model") {
    const body = new THREE.Mesh(new THREE.BoxGeometry(1.12, 1.12, .78), material("#9eabb7", {metalness: .72, roughness: .31}));
    group.add(body);
    const port = new THREE.Mesh(new THREE.TorusGeometry(.28, .07, 8, 24), material(tone.line, {emissive: tone.glow, emissiveIntensity: .6, metalness: .65}));
    port.position.z = .43; group.add(port);
    for (const side of [-1, 1]) {
      const wing = new THREE.Mesh(new THREE.BoxGeometry(.72, .18, .32), material("#65727e", {metalness: .74, roughness: .3}));
      wing.position.set(side * .76, 0, 0); group.add(wing);
      ball(group, tone.glow, [side * 1.07, 0, .18], [.07, .07, .07], {emissive: tone.glow, emissiveIntensity: 1.2});
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
  const lamp = ball(group, "#ff8a3d", [0, 0, .39], [.16, .16, .12], {emissive: "#ff8a3d", emissiveIntensity: 2});
  glowSprite(group, [0, 0, .43], [.72, .72, 1], "#ff8a3d", .72);
  const fins = [];
  for (let i = 0; i < 4; i += 1) {
    const fin = new THREE.Group();
    fin.rotation.z = i * Math.PI / 2 + Math.PI / 4;
    group.add(fin);
    rod(fin, [0, .22, 0], [0, .68, 0], "#7a8b99", .045, {metalness: .8, roughness: .25});
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
  const lip = new THREE.Mesh(new THREE.TorusGeometry(.58, .05, 6, 16), material("#f0d58a", {metalness: .72, roughness: .2}));
  lip.position.y = .5; group.add(lip);
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
  const xScale = 3.4 / (size * 1.64), yScale = 3.4 / (size * 1.4);
  const toWorld = (x, y, z = .15) => new THREE.Vector3(x * xScale, -(y + size * .08) * yScale, z);
  const floorY = 44 * size / 100;
  state.toys.forEach((entry, index) => {
    const toy = toys[index];
    if (!toy) { entry.group.visible = false; return; }
    entry.group.visible = true;
    const playing = activity?.name === "toy" && activity.toy?.kind === toy.kind;
    entry.group.position.copy(toWorld(toy.x, toy.y ?? floorY, playing ? .62 : .17));
    entry.group.scale.setScalar(playing ? .23 : .18);
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
  renderer.toneMappingExposure = 1.12;
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1.7, 1.7, 1.7, -1.7, .1, 30);
  camera.position.set(0, 0, 8);
  camera.lookAt(0, 0, 0);
  scene.add(new THREE.HemisphereLight(0xc8f4ff, 0x13212d, 2.05));
  const key = new THREE.DirectionalLight(0xfff1d7, 3.1);
  key.position.set(-3, 4, 5);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0x65c8ff, 1.65);
  fill.position.set(3, 1, 3);
  scene.add(fill);
  const rim = new THREE.DirectionalLight(0x9dffd2, 2.2);
  rim.position.set(0, 2, -4);
  scene.add(rim);
  const shadow = new THREE.Mesh(PLANE, new THREE.MeshBasicMaterial({map: shadowTexture(), transparent: true, depthWrite: false}));
  shadow.position.set(0, -1.12, -.25);
  scene.add(shadow);
  const aura = glowSprite(scene, [0, -.12, -1.05], [2.8, 2.7, 1], "#73eaff", .42);
  aura.renderOrder = 0;
  const root = new THREE.Group();
  scene.add(root);
  return {renderer, scene, camera, root, aura, shadow, models: new Map(), model: null, props: null, propKey: "", propState: null};
}

export class HatchlingRenderer3D {
  constructor() {
    this.views = new WeakMap();
    this.failedCanvases = new WeakSet();
  }

  draw(ctx, pet, {x, y, size, t = 0, look = [0, 0], squash = 0, lift = 0, aura = true, shadow = true, act = "", dance = "", activity = null, toys = []} = {}) {
    if (!ctx?.canvas || !pet || !Number.isFinite(size) || size <= 0) return false;
    const host = ctx.canvas;
    if (this.failedCanvases.has(host)) return false;
    let view = this.views.get(host);
    try {
      if (!view) {
        view = createView(document.createElement("canvas"));
        this.views.set(host, view);
      }
      const tone = window.HatchlingArt?.tones?.(pet) || {light: "#4ee5b0", dark: "#06261c", line: "#6bffc8", glow: "#9dffd2", eye: "#eafff6", iris: "#0e6b4b", vein: "#b6ffe0"};
      const key = JSON.stringify([pet.species, pet.kind, pet.sample_kind, pet.stage, pet.form, pet.sick, pet.dormant,
        pet.asleep || pet.eyesShut, pet.reaction, pet.mood_word, tone.light, tone.dark, tone.line, tone.glow, tone.eye, tone.iris, tone.vein]);
      let entry = view.models.get(key);
      if (!entry) {
        const group = new THREE.Group();
        view.root.add(group);
        const model = pet.stage === "egg" ? makeEgg(group, pet, tone)
          : pet.species === "bot" ? makeBot(group, pet, tone)
            : pet.species === "sample" ? makeSample(group, pet, tone) : makeLarva(group, pet, tone);
        if (pet.form) model.details = formMarks(group, pet, tone);
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
      const breathing = still ? 1 + Math.sin(t * 1.2) * .012 : 1 + Math.sin(t * 2.2) * .023;
      const stretch = action === "stretch" ? Math.sin(Math.min(1, (activity?.t || 0) / .7) * Math.PI) * .13 : 0;
      const crouch = action === "groom" ? .035 : action === "toy" || action === "keepy" || action === "tag" ? -.025 : 0;
      const scaleX = (1 + squash * .22) * breathing * (1 - stretch * .18);
      const scaleY = (1 - squash * .22 + stretch + crouch) / breathing;
      if (!view.model.body.userData.baseScaleX) {
        view.model.body.userData.baseScaleX = view.model.body.scale.x / scaleX;
        view.model.body.userData.baseScaleY = view.model.body.scale.y / scaleY;
      }
      view.model.body.scale.x = view.model.body.userData.baseScaleX * scaleX;
      view.model.body.scale.y = view.model.body.userData.baseScaleY * scaleY;
      view.model.body.position.y = (lift / size) * 1.45 + (still ? 0 : Math.sin(t * 2.2) * .025);
      const dancing = action === "dance";
      const grooving = activity?.style || dance;
      view.model.body.position.x = action === "groom" ? Math.sin((activity?.t || 0) * 5) * .025 : 0;
      view.model.body.rotation.z = still ? 0 : action === "stretch" ? Math.sin(t * 3) * .025
        : action === "groom" ? Math.sin((activity?.t || 0) * 5) * .035
          : Math.sin(t * (dancing ? 6.5 : 1.4)) * (dancing ? .095 : .014);
      view.model.body.rotation.x = dancing ? Math.sin(t * 5.1 + (grooving === "spin" ? 1.4 : 0)) * .055
        : action === "yawn" || action === "doze" ? -.035 : action === "stretch" ? -.045 : 0;
      if (view.model.core) {
        const pulse = 1 + Math.sin(t * 3.2) * (still ? .035 : .09);
        if (!view.model.core.userData.baseScale) view.model.core.userData.baseScale = view.model.core.scale.clone();
        view.model.core.scale.copy(view.model.core.userData.baseScale).multiplyScalar(pulse);
        view.model.core.material.emissiveIntensity = 1.45 + (Math.sin(t * 3.2) + 1) * .45;
      }
      if (view.model.coreGlow) view.model.coreGlow.material.opacity = .48 + (Math.sin(t * 3.2) + 1) * .16;
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
        const side = index % 2 ? 1 : -1;
        const idle = Math.sin(t * (still ? .5 : dancing ? 5.4 : 2.4) + index * 1.7);
        appendage.rotation.z = action === "stretch" ? side * (.25 + stretch * 2.2) + idle * .035
          : action === "groom" && index === 0 ? -.42 + idle * .08
            : action === "wave" && index === 0 ? Math.sin(t * 7) * .34
              : idle * (still ? .018 : dancing ? .2 : .07);
      }
      view.renderer.render(view.scene, view.camera);
      ctx.drawImage(view.renderer.domElement, x - size * .82, y - size * .78, size * 1.64, size * 1.4);
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
