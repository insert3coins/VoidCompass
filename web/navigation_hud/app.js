const params = new URLSearchParams(location.search);
const token = params.get('token') || '';
const overlay = params.get('overlay') || 'navigation';
const api = (path) => `${path}?token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
const $ = (id) => document.getElementById(id);

const dom = Object.fromEntries([
  'hud', 'state-canvas', 'state-label', 'region-label', 'system-clock', 'current-system',
  'route-title', 'route-next', 'route-distance', 'route-progress', 'route-packet',
  'route-pips', 'route-origin', 'route-destination', 'survey-state', 'survey-count',
  'survey-rail', 'metric-fuel', 'metric-bio', 'metric-geo', 'expanded-fuel',
  'expanded-bio', 'expanded-geo', 'expanded-traffic', 'context-label',
  'secondary-label', 'traffic-label', 'link-state',
].map((id) => [id, $(id)]));
const stateIndicator = new window.NavigationIndicator(dom['state-canvas']);

let snapshot = null;
let arrivalTimer = null;
let lastEventSequence = null;
let lastServerContact = Date.now();
let lastRevision = -1;
let healthPollActive = false;

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
  if (route.dense && hops.length) {
    const cells = Math.max(10, Math.min(18, Number(route.cells || 14)));
    host.className = 'route-pips dense';
    host.style.setProperty('--cells', cells);
    const progress = Math.max(0, Math.min(1, Number(route.progress_percent || 0) / 100));
    const currentCell = Math.max(0, Math.min(cells - 1, Math.round(progress * (cells - 1))));
    for (let index = 0; index < cells; index += 1) {
      const cell = document.createElement('i');
      cell.className = `route-cell${index < currentCell ? ' done' : ''}${index === currentCell ? ' here' : ''}`;
      host.appendChild(cell);
    }
    return;
  }
  host.className = 'route-pips';
  for (const hop of hops) {
    const pip = document.createElement('i');
    pip.className = [
      'route-pip', hop.completed && 'completed', hop.current && 'current',
      hop.next && 'next', hop.scoopable === false && 'unscoopable',
    ].filter(Boolean).join(' ');
    pip.style.left = `${Math.max(0, Math.min(100, Number(hop.position || 0)))}%`;
    pip.title = hop.name || '';
    host.appendChild(pip);
  }
}

function renderSurvey(survey = {}) {
  dom['survey-state'].textContent = survey.label || 'COUNT UNKNOWN';
  dom['survey-state'].style.color = survey.tone || 'var(--accent)';
  dom['survey-count'].textContent = survey.count || '0/? · --%';
  dom['survey-count'].style.color = survey.tone || 'var(--accent)';
  const host = dom['survey-rail'];
  host.className = `survey-rail${survey.live ? ' live' : ''}`;
  host.style.setProperty('--survey-tone', survey.tone || 'var(--accent)');
  host.replaceChildren();
  const completion = Math.max(0, Math.min(12, Number(survey.percent || 0) / 100 * 12));
  for (let index = 0; index < 12; index += 1) {
    const segment = document.createElement('span');
    segment.className = 'survey-segment';
    const fill = document.createElement('i');
    fill.style.setProperty('--fill', Math.max(0, Math.min(1, completion - index)));
    segment.appendChild(fill);
    host.appendChild(segment);
  }
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
  setTheme(data.theme);
  const hud = dom.hud;
  hud.classList.toggle('standard', data.layout !== 'expanded');
  hud.classList.toggle('expanded', data.layout === 'expanded');
  hud.classList.toggle('no-crt', !data.effects?.crt);
  hud.classList.toggle('reduced-motion', Boolean(data.effects?.reduced_motion));
  hud.dataset.motion = data.state?.motion || 'flight';
  hud.dataset.state = data.state?.label || 'FLIGHT';
  hud.style.setProperty('--state', data.state?.color || 'var(--dim)');
  const energy = Math.max(.55, Math.min(1.6, Number(data.effects?.energy || 1)));
  hud.style.setProperty('--motion-energy', String(energy));
  hud.style.setProperty('--motion-scale', String(1 / energy));
  dom['state-label'].textContent = data.state?.label || 'FLIGHT';
  stateIndicator.update({
    motion: data.state?.motion || 'flight',
    label: data.state?.label || 'FLIGHT',
    color: data.state?.color || '#607584',
    energy,
    reduced: Boolean(data.effects?.reduced_motion),
    eventSequence: data.state?.event_sequence,
    eventKind: data.state?.event_kind,
  });
  const eventSequence = data.state?.event_sequence;
  if (eventSequence != null && eventSequence !== lastEventSequence) {
    lastEventSequence = eventSequence;
    hud.dataset.event = 'false';
    void hud.offsetWidth;
    hud.dataset.event = 'true';
    setTimeout(() => { hud.dataset.event = 'false'; }, 900);
  }
  const system = data.system || {};
  dom['current-system'].textContent = system.name || '---';
  dom['region-label'].textContent = system.region || 'REGION UNKNOWN';
  renderRoute(data.route);
  renderSurvey(data.survey);
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
