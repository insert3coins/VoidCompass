import * as THREE from "/galactic_map/vendor/three.module.min.js";
import {orbitFrames,relPos} from "./orbits.js";
import {starColor,starKind,starMaterial,promMaterial,addJets,coronaTex,flatTex,palette,
  bodyMaterial,atmRecipe,atmMaterial,ringStrip,ringMaterial,STAR_T,SurfaceBaker} from "./materials.js";
import {SystemModel,radiusMm,cruiseSeconds} from "./astro.js";

const DEG=Math.PI/180;
const valid=v=>v!==null&&v!==undefined&&Number.isFinite(Number(v));
const circleCover=(sun,occ,sep)=>{
  if(sep>=sun+occ)return 0;
  if(sep<=Math.abs(sun-occ))return Math.min(1,occ*occ/(sun*sun));
  const s=sun*sun,o=occ*occ,d=sep*sep;
  return (s*Math.acos(Math.max(-1,Math.min(1,(d+s-o)/(2*sep*sun))))
    +o*Math.acos(Math.max(-1,Math.min(1,(d+o-s)/(2*sep*occ))))
    -.5*Math.sqrt(Math.max(0,(-sep+sun+occ)*(sep+sun-occ)*(sep-sun+occ)*(sep+sun+occ))))/(Math.PI*s);
};
// Quality: pixel ratio cap, surface texture size (and for the selected world), bake budget per frame.
export const QUALITY={low:{pr:1,tex:256,sel:512,budget:131072},standard:{pr:1.5,tex:512,sel:1024,budget:524288},high:{pr:2,tex:1024,sel:2048,budget:1048576}};
// The survey layer's filters: what a body must have to stay lit.
export const SURVEY_FILTERS={
  all:()=>true,
  bio:b=>(b._survey?.bio||0)>0,
  geo:b=>(b._survey?.geo||0)>0,
  unmapped:b=>b.type!=='Star'&&!b._survey?.mapped,
  valuable:b=>/Earth-like|Water world|Ammonia/i.test(b.subType||'')||(b._facts?.estimated_value||b._survey?.value||0)>=500000,
  first:b=>b._survey?.wasDiscovered===false,
  landable:b=>b.isLandable===true,
};
const SURVEY_TINT={bio:0x52e08a,geo:0xf0a04a,valuable:0xf4d35e,first:0xc78bff,unmapped:0x5d7a8f,landable:0x7fd8ff,all:0x7fd8ff};
const stamp=s=>{const t=Date.parse(String(s||'').trim().replace(' ','T').replace(/\+00(:00)?$/,'Z'));return Number.isFinite(t)?t:null;};
function spriteTexture(draw,size=64){const c=document.createElement('canvas');c.width=c.height=size;const g=c.getContext('2d');draw(g);const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;return t;}

export class SystemMapScene {
  constructor(stage,{onSelect,onState,quality='standard'}={}) {
    this.stage=stage;this.onSelect=onSelect;this.onState=onState;this.nodes=new Map();this.byId=new Map();this.parentOf=new Map();
    this.world=new Map();this.display=new Map();this.layout=new Map();this.origin=new THREE.Vector3();this.focus=null;this.selected=null;
    this.live=true;this.time=Date.now();this.speed=1;this.active=false;this.raf=0;this.frames=0;this.markers=[];this.surface=null;
    this.survey={on:false,filter:'all'};this.quality=QUALITY[quality]||QUALITY.standard;this.qualityName=QUALITY[quality]?quality:'standard';
    this.view={trueScale:false,orbits:true,labels:true,stations:true,yaw:.55,pitch:.6,distance:110};
    this.pose={yaw:.55,pitch:.6,distance:110};this.target=new THREE.Vector3();this.aim=new THREE.Vector3();
    this.abort=new AbortController();this.motion=matchMedia('(prefers-reduced-motion: reduce)');
    this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,logarithmicDepthBuffer:true,powerPreference:'high-performance'});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,this.quality.pr));this.renderer.setClearColor(0x02050a);
    this.renderer.domElement.tabIndex=0;this.renderer.domElement.setAttribute('aria-label','System map. Drag to orbit, wheel to zoom, click a body. Arrow keys rotate; plus and minus zoom.');
    stage.prepend(this.renderer.domElement);
    this.scene=new THREE.Scene();this.camera=new THREE.PerspectiveCamera(45,1,.00001,1e12);
    this.geometry=new THREE.SphereGeometry(1,80,48);this.ray=new THREE.Raycaster();this.pointer=new THREE.Vector2();
    this.baker=new SurfaceBaker(this.renderer);this.baker.maxBudget=this.quality.budget;
    this.renderTarget=new THREE.WebGLRenderTarget(1,1,{type:THREE.HalfFloatType});
    this.output=new THREE.Scene();this.outputCamera=new THREE.Camera();
    this.outputMaterial=new THREE.ShaderMaterial({uniforms:{map:{value:this.renderTarget.texture}},depthTest:false,depthWrite:false,
      vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}',
      fragmentShader:`uniform sampler2D map;varying vec2 vUv;
      void main(){vec3 c=max(texture2D(map,vUv).rgb*.9,0.);float m=max(c.r,max(c.g,c.b));
      if(m>.8){float k=.8+.2*(1.-exp(-(m-.8)/.2));c=mix(c*k/m,vec3(k),clamp((m-1.)/5.,0.,.8));}
      c=mix(c*12.92,1.055*pow(c,vec3(1./2.4))-.055,step(.0031308,c));gl_FragColor=vec4(c,1.);}`});
    this.output.add(new THREE.Mesh(new THREE.PlaneGeometry(2,2),this.outputMaterial));
    const positions=[];let seed=7569;const random=()=>((seed=Math.imul(seed,1664525)+1013904223>>>0)/4294967296);
    for(let i=0;i<950;i++){const a=random()*Math.PI*2,z=random()*2-1,r=Math.sqrt(1-z*z);positions.push(Math.cos(a)*r*1500,z*1500,Math.sin(a)*r*1500);}
    const skyGeometry=new THREE.BufferGeometry();skyGeometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
    this.sky=new THREE.Points(skyGeometry,new THREE.PointsMaterial({color:0x8ea9c0,size:1.1,sizeAttenuation:false,transparent:true,opacity:.45,depthWrite:false}));this.scene.add(this.sky);
    this.textures={
      ring:spriteTexture(g=>{g.strokeStyle='#fff';g.lineWidth=3;g.beginPath();g.arc(128,128,120,0,Math.PI*2);g.stroke();},256),
      dash:spriteTexture(g=>{g.strokeStyle='#fff';g.lineWidth=3;g.setLineDash([14,12]);g.beginPath();g.arc(128,128,120,0,Math.PI*2);g.stroke();},256),
      diamond:spriteTexture(g=>{g.fillStyle='#fff';g.strokeStyle='#02050a';g.lineWidth=5;g.beginPath();g.moveTo(32,8);g.lineTo(56,32);g.lineTo(32,56);g.lineTo(8,32);g.closePath();g.stroke();g.fill();}),
      pin:spriteTexture(g=>{g.fillStyle='#fff';g.strokeStyle='#02050a';g.lineWidth=7;g.beginPath();g.arc(32,32,17,0,Math.PI*2);g.stroke();g.fill();}),
    };
    this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(stage);this.resize();
    const signal=this.abort.signal, canvas=this.renderer.domElement;
    canvas.addEventListener('pointerdown',e=>{if(e.button>2)return;this.drag={id:e.pointerId,x:e.clientX,y:e.clientY,sx:e.clientX,sy:e.clientY};canvas.setPointerCapture(e.pointerId);},{signal});
    canvas.addEventListener('pointermove',e=>{const d=this.drag;if(!d||d.id!==e.pointerId)return;
      if(this.surface){this.surface.look.yaw-=(e.clientX-d.x)*.004;this.surface.look.pitch=Math.max(-1.4,Math.min(1.4,this.surface.look.pitch-(e.clientY-d.y)*.004));}
      else{this.view.yaw-=(e.clientX-d.x)*.006;this.view.pitch=Math.max(-1.5,Math.min(1.5,this.view.pitch+(e.clientY-d.y)*.006));}
      d.x=e.clientX;d.y=e.clientY;this.wake();},{signal});
    canvas.addEventListener('pointerup',e=>{const d=this.drag;this.drag=null;if(d&&!this.surface&&Math.hypot(e.clientX-d.sx,e.clientY-d.sy)<6){const box=canvas.getBoundingClientRect();this.pointer.set((e.clientX-box.left)/box.width*2-1,-(e.clientY-box.top)/box.height*2+1);this.ray.setFromCamera(this.pointer,this.camera);const hit=this.ray.intersectObjects([...this.nodes.values()].filter(n=>n.group.visible).map(n=>n.mesh),false)[0];if(hit)this.select(hit.object.userData.bodyId);}}, {signal});
    canvas.addEventListener('pointercancel',()=>{this.drag=null;},{signal});
    canvas.addEventListener('wheel',e=>{e.preventDefault();if(this.surface)this.surface.fov=Math.max(8,Math.min(100,this.surface.fov*Math.exp(e.deltaY*.0012)));else this.view.distance=Math.max(.0001,Math.min(1e10,this.view.distance*Math.exp(e.deltaY*.0014)));this.wake();},{signal,passive:false});
    canvas.addEventListener('contextmenu',e=>e.preventDefault(),{signal});
    canvas.addEventListener('keydown',e=>{const keys={ArrowLeft:()=>this.view.yaw-=.12,ArrowRight:()=>this.view.yaw+=.12,ArrowUp:()=>this.view.pitch=Math.min(1.5,this.view.pitch+.12),ArrowDown:()=>this.view.pitch=Math.max(-1.5,this.view.pitch-.12),'+':()=>this.view.distance*=.8,'=':()=>this.view.distance*=.8,'-':()=>this.view.distance*=1.25,'0':()=>this.reset()};if(keys[e.key]&&!this.surface){e.preventDefault();keys[e.key]();this.wake();}},{signal});
    canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();this.setActive(false);this.onState?.({error:'Graphics connection interrupted. Reopen the System Map to restore it.'});},{signal});
  }
  resize(){const w=this.stage.clientWidth,h=this.stage.clientHeight;if(w<1||h<1)return;this.width=w;this.height=h;this.renderer.setSize(w,h,false);this.renderTarget.setSize(Math.round(w*this.renderer.getPixelRatio()),Math.round(h*this.renderer.getPixelRatio()));this.camera.aspect=w/h;this.camera.updateProjectionMatrix();this.wake();}
  setQuality(name){const q=QUALITY[name];if(!q)return;this.quality=q;this.qualityName=name;this.renderer.setPixelRatio(Math.min(devicePixelRatio,q.pr));this.baker.maxBudget=q.budget;this.resize();
    for(const node of this.nodes.values())if(node.data.type!=='Star')this.baker.request(node.data,node.material,node.data.bodyId===this.selected?q.sel:q.tex);this.wake();}
  // Compile the scene's shaders ahead of the first frame (into the same target the frames use).
  warmUp(){if(this.warmed||!this.system||this.disposed)return;this.warmed=true;const previous=this.renderer.getRenderTarget();this.renderer.setRenderTarget(this.renderTarget);
    const compiled=this.renderer.compileAsync(this.scene,this.camera);this.renderer.setRenderTarget(previous);compiled.catch(()=>{});}
  setData(system) {
    const changed=this.system?.name!==system.name||this.system?.id64!==system.id64;
    this.system=system;
    if(changed){this.exitSurface(false);this.focus=null;this.selected=null;for(const node of this.nodes.values())this.removeNode(node);this.nodes.clear();this.warmed=false;}
    this.byId=new Map((system.bodies||[]).map(b=>[b.bodyId,{...b,_t0:b._epoch*1000}]));this.parentOf=new Map();
    for(const b of this.byId.values())if(b.bodyId!==0){const chain=(b.parents||[]).flatMap(p=>Object.values(p)).filter(id=>id!==b.bodyId);for(let i=0;i<chain.length;i++){const child=i?chain[i-1]:b.bodyId;if(!this.parentOf.has(child)&&child!==0)this.parentOf.set(child,chain[i]);}}
    orbitFrames(this.byId,this.parentOf);this.model=new SystemModel(this.byId,this.parentOf);this.eclipseCache=new Map();
    for(const [id,node]of this.nodes)if(!this.byId.has(id)){this.removeNode(node);this.nodes.delete(id);}
    for(const b of this.byId.values()) {
      if(b.type==='Barycentre')continue;
      const signature=JSON.stringify([b.type,b.subType,b.radius,b.solarRadius,b.spectralClass,b.rings,b.atmosphereType,b.surfaceTemperature,b.atmosphereComposition,b.solidComposition,b.surfacePressure]);
      let node=this.nodes.get(b.bodyId);
      if(node?.signature!==signature){if(node)this.removeNode(node);node=this.createNode(b);node.signature=signature;this.nodes.set(b.bodyId,node);}
      node.data=b;node.approx=!!b._approx;
      this.surveyLabel(node);
      node.label.classList.toggle('scanned',!!b._survey?.scanned);node.label.title=b._resolved?`${b.name} · ${b._source}`:b._approx?`${b.name} · orbital phase unknown, placed approximately`:`${b.name} · orbital position unavailable`;
    }
    this.layoutOverview();
    for(const node of this.nodes.values()){const b=node.data,orbitKey=JSON.stringify([b.parents,b._resolved,b._approx,b.semiMajorAxis,b.orbitalEccentricity,b.orbitalInclination,b.ascendingNode,b.argOfPeriapsis,b.axialTilt,b._F,this.layout.get(b.bodyId)]);if(node.orbitKey!==orbitKey){node.orbitKey=orbitKey;this.orbitLine(node);}}
    this.lightTime=null;this.positions();this.buildMarkers();if(changed)this.reset(true);this.wake();
  }
  short(b){const name=String(b.name||b.bodyId);return name.toLowerCase().startsWith((this.system.name+' ').toLowerCase())?name.slice(this.system.name.length+1):name;}
  createNode(b) {
    const group=new THREE.Group(),tilt=new THREE.Group();group.add(tilt);this.scene.add(group);
    const star=b.type==='Star',solar=b.solarRadius>0?b.solarRadius:.5,planet=b.radius>0?b.radius:1000;
    const radius=star?solar*695.7:planet/1000;
    const size=star?1.7+Math.log10(1+solar*5)*.7:.32+Math.log10(1+planet/1000)*.32;
    const K=star?starKind(b):null,material=star?(K.kind===3?new THREE.MeshBasicMaterial({color:0x020205}):starMaterial(b,new THREE.Color(starColor(b)),K)):bodyMaterial(flatTex);
    const mesh=new THREE.Mesh(this.geometry,material);mesh.scale.setScalar(radius);mesh.userData.bodyId=b.bodyId;tilt.add(mesh);
    const radiusKnown=star?valid(b.solarRadius)&&b.solarRadius>0:valid(b.radius)&&b.radius>0;
    const node={group,tilt,mesh,material,radius,size,radiusKnown,data:b,mats:[material],rings:[]};
    if(star&&K.halo){const halo=new THREE.Sprite(new THREE.SpriteMaterial({map:coronaTex(K.halo),color:starColor(b),transparent:true,blending:THREE.AdditiveBlending,depthWrite:false,opacity:.36}));halo.scale.setScalar(radius*K.halo);tilt.add(halo);}
    if(star&&[0,4].includes(K.kind)){const prom=new THREE.Mesh(new THREE.PlaneGeometry(2.8,2.8),promMaterial(new THREE.Color(starColor(b))));prom.scale.setScalar(radius);tilt.add(prom);node.prom=prom;}
    if(star&&K.kind===2)addJets(tilt,radius,new THREE.Color(starColor(b)));
    if(!star){material.uniforms.uTint.value.setRGB(...palette(b)[0].map(v=>v/255));material.uniforms.uKind.value=/giant/i.test(b.subType||'')?0:1;
      this.baker.request(b,material,this.quality.tex);
      const recipe=atmRecipe(b);if(recipe){const atmosphere=new THREE.Mesh(this.geometry,atmMaterial(recipe));atmosphere.scale.setScalar(radius*(1+recipe.hf));atmosphere.renderOrder=2;tilt.add(atmosphere);node.mats.push(atmosphere.material);node.atmosphere=atmosphere;}
      if(b.rings?.length){const strip=ringStrip(b);node.strip=strip;for(const r of b.rings){const ring=new THREE.Mesh(new THREE.RingGeometry(r.innerRadius/1e6,r.outerRadius/1e6,192),ringMaterial(b,strip));ring.rotation.x=-Math.PI/2;tilt.add(ring);node.mats.push(ring.material);node.rings.push(ring);}
        material.uniforms.uRing.value.set(strip.rin,strip.rout,.92,1);material.uniforms.uRingTex.value=strip.tex;}
    }
    // The survey layer's halo: a ring round the body in its category's colour.
    node.halo=new THREE.Sprite(new THREE.SpriteMaterial({map:this.textures.ring,transparent:true,depthWrite:false,opacity:.9}));node.halo.visible=false;group.add(node.halo);
    const label=document.createElement('button');label.type='button';label.className='sm-label';label.dataset.bodyId=b.bodyId;label.onclick=()=>this.select(b.bodyId);label.textContent=this.short(b);this.stage.append(label);node.label=label;
    return node;
  }
  removeNode(node){this.baker.cancel(node.material);node.label.remove();node.group.removeFromParent();if(node.line){node.line.removeFromParent();node.line.geometry.dispose();node.line.material.dispose();}node.strip?.tex.dispose();node.group.traverse(o=>{if(o.geometry&&o.geometry!==this.geometry)o.geometry.dispose();if(o.material){for(const m of Array.isArray(o.material)?o.material:[o.material])m.dispose();}});}
  // Overview: true directions, but each family placed outside its inner neighbours' reach, so moons,
  // rings and neighbouring planets never overlap however compressed the distances are.
  layoutOverview(){
    const kids=new Map(),axis=id=>{const b=this.byId.get(id);return b?.semiMajorAxis||(b?.distanceToArrival||0)/499;};
    for(const [child,parent]of this.parentOf){if(!kids.has(parent))kids.set(parent,[]);kids.get(parent).push(child);}
    for(const list of kids.values())list.sort((a,b)=>axis(a)-axis(b));
    const own=id=>{const n=this.nodes.get(id);if(!n)return 0;return Math.max(n.size,n.strip?n.strip.rout*n.size/n.radius:0);};
    const stellar=id=>{const b=this.byId.get(id);return !b||b.type==='Star'||(b.type==='Barycentre'&&(kids.get(id)||[]).some(c=>this.byId.get(c)?.type==='Star'));};
    // Each body keeps its compressed true distance unless its family would overlap the one inside it.
    const logRadius=(id,parent)=>{const len=(this.byId.get(id)?.semiMajorAxis||0)*149597.8707;return stellar(parent)?5+Math.log10(1+len)*6.5:1.7+Math.log10(1+len)*.9;};
    this.layout=new Map();
    const extent=(id,depth=0)=>{
      const list=kids.get(id)||[];let cursor=own(id);if(depth>12||!list.length)return cursor;
      const gap=stellar(id)?1.2:.3;cursor+=gap;
      for(const child of list){const e=extent(child,depth+1),r=Math.max(logRadius(child,id),cursor+e);this.layout.set(child,r);cursor=r+e+gap;}
      return cursor;
    };
    for(const id of this.byId.keys())if(!this.parentOf.has(id))extent(id);
  }
  relative(b,anomaly) {
    const p=relPos(b,this.time,anomaly);if(this.view.trueScale)return p;
    const length=Math.hypot(p.x,p.y,p.z)||1,r=this.layout.get(b.bodyId)??(5+Math.log10(1+length)*6.5);
    return {x:p.x/length*r,y:p.y/length*r,z:p.z/length*r};
  }
  orbitLine(node){if(node.line){node.line.removeFromParent();node.line.geometry.dispose();node.line.material.dispose();node.line=null;}const b=node.data;if(!(b._resolved||b._approx)||!this.parentOf.has(b.bodyId))return;
    const points=[];for(let i=0;i<=240;i++){const p=this.relative(b,i/240*Math.PI*2);points.push(new THREE.Vector3(p.x,p.z,-p.y));}
    const geometry=new THREE.BufferGeometry().setFromPoints(points);
    node.line=b._approx?new THREE.Line(geometry,new THREE.LineDashedMaterial({color:0x7a6a3c,transparent:true,opacity:.35,dashSize:.6,gapSize:.5})):new THREE.Line(geometry,new THREE.LineBasicMaterial({color:0x416477,transparent:true,opacity:.28}));
    if(b._approx){node.line.computeLineDistances();const s=this.view.trueScale?Math.max(1,(b.semiMajorAxis||1)*1500):1;node.line.material.dashSize=.6*s;node.line.material.gapSize=.5*s;}
    node.line.frustumCulled=false;this.scene.add(node.line);
  }
  positions(){
    this.world.clear();this.display.clear();const known=new Set(),visiting=new Set();
    const get=id=>{if(this.world.has(id))return;const b=this.byId.get(id);if(!b||visiting.has(id))return;visiting.add(id);
      const parent=this.parentOf.get(id);let world=new THREE.Vector3(),display=new THREE.Vector3();
      if(id===0){known.add(id);}else if((b._resolved||b._approx)&&parent!==undefined){get(parent);if(known.has(parent)){const p=relPos(b,this.time),d=this.relative(b);world=this.world.get(parent).clone().add(new THREE.Vector3(p.x,p.z,-p.y));display=this.display.get(parent).clone().add(new THREE.Vector3(d.x,d.z,-d.y));known.add(id);}}
      visiting.delete(id);this.world.set(id,world);this.display.set(id,display);
    };
    for(const id of this.byId.keys())get(id);
    let unknown=0,reach=8;for(const p of this.display.values())reach=Math.max(reach,p.length());
    for(const [id,node]of this.nodes){node.known=known.has(id);if(!node.known)this.display.set(id,new THREE.Vector3((unknown++-2)*3.2,-reach*.3,-reach*.5));}
    this.known=known;
    const P=this.view.trueScale?this.world:this.display;
    if(this.focus!==null&&P.has(this.focus))this.aim.copy(P.get(this.focus));else this.aim.set(0,0,0);
    const step=this.motion.matches||this.surface?1:.16;this.target.lerp(this.aim,step);this.origin.copy(this.target);
    for(const [id,node]of this.nodes){node.group.visible=!this.view.trueScale||(node.known&&node.radiusKnown);node.group.position.copy(P.get(id)||new THREE.Vector3()).sub(this.origin);const scale=this.view.trueScale?1:node.size/node.radius;node.tilt.scale.setScalar(scale);
      const F=node.data._F;if(F){const R=[[F[0][0],F[0][2],-F[0][1]],[F[2][0],F[2][2],-F[2][1]],[-F[1][0],-F[1][2],F[1][1]]];node.tilt.setRotationFromMatrix(new THREE.Matrix4().set(...R[0],0,...R[1],0,...R[2],0,0,0,0,1));}
      if(node.line){node.line.visible=this.view.orbits&&node.known&&!this.surface;node.line.position.copy(P.get(this.parentOf.get(id))||new THREE.Vector3()).sub(this.origin);}
      const reachDisplay=this.view.trueScale?Math.max(node.radius,node.strip?.rout||0):Math.max(node.size,(node.strip?.rout||0)*node.size/node.radius);node.reach=reachDisplay;
      const match=this.survey.on&&node.data.type!=='Star'&&this.survey.filter!=='all'&&SURVEY_FILTERS[this.survey.filter]?.(node.data);
      const tint=match?SURVEY_TINT[this.survey.filter]:this.survey.on?this.surveyTint(node.data):null;
      node.halo.visible=Boolean(tint)&&node.group.visible&&!this.surface;if(node.halo.visible){node.halo.material.color.setHex(tint);node.halo.scale.setScalar(reachDisplay*3.1);}
    }
  }
  surveyTint(b){if(b.type==='Star')return null;if(SURVEY_FILTERS.bio(b))return SURVEY_TINT.bio;if(SURVEY_FILTERS.valuable(b))return SURVEY_TINT.valuable;if(SURVEY_FILTERS.geo(b))return SURVEY_TINT.geo;if(SURVEY_FILTERS.first(b))return SURVEY_TINT.first;return null;}
  setSurvey(on,filter){this.survey={on:!!on,filter:SURVEY_FILTERS[filter]?filter:'all'};for(const node of this.nodes.values())this.surveyLabel(node);for(const m of this.markers)if(m.kind==='hotspot')m.object.visible=this.survey.on||m.bodyId===this.selected;this.wake();}
  surveyMatch(b){return !this.survey.on||this.survey.filter==='all'||Boolean(SURVEY_FILTERS[this.survey.filter]?.(b));}
  surveyLabel(node){const b=node.data,s=b._survey||{},badge=[];
    if(this.survey.on&&b.type!=='Star'){if(s.bio)badge.push(`BIO ${s.bio}`);if(s.geo)badge.push(`GEO ${s.geo}`);if(s.mapped)badge.push('DSS ✓');const value=b._facts?.estimated_value||s.value;if(value>=100000)badge.push(`${(value/1e6).toFixed(value>=1e7?0:1)}M`);if(s.wasDiscovered===false)badge.push('★ FIRST');}
    const text=this.short(b)+(b._approx?' ≈':'')+(badge.length?` · ${badge.join(' · ')}`:'');if(node.label.textContent!==text){node.label.textContent=text;node.labelW=0;}
    node.label.classList.toggle('dimmed',this.survey.on&&!this.surveyMatch(b));}
  // ---- markers: you, the target, stations, carriers, surface pins, ring hotspots
  clearMarkers(){for(const m of this.markers){m.object.removeFromParent();m.object.material?.dispose();m.object.geometry?.dispose();m.label?.remove();}this.markers=[];}
  marker(kind,{texture,color,size=.03,parent,position=[0,0,0],text='',title='',bodyId=null,attenuate=['you','target','stop'].includes(kind),priority=1,click=null}){
    const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:this.textures[texture],color,transparent:true,depthWrite:false,depthTest:kind==='pin',sizeAttenuation:attenuate}));
    sprite.scale.setScalar(size);sprite.position.set(...position);sprite.renderOrder=4;(parent||this.scene).add(sprite);
    let label=null;if(text){label=document.createElement('button');label.type='button';label.className=`sm-label sm-mark sm-mark-${kind}`;label.textContent=text;label.title=title||text;label.hidden=true;label.onclick=()=>{if(bodyId!==null)this.select(bodyId);};this.stage.append(label);}
    const m={kind,object:sprite,label,bodyId,priority,click,size};this.markers.push(m);return m;
  }
  nodeFor(id,name){if(id!==null&&id!==undefined&&this.nodes.has(Number(id)))return this.nodes.get(Number(id));const n=String(name||'').toLowerCase();if(!n)return null;
    for(const node of this.nodes.values()){const full=String(node.data.name||'').toLowerCase();if(full===n||this.short(node.data).toLowerCase()===n)return node;}return null;}
  surfacePoint(lat,lon){const la=lat*DEG,lo=lon*DEG;return [Math.cos(la)*Math.cos(lo)*1.012,Math.sin(la)*1.012,-Math.cos(la)*Math.sin(lo)*1.012];}
  buildMarkers(){
    this.clearMarkers();const sys=this.system||{},you=sys.you||{},model=this.model;this.placed=[];
    // Stations and carriers from the public catalogue, placed at the body that was at their reported distance.
    const perBody=new Map();
    const add=(entry,node)=>{const list=perBody.get(node)||[];list.push(entry);perBody.set(node,list);};
    for(const st of sys.stations||[]){const carrier=/carrier/i.test(st.type||'');const at=stamp(st.updateTime);const place=model?.placeByDistance(st.distanceToArrival,at);
      const node=place?this.nodes.get(place.body.bodyId):null;const entry={kind:carrier?'carrier':'station',name:carrier&&st.carrierName?`${st.carrierName} ${st.name}`:st.name,type:st.type||'Station',st,alt:place?.alt?this.short(place.alt):'',body:node?.data.bodyId??null,seen:at||null};
      this.placed.push(entry);if(node)add(entry,node);}
    for(const fc of sys.carriers||[]){const node=this.nodeFor(null,fc.body);const entry={kind:'own-carrier',name:`${fc.name||'Your carrier'} ${fc.callsign||''}`.trim(),type:'Your fleet carrier',body:node?.data.bodyId??null,own:true};
      this.placed=this.placed.filter(p=>!(p.kind==='carrier'&&fc.callsign&&String(p.st?.name).toUpperCase()===String(fc.callsign).toUpperCase()));this.placed.push(entry);if(node)add(entry,node);}
    for(const [node,list]of perBody)list.forEach((entry,i)=>{const a=i*.9+.4;const m=this.marker(entry.kind,{texture:'diamond',color:entry.kind==='station'?0x7fd8ff:entry.kind==='carrier'?0xf0a04a:0x52e08a,size:.022,parent:node.group,text:`${entry.kind==='station'?'◇':'⛴'} ${entry.name}`,title:`${entry.name} · ${entry.type}${entry.alt?` · near ${this.short(node.data)} or ${entry.alt}`:''}`,bodyId:node.data.bodyId,priority:2});
      m.offset=[Math.cos(a),.35+.12*i,Math.sin(a)];m.node=node;m.station=true;});
    // Surface pins: public settlements and ports, your saved sites, expedition stops, you.
    const pin=(node,lat,lon,kind,color,text)=>{if(!node||!valid(lat)||!valid(lon))return;const m=this.marker('pin',{texture:'pin',color,size:.016,parent:node.mesh,position:this.surfacePoint(lat,lon),text,bodyId:node.data.bodyId,priority:kind==='you'?5:1});m.pinKind=kind;m.node=node;};
    for(const node of this.nodes.values())for(const st of node.data.surfaceStations||[])pin(node,st.latitude,st.longitude,'settlement',0xdfe8ef,`⌂ ${st.name}`);
    for(const place of sys.places||[]){const node=this.nodeFor(null,place.body);if(!node)continue;if(valid(place.lat)&&valid(place.lon))pin(node,place.lat,place.lon,place.kind,place.kind==='site'?0x52e08a:0xf0a04a,`${place.kind==='site'?'✚':'⚐'} ${place.label}`);
      else{const m=this.marker('stop',{texture:'dash',color:0xf0a04a,size:.05,parent:node.group,text:`⚐ ${place.label}`,bodyId:node.data.bodyId,priority:3});m.node=node;m.halo=true;}}
    // Where you are.
    const docked=you.station?.name?this.placed.find(p=>p.body!==null&&String(p.st?.name||p.name).toLowerCase()===String(you.station.name).toLowerCase()):null;
    const here=this.nodeFor(you.body_id,you.body)||(docked?this.nodes.get(docked.body):null);this.youNode=here||null;
    if(here){if(valid(you.lat)&&valid(you.lon)&&(you.landed||you.on_foot||you.srv||you.altitude_m!==null))pin(here,you.lat,you.lon,'you',0x00e5ff,'');
      const m=this.marker('you',{texture:'ring',color:0x00e5ff,size:.07,parent:here.group,text:`▼ YOU · ${this.youText()}`,bodyId:here.data.bodyId,priority:6});m.node=here;m.halo=true;m.pulse=true;}
    // Elite's navigation target.
    const tgt=sys.target||{},targetNode=this.nodeFor(tgt.body_id??tgt.id??tgt.body,tgt.name);this.targetNode=targetNode||null;
    if(targetNode&&targetNode!==here){const m=this.marker('target',{texture:'dash',color:0xffb347,size:.08,parent:targetNode.group,text:'⌖ TARGET',bodyId:targetNode.data.bodyId,priority:5});m.node=targetNode;m.halo=true;}
    // Ring hotspots: dots round the ring they were found in (where in the ring is not in the data).
    for(const node of this.nodes.values())(node.data.rings||[]).forEach(ring=>{if(!ring.hotspots?.length)return;const r=(ring.innerRadius+ring.outerRadius)/2e6,dots=[],colors=[];
      const tints={painite:[.85,.45,1],platinum:[.9,.95,1],'low temperature diamonds':[.7,.95,1],'void opal':[.55,.75,1],tritium:[.5,1,.8],alexandrite:[1,.5,.6]};
      let k=0;for(const spot of ring.hotspots)for(let i=0;i<Math.min(4,spot.count||1);i++,k++){const a=k*2.399;dots.push(Math.cos(a)*r,0,Math.sin(a)*r);colors.push(...(tints[String(spot.material).toLowerCase()]||[1,.85,.4]));}
      const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(dots,3));geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
      const points=new THREE.Points(geometry,new THREE.PointsMaterial({size:7,sizeAttenuation:false,vertexColors:true,transparent:true,depthWrite:false}));node.tilt.add(points);
      this.markers.push({kind:'hotspot',object:points,label:null,bodyId:node.data.bodyId,node});points.visible=this.survey.on||node.data.bodyId===this.selected;});
  }
  youText(){const y=this.system?.you||{},st=y.station;return y.docked?`DOCKED${st?.name?` AT ${st.name.toUpperCase()}`:''}`:y.on_foot?'ON FOOT':y.srv?'IN THE SRV':y.landed?'LANDED':y.state&&/SUPERCRUISE/i.test(y.state)?'SUPERCRUISE':'NEAR';}
  youSummary(){const y=this.system?.you;if(!y)return '';if(this.youNode)return `${this.youText()} · ${this.short(this.youNode.data)}`;if(y.docked&&y.station?.name)return `DOCKED AT ${y.station.name.toUpperCase()}`;
    const tgt=this.system?.target||{};return /SUPERCRUISE/i.test(y.state||'')?`IN SUPERCRUISE${tgt.name?` · HEADING TO ${String(tgt.name).toUpperCase()}`:''}`:'IN THIS SYSTEM';}
  findMe(){if(this.youNode){this.select(this.youNode.data.bodyId);return true;}return false;}
  // ---- facts the inspector asks for
  stationsAt(id){return (this.placed||[]).filter(p=>p.body===id);}
  unplaced(){return (this.placed||[]).filter(p=>p.body===null);}
  fromYou(id){const b=this.byId.get(id);if(!b)return null;const here=this.youNode?.data;
    if(here&&here.bodyId!==id){const ls=this.model.distanceLs(here.bodyId,id,this.time);if(ls!==null)return {ls,from:this.short(here),cruise:cruiseSeconds(ls)};}
    if(!here&&valid(b.distanceToArrival)&&b.distanceToArrival>0)return {ls:b.distanceToArrival,from:'the arrival star',cruise:cruiseSeconds(b.distanceToArrival)};return null;}
  eclipses(id){const key=`${id}|${Math.floor(this.time/3600000)}`;if(!this.eclipseCache.has(key)){if(this.eclipseCache.size>24)this.eclipseCache.clear();this.eclipseCache.set(key,this.model?.eclipses(id,this.time)||{reason:'orbit'});}return this.eclipseCache.get(key);}
  dayNight(id,lat,lon){return this.model?.dayNight(id,lat,lon,this.time)||{reason:'orbit'};}
  sitesOn(id){const node=this.nodes.get(id),y=this.system?.you||{},out=[];if(!node)return out;
    for(const st of node.data.surfaceStations||[])if(valid(st.latitude)&&valid(st.longitude))out.push({name:st.name,kind:st.type||'Settlement',lat:st.latitude,lon:st.longitude});
    for(const p of this.system?.places||[])if(this.nodeFor(null,p.body)===node&&valid(p.lat)&&valid(p.lon))out.push({name:p.label,kind:p.kind==='site'?'Your saved site':'Expedition stop',lat:p.lat,lon:p.lon});
    if(this.youNode===node&&valid(y.lat)&&valid(y.lon))out.unshift({name:'You',kind:'Your position',lat:y.lat,lon:y.lon});
    return out.slice(0,8);}
  // ---- lighting
  visibility(body,star){if(!this.known.has(body.bodyId)||!this.known.has(star.bodyId)||body._approx||!this.nodes.get(star.bodyId)?.radiusKnown)return {fraction:null,by:''};const wb=this.world.get(body.bodyId),ws=this.world.get(star.bodyId),light=ws.clone().sub(wb),d=light.length(),sr=this.nodes.get(star.bodyId)?.radius||0;if(!d||!sr)return {fraction:1,by:''};const a=Math.asin(Math.min(.999,sr/d));let fraction=1,by='';
    for(const [id,n]of this.nodes){if(id===body.bodyId||id===star.bodyId||!n.known||n.approx||!n.radiusKnown||n.data.type==='Star')continue;const occ=this.world.get(id).clone().sub(wb),distance=occ.length();if(!distance||distance>=d||occ.dot(light)<=0)continue;const sep=occ.angleTo(light),cover=circleCover(a,Math.asin(Math.min(.999,n.radius/distance)),sep);if(cover>1-fraction){fraction=1-cover;by=n.data.name;}}
    return {fraction,by};
  }
  lighting(){const stars=[...this.nodes.values()].filter(n=>n.data.type==='Star'&&n.known).slice(0,4),nrm=new THREE.Vector3();
    const measure=this.lightTime===null||this.lightTime===undefined||Math.abs(this.time-this.lightTime)>1000;if(measure)this.lightTime=this.time;
    for(const node of this.nodes.values()){if(node.data.type==='Star')continue;const eclipses=!node.eclipse||measure?stars.map(s=>this.visibility(node.data,s.data)):node.eclipse;node.eclipse=eclipses;
      nrm.set(0,1,0).applyQuaternion(node.tilt.quaternion);
      for(const material of node.mats){const u=material.uniforms;if(!u?.uNStars)continue;u.uNStars.value=stars.length;u.uNight.value=.018;
        for(let i=0;i<stars.length;i++){const s=stars[i];u.uStars.value[i].set(s.group.position.x,s.group.position.y,s.group.position.z,s.radius*(this.view.trueScale?1:s.size/s.radius));u.uStarCol.value[i].set(starColor(s.data));u.uEcl.value[i]=eclipses[i].fraction??1;}
        if(measure||!node.occluders)node.occluders=[...this.nodes.values()].filter(n=>n!==node&&n.known&&!n.approx&&n.data.type!=='Star').sort((a,b)=>a.group.position.distanceToSquared(node.group.position)-b.group.position.distanceToSquared(node.group.position)).slice(0,11);
        const occ=this.view.trueScale?[...node.occluders]:[];
        if(node.rings.some(r=>r.material===material))occ.unshift(node);u.uNOcc.value=occ.length;
        occ.forEach((n,i)=>u.uOcc.value[i].set(n.group.position.x,n.group.position.y,n.group.position.z,n.radius));
        u.uRingN?.value.copy(nrm);u.uRN?.value.copy(nrm);u.uRingC?.value.copy(node.group.position);
      }
    }
  }
  select(id,{fly=true,notify=true}={}){id=Number(id);const node=this.nodes.get(id);if(!node)return;if(this.surface&&this.surface.id!==id)this.exitSurface(false);this.selected=id;
    if(fly){if(node.data.type!=='Star'){this.baker.request(node.data,node.material,this.quality.sel);this.baker.prioritize(node.material);}if(this.view.trueScale&&(!node.known||!node.radiusKnown))this.setScale(false);this.focus=id;const r=this.view.trueScale?Math.max(node.radius,node.strip?.rout||0):Math.max(node.size,(node.strip?.rout||0)*node.size/node.radius);this.view.distance=Math.max(.0001,r*3.7);
      const star=[...this.nodes.values()].find(n=>n.data.type==='Star'&&n!==node&&n.known);if(star){const direction=star.group.position.clone().sub(node.group.position).normalize();if(node.rings.length){const normal=new THREE.Vector3(0,1,0).applyQuaternion(node.tilt.quaternion);if(normal.dot(direction)<0)normal.negate();direction.multiplyScalar(.8).addScaledVector(normal,.9).normalize();}this.view.yaw=Math.atan2(direction.x,direction.z)+.25;this.view.pitch=node.rings.length?Math.asin(direction.y):.45;}}
    for(const [key,n]of this.nodes)n.label.classList.toggle('selected',key===id);for(const m of this.markers)if(m.kind==='hotspot')m.object.visible=this.survey.on||m.bodyId===id;if(notify)this.onSelect?.(id);this.wake();}
  reset(instant=false){if(this.surface)this.exitSurface(false);this.focus=null;this.positions();const P=this.view.trueScale?this.world:this.display;let extent=8;for(const [id,n]of this.nodes)if(n.known){extent=Math.max(extent,(P.get(id)?.length()||0)+(this.view.trueScale?n.radius:n.size)*2);
      if(n.line){n.line.geometry.computeBoundingSphere();const sphere=n.line.geometry.boundingSphere;extent=Math.max(extent,(P.get(this.parentOf.get(id))?.length()||0)+sphere.center.length()+sphere.radius);}}
    this.view.distance=extent*2.2;this.view.yaw=.55;this.view.pitch=.6;if(instant){Object.assign(this.pose,this.view);this.target.set(0,0,0);}this.wake();}
  setScale(trueScale){if(this.view.trueScale===trueScale)return;this.view.trueScale=trueScale;for(const n of this.nodes.values())this.orbitLine(n);if(this.surface)return;const selected=this.selected;this.reset(true);if(selected!==null)this.select(selected,{notify:false});}
  setTime(speed){this.speed=speed;this.live=speed===1;this.wake();}
  step(seconds){this.live=false;this.speed=0;this.time+=seconds*1000;this.wake();}
  // ---- the sky from a world's surface (true scale), standing where a chosen object sits at a set height
  skyTargets(id){const node=this.nodes.get(id);if(!node)return [];const W=this.model.worldAt(this.time),pb=W.get(id);if(!pb)return [];
    return [...this.nodes.values()].filter(n=>n!==node&&n.known&&n.radiusKnown&&!n.approx&&W.get(n.data.bodyId)).map(n=>{const p=W.get(n.data.bodyId),d=Math.hypot(p.x-pb.x,p.y-pb.y,p.z-pb.z);return {id:n.data.bodyId,name:this.short(n.data),type:n.data.type,ang:2*Math.asin(Math.min(1,radiusMm(n.data)/Math.max(d,1e-9)))/DEG};})
      .sort((x,y)=>(y.type==='Star')-(x.type==='Star')||y.ang-x.ang).slice(0,14);}
  enterSurface(id){const node=this.nodes.get(id);if(!node||node.data.type==='Star'||!node.known||node.approx||!node.radiusKnown)return null;const list=this.skyTargets(id);if(!list.length)return null;
    const parent=this.byId.get(this.parentOf.get(id)),pick=(parent&&parent.type!=='Barycentre'&&list.find(x=>x.id===parent.bodyId))||list.find(x=>x.type!=='Star')||list[0];
    this.surface={id,target:pick.id,el:20,az:0,fov:60,look:{yaw:0,pitch:0},trueScale:this.view.trueScale};
    if(!this.view.trueScale){this.view.trueScale=true;for(const n of this.nodes.values())this.orbitLine(n);}
    if(node.atmosphere)node.atmosphere.visible=false;node.label.hidden=true;this.focus=id;this.selected=id;this.wake();return {targets:list,target:pick.id};}
  setSurface(changes){if(!this.surface)return;Object.assign(this.surface,changes);if('target' in changes)this.surface.look={yaw:0,pitch:0};this.wake();}
  exitSurface(fly=true){const s=this.surface;if(!s)return;this.surface=null;const node=this.nodes.get(s.id);if(node?.atmosphere)node.atmosphere.visible=true;this.camera.fov=45;this.camera.up.set(0,1,0);this.camera.updateProjectionMatrix();
    if(!s.trueScale){this.view.trueScale=false;for(const n of this.nodes.values())this.orbitLine(n);}if(fly&&node)this.select(s.id,{notify:false});this.wake();}
  surfacePose(){const s=this.surface,node=this.nodes.get(s.id),aim=this.nodes.get(s.target);if(!node||!aim){this.exitSurface(false);return false;}
    const pb=node.group.position,pt=aim.group.position,t=pt.clone().sub(pb).normalize(),n=new THREE.Vector3(0,1,0).applyQuaternion(node.tilt.quaternion);
    const side=n.clone().addScaledVector(t,-n.dot(t));if(side.lengthSq()<1e-6)side.set(1,0,0).addScaledVector(t,-t.x);side.normalize().applyAxisAngle(t,s.az*DEG);
    const el=s.el*DEG,up=t.clone().multiplyScalar(Math.sin(el)).addScaledVector(side,Math.cos(el)).normalize();
    const eye=pb.clone().addScaledVector(up,node.radius*1.0004+.002),forward=pt.clone().sub(eye).normalize();
    forward.applyAxisAngle(up,s.look.yaw);const right=forward.clone().cross(up).normalize();forward.applyAxisAngle(right,s.look.pitch);
    this.camera.fov=s.fov;this.camera.updateProjectionMatrix();this.camera.position.copy(eye);this.camera.up.copy(up);this.camera.lookAt(eye.clone().add(forward));this.camera.updateMatrixWorld();return true;}
  setActive(active){this.active=active&&!this.disposed;if(!this.active){cancelAnimationFrame(this.raf);this.raf=0;return;}this.last=performance.now();this.resize();this.wake();}
  wake(){if(this.active&&!this.raf&&!this.disposed)this.raf=requestAnimationFrame(t=>this.frame(t));}
  frame(now){this.raf=0;if(!this.active||this.disposed)return;const dt=Math.min(.1,(now-(this.last||now))/1000);this.last=now;this.time=this.live?Date.now():this.time+dt*1000*this.speed;STAR_T.value=this.motion.matches?0:this.time/1000%100000;
    this.positions();
    if(!(this.surface&&this.surfacePose())){const ease=this.motion.matches?1:1-Math.exp(-dt*12);for(const key of ['yaw','pitch','distance'])this.pose[key]+=(this.view[key]-this.pose[key])*ease;
      const {yaw,pitch,distance}=this.pose;this.camera.position.set(Math.sin(yaw)*Math.cos(pitch)*distance,Math.sin(pitch)*distance,Math.cos(yaw)*Math.cos(pitch)*distance);this.camera.up.set(0,1,0);this.camera.lookAt(0,0,0);this.camera.updateMatrixWorld();}
    this.sky.position.copy(this.camera.position);
    for(const node of this.nodes.values())if(node.prom)node.prom.lookAt(this.camera.position);
    this.placeMarkers(now);this.lighting();this.baker.tick();this.renderer.setRenderTarget(this.renderTarget);this.renderer.render(this.scene,this.camera);this.renderer.setRenderTarget(null);this.renderer.render(this.output,this.outputCamera);this.frames++;
    if(now-(this.labelTime||0)>120){this.labelTime=now;this.labels();const node=this.nodes.get(this.selected);this.onState?.({time:this.time,live:this.live,speed:this.speed,trueScale:this.view.trueScale,selected:this.selected,eclipse:node?.eclipse||[],frames:this.frames,surface:Boolean(this.surface)});}
    this.wake();
  }
  // Markers beside a body sit just outside it; halos pulse; everything scales with the body's drawn size.
  placeMarkers(now){for(const m of this.markers){if(m.kind==='hotspot')continue;
    if(m.kind==='pin'){m.object.visible=!this.surface&&m.node.group.visible&&(m.pinKind==='you'||m.node.data.bodyId===this.selected||(this.view.stations&&m.pinKind==='settlement'&&this.view.trueScale));
      if(m.object.visible)m.object.scale.setScalar(m.size/Math.max(1e-9,m.node.mesh.scale.x*m.node.tilt.scale.x));continue;}
    const node=m.node;if(!node)continue;const r=node.reach||node.size;
    if(m.station){m.object.visible=this.view.stations&&node.group.visible&&!this.surface;m.object.position.set(m.offset[0]*r*2.4,m.offset[1]*r*2.4,m.offset[2]*r*2.4);}
    else if(m.halo){m.object.visible=node.group.visible&&!this.surface;const k=m.pulse&&!this.motion.matches?1+.06*Math.sin(now/260):1;m.object.scale.setScalar(r*(m.kind==='you'?2.7:2.45)*k);m.object.material.opacity=m.kind==='you'?.85:.7;}}}
  labels(){const occupied=[],focusId=this.surface?null:this.selected,list=[...this.nodes.values()].map(node=>({el:node.label,object:node.group,priority:node.data.bodyId===focusId?9:(this.survey.on&&!this.surveyMatch(node.data)?0:1),show:this.view.labels&&node.group.visible&&node.data.bodyId!==this.surface?.id,node,w:'labelW'}))
      .concat(this.markers.filter(m=>m.label).map(m=>({el:m.label,object:m.object,priority:m.priority,show:this.view.labels&&m.object.visible&&(m.kind!=='pin'&&m.kind!=='station'&&m.kind!=='carrier'&&m.kind!=='own-carrier'||m.node?.data.bodyId===this.selected),node:m,w:'labelW'})))
      .sort((a,b)=>b.priority-a.priority);
    const world=new THREE.Vector3();
    for(const entry of list){const el=entry.el;entry.object.getWorldPosition(world);const p=world.project(this.camera);let x=(p.x*.5+.5)*this.width,y=(-p.y*.5+.5)*this.height;
      let show=entry.show&&p.z>-1&&p.z<1&&x>4&&x<this.width-4&&y>6&&y<this.height-22;
      if(show){if(!entry.node[entry.w]){el.hidden=false;entry.node[entry.w]=el.offsetWidth||90;}const w=entry.node[entry.w];if(x+w+6>this.width)x=x-w-10;if(x<4)show=false;
        const box=[x,y+14,x+w,y+36];if(show&&entry.priority<9&&occupied.some(b=>box[0]<b[2]&&box[2]>b[0]&&box[1]<b[3]&&box[3]>b[1]))show=false;
        if(show){el.style.transform=`translate(${Math.round(x)}px,${Math.round(y+14)}px)`;occupied.push(box);}}
      el.hidden=!show;}}
  state(){return {renderer:'three',system:this.system?.name,bodies:this.nodes.size,frames:this.frames,active:this.active,selected:this.selected,trueScale:this.view.trueScale,camera:{...this.view},bakes:this.baker.queue.length,
    quality:this.qualityName,surface:Boolean(this.surface),you:this.youNode?.data.bodyId??null,target:this.targetNode?.data.bodyId??null,markers:this.markers.length,survey:{...this.survey},
    layout:Object.fromEntries([...this.layout].map(([id,r])=>[id,+r.toFixed(3)])),placed:(this.placed||[]).map(p=>({name:p.name,kind:p.kind,body:p.body}))};}
  dispose(){this.disposed=true;this.setActive(false);this.abort.abort();this.resizeObserver.disconnect();this.clearMarkers();for(const n of this.nodes.values())this.removeNode(n);this.nodes.clear();this.baker.dispose();this.geometry.dispose();this.sky.geometry.dispose();this.sky.material.dispose();for(const t of Object.values(this.textures))t.dispose();this.renderTarget.dispose();this.output.children[0].geometry.dispose();this.outputMaterial.dispose();this.renderer.dispose();this.renderer.forceContextLoss();this.renderer.domElement.remove();}
}
