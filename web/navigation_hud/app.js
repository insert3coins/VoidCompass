const params = new URLSearchParams(location.search);
const token = params.get('token') || '';
const overlay = params.get('overlay') || 'navigation';
const api = (path) => `${path}?token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
const $ = (id) => document.getElementById(id);

const dom = Object.fromEntries([
  'hud', 'state-canvas', 'state-label', 'vehicle-display', 'vehicle-image',
  'region-label', 'system-clock', 'current-system',
  'route-title', 'route-next', 'route-distance', 'route-progress', 'route-packet',
  'route-pips', 'route-origin', 'route-destination', 'survey-block', 'survey-title',
  'survey-title-text', 'survey-state', 'survey-mode', 'survey-remaining',
  'survey-count', 'survey-percent', 'survey-progress-marker',
  'survey-rail', 'survey-signals', 'metric-fuel', 'metric-bio', 'metric-geo', 'expanded-fuel',
  'expanded-bio', 'expanded-geo', 'expanded-traffic', 'context-label',
  'secondary-label', 'traffic-label', 'link-state',
].map((id) => [id, $(id)]));
const stateIndicator = new window.NavigationIndicator(dom['state-canvas']);

let snapshot = null;
let arrivalTimer = null;
let lastIndicatorSignature = '';
let stateChangeTimer = null;
let vehicleImageTransition = null;
let lastServerContact = Date.now();
let lastRevision = -1;
let healthPollActive = false;
let lastSurveyProgress = null;
let surveyPulseTimer = null;
let surveyMarkerTimer = null;

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

function vehiclePresentation(state = {}) {
  const motion = String(state.motion || 'flight');
  const label = String(state.label || 'FLIGHT').toUpperCase();
  const vehicle = state.vehicle || {};
  const catalog = window.VoidCompassShipCatalog;
  if (motion === 'carrier_transit' || motion === 'carrier_arrival') {
    return catalog.carrier();
  }
  if (motion === 'on_foot' || label === 'ONFOOT' || label === 'ON FOOT') {
    return catalog.onFoot();
  }
  if (motion === 'surface_vehicle' || motion.startsWith('vehicle_')) {
    if (label.includes('NOMAD') || String(vehicle.surface || '').toUpperCase() === 'NOMAD') {
      return catalog.resolveSurface('NOMAD');
    }
    if (label.includes('FIGHTER')) {
      return catalog.fighter();
    }
    if (label.includes('SRV') || label.includes('SCARAB') || label.includes('SCORPION') || vehicle.surface) {
      const surface = label.includes('SCORPION') ? 'SCORPION'
        : label.includes('SCARAB') ? 'SCARAB' : vehicle.surface;
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
  const hostRect = host.getBoundingClientRect();
  const imageRect = image.getBoundingClientRect();
  const computed = getComputedStyle(image);
  const ghost = image.cloneNode(false);
  ghost.removeAttribute('id');
  ghost.className = 'vehicle-outgoing';
  ghost.alt = '';
  ghost.setAttribute('aria-hidden', 'true');
  ghost.style.left = `${imageRect.left - hostRect.left}px`;
  ghost.style.top = `${imageRect.top - hostRect.top}px`;
  ghost.style.width = `${imageRect.width}px`;
  ghost.style.height = `${imageRect.height}px`;
  ghost.style.opacity = computed.opacity;
  ghost.style.filter = computed.filter;
  host.appendChild(ghost);

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

function renderVehicle(state = {}, reducedMotion = false) {
  const presentation = vehiclePresentation(state);
  const host = dom['vehicle-display'];
  const image = dom['vehicle-image'];
  if (reducedMotion) clearVehicleTransition(host, image);
  if (!presentation) {
    clearVehicleTransition(host, image);
    host.hidden = true;
    image.removeAttribute('src');
    image.alt = '';
    return null;
  }
  host.hidden = false;
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

function setMetric(id, metric) {
  const element = dom[id];
  element.textContent = metric?.value ?? '--';
  element.parentElement.style.setProperty('--metric-color', metric?.color || 'var(--accent)');
}

function renderRoute(route = {}) {
  dom['route-title'].textContent = route.header || 'NO ACTIVE ROUTE';
  dom['route-next'].textContent = route.next_distance || '';
  dom['route-distance'].textContent = route.distance || '';
  dom['route-origin'].textContent = route.origin_current === false ? 'START' : 'CURRENT';
  dom['route-destination'].textContent = route.active || route.hops?.length ? 'DEST' : 'NEXT';
  dom['route-progress'].style.width = `${Math.max(0, Math.min(100, Number(route.progress_percent || 0)))}%`;
  dom['route-packet'].style.display = route.active ? '' : 'none';
  const host = dom['route-pips'];
  host.replaceChildren();
  const hops = Array.isArray(route.hops) ? route.hops : [];
  host.className = `route-pips unified${hops.length > 48 ? ' ultra-dense' : hops.length > 18 ? ' dense' : ''}`;
  let previousPosition = 0;
  for (const hop of hops) {
    const endPosition = Math.max(previousPosition, Math.min(100, Number(hop.position || 0)));
    const segment = document.createElement('i');
    segment.className = [
      'route-segment', hop.completed && 'completed', hop.current && 'current',
      hop.next && 'next', hop.scoopable === false && 'unscoopable',
    ].filter(Boolean).join(' ');
    segment.style.left = `${previousPosition}%`;
    segment.style.width = `${Math.max(.18, endPosition - previousPosition)}%`;
    segment.title = hop.name || '';
    const waypoint = document.createElement('b');
    waypoint.setAttribute('aria-hidden', 'true');
    segment.appendChild(waypoint);
    host.appendChild(segment);
    previousPosition = endPosition;
  }
}

function renderSurvey(survey = {}, theme = {}, systemName = '') {
  const state = ['unknown', 'live', 'retained', 'complete'].includes(String(survey.state))
    ? String(survey.state) : (survey.complete ? 'complete' : survey.live ? 'live' : 'unknown');
  const scanned = Math.max(0, Number.parseInt(survey.scanned, 10) || 0);
  const total = Math.max(0, Number.parseInt(survey.total, 10) || 0);
  const totalKnown = survey.total_known !== false && state !== 'unknown';
  const percent = Math.max(0, Math.min(100, Number(survey.percent || 0)));
  const rawSignals = survey.signals || {};
  const signalCounts = Object.fromEntries(['bio', 'geo', 'valuable'].map((kind) => [
    kind, Math.max(0, Number.parseInt(rawSignals[kind], 10) || 0),
  ]));
  const tone = survey.tone
    ? themedStateColour(survey.tone, theme)
    : (state === 'unknown' ? (theme.dim || 'var(--dim)') : (theme.accent || 'var(--accent)'));
  const block = dom['survey-block'];
  block.dataset.surveyState = state;
  block.style.setProperty('--survey-tone', tone);
  dom['survey-title-text'].textContent = state === 'complete'
    ? 'SYSTEM SURVEY COMPLETE' : 'SYSTEM SURVEY';
  const remaining = totalKnown ? Math.max(0, total - scanned) : null;
  const modeLabels = {
    unknown: 'COUNT UNKNOWN', live: 'LIVE FSS', retained: 'RECORDED', complete: '',
  };
  dom['survey-mode'].textContent = modeLabels[state];
  dom['survey-remaining'].textContent = state !== 'complete' && remaining > 0
    ? `${remaining} REMAIN` : '';
  dom['survey-state'].style.color = tone;
  dom['survey-count'].textContent = `${scanned} / ${totalKnown ? total : '?'} BODIES`;
  dom['survey-count'].style.color = tone;
  dom['survey-percent'].textContent = totalKnown ? `${Math.round(percent)}%` : '--%';
  dom['survey-percent'].style.color = tone;

  const host = dom['survey-rail'];
  const previous = lastSurveyProgress;
  const sameSystem = Boolean(previous && previous.systemName === systemName);
  const progressed = Boolean(sameSystem && totalKnown && (
    scanned > previous.scanned || percent > previous.percent
  ));
  if (progressed) {
    host.classList.remove('scan-pulse');
    void host.offsetWidth;
    host.classList.add('scan-pulse');
    block.classList.remove('survey-progressing');
    void block.offsetWidth;
    block.classList.add('survey-progressing');
    if (surveyPulseTimer) clearTimeout(surveyPulseTimer);
    surveyPulseTimer = setTimeout(() => {
      host.classList.remove('scan-pulse');
      block.classList.remove('survey-progressing');
      surveyPulseTimer = null;
    }, 1050);
  } else if (!surveyPulseTimer) {
    host.classList.remove('scan-pulse');
  }
  const segmentCount = totalKnown && total > 0 && total <= 24 ? total : (total > 24 ? 24 : 12);
  host.style.setProperty('--survey-segments', String(segmentCount));
  const completion = percent / 100 * segmentCount;
  if (host.children.length !== segmentCount) {
    host.replaceChildren();
    for (let index = 0; index < segmentCount; index += 1) {
      const segment = document.createElement('span');
      segment.className = 'survey-segment';
      const fill = document.createElement('i');
      segment.appendChild(fill);
      host.appendChild(segment);
    }
  }
  const segments = Array.from(host.children);
  segments.forEach((segment, index) => {
    const fill = segment.firstElementChild;
    fill.style.setProperty('--fill', Math.max(0, Math.min(1, completion - index)));
  });
  if (progressed) {
    segments.forEach((segment) => segment.classList.remove('acquired'));
    void host.offsetWidth;
    const priorCompletion = Math.max(0, Math.min(segmentCount,
      Number(previous.percent || 0) / 100 * segmentCount));
    const firstChanged = Math.min(segmentCount - 1, Math.floor(priorCompletion));
    const lastChanged = Math.min(segmentCount - 1,
      Math.max(firstChanged, Math.ceil(completion) - 1));
    for (let index = firstChanged; index <= lastChanged; index += 1) {
      segments[index]?.classList.add('acquired');
    }
  }

  const marker = dom['survey-progress-marker'];
  const markerPosition = 7 + (percent / 100 * 86);
  if (!sameSystem) marker.classList.add('resetting');
  marker.style.left = `${markerPosition}%`;
  if (!sameSystem) requestAnimationFrame(() => marker.classList.remove('resetting'));
  marker.classList.toggle('unavailable', !totalKnown);
  marker.classList.toggle('complete', state === 'complete');
  if (progressed) {
    marker.classList.remove('acquiring');
    void marker.offsetWidth;
    marker.classList.add('acquiring');
    if (surveyMarkerTimer) clearTimeout(surveyMarkerTimer);
    surveyMarkerTimer = setTimeout(() => {
      marker.classList.remove('acquiring');
      surveyMarkerTimer = null;
    }, 850);
  }
  const signalHost = dom['survey-signals'];
  for (const [kind, shortLabel, title] of [
    ['bio', 'B', 'Biological signals'],
    ['geo', 'G', 'Geological signals'],
    ['valuable', 'V', 'High-value bodies'],
  ]) {
    const count = signalCounts[kind];
    let marker = signalHost.querySelector(`[data-signal-kind="${kind}"]`);
    if (!marker) {
      marker = document.createElement('i');
      marker.className = `survey-notch ${kind}`;
      marker.dataset.signalKind = kind;
      signalHost.appendChild(marker);
    }
    marker.textContent = shortLabel;
    marker.title = `${title}: ${count}`;
    marker.setAttribute('aria-label', `${title}: ${count}`);
    marker.classList.toggle('present', count > 0);
    const signalFound = Boolean(sameSystem
      && count > Number(previous?.signals?.[kind] || 0));
    if (signalFound) {
      marker.classList.remove('found');
      void marker.offsetWidth;
      marker.classList.add('found');
    }
  }
  lastSurveyProgress = {systemName, scanned, total, percent, state, signals: signalCounts};
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

function render(data) {
  if (!data || data.schema !== 1) return;
  snapshot = data;
  const overlayOpacity = Number(data.effects?.opacity);
  document.body.style.opacity = String(Number.isFinite(overlayOpacity)
    ? Math.max(.4, Math.min(1, overlayOpacity)) : 1);
  const theme = setTheme(data.theme);
  const hud = dom.hud;
  hud.classList.toggle('standard', data.layout !== 'expanded');
  hud.classList.toggle('expanded', data.layout === 'expanded');
  hud.classList.toggle('no-crt', !data.effects?.crt);
  const reducedMotion = Boolean(data.effects?.reduced_motion);
  hud.classList.toggle('reduced-motion', reducedMotion);
  hud.dataset.motion = data.state?.motion || 'flight';
  hud.dataset.state = data.state?.label || 'FLIGHT';
  const vehicle = renderVehicle(data.state, reducedMotion);
  const stateColour = themedStateColour(data.state?.color, theme);
  hud.style.setProperty('--state', stateColour);
  const energy = Math.max(.55, Math.min(1.6, Number(data.effects?.energy || 1)));
  hud.style.setProperty('--motion-energy', String(energy));
  hud.style.setProperty('--motion-scale', String(1 / energy));
  const indicatorSignature = `${data.state?.motion || 'flight'}|${data.state?.label || 'FLIGHT'}|${vehicle?.key || 'none'}`;
  dom['state-label'].textContent = data.state?.label || 'FLIGHT';
  if (lastIndicatorSignature && indicatorSignature !== lastIndicatorSignature
      && !data.effects?.reduced_motion) {
    hud.classList.remove('state-changing');
    void dom['state-label'].offsetWidth;
    hud.classList.add('state-changing');
    if (stateChangeTimer) clearTimeout(stateChangeTimer);
    stateChangeTimer = setTimeout(() => {
      hud.classList.remove('state-changing');
      stateChangeTimer = null;
    }, 620);
  }
  lastIndicatorSignature = indicatorSignature;
  stateIndicator.update({
    motion: data.state?.motion || 'flight',
    label: data.state?.label || 'FLIGHT',
    vehicleKey: vehicle?.key || '',
    color: stateColour,
    energy,
    dynamics: data.state?.dynamics || {},
    reduced: Boolean(data.effects?.reduced_motion),
    eventSequence: data.state?.event_sequence,
    eventKind: data.state?.event_kind,
  });
  const system = data.system || {};
  dom['current-system'].textContent = system.name || '---';
  dom['region-label'].textContent = system.region || 'REGION UNKNOWN';
  renderRoute(data.route);
  renderSurvey(data.survey, theme, system.name || '');
  const metrics = data.metrics || {};
  for (const prefix of ['metric', 'expanded']) {
    setMetric(`${prefix}-fuel`, metrics.fuel);
    setMetric(`${prefix}-bio`, metrics.bio);
    setMetric(`${prefix}-geo`, metrics.geo);
  }
  dom['expanded-traffic'].textContent = metrics.traffic?.value || '0 / 0 / 0';
  dom['expanded-traffic'].parentElement.style.setProperty('--metric-color', metrics.traffic?.color || 'var(--dim)');
  dom['context-label'].textContent = data.context?.primary || '';
  dom['context-label'].style.color = data.context?.primary_color || 'var(--accent)';
  dom['secondary-label'].textContent = data.layout === 'expanded' ? (data.context?.secondary || '') : '';
  dom['secondary-label'].style.color = data.context?.secondary_color || 'var(--yellow)';
  dom['traffic-label'].textContent = data.layout === 'expanded' ? '' : (data.context?.traffic || '');
  updateClock();
}

async function fetchSnapshot() {
  const response = await fetch(api('/api/snapshot'), {cache: 'no-store'});
  if (!response.ok) throw new Error(`Snapshot HTTP ${response.status}`);
  lastServerContact = Date.now();
  return response.json();
}

async function acknowledgeRendered(revision) {
  try {
    await fetch(api('/api/rendered'), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({revision}),
    });
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
    if (Number.isFinite(revision) && revision !== lastRevision) {
      render(await fetchSnapshot());
      lastRevision = revision;
      await acknowledgeRendered(revision);
      dom['link-state'].textContent = 'HTML NAV // LIVE';
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
  if (arrivalTimer) clearInterval(arrivalTimer);
});
start();
