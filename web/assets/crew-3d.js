import * as THREE from "../galactic_map/vendor/three.module.min.js";
import {createAsterMotion} from "./aster-3d.js";
import {createCompanionFrame, COMPANION_EXTENT} from "./companion-frame.js";
import {SIGNATURES} from "./companion-colours.js";
import {createCompanionCore} from "./companion-core.js";
import {addLyraRobot, addLyraHalo} from "./lyra-robot.js";
import {addAxiomSurveyor, addMeridianNavigator, addOfficerHalo, createOfficerFinish} from "./officer-robots.js";
import {createMood} from "./companion-mood.js";

const TAU = Math.PI * 2;
const clamp = (n, lo=0, hi=1) => Math.max(lo, Math.min(hi, n));

// Original procedural displays: no image plates, opaque backdrops or character likenesses.
export function createCrewDisplay(canvas, identity) {
  const lyra = identity === "lyra";
  const portrait = identity === "meridian" || lyra || identity === "axiom";
  const meridian = identity === "meridian", axiom = identity === "axiom";
  const signature = SIGNATURES[identity];
  const renderer = new THREE.WebGLRenderer({canvas, alpha:true, antialias:true, premultipliedAlpha:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0, 0); renderer.outputColorSpace = THREE.SRGBColorSpace;
  const finish=axiom||meridian?createOfficerFinish(renderer,meridian?.18:.20):null;let drawCalls=0;
  const extent = COMPANION_EXTENT, scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-extent,extent,extent,-extent,.1,20); camera.position.z = 5;
  const rig = new THREE.Group(), field = new THREE.Group(), rings = new THREE.Group();
  scene.add(rig); rig.add(field,rings);
  const uniforms = {uTime:{value:0},uEnergy:{value:0},uScan:{value:0},uIdle:{value:1},uColour:{value:new THREE.Color(signature.primary)},
    uOther:{value:new THREE.Color(signature.secondary)},uDpr:{value:renderer.getPixelRatio()},uScale:{value:1},uMouth:{value:0},uFace:{value:0},
    uSmile:{value:0},uMood:{value:new THREE.Vector4()}};
  const reactor=identity!=="axiom"?null:createCompanionCore({identity,diamond:axiom,time:uniforms.uTime,energy:uniforms.uEnergy,
    colour:uniforms.uColour,highlight:uniforms.uOther});
  if(reactor){reactor.group.position.z=.45;rig.add(reactor.group);}
  const service={value:0};
  scene.add(createCompanionFrame({colour:uniforms.uColour,energy:uniforms.uEnergy,opening:portrait?0:.48,service,
    style:axiom?"scale":meridian?"compass":""}));
  const shader = (vertexShader,fragmentShader,extra={}) => new THREE.ShaderMaterial({vertexShader,fragmentShader,uniforms:{...uniforms,uOpacity:{value:1},...extra},
    transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide});
  const lineVertex = `uniform float uTime,uEnergy,uScan;varying vec3 vPos;
    void main(){vPos=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`;
  const lineFragment = `uniform float uTime,uEnergy,uScan,uOpacity,uMouth,uFace;uniform vec3 uColour,uOther;varying vec3 vPos;
    void main(){if(uFace>.5){vec2 mouth=vec2(vPos.x/.14,(vPos.y+.245)/(.008+uMouth*.075));if(dot(mouth,mouth)<1.0)discard;}
      float sweep=pow(max(0.0,1.0-abs(vPos.y-sin(uTime*.95))/.10),2.0);
      float blue=.4+.3*sin(vPos.y*3.0+uTime*.3);
      gl_FragColor=vec4(mix(uColour,uOther,blue),(.48+uEnergy*.25+sweep*(.38+uScan*.2))*uOpacity);
      #include <colorspace_fragment>
    }`;
  function lines(points, parent, material=shader(lineVertex,lineFragment)) {
    const geometry = new THREE.BufferGeometry(); geometry.setAttribute("position",new THREE.Float32BufferAttribute(points,3));
    const object = new THREE.LineSegments(geometry,material); parent.add(object); return object;
  }
  function arc(radius,start,end,z=0,count=100) {
    const points=[];
    for(let i=0;i<count;i++)for(const a of [start+(end-start)*i/count,start+(end-start)*(i+1)/count]) points.push(Math.cos(a)*radius,Math.sin(a)*radius,z);
    return points;
  }
  const outer = lines(arc(1.045,0,TAU),rings);
  const rotor = new THREE.Group(); rings.add(rotor);
  let ticks=[];
  for(let i=0;i<96;i++){
    const a=i/96*TAU,r=i%8===0?.985:1.012;
    ticks.push(Math.cos(a)*r,Math.sin(a)*r,0,Math.cos(a)*1.035,Math.sin(a)*1.035,0);
  }
  lines(ticks,rings);
  const rotorPaths=[];
  const counter = new THREE.Group(); rings.add(counter);
  const counterPaths=[];
  if(axiom){
    // A measuring scale: graduations every 5 degrees, long every 30; a vernier inside it.
    rotorPaths.push(...arc(.94,0,TAU));
    for(let i=0;i<72;i++){const a=i/72*TAU,l=i%6===0?.05:.022;
      rotorPaths.push(Math.cos(a)*.94,Math.sin(a)*.94,0,Math.cos(a)*(.94-l),Math.sin(a)*(.94-l),0);}
    for(let i=0;i<10;i++){const b=i*TAU/72*.9;
      counterPaths.push(Math.cos(b)*.875,Math.sin(b)*.875,0,Math.cos(b)*.85,Math.sin(b)*.85,0);}
    counterPaths.push(...arc(.875,0,TAU*.125));
  }else{
    for(let i=0;i<6;i++) rotorPaths.push(...arc(.94,i*TAU/6+.06,(i+(i===0?.86:.58))*TAU/6));
    for(let i=0;i<3;i++) counterPaths.push(...arc(.875,i*TAU/3+.12,(i+.35)*TAU/3));
  }
  lines(rotorPaths,rotor);
  lines(counterPaths,counter);
  // Axiom's tally: a mark lit for each body it has counted in this system.
  let tally=null;
  if(axiom){
    const marks=[],order=[];
    for(let i=0;i<60;i++){const a=Math.PI/2-i/60*TAU;
      marks.push(Math.cos(a)*.952,Math.sin(a)*.952,0,Math.cos(a)*.972,Math.sin(a)*.972,0);order.push(i,i);}
    const geometry=new THREE.BufferGeometry();geometry.setAttribute("position",new THREE.Float32BufferAttribute(marks,3));
    geometry.setAttribute("aOrder",new THREE.Float32BufferAttribute(order,1));
    tally=new THREE.LineSegments(geometry,shader(`attribute float aOrder;varying float vOrder;
      void main(){vOrder=aOrder;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
      `uniform vec3 uColour,uOther;uniform float uCount,uFresh;varying float vOrder;
       void main(){float lit=1.0-step(uCount,vOrder+.5);float newest=lit*step(uCount-1.5,vOrder)*uFresh;
         gl_FragColor=vec4(mix(uColour,uOther,.6+newest*.4),.10+lit*.75+newest*.6);
         #include <colorspace_fragment>
       }`,{uCount:{value:0},uFresh:{value:0}}));
    rings.add(tally);
  }
  const inner = lines(arc(portrait?.84:.57,0,TAU),rings);
  const scan = lines([-.53,0,.5,.53,0,.5],field);
  const sweep = new THREE.Mesh(new THREE.PlaneGeometry(2.12,2.12),shader(
    `varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    `varying vec2 vUv;uniform float uTime,uEnergy,uIdle;uniform vec3 uColour,uOther;
     void main(){vec2 p=(vUv-.5)*2.12;float r=length(p);float a=atan(p.y,p.x);
       float phase=mod(a-uTime*.65+6.2831853,6.2831853);
       float tail=exp(-phase*8.0);float band=exp(-pow((r-.985)/.016,2.0));
       float echo=exp(-pow((r-.90)/.012,2.0))*exp(-mod(-a-uTime*.42+6.2831853,6.2831853)*12.0);
       gl_FragColor=vec4(mix(uColour,uOther,.25),(band*tail*.85+echo*.6)*(uIdle+uEnergy));
       #include <colorspace_fragment>
     }`));sweep.position.z=.55;rings.add(sweep);
  const halo=lyra?addLyraHalo(rings,uniforms):axiom?addOfficerHalo(rings,uniforms,"axiom"):null;
  if(lyra)for(const object of [rotor,counter,inner,sweep])object.visible=false;
  if(axiom||meridian){inner.visible=false;rotor.position.z=counter.position.z=-.35;}
  if(axiom)sweep.visible=false;
  let portraitLayer=null,needle=null,needleMaterial=null,bodyMap=null,wake=null;
  if(lyra) {
    portraitLayer=addLyraRobot(field,uniforms,renderer,scene);
  } else if(axiom) {
    portraitLayer=addAxiomSurveyor(field,uniforms,renderer,scene);
    portraitLayer.coreMount.add(reactor.group);reactor.group.position.set(0,0,0);reactor.group.scale.setScalar(.32);
  } else if(portrait) {
    portraitLayer=addMeridianNavigator(field,uniforms,renderer,scene);
    const brackets=[];
    for(const sign of [-1,1])for(const y of [-.42,.42])brackets.push(sign*.66,y,0,sign*.73,y,0,sign*.73,y,0,sign*.73,y+Math.sign(y)*.12,0);
    lines(brackets,rings);
    needle=new THREE.Group();needle.position.z=.6;needle.visible=false;rings.add(needle);
    needleMaterial=shader(lineVertex,lineFragment,{uOpacity:{value:0}});
    lines([0,.86,0,0,1.01,0, -.06,.89,0,.06,.89,0],needle,needleMaterial);
    const arrow=new THREE.BufferGeometry();arrow.setAttribute("position",new THREE.Float32BufferAttribute([0,1.035,0,-.065,.94,0,.065,.94,0],3));
    needle.add(new THREE.Mesh(arrow,needleMaterial));
    wake=new THREE.Mesh(new THREE.PlaneGeometry(2.2,2.2),shader(
      `varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
      `varying vec2 vUv;uniform vec3 uColour,uOther;uniform float uWake;
       void main(){if(uWake<0.0)discard;vec2 p=(vUv-.5)*2.2;float r=length(p);
         float front=.25+uWake*.8;float band=exp(-pow((r-front)/.035,2.0))+exp(-pow((r-front+.12)/.025,2.0))*.5;
         gl_FragColor=vec4(mix(uColour,uOther,.4),band*(1.0-uWake)*.7);
         #include <colorspace_fragment>
       }`,{uWake:{value:-1}}));
    wake.position.z=.5;rings.add(wake);
  }
  if(axiom) {
    const map=new THREE.BufferGeometry();
    map.setAttribute("position",new THREE.Float32BufferAttribute(new Float32Array(48*3),3));
    map.setAttribute("aBody",new THREE.Float32BufferAttribute(new Float32Array(48*4),4));
    map.setDrawRange(0,0);
    bodyMap=new THREE.Points(map,shader(`attribute vec4 aBody;uniform float uTime,uDpr,uScale,uMapShow;varying vec3 vKind;
      vec3 kind(float k){
        if(k<.5)return vec3(1.0,.88,.55);if(k<1.5)return vec3(.95,.62,.32);if(k<2.5)return vec3(.35,.85,1.0);
        if(k<3.5)return vec3(.45,1.0,.6);if(k<4.5)return vec3(.75,.95,.45);if(k<5.5)return vec3(.78,.55,.4);
        if(k<6.5)return vec3(.72,.86,1.0);return vec3(.62,.62,.66);}
      void main(){float r=aBody.x,a=aBody.y+uTime*.05/max(r,.3);
        vKind=kind(aBody.z);
        gl_Position=projectionMatrix*modelViewMatrix*vec4(cos(a)*r,sin(a)*r,.3,1.0);
        gl_PointSize=max(1.5,aBody.w*uScale*uMapShow)*uDpr;}`,
      `uniform float uMapShow;varying vec3 vKind;
       void main(){float d=length(gl_PointCoord-.5);if(d>.5)discard;
         float core=1.0-smoothstep(.0,.22,d),halo=1.0-smoothstep(.22,.5,d);
         gl_FragColor=vec4(mix(vKind,vec3(1.0),core*.5),(core+halo*.55)*uMapShow);
         #include <colorspace_fragment>
       }`,{uMapShow:{value:0}}));
    bodyMap.frustumCulled=false;bodyMap.renderOrder=-1;bodyMap.position.z=-.30;rings.add(bodyMap);
  }
  // Faint light behind the structure, with a truly transparent centre and corners.
  const glow=new THREE.Mesh(new THREE.PlaneGeometry(2.5,2.5),shader(`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    `varying vec2 vUv;uniform vec3 uColour;uniform float uEnergy;
     void main(){float r=length((vUv-.5)*2.5);float a=exp(-pow((r-.81)/.12,2.0))*(.055+uEnergy*.04);
       gl_FragColor=vec4(uColour,a);
       #include <colorspace_fragment>
     }`));glow.position.z=-.6;rig.add(glow);
  const life=createAsterMotion();
  let state="idle",level=0,speechLevel=null,idle=true,reduced=false,focus="tracking",activity=1,visible=true,disposed=false;
  let frame=0,last=0,time=0,frames=0,dirty=true,frameRate=30,accent=signature.primary,secondary=signature.secondary,pose={attention:0},mouthOpen=0;
  // Every officer wears the mood of what it is saying, in its own way (5.7.6).
  const moods=createMood(),expression=moods.expression;
  // Moments in its own line of work: Meridian's heading needle, Axiom's lit facets.
  let moment={},needleAngle=null,needleShow=0,needleTarget=0;
  let scanPhase=0,needleMoving=false,wakeAt=-1,lastJumps=null,tallyCount=0,tallyFresh=0,mapShow=0,otherMoving=false;
  function updateNeedle(dt){
    if(!needle)return;
    // On a route with the drive charging, the next star, bright; at rest, home
    // (or the core when home is close by), dimmer. Hidden without a position.
    const next=Number(moment.route?.bearing),home=Number(moment.heading?.home),core=Number(moment.heading?.core);
    const far=Number(moment.heading?.home_ly)>=20;
    const charging=Number.isFinite(next)&&state==="charging";
    const bearing=charging?next:far&&Number.isFinite(home)?home:Number.isFinite(core)?core:NaN;
    const wanted=Number.isFinite(bearing)?(charging?1:.45):0;
    needleTarget=wanted;
    const rate=reduced?1:1-Math.exp(-dt*4);
    if(wanted){
      const goal=-bearing*Math.PI/180;
      if(needleAngle===null||reduced)needleAngle=goal;
      else{const turn=Math.atan2(Math.sin(goal-needleAngle),Math.cos(goal-needleAngle));needleAngle+=turn*rate;}
    }
    needleShow+=(wanted-needleShow)*rate;if(Math.abs(wanted-needleShow)<.01)needleShow=wanted;
    if(!wanted){needleMoving=needleShow!==0;needle.visible=needleShow>0;needleMaterial.uniforms.uOpacity.value=needleShow;return;}
    needleMoving=needleShow!==wanted||(wanted&&Math.abs(Math.atan2(Math.sin(-bearing*Math.PI/180-needleAngle),Math.cos(-bearing*Math.PI/180-needleAngle)))>.002);
    needle.visible=needleShow>0;needle.rotation.z=needleAngle||0;needleMaterial.uniforms.uOpacity.value=needleShow;
  }
  function updateOwn(dt){
    const rate=reduced?1:1-Math.exp(-dt*5);
    otherMoving=false;
    if(meridian&&wake){
      // The wake: a ripple out across the rings for each jump.
      if(wakeAt>=0){wakeAt=reduced?-1:wakeAt+dt/1.6;if(wakeAt>=1)wakeAt=-1;else otherMoving=true;}
      wake.material.uniforms.uWake.value=wakeAt;
    }
    if(axiom&&tally){
      const bodies=moment.scan?.bodies||[];
      const count=Math.min(60,Math.max(bodies.length,Number(moment.scan?.found)||0));
      if(count>tallyCount)tallyFresh=1;
      tallyCount=count;
      tallyFresh=reduced?0:Math.max(0,tallyFresh-dt*1.5);
      if(tallyFresh>0)otherMoving=true;
      tally.material.uniforms.uCount.value=tallyCount;tally.material.uniforms.uFresh.value=tallyFresh;
      const wanted=bodies.length?1:0;
      mapShow+=(wanted-mapShow)*rate;if(Math.abs(wanted-mapShow)<.01)mapShow=wanted;else otherMoving=true;
      bodyMap.material.uniforms.uMapShow.value=mapShow;
    }
  }
  function placeBodies(){
    if(!bodyMap)return;
    const bodies=(moment.scan?.bodies||[]).slice(0,48);
    const KINDS={star:0,gas:1,water:2,earthlike:3,ammonia:4,metal:5,icy:6};
    const positions=bodyMap.geometry.getAttribute("position"),info=bodyMap.geometry.getAttribute("aBody");
    bodies.forEach(([ls,kind],i)=>{
      // Clear of the crystal, out to the scale: nearer bodies inside, distant ones out.
      const r=.84+.08*Math.min(1,Math.log10(Math.max(0,Number(ls)||0)+1)/5.5);
      info.setXYZW(i,r,i*2.39996,KINDS[kind]??7,kind==="star"?11:kind==="gas"?9:7);positions.setXYZ(i,0,0,0);
    });
    info.needsUpdate=true;positions.needsUpdate=true;bodyMap.geometry.setDrawRange(0,bodies.length);
  }
  function schedule(){if(!frame&&!disposed&&visible&&!document.hidden)frame=requestAnimationFrame(draw);}
  function changed(){dirty=true;schedule();}
  function resize(){const rect=canvas.getBoundingClientRect();if(!rect.width||!rect.height)return;
    renderer.setSize(rect.width,rect.height,false);camera.left=-extent*rect.width/rect.height;camera.right=-camera.left;camera.updateProjectionMatrix();
    uniforms.uScale.value=clamp(rect.width/256,.4,1.5);reactor?.resize(rect.width,rect.height);changed();}
  function draw(now){
    frame=0;if(disposed||!visible||document.hidden)return;
    const active=!reduced&&(idle||state!=="idle"||pose.attention>0||moods.settling||needleMoving||otherMoving);
    if(!active&&!dirty)return;if(now-last<1000/frameRate-.7){schedule();return;}
    const dt=clamp((now-last)/1000,0,.12);last=now;dirty=false;
    pose=life.step(dt,{state,idle,reduced,focus,intensity:activity});if(pose.active)time+=dt*activity;
    const energy=state==="speaking"?level:state==="listening"?level*.6:state==="charging"?.5:0;
    uniforms.uTime.value=time;uniforms.uEnergy.value=energy;
    uniforms.uIdle.value=idle?1:0;
    uniforms.uScan.value=state==="working"||state==="listening"?1:0;
    uniforms.uColour.value.set(state==="alert"?"#ff7855":accent);
    uniforms.uOther.value.set(state==="alert"?"#ffbd99":secondary);
    rotor.rotation.z=time*(portrait?-.24:.30);counter.rotation.z=time*(portrait?.33:-.23);
    inner.rotation.x=portrait?0:.24*Math.sin(time*.6);
    const drift=idle&&!reduced?1:0;
    field.rotation.y=portrait?pose.x*.23+drift*Math.sin(time*.55)*.13*(focus==="off"?0:1):pose.x*.16+drift*Math.sin(time*.5)*.30;
    field.rotation.x=-pose.y*.12+drift*Math.sin(time*.72)*(portrait?(focus==="off"?0:.045):.16);
    field.rotation.z=portrait?0:time*.065;
    field.scale.setScalar(1+drift*Math.sin(time*1.25)*(portrait?.012:.025));
    field.position.set(pose.x*.02,pose.y*.02,0);
    moods.step(dt,reduced);
    const {joy,worry,sad,curious}=expression;
    uniforms.uMood.value.set(joy,worry,sad,curious);
    reactor?.update({state,clock:time,level:state==="speaking"?level:state==="listening"?level*.6:0,
      animated:pose.active,pulse:pose.pulse,expression,scan:moment.scan||null});
    if(portrait){
      const target=speechLevel!==null&&!reduced?Math.pow(clamp(speechLevel*1.65),.75):0;
      mouthOpen=speechLevel===null||reduced?0:mouthOpen+(target-mouthOpen)*(1-Math.exp(-dt*(target>mouthOpen?24:18)));
      if(mouthOpen<.001)mouthOpen=0;
      uniforms.uMouth.value=mouthOpen;
    }
    if(meridian){
      // Meridian: a smile or a frown, a tilt when curious, a dip when downcast
      // (held level with Fixed focus), rings drawn in and the scan quicker when wary.
      uniforms.uSmile.value=joy-worry*.5-sad*1.4;
      const tracking=!reduced&&focus!=="off";
      field.rotation.z+=tracking?curious*.08:0;field.rotation.x+=tracking?sad*.09:0;
      field.position.y-=sad*.025;
      rings.scale.setScalar(1-worry*.03);
      updateNeedle(dt);
    }
    updateOwn(dt);
    portraitLayer?.update({clock:time,pose,mouthOpen,reduced,focus,animated:pose.active,expression,scan:moment.scan||null,bearing:needleAngle,bearingVisible:needleShow>0});
    halo?.update({clock:time,reduced,animated:pose.active});
    scanPhase+=dt*activity*(1+worry*1.6);
    scan.position.y=Math.sin(scanPhase*.95)*.67;
    scan.visible=false;
    outer.scale.setScalar(1+(pose.pulse||0)*.015);
    if(finish)drawCalls=finish.render(scene,camera);else{renderer.render(scene,camera);drawCalls=renderer.info.render.calls;}frames++;if(pose.active||moods.settling||needleMoving||otherMoving)schedule();
  }
  const observer=new ResizeObserver(resize);observer.observe(canvas);
  function visibility(){if(document.hidden){cancelAnimationFrame(frame);frame=0;}else changed();}
  document.addEventListener("visibilitychange",visibility);resize();schedule();
  return {
    setState(value,valueLevel=0,spokenLevel=null){
      const next=clamp(Number(valueLevel)||0),spoken=spokenLevel===null?null:clamp(Number(spokenLevel)||0);
      if(state!==value||Math.abs(next-level)>.004||spoken!==speechLevel){moods.state(value);state=value;level=next;speechLevel=spoken;changed();}
    },
    setContext(model){
      const moved=life.context(model),felt=moods.context(model);
      const next=model?.moment&&typeof model.moment==="object"?model.moment:{};
      // 5.7.7: service pips on the bezel, from your standing with this officer.
      const pips=Math.max(0,Math.min(4,Math.round(Number(next.service)||0)));
      if(pips!==service.value){service.value=pips;changed();}
      const fresh=JSON.stringify(next)!==JSON.stringify(moment);
      if(fresh){
        const jumps=Number(next.jumps)||0;
        if(meridian&&lastJumps!==null&&jumps>lastJumps&&!reduced)wakeAt=0;
        lastJumps=jumps;
        const bodiesChanged=JSON.stringify(next.scan?.bodies||[])!==JSON.stringify(moment.scan?.bodies||[]);
        moment=next;
        if(bodiesChanged)placeBodies();
      }
      if(moved||felt||fresh)changed();
    },
    setColour(value,highlight=signature.secondary){if(/^#[0-9a-f]{6}$/i.test(value)&&/^#[0-9a-f]{6}$/i.test(highlight)&&(accent!==value||secondary!==highlight)){accent=value;secondary=highlight;changed();}},
    setFocus(value){const next=["off","tracking","expressive"].includes(value)?value:"tracking";if(focus!==next){focus=next;changed();}},
    setActivity(value){const next={calm:.5,standard:1,alive:1.6}[value]||1;if(activity!==next){activity=next;changed();}},
    setMotion(value){if(idle!==Boolean(value)){idle=Boolean(value);changed();}},
    setReducedMotion(value){if(reduced!==Boolean(value)){reduced=Boolean(value);changed();}},
    setFrameRate(value){const next=[15,24,30,60].includes(Number(value))?Number(value):30;if(frameRate!==next){frameRate=next;changed();}},
    setVisible(value){if(visible!==Boolean(value)){visible=Boolean(value);if(!visible){cancelAnimationFrame(frame);frame=0;}else changed();}},
    inspect(){return {...pose,identity,design:lyra?"robot-companion":axiom?"precision-android":"navigator-android",frames,state,reduced,idle,focus,frameRate,time,accent,secondary,intensity:activity,
      width:canvas.clientWidth,height:canvas.clientHeight,drawCalls,reactor:reactor?.inspect()||null,mouthOpen,mood:moods.mood,expression:{...expression},expressing:moods.settling,smileCurve:uniforms.uSmile.value,
      needle:needle?{visible:needle.visible,angle:needleAngle,show:needleShow,target:needleTarget}:null,
      wake:wake?wakeAt:null,
      tally:tally?{count:tallyCount,fresh:tallyFresh}:null,map:bodyMap?{bodies:bodyMap.geometry.drawRange.count,show:mapShow}:null,
      moving:needleMoving||otherMoving,...portraitLayer?.inspect()};},
    destroy(){disposed=true;portraitLayer?.destroy();finish?.destroy();cancelAnimationFrame(frame);observer.disconnect();document.removeEventListener("visibilitychange",visibility);
      const geometries=new Set(),materials=new Set();scene.traverse(object=>{if(object.geometry)geometries.add(object.geometry);if(object.material)materials.add(object.material);});
      geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());renderer.dispose();},
  };
}
