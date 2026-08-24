import * as THREE from './vendor/three.module.min.js';
import { OrbitControls } from './vendor/OrbitControls.js';

const params = new URLSearchParams(window.location.search);
const token = params.get('token') || '';
const captureMode = params.get('capture') === '1';
if (window.self !== window.top) document.documentElement.classList.add('embedded-atlas');
const api = (path) => `${path}${path.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`;

const LAYERS = [
  'Regions', 'Travel', 'Planned', 'Return', 'Sectors', 'Valuable', 'Biology',
  'Codex', 'Photos', 'Recon', 'Revisit', 'Bookmarks', 'Annotations',
];
const DEFAULT_LAYER_STATE = Object.fromEntries(LAYERS.map((name) => [name, name !== 'Return']));
const GALACTIC_CENTRE = new THREE.Vector3(0, 0, 25899);
const GALAXY_RADIUS = 51500;
const MAP_ORIENTATION = 'galactic-north-up-east-right-v2';
const DEFAULT_TILT_DIRECTION = new THREE.Vector3(0, .74, -.67).normalize();
const ROUTE_TILT_DIRECTION = new THREE.Vector3(0, .78, -.63).normalize();

const dom = Object.fromEntries([
  'viewport', 'route-overlay', 'travel-overlay-halo', 'travel-overlay-path',
  'nav-overlay-halo', 'nav-overlay-path', 'return-overlay-path',
  'region-labels', 'cluster-labels', 'current-system', 'current-region',
  'connection-state', 'commander-name', 'live-dot', 'search', 'search-button',
  'search-results', 'view-mode', 'scope-mode', 'current-button', 'route-button',
  'atlas-button', 'top-button', 'mark-button', 'reset-button', 'depth-scale',
  'depth-value', 'layer-grid', 'layers-toggle', 'inspector', 'close-inspector',
  'inspect-kind', 'inspect-title', 'inspect-system', 'inspect-detail',
  'inspect-coordinates', 'inspect-actions', 'stat-systems', 'stat-distance',
  'stat-markers', 'stat-annotations', 'route-state', 'camera-state', 'tooltip',
  'context-menu', 'annotation-dialog', 'annotation-form', 'annotation-location',
  'annotation-id', 'annotation-position', 'annotation-category', 'annotation-title',
  'annotation-note', 'annotation-system', 'annotation-delete', 'annotation-cancel', 'loading',
  'loading-status', 'coord-x', 'coord-y', 'coord-z', 'scale-line', 'scale-label',
  'axis-compass', 'axis-east-line', 'axis-north-line', 'axis-east-label',
  'axis-north-label',
].map((id) => [id, document.getElementById(id)]));

let renderer;
let scene;
let camera;
let controls;
let viewportResizeObserver;
let viewportResizeFrame = 0;
let viewportWidth = 1;
let viewportHeight = 1;
let regions;
let snapshot;
let activeProfile = null;
let currentThemeKey = '';
let selectedRecord = null;
let pointerDown = null;
let hoverFrame = null;
let eventSource = null;
let connected = false;
let viewState = {
  mode: 'Galactic Atlas', scope: 'All History', layers: {...DEFAULT_LAYER_STATE},
  orientation: MAP_ORIENTATION, depth_scale: 4, top_down: false,
  camera: {position: null, target: null},
};
let cameraTween = null;
let lastFrame = 0;
let lastClusterCell = -1;
let screenPickRecords = [];
let clusterLabelRecords = [];
let routeVectors = [];
let returnRouteVectors = [];
let plannedPaths = [];
let tracerPath = null;
let tracer;
let currentBeacon;
let waypointBeacon;
let lastFocusRequest = null;
let saveTimer = null;
let rebuildTimer = null;
let staticBuildGeneration = 0;
let captureFramesRemaining = captureMode ? 180 : 0;
let lastRouteOverlayFrame = -Infinity;

const groups = {};
const layerGroups = {};

function setLoading(message, failed = false) {
  dom['loading-status'].textContent = message;
  if (failed) {
    dom.loading.querySelector('h2').textContent = 'GALACTIC ATLAS UNAVAILABLE';
    dom.loading.querySelector('h2').style.color = 'var(--red)';
  }
}

function number(value, digits = 0) {
  return Number(value || 0).toLocaleString(undefined, {
    maximumFractionDigits: digits, minimumFractionDigits: digits,
  });
}

function measureViewport() {
  const rect = dom.viewport?.getBoundingClientRect();
  viewportWidth = Math.max(1, Math.round(rect?.width || dom.viewport?.clientWidth || window.innerWidth || 1));
  viewportHeight = Math.max(1, Math.round(rect?.height || dom.viewport?.clientHeight || window.innerHeight || 1));
  return {width: viewportWidth, height: viewportHeight};
}

function viewportMetrics() {
  return {
    width: viewportWidth,
    height: viewportHeight,
  };
}

function scheduleViewportResize() {
  if (viewportResizeFrame) cancelAnimationFrame(viewportResizeFrame);
  viewportResizeFrame = requestAnimationFrame(() => {
    viewportResizeFrame = 0;
    onResize();
  });
}

function validPosition(value) {
  return Array.isArray(value) && value.length >= 3 && value.slice(0, 3).every(Number.isFinite);
}

function positionOf(record) {
  const value = record?.position || record?.pos;
  return validPosition(value) ? value.slice(0, 3) : null;
}

function scenePosition(value) {
  // Elite's galactic +X runs to the right when +Z (Beagle/north) is up.
  // Three's above-plane camera has the opposite screen handedness, so mirror
  // only the display X axis while retaining unmodified journal coordinates.
  return new THREE.Vector3(-value[0], value[1] * viewState.depth_scale, value[2]);
}

function command(payload) {
  return fetch(api('/api/command'), {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-VoidCompass-Token': token},
    body: JSON.stringify(payload),
    cache: 'no-store',
  }).catch(() => null);
}

function setConnection(state, label) {
  connected = state === 'connected';
  dom['connection-state'].textContent = label;
  dom['live-dot'].classList.toggle('connected', state === 'connected');
  dom['live-dot'].classList.toggle('offline', state === 'offline');
}

function applyTheme(theme) {
  if (!theme) return false;
  const key = JSON.stringify(theme);
  if (key === currentThemeKey) return false;
  currentThemeKey = key;
  const mapping = {
    bg: '--bg', panel: '--panel', panel_alt: '--panel-alt', panel_raised: '--raised',
    header: '--header', input: '--input', inset: '--inset', border: '--border',
    border_soft: '--border-soft', selection: '--selection', accent: '--accent',
    orange: '--orange', text: '--text', muted: '--muted', dim: '--dim',
    green: '--green', yellow: '--yellow', red: '--red',
  };
  for (const [keyName, variable] of Object.entries(mapping)) {
    if (theme[keyName]) document.documentElement.style.setProperty(variable, theme[keyName]);
  }
  if (renderer) renderer.setClearColor(theme.bg || '#070b10', 1);
  return true;
}

function colourForLayer(name) {
  const theme = snapshot?.theme || {};
  return {
    Regions: theme.dim, Travel: theme.accent, Sectors: theme.dim,
    Planned: theme.yellow,
    Return: theme.green, Valuable: theme.orange, Biology: theme.green,
    Codex: theme.accent, Photos: theme.text, Recon: theme.red,
    Revisit: theme.orange, Bookmarks: theme.yellow, Annotations: theme.orange,
  }[name] || theme.accent || '#00d1ff';
}

function disposeMaterial(material) {
  if (!material) return;
  if (Array.isArray(material)) return material.forEach(disposeMaterial);
  for (const key of Object.keys(material)) {
    const value = material[key];
    if (value?.isTexture && value.userData?.ownedByAtlas) value.dispose();
  }
  material.dispose?.();
}

function clearGroup(group) {
  if (!group) return;
  while (group.children.length) {
    const child = group.children[0];
    group.remove(child);
    child.traverse?.((object) => {
      object.geometry?.dispose?.();
      disposeMaterial(object.material);
    });
  }
}

function initialiseThree() {
  const viewport = measureViewport();
  scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2('#070b10', 0.0000075);
  camera = new THREE.PerspectiveCamera(46, viewport.width / viewport.height, 2, 600000);
  camera.position.copy(GALACTIC_CENTRE).add(
    DEFAULT_TILT_DIRECTION.clone().multiplyScalar(132000),
  );
  renderer = new THREE.WebGLRenderer({
    antialias: true, alpha: false, powerPreference: 'high-performance',
    preserveDrawingBuffer: captureMode,
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  renderer.setSize(viewport.width, viewport.height, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor('#070b10', 1);
  renderer.domElement.tabIndex = 0;
  dom.viewport.appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.target.copy(GALACTIC_CENTRE);
  controls.enableDamping = true;
  controls.dampingFactor = 0.075;
  controls.rotateSpeed = 0.42;
  controls.panSpeed = 0.72;
  controls.zoomSpeed = 0.92;
  controls.minDistance = 45;
  controls.maxDistance = 260000;
  controls.maxPolarAngle = Math.PI * 0.495;
  controls.update();
  controls.addEventListener('change', () => {
    dom['camera-state'].textContent = cameraStatus();
    scheduleClusterRebuild();
  });
  controls.addEventListener('end', () => {
    rebuildClustersIfNeeded(true);
    scheduleSaveView();
  });

  for (const name of ['galaxy', 'regions', 'route', 'return', 'planned', 'markers', 'current', 'animation']) {
    groups[name] = new THREE.Group();
    groups[name].name = name;
    scene.add(groups[name]);
  }
  for (const name of LAYERS) {
    if (['Regions', 'Planned', 'Return'].includes(name)) continue;
    layerGroups[name] = new THREE.Group();
    layerGroups[name].name = `layer-${name}`;
    groups.markers.add(layerGroups[name]);
  }

  renderer.domElement.addEventListener('pointerdown', onPointerDown, true);
  renderer.domElement.addEventListener('pointerup', onPointerUp, true);
  renderer.domElement.addEventListener('pointercancel', onPointerCancel, true);
  renderer.domElement.addEventListener('click', onCanvasClick);
  renderer.domElement.addEventListener('pointermove', onPointerMove);
  renderer.domElement.addEventListener('pointerleave', hideTooltip);
  renderer.domElement.addEventListener('contextmenu', onContextMenu);
  window.addEventListener('resize', scheduleViewportResize);
  window.addEventListener('message', (event) => {
    if (event.source === window.parent && event.data?.type === 'voidcompass-atlas-viewport') {
      scheduleViewportResize();
    }
  });
  if (typeof ResizeObserver === 'function') {
    viewportResizeObserver = new ResizeObserver(() => scheduleViewportResize());
    viewportResizeObserver.observe(dom.viewport);
  }
}

function seededRandom(seed) {
  let value = seed >>> 0;
  return () => {
    value += 0x6D2B79F5;
    let t = value;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function regionColour(id) {
  const accent = new THREE.Color(snapshot?.theme?.accent || '#00d1ff');
  const hsl = {};
  accent.getHSL(hsl);
  return new THREE.Color().setHSL(
    (hsl.h + id * 0.381966) % 1, Math.max(.38, hsl.s), Math.max(.46, hsl.l * .82),
  );
}

function buildStaticGalaxy() {
  if (!regions || !scene) return;
  const generation = ++staticBuildGeneration;
  clearGroup(groups.galaxy);
  clearGroup(groups.regions);
  dom['region-labels'].replaceChildren();
  const theme = snapshot?.theme || {};
  scene.fog.color.set(theme.bg || '#070b10');

  const textureLoader = new THREE.TextureLoader();
  textureLoader.load('/assets/atlas.png', (texture) => {
    if (generation !== staticBuildGeneration) {
      texture.dispose();
      return;
    }
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
    texture.wrapS = THREE.RepeatWrapping;
    texture.repeat.x = -1;
    texture.offset.x = 1;
    texture.userData.ownedByAtlas = true;
    const geometry = new THREE.PlaneGeometry(GALAXY_RADIUS * 2, GALAXY_RADIUS * 2);
    const material = new THREE.MeshBasicMaterial({
      map: texture, transparent: true, opacity: .96, depthWrite: false,
      side: THREE.DoubleSide, blending: THREE.NormalBlending, toneMapped: false,
      fog: false,
    });
    const plane = new THREE.Mesh(geometry, material);
    plane.rotation.x = -Math.PI / 2;
    plane.position.set(GALACTIC_CENTRE.x, -180, GALACTIC_CENTRE.z);
    plane.renderOrder = -5;
    groups.galaxy.add(plane);
    // Capture mode renders on demand, so explicitly paint once the image has
    // decoded instead of waiting for a second animation frame.
    if (captureMode) renderer.render(scene, camera);
  });

  const random = seededRandom(0x5A17C0DE);
  const starPositions = [];
  const starColours = [];
  const accent = new THREE.Color(theme.accent || '#00d1ff');
  const warm = new THREE.Color(theme.orange || '#ff8a3d');
  const pale = new THREE.Color(theme.text || '#dcebf3');
  for (let index = 0; index < 15000; index += 1) {
    const radial = Math.pow(random(), .68);
    const arm = index % 4;
    const spread = (random() - .5) * (.28 + radial * .35);
    const angle = arm * Math.PI / 2 + .62 + radial * 5.12 + spread;
    const radius = radial * GALAXY_RADIUS * (.92 + random() * .12);
    starPositions.push(
      -Math.cos(angle) * radius,
      (random() - .5) * (120 + radial * 2300),
      GALACTIC_CENTRE.z + Math.sin(angle) * radius * .92,
    );
    const colour = (radial < .23 ? warm : accent).clone().lerp(pale, random() * .38);
    starColours.push(colour.r, colour.g, colour.b);
  }
  const starGeometry = new THREE.BufferGeometry();
  starGeometry.setAttribute('position', new THREE.Float32BufferAttribute(starPositions, 3));
  starGeometry.setAttribute('color', new THREE.Float32BufferAttribute(starColours, 3));
  const stars = new THREE.Points(starGeometry, new THREE.PointsMaterial({
    size: 1.35, sizeAttenuation: false, vertexColors: true,
    transparent: true, opacity: .62, depthWrite: false, fog: false,
    blending: THREE.AdditiveBlending,
  }));
  groups.galaxy.add(stars);

  for (const radius of [10000, 20000, 30000, 40000, 50000]) {
    const points = [];
    for (let index = 0; index <= 128; index += 1) {
      const angle = index / 128 * Math.PI * 2;
      points.push(new THREE.Vector3(
        Math.cos(angle) * radius, -30,
        GALACTIC_CENTRE.z + Math.sin(angle) * radius,
      ));
    }
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(points),
      new THREE.LineBasicMaterial({
        color: theme.border || '#243746', transparent: true, opacity: .24,
        depthWrite: false,
      }),
    );
    groups.galaxy.add(line);
  }
  const radialPositions = [];
  for (let index = 0; index < 12; index += 1) {
    const angle = index / 12 * Math.PI * 2;
    radialPositions.push(
      0, -30, GALACTIC_CENTRE.z,
      Math.cos(angle) * GALAXY_RADIUS, -30,
      GALACTIC_CENTRE.z + Math.sin(angle) * GALAXY_RADIUS,
    );
  }
  const radialGeometry = new THREE.BufferGeometry();
  radialGeometry.setAttribute('position', new THREE.Float32BufferAttribute(radialPositions, 3));
  groups.galaxy.add(new THREE.LineSegments(
    radialGeometry,
    new THREE.LineBasicMaterial({
      color: theme.border_soft || '#192a36', transparent: true, opacity: .18,
      depthWrite: false,
    }),
  ));

  const fillPositions = [];
  const fillColours = [];
  for (const [x1, z1, x2, z2, id] of regions.fills) {
    fillPositions.push(
      -x1, -85, z1, -x2, -85, z1, -x2, -85, z2,
      -x1, -85, z1, -x2, -85, z2, -x1, -85, z2,
    );
    const colour = regionColour(id);
    for (let vertex = 0; vertex < 6; vertex += 1) fillColours.push(colour.r, colour.g, colour.b);
  }
  const fillGeometry = new THREE.BufferGeometry();
  fillGeometry.setAttribute('position', new THREE.Float32BufferAttribute(fillPositions, 3));
  fillGeometry.setAttribute('color', new THREE.Float32BufferAttribute(fillColours, 3));
  const fillMesh = new THREE.Mesh(fillGeometry, new THREE.MeshBasicMaterial({
    vertexColors: true, transparent: true, opacity: .035,
    side: THREE.DoubleSide, depthWrite: false, fog: false,
  }));
  fillMesh.renderOrder = -1;
  groups.regions.add(fillMesh);

  const segmentPositions = [];
  for (const [x1, z1, x2, z2] of regions.segments) {
    segmentPositions.push(-x1, -15, z1, -x2, -15, z2);
  }
  const segmentGeometry = new THREE.BufferGeometry();
  segmentGeometry.setAttribute('position', new THREE.Float32BufferAttribute(segmentPositions, 3));
  groups.regions.add(new THREE.LineSegments(
    segmentGeometry,
    new THREE.LineBasicMaterial({
      color: theme.orange || '#ff8a3d', transparent: true, opacity: .20,
      depthWrite: false, fog: false,
    }),
  ));

  for (const row of regions.labels) {
    const label = document.createElement('span');
    label.className = 'region-label';
    label.textContent = `${String(row.id).padStart(2, '0')}  ${row.name.toUpperCase()}`;
    label.dataset.id = row.id;
    label._mapPosition = scenePosition(row.position);
    label._weight = row.weight;
    dom['region-labels'].appendChild(label);
  }
  applyLayerVisibility();
}

function lineObject(points, material) {
  if (points.length < 2) return null;
  return new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), material);
}

function starColour(starClass) {
  const code = String(starClass || '').trim().toUpperCase()[0];
  const value = {
    O: '#a9cfff', B: '#c5d9ff', A: '#e6ecff', F: '#fff3d1', G: '#ffe38c',
    K: '#ffb65c', M: '#ff795a', L: '#d86a3c', T: '#c05040', Y: '#9b4545',
    D: '#e8f2ff', N: '#9fdcff', H: '#c98dff',
  }[code] || snapshot?.theme?.muted || '#91a8b7';
  return new THREE.Color(value);
}

function filteredRoute() {
  const rows = snapshot?.route || [];
  if (viewState.scope === 'Current Session') {
    const start = Number(snapshot?.session?.started_epoch || 0) * 1000;
    return rows.filter((row) => !start || Date.parse(row.timestamp || '') >= start);
  }
  if (viewState.scope === 'Active Expedition') {
    const names = new Set((snapshot?.expedition?.systems || []).map((name) => String(name).toLowerCase()));
    return rows.filter((row) => names.has(String(row.system || '').toLowerCase()));
  }
  return rows;
}

function clusterCellSize() {
  const distance = camera.position.distanceTo(controls.target);
  if (distance > 120000) return 4500;
  if (distance > 75000) return 2400;
  if (distance > 42000) return 1100;
  if (distance > 22000) return 480;
  if (distance > 9000) return 160;
  return 0;
}

function clusterRecords(rows, positionKey, cellSize, layerAware = false) {
  if (!cellSize) return rows.map((row) => ({rows: [row], position: positionKey(row)}));
  const buckets = new Map();
  for (const row of rows) {
    const position = positionKey(row);
    if (!validPosition(position)) continue;
    const layer = layerAware ? String(row.layer || '') : '';
    const key = `${layer}:${Math.round(position[0] / cellSize)}:${Math.round(position[2] / cellSize)}`;
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(row);
  }
  return [...buckets.values()].map((items) => {
    const positions = items.map(positionKey).filter(validPosition);
    const position = [0, 1, 2].map((axis) => positions.reduce((sum, pos) => sum + pos[axis], 0) / positions.length);
    return {rows: items, position};
  });
}

function makePoints(records, positions, colours, size = 4) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions.flatMap((value) => value.toArray()), 3));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colours.flatMap((value) => [value.r, value.g, value.b]), 3));
  const points = new THREE.Points(geometry, new THREE.PointsMaterial({
    size, sizeAttenuation: false, vertexColors: true, transparent: true,
    opacity: .94, depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  points.userData.records = records;
  return points;
}

function pathPoints(positions, colour, size, opacity, blending = THREE.AdditiveBlending) {
  if (!positions.length) return null;
  const geometry = new THREE.BufferGeometry().setFromPoints(positions);
  return new THREE.Points(geometry, new THREE.PointsMaterial({
    color: colour, size, sizeAttenuation: false, transparent: true,
    opacity, depthWrite: false, blending,
  }));
}

function buildVisitedRoute() {
  clearGroup(groups.route);
  clearGroup(groups.return);
  routeVectors = [];
  returnRouteVectors = [];
  const rows = filteredRoute().filter((row) => validPosition(row.pos));
  routeVectors = rows.map((row) => scenePosition(row.pos));
  if (routeVectors.length > 1) {
    const colours = [];
    const start = new THREE.Color(snapshot.theme.dim);
    const end = new THREE.Color(snapshot.theme.accent);
    for (let index = 0; index < routeVectors.length; index += 1) {
      const colour = start.clone().lerp(end, Math.pow(index / Math.max(1, routeVectors.length - 1), .72));
      colours.push(colour.r, colour.g, colour.b);
    }
    const geometry = new THREE.BufferGeometry().setFromPoints(routeVectors);
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colours, 3));
    groups.route.add(new THREE.Line(
      geometry,
      new THREE.LineBasicMaterial({
        vertexColors: true, transparent: true, opacity: .72, depthWrite: false,
      }),
    ));
    // Screen-sized breadcrumb points keep long travel histories legible over
    // the bright Milky Way texture at every zoom level. The glow and core are
    // static GPU point clouds, so five thousand retained systems remain cheap.
    const historyGlow = pathPoints(
      routeVectors, snapshot.theme.accent, 6.4, .19,
    );
    const historyCore = pathPoints(
      routeVectors, snapshot.theme.text, 2.15, .76,
    );
    if (historyGlow) groups.route.add(historyGlow);
    if (historyCore) groups.route.add(historyCore);
    returnRouteVectors = routeVectors.slice(-60).reverse();
    const returnLine = lineObject(returnRouteVectors, new THREE.LineDashedMaterial({
      color: snapshot.theme.green, transparent: true, opacity: .65,
      dashSize: 350, gapSize: 260, depthWrite: false,
    }));
    if (returnLine) {
      returnLine.computeLineDistances();
      groups.return.add(returnLine);
    }
  }

  const cell = clusterCellSize();
  const clusters = clusterRecords(rows, (row) => row.pos, cell);
  const plannedSystems = new Set(
    (snapshot?.planned || []).map((row) => String(row.system || '').toLowerCase()),
  );
  const records = [];
  const positions = [];
  const colours = [];
  for (const cluster of clusters) {
    const position = scenePosition(cluster.position);
    positions.push(position);
    if (cluster.rows.length === 1) {
      const row = cluster.rows[0];
      const onNavigationRoute = plannedSystems.has(String(row.system || '').toLowerCase());
      records.push({
        kind: 'System', system: row.system, subject: 'Visited system',
        detail: row.fss_complete ? 'FSS survey complete' : 'Retained journal arrival',
        position: row.pos, star_class: row.star_class,
      });
      colours.push(onNavigationRoute
        ? new THREE.Color(snapshot.theme.yellow) : starColour(row.star_class));
    } else {
      const onNavigationRoute = cluster.rows.some((row) =>
        plannedSystems.has(String(row.system || '').toLowerCase()));
      records.push({
        kind: 'Cluster', subject: 'Visited system cluster',
        detail: `${cluster.rows.length.toLocaleString()} nearby retained systems`,
        position: cluster.position, rows: cluster.rows,
      });
      colours.push(new THREE.Color(
        onNavigationRoute ? snapshot.theme.yellow : snapshot.theme.muted,
      ));
      clusterLabelRecords.push({
        position, count: cluster.rows.length,
        colour: onNavigationRoute ? snapshot.theme.yellow : snapshot.theme.accent,
        layer: 'Travel', navigation: onNavigationRoute,
      });
    }
  }
  if (records.length) {
    const points = makePoints(records, positions, colours, 4.2);
    groups.route.add(points);
    for (let index = 0; index < records.length; index += 1) {
      screenPickRecords.push({
        position: positions[index], record: records[index], layer: 'Travel',
      });
    }
  }
}

function buildPlannedRoute() {
  clearGroup(groups.planned);
  plannedPaths = [];
  const rows = (snapshot?.planned || []).filter((row) => validPosition(row.pos));
  const sources = new Map();
  for (const row of rows) {
    if (!sources.has(row.source)) sources.set(row.source, []);
    sources.get(row.source).push(row);
  }
  for (const [source, entries] of sources.entries()) {
    const vectors = entries.map((row) => scenePosition(row.pos));
    plannedPaths.push({source, vectors});
    const line = lineObject(vectors, new THREE.LineDashedMaterial({
      color: source === 'game' ? snapshot.theme.yellow : snapshot.theme.orange,
      transparent: true, opacity: source === 'game' ? 1 : .82,
      dashSize: source === 'game' ? 680 : 260,
      gapSize: source === 'game' ? 170 : 190,
      depthWrite: false,
    }));
    if (line) {
      line.computeLineDistances();
      groups.planned.add(line);
    }
    if (entries.length) {
      const records = entries.map((row) => ({
        kind: 'Waypoint', system: row.system,
        subject: row.visited ? 'Completed waypoint' : 'Planned waypoint',
        detail: source === 'game' ? 'Elite navigation route' : 'Void Compass waypoint',
        position: row.pos,
      }));
      const colours = entries.map((row) => new THREE.Color(
        row.visited ? snapshot.theme.dim
          : source === 'game' ? snapshot.theme.yellow : snapshot.theme.orange,
      ));
      const haloColours = entries.map(() => new THREE.Color(
        source === 'game' ? snapshot.theme.yellow : snapshot.theme.orange,
      ));
      const halo = makePoints(records, vectors, haloColours, 12);
      halo.material.opacity = .18;
      const points = makePoints(records, vectors, colours, 6.2);
      groups.planned.add(halo);
      groups.planned.add(points);
      records.forEach((record, index) => screenPickRecords.push({
        position: vectors[index], record, layer: 'Planned',
      }));
    }
  }
  const nextName = String(snapshot?.route_context?.next_system || '').toLowerCase();
  const next = rows.find((row) => nextName && String(row.system || '').toLowerCase() === nextName);
  waypointBeacon = next ? scenePosition(next.pos) : null;
  const tracerRows = (sources.get('game') || rows).map((row) => scenePosition(row.pos));
  tracerPath = preparePath(tracerRows);
  tracer = null;
  if (tracerPath && !snapshot.reduced_motion) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      'position', new THREE.Float32BufferAttribute(new Float32Array(15), 3),
    );
    tracer = new THREE.Points(geometry, new THREE.PointsMaterial({
      color: snapshot.theme.yellow, size: 7.4, sizeAttenuation: false,
      transparent: true, opacity: .92, depthWrite: false,
      blending: THREE.AdditiveBlending,
    }));
    groups.animation.add(tracer);
  }
}

function buildMarkers() {
  for (const group of Object.values(layerGroups)) clearGroup(group);
  const markers = (snapshot?.markers || []).filter((row) => validPosition(row.position));
  const cell = clusterCellSize();
  for (const layer of LAYERS) {
    if (!layerGroups[layer]) continue;
    const source = markers.filter((row) => row.layer === layer);
    const clusters = layer === 'Annotations'
      ? source.map((row) => ({rows: [row], position: row.position}))
      : clusterRecords(source, (row) => row.position, cell, true);
    const records = [];
    const positions = [];
    const colours = [];
    for (const cluster of clusters) {
      const position = scenePosition(cluster.position);
      positions.push(position);
      if (cluster.rows.length === 1) {
        const record = {...cluster.rows[0]};
        records.push(record);
        colours.push(new THREE.Color(
          record.status === 'surveyed' ? snapshot.theme.green
            : record.status === 'incomplete' ? snapshot.theme.orange
              : colourForLayer(layer),
        ));
      } else {
        const layerCounts = new Map();
        for (const row of cluster.rows) layerCounts.set(row.layer, (layerCounts.get(row.layer) || 0) + 1);
        records.push({
          kind: 'Cluster', subject: `${layer} intelligence cluster`,
          detail: [...layerCounts].map(([name, count]) => `${name} ${count}`).join(' · '),
          position: cluster.position, rows: cluster.rows,
        });
        colours.push(new THREE.Color(colourForLayer(layer)));
        clusterLabelRecords.push({
          position, count: cluster.rows.length, colour: colourForLayer(layer), layer,
        });
      }
    }
    if (records.length) {
      const points = makePoints(records, positions, colours, layer === 'Annotations' ? 7.5 : 6.2);
      layerGroups[layer].add(points);
      records.forEach((record, index) => screenPickRecords.push({
        position: positions[index], record, layer,
      }));
    }
  }
}

function buildCurrentLocator() {
  clearGroup(groups.current);
  currentBeacon = null;
  const current = snapshot?.current || {};
  if (!validPosition(current.position)) return;
  currentBeacon = new THREE.Group();
  currentBeacon.position.copy(scenePosition(current.position));
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(190, 225, 48),
    new THREE.MeshBasicMaterial({
      color: snapshot.theme.orange, side: THREE.DoubleSide,
      transparent: true, opacity: .8, depthWrite: false,
    }),
  );
  ring.rotation.x = -Math.PI / 2;
  ring.name = 'pulse-ring';
  currentBeacon.add(ring);
  const shape = new THREE.Shape();
  shape.moveTo(0, -250);
  shape.lineTo(125, 180);
  shape.lineTo(0, 110);
  shape.lineTo(-125, 180);
  shape.closePath();
  const glyph = new THREE.Mesh(
    new THREE.ShapeGeometry(shape),
    new THREE.MeshBasicMaterial({
      color: snapshot.theme.orange, side: THREE.DoubleSide, depthWrite: false,
    }),
  );
  glyph.rotation.x = -Math.PI / 2;
  glyph.position.y = 30;
  currentBeacon.add(glyph);
  groups.current.add(currentBeacon);
  const record = {
    kind: 'System', system: current.system, subject: 'Current commander position',
    detail: current.ship ? `Aboard ${current.ship}` : 'Live journal position',
    position: current.position,
  };
  screenPickRecords.push({position: currentBeacon.position, record});
}

function rebuildDynamicScene() {
  if (!snapshot || !scene) return;
  screenPickRecords = [];
  clusterLabelRecords = [];
  clearGroup(groups.animation);
  buildVisitedRoute();
  buildPlannedRoute();
  buildMarkers();
  buildCurrentLocator();
  buildClusterLabels();
  applyLayerVisibility();
  lastRouteOverlayFrame = -Infinity;
  lastClusterCell = clusterCellSize();
}

function buildClusterLabels() {
  dom['cluster-labels'].replaceChildren();
  for (const row of clusterLabelRecords.slice(0, 140)) {
    const element = document.createElement('span');
    element.className = 'cluster-label';
    element.textContent = row.count > 999 ? '999+' : String(row.count);
    element.style.borderColor = row.colour;
    element.classList.toggle('navigation-route', Boolean(row.navigation));
    element.dataset.layer = row.layer || '';
    element._mapPosition = row.position;
    dom['cluster-labels'].appendChild(element);
  }
}

function applyLayerVisibility() {
  if (!scene) return;
  groups.regions.visible = viewState.layers.Regions !== false;
  groups.route.visible = viewState.layers.Travel !== false;
  groups.planned.visible = viewState.layers.Planned !== false;
  groups.animation.visible = viewState.layers.Planned !== false;
  groups.return.visible = viewState.layers.Return === true;
  for (const [name, group] of Object.entries(layerGroups)) {
    group.visible = viewState.layers[name] !== false;
  }
  dom['region-labels'].style.display = groups.regions.visible ? 'block' : 'none';
  updateRouteOverlay(performance.now(), true);
}

function preparePath(points) {
  if (!points || points.length < 2) return null;
  const lengths = [0];
  for (let index = 1; index < points.length; index += 1) {
    lengths.push(lengths[index - 1] + points[index].distanceTo(points[index - 1]));
  }
  return lengths.at(-1) > 1 ? {points, lengths, total: lengths.at(-1)} : null;
}

function pointOnPath(path, fraction) {
  const target = ((fraction % 1) + 1) % 1 * path.total;
  let index = 1;
  while (index < path.lengths.length && path.lengths[index] < target) index += 1;
  if (index >= path.points.length) return path.points.at(-1).clone();
  const span = Math.max(.001, path.lengths[index] - path.lengths[index - 1]);
  const amount = (target - path.lengths[index - 1]) / span;
  return path.points[index - 1].clone().lerp(path.points[index], amount);
}

function updateLabels() {
  if (!camera) return;
  const {width, height} = viewportMetrics();
  const currentRegionId = snapshot?.current?.region?.id;
  const occupied = [];
  const labels = [...dom['region-labels'].children].sort((a, b) => {
    const ac = Number(a.dataset.id) === Number(currentRegionId);
    const bc = Number(b.dataset.id) === Number(currentRegionId);
    return Number(bc) - Number(ac) || (b._weight || 0) - (a._weight || 0);
  });
  for (const label of labels) {
    const projected = label._mapPosition.clone().project(camera);
    const visible = projected.z > -1 && projected.z < 1;
    const x = (projected.x * .5 + .5) * width;
    const y = (-projected.y * .5 + .5) * height;
    const bounds = [x - 65, y - 9, x + 65, y + 9];
    const current = Number(label.dataset.id) === Number(currentRegionId);
    const overlap = occupied.some((other) => bounds[0] < other[2] && bounds[2] > other[0] && bounds[1] < other[3] && bounds[3] > other[1]);
    const show = visible && x > 310 && x < width - 25 && y > 92 && y < height - 65 && (!overlap || current);
    label.hidden = !show;
    label.classList.toggle('current', current);
    if (show) {
      label.style.left = `${x}px`;
      label.style.top = `${y}px`;
      occupied.push(bounds);
    }
  }
  for (const label of dom['cluster-labels'].children) {
    const projected = label._mapPosition.clone().project(camera);
    const x = (projected.x * .5 + .5) * width;
    const y = (-projected.y * .5 + .5) * height;
    const layer = label.dataset.layer;
    const show = (!layer || viewState.layers[layer] !== false)
      && projected.z > -1 && projected.z < 1
      && x > 305 && x < width - 18 && y > 88 && y < height - 58;
    label.hidden = !show;
    if (show) {
      label.style.left = `${x}px`;
      label.style.top = `${y}px`;
    }
  }
}

function svgPathForVectors(vectors, maximumPoints = 750) {
  if (!camera || vectors.length < 2) return '';
  const {width, height} = viewportMetrics();
  const step = Math.max(1, Math.ceil(vectors.length / maximumPoints));
  const selected = [];
  for (let index = 0; index < vectors.length; index += step) selected.push(vectors[index]);
  if (selected.at(-1) !== vectors.at(-1)) selected.push(vectors.at(-1));
  let output = '';
  let drawing = false;
  for (const vector of selected) {
    const projected = vector.clone().project(camera);
    if (projected.z <= -1 || projected.z >= 1) {
      drawing = false;
      continue;
    }
    const x = (projected.x * .5 + .5) * width;
    const y = (-projected.y * .5 + .5) * height;
    output += `${drawing ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`;
    drawing = true;
  }
  return output;
}

function updateRouteOverlay(now, force = false) {
  if (!camera || (!force && now - lastRouteOverlayFrame < 66)) return;
  lastRouteOverlayFrame = now;
  const {width, height} = viewportMetrics();
  dom['route-overlay'].setAttribute('viewBox', `0 0 ${width} ${height}`);
  const travelPath = viewState.layers.Travel === false
    ? '' : svgPathForVectors(routeVectors);
  dom['travel-overlay-halo'].setAttribute('d', travelPath);
  dom['travel-overlay-path'].setAttribute('d', travelPath);
  dom['return-overlay-path'].setAttribute(
    'd', viewState.layers.Return === true ? svgPathForVectors(returnRouteVectors, 180) : '',
  );
  const navPath = viewState.layers.Planned === false
    ? '' : plannedPaths.map((row) => svgPathForVectors(row.vectors, 420)).join('');
  dom['nav-overlay-halo'].setAttribute('d', navPath);
  dom['nav-overlay-path'].setAttribute('d', navPath);
  updateAtlasInstruments();
}

function niceScaleDistance(value) {
  if (!Number.isFinite(value) || value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalised = value / magnitude;
  const step = normalised >= 5 ? 5 : normalised >= 2 ? 2 : 1;
  return step * magnitude;
}

function updateAtlasInstruments() {
  if (!camera || !controls) return;
  const {height} = viewportMetrics();
  const distance = camera.position.distanceTo(controls.target);
  const verticalField = 2 * distance * Math.tan(THREE.MathUtils.degToRad(camera.fov * .5));
  const worldPerPixel = verticalField / height;
  const scaleDistance = niceScaleDistance(worldPerPixel * 105);
  const scalePixels = Math.max(42, Math.min(118, scaleDistance / worldPerPixel));
  dom['scale-line'].style.width = `${scalePixels.toFixed(1)}px`;
  dom['scale-label'].textContent = `${number(scaleDistance, scaleDistance < 10 ? 1 : 0)} LY`;

  const origin = controls.target.clone();
  const originProjected = origin.clone().project(camera);
  const updateAxis = (vector, line, label) => {
    const projected = origin.clone().add(vector).project(camera);
    let dx = projected.x - originProjected.x;
    let dy = -(projected.y - originProjected.y);
    const length = Math.hypot(dx, dy) || 1;
    dx /= length;
    dy /= length;
    line.setAttribute('x2', (46 + dx * 28).toFixed(1));
    line.setAttribute('y2', (46 + dy * 28).toFixed(1));
    label.setAttribute('x', (46 + dx * 38).toFixed(1));
    label.setAttribute('y', (46 + dy * 38).toFixed(1));
  };
  // Display-space +X is mirrored from raw Elite coordinates by design.
  updateAxis(new THREE.Vector3(-4000, 0, 0), dom['axis-east-line'], dom['axis-east-label']);
  updateAxis(new THREE.Vector3(0, 0, 4000), dom['axis-north-line'], dom['axis-north-label']);
}

function animate(now) {
  if (!captureMode || captureFramesRemaining-- > 0) requestAnimationFrame(animate);
  const delta = Math.min(.08, Math.max(0, (now - lastFrame) / 1000));
  lastFrame = now;
  if (!renderer || !scene) return;
  controls.update();
  if (cameraTween) updateCameraTween(now);
  updateRouteOverlay(now);
  const reduced = snapshot?.reduced_motion;
  if (!reduced) {
    const phase = now / 1000;
    if (currentBeacon) {
      const pulse = 1 + (Math.sin(phase * 2.2) + 1) * .12;
      currentBeacon.getObjectByName('pulse-ring')?.scale.setScalar(pulse);
    }
    if (tracer && tracerPath) {
      const positions = tracer.geometry.getAttribute('position');
      for (let index = 0; index < positions.count; index += 1) {
        const point = pointOnPath(tracerPath, phase * .035 - index * .022);
        positions.setXYZ(index, point.x, point.y, point.z);
      }
      positions.needsUpdate = true;
      tracer.material.size = 7.2 + (Math.sin(phase * 3.1) + 1) * .75;
    }
    if (waypointBeacon) {
      if (!groups.animation.getObjectByName('waypoint-beacon')) {
        const beaconGroup = new THREE.Group();
        beaconGroup.position.copy(waypointBeacon);
        beaconGroup.name = 'waypoint-beacon';
        const ring = new THREE.Mesh(
          new THREE.RingGeometry(230, 270, 40),
          new THREE.MeshBasicMaterial({
            color: snapshot.theme.yellow, side: THREE.DoubleSide,
            transparent: true, opacity: .72, depthWrite: false,
          }),
        );
        ring.rotation.x = -Math.PI / 2;
        beaconGroup.add(ring);
        const core = pathPoints(
          [new THREE.Vector3()], snapshot.theme.yellow, 13.5, .92,
        );
        core.name = 'beacon-core';
        beaconGroup.add(core);
        groups.animation.add(beaconGroup);
      }
      const beacon = groups.animation.getObjectByName('waypoint-beacon');
      beacon?.scale.setScalar(1 + (Math.sin(phase * 1.45) + 1) * .18);
    }
  }
  updateLabels();
  renderer.render(scene, camera);
}

function updateCameraTween(now) {
  const amount = Math.min(1, (now - cameraTween.started) / cameraTween.duration);
  const eased = amount * amount * (3 - 2 * amount);
  camera.position.lerpVectors(cameraTween.fromPosition, cameraTween.toPosition, eased);
  controls.target.lerpVectors(cameraTween.fromTarget, cameraTween.toTarget, eased);
  if (amount >= 1) {
    cameraTween = null;
    controls.update();
    rebuildClustersIfNeeded(true);
    scheduleSaveView();
  }
}

function tweenCamera(target, distance, direction = null) {
  target = target.clone();
  const currentDirection = direction || camera.position.clone().sub(controls.target).normalize();
  if (currentDirection.lengthSq() < .1) currentDirection.copy(DEFAULT_TILT_DIRECTION);
  if (!viewState.top_down) camera.up.set(0, 1, 0);
  const destination = target.clone().add(currentDirection.clone().multiplyScalar(Math.max(80, distance)));
  cameraTween = {
    started: performance.now(), duration: snapshot?.reduced_motion ? 1 : 720,
    fromPosition: camera.position.clone(), toPosition: destination,
    fromTarget: controls.target.clone(), toTarget: target,
  };
}

function framePositions(values, fallbackRadius = 1200) {
  const positions = values.filter(validPosition).map(scenePosition);
  if (!positions.length) return;
  const box = new THREE.Box3().setFromPoints(positions);
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  const radius = Math.max(fallbackRadius, sphere.radius);
  const distance = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov * .5)) * 1.18;
  tweenCamera(sphere.center, Math.min(235000, distance), ROUTE_TILT_DIRECTION);
}

function setPreset(mode, animateCamera = true) {
  viewState.mode = mode;
  dom['view-mode'].value = mode;
  if (mode === 'Galactic Atlas') {
    viewState.top_down = false;
    camera.up.set(0, 1, 0);
    const target = GALACTIC_CENTRE.clone();
    const distance = 132000;
    if (animateCamera) tweenCamera(target, distance, DEFAULT_TILT_DIRECTION);
    else {
      controls.target.copy(target);
      camera.position.copy(target).add(DEFAULT_TILT_DIRECTION.clone().multiplyScalar(distance));
      controls.update();
    }
  } else if (mode === 'Route Focus') {
    framePositions(filteredRoute().map((row) => row.pos), 2500);
  } else {
    const current = snapshot?.current?.position;
    const recent = filteredRoute().slice(-40).map((row) => row.pos);
    if (validPosition(current)) recent.push(current);
    framePositions(recent, 1500);
  }
  dom['top-button'].textContent = viewState.top_down ? 'TILTED VIEW' : 'TOP VIEW';
  syncViewControls();
  dom['camera-state'].textContent = cameraStatus();
  scheduleSaveView();
}

function toggleTopView() {
  const distance = camera.position.distanceTo(controls.target);
  viewState.top_down = !viewState.top_down;
  if (viewState.top_down) {
    camera.up.set(0, 0, 1);
    tweenCamera(controls.target, distance, new THREE.Vector3(0, 1, .0001).normalize());
  } else {
    camera.up.set(0, 1, 0);
    tweenCamera(controls.target, distance, DEFAULT_TILT_DIRECTION);
  }
  dom['top-button'].textContent = viewState.top_down ? 'TILTED VIEW' : 'TOP VIEW';
  syncViewControls();
  scheduleSaveView();
}

function syncViewControls() {
  dom['atlas-button'].classList.toggle('view-active', viewState.mode === 'Galactic Atlas');
  dom['route-button'].classList.toggle('view-active', viewState.mode === 'Route Focus');
  dom['current-button'].classList.toggle('view-active', viewState.mode === 'Current Vicinity');
  dom['top-button'].classList.toggle('view-active', viewState.top_down);
}

function cameraStatus() {
  const distance = camera ? camera.position.distanceTo(controls.target) : 0;
  return `${viewState.mode.toUpperCase()} · ${viewState.top_down ? 'TOP' : '3D'} · ${number(distance, 0)} LY FIELD`;
}

function scheduleClusterRebuild() {
  clearTimeout(rebuildTimer);
  rebuildTimer = setTimeout(() => rebuildClustersIfNeeded(false), 140);
}

function rebuildClustersIfNeeded(force = false) {
  const cell = clusterCellSize();
  if (force || cell !== lastClusterCell) rebuildDynamicScene();
}

function scheduleSaveView() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveView, 420);
}

function saveView() {
  if (!camera || !controls) return;
  viewState.camera = {
    position: camera.position.toArray(), target: controls.target.toArray(),
  };
  command({action: 'save_view', state: viewState});
}

function restoreView(state) {
  viewState = {
    orientation: MAP_ORIENTATION,
    mode: state?.mode || 'Galactic Atlas',
    scope: state?.scope || 'All History',
    layers: {...DEFAULT_LAYER_STATE, ...(state?.layers || {})},
    depth_scale: Math.max(1, Math.min(20, Number(state?.depth_scale || 4))),
    top_down: Boolean(state?.top_down),
    camera: state?.camera || {position: null, target: null},
  };
  dom['view-mode'].value = viewState.mode;
  dom['scope-mode'].value = viewState.scope;
  dom['depth-scale'].value = viewState.depth_scale;
  dom['depth-value'].textContent = `${viewState.depth_scale}×`;
  syncLayerControls();
  if (viewState.top_down) camera.up.set(0, 0, 1);
  else camera.up.set(0, 1, 0);
  if (validPosition(viewState.camera?.position) && validPosition(viewState.camera?.target)) {
    camera.position.fromArray(viewState.camera.position);
    controls.target.fromArray(viewState.camera.target);
    controls.update();
  } else {
    setPreset(viewState.mode, false);
  }
  dom['top-button'].textContent = viewState.top_down ? 'TILTED VIEW' : 'TOP VIEW';
  syncViewControls();
}

function createLayerControls() {
  dom['layer-grid'].replaceChildren();
  for (const name of LAYERS) {
    const label = document.createElement('label');
    label.className = 'layer-toggle';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.dataset.layer = name;
    input.addEventListener('change', () => {
      viewState.layers[name] = input.checked;
      applyLayerVisibility();
      scheduleSaveView();
    });
    const swatch = document.createElement('span');
    swatch.className = 'layer-swatch';
    swatch.style.color = colourForLayer(name);
    swatch.style.background = colourForLayer(name);
    const text = document.createElement('span');
    text.className = 'layer-name';
    text.textContent = ({
      Travel: 'TRAVEL HISTORY', Planned: 'NAV ROUTE', Return: 'RETURN PATH',
    }[name] || name).toUpperCase();
    label.append(input, swatch, text);
    dom['layer-grid'].appendChild(label);
  }
  syncLayerControls();
}

function syncLayerControls() {
  for (const input of dom['layer-grid'].querySelectorAll('input[data-layer]')) {
    input.checked = viewState.layers[input.dataset.layer] !== false;
    const swatch = input.parentElement.querySelector('.layer-swatch');
    swatch.style.color = colourForLayer(input.dataset.layer);
    swatch.style.background = colourForLayer(input.dataset.layer);
  }
}

function updateInterface() {
  const current = snapshot?.current || {};
  const summary = snapshot?.summary || {};
  dom['current-system'].textContent = current.system || 'POSITION UNKNOWN';
  dom['current-region'].textContent = current.region
    ? `REGION ${String(current.region.id).padStart(2, '0')} // ${current.region.name.toUpperCase()}`
    : 'OUTSIDE RETAINED REGION DATA';
  dom['commander-name'].textContent = snapshot?.profile?.commander || 'LOCAL COMMANDER';
  const coordinates = validPosition(current.position) ? current.position : null;
  dom['coord-x'].textContent = coordinates ? number(coordinates[0], 1) : '—';
  dom['coord-y'].textContent = coordinates ? number(coordinates[1], 1) : '—';
  dom['coord-z'].textContent = coordinates ? number(coordinates[2], 1) : '—';
  dom['stat-systems'].textContent = number(summary.systems);
  dom['stat-distance'].textContent = `${number(summary.distance_ly, 1)} LY`;
  dom['stat-markers'].textContent = number(summary.markers);
  dom['stat-annotations'].textContent = number(summary.annotations);
  const route = snapshot?.route_context || {};
  dom['route-state'].textContent = route.off_route
    ? `OFF ROUTE${route.nearest_distance_ly != null ? ` · ${number(route.nearest_distance_ly, 1)} LY` : ''}`
    : route.next_system ? `NEXT // ${route.next_system} · ${number(route.remaining)} REMAINING`
      : 'NO ACTIVE ROUTE';
  dom['camera-state'].textContent = cameraStatus();
}

function applySnapshot(data, first = false) {
  if (!data || data.schema !== 1) return;
  const profileChanged = activeProfile !== data.profile?.id;
  const themeChanged = applyTheme(data.theme);
  snapshot = data;
  document.documentElement.classList.toggle(
    'reduced-motion', Boolean(data.reduced_motion),
  );
  if (profileChanged || first) {
    activeProfile = data.profile?.id;
    restoreView(data.view_state || {});
  }
  if (themeChanged || first || profileChanged) {
    createLayerControls();
    buildStaticGalaxy();
  }
  rebuildDynamicScene();
  updateInterface();
  if (data.focus_request && data.focus_request.id !== lastFocusRequest) {
    lastFocusRequest = data.focus_request.id;
    focusPosition(data.focus_request.position, 2200);
  }
}

function focusPosition(position, distance = 1800) {
  if (!validPosition(position)) return;
  viewState.mode = 'Current Vicinity';
  dom['view-mode'].value = viewState.mode;
  syncViewControls();
  tweenCamera(scenePosition(position), distance);
}

function focusRecord(record) {
  if (record?.kind === 'Cluster' && Array.isArray(record.rows)) {
    framePositions(record.rows.map((row) => positionOf(row)), 500);
  } else {
    const position = positionOf(record);
    if (position) focusPosition(position, record?.kind === 'Region' ? 16000 : 1900);
  }
  inspect(record);
}

function screenPoint(vector) {
  const {width, height} = viewportMetrics();
  const projected = vector.clone().project(camera);
  return {
    x: (projected.x * .5 + .5) * width,
    y: (-projected.y * .5 + .5) * height,
    visible: projected.z > -1 && projected.z < 1
      && projected.x > -1 && projected.x < 1
      && projected.y > -1 && projected.y < 1,
  };
}

function pickAt(clientX, clientY, maxDistance = 14) {
  let nearest = null;
  let best = maxDistance * maxDistance;
  for (const item of screenPickRecords) {
    if (item.layer && viewState.layers[item.layer] === false) continue;
    const point = screenPoint(item.position);
    if (!point.visible) continue;
    const dx = point.x - clientX;
    const dy = point.y - clientY;
    const distance = dx * dx + dy * dy;
    if (distance < best) {
      best = distance;
      nearest = item.record;
    }
  }
  return nearest;
}

function planePositionAt(clientX, clientY) {
  const {width, height} = viewportMetrics();
  const ndc = new THREE.Vector2(clientX / width * 2 - 1, -(clientY / height) * 2 + 1);
  const ray = new THREE.Raycaster();
  ray.setFromCamera(ndc, camera);
  const result = new THREE.Vector3();
  return ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), result)
    ? [-result.x, 0, result.z] : null;
}

function onPointerDown(event) {
  hideContextMenu();
  pointerDown = {
    x: event.clientX, y: event.clientY, button: event.button,
    maximumTravel: 0, releasedAt: 0,
  };
  if (event.ctrlKey) {
    event.preventDefault();
    event.stopImmediatePropagation();
    const position = planePositionAt(event.clientX, event.clientY);
    if (position) openAnnotation(position);
  }
}

function updatePointerTravel(event) {
  if (!pointerDown) return;
  pointerDown.maximumTravel = Math.max(
    pointerDown.maximumTravel,
    Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y),
  );
}

function onPointerUp(event) {
  updatePointerTravel(event);
  if (pointerDown) pointerDown.releasedAt = performance.now();
}

function onPointerCancel() { pointerDown = null; }

function onCanvasClick(event) {
  if (event.ctrlKey) return;
  updatePointerTravel(event);
  if (pointerDown?.maximumTravel > 5) return;
  const record = pickAt(event.clientX, event.clientY);
  if (record) focusRecord(record);
}

function onPointerMove(event) {
  updatePointerTravel(event);
  if (hoverFrame) return;
  hoverFrame = requestAnimationFrame(() => {
    hoverFrame = null;
    const record = pickAt(event.clientX, event.clientY, 10);
    if (!record) return hideTooltip();
    const {width, height} = viewportMetrics();
    dom.tooltip.textContent = [record.subject || record.kind, record.system].filter(Boolean).join(' // ');
    dom.tooltip.style.left = `${Math.max(4, Math.min(width - 290, event.clientX + 13))}px`;
    dom.tooltip.style.top = `${Math.max(4, Math.min(height - 45, event.clientY + 13))}px`;
    dom.tooltip.hidden = false;
  });
}

function hideTooltip() { dom.tooltip.hidden = true; }

function onContextMenu(event) {
  event.preventDefault();
  updatePointerTravel(event);
  // OrbitControls uses a right-button drag to pan. Chromium fires a
  // contextmenu event after that gesture, so only a stationary right-click
  // is allowed to expose annotation actions.
  const recentRightGesture = pointerDown?.button === 2
    && (!pointerDown.releasedAt || performance.now() - pointerDown.releasedAt < 800);
  if (recentRightGesture && pointerDown.maximumTravel > 5) {
    hideContextMenu();
    pointerDown = null;
    return;
  }
  pointerDown = null;
  const record = pickAt(event.clientX, event.clientY);
  const position = positionOf(record) || planePositionAt(event.clientX, event.clientY);
  dom['context-menu'].replaceChildren();
  const addAction = (label, callback, danger = false) => {
    const item = document.createElement('button');
    item.textContent = label;
    if (danger) item.style.color = 'var(--red)';
    item.addEventListener('click', () => { hideContextMenu(); callback(); });
    dom['context-menu'].appendChild(item);
  };
  if (record?.kind === 'Annotation') {
    addAction('EDIT ANNOTATION', () => openAnnotation(record.position, record));
    addAction('DELETE ANNOTATION', () => deleteAnnotation(record.annotation_id), true);
  }
  if (position) addAction('ADD ANNOTATION HERE', () => openAnnotation(position, null, record?.system));
  if (record) addAction('INSPECT MAP RECORD', () => inspect(record));
  const {width, height} = viewportMetrics();
  dom['context-menu'].style.left = `${Math.max(4, Math.min(width - 205, event.clientX))}px`;
  dom['context-menu'].style.top = `${Math.max(4, Math.min(height - 130, event.clientY))}px`;
  dom['context-menu'].hidden = false;
}

function hideContextMenu() { dom['context-menu'].hidden = true; }

function inspect(record) {
  if (!record) return;
  selectedRecord = record;
  dom['inspect-kind'].textContent = String(record.kind || 'MAP INTELLIGENCE').toUpperCase();
  dom['inspect-title'].textContent = record.subject || record.system || record.kind || 'Map record';
  dom['inspect-system'].textContent = record.system || '';
  dom['inspect-detail'].textContent = record.detail || 'Retained commander map evidence.';
  const position = positionOf(record);
  dom['inspect-coordinates'].replaceChildren();
  if (position) {
    for (const [label, value] of [['X', position[0]], ['Y', position[1]], ['Z', position[2]]]) {
      const dt = document.createElement('dt');
      dt.textContent = label;
      const dd = document.createElement('dd');
      dd.textContent = `${number(value, 2)} LY`;
      dom['inspect-coordinates'].append(dt, dd);
    }
  }
  dom['inspect-actions'].replaceChildren();
  const addButton = (label, callback, primary = false) => {
    const item = document.createElement('button');
    item.textContent = label;
    if (primary) item.className = 'primary-button';
    item.addEventListener('click', callback);
    dom['inspect-actions'].appendChild(item);
  };
  if (position) {
    addButton('FOCUS', () => focusPosition(position, record.kind === 'Region' ? 16000 : 1600), true);
    addButton('ADD MARK', () => openAnnotation(position, null, record.system));
  }
  if (record.kind === 'Annotation') {
    addButton('EDIT', () => openAnnotation(position, record));
    addButton('DELETE', () => deleteAnnotation(record.annotation_id));
  } else if (!['Cluster', 'Region'].includes(record.kind)) {
    addButton('OPEN IN VOID COMPASS', () => command({action: 'open_record', record}));
  }
  dom.inspector.classList.add('open');
}

function closeInspector() {
  dom.inspector.classList.remove('open');
  selectedRecord = null;
}

function openAnnotation(position, existing = null, system = '') {
  if (!validPosition(position)) return;
  dom['annotation-id'].value = existing?.annotation_id || existing?.id || '';
  dom['annotation-position'].value = JSON.stringify(position);
  dom['annotation-system'].value = system || existing?.system || '';
  dom['annotation-category'].value = existing?.category || 'Note';
  dom['annotation-title'].value = existing?.subject || existing?.title || system || '';
  dom['annotation-note'].value = existing?.note || '';
  dom['annotation-location'].textContent = `${system || existing?.system || 'DEEP SPACE'} // ${position.map((value) => number(value, 2)).join(' · ')} LY`;
  dom['annotation-delete'].hidden = !dom['annotation-id'].value;
  dom['annotation-dialog'].showModal();
  dom['annotation-title'].focus();
}

function deleteAnnotation(id) {
  if (!id || !window.confirm('Delete this commander map annotation?')) return;
  command({action: 'annotation_delete', id});
  if (dom['annotation-dialog'].open) dom['annotation-dialog'].close();
  closeInspector();
}

function buildSearchIndex() {
  const rows = [];
  for (const row of snapshot?.route || []) {
    rows.push({label: row.system, hint: 'VISITED SYSTEM', record: {kind: 'System', system: row.system, subject: 'Visited system', detail: row.fss_complete ? 'FSS survey complete' : 'Retained journal arrival', position: row.pos}});
  }
  for (const record of snapshot?.markers || []) {
    rows.push({label: record.subject || record.system, hint: `${record.layer}${record.system ? ` // ${record.system}` : ''}`, record});
  }
  for (const row of regions?.labels || []) {
    rows.push({label: row.name, hint: `CODEX REGION ${String(row.id).padStart(2, '0')}`, record: {kind: 'Region', subject: row.name, detail: `Universal Cartographics region ${row.id} of 42`, position: row.position}});
  }
  return rows;
}

function runSearch() {
  const query = dom.search.value.trim().toLowerCase();
  if (!query) {
    dom['search-results'].hidden = true;
    return;
  }
  const matches = buildSearchIndex()
    .filter((row) => `${row.label} ${row.hint}`.toLowerCase().includes(query))
    .sort((a, b) => Number(!String(a.label).toLowerCase().startsWith(query)) - Number(!String(b.label).toLowerCase().startsWith(query)) || String(a.label).length - String(b.label).length)
    .slice(0, 9);
  dom['search-results'].replaceChildren();
  for (const row of matches) {
    const item = document.createElement('button');
    item.className = 'search-result';
    const title = document.createElement('strong');
    title.textContent = row.label || 'Map record';
    const hint = document.createElement('small');
    hint.textContent = row.hint;
    item.append(title, hint);
    item.addEventListener('click', () => {
      dom.search.value = row.label;
      dom['search-results'].hidden = true;
      focusRecord(row.record);
    });
    dom['search-results'].appendChild(item);
  }
  if (!matches.length) {
    const empty = document.createElement('div');
    empty.className = 'search-result';
    empty.textContent = 'No retained map record matches this search.';
    dom['search-results'].appendChild(empty);
  }
  dom['search-results'].hidden = false;
}

function bindInterface() {
  dom['search-button'].addEventListener('click', runSearch);
  dom.search.addEventListener('input', runSearch);
  dom.search.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') { event.preventDefault(); runSearch(); }
    if (event.key === 'Escape') dom['search-results'].hidden = true;
  });
  dom['view-mode'].addEventListener('change', () => setPreset(dom['view-mode'].value));
  dom['scope-mode'].addEventListener('change', () => {
    viewState.scope = dom['scope-mode'].value;
    rebuildDynamicScene();
    setPreset(viewState.mode);
    scheduleSaveView();
  });
  dom['current-button'].addEventListener('click', () => {
    if (validPosition(snapshot?.current?.position)) focusPosition(snapshot.current.position, 1500);
  });
  dom['route-button'].addEventListener('click', () => setPreset('Route Focus'));
  dom['atlas-button'].addEventListener('click', () => setPreset('Galactic Atlas'));
  dom['top-button'].addEventListener('click', toggleTopView);
  dom['mark-button'].addEventListener('click', () => {
    const position = positionOf(selectedRecord) || snapshot?.current?.position;
    if (validPosition(position)) openAnnotation(position, null, selectedRecord?.system || snapshot?.current?.system);
  });
  dom['reset-button'].addEventListener('click', () => setPreset(viewState.mode));
  dom['depth-scale'].addEventListener('input', () => {
    viewState.depth_scale = Number(dom['depth-scale'].value);
    dom['depth-value'].textContent = `${viewState.depth_scale}×`;
  });
  dom['depth-scale'].addEventListener('change', () => {
    rebuildDynamicScene();
    setPreset(viewState.mode);
    scheduleSaveView();
  });
  dom['layers-toggle'].addEventListener('click', () => {
    const enable = Object.values(viewState.layers).some((value) => !value);
    for (const name of LAYERS) viewState.layers[name] = enable;
    syncLayerControls();
    applyLayerVisibility();
    scheduleSaveView();
  });
  dom['close-inspector'].addEventListener('click', closeInspector);
  dom['annotation-cancel'].addEventListener('click', () => dom['annotation-dialog'].close());
  dom['annotation-delete'].addEventListener('click', () => deleteAnnotation(dom['annotation-id'].value));
  dom['annotation-form'].addEventListener('submit', (event) => {
    event.preventDefault();
    const position = JSON.parse(dom['annotation-position'].value || 'null');
    command({
      action: 'annotation_upsert',
      annotation: {
        id: dom['annotation-id'].value,
        category: dom['annotation-category'].value,
        title: dom['annotation-title'].value,
        note: dom['annotation-note'].value,
        system: dom['annotation-system'].value,
        position,
      },
    });
    dom['annotation-dialog'].close();
  });
  document.addEventListener('pointerdown', (event) => {
    if (!dom['context-menu'].contains(event.target)) hideContextMenu();
  });
}

function onResize() {
  if (!renderer || !camera) return;
  const {width, height} = measureViewport();
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  renderer.setSize(width, height, false);
  dom['route-overlay'].setAttribute('viewBox', `0 0 ${width} ${height}`);
  updateLabels();
  updateRouteOverlay(performance.now(), true);
}

async function fetchSnapshot() {
  const response = await fetch(api('/api/snapshot'), {cache: 'no-store'});
  if (!response.ok) throw new Error(`Snapshot HTTP ${response.status}`);
  return response.json();
}

async function connectLiveEvents() {
  eventSource?.close();
  eventSource = new EventSource(api('/api/events'));
  eventSource.addEventListener('revision', async () => {
    try {
      const data = await fetchSnapshot();
      applySnapshot(data);
      setConnection('connected', 'LIVE JOURNAL LINK');
    } catch (error) {
      setConnection('offline', 'SNAPSHOT RETRYING');
    }
  });
  eventSource.onopen = () => setConnection('connected', 'LIVE JOURNAL LINK');
  eventSource.onerror = () => setConnection('offline', 'LOCAL LINK RETRYING');
}

async function start() {
  if (!token) {
    setLoading('This atlas URL is missing its private session token.', true);
    return;
  }
  try {
    setLoading('Initialising WebGL renderer…');
    initialiseThree();
    bindInterface();
    setLoading('Loading Codex regions and commander history…');
    const [regionPayload, data] = await Promise.all([
      fetch(api('/api/regions'), {cache: 'force-cache'}).then((response) => response.json()),
      fetchSnapshot(),
    ]);
    regions = regionPayload;
    applySnapshot(data, true);
    if (!captureMode) {
      await connectLiveEvents();
      command({action: 'ready'});
      setConnection('connected', 'LIVE JOURNAL LINK');
      setInterval(() => command({action: 'heartbeat'}), 5000);
    } else {
      setConnection('connected', 'LOCAL CAPTURE');
    }
    dom.loading.classList.add('done');
    if (window.parent !== window) {
      window.parent.postMessage({type: 'voidcompass-atlas-ready'}, '*');
    }
    if (captureMode) animate(performance.now());
    else requestAnimationFrame(animate);
  } catch (error) {
    console.error(error);
    setConnection('offline', 'ATLAS START FAILED');
    setLoading(`Could not initialise the local atlas: ${error.message}`, true);
  }
}

start();
