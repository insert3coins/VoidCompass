// The atlas camera: a map you pan and zoom, which also tilts into 3D.
//
// It is kept in Elite's own terms: the point it looks at (galactic x, z),
// how far away it is in light years, a heading (0: galactic north, towards
// Sagittarius A* and on to Beagle Point, is up) and a tilt (0: straight down).
// Left drag pans with the point under the cursor staying under it; the wheel
// zooms towards the cursor; right drag turns and tilts.
import * as THREE from './vendor/three.module.min.js';

export const DISTANCE = {min: 20, max: 400000};
export const TILT = {min: 0, max: 72};
const DEG = Math.PI / 180;

// Elite's axes: +x east, +y up, +z north. Seen from above with north up, east
// is to the right: a left-handed frame. The scene flips z to stay right-handed.
export const toScene = (x, y, z, depth = 1) => new THREE.Vector3(x, y * depth, -z);

export function createCamera(canvas, {onChange, onClick, onHover, onInteract} = {}) {
  const camera = new THREE.PerspectiveCamera(35, 1, 1, 1e6);
  const state = {x: 25, z: 25900, distance: 150000, heading: 0, tilt: 0};
  const ray = new THREE.Raycaster();
  const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  let width = 1, height = 1;
  let flight = null;
  let drag = null;

  function place() {
    const heading = state.heading * DEG, tilt = state.tilt * DEG;
    const north = new THREE.Vector3(Math.sin(heading), 0, -Math.cos(heading));
    const target = toScene(state.x, 0, state.z);
    const back = north.clone().multiplyScalar(-state.distance * Math.sin(tilt));
    camera.position.copy(target).add(back).add(new THREE.Vector3(0, state.distance * Math.cos(tilt), 0));
    camera.up.copy(north.multiplyScalar(Math.cos(tilt)).add(new THREE.Vector3(0, Math.sin(tilt), 0))).normalize();
    camera.near = Math.max(.5, state.distance * .01);
    camera.far = state.distance * 6 + 250000;
    camera.lookAt(target);
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld();
  }

  function changed(user = false) {
    place();
    onChange?.(user);
  }

  // Where a screen point meets the galactic plane, in Elite x/z.
  function pick(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    const ndc = new THREE.Vector2(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hit = new THREE.Vector3();
    if (!ray.ray.intersectPlane(plane, hit)) return null;
    return {x: hit.x, z: -hit.z};
  }

  // Light years one screen pixel covers at the point the camera looks at.
  const lyPerPixel = () => (2 * state.distance * Math.tan(camera.fov * DEG / 2)) / Math.max(1, height);

  function zoomAt(factor, clientX, clientY) {
    const before = clientX == null ? null : pick(clientX, clientY);
    state.distance = Math.min(DISTANCE.max, Math.max(DISTANCE.min, state.distance * factor));
    place();
    const after = clientX == null ? null : pick(clientX, clientY);
    if (before && after) {
      state.x += before.x - after.x;
      state.z += before.z - after.z;
    }
    changed(true);
  }

  function stopFlight() {
    flight = null;
  }

  // An eased flight: the distance moves in log steps, so a trip from the whole
  // galaxy down to one system doesn't rush the last part.
  function flyTo(goal, duration = 1100) {
    const from = {...state};
    const to = {
      x: goal.x ?? state.x, z: goal.z ?? state.z,
      distance: Math.min(DISTANCE.max, Math.max(DISTANCE.min, goal.distance ?? state.distance)),
      heading: goal.heading ?? state.heading, tilt: Math.min(TILT.max, Math.max(TILT.min, goal.tilt ?? state.tilt)),
    };
    let turn = ((to.heading - from.heading + 540) % 360) - 180;
    if (!duration) {
      Object.assign(state, to);
      changed(false);
      return;
    }
    flight = {start: performance.now(), duration, from, to, turn};
  }

  function step(now) {
    if (!flight) return false;
    const t = Math.min(1, (now - flight.start) / flight.duration);
    const ease = t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    const {from, to} = flight;
    state.x = from.x + (to.x - from.x) * ease;
    state.z = from.z + (to.z - from.z) * ease;
    state.distance = Math.exp(Math.log(from.distance) + (Math.log(to.distance) - Math.log(from.distance)) * ease);
    state.heading = (from.heading + flight.turn * ease + 360) % 360;
    state.tilt = from.tilt + (to.tilt - from.tilt) * ease;
    // A finished flight is where the commander asked to be: keep it.
    if (t >= 1) flight = null;
    changed(t >= 1);
    return true;
  }

  canvas.addEventListener('contextmenu', (event) => event.preventDefault());
  canvas.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 && event.button !== 2) return;
    canvas.setPointerCapture(event.pointerId);
    stopFlight();
    onInteract?.();
    const rotate = event.button === 2 || event.shiftKey;
    drag = {id: event.pointerId, button: event.button, rotate, sx: event.clientX, sy: event.clientY,
      lx: event.clientX, ly: event.clientY, moved: false, grab: rotate ? null : pick(event.clientX, event.clientY)};
  });
  canvas.addEventListener('pointermove', (event) => {
    if (!drag || drag.id !== event.pointerId) {
      onHover?.(event);
      return;
    }
    if (!drag.moved && Math.hypot(event.clientX - drag.sx, event.clientY - drag.sy) < 4) return;
    drag.moved = true;
    canvas.classList.add(drag.rotate ? 'turning' : 'panning');
    if (drag.rotate) {
      state.heading = (state.heading + (event.clientX - drag.lx) * .3 + 360) % 360;
      state.tilt = Math.min(TILT.max, Math.max(TILT.min, state.tilt + (event.clientY - drag.ly) * .25));
      changed(true);
    } else if (drag.grab) {
      const hit = pick(event.clientX, event.clientY);
      if (hit) {
        state.x += drag.grab.x - hit.x;
        state.z += drag.grab.z - hit.z;
        changed(true);
      }
    }
    drag.lx = event.clientX;
    drag.ly = event.clientY;
  });
  const release = (event) => {
    if (!drag || drag.id !== event.pointerId) return;
    const click = !drag.moved;
    const button = drag.button;
    drag = null;
    canvas.classList.remove('panning', 'turning');
    if (click && event.type === 'pointerup') onClick?.(event, button);
  };
  canvas.addEventListener('pointerup', release);
  canvas.addEventListener('pointercancel', release);
  canvas.addEventListener('wheel', (event) => {
    event.preventDefault();
    stopFlight();
    onInteract?.();
    const lines = event.deltaMode === 1 ? 40 : event.deltaMode === 2 ? 800 : 1;
    zoomAt(Math.exp(event.deltaY * lines * .0016), event.clientX, event.clientY);
  }, {passive: false});

  function key(event) {
    const pan = state.distance * .12;
    const heading = state.heading * DEG;
    const move = (east, north) => {
      state.x += east * Math.cos(heading) + north * Math.sin(heading);
      state.z += north * Math.cos(heading) - east * Math.sin(heading);
      changed(true);
    };
    const actions = {
      ArrowUp: () => move(0, pan), ArrowDown: () => move(0, -pan),
      ArrowLeft: () => move(-pan, 0), ArrowRight: () => move(pan, 0),
      '+': () => zoomAt(.8), '=': () => zoomAt(.8), '-': () => zoomAt(1.25), '_': () => zoomAt(1.25),
      q: () => { state.heading = (state.heading + 350) % 360; changed(true); },
      e: () => { state.heading = (state.heading + 10) % 360; changed(true); },
      PageUp: () => { state.tilt = Math.min(TILT.max, state.tilt + 6); changed(true); },
      PageDown: () => { state.tilt = Math.max(TILT.min, state.tilt - 6); changed(true); },
      n: () => flyTo({heading: 0}, 500),
    };
    const action = actions[event.key] || actions[event.key.toLowerCase?.()];
    if (!action) return false;
    stopFlight();
    onInteract?.();
    action();
    return true;
  }

  function resize(nextWidth, nextHeight) {
    width = Math.max(1, nextWidth);
    height = Math.max(1, nextHeight);
    camera.aspect = width / height;
    place();
  }

  place();
  return {
    camera, state, pick, flyTo, step, key, resize, lyPerPixel,
    zoom: (factor) => { stopFlight(); zoomAt(factor); },
    get flying() { return Boolean(flight); },
    get dragging() { return Boolean(drag?.moved); },
    set(values) { Object.assign(state, values); changed(false); },
  };
}
