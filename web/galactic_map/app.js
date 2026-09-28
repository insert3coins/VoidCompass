// Galactic Atlas: Elite's 42 Codex regions and everywhere the commander has
// been, from the journal. Python owns the data (a snapshot per change, over
// an event stream); this page draws it, answers "where is that?", keeps the
// commander's view and map marks, and replays the journey.
import * as THREE from './vendor/three.module.min.js';
import {createCamera} from './camera.js';
import {createScene, MARKER_SHAPES} from './scene.js';
import {decodeRegions, regionVisits} from './regions.js';

const params = new URLSearchParams(window.location.search);
const token = params.get('token') || '';
const api = (path) => `${path}${path.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`;
if (window.self !== window.top) document.documentElement.classList.add('embedded');

const ORIENTATION = 'galactic-north-up-east-right-v3';
const FOV_HALF = 17.5 * Math.PI / 180;
const LAYERS = ['Regions', 'Travel', 'Planned', 'Return', 'Sectors', 'Valuable', 'Biology', 'Codex',
  'Photos', 'Recon', 'Revisit', 'Bookmarks', 'Annotations'];
const LAYER_INFO = {
  Regions: {label: 'Codex regions', shape: 'hexagon', tone: 'border'},
  Travel: {label: 'Where you have been', shape: 'line', tone: 'accent'},
  Planned: {label: 'Plotted route', shape: 'dash', tone: 'orange'},
  Return: {label: 'Retrace the last 60 jumps', shape: 'line', tone: 'green'},
  Sectors: {label: 'Expedition sectors', shape: 'square', tone: 'muted'},
  Valuable: {label: 'Valuable worlds', shape: 'diamond', tone: 'yellow'},
  Biology: {label: 'Biology', shape: 'circle', tone: 'green'},
  Codex: {label: 'Codex entries', shape: 'hexagon', tone: 'accent'},
  Photos: {label: 'Screenshots', shape: 'square', tone: 'text'},
  Recon: {label: 'Recon candidates', shape: 'triangle', tone: 'orange'},
  Revisit: {label: 'Unfinished surveys', shape: 'ring', tone: 'red'},
  Bookmarks: {label: 'Bookmarks', shape: 'star', tone: 'orange'},
  Annotations: {label: 'Your map marks', shape: 'cross', tone: 'text'},
};
const MARK_TONES = {Note: 'text', Danger: 'red', 'Region of Interest': 'yellow', 'Survey Target': 'green', Waypoint: 'accent'};
const SECTOR_TONES = {surveyed: 'green', incomplete: 'yellow', untouched: 'dim'};
// Well-known places, at their published galactic coordinates.
const PLACES = [
  {name: 'Sol', pos: [0, 0, 0], note: 'Home of humanity'},
  {name: 'Sagittarius A*', pos: [25.21875, -20.90625, 25899.96875], note: 'The black hole at the heart of the galaxy'},
  {name: 'Colonia', pos: [-9530.5, -910.28125, 19808.125], note: 'The frontier colony, 22,000 ly from Sol'},
  {name: 'Beagle Point', pos: [-1111.5625, -134.21875, 65269.75], note: 'The far rim, 65,000 ly out'},
  {name: 'Merope', pos: [-78.59375, -149.625, -340.53125], note: 'The Pleiades'},
];

const $ = (id) => document.getElementById(id);
const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const number = (value, digits = 0) => Number(value || 0).toLocaleString(undefined, {minimumFractionDigits: digits, maximumFractionDigits: digits});
const ly = (value) => `${number(value, value < 100 ? 1 : 0)} LY`;
const distance3 = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const validPos = (value) => Array.isArray(value) && value.length >= 3 && value.slice(0, 3).every(Number.isFinite);
const posOf = (row) => (validPos(row?.pos) ? row.pos.slice(0, 3) : validPos(row?.position) ? row.position.slice(0, 3) : null);
const epoch = (value) => { const t = Date.parse(value || ''); return Number.isFinite(t) ? t : 0; };
const day = (value) => { const t = epoch(value); return t ? new Date(t).toLocaleDateString(undefined, {day: '2-digit', month: 'short', year: 'numeric'}).toUpperCase() : '—'; };

let viewport, scene, cam;
let theme = {};
let regions = null;
let snapshot = null;
let viewState = {scope: 'All History', layers: Object.fromEntries(LAYERS.map((name) => [name, name !== 'Return'])),
  depth_scale: 4, grid: true, atmosphere: true, labels: true, camera: null};
let route = [];
let systems = new Map();
let markers = [];
let plannedLine = [];
let visits = new Map();
let current = null;
let currentRegion = 0;
let selection = null;
let hoverItem = null;
let hoverRegion = 0;
let pickables = [];
let pickDirty = true;
let labelsDirty = true;
let replay = {value: 1, playing: false, last: 0, duration: 16000};
let reducedMotion = false;
let lastInteraction = 0;
let lastRender = 0;
let lastFocus = null;
let saveTimer = 0;
let width = 1, height = 1;

// --- Theme and tones ---------------------------------------------------------------
const CSS_TOKENS = ['bg', 'panel', 'panel_alt', 'panel_raised', 'header', 'input', 'inset', 'border', 'border_soft',
  'selection', 'accent', 'orange', 'text', 'muted', 'dim', 'green', 'yellow', 'red'];
function applyTheme(values = {}) {
  const key = JSON.stringify(values);
  if (key === JSON.stringify(theme)) return false;
  theme = {...values};
  for (const name of CSS_TOKENS) if (values[name]) document.documentElement.style.setProperty(`--${name.replace('_', '-')}`, values[name]);
  scene.setTheme(values);
  return true;
}
const tone = (name) => new THREE.Color(theme[name] || {accent: '#00d1ff', orange: '#ff8a3d', text: '#dcebf3', muted: '#91a8b7', dim: '#607584', green: '#54e39a', yellow: '#f5c76d', red: '#ff6b70', border: '#243746'}[name] || '#dcebf3');

// A star's colour on the map follows its class, in the theme's own colours.
function starTone(value) {
  const cls = String(value || '').toUpperCase();
  if (cls.startsWith('TTS') || cls.startsWith('AEBE')) return 'orange';
  if (/^(O|B|W|N)/.test(cls)) return 'accent';
  if (/^(A|F|D)/.test(cls)) return 'text';
  if (cls.startsWith('G')) return 'yellow';
  if (cls.startsWith('K')) return 'orange';
  if (/^(M|L|T|Y|C|S)/.test(cls)) return 'red';
  return 'muted';
}
const markerTone = (row) => (row.layer === 'Annotations' ? MARK_TONES[row.category] || 'text' : LAYER_INFO[row.layer]?.tone || 'text');

function glyph(shape, colour) {
  const paths = {
    circle: '<circle cx="7" cy="7" r="4.5"/>', diamond: '<path d="M7 1.5 12.5 7 7 12.5 1.5 7z"/>',
    square: '<rect x="3" y="3" width="8" height="8"/>', triangle: '<path d="M7 2 12.5 12H1.5z"/>',
    star: '<path d="M7 1.2l1.7 3.8 4.1.4-3.1 2.8.9 4.1L7 10.2l-3.6 2.1.9-4.1L1.2 5.4l4.1-.4z"/>',
    hexagon: '<path d="M7 1.5l4.8 2.75v5.5L7 12.5l-4.8-2.75v-5.5z"/>',
    ring: '<circle cx="7" cy="7" r="4" fill="none" stroke-width="2.2"/>', cross: '<path d="M5.6 1.5h2.8v4.1h4.1v2.8H8.4v4.1H5.6V8.4H1.5V5.6h4.1z"/>',
    line: '<path d="M1 10 5 6l3 2 5-5" fill="none" stroke-width="2"/>', dash: '<path d="M1 7h3M6 7h3M11 7h2" fill="none" stroke-width="2"/>',
  };
  return `<svg class="glyph" viewBox="0 0 14 14" fill="${colour}" stroke="${colour}">${paths[shape] || paths.circle}</svg>`;
}

// --- Talking to Python -----------------------------------------------------------------
function command(payload) {
  return fetch(api('/api/command'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)})
    .then((response) => response.ok).catch(() => false);
}

function scheduleSave() {
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
    const {x, z, distance, heading, tilt} = cam.state;
    command({action: 'save_view', state: {
      orientation: ORIENTATION, scope: viewState.scope, layers: viewState.layers, depth_scale: viewState.depth_scale,
      grid: viewState.grid, atmosphere: viewState.atmosphere, labels: viewState.labels,
      camera: {target: [x, 0, z], distance, heading, tilt},
    }});
  }, 1200);
}

function setLink(stateName, text) {
  $('link-dot').className = `link-dot ${stateName}`;
  $('link-state').textContent = text;
}

// --- Deriving what to draw from the snapshot ---------------------------------------------------
function scopedRoute(data) {
  const rows = (data.route || []).filter((row) => validPos(row.pos));
  if (viewState.scope === 'Current Session') {
    const since = Number(data.session?.started_epoch || 0) * 1000;
    return since ? rows.filter((row) => epoch(row.timestamp) >= since) : rows;
  }
  if (viewState.scope === 'Active Expedition' && data.expedition) {
    const since = epoch(data.expedition.started);
    const names = new Set((data.expedition.systems || []).map((name) => String(name).toLowerCase()));
    return rows.filter((row) => (since && epoch(row.timestamp) >= since) || names.has(String(row.system || '').toLowerCase()));
  }
  return rows;
}

function derive() {
  const data = snapshot;
  route = scopedRoute(data);
  systems = new Map();
  for (const row of route) {
    const key = String(row.system || '').toLowerCase();
    if (!key) continue;
    const entry = systems.get(key) || {kind: 'system', name: row.system, pos: row.pos, visits: 0, first: row.timestamp, last: row.timestamp,
      star: row.star_class, fss: false, jump: 0, records: []};
    entry.visits += 1;
    entry.pos = row.pos;
    entry.last = row.timestamp || entry.last;
    entry.first = entry.first || row.timestamp;
    entry.star = row.star_class || entry.star;
    entry.fss = entry.fss || Boolean(row.fss_complete);
    entry.jump = Number(row.jump_dist || 0) || entry.jump;
    systems.set(key, entry);
  }
  markers = (data.markers || []).filter((row) => validPos(row.position)).map((row, index) => ({...row, kind: 'marker', recordKind: row.kind, index, pos: row.position.slice(0, 3)}));
  for (const row of markers) {
    const entry = row.system ? systems.get(row.system.toLowerCase()) : null;
    if (entry) entry.records.push(row);
  }
  current = validPos(data.current?.position) ? data.current.position.slice(0, 3) : null;
  currentRegion = current && regions ? regions.idAt(current[0], current[2]) : 0;
  const planned = (data.planned || []).filter((row) => validPos(row.pos) && !row.visited);
  plannedLine = planned.length ? [...(current ? [{pos: current, system: data.current.system}] : []), ...planned] : [];
  visits = regions ? regionVisits(regions, route) : new Map();
}

function pushScene() {
  const layers = viewState.layers;
  scene.setVisibility(layers);
  scene.setBackdrop({grid: viewState.grid, glow: viewState.atmosphere});
  scene.setRoute(route);
  scene.setRetrace(route.slice(-61));
  scene.setPlanned(plannedLine);
  const chosenSystem = selection?.kind === 'system' ? selection.name.toLowerCase() : '';
  // When each system was first reached, as a share of the journey, so a
  // replay only shows what the commander had seen by then.
  const reached = new Map();
  route.forEach((row, index) => {
    const key = String(row.system || '').toLowerCase();
    if (key && !reached.has(key)) reached.set(key, index / Math.max(1, route.length - 1));
  });
  scene.setSystems([...systems.values()].map((entry) => ({
    t: reached.get(entry.name.toLowerCase()) ?? -1,
    pos: entry.pos, color: tone(starTone(entry.star)), shape: MARKER_SHAPES.circle,
    size: entry.visits > 1 ? 6 : 5, state: entry.name.toLowerCase() === chosenSystem ? 1 : 0,
  })));
  scene.setMarkers(markers.filter((row) => layers[row.layer] && row.layer !== 'Sectors').map((row) => ({
    t: row.system ? reached.get(row.system.toLowerCase()) ?? -1 : -1,
    pos: row.pos, color: tone(markerTone(row)), shape: MARKER_SHAPES[LAYER_INFO[row.layer]?.shape] ?? 0, size: 10.5,
    state: selection?.kind === 'marker' && selection.index === row.index ? 1 : hoverItem?.kind === 'marker' && hoverItem.index === row.index ? .6 : 0,
  })));
  scene.setSectors(markers.filter((row) => row.layer === 'Sectors').map((row) => ({
    pos: row.pos, size: Number(row.cell_size || 100), color: tone(SECTOR_TONES[row.status] || 'dim'),
  })));
  pushBeacons();
  scene.setVisitedRegions([...visits.keys()]);
  scene.setRegionState({current: currentRegion, selected: selection?.kind === 'region' ? selection.id : 0, hover: hoverRegion});
  pickDirty = labelsDirty = true;
}

function replayHead() {
  if (replay.value >= 1 || route.length < 2) return null;
  const at = replay.value * (route.length - 1);
  const index = Math.floor(at), frac = at - index;
  const a = route[index], b = route[Math.min(route.length - 1, index + 1)];
  return {pos: a.pos.map((value, axis) => value + (b.pos[axis] - value) * frac), row: frac < .5 ? a : b};
}

function pushBeacons() {
  const rows = [];
  const head = replayHead();
  if (current && !head) rows.push({pos: current, color: tone('accent'), shape: MARKER_SHAPES.target, size: 38, current: true});
  if (head) rows.push({pos: head.pos, color: tone('accent'), shape: MARKER_SHAPES.target, size: 30, current: true});
  if (plannedLine.length > 1 && viewState.layers.Planned) rows.push({pos: plannedLine.at(-1).pos, color: tone('orange'), shape: MARKER_SHAPES.star, size: 16});
  for (const place of PLACES) rows.push({pos: place.pos, color: tone('muted'), shape: MARKER_SHAPES.ring, size: 10});
  scene.setBeacons(rows, head ? head.pos : current);
}

// --- Applying a snapshot ------------------------------------------------------------------------
function applySnapshot(data, first = false) {
  snapshot = data;
  reducedMotion = Boolean(data.reduced_motion) || window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.documentElement.classList.toggle('reduced-motion', reducedMotion);
  applyTheme(data.theme || {});
  if (first) {
    const saved = data.view_state || {};
    viewState = {...viewState, ...saved, layers: {...viewState.layers, ...(saved.layers || {})}};
    syncControls();
  }
  if (scene.depth !== viewState.depth_scale) scene.setDepth(viewState.depth_scale);
  derive();
  if (selection?.kind === 'system') selection = systems.get(selection.name.toLowerCase()) || selection;
  pushScene();
  renderHeader();
  renderStats();
  renderPlaces();
  renderRegionList();
  renderLayers();
  renderReplayLabels();
  if (selection) showInspector(selection, false);
  if (first) initialView();
  const focus = data.focus_request;
  if (focus && focus.id !== lastFocus) {
    lastFocus = focus.id;
    if (!first || validPos(focus.position)) focusOn({kind: 'system', name: focus.system, pos: focus.position}, 420);
  }
}

function renderHeader() {
  const data = snapshot;
  $('here-system').textContent = data.current?.system || 'Position unknown';
  const region = data.current?.region;
  $('here-region').textContent = region?.name ? `REGION ${String(region.id).padStart(2, '0')} · ${region.name.toUpperCase()}` : 'WAITING FOR THE JOURNAL';
  $('commander').textContent = data.profile?.commander ? `CMDR ${data.profile.commander}` : '';
  const context = data.route_context || {};
  if (plannedLine.length > 1) {
    const destination = plannedLine.at(-1);
    $('route-state').textContent = `NEXT · ${context.next_system || plannedLine[1]?.system || '—'}`;
    $('route-detail').textContent = `${number(plannedLine.length - 1)} JUMPS TO ${String(destination.system || 'DESTINATION').toUpperCase()} · ${ly(distance3(plannedLine[0].pos, destination.pos))}`;
  } else {
    $('route-state').textContent = 'NO ROUTE PLOTTED';
    $('route-detail').textContent = current ? `${ly(distance3([0, 0, 0], current))} FROM SOL` : '';
  }
}

function renderStats() {
  $('stat-systems').textContent = number(systems.size);
  $('stat-distance').textContent = ly(route.reduce((sum, row) => sum + Number(row.jump_dist || 0), 0));
  $('stat-regions').textContent = `${visits.size} / 42`;
  $('stat-intel').textContent = number(markers.filter((row) => row.layer !== 'Annotations' && row.layer !== 'Sectors').length);
  $('stat-marks').textContent = number((snapshot.annotations || []).length);
  $('tab-regions-count').textContent = String(visits.size);
}

// --- Panels ---------------------------------------------------------------------------------------
function renderPlaces() {
  const rows = [];
  if (current) rows.push({key: 'here', icon: '◎', title: snapshot.current.system || 'Your position', sub: 'YOU ARE HERE'});
  if (plannedLine.length > 1) rows.push({key: 'dest', icon: '★', title: plannedLine.at(-1).system || 'Destination', sub: `ROUTE DESTINATION · ${plannedLine.length - 1} JUMPS`});
  if (route.length > 1) rows.push({key: 'journey', icon: '⤳', title: 'Your journey', sub: `${number(systems.size)} SYSTEMS · ${visits.size} REGIONS`});
  rows.push({key: 'galaxy', icon: '✺', title: 'The whole galaxy', sub: '42 CODEX REGIONS'});
  PLACES.forEach((place, index) => rows.push({key: `place-${index}`, icon: '◇', title: place.name, sub: place.note.toUpperCase()}));
  $('places').innerHTML = rows.map((row) => `<button type="button" class="row-button" data-place="${row.key}"><i>${row.icon}</i><span><b>${escape(row.title)}</b><small>${escape(row.sub)}</small></span></button>`).join('');
}

function renderRegionList() {
  if (!regions) return;
  const visited = visits.size;
  $('regions-visited').textContent = String(visited);
  $('regions-meter').style.width = `${visited / 42 * 100}%`;
  $('region-list').innerHTML = regions.labels.map((label) => {
    const entry = visits.get(label.id);
    const here = label.id === currentRegion;
    const sub = entry ? `${number(entry.systems)} SYSTEM${entry.systems === 1 ? '' : 'S'} · FIRST ${day(entry.first)}` : 'NOT VISITED';
    const active = selection?.kind === 'region' && selection.id === label.id;
    return `<button type="button" class="row-button${entry ? ' visited' : ''}${here ? ' here' : ''}${active ? ' active' : ''}" data-region="${label.id}"><i>${String(label.id).padStart(2, '0')}</i><span><b>${escape(label.name)}</b><small>${sub}</small></span>${here ? '<em>HERE</em>' : ''}</button>`;
  }).join('');
}

function layerCount(name) {
  if (name === 'Regions') return 42;
  if (name === 'Travel') return systems.size;
  if (name === 'Planned') return Math.max(0, plannedLine.length - 1);
  if (name === 'Return') return Math.min(60, Math.max(0, route.length - 1));
  return markers.filter((row) => row.layer === name).length;
}

function renderLayers() {
  $('layer-list').innerHTML = LAYERS.map((name) => {
    const info = LAYER_INFO[name];
    const on = viewState.layers[name] !== false;
    return `<button type="button" class="row-button" data-layer="${name}" aria-pressed="${on}">${glyph(info.shape, theme[info.tone] || 'currentColor')}<span><b>${escape(info.label)}</b></span><em>${number(layerCount(name))}</em><i class="switch"></i></button>`;
  }).join('');
}

function syncControls() {
  $('scope').value = viewState.scope;
  $('toggle-grid').checked = viewState.grid !== false;
  $('toggle-glow').checked = viewState.atmosphere !== false;
  $('toggle-labels').checked = viewState.labels !== false;
  $('depth').value = String(viewState.depth_scale);
  $('depth-value').textContent = `${viewState.depth_scale}×`;
}

function renderReplayLabels() {
  $('replay-start').textContent = route.length ? day(route[0].timestamp) : '—';
  $('replay-end').textContent = route.length ? day(route.at(-1).timestamp) : '—';
  const head = replayHead();
  $('replay-now').textContent = head ? `${head.row.system || '—'} · ${day(head.row.timestamp)}` : route.length ? 'FULL HISTORY' : 'NO JOURNAL HISTORY YET';
  $('replay').value = String(Math.round(replay.value * 1000));
  $('replay-play').innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${replay.playing ? 'M6 5h4v14H6zM14 5h4v14h-4z' : 'M8 5v14l11-7z'}"/></svg>`;
}

// --- Inspector ---------------------------------------------------------------------------------------
function fact(label, value, wide = false) {
  return `<div${wide ? ' class="wide"' : ''}><dt>${escape(label)}</dt><dd>${value}</dd></div>`;
}
const coords = (pos) => `${number(pos[0], 1)} / ${number(pos[1], 1)} / ${number(pos[2], 1)}`;

function recordRow(row) {
  const info = LAYER_INFO[row.layer] || {};
  const actions = row.layer === 'Annotations'
    ? `<button type="button" data-edit-mark="${escape(row.annotation_id)}">EDIT</button>`
    : row.layer !== 'Sectors' ? `<button type="button" data-open-record="${row.index}">OPEN</button>` : '';
  return `<div class="record">${glyph(info.shape, theme[markerTone(row)] || 'currentColor')}<span><b>${escape(row.subject || row.kind)}</b><small>${escape(row.detail || info.label || '')}</small></span>${actions}</div>`;
}

function showInspector(item, reveal = true) {
  selection = item;
  const kind = $('inspect-kind'), title = $('inspect-title'), sub = $('inspect-sub');
  const facts = [], actions = [];
  let records = [];
  const regionId = item.pos && regions ? regions.idAt(item.pos[0], item.pos[2]) : 0;
  const regionName = regionId ? regions.names[regionId] : 'Outside the charted regions';
  if (item.kind === 'system') {
    kind.textContent = 'STAR SYSTEM';
    title.textContent = item.name;
    sub.textContent = `REGION ${String(regionId).padStart(2, '0')} · ${regionName.toUpperCase()}`;
    const starTag = item.star ? `<span class="chip" style="color:${theme[starTone(item.star)] || 'inherit'}">CLASS ${escape(item.star)}</span>` : '—';
    facts.push(fact('STAR', starTag), fact('VISITS', number(item.visits || 0)));
    if (item.first) facts.push(fact('FIRST VISIT', day(item.first)), fact('LAST VISIT', day(item.last)));
    facts.push(fact('FROM SOL', ly(distance3([0, 0, 0], item.pos))), fact('FROM YOU', current ? ly(distance3(current, item.pos)) : '—'));
    if (item.visits) facts.push(fact('SURVEY', item.fss ? '<span class="chip" style="color:var(--green)">FSS COMPLETE</span>' : 'NOT COMPLETE'));
    facts.push(fact('GALACTIC X / Y / Z', coords(item.pos), true));
    records = item.records || markers.filter((row) => row.system && row.system.toLowerCase() === String(item.name).toLowerCase());
  } else if (item.kind === 'marker') {
    const info = LAYER_INFO[item.layer] || {};
    kind.textContent = (item.layer === 'Annotations' ? `YOUR MAP MARK · ${item.category || 'NOTE'}` : info.label || item.layer).toUpperCase();
    title.textContent = item.subject || item.kind;
    sub.textContent = `${item.system ? `${item.system.toUpperCase()} · ` : ''}${regionName.toUpperCase()}`;
    if (item.detail) facts.push(fact('DETAIL', escape(item.detail), true));
    facts.push(fact('FROM SOL', ly(distance3([0, 0, 0], item.pos))), fact('FROM YOU', current ? ly(distance3(current, item.pos)) : '—'));
    facts.push(fact('GALACTIC X / Y / Z', coords(item.pos), true));
    records = item.system ? markers.filter((row) => row !== item && row.system && row.system.toLowerCase() === item.system.toLowerCase()) : [];
    if (item.layer === 'Annotations') actions.push(`<button type="button" data-edit-mark="${escape(item.annotation_id)}">EDIT MARK</button>`);
    else if (item.layer !== 'Sectors') actions.push(`<button type="button" data-open-record="${item.index}">OPEN IN VOID COMPASS</button>`);
  } else if (item.kind === 'region') {
    const entry = visits.get(item.id);
    const label = regions.labels.find((row) => row.id === item.id);
    kind.textContent = `CODEX REGION ${String(item.id).padStart(2, '0')}`;
    title.textContent = regions.names[item.id];
    sub.textContent = item.id === currentRegion ? 'YOU ARE IN THIS REGION' : entry ? 'VISITED' : 'NOT VISITED YET';
    facts.push(fact('YOUR SYSTEMS', entry ? number(entry.systems) : '0'), fact('SIZE', `${number((label?.weight || 0) * Math.pow(8 * regions.scale, 2) / 1e6, 0)} MLY²`));
    if (entry) facts.push(fact('FIRST ENTERED', day(entry.first)), fact('LAST SEEN', day(entry.last)));
    const anchor = label?.position;
    if (anchor) facts.push(fact('FROM SOL', ly(Math.hypot(anchor[0], anchor[2]))), fact('FROM YOU', current ? ly(Math.hypot(anchor[0] - current[0], anchor[2] - current[2])) : '—'));
    item.pos = anchor || item.pos;
  } else if (item.kind === 'place') {
    kind.textContent = 'LANDMARK';
    title.textContent = item.name;
    sub.textContent = regionName.toUpperCase();
    facts.push(fact('ABOUT', escape(item.note), true), fact('FROM SOL', ly(distance3([0, 0, 0], item.pos))), fact('FROM YOU', current ? ly(distance3(current, item.pos)) : '—'));
    facts.push(fact('GALACTIC X / Y / Z', coords(item.pos), true));
  } else {
    kind.textContent = 'POINT IN SPACE';
    title.textContent = regionName;
    sub.textContent = regionId ? `CODEX REGION ${String(regionId).padStart(2, '0')}` : '';
    facts.push(fact('FROM SOL', ly(distance3([0, 0, 0], item.pos))), fact('FROM YOU', current ? ly(distance3(current, item.pos)) : '—'));
    facts.push(fact('GALACTIC X / Z', `${number(item.pos[0], 0)} / ${number(item.pos[2], 0)}`, true));
  }
  if (item.pos) actions.unshift('<button type="button" class="primary" data-act="focus">FOCUS</button>');
  if (item.pos && item.kind !== 'region') actions.push('<button type="button" data-act="mark">ADD MAP MARK</button>');
  $('inspect-facts').innerHTML = facts.join('');
  $('inspect-records').innerHTML = records.length ? `<p class="section-title">INTEL HERE</p>${records.map(recordRow).join('')}` : '';
  $('inspect-actions').innerHTML = actions.join('');
  if (reveal) $('inspector').hidden = false;
  scene.setRegionState({selected: item.kind === 'region' ? item.id : 0});
  if (reveal) {
    pushScene();
    renderRegionList();
  }
  labelsDirty = true;
}

function closeInspector() {
  selection = null;
  $('inspector').hidden = true;
  pushScene();
  renderRegionList();
}

// --- The camera's places ----------------------------------------------------------------------------------
// The map area the panels leave clear, so a framed place isn't under them.
function clearArea() {
  const side = document.querySelector('.side');
  const left = side && !side.classList.contains('collapsed') && width > 820 ? side.getBoundingClientRect().right + 12 : 12;
  const right = !$('inspector').hidden && width > 820 ? $('inspector').getBoundingClientRect().left - 12 : width - 12;
  const bottom = document.querySelector('.journey').getBoundingClientRect().top - 12;
  return {left, right: Math.max(left + 100, right), top: 12, bottom: Math.max(120, bottom)};
}

// Aim so that (x, z) lands in the middle of the clear area.
function aim(x, z, distance) {
  const area = clearArea();
  const lyPx = (2 * distance * Math.tan(FOV_HALF)) / height;
  const dx = ((area.left + area.right) / 2 - width / 2) * lyPx;
  const dy = ((area.top + area.bottom) / 2 - height / 2) * lyPx;
  const heading = cam.state.heading * Math.PI / 180;
  // Moving the target by the screen offset, turned by the heading.
  return {x: x - (dx * Math.cos(heading) - dy * Math.sin(heading)), z: z - (-dx * Math.sin(heading) - dy * Math.cos(heading))};
}

function frame(points, duration = 1100, minimum = 400) {
  if (!points.length) return;
  const xs = points.map((pos) => pos[0]), zs = points.map((pos) => pos[2]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minZ = Math.min(...zs), maxZ = Math.max(...zs);
  const area = clearArea();
  const aspect = (area.right - area.left) / Math.max(1, area.bottom - area.top);
  const span = Math.max(maxZ - minZ, (maxX - minX) / aspect, minimum) * 1.25;
  const distance = span / (2 * Math.tan(FOV_HALF)) * (height / Math.max(1, area.bottom - area.top));
  cam.flyTo({...aim((minX + maxX) / 2, (minZ + maxZ) / 2, distance), distance}, reducedMotion ? 0 : duration);
}

function focusOn(item, distance = 500) {
  if (!validPos(item.pos)) return;
  const known = item.kind === 'system' && systems.get(String(item.name || '').toLowerCase());
  showInspector(known || item);
  const d = Math.min(cam.state.distance, distance);
  cam.flyTo({...aim(item.pos[0], item.pos[2], d), distance: d}, reducedMotion ? 0 : 1300);
}

function galaxyView(duration = 1200) {
  frame([[-45000, 0, -3000], [45000, 0, 68000]], duration);
}

function regionView(id) {
  const label = regions.labels.find((row) => row.id === id);
  if (!label) return;
  const radius = Math.sqrt(label.weight / Math.PI) * 8 * regions.scale;
  frame([[label.position[0] - radius, 0, label.position[2] - radius], [label.position[0] + radius, 0, label.position[2] + radius]]);
  showInspector({kind: 'region', id, pos: label.position});
}

function initialView() {
  const saved = viewState.camera;
  if (saved && validPos(saved.target) && saved.distance) {
    cam.set({x: saved.target[0], z: saved.target[2], distance: saved.distance, heading: saved.heading || 0, tilt: saved.tilt || 0});
  } else if (route.length > 1) {
    frame(route.map((row) => row.pos), 0);
  } else {
    galaxyView(0);
  }
}

function place(key) {
  if (key === 'here' && current) return focusOn({kind: 'system', name: snapshot.current.system, pos: current}, 900);
  if (key === 'dest' && plannedLine.length > 1) return frame(plannedLine.map((row) => row.pos));
  if (key === 'journey') return frame(route.map((row) => row.pos));
  if (key === 'galaxy') return galaxyView();
  const index = Number(String(key).replace('place-', ''));
  const landmark = PLACES[index];
  if (landmark) focusOn({kind: 'place', ...landmark}, 2500);
}

// --- Picking ----------------------------------------------------------------------------------------------
function refreshPickables() {
  if (!pickDirty) return;
  pickDirty = false;
  const rows = [];
  const layers = viewState.layers;
  for (const row of markers) if (layers[row.layer] && row.layer !== 'Sectors') rows.push({item: row, pos: row.pos, rank: 3});
  if (layers.Travel) for (const entry of systems.values()) rows.push({item: entry, pos: entry.pos, rank: 2});
  PLACES.forEach((landmark) => rows.push({item: {kind: 'place', ...landmark}, pos: landmark.pos, rank: 1}));
  for (const row of rows) row.screen = scene.project(row.pos, width, height);
  pickables = rows.filter((row) => row.screen);
}

function pickAt(clientX, clientY) {
  refreshPickables();
  const rect = viewport.getBoundingClientRect();
  const x = clientX - rect.left, y = clientY - rect.top;
  let best = null, bestScore = Infinity;
  for (const row of pickables) {
    const d = Math.hypot(row.screen.x - x, row.screen.y - y);
    if (d > 12) continue;
    const score = d - row.rank * 3;
    if (score < bestScore) { best = row.item; bestScore = score; }
  }
  return best;
}

function tooltip(event, html) {
  const tip = $('tooltip');
  if (!html) { tip.hidden = true; return; }
  tip.innerHTML = html;
  tip.hidden = false;
  const x = Math.min(window.innerWidth - tip.offsetWidth - 8, event.clientX + 16);
  const y = Math.min(window.innerHeight - tip.offsetHeight - 8, event.clientY + 16);
  tip.style.left = `${x}px`;
  tip.style.top = `${y}px`;
}

function onHover(event) {
  const item = pickAt(event.clientX, event.clientY);
  const point = cam.pick(event.clientX, event.clientY);
  const regionId = point && regions ? regions.idAt(point.x, point.z) : 0;
  const changedItem = item !== hoverItem;
  hoverItem = item;
  if (regionId !== hoverRegion) {
    hoverRegion = regionId;
    scene.setRegionState({hover: viewState.layers.Regions ? regionId : 0});
    labelsDirty = true;
  }
  if (changedItem && item?.kind === 'marker') pushScene();
  viewport.querySelector('canvas').style.cursor = item ? 'pointer' : '';
  if (item) {
    const where = item.kind === 'marker' ? (LAYER_INFO[item.layer]?.label || item.layer) : item.kind === 'place' ? 'LANDMARK' : `${item.star ? `CLASS ${item.star} · ` : ''}${item.visits} VISIT${item.visits === 1 ? '' : 'S'}`;
    tooltip(event, `<b>${escape(item.name || item.subject || item.system)}</b><small>${escape(String(where).toUpperCase())}</small>`);
  } else if (point) {
    const name = regionId ? regions.names[regionId] : 'Beyond the charted regions';
    tooltip(event, `<b>${escape(name)}</b><small>X ${number(point.x)} · Z ${number(point.z)} LY${current ? ` · ${ly(Math.hypot(point.x - current[0], point.z - current[2]))} FROM YOU` : ''}</small>`);
  } else {
    tooltip(event, '');
  }
}

function onClick(event, button) {
  hideMenu();
  const item = pickAt(event.clientX, event.clientY);
  const point = cam.pick(event.clientX, event.clientY);
  if (button === 2) return openMenu(event, item, point);
  if (item) return showInspector(item);
  if (!point) return;
  const regionId = regions?.idAt(point.x, point.z) || 0;
  if (regionId && viewState.layers.Regions) showInspector({kind: 'region', id: regionId, pos: [point.x, 0, point.z]});
  else showInspector({kind: 'point', pos: [point.x, 0, point.z]});
}

function onDoubleClick(event) {
  const item = pickAt(event.clientX, event.clientY);
  if (item?.pos) return focusOn(item, Math.max(60, cam.state.distance * .3));
  const point = cam.pick(event.clientX, event.clientY);
  if (point) cam.flyTo({x: point.x, z: point.z, distance: cam.state.distance * .35}, reducedMotion ? 0 : 700);
}

// --- Context menu and map marks -----------------------------------------------------------------------------
function hideMenu() { $('menu').hidden = true; }

function openMenu(event, item, point) {
  const pos = item?.pos || (point ? [point.x, 0, point.z] : null);
  if (!pos) return;
  const regionId = regions?.idAt(pos[0], pos[2]) || 0;
  const title = item ? (item.name || item.subject) : regionId ? regions.names[regionId] : 'Deep space';
  const menu = $('menu');
  menu.innerHTML = `<p>${escape(String(title).toUpperCase())}</p>
    <button type="button" data-menu="mark">Add a map mark here</button>
    <button type="button" data-menu="centre">Centre the map here</button>
    ${item ? '<button type="button" data-menu="inspect">Show details</button>' : ''}
    ${regionId ? '<button type="button" data-menu="region">About this region</button>' : ''}`;
  menu.hidden = false;
  menu.style.left = `${Math.min(window.innerWidth - menu.offsetWidth - 8, event.clientX)}px`;
  menu.style.top = `${Math.min(window.innerHeight - menu.offsetHeight - 8, event.clientY)}px`;
  menu.onclick = (click) => {
    const action = click.target.closest('[data-menu]')?.dataset.menu;
    if (!action) return;
    hideMenu();
    if (action === 'mark') openMark({position: pos, system: item?.kind === 'system' ? item.name : item?.system || ''});
    if (action === 'centre') cam.flyTo(aim(pos[0], pos[2], cam.state.distance), reducedMotion ? 0 : 600);
    if (action === 'inspect') showInspector(item);
    if (action === 'region') showInspector({kind: 'region', id: regionId, pos});
  };
}

function openMark(values) {
  const existing = values.id ? (snapshot.annotations || []).find((row) => row.id === values.id) : null;
  const mark = existing || values;
  $('mark-heading').textContent = existing ? 'Edit map mark' : 'New map mark';
  $('mark-id').value = existing?.id || '';
  $('mark-position').value = JSON.stringify(mark.position);
  $('mark-system').value = mark.system || '';
  $('mark-category').value = existing?.category || 'Note';
  $('mark-title').value = existing?.title || (mark.system ? mark.system : '');
  $('mark-note').value = existing?.note || '';
  const regionId = regions?.idAt(mark.position[0], mark.position[2]) || 0;
  $('mark-where').textContent = `${mark.system ? `${mark.system.toUpperCase()} · ` : ''}${regionId ? regions.names[regionId].toUpperCase() : 'DEEP SPACE'} · X ${number(mark.position[0])} Z ${number(mark.position[2])}`;
  const remove = $('mark-delete');
  remove.hidden = !existing;
  remove.textContent = 'DELETE';
  remove.dataset.armed = '';
  $('mark-dialog').showModal();
  $('mark-title').focus();
}

// --- Labels on the map --------------------------------------------------------------------------------------
const labelPool = new Map();
function labelElement(key, className, html) {
  let el = labelPool.get(key);
  if (!el) {
    el = document.createElement('div');
    $('labels').appendChild(el);
    labelPool.set(key, el);
  }
  if (el.dataset.html !== html || el.className !== `label ${className}`) {
    el.className = `label ${className}`;
    el.innerHTML = html;
    el.dataset.html = html;
    el.dataset.w = '';
  }
  if (!el.dataset.w) {
    el.style.transform = 'translate(-9999px, -9999px)';
    el.style.opacity = '1';
    el.dataset.w = String(el.offsetWidth);
    el.dataset.h = String(el.offsetHeight);
  }
  return el;
}

function updateLabels() {
  labelsDirty = false;
  const candidates = [];
  const head = replayHead();
  if (head) candidates.push({key: 'head', cls: 'head', pos: head.pos, dy: -30, html: `${escape(head.row.system || '')}<small>${day(head.row.timestamp)}</small>`, rank: 120});
  if (current && !head) candidates.push({key: 'here', cls: 'here', pos: current, dy: -34, html: `${escape(snapshot.current?.system || 'You')}<small>YOU ARE HERE</small>`, rank: 110});
  if (plannedLine.length > 1 && viewState.layers.Planned) candidates.push({key: 'dest', cls: 'dest', pos: plannedLine.at(-1).pos, dy: -24, html: `${escape(plannedLine.at(-1).system || 'Destination')}<small>DESTINATION</small>`, rank: 100});
  const isHere = selection?.kind === 'system' && current && selection.pos && distance3(selection.pos, current) < .01;
  if (selection?.pos && ['system', 'marker', 'place'].includes(selection.kind) && !isHere) {
    candidates.push({key: 'pick', cls: 'pick', pos: selection.pos, dy: 22, html: escape(selection.name || selection.subject || ''), rank: 105});
  }
  for (const landmark of PLACES) candidates.push({key: `place-${landmark.name}`, cls: 'place', pos: landmark.pos, dx: 0, dy: 14, html: escape(landmark.name), rank: 80});
  if (regions && viewState.layers.Regions && viewState.labels !== false) {
    const lyPx = cam.lyPerPixel();
    for (const label of regions.labels) {
      const entry = visits.get(label.id);
      const size = Math.sqrt(label.weight) * 8 * regions.scale / lyPx;
      if (size < 50) continue;
      const cls = `region${entry ? ' visited' : ''}${label.id === hoverRegion ? ' hover' : ''}`;
      const html = `${escape(label.name)}${entry ? `<small>${number(entry.systems)} SYSTEM${entry.systems === 1 ? '' : 'S'}</small>` : ''}`;
      candidates.push({key: `region-${label.id}`, cls, pos: label.position, html, rank: 10 + Math.min(40, label.weight / 60) + (label.id === hoverRegion ? 30 : 0)});
    }
  }
  candidates.sort((a, b) => b.rank - a.rank);
  const placed = [];
  const used = new Set();
  for (const candidate of candidates) {
    const screen = scene.project(candidate.pos, width, height);
    if (!screen) continue;
    const el = labelElement(candidate.key, candidate.cls, candidate.html);
    const w = Number(el.dataset.w), h = Number(el.dataset.h);
    const x = screen.x + (candidate.dx || 0) - w / 2, y = screen.y + (candidate.dy || 0) - h / 2;
    if (x + w < 0 || y + h < 0 || x > width || y > height) continue;
    const box = {l: x - 6, r: x + w + 6, t: y - 3, b: y + h + 3};
    if (placed.some((other) => box.l < other.r && box.r > other.l && box.t < other.b && box.b > other.t)) continue;
    placed.push(box);
    used.add(candidate.key);
    el.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
    el.style.opacity = '1';
  }
  for (const [key, el] of labelPool) {
    if (!used.has(key)) el.style.opacity = '0';
  }
}

// --- Instruments --------------------------------------------------------------------------------------------
function updateInstruments() {
  $('compass-needle').setAttribute('transform', `rotate(${-cam.state.heading} 32 32)`);
  $('tilt').classList.toggle('on', cam.state.tilt > 3);
  const lyPx = cam.lyPerPixel();
  const target = lyPx * 110;
  const power = Math.pow(10, Math.floor(Math.log10(target)));
  const step = [1, 2, 5, 10].find((value) => value * power >= target * .55) * power;
  $('scale-bar').style.width = `${Math.round(step / lyPx)}px`;
  $('scale-label').textContent = step >= 1000 ? `${number(step / 1000)} KLY` : `${number(step)} LY`;
}

// --- The render loop ------------------------------------------------------------------------------------------
function loop(now) {
  window.requestAnimationFrame(loop);
  if (document.hidden) return;
  const flying = cam.step(now);
  if (replay.playing) {
    replay.value = Math.min(1, replay.value + (now - replay.last) / replay.duration);
    replay.last = now;
    if (replay.value >= 1) replay.playing = false;
    pushBeacons();
    renderReplayLabels();
    labelsDirty = true;
  }
  const busy = flying || cam.dragging || replay.playing || now - lastInteraction < 800;
  if (!busy && !labelsDirty && (reducedMotion || now - lastRender < 40)) return;
  lastRender = now;
  if (labelsDirty) updateLabels();
  updateInstruments();
  const lyPx = cam.lyPerPixel();
  scene.render(now, {lyPerPixel: lyPx, replay: replay.value >= 1 ? 2 : replay.value, motion: !reducedMotion,
    // While the journey replays, the system dots step back so the line reads.
    systemAlpha: replay.value < 1 ? .12 : Math.max(.18, Math.min(1, (70 - lyPx) / 50))});
}

function resize() {
  const rect = viewport.getBoundingClientRect();
  width = Math.max(1, Math.round(rect.width));
  height = Math.max(1, Math.round(rect.height));
  scene.resize(width, height);
  cam.resize(width, height);
  pickDirty = labelsDirty = true;
}

// --- Wiring the interface ---------------------------------------------------------------------------------------
function bind() {
  document.querySelector('.tabs').addEventListener('click', (event) => {
    const tab = event.target.closest('[data-tab]');
    if (tab) {
      document.querySelector('.side').classList.remove('collapsed');
      document.querySelectorAll('[data-tab]').forEach((button) => button.classList.toggle('active', button === tab));
      document.querySelectorAll('[data-panel]').forEach((panel) => { panel.hidden = panel.dataset.panel !== tab.dataset.tab; });
    }
    if (event.target.closest('#side-collapse')) document.querySelector('.side').classList.toggle('collapsed');
  });
  $('places').addEventListener('click', (event) => {
    const button = event.target.closest('[data-place]');
    if (button) place(button.dataset.place);
  });
  $('region-list').addEventListener('click', (event) => {
    const button = event.target.closest('[data-region]');
    if (button) regionView(Number(button.dataset.region));
  });
  $('layer-list').addEventListener('click', (event) => {
    const button = event.target.closest('[data-layer]');
    if (!button) return;
    const name = button.dataset.layer;
    viewState.layers[name] = viewState.layers[name] === false;
    renderLayers();
    pushScene();
    scheduleSave();
  });
  $('scope').addEventListener('change', (event) => {
    viewState.scope = event.target.value;
    applySnapshot(snapshot);
    scheduleSave();
  });
  const toggle = (id, key) => $(id).addEventListener('change', (event) => {
    viewState[key] = event.target.checked;
    pushScene();
    scheduleSave();
  });
  toggle('toggle-grid', 'grid');
  toggle('toggle-glow', 'atmosphere');
  toggle('toggle-labels', 'labels');
  $('depth').addEventListener('input', (event) => {
    viewState.depth_scale = Number(event.target.value);
    $('depth-value').textContent = `${viewState.depth_scale}×`;
    scene.setDepth(viewState.depth_scale);
    pickDirty = labelsDirty = true;
    scheduleSave();
  });
  $('search').addEventListener('input', runSearch);
  $('search').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') $('search-results').querySelector('button')?.click();
    if (event.key === 'Escape') { event.target.value = ''; runSearch(); }
  });
  $('search-results').addEventListener('click', (event) => {
    const button = event.target.closest('[data-hit]');
    if (!button) return;
    const hit = searchHits[Number(button.dataset.hit)];
    if (hit.kind === 'region') regionView(hit.id);
    else focusOn(hit, hit.kind === 'place' ? 2500 : 420);
  });
  $('inspector-close').addEventListener('click', closeInspector);
  $('inspector').addEventListener('click', (event) => {
    const act = event.target.closest('[data-act]')?.dataset.act;
    if (act === 'focus' && selection?.pos) {
      if (selection.kind === 'region') regionView(selection.id);
      else focusOn(selection, 420);
    }
    if (act === 'mark' && selection?.pos) openMark({position: selection.pos, system: selection.kind === 'system' ? selection.name : selection.system || ''});
    const open = event.target.closest('[data-open-record]');
    if (open) {
      const row = markers[Number(open.dataset.openRecord)];
      if (row) command({action: 'open_record', record: {kind: row.recordKind, system: row.system, subject: row.subject,
        detail: row.detail, bookmark_id: row.bookmark_id, annotation_id: row.annotation_id, category: row.category, position: row.pos}});
    }
    const edit = event.target.closest('[data-edit-mark]');
    if (edit) openMark({id: edit.dataset.editMark});
  });
  $('compass').addEventListener('click', () => cam.flyTo({heading: 0}, reducedMotion ? 0 : 500));
  $('zoom-in').addEventListener('click', () => cam.zoom(.6));
  $('zoom-out').addEventListener('click', () => cam.zoom(1.6));
  $('tilt').addEventListener('click', () => cam.flyTo({tilt: cam.state.tilt > 3 ? 0 : 52}, reducedMotion ? 0 : 700));
  $('replay').addEventListener('input', (event) => {
    replay.playing = false;
    replay.value = Number(event.target.value) / 1000;
    pushBeacons();
    renderReplayLabels();
    labelsDirty = true;
    lastInteraction = performance.now();
  });
  $('replay-play').addEventListener('click', () => {
    if (route.length < 2) return;
    if (replay.playing) replay.playing = false;
    else {
      if (replay.value >= .999) replay.value = 0;
      replay.playing = true;
      replay.last = performance.now();
      replay.duration = Math.min(40000, Math.max(10000, route.length * 30));
    }
    renderReplayLabels();
  });
  $('mark-cancel').addEventListener('click', () => $('mark-dialog').close());
  $('mark-delete').addEventListener('click', (event) => {
    const button = event.currentTarget;
    if (!button.dataset.armed) {
      button.dataset.armed = '1';
      button.textContent = 'CONFIRM DELETE';
      return;
    }
    command({action: 'annotation_delete', id: $('mark-id').value});
    $('mark-dialog').close();
    closeInspector();
  });
  $('mark-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const position = JSON.parse($('mark-position').value || 'null');
    if (!validPos(position)) return;
    command({action: 'annotation_upsert', annotation: {
      id: $('mark-id').value || undefined, category: $('mark-category').value, title: $('mark-title').value.trim() || $('mark-category').value,
      note: $('mark-note').value.trim(), system: $('mark-system').value, position,
    }});
    viewState.layers.Annotations = true;
    $('mark-dialog').close();
  });
  document.addEventListener('keydown', (event) => {
    if (event.target.closest?.('input, textarea, select, dialog')) return;
    if (event.key === 'Escape') { hideMenu(); if (!$('inspector').hidden) closeInspector(); return; }
    if (cam.key(event)) event.preventDefault();
  });
  document.addEventListener('pointerdown', (event) => { if (!event.target.closest('#menu')) hideMenu(); });
  viewport.addEventListener('pointerleave', () => tooltip(null, ''));
  viewport.addEventListener('dblclick', onDoubleClick);
  window.addEventListener('message', (event) => {
    if (window.parent === window || event.source !== window.parent) return;
    if (event.data?.type === 'voidcompass-atlas-viewport') resize();
    if (event.data?.type === 'voidcompass-atlas-focus-layer' && LAYERS.includes(event.data.layer)) {
      viewState.layers[event.data.layer] = true;
      renderLayers();
      pushScene();
      const points = markers.filter((row) => row.layer === event.data.layer).map((row) => row.pos);
      if (points.length) frame(points);
      scheduleSave();
    }
  });
  new ResizeObserver(resize).observe(viewport);
}

// --- Search -------------------------------------------------------------------------------------------------------
let searchHits = [];
function runSearch() {
  const query = $('search').value.trim().toLowerCase();
  const box = $('search-results');
  if (query.length < 2) {
    box.hidden = true;
    searchHits = [];
    return;
  }
  const hits = [];
  for (const entry of systems.values()) if (entry.name.toLowerCase().includes(query)) hits.push({...entry, icon: '●', sub: `${entry.visits} VISIT${entry.visits === 1 ? '' : 'S'} · ${regions ? regions.names[regions.idAt(entry.pos[0], entry.pos[2])] || '' : ''}`});
  for (const row of plannedLine.slice(1)) if (String(row.system || '').toLowerCase().includes(query)) hits.push({kind: 'system', name: row.system, pos: row.pos, icon: '★', sub: 'ON YOUR PLOTTED ROUTE'});
  if (regions) regions.labels.forEach((label) => { if (label.name.toLowerCase().includes(query)) hits.push({kind: 'region', id: label.id, name: label.name, pos: label.position, icon: '⬡', sub: `CODEX REGION ${String(label.id).padStart(2, '0')}`}); });
  for (const landmark of PLACES) if (landmark.name.toLowerCase().includes(query)) hits.push({kind: 'place', ...landmark, icon: '◇', sub: 'LANDMARK'});
  for (const row of markers) if (row.layer === 'Annotations' && String(row.subject || '').toLowerCase().includes(query)) hits.push({...row, name: row.subject, icon: '✚', sub: 'YOUR MAP MARK'});
  hits.sort((a, b) => (a.name.toLowerCase().startsWith(query) ? 0 : 1) - (b.name.toLowerCase().startsWith(query) ? 0 : 1));
  searchHits = hits.slice(0, 14);
  box.hidden = false;
  box.innerHTML = searchHits.length
    ? searchHits.map((hit, index) => `<button type="button" class="row-button" data-hit="${index}"><i>${hit.icon}</i><span><b>${escape(hit.name)}</b><small>${escape(String(hit.sub).toUpperCase())}</small></span></button>`).join('')
    : '<p class="hint">Nothing in your records by that name. The atlas knows the systems you have visited, your route, the 42 regions and your marks.</p>';
}

// --- Start ----------------------------------------------------------------------------------------------------------
async function fetchSnapshot() {
  const response = await fetch(api('/api/snapshot'), {cache: 'no-store'});
  if (!response.ok) throw new Error(`snapshot ${response.status}`);
  return response.json();
}

function connect() {
  const events = new EventSource(api('/api/events'));
  events.addEventListener('revision', async () => {
    try {
      applySnapshot(await fetchSnapshot());
      setLink('live', 'LIVE JOURNAL LINK');
    } catch (_error) {
      setLink('lost', 'RETRYING');
    }
  });
  events.onopen = () => setLink('live', 'LIVE JOURNAL LINK');
  events.onerror = () => setLink('lost', 'LINK RETRYING');
}

function fail(message) {
  $('loading').classList.add('failed');
  $('loading').querySelector('h2').textContent = 'The atlas could not start';
  $('loading-status').textContent = message;
}

async function start() {
  if (!token) return fail('This atlas address is missing its private session token.');
  try {
    viewport = $('viewport');
    scene = createScene(viewport);
    cam = createCamera(scene.renderer.domElement, {
      onChange(user) {
        pickDirty = labelsDirty = true;
        if (user) {
          lastInteraction = performance.now();
          scheduleSave();
          hideMenu();
        }
      },
      onClick, onHover,
      onInteract() { lastInteraction = performance.now(); },
    });
    scene.useCamera(cam.camera);
    bind();
    resize();
    $('loading-status').textContent = 'Charting the 42 Codex regions…';
    const [regionPayload, data] = await Promise.all([
      fetch(api('/api/regions'), {cache: 'force-cache'}).then((response) => response.json()),
      fetchSnapshot(),
    ]);
    regions = decodeRegions(regionPayload);
    scene.setRegions(regions);
    applySnapshot(data, true);
    connect();
    command({action: 'ready'});
    window.setInterval(() => command({action: 'heartbeat'}), 5000);
    $('loading').classList.add('done');
    if (window.parent !== window) window.parent.postMessage({type: 'voidcompass-atlas-ready'}, '*');
    window.requestAnimationFrame(loop);
    window.voidcompassAtlas = {
      state: () => ({camera: {...cam.state}, selection: selection && {kind: selection.kind, name: selection.name || selection.subject, id: selection.id},
        systems: systems.size, regionsVisited: visits.size, currentRegion, layers: {...viewState.layers}, replay: replay.value,
        labels: [...labelPool.entries()].filter(([, el]) => el.style.opacity === '1').map(([key]) => key)}),
      project: (pos) => scene.project(pos, width, height),
      regionAt: (x, z) => regions.idAt(x, z),
    };
  } catch (error) {
    console.error(error);
    fail(`Could not start the map: ${error.message || error}`);
  }
}

start();
