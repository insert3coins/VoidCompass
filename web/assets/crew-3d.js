import * as THREE from "../galactic_map/vendor/three.module.min.js";
import {createAsterMotion} from "./aster-3d.js";
import {createCompanionFrame, COMPANION_EXTENT} from "./companion-frame.js";
import {SIGNATURES} from "./companion-colours.js";
import {createCompanionCore} from "./companion-core.js";
import {addLyraRobot, addLyraHalo} from "./lyra-robot.js";

const TAU = Math.PI * 2;
const clamp = (n, lo=0, hi=1) => Math.max(lo, Math.min(hi, n));

// Original procedural displays: no image plates, opaque backdrops or character likenesses.
export function createCrewDisplay(canvas, identity) {
  const lyra = identity === "lyra";
  const portrait = identity === "meridian" || lyra;
  const signature = SIGNATURES[identity];
  const renderer = new THREE.WebGLRenderer({canvas, alpha:true, antialias:true, premultipliedAlpha:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0, 0); renderer.outputColorSpace = THREE.SRGBColorSpace;
  const extent = COMPANION_EXTENT, scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-extent,extent,extent,-extent,.1,20); camera.position.z = 5;
  const rig = new THREE.Group(), field = new THREE.Group(), rings = new THREE.Group();
  scene.add(rig); rig.add(field,rings);
  const uniforms = {uTime:{value:0},uEnergy:{value:0},uScan:{value:0},uIdle:{value:1},uColour:{value:new THREE.Color(signature.primary)},
    uOther:{value:new THREE.Color(signature.secondary)},uDpr:{value:renderer.getPixelRatio()},uScale:{value:1},uMouth:{value:0},uFace:{value:0}};
  const reactor=portrait?null:createCompanionCore({identity,time:uniforms.uTime,energy:uniforms.uEnergy,
    colour:uniforms.uColour,highlight:uniforms.uOther});
  if(reactor){reactor.group.position.z=.45;rig.add(reactor.group);}
  scene.add(createCompanionFrame({colour:uniforms.uColour,energy:uniforms.uEnergy,opening:portrait?0:.48}));
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
  for(let i=0;i<6;i++) rotorPaths.push(...arc(.94,i*TAU/6+.06,(i+(i===0?.86:.58))*TAU/6));
  lines(rotorPaths,rotor);
  const counter = new THREE.Group(); rings.add(counter);
  const counterPaths=[];
  for(let i=0;i<3;i++) counterPaths.push(...arc(.875,i*TAU/3+.12,(i+.35)*TAU/3));
  lines(counterPaths,counter);
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
  const halo=lyra?addLyraHalo(rings,uniforms):null;
  if(halo)for(const object of [rotor,counter,inner,sweep])object.visible=false;
  let portraitLayer=null;
  if(lyra) {
    portraitLayer=addLyraRobot(field,uniforms,renderer,scene);
  } else if(portrait) {
    // An anonymous instrument portrait: elliptical skull, modeled cheeks and a subtle nose ridge.
    function head(lat,a) {
      const y=Math.cos(lat)*.73, width=Math.pow(Math.sin(lat),.72)*(.39+.035*Math.cos(lat));
      const x=Math.sin(a)*width;
      let z=Math.cos(a)*Math.sin(lat)*.31;
      if(Math.cos(a)>0){
        z+=.17*Math.exp(-Math.pow(x/.09,2)-Math.pow((y+.015)/.22,2));
        z-=.07*Math.exp(-Math.pow((Math.abs(x)-.16)/.085,2)-Math.pow((y-.14)/.075,2));
        z+=.025*Math.exp(-Math.pow((Math.abs(x)-.21)/.12,2)-Math.pow((y+.07)/.12,2));
      }
      return [x,y,z];
    }
    const face=[];
    for(let j=1;j<30;j++)for(let i=0;i<72;i++) face.push(...head(j/30*Math.PI,-Math.PI/2+i/72*Math.PI),...head(j/30*Math.PI,-Math.PI/2+(i+1)/72*Math.PI));
    for(let i=0;i<=36;i++)for(let j=0;j<60;j++)face.push(...head(j/60*Math.PI,-Math.PI/2+i/36*Math.PI),...head((j+1)/60*Math.PI,-Math.PI/2+i/36*Math.PI));
    lines(face,field,shader(lineVertex,lineFragment,{uOpacity:{value:.68},uFace:{value:1}}));
    const silhouette=[];
    for(const side of [-1,1])for(let j=0;j<60;j++)silhouette.push(...head(j/60*Math.PI,side*Math.PI/2),...head((j+1)/60*Math.PI,side*Math.PI/2));
    const details=[...silhouette];
    const curve = (fn,n=28) => {for(let i=0;i<n;i++) details.push(...fn(i/n),...fn((i+1)/n));};
    for(const sign of [-1,1]) {
      curve(t=>[sign*(.08+t*.17),.18+Math.sin(t*Math.PI)*.025,.287]);
      curve(t=>[sign*(.09+t*.14),.115-Math.sin(t*Math.PI)*.018,.275]);
      curve(t=>[sign*(.393+Math.sin(t*Math.PI)*.038),.13-t*.26,.015]);
    }
    curve(t=>[(t-.5)*.16,-.082-Math.sin(t*Math.PI)*.022,.405]);
    lines(details,field);
    const lips=new THREE.Mesh(new THREE.PlaneGeometry(.34,.22),new THREE.ShaderMaterial({
      uniforms,
      vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
      fragmentShader:`varying vec2 vUv;uniform vec3 uColour,uOther;uniform float uMouth;
        void main(){vec2 p=(vUv-.5)*vec2(.34,.22);float x=abs(p.x)/.135;if(x>1.0)discard;
          float curve=sqrt(max(0.0,1.0-x*x)),opening=uMouth*.075;
          float upper=.003+curve*opening*.55+sin(x*3.14159265)*.003;
          float lower=-.003-curve*opening;
          float aa=max(fwidth(p.y),.0015);
          float lip=1.0-smoothstep(.002,.002+aa,min(abs(p.y-upper),abs(p.y-lower)));
          float cavity=smoothstep(lower-aa,lower+aa,p.y)*(1.0-smoothstep(upper-aa,upper+aa,p.y));
          gl_FragColor=vec4(mix(vec3(.004,.009,.016),mix(uColour,uOther,.25),lip),max(cavity*.94,lip*.95));
          #include <colorspace_fragment>
        }`,
      transparent:true,depthWrite:false,blending:THREE.NormalBlending,side:THREE.DoubleSide,forceSinglePass:true,
    }));
    lips.position.set(0,-.245,.43);lips.renderOrder=2;field.add(lips);
    lines([-.18,-.69,0,-.21,-.8,0,-.21,-.8,0,-.55,-.9,0,.18,-.69,0,.21,-.8,0,.21,-.8,0,.55,-.9,0],field);
    const brackets=[];
    for(const sign of [-1,1])for(const y of [-.42,.42])brackets.push(sign*.66,y,0,sign*.73,y,0,sign*.73,y,0,sign*.73,y+Math.sign(y)*.12,0);
    lines(brackets,rings);
  } else {
    const seeds=[],positions=[];
    for(let i=0;i<5400;i++){
      const random=n=>{const v=Math.sin((i+1)*n)*43758.5453;return v-Math.floor(v);};
      seeds.push(random(12.9898),random(39.346),random(73.156),random(91.217)); positions.push(0,0,0);
    }
    const geometry=new THREE.BufferGeometry(); geometry.setAttribute("position",new THREE.Float32BufferAttribute(positions,3));
    geometry.setAttribute("aSeed",new THREE.Float32BufferAttribute(seeds,4));
    const material=shader(`attribute vec4 aSeed;uniform float uTime,uEnergy,uDpr,uScale;varying float vLight,vTint;
      void main(){float a=aSeed.x*6.2831853+uTime*(.22+aSeed.z*.045);float b=aSeed.y*6.2831853+uTime*.45;
        float wave=sin(a*5.0+uTime*1.2)*.035+sin(a*11.0-uTime*.8)*.018;
        float tube=.12+.045*sin(a*3.0+uTime*.8)+uEnergy*.06;
        float r=.77+cos(b)*tube+wave;
        vec3 p=vec3(cos(a)*r,sin(a)*r,sin(b)*tube*1.8);
        p.xy*=1.0+uEnergy*.025*sin(a*8.0-uTime*3.0);
        gl_Position=projectionMatrix*modelViewMatrix*vec4(p,1.0);
        gl_PointSize=max(.8,(.65+aSeed.w*1.9+uEnergy*.65)*uScale)*uDpr;
        float travelling=.5+.5*sin(a*3.0-uTime*1.7);
        vLight=(.22+.65*aSeed.w)*(.5+travelling*.7);vTint=.5+.5*sin(a-uTime*.65);
      }`,`uniform vec3 uColour,uOther;varying float vLight,vTint;
      void main(){float d=length(gl_PointCoord-.5);if(d>.5)discard;
        gl_FragColor=vec4(mix(uColour,uOther,vTint*.75),(1.0-smoothstep(.05,.5,d))*vLight);
        #include <colorspace_fragment>
      }`);
    const cloud=new THREE.Points(geometry,material);cloud.frustumCulled=false;field.add(cloud);
    const orbit=lines(arc(.77,0,TAU),field);orbit.rotation.x=.55;
    const orbit2=lines(arc(.79,0,TAU),field);orbit2.rotation.x=-.55;
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
  function schedule(){if(!frame&&!disposed&&visible&&!document.hidden)frame=requestAnimationFrame(draw);}
  function changed(){dirty=true;schedule();}
  function resize(){const rect=canvas.getBoundingClientRect();if(!rect.width||!rect.height)return;
    renderer.setSize(rect.width,rect.height,false);camera.left=-extent*rect.width/rect.height;camera.right=-camera.left;camera.updateProjectionMatrix();
    uniforms.uScale.value=clamp(rect.width/256,.4,1.5);reactor?.resize(rect.width,rect.height);changed();}
  function draw(now){
    frame=0;if(disposed||!visible||document.hidden)return;
    const active=!reduced&&(idle||state!=="idle"||pose.attention>0);
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
    reactor?.update({state,clock:time,level:state==="speaking"?level:state==="listening"?level*.6:0,
      animated:pose.active,pulse:pose.pulse});
    if(portrait){
      const target=speechLevel!==null&&!reduced?Math.pow(clamp(speechLevel*1.65),.75):0;
      mouthOpen=speechLevel===null||reduced?0:mouthOpen+(target-mouthOpen)*(1-Math.exp(-dt*(target>mouthOpen?24:18)));
      if(mouthOpen<.001)mouthOpen=0;
      uniforms.uMouth.value=mouthOpen;
    }
    portraitLayer?.update({clock:time,pose,mouthOpen,reduced,focus,animated:pose.active});
    halo?.update({clock:time,reduced,animated:pose.active});
    scan.position.y=Math.sin(time*.95)*.67;scan.visible=portrait&&!lyra&&(idle||state==="working"||state==="listening");
    outer.scale.setScalar(1+(pose.pulse||0)*.015);
    renderer.render(scene,camera);frames++;if(pose.active)schedule();
  }
  const observer=new ResizeObserver(resize);observer.observe(canvas);
  function visibility(){if(document.hidden){cancelAnimationFrame(frame);frame=0;}else changed();}
  document.addEventListener("visibilitychange",visibility);resize();schedule();
  return {
    setState(value,valueLevel=0,spokenLevel=null){
      const next=clamp(Number(valueLevel)||0),spoken=spokenLevel===null?null:clamp(Number(spokenLevel)||0);
      if(state!==value||Math.abs(next-level)>.004||spoken!==speechLevel){state=value;level=next;speechLevel=spoken;changed();}
    },
    setContext(model){if(life.context(model))changed();},
    setColour(value,highlight=signature.secondary){if(/^#[0-9a-f]{6}$/i.test(value)&&/^#[0-9a-f]{6}$/i.test(highlight)&&(accent!==value||secondary!==highlight)){accent=value;secondary=highlight;changed();}},
    setFocus(value){const next=["off","tracking","expressive"].includes(value)?value:"tracking";if(focus!==next){focus=next;changed();}},
    setActivity(value){const next={calm:.5,standard:1,alive:1.6}[value]||1;if(activity!==next){activity=next;changed();}},
    setMotion(value){if(idle!==Boolean(value)){idle=Boolean(value);changed();}},
    setReducedMotion(value){if(reduced!==Boolean(value)){reduced=Boolean(value);changed();}},
    setFrameRate(value){const next=[15,24,30,60].includes(Number(value))?Number(value):30;if(frameRate!==next){frameRate=next;changed();}},
    setVisible(value){if(visible!==Boolean(value)){visible=Boolean(value);if(!visible){cancelAnimationFrame(frame);frame=0;}else changed();}},
    inspect(){return {...pose,identity,design:lyra?"robot-companion":portrait?"wireframe-portrait":"particle-torus",frames,state,reduced,idle,focus,frameRate,time,accent,secondary,intensity:activity,
      width:canvas.clientWidth,height:canvas.clientHeight,drawCalls:renderer.info.render.calls,reactor:reactor?.inspect()||null,mouthOpen,...portraitLayer?.inspect()};},
    destroy(){disposed=true;portraitLayer?.destroy();cancelAnimationFrame(frame);observer.disconnect();document.removeEventListener("visibilitychange",visibility);
      const geometries=new Set(),materials=new Set();scene.traverse(object=>{if(object.geometry)geometries.add(object.geometry);if(object.material)materials.add(object.material);});
      geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());renderer.dispose();},
  };
}
