import * as THREE from "../galactic_map/vendor/three.module.min.js";

// The live overlay, dashboard and preview share this Three.js instrument.
export function createAsterDisplay(canvas) {
  const TAU = Math.PI * 2;
  const renderer = new THREE.WebGLRenderer({canvas, alpha: true, antialias: true, premultipliedAlpha: true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(39, 1, .1, 20);
  camera.position.set(.08, .06, 4.2);
  camera.lookAt(0, 0, 0);
  scene.add(new THREE.AmbientLight(0xc7dfed, 1.6));
  const light = new THREE.DirectionalLight(0xe8faff, 3.5);
  light.position.set(-2, 3, 4); scene.add(light);
  const assembly = new THREE.Group(); scene.add(assembly);
  const outer = new THREE.Group(), inner = new THREE.Group(), core = new THREE.Group();
  assembly.add(outer, inner, core);
  const inkMaterials = [];
  function ink(opacity = 1) {
    const material = new THREE.MeshBasicMaterial({color: 0x65e4ef, transparent: true, opacity,
      depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending});
    inkMaterials.push(material);
    return material;
  }
  const bright = ink(.85), medium = ink(.38), faint = ink(.12);
  const housing = new THREE.MeshStandardMaterial({color: 0x243747, metalness: .76, roughness: .38});
  function ring(parent, radius, tube, material, z = 0, arc = TAU, start = 0) {
    const mesh = new THREE.Mesh(new THREE.TorusGeometry(radius, tube, 8, Math.max(24, Math.round(128 * arc / TAU)), arc), material);
    mesh.position.z = z; mesh.rotation.z = start; parent.add(mesh); return mesh;
  }
  ring(assembly, 1.2, .014, housing, -.08);
  ring(assembly, 1.16, .006, faint, -.065);
  ring(assembly, .82, .014, housing, .025);
  ring(assembly, .835, .003, medium, .042);
  ring(assembly, .68, .004, faint, .08);
  for (let i = 0; i < 4; i++) {
    const a = i * TAU / 4;
    ring(outer, 1.10, .004, bright, -.015, 1.03, a + .05);
    ring(outer, 1.06, .01, faint, -.005, .28, a + .06);
    ring(inner, .79, .004, bright, .05, .84, a + .10);
    ring(inner, .74, .006, medium, .075, .36, a + .31);
  }
  const dummy = new THREE.Object3D();
  const tickGeometry = new THREE.BoxGeometry(.005, .025, .006);
  const ticks = new THREE.InstancedMesh(tickGeometry, medium, 120);
  for (let i = 0; i < 120; i++) {
    const a = i * TAU / 120;
    dummy.position.set(Math.sin(a) * 1.185, Math.cos(a) * 1.185, -.045);
    dummy.rotation.set(0, 0, -a); dummy.scale.set(1, i % 5 ? 1 : 2, 1); dummy.updateMatrix();
    ticks.setMatrixAt(i, dummy.matrix);
  }
  assembly.add(ticks);
  const segmentGeometry = new THREE.RingGeometry(.925, .985, 12, 1, 0, .068);
  const segmentMaterials = [], segments = [];
  for (let i = 0; i < 48; i++) {
    const material = ink(i % 4 ? .2 : .55);
    const mesh = new THREE.Mesh(segmentGeometry, material);
    mesh.position.z = -.025; mesh.rotation.z = i / 48 * TAU;
    outer.add(mesh); segmentMaterials.push(material); segments.push(mesh);
  }
  ring(core, .59, .004, medium, .11);
  ring(core, .54, .002, faint, .15);
  for (let i = 0; i < 3; i++) ring(core, .51, .006, bright, .16, .88, i * TAU / 3 + .2);
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(.22, .22, .025, 48), housing);
  disc.rotation.x = Math.PI / 2; disc.position.z = .18; core.add(disc);
  const markMaterial = ink(.95);
  for (let i = 0; i < 6; i++) {
    const a = i / 6 * TAU;
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(.012, .14, .012), markMaterial);
    mesh.position.set(Math.sin(a) * .12, Math.cos(a) * .12, .23); mesh.rotation.z = -a; core.add(mesh);
  }
  ring(core, .055, .004, bright, .24);
  const waveform = new THREE.Group(); waveform.position.set(0, -.36, .25); assembly.add(waveform);
  const bars = [];
  const barGeometry = new THREE.BoxGeometry(.009, .04, .009);
  for (let i = 0; i < 25; i++) {
    const mesh = new THREE.Mesh(barGeometry, medium);
    mesh.position.x = (i - 12) * .019; waveform.add(mesh); bars.push(mesh);
  }
  const colour = new THREE.Color();
  let state = "idle", level = 0, accent = "#65e4ef", motion = true;
  let frame = 0, last = 0, disposed = false, tiltX = 0, tiltY = 0, visible = true, dirty = true, frameRate = 30;
  function resize() {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    renderer.setSize(rect.width, rect.height, false); dirty = true;
    camera.aspect = rect.width / rect.height; camera.updateProjectionMatrix();
  }
  const observer = new ResizeObserver(resize); observer.observe(canvas);
  function draw(now) {
    if (disposed) return;
    frame = requestAnimationFrame(draw);
    if (!visible || document.hidden || (!motion && !dirty) || now - last < 1000 / frameRate) return;
    dirty = false;
    last = now;
    const t = motion ? now / 1000 : 0;
    const active = state === "speaking" || state === "listening";
    const energy = state === "speaking" ? level : state === "listening" ? Math.min(1, level * 6) : .03;
    colour.set(state === "alert" ? "#ffbf7c" : accent);
    for (const material of inkMaterials) material.color.copy(colour);
    outer.rotation.z = t * (state === "working" ? .18 : .018);
    inner.rotation.z = -t * .035;
    core.rotation.z = motion ? Math.sin(t * .3) * .025 : 0;
    assembly.rotation.x += ((motion ? tiltY * .12 : 0) - assembly.rotation.x) * .08;
    assembly.rotation.y += ((motion ? tiltX * .12 : 0) - assembly.rotation.y) * .08;
    const breathe = motion ? Math.sin(t * 1.1) * .0025 : 0;
    core.scale.setScalar(1 + breathe + energy * .008);
    for (let i = 0; i < segments.length; i++) {
      segmentMaterials[i].opacity = i % 4 ? .15 + energy * .55 * (.5 + .5 * Math.sin(i * 1.7 + t * 4)) : .58;
    }
    for (let i = 0; i < bars.length; i++) {
      const wave = Math.sin((i + 1) / 26 * Math.PI);
      bars[i].scale.y = active ? .25 + wave * energy * 3 * (.3 + .7 * Math.abs(Math.sin(i * .9 + t * 7))) : .12;
    }
    renderer.render(scene, camera);
  }
  resize(); frame = requestAnimationFrame(draw);
  return {
    setState(value, valueLevel = 0) { const next = Math.max(0, Math.min(1, Number(valueLevel) || 0)); if (state !== value || Math.abs(level - next) > .005) dirty = true; state = value; level = next; },
    setColour(value) { if (/^#[0-9a-f]{6}$/i.test(value)) accent = value; dirty = true; },
    setMotion(value) { if (motion !== Boolean(value)) dirty = true; motion = Boolean(value); },
    setFrameRate(value) { frameRate = [15,24,30,60].includes(Number(value)) ? Number(value) : 30; },
    setVisible(value) { if (visible !== Boolean(value)) { visible = Boolean(value); dirty = true; if (!visible) cancelAnimationFrame(frame); else if (!disposed) frame = requestAnimationFrame(draw); } },
    setTilt(x, y) { tiltX = Math.max(-1, Math.min(1, x)); tiltY = Math.max(-1, Math.min(1, y)); },
    destroy() {
      disposed = true; cancelAnimationFrame(frame); observer.disconnect();
      const geometries = new Set(), materials = new Set();
      scene.traverse((object) => { if (object.geometry) geometries.add(object.geometry); if (object.material) materials.add(object.material); });
      geometries.forEach((geometry) => geometry.dispose()); materials.forEach((material) => material.dispose()); renderer.dispose();
    },
  };
}
