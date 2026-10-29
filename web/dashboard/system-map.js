const html=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=(value,digits=1)=>value===null||value===undefined||!Number.isFinite(Number(value))?'—':Number(value).toLocaleString(undefined,{maximumFractionDigits:digits});
const valid=v=>v!==null&&v!==undefined&&Number.isFinite(Number(v));
// Game time is UTC with the year moved on 1286 years.
const gameTime=ms=>{const d=new Date(ms);return `${d.getUTCFullYear()+1286}-${String(d.getUTCMonth()+1).padStart(2,'0')}-${String(d.getUTCDate()).padStart(2,'0')} ${d.toISOString().slice(11,16)}`;};
const duration=s=>s<90?`${Math.round(s)} S`:s<5400?`${Math.round(s/60)} MIN`:`${(s/3600).toFixed(1)} H`;
const until=(ms,now)=>{const m=Math.round((ms-now)/60000);return m<1?'NOW':m<90?`IN ${m} MIN`:m<2880?`IN ${Math.floor(m/60)} H ${m%60} MIN`:`IN ${Math.floor(m/1440)} DAYS`;};
const SURVEY_LABELS=[['all','ALL'],['bio','BIOLOGY'],['geo','GEOLOGY'],['unmapped','UNMAPPED'],['valuable','VALUABLE'],['first','FIRST DISCOVERY'],['landable','LANDABLE']];
let scene=null,loading=null,epoch=0,active=false,warm=false,latest=null,profile='',fingerprint='',selection=null,pendingSelection=null,filter='';
let listKey='',detailKey='',context=null,surveyFilter='all',dayCache=new Map();
const root=()=>document.getElementById('system-map-workspace');

function skeleton(){const node=root();if(!node||node.dataset.mounted)return false;
  // Explore rebuilt its tabs: the old canvas went with them, so the scene starts afresh.
  if(scene){scene.dispose();scene=null;loading=null;fingerprint='';}
  listKey='';detailKey='';node.dataset.mounted='true';
  node.innerHTML=`<div class="sm-toolbar"><div class="sm-identity"><small>VOID COMPASS / LIVE SYSTEM LINK</small><h3 id="sm-system">Awaiting journal</h3><span id="sm-source" role="status"></span></div><button type="button" class="sm-you" id="sm-you" data-sm="findme" hidden title="Fly to where you are"><i aria-hidden="true">●</i><span></span></button><div class="sm-tools"><button type="button" data-sm="fit" title="Fit the whole system">FIT SYSTEM</button><button type="button" data-sm="expand" aria-pressed="false">EXPAND MAP</button></div></div>
  <div class="sm-layout"><aside class="sm-hierarchy" aria-label="System bodies"><header><div><small>SYSTEM ARCHITECTURE</small><b id="sm-count">0 BODIES</b></div><label><span class="sr-only">Filter bodies</span><input type="search" id="sm-filter" placeholder="Find a body…" autocomplete="off"></label></header><div id="sm-bodies" role="list" tabindex="-1"></div><footer><i></i>PERSONAL SCANS <span>○ PUBLIC CATALOGUE · ≈ APPROXIMATE ORBIT</span></footer></aside>
  <section class="sm-view"><div class="sm-viewbar"><div role="group" aria-label="Map scale"><button type="button" data-sm="overview" aria-pressed="true">OVERVIEW</button><button type="button" data-sm="scale" aria-pressed="false">TRUE SCALE</button></div><div role="group" aria-label="Map layers"><button type="button" data-sm="orbits" aria-pressed="true">ORBITS</button><button type="button" data-sm="labels" aria-pressed="true">LABELS</button><button type="button" data-sm="stations" aria-pressed="true" title="Stations, settlements and carriers">STATIONS</button><button type="button" data-sm="survey" aria-pressed="false" title="Your survey on the map: biology, geology, value, first discoveries">SURVEY</button><label class="sm-quality"><span class="sr-only">Graphics quality</span><select id="sm-quality" title="Graphics quality: lower suits slower PCs"><option value="low">LOW</option><option value="standard" selected>STANDARD</option><option value="high">HIGH</option></select></label></div>
    <div class="sm-survey-filters" id="sm-survey-filters" role="group" aria-label="Survey filter" hidden>${SURVEY_LABELS.map(([id,label])=>`<button type="button" data-sm-filter="${id}" aria-pressed="${id==='all'}">${label}</button>`).join('')}</div></div>
    <div class="sm-stage" id="sm-stage"><div class="sm-empty" id="sm-empty" role="status"><i aria-hidden="true">◎</i><b>LINKING SYSTEM ARCHITECTURE</b><p>Your current system follows the journal. Public body data arrives from Spansh.</p></div><div class="sm-corners" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
      <div class="sm-surface" id="sm-surface" hidden><header><small>THE SKY FROM</small><b id="sm-surface-body"></b><button type="button" data-sm="surface-exit">◄ BACK TO THE MAP</button></header>
        <label>LOOK AT<select id="sm-surface-target"></select></label><label>HEIGHT IN THE SKY <output id="sm-surface-el-out">20°</output><input type="range" id="sm-surface-el" min="0" max="90" value="20"></label><label>AROUND <output id="sm-surface-az-out">0°</output><input type="range" id="sm-surface-az" min="0" max="359" value="0"></label><p>True scale and true angular sizes. Drag to look around, wheel to zoom. The ground is illustrative.</p></div></div>
    <div class="sm-time"><div><small>GALACTIC STANDARD TIME / UTC</small><time id="sm-clock">—</time></div><div class="sm-time-controls"><button type="button" data-sm="back" title="Step back one hour">−1 H</button><label><span class="sr-only">Orbital simulation speed</span><select id="sm-speed"><option value="-3600">REWIND · 1 H / S</option><option value="0">PAUSED</option><option value="1" selected>REAL TIME</option><option value="60">1 MIN / S</option><option value="3600">1 H / S</option><option value="86400">1 DAY / S</option></select></label><button type="button" data-sm="forward" title="Step forward one hour">+1 H</button><button type="button" data-sm="live">LIVE NOW</button></div></div>
    <footer class="sm-caption"><span id="sm-scale-note">Overview enlarges bodies and spaces them out; directions are real.</span><span>DRAG ORBIT · WHEEL ZOOM · CLICK SELECT</span></footer>
  </section><aside class="sm-inspector" aria-label="Selected body"><div id="sm-detail"><div class="sm-inspector-empty"><small>BODY TELEMETRY</small><b>Select a world.</b><p>Explore the system, inspect your discoveries and see how its worlds move.</p></div></div><section class="sm-light" id="sm-light" hidden><small>STARLIGHT AT THIS MOMENT</small><div id="sm-starlight"></div><p>Computed from known orbits and radii. Surface detail is illustrative.</p></section></aside></div>`;
  node.addEventListener('click',e=>{const body=e.target.closest('[data-sm-body]');if(body){select(Number(body.dataset.smBody));return;}
    const chip=e.target.closest('[data-sm-filter]');if(chip){surveyFilter=chip.dataset.smFilter;scene?.setSurvey(scene.survey.on,surveyFilter);syncControls();saveView();renderList();return;}
    const button=e.target.closest('[data-sm]');if(!button)return;const action=button.dataset.sm;
    if(action==='expand'){const expanded=node.classList.toggle('sm-expanded');button.setAttribute('aria-pressed',String(expanded));button.textContent=expanded?'RESTORE PANELS':'EXPAND MAP';scene?.resize();return;}
    if(!scene)return;
    if(action==='fit')scene.reset();else if(action==='overview')scene.setScale(false);else if(action==='scale')scene.setScale(true);
    else if(action==='orbits'||action==='labels'||action==='stations'){scene.view[action]=!scene.view[action];scene.wake();}
    else if(action==='survey'){scene.setSurvey(!scene.survey.on,surveyFilter);renderList();}
    else if(action==='findme'){if(scene.findMe()){selection=scene.selected;renderList();renderDetail();}}
    else if(action==='surface'){enterSurface(Number(button.dataset.body));return;}
    else if(action==='surface-exit'){scene.exitSurface();syncSurface();return;}
    else if(action==='back'||action==='forward'){scene.step(action==='back'?-3600:3600);node.querySelector('#sm-speed').value='0';}
    else if(action==='live'){scene.time=Date.now();scene.setTime(1);node.querySelector('#sm-speed').value='1';}
    syncControls();saveView();
  });
  node.querySelector('#sm-speed').addEventListener('change',e=>scene?.setTime(Number(e.target.value)));
  node.querySelector('#sm-filter').addEventListener('input',e=>{filter=e.target.value;renderList();});
  node.querySelector('#sm-quality').addEventListener('change',e=>{scene?.setQuality(e.target.value);saveView();});
  node.querySelector('#sm-surface-target').addEventListener('change',e=>scene?.setSurface({target:Number(e.target.value)}));
  for(const key of ['el','az'])node.querySelector(`#sm-surface-${key}`).addEventListener('input',e=>{const value=Number(e.target.value);node.querySelector(`#sm-surface-${key}-out`).textContent=`${value}°`;scene?.setSurface({[key]:value});});
  return true;
}

function syncControls(){if(!scene)return;const node=root();if(!node)return;
  const press=(key,on)=>node.querySelector(`[data-sm="${key}"]`)?.setAttribute('aria-pressed',String(on));
  press('overview',!scene.view.trueScale);press('scale',scene.view.trueScale);for(const key of ['orbits','labels','stations'])press(key,scene.view[key]);press('survey',scene.survey.on);
  node.querySelector('#sm-survey-filters').hidden=!scene.survey.on;for(const chip of node.querySelectorAll('[data-sm-filter]'))chip.setAttribute('aria-pressed',String(chip.dataset.smFilter===scene.survey.filter));
  node.querySelector('#sm-quality').value=scene.qualityName;
  node.querySelector('#sm-scale-note').textContent=scene.view.trueScale?'Known sizes and distances. Incomplete orbits and sizes remain in the body list.':'Bodies enlarged and spaced out; directions are real. Unresolved bodies sit on a schematic row.';}
function saveView(){if(!scene||!profile)return;try{localStorage.setItem(`voidcompass.system-map.${profile}`,JSON.stringify({orbits:scene.view.orbits,labels:scene.view.labels,stations:scene.view.stations,trueScale:scene.view.trueScale,survey:scene.survey.on,filter:scene.survey.filter,quality:scene.qualityName}));}catch{}}
function readView(){try{return JSON.parse(localStorage.getItem(`voidcompass.system-map.${profile}`)||'{}')||{};}catch{return {};}}

function renderList(){if(!latest||!root())return;const system=latest.system||{},rows=(system.bodies||[]).filter(b=>b.type!=='Barycentre');
  const you=scene?.youNode?.data.bodyId??null,target=scene?.targetNode?.data.bodyId??null,dim=b=>scene&&scene.survey.on&&!scene.surveyMatch(b);
  const markup=rows.filter(b=>String(b.name).toLowerCase().includes(filter.trim().toLowerCase())).map(b=>{
    const parents=(b.parents||[]).length,scanned=!!b._survey?.scanned,stations=(scene?.stationsAt(b.bodyId)||[]).length+(b.surfaceStations||[]).length;
    const tag=b._survey?.mapped?'DSS':b._survey?.bio?`BIO ${number(b._survey.bio,0)}`:b._approx?'≈':!b._resolved?'?':'';
    return `<button type="button" role="listitem" class="sm-body${Number(selection)===b.bodyId&&selection!==null?' selected':''}${b.type==='Star'?' star':''}${dim(b)?' dimmed':''}" data-sm-body="${b.bodyId}" aria-pressed="${selection!==null&&Number(selection)===b.bodyId}" style="--depth:${Math.min(3,parents)}"><i class="${scanned?'personal':''}">${b.type==='Star'?'✦':'○'}</i><span><b>${html(String(b.name).replace(new RegExp('^'+String(system.name).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\s+','i'),''))}</b><small>${html(b.subType||b.type)}${you===b.bodyId?' · <q>YOU</q>':''}${target===b.bodyId?' · <q class="target">TARGET</q>':''}${stations?` · ◇${stations}`:''}</small></span><em>${tag}</em></button>`;
  }).join('')||'<p class="sm-no-results">No matching bodies.</p>';
  if(markup!==listKey){root().querySelector('#sm-bodies').innerHTML=markup;listKey=markup;}
  root().querySelector('#sm-count').textContent=`${rows.length} BODIES${system.bodyCount?` / ${system.bodyCount} KNOWN`:''}`;
}

function section(title,body,note=''){return body?`<section class="sm-section"><small>${title}</small>${body}${note?`<p class="sm-note">${note}</p>`:''}</section>`:'';}
function rows(list){return list.length?`<dl class="sm-facts">${list.map(([label,value])=>`<div><dt>${html(label)}</dt><dd>${value}</dd></div>`).join('')}</dl>`:'';}
function eclipseCard(event,star){const W=86,H=86,c=W/2,unit=Math.max(event.aS,Math.min(event.aO,event.aS*6))*1.15,px=(W/2-4)/unit,rS=event.aS*px,rO=event.aO*px;
  return `<div class="sm-eclipse"><svg viewBox="0 0 ${W} ${H}" aria-hidden="true"><circle cx="${c}" cy="${c}" r="${rS}" class="sun"/><circle cx="${c+event.sep*px}" cy="${c}" r="${rO}" class="occ"/></svg><span><b>${gameTime(event.t)}</b><em>${html(event.by?String(event.by.name||'').replace(new RegExp('^'+String(latest?.system?.name||'').replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\s+','i'),''):'?')} · ${event.vis<.005?'TOTAL':`${number((1-event.vis)*100,0)}% COVERED`}</em><small>${number(event.hours,1)} H OF SHADOW · ${html(star)}</small></span></div>`;}
function dayNightFor(body,site){if(!scene)return null;const key=`${body.bodyId}|${site.lat}|${site.lon}|${Math.floor(scene.time/60000)}`;if(!dayCache.has(key)){if(dayCache.size>40)dayCache.clear();dayCache.set(key,scene.dayNight(body.bodyId,site.lat,site.lon));}return dayCache.get(key);}

function renderDetail(){const node=root();const body=(latest?.system?.bodies||[]).find(b=>b.bodyId===Number(selection));if(!node||!body||selection===null)return;
  const scanned=body._survey?.scanned,known=value=>value===true?'YES':value===false?'NO':'UNKNOWN',facts=body._facts||{},star=body.type==='Star';
  const telemetry=[['RADIUS',star&&body.solarRadius?`${number(body.solarRadius,3)} R☉`:body.radius?`${number(body.radius,0)} KM`:'—'],['MASS',star?(body.solarMasses?`${number(body.solarMasses,3)} M☉`:'—'):(body.earthMasses?`${number(body.earthMasses,4)} M⊕`:'—')],['GRAVITY',valid(body.gravity)?`${number(body.gravity,3)} G`:'—'],['TEMPERATURE',valid(body.surfaceTemperature)?`${number(body.surfaceTemperature,0)} K`:'—'],['ARRIVAL DISTANCE',valid(body.distanceToArrival)?`${number(body.distanceToArrival)} LS`:'—'],['ORBITAL PERIOD',valid(body.orbitalPeriod)?`${number(body.orbitalPeriod,3)} DAYS`:'—'],['ROTATION',valid(body.rotationalPeriod)?`${number(body.rotationalPeriod,3)} DAYS${body.rotationalPeriodTidallyLocked?' · LOCKED':''}`:'—'],['ATMOSPHERE',body.atmosphereType||'UNKNOWN'],['LANDABLE',known(body.isLandable)],['RINGS',body.rings?.length?body.rings.map(r=>r.type).join(' / '):'NONE REPORTED']].map(([l,v])=>[l,html(v)]);
  const flags=[scanned?'PERSONALLY SCANNED':body._source?.includes('journal')?'JOURNAL SIGNALS':'PUBLIC CATALOGUE',body._survey?.mapped?'DSS COMPLETE':'',body._survey?.bio?`${number(body._survey.bio,0)} BIOLOGICAL SIGNALS`:'',body._survey?.geo?`${number(body._survey.geo,0)} GEOLOGICAL SIGNALS`:'',body._survey?.wasDiscovered===false?'FIRST DISCOVERY':'',scene?.youNode?.data.bodyId===body.bodyId?'YOU ARE HERE':''].filter(Boolean);
  const note=body._resolved?'Orbital elements and their measurement epoch are available.':body._approx?'Approximate: its distance and parent are known, its place along the orbit is not.':'Position unresolved. More orbital data is needed; overview placement is schematic.';
  const from=scene?.fromYou(body.bodyId);
  const travel=from?section('FROM YOU',rows([['DISTANCE',`${number(from.ls,from.ls<10?2:0)} LS`],['FROM',html(String(from.from).toUpperCase())],['SUPERCRUISE',`≈ ${duration(from.cruise)}`]]),'A rough supercruise estimate: no slowdowns or gravity wells.'):'';
  const value=facts.estimated_value||body._survey?.value;
  const organics=(facts.organics||[]).map(o=>`<li><b>${html(o.name)}</b><em>${html(String(o.state).toUpperCase())}</em></li>`).join('');
  const genera=(facts.genera||[]).filter(g=>!(facts.organics||[]).some(o=>String(o.name).toLowerCase().includes(String(g).toLowerCase()))).map(g=>`<li><b>${html(g)}</b><em>SIGNAL</em></li>`).join('');
  const survey=section('SURVEY',[value?`<div class="sm-value"><small>${body._survey?.value?'PERSONAL SURVEY VALUE':'ESTIMATED VALUE'}</small><b>${number(value,0)} CR</b></div>`:'',facts.dss?`<p class="sm-line">DSS ${number(facts.dss.probes,0)} / ${number(facts.dss.target,0)} PROBES${facts.dss.efficient?' · EFFICIENT':''}</p>`:'',organics||genera?`<ul class="sm-list">${organics}${genera}</ul>`:'',facts.codex?.length?`<p class="sm-line">CODEX: ${facts.codex.map(html).join(' · ')}</p>`:'',facts.notes?.length?`<p class="sm-line notable">${facts.notes.map(html).join(' · ')}</p>`:''].join(''));
  const mix=list=>(list||[]).slice(0,5).map(r=>`<li><b>${html(r.name)}</b><em>${number(r.percent,1)}%</em></li>`).join('');
  const materials=(facts.materials||[]).slice(0,8).map(r=>`<li><b>${html(r.name)}</b><em>${number(r.percent,1)}%</em></li>`).join('');
  const composition=section('COMPOSITION',[facts.atmosphere_composition?.length?`<p class="sm-sub">ATMOSPHERE</p><ul class="sm-list">${mix(facts.atmosphere_composition)}</ul>`:'',materials?`<p class="sm-sub">SURFACE MATERIALS</p><ul class="sm-list">${materials}</ul>`:'',facts.composition?`<p class="sm-sub">BODY</p><ul class="sm-list">${Object.entries(facts.composition).map(([k,v])=>`<li><b>${html(k)}</b><em>${number(v,1)}%</em></li>`).join('')}</ul>`:''].join(''));
  const rings=section('RINGS',(body.rings||[]).map(r=>`<div class="sm-ring"><b>${html(String(r.name||'').replace(body.name,'').trim()||'Ring')}</b><span>${html(String(r.type).toUpperCase())}</span>${r.hotspots?.length?`<p>${r.hotspots.map(h=>`<em>${html(h.material)} ×${number(h.count,0)}</em>`).join('')}</p>`:''}</div>`).join(''),(body.rings||[]).some(r=>r.hotspots?.length)?'Hotspots from your ring scans. Where in the ring they sit is not in the data.':'');
  const placed=scene?.stationsAt(body.bodyId)||[];
  const stationRows=[...placed.map(p=>`<li><b>${p.kind==='station'?'◇':'⛴'} ${html(p.name)}</b><em>${html(String(p.type).toUpperCase())}${p.alt?` · OR NEAR ${html(p.alt.toUpperCase())}`:''}</em></li>`),...(body.surfaceStations||[]).map(s=>`<li><b>⌂ ${html(s.name)}</b><em>${html(String(s.type||'SETTLEMENT').toUpperCase())}${valid(s.latitude)?` · ${number(s.latitude,2)}°, ${number(s.longitude,2)}°`:''}</em></li>`)].join('');
  const stations=section('STATIONS, SETTLEMENTS & CARRIERS',stationRows?`<ul class="sm-list">${stationRows}</ul>`:'',placed.length?'Orbital stations and carriers are placed at the body that was at their reported distance when they were reported. Carriers may have jumped since.':'');
  const places=(latest.system.places||[]).filter(p=>scene?.nodeFor(null,p.body)?.data.bodyId===body.bodyId);
  const yours=section('YOUR PLACES',places.length?`<ul class="sm-list">${places.map(p=>`<li><b>${p.kind==='site'?'✚':'⚐'} ${html(p.label)}</b><em>${p.kind==='site'?'SAVED SITE':`EXPEDITION STOP${p.reached?' · REACHED':''}`}${valid(p.lat)?` · ${number(p.lat,2)}°, ${number(p.lon,2)}°`:''}</em></li>`).join('')}</ul>`:'');
  let eclipses='';if(!star&&scene){const result=scene.eclipses(body.bodyId);
    eclipses=section('ECLIPSES',result.events?(result.events.length?result.events.slice(0,4).map(e=>eclipseCard(e,String(result.star.name||''))).join(''):`<p class="sm-line">No eclipse of ${html(result.star.name)} in the next ${number(result.span,0)} days.</p>`):`<p class="sm-line">${result.reason==='orbit'?'Needs this world\'s full orbit to predict.':'No star with a known size to cast a shadow.'}</p>`,result.events?.length?'Mid-eclipse in game time, with the star and the shadowing body at their true sizes as seen from the surface.':'');}
  let day='';const sites=star?[]:scene?.sitesOn(body.bodyId)||[];
  if(sites.length){const now=scene.time,parts=sites.map(site=>{const info=dayNightFor(body,site);if(!info||info.reason)return `<li><b>${html(site.name)}</b><em>${info?.reason==='spin'?'SPINS FREELY: NO ROTATION PHASE IN THE DATA':'NEEDS THE FULL ORBIT'}</em></li>`;
      const up=info.now.up,next=up?info.set:info.rise;return `<li><b>${up?'☀':'☾'} ${html(site.name)}</b><em>${up?'DAY':'NIGHT'} · STAR ${number(info.now.alt,0)}°${next?` · ${up?'SETS':'RISES'} ${until(next,now)}`:info.toStar?' · LOCKED TO ITS STAR':''}${info.day?` · DAY ${number(info.day*24,1)} H`:''}</em></li>`;}).join('');
    day=section('DAY & NIGHT',`<ul class="sm-list">${parts}</ul>`,'For tidally locked worlds. Assumes 0° longitude faces the parent; not yet checked in the game.');}
  const surface=!star&&body._resolved&&scene?`<button type="button" class="sm-surface-open" data-sm="surface" data-body="${body.bodyId}">VIEW THE SKY FROM ${html(String(body.name||'').toUpperCase())}</button>`:'';
  const markup=`<header class="sm-body-heading"><small>${html(star?'STELLAR TELEMETRY':'PLANETARY TELEMETRY')}</small><h3>${html(body.name)}</h3><p>${html(body.subType||body.type)}</p></header><div class="sm-flags">${flags.map(v=>`<span>${html(v)}</span>`).join('')}</div><p class="sm-position-note${body._resolved?'':' uncertain'}">${note}</p>${surface}${travel}${rows(telemetry)}${survey}${composition}${rings}${stations}${yours}${eclipses}${day}<footer class="sm-evidence"><b>${html(body._source==='journal+spansh'?'JOURNAL + SPANSH':body._source==='journal'?'YOUR JOURNAL':'SPANSH CATALOGUE')}</b><p>Public records do not count as your scans, mappings or discoveries. Surface patterns are illustrative.</p></footer>`;
  if(markup!==detailKey){node.querySelector('#sm-detail').innerHTML=markup;detailKey=markup;}
  node.querySelector('#sm-light').hidden=star;
}

function enterSurface(id){if(!scene)return;const result=scene.enterSurface(id);if(!result)return;const node=root();
  node.querySelector('#sm-surface-target').innerHTML=result.targets.map(t=>`<option value="${t.id}"${t.id===result.target?' selected':''}>${html(t.name)} · ${t.ang>=1?`${number(t.ang,2)}°`:t.ang*60>=1?`${number(t.ang*60,1)}′`:`${number(t.ang*3600,1)}″`} WIDE</option>`).join('');
  for(const [key,value]of [['el',20],['az',0]]){node.querySelector(`#sm-surface-${key}`).value=value;node.querySelector(`#sm-surface-${key}-out`).textContent=`${value}°`;}
  node.querySelector('#sm-surface-body').textContent=scene.short(scene.nodes.get(id).data);syncSurface();syncControls();}
function syncSurface(){const node=root();if(!node)return;const on=Boolean(scene?.surface);node.querySelector('#sm-surface').hidden=!on;node.classList.toggle('sm-surfacing',on);}

const validSelect=id=>(latest?.system?.bodies||[]).some(b=>b.bodyId===Number(id));
function select(id,{fly=true}={}){selection=id;scene?.select(id,{fly,notify:false});syncSurface();renderList();renderDetail();}
function receiveState(state){if(state.error){showError(state.error);return;}const node=root();if(!node)return;node.querySelector('#sm-clock').textContent=`${gameTime(state.time)}:${new Date(state.time).toISOString().slice(17,19)}${state.live?' · LIVE':''}`;
  if(Boolean(state.surface)!==!node.querySelector('#sm-surface').hidden)syncSurface();
  const body=(latest?.system?.bodies||[]).find(b=>b.bodyId===selection);
  if(body&&body.type!=='Star'){const stars=(latest.system.bodies||[]).filter(b=>b.type==='Star'&&scene?.known.has(b.bodyId)).slice(0,4);const markup=stars.map((star,i)=>{const light=state.eclipse[i];return `<div><b>${html(star.name)}</b><span>${light?.fraction===null||!light?'UNRESOLVED':`${number(light.fraction*100,1)}% VISIBLE`}</span>${light?.by?`<small>Shadow cast by ${html(light.by)}</small>`:''}</div>`;}).join('')||'<p>Waiting for resolved stellar positions.</p>';const slot=node.querySelector('#sm-starlight');if(slot.innerHTML!==markup)slot.innerHTML=markup;}
  // The simulated clock moves day and night on: refresh the inspector each game minute when live,
  // and every two seconds while the clock runs fast or is set by hand.
  const minute=Math.floor(state.time/60000),now=performance.now();
  if(selection!==null&&(state.live?minute!==receiveState.minute:minute!==receiveState.minute&&now-(receiveState.at||0)>2000)){receiveState.minute=minute;receiveState.at=now;renderDetail();}
}
function showError(message){const empty=root()?.querySelector('#sm-empty');if(empty){empty.hidden=false;empty.innerHTML=`<i>◎</i><b>SYSTEM MAP GRAPHICS UNAVAILABLE</b><p>${html(message)}</p><button type="button" id="sm-retry">RETRY GRAPHICS</button>`;empty.querySelector('button').onclick=()=>{scene?.dispose();scene=null;loading=null;fingerprint='';ensureScene();};}}

async function ensureScene(){if(scene||loading||!(active||warm)||!root())return;const ticket=epoch;loading=import('./system-map/scene.js');
  try{const module=await loading;if(ticket!==epoch||!(active||warm)||!root())return;const saved=readView();
    scene=new module.SystemMapScene(root().querySelector('#sm-stage'),{onSelect:id=>select(id,{fly:false}),onState:receiveState,quality:saved.quality||'standard'});
    for(const key of ['orbits','labels','stations'])if(typeof saved[key]==='boolean')scene.view[key]=saved[key];
    surveyFilter=saved.filter||'all';if(saved.survey)scene.setSurvey(true,surveyFilter);
    if(latest){scene.setData(latest.system);fingerprint=JSON.stringify(latest.system);}
    const empty=root().querySelector('#sm-empty');empty.innerHTML='<i aria-hidden="true">◎</i><b>AWAITING SYSTEM BODIES</b><p>Your journal scans and public Spansh data build this system.</p>';empty.hidden=!!latest?.system?.bodies?.some(b=>b.type!=='Barycentre');
    if(saved.trueScale)scene.setScale(true);scene.setActive(active&&!document.hidden);if(!active)scene.warmUp();applySelection();syncControls();renderYou();renderList();
  }catch(error){showError(error.message||String(error));}finally{if(ticket===epoch)loading=null;}
}
function applySelection(){const rows=latest?.system?.bodies||[];if(pendingSelection&&String(pendingSelection.system).toLowerCase()===String(latest?.system?.name).toLowerCase()){const b=rows.find(b=>String(b.bodyId)===String(pendingSelection.bodyId)||b.name?.toLowerCase()===pendingSelection.name?.toLowerCase());if(b){if(scene)pendingSelection=null;select(b.bodyId);return;}}
  if(selection!==null&&scene&&scene.selected!==selection&&validSelect(selection))scene.select(selection,{fly:false,notify:false});
  if(selection===null||!validSelect(selection)){const target=latest?.system?.target||{};const b=rows.find(b=>String(b.bodyId)===String(target.body_id??target.id??target.body))||rows.find(b=>b.type==='Planet')||rows.find(b=>b.type==='Star');if(b)select(b.bodyId,{fly:false});}
}
function renderYou(){const chip=root()?.querySelector('#sm-you');if(!chip)return;const text=scene?.youSummary()||'';chip.hidden=!text;chip.querySelector('span').textContent=text?`YOU ARE HERE · ${text}`:'';chip.disabled=!scene?.youNode;}

export function renderSystemMap(data){if(!data?.system)return;const nextProfile=String(data.profile_key||'default');if(profile&&profile!==nextProfile)resetSystemMap();profile=nextProfile;
  const changed=latest?.system?.name!==data.system.name||latest?.system?.id64!==data.system.id64;latest=data;
  // The map lives in Explore's SYSTEM MAP tab; until Explore has drawn it, keep the data for later.
  const fresh=skeleton(),node=root();if(!node)return;
  if(changed||fresh){selection=changed?null:selection;detailKey='';if(changed){node.querySelector('#sm-detail').textContent='Select a body to inspect its telemetry.';node.querySelector('#sm-light').hidden=true;}}
  node.querySelector('#sm-system').textContent=data.system.name||'Waiting for your current system';node.querySelector('#sm-source').textContent=data.catalogue?.detail||'Journal link active';node.querySelector('#sm-source').dataset.status=data.catalogue?.status||'waiting';
  const empty=node.querySelector('#sm-empty');if(!node.querySelector('#sm-retry')){empty.hidden=!!data.system.bodies?.some(b=>b.type!=='Barycentre');if(!empty.hidden){empty.querySelector('b').textContent=data.system.name?'AWAITING SYSTEM BODIES':'AWAITING JOURNAL LINK';empty.querySelector('p').textContent=data.catalogue?.status==='loading'?'Fetching Spansh data. Journal scans will appear as they arrive.':'Your own scans will build the map even when public data is unavailable.';}}
  const key=JSON.stringify(data.system);if(scene&&key!==fingerprint){scene.setData(data.system);fingerprint=key;}
  renderYou();renderList();applySelection();renderDetail();if(active||warm)ensureScene();
}
export function openSystemMap({system='',bodyId='',name=''}={}){pendingSelection={system,bodyId,name};context?.showPage('system-map');applySelection();}
export function installSystemMap(ui){context=ui;document.addEventListener('visibilitychange',()=>scene?.setActive(active&&!document.hidden));window.addEventListener('pagehide',()=>resetSystemMap());}
// Active: the SYSTEM MAP tab is showing, so it draws. Warm: Explore is open, so the scene is built
// and its shaders compile in the background, ready for the tab.
export function setSystemMapActive(value,warming=false){active=!!value;warm=!!warming;if(skeleton()&&latest)renderSystemMap(latest);scene?.setActive(active&&!document.hidden);if(scene&&!active&&warm)scene.warmUp();if(active||warm)ensureScene();if(!active)saveView();}
export function resetSystemMap(){epoch++;scene?.dispose();scene=null;loading=null;latest=null;selection=null;pendingSelection=null;fingerprint='';listKey='';detailKey='';filter='';profile='';dayCache=new Map();const node=root();if(node?.dataset.mounted){node.querySelector('#sm-filter').value='';node.classList.remove('sm-expanded','sm-surfacing');const expand=node.querySelector('[data-sm="expand"]');expand.setAttribute('aria-pressed','false');expand.textContent='EXPAND MAP';node.querySelector('#sm-system').textContent='Waiting for your current system';node.querySelector('#sm-source').textContent='';node.querySelector('#sm-bodies').replaceChildren();node.querySelector('#sm-detail').textContent='Select a body to inspect its telemetry.';node.querySelector('#sm-light').hidden=true;node.querySelector('#sm-surface').hidden=true;node.querySelector('#sm-you').hidden=true;}}
export function systemMapState(){return scene?.state()||{renderer:'pending',active};}
