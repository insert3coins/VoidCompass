// Three-dimensional housing and optics for the Watcher. Its established
// canvas painter remains the live lens, so journal effects, expressions,
// lore and reduced-motion behavior all come from the same source.
import * as THREE from '../galactic_map/vendor/three.module.min.js';

const views = new WeakMap();
const failed = new WeakSet();
const TAU = Math.PI * 2;

function random(seed) {
  return () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
}

function ring(group, radius, tube, color, metalness, roughness, z) {
  const mesh = new THREE.Mesh(new THREE.TorusGeometry(radius, tube, 12, 128),
    new THREE.MeshStandardMaterial({color, metalness: metalness * .48, roughness,
      emissive: color, emissiveIntensity: .08}));
  mesh.position.z = z;
  group.add(mesh);
  return mesh;
}

function createView(source) {
  const canvas = document.createElement('canvas');
  const renderer = new THREE.WebGLRenderer({canvas, alpha: true, antialias: true, premultipliedAlpha: true});
  renderer.setPixelRatio(1);
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping;
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, .1, 20);
  camera.position.z = 5;
  scene.add(new THREE.HemisphereLight(0xbfd9ef, 0x111a23, 1.3));
  const key = new THREE.DirectionalLight(0xe5f2ff, 2.4);
  key.position.set(-2, 3, 5); scene.add(key);
  const fill = new THREE.DirectionalLight(0x91b4cf, .65);
  fill.position.set(3, -2, 4); scene.add(fill);

  // Only the dimensional housing and glass are rendered here. The living
  // lens stays on the host canvas, retaining its full-rate journal effects.

  const bezel = new THREE.Group(); scene.add(bezel);
  const profile = [[.76,.015],[.77,.06],[.805,.095],[.83,.105],[.85,.055],
    [.90,.055],[.925,.09],[.96,.08],[.985,.02],[.98,-.04],[.80,-.06]];
  const housing = new THREE.Mesh(new THREE.LatheGeometry(profile.map(([r,z]) => new THREE.Vector2(r,z)),128),
    new THREE.MeshStandardMaterial({color:0x293b49,metalness:.68,roughness:.4,side:THREE.DoubleSide}));
  housing.rotation.x = Math.PI/2; bezel.add(housing);
  const band = (inner, outer, color, z, roughness = .36) => {
    const mesh = new THREE.Mesh(new THREE.RingGeometry(inner, outer, 128),
      new THREE.MeshStandardMaterial({color, metalness: .3, roughness,
        emissive: color, emissiveIntensity: .08, side: THREE.DoubleSide}));
    mesh.position.z = z; bezel.add(mesh);
    return mesh;
  };
  // Recessed glass in front of a stepped, machined metal instrument housing.
  band(.765, .985, 0x121c24, .018);
  band(.817, .956, 0x627888, .035);
  band(.837, .918, 0x293d4a, .050);
  band(.766, .810, 0x1b2b36, .055);
  band(.812, .828, 0x869ca9, .065, .28);
  band(.910, .956, 0x8da3b1, .055, .30);
  ring(bezel, .972, .013, 0x0c151d, .84, .3, .035);
  ring(bezel, .948, .014, 0x536673, .88, .27, .045);
  ring(bezel, .919, .008, 0x0d1921, .75, .28, .058);
  ring(bezel, .837, .016, 0x697c88, .92, .22, .075);
  ring(bezel, .804, .010, 0x09131b, .7, .25, .085);
  ring(bezel, .787, .007, 0x253944, .75, .25, .07);
  ring(bezel, .766, .004, 0x465967, .7, .30, .065);
  ring(bezel, .734, .003, 0x334751, .6, .30, .05);
  // Short curved highlights make the metal's bevels read as rounded rather
  // than flat painted circles, even at the overlay's smallest sizes.
  const highlight = new THREE.Mesh(new THREE.TorusGeometry(.936, .011, 8, 56, Math.PI * .44),
    new THREE.MeshBasicMaterial({color: 0xe2f5ff, transparent: true, opacity: .66}));
  highlight.rotation.z = Math.PI * .52; highlight.position.z = .08; bezel.add(highlight);
  const innerHighlight = new THREE.Mesh(new THREE.TorusGeometry(.822, .004, 8, 56, Math.PI * .38),
    new THREE.MeshBasicMaterial({color: 0xc5e8f4, transparent: true, opacity: .46}));
  innerHighlight.rotation.z = Math.PI * .55; innerHighlight.position.z = .09; bezel.add(innerHighlight);
  const tickMaterial = new THREE.MeshBasicMaterial({color: 0x00c8ff, transparent: true, opacity: .68});
  const tickGeometry = new THREE.PlaneGeometry(.0033, .023);
  const ticks = new THREE.InstancedMesh(tickGeometry, tickMaterial, 64);
  const dummy = new THREE.Object3D();
  for (let i = 0; i < 64; i++) {
    const angle = i / 64 * TAU;
    dummy.position.set(Math.sin(angle) * .882, Math.cos(angle) * .882, .09);
    dummy.rotation.z = -angle;
    dummy.scale.set(1, i % 16 === 0 ? 2 : i % 4 === 0 ? 1.35 : 1, 1);
    dummy.updateMatrix(); ticks.setMatrixAt(i, dummy.matrix);
  }
  bezel.add(ticks);

  const recessMaterial = new THREE.MeshStandardMaterial({color:0x080f16,metalness:.45,roughness:.7});
  const recesses = new THREE.InstancedMesh(new THREE.BoxGeometry(.006,.018,.006),recessMaterial,96);
  for(let i=0;i<96;i++) {
    const a=i/96*TAU;
    dummy.position.set(Math.sin(a)*.965,Math.cos(a)*.965,.066);
    dummy.rotation.set(0,0,-a);dummy.scale.set(1,1,1);dummy.updateMatrix();recesses.setMatrixAt(i,dummy.matrix);
  }
  bezel.add(recesses);
  const fasteners = new THREE.InstancedMesh(new THREE.CylinderGeometry(.009,.011,.005,12),
    new THREE.MeshStandardMaterial({color:0x9cabb6,metalness:.7,roughness:.36}),8);
  const slots = new THREE.InstancedMesh(new THREE.BoxGeometry(.011,.002,.002),recessMaterial,8);
  for(let i=0;i<8;i++) {
    const a=(i+.5)/8*TAU;
    dummy.position.set(Math.sin(a)*.933,Math.cos(a)*.933,.092);
    dummy.rotation.set(Math.PI/2,0,0);dummy.updateMatrix();fasteners.setMatrixAt(i,dummy.matrix);
    dummy.position.z=.096;dummy.rotation.set(0,0,-a+.4);dummy.updateMatrix();slots.setMatrixAt(i,dummy.matrix);
  }
  bezel.add(fasteners,slots);

  // A real curved transparent surface catches the light over the live iris.
  const glass = new THREE.Mesh(new THREE.SphereGeometry(.78, 64, 32),
    new THREE.MeshPhysicalMaterial({color: 0x9bc9e2, metalness: 0, roughness: .12,
      transparent: true, opacity: .035, depthWrite: false, clearcoat: 1, clearcoatRoughness: .06}));
  glass.scale.z = .19; glass.position.z = -.04; scene.add(glass);

  // Sparse stars inhabit three dimensions in front of the painted spiral;
  // the existing spiral and event animations remain visible behind them.
  const next = random(55413), positions = [];
  for (let i = 0; i < 210; i++) {
    const radius = .12 + Math.pow(next(), .85) * .51;
    const angle = (i % 2) * Math.PI + radius * 9 + (next() - .5) * .72;
    positions.push(Math.cos(angle) * radius, Math.sin(angle) * radius * .68, -.11 + next() * .08);
  }
  const starsGeometry = new THREE.BufferGeometry();
  starsGeometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  // Stars are composited below the existing expression and story shadows.
  const starsMaterial = new THREE.ShaderMaterial({
    uniforms: {tint: {value: new THREE.Color(0x34dbff)},
      alpha: {value: .4}, pointSize: {value: 1.2}},
    vertexShader: `uniform float pointSize;
      void main() {
        vec4 world = modelMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * viewMatrix * world;
        gl_PointSize = pointSize;
      }`,
    fragmentShader: `uniform vec3 tint;
      uniform float alpha;
      void main() {
        float falloff = 1.0 - smoothstep(.15, .5, length(gl_PointCoord - .5));
        gl_FragColor = vec4(tint, alpha * falloff);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const stars = new THREE.Points(starsGeometry, starsMaterial); scene.add(stars);
  const cache = document.createElement('canvas');
  const view = {renderer, scene, camera, tickMaterial, starsMaterial, stars, glass, cache,
    cacheContext: cache.getContext('2d'), lost: false, size: 0, lastRendered: -Infinity, spin: 0,
    colorKey: '', color: null, brightness: 0};
  canvas.addEventListener('webglcontextlost', (event) => { event.preventDefault(); view.lost = true; });
  canvas.addEventListener('webglcontextrestored', () => {
    view.lost = false; view.lastRendered = -Infinity; view.color = null;
    window.dispatchEvent(new Event('heartbeat-three-ready'));
  });
  return view;
}

class WatcherRenderer3D {
  draw(source, {x = 0, y = 0, size: drawSize = 0, tint = [0, 209, 255], level = 1, spin = 0, dim = 1,
    colorKey = '', force = false} = {}) {
    if (!source?.width || !source?.height || failed.has(source)) return false;
    let view = views.get(source);
    try {
      if (!view) { view = createView(source); views.set(source, view); }
      if (view.lost) return false;
      const size = Math.max(1, Math.min(768, source.width));
      if (view.size !== size) {
        view.renderer.setSize(size, size, false); view.size = size;
        view.cache.width = view.cache.height = size; view.lastRendered = -Infinity; view.color = null;
      }
      const now = performance.now();
      const rgb = (Array.isArray(tint) ? tint : [0, 209, 255])
        .map((v) => Math.max(0, Math.min(255, Number(v) || 0)));
      const brightness = level * dim;
      const changed = !view.color || rgb.some((value, index) => Math.abs(value - view.color[index]) >= 8)
        || Math.abs(brightness - view.brightness) >= .15;
      // WebGL-to-2D copies synchronize the GPU. Cache the dimensional layer
      // and keep the galaxy, gaze, lights and journal effects at full rate.
      if (force || colorKey !== view.colorKey || (changed && now - view.lastRendered > 1000)) {
        const color = new THREE.Color().setRGB(...rgb.map((v) => v / 255), THREE.SRGBColorSpace);
        view.tickMaterial.color.copy(color);
        view.starsMaterial.uniforms.tint.value.copy(color);
        view.starsMaterial.uniforms.alpha.value = Math.max(0, Math.min(.55, .40 * level * dim));
        view.starsMaterial.uniforms.pointSize.value = Math.max(.65, 1.3 * size / 384);
        view.stars.rotation.z = 0;
        view.renderer.render(view.scene, view.camera);
        view.cacheContext.clearRect(0, 0, size, size);
        view.cacheContext.drawImage(view.renderer.domElement, 0, 0, size, size);
        view.lastRendered = performance.now();
        view.spin = spin;
        view.colorKey = colorKey;
        view.color = rgb;
        view.brightness = brightness;
      }
      const ctx = source.getContext('2d');
      ctx.save(); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
      ctx.drawImage(view.cache, x - drawSize / 2, y - drawSize / 2, drawSize, drawSize); ctx.restore();
      return true;
    } catch (error) {
      failed.add(source);
      console.warn('Watcher 3D unavailable; using the canvas eye.', error);
      view?.renderer.dispose();
      return false;
    }
  }

  glass(source, {x, y, size, spin = 0, lookX = 0, lookY = 0, aperture = 0, level = 1} = {}) {
    const view = views.get(source);
    if (!view || view.lost || !view.size) return;
    const ctx = source.getContext('2d');
    ctx.save();
    ctx.beginPath(); ctx.arc(x, y, size * .39, 0, TAU); ctx.clip();
    ctx.translate(x + lookX * size * .12, y + lookY * size * .12);
    ctx.rotate((spin - view.spin) * .7);
    ctx.drawImage(view.cache, -size / 2, -size / 2, size, size);
    ctx.restore();
    // The front dome catches light against the deeper star field's parallax.
    const radius=size*.39;
    ctx.save();ctx.beginPath();ctx.arc(x,y,radius,0,TAU);ctx.clip();
    ctx.translate(x-lookX*size*.045,y-lookY*size*.045);
    const light=ctx.createRadialGradient(-radius*.38,-radius*.55,radius*.03,-radius*.38,-radius*.55,radius*.75);
    light.addColorStop(0,`rgba(210,235,249,${.045+.025*level})`);
    light.addColorStop(.3,'rgba(166,208,235,.018)');light.addColorStop(1,'rgba(166,208,235,0)');
    ctx.fillStyle=light;ctx.fillRect(-radius,-radius,radius*2,radius*2);
    ctx.globalCompositeOperation='lighter';
    const ghost=ctx.createRadialGradient(radius*.32,radius*.39,0,radius*.32,radius*.39,radius*(.08+.025*aperture));
    ghost.addColorStop(0,`rgba(169,217,241,${.025+.035*level})`);ghost.addColorStop(1,'rgba(169,217,241,0)');
    ctx.fillStyle=ghost;ctx.fillRect(-radius,-radius,radius*2,radius*2);ctx.restore();
  }

  // A soft moving reflection across the modeled metal catches the eye's
  // breathing and voice without forcing another WebGL readback each frame.
  sheen(source, {x, y, size, phase = 0, tint = [0, 209, 255], strength = 0} = {}) {
    if (!views.has(source) || strength <= .001) return;
    const ctx = source.getContext('2d'), radius = size * .46;
    const angle = -Math.PI * .7 + Math.sin(phase * .38) * .48;
    const gx = x + Math.cos(angle) * radius, gy = y + Math.sin(angle) * radius;
    const halo = Math.max(2, size * .04), rgb = tint.map(v => Math.round(Math.max(0, Math.min(255, v))));
    const glow = ctx.createRadialGradient(gx, gy, 0, gx, gy, halo);
    glow.addColorStop(0, `rgba(${rgb.join(',')},${Math.min(.32, strength)})`);
    glow.addColorStop(1, `rgba(${rgb.join(',')},0)`);
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = glow;
    ctx.fillRect(gx - halo, gy - halo, halo * 2, halo * 2); ctx.restore();
  }

  dispose(source) {
    const view = views.get(source);
    if (!view) return;
    view.scene.traverse((object) => {
      object.geometry?.dispose();
      if (Array.isArray(object.material)) object.material.forEach((material) => material.dispose());
      else object.material?.dispose();
    });
    view.renderer.dispose();
    views.delete(source);
  }
}

window.HeartbeatThree = new WatcherRenderer3D();
window.dispatchEvent(new Event('heartbeat-three-ready'));
