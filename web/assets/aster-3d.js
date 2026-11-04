import * as THREE from "../galactic_map/vendor/three.module.min.js";

const TAU = Math.PI * 2;
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
  uniform vec3 uColour,uWarm;uniform float uTime,uEnergy,uOpacity,uPhase,uBlend,uDashes;
  varying float vSide,vAngle;
  void main(){
    float edge=pow(max(0.0,1.0-abs(vSide)),1.8);
    float spine=pow(max(0.0,1.0-abs(vSide)),9.0);
    float travel=.58+.42*pow(.5+.5*cos(vAngle*2.0-uTime*.65+uPhase),3.0);
    if(uDashes>.5 && fract(vAngle/6.2831853*36.0-uTime*.075)>.32)discard;
    vec3 colour=mix(uColour,uWarm,uBlend*(.5+.5*sin(vAngle+uTime*.22)));
    colour=mix(colour,vec3(.88,.98,1.0),spine*.76);
    gl_FragColor=vec4(colour*(1.0+uEnergy*.38),edge*travel*uOpacity);
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
  uniform vec3 uColour,uWarm;uniform float uTime,uEnergy,uScan;
  varying vec2 vUv;
  float stroke(float d,float width){return 1.0-smoothstep(width,width+max(fwidth(d),.002),abs(d));}
  float hexagon(vec2 p){p=abs(p);return max(p.x*.8660254+p.y*.5,p.y);}
  void main(){
    vec2 p=(vUv-.5)*2.0;float r=length(p),a=atan(p.y,p.x);
    if(r>1.0)discard;
    float outer=stroke(r-.84,.011)*(1.0-step(.76,fract((a+uTime*.30)/6.2831853*3.0)));
    float inner=stroke(r-.73,.005)*(1.0-step(.62,fract((a-uTime*.23+1.0)/6.2831853*3.0)));
    float h=hexagon(p);
    float frame=stroke(h-.57,.007)+stroke(h-.42,.004)*.55;
    float trace=stroke(h-.52,.004)*pow(.5+.5*cos(a*3.0-uTime*.9),6.0);
    float tick=stroke(r-.95,.035)*(1.0-step(.06,fract(a/6.2831853*24.0)))*.32;
    float scan=stroke(p.y-sin(uTime*.72)*.53,.004)*(1.0-step(.55,h))*uScan*.45;
    float glow=exp(-pow((r-.84)/.035,2.0))*.10;
    float alpha=clamp(outer*.8+inner*.6+frame*.65+trace*.8+tick+scan+glow,0.0,1.0);
    vec3 colour=mix(uColour,uWarm,inner*.48);
    colour=mix(colour,vec3(.87,.97,1.0),clamp((outer+trace)*uEnergy*.5,0.0,.45));
    gl_FragColor=vec4(colour,alpha*(.85+uEnergy*.15));
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
  const scene=new THREE.Scene(),extent=1.275;
  const camera=new THREE.OrthographicCamera(-extent,extent,extent,-extent,.1,20);camera.position.z=5;
  const assembly=new THREE.Group(),halo=new THREE.Group(),commandCore=new THREE.Group();
  scene.add(assembly);assembly.add(halo,commandCore);
  const colour=new THREE.Color('#65e4ef'),warm=new THREE.Color('#a8b4ff');
  const uTime={value:0},uEnergy={value:0},uOpen={value:.61},uColour={value:colour},uWarm={value:warm},uScan={value:0};
  const shared={uTime,uEnergy,uOpen,uColour,uWarm};
  const shader=(vertexShader,fragmentShader,uniforms={})=>new THREE.ShaderMaterial({
    vertexShader,fragmentShader,uniforms:{...shared,...uniforms},transparent:true,depthWrite:false,
    blending:THREE.AdditiveBlending,side:THREE.DoubleSide,forceSinglePass:true});
  const plane=new THREE.PlaneGeometry(1,1);
  const aura=new THREE.Mesh(plane,shader(planeVertex,auraFragment));
  aura.scale.set(2.55,2.55,1);aura.position.z=-.2;assembly.add(aura);
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
  let state='idle',level=0,smoothLevel=0,accent='#65e4ef',idle=true,reduced=false,focus='tracking',activity=1;
  let frame=0,last=0,time=0,disposed=false,visible=true,dirty=true,frameRate=30,tiltX=0,tiltY=0;
  let lastPose={x:0,y:0,aperture:.61,pulse:0,time:0,activity:'idle'},frames=0;
  function schedule(){if(!frame&&!disposed&&visible&&!document.hidden)frame=requestAnimationFrame(draw);}
  function changed(){dirty=true;schedule();}
  function resize(){
    const rect=canvas.getBoundingClientRect();if(!rect.width||!rect.height)return;
    renderer.setSize(rect.width,rect.height,false);const aspect=rect.width/rect.height;
    camera.left=-extent*aspect;camera.right=extent*aspect;camera.updateProjectionMatrix();changed();
  }
  const observer=new ResizeObserver(resize);observer.observe(canvas);
  function draw(now){
    frame=0;if(disposed||!visible||document.hidden)return;
    const active=!reduced&&(idle||state!=='idle'||lastPose.attention>0);
    if(!active&&!dirty)return;
    if(now-last<1000/frameRate-.7){schedule();return;}
    const delta=clamp((now-last)/1000,0,.12);last=now;dirty=false;
    lastPose=life.step(delta,{state,idle,reduced,focus,intensity:activity});
    if(active)time+=delta*activity;
    smoothLevel=reduced?level:smoothLevel+(level-smoothLevel)*(1-Math.exp(-delta*9));
    const energy=(state==='speaking'?smoothLevel:state==='listening'?level*.7:state==='charging'?.45:.025)+lastPose.pulse*.28;
    uTime.value=time;uEnergy.value=energy;uOpen.value=lastPose.aperture;
    colour.set(state==='alert'?'#ffab55':accent);warm.set(state==='alert'?'#ffdbac':'#a8b4ff');
    halo.rotation.z=time*.026;
    halo.position.set(lastPose.x*.025,lastPose.y*.025,0);
    commandCore.position.set(lastPose.x*.045,lastPose.y*.045,0);
    commandCore.rotation.x=-lastPose.y*.12;commandCore.rotation.y=lastPose.x*.12;
    commandCore.scale.setScalar(1+(lastPose.aperture-.61)*.045+energy*.035);
    uScan.value=state==='working'?1:state==='listening'?.7:0;
    assembly.rotation.x=reduced?0:tiltY*.07;assembly.rotation.y=reduced?0:tiltX*.07;
    renderer.render(scene,camera);frames++;
    if(!reduced&&(idle||state!=='idle'||lastPose.attention>0))schedule();
  }
  function visibility(){if(document.hidden){cancelAnimationFrame(frame);frame=0;}else changed();}
  document.addEventListener('visibilitychange',visibility);
  resize();schedule();
  return {
    setState(value,valueLevel=0){const next=clamp(Number(valueLevel)||0);if(state!==value||Math.abs(next-level)>.004){state=value;level=next;changed();}},
    setContext(model){if(life.context(model))changed();},
    setColour(value){if(/^#[0-9a-f]{6}$/i.test(value)&&accent!==value){accent=value;changed();}},
    setActivity(value){const next={calm:.5,standard:1,alive:1.6}[value]||1;if(activity!==next){activity=next;changed();}},
    setFocus(value){const next=['off','tracking','expressive'].includes(value)?value:'tracking';if(focus!==next){focus=next;changed();}},
    setMotion(value){if(idle!==Boolean(value)){idle=Boolean(value);changed();}},
    setReducedMotion(value){if(reduced!==Boolean(value)){reduced=Boolean(value);changed();}},
    setFrameRate(value){frameRate=[15,24,30,60].includes(Number(value))?Number(value):30;},
    setVisible(value){if(visible!==Boolean(value)){visible=Boolean(value);if(!visible){cancelAnimationFrame(frame);frame=0;}else changed();}},
    setTilt(x,y){tiltX=clamp(x,-1,1);tiltY=clamp(y,-1,1);changed();},
    inspect(){return {...lastPose,frames,state,reduced,idle,focus,frameRate,drawCalls:renderer.info.render.calls,design:'luminous-halo',core:'segmented-command'};},
    destroy(){disposed=true;cancelAnimationFrame(frame);observer.disconnect();document.removeEventListener('visibilitychange',visibility);const geometries=new Set(),materials=new Set();scene.traverse(object=>{if(object.geometry)geometries.add(object.geometry);for(const material of Array.isArray(object.material)?object.material:[object.material])if(material)materials.add(material);});geometries.forEach(geometry=>geometry.dispose());materials.forEach(material=>material.dispose());renderer.dispose();},
  };
}
