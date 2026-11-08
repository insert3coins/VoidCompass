import * as THREE from "../galactic_map/vendor/three.module.min.js";
import {createCompanionFrame, COMPANION_EXTENT} from "./companion-frame.js";
import {SIGNATURES} from "./companion-colours.js";
import {createCompanionCore} from "./companion-core.js";
import {createMood} from "./companion-mood.js";

const TAU = Math.PI * 2;
// The rota's duties, in order round Aster's core (crew_rota.DUTIES).
const DUTIES = ["docked", "scanning", "surface", "route", "deep", "flight"];
// Ship's time, for the watch bells; a page under test may set its own clock.
const shipTime = () => (typeof globalThis.__voidcompassNow === "function" ? globalThis.__voidcompassNow() : Date.now());
// Bells as a ship keeps them: one at half past, two on the hour after, up to
// eight at the end of each four-hour watch.
export function bellsAt(time) {
  const date = new Date(time), index = date.getHours() * 2 + (date.getMinutes() >= 30 ? 1 : 0);
  return {index, count: index % 8 || 8};
}
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const gazeDirections = {up:[0,.7],down:[0,-.7],left:[-.8,0],right:[.8,0],side:[.8,.12],centre:[0,0]};
const watchPoints = [[-.52,.22],[.38,.15],[.08,-.35],[0,0],[.55,-.08],[-.2,.38],[0,0]];

export function createAsterMotion() {
  let time = 0, x = 0, y = 0, aperture = .61, lastSeq = null, attention = 0, pulse = 0;
  let eventX = 0, eventY = 0, activity = "idle";
  function context(model = {}) {
    const previousActivity = activity;
    const label = String(model.state || model.activity || "").toUpperCase();
    activity = /COMBAT|INTERDICT|DANGER/.test(label) ? "wary"
      : /FSS|DSS|SCAN|MAP|EXPLOR/.test(label) ? "scanning"
      : /SURFACE|SRV|FOOT|GLIDE|LANDING/.test(label) ? "surface"
      : /SUPERCRUISE|HYPER|JUMP|FSD/.test(label) ? "ahead"
      : /DOCK|LANDED/.test(label) ? "relaxed" : "idle";
    const events = (model.events || []).filter(row => Number.isFinite(Number(row.seq)));
    const latest = events.reduce((value, row) => Math.max(value, Number(row.seq)), 0);
    if (lastSeq === null || latest < lastSeq) { lastSeq = latest; return activity !== previousActivity; }
    const fresh = events.filter(row => Number(row.seq) > lastSeq).sort((a,b) => Number(a.seq)-Number(b.seq));
    lastSeq = latest;
    if (!fresh.length) { if (activity !== previousActivity) attention = 1; return activity !== previousActivity; }
    const event = fresh.reduce((a,b) => Number(a.weight || 0) > Number(b.weight || 0) ? a : b);
    const direction = model.overlays?.[event.overlay] || gazeDirections[event.gaze] || [Math.sin(latest * 1.7) * .5,.18];
    eventX = clamp(Number(direction[0]) || 0,-1,1);
    eventY = clamp((model.overlays?.[event.overlay] ? -1 : 1) * (Number(direction[1]) || 0),-1,1);
    attention = event.rare ? 4 : 2.2;
    pulse = Math.max(pulse, clamp(Number(event.weight) || .2) * (event.rare ? 1.2 : 1));
    return true;
  }
  function step(dt, {state="idle", idle=true, reduced=false, focus="tracking", intensity=1} = {}) {
    const animated = !reduced && (idle || state !== "idle" || attention > 0);
    const delta = animated ? clamp(dt,0,.12) : 0;
    if (reduced) { attention = 0; pulse = 0; }
    time += delta * intensity;
    attention = Math.max(0, attention - delta);
    pulse *= Math.exp(-delta * 2.4);
    if (pulse < .001) pulse = 0;
    const point = watchPoints[Math.floor(time / 3.7) % watchPoints.length];
    let tx = idle ? point[0] + Math.sin(time * .43) * .05 : 0;
    let ty = idle ? point[1] + Math.cos(time * .31) * .04 : 0;
    let opening = .61;
    if (activity === "scanning") { tx = Math.sin(time * .75) * .65; ty = Math.cos(time * .41) * .22; opening = .72; }
    else if (activity === "surface") { ty -= .28; opening = .56; }
    else if (activity === "ahead") { tx *= .4; ty = .24; opening = .52; }
    else if (activity === "relaxed") { tx *= .55; ty *= .55; opening = .67; }
    if (attention > 0 && state === "idle") { tx = eventX * .75; ty = eventY * .75; opening = .78; }
    if (state === "listening") { tx = Math.sin(time * .3) * .045; ty = .10; opening = .88; }
    else if (state === "working") { tx = Math.sin(time * 1.25) * .48; ty = -.06; opening = .45; }
    else if (state === "speaking") { tx = Math.sin(time * .41) * .065; ty = .08; opening = .72; }
    else if (state === "alert") { tx = Math.sin(time * 1.6) * .22; ty = .04; opening = .32; }
    else if (state === "charging") { tx = 0; ty = .27; opening = .92; }
    const refocus = idle && state === "idle" ? Math.pow(Math.max(0,Math.sin(time * .39 - 1.5)),18) : 0;
    opening -= refocus * .19;
    const gain = focus === "off" ? 0 : focus === "expressive" ? 1.45 : 1;
    const ease = 1 - Math.exp(-Math.max(delta,.001) * (attention > 0 ? 8 : 3.8));
    if (reduced || focus === "off") { x = 0; y = 0; aperture = opening; }
    else { x += (tx * gain - x) * ease; y += (ty * gain - y) * ease; aperture += (opening - aperture) * ease; }
    return {x, y, aperture, pulse, refocus, time, activity, active: animated, attention};
  }
  return {context, step};
}

const haloVertex = `
  attribute float aAngle, aSide;
  uniform float uTime,uEnergy,uRadius,uWidth,uPhase,uOpen;
  varying float vSide,vAngle;
  void main(){
    float a=aAngle;
    float flow=uTime*.43;
    float bend=sin(a*3.0+flow+uPhase)*.074+cos(a*2.0-flow*.61+uPhase*.3)*.046;
    float voice=sin(a*12.0-uTime*3.2+uPhase)*uEnergy*.014;
    float width=uWidth*(.82+.22*sin(a*3.0-uTime*.7+uPhase));
    float r=uRadius+bend+voice+aSide*width+(uOpen-.61)*.035;
    vec3 p=vec3(cos(a)*r,sin(a)*r,sin(a*2.0+flow+uPhase)*.08);
    vSide=aSide;vAngle=a;
    gl_Position=projectionMatrix*modelViewMatrix*vec4(p,1.0);
  }`;
const haloFragment = `
  uniform vec3 uColour,uWarm;uniform float uTime,uEnergy,uOpacity,uPhase,uBlend,uDashes,uDim,uSweep;
  varying float vSide,vAngle;
  void main(){
    float edge=pow(max(0.0,1.0-abs(vSide)),1.8);
    float spine=pow(max(0.0,1.0-abs(vSide)),9.0);
    float travel=.58+.42*pow(.5+.5*cos(vAngle*2.0-uTime*.65+uPhase),3.0);
    if(uDashes>.5 && fract(vAngle/6.2831853*36.0-uTime*.075)>.32)discard;
    vec3 colour=mix(uColour,uWarm,uBlend*(.5+.5*sin(vAngle+uTime*.22)));
    colour=mix(colour,vec3(.88,.98,1.0),spine*.76);
    float gap=abs(mod(vAngle-(1.5707963-uSweep*6.2831853)+3.1415927,6.2831853)-3.1415927);
    float sweep=exp(-gap*gap*18.0)*step(0.0,uSweep)*(1.0-step(1.0,uSweep));
    colour=mix(colour,vec3(.92,1.0,1.0),sweep*.7);
    gl_FragColor=vec4(colour*(1.0+uEnergy*.38),edge*travel*uOpacity*(1.0-uDim*.4)*(1.0+sweep*2.2));
    #include <colorspace_fragment>
  }`;
const planeVertex = `varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`;
const auraFragment = `
  uniform vec3 uColour,uWarm;uniform float uTime,uEnergy;
  varying vec2 vUv;
  void main(){
    vec2 p=(vUv-.5)*2.0;float r=length(p),a=atan(p.y,p.x);
    if(r>.995)discard;
    float contour=.79+sin(a*3.0+uTime*.43)*.042+cos(a*2.0-uTime*.26)*.025;
    float halo=exp(-pow((r-contour)/.075,2.0))*(.10+uEnergy*.10);
    float boundary=.95+sin(a*3.0+uTime*.2)*.007+cos(a*2.0-uTime*.16)*.006;
    float corona=exp(-pow((r-boundary)/.028,2.0))*.20;
    float falloff=1.0-smoothstep(.98,.995,r);
    vec3 colour=mix(uColour,uWarm,.18*(.5+.5*sin(a-uTime*.2)));
    gl_FragColor=vec4(colour,(halo+corona)*falloff);
    #include <colorspace_fragment>
  }`;
const coreFragment = `
  uniform vec3 uColour,uWarm;uniform float uTime,uEnergy,uScan,uDim;
  varying vec2 vUv;
  float stroke(float d,float width){return 1.0-smoothstep(width,width+max(fwidth(d),.002),abs(d));}
  float hexagon(vec2 p){p=abs(p);return max(p.x*.8660254+p.y*.5,p.y);}
  void main(){
    vec2 p=(vUv-.5)*2.0;float r=length(p),a=atan(p.y,p.x);
    if(r>1.0)discard;
    float outer=stroke(r-.84,.014)*(1.0-step(.76,fract((a+uTime*.30)/6.2831853*3.0)));
    float inner=stroke(r-.73,.005)*(1.0-step(.62,fract((a-uTime*.23+1.0)/6.2831853*3.0)));
    float h=hexagon(p);
    float frame=stroke(h-.57,.010)+stroke(h-.42,.005)*.65;
    float trace=stroke(h-.52,.004)*pow(.5+.5*cos(a*3.0-uTime*.9),6.0);
    float tick=stroke(r-.95,.035)*(1.0-step(.06,fract(a/6.2831853*24.0)))*.32;
    float scan=stroke(p.y-sin(uTime*.72)*.53,.004)*(1.0-step(.55,h))*uScan*.45;
    float glow=exp(-pow((r-.84)/.035,2.0))*.10;
    float alpha=clamp(outer*.9+inner*.72+frame*.8+trace*.85+tick+scan+glow,0.0,1.0);
    vec3 colour=mix(uColour,uWarm,inner*.48);
    colour=mix(colour,vec3(.87,.97,1.0),clamp((outer+trace)*uEnergy*.5,0.0,.45));
    gl_FragColor=vec4(colour,alpha*(.96+uEnergy*.04)*(1.0-uDim*.35));
    #include <colorspace_fragment>
  }`;
const dustVertex = `
  attribute vec4 aSeed;uniform float uTime,uEnergy,uDpr;
  varying float vAlpha;
  void main(){
    float a=aSeed.x*6.2831853+uTime*(.11+aSeed.w*.10);
    float r=.99+sin(a*3.0+uTime*.43)*.074+cos(a*2.0-uTime*.26)*.046+(aSeed.y-.5)*.22;
    vec3 p=vec3(cos(a)*r,sin(a)*r,(aSeed.z-.5)*.23);
    gl_Position=projectionMatrix*modelViewMatrix*vec4(p,1.0);
    gl_PointSize=uDpr*(.65+aSeed.w*.85+uEnergy*.7);
    vAlpha=(.15+aSeed.w*.35)*(.7+.3*sin(a+uTime));
  }`;
const dustFragment = `uniform vec3 uColour;varying float vAlpha;
  void main(){float d=length(gl_PointCoord-vec2(.5));if(d>.5)discard;gl_FragColor=vec4(uColour,(1.0-smoothstep(.04,.5,d))*vAlpha);
    #include <colorspace_fragment>
  }`;

export function createAsterDisplay(canvas) {
  const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,premultipliedAlpha:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));renderer.setClearColor(0x000000,0);
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  const scene=new THREE.Scene(),extent=COMPANION_EXTENT;
  const camera=new THREE.OrthographicCamera(-extent,extent,extent,-extent,.1,20);camera.position.z=5;
  const assembly=new THREE.Group(),halo=new THREE.Group(),commandCore=new THREE.Group();
  scene.add(assembly);assembly.add(halo,commandCore);
  halo.scale.setScalar(.87);
  const signature=SIGNATURES.aster;
  const colour=new THREE.Color(signature.primary),warm=new THREE.Color(signature.secondary);
  const uTime={value:0},uEnergy={value:0},uOpen={value:.61},uColour={value:colour},uWarm={value:warm},uScan={value:0};
  const uDim={value:0},uSweep={value:-1};
  const shared={uTime,uEnergy,uOpen,uColour,uWarm,uDim,uSweep};
  const service={value:0};
  scene.add(createCompanionFrame({colour:uColour,energy:uEnergy,opening:.29,style:'command',service}));
  const shader=(vertexShader,fragmentShader,uniforms={})=>new THREE.ShaderMaterial({
    vertexShader,fragmentShader,uniforms:{...shared,...uniforms},transparent:true,depthWrite:false,
    blending:THREE.AdditiveBlending,side:THREE.DoubleSide,forceSinglePass:true});
  const plane=new THREE.PlaneGeometry(1,1);
  const aura=new THREE.Mesh(plane,shader(planeVertex,auraFragment));
  aura.scale.set(2.22,2.22,1);aura.position.z=-.2;assembly.add(aura);
  const geometry=new THREE.BufferGeometry(),angles=[],sides=[],positions=[],indices=[];
  for(let i=0;i<=320;i++)for(let edge=0;edge<2;edge++){
    const a=i/320*TAU;angles.push(a);sides.push(edge?1:-1);positions.push(Math.cos(a),Math.sin(a),0);
  }
  for(let i=0;i<320;i++){const j=i*2;indices.push(j,j+1,j+2,j+1,j+3,j+2);}
  geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
  geometry.setAttribute('aAngle',new THREE.Float32BufferAttribute(angles,1));
  geometry.setAttribute('aSide',new THREE.Float32BufferAttribute(sides,1));geometry.setIndex(indices);
  function strand(radius,width,phase,opacity,blend=0,dashes=0){
    const material=shader(haloVertex,haloFragment,{uRadius:{value:radius},uWidth:{value:width},uPhase:{value:phase},uOpacity:{value:opacity},uBlend:{value:blend},uDashes:{value:dashes}});
    const mesh=new THREE.Mesh(geometry,material);mesh.frustumCulled=false;halo.add(mesh);return mesh;
  }
  strand(1.015,.085,0,.58,.05);strand(1.025,.045,.8,.62,.55);strand(.99,.060,1.7,.45,.18);
  for(let i=0;i<16;i++){
    const mesh=strand(.977+i*.0045,.0025+(i%3)*.0008,i*.13,.48+(i%4)*.08,i%5===0?.8:.05);
    mesh.position.z=(i-8)*.008;
  }
  strand(.87,.003,2.3,.28,.12,1);
  const core=new THREE.Mesh(plane,shader(planeVertex,coreFragment,{uScan}));
  core.scale.set(1.16,1.16,1);core.position.z=.15;commandCore.add(core);
  const reactor=createCompanionCore({identity:"aster",time:uTime,energy:uEnergy,colour:uColour,highlight:uWarm});
  reactor.group.position.z=.22;commandCore.add(reactor.group);
  // The watch bill: a chevron for each of the rota's duties, the one on now lit.
  const billPoints=[],billOrder=[];
  DUTIES.forEach((_duty,i)=>{
    const a=Math.PI/2-i/DUTIES.length*TAU,c=Math.cos(a),s=Math.sin(a),r=.64;
    const tip=[c*(r+.035),s*(r+.035),0],left=[c*r-s*.028,s*r+c*.028,0],right=[c*r+s*.028,s*r-c*.028,0];
    billPoints.push(...left,...tip,...tip,...right);billOrder.push(i,i,i,i);
  });
  const billGeometry=new THREE.BufferGeometry();
  billGeometry.setAttribute('position',new THREE.Float32BufferAttribute(billPoints,3));
  billGeometry.setAttribute('aDuty',new THREE.Float32BufferAttribute(billOrder,1));
  const bill=new THREE.LineSegments(billGeometry,shader(`attribute float aDuty;varying float vDuty;
    void main(){vDuty=aDuty;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    `uniform vec3 uColour,uWarm;uniform float uDuty,uHand,uBill;varying float vDuty;
     void main(){float on=1.0-step(.5,abs(vDuty-uDuty));
       float hand=uHand<0.0?0.0:exp(-pow((uHand*6.0-vDuty)/.6,2.0));
       gl_FragColor=vec4(mix(uColour,uWarm,on*.5+hand*.5),(.18+on*.8+hand*.8)*uBill);
       #include <colorspace_fragment>
     }`,{uDuty:{value:-1},uHand:{value:-1},uBill:{value:0}}));
  bill.position.z=.3;commandCore.add(bill);
  const padCanvas=document.createElement('canvas');padCanvas.width=padCanvas.height=128;
  const padTexture=new THREE.CanvasTexture(padCanvas);padTexture.colorSpace=THREE.SRGBColorSpace;
  const padMaterial=new THREE.MeshBasicMaterial({map:padTexture,transparent:true,depthWrite:false,opacity:0,
    blending:THREE.AdditiveBlending,color:colour});
  const padLabel=new THREE.Mesh(plane,padMaterial);padLabel.scale.set(.5,.5,1);padLabel.position.z=.4;
  padLabel.visible=false;commandCore.add(padLabel);
  function drawPad(pad){
    const context=padCanvas.getContext('2d');context.clearRect(0,0,128,128);
    context.fillStyle='#ffffff';context.textAlign='center';context.textBaseline='middle';
    context.font='600 22px Consolas, monospace';context.fillText('PAD',64,34);
    context.font='700 58px Consolas, monospace';context.fillText(String(pad).padStart(2,'0'),64,82);
    padTexture.needsUpdate=true;
  }
  const seeds=[],dustPositions=[];
  for(let i=0;i<140;i++){
    const random=n=>{const x=Math.sin((i+1)*n)*43758.5453;return x-Math.floor(x);};
    seeds.push(random(12.9898),random(39.346),random(73.156),random(91.217));dustPositions.push(0,0,0);
  }
  const dustGeometry=new THREE.BufferGeometry();dustGeometry.setAttribute('position',new THREE.Float32BufferAttribute(dustPositions,3));
  dustGeometry.setAttribute('aSeed',new THREE.Float32BufferAttribute(seeds,4));
  const dust=new THREE.Points(dustGeometry,shader(dustVertex,dustFragment,{uDpr:{value:renderer.getPixelRatio()}}));
  dust.frustumCulled=false;halo.add(dust);
  const life=createAsterMotion();
  let state='idle',level=0,smoothLevel=0,accent=signature.primary,secondary=signature.secondary,idle=true,reduced=false,focus='tracking',activity=1;
  let frame=0,last=0,time=0,disposed=false,visible=true,dirty=true,frameRate=30,tiltX=0,tiltY=0;
  let lastPose={x:0,y:0,aperture:.61,pulse:0,time:0,activity:'idle'},frames=0;
  // The mood of what it says (5.7.6), and docking granted: the pad, and a sweep once round.
  const moods=createMood(),expression=moods.expression;
  let pad=null,padShow=0,sweep=-1,beat=-1,haloSpin=0,moving=false;
  // The watch bells, and the watch bill: the rota's duty, a sweep at a handover.
  let bellIndex=null,strikes=[],bellAt=-1,bellCount=0,watch={rota:false,duty:null},billShow=0,handover=-1;
  function listenForBells(){
    const bell=bellsAt(shipTime());
    if(bellIndex!==null&&bell.index!==bellIndex&&!reduced){
      // Struck in pairs: ding-ding, ding-ding, then any odd one.
      strikes=Array.from({length:bell.count},(_,i)=>Math.floor(i/2)*.95+(i%2)*.32);bellAt=0;bellCount=bell.count;
    }
    bellIndex=bell.index;
  }
  function schedule(){if(!frame&&!disposed&&visible&&!document.hidden)frame=requestAnimationFrame(draw);}
  function changed(){dirty=true;schedule();}
  function resize(){
    const rect=canvas.getBoundingClientRect();if(!rect.width||!rect.height)return;
    renderer.setSize(rect.width,rect.height,false);const aspect=rect.width/rect.height;
    reactor.resize(rect.width,rect.height);
    camera.left=-extent*aspect;camera.right=extent*aspect;camera.updateProjectionMatrix();changed();
  }
  const observer=new ResizeObserver(resize);observer.observe(canvas);
  function draw(now){
    frame=0;if(disposed||!visible||document.hidden)return;
    const active=!reduced&&(idle||state!=='idle'||lastPose.attention>0||moods.settling||moving);
    if(!active&&!dirty)return;
    if(now-last<1000/frameRate-.7){schedule();return;}
    const delta=clamp((now-last)/1000,0,.12);last=now;dirty=false;
    lastPose=life.step(delta,{state,idle,reduced,focus,intensity:activity});
    if(active)time+=delta*activity;
    smoothLevel=reduced?level:smoothLevel+(level-smoothLevel)*(1-Math.exp(-delta*9));
    const wasPleased=expression.joy>.5;
    moods.step(delta,reduced);
    const {joy,worry,sad,curious}=expression;
    // Pleased: the halo pulses twice, like an acknowledgement (still, with Reduced motion).
    if(!wasPleased&&joy>.5&&!reduced)beat=0;
    let acknowledge=0;
    if(beat>=0){beat+=delta;acknowledge=Math.exp(-Math.pow((beat-.15)/.08,2))+Math.exp(-Math.pow((beat-.5)/.08,2));if(beat>.8)beat=-1;}
    // Docking granted: the number shows, and a bright band runs once round the halo.
    const wanted=pad!==null?1:0;
    padShow=reduced?wanted:padShow+(wanted-padShow)*(1-Math.exp(-delta*6));
    if(Math.abs(wanted-padShow)<.01)padShow=wanted;
    if(sweep>=0){sweep=reduced?-1:sweep+delta/1.6;if(sweep>=1)sweep=-1;}
    padLabel.visible=padShow>0;padMaterial.opacity=padShow*(.85+(1-sad)*.15);padMaterial.color.copy(colour);
    // The prism steps back behind the number.
    reactor.group.scale.setScalar(1-padShow*.45);
    uSweep.value=sweep;uDim.value=sad;
    // A bell: the halo rings once for each strike.
    listenForBells();
    let ring=0;
    if(bellAt>=0){bellAt+=delta;for(const at of strikes)ring+=Math.exp(-Math.pow((bellAt-at)/.07,2));
      if(bellAt>strikes[strikes.length-1]+.6)bellAt=-1;}
    // The watch bill shows with the rota on; a handover runs a light round it once.
    const billWanted=watch.rota?1:0;
    billShow=reduced?billWanted:billShow+(billWanted-billShow)*(1-Math.exp(-delta*5));
    if(Math.abs(billWanted-billShow)<.01)billShow=billWanted;
    if(handover>=0){handover=reduced?-1:handover+delta/1.4;if(handover>=1)handover=-1;}
    const billUniforms=bill.material.uniforms;
    billUniforms.uBill.value=billShow;billUniforms.uHand.value=handover;
    billUniforms.uDuty.value=DUTIES.indexOf(watch.duty);
    moving=beat>=0||sweep>=0||padShow!==wanted||bellAt>=0||handover>=0||billShow!==billWanted;
    const energy=((state==='speaking'?smoothLevel:state==='listening'?level*.7:state==='charging'?.45:.025)+lastPose.pulse*.28
      +joy*.06+acknowledge*.55+ring*.6)*(1-sad*.35);
    uTime.value=time;uEnergy.value=energy;uOpen.value=lastPose.aperture;
    colour.set(state==='alert'?'#ffab55':accent);warm.set(state==='alert'?'#ffdbac':secondary);
    // Wary holds it still; downcast slows it.
    haloSpin+=active?delta*activity*Math.max(.05,1-worry*.9-sad*.5):0;
    halo.rotation.z=haloSpin*.026;
    halo.position.set(lastPose.x*.025,lastPose.y*.025,0);
    commandCore.position.set(lastPose.x*.045,lastPose.y*.045,0);
    commandCore.rotation.x=-lastPose.y*.12;commandCore.rotation.y=lastPose.x*.12;
    commandCore.scale.setScalar(1+(lastPose.aperture-.61)*.045+energy*.035);
    // Curious: a scanning sweep crosses the prism.
    uScan.value=Math.max(state==='working'?1:state==='listening'?.7:0,curious);
    reactor.update({state,clock:time,level:state==='speaking'?smoothLevel:state==='listening'?level*.7:0,
      animated:active,pulse:lastPose.pulse,expression});
    assembly.rotation.x=reduced?0:tiltY*.07;assembly.rotation.y=reduced?0:tiltX*.07;
    renderer.render(scene,camera);frames++;
    if(!reduced&&(idle||state!=='idle'||lastPose.attention>0)||moods.settling||moving)schedule();
  }
  function visibility(){if(document.hidden){cancelAnimationFrame(frame);frame=0;}else changed();}
  document.addEventListener('visibilitychange',visibility);
  resize();schedule();
  return {
    setState(value,valueLevel=0){const next=clamp(Number(valueLevel)||0);if(state!==value||Math.abs(next-level)>.004){moods.state(value);state=value;level=next;changed();}},
    setContext(model){
      const moved=life.context(model),felt=moods.context(model);
      // 5.7.7: service pips on the bezel, from your standing with Aster.
      const pips=Math.max(0,Math.min(4,Math.round(Number(model?.moment?.service)||0)));
      if(pips!==service.value){service.value=pips;changed();}
      const granted=Number.isFinite(Number(model?.moment?.dock?.pad))&&model.moment.dock.pad!==null?Number(model.moment.dock.pad):null;
      const fresh=granted!==pad;
      if(fresh){if(granted!==null){drawPad(granted);sweep=0;}pad=granted;}
      const next={rota:Boolean(model?.moment?.watch?.rota),duty:model?.moment?.watch?.duty||null};
      const turned=next.rota!==watch.rota||next.duty!==watch.duty;
      // Taking the watch, or the duty changing under the rota: the bill lights round once.
      if(turned&&next.rota&&!reduced)handover=0;
      watch=next;
      const before=bellIndex;listenForBells();
      if(moved||felt||fresh||turned||bellIndex!==before||bellAt>=0)changed();
    },
    setColour(value,highlight=signature.secondary){if(/^#[0-9a-f]{6}$/i.test(value)&&/^#[0-9a-f]{6}$/i.test(highlight)&&(accent!==value||secondary!==highlight)){accent=value;secondary=highlight;changed();}},
    setActivity(value){const next={calm:.5,standard:1,alive:1.6}[value]||1;if(activity!==next){activity=next;changed();}},
    setFocus(value){const next=['off','tracking','expressive'].includes(value)?value:'tracking';if(focus!==next){focus=next;changed();}},
    setMotion(value){if(idle!==Boolean(value)){idle=Boolean(value);changed();}},
    setReducedMotion(value){if(reduced!==Boolean(value)){reduced=Boolean(value);changed();}},
    setFrameRate(value){frameRate=[15,24,30,60].includes(Number(value))?Number(value):30;},
    setVisible(value){if(visible!==Boolean(value)){visible=Boolean(value);if(!visible){cancelAnimationFrame(frame);frame=0;}else changed();}},
    setTilt(x,y){tiltX=clamp(x,-1,1);tiltY=clamp(y,-1,1);changed();},
    inspect(){return {...lastPose,frames,state,reduced,idle,focus,frameRate,accent,secondary,drawCalls:renderer.info.render.calls,design:'luminous-halo',core:'segmented-command',reactor:reactor.inspect(),
      mood:moods.mood,expression:{...expression},expressing:moods.settling,pad,padShow,sweep,acknowledging:beat>=0,moving,
      bells:bellAt>=0?bellCount:0,watch:{...watch,show:billShow,handover}};},
    destroy(){disposed=true;padTexture.dispose();cancelAnimationFrame(frame);observer.disconnect();document.removeEventListener('visibilitychange',visibility);const geometries=new Set(),materials=new Set();scene.traverse(object=>{if(object.geometry)geometries.add(object.geometry);for(const material of Array.isArray(object.material)?object.material:[object.material])if(material)materials.add(material);});geometries.forEach(geometry=>geometry.dispose());materials.forEach(material=>material.dispose());renderer.dispose();},
  };
}
