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
  'survey-rail', 'survey-progress-fill', 'survey-acquisition', 'survey-signals',
  'survey-signal-bio', 'survey-signal-geo', 'survey-signal-mining', 'survey-signal-valuable',
  'metric-fuel', 'metric-bio', 'metric-geo', 'expanded-fuel',
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
let lastRouteSignature = '';
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

function vehiclePresentation(state = {}) {
  const motion = String(state.motion || 'flight');
  const label = String(state.label || 'FLIGHT').toUpperCase();
  const vehicle = state.vehicle || {};
  const catalog = window.VoidCompassShipCatalog;
  if (motion.startsWith('carrier_')) {
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
    if (label.includes('SRV') || label.includes('SCARAB') || label.includes('SCORPION')
        || label.includes('RHINO') || vehicle.surface) {
      const surface = label.includes('SCORPION') ? 'SCORPION'
        : label.includes('RHINO') ? 'RHINO'
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
  const hops = Array.isArray(route.hops) ? route.hops : [];
  const signature = JSON.stringify([
    route.header || '', route.next_distance || '', route.distance || '',
    Boolean(route.active), route.origin_current === false ? 'start' : 'current',
    Number(route.progress_percent || 0),
    hops.map((hop) => [hop.position, hop.completed, hop.current, hop.next, hop.scoopable, hop.name]),
  ]);
  if (signature === lastRouteSignature) return;
  lastRouteSignature = signature;
  dom['route-title'].textContent = route.header || 'NO ACTIVE ROUTE';
  dom['route-next'].textContent = route.next_distance || '';
  dom['route-distance'].textContent = route.distance || '';
  dom['route-origin'].textContent = route.origin_current === false ? 'START' : 'CURRENT';
  dom['route-destination'].textContent = route.active || route.hops?.length ? 'DEST' : 'NEXT';
  dom['route-progress'].style.width = `${Math.max(0, Math.min(100, Number(route.progress_percent || 0)))}%`;
  dom['route-packet'].style.display = route.active ? '' : 'none';
  const host = dom['route-pips'];
  host.replaceChildren();
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

function renderSurvey(survey = {}, theme = {}, systemName = '', reducedMotion = false) {
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
  const signature = JSON.stringify([
    systemName, state, scanned, total, totalKnown, Math.round(percent * 100) / 100,
    signalCounts.bio, signalCounts.geo, signalCounts.mining, signalCounts.valuable, tone, reducedMotion,
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
    alert.querySelector('em').textContent = String(count);
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
  renderSurvey(data.survey, theme, system.name || '', reducedMotion);
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
