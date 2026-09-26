const params = new URLSearchParams(location.search);
const token = params.get('token') || '';
const overlay = params.get('overlay') || 'navigation';
const api = (path) => `${path}?token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
const $ = (id) => document.getElementById(id);

const dom = Object.fromEntries([
  'hud', 'notice', 'state-tag', 'state-label', 'event-notice',
  'instrument', 'instrument-fill', 'instrument-marker', 'instrument-readout',
  'lamps', 'fuel-gauge', 'fuel-cells', 'metric-fuel',
  'vehicle-display', 'vehicle-image', 'vehicle-type', 'vehicle-name',
  'region-label', 'system-clock', 'current-system', 'current-star-orb', 'current-star-label',
  'route-block', 'route-title', 'route-target', 'route-target-label', 'route-star-orb', 'route-next', 'route-distance', 'route-progress',
  'route-pips', 'route-origin', 'route-destination', 'survey-block', 'survey-title',
  'route-star', 'route-feedback', 'route-fuel',
  'survey-title-text', 'survey-state', 'survey-mode', 'survey-remaining',
  'survey-count', 'survey-percent', 'survey-progress-marker',
  'survey-rail', 'survey-progress-fill', 'survey-acquisition', 'survey-signals',
  'survey-signal-bio', 'survey-signal-geo', 'survey-signal-mining', 'survey-signal-valuable',
  'context-label', 'secondary-label', 'traffic-label', 'link-state',
].map((id) => [id, $(id)]));

let snapshot = null;
let arrivalTimer = null;
let lastStateSignature = '';
let stateChangeTimer = null;
let vehicleImageTransition = null;
let lastServerContact = Date.now();
let lastRevision = -1;
let pageReady = false;
let healthPollActive = false;
let lastRouteSignature = '';
let routeMemory = null;
let routeFeedbackTimer = null;
let routeNoticeTimer = null;
let lastLampSignature = '';
let lastNoticeSequence = null;
let eventNoticeTimer = null;
const osMotionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');

function routeFeedback(message) {
  clearTimeout(routeFeedbackTimer);
  clearTimeout(routeNoticeTimer);
  dom['route-feedback'].textContent = message;
  briefHighlight(dom['route-feedback'], 'system-arrival');
  const routeBlock = dom['route-block'];
  routeBlock.classList.remove('route-notice');
  routeBlock.dataset.notice = message.startsWith('ARRIVED') ? 'arrived'
    : message === 'ROUTE CLEARED' ? 'cleared' : 'updated';
  if (!dom.hud.classList.contains('reduced-motion')) {
    void routeBlock.offsetWidth;
    routeBlock.classList.add('route-notice');
    routeNoticeTimer = setTimeout(() => routeBlock.classList.remove('route-notice'), 900);
  }
  routeFeedbackTimer = setTimeout(() => {
    dom['route-feedback'].textContent = '';
    routeFeedbackTimer = null;
  }, 4500);
}
let lastSurveyProgress = null;
let lastSurveySignature = '';

function colour(value, fallback) {
  return /^#[0-9a-f]{6}$/i.test(String(value || '')) ? value : fallback;
}

function setTheme(theme = {}) {
  const root = document.documentElement.style;
  const values = {
    accent: colour(theme.accent, '#00d1ff'), orange: colour(theme.orange, '#ff7a18'),
    green: colour(theme.green, '#4ee59b'), yellow: colour(theme.yellow, '#ffd166'),
    red: colour(theme.red, '#ff6075'), text: colour(theme.text, '#dce8ef'),
    muted: colour(theme.muted, '#85939d'), dim: colour(theme.dim, '#52616c'),
    bg: colour(theme.bg, '#070b10'), panel: colour(theme.panel, '#0d141c'),
    border: colour(theme.border, '#243746'), inset: colour(theme.inset, '#0a1118'),
  };
  for (const [key, value] of Object.entries(values)) root.setProperty(`--${key}`, value);
  root.setProperty('--text-scale', String(Math.max(.75, Math.min(2, Number(theme.text_scale || 1)))));
  return values;
}

function themedStateColour(value, theme) {
  const original = colour(value, theme.dim);
  return ({
    '#00d1ff': theme.accent,
    '#ff7a18': theme.orange,
    '#4ee59b': theme.green,
    '#ffd166': theme.yellow,
    '#7d8891': theme.dim,
  })[original.toLowerCase()] || original;
}

// Frontier supplies a class for the arrival star, not an image or a complete
// inventory of every star in the system. Keep unknown classes visually neutral.
function starFamily(value) {
  const code = String(value || '').trim().toUpperCase();
  if (!code) return 'unknown';
  if (['H', 'BH', 'SUPERMASSIVEBLACKHOLE'].includes(code)) return 'blackhole';
  if (['N', 'NS'].includes(code)) return 'neutron';
  if (code.startsWith('D')) return 'dwarf';
  if (code === 'TTS') return 'tauri';
  if (code === 'AEBE') return 'a';
  if (code.startsWith('W')) return 'wolf';
  if (code.startsWith('C')) return 'carbon';
  if (code.startsWith('S')) return 'm';
  if (code === 'X') return 'exotic';
  const primary = code[0].toLowerCase();
  return 'obafgkmlty'.includes(primary) ? primary : 'unknown';
}

function renderStarOrb(element, starClass) {
  const family = starFamily(starClass);
  const className = `star-orb star-${family}`;
  const title = starClass ? `Arrival star class ${starClass}` : 'Arrival star class unknown';
  if (element.className !== className) element.className = className;
  if (element.title !== title) element.title = title;
}

// ---------------------------------------------------------------------------
// Status plate. Elite's cockpit reports state with a few notice styles and the
// ship's own indicator lamps, so each state family gets one instrument band
// rather than a bespoke scene, and the band only draws journal-backed values.
// ---------------------------------------------------------------------------

const DISPLAY_LABELS = {
  FLIGHT: 'NORMAL SPACE',
  ONFOOT: 'ON FOOT',
  'MASS LOCK': 'MASS LOCKED',
  'FSD CHARGE': 'FSD CHARGING',
  'HYPER CHARGE': 'JUMP CHARGING',
  'SC ASSIST': 'SUPERCRUISE ASSIST',
  'ORBITAL APPROACH': 'ORBITAL CRUISE',
  'DOCK REQUEST': 'DOCKING REQUESTED',
  'DOCK CLEARED': 'DOCKING GRANTED',
  'DOCK DENIED': 'DOCKING DENIED',
  'DOCK CANCELLED': 'DOCKING CANCELLED',
  'DOCK TIMEOUT': 'DOCKING TIMED OUT',
  'DOCK ASSIST': 'DOCKING COMPUTER',
  HANDBRAKE: 'HANDBRAKE ON',
};

function displayLabel(label) {
  const text = String(label || 'FLIGHT').toUpperCase();
  const pad = /^PAD (\d+) CLEARED$/.exec(text);
  if (pad) return `DOCKING GRANTED · PAD ${pad[1]}`;
  return DISPLAY_LABELS[text] || text;
}

const SURFACE_MOTIONS = new Set(['surface_vehicle', 'srv_handbrake', 'srv_turret', 'srv_drive_assist']);

function stateTag(state = {}) {
  const category = String(state.category || 'flight');
  const motion = String(state.motion || 'flight');
  const label = String(state.label || '').toUpperCase();
  if (category === 'drive') return motion.startsWith('carrier_') ? 'CARRIER' : 'FSD';
  if (category === 'vehicle') {
    if (SURFACE_MOTIONS.has(motion)) return 'SRV';
    if (motion === 'fighter') return 'FIGHTER';
    if (motion === 'on_foot' || motion === 'carrier_deck') return 'SUIT';
    if (label === 'TAXI') return 'PASSENGER';
    if (label === 'MULTICREW') return 'CREW';
    return 'VEHICLE';
  }
  if (category === 'scan') return motion === 'map' ? 'MAP' : motion === 'target_lock' ? 'TARGET' : 'SENSORS';
  return ({
    restrict: 'CAUTION', alert: 'WARNING', planet: 'PLANETARY',
    dock: 'DOCKING', panel: 'COCKPIT',
  })[category] || 'SHIP';
}

const FLOW_VARIANTS = {
  fsd_charge: 'charge', jump: 'jump', supercruise: 'cruise', supercruise_assist: 'cruise',
  supercruise_overcharge: 'overcharge', arrival: 'arrive', local_arrival: 'arrive',
  fsd_cooldown: 'cool', carrier_preparing: 'carrier', carrier_lockdown: 'carrier',
  carrier_transit: 'jump', carrier_arrival: 'arrive',
};

function finite(value) {
  return value != null && value !== '' && Number.isFinite(Number(value));
}

function instrumentFor(state = {}) {
  const category = String(state.category || 'flight');
  const motion = String(state.motion || 'flight');
  const dynamics = state.dynamics || {};
  if (category === 'drive') return {kind: 'flow', variant: FLOW_VARIANTS[motion] || 'cruise'};
  if (category === 'alert') return {kind: 'alert'};
  if (category === 'restrict') return {kind: 'lock'};
  if (category === 'planet' && finite(dynamics.altitude_m) && Number(dynamics.altitude_m) >= 0) {
    return {kind: 'altimeter'};
  }
  if (motion === 'scanner' && String(state.label || '').toUpperCase() === 'FSS') return {kind: 'scan'};
  return {kind: 'idle'};
}

// 10 m to 200 km on a log scale: the whole descent from orbital cruise to the
// pad reads on one bar, and the last few hundred metres still move visibly.
function altimeterPosition(altitude) {
  const metres = Math.max(10, Number(altitude) || 0);
  return Math.max(0, Math.min(1, Math.log10(metres / 10) / Math.log10(20000)));
}

function formatAltitude(altitude) {
  const metres = Math.max(0, Number(altitude) || 0);
  if (metres >= 100000) return `${Math.round(metres / 1000)} KM`;
  if (metres >= 1000) return `${(metres / 1000).toFixed(1)} KM`;
  return `${Math.round(metres)} M`;
}

function instrumentReadout(state, instrument) {
  const dynamics = state.dynamics || {};
  if (instrument.kind === 'flow') {
    if (dynamics.neutron_boost) {
      const boost = Number(dynamics.neutron_boost_value) || 0;
      return boost > 0 ? `SUPERCHARGED ×${boost.toFixed(1)}` : 'FSD SUPERCHARGED';
    }
    if (dynamics.fsd_injection) {
      const amount = Math.round(Number(dynamics.fsd_injection_percent) || 0);
      return amount > 0 ? `INJECTION +${amount}%` : 'FSD INJECTION';
    }
    return '';
  }
  if (instrument.kind === 'altimeter') {
    const parts = [`ALT ${formatAltitude(dynamics.altitude_m)}`];
    const vertical = Number(dynamics.vertical_mps) || 0;
    if (vertical > 1) parts.push(`▼ ${Math.round(vertical)} M/S`);
    else if (vertical < -1) parts.push(`▲ ${Math.round(-vertical)} M/S`);
    const gravity = Number(dynamics.gravity_g) || 0;
    if (gravity > 0) parts.push(`${gravity.toFixed(2)} G`);
    return parts.join('  ');
  }
  if (instrument.kind === 'scan') return `${Math.round(Math.max(0, Math.min(1, Number(dynamics.scan_percent) || 0)) * 100)}%`;
  if (state.category === 'planet') {
    const gravity = Number(dynamics.gravity_g) || 0;
    return gravity > 0 ? `${gravity.toFixed(2)} G` : '';
  }
  return '';
}

function renderInstrument(state) {
  const instrument = instrumentFor(state);
  const host = dom.instrument;
  const dynamics = state.dynamics || {};
  host.dataset.instrument = instrument.kind;
  if (instrument.variant) host.dataset.variant = instrument.variant;
  else delete host.dataset.variant;
  host.classList.toggle('supercharged', instrument.kind === 'flow'
    && Boolean(dynamics.neutron_boost || dynamics.fsd_injection));
  let fill = 0;
  let marker = null;
  if (instrument.kind === 'altimeter') {
    marker = altimeterPosition(dynamics.altitude_m);
    fill = marker;
    const vertical = Number(dynamics.vertical_mps) || 0;
    host.dataset.vertical = vertical > 1 ? 'down' : vertical < -1 ? 'up' : 'hold';
  } else {
    delete host.dataset.vertical;
  }
  if (instrument.kind === 'scan') {
    fill = Math.max(0, Math.min(1, Number(dynamics.scan_percent) || 0));
    marker = fill;
  }
  dom['instrument-fill'].style.transform = `scaleX(${fill})`;
  dom['instrument-marker'].hidden = marker == null;
  if (marker != null) dom['instrument-marker'].style.left = `${(marker * 100).toFixed(2)}%`;
  dom['instrument-readout'].textContent = instrumentReadout(state, instrument);
  return instrument;
}

// The ship's own indicator lamps, lit only while engaged. A lamp that merely
// repeats the state notice (SILENT RUNNING shown as SILENT RUNNING) is omitted.
function lampsFor(state = {}) {
  const dynamics = state.dynamics || {};
  const label = String(state.label || '').toUpperCase();
  const motion = String(state.motion || '');
  if (SURFACE_MOTIONS.has(motion)) {
    return [
      ['HANDBRAKE', dynamics.srv_handbrake, 'caution', 'HANDBRAKE'],
      ['TURRET', dynamics.srv_turret, 'info', 'TURRET VIEW'],
      ['DRIVE ASSIST', dynamics.srv_drive_assist, 'info', 'DRIVE ASSIST'],
      ['NIGHT VISION', dynamics.night_vision, 'info', ''],
    ].filter(([, on, , owner]) => on && owner !== label)
      .map(([text, , tone]) => ({text, tone}));
  }
  if (state.category === 'vehicle' || !dynamics.in_main_ship) return [];
  const lamps = [{
    text: dynamics.analysis_mode ? 'ANALYSIS' : 'COMBAT',
    tone: dynamics.analysis_mode ? 'info' : 'hud',
    mode: true,
  }];
  for (const [text, on, tone, owner] of [
    ['SHIELDS DOWN', dynamics.shields_known && !dynamics.shields_up, 'danger', ''],
    ['HEAT', dynamics.overheating, 'danger', 'HEAT CRITICAL'],
    ['LOW FUEL', dynamics.low_fuel, 'danger', ''],
    ['HARDPOINTS', dynamics.hardpoints_deployed, 'hud', ''],
    ['GEAR', dynamics.landing_gear, 'hud', ''],
    ['CARGO SCOOP', dynamics.cargo_scoop, 'hud', ''],
    ['FUEL SCOOPING', dynamics.fuel_scooping, 'good', ''],
    ['SILENT RUNNING', dynamics.silent_running, 'caution', 'SILENT RUNNING'],
    ['FA OFF', dynamics.flight_assist_off, 'caution', 'FLIGHT ASSIST OFF'],
    ['SC ASSIST', dynamics.supercruise_assist, 'info', 'SC ASSIST'],
    ['NIGHT VISION', dynamics.night_vision, 'info', ''],
  ]) {
    if (on && owner !== label) lamps.push({text, tone});
  }
  return lamps;
}

function renderLamps(state) {
  const lamps = lampsFor(state);
  const signature = JSON.stringify(lamps);
  if (signature === lastLampSignature) return lamps;
  lastLampSignature = signature;
  const host = dom.lamps;
  host.replaceChildren(...lamps.map((lamp) => {
    const node = document.createElement('span');
    node.className = `lamp tone-${lamp.tone}${lamp.mode ? ' mode' : ''}`;
    node.textContent = lamp.text;
    return node;
  }));
  return lamps;
}

const FUEL_CELLS = 10;

function renderFuel(fuel = {}, dynamics = {}, theme = {}) {
  const gauge = dom['fuel-gauge'];
  const cells = dom['fuel-cells'];
  if (cells.children.length !== FUEL_CELLS) {
    cells.replaceChildren(...Array.from({length: FUEL_CELLS}, () => document.createElement('i')));
  }
  const percent = finite(fuel?.percent) ? Math.max(0, Math.min(100, Number(fuel.percent))) : null;
  const lit = percent == null ? 0 : Math.ceil(percent / (100 / FUEL_CELLS));
  [...cells.children].forEach((cell, index) => cell.classList.toggle('lit', index < lit));
  dom['metric-fuel'].textContent = percent == null ? '--' : `${Math.round(percent)}%`;
  gauge.style.setProperty('--fuel-tone', percent == null
    ? 'var(--dim)' : themedStateColour(fuel?.color, theme));
  gauge.classList.toggle('unknown', percent == null);
  gauge.classList.toggle('scooping', Boolean(dynamics.fuel_scooping));
}

function renderEventNotice(notice, theme, reducedMotion) {
  const node = dom['event-notice'];
  if (!notice || notice.seq == null) return;
  if (lastNoticeSequence === null) {
    // A notice already live when the page loaded is still worth showing, but
    // only once: later snapshots repeat the same sequence until it expires.
    lastNoticeSequence = notice.seq;
  } else if (notice.seq === lastNoticeSequence) {
    return;
  }
  lastNoticeSequence = notice.seq;
  const tone = ['accent', 'green', 'yellow', 'orange', 'red'].includes(notice.tone) ? notice.tone : 'accent';
  node.textContent = notice.detail ? `${notice.text} · ${notice.detail}` : notice.text;
  node.style.setProperty('--event-tone', `var(--${tone})`);
  node.classList.remove('showing');
  if (!reducedMotion) void node.offsetWidth;
  node.classList.add('showing');
  clearTimeout(eventNoticeTimer);
  eventNoticeTimer = setTimeout(() => {
    node.classList.remove('showing');
    eventNoticeTimer = null;
  }, Math.max(1000, Number(notice.duration || 2.4) * 1000));
}

function renderStatus(data, theme, reducedMotion) {
  const state = data.state || {};
  const hud = dom.hud;
  const category = String(state.category || 'flight');
  const label = String(state.label || 'FLIGHT').toUpperCase();
  hud.dataset.motion = state.motion || 'flight';
  hud.dataset.state = label;
  hud.dataset.category = category;
  const tone = category === 'alert' ? theme.red : themedStateColour(state.color, theme);
  hud.style.setProperty('--state', tone);
  dom['state-tag'].textContent = stateTag(state);
  dom['state-label'].textContent = displayLabel(label);
  const signature = `${category}|${label}`;
  if (lastStateSignature && signature !== lastStateSignature && !reducedMotion) {
    hud.classList.remove('state-changing');
    void dom.notice.offsetWidth;
    hud.classList.add('state-changing');
    clearTimeout(stateChangeTimer);
    stateChangeTimer = setTimeout(() => {
      hud.classList.remove('state-changing');
      stateChangeTimer = null;
    }, 420);
  }
  lastStateSignature = signature;
  renderInstrument(state);
  renderLamps(state);
  renderFuel(data.metrics?.fuel, state.dynamics || {}, theme);
  renderEventNotice(state.notice, theme, reducedMotion);
}

// ---------------------------------------------------------------------------
// Ship hologram. The catalogue portraits are kept; only their framing changed.
// ---------------------------------------------------------------------------

function vehiclePresentation(state = {}) {
  const motion = String(state.motion || 'flight');
  const label = String(state.label || 'FLIGHT').toUpperCase();
  const vehicle = state.vehicle || {};
  const catalog = window.VoidCompassShipCatalog;
  const surfaceControl = [
    'srv_handbrake', 'srv_turret', 'srv_drive_assist',
  ].includes(motion);
  if (motion.startsWith('carrier_')) {
    return catalog.carrier();
  }
  if (motion === 'on_foot' || label === 'ONFOOT' || label === 'ON FOOT') {
    return catalog.onFoot();
  }
  if (motion === 'surface_vehicle' || motion.startsWith('vehicle_') || surfaceControl) {
    if (label.includes('NOMAD') || String(vehicle.surface || '').toUpperCase() === 'NOMAD') {
      return catalog.resolveSurface('NOMAD');
    }
    if (!surfaceControl && label.includes('FIGHTER')) {
      return catalog.fighter();
    }
    if (label.includes('SRV') || label.includes('SCARAB') || label.includes('SCORPION')
        || label.includes('RHINO') || vehicle.surface || surfaceControl) {
      const surface = label.includes('SCORPION') ? 'SCORPION'
        : label.includes('RHINO') ? 'RHINO'
          : label.includes('SCARAB') ? 'SCARAB' : (vehicle.surface || 'SRV');
      return catalog.resolveSurface(surface);
    }
  }
  if (motion === 'fighter' || label === 'FIGHTER') {
    return catalog.fighter();
  }
  return catalog.resolveShip(vehicle);
}

function clearVehicleTransition(host, image) {
  if (vehicleImageTransition) {
    vehicleImageTransition.cancel();
    vehicleImageTransition = null;
  }
  host.classList.remove('vehicle-swapping');
  host.querySelectorAll('.vehicle-outgoing').forEach((ghost) => ghost.remove());
  image.style.removeProperty('opacity');
  image.style.removeProperty('transform');
  image.style.removeProperty('filter');
}

function animateVehicleSwap(host, image, presentation) {
  const bay = image.parentElement;
  const bayRect = bay.getBoundingClientRect();
  const imageRect = image.getBoundingClientRect();
  const computed = getComputedStyle(image);
  const ghost = image.cloneNode(false);
  ghost.removeAttribute('id');
  ghost.className = 'vehicle-outgoing';
  ghost.alt = '';
  ghost.setAttribute('aria-hidden', 'true');
  ghost.style.left = `${imageRect.left - bayRect.left}px`;
  ghost.style.top = `${imageRect.top - bayRect.top}px`;
  ghost.style.width = `${imageRect.width}px`;
  ghost.style.height = `${imageRect.height}px`;
  ghost.style.opacity = computed.opacity;
  ghost.style.filter = computed.filter;
  bay.appendChild(ghost);

  host.classList.add('vehicle-swapping');
  host.dataset.vehicle = presentation.key;
  image.alt = presentation.alt;
  image.src = presentation.src;

  const outgoing = ghost.animate([
    {opacity: Number(computed.opacity) || 1, transform: 'translateX(0) scale(1)'},
    {opacity: .42, transform: 'translateX(-3px) scale(.985)', offset: .45},
    {opacity: 0, transform: 'translateX(-9px) scale(.95)'},
  ], {duration: 430, easing: 'cubic-bezier(.3,.05,.35,1)', fill: 'forwards'});
  vehicleImageTransition = image.animate([
    {opacity: 0, transform: 'translateX(9px) scale(.95)', filter: 'brightness(1.7) blur(.8px)'},
    {opacity: .55, transform: 'translateX(3px) scale(.985)', filter: 'brightness(1.5) blur(0)', offset: .48},
    {opacity: 1, transform: 'translateX(0) scale(1)', filter: computed.filter},
  ], {duration: 520, easing: 'cubic-bezier(.2,.75,.2,1)'});
  outgoing.onfinish = () => ghost.remove();
  vehicleImageTransition.onfinish = () => {
    vehicleImageTransition = null;
    host.classList.remove('vehicle-swapping');
  };
}

function vehicleCaption(state = {}, presentation = null) {
  const vehicle = state.vehicle || {};
  const type = String(presentation?.name || vehicle.ship_type || '').toUpperCase();
  const name = String(vehicle.ship_name || '').trim().toUpperCase();
  const ownShip = presentation && !['fighter', 'onfoot', 'carrier', 'nomad', 'scarab', 'scorpion', 'rhino']
    .includes(presentation.key);
  return {type: type || (ownShip ? 'SHIP' : ''), name: ownShip && name !== type ? name : ''};
}

function renderVehicle(state = {}, reducedMotion = false) {
  const presentation = vehiclePresentation(state);
  const host = dom['vehicle-display'];
  const image = dom['vehicle-image'];
  const caption = vehicleCaption(state, presentation);
  dom['vehicle-type'].textContent = caption.type;
  dom['vehicle-name'].textContent = caption.name;
  if (reducedMotion) clearVehicleTransition(host, image);
  if (!presentation) {
    clearVehicleTransition(host, image);
    host.classList.add('empty');
    image.removeAttribute('src');
    image.alt = '';
    return null;
  }
  host.classList.remove('empty');
  const previousSrc = image.getAttribute('src') || '';
  if (previousSrc && previousSrc !== presentation.src && !reducedMotion
      && typeof image.animate === 'function') {
    clearVehicleTransition(host, image);
    animateVehicleSwap(host, image, presentation);
  } else {
    host.dataset.vehicle = presentation.key;
    image.alt = presentation.alt;
    if (previousSrc !== presentation.src) image.src = presentation.src;
  }
  return presentation;
}

// ---------------------------------------------------------------------------
// Route and survey
// ---------------------------------------------------------------------------

function renderRoute(route = {}, systemName = '') {
  const hops = Array.isArray(route.hops) ? route.hops : [];
  const names = JSON.stringify(hops.map(hop => hop.name));
  const present = Boolean(route.active || route.complete || hops.length);
  dom['route-block'].dataset.routeState = route.complete ? 'complete' : present ? 'active' : 'empty';
  const arrived = Boolean(routeMemory && systemName && routeMemory.systemName
    && systemName !== routeMemory.systemName);
  if (routeMemory) {
    if (arrived) routeFeedback(`ARRIVED · ${systemName}`);
    else if (routeMemory.present && !present) routeFeedback('ROUTE CLEARED');
    else if (present && (!routeMemory.present || names !== routeMemory.names || route.source !== routeMemory.source)) routeFeedback('ROUTE UPDATED');
  }
  routeMemory = {names, present, source: route.source, systemName};
  const star = route.next_star || {};
  const nextHop = hops.find(hop => hop.next);
  const starClass = route.complete ? (hops.at(-1)?.star_class || '')
    : route.active ? (star.star_class || nextHop?.star_class || '') : '';
  const scoopable = star.star_class ? star.scoopable : nextHop?.scoopable;
  renderStarOrb(dom['route-star-orb'], starClass);
  const classKnown = Boolean(starClass && route.active && !route.complete);
  dom['route-star'].textContent = classKnown
    ? `${starClass} · ${scoopable === true ? 'SCOOPABLE' : scoopable === false ? 'NON-SCOOP' : 'SCOOP UNKNOWN'}`
    : route.active && !route.complete ? 'STAR UNKNOWN' : '';
  dom['route-star'].classList.toggle('unscoopable', scoopable === false && classKnown);
  const endurance = route.fuel_endurance_jumps;
  const estimated = typeof endurance === 'number' && Number.isFinite(endurance) && endurance >= 0;
  dom['route-fuel'].textContent = route.active && !route.complete
    ? estimated ? `EST. FUEL ${endurance} JUMPS${endurance <= 1 ? ' · REFUEL' : ''}` : 'FUEL RANGE UNKNOWN' : '';
  dom['route-fuel'].classList.toggle('fuel-caution', estimated && endurance <= 2);
  dom['route-fuel'].title = 'Estimate based on recent fuel use, not a verified range or next-jump fuel calculation.';
  const previousSignature = lastRouteSignature;
  const previousProgress = Number(dom['route-progress'].dataset.progress || 0);
  const signature = JSON.stringify([
    route.target, route.source, route.progress_text, route.leg_distance, route.remaining_distance, route.complete,
    route.header || '', route.next_distance || '', route.distance || '',
    Boolean(route.active), route.origin_current === false ? 'start' : 'current',
    Number(route.progress_percent || 0),
    hops.map((hop) => [hop.position, hop.completed, hop.current, hop.next, hop.scoopable, hop.star_class, hop.name]),
  ]);
  if (signature === lastRouteSignature) return;
  lastRouteSignature = signature;
  const target = route.target || hops.find(hop => hop.next)?.name || '';
  dom['route-target-label'].textContent = route.complete ? 'ARRIVED' : route.source === 'waypoints' ? 'NEXT STOP' : 'NEXT JUMP';
  dom['route-target'].textContent = target || (route.active ? 'DESTINATION PENDING' : 'NO DESTINATION PLOTTED');
  const done = hops.filter(hop => hop.completed || hop.current).length;
  if (previousSignature && arrived) briefHighlight(dom['route-target'], 'target-promoted');
  const nextIndex = hops.findIndex(hop => hop.next);
  const progressLabel = hops.length ? `${route.source === 'waypoints' ? 'STOP' : 'JUMP'} ${route.complete ? hops.length : nextIndex >= 0 ? nextIndex + 1 : Math.min(done + 1, hops.length)} / ${hops.length}` : '';
  // With nothing plotted the target line already says so; a stale count
  // from an earlier route must not linger beside it.
  dom['route-title'].textContent = route.complete ? 'ROUTE COMPLETE'
    : present ? progressLabel || route.progress_text || route.header || '' : '';
  const distance = value => value && !['--', 'None'].includes(String(value)) ? String(value) : '—';
  dom['route-next'].textContent = route.active && !route.complete ? distance(route.leg_distance ?? route.next_distance) : '';
  dom['route-distance'].textContent = route.active && !route.complete ? `${distance(route.remaining_distance ?? route.distance)} LEFT` : '';
  dom['route-origin'].textContent = route.origin_current === false ? 'START' : 'HERE';
  dom['route-destination'].textContent = route.active || route.hops?.length ? 'DEST' : 'NEXT';
  dom['route-progress'].style.width = `${hops.length ? done / hops.length * 100 : 0}%`;
  dom['route-progress'].dataset.progress = String(route.progress_percent || 0);
  if (previousSignature && Number(route.progress_percent || 0) > previousProgress) {
    briefHighlight(dom['route-progress'], 'route-arrival');
  }
  const host = dom['route-pips'];
  host.className = `route-pips unified${hops.length > 48 ? ' ultra-dense' : hops.length > 18 ? ' dense' : ''}`;
  host.setAttribute('aria-label', `${hops.length} waypoints; ${hops.filter(hop => hop.completed).length} completed`);
  // Equal slots preserve every stop, including coincident/distant route positions.
  // Reuse nodes so distance updates do not restart the next-leg animation.
  while (host.children.length > hops.length) host.lastElementChild.remove();
  for (const [index, hop] of hops.entries()) {
    const segment = host.children[index] || document.createElement('i');
    const family = starFamily(hop.star_class);
    segment.className = [
      'route-segment', `star-${family}`, family !== 'unknown' && 'known-star',
      hop.completed && 'completed', hop.current && 'current',
      hop.next && 'next', hop.scoopable === false && 'unscoopable',
    ].filter(Boolean).join(' ');
    segment.style.left = `${index / hops.length * 100}%`;
    segment.style.width = `${100 / hops.length}%`;
    segment.title = `${index + 1}. ${hop.name || 'Unknown'}${hop.current ? ' · current' : hop.next ? ' · next' : hop.completed ? ' · completed' : ''} · ${hop.star_class ? `star class ${hop.star_class}` : 'star class unknown'}${hop.scoopable === false ? ' · unscoopable' : ''}`;
    if (!segment.firstElementChild) {
      const waypoint = document.createElement('b');
      waypoint.setAttribute('aria-hidden', 'true');
      segment.appendChild(waypoint);
      host.appendChild(segment);
    }
  }
}

function renderSurvey(survey = {}, theme = {}, systemName = '', reducedMotion = false, bioProgress = '') {
  const state = ['unknown', 'live', 'retained', 'complete'].includes(String(survey.state))
    ? String(survey.state) : (survey.complete ? 'complete' : survey.live ? 'live' : 'unknown');
  const scanned = Math.max(0, Number.parseInt(survey.scanned, 10) || 0);
  const total = Math.max(0, Number.parseInt(survey.total, 10) || 0);
  const totalKnown = survey.total_known !== false && state !== 'unknown';
  const percent = Math.max(0, Math.min(100, Number(survey.percent || 0)));
  const rawSignals = survey.signals || {};
  const signalCounts = Object.fromEntries(['bio', 'geo', 'mining', 'valuable'].map((kind) => [
    kind, Math.max(0, Number.parseInt(rawSignals[kind], 10) || 0),
  ]));
  const tone = survey.tone
    ? themedStateColour(survey.tone, theme)
    : (state === 'unknown' ? (theme.dim || 'var(--dim)') : (theme.accent || 'var(--accent)'));
  // Show organic progress (logged/found) once any biology is known.
  const bioText = signalCounts.bio > 0 && /^\d+\/\d+$/.test(String(bioProgress)) ? String(bioProgress) : String(signalCounts.bio);
  const signature = JSON.stringify([
    systemName, state, scanned, total, totalKnown, Math.round(percent * 100) / 100,
    signalCounts.bio, signalCounts.geo, signalCounts.mining, signalCounts.valuable, tone, reducedMotion, bioText,
  ]);
  if (signature === lastSurveySignature) return;

  const block = dom['survey-block'];
  const previous = lastSurveyProgress;
  const sameSystem = Boolean(previous && previous.systemName === systemName);
  const progressed = Boolean(sameSystem && totalKnown && (
    scanned > previous.scanned || percent > previous.percent
  ));
  block.dataset.surveyState = state;
  block.style.setProperty('--survey-tone', tone);
  dom['survey-title-text'].textContent = state === 'complete'
    ? 'SURVEY COMPLETE' : 'SYSTEM SURVEY';
  const remaining = totalKnown ? Math.max(0, total - scanned) : null;
  const modeLabels = {
    unknown: 'COUNT UNKNOWN', live: 'LIVE FSS', retained: 'RECORDED', complete: '',
  };
  dom['survey-mode'].textContent = modeLabels[state];
  dom['survey-remaining'].textContent = state !== 'complete' && remaining > 0
    ? `${remaining} REMAIN` : '';
  dom['survey-count'].textContent = `${scanned} / ${totalKnown ? total : '?'} BODIES`;
  dom['survey-percent'].textContent = totalKnown ? `${Math.round(percent)}%` : '--%';

  const host = dom['survey-rail'];
  const segmentCount = totalKnown && total > 0 && total <= 24 ? total : (total > 24 ? 24 : 12);
  const progressRatio = totalKnown ? percent / 100 : 0;
  const markerPosition = Math.max(1, Math.min(99, percent));
  host.style.setProperty('--survey-tick', `${100 / Math.max(1, segmentCount)}%`);
  host.style.setProperty('--survey-progress', String(progressRatio));
  host.style.setProperty('--survey-head', `${markerPosition}%`);
  host.classList.toggle('resetting', !sameSystem);
  dom['survey-progress-fill'].style.transform = `scaleX(${progressRatio})`;
  const marker = dom['survey-progress-marker'];
  marker.style.left = `${markerPosition}%`;
  marker.classList.toggle('unavailable', !totalKnown);
  marker.classList.toggle('complete', state === 'complete');
  dom['survey-acquisition'].style.left = `${markerPosition}%`;
  if (!sameSystem) requestAnimationFrame(() => host.classList.remove('resetting'));

  const animatedNodes = [dom['survey-acquisition'], marker, dom['survey-count']];
  if (reducedMotion) {
    for (const node of animatedNodes) node.getAnimations?.().forEach((animation) => animation.cancel());
  } else if (progressed && typeof dom['survey-acquisition'].animate === 'function') {
    dom['survey-acquisition'].getAnimations().forEach((animation) => animation.cancel());
    marker.getAnimations().forEach((animation) => animation.cancel());
    dom['survey-count'].getAnimations().forEach((animation) => animation.cancel());
    dom['survey-acquisition'].animate([
      {opacity: 0, transform: 'translate(-50%,-50%) scaleX(.25)'},
      {opacity: .95, transform: 'translate(-50%,-50%) scaleX(1.5)', offset: .34},
      {opacity: .42, transform: 'translate(-50%,-50%) scaleX(.72)', offset: .64},
      {opacity: 0, transform: 'translate(-50%,-50%) scaleX(1.08)'},
    ], {duration: 620, easing: 'cubic-bezier(.16,.78,.2,1)'});
    marker.animate([
      {filter: 'brightness(1)', transform: 'translateX(-50%) scaleY(.45)'},
      {filter: 'brightness(2.25)', transform: 'translateX(-50%) scaleY(1.35)', offset: .38},
      {filter: 'brightness(1)', transform: 'translateX(-50%) scaleY(1)'},
    ], {duration: 540, easing: 'cubic-bezier(.16,.78,.2,1)'});
    dom['survey-count'].animate([
      {color: tone, textShadow: 'none'},
      {color: theme.text || '#dce8ef', textShadow: `0 0 7px ${tone}`, offset: .38},
      {color: tone, textShadow: 'none'},
    ], {duration: 520, easing: 'ease-out'});
  }

  const signalHost = dom['survey-signals'];
  let visibleSignals = 0;
  for (const [kind, title] of [
    ['bio', 'Biological signals'],
    ['geo', 'Geological signals'],
    ['mining', 'Planetary mining locations'],
    ['valuable', 'High-value bodies'],
  ]) {
    const count = signalCounts[kind];
    const alert = dom[`survey-signal-${kind}`];
    alert.querySelector('em').textContent = kind === 'bio' ? bioText : String(count);
    alert.title = `${title}: ${count}`;
    alert.setAttribute('aria-label', `${title}: ${count}`);
    alert.classList.toggle('present', count > 0);
    if (count > 0) visibleSignals += 1;
    const signalFound = Boolean(sameSystem
      && count > Number(previous?.signals?.[kind] || 0));
    if (signalFound && !reducedMotion && typeof alert.animate === 'function') {
      alert.getAnimations().forEach((animation) => animation.cancel());
      alert.animate([
        {opacity: .18, transform: 'scale(.72)', filter: 'brightness(1)'},
        {opacity: 1, transform: 'scale(1.12)', filter: 'brightness(2.25)', offset: .34},
        {opacity: 1, transform: 'scale(1)', filter: 'brightness(1)'},
      ], {duration: 680, easing: 'cubic-bezier(.16,.78,.2,1)'});
    }
  }
  signalHost.classList.toggle('has-signals', visibleSignals > 0);
  lastSurveyProgress = {systemName, scanned, total, percent, state, signals: signalCounts};
  lastSurveySignature = signature;
}

function formatClock(epoch) {
  const arrival = Number(epoch || 0);
  if (!Number.isFinite(arrival) || arrival <= 0) return '--:--';
  const elapsed = Math.max(0, Date.now() / 1000 - arrival);
  const hours = Math.floor(elapsed / 3600);
  const minutes = Math.floor(elapsed % 3600 / 60);
  const seconds = Math.floor(elapsed % 60);
  return hours ? `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
    : `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function updateClock() {
  dom['system-clock'].textContent = formatClock(snapshot?.system?.arrival_epoch);
}

// Event highlights settle automatically; ordinary telemetry refreshes do not
// restart them. The drive band is the only sustained animation.
const highlightTimers = new WeakMap();
function briefHighlight(element, className) {
  if (dom.hud.classList.contains('reduced-motion')) return;
  clearTimeout(highlightTimers.get(element));
  element.classList.remove(className);
  void element.offsetWidth;
  element.classList.add(className);
  highlightTimers.set(element, setTimeout(() => element.classList.remove(className), 1600));
}
let lastSystemName = '';
let lastAttentionText = '';

function render(data) {
  if (!data || data.schema !== 1) return;
  snapshot = data;
  const overlayOpacity = Number(data.effects?.opacity);
  document.body.style.opacity = String(Number.isFinite(overlayOpacity)
    ? Math.max(.4, Math.min(1, overlayOpacity)) : 1);
  const theme = setTheme(data.theme);
  const hud = dom.hud;
  const expanded = data.layout === 'expanded';
  hud.classList.toggle('standard', !expanded);
  hud.classList.toggle('expanded', expanded);
  hud.classList.toggle('no-crt', !data.effects?.crt);
  // A hidden overlay keeps its state but stops spending frames on it.
  hud.classList.toggle('dormant', data.window?.visible === false);
  const reducedMotion = Boolean(data.effects?.reduced_motion || osMotionPreference.matches);
  const enteringReducedMotion = reducedMotion && !hud.classList.contains('reduced-motion');
  hud.classList.toggle('reduced-motion', reducedMotion);
  if (enteringReducedMotion) {
    for (const className of ['route-arrival', 'system-arrival', 'target-promoted', 'context-attention']) {
      hud.querySelectorAll(`.${className}`).forEach((node) => node.classList.remove(className));
    }
    dom['route-block'].classList.remove('route-notice');
    hud.classList.remove('state-changing');
    clearTimeout(routeNoticeTimer);
  }
  const energy = Math.max(.55, Math.min(1.6, Number(data.effects?.energy || 1)));
  hud.style.setProperty('--motion-scale', String(1 / energy));
  renderVehicle(data.state, reducedMotion);
  renderStatus(data, theme, reducedMotion);
  const system = data.system || {};
  if (lastSystemName && system.name && lastSystemName !== system.name) briefHighlight(dom['current-system'], 'system-arrival');
  lastSystemName = system.name || '';
  dom['current-system'].textContent = system.name || '---';
  const currentStarClass = String(system.star_class || '').trim();
  renderStarOrb(dom['current-star-orb'], currentStarClass);
  dom['current-star-label'].textContent = currentStarClass ? `STAR ${currentStarClass.toUpperCase()}` : 'STAR ?';
  dom['current-star-label'].title = currentStarClass ? `Known local star class ${currentStarClass}` : 'Local star class unknown';
  dom['region-label'].textContent = system.region || 'REGION UNKNOWN';
  hud.classList.toggle('surface-focus', Boolean(data.context?.surface));
  renderRoute(data.route, system.name || '');
  const metrics = data.metrics || {};
  renderSurvey(data.survey, theme, system.name || '', reducedMotion, metrics.bio?.value);
  dom['context-label'].textContent = data.context?.primary || '';
  dom['context-label'].style.color = themedStateColour(data.context?.primary_color, theme);
  dom['secondary-label'].textContent = expanded ? (data.context?.secondary || '') : '';
  dom['secondary-label'].style.color = themedStateColour(data.context?.secondary_color, theme);
  dom['traffic-label'].textContent = expanded && metrics.traffic?.value
    ? `TRAFFIC ${metrics.traffic.value}` : (data.context?.traffic || '');
  const attentionText = ['alert', 'warn', 'warning'].includes(data.context?.attention)
    ? [data.context?.primary, data.context?.secondary].filter(Boolean).join('|') : '';
  if (attentionText && attentionText !== lastAttentionText) briefHighlight(dom['context-label'], 'context-attention');
  lastAttentionText = attentionText;
  updateClock();
  // A running CSS transition can outlive a just-enabled reduced-motion rule.
  // Stop those in-flight effects as well as preventing new ones.
  if (reducedMotion) hud.getAnimations({subtree: true}).forEach((animation) => animation.cancel());
}

async function fetchSnapshot() {
  const response = await fetch(api('/api/snapshot'), {cache: 'no-store'});
  if (!response.ok) throw new Error(`Snapshot HTTP ${response.status}`);
  lastServerContact = Date.now();
  return response.json();
}

async function acknowledgeRendered(revision) {
  try {
    const response = await fetch(api('/api/rendered'), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({revision}),
    });
    return response.ok;
  } catch (_error) {
    return false;
  }
}

async function acknowledgeReady() {
  if (pageReady || lastRevision < 0) return;
  try {
    const response = await fetch(api('/api/ready'), {
      method: 'POST', body: '{}',
    });
    pageReady = response.ok;
  } catch (_error) {}
}

async function checkHostHealth() {
  if (healthPollActive) return;
  healthPollActive = true;
  try {
    const response = await fetch(api('/api/health'), {cache: 'no-store'});
    if (!response.ok) throw new Error(`Health HTTP ${response.status}`);
    const health = await response.json();
    lastServerContact = Date.now();
    const revision = Number(health.revision);
    pageReady = pageReady || Boolean(health.ready);
    if (Number.isFinite(revision) && revision !== lastRevision) {
      render(await fetchSnapshot());
      if (await acknowledgeRendered(revision)) {
        lastRevision = revision;
        await acknowledgeReady();
        dom['link-state'].textContent = 'HTML NAV // LIVE';
      }
    } else if (!pageReady) {
      await acknowledgeReady();
    }
  } catch (_error) {
    if (Date.now() - lastServerContact > 15000) {
      dom['link-state'].textContent = 'HTML NAV // HOST OFFLINE';
    }
  } finally {
    healthPollActive = false;
  }
}

async function start() {
  if (!token) return;
  await checkHostHealth();
  if (lastRevision < 0) dom['link-state'].textContent = 'HTML NAV // RETRYING';
  arrivalTimer = setInterval(updateClock, 1000);
  // One EventSource per overlay can exhaust WebView2's HTTP/1.1 connection
  // pool. Revision checks transfer no model when unchanged and keep this
  // primary flight instrument responsive without a permanent connection.
  setInterval(checkHostHealth, 250);
}

window.addEventListener('beforeunload', () => {
  clearTimeout(routeFeedbackTimer);
  clearTimeout(routeNoticeTimer);
  clearTimeout(eventNoticeTimer);
  if (arrivalTimer) clearInterval(arrivalTimer);
});
osMotionPreference.addEventListener('change', () => {
  if (snapshot) render(snapshot);
});
start();
